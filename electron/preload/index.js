const { contextBridge } = require("electron");

const { createDesktopApi } = require("./api.js");

function initPreload() {
  contextBridge.exposeInMainWorld("sqlGuardDesktop", createDesktopApi());
}

module.exports = {
  initPreload,
};
