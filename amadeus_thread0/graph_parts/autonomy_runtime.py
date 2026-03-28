from __future__ import annotations

from typing import Any

from .action_packets import build_behavior_action_packet, make_proposal_id, normalize_action_packet, normalize_action_packets
from .digital_body_runtime import normalize_embodied_context

_OWN_RHYTHM_EVENT_KINDS = {
    "self_activity_state",
    "time_idle",
    "scheduled_checkin_due",
    "scheduled_life_due",
}

_ARTIFACT_KIND_LABELS = {
    "file": "前面的文件",
    "document": "前面的文档",
    "buffer": "前面的缓冲区",
    "notebook": "前面的笔记本",
    "workspace": "前面的工作区",
    "page": "前面的页面",
    "tab": "前面的标签页",
    "site": "前面的站点",
    "browser_page": "前面的页面",
    "search_result": "前面的检索结果",
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _clean_list(value: Any, *, limit: int = 3) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for item in _list_or_empty(value):
        text = _clean_text(item).lower()
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
        if len(items) >= max(1, int(limit)):
            break
    return items


def _clean_text(value: Any, *, limit: int = 220) -> str:
    return str(value or "").strip()[:limit]


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        cast = float(value)
    except Exception:
        cast = float(default)
    return max(0.0, min(1.0, cast))


def _normalized_intent_origin(value: Any) -> str:
    text = _clean_text(value).lower()
    return text if text in {"motive_goal", "own_rhythm", "counterpart_request", "capability_upgrade"} else ""


def _artifact_surface_label(embodied: dict[str, Any]) -> str:
    label = _clean_text(embodied.get("active_artifact_label"))
    if label:
        return label
    ref = _clean_text(embodied.get("active_artifact_ref"))
    if ref:
        return ref
    kind = _clean_text(embodied.get("active_artifact_kind")).lower()
    return _ARTIFACT_KIND_LABELS.get(kind, "前面的工作面")


def _artifact_reacquisition_mode(embodied: dict[str, Any]) -> str:
    mode = _clean_text(embodied.get("artifact_reacquisition_mode")).lower()
    if mode:
        return mode
    kind = _clean_text(embodied.get("active_artifact_kind")).lower()
    if kind == "search_result":
        return "rerun_search"
    if kind in {"workspace"}:
        return "reattach_workspace"
    if kind in {"page", "tab", "site", "browser_page"}:
        return "reopen_page"
    if kind in {"file", "document", "buffer", "notebook"}:
        return "reopen_file"
    return "reattach_artifact"


def _artifact_reacquisition_reason(embodied: dict[str, Any]) -> str:
    continuity = _clean_text(embodied.get("artifact_continuity")).lower()
    label = _artifact_surface_label(embodied)
    mode = _artifact_reacquisition_mode(embodied)
    if continuity == "stale":
        return f"先确认{label}还是当前这一版，再继续往下做。"
    if mode == "rerun_search":
        return "先把前面的检索结果重新拿回来，再继续往下做。"
    if mode == "reattach_workspace":
        return f"先把{label}重新接回当前上下文，再继续往下做。"
    if mode in {"reopen_page", "restore_page", "reopen_file", "restore_file"}:
        return f"先把{label}重新打开，再继续往下做。"
    return f"先把{label}重新接回当前上下文，再继续往下做。"


def _artifact_reacquisition_packet(embodied: dict[str, Any]) -> dict[str, Any]:
    continuity = _clean_text(embodied.get("artifact_continuity")).lower()
    if continuity not in {"missing", "detached"}:
        return {}
    origin = _normalized_intent_origin(embodied.get("primary_origin")) or "motive_goal"
    mode = _artifact_reacquisition_mode(embodied)
    label = _artifact_surface_label(embodied)
    target = _clean_text(embodied.get("active_artifact_ref")) or label
    reason = _artifact_reacquisition_reason(embodied)
    return normalize_action_packet(
        {
            "proposal_id": make_proposal_id("artifact", continuity, mode, target, origin),
            "origin": origin,
            "intent": f"artifact:{mode}",
            "status": "proposed",
            "risk": "read",
            "requires_approval": False,
            "capability_steps": [
                {
                    "kind": "artifact",
                    "name": mode,
                    "target": target,
                    "status": "pending",
                    "requires_approval": False,
                    "note": reason,
                }
            ],
            "expected_effect": reason,
            "result_summary": "",
            "writeback_ready": False,
        }
    )


def _embodied_carryover_autonomy_signal(carryover: dict[str, Any]) -> dict[str, Any]:
    embodied = normalize_embodied_context(carryover.get("embodied_context"))
    if not embodied:
        return {}
    kind = _clean_text(embodied.get("kind")).lower()
    primary_status = _clean_text(embodied.get("primary_status")).lower()
    primary_origin = _normalized_intent_origin(embodied.get("primary_origin"))
    block_reason = _clean_text(embodied.get("block_reason"))
    requested_help = bool(embodied.get("requested_help", False))
    requested_access = _clean_list(embodied.get("requested_access"))
    missing_access = _clean_list(embodied.get("missing_access"))
    access_label = "、".join((requested_access or missing_access)[:2])

    if kind == "access_request_pending" or primary_status == "awaiting_approval" or requested_help:
        if access_label and requested_help:
            reason = f"那件事还卡在等{access_label}和外部确认这一步。"
        elif access_label:
            reason = f"那件事还卡在等{access_label}这一步。"
        else:
            reason = "那件事还停在额外入口确认之前。"
        return {
            "mode": "approval_pending",
            "origin": primary_origin,
            "reason": reason,
            "requires_approval": True,
            "continuity_floor": 0.46,
            "confidence_floor": 0.52,
            "block_reason": "",
        }

    artifact_continuity = _clean_text(embodied.get("artifact_continuity")).lower()
    if artifact_continuity in {"missing", "detached"}:
        return {
            "mode": "reacquire_artifact",
            "origin": primary_origin or "motive_goal",
            "reason": _artifact_reacquisition_reason(embodied),
            "requires_approval": False,
            "continuity_floor": 0.44,
            "confidence_floor": 0.5,
            "block_reason": "",
            "artifact_continuity": artifact_continuity,
            "artifact_reacquisition_mode": _artifact_reacquisition_mode(embodied),
            "active_artifact_kind": _clean_text(embodied.get("active_artifact_kind")).lower(),
            "active_artifact_label": _artifact_surface_label(embodied),
            "active_artifact_ref": _clean_text(embodied.get("active_artifact_ref")),
        }

    if kind == "environmental_friction" or block_reason or missing_access:
        if block_reason:
            reason = block_reason
        elif access_label:
            reason = f"那件事暂时还受{access_label}这类环境条件限制。"
        else:
            reason = "那件事暂时还受当前环境条件限制。"
        return {
            "mode": "blocked",
            "origin": primary_origin,
            "reason": reason,
            "requires_approval": False,
            "continuity_floor": 0.42,
            "confidence_floor": 0.48,
            "block_reason": reason,
        }

    return {}


def autonomy_intent_has_signal(intent: Any) -> bool:
    if not isinstance(intent, dict) or not intent:
        return False
    for key in ("mode", "origin", "reason", "primary_proposal_id"):
        if _clean_text(intent.get(key)):
            return True
    for key in ("confidence", "own_rhythm_weight", "continuity_weight"):
        if _clamp01(intent.get(key), 0.0) > 0.0:
            return True
    return bool(intent.get("requires_approval", False))


def normalize_autonomy_intent(intent: Any) -> dict[str, Any]:
    row = _dict_or_empty(intent)
    if not autonomy_intent_has_signal(row):
        return {}
    return {
        "mode": _clean_text(row.get("mode")).lower() or "language_response",
        "origin": _clean_text(row.get("origin")).lower() or "motive_goal",
        "reason": _clean_text(row.get("reason")),
        "confidence": round(_clamp01(row.get("confidence"), 0.0), 3),
        "own_rhythm_weight": round(_clamp01(row.get("own_rhythm_weight"), 0.0), 3),
        "continuity_weight": round(_clamp01(row.get("continuity_weight"), 0.0), 3),
        "requires_approval": bool(row.get("requires_approval", False)),
        "primary_proposal_id": _clean_text(row.get("primary_proposal_id")),
    }


def _derive_intent_mode(
    *,
    current_event: dict[str, Any],
    packet: dict[str, Any],
    block_reason: str,
) -> str:
    status = _clean_text(packet.get("status")).lower()
    tool_name = _clean_text(packet.get("tool_name")).lower()
    intent = _clean_text(packet.get("intent")).lower()
    event_kind = _clean_text(current_event.get("kind")).lower()
    linked_queue_id = _clean_text(packet.get("linked_queue_id"))
    requires_approval = bool(packet.get("requires_approval", False))
    if block_reason or status in {"blocked", "rejected"}:
        return "blocked"
    if status == "awaiting_approval" or (requires_approval and status in {"proposed", "approved"}):
        return "approval_pending"
    if tool_name and status in {"approved", "executing"}:
        return "autonomy_executing"
    if tool_name and status == "completed":
        return "tool_completed"
    if intent.startswith("artifact:"):
        return "reacquire_artifact"
    if status == "queued" or linked_queue_id:
        return "queue_followthrough"
    if event_kind in _OWN_RHYTHM_EVENT_KINDS:
        return "own_rhythm_presence"
    return "language_response"


def _derive_intent_reason(
    *,
    current_event: dict[str, Any],
    behavior_action: dict[str, Any],
    behavior_plan: dict[str, Any],
    packet: dict[str, Any],
    block_reason: str,
) -> str:
    if block_reason:
        return block_reason
    for candidate in (
        packet.get("expected_effect"),
        behavior_plan.get("goal_frame"),
        behavior_action.get("goal_frame"),
        behavior_plan.get("note"),
        behavior_action.get("note"),
        current_event.get("semantic_goal"),
        current_event.get("text"),
    ):
        text = _clean_text(candidate)
        if text:
            return text
    return ""


def _packet_reason_text(packet: dict[str, Any]) -> str:
    for candidate in (
        packet.get("expected_effect"),
        packet.get("result_summary"),
    ):
        text = _clean_text(candidate)
        if text:
            return text
    for step in _list_or_empty(packet.get("capability_steps")):
        note = _clean_text(_dict_or_empty(step).get("note"))
        if note:
            return note
    tool_name = _clean_text(packet.get("tool_name"))
    intent = _clean_text(packet.get("intent"))
    status = _clean_text(packet.get("status")).lower()
    if status == "awaiting_approval":
        label = tool_name or intent
        if label:
            return f"等待审批后再决定是否执行 {label}。"
    return ""


def _packet_is_default_language_shell(packet: dict[str, Any]) -> bool:
    row = _dict_or_empty(packet)
    if not row:
        return False
    if any(
        (
            bool(row.get("requires_approval", False)),
            _clean_text(row.get("tool_name")),
            _clean_text(row.get("linked_queue_id")),
            _clean_text(row.get("block_reason")),
            _clean_text(row.get("expected_effect")),
            _clean_text(row.get("result_summary")),
        )
    ):
        return False
    if _clean_text(row.get("intent")).lower() != "respond":
        return False
    if _clean_text(row.get("status")).lower() not in {"", "proposed"}:
        return False
    if _clean_text(row.get("risk")).lower() not in {"", "read"}:
        return False
    steps = _list_or_empty(row.get("capability_steps"))
    if len(steps) != 1:
        return False
    step = _dict_or_empty(steps[0])
    return (
        _clean_text(step.get("kind")).lower() == "speak"
        and _clean_text(step.get("name")).lower() == "reply"
        and _clean_text(step.get("target")) == ""
        and _clean_text(step.get("note")) == ""
        and _clean_text(step.get("status")).lower() in {"", "pending"}
        and not bool(step.get("requires_approval", False))
    )


def refresh_autonomy_intent_from_packets(
    autonomy_intent: Any,
    action_packets: Any,
    *,
    current_event: dict[str, Any] | None = None,
    block_reason: str = "",
) -> dict[str, Any]:
    packets = normalize_action_packets(action_packets)
    base = normalize_autonomy_intent(autonomy_intent)
    current = _dict_or_empty(current_event)
    block = _clean_text(block_reason)
    if not packets:
        if block:
            base = dict(base or {})
            base.update({"mode": "blocked", "reason": block})
        return normalize_autonomy_intent(base)

    primary = dict(packets[0])
    mode = _derive_intent_mode(current_event=current, packet=primary, block_reason=block)
    base_primary_proposal_id = _clean_text(base.get("primary_proposal_id"))
    primary_proposal_id = _clean_text(primary.get("proposal_id"))
    primary_reason = _packet_reason_text(primary) or block
    if base_primary_proposal_id and base_primary_proposal_id == primary_proposal_id:
        reason = _clean_text(base.get("reason")) or primary_reason
    else:
        reason = primary_reason or _clean_text(base.get("reason")) or block
    confidence = max(_clamp01(base.get("confidence"), 0.0), 0.56 if packets else 0.0)
    own_rhythm_weight = _clamp01(base.get("own_rhythm_weight"), 0.0)
    continuity_weight = _clamp01(base.get("continuity_weight"), 0.0)
    requires_approval = any(bool(packet.get("requires_approval", False)) for packet in packets)
    return normalize_autonomy_intent(
        {
            "mode": mode,
            "origin": _clean_text(primary.get("origin")).lower() or _clean_text(base.get("origin")).lower(),
            "reason": reason,
            "confidence": confidence,
            "own_rhythm_weight": own_rhythm_weight,
            "continuity_weight": continuity_weight,
            "requires_approval": requires_approval,
            "primary_proposal_id": primary_proposal_id or base_primary_proposal_id,
        }
    )


def derive_autonomy_runtime(
    *,
    current_event: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None,
    behavior_plan: dict[str, Any] | None,
    behavior_queue: Any,
    world_model_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
    interaction_carryover: dict[str, Any] | None = None,
    agenda_lifecycle_residue: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = _dict_or_empty(current_event)
    action = _dict_or_empty(behavior_action)
    plan = _dict_or_empty(behavior_plan)
    world = _dict_or_empty(world_model_state)
    semantic = _dict_or_empty(semantic_narrative_profile)
    carryover = _dict_or_empty(interaction_carryover)
    agenda_lifecycle = _dict_or_empty(agenda_lifecycle_residue)
    embodied_signal = _embodied_carryover_autonomy_signal(carryover)
    embodied_packet = _artifact_reacquisition_packet(normalize_embodied_context(carryover.get("embodied_context")))
    behavior_packet = build_behavior_action_packet(
        current_event=event,
        behavior_action=action,
        behavior_plan=plan,
        behavior_queue=behavior_queue,
        agenda_lifecycle_residue=agenda_lifecycle,
    )
    action_packets = normalize_action_packets([behavior_packet] if behavior_packet else [])
    primary_packet = dict(action_packets[0]) if action_packets else {}
    primary_packet_source = "behavior"
    if embodied_packet and (not primary_packet or _packet_is_default_language_shell(primary_packet)):
        action_packets = [embodied_packet]
        primary_packet = dict(embodied_packet)
        primary_packet_source = "embodied_carryover"
    elif primary_packet and embodied_signal and _packet_is_default_language_shell(primary_packet):
        primary_packet = {}
        action_packets = []
        primary_packet_source = ""
    intent_packets = action_packets
    continuity_weight = round(
        _clamp01(
            max(
                _clamp01(carryover.get("strength"), 0.0),
                _clamp01(semantic.get("continuity_depth"), 0.0),
                _clamp01(semantic.get("history_weight"), 0.0),
                _clamp01(agenda_lifecycle.get("continuity_anchor"), 0.0),
                _clamp01(agenda_lifecycle.get("semantic_continuity_depth"), 0.0),
                _clamp01(embodied_signal.get("continuity_floor"), 0.0),
            ),
            0.0,
        ),
        3,
    )
    own_rhythm_weight = round(
        _clamp01(
            max(
                _clamp01(world.get("self_activity_momentum"), 0.0),
                _clamp01(event.get("self_activity_momentum"), 0.0),
                _clamp01(agenda_lifecycle.get("own_rhythm_anchor"), 0.0),
                _clamp01(agenda_lifecycle.get("own_rhythm_bias"), 0.0),
            ),
            0.0,
        ),
        3,
    )
    block_reason = _clean_text(primary_packet.get("block_reason")) or (
        _clean_text(embodied_signal.get("block_reason")) if not primary_packet else ""
    )
    autonomy_intent = normalize_autonomy_intent(
        {
            "mode": _derive_intent_mode(current_event=event, packet=primary_packet, block_reason=block_reason)
            if primary_packet
            else (
                _clean_text(embodied_signal.get("mode"))
                or ("own_rhythm_presence" if _clean_text(event.get("kind")).lower() in _OWN_RHYTHM_EVENT_KINDS else "language_response")
            ),
            "origin": _clean_text(primary_packet.get("origin")).lower()
            or _clean_text(embodied_signal.get("origin")).lower()
            or "motive_goal",
            "reason": _derive_intent_reason(
                current_event=event,
                behavior_action=action,
                behavior_plan=plan,
                packet=primary_packet,
                block_reason=block_reason,
            ),
            "confidence": max(
                _clamp01(action.get("engagement_level"), 0.0),
                _clamp01(action.get("initiative_level"), 0.0),
                continuity_weight,
                own_rhythm_weight * 0.92,
                _clamp01(embodied_signal.get("confidence_floor"), 0.0),
                0.38 if primary_packet else 0.0,
            ),
            "own_rhythm_weight": own_rhythm_weight,
            "continuity_weight": continuity_weight,
            "requires_approval": bool(primary_packet.get("requires_approval", False))
            or bool(embodied_signal.get("requires_approval", False)),
            "primary_proposal_id": _clean_text(primary_packet.get("proposal_id")),
        }
    )
    if not primary_packet and embodied_signal:
        autonomy_intent = normalize_autonomy_intent(
            {
                **autonomy_intent,
                "reason": _clean_text(autonomy_intent.get("reason")) or _clean_text(embodied_signal.get("reason")),
                "origin": _clean_text(autonomy_intent.get("origin")).lower()
                or _clean_text(embodied_signal.get("origin")).lower()
                or "motive_goal",
            }
    )
    autonomy_intent = refresh_autonomy_intent_from_packets(
        autonomy_intent,
        intent_packets,
        current_event=event,
        block_reason=block_reason,
    )
    pending_action_proposal = (
        normalize_action_packet(primary_packet)
        if primary_packet and bool(primary_packet.get("requires_approval", False))
        else {}
    )
    action_trace: list[dict[str, Any]] = []
    if primary_packet:
        action_trace.append(
            {
                "proposal_id": _clean_text(primary_packet.get("proposal_id")),
                "origin": _clean_text(primary_packet.get("origin")).lower(),
                "intent": _clean_text(primary_packet.get("intent")).lower(),
                "status": _clean_text(primary_packet.get("status")).lower() or "proposed",
                "risk": _clean_text(primary_packet.get("risk")).lower() or "read",
                "source": "interaction_carryover" if primary_packet_source == "embodied_carryover" else "prepare_turn_runtime",
                "event": "derived_from_embodied_carryover" if primary_packet_source == "embodied_carryover" else "derived_from_behavior",
                "requires_approval": bool(primary_packet.get("requires_approval", False)),
                "linked_queue_id": _clean_text(primary_packet.get("linked_queue_id")),
            }
        )
    return {
        "autonomy_intent": autonomy_intent,
        "action_packets": action_packets,
        "pending_action_proposal": pending_action_proposal,
        "action_trace": action_trace,
        "autonomy_block_reason": block_reason,
    }


__all__ = [
    "autonomy_intent_has_signal",
    "derive_autonomy_runtime",
    "normalize_autonomy_intent",
    "refresh_autonomy_intent_from_packets",
]
