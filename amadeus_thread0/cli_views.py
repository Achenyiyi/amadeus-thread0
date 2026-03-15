from __future__ import annotations

from typing import Any


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


def _focus_preview(worldline_focus: Any, *, limit: int = 3) -> list[str]:
    if not isinstance(worldline_focus, list):
        return []
    out: list[str] = []
    for item in worldline_focus:
        if not isinstance(item, dict):
            continue
        text = str(item.get("summary") or item.get("text") or item.get("label") or "").strip()
        if not text:
            continue
        out.append(text[:120])
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
    return {
        "event_kind": str(current_event.get("kind") or "").strip(),
        "trigger_family": str(current_event.get("trigger_family") or "").strip(),
        "carryover_mode": str(current_event.get("carryover_mode") or "").strip(),
        "carryover_strength": _metric(current_event.get("carryover_strength"), 0.0),
        "relationship_weather": str(current_event.get("relationship_weather") or "").strip(),
        "presence_residue": _metric(current_event.get("presence_residue"), 0.0),
        "ambient_resonance": _metric(current_event.get("ambient_resonance"), 0.0),
        "self_activity_momentum": _metric(current_event.get("self_activity_momentum"), 0.0),
        "scheduled_after_min": _int_metric(current_event.get("scheduled_after_min"), 0),
        "idle_minutes": _int_metric(current_event.get("idle_minutes"), 0),
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
                "carryover_mode": str(item.get("carryover_mode") or "").strip(),
                "carryover_strength": _metric(item.get("carryover_strength"), 0.0),
                "relationship_weather": str(item.get("relationship_weather") or "").strip(),
                "presence_residue": _metric(item.get("presence_residue"), 0.0),
                "ambient_resonance": _metric(item.get("ambient_resonance"), 0.0),
                "self_activity_momentum": _metric(item.get("self_activity_momentum"), 0.0),
                "attention_target": str(item.get("attention_target") or "").strip(),
                "nonverbal_signal": str(item.get("nonverbal_signal") or "").strip(),
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
        lines.append(residue)
        if row.get("note"):
            lines.append(f"  note={row['note']}")
    return "\n".join(lines)


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
    queue_preview = build_behavior_queue_cli_summary(behavior_queue, limit=3)
    window_profile = _window_profile_summary(behavior.get("window_profile"))

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
            "counterpart_stance": str(counterpart.get("stance") or "").strip(),
            "counterpart_scene": str(counterpart.get("scene") or "").strip(),
            "behavior_mode": str(behavior.get("interaction_mode") or "").strip(),
            "action_target": str(behavior.get("action_target") or "").strip(),
            "behavior_weather": str(behavior.get("relationship_weather") or "").strip(),
            "carryover_mode": str(carryover.get("carryover_mode") or "").strip(),
            "carryover_strength": _metric(carryover.get("strength"), 0.0),
            "carryover_weather": str(carryover.get("relationship_weather") or "").strip(),
            "recon_event_kind": str(recon.get("event_kind") or "").strip(),
            "recon_interaction_frame": str(recon.get("interaction_frame") or "").strip(),
        },
        "event_residue": _event_residue_summary(current_event),
        "opening_window": window_profile,
        "behavior_plan": {
            "kind": str(behavior_plan.get("kind") or "").strip(),
            "target": str(behavior_plan.get("target") or "").strip(),
            "trigger_family": str(behavior_plan.get("trigger_family") or "").strip(),
            "scheduled_after_min": _int_metric(behavior_plan.get("scheduled_after_min"), 0),
            "carryover_mode": str(behavior_plan.get("carryover_mode") or "").strip(),
            "carryover_strength": _metric(behavior_plan.get("carryover_strength"), 0.0),
            "relationship_weather": str(behavior_plan.get("relationship_weather") or "").strip(),
        },
        "behavior_queue_preview": queue_preview,
        "worldline_focus_preview": _focus_preview(worldline_focus, limit=3),
    }


def build_evolution_summary_line(summary: dict[str, Any] | None) -> str:
    if not isinstance(summary, dict):
        return "-"
    continuity = summary.get("continuity_vector") if isinstance(summary.get("continuity_vector"), dict) else {}
    current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
    world = summary.get("world_dynamics") if isinstance(summary.get("world_dynamics"), dict) else {}

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
    carry_mode = str(current_turn.get("carryover_mode") or "").strip()
    if carry_mode:
        parts.append(f"carry={carry_mode}:{_metric(current_turn.get('carryover_strength'), 0.0):.3f}")
    carry_weather = str(current_turn.get("carryover_weather") or "").strip()
    if carry_weather:
        parts.append(f"weather={carry_weather}")
    stance = str(current_turn.get("counterpart_stance") or "").strip()
    if stance:
        parts.append(f"stance={stance}")
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
    bond_depth = _metric(world.get("bond_depth"), 0.0)
    tension = _metric(world.get("tension_load"), 0.0)
    parts.append(f"bond={bond_depth:.3f}")
    parts.append(f"tension={tension:.3f}")
    return " | ".join(parts)
