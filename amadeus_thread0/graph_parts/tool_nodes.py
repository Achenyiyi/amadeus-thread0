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
from ..evolution_engine.reconsolidation import build_reconsolidation_snapshot
from .action_packets import (
    build_tool_action_packet,
    compact_artifact_identity,
    make_proposal_id,
    normalize_access_acquire_proposal,
    normalize_access_acquire_proposals,
    normalize_action_packets,
    normalize_artifact_context,
    risk_from_tool_name,
    upsert_action_packet,
)
from .autonomy_runtime import refresh_autonomy_intent_from_packets
from .digital_body_runtime import (
    derive_digital_body_state,
    merge_digital_body_hints,
    normalize_embodied_context,
    selected_access_proposal_resolved,
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
from ..utils.tools import (
    build_workspace_command_execution_spec,
    preview_workspace_command_execution,
    preview_workspace_mutation,
)

_AUTO_EXECUTABLE_ARTIFACT_INTENTS = {
    "artifact:reopen_file",
    "artifact:restore_file",
    "artifact:reattach_workspace",
    "artifact:reopen_page",
    "artifact:restore_page",
    "artifact:rerun_search",
}

_AUTO_EXECUTABLE_ACCESS_INTENTS = {
    "access:refresh_state",
}

_WORKSPACE_FILE_MUTATION_TOOLS = {
    "write_workspace_file": "write",
    "append_workspace_file": "append",
    "replace_workspace_text": "replace",
    "replace_workspace_lines": "replace_lines",
}

_WORKSPACE_FILE_MUTATION_INTENTS = {
    "artifact:write_file": "write_workspace_file",
    "artifact:append_file": "append_workspace_file",
    "artifact:replace_text": "replace_workspace_text",
    "artifact:replace_lines": "replace_workspace_lines",
}

_WORKSPACE_INSPECTION_TOOL_NAMES = {"inspect_workspace_path"}
_SOURCE_REF_INSPECTION_TOOL_NAMES = {"inspect_source_ref"}
_SOURCE_REF_COMPARISON_TOOL_NAMES = {"compare_source_refs"}


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
    action_packets = normalize_action_packets(state.get("action_packets"))
    action_trace = [dict(item) for item in (state.get("action_trace") if isinstance(state.get("action_trace"), list) else []) if isinstance(item, dict)]
    autonomy_block_reason = str(state.get("autonomy_block_reason") or "").strip()

    for tc in tool_calls:
        tc_id = str(tc.get("id") or "")
        name = str(tc.get("name") or "")
        args = tc.get("args") if isinstance(tc.get("args"), dict) else {}
        if not tc_id:
            tc_id = f"call_{len(order)}"
        proposal_id = _proposal_id_for_tool_call(tc_id, name, args)
        risk = risk_from_tool_name(name)
        order.append(tc_id)
        row = {"id": tc_id, "name": name, "args": args, "proposal_id": proposal_id}
        mutation_preview = preview_workspace_mutation(name, args)
        if mutation_preview:
            row["mutation_preview"] = mutation_preview
        execution_preview = preview_workspace_command_execution(name, args)
        if execution_preview:
            row["execution_preview"] = execution_preview
        execution_spec = build_workspace_command_execution_spec(args)
        if execution_spec:
            row["execution_spec"] = execution_spec
        if name in auto_set and risk != "external_mutation":
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
                "proposal_ids": [str(item.get("proposal_id") or "").strip() for item in need_human],
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
    pending_action_proposal: dict[str, Any] = {}
    for row in queued:
        name = str(row.get("name") or "")
        proposal_id = str(row.get("proposal_id") or "").strip()
        args = row.get("args") if isinstance(row.get("args"), dict) else {}
        action = str(row.get("action") or "").strip().lower()
        risk = risk_from_tool_name(name)
        packet_status = "approved" if action in {"approve", "edit"} else "rejected"
        packet = build_tool_action_packet(
            tool_name=name,
            proposal_id=proposal_id,
            args=args,
            action=action,
            status=packet_status,
            result_summary=str(row.get("reason") or ""),
            block_reason=str(row.get("reason") or "") if action == "reject" else "",
            mutation_preview=row.get("mutation_preview") if isinstance(row.get("mutation_preview"), dict) else None,
            execution_spec=row.get("execution_spec") if isinstance(row.get("execution_spec"), dict) else None,
            execution_preview=row.get("execution_preview") if isinstance(row.get("execution_preview"), dict) else None,
        )
        action_packets = upsert_action_packet(action_packets, packet)
        action_trace.append(
            _action_trace_entry(
                proposal_id=proposal_id,
                name=name,
                status=packet_status,
                event="tool_gate_decision",
                risk=risk,
                source="tool_gate",
                result_summary=str(row.get("reason") or ""),
                block_reason=str(row.get("reason") or "") if action == "reject" else "",
                requires_approval=risk != "read",
            )
        )
        if risk != "read" and packet_status in {"proposed", "awaiting_approval"}:
            pending_action_proposal = dict(packet)
        if action == "reject" and str(row.get("reason") or "").strip():
            autonomy_block_reason = str(row.get("reason") or "").strip()

    autonomy_intent = refresh_autonomy_intent_from_packets(
        state.get("autonomy_intent"),
        action_packets,
        current_event=state.get("current_event") if isinstance(state.get("current_event"), dict) else {},
        block_reason=autonomy_block_reason,
    )
    digital_body_state = derive_digital_body_state(
        current_event=state.get("current_event") if isinstance(state.get("current_event"), dict) else {},
        behavior_queue=state.get("behavior_queue"),
        action_packets=action_packets,
        interaction_carryover=state.get("interaction_carryover") if isinstance(state.get("interaction_carryover"), dict) else {},
        toolset_unlocks=state.get("toolset_unlocks") if isinstance(state.get("toolset_unlocks"), dict) else {},
        autonomy_block_reason=autonomy_block_reason,
        session_context=state.get("session_context") if isinstance(state.get("session_context"), dict) else {},
        last_external_tools=state.get("last_external_tools"),
    )
    return {
        "approval_actions": queued,
        "action_packets": action_packets,
        "pending_action_proposal": pending_action_proposal,
        "action_trace": action_trace,
        "autonomy_block_reason": autonomy_block_reason,
        "autonomy_intent": autonomy_intent,
        "digital_body_state": digital_body_state,
        "reconsolidation_snapshot": _rebuild_reconsolidation_with_autonomy(
            state,
            autonomy_intent=autonomy_intent,
            action_packets=action_packets,
            action_trace=action_trace,
            autonomy_block_reason=autonomy_block_reason,
            digital_body_state=digital_body_state,
        ),
    }


def _tool_lookup(name: str) -> BaseTool | None:
    bundle = _get_tool_bundle()
    for t in [*bundle.base_tools, *bundle.extended_tools]:
        if t is None:
            continue
        if str(getattr(t, "name", "") or "") == name:
            return t
    return None


def _tool_result_summary(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()[:220]
    if isinstance(result, dict):
        for key in ("message", "summary", "reason", "status", "title", "text"):
            text = str(result.get(key) or "").strip()
            if text:
                return text[:220]
        if "requested_tools" in result and isinstance(result.get("requested_tools"), list):
            requested = [str(item).strip() for item in result.get("requested_tools", []) if str(item or "").strip()]
            if requested:
                return ("requested_tools=" + ",".join(requested))[:220]
    return str(result).strip()[:220]


def _proposal_id_for_tool_call(tc_id: str, name: str, args: dict[str, Any]) -> str:
    return make_proposal_id(
        tc_id,
        name,
        str(args.get("target") or "").strip(),
        str(args.get("query") or "").strip(),
        str(args.get("reason") or "").strip(),
    )


def _artifact_execution_candidate(packet: dict[str, Any]) -> dict[str, Any]:
    row = dict(packet or {})
    intent = str(row.get("intent") or "").strip().lower()
    status = str(row.get("status") or "").strip().lower()
    risk = str(row.get("risk") or "").strip().lower()
    if intent not in _AUTO_EXECUTABLE_ARTIFACT_INTENTS:
        return {}
    if bool(row.get("requires_approval", False)) or risk not in {"", "read"}:
        return {}
    if status not in {"", "proposed", "queued", "approved"}:
        return {}
    proposal_id = str(row.get("proposal_id") or "").strip()
    if not proposal_id:
        return {}
    tool_name = str(row.get("tool_name") or "").strip().lower() or "reacquire_artifact"
    tool_args = dict(row.get("tool_args") or {}) if isinstance(row.get("tool_args"), dict) else {}
    steps = row.get("capability_steps") if isinstance(row.get("capability_steps"), list) else []
    primary_step = next((dict(item) for item in steps if isinstance(item, dict)), {})
    target = (
        str(tool_args.get("artifact_ref") or "").strip()
        or str(primary_step.get("target") or "").strip()
        or str(row.get("result_summary") or "").strip()
    )
    mode = str(tool_args.get("mode") or "").strip().lower() or intent.split(":", 1)[1]
    artifact_kind = (
        str(tool_args.get("artifact_kind") or "").strip().lower()
        or (
            "page"
            if mode in {"reopen_page", "restore_page"}
            else "workspace"
            if mode == "reattach_workspace"
            else "search_result"
            if mode == "rerun_search"
            else "file"
        )
    )
    label = str(tool_args.get("artifact_label") or "").strip() or target
    return {
        "candidate_kind": "artifact",
        "proposal_id": proposal_id,
        "intent": intent,
        "mode": mode,
        "artifact_kind": artifact_kind,
        "target": target,
        "label": label,
        "packet": row,
        "tool_name": tool_name,
        "tool_args": tool_args,
    }


def _access_execution_candidate(packet: dict[str, Any]) -> dict[str, Any]:
    row = dict(packet or {})
    intent = str(row.get("intent") or "").strip().lower()
    status = str(row.get("status") or "").strip().lower()
    risk = str(row.get("risk") or "").strip().lower()
    if intent not in _AUTO_EXECUTABLE_ACCESS_INTENTS:
        return {}
    if bool(row.get("requires_approval", False)) or risk not in {"", "read"}:
        return {}
    if status not in {"", "proposed", "queued", "approved"}:
        return {}
    proposal_id = str(row.get("proposal_id") or "").strip()
    if not proposal_id:
        return {}
    tool_name = str(row.get("tool_name") or "").strip().lower() or "refresh_access_state"
    tool_args = dict(row.get("tool_args") or {}) if isinstance(row.get("tool_args"), dict) else {}
    steps = row.get("capability_steps") if isinstance(row.get("capability_steps"), list) else []
    primary_step = next((dict(item) for item in steps if isinstance(item, dict)), {})
    target = str(primary_step.get("target") or "").strip() or "runtime_access"
    return {
        "candidate_kind": "access",
        "proposal_id": proposal_id,
        "intent": intent,
        "mode": "refresh_state",
        "target": target,
        "label": target,
        "packet": row,
        "tool_name": tool_name,
        "tool_args": tool_args,
    }


def _workspace_access_mutation_candidate(
    packet: dict[str, Any],
    *,
    session_context: dict[str, Any],
    current_event: dict[str, Any],
) -> dict[str, Any]:
    row = dict(packet or {})
    intent = str(row.get("intent") or "").strip().lower()
    status = str(row.get("status") or "").strip().lower()
    proposal_id = str(row.get("proposal_id") or "").strip()
    selected = normalize_access_acquire_proposal(row.get("selected_access_proposal"))
    if intent != "access:request_help" or status != "approved" or not proposal_id or not selected:
        return {}
    if str(selected.get("path_kind") or "").strip().lower() != "create_new":
        return {}
    if str(selected.get("mode") or "").strip().lower() != "operator_create_workspace":
        return {}
    tool_name = str(row.get("tool_name") or "").strip().lower() or "create_workspace_access"
    tool_args = dict(row.get("tool_args") or {}) if isinstance(row.get("tool_args"), dict) else {}
    if tool_args:
        hints = (
            dict(tool_args.get("access_hints") or {})
            if isinstance(tool_args.get("access_hints"), dict)
            else {}
        )
    else:
        hints = merge_digital_body_hints(
            session_context=session_context,
            current_event=current_event,
        )
        access_proposals = normalize_access_acquire_proposals(row.get("access_acquire_proposals"))
        if access_proposals:
            hints["access_acquire_proposals"] = access_proposals
        hints["selected_access_proposal"] = selected
        tool_args = {
            "workspace_name": str(selected.get("workspace_name") or row.get("workspace_name") or "").strip(),
            "access_hints": hints,
        }
    if not isinstance(hints.get("selected_access_proposal"), dict):
        hints["selected_access_proposal"] = selected
    if selected_access_proposal_resolved(hints=hints, proposal=selected):
        return {}
    return {
        "candidate_kind": "workspace_access_mutation",
        "proposal_id": proposal_id,
        "intent": intent,
        "mode": "create_workspace_access",
        "target": str(selected.get("target") or "filesystem").strip() or "filesystem",
        "label": str(selected.get("summary") or selected.get("operator_action") or "workspace").strip() or "workspace",
        "packet": row,
        "selected_access_proposal": selected,
        "tool_name": tool_name,
        "tool_args": tool_args,
    }


def _workspace_file_mutation_candidate(
    packet: dict[str, Any],
    *,
    session_context: dict[str, Any],
    current_event: dict[str, Any],
) -> dict[str, Any]:
    row = dict(packet or {})
    status = str(row.get("status") or "").strip().lower()
    proposal_id = str(row.get("proposal_id") or "").strip()
    if status != "approved" or not proposal_id:
        return {}

    tool_name = str(row.get("tool_name") or "").strip().lower()
    if tool_name not in _WORKSPACE_FILE_MUTATION_TOOLS:
        tool_name = _WORKSPACE_FILE_MUTATION_INTENTS.get(str(row.get("intent") or "").strip().lower(), "")
    if tool_name not in _WORKSPACE_FILE_MUTATION_TOOLS:
        return {}

    tool_args = dict(row.get("tool_args") or {}) if isinstance(row.get("tool_args"), dict) else {}
    steps = row.get("capability_steps") if isinstance(row.get("capability_steps"), list) else []
    primary_step = next((dict(item) for item in steps if isinstance(item, dict)), {})
    relative_path = str(tool_args.get("relative_path") or primary_step.get("target") or "").strip()
    if not relative_path:
        return {}

    mutation_mode = _WORKSPACE_FILE_MUTATION_TOOLS.get(tool_name, "")
    if mutation_mode in {"write", "append"} and "content" not in tool_args:
        return {}
    if mutation_mode == "replace" and not str(tool_args.get("old_text") or ""):
        return {}
    if mutation_mode == "replace_lines":
        try:
            start_line = int(tool_args.get("start_line") or 0)
            end_line = int(tool_args.get("end_line") or 0)
        except Exception:
            return {}
        if start_line <= 0 or end_line < start_line:
            return {}

    merged_hints = merge_digital_body_hints(
        session_context=session_context,
        current_event=current_event,
    )
    provided_hints = dict(tool_args.get("access_hints") or {}) if isinstance(tool_args.get("access_hints"), dict) else {}
    tool_args["access_hints"] = {**merged_hints, **provided_hints}

    return {
        "candidate_kind": "workspace_file_mutation",
        "proposal_id": proposal_id,
        "intent": str(row.get("intent") or "").strip().lower(),
        "mode": mutation_mode,
        "target": relative_path,
        "label": relative_path,
        "packet": row,
        "tool_name": tool_name,
        "tool_args": tool_args,
    }


def _workspace_path_inspection_candidate(
    packet: dict[str, Any],
    *,
    session_context: dict[str, Any],
    current_event: dict[str, Any],
) -> dict[str, Any]:
    row = dict(packet or {})
    status = str(row.get("status") or "").strip().lower()
    risk = str(row.get("risk") or "").strip().lower()
    proposal_id = str(row.get("proposal_id") or "").strip()
    if bool(row.get("requires_approval", False)) or risk not in {"", "read"}:
        return {}
    if status not in {"", "proposed", "queued", "approved"} or not proposal_id:
        return {}

    tool_name = str(row.get("tool_name") or "").strip().lower()
    if tool_name not in _WORKSPACE_INSPECTION_TOOL_NAMES:
        if str(row.get("intent") or "").strip().lower() != "artifact:inspect_path":
            return {}
        tool_name = "inspect_workspace_path"

    tool_args = dict(row.get("tool_args") or {}) if isinstance(row.get("tool_args"), dict) else {}
    steps = row.get("capability_steps") if isinstance(row.get("capability_steps"), list) else []
    primary_step = next((dict(item) for item in steps if isinstance(item, dict)), {})
    relative_path = str(tool_args.get("relative_path") or primary_step.get("target") or ".").strip() or "."
    merged_hints = merge_digital_body_hints(
        session_context=session_context,
        current_event=current_event,
    )
    provided_hints = dict(tool_args.get("access_hints") or {}) if isinstance(tool_args.get("access_hints"), dict) else {}
    tool_args["access_hints"] = {**merged_hints, **provided_hints}
    tool_args["relative_path"] = relative_path

    return {
        "candidate_kind": "workspace_path_inspection",
        "proposal_id": proposal_id,
        "intent": str(row.get("intent") or "").strip().lower(),
        "mode": "inspect_workspace_path",
        "target": relative_path,
        "label": relative_path,
        "packet": row,
        "tool_name": tool_name,
        "tool_args": tool_args,
    }


def _source_ref_inspection_candidate(
    packet: dict[str, Any],
    *,
    session_context: dict[str, Any],
    current_event: dict[str, Any],
) -> dict[str, Any]:
    row = dict(packet or {})
    status = str(row.get("status") or "").strip().lower()
    risk = str(row.get("risk") or "").strip().lower()
    proposal_id = str(row.get("proposal_id") or "").strip()
    if bool(row.get("requires_approval", False)) or risk not in {"", "read"}:
        return {}
    if status not in {"", "proposed", "queued", "approved"} or not proposal_id:
        return {}

    tool_name = str(row.get("tool_name") or "").strip().lower()
    if tool_name not in _SOURCE_REF_INSPECTION_TOOL_NAMES:
        if str(row.get("intent") or "").strip().lower() != "artifact:inspect_source_ref":
            return {}
        tool_name = "inspect_source_ref"

    tool_args = dict(row.get("tool_args") or {}) if isinstance(row.get("tool_args"), dict) else {}
    steps = row.get("capability_steps") if isinstance(row.get("capability_steps"), list) else []
    primary_step = next((dict(item) for item in steps if isinstance(item, dict)), {})
    merged_hints = merge_digital_body_hints(
        session_context=session_context,
        current_event=current_event,
    )
    provided_hints = dict(tool_args.get("access_hints") or {}) if isinstance(tool_args.get("access_hints"), dict) else {}
    tool_args["access_hints"] = {**merged_hints, **provided_hints}
    if not str(tool_args.get("artifact_ref") or "").strip():
        artifact_ref = str(primary_step.get("target") or row.get("result_summary") or "").strip()
        if artifact_ref:
            tool_args["artifact_ref"] = artifact_ref
    if not str(tool_args.get("artifact_label") or "").strip():
        artifact_label = str(primary_step.get("note") or "").strip()
        if artifact_label:
            tool_args["artifact_label"] = artifact_label

    target = str(tool_args.get("artifact_ref") or tool_args.get("artifact_label") or "").strip() or "saved-source"
    return {
        "candidate_kind": "source_ref_inspection",
        "proposal_id": proposal_id,
        "intent": str(row.get("intent") or "").strip().lower(),
        "mode": "inspect_source_ref",
        "target": target,
        "label": target,
        "packet": row,
        "tool_name": tool_name,
        "tool_args": tool_args,
    }


def _source_ref_comparison_candidate(
    packet: dict[str, Any],
    *,
    session_context: dict[str, Any],
    current_event: dict[str, Any],
) -> dict[str, Any]:
    row = dict(packet or {})
    status = str(row.get("status") or "").strip().lower()
    risk = str(row.get("risk") or "").strip().lower()
    proposal_id = str(row.get("proposal_id") or "").strip()
    if bool(row.get("requires_approval", False)) or risk not in {"", "read"}:
        return {}
    if status not in {"", "proposed", "queued", "approved"} or not proposal_id:
        return {}

    tool_name = str(row.get("tool_name") or "").strip().lower()
    if tool_name not in _SOURCE_REF_COMPARISON_TOOL_NAMES:
        if str(row.get("intent") or "").strip().lower() != "artifact:compare_source_refs":
            return {}
        tool_name = "compare_source_refs"

    tool_args = dict(row.get("tool_args") or {}) if isinstance(row.get("tool_args"), dict) else {}
    merged_hints = merge_digital_body_hints(
        session_context=session_context,
        current_event=current_event,
    )
    provided_hints = dict(tool_args.get("access_hints") or {}) if isinstance(tool_args.get("access_hints"), dict) else {}
    tool_args["access_hints"] = {**merged_hints, **provided_hints}
    source_ref_ids = [
        int(item)
        for item in (
            tool_args.get("source_ref_ids")
            if isinstance(tool_args.get("source_ref_ids"), list)
            else tool_args.get("access_hints", {}).get("artifact_source_ref_ids")
            if isinstance(tool_args.get("access_hints"), dict)
            else []
        )
        if str(item or "").strip().isdigit()
    ]
    if int(tool_args.get("source_ref_id") or 0) <= 0 and source_ref_ids:
        tool_args["source_ref_id"] = int(source_ref_ids[0])
    if int(tool_args.get("compare_source_ref_id") or 0) <= 0 and len(source_ref_ids) <= 2:
        for item in source_ref_ids:
            if item > 0 and item != int(tool_args.get("source_ref_id") or 0):
                tool_args["compare_source_ref_id"] = item
                break
    if int(tool_args.get("source_ref_id") or 0) <= 0:
        return {}

    compare_target = int(tool_args.get("compare_source_ref_id") or 0)
    target = (
        f"source_ref:{int(tool_args['source_ref_id'])}<->source_ref:{compare_target}"
        if compare_target > 0
        else f"source_ref:{int(tool_args['source_ref_id'])}<->candidate_set"
    )
    return {
        "candidate_kind": "source_ref_comparison",
        "proposal_id": proposal_id,
        "intent": str(row.get("intent") or "").strip().lower(),
        "mode": "compare_source_refs",
        "target": target,
        "label": target,
        "packet": row,
        "tool_name": tool_name,
        "tool_args": tool_args,
    }


def _first_autonomy_execution_candidate(state: ThreadState) -> dict[str, Any]:
    packets = normalize_action_packets(state.get("action_packets"))
    session_context = state.get("session_context") if isinstance(state.get("session_context"), dict) else {}
    current_event = state.get("current_event") if isinstance(state.get("current_event"), dict) else {}
    for packet in packets:
        candidate = _artifact_execution_candidate(packet)
        if candidate:
            return candidate
        candidate = _access_execution_candidate(packet)
        if candidate:
            return candidate
        candidate = _workspace_access_mutation_candidate(
            packet,
            session_context=session_context,
            current_event=current_event,
        )
        if candidate:
            return candidate
        candidate = _workspace_file_mutation_candidate(
            packet,
            session_context=session_context,
            current_event=current_event,
        )
        if candidate:
            return candidate
        candidate = _workspace_path_inspection_candidate(
            packet,
            session_context=session_context,
            current_event=current_event,
        )
        if candidate:
            return candidate
        candidate = _source_ref_inspection_candidate(
            packet,
            session_context=session_context,
            current_event=current_event,
        )
        if candidate:
            return candidate
        candidate = _source_ref_comparison_candidate(
            packet,
            session_context=session_context,
            current_event=current_event,
        )
        if candidate:
            return candidate
    return {}


def _has_direct_autonomy_execution_candidate(state: ThreadState) -> bool:
    return bool(_first_autonomy_execution_candidate(state))


def _action_trace_entry(
    *,
    proposal_id: str,
    name: str,
    status: str,
    event: str,
    risk: str,
    source: str,
    result_summary: str = "",
    block_reason: str = "",
    requires_approval: bool = False,
) -> dict[str, Any]:
    return {
        "proposal_id": proposal_id,
        "intent": "toolset_upgrade_proposal" if name == "request_toolset_upgrade" else f"tool:{str(name or '').strip().lower()}",
        "origin": "capability_upgrade" if name == "request_toolset_upgrade" else "motive_goal",
        "status": str(status or "").strip().lower(),
        "event": str(event or "").strip().lower(),
        "risk": str(risk or "").strip().lower(),
        "source": source,
        "result_summary": str(result_summary or "").strip()[:220],
        "block_reason": str(block_reason or "").strip()[:220],
        "requires_approval": bool(requires_approval),
    }


def _artifact_trace_entry(
    *,
    proposal_id: str,
    intent: str,
    origin: str,
    status: str,
    event: str,
    source: str,
    result_summary: str = "",
    block_reason: str = "",
) -> dict[str, Any]:
    return {
        "proposal_id": str(proposal_id or "").strip(),
        "intent": str(intent or "").strip().lower(),
        "origin": str(origin or "").strip().lower() or "motive_goal",
        "status": str(status or "").strip().lower(),
        "event": str(event or "").strip().lower(),
        "risk": "read",
        "source": str(source or "").strip().lower(),
        "result_summary": str(result_summary or "").strip()[:220],
        "block_reason": str(block_reason or "").strip()[:220],
        "requires_approval": False,
    }


def _autonomy_execution_trace_entry(
    *,
    packet: dict[str, Any],
    status: str,
    event: str,
    source: str,
    result_summary: str = "",
    block_reason: str = "",
) -> dict[str, Any]:
    row = dict(packet or {})
    return {
        "proposal_id": str(row.get("proposal_id") or "").strip(),
        "intent": str(row.get("intent") or "").strip().lower(),
        "origin": str(row.get("origin") or "").strip().lower() or "motive_goal",
        "status": str(status or "").strip().lower(),
        "event": str(event or "").strip().lower(),
        "risk": str(row.get("risk") or "").strip().lower() or "read",
        "source": str(source or "").strip().lower(),
        "result_summary": str(result_summary or "").strip()[:220],
        "block_reason": str(block_reason or "").strip()[:220],
        "requires_approval": bool(row.get("requires_approval", False)),
    }


def _artifact_context_from_reacquisition_result(
    *,
    result: Any,
    artifact_kind: str,
    artifact_target: str,
    artifact_label: str,
    mode: str,
) -> dict[str, Any]:
    row = dict(result) if isinstance(result, dict) else {}
    source_ref_ids = row.get("source_ref_ids") if isinstance(row.get("source_ref_ids"), list) else []
    carrier = "source_ref" if source_ref_ids or str(row.get("source_url") or "").strip() else "filesystem"
    return normalize_artifact_context(
        {
            "carrier": carrier,
            "artifact_kind": str(row.get("artifact_kind") or artifact_kind or "").strip().lower(),
            "artifact_ref": str(row.get("artifact_ref") or artifact_target or "").strip(),
            "artifact_label": str(row.get("artifact_label") or artifact_label or artifact_target or "").strip(),
            "workspace_root": str(row.get("workspace_root") or "").strip(),
            "reacquisition_mode": str(row.get("artifact_reacquisition_mode") or mode or "").strip().lower(),
            "preview": str(row.get("artifact_preview") or "").strip(),
            "preview_truncated": bool(row.get("artifact_preview_truncated", False)),
            "exists": bool(row.get("artifact_exists", False)),
            "size_bytes": row.get("artifact_size_bytes"),
            "updated_at": row.get("artifact_updated_at"),
            "source_ref_ids": source_ref_ids,
            "preferred_source_ref_id": row.get("preferred_source_ref_id"),
            "preferred_anchor_reason": row.get("preferred_anchor_reason"),
            "source_url": str(row.get("source_url") or "").strip(),
            "source_query": str(row.get("source_query") or "").strip(),
            "source_title": str(row.get("artifact_label") or artifact_label or "").strip(),
            "source_tool_name": str(row.get("tool_name") or "").strip(),
        }
    )


def _access_hints_from_refresh_result(result: Any) -> dict[str, Any]:
    row = dict(result) if isinstance(result, dict) else {}
    hints = dict(row.get("access_hints") or {}) if isinstance(row.get("access_hints"), dict) else {}
    access_state = dict(row.get("access_state") or {}) if isinstance(row.get("access_state"), dict) else {}
    for key in (
        "browser_session",
        "account_state",
        "cookie_state",
        "api_key_state",
        "quota_state",
        "filesystem_state",
        "sandbox_mode",
        "network_access",
        "session_continuity",
        "session_expires_in_s",
        "session_recovery_mode",
        "retry_after_s",
        "cooldown_scope",
        "missing_access",
        "requestable_access",
        "conditions",
    ):
        if key in access_state and access_state.get(key) not in (None, ""):
            hints[key] = access_state.get(key)
    if "conditions" in hints and "constraints" not in hints:
        hints["constraints"] = hints.pop("conditions")
    return hints


def _access_packet_fields_from_tool_result(result: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    row = dict(result) if isinstance(result, dict) else {}
    access_hints = dict(row.get("access_hints") or {}) if isinstance(row.get("access_hints"), dict) else {}
    access_state = dict(row.get("access_state") or {}) if isinstance(row.get("access_state"), dict) else {}
    access_acquire_proposals = access_state.get("access_acquire_proposals")
    if not isinstance(access_acquire_proposals, list):
        access_acquire_proposals = access_hints.get("access_acquire_proposals")
    selected_access_proposal = access_state.get("selected_access_proposal")
    if not isinstance(selected_access_proposal, dict):
        selected_access_proposal = access_hints.get("selected_access_proposal")
    return (
        normalize_access_acquire_proposals(access_acquire_proposals),
        normalize_access_acquire_proposal(selected_access_proposal),
    )


def _artifact_context_from_tool_result(result: Any) -> dict[str, Any]:
    row = dict(result) if isinstance(result, dict) else {}
    return normalize_artifact_context(row.get("artifact_context"))


def _execution_preview_from_tool_result(result: Any) -> dict[str, Any]:
    row = dict(result) if isinstance(result, dict) else {}
    preview = row.get("execution_preview")
    return dict(preview) if isinstance(preview, dict) else {}


def _execution_spec_from_tool_result(result: Any) -> dict[str, Any]:
    row = dict(result) if isinstance(result, dict) else {}
    spec = row.get("execution_spec")
    return dict(spec) if isinstance(spec, dict) else {}


def _execution_result_from_tool_result(result: Any) -> dict[str, Any]:
    row = dict(result) if isinstance(result, dict) else {}
    execution_result = row.get("execution_result")
    return dict(execution_result) if isinstance(execution_result, dict) else {}


def _artifact_hints_from_tool_result(result: Any) -> dict[str, Any]:
    row = dict(result) if isinstance(result, dict) else {}
    hints = dict(row.get("access_hints") or {}) if isinstance(row.get("access_hints"), dict) else {}
    artifact_context = _artifact_context_from_tool_result(result)
    if not artifact_context:
        return hints

    artifact_identity = compact_artifact_identity(artifact_context)
    artifact_kind = str(artifact_context.get("artifact_kind") or "").strip().lower()
    artifact_ref = str(artifact_context.get("artifact_ref") or "").strip()
    artifact_label = (
        str(artifact_context.get("artifact_label") or "").strip()
        or str(artifact_context.get("source_title") or "").strip()
        or artifact_ref
    )
    artifact_continuity = "attached" if bool(artifact_context.get("exists", True)) else "missing"
    hints.update(
        {
            "artifact_continuity": artifact_continuity,
            "active_artifact_kind": artifact_kind,
            "active_artifact_ref": artifact_ref,
            "active_artifact_label": artifact_label[:160],
            "artifact_age_s": 0,
            "artifact_reacquisition_mode": str(artifact_context.get("reacquisition_mode") or "").strip().lower(),
        }
    )
    workspace_root = str(artifact_context.get("workspace_root") or "").strip()
    if workspace_root:
        hints["workspace_root"] = workspace_root
    if artifact_identity:
        hints.update(artifact_identity)

    world_surfaces = [
        str(item).strip().lower()
        for item in (hints.get("world_surfaces") if isinstance(hints.get("world_surfaces"), list) else [])
        if str(item or "").strip()
    ]
    carrier = str(artifact_context.get("carrier") or "").strip().lower()
    if carrier == "filesystem":
        if "filesystem" not in world_surfaces:
            world_surfaces.append("filesystem")
    elif carrier == "source_ref":
        for surface in ("source_ref", "browser"):
            if surface not in world_surfaces:
                world_surfaces.append(surface)
    if world_surfaces:
        hints["world_surfaces"] = world_surfaces[:12]
    return hints


def _rebuild_reconsolidation_with_autonomy(
    state: ThreadState,
    *,
    autonomy_intent: dict[str, Any],
    action_packets: list[dict[str, Any]],
    action_trace: list[dict[str, Any]],
    autonomy_block_reason: str,
    digital_body_state: dict[str, Any],
) -> dict[str, Any]:
    return build_reconsolidation_snapshot(
        current_event=state.get("current_event") if isinstance(state.get("current_event"), dict) else {},
        appraisal=state.get("turn_appraisal") if isinstance(state.get("turn_appraisal"), dict) else {},
        world_model_state=state.get("world_model_state") if isinstance(state.get("world_model_state"), dict) else {},
        semantic_narrative_profile=state.get("semantic_narrative_profile")
        if isinstance(state.get("semantic_narrative_profile"), dict)
        else {},
        latent_state=state.get("evolution_state") if isinstance(state.get("evolution_state"), dict) else {},
        emotion_state=state.get("emotion_state") if isinstance(state.get("emotion_state"), dict) else {},
        bond_state=state.get("bond_state") if isinstance(state.get("bond_state"), dict) else {},
        counterpart_assessment=state.get("counterpart_assessment")
        if isinstance(state.get("counterpart_assessment"), dict)
        else {},
        behavior_action=state.get("behavior_action") if isinstance(state.get("behavior_action"), dict) else {},
        behavior_plan=state.get("behavior_plan") if isinstance(state.get("behavior_plan"), dict) else {},
        interaction_carryover=state.get("interaction_carryover") if isinstance(state.get("interaction_carryover"), dict) else {},
        agenda_lifecycle_residue=state.get("agenda_lifecycle_residue")
        if isinstance(state.get("agenda_lifecycle_residue"), dict)
        else {},
        autonomy_intent=autonomy_intent,
        action_packets=action_packets,
        action_trace=action_trace,
        autonomy_block_reason=autonomy_block_reason,
        digital_body_state=digital_body_state,
    )


def _node_autonomy_execute(state: ThreadState) -> dict[str, Any]:
    candidate = _first_autonomy_execution_candidate(state)
    if not candidate:
        return {}

    candidate_kind = str(candidate.get("candidate_kind") or "").strip().lower()
    proposal_id = str(candidate.get("proposal_id") or "").strip()
    intent = str(candidate.get("intent") or "").strip().lower()
    mode = str(candidate.get("mode") or "").strip().lower()
    target = str(candidate.get("target") or "").strip()
    label = str(candidate.get("label") or target).strip()
    packet = dict(candidate.get("packet") or {})
    origin = str(packet.get("origin") or "").strip().lower() or "motive_goal"

    if candidate_kind == "artifact":
        tool_name = str(candidate.get("tool_name") or "").strip().lower() or "reacquire_artifact"
    elif candidate_kind == "workspace_access_mutation":
        tool_name = str(candidate.get("tool_name") or "").strip().lower() or "create_workspace_access"
    elif candidate_kind == "workspace_file_mutation":
        tool_name = str(candidate.get("tool_name") or "").strip().lower()
    elif candidate_kind == "workspace_path_inspection":
        tool_name = str(candidate.get("tool_name") or "").strip().lower() or "inspect_workspace_path"
    else:
        tool_name = str(candidate.get("tool_name") or "").strip().lower() or "refresh_access_state"
    tool = _tool_lookup(tool_name)
    action_packets = normalize_action_packets(state.get("action_packets"))
    action_trace = [
        dict(item)
        for item in (state.get("action_trace") if isinstance(state.get("action_trace"), list) else [])
        if isinstance(item, dict)
    ]
    evidence_pack = list(state.get("evidence_pack") or [])
    session_context = dict(state.get("session_context") or {}) if isinstance(state.get("session_context"), dict) else {}
    autonomy_block_reason = ""

    if tool is None:
        reason = tool_name
        action_packets = upsert_action_packet(
            action_packets,
            {
                **packet,
                "status": "blocked",
                "result_summary": reason,
                "block_reason": reason,
                "writeback_ready": False,
            },
        )
        action_trace.append(
            _autonomy_execution_trace_entry(
                packet=packet,
                status="blocked",
                event="tool_not_found",
                source="autonomy_execute",
                result_summary=reason,
                block_reason=reason,
            )
        )
        autonomy_block_reason = reason
        autonomy_intent = refresh_autonomy_intent_from_packets(
            state.get("autonomy_intent"),
            action_packets,
            current_event=state.get("current_event") if isinstance(state.get("current_event"), dict) else {},
            block_reason=autonomy_block_reason,
        )
        digital_body_state = derive_digital_body_state(
            current_event=state.get("current_event") if isinstance(state.get("current_event"), dict) else {},
            behavior_queue=state.get("behavior_queue"),
            action_packets=action_packets,
            interaction_carryover=state.get("interaction_carryover") if isinstance(state.get("interaction_carryover"), dict) else {},
            toolset_unlocks=state.get("toolset_unlocks") if isinstance(state.get("toolset_unlocks"), dict) else {},
            autonomy_block_reason=autonomy_block_reason,
            session_context=session_context,
            last_external_tools=state.get("last_external_tools"),
        )
        return {
            "action_packets": action_packets,
            "pending_action_proposal": {},
            "action_trace": action_trace,
            "autonomy_block_reason": autonomy_block_reason,
            "autonomy_intent": autonomy_intent,
            "digital_body_state": digital_body_state,
            "reconsolidation_snapshot": _rebuild_reconsolidation_with_autonomy(
                state,
                autonomy_intent=autonomy_intent,
                action_packets=action_packets,
                action_trace=action_trace,
                autonomy_block_reason=autonomy_block_reason,
                digital_body_state=digital_body_state,
            ),
        }

    if candidate_kind == "artifact":
        candidate_tool_args = dict(candidate.get("tool_args") or {}) if isinstance(candidate.get("tool_args"), dict) else {}
        carryover = dict(state.get("interaction_carryover") or {}) if isinstance(state.get("interaction_carryover"), dict) else {}
        carried_embodied = normalize_embodied_context(carryover.get("embodied_context"))
        merged_hints = merge_digital_body_hints(
            session_context=session_context,
            current_event=state.get("current_event") if isinstance(state.get("current_event"), dict) else {},
        )
        workspace_root = (
            str(candidate_tool_args.get("workspace_root") or "").strip()
            or str(merged_hints.get("workspace_root") or "").strip()
            or str(carried_embodied.get("workspace_root") or "").strip()
        )
        if candidate_tool_args:
            tool_args = candidate_tool_args
        else:
            tool_args = {
                "mode": mode,
                "artifact_kind": str(candidate.get("artifact_kind") or "").strip().lower(),
                "artifact_ref": target,
                "artifact_label": label,
            }
        if workspace_root and not str(tool_args.get("workspace_root") or "").strip():
            tool_args["workspace_root"] = workspace_root
    elif candidate_kind == "workspace_access_mutation":
        candidate_tool_args = dict(candidate.get("tool_args") or {}) if isinstance(candidate.get("tool_args"), dict) else {}
        if candidate_tool_args:
            tool_args = candidate_tool_args
        else:
            tool_args = {
                "access_hints": merge_digital_body_hints(
                    session_context=session_context,
                    current_event=state.get("current_event") if isinstance(state.get("current_event"), dict) else {},
                ),
                "workspace_name": str(candidate.get("workspace_name") or "").strip(),
            }
    elif candidate_kind == "workspace_file_mutation":
        tool_args = dict(candidate.get("tool_args") or {}) if isinstance(candidate.get("tool_args"), dict) else {}
    elif candidate_kind == "workspace_path_inspection":
        candidate_tool_args = dict(candidate.get("tool_args") or {}) if isinstance(candidate.get("tool_args"), dict) else {}
        if candidate_tool_args:
            tool_args = candidate_tool_args
        else:
            tool_args = {
                "relative_path": target or ".",
                "access_hints": merge_digital_body_hints(
                    session_context=session_context,
                    current_event=state.get("current_event") if isinstance(state.get("current_event"), dict) else {},
                ),
            }
    else:
        candidate_tool_args = dict(candidate.get("tool_args") or {}) if isinstance(candidate.get("tool_args"), dict) else {}
        if candidate_tool_args:
            tool_args = candidate_tool_args
        else:
            tool_args = {
                "access_hints": merge_digital_body_hints(
                    session_context=session_context,
                    current_event=state.get("current_event") if isinstance(state.get("current_event"), dict) else {},
                )
            }
    tool_call_id = f"auto-{proposal_id}"
    synthetic_ai = AIMessage(
        content="",
        tool_calls=[{"id": tool_call_id, "name": tool_name, "args": dict(tool_args)}],
    )
    messages: list[Any] = [synthetic_ai]
    action_packets = upsert_action_packet(
        action_packets,
        {
            **packet,
            "status": "executing",
            "tool_name": tool_name or str(packet.get("tool_name") or "").strip(),
            "tool_args": tool_args,
            "result_summary": "",
            "block_reason": "",
            "writeback_ready": False,
        },
    )
    action_trace.append(
        _autonomy_execution_trace_entry(
            packet=packet,
            status="executing",
            event="started",
            source="autonomy_execute",
        )
    )

    try:
        result = _invoke_tool(tool, tool_args)
        payload = {"ok": True, "data": result}
        messages.append(ToolMessage(content=_safe_json(payload), tool_call_id=tool_call_id))
        result_summary = _tool_result_summary(result)
        packet_update = {
            **packet,
            "status": "completed",
            "tool_name": tool_name or str(packet.get("tool_name") or "").strip(),
            "tool_args": tool_args,
            "result_summary": result_summary,
            "block_reason": "",
            "writeback_ready": True,
        }
        hints = dict(session_context.get("digital_body_hints") or {}) if isinstance(session_context.get("digital_body_hints"), dict) else {}
        if candidate_kind == "artifact":
            artifact_kind = str(candidate.get("artifact_kind") or "").strip().lower()
            artifact_context = _artifact_context_from_reacquisition_result(
                result=result,
                artifact_kind=artifact_kind,
                artifact_target=target,
                artifact_label=label,
                mode=mode,
            )
            artifact_identity = compact_artifact_identity(artifact_context)
            packet_update["artifact_context"] = artifact_context
            hints.update(
                {
                    "artifact_continuity": str((result or {}).get("artifact_continuity") or "attached"),
                    "active_artifact_kind": str((result or {}).get("artifact_kind") or artifact_kind),
                    "active_artifact_ref": str((result or {}).get("artifact_ref") or target),
                    "active_artifact_label": str((result or {}).get("artifact_label") or label),
                    "artifact_age_s": 0,
                    "artifact_reacquisition_mode": mode,
                    "artifact_carrier": str(artifact_identity.get("artifact_carrier") or ""),
                    "artifact_source_ref_ids": list(artifact_identity.get("artifact_source_ref_ids") or []),
                    "preferred_source_ref_id": artifact_identity.get("preferred_source_ref_id"),
                    "preferred_anchor_reason": str(artifact_identity.get("preferred_anchor_reason") or ""),
                    "artifact_source_url": str(artifact_identity.get("artifact_source_url") or ""),
                    "artifact_source_query": str(artifact_identity.get("artifact_source_query") or ""),
                    "artifact_source_title": str(artifact_identity.get("artifact_source_title") or ""),
                    "artifact_source_tool_name": str(artifact_identity.get("artifact_source_tool_name") or ""),
                }
            )
            workspace_root = str((result or {}).get("workspace_root") or tool_args.get("workspace_root") or "").strip()
            if workspace_root:
                hints["workspace_root"] = workspace_root
            preview = str((result or {}).get("artifact_preview") or "").strip()
            if preview:
                evidence_pack.append(
                    {
                        "tool_name": "reacquire_artifact",
                        "title": str((result or {}).get("artifact_label") or label or target)[:140],
                        "snippet": preview[:1200],
                        "query": result_summary or f"artifact:{mode}",
                        "source_id": int(((result or {}).get("source_ref_ids") or [0])[0] or 0),
                        "url": str((result or {}).get("source_url") or (result or {}).get("artifact_ref") or ""),
                        "span_hint": "artifact_reacquired",
            }
                )
        else:
            hints.update(_access_hints_from_refresh_result(result))
            hints.update(_artifact_hints_from_tool_result(result))
            access_acquire_proposals, selected_access_proposal = _access_packet_fields_from_tool_result(result)
            hints["access_acquire_proposals"] = access_acquire_proposals
            if selected_access_proposal:
                hints["selected_access_proposal"] = selected_access_proposal
            else:
                hints.pop("selected_access_proposal", None)
            packet_update["access_acquire_proposals"] = access_acquire_proposals
            packet_update["selected_access_proposal"] = selected_access_proposal
            artifact_context = _artifact_context_from_tool_result(result)
            if artifact_context:
                packet_update["artifact_context"] = artifact_context
        session_context["digital_body_hints"] = hints
        action_packets = upsert_action_packet(action_packets, packet_update)
        action_trace.append(
            _autonomy_execution_trace_entry(
                packet=packet_update,
                status="completed",
                event="completed",
                source="autonomy_execute",
                result_summary=result_summary,
            )
        )
    except Exception as e:
        error_text = str(e)
        payload = {
            "ok": False,
            "error": {
                "code": (
                    "AUTO_ARTIFACT_EXEC_ERROR"
                    if candidate_kind == "artifact"
                    else "AUTO_WORKSPACE_MUTATION_EXEC_ERROR"
                    if candidate_kind == "workspace_file_mutation"
                    else "AUTO_ACCESS_EXEC_ERROR"
                ),
                "message": error_text,
            },
        }
        messages.append(ToolMessage(content=_safe_json(payload), tool_call_id=tool_call_id))
        action_packets = upsert_action_packet(
            action_packets,
            {
                **packet,
                "status": "blocked",
                "tool_name": tool_name or str(packet.get("tool_name") or "").strip(),
                "tool_args": tool_args,
                "result_summary": error_text,
                "block_reason": error_text,
                "writeback_ready": False,
            },
        )
        action_trace.append(
            _autonomy_execution_trace_entry(
                packet=packet,
                status="blocked",
                event="tool_error",
                source="autonomy_execute",
                result_summary=error_text,
                block_reason=error_text,
            )
        )
        autonomy_block_reason = error_text

    autonomy_intent = refresh_autonomy_intent_from_packets(
        state.get("autonomy_intent"),
        action_packets,
        current_event=state.get("current_event") if isinstance(state.get("current_event"), dict) else {},
        block_reason=autonomy_block_reason,
    )
    digital_body_state = derive_digital_body_state(
        current_event=state.get("current_event") if isinstance(state.get("current_event"), dict) else {},
        behavior_queue=state.get("behavior_queue"),
        action_packets=action_packets,
        interaction_carryover=state.get("interaction_carryover") if isinstance(state.get("interaction_carryover"), dict) else {},
        toolset_unlocks=state.get("toolset_unlocks") if isinstance(state.get("toolset_unlocks"), dict) else {},
        autonomy_block_reason=autonomy_block_reason,
        session_context=session_context,
        last_external_tools=state.get("last_external_tools"),
    )
    return {
        "messages": messages,
        "evidence_pack": evidence_pack[-50:],
        "action_packets": action_packets,
        "pending_action_proposal": {},
        "action_trace": action_trace,
        "autonomy_block_reason": autonomy_block_reason,
        "autonomy_intent": autonomy_intent,
        "digital_body_state": digital_body_state,
        "session_context": session_context,
        "reconsolidation_snapshot": _rebuild_reconsolidation_with_autonomy(
            state,
            autonomy_intent=autonomy_intent,
            action_packets=action_packets,
            action_trace=action_trace,
            autonomy_block_reason=autonomy_block_reason,
            digital_body_state=digital_body_state,
        ),
    }


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
    session_context = dict(state.get("session_context") or {}) if isinstance(state.get("session_context"), dict) else {}
    guard_checked = int(state.get("memory_guard_checked", 0) or 0)
    guard_blocked = int(state.get("memory_guard_blocked", 0) or 0)
    action_packets = normalize_action_packets(state.get("action_packets"))
    action_trace = [dict(item) for item in (state.get("action_trace") if isinstance(state.get("action_trace"), list) else []) if isinstance(item, dict)]
    autonomy_block_reason = str(state.get("autonomy_block_reason") or "").strip()

    tool_msgs: list[ToolMessage] = []
    for tc in tool_calls:
        tc_id = str(tc.get("id") or "")
        name = str(tc.get("name") or "")
        args = tc.get("args") if isinstance(tc.get("args"), dict) else {}
        decision = action_map.get(tc_id, {"action": "reject", "reason": "no decision"})
        action = str(decision.get("action") or "reject").strip().lower()
        if action == "edit" and isinstance(decision.get("args"), dict):
            args = dict(decision.get("args"))
        proposal_id = str(decision.get("proposal_id") or _proposal_id_for_tool_call(tc_id, name, args)).strip()
        risk = risk_from_tool_name(name)
        existing_packet = next(
            (
                dict(packet)
                for packet in action_packets
                if str(packet.get("proposal_id") or "").strip() == proposal_id
            ),
            {},
        )
        mutation_preview = (
            dict(existing_packet.get("mutation_preview") or {})
            if isinstance(existing_packet.get("mutation_preview"), dict)
            else {}
        )
        execution_spec = (
            dict(existing_packet.get("execution_spec") or {})
            if isinstance(existing_packet.get("execution_spec"), dict)
            else {}
        )
        execution_preview = (
            dict(existing_packet.get("execution_preview") or {})
            if isinstance(existing_packet.get("execution_preview"), dict)
            else {}
        )

        record: dict[str, Any] = {
            "tool": name,
            "tool_call_id": tc_id,
            "proposal_id": proposal_id,
            "action": action,
            "args": args,
        }

        if action == "reject":
            reason = str(decision.get("reason") or "rejected").strip()
            payload = {"ok": False, "error": {"code": "REJECTED", "message": reason}}
            tool_msgs.append(ToolMessage(content=_safe_json(payload), tool_call_id=tc_id))
            record["result"] = payload
            _audit_jsonl("tool_audit.jsonl", record)
            action_packets = upsert_action_packet(
                action_packets,
                build_tool_action_packet(
                    tool_name=name,
                    proposal_id=proposal_id,
                    args=args,
                    action=action,
                    status="rejected",
                    result_summary=reason,
                    block_reason=reason,
                    mutation_preview=mutation_preview,
                    execution_spec=execution_spec,
                    execution_preview=execution_preview,
                ),
            )
            action_trace.append(
                _action_trace_entry(
                    proposal_id=proposal_id,
                    name=name,
                    status="rejected",
                    event="rejected",
                    risk=risk,
                    source="tool_execute",
                    result_summary=reason,
                    block_reason=reason,
                    requires_approval=risk != "read",
                )
            )
            autonomy_block_reason = reason
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
            action_packets = upsert_action_packet(
                action_packets,
                build_tool_action_packet(
                    tool_name=name,
                    proposal_id=proposal_id,
                    args=args,
                    action=action,
                    status="blocked",
                    result_summary=reason,
                    block_reason=reason,
                    mutation_preview=mutation_preview,
                    execution_spec=execution_spec,
                    execution_preview=execution_preview,
                ),
            )
            action_trace.append(
                _action_trace_entry(
                    proposal_id=proposal_id,
                    name=name,
                    status="blocked",
                    event="memory_guard_blocked",
                    risk=risk,
                    source="tool_execute",
                    result_summary=reason,
                    block_reason=reason,
                    requires_approval=risk != "read",
                )
            )
            autonomy_block_reason = reason
            continue

        tool = _tool_lookup(name)
        if tool is None:
            payload = {"ok": False, "error": {"code": "TOOL_NOT_FOUND", "message": name}}
            tool_msgs.append(ToolMessage(content=_safe_json(payload), tool_call_id=tc_id))
            record["result"] = payload
            _audit_jsonl("tool_audit.jsonl", record)
            action_packets = upsert_action_packet(
                action_packets,
                build_tool_action_packet(
                    tool_name=name,
                    proposal_id=proposal_id,
                    args=args,
                    action=action,
                    status="blocked",
                    result_summary=name,
                    block_reason=name,
                    mutation_preview=mutation_preview,
                    execution_spec=execution_spec,
                    execution_preview=execution_preview,
                ),
            )
            action_trace.append(
                _action_trace_entry(
                    proposal_id=proposal_id,
                    name=name,
                    status="blocked",
                    event="tool_not_found",
                    risk=risk,
                    source="tool_execute",
                    result_summary=name,
                    block_reason=name,
                    requires_approval=risk != "read",
                )
            )
            autonomy_block_reason = name
            continue

        try:
            action_packets = upsert_action_packet(
                action_packets,
                build_tool_action_packet(
                    tool_name=name,
                    proposal_id=proposal_id,
                    args=args,
                    action=action,
                    status="executing",
                    mutation_preview=mutation_preview,
                    execution_spec=execution_spec,
                    execution_preview=execution_preview,
                ),
            )
            action_trace.append(
                _action_trace_entry(
                    proposal_id=proposal_id,
                    name=name,
                    status="executing",
                    event="started",
                    risk=risk,
                    source="tool_execute",
                    requires_approval=risk != "read",
                )
            )
            invoke_args = dict(args)
            if name == "execute_workspace_command" and proposal_id and not str(invoke_args.get("proposal_id") or "").strip():
                invoke_args["proposal_id"] = proposal_id
            result = _invoke_tool(tool, invoke_args)
            _auto_reconsolidate_after_tool(
                store,
                tool_name=name,
                args=invoke_args,
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
            result_summary = _tool_result_summary(result)
            tool_hints = _access_hints_from_refresh_result(result)
            artifact_hints = _artifact_hints_from_tool_result(result)
            access_acquire_proposals, selected_access_proposal = _access_packet_fields_from_tool_result(result)
            artifact_context = _artifact_context_from_tool_result(result)
            execution_spec_from_result = _execution_spec_from_tool_result(result)
            execution_preview_from_result = _execution_preview_from_tool_result(result)
            execution_result = _execution_result_from_tool_result(result)
            if tool_hints or artifact_hints:
                hints = dict(session_context.get("digital_body_hints") or {}) if isinstance(session_context.get("digital_body_hints"), dict) else {}
                hints.update(tool_hints)
                hints.update(artifact_hints)
                hints["access_acquire_proposals"] = access_acquire_proposals
                if selected_access_proposal:
                    hints["selected_access_proposal"] = selected_access_proposal
                else:
                    hints.pop("selected_access_proposal", None)
                session_context["digital_body_hints"] = hints
            packet_status = "completed"
            packet_event = "completed"
            block_reason = ""
            if str(execution_result.get("status") or "").strip().lower() == "blocked":
                packet_status = "blocked"
                packet_event = "tool_blocked"
                block_reason = str(execution_result.get("error_summary") or result_summary or "").strip()
            completed_packet = build_tool_action_packet(
                tool_name=name,
                proposal_id=proposal_id,
                args=args,
                action=action,
                status=packet_status,
                result_summary=result_summary,
                mutation_preview=mutation_preview,
                execution_spec=execution_spec_from_result or execution_spec,
                execution_preview=execution_preview_from_result or execution_preview,
                execution_result=execution_result,
            )
            if access_acquire_proposals:
                completed_packet["access_acquire_proposals"] = access_acquire_proposals
            if selected_access_proposal:
                completed_packet["selected_access_proposal"] = selected_access_proposal
            if artifact_context:
                completed_packet["artifact_context"] = artifact_context
            action_packets = upsert_action_packet(
                action_packets,
                completed_packet,
            )
            action_trace.append(
                _action_trace_entry(
                    proposal_id=proposal_id,
                    name=name,
                    status=packet_status,
                    event=packet_event,
                    risk=risk,
                    source="tool_execute",
                    result_summary=result_summary,
                    block_reason=block_reason,
                    requires_approval=risk != "read",
                )
            )
            if block_reason:
                autonomy_block_reason = block_reason
        except Exception as e:
            payload = {"ok": False, "error": {"code": "TOOL_EXEC_ERROR", "message": str(e)}}
            tool_msgs.append(ToolMessage(content=_safe_json(payload), tool_call_id=tc_id))
            record["result"] = payload
            _audit_jsonl("tool_audit.jsonl", record)
            error_text = str(e)
            action_packets = upsert_action_packet(
                action_packets,
                build_tool_action_packet(
                    tool_name=name,
                    proposal_id=proposal_id,
                    args=args,
                    action=action,
                    status="blocked",
                    result_summary=error_text,
                    block_reason=error_text,
                    mutation_preview=mutation_preview,
                    execution_spec=execution_spec,
                    execution_preview=execution_preview,
                ),
            )
            action_trace.append(
                _action_trace_entry(
                    proposal_id=proposal_id,
                    name=name,
                    status="blocked",
                    event="tool_error",
                    risk=risk,
                    source="tool_execute",
                    result_summary=error_text,
                    block_reason=error_text,
                    requires_approval=risk != "read",
                )
            )
            autonomy_block_reason = error_text

    pending_action_proposal = {}
    for packet in action_packets:
        if bool(packet.get("requires_approval", False)) and str(packet.get("status") or "").strip().lower() in {
            "proposed",
            "awaiting_approval",
        }:
            pending_action_proposal = dict(packet)
            break
    autonomy_intent = refresh_autonomy_intent_from_packets(
        state.get("autonomy_intent"),
        action_packets,
        current_event=state.get("current_event") if isinstance(state.get("current_event"), dict) else {},
        block_reason=autonomy_block_reason,
    )
    digital_body_state = derive_digital_body_state(
        current_event=state.get("current_event") if isinstance(state.get("current_event"), dict) else {},
        behavior_queue=state.get("behavior_queue"),
        action_packets=action_packets,
        interaction_carryover=state.get("interaction_carryover") if isinstance(state.get("interaction_carryover"), dict) else {},
        toolset_unlocks=unlocks,
        autonomy_block_reason=autonomy_block_reason,
        session_context=session_context,
        last_external_tools=sorted(list(external_tools)),
    )

    return {
        "messages": tool_msgs,
        "approval_actions": [],
        "tool_round": int(state.get("tool_round", 0)) + 1,
        "toolset_unlocks": unlocks,
        "evidence_pack": evidence_pack[-50:],
        "last_external_tools": sorted(list(external_tools)),
        "memory_guard_checked": guard_checked,
        "memory_guard_blocked": guard_blocked,
        "action_packets": action_packets,
        "pending_action_proposal": pending_action_proposal,
        "action_trace": action_trace,
        "autonomy_block_reason": autonomy_block_reason,
        "autonomy_intent": autonomy_intent,
        "digital_body_state": digital_body_state,
        "session_context": session_context,
        "reconsolidation_snapshot": _rebuild_reconsolidation_with_autonomy(
            state,
            autonomy_intent=autonomy_intent,
            action_packets=action_packets,
            action_trace=action_trace,
            autonomy_block_reason=autonomy_block_reason,
            digital_body_state=digital_body_state,
        ),
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
