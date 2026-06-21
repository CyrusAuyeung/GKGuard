const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const https = require("https");
const http = require("http");
const net = require("net");
const path = require("path");
const { autoUpdater } = require("electron-updater");
const { Client: SshClient } = require("ssh2");

const DEFAULT_PORT = Number(process.env.GKGUARD_PORT || 8000);
const HOST = "127.0.0.1";
const STATIC_ASSET_VERSION = "v0.1.34-ui";
const START_TIMEOUT_MS = 18000;
const POLL_INTERVAL_MS = 450;
const C1_CONNECT_TIMEOUT_MS = Number(process.env.C1_CONNECT_TIMEOUT_MS || 18000);
const LATEST_RELEASE_API = "https://api.github.com/repos/CyrusAuyeung/GKGuard/releases/latest";
const RELEASES_URL = "https://github.com/CyrusAuyeung/GKGuard/releases/latest";
const DEFAULT_C1_DIRECT_URL = "http://10.4.167.122:8000";
const DEFAULT_C1_TUNNEL_URL = "http://127.0.0.1:18000";
const APP_ICON_PATH = getAppIconPath();
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
let cachedUpdateInfo = null;
let cachedManualUpdateAsset = null;
let updateReadyToInstall = false;
let sshClient = null;
let sshForwardServer = null;
let activeBackendPort = DEFAULT_PORT;

autoUpdater.autoDownload = false;
autoUpdater.autoInstallOnAppQuit = false;

function sendUpdateEvent(payload) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("gkguard:update-event", payload);
  }
}

autoUpdater.on("download-progress", (progress) => {
  sendUpdateEvent({ type: "download-progress", percent: Math.round(progress.percent || 0) });
});

autoUpdater.on("update-downloaded", (info) => {
  cachedUpdateInfo = info || cachedUpdateInfo;
  updateReadyToInstall = true;
  sendUpdateEvent({ type: "update-downloaded", version: info?.version || cachedUpdateInfo?.version || "" });
});

autoUpdater.on("error", (error) => {
  sendUpdateEvent({ type: "error", message: error.message });
});

function getAppIconPath() {
  const iconsRoot = path.join(__dirname, "assets", "icons");
  if (process.platform === "win32") {
    return path.join(iconsRoot, "app-mark.ico");
  }
  return path.join(iconsRoot, "app-mark.png");
}

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

function getDesktopPlatformName() {
  if (process.platform === "win32") return "windows";
  if (process.platform === "darwin") return "macos";
  if (process.platform === "linux") return "linux";
  return process.platform;
}

function shouldUseEmbeddedUpdater() {
  return app.isPackaged && process.platform === "win32";
}

function getBackendExecutableName() {
  return process.platform === "win32" ? "gkguard-backend.exe" : "gkguard-backend";
}

function getReleaseAssetMatchers() {
  if (process.platform === "win32") {
    return [
      /^GKGuard-Setup-.*\.exe$/i,
      /^GKGuard-Windows-.*\.exe$/i,
    ];
  }
  if (process.platform === "darwin") {
    return [
      /^GKGuard-macOS-.*\.dmg$/i,
      /^GKGuard-macOS-.*\.zip$/i,
      /^GKGuard-.*(?:mac|macos|darwin).*\.(?:dmg|zip)$/i,
    ];
  }
  if (process.platform === "linux") {
    return [
      /^GKGuard-Linux-.*\.AppImage$/i,
      /^GKGuard-Linux-.*\.deb$/i,
      /^GKGuard-.*linux.*\.(?:AppImage|deb|rpm|tar\.gz)$/i,
    ];
  }
  return [/^GKGuard-.*$/i];
}

function getPreferredReleaseAsset(release) {
  const assets = release?.assets || [];
  for (const matcher of getReleaseAssetMatchers()) {
    const asset = assets.find((candidate) => matcher.test(candidate.name || ""));
    if (asset) {
      return asset;
    }
  }
  return null;
}

function isPlatformInstallerFilename(filename) {
  return getReleaseAssetMatchers().some((matcher) => matcher.test(filename || ""));
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

function getBaseUrl(port = activeBackendPort) {
  return `http://${HOST}:${port}`;
}

function getHealthUrl(port = activeBackendPort) {
  return `${getBaseUrl(port)}/health`;
}

function getC1StatusUrl(port = activeBackendPort) {
  return `${getBaseUrl(port)}/c1/status`;
}

function getDemoUrl(port = activeBackendPort) {
  return `${getBaseUrl(port)}/demo?desktop=1&asset=${encodeURIComponent(STATIC_ASSET_VERSION)}`;
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
  if (shouldUseEmbeddedUpdater()) {
    try {
      const update = await autoUpdater.checkForUpdates();
      cachedUpdateInfo = update?.updateInfo || null;
      cachedManualUpdateAsset = null;
      const latestVersion = cachedUpdateInfo?.version || app.getVersion();
      return {
        currentVersion: app.getVersion(),
        latestVersion,
        updateAvailable: compareVersions(latestVersion, app.getVersion()) > 0,
        releaseUrl: cachedUpdateInfo?.releaseUrl || RELEASES_URL,
        downloadUrl: "embedded://auto-updater",
        assetName: cachedUpdateInfo?.files?.[0]?.url || "",
        publishedAt: cachedUpdateInfo?.releaseDate || "",
        platform: getDesktopPlatformName(),
        embedded: true,
        downloaded: updateReadyToInstall,
      };
    } catch (error) {
      const manualUpdate = await checkForManualReleaseUpdate();
      return {
        ...manualUpdate,
        embedded: false,
        fallbackReason: error.message,
      };
    }
  }

  return checkForManualReleaseUpdate();
}

async function checkForManualReleaseUpdate() {
  const release = await getHttpsJson(LATEST_RELEASE_API);
  const currentVersion = app.getVersion();
  const latestVersion = String(release.tag_name || "").replace(/^v/i, "");
  const installer = getPreferredReleaseAsset(release);
  cachedManualUpdateAsset = installer || null;
  return {
    currentVersion,
    latestVersion,
    updateAvailable: compareVersions(latestVersion, currentVersion) > 0,
    releaseUrl: release.html_url || RELEASES_URL,
    downloadUrl: installer?.browser_download_url || release.html_url || RELEASES_URL,
    assetName: installer?.name || "",
    publishedAt: release.published_at || "",
    platform: getDesktopPlatformName(),
    embedded: false,
    downloaded: false,
  };
}

async function downloadUpdate() {
  if (!shouldUseEmbeddedUpdater() || cachedManualUpdateAsset) {
    const fallbackUrl = cachedManualUpdateAsset?.browser_download_url || RELEASES_URL;
    shell.openExternal(fallbackUrl);
    return { started: true, embedded: false, fallbackUrl };
  }
  if (updateReadyToInstall) {
    return { started: false, embedded: true, downloaded: true };
  }
  await autoUpdater.downloadUpdate();
  return { started: true, embedded: true };
}

function installDownloadedUpdate() {
  if (!app.isPackaged || !updateReadyToInstall) {
    return { started: false };
  }
  autoUpdater.quitAndInstall(false, true);
  return { started: true };
}

function getBackendRoot() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "backend");
  }
  return path.join(__dirname, "..", "backend");
}

function getBundledBackendExecutable() {
  return path.join(process.resourcesPath, "backend-bin", getBackendExecutableName());
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
    GKGUARD_PORT: String(activeBackendPort),
    C1_CONFIG_PATH: getC1ConfigPath(),
    C1_CANDIDATE_URLS: process.env.C1_CANDIDATE_URLS || `${DEFAULT_C1_TUNNEL_URL},${DEFAULT_C1_DIRECT_URL}`,
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

function getTunnelBaseUrl(tunnel) {
  return `http://127.0.0.1:${tunnel.localPort}`;
}

function swallowTunnelNetworkError(error) {
  const code = error?.code || "";
  return ["ECONNRESET", "EPIPE", "ETIMEDOUT", "ECONNABORTED"].includes(code)
    || /read ECONNRESET|socket hang up/i.test(error?.message || "");
}

function closeTunnelStream(stream) {
  if (!stream || stream.destroyed) {
    return;
  }
  stream.destroy();
}

function isC1TunnelConnected(status, tunnel) {
  return Boolean(tunnel && status?.selectedBaseUrl === getTunnelBaseUrl(tunnel));
}

async function waitForC1Connection(timeoutMs = C1_CONNECT_TIMEOUT_MS, options = {}) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    try {
      const status = await getJson(getC1StatusUrl(), 2500);
      const connected = options.requireTunnel ? isC1TunnelConnected(status, options.tunnel) : isC1Connected(status);
      if (connected) {
        return true;
      }
    } catch {
      // Keep polling while the backend or tunnel is still settling.
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  return false;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function probeC1Endpoint(baseUrl, timeoutMs = 1200) {
  const [openapi, health] = await Promise.allSettled([
    getJson(`${baseUrl}/openapi.json`, timeoutMs),
    getJson(`${baseUrl}/health`, timeoutMs),
  ]);
  return {
    reachable: openapi.status === "fulfilled" || health.status === "fulfilled",
    openapiOk: openapi.status === "fulfilled",
    healthOk: health.status === "fulfilled",
    openapiError: openapi.status === "rejected" ? openapi.reason?.message : "",
    healthError: health.status === "rejected" ? health.reason?.message : "",
  };
}

async function waitForC1TunnelReady(tunnel, onProgress, timeoutMs = C1_CONNECT_TIMEOUT_MS) {
  const startedAt = Date.now();
  const tunnelBaseUrl = getTunnelBaseUrl(tunnel);
  while (Date.now() - startedAt < timeoutMs) {
    const elapsed = Date.now() - startedAt;
    const percent = Math.min(92, 58 + Math.round((elapsed / timeoutMs) * 34));
    onProgress?.({ percent, message: "正在确认 C1 服务响应..." });

    const endpointStatus = await probeC1Endpoint(tunnelBaseUrl, 1200);
    if (endpointStatus.reachable) {
      return { connected: true, verified: endpointStatus.healthOk, status: endpointStatus };
    }

    await delay(450);
  }

  return { connected: false, verified: false };
}

function stopSshTunnel() {
  if (sshForwardServer) {
    sshForwardServer.close();
    sshForwardServer = null;
  }
  if (sshClient) {
    sshClient.end();
    sshClient = null;
  }
}

function startEmbeddedSshTunnel(tunnel, password, onProgress) {
  const forward = `${tunnel.localPort}:${tunnel.remoteHost}:${tunnel.remotePort}`;
  const target = `${tunnel.user}@${tunnel.host}`;

  return new Promise((resolve, reject) => {
    stopSshTunnel();
    onProgress?.({ percent: 18, message: "正在连接 SSH 服务器..." });
    const client = new SshClient();
    let server = null;
    let settled = false;

    const fail = (error) => {
      if (settled) return;
      settled = true;
      if (server) {
        server.close();
      }
      client.end();
      stopSshTunnel();
      reject(error);
    };

    client.on("ready", () => {
      onProgress?.({ percent: 42, message: "SSH 已认证，正在建立本机隧道..." });
      server = net.createServer((socket) => {
        socket.on("error", (error) => {
          if (!swallowTunnelNetworkError(error)) {
            console.warn(`C1 tunnel socket error: ${error.message}`);
          }
        });

        client.forwardOut("127.0.0.1", 0, tunnel.remoteHost, tunnel.remotePort, (error, stream) => {
          if (error) {
            closeTunnelStream(socket);
            return;
          }

          stream.on("error", (streamError) => {
            if (!swallowTunnelNetworkError(streamError)) {
              console.warn(`C1 tunnel stream error: ${streamError.message}`);
            }
            closeTunnelStream(socket);
          });
          stream.on("close", () => closeTunnelStream(socket));
          socket.on("close", () => closeTunnelStream(stream));

          socket.pipe(stream);
          stream.pipe(socket);
        });
      });

      server.once("error", fail);
      server.listen(tunnel.localPort, "127.0.0.1", () => {
        if (settled) return;
        settled = true;
        sshClient = client;
        sshForwardServer = server;
        onProgress?.({ percent: 56, message: "本机隧道已建立，正在检测 C1..." });
        resolve({ target, forward });
      });
    });

    client.once("error", fail);
    client.on("close", () => {
      if (sshClient === client) {
        sshClient = null;
        if (sshForwardServer) {
          sshForwardServer.close();
          sshForwardServer = null;
        }
      }
    });

    client.connect({
      host: tunnel.host,
      port: 22,
      username: tunnel.user,
      password,
      readyTimeout: 12000,
      keepaliveInterval: 15000,
      keepaliveCountMax: 3,
    });
  });
}

function promptForSshPassword(tunnel, reason, connectWithPassword) {
  return new Promise((resolve) => {
    const modal = new BrowserWindow({
      width: 560,
      height: 640,
      parent: mainWindow,
      modal: true,
      resizable: false,
      minimizable: false,
      maximizable: false,
      title: "连接 CampusVision C1 服务",
      icon: APP_ICON_PATH,
      backgroundColor: "#f4f7fb",
      autoHideMenuBar: true,
      webPreferences: {
        contextIsolation: true,
        nodeIntegration: false,
        preload: path.join(__dirname, "preload.js"),
        sandbox: true,
      },
    });

    let resolved = false;
    let connecting = false;
    let lastProgressPercent = 0;
    const sendProgress = (payload) => {
      const percent = Number(payload?.percent);
      if (Number.isFinite(percent)) {
        lastProgressPercent = Math.max(0, Math.min(100, percent));
      }
      if (!modal.isDestroyed()) {
        modal.webContents.send("gkguard:ssh-connect-progress", payload);
      }
    };

    const done = (value) => {
      if (resolved) return;
      resolved = true;
      resolve(value);
      if (!modal.isDestroyed()) {
        modal.close();
      }
    };

    const submitHandler = async (event, password) => {
      if (event.sender === modal.webContents) {
        if (connecting) {
          return;
        }
        const submittedPassword = typeof password === "string" ? password : "";
        if (!submittedPassword) {
          sendProgress({ percent: 0, message: "请输入服务器密码。", busy: false, failed: true, recoverable: true });
          return;
        }
        connecting = true;
        lastProgressPercent = 12;
        sendProgress({ percent: 12, message: "已收到密码，正在连接...", busy: true });
        try {
          const result = await connectWithPassword(submittedPassword, sendProgress);
          sendProgress({ percent: 100, message: result.verified ? "CampusVision C1 已连接。" : "隧道已建立，可继续检索。", busy: false, done: true });
          setTimeout(() => done(result), 420);
        } catch (error) {
          connecting = false;
          sendProgress({ percent: Math.max(12, lastProgressPercent), message: `连接失败：${error.message}`, busy: false, failed: true, recoverable: true });
        }
      }
    };
    const cancelHandler = (event) => {
      if (event.sender === modal.webContents) {
        ipcMain.off("gkguard:ssh-password-submit", submitHandler);
        ipcMain.off("gkguard:ssh-password-cancel", cancelHandler);
        done({ connected: false, cancelled: true });
      }
    };

    ipcMain.on("gkguard:ssh-password-submit", submitHandler);
    ipcMain.on("gkguard:ssh-password-cancel", cancelHandler);
    modal.on("closed", () => {
      ipcMain.off("gkguard:ssh-password-submit", submitHandler);
      ipcMain.off("gkguard:ssh-password-cancel", cancelHandler);
      done({ connected: false, cancelled: true });
    });

    const query = new URLSearchParams({
      host: tunnel.host,
      user: tunnel.user,
      localPort: String(tunnel.localPort),
      remoteHost: tunnel.remoteHost,
      remotePort: String(tunnel.remotePort),
      reason,
    });
    modal.loadFile(path.join(__dirname, "ssh-password.html"), { query: Object.fromEntries(query) });
  });
}

async function promptForC1Tunnel(reason = "未检测到 CampusVision C1 服务") {
  const tunnel = getSshTunnelConfig();
  if (!tunnel) {
    return false;
  }

  const result = await promptForSshPassword(tunnel, reason, async (password, onProgress) => {
    await startEmbeddedSshTunnel(tunnel, password, onProgress);
    return waitForC1TunnelReady(tunnel, onProgress);
  });

  if (result?.connected) {
    return true;
  }

  if (result?.cancelled) {
    return false;
  }

  await dialog.showMessageBox(mainWindow, {
    type: "warning",
    title: "CampusVision C1 连接失败",
    message: "尚未确认 CampusVision C1 服务可用",
    detail: `${result?.error?.message || "SSH 隧道未能连接到 CampusVision C1。"}\n\n请确认服务器密码、校园网/VPN、CampusVision C1 服务状态和 18000 端口占用情况。`,
  });
  return false;
}

async function maybePromptForC1Tunnel() {
  const tunnel = getSshTunnelConfig();
  if (!tunnel) {
    return false;
  }

  try {
    const status = await getJson(getC1StatusUrl(), 2500);
    if (isC1TunnelConnected(status, tunnel)) {
      return true;
    }
    if (isC1Connected(status)) {
      return promptForC1Tunnel("CampusVision C1 直连可达，但尚未通过服务器密码建立 SSH 隧道");
    }
    return promptForC1Tunnel(status?.healthError ? "CampusVision C1 服务当前不可用" : "未检测到 CampusVision C1 服务");
  } catch {
    return promptForC1Tunnel("未检测到 CampusVision C1 服务");
  }
}

function waitForHealthCheck(timeoutMs = START_TIMEOUT_MS) {
  const startedAt = Date.now();
  return new Promise((resolve, reject) => {
    const check = () => {
      const request = http.get(getHealthUrl(), (response) => {
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
    String(activeBackendPort),
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

function getText(url, timeoutMs = 1200) {
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
        resolve(body);
      });
    });

    request.on("error", reject);
    request.setTimeout(timeoutMs, () => {
      request.destroy(new Error("Request timed out"));
    });
  });
}

async function existingBackendMatchesCurrentBuild(port) {
  try {
    await getJson(getHealthUrl(port), 900);
    const page = await getText(getDemoUrl(port), 900);
    return page.includes(`/static/styles.css?v=${STATIC_ASSET_VERSION}`)
      && page.includes(`/static/app.js?v=${STATIC_ASSET_VERSION}`);
  } catch {
    return false;
  }
}

function isPortAvailable(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => resolve(false));
    server.once("listening", () => {
      server.close(() => resolve(true));
    });
    server.listen(port, HOST);
  });
}

function getAvailablePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.once("listening", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : DEFAULT_PORT;
      server.close(() => resolve(port));
    });
    server.listen(0, HOST);
  });
}

async function prepareBackendPort() {
  if (await existingBackendMatchesCurrentBuild(DEFAULT_PORT)) {
    activeBackendPort = DEFAULT_PORT;
    return;
  }

  if (await isPortAvailable(DEFAULT_PORT)) {
    activeBackendPort = DEFAULT_PORT;
    return;
  }

  activeBackendPort = await getAvailablePort();
}

async function ensureBackend() {
  await prepareBackendPort();
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
    minWidth: 680,
    minHeight: 640,
    icon: APP_ICON_PATH,
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
    if (!isPlatformInstallerFilename(item.getFilename())) {
      return;
    }
    item.once("done", async (_doneEvent, state) => {
      if (state !== "completed") {
        await dialog.showMessageBox(mainWindow, {
          type: "warning",
          title: "下载未完成",
          message: "新版安装文件未完成下载",
          detail: "请检查网络后在 GKGuard 中重新点击检查更新。",
        });
        return;
      }
      const filePath = item.getSavePath();
      const result = await dialog.showMessageBox(mainWindow, {
        type: "info",
        title: "新版已下载",
        message: "GKGuard 新版安装文件已下载完成",
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

ipcMain.handle("gkguard:download-update", () => downloadUpdate());

ipcMain.handle("gkguard:install-update", () => installDownloadedUpdate());

ipcMain.handle("gkguard:connect-c1", async (_event, reason) => {
  const connected = await promptForC1Tunnel(typeof reason === "string" && reason ? reason : "CampusVision C1 服务当前不可用");
  return { connected, prompted: true };
});

async function boot() {
  createWindow();
  try {
    await ensureBackend();
    await maybePromptForC1Tunnel();
    await mainWindow.webContents.session.clearCache().catch((error) => {
      console.warn(`Failed to clear Electron cache before loading GKGuard UI: ${error.message}`);
    });
    await mainWindow.loadURL(getDemoUrl());
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
