from __future__ import annotations

from typing import Any

from ..graph_parts.relational_runtime import _counterpart_assessment_profile

_SEMANTIC_ANCHOR_FLOAT_KEYS = (
    "continuity_anchor",
    "own_rhythm_anchor",
    "recontact_anchor",
    "boundary_anchor",
    "memory_anchor",
    "semantic_continuity_depth",
    "semantic_identity_gravity",
    "lineage_gravity",
    "contact_lineage",
    "repair_lineage",
    "boundary_lineage",
    "selfhood_lineage",
    "agency_lineage",
)


def _metric(value: Any, default: float = 0.0) -> float:
    try:
        return round(float(value), 3)
    except Exception:
        return round(float(default), 3)


def _int_metric(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _clean_list(values: Any, *, limit: int = 4) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if not text:
            continue
        out.append(text)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _clean_int_list(values: Any, *, limit: int = 8) -> list[int]:
    if not isinstance(values, list):
        return []
    out: list[int] = []
    for item in values:
        try:
            number = int(item)
        except Exception:
            continue
        if number <= 0:
            continue
        out.append(number)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _clean_access_grants(values: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in out:
            continue
        out.append(lowered)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _clean_access_acquire_proposal(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    target = str(value.get("target") or "").strip().lower()
    mode = str(value.get("mode") or "").strip().lower()
    summary = str(value.get("summary") or "").strip()
    operator_action = str(value.get("operator_action") or "").strip()
    grants = _clean_access_grants(value.get("grants"), limit=8)
    requires_operator = bool(value.get("requires_operator", False))
    if not any((target, mode, summary, operator_action, grants, requires_operator)):
        return {}
    return {
        "target": target,
        "mode": mode,
        "summary": summary[:220],
        "operator_action": operator_action[:220],
        "grants": grants,
        "requires_operator": requires_operator,
    }


def _clean_access_acquire_proposals(values: Any, *, limit: int = 8) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in values:
        proposal = _clean_access_acquire_proposal(item)
        if not proposal:
            continue
        key = (
            str(proposal.get("target") or "").strip(),
            str(proposal.get("mode") or "").strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(proposal)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _focus_preview_text(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    return str(item.get("summary") or item.get("text") or item.get("label") or "").strip()


def _focus_preview(worldline_focus: Any, *, limit: int = 3) -> list[str]:
    if not isinstance(worldline_focus, list):
        return []
    out: list[str] = []
    for item in worldline_focus:
        text = _focus_preview_text(item)
        if not text:
            continue
        out.append(text[:120])
        if len(out) >= max(1, int(limit)):
            break
    return out


def _focus_preview_items(worldline_focus: Any, *, limit: int = 3) -> list[dict[str, Any]]:
    if not isinstance(worldline_focus, list):
        return []
    out: list[dict[str, Any]] = []
    for item in worldline_focus:
        text = _focus_preview_text(item)
        if not text:
            continue
        out.append(
            {
                "id": _int_metric(item.get("id"), 0),
                "kind": str(item.get("focus_kind") or item.get("category") or "memory").strip() or "memory",
                "text": text[:120],
                "status": str(item.get("status") or "").strip(),
                "due_at": str(item.get("due_at") or "").strip(),
                "severity": _metric(item.get("severity"), 0.0),
                "affinity_delta": _metric(item.get("affinity_delta"), 0.0),
                "trust_delta": _metric(item.get("trust_delta"), 0.0),
                "created_at": _int_metric(item.get("created_at"), 0),
                "updated_at": _int_metric(item.get("updated_at"), 0),
            }
        )
        if len(out) >= max(1, int(limit)):
            break
    return out


def _top_narrative_preview(top_narratives: Any, *, limit: int = 3) -> list[dict[str, Any]]:
    if not isinstance(top_narratives, list):
        return []
    out: list[dict[str, Any]] = []
    for item in top_narratives:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "category": str(item.get("category") or "").strip(),
                "score": _metric(item.get("score"), 0.0),
                "reactivated": bool(item.get("reactivated", False)),
                "text": str(item.get("text") or "").strip()[:120],
                "primary_motive": str(item.get("primary_motive") or "").strip(),
                "motive_tension": str(item.get("motive_tension") or "").strip(),
                "counterpart_snapshot": _narrative_counterpart_preview(item.get("counterpart_snapshot")),
                "proactive_continuity": _narrative_proactive_preview(item.get("proactive_continuity")),
            }
        )
        if len(out) >= max(1, int(limit)):
            break
    return out


def _narrative_counterpart_preview(counterpart: Any) -> dict[str, Any]:
    if not isinstance(counterpart, dict) or not counterpart:
        return {}
    preview = {
        "stance": str(counterpart.get("counterpart_stance") or "").strip(),
        "scene": str(counterpart.get("counterpart_scene") or "").strip(),
        "respect_level": _metric(counterpart.get("counterpart_respect_level"), 0.0),
        "reciprocity": _metric(counterpart.get("counterpart_reciprocity"), 0.0),
        "boundary_pressure": _metric(counterpart.get("counterpart_boundary_pressure"), 0.0),
        "reliability_read": _metric(counterpart.get("counterpart_reliability_read"), 0.0),
        "profile": dict(counterpart.get("counterpart_profile"))
        if isinstance(counterpart.get("counterpart_profile"), dict)
        else {},
        "support_count": _int_metric(counterpart.get("counterpart_support_count"), 0),
        "support_mass": _metric(counterpart.get("counterpart_support_mass"), 0.0),
        "confidence_avg": _metric(counterpart.get("counterpart_confidence_avg"), 0.0),
        "fresh_ratio": _metric(counterpart.get("counterpart_fresh_ratio"), 0.0),
    }
    if any(
        (
            preview["stance"],
            preview["scene"],
            preview["profile"],
            preview["support_count"] > 0,
            preview["respect_level"] > 0.0,
            preview["reciprocity"] > 0.0,
            preview["boundary_pressure"] > 0.0,
            preview["reliability_read"] > 0.0,
            preview["support_mass"] > 0.0,
            preview["confidence_avg"] > 0.0,
            preview["fresh_ratio"] > 0.0,
        )
    ):
        return preview
    return {}


def _narrative_proactive_preview(proactive: Any) -> dict[str, Any]:
    if not isinstance(proactive, dict) or not proactive:
        return {}
    preview = {
        "score": _metric(proactive.get("_score"), 0.0),
        "continuity_anchor": _metric(proactive.get("continuity_anchor"), 0.0),
        "own_rhythm_anchor": _metric(proactive.get("own_rhythm_anchor"), 0.0),
        "recontact_anchor": _metric(proactive.get("recontact_anchor"), 0.0),
        "boundary_anchor": _metric(proactive.get("boundary_anchor"), 0.0),
        "memory_anchor": _metric(proactive.get("memory_anchor"), 0.0),
        "semantic_continuity_depth": _metric(proactive.get("semantic_continuity_depth"), 0.0),
        "semantic_identity_gravity": _metric(proactive.get("semantic_identity_gravity"), 0.0),
        "lineage_gravity": _metric(proactive.get("lineage_gravity"), 0.0),
        "contact_lineage": _metric(proactive.get("contact_lineage"), 0.0),
        "repair_lineage": _metric(proactive.get("repair_lineage"), 0.0),
        "boundary_lineage": _metric(proactive.get("boundary_lineage"), 0.0),
        "selfhood_lineage": _metric(proactive.get("selfhood_lineage"), 0.0),
        "agency_lineage": _metric(proactive.get("agency_lineage"), 0.0),
        "long_term_axis_count": _int_metric(proactive.get("long_term_axis_count"), 0),
    }
    if any(
        float(preview.get(key) or 0.0) > 0.0
        for key in preview
        if key != "long_term_axis_count"
    ) or preview["long_term_axis_count"] > 0:
        return preview
    return {}


def _long_term_identity_preview(items: Any, *, limit: int = 3) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "category": str(item.get("category") or "").strip(),
                "score": _metric(item.get("score"), 0.0),
                "horizon_tag": str(item.get("horizon_tag") or "").strip(),
                "text": str(item.get("text") or "").strip()[:120],
                "prompt_text": str(item.get("prompt_text") or "").strip()[:120],
                "primary_motive": str(item.get("primary_motive") or "").strip(),
                "motive_tension": str(item.get("motive_tension") or "").strip(),
                "sedimentation_score": _metric(item.get("sedimentation_score"), 0.0),
                "persistence_score": _metric(item.get("persistence_score"), 0.0),
                "integration_score": _metric(item.get("integration_score"), 0.0),
                "support_span_s": _int_metric(item.get("support_span_s"), 0),
                "reactivation_hits": _int_metric(item.get("reactivation_hits"), 0),
                "identity_strength": _metric(item.get("identity_strength"), 0.0),
                "lineage_depth": _metric(item.get("lineage_depth"), 0.0),
                "counterpart_snapshot": _narrative_counterpart_preview(item.get("counterpart_snapshot")),
                "proactive_continuity": _narrative_proactive_preview(item.get("proactive_continuity")),
            }
        )
        if len(out) >= max(1, int(limit)):
            break
    return out


def _window_profile_summary(profile: Any) -> dict[str, Any]:
    if not isinstance(profile, dict) or not profile:
        return {}
    profile_type = str(profile.get("profile_type") or "").strip()
    if profile_type == "scheduled_window":
        score = _metric(profile.get("maturity"), 0.0)
        required = _metric(profile.get("required_maturity"), 0.0)
        ready = bool(profile.get("invite_ready", False))
        score_label = "maturity"
        required_label = "required_maturity"
        ready_label = "invite_ready"
    elif profile_type == "self_opening":
        score = _metric(profile.get("readiness"), 0.0)
        required = _metric(profile.get("required_readiness"), 0.0)
        ready = bool(profile.get("reopen_ready", False))
        score_label = "readiness"
        required_label = "required_readiness"
        ready_label = "reopen_ready"
    else:
        score = _metric(profile.get("maturity"), 0.0)
        required = _metric(profile.get("required_maturity"), 0.0)
        ready = bool(profile.get("invite_ready", False) or profile.get("reopen_ready", False))
        score_label = "score"
        required_label = "required"
        ready_label = "ready"
    return {
        "profile_type": profile_type,
        "event_kind": str(profile.get("event_kind") or "").strip(),
        "family": str(profile.get("family") or "").strip(),
        "trigger_family": str(profile.get("trigger_family") or "").strip(),
        "stance": str(profile.get("stance") or "").strip(),
        "scene": str(profile.get("scene") or "").strip(),
        "decision": str(profile.get("decision") or "").strip(),
        score_label: score,
        required_label: required,
        "gap": round(score - required, 3),
        ready_label: ready,
        "recheck_min": _int_metric(profile.get("recheck_min"), 0),
        "continuity_bonus": _metric(profile.get("continuity_bonus"), 0.0),
        "continuity_discount": _metric(profile.get("continuity_discount"), 0.0),
        "carryover_mode": str(profile.get("carryover_mode") or "").strip(),
        "carryover_strength": _metric(profile.get("carryover_strength"), 0.0),
        "event_carryover_mode": str(profile.get("event_carryover_mode") or "").strip(),
        "event_carryover_strength": _metric(profile.get("event_carryover_strength"), 0.0),
        "presence_residue": _metric(profile.get("presence_residue"), 0.0),
        "ambient_resonance": _metric(profile.get("ambient_resonance"), 0.0),
        "self_activity_momentum": _metric(profile.get("self_activity_momentum"), 0.0),
        "recontact_echo": _metric(profile.get("recontact_echo"), 0.0),
        "own_rhythm_load": _metric(profile.get("own_rhythm_load"), 0.0),
    }


def _embodied_context_summary(state: Any) -> dict[str, Any]:
    normalized = _digital_body_consequence_summary(state)
    if not normalized:
        return {}
    return {
        "kind": str(normalized.get("kind") or "").strip(),
        "summary": str(normalized.get("summary") or "").strip(),
        "access_mode": str(normalized.get("access_mode") or "").strip(),
        "active_surface": str(normalized.get("active_surface") or "").strip(),
        "requested_access": _clean_list(normalized.get("requested_access"), limit=8),
        "missing_access": _clean_list(normalized.get("missing_access"), limit=8),
        "granted_toolsets": _clean_list(normalized.get("granted_toolsets"), limit=8),
        "active_tools": _clean_list(normalized.get("active_tools"), limit=8),
        "block_reason": str(normalized.get("block_reason") or "").strip(),
        "artifact_continuity": str(normalized.get("artifact_continuity") or "").strip(),
        "active_artifact_kind": str(normalized.get("active_artifact_kind") or "").strip(),
        "active_artifact_ref": str(normalized.get("active_artifact_ref") or "").strip(),
        "active_artifact_label": str(normalized.get("active_artifact_label") or "").strip(),
        "artifact_age_s": _int_metric(normalized.get("artifact_age_s"), 0),
        "artifact_reacquisition_mode": str(normalized.get("artifact_reacquisition_mode") or "").strip(),
        "artifact_carrier": str(normalized.get("artifact_carrier") or "").strip(),
        "artifact_source_ref_ids": _clean_int_list(normalized.get("artifact_source_ref_ids"), limit=8),
        "artifact_source_url": str(normalized.get("artifact_source_url") or "").strip(),
        "artifact_source_query": str(normalized.get("artifact_source_query") or "").strip(),
        "artifact_source_title": str(normalized.get("artifact_source_title") or "").strip(),
        "artifact_source_tool_name": str(normalized.get("artifact_source_tool_name") or "").strip(),
        "primary_proposal_id": str(normalized.get("primary_proposal_id") or "").strip(),
        "primary_status": str(normalized.get("primary_status") or "").strip(),
        "procedural_growth": bool(normalized.get("procedural_growth", False)),
        "environmental_friction": bool(normalized.get("environmental_friction", False)),
        "requested_help": bool(normalized.get("requested_help", False)),
    }


def _history_embodied_context(*sources: Any) -> dict[str, Any]:
    for source in sources:
        if not isinstance(source, dict):
            continue
        for key in ("embodied_context", "digital_body_consequence"):
            candidate = source.get(key)
            if isinstance(candidate, dict):
                embodied = _embodied_context_summary(candidate)
                if embodied:
                    return embodied
    return {}


def _render_embodied_context_text(state: Any) -> str:
    context = _embodied_context_summary(state)
    if not context:
        return ""
    parts = ["bodyfx=" + (str(context.get("kind") or "").strip() or "-")]
    requested_access = _clean_list(context.get("requested_access"), limit=2)
    missing_access = _clean_list(context.get("missing_access"), limit=2)
    granted_toolsets = _clean_list(context.get("granted_toolsets"), limit=2)
    active_tools = _clean_list(context.get("active_tools"), limit=2)
    artifact_continuity = str(context.get("artifact_continuity") or "").strip()
    artifact_kind = str(context.get("active_artifact_kind") or "").strip()
    artifact_label = (
        str(context.get("active_artifact_label") or "").strip()
        or str(context.get("active_artifact_ref") or "").strip()
        or artifact_kind
    )
    artifact_reacquisition = str(context.get("artifact_reacquisition_mode") or "").strip()
    if requested_access:
        parts.append("ask=" + ",".join(requested_access))
    if missing_access:
        parts.append("missing=" + ",".join(missing_access))
    if granted_toolsets:
        parts.append("grant=" + ",".join(granted_toolsets))
    elif active_tools:
        parts.append("tools=" + ",".join(active_tools))
    if artifact_continuity:
        artifact_text = artifact_kind or "artifact"
        if artifact_label:
            artifact_text += ":" + artifact_label[:40]
        artifact_text += ":" + artifact_continuity
        if artifact_reacquisition:
            artifact_text += ":" + artifact_reacquisition
        parts.append(artifact_text)
    if bool(context.get("requested_help", False)):
        parts.append("help=yes")
    if bool(context.get("procedural_growth", False)):
        parts.append("growth=yes")
    if bool(context.get("environmental_friction", False)):
        parts.append("friction=yes")
    status = str(context.get("primary_status") or "").strip()
    if status:
        parts.append("status=" + status)
    return " ".join(parts)


def _interaction_carryover_summary(carryover: Any) -> dict[str, Any]:
    if not isinstance(carryover, dict) or not carryover:
        return {}
    summary = {
        "source": str(carryover.get("source") or "").strip(),
        "source_event_kind": str(carryover.get("source_event_kind") or "").strip(),
        "source_behavior_mode": str(carryover.get("source_behavior_mode") or "").strip(),
        "source_action_target": str(carryover.get("source_action_target") or "").strip(),
        "source_primary_motive": str(carryover.get("source_primary_motive") or "").strip(),
        "source_motive_tension": str(carryover.get("source_motive_tension") or "").strip(),
        "source_goal_frame": str(carryover.get("source_goal_frame") or "").strip(),
        "source_text": str(carryover.get("source_text") or "").strip()[:180],
        "source_tags": _clean_list(carryover.get("source_tags"), limit=10),
        "carryover_mode": str(carryover.get("carryover_mode") or "").strip(),
        "strength": _metric(carryover.get("strength"), 0.0),
        "relationship_weather": str(carryover.get("relationship_weather") or "").strip(),
        "idle_minutes": _int_metric(carryover.get("idle_minutes"), 0),
        "source_turn_gap": _int_metric(carryover.get("source_turn_gap"), 0),
        "attention_target": str(carryover.get("attention_target") or "").strip(),
        "nonverbal_signal": str(carryover.get("nonverbal_signal") or "").strip(),
        "note": str(carryover.get("note") or "").strip(),
        "created_at": _int_metric(carryover.get("created_at"), 0),
    }
    embodied_context = _embodied_context_summary(carryover.get("embodied_context"))
    if embodied_context:
        summary["embodied_context"] = embodied_context
    return summary


def _event_residue_summary(current_event: Any, *, digital_body_consequence: Any = None) -> dict[str, Any]:
    if not isinstance(current_event, dict) or not current_event:
        return {}
    perception = current_event.get("perception") if isinstance(current_event.get("perception"), dict) else {}
    summary = {
        "event_kind": str(current_event.get("kind") or "").strip(),
        "source": str(current_event.get("source") or "").strip(),
        "event_frame": str(current_event.get("event_frame") or "").strip(),
        "response_style_hint": str(current_event.get("response_style_hint") or "").strip(),
        "science_mode": bool(current_event.get("science_mode", False)),
        "continuation_mode": bool(current_event.get("continuation_mode", False)),
        "counterpart_name": str(current_event.get("counterpart_name") or "").strip(),
        "appraisal_label": str(current_event.get("appraisal_label") or "").strip(),
        "appraisal_confidence": _metric(current_event.get("appraisal_confidence"), 0.0),
        "created_at": _int_metric(current_event.get("created_at"), 0),
        "tags": _clean_list(current_event.get("tags"), limit=8),
        "thread_id": str(perception.get("thread_id") or "").strip(),
        "turn_id": str(perception.get("turn_id") or "").strip(),
        "event_id": str(perception.get("event_id") or "").strip(),
        "trigger_family": str(current_event.get("trigger_family") or "").strip(),
        "derived_from_plan_kind": str(current_event.get("derived_from_plan_kind") or "").strip(),
        "commitment_id": _int_metric(current_event.get("commitment_id"), 0),
        "due_at": str(current_event.get("due_at") or "").strip(),
        "carryover_mode": str(current_event.get("carryover_mode") or "").strip(),
        "carryover_strength": _metric(current_event.get("carryover_strength"), 0.0),
        "relationship_weather": str(current_event.get("relationship_weather") or "").strip(),
        "channel": str(perception.get("channel") or "").strip(),
        "modality": str(perception.get("modality") or "").strip(),
        "source_role": str(perception.get("source_role") or "").strip(),
        "trust_tier": str(perception.get("trust_tier") or "").strip(),
        "salience": _metric(perception.get("salience"), 0.0),
        "interruptibility": str(perception.get("interruptibility") or "").strip(),
        "delivery_mode": str(perception.get("delivery_mode") or "").strip(),
        "is_proactive": bool(perception.get("is_proactive", False)),
        "presence_residue": _metric(current_event.get("presence_residue"), 0.0),
        "ambient_resonance": _metric(current_event.get("ambient_resonance"), 0.0),
        "self_activity_momentum": _metric(current_event.get("self_activity_momentum"), 0.0),
        "attention_target_hint": str(current_event.get("attention_target_hint") or "").strip(),
        "nonverbal_signal_hint": str(current_event.get("nonverbal_signal_hint") or "").strip(),
        "scheduled_after_min": _int_metric(current_event.get("scheduled_after_min"), 0),
        "idle_minutes": _int_metric(current_event.get("idle_minutes"), 0),
    }
    embodied = _embodied_context_summary(digital_body_consequence)
    if embodied:
        summary["digital_body_consequence"] = embodied
    return summary


def _agenda_lifecycle_summary(residue: Any) -> dict[str, Any]:
    if not isinstance(residue, dict) or not residue:
        return {}
    summary = {
        "kind": str(residue.get("kind") or "").strip(),
        "source_event_kind": str(residue.get("source_event_kind") or "").strip(),
        "trigger_family": str(residue.get("trigger_family") or "").strip(),
        "carryover_mode": str(residue.get("carryover_mode") or "").strip(),
        "carryover_strength": _metric(residue.get("carryover_strength"), 0.0),
        "relationship_weather": str(residue.get("relationship_weather") or "").strip(),
        "hold_count": _int_metric(residue.get("hold_count"), 0),
        "idle_minutes": _int_metric(residue.get("idle_minutes"), 0),
        "attention_target": str(residue.get("attention_target") or "").strip(),
        "nonverbal_signal": str(residue.get("nonverbal_signal") or "").strip(),
        "presence_residue": _metric(residue.get("presence_residue"), 0.0),
        "ambient_resonance": _metric(residue.get("ambient_resonance"), 0.0),
        "self_activity_momentum": _metric(residue.get("self_activity_momentum"), 0.0),
        "continuity_anchor": _metric(residue.get("continuity_anchor"), 0.0),
        "own_rhythm_anchor": _metric(residue.get("own_rhythm_anchor"), 0.0),
        "recontact_anchor": _metric(residue.get("recontact_anchor"), 0.0),
        "boundary_anchor": _metric(residue.get("boundary_anchor"), 0.0),
        "memory_anchor": _metric(residue.get("memory_anchor"), 0.0),
        "semantic_continuity_depth": _metric(residue.get("semantic_continuity_depth"), 0.0),
        "semantic_identity_gravity": _metric(residue.get("semantic_identity_gravity"), 0.0),
        "lineage_gravity": _metric(residue.get("lineage_gravity"), 0.0),
        "contact_lineage": _metric(residue.get("contact_lineage"), 0.0),
        "repair_lineage": _metric(residue.get("repair_lineage"), 0.0),
        "boundary_lineage": _metric(residue.get("boundary_lineage"), 0.0),
        "selfhood_lineage": _metric(residue.get("selfhood_lineage"), 0.0),
        "agency_lineage": _metric(residue.get("agency_lineage"), 0.0),
        "long_term_axis_count": _int_metric(residue.get("long_term_axis_count"), 0),
        "own_rhythm_bias": _metric(residue.get("own_rhythm_bias"), 0.0),
        "recontact_cooldown": _metric(residue.get("recontact_cooldown"), 0.0),
        "counterpart_scene_bias": str(residue.get("counterpart_scene_bias") or "").strip(),
        "counterpart_boundary_delta": _metric(residue.get("counterpart_boundary_delta"), 0.0),
        "created_at": _int_metric(residue.get("created_at"), 0),
        "source_tags": _clean_list(residue.get("source_tags"), limit=6),
        "note": str(residue.get("note") or "").strip()[:160],
    }
    embodied = _embodied_context_summary(residue.get("embodied_context"))
    if embodied:
        summary["embodied_context"] = embodied
    return summary


def _behavior_consequence_summary(consequence: Any) -> dict[str, Any]:
    if not isinstance(consequence, dict) or not consequence:
        return {}
    summary = {
        "kind": str(consequence.get("kind") or "").strip(),
        "summary": str(consequence.get("summary") or "").strip(),
        "relationship_effect": str(consequence.get("relationship_effect") or "").strip(),
        "self_effect": str(consequence.get("self_effect") or "").strip(),
        "trigger_family": str(consequence.get("trigger_family") or "").strip(),
        "relationship_weather": str(consequence.get("relationship_weather") or "").strip(),
        "carryover_mode": str(consequence.get("carryover_mode") or "").strip(),
        "timing_window_min": _int_metric(consequence.get("timing_window_min"), 0),
        "silent": bool(consequence.get("silent", False)),
        "delayed": bool(consequence.get("delayed", False)),
        "stale_window": bool(consequence.get("stale_window", False)),
    }
    embodied = _embodied_context_summary(consequence.get("embodied_context"))
    if embodied:
        summary["embodied_context"] = embodied
    return summary


def _digital_body_summary(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict) or not state:
        return {}
    access_state = state.get("access_state") if isinstance(state.get("access_state"), dict) else {}
    resource_state = state.get("resource_state") if isinstance(state.get("resource_state"), dict) else {}
    summary = {
        "active_surface": str(state.get("active_surface") or "").strip(),
        "perception_channels": _clean_list(state.get("perception_channels"), limit=8),
        "action_channels": _clean_list(state.get("action_channels"), limit=8),
        "world_surfaces": _clean_list(state.get("world_surfaces"), limit=12),
        "available_toolsets": _clean_list(state.get("available_toolsets"), limit=8),
        "active_tools": _clean_list(state.get("active_tools"), limit=8),
        "access": {
            "mode": str(access_state.get("mode") or "").strip(),
            "conditions": _clean_list(access_state.get("conditions"), limit=8),
            "block_reason": str(access_state.get("block_reason") or "").strip(),
            "retry_after_s": _int_metric(access_state.get("retry_after_s"), 0),
            "cooldown_scope": str(access_state.get("cooldown_scope") or "").strip(),
            "session_continuity": str(access_state.get("session_continuity") or "").strip(),
            "session_expires_in_s": _int_metric(access_state.get("session_expires_in_s"), 0),
            "session_recovery_mode": str(access_state.get("session_recovery_mode") or "").strip(),
            "pending_approval_count": _int_metric(access_state.get("pending_approval_count"), 0),
            "external_mutation_pending": bool(access_state.get("external_mutation_pending", False)),
            "granted_toolsets": _clean_list(access_state.get("granted_toolsets"), limit=8),
            "missing_access": _clean_list(access_state.get("missing_access"), limit=8),
            "requestable_access": _clean_list(access_state.get("requestable_access"), limit=8),
            "browser_session": str(access_state.get("browser_session") or "").strip(),
            "account_state": str(access_state.get("account_state") or "").strip(),
            "cookie_state": str(access_state.get("cookie_state") or "").strip(),
            "api_key_state": str(access_state.get("api_key_state") or "").strip(),
            "quota_state": str(access_state.get("quota_state") or "").strip(),
            "filesystem_state": str(access_state.get("filesystem_state") or "").strip(),
            "sandbox_mode": str(access_state.get("sandbox_mode") or "").strip(),
            "network_access": str(access_state.get("network_access") or "").strip(),
            "access_acquire_proposals": _clean_access_acquire_proposals(access_state.get("access_acquire_proposals"), limit=8),
            "selected_access_proposal": _clean_access_acquire_proposal(access_state.get("selected_access_proposal")),
        },
        "resources": {
            "behavior_queue_depth": _int_metric(resource_state.get("behavior_queue_depth"), 0),
            "action_packet_count": _int_metric(resource_state.get("action_packet_count"), 0),
            "pending_approval_count": _int_metric(resource_state.get("pending_approval_count"), 0),
            "queued_packet_count": _int_metric(resource_state.get("queued_packet_count"), 0),
            "executing_packet_count": _int_metric(resource_state.get("executing_packet_count"), 0),
            "completed_packet_count": _int_metric(resource_state.get("completed_packet_count"), 0),
            "blocked_packet_count": _int_metric(resource_state.get("blocked_packet_count"), 0),
            "external_tool_count": _int_metric(resource_state.get("external_tool_count"), 0),
            "artifact_continuity": str(resource_state.get("artifact_continuity") or "").strip(),
            "active_artifact_kind": str(resource_state.get("active_artifact_kind") or "").strip(),
            "active_artifact_ref": str(resource_state.get("active_artifact_ref") or "").strip(),
            "active_artifact_label": str(resource_state.get("active_artifact_label") or "").strip(),
            "artifact_age_s": _int_metric(resource_state.get("artifact_age_s"), 0),
            "artifact_reacquisition_mode": str(resource_state.get("artifact_reacquisition_mode") or "").strip(),
            "artifact_carrier": str(resource_state.get("artifact_carrier") or "").strip(),
            "artifact_source_ref_ids": _clean_int_list(resource_state.get("artifact_source_ref_ids"), limit=8),
            "artifact_source_url": str(resource_state.get("artifact_source_url") or "").strip(),
            "artifact_source_query": str(resource_state.get("artifact_source_query") or "").strip(),
            "artifact_source_title": str(resource_state.get("artifact_source_title") or "").strip(),
            "artifact_source_tool_name": str(resource_state.get("artifact_source_tool_name") or "").strip(),
        },
        "constraints": _clean_list(state.get("body_constraints"), limit=8),
    }
    if any(
        (
            summary["active_surface"],
            summary["perception_channels"],
            summary["action_channels"],
            summary["world_surfaces"],
            summary["available_toolsets"],
            summary["active_tools"],
            summary["access"]["mode"],
            summary["access"]["conditions"],
            summary["access"]["block_reason"],
            summary["access"]["retry_after_s"] > 0,
            summary["access"]["cooldown_scope"],
            summary["access"]["session_continuity"],
            summary["access"]["session_expires_in_s"] > 0,
            summary["access"]["session_recovery_mode"],
            summary["access"]["pending_approval_count"] > 0,
            summary["access"]["external_mutation_pending"],
            summary["access"]["granted_toolsets"],
            summary["access"]["missing_access"],
            summary["access"]["requestable_access"],
            summary["access"]["browser_session"],
            summary["access"]["account_state"],
            summary["access"]["cookie_state"],
            summary["access"]["api_key_state"],
            summary["access"]["quota_state"],
            summary["access"]["filesystem_state"],
            summary["access"]["sandbox_mode"],
            summary["access"]["network_access"],
            summary["access"]["access_acquire_proposals"],
            summary["access"]["selected_access_proposal"],
            summary["resources"]["behavior_queue_depth"] > 0,
            summary["resources"]["action_packet_count"] > 0,
            summary["resources"]["pending_approval_count"] > 0,
            summary["resources"]["queued_packet_count"] > 0,
            summary["resources"]["executing_packet_count"] > 0,
            summary["resources"]["completed_packet_count"] > 0,
            summary["resources"]["blocked_packet_count"] > 0,
            summary["resources"]["external_tool_count"] > 0,
            summary["resources"]["artifact_continuity"],
            summary["resources"]["active_artifact_kind"],
            summary["resources"]["active_artifact_ref"],
            summary["resources"]["active_artifact_label"],
            summary["resources"]["artifact_age_s"] > 0,
            summary["resources"]["artifact_reacquisition_mode"],
            summary["resources"]["artifact_carrier"],
            summary["resources"]["artifact_source_ref_ids"],
            summary["resources"]["artifact_source_url"],
            summary["resources"]["artifact_source_query"],
            summary["resources"]["artifact_source_title"],
            summary["resources"]["artifact_source_tool_name"],
            summary["constraints"],
        )
    ):
        return summary
    return {}


def _digital_body_consequence_summary(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict) or not state:
        return {}
    summary = {
        "kind": str(state.get("kind") or "").strip(),
        "summary": str(state.get("summary") or "").strip()[:220],
        "access_mode": str(state.get("access_mode") or "").strip(),
        "active_surface": str(state.get("active_surface") or "").strip(),
        "world_surfaces": _clean_list(state.get("world_surfaces"), limit=12),
        "missing_access": _clean_list(state.get("missing_access"), limit=8),
        "requested_access": _clean_list(state.get("requested_access"), limit=8),
        "granted_toolsets": _clean_list(state.get("granted_toolsets"), limit=8),
        "active_tools": _clean_list(state.get("active_tools"), limit=8),
        "block_reason": str(state.get("block_reason") or "").strip()[:220],
        "retry_after_s": _int_metric(state.get("retry_after_s"), 0),
        "cooldown_scope": str(state.get("cooldown_scope") or "").strip(),
        "session_continuity": str(state.get("session_continuity") or "").strip(),
        "session_expires_in_s": _int_metric(state.get("session_expires_in_s"), 0),
        "session_recovery_mode": str(state.get("session_recovery_mode") or "").strip(),
        "artifact_continuity": str(state.get("artifact_continuity") or "").strip(),
        "active_artifact_kind": str(state.get("active_artifact_kind") or "").strip(),
        "active_artifact_ref": str(state.get("active_artifact_ref") or "").strip()[:220],
        "active_artifact_label": str(state.get("active_artifact_label") or "").strip()[:160],
        "artifact_age_s": _int_metric(state.get("artifact_age_s"), 0),
        "artifact_reacquisition_mode": str(state.get("artifact_reacquisition_mode") or "").strip(),
        "artifact_carrier": str(state.get("artifact_carrier") or "").strip(),
        "artifact_source_ref_ids": _clean_int_list(state.get("artifact_source_ref_ids"), limit=8),
        "artifact_source_url": str(state.get("artifact_source_url") or "").strip()[:320],
        "artifact_source_query": str(state.get("artifact_source_query") or "").strip()[:220],
        "artifact_source_title": str(state.get("artifact_source_title") or "").strip()[:160],
        "artifact_source_tool_name": str(state.get("artifact_source_tool_name") or "").strip(),
        "primary_proposal_id": str(state.get("primary_proposal_id") or "").strip(),
        "primary_status": str(state.get("primary_status") or "").strip(),
        "primary_origin": str(state.get("primary_origin") or "").strip(),
        "primary_intent": str(state.get("primary_intent") or "").strip(),
        "primary_tool_name": str(state.get("primary_tool_name") or "").strip(),
        "procedural_growth": bool(state.get("procedural_growth", False)),
        "environmental_friction": bool(state.get("environmental_friction", False)),
        "requested_help": bool(state.get("requested_help", False)),
        "access_acquire_proposals": _clean_access_acquire_proposals(state.get("access_acquire_proposals"), limit=8),
        "selected_access_proposal": _clean_access_acquire_proposal(state.get("selected_access_proposal")),
    }
    if any(
        (
            summary["kind"],
            summary["summary"],
            summary["access_mode"],
            summary["active_surface"],
            summary["world_surfaces"],
            summary["missing_access"],
            summary["requested_access"],
            summary["granted_toolsets"],
            summary["active_tools"],
            summary["block_reason"],
            summary["retry_after_s"] > 0,
            summary["cooldown_scope"],
            summary["session_continuity"],
            summary["session_expires_in_s"] > 0,
            summary["session_recovery_mode"],
            summary["artifact_continuity"],
            summary["active_artifact_kind"],
            summary["active_artifact_ref"],
            summary["active_artifact_label"],
            summary["artifact_age_s"] > 0,
            summary["artifact_reacquisition_mode"],
            summary["artifact_carrier"],
            summary["artifact_source_ref_ids"],
            summary["artifact_source_url"],
            summary["artifact_source_query"],
            summary["artifact_source_title"],
            summary["artifact_source_tool_name"],
            summary["primary_proposal_id"],
            summary["primary_status"],
            summary["primary_origin"],
            summary["primary_intent"],
            summary["primary_tool_name"],
            summary["procedural_growth"],
            summary["environmental_friction"],
            summary["requested_help"],
            summary["access_acquire_proposals"],
            summary["selected_access_proposal"],
        )
    ):
        return summary
    return {}


def build_behavior_queue_cli_summary(queue: Any, *, limit: int = 3) -> list[dict[str, Any]]:
    if not isinstance(queue, list):
        return []
    out: list[dict[str, Any]] = []
    for item in queue:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip()
        if not kind:
            continue
        out.append(
            {
                "agenda_id": str(item.get("agenda_id") or "").strip(),
                "kind": kind,
                "target": str(item.get("target") or "").strip(),
                "status": str(item.get("status") or "").strip(),
                "trigger_family": str(item.get("trigger_family") or "").strip(),
                "scheduled_after_min": _int_metric(item.get("scheduled_after_min"), 0),
                "expires_after_min": _int_metric(item.get("expires_after_min"), 0),
                "priority": _metric(item.get("priority"), 0.0),
                "base_priority": _metric(item.get("base_priority"), 0.0),
                "hold_count": _int_metric(item.get("hold_count"), 0),
                "last_recheck_at_min": _int_metric(item.get("last_recheck_at_min"), 0),
                "allow_interrupt": bool(item.get("allow_interrupt", True)),
                "primary_motive": str(item.get("primary_motive") or "").strip(),
                "motive_tension": str(item.get("motive_tension") or "").strip(),
                "goal_frame": str(item.get("goal_frame") or "").strip()[:160],
                "source_event_kind": str(item.get("source_event_kind") or "").strip(),
                "created_at": _int_metric(item.get("created_at"), 0),
                "carryover_mode": str(item.get("carryover_mode") or "").strip(),
                "carryover_strength": _metric(item.get("carryover_strength"), 0.0),
                "relationship_weather": str(item.get("relationship_weather") or "").strip(),
                "presence_residue": _metric(item.get("presence_residue"), 0.0),
                "ambient_resonance": _metric(item.get("ambient_resonance"), 0.0),
                "self_activity_momentum": _metric(item.get("self_activity_momentum"), 0.0),
                "attention_target": str(item.get("attention_target") or "").strip(),
                "nonverbal_signal": str(item.get("nonverbal_signal") or "").strip(),
                "continuity_anchor": _metric(item.get("continuity_anchor"), 0.0),
                "own_rhythm_anchor": _metric(item.get("own_rhythm_anchor"), 0.0),
                "recontact_anchor": _metric(item.get("recontact_anchor"), 0.0),
                "boundary_anchor": _metric(item.get("boundary_anchor"), 0.0),
                "memory_anchor": _metric(item.get("memory_anchor"), 0.0),
                "semantic_continuity_depth": _metric(item.get("semantic_continuity_depth"), 0.0),
                "semantic_identity_gravity": _metric(item.get("semantic_identity_gravity"), 0.0),
                "lineage_gravity": _metric(item.get("lineage_gravity"), 0.0),
                "contact_lineage": _metric(item.get("contact_lineage"), 0.0),
                "repair_lineage": _metric(item.get("repair_lineage"), 0.0),
                "boundary_lineage": _metric(item.get("boundary_lineage"), 0.0),
                "selfhood_lineage": _metric(item.get("selfhood_lineage"), 0.0),
                "agency_lineage": _metric(item.get("agency_lineage"), 0.0),
                "long_term_axis_count": _int_metric(item.get("long_term_axis_count"), 0),
                "note": str(item.get("note") or "").strip()[:160],
            }
        )
        if len(out) >= max(1, int(limit)):
            break
    return out


def render_action_packet_cli_text(packets: Any, *, limit: int = 4) -> str:
    if not isinstance(packets, list) or not packets:
        return "- no action packets"
    rows: list[str] = []
    for item in packets[: max(1, int(limit))]:
        if not isinstance(item, dict):
            continue
        proposal_id = str(item.get("proposal_id") or "").strip() or "-"
        intent = str(item.get("intent") or "").strip() or "-"
        status = str(item.get("status") or "").strip() or "-"
        risk = str(item.get("risk") or "").strip() or "-"
        origin = str(item.get("origin") or "").strip() or "-"
        effect = str(item.get("expected_effect") or item.get("result_summary") or "").strip()
        line = f"- {proposal_id} | {origin} | {intent} | {status} | {risk}"
        if effect:
            line += " | " + effect[:120]
        rows.append(line)
    return "\n".join(rows) if rows else "- no action packets"


def render_autonomy_cli_text(autonomy: Any) -> str:
    if not isinstance(autonomy, dict) or not autonomy:
        return "- no autonomy state"
    intent = autonomy.get("intent") if isinstance(autonomy.get("intent"), dict) else {}
    pending = autonomy.get("pending_approval") if isinstance(autonomy.get("pending_approval"), dict) else {}
    trace = autonomy.get("execution_trace") if isinstance(autonomy.get("execution_trace"), list) else []
    block_reason = str(autonomy.get("block_reason") or "").strip()
    parts = [
        "mode=" + (str(intent.get("mode") or "").strip() or "-"),
        "origin=" + (str(intent.get("origin") or "").strip() or "-"),
        "confidence=" + f"{_metric(intent.get('confidence'), 0.0):.3f}",
        "packets=" + str(len(autonomy.get("action_packets") if isinstance(autonomy.get("action_packets"), list) else [])),
    ]
    if pending:
        parts.append("pending=" + (str(pending.get("proposal_id") or "").strip() or "-"))
    if trace:
        last = trace[-1] if isinstance(trace[-1], dict) else {}
        if last:
            parts.append("last=" + (str(last.get("event") or "").strip() or "-"))
    if block_reason:
        parts.append("block=" + block_reason[:80])
    return " | ".join(parts)


def render_behavior_queue_cli_text(queue: Any, *, limit: int = 3) -> str:
    rows = build_behavior_queue_cli_summary(queue, limit=limit)
    if not rows:
        return "- (empty)"
    lines: list[str] = []
    for idx, row in enumerate(rows, start=1):
        header = (
            f"- #{idx} {row['kind']}"
            + (f"/{row['trigger_family']}" if row.get("trigger_family") else "")
            + f" status={row['status'] or 'pending'}"
            + f" p={_metric(row.get('priority'), 0.0):.3f}"
            + f" after={_int_metric(row.get('scheduled_after_min'), 0)}m"
        )
        if _int_metric(row.get("expires_after_min"), 0) > 0:
            header += f" exp={_int_metric(row.get('expires_after_min'), 0)}m"
        if _int_metric(row.get("hold_count"), 0) > 0:
            header += f" holds={_int_metric(row.get('hold_count'), 0)}"
        lines.append(header)
        residue = (
            f"  carry={row['carryover_mode'] or '-'}:{_metric(row.get('carryover_strength'), 0.0):.3f}"
            + f" residue={_metric(row.get('presence_residue'), 0.0):.3f}/"
            + f"{_metric(row.get('ambient_resonance'), 0.0):.3f}/"
            + f"{_metric(row.get('self_activity_momentum'), 0.0):.3f}"
        )
        if row.get("relationship_weather"):
            residue += f" weather={row['relationship_weather']}"
        if row.get("attention_target"):
            residue += f" target={row['attention_target']}"
        if row.get("source_event_kind"):
            residue += f" event={row['source_event_kind']}"
        if not bool(row.get("allow_interrupt", True)):
            residue += " interrupt=no"
        lines.append(residue)
        motive_bits = [str(row.get("primary_motive") or "").strip(), str(row.get("motive_tension") or "").strip()]
        motive_bits = [bit for bit in motive_bits if bit]
        if motive_bits or row.get("goal_frame"):
            detail = ""
            if motive_bits:
                detail += "  motive=" + " / ".join(motive_bits)
            if row.get("goal_frame"):
                detail += (" | " if detail else "  ") + f"goal={row['goal_frame']}"
            lines.append(detail)
        has_anchor_signal = any(
            float(row.get(key) or 0.0) > 0.0
            for key in (
                "continuity_anchor",
                "own_rhythm_anchor",
                "recontact_anchor",
                "boundary_anchor",
                "memory_anchor",
                "semantic_continuity_depth",
                "semantic_identity_gravity",
                "lineage_gravity",
                "contact_lineage",
                "repair_lineage",
                "boundary_lineage",
                "selfhood_lineage",
                "agency_lineage",
            )
        ) or _int_metric(row.get("long_term_axis_count"), 0) > 0
        if has_anchor_signal:
            lines.append(
                "  anchors="
                + f"{_metric(row.get('continuity_anchor'), 0.0):.2f}/"
                + f"{_metric(row.get('own_rhythm_anchor'), 0.0):.2f}/"
                + f"{_metric(row.get('recontact_anchor'), 0.0):.2f}/"
                + f"{_metric(row.get('boundary_anchor'), 0.0):.2f}/"
                + f"{_metric(row.get('memory_anchor'), 0.0):.2f}"
                + " semantic="
                + f"{_metric(row.get('semantic_continuity_depth'), 0.0):.2f}/"
                + f"{_metric(row.get('semantic_identity_gravity'), 0.0):.2f}"
            )
            lines.append(
                "  lineage="
                + f"{_metric(row.get('lineage_gravity'), 0.0):.2f}/"
                + f"{_metric(row.get('contact_lineage'), 0.0):.2f}/"
                + f"{_metric(row.get('repair_lineage'), 0.0):.2f}/"
                + f"{_metric(row.get('boundary_lineage'), 0.0):.2f}/"
                + f"{_metric(row.get('selfhood_lineage'), 0.0):.2f}/"
                + f"{_metric(row.get('agency_lineage'), 0.0):.2f}"
                + f" axes={_int_metric(row.get('long_term_axis_count'), 0)}"
            )
        if row.get("note"):
            lines.append(f"  note={row['note']}")
    return "\n".join(lines)


def build_counterpart_assessment_cli_summary(history: Any, *, limit: int = 5) -> list[dict[str, Any]]:
    if not isinstance(history, list):
        return []
    out: list[dict[str, Any]] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        content = item.get("content") if isinstance(item.get("content"), dict) else {}
        summary = str(content.get("summary") or item.get("summary") or "").strip()
        stance = str(content.get("stance") or item.get("stance") or "").strip().lower()
        scene = str(content.get("scene") or item.get("scene") or "").strip().lower()
        if not any((summary, stance, scene)):
            continue
        row = {
            "id": _int_metric(item.get("id"), 0),
            "summary": summary,
            "stance": stance,
            "scene": scene,
            "created_at": _int_metric(content.get("created_at", item.get("created_at")), 0),
            "respect_level": _metric(content.get("respect_level", item.get("respect_level")), 0.5),
            "reciprocity": _metric(content.get("reciprocity", item.get("reciprocity")), 0.5),
            "boundary_pressure": _metric(content.get("boundary_pressure", item.get("boundary_pressure")), 0.1),
            "reliability_read": _metric(content.get("reliability_read", item.get("reliability_read")), 0.5),
            "event_kind": str(content.get("event_kind") or item.get("event_kind") or "").strip(),
            "interaction_frame": str(content.get("interaction_frame") or item.get("interaction_frame") or "").strip(),
            "primary_motive": str(content.get("primary_motive") or item.get("primary_motive") or "").strip(),
            "motive_tension": str(content.get("motive_tension") or item.get("motive_tension") or "").strip(),
            "goal_frame": str(content.get("goal_frame") or item.get("goal_frame") or "").strip(),
        }
        profile = _counterpart_assessment_profile({**row, "assessment_profile": content.get("assessment_profile") or item.get("assessment_profile")})
        if profile:
            row["assessment_profile"] = profile
        embodied_context = _history_embodied_context(content, item)
        if embodied_context:
            row["embodied_context"] = embodied_context
        out.append(row)
    capped = max(1, int(limit))
    return out[-capped:]


def render_counterpart_assessment_cli_text(history: Any, *, limit: int = 5) -> str:
    rows = build_counterpart_assessment_cli_summary(history, limit=limit)
    if not rows:
        return "- (empty)"
    lines: list[str] = []
    for row in rows:
        header = (
            f"- #{row['id']} {row['stance'] or '-'}"
            + (f"/{row['scene']}" if row.get("scene") else "")
            + f" respect={_metric(row.get('respect_level'), 0.5):.2f}"
            + f" reciprocity={_metric(row.get('reciprocity'), 0.5):.2f}"
            + f" pressure={_metric(row.get('boundary_pressure'), 0.1):.2f}"
            + f" reliability={_metric(row.get('reliability_read'), 0.5):.2f}"
        )
        if row.get("event_kind"):
            header += f" event={row['event_kind']}"
        if row.get("interaction_frame"):
            header += f" frame={row['interaction_frame']}"
        lines.append(header)
        if row.get("summary"):
            lines.append(f"  {row['summary']}")
        profile = row.get("assessment_profile") if isinstance(row.get("assessment_profile"), dict) else {}
        if profile:
            scene_strengths = profile.get("scene_strengths") if isinstance(profile.get("scene_strengths"), dict) else {}
            dominant = str(profile.get("dominant_scene_signal") or "").strip()
            dominant_score = _metric(scene_strengths.get(dominant), 0.0) if dominant else 0.0
            lines.append(
                "  read="
                + (f"{dominant}:{dominant_score:.2f} " if dominant else "")
                + f"open={_metric(profile.get('openness_drive'), 0.0):.2f} "
                + f"guard={_metric(profile.get('guarded_drive'), 0.0):.2f} "
                + f"margin={_metric(profile.get('guard_margin'), 0.0):.2f}"
            )
            lines.append(
                "  counterpart="
                + f"safe={_metric(profile.get('safety_read'), 0.0):.2f} "
                + f"repair={_metric(profile.get('repairability'), 0.0):.2f} "
                + f"predict={_metric(profile.get('predictability'), 0.0):.2f} "
                + f"risk={_metric(profile.get('dependency_risk'), 0.0):.2f} "
                + f"close={_metric(profile.get('closeness_read'), 0.0):.2f}"
            )
        embodied_line = _render_embodied_context_text(row.get("embodied_context"))
        if embodied_line:
            lines.append("  " + embodied_line)
        motive_bits = [str(row.get("primary_motive") or "").strip(), str(row.get("motive_tension") or "").strip()]
        motive_bits = [bit for bit in motive_bits if bit]
        if motive_bits or row.get("goal_frame"):
            detail = ""
            if motive_bits:
                detail += "  motive=" + " / ".join(motive_bits)
            if row.get("goal_frame"):
                detail += (" | " if detail else "  ") + f"goal={row['goal_frame']}"
            lines.append(detail)
    return "\n".join(lines)


def build_proactive_continuity_cli_summary(history: Any, *, limit: int = 5) -> list[dict[str, Any]]:
    if not isinstance(history, list):
        return []
    out: list[dict[str, Any]] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        content = item.get("content") if isinstance(item.get("content"), dict) else {}
        summary = str(content.get("summary") or item.get("summary") or "").strip()
        kind = str(content.get("kind") or item.get("kind") or "").strip().lower()
        trace_family = str(content.get("trace_family") or item.get("trace_family") or "").strip().lower()
        carryover_mode = str(content.get("carryover_mode") or item.get("carryover_mode") or "").strip().lower()
        if not any((summary, kind, trace_family, carryover_mode)):
            continue
        row = {
            "id": _int_metric(item.get("id"), 0),
            "summary": summary,
            "kind": kind,
            "trace_family": trace_family,
            "source_event_kind": str(content.get("source_event_kind") or item.get("source_event_kind") or "").strip().lower(),
            "trigger_family": str(content.get("trigger_family") or item.get("trigger_family") or "").strip().lower(),
            "carryover_mode": carryover_mode,
            "relationship_weather": str(content.get("relationship_weather") or item.get("relationship_weather") or "").strip().lower(),
            "counterpart_scene_bias": str(content.get("counterpart_scene_bias") or item.get("counterpart_scene_bias") or "").strip().lower(),
            "hold_count": _int_metric(content.get("hold_count", item.get("hold_count")), 0),
            "carryover_strength": _metric(content.get("carryover_strength", item.get("carryover_strength")), 0.0),
            "recontact_cooldown": _metric(content.get("recontact_cooldown", item.get("recontact_cooldown")), 0.0),
            "presence_residue": _metric(content.get("presence_residue", item.get("presence_residue")), 0.0),
            "ambient_resonance": _metric(content.get("ambient_resonance", item.get("ambient_resonance")), 0.0),
            "self_activity_momentum": _metric(content.get("self_activity_momentum", item.get("self_activity_momentum")), 0.0),
            "continuity_anchor": _metric(content.get("continuity_anchor", item.get("continuity_anchor")), 0.0),
            "own_rhythm_anchor": _metric(content.get("own_rhythm_anchor", item.get("own_rhythm_anchor")), 0.0),
            "recontact_anchor": _metric(content.get("recontact_anchor", item.get("recontact_anchor")), 0.0),
            "boundary_anchor": _metric(content.get("boundary_anchor", item.get("boundary_anchor")), 0.0),
            "memory_anchor": _metric(content.get("memory_anchor", item.get("memory_anchor")), 0.0),
            "semantic_continuity_depth": _metric(
                content.get("semantic_continuity_depth", item.get("semantic_continuity_depth")), 0.0
            ),
            "semantic_identity_gravity": _metric(
                content.get("semantic_identity_gravity", item.get("semantic_identity_gravity")), 0.0
            ),
            "lineage_gravity": _metric(content.get("lineage_gravity", item.get("lineage_gravity")), 0.0),
            "contact_lineage": _metric(content.get("contact_lineage", item.get("contact_lineage")), 0.0),
            "repair_lineage": _metric(content.get("repair_lineage", item.get("repair_lineage")), 0.0),
            "boundary_lineage": _metric(content.get("boundary_lineage", item.get("boundary_lineage")), 0.0),
            "selfhood_lineage": _metric(content.get("selfhood_lineage", item.get("selfhood_lineage")), 0.0),
            "agency_lineage": _metric(content.get("agency_lineage", item.get("agency_lineage")), 0.0),
            "long_term_axis_count": _int_metric(content.get("long_term_axis_count", item.get("long_term_axis_count")), 0),
            "own_rhythm_bias": _metric(content.get("own_rhythm_bias", item.get("own_rhythm_bias")), 0.0),
            "counterpart_boundary_delta": _metric(content.get("counterpart_boundary_delta", item.get("counterpart_boundary_delta")), 0.0),
            "created_at": _int_metric(content.get("created_at", item.get("created_at")), 0),
            "primary_motive": str(content.get("primary_motive") or item.get("primary_motive") or "").strip(),
            "motive_tension": str(content.get("motive_tension") or item.get("motive_tension") or "").strip(),
            "goal_frame": str(content.get("goal_frame") or item.get("goal_frame") or "").strip(),
        }
        embodied_context = _history_embodied_context(content, item)
        if embodied_context:
            row["embodied_context"] = embodied_context
        out.append(row)
    capped = max(1, int(limit))
    return out[-capped:]


def render_proactive_continuity_cli_text(history: Any, *, limit: int = 5) -> str:
    rows = build_proactive_continuity_cli_summary(history, limit=limit)
    if not rows:
        return "- (empty)"
    lines: list[str] = []
    for row in rows:
        header = f"- #{row['id']} {row['trace_family'] or '-'}"
        if row.get("kind"):
            header += f"/{row['kind']}"
        header += (
            f" carry={row['carryover_mode'] or '-'}:{_metric(row.get('carryover_strength'), 0.0):.2f}"
            + f" hold={_int_metric(row.get('hold_count'), 0)}"
            + f" own={_metric(row.get('own_rhythm_bias'), 0.0):.2f}"
            + f" self={_metric(row.get('self_activity_momentum'), 0.0):.2f}"
        )
        if row.get("trigger_family"):
            header += f" trigger={row['trigger_family']}"
        if row.get("source_event_kind"):
            header += f" event={row['source_event_kind']}"
        lines.append(header)
        detail = (
            f"  residue={_metric(row.get('presence_residue'), 0.0):.2f}/"
            + f"{_metric(row.get('ambient_resonance'), 0.0):.2f}"
            + f" cooldown={_metric(row.get('recontact_cooldown'), 0.0):.2f}"
        )
        if row.get("relationship_weather"):
            detail += f" weather={row['relationship_weather']}"
        if row.get("counterpart_scene_bias"):
            detail += f" scene={row['counterpart_scene_bias']}"
        lines.append(detail)
        if any(
            float(row.get(key) or 0.0) > 0.0
            for key in (
                "continuity_anchor",
                "own_rhythm_anchor",
                "recontact_anchor",
                "boundary_anchor",
                "memory_anchor",
                "lineage_gravity",
                "contact_lineage",
                "repair_lineage",
                "boundary_lineage",
                "selfhood_lineage",
                "agency_lineage",
            )
        ) or _int_metric(row.get("long_term_axis_count"), 0) > 0:
            lines.append(
                "  anchors="
                + f"{_metric(row.get('continuity_anchor'), 0.0):.2f}/"
                + f"{_metric(row.get('own_rhythm_anchor'), 0.0):.2f}/"
                + f"{_metric(row.get('recontact_anchor'), 0.0):.2f}/"
                + f"{_metric(row.get('boundary_anchor'), 0.0):.2f}/"
                + f"{_metric(row.get('memory_anchor'), 0.0):.2f}"
                + " semantic="
                + f"{_metric(row.get('semantic_continuity_depth'), 0.0):.2f}/"
                + f"{_metric(row.get('semantic_identity_gravity'), 0.0):.2f}"
                + " lineage="
                + f"{_metric(row.get('lineage_gravity'), 0.0):.2f}/"
                + f"{_metric(row.get('contact_lineage'), 0.0):.2f}/"
                + f"{_metric(row.get('repair_lineage'), 0.0):.2f}/"
                + f"{_metric(row.get('boundary_lineage'), 0.0):.2f}/"
                + f"{_metric(row.get('selfhood_lineage'), 0.0):.2f}/"
                + f"{_metric(row.get('agency_lineage'), 0.0):.2f}"
                + f" axes={_int_metric(row.get('long_term_axis_count'), 0)}"
            )
        embodied_line = _render_embodied_context_text(row.get("embodied_context"))
        if embodied_line:
            lines.append("  " + embodied_line)
        if row.get("summary"):
            lines.append(f"  {row['summary']}")
        motive_bits = [str(row.get("primary_motive") or "").strip(), str(row.get("motive_tension") or "").strip()]
        motive_bits = [bit for bit in motive_bits if bit]
        if motive_bits or row.get("goal_frame"):
            extra = ""
            if motive_bits:
                extra += "  motive=" + " / ".join(motive_bits)
            if row.get("goal_frame"):
                extra += (" | " if extra else "  ") + f"goal={row['goal_frame']}"
            lines.append(extra)
    return "\n".join(lines)


def _frozen_counterpart_snapshot(reconsolidation_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    recon = dict(reconsolidation_snapshot or {})
    counterpart = recon.get("counterpart")
    return dict(counterpart) if isinstance(counterpart, dict) else {}


def _frozen_semantic_anchor_bundle(reconsolidation_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    recon = dict(reconsolidation_snapshot or {})
    bundle = recon.get("semantic_anchor_bundle")
    if isinstance(bundle, dict):
        snapshot = {
            key: _metric(bundle.get(key), 0.0)
            for key in _SEMANTIC_ANCHOR_FLOAT_KEYS
        }
        snapshot["long_term_axis_count"] = _int_metric(bundle.get("long_term_axis_count"), 0)
        if any(float(snapshot.get(key) or 0.0) > 0.0 for key in _SEMANTIC_ANCHOR_FLOAT_KEYS) or snapshot["long_term_axis_count"] > 0:
            return snapshot

    continuity = recon.get("semantic_continuity")
    if not isinstance(continuity, dict):
        return {}
    lineage_snapshot = continuity.get("lineage_snapshot") if isinstance(continuity.get("lineage_snapshot"), dict) else {}
    return {
        "continuity_anchor": 0.0,
        "own_rhythm_anchor": 0.0,
        "recontact_anchor": 0.0,
        "boundary_anchor": 0.0,
        "memory_anchor": 0.0,
        "semantic_continuity_depth": _metric(continuity.get("continuity_depth"), 0.0),
        "semantic_identity_gravity": _metric(continuity.get("identity_gravity"), 0.0),
        "lineage_gravity": _metric(continuity.get("lineage_gravity"), 0.0),
        "contact_lineage": max(
            _metric(lineage_snapshot.get("bond_style"), 0.0),
            _metric(lineage_snapshot.get("presence_style"), 0.0),
            _metric(lineage_snapshot.get("commitment_style"), 0.0),
            _metric(lineage_snapshot.get("repair_style"), 0.0),
        ),
        "repair_lineage": max(
            _metric(lineage_snapshot.get("repair_style"), 0.0),
            _metric(lineage_snapshot.get("commitment_style"), 0.0),
            _metric(lineage_snapshot.get("bond_style"), 0.0),
        ),
        "boundary_lineage": max(
            _metric(lineage_snapshot.get("boundary_style"), 0.0),
            _metric(lineage_snapshot.get("selfhood_style"), 0.0),
        ),
        "selfhood_lineage": max(
            _metric(lineage_snapshot.get("selfhood_style"), 0.0),
            _metric(lineage_snapshot.get("agency_style"), 0.0),
            _metric(lineage_snapshot.get("rhythm_style"), 0.0),
        ),
        "agency_lineage": max(
            _metric(lineage_snapshot.get("agency_style"), 0.0),
            _metric(lineage_snapshot.get("rhythm_style"), 0.0),
            _metric(lineage_snapshot.get("selfhood_style"), 0.0),
        ),
        "long_term_axis_count": 0,
    }


def build_evolution_cli_summary(
    *,
    relationship: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
    emotion_state: dict[str, Any] | None = None,
    bond_state: dict[str, Any] | None = None,
    counterpart_assessment: dict[str, Any] | None = None,
    behavior_action: dict[str, Any] | None = None,
    behavior_plan: dict[str, Any] | None = None,
    behavior_queue: list[dict[str, Any]] | None = None,
    interaction_carryover: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
    worldline_focus: list[dict[str, Any]] | None = None,
    reconsolidation_snapshot: dict[str, Any] | None = None,
    agenda_lifecycle_residue: dict[str, Any] | None = None,
    autonomy_intent: dict[str, Any] | None = None,
    action_packets: list[dict[str, Any]] | None = None,
    pending_approval: dict[str, Any] | None = None,
    action_trace: list[dict[str, Any]] | None = None,
    autonomy_block_reason: str | None = None,
    digital_body_state: dict[str, Any] | None = None,
    digital_body_consequence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    relationship = dict(relationship or {})
    semantic = dict(semantic_narrative_profile or {})
    world = dict(world_model_state or {})
    emotion = dict(emotion_state or {})
    bond = dict(bond_state or {})
    counterpart = dict(counterpart_assessment or {})
    behavior = dict(behavior_action or {})
    behavior_plan = dict(behavior_plan or {})
    carryover = dict(interaction_carryover or {})
    current_event = dict(current_event or {})
    recon = dict(reconsolidation_snapshot or {})
    agenda_lifecycle = dict(agenda_lifecycle_residue or {})
    autonomy_intent = dict(autonomy_intent or {})
    pending_approval = dict(pending_approval or {})
    action_trace = list(action_trace or [])
    digital_body = _digital_body_summary(digital_body_state)
    digital_body_consequence = _digital_body_consequence_summary(digital_body_consequence)
    frozen_counterpart = _frozen_counterpart_snapshot(recon)
    frozen_semantic_anchor_bundle = _frozen_semantic_anchor_bundle(recon)
    recon_consequence = (
        dict(recon.get("behavior_consequence"))
        if isinstance(recon.get("behavior_consequence"), dict)
        else {}
    )
    queue_preview = build_behavior_queue_cli_summary(behavior_queue, limit=3)
    window_profile = _window_profile_summary(behavior.get("window_profile"))
    identity_preview = _long_term_identity_preview(semantic.get("long_term_self_narratives"), limit=3)
    carryover_summary = _interaction_carryover_summary(carryover)
    behavior_consequence_summary = _behavior_consequence_summary(recon_consequence)
    behavior_action_embodied = _embodied_context_summary(behavior.get("embodied_context"))
    behavior_plan_embodied = _embodied_context_summary(behavior_plan.get("embodied_context"))

    return {
        "relationship": {
            "stage": str(relationship.get("stage") or "").strip(),
            "affinity_score": _metric(relationship.get("affinity_score"), 0.0),
            "trust_score": _metric(relationship.get("trust_score"), 0.0),
            "notes": str(relationship.get("notes") or "").strip(),
        },
        "continuity_vector": {
            "presence": {
                "semantic": _metric(semantic.get("presence_carry"), 0.0),
                "world": _metric(world.get("presence_residue"), 0.0),
            },
            "ambient": {
                "semantic": _metric(semantic.get("ambient_attunement"), 0.0),
                "world": _metric(world.get("ambient_resonance"), 0.0),
            },
            "rhythm": {
                "semantic": _metric(semantic.get("rhythm_continuity"), 0.0),
                "world": _metric(world.get("self_activity_momentum"), 0.0),
            },
        },
        "semantic_continuity": {
            "history_weight": _metric(semantic.get("history_weight"), 0.0),
            "dominant_category": str(semantic.get("dominant_category") or "").strip(),
            "active_categories": _clean_list(semantic.get("active_categories"), limit=6),
            "reactivated_categories": _clean_list(semantic.get("reactivated_categories"), limit=6),
            "summary_lines": _clean_list(semantic.get("summary_lines"), limit=3),
            "anchor_lines": _clean_list(semantic.get("anchor_lines"), limit=3),
            "top_narratives": _top_narrative_preview(semantic.get("top_narratives"), limit=3),
            "frozen_anchor_bundle": frozen_semantic_anchor_bundle,
        },
        "identity_continuity": {
            "identity_lines": _clean_list(semantic.get("identity_lines"), limit=3),
            "identity_prompt_lines": _clean_list(semantic.get("identity_prompt_lines"), limit=3),
            "dominant_identity_category": (
                str(identity_preview[0].get("category") or "").strip()
                if identity_preview
                else ""
            ),
            "long_term_self_narratives": identity_preview,
        },
        "world_dynamics": {
            "bond_depth": _metric(world.get("bond_depth"), 0.0),
            "tension_load": _metric(world.get("tension_load"), 0.0),
            "selfhood_load": _metric(world.get("selfhood_load"), 0.0),
            "agency_load": _metric(world.get("agency_load"), 0.0),
            "memory_gravity": _metric(world.get("memory_gravity"), 0.0),
            "companionship_pull": _metric(world.get("companionship_pull"), 0.0),
            "task_pull": _metric(world.get("task_pull"), 0.0),
        },
        "current_turn": {
            "event_kind": str(current_event.get("kind") or "").strip(),
            "emotion_label": str(emotion.get("label") or "neutral").strip(),
            "trust": _metric(bond.get("trust"), 0.0),
            "closeness": _metric(bond.get("closeness"), 0.0),
            "hurt": _metric(bond.get("hurt"), 0.0),
            "counterpart_summary": str((frozen_counterpart or counterpart).get("summary") or "").strip(),
            "counterpart_stance": str((frozen_counterpart or counterpart).get("stance") or "").strip(),
            "counterpart_scene": str((frozen_counterpart or counterpart).get("scene") or "").strip(),
            "counterpart_respect_level": _metric((frozen_counterpart or counterpart).get("respect_level"), 0.5),
            "counterpart_reciprocity": _metric((frozen_counterpart or counterpart).get("reciprocity"), 0.5),
            "counterpart_boundary_pressure": _metric((frozen_counterpart or counterpart).get("boundary_pressure"), 0.1),
            "counterpart_reliability_read": _metric((frozen_counterpart or counterpart).get("reliability_read"), 0.5),
            "counterpart_profile": _counterpart_assessment_profile(frozen_counterpart or counterpart),
            "behavior_mode": str(behavior.get("interaction_mode") or "").strip(),
            "action_target": str(behavior.get("action_target") or "").strip(),
            "channel": str(behavior.get("channel") or "").strip(),
            "approach_style": str(behavior.get("approach_style") or "").strip(),
            "engagement_level": _metric(behavior.get("engagement_level"), 0.0),
            "initiative_level": _metric(behavior.get("initiative_level"), 0.0),
            "followup_intent": str(behavior.get("followup_intent") or "").strip(),
            "task_focus": str(behavior.get("task_focus") or "").strip(),
            "affect_surface": str(behavior.get("affect_surface") or "").strip(),
            "silence_ok": bool(behavior.get("silence_ok", False)),
            "proactive_checkin_readiness": _metric(behavior.get("proactive_checkin_readiness"), 0.0),
            "deferred_action_family": str(behavior.get("deferred_action_family") or "").strip(),
            "attention_target": str(behavior.get("attention_target") or "").strip(),
            "nonverbal_signal": str(behavior.get("nonverbal_signal") or "").strip(),
            "initiative_shape": str(behavior.get("initiative_shape") or "").strip(),
            "disclosure_posture": str(behavior.get("disclosure_posture") or "").strip(),
            "primary_motive": str(behavior.get("primary_motive") or "").strip(),
            "motive_tension": str(behavior.get("motive_tension") or "").strip(),
            "goal_frame": str(behavior.get("goal_frame") or "").strip(),
            "behavior_note": str(behavior.get("note") or "").strip(),
            "behavior_action_embodied_context": behavior_action_embodied,
            "timing_window_min": _int_metric(behavior.get("timing_window_min"), 0),
            "behavior_weather": str(behavior.get("relationship_weather") or "").strip(),
            "carryover_mode": str(carryover.get("carryover_mode") or "").strip(),
            "carryover_strength": _metric(carryover.get("strength"), 0.0),
            "carryover_weather": str(carryover.get("relationship_weather") or "").strip(),
            "recon_event_kind": str(recon.get("event_kind") or "").strip(),
            "recon_interaction_frame": str(recon.get("interaction_frame") or "").strip(),
            "behavior_consequence_kind": str(recon_consequence.get("kind") or "").strip(),
            "behavior_consequence_summary": str(recon_consequence.get("summary") or "").strip(),
            "behavior_consequence_embodied_context": behavior_consequence_summary.get("embodied_context")
            if isinstance(behavior_consequence_summary.get("embodied_context"), dict)
            else {},
            "semantic_anchor_bundle": frozen_semantic_anchor_bundle,
            "autonomy_mode": str(autonomy_intent.get("mode") or "").strip(),
            "autonomy_origin": str(autonomy_intent.get("origin") or "").strip(),
            "autonomy_reason": str(autonomy_intent.get("reason") or "").strip(),
            "autonomy_confidence": _metric(autonomy_intent.get("confidence"), 0.0),
            "autonomy_requires_approval": bool(autonomy_intent.get("requires_approval", False)),
            "action_packet_count": len(action_packets or []),
            "autonomy_block_reason": str(autonomy_block_reason or "").strip(),
            "digital_body_surface": str(digital_body.get("active_surface") or "").strip(),
            "digital_body_access_mode": str(
                (
                    digital_body.get("access")
                    if isinstance(digital_body.get("access"), dict)
                    else {}
                ).get("mode")
                or ""
            ).strip(),
            "digital_body_pending_approval_count": _int_metric(
                (
                    digital_body.get("access")
                    if isinstance(digital_body.get("access"), dict)
                    else {}
                ).get("pending_approval_count"),
                0,
            ),
            "digital_body_retry_after_s": _int_metric(
                (
                    digital_body.get("access")
                    if isinstance(digital_body.get("access"), dict)
                    else {}
                ).get("retry_after_s"),
                0,
            ),
            "digital_body_cooldown_scope": str(
                (
                    digital_body.get("access")
                    if isinstance(digital_body.get("access"), dict)
                    else {}
                ).get("cooldown_scope")
                or ""
            ).strip(),
            "digital_body_session_continuity": str(
                (
                    digital_body.get("access")
                    if isinstance(digital_body.get("access"), dict)
                    else {}
                ).get("session_continuity")
                or ""
            ).strip(),
            "digital_body_session_expires_in_s": _int_metric(
                (
                    digital_body.get("access")
                    if isinstance(digital_body.get("access"), dict)
                    else {}
                ).get("session_expires_in_s"),
                0,
            ),
            "digital_body_session_recovery_mode": str(
                (
                    digital_body.get("access")
                    if isinstance(digital_body.get("access"), dict)
                    else {}
                ).get("session_recovery_mode")
                or ""
            ).strip(),
            "digital_body_artifact_continuity": str(
                (
                    digital_body.get("resources")
                    if isinstance(digital_body.get("resources"), dict)
                    else {}
                ).get("artifact_continuity")
                or ""
            ).strip(),
            "digital_body_active_artifact_kind": str(
                (
                    digital_body.get("resources")
                    if isinstance(digital_body.get("resources"), dict)
                    else {}
                ).get("active_artifact_kind")
                or ""
            ).strip(),
            "digital_body_active_artifact_label": str(
                (
                    digital_body.get("resources")
                    if isinstance(digital_body.get("resources"), dict)
                    else {}
                ).get("active_artifact_label")
                or (
                    (
                        digital_body.get("resources")
                        if isinstance(digital_body.get("resources"), dict)
                        else {}
                    ).get("active_artifact_ref")
                    or ""
                )
            ).strip(),
            "digital_body_artifact_reacquisition_mode": str(
                (
                    digital_body.get("resources")
                    if isinstance(digital_body.get("resources"), dict)
                    else {}
                ).get("artifact_reacquisition_mode")
                or ""
            ).strip(),
            "digital_body_consequence_kind": str(digital_body_consequence.get("kind") or "").strip(),
            "digital_body_consequence_summary": str(digital_body_consequence.get("summary") or "").strip(),
            "digital_body_procedural_growth": bool(digital_body_consequence.get("procedural_growth", False)),
            "digital_body_requested_help": bool(digital_body_consequence.get("requested_help", False)),
            "digital_body_environmental_friction": bool(digital_body_consequence.get("environmental_friction", False)),
        },
        "event_residue": _event_residue_summary(current_event, digital_body_consequence=digital_body_consequence),
        "interaction_carryover": carryover_summary,
        "agenda_lifecycle": _agenda_lifecycle_summary(agenda_lifecycle),
        "behavior_consequence": behavior_consequence_summary,
        "opening_window": window_profile,
        "behavior_plan": {
            "kind": str(behavior_plan.get("kind") or "").strip(),
            "target": str(behavior_plan.get("target") or "").strip(),
            "trigger_family": str(behavior_plan.get("trigger_family") or "").strip(),
            "scheduled_after_min": _int_metric(behavior_plan.get("scheduled_after_min"), 0),
            "allow_interrupt": bool(behavior_plan.get("allow_interrupt", True)),
            "primary_motive": str(behavior_plan.get("primary_motive") or "").strip(),
            "motive_tension": str(behavior_plan.get("motive_tension") or "").strip(),
            "goal_frame": str(behavior_plan.get("goal_frame") or "").strip(),
            "carryover_mode": str(behavior_plan.get("carryover_mode") or "").strip(),
            "carryover_strength": _metric(behavior_plan.get("carryover_strength"), 0.0),
            "relationship_weather": str(behavior_plan.get("relationship_weather") or "").strip(),
            "attention_target": str(behavior_plan.get("attention_target") or "").strip(),
            "nonverbal_signal": str(behavior_plan.get("nonverbal_signal") or "").strip(),
            "note": str(behavior_plan.get("note") or "").strip(),
            "presence_residue": _metric(behavior_plan.get("presence_residue"), 0.0),
            "ambient_resonance": _metric(behavior_plan.get("ambient_resonance"), 0.0),
            "self_activity_momentum": _metric(behavior_plan.get("self_activity_momentum"), 0.0),
            "embodied_context": behavior_plan_embodied,
        },
        "behavior_queue_preview": queue_preview,
        "autonomy": {
            "intent": {
                "mode": str(autonomy_intent.get("mode") or "").strip(),
                "origin": str(autonomy_intent.get("origin") or "").strip(),
                "reason": str(autonomy_intent.get("reason") or "").strip(),
                "confidence": _metric(autonomy_intent.get("confidence"), 0.0),
                "own_rhythm_weight": _metric(autonomy_intent.get("own_rhythm_weight"), 0.0),
                "continuity_weight": _metric(autonomy_intent.get("continuity_weight"), 0.0),
                "requires_approval": bool(autonomy_intent.get("requires_approval", False)),
                "primary_proposal_id": str(autonomy_intent.get("primary_proposal_id") or "").strip(),
            },
            "action_packets": [dict(item) for item in (action_packets or [])[:5] if isinstance(item, dict)],
            "pending_approval": pending_approval,
            "execution_trace": [dict(item) for item in action_trace[:8] if isinstance(item, dict)],
            "block_reason": str(autonomy_block_reason or "").strip(),
        },
        "digital_body": digital_body,
        "digital_body_consequence": digital_body_consequence,
        "worldline_focus_preview": _focus_preview(worldline_focus, limit=3),
        "worldline_focus_items": _focus_preview_items(worldline_focus, limit=3),
    }


def build_evolution_summary_line(summary: dict[str, Any] | None) -> str:
    if not isinstance(summary, dict):
        return "-"
    continuity = summary.get("continuity_vector") if isinstance(summary.get("continuity_vector"), dict) else {}
    current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
    carryover = summary.get("interaction_carryover") if isinstance(summary.get("interaction_carryover"), dict) else {}
    world = summary.get("world_dynamics") if isinstance(summary.get("world_dynamics"), dict) else {}
    identity = summary.get("identity_continuity") if isinstance(summary.get("identity_continuity"), dict) else {}
    lifecycle = summary.get("agenda_lifecycle") if isinstance(summary.get("agenda_lifecycle"), dict) else {}
    behavior_plan = summary.get("behavior_plan") if isinstance(summary.get("behavior_plan"), dict) else {}
    behavior_consequence = summary.get("behavior_consequence") if isinstance(summary.get("behavior_consequence"), dict) else {}

    def _axis_text(name: str) -> str:
        axis = continuity.get(name) if isinstance(continuity.get(name), dict) else {}
        return (
            f"{name}="
            f"{_metric(axis.get('semantic'), 0.0):.3f}/{_metric(axis.get('world'), 0.0):.3f}"
        )

    parts = [
        _axis_text("presence"),
        _axis_text("ambient"),
        _axis_text("rhythm"),
    ]
    mode = str(current_turn.get("behavior_mode") or "").strip()
    if mode:
        parts.append(f"mode={mode}")
    motive = str(current_turn.get("primary_motive") or "").strip()
    if motive:
        parts.append(f"motive={motive}")
    action_embodied = (
        current_turn.get("behavior_action_embodied_context")
        if isinstance(current_turn.get("behavior_action_embodied_context"), dict)
        else {}
    )
    action_embodied_kind = str(action_embodied.get("kind") or "").strip()
    if action_embodied_kind:
        parts.append(f"actfx={action_embodied_kind}")
    consequence_kind = str(current_turn.get("behavior_consequence_kind") or "").strip()
    if consequence_kind:
        parts.append(f"cons={consequence_kind}")
    consequence_embodied = (
        behavior_consequence.get("embodied_context")
        if isinstance(behavior_consequence.get("embodied_context"), dict)
        else current_turn.get("behavior_consequence_embodied_context")
        if isinstance(current_turn.get("behavior_consequence_embodied_context"), dict)
        else {}
    )
    consequence_embodied_kind = str(consequence_embodied.get("kind") or "").strip()
    if consequence_embodied_kind:
        parts.append(f"consfx={consequence_embodied_kind}")
    autonomy_mode = str(current_turn.get("autonomy_mode") or "").strip()
    if autonomy_mode:
        parts.append(f"autonomy={autonomy_mode}")
    action_packet_count = _int_metric(current_turn.get("action_packet_count"), 0)
    if action_packet_count > 0:
        parts.append(f"packets={action_packet_count}")
    body_surface = str(current_turn.get("digital_body_surface") or "").strip()
    body_access = str(current_turn.get("digital_body_access_mode") or "").strip()
    if body_surface or body_access:
        parts.append(f"body={body_surface or '-'}:{body_access or '-'}")
    body_fx = str(current_turn.get("digital_body_consequence_kind") or "").strip()
    if body_fx:
        parts.append(f"bodyfx={body_fx}")
    body_pending = _int_metric(current_turn.get("digital_body_pending_approval_count"), 0)
    if body_pending > 0:
        parts.append(f"approvals={body_pending}")
    body_retry_after = _int_metric(current_turn.get("digital_body_retry_after_s"), 0)
    body_cooldown_scope = str(current_turn.get("digital_body_cooldown_scope") or "").strip()
    if body_retry_after > 0:
        retry_label = f"retry={body_retry_after}s"
        if body_cooldown_scope:
            retry_label += f"@{body_cooldown_scope}"
        parts.append(retry_label)
    body_session_continuity = str(current_turn.get("digital_body_session_continuity") or "").strip()
    body_session_expires = _int_metric(current_turn.get("digital_body_session_expires_in_s"), 0)
    body_session_recovery = str(current_turn.get("digital_body_session_recovery_mode") or "").strip()
    if body_session_continuity and (
        body_session_continuity != "stable" or body_session_expires > 0 or body_session_recovery
    ):
        session_label = f"session={body_session_continuity}"
        if body_session_expires > 0:
            session_label += f":{body_session_expires}s"
        if body_session_recovery:
            session_label += f":{body_session_recovery}"
        parts.append(session_label)
    body_artifact_continuity = str(current_turn.get("digital_body_artifact_continuity") or "").strip()
    body_artifact_kind = str(current_turn.get("digital_body_active_artifact_kind") or "").strip()
    body_artifact_label = str(current_turn.get("digital_body_active_artifact_label") or "").strip()
    body_artifact_reacquisition = str(current_turn.get("digital_body_artifact_reacquisition_mode") or "").strip()
    if body_artifact_continuity:
        artifact_label = body_artifact_kind or "artifact"
        if body_artifact_label:
            artifact_label += ":" + body_artifact_label[:40]
        artifact_label += ":" + body_artifact_continuity
        if body_artifact_reacquisition:
            artifact_label += ":" + body_artifact_reacquisition
        parts.append(f"artifact={artifact_label}")
    carry_mode = str(current_turn.get("carryover_mode") or "").strip()
    if carry_mode:
        parts.append(f"carry={carry_mode}:{_metric(current_turn.get('carryover_strength'), 0.0):.3f}")
    carry_weather = str(current_turn.get("carryover_weather") or "").strip()
    if carry_weather:
        parts.append(f"weather={carry_weather}")
    carry_embodied = carryover.get("embodied_context") if isinstance(carryover.get("embodied_context"), dict) else {}
    carry_embodied_kind = str(carry_embodied.get("kind") or "").strip()
    if carry_embodied_kind:
        parts.append(f"carryfx={carry_embodied_kind}")
    plan_embodied = behavior_plan.get("embodied_context") if isinstance(behavior_plan.get("embodied_context"), dict) else {}
    plan_embodied_kind = str(plan_embodied.get("kind") or "").strip()
    if plan_embodied_kind:
        parts.append(f"planfx={plan_embodied_kind}")
    stance = str(current_turn.get("counterpart_stance") or "").strip()
    if stance:
        parts.append(f"stance={stance}")
    counterpart_profile = current_turn.get("counterpart_profile") if isinstance(current_turn.get("counterpart_profile"), dict) else {}
    if counterpart_profile:
        dominant = str(counterpart_profile.get("dominant_scene_signal") or "").strip()
        scene_strengths = counterpart_profile.get("scene_strengths") if isinstance(counterpart_profile.get("scene_strengths"), dict) else {}
        if dominant:
            parts.append(f"read={dominant}:{_metric(scene_strengths.get(dominant), 0.0):.3f}")
    opening_window = summary.get("opening_window") if isinstance(summary.get("opening_window"), dict) else {}
    if opening_window:
        profile_type = str(opening_window.get("profile_type") or "").strip()
        if profile_type == "self_opening":
            score = _metric(opening_window.get("readiness"), 0.0)
            required = _metric(opening_window.get("required_readiness"), 0.0)
        else:
            score = _metric(opening_window.get("maturity"), 0.0)
            required = _metric(opening_window.get("required_maturity"), 0.0)
        parts.append(f"window={profile_type or 'window'}:{score:.3f}/{required:.3f}")
        decision = str(opening_window.get("decision") or "").strip()
        if decision:
            parts.append(f"decision={decision}")
        recheck_min = _int_metric(opening_window.get("recheck_min"), 0)
        if recheck_min > 0 and decision in {"wait_and_recheck", "hold_own_rhythm"}:
            parts.append(f"recheck={recheck_min}m")
    lifecycle_kind = str(lifecycle.get("kind") or "").strip()
    if lifecycle_kind:
        parts.append(
            "lifecycle="
            + lifecycle_kind
            + ":"
            + (str(lifecycle.get("carryover_mode") or "").strip() or "-")
            + f":{_metric(lifecycle.get('carryover_strength'), 0.0):.3f}"
        )
        hold_count = _int_metric(lifecycle.get("hold_count"), 0)
        if hold_count > 0:
            parts.append(f"holds={hold_count}")
        cooldown = _metric(lifecycle.get("recontact_cooldown"), 0.0)
        if cooldown > 0.0:
            parts.append(f"cool={cooldown:.3f}")
        lifecycle_embodied = lifecycle.get("embodied_context") if isinstance(lifecycle.get("embodied_context"), dict) else {}
        lifecycle_embodied_kind = str(lifecycle_embodied.get("kind") or "").strip()
        if lifecycle_embodied_kind:
            parts.append(f"lifecyclefx={lifecycle_embodied_kind}")
    bond_depth = _metric(world.get("bond_depth"), 0.0)
    tension = _metric(world.get("tension_load"), 0.0)
    long_term = identity.get("long_term_self_narratives") if isinstance(identity.get("long_term_self_narratives"), list) else []
    if long_term and isinstance(long_term[0], dict):
        identity_cat = str(long_term[0].get("category") or "").strip()
        identity_score = _metric(long_term[0].get("score"), 0.0)
        if identity_cat:
            parts.append(f"identity={identity_cat}:{identity_score:.3f}")
    parts.append(f"bond={bond_depth:.3f}")
    parts.append(f"tension={tension:.3f}")
    return " | ".join(parts)
