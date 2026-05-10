const { app, BrowserWindow, ipcMain, session, shell } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const net = require("net");
const path = require("path");

const BACKEND_HOST = process.env.AMADEUS_HTTP_HOST || "127.0.0.1";
const BACKEND_PORT = Number(process.env.AMADEUS_HTTP_PORT || "4180");
const BACKEND_BASE_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`;
const DEV_RENDERER_URL = process.env.VITE_DEV_SERVER_URL || process.env.AMADEUS_RENDERER_URL || "http://localhost:4173";
const isDev = !app.isPackaged;

let backendProcess = null;
let mainWindow = null;

function findRepoRootFrom(startPath) {
  let current = path.resolve(startPath || ".");
  for (let depth = 0; depth < 8; depth += 1) {
    if (fs.existsSync(path.join(current, "amadeus_thread0", "runtime", "http_dev_server.py"))) {
      return current;
    }
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }
  return "";
}

function resolveRepoRoot() {
  const explicitRoot = String(process.env.AMADEUS_REPO_ROOT || "").trim();
  if (explicitRoot) return explicitRoot;

  const portableExecutableDir = String(process.env.PORTABLE_EXECUTABLE_DIR || "").trim();
  const portableExecutableFile = String(process.env.PORTABLE_EXECUTABLE_FILE || "").trim();
  const argvExecutable = String(process.argv[0] || "").trim();
  const candidates = [
    portableExecutableDir,
    portableExecutableFile ? path.dirname(portableExecutableFile) : "",
    argvExecutable ? path.dirname(argvExecutable) : "",
    path.resolve(__dirname, "..", ".."),
    path.resolve(process.cwd()),
    path.resolve(app.getAppPath(), "..", "..", "..", ".."),
  ].filter(Boolean);

  for (const candidate of candidates) {
    const repoRoot = findRepoRootFrom(candidate);
    if (repoRoot) return repoRoot;
  }

  return path.resolve(__dirname, "..", "..");
}

function canConnect(host, port, timeoutMs = 350) {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    let settled = false;
    function finish(value) {
      if (settled) return;
      settled = true;
      socket.destroy();
      resolve(value);
    }
    socket.setTimeout(timeoutMs);
    socket.once("connect", () => finish(true));
    socket.once("timeout", () => finish(false));
    socket.once("error", () => finish(false));
    socket.connect(port, host);
  });
}

async function waitForBackend(maxMs = 12000) {
  const started = Date.now();
  while (Date.now() - started < maxMs) {
    if (await canConnect(BACKEND_HOST, BACKEND_PORT, 450)) return true;
    await new Promise((resolve) => setTimeout(resolve, 350));
  }
  return false;
}

async function startBackend() {
  if (await canConnect(BACKEND_HOST, BACKEND_PORT)) {
    return { status: "already_running", baseUrl: BACKEND_BASE_URL, pid: null };
  }
  if (backendProcess) {
    return { status: "starting", baseUrl: BACKEND_BASE_URL, pid: backendProcess.pid || null };
  }

  const repoRoot = resolveRepoRoot();
  const python = process.env.AMADEUS_PYTHON || "python";
  const args = [
    "-m",
    "amadeus_thread0.runtime.http_dev_server",
    "--host",
    BACKEND_HOST,
    "--port",
    String(BACKEND_PORT),
    "--thread-id",
    process.env.AMADEUS_THREAD_ID || "thread0",
  ];

  backendProcess = spawn(python, args, {
    cwd: repoRoot,
    env: {
      ...process.env,
      AMADEUS_HTTP_HOST: BACKEND_HOST,
      AMADEUS_HTTP_PORT: String(BACKEND_PORT),
      PYTHONIOENCODING: "utf-8",
    },
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
  });

  backendProcess.stdout.on("data", (chunk) => {
    process.stdout.write(`[amadeus-backend] ${chunk}`);
  });
  backendProcess.stderr.on("data", (chunk) => {
    process.stderr.write(`[amadeus-backend] ${chunk}`);
  });
  backendProcess.once("exit", (code, signal) => {
    process.stdout.write(`[amadeus-backend] exited code=${code} signal=${signal}\n`);
    backendProcess = null;
  });

  const ready = await waitForBackend();
  return {
    status: ready ? "started" : "timeout",
    baseUrl: BACKEND_BASE_URL,
    pid: backendProcess ? backendProcess.pid || null : null,
  };
}

function stopBackend() {
  if (!backendProcess) return { status: "not_running" };
  const pid = backendProcess.pid || null;
  backendProcess.kill();
  backendProcess = null;
  return { status: "stopped", pid };
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1365,
    height: 768,
    minWidth: 1180,
    minHeight: 720,
    title: "Amadeus-K",
    backgroundColor: "#070912",
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      additionalArguments: [`--amadeus-backend-base=${BACKEND_BASE_URL}`],
    },
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  if (isDev) {
    mainWindow.loadURL(DEV_RENDERER_URL);
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }
}

function registerIpc() {
  ipcMain.handle("desktop:getBackendBase", () => BACKEND_BASE_URL);
  ipcMain.handle("desktop:startBackend", () => startBackend());
  ipcMain.handle("desktop:stopBackend", () => stopBackend());
  ipcMain.handle("desktop:getCapabilities", async () => {
    await startBackend();
    return { status: "ready", baseUrl: BACKEND_BASE_URL, platform: process.platform, isPackaged: app.isPackaged };
  });
  ipcMain.handle("media:listDevices", () => ({
    status: "renderer_owned",
    reason: "mediaDevices.enumerateDevices is only available in the renderer after permission grant",
  }));
  ipcMain.handle("media:startCall", () => ({ status: "renderer_backend_route", baseUrl: BACKEND_BASE_URL }));
  ipcMain.handle("media:stopCall", () => ({ status: "renderer_backend_route", baseUrl: BACKEND_BASE_URL }));
  ipcMain.handle("media:setMicMuted", (_event, muted) => ({ status: "local_state", muted: Boolean(muted) }));
  ipcMain.handle("media:setCameraEnabled", (_event, enabled) => ({ status: "local_state", enabled: Boolean(enabled) }));
  ipcMain.handle("media:submitAudioChunk", () => ({ status: "renderer_backend_route", baseUrl: BACKEND_BASE_URL }));
  ipcMain.handle("media:submitVideoFrame", () => ({ status: "renderer_backend_route", baseUrl: BACKEND_BASE_URL }));
  ipcMain.handle("artifact:submit", () => ({ status: "renderer_backend_route", baseUrl: BACKEND_BASE_URL }));
}

app.whenReady().then(async () => {
  registerIpc();
  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    const allowed = ["media", "camera", "microphone"].includes(permission);
    callback(allowed);
  });
  await startBackend();
  createWindow();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

app.on("before-quit", () => {
  stopBackend();
});
