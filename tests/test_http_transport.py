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
        self.history_calls = []

    def runtime_productization(self):
        return BackendApiEnvelope(
            kind="runtime_productization",
            thread_id="thread-http",
            payload={"readiness_status": "runtime_productization_phase3_ready"},
        )

    def checkpoint_history(self, *, limit=10, config=None):
        self.history_calls.append({"limit": limit, "config": config})
        return BackendApiEnvelope(
            kind="checkpoint_history",
            thread_id="thread-http",
            payload={"limit": limit, "config": config or {}},
        )

    def build_turn_response(self, *, state_values, streamed_text="", meta=None):
        self.turn_calls.append({"state_values": state_values, "streamed_text": streamed_text, "meta": meta})
        return BackendApiEnvelope(
            kind="assistant_turn",
            thread_id="thread-http",
            payload={"final_text": streamed_text, "state_values": state_values},
        )


def test_wsgi_get_route_returns_backend_v1_envelope():
    app = create_http_transport_app(_FakeBackendApi())

    response = call_wsgi_app(app, "GET", "/api/runtime-productization")

    assert response["status"] == 200
    assert response["headers"]["content-type"] == "application/json; charset=utf-8"
    assert response["body"]["schema_version"] == "backend.v1"
    assert response["body"]["kind"] == "runtime_productization"
    assert response["body"]["payload"]["readiness_status"] == "runtime_productization_phase3_ready"


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
