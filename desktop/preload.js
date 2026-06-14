const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("gkguardDesktop", {
  getAppInfo: () => ipcRenderer.invoke("gkguard:get-app-info"),
  checkForUpdates: () => ipcRenderer.invoke("gkguard:check-for-updates"),
  downloadUpdate: (url) => ipcRenderer.invoke("gkguard:download-update", url),
});