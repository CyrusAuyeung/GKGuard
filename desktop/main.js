const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const https = require("https");
const http = require("http");
const path = require("path");

const PORT = Number(process.env.GKGUARD_PORT || 8000);
const HOST = "127.0.0.1";
const BASE_URL = `http://${HOST}:${PORT}`;
const HEALTH_URL = `${BASE_URL}/health`;
const C1_STATUS_URL = `${BASE_URL}/c1/status`;
const DEMO_URL = `${BASE_URL}/demo?desktop=1`;
const START_TIMEOUT_MS = 18000;
const POLL_INTERVAL_MS = 450;
const C1_CONNECT_TIMEOUT_MS = Number(process.env.C1_CONNECT_TIMEOUT_MS || 45000);
const LATEST_RELEASE_API = "https://api.github.com/repos/CyrusAuyeung/GKGuard/releases/latest";
const RELEASES_URL = "https://github.com/CyrusAuyeung/GKGuard/releases/latest";
const DEFAULT_C1_DIRECT_URL = "http://10.4.167.122:8000";
const DEFAULT_C1_TUNNEL_URL = "http://127.0.0.1:18000";
const DEFAULT_C1_SSH_TUNNEL = {
  enabled: true,
  host: "10.4.167.122",
  user: "speng",
  localPort: 18000,
  remoteHost: "127.0.0.1",
  remotePort: 8000,
};

let backendProcess = null;
let mainWindow = null;

function compareVersions(left, right) {
  const leftParts = String(left || "").replace(/^v/i, "").split(/[.-]/).map((part) => Number.parseInt(part, 10) || 0);
  const rightParts = String(right || "").replace(/^v/i, "").split(/[.-]/).map((part) => Number.parseInt(part, 10) || 0);
  const length = Math.max(leftParts.length, rightParts.length, 3);
  for (let index = 0; index < length; index += 1) {
    const diff = (leftParts[index] || 0) - (rightParts[index] || 0);
    if (diff !== 0) return diff;
  }
  return 0;
}

function getHttpsJson(url, timeoutMs = 8000) {
  return new Promise((resolve, reject) => {
    const request = https.get(url, {
      headers: {
        Accept: "application/vnd.github+json",
        "User-Agent": `GKGuard/${app.getVersion()}`,
      },
    }, (response) => {
      let body = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => {
        body += chunk;
      });
      response.on("end", () => {
        if (response.statusCode !== 200) {
          reject(new Error(`GitHub Release API returned HTTP ${response.statusCode}`));
          return;
        }
        try {
          resolve(JSON.parse(body));
        } catch (error) {
          reject(error);
        }
      });
    });

    request.on("error", reject);
    request.setTimeout(timeoutMs, () => {
      request.destroy(new Error("Update check timed out"));
    });
  });
}

function isTrustedReleaseUrl(url) {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" && parsed.hostname === "github.com" && parsed.pathname.startsWith("/CyrusAuyeung/GKGuard/releases/");
  } catch {
    return false;
  }
}

async function checkForUpdates() {
  const release = await getHttpsJson(LATEST_RELEASE_API);
  const currentVersion = app.getVersion();
  const latestVersion = String(release.tag_name || "").replace(/^v/i, "");
  const installer = (release.assets || []).find((asset) => /^GKGuard-Setup-.*\.exe$/i.test(asset.name));
  return {
    currentVersion,
    latestVersion,
    updateAvailable: compareVersions(latestVersion, currentVersion) > 0,
    releaseUrl: release.html_url || RELEASES_URL,
    downloadUrl: installer?.browser_download_url || release.html_url || RELEASES_URL,
    assetName: installer?.name || "",
    publishedAt: release.published_at || "",
  };
}

function getBackendRoot() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "backend");
  }
  return path.join(__dirname, "..", "backend");
}

function getBundledBackendExecutable() {
  return path.join(process.resourcesPath, "backend-bin", "gkguard-backend.exe");
}

function getPythonCandidates() {
  return [process.env.GKGUARD_PYTHON, "python", "py", "python3"].filter(Boolean);
}

function getC1ConfigPath() {
  return process.env.C1_CONFIG_PATH || path.join(app.getPath("userData"), "c1-connection.json");
}

function getBackendEnv() {
  return {
    ...process.env,
    PYTHONUNBUFFERED: "1",
    C1_CONFIG_PATH: getC1ConfigPath(),
    C1_CANDIDATE_URLS: process.env.C1_CANDIDATE_URLS || `${DEFAULT_C1_DIRECT_URL},${DEFAULT_C1_TUNNEL_URL}`,
  };
}

function readC1ConnectionConfig() {
  try {
    const configPath = getC1ConfigPath();
    if (!fs.existsSync(configPath)) {
      return {};
    }
    return JSON.parse(fs.readFileSync(configPath, "utf8"));
  } catch {
    return {};
  }
}

function toPort(value, fallback) {
  const port = Number(value || fallback);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    return fallback;
  }
  return port;
}

function isSafeSshToken(value) {
  return typeof value === "string" && /^[A-Za-z0-9._-]+$/.test(value);
}

function getSshTunnelConfig() {
  const config = readC1ConnectionConfig();
  const tunnel = { ...DEFAULT_C1_SSH_TUNNEL, ...(config.sshTunnel || {}) };
  const enabledValue = process.env.C1_SSH_TUNNEL || tunnel.enabled;
  const enabled = enabledValue === true || String(enabledValue).toLowerCase() === "true" || String(enabledValue) === "1";
  if (!enabled) {
    return null;
  }

  const host = process.env.C1_SSH_HOST || tunnel.host;
  const user = process.env.C1_SSH_USER || tunnel.user;
  const remoteHost = process.env.C1_SSH_REMOTE_HOST || tunnel.remoteHost || "127.0.0.1";
  const localPort = toPort(process.env.C1_SSH_LOCAL_PORT || tunnel.localPort, 18000);
  const remotePort = toPort(process.env.C1_SSH_REMOTE_PORT || tunnel.remotePort, 8000);

  if (!isSafeSshToken(host) || !isSafeSshToken(user) || !isSafeSshToken(remoteHost)) {
    return null;
  }

  return { host, user, remoteHost, localPort, remotePort };
}

function getJson(url, timeoutMs = 2500) {
  return new Promise((resolve, reject) => {
    const request = http.get(url, (response) => {
      let body = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => {
        body += chunk;
      });
      response.on("end", () => {
        if (response.statusCode !== 200) {
          reject(new Error(`HTTP ${response.statusCode}`));
          return;
        }
        try {
          resolve(JSON.parse(body));
        } catch (error) {
          reject(error);
        }
      });
    });

    request.on("error", reject);
    request.setTimeout(timeoutMs, () => {
      request.destroy(new Error("Request timed out"));
    });
  });
}

function isC1Connected(status) {
  return Boolean(status && (status.selectedBaseUrl || (status.reachable && status.healthOk)));
}

async function waitForC1Connection(timeoutMs = C1_CONNECT_TIMEOUT_MS) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    try {
      const status = await getJson(C1_STATUS_URL, 2500);
      if (isC1Connected(status)) {
        return true;
      }
    } catch {
      // Keep polling while the backend or tunnel is still settling.
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  return false;
}

function openSshTunnelTerminal(tunnel) {
  const forward = `${tunnel.localPort}:${tunnel.remoteHost}:${tunnel.remotePort}`;
  const target = `${tunnel.user}@${tunnel.host}`;
  const command = `ssh -N -L ${forward} ${target}`;

  if (process.platform === "win32") {
    const child = spawn("cmd.exe", ["/c", "start", "GKGuard C1 Tunnel", "powershell.exe", "-NoExit", "-Command", command], {
      detached: true,
      stdio: "ignore",
      windowsHide: false,
    });
    child.unref();
    return;
  }

  const child = spawn("ssh", ["-N", "-L", forward, target], {
    detached: true,
    stdio: "ignore",
  });
  child.unref();
}

async function maybePromptForC1Tunnel() {
  const tunnel = getSshTunnelConfig();
  if (!tunnel) {
    return false;
  }

  try {
    const status = await getJson(C1_STATUS_URL, 2500);
    if (isC1Connected(status)) {
      return true;
    }
  } catch {
    return false;
  }

  const result = await dialog.showMessageBox(mainWindow, {
    type: "question",
    title: "连接 C1 服务器",
    message: "未检测到 C1 服务，是否现在打开 SSH 登录窗口？",
    detail: `GKGuard 将打开一个 PowerShell 窗口并执行 SSH 隧道：\nssh -N -L ${tunnel.localPort}:${tunnel.remoteHost}:${tunnel.remotePort} ${tunnel.user}@${tunnel.host}\n\n请在该窗口输入服务器密码。GKGuard 不会保存密码。`,
    buttons: ["输入密码连接 C1", "继续离线演示"],
    defaultId: 0,
    cancelId: 1,
  });

  if (result.response !== 0) {
    return false;
  }

  openSshTunnelTerminal(tunnel);
  const connected = await waitForC1Connection();
  if (!connected) {
    await dialog.showMessageBox(mainWindow, {
      type: "info",
      title: "C1 暂未连接",
      message: "尚未检测到 C1 服务",
      detail: "可以继续使用离线 mock 演示。若刚刚输入密码，请确认 SSH 窗口没有报错，或稍后在页面中重新上传照片。",
    });
  }
  return connected;
}

function waitForHealthCheck(timeoutMs = START_TIMEOUT_MS) {
  const startedAt = Date.now();
  return new Promise((resolve, reject) => {
    const check = () => {
      const request = http.get(HEALTH_URL, (response) => {
        response.resume();
        if (response.statusCode === 200) {
          resolve();
          return;
        }
        retry();
      });

      request.on("error", retry);
      request.setTimeout(2000, () => {
        request.destroy();
        retry();
      });
    };

    const retry = () => {
      if (Date.now() - startedAt >= timeoutMs) {
        reject(new Error(`后端服务在 ${timeoutMs / 1000} 秒内未就绪。`));
        return;
      }
      setTimeout(check, POLL_INTERVAL_MS);
    };

    check();
  });
}

function spawnBackendWith(command) {
  const backendRoot = getBackendRoot();
  const args = [
    "-m",
    "uvicorn",
    "app.main:app",
    "--app-dir",
    backendRoot,
    "--host",
    HOST,
    "--port",
    String(PORT),
  ];

  return spawn(command, args, {
    cwd: backendRoot,
    windowsHide: true,
    env: getBackendEnv(),
  });
}

function spawnBundledBackend() {
  return spawn(getBundledBackendExecutable(), [], {
    cwd: path.dirname(getBundledBackendExecutable()),
    windowsHide: true,
    env: getBackendEnv(),
  });
}

async function startBackend() {
  if (app.isPackaged) {
    backendProcess = spawnBundledBackend();
    const startupError = await new Promise((resolve) => {
      const timer = setTimeout(() => resolve(null), 900);
      backendProcess.once("error", (error) => {
        clearTimeout(timer);
        resolve(error);
      });
      backendProcess.once("exit", (code) => {
        clearTimeout(timer);
        resolve(new Error(`内置后端启动失败，退出码 ${code ?? "unknown"}`));
      });
    });

    if (startupError) {
      backendProcess = null;
      throw startupError;
    }

    return "bundled-backend";
  }

  const pythonCandidates = getPythonCandidates();
  let lastError = null;

  for (const command of pythonCandidates) {
    backendProcess = spawnBackendWith(command);

    const startupError = await new Promise((resolve) => {
      const timer = setTimeout(() => resolve(null), 900);
      backendProcess.once("error", (error) => {
        clearTimeout(timer);
        resolve(error);
      });
      backendProcess.once("exit", (code) => {
        clearTimeout(timer);
        resolve(new Error(`${command} 启动失败，退出码 ${code ?? "unknown"}`));
      });
    });

    if (!startupError) {
      return command;
    }

    lastError = startupError;
    backendProcess = null;
  }

  throw lastError || new Error("未找到可用的 Python 命令。请安装 Python，并执行 pip install -r backend/requirements.txt。");
}

async function ensureBackend() {
  try {
    await waitForHealthCheck(1200);
    return "existing";
  } catch {
    const command = await startBackend();
    await waitForHealthCheck();
    return command;
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1380,
    height: 860,
    minWidth: 1180,
    minHeight: 720,
    backgroundColor: "#f4f7fb",
    title: "GKGuard",
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, "preload.js"),
      sandbox: true,
    },
  });

  mainWindow.webContents.session.on("will-download", (_event, item) => {
    if (!/^GKGuard-Setup-.*\.exe$/i.test(item.getFilename())) {
      return;
    }
    item.once("done", async (_doneEvent, state) => {
      if (state !== "completed") {
        await dialog.showMessageBox(mainWindow, {
          type: "warning",
          title: "下载未完成",
          message: "新版安装包未完成下载",
          detail: "请检查网络后在 GKGuard 中重新点击检查更新。",
        });
        return;
      }
      const filePath = item.getSavePath();
      const result = await dialog.showMessageBox(mainWindow, {
        type: "info",
        title: "新版已下载",
        message: "GKGuard 新版安装包已下载完成",
        detail: filePath,
        buttons: ["打开所在文件夹", "稍后安装"],
        defaultId: 0,
        cancelId: 1,
      });
      if (result.response === 0) {
        shell.showItemInFolder(filePath);
      }
    });
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.loadFile(path.join(__dirname, "loading.html"));
}

ipcMain.handle("gkguard:get-app-info", () => ({
  version: app.getVersion(),
  isPackaged: app.isPackaged,
  platform: process.platform,
}));

ipcMain.handle("gkguard:check-for-updates", () => checkForUpdates());

ipcMain.handle("gkguard:download-update", (_event, url) => {
  const targetUrl = isTrustedReleaseUrl(url) ? url : RELEASES_URL;
  if (!mainWindow) {
    shell.openExternal(targetUrl);
    return { started: false, fallbackUrl: targetUrl };
  }
  mainWindow.webContents.downloadURL(targetUrl);
  return { started: true };
});

async function boot() {
  createWindow();
  try {
    await ensureBackend();
    await maybePromptForC1Tunnel();
    await mainWindow.loadURL(DEMO_URL);
    if (process.argv.includes("--devtools")) {
      mainWindow.webContents.openDevTools({ mode: "detach" });
    }
  } catch (error) {
    await dialog.showMessageBox(mainWindow, {
      type: "error",
      title: "GKGuard 启动失败",
      message: "无法启动本地后端服务",
      detail: app.isPackaged
        ? `${error.message}\n\n安装包内置后端未能启动，请重新下载最新 Release。`
        : `${error.message}\n\n请先在 backend 目录执行：python -m pip install -r requirements.txt`,
    });
    app.quit();
  }
}

function stopBackend() {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
  backendProcess = null;
}

app.whenReady().then(boot);

app.on("window-all-closed", () => {
  stopBackend();
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    boot();
  }
});

app.on("before-quit", stopBackend);