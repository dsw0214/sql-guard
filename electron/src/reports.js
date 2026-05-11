export function isHighRisk(level) {
    return level === "P0" || level === "P1";
}

export function filterIssues(issues, highRiskOnly) {
    const list = Array.isArray(issues) ? issues : [];
    if (!highRiskOnly) {
        return list;
    }
    return list.filter((item) => isHighRisk(item.level));
}

export function toMarkdownReport(data, options) {
    const { highRiskOnly, template } = options;
    const topIssues = filterIssues(data.issues, highRiskOnly);
    const lines = [];

    lines.push("# SQLGuard 检测报告");
    lines.push("");
    lines.push(`- 模式: ${data.mode || ""}`);
    lines.push(`- 风险分: ${data.score ?? 0}`);
    lines.push(`- 问题数: ${data.stats?.total_issue_count ?? 0}`);
    lines.push(`- 导出模板: ${template === "simple" ? "简版" : "详细版"}`);
    lines.push(`- 高风险筛选: ${highRiskOnly ? "开启" : "关闭"}`);

    if (data.attachment) {
        lines.push(`- 附件: ${data.attachment.filename} (${data.attachment.size} bytes)`);
    }

    lines.push("");
    lines.push("## 汇总问题");
    lines.push("");

    if (!topIssues.length) {
        lines.push("- 未发现风险");
    } else {
        topIssues.forEach((item) => {
            lines.push(`- [${item.level}] (${item.source || "rule"}) ${item.message}${item.hint ? ` | 建议: ${item.hint}` : ""}`);
        });
    }

    if (template === "detailed" && data.attachment?.is_archive && Array.isArray(data.attachment.files)) {
        lines.push("");
        lines.push("## 分文件详情");
        lines.push("");

        data.attachment.files.forEach((file) => {
            lines.push(`### ${file.filename}`);
            lines.push(`- 风险分: ${file.score ?? 0}`);
            lines.push(`- 问题数: ${file.stats?.total_issue_count ?? 0}`);

            const fileIssues = filterIssues(file.issues, highRiskOnly);
            if (!fileIssues.length) {
                lines.push("- 未发现风险");
            } else {
                fileIssues.forEach((item) => {
                    lines.push(`- [${item.level}] (${item.source || "rule"}) ${item.message}${item.hint ? ` | 建议: ${item.hint}` : ""}`);
                });
            }
            lines.push("");
        });
    }

    return lines.join("\n");
}

export function buildJsonPayload(data, options) {
    const { highRiskOnly, template } = options;
    const topIssues = filterIssues(data.issues, highRiskOnly);

    if (template === "simple") {
        return {
            mode: data.mode,
            score: data.score,
            total_issue_count: data.stats?.total_issue_count ?? 0,
            exported_issue_count: topIssues.length,
            high_risk_only: highRiskOnly,
            issues: topIssues,
            attachment: data.attachment
                ? {
                    filename: data.attachment.filename,
                    size: data.attachment.size,
                    is_archive: !!data.attachment.is_archive,
                }
                : null,
        };
    }

    return {
        ...data,
        exported_issue_count: topIssues.length,
        high_risk_only: highRiskOnly,
        issues: topIssues,
    };
}

export function toMarkdownSubReport(file, mode, highRiskOnly) {
    const fileIssues = filterIssues(file.issues, highRiskOnly);
    const lines = [];

    lines.push(`# SQLGuard 子报告 - ${file.filename}`);
    lines.push("");
    lines.push(`- 主报告模式: ${mode || ""}`);
    lines.push(`- 文件风险分: ${file.score ?? 0}`);
    lines.push(`- 文件问题数: ${file.stats?.total_issue_count ?? 0}`);
    lines.push(`- 高风险筛选: ${highRiskOnly ? "开启" : "关闭"}`);
    lines.push("");
    lines.push("## 问题列表");
    lines.push("");

    if (!fileIssues.length) {
        lines.push("- 未发现风险");
    } else {
        fileIssues.forEach((item) => {
            lines.push(`- [${item.level}] (${item.source || "rule"}) ${item.message}${item.hint ? ` | 建议: ${item.hint}` : ""}`);
        });
    }

    return lines.join("\n");
}

export function buildJsonSubReport(file, mode, highRiskOnly) {
    return {
        filename: file.filename,
        size: file.size,
        score: file.score,
        stats: file.stats || {},
        high_risk_only: highRiskOnly,
        mode: mode || "",
        issues: filterIssues(file.issues, highRiskOnly),
    };
}
