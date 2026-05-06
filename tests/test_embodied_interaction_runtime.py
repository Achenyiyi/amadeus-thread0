from __future__ import annotations

from amadeus_thread0.runtime.embodied_interaction_runtime import (
    EMBODIED_INTERACTION_PHASE1_READINESS,
    build_embodied_interaction_readback,
    compact_embodied_interaction_line,
)
from amadeus_thread0.runtime.multimodal_sources import (
    build_multimodal_inspection_packet,
    normalize_multimodal_source,
)


def _turn_with_sources() -> dict:
    return {
        "final_text": "请问有什么可以帮你？",
        "current_event": {
            "kind": "multimodal_observation",
            "text": "panel.png",
            "digital_body_hints": {
                "multimodal_sources": [
                    {
                        "source_id": "img-runtime-1",
                        "modality": "image",
                        "path": "fixtures/panel.png",
                        "consent_scope": "single_turn",
                        "capture_method": "operator_attached_file",
                        "label": "panel.png",
                    }
                ]
            },
        },
        "digital_body": {
            "resource_state": {
                "artifact_continuity": "attached",
                "active_artifact_kind": "image",
                "active_artifact_ref": "fixtures/panel.png",
                "active_artifact_label": "panel.png",
            }
        },
        "interaction_carryover": {"embodied_context": {"kind": "multimodal_observation"}},
        "reconsolidation_snapshot": {"final_text": "请问有什么可以帮你？"},
    }


def test_readback_promotes_available_source_to_runtime_surfaces():
    readback = build_embodied_interaction_readback(_turn_with_sources())

    assert readback["schema"] == "embodied_interaction.runtime.v1"
    assert readback["readiness_status"] == EMBODIED_INTERACTION_PHASE1_READINESS
    assert readback["source_status"]["available_count"] == 1
    assert readback["current_event"]["perception_sources"][0]["source_ref_id"] == "img-runtime-1"
    assert readback["current_event"]["perception_sources"][0]["source_kind"] == "image_file"
    assert readback["digital_body"]["resource_state"]["multimodal_source_refs"] == ["img-runtime-1"]
    assert (
        readback["interaction_carryover"]["embodied_context"]["multimodal_sources"][0][
            "source_ref_id"
        ]
        == "img-runtime-1"
    )
    assert readback["authority_boundary"]["live_microphone_enabled"] is False
    assert readback["authority_boundary"]["live_camera_enabled"] is False


def test_blocked_live_capture_stays_blocked_and_not_written_as_available():
    turn = {
        "current_event": {
            "digital_body_hints": {
                "multimodal_sources": [
                    {
                        "source_id": "mic-live",
                        "modality": "audio",
                        "artifact_ref": "live:microphone",
                        "consent_scope": "single_turn",
                        "capture_method": "background_microphone",
                    }
                ]
            }
        }
    }

    readback = build_embodied_interaction_readback(turn)

    assert readback["overall_status"] == "in_progress"
    assert readback["readiness_status"] == "embodied_interaction_runtime_phase1_in_progress"
    assert readback["source_status"]["available_count"] == 0
    assert readback["source_status"]["blocked_count"] == 1
    assert readback["source_status"]["blocked_sources"][0]["source_ref_id"] == "mic-live"
    assert "blocked_capture_method" in readback["source_status"]["blocked_sources"][0]["block_reasons"]


def test_chinese_semantic_floor_updates_final_and_snapshot_text_together():
    readback = build_embodied_interaction_readback(_turn_with_sources())

    semantic = readback["chinese_semantic_surface"]
    assert semantic["status"] == "floor_rewritten"
    assert semantic["applied_floor"] is True
    assert semantic["runtime_final_text"] == "嗯，我在。你直接说吧，我会顺着这轮的语境接住。"
    assert readback["final_text"] == semantic["runtime_final_text"]
    assert readback["reconsolidation_snapshot"]["final_text"] == semantic["runtime_final_text"]


def test_chinese_semantic_surface_exposes_runtime_policy_envelope():
    readback = build_embodied_interaction_readback(
        {
            "final_text": "请问有什么可以帮你？",
            "reconsolidation_snapshot": {"final_text": "请问有什么可以帮你？"},
        }
    )

    policy = readback["chinese_semantic_surface"]["runtime_policy"]
    assert policy["readiness_status"] == "chinese_semantic_descaffolding_phase2_ready"
    assert policy["selected_policy"]["family"] == "generic_assistant_tone"
    assert policy["selected_policy"]["replacement_strategy"] == "deterministic_safe_surface_floor"
    assert readback["final_text"] == policy["runtime_final_text"]
    assert readback["reconsolidation_snapshot"]["final_text"] == policy["runtime_final_text"]
    assert readback["chinese_semantic_surface"]["tts_text"] == readback["final_text"]
    assert readback["chinese_semantic_surface"]["text_tts_drift"] is False


def test_no_sources_and_no_semantic_residue_remains_not_applicable_without_breaking_payloads():
    readback = build_embodied_interaction_readback(
        {
            "final_text": "嗯，我听见了。",
            "reconsolidation_snapshot": {"final_text": "嗯，我听见了。"},
        }
    )

    assert readback["overall_status"] == "not_applicable"
    assert readback["readiness_status"] == "embodied_interaction_runtime_phase1_not_applicable"
    assert readback["source_status"]["available_count"] == 0
    assert readback["chinese_semantic_surface"]["status"] == "no_semantic_residue"
    assert readback["final_text"] == "嗯，我听见了。"


def test_compact_line_names_sources_semantics_and_boundaries():
    line = compact_embodied_interaction_line(
        build_embodied_interaction_readback(_turn_with_sources())
    )

    assert "embodied_interaction=embodied_interaction_runtime_phase1_ready" in line
    assert "sources=1" in line
    assert "semantic_floor=floor_rewritten" in line
    assert "live_capture=false" in line


def test_artifact_semantics_reaches_perception_appraisal_and_carryover():
    turn = {
        "final_text": "嗯，我听见了。",
        "current_event": {
            "kind": "multimodal_observation",
            "perception": {"channel": "image"},
            "digital_body_hints": {
                "multimodal_sources": [
                    {
                        "source_id": "img-runtime-sem-1",
                        "modality": "image",
                        "path": "fixtures/login.png",
                        "consent_scope": "single_turn",
                        "capture_method": "operator_attached_file",
                        "semantic_summary": "A login dialog with an expired session warning.",
                        "semantic_label": "login_prompt",
                    }
                ]
            },
        },
        "turn_appraisal": {"scene": "artifact_review"},
        "interaction_carryover": {"embodied_context": {"kind": "multimodal_observation"}},
        "reconsolidation_snapshot": {"final_text": "嗯，我听见了。"},
    }

    readback = build_embodied_interaction_readback(turn)

    observation = readback["artifact_semantics"]["semantic_observations"][0]
    assert readback["readiness_status"] == "embodied_interaction_runtime_phase5_ready"
    assert (
        readback["artifact_semantics"]["readiness_status"]
        == "artifact_perception_semantics_ready"
    )
    assert observation["source_ref_id"] == "img-runtime-sem-1"
    assert (
        readback["current_event"]["perception"]["semantic_observations"][0]["source_ref_id"]
        == "img-runtime-sem-1"
    )
    assert readback["current_event"]["perception"]["channel"] == "image"
    assert (
        readback["turn_appraisal"]["perception_semantics"]["semantic_observations"][0][
            "source_ref_id"
        ]
        == "img-runtime-sem-1"
    )
    assert (
        readback["interaction_carryover"]["embodied_context"][
            "artifact_semantic_observations"
        ][0]["source_ref_id"]
        == "img-runtime-sem-1"
    )


def test_artifact_appraisal_evidence_reaches_appraisal_and_carryover_surfaces():
    turn = {
        "final_text": "嗯，我听见了。",
        "current_event": {
            "kind": "multimodal_observation",
            "perception": {"channel": "image"},
            "digital_body_hints": {
                "multimodal_sources": [
                    {
                        "source_id": "img-runtime-appraisal-1",
                        "modality": "image",
                        "path": "fixtures/login.png",
                        "consent_scope": "single_turn",
                        "capture_method": "operator_attached_file",
                        "semantic_summary": "A login dialog with an expired session warning.",
                        "semantic_label": "login_prompt",
                    }
                ]
            },
        },
        "turn_appraisal": {"scene": "artifact_review"},
        "interaction_carryover": {"embodied_context": {"kind": "multimodal_observation"}},
        "reconsolidation_snapshot": {"final_text": "嗯，我听见了。"},
    }

    readback = build_embodied_interaction_readback(turn)

    evidence = readback["artifact_appraisal"]["evidence_items"][0]
    assert readback["readiness_status"] == "embodied_interaction_runtime_phase5_ready"
    assert evidence["source_ref_id"] == "img-runtime-appraisal-1"
    assert evidence["suggested_appraisal_delta"]["access_friction"] is True
    assert (
        readback["current_event"]["perception"]["appraisal_evidence"][0]["source_ref_id"]
        == "img-runtime-appraisal-1"
    )
    assert (
        readback["turn_appraisal"]["artifact_evidence"][0]["source_ref_id"]
        == "img-runtime-appraisal-1"
    )
    assert (
        readback["turn_appraisal"]["perception_semantics"]["appraisal_evidence"][0][
            "source_ref_id"
        ]
        == "img-runtime-appraisal-1"
    )
    assert (
        readback["interaction_carryover"]["embodied_context"][
            "artifact_appraisal_evidence"
        ][0]["source_ref_id"]
        == "img-runtime-appraisal-1"
    )


def test_artifact_motive_hints_reach_readback_surfaces_without_replacing_behavior_motive():
    turn = {
        "final_text": "嗯，我听见了。",
        "current_event": {
            "kind": "multimodal_observation",
            "perception": {"channel": "image"},
            "digital_body_hints": {
                "multimodal_sources": [
                    {
                        "source_id": "img-runtime-motive-1",
                        "modality": "image",
                        "path": "fixtures/login.png",
                        "consent_scope": "single_turn",
                        "capture_method": "operator_attached_file",
                        "semantic_summary": "A login dialog with an expired session warning.",
                        "semantic_label": "login_prompt",
                    }
                ]
            },
        },
        "turn_appraisal": {"scene": "artifact_review"},
        "behavior_plan": {"primary_motive": "continue_workspace_task"},
        "interaction_carryover": {"embodied_context": {"kind": "multimodal_observation"}},
        "reconsolidation_snapshot": {"final_text": "嗯，我听见了。"},
    }

    readback = build_embodied_interaction_readback(turn)

    hint = readback["artifact_motive"]["motive_hints"][0]
    assert readback["readiness_status"] == "embodied_interaction_runtime_phase5_ready"
    assert hint["source_ref_id"] == "img-runtime-motive-1"
    assert hint["primary_motive_hint"] == "restore_access_continuity"
    assert (
        readback["current_event"]["perception"]["motive_hints"][0]["source_ref_id"]
        == "img-runtime-motive-1"
    )
    assert (
        readback["turn_appraisal"]["motive_evidence"][0]["source_ref_id"]
        == "img-runtime-motive-1"
    )
    assert (
        readback["turn_appraisal"]["perception_semantics"]["motive_hints"][0][
            "source_ref_id"
        ]
        == "img-runtime-motive-1"
    )
    assert (
        readback["interaction_carryover"]["embodied_context"]["artifact_motive_hints"][0][
            "source_ref_id"
        ]
        == "img-runtime-motive-1"
    )
    assert readback["behavior_plan"]["primary_motive"] == "continue_workspace_task"
    assert (
        readback["behavior_plan"]["artifact_motive_hints"][0]["primary_motive_hint"]
        == "restore_access_continuity"
    )


def test_artifact_behavior_alignment_reaches_readback_without_mutating_behavior_motive():
    turn = {
        "final_text": "嗯，我听见了。",
        "current_event": {
            "kind": "multimodal_observation",
            "perception": {"channel": "image"},
            "digital_body_hints": {
                "multimodal_sources": [
                    {
                        "source_id": "img-runtime-align-1",
                        "modality": "image",
                        "path": "fixtures/login.png",
                        "consent_scope": "single_turn",
                        "capture_method": "operator_attached_file",
                        "semantic_summary": "A login dialog with an expired session warning.",
                        "semantic_label": "login_prompt",
                    }
                ]
            },
        },
        "turn_appraisal": {"scene": "artifact_review"},
        "behavior_action": {"primary_motive": "continue_workspace_task"},
        "behavior_plan": {"primary_motive": "continue_workspace_task"},
        "interaction_carryover": {"embodied_context": {"kind": "multimodal_observation"}},
        "reconsolidation_snapshot": {"final_text": "嗯，我听见了。"},
    }

    readback = build_embodied_interaction_readback(turn)

    alignment = readback["artifact_behavior_alignment"]
    assert readback["readiness_status"] == "embodied_interaction_runtime_phase5_ready"
    assert alignment["readiness_status"] == "artifact_behavior_alignment_ready"
    assert alignment["alignment_items"][0]["alignment_status"] == "advisory_not_reflected"
    assert (
        readback["current_event"]["perception"]["behavior_alignment"]["alignment_items"][0][
            "source_ref_id"
        ]
        == "img-runtime-align-1"
    )
    assert (
        readback["turn_appraisal"]["behavior_alignment_evidence"]["alignment_items"][0][
            "source_ref_id"
        ]
        == "img-runtime-align-1"
    )
    assert (
        readback["turn_appraisal"]["perception_semantics"]["behavior_alignment"][
            "alignment_items"
        ][0]["source_ref_id"]
        == "img-runtime-align-1"
    )
    assert (
        readback["interaction_carryover"]["embodied_context"][
            "artifact_behavior_alignment"
        ]["alignment_items"][0]["source_ref_id"]
        == "img-runtime-align-1"
    )
    assert readback["behavior_plan"]["primary_motive"] == "continue_workspace_task"
    assert (
        readback["behavior_plan"]["artifact_behavior_alignment"]["alignment_summary"][
            "should_mutate_behavior"
        ]
        is False
    )


def test_completed_multimodal_inspection_packet_reaches_artifact_semantics_without_live_capture():
    source = normalize_multimodal_source(
        {
            "source_id": "img-runtime-approved-1",
            "modality": "image",
            "path": "fixtures/approved.png",
            "consent_scope": "single_turn",
            "capture_method": "operator_attached_file",
            "label": "approved.png",
        }
    )
    packet = build_multimodal_inspection_packet(
        source,
        status="completed",
        approved_result={
            "semantic_summary": "An approved fixture result says a checklist is visible.",
            "tags": ["checklist"],
            "confidence": 0.8,
        },
    )

    readback = build_embodied_interaction_readback(
        {
            "final_text": "嗯，我看到了。",
            "current_event": {"digital_body_hints": {"multimodal_sources": [source]}},
            "action_packets": [packet],
            "behavior_action": {"primary_motive": "continue_artifact_review"},
            "behavior_plan": {"primary_motive": "continue_artifact_review"},
            "interaction_carryover": {"embodied_context": {"kind": "multimodal_observation"}},
            "reconsolidation_snapshot": {"final_text": "嗯，我看到了。"},
        }
    )

    observation = readback["artifact_semantics"]["semantic_observations"][0]
    assert observation["source"] == "approved_inspection_result"
    assert observation["source_ref_id"] == "img-runtime-approved-1"
    assert observation["model_api_called"] is False
    assert readback["authority_boundary"]["live_microphone_enabled"] is False
    assert readback["authority_boundary"]["live_camera_enabled"] is False
    assert readback["authority_boundary"]["background_screen_capture_enabled"] is False
