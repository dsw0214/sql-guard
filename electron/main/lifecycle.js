const { app, BrowserWindow } = require("electron");

const { createMainWindow } = require("./window.js");
const { registerApplicationMenu } = require("./menu.js");
const { registerIpcHandlers } = require("./ipc.js");
const { shouldDisableHardwareAcceleration } = require("./config.js");

const APP_DISPLAY_NAME = "sql-guard";

if (shouldDisableHardwareAcceleration()) {
  // Some Chromium GPU mailbox errors still appear on macOS unless the
  // related command-line switches are disabled before app ready.
  app.commandLine.appendSwitch("disable-gpu");
  app.commandLine.appendSwitch("disable-gpu-compositing");
  app.disableHardwareAcceleration();
}

function registerAppLifecycle() {
  app.whenReady().then(() => {
    app.setName(APP_DISPLAY_NAME);
    registerIpcHandlers();
    const mainWindow = createMainWindow();
    registerApplicationMenu(mainWindow);

    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        const win = createMainWindow();
        registerApplicationMenu(win);
      }
    });
  });

  app.on("window-all-closed", () => {
    if (process.platform !== "darwin") {
      app.quit();
    }
  });
}

module.exports = {
  registerAppLifecycle,
};
