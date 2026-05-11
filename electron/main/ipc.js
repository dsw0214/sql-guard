const { ipcMain, shell, app } = require("electron");

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
    return {
      appName: app.getName(),
      appVersion: app.getVersion(),
      platform: process.platform,
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
