import re
from typing import Dict, List, Optional, Tuple

from sqlglot import exp

from .sql_parser import extract_tables, parse_stmt


def rule_issue(level: str, message: str, hint: Optional[str] = None) -> Dict:
    return {
        "level": level,
        "message": message,
        "source": "rule",
        "hint": hint,
    }


def analyze_statement(stmt: str, dialect: Optional[str]) -> Tuple[List[Dict], List[str]]:
    issues: List[Dict] = []
    lower_sql = stmt.lower()
    expr = parse_stmt(stmt, dialect)

    if not expr:
        if "select *" in lower_sql:
            issues.append(rule_issue("P3", "避免使用 SELECT *", "明确指定字段，减少 IO 与网络传输"))
        if re.search(r"delete\s+from\s+\w+\s*;?$", lower_sql):
            issues.append(rule_issue("P1", "DELETE 缺少 WHERE 条件", "请添加精确过滤条件"))
        if re.search(r"update\s+\w+\s+set\s+", lower_sql) and "where" not in lower_sql:
            issues.append(rule_issue("P1", "UPDATE 缺少 WHERE 条件", "请添加主键或唯一索引条件"))
        if re.search(r"drop\s+table", lower_sql):
            issues.append(rule_issue("P0", "禁止 DROP TABLE", "建议改为受控迁移脚本执行"))
        if "select" in lower_sql and "limit" not in lower_sql:
            issues.append(rule_issue("P3", "建议增加 LIMIT", "避免全表读取引发慢查询"))
        return issues, []

    tables = extract_tables(expr)

    if isinstance(expr, exp.Select):
        if expr.find(exp.Star):
            issues.append(rule_issue("P3", "避免使用 SELECT *", "明确指定字段，减少 IO 与网络传输"))
        if not expr.args.get("limit"):
            issues.append(rule_issue("P3", "建议增加 LIMIT", "避免全表读取引发慢查询"))
        if not expr.args.get("where"):
            issues.append(rule_issue("P2", "SELECT 缺少 WHERE 过滤", "建议使用索引字段过滤范围"))

    if isinstance(expr, exp.Delete) and not expr.args.get("where"):
        issues.append(rule_issue("P1", "DELETE 缺少 WHERE 条件", "请添加精确过滤条件"))

    if isinstance(expr, exp.Update) and not expr.args.get("where"):
        issues.append(rule_issue("P1", "UPDATE 缺少 WHERE 条件", "请添加主键或唯一索引条件"))

    if isinstance(expr, exp.Drop):
        kind = str(expr.args.get("kind", "")).upper()
        if "TABLE" in kind:
            issues.append(rule_issue("P0", "禁止 DROP TABLE", "建议改为受控迁移脚本执行"))

    expr_name = type(expr).__name__
    is_truncate_stmt = expr_name in {"Truncate", "TruncateTable"} or lower_sql.startswith("truncate ")
    if is_truncate_stmt:
        issues.append(rule_issue("P0", "TRUNCATE TABLE 风险高", "建议在变更窗口并做好备份"))

    if re.search(r"where\s+1\s*=\s*1", lower_sql):
        issues.append(rule_issue("P2", "存在宽泛过滤条件 WHERE 1=1", "确认是否会扩大影响范围"))

    if re.search(r"order\s+by\s+(rand|random)\s*\(\s*\)", lower_sql):
        issues.append(rule_issue("P2", "ORDER BY RAND()/RANDOM() 可能导致性能问题", "建议使用采样表或预计算随机键"))

    if re.search(r"\bcross\s+join\b", lower_sql):
        issues.append(rule_issue("P2", "存在 CROSS JOIN，可能导致笛卡尔积", "请确认连接条件与数据规模"))

    return issues, tables
