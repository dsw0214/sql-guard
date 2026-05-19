from typing import Dict, List, Optional

from app.config import AppConfig
from .ai_client import analyze_sql_with_ai
from .rule_engine import analyze_statement
from .sql_parser import split_sql_statements_with_meta


LEVEL_WEIGHT: Dict[str, int] = {
    "P0": 40,
    "P1": 25,
    "P2": 12,
    "P3": 6,
}

LEVEL_ORDER: Dict[str, int] = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def risk_score(
    issues: List[Dict],
    statement_count: int = 0,
    table_count: int = 0,
    unique_rule_count: int = 0,
) -> int:
    if not issues:
        return 0
    score = sum(LEVEL_WEIGHT.get(i.get("level", "P3"), 6) for i in issues)

    has_p0 = any(i.get("level") == "P0" for i in issues)
    p1_count = sum(1 for i in issues if i.get("level") == "P1")
    if has_p0:
        score += 15
    if p1_count >= 2:
        score += 10

    score += min(15, statement_count * 2)
    score += min(10, table_count * 2)
    score += min(10, unique_rule_count)
    return min(100, score)


def _normalize_level(level: str) -> str:
    value = (level or "").upper().strip()
    if value in {"P0", "P1", "P2", "P3"}:
        return value
    return "P3"


def _normalize_policy(request_policy: Optional[Dict]) -> Dict:
    env_policy = AppConfig.rule_policy_view()
    policy = {
        "enabled_rules": set(env_policy.get("enabled_rules", [])),
        "disabled_rules": set(env_policy.get("disabled_rules", [])),
        "enabled_categories": set(env_policy.get("enabled_categories", [])),
        "severity_overrides": dict(env_policy.get("severity_overrides", {})),
    }

    if not request_policy:
        return policy

    for rid in request_policy.get("enabled_rules", []) or []:
        policy["enabled_rules"].add(rid)
    for rid in request_policy.get("disabled_rules", []) or []:
        policy["disabled_rules"].add(rid)
    for cat in request_policy.get("enabled_categories", []) or []:
        policy["enabled_categories"].add(cat)
    for rid, level in (request_policy.get("severity_overrides", {}) or {}).items():
        policy["severity_overrides"][rid] = _normalize_level(str(level))

    return policy


def _normalize_suppressions(request_suppressions: Optional[List[Dict]]) -> List[Dict]:
    suppressions = list(AppConfig.default_suppressions())
    for item in request_suppressions or []:
        if not item.get("rule_id"):
            continue
        suppressions.append(
            {
                "rule_id": str(item.get("rule_id")),
                "statement_index": item.get("statement_index"),
                "scope": (item.get("scope") or "global"),
            }
        )
    return suppressions


def _is_suppressed(issue: Dict, suppressions: List[Dict]) -> bool:
    for item in suppressions:
        if item.get("rule_id") != issue.get("rule_id"):
            continue
        if item.get("scope") == "statement":
            if item.get("statement_index") != issue.get("statement_index"):
                continue
        return True
    return False


def _apply_policy(issues: List[Dict], policy: Dict, suppressions: List[Dict]) -> List[Dict]:
    result: List[Dict] = []
    enabled_rules = policy.get("enabled_rules", set())
    disabled_rules = policy.get("disabled_rules", set())
    enabled_categories = policy.get("enabled_categories", set())
    severity_overrides = policy.get("severity_overrides", {})

    for item in issues:
        rule_id = item.get("rule_id")
        category = item.get("category")

        if enabled_rules and rule_id and rule_id not in enabled_rules:
            continue
        if rule_id in disabled_rules:
            continue
        if enabled_categories and category and category not in enabled_categories:
            continue
        if _is_suppressed(item, suppressions):
            continue

        level = severity_overrides.get(rule_id)
        if level:
            item = {**item, "level": level, "severity": level}
        result.append(item)

    return result


def _issue_key(item: Dict) -> str:
    rule_id = item.get("rule_id") or ""
    message = (item.get("message") or "").strip()
    stmt_idx = item.get("statement_index") or 0
    return f"{rule_id}|{message}|{stmt_idx}"


def _baseline_diff(current: List[Dict], baseline: Optional[List[Dict]]) -> Dict:
    baseline_items = baseline or []
    current_map = {_issue_key(i): i for i in current}
    baseline_map = {_issue_key(i): i for i in baseline_items}

    new_keys = [k for k in current_map if k not in baseline_map]
    resolved_keys = [k for k in baseline_map if k not in current_map]
    unchanged_keys = [k for k in current_map if k in baseline_map]

    return {
        "new_issue_count": len(new_keys),
        "resolved_issue_count": len(resolved_keys),
        "unchanged_issue_count": len(unchanged_keys),
        "new_issues": [current_map[k] for k in new_keys],
        "resolved_issues": [baseline_map[k] for k in resolved_keys],
    }


def _evaluate_ci_gate(
    gate: Optional[Dict],
    issues: List[Dict],
    score: int,
    ai_error: Optional[str],
    baseline: Dict,
) -> Dict:
    if not gate:
        return {"enabled": False, "passed": True, "blocked_reasons": []}

    blocked_reasons: List[str] = []
    effective_issues = baseline.get("new_issues", []) if gate.get("only_new_issues") else issues

    max_allowed_severity = gate.get("max_allowed_severity")
    if max_allowed_severity:
        threshold = LEVEL_ORDER.get(str(max_allowed_severity).upper(), 3)
        breach = any(LEVEL_ORDER.get((i.get("level") or "P3").upper(), 3) < threshold for i in effective_issues)
        if breach:
            blocked_reasons.append(f"severity>{max_allowed_severity}")

    max_score = gate.get("max_score")
    if max_score is not None and score > int(max_score):
        blocked_reasons.append(f"score>{max_score}")

    max_total_issues = gate.get("max_total_issues")
    if max_total_issues is not None and len(effective_issues) > int(max_total_issues):
        blocked_reasons.append(f"issues>{max_total_issues}")

    if gate.get("fail_on_ai_error") and ai_error:
        blocked_reasons.append("ai-error")

    return {
        "enabled": True,
        "passed": len(blocked_reasons) == 0,
        "blocked_reasons": blocked_reasons,
        "metrics": {
            "effective_issue_count": len(effective_issues),
            "score": score,
            "ai_error": bool(ai_error),
            "only_new_issues": bool(gate.get("only_new_issues")),
        },
    }


def dedupe_issues(issues: List[Dict], max_issues: int) -> List[Dict]:
    seen = set()
    merged: List[Dict] = []
    for item in issues:
        key = (
            item.get("rule_id") or f"fallback:{item.get('level', 'P3')}:{item.get('message', '')}",
            (item.get("sql_fragment") or "").strip().lower()[:400],
            item.get("statement_index"),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)

    level_priority = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    merged.sort(key=lambda x: level_priority.get(x.get("level", "P3"), 3))
    return merged[:max_issues]


async def analyze_sql(
    sql: str,
    mode: str,
    dialect: Optional[str],
    max_issues: int,
    policy: Optional[Dict] = None,
    suppressions: Optional[List[Dict]] = None,
    baseline_issues: Optional[List[Dict]] = None,
    ci_gate: Optional[Dict] = None,
) -> Dict:
    statement_meta = split_sql_statements_with_meta(sql, dialect)
    rule_issues: List[Dict] = []
    tables: List[str] = []

    if mode in {"rule", "hybrid"}:
        for item in statement_meta:
            stmt_issues, stmt_tables = analyze_statement(
                item["statement"],
                dialect,
                statement_index=item.get("statement_index"),
                line_start=item.get("line_start"),
                line_end=item.get("line_end"),
            )
            rule_issues.extend(stmt_issues)
            tables.extend(stmt_tables)

    ai_issues: List[Dict] = []
    ai_error: Optional[str] = None

    if mode in {"ai", "hybrid"}:
        ai_issues, ai_error = await analyze_sql_with_ai(sql, dialect=dialect, max_issues=max_issues)

    merged_issues = rule_issues + ai_issues
    effective_policy = _normalize_policy(policy)
    effective_suppressions = _normalize_suppressions(suppressions)
    policy_issues = _apply_policy(merged_issues, effective_policy, effective_suppressions)
    issues = dedupe_issues(policy_issues, max_issues=max_issues)
    unique_rule_count = len({i.get("rule_id") for i in issues if i.get("rule_id")})

    score = risk_score(
        issues,
        statement_count=len(statement_meta),
        table_count=len(set(tables)),
        unique_rule_count=unique_rule_count,
    )
    baseline = _baseline_diff(issues, baseline_issues)
    gate_result = _evaluate_ci_gate(ci_gate, issues, score, ai_error, baseline)

    return {
        "sql": sql,
        "mode": mode,
        "issues": issues,
        "score": score,
        "stats": {
            "statement_count": len(statement_meta),
            "table_count": len(set(tables)),
            "rule_issue_count": len(rule_issues),
            "ai_issue_count": len(ai_issues),
            "total_issue_count": len(issues),
            "unique_rule_count": unique_rule_count,
        },
        "tables": sorted(set(tables)),
        "policy": {
            "enabled_rules": sorted(effective_policy.get("enabled_rules", set())),
            "disabled_rules": sorted(effective_policy.get("disabled_rules", set())),
            "enabled_categories": sorted(effective_policy.get("enabled_categories", set())),
            "severity_overrides": effective_policy.get("severity_overrides", {}),
            "suppression_count": len(effective_suppressions),
        },
        "baseline": baseline,
        "ci_gate": gate_result,
        "ai": {
            "enabled": mode in {"ai", "hybrid"},
            "error": ai_error,
        },
    }
