from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from langgraph.types import Command

from ..evolution_engine.reconsolidation import build_reconsolidation_snapshot
from ..graph_parts.digital_body_runtime import (
    access_proposal_identity,
    access_proposal_progress,
    derive_access_acquire_proposals,
    derive_digital_body_state,
    enrich_access_acquire_proposal,
    normalize_access_acquire_proposal,
    prune_resolved_access_hints,
    select_access_acquire_proposal,
    selected_access_proposal_resolved,
)
from ..graph_parts.action_packets import build_tool_action_packet, normalize_action_packets
from ..graph_parts.autonomy_runtime import refresh_autonomy_intent_from_packets
from ..graph_parts import build_implicit_idle_event_override, build_implicit_idle_state_update
from ..graph_parts.relational_runtime import _prefer_refreshed_relationship_state, _worldline_focus
from ..memory_store import MemoryStore
from ..utils.cli_views import (
    build_behavior_queue_cli_summary,
    build_counterpart_assessment_cli_summary,
    build_evolution_cli_summary,
    build_proactive_continuity_cli_summary,
)
from .event_identity import resolve_readback_current_event
from .final_state import (
    resolve_agenda_lifecycle_residue,
    resolve_action_packets,
    resolve_action_trace,
    resolve_autonomy_block_reason,
    resolve_autonomy_intent,
    resolve_behavior_payloads,
    resolve_behavior_queue,
    resolve_counterpart_assessment,
    resolve_digital_body_consequence,
    resolve_digital_body_state,
    resolve_interaction_carryover,
    resolve_pending_action_proposal,
)


def _coerce_values(snapshot: Any) -> dict[str, Any]:
    values = getattr(snapshot, "values", {}) if snapshot is not None else {}
    return dict(values) if isinstance(values, dict) else {}


def _thread_id_from_config(config: dict[str, Any] | None, fallback: str) -> str:
    configurable = (config or {}).get("configurable") if isinstance(config, dict) else {}
    thread_id = str((configurable or {}).get("thread_id") or fallback).strip()
    return thread_id or fallback


def _normalized_graph_config(
    config: dict[str, Any] | None,
    *,
    fallback_thread_id: str,
    fallback_user_id: str | None = None,
) -> dict[str, Any]:
    normalized = dict(config) if isinstance(config, dict) else {}
    configurable = dict(normalized.get("configurable") or {}) if isinstance(normalized.get("configurable"), dict) else {}
    thread_id = str(configurable.get("thread_id") or fallback_thread_id).strip()
    configurable["thread_id"] = thread_id or fallback_thread_id
    if not str(configurable.get("user_id") or "").strip() and str(fallback_user_id or "").strip():
        configurable["user_id"] = str(fallback_user_id).strip()
    normalized["configurable"] = configurable
    return normalized


def _message_content(message: Any) -> str:
    return str(getattr(message, "content", "") or "").strip()


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _resolved_relationship_state(
    memory_store: MemoryStore,
    values: dict[str, Any] | None,
) -> dict[str, Any]:
    vals = values if isinstance(values, dict) else {}
    runtime_relationship = vals.get("relationship") if isinstance(vals.get("relationship"), dict) else {}
    persisted_relationship = memory_store.get_relationship()
    return _prefer_refreshed_relationship_state(runtime_relationship, persisted_relationship)


def _resolved_worldline_focus(
    memory_store: MemoryStore,
    values: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    vals = values if isinstance(values, dict) else {}
    if "worldline_focus" in vals and isinstance(vals.get("worldline_focus"), list):
        return list(vals.get("worldline_focus") or [])
    return _worldline_focus(memory_store)


def _resolved_readback_current_event(
    values: dict[str, Any] | None,
    *,
    thread_id: str,
) -> dict[str, Any]:
    vals = values if isinstance(values, dict) else {}
    session_context = vals.get("session_context") if isinstance(vals.get("session_context"), dict) else {}
    return resolve_readback_current_event(
        vals,
        thread_id=thread_id,
        session_context=session_context,
    )


def _state_final_text(values: dict[str, Any] | None) -> str:
    data = values if isinstance(values, dict) else {}
    final_text = str(data.get("final_text") or "").strip()
    if final_text:
        return final_text
    msgs = data.get("messages")
    if isinstance(msgs, list) and msgs:
        return _message_content(msgs[-1])
    return ""


def _payload_value(interrupt_payload: Any) -> dict[str, Any]:
    payload = getattr(interrupt_payload, "value", None)
    if payload is None and isinstance(interrupt_payload, dict):
        payload = interrupt_payload.get("value")
    return dict(payload or {}) if isinstance(payload, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _snapshot_has_pending_graph_interrupt(snapshot: Any) -> bool:
    next_items = getattr(snapshot, "next", None)
    if isinstance(next_items, tuple):
        next_items = list(next_items)
    return bool(next_items)


@dataclass
class StreamInvocationResult:
    values: dict[str, Any]
    streamed_text: str
    approval_request: ToolApprovalRequest | None = None


@dataclass
class ToolApprovalRequest:
    kind: str
    source: str
    tool_calls: list[dict[str, Any]]
    payload: dict[str, Any]


@dataclass
class EventRoundResult:
    values: dict[str, Any]
    final_text: str


def _approval_request_from_output(output: Any) -> ToolApprovalRequest | None:
    if not isinstance(output, dict):
        return None
    interrupts = output.get("__interrupt__")
    if isinstance(interrupts, tuple):
        interrupts = list(interrupts)
    if not isinstance(interrupts, list) or not interrupts:
        return None
    payload = _payload_value(interrupts[0])
    kind = str(payload.get("kind") or "").strip().lower()
    if kind != "tool_approval":
        return None
    tool_calls = payload.get("tool_calls")
    if not isinstance(tool_calls, list):
        tool_calls = []
    normalized_calls = [dict(item) for item in tool_calls if isinstance(item, dict)]
    return ToolApprovalRequest(
        kind=kind,
        source=str(payload.get("source") or "").strip().lower(),
        tool_calls=normalized_calls,
        payload=payload,
    )


_ACCESS_REQUEST_INTENT = "access:request_help"
_ACCESS_HINT_KEYS = {
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
    "constraints",
    "world_surfaces",
    "selected_access_proposal",
}


def _pending_access_request_packet(values: dict[str, Any] | None) -> dict[str, Any]:
    data = values if isinstance(values, dict) else {}
    packet = resolve_pending_action_proposal(
        pending_action_proposal=_dict_or_empty(data.get("pending_action_proposal")),
        action_packets=data.get("action_packets"),
        reconsolidation_snapshot=_dict_or_empty(data.get("reconsolidation_snapshot")),
    )
    if str(packet.get("intent") or "").strip().lower() != _ACCESS_REQUEST_INTENT:
        return {}
    return packet


def _approval_request_from_pending_access(values: dict[str, Any] | None) -> ToolApprovalRequest | None:
    data = values if isinstance(values, dict) else {}
    packet = _pending_access_request_packet(data)
    if not packet:
        return None
    digital_body = _resolved_digital_body(data)
    access_state = _dict_or_empty(digital_body.get("access_state"))
    access_acquire_proposals = (
        list(access_state.get("access_acquire_proposals") or [])
        if isinstance(access_state.get("access_acquire_proposals"), list)
        else []
    )
    if not access_acquire_proposals:
        access_acquire_proposals = (
            list(packet.get("access_acquire_proposals") or [])
            if isinstance(packet.get("access_acquire_proposals"), list)
            else []
        )
    if not access_acquire_proposals:
        access_acquire_proposals = derive_access_acquire_proposals(hints=access_state)
    selected_access_proposal = select_access_acquire_proposal(
        proposals=access_acquire_proposals,
        preferred=access_state.get("selected_access_proposal") if isinstance(access_state.get("selected_access_proposal"), dict) else packet.get("selected_access_proposal"),
    )
    payload = {
        "kind": "access_request",
        "source": "access",
        "proposal_id": str(packet.get("proposal_id") or "").strip(),
        "tool_calls": [
            {
                "name": "access_request_help",
                "proposal_id": str(packet.get("proposal_id") or "").strip(),
                "args": {
                    "requested_access": list(access_state.get("requestable_access") or []),
                    "missing_access": list(access_state.get("missing_access") or []),
                    "access_acquire_proposals": access_acquire_proposals,
                    "selected_access_proposal": selected_access_proposal,
                    "session_recovery_mode": str(access_state.get("session_recovery_mode") or ""),
                    "browser_session": str(access_state.get("browser_session") or ""),
                    "account_state": str(access_state.get("account_state") or ""),
                    "cookie_state": str(access_state.get("cookie_state") or ""),
                    "api_key_state": str(access_state.get("api_key_state") or ""),
                    "quota_state": str(access_state.get("quota_state") or ""),
                    "block_reason": str(access_state.get("block_reason") or ""),
                    "expected_effect": str(packet.get("expected_effect") or ""),
                    "access_updates": {},
                },
            }
        ],
    }
    return ToolApprovalRequest(
        kind="access_request",
        source="access",
        tool_calls=[dict(item) for item in payload["tool_calls"]],
        payload=payload,
    )


def _approval_trace_entry(
    *,
    proposal_id: str,
    tool_name: str,
    source: str,
    risk: str,
) -> dict[str, Any]:
    name = str(tool_name or "").strip()
    return {
        "proposal_id": str(proposal_id or "").strip(),
        "intent": "toolset_upgrade_proposal" if name == "request_toolset_upgrade" else f"tool:{name.lower()}",
        "origin": "capability_upgrade" if name == "request_toolset_upgrade" else "motive_goal",
        "status": "awaiting_approval",
        "event": "approval_requested",
        "risk": str(risk or "").strip().lower() or "read",
        "source": str(source or "").strip().lower() or "tool_gate",
        "result_summary": "",
        "block_reason": "",
        "requires_approval": True,
    }


def _merge_pending_approval_state(
    values: dict[str, Any] | None,
    approval_request: ToolApprovalRequest | None,
) -> dict[str, Any]:
    data = dict(values or {})
    if approval_request is None:
        return data
    if str(approval_request.kind or "").strip().lower() != "tool_approval":
        return data

    existing_packets = normalize_action_packets(data.get("action_packets"))
    existing_trace = [
        dict(item)
        for item in (_list_or_empty(data.get("action_trace")))
        if isinstance(item, dict)
    ]
    pending_packets: list[dict[str, Any]] = []
    pending_trace: list[dict[str, Any]] = []
    for tool_call in approval_request.tool_calls:
        if not isinstance(tool_call, dict):
            continue
        name = str(tool_call.get("name") or "").strip()
        proposal_id = str(tool_call.get("proposal_id") or "").strip()
        args = dict(tool_call.get("args") or {}) if isinstance(tool_call.get("args"), dict) else {}
        if not name or not proposal_id:
            continue
        packet = build_tool_action_packet(
            tool_name=name,
            proposal_id=proposal_id,
            args=args,
            status="awaiting_approval",
        )
        if not packet:
            continue
        pending_packets.append(packet)
        pending_trace.append(
            _approval_trace_entry(
                proposal_id=proposal_id,
                tool_name=name,
                source=approval_request.source,
                risk=str(packet.get("risk") or ""),
            )
        )

    if not pending_packets:
        return data

    pending_ids = {
        str(packet.get("proposal_id") or "").strip()
        for packet in pending_packets
        if str(packet.get("proposal_id") or "").strip()
    }
    merged_packets = list(pending_packets)
    merged_packets.extend(
        packet
        for packet in existing_packets
        if str(packet.get("proposal_id") or "").strip() not in pending_ids
    )
    existing_trace_keys = {
        (
            str(item.get("proposal_id") or "").strip(),
            str(item.get("event") or "").strip(),
            str(item.get("status") or "").strip(),
        )
        for item in existing_trace
    }
    for item in pending_trace:
        key = (
            str(item.get("proposal_id") or "").strip(),
            str(item.get("event") or "").strip(),
            str(item.get("status") or "").strip(),
        )
        if key not in existing_trace_keys:
            existing_trace.append(item)

    data["action_packets"] = merged_packets
    data["pending_action_proposal"] = dict(pending_packets[0])
    data["action_trace"] = existing_trace
    data["autonomy_intent"] = refresh_autonomy_intent_from_packets(
        data.get("autonomy_intent"),
        merged_packets,
        current_event=_dict_or_empty(data.get("current_event")),
        block_reason=str(data.get("autonomy_block_reason") or ""),
    )
    return data


def _normalize_access_updates(args: dict[str, Any] | None) -> dict[str, Any]:
    data = _dict_or_empty(args)
    raw_updates = data.get("access_updates")
    updates = _dict_or_empty(raw_updates) if isinstance(raw_updates, dict) else data
    normalized: dict[str, Any] = {}
    for key in _ACCESS_HINT_KEYS:
        if key not in updates:
            continue
        value = updates.get(key)
        if value is None:
            continue
        if key in {"missing_access", "requestable_access", "constraints", "world_surfaces"}:
            normalized[key] = [str(item).strip().lower() for item in _list_or_empty(value) if str(item or "").strip()]
        elif key == "selected_access_proposal":
            proposal = normalize_access_acquire_proposal(value)
            if proposal:
                normalized[key] = proposal
        else:
            normalized[key] = value
    return normalized


def _prune_resolved_access_lists(hints: dict[str, Any]) -> dict[str, Any]:
    return prune_resolved_access_hints(hints)


def _access_request_trace_entry(
    *,
    proposal_id: str,
    status: str,
    event: str,
    result_summary: str = "",
    block_reason: str = "",
) -> dict[str, Any]:
    return {
        "proposal_id": str(proposal_id or "").strip(),
        "intent": _ACCESS_REQUEST_INTENT,
        "origin": "counterpart_request",
        "status": str(status or "").strip().lower(),
        "event": str(event or "").strip().lower(),
        "risk": "external_mutation",
        "source": "access_resume",
        "result_summary": str(result_summary or "").strip()[:220],
        "block_reason": str(block_reason or "").strip()[:220],
        "requires_approval": True,
    }


def _apply_access_request_resolution(
    values: dict[str, Any] | None,
    decision: dict[str, Any] | None,
) -> dict[str, Any]:
    data = dict(values or {})
    packet = _pending_access_request_packet(data)
    if not packet:
        return data

    proposal_id = str(packet.get("proposal_id") or "").strip()
    action = str(_dict_or_empty(decision).get("action") or "reject").strip().lower()
    if action not in {"approve", "edit", "reject"}:
        action = "reject"
    decision_args = _normalize_access_updates(_dict_or_empty(decision).get("args"))
    decision_reason = str(_dict_or_empty(decision).get("reason") or "").strip()

    session_context = _dict_or_empty(data.get("session_context"))
    hints = dict(session_context.get("digital_body_hints") or {}) if isinstance(session_context.get("digital_body_hints"), dict) else {}
    if decision_args:
        hints.update(decision_args)
    hints = _prune_resolved_access_lists(hints)
    proposal_source = (
        list(hints.get("access_acquire_proposals") or [])
        if isinstance(hints.get("access_acquire_proposals"), list)
        else list(packet.get("access_acquire_proposals") or [])
        if isinstance(packet.get("access_acquire_proposals"), list)
        else []
    )
    selected_access_proposal = select_access_acquire_proposal(
        proposals=proposal_source,
        preferred=hints.get("selected_access_proposal") if isinstance(hints.get("selected_access_proposal"), dict) else packet.get("selected_access_proposal"),
    )
    proposal_progress = access_proposal_progress(hints=hints, proposal=selected_access_proposal)

    if action == "reject":
        packet_status = "rejected"
        result_summary = decision_reason or "access request rejected by operator"
        block_reason = result_summary
    elif decision_args:
        has_access_updates = any(
            key in decision_args
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
                "constraints",
                "world_surfaces",
            )
        )
        if has_access_updates and (not selected_access_proposal or selected_access_proposal_resolved(hints=hints, proposal=selected_access_proposal)):
            packet_status = "completed"
        else:
            packet_status = "approved"
        if packet_status == "completed":
            result_summary = decision_reason or "operator supplied access updates"
        elif has_access_updates and proposal_progress.get("partial", False):
            result_summary = decision_reason or (
                " / ".join(str(item) for item in proposal_progress.get("resolved_grants", [])[:2])
                + " 已经补回一部分，但这条访问路径还没完全接通。"
            )
        else:
            result_summary = decision_reason or (
                str(selected_access_proposal.get("summary") or "").strip()
                or "operator accepted the access acquisition path"
            )
        block_reason = ""
    else:
        packet_status = "approved"
        result_summary = decision_reason or (
            str(selected_access_proposal.get("summary") or "").strip()
            or "operator accepted the access acquisition path"
        )
        block_reason = ""

    hints["requested_help"] = False
    hints["primary_proposal_id"] = proposal_id
    hints["primary_status"] = packet_status
    hints["primary_origin"] = str(packet.get("origin") or "").strip().lower() or "counterpart_request"
    hints["primary_intent"] = _ACCESS_REQUEST_INTENT
    if packet_status == "rejected":
        hints.pop("selected_access_proposal", None)
    elif selected_access_proposal:
        hints["selected_access_proposal"] = selected_access_proposal
    if packet_status == "completed" and selected_access_proposal_resolved(hints=hints, proposal=selected_access_proposal):
        hints.pop("selected_access_proposal", None)
        hints["access_acquire_proposals"] = [
            proposal
            for proposal in list(hints.get("access_acquire_proposals") or [])
            if isinstance(proposal, dict) and access_proposal_identity(proposal) != access_proposal_identity(selected_access_proposal)
        ]
    selected_access_proposal = enrich_access_acquire_proposal(hints=hints, proposal=selected_access_proposal)
    session_context["digital_body_hints"] = hints

    action_packets = normalize_action_packets(data.get("action_packets"))
    updated_packets: list[dict[str, Any]] = []
    for row in action_packets:
        if str(row.get("proposal_id") or "").strip() == proposal_id:
            updated_packets.append(
                {
                    **row,
                    "status": packet_status,
                    "result_summary": result_summary,
                    "block_reason": block_reason,
                    "writeback_ready": packet_status == "completed",
                    "selected_access_proposal": selected_access_proposal,
                }
            )
        else:
            updated_packets.append(dict(row))

    action_trace = [dict(item) for item in _list_or_empty(data.get("action_trace")) if isinstance(item, dict)]
    action_trace.append(
        _access_request_trace_entry(
            proposal_id=proposal_id,
            status=packet_status,
            event=(
                "resolved_by_user"
                if packet_status == "completed"
                else "approved_by_user"
                if packet_status == "approved"
                else "rejected_by_user"
            ),
            result_summary=result_summary,
            block_reason=block_reason,
        )
    )

    autonomy_block_reason = block_reason if packet_status == "rejected" else ""
    autonomy_intent = refresh_autonomy_intent_from_packets(
        data.get("autonomy_intent"),
        updated_packets,
        current_event=_dict_or_empty(data.get("current_event")),
        block_reason=autonomy_block_reason,
    )
    digital_body_state = derive_digital_body_state(
        current_event=_dict_or_empty(data.get("current_event")),
        behavior_queue=data.get("behavior_queue") if isinstance(data.get("behavior_queue"), list) else data.get("behavior_agenda"),
        action_packets=updated_packets,
        interaction_carryover=_dict_or_empty(data.get("interaction_carryover")),
        toolset_unlocks=_dict_or_empty(data.get("toolset_unlocks")),
        autonomy_block_reason=autonomy_block_reason,
        session_context=session_context,
        last_external_tools=data.get("last_external_tools"),
    )
    reconsolidation_snapshot = build_reconsolidation_snapshot(
        current_event=_dict_or_empty(data.get("current_event")),
        appraisal=_dict_or_empty(data.get("turn_appraisal")),
        world_model_state=_dict_or_empty(data.get("world_model_state")),
        semantic_narrative_profile=_dict_or_empty(data.get("semantic_narrative_profile")),
        latent_state=_dict_or_empty(data.get("evolution_state")),
        emotion_state=_dict_or_empty(data.get("emotion_state")),
        bond_state=_dict_or_empty(data.get("bond_state")),
        counterpart_assessment=_dict_or_empty(data.get("counterpart_assessment")),
        behavior_action=_dict_or_empty(data.get("behavior_action")),
        behavior_plan=_dict_or_empty(data.get("behavior_plan")),
        interaction_carryover=_dict_or_empty(data.get("interaction_carryover")),
        agenda_lifecycle_residue=_dict_or_empty(data.get("agenda_lifecycle_residue")),
        autonomy_intent=autonomy_intent,
        action_packets=updated_packets,
        action_trace=action_trace,
        autonomy_block_reason=autonomy_block_reason,
        digital_body_state=digital_body_state,
    )
    return {
        **data,
        "session_context": session_context,
        "action_packets": updated_packets,
        "pending_action_proposal": {},
        "action_trace": action_trace,
        "autonomy_block_reason": autonomy_block_reason,
        "autonomy_intent": autonomy_intent,
        "digital_body_state": digital_body_state,
        "reconsolidation_snapshot": reconsolidation_snapshot,
    }


def _resolved_autonomy(values: dict[str, Any] | None) -> dict[str, Any]:
    data = values if isinstance(values, dict) else {}
    reconsolidation_snapshot = _dict_or_empty(data.get("reconsolidation_snapshot"))
    action_packets = resolve_action_packets(
        action_packets=data.get("action_packets"),
        reconsolidation_snapshot=reconsolidation_snapshot,
    )
    return {
        "intent": resolve_autonomy_intent(
            autonomy_intent=_dict_or_empty(data.get("autonomy_intent")),
            reconsolidation_snapshot=reconsolidation_snapshot,
            action_packets=action_packets,
            current_event=_dict_or_empty(data.get("current_event")),
            autonomy_block_reason=str(data.get("autonomy_block_reason") or ""),
        ),
        "action_packets": action_packets,
        "pending_approval": resolve_pending_action_proposal(
            pending_action_proposal=_dict_or_empty(data.get("pending_action_proposal")),
            action_packets=action_packets,
            reconsolidation_snapshot=reconsolidation_snapshot,
        ),
        "execution_trace": resolve_action_trace(
            action_trace=data.get("action_trace"),
            reconsolidation_snapshot=reconsolidation_snapshot,
        ),
        "block_reason": resolve_autonomy_block_reason(
            autonomy_block_reason=str(data.get("autonomy_block_reason") or ""),
            action_packets=action_packets,
            reconsolidation_snapshot=reconsolidation_snapshot,
        ),
    }


def _resolved_digital_body(values: dict[str, Any] | None) -> dict[str, Any]:
    data = values if isinstance(values, dict) else {}
    body = resolve_digital_body_state(
        digital_body_state=_dict_or_empty(data.get("digital_body_state")),
        reconsolidation_snapshot=_dict_or_empty(data.get("reconsolidation_snapshot")),
    )
    if body:
        return body
    return derive_digital_body_state(
        current_event=_dict_or_empty(data.get("current_event")),
        behavior_queue=data.get("behavior_queue") if isinstance(data.get("behavior_queue"), list) else data.get("behavior_agenda"),
        action_packets=data.get("action_packets"),
        interaction_carryover=_dict_or_empty(data.get("interaction_carryover")),
        toolset_unlocks=_dict_or_empty(data.get("toolset_unlocks")),
        autonomy_block_reason=str(data.get("autonomy_block_reason") or ""),
        session_context=_dict_or_empty(data.get("session_context")),
        last_external_tools=data.get("last_external_tools"),
    )


def _resolved_digital_body_consequence(
    values: dict[str, Any] | None,
    *,
    digital_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = values if isinstance(values, dict) else {}
    reconsolidation_snapshot = _dict_or_empty(data.get("reconsolidation_snapshot"))
    resolved_body = digital_body if isinstance(digital_body, dict) and digital_body else _resolved_digital_body(data)
    action_packets = resolve_action_packets(
        action_packets=data.get("action_packets"),
        reconsolidation_snapshot=reconsolidation_snapshot,
    )
    return resolve_digital_body_consequence(
        digital_body_consequence=_dict_or_empty(data.get("digital_body_consequence")),
        digital_body_state=resolved_body,
        action_packets=action_packets,
        reconsolidation_snapshot=reconsolidation_snapshot,
    )


@dataclass
class BackendSession:
    graph: Any
    memory_store: MemoryStore
    thread_id: str
    user_id: str | None = None

    def config(self, *, checkpoint_id: str | None = None) -> dict[str, Any]:
        configurable: dict[str, Any] = {"thread_id": self.thread_id}
        if str(self.user_id or "").strip():
            configurable["user_id"] = self.user_id
        if str(checkpoint_id or "").strip():
            configurable["checkpoint_id"] = str(checkpoint_id).strip()
        return {"configurable": configurable}

    def build_run_config(self, pending_checkpoint_id: str | None) -> tuple[dict[str, Any], str | None]:
        if str(pending_checkpoint_id or "").strip():
            return self.config(checkpoint_id=str(pending_checkpoint_id).strip()), None
        return self.config(), pending_checkpoint_id

    def get_state_values(self, *, config: dict[str, Any] | None = None) -> dict[str, Any]:
        cfg = _normalized_graph_config(
            config or self.config(),
            fallback_thread_id=self.thread_id,
            fallback_user_id=self.user_id,
        )
        return _coerce_values(self.graph.get_state(cfg))

    def emotion_label(self, *, config: dict[str, Any] | None = None, default: str = "neutral") -> str:
        vals = self.get_state_values(config=config)
        emotion_state = vals.get("emotion_state") if isinstance(vals.get("emotion_state"), dict) else {}
        label = str((emotion_state or {}).get("label") or "").strip()
        return label or str(default or "neutral")

    def apply_implicit_idle_maturation(
        self,
        *,
        run_config: dict[str, Any],
        last_conversation_touch_ts: int | None,
        trigger_minutes: int,
        now_ts: int | None = None,
    ) -> bool:
        if int(trigger_minutes or 0) <= 0 or last_conversation_touch_ts is None:
            return False
        clock_now = int(now_ts or 0) or 0
        if clock_now <= 0:
            import time as _time

            clock_now = int(_time.time())
        elapsed_seconds = max(0, clock_now - int(last_conversation_touch_ts))
        elapsed_minutes = elapsed_seconds // 60
        if elapsed_minutes < int(trigger_minutes):
            return False

        cfg = _normalized_graph_config(
            run_config,
            fallback_thread_id=self.thread_id,
            fallback_user_id=self.user_id,
        )
        current_values = self.get_state_values(config=cfg)
        if not isinstance(current_values, dict):
            return False
        prepared = build_implicit_idle_state_update(
            current_values,
            idle_minutes=int(elapsed_minutes),
            created_at=clock_now,
        )
        self.graph.update_state(cfg, prepared, as_node="prepare_turn")
        return True

    def build_idle_event_payload(
        self,
        *,
        run_config: dict[str, Any],
        idle_minutes: int,
        note: str = "",
        created_at: int | None = None,
        extra_tags: list[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        cfg = _normalized_graph_config(
            run_config,
            fallback_thread_id=self.thread_id,
            fallback_user_id=self.user_id,
        )
        current_values = self.get_state_values(config=cfg)
        event_override = build_implicit_idle_event_override(
            current_values if isinstance(current_values, dict) else {},
            idle_minutes=int(idle_minutes),
            note=str(note or "").strip(),
            created_at=created_at,
            extra_tags=extra_tags or [],
        )
        return {"event_override": event_override}

    def invoke_stream(
        self,
        payload: Any,
        *,
        config: dict[str, Any] | None = None,
        on_text: Callable[[str], None] | None = None,
    ) -> StreamInvocationResult:
        cfg = _normalized_graph_config(
            config or self.config(),
            fallback_thread_id=self.thread_id,
            fallback_user_id=self.user_id,
        )
        last_values: dict[str, Any] | None = None
        buf = ""
        for mode, chunk in self.graph.stream(payload, config=cfg, stream_mode=["messages", "values"]):
            if mode == "values":
                last_values = dict(chunk) if isinstance(chunk, dict) else {}
                continue
            if mode != "messages":
                continue
            msg, meta = chunk
            if (meta or {}).get("langgraph_node") != "call_model":
                continue
            if not type(msg).__name__.endswith("Chunk"):
                continue
            text = getattr(msg, "content", "") or ""
            if not text:
                continue
            buf += str(text)
            if callable(on_text):
                on_text(str(text))
        values = last_values or {}
        approval_request = _approval_request_from_output(values)
        values = _merge_pending_approval_state(values, approval_request)
        if approval_request is None:
            approval_request = _approval_request_from_pending_access(values)
        return StreamInvocationResult(
            values=values,
            streamed_text=buf,
            approval_request=approval_request,
        )

    def resume_stream(
        self,
        decisions: list[dict[str, Any]],
        *,
        config: dict[str, Any] | None = None,
        on_text: Callable[[str], None] | None = None,
    ) -> StreamInvocationResult:
        cfg = _normalized_graph_config(
            config or self.config(),
            fallback_thread_id=self.thread_id,
            fallback_user_id=self.user_id,
        )
        snapshot = self.graph.get_state(cfg)
        current_values = _coerce_values(snapshot)
        pending_access = _approval_request_from_pending_access(current_values)
        if pending_access is not None and not _snapshot_has_pending_graph_interrupt(snapshot):
            decision = next((dict(item) for item in decisions if isinstance(item, dict)), {})
            resolved_values = _apply_access_request_resolution(current_values, decision)
            self.graph.update_state(cfg, resolved_values, as_node="prepare_turn")
            return StreamInvocationResult(
                values=resolved_values,
                streamed_text="",
                approval_request=_approval_request_from_pending_access(resolved_values),
            )
        return self.invoke_stream(
            Command(resume={"decisions": decisions}),
            config=cfg,
            on_text=on_text,
        )

    def extract_final_text(
        self,
        values: dict[str, Any] | None,
        *,
        streamed_text: str = "",
    ) -> str:
        final_text = _state_final_text(values)
        if final_text:
            return final_text
        return str(streamed_text or "").strip()

    def invoke_event_round(
        self,
        *,
        run_config: dict[str, Any],
        event_payload: dict[str, Any],
        auto_resume_memory_approval: Callable[[dict[str, Any]], bool] | None = None,
        reject_reason: str = "event_round_no_manual_tooling",
    ) -> EventRoundResult:
        before_values = self.get_state_values(config=run_config)
        before_messages = before_values.get("messages") if isinstance(before_values.get("messages"), list) else []
        before_len = len(before_messages)

        out = self.graph.invoke(event_payload, config=run_config)
        approval_request = _approval_request_from_output(out)
        while approval_request is not None:
            if callable(auto_resume_memory_approval) and auto_resume_memory_approval(approval_request.payload):
                decisions = [{"action": "approve"} for _ in approval_request.tool_calls]
            else:
                decisions = [{"action": "reject", "reason": reject_reason} for _ in approval_request.tool_calls]
            out = self.graph.invoke(
                Command(resume={"decisions": decisions}),
                config=_normalized_graph_config(
                    run_config,
                    fallback_thread_id=self.thread_id,
                    fallback_user_id=self.user_id,
                ),
            )
            approval_request = _approval_request_from_output(out)

        after_values = self.get_state_values(config=run_config)
        final_text = str(after_values.get("final_text") or "").strip()
        if not final_text:
            after_messages = after_values.get("messages") if isinstance(after_values.get("messages"), list) else []
            final_text = ""
            if len(after_messages) > before_len and after_messages:
                final_text = _message_content(after_messages[-1])
        return EventRoundResult(values=after_values, final_text=final_text)

    def build_evolution_summary(self, *, state_values: dict[str, Any] | None = None) -> dict[str, Any]:
        vals = state_values if isinstance(state_values, dict) else self.get_state_values()
        current_event = _resolved_readback_current_event(vals, thread_id=self.thread_id)
        reconsolidation_snapshot = (
            vals.get("reconsolidation_snapshot") if isinstance(vals.get("reconsolidation_snapshot"), dict) else {}
        )
        behavior_action, behavior_plan = resolve_behavior_payloads(
            behavior_action=vals.get("behavior_action") if isinstance(vals.get("behavior_action"), dict) else {},
            behavior_plan=vals.get("behavior_plan") if isinstance(vals.get("behavior_plan"), dict) else {},
            reconsolidation_snapshot=reconsolidation_snapshot,
            current_event=current_event,
            world_model_state=vals.get("world_model_state") if isinstance(vals.get("world_model_state"), dict) else {},
        )
        interaction_carryover = resolve_interaction_carryover(
            interaction_carryover=vals.get("interaction_carryover")
            if isinstance(vals.get("interaction_carryover"), dict)
            else {},
            reconsolidation_snapshot=reconsolidation_snapshot,
        )
        counterpart_assessment = resolve_counterpart_assessment(
            counterpart_assessment=vals.get("counterpart_assessment")
            if isinstance(vals.get("counterpart_assessment"), dict)
            else {},
            reconsolidation_snapshot=reconsolidation_snapshot,
        )
        agenda_lifecycle_residue = resolve_agenda_lifecycle_residue(
            agenda_lifecycle_residue=vals.get("agenda_lifecycle_residue")
            if isinstance(vals.get("agenda_lifecycle_residue"), dict)
            else {},
            reconsolidation_snapshot=reconsolidation_snapshot,
        )
        behavior_queue = resolve_behavior_queue(
            behavior_queue=vals.get("behavior_queue"),
            behavior_agenda=vals.get("behavior_agenda"),
        )
        autonomy = _resolved_autonomy(vals)
        digital_body = _resolved_digital_body(vals)
        digital_body_consequence = _resolved_digital_body_consequence(vals, digital_body=digital_body)
        return build_evolution_cli_summary(
            relationship=_resolved_relationship_state(self.memory_store, vals),
            semantic_narrative_profile=vals.get("semantic_narrative_profile")
            if isinstance(vals.get("semantic_narrative_profile"), dict)
            else {},
            world_model_state=vals.get("world_model_state") if isinstance(vals.get("world_model_state"), dict) else {},
            emotion_state=vals.get("emotion_state") if isinstance(vals.get("emotion_state"), dict) else {},
            bond_state=vals.get("bond_state") if isinstance(vals.get("bond_state"), dict) else {},
            counterpart_assessment=counterpart_assessment,
            behavior_action=behavior_action,
            behavior_plan=behavior_plan,
            behavior_queue=behavior_queue,
            interaction_carryover=interaction_carryover,
            current_event=current_event,
            worldline_focus=_resolved_worldline_focus(self.memory_store, vals),
            reconsolidation_snapshot=reconsolidation_snapshot,
            agenda_lifecycle_residue=agenda_lifecycle_residue,
            autonomy_intent=autonomy.get("intent"),
            action_packets=autonomy.get("action_packets"),
            pending_approval=autonomy.get("pending_approval"),
            action_trace=autonomy.get("execution_trace"),
            autonomy_block_reason=autonomy.get("block_reason"),
            digital_body_state=digital_body,
            digital_body_consequence=digital_body_consequence,
        )

    def worldline_view(self) -> dict[str, Any]:
        snap = self.memory_store.snapshot()
        vals = self.get_state_values()
        counterpart_history = snap.get("counterpart_assessment_history", [])
        proactive_history = snap.get("proactive_continuity_history", [])
        autonomy = _resolved_autonomy(vals)
        return {
            "worldline_summary": self.build_evolution_summary(state_values=vals),
            "worldline_events": snap.get("worldline_events", []),
            "commitments": snap.get("commitments", []),
            "conflict_repair": snap.get("conflict_repair", []),
            "unresolved_tensions": snap.get("unresolved_tensions", []),
            "autonomy": autonomy,
            "counterpart_assessment_history": counterpart_history,
            "counterpart_assessment_preview": build_counterpart_assessment_cli_summary(counterpart_history, limit=5),
            "proactive_continuity_history": proactive_history,
            "proactive_continuity_preview": build_proactive_continuity_cli_summary(proactive_history, limit=5),
            "semantic_self_narratives": snap.get("semantic_self_narratives", []),
            "revision_traces": snap.get("revision_traces", []),
        }

    def bond_view(self) -> dict[str, Any]:
        vals = self.get_state_values()
        relationship_state = _resolved_relationship_state(self.memory_store, vals)
        counterpart_history = list(reversed(self.memory_store.list_counterpart_assessment_history(limit=30)))
        proactive_history = list(reversed(self.memory_store.list_proactive_continuity_history(limit=30)))
        autonomy = _resolved_autonomy(vals)
        return {
            "relationship_state": relationship_state,
            "bond_state": vals.get("bond_state") if isinstance(vals.get("bond_state"), dict) else {},
            "autonomy": autonomy,
            "relationship_timeline": list(reversed(self.memory_store.list_relationship_timeline(limit=30))),
            "counterpart_assessment_history": counterpart_history,
            "counterpart_assessment_preview": build_counterpart_assessment_cli_summary(counterpart_history, limit=5),
            "proactive_continuity_history": proactive_history,
            "proactive_continuity_preview": build_proactive_continuity_cli_summary(proactive_history, limit=5),
            "conflict_repair": list(reversed(self.memory_store.list_conflict_repairs(limit=30))),
        }

    def sources_view(self) -> dict[str, Any]:
        vals = self.get_state_values()
        return {
            "sources": list(reversed(self.memory_store.list_source_refs(limit=30))),
            "claim_links": vals.get("claim_links") if isinstance(vals.get("claim_links"), list) else [],
        }

    def persona_view(self) -> dict[str, Any]:
        vals = self.get_state_values()
        current_event = _resolved_readback_current_event(vals, thread_id=self.thread_id)
        reconsolidation_snapshot = (
            vals.get("reconsolidation_snapshot") if isinstance(vals.get("reconsolidation_snapshot"), dict) else {}
        )
        queue_vals = resolve_behavior_queue(
            behavior_queue=vals.get("behavior_queue"),
            behavior_agenda=vals.get("behavior_agenda"),
        )
        behavior_action, behavior_plan = resolve_behavior_payloads(
            behavior_action=vals.get("behavior_action") if isinstance(vals.get("behavior_action"), dict) else {},
            behavior_plan=vals.get("behavior_plan") if isinstance(vals.get("behavior_plan"), dict) else {},
            reconsolidation_snapshot=reconsolidation_snapshot,
            current_event=current_event,
            world_model_state=vals.get("world_model_state") if isinstance(vals.get("world_model_state"), dict) else {},
        )
        interaction_carryover = resolve_interaction_carryover(
            interaction_carryover=vals.get("interaction_carryover")
            if isinstance(vals.get("interaction_carryover"), dict)
            else {},
            reconsolidation_snapshot=reconsolidation_snapshot,
        )
        counterpart_assessment = resolve_counterpart_assessment(
            counterpart_assessment=vals.get("counterpart_assessment")
            if isinstance(vals.get("counterpart_assessment"), dict)
            else {},
            reconsolidation_snapshot=reconsolidation_snapshot,
        )
        agenda_lifecycle_residue = resolve_agenda_lifecycle_residue(
            agenda_lifecycle_residue=vals.get("agenda_lifecycle_residue")
            if isinstance(vals.get("agenda_lifecycle_residue"), dict)
            else {},
            reconsolidation_snapshot=reconsolidation_snapshot,
        )
        autonomy = _resolved_autonomy(vals)
        digital_body = _resolved_digital_body(vals)
        digital_body_consequence = _resolved_digital_body_consequence(vals, digital_body=digital_body)
        return {
            "evolution_summary": self.build_evolution_summary(state_values=vals),
            "persona_state": vals.get("persona_state") if isinstance(vals.get("persona_state"), dict) else {},
            "emotion_state": vals.get("emotion_state") if isinstance(vals.get("emotion_state"), dict) else {},
            "bond_state": vals.get("bond_state") if isinstance(vals.get("bond_state"), dict) else {},
            "allostasis_state": vals.get("allostasis_state") if isinstance(vals.get("allostasis_state"), dict) else {},
            "counterpart_assessment": counterpart_assessment,
            "semantic_narrative_profile": vals.get("semantic_narrative_profile")
            if isinstance(vals.get("semantic_narrative_profile"), dict)
            else {},
            "world_model_state": vals.get("world_model_state") if isinstance(vals.get("world_model_state"), dict) else {},
            "evolution_state": vals.get("evolution_state") if isinstance(vals.get("evolution_state"), dict) else {},
            "reconsolidation_snapshot": reconsolidation_snapshot,
            "turn_appraisal": vals.get("turn_appraisal") if isinstance(vals.get("turn_appraisal"), dict) else {},
            "behavior_policy": vals.get("behavior_policy") if isinstance(vals.get("behavior_policy"), dict) else {},
            "behavior_action": behavior_action,
            "interaction_carryover": interaction_carryover,
            "agenda_lifecycle_residue": agenda_lifecycle_residue,
            "behavior_plan": behavior_plan,
            "behavior_queue": queue_vals,
            "behavior_queue_summary": build_behavior_queue_cli_summary(queue_vals, limit=3),
            "autonomy": autonomy,
            "digital_body": digital_body,
            "digital_body_consequence": digital_body_consequence,
            "science_mode": bool(vals.get("science_mode", False)),
            "tsundere_intensity": vals.get("tsundere_intensity", 0.5),
            "ooc_detector": vals.get("ooc_detector") if isinstance(vals.get("ooc_detector"), dict) else {},
            "canon_guard": vals.get("canon_guard") if isinstance(vals.get("canon_guard"), dict) else {},
        }

    def appraisal_view(self) -> dict[str, Any]:
        vals = self.get_state_values()
        return vals.get("turn_appraisal") if isinstance(vals.get("turn_appraisal"), dict) else {}

    def current_checkpoint_view(self, *, config: dict[str, Any] | None = None) -> dict[str, Any]:
        cfg = _normalized_graph_config(
            config or self.config(),
            fallback_thread_id=self.thread_id,
            fallback_user_id=self.user_id,
        )
        thread_id = _thread_id_from_config(cfg, self.thread_id)
        snapshot = self.graph.get_state(cfg)
        snapshot_cfg = getattr(snapshot, "config", {}) if snapshot is not None else {}
        checkpoint_id = None
        if isinstance(snapshot_cfg, dict):
            checkpoint_id = (snapshot_cfg.get("configurable") or {}).get("checkpoint_id")
        return {"thread_id": thread_id, "checkpoint_id": checkpoint_id}

    def checkpoint_history_view(
        self,
        *,
        limit: int = 10,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cfg = _normalized_graph_config(
            config or self.config(),
            fallback_thread_id=self.thread_id,
            fallback_user_id=self.user_id,
        )
        thread_id = _thread_id_from_config(cfg, self.thread_id)
        try:
            capped_limit = max(1, int(limit))
        except Exception:
            capped_limit = 10
        history_rows = list(self.graph.get_state_history(cfg))
        rows: list[dict[str, Any]] = []
        for snapshot in history_rows[:capped_limit]:
            snapshot_cfg = getattr(snapshot, "config", {}) if snapshot is not None else {}
            checkpoint_id = None
            if isinstance(snapshot_cfg, dict):
                checkpoint_id = (snapshot_cfg.get("configurable") or {}).get("checkpoint_id")
            rows.append(
                {
                    "checkpoint_id": checkpoint_id,
                    "next": list(getattr(snapshot, "next", []) or []),
                }
            )
        return {
            "thread_id": thread_id,
            "limit": capped_limit,
            "total": len(history_rows),
            "rows": rows,
        }

    def behavior_queue_view(self, *, config: dict[str, Any] | None = None) -> dict[str, Any]:
        vals = self.get_state_values(config=config)
        queue = resolve_behavior_queue(
            behavior_queue=vals.get("behavior_queue"),
            behavior_agenda=vals.get("behavior_agenda"),
        )
        autonomy = _resolved_autonomy(vals)
        return {
            "behavior_queue": queue,
            "behavior_queue_summary": build_behavior_queue_cli_summary(queue, limit=3),
            "autonomy": autonomy,
        }


__all__ = [
    "BackendSession",
    "EventRoundResult",
    "StreamInvocationResult",
    "ToolApprovalRequest",
]
