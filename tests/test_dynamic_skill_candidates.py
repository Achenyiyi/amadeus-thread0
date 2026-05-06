from __future__ import annotations

from amadeus_thread0.runtime.dynamic_skill_candidates import (
    build_skill_candidate_approval,
    propose_skill_candidate_from_trace,
    verify_candidate_hash,
)


def test_candidate_from_completed_procedural_trace_is_proposal_only():
    candidate = propose_skill_candidate_from_trace(
        {
            "trace_id": "proc-1",
            "kind": "workspace_procedure",
            "confidence": 0.91,
            "summary": "triage pytest failures with rg and pytest",
            "completed": True,
        }
    )
    assert candidate["status"] == "proposed"
    assert candidate["requires_approval"] is True
    assert candidate["registry_written"] is False
    assert candidate["hash"]


def test_pending_trace_cannot_become_skill_candidate():
    candidate = propose_skill_candidate_from_trace(
        {
            "trace_id": "proc-2",
            "kind": "workspace_procedure",
            "status": "pending_approval",
            "completed": False,
        }
    )
    assert candidate["status"] == "blocked"
    assert "not_completed_fact" in candidate["block_reasons"]


def test_approval_payload_contains_candidate_id_and_hash():
    candidate = propose_skill_candidate_from_trace(
        {
            "trace_id": "proc-3",
            "trace_kind": "workspace_procedure",
            "confidence": 0.88,
            "result_summary": "reuse rg then pytest triage",
            "completed": True,
        }
    )

    approval = build_skill_candidate_approval(candidate)

    assert approval["operation"] == "propose_candidate"
    assert approval["candidate_id"] == candidate["candidate_id"]
    assert approval["skill_id"] == candidate["skill_id"]
    assert approval["hash"] == candidate["hash"]
    assert approval["requires_approval"] is True


def test_candidate_hash_verification_detects_drift():
    candidate = propose_skill_candidate_from_trace(
        {
            "trace_id": "proc-4",
            "trace_kind": "workspace_procedure",
            "confidence": 0.88,
            "result_summary": "reuse source ref inspection",
            "completed": True,
        }
    )
    assert verify_candidate_hash(candidate)["verified"] is True
    drifted = {**candidate, "draft_skill_md": candidate["draft_skill_md"] + "\nextra"}
    assert verify_candidate_hash(drifted)["verified"] is False
