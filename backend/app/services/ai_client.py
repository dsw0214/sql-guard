import json
import re
from typing import Dict, List, Optional, Tuple

import httpx

from app.config import AppConfig


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
    system_prompt = (
        "你是资深数据库审核助手。"
        "请分析 SQL 的安全性与性能风险，并仅返回 JSON 数组。"
        "每个元素格式: {\"level\":\"P0|P1|P2|P3\",\"message\":\"...\",\"hint\":\"...\"}。"
        "不要输出任何额外文本。"
    )
    user_prompt = (
        f"SQL 方言: {dialect or 'generic'}\\n"
        f"最大问题数: {max_issues}\\n"
        f"SQL:\\n{sql}"
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
        if AppConfig.ai_provider() == "ollama":
            content, err = await call_ollama(system_prompt, user_prompt)
        else:
            content, err = await call_openai_compatible(body)

        if err:
            return [], err

        raw_issues = extract_json_array(content)
        issues: List[Dict] = []
        for item in raw_issues[:max_issues]:
            level = str(item.get("level", "P3")).upper()
            if level not in {"P0", "P1", "P2", "P3"}:
                level = "P3"

            issues.append(
                {
                    "level": level,
                    "message": str(item.get("message", "AI 检测发现潜在风险")).strip(),
                    "source": "ai",
                    "hint": str(item.get("hint", "")).strip() or None,
                }
            )
        return issues, None
    except Exception as exc:
        msg = str(exc).strip() or exc.__class__.__name__
        return [], f"AI 请求异常: {msg}"
