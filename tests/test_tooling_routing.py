from __future__ import annotations

from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage

from amadeus_thread0.graph_parts.nodes import _node_tool_limit
from amadeus_thread0.graph_parts.tooling import (
    _infer_memory_tool_calls,
    _parse_explicit_tool_call,
    _parse_set_profile_args,
)


def test_parse_set_profile_args_from_natural_language():
    payload = _parse_set_profile_args("把我的nickname设为凶真")

    assert payload["key"] == "nickname"
    assert payload["value"] == "凶真"
    assert payload["mode"] == "merge"


def test_parse_explicit_tool_call_prefers_named_registered_tool():
    tools = [SimpleNamespace(name="set_profile")]

    calls = _parse_explicit_tool_call("请调用 set_profile 工具，把我的nickname设为凶真", tools)

    assert calls is not None
    assert calls[0]["name"] == "set_profile"
    assert calls[0]["args"]["key"] == "nickname"
    assert calls[0]["args"]["value"] == "凶真"


def test_infer_memory_tool_calls_adds_commitment_and_worldline_event_for_explicit_request():
    calls = _infer_memory_tool_calls("请记住，下周一起复盘实验，别忘了提醒我。")
    names = [call["name"] for call in calls]

    assert "add_commitment" in names
    assert "add_worldline_event" in names


def test_node_tool_limit_returns_fallback_reply_for_tool_overflow():
    state = {
        "messages": [
            HumanMessage(content="继续帮我检索这个问题。"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_limit_1",
                        "name": "search_docs",
                        "args": {"query": "test"},
                    }
                ],
            ),
        ]
    }

    out = _node_tool_limit(state)
    messages = out["messages"]

    assert len(messages) == 2
    assert messages[0].tool_call_id == "call_limit_1"
    assert "TOOL_LIMIT" in messages[0].content
    assert isinstance(messages[1], AIMessage)
    assert str(messages[1].content).strip()
