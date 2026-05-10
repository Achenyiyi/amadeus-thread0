from __future__ import annotations

import base64
import hashlib
import os
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .session_orchestrator import build_tts_render_plan, push_tts_segments
from .tts_io import create_dashscope_realtime_session, get_tts_config


DESKTOP_LIVE_CAPTURE_SCHEMA = "desktop_live_capture.v1"
MEDIA_SESSION_SCHEMA = "media_session.v1"
MEDIA_TURN_SCHEMA = "media_turn.v1"
ARTIFACT_SUBMISSION_SCHEMA = "artifact_submission.v1"
MEDIA_TTS_SCHEMA = "media_tts.v1"

ALLOWED_PERMISSIONS = {"microphone", "camera", "artifact"}
ALLOWED_ARTIFACT_MODALITIES = {"image", "audio", "video", "text", "file", "screenshot", "camera_snapshot"}
BLOCKED_CAPTURE_METHODS = {
    "background_microphone",
    "background_camera",
    "background_screen",
    "background_desktop",
    "secret_capture",
    "implicit_capture",
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _bool(value: Any) -> bool:
    return bool(value is True or str(value).strip().lower() in {"1", "true", "yes", "on"})


def _now() -> int:
    return int(time.time())


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in parts if str(part))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _infer_audio_format(mime_type: str, explicit: str = "") -> str:
    fmt = str(explicit or "").strip().lower().replace(".", "")
    if fmt:
        return fmt
    mime = str(mime_type or "").strip().lower()
    if "wav" in mime or "wave" in mime:
        return "wav"
    if "mpeg" in mime or "mp3" in mime:
        return "mp3"
    if "pcm" in mime:
        return "pcm"
    return ""


def _extract_asr_text(sentence: Any) -> str:
    if isinstance(sentence, list):
        parts = []
        for item in sentence:
            if isinstance(item, dict) and str(item.get("text") or "").strip():
                parts.append(str(item.get("text") or "").strip())
        return "".join(parts).strip()
    if isinstance(sentence, dict):
        return str(sentence.get("text") or "").strip()
    return ""


def _permission_row(status: str = "not_requested", *, requested_at: int = 0) -> dict[str, Any]:
    row: dict[str, Any] = {
        "status": status,
        "system_grant": "unknown",
        "requested_at": requested_at,
    }
    return row


@dataclass
class DesktopMediaRuntime:
    """In-memory desktop media contract state.

    The runtime records explicit user consent and media-session state. It does not
    interpret media semantically, call multimodal models, or write memory facts.
    """

    thread_id: str
    permission_state: dict[str, dict[str, Any]] = field(default_factory=dict)
    session: dict[str, Any] = field(default_factory=dict)
    latest_media_turn: dict[str, Any] = field(default_factory=dict)
    latest_artifact: dict[str, Any] = field(default_factory=dict)
    latest_tts: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for permission in ALLOWED_PERMISSIONS:
            self.permission_state.setdefault(permission, _permission_row())

    def authority_boundary(self, *, active_session: bool | None = None) -> dict[str, Any]:
        active = bool(self.session.get("active", False)) if active_session is None else bool(active_session)
        return {
            "schema": DESKTOP_LIVE_CAPTURE_SCHEMA,
            "live_capture_policy": "explicit_desktop_user_consent_only",
            "live_capture_enabled": active,
            "live_capture_auto_enabled": False,
            "background_capture_allowed": False,
            "frontend_semantics_owner": False,
            "model_api_auto_call_allowed": False,
            "memory_write_allowed_from_frontend": False,
            "persona_core_mutation_allowed": False,
        }

    def capabilities(self, *, settings: Any = None, env: dict[str, str] | None = None) -> dict[str, Any]:
        current_env = dict(env or os.environ)
        tts_backend = str(current_env.get("AMADEUS_TTS_BACKEND") or "").strip()
        return {
            "schema": DESKTOP_LIVE_CAPTURE_SCHEMA,
            "thread_id": self.thread_id,
            "desktop_target": "windows_private_alpha",
            "capture_policy": {
                "microphone": "explicit_user_toggle",
                "camera": "explicit_user_toggle",
                "screen": "not_enabled",
                "background_capture": "blocked",
            },
            "providers": {
                "asr": {
                    "provider": "dashscope_priority",
                    "status": "contract_ready_provider_not_bound",
                    "api_key_set": bool(str(current_env.get("DASHSCOPE_API_KEY") or "").strip()),
                },
                "tts": {
                    "provider": tts_backend or "dashscope_realtime",
                    "status": "available_if_configured" if tts_backend or str(current_env.get("AMADEUS_TTS_ENABLED") or "").strip() else "not_configured",
                    "api_key_set": bool(str(current_env.get("DASHSCOPE_API_KEY") or "").strip()),
                    "model": str(current_env.get("AMADEUS_TTS_DASHSCOPE_MODEL") or "").strip(),
                },
                "vision": {
                    "provider": "explicit_provider_required",
                    "status": "readback_only_no_auto_model_call",
                },
            },
            "device_enumeration": {
                "owner": "electron_renderer",
                "system_grant_source": "desktop_os_prompt",
            },
            "permissions": self.permission_snapshot(),
            "media_session": self.session_snapshot(),
            "authority_boundary": self.authority_boundary(),
            "routes": {
                "read": ["/api/desktop/capabilities", "/api/media/session/current"],
                "control": [
                    "/api/desktop/permissions/request",
                    "/api/media/session/start",
                    "/api/media/session/stop",
                    "/api/media/audio/input",
                    "/api/media/video/frame",
                    "/api/media/tts/synthesize",
                    "/api/artifacts/submit",
                ],
            },
        }

    def permission_snapshot(self) -> dict[str, Any]:
        return {
            "schema": "desktop_permission_state.v1",
            "permissions": {key: dict(value) for key, value in self.permission_state.items()},
            "authority_boundary": self.authority_boundary(),
        }

    def request_permissions(self, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = _dict_or_empty(body)
        requested = _list_of_strings(data.get("permissions"))
        if not requested and str(data.get("permission") or "").strip():
            requested = [str(data.get("permission") or "").strip()]
        now = _now()
        accepted: list[str] = []
        rejected: list[str] = []
        for permission in requested:
            normalized = permission.lower()
            if normalized not in ALLOWED_PERMISSIONS:
                rejected.append(permission)
                continue
            self.permission_state[normalized] = {
                "status": "requested",
                "system_grant": "unknown",
                "requested_at": now,
                "source": str(data.get("source") or "desktop_user_action"),
            }
            accepted.append(normalized)
        payload = self.permission_snapshot()
        payload.update(
            {
                "requested": accepted,
                "rejected": rejected,
                "status": "requested" if accepted else "blocked",
                "failure_reasons": [] if accepted else ["no_supported_permissions_requested"],
            }
        )
        return payload

    def session_snapshot(self) -> dict[str, Any]:
        if not self.session:
            return {
                "schema": MEDIA_SESSION_SCHEMA,
                "status": "stopped",
                "active": False,
                "session_id": "",
                "permissions": self.permission_snapshot()["permissions"],
                "latest_media_turn": dict(self.latest_media_turn),
                "latest_artifact": dict(self.latest_artifact),
                "latest_tts": dict(self.latest_tts),
                "authority_boundary": self.authority_boundary(active_session=False),
            }
        snapshot = dict(self.session)
        snapshot["schema"] = MEDIA_SESSION_SCHEMA
        snapshot["permissions"] = self.permission_snapshot()["permissions"]
        snapshot["latest_media_turn"] = dict(self.latest_media_turn)
        snapshot["latest_artifact"] = dict(self.latest_artifact)
        snapshot["latest_tts"] = dict(self.latest_tts)
        snapshot["authority_boundary"] = self.authority_boundary(active_session=bool(snapshot.get("active")))
        return snapshot

    def start_session(self, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = _dict_or_empty(body)
        consent = _bool(data.get("consent"))
        requested = _list_of_strings(data.get("requested_permissions")) or ["microphone", "camera"]
        supported = [permission for permission in requested if permission in ALLOWED_PERMISSIONS]
        if not consent:
            return {
                "schema": MEDIA_SESSION_SCHEMA,
                "status": "blocked",
                "active": False,
                "failure_reasons": ["explicit_user_consent_required"],
                "authority_boundary": self.authority_boundary(active_session=False),
            }
        for permission in supported:
            if self.permission_state.get(permission, {}).get("status") == "not_requested":
                self.permission_state[permission] = _permission_row("requested", requested_at=_now())
        session_id = _stable_id("media", self.thread_id, _now(), data.get("mode") or "av_call")
        self.session = {
            "schema": MEDIA_SESSION_SCHEMA,
            "session_id": session_id,
            "status": "active",
            "active": True,
            "mode": str(data.get("mode") or "human_ai_av_call"),
            "started_at": _now(),
            "stopped_at": 0,
            "requested_permissions": supported,
            "capture_policy": "explicit_desktop_user_consent_only",
            "audio": {
                "enabled": "microphone" in supported,
                "muted": bool(data.get("mic_muted", False)),
                "provider": "dashscope_priority",
                "asr_status": "provider_not_bound",
            },
            "video": {
                "enabled": "camera" in supported,
                "frame_rate_policy": "low_frequency_or_user_snapshot",
                "vision_status": "readback_only_no_auto_model_call",
            },
        }
        return self.session_snapshot()

    def stop_session(self, body: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.session or not bool(self.session.get("active")):
            return self.session_snapshot()
        self.session["status"] = "stopped"
        self.session["active"] = False
        self.session["stopped_at"] = _now()
        self.session["stop_reason"] = str(_dict_or_empty(body).get("reason") or "user_stopped")
        return self.session_snapshot()

    def _session_active_or_blocked(self) -> tuple[bool, dict[str, Any] | None]:
        if self.session and bool(self.session.get("active")):
            return True, None
        return False, {
            "schema": MEDIA_TURN_SCHEMA,
            "status": "blocked",
            "failure_reasons": ["active_media_session_required"],
            "media_session": self.session_snapshot(),
            "authority_boundary": self.authority_boundary(active_session=False),
        }

    def _transcribe_audio(self, data: dict[str, Any], *, settings: Any = None) -> tuple[str, dict[str, Any], list[str]]:
        provided = str(data.get("audio_base64") or "").strip()
        mime_type = str(data.get("mime_type") or "audio/wav").strip()
        audio_format = _infer_audio_format(mime_type, str(data.get("audio_format") or ""))
        sample_rate = _int_value(data.get("sample_rate_hz"), 16000) or 16000
        model = str(os.getenv("AMADEUS_ASR_DASHSCOPE_MODEL", "paraformer-realtime-v2") or "paraformer-realtime-v2").strip()
        base_meta = {
            "provider": "dashscope_priority",
            "model": model,
            "status": "asr_provider_not_connected",
            "transcript": "",
            "model_api_called": False,
            "audio_format": audio_format,
            "sample_rate_hz": sample_rate,
        }
        if not provided:
            return "", base_meta, ["asr_provider_not_connected"]
        if not str(os.getenv("DASHSCOPE_API_KEY", "")).strip():
            meta = dict(base_meta)
            meta["status"] = "dashscope_api_key_required"
            return "", meta, ["dashscope_api_key_required"]
        if audio_format not in {"wav", "mp3", "pcm"}:
            meta = dict(base_meta)
            meta["status"] = "asr_audio_format_not_supported"
            return "", meta, ["asr_audio_format_not_supported"]
        try:
            raw = base64.b64decode(provided, validate=True)
        except Exception:
            meta = dict(base_meta)
            meta["status"] = "invalid_audio_base64"
            return "", meta, ["invalid_audio_base64"]
        max_bytes = _int_value(os.getenv("AMADEUS_ASR_MAX_AUDIO_BYTES"), 8_000_000)
        if not raw:
            meta = dict(base_meta)
            meta["status"] = "empty_audio"
            return "", meta, ["empty_audio"]
        if len(raw) > max_bytes:
            meta = dict(base_meta)
            meta["status"] = "audio_too_large"
            return "", meta, ["audio_too_large"]

        data_dir = Path(getattr(settings, "data_dir", Path("data")) if settings is not None else Path("data"))
        media_dir = data_dir / "media_in"
        media_dir.mkdir(parents=True, exist_ok=True)
        audio_path = media_dir / f"asr-{_stable_id('chunk', self.thread_id, time.time(), len(raw))}.{audio_format}"
        audio_path.write_bytes(raw)

        started = time.time()
        try:
            import dashscope  # type: ignore
            from dashscope.audio.asr.recognition import Recognition, RecognitionCallback  # type: ignore

            dashscope.api_key = str(os.getenv("DASHSCOPE_API_KEY", "")).strip()
            recognizer = Recognition(
                model=model,
                callback=RecognitionCallback(),
                format=audio_format,
                sample_rate=sample_rate,
            )
            result = recognizer.call(str(audio_path))
            status_code = int(getattr(result, "status_code", 0) or 0)
            sentence = result.get_sentence() if hasattr(result, "get_sentence") else None
            transcript = _extract_asr_text(sentence)
            if status_code != 200:
                meta = dict(base_meta)
                meta.update(
                    {
                        "status": "dashscope_asr_failed",
                        "model_api_called": True,
                        "status_code": status_code,
                        "request_id": str(getattr(result, "request_id", "") or ""),
                        "message": str(getattr(result, "message", "") or ""),
                        "latency_ms": int((time.time() - started) * 1000),
                    }
                )
                return "", meta, [f"dashscope_asr_failed:{status_code}"]
            if not transcript:
                meta = dict(base_meta)
                meta.update(
                    {
                        "status": "dashscope_asr_empty_transcript",
                        "model_api_called": True,
                        "status_code": status_code,
                        "request_id": str(getattr(result, "request_id", "") or ""),
                        "latency_ms": int((time.time() - started) * 1000),
                    }
                )
                return "", meta, ["dashscope_asr_empty_transcript"]
            meta = dict(base_meta)
            meta.update(
                {
                    "status": "transcribed",
                    "transcript": transcript,
                    "model_api_called": True,
                    "status_code": status_code,
                    "request_id": str(getattr(result, "request_id", "") or ""),
                    "latency_ms": int((time.time() - started) * 1000),
                }
            )
            return transcript, meta, []
        except Exception as exc:
            meta = dict(base_meta)
            meta.update(
                {
                    "status": "dashscope_asr_exception",
                    "model_api_called": True,
                    "latency_ms": int((time.time() - started) * 1000),
                    "message": str(exc),
                }
            )
            return "", meta, [f"dashscope_asr_exception:{str(exc)}"]

    def submit_audio_input(self, body: dict[str, Any] | None = None, *, settings: Any = None) -> dict[str, Any]:
        data = _dict_or_empty(body)
        active, blocked = self._session_active_or_blocked()
        if not active and blocked is not None:
            self.latest_media_turn = blocked
            return blocked
        if not _bool(data.get("consent")):
            payload = {
                "schema": MEDIA_TURN_SCHEMA,
                "status": "blocked",
                "modality": "audio",
                "failure_reasons": ["explicit_user_consent_required"],
                "media_session": self.session_snapshot(),
                "authority_boundary": self.authority_boundary(),
            }
            self.latest_media_turn = payload
            return payload
        transcript = str(data.get("transcript") or "").strip()
        asr_meta: dict[str, Any]
        failures: list[str]
        if transcript:
            asr_meta = {
                "provider": "dashscope_priority",
                "status": "provided_transcript",
                "transcript": transcript,
                "model_api_called": False,
            }
            failures = []
        else:
            transcript, asr_meta, failures = self._transcribe_audio(data, settings=settings)
        payload = {
            "schema": MEDIA_TURN_SCHEMA,
            "status": "transcript_ready" if transcript else "blocked",
            "modality": "audio",
            "media_session_id": str(self.session.get("session_id") or ""),
            "audio": {
                "duration_ms": int(data.get("duration_ms") or 0),
                "audio_digest": str(data.get("audio_digest") or "").strip(),
                "mime_type": str(data.get("mime_type") or "audio/wav"),
                "sample_rate_hz": _int_value(data.get("sample_rate_hz"), 0),
                "audio_base64_received": bool(str(data.get("audio_base64") or "").strip()),
            },
            "asr": asr_meta,
            "chat_dispatch": {
                "allowed": bool(transcript),
                "route_equivalent": "/api/chat/send",
            },
            "authority_boundary": self.authority_boundary(),
            "failure_reasons": [] if transcript else failures,
        }
        self.latest_media_turn = payload
        return payload

    def submit_video_frame(self, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = _dict_or_empty(body)
        active, blocked = self._session_active_or_blocked()
        if not active and blocked is not None:
            self.latest_media_turn = blocked
            return blocked
        if not _bool(data.get("consent")):
            payload = {
                "schema": MEDIA_TURN_SCHEMA,
                "status": "blocked",
                "modality": "video",
                "failure_reasons": ["explicit_user_consent_required"],
                "media_session": self.session_snapshot(),
                "authority_boundary": self.authority_boundary(),
            }
            self.latest_media_turn = payload
            return payload
        payload = {
            "schema": MEDIA_TURN_SCHEMA,
            "status": "accepted_readback_only",
            "modality": "video",
            "media_session_id": str(self.session.get("session_id") or ""),
            "frame": {
                "frame_digest": str(data.get("frame_digest") or "").strip(),
                "width": int(data.get("width") or 0),
                "height": int(data.get("height") or 0),
                "captured_at": int(data.get("captured_at") or _now()),
                "caption": str(data.get("caption") or "").strip(),
            },
            "vision": {
                "provider": "explicit_provider_required",
                "model_api_called": False,
                "status": "metadata_accepted_no_auto_model_call",
            },
            "perception_readback": {
                "source": "desktop_camera_user_consented",
                "writeback_ready": False,
            },
            "authority_boundary": self.authority_boundary(),
            "failure_reasons": [],
        }
        self.latest_media_turn = payload
        return payload

    def submit_artifact(self, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = _dict_or_empty(body)
        modality = str(data.get("modality") or "").strip().lower()
        capture_method = str(data.get("capture_method") or "user_selected_file").strip().lower()
        digest = str(data.get("content_digest") or data.get("digest") or "").strip()
        label = str(data.get("label") or data.get("filename") or "artifact").strip()
        failures: list[str] = []
        if not _bool(data.get("consent")):
            failures.append("explicit_user_consent_required")
        if modality not in ALLOWED_ARTIFACT_MODALITIES:
            failures.append("unsupported_modality")
        if capture_method in BLOCKED_CAPTURE_METHODS:
            failures.append("blocked_capture_method")
        if not digest:
            failures.append("content_digest_required")
        artifact_id = _stable_id("artifact", self.thread_id, digest or label, modality, capture_method)
        payload = {
            "schema": ARTIFACT_SUBMISSION_SCHEMA,
            "status": "blocked" if failures else "accepted",
            "artifact": {
                "artifact_id": artifact_id,
                "label": label,
                "modality": modality,
                "content_digest": digest,
                "mime_type": str(data.get("mime_type") or "").strip(),
                "size_bytes": int(data.get("size_bytes") or 0),
                "capture_method": capture_method,
            },
            "source_ref": {
                "id": artifact_id,
                "tool_name": "desktop_artifact_submit",
                "title": label,
                "query": modality,
            },
            "inspection": {
                "status": "available_for_explicit_inspection",
                "auto_execute": False,
                "model_api_call_planned": False,
                "live_capture_used": capture_method == "camera_snapshot",
            },
            "authority_boundary": self.authority_boundary(),
            "failure_reasons": failures,
        }
        self.latest_artifact = payload
        return payload

    def synthesize_tts(self, body: dict[str, Any] | None = None, *, settings: Any = None) -> dict[str, Any]:
        data = _dict_or_empty(body)
        text = str(data.get("text") or "").strip()
        emotion_label = str(data.get("emotion_label") or "neutral").strip() or "neutral"
        failures: list[str] = []
        if not text:
            failures.append("text_required")

        cfg = get_tts_config()
        backend = str(os.getenv("AMADEUS_TTS_BACKEND", "dashscope_realtime") or "dashscope_realtime").strip().lower()
        if backend not in {"dashscope_realtime", "dashscope"}:
            failures.append("unsupported_tts_backend")
        if not bool(cfg.enabled):
            failures.append("tts_disabled")
        if not str(cfg.ref_audio or "").strip():
            failures.append("tts_ref_audio_required")
        if not str(os.getenv("DASHSCOPE_API_KEY", "")).strip():
            failures.append("dashscope_api_key_required")

        plan = build_tts_render_plan(text, emotion_label)
        base_payload: dict[str, Any] = {
            "schema": MEDIA_TTS_SCHEMA,
            "status": "blocked" if failures else "pending",
            "provider": "dashscope_realtime",
            "emotion_label": emotion_label,
            "text": text,
            "render_plan": plan,
            "audio": {
                "mime_type": "audio/wav",
                "sample_rate_hz": 24000,
                "url": "",
                "path": "",
                "duration_ms": 0,
                "bytes": 0,
            },
            "failure_reasons": failures,
            "authority_boundary": self.authority_boundary(),
        }
        if failures:
            self.latest_tts = base_payload
            return base_payload

        out_dir = Path(getattr(settings, "data_dir", Path("data")) if settings is not None else Path("data")) / "tts_out"
        try:
            session = create_dashscope_realtime_session(
                ref_audio=str(cfg.ref_audio),
                out_dir=out_dir,
                play_audio=False,
            )
            t0 = time.time()
            tts_plan = push_tts_segments(session, text=text, emotion_label=emotion_label)
            session.finish_and_wait()
            duration_ms = 0
            if Path(session.out_path).exists():
                try:
                    with wave.open(str(session.out_path), "rb") as wf:
                        frames = wf.getnframes()
                        rate = wf.getframerate() or 24000
                        duration_ms = int((frames / float(rate)) * 1000)
                except Exception:
                    duration_ms = 0
            if int(session.total_audio_bytes or 0) <= 0:
                raise RuntimeError("dashscope returned 0 audio bytes")
            audio_base64 = ""
            try:
                audio_base64 = base64.b64encode(Path(session.out_path).read_bytes()).decode("ascii")
            except Exception:
                audio_base64 = ""
            payload = dict(base_payload)
            payload.update(
                {
                    "status": "synthesized",
                    "render_plan": tts_plan,
                    "latency_ms": int((time.time() - t0) * 1000),
                    "audio": {
                        "mime_type": "audio/wav",
                        "sample_rate_hz": 24000,
                        "url": f"/api/media/tts/audio?path={Path(session.out_path).name}",
                        "path": str(session.out_path),
                        "duration_ms": duration_ms,
                        "bytes": int(session.total_audio_bytes or 0),
                        "base64": audio_base64,
                    },
                    "failure_reasons": [],
                }
            )
        except Exception as exc:
            payload = dict(base_payload)
            payload.update(
                {
                    "status": "failed",
                    "failure_reasons": [f"tts_synthesis_failed:{str(exc)}"],
                }
            )
        self.latest_tts = payload
        return payload


__all__ = [
    "ARTIFACT_SUBMISSION_SCHEMA",
    "DESKTOP_LIVE_CAPTURE_SCHEMA",
    "MEDIA_TTS_SCHEMA",
    "MEDIA_SESSION_SCHEMA",
    "MEDIA_TURN_SCHEMA",
    "DesktopMediaRuntime",
]
