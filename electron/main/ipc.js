const { ipcMain, shell, app } = require("electron");
const path = require("path");

const ALLOWED_EXTERNAL_PROTOCOLS = new Set(["http:", "https:", "mailto:"]);

function isSafeExternalUrl(rawUrl) {
  if (typeof rawUrl !== "string" || !rawUrl.trim()) {
    return false;
  }

  try {
    const parsed = new URL(rawUrl);
    return ALLOWED_EXTERNAL_PROTOCOLS.has(parsed.protocol);
  } catch {
    return false;
  }
}

function registerIpcHandlers() {
  ipcMain.handle("app:getMeta", () => {
    let buildDate = "";
    let buildRun = "";

    try {
      const pkg = require(path.join(app.getAppPath(), "package.json"));
      buildDate = typeof pkg.buildDate === "string" ? pkg.buildDate : "";
      buildRun = typeof pkg.buildRun === "string" ? pkg.buildRun : "";
    } catch {
      // Ignore package metadata read errors and return base app info.
    }

    return {
      appName: app.getName(),
      appVersion: app.getVersion(),
      platform: process.platform,
      buildDate,
      buildRun,
    };
  });

  ipcMain.handle("app:openExternal", async (_event, rawUrl) => {
    if (!isSafeExternalUrl(rawUrl)) {
      return { ok: false, error: "Unsupported or invalid URL" };
    }

    await shell.openExternal(rawUrl);
    return { ok: true };
  });
}

module.exports = {
  registerIpcHandlers,
};
