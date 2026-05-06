from __future__ import annotations

from amadeus_thread0.graph_parts.action_packets import normalize_action_packet
from amadeus_thread0.runtime.artifact_perception_semantics import build_artifact_semantics_readback
from amadeus_thread0.runtime.embodied_interaction_runtime import build_embodied_interaction_readback
from amadeus_thread0.runtime.multimodal_sources import (
    build_multimodal_inspection_packet,
    normalize_multimodal_source,
)


def test_inspection_packet_requires_approval_and_never_auto_executes():
    source = normalize_multimodal_source(
        {
            "source_id": "img-inspect-1",
            "modality": "image",
            "path": "fixtures/panel.png",
            "consent_scope": "single_turn",
            "capture_method": "operator_attached_file",
            "label": "panel.png",
        }
    )

    packet = build_multimodal_inspection_packet(source, origin="counterpart_request")

    assert packet["intent"] == "artifact:inspect_multimodal"
    assert packet["status"] == "awaiting_approval"
    assert packet["risk"] == "external_mutation"
    assert packet["requires_approval"] is True
    assert packet["writeback_ready"] is False
    assert packet["proposal_id"].startswith("ap-")
    assert packet["tool_name"] == "inspect_multimodal_artifact"
    assert packet["multimodal_inspection_spec"]["source_ref_id"] == "img-inspect-1"
    assert packet["multimodal_inspection_spec"]["model_api_call_allowed"] is False
    assert packet["multimodal_inspection_spec"]["live_capture_allowed"] is False
    assert packet["multimodal_inspection_preview"]["auto_execute"] is False
    assert packet["multimodal_inspection_preview"]["model_api_call_planned"] is False
    assert packet["multimodal_inspection_preview"]["requires_approval"] is True


def test_blocked_live_capture_builds_blocked_packet_without_model_preview():
    source = normalize_multimodal_source(
        {
            "source_id": "mic-live-phase2",
            "modality": "audio",
            "artifact_ref": "live:microphone",
            "consent_scope": "single_turn",
            "capture_method": "background_microphone",
        }
    )

    packet = build_multimodal_inspection_packet(source, origin="counterpart_request")

    assert source["status"] == "blocked"
    assert packet["status"] == "blocked"
    assert packet["requires_approval"] is False
    assert packet["writeback_ready"] is False
    assert packet["block_reason"] == "blocked_capture_method"
    assert packet["multimodal_inspection_preview"]["blocked"] is True
    assert packet["multimodal_inspection_preview"]["auto_execute"] is False
    assert packet["multimodal_inspection_preview"]["model_api_call_planned"] is False


def test_action_packet_normalizer_preserves_multimodal_inspection_fields():
    source = normalize_multimodal_source(
        {
            "source_id": "screen-inspect-1",
            "modality": "screen",
            "path": "fixtures/screen.png",
            "consent_scope": "single_turn",
            "capture_method": "operator_attached_file",
        }
    )
    packet = build_multimodal_inspection_packet(source)

    normalized = normalize_action_packet(packet)

    assert normalized["multimodal_inspection_spec"]["source_ref_id"] == "screen-inspect-1"
    assert normalized["multimodal_inspection_preview"]["auto_execute"] is False
    assert normalized["multimodal_inspection_result"] == {}


def test_completed_approved_inspection_result_becomes_semantic_observation():
    readback = build_artifact_semantics_readback(
        [
            {
                "source_id": "img-approved-1",
                "modality": "image",
                "path": "fixtures/panel.png",
                "consent_scope": "single_turn",
                "capture_method": "operator_attached_file",
                "multimodal_inspection_result": {
                    "status": "completed",
                    "approval_status": "approved",
                    "source_ref_id": "img-approved-1",
                    "semantic_summary": "The panel shows a failed login message.",
                    "tags": ["login", "failure"],
                    "confidence": 0.83,
                },
            }
        ]
    )

    observation = readback["semantic_observations"][0]
    assert readback["status"] == "ready"
    assert observation["source"] == "approved_inspection_result"
    assert observation["source_ref_id"] == "img-approved-1"
    assert observation["summary"] == "The panel shows a failed login message."
    assert observation["model_api_called"] is False
    assert observation["writeback_ready"] is False


def test_pending_and_rejected_inspection_results_do_not_emit_semantics():
    readback = build_artifact_semantics_readback(
        [
            {
                "source_id": "img-pending",
                "modality": "image",
                "path": "fixtures/pending.png",
                "consent_scope": "single_turn",
                "capture_method": "operator_attached_file",
                "multimodal_inspection_result": {
                    "status": "awaiting_approval",
                    "approval_status": "pending",
                    "semantic_summary": "Should not be admitted.",
                },
            },
            {
                "source_id": "img-rejected",
                "modality": "image",
                "path": "fixtures/rejected.png",
                "consent_scope": "single_turn",
                "capture_method": "operator_attached_file",
                "multimodal_inspection_result": {
                    "status": "rejected",
                    "approval_status": "rejected",
                    "semantic_summary": "Should not be admitted.",
                },
            },
        ]
    )

    assert readback["status"] == "empty"
    assert readback["semantic_observations"] == []


def test_runtime_uses_completed_action_packet_inspection_result_as_semantics():
    source = normalize_multimodal_source(
        {
            "source_id": "img-runtime-inspection-1",
            "modality": "image",
            "path": "fixtures/task.png",
            "consent_scope": "single_turn",
            "capture_method": "operator_attached_file",
            "label": "task.png",
        }
    )
    packet = build_multimodal_inspection_packet(
        source,
        status="completed",
        approved_result={
            "semantic_summary": "A checklist is visible.",
            "tags": ["checklist"],
            "confidence": 0.8,
        },
    )
    readback = build_embodied_interaction_readback(
        {
            "final_text": "嗯，我看到了。",
            "current_event": {"digital_body_hints": {"multimodal_sources": [source]}},
            "action_packets": [packet],
            "reconsolidation_snapshot": {"final_text": "嗯，我看到了。"},
        }
    )

    assert readback["artifact_semantics"]["semantic_observations"][0]["source"] == "approved_inspection_result"
    assert (
        readback["current_event"]["perception"]["semantic_observations"][0]["source_ref_id"]
        == source["source_id"]
    )
