from __future__ import annotations

from amadeus_thread0.runtime.living_loop_realism import (
    LIVING_LOOP_REALISM_PHASE1_READINESS,
    build_living_loop_realism_readback,
    compact_living_loop_realism_line,
    evaluate_behavior_causality,
)


def _realistic_turn() -> dict:
    return {
        "final_text": "嗯。我听见了。边界还在，但这次我会先把话放轻一点。",
        "current_event": {
            "kind": "user_utterance",
            "text": "之前那件事我一直记着，我们能慢慢聊吗？",
            "tags": ["repair", "relationship"],
        },
        "turn_appraisal": {
            "scene": "repair_attempt",
            "interaction_frame": "relationship",
            "signals": {"repair": True, "care": True},
        },
        "emotion_state": {"label": "hurt", "valence": -0.08, "arousal": 0.22},
        "bond_state": {"trust": 0.60, "closeness": 0.58, "hurt": 0.14, "repair_confidence": 0.66},
        "allostasis_state": {"autonomy_need": 0.38, "safety_need": 0.42, "cognitive_budget": 0.70},
        "counterpart_assessment": {
            "stance": "watchful",
            "scene": "repair_attempt",
            "boundary_pressure": 0.18,
            "reliability_read": 0.62,
        },
        "semantic_narrative_profile": {
            "repair_residue": 0.76,
            "continuity_depth": 0.68,
            "commitment_carry": 0.62,
            "continuity_axes": [{"category": "repair_style", "score": 0.74}],
        },
        "behavior_action": {
            "interaction_mode": "low_pressure_support",
            "action_target": "low_pressure_hold",
            "primary_motive": "support_without_pressure",
            "motive_tension": "boundary_vs_closeness",
            "goal_frame": "先低负担接住，不接管对方节奏。",
        },
        "behavior_plan": {
            "kind": "low_pressure_support",
            "interaction_mode": "low_pressure_support",
            "primary_motive": "support_without_pressure",
            "goal_frame": "先低负担接住，不接管对方节奏。",
        },
        "digital_body_consequence": {"kind": "relationship_repair_acknowledged"},
        "reconsolidation_snapshot": {
            "behavior_action": {"primary_motive": "support_without_pressure"},
            "behavior_plan": {"kind": "low_pressure_support", "primary_motive": "support_without_pressure"},
            "digital_body_consequence": {"kind": "relationship_repair_acknowledged"},
            "final_text": "嗯。我听见了。边界还在，但这次我会先把话放轻一点。",
        },
        "writeback_trace": {
            "revision_traces": [{"namespace": "semantic_self_evidence", "target_id": "repair_style"}],
            "counterpart_assessment_history": [{"stance": "watchful", "scene": "repair_attempt"}],
        },
    }


def test_behavior_causality_passes_when_state_drives_behavior():
    report = evaluate_behavior_causality(_realistic_turn())

    assert report["status"] == "ready"
    assert report["missing_links"] == []
    assert report["links"]["appraisal_to_motive"]["status"] == "ready"
    assert report["links"]["state_to_behavior"]["status"] == "ready"
    assert report["links"]["final_semantics_alignment"]["status"] == "ready"


def test_behavior_causality_fails_when_appraisal_conflicts_with_motive():
    turn = _realistic_turn()
    turn["turn_appraisal"] = {"scene": "repair_attempt", "signals": {"repair": True}}
    turn["behavior_action"] = {"primary_motive": "solve_task", "interaction_mode": "tooling"}
    turn["behavior_plan"] = {"primary_motive": "solve_task", "kind": "tooling"}

    report = evaluate_behavior_causality(turn)

    assert report["status"] == "incomplete"
    assert "appraisal_to_motive" in report["missing_links"]


def test_behavior_causality_fails_when_snapshot_motive_conflicts_with_final_action():
    turn = _realistic_turn()
    turn["reconsolidation_snapshot"] = {
        **turn["reconsolidation_snapshot"],
        "behavior_action": {"primary_motive": "solve_task"},
    }

    report = evaluate_behavior_causality(turn)

    assert report["status"] == "incomplete"
    assert "final_semantics_alignment" in report["missing_links"]


def test_readback_keeps_authority_boundary_closed():
    readback = build_living_loop_realism_readback(current_turn=_realistic_turn())

    assert readback["readiness_status"] == LIVING_LOOP_REALISM_PHASE1_READINESS
    assert readback["schema"] == "living_loop_realism.v1"
    assert readback["authority_boundary"]["persona_core_mutation_allowed"] is False
    assert readback["authority_boundary"]["memory_write_allowed"] is False
    assert readback["authority_boundary"]["prompt_sprawl_rewrite_allowed"] is False


def test_compact_line_names_causality_status():
    line = compact_living_loop_realism_line(build_living_loop_realism_readback(current_turn=_realistic_turn()))

    assert "realism=living_loop_runtime_realism_phase1_ready" in line
    assert "causality=ready" in line
