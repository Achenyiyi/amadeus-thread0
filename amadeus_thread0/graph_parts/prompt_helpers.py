from __future__ import annotations

import re
from typing import Any

from .behavior_agenda import _normalize_behavior_agenda
from .common import _clamp01
from .relational_runtime import _focus_text


_WORKING_ITEM_PREFIX_RE = re.compile(r"^(?:[A-Z]{1,3}\d*(?:\([^)]*\))?)\s*:\s*")
_RELATIONSHIP_STAGE_TEXT = {
    "friend": "朋友阶段",
    "warming": "慢慢热起来的阶段",
    "close": "比较亲近的阶段",
    "close_friend": "比较亲近的阶段",
    "strained": "有点发紧的阶段",
    "repairing": "还在修复中的阶段",
    "ambiguous": "还没完全定下来的阶段",
    "trusted_partner": "高信任搭档的阶段",
}


def _source_tag_floor(source_tags: set[str], *names: str, floor: float = 0.52) -> float:
    return floor if any(str(name).strip().lower() in source_tags for name in names) else 0.0


def _normalize_working_item_text(item: Any) -> str:
    text = str(item or "").strip()
    if not text:
        return ""
    lower = text.lower()
    if lower.startswith("relationship_stage="):
        stage = text.split("=", 1)[1].strip().lower()
        if not stage:
            return ""
        stage_text = _RELATIONSHIP_STAGE_TEXT.get(stage, stage.replace("_", " "))
        return f"当前关系还大致停在{stage_text}"
    text = _WORKING_ITEM_PREFIX_RE.sub("", text).strip()
    return text


def _compact_working_item_fallback_texts(working_items: Any, *, limit: int = 2) -> list[str]:
    texts: list[str] = []
    seen: set[str] = set()
    if not isinstance(working_items, list):
        return texts
    for item in working_items:
        text = _normalize_working_item_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        texts.append(text[:160])
        if len(texts) >= int(limit):
            break
    return texts


def _compact_recent_event_lines(recent_events: Any, *, limit: int = 3) -> list[str]:
    lines: list[str] = []
    if not isinstance(recent_events, list):
        return lines
    for item in recent_events[-int(limit):]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("effective_text") or item.get("text") or "").strip()
        frame = str(item.get("event_frame") or "").strip()
        tags = item.get("tags") if isinstance(item.get("tags"), list) else []
        tag_text = ", ".join(str(tag).strip() for tag in tags[:4] if str(tag).strip())
        if not text:
            continue
        if frame and tag_text:
            lines.append(f"- {text[:120]} | frame={frame[:72]} | tags={tag_text}")
        elif frame:
            lines.append(f"- {text[:120]} | frame={frame[:72]}")
        elif tag_text:
            lines.append(f"- {text[:120]} | tags={tag_text}")
        else:
            lines.append(f"- {text[:120]}")
    return lines

def _recent_background_scene_hint(
    recent_events: Any,
    *,
    current_event: dict[str, Any] | None = None,
) -> str:
    event = dict(current_event or {})
    if str(event.get("kind") or "user_utterance").strip().lower() != "user_utterance":
        return ""
    if not isinstance(recent_events, list):
        return ""

    for item in reversed(recent_events):
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip().lower()
        if not kind or kind == "user_utterance":
            continue
        tags = {
            str(tag).strip().lower()
            for tag in (item.get("tags") if isinstance(item.get("tags"), list) else [])
            if str(tag).strip()
        }
        if kind == "self_activity_state":
            if {"deep_focus", "own_task"} & tags:
                return "刚才你原本还在自己的事情里，这句更像顺手从那边回头。"
            if {"break_window", "small_opening", "reapproach"} & tags:
                return "刚才你只是从自己的节奏里短暂抬头，所以这句不会一下子铺得很满。"
            return "刚才你还在按自己的节奏待着，这句不是凭空跳出来的。"
        if kind == "scheduled_life_due":
            if {"shared_activity_window", "offer_window"} & tags:
                return "刚才你们之间还留着一点能继续一起待会儿的空当，这句会带一点那边的余温。"
            if {"deadline_window", "work_nudge", "task_window"} & tags:
                return "刚才你心里还挂着一件要记着的事，所以注意力不会完全是空白的。"
            return "刚才有点生活上的惦记掠过去了，所以你开口时会带着一点余波。"
        if kind == "scheduled_checkin_due":
            return "刚才有一下原本可能开口的时机掠过去了，所以这句会自然更轻一点。"
        if kind == "time_idle":
            if {"respect_space", "user_busy", "cognitive_load"} & tags:
                return "前面那阵安静更像是在判断现在适不适合靠近，而不是单纯空白。"
            return "刚才那段安静还留着一点余温，所以这句不会像重新开机。"
        if kind == "ambient_shift":
            return "刚才周围有一点小变化掠过去了，所以你这句会带着一点当下环境感。"
        if kind == "gesture_signal":
            return "刚才那个小动作留下的在场感还没退干净，所以你会先顺着那个感觉开口。"
        break
    return ""

def _compact_interaction_carryover_hint(carryover: dict[str, Any] | None) -> str:
    if not isinstance(carryover, dict):
        return ""
    relationship_weather = str(carryover.get("relationship_weather") or "").strip().lower()
    mode = str(carryover.get("carryover_mode") or "").strip().lower()
    strength = _clamp01(carryover.get("strength"), 0.0)
    source_turn_gap = max(0, int(carryover.get("source_turn_gap") or 0))
    attention_target = str(carryover.get("attention_target") or "").strip().lower()
    note = str(carryover.get("note") or "").strip()
    if not mode or strength < 0.12:
        return ""

    parts: list[str] = []
    if note:
        parts.append(note.rstrip("。"))
    elif mode == "own_rhythm":
        parts.append("前面那段安静还留着一点你自己的节奏")
    elif mode == "quiet_recontact":
        parts.append("刚从安静里抬头，这轮开口会自然轻一点")
    elif mode == "small_opening":
        parts.append("安静过后还留着一个不太张扬的小开口")
    elif mode == "shared_window":
        parts.append("前面那点还能接着说下去的空当还没完全过去")
    elif mode == "task_window":
        parts.append("之前那件挂着的事还留在你的注意力里")
    elif mode == "life_window":
        parts.append("前面那点生活上的惦记还留在你心里")
    elif mode == "brief_presence":
        parts.append("上一下轻信号留下的在场感还没完全退掉")
    elif mode == "ambient_echo":
        parts.append("刚才注意到的小动静还留在你的感知里")

    weather_phrase = _relationship_weather_phrase(relationship_weather, strength=strength)
    if weather_phrase:
        parts.append(weather_phrase)

    if source_turn_gap >= 2:
        parts.append("中间虽然已经隔了几句，这层余波还没完全退掉")
    elif source_turn_gap == 1:
        parts.append("中间隔了一句，但这层余波还在")

    if strength >= 0.58:
        parts.append("这层余韵还比较明显")
    elif strength >= 0.34:
        parts.append("这层余韵还在")

    if attention_target == "self_then_counterpart":
        parts.append("你会先从自己的节奏里抬头，再把注意力递过去")
    elif attention_target == "shared_window":
        parts.append("注意力会顺手落回你们刚才那点还能接着一起待会儿的空当")
    elif attention_target == "shared_task":
        parts.append("注意力还贴着那件共同的事")
    elif attention_target == "counterpart_state" and mode == "life_window":
        parts.append("你会顺手记着他的状态，再决定要不要把那件小事提回来")
    elif attention_target == "object_then_user":
        parts.append("你会先掠过刚才那点小事，再回到他身上")
    elif attention_target == "counterpart_state" and mode in {"quiet_recontact", "brief_presence"}:
        parts.append("所以你会先轻轻确认他的在场")

    return "，".join(parts[:3]) + "。"


def _compact_long_horizon_continuity_hint(
    *,
    world_model_state: dict[str, Any] | None,
    semantic_narrative_profile: dict[str, Any] | None = None,
    interaction_carryover: dict[str, Any] | None = None,
    counterpart_assessment: dict[str, Any] | None = None,
) -> str:
    world = dict(world_model_state or {})
    semantic = dict(semantic_narrative_profile or {})
    carryover = dict(interaction_carryover or {})
    assessment = dict(counterpart_assessment or {})
    source_tags = {
        str(item).strip().lower()
        for item in (carryover.get("source_tags") if isinstance(carryover.get("source_tags"), list) else [])
        if str(item).strip()
    }

    axis_count = max(
        0,
        int(world.get("long_term_axis_count") or 0),
        int(semantic.get("long_term_axis_count") or 0),
    )
    continuity_depth = max(
        _clamp01(world.get("semantic_continuity_depth"), 0.0),
        _clamp01(semantic.get("continuity_depth"), 0.0),
        _source_tag_floor(source_tags, "continuity_anchor", floor=0.5),
    )
    identity_gravity = max(
        _clamp01(world.get("semantic_identity_gravity"), 0.0),
        _clamp01(semantic.get("identity_gravity"), 0.0),
    )
    lineage_gravity = max(
        _clamp01(world.get("lineage_gravity"), 0.0),
        _clamp01(semantic.get("lineage_gravity"), 0.0),
    )
    continuity_score = max(
        continuity_depth,
        identity_gravity,
        lineage_gravity,
        _clamp01(axis_count / 4.0),
    )

    own_score = max(
        _clamp01(world.get("own_rhythm_anchor"), 0.0),
        _clamp01(world.get("agency_lineage"), 0.0),
        _clamp01(semantic.get("rhythm_continuity"), 0.0),
        _clamp01(semantic.get("agency_drive"), 0.0),
        _source_tag_floor(source_tags, "own_rhythm_anchor", "agency_lineage"),
    )
    contact_score = max(
        _clamp01(world.get("recontact_anchor"), 0.0),
        _clamp01(world.get("memory_anchor"), 0.0),
        _clamp01(world.get("contact_lineage"), 0.0),
        _clamp01(world.get("repair_lineage"), 0.0),
        _clamp01(semantic.get("presence_carry"), 0.0),
        _clamp01(semantic.get("repair_residue"), 0.0),
        _clamp01(semantic.get("commitment_carry"), 0.0),
        _source_tag_floor(
            source_tags,
            "recontact_anchor",
            "memory_anchor",
            "contact_lineage",
            "repair_lineage",
        ),
    )
    stance = str(assessment.get("stance") or "").strip().lower()
    boundary_score = max(
        _clamp01(world.get("boundary_anchor"), 0.0),
        _clamp01(world.get("boundary_lineage"), 0.0),
        _clamp01(world.get("selfhood_lineage"), 0.0),
        _clamp01(semantic.get("boundary_residue"), 0.0),
        _clamp01(semantic.get("selfhood_integrity"), 0.0),
        0.84 * _clamp01(assessment.get("boundary_pressure"), 0.0),
        0.56 if stance in {"guarded", "watchful"} else 0.0,
        _source_tag_floor(source_tags, "boundary_anchor", "boundary_lineage", "selfhood_lineage"),
    )

    if max(continuity_score, own_score, contact_score, boundary_score) < 0.42:
        return ""

    parts: list[str] = []
    if continuity_score >= 0.5:
        if axis_count >= 2 or lineage_gravity >= 0.54 or continuity_depth >= 0.54 or identity_gravity >= 0.54:
            parts.append("这轮不是凭空冒出来的一句，前面慢慢沉下来的判断和关系惯性都会一起带进来")

    if boundary_score >= 0.48 and boundary_score >= max(own_score, contact_score) + 0.05:
        if contact_score >= 0.44:
            parts.append("会接住对方，但边界上的判断还在，所以不会因为表面缓和就一下子全放松")
        else:
            parts.append("边界上的判断还在往下延续，所以不会因为眼前这句就一下子把分寸全放开")
    elif own_score >= 0.46 and own_score >= max(boundary_score, contact_score) + 0.05:
        parts.append("自己的节奏和主动性还在往下延续，更像从原来的轨道里回头，而不是被一下子拽过去")
    elif contact_score >= 0.46:
        if boundary_score >= 0.44:
            parts.append("靠近和分寸会一起在场，你会顺着前面的脉络往下接，但不会一下子把话说满")
        else:
            parts.append("靠近、修补或记挂的脉络还在，所以这句会顺着前面的线往下接")
    elif continuity_score >= 0.54:
        parts.append("这段关系和自我判断已经有连续脉络，不会每轮都按成全新的起点")

    ordered: list[str] = []
    for item in parts:
        text = str(item or "").strip().rstrip("。")
        if text and text not in ordered:
            ordered.append(text)
    if not ordered:
        return ""
    return "；".join(ordered[:2]) + "。"

def _relationship_weather_phrase(relationship_weather: Any, *, strength: float = 0.0) -> str:
    weather = str(relationship_weather or "").strip().lower()
    residue = _clamp01(strength, 0.0)
    if weather == "guarded_residue":
        return (
            "前面那点别扭和防备还没完全退掉"
            if residue >= 0.42
            else "那点防备还没完全散"
        )
    if weather == "warm_residue":
        return (
            "刚顺下来的熟悉感和回暖还在"
            if residue >= 0.42
            else "那点回暖和熟悉感还在"
        )
    if weather == "repair_residue":
        return (
            "刚修补回来的那点小心和回暖还在"
            if residue >= 0.42
            else "那点刚缓回来的小心还在"
        )
    return ""

def _compact_behavior_agenda_hint(
    agenda: Any,
    *,
    current_event: dict[str, Any] | None = None,
) -> str:
    event = dict(current_event or {})
    event_kind = str(event.get("kind") or "user_utterance").strip().lower()
    if event_kind != "user_utterance":
        return ""

    entries = _normalize_behavior_agenda(agenda)
    if not entries:
        return ""

    def _agenda_rank(entry: dict[str, Any]) -> tuple[float, float, float, float]:
        return (
            _clamp01(entry.get("priority"), 0.0),
            _clamp01(entry.get("base_priority"), 0.0),
            _clamp01(entry.get("carryover_strength"), 0.0),
            _clamp01(entry.get("self_activity_momentum"), 0.0),
        )

    top = max(entries, key=_agenda_rank)
    status = str(top.get("status") or "").strip().lower()
    if status and status not in {"pending", "queued", "held"}:
        return ""

    kind = str(top.get("kind") or "").strip().lower()
    trigger_family = str(top.get("trigger_family") or "").strip().lower()
    carryover_mode = str(top.get("carryover_mode") or "").strip().lower()
    attention_target = str(top.get("attention_target") or "").strip().lower()
    hold_count = max(0, int(top.get("hold_count") or 0))
    carryover_strength = _clamp01(top.get("carryover_strength"), 0.0)
    self_activity_momentum = _clamp01(top.get("self_activity_momentum"), 0.0)
    salience = max(
        _clamp01(top.get("priority"), 0.0),
        _clamp01(top.get("base_priority"), 0.0),
        carryover_strength,
        self_activity_momentum,
    )
    if salience < 0.24 and hold_count <= 0:
        return ""

    parts: list[str] = []
    if kind == "self_activity_continue" or trigger_family == "self_activity" or carryover_mode in {"own_rhythm", "small_opening"}:
        if hold_count >= 2:
            parts.append("你手头那段自己的节奏还没完全放下，这句更像从那边顺手回头")
        elif self_activity_momentum >= 0.56 or carryover_mode == "own_rhythm":
            parts.append("你手头那点自己的事情还挂着，所以不是完全空下来等他")
        else:
            parts.append("你这句会带着一点自己的节奏，不是把全部重心都压过去")
    elif kind == "deferred_checkin":
        if trigger_family in {"shared_activity", "shared_activity_window"}:
            parts.append("你心里还挂着一点还能再靠近一点的空当，但不会硬把它扯到台前")
        elif trigger_family == "life_window" or carryover_mode == "life_window":
            parts.append("你心里还留着一点生活上的小挂念，不过这轮不急着把它说成任务")
        elif trigger_family == "deadline_window" or carryover_mode == "task_window":
            parts.append("你还记着一件挂着的事，不过这轮不必急着把它提到前台")
        elif carryover_mode in {"quiet_recontact", "brief_presence"} or trigger_family in {"light_checkin", "observe"}:
            parts.append("你心里还留着一次没说出口的确认，所以起手会自然轻一点")

    if hold_count >= 2 and kind == "deferred_checkin":
        parts.append("那件事暂时被放回背景里，但不代表已经忘掉")

    if attention_target == "self_then_counterpart":
        parts.append("注意力会先从你自己这边抬头，再递到他身上")
    elif attention_target == "own_task":
        parts.append("注意力底下还压着你自己手头的事")
    elif attention_target == "shared_window":
        parts.append("注意力还会顺手掠过你们刚才那点还能接着一起待会儿的空当")
    elif attention_target == "shared_task":
        parts.append("注意力底下还贴着那件共同的事")
    elif attention_target == "counterpart_state" and carryover_mode in {"quiet_recontact", "brief_presence"}:
        parts.append("所以你更像先轻轻确认他的状态，再决定要不要展开")

    deduped: list[str] = []
    for item in parts:
        text = str(item or "").strip().rstrip("。")
        if text and text not in deduped:
            deduped.append(text)
    if not deduped:
        return ""
    return "，".join(deduped[:2]) + "。"

def _compact_focus_lines(items: list[dict[str, Any]], limit: int = 4) -> list[str]:
    lines: list[str] = []
    for item in items[: max(1, int(limit))]:
        text = _focus_text(item)
        if not text:
            continue
        lines.append(f"- {text[:180]}")
    return lines

def _compact_rule_lines(user_rules: list[Any], limit: int = 3) -> list[str]:
    lines: list[str] = []
    for item in user_rules[: max(1, int(limit))]:
        if isinstance(item, dict):
            text = str(item.get("text") or "").strip()
        else:
            text = str(item or "").strip()
        if text:
            lines.append(f"- {text[:160]}")
    return lines
