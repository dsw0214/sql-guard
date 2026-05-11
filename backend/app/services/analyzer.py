from typing import Dict, List, Optional

from .ai_client import analyze_sql_with_ai
from .rule_engine import analyze_statement
from .sql_parser import split_sql_statements


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
        key = (item.get("level"), item.get("message"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)

    level_priority = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    merged.sort(key=lambda x: level_priority.get(x.get("level", "P3"), 3))
    return merged[:max_issues]


async def analyze_sql(sql: str, mode: str, dialect: Optional[str], max_issues: int) -> Dict:
    statements = split_sql_statements(sql, dialect)
    rule_issues: List[Dict] = []
    tables: List[str] = []

    if mode in {"rule", "hybrid"}:
        for stmt in statements:
            stmt_issues, stmt_tables = analyze_statement(stmt, dialect)
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
            "statement_count": len(statements),
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
