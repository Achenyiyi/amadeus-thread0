const { contextBridge, ipcRenderer } = require("electron");

const allowedChannels = new Set([
  "desktop:getCapabilities",
  "desktop:startBackend",
  "desktop:stopBackend",
  "desktop:getBackendBase",
  "media:listDevices",
  "media:startCall",
  "media:stopCall",
  "media:setMicMuted",
  "media:setCameraEnabled",
  "media:submitAudioChunk",
  "media:submitVideoFrame",
  "artifact:submit",
]);

function invoke(channel, payload) {
  if (!allowedChannels.has(channel)) {
    throw new Error(`Blocked IPC channel: ${channel}`);
  }
  return ipcRenderer.invoke(channel, payload);
}

const argPrefix = "--amadeus-backend-base=";
const backendArg = process.argv.find((arg) => String(arg).startsWith(argPrefix));
const backendBase = backendArg ? backendArg.slice(argPrefix.length) : "";

contextBridge.exposeInMainWorld("amadeusDesktop", {
  isElectron: true,
  backendBase,
  getBackendBase: () => invoke("desktop:getBackendBase"),
  getCapabilities: () => invoke("desktop:getCapabilities"),
  startBackend: () => invoke("desktop:startBackend"),
  stopBackend: () => invoke("desktop:stopBackend"),
  listDevices: () => invoke("media:listDevices"),
  startCall: () => invoke("media:startCall"),
  stopCall: () => invoke("media:stopCall"),
  setMicMuted: (muted) => invoke("media:setMicMuted", { muted: Boolean(muted) }),
  setCameraEnabled: (enabled) => invoke("media:setCameraEnabled", { enabled: Boolean(enabled) }),
  submitAudioChunk: (payload) => invoke("media:submitAudioChunk", payload || {}),
  submitVideoFrame: (payload) => invoke("media:submitVideoFrame", payload || {}),
  submitArtifact: (payload) => invoke("artifact:submit", payload || {}),
});
