from typing import Dict, List, Optional, Tuple

from .rules_registry import get_rule_definitions
from .sql_parser import extract_tables, parse_stmt


def rule_issue(
    level: str,
    message: str,
    hint: Optional[str] = None,
    rule_id: Optional[str] = None,
    category: str = "general",
    dialect_scope: str = "generic",
    docs_url: Optional[str] = None,
    statement_index: Optional[int] = None,
    line_start: Optional[int] = None,
    line_end: Optional[int] = None,
    sql_fragment: Optional[str] = None,
) -> Dict:
    return {
        "level": level,
        "severity": level,
        "message": message,
        "source": "rule",
        "rule_id": rule_id or "RG-GENERAL-000",
        "category": category,
        "dialect_scope": dialect_scope,
        "docs_url": docs_url,
        "statement_index": statement_index,
        "line_start": line_start,
        "line_end": line_end,
        "sql_fragment": sql_fragment,
        "hint": hint,
    }


def analyze_statement(
    stmt: str,
    dialect: Optional[str],
    statement_index: Optional[int] = None,
    line_start: Optional[int] = None,
    line_end: Optional[int] = None,
) -> Tuple[List[Dict], List[str]]:
    issues: List[Dict] = []
    lower_sql = stmt.lower()
    expr = parse_stmt(stmt, dialect)
    dialect_scope = dialect or "generic"

    for rule in get_rule_definitions(dialect_scope):
        if not rule.detector(stmt, lower_sql, expr):
            continue
        issues.append(
            rule_issue(
                level=rule.level,
                message=rule.message,
                hint=rule.hint,
                rule_id=rule.rule_id,
                category=rule.category,
                dialect_scope=dialect_scope,
                docs_url=f"https://github.com/dsw0214/sql-guard/wiki/rules#{rule.docs_slug}",
                statement_index=statement_index,
                line_start=line_start,
                line_end=line_end,
                sql_fragment=stmt[:400],
            )
        )

    tables = extract_tables(expr) if expr else []
    return issues, tables
