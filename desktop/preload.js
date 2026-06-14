const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("gkguardDesktop", {
  getAppInfo: () => ipcRenderer.invoke("gkguard:get-app-info"),
  checkForUpdates: () => ipcRenderer.invoke("gkguard:check-for-updates"),
  downloadUpdate: () => ipcRenderer.invoke("gkguard:download-update"),
  installUpdate: () => ipcRenderer.invoke("gkguard:install-update"),
  onUpdateEvent: (callback) => {
    const listener = (_event, payload) => callback(payload);
    ipcRenderer.on("gkguard:update-event", listener);
    return () => ipcRenderer.off("gkguard:update-event", listener);
  },
  connectC1: (reason) => ipcRenderer.invoke("gkguard:connect-c1", reason),
  onSshConnectProgress: (callback) => {
    const listener = (_event, payload) => callback(payload);
    ipcRenderer.on("gkguard:ssh-connect-progress", listener);
    return () => ipcRenderer.off("gkguard:ssh-connect-progress", listener);
  },
  submitSshPassword: (password) => ipcRenderer.send("gkguard:ssh-password-submit", password),
  cancelSshPassword: () => ipcRenderer.send("gkguard:ssh-password-cancel"),
});