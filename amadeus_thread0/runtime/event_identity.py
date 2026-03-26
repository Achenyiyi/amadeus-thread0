from __future__ import annotations

from typing import Any


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _has_readback_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _readback_field(perception: dict[str, Any], context: dict[str, Any], key: str) -> Any:
    current = perception.get(key)
    if _has_readback_value(current):
        return current
    fallback = context.get(key)
    if _has_readback_value(fallback):
        return fallback
    if key in perception:
        return current
    return fallback


def resolve_readback_current_event(
    values: dict[str, Any] | None,
    *,
    thread_id: str,
    session_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = values if isinstance(values, dict) else {}
    current_event = _dict_or_empty(data.get("current_event"))
    if not current_event:
        return {}
    perception = current_event.get("perception") if isinstance(current_event.get("perception"), dict) else {}
    context = session_context if isinstance(session_context, dict) else {}
    session_thread_id = (
        str(context.get("thread_id") or "").strip()
        or str(perception.get("thread_id") or "").strip()
        or str(thread_id or "").strip()
    )
    created_at = int(current_event.get("created_at") or 0)
    kind = str(current_event.get("kind") or "external_event").strip() or "external_event"
    source = str(current_event.get("source") or "external").strip() or "external"
    current_event["kind"] = kind
    current_event["source"] = source
    if created_at > 0 or "created_at" in current_event:
        current_event["created_at"] = created_at
    turn_id = str(perception.get("turn_id") or "").strip() or str(context.get("turn_id") or "").strip() or (
        f"{session_thread_id}:{created_at}" if session_thread_id and created_at else ""
    )
    event_id = str(perception.get("event_id") or "").strip() or (
        f"{session_thread_id}:{created_at}:{kind}:{source}"
        if session_thread_id and created_at
        else f"event:{created_at}:{kind}:{source}"
    )
    perception_fields = (
        "channel",
        "modality",
        "source_role",
        "trust_tier",
        "salience",
        "interruptibility",
        "delivery_mode",
        "is_proactive",
    )
    current_event["perception"] = {
        **perception,
        "thread_id": session_thread_id,
        "turn_id": turn_id,
        "event_id": event_id,
        **{
            key: _readback_field(perception, context, key)
            for key in perception_fields
            if _has_readback_value(_readback_field(perception, context, key))
            or key in perception
            or key in context
        },
    }
    return current_event


def resolve_readback_session_context(
    values: dict[str, Any] | None,
    *,
    thread_id: str,
    current_event: dict[str, Any] | None,
) -> dict[str, Any]:
    data = values if isinstance(values, dict) else {}
    base = _dict_or_empty(data.get("session_context"))
    event = current_event if isinstance(current_event, dict) else {}
    perception = event.get("perception") if isinstance(event.get("perception"), dict) else {}
    return {
        **base,
        "thread_id": str(base.get("thread_id") or "").strip()
        or str(perception.get("thread_id") or "").strip()
        or str(thread_id or "").strip(),
        "turn_id": str(base.get("turn_id") or "").strip() or str(perception.get("turn_id") or "").strip(),
        "event_id": str(perception.get("event_id") or "").strip(),
    }


__all__ = ["resolve_readback_current_event", "resolve_readback_session_context"]
