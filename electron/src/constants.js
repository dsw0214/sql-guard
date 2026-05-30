export const DEFAULT_API_BASE = "http://127.0.0.1:8000";
export const SETTINGS_KEY = "sqlguard.ui.settings.v1";

function ensureClientId(settings) {
    if (settings && typeof settings.clientId === "string" && settings.clientId.trim()) {
        return settings.clientId.trim();
    }

    let clientId = "";
    try {
        clientId = typeof crypto !== "undefined" && crypto.randomUUID
            ? crypto.randomUUID()
            : `client-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    } catch (_) {
        clientId = `client-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    }

    try {
        const next = { ...(settings || {}), clientId };
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(next));
    } catch (_) {
        // Ignore persistence errors.
    }

    return clientId;
}

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

export function getClientId() {
    try {
        const raw = localStorage.getItem(SETTINGS_KEY);
        const parsed = raw ? JSON.parse(raw) : {};
        return ensureClientId(parsed && typeof parsed === "object" ? parsed : {});
    } catch (_) {
        return ensureClientId({});
    }
}
