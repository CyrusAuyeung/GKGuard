const { app, BrowserWindow, dialog, shell } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");

const PORT = Number(process.env.GKGUARD_PORT || 8000);
const HOST = "127.0.0.1";
const BASE_URL = `http://${HOST}:${PORT}`;
const HEALTH_URL = `${BASE_URL}/health`;
const DEMO_URL = `${BASE_URL}/demo?desktop=1`;
const START_TIMEOUT_MS = 18000;
const POLL_INTERVAL_MS = 450;

let backendProcess = null;
let mainWindow = null;

function getBackendRoot() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "backend");
  }
  return path.join(__dirname, "..", "backend");
}

function getPythonCandidates() {
  return [process.env.GKGUARD_PYTHON, "python", "py", "python3"].filter(Boolean);
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
    env: {
      ...process.env,
      PYTHONUNBUFFERED: "1",
    },
  });
}

async function startBackend() {
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
      sandbox: true,
    },
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.loadFile(path.join(__dirname, "loading.html"));
}

async function boot() {
  createWindow();
  try {
    await ensureBackend();
    await mainWindow.loadURL(DEMO_URL);
    if (process.argv.includes("--devtools")) {
      mainWindow.webContents.openDevTools({ mode: "detach" });
    }
  } catch (error) {
    await dialog.showMessageBox(mainWindow, {
      type: "error",
      title: "GKGuard 启动失败",
      message: "无法启动本地后端服务",
      detail: `${error.message}\n\n请先在 backend 目录执行：python -m pip install -r requirements.txt`,
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