from __future__ import annotations

import uuid
from typing import Any

from .state import AgendaLifecycleResiduePayload, BehaviorAgendaEntryPayload, EventPayload
from .turn_events import _now_ts

QUEUEABLE_BEHAVIOR_PLAN_KINDS = {"deferred_checkin", "self_activity_continue"}
_AGENDA_LONG_HORIZON_FLOAT_KEYS = (
    "continuity_anchor",
    "own_rhythm_anchor",
    "recontact_anchor",
    "boundary_anchor",
    "memory_anchor",
    "semantic_continuity_depth",
    "semantic_identity_gravity",
)
_AGENDA_LONG_HORIZON_INT_KEYS = ("long_term_axis_count",)


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
    except Exception:
        v = float(default)
    return max(0.0, min(1.0, v))


def _snapshot_value(raw: Any, key: str, default: float = 0.0) -> float:
    if not isinstance(raw, dict):
        return _clamp01(default, default)
    return _clamp01(raw.get(key), default)


def _agenda_long_horizon_snapshot(
    *,
    world_model_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
) -> dict[str, float | int]:
    world = world_model_state if isinstance(world_model_state, dict) else {}
    semantic = semantic_narrative_profile if isinstance(semantic_narrative_profile, dict) else {}
    persistence = semantic.get("persistence_snapshot") if isinstance(semantic.get("persistence_snapshot"), dict) else {}
    sedimentation = semantic.get("sedimentation_snapshot") if isinstance(semantic.get("sedimentation_snapshot"), dict) else {}

    continuity_depth = _snapshot_value(semantic, "continuity_depth")
    identity_gravity = _snapshot_value(semantic, "identity_gravity")
    long_term_axis_count = max(0, int(semantic.get("long_term_axis_count") or 0)) if isinstance(semantic, dict) else 0
    axis_norm = _clamp01(long_term_axis_count / 4.0)
    history_weight = _snapshot_value(semantic, "history_weight")
    commitment_carry = _snapshot_value(semantic, "commitment_carry")
    presence_carry = _snapshot_value(semantic, "presence_carry")
    boundary_residue = _snapshot_value(semantic, "boundary_residue")
    agency_drive = _snapshot_value(semantic, "agency_drive")
    rhythm_continuity = _snapshot_value(semantic, "rhythm_continuity")
    selfhood_integrity = _snapshot_value(semantic, "selfhood_integrity")
    world_self_activity = _snapshot_value(world, "self_activity_momentum")
    world_agency = _snapshot_value(world, "agency_load")
    world_boundary = _snapshot_value(world, "boundary_load")
    world_memory = _snapshot_value(world, "memory_gravity")

    rhythm_persistence = _snapshot_value(persistence, "rhythm_style")
    agency_persistence = _snapshot_value(persistence, "agency_style")
    boundary_persistence = _snapshot_value(persistence, "boundary_style")
    presence_persistence = _snapshot_value(persistence, "presence_style")
    commitment_persistence = _snapshot_value(persistence, "commitment_style")
    bond_sedimentation = _snapshot_value(sedimentation, "bond_style")
    rhythm_sedimentation = _snapshot_value(sedimentation, "rhythm_style")
    agency_sedimentation = _snapshot_value(sedimentation, "agency_style")
    boundary_sedimentation = _snapshot_value(sedimentation, "boundary_style")

    own_rhythm_anchor = _clamp01(
        0.26 * max(rhythm_continuity, rhythm_persistence, 0.92 * rhythm_sedimentation)
        + 0.18 * max(agency_drive, agency_persistence, 0.92 * agency_sedimentation)
        + 0.18 * world_self_activity
        + 0.12 * world_agency
        + 0.10 * continuity_depth
        + 0.08 * identity_gravity
        + 0.08 * axis_norm
    )
    recontact_anchor = _clamp01(
        0.24 * presence_carry
        + 0.20 * history_weight
        + 0.14 * commitment_carry
        + 0.14 * world_memory
        + 0.12 * max(presence_persistence, bond_sedimentation)
        + 0.08 * continuity_depth
        + 0.08 * axis_norm
    )
    continuity_anchor = _clamp01(
        0.32 * continuity_depth
        + 0.22 * identity_gravity
        + 0.16 * max(rhythm_continuity, agency_drive)
        + 0.14 * max(history_weight, world_memory)
        + 0.08 * axis_norm
        + 0.08 * max(rhythm_persistence, agency_persistence)
    )
    boundary_anchor = _clamp01(
        0.30 * max(boundary_residue, boundary_persistence, 0.92 * boundary_sedimentation)
        + 0.20 * world_boundary
        + 0.18 * identity_gravity
        + 0.12 * selfhood_integrity
        + 0.10 * continuity_depth
        + 0.10 * axis_norm
    )
    memory_anchor = _clamp01(
        0.28 * max(history_weight, world_memory)
        + 0.22 * commitment_carry
        + 0.16 * presence_carry
        + 0.14 * max(commitment_persistence, bond_sedimentation)
        + 0.12 * continuity_depth
        + 0.08 * axis_norm
    )
    return {
        "continuity_anchor": round(continuity_anchor, 3),
        "own_rhythm_anchor": round(own_rhythm_anchor, 3),
        "recontact_anchor": round(recontact_anchor, 3),
        "boundary_anchor": round(boundary_anchor, 3),
        "memory_anchor": round(memory_anchor, 3),
        "semantic_continuity_depth": round(continuity_depth, 3),
        "semantic_identity_gravity": round(identity_gravity, 3),
        "long_term_axis_count": int(long_term_axis_count),
    }


def _agenda_long_horizon_bias(
    entry: dict[str, Any],
    *,
    world_model_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
) -> dict[str, float | int]:
    current = _agenda_long_horizon_snapshot(
        world_model_state=world_model_state,
        semantic_narrative_profile=semantic_narrative_profile,
    )
    merged: dict[str, float | int] = dict(current)
    for key in _AGENDA_LONG_HORIZON_FLOAT_KEYS:
        merged[key] = round(max(_clamp01(entry.get(key), 0.0), float(current.get(key) or 0.0)), 3)
    merged["long_term_axis_count"] = max(
        max(0, int(entry.get("long_term_axis_count") or 0)),
        int(current.get("long_term_axis_count") or 0),
    )
    return merged


def _merge_long_horizon_entry_fields(*entries: dict[str, Any] | None) -> dict[str, float | int]:
    merged: dict[str, float | int] = {}
    for key in _AGENDA_LONG_HORIZON_FLOAT_KEYS:
        merged[key] = round(
            max([_clamp01(entry.get(key), 0.0) for entry in entries if isinstance(entry, dict)] or [0.0]),
            3,
        )
    merged["long_term_axis_count"] = max(
        [max(0, int(entry.get("long_term_axis_count") or 0)) for entry in entries if isinstance(entry, dict)]
        or [0]
    )
    return merged

def _promote_due_behavior_plan_event(event: EventPayload, prior_behavior_plan: Any) -> EventPayload:
    if not isinstance(event, dict) or not event:
        return event
    if str(event.get("kind") or "").strip() != "time_idle":
        return event
    if not isinstance(prior_behavior_plan, dict):
        return event

    plan_kind = str(prior_behavior_plan.get("kind") or "").strip()
    if plan_kind not in {"deferred_checkin", "self_activity_continue"}:
        return event

    try:
        idle_minutes = max(0, int(event.get("idle_minutes") or 0))
    except Exception:
        idle_minutes = 0
    try:
        due_after = max(0, int(prior_behavior_plan.get("scheduled_after_min") or 0))
    except Exception:
        due_after = 0
    if idle_minutes < max(1, due_after):
        return event

    trigger_family = str(prior_behavior_plan.get("trigger_family") or "light_checkin").strip() or "light_checkin"
    tags = event.get("tags") if isinstance(event.get("tags"), list) else []
    note = str(prior_behavior_plan.get("note") or "").strip()
    carryover_mode = str(prior_behavior_plan.get("carryover_mode") or "").strip()
    carryover_strength = _clamp01(prior_behavior_plan.get("carryover_strength"), 0.0)
    relationship_weather = str(prior_behavior_plan.get("relationship_weather") or "").strip().lower()
    primary_motive = str(prior_behavior_plan.get("primary_motive") or "").strip()
    motive_tension = str(prior_behavior_plan.get("motive_tension") or "").strip()
    goal_frame = str(prior_behavior_plan.get("goal_frame") or "").strip()
    attention_target = str(prior_behavior_plan.get("attention_target") or "").strip()
    nonverbal_signal = str(prior_behavior_plan.get("nonverbal_signal") or "").strip()
    presence_residue = _clamp01(prior_behavior_plan.get("presence_residue"), 0.0)
    ambient_resonance = _clamp01(prior_behavior_plan.get("ambient_resonance"), 0.0)
    self_activity_momentum = _clamp01(prior_behavior_plan.get("self_activity_momentum"), 0.0)
    promoted = dict(event)
    if plan_kind == "self_activity_continue":
        reopen_hint = bool(
            carryover_mode == "small_opening"
            or (
                self_activity_momentum < 0.58
                and (
                    carryover_strength >= 0.56
                    or presence_residue >= 0.30
                    or ambient_resonance >= 0.32
                )
            )
        )
        quiet_reapproach = bool(
            not reopen_hint
            and (
                carryover_mode in {"quiet_recontact", "brief_presence"}
                or presence_residue >= 0.28
                or ambient_resonance >= 0.30
            )
        )
        merged_tags = list(
            dict.fromkeys(
                item
                for item in [
                    *(str(item).strip() for item in tags if str(item).strip()),
                    "self_activity",
                    "break_window" if reopen_hint else "",
                    "small_opening" if reopen_hint else "",
                    "reapproach" if (reopen_hint or quiet_reapproach) else "",
                    "quiet_presence" if presence_residue >= 0.28 else "",
                    "ambient_echo" if ambient_resonance >= 0.32 else "",
                    "deep_focus" if self_activity_momentum >= 0.58 else "",
                    "own_task" if self_activity_momentum >= 0.64 and (carryover_mode == "own_rhythm" or carryover_strength >= 0.58) else "",
                ]
                if item
            )
        )
        promoted_text = "你手头那件事暂时告一段落，像是终于空出一点点注意力，又把视线偏回了对方这边。"
        if self_activity_momentum >= 0.64 and carryover_mode == "own_rhythm":
            promoted_text = "你手头那点事还没真正放下，只是隔着自己的节奏，短暂把注意力往对方这边偏了一下。"
        elif self_activity_momentum >= 0.58:
            promoted_text = "你先把自己手头那点事收了个尾，过了一会儿才像是终于愿意把注意力重新抬起来。"
        elif reopen_hint:
            promoted_text = "你没有一下子凑近，只是从自己的节奏里抬起头，顺手留了一个很小的开口。"
        elif quiet_reapproach:
            promoted_text = "你没有完全从自己的事情里抽出来，只是顺着那点还没散掉的在场感，安静地留意了一下对方这边。"
        promoted_frame = note or (
            "你从自己手头的事情里抬起头，留下一个自然的小开口。"
            if reopen_hint
            else "你还在自己的节奏里，只是注意力短暂松了一下。"
        )
        if presence_residue >= 0.30:
            promoted_frame += " 前面那点在场感还没完全退掉。"
        if ambient_resonance >= 0.32:
            promoted_frame += " 刚才环境里的细小动静也还留在你的感知里。"
        promoted.update(
            {
                "kind": "self_activity_state",
                "source": "self",
                "text": promoted_text,
                "effective_text": promoted_text,
                "semantic_goal": (
                    "你从自己的节奏里重新抬头，留一个小开口。"
                    if reopen_hint
                    else "你仍在自己的节奏里，只是短暂把注意力挪向外界。"
                ),
                "event_frame": promoted_frame,
                "tags": merged_tags,
                "derived_from_plan_kind": plan_kind,
                "trigger_family": trigger_family or "self_activity",
                "scheduled_after_min": due_after,
                "carryover_mode": carryover_mode or "own_rhythm",
                "carryover_strength": round(max(carryover_strength, self_activity_momentum), 3),
                "relationship_weather": relationship_weather,
                "primary_motive": primary_motive,
                "motive_tension": motive_tension,
                "goal_frame": goal_frame,
                "presence_residue": round(presence_residue, 3),
                "ambient_resonance": round(ambient_resonance, 3),
                "self_activity_momentum": round(self_activity_momentum, 3),
                "attention_target_hint": attention_target,
                "nonverbal_signal_hint": nonverbal_signal,
            }
        )
        return promoted

    effective_carryover_mode = carryover_mode or ("quiet_recontact" if trigger_family in {"observe", "light_checkin"} else "")
    recontact_echo = max(
        presence_residue,
        0.82 * ambient_resonance,
        carryover_strength if effective_carryover_mode in {"quiet_recontact", "brief_presence", "small_opening"} else 0.0,
    )
    own_rhythm_load = max(
        self_activity_momentum,
        carryover_strength if effective_carryover_mode == "own_rhythm" else 0.45 * carryover_strength if effective_carryover_mode == "small_opening" else 0.0,
    )
    extra_tags: list[str] = []
    if trigger_family in {"shared_activity", "shared_activity_window"}:
        extra_tags.extend(["shared_activity_window", "offer_window"])
    elif trigger_family == "deadline_window":
        extra_tags.extend(["deadline_window", "task_window", "work_nudge", "shared_task"])
    elif trigger_family == "life_window":
        extra_tags.append("life_window")
    if effective_carryover_mode in {"quiet_recontact", "brief_presence"} or recontact_echo >= 0.28:
        extra_tags.append("quiet_presence")
    if effective_carryover_mode == "ambient_echo" or ambient_resonance >= 0.30:
        extra_tags.append("ambient_echo")
    if effective_carryover_mode in {"own_rhythm", "small_opening"} or own_rhythm_load >= 0.34:
        extra_tags.append("from_own_rhythm")
    merged_tags = list(
        dict.fromkeys(
            [
                *(str(item).strip() for item in tags if str(item).strip()),
                "scheduled_due",
                trigger_family,
                *extra_tags,
            ]
        )
    )
    promoted_text = "之前延后的接近理由并没有完全退掉，过了一会儿又轻轻回到了你的注意力里。"
    semantic_goal = "延后的接近理由重新回到你的注意力里。"
    if trigger_family in {"shared_activity", "shared_activity_window"}:
        promoted_text = "你们刚才顺手留出来的那点空当还没完全过去，过了一会儿你又想起了对方。"
        semantic_goal = "你又想起你们刚才那点还能一起接着做点什么的空当。"
    elif trigger_family == "deadline_window":
        promoted_text = "前面挂着的那件事又回到了你的注意力里，像是到了可以轻轻提一下的节点。"
        semantic_goal = "前面挂着的事重新浮回你的注意力里。"
    elif trigger_family == "life_window":
        promoted_text = "前面那点生活上的事又被你想起来了，不过更像顺手惦记一下，不是任务提醒。"
        semantic_goal = "你又想起前面提过的那点生活上的事。"
        if own_rhythm_load >= 0.56:
            promoted_text = "你还在自己的节奏里，但又忽然想起对方前面提过的那点生活上的事。"
        elif recontact_echo >= 0.30:
            promoted_text = "前面那点生活上的小惦记没完全过去，过了一会儿你又想起来了。"
    elif effective_carryover_mode == "ambient_echo" or ambient_resonance >= 0.30:
        promoted_text = "刚才环境里留下的那点余波，让你又顺手想起了对方。"
        semantic_goal = "环境余波让你重新想到对方。"
    elif own_rhythm_load >= 0.56 and effective_carryover_mode in {"own_rhythm", "small_opening"}:
        promoted_text = "你还在自己的节奏里，但前面那点没说出口的确认感又轻轻碰了你一下。"
        semantic_goal = "你仍在自己的节奏里，但没说出口的确认感又回到注意力里。"
    elif recontact_echo >= 0.28 or effective_carryover_mode in {"quiet_recontact", "brief_presence"}:
        promoted_text = "前面那点没说出口的确认感还没散掉，过了一会儿又回到了你的注意力里。"
        semantic_goal = "没说出口的确认感重新回到你的注意力里。"
    promoted_frame = note or (
        "你不是专门停下手头的事来找对方，只是注意力又短暂偏了回来。"
        if own_rhythm_load >= 0.56
        else "前面那点没说出口的余温，过了一会儿又轻轻回到了你的注意力里。"
        if recontact_echo >= 0.28
        else "之前延后的接近理由，现在又轻轻回到了你的注意力里。"
    )
    if ambient_resonance >= 0.32:
        promoted_frame += " 刚才环境里的细小动静也还留在你的感知里。"
    promoted.update(
        {
            "kind": "scheduled_checkin_due",
            "source": "scheduler",
            "text": promoted_text,
            "effective_text": promoted_text,
            "semantic_goal": semantic_goal[:220],
            "event_frame": promoted_frame,
            "tags": merged_tags,
            "derived_from_plan_kind": plan_kind,
            "trigger_family": trigger_family,
            "scheduled_after_min": due_after,
            "carryover_mode": effective_carryover_mode,
            "carryover_strength": round(max(carryover_strength, presence_residue, ambient_resonance), 3),
            "relationship_weather": relationship_weather,
            "primary_motive": primary_motive,
            "motive_tension": motive_tension,
            "goal_frame": goal_frame,
            "presence_residue": round(presence_residue, 3),
            "ambient_resonance": round(ambient_resonance, 3),
            "self_activity_momentum": round(self_activity_momentum, 3),
            "attention_target_hint": attention_target,
            "nonverbal_signal_hint": nonverbal_signal,
        }
    )
    return promoted


def _promote_due_behavior_action_event(
    event: EventPayload,
    prior_current_event: Any,
    prior_behavior_action: Any,
) -> EventPayload:
    if not isinstance(event, dict) or not event:
        return event
    if str(event.get("kind") or "").strip() != "time_idle":
        return event
    if not isinstance(prior_behavior_action, dict):
        return event
    if str(prior_behavior_action.get("action_target") or "").strip() != "wait_and_recheck":
        return event
    if not isinstance(prior_current_event, dict):
        return event
    if str(prior_current_event.get("kind") or "").strip() != "time_idle":
        return event

    try:
        idle_minutes = max(0, int(event.get("idle_minutes") or 0))
    except Exception:
        idle_minutes = 0
    try:
        due_after = max(0, int(prior_behavior_action.get("timing_window_min") or 0))
    except Exception:
        due_after = 0
    if idle_minutes < max(1, due_after):
        return event

    trigger_family = str(prior_behavior_action.get("deferred_action_family") or "light_checkin").strip() or "light_checkin"
    attention_target_hint = str(prior_behavior_action.get("attention_target") or "").strip()
    nonverbal_signal_hint = str(prior_behavior_action.get("nonverbal_signal") or "").strip()
    relationship_weather = str(prior_behavior_action.get("relationship_weather") or "").strip().lower()
    tags = event.get("tags") if isinstance(event.get("tags"), list) else []
    extra_tags: list[str] = []
    if trigger_family in {"shared_activity", "shared_activity_window"}:
        extra_tags.extend(["shared_activity_window", "offer_window"])
    elif trigger_family == "deadline_window":
        extra_tags.extend(["deadline_window", "task_window", "work_nudge", "shared_task"])
    elif trigger_family == "life_window":
        extra_tags.append("life_window")
    elif trigger_family in {"observe", "light_checkin"}:
        extra_tags.append("quiet_presence")
    merged_tags = list(
        dict.fromkeys(
            [
                *(str(item).strip() for item in tags if str(item).strip()),
                "scheduled_due",
                trigger_family,
                *extra_tags,
            ]
        )
    )
    promoted = dict(event)
    promoted_text = "之前延后的接近理由，现在又轻轻回到了你的注意力里。"
    semantic_goal = "延后的接近理由重新回到你的注意力里。"
    if trigger_family in {"shared_activity", "shared_activity_window"}:
        promoted_text = "你们刚才顺手留出来的那点空当还没完全过去，过了一会儿你又想起了对方。"
        semantic_goal = "你又想起你们刚才那点还能一起接着做点什么的空当。"
    elif trigger_family == "deadline_window":
        promoted_text = "前面挂着的那件事又回到了你的注意力里，像是到了可以轻轻提一下的节点。"
        semantic_goal = "前面挂着的事重新浮回你的注意力里。"
    elif trigger_family == "life_window":
        promoted_text = "前面那点生活上的事又被你想起来了，不过更像顺手惦记一下，不是任务提醒。"
        semantic_goal = "你又想起前面提过的那点生活上的事。"
    elif trigger_family in {"observe", "light_checkin"}:
        promoted_text = "前面那点没说出口的确认感，过了一会儿又轻轻回到了你的注意力里。"
        semantic_goal = "没说出口的确认感重新回到你的注意力里。"
    promoted.update(
        {
            "kind": "scheduled_checkin_due",
            "source": "scheduler",
            "text": promoted_text,
            "effective_text": promoted_text,
            "semantic_goal": semantic_goal[:220],
            "event_frame": (
                str(event.get("event_frame") or "").strip()
                or "之前延后的接近理由，现在又轻轻回到了你的注意力里。"
            ),
            "tags": merged_tags,
            "derived_from_plan_kind": "implicit_deferred_checkin",
            "trigger_family": trigger_family,
            "scheduled_after_min": due_after,
            "carryover_mode": "quiet_recontact" if trigger_family in {"observe", "light_checkin"} else "",
            "relationship_weather": relationship_weather,
            "attention_target_hint": attention_target_hint,
            "nonverbal_signal_hint": nonverbal_signal_hint,
        }
    )
    return promoted


def _normalize_behavior_agenda(raw: Any, *, limit: int = 8) -> list[BehaviorAgendaEntryPayload]:
    if not isinstance(raw, list):
        return []
    items: list[BehaviorAgendaEntryPayload] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        kind = str(entry.get("kind") or "").strip()
        target = str(entry.get("target") or "").strip() or "counterpart"
        if not kind:
            continue
        try:
            scheduled_after_min = max(0, int(entry.get("scheduled_after_min") or 0))
        except Exception:
            scheduled_after_min = 0
        try:
            expires_after_min = max(0, int(entry.get("expires_after_min") or 0))
        except Exception:
            expires_after_min = 0
        try:
            priority = float(entry.get("priority") or 0.0)
        except Exception:
            priority = 0.0
        try:
            base_priority = float(entry.get("base_priority") or priority)
        except Exception:
            base_priority = priority
        normalized: BehaviorAgendaEntryPayload = {
            "agenda_id": str(entry.get("agenda_id") or uuid.uuid4().hex[:12]).strip(),
            "kind": kind,
            "target": target,
            "scheduled_after_min": scheduled_after_min,
            "expires_after_min": expires_after_min,
            "base_priority": max(0.0, min(1.0, base_priority)),
            "priority": max(0.0, min(1.0, priority)),
            "trigger_family": str(entry.get("trigger_family") or "none").strip() or "none",
            "allow_interrupt": bool(entry.get("allow_interrupt", True)),
            "primary_motive": str(entry.get("primary_motive") or "").strip(),
            "motive_tension": str(entry.get("motive_tension") or "").strip(),
            "goal_frame": str(entry.get("goal_frame") or "").strip(),
            "note": str(entry.get("note") or "").strip(),
            "source_event_kind": str(entry.get("source_event_kind") or "").strip(),
            "created_at": int(entry.get("created_at") or _now_ts()),
            "status": str(entry.get("status") or "pending").strip() or "pending",
            "hold_count": max(0, int(entry.get("hold_count") or 0)),
            "last_recheck_at_min": max(0, int(entry.get("last_recheck_at_min") or 0)),
            "carryover_mode": str(entry.get("carryover_mode") or "").strip(),
            "carryover_strength": round(_clamp01(entry.get("carryover_strength"), 0.0), 3),
            "relationship_weather": str(entry.get("relationship_weather") or "").strip(),
            "attention_target": str(entry.get("attention_target") or "").strip(),
            "nonverbal_signal": str(entry.get("nonverbal_signal") or "").strip(),
            "presence_residue": round(_clamp01(entry.get("presence_residue"), 0.0), 3),
            "ambient_resonance": round(_clamp01(entry.get("ambient_resonance"), 0.0), 3),
            "self_activity_momentum": round(_clamp01(entry.get("self_activity_momentum"), 0.0), 3),
            "continuity_anchor": round(_clamp01(entry.get("continuity_anchor"), 0.0), 3),
            "own_rhythm_anchor": round(_clamp01(entry.get("own_rhythm_anchor"), 0.0), 3),
            "recontact_anchor": round(_clamp01(entry.get("recontact_anchor"), 0.0), 3),
            "boundary_anchor": round(_clamp01(entry.get("boundary_anchor"), 0.0), 3),
            "memory_anchor": round(_clamp01(entry.get("memory_anchor"), 0.0), 3),
            "semantic_continuity_depth": round(_clamp01(entry.get("semantic_continuity_depth"), 0.0), 3),
            "semantic_identity_gravity": round(_clamp01(entry.get("semantic_identity_gravity"), 0.0), 3),
            "long_term_axis_count": max(0, int(entry.get("long_term_axis_count") or 0)),
        }
        items.append(normalized)
    items.sort(key=lambda item: (-float(item.get("priority") or 0.0), int(item.get("created_at") or 0), str(item.get("agenda_id") or "")))
    return items[: max(1, int(limit))]


def _behavior_agenda_priority_from_plan(current_event: dict[str, Any], plan: dict[str, Any]) -> float:
    kind = str(plan.get("kind") or "").strip()
    trigger_family = str(plan.get("trigger_family") or "").strip()
    event_kind = str(current_event.get("kind") or "").strip()
    if kind == "self_activity_continue":
        return 0.66
    if kind == "deferred_checkin":
        if trigger_family == "light_checkin":
            return 0.52
        if trigger_family == "observe":
            return 0.38
        return 0.46
    if event_kind == "scheduled_life_due":
        return 0.58
    return 0.4


def _behavior_agenda_counterpart_delta(entry: dict[str, Any], counterpart_assessment: dict[str, Any] | None) -> float:
    if not isinstance(entry, dict):
        return 0.0
    assessment = counterpart_assessment if isinstance(counterpart_assessment, dict) else {}
    if not assessment:
        return 0.0

    target = str(entry.get("target") or "").strip()
    kind = str(entry.get("kind") or "").strip()
    trigger_family = str(entry.get("trigger_family") or "").strip()
    if target != "counterpart":
        if kind == "self_activity_continue":
            stance = str(assessment.get("stance") or "").strip().lower()
            boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
            if stance == "guarded":
                return 0.08 + 0.08 * boundary_pressure
            if stance == "watchful":
                return 0.03 + 0.05 * boundary_pressure
        return 0.0

    stance = str(assessment.get("stance") or "").strip().lower()
    scene = str(assessment.get("scene") or "").strip().lower()
    respect = _clamp01(assessment.get("respect_level"), 0.5)
    reciprocity = _clamp01(assessment.get("reciprocity"), 0.5)
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    reliability = _clamp01(assessment.get("reliability_read"), 0.5)
    delta = 0.0

    if stance == "guarded":
        delta -= 0.14 + 0.10 * boundary_pressure
        if trigger_family in {"shared_activity", "shared_activity_window", "life_window"}:
            delta -= 0.04
    elif stance == "watchful":
        delta -= 0.04 + 0.08 * max(0.0, boundary_pressure - 0.2)
    else:
        delta += 0.06 * max(0.0, respect - 0.5) + 0.04 * max(0.0, reciprocity - 0.5) + 0.03 * max(0.0, reliability - 0.5)

    if scene in {"boundary_non_compliance", "relationship_degradation"}:
        delta -= 0.08
    elif scene == "repair_attempt":
        delta += 0.06
    elif scene == "care_bid":
        delta += 0.04
    elif scene == "busy_not_disrespectful":
        delta += 0.02

    return delta


def _behavior_agenda_history_delta(entry: dict[str, Any], current_event: dict[str, Any]) -> float:
    if not isinstance(entry, dict):
        return 0.0

    kind = str(entry.get("kind") or "").strip()
    trigger_family = str(entry.get("trigger_family") or "").strip()
    hold_count = max(0, int(entry.get("hold_count") or 0))
    if hold_count <= 0:
        return 0.0

    event_kind = str(current_event.get("kind") or "").strip()
    try:
        idle_minutes = max(0, int(current_event.get("idle_minutes") or 0))
    except Exception:
        idle_minutes = 0
    try:
        last_recheck_at_min = max(0, int(entry.get("last_recheck_at_min") or 0))
    except Exception:
        last_recheck_at_min = 0
    try:
        expires_after_min = max(0, int(entry.get("expires_after_min") or 0))
    except Exception:
        expires_after_min = 0

    delta = 0.0
    if kind == "deferred_checkin":
        per_hold_penalty = 0.02 if trigger_family in {"shared_activity", "shared_activity_window", "deadline_window", "life_window"} else 0.03
        delta -= min(0.18, per_hold_penalty * hold_count)
    elif kind == "self_activity_continue":
        delta -= min(0.08, 0.015 * hold_count)

    if event_kind == "time_idle":
        if last_recheck_at_min > 0 and idle_minutes <= last_recheck_at_min + 6:
            delta -= 0.04
        if kind == "deferred_checkin" and expires_after_min > 0:
            remaining_window = max(0, expires_after_min - idle_minutes)
            if remaining_window <= 12:
                delta -= 0.08
            elif remaining_window <= 24:
                delta -= 0.04

    return delta


def _behavior_agenda_context_priority(
    current_event: dict[str, Any],
    entry: dict[str, Any],
    counterpart_assessment: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
) -> float:
    base_priority = float(entry.get("base_priority") or entry.get("priority") or 0.0)
    kind = str(entry.get("kind") or "").strip()
    trigger_family = str(entry.get("trigger_family") or "").strip()
    target = str(entry.get("target") or "").strip()
    event_kind = str(current_event.get("kind") or "").strip()
    event_tags = {
        str(item).strip()
        for item in (current_event.get("tags") if isinstance(current_event.get("tags"), list) else [])
        if str(item).strip()
    }
    carryover_mode = str(entry.get("carryover_mode") or "").strip()
    carryover_strength = _clamp01(entry.get("carryover_strength"), 0.0)
    presence_residue = _clamp01(entry.get("presence_residue"), 0.0)
    ambient_resonance = _clamp01(entry.get("ambient_resonance"), 0.0)
    self_activity_momentum = _clamp01(entry.get("self_activity_momentum"), 0.0)
    long_horizon = _agenda_long_horizon_bias(
        entry,
        world_model_state=world_model_state,
        semantic_narrative_profile=semantic_narrative_profile,
    )
    continuity_anchor = _clamp01(long_horizon.get("continuity_anchor"), 0.0)
    own_rhythm_anchor = _clamp01(long_horizon.get("own_rhythm_anchor"), 0.0)
    recontact_anchor = _clamp01(long_horizon.get("recontact_anchor"), 0.0)
    boundary_anchor = _clamp01(long_horizon.get("boundary_anchor"), 0.0)
    memory_anchor = _clamp01(long_horizon.get("memory_anchor"), 0.0)
    delta = 0.0

    if event_kind == "time_idle":
        if "user_busy" in event_tags or "cognitive_load" in event_tags:
            if kind == "deferred_checkin" and target == "counterpart":
                delta -= 0.18 if trigger_family in {"light_checkin", "deadline_window", "life_window"} else 0.12
            elif kind == "self_activity_continue":
                delta += 0.06
        if "respect_space" in event_tags and kind == "deferred_checkin":
            delta -= 0.08
        if "late_night" in event_tags or "quiet_presence" in event_tags:
            if kind == "deferred_checkin" and trigger_family in {"light_checkin", "observe"}:
                delta += 0.18 if trigger_family == "light_checkin" else 0.28
            elif kind == "self_activity_continue":
                delta -= 0.05
        if "quiet_work" in event_tags and kind == "deferred_checkin" and trigger_family == "light_checkin":
            delta += 0.04
        if kind == "deferred_checkin" and carryover_mode == "quiet_recontact":
            delta += 0.04 * carryover_strength + 0.03 * presence_residue
        if kind == "deferred_checkin" and carryover_mode == "ambient_echo":
            delta += 0.03 * ambient_resonance
    elif event_kind == "scheduled_life_due":
        if kind == "deferred_checkin" and trigger_family in {"life_window", "shared_activity_window", "deadline_window"}:
            delta += 0.18
        elif kind == "self_activity_continue":
            delta -= 0.08
    elif event_kind == "self_activity_state":
        if kind == "self_activity_continue":
            delta += 0.10
            if carryover_mode in {"own_rhythm", "small_opening"}:
                delta += 0.04 * self_activity_momentum
        elif kind == "deferred_checkin" and target == "counterpart":
            delta -= 0.04

    if event_kind in {"time_idle", "self_activity_state", "scheduled_life_due"}:
        if kind == "self_activity_continue":
            delta += 0.08 * own_rhythm_anchor + 0.04 * continuity_anchor
            if event_kind in {"time_idle", "self_activity_state"}:
                delta += 0.04 * own_rhythm_anchor + 0.03 * continuity_anchor
            if boundary_anchor >= 0.48 and event_kind == "time_idle":
                delta += 0.02 * boundary_anchor
        elif kind == "deferred_checkin":
            if trigger_family in {"observe", "light_checkin"}:
                delta -= 0.06 * own_rhythm_anchor + 0.04 * continuity_anchor
                delta += 0.02 * recontact_anchor
            elif trigger_family == "life_window":
                delta -= 0.05 * own_rhythm_anchor + 0.02 * continuity_anchor
                delta += 0.03 * recontact_anchor + 0.02 * memory_anchor
            elif trigger_family in {"shared_activity", "shared_activity_window", "deadline_window"}:
                delta -= 0.02 * own_rhythm_anchor
                delta += 0.05 * memory_anchor + 0.02 * recontact_anchor
            if boundary_anchor >= 0.56 and trigger_family in {"observe", "light_checkin", "shared_activity", "shared_activity_window"}:
                delta -= 0.04 * boundary_anchor

    delta += _behavior_agenda_counterpart_delta(entry, counterpart_assessment)
    delta += _behavior_agenda_history_delta(entry, current_event)
    return round(max(0.05, min(0.95, base_priority + delta)), 3)


def _reprioritize_behavior_agenda(
    agenda: list[BehaviorAgendaEntryPayload],
    current_event: dict[str, Any],
    counterpart_assessment: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
) -> list[BehaviorAgendaEntryPayload]:
    updated: list[BehaviorAgendaEntryPayload] = []
    for entry in _normalize_behavior_agenda(agenda):
        updated.append(
            {
                **entry,
                "priority": _behavior_agenda_context_priority(
                    current_event,
                    entry,
                    counterpart_assessment=counterpart_assessment,
                    world_model_state=world_model_state,
                    semantic_narrative_profile=semantic_narrative_profile,
                ),
            }
        )
    return _normalize_behavior_agenda(updated)


def _behavior_agenda_expiry_from_plan(current_event: dict[str, Any], plan: dict[str, Any]) -> int:
    kind = str(plan.get("kind") or "").strip()
    try:
        due_after = max(0, int(plan.get("scheduled_after_min") or 0))
    except Exception:
        due_after = 0
    if kind == "self_activity_continue":
        return max(90, due_after + 120)
    if kind == "deferred_checkin":
        return max(45, due_after + 60)
    return max(0, due_after + 45 if due_after > 0 else 0)


def _behavior_agenda_entry_from_plan(
    current_event: dict[str, Any],
    plan: dict[str, Any],
    *,
    world_model_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
) -> BehaviorAgendaEntryPayload | None:
    if not isinstance(current_event, dict) or not isinstance(plan, dict):
        return None
    kind = str(plan.get("kind") or "").strip()
    if kind not in QUEUEABLE_BEHAVIOR_PLAN_KINDS:
        return None
    return {
        "agenda_id": uuid.uuid4().hex[:12],
        "kind": kind,
        "target": str(plan.get("target") or "counterpart").strip() or "counterpart",
        "scheduled_after_min": max(0, int(plan.get("scheduled_after_min") or 0)),
        "expires_after_min": _behavior_agenda_expiry_from_plan(current_event, plan),
        "base_priority": _behavior_agenda_priority_from_plan(current_event, plan),
        "priority": _behavior_agenda_priority_from_plan(current_event, plan),
        "trigger_family": str(plan.get("trigger_family") or "none").strip() or "none",
        "allow_interrupt": bool(plan.get("allow_interrupt", True)),
        "primary_motive": str(plan.get("primary_motive") or "").strip(),
        "motive_tension": str(plan.get("motive_tension") or "").strip(),
        "goal_frame": str(plan.get("goal_frame") or "").strip(),
        "note": str(plan.get("note") or "").strip(),
        "source_event_kind": str(current_event.get("kind") or "").strip(),
        "created_at": _now_ts(),
        "status": "pending",
        "hold_count": 0,
        "last_recheck_at_min": 0,
        "carryover_mode": str(plan.get("carryover_mode") or "").strip(),
        "carryover_strength": round(_clamp01(plan.get("carryover_strength"), 0.0), 3),
        "relationship_weather": str(plan.get("relationship_weather") or "").strip(),
        "attention_target": str(plan.get("attention_target") or "").strip(),
        "nonverbal_signal": str(plan.get("nonverbal_signal") or "").strip(),
        "presence_residue": round(_clamp01(plan.get("presence_residue"), 0.0), 3),
        "ambient_resonance": round(_clamp01(plan.get("ambient_resonance"), 0.0), 3),
        "self_activity_momentum": round(_clamp01(plan.get("self_activity_momentum"), 0.0), 3),
        **_agenda_long_horizon_snapshot(
            world_model_state=world_model_state,
            semantic_narrative_profile=semantic_narrative_profile,
        ),
    }


def _behavior_agenda_signature(entry: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(entry.get("kind") or "").strip(),
        str(entry.get("target") or "").strip(),
        str(entry.get("trigger_family") or "").strip(),
    )


def _merge_behavior_agenda(
    prior_agenda: Any,
    current_event: dict[str, Any],
    behavior_plan: dict[str, Any],
    counterpart_assessment: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
) -> list[BehaviorAgendaEntryPayload]:
    agenda = _normalize_behavior_agenda(prior_agenda)
    new_entry = _behavior_agenda_entry_from_plan(
        current_event,
        behavior_plan,
        world_model_state=world_model_state,
        semantic_narrative_profile=semantic_narrative_profile,
    )
    if not new_entry:
        return _reprioritize_behavior_agenda(
            agenda,
            current_event,
            counterpart_assessment=counterpart_assessment,
            world_model_state=world_model_state,
            semantic_narrative_profile=semantic_narrative_profile,
        )

    signature = _behavior_agenda_signature(new_entry)
    for idx, existing in enumerate(agenda):
        if _behavior_agenda_signature(existing) != signature:
            continue
        agenda[idx] = {
            **existing,
            **new_entry,
            **_merge_long_horizon_entry_fields(existing, new_entry),
            "agenda_id": str(existing.get("agenda_id") or new_entry.get("agenda_id") or uuid.uuid4().hex[:12]),
            "created_at": int(existing.get("created_at") or new_entry.get("created_at") or _now_ts()),
            "base_priority": float(existing.get("base_priority") or new_entry.get("base_priority") or new_entry.get("priority") or 0.0),
            "status": "pending",
            "hold_count": max(0, int(existing.get("hold_count") or 0)),
            "last_recheck_at_min": max(0, int(existing.get("last_recheck_at_min") or 0)),
        }
        break
    else:
        agenda.append(new_entry)
    return _reprioritize_behavior_agenda(
        agenda,
        current_event,
        counterpart_assessment=counterpart_assessment,
        world_model_state=world_model_state,
        semantic_narrative_profile=semantic_narrative_profile,
    )


def _behavior_agenda_is_expired(entry: dict[str, Any], idle_minutes: int) -> bool:
    try:
        expires_after_min = max(0, int(entry.get("expires_after_min") or 0))
    except Exception:
        expires_after_min = 0
    return bool(expires_after_min and idle_minutes >= expires_after_min)


def _behavior_agenda_is_due(entry: dict[str, Any], idle_minutes: int) -> bool:
    try:
        scheduled_after_min = max(0, int(entry.get("scheduled_after_min") or 0))
    except Exception:
        scheduled_after_min = 0
    return idle_minutes >= max(1, scheduled_after_min)


def _behavior_agenda_should_hold(
    entry: dict[str, Any],
    current_event: dict[str, Any],
    idle_minutes: int,
    counterpart_assessment: dict[str, Any] | None = None,
    *,
    world_model_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
) -> bool:
    if str(current_event.get("kind") or "").strip() != "time_idle":
        return False
    if str(entry.get("kind") or "").strip() != "deferred_checkin":
        return False
    event_tags = {
        str(item).strip()
        for item in (current_event.get("tags") if isinstance(current_event.get("tags"), list) else [])
        if str(item).strip()
    }
    trigger_family = str(entry.get("trigger_family") or "").strip()
    assessment = counterpart_assessment if isinstance(counterpart_assessment, dict) else {}
    stance = str(assessment.get("stance") or "").strip().lower()
    scene = str(assessment.get("scene") or "").strip().lower()
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    long_horizon = _agenda_long_horizon_bias(
        entry,
        world_model_state=world_model_state,
        semantic_narrative_profile=semantic_narrative_profile,
    )
    continuity_anchor = _clamp01(long_horizon.get("continuity_anchor"), 0.0)
    own_rhythm_anchor = _clamp01(long_horizon.get("own_rhythm_anchor"), 0.0)

    if "user_busy" in event_tags or "cognitive_load" in event_tags:
        return trigger_family in {"observe", "light_checkin", "life_window", "deadline_window"}
    if "respect_space" in event_tags:
        if (
            trigger_family in {"life_window", "deadline_window"}
            and own_rhythm_anchor >= 0.56
            and continuity_anchor >= 0.50
        ):
            return True
        return trigger_family in {"observe", "light_checkin"}
    if (
        stance == "guarded"
        and boundary_pressure >= 0.36
        and trigger_family in {"observe", "light_checkin", "life_window", "deadline_window", "shared_activity", "shared_activity_window"}
    ):
        return True
    if scene in {"boundary_non_compliance", "relationship_degradation"} and trigger_family in {"light_checkin", "shared_activity", "shared_activity_window"}:
        return True
    if "late_night" in event_tags or "quiet_presence" in event_tags:
        return False
    return False


def _behavior_agenda_should_release(
    entry: dict[str, Any],
    current_event: dict[str, Any],
    idle_minutes: int,
    counterpart_assessment: dict[str, Any] | None = None,
    *,
    world_model_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
    next_hold_count: int | None = None,
) -> bool:
    if str(current_event.get("kind") or "").strip() != "time_idle":
        return False
    if str(entry.get("kind") or "").strip() != "deferred_checkin":
        return False
    hold_count = max(0, int(next_hold_count if next_hold_count is not None else entry.get("hold_count") or 0))
    if hold_count <= 0:
        return False

    event_tags = {
        str(item).strip()
        for item in (current_event.get("tags") if isinstance(current_event.get("tags"), list) else [])
        if str(item).strip()
    }
    trigger_family = str(entry.get("trigger_family") or "").strip()
    carryover_mode = str(entry.get("carryover_mode") or "").strip()
    self_activity_momentum = _clamp01(entry.get("self_activity_momentum"), 0.0)
    assessment = counterpart_assessment if isinstance(counterpart_assessment, dict) else {}
    stance = str(assessment.get("stance") or "").strip().lower()
    scene = str(assessment.get("scene") or "").strip().lower()
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    long_horizon = _agenda_long_horizon_bias(
        entry,
        world_model_state=world_model_state,
        semantic_narrative_profile=semantic_narrative_profile,
    )
    continuity_anchor = _clamp01(long_horizon.get("continuity_anchor"), 0.0)
    own_rhythm_anchor = _clamp01(long_horizon.get("own_rhythm_anchor"), 0.0)
    boundary_anchor = _clamp01(long_horizon.get("boundary_anchor"), 0.0)
    respect_scene = bool({"user_busy", "cognitive_load", "respect_space"} & event_tags)

    if (
        hold_count >= 2
        and stance == "guarded"
        and boundary_pressure >= 0.46
        and trigger_family in {"observe", "light_checkin", "life_window", "deadline_window", "shared_activity", "shared_activity_window"}
    ):
        return True
    if (
        hold_count >= 2
        and scene in {"boundary_non_compliance", "relationship_degradation"}
        and trigger_family in {"light_checkin", "shared_activity", "shared_activity_window"}
    ):
        return True
    if (
        hold_count >= 2
        and respect_scene
        and trigger_family == "life_window"
        and own_rhythm_anchor >= 0.56
        and continuity_anchor >= 0.50
    ):
        return True
    if (
        hold_count >= 3
        and respect_scene
        and trigger_family in {"observe", "light_checkin"}
        and own_rhythm_anchor >= 0.54
    ):
        return True
    if (
        hold_count >= 2
        and boundary_anchor >= 0.60
        and scene in {"boundary_non_compliance", "relationship_degradation"}
        and trigger_family in {"observe", "light_checkin", "shared_activity", "shared_activity_window"}
    ):
        return True
    if (
        hold_count >= 3
        and ("user_busy" in event_tags or "cognitive_load" in event_tags or "respect_space" in event_tags)
        and trigger_family in {"observe", "light_checkin", "life_window", "deadline_window"}
        and (carryover_mode in {"own_rhythm", "quiet_recontact", "brief_presence"} or self_activity_momentum >= 0.46)
    ):
        return True
    if hold_count >= 4 and trigger_family in {"observe", "light_checkin"}:
        return True
    return False


def _behavior_agenda_release_strategy(
    entry: dict[str, Any],
    current_event: dict[str, Any],
    idle_minutes: int,
    counterpart_assessment: dict[str, Any] | None = None,
    *,
    world_model_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
    next_hold_count: int | None = None,
) -> str:
    if not _behavior_agenda_should_release(
        entry,
        current_event,
        idle_minutes,
        counterpart_assessment=counterpart_assessment,
        world_model_state=world_model_state,
        semantic_narrative_profile=semantic_narrative_profile,
        next_hold_count=next_hold_count,
    ):
        return ""

    hold_count = max(0, int(next_hold_count if next_hold_count is not None else entry.get("hold_count") or 0))
    event_tags = {
        str(item).strip()
        for item in (current_event.get("tags") if isinstance(current_event.get("tags"), list) else [])
        if str(item).strip()
    }
    trigger_family = str(entry.get("trigger_family") or "").strip().lower()
    carryover_mode = str(entry.get("carryover_mode") or "").strip().lower()
    carryover_strength = _clamp01(entry.get("carryover_strength"), 0.0)
    self_activity_momentum = _clamp01(entry.get("self_activity_momentum"), 0.0)
    assessment = counterpart_assessment if isinstance(counterpart_assessment, dict) else {}
    scene = str(assessment.get("scene") or "").strip().lower()
    respect_scene = bool({"user_busy", "cognitive_load", "respect_space"} & event_tags)
    long_horizon = _agenda_long_horizon_bias(
        entry,
        world_model_state=world_model_state,
        semantic_narrative_profile=semantic_narrative_profile,
    )
    continuity_anchor = _clamp01(long_horizon.get("continuity_anchor"), 0.0)
    own_rhythm_anchor = _clamp01(long_horizon.get("own_rhythm_anchor"), 0.0)
    memory_anchor = _clamp01(long_horizon.get("memory_anchor"), 0.0)

    if (
        trigger_family == "life_window"
        and hold_count >= 2
        and respect_scene
        and scene not in {"boundary_non_compliance", "relationship_degradation"}
        and (
            carryover_mode in {"own_rhythm", "life_window", "small_opening"}
            or self_activity_momentum >= 0.54
            or carryover_strength >= 0.44
            or own_rhythm_anchor >= 0.56
        )
        and (
            max(continuity_anchor, own_rhythm_anchor) >= 0.50
            or self_activity_momentum >= 0.54
            or carryover_mode in {"own_rhythm", "life_window"}
        )
    ):
        return "return_to_self_activity"
    if (
        trigger_family in {"observe", "light_checkin"}
        and hold_count >= 3
        and respect_scene
        and own_rhythm_anchor >= 0.54
        and continuity_anchor >= 0.48
    ):
        return "drop"
    if (
        trigger_family in {"shared_activity", "shared_activity_window"}
        and hold_count >= 2
        and scene in {"boundary_non_compliance", "relationship_degradation"}
        and memory_anchor <= 0.44
    ):
        return "drop"
    return "drop"


def _released_life_window_to_self_activity_event(
    event: EventPayload,
    entry: dict[str, Any],
) -> EventPayload:
    base_tags = [
        str(item).strip()
        for item in (event.get("tags") if isinstance(event.get("tags"), list) else [])
        if str(item).strip()
    ]
    carryover_strength = _clamp01(entry.get("carryover_strength"), 0.0)
    presence_residue = _clamp01(entry.get("presence_residue"), 0.0)
    ambient_resonance = _clamp01(entry.get("ambient_resonance"), 0.0)
    own_rhythm_anchor = _clamp01(entry.get("own_rhythm_anchor"), 0.0)
    continuity_anchor = _clamp01(entry.get("continuity_anchor"), 0.0)
    self_activity_momentum = max(
        0.58,
        _clamp01(entry.get("self_activity_momentum"), 0.0),
        0.84 * own_rhythm_anchor,
        0.68 * continuity_anchor,
    )
    merged_tags = list(
        dict.fromkeys(
            [
                *base_tags,
                "self_activity",
                "own_task",
                "released_from_life_window",
                "deep_focus" if self_activity_momentum >= 0.64 else "",
                "quiet_presence" if presence_residue >= 0.28 else "",
                "ambient_echo" if ambient_resonance >= 0.30 else "",
            ]
        )
    )
    promoted_text = "那点生活上的惦记没有继续往前推，你把它收回心里，又回到了自己的节奏里。"
    if self_activity_momentum >= 0.64:
        promoted_text = "那点生活上的小惦记没有必要硬往前推，你顺手把它收回心里，继续忙自己的事。"
    elif presence_residue >= 0.30:
        promoted_text = "那点生活上的惦记还在，但你没有追着说下去，只是把它收回心里，继续自己的节奏。"
    promoted_frame = (
        "这点生活上的惦记先留在心里，不再继续挂着；她把注意力慢慢收回自己的节奏里。"
    )
    if ambient_resonance >= 0.30:
        promoted_frame += " 环境里的细小动静还留在她的感知里。"
    return {
        **event,
        "kind": "self_activity_state",
        "source": "self",
        "text": promoted_text,
        "effective_text": promoted_text,
        "semantic_goal": "把没说出口的生活惦记收回心里，继续自己的节奏。",
        "event_frame": promoted_frame,
        "tags": merged_tags,
        "derived_from_plan_kind": "released_deferred_checkin",
        "trigger_family": str(entry.get("trigger_family") or "").strip() or "life_window",
        "scheduled_after_min": max(0, int(entry.get("scheduled_after_min") or 0)),
        "carryover_mode": "own_rhythm",
        "carryover_strength": round(max(carryover_strength, self_activity_momentum), 3),
        "relationship_weather": str(entry.get("relationship_weather") or "").strip().lower(),
        "presence_residue": round(presence_residue, 3),
        "ambient_resonance": round(ambient_resonance, 3),
        "self_activity_momentum": round(self_activity_momentum, 3),
        "attention_target_hint": "own_task",
        "nonverbal_signal_hint": "inward_focus",
    }


def _behavior_agenda_next_recheck_min(
    entry: dict[str, Any],
    current_event: dict[str, Any],
    idle_minutes: int,
    counterpart_assessment: dict[str, Any] | None = None,
    *,
    world_model_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
) -> int:
    trigger_family = str(entry.get("trigger_family") or "").strip()
    carryover_mode = str(entry.get("carryover_mode") or "").strip().lower()
    carryover_strength = _clamp01(entry.get("carryover_strength"), 0.0)
    presence_residue = _clamp01(entry.get("presence_residue"), 0.0)
    ambient_resonance = _clamp01(entry.get("ambient_resonance"), 0.0)
    self_activity_momentum = _clamp01(entry.get("self_activity_momentum"), 0.0)
    recontact_echo = max(
        presence_residue,
        0.82 * ambient_resonance,
        carryover_strength if carryover_mode in {"quiet_recontact", "brief_presence", "small_opening"} else 0.0,
    )
    own_rhythm_load = max(
        self_activity_momentum,
        carryover_strength if carryover_mode == "own_rhythm" else 0.45 * carryover_strength if carryover_mode == "small_opening" else 0.0,
    )
    event_tags = {
        str(item).strip()
        for item in (current_event.get("tags") if isinstance(current_event.get("tags"), list) else [])
        if str(item).strip()
    }
    assessment = counterpart_assessment if isinstance(counterpart_assessment, dict) else {}
    stance = str(assessment.get("stance") or "").strip().lower()
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    hold_count = max(0, int(entry.get("hold_count") or 0))
    long_horizon = _agenda_long_horizon_bias(
        entry,
        world_model_state=world_model_state,
        semantic_narrative_profile=semantic_narrative_profile,
    )
    continuity_anchor = _clamp01(long_horizon.get("continuity_anchor"), 0.0)
    own_rhythm_anchor = _clamp01(long_horizon.get("own_rhythm_anchor"), 0.0)
    recontact_anchor = _clamp01(long_horizon.get("recontact_anchor"), 0.0)
    boundary_anchor = _clamp01(long_horizon.get("boundary_anchor"), 0.0)
    memory_anchor = _clamp01(long_horizon.get("memory_anchor"), 0.0)
    recontact_echo = max(
        recontact_echo,
        0.74 * recontact_anchor,
        0.24 * memory_anchor if trigger_family in {"life_window", "shared_activity", "shared_activity_window", "deadline_window"} else 0.0,
    )
    own_rhythm_load = max(
        own_rhythm_load,
        0.86 * own_rhythm_anchor,
        0.54 * continuity_anchor,
    )

    gap = 8
    if "user_busy" in event_tags or "cognitive_load" in event_tags:
        gap = 16 if trigger_family in {"life_window", "deadline_window", "shared_activity", "shared_activity_window"} else 10
    elif "respect_space" in event_tags:
        gap = 14
    elif stance == "guarded" and boundary_pressure >= 0.36:
        gap = 18 if trigger_family in {"shared_activity", "shared_activity_window"} else 12
    elif "late_night" in event_tags or "quiet_presence" in event_tags:
        gap = 10
    if recontact_echo >= 0.24:
        gap -= 1 + int(round(4 * max(0.0, recontact_echo - 0.24)))
        if trigger_family in {"shared_activity", "shared_activity_window", "life_window"}:
            gap -= 1
    if own_rhythm_load >= 0.34:
        gap += 1 + int(round(5 * max(0.0, own_rhythm_load - 0.34)))
        if trigger_family in {"light_checkin", "observe"} and own_rhythm_load >= 0.56:
            gap += 1
    if continuity_anchor >= 0.54 and trigger_family in {"observe", "light_checkin", "life_window"}:
        gap += 1 + int(round(4 * max(0.0, continuity_anchor - 0.54)))
    if memory_anchor >= 0.46 and trigger_family in {"shared_activity", "shared_activity_window", "deadline_window"}:
        gap -= 1 + int(round(3 * max(0.0, memory_anchor - 0.46)))
    if boundary_anchor >= 0.56 and trigger_family in {"light_checkin", "shared_activity", "shared_activity_window"}:
        gap += 1 + int(round(3 * max(0.0, boundary_anchor - 0.56)))
    if hold_count > 0:
        gap += min(24, 4 * hold_count)
        if trigger_family in {"shared_activity", "shared_activity_window"} and hold_count >= 2:
            gap += 8
    gap = max(6, gap)
    return max(idle_minutes + gap, int(entry.get("scheduled_after_min") or 0) + 1)


def _reschedule_held_behavior_agenda(
    entry: dict[str, Any],
    current_event: dict[str, Any],
    idle_minutes: int,
    counterpart_assessment: dict[str, Any] | None = None,
    *,
    world_model_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
) -> BehaviorAgendaEntryPayload:
    hold_count = max(0, int(entry.get("hold_count") or 0)) + 1
    next_due = _behavior_agenda_next_recheck_min(
        {
            **entry,
            "hold_count": hold_count,
        },
        current_event,
        idle_minutes,
        counterpart_assessment=counterpart_assessment,
        world_model_state=world_model_state,
        semantic_narrative_profile=semantic_narrative_profile,
    )
    base_priority = float(entry.get("base_priority") or entry.get("priority") or 0.0)
    priority = max(0.05, min(0.95, base_priority - min(0.12, 0.02 * hold_count)))
    note = str(entry.get("note") or "").strip()
    if not note:
        note = "这次先不推进，往后顺延一点。"
    return {
        **entry,
        "scheduled_after_min": next_due,
        "priority": round(priority, 3),
        "hold_count": hold_count,
        "last_recheck_at_min": max(0, int(idle_minutes)),
        "status": "pending",
        "note": note,
    }


def _agenda_entry_signal_summary(entry: dict[str, Any]) -> tuple[str, float, float, float, float, float, float]:
    carryover_mode = str(entry.get("carryover_mode") or "").strip().lower()
    carryover_strength = _clamp01(entry.get("carryover_strength"), 0.0)
    presence_residue = _clamp01(entry.get("presence_residue"), 0.0)
    ambient_resonance = _clamp01(entry.get("ambient_resonance"), 0.0)
    self_activity_momentum = _clamp01(entry.get("self_activity_momentum"), 0.0)
    recontact_echo = max(
        presence_residue,
        0.82 * ambient_resonance,
        carryover_strength if carryover_mode in {"quiet_recontact", "brief_presence", "small_opening"} else 0.0,
    )
    own_rhythm_bias = max(
        self_activity_momentum,
        carryover_strength if carryover_mode == "own_rhythm" else 0.45 * carryover_strength if carryover_mode == "small_opening" else 0.0,
    )
    return (
        carryover_mode,
        carryover_strength,
        presence_residue,
        ambient_resonance,
        self_activity_momentum,
        recontact_echo,
        own_rhythm_bias,
    )


def _select_primary_agenda_entry(entries: list[BehaviorAgendaEntryPayload]) -> BehaviorAgendaEntryPayload | None:
    if not entries:
        return None
    ranked = sorted(
        entries,
        key=lambda item: (
            -float(item.get("priority") or 0.0),
            int(item.get("created_at") or 0),
            str(item.get("agenda_id") or ""),
        ),
    )
    return ranked[0] if ranked else None


def _agenda_lifecycle_residue(
    *,
    kind: str,
    event: EventPayload,
    entry: dict[str, Any],
    counterpart_assessment: dict[str, Any] | None = None,
    hold_count: int | None = None,
    promoted_event: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
) -> AgendaLifecycleResiduePayload:
    assessment = counterpart_assessment if isinstance(counterpart_assessment, dict) else {}
    event_tags = [
        str(item).strip().lower()
        for item in (event.get("tags") if isinstance(event.get("tags"), list) else [])
        if str(item).strip()
    ]
    (
        carryover_mode,
        carryover_strength,
        presence_residue,
        ambient_resonance,
        self_activity_momentum,
        recontact_echo,
        own_rhythm_bias,
    ) = _agenda_entry_signal_summary(entry)
    stance = str(assessment.get("stance") or "").strip().lower()
    scene = str(assessment.get("scene") or "").strip().lower()
    effective_hold_count = max(0, int(hold_count if hold_count is not None else entry.get("hold_count") or 0))
    long_horizon = _agenda_long_horizon_bias(
        entry,
        world_model_state=world_model_state,
        semantic_narrative_profile=semantic_narrative_profile,
    )
    continuity_anchor = _clamp01(long_horizon.get("continuity_anchor"), 0.0)
    own_rhythm_anchor = _clamp01(long_horizon.get("own_rhythm_anchor"), 0.0)
    recontact_anchor = _clamp01(long_horizon.get("recontact_anchor"), 0.0)
    residue_mode = carryover_mode
    residue_strength = carryover_strength
    recontact_echo = max(recontact_echo, 0.72 * recontact_anchor)
    own_rhythm_bias = max(own_rhythm_bias, own_rhythm_anchor, 0.72 * continuity_anchor)
    self_activity_momentum = max(self_activity_momentum, 0.84 * own_rhythm_anchor)

    if kind in {"released_to_self_activity", "dropped", "expired"}:
        residue_mode = "own_rhythm"
        residue_strength = max(own_rhythm_bias, 0.34 + 0.04 * min(4, effective_hold_count))
    elif kind == "held":
        if own_rhythm_bias >= max(0.34, recontact_echo + 0.04):
            residue_mode = "own_rhythm"
            residue_strength = max(own_rhythm_bias, 0.32 + 0.03 * min(4, effective_hold_count))
        else:
            residue_mode = "quiet_recontact"
            residue_strength = max(0.16, min(0.44, recontact_echo * 0.84))
    elif kind == "promoted" and isinstance(promoted_event, dict):
        residue_mode = str(promoted_event.get("carryover_mode") or residue_mode).strip().lower() or residue_mode
        residue_strength = max(residue_strength, _clamp01(promoted_event.get("carryover_strength"), 0.0))
        presence_residue = max(presence_residue, _clamp01(promoted_event.get("presence_residue"), 0.0))
        ambient_resonance = max(ambient_resonance, _clamp01(promoted_event.get("ambient_resonance"), 0.0))
        self_activity_momentum = max(self_activity_momentum, _clamp01(promoted_event.get("self_activity_momentum"), 0.0))
        _, _, _, _, _, recontact_echo, own_rhythm_bias = _agenda_entry_signal_summary(
            {
                **entry,
                "carryover_mode": residue_mode,
                "carryover_strength": residue_strength,
                "presence_residue": presence_residue,
                "ambient_resonance": ambient_resonance,
                "self_activity_momentum": self_activity_momentum,
            }
        )

    counterpart_scene_bias = ""
    counterpart_boundary_delta = 0.0
    if {"user_busy", "cognitive_load", "respect_space"} & set(event_tags):
        if scene not in {"relationship_degradation", "boundary_non_compliance"}:
            counterpart_scene_bias = "busy_not_disrespectful"
            counterpart_boundary_delta = -0.04 if stance != "guarded" else -0.01
    elif kind in {"held", "dropped", "expired"} and stance in {"watchful", "guarded"}:
        counterpart_boundary_delta = 0.02 if stance == "watchful" else 0.01

    if kind == "released_to_self_activity":
        note = "前面挂着的窗口没有继续往前推，注意力被自然收回到了自己的节奏里。"
    elif kind == "held":
        note = "这次先把窗口按住，没有顺势往前推进。"
    elif kind == "dropped":
        note = "前面那点接近窗口这次就让它自然落下，不再继续挂着。"
    elif kind == "expired":
        note = "前面的窗口已经自然过期，不再继续占着注意力。"
    else:
        note = "前面的窗口已经转成了这轮真正生效的行为余波。"

    return {
        "kind": kind,
        "source_event_kind": str(event.get("kind") or "time_idle").strip().lower() or "time_idle",
        "trigger_family": str(entry.get("trigger_family") or "").strip().lower(),
        "carryover_mode": residue_mode,
        "carryover_strength": round(_clamp01(residue_strength), 3),
        "relationship_weather": str(entry.get("relationship_weather") or "").strip().lower(),
        "hold_count": effective_hold_count,
        "idle_minutes": max(0, int(event.get("idle_minutes") or 0)),
        "attention_target": str(entry.get("attention_target") or "").strip(),
        "nonverbal_signal": str(entry.get("nonverbal_signal") or "").strip(),
        "note": note,
        "source_tags": list(
            dict.fromkeys(
                item
                for item in [
                    *event_tags,
                    "agenda_lifecycle",
                    kind,
                    str(entry.get("trigger_family") or "").strip().lower(),
                ]
                if item
            )
        ),
        "presence_residue": round(presence_residue, 3),
        "ambient_resonance": round(ambient_resonance, 3),
        "self_activity_momentum": round(self_activity_momentum, 3),
        "own_rhythm_bias": round(own_rhythm_bias, 3),
        "recontact_cooldown": round(_clamp01(max(own_rhythm_bias, 0.82 * effective_hold_count / 4.0 - 0.18 * recontact_echo)), 3),
        "counterpart_scene_bias": counterpart_scene_bias,
        "counterpart_boundary_delta": round(counterpart_boundary_delta, 3),
        "created_at": _now_ts(),
    }


def _promote_due_behavior_agenda_event_with_residue(
    event: EventPayload,
    prior_behavior_agenda: Any,
    counterpart_assessment: dict[str, Any] | None = None,
    *,
    world_model_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
) -> tuple[EventPayload, list[BehaviorAgendaEntryPayload], AgendaLifecycleResiduePayload]:
    agenda = _normalize_behavior_agenda(prior_behavior_agenda)
    if not isinstance(event, dict) or not event or str(event.get("kind") or "").strip() != "time_idle":
        return event, agenda, {}
    try:
        idle_minutes = max(0, int(event.get("idle_minutes") or 0))
    except Exception:
        idle_minutes = 0

    expired_entries = [entry for entry in agenda if _behavior_agenda_is_expired(entry, idle_minutes)]
    active_agenda = [entry for entry in agenda if not _behavior_agenda_is_expired(entry, idle_minutes)]
    active_agenda = _reprioritize_behavior_agenda(
        active_agenda,
        event,
        counterpart_assessment=counterpart_assessment,
        world_model_state=world_model_state,
        semantic_narrative_profile=semantic_narrative_profile,
    )
    due_entries = [entry for entry in active_agenda if _behavior_agenda_is_due(entry, idle_minutes)]
    if not due_entries:
        residue: AgendaLifecycleResiduePayload = {}
        primary_expired = _select_primary_agenda_entry(expired_entries)
        if isinstance(primary_expired, dict):
            residue = _agenda_lifecycle_residue(
                kind="expired",
                event=event,
                entry=primary_expired,
                counterpart_assessment=counterpart_assessment,
                hold_count=max(0, int(primary_expired.get("hold_count") or 0)),
                world_model_state=world_model_state,
                semantic_narrative_profile=semantic_narrative_profile,
            )
        return event, _normalize_behavior_agenda(active_agenda), residue

    held_ids: set[str] = set()
    released_strategies: dict[str, str] = {}
    ready_entries: list[BehaviorAgendaEntryPayload] = []
    held_counts: dict[str, int] = {}
    for entry in due_entries:
        next_hold_count = max(0, int(entry.get("hold_count") or 0)) + 1
        if _behavior_agenda_should_hold(
            entry,
            event,
            idle_minutes,
            counterpart_assessment=counterpart_assessment,
            world_model_state=world_model_state,
            semantic_narrative_profile=semantic_narrative_profile,
        ):
            release_strategy = _behavior_agenda_release_strategy(
                entry,
                event,
                idle_minutes,
                counterpart_assessment=counterpart_assessment,
                world_model_state=world_model_state,
                semantic_narrative_profile=semantic_narrative_profile,
                next_hold_count=next_hold_count,
            )
            if release_strategy:
                released_strategies[str(entry.get("agenda_id") or "")] = release_strategy
                held_counts[str(entry.get("agenda_id") or "")] = next_hold_count
                continue
            held_ids.add(str(entry.get("agenda_id") or ""))
            held_counts[str(entry.get("agenda_id") or "")] = next_hold_count
            continue
        ready_entries.append(entry)
    if not ready_entries:
        promoted_release = event
        residue: AgendaLifecycleResiduePayload = {}
        if released_strategies:
            released_entries = [
                entry for entry in active_agenda if str(entry.get("agenda_id") or "") in released_strategies
            ]
            released_entries.sort(
                key=lambda item: (
                    -float(item.get("priority") or 0.0),
                    int(item.get("created_at") or 0),
                    str(item.get("agenda_id") or ""),
                )
            )
            for entry in released_entries:
                release_strategy = released_strategies.get(str(entry.get("agenda_id") or ""))
                if release_strategy == "return_to_self_activity":
                    promoted_release = _released_life_window_to_self_activity_event(event, entry)
                    residue = _agenda_lifecycle_residue(
                        kind="released_to_self_activity",
                        event=event,
                        entry=entry,
                        counterpart_assessment=counterpart_assessment,
                        hold_count=held_counts.get(str(entry.get("agenda_id") or ""), max(0, int(entry.get("hold_count") or 0))),
                        promoted_event=promoted_release,
                        world_model_state=world_model_state,
                        semantic_narrative_profile=semantic_narrative_profile,
                    )
                    break
            if not residue and released_entries:
                primary_released = released_entries[0]
                residue = _agenda_lifecycle_residue(
                    kind="dropped",
                    event=event,
                    entry=primary_released,
                    counterpart_assessment=counterpart_assessment,
                    hold_count=held_counts.get(str(primary_released.get("agenda_id") or ""), max(0, int(primary_released.get("hold_count") or 0))),
                    world_model_state=world_model_state,
                    semantic_narrative_profile=semantic_narrative_profile,
                )
        elif held_ids:
            held_entries = [
                entry for entry in active_agenda if str(entry.get("agenda_id") or "") in held_ids
            ]
            primary_held = _select_primary_agenda_entry(held_entries)
            if isinstance(primary_held, dict):
                residue = _agenda_lifecycle_residue(
                    kind="held",
                    event=event,
                    entry=primary_held,
                    counterpart_assessment=counterpart_assessment,
                    hold_count=held_counts.get(str(primary_held.get("agenda_id") or ""), max(0, int(primary_held.get("hold_count") or 0))),
                    world_model_state=world_model_state,
                    semantic_narrative_profile=semantic_narrative_profile,
                )
        rescheduled: list[BehaviorAgendaEntryPayload] = []
        for entry in active_agenda:
            if str(entry.get("agenda_id") or "") in released_strategies:
                continue
            if str(entry.get("agenda_id") or "") in held_ids:
                rescheduled.append(
                    _reschedule_held_behavior_agenda(
                        entry,
                        event,
                        idle_minutes,
                        counterpart_assessment=counterpart_assessment,
                        world_model_state=world_model_state,
                        semantic_narrative_profile=semantic_narrative_profile,
                    )
                )
            else:
                rescheduled.append(entry)
        return promoted_release, _normalize_behavior_agenda(rescheduled), residue

    ready_entries.sort(key=lambda item: (-float(item.get("priority") or 0.0), int(item.get("created_at") or 0), str(item.get("agenda_id") or "")))
    selected = ready_entries[0]
    promoted = _promote_due_behavior_plan_event(event, selected)
    if promoted == event:
        return event, _normalize_behavior_agenda(active_agenda), {}
    remaining = [entry for entry in active_agenda if str(entry.get("agenda_id") or "") != str(selected.get("agenda_id") or "")]
    return (
        promoted,
        _normalize_behavior_agenda(remaining),
        _agenda_lifecycle_residue(
            kind="promoted",
            event=event,
            entry=selected,
            counterpart_assessment=counterpart_assessment,
            hold_count=max(0, int(selected.get("hold_count") or 0)),
            promoted_event=promoted,
            world_model_state=world_model_state,
            semantic_narrative_profile=semantic_narrative_profile,
        ),
    )


def _promote_due_behavior_agenda_event(
    event: EventPayload,
    prior_behavior_agenda: Any,
    counterpart_assessment: dict[str, Any] | None = None,
    *,
    world_model_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
) -> tuple[EventPayload, list[BehaviorAgendaEntryPayload]]:
    promoted, agenda, _ = _promote_due_behavior_agenda_event_with_residue(
        event,
        prior_behavior_agenda,
        counterpart_assessment=counterpart_assessment,
        world_model_state=world_model_state,
        semantic_narrative_profile=semantic_narrative_profile,
    )
    return promoted, agenda

