from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from ..config import CANON_COUNTERPART_NAME
from ..evolution_engine import (
    build_event_frame as _engine_event_frame,
    build_event_tags as _engine_event_tags,
)
from ..memory_store import MemoryStore
from .common import _now_ts as _common_now_ts, _sanitize_obj as _common_sanitize_obj
from .postprocess import _has_any_marker
from .retrieval import _commitment_priority, _record_value
from .state import EventPayload


def _now_ts() -> int:
    return _common_now_ts()


def _event_tags(
    *,
    response_style_hint: str,
    science_mode: bool,
    continuation_mode: bool,
    user_text: str,
    appraisal: dict[str, Any] | None = None,
) -> list[str]:
    _ = user_text
    return _engine_event_tags(
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        continuation_mode=continuation_mode,
        appraisal=appraisal,
    )


def _event_frame(
    *,
    response_style_hint: str,
    science_mode: bool,
    user_text: str,
    continuation_mode: bool,
    appraisal: dict[str, Any] | None = None,
) -> str:
    _ = user_text
    return _engine_event_frame(
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        continuation_mode=continuation_mode,
        appraisal=appraisal,
    )


def _sanitize_obj(value: Any) -> Any:
    return _common_sanitize_obj(value)


def _is_silent_behavior_event(current_event: dict[str, Any], behavior_action: dict[str, Any]) -> bool:
    if not isinstance(current_event, dict) or not isinstance(behavior_action, dict):
        return False
    return str(behavior_action.get("channel") or "").strip() == "silence"


def _build_current_event(
    *,
    user_text: str,
    effective_text: str,
    response_style_hint: str,
    science_mode: bool,
    continuation_mode: bool,
    appraisal: dict[str, Any],
    counterpart_name: str,
    pending_user_goal: str,
) -> EventPayload:
    semantic_goal = str(pending_user_goal or effective_text or user_text).strip()
    return _sanitize_obj(
        {
            "kind": "user_utterance",
            "source": "text",
            "text": str(user_text or "").strip(),
            "effective_text": str(effective_text or user_text or "").strip(),
            "semantic_goal": semantic_goal[:220],
            "response_style_hint": str(response_style_hint or "natural").strip() or "natural",
            "science_mode": bool(science_mode),
            "continuation_mode": bool(continuation_mode),
            "counterpart_name": str(counterpart_name or CANON_COUNTERPART_NAME).strip(),
            "event_frame": _event_frame(
                response_style_hint=response_style_hint,
                science_mode=science_mode,
                user_text=user_text,
                continuation_mode=continuation_mode,
                appraisal=appraisal,
            ),
            "appraisal_label": str(appraisal.get("emotion_label") or appraisal.get("label") or "").strip(),
            "appraisal_confidence": float(appraisal.get("confidence", 0.0) or 0.0),
            "tags": _event_tags(
                response_style_hint=response_style_hint,
                science_mode=science_mode,
                continuation_mode=continuation_mode,
                user_text=user_text,
                appraisal=appraisal,
            ),
            "created_at": _now_ts(),
        }
    )


def _normalize_event_override(raw: Any, *, counterpart_name: str) -> EventPayload:
    raw = _sanitize_obj(raw)
    if not isinstance(raw, dict) or not raw:
        return {}
    meaningful = False
    for key in (
        "kind",
        "text",
        "effective_text",
        "semantic_goal",
        "goal_frame",
        "event_frame",
        "tags",
        "idle_minutes",
        "trigger_family",
        "commitment_id",
        "derived_from_plan_kind",
    ):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            meaningful = True
            break
        if isinstance(value, (int, float)) and float(value) != 0.0:
            meaningful = True
            break
        if isinstance(value, list) and value:
            meaningful = True
            break
        if isinstance(value, bool) and value:
            meaningful = True
            break
    if not meaningful:
        return {}
    event_kind = str(raw.get("kind") or "external_event").strip() or "external_event"
    source = str(raw.get("source") or "external").strip() or "external"
    text = str(raw.get("text") or "").strip()
    effective_text = str(raw.get("effective_text") or text).strip()
    semantic_goal = str(raw.get("semantic_goal") or effective_text or text).strip()
    response_style_hint = str(raw.get("response_style_hint") or "natural").strip() or "natural"
    event_frame = str(raw.get("event_frame") or "").strip()
    if not event_frame:
        if event_kind == "time_idle":
            try:
                idle_minutes = int(raw.get("idle_minutes") or 0)
            except Exception:
                idle_minutes = 0
            event_frame = f"{max(1, idle_minutes)} 分钟的静默时间过去了。"
        else:
            event_frame = "来自外界的一次事件输入"
    tags = raw.get("tags") if isinstance(raw.get("tags"), list) else []
    payload: EventPayload = {
        "kind": event_kind,
        "source": source,
        "text": text,
        "effective_text": effective_text,
        "semantic_goal": semantic_goal[:220],
        "response_style_hint": response_style_hint,
        "science_mode": bool(raw.get("science_mode", False)),
        "continuation_mode": bool(raw.get("continuation_mode", False)),
        "counterpart_name": str(raw.get("counterpart_name") or counterpart_name or CANON_COUNTERPART_NAME).strip(),
        "event_frame": event_frame,
        "appraisal_label": str(raw.get("appraisal_label") or "").strip(),
        "appraisal_confidence": float(raw.get("appraisal_confidence", 0.0) or 0.0),
        "tags": [str(item).strip() for item in tags if str(item or "").strip()],
        "created_at": int(raw.get("created_at") or _now_ts()),
    }
    primary_motive = str(raw.get("primary_motive") or "").strip()
    if primary_motive:
        payload["primary_motive"] = primary_motive
    motive_tension = str(raw.get("motive_tension") or "").strip()
    if motive_tension:
        payload["motive_tension"] = motive_tension
    goal_frame = str(raw.get("goal_frame") or "").strip()
    if goal_frame:
        payload["goal_frame"] = goal_frame[:220]
    if event_kind == "time_idle":
        try:
            payload["idle_minutes"] = max(1, int(raw.get("idle_minutes") or 0))
        except Exception:
            payload["idle_minutes"] = 1
    if raw.get("derived_from_plan_kind"):
        payload["derived_from_plan_kind"] = str(raw.get("derived_from_plan_kind") or "").strip()
    if raw.get("trigger_family"):
        payload["trigger_family"] = str(raw.get("trigger_family") or "").strip()
    if "commitment_id" in raw:
        try:
            payload["commitment_id"] = int(raw.get("commitment_id") or 0)
        except Exception:
            pass
    if raw.get("due_at"):
        payload["due_at"] = str(raw.get("due_at") or "").strip()
    if "scheduled_after_min" in raw:
        try:
            payload["scheduled_after_min"] = max(0, int(raw.get("scheduled_after_min") or 0))
        except Exception:
            payload["scheduled_after_min"] = 0
    carryover_mode = str(raw.get("carryover_mode") or "").strip()
    if carryover_mode:
        payload["carryover_mode"] = carryover_mode
    if "carryover_strength" in raw:
        try:
            payload["carryover_strength"] = max(0.0, min(1.0, float(raw.get("carryover_strength") or 0.0)))
        except Exception:
            payload["carryover_strength"] = 0.0
    relationship_weather = str(raw.get("relationship_weather") or "").strip()
    if relationship_weather:
        payload["relationship_weather"] = relationship_weather
    if "presence_residue" in raw:
        try:
            payload["presence_residue"] = max(0.0, min(1.0, float(raw.get("presence_residue") or 0.0)))
        except Exception:
            payload["presence_residue"] = 0.0
    if "ambient_resonance" in raw:
        try:
            payload["ambient_resonance"] = max(0.0, min(1.0, float(raw.get("ambient_resonance") or 0.0)))
        except Exception:
            payload["ambient_resonance"] = 0.0
    if "self_activity_momentum" in raw:
        try:
            payload["self_activity_momentum"] = max(0.0, min(1.0, float(raw.get("self_activity_momentum") or 0.0)))
        except Exception:
            payload["self_activity_momentum"] = 0.0
    attention_target_hint = str(raw.get("attention_target_hint") or "").strip()
    if attention_target_hint:
        payload["attention_target_hint"] = attention_target_hint
    nonverbal_signal_hint = str(raw.get("nonverbal_signal_hint") or "").strip()
    if nonverbal_signal_hint:
        payload["nonverbal_signal_hint"] = nonverbal_signal_hint
    return _sanitize_obj(payload)


def _parse_due_at_timestamp(raw: Any) -> int | None:
    text = str(raw or "").strip()
    if not text:
        return None
    normalized = re.sub(r"[Tt]", " ", text).replace("/", "-")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(normalized, fmt)
            return int(parsed.timestamp())
        except Exception:
            continue
    return None


def _commitment_life_window_family(text: str) -> str:
    content = str(text or "").strip()
    shared_markers = {"一起看", "看一集", "追番", "看剧", "休息一下", "歇一下", "一起玩", "一起去", "一起听"}
    work_markers = {"稿", "交稿", "改稿", "收尾", "引言", "论文", "演示", "训练", "复盘", "答辩", "实验", "日志", "提交", "改完"}
    if _has_any_marker(content, shared_markers):
        return "shared_activity_window"
    if _has_any_marker(content, work_markers):
        return "deadline_window"
    return "life_window"


def _promote_due_commitment_event(
    event: EventPayload,
    store: MemoryStore,
    *,
    counterpart_name: str,
) -> EventPayload:
    if not isinstance(event, dict) or not event:
        return event
    if str(event.get("kind") or "").strip() != "time_idle":
        return event
    event_tags = {
        str(item).strip()
        for item in (event.get("tags") if isinstance(event.get("tags"), list) else [])
        if str(item).strip()
    }
    now_ts = _now_ts()
    candidates: list[tuple[float, dict[str, Any], str]] = []
    for item in store.list_commitments(limit=20):
        status = str(_record_value(item, "status", item.get("status") or "open") or "open").strip().lower()
        if status not in {"open", "active", "pending"}:
            continue
        due_at = str(_record_value(item, "due_at", "") or "").strip()
        due_ts = _parse_due_at_timestamp(due_at)
        if due_ts is None:
            continue
        text = str(_record_value(item, "text", "") or "").strip()
        if not text:
            continue
        family = _commitment_life_window_family(text)
        lead_window_s = 3 * 3600 if family == "deadline_window" else 2 * 3600
        stale_window_s = 18 * 3600 if family == "shared_activity_window" else 24 * 3600
        if not (now_ts >= due_ts - lead_window_s and now_ts <= due_ts + stale_window_s):
            continue
        priority = _commitment_priority(item)
        if family == "shared_activity_window" and ("late_night" in event_tags or "quiet_presence" in event_tags):
            priority += 0.08
        if family == "deadline_window" and "quiet_work" in event_tags:
            priority += 0.06
        candidates.append((priority, item, family))
    if not candidates:
        return event

    candidates.sort(key=lambda item: item[0], reverse=True)
    _, selected, family = candidates[0]
    text = str(_record_value(selected, "text", "") or "").strip()
    due_at = str(_record_value(selected, "due_at", "") or "").strip()
    commitment_id = int(selected.get("id") or 0)
    merged_tags = list(
        dict.fromkeys(
            [
                *(str(item).strip() for item in event.get("tags", []) if str(item).strip()),
                "scheduled_due",
                family,
                "commitment_window",
                "shared_task" if family == "deadline_window" else "offer_window" if family == "shared_activity_window" else "life_window",
                "work_nudge" if family == "deadline_window" else "",
            ]
        )
    )
    promoted = dict(event)
    promoted.update(
        {
            "kind": "scheduled_life_due",
            "source": "commitment_scheduler",
            "text": (
                f"你们之前认真留过的那个共同安排，又回到了你的注意力里：{text}"
                if family == "shared_activity_window"
                else f"前面认真挂着的那件事，又回到了你的注意力里：{text}"
                if family == "deadline_window"
                else f"你前面认真说过的那点事，又轻轻浮回了你的注意力里：{text}"
            ),
            "effective_text": (
                text
                if family == "deadline_window"
                else f"你又想起你们刚才那点还能一起接着做点什么的空当：{text}"
                if family == "shared_activity_window"
                else f"你又想起前面提过的那点生活上的事：{text}"
            ),
            "semantic_goal": (
                f"你又想起和{counterpart_name}之间刚才那点还能一起接着做点什么的空当：{text}"
                if family == "shared_activity_window"
                else f"和{counterpart_name}之间挂着的事重新浮回你的注意力里：{text}"
                if family == "deadline_window"
                else f"你又想起和{counterpart_name}之间前面那点生活上的挂念：{text}"
            )[:220],
            "event_frame": "scheduled_deadline_window" if family == "deadline_window" else "scheduled_shared_activity_window" if family == "shared_activity_window" else "scheduled_life_window",
            "trigger_family": family,
            "derived_from_plan_kind": "commitment_window",
            "scheduled_after_min": 0,
            "commitment_id": commitment_id,
            "due_at": due_at,
            "counterpart_name": counterpart_name,
            "tags": merged_tags,
        }
    )
    return promoted


def _appraisal_event_context(
    *,
    user_text: str,
    effective_text: str,
    response_style_hint: str,
    science_mode: bool,
    continuation_mode: bool,
    counterpart_name: str,
    pending_user_goal: str,
    event_override: Any,
) -> EventPayload:
    if isinstance(event_override, dict) and event_override:
        return _normalize_event_override(event_override, counterpart_name=counterpart_name)
    return _sanitize_obj(
        {
            "kind": "user_utterance",
            "source": "text",
            "text": str(user_text or "").strip(),
            "effective_text": str(effective_text or user_text or "").strip(),
            "semantic_goal": str(pending_user_goal or effective_text or user_text or "").strip()[:220],
            "response_style_hint": str(response_style_hint or "natural").strip() or "natural",
            "science_mode": bool(science_mode),
            "continuation_mode": bool(continuation_mode),
            "counterpart_name": str(counterpart_name or CANON_COUNTERPART_NAME).strip(),
            "event_frame": _event_frame(
                response_style_hint=response_style_hint,
                science_mode=science_mode,
                user_text=user_text,
                continuation_mode=continuation_mode,
            ),
            "tags": _event_tags(
                response_style_hint=response_style_hint,
                science_mode=science_mode,
                continuation_mode=continuation_mode,
                user_text=user_text,
                appraisal={},
            ),
            "created_at": _now_ts(),
        }
    )


def _append_recent_events(history: Any, current_event: EventPayload, *, limit: int = 6) -> list[EventPayload]:
    items: list[EventPayload] = []
    if isinstance(history, list):
        for item in history:
            if isinstance(item, dict):
                items.append(_sanitize_obj(dict(item)))
    if isinstance(current_event, dict) and str(current_event.get("text") or current_event.get("effective_text") or "").strip():
        items.append(_sanitize_obj(dict(current_event)))
    deduped: list[EventPayload] = []
    seen: set[str] = set()
    for item in reversed(items):
        key = json.dumps(
            {
                "text": str(item.get("text") or ""),
                "effective_text": str(item.get("effective_text") or ""),
                "created_at": int(item.get("created_at") or 0),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= int(limit):
            break
    deduped.reverse()
    return deduped
