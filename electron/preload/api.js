const { ipcRenderer } = require("electron");

function createDesktopApi() {
  return {
    getMeta() {
      return ipcRenderer.invoke("app:getMeta");
    },
    openExternal(url) {
      return ipcRenderer.invoke("app:openExternal", url);
    },
  };
}

module.exports = {
  createDesktopApi,
};
