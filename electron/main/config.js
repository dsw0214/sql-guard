const path = require("path");
const { app } = require("electron");

const WINDOW_OPTIONS = {
  width: 1000,
  height: 700,
};

function getWebPreferences() {
  return {
    preload: path.join(__dirname, "..", "preload.js"),
    // Keep renderer secure by default.
    nodeIntegration: false,
    contextIsolation: true,
    sandbox: true,
    webSecurity: true,
  };
}

function shouldOpenDevTools() {
  const flag = process.env.ELECTRON_OPEN_DEVTOOLS;
  if (typeof flag === "string") {
    return flag !== "0" && flag.toLowerCase() !== "false";
  }

  // Production package defaults to closed DevTools.
  if (app.isPackaged || String(process.env.NODE_ENV || "").toLowerCase() === "production") {
    return false;
  }

  return true;
}

function shouldDisableHardwareAcceleration() {
  const flag = process.env.SQLGUARD_DISABLE_HW_ACCELERATION;
  if (typeof flag === "string") {
    return flag !== "0" && flag.toLowerCase() !== "false";
  }

  // macOS 上 Chromium/Electron 偶发出现 SharedImage/Invalid mailbox 日志，
  // 对当前这类非图形密集型工具，默认关闭硬件加速更稳妥。
  return process.platform === "darwin";
}

module.exports = {
  WINDOW_OPTIONS,
  getWebPreferences,
  shouldOpenDevTools,
  shouldDisableHardwareAcceleration,
};
