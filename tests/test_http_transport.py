from __future__ import annotations

from amadeus_thread0.runtime.backend_api import BackendApiEnvelope
from amadeus_thread0.runtime.http_transport import (
    HTTP_TRANSPORT_AUTHORITY_BOUNDARY,
    build_wsgi_app,
    call_wsgi_app,
    create_http_transport_app,
)
from amadeus_thread0.runtime.transport_adapter import BackendTransportAdapter


class _FakeBackendApi:
    def __init__(self) -> None:
        self.turn_calls = []
        self.chat_calls = []
        self.current_turn_calls = []
        self.history_calls = []

    def runtime_productization(self):
        return BackendApiEnvelope(
            kind="runtime_productization",
            thread_id="thread-http",
            payload={"readiness_status": "runtime_productization_phase3_ready"},
        )

    def operator_console_rc(self):
        return BackendApiEnvelope(
            kind="operator_console_rc",
            thread_id="thread-http",
            payload={"readiness_status": "operator_console_rc_phase1_ready"},
        )

    def desktop_capabilities(self):
        return BackendApiEnvelope(
            kind="desktop_capabilities",
            thread_id="thread-http",
            payload={"schema": "desktop_live_capture.v1"},
        )

    def request_desktop_permissions(self, *, body=None):
        return BackendApiEnvelope(
            kind="desktop_permission_state",
            thread_id="thread-http",
            payload={"requested": body.get("permissions", []) if isinstance(body, dict) else []},
        )

    def current_media_session(self):
        return BackendApiEnvelope(kind="media_session", thread_id="thread-http", payload={"status": "stopped"})

    def start_media_session(self, *, body=None):
        return BackendApiEnvelope(kind="media_session", thread_id="thread-http", payload={"status": "active", "body": body or {}})

    def stop_media_session(self, *, body=None):
        return BackendApiEnvelope(kind="media_session", thread_id="thread-http", payload={"status": "stopped", "body": body or {}})

    def submit_media_audio(self, *, body=None):
        return BackendApiEnvelope(kind="media_turn", thread_id="thread-http", payload={"modality": "audio", "body": body or {}})

    def submit_media_video_frame(self, *, body=None):
        return BackendApiEnvelope(kind="media_turn", thread_id="thread-http", payload={"modality": "video", "body": body or {}})

    def synthesize_media_tts(self, *, body=None):
        return BackendApiEnvelope(kind="media_tts", thread_id="thread-http", payload={"text": (body or {}).get("text", "")})

    def submit_artifact(self, *, body=None):
        return BackendApiEnvelope(kind="artifact_submission", thread_id="thread-http", payload={"body": body or {}})

    def checkpoint_history(self, *, limit=10, config=None):
        self.history_calls.append({"limit": limit, "config": config})
        return BackendApiEnvelope(
            kind="checkpoint_history",
            thread_id="thread-http",
            payload={"limit": limit, "config": config or {}},
        )

    def current_turn(self, *, config=None):
        self.current_turn_calls.append({"config": config})
        return BackendApiEnvelope(
            kind="assistant_turn",
            thread_id="thread-http",
            payload={"final_text": "http current turn"},
        )

    def send_chat(self, *, message, config=None, meta=None):
        self.chat_calls.append({"message": message, "config": config, "meta": meta})
        return BackendApiEnvelope(
            kind="assistant_turn",
            thread_id="thread-http",
            payload={"final_text": f"http reply:{message}"},
        )

    def build_turn_response(self, *, state_values, streamed_text="", meta=None):
        self.turn_calls.append({"state_values": state_values, "streamed_text": streamed_text, "meta": meta})
        return BackendApiEnvelope(
            kind="assistant_turn",
            thread_id="thread-http",
            payload={"final_text": streamed_text, "state_values": state_values},
        )


class _FailingBackendApi(_FakeBackendApi):
    def send_chat(self, *, message, config=None, meta=None):
        raise RuntimeError("model backend unavailable")


def test_wsgi_get_route_returns_backend_v1_envelope():
    app = create_http_transport_app(_FakeBackendApi())

    response = call_wsgi_app(app, "GET", "/api/runtime-productization")

    assert response["status"] == 200
    assert response["headers"]["content-type"] == "application/json; charset=utf-8"
    assert response["body"]["schema_version"] == "backend.v1"
    assert response["body"]["kind"] == "runtime_productization"
    assert response["body"]["payload"]["readiness_status"] == "runtime_productization_phase3_ready"


def test_wsgi_operator_console_rc_route_returns_backend_v1_envelope():
    app = create_http_transport_app(_FakeBackendApi())

    response = call_wsgi_app(app, "GET", "/api/operator-console-rc")

    assert response["status"] == 200
    assert response["body"]["schema_version"] == "backend.v1"
    assert response["body"]["kind"] == "operator_console_rc"
    assert response["body"]["payload"]["readiness_status"] == "operator_console_rc_phase1_ready"


def test_wsgi_current_turn_route_returns_backend_v1_assistant_turn():
    api = _FakeBackendApi()
    app = create_http_transport_app(api)

    response = call_wsgi_app(app, "GET", "/api/turns/current")

    assert response["status"] == 200
    assert response["body"]["schema_version"] == "backend.v1"
    assert response["body"]["kind"] == "assistant_turn"
    assert response["body"]["payload"]["final_text"] == "http current turn"
    assert api.current_turn_calls == [{"config": None}]


def test_wsgi_chat_send_route_returns_backend_v1_assistant_turn():
    api = _FakeBackendApi()
    app = create_http_transport_app(api)

    response = call_wsgi_app(
        app,
        "POST",
        "/api/chat/send",
        body={
            "message": "  hello  ",
            "config": {"configurable": {"thread_id": "thread-http"}},
            "meta": {"client": "frontend_runtime_shell"},
        },
    )

    assert response["status"] == 200
    assert response["body"]["schema_version"] == "backend.v1"
    assert response["body"]["kind"] == "assistant_turn"
    assert response["body"]["payload"]["final_text"] == "http reply:hello"
    assert api.chat_calls == [
        {
            "message": "hello",
            "config": {"configurable": {"thread_id": "thread-http"}},
            "meta": {"client": "frontend_runtime_shell"},
        }
    ]


def test_wsgi_chat_send_rejects_empty_message():
    api = _FakeBackendApi()
    app = create_http_transport_app(api)

    response = call_wsgi_app(app, "POST", "/api/chat/send", body={"message": ""})

    assert response["status"] == 400
    assert response["body"]["error"]["code"] == "INVALID_CHAT_MESSAGE"
    assert api.chat_calls == []


def test_wsgi_desktop_media_routes_return_backend_v1_envelopes():
    app = create_http_transport_app(_FakeBackendApi())

    routes = [
        ("GET", "/api/desktop/capabilities", None, "desktop_capabilities"),
        ("GET", "/api/media/session/current", None, "media_session"),
        ("POST", "/api/desktop/permissions/request", {"permissions": ["microphone"]}, "desktop_permission_state"),
        ("POST", "/api/media/session/start", {"consent": True}, "media_session"),
        ("POST", "/api/media/session/stop", {"reason": "test"}, "media_session"),
        ("POST", "/api/media/audio/input", {"transcript": "hello"}, "media_turn"),
        ("POST", "/api/media/video/frame", {"frame_digest": "x"}, "media_turn"),
        ("POST", "/api/media/tts/synthesize", {"text": "hello"}, "media_tts"),
        ("POST", "/api/artifacts/submit", {"content_digest": "x"}, "artifact_submission"),
    ]
    for method, route, body, kind in routes:
        response = call_wsgi_app(app, method, route, body=body)
        assert response["status"] == 200, route
        assert response["body"]["schema_version"] == "backend.v1", route
        assert response["body"]["kind"] == kind, route


def test_wsgi_runtime_exception_returns_structured_500():
    app = create_http_transport_app(_FailingBackendApi())

    response = call_wsgi_app(app, "POST", "/api/chat/send", body={"message": "hello"})

    assert response["status"] == 500
    assert response["body"]["error"]["code"] == "BACKEND_RUNTIME_ERROR"
    assert "model backend unavailable" in response["body"]["error"]["message"]


def test_wsgi_post_route_forwards_json_body_without_rebuilding_schema():
    api = _FakeBackendApi()
    app = create_http_transport_app(api)

    response = call_wsgi_app(
        app,
        "POST",
        "/api/turns/finalize",
        body={"state_values": {"x": 1}, "streamed_text": "hello", "meta": {"via": "http"}},
    )

    assert response["status"] == 200
    assert response["body"]["kind"] == "assistant_turn"
    assert response["body"]["payload"]["final_text"] == "hello"
    assert api.turn_calls == [{"state_values": {"x": 1}, "streamed_text": "hello", "meta": {"via": "http"}}]


def test_wsgi_query_string_is_decoded_for_adapter_query():
    api = _FakeBackendApi()
    app = build_wsgi_app(BackendTransportAdapter(api))

    response = call_wsgi_app(app, "GET", "/api/checkpoints/history", query_string="limit=2")

    assert response["status"] == 200
    assert response["body"]["payload"]["limit"] == 2
    assert api.history_calls == [{"limit": 2, "config": None}]


def test_wsgi_invalid_json_returns_structured_400_without_calling_adapter():
    api = _FakeBackendApi()
    app = create_http_transport_app(api)

    response = call_wsgi_app(app, "POST", "/api/turns/finalize", raw_body=b"{bad json")

    assert response["status"] == 400
    assert response["body"]["error"]["code"] == "INVALID_JSON"
    assert api.turn_calls == []


def test_wsgi_wrapper_exposes_closed_authority_boundary():
    assert HTTP_TRANSPORT_AUTHORITY_BOUNDARY["transport_role"] == "thin_wrapper"
    assert HTTP_TRANSPORT_AUTHORITY_BOUNDARY["backend_semantics_owner"] is False
    assert HTTP_TRANSPORT_AUTHORITY_BOUNDARY["memory_write_authority"] is False
    assert HTTP_TRANSPORT_AUTHORITY_BOUNDARY["frontend_semantics_owner"] is False
    assert HTTP_TRANSPORT_AUTHORITY_BOUNDARY["sse_or_websocket_streaming_enabled"] is False


def test_http_dev_server_module_builds_wsgi_app_from_runtime_bundle(monkeypatch, tmp_path):
    from amadeus_thread0.runtime import http_dev_server

    calls = []

    class FakeBundle:
        thread_id = "thread-dev"

        def backend_api(self, *, base_data_dir, cwd=None):
            calls.append({"base_data_dir": base_data_dir, "cwd": cwd})
            return _FakeBackendApi()

    monkeypatch.setattr(http_dev_server.RuntimeBundle, "create", lambda *, thread_id, settings: FakeBundle())

    app, bundle = http_dev_server.create_dev_server_app(thread_id="thread-dev", base_data_dir=tmp_path, cwd=tmp_path)

    response = call_wsgi_app(app, "POST", "/api/chat/send", body={"message": "ping"})
    assert bundle.thread_id == "thread-dev"
    assert response["status"] == 200
    assert response["body"]["kind"] == "assistant_turn"
    assert response["body"]["payload"]["final_text"] == "http reply:ping"
    assert calls == [{"base_data_dir": tmp_path, "cwd": tmp_path}]


def test_http_dev_server_uses_threaded_wsgi_server_for_parallel_frontend_bootstrap():
    from amadeus_thread0.runtime import http_dev_server

    assert http_dev_server.ThreadedWsgiServer.daemon_threads is True
    assert hasattr(http_dev_server.ThreadedWsgiServer, "process_request_thread")
