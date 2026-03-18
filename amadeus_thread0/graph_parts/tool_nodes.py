from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END
from langgraph.types import interrupt

from ..config import (
    ABLATE_WORLDLINE_MEMORY,
    CLAIM_REQUIRED_TOOLS,
    TOOLSET_UPGRADE_TTL_S,
    TOOL_CALLS_MAX,
    auto_approve_tool_names,
)
from .common import _now_ts, _safe_json
from .generation_profile import _ensure_response_structure
from .messages import _last_user_text, _latest_ai, _messages
from .memory_evolution import _auto_reconsolidate_after_tool
from .persona_runtime import _is_external_probe_context
from .runtime_services import _audit_jsonl, _get_store, _get_tool_bundle
from .state import ThreadState
from .tool_policies import MEMORY_WRITE_TOOLS, WORLDLINE_ABLATION_READ_TOOLS
from .tool_runtime import (
    _build_evidence_from_tool_result,
    _invoke_tool,
    _memory_guard_check,
)


def _available_tools_for_state(state: ThreadState) -> list[BaseTool]:
    if _is_external_probe_context(state=state):
        return []
    bundle = _get_tool_bundle()
    unlocks = dict(state.get("toolset_unlocks") or {})
    now = _now_ts()
    active = {k for k, exp in unlocks.items() if int(exp) > now}
    worldline_ablation = bool(ABLATE_WORLDLINE_MEMORY)

    tools: list[BaseTool] = []
    for t in bundle.base_tools:
        if t is not None:
            if worldline_ablation and str(getattr(t, "name", "") or "") in WORLDLINE_ABLATION_READ_TOOLS:
                continue
            tools.append(t)
    for t in bundle.extended_tools:
        if t is None:
            continue
        name = str(getattr(t, "name", "") or "")
        if worldline_ablation and name in WORLDLINE_ABLATION_READ_TOOLS:
            continue
        if name in active:
            tools.append(t)
    return tools


def _tool_limit_fallback_text(state: ThreadState) -> str:
    user_text = _last_user_text(_messages(state))
    if any(marker in user_text for marker in {"记得", "回忆", "上次", "之前", "继续"}):
        text = "我一下子还接不上刚才那段。你把最关键的那句再给我一下，我就顺着接回去。"
    elif any(marker in user_text for marker in {"检索", "搜索", "文档", "资料"}):
        text = "这轮我先停在这里。再继续盲查意义不大，你把关键词再收紧一点，我就继续往下翻。"
    else:
        text = "我先停在这里。再硬往下翻只会越说越乱，你把问题再收紧一点，我就继续。"
    return _ensure_response_structure(text.replace("\\n", "\n"), user_text)


def _node_tool_limit(state: ThreadState) -> dict[str, Any]:
    msgs = _messages(state)
    ai = _latest_ai(msgs)
    tool_msgs: list[ToolMessage] = []
    for tc in list(getattr(ai, "tool_calls", None) or []):
        tc_id = str(tc.get("id") or "")
        if not tc_id:
            continue
        payload = {
            "ok": False,
            "error": {
                "code": "TOOL_LIMIT",
                "message": f"tool calls exceeded max={int(TOOL_CALLS_MAX)} for this turn",
            },
        }
        tool_msgs.append(ToolMessage(content=_safe_json(payload), tool_call_id=tc_id))

    msg = AIMessage(content=_tool_limit_fallback_text(state))
    return {"messages": [*tool_msgs, msg]}


def _node_tool_gate(state: ThreadState) -> dict[str, Any]:
    msgs = _messages(state)
    ai = _latest_ai(msgs)
    if ai is None:
        return {"approval_actions": []}

    tool_calls = list(getattr(ai, "tool_calls", None) or [])
    if not tool_calls:
        return {"approval_actions": []}

    auto_set = auto_approve_tool_names()
    queued: list[dict[str, Any]] = []
    need_human: list[dict[str, Any]] = []
    order: list[str] = []

    for tc in tool_calls:
        tc_id = str(tc.get("id") or "")
        name = str(tc.get("name") or "")
        args = tc.get("args") if isinstance(tc.get("args"), dict) else {}
        if not tc_id:
            tc_id = f"call_{len(order)}"
        order.append(tc_id)
        row = {"id": tc_id, "name": name, "args": args}
        if name in auto_set:
            queued.append({**row, "action": "approve"})
        else:
            need_human.append(row)

    if need_human:
        source = (
            "memory"
            if any(str(x.get("name") or "") in MEMORY_WRITE_TOOLS for x in need_human)
            else "dialog"
        )
        resume = interrupt(
            {
                "kind": "tool_approval",
                "source": source,
                "tool_calls": need_human,
            }
        )

        decisions: list[dict[str, Any]] = []
        if isinstance(resume, dict):
            dec = resume.get("decisions")
            if isinstance(dec, list):
                decisions = [d for d in dec if isinstance(d, dict)]

        for i, row in enumerate(need_human):
            d = decisions[i] if i < len(decisions) else {"action": "reject"}
            action = str(d.get("action") or "reject").strip().lower()
            if action not in {"approve", "reject", "edit"}:
                action = "reject"
            edit_args = d.get("args") if isinstance(d.get("args"), dict) else row["args"]
            queued.append(
                {
                    **row,
                    "action": action,
                    "args": edit_args,
                    "reason": str(d.get("reason") or "").strip(),
                }
            )

    rank = {tc_id: idx for idx, tc_id in enumerate(order)}
    queued.sort(key=lambda x: rank.get(str(x.get("id")), 10_000))
    return {"approval_actions": queued}


def _tool_lookup(name: str) -> BaseTool | None:
    bundle = _get_tool_bundle()
    for t in [*bundle.base_tools, *bundle.extended_tools]:
        if t is None:
            continue
        if str(getattr(t, "name", "") or "") == name:
            return t
    return None


def _node_tool_execute(state: ThreadState) -> dict[str, Any]:
    store = _get_store()
    msgs = _messages(state)
    ai = _latest_ai(msgs)
    if ai is None:
        return {"approval_actions": []}

    tool_calls = list(getattr(ai, "tool_calls", None) or [])
    actions = list(state.get("approval_actions") or [])
    action_map = {str(a.get("id") or ""): a for a in actions}

    unlocks = dict(state.get("toolset_unlocks") or {})
    evidence_pack = list(state.get("evidence_pack") or [])
    external_tools = set(state.get("last_external_tools") or [])
    guard_checked = int(state.get("memory_guard_checked", 0) or 0)
    guard_blocked = int(state.get("memory_guard_blocked", 0) or 0)

    tool_msgs: list[ToolMessage] = []
    for tc in tool_calls:
        tc_id = str(tc.get("id") or "")
        name = str(tc.get("name") or "")
        args = tc.get("args") if isinstance(tc.get("args"), dict) else {}
        decision = action_map.get(tc_id, {"action": "reject", "reason": "no decision"})
        action = str(decision.get("action") or "reject").strip().lower()
        if action == "edit" and isinstance(decision.get("args"), dict):
            args = dict(decision.get("args"))

        record: dict[str, Any] = {
            "tool": name,
            "tool_call_id": tc_id,
            "action": action,
            "args": args,
        }

        if action == "reject":
            reason = str(decision.get("reason") or "rejected").strip()
            payload = {"ok": False, "error": {"code": "REJECTED", "message": reason}}
            tool_msgs.append(ToolMessage(content=_safe_json(payload), tool_call_id=tc_id))
            record["result"] = payload
            _audit_jsonl("tool_audit.jsonl", record)
            continue

        if name in MEMORY_WRITE_TOOLS:
            guard_checked += 1
        ok, reason = _memory_guard_check(name, args, store)
        if not ok:
            guard_blocked += 1
            payload = {"ok": False, "error": {"code": "MEMORY_GUARD_BLOCKED", "message": reason}}
            tool_msgs.append(ToolMessage(content=_safe_json(payload), tool_call_id=tc_id))
            record["result"] = payload
            _audit_jsonl("tool_audit.jsonl", record)
            continue

        tool = _tool_lookup(name)
        if tool is None:
            payload = {"ok": False, "error": {"code": "TOOL_NOT_FOUND", "message": name}}
            tool_msgs.append(ToolMessage(content=_safe_json(payload), tool_call_id=tc_id))
            record["result"] = payload
            _audit_jsonl("tool_audit.jsonl", record)
            continue

        try:
            result = _invoke_tool(tool, args)
            _auto_reconsolidate_after_tool(
                store,
                tool_name=name,
                args=args,
                result=result,
            )
            payload = {"ok": True, "data": result}
            tool_msgs.append(ToolMessage(content=_safe_json(payload), tool_call_id=tc_id))

            if name == "request_toolset_upgrade" and isinstance(result, dict):
                req = result.get("requested_tools")
                if isinstance(req, list):
                    exp = _now_ts() + int(TOOLSET_UPGRADE_TTL_S)
                    for x in req:
                        nm = str(x).strip()
                        if nm:
                            unlocks[nm] = exp

            ev = _build_evidence_from_tool_result(tool_name=name, result=result, store=store)
            if ev:
                evidence_pack.extend(ev)
                external_tools.add(name)
            elif name in CLAIM_REQUIRED_TOOLS:
                external_tools.add(name)

            record["result"] = payload
            _audit_jsonl("tool_audit.jsonl", record)
        except Exception as e:
            payload = {"ok": False, "error": {"code": "TOOL_EXEC_ERROR", "message": str(e)}}
            tool_msgs.append(ToolMessage(content=_safe_json(payload), tool_call_id=tc_id))
            record["result"] = payload
            _audit_jsonl("tool_audit.jsonl", record)

    return {
        "messages": tool_msgs,
        "approval_actions": [],
        "tool_round": int(state.get("tool_round", 0)) + 1,
        "toolset_unlocks": unlocks,
        "evidence_pack": evidence_pack[-50:],
        "last_external_tools": sorted(list(external_tools)),
        "memory_guard_checked": guard_checked,
        "memory_guard_blocked": guard_blocked,
    }


def _route_after_model(state: ThreadState) -> str:
    ai = _latest_ai(_messages(state))
    if ai is None:
        return END
    tool_calls = list(getattr(ai, "tool_calls", None) or [])
    if not tool_calls:
        return END
    if int(state.get("tool_round", 0)) >= int(TOOL_CALLS_MAX):
        return "tool_limit"
    return "tool_gate"
