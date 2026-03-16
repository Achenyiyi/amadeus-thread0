from __future__ import annotations

import re

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    messages_from_dict,
)

from ..config import CONTEXT_TRIM_TRIGGER_MESSAGES
from ..memory_store import MemoryStore
from .common import _now_ts, _sanitize_message, _sanitize_obj
from .state import ThreadState


def _messages(state: ThreadState) -> list[BaseMessage]:
    msgs = state.get("messages") or []
    out: list[BaseMessage] = []
    for m in msgs:
        if isinstance(m, BaseMessage):
            out.append(_sanitize_message(m))
            continue
        if isinstance(m, dict):
            try:
                restored = messages_from_dict([m])
            except Exception:
                restored = []
            if restored:
                out.extend(_sanitize_message(msg) for msg in restored if isinstance(msg, BaseMessage))
                continue

            data = m.get("data") if isinstance(m.get("data"), dict) else {}
            role = str(m.get("role") or m.get("type") or data.get("type") or "").lower().strip()
            content = _sanitize_obj(m.get("content") if "content" in m else data.get("content", ""))
            if role in {"user", "human"}:
                out.append(HumanMessage(content=content))
            elif role in {"assistant", "ai"}:
                tool_calls = m.get("tool_calls")
                if not isinstance(tool_calls, list):
                    tool_calls = data.get("tool_calls")
                out.append(
                    AIMessage(
                        content=content,
                        tool_calls=list(tool_calls or []),
                        additional_kwargs=dict(m.get("additional_kwargs") or data.get("additional_kwargs") or {}),
                    )
                )
            elif role == "system":
                out.append(SystemMessage(content=content))
            elif role == "tool":
                tool_call_id = m.get("tool_call_id") or data.get("tool_call_id") or ""
                out.append(ToolMessage(content=content, tool_call_id=str(tool_call_id)))
    return out

def _last_user_text(msgs: list[BaseMessage]) -> str:
    for m in reversed(msgs):
        if isinstance(m, HumanMessage):
            return str(m.content or "")
        if getattr(m, "type", "") == "human":
            return str(getattr(m, "content", "") or "")
    return ""

def _previous_user_text(msgs: list[BaseMessage]) -> str:
    seen_current = False
    for m in reversed(msgs):
        if isinstance(m, HumanMessage) or getattr(m, "type", "") == "human":
            if not seen_current:
                seen_current = True
                continue
            return str(getattr(m, "content", "") or "")
    return ""

def _last_ai_text(msgs: list[BaseMessage]) -> str:
    for m in reversed(msgs):
        if isinstance(m, AIMessage):
            c = m.content
            if isinstance(c, str):
                return c
            return str(c or "")
    return ""

def _recent_ai_texts(msgs: list[BaseMessage], limit: int = 4) -> list[str]:
    out: list[str] = []
    for m in reversed(msgs):
        if not isinstance(m, AIMessage):
            continue
        if list(getattr(m, "tool_calls", None) or []):
            continue
        text = str(getattr(m, "content", "") or "").strip()
        if not text:
            continue
        out.append(text)
        if len(out) >= max(1, int(limit)):
            break
    return list(reversed(out))

def _latest_ai(msgs: list[BaseMessage]) -> AIMessage | None:
    for m in reversed(msgs):
        if isinstance(m, AIMessage):
            return m
    return None

def _window_messages(msgs: list[BaseMessage], keep: int) -> list[BaseMessage]:
    if keep <= 0:
        keep = 20
    if len(msgs) <= keep:
        return msgs

    start = max(0, len(msgs) - keep)
    while start > 0:
        cur = msgs[start]
        prev = msgs[start - 1]
        if isinstance(cur, ToolMessage):
            start -= 1
            continue
        if isinstance(prev, AIMessage) and list(getattr(prev, "tool_calls", None) or []):
            start -= 1
            continue
        break
    return msgs[start:]

def _compact_thread_if_needed(msgs: list[BaseMessage], store: MemoryStore) -> None:
    if len(msgs) < int(CONTEXT_TRIM_TRIGGER_MESSAGES):
        return
    excerpts: list[str] = []
    for m in msgs[-36:]:
        role = "U" if isinstance(m, HumanMessage) else "A" if isinstance(m, AIMessage) else "T"
        content = str(getattr(m, "content", "") or "").strip()
        if not content:
            continue
        content = re.sub(r"\s+", " ", content)[:80]
        excerpts.append(f"{role}:{content}")
    if not excerpts:
        return
    summary = " | ".join(excerpts[-12:])[:420]
    store.set_profile("thread_summary", summary)
    store.set_profile_meta(
        "thread_summary",
        {
            "source": "context_compaction",
            "updated_at": _now_ts(),
            "message_count": len(msgs),
        },
    )
