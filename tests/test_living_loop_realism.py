from __future__ import annotations

from amadeus_thread0.runtime.living_loop_realism import (
    LIVING_LOOP_REALISM_PHASE1_READINESS,
    LIVING_LOOP_REALISM_PHASE2_READINESS,
    LIVING_LOOP_REALISM_PHASE3_READINESS,
    build_backend_payload_realism_readback,
    build_living_loop_realism_readback,
    compact_backend_payload_realism_line,
    compact_living_loop_realism_line,
    evaluate_behavior_causality,
    normalize_backend_turn_payload_for_realism,
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


def _backend_payload() -> dict:
    turn = _realistic_turn()
    return {
        **turn,
        "emotion_label": "hurt",
        "session_context": {"thread_id": "thread-a", "turn_started_at": 1_777_777_001},
        "turn_summary": {
            "current_turn": {
                "recon_event_kind": "user_utterance",
                "counterpart_scene": "repair_attempt",
                "behavior_consequence_kind": "relationship_repair_acknowledged",
                "digital_body_consequence_kind": "relationship_repair_acknowledged",
            },
            "relationship": {"stage": "repairing"},
            "digital_body_consequence": {"kind": "relationship_repair_acknowledged"},
        },
        "autonomy": {"intent": {"mode": "assist"}, "action_packets": []},
        "skills": {"active_skill_ids": []},
        "digital_body": {
            "active_surface": "dialogue",
            "access_state": {"mode": "dialogue_only"},
            "resource_state": {"artifact_continuity": "none"},
        },
        "operator_readback": {"schema": "operator_readback.v2", "readiness_status": "runtime_productization_phase2_ready"},
    }


def test_normalize_backend_payload_preserves_realism_turn_fields():
    normalized = normalize_backend_turn_payload_for_realism(_backend_payload())

    assert normalized["final_text"] == "嗯。我听见了。边界还在，但这次我会先把话放轻一点。"
    assert normalized["behavior_action"]["primary_motive"] == "support_without_pressure"
    assert normalized["turn_appraisal"]["scene"] == "repair_attempt"
    assert normalized["writeback_trace"]["revision_traces"][0]["target_id"] == "repair_style"


def test_backend_payload_readback_returns_phase2_ready():
    readback = build_backend_payload_realism_readback(_backend_payload())

    assert readback["schema"] == "living_loop_realism.backend_payload.v1"
    assert readback["readiness_status"] == LIVING_LOOP_REALISM_PHASE2_READINESS
    assert readback["backend_payload"]["source"] == "backend_payload"
    assert readback["backend_payload"]["status"] == "ready"
    assert readback["causality"]["status"] == "ready"
    assert readback["authority_boundary"]["persona_core_mutation_allowed"] is False


def _artifact_alignment(status: str = "causally_aligned") -> dict:
    return {
        "schema": "artifact_behavior_alignment.v1",
        "status": "ready",
        "readiness_status": "artifact_behavior_alignment_ready",
        "alignment_items": [
            {
                "source_ref_id": "img-align-1",
                "primary_motive_hint": "restore_access_continuity",
                "behavior_primary_motive": "restore_access_continuity",
                "plan_primary_motive": "restore_access_continuity",
                "alignment_status": status,
                "behavior_mutation_applied": False,
                "authority": {
                    "model_api_called": False,
                    "memory_write_allowed": False,
                    "writeback_ready": False,
                    "behavior_mutation_allowed": False,
                    "behavior_mutation_applied": False,
                },
            }
        ],
        "alignment_summary": {
            "alignment_status": status,
            "aligned_count": 1 if status == "causally_aligned" else 0,
            "advisory_not_reflected_count": 1 if status == "advisory_not_reflected" else 0,
            "conflict_count": 1 if status == "behavior_conflict_observed" else 0,
            "should_mutate_behavior": False,
            "should_write_memory": False,
        },
        "authority_boundary": {
            "persona_core_mutation_allowed": False,
            "memory_write_allowed": False,
            "behavior_mutation_allowed": False,
            "external_mutation_allowed": False,
            "live_capture_enabled": False,
            "multimodal_model_api_called": False,
            "writeback_allowed": False,
        },
        "model_api_called": False,
        "writeback_ready_count": 0,
    }


def test_backend_payload_with_artifact_behavior_alignment_promotes_phase3_readiness():
    payload = _backend_payload()
    payload["turn_appraisal"] = {
        "scene": "artifact_review",
        "interaction_frame": "task",
        "signals": {"task": True, "workspace": True},
    }
    payload["behavior_action"] = {
        **payload["behavior_action"],
        "primary_motive": "restore_access_continuity",
    }
    payload["behavior_plan"] = {
        **payload["behavior_plan"],
        "primary_motive": "restore_access_continuity",
    }
    payload["reconsolidation_snapshot"] = {
        **payload["reconsolidation_snapshot"],
        "behavior_action": {"primary_motive": "restore_access_continuity"},
        "behavior_plan": {"primary_motive": "restore_access_continuity"},
    }
    payload["writeback_trace"] = {
        "revision_traces": [{"namespace": "artifact_access", "target_id": "restore_access_continuity"}]
    }
    payload["embodied_interaction"] = {
        "readiness_status": "embodied_interaction_runtime_phase5_ready",
        "artifact_behavior_alignment": _artifact_alignment("causally_aligned"),
    }

    readback = build_backend_payload_realism_readback(payload)

    assert readback["readiness_status"] == LIVING_LOOP_REALISM_PHASE3_READINESS
    assert readback["artifact_behavior_alignment"]["status"] == "ready"
    assert readback["artifact_behavior_alignment"]["alignment_visible"] is True
    assert readback["artifact_behavior_alignment"]["alignment_status"] == "causally_aligned"
    assert readback["artifact_behavior_alignment"]["causally_aligned_count"] == 1
    assert readback["artifact_behavior_alignment"]["behavior_mutation_applied"] is False
    assert readback["authority_boundary"]["memory_write_allowed"] is False


def test_backend_payload_without_artifact_alignment_stays_phase2_ready():
    readback = build_backend_payload_realism_readback(_backend_payload())

    assert readback["readiness_status"] == LIVING_LOOP_REALISM_PHASE2_READINESS
    assert readback["artifact_behavior_alignment"]["status"] == "not_applicable"
    assert readback["artifact_behavior_alignment"]["alignment_visible"] is False


def test_backend_payload_requires_backend_only_surfaces():
    payload = _backend_payload()
    payload.pop("turn_summary")

    readback = build_backend_payload_realism_readback(payload)

    assert readback["overall_status"] == "in_progress"
    assert readback["backend_payload"]["status"] == "missing"
    assert "turn_summary" in readback["backend_payload"]["missing_fields"]
    assert readback["readiness_status"] == "living_loop_runtime_realism_phase2_in_progress"


def test_backend_payload_compact_line_names_source_status():
    line = compact_backend_payload_realism_line(build_backend_payload_realism_readback(_backend_payload()))

    assert "backend_payload=ready" in line
    assert "realism=living_loop_runtime_realism_phase2_ready" in line
    assert "causality=ready" in line
