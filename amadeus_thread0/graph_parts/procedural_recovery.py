from __future__ import annotations

import hashlib
from typing import Any

from .procedural_outcome import normalize_procedural_outcomes


ALLOWED_PROCEDURAL_RECOVERY_KINDS = {
    "inspect_failure_artifact",
    "adjust_bounded_command",
    "preserve_manual_takeover",
    "avoid_blocked_boundary",
    "refresh_workspace_context",
    "hold_for_approval",
    "no_recovery_needed",
}

ALLOWED_PROCEDURAL_RECOVERY_STATUSES = {
    "suggested",
    "pending",
    "resolved",
    "blocked",
    "expired",
}

ALLOWED_RECOVERY_BIAS_KINDS = {
    "workspace_guidance",
    "boundary_only",
    "browser_manual_takeover",
    "hold",
}

_BASE_MUST_NOT_REPEAT = {
    "package install",
    "shell wrapper",
    "git mutation",
    "network enablement",
    "privileged container",
    "docker socket",
    "host secret passthrough",
    "external executor harness",
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


def _clean_text_list(value: Any, *, limit: int = 8, item_limit: int = 220, lower: bool = False) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in _list_or_empty(value):
        text = _clean_text(item, limit=item_limit, lower=lower)
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


def _stable_recovery_id(seed: dict[str, Any]) -> str:
    parts = [
        _clean_text(seed.get("source_outcome_id"), limit=80),
        _clean_text(seed.get("source_trace_id"), limit=80),
        _clean_text(seed.get("source_proposal_id"), limit=128),
        _clean_text(seed.get("source_run_id"), limit=128),
        _clean_text(seed.get("recovery_kind"), limit=80, lower=True),
        _clean_text(seed.get("allowed_bias_kind"), limit=80, lower=True),
    ]
    digest = hashlib.sha1("|".join(parts).encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"proc_rec_{digest}"


def normalize_procedural_recovery(value: Any) -> dict[str, Any]:
    row = _dict_or_empty(value)
    if not row:
        return {}
    recovery_kind = _clean_text(row.get("recovery_kind"), limit=80, lower=True)
    if recovery_kind not in ALLOWED_PROCEDURAL_RECOVERY_KINDS:
        return {}
    status = _clean_text(row.get("status"), limit=32, lower=True) or "suggested"
    if status not in ALLOWED_PROCEDURAL_RECOVERY_STATUSES:
        return {}
    allowed_bias_kind = _clean_text(row.get("allowed_bias_kind"), limit=80, lower=True)
    if allowed_bias_kind not in ALLOWED_RECOVERY_BIAS_KINDS:
        return {}
    normalized: dict[str, Any] = {
        "recovery_id": _clean_text(row.get("recovery_id"), limit=80)
        if _clean_text(row.get("recovery_id"), limit=80).startswith("proc_rec_")
        else "",
        "source_outcome_id": _clean_text(row.get("source_outcome_id"), limit=80),
        "source_trace_id": _clean_text(row.get("source_trace_id"), limit=80),
        "source_proposal_id": _clean_text(row.get("source_proposal_id"), limit=128),
        "source_run_id": _clean_text(row.get("source_run_id"), limit=128),
        "recovery_kind": recovery_kind,
        "status": status,
        "safe_to_reuse": bool(row.get("safe_to_reuse", False)),
        "requires_approval": bool(row.get("requires_approval", False)),
        "allowed_bias_kind": allowed_bias_kind,
        "suggested_next_step": _clean_text(row.get("suggested_next_step"), limit=260),
        "must_not_repeat": _clean_text_list(row.get("must_not_repeat"), limit=10, item_limit=180, lower=True),
        "evidence_refs": _clean_text_list(row.get("evidence_refs"), limit=8, item_limit=320),
    }
    if not normalized["recovery_id"]:
        normalized["recovery_id"] = _stable_recovery_id(normalized)
    if not any(
        (
            normalized["source_outcome_id"],
            normalized["source_trace_id"],
            normalized["source_proposal_id"],
            normalized["source_run_id"],
            normalized["evidence_refs"],
        )
    ):
        return {}
    return normalized


def normalize_procedural_recoveries(value: Any, *, limit: int = 8) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in _list_or_empty(value):
        recovery = normalize_procedural_recovery(item)
        if not recovery:
            continue
        recovery_id = _clean_text(recovery.get("recovery_id"), limit=80)
        if recovery_id in seen:
            continue
        seen.add(recovery_id)
        out.append(recovery)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _failure_step(outcome: dict[str, Any]) -> str:
    refs = _clean_text_list(outcome.get("evidence_refs"), limit=8, item_limit=320)
    has_stderr = any("stderr" in ref.lower() for ref in refs)
    has_stdout = any("stdout" in ref.lower() for ref in refs)
    if has_stderr and has_stdout:
        return "inspect stderr/stdout artifacts before rerunning a bounded command"
    if has_stderr:
        return "inspect stderr artifact before rerunning a bounded command"
    return "inspect failure artifacts before rerunning a bounded command"


def _safe_must_not_repeat(outcome: dict[str, Any], *extra: str) -> list[str]:
    hint = _clean_text(outcome.get("recovery_hint"), limit=220, lower=True)
    items = set(_BASE_MUST_NOT_REPEAT)
    for item in extra:
        if item:
            items.add(_clean_text(item, limit=180, lower=True))
    if "package install" in hint or "pip install" in hint:
        items.add("package install is blocked")
        items.add(hint)
    if "browser" in hint and ("mutation" in hint or "fill" in hint or "click" in hint):
        items.add(hint)
    return _clean_text_list(sorted(items), limit=10, item_limit=180, lower=True)


def _recovery_from_outcome(outcome: dict[str, Any], *, include_noop: bool) -> dict[str, Any]:
    kind = _clean_text(outcome.get("outcome_kind"), limit=80, lower=True)
    hint = _clean_text(outcome.get("recovery_hint"), limit=220)
    common = {
        "source_outcome_id": outcome.get("outcome_id"),
        "source_trace_id": outcome.get("source_trace_id"),
        "source_proposal_id": outcome.get("source_proposal_id"),
        "source_run_id": outcome.get("source_run_id"),
        "status": "suggested",
        "evidence_refs": outcome.get("evidence_refs"),
    }
    if kind == "failed_execution":
        return normalize_procedural_recovery(
            {
                **common,
                "recovery_kind": "inspect_failure_artifact",
                "safe_to_reuse": False,
                "requires_approval": False,
                "allowed_bias_kind": "workspace_guidance",
                "suggested_next_step": _failure_step(outcome),
                "must_not_repeat": _safe_must_not_repeat(outcome),
            }
        )
    if kind == "blocked_boundary_reinforced":
        blocked = hint or "blocked action"
        return normalize_procedural_recovery(
            {
                **common,
                "recovery_kind": "avoid_blocked_boundary",
                "safe_to_reuse": False,
                "requires_approval": True,
                "allowed_bias_kind": "boundary_only",
                "suggested_next_step": "avoid repeating the blocked action; choose a bounded approved path instead",
                "must_not_repeat": _safe_must_not_repeat(outcome, blocked),
            }
        )
    if kind == "manual_takeover_required":
        return normalize_procedural_recovery(
            {
                **common,
                "recovery_kind": "preserve_manual_takeover",
                "safe_to_reuse": False,
                "requires_approval": True,
                "allowed_bias_kind": "browser_manual_takeover",
                "suggested_next_step": hint or "manual browser takeover is still required before continuing",
                "must_not_repeat": _safe_must_not_repeat(outcome, "browser mutation"),
            }
        )
    if kind == "stale_or_mismatched_context":
        return normalize_procedural_recovery(
            {
                **common,
                "recovery_kind": "refresh_workspace_context",
                "safe_to_reuse": False,
                "requires_approval": False,
                "allowed_bias_kind": "workspace_guidance",
                "suggested_next_step": "refresh workspace/artifact context before reusing this procedure",
                "must_not_repeat": _safe_must_not_repeat(outcome),
            }
        )
    if kind == "no_executed_attempt":
        return normalize_procedural_recovery(
            {
                **common,
                "recovery_kind": "hold_for_approval",
                "safe_to_reuse": False,
                "requires_approval": True,
                "allowed_bias_kind": "hold",
                "suggested_next_step": hint or "attempt did not execute; keep it as an unfulfilled intention",
                "must_not_repeat": _safe_must_not_repeat(outcome),
            }
        )
    if include_noop and kind in {"confirmed_success", "partial_success"}:
        return normalize_procedural_recovery(
            {
                **common,
                "recovery_kind": "no_recovery_needed",
                "safe_to_reuse": bool(outcome.get("reuse_allowed", False)),
                "requires_approval": False,
                "allowed_bias_kind": "workspace_guidance",
                "suggested_next_step": "no recovery needed; keep normal approval semantics for any future execution",
                "must_not_repeat": _safe_must_not_repeat(outcome),
            }
        )
    return {}


def derive_procedural_recoveries_from_outcomes(
    outcomes: Any,
    *,
    include_noop: bool = False,
) -> list[dict[str, Any]]:
    recoveries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for outcome in normalize_procedural_outcomes(outcomes):
        recovery = _recovery_from_outcome(outcome, include_noop=include_noop)
        if not recovery:
            continue
        recovery_id = _clean_text(recovery.get("recovery_id"), limit=80)
        if recovery_id in seen:
            continue
        seen.add(recovery_id)
        recoveries.append(recovery)
    return recoveries[:8]


def _recoveries_for_trace(trace: dict[str, Any], recoveries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trace_id = _clean_text(trace.get("trace_id"), limit=80)
    proposal_id = _clean_text(trace.get("source_proposal_id"), limit=128)
    run_id = _clean_text(trace.get("source_run_id"), limit=128)
    matched = []
    for recovery in recoveries:
        if trace_id and _clean_text(recovery.get("source_trace_id"), limit=80) == trace_id:
            matched.append(recovery)
            continue
        if proposal_id and _clean_text(recovery.get("source_proposal_id"), limit=128) == proposal_id:
            matched.append(recovery)
            continue
        if run_id and _clean_text(recovery.get("source_run_id"), limit=128) == run_id:
            matched.append(recovery)
    return matched


def apply_recovery_markers_to_traces(traces: Any, recoveries: Any) -> list[dict[str, Any]]:
    from .procedural_growth import normalize_procedural_trace, normalize_procedural_traces

    normalized_recoveries = normalize_procedural_recoveries(recoveries)
    if not normalized_recoveries:
        return normalize_procedural_traces(traces)
    marked: list[dict[str, Any]] = []
    for trace in normalize_procedural_traces(traces):
        matched = _recoveries_for_trace(trace, normalized_recoveries)
        if not matched:
            marked.append(trace)
            continue
        latest = matched[-1]
        updated = dict(trace)
        updated["recovery_required"] = _clean_text(latest.get("recovery_kind"), lower=True) != "no_recovery_needed"
        updated["recovery_kind"] = _clean_text(latest.get("recovery_kind"), limit=80, lower=True)
        updated["recovery_allowed_bias_kind"] = _clean_text(latest.get("allowed_bias_kind"), limit=80, lower=True)
        updated["recovery_suggested_next_step"] = _clean_text(latest.get("suggested_next_step"), limit=260)
        updated["recovery_refs"] = [
            _clean_text(item.get("recovery_id"), limit=80)
            for item in matched
            if _clean_text(item.get("recovery_id"), limit=80)
        ][:8]
        if bool(updated["recovery_required"]):
            updated["reuse_allowed"] = False
            if updated["recovery_allowed_bias_kind"] in {"boundary_only", "browser_manual_takeover", "hold"}:
                updated["boundary_reinforced"] = True
        normalized = normalize_procedural_trace(updated)
        if normalized:
            for key in (
                "recovery_required",
                "recovery_kind",
                "recovery_allowed_bias_kind",
                "recovery_suggested_next_step",
                "recovery_refs",
            ):
                if key in updated:
                    normalized[key] = updated[key]
            if "reuse_allowed" in updated:
                normalized["reuse_allowed"] = updated["reuse_allowed"]
            if "boundary_reinforced" in updated:
                normalized["boundary_reinforced"] = updated["boundary_reinforced"]
            marked.append(normalized)
    return marked


def summarize_procedural_recoveries(recoveries: Any) -> dict[str, Any]:
    normalized = normalize_procedural_recoveries(recoveries)
    if not normalized:
        return {
            "procedural_recovery": False,
            "recoveries": [],
            "last_recovery_kind": "",
            "source_trace_id": "",
            "source_run_id": "",
            "safe_to_reuse": False,
            "requires_approval": False,
            "allowed_bias_kind": "",
        }
    latest = normalized[-1]
    return {
        "procedural_recovery": True,
        "recoveries": normalized,
        "last_recovery_kind": _clean_text(latest.get("recovery_kind"), limit=80, lower=True),
        "source_trace_id": _clean_text(latest.get("source_trace_id"), limit=80),
        "source_run_id": _clean_text(latest.get("source_run_id"), limit=128),
        "safe_to_reuse": bool(latest.get("safe_to_reuse", False)),
        "requires_approval": bool(latest.get("requires_approval", False)),
        "allowed_bias_kind": _clean_text(latest.get("allowed_bias_kind"), limit=80, lower=True),
        "suggested_next_step": _clean_text(latest.get("suggested_next_step"), limit=260),
    }


__all__ = [
    "ALLOWED_PROCEDURAL_RECOVERY_KINDS",
    "ALLOWED_PROCEDURAL_RECOVERY_STATUSES",
    "ALLOWED_RECOVERY_BIAS_KINDS",
    "apply_recovery_markers_to_traces",
    "derive_procedural_recoveries_from_outcomes",
    "normalize_procedural_recoveries",
    "normalize_procedural_recovery",
    "summarize_procedural_recoveries",
]
