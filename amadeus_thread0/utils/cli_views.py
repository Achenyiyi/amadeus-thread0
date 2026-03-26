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


def _event_residue_summary(current_event: Any) -> dict[str, Any]:
    if not isinstance(current_event, dict) or not current_event:
        return {}
    perception = current_event.get("perception") if isinstance(current_event.get("perception"), dict) else {}
    return {
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


def _agenda_lifecycle_summary(residue: Any) -> dict[str, Any]:
    if not isinstance(residue, dict) or not residue:
        return {}
    return {
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
        out.append(
            {
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
        )
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
            "timing_window_min": _int_metric(behavior.get("timing_window_min"), 0),
            "behavior_weather": str(behavior.get("relationship_weather") or "").strip(),
            "carryover_mode": str(carryover.get("carryover_mode") or "").strip(),
            "carryover_strength": _metric(carryover.get("strength"), 0.0),
            "carryover_weather": str(carryover.get("relationship_weather") or "").strip(),
            "recon_event_kind": str(recon.get("event_kind") or "").strip(),
            "recon_interaction_frame": str(recon.get("interaction_frame") or "").strip(),
            "behavior_consequence_kind": str(recon_consequence.get("kind") or "").strip(),
            "behavior_consequence_summary": str(recon_consequence.get("summary") or "").strip(),
            "semantic_anchor_bundle": frozen_semantic_anchor_bundle,
        },
        "event_residue": _event_residue_summary(current_event),
        "agenda_lifecycle": _agenda_lifecycle_summary(agenda_lifecycle),
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
        },
        "behavior_queue_preview": queue_preview,
        "worldline_focus_preview": _focus_preview(worldline_focus, limit=3),
        "worldline_focus_items": _focus_preview_items(worldline_focus, limit=3),
    }


def build_evolution_summary_line(summary: dict[str, Any] | None) -> str:
    if not isinstance(summary, dict):
        return "-"
    continuity = summary.get("continuity_vector") if isinstance(summary.get("continuity_vector"), dict) else {}
    current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
    world = summary.get("world_dynamics") if isinstance(summary.get("world_dynamics"), dict) else {}
    identity = summary.get("identity_continuity") if isinstance(summary.get("identity_continuity"), dict) else {}
    lifecycle = summary.get("agenda_lifecycle") if isinstance(summary.get("agenda_lifecycle"), dict) else {}

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
    consequence_kind = str(current_turn.get("behavior_consequence_kind") or "").strip()
    if consequence_kind:
        parts.append(f"cons={consequence_kind}")
    carry_mode = str(current_turn.get("carryover_mode") or "").strip()
    if carry_mode:
        parts.append(f"carry={carry_mode}:{_metric(current_turn.get('carryover_strength'), 0.0):.3f}")
    carry_weather = str(current_turn.get("carryover_weather") or "").strip()
    if carry_weather:
        parts.append(f"weather={carry_weather}")
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
