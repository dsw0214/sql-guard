const { app, BrowserWindow } = require("electron");

const { createMainWindow } = require("./window.js");
const { registerIpcHandlers } = require("./ipc.js");
const { shouldDisableHardwareAcceleration } = require("./config.js");

if (shouldDisableHardwareAcceleration()) {
  app.disableHardwareAcceleration();
}

function registerAppLifecycle() {
  app.whenReady().then(() => {
    registerIpcHandlers();
    createMainWindow();

    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        createMainWindow();
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
