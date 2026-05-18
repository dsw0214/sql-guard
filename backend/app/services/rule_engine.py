import re
from typing import Dict, List, Optional, Tuple

from sqlglot import exp

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

    def add(
        level: str,
        rule_id: str,
        category: str,
        message: str,
        hint: Optional[str],
        docs_slug: str,
    ) -> None:
        issues.append(
            rule_issue(
                level=level,
                message=message,
                hint=hint,
                rule_id=rule_id,
                category=category,
                dialect_scope=dialect_scope,
                docs_url=f"https://github.com/dsw0214/sql-guard/wiki/rules#{docs_slug}",
                statement_index=statement_index,
                line_start=line_start,
                line_end=line_end,
                sql_fragment=stmt[:400],
            )
        )

    if not expr:
        if "select *" in lower_sql:
            add("P3", "RG-SELECT-STAR", "query-style", "避免使用 SELECT *", "明确指定字段，减少 IO 与网络传输", "rg-select-star")
        if re.search(r"delete\s+from\s+\w+\s*;?$", lower_sql):
            add("P1", "RG-DML-DELETE-NO-WHERE", "dml-safety", "DELETE 缺少 WHERE 条件", "请添加精确过滤条件", "rg-dml-delete-no-where")
        if re.search(r"update\s+\w+\s+set\s+", lower_sql) and "where" not in lower_sql:
            add("P1", "RG-DML-UPDATE-NO-WHERE", "dml-safety", "UPDATE 缺少 WHERE 条件", "请添加主键或唯一索引条件", "rg-dml-update-no-where")
        if re.search(r"insert\s+into\s+\w+\s+values\s*\(", lower_sql):
            add("P2", "RG-DML-INSERT-NO-COLUMNS", "dml-safety", "INSERT 未显式指定列名", "请显式声明列清单，避免表结构变更导致写入错位", "rg-dml-insert-no-columns")
        if re.search(r"\breplace\s+into\b", lower_sql):
            add("P1", "RG-DML-REPLACE-INTO", "dml-safety", "REPLACE INTO 会隐式删除再插入", "请确认主键冲突行为，避免触发意外删除与审计缺失", "rg-dml-replace-into")
        if re.search(r"insert\s+overwrite\b", lower_sql):
            add("P1", "RG-DML-INSERT-OVERWRITE", "dml-safety", "INSERT OVERWRITE 存在覆盖风险", "建议在变更窗口执行并提前备份", "rg-dml-insert-overwrite")
        if re.search(r"drop\s+table", lower_sql):
            add("P0", "RG-DDL-DROP-TABLE", "ddl-safety", "禁止 DROP TABLE", "建议改为受控迁移脚本执行", "rg-ddl-drop-table")
        if re.search(r"drop\s+(database|schema)", lower_sql):
            add("P0", "RG-DDL-DROP-DB", "ddl-safety", "禁止 DROP DATABASE/SCHEMA", "请改为受控变更流程，并确认备份与回滚方案", "rg-ddl-drop-db")
        if re.search(r"alter\s+table\b", lower_sql):
            add("P2", "RG-DDL-ALTER-TABLE", "ddl-safety", "ALTER TABLE 可能导致锁表或长事务", "建议评估大表影响并选择低峰变更窗口", "rg-ddl-alter-table")
        if re.search(r"rename\s+table\b", lower_sql):
            add("P1", "RG-DDL-RENAME-TABLE", "ddl-safety", "RENAME TABLE 可能影响依赖服务", "请确认上下游 SQL、视图、任务调度已同步更新", "rg-ddl-rename-table")
        if re.search(r"\b(drop|alter|create)\s+table\b", lower_sql) and "if exists" not in lower_sql and "if not exists" not in lower_sql:
            add("P3", "RG-DDL-NO-IDEMPOTENT-GUARD", "ddl-safety", "DDL 缺少 IF EXISTS/IF NOT EXISTS 防护", "建议补充幂等保护，降低重复执行失败风险", "rg-ddl-no-idempotent-guard")
        if "select" in lower_sql and "limit" not in lower_sql:
            add("P3", "RG-SELECT-NO-LIMIT", "performance", "建议增加 LIMIT", "避免全表读取引发慢查询", "rg-select-no-limit")
        if re.search(r"like\s+['\"]%", lower_sql):
            add("P2", "RG-PERF-LEADING-WILDCARD", "performance", "LIKE 前导通配符可能导致索引失效", "建议使用倒排索引或改写查询条件", "rg-perf-leading-wildcard")
        if re.search(r"\bwhere\b[\s\S]{0,80}\b(lower|upper|substr|substring|cast|date|to_char)\s*\(", lower_sql):
            add("P2", "RG-PERF-FUNC-ON-WHERE", "performance", "WHERE 过滤列上使用函数可能导致全表扫描", "建议将函数移到常量侧或增加函数索引", "rg-perf-func-on-where")
        if re.search(r"\bin\s*\(([^)]*,){30,}[^)]*\)", lower_sql):
            add("P2", "RG-PERF-LARGE-IN", "performance", "IN 列表过长可能影响执行计划", "建议改为临时表 JOIN 或批量分段查询", "rg-perf-large-in")
        return issues, []

    tables = extract_tables(expr)

    if isinstance(expr, exp.Select):
        if expr.find(exp.Star):
            add("P3", "RG-SELECT-STAR", "query-style", "避免使用 SELECT *", "明确指定字段，减少 IO 与网络传输", "rg-select-star")
        if not expr.args.get("limit"):
            add("P3", "RG-SELECT-NO-LIMIT", "performance", "建议增加 LIMIT", "避免全表读取引发慢查询", "rg-select-no-limit")
        if not expr.args.get("where"):
            add("P2", "RG-SELECT-NO-WHERE", "performance", "SELECT 缺少 WHERE 过滤", "建议使用索引字段过滤范围", "rg-select-no-where")

    if isinstance(expr, exp.Insert):
        if not expr.args.get("columns"):
            add("P2", "RG-DML-INSERT-NO-COLUMNS", "dml-safety", "INSERT 未显式指定列名", "请显式声明列清单，避免表结构变更导致写入错位", "rg-dml-insert-no-columns")

    if isinstance(expr, exp.Delete) and not expr.args.get("where"):
        add("P1", "RG-DML-DELETE-NO-WHERE", "dml-safety", "DELETE 缺少 WHERE 条件", "请添加精确过滤条件", "rg-dml-delete-no-where")

    if isinstance(expr, exp.Update) and not expr.args.get("where"):
        add("P1", "RG-DML-UPDATE-NO-WHERE", "dml-safety", "UPDATE 缺少 WHERE 条件", "请添加主键或唯一索引条件", "rg-dml-update-no-where")

    if re.search(r"\breplace\s+into\b", lower_sql):
        add("P1", "RG-DML-REPLACE-INTO", "dml-safety", "REPLACE INTO 会隐式删除再插入", "请确认主键冲突行为，避免触发意外删除与审计缺失", "rg-dml-replace-into")

    if re.search(r"insert\s+overwrite\b", lower_sql):
        add("P1", "RG-DML-INSERT-OVERWRITE", "dml-safety", "INSERT OVERWRITE 存在覆盖风险", "建议在变更窗口执行并提前备份", "rg-dml-insert-overwrite")

    if isinstance(expr, exp.Drop):
        kind = str(expr.args.get("kind", "")).upper()
        if "TABLE" in kind:
            add("P0", "RG-DDL-DROP-TABLE", "ddl-safety", "禁止 DROP TABLE", "建议改为受控迁移脚本执行", "rg-ddl-drop-table")
        if "DATABASE" in kind or "SCHEMA" in kind:
            add("P0", "RG-DDL-DROP-DB", "ddl-safety", "禁止 DROP DATABASE/SCHEMA", "请改为受控变更流程，并确认备份与回滚方案", "rg-ddl-drop-db")

    if re.search(r"alter\s+table\b", lower_sql):
        add("P2", "RG-DDL-ALTER-TABLE", "ddl-safety", "ALTER TABLE 可能导致锁表或长事务", "建议评估大表影响并选择低峰变更窗口", "rg-ddl-alter-table")

    if re.search(r"rename\s+table\b", lower_sql):
        add("P1", "RG-DDL-RENAME-TABLE", "ddl-safety", "RENAME TABLE 可能影响依赖服务", "请确认上下游 SQL、视图、任务调度已同步更新", "rg-ddl-rename-table")

    if re.search(r"\b(drop|alter|create)\s+table\b", lower_sql) and "if exists" not in lower_sql and "if not exists" not in lower_sql:
        add("P3", "RG-DDL-NO-IDEMPOTENT-GUARD", "ddl-safety", "DDL 缺少 IF EXISTS/IF NOT EXISTS 防护", "建议补充幂等保护，降低重复执行失败风险", "rg-ddl-no-idempotent-guard")

    expr_name = type(expr).__name__
    is_truncate_stmt = expr_name in {"Truncate", "TruncateTable"} or lower_sql.startswith("truncate ")
    if is_truncate_stmt:
        add("P0", "RG-DDL-TRUNCATE", "ddl-safety", "TRUNCATE TABLE 风险高", "建议在变更窗口并做好备份", "rg-ddl-truncate")

    if re.search(r"where\s+1\s*=\s*1", lower_sql):
        add("P2", "RG-DML-WEAK-WHERE", "dml-safety", "存在宽泛过滤条件 WHERE 1=1", "确认是否会扩大影响范围", "rg-dml-weak-where")

    if re.search(r"\bwhere\s+true\b", lower_sql):
        add("P2", "RG-DML-WEAK-WHERE", "dml-safety", "存在宽泛过滤条件 WHERE TRUE", "请确认是否会扩大影响范围", "rg-dml-weak-where")

    if re.search(r"order\s+by\s+(rand|random)\s*\(\s*\)", lower_sql):
        add("P2", "RG-PERF-ORDER-RANDOM", "performance", "ORDER BY RAND()/RANDOM() 可能导致性能问题", "建议使用采样表或预计算随机键", "rg-perf-order-random")

    if re.search(r"\bcross\s+join\b", lower_sql):
        add("P2", "RG-PERF-CROSS-JOIN", "performance", "存在 CROSS JOIN，可能导致笛卡尔积", "请确认连接条件与数据规模", "rg-perf-cross-join")

    if re.search(r"like\s+['\"]%", lower_sql):
        add("P2", "RG-PERF-LEADING-WILDCARD", "performance", "LIKE 前导通配符可能导致索引失效", "建议使用倒排索引或改写查询条件", "rg-perf-leading-wildcard")

    if re.search(r"\bwhere\b[\s\S]{0,80}\b(lower|upper|substr|substring|cast|date|to_char)\s*\(", lower_sql):
        add("P2", "RG-PERF-FUNC-ON-WHERE", "performance", "WHERE 过滤列上使用函数可能导致全表扫描", "建议将函数移到常量侧或增加函数索引", "rg-perf-func-on-where")

    if re.search(r"\bin\s*\(([^)]*,){30,}[^)]*\)", lower_sql):
        add("P2", "RG-PERF-LARGE-IN", "performance", "IN 列表过长可能影响执行计划", "建议改为临时表 JOIN 或批量分段查询", "rg-perf-large-in")

    subquery_count = len(list(expr.find_all(exp.Subquery)))
    if subquery_count >= 2:
        add("P2", "RG-PERF-NESTED-SUBQUERY", "performance", "存在多层子查询，可能导致优化器退化", "建议评估是否可改写为 JOIN 或中间结果表", "rg-perf-nested-subquery")

    return issues, tables
