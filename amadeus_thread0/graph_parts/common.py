from __future__ import annotations

import json
import time
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from .postprocess import _clean_utf8_text


def _now_ts() -> int:
    return int(time.time())


def _sanitize_obj(value: Any) -> Any:
    if isinstance(value, str):
        return _clean_utf8_text(value)
    if isinstance(value, list):
        return [_sanitize_obj(x) for x in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_obj(x) for x in value)
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for k, v in value.items():
            out[_sanitize_obj(k)] = _sanitize_obj(v)
        return out
    return value


def _sanitize_message(msg: BaseMessage) -> BaseMessage:
    try:
        dumped = msg.model_dump(mode="python")
        cleaned_dump = _sanitize_obj(dumped)
        if isinstance(cleaned_dump, dict):
            cleaned_dump.pop("type", None)
            return type(msg)(**cleaned_dump)
    except Exception:
        pass

    content = getattr(msg, "content", "")
    cleaned = _sanitize_obj(content)
    try:
        return msg.model_copy(update={"content": cleaned})
    except Exception:
        pass

    if isinstance(msg, HumanMessage):
        return HumanMessage(content=cleaned)
    if isinstance(msg, AIMessage):
        return AIMessage(
            content=cleaned,
            tool_calls=list(getattr(msg, "tool_calls", None) or []),
            additional_kwargs=dict(getattr(msg, "additional_kwargs", {}) or {}),
            response_metadata=dict(getattr(msg, "response_metadata", {}) or {}),
        )
    if isinstance(msg, SystemMessage):
        return SystemMessage(content=cleaned)
    if isinstance(msg, ToolMessage):
        return ToolMessage(content=cleaned, tool_call_id=str(getattr(msg, "tool_call_id", "")))
    return msg


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(_sanitize_obj(value), ensure_ascii=False)
    except Exception:
        return json.dumps(_clean_utf8_text(str(value)), ensure_ascii=False)


def _norm_text(text: str) -> str:
    return str(text or "").strip().lower()


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
    except Exception:
        v = float(default)
    return max(0.0, min(1.0, v))


def _clamp_signed(value: Any, low: float = -1.0, high: float = 1.0, default: float = 0.0) -> float:
    try:
        v = float(value)
    except Exception:
        v = float(default)
    return max(float(low), min(float(high), v))
