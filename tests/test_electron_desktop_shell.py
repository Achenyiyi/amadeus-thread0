from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_electron_main_starts_backend_and_keeps_renderer_sandboxed():
    main = _read("frontend/electron/main.cjs")

    assert "amadeus_thread0.runtime.http_dev_server" in main
    assert "127.0.0.1" in main
    assert "4180" in main
    assert "contextIsolation: true" in main
    assert "nodeIntegration: false" in main
    assert "sandbox: true" in main
    assert "desktop:startBackend" in main
    assert "desktop:stopBackend" in main


def test_electron_preload_exposes_only_whitelisted_desktop_api():
    preload = _read("frontend/electron/preload.cjs")

    for channel in (
        "desktop:getCapabilities",
        "desktop:startBackend",
        "desktop:stopBackend",
        "media:listDevices",
        "media:startCall",
        "media:stopCall",
        "media:setMicMuted",
        "media:setCameraEnabled",
        "media:submitAudioChunk",
        "media:submitVideoFrame",
        "artifact:submit",
    ):
        assert channel in preload

    assert "contextBridge.exposeInMainWorld" in preload
    assert "allowedChannels" in preload
    assert "fs" not in preload
    assert "child_process" not in preload
