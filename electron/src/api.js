import { getApiBase } from "./constants.js";

export async function requestWithTimeout(url, options, timeoutMs = 200000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
        const res = await fetch(url, {
            ...options,
            signal: controller.signal,
        });

        if (!res.ok) {
            let detail = "";
            try {
                const errBody = await res.json();
                detail = errBody.detail ? `: ${errBody.detail}` : "";
            } catch (_) {
                detail = "";
            }
            throw new Error(`请求失败: ${res.status}${detail}`);
        }

        return await res.json();
    } finally {
        clearTimeout(timer);
    }
}

export async function reviewSqlRequest({ sql, mode, dialect, maxIssues }) {
    return requestWithTimeout(`${getApiBase()}/review`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            sql,
            mode,
            dialect,
            max_issues: maxIssues,
        }),
    });
}

export async function reviewSqlFileRequest({ file, mode, dialect, maxIssues }) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("mode", mode);
    formData.append("dialect", dialect);
    formData.append("max_issues", String(maxIssues));

    return requestWithTimeout(`${getApiBase()}/review/upload`, {
        method: "POST",
        body: formData,
    });
}

export async function checkBackendStatus() {
    try {
        const data = await requestWithTimeout(`${getApiBase()}/`, {
            method: "GET",
        }, 4000);

        return {
            ok: true,
            message: data && data.message ? String(data.message) : "ok",
        };
    } catch (err) {
        return {
            ok: false,
            message: err && err.message ? err.message : "backend unavailable",
        };
    }
}
