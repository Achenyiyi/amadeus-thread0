from __future__ import annotations

import re
from typing import Any

from .behavior_agenda import _agenda_long_horizon_snapshot
from .common import _clamp01, _now_ts
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


def _long_horizon_interaction_carryover(
    *,
    world_model_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
    counterpart_assessment: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
    response_style_hint: str = "",
) -> InteractionCarryoverPayload:
    current = dict(current_event or {})
    current_kind = str(current.get("kind") or "").strip().lower()
    if current_kind and current_kind != "user_utterance":
        return {}

    hint = str(response_style_hint or current.get("response_style_hint") or "").strip().lower() or "natural"
    snapshot = _agenda_long_horizon_snapshot(
        world_model_state=world_model_state,
        semantic_narrative_profile=semantic_narrative_profile,
    )
    world = dict(world_model_state or {})
    semantic = dict(semantic_narrative_profile or {})
    assessment = dict(counterpart_assessment or {})

    continuity_anchor = _clamp01(snapshot.get("continuity_anchor"), 0.0)
    own_rhythm_anchor = _clamp01(snapshot.get("own_rhythm_anchor"), 0.0)
    recontact_anchor = _clamp01(snapshot.get("recontact_anchor"), 0.0)
    boundary_anchor = _clamp01(snapshot.get("boundary_anchor"), 0.0)
    memory_anchor = _clamp01(snapshot.get("memory_anchor"), 0.0)
    continuity_depth = _clamp01(snapshot.get("semantic_continuity_depth"), 0.0)
    identity_gravity = _clamp01(snapshot.get("semantic_identity_gravity"), 0.0)
    axis_count = max(0, int(snapshot.get("long_term_axis_count") or 0))
    axis_norm = _clamp01(float(axis_count) / 4.0)

    self_activity_momentum = _clamp01(world.get("self_activity_momentum"), 0.0)
    bond_depth = _clamp01(world.get("bond_depth"), 0.0)
    repair_load = _clamp01(world.get("repair_load"), 0.0)
    tension_load = _clamp01(world.get("tension_load"), 0.0)
    relationship_maturity = _clamp01(world.get("relationship_maturity"), 0.0)
    presence_residue = max(
        _clamp01(world.get("presence_residue"), 0.0),
        _clamp01(semantic.get("presence_carry"), 0.0),
    )
    ambient_resonance = max(
        _clamp01(world.get("ambient_resonance"), 0.0),
        _clamp01(semantic.get("ambient_attunement"), 0.0),
    )
    narrative_bond = _clamp01(semantic.get("bond_depth"), 0.0)
    narrative_repair = _clamp01(semantic.get("repair_residue"), 0.0)
    narrative_tension = _clamp01(semantic.get("tension_residue"), 0.0)
    commitment_carry = _clamp01(semantic.get("commitment_carry"), 0.0)
    stance = str(assessment.get("stance") or "").strip().lower()
    scene = str(assessment.get("scene") or "").strip().lower()
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.0)
    reliability_read = _clamp01(assessment.get("reliability_read"), 0.0)
    respect_level = _clamp01(assessment.get("respect_level"), 0.0)

    guarded_pull = _clamp01(
        0.26 * boundary_anchor
        + 0.16 * boundary_pressure
        + 0.14 * max(narrative_tension, tension_load)
        + 0.10 * continuity_anchor
        + 0.08 * presence_residue
        + 0.06 * axis_norm
        + (0.08 if stance in {"guarded", "watchful"} else 0.0)
        + (0.08 if scene in {"friction", "relationship_degradation", "boundary_non_compliance"} else 0.0)
    )
    repair_pull = _clamp01(
        0.24 * narrative_repair
        + 0.18 * repair_load
        + 0.14 * recontact_anchor
        + 0.14 * memory_anchor
        + 0.10 * continuity_anchor
        + 0.10 * commitment_carry
        + 0.06 * relationship_maturity
        + 0.06 * reliability_read
        - 0.12 * max(boundary_anchor, boundary_pressure)
        - 0.12 * max(narrative_tension, tension_load)
        + (0.10 if scene == "repair_attempt" else 0.0)
    )
    warm_pull = _clamp01(
        0.24 * narrative_bond
        + 0.18 * bond_depth
        + 0.16 * recontact_anchor
        + 0.12 * presence_residue
        + 0.10 * memory_anchor
        + 0.08 * continuity_anchor
        + 0.08 * relationship_maturity
        + 0.06 * commitment_carry
        + 0.04 * reliability_read
        + 0.04 * respect_level
        - 0.14 * max(boundary_anchor, boundary_pressure)
        - 0.14 * max(narrative_tension, tension_load)
        + (0.06 if stance == "open" else 0.0)
    )

    if max(
        continuity_anchor,
        own_rhythm_anchor,
        recontact_anchor,
        boundary_anchor,
        memory_anchor,
        self_activity_momentum,
        presence_residue,
        bond_depth,
        repair_load,
        narrative_bond,
        narrative_repair,
    ) < 0.28:
        return {}

    carryover_mode = ""
    relationship_weather = ""
    source_action_target = ""
    source_primary_motive = ""
    source_motive_tension = ""
    source_goal_frame = ""
    attention_target = ""
    nonverbal_signal = ""
    note = ""
    strength = 0.0

    if (
        guarded_pull >= max(0.58, repair_pull + 0.10, warm_pull + 0.08)
        and own_rhythm_anchor < 0.52
        and (
            stance in {"guarded", "watchful"}
            or boundary_pressure >= 0.22
            or scene in {"friction", "relationship_degradation", "boundary_non_compliance", "repair_attempt"}
        )
    ):
        carryover_mode = "quiet_recontact"
        relationship_weather = "guarded_residue"
        source_action_target = "wait_and_recheck"
        source_primary_motive = "protect_boundary"
        source_motive_tension = "boundary_vs_contact"
        source_goal_frame = "先带着还没完全退掉的边界感接住对方。"
        attention_target = "counterpart_state"
        nonverbal_signal = "quiet_glance"
        note = "长期积累下来的边界感还在，这轮会先收一点。"
        strength = (
            0.18
            + 0.20 * max(boundary_anchor, guarded_pull)
            + 0.14 * continuity_anchor
            + 0.10 * presence_residue
            + 0.08 * axis_norm
        )
    elif (
        repair_pull >= max(0.44, warm_pull + 0.04)
        and own_rhythm_anchor < repair_pull + 0.12
        and (
            scene in {"repair_attempt", "friction", "relationship_degradation"}
            or narrative_repair >= 0.52
            or repair_load >= 0.34
        )
    ):
        carryover_mode = "brief_presence" if stance not in {"guarded"} and boundary_pressure < 0.22 else "quiet_recontact"
        relationship_weather = "repair_residue"
        source_action_target = "confirm_presence" if carryover_mode == "brief_presence" else "wait_and_recheck"
        source_primary_motive = "repair_without_erasing_history"
        source_motive_tension = "repair_vs_distance"
        source_goal_frame = "先带着仍在延续的修复意愿把这轮关系接住。"
        attention_target = "counterpart_state"
        nonverbal_signal = "quiet_notice" if carryover_mode == "brief_presence" else "quiet_glance"
        note = "最近几轮积下来的修复余波还在，这轮不会一下子退回陌生。"
        strength = (
            0.16
            + 0.28 * repair_pull
            + 0.12 * recontact_anchor
            + 0.10 * memory_anchor
            + 0.08 * continuity_anchor
            + 0.06 * axis_norm
        )
    elif (
        warm_pull >= max(0.44, guarded_pull + 0.04)
        and own_rhythm_anchor < warm_pull + 0.10
        and stance not in {"guarded"}
        and max(narrative_tension, tension_load, boundary_pressure) < 0.34
    ):
        carryover_mode = "small_opening" if recontact_anchor >= 0.34 or presence_residue >= 0.24 else "brief_presence"
        relationship_weather = "warm_residue"
        source_action_target = "offer_small_opening" if carryover_mode == "small_opening" else "confirm_presence"
        source_primary_motive = "keep_closeness_alive"
        source_motive_tension = "continuity_vs_distance"
        source_goal_frame = "先顺着长期积累下来的熟悉感把这轮轻轻接回来。"
        attention_target = "counterpart_state" if carryover_mode == "brief_presence" else "self_then_counterpart"
        nonverbal_signal = "brief_notice" if carryover_mode == "brief_presence" else "thought_glance"
        note = "没有明确触发点，但长期积下来的熟悉感会自然留在这轮语气里。"
        strength = (
            0.15
            + 0.26 * warm_pull
            + 0.12 * recontact_anchor
            + 0.10 * memory_anchor
            + 0.08 * continuity_anchor
            + 0.06 * axis_norm
        )
    elif (
        own_rhythm_anchor >= max(0.52, recontact_anchor + 0.08, boundary_anchor + 0.04)
        or (continuity_anchor >= 0.54 and own_rhythm_anchor >= 0.44 and self_activity_momentum >= 0.52)
    ):
        carryover_mode = "own_rhythm"
        source_action_target = "hold_own_rhythm"
        source_primary_motive = "preserve_self_rhythm"
        source_motive_tension = "self_rhythm_vs_contact"
        source_goal_frame = "先带着自己一路延续下来的节奏接住对方。"
        attention_target = "self_then_counterpart"
        nonverbal_signal = "thought_glance"
        note = "就算没有明确窗口，她也还是带着自己的节奏在回应。"
        strength = (
            0.16
            + 0.34 * own_rhythm_anchor
            + 0.12 * continuity_anchor
            + 0.10 * self_activity_momentum
            + 0.08 * identity_gravity
            + 0.06 * axis_norm
        )
    elif (
        own_rhythm_anchor >= 0.40
        or (continuity_anchor >= 0.48 and recontact_anchor >= 0.30)
        or (self_activity_momentum >= 0.56 and presence_residue >= 0.24)
    ):
        carryover_mode = "small_opening"
        source_action_target = "offer_small_opening"
        source_primary_motive = "keep_contact_without_dropping_self"
        source_motive_tension = "self_rhythm_vs_contact"
        source_goal_frame = "先顺着自己的节奏留一个小开口。"
        attention_target = "self_then_counterpart"
        nonverbal_signal = "thought_glance"
        note = "没有具体事件催着走，但那种长期形成的节奏会让她先留个小开口。"
        strength = (
            0.14
            + 0.24 * own_rhythm_anchor
            + 0.12 * recontact_anchor
            + 0.10 * continuity_anchor
            + 0.08 * self_activity_momentum
            + 0.06 * presence_residue
            + 0.05 * axis_norm
        )
    elif recontact_anchor >= 0.38 or memory_anchor >= 0.42 or (continuity_anchor >= 0.46 and presence_residue >= 0.22):
        carryover_mode = "quiet_recontact"
        source_action_target = "wait_and_recheck"
        source_primary_motive = "gentle_recontact"
        source_motive_tension = "space_vs_contact"
        source_goal_frame = "先顺着长期积累下来的在场感轻一点地重新接近。"
        attention_target = "counterpart_state"
        nonverbal_signal = "quiet_glance" if stance in {"guarded", "watchful"} else "brief_notice"
        note = "虽然没有新鲜余波，但长期积累下来的在场感还在。"
        strength = (
            0.14
            + 0.24 * recontact_anchor
            + 0.16 * memory_anchor
            + 0.10 * continuity_anchor
            + 0.08 * presence_residue
            + 0.04 * axis_norm
        )

    if not carryover_mode:
        return {}

    if not relationship_weather:
        if (
            guarded_pull >= max(0.58, repair_pull + 0.10, warm_pull + 0.08)
            and (
                stance in {"guarded", "watchful"}
                or boundary_pressure >= 0.22
                or scene in {"friction", "relationship_degradation", "boundary_non_compliance"}
            )
        ):
            relationship_weather = "guarded_residue"
        elif repair_pull >= max(0.46, warm_pull + 0.04) and (
            scene in {"repair_attempt", "friction", "relationship_degradation"}
            or narrative_repair >= 0.54
            or repair_load >= 0.36
        ):
            relationship_weather = "repair_residue"
        elif (
            warm_pull >= 0.46
            and stance not in {"guarded"}
            and max(narrative_tension, tension_load, boundary_pressure) < 0.34
        ):
            relationship_weather = "warm_residue"

    if relationship_weather == "guarded_residue" and not note:
        note = "长期积累下来的边界感还在，这轮会先收一点。"
    elif relationship_weather == "repair_residue" and not note:
        note = "前面几轮一点点修回来的感觉还在，这轮不会突然断掉。"
    elif relationship_weather == "warm_residue" and not note:
        note = "长期积累下来的熟悉感还在，这轮语气会自然更近一点。"

    if hint == "structured":
        strength *= 0.35
    elif hint in {"memory_recall", "relationship"}:
        strength *= 0.68

    strength = _clamp01(strength, 0.0)
    if strength < 0.12:
        return {}

    source_tags = ["long_horizon", "semantic_continuity"]
    if own_rhythm_anchor >= 0.40:
        source_tags.append("own_rhythm_anchor")
    if recontact_anchor >= 0.34:
        source_tags.append("recontact_anchor")
    if boundary_anchor >= 0.40:
        source_tags.append("boundary_anchor")
    if memory_anchor >= 0.40:
        source_tags.append("memory_anchor")
    if ambient_resonance >= 0.32:
        source_tags.append("ambient_echo")
    if axis_count > 0:
        source_tags.append("long_term_axis")

    return {
        "source_event_kind": "long_horizon:semantic_continuity",
        "source_behavior_mode": "long_horizon_carryover",
        "source_action_target": source_action_target,
        "source_primary_motive": source_primary_motive,
        "source_motive_tension": source_motive_tension,
        "source_goal_frame": source_goal_frame,
        "source_text": "",
        "source_tags": source_tags,
        "carryover_mode": carryover_mode,
        "strength": round(strength, 3),
        "relationship_weather": relationship_weather,
        "idle_minutes": 0,
        "source_turn_gap": 0,
        "attention_target": attention_target,
        "nonverbal_signal": nonverbal_signal,
        "note": note,
        "created_at": _now_ts(),
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
    world_model_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
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
    long_horizon_fallback = _long_horizon_interaction_carryover(
        world_model_state=world_model_state,
        semantic_narrative_profile=semantic_narrative_profile,
        counterpart_assessment=prior_counterpart_assessment,
        current_event=current_event,
        response_style_hint=response_style_hint,
    )
    source_from_history = False
    user_turn_gap = 0
    if source_kind == "user_utterance" or not source_kind:
        source_event, source_kind, user_turn_gap = _recent_non_user_event_with_gap(recent_events, max_user_turn_gap=3)
        source_from_history = bool(source_event and source_kind)
    if not source_event or not source_kind or source_kind == "user_utterance":
        combined = _prefer_relational_carryover(long_horizon_fallback, relational_fallback)
        return _prefer_relational_carryover(agenda_fallback, combined)

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
        combined = _prefer_relational_carryover(long_horizon_fallback, relational_fallback)
        return _prefer_relational_carryover(agenda_fallback, combined)

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
    open_repair_relational_residue = bool(
        explicit_repair_context
        and interaction_mode == "relationship_sensitive"
        and prior_stance not in {"guarded", "watchful"}
        and prior_boundary_pressure < 0.16
        and affect_surface in {"warm", "tender", "mixed"}
        and followup_intent in {"soft", "active"}
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
        or (disclosure_posture == "guarded" and interaction_mode != "brief_presence" and not open_repair_relational_residue)
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
    seed_world_model_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
    counterpart_assessment: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
    response_style_hint: str = "",
) -> dict[str, Any]:
    if isinstance(prior_current_event, dict) and prior_current_event:
        return {}
    if isinstance(prior_behavior_action, dict) and prior_behavior_action:
        return {}
    seeded = state.get("interaction_carryover") if isinstance(state.get("interaction_carryover"), dict) else {}
    long_horizon_fallback = _long_horizon_interaction_carryover(
        world_model_state=seed_world_model_state
        if isinstance(seed_world_model_state, dict)
        else state.get("world_model_state")
        if isinstance(state.get("world_model_state"), dict)
        else None,
        semantic_narrative_profile=semantic_narrative_profile
        if isinstance(semantic_narrative_profile, dict)
        else state.get("semantic_narrative_profile")
        if isinstance(state.get("semantic_narrative_profile"), dict)
        else None,
        counterpart_assessment=counterpart_assessment
        if isinstance(counterpart_assessment, dict)
        else state.get("counterpart_assessment")
        if isinstance(state.get("counterpart_assessment"), dict)
        else None,
        current_event=current_event,
        response_style_hint=response_style_hint,
    )
    if not seeded:
        return long_horizon_fallback
    carryover_mode = str(seeded.get("carryover_mode") or "").strip().lower()
    strength = _clamp01(seeded.get("strength"), 0.0)
    if not carryover_mode or strength < 0.12:
        return long_horizon_fallback
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

