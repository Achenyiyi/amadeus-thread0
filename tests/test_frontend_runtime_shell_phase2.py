from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_frontend_phase2_contract_types_include_live_readback_surfaces():
    types = _read("frontend/src/contracts/backend.ts")
    docs_types = _read("docs/engineering/frontend_contract/backend_api.types.ts")

    for content in (types, docs_types):
        assert '| "runtime_productization"' in content
        assert '| "operator_console_rc"' in content
        assert "RuntimeProductizationPayload" in content
        assert "OperatorConsoleRcPayload" in content
        assert "operator_readback?: JsonRecord" in content
        assert "living_loop_realism?: JsonRecord" in content
        assert "embodied_interaction?: JsonRecord" in content


def test_frontend_phase2_client_exposes_route_transport_without_backend_semantic_ownership():
    client = _read("frontend/src/runtime/backendClient.ts")

    assert "BackendRouteTransport" in client
    assert "RouteBackendClient" in client
    assert 'schema_version !== "backend.v1"' in client
    assert "createSessionSnapshotFromEnvelopes" in client
    assert '"/api/turns/current"' in client
    assert '"/api/checkpoints/current"' in client
    assert '"/api/checkpoints/history"' in client
    assert '"/api/operator-console-rc"' in client
    assert "route backend unavailable; using mock envelopes" not in client
    assert "loadMockSession()).transcript" not in client
    assert '"/api/chat/send"' in client
    assert "sendMessage(" in client
    assert 'method: "POST"' in client
    assert "requestEnvelopeWithRetry" in client
    assert "Promise.all([" not in client

    forbidden = ["memoryReducer", "personaReducer", "autonomyReducer", "digitalBodyReducer"]
    for term in forbidden:
        assert term not in client


def test_frontend_dev_server_proxies_api_to_local_backend_transport():
    vite_config = _read("frontend/vite.config.ts")
    package_json = _read("frontend/package.json")

    assert '"/api"' in vite_config
    assert '"http://127.0.0.1:4180"' in vite_config
    assert '"dev:live"' in package_json


def test_frontend_phase2_ui_renders_backend_owned_readback_blocks():
    app = _read("frontend/src/App.tsx")

    assert "Operator readback" in app
    assert "Living loop realism" in app
    assert "Embodied interaction" in app
    assert "Runtime productization" in app
    assert "Operator console RC" in app
    assert "session.transportMode" in app
    assert "onSubmit" in app
    assert "textarea" in app
    assert "Send" in app


def test_frontend_has_no_pending_fake_action_controls():
    app = _read("frontend/src/App.tsx")

    for term in (
        "Voice channel pending",
        "Artifact lane pending",
        "Approval bridge pending",
        "ToolRingButton",
        "Future action dock",
    ):
        assert term not in app


def test_frontend_archive_panel_consumes_checkpoint_route_envelopes():
    app = _read("frontend/src/App.tsx")
    data = _read("frontend/src/data/mockBackend.ts")

    assert "session.currentCheckpoint" in app
    assert "session.checkpointHistory" in app
    assert "Raw archive envelopes" in app
    assert "currentCheckpoint?: BackendEnvelopeFor<\"current_checkpoint\">" in data
    assert "checkpointHistory?: BackendEnvelopeFor<\"checkpoint_history\">" in data


def test_frontend_phase2_has_no_frontend_owned_semantic_modules():
    frontend_files = list((ROOT / "frontend" / "src").rglob("*"))
    forbidden_names = {
        "memoryReducer.ts",
        "personaReducer.ts",
        "autonomyReducer.ts",
        "digitalBodyReducer.ts",
        "memoryStore.ts",
        "personaStore.ts",
        "autonomyStore.ts",
        "digitalBodyStore.ts",
    }

    assert not {path.name for path in frontend_files} & forbidden_names

