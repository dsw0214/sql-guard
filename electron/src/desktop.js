function getDesktopBridge() {
    if (typeof window === "undefined") {
        return null;
    }

    const bridge = window.sqlGuardDesktop;
    if (!bridge || typeof bridge.getMeta !== "function" || typeof bridge.openExternal !== "function") {
        return null;
    }

    return bridge;
}

export async function loadDesktopMeta() {
    const bridge = getDesktopBridge();
    if (!bridge) {
        return null;
    }

    try {
        const meta = await bridge.getMeta();
        if (!meta || typeof meta !== "object") {
            return null;
        }
        return meta;
    } catch {
        return null;
    }
}

export async function openExternalSafely(url) {
    const bridge = getDesktopBridge();
    if (!bridge) {
        // Fallback: open in system browser via window.open (browser / dev context)
        window.open(url, "_blank", "noopener,noreferrer");
        return { ok: true };
    }

    try {
        const result = await bridge.openExternal(url);
        if (!result || typeof result !== "object") {
            return { ok: false, error: "Invalid response" };
        }
        return result;
    } catch (err) {
        return { ok: false, error: err && err.message ? err.message : "Failed to open external URL" };
    }
}
