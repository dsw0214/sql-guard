const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("sqlGuardDesktop", {
	getMeta() {
		return ipcRenderer.invoke("app:getMeta");
	},
	openExternal(url) {
		return ipcRenderer.invoke("app:openExternal", url);
	},
});
