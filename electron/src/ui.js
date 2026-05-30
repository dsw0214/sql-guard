import { state } from "./state.js";
import { escapeHtml, escapeRegExp } from "./helpers.js";
import { filterIssues } from "./reports.js";

export function getRefs() {
    return {
        sql: document.getElementById("sql"),
        reviewBtn: document.getElementById("reviewBtn"),
        uploadReviewBtn: document.getElementById("uploadReviewBtn"),
        sqlFile: document.getElementById("sqlFile"),
        fileMeta: document.getElementById("fileMeta"),
        mode: document.getElementById("mode"),
        dialect: document.getElementById("dialect"),
        highRiskOnly: document.getElementById("highRiskOnly"),
        reportTemplate: document.getElementById("reportTemplate"),
        archiveDiagFilter: document.getElementById("archiveDiagFilter"),
        themeMode: document.getElementById("themeMode"),
        themeColor: document.getElementById("themeColor"),
        serverUrl: document.getElementById("serverUrl"),
        apiToken: document.getElementById("apiToken"),
        aiProvider: document.getElementById("aiProvider"),
        aiBaseUrl: document.getElementById("aiBaseUrl"),
        aiModel: document.getElementById("aiModel"),
        aiApiKey: document.getElementById("aiApiKey"),
        aiHttpTimeout: document.getElementById("aiHttpTimeout"),
        ollamaBaseUrl: document.getElementById("ollamaBaseUrl"),
        ollamaModel: document.getElementById("ollamaModel"),
        ollamaHttpTimeout: document.getElementById("ollamaHttpTimeout"),
        openaiConfigGroup: document.getElementById("openaiConfigGroup"),
        ollamaConfigGroup: document.getElementById("ollamaConfigGroup"),
        loadAiConfigBtn: document.getElementById("loadAiConfigBtn"),
        saveAiConfigBtn: document.getElementById("saveAiConfigBtn"),
        aiConfigStatus: document.getElementById("aiConfigStatus"),
        previewScrollMode: document.getElementById("previewScrollMode"),
        exportJsonBtn: document.getElementById("exportJsonBtn"),
        exportMdBtn: document.getElementById("exportMdBtn"),
        exportCurrentFileBtn: document.getElementById("exportCurrentFileBtn"),
        exportCurrentFileJsonBtn: document.getElementById("exportCurrentFileJsonBtn"),
        resetSettingsBtn: document.getElementById("resetSettingsBtn"),
        resetExportSettingsBtn: document.getElementById("resetExportSettingsBtn"),
        loading: document.getElementById("loading"),
        result: document.getElementById("result"),
        previewModal: document.getElementById("previewModal"),
        previewMeta: document.getElementById("previewMeta"),
        previewSearch: document.getElementById("previewSearch"),
        previewPrevBtn: document.getElementById("previewPrevBtn"),
        previewNextBtn: document.getElementById("previewNextBtn"),
        previewHitCount: document.getElementById("previewHitCount"),
        previewContent: document.getElementById("previewContent"),
        previewCancelBtn: document.getElementById("previewCancelBtn"),
        confirmDownloadBtn: document.getElementById("confirmDownloadBtn"),
        confirmModal: document.getElementById("confirmModal"),
        confirmMessage: document.getElementById("confirmMessage"),
        confirmCancelBtn: document.getElementById("confirmCancelBtn"),
        confirmOkBtn: document.getElementById("confirmOkBtn"),
        appMeta: document.getElementById("appMeta"),
        backendStatus: document.getElementById("backendStatus"),
        refreshBackendStatusBtn: document.getElementById("refreshBackendStatusBtn"),
        docLink: document.getElementById("docLink"),
    };
}

export function getReviewOptions(refs) {
    return {
        mode: refs.mode.value,
        dialect: refs.dialect.value || "generic",
        maxIssues: 20,
    };
}

export function getFilterOptions(refs) {
    return {
        highRiskOnly: refs.highRiskOnly.checked,
        template: refs.reportTemplate.value,
        archiveDiagFilter: refs.archiveDiagFilter.value,
    };
}

export function setReviewingState(refs, isLoading, message) {
    state.reviewing = isLoading;
    refs.reviewBtn.disabled = isLoading;
    refs.uploadReviewBtn.disabled = isLoading;
    refs.reviewBtn.textContent = isLoading ? "检测中..." : "开始检测";
    refs.uploadReviewBtn.textContent = isLoading ? "上传检测中..." : "上传附件检测";
    refs.loading.style.display = isLoading ? "block" : "none";
    refs.loading.innerHTML = `<span class="spinner"></span>${message || "正在检测 SQL，请稍候..."}`;
}

export function setPreviewNavEnabled(refs, enabled) {
    refs.previewPrevBtn.disabled = !enabled;
    refs.previewNextBtn.disabled = !enabled;
}

export function updateCurrentFileExportButton(refs) {
    const archiveFiles = state.lastResult && state.lastResult.attachment && state.lastResult.attachment.is_archive && Array.isArray(state.lastResult.attachment.files);
    const enabled = !!(archiveFiles && state.currentExpandedFile);
    refs.exportCurrentFileBtn.disabled = !enabled;
    refs.exportCurrentFileJsonBtn.disabled = !enabled;
}

export function setExportEnabled(refs, enabled) {
    refs.exportJsonBtn.disabled = !enabled;
    refs.exportMdBtn.disabled = !enabled;
    updateCurrentFileExportButton(refs);
}

function renderIssueBlock(issue) {
    const level = String(issue.level || "P3").toUpperCase();
    const levelClass = ["P0", "P1", "P2", "P3"].includes(level) ? `level-${level.toLowerCase()}` : "level-p3";
    const structureGroup = issue.structure_group ? String(issue.structure_group) : "";
    const occurrenceCount = Number(issue.occurrence_count || 0);
    const statementIndices = Array.isArray(issue.statement_indices) ? issue.statement_indices.filter(Number.isInteger) : [];
    const stmtRange = statementIndices.length
        ? `${statementIndices[0]}-${statementIndices[statementIndices.length - 1]}`
        : "";
    const stmtIndex = Number.isInteger(issue.statement_index) ? issue.statement_index : null;
    const lineStart = Number.isInteger(issue.line_start) ? issue.line_start : null;
    const lineEnd = Number.isInteger(issue.line_end) ? issue.line_end : null;
    const ddlType = issue.ddl_reference && issue.ddl_reference.ddl_type
        ? String(issue.ddl_reference.ddl_type)
        : "";
    const structureOutline = String((issue.ddl_reference && issue.ddl_reference.structure_outline) || issue.structure_outline || "").trim();
    const fragment = String((issue.ddl_reference && issue.ddl_reference.sql_fragment) || issue.sql_fragment || "").trim();

    const metaParts = [`来源: ${escapeHtml(issue.source || "rule")}`];
    if (structureGroup) {
        metaParts.push(`结构组: ${escapeHtml(structureGroup)}`);
    }
    if (stmtIndex !== null) {
        metaParts.push(`语句#${stmtIndex}`);
    }
    if (statementIndices.length > 1) {
        metaParts.push(`语句组:${stmtRange}`);
    }
    if (lineStart !== null) {
        metaParts.push(lineEnd !== null && lineEnd !== lineStart ? `行 ${lineStart}-${lineEnd}` : `行 ${lineStart}`);
    }
    if (occurrenceCount > 1) {
        metaParts.push(`同结构命中 ${occurrenceCount} 次`);
    }
    if (ddlType) {
        metaParts.push(`DDL: ${escapeHtml(ddlType)}`);
    }

    return `
        <div class="issue ${levelClass}">
            <b class="issue-level">${escapeHtml(level)}</b> <span class="meta">${metaParts.join(" | ")}</span><br>
            ${escapeHtml(issue.message)}${issue.hint ? `<div class="meta">建议: ${escapeHtml(issue.hint)}</div>` : ""}
            ${structureOutline ? `<div class="meta">结构: <code>${escapeHtml(structureOutline.length > 260 ? `${structureOutline.slice(0, 260)}...` : structureOutline)}</code></div>` : ""}
            ${fragment ? `<div class="meta">SQL: <code>${escapeHtml(fragment.length > 220 ? `${fragment.slice(0, 220)}...` : fragment)}</code></div>` : ""}
        </div>
    `;
}

function renderGroupedIssues(issues) {
    if (!Array.isArray(issues) || issues.length === 0) {
        return "";
    }

    const levelOrder = ["P0", "P1", "P2", "P3"];
    const groups = new Map();

    issues.forEach((issue) => {
        const level = String(issue.level || "P3").toUpperCase();
        const normalized = levelOrder.includes(level) ? level : "P3";
        const sg = issue.structure_group ? String(issue.structure_group) : "SG-UNGROUPED";
        const key = `${normalized}|${sg}`;
        if (!groups.has(key)) {
            groups.set(key, { level: normalized, structureGroup: sg, items: [] });
        }
        groups.get(key).items.push(issue);
    });

    const sections = Array.from(groups.values()).sort((left, right) => {
        const leftIdx = levelOrder.indexOf(left.level);
        const rightIdx = levelOrder.indexOf(right.level);
        if (leftIdx !== rightIdx) {
            return leftIdx - rightIdx;
        }
        if (right.items.length !== left.items.length) {
            return right.items.length - left.items.length;
        }
        return left.structureGroup.localeCompare(right.structureGroup);
    });

    return sections
        .map((section) => {
            const levelClass = `severity-group severity-${section.level.toLowerCase()}`;
            return `
                <section class="${levelClass}">
                    <div class="severity-group-title">${section.level} · ${escapeHtml(section.structureGroup)} · ${section.items.length} 条</div>
                    ${section.items.map(renderIssueBlock).join("")}
                </section>
            `;
        })
        .join("");
}

function buildArchiveTree(paths) {
    const root = {};
    paths.forEach((path) => {
        const clean = String(path || "").replace(/\\/g, "/").replace(/^\/+/, "");
        if (!clean) {
            return;
        }
        const parts = clean.split("/").filter(Boolean);
        let node = root;
        parts.forEach((part, idx) => {
            if (!node[part]) {
                node[part] = { __children: {}, __leaf: false };
            }
            if (idx === parts.length - 1) {
                node[part].__leaf = true;
            }
            node = node[part].__children;
        });
    });
    return root;
}

function renderTreeNode(node) {
    const keys = Object.keys(node).sort((a, b) => a.localeCompare(b));
    if (keys.length === 0) {
        return "";
    }

    let html = '<ul class="tree">';
    keys.forEach((key) => {
        const item = node[key];
        const hasChildren = Object.keys(item.__children).length > 0;
        html += `<li>${escapeHtml(key)}`;
        if (hasChildren) {
            html += renderTreeNode(item.__children);
        }
        html += "</li>";
    });
    html += "</ul>";
    return html;
}

function renderArchiveOverview(data) {
    const files = Array.isArray(data?.attachment?.files) ? data.attachment.files : [];
    const riskyFiles = files.filter((file) => Number(file?.stats?.total_issue_count || 0) > 0).length;
    const cleanFiles = Math.max(0, files.length - riskyFiles);

    return `
        <div class="archive-overview">
            <div class="archive-stat">
                <span class="archive-stat-label">分析文件</span>
                <strong class="archive-stat-value">${data.stats?.analyzed_file_count ?? data.stats?.file_count ?? 0}</strong>
            </div>
            <div class="archive-stat">
                <span class="archive-stat-label">有风险文件</span>
                <strong class="archive-stat-value">${riskyFiles}</strong>
            </div>
            <div class="archive-stat">
                <span class="archive-stat-label">无风险文件</span>
                <strong class="archive-stat-value">${cleanFiles}</strong>
            </div>
            <div class="archive-stat">
                <span class="archive-stat-label">总问题数</span>
                <strong class="archive-stat-value">${data.stats?.total_issue_count ?? 0}</strong>
            </div>
        </div>
    `;
}

function renderArchiveFileSummary(file) {
    const stats = file?.stats || {};
    const levelCount = { P0: 0, P1: 0, P2: 0, P3: 0 };

    (Array.isArray(file?.issues) ? file.issues : []).forEach((issue) => {
        const level = String(issue?.level || "P3").toUpperCase();
        levelCount[level] = (levelCount[level] || 0) + 1;
    });

    return `
        <div class="file-summary-row">
            <span class="file-summary-chip chip-p0">P0 ${levelCount.P0}</span>
            <span class="file-summary-chip chip-p1">P1 ${levelCount.P1}</span>
            <span class="file-summary-chip chip-p2">P2 ${levelCount.P2}</span>
            <span class="file-summary-chip chip-p3">P3 ${levelCount.P3}</span>
            <span class="meta">语句数: ${stats.statement_count ?? 0}</span>
            <span class="meta">问题数: ${stats.total_issue_count ?? 0}</span>
        </div>
    `;
}

function buildAiErrorGuidance(errorMessage) {
    const msg = String(errorMessage || "").toLowerCase();
    if (!msg) {
        return "";
    }

    if (msg.includes("ollama") && msg.includes("超时")) {
        return "建议: 提高 SQLGUARD_OLLAMA_HTTP_TIMEOUT（例如 300/600），并确认 Ollama 模型可及时响应。";
    }

    if (msg.includes("超时")) {
        return "建议: 提高 SQLGUARD_AI_HTTP_TIMEOUT 或 SQLGUARD_OLLAMA_HTTP_TIMEOUT，并检查模型端响应速度。";
    }

    if (msg.includes("网络异常") || msg.includes("failed") || msg.includes("connect")) {
        return "建议: 检查 AI 服务地址与端口是否可达，并确认 provider 与模型配置一致。";
    }

    if (msg.includes("未配置") && msg.includes("api_key")) {
        return "建议: 设置 SQLGUARD_AI_API_KEY，或将 SQLGUARD_AI_PROVIDER 切换为 ollama。";
    }

    return "";
}

export function renderResult(refs, data, mode) {
    state.lastResult = data;
    state.lastRenderMode = mode || data.mode || "hybrid";
    state.currentExpandedFile = null;
    setExportEnabled(refs, true);

    const { highRiskOnly, archiveDiagFilter } = getFilterOptions(refs);
    const sourceIssues = Array.isArray(data.grouped_issues) && data.grouped_issues.length
        ? data.grouped_issues
        : data.issues;
    const displayIssues = filterIssues(sourceIssues, highRiskOnly);

    let html = `<h2>检测结果</h2>
        <p class="meta">模式: ${data.mode || mode} | 风险分: ${data.score ?? 0} | 问题数: ${data.stats?.total_issue_count ?? 0}</p>`;

    if (highRiskOnly) {
        html += '<p class="meta">当前仅展示高风险问题（P0/P1）</p>';
    }

    if (data.attachment) {
        html += `<p class="meta">附件: ${data.attachment.filename} (${data.attachment.size} bytes)</p>`;
        if (data.attachment.is_archive) {
            html += `<p class="meta">压缩包分析文件数: ${data.stats?.analyzed_file_count ?? data.stats?.file_count ?? 0} | 跳过: ${data.stats?.skipped_file_count ?? 0} | 失败: ${data.stats?.failed_file_count ?? 0}</p>`;
            html += `<p class="meta">并发分析: ${data.attachment.analyze_concurrency ?? "n/a"}</p>`;
            html += `<p class="meta">唯一SQL内容数: ${data.attachment.unique_sql_count ?? "n/a"} | 重复内容文件数: ${data.stats?.duplicate_sql_file_count ?? 0}</p>`;

            const zipSummary = data.attachment.archive_summary;
            if (zipSummary) {
                html += `<p class="meta">压缩包条目: ${zipSummary.total_entries ?? 0} | 隐藏文件: ${zipSummary.hidden_entries ?? 0} | 系统元数据: ${zipSummary.system_meta_entries ?? 0} | 非SQL: ${zipSummary.non_sql_entries ?? 0} | 空文件: ${zipSummary.empty_entries ?? 0} | 编码失败: ${zipSummary.decode_failed_entries ?? 0} | 读取失败: ${zipSummary.read_failed_entries ?? 0} | 路径异常: ${zipSummary.unsafe_path_entries ?? 0} | 超限: ${zipSummary.oversized_entries ?? 0}</p>`;
            }

            const failedFiles = Array.isArray(data.attachment.failed_files) ? data.attachment.failed_files : [];
            const skippedFiles = (Array.isArray(data.attachment.skipped_files) ? data.attachment.skipped_files : [])
                .filter((f) => String(f?.reason || "") !== "hidden-file");

            if (archiveDiagFilter !== "none" && archiveDiagFilter !== "duplicates" && (failedFiles.length > 0 || skippedFiles.length > 0)) {
                html += "<div class=\"file-detail\"><summary>压缩包诊断明细</summary>";

                if (archiveDiagFilter !== "skipped" && failedFiles.length > 0) {
                    html += "<p class=\"meta\">失败文件</p>";
                    html += failedFiles.map((f) => `<div class=\"issue\"><b>${escapeHtml(f.filename || "unknown")}</b><br>${escapeHtml(f.error || "分析失败")}</div>`).join("");
                }

                if (archiveDiagFilter !== "failed" && skippedFiles.length > 0) {
                    html += "<p class=\"meta\">跳过文件</p>";
                    html += skippedFiles.map((f) => `<div class=\"issue\"><b>${escapeHtml(f.filename || "unknown")}</b><br>原因: ${escapeHtml(f.reason || "unknown")}</div>`).join("");
                }

                html += "</div>";
            }

            const contentGroups = Array.isArray(data.attachment.content_groups) ? data.attachment.content_groups : [];
            const displayGroups = archiveDiagFilter === "duplicates"
                ? contentGroups.filter((g) => Number(g.file_count || 0) > 1)
                : contentGroups;

            if (displayGroups.length > 0 && archiveDiagFilter !== "none") {
                html += "<div class=\"file-detail\"><summary>同内容分组</summary>";
                html += displayGroups
                    .map((g) => {
                        const sample = Array.isArray(g.sample_files) ? g.sample_files.join(", ") : "";
                        return `<p class=\"meta\">${escapeHtml(g.group_id || "unknown")} | 文件数: ${g.file_count ?? 0}${sample ? ` | 示例: ${escapeHtml(sample)}` : ""}</p>`;
                    })
                    .join("");
                html += "</div>";
            } else if (archiveDiagFilter === "duplicates") {
                html += '<p class="meta">当前压缩包没有重复内容组</p>';
            }
        }
    }

    if (data.ai?.error) {
        const guidance = buildAiErrorGuidance(data.ai.error);
        html += `<div class="issue"><b>AI提示</b><br>${escapeHtml(String(data.ai.error))}${guidance ? `<div class="meta">${escapeHtml(guidance)}</div>` : ""}</div>`;
    }

    if (data.attachment?.is_archive && Array.isArray(data.attachment.files)) {
        html += "<h3>压缩包汇总</h3>";
        html += renderArchiveOverview(data);
        if (!displayIssues.length) {
            html += '<p class="meta">整包聚合结果未发现风险，详细结论请查看分文件结果。</p>';
        } else {
            html += '<p class="meta">整包统计仅用于汇总，详细风险请以下方分文件结果为准。</p>';
        }
    } else if (!displayIssues.length) {
        html += "<p>未发现风险</p>";
    } else {
        html += renderGroupedIssues(displayIssues);
    }

    if (data.attachment?.is_archive && Array.isArray(data.attachment.files)) {
        const fileNames = data.attachment.files.map((f) => f.filename);
        html += "<h3>压缩包目录</h3>";
        html += renderTreeNode(buildArchiveTree(fileNames));

        html += "<h3>分文件结果</h3>";
        const filesForDisplay = archiveDiagFilter === "duplicates"
            ? data.attachment.files.filter((f) => Number(f.content_group_size || 1) > 1)
            : data.attachment.files;

        filesForDisplay.sort((left, right) => {
            const rightIssues = Number(right?.stats?.total_issue_count || 0);
            const leftIssues = Number(left?.stats?.total_issue_count || 0);
            if (rightIssues !== leftIssues) {
                return rightIssues - leftIssues;
            }
            return Number(right?.score || 0) - Number(left?.score || 0);
        });

        filesForDisplay.forEach((file) => {
            const fileSourceIssues = Array.isArray(file.grouped_issues) && file.grouped_issues.length
                ? file.grouped_issues
                : file.issues;
            const fileIssues = filterIssues(fileSourceIssues, highRiskOnly);
            html += `
                <details class="file-detail" data-filename="${escapeHtml(file.filename)}">
                    <summary>${escapeHtml(file.filename)} | 分组: ${escapeHtml(file.content_group || "n/a")} | 同组文件数: ${file.content_group_size ?? 1} | 风险分: ${file.score ?? 0} | 问题数: ${file.stats?.total_issue_count ?? 0} | 大小: ${file.size} bytes</summary>
                    ${renderArchiveFileSummary(file)}
                    ${fileIssues.length === 0 ? '<p class="meta">该文件未发现符合当前筛选条件的风险</p>' : renderGroupedIssues(fileIssues)}
                </details>
            `;
        });

        if (archiveDiagFilter === "duplicates" && filesForDisplay.length === 0) {
            html += '<p class="meta">当前压缩包没有可显示的重复内容文件</p>';
        }
    }

    refs.result.innerHTML = html;
}

export function renderError(refs, err) {
    setExportEnabled(refs, false);
    state.lastResult = null;
    state.currentExpandedFile = null;

    const isTimeout = err && err.name === "AbortError";
    const msg = isTimeout
        ? "请求超时（20秒），请检查后端状态或网络连接"
        : (err && err.message ? err.message : "请求失败，请确认后端是否启动");

    refs.result.innerHTML = `
        <h2>检测结果</h2>
        <div class="issue">
            <b>ERROR</b><br>
            ${escapeHtml(msg)}
        </div>
    `;
}

export function openPreviewModal(refs, type, filename, content, mimeType) {
    state.previewState = { type, filename, content, mimeType };
    refs.previewMeta.textContent = `格式: ${type.toUpperCase()} | 文件名: ${filename}`;
    refs.previewSearch.value = "";
    state.previewMatchIndex = -1;
    state.previewMatchCount = 0;
    setPreviewNavEnabled(refs, false);
    renderPreviewContent(refs, "");
    refs.previewModal.style.display = "flex";
}

export function closePreviewModal(refs) {
    refs.previewModal.style.display = "none";
    state.previewMatchIndex = -1;
    state.previewMatchCount = 0;
}

export function renderPreviewContent(refs, keyword) {
    const raw = state.previewState.content || "";
    if (!keyword) {
        refs.previewContent.textContent = raw;
        refs.previewContent.scrollTop = 0;
        refs.previewHitCount.textContent = "0/0";
        state.previewMatchIndex = -1;
        state.previewMatchCount = 0;
        setPreviewNavEnabled(refs, false);
        return;
    }

    const escapedKeyword = escapeRegExp(keyword);
    const regex = new RegExp(escapedKeyword, "gi");
    const matches = raw.match(regex) || [];
    const highlighted = escapeHtml(raw).replace(new RegExp(escapedKeyword, "gi"), (m) => `<mark class="preview-hit">${escapeHtml(m)}</mark>`);

    refs.previewContent.innerHTML = highlighted;
    state.previewMatchCount = matches.length;

    if (state.previewMatchCount === 0) {
        state.previewMatchIndex = -1;
        refs.previewHitCount.textContent = "0/0";
        setPreviewNavEnabled(refs, false);
        return;
    }

    state.previewMatchIndex = 0;
    focusPreviewMatch(refs, state.previewMatchIndex);
    refs.previewHitCount.textContent = `1/${state.previewMatchCount}`;
    setPreviewNavEnabled(refs, true);
}

function focusPreviewMatch(refs, index) {
    const nodes = Array.from(refs.previewContent.querySelectorAll("mark.preview-hit"));
    if (!nodes.length) {
        return;
    }

    nodes.forEach((n) => n.classList.remove("preview-hit-active"));
    const target = nodes[index];
    if (!target) {
        return;
    }

    target.classList.add("preview-hit-active");
    const scrollMode = refs.previewScrollMode.value || "smooth";
    target.scrollIntoView({ block: "center", behavior: scrollMode === "instant" ? "auto" : "smooth" });
}

export function jumpPreviewHit(refs, step) {
    if (!state.previewMatchCount) {
        return;
    }

    state.previewMatchIndex = (state.previewMatchIndex + step + state.previewMatchCount) % state.previewMatchCount;
    focusPreviewMatch(refs, state.previewMatchIndex);
    refs.previewHitCount.textContent = `${state.previewMatchIndex + 1}/${state.previewMatchCount}`;
}

export function showConfirm(refs, message) {
    return new Promise((resolve) => {
        state.confirmResolver = resolve;
        refs.confirmMessage.textContent = message;
        refs.confirmModal.style.display = "flex";
    });
}

export function resolveConfirm(refs, ok) {
    refs.confirmModal.style.display = "none";
    if (state.confirmResolver) {
        const fn = state.confirmResolver;
        state.confirmResolver = null;
        fn(!!ok);
    }
}
