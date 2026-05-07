from __future__ import annotations

from copy import deepcopy

from amadeus_thread0.runtime.approved_artifact_multimodal_runtime import (
    APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_IN_PROGRESS,
    APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_READY,
    apply_approved_artifact_multimodal_runtime_to_payload,
    build_approved_artifact_multimodal_runtime_readback,
    compact_approved_artifact_multimodal_runtime_line,
)
from amadeus_thread0.runtime.embodied_interaction_runtime import (
    build_embodied_interaction_readback,
)
from amadeus_thread0.runtime.multimodal_sources import (
    build_multimodal_inspection_packet,
    normalize_multimodal_source,
)


def _source(source_id: str = "img-approved-runtime-1") -> dict:
    return normalize_multimodal_source(
        {
            "source_id": source_id,
            "modality": "image",
            "path": f"fixtures/{source_id}.png",
            "consent_scope": "single_turn",
            "capture_method": "operator_attached_file",
            "label": f"{source_id}.png",
        }
    )


def _approved_result(source_id: str = "img-approved-runtime-1") -> dict:
    return {
        "source_ref_id": source_id,
        "semantic_summary": "The approved result says a checklist is visible.",
        "tags": ["checklist"],
        "confidence": 0.84,
    }


def test_exact_approved_result_completes_frozen_packet_and_feeds_embodied_semantics():
    source = _source()
    pending = build_multimodal_inspection_packet(source)

    readback = build_approved_artifact_multimodal_runtime_readback(
        pending,
        approval={
            "proposal_id": pending["proposal_id"],
            "approval_status": "approved",
        },
        approved_result=_approved_result(),
    )

    completed = readback["completed_packet"]
    result = completed["multimodal_inspection_result"]
    boundary = readback["authority_boundary"]
    assert readback["schema"] == "approved_artifact_multimodal_runtime.v1"
    assert readback["overall_status"] == "passed"
    assert readback["readiness_status"] == APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_READY
    assert completed["proposal_id"] == pending["proposal_id"]
    assert completed["status"] == "completed"
    assert completed["requires_approval"] is False
    assert completed["writeback_ready"] is True
    assert result["source"] == "approved_inspection_result"
    assert result["source_ref_id"] == "img-approved-runtime-1"
    assert result["semantic_summary"] == "The approved result says a checklist is visible."
    assert result["model_api_called"] is False
    assert boundary["multimodal_model_api_called"] is False
    assert boundary["live_capture_allowed"] is False
    assert boundary["memory_write_allowed"] is False
    assert boundary["external_mutation_allowed"] is False

    embodied = build_embodied_interaction_readback(
        {
            "final_text": "嗯，我看到了。",
            "current_event": {"digital_body_hints": {"multimodal_sources": [source]}},
            "action_packets": [completed],
            "behavior_action": {"primary_motive": "continue_artifact_review"},
            "behavior_plan": {"primary_motive": "continue_artifact_review"},
            "interaction_carryover": {"embodied_context": {"kind": "multimodal_observation"}},
            "reconsolidation_snapshot": {"final_text": "嗯，我看到了。"},
        }
    )
    observations = embodied["artifact_semantics"]["semantic_observations"]
    assert len(observations) == 1
    assert observations[0]["source"] == "approved_inspection_result"
    assert observations[0]["source_ref_id"] == "img-approved-runtime-1"


def test_source_drift_rejects_result_without_completed_packet_or_semantics():
    source = _source()
    pending = build_multimodal_inspection_packet(source)

    readback = build_approved_artifact_multimodal_runtime_readback(
        pending,
        approval={
            "proposal_id": pending["proposal_id"],
            "approval_status": "approved",
        },
        approved_result={
            **_approved_result("img-different-source"),
            "artifact_ref": "fixtures/img-different-source.png",
        },
    )

    assert readback["overall_status"] == "in_progress"
    assert readback["readiness_status"] == APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_IN_PROGRESS
    assert readback["completed_packet"] == {}
    assert "source_ref_id_drift" in readback["failure_reasons"]

    embodied = build_embodied_interaction_readback(
        {
            "current_event": {"digital_body_hints": {"multimodal_sources": [source]}},
            "action_packets": [pending],
        }
    )
    assert embodied["artifact_semantics"]["semantic_observations"] == []


def test_approval_proposal_drift_rejects_result_without_mutating_packet():
    source = _source()
    pending = build_multimodal_inspection_packet(source)

    readback = build_approved_artifact_multimodal_runtime_readback(
        pending,
        approval={
            "proposal_id": "ap-not-the-frozen-packet",
            "approval_status": "approved",
        },
        approved_result=_approved_result(),
    )

    assert readback["overall_status"] == "in_progress"
    assert readback["completed_packet"] == {}
    assert "approval_proposal_id_drift" in readback["failure_reasons"]


def test_model_api_or_live_capture_result_is_rejected_fail_closed():
    source = _source()
    pending = build_multimodal_inspection_packet(source)

    model_called = build_approved_artifact_multimodal_runtime_readback(
        pending,
        approval={
            "proposal_id": pending["proposal_id"],
            "approval_status": "approved",
        },
        approved_result={**_approved_result(), "model_api_called": True},
    )
    live_capture = build_approved_artifact_multimodal_runtime_readback(
        pending,
        approval={
            "proposal_id": pending["proposal_id"],
            "approval_status": "approved",
        },
        approved_result={**_approved_result(), "live_capture_used": True},
    )

    assert model_called["completed_packet"] == {}
    assert live_capture["completed_packet"] == {}
    assert "model_api_called_not_allowed" in model_called["failure_reasons"]
    assert "live_capture_used_not_allowed" in live_capture["failure_reasons"]
    assert model_called["authority_boundary"]["multimodal_model_api_called"] is False
    assert live_capture["authority_boundary"]["live_capture_allowed"] is False


def test_payload_application_completes_matching_packet_and_preserves_original_payload():
    source = _source()
    pending = build_multimodal_inspection_packet(source)
    payload = {
        "kind": "assistant_turn",
        "final_text": "嗯，我看到了。",
        "current_event": {"digital_body_hints": {"multimodal_sources": [source]}},
        "action_packets": [pending],
        "reconsolidation_snapshot": {"final_text": "嗯，我看到了。"},
    }
    before = deepcopy(payload)

    updated = apply_approved_artifact_multimodal_runtime_to_payload(
        payload,
        approvals=[
            {
                "proposal_id": pending["proposal_id"],
                "approval_status": "approved",
            }
        ],
        approved_results=[
            {
                "proposal_id": pending["proposal_id"],
                **_approved_result(),
            }
        ],
    )

    assert payload == before
    assert updated["action_packets"][0]["status"] == "completed"
    assert updated["action_packets"][0]["writeback_ready"] is True
    readback = updated["approved_artifact_multimodal_runtime"]
    assert readback["readiness_status"] == APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_READY
    assert readback["summary"]["completed_count"] == 1
    assert readback["summary"]["failed_count"] == 0
    line = compact_approved_artifact_multimodal_runtime_line(readback)
    assert (
        "approved_artifact_multimodal=approved_artifact_multimodal_runtime_phase1_ready"
        in line
    )
    assert "completed=1" in line
