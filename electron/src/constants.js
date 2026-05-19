export const DEFAULT_API_BASE = "http://127.0.0.1:8000";
export const SETTINGS_KEY = "sqlguard.ui.settings.v1";

export function getApiBase() {
    try {
        const raw = localStorage.getItem(SETTINGS_KEY);
        if (raw) {
            const parsed = JSON.parse(raw);
            if (parsed && typeof parsed.serverUrl === "string" && parsed.serverUrl.trim()) {
                return parsed.serverUrl.trim().replace(/\/$/, "");
            }
        }
    } catch (_) {
        // Fall through to default.
    }
    return DEFAULT_API_BASE;
}

export function getApiToken() {
    try {
        const raw = localStorage.getItem(SETTINGS_KEY);
        if (raw) {
            const parsed = JSON.parse(raw);
            if (parsed && typeof parsed.apiToken === "string" && parsed.apiToken.trim()) {
                return parsed.apiToken.trim();
            }
        }
    } catch (_) {
        // Fall through to empty token.
    }
    return "";
}
