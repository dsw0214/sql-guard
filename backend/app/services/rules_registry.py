import re
from dataclasses import dataclass
from typing import Callable, List, Optional, Set

from sqlglot import exp


@dataclass(frozen=True)
class RuleDefinition:
    rule_id: str
    level: str
    category: str
    message: str
    hint: str
    docs_slug: str
    detector: Callable[[str, str, Optional[exp.Expression]], bool]
    dialects: Optional[Set[str]] = None


def _is_select(expr: Optional[exp.Expression], lower_sql: str) -> bool:
    return isinstance(expr, exp.Select) or ("select" in lower_sql)


def _no_where(expr: Optional[exp.Expression], lower_sql: str) -> bool:
    if expr is not None:
        return not bool(expr.args.get("where"))
    return " where " not in f" {lower_sql} "


def _no_limit(expr: Optional[exp.Expression], lower_sql: str) -> bool:
    if expr is not None:
        return not bool(expr.args.get("limit"))
    return " limit " not in f" {lower_sql} "


def _dml_no_where(keyword: str) -> Callable[[str, str, Optional[exp.Expression]], bool]:
    pattern = re.compile(rf"\b{keyword}\b")

    def _fn(_stmt: str, lower_sql: str, expr: Optional[exp.Expression]) -> bool:
        if not pattern.search(lower_sql):
            return False
        if keyword == "delete" and isinstance(expr, exp.Delete):
            return _no_where(expr, lower_sql)
        if keyword == "update" and isinstance(expr, exp.Update):
            return _no_where(expr, lower_sql)
        if expr is not None and not isinstance(expr, (exp.Delete, exp.Update)):
            return False
        return _no_where(expr, lower_sql)

    return _fn


def _ddl_missing_idempotent(_stmt: str, lower_sql: str, _expr: Optional[exp.Expression]) -> bool:
    if not re.search(r"\b(drop|alter|create)\s+table\b", lower_sql):
        return False
    return "if exists" not in lower_sql and "if not exists" not in lower_sql


def _func_on_where(_stmt: str, lower_sql: str, _expr: Optional[exp.Expression]) -> bool:
    return bool(re.search(r"\bwhere\b[\s\S]{0,100}\b(lower|upper|substr|substring|cast|date|to_char)\s*\(", lower_sql))


def _large_in(_stmt: str, lower_sql: str, _expr: Optional[exp.Expression]) -> bool:
    return bool(re.search(r"\bin\s*\(([^)]*,){30,}[^)]*\)", lower_sql))


def _nested_subquery(_stmt: str, _lower_sql: str, expr: Optional[exp.Expression]) -> bool:
    if expr is None:
        return False
    return len(list(expr.find_all(exp.Subquery))) >= 2


def _insert_no_columns(_stmt: str, lower_sql: str, expr: Optional[exp.Expression]) -> bool:
    if isinstance(expr, exp.Insert):
        return not bool(expr.args.get("columns"))
    return bool(re.search(r"insert\s+into\s+\w+\s+values\s*\(", lower_sql))


def _drop_table(_stmt: str, lower_sql: str, expr: Optional[exp.Expression]) -> bool:
    if isinstance(expr, exp.Drop):
        return "TABLE" in str(expr.args.get("kind", "")).upper()
    return "drop table" in lower_sql


def _drop_database(_stmt: str, lower_sql: str, expr: Optional[exp.Expression]) -> bool:
    if isinstance(expr, exp.Drop):
        kind = str(expr.args.get("kind", "")).upper()
        return "DATABASE" in kind or "SCHEMA" in kind
    return bool(re.search(r"drop\s+(database|schema)", lower_sql))


def _truncate(_stmt: str, lower_sql: str, expr: Optional[exp.Expression]) -> bool:
    expr_name = type(expr).__name__ if expr is not None else ""
    return expr_name in {"Truncate", "TruncateTable"} or lower_sql.startswith("truncate ")


def _select_star(_stmt: str, lower_sql: str, expr: Optional[exp.Expression]) -> bool:
    if isinstance(expr, exp.Select):
        return bool(expr.find(exp.Star))
    return "select *" in lower_sql


def _select_no_limit(stmt: str, lower_sql: str, expr: Optional[exp.Expression]) -> bool:
    return _is_select(expr, lower_sql) and _no_limit(expr, lower_sql)


def _select_no_where(stmt: str, lower_sql: str, expr: Optional[exp.Expression]) -> bool:
    return _is_select(expr, lower_sql) and _no_where(expr, lower_sql)


def _rule_definitions() -> List[RuleDefinition]:
    return [
        RuleDefinition("RG-SELECT-STAR", "P3", "query-style", "避免使用 SELECT *", "明确指定字段，减少 IO 与网络传输", "rg-select-star", _select_star),
        RuleDefinition("RG-SELECT-NO-LIMIT", "P3", "performance", "建议增加 LIMIT", "避免全表读取引发慢查询", "rg-select-no-limit", _select_no_limit),
        RuleDefinition("RG-SELECT-NO-WHERE", "P2", "performance", "SELECT 缺少 WHERE 过滤", "建议使用索引字段过滤范围", "rg-select-no-where", _select_no_where),
        RuleDefinition("RG-DML-DELETE-NO-WHERE", "P1", "dml-safety", "DELETE 缺少 WHERE 条件", "请添加精确过滤条件", "rg-dml-delete-no-where", _dml_no_where("delete")),
        RuleDefinition("RG-DML-UPDATE-NO-WHERE", "P1", "dml-safety", "UPDATE 缺少 WHERE 条件", "请添加主键或唯一索引条件", "rg-dml-update-no-where", _dml_no_where("update")),
        RuleDefinition("RG-DML-INSERT-NO-COLUMNS", "P2", "dml-safety", "INSERT 未显式指定列名", "请显式声明列清单，避免表结构变更导致写入错位", "rg-dml-insert-no-columns", _insert_no_columns),
        RuleDefinition("RG-DML-REPLACE-INTO", "P1", "dml-safety", "REPLACE INTO 会隐式删除再插入", "请确认主键冲突行为，避免触发意外删除与审计缺失", "rg-dml-replace-into", lambda _s, l, _e: bool(re.search(r"\breplace\s+into\b", l))),
        RuleDefinition("RG-DML-INSERT-OVERWRITE", "P1", "dml-safety", "INSERT OVERWRITE 存在覆盖风险", "建议在变更窗口执行并提前备份", "rg-dml-insert-overwrite", lambda _s, l, _e: bool(re.search(r"insert\s+overwrite\b", l))),
        RuleDefinition("RG-DML-WEAK-WHERE", "P2", "dml-safety", "存在宽泛过滤条件 WHERE 1=1/TRUE", "请确认是否会扩大影响范围", "rg-dml-weak-where", lambda _s, l, _e: bool(re.search(r"where\s+1\s*=\s*1|\bwhere\s+true\b", l))),
        RuleDefinition("RG-DDL-DROP-TABLE", "P0", "ddl-safety", "禁止 DROP TABLE", "建议改为受控迁移脚本执行", "rg-ddl-drop-table", _drop_table),
        RuleDefinition("RG-DDL-DROP-DB", "P0", "ddl-safety", "禁止 DROP DATABASE/SCHEMA", "请改为受控变更流程，并确认备份与回滚方案", "rg-ddl-drop-db", _drop_database),
        RuleDefinition("RG-DDL-ALTER-TABLE", "P2", "ddl-safety", "ALTER TABLE 可能导致锁表或长事务", "建议评估大表影响并选择低峰变更窗口", "rg-ddl-alter-table", lambda _s, l, _e: bool(re.search(r"alter\s+table\b", l))),
        RuleDefinition("RG-DDL-RENAME-TABLE", "P1", "ddl-safety", "RENAME TABLE 可能影响依赖服务", "请确认上下游 SQL、视图、任务调度已同步更新", "rg-ddl-rename-table", lambda _s, l, _e: bool(re.search(r"rename\s+table\b", l))),
        RuleDefinition("RG-DDL-NO-IDEMPOTENT-GUARD", "P3", "ddl-safety", "DDL 缺少 IF EXISTS/IF NOT EXISTS 防护", "建议补充幂等保护，降低重复执行失败风险", "rg-ddl-no-idempotent-guard", _ddl_missing_idempotent),
        RuleDefinition("RG-DDL-TRUNCATE", "P0", "ddl-safety", "TRUNCATE TABLE 风险高", "建议在变更窗口并做好备份", "rg-ddl-truncate", _truncate),
        RuleDefinition("RG-PERF-ORDER-RANDOM", "P2", "performance", "ORDER BY RAND()/RANDOM() 可能导致性能问题", "建议使用采样表或预计算随机键", "rg-perf-order-random", lambda _s, l, _e: bool(re.search(r"order\s+by\s+(rand|random)\s*\(\s*\)", l))),
        RuleDefinition("RG-PERF-CROSS-JOIN", "P2", "performance", "存在 CROSS JOIN，可能导致笛卡尔积", "请确认连接条件与数据规模", "rg-perf-cross-join", lambda _s, l, _e: bool(re.search(r"\bcross\s+join\b", l))),
        RuleDefinition("RG-PERF-LEADING-WILDCARD", "P2", "performance", "LIKE 前导通配符可能导致索引失效", "建议使用倒排索引或改写查询条件", "rg-perf-leading-wildcard", lambda _s, l, _e: bool(re.search(r"like\s+['\"]%", l))),
        RuleDefinition("RG-PERF-FUNC-ON-WHERE", "P2", "performance", "WHERE 过滤列上使用函数可能导致全表扫描", "建议将函数移到常量侧或增加函数索引", "rg-perf-func-on-where", _func_on_where),
        RuleDefinition("RG-PERF-LARGE-IN", "P2", "performance", "IN 列表过长可能影响执行计划", "建议改为临时表 JOIN 或批量分段查询", "rg-perf-large-in", _large_in),
        RuleDefinition("RG-PERF-NESTED-SUBQUERY", "P2", "performance", "存在多层子查询，可能导致优化器退化", "建议评估是否可改写为 JOIN 或中间结果表", "rg-perf-nested-subquery", _nested_subquery),
        # Dialect-focused examples
        RuleDefinition("RG-MYSQL-SQL-CALC-FOUND-ROWS", "P2", "dialect-mysql", "SQL_CALC_FOUND_ROWS 已过时且性能差", "建议改用 COUNT(*) + 分页查询", "rg-mysql-sql-calc-found-rows", lambda _s, l, _e: "sql_calc_found_rows" in l, {"mysql"}),
        RuleDefinition("RG-POSTGRES-ILIKE-PREFIX", "P3", "dialect-postgresql", "ILIKE 前导通配符可能导致性能问题", "建议配合 trigram 索引或调整查询模式", "rg-postgres-ilike-prefix", lambda _s, l, _e: bool(re.search(r"ilike\s+['\"]%", l)), {"postgresql", "postgres"}),
    ]


def get_rule_definitions(dialect: Optional[str]) -> List[RuleDefinition]:
    normalized_dialect = (dialect or "generic").lower()
    rules = _rule_definitions()
    return [
        rule
        for rule in rules
        if not rule.dialects or normalized_dialect in rule.dialects
    ]
