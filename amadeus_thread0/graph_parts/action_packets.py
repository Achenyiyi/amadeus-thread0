from __future__ import annotations

import hashlib
from typing import Any

from .tool_policies import MEMORY_WRITE_TOOLS

_VALID_ORIGINS = {"motive_goal", "own_rhythm", "counterpart_request", "capability_upgrade"}
_VALID_STATUSES = {
    "proposed",
    "queued",
    "awaiting_approval",
    "approved",
    "rejected",
    "executing",
    "completed",
    "blocked",
}
_VALID_RISKS = {"read", "memory_write", "external_mutation"}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _clean_text(value: Any, *, limit: int = 220) -> str:
    text = str(value or "").strip()
    return text[:limit]


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _normalize_source_ref_ids(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    out: list[int] = []
    for item in value:
        sid = _coerce_int(item, 0)
        if sid > 0:
            out.append(sid)
    return out[:8]


def normalize_artifact_context(value: Any) -> dict[str, Any]:
    row = _dict_or_empty(value)
    if not row:
        return {}
    preview_raw = str(row.get("preview") or row.get("artifact_preview") or "").strip()
    preview = preview_raw[:1200]
    preview_truncated = _coerce_bool(
        row.get("preview_truncated"),
        _coerce_bool(row.get("artifact_preview_truncated"), len(preview_raw) > len(preview)),
    )
    normalized = {
        "carrier": _clean_text(row.get("carrier")),
        "artifact_kind": _clean_text(row.get("artifact_kind")).lower(),
        "artifact_ref": _clean_text(row.get("artifact_ref"), limit=320),
        "artifact_label": _clean_text(row.get("artifact_label"), limit=160),
        "reacquisition_mode": _clean_text(row.get("reacquisition_mode") or row.get("artifact_reacquisition_mode")).lower(),
        "preview": preview,
        "preview_truncated": preview_truncated,
        "exists": _coerce_bool(row.get("exists"), _coerce_bool(row.get("artifact_exists"), False)),
        "size_bytes": max(0, _coerce_int(row.get("size_bytes") if "size_bytes" in row else row.get("artifact_size_bytes"), 0)),
        "updated_at": max(0, _coerce_int(row.get("updated_at") if "updated_at" in row else row.get("artifact_updated_at"), 0)),
        "source_ref_ids": _normalize_source_ref_ids(row.get("source_ref_ids")),
        "source_url": _clean_text(row.get("source_url"), limit=320),
        "source_query": _clean_text(row.get("source_query"), limit=220),
        "source_title": _clean_text(row.get("source_title"), limit=160),
        "source_tool_name": _clean_text(row.get("source_tool_name") or row.get("tool_name"), limit=80),
    }
    if any(
        (
            normalized["carrier"],
            normalized["artifact_kind"],
            normalized["artifact_ref"],
            normalized["artifact_label"],
            normalized["reacquisition_mode"],
            normalized["preview"],
            normalized["preview_truncated"],
            normalized["exists"],
            normalized["size_bytes"] > 0,
            normalized["updated_at"] > 0,
            bool(normalized["source_ref_ids"]),
            normalized["source_url"],
            normalized["source_query"],
            normalized["source_title"],
            normalized["source_tool_name"],
        )
    ):
        return normalized
    return {}


def compact_artifact_identity(value: Any) -> dict[str, Any]:
    artifact = normalize_artifact_context(value)
    if not artifact:
        return {}
    normalized = {
        "artifact_carrier": _clean_text(artifact.get("carrier"), limit=64).lower(),
        "artifact_source_ref_ids": _normalize_source_ref_ids(artifact.get("source_ref_ids")),
        "artifact_source_url": _clean_text(artifact.get("source_url"), limit=320),
        "artifact_source_query": _clean_text(artifact.get("source_query"), limit=220),
        "artifact_source_title": _clean_text(artifact.get("source_title"), limit=160),
        "artifact_source_tool_name": _clean_text(artifact.get("source_tool_name"), limit=80).lower(),
    }
    if any(
        (
            normalized["artifact_carrier"],
            bool(normalized["artifact_source_ref_ids"]),
            normalized["artifact_source_url"],
            normalized["artifact_source_query"],
            normalized["artifact_source_title"],
            normalized["artifact_source_tool_name"],
        )
    ):
        return normalized
    return {}


def make_proposal_id(*parts: Any) -> str:
    seed = "|".join(_clean_text(part, limit=160) for part in parts if _clean_text(part, limit=160))
    if not seed:
        seed = "action-packet"
    digest = hashlib.sha1(seed.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"ap-{digest}"


def normalize_capability_steps(steps: Any) -> list[dict[str, Any]]:
    if not isinstance(steps, list):
        return []
    out: list[dict[str, Any]] = []
    for item in steps:
        row = _dict_or_empty(item)
        kind = _clean_text(row.get("kind"))
        name = _clean_text(row.get("name"))
        target = _clean_text(row.get("target"))
        note = _clean_text(row.get("note"))
        status = _clean_text(row.get("status")).lower() or "pending"
        requires_approval = _coerce_bool(row.get("requires_approval"), False)
        if not any((kind, name, target, note)):
            continue
        out.append(
            {
                "kind": kind or "action",
                "name": name,
                "target": target,
                "status": status,
                "requires_approval": requires_approval,
                "note": note,
            }
        )
    return out


def action_packet_has_signal(packet: Any) -> bool:
    if not isinstance(packet, dict) or not packet:
        return False
    for key in (
        "proposal_id",
        "origin",
        "intent",
        "status",
        "risk",
        "expected_effect",
        "result_summary",
        "linked_queue_id",
        "tool_name",
        "block_reason",
    ):
        if _clean_text(packet.get(key)):
            return True
    if _coerce_bool(packet.get("requires_approval"), False):
        return True
    if _coerce_bool(packet.get("writeback_ready"), False):
        return True
    if normalize_artifact_context(packet.get("artifact_context")):
        return True
    return bool(normalize_capability_steps(packet.get("capability_steps")))


def normalize_action_packet(packet: Any) -> dict[str, Any]:
    row = _dict_or_empty(packet)
    if not action_packet_has_signal(row):
        return {}
    origin = _clean_text(row.get("origin")).lower()
    if origin not in _VALID_ORIGINS:
        origin = "motive_goal"
    intent = _clean_text(row.get("intent")).lower() or "respond"
    status = _clean_text(row.get("status")).lower() or "proposed"
    if status not in _VALID_STATUSES:
        status = "proposed"
    risk = _clean_text(row.get("risk")).lower() or "read"
    if risk not in _VALID_RISKS:
        risk = "read"
    capability_steps = normalize_capability_steps(row.get("capability_steps"))
    expected_effect = _clean_text(row.get("expected_effect"))
    result_summary = _clean_text(row.get("result_summary"))
    linked_queue_id = _clean_text(row.get("linked_queue_id"))
    tool_name = _clean_text(row.get("tool_name"))
    block_reason = _clean_text(row.get("block_reason"))
    artifact_context = normalize_artifact_context(row.get("artifact_context"))
    requires_approval = _coerce_bool(row.get("requires_approval"), risk != "read")
    writeback_ready = _coerce_bool(row.get("writeback_ready"), status == "completed")
    proposal_id = _clean_text(row.get("proposal_id")) or make_proposal_id(
        origin,
        intent,
        status,
        linked_queue_id,
        tool_name,
        expected_effect,
    )
    return {
        "proposal_id": proposal_id,
        "origin": origin,
        "intent": intent,
        "status": status,
        "risk": risk,
        "requires_approval": requires_approval,
        "capability_steps": capability_steps,
        "expected_effect": expected_effect,
        "result_summary": result_summary,
        "writeback_ready": writeback_ready,
        "linked_queue_id": linked_queue_id,
        "tool_name": tool_name,
        "block_reason": block_reason,
        "artifact_context": artifact_context,
    }


def normalize_action_packets(packets: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    by_id: dict[str, int] = {}
    for item in _list_or_empty(packets):
        packet = normalize_action_packet(item)
        if not packet:
            continue
        proposal_id = str(packet.get("proposal_id") or "").strip()
        if proposal_id and proposal_id in by_id:
            out[by_id[proposal_id]] = packet
            continue
        by_id[proposal_id] = len(out)
        out.append(packet)
    return out


def derive_action_packet_origin(
    *,
    current_event: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None,
    behavior_plan: dict[str, Any] | None,
) -> str:
    event = _dict_or_empty(current_event)
    action = _dict_or_empty(behavior_action)
    plan = _dict_or_empty(behavior_plan)
    event_kind = _clean_text(event.get("kind")).lower()
    trigger_family = _clean_text(plan.get("trigger_family")).lower()
    if event_kind in {"self_activity_state", "time_idle", "scheduled_checkin_due", "scheduled_life_due"}:
        return "own_rhythm"
    if trigger_family in {"life_window", "small_opening", "self_activity", "shared_activity_window"}:
        return "own_rhythm"
    if event_kind in {"user_utterance", "gesture_signal"}:
        return "counterpart_request"
    if _clean_text(action.get("primary_motive")) or _clean_text(plan.get("primary_motive")):
        return "motive_goal"
    return "motive_goal"


def derive_action_packet_intent(
    *,
    behavior_action: dict[str, Any] | None,
    behavior_plan: dict[str, Any] | None,
) -> str:
    action = _dict_or_empty(behavior_action)
    plan = _dict_or_empty(behavior_plan)
    plan_kind = _clean_text(plan.get("kind")).lower()
    if plan_kind:
        return plan_kind
    followup_intent = _clean_text(action.get("followup_intent")).lower()
    if followup_intent:
        return followup_intent
    interaction_mode = _clean_text(action.get("interaction_mode")).lower()
    if interaction_mode:
        return interaction_mode
    return "respond"


def build_behavior_action_packet(
    *,
    current_event: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None,
    behavior_plan: dict[str, Any] | None,
    behavior_queue: Any,
    agenda_lifecycle_residue: dict[str, Any] | None = None,
) -> dict[str, Any]:
    action = _dict_or_empty(behavior_action)
    plan = _dict_or_empty(behavior_plan)
    queue = normalize_action_packets(
        [
            {
                "proposal_id": item.get("agenda_id"),
                "intent": item.get("kind"),
                "status": item.get("status") or "queued",
                "expected_effect": item.get("goal_frame") or item.get("note"),
                "linked_queue_id": item.get("agenda_id"),
            }
            for item in _list_or_empty(behavior_queue)
            if isinstance(item, dict) and (_clean_text(item.get("kind")) or _clean_text(item.get("agenda_id")))
        ]
    )
    linked_queue_id = str(queue[0].get("proposal_id") or "") if queue else ""
    intent = derive_action_packet_intent(behavior_action=action, behavior_plan=plan)
    origin = derive_action_packet_origin(
        current_event=current_event,
        behavior_action=action,
        behavior_plan=plan,
    )
    expected_effect = _clean_text(plan.get("goal_frame") or action.get("goal_frame") or plan.get("note") or action.get("note"))
    if not any((intent, expected_effect, linked_queue_id, _clean_text(action.get("interaction_mode")))):
        return {}
    status = "queued" if _clean_text(plan.get("kind")) or linked_queue_id else "proposed"
    capability_steps = [
        {
            "kind": "speak",
            "name": _clean_text(action.get("interaction_mode")) or "reply",
            "target": _clean_text(action.get("action_target")) or _clean_text(plan.get("target")),
            "status": "pending",
            "requires_approval": False,
            "note": _clean_text(action.get("goal_frame") or plan.get("goal_frame")),
        }
    ]
    if _clean_text(plan.get("kind")) or linked_queue_id:
        capability_steps.append(
            {
                "kind": "queue",
                "name": _clean_text(plan.get("kind")) or "behavior_queue",
                "target": _clean_text(plan.get("target")) or linked_queue_id,
                "status": status,
                "requires_approval": False,
                "note": _clean_text(plan.get("trigger_family") or plan.get("note")),
            }
        )
    packet = {
        "proposal_id": make_proposal_id(
            _clean_text(current_event and current_event.get("kind")),
            intent,
            _clean_text(plan.get("kind")),
            _clean_text(action.get("interaction_mode")),
            linked_queue_id,
        ),
        "origin": origin,
        "intent": intent,
        "status": status,
        "risk": "read",
        "requires_approval": False,
        "capability_steps": capability_steps,
        "expected_effect": expected_effect,
        "result_summary": _clean_text(agenda_lifecycle_residue and agenda_lifecycle_residue.get("note")),
        "writeback_ready": False,
        "linked_queue_id": linked_queue_id,
    }
    return normalize_action_packet(packet)


def risk_from_tool_name(name: str) -> str:
    tool_name = _clean_text(name).lower()
    if tool_name in MEMORY_WRITE_TOOLS:
        return "memory_write"
    if tool_name == "request_toolset_upgrade":
        return "read"
    return "external_mutation"


def build_tool_action_packet(
    *,
    tool_name: str,
    proposal_id: str = "",
    args: dict[str, Any] | None = None,
    action: str = "",
    status: str = "",
    result_summary: str = "",
    block_reason: str = "",
) -> dict[str, Any]:
    name = _clean_text(tool_name)
    risk = risk_from_tool_name(name)
    packet_status = _clean_text(status).lower() or ("awaiting_approval" if action == "approve" else "proposed")
    if packet_status not in _VALID_STATUSES:
        packet_status = "proposed"
    requires_approval = risk != "read"
    intent = "toolset_upgrade_proposal" if name == "request_toolset_upgrade" else f"tool:{name.lower()}"
    return normalize_action_packet(
        {
            "proposal_id": proposal_id or make_proposal_id(name, action, result_summary),
            "origin": "capability_upgrade" if name == "request_toolset_upgrade" else "motive_goal",
            "intent": intent,
            "status": packet_status,
            "risk": risk,
            "requires_approval": requires_approval,
            "capability_steps": [
                {
                    "kind": "tool_call",
                    "name": name,
                    "target": _clean_text((_dict_or_empty(args)).get("target")),
                    "status": packet_status,
                    "requires_approval": requires_approval,
                    "note": _clean_text((_dict_or_empty(args)).get("reason") or (_dict_or_empty(args)).get("query")),
                }
            ],
            "expected_effect": _clean_text((_dict_or_empty(args)).get("reason") or (_dict_or_empty(args)).get("query")),
            "result_summary": result_summary,
            "writeback_ready": packet_status == "completed",
            "tool_name": name,
            "block_reason": block_reason,
        }
    )


def upsert_action_packet(packets: Any, packet: Any) -> list[dict[str, Any]]:
    rows = normalize_action_packets(packets)
    normalized = normalize_action_packet(packet)
    if not normalized:
        return rows
    proposal_id = str(normalized.get("proposal_id") or "").strip()
    for idx, existing in enumerate(rows):
        if str(existing.get("proposal_id") or "").strip() == proposal_id:
            rows[idx] = normalized
            return rows
    rows.append(normalized)
    return rows


__all__ = [
    "action_packet_has_signal",
    "build_behavior_action_packet",
    "build_tool_action_packet",
    "compact_artifact_identity",
    "derive_action_packet_intent",
    "derive_action_packet_origin",
    "make_proposal_id",
    "normalize_action_packet",
    "normalize_action_packets",
    "normalize_artifact_context",
    "normalize_capability_steps",
    "risk_from_tool_name",
    "upsert_action_packet",
]
