import { SETTINGS_KEY, getClientId } from "./constants.js";
import { normalizeThemeColor, normalizeThemeMode } from "./theme.js";

export function getPersistedSettings() {
    try {
        const raw = localStorage.getItem(SETTINGS_KEY);
        if (!raw) {
            return {};
        }
        const parsed = JSON.parse(raw);
        return parsed && typeof parsed === "object" ? parsed : {};
    } catch (_) {
        return {};
    }
}

export function saveSettings(refs) {
    const payload = {
        highRiskOnly: refs.highRiskOnly.checked,
        reportTemplate: refs.reportTemplate.value,
        archiveDiagFilter: refs.archiveDiagFilter.value,
        themeMode: refs.themeMode.value,
        themeColor: refs.themeColor.value,
        serverUrl: refs.serverUrl.value.trim(),
        apiToken: refs.apiToken.value.trim(),
        clientId: getClientId(),
        aiProvider: refs.aiProvider.value,
        aiBaseUrl: refs.aiBaseUrl.value.trim(),
        aiModel: refs.aiModel.value.trim(),
        aiApiKey: refs.aiApiKey.value,
        aiHttpTimeout: String(refs.aiHttpTimeout.value || "").trim(),
        ollamaBaseUrl: refs.ollamaBaseUrl.value.trim(),
        ollamaModel: refs.ollamaModel.value.trim(),
        ollamaHttpTimeout: String(refs.ollamaHttpTimeout.value || "").trim(),
        previewScrollMode: refs.previewScrollMode.value,
        mode: refs.mode.value,
        dialect: refs.dialect.value || "generic",
    };
    try {
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(payload));
    } catch (_) {
        // Ignore persistence errors to avoid breaking core workflow.
    }
}

export function applyPersistedSettings(refs) {
    const settings = getPersistedSettings();

    if (typeof settings.highRiskOnly === "boolean") {
        refs.highRiskOnly.checked = settings.highRiskOnly;
    }

    if (settings.reportTemplate === "simple" || settings.reportTemplate === "detailed") {
        refs.reportTemplate.value = settings.reportTemplate;
    }

    if (settings.archiveDiagFilter === "all" || settings.archiveDiagFilter === "duplicates" || settings.archiveDiagFilter === "failed" || settings.archiveDiagFilter === "skipped" || settings.archiveDiagFilter === "none") {
        refs.archiveDiagFilter.value = settings.archiveDiagFilter;
    }

    refs.themeMode.value = normalizeThemeMode(settings.themeMode);
    refs.themeColor.value = normalizeThemeColor(settings.themeColor);

    if (typeof settings.serverUrl === "string" && settings.serverUrl.trim()) {
        refs.serverUrl.value = settings.serverUrl.trim();
    }

    if (typeof settings.apiToken === "string") {
        refs.apiToken.value = settings.apiToken.trim();
    }

    if (settings.aiProvider === "openai" || settings.aiProvider === "ollama") {
        refs.aiProvider.value = settings.aiProvider;
    }
    if (typeof settings.aiBaseUrl === "string") {
        refs.aiBaseUrl.value = settings.aiBaseUrl.trim();
    }
    if (typeof settings.aiModel === "string") {
        refs.aiModel.value = settings.aiModel.trim();
    }
    if (typeof settings.aiApiKey === "string") {
        refs.aiApiKey.value = settings.aiApiKey;
    }
    if (typeof settings.aiHttpTimeout === "string" || typeof settings.aiHttpTimeout === "number") {
        refs.aiHttpTimeout.value = String(settings.aiHttpTimeout).trim();
    }
    if (typeof settings.ollamaBaseUrl === "string") {
        refs.ollamaBaseUrl.value = settings.ollamaBaseUrl.trim();
    }
    if (typeof settings.ollamaModel === "string") {
        refs.ollamaModel.value = settings.ollamaModel.trim();
    }
    if (typeof settings.ollamaHttpTimeout === "string" || typeof settings.ollamaHttpTimeout === "number") {
        refs.ollamaHttpTimeout.value = String(settings.ollamaHttpTimeout).trim();
    }

    if (settings.previewScrollMode === "smooth" || settings.previewScrollMode === "instant") {
        refs.previewScrollMode.value = settings.previewScrollMode;
    }

    if (settings.mode === "rule" || settings.mode === "ai" || settings.mode === "hybrid") {
        refs.mode.value = settings.mode;
    }

    if (typeof settings.dialect === "string" && settings.dialect.trim()) {
        refs.dialect.value = settings.dialect;
    }
}

export function applyDefaultSettings(refs) {
    refs.highRiskOnly.checked = false;
    refs.reportTemplate.value = "detailed";
    refs.archiveDiagFilter.value = "all";
    refs.themeMode.value = "default";
    refs.themeColor.value = "#43e7ff";
    refs.serverUrl.value = "";
    refs.apiToken.value = "";
    getClientId();
    refs.aiProvider.value = "ollama";
    refs.aiBaseUrl.value = "https://api.openai.com/v1";
    refs.aiModel.value = "gpt-4o-mini";
    refs.aiApiKey.value = "";
    refs.aiHttpTimeout.value = "30000";
    refs.ollamaBaseUrl.value = "http://cn212001352.bilibili.local:11434";
    refs.ollamaModel.value = "qwen3.5:9b";
    refs.ollamaHttpTimeout.value = "30000";
    refs.previewScrollMode.value = "smooth";
    refs.mode.value = "hybrid";
    refs.dialect.value = "generic";
}

export function applyDefaultExportSettings(refs) {
    refs.highRiskOnly.checked = false;
    refs.reportTemplate.value = "detailed";
    refs.archiveDiagFilter.value = "all";
    refs.themeMode.value = "default";
    refs.themeColor.value = "#43e7ff";
    refs.previewScrollMode.value = "smooth";
}

export function clearSettings() {
    try {
        localStorage.removeItem(SETTINGS_KEY);
    } catch (_) {
        // Ignore persistence errors.
    }
}
