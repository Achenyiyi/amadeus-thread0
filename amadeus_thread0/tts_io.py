from __future__ import annotations

import base64
import json
import os
import time
import uuid
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .settings import get_settings


_DASHSCOPE_VOICE_CACHE_PATH = "tts_voice_cache.json"


def _dashscope_voice_cache_file() -> Path:
    s = get_settings()
    return s.data_dir / _DASHSCOPE_VOICE_CACHE_PATH


def _load_json_file(p: Path) -> dict[str, Any]:
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {}


def _save_json_file(p: Path, data: dict[str, Any]) -> None:
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _norm_ref_audio_key(ref_audio_path: Path) -> str:
    try:
        p = ref_audio_path.expanduser().resolve()
    except Exception:
        p = ref_audio_path.expanduser()

    try:
        st = p.stat()
        mtime = int(st.st_mtime)
        size = int(st.st_size)
    except Exception:
        mtime = 0
        size = 0

    return f"{str(p)}|mtime={mtime}|size={size}"


def _get_or_create_dashscope_voice(ref_audio_path: Path) -> str:
    """DashScope 声音复刻：把 ref_audio 注册成 voice（服务端缓存），并做本地持久化缓存。"""

    api_key = str(os.getenv("DASHSCOPE_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError("missing DASHSCOPE_API_KEY")

    target_model = str(
        os.getenv("AMADEUS_TTS_DASHSCOPE_TARGET_MODEL", "qwen3-tts-vc-realtime-2026-01-15")
    ).strip()
    preferred_name = str(os.getenv("AMADEUS_TTS_DASHSCOPE_PREFERRED_NAME", "amadeus")).strip()
    audio_mime = str(os.getenv("AMADEUS_TTS_DASHSCOPE_AUDIO_MIME", "audio/wav")).strip()
    enroll_url = str(
        os.getenv(
            "AMADEUS_TTS_DASHSCOPE_ENROLL_URL",
            "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization",
        )
    ).strip()

    ref_key = _norm_ref_audio_key(ref_audio_path)

    cache_file = _dashscope_voice_cache_file()
    cache = _load_json_file(cache_file)
    cached = cache.get(ref_key)
    if isinstance(cached, str) and cached.strip():
        return cached.strip()

    import requests  # type: ignore

    if not ref_audio_path.exists():
        raise ValueError("ref_audio not found: " + str(ref_audio_path))

    base64_str = base64.b64encode(ref_audio_path.read_bytes()).decode("utf-8")
    data_uri = f"data:{audio_mime};base64,{base64_str}"

    # 按官方文档：enrollment 只上传音频（data uri），不传入 ref_text/ref_language
    payload = {
        "model": "qwen-voice-enrollment",
        "input": {
            "action": "create",
            "target_model": target_model,
            "preferred_name": preferred_name,
            "audio": {"data": data_uri},
        },
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = requests.post(enroll_url, json=payload, headers=headers, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"dashscope enrollment failed: {resp.status_code}, {resp.text}")

    voice = resp.json()["output"]["voice"]
    if not isinstance(voice, str) or not voice.strip():
        raise RuntimeError("dashscope enrollment returned empty voice")

    cache[ref_key] = voice.strip()
    _save_json_file(cache_file, cache)
    return voice.strip()


@dataclass
class TTSConfig:
    enabled: bool
    ref_audio: str
    ref_text: str


def get_tts_config() -> TTSConfig:
    s = get_settings()
    enabled = bool(getattr(s, "tts_enabled", False))
    ref_audio = str(getattr(s, "tts_ref_audio", "")).strip()
    ref_text = str(getattr(s, "tts_ref_text", "")).strip()
    return TTSConfig(enabled=enabled, ref_audio=ref_audio, ref_text=ref_text)


class DashscopeRealtimeSession:
    """DashScope Qwen3-TTS Realtime 会话。"""

    def __init__(self, voice: str, out_path: Path, play_audio: bool):
        self.voice = voice
        self.out_path = out_path
        self.play_audio = bool(play_audio)

        self._pcm_chunks: list[bytes] = []
        self._first_audio_delay: float | None = None
        self._t0 = time.time()

        self._done = None
        self._client = None

        # CLI 会读取这个字段来判断是否收到音频（用于诊断 API key/model/ws url）。
        self.total_audio_bytes: int = 0

    @property
    def first_audio_delay(self) -> float | None:
        return self._first_audio_delay

    def connect(self) -> None:
        import dashscope  # type: ignore
        from dashscope.audio.qwen_tts_realtime import (  # type: ignore
            AudioFormat,
            QwenTtsRealtime,
            QwenTtsRealtimeCallback,
        )

        dashscope.api_key = str(os.getenv("DASHSCOPE_API_KEY", "")).strip()

        ws_url = str(
            os.getenv(
                "AMADEUS_TTS_DASHSCOPE_WS_URL",
                "wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
            )
        ).strip()
        model = str(
            os.getenv(
                "AMADEUS_TTS_DASHSCOPE_MODEL",
                "qwen3-tts-vc-realtime-2026-01-15",
            )
        ).strip()

        play_audio = self.play_audio
        pcm_chunks = self._pcm_chunks
        t0 = self._t0

        player = None
        stream = None
        if play_audio:
            import pyaudio  # type: ignore

            player = pyaudio.PyAudio()
            stream = player.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=24000,
                output=True,
            )

        self_first_audio_delay = [self._first_audio_delay]

        class _Cb(QwenTtsRealtimeCallback):
            def __init__(self):
                import threading

                self.done = threading.Event()

            def on_close(self, close_status_code, close_msg) -> None:
                try:
                    if stream is not None:
                        stream.stop_stream()
                        stream.close()
                    if player is not None:
                        player.terminate()
                except Exception:
                    pass

            def on_event(self, response: dict) -> None:
                try:
                    event_type = response.get("type", "")
                    if event_type == "response.audio.delta":
                        raw = base64.b64decode(response.get("delta") or b"")
                        if raw:
                            pcm_chunks.append(raw)
                            if self_first_audio_delay[0] is None:
                                self_first_audio_delay[0] = time.time() - t0
                            if stream is not None:
                                stream.write(raw)
                    elif event_type == "session.finished":
                        self.done.set()
                except Exception:
                    pass

        cb = _Cb()
        client = QwenTtsRealtime(model=model, callback=cb, url=ws_url)
        client.connect()
        client.update_session(
            voice=self.voice,
            response_format=AudioFormat.PCM_24000HZ_MONO_16BIT,
            mode="server_commit",
        )

        self._done = cb.done
        self._client = client
        self._first_audio_delay = self_first_audio_delay[0]

    def append_text(self, text: str) -> None:
        if self._client is None:
            raise RuntimeError("dashscope realtime not connected")
        self._client.append_text(text)

    def finish_and_wait(self) -> None:
        if self._client is None or self._done is None:
            return
        self._client.finish()
        self._done.wait()

        pcm = b"".join(self._pcm_chunks)
        self.total_audio_bytes = int(len(pcm))
        if pcm:
            self.out_path.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(self.out_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # int16
                wf.setframerate(24000)
                wf.writeframes(pcm)


def create_dashscope_realtime_session(
    *,
    ref_audio: str,
    out_dir: Path | None = None,
    play_audio: bool = True,
) -> DashscopeRealtimeSession:
    s = get_settings()
    if out_dir is None:
        out_dir = s.data_dir / "tts_out"
    out_dir.mkdir(parents=True, exist_ok=True)

    ref_audio_path = Path(ref_audio).expanduser()
    voice = _get_or_create_dashscope_voice(ref_audio_path)

    fname = f"tts-rt-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.wav"
    out_path = out_dir / fname

    sess = DashscopeRealtimeSession(voice=voice, out_path=out_path, play_audio=play_audio)
    sess.connect()
    return sess