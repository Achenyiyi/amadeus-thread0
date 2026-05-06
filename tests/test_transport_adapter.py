from __future__ import annotations

from types import SimpleNamespace

from amadeus_thread0.runtime.backend_api import BackendApiEnvelope
from amadeus_thread0.runtime.transport_adapter import BackendTransportAdapter


class _FakeBackendApi:
    def __init__(self) -> None:
        self.turn_calls = []
        self.event_calls = []

    def thread_inventory(self):
        return BackendApiEnvelope(kind="thread_inventory", thread_id="thread-a", payload={"current_thread_id": "thread-a"})

    def runtime_layout(self):
        return BackendApiEnvelope(kind="runtime_layout", thread_id="thread-a", payload={"repo_runtime": {"ok": True}})

    def environment_summary(self):
        return BackendApiEnvelope(kind="environment_summary", thread_id="thread-a", payload={"runtime_mode": "regression"})

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


def test_transport_adapter_event_route_delegates_to_backend_api():
    api = _FakeBackendApi()
    adapter = BackendTransportAdapter(backend_api=api)

    response = adapter.handle("POST", "/api/event-rounds/finalize", body={"state_values": {}, "final_text": "我在。"})

    assert response["status"] == 200
    assert response["body"]["kind"] == "event_round"
    assert response["body"]["payload"]["final_text"] == "我在。"
    assert api.event_calls[0]["final_text"] == "我在。"


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

