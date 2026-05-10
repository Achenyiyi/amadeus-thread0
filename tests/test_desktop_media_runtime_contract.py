from __future__ import annotations

from types import SimpleNamespace

from amadeus_thread0.runtime.backend_api import BackendAPI, BackendApiEnvelope
from amadeus_thread0.runtime.transport_adapter import BackendTransportAdapter


class _FakeBackendSession:
    def __init__(self) -> None:
        self.messages = []

    def invoke_stream(self, message, config=None, on_text=None):
        self.messages.append({"message": message, "config": config})
        return SimpleNamespace(values={"final_text": "听到了。"}, streamed_text="听到了。", approval_request=None)

    def extract_final_text(self, values, streamed_text=""):
        return str(streamed_text or values.get("final_text") or "")

    def build_evolution_summary(self, state_values=None):
        return {
            "current_turn": {
                "trust": 0.5,
                "closeness": 0.5,
                "carryover_strength": 0.5,
                "primary_motive": "care",
                "goal_frame": "respond_to_voice",
            }
        }


class _FakeBundle:
    thread_id = "thread-media"
    settings = SimpleNamespace(data_dir=".", checkpoint_db_path="", model_base_url="", model_provider="mock", model_name="mock", runtime_mode="test")

    def __init__(self) -> None:
        self.backend_session = _FakeBackendSession()
        self.memory_admin = SimpleNamespace(snapshot_view=lambda: {})

    def config(self):
        return {"configurable": {"thread_id": self.thread_id}}


def _api() -> BackendAPI:
    return BackendAPI(runtime_bundle=_FakeBundle(), base_data_dir=SimpleNamespace())


def test_desktop_capabilities_route_returns_explicit_consent_policy():
    response = BackendTransportAdapter(_api()).handle("GET", "/api/desktop/capabilities")

    assert response["status"] == 200
    assert response["body"]["kind"] == "desktop_capabilities"
    payload = response["body"]["payload"]
    assert payload["schema"] == "desktop_live_capture.v1"
    assert payload["authority_boundary"]["live_capture_policy"] == "explicit_desktop_user_consent_only"
    assert payload["authority_boundary"]["live_capture_auto_enabled"] is False
    assert payload["capture_policy"]["background_capture"] == "blocked"


def test_media_session_start_requires_explicit_consent():
    adapter = BackendTransportAdapter(_api())

    blocked = adapter.handle("POST", "/api/media/session/start", body={"requested_permissions": ["microphone"]})
    started = adapter.handle(
        "POST",
        "/api/media/session/start",
        body={"consent": True, "requested_permissions": ["microphone", "camera"]},
    )

    assert blocked["status"] == 200
    assert blocked["body"]["payload"]["status"] == "blocked"
    assert "explicit_user_consent_required" in blocked["body"]["payload"]["failure_reasons"]
    assert started["body"]["payload"]["status"] == "active"
    assert started["body"]["payload"]["authority_boundary"]["live_capture_enabled"] is True
    assert started["body"]["payload"]["authority_boundary"]["live_capture_auto_enabled"] is False


def test_audio_input_fail_closed_without_active_session_or_consent():
    adapter = BackendTransportAdapter(_api())

    no_session = adapter.handle("POST", "/api/media/audio/input", body={"consent": True, "transcript": "你好"})
    adapter.handle("POST", "/api/media/session/start", body={"consent": True, "requested_permissions": ["microphone"]})
    no_consent = adapter.handle("POST", "/api/media/audio/input", body={"transcript": "你好"})

    assert no_session["body"]["kind"] == "media_turn"
    assert no_session["body"]["payload"]["status"] == "blocked"
    assert "active_media_session_required" in no_session["body"]["payload"]["failure_reasons"]
    assert no_consent["body"]["payload"]["status"] == "blocked"
    assert "explicit_user_consent_required" in no_consent["body"]["payload"]["failure_reasons"]


def test_audio_transcript_dispatches_through_chat_turn_path():
    api = _api()
    adapter = BackendTransportAdapter(api)
    adapter.handle("POST", "/api/media/session/start", body={"consent": True, "requested_permissions": ["microphone"]})

    response = adapter.handle(
        "POST",
        "/api/media/audio/input",
        body={"consent": True, "transcript": "你听得到吗", "duration_ms": 1200, "audio_digest": "sha256:voice"},
    )

    payload = response["body"]["payload"]
    assert response["body"]["kind"] == "media_turn"
    assert payload["status"] == "transcript_ready"
    assert payload["chat_dispatch"]["route_equivalent"] == "/api/chat/send"
    assert payload["assistant_turn"]["kind"] == "assistant_turn"
    assert payload["assistant_turn"]["meta"]["source"] == "media_audio_input"
    assert api.backend_session.messages[0]["message"]["messages"][0]["content"] == "你听得到吗"


def test_video_frame_is_readback_only_and_stops_after_session_stop():
    adapter = BackendTransportAdapter(_api())
    adapter.handle("POST", "/api/media/session/start", body={"consent": True, "requested_permissions": ["camera"]})

    accepted = adapter.handle(
        "POST",
        "/api/media/video/frame",
        body={"consent": True, "frame_digest": "sha256:frame", "width": 640, "height": 360},
    )
    adapter.handle("POST", "/api/media/session/stop", body={"reason": "test"})
    blocked = adapter.handle(
        "POST",
        "/api/media/video/frame",
        body={"consent": True, "frame_digest": "sha256:frame2"},
    )

    assert accepted["body"]["payload"]["status"] == "accepted_readback_only"
    assert accepted["body"]["payload"]["vision"]["model_api_called"] is False
    assert accepted["body"]["payload"]["perception_readback"]["writeback_ready"] is False
    assert blocked["body"]["payload"]["status"] == "blocked"
    assert "active_media_session_required" in blocked["body"]["payload"]["failure_reasons"]


def test_artifact_submission_requires_consent_digest_and_blocks_background_capture():
    adapter = BackendTransportAdapter(_api())

    accepted = adapter.handle(
        "POST",
        "/api/artifacts/submit",
        body={
            "consent": True,
            "modality": "image",
            "content_digest": "sha256:image",
            "filename": "scene.png",
            "capture_method": "user_selected_file",
        },
    )
    blocked = adapter.handle(
        "POST",
        "/api/artifacts/submit",
        body={
            "consent": True,
            "modality": "image",
            "content_digest": "sha256:bad",
            "capture_method": "background_camera",
        },
    )

    assert accepted["body"]["kind"] == "artifact_submission"
    assert accepted["body"]["payload"]["status"] == "accepted"
    assert accepted["body"]["payload"]["inspection"]["auto_execute"] is False
    assert blocked["body"]["payload"]["status"] == "blocked"
    assert "blocked_capture_method" in blocked["body"]["payload"]["failure_reasons"]


def test_media_tts_fails_closed_when_provider_is_not_configured(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    response = BackendTransportAdapter(_api()).handle(
        "POST",
        "/api/media/tts/synthesize",
        body={"text": "助手回复", "emotion_label": "warm"},
    )

    assert response["status"] == 200
    assert response["body"]["kind"] == "media_tts"
    payload = response["body"]["payload"]
    assert payload["schema"] == "media_tts.v1"
    assert payload["status"] == "blocked"
    assert "dashscope_api_key_required" in payload["failure_reasons"]
    assert payload["authority_boundary"]["frontend_semantics_owner"] is False
