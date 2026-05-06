from __future__ import annotations

from amadeus_thread0.runtime.embodied_interaction_runtime import (
    EMBODIED_INTERACTION_PHASE1_READINESS,
    build_embodied_interaction_readback,
    compact_embodied_interaction_line,
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
