from __future__ import annotations

from types import SimpleNamespace

from amadeus_thread0.runtime.backend_api import BackendApiEnvelope
from amadeus_thread0.runtime.transport_adapter import BackendTransportAdapter


class _FakeBackendApi:
    def __init__(self) -> None:
        self.turn_calls = []
        self.event_calls = []
        self.current_turn_calls = []
        self.chat_calls = []

    def thread_inventory(self):
        return BackendApiEnvelope(kind="thread_inventory", thread_id="thread-a", payload={"current_thread_id": "thread-a"})

    def runtime_layout(self):
        return BackendApiEnvelope(kind="runtime_layout", thread_id="thread-a", payload={"repo_runtime": {"ok": True}})

    def environment_summary(self):
        return BackendApiEnvelope(kind="environment_summary", thread_id="thread-a", payload={"runtime_mode": "regression"})

    def runtime_productization(self):
        return BackendApiEnvelope(
            kind="runtime_productization",
            thread_id="thread-a",
            payload={"readiness_status": "runtime_productization_phase1_ready"},
        )

    def operator_console_rc(self):
        return BackendApiEnvelope(
            kind="operator_console_rc",
            thread_id="thread-a",
            payload={"readiness_status": "operator_console_rc_phase1_ready"},
        )

    def desktop_capabilities(self):
        return BackendApiEnvelope(
            kind="desktop_capabilities",
            thread_id="thread-a",
            payload={"schema": "desktop_live_capture.v1"},
        )

    def request_desktop_permissions(self, *, body=None):
        return BackendApiEnvelope(
            kind="desktop_permission_state",
            thread_id="thread-a",
            payload={"requested": body.get("permissions", []) if isinstance(body, dict) else []},
        )

    def current_media_session(self):
        return BackendApiEnvelope(kind="media_session", thread_id="thread-a", payload={"status": "stopped"})

    def start_media_session(self, *, body=None):
        return BackendApiEnvelope(kind="media_session", thread_id="thread-a", payload={"status": "active", "body": body or {}})

    def stop_media_session(self, *, body=None):
        return BackendApiEnvelope(kind="media_session", thread_id="thread-a", payload={"status": "stopped", "body": body or {}})

    def submit_media_audio(self, *, body=None):
        return BackendApiEnvelope(kind="media_turn", thread_id="thread-a", payload={"modality": "audio", "body": body or {}})

    def submit_media_video_frame(self, *, body=None):
        return BackendApiEnvelope(kind="media_turn", thread_id="thread-a", payload={"modality": "video", "body": body or {}})

    def synthesize_media_tts(self, *, body=None):
        return BackendApiEnvelope(kind="media_tts", thread_id="thread-a", payload={"text": (body or {}).get("text", "")})

    def submit_artifact(self, *, body=None):
        return BackendApiEnvelope(kind="artifact_submission", thread_id="thread-a", payload={"body": body or {}})

    def persona(self):
        return BackendApiEnvelope(kind="persona_view", thread_id="thread-a", payload={"persona_state": {"mood": "focused"}})

    def worldline(self):
        return BackendApiEnvelope(kind="worldline_view", thread_id="thread-a", payload={"worldline_events": []})

    def bond(self):
        return BackendApiEnvelope(kind="bond_view", thread_id="thread-a", payload={"bond_state": {}})

    def sources(self):
        return BackendApiEnvelope(kind="sources_view", thread_id="thread-a", payload={"sources": []})

    def appraisal(self):
        return BackendApiEnvelope(kind="appraisal_view", thread_id="thread-a", payload={"turn_appraisal": {}})

    def behavior_queue(self, *, config=None):
        return BackendApiEnvelope(kind="behavior_queue_view", thread_id="thread-a", payload={"config": config or {}})

    def current_checkpoint(self, *, config=None):
        return BackendApiEnvelope(kind="current_checkpoint", thread_id="thread-a", payload={"config": config or {}})

    def checkpoint_history(self, *, limit=10, config=None):
        return BackendApiEnvelope(kind="checkpoint_history", thread_id="thread-a", payload={"limit": limit, "config": config or {}})

    def current_turn(self, *, config=None):
        self.current_turn_calls.append({"config": config})
        return BackendApiEnvelope(kind="assistant_turn", thread_id="thread-a", payload={"final_text": "真实当前回合"})

    def send_chat(self, *, message, config=None, meta=None):
        self.chat_calls.append({"message": message, "config": config, "meta": meta})
        return BackendApiEnvelope(
            kind="assistant_turn",
            thread_id="thread-a",
            payload={"final_text": f"reply:{message}"},
        )

    def build_turn_response(self, *, state_values, streamed_text="", meta=None):
        self.turn_calls.append({"state_values": state_values, "streamed_text": streamed_text, "meta": meta})
        return BackendApiEnvelope(kind="assistant_turn", thread_id="thread-a", payload={"final_text": "助手回合"})

    def build_event_round_response(self, *, state_values, final_text, meta=None):
        self.event_calls.append({"state_values": state_values, "final_text": final_text, "meta": meta})
        return BackendApiEnvelope(kind="event_round", thread_id="thread-a", payload={"final_text": final_text})


def test_transport_adapter_read_route_returns_backend_envelope_dict():
    adapter = BackendTransportAdapter(backend_api=_FakeBackendApi())

    response = adapter.handle("GET", "/api/persona-view")

    assert response["status"] == 200
    assert response["body"]["schema_version"] == "backend.v1"
    assert response["body"]["kind"] == "persona_view"
    assert response["body"]["payload"]["persona_state"]["mood"] == "focused"


def test_transport_adapter_turn_route_delegates_to_backend_api_without_schema_rebuild():
    api = _FakeBackendApi()
    adapter = BackendTransportAdapter(backend_api=api)

    response = adapter.handle(
        "POST",
        "/api/turns/finalize",
        body={"state_values": {"x": 1}, "streamed_text": "stream", "meta": {"transport": "test"}},
    )

    assert response["status"] == 200
    assert response["body"]["kind"] == "assistant_turn"
    assert api.turn_calls == [{"state_values": {"x": 1}, "streamed_text": "stream", "meta": {"transport": "test"}}]


def test_transport_adapter_current_turn_route_delegates_to_backend_api():
    api = _FakeBackendApi()
    adapter = BackendTransportAdapter(backend_api=api)

    response = adapter.handle("GET", "/api/turns/current")

    assert response["status"] == 200
    assert response["body"]["schema_version"] == "backend.v1"
    assert response["body"]["kind"] == "assistant_turn"
    assert response["body"]["payload"]["final_text"] == "真实当前回合"
    assert api.current_turn_calls == [{"config": None}]


def test_transport_adapter_chat_send_route_delegates_to_backend_api():
    api = _FakeBackendApi()
    adapter = BackendTransportAdapter(backend_api=api)

    response = adapter.handle(
        "POST",
        "/api/chat/send",
        body={
            "message": "  你好  ",
            "config": {"configurable": {"thread_id": "thread-a"}},
            "meta": {"client": "frontend"},
        },
    )

    assert response["status"] == 200
    assert response["body"]["schema_version"] == "backend.v1"
    assert response["body"]["kind"] == "assistant_turn"
    assert response["body"]["payload"]["final_text"] == "reply:你好"
    assert api.chat_calls == [
        {
            "message": "你好",
            "config": {"configurable": {"thread_id": "thread-a"}},
            "meta": {"client": "frontend"},
        }
    ]


def test_transport_adapter_chat_send_rejects_empty_message():
    api = _FakeBackendApi()
    adapter = BackendTransportAdapter(backend_api=api)

    response = adapter.handle("POST", "/api/chat/send", body={"message": "  "})

    assert response["status"] == 400
    assert response["body"]["error"]["code"] == "INVALID_CHAT_MESSAGE"
    assert response["body"]["error"]["path"] == "/api/chat/send"
    assert api.chat_calls == []


def test_transport_adapter_runtime_productization_route_delegates_to_backend_api():
    adapter = BackendTransportAdapter(backend_api=_FakeBackendApi())

    response = adapter.handle("GET", "/api/runtime-productization")

    assert response["status"] == 200
    assert response["body"]["kind"] == "runtime_productization"
    assert response["body"]["payload"]["readiness_status"] == "runtime_productization_phase1_ready"


def test_transport_adapter_operator_console_rc_route_delegates_to_backend_api():
    adapter = BackendTransportAdapter(backend_api=_FakeBackendApi())

    response = adapter.handle("GET", "/api/operator-console-rc")

    assert response["status"] == 200
    assert response["body"]["schema_version"] == "backend.v1"
    assert response["body"]["kind"] == "operator_console_rc"
    assert response["body"]["payload"]["readiness_status"] == "operator_console_rc_phase1_ready"


def test_transport_adapter_event_route_delegates_to_backend_api():
    api = _FakeBackendApi()
    adapter = BackendTransportAdapter(backend_api=api)

    response = adapter.handle("POST", "/api/event-rounds/finalize", body={"state_values": {}, "final_text": "我在。"})

    assert response["status"] == 200
    assert response["body"]["kind"] == "event_round"
    assert response["body"]["payload"]["final_text"] == "我在。"
    assert api.event_calls[0]["final_text"] == "我在。"


def test_transport_adapter_desktop_media_routes_delegate_to_backend_api():
    adapter = BackendTransportAdapter(backend_api=_FakeBackendApi())

    assert adapter.handle("GET", "/api/desktop/capabilities")["body"]["kind"] == "desktop_capabilities"
    assert adapter.handle("GET", "/api/media/session/current")["body"]["kind"] == "media_session"
    assert adapter.handle("POST", "/api/desktop/permissions/request", body={"permissions": ["microphone"]})["body"]["kind"] == "desktop_permission_state"
    assert adapter.handle("POST", "/api/media/session/start", body={"consent": True})["body"]["payload"]["status"] == "active"
    assert adapter.handle("POST", "/api/media/session/stop", body={"reason": "test"})["body"]["payload"]["status"] == "stopped"
    assert adapter.handle("POST", "/api/media/audio/input", body={"transcript": "hello"})["body"]["payload"]["modality"] == "audio"
    assert adapter.handle("POST", "/api/media/video/frame", body={"frame_digest": "x"})["body"]["payload"]["modality"] == "video"
    assert adapter.handle("POST", "/api/media/tts/synthesize", body={"text": "hello"})["body"]["kind"] == "media_tts"
    assert adapter.handle("POST", "/api/artifacts/submit", body={"content_digest": "x"})["body"]["kind"] == "artifact_submission"


def test_transport_adapter_unknown_route_is_structured_404():
    adapter = BackendTransportAdapter(backend_api=_FakeBackendApi())

    response = adapter.handle("GET", "/api/nope")

    assert response["status"] == 404
    assert response["body"]["error"]["code"] == "ROUTE_NOT_FOUND"
    assert response["body"]["error"]["path"] == "/api/nope"


def test_transport_adapter_rejects_wrong_method():
    adapter = BackendTransportAdapter(backend_api=_FakeBackendApi())

    response = adapter.handle("POST", "/api/persona-view")

    assert response["status"] == 405
    assert response["body"]["error"]["code"] == "METHOD_NOT_ALLOWED"

