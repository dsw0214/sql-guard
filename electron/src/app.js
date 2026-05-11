import { state } from "./state.js";
import { sanitizeFilename, downloadText } from "./helpers.js";
import { applyPersistedSettings, applyDefaultSettings, applyDefaultExportSettings, clearSettings, saveSettings } from "./settings.js";
import { reviewSqlRequest, reviewSqlFileRequest, checkBackendStatus } from "./api.js";
import { buildJsonPayload, buildJsonSubReport, toMarkdownReport, toMarkdownSubReport } from "./reports.js";
import { loadDesktopMeta, openExternalSafely } from "./desktop.js";
import { applyTheme, normalizeThemeColor, normalizeThemeMode, syncThemeControls } from "./theme.js";
import { getApiBase } from "./constants.js";
import {
    closePreviewModal,
    getFilterOptions,
    getRefs,
    getReviewOptions,
    jumpPreviewHit,
    openPreviewModal,
    renderError,
    renderPreviewContent,
    renderResult,
    resolveConfirm,
    setReviewingState,
    showConfirm,
    updateCurrentFileExportButton,
} from "./ui.js";

const refs = getRefs();

function applyThemeFromControls() {
    const mode = normalizeThemeMode(refs.themeMode.value);
    const color = normalizeThemeColor(refs.themeColor.value);
    refs.themeMode.value = mode;
    refs.themeColor.value = color;
    applyTheme(mode, color);
    syncThemeControls(refs);
}

async function refreshBackendStatus() {
    if (!refs.backendStatus) {
        return;
    }

    refs.backendStatus.classList.remove("status-ok", "status-bad");
    refs.backendStatus.textContent = "后端状态: 检查中...";

    const result = await checkBackendStatus();
    refs.backendStatus.classList.add(result.ok ? "status-ok" : "status-bad");
    refs.backendStatus.textContent = result.ok ? "后端状态: 在线" : `后端状态: 离线 (${result.message})`;
}

function previewReport(type) {
    if (!state.lastResult) {
        renderError(refs, new Error("暂无可导出的检测结果"));
        return;
    }

    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const options = getFilterOptions(refs);
    const suffix = options.template === "simple" ? "simple" : "detailed";

    if (type === "json") {
        const payload = buildJsonPayload(state.lastResult, options);
        openPreviewModal(
            refs,
            "json",
            `sqlguard-report-${suffix}-${stamp}.json`,
            JSON.stringify(payload, null, 2),
            "application/json;charset=utf-8"
        );
        return;
    }

    openPreviewModal(
        refs,
        "md",
        `sqlguard-report-${suffix}-${stamp}.md`,
        toMarkdownReport(state.lastResult, options),
        "text/markdown;charset=utf-8"
    );
}

function downloadPreviewReport() {
    const { content, filename, mimeType } = state.previewState;
    if (!content || !filename || !mimeType) {
        renderError(refs, new Error("预览内容为空，无法下载"));
        return;
    }

    downloadText(content, filename, mimeType);
    closePreviewModal(refs);
}

function getCurrentExpandedFileResult() {
    if (!state.lastResult || !state.lastResult.attachment || !state.lastResult.attachment.is_archive || !Array.isArray(state.lastResult.attachment.files)) {
        return { error: "当前结果不是压缩包检测，无法导出子报告", file: null };
    }

    if (!state.currentExpandedFile) {
        return { error: "请先展开一个分文件详情后再导出", file: null };
    }

    const file = state.lastResult.attachment.files.find((f) => f.filename === state.currentExpandedFile);
    if (!file) {
        return { error: "未找到当前展开文件的检测结果", file: null };
    }

    return { error: null, file };
}

function exportCurrentFileSubReport() {
    const { error, file } = getCurrentExpandedFileResult();
    if (error) {
        renderError(refs, new Error(error));
        return;
    }

    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const safeName = sanitizeFilename(file.filename);
    const options = getFilterOptions(refs);

    openPreviewModal(
        refs,
        "md",
        `sqlguard-subreport-${safeName}-${stamp}.md`,
        toMarkdownSubReport(file, state.lastResult.mode || "", options.highRiskOnly),
        "text/markdown;charset=utf-8"
    );
}

function exportCurrentFileSubReportJson() {
    const { error, file } = getCurrentExpandedFileResult();
    if (error) {
        renderError(refs, new Error(error));
        return;
    }

    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const safeName = sanitizeFilename(file.filename);
    const options = getFilterOptions(refs);
    const payload = buildJsonSubReport(file, state.lastResult.mode || "", options.highRiskOnly);

    openPreviewModal(
        refs,
        "json",
        `sqlguard-subreport-${safeName}-${stamp}.json`,
        JSON.stringify(payload, null, 2),
        "application/json;charset=utf-8"
    );
}

async function resetSettings() {
    const ok = await showConfirm(refs, "确认重置全部 UI 设置吗？\n此操作会恢复默认项（含检测模式与方言）。");
    if (!ok) {
        return;
    }

    clearSettings();
    applyDefaultSettings(refs);
    saveSettings(refs);

    if (state.lastResult) {
        renderResult(refs, state.lastResult, state.lastRenderMode);
    }
}

async function resetExportSettings() {
    const ok = await showConfirm(refs, "确认仅重置导出相关设置吗？\n（高风险筛选、导出模板、跳转动画）");
    if (!ok) {
        return;
    }

    applyDefaultExportSettings(refs);
    saveSettings(refs);

    if (state.lastResult) {
        renderResult(refs, state.lastResult, state.lastRenderMode);
    }
}

async function reviewSQL() {
    if (state.reviewing) {
        return;
    }

    setReviewingState(refs, true, "正在检测 SQL，请稍候...");
    refs.result.innerHTML = '<h2>检测结果</h2><p class="meta">请求已发送，等待接口返回...</p>';

    const sql = refs.sql.value;
    const options = getReviewOptions(refs);

    try {
        const data = await reviewSqlRequest({
            sql,
            mode: options.mode,
            dialect: options.dialect,
            maxIssues: options.maxIssues,
        });
        renderResult(refs, data, options.mode);
    } catch (err) {
        renderError(refs, err);
    } finally {
        setReviewingState(refs, false);
    }
}

async function reviewSQLFile() {
    if (state.reviewing) {
        return;
    }

    const file = refs.sqlFile.files && refs.sqlFile.files[0];
    if (!file) {
        renderError(refs, new Error("请先选择 SQL 附件（.sql/.txt/.zip）"));
        return;
    }

    const options = getReviewOptions(refs);
    setReviewingState(refs, true, "正在上传并检测附件，请稍候...");
    refs.result.innerHTML = '<h2>检测结果</h2><p class="meta">附件上传中，等待接口返回...</p>';

    try {
        const data = await reviewSqlFileRequest({
            file,
            mode: options.mode,
            dialect: options.dialect,
            maxIssues: options.maxIssues,
        });
        renderResult(refs, data, options.mode);
    } catch (err) {
        renderError(refs, err);
    } finally {
        setReviewingState(refs, false);
    }
}

function bindEvents() {
    refs.reviewBtn.addEventListener("click", reviewSQL);
    refs.uploadReviewBtn.addEventListener("click", reviewSQLFile);
    refs.exportJsonBtn.addEventListener("click", () => previewReport("json"));
    refs.exportMdBtn.addEventListener("click", () => previewReport("md"));
    refs.exportCurrentFileBtn.addEventListener("click", exportCurrentFileSubReport);
    refs.exportCurrentFileJsonBtn.addEventListener("click", exportCurrentFileSubReportJson);
    refs.resetSettingsBtn.addEventListener("click", resetSettings);
    refs.resetExportSettingsBtn.addEventListener("click", resetExportSettings);
    if (refs.refreshBackendStatusBtn) {
        refs.refreshBackendStatusBtn.addEventListener("click", refreshBackendStatus);
    }

    refs.previewCancelBtn.addEventListener("click", () => closePreviewModal(refs));
    refs.confirmDownloadBtn.addEventListener("click", downloadPreviewReport);
    refs.confirmCancelBtn.addEventListener("click", () => resolveConfirm(refs, false));
    refs.confirmOkBtn.addEventListener("click", () => resolveConfirm(refs, true));

    refs.highRiskOnly.addEventListener("change", () => {
        saveSettings(refs);
        if (state.lastResult) {
            renderResult(refs, state.lastResult, state.lastRenderMode);
        }
    });

    refs.reportTemplate.addEventListener("change", () => saveSettings(refs));
    refs.archiveDiagFilter.addEventListener("change", () => {
        saveSettings(refs);
        if (state.lastResult) {
            renderResult(refs, state.lastResult, state.lastRenderMode);
        }
    });
    refs.previewScrollMode.addEventListener("change", () => saveSettings(refs));
    refs.mode.addEventListener("change", () => saveSettings(refs));
    refs.dialect.addEventListener("change", () => saveSettings(refs));
    refs.themeMode.addEventListener("change", () => {
        applyThemeFromControls();
        saveSettings(refs);
    });
    refs.themeColor.addEventListener("input", () => {
        if (refs.themeMode.value !== "custom") {
            return;
        }
        applyThemeFromControls();
        saveSettings(refs);
    });

    refs.serverUrl.addEventListener("change", () => {
        saveSettings(refs);
        refreshBackendStatus(refs);
    });

    refs.previewSearch.addEventListener("input", (e) => {
        renderPreviewContent(refs, (e.target && e.target.value) || "");
    });

    refs.previewSearch.addEventListener("keydown", (e) => {
        if (e.key !== "Enter") {
            return;
        }
        e.preventDefault();
        jumpPreviewHit(refs, e.shiftKey ? -1 : 1);
    });

    refs.previewModal.addEventListener("click", (e) => {
        if (e.target && e.target.id === "previewModal") {
            closePreviewModal(refs);
        }
    });

    refs.confirmModal.addEventListener("click", (e) => {
        if (e.target && e.target.id === "confirmModal") {
            resolveConfirm(refs, false);
        }
    });

    document.addEventListener("keydown", (e) => {
        if (e.key !== "Escape") {
            return;
        }

        if (refs.confirmModal.style.display === "flex") {
            resolveConfirm(refs, false);
            return;
        }

        closePreviewModal(refs);
    });

    refs.result.addEventListener("toggle", (e) => {
        const target = e.target;
        if (!target || target.tagName !== "DETAILS" || !target.classList.contains("file-detail")) {
            return;
        }

        if (target.open) {
            state.currentExpandedFile = target.getAttribute("data-filename") || "";
            document.querySelectorAll(".file-detail[open]").forEach((details) => {
                if (details !== target) {
                    details.open = false;
                }
            });
        } else if (state.currentExpandedFile === (target.getAttribute("data-filename") || "")) {
            state.currentExpandedFile = null;
        }

        updateCurrentFileExportButton(refs);
    }, true);

    refs.sqlFile.addEventListener("change", (e) => {
        const file = e.target.files && e.target.files[0];
        if (!file) {
            refs.fileMeta.textContent = "";
            return;
        }
        refs.fileMeta.textContent = `已选择附件: ${file.name} (${file.size} bytes)`;
    });
}

function init() {
    applyPersistedSettings(refs);
    applyThemeFromControls();
    bindEvents();
    refreshBackendStatus();

    loadDesktopMeta().then((meta) => {
        if (!refs.appMeta) {
            return;
        }

        if (!meta) {
            refs.appMeta.textContent = "桌面信息: unavailable";
            return;
        }

        const appName = meta.appName || "SQLGuard";
        const appVersion = meta.appVersion || "unknown";
        const platform = meta.platform || "unknown";
        refs.appMeta.textContent = `桌面信息: ${appName} v${appVersion} (${platform})`;
    });

    if (refs.docLink) {
        refs.docLink.addEventListener("click", async (e) => {
            e.preventDefault();
            const result = await openExternalSafely(`${getApiBase()}/docs`);
            if (!result.ok) {
                renderError(refs, new Error(result.error || "无法打开外部链接"));
            }
        });
    }
}

init();
