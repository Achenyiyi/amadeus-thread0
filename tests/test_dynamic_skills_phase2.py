from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from amadeus_thread0.graph_parts.skill_runtime import (
    backend_skill_envelope,
    derive_procedural_continuity,
    derive_skill_effects,
)
from amadeus_thread0.runtime.dynamic_skill_candidates import (
    build_candidate_install_packet,
    freeze_skill_candidate_payload,
    propose_skill_candidate_from_trace,
    verify_candidate_approval,
)
from amadeus_thread0.runtime.skill_registry import SkillRegistryError, SkillRegistryManager
from amadeus_thread0.utils.tools import preview_skill_operation


def _candidate():
    return propose_skill_candidate_from_trace(
        {
            "trace_id": "trace-skill-1",
            "status": "completed",
            "summary": "Use rg to inspect pytest failures before editing.",
            "skill_id": "pytest-failure-review",
            "requested_permissions": ["filesystem_read", "filesystem_read"],
            "sandbox_profiles": ["docker_local_isolated"],
        }
    )


def test_candidate_freeze_preserves_hash_version_and_permissions():
    frozen = freeze_skill_candidate_payload(_candidate())
    packet = build_candidate_install_packet(frozen)
    verification = verify_candidate_approval(frozen, packet["tool_args"]["candidate_payload"])

    assert frozen["schema"] == "dynamic_skill_candidate.v1"
    assert frozen["status"] == "frozen"
    assert frozen["version"] == "0.1.0"
    assert frozen["requested_permissions"] == ["filesystem_read"]
    assert frozen["sandbox_profiles"] == ["docker_local_isolated"]
    assert frozen["hash"].startswith("sha256:")
    assert packet["intent"] == "skills:install"
    assert packet["status"] == "awaiting_approval"
    assert packet["risk"] == "external_mutation"
    assert packet["requires_approval"] is True
    assert packet["tool_args"]["candidate_id"] == frozen["candidate_id"]
    assert packet["tool_args"]["hash"] == frozen["hash"]
    assert verification["verified"] is True


def test_candidate_approval_detects_payload_drift():
    frozen = freeze_skill_candidate_payload(_candidate())
    drifted = {**frozen, "version": "9.9.9"}

    verification = verify_candidate_approval(frozen, drifted)

    assert verification["verified"] is False
    assert "version_drift" in verification["failure_reasons"]


def test_registry_installs_and_enables_exact_frozen_candidate():
    with tempfile.TemporaryDirectory() as tmp:
        manager = SkillRegistryManager(base_dir=Path(tmp) / "repo", data_dir=Path(tmp) / "data")
        frozen = freeze_skill_candidate_payload(_candidate())

        result = manager.install_candidate(frozen, frozen, thread_id="thread-dyn", enable=True)
        state = manager.compute_session_skill_state(thread_id="thread-dyn", query_text="pytest failures")
        lock_path = Path(tmp) / "data" / "skills" / "installed" / "pytest-failure-review" / "0.1.0" / "skill.lock.json"
        lock_payload = json.loads(lock_path.read_text(encoding="utf-8"))

        assert result["status"] == "installed"
        assert result["enabled"] is True
        assert result["hash"] == frozen["hash"]
        assert state["active_skill_ids"] == ["pytest-failure-review"]
        assert lock_payload["source"] == "dynamic_candidate"
        assert lock_payload["candidate_id"] == frozen["candidate_id"]


def test_registry_rejects_candidate_install_when_approval_payload_drifts():
    with tempfile.TemporaryDirectory() as tmp:
        manager = SkillRegistryManager(base_dir=Path(tmp) / "repo", data_dir=Path(tmp) / "data")
        frozen = freeze_skill_candidate_payload(_candidate())
        drifted = {**frozen, "hash": "sha256:" + "0" * 64}

        with pytest.raises(SkillRegistryError):
            manager.install_candidate(frozen, drifted, thread_id="thread-dyn", enable=True)

        assert manager.runtime_catalog() == []
        assert manager.compute_session_skill_state(thread_id="thread-dyn")["active_skill_ids"] == []


def test_pending_dynamic_candidate_proposal_surfaces_candidate_metadata_without_activation():
    frozen = freeze_skill_candidate_payload(_candidate())
    packet = build_candidate_install_packet(frozen)

    envelope = backend_skill_envelope(
        {"catalog_entries": [], "active_skill_entries": []},
        pending_action_proposal=packet,
    )

    assert envelope["active"] == []
    assert envelope["pending_approval"]["candidate_id"] == frozen["candidate_id"]
    assert envelope["pending_approval"]["candidate_hash"] == frozen["hash"]
    assert envelope["pending_approval"]["source"] == "dynamic_candidate"


def test_completed_dynamic_skill_use_resurfaces_only_after_actual_use():
    state = {
        "active_skill_entries": [
            {
                "skill_id": "pytest-failure-review",
                "name": "pytest-failure-review",
                "version": "0.1.0",
                "source": "dynamic_candidate",
                "trust_tier": "approved_candidate",
                "allowed_tools": ["execute_workspace_command"],
            }
        ]
    }
    effects = derive_skill_effects(
        state,
        [{"tool_name": "execute_workspace_command", "status": "completed", "proposal_id": "ap-use-1"}],
    )
    continuity = derive_procedural_continuity(
        {
            "kind": "skill_usage_completed",
            "primary_status": "completed",
            "primary_tool_name": "execute_workspace_command",
            "primary_proposal_id": "ap-use-1",
            "skill_effects": effects,
        }
    )

    assert effects[0]["operation"] == "use"
    assert effects[0]["source"] == "dynamic_candidate"
    assert continuity["capability_family"] == "skill"
    assert continuity["last_success_ref"] == "ap-use-1"


def test_dynamic_candidate_tool_preview_uses_frozen_payload_without_remote_catalog_lookup():
    frozen = freeze_skill_candidate_payload(_candidate())

    preview = preview_skill_operation("install_skill", {"candidate_payload": frozen})

    assert preview["resolved_args"]["skill_id"] == frozen["skill_id"]
    assert preview["resolved_args"]["candidate_id"] == frozen["candidate_id"]
    assert preview["skill_preview"]["source"] == "dynamic_candidate"
    assert preview["skill_preview"]["candidate_hash"] == frozen["hash"]
