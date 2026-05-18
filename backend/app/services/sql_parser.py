import re
from typing import Dict, List, Optional

import sqlglot
from sqlglot import exp


def normalize_sql(sql: str) -> str:
    sql = re.sub(r"/\*[\s\S]*?\*/", "", sql)
    sql = re.sub(r"--.*?$", "", sql, flags=re.MULTILINE)
    sql = re.sub(r"\s+", " ", sql).strip()
    return sql


def parse_stmt(stmt: str, dialect: Optional[str]) -> Optional[exp.Expression]:
    try:
        read = None if not dialect or dialect == "generic" else dialect
        return sqlglot.parse_one(stmt, read=read)
    except Exception:
        return None


def extract_tables(expr: exp.Expression) -> List[str]:
    return sorted({t.name for t in expr.find_all(exp.Table) if t.name})


def split_sql_statements(sql: str, dialect: Optional[str]) -> List[str]:
    read = None if not dialect or dialect == "generic" else dialect
    try:
        parsed = sqlglot.parse(sql, read=read)
        statements = [p.sql(dialect=read) if read else p.sql() for p in parsed]
        statements = [s.strip() for s in statements if s and s.strip()]
        if statements:
            return statements
    except Exception:
        pass

    return [s.strip() for s in re.split(r";\s*", sql) if s.strip()]


def split_sql_statements_with_meta(sql: str, dialect: Optional[str]) -> List[Dict]:
    statements = split_sql_statements(sql, dialect)
    if not statements:
        return []

    meta: List[Dict] = []
    cursor = 0

    for idx, stmt in enumerate(statements, start=1):
        start = sql.find(stmt, cursor)
        if start < 0:
            start = cursor
        end = start + len(stmt)

        line_start = sql.count("\n", 0, start) + 1
        line_end = sql.count("\n", 0, max(start, end - 1)) + 1

        meta.append(
            {
                "statement_index": idx,
                "statement": stmt,
                "start_offset": start,
                "end_offset": end,
                "line_start": line_start,
                "line_end": line_end,
            }
        )
        cursor = end

    return meta
