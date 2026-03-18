from __future__ import annotations

import sqlite3
from functools import lru_cache

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from ..settings import get_settings
from .turn_events import _is_silent_behavior_event
from .nodes import _node_call_model, _node_prepare_turn
from .runtime_services import _get_store, _get_tool_bundle
from .state import ThreadState
from .tool_nodes import _node_tool_execute, _node_tool_gate, _node_tool_limit, _route_after_model

_CHECKPOINT_CONN: sqlite3.Connection | None = None


def _route_after_prepare(state: ThreadState) -> str:
    current_event = state.get("current_event") if isinstance(state.get("current_event"), dict) else {}
    behavior_action = state.get("behavior_action") if isinstance(state.get("behavior_action"), dict) else {}
    if _is_silent_behavior_event(current_event, behavior_action):
        return END
    return "call_model"


def _build_checkpointer() -> SqliteSaver:
    global _CHECKPOINT_CONN
    if _CHECKPOINT_CONN is None:
        s = get_settings()
        s.checkpoint_db_path.parent.mkdir(parents=True, exist_ok=True)
        _CHECKPOINT_CONN = sqlite3.connect(str(s.checkpoint_db_path), check_same_thread=False)
        _CHECKPOINT_CONN.execute("PRAGMA journal_mode=WAL")
        _CHECKPOINT_CONN.execute("PRAGMA foreign_keys=ON")
    return SqliteSaver(_CHECKPOINT_CONN)


def reset_runtime_caches() -> None:
    global _CHECKPOINT_CONN
    try:
        if _CHECKPOINT_CONN is not None:
            _CHECKPOINT_CONN.close()
    except Exception:
        pass
    _CHECKPOINT_CONN = None
    _get_store.cache_clear()
    _get_tool_bundle.cache_clear()
    build_graph.cache_clear()


@lru_cache(maxsize=1)
def build_graph():
    s = get_settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)

    builder = StateGraph(ThreadState)
    builder.add_node("prepare_turn", _node_prepare_turn)
    builder.add_node("call_model", _node_call_model)
    builder.add_node("tool_gate", _node_tool_gate)
    builder.add_node("tool_execute", _node_tool_execute)
    builder.add_node("tool_limit", _node_tool_limit)

    builder.add_edge(START, "prepare_turn")
    builder.add_conditional_edges(
        "prepare_turn",
        _route_after_prepare,
        {
            "call_model": "call_model",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "call_model",
        _route_after_model,
        {
            "tool_gate": "tool_gate",
            "tool_limit": "tool_limit",
            END: END,
        },
    )
    builder.add_edge("tool_gate", "tool_execute")
    builder.add_edge("tool_execute", "call_model")
    builder.add_edge("tool_limit", END)

    return builder.compile(checkpointer=_build_checkpointer())
