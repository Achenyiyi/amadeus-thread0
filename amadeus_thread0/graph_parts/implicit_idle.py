from __future__ import annotations

from datetime import datetime
from typing import Any

from .common import _now_ts
from .state import ThreadState

_OWN_RHYTHM_TAGS = {"from_own_rhythm", "own_task", "deep_focus", "break_window", "small_opening", "reapproach"}
_QUIET_PRESENCE_MODES = {"quiet_recontact", "brief_presence"}
_OWN_RHYTHM_MODES = {"own_rhythm", "small_opening"}
_AMBIENT_ECHO_MODES = {"ambient_echo"}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _normalize_tag_list(*chunks: Any) -> list[str]:
    ordered: list[str] = []
    for chunk in chunks:
        items = chunk if isinstance(chunk, (list, tuple, set)) else [chunk]
        for item in items:
            text = str(item or "").strip()
            if text and text not in ordered:
                ordered.append(text)
    return ordered


def build_implicit_idle_event_override(
    state: ThreadState | dict[str, Any] | None,
    *,
    idle_minutes: int,
    note: str = "",
    created_at: int | None = None,
    extra_tags: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, Any]:
    seeded: ThreadState = dict(state or {})
    try:
        idle_window = max(1, min(24 * 60, int(idle_minutes)))
    except Exception:
        idle_window = 1
    now_ts = int(created_at or _now_ts())
    event_text = str(note or "").strip() or f"已经安静地过去了 {idle_window} 分钟，没有新的用户消息。"

    prior_event = seeded.get("current_event") if isinstance(seeded.get("current_event"), dict) else {}
    prior_tags = {
        str(item).strip()
        for item in (prior_event.get("tags") if isinstance(prior_event.get("tags"), list) else [])
        if str(item).strip()
    }
    prior_behavior_action = seeded.get("behavior_action") if isinstance(seeded.get("behavior_action"), dict) else {}
    interaction_carryover = seeded.get("interaction_carryover") if isinstance(seeded.get("interaction_carryover"), dict) else {}
    world = seeded.get("world_model_state") if isinstance(seeded.get("world_model_state"), dict) else {}
    assessment = seeded.get("counterpart_assessment") if isinstance(seeded.get("counterpart_assessment"), dict) else {}
    relationship_weather = (
        str(interaction_carryover.get("relationship_weather") or "").strip().lower()
        or str(prior_behavior_action.get("relationship_weather") or "").strip().lower()
        or str(prior_event.get("relationship_weather") or "").strip().lower()
    )
    carryover_mode = str(interaction_carryover.get("carryover_mode") or "").strip().lower()
    carryover_strength = _safe_float(interaction_carryover.get("strength"), 0.0) if interaction_carryover else 0.0
    presence_residue = _safe_float(world.get("presence_residue"), 0.0) if world else 0.0
    ambient_resonance = _safe_float(world.get("ambient_resonance"), 0.0) if world else 0.0
    self_activity_momentum = _safe_float(world.get("self_activity_momentum"), 0.0) if world else 0.0
    action_target = str(prior_behavior_action.get("action_target") or "").strip().lower()
    try:
        timing_window_min = int(prior_behavior_action.get("timing_window_min") or 0) if prior_behavior_action else 0
    except Exception:
        timing_window_min = 0
    stance = str(assessment.get("stance") or "").strip().lower()
    scene = str(assessment.get("scene") or "").strip().lower()

    tags = _normalize_tag_list("time_idle", "ambient", "behavior_layer", extra_tags or [])
    if prior_tags & {"respect_space", "user_busy", "cognitive_load"}:
        tags = _normalize_tag_list(tags, sorted(prior_tags & {"respect_space", "user_busy", "cognitive_load"}))
    if stance == "guarded" and "respect_space" not in tags and prior_tags & {"quiet_presence"}:
        tags = _normalize_tag_list(tags, "respect_space")
    if (
        carryover_mode in _QUIET_PRESENCE_MODES
        or bool(prior_tags & {"quiet_presence", "brief_presence"})
        or presence_residue >= 0.28
    ):
        tags = _normalize_tag_list(tags, "quiet_presence")
    if (
        carryover_mode in _AMBIENT_ECHO_MODES
        or bool(prior_tags & {"ambient_echo"})
        or ambient_resonance >= 0.30
    ):
        tags = _normalize_tag_list(tags, "ambient_echo")
    if (
        carryover_mode in _OWN_RHYTHM_MODES
        or action_target == "hold_own_rhythm"
        or bool(prior_tags & _OWN_RHYTHM_TAGS)
        or self_activity_momentum >= 0.56
    ):
        tags = _normalize_tag_list(tags, "from_own_rhythm")
    if self_activity_momentum >= 0.60 or bool(prior_tags & {"own_task", "deep_focus"}):
        tags = _normalize_tag_list(tags, "own_task")
    if self_activity_momentum >= 0.66 or bool(prior_tags & {"deep_focus"}):
        tags = _normalize_tag_list(tags, "deep_focus")

    try:
        hour = int(datetime.fromtimestamp(now_ts).hour)
    except Exception:
        hour = -1
    if hour >= 23 or 0 <= hour <= 5:
        tags = _normalize_tag_list(tags, "late_night")

    stale_window = False
    if action_target == "wait_and_recheck":
        stale_after = max(45, timing_window_min * 3 if timing_window_min > 0 else 90)
        if idle_window >= stale_after:
            stale_window = True
            tags = _normalize_tag_list(tags, "stale_window")

    frame_parts = [f"和对方之间安静地过去了 {idle_window} 分钟。"]
    if "respect_space" in tags:
        frame_parts.append("这段安静更像是在给对方留空间。")
    elif "user_busy" in tags or "cognitive_load" in tags:
        frame_parts.append("她默认对方大概还在忙，先不急着往前推。")
    if "from_own_rhythm" in tags:
        frame_parts.append("她这段时间仍在自己的节奏里。")
    if "quiet_presence" in tags:
        frame_parts.append("前面那点没说出口的在场感还没有完全退掉。")
    if "ambient_echo" in tags:
        frame_parts.append("环境里残留的细小动静还挂在她的感知边缘。")
    if stale_window:
        frame_parts.append("之前那点低压接近的窗口已经自然过期。")
    if relationship_weather:
        frame_parts.append(f"当前关系天气更接近 {relationship_weather}。")
    elif scene in {"boundary_non_compliance", "relationship_degradation"}:
        frame_parts.append("这轮关系气压偏低。")
    frame_parts.append("现在轮到她决定是否重新抬头。")

    return {
        "kind": "time_idle",
        "source": "time",
        "text": event_text,
        "effective_text": event_text,
        "semantic_goal": "time passed without new user input",
        "response_style_hint": "companion",
        "event_frame": " ".join(frame_parts),
        "tags": tags,
        "idle_minutes": idle_window,
        "created_at": now_ts,
        "relationship_weather": relationship_weather,
        "carryover_mode": carryover_mode,
        "carryover_strength": round(max(0.0, min(1.0, carryover_strength)), 3),
        "presence_residue": round(max(0.0, min(1.0, presence_residue)), 3),
        "ambient_resonance": round(max(0.0, min(1.0, ambient_resonance)), 3),
        "self_activity_momentum": round(max(0.0, min(1.0, self_activity_momentum)), 3),
    }


def build_implicit_idle_state_update(
    state: ThreadState | dict[str, Any] | None,
    *,
    idle_minutes: int,
    note: str = "",
    created_at: int | None = None,
) -> dict[str, Any]:
    from .nodes import _node_prepare_turn

    seeded: ThreadState = dict(state or {})
    seeded["event_override"] = build_implicit_idle_event_override(
        seeded,
        idle_minutes=idle_minutes,
        note=note,
        created_at=created_at,
        extra_tags=["implicit_idle"],
    )
    return _node_prepare_turn(seeded)
