from __future__ import annotations

import re
from typing import Any

from ..config import ABLATE_WORLDLINE_MEMORY, CANON_COUNTERPART_NAME
from ..memory_store import MemoryStore
from .common import _clamp01, _clamp_signed, _now_ts
from .postprocess import _looks_like_light_smalltalk
from .retrieval import (
    _commitment_priority,
    _conflict_repair_salience,
    _record_value,
    _relationship_salience,
    _tension_salience,
)
from .state import AgendaLifecycleResiduePayload, InteractionCarryoverPayload, ThreadState


def _recent_non_user_event_with_gap(
    recent_events: Any,
    *,
    max_user_turn_gap: int = 3,
) -> tuple[dict[str, Any], str, int]:
    if not isinstance(recent_events, list):
        return {}, "", 0
    user_turn_gap = 0
    for item in reversed(recent_events):
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip().lower()
        if not kind:
            continue
        if kind == "user_utterance":
            user_turn_gap += 1
            if user_turn_gap > max(0, int(max_user_turn_gap)):
                break
            continue
        return dict(item), kind, user_turn_gap
    return {}, "", 0

def _history_source_behavior_hint(source_event: dict[str, Any]) -> dict[str, str]:
    event = dict(source_event or {})
    kind = str(event.get("kind") or "").strip().lower()
    tags = {
        str(tag).strip().lower()
        for tag in (event.get("tags") if isinstance(event.get("tags"), list) else [])
        if str(tag).strip()
    }
    carryover_mode = str(event.get("carryover_mode") or "").strip().lower()
    attention_target = str(event.get("attention_target_hint") or "").strip()
    nonverbal_signal = str(event.get("nonverbal_signal_hint") or "").strip()

    if kind == "self_activity_state":
        if {"deep_focus", "own_task"} & tags or carryover_mode == "own_rhythm":
            return {
                "behavior_mode": "self_activity_hold",
                "action_target": "hold_own_rhythm",
                "attention_target": attention_target or "self_then_counterpart",
                "nonverbal_signal": nonverbal_signal or "thought_glance",
            }
        return {
            "behavior_mode": "self_activity_reopen",
            "action_target": "offer_small_opening",
            "attention_target": attention_target or "self_then_counterpart",
            "nonverbal_signal": nonverbal_signal or "thought_glance",
        }
    if kind in {"scheduled_checkin_due", "scheduled_life_due"}:
        if {"shared_activity_window", "offer_window"} & tags or "shared_activity" in str(event.get("trigger_family") or "").strip().lower():
            return {
                "behavior_mode": "shared_activity_offer",
                "action_target": "offer_shared_activity",
                "attention_target": attention_target or "shared_window",
                "nonverbal_signal": nonverbal_signal or "nudge_presence",
            }
        if {"deadline_window", "work_nudge", "task_window"} & tags or str(event.get("trigger_family") or "").strip().lower() == "deadline_window":
            return {
                "behavior_mode": "scheduled_life_nudge",
                "action_target": "light_work_nudge",
                "attention_target": attention_target or "shared_task",
                "nonverbal_signal": nonverbal_signal or "focus_glance",
            }
        if {"life_window"} & tags or str(event.get("trigger_family") or "").strip().lower() == "life_window":
            return {
                "behavior_mode": "scheduled_life_nudge",
                "action_target": "light_life_nudge",
                "attention_target": attention_target or "counterpart_state",
                "nonverbal_signal": nonverbal_signal or "quiet_glance",
            }
        return {
            "behavior_mode": "proactive_checkin" if kind == "scheduled_checkin_due" else "scheduled_life_nudge",
            "action_target": "wait_and_recheck",
            "attention_target": attention_target or "counterpart_state",
            "nonverbal_signal": nonverbal_signal or "quiet_glance",
        }
    if kind == "time_idle":
        if {"respect_space", "user_busy", "cognitive_load"} & tags:
            return {
                "behavior_mode": "idle_presence",
                "action_target": "wait_and_recheck",
                "attention_target": attention_target or "counterpart_state",
                "nonverbal_signal": nonverbal_signal or "quiet_glance",
            }
        return {
            "behavior_mode": "idle_presence",
            "action_target": "hold_own_rhythm" if {"self_activity", "own_task", "quiet_presence"} & tags else "reach_out_now",
            "attention_target": attention_target or "self_then_counterpart",
            "nonverbal_signal": nonverbal_signal or "thought_glance",
        }
    if kind == "gesture_signal":
        return {
            "behavior_mode": "brief_presence",
            "action_target": "confirm_presence",
            "attention_target": attention_target or "counterpart_state",
            "nonverbal_signal": nonverbal_signal or "brief_notice",
        }
    if kind == "ambient_shift":
        return {
            "behavior_mode": "companion_reply",
            "action_target": "ambient_checkin",
            "attention_target": attention_target or "ambient_cue",
            "nonverbal_signal": nonverbal_signal or "still_presence",
        }
    if kind == "scene_observation":
        return {
            "behavior_mode": "companion_reply",
            "action_target": "respond_now",
            "attention_target": attention_target or "object_then_user",
            "nonverbal_signal": nonverbal_signal or "small_notice",
        }
    return {
        "behavior_mode": "",
        "action_target": "",
        "attention_target": attention_target,
        "nonverbal_signal": nonverbal_signal,
    }

def _recent_interaction_carryover(
    *,
    prior_current_event: dict[str, Any] | None,
    prior_behavior_action: dict[str, Any] | None,
    prior_agenda_lifecycle_residue: dict[str, Any] | None = None,
    prior_counterpart_assessment: dict[str, Any] | None = None,
    recent_events: Any,
    current_event: dict[str, Any] | None,
    response_style_hint: str,
) -> InteractionCarryoverPayload:
    current = dict(current_event or {})
    current_kind = str(current.get("kind") or "user_utterance").strip().lower()
    if current_kind != "user_utterance":
        return {}

    source_event = dict(prior_current_event or {})
    source_kind = str(source_event.get("kind") or "").strip().lower()
    prior_action = dict(prior_behavior_action or {})
    relational_fallback = _prior_user_exchange_carryover(
        source_event,
        prior_action,
        prior_counterpart_assessment=prior_counterpart_assessment,
        response_style_hint=response_style_hint,
    )
    agenda_fallback = _agenda_lifecycle_carryover(
        prior_agenda_lifecycle_residue,
        current_event=current_event,
    )
    source_from_history = False
    user_turn_gap = 0
    if source_kind == "user_utterance" or not source_kind:
        source_event, source_kind, user_turn_gap = _recent_non_user_event_with_gap(recent_events, max_user_turn_gap=3)
        source_from_history = bool(source_event and source_kind)
    if not source_event or not source_kind or source_kind == "user_utterance":
        return _prefer_relational_carryover(agenda_fallback, relational_fallback)

    prior_action = {} if source_from_history else prior_action
    source_behavior_mode = str(prior_action.get("interaction_mode") or "").strip().lower()
    source_action_target = str(prior_action.get("action_target") or "").strip().lower()
    source_primary_motive = str(prior_action.get("primary_motive") or "").strip().lower()
    source_motive_tension = str(prior_action.get("motive_tension") or "").strip().lower()
    source_goal_frame = str(prior_action.get("goal_frame") or "").strip()
    idle_minutes = 0
    try:
        idle_minutes = int(source_event.get("idle_minutes") or 0)
    except Exception:
        idle_minutes = 0
    source_tags = [
        str(item).strip()
        for item in (source_event.get("tags") if isinstance(source_event.get("tags"), list) else [])
        if str(item).strip()
    ]
    hint = str(response_style_hint or "").strip().lower() or "natural"
    if source_from_history:
        implied = _history_source_behavior_hint(source_event)
        source_behavior_mode = str(implied.get("behavior_mode") or source_behavior_mode).strip().lower()
        source_action_target = str(implied.get("action_target") or source_action_target).strip().lower()
    carryover_mode = ""
    strength = 0.0
    attention_target = str(source_event.get("attention_target_hint") or "").strip()
    nonverbal_signal = str(source_event.get("nonverbal_signal_hint") or "").strip()
    relationship_weather = str(source_event.get("relationship_weather") or "").strip().lower()
    note = ""

    if source_kind == "time_idle":
        if source_action_target == "hold_own_rhythm" or source_behavior_mode in {"self_activity_hold", "idle_presence"}:
            carryover_mode = "own_rhythm"
            strength = 0.40 + min(0.18, idle_minutes / 150.0)
            attention_target = "self_then_counterpart"
            nonverbal_signal = "thought_glance"
            note = "前面那段安静还留着一点她自己的节奏。"
        elif source_action_target == "wait_and_recheck":
            carryover_mode = "quiet_recontact"
            strength = 0.30 + min(0.16, idle_minutes / 180.0)
            attention_target = "counterpart_state"
            nonverbal_signal = "quiet_glance"
            note = "刚从安静里抬头时，这轮开口会更轻一点。"
        else:
            carryover_mode = "small_opening"
            strength = 0.28 + min(0.12, idle_minutes / 240.0)
            attention_target = "counterpart_state"
            nonverbal_signal = "brief_notice"
            note = "安静过后，她会先留一个不太张扬的小开口。"
    elif source_kind == "self_activity_state":
        if source_action_target == "hold_own_rhythm":
            carryover_mode = "own_rhythm"
            strength = 0.42
            attention_target = "self_then_counterpart"
            nonverbal_signal = "thought_glance"
            note = "她会先带着自己的节奏接住对方。"
        else:
            carryover_mode = "small_opening"
            strength = 0.36
            attention_target = "self_then_counterpart"
            nonverbal_signal = "thought_glance"
            note = "刚从自己的事情里抬头时，她更像是顺手把话接住。"
    elif source_kind in {"scheduled_checkin_due", "scheduled_life_due"}:
        if source_action_target == "offer_shared_activity":
            carryover_mode = "shared_window"
            strength = 0.32
            attention_target = "shared_window"
            nonverbal_signal = "nudge_presence"
            note = "前面那点还能接着说下去的空当还没完全过去。"
        elif source_action_target == "light_work_nudge" and (
            {"deadline_window", "work_nudge", "task_window", "shared_task"} & {str(item).strip().lower() for item in source_tags}
            or str(source_event.get("trigger_family") or "").strip().lower() == "deadline_window"
        ):
            carryover_mode = "task_window"
            strength = 0.30
            attention_target = "shared_task"
            nonverbal_signal = "focus_glance"
            note = "之前那件事的节点还留在她的注意力里。"
        elif source_action_target in {"light_work_nudge", "light_life_nudge"}:
            carryover_mode = "life_window"
            strength = 0.26
            attention_target = "counterpart_state"
            nonverbal_signal = "quiet_glance"
            note = "前面那点生活上的惦记还留在她心里。"
        elif source_action_target == "wait_and_recheck":
            carryover_mode = "quiet_recontact"
            strength = 0.24
            attention_target = "counterpart_state"
            nonverbal_signal = "quiet_glance"
            note = "刚才没开口的那一下，会让这轮先更轻一点。"
    elif source_kind == "gesture_signal":
        carryover_mode = "brief_presence"
        strength = 0.20
        attention_target = "counterpart_state"
        nonverbal_signal = "brief_notice"
        note = "上一下轻信号留下的在场感还没完全退掉。"
    elif source_kind == "ambient_shift":
        carryover_mode = "ambient_echo"
        strength = 0.22
        attention_target = "ambient_cue"
        nonverbal_signal = "still_presence"
        note = "刚才那点环境变化还在她的感知里。"
    elif source_kind == "scene_observation":
        carryover_mode = "ambient_echo"
        strength = 0.24
        attention_target = "object_then_user"
        nonverbal_signal = "small_notice"
        note = "刚才注意到的小事，还会顺手带进这轮开口里。"

    if not carryover_mode:
        return {}

    if source_from_history and user_turn_gap > 0:
        if carryover_mode in {"shared_window", "task_window"}:
            strength *= max(0.46, 1.0 - 0.14 * user_turn_gap)
        elif carryover_mode in {"own_rhythm", "small_opening"}:
            strength *= max(0.34, 1.0 - 0.18 * user_turn_gap)
        else:
            strength *= max(0.30, 1.0 - 0.22 * user_turn_gap)

    if hint == "structured":
        strength *= 0.35
    elif hint in {"memory_recall", "relationship"}:
        strength *= 0.65
    strength = _clamp01(strength, 0.0)
    if strength < 0.12:
        return relational_fallback

    derived = {
        "source_event_kind": source_kind,
        "source_behavior_mode": source_behavior_mode,
        "source_action_target": source_action_target,
        "source_primary_motive": source_primary_motive,
        "source_motive_tension": source_motive_tension,
        "source_goal_frame": source_goal_frame,
        "source_text": str(source_event.get("effective_text") or source_event.get("text") or "").strip()[:180],
        "source_tags": source_tags[:6],
        "carryover_mode": carryover_mode,
        "strength": round(strength, 3),
        "relationship_weather": relationship_weather,
        "idle_minutes": max(0, idle_minutes),
        "attention_target": attention_target,
        "nonverbal_signal": nonverbal_signal,
        "note": note,
        "source_turn_gap": max(0, int(user_turn_gap)),
        "created_at": _now_ts(),
    }
    combined = _prefer_relational_carryover(derived, relational_fallback)
    return _prefer_relational_carryover(agenda_fallback, combined)


def _agenda_lifecycle_carryover(
    residue: dict[str, Any] | None,
    *,
    current_event: dict[str, Any] | None,
) -> AgendaLifecycleResiduePayload | InteractionCarryoverPayload:
    current = dict(current_event or {})
    if str(current.get("kind") or "").strip().lower() != "user_utterance":
        return {}
    payload = dict(residue or {})
    kind = str(payload.get("kind") or "").strip().lower()
    carryover_mode = str(payload.get("carryover_mode") or "").strip().lower()
    strength = _clamp01(payload.get("carryover_strength"), 0.0)
    if not kind or not carryover_mode or strength < 0.12:
        return {}
    source_tags = [
        str(item).strip().lower()
        for item in (payload.get("source_tags") if isinstance(payload.get("source_tags"), list) else [])
        if str(item).strip()
    ]
    return {
        "source_event_kind": f"agenda_lifecycle:{kind}",
        "source_behavior_mode": "agenda_lifecycle",
        "source_action_target": "hold_own_rhythm" if carryover_mode == "own_rhythm" else "wait_and_recheck",
        "source_primary_motive": "preserve_self_rhythm" if carryover_mode == "own_rhythm" else "gentle_recontact",
        "source_motive_tension": "self_rhythm_vs_contact" if carryover_mode == "own_rhythm" else "space_vs_contact",
        "source_goal_frame": str(payload.get("note") or "").strip(),
        "source_text": str(payload.get("note") or "").strip()[:180],
        "source_tags": source_tags,
        "carryover_mode": carryover_mode,
        "strength": round(strength, 3),
        "relationship_weather": str(payload.get("relationship_weather") or "").strip().lower(),
        "idle_minutes": max(0, int(payload.get("idle_minutes") or 0)),
        "source_turn_gap": 0,
        "attention_target": str(payload.get("attention_target") or "").strip() or "self_then_counterpart",
        "nonverbal_signal": str(payload.get("nonverbal_signal") or "").strip() or "thought_glance",
        "note": str(payload.get("note") or "").strip(),
        "created_at": int(payload.get("created_at") or _now_ts()),
    }


def _apply_agenda_lifecycle_residue_to_runtime_state(
    *,
    agenda_lifecycle_residue: dict[str, Any] | None,
    world_model_state: dict[str, Any] | None,
    counterpart_assessment: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    residue = dict(agenda_lifecycle_residue or {})
    if not residue:
        return dict(world_model_state or {}), dict(counterpart_assessment or {})
    kind = str(residue.get("kind") or "").strip().lower()
    if kind not in {"held", "released_to_self_activity", "dropped", "expired"}:
        return dict(world_model_state or {}), dict(counterpart_assessment or {})

    world = dict(world_model_state or {})
    assessment = dict(counterpart_assessment or {})
    own_rhythm_bias = max(
        _clamp01(residue.get("own_rhythm_bias"), 0.0),
        _clamp01(residue.get("self_activity_momentum"), 0.0),
    )
    presence_residue = _clamp01(residue.get("presence_residue"), 0.0)
    ambient_resonance = _clamp01(residue.get("ambient_resonance"), 0.0)
    cooldown = _clamp01(residue.get("recontact_cooldown"), 0.0)

    world["self_activity_momentum"] = round(max(_clamp01(world.get("self_activity_momentum"), 0.0), own_rhythm_bias), 3)
    world["presence_residue"] = round(
        max(
            _clamp01(world.get("presence_residue"), 0.0),
            presence_residue * (0.92 if kind == "released_to_self_activity" else 0.82 if kind == "held" else 0.72),
        ),
        3,
    )
    world["ambient_resonance"] = round(max(_clamp01(world.get("ambient_resonance"), 0.0), 0.88 * ambient_resonance), 3)
    boundary_load = _clamp01(world.get("boundary_load"), 0.0)
    if kind == "released_to_self_activity":
        boundary_load = max(boundary_load, 0.08 + 0.10 * cooldown)
    else:
        boundary_load = max(boundary_load, 0.12 + 0.18 * cooldown)
    world["boundary_load"] = round(_clamp01(boundary_load), 3)

    if assessment:
        scene_bias = str(residue.get("counterpart_scene_bias") or "").strip().lower()
        stance = str(assessment.get("stance") or "").strip().lower()
        if scene_bias and stance != "guarded":
            assessment["scene"] = scene_bias
        boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1) + float(residue.get("counterpart_boundary_delta") or 0.0)
        assessment["boundary_pressure"] = round(_clamp01(boundary_pressure), 3)
        if scene_bias == "busy_not_disrespectful":
            assessment["reliability_read"] = round(max(_clamp01(assessment.get("reliability_read"), 0.5), 0.52), 3)
            assessment["respect_level"] = round(max(_clamp01(assessment.get("respect_level"), 0.5), 0.52), 3)

    return world, assessment

def _prefer_relational_carryover(
    derived: InteractionCarryoverPayload | dict[str, Any] | None,
    relational_fallback: InteractionCarryoverPayload | dict[str, Any] | None,
) -> InteractionCarryoverPayload:
    fallback = dict(relational_fallback or {})
    base = dict(derived or {})
    if not fallback:
        return base
    if not base:
        return fallback

    fallback_weather = str(fallback.get("relationship_weather") or "").strip().lower()
    fallback_strength = _clamp01(fallback.get("strength"), 0.0)
    base_strength = _clamp01(base.get("strength"), 0.0)
    base_mode = str(base.get("carryover_mode") or "").strip().lower()

    if fallback_weather == "guarded_residue":
        # Fresh guardedness from the last user exchange should usually dominate
        # older background nudges; otherwise the system feels like it "forgets"
        # being upset as soon as another soft residue exists.
        if base_mode == "own_rhythm" and base_strength >= fallback_strength + 0.10:
            merged = dict(base)
            merged["relationship_weather"] = fallback_weather
            merged["strength"] = round(max(base_strength, fallback_strength), 3)
            merged["note"] = str(fallback.get("note") or merged.get("note") or "").strip()
            return merged
        return fallback

    if fallback_weather in {"warm_residue", "repair_residue"}:
        if fallback_strength >= base_strength + 0.08:
            return fallback
        merged = dict(base)
        merged["relationship_weather"] = fallback_weather
        if not str(merged.get("note") or "").strip():
            merged["note"] = str(fallback.get("note") or "").strip()
        return merged

    if fallback_strength > base_strength + 0.08:
        return fallback
    return base

def _prior_user_exchange_carryover(
    source_event: dict[str, Any] | None,
    prior_action: dict[str, Any] | None,
    *,
    prior_counterpart_assessment: dict[str, Any] | None = None,
    response_style_hint: str,
) -> InteractionCarryoverPayload:
    event = dict(source_event or {})
    if str(event.get("kind") or "").strip().lower() != "user_utterance":
        return {}
    action = dict(prior_action or {})
    if not action:
        return {}
    hint = str(response_style_hint or "").strip().lower() or "natural"
    if hint in {"structured", "memory_recall"}:
        return {}

    source_text = str(event.get("effective_text") or event.get("text") or "").strip()
    source_tags = {
        str(item).strip().lower()
        for item in (event.get("tags") if isinstance(event.get("tags"), list) else [])
        if str(item).strip()
    }
    interaction_mode = str(action.get("interaction_mode") or "").strip().lower()
    approach_style = str(action.get("approach_style") or "").strip().lower()
    affect_surface = str(action.get("affect_surface") or "").strip().lower()
    followup_intent = str(action.get("followup_intent") or "").strip().lower()
    disclosure_posture = str(action.get("disclosure_posture") or "").strip().lower()
    attention_target = str(action.get("attention_target") or "").strip() or "counterpart_state"
    nonverbal_signal = str(action.get("nonverbal_signal") or "").strip()
    primary_motive = str(action.get("primary_motive") or "").strip().lower()
    motive_tension = str(action.get("motive_tension") or "").strip().lower()
    goal_frame = str(action.get("goal_frame") or "").strip()
    initiative_level = _clamp01(action.get("initiative_level"), 0.0)
    engagement_level = _clamp01(action.get("engagement_level"), 0.0)
    assessment = dict(prior_counterpart_assessment or {})
    prior_stance = str(assessment.get("stance") or "").strip().lower()
    prior_scene = str(assessment.get("scene") or "").strip().lower()
    prior_boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.0)
    base_strength = max(initiative_level, 0.72 * engagement_level)
    explicit_repair_context = bool(
        prior_scene == "repair_attempt"
        or "repair" in source_tags
        or re.search(r"(道歉|说开|原谅|和好|别冷掉|正常回我|别装成陌生人|不在走流程|不是在走流程)", source_text)
    )
    guarded_brief_presence = bool(
        interaction_mode == "brief_presence"
        and (
            prior_stance in {"guarded", "watchful"}
            or prior_scene in {"friction", "relationship_degradation", "boundary_non_compliance", "repair_attempt"}
            or prior_boundary_pressure >= 0.18
            or motive_tension in {"space_vs_contact", "boundary_vs_closeness", "care_vs_guard"}
        )
    )
    guarded_relational_residue = bool(
        interaction_mode == "relationship_sensitive"
        and (
            prior_stance in {"guarded", "watchful"}
            or (
                str(action.get("action_target") or "").strip().lower() == "protect_relationship_boundary"
                and (prior_boundary_pressure >= 0.16 or prior_scene in {"relationship_degradation", "boundary_non_compliance", "friction"})
            )
        )
    )

    if (
        approach_style == "guarded"
        or (disclosure_posture == "guarded" and interaction_mode != "brief_presence")
        or affect_surface == "cool"
        or guarded_relational_residue
        or guarded_brief_presence
    ):
        strength = _clamp01(
            0.18
            + 0.14 * base_strength
            + (0.08 if disclosure_posture == "guarded" and interaction_mode != "brief_presence" else 0.0)
            + (0.06 if followup_intent == "none" else 0.0)
            + (0.04 if prior_stance == "guarded" else 0.0)
        )
        if strength < 0.16:
            return {}
        return {
            "source_event_kind": "user_utterance",
            "source_behavior_mode": interaction_mode,
            "source_action_target": str(action.get("action_target") or "").strip().lower(),
            "source_primary_motive": primary_motive,
            "source_motive_tension": motive_tension,
            "source_goal_frame": goal_frame,
            "source_text": str(event.get("effective_text") or event.get("text") or "").strip()[:180],
            "source_tags": [],
            "carryover_mode": "quiet_recontact",
            "strength": round(strength, 3),
            "relationship_weather": "guarded_residue",
            "idle_minutes": 0,
            "source_turn_gap": 0,
            "attention_target": "counterpart_state",
            "nonverbal_signal": nonverbal_signal or "quiet_glance",
            "note": "上一轮那点情绪还没完全退掉，这轮会先收一点。",
            "created_at": _now_ts(),
        }

    if (
        interaction_mode in {"low_pressure_support", "relationship_sensitive", "companion_reply", "shared_memory", "brief_presence"}
        and affect_surface in {"warm", "tender", "mixed"}
        and followup_intent in {"soft", "active"}
    ):
        if interaction_mode == "relationship_sensitive" and not explicit_repair_context:
            return {}
        weather = "repair_residue" if interaction_mode == "relationship_sensitive" else "warm_residue"
        strength = _clamp01(
            0.16
            + 0.16 * base_strength
            + (0.06 if affect_surface in {"warm", "tender"} else 0.0)
            + (0.04 if followup_intent == "active" else 0.0)
        )
        if strength < 0.16:
            return {}
        return {
            "source_event_kind": "user_utterance",
            "source_behavior_mode": interaction_mode,
            "source_action_target": str(action.get("action_target") or "").strip().lower(),
            "source_primary_motive": primary_motive,
            "source_motive_tension": motive_tension,
            "source_goal_frame": goal_frame,
            "source_text": str(event.get("effective_text") or event.get("text") or "").strip()[:180],
            "source_tags": [],
            "carryover_mode": "brief_presence" if weather == "repair_residue" else "small_opening",
            "strength": round(strength, 3),
            "relationship_weather": weather,
            "idle_minutes": 0,
            "source_turn_gap": 0,
            "attention_target": "counterpart_state",
            "nonverbal_signal": nonverbal_signal or ("quiet_notice" if weather == "repair_residue" else "brief_notice"),
            "note": "上一轮留下来的那点感觉还在，这轮不会一下子退回陌生。",
            "created_at": _now_ts(),
        }
    return {}

def _seeded_interaction_carryover_from_state(
    *,
    state: ThreadState,
    prior_current_event: dict[str, Any] | None,
    prior_behavior_action: dict[str, Any] | None,
) -> dict[str, Any]:
    if isinstance(prior_current_event, dict) and prior_current_event:
        return {}
    if isinstance(prior_behavior_action, dict) and prior_behavior_action:
        return {}
    seeded = state.get("interaction_carryover") if isinstance(state.get("interaction_carryover"), dict) else {}
    if not seeded:
        return {}
    carryover_mode = str(seeded.get("carryover_mode") or "").strip().lower()
    strength = _clamp01(seeded.get("strength"), 0.0)
    if not carryover_mode or strength < 0.12:
        return {}
    out: dict[str, Any] = {
        "source_event_kind": str(seeded.get("source_event_kind") or "seed_state").strip().lower() or "seed_state",
        "source_behavior_mode": str(seeded.get("source_behavior_mode") or "").strip().lower(),
        "source_action_target": str(seeded.get("source_action_target") or "").strip().lower(),
        "source_primary_motive": str(seeded.get("source_primary_motive") or "").strip().lower(),
        "source_motive_tension": str(seeded.get("source_motive_tension") or "").strip().lower(),
        "source_goal_frame": str(seeded.get("source_goal_frame") or "").strip(),
        "source_text": str(seeded.get("source_text") or "").strip()[:180],
        "source_tags": [
            str(item).strip()
            for item in (seeded.get("source_tags") if isinstance(seeded.get("source_tags"), list) else [])
            if str(item).strip()
        ],
        "carryover_mode": carryover_mode,
        "strength": round(strength, 3),
        "relationship_weather": str(seeded.get("relationship_weather") or "").strip().lower(),
        "idle_minutes": max(0, int(seeded.get("idle_minutes") or 0)),
        "source_turn_gap": max(0, int(seeded.get("source_turn_gap") or 0)),
        "attention_target": str(seeded.get("attention_target") or "").strip().lower(),
        "nonverbal_signal": str(seeded.get("nonverbal_signal") or "").strip().lower(),
        "note": str(seeded.get("note") or "").strip(),
        "created_at": int(seeded.get("created_at") or _now_ts()),
    }
    cleaned: dict[str, Any] = {}
    for key, value in out.items():
        if value is None:
            continue
        if isinstance(value, str) and not value:
            continue
        if isinstance(value, list) and not value:
            continue
        cleaned[key] = value
    return cleaned

def _relationship_signal_strength(relationship: dict[str, Any] | None) -> float:
    rel = relationship if isinstance(relationship, dict) else {}
    notes = str(rel.get("notes") or "").strip()
    stage = str(rel.get("stage") or "").strip().lower()
    try:
        affinity = abs(float(rel.get("affinity_score", 0.0) or 0.0))
    except Exception:
        affinity = 0.0
    try:
        trust = abs(float(rel.get("trust_score", 0.0) or 0.0))
    except Exception:
        trust = 0.0
    stage_bonus = {
        "trusted": 0.28,
        "warming": 0.18,
        "strained": 0.24,
        "friend": 0.0,
        "": 0.0,
    }.get(stage, 0.10)
    notes_bonus = 0.08 if notes else 0.0
    return affinity + trust + stage_bonus + notes_bonus

def _relationship_has_meaningful_signal(relationship: dict[str, Any] | None) -> bool:
    rel = relationship if isinstance(relationship, dict) else {}
    notes = str(rel.get("notes") or "").strip()
    stage = str(rel.get("stage") or "").strip().lower()
    try:
        affinity = abs(float(rel.get("affinity_score", 0.0) or 0.0))
    except Exception:
        affinity = 0.0
    try:
        trust = abs(float(rel.get("trust_score", 0.0) or 0.0))
    except Exception:
        trust = 0.0
    return bool(notes or affinity > 0.06 or trust > 0.06 or stage not in {"", "friend"})

def _prefer_relationship_state(*candidates: dict[str, Any] | None) -> dict[str, Any]:
    best: dict[str, Any] = {}
    best_strength = -1.0
    for item in candidates:
        if not isinstance(item, dict) or not item:
            continue
        strength = _relationship_signal_strength(item)
        if strength > best_strength:
            best = dict(item)
            best_strength = strength
    return best

def _prefer_refreshed_relationship_state(
    current_relationship: dict[str, Any] | None,
    refreshed_relationship: dict[str, Any] | None,
) -> dict[str, Any]:
    refreshed = dict(refreshed_relationship or {})
    if _relationship_has_meaningful_signal(refreshed):
        return refreshed
    current = dict(current_relationship or {})
    if _relationship_has_meaningful_signal(current):
        return current
    return _prefer_relationship_state(refreshed, current)

def _relationship_runtime_snapshot(
    *,
    relationship: dict[str, Any] | None,
    bond_state: dict[str, Any] | None,
    world_model_state: dict[str, Any] | None,
    counterpart_assessment: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rel = dict(relationship or {})
    bond = dict(bond_state or {})
    world = dict(world_model_state or {})
    assessment = dict(counterpart_assessment or {})
    semantic = dict(semantic_narrative_profile or {})
    stage = str(rel.get("stage") or "").strip().lower() or "friend"
    notes = str(rel.get("notes") or "").strip()
    try:
        affinity = float(rel.get("affinity_score", 0.0) or 0.0)
    except Exception:
        affinity = 0.0
    try:
        trust = float(rel.get("trust_score", 0.0) or 0.0)
    except Exception:
        trust = 0.0

    closeness = _clamp01(bond.get("closeness"), 0.5)
    bond_trust = _clamp01(bond.get("trust"), 0.5)
    hurt = _clamp01(bond.get("hurt"), 0.0)
    irritation = _clamp01(bond.get("irritation"), 0.0)
    maturity = _clamp01(world.get("relationship_maturity"), 0.0)
    bond_depth = _clamp01(world.get("bond_depth"), 0.0)
    repair_load = _clamp01(world.get("repair_load"), 0.0)
    tension = _clamp01(world.get("tension_load"), 0.0)
    semantic_history = _clamp01(semantic.get("history_weight"), 0.0)
    semantic_bond = _clamp01(semantic.get("bond_depth"), 0.0)
    semantic_presence = _clamp01(semantic.get("presence_carry"), 0.0)
    semantic_commitment = _clamp01(semantic.get("commitment_carry"), 0.0)
    semantic_repair = _clamp01(semantic.get("repair_residue"), 0.0)
    semantic_tension = _clamp01(semantic.get("tension_residue"), 0.0)
    semantic_boundary = _clamp01(semantic.get("boundary_residue"), 0.0)
    boundary = max(
        _clamp01(world.get("boundary_load"), 0.0),
        _clamp01(assessment.get("boundary_pressure"), 0.0),
    )
    relationship_memory_floor = _clamp01(
        0.28 * semantic_bond
        + 0.20 * semantic_presence
        + 0.18 * semantic_commitment
        + 0.18 * semantic_history
        + 0.16 * semantic_repair
    )
    relationship_tension_pressure = _clamp01(0.58 * semantic_tension + 0.42 * semantic_boundary)

    affinity_floor = _clamp_signed(
        0.70 * max(0.0, closeness - 0.5)
        + 0.08 * bond_depth
        + 0.06 * maturity
        + 0.14 * relationship_memory_floor
        - 0.12 * tension
        - 0.10 * relationship_tension_pressure
        - 0.10 * boundary
        - 0.10 * hurt
        - 0.06 * irritation,
        -1.5,
        1.5,
        0.0,
    )
    trust_floor = _clamp_signed(
        0.72 * max(0.0, bond_trust - 0.5)
        + 0.08 * maturity
        + 0.06 * repair_load
        + 0.10 * relationship_memory_floor
        + 0.06 * max(semantic_commitment, semantic_repair)
        - 0.14 * tension
        - 0.12 * relationship_tension_pressure
        - 0.12 * boundary
        - 0.12 * hurt
        - 0.08 * irritation,
        -1.5,
        1.5,
        0.0,
    )

    if trust <= 0.06:
        trust = max(trust, trust_floor)
    if affinity <= 0.06:
        affinity = max(affinity, affinity_floor)
    if trust < -0.06:
        trust = min(trust, trust_floor)
    if affinity < -0.06:
        affinity = min(affinity, affinity_floor)

    if trust <= -0.20 or affinity <= -0.20:
        stage = "strained"
    elif trust >= 0.45 and affinity >= 0.45:
        stage = "trusted"
    elif stage == "trusted":
        stage = "trusted"
    elif stage == "warming" or trust >= 0.18 or affinity >= 0.18:
        stage = "warming"
    else:
        stage = "friend"

    if stage == "friend" and relationship_memory_floor >= 0.44 and (trust >= 0.10 or affinity >= 0.10):
        stage = "warming"
    if stage == "warming" and relationship_tension_pressure >= 0.48 and trust <= 0.04 and affinity <= 0.04:
        stage = "strained"

    if not notes and stage == "friend" and (trust >= 0.05 or affinity >= 0.05):
        notes = "并不是从零开始的陌生状态，更像带着旧日熟悉感重新接上线。"
    if not notes and stage == "warming" and relationship_memory_floor >= 0.42:
        notes = "已经不只是普通寒暄，更像带着前面留下的熟悉感继续靠近。"
    if not notes and relationship_tension_pressure >= 0.46:
        notes = "前面留下的别扭和边界感还在，关系没有断，但也没有被自动翻篇。"

    return {
        "stage": stage,
        "notes": notes,
        "affinity_score": round(float(affinity), 3),
        "trust_score": round(float(trust), 3),
        "derived": bool(rel.get("derived", True)),
    }

def _focus_text(item: dict[str, Any]) -> str:
    return str(_record_value(item, "text", "") or _record_value(item, "summary", "") or "").strip()

def _focus_payload(items: list[dict[str, Any]], limit: int = 4) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for item in items[: max(1, int(limit))]:
        text = _focus_text(item)
        if not text:
            continue
        payload.append(
            {
                "kind": str(item.get("focus_kind") or item.get("category") or "memory").strip() or "memory",
                "text": text,
            }
        )
    return payload

def _compact_relationship_summary(relationship: dict[str, Any]) -> str:
    if not isinstance(relationship, dict):
        return "关系信息为空。"
    stage = str(relationship.get("stage") or "").strip() or "unknown"
    notes = str(relationship.get("notes") or "").strip()
    try:
        affinity = float(relationship.get("affinity_score", 0.0) or 0.0)
    except Exception:
        affinity = 0.0
    try:
        trust = float(relationship.get("trust_score", 0.0) or 0.0)
    except Exception:
        trust = 0.0
    if stage == "trusted":
        base = "已经形成了稳定而熟悉的共同历史。"
    elif trust >= 0.45 or affinity >= 0.45:
        base = "信任已经明显上升，关系开始变稳。"
    elif stage == "warming" or trust >= 0.20 or affinity >= 0.20:
        base = "还带着克制，但熟悉感已经在前面了，不需要像陌生人那样重新试探。"
    elif notes:
        base = notes[:120]
    else:
        base = "并不是从零开始的陌生状态，更像带着旧日熟悉感重新接上线。"
    if notes and notes not in base and not _looks_like_light_smalltalk(notes):
        base += f" 备注：{notes[:120]}"
    return base

def _counterpart_assessment_summary(
    assessment: dict[str, Any],
    *,
    counterpart_name: str = CANON_COUNTERPART_NAME,
) -> str:
    if not isinstance(assessment, dict) or not assessment:
        return ""
    stance = str(assessment.get("stance") or "").strip().lower()
    scene = str(assessment.get("scene") or "").strip().lower()
    respect = _clamp01(assessment.get("respect_level"), 0.5)
    reciprocity = _clamp01(assessment.get("reciprocity"), 0.5)
    pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    reliability = _clamp01(assessment.get("reliability_read"), 0.5)

    if scene == "busy_not_disrespectful":
        return f"你判断{counterpart_name}现在更像是忙乱或超负荷，不等于不尊重你。"
    if scene == "repair_attempt":
        if stance in {"guarded", "watchful"} or pressure >= 0.28:
            return f"你看得出{counterpart_name}是在认真补救，但这不等于现在就能当作已经翻篇。"
        return f"你判断{counterpart_name}这次是在认真修补，不是随口敷衍过去。"
    if scene == "care_bid":
        if respect >= 0.62 and reciprocity >= 0.58:
            return f"你觉得{counterpart_name}这句是在认真靠近你，不是普通客套。"
        return f"你会把{counterpart_name}这次开口当成一次真实靠近，而不是流程化回应。"
    if scene in {"relationship_degradation", "boundary_non_compliance", "friction"}:
        return f"你判断和{counterpart_name}之间那点摩擦还在，不会把这轮轻易读成已经没事。"
    if stance == "guarded":
        if pressure >= 0.62:
            return f"你会对{counterpart_name}保持明显警觉；如果越界继续发生，你会先拉开距离。"
        return f"你暂时不会完全放松，对{counterpart_name}仍保留距离和观察。"
    if stance == "watchful":
        if reliability < 0.46:
            return f"你还愿意继续和{counterpart_name}说，但会观察他是不是认真、稳定，而不是一时兴起。"
        if pressure >= 0.32:
            return f"你愿意继续回应{counterpart_name}，但会留意他是不是在试探你的边界。"
        return f"你对{counterpart_name}基本愿意继续打开，但还保留一点判断和余地。"
    if respect >= 0.62 and reciprocity >= 0.58:
        return f"你觉得{counterpart_name}基本是在认真对待你，也愿意双向互动。"
    if reliability >= 0.58:
        return f"你目前对{counterpart_name}的判断偏正面，愿意继续把这段互动当成双向关系。"
    return f"你此刻对{counterpart_name}的判断还在形成中，会边互动边继续观察。"

def _compact_counterpart_assessment_hint(
    assessment: dict[str, Any],
    *,
    counterpart_name: str = CANON_COUNTERPART_NAME,
) -> str:
    if not isinstance(assessment, dict) or not assessment:
        return ""
    summary = str(assessment.get("summary") or "").strip()
    if summary:
        return summary
    return _counterpart_assessment_summary(assessment, counterpart_name=counterpart_name)

def _worldline_focus(store: MemoryStore) -> list[dict[str, Any]]:
    if bool(ABLATE_WORLDLINE_MEMORY):
        return []
    commitments = store.list_commitments(limit=12)
    open_items: list[dict[str, Any]] = []
    for c in commitments:
        status = str(c.get("status") or c.get("content", {}).get("status") or "open").lower()
        if status in {"resolved", "done", "closed"}:
            continue
        open_items.append(c)
    open_items.sort(
        key=lambda item: (
            _commitment_priority(item),
            int(item.get("created_at") or 0),
        ),
        reverse=True,
    )
    repairs = store.list_conflict_repairs(limit=8)
    repairs.sort(
        key=lambda item: (
            _conflict_repair_salience(item),
            int(item.get("created_at") or 0),
        ),
        reverse=True,
    )
    bond_items = store.list_relationship_timeline(limit=8)
    bond_items.sort(
        key=lambda item: (
            _relationship_salience(item),
            int(item.get("created_at") or 0),
        ),
        reverse=True,
    )

    tension_items = store.list_unresolved_tensions(limit=8)
    tension_items.sort(
        key=lambda item: (
            _tension_salience(item),
            int(item.get("updated_at") or item.get("created_at") or 0),
        ),
        reverse=True,
    )

    focus: list[dict[str, Any]] = []
    seen_text: set[str] = set()

    def _push(items: list[dict[str, Any]], kind: str) -> None:
        for item in items:
            text = _focus_text(item)
            if not text or text in seen_text:
                continue
            enriched = dict(item)
            enriched["focus_kind"] = kind
            focus.append(enriched)
            seen_text.add(text)
            if len(focus) >= 5:
                break

    _push(open_items, "commitment")
    if len(focus) < 5:
        _push(tension_items, "unresolved_tension")
    if len(focus) < 5:
        _push(repairs, "conflict_repair")
    if len(focus) < 5:
        _push(bond_items, "relationship_timeline")
    return focus[:5]
