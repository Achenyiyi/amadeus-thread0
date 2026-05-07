from __future__ import annotations

from amadeus_thread0.graph_parts.skill_runtime import derive_procedural_continuity, derive_skill_effects
from amadeus_thread0.runtime.dynamic_skill_candidate_runtime import (
    build_dynamic_skill_candidate_runtime_readback,
    compact_dynamic_skill_candidate_runtime_line,
)
from amadeus_thread0.runtime.dynamic_skill_candidates import (
    build_candidate_install_packet,
    freeze_skill_candidate_payload,
    propose_skill_candidate_from_trace,
)


def _candidate() -> dict:
    return propose_skill_candidate_from_trace(
        {
            "trace_id": "trace-runtime-candidate",
            "status": "completed",
            "summary": "Use rg to inspect pytest failures before editing.",
            "skill_id": "pytest-failure-review",
            "requested_permissions": ["filesystem_read"],
            "sandbox_profiles": ["docker_local_isolated"],
        }
    )


def _frozen_candidate() -> dict:
    return freeze_skill_candidate_payload(_candidate())


def _pending_packet() -> dict:
    return build_candidate_install_packet(_frozen_candidate())


def test_pending_candidate_is_visible_without_registry_write_or_activation():
    frozen = _frozen_candidate()
    packet = _pending_packet()

    readback = build_dynamic_skill_candidate_runtime_readback(
        {
            "autonomy": {"action_packets": [packet], "pending_approval": packet},
            "skills": {
                "installed": [],
                "active": [],
                "pending_approval": {
                    "operation": "install_skill",
                    "candidate_id": frozen["candidate_id"],
                    "candidate_hash": frozen["hash"],
                    "skill_id": frozen["skill_id"],
                    "source": "dynamic_candidate",
                },
            },
        }
    )

    assert readback["schema"] == "dynamic_skill_candidate_runtime.v1"
    assert readback["readiness_status"] == "dynamic_skill_candidate_runtime_phase1_ready"
    assert readback["summary"]["candidate_count"] == 1
    assert readback["summary"]["pending_approval_count"] == 1
    assert readback["summary"]["installed_count"] == 0
    assert readback["summary"]["active_count"] == 0
    candidate = readback["candidates"][0]
    assert candidate["candidate_id"] == frozen["candidate_id"]
    assert candidate["skill_id"] == frozen["skill_id"]
    assert candidate["candidate_state"] == "pending_approval"
    assert candidate["approval_state"] == "awaiting_approval"
    assert candidate["install_state"] == "not_installed"
    assert candidate["requires_approval"] is True
    assert candidate["registry_written"] is False
    assert candidate["active_after_install"] is False
    assert candidate["writeback_ready"] is False
    assert candidate["model_api_called"] is False
    assert candidate["memory_write_allowed"] is False
    assert readback["authority_boundary"]["registry_auto_write_allowed"] is False
    assert readback["authority_boundary"]["memory_write_allowed"] is False


def test_blocked_candidate_stays_visible_but_never_active_or_writeback_ready():
    frozen = _frozen_candidate()
    packet = _pending_packet()
    packet["status"] = "blocked"
    packet["block_reason"] = "operator rejected the capability mutation"

    readback = build_dynamic_skill_candidate_runtime_readback(
        {
            "autonomy": {"action_packets": [packet]},
            "skills": {"installed": [], "active": []},
        }
    )

    candidate = readback["candidates"][0]
    assert candidate["candidate_id"] == frozen["candidate_id"]
    assert candidate["candidate_state"] == "blocked"
    assert candidate["approval_state"] == "blocked"
    assert candidate["install_state"] == "blocked"
    assert candidate["active_after_install"] is False
    assert candidate["registry_written"] is False
    assert candidate["writeback_ready"] is False
    assert "blocked_candidate" in candidate["failure_reasons"]


def test_approved_install_readback_requires_installed_registry_evidence():
    frozen = _frozen_candidate()
    packet = _pending_packet()
    packet["status"] = "completed"
    packet["result_summary"] = "installed pytest-failure-review@0.1.0"
    packet["writeback_ready"] = True

    readback = build_dynamic_skill_candidate_runtime_readback(
        {
            "autonomy": {"action_packets": [packet]},
            "skills": {
                "installed": [
                    {
                        "skill_id": frozen["skill_id"],
                        "version": frozen["version"],
                        "source": "dynamic_candidate",
                        "hash": frozen["hash"],
                        "status": "installed",
                    }
                ],
                "active": [
                    {
                        "skill_id": frozen["skill_id"],
                        "version": frozen["version"],
                        "source": "dynamic_candidate",
                        "trust_tier": "approved_candidate",
                        "hash": frozen["hash"],
                    }
                ],
            },
            "digital_body_consequence": {
                "kind": "skill_install_completed",
                "primary_status": "completed",
                "primary_tool_name": "install_skill",
            },
        }
    )

    candidate = readback["candidates"][0]
    assert candidate["candidate_state"] == "installed_active"
    assert candidate["approval_state"] == "approved"
    assert candidate["install_state"] == "installed"
    assert candidate["registry_written"] is True
    assert candidate["active_after_install"] is True
    assert candidate["writeback_ready"] is True
    assert readback["summary"]["installed_count"] == 1
    assert readback["summary"]["active_count"] == 1


def test_completed_skill_use_is_the_only_path_to_procedural_continuity():
    frozen = _frozen_candidate()
    state = {
        "active_skill_entries": [
            {
                "skill_id": frozen["skill_id"],
                "name": frozen["skill_id"],
                "version": frozen["version"],
                "source": "dynamic_candidate",
                "trust_tier": "approved_candidate",
                "allowed_tools": ["execute_workspace_command"],
            }
        ]
    }
    effects = derive_skill_effects(
        state,
        [{"tool_name": "execute_workspace_command", "status": "completed", "proposal_id": "ap-use-runtime"}],
    )
    continuity = derive_procedural_continuity(
        {
            "kind": "skill_usage_completed",
            "primary_status": "completed",
            "primary_tool_name": "execute_workspace_command",
            "primary_proposal_id": "ap-use-runtime",
            "skill_effects": effects,
        }
    )

    readback = build_dynamic_skill_candidate_runtime_readback(
        {
            "skills": {
                "active": [
                    {
                        "skill_id": frozen["skill_id"],
                        "version": frozen["version"],
                        "source": "dynamic_candidate",
                        "trust_tier": "approved_candidate",
                    }
                ]
            },
            "digital_body_consequence": {
                "kind": "skill_usage_completed",
                "primary_status": "completed",
                "primary_tool_name": "execute_workspace_command",
                "skill_effects": effects,
                "procedural_continuity": continuity,
            },
        }
    )

    assert continuity["capability_family"] == "skill"
    assert readback["continuity"]["status"] == "completed_use_only"
    assert readback["continuity"]["capability_family"] == "skill"
    assert readback["continuity"]["identity_safe"] is True
    assert readback["authority_boundary"]["proposal_becomes_fact_allowed"] is False


def test_not_applicable_when_no_dynamic_candidate_signal_exists():
    readback = build_dynamic_skill_candidate_runtime_readback(
        {
            "skills": {"installed": [], "active": []},
            "autonomy": {"action_packets": []},
        }
    )

    assert readback["overall_status"] == "not_applicable"
    assert readback["readiness_status"] == "dynamic_skill_candidate_runtime_phase1_not_applicable"
    assert readback["summary"]["candidate_count"] == 0
    assert compact_dynamic_skill_candidate_runtime_line(readback)

