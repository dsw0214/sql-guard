import json
import re
from typing import Dict, List, Optional, Tuple

import httpx

from app.config import AppConfig
from .sql_parser import split_sql_statements

ALLOWED_LEVELS = {"P0", "P1", "P2", "P3"}
_CREATE_TABLE_PREFIX_RE = re.compile(
    r"^\s*create\s+(?:temporary\s+)?table\s+(?:if\s+not\s+exists\s+)?(?:`[^`]+`|\w+(?:\.\w+)*)\s+",
    re.IGNORECASE,
)


def _normalize_sql_for_hash(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip().lower()


def _prepare_sql_for_ai(sql: str, dialect: Optional[str]) -> Tuple[str, Dict[str, int]]:
    """Prepare SQL payload for AI by deduping repeated CREATE TABLE structures.

    This is intentionally lightweight to reduce prompt size and generation time
    on sharded DDL files where only table names differ.
    """
    meta = {
        "original_char_count": len(sql),
        "prepared_char_count": len(sql),
        "total_statement_count": 0,
        "retained_statement_count": 0,
        "deduped_create_statement_count": 0,
        "truncated": 0,
    }

    statements = split_sql_statements(sql, dialect)
    if not statements:
        max_chars = AppConfig.ai_max_sql_chars()
        trimmed = sql if len(sql) <= max_chars else sql[:max_chars]
        meta["prepared_char_count"] = len(trimmed)
        meta["truncated"] = 1 if len(sql) > max_chars else 0
        return trimmed, meta

    meta["total_statement_count"] = len(statements)
    dedupe_enabled = AppConfig.ai_dedupe_create_structures()
    retained: List[str] = []
    create_seen: Dict[str, int] = {}

    for stmt in statements:
        normalized_stmt = stmt.strip()
        if not normalized_stmt:
            continue

        if dedupe_enabled:
            m = _CREATE_TABLE_PREFIX_RE.match(normalized_stmt)
            if m:
                canonical_stmt = "CREATE TABLE __T__ " + normalized_stmt[m.end():]
                stmt_key = "create:" + _normalize_sql_for_hash(canonical_stmt)
                create_seen[stmt_key] = create_seen.get(stmt_key, 0) + 1
                if create_seen[stmt_key] > 1:
                    continue

        retained.append(normalized_stmt)

    meta["retained_statement_count"] = len(retained)
    meta["deduped_create_statement_count"] = max(0, len(statements) - len(retained))

    prepared_sql = ";\n".join(retained)
    if prepared_sql and not prepared_sql.endswith(";"):
        prepared_sql = prepared_sql + ";"

    max_chars = AppConfig.ai_max_sql_chars()
    if len(prepared_sql) > max_chars:
        prepared_sql = prepared_sql[:max_chars]
        meta["truncated"] = 1

    meta["prepared_char_count"] = len(prepared_sql)
    return prepared_sql, meta


def extract_json_array(text: str) -> List[Dict]:
    text = text.strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        pass

    m = re.search(r"\[[\s\S]*\]", text)
    if not m:
        return []
    try:
        parsed = json.loads(m.group(0))
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def _is_str_or_none(value: object) -> bool:
    return value is None or isinstance(value, str)


def _is_int_or_none(value: object) -> bool:
    return value is None or isinstance(value, int)


def _validate_ai_issue_schema(item: object) -> Optional[Dict]:
    if not isinstance(item, dict):
        return None

    level = item.get("level")
    message = item.get("message")
    if not isinstance(level, str) or not isinstance(message, str):
        return None

    normalized_level = level.upper().strip()
    if normalized_level not in ALLOWED_LEVELS:
        return None

    if not message.strip():
        return None

    optional_string_fields = ["hint", "evidence", "rule_id", "category", "sql_fragment"]
    if any(not _is_str_or_none(item.get(field)) for field in optional_string_fields):
        return None

    optional_int_fields = ["statement_index", "line_start", "line_end"]
    if any(not _is_int_or_none(item.get(field)) for field in optional_int_fields):
        return None

    return item


def _coerce_ai_issue(item: Dict, sql: str) -> Optional[Dict]:
    validated = _validate_ai_issue_schema(item)
    if not validated:
        return None

    raw_message = str(validated.get("message", "")).strip()
    if not raw_message:
        return None

    level = str(validated.get("level", "P3")).upper().strip()

    hint = str(validated.get("hint", "")).strip() or None
    evidence = str(validated.get("evidence", "")).strip() or raw_message
    if len(evidence) > 260:
        evidence = f"{evidence[:257]}..."

    fragment = str(validated.get("sql_fragment", "")).strip()
    if not fragment:
        fragment = sql[:260].strip()

    return {
        "level": level,
        "severity": level,
        "message": raw_message,
        "source": "ai",
        "hint": hint,
        "rule_id": str(validated.get("rule_id", "AI-GENERAL-001")).strip() or "AI-GENERAL-001",
        "category": str(validated.get("category", "ai")).strip() or "ai",
        "statement_index": validated.get("statement_index"),
        "line_start": validated.get("line_start"),
        "line_end": validated.get("line_end"),
        "sql_fragment": fragment,
        "evidence": evidence,
    }


def _fallback_ai_issues(content: str, sql: str, max_issues: int) -> List[Dict]:
    lines = [line.strip(" -\t") for line in content.splitlines() if line.strip()]
    candidates: List[str] = []
    for line in lines:
        if re.search(r"(风险|risk|slow|full\s*scan|lock|死锁|注入|drop|truncate|delete)", line, re.IGNORECASE):
            candidates.append(line)
    if not candidates and lines:
        candidates = lines[:1]

    issues: List[Dict] = []
    for text in candidates[:max_issues]:
        issues.append(
            {
                "level": "P3",
                "severity": "P3",
                "message": text[:240],
                "source": "ai",
                "hint": "AI 未按 JSON 返回，已使用回退提取，请人工复核",
                "rule_id": "AI-FALLBACK-001",
                "category": "ai",
                "statement_index": None,
                "line_start": None,
                "line_end": None,
                "sql_fragment": sql[:260].strip(),
                "evidence": text[:260],
            }
        )
    return issues


async def call_openai_compatible(body: Dict) -> Tuple[str, Optional[str]]:
    api_key = AppConfig.ai_api_key()
    if not api_key:
        return "", "未配置 SQLGUARD_AI_API_KEY，已跳过 AI 分析"

    payload = dict(body)
    payload["model"] = AppConfig.ai_model()
    payload.setdefault("temperature", AppConfig.ai_temperature())
    payload.setdefault("seed", AppConfig.ai_seed())

    timeout = AppConfig.ai_http_timeout_seconds()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{AppConfig.ai_base_url()}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except httpx.TimeoutException:
        return "", f"AI 请求超时: {timeout:.0f}s"
    except httpx.RequestError as exc:
        return "", f"AI 网络异常: {exc!s}"

    if resp.status_code >= 400:
        detail = (resp.text or "").strip()
        if detail:
            detail = detail[:240]
            return "", f"AI 请求失败: HTTP {resp.status_code} - {detail}"
        return "", f"AI 请求失败: HTTP {resp.status_code}"

    data = resp.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return content, None


async def call_ollama(system_prompt: str, user_prompt: str) -> Tuple[str, Optional[str]]:
    body = {
        "model": AppConfig.ollama_model(),
        "stream": False,
        "think": False,
        "options": {
            "temperature": AppConfig.ai_temperature(),
            "seed": AppConfig.ai_seed(),
        },
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    timeout = AppConfig.ollama_http_timeout_seconds()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{AppConfig.ollama_base_url()}/api/chat",
                headers={"Content-Type": "application/json"},
                json=body,
            )
    except httpx.TimeoutException:
        return "", f"Ollama 请求超时: {timeout:.0f}s"
    except httpx.RequestError as exc:
        return "", f"Ollama 网络异常: {exc!s}"

    if resp.status_code >= 400:
        detail = (resp.text or "").strip()
        if detail:
            detail = detail[:240]
            return "", f"Ollama 请求失败: HTTP {resp.status_code} - {detail}"
        return "", f"Ollama 请求失败: HTTP {resp.status_code}"

    data = resp.json()
    content = data.get("message", {}).get("content", "")
    return content, None


async def analyze_sql_with_ai(sql: str, dialect: Optional[str], max_issues: int) -> Tuple[List[Dict], Optional[str]]:
    prepared_sql, compact_meta = _prepare_sql_for_ai(sql, dialect)

    system_prompt = (
        "你是资深数据库审核助手。"
        "请分析 SQL 的安全性与性能风险，并仅返回 JSON 数组。"
        "每个元素格式必须是: "
        "{\"level\":\"P0|P1|P2|P3\",\"message\":\"...\",\"hint\":\"...\",\"evidence\":\"...\"}。"
        "不得输出 markdown、解释文字、代码块。"
    )
    user_prompt = (
        f"SQL 方言: {dialect or 'generic'}\\n"
        f"最大问题数: {max_issues}\\n"
        f"压缩信息: 原始长度={compact_meta['original_char_count']} 字符, "
        f"压缩后长度={compact_meta['prepared_char_count']} 字符, "
        f"总语句数={compact_meta['total_statement_count']}, "
        f"保留语句数={compact_meta['retained_statement_count']}, "
        f"去重CREATE数={compact_meta['deduped_create_statement_count']}, "
        f"是否截断={compact_meta['truncated']}\\n"
        f"SQL:\\n{prepared_sql}"
    )

    body = {
        "temperature": AppConfig.ai_temperature(),
        "seed": AppConfig.ai_seed(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    try:
        last_content = ""
        for _ in range(AppConfig.ai_max_retries()):
            if AppConfig.ai_provider() == "ollama":
                content, err = await call_ollama(system_prompt, user_prompt)
            else:
                content, err = await call_openai_compatible(body)

            if err:
                return [], err

            last_content = content or ""
            raw_issues = extract_json_array(last_content)
            issues: List[Dict] = []
            for item in raw_issues[:max_issues]:
                issue = _coerce_ai_issue(item, sql)
                if issue:
                    issues.append(issue)

            if issues:
                return issues, None

        if AppConfig.ai_schema_fallback_enabled() and last_content:
            fallback_issues = _fallback_ai_issues(last_content, sql, max_issues)
            if fallback_issues:
                return fallback_issues, "AI 返回格式不符合 JSON Schema，已使用回退提取"

        return [], "AI 返回格式不符合 JSON Schema"
    except Exception as exc:
        msg = str(exc).strip() or exc.__class__.__name__
        return [], f"AI 请求异常: {msg}"
