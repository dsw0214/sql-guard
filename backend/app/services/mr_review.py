import re
from typing import Dict, List, Optional

from .analyzer import analyze_sql
from .sql_parser import split_sql_statements

TEXT_SQL_FILE_SUFFIX = {".sql", ".txt", ".py", ".js", ".ts", ".tsx", ".jsx", ".md"}


def _extract_sql_candidates(lines: List[str], max_sql: int) -> List[str]:
    merged = "\n".join(lines)
    statements = split_sql_statements(merged, dialect="generic")
    sql_like: List[str] = []
    for stmt in statements:
        if re.search(r"\b(select|update|delete|insert|drop|truncate|alter|create|replace|merge)\b", stmt, re.IGNORECASE):
            sql_like.append(stmt)
        if len(sql_like) >= max_sql:
            break
    return sql_like


def extract_sql_from_diff(diff_text: str, max_sql: int) -> List[str]:
    added_lines: List[str] = []
    current_file = ""

    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue

        if current_file:
            dot = current_file.rfind(".")
            ext = current_file[dot:].lower() if dot >= 0 else ""
            if ext and ext not in TEXT_SQL_FILE_SUFFIX:
                continue

        if not line.startswith("+") or line.startswith("++"):
            continue

        content = line[1:].rstrip()
        if not content.strip():
            continue
        if re.match(r"^\s*(#|//|\*)", content):
            continue
        added_lines.append(content)

    return _extract_sql_candidates(added_lines, max_sql=max_sql)


def extract_deleted_sql_from_diff(diff_text: str, max_sql: int) -> List[str]:
    removed_lines: List[str] = []
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if not line.startswith("-") or line.startswith("--"):
            continue
        content = line[1:].rstrip()
        if not content.strip():
            continue
        removed_lines.append(content)
    return _extract_sql_candidates(removed_lines, max_sql=max_sql)


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
    ci_gate: Optional[Dict] = None,
) -> Dict:
    sql_candidates = extract_sql_from_diff(diff, max_sql)
    deleted_sql_candidates = extract_deleted_sql_from_diff(diff, max_sql)
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
            ci_gate=ci_gate,
        )
        reviews.append(
            {
                "index": idx,
                "sql": sql,
                "score": result["score"],
                "issues": result["issues"],
                "stats": result["stats"],
                "ci_gate": result.get("ci_gate", {"enabled": False, "passed": True, "blocked_reasons": []}),
            }
        )

    high_risk = sum(1 for r in reviews if any(i.get("level") in {"P0", "P1"} for i in r["issues"]))
    gate_enabled = bool(ci_gate)
    gate_failed_count = sum(1 for r in reviews if not r.get("ci_gate", {}).get("passed", True))
    return {
        "title": title,
        "description": description,
        "sql_count": len(sql_candidates),
        "deleted_sql_count": len(deleted_sql_candidates),
        "high_risk_sql_count": high_risk,
        "reviews": reviews,
        "diff_summary": {
            "added_sql_candidates": len(sql_candidates),
            "deleted_sql_candidates": len(deleted_sql_candidates),
        },
        "ci_gate": {
            "enabled": gate_enabled,
            "passed": (gate_failed_count == 0),
            "failed_sql_count": gate_failed_count,
        },
    }
