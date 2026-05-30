import hashlib
import re
from typing import Dict, List, Optional, Tuple

from app.config import AppConfig
from sqlglot import exp
from .ai_client import analyze_sql_with_ai
from .rule_engine import analyze_statement
from .sql_parser import parse_stmt
from .sql_parser import split_sql_statements_with_meta


LEVEL_WEIGHT: Dict[str, int] = {
    "P0": 40,
    "P1": 25,
    "P2": 12,
    "P3": 6,
}

LEVEL_ORDER: Dict[str, int] = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def risk_score(
    issues: List[Dict],
    statement_count: int = 0,
    table_count: int = 0,
    unique_rule_count: int = 0,
) -> int:
    if not issues:
        return 0
    score = sum(LEVEL_WEIGHT.get(i.get("level", "P3"), 6) for i in issues)

    has_p0 = any(i.get("level") == "P0" for i in issues)
    p1_count = sum(1 for i in issues if i.get("level") == "P1")
    if has_p0:
        score += 15
    if p1_count >= 2:
        score += 10

    score += min(15, statement_count * 2)
    score += min(10, table_count * 2)
    score += min(10, unique_rule_count)
    return min(100, score)


def _normalize_level(level: str) -> str:
    value = (level or "").upper().strip()
    if value in {"P0", "P1", "P2", "P3"}:
        return value
    return "P3"


def _normalize_policy(request_policy: Optional[Dict]) -> Dict:
    env_policy = AppConfig.rule_policy_view()
    policy = {
        "enabled_rules": set(env_policy.get("enabled_rules", [])),
        "disabled_rules": set(env_policy.get("disabled_rules", [])),
        "enabled_categories": set(env_policy.get("enabled_categories", [])),
        "severity_overrides": dict(env_policy.get("severity_overrides", {})),
    }

    if not request_policy:
        return policy

    for rid in request_policy.get("enabled_rules", []) or []:
        policy["enabled_rules"].add(rid)
    for rid in request_policy.get("disabled_rules", []) or []:
        policy["disabled_rules"].add(rid)
    for cat in request_policy.get("enabled_categories", []) or []:
        policy["enabled_categories"].add(cat)
    for rid, level in (request_policy.get("severity_overrides", {}) or {}).items():
        policy["severity_overrides"][rid] = _normalize_level(str(level))

    return policy


def _normalize_suppressions(request_suppressions: Optional[List[Dict]]) -> List[Dict]:
    suppressions = list(AppConfig.default_suppressions())
    for item in request_suppressions or []:
        if not item.get("rule_id"):
            continue
        suppressions.append(
            {
                "rule_id": str(item.get("rule_id")),
                "statement_index": item.get("statement_index"),
                "scope": (item.get("scope") or "global"),
            }
        )
    return suppressions


def _is_suppressed(issue: Dict, suppressions: List[Dict]) -> bool:
    for item in suppressions:
        if item.get("rule_id") != issue.get("rule_id"):
            continue
        if item.get("scope") == "statement":
            if item.get("statement_index") != issue.get("statement_index"):
                continue
        return True
    return False


def _apply_policy(issues: List[Dict], policy: Dict, suppressions: List[Dict]) -> List[Dict]:
    result: List[Dict] = []
    enabled_rules = policy.get("enabled_rules", set())
    disabled_rules = policy.get("disabled_rules", set())
    enabled_categories = policy.get("enabled_categories", set())
    severity_overrides = policy.get("severity_overrides", {})

    for item in issues:
        rule_id = item.get("rule_id")
        category = item.get("category")

        if enabled_rules and rule_id and rule_id not in enabled_rules:
            continue
        if rule_id in disabled_rules:
            continue
        if enabled_categories and category and category not in enabled_categories:
            continue
        if _is_suppressed(item, suppressions):
            continue

        level = severity_overrides.get(rule_id)
        if level:
            item = {**item, "level": level, "severity": level}
        result.append(item)

    return result


def _issue_key(item: Dict) -> str:
    rule_id = item.get("rule_id") or ""
    message = (item.get("message") or "").strip()
    stmt_idx = item.get("statement_index") or 0
    return f"{rule_id}|{message}|{stmt_idx}"


def _baseline_diff(current: List[Dict], baseline: Optional[List[Dict]]) -> Dict:
    baseline_items = baseline or []
    current_map = {_issue_key(i): i for i in current}
    baseline_map = {_issue_key(i): i for i in baseline_items}

    new_keys = [k for k in current_map if k not in baseline_map]
    resolved_keys = [k for k in baseline_map if k not in current_map]
    unchanged_keys = [k for k in current_map if k in baseline_map]

    return {
        "new_issue_count": len(new_keys),
        "resolved_issue_count": len(resolved_keys),
        "unchanged_issue_count": len(unchanged_keys),
        "new_issues": [current_map[k] for k in new_keys],
        "resolved_issues": [baseline_map[k] for k in resolved_keys],
    }


def _evaluate_ci_gate(
    gate: Optional[Dict],
    issues: List[Dict],
    score: int,
    ai_error: Optional[str],
    baseline: Dict,
) -> Dict:
    if not gate:
        return {"enabled": False, "passed": True, "blocked_reasons": []}

    blocked_reasons: List[str] = []
    effective_issues = baseline.get("new_issues", []) if gate.get("only_new_issues") else issues

    max_allowed_severity = gate.get("max_allowed_severity")
    if max_allowed_severity:
        threshold = LEVEL_ORDER.get(str(max_allowed_severity).upper(), 3)
        breach = any(LEVEL_ORDER.get((i.get("level") or "P3").upper(), 3) < threshold for i in effective_issues)
        if breach:
            blocked_reasons.append(f"severity>{max_allowed_severity}")

    max_score = gate.get("max_score")
    if max_score is not None and score > int(max_score):
        blocked_reasons.append(f"score>{max_score}")

    max_total_issues = gate.get("max_total_issues")
    if max_total_issues is not None and len(effective_issues) > int(max_total_issues):
        blocked_reasons.append(f"issues>{max_total_issues}")

    if gate.get("fail_on_ai_error") and ai_error:
        blocked_reasons.append("ai-error")

    return {
        "enabled": True,
        "passed": len(blocked_reasons) == 0,
        "blocked_reasons": blocked_reasons,
        "metrics": {
            "effective_issue_count": len(effective_issues),
            "score": score,
            "ai_error": bool(ai_error),
            "only_new_issues": bool(gate.get("only_new_issues")),
        },
    }


# Matches: CREATE [TEMPORARY] TABLE [IF NOT EXISTS] <name>  (unquoted or backtick-quoted)
_CREATE_TABLE_RE = re.compile(
    r"^\s*create\s+(?:temporary\s+)?table\s+(?:if\s+not\s+exists\s+)?"
    r"(?:`[^`]+`|\w+(?:\.\w+)*)\s+",
    re.IGNORECASE,
)


def _canonical_stmt_key(stmt: str, dialect: Optional[str]) -> str:
    """Return a structural fingerprint for *stmt*.

    For CREATE TABLE statements the table / schema identifier is replaced with
    a placeholder using a fast regex (no AST parse), so sharded tables that
    share the same column definitions map to the same key.
    For all other statement types the normalised full text is hashed.
    """
    m = _CREATE_TABLE_RE.match(stmt)
    if m:
        # Replace everything up to and including the table name with a
        # normalised prefix so the key depends only on the column definitions.
        body = stmt[m.end():]  # column list + options
        canonical = "CREATE TABLE __T__ " + body
        normalized = re.sub(r"\s+", " ", canonical.lower()).strip()
        return "c:" + hashlib.sha256(normalized.encode()).hexdigest()

    expr = parse_stmt(stmt, dialect)
    if expr is not None:
        canonical_expr = expr.copy()

        # Normalize identifiers and literals so statements with identical
        # structure but different names/values land in the same group.
        for table in canonical_expr.find_all(exp.Table):
            if table.args.get("this") is not None:
                table.set("this", exp.to_identifier("__TABLE__"))
            if table.args.get("db") is not None:
                table.set("db", exp.to_identifier("__DB__"))
            if table.args.get("catalog") is not None:
                table.set("catalog", exp.to_identifier("__CATALOG__"))

        for column in canonical_expr.find_all(exp.Column):
            if column.args.get("this") is not None:
                column.set("this", exp.to_identifier("__COL__"))
            if column.args.get("table") is not None:
                column.set("table", exp.to_identifier("__TABLE_ALIAS__"))

        for lit in canonical_expr.find_all(exp.Literal):
            lit.set("this", "__LIT__")

        normalized = re.sub(r"\s+", " ", canonical_expr.sql().lower()).strip()
        return "a:" + hashlib.sha256(normalized.encode()).hexdigest()

    normalized = re.sub(r"\s+", " ", stmt.lower()).strip()
    return "s:" + hashlib.sha256(normalized.encode()).hexdigest()


def _format_structure_group_id(key: str) -> str:
    digest = key.split(":", 1)[-1]
    return f"SG-{digest[:10].upper()}"


def _split_top_level_csv(text: str) -> List[str]:
    items: List[str] = []
    depth = 0
    start = 0
    for idx, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            items.append(text[start:idx].strip())
            start = idx + 1
    tail = text[start:].strip()
    if tail:
        items.append(tail)
    return items


def _extract_create_table_outline(stmt: str) -> Optional[str]:
    m = _CREATE_TABLE_RE.match(stmt)
    if not m:
        return None

    body = stmt[m.end():]
    start = body.find("(")
    if start < 0:
        return None

    depth = 0
    end = -1
    for idx in range(start, len(body)):
        ch = body[idx]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                end = idx
                break
    if end < 0:
        return None

    columns_blob = body[start + 1:end]
    items = _split_top_level_csv(columns_blob)

    outlines: List[str] = []
    for item in items:
        token = item.strip()
        if not token:
            continue
        if re.match(r"^(primary\s+key|unique\b|key\b|constraint\b|index\b|foreign\s+key|check\b)", token, re.IGNORECASE):
            continue
        parts = re.split(r"\s+", token, maxsplit=2)
        if len(parts) < 2:
            continue
        col = parts[0].strip("`\"")
        dtype = parts[1]
        not_null = " NOT NULL" if re.search(r"\bnot\s+null\b", token, re.IGNORECASE) else ""
        outlines.append(f"{col} {dtype}{not_null}")

    if not outlines:
        return None

    limit = 8
    head = outlines[:limit]
    suffix = f" (+{len(outlines) - limit} cols)" if len(outlines) > limit else ""
    return " | ".join(head) + suffix


def _structure_outline(stmt: str) -> str:
    create_outline = _extract_create_table_outline(stmt)
    if create_outline:
        return create_outline

    compact = re.sub(r"\s+", " ", stmt).strip()
    return compact[:220] + ("..." if len(compact) > 220 else "")


def _build_grouped_issues(issues: List[Dict], structure_group_map: Optional[Dict[str, Dict]] = None) -> List[Dict]:
    grouped: Dict[Tuple[str, str, str, str, str], Dict] = {}
    for item in issues:
        group_id = str(item.get("structure_group") or "SG-UNGROUPED")
        source = str(item.get("source") or "unknown")
        level = str(item.get("level") or "P3")
        rule_id = str(item.get("rule_id") or "RG-UNKNOWN")
        message = str(item.get("message") or "")
        key = (group_id, source, level, rule_id, message)

        row = grouped.get(key)
        if not row:
            row = {
                "structure_group": group_id,
                "source": source,
                "level": level,
                "rule_id": rule_id,
                "message": message,
                "occurrence_count": 0,
                "statement_indices": [],
                "line_ranges": [],
                "table_names": set(),
                "sample_sql_fragment": item.get("sql_fragment"),
                "hint": item.get("hint"),
                "ddl_references": {},
                "structure_outline": item.get("structure_outline"),
            }
            grouped[key] = row

        row["occurrence_count"] += 1
        stmt_idx = item.get("statement_index")
        if isinstance(stmt_idx, int):
            row["statement_indices"].append(stmt_idx)
        line_start = item.get("line_start")
        line_end = item.get("line_end")
        if isinstance(line_start, int) and isinstance(line_end, int):
            row["line_ranges"].append([line_start, line_end])
        for t in item.get("table_names", []) or []:
            if t:
                row["table_names"].add(str(t))

        ddl_ref = item.get("ddl_reference")
        if isinstance(ddl_ref, dict):
            ddl_key = (
                ddl_ref.get("statement_index"),
                ddl_ref.get("line_start"),
                ddl_ref.get("line_end"),
                ddl_ref.get("ddl_type"),
                ddl_ref.get("sql_fragment"),
            )
            if ddl_key not in row["ddl_references"]:
                row["ddl_references"][ddl_key] = {
                    "statement_index": ddl_ref.get("statement_index"),
                    "line_start": ddl_ref.get("line_start"),
                    "line_end": ddl_ref.get("line_end"),
                    "ddl_type": ddl_ref.get("ddl_type"),
                    "sql_fragment": ddl_ref.get("sql_fragment"),
                }

    result: List[Dict] = []
    for row in grouped.values():
        group_meta = (structure_group_map or {}).get(str(row["structure_group"]), {})
        structure_outline = row.get("structure_outline") or group_meta.get("structure_outline")
        sample_sql_fragment = row.get("sample_sql_fragment") or group_meta.get("sample_sql_fragment")
        result.append(
            {
                "structure_group": row["structure_group"],
                "source": row["source"],
                "level": row["level"],
                "rule_id": row["rule_id"],
                "message": row["message"],
                "occurrence_count": row["occurrence_count"],
                "statement_indices": sorted(row["statement_indices"]),
                "line_ranges": row["line_ranges"],
                "table_names": sorted(row["table_names"]),
                "sample_sql_fragment": sample_sql_fragment,
                "structure_outline": structure_outline,
                "hint": row["hint"],
                "ddl_references": list(row["ddl_references"].values()),
            }
        )

    level_priority = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    result.sort(
        key=lambda x: (
            level_priority.get(str(x.get("level", "P3")), 3),
            -int(x.get("occurrence_count", 0)),
            str(x.get("structure_group", "")),
        )
    )
    return result


def _ddl_type(expr: Optional[exp.Expression], stmt: str) -> Optional[str]:
    lower = stmt.lower()

    if expr is not None:
        if isinstance(expr, exp.Create):
            return "CREATE"
        if isinstance(expr, exp.Alter):
            return "ALTER"
        if isinstance(expr, exp.Drop):
            return "DROP"

        truncate_cls = getattr(exp, "TruncateTable", None)
        if truncate_cls is not None and isinstance(expr, truncate_cls):
            return "TRUNCATE"

        rename_table_cls = getattr(exp, "RenameTable", None)
        if rename_table_cls is not None and isinstance(expr, rename_table_cls):
            return "RENAME"

        # Some sqlglot versions expose RENAME as exp.Rename rather than
        # exp.RenameTable.
        rename_cls = getattr(exp, "Rename", None)
        if rename_cls is not None and isinstance(expr, rename_cls):
            return "RENAME"

    if re.search(r"\bcreate\b", lower):
        return "CREATE"
    if re.search(r"\balter\b", lower):
        return "ALTER"
    if re.search(r"\bdrop\b", lower):
        return "DROP"
    if re.search(r"\btruncate\b", lower):
        return "TRUNCATE"
    if re.search(r"\brename\b", lower):
        return "RENAME"
    return None


def _build_ddl_references(statement_meta: List[Dict], dialect: Optional[str], issues: List[Dict]) -> List[Dict]:
    issue_by_stmt: Dict[int, List[Dict]] = {}
    for issue in issues:
        stmt_idx = issue.get("statement_index")
        if isinstance(stmt_idx, int):
            issue_by_stmt.setdefault(stmt_idx, []).append(issue)

    ddl_refs: List[Dict] = []
    for item in statement_meta:
        stmt = str(item.get("statement") or "").strip()
        if not stmt:
            continue
        expr = parse_stmt(stmt, dialect)
        ddl_kind = _ddl_type(expr, stmt)
        if not ddl_kind:
            continue

        stmt_idx = item.get("statement_index")
        related_issues = issue_by_stmt.get(stmt_idx, []) if isinstance(stmt_idx, int) else []

        rule_ids = sorted({str(i.get("rule_id")) for i in related_issues if i.get("rule_id")})
        levels = sorted({str(i.get("level")) for i in related_issues if i.get("level")})
        row = {
            "statement_index": stmt_idx,
            "line_start": item.get("line_start"),
            "line_end": item.get("line_end"),
            "ddl_type": ddl_kind,
            "sql_fragment": stmt[:400],
            "structure_outline": _structure_outline(stmt),
            "structure_group": _format_structure_group_id(_canonical_stmt_key(stmt, dialect)),
            "issue_count": len(related_issues),
            "rule_ids": rule_ids,
            "levels": levels,
        }
        ddl_refs.append(row)

        for issue in related_issues:
            issue["ddl_reference"] = {
                "statement_index": row["statement_index"],
                "line_start": row["line_start"],
                "line_end": row["line_end"],
                "ddl_type": row["ddl_type"],
                "sql_fragment": row["sql_fragment"],
                "structure_outline": row["structure_outline"],
            }

    ddl_refs.sort(key=lambda x: (int(x.get("statement_index") or 0), str(x.get("ddl_type") or "")))
    return ddl_refs


def dedupe_issues(issues: List[Dict], max_issues: int) -> List[Dict]:
    seen = set()
    merged: List[Dict] = []
    for item in issues:
        key = (
            item.get("rule_id") or f"fallback:{item.get('level', 'P3')}:{item.get('message', '')}",
            (item.get("sql_fragment") or "").strip().lower()[:400],
            item.get("statement_index"),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)

    level_priority = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    merged.sort(key=lambda x: level_priority.get(x.get("level", "P3"), 3))
    return merged[:max_issues]


async def analyze_sql(
    sql: str,
    mode: str,
    dialect: Optional[str],
    max_issues: int,
    policy: Optional[Dict] = None,
    suppressions: Optional[List[Dict]] = None,
    baseline_issues: Optional[List[Dict]] = None,
    ci_gate: Optional[Dict] = None,
) -> Dict:
    statement_meta = split_sql_statements_with_meta(sql, dialect)
    rule_issues: List[Dict] = []
    tables: List[str] = []
    structure_groups: List[Dict] = []
    all_structure_groups: List[Dict] = []

    if mode in {"rule", "hybrid"}:
        # Per-call cache keyed by structural fingerprint.
        # Identical structures (e.g. sharded tables) are analysed once; the
        # cached issue templates are re-stamped with the actual statement
        # index and line numbers for each duplicate.
        _rule_cache: Dict[str, Tuple[List[Dict], List[str]]] = {}
        _group_meta: Dict[str, Dict] = {}
        for item in statement_meta:
            stmt = item["statement"]
            stmt_idx = item.get("statement_index")
            line_s = item.get("line_start")
            line_e = item.get("line_end")

            key = _canonical_stmt_key(stmt, dialect)
            group_id = _format_structure_group_id(key)

            row = _group_meta.get(key)
            if not row:
                row = {
                    "group_id": group_id,
                    "statement_indices": [],
                    "line_ranges": [],
                    "sample_sql_fragment": stmt[:400],
                    "structure_outline": _structure_outline(stmt),
                    "sample_tables": [],
                    "rule_issue_count": 0,
                    "unique_rule_ids": set(),
                }
                _group_meta[key] = row
            row["statement_indices"].append(stmt_idx)
            row["line_ranges"].append([line_s, line_e])

            if key in _rule_cache:
                cached_tmpls, stmt_tables = _rule_cache[key]
                stmt_issues = [
                    {
                        **tmpl,
                        "statement_index": stmt_idx,
                        "line_start": line_s,
                        "line_end": line_e,
                        "sql_fragment": stmt[:400],
                        "structure_outline": row["structure_outline"],
                        "structure_group": group_id,
                        "table_names": sorted(set(stmt_tables)),
                    }
                    for tmpl in cached_tmpls
                ]
            else:
                stmt_issues, stmt_tables = analyze_statement(
                    stmt,
                    dialect,
                    statement_index=stmt_idx,
                    line_start=line_s,
                    line_end=line_e,
                )
                # Store template without position fields so they can be
                # overridden for each duplicate statement.
                _rule_cache[key] = (
                    [
                        {k: v for k, v in issue.items() if k not in ("statement_index", "line_start", "line_end", "sql_fragment")}
                        for issue in stmt_issues
                    ],
                    stmt_tables,
                )

                for issue in stmt_issues:
                    issue["structure_group"] = group_id
                    issue["table_names"] = sorted(set(stmt_tables))
                    issue["structure_outline"] = row["structure_outline"]

            row["sample_tables"] = sorted(set((row.get("sample_tables") or []) + stmt_tables))[:5]
            row["rule_issue_count"] += len(stmt_issues)
            for issue in stmt_issues:
                rid = issue.get("rule_id")
                if rid:
                    row["unique_rule_ids"].add(rid)

            rule_issues.extend(stmt_issues)
            tables.extend(stmt_tables)

        for row in _group_meta.values():
            all_structure_groups.append(
                {
                    "group_id": row["group_id"],
                    "occurrence_count": len(row["statement_indices"]),
                    "statement_indices": row["statement_indices"],
                    "line_ranges": row["line_ranges"],
                    "sample_sql_fragment": row["sample_sql_fragment"],
                    "structure_outline": row["structure_outline"],
                    "sample_tables": row["sample_tables"],
                    "rule_issue_count": row["rule_issue_count"],
                    "unique_rule_ids": sorted(row["unique_rule_ids"]),
                }
            )

        all_structure_groups.sort(key=lambda x: (-x["occurrence_count"], x["group_id"]))
        structure_groups = [item for item in all_structure_groups if int(item.get("occurrence_count", 0)) > 1]

    ai_issues: List[Dict] = []
    ai_error: Optional[str] = None

    if mode in {"ai", "hybrid"}:
        ai_issues, ai_error = await analyze_sql_with_ai(sql, dialect=dialect, max_issues=max_issues)

    merged_issues = rule_issues + ai_issues
    effective_policy = _normalize_policy(policy)
    effective_suppressions = _normalize_suppressions(suppressions)
    policy_issues = _apply_policy(merged_issues, effective_policy, effective_suppressions)
    ddl_references = _build_ddl_references(statement_meta, dialect, policy_issues)
    structure_group_map = {str(item.get("group_id")): item for item in all_structure_groups}
    grouped_issues = _build_grouped_issues(policy_issues, structure_group_map=structure_group_map)
    issues = dedupe_issues(policy_issues, max_issues=max_issues)
    unique_rule_count = len({i.get("rule_id") for i in issues if i.get("rule_id")})

    score = risk_score(
        issues,
        statement_count=len(statement_meta),
        table_count=len(set(tables)),
        unique_rule_count=unique_rule_count,
    )
    baseline = _baseline_diff(issues, baseline_issues)
    gate_result = _evaluate_ci_gate(ci_gate, issues, score, ai_error, baseline)

    return {
        "sql": sql,
        "mode": mode,
        "issues": issues,
        "score": score,
        "stats": {
            "statement_count": len(statement_meta),
            "table_count": len(set(tables)),
            "rule_issue_count": len(rule_issues),
            "ai_issue_count": len(ai_issues),
            "total_issue_count": len(issues),
            "grouped_issue_count": len(grouped_issues),
            "unique_rule_count": unique_rule_count,
            "structure_group_total_count": len(all_structure_groups),
            "structure_group_count": len(structure_groups),
            "ddl_reference_count": len(ddl_references),
        },
        "structure_groups": structure_groups,
        "grouped_issues": grouped_issues,
        "ddl_references": ddl_references,
        "tables": sorted(set(tables)),
        "policy": {
            "enabled_rules": sorted(effective_policy.get("enabled_rules", set())),
            "disabled_rules": sorted(effective_policy.get("disabled_rules", set())),
            "enabled_categories": sorted(effective_policy.get("enabled_categories", set())),
            "severity_overrides": effective_policy.get("severity_overrides", {}),
            "suppression_count": len(effective_suppressions),
        },
        "baseline": baseline,
        "ci_gate": gate_result,
        "ai": {
            "enabled": mode in {"ai", "hybrid"},
            "error": ai_error,
        },
    }
