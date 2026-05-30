import bisect
import functools
import logging
import re
from typing import Dict, List, Optional

import sqlglot
from sqlglot.errors import ErrorLevel
from sqlglot import exp

from app.config import AppConfig


logger = logging.getLogger(__name__)
_SQLGLOT_LOGGER_CONFIG: Optional[bool] = None


def _sql_preview(stmt: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", (stmt or "").strip())
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _configure_sqlglot_logger() -> None:
    global _SQLGLOT_LOGGER_CONFIG
    warning_enabled = AppConfig.sqlglot_warning_enabled()
    if _SQLGLOT_LOGGER_CONFIG is warning_enabled:
        return

    parser_logger = logging.getLogger("sqlglot.parser")
    parser_logger.setLevel(logging.WARNING if warning_enabled else logging.ERROR)
    _SQLGLOT_LOGGER_CONFIG = warning_enabled


def normalize_sql(sql: str) -> str:
    sql = re.sub(r"/\*[\s\S]*?\*/", "", sql)
    sql = re.sub(r"--.*?$", "", sql, flags=re.MULTILINE)
    sql = re.sub(r"\s+", " ", sql).strip()
    return sql


@functools.lru_cache(maxsize=512)
def parse_stmt(stmt: str, dialect: Optional[str]) -> Optional[exp.Expression]:
    _configure_sqlglot_logger()

    stmt_norm = (stmt or "").strip()
    if _looks_like_column_definition(stmt_norm):
        if AppConfig.sql_parser_debug_enabled():
            logger.debug(
                "sql_parser.skip_fragment dialect=%s reason=column-definition sql=%s",
                dialect or "generic",
                _sql_preview(stmt_norm),
            )
        return None

    try:
        read = None if not dialect or dialect == "generic" else dialect
        kwargs = {"read": read, "error_level": ErrorLevel.IGNORE}
        # Different sqlglot versions may or may not support unsupported_level.
        try:
            return sqlglot.parse_one(stmt_norm, unsupported_level=ErrorLevel.IGNORE, **kwargs)
        except TypeError:
            return sqlglot.parse_one(stmt_norm, **kwargs)
    except Exception as exc:
        if AppConfig.sql_parser_debug_enabled():
            logger.debug(
                "sql_parser.parse_one_failed dialect=%s err=%s sql=%s",
                dialect or "generic",
                str(exc)[:200],
                _sql_preview(stmt_norm),
            )
        return None


def extract_tables(expr: exp.Expression) -> List[str]:
    return sorted({t.name for t in expr.find_all(exp.Table) if t.name})


def split_sql_statements(sql: str, dialect: Optional[str]) -> List[str]:
    _configure_sqlglot_logger()

    read = None if not dialect or dialect == "generic" else dialect
    try:
        kwargs = {"read": read, "error_level": ErrorLevel.IGNORE}
        try:
            parsed = sqlglot.parse(sql, unsupported_level=ErrorLevel.IGNORE, **kwargs)
        except TypeError:
            parsed = sqlglot.parse(sql, **kwargs)
        statements = [p.sql(dialect=read) if read else p.sql() for p in parsed]
        statements = [s.strip() for s in statements if s and s.strip()]
        if statements:
            return statements
    except Exception as exc:
        if AppConfig.sql_parser_debug_enabled():
            logger.debug(
                "sql_parser.split_parse_failed dialect=%s err=%s sql=%s",
                dialect or "generic",
                str(exc)[:200],
                _sql_preview(sql),
            )
        pass

    if AppConfig.sql_parser_debug_enabled():
        logger.debug(
            "sql_parser.split_fallback_regex dialect=%s sql=%s",
            dialect or "generic",
            _sql_preview(sql),
        )

    return [s.strip() for s in re.split(r";\s*", sql) if s.strip()]


def _build_line_index(sql: str) -> List[int]:
    """Return sorted list of character offsets at which each line starts.

    Line 1 starts at offset 0; every subsequent line starts at the character
    immediately after a '\\n'. Used for O(log n) offset-to-line lookups.
    """
    offsets = [0]
    for i, ch in enumerate(sql):
        if ch == "\n":
            offsets.append(i + 1)
    return offsets


_COLUMN_DEF_RE = re.compile(
    r"^\s*`?[a-zA-Z_][\w$]*`?\s+"
    r"(?:bigint|int|tinyint|smallint|mediumint|decimal|numeric|float|double|real|char|varchar|text|longtext|mediumtext|datetime|timestamp|date|time|json|blob|boolean|bool)\b",
    re.IGNORECASE,
)


def _looks_like_column_definition(stmt: str) -> bool:
    if not stmt:
        return False

    # Standalone column lines in diffs often trigger "fallback to Command"
    # warnings in sqlglot and are not complete SQL statements.
    if re.search(r"\b(select|insert|update|delete|create|alter|drop|truncate|rename|merge|replace|with)\b", stmt, re.IGNORECASE):
        return False

    if "," in stmt and not re.search(r"\b(comment|default|not\s+null|null|primary\s+key|unique)\b", stmt, re.IGNORECASE):
        return False

    return bool(_COLUMN_DEF_RE.match(stmt))


def _offset_to_line(line_index: List[int], offset: int) -> int:
    """Return 1-based line number for a given character offset."""
    return bisect.bisect_right(line_index, offset)


def split_sql_statements_with_meta(sql: str, dialect: Optional[str]) -> List[Dict]:
    statements = split_sql_statements(sql, dialect)
    if not statements:
        return []

    # Build line index once — O(n) — then use bisect for each statement — O(log n).
    line_index = _build_line_index(sql)
    meta: List[Dict] = []
    cursor = 0

    for idx, stmt in enumerate(statements, start=1):
        start = sql.find(stmt, cursor)
        if start < 0:
            start = cursor
        end = start + len(stmt)

        line_start = _offset_to_line(line_index, start)
        line_end = _offset_to_line(line_index, max(start, end - 1))

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
