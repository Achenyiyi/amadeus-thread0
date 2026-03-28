from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_CONTRACT = REPO_ROOT / "docs" / "engineering" / "frontend_contract"
FRONTEND_CONTRACT = REPO_ROOT / "frontend" / "src"
MOCK_NAMES = [
    "assistant_turn.json",
    "event_round.json",
    "persona_view.json",
    "worldline_view.json",
    "bond_view.json",
]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_frontend_contract_types_stay_synced_with_docs_copy():
    docs_types = _read_text(DOC_CONTRACT / "backend_api.types.ts")
    frontend_types = _read_text(FRONTEND_CONTRACT / "contracts" / "backend.ts")
    assert frontend_types == docs_types


def test_frontend_mock_files_stay_synced_with_docs_copy():
    for name in MOCK_NAMES:
        docs_payload = _read_json(DOC_CONTRACT / "mocks" / name)
        frontend_payload = _read_json(FRONTEND_CONTRACT / "mocks" / name)
        assert frontend_payload == docs_payload, name


def test_frontend_contract_mocks_surface_embodied_and_autonomy_contract():
    assistant = _read_json(DOC_CONTRACT / "mocks" / "assistant_turn.json")
    event_round = _read_json(DOC_CONTRACT / "mocks" / "event_round.json")
    persona = _read_json(DOC_CONTRACT / "mocks" / "persona_view.json")
    worldline = _read_json(DOC_CONTRACT / "mocks" / "worldline_view.json")
    bond = _read_json(DOC_CONTRACT / "mocks" / "bond_view.json")

    assistant_payload = assistant["payload"]
    assistant_summary = assistant_payload["turn_summary"]
    assert assistant_summary["current_turn"]["behavior_action_embodied_context"]["kind"] == "access_request_pending"
    assert assistant_summary["current_turn"]["behavior_consequence_embodied_context"]["kind"] == "environmental_friction"
    assert assistant_summary["behavior_plan"]["embodied_context"]["kind"] == "access_request_pending"
    assert assistant_summary["behavior_consequence"]["embodied_context"]["kind"] == "environmental_friction"
    assert assistant_summary["event_residue"]["digital_body_consequence"]["kind"] == "access_request_pending"
    assert assistant_summary["autonomy"]["intent"]["mode"] == "proposal"
    assert assistant_summary["digital_body"]["access"]["mode"] == "approval_pending"
    assert assistant_summary["digital_body_consequence"]["kind"] == "access_request_pending"
    assert assistant_payload["behavior_action"]["embodied_context"]["kind"] == "access_request_pending"
    assert assistant_payload["behavior_plan"]["embodied_context"]["kind"] == "access_request_pending"
    assert assistant_payload["interaction_carryover"]["embodied_context"]["kind"] == "access_request_pending"
    assert assistant_payload["autonomy"]["pending_approval"]["proposal_id"] == "ap-approve-1"
    assert assistant_payload["digital_body"]["access"]["pending_approval_count"] == 1
    assert assistant_payload["digital_body_consequence"]["kind"] == "access_request_pending"
    assert assistant_payload["writeback_trace"]["revision_traces"][0]["embodied_context"]["kind"] == "access_request_pending"

    event_payload = event_round["payload"]
    event_summary = event_payload["turn_summary"]
    assert event_summary["current_turn"]["behavior_action_embodied_context"]["kind"] == "access_request_pending"
    assert event_summary["autonomy"]["intent"]["mode"] == "proposal"
    assert event_payload["autonomy"]["pending_approval"]["proposal_id"] == "ap-approve-1"
    assert event_payload["digital_body_consequence"]["kind"] == "access_request_pending"
    assert event_payload["writeback_trace"]["revision_traces"][0]["embodied_context"]["kind"] == "access_request_pending"

    persona_payload = persona["payload"]
    persona_summary = persona_payload["evolution_summary"]
    assert persona_summary["current_turn"]["behavior_action_embodied_context"]["kind"] == "access_request_pending"
    assert persona_summary["behavior_consequence"]["embodied_context"]["kind"] == "environmental_friction"
    assert persona_payload["behavior_action"]["embodied_context"]["kind"] == "access_request_pending"
    assert persona_payload["behavior_plan"]["embodied_context"]["kind"] == "access_request_pending"
    assert persona_payload["autonomy"]["intent"]["mode"] == "proposal"
    assert persona_payload["digital_body"]["access"]["mode"] == "approval_pending"
    assert persona_payload["digital_body_consequence"]["kind"] == "access_request_pending"

    worldline_payload = worldline["payload"]
    worldline_summary = worldline_payload["worldline_summary"]
    assert worldline_summary["current_turn"]["behavior_action_embodied_context"]["kind"] == "access_request_pending"
    assert worldline_summary["autonomy"]["intent"]["mode"] == "proposal"
    assert worldline_payload["autonomy"]["pending_approval"]["proposal_id"] == "ap-approve-1"
    assert worldline_payload["revision_traces"][0]["embodied_context"]["kind"] == "access_request_pending"
    assert worldline_payload["counterpart_assessment_preview"][0]["embodied_context"]["kind"] == "access_request_pending"
    assert worldline_payload["proactive_continuity_preview"][0]["embodied_context"]["kind"] == "access_request_pending"

    bond_payload = bond["payload"]
    assert bond_payload["autonomy"]["pending_approval"]["proposal_id"] == "ap-approve-1"
    assert bond_payload["counterpart_assessment_preview"][0]["embodied_context"]["kind"] == "access_request_pending"
    assert bond_payload["proactive_continuity_preview"][0]["embodied_context"]["kind"] == "access_request_pending"
