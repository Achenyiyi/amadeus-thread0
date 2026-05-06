from __future__ import annotations

from amadeus_thread0.runtime.dynamic_skill_candidates import (
    build_candidate_install_packet,
    freeze_skill_candidate_payload,
    propose_skill_candidate_from_trace,
    verify_candidate_approval,
)


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
