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
    seen: set[int] = set()
    for item in value:
        sid = _coerce_int(item, 0)
        if sid > 0 and sid not in seen:
            seen.add(sid)
            out.append(sid)
    return out[:8]


def _preferred_first_source_ref_ids(ids: list[int], preferred_source_ref_id: int) -> list[int]:
    ordered = [sid for sid in ids if sid > 0]
    preferred = max(0, int(preferred_source_ref_id or 0))
    if preferred <= 0 or preferred not in ordered:
        return ordered[:8]
    return [preferred, *[sid for sid in ordered if sid != preferred]][:8]


def _normalize_tool_args(value: Any, *, depth: int = 0) -> dict[str, Any]:
    if not isinstance(value, dict) or depth > 4:
        return {}
    normalized: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = _clean_text(raw_key, limit=80)
        if not key:
            continue
        if raw_value is None or isinstance(raw_value, (str, int, float, bool)):
            normalized[key] = raw_value
            continue
        if isinstance(raw_value, dict):
            child = _normalize_tool_args(raw_value, depth=depth + 1)
            if child:
                normalized[key] = child
            continue
        if isinstance(raw_value, list):
            items: list[Any] = []
            for item in raw_value[:32]:
                if item is None or isinstance(item, (str, int, float, bool)):
                    items.append(item)
                elif isinstance(item, dict):
                    child = _normalize_tool_args(item, depth=depth + 1)
                    if child:
                        items.append(child)
                elif isinstance(item, list) and depth < 4:
                    nested = []
                    for nested_item in item[:32]:
                        if nested_item is None or isinstance(nested_item, (str, int, float, bool)):
                            nested.append(nested_item)
                    if nested:
                        items.append(nested)
            if items:
                normalized[key] = items
            continue
        normalized[key] = str(raw_value)
    return normalized


def normalize_mutation_preview(value: Any) -> dict[str, Any]:
    row = _dict_or_empty(value)
    if not row:
        return {}
    normalized = {
        "tool_name": _clean_text(row.get("tool_name"), limit=80).lower(),
        "can_apply": _coerce_bool(row.get("can_apply"), False),
        "mutation_mode": _clean_text(row.get("mutation_mode"), limit=32).lower(),
        "workspace_name": _clean_text(row.get("workspace_name"), limit=120),
        "relative_path": _clean_text(row.get("relative_path"), limit=220),
        "file_path": _clean_text(row.get("file_path"), limit=320),
        "file_name": _clean_text(row.get("file_name"), limit=160),
        "target_exists": _coerce_bool(row.get("target_exists"), False),
        "created_new": _coerce_bool(row.get("created_new"), False),
        "start_line": max(0, _coerce_int(row.get("start_line"), 0)),
        "end_line": max(0, _coerce_int(row.get("end_line"), 0)),
        "match_count": max(0, _coerce_int(row.get("match_count"), 0)),
        "replace_count": max(0, _coerce_int(row.get("replace_count"), 0)),
        "replaced_line_count": max(0, _coerce_int(row.get("replaced_line_count"), 0)),
        "inserted_line_count": max(0, _coerce_int(row.get("inserted_line_count"), 0)),
        "appended_bytes": max(0, _coerce_int(row.get("appended_bytes"), 0)),
        "error_code": _clean_text(row.get("error_code"), limit=64).upper(),
        "error_message": _clean_text(row.get("error_message")),
        "summary": _clean_text(row.get("summary")),
        "preview_truncated": _coerce_bool(row.get("preview_truncated"), False),
        "diff_preview": _clean_text(row.get("diff_preview"), limit=1600),
    }
    if any(
        (
            normalized["tool_name"],
            normalized["can_apply"],
            normalized["mutation_mode"],
            normalized["workspace_name"],
            normalized["relative_path"],
            normalized["file_path"],
            normalized["file_name"],
            normalized["target_exists"],
            normalized["created_new"],
            normalized["start_line"] > 0,
            normalized["end_line"] > 0,
            normalized["match_count"] > 0,
            normalized["replace_count"] > 0,
            normalized["replaced_line_count"] > 0,
            normalized["inserted_line_count"] > 0,
            normalized["appended_bytes"] > 0,
            normalized["error_code"],
            normalized["error_message"],
            normalized["summary"],
            normalized["preview_truncated"],
            normalized["diff_preview"],
        )
    ):
        return normalized
    return {}


def normalize_execution_spec(value: Any) -> dict[str, Any]:
    row = _dict_or_empty(value)
    if not row:
        return {}
    argv = [str(item).strip() for item in _list_or_empty(row.get("argv")) if str(item or "").strip()][:64]
    allowed_roots = [_clean_text(item, limit=320) for item in _list_or_empty(row.get("allowed_roots")) if _clean_text(item, limit=320)][:8]
    expected_artifacts = [
        _clean_text(item, limit=320).replace("\\", "/")
        for item in _list_or_empty(row.get("expected_artifacts"))
        if _clean_text(item, limit=320)
    ][:16]
    normalized = {
        "executor": _clean_text(row.get("executor"), limit=64).lower(),
        "profile": _clean_text(row.get("profile"), limit=64).lower(),
        "argv": argv,
        "cwd": _clean_text(row.get("cwd"), limit=320),
        "allowed_roots": allowed_roots,
        "timeout_s": max(0, _coerce_int(row.get("timeout_s"), 0)),
        "writes_expected": _coerce_bool(row.get("writes_expected"), False),
        "expected_artifacts": expected_artifacts,
    }
    if any(
        (
            normalized["executor"],
            normalized["profile"],
            normalized["argv"],
            normalized["cwd"],
            normalized["allowed_roots"],
            normalized["timeout_s"] > 0,
            normalized["writes_expected"],
            normalized["expected_artifacts"],
        )
    ):
        return normalized
    return {}


def normalize_execution_preview(value: Any) -> dict[str, Any]:
    row = _dict_or_empty(value)
    if not row:
        return {}
    argv = [str(item).strip() for item in _list_or_empty(row.get("argv")) if str(item or "").strip()][:64]
    allowed_roots = [_clean_text(item, limit=320) for item in _list_or_empty(row.get("allowed_roots")) if _clean_text(item, limit=320)][:8]
    expected_artifacts = [
        _clean_text(item, limit=320).replace("\\", "/")
        for item in _list_or_empty(row.get("expected_artifacts"))
        if _clean_text(item, limit=320)
    ][:16]
    normalized = {
        "runner_kind": _clean_text(row.get("runner_kind"), limit=80).lower(),
        "isolation_level": _clean_text(row.get("isolation_level"), limit=80).lower(),
        "argv": argv,
        "cwd": _clean_text(row.get("cwd"), limit=320),
        "allowed_roots": allowed_roots,
        "timeout_s": max(0, _coerce_int(row.get("timeout_s"), 0)),
        "writes_expected": _coerce_bool(row.get("writes_expected"), False),
        "expected_artifacts": expected_artifacts,
    }
    if any(
        (
            normalized["runner_kind"],
            normalized["isolation_level"],
            normalized["argv"],
            normalized["cwd"],
            normalized["allowed_roots"],
            normalized["timeout_s"] > 0,
            normalized["writes_expected"],
            normalized["expected_artifacts"],
        )
    ):
        return normalized
    return {}


def normalize_execution_result(value: Any) -> dict[str, Any]:
    row = _dict_or_empty(value)
    if not row:
        return {}
    produced_artifacts = [
        _clean_text(item, limit=320)
        for item in _list_or_empty(row.get("produced_artifacts"))
        if _clean_text(item, limit=320)
    ][:16]
    normalized = {
        "run_id": _clean_text(row.get("run_id"), limit=128),
        "status": _clean_text(row.get("status"), limit=32).lower(),
        "exit_code": _coerce_int(row.get("exit_code"), 0),
        "duration_ms": max(0, _coerce_int(row.get("duration_ms"), 0)),
        "stdout_log_ref": _clean_text(row.get("stdout_log_ref"), limit=320),
        "stderr_log_ref": _clean_text(row.get("stderr_log_ref"), limit=320),
        "produced_artifacts": produced_artifacts,
        "error_summary": _clean_text(row.get("error_summary")),
    }
    if any(
        (
            normalized["run_id"],
            normalized["status"],
            normalized["exit_code"] != 0,
            normalized["duration_ms"] > 0,
            normalized["stdout_log_ref"],
            normalized["stderr_log_ref"],
            normalized["produced_artifacts"],
            normalized["error_summary"],
        )
    ):
        return normalized
    return {}


def _normalize_access_grants(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = _clean_text(item, limit=64).lower()
        if text and text not in out:
            out.append(text)
        if len(out) >= 8:
            break
    return out


def _coerce_ratio(value: Any) -> float:
    try:
        cast = float(value)
    except Exception:
        cast = 0.0
    return round(max(0.0, min(1.0, cast)), 3)


def normalize_access_acquire_proposal(value: Any) -> dict[str, Any]:
    row = _dict_or_empty(value)
    if not row:
        return {}
    target = _clean_text(row.get("target"), limit=64).lower()
    mode = _clean_text(row.get("mode"), limit=64).lower()
    path_kind = _clean_text(row.get("path_kind"), limit=32).lower()
    if path_kind not in {"acquire_existing", "create_new"}:
        path_kind = "acquire_existing"
    summary = _clean_text(row.get("summary"))
    operator_action = _clean_text(row.get("operator_action"))
    grants = _normalize_access_grants(row.get("grants"))
    requires_operator = _coerce_bool(row.get("requires_operator"), True)
    resolved_grants = [item for item in _normalize_access_grants(row.get("resolved_grants")) if item in grants]
    pending_grants = [
        item
        for item in _normalize_access_grants(row.get("pending_grants"))
        if item in grants and item not in resolved_grants
    ]
    if not any((target, mode, summary, operator_action, grants, requires_operator)):
        return {}
    normalized = {
        "target": target,
        "mode": mode,
        "path_kind": path_kind,
        "summary": summary,
        "operator_action": operator_action,
        "grants": grants,
        "requires_operator": requires_operator,
    }
    if grants and (resolved_grants or pending_grants or "completion_ratio" in row):
        normalized.update(
            {
                "resolved_grants": resolved_grants,
                "pending_grants": pending_grants,
                "completion_ratio": _coerce_ratio(row.get("completion_ratio")),
            }
        )
    return normalized


def normalize_access_acquire_proposals(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in value:
        proposal = normalize_access_acquire_proposal(item)
        if not proposal:
            continue
        key = (
            str(proposal.get("target") or "").strip(),
            str(proposal.get("mode") or "").strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(proposal)
        if len(merged) >= 8:
            break
    return merged


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
    source_ref_ids = _normalize_source_ref_ids(row.get("source_ref_ids"))
    preferred_source_ref_id = max(0, _coerce_int(row.get("preferred_source_ref_id"), 0))
    source_ref_ids = _preferred_first_source_ref_ids(source_ref_ids, preferred_source_ref_id)

    normalized = {
        "carrier": _clean_text(row.get("carrier")),
        "artifact_kind": _clean_text(row.get("artifact_kind")).lower(),
        "artifact_ref": _clean_text(row.get("artifact_ref"), limit=320),
        "artifact_label": _clean_text(row.get("artifact_label"), limit=160),
        "workspace_root": _clean_text(row.get("workspace_root"), limit=320),
        "reacquisition_mode": _clean_text(row.get("reacquisition_mode") or row.get("artifact_reacquisition_mode")).lower(),
        "preview": preview,
        "preview_truncated": preview_truncated,
        "exists": _coerce_bool(row.get("exists"), _coerce_bool(row.get("artifact_exists"), False)),
        "size_bytes": max(0, _coerce_int(row.get("size_bytes") if "size_bytes" in row else row.get("artifact_size_bytes"), 0)),
        "updated_at": max(0, _coerce_int(row.get("updated_at") if "updated_at" in row else row.get("artifact_updated_at"), 0)),
        "source_ref_ids": source_ref_ids,
        "preferred_source_ref_id": preferred_source_ref_id,
        "preferred_anchor_reason": _clean_text(row.get("preferred_anchor_reason"), limit=120).lower(),
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
            normalized["workspace_root"],
            normalized["reacquisition_mode"],
            normalized["preview"],
            normalized["preview_truncated"],
            normalized["exists"],
            normalized["size_bytes"] > 0,
            normalized["updated_at"] > 0,
            bool(normalized["source_ref_ids"]),
            normalized["preferred_source_ref_id"] > 0,
            normalized["preferred_anchor_reason"],
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
    preferred_source_ref_id = max(0, _coerce_int(artifact.get("preferred_source_ref_id"), 0))
    artifact_source_ref_ids = _preferred_first_source_ref_ids(
        _normalize_source_ref_ids(artifact.get("source_ref_ids")),
        preferred_source_ref_id,
    )
    normalized = {
        "artifact_carrier": _clean_text(artifact.get("carrier"), limit=64).lower(),
        "artifact_source_ref_ids": artifact_source_ref_ids,
        "preferred_source_ref_id": preferred_source_ref_id,
        "preferred_anchor_reason": _clean_text(artifact.get("preferred_anchor_reason"), limit=120).lower(),
        "artifact_source_url": _clean_text(artifact.get("source_url"), limit=320),
        "artifact_source_query": _clean_text(artifact.get("source_query"), limit=220),
        "artifact_source_title": _clean_text(artifact.get("source_title"), limit=160),
        "artifact_source_tool_name": _clean_text(artifact.get("source_tool_name"), limit=80).lower(),
    }
    if any(
        (
            normalized["artifact_carrier"],
            bool(normalized["artifact_source_ref_ids"]),
            normalized["preferred_source_ref_id"] > 0,
            normalized["preferred_anchor_reason"],
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
    if normalize_access_acquire_proposals(packet.get("access_acquire_proposals")):
        return True
    if normalize_access_acquire_proposal(packet.get("selected_access_proposal")):
        return True
    if normalize_mutation_preview(packet.get("mutation_preview")):
        return True
    if normalize_execution_spec(packet.get("execution_spec")):
        return True
    if normalize_execution_preview(packet.get("execution_preview")):
        return True
    if normalize_execution_result(packet.get("execution_result")):
        return True
    if _normalize_tool_args(packet.get("tool_args")):
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
    access_acquire_proposals = normalize_access_acquire_proposals(row.get("access_acquire_proposals"))
    selected_access_proposal = normalize_access_acquire_proposal(row.get("selected_access_proposal"))
    mutation_preview = normalize_mutation_preview(row.get("mutation_preview"))
    execution_spec = normalize_execution_spec(row.get("execution_spec"))
    execution_preview = normalize_execution_preview(row.get("execution_preview"))
    execution_result = normalize_execution_result(row.get("execution_result"))
    tool_args = _normalize_tool_args(row.get("tool_args"))
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
        "tool_args": tool_args,
        "block_reason": block_reason,
        "artifact_context": artifact_context,
        "access_acquire_proposals": access_acquire_proposals,
        "selected_access_proposal": selected_access_proposal,
        "mutation_preview": mutation_preview,
        "execution_spec": execution_spec,
        "execution_preview": execution_preview,
        "execution_result": execution_result,
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
    if tool_name in {
        "request_toolset_upgrade",
        "reacquire_artifact",
        "inspect_source_ref",
        "compare_source_refs",
        "inspect_workspace_path",
        "refresh_access_state",
    }:
        return "read"
    return "external_mutation"


def _tool_packet_intent(name: str) -> str:
    tool_name = _clean_text(name).lower()
    if tool_name == "request_toolset_upgrade":
        return "toolset_upgrade_proposal"
    if tool_name == "execute_workspace_command":
        return "sandbox:execute_workspace_command"
    return f"tool:{tool_name}"


def build_tool_action_packet(
    *,
    tool_name: str,
    proposal_id: str = "",
    args: dict[str, Any] | None = None,
    action: str = "",
    status: str = "",
    result_summary: str = "",
    block_reason: str = "",
    mutation_preview: dict[str, Any] | None = None,
    execution_spec: dict[str, Any] | None = None,
    execution_preview: dict[str, Any] | None = None,
    execution_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    name = _clean_text(tool_name)
    risk = risk_from_tool_name(name)
    packet_status = _clean_text(status).lower() or ("awaiting_approval" if action == "approve" else "proposed")
    if packet_status not in _VALID_STATUSES:
        packet_status = "proposed"
    requires_approval = risk != "read"
    intent = _tool_packet_intent(name)
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
            "tool_args": _dict_or_empty(args),
            "block_reason": block_reason,
            "mutation_preview": normalize_mutation_preview(mutation_preview),
            "execution_spec": normalize_execution_spec(execution_spec),
            "execution_preview": normalize_execution_preview(execution_preview),
            "execution_result": normalize_execution_result(execution_result),
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
    "normalize_access_acquire_proposal",
    "normalize_access_acquire_proposals",
    "normalize_action_packet",
    "normalize_action_packets",
    "normalize_artifact_context",
    "normalize_capability_steps",
    "normalize_execution_preview",
    "normalize_execution_result",
    "normalize_execution_spec",
    "normalize_mutation_preview",
    "risk_from_tool_name",
    "upsert_action_packet",
]
