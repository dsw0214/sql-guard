import { SETTINGS_KEY } from "./constants.js";
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
