from __future__ import annotations

from typing import Any


LIVING_LOOP_REALISM_PHASE1_READINESS = "living_loop_runtime_realism_phase1_ready"
LIVING_LOOP_REALISM_IN_PROGRESS = "living_loop_runtime_realism_phase1_in_progress"
LIVING_LOOP_REALISM_PHASE2_READINESS = "living_loop_runtime_realism_phase2_ready"
LIVING_LOOP_REALISM_PHASE2_IN_PROGRESS = "living_loop_runtime_realism_phase2_in_progress"
LIVING_LOOP_REALISM_PHASE3_READINESS = "living_loop_runtime_realism_phase3_ready"
LIVING_LOOP_REALISM_PHASE3_IN_PROGRESS = "living_loop_runtime_realism_phase3_in_progress"

CAUSAL_LINKS = (
    "appraisal_to_motive",
    "state_to_behavior",
    "action_plan_alignment",
    "consequence_reconsolidation_alignment",
    "final_semantics_alignment",
)

BACKEND_PAYLOAD_REQUIRED_FIELDS = (
    "final_text",
    "behavior_action",
    "behavior_plan",
    "turn_summary",
    "writeback_trace",
    "reconsolidation_snapshot",
)

ARTIFACT_ALIGNMENT_ALLOWED_STATUSES = (
    "causally_aligned",
    "advisory_not_reflected",
)

AUTHORITY_BOUNDARY = {
    "persona_core_mutation_allowed": False,
    "memory_write_allowed": False,
    "prompt_sprawl_rewrite_allowed": False,
    "live_capture_enabled": False,
    "external_mutation_allowed": False,
    "auto_skill_registry_write": False,
}

_REPAIR_MOTIVES = {
    "support_without_pressure",
    "repair_without_erasing_boundary",
    "protect_boundary",
    "honor_continuity",
}
_BOUNDARY_MOTIVES = {"protect_boundary", "preserve_self_rhythm"}
_CONTINUITY_MOTIVES = {
    "honor_continuity",
    "confirm_presence",
    "gentle_recontact",
    "maintain_natural_contact",
    "open_shared_window",
    "support_without_pressure",
}
_TASK_MOTIVES = {
    "solve_task",
    "continue_workspace_task",
    "restore_workspace_continuity",
    "restore_access_continuity",
    "request_access_help",
    "resolve_access_before_task",
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _lower(value: Any) -> str:
    return _clean(value).lower()


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return default


def _has_text(value: Any) -> bool:
    return bool(_clean(value))


def _any_text_contains(values: list[str], needles: set[str]) -> bool:
    haystack = " ".join(values).lower()
    return any(needle in haystack for needle in needles)


def _field_texts(*rows: dict[str, Any]) -> list[str]:
    fields = (
        "primary_motive",
        "motive",
        "interaction_mode",
        "action_target",
        "kind",
        "target",
        "motive_tension",
        "goal_frame",
        "note",
        "relationship_weather",
        "attention_target",
        "trigger_family",
        "presence_family",
    )
    texts: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        for field in fields:
            text = _lower(row.get(field))
            if text:
                texts.append(text)
    return texts


def _signals_from_appraisal(appraisal: dict[str, Any]) -> set[str]:
    scene = _lower(appraisal.get("scene") or appraisal.get("interaction_frame") or appraisal.get("selfhood_scene"))
    frame = _lower(appraisal.get("interaction_frame"))
    selfhood_scene = _lower(appraisal.get("selfhood_scene"))
    signals = {
        key
        for key, value in _dict_or_empty(appraisal.get("signals")).items()
        if bool(value) and _clean(key)
    }
    for value in (scene, frame, selfhood_scene):
        if value:
            signals.add(value)
    return signals


def _primary_motive(action: dict[str, Any], plan: dict[str, Any], snapshot: dict[str, Any]) -> str:
    snapshot_action = _dict_or_empty(snapshot.get("behavior_action"))
    for row in (action, plan, snapshot_action):
        motive = _clean(row.get("primary_motive") or row.get("motive"))
        if motive:
            return motive
    return ""


def _status_row(status: bool, summary: str, *, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": "ready" if status else "missing",
        "summary": summary,
        "evidence": dict(evidence or {}),
    }


def _appraisal_to_motive(turn: dict[str, Any]) -> dict[str, Any]:
    appraisal = _dict_or_empty(turn.get("turn_appraisal"))
    action = _dict_or_empty(turn.get("behavior_action"))
    plan = _dict_or_empty(turn.get("behavior_plan"))
    snapshot = _dict_or_empty(turn.get("reconsolidation_snapshot"))
    motive = _primary_motive(action, plan, snapshot)
    signals = _signals_from_appraisal(appraisal)
    scene_text = " ".join(sorted(signals))
    motive_set = {motive}
    if not appraisal or not motive:
        return _status_row(
            False,
            "Appraisal and motive must both be present before causality can be assessed.",
            evidence={"signals": sorted(signals), "primary_motive": motive},
        )
    if any(token in scene_text for token in ("repair", "apology", "care")):
        ok = bool(motive_set & _REPAIR_MOTIVES)
        return _status_row(
            ok,
            "Repair/care appraisal constrains motive toward low-pressure repair or boundary-preserving contact.",
            evidence={"signals": sorted(signals), "primary_motive": motive, "allowed_motives": sorted(_REPAIR_MOTIVES)},
        )
    if any(token in scene_text for token in ("boundary", "selfhood", "equality", "autonomy")):
        ok = bool(motive_set & _BOUNDARY_MOTIVES)
        return _status_row(
            ok,
            "Boundary/selfhood appraisal constrains motive toward boundary or own-rhythm preservation.",
            evidence={"signals": sorted(signals), "primary_motive": motive, "allowed_motives": sorted(_BOUNDARY_MOTIVES)},
        )
    if any(token in scene_text for token in ("daily", "companion", "presence", "continuity", "relationship")):
        ok = bool(motive_set & (_CONTINUITY_MOTIVES | _REPAIR_MOTIVES | _BOUNDARY_MOTIVES))
        return _status_row(
            ok,
            "Daily/relationship appraisal constrains motive toward continuity, presence, repair, or boundary.",
            evidence={"signals": sorted(signals), "primary_motive": motive},
        )
    if any(token in scene_text for token in ("task", "workspace", "co_work")):
        ok = bool(motive_set & (_TASK_MOTIVES | _CONTINUITY_MOTIVES))
        return _status_row(
            ok,
            "Task/workspace appraisal constrains motive toward task continuity without replacing relational context.",
            evidence={"signals": sorted(signals), "primary_motive": motive},
        )
    return _status_row(
        True,
        "Neutral appraisal has a visible motive and no contradictory scene constraint.",
        evidence={"signals": sorted(signals), "primary_motive": motive},
    )


def _state_influence_markers(turn: dict[str, Any]) -> dict[str, list[str]]:
    emotion = _dict_or_empty(turn.get("emotion_state"))
    bond = _dict_or_empty(turn.get("bond_state"))
    allostasis = _dict_or_empty(turn.get("allostasis_state"))
    counterpart = _dict_or_empty(turn.get("counterpart_assessment"))
    semantic = _dict_or_empty(turn.get("semantic_narrative_profile"))
    action = _dict_or_empty(turn.get("behavior_action"))
    plan = _dict_or_empty(turn.get("behavior_plan"))
    texts = _field_texts(action, plan)
    markers: dict[str, list[str]] = {}

    emotion_label = _lower(emotion.get("label"))
    if emotion_label in {"hurt", "guarded", "wary", "irritated"} and _any_text_contains(
        texts,
        {"boundary", "low_pressure", "watch", "guard", "hold", "distance"},
    ):
        markers["emotion_state"] = [emotion_label]
    elif emotion_label in {"care", "calm", "tease", "warm"} and _any_text_contains(
        texts,
        {"presence", "support", "continuity", "contact", "respond_now"},
    ):
        markers["emotion_state"] = [emotion_label]

    if _clamp01(bond.get("repair_confidence")) >= 0.5 or _clamp01(bond.get("hurt")) >= 0.12:
        if _any_text_contains(texts, {"repair", "low_pressure", "boundary", "support"}):
            markers["bond_state"] = [
                f"repair_confidence={_clamp01(bond.get('repair_confidence')):.2f}",
                f"hurt={_clamp01(bond.get('hurt')):.2f}",
            ]
    elif _clamp01(bond.get("trust")) >= 0.62 or _clamp01(bond.get("closeness")) >= 0.62:
        if _any_text_contains(texts, {"continuity", "presence", "contact", "honor"}):
            markers["bond_state"] = [
                f"trust={_clamp01(bond.get('trust')):.2f}",
                f"closeness={_clamp01(bond.get('closeness')):.2f}",
            ]

    if _clamp01(allostasis.get("autonomy_need")) >= 0.34 or _clamp01(allostasis.get("safety_need")) >= 0.34:
        if _any_text_contains(texts, {"boundary", "own_rhythm", "low_pressure", "hold", "protect"}):
            markers["allostasis_state"] = [
                f"autonomy_need={_clamp01(allostasis.get('autonomy_need')):.2f}",
                f"safety_need={_clamp01(allostasis.get('safety_need')):.2f}",
            ]

    counterpart_scene = _lower(counterpart.get("scene"))
    counterpart_stance = _lower(counterpart.get("stance"))
    if (
        counterpart_scene in {"repair_attempt", "friction", "daily_contact", "care_bid"}
        or counterpart_stance in {"watchful", "open", "guarded"}
    ) and _any_text_contains(texts, {"repair", "boundary", "presence", "support", "relationship"}):
        markers["counterpart_assessment"] = [counterpart_scene or counterpart_stance]

    semantic_keys = {
        key
        for key, value in semantic.items()
        if isinstance(value, (int, float)) and _clamp01(value) >= 0.5
    }
    axis_categories = {
        _lower(item.get("category"))
        for item in _list_or_empty(semantic.get("continuity_axes"))
        if isinstance(item, dict) and _lower(item.get("category"))
    }
    if semantic_keys or axis_categories:
        semantic_text = " ".join(sorted(semantic_keys | axis_categories))
        if (
            ("repair" in semantic_text and _any_text_contains(texts, {"repair", "support", "low_pressure"}))
            or ("boundary" in semantic_text and _any_text_contains(texts, {"boundary", "protect"}))
            or ("continuity" in semantic_text and _any_text_contains(texts, {"continuity", "honor", "presence"}))
            or ("commitment" in semantic_text and _any_text_contains(texts, {"continuity", "honor", "presence"}))
        ):
            markers["semantic_narrative_profile"] = sorted(semantic_keys | axis_categories)

    return markers


def _state_to_behavior(turn: dict[str, Any]) -> dict[str, Any]:
    markers = _state_influence_markers(turn)
    ok = len(markers) >= 2
    return _status_row(
        ok,
        "At least two internal/relationship state families must leave compatible behavior markers.",
        evidence={"influence_markers": markers, "influence_family_count": len(markers)},
    )


def _action_plan_alignment(turn: dict[str, Any]) -> dict[str, Any]:
    action = _dict_or_empty(turn.get("behavior_action"))
    plan = _dict_or_empty(turn.get("behavior_plan"))
    action_motive = _clean(action.get("primary_motive") or action.get("motive"))
    plan_motive = _clean(plan.get("primary_motive") or plan.get("motive"))
    action_mode = _clean(action.get("interaction_mode"))
    plan_mode = _clean(plan.get("interaction_mode"))
    if action_motive and plan_motive and action_motive != plan_motive:
        return _status_row(
            False,
            "Behavior action and plan disagree on primary motive.",
            evidence={"action_motive": action_motive, "plan_motive": plan_motive},
        )
    if action_mode and plan_mode and action_mode != plan_mode:
        return _status_row(
            False,
            "Behavior action and plan disagree on interaction mode.",
            evidence={"action_interaction_mode": action_mode, "plan_interaction_mode": plan_mode},
        )
    return _status_row(
        bool(action or plan),
        "Behavior action and plan keep one final motive/mode.",
        evidence={"action_motive": action_motive, "plan_motive": plan_motive, "action_mode": action_mode, "plan_mode": plan_mode},
    )


def _consequence_reconsolidation_alignment(turn: dict[str, Any]) -> dict[str, Any]:
    consequence = _dict_or_empty(turn.get("digital_body_consequence"))
    snapshot = _dict_or_empty(turn.get("reconsolidation_snapshot"))
    snapshot_consequence = _dict_or_empty(snapshot.get("digital_body_consequence"))
    consequence_kind = _clean(consequence.get("kind"))
    snapshot_kind = _clean(snapshot_consequence.get("kind"))
    if consequence_kind and snapshot_kind and consequence_kind != snapshot_kind:
        return _status_row(
            False,
            "Digital-body consequence changed before reconsolidation.",
            evidence={"consequence_kind": consequence_kind, "snapshot_consequence_kind": snapshot_kind},
        )
    return _status_row(
        bool(consequence_kind or snapshot_kind),
        "Digital-body consequence stays aligned with reconsolidation.",
        evidence={"consequence_kind": consequence_kind, "snapshot_consequence_kind": snapshot_kind},
    )


def _writeback_has_motive(writeback: dict[str, Any], motive: str) -> bool:
    if not motive:
        return False
    revision_traces = _list_or_empty(writeback.get("revision_traces"))
    history = [
        *_list_or_empty(writeback.get("counterpart_assessment_history")),
        *_list_or_empty(writeback.get("proactive_continuity_history")),
    ]
    for row in [*revision_traces, *history]:
        if not isinstance(row, dict):
            continue
        if motive in str(row):
            return True
        namespace = _lower(row.get("namespace"))
        target = _lower(row.get("target_id"))
        if motive.startswith("support") and ("repair" in namespace or "repair" in target):
            return True
        if motive.startswith("protect") and ("boundary" in namespace or "boundary" in target):
            return True
        if motive.startswith("honor") and ("continuity" in namespace or "continuity" in target):
            return True
    return False


def _final_semantics_alignment(turn: dict[str, Any]) -> dict[str, Any]:
    action = _dict_or_empty(turn.get("behavior_action"))
    plan = _dict_or_empty(turn.get("behavior_plan"))
    snapshot = _dict_or_empty(turn.get("reconsolidation_snapshot"))
    snapshot_action = _dict_or_empty(snapshot.get("behavior_action"))
    snapshot_plan = _dict_or_empty(snapshot.get("behavior_plan"))
    writeback = _dict_or_empty(turn.get("writeback_trace"))
    motives = [
        _clean(action.get("primary_motive") or action.get("motive")),
        _clean(plan.get("primary_motive") or plan.get("motive")),
        _clean(snapshot_action.get("primary_motive") or snapshot_action.get("motive")),
        _clean(snapshot_plan.get("primary_motive") or snapshot_plan.get("motive")),
    ]
    present_motives = [motive for motive in motives if motive]
    unique_motives = sorted(set(present_motives))
    final_text = _clean(turn.get("final_text"))
    snapshot_text = _clean(snapshot.get("final_text"))
    text_aligned = not snapshot_text or not final_text or snapshot_text == final_text
    motive_aligned = len(unique_motives) <= 1
    writeback_aligned = not unique_motives or _writeback_has_motive(writeback, unique_motives[0])
    ok = bool(text_aligned and motive_aligned and writeback_aligned)
    return _status_row(
        ok,
        "Final text, action, plan, snapshot, and writeback preserve one final behavior semantics.",
        evidence={
            "unique_motives": unique_motives,
            "final_text_matches_snapshot": text_aligned,
            "writeback_mentions_motive": writeback_aligned,
        },
    )


def evaluate_behavior_causality(current_turn: dict[str, Any] | None) -> dict[str, Any]:
    turn = _dict_or_empty(current_turn)
    links = {
        "appraisal_to_motive": _appraisal_to_motive(turn),
        "state_to_behavior": _state_to_behavior(turn),
        "action_plan_alignment": _action_plan_alignment(turn),
        "consequence_reconsolidation_alignment": _consequence_reconsolidation_alignment(turn),
        "final_semantics_alignment": _final_semantics_alignment(turn),
    }
    missing = [name for name in CAUSAL_LINKS if str(links[name].get("status") or "") != "ready"]
    return {
        "status": "ready" if not missing else "incomplete",
        "ready_link_count": len(CAUSAL_LINKS) - len(missing),
        "total_link_count": len(CAUSAL_LINKS),
        "missing_links": missing,
        "links": links,
    }


def build_living_loop_realism_readback(*, current_turn: dict[str, Any] | None = None) -> dict[str, Any]:
    causality = evaluate_behavior_causality(current_turn)
    ready = str(causality.get("status") or "") == "ready"
    return {
        "phase": "Living Loop Runtime Realism Phase 1",
        "schema": "living_loop_realism.v1",
        "overall_status": "passed" if ready else "in_progress",
        "readiness_status": LIVING_LOOP_REALISM_PHASE1_READINESS if ready else LIVING_LOOP_REALISM_IN_PROGRESS,
        "causality": causality,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "failure_reasons": list(causality.get("missing_links") or []),
    }


def _backend_payload_status(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = _dict_or_empty(payload)
    missing = [field for field in BACKEND_PAYLOAD_REQUIRED_FIELDS if field not in data]
    empty = [
        field
        for field in BACKEND_PAYLOAD_REQUIRED_FIELDS
        if field in data
        and (
            (isinstance(data.get(field), dict) and not data.get(field))
            or (isinstance(data.get(field), list) and not data.get(field))
            or (isinstance(data.get(field), str) and not data.get(field).strip())
            or data.get(field) is None
        )
    ]
    ready = not missing and not empty
    return {
        "source": "backend_payload",
        "status": "ready" if ready else "missing",
        "missing_fields": missing,
        "empty_fields": empty,
        "required_fields": list(BACKEND_PAYLOAD_REQUIRED_FIELDS),
    }


def _artifact_behavior_alignment_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    embodied = _dict_or_empty(payload.get("embodied_interaction"))
    alignment = _dict_or_empty(embodied.get("artifact_behavior_alignment"))
    if not alignment:
        return {
            "source": "embodied_interaction.artifact_behavior_alignment",
            "status": "not_applicable",
            "alignment_visible": False,
            "alignment_status": "not_applicable",
            "alignment_count": 0,
            "causally_aligned_count": 0,
            "advisory_not_reflected_count": 0,
            "conflict_count": 0,
            "model_api_called": False,
            "writeback_ready_count": 0,
            "should_write_memory": False,
            "behavior_mutation_allowed": False,
            "behavior_mutation_applied": False,
            "failure_reasons": [],
        }
    items = [
        dict(item)
        for item in _list_or_empty(alignment.get("alignment_items"))
        if isinstance(item, dict)
    ]
    summary = _dict_or_empty(alignment.get("alignment_summary"))
    boundary = _dict_or_empty(alignment.get("authority_boundary"))
    alignment_status = _clean(summary.get("alignment_status")) or _clean(
        items[0].get("alignment_status") if items else ""
    )
    model_api_called = bool(alignment.get("model_api_called", False)) or bool(
        boundary.get("multimodal_model_api_called", False)
    ) or any(
        bool(_dict_or_empty(item.get("authority")).get("model_api_called", False))
        for item in items
    )
    writeback_ready_count = int(alignment.get("writeback_ready_count") or 0) + sum(
        1 for item in items if bool(_dict_or_empty(item.get("authority")).get("writeback_ready", False))
    )
    should_write_memory = bool(summary.get("should_write_memory", False)) or bool(
        boundary.get("memory_write_allowed", False)
    ) or any(
        bool(_dict_or_empty(item.get("authority")).get("memory_write_allowed", False))
        for item in items
    )
    behavior_mutation_allowed = bool(summary.get("should_mutate_behavior", False)) or bool(
        boundary.get("behavior_mutation_allowed", False)
    ) or any(
        bool(_dict_or_empty(item.get("authority")).get("behavior_mutation_allowed", False))
        for item in items
    )
    behavior_mutation_applied = any(
        bool(item.get("behavior_mutation_applied", False))
        or bool(_dict_or_empty(item.get("authority")).get("behavior_mutation_applied", False))
        for item in items
    )
    external_mutation_allowed = bool(boundary.get("external_mutation_allowed", False))
    failure_reasons: list[str] = []
    if _clean(alignment.get("status")) != "ready":
        failure_reasons.append(f"artifact_alignment_status={_clean(alignment.get('status')) or 'missing'}")
    if _clean(alignment.get("readiness_status")) != "artifact_behavior_alignment_ready":
        failure_reasons.append(
            f"artifact_alignment_readiness={_clean(alignment.get('readiness_status')) or 'missing'}"
        )
    if not items:
        failure_reasons.append("artifact_alignment_missing_items")
    if alignment_status not in ARTIFACT_ALIGNMENT_ALLOWED_STATUSES:
        failure_reasons.append(f"artifact_alignment_status={alignment_status or 'missing'}")
    if model_api_called:
        failure_reasons.append("artifact_alignment_model_api_called")
    if writeback_ready_count:
        failure_reasons.append("artifact_alignment_writeback_ready")
    if should_write_memory:
        failure_reasons.append("artifact_alignment_memory_write")
    if behavior_mutation_allowed:
        failure_reasons.append("artifact_alignment_behavior_mutation_allowed")
    if behavior_mutation_applied:
        failure_reasons.append("artifact_alignment_behavior_mutation_applied")
    if external_mutation_allowed:
        failure_reasons.append("artifact_alignment_external_mutation_allowed")
    ready = not failure_reasons
    return {
        "source": "embodied_interaction.artifact_behavior_alignment",
        "status": "ready" if ready else "blocked",
        "alignment_visible": ready,
        "alignment_status": alignment_status,
        "alignment_count": len(items),
        "causally_aligned_count": int(summary.get("aligned_count") or 0),
        "advisory_not_reflected_count": int(summary.get("advisory_not_reflected_count") or 0),
        "conflict_count": int(summary.get("conflict_count") or 0),
        "model_api_called": model_api_called,
        "writeback_ready_count": writeback_ready_count,
        "should_write_memory": should_write_memory,
        "behavior_mutation_allowed": behavior_mutation_allowed,
        "behavior_mutation_applied": behavior_mutation_applied,
        "failure_reasons": failure_reasons,
    }


def normalize_backend_turn_payload_for_realism(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = _dict_or_empty(payload)
    return {
        "final_text": data.get("final_text"),
        "current_event": _dict_or_empty(data.get("current_event")),
        "turn_appraisal": _dict_or_empty(data.get("turn_appraisal")),
        "emotion_state": _dict_or_empty(data.get("emotion_state")),
        "bond_state": _dict_or_empty(data.get("bond_state")),
        "allostasis_state": _dict_or_empty(data.get("allostasis_state")),
        "counterpart_assessment": _dict_or_empty(data.get("counterpart_assessment")),
        "semantic_narrative_profile": _dict_or_empty(data.get("semantic_narrative_profile")),
        "behavior_action": _dict_or_empty(data.get("behavior_action")),
        "behavior_plan": _dict_or_empty(data.get("behavior_plan")),
        "digital_body_consequence": _dict_or_empty(data.get("digital_body_consequence")),
        "reconsolidation_snapshot": _dict_or_empty(data.get("reconsolidation_snapshot")),
        "writeback_trace": _dict_or_empty(data.get("writeback_trace")),
        "embodied_interaction": _dict_or_empty(data.get("embodied_interaction")),
    }


def build_backend_payload_realism_readback(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = _dict_or_empty(payload)
    backend_payload = _backend_payload_status(payload)
    current_turn = normalize_backend_turn_payload_for_realism(payload)
    causality = evaluate_behavior_causality(current_turn)
    base_ready = (
        str(backend_payload.get("status") or "") == "ready"
        and str(causality.get("status") or "") == "ready"
    )
    artifact_alignment = _artifact_behavior_alignment_from_payload(data)
    alignment_present = str(artifact_alignment.get("status") or "") == "ready"
    artifact_ready = str(artifact_alignment.get("status") or "") == "ready"
    ready = bool(base_ready and (not alignment_present or artifact_ready))
    failure_reasons = list(causality.get("missing_links") or [])
    failure_reasons.extend(f"missing_backend_field:{field}" for field in backend_payload.get("missing_fields") or [])
    failure_reasons.extend(f"empty_backend_field:{field}" for field in backend_payload.get("empty_fields") or [])
    failure_reasons.extend(artifact_alignment.get("failure_reasons") or [])
    readiness = LIVING_LOOP_REALISM_PHASE2_READINESS
    in_progress = LIVING_LOOP_REALISM_PHASE2_IN_PROGRESS
    phase = "Living Loop Runtime Realism Phase 2"
    if alignment_present:
        readiness = LIVING_LOOP_REALISM_PHASE3_READINESS
        in_progress = LIVING_LOOP_REALISM_PHASE3_IN_PROGRESS
        phase = "Living Loop Runtime Realism Phase 3"
    return {
        "phase": phase,
        "schema": "living_loop_realism.backend_payload.v1",
        "overall_status": "passed" if ready else "in_progress",
        "readiness_status": readiness if ready else in_progress,
        "backend_payload": backend_payload,
        "causality": causality,
        "artifact_behavior_alignment": artifact_alignment,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "failure_reasons": failure_reasons,
    }


def compact_living_loop_realism_line(readback: dict[str, Any] | None) -> str:
    data = _dict_or_empty(readback)
    if not data:
        return ""
    causality = _dict_or_empty(data.get("causality"))
    parts = [
        f"realism={_clean(data.get('readiness_status')) or 'unknown'}",
        f"causality={_clean(causality.get('status')) or 'unknown'}",
    ]
    missing = [_clean(item) for item in _list_or_empty(causality.get("missing_links")) if _clean(item)]
    if missing:
        parts.append("missing=" + ",".join(missing))
    boundary = _dict_or_empty(data.get("authority_boundary"))
    parts.append(f"prompt_sprawl={str(bool(boundary.get('prompt_sprawl_rewrite_allowed', False))).lower()}")
    return " | ".join(parts)


def compact_backend_payload_realism_line(readback: dict[str, Any] | None) -> str:
    data = _dict_or_empty(readback)
    if not data:
        return ""
    causality = _dict_or_empty(data.get("causality"))
    backend_payload = _dict_or_empty(data.get("backend_payload"))
    parts = [
        f"realism={_clean(data.get('readiness_status')) or 'unknown'}",
        f"backend_payload={_clean(backend_payload.get('status')) or 'unknown'}",
        f"causality={_clean(causality.get('status')) or 'unknown'}",
    ]
    missing = [_clean(item) for item in _list_or_empty(data.get("failure_reasons")) if _clean(item)]
    if missing:
        parts.append("missing=" + ",".join(missing))
    boundary = _dict_or_empty(data.get("authority_boundary"))
    parts.append(f"prompt_sprawl={str(bool(boundary.get('prompt_sprawl_rewrite_allowed', False))).lower()}")
    return " | ".join(parts)


__all__ = [
    "AUTHORITY_BOUNDARY",
    "BACKEND_PAYLOAD_REQUIRED_FIELDS",
    "CAUSAL_LINKS",
    "LIVING_LOOP_REALISM_IN_PROGRESS",
    "LIVING_LOOP_REALISM_PHASE1_READINESS",
    "LIVING_LOOP_REALISM_PHASE2_IN_PROGRESS",
    "LIVING_LOOP_REALISM_PHASE2_READINESS",
    "LIVING_LOOP_REALISM_PHASE3_IN_PROGRESS",
    "LIVING_LOOP_REALISM_PHASE3_READINESS",
    "build_backend_payload_realism_readback",
    "build_living_loop_realism_readback",
    "compact_backend_payload_realism_line",
    "compact_living_loop_realism_line",
    "evaluate_behavior_causality",
    "normalize_backend_turn_payload_for_realism",
]
