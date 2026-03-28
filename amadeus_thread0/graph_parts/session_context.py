from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from .state import SessionContextPayload, ThreadState


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _configurable(config: RunnableConfig | dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(config, dict):
        return {}
    payload = config.get("configurable")
    return dict(payload) if isinstance(payload, dict) else {}


def _legacy_thread_id_from_state(state: ThreadState | dict[str, Any] | None) -> str:
    data = state if isinstance(state, dict) else {}
    current_event = data.get("current_event")
    if not isinstance(current_event, dict):
        return ""
    perception = current_event.get("perception")
    if not isinstance(perception, dict):
        return ""
    return _clean_text(perception.get("thread_id"))


def resolve_session_context(
    *,
    state: ThreadState | dict[str, Any] | None,
    config: RunnableConfig | dict[str, Any] | None,
    turn_now_ts: int,
) -> SessionContextPayload:
    data = state if isinstance(state, dict) else {}
    state_context = data.get("session_context")
    state_context = dict(state_context) if isinstance(state_context, dict) else {}
    configurable = _configurable(config)

    thread_id = (
        _clean_text(configurable.get("thread_id"))
        or _clean_text(state_context.get("thread_id"))
        or _legacy_thread_id_from_state(data)
        or "thread"
    )
    turn_started_at = int(turn_now_ts or state_context.get("turn_started_at") or 0)
    prior_turn_started_at = int(state_context.get("turn_started_at") or 0)
    turn_id = _clean_text(state_context.get("turn_id"))
    if not turn_id or prior_turn_started_at != turn_started_at:
        turn_id = f"{thread_id}:{turn_started_at}" if thread_id else f"turn:{turn_started_at}"

    resolved: SessionContextPayload = {
        "thread_id": thread_id,
        "turn_id": turn_id,
        "turn_started_at": turn_started_at,
    }
    user_id = _clean_text(configurable.get("user_id")) or _clean_text(state_context.get("user_id"))
    checkpoint_id = _clean_text(configurable.get("checkpoint_id")) or _clean_text(state_context.get("checkpoint_id"))
    if user_id:
        resolved["user_id"] = user_id
    if checkpoint_id:
        resolved["checkpoint_id"] = checkpoint_id
    hint_payload = configurable.get("digital_body_hints")
    if not isinstance(hint_payload, dict):
        hint_payload = state_context.get("digital_body_hints")
    if isinstance(hint_payload, dict) and hint_payload:
        resolved["digital_body_hints"] = dict(hint_payload)
    return resolved


__all__ = ["resolve_session_context"]
