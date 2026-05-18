from io import BytesIO
import asyncio
import hashlib
import os
import zipfile
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, UploadFile

from .analyzer import analyze_sql, dedupe_issues, risk_score

ALLOWED_SQL_EXTENSIONS = {".sql", ".txt"}
ALLOWED_EXTENSIONS = {".sql", ".txt", ".zip"}
MAX_FILE_SIZE = 2 * 1024 * 1024
MAX_ZIP_ENTRIES = 100
MAX_ZIP_TOTAL_UNCOMPRESSED = 10 * 1024 * 1024
MAX_SKIP_DETAIL_RECORDS = 300
ZIP_ANALYZE_CONCURRENCY = max(1, min(16, int(os.getenv("SQLGUARD_ZIP_ANALYZE_CONCURRENCY", "4"))))


def _get_extension(filename: str) -> str:
    idx = filename.rfind(".")
    return filename[idx:].lower() if idx >= 0 else ""


def _decode_content(content: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=400, detail="文件编码不支持，请使用 UTF-8 或 GB18030")


def _validate_file(filename: str, size: int) -> None:
    if not filename:
        raise HTTPException(status_code=400, detail="缺少文件名")

    ext = _get_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 .sql、.txt 或 .zip 文件")

    if size == 0:
        raise HTTPException(status_code=400, detail="上传文件为空")

    if size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"文件过大，限制 {MAX_FILE_SIZE // (1024 * 1024)}MB")


def _validate_zip_size(size: int) -> None:
    if size == 0:
        raise HTTPException(status_code=400, detail="上传文件为空")
    if size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"压缩包过大，限制 {MAX_FILE_SIZE // (1024 * 1024)}MB")


def _normalize_zip_name(name: str) -> str:
    return name.replace("\\", "/").strip()


def _normalize_sql_for_hash(sql_text: str) -> str:
    normalized_lines = [line.rstrip() for line in sql_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(normalized_lines).strip()


def _format_group_id(sql_hash: str) -> str:
    return f"G-{sql_hash[:10].upper()}"


def _is_safe_zip_entry(name: str) -> bool:
    if not name:
        return False
    if name.startswith("/"):
        return False
    parts = [p for p in name.split("/") if p not in ("", ".")]
    return all(p != ".." for p in parts)


def _is_hidden_zip_entry(name: str) -> bool:
    parts = [p for p in name.split("/") if p not in ("", ".")]
    return any(part.startswith(".") for part in parts)


def _is_system_meta_zip_entry(name: str) -> bool:
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if not parts:
        return False
    return parts[0].upper() == "__MACOSX"


def _extract_sql_files_from_zip(raw: bytes) -> Tuple[List[Tuple[str, str, int]], Dict[str, int], List[Dict[str, str]]]:
    files: List[Tuple[str, str, int]] = []
    total_uncompressed = 0
    skipped_files: List[Dict[str, str]] = []
    summary = {
        "total_entries": 0,
        "unsafe_path_entries": 0,
        "hidden_entries": 0,
        "system_meta_entries": 0,
        "non_sql_entries": 0,
        "empty_entries": 0,
        "oversized_entries": 0,
        "decode_failed_entries": 0,
        "read_failed_entries": 0,
    }

    def _record_skip(name: str, reason: str) -> None:
        if len(skipped_files) >= MAX_SKIP_DETAIL_RECORDS:
            return
        skipped_files.append({"filename": name, "reason": reason})

    try:
        with zipfile.ZipFile(BytesIO(raw)) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_ZIP_ENTRIES:
                raise HTTPException(status_code=400, detail=f"压缩包文件数量过多，限制 {MAX_ZIP_ENTRIES} 个")

            for info in infos:
                summary["total_entries"] += 1
                if info.is_dir():
                    continue

                name = _normalize_zip_name(info.filename)
                if not _is_safe_zip_entry(name):
                    summary["unsafe_path_entries"] += 1
                    _record_skip(name, "unsafe-path")
                    continue

                if _is_hidden_zip_entry(name):
                    summary["hidden_entries"] += 1
                    _record_skip(name, "hidden-file")
                    continue

                if _is_system_meta_zip_entry(name):
                    summary["system_meta_entries"] += 1
                    _record_skip(name, "system-meta")
                    continue

                ext = _get_extension(name)
                total_uncompressed += info.file_size

                if total_uncompressed > MAX_ZIP_TOTAL_UNCOMPRESSED:
                    raise HTTPException(status_code=400, detail="压缩包解压后总大小超限（10MB）")

                if ext not in ALLOWED_SQL_EXTENSIONS:
                    summary["non_sql_entries"] += 1
                    _record_skip(name, "non-sql")
                    continue

                if info.file_size == 0:
                    summary["empty_entries"] += 1
                    _record_skip(name, "empty")
                    continue

                if info.file_size > MAX_FILE_SIZE:
                    summary["oversized_entries"] += 1
                    _record_skip(name, "oversized")
                    continue

                try:
                    content = zf.read(info)
                except Exception:
                    summary["read_failed_entries"] += 1
                    _record_skip(name, "read-failed")
                    continue

                try:
                    sql_text = _decode_content(content).strip()
                except HTTPException:
                    summary["decode_failed_entries"] += 1
                    _record_skip(name, "decode-failed")
                    continue

                if not sql_text:
                    summary["empty_entries"] += 1
                    _record_skip(name, "empty")
                    continue

                files.append((name, sql_text, info.file_size))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="无效的 ZIP 压缩包")

    if not files:
        raise HTTPException(status_code=400, detail="压缩包中未找到可用的 .sql/.txt 文件（请检查编码、内容与后缀）")

    return files, summary, skipped_files


async def _review_single_sql_text(sql_text: str, mode: str, dialect: Optional[str], max_issues: int) -> Dict:
    return await analyze_sql(sql_text, mode, dialect, max_issues)


async def _review_zip_sql_files(
    filename: str,
    raw: bytes,
    mode: str,
    dialect: Optional[str],
    max_issues: int,
) -> Dict:
    files, zip_summary, skipped_files = _extract_sql_files_from_zip(raw)

    aggregate_issues: List[Dict] = []
    total_statement_count = 0
    total_table_count = 0
    total_rule_issue_count = 0
    total_ai_issue_count = 0
    file_results: List[Dict] = []

    failed_files: List[Dict[str, str]] = []
    semaphore = asyncio.Semaphore(ZIP_ANALYZE_CONCURRENCY)
    analysis_cache: Dict[str, Dict] = {}

    # Group files by normalized SQL hash so same content gets the same analysis result.
    grouped_files: Dict[str, Dict[str, object]] = {}
    for inner_name, sql_text, inner_size in files:
        sql_key = hashlib.sha256(_normalize_sql_for_hash(sql_text).encode("utf-8")).hexdigest()
        if sql_key not in grouped_files:
            grouped_files[sql_key] = {
                "sql_text": sql_text,
                "group_id": _format_group_id(sql_key),
                "files": [],
            }
        grouped_files[sql_key]["files"].append((inner_name, inner_size))

    async def _analyze_one(sql_key: str, sql_text: str) -> Optional[Dict]:
        async with semaphore:
            try:
                result = await _review_single_sql_text(sql_text, mode, dialect, max_issues)
                analysis_cache[sql_key] = result
                return result
            except Exception as exc:  # pragma: no cover - defensive guard for partial failure
                grouped = grouped_files.get(sql_key, {})
                group_items = grouped.get("files", [])
                for file_name, _ in group_items:
                    failed_files.append(
                        {
                            "filename": file_name,
                            "error": str(exc)[:300] or "分析失败",
                        }
                    )
                return None

    analyzed = await asyncio.gather(
        *[
            _analyze_one(sql_key, grouped["sql_text"])
            for sql_key, grouped in grouped_files.items()
        ]
    )

    for sql_key, item in zip(grouped_files.keys(), analyzed):
        if not item:
            continue

        result = analysis_cache.get(sql_key)
        if not result:
            continue

        grouped = grouped_files.get(sql_key, {})
        group_items = grouped.get("files", [])
        group_id = grouped.get("group_id", _format_group_id(sql_key))

        for inner_name, inner_size in group_items:
            for issue in result.get("issues", []):
                aggregate_issues.append(
                    {
                        **issue,
                        "message": f"[{inner_name}] {issue.get('message', '')}",
                    }
                )

            file_results.append(
                {
                    "filename": inner_name,
                    "size": inner_size,
                    "score": result.get("score", 0),
                    "issues": result.get("issues", []),
                    "stats": result.get("stats", {}),
                    "content_group": group_id,
                    "content_group_size": len(group_items),
                }
            )

        stats = result.get("stats", {})
        group_count = len(group_items)
        total_statement_count += int(stats.get("statement_count", 0)) * group_count
        total_table_count += int(stats.get("table_count", 0)) * group_count
        total_rule_issue_count += int(stats.get("rule_issue_count", 0)) * group_count
        total_ai_issue_count += int(stats.get("ai_issue_count", 0)) * group_count

    if not file_results:
        raise HTTPException(status_code=400, detail="压缩包中 SQL 文件解析失败，无法完成分析")

    merged_issues = dedupe_issues(aggregate_issues, max_issues=max(max_issues, len(aggregate_issues)))
    merged_issues.sort(key=lambda x: {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(x.get("level", "P3"), 3))

    skipped_file_count = (
        zip_summary["unsafe_path_entries"]
        + zip_summary["hidden_entries"]
        + zip_summary["system_meta_entries"]
        + zip_summary["non_sql_entries"]
        + zip_summary["empty_entries"]
        + zip_summary["oversized_entries"]
        + zip_summary["decode_failed_entries"]
        + zip_summary["read_failed_entries"]
    )

    content_groups = []
    for sql_key, grouped in grouped_files.items():
        group_items = grouped.get("files", [])
        content_groups.append(
            {
                "group_id": grouped.get("group_id", _format_group_id(sql_key)),
                "file_count": len(group_items),
                "sample_files": [name for name, _ in group_items[:5]],
            }
        )

    unique_rule_count = len({i.get("rule_id") for i in merged_issues if i.get("rule_id")})

    return {
        "sql": "",
        "mode": mode,
        "issues": merged_issues,
        "score": risk_score(
            merged_issues,
            statement_count=total_statement_count,
            table_count=total_table_count,
            unique_rule_count=unique_rule_count,
        ),
        "stats": {
            "statement_count": total_statement_count,
            "table_count": total_table_count,
            "rule_issue_count": total_rule_issue_count,
            "ai_issue_count": total_ai_issue_count,
            "total_issue_count": len(merged_issues),
            "unique_rule_count": unique_rule_count,
            "file_count": len(file_results),
            "analyzed_file_count": len(file_results),
            "failed_file_count": len(failed_files),
            "skipped_file_count": skipped_file_count,
            "duplicate_sql_file_count": max(0, len(file_results) - len(grouped_files)),
        },
        "ai": {
            "enabled": mode in {"ai", "hybrid"},
            "error": None,
        },
        "attachment": {
            "filename": filename,
            "size": len(raw),
            "is_archive": True,
            "files": file_results,
            "failed_files": failed_files,
            "skipped_files": skipped_files,
            "archive_summary": zip_summary,
            "analyze_concurrency": ZIP_ANALYZE_CONCURRENCY,
            "unique_sql_count": len(grouped_files),
            "content_groups": content_groups,
        },
    }


async def review_sql_attachment(
    upload_file: UploadFile,
    mode: str,
    dialect: Optional[str],
    max_issues: int,
) -> dict:
    filename = upload_file.filename or ""
    raw = await upload_file.read()
    ext = _get_extension(filename)

    if ext == ".zip":
        _validate_zip_size(len(raw))
        return await _review_zip_sql_files(filename, raw, mode, dialect, max_issues)

    _validate_file(filename, len(raw))

    sql_text = _decode_content(raw).strip()
    if not sql_text:
        raise HTTPException(status_code=400, detail="文件内容为空")

    result = await _review_single_sql_text(sql_text, mode, dialect, max_issues)
    result["attachment"] = {
        "filename": filename,
        "size": len(raw),
        "is_archive": False,
    }
    return result
