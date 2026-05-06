from __future__ import annotations

from typing import Any


RESIDUAL_LIVING_LOOP_PHASE1_READINESS = "residual_living_loop_phase1_ready"
RESIDUAL_LIVING_LOOP_IN_PROGRESS = "residual_living_loop_phase1_in_progress"

NORTH_STAR_STAGES = (
    "perception",
    "appraisal",
    "internal_state_change",
    "motive_goal_shift",
    "behavior",
    "consequence",
    "memory_reconsolidation",
    "self_narrative_update",
)

AUTHORITY_BOUNDARY = {
    "live_capture_enabled": False,
    "auto_skill_registry_write": False,
    "external_harness_auto_enabled": False,
    "frontend_semantics_owner": False,
    "persona_core_mutation_allowed": False,
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _has_content(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (dict, list, tuple, set)):
        return bool(value)
    return bool(value)


def _nested_dict(row: dict[str, Any], key: str) -> dict[str, Any]:
    return _dict_or_empty(row.get(key))


def _stage_evidence(current_turn: dict[str, Any]) -> dict[str, bool]:
    event = _nested_dict(current_turn, "current_event")
    appraisal = _nested_dict(current_turn, "turn_appraisal")
    emotion = _nested_dict(current_turn, "emotion_state")
    bond = _nested_dict(current_turn, "bond_state")
    allostasis = _nested_dict(current_turn, "allostasis_state")
    action = _nested_dict(current_turn, "behavior_action")
    plan = _nested_dict(current_turn, "behavior_plan")
    consequence = _nested_dict(current_turn, "digital_body_consequence")
    snapshot = _nested_dict(current_turn, "reconsolidation_snapshot")
    writeback = _nested_dict(current_turn, "writeback_trace")
    semantic_profile = _nested_dict(current_turn, "semantic_narrative_profile")

    snapshot_consequence = _dict_or_empty(snapshot.get("digital_body_consequence"))
    snapshot_action = _dict_or_empty(snapshot.get("behavior_action"))
    revision_traces = _list_or_empty(writeback.get("revision_traces"))
    counterpart_history = _list_or_empty(writeback.get("counterpart_assessment_history"))
    proactive_history = _list_or_empty(writeback.get("proactive_continuity_history"))

    return {
        "perception": _has_content(event)
        and (_has_content(event.get("perception")) or _has_content(event.get("kind"))),
        "appraisal": _has_content(appraisal),
        "internal_state_change": _has_content(emotion) and _has_content(bond) and _has_content(allostasis),
        "motive_goal_shift": _has_content(action.get("primary_motive"))
        or _has_content(action.get("motive"))
        or _has_content(plan.get("primary_motive"))
        or _has_content(snapshot_action.get("primary_motive")),
        "behavior": _has_content(action) or _has_content(plan) or _has_content(current_turn.get("final_text")),
        "consequence": _has_content(consequence) or _has_content(snapshot_consequence),
        "memory_reconsolidation": bool(revision_traces or counterpart_history or proactive_history),
        "self_narrative_update": _has_content(semantic_profile.get("continuity_axes"))
        or any(
            str(trace.get("namespace") or trace.get("target_id") or "").startswith("semantic")
            for trace in revision_traces
            if isinstance(trace, dict)
        ),
    }


def evaluate_living_loop_trace(current_turn: dict[str, Any] | None) -> dict[str, Any]:
    turn = _dict_or_empty(current_turn)
    evidence = _stage_evidence(turn)
    missing = [stage for stage in NORTH_STAR_STAGES if not evidence.get(stage)]
    ready_count = len(NORTH_STAR_STAGES) - len(missing)
    return {
        "status": "ready" if not missing else "incomplete",
        "ready_stage_count": ready_count,
        "total_stage_count": len(NORTH_STAR_STAGES),
        "missing_stages": missing,
        "stages": {stage: "ready" if evidence.get(stage) else "missing" for stage in NORTH_STAR_STAGES},
    }


def _ready_row(summary: str, *, runtime_available: bool = True) -> dict[str, Any]:
    return {
        "status": "ready",
        "runtime_available": runtime_available,
        "summary": summary,
        "blocked_surfaces": [],
    }


def _blocked_row(summary: str, blocked_surfaces: list[str], *, runtime_available: bool = False) -> dict[str, Any]:
    return {
        "status": "ready",
        "runtime_available": runtime_available,
        "summary": summary,
        "blocked_surfaces": blocked_surfaces,
    }


def _chinese_semantic_row() -> dict[str, Any]:
    try:
        from amadeus_thread0.graph_parts.chinese_semantic_surface import (
            FAMILIES,
            candidate_replacement_semantics,
        )
    except Exception as exc:
        return {
            "status": "incomplete",
            "runtime_available": False,
            "summary": f"Chinese semantic diagnostics unavailable: {exc}",
            "blocked_surfaces": ["prompt_sprawl_rewrite", "persona_core_redefinition"],
        }

    missing = [
        family
        for family in sorted(FAMILIES)
        if not str(candidate_replacement_semantics(family).get("replacement_semantic") or "").strip()
    ]
    return {
        "status": "ready" if not missing else "incomplete",
        "runtime_available": False,
        "summary": "Semantic Chinese surface diagnostics are present before broad runtime rewrite.",
        "missing_replacement_families": missing,
        "blocked_surfaces": [
            "prompt_sprawl_rewrite",
            "persona_core_redefinition",
            "ad_hoc_reply_tone_micro_polish",
        ],
    }


def _multimodal_bridge_row(current_turn: dict[str, Any]) -> dict[str, Any]:
    event = _nested_dict(current_turn, "current_event")
    perception = _dict_or_empty(event.get("perception"))
    hints = _dict_or_empty(event.get("digital_body_hints")) or _dict_or_empty(perception.get("digital_body_hints"))
    modality = str(perception.get("modality") or perception.get("channel") or "").strip()
    source = _dict_or_empty(hints.get("multimodal_source"))
    blocked_source = str(source.get("status") or "").strip() == "blocked"
    source_block_reasons = _list_or_empty(source.get("block_reasons"))
    has_source_bridge = bool(
        hints.get("artifact_carrier")
        or hints.get("active_artifact_kind")
        or hints.get("multimodal_source")
        or modality in {"text", "image", "audio", "screen", "browser_capture"}
    )
    if blocked_source and any("capture" in str(reason) for reason in source_block_reasons):
        return {
            "status": "ready",
            "runtime_available": False,
            "summary": "Blocked capture remains visible as a body condition instead of becoming perception fact.",
            "blocked_surfaces": source_block_reasons,
        }
    return {
        "status": "ready" if has_source_bridge else "incomplete",
        "runtime_available": bool(has_source_bridge),
        "summary": "Consent-bound source artifacts can enter perception as digital-body hints.",
        "blocked_surfaces": [
            "live_microphone_capture",
            "live_camera_capture",
            "background_screen_capture",
            "secret_capture",
        ],
    }


def _dynamic_capability_row(current_turn: dict[str, Any]) -> dict[str, Any]:
    skills = _nested_dict(current_turn, "skills")
    autonomy = _nested_dict(current_turn, "autonomy")
    packets = _list_or_empty(autonomy.get("action_packets"))
    pending_skill = _dict_or_empty(skills.get("pending_approval"))
    auto_registry_write = any(
        str(packet.get("intent") or "").startswith("skill:")
        and str(packet.get("status") or "") == "completed"
        and not bool(packet.get("requires_approval", True))
        for packet in packets
        if isinstance(packet, dict)
    )
    return {
        "status": "incomplete" if auto_registry_write else "ready",
        "runtime_available": False,
        "summary": "Dynamic skills and workflow candidates remain proposal/hash/approval-gated.",
        "pending_skill_proposal": bool(pending_skill),
        "blocked_surfaces": [
            "auto_install",
            "auto_enable",
            "registry_write_without_approval",
            "persona_core_skill_patch",
        ],
    }


def _long_horizon_row(current_turn: dict[str, Any]) -> dict[str, Any]:
    semantic_profile = _nested_dict(current_turn, "semantic_narrative_profile")
    axes = _list_or_empty(semantic_profile.get("continuity_axes"))
    return {
        "status": "ready" if axes else "incomplete",
        "runtime_available": False,
        "summary": "Long-horizon calibration remains offline while semantic continuity axes stay visible.",
        "blocked_surfaces": [
            "keyword_scene_script_sprawl",
            "online_personality_tuning_without_audit",
        ],
    }


def build_residual_living_loop_readback(*, current_turn: dict[str, Any] | None = None) -> dict[str, Any]:
    turn = _dict_or_empty(current_turn)
    trace = evaluate_living_loop_trace(turn)
    residuals = {
        "living_loop_traceability": {
            "status": "ready" if trace["status"] == "ready" else "incomplete",
            "runtime_available": True,
            "summary": "North-star loop stages are visible in one final-turn packet.",
            "missing_stages": list(trace.get("missing_stages") or []),
            "blocked_surfaces": [],
        },
        "chinese_semantic_descaffolding": _chinese_semantic_row(),
        "multimodal_perception_bridge": _multimodal_bridge_row(turn),
        "dynamic_capability_boundaries": _dynamic_capability_row(turn),
        "natural_long_horizon_calibration": _long_horizon_row(turn),
    }
    incomplete = [key for key, row in residuals.items() if str(row.get("status") or "") != "ready"]
    overall = "passed" if not incomplete else "in_progress"
    return {
        "phase": "Residual Living Loop Closure Phase 1",
        "schema": "residual_living_loop.v1",
        "overall_status": overall,
        "readiness_status": RESIDUAL_LIVING_LOOP_PHASE1_READINESS if not incomplete else RESIDUAL_LIVING_LOOP_IN_PROGRESS,
        "living_loop_trace": trace,
        "residuals": residuals,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "failure_reasons": incomplete,
    }


def compact_residual_living_loop_line(readback: dict[str, Any] | None) -> str:
    data = _dict_or_empty(readback)
    if not data:
        return ""
    trace = _dict_or_empty(data.get("living_loop_trace"))
    boundary = _dict_or_empty(data.get("authority_boundary"))
    parts = [
        f"residual={str(data.get('readiness_status') or '').strip() or 'unknown'}",
        f"loop={str(trace.get('status') or 'unknown').strip()}",
    ]
    missing = _list_or_empty(trace.get("missing_stages"))
    if missing:
        parts.append("missing=" + ",".join(str(item) for item in missing))
    parts.append(f"blocked_live_capture={str(not bool(boundary.get('live_capture_enabled', False))).lower()}")
    parts.append(f"auto_skill_write={str(bool(boundary.get('auto_skill_registry_write', False))).lower()}")
    return " | ".join(parts)


__all__ = [
    "AUTHORITY_BOUNDARY",
    "NORTH_STAR_STAGES",
    "RESIDUAL_LIVING_LOOP_IN_PROGRESS",
    "RESIDUAL_LIVING_LOOP_PHASE1_READINESS",
    "build_residual_living_loop_readback",
    "compact_residual_living_loop_line",
    "evaluate_living_loop_trace",
]
