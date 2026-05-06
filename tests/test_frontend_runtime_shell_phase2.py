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
        assert "RuntimeProductizationPayload" in content
        assert "operator_readback?: JsonRecord" in content
        assert "living_loop_realism?: JsonRecord" in content
        assert "embodied_interaction?: JsonRecord" in content


def test_frontend_phase2_client_exposes_route_transport_without_backend_semantic_ownership():
    client = _read("frontend/src/runtime/backendClient.ts")

    assert "BackendRouteTransport" in client
    assert "RouteBackendClient" in client
    assert 'schema_version !== "backend.v1"' in client
    assert "createSessionSnapshotFromEnvelopes" in client

    forbidden = ["memoryReducer", "personaReducer", "autonomyReducer", "digitalBodyReducer"]
    for term in forbidden:
        assert term not in client


def test_frontend_phase2_ui_renders_backend_owned_readback_blocks():
    app = _read("frontend/src/App.tsx")

    assert "Operator readback" in app
    assert "Living loop realism" in app
    assert "Embodied interaction" in app
    assert "Runtime productization" in app
    assert "session.transportMode" in app


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

