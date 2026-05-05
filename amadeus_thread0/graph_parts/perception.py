from __future__ import annotations

from typing import Any


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _clamp01(value: Any, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return float(default)


def _channel_from_source(source: str) -> str:
    normalized = _clean_text(source).lower()
    if normalized in {"text", "chat", "cli", "im", "dm"}:
        return "text"
    if normalized in {"voice", "audio", "speech", "tts"}:
        return "voice"
    if normalized in {"vision", "camera", "image"}:
        return "vision"
    if normalized in {"browser", "browser_runtime", "web_runtime"}:
        return "browser"
    if normalized in {"sandbox", "sandbox_runner", "workspace_runner"}:
        return "sandbox"
    if normalized in {"skill", "skills", "skill_runtime"}:
        return "skill"
    if normalized in {"ambient", "environment"}:
        return "ambient"
    if normalized in {"system", "commitment_scheduler", "scheduler"}:
        return "system"
    return normalized or "external"


def _modality_from_event(kind: str, source: str) -> str:
    normalized_kind = _clean_text(kind).lower()
    channel = _channel_from_source(source)
    if normalized_kind == "tts_presence_timing_observation":
        return "TTS_presence_timing"
    if normalized_kind in {"browser_runtime_observation", "body_resource_observation"}:
        return "browser" if channel == "browser" else "body"
    if normalized_kind == "sandbox_run_observation":
        return "sandbox"
    if normalized_kind == "skill_usage_observation":
        return "skill"
    if normalized_kind == "audio_observation":
        return "audio"
    if normalized_kind == "vision_observation":
        return "vision"
    if channel in {"text", "voice", "vision", "ambient", "browser", "sandbox", "skill"}:
        return channel
    if normalized_kind.startswith("self_"):
        return "internal"
    if channel == "system":
        return "system"
    return "external"


def _source_role(kind: str, source: str) -> str:
    normalized_kind = _clean_text(kind).lower()
    normalized_source = _clean_text(source).lower()
    if normalized_kind == "user_utterance":
        return "counterpart"
    if normalized_kind.startswith("self_"):
        return "self"
    if normalized_kind == "tts_presence_timing_observation" or normalized_source == "tts":
        return "runtime"
    if normalized_kind == "skill_usage_observation" or normalized_source in {"skill", "skills", "skill_runtime"}:
        return "capability"
    if normalized_kind in {
        "browser_runtime_observation",
        "sandbox_run_observation",
        "audio_observation",
        "vision_observation",
        "body_resource_observation",
    } or normalized_source in {"browser", "browser_runtime", "web_runtime", "sandbox", "sandbox_runner", "workspace_runner"}:
        return "environment"
    if normalized_source in {"system", "commitment_scheduler", "scheduler"}:
        return "system"
    return "external"


def _interruptibility(kind: str, source: str) -> str:
    normalized_kind = _clean_text(kind).lower()
    normalized_source = _clean_text(source).lower()
    if normalized_kind == "user_utterance":
        return "hard"
    if normalized_kind in {"gesture_signal", "scene_observation"}:
        return "hard"
    if normalized_kind in {"time_idle", "scheduled_life_due"}:
        return "soft"
    if normalized_kind.startswith("self_") or normalized_source in {"system", "commitment_scheduler", "scheduler"}:
        return "soft"
    return "passive"


def _delivery_mode(kind: str, source: str) -> str:
    normalized_kind = _clean_text(kind).lower()
    normalized_source = _clean_text(source).lower()
    if normalized_kind == "user_utterance":
        return "direct"
    if normalized_kind == "tts_presence_timing_observation":
        return "spoken"
    if normalized_source in {"system", "commitment_scheduler", "scheduler"}:
        return "scheduled"
    if normalized_kind.startswith("self_"):
        return "self_initiated"
    if normalized_kind in {"audio_observation", "vision_observation"}:
        return "ambient"
    if normalized_kind in {"browser_runtime_observation", "sandbox_run_observation", "skill_usage_observation", "body_resource_observation"}:
        return "external"
    if normalized_source in {"ambient", "vision"}:
        return "ambient"
    return "external"


def _trust_tier(kind: str, source: str) -> str:
    normalized_kind = _clean_text(kind).lower()
    normalized_source = _clean_text(source).lower()
    if normalized_kind == "tts_presence_timing_observation":
        return "high_runtime_telemetry"
    if normalized_kind in {"user_utterance", "time_idle", "scheduled_life_due"}:
        return "high"
    if normalized_kind.startswith("self_") or normalized_source in {"system", "commitment_scheduler", "scheduler"}:
        return "high"
    if normalized_kind in {
        "browser_runtime_observation",
        "sandbox_run_observation",
        "skill_usage_observation",
        "audio_observation",
        "vision_observation",
        "body_resource_observation",
    }:
        return "medium"
    if normalized_source in {"vision", "ambient", "voice", "audio", "browser", "sandbox", "skill"}:
        return "medium"
    return "medium" if normalized_kind else "low"


def _base_salience(kind: str, source: str, tags: list[str], text: str) -> float:
    normalized_kind = _clean_text(kind).lower()
    normalized_source = _clean_text(source).lower()
    normalized_tags = {str(item or "").strip().lower() for item in tags if str(item or "").strip()}
    salience = 0.45
    if normalized_kind == "user_utterance":
        salience = 0.82
    elif normalized_kind in {"gesture_signal", "scene_observation"}:
        salience = 0.7
    elif normalized_kind in {"time_idle", "scheduled_life_due"}:
        salience = 0.58
    elif normalized_kind.startswith("self_"):
        salience = 0.52
    elif normalized_source == "ambient":
        salience = 0.4
    if {"care_opportunity", "relationship", "repair", "boundary", "commitment_window"} & normalized_tags:
        salience += 0.08
    if len(_clean_text(text)) >= 60:
        salience += 0.04
    return max(0.0, min(1.0, salience))


def attach_perception_context(
    event: dict[str, Any] | None,
    *,
    thread_id: str,
    turn_now_ts: int,
    turn_id: str = "",
) -> dict[str, Any]:
    payload = dict(event or {}) if isinstance(event, dict) else {}
    if not payload:
        return {}
    kind = _clean_text(payload.get("kind")) or "external_event"
    source = _clean_text(payload.get("source")) or "external"
    created_at = int(payload.get("created_at") or turn_now_ts or 0)
    tags = payload.get("tags") if isinstance(payload.get("tags"), list) else []
    text = _clean_text(payload.get("effective_text")) or _clean_text(payload.get("text"))
    perception = payload.get("perception") if isinstance(payload.get("perception"), dict) else {}
    digital_body_hints = (
        dict(perception.get("digital_body_hints"))
        if isinstance(perception.get("digital_body_hints"), dict)
        else dict(payload.get("digital_body_hints"))
        if isinstance(payload.get("digital_body_hints"), dict)
        else {}
    )
    session_thread_id = _clean_text(perception.get("thread_id")) or _clean_text(thread_id)
    event_id = _clean_text(perception.get("event_id")) or (
        f"{session_thread_id}:{created_at}:{kind}:{source}"
        if session_thread_id
        else f"event:{created_at}:{kind}:{source}"
    )
    session_turn_id = _clean_text(perception.get("turn_id")) or _clean_text(turn_id)
    if not session_turn_id:
        session_turn_id = f"{session_thread_id}:{turn_now_ts}" if session_thread_id else f"turn:{turn_now_ts}"
    payload["perception"] = {
        "event_id": event_id,
        "thread_id": session_thread_id,
        "turn_id": session_turn_id,
        "channel": _clean_text(perception.get("channel")) or _channel_from_source(source),
        "modality": _clean_text(perception.get("modality")) or _modality_from_event(kind, source),
        "source_role": _clean_text(perception.get("source_role")) or _source_role(kind, source),
        "trust_tier": _clean_text(perception.get("trust_tier")) or _trust_tier(kind, source),
        "salience": _clamp01(
            perception.get("salience")
            if "salience" in perception
            else _base_salience(kind, source, tags, text),
            _base_salience(kind, source, tags, text),
        ),
        "interruptibility": _clean_text(perception.get("interruptibility")) or _interruptibility(kind, source),
        "delivery_mode": _clean_text(perception.get("delivery_mode")) or _delivery_mode(kind, source),
        "is_proactive": bool(
            perception.get("is_proactive")
            if "is_proactive" in perception
            else _delivery_mode(kind, source) in {"scheduled", "self_initiated", "ambient"}
        ),
    }
    if digital_body_hints:
        payload["digital_body_hints"] = dict(digital_body_hints)
        payload["perception"]["digital_body_hints"] = dict(digital_body_hints)
    return payload


__all__ = ["attach_perception_context"]
