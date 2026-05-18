import re
from typing import Dict, List, Optional

from .analyzer import analyze_sql
from .sql_parser import split_sql_statements


def extract_sql_from_diff(diff_text: str, max_sql: int) -> List[str]:
    sql_lines: List[str] = []
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if not line.startswith("+"):
            continue

        content = line[1:].strip()
        if not content:
            continue
        if re.match(r"^(#|//)", content):
            continue
        if re.search(r"\b(select|update|delete|insert|drop|truncate|alter|create)\b", content, re.IGNORECASE):
            sql_lines.append(content)

    merged = "\n".join(sql_lines)
    statements = split_sql_statements(merged, dialect="generic")
    return statements[:max_sql]


async def review_merge_request(
    title: Optional[str],
    description: Optional[str],
    diff: str,
    mode: str,
    dialect: Optional[str],
    max_issues: int,
    max_sql: int,
    policy: Optional[Dict] = None,
    suppressions: Optional[List[Dict]] = None,
    baseline_issues: Optional[List[Dict]] = None,
) -> Dict:
    sql_candidates = extract_sql_from_diff(diff, max_sql)
    reviews: List[Dict] = []

    for idx, sql in enumerate(sql_candidates, start=1):
        result = await analyze_sql(
            sql,
            mode,
            dialect,
            max_issues,
            policy=policy,
            suppressions=suppressions,
            baseline_issues=baseline_issues,
        )
        reviews.append(
            {
                "index": idx,
                "sql": sql,
                "score": result["score"],
                "issues": result["issues"],
                "stats": result["stats"],
            }
        )

    high_risk = sum(1 for r in reviews if any(i.get("level") in {"P0", "P1"} for i in r["issues"]))
    return {
        "title": title,
        "description": description,
        "sql_count": len(sql_candidates),
        "high_risk_sql_count": high_risk,
        "reviews": reviews,
    }
