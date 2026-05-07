from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..graph_parts.action_packets import normalize_action_packet, normalize_action_packets
from .multimodal_sources import (
    normalize_multimodal_inspection_preview,
    normalize_multimodal_inspection_result,
    normalize_multimodal_inspection_spec,
)


APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_READY = (
    "approved_artifact_multimodal_runtime_phase1_ready"
)
APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_IN_PROGRESS = (
    "approved_artifact_multimodal_runtime_phase1_in_progress"
)

AUTHORITY_BOUNDARY = {
    "persona_core_mutation_allowed": False,
    "memory_write_allowed": False,
    "external_mutation_allowed": False,
    "live_microphone_enabled": False,
    "live_camera_enabled": False,
    "background_screen_capture_enabled": False,
    "live_capture_allowed": False,
    "multimodal_model_api_called": False,
    "multimodal_model_api_call_allowed": False,
    "skill_registry_write_allowed": False,
    "frontend_semantics_owner": False,
}

UNSAFE_RESULT_FLAGS = {
    "model_api_called": "model_api_called_not_allowed",
    "model_api_call_allowed": "model_api_call_allowed_not_allowed",
    "model_api_call_planned": "model_api_call_planned_not_allowed",
    "live_capture_used": "live_capture_used_not_allowed",
    "live_capture_allowed": "live_capture_allowed_not_allowed",
    "background_capture_used": "background_capture_used_not_allowed",
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _clean(value: Any, *, lower: bool = False) -> str:
    text = str(value or "").strip()
    return text.lower() if lower else text


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


def _approval_status(value: dict[str, Any]) -> str:
    return _clean(
        value.get("approval_status")
        or value.get("status")
        or value.get("decision")
        or value.get("operator_decision"),
        lower=True,
    )


def _result_summary(result: dict[str, Any]) -> str:
    for key in ("semantic_summary", "caption", "observed_text", "ocr_text", "transcript"):
        text = _clean(result.get(key))
        if text:
            return text[:220]
    return ""


def _add_failure(failures: list[str], reason: str) -> None:
    if reason and reason not in failures:
        failures.append(reason)


def _field_drift(
    failures: list[str],
    *,
    result: dict[str, Any],
    spec: dict[str, Any],
    field: str,
) -> None:
    result_value = _clean(result.get(field))
    spec_value = _clean(spec.get(field))
    if result_value and spec_value and result_value != spec_value:
        _add_failure(failures, f"{field}_drift")


def _readback(
    *,
    overall_status: str,
    completed_packet: dict[str, Any] | None,
    pending_packet: dict[str, Any] | None,
    approval: dict[str, Any] | None,
    result: dict[str, Any] | None,
    failure_reasons: list[str],
) -> dict[str, Any]:
    ready = overall_status == "passed"
    return {
        "schema": "approved_artifact_multimodal_runtime.v1",
        "overall_status": overall_status,
        "readiness_status": (
            APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_READY
            if ready
            else APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_IN_PROGRESS
        ),
        "completed_packet": completed_packet or {},
        "pending_packet": pending_packet or {},
        "approval": approval or {},
        "approved_result": result or {},
        "summary": {
            "completed_count": 1 if completed_packet else 0,
            "failed_count": 0 if ready else 1,
            "failure_count": len(failure_reasons),
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "failure_reasons": list(failure_reasons),
    }


def build_approved_artifact_multimodal_runtime_readback(
    packet: dict[str, Any] | None,
    *,
    approval: dict[str, Any] | None = None,
    approved_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = normalize_action_packet(packet)
    approval_row = _dict_or_empty(approval)
    raw_result = _dict_or_empty(approved_result)
    failures: list[str] = []

    if not normalized:
        _add_failure(failures, "missing_packet")
        return _readback(
            overall_status="in_progress",
            completed_packet=None,
            pending_packet={},
            approval=approval_row,
            result={},
            failure_reasons=failures,
        )

    proposal_id = _clean(normalized.get("proposal_id"))
    if not proposal_id:
        _add_failure(failures, "missing_proposal_id")
    if _clean(normalized.get("intent"), lower=True) != "artifact:inspect_multimodal":
        _add_failure(failures, "unsupported_packet_intent")

    approval_proposal_id = _clean(approval_row.get("proposal_id"))
    if approval_proposal_id and proposal_id and approval_proposal_id != proposal_id:
        _add_failure(failures, "approval_proposal_id_drift")
    status = _approval_status(approval_row)
    if status != "approved":
        _add_failure(failures, "approval_not_approved")

    packet_status = _clean(normalized.get("status"), lower=True)
    if packet_status not in {"awaiting_approval", "approved"}:
        _add_failure(failures, "packet_status_not_approvable")

    spec = normalize_multimodal_inspection_spec(normalized.get("multimodal_inspection_spec"))
    preview = normalize_multimodal_inspection_preview(normalized.get("multimodal_inspection_preview"))
    if not spec:
        _add_failure(failures, "missing_multimodal_inspection_spec")
    if not preview:
        _add_failure(failures, "missing_multimodal_inspection_preview")
    if _coerce_bool(spec.get("model_api_call_allowed"), False):
        _add_failure(failures, "spec_model_api_call_allowed")
    if _coerce_bool(spec.get("live_capture_allowed"), False):
        _add_failure(failures, "spec_live_capture_allowed")
    if _coerce_bool(preview.get("auto_execute"), False):
        _add_failure(failures, "preview_auto_execute_not_allowed")
    if _coerce_bool(preview.get("model_api_call_planned"), False):
        _add_failure(failures, "preview_model_api_call_planned")
    if _coerce_bool(preview.get("live_capture_allowed"), False):
        _add_failure(failures, "preview_live_capture_allowed")

    if _clean(raw_result.get("proposal_id")) and _clean(raw_result.get("proposal_id")) != proposal_id:
        _add_failure(failures, "result_proposal_id_drift")
    for flag, reason in UNSAFE_RESULT_FLAGS.items():
        if _coerce_bool(raw_result.get(flag), False):
            _add_failure(failures, reason)

    result_seed = {
        "status": "completed",
        "approval_status": "approved",
        "source_ref_id": spec.get("source_ref_id"),
        "modality": spec.get("modality"),
        "artifact_ref": spec.get("artifact_ref"),
        "artifact_label": spec.get("artifact_label"),
    }
    result_seed.update(raw_result)
    result_seed.pop("proposal_id", None)
    result = normalize_multimodal_inspection_result(result_seed)
    if not result:
        _add_failure(failures, "missing_approved_result")
    if result.get("status") != "completed":
        _add_failure(failures, "result_not_completed")
    if result.get("approval_status") != "approved":
        _add_failure(failures, "result_not_approved")
    if not _result_summary(result):
        _add_failure(failures, "missing_semantic_result")
    if result.get("source") not in {"", "approved_inspection_result"}:
        _add_failure(failures, "unsupported_result_source")

    for field in ("source_ref_id", "modality", "artifact_ref", "artifact_label"):
        _field_drift(failures, result=result, spec=spec, field=field)

    if failures:
        return _readback(
            overall_status="in_progress",
            completed_packet=None,
            pending_packet=normalized,
            approval=approval_row,
            result=result,
            failure_reasons=failures,
        )

    completed = dict(normalized)
    completed.update(
        {
            "status": "completed",
            "requires_approval": False,
            "writeback_ready": True,
            "result_summary": _result_summary(result),
            "multimodal_inspection_spec": spec,
            "multimodal_inspection_preview": preview,
            "multimodal_inspection_result": result,
        }
    )
    completed_steps: list[dict[str, Any]] = []
    for item in _list_or_empty(completed.get("capability_steps")):
        step = _dict_or_empty(item)
        if not step:
            continue
        step["status"] = "completed"
        step["requires_approval"] = False
        completed_steps.append(step)
    completed["capability_steps"] = completed_steps
    completed = normalize_action_packet(completed)

    return _readback(
        overall_status="passed",
        completed_packet=completed,
        pending_packet=normalized,
        approval=approval_row,
        result=result,
        failure_reasons=[],
    )


def _rows_by_proposal_id(rows: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row_value in _list_or_empty(rows):
        row = _dict_or_empty(row_value)
        proposal_id = _clean(row.get("proposal_id"))
        if proposal_id:
            indexed[proposal_id] = row
    return indexed


def _aggregate_readbacks(readbacks: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [
        _dict_or_empty(row.get("completed_packet"))
        for row in readbacks
        if _dict_or_empty(row.get("completed_packet"))
    ]
    failed = [row for row in readbacks if str(row.get("overall_status") or "") != "passed"]
    failure_reasons: list[str] = []
    for row in failed:
        for reason in _list_or_empty(row.get("failure_reasons")):
            _add_failure(failure_reasons, str(reason))
    ready = bool(completed) and not failed
    return {
        "schema": "approved_artifact_multimodal_runtime.v1",
        "overall_status": "passed" if ready else "in_progress",
        "readiness_status": (
            APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_READY
            if ready
            else APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_IN_PROGRESS
        ),
        "summary": {
            "packet_count": len(readbacks),
            "completed_count": len(completed),
            "failed_count": len(failed),
            "failure_count": len(failure_reasons),
        },
        "completed_packets": completed,
        "scenario_readbacks": readbacks,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "failure_reasons": failure_reasons,
    }


def apply_approved_artifact_multimodal_runtime_to_payload(
    payload: dict[str, Any] | None,
    *,
    approvals: list[dict[str, Any]] | None = None,
    approved_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    data = deepcopy(_dict_or_empty(payload))
    approval_by_id = _rows_by_proposal_id(approvals)
    result_by_id = _rows_by_proposal_id(approved_results)
    next_packets: list[dict[str, Any]] = []
    readbacks: list[dict[str, Any]] = []

    for packet in normalize_action_packets(data.get("action_packets")):
        if _clean(packet.get("intent"), lower=True) != "artifact:inspect_multimodal":
            next_packets.append(packet)
            continue
        proposal_id = _clean(packet.get("proposal_id"))
        approval = approval_by_id.get(proposal_id)
        result = result_by_id.get(proposal_id)
        if not approval or not result:
            next_packets.append(packet)
            continue
        readback = build_approved_artifact_multimodal_runtime_readback(
            packet,
            approval=approval,
            approved_result=result,
        )
        readbacks.append(readback)
        completed = _dict_or_empty(readback.get("completed_packet"))
        next_packets.append(completed or packet)

    data["action_packets"] = next_packets
    data["approved_artifact_multimodal_runtime"] = _aggregate_readbacks(readbacks)
    return data


def compact_approved_artifact_multimodal_runtime_line(readback: dict[str, Any] | None) -> str:
    data = _dict_or_empty(readback)
    summary = _dict_or_empty(data.get("summary"))
    return " | ".join(
        [
            f"approved_artifact_multimodal={_clean(data.get('readiness_status')) or 'unknown'}",
            f"completed={int(summary.get('completed_count') or 0)}",
            f"failed={int(summary.get('failed_count') or 0)}",
            "live_capture=false",
            "model_api=false",
        ]
    )


__all__ = [
    "APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_IN_PROGRESS",
    "APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_READY",
    "AUTHORITY_BOUNDARY",
    "apply_approved_artifact_multimodal_runtime_to_payload",
    "build_approved_artifact_multimodal_runtime_readback",
    "compact_approved_artifact_multimodal_runtime_line",
]
