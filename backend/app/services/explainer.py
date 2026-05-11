from typing import Dict, List, Optional

from sqlglot import exp

from .sql_parser import extract_tables, parse_stmt, split_sql_statements


def explain_sql(sql: str, dialect: Optional[str]) -> Dict:
    statements = split_sql_statements(sql, dialect)
    tables: List[str] = []
    statement_types: List[str] = []
    insights: List[str] = []

    for stmt in statements:
        expr = parse_stmt(stmt, dialect)
        if expr:
            statement_types.append(type(expr).__name__.replace("Expression", ""))
            tables.extend(extract_tables(expr))

            if isinstance(expr, exp.Select):
                if not expr.args.get("where"):
                    insights.append("SELECT 语句没有 WHERE 条件，可能造成大范围扫描")
                if not expr.args.get("limit"):
                    insights.append("SELECT 语句没有 LIMIT，可能返回过多数据")
                if expr.find(exp.Star):
                    insights.append("SELECT * 可能导致不必要的列读取")

            if isinstance(expr, exp.Join):
                insights.append("存在 JOIN，请确认连接字段已建立索引")
        else:
            statement_types.append("Unknown")

    return {
        "statement_count": len(statements),
        "statement_types": statement_types,
        "tables": sorted(set(tables)),
        "insights": list(dict.fromkeys(insights)),
    }
