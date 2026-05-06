from __future__ import annotations

from amadeus_thread0.graph_parts.capability_growth import (
    derive_workflow_candidate,
    summarize_workflow_candidate,
    workflow_candidate_to_planning_bias,
)


def test_repeated_completed_traces_form_workflow_candidate():
    candidate = derive_workflow_candidate(
        [
            {"trace_id": "p1", "status": "completed", "capability_family": "workspace", "confidence": 0.82},
            {"trace_id": "p2", "status": "completed", "capability_family": "workspace", "confidence": 0.88},
        ]
    )
    assert candidate["status"] == "candidate"
    assert candidate["capability_family"] == "workspace"
    assert candidate["recommended_next_action"] in {"reuse", "propose_skill"}
    assert candidate["origin_trace_ids"] == ["p1", "p2"]


def test_blocked_traces_cannot_become_capability_claim():
    candidate = derive_workflow_candidate(
        [{"trace_id": "p3", "status": "blocked", "capability_family": "sandbox", "confidence": 0.9}]
    )
    assert candidate["status"] == "blocked"
    assert "no_completed_evidence" in candidate["block_reasons"]


def test_workflow_candidate_to_planning_bias_preserves_approval():
    candidate = derive_workflow_candidate(
        [
            {"trace_id": "p1", "status": "completed", "capability_family": "sandbox", "confidence": 0.82},
            {"trace_id": "p2", "status": "completed", "capability_family": "sandbox", "confidence": 0.88},
        ]
    )
    bias = workflow_candidate_to_planning_bias(
        candidate,
        {"access_state": {"sandbox_state": {"runner_kind": "docker_isolated_runner"}}},
    )
    assert bias["planning_bias"] is True
    assert bias["requires_approval"] is True
    assert bias["capability_claim"] is False


def test_summarize_workflow_candidate_is_compact():
    candidate = derive_workflow_candidate(
        [
            {"trace_id": "p1", "status": "completed", "capability_family": "browser", "confidence": 0.82},
            {"trace_id": "p2", "status": "completed", "capability_family": "browser", "confidence": 0.88},
        ]
    )
    assert "browser" in summarize_workflow_candidate(candidate)
