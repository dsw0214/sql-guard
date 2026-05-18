from typing import Dict, List, Optional

from .ai_client import analyze_sql_with_ai
from .rule_engine import analyze_statement
from .sql_parser import split_sql_statements_with_meta


LEVEL_WEIGHT: Dict[str, int] = {
    "P0": 40,
    "P1": 25,
    "P2": 12,
    "P3": 6,
}


def risk_score(issues: List[Dict]) -> int:
    if not issues:
        return 0
    score = sum(LEVEL_WEIGHT.get(i.get("level", "P3"), 6) for i in issues)
    return min(100, score)


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


async def analyze_sql(sql: str, mode: str, dialect: Optional[str], max_issues: int) -> Dict:
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

    issues = dedupe_issues(rule_issues + ai_issues, max_issues=max_issues)

    return {
        "sql": sql,
        "mode": mode,
        "issues": issues,
        "score": risk_score(issues),
        "stats": {
            "statement_count": len(statement_meta),
            "table_count": len(set(tables)),
            "rule_issue_count": len(rule_issues),
            "ai_issue_count": len(ai_issues),
            "total_issue_count": len(issues),
        },
        "tables": sorted(set(tables)),
        "ai": {
            "enabled": mode in {"ai", "hybrid"},
            "error": ai_error,
        },
    }
