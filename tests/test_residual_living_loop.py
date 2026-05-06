from __future__ import annotations

from amadeus_thread0.runtime.residual_living_loop import (
    RESIDUAL_LIVING_LOOP_PHASE1_READINESS,
    build_residual_living_loop_readback,
    compact_residual_living_loop_line,
    evaluate_living_loop_trace,
)


def _complete_turn() -> dict:
    return {
        "current_event": {
            "kind": "user_message",
            "perception": {"modality": "text"},
            "digital_body_hints": {"artifact_carrier": "multimodal_source"},
        },
        "turn_appraisal": {"scene": "repair", "confidence": 0.84},
        "emotion_state": {"label": "guarded"},
        "bond_state": {"trust": 0.58},
        "allostasis_state": {"autonomy_need": 0.62},
        "behavior_action": {"primary_motive": "repair_without_erasing_boundary"},
        "behavior_plan": {"action_family": "low_pressure_support"},
        "digital_body_consequence": {"kind": "source_material_inspected"},
        "reconsolidation_snapshot": {
            "behavior_action": {"primary_motive": "repair_without_erasing_boundary"},
            "digital_body_consequence": {"kind": "source_material_inspected"},
        },
        "writeback_trace": {
            "revision_traces": [{"namespace": "semantic_self_evidence"}],
            "counterpart_assessment_history": [{"stance": "watchful"}],
        },
        "semantic_narrative_profile": {"continuity_axes": [{"category": "repair_style"}]},
        "skills": {"pending_approval": None, "active": []},
        "autonomy": {"action_packets": []},
    }


def test_living_loop_trace_passes_when_all_north_star_stages_are_visible():
    trace = evaluate_living_loop_trace(_complete_turn())

    assert trace["status"] == "ready"
    assert trace["ready_stage_count"] == 8
    assert trace["missing_stages"] == []


def test_living_loop_trace_fails_when_writeback_is_missing():
    turn = _complete_turn()
    turn.pop("writeback_trace")

    trace = evaluate_living_loop_trace(turn)

    assert trace["status"] == "incomplete"
    assert "memory_reconsolidation" in trace["missing_stages"]


def test_residual_readback_closes_without_widening_authority():
    readback = build_residual_living_loop_readback(current_turn=_complete_turn())

    assert readback["readiness_status"] == RESIDUAL_LIVING_LOOP_PHASE1_READINESS
    assert readback["authority_boundary"]["live_capture_enabled"] is False
    assert readback["authority_boundary"]["auto_skill_registry_write"] is False
    assert readback["authority_boundary"]["external_harness_auto_enabled"] is False
    assert readback["residuals"]["chinese_semantic_descaffolding"]["status"] == "ready"
    assert readback["residuals"]["multimodal_perception_bridge"]["status"] == "ready"


def test_compact_line_is_short_and_actionable():
    readback = build_residual_living_loop_readback(current_turn=_complete_turn())

    line = compact_residual_living_loop_line(readback)

    assert "residual=residual_living_loop_phase1_ready" in line
    assert "loop=ready" in line
    assert "blocked_live_capture=true" in line
