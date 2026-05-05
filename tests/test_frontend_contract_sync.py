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


def _require_path(row: dict, dotted_path: str):
    value = row
    for part in dotted_path.split("."):
        assert isinstance(value, dict), dotted_path
        assert part in value, dotted_path
        value = value[part]
    return value


def _assert_skills_contract(payload: dict) -> None:
    skills = _require_path(payload, "skills")
    assert isinstance(skills["active"], list)
    assert isinstance(skills["pending_approval"], dict)
    if skills["active"]:
        active = skills["active"][0]
        assert active["skill_id"] == "source-ref-anchor-review"
        assert "skill_excerpt" in active
    pending = skills["pending_approval"]
    assert pending["proposal_id"] == "ap-skill-install-1"
    assert pending["operation"] == "install"
    assert pending["skill_id"] == "workspace-regression-triage"
    assert pending["resolved_version"] == "1.1.0"
    assert pending["source"] == "official_registry"
    assert pending["hash"] == "sha256:contract-demo"
    assert pending["requested_permissions"] == ["filesystem_read"]
    assert pending["sandbox_profiles"] == ["workspace_read"]
    assert pending["verification_summary"] == "registry metadata verified"


def _assert_raw_body_contract(payload: dict) -> None:
    access_state = _require_path(payload, "digital_body.access_state")
    resource_state = _require_path(payload, "digital_body.resource_state")
    sandbox_state = access_state["sandbox_state"]
    browser_runtime_state = access_state["browser_runtime_state"]
    assert sandbox_state["runner_kind"] == "docker_isolated_runner"
    assert sandbox_state["isolation_level"] == "docker_local_isolated"
    assert sandbox_state["image_ref"] == "amadeus-thread0/sandbox-phase2:py312"
    assert sandbox_state["network_policy"] == "none"
    assert sandbox_state["workspace_root_kind"] == "runtime_owned"
    assert browser_runtime_state["runner_kind"] == "playwright_persistent_context"
    assert browser_runtime_state["isolation_level"] == "persistent_profile_runtime"
    assert resource_state["workspace_root"] == "E:/runtime/workspaces/contract-demo"


def _assert_summary_body_contract(summary: dict) -> None:
    access = _require_path(summary, "digital_body.access")
    resources = _require_path(summary, "digital_body.resources")
    sandbox_state = access["sandbox_state"]
    browser_runtime_state = access["browser_runtime_state"]
    assert sandbox_state["runner_kind"] == "docker_isolated_runner"
    assert sandbox_state["isolation_level"] == "docker_local_isolated"
    assert sandbox_state["image_ref"] == "amadeus-thread0/sandbox-phase2:py312"
    assert sandbox_state["network_policy"] == "none"
    assert sandbox_state["workspace_root_kind"] == "runtime_owned"
    assert browser_runtime_state["runner_kind"] == "playwright_persistent_context"
    assert browser_runtime_state["isolation_level"] == "persistent_profile_runtime"
    assert resources["workspace_root"] == "E:/runtime/workspaces/contract-demo"


def _assert_phase2_packet_contract(payload: dict) -> None:
    packet = payload["autonomy"]["action_packets"][0]
    pending = payload["autonomy"]["pending_approval"]
    for block in (packet["execution_spec"], packet["execution_preview"], pending["execution_preview"]):
        assert block["runner_kind"] == "docker_isolated_runner"
        assert block["isolation_level"] == "docker_local_isolated"
        assert block["image_ref"] == "amadeus-thread0/sandbox-phase2:py312"
        assert block["network_policy"] == "none"
        assert block["workspace_root_kind"] == "runtime_owned"
    assert packet["intent"] == "sandbox:execute_workspace_command"
    assert packet["risk"] == "external_mutation"
    assert packet["requires_approval"] is True
    assert packet["execution_result"]["status"] == "not_started"


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
    _assert_summary_body_contract(assistant_summary)
    assert assistant_summary["digital_body_consequence"]["kind"] == "access_request_pending"
    assert assistant_payload["behavior_action"]["embodied_context"]["kind"] == "access_request_pending"
    assert assistant_payload["behavior_plan"]["embodied_context"]["kind"] == "access_request_pending"
    assert assistant_payload["interaction_carryover"]["embodied_context"]["kind"] == "access_request_pending"
    assert assistant_payload["autonomy"]["pending_approval"]["proposal_id"] == "ap-approve-1"
    assert assistant_payload["digital_body"]["access_state"]["pending_approval_count"] == 1
    assert assistant_payload["digital_body_consequence"]["kind"] == "access_request_pending"
    assert assistant_payload["writeback_trace"]["revision_traces"][0]["embodied_context"]["kind"] == "access_request_pending"
    _assert_skills_contract(assistant_payload)
    _assert_raw_body_contract(assistant_payload)
    _assert_phase2_packet_contract(assistant_payload)

    event_payload = event_round["payload"]
    event_summary = event_payload["turn_summary"]
    assert event_summary["current_turn"]["behavior_action_embodied_context"]["kind"] == "access_request_pending"
    assert event_summary["autonomy"]["intent"]["mode"] == "proposal"
    _assert_summary_body_contract(event_summary)
    assert event_payload["autonomy"]["pending_approval"]["proposal_id"] == "ap-approve-1"
    assert event_payload["digital_body_consequence"]["kind"] == "access_request_pending"
    assert event_payload["writeback_trace"]["revision_traces"][0]["embodied_context"]["kind"] == "access_request_pending"
    _assert_skills_contract(event_payload)
    _assert_raw_body_contract(event_payload)
    _assert_phase2_packet_contract(event_payload)

    persona_payload = persona["payload"]
    persona_summary = persona_payload["evolution_summary"]
    assert persona_summary["current_turn"]["behavior_action_embodied_context"]["kind"] == "access_request_pending"
    assert persona_summary["behavior_consequence"]["embodied_context"]["kind"] == "environmental_friction"
    _assert_summary_body_contract(persona_summary)
    assert persona_payload["behavior_action"]["embodied_context"]["kind"] == "access_request_pending"
    assert persona_payload["behavior_plan"]["embodied_context"]["kind"] == "access_request_pending"
    assert persona_payload["autonomy"]["intent"]["mode"] == "proposal"
    assert persona_payload["digital_body"]["access_state"]["mode"] == "approval_pending"
    assert persona_payload["digital_body_consequence"]["kind"] == "access_request_pending"
    _assert_raw_body_contract(persona_payload)
    _assert_phase2_packet_contract(persona_payload)

    worldline_payload = worldline["payload"]
    worldline_summary = worldline_payload["worldline_summary"]
    assert worldline_summary["current_turn"]["behavior_action_embodied_context"]["kind"] == "access_request_pending"
    assert worldline_summary["autonomy"]["intent"]["mode"] == "proposal"
    _assert_summary_body_contract(worldline_summary)
    assert worldline_payload["autonomy"]["pending_approval"]["proposal_id"] == "ap-approve-1"
    assert worldline_payload["revision_traces"][0]["embodied_context"]["kind"] == "access_request_pending"
    assert worldline_payload["counterpart_assessment_preview"][0]["embodied_context"]["kind"] == "access_request_pending"
    assert worldline_payload["proactive_continuity_preview"][0]["embodied_context"]["kind"] == "access_request_pending"
    _assert_phase2_packet_contract(worldline_payload)

    bond_payload = bond["payload"]
    assert bond_payload["autonomy"]["pending_approval"]["proposal_id"] == "ap-approve-1"
    assert bond_payload["counterpart_assessment_preview"][0]["embodied_context"]["kind"] == "access_request_pending"
    assert bond_payload["proactive_continuity_preview"][0]["embodied_context"]["kind"] == "access_request_pending"
    _assert_phase2_packet_contract(bond_payload)
