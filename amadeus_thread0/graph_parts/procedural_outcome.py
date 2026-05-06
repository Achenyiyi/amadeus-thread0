from __future__ import annotations

import hashlib
from typing import Any

from .action_packets import normalize_action_packet


ALLOWED_PROCEDURAL_OUTCOME_KINDS = {
    "confirmed_success",
    "partial_success",
    "failed_execution",
    "blocked_boundary_reinforced",
    "manual_takeover_required",
    "stale_or_mismatched_context",
    "no_executed_attempt",
}

ALLOWED_ATTEMPT_STATUSES = {
    "completed",
    "executed",
    "blocked",
    "rejected",
    "expired",
    "awaiting_approval",
    "approved",
    "proposed",
    "queued",
    "executing",
    "pending",
}

NON_EXECUTED_ATTEMPT_STATUSES = {
    "rejected",
    "expired",
    "awaiting_approval",
    "approved",
    "proposed",
    "queued",
    "executing",
    "pending",
}

_OUTCOME_DELTAS = {
    "confirmed_success": 0.08,
    "partial_success": 0.02,
    "failed_execution": -0.12,
    "blocked_boundary_reinforced": -0.08,
    "manual_takeover_required": 0.0,
    "stale_or_mismatched_context": 0.0,
    "no_executed_attempt": 0.0,
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _clean_text(value: Any, *, limit: int = 220, lower: bool = False) -> str:
    text = str(value or "").strip()
    if lower:
        text = text.lower()
    return text[: max(1, int(limit))]


def _clean_text_list(value: Any, *, limit: int = 8, item_limit: int = 220) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in _list_or_empty(value):
        text = _clean_text(item, limit=item_limit)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _clamp(value: Any, *, minimum: float = -1.0, maximum: float = 1.0, default: float = 0.0) -> float:
    try:
        cast = float(value)
    except Exception:
        cast = float(default)
    return round(max(minimum, min(maximum, cast)), 3)


def _clamp01(value: Any, default: float = 0.0) -> float:
    return _clamp(value, minimum=0.0, maximum=1.0, default=default)


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _normalize_procedural_planning(value: Any) -> dict[str, Any]:
    from .procedural_planning import normalize_procedural_planning

    return normalize_procedural_planning(value)


def _normalize_procedural_trace(value: Any) -> dict[str, Any]:
    from .procedural_growth import normalize_procedural_trace

    return normalize_procedural_trace(value)


def _normalize_procedural_traces(value: Any) -> list[dict[str, Any]]:
    from .procedural_growth import normalize_procedural_traces

    return normalize_procedural_traces(value)


def _stable_outcome_id(seed: dict[str, Any]) -> str:
    parts = [
        _clean_text(seed.get("source_trace_id"), limit=80),
        _clean_text(seed.get("source_proposal_id"), limit=128),
        _clean_text(seed.get("source_run_id"), limit=128),
        _clean_text(seed.get("planning_bias_kind"), limit=80, lower=True),
        _clean_text(seed.get("source_tool_name"), limit=120, lower=True),
        _clean_text(seed.get("attempt_status"), limit=32, lower=True),
        _clean_text(seed.get("outcome_kind"), limit=80, lower=True),
    ]
    digest = hashlib.sha1("|".join(parts).encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"proc_out_{digest}"


def normalize_procedural_outcome(value: Any) -> dict[str, Any]:
    row = _dict_or_empty(value)
    if not row:
        return {}
    outcome_kind = _clean_text(row.get("outcome_kind"), limit=80, lower=True)
    if outcome_kind not in ALLOWED_PROCEDURAL_OUTCOME_KINDS:
        return {}
    attempt_status = _clean_text(row.get("attempt_status"), limit=32, lower=True)
    if attempt_status not in ALLOWED_ATTEMPT_STATUSES:
        return {}
    source_trace_id = _clean_text(row.get("source_trace_id"), limit=80)
    source_proposal_id = _clean_text(row.get("source_proposal_id"), limit=128)
    source_run_id = _clean_text(row.get("source_run_id"), limit=128)
    source_tool_name = _clean_text(row.get("source_tool_name"), limit=120, lower=True)
    evidence_refs = _clean_text_list(row.get("evidence_refs"), limit=8, item_limit=320)
    normalized: dict[str, Any] = {
        "outcome_id": _clean_text(row.get("outcome_id"), limit=80)
        if _clean_text(row.get("outcome_id"), limit=80).startswith("proc_out_")
        else "",
        "source_trace_id": source_trace_id,
        "source_proposal_id": source_proposal_id,
        "source_run_id": source_run_id,
        "planning_bias_kind": _clean_text(row.get("planning_bias_kind"), limit=80, lower=True),
        "source_tool_name": source_tool_name,
        "attempt_status": attempt_status,
        "outcome_kind": outcome_kind,
        "confidence_delta": _clamp(row.get("confidence_delta"), default=_OUTCOME_DELTAS.get(outcome_kind, 0.0)),
        "reuse_allowed": bool(row.get("reuse_allowed", False)),
        "boundary_reinforced": bool(row.get("boundary_reinforced", False)),
        "recovery_hint": _clean_text(row.get("recovery_hint"), limit=220),
        "evidence_refs": evidence_refs,
    }
    if not normalized["outcome_id"]:
        normalized["outcome_id"] = _stable_outcome_id(normalized)
    if not any((source_trace_id, source_proposal_id, source_run_id, source_tool_name, evidence_refs)):
        return {}
    return normalized


def _planning_from_packet(packet: dict[str, Any], fallback: Any) -> dict[str, Any]:
    tool_args = _dict_or_empty(packet.get("tool_args"))
    planning = _normalize_procedural_planning(tool_args.get("procedural_planning"))
    if planning:
        return planning
    return _normalize_procedural_planning(fallback)


def _trace_id_from_packet(packet: dict[str, Any], planning: dict[str, Any], traces: Any) -> str:
    trace_id = _clean_text(planning.get("trace_id"), limit=80)
    if trace_id:
        return trace_id
    proposal_id = _clean_text(packet.get("proposal_id"), limit=128)
    for trace in _normalize_procedural_traces(traces):
        if _clean_text(trace.get("source_proposal_id"), limit=128) == proposal_id:
            return _clean_text(trace.get("trace_id"), limit=80)
    return ""


def _execution_result(packet: dict[str, Any]) -> dict[str, Any]:
    return _dict_or_empty(packet.get("execution_result"))


def _browser_result(packet: dict[str, Any]) -> dict[str, Any]:
    return _dict_or_empty(packet.get("browser_execution_result"))


def _browser_preview(packet: dict[str, Any]) -> dict[str, Any]:
    return _dict_or_empty(packet.get("browser_execution_preview"))


def _source_run_id(packet: dict[str, Any]) -> str:
    execution = _execution_result(packet)
    browser = _browser_result(packet)
    return (
        _clean_text(execution.get("run_id"), limit=128)
        or _clean_text(browser.get("run_id"), limit=128)
        or _clean_text(packet.get("proposal_id"), limit=128)
    )


def _evidence_refs(packet: dict[str, Any], source_run_id: str) -> list[str]:
    execution = _execution_result(packet)
    browser = _browser_result(packet)
    refs = [
        source_run_id,
        execution.get("stdout_log_ref"),
        execution.get("stderr_log_ref"),
        *_list_or_empty(execution.get("produced_artifacts")),
        browser.get("download_path"),
        browser.get("url"),
    ]
    return _clean_text_list(refs, limit=8, item_limit=320)


def _manual_takeover(packet: dict[str, Any]) -> bool:
    browser = _browser_result(packet)
    preview = _browser_preview(packet)
    return bool(
        browser.get("manual_takeover_required", False)
        or preview.get("requires_manual_takeover", False)
        or _clean_text(browser.get("last_action_status"), limit=64, lower=True) == "manual_takeover_required"
        or "manual takeover" in _clean_text(packet.get("block_reason"), limit=220, lower=True)
        or "manual browser" in _clean_text(packet.get("block_reason"), limit=220, lower=True)
    )


def _execution_failed(packet: dict[str, Any]) -> bool:
    execution = _execution_result(packet)
    if not execution:
        return False
    result_status = _clean_text(execution.get("status"), limit=32, lower=True)
    return result_status in {"failed", "blocked", "error"} or _coerce_int(execution.get("exit_code"), 0) != 0


def _blocked_boundary(packet: dict[str, Any]) -> bool:
    if _clean_text(packet.get("status"), limit=32, lower=True) == "blocked":
        return True
    execution = _execution_result(packet)
    browser = _browser_result(packet)
    return bool(
        _clean_text(execution.get("status"), limit=32, lower=True) == "blocked"
        or _clean_text(browser.get("status"), limit=32, lower=True) == "blocked"
    )


def _result_summary(packet: dict[str, Any]) -> str:
    execution = _execution_result(packet)
    browser = _browser_result(packet)
    if _execution_failed(packet):
        return (
            _clean_text(execution.get("error_summary"), limit=220)
            or _clean_text(packet.get("result_summary"), limit=220)
        )
    return (
        _clean_text(packet.get("result_summary"), limit=220)
        or _clean_text(execution.get("error_summary"), limit=220)
        or _clean_text(browser.get("error_summary"), limit=220)
        or _clean_text(packet.get("block_reason"), limit=220)
    )


def _outcome_kind(packet: dict[str, Any]) -> str:
    status = _clean_text(packet.get("status"), limit=32, lower=True)
    if status in NON_EXECUTED_ATTEMPT_STATUSES:
        return "no_executed_attempt"
    if _manual_takeover(packet):
        return "manual_takeover_required"
    if _execution_failed(packet):
        return "failed_execution"
    if _blocked_boundary(packet):
        return "blocked_boundary_reinforced"
    if status in {"completed", "executed"}:
        return "confirmed_success"
    return "no_executed_attempt"


def _reuse_allowed(kind: str, packet: dict[str, Any]) -> bool:
    if kind == "confirmed_success":
        return True
    if kind == "partial_success":
        return _clean_text(packet.get("status"), limit=32, lower=True) in {"completed", "executed"}
    return False


def _boundary_reinforced(kind: str) -> bool:
    return kind in {"blocked_boundary_reinforced", "manual_takeover_required"}


def _recovery_hint(kind: str, packet: dict[str, Any]) -> str:
    if kind == "confirmed_success":
        return ""
    if kind == "no_executed_attempt":
        return "attempt did not execute; keep it as an unfulfilled intention"
    if kind == "manual_takeover_required":
        return "manual browser takeover is still required before continuing"
    summary = _result_summary(packet)
    if kind == "failed_execution":
        return summary or "execution failed; inspect result logs before reusing this procedure"
    if kind == "blocked_boundary_reinforced":
        return summary or "boundary was reinforced; avoid repeating the blocked action"
    if kind == "stale_or_mismatched_context":
        return "current context no longer matches this procedural trace"
    return summary


def derive_procedural_outcomes_from_action_packets(
    action_packets: Any,
    *,
    planning_bias: Any = None,
    traces: Any = None,
) -> list[dict[str, Any]]:
    outcomes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in _list_or_empty(action_packets):
        raw = _dict_or_empty(item)
        packet = normalize_action_packet(raw)
        if not packet:
            continue
        planning = _planning_from_packet(packet, planning_bias)
        trace_id = _trace_id_from_packet(packet, planning, traces)
        outcome_kind = _outcome_kind(packet)
        source_run_id = _source_run_id(packet)
        outcome = normalize_procedural_outcome(
            {
                "source_trace_id": trace_id,
                "source_proposal_id": packet.get("proposal_id"),
                "source_run_id": source_run_id,
                "planning_bias_kind": planning.get("bias_kind"),
                "source_tool_name": packet.get("tool_name"),
                "attempt_status": packet.get("status"),
                "outcome_kind": outcome_kind,
                "confidence_delta": _OUTCOME_DELTAS.get(outcome_kind, 0.0),
                "reuse_allowed": _reuse_allowed(outcome_kind, packet),
                "boundary_reinforced": _boundary_reinforced(outcome_kind),
                "recovery_hint": _recovery_hint(outcome_kind, packet),
                "evidence_refs": _evidence_refs(packet, source_run_id),
            }
        )
        if not outcome:
            continue
        outcome_id = _clean_text(outcome.get("outcome_id"), limit=80)
        if outcome_id in seen:
            continue
        seen.add(outcome_id)
        outcomes.append(outcome)
    return outcomes[:8]


def normalize_procedural_outcomes(value: Any, *, limit: int = 8) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in _list_or_empty(value):
        outcome = normalize_procedural_outcome(item)
        if not outcome:
            continue
        outcome_id = _clean_text(outcome.get("outcome_id"), limit=80)
        if outcome_id in seen:
            continue
        seen.add(outcome_id)
        out.append(outcome)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _outcomes_for_trace(trace: dict[str, Any], outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trace_id = _clean_text(trace.get("trace_id"), limit=80)
    proposal_id = _clean_text(trace.get("source_proposal_id"), limit=128)
    run_id = _clean_text(trace.get("source_run_id"), limit=128)
    matched = []
    for outcome in outcomes:
        if trace_id and _clean_text(outcome.get("source_trace_id"), limit=80) == trace_id:
            matched.append(outcome)
            continue
        if proposal_id and _clean_text(outcome.get("source_proposal_id"), limit=128) == proposal_id:
            matched.append(outcome)
            continue
        if run_id and _clean_text(outcome.get("source_run_id"), limit=128) == run_id:
            matched.append(outcome)
    return matched


def calibrate_procedural_traces_with_outcomes(traces: Any, outcomes: Any) -> list[dict[str, Any]]:
    normalized_outcomes = normalize_procedural_outcomes(outcomes)
    if not normalized_outcomes:
        return _normalize_procedural_traces(traces)
    calibrated: list[dict[str, Any]] = []
    for trace in _normalize_procedural_traces(traces):
        matched = _outcomes_for_trace(trace, normalized_outcomes)
        if not matched:
            calibrated.append(trace)
            continue
        delta = round(sum(float(item.get("confidence_delta") or 0.0) for item in matched), 3)
        latest = matched[-1]
        updated = dict(trace)
        updated["confidence"] = _clamp01(float(trace.get("confidence") or 0.0) + delta, 0.0)
        updated["last_outcome_kind"] = _clean_text(latest.get("outcome_kind"), limit=80, lower=True)
        updated["last_outcome_id"] = _clean_text(latest.get("outcome_id"), limit=80)
        updated["reuse_allowed"] = bool(latest.get("reuse_allowed", False))
        updated["boundary_reinforced"] = bool(any(item.get("boundary_reinforced", False) for item in matched))
        refs = [
            _clean_text(item.get("outcome_id"), limit=80)
            for item in matched
            if _clean_text(item.get("outcome_id"), limit=80)
        ]
        if refs:
            updated["outcome_refs"] = refs[:8]
        recovery_hints = [
            _clean_text(item.get("recovery_hint"), limit=220)
            for item in matched
            if _clean_text(item.get("recovery_hint"), limit=220)
        ]
        if recovery_hints:
            existing_notes = _clean_text_list(updated.get("boundary_notes"), limit=8)
            updated["boundary_notes"] = _clean_text_list([*existing_notes, *recovery_hints], limit=8)
        calibrated_trace = _normalize_procedural_trace(updated)
        if calibrated_trace:
            for key in ("last_outcome_kind", "last_outcome_id", "reuse_allowed", "boundary_reinforced", "outcome_refs"):
                if key in updated:
                    calibrated_trace[key] = updated[key]
            calibrated.append(calibrated_trace)
    return calibrated


def summarize_procedural_outcomes(outcomes: Any) -> dict[str, Any]:
    normalized = normalize_procedural_outcomes(outcomes)
    if not normalized:
        return {
            "procedural_outcome": False,
            "outcomes": [],
            "last_outcome_kind": "",
            "confidence_delta_total": 0.0,
            "boundary_reinforced": False,
            "reuse_allowed": False,
        }
    latest = normalized[-1]
    return {
        "procedural_outcome": True,
        "outcomes": normalized,
        "last_outcome_kind": _clean_text(latest.get("outcome_kind"), limit=80, lower=True),
        "source_trace_id": _clean_text(latest.get("source_trace_id"), limit=80),
        "source_run_id": _clean_text(latest.get("source_run_id"), limit=128),
        "confidence_delta_total": round(sum(float(item.get("confidence_delta") or 0.0) for item in normalized), 3),
        "boundary_reinforced": bool(any(item.get("boundary_reinforced", False) for item in normalized)),
        "reuse_allowed": bool(latest.get("reuse_allowed", False)),
        "recovery_hint": _clean_text(latest.get("recovery_hint"), limit=220),
    }


__all__ = [
    "ALLOWED_ATTEMPT_STATUSES",
    "ALLOWED_PROCEDURAL_OUTCOME_KINDS",
    "calibrate_procedural_traces_with_outcomes",
    "derive_procedural_outcomes_from_action_packets",
    "normalize_procedural_outcome",
    "normalize_procedural_outcomes",
    "summarize_procedural_outcomes",
]
