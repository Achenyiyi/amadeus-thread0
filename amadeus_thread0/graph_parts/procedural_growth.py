from __future__ import annotations

import hashlib
from typing import Any

from .action_packets import normalize_action_packet
from .procedural_outcome import (
    calibrate_procedural_traces_with_outcomes,
    derive_procedural_outcomes_from_action_packets,
    normalize_procedural_outcomes,
    summarize_procedural_outcomes,
)
from .procedural_recovery import (
    apply_recovery_markers_to_traces,
    derive_procedural_recoveries_from_outcomes,
    normalize_procedural_recoveries,
    summarize_procedural_recoveries,
)


ALLOWED_PROCEDURAL_TRACE_KINDS = {
    "workspace_procedure",
    "sandbox_execution_pattern",
    "browser_runtime_pattern",
    "skill_usage_pattern",
    "blocked_boundary_pattern",
    "recovery_pattern",
}

COMPLETED_PACKET_STATUSES = {"completed", "executed"}
BLOCKED_PACKET_STATUSES = {"blocked"}
NON_FACT_PACKET_STATUSES = {
    "pending",
    "rejected",
    "expired",
    "awaiting_approval",
    "approved",
    "proposed",
    "queued",
    "executing",
}

_SKILL_MUTATION_OPERATIONS = {
    "install",
    "update",
    "enable",
    "disable",
    "pin",
    "unpin",
    "install_skill",
    "update_skill",
    "enable_skill",
    "disable_skill",
    "pin_skill",
    "unpin_skill",
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


def _clean_text_list(value: Any, *, limit: int = 6, item_limit: int = 160) -> list[str]:
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


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        cast = float(value)
    except Exception:
        cast = float(default)
    return round(max(0.0, min(1.0, cast)), 3)


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _stable_trace_id(seed: dict[str, Any]) -> str:
    parts = [
        _clean_text(seed.get("trace_kind"), limit=80, lower=True),
        _clean_text(seed.get("source_proposal_id"), limit=128),
        _clean_text(seed.get("source_run_id"), limit=128),
        _clean_text(seed.get("source_tool_name"), limit=120, lower=True),
        _clean_text(seed.get("status"), limit=32, lower=True),
        _clean_text(seed.get("result_summary"), limit=120),
    ]
    digest = hashlib.sha1("|".join(parts).encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"proc_{digest}"


def normalize_procedural_trace(value: Any) -> dict[str, Any]:
    row = _dict_or_empty(value)
    if not row:
        return {}
    trace_kind = _clean_text(row.get("trace_kind"), limit=80, lower=True)
    if trace_kind not in ALLOWED_PROCEDURAL_TRACE_KINDS:
        return {}
    status = _clean_text(row.get("status"), limit=32, lower=True)
    if status not in COMPLETED_PACKET_STATUSES | BLOCKED_PACKET_STATUSES | {"recovered"}:
        return {}
    normalized = {
        "trace_id": _clean_text(row.get("trace_id"), limit=80)
        if _clean_text(row.get("trace_id"), limit=80).startswith("proc_")
        else "",
        "trace_kind": trace_kind,
        "source_proposal_id": _clean_text(row.get("source_proposal_id"), limit=128),
        "source_run_id": _clean_text(row.get("source_run_id"), limit=128),
        "source_tool_name": _clean_text(row.get("source_tool_name"), limit=120, lower=True),
        "status": "completed" if status == "executed" else status,
        "preconditions": _clean_text_list(row.get("preconditions"), limit=8),
        "procedure_steps": _clean_text_list(row.get("procedure_steps"), limit=8),
        "result_summary": _clean_text(row.get("result_summary"), limit=220),
        "reuse_conditions": _clean_text_list(row.get("reuse_conditions"), limit=8),
        "boundary_notes": _clean_text_list(row.get("boundary_notes"), limit=8),
        "confidence": _clamp01(row.get("confidence"), 0.0),
    }
    for key in ("last_outcome_kind", "last_outcome_id"):
        text = _clean_text(row.get(key), limit=80, lower=key == "last_outcome_kind")
        if text:
            normalized[key] = text
    for key in ("recovery_kind", "recovery_allowed_bias_kind"):
        text = _clean_text(row.get(key), limit=80, lower=True)
        if text:
            normalized[key] = text
    recovery_next_step = _clean_text(row.get("recovery_suggested_next_step"), limit=260)
    if recovery_next_step:
        normalized["recovery_suggested_next_step"] = recovery_next_step
    if "reuse_allowed" in row:
        normalized["reuse_allowed"] = bool(row.get("reuse_allowed", False))
    if "boundary_reinforced" in row:
        normalized["boundary_reinforced"] = bool(row.get("boundary_reinforced", False))
    if "recovery_required" in row:
        normalized["recovery_required"] = bool(row.get("recovery_required", False))
    outcome_refs = _clean_text_list(row.get("outcome_refs"), limit=8, item_limit=80)
    if outcome_refs:
        normalized["outcome_refs"] = outcome_refs
    recovery_refs = _clean_text_list(row.get("recovery_refs"), limit=8, item_limit=80)
    if recovery_refs:
        normalized["recovery_refs"] = recovery_refs
    if not normalized["trace_id"]:
        normalized["trace_id"] = _stable_trace_id(normalized)
    if not any(
        (
            normalized["source_proposal_id"],
            normalized["source_run_id"],
            normalized["source_tool_name"],
            normalized["procedure_steps"],
            normalized["result_summary"],
            normalized["boundary_notes"],
        )
    ):
        return {}
    return normalized


def normalize_procedural_traces(value: Any, *, limit: int = 8) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in _list_or_empty(value):
        trace = normalize_procedural_trace(item)
        if not trace:
            continue
        trace_id = str(trace.get("trace_id") or "").strip()
        if trace_id in seen:
            continue
        seen.add(trace_id)
        out.append(trace)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _packet_with_raw_extras(value: Any) -> dict[str, Any]:
    raw = _dict_or_empty(value)
    normalized = normalize_action_packet(raw)
    if not normalized:
        return {}
    merged = dict(normalized)
    for key in ("skill_effects",):
        if key in raw:
            merged[key] = raw.get(key)
    raw_status = _clean_text(raw.get("status"), limit=32, lower=True)
    if raw_status:
        merged["_raw_status"] = raw_status
    return merged


def _packet_status(packet: dict[str, Any]) -> str:
    return _clean_text(packet.get("_raw_status") or packet.get("status"), limit=32, lower=True)


def _execution_result(packet: dict[str, Any]) -> dict[str, Any]:
    return _dict_or_empty(packet.get("execution_result"))


def _browser_result(packet: dict[str, Any]) -> dict[str, Any]:
    return _dict_or_empty(packet.get("browser_execution_result"))


def _browser_preview(packet: dict[str, Any]) -> dict[str, Any]:
    return _dict_or_empty(packet.get("browser_execution_preview"))


def _is_sandbox_packet(packet: dict[str, Any]) -> bool:
    intent = _clean_text(packet.get("intent"), limit=120, lower=True)
    tool_name = _clean_text(packet.get("tool_name"), limit=120, lower=True)
    return bool(
        intent == "sandbox:execute_workspace_command"
        or tool_name == "execute_workspace_command"
        or packet.get("execution_spec")
        or packet.get("execution_preview")
        or packet.get("execution_result")
    )


def _is_browser_packet(packet: dict[str, Any]) -> bool:
    intent = _clean_text(packet.get("intent"), limit=120, lower=True)
    tool_name = _clean_text(packet.get("tool_name"), limit=120, lower=True)
    return bool(
        intent.startswith("browser:")
        or tool_name.startswith("browser_")
        or packet.get("browser_execution_spec")
        or packet.get("browser_execution_preview")
        or packet.get("browser_execution_result")
    )


def _is_completed_packet(packet: dict[str, Any]) -> bool:
    status = _packet_status(packet)
    if status not in COMPLETED_PACKET_STATUSES:
        return False
    execution = _execution_result(packet)
    if execution:
        result_status = _clean_text(execution.get("status"), limit=32, lower=True)
        if result_status in BLOCKED_PACKET_STATUSES:
            return False
        if _coerce_int(execution.get("exit_code"), 0) != 0:
            return False
    browser = _browser_result(packet)
    if browser:
        result_status = _clean_text(browser.get("status"), limit=32, lower=True)
        if result_status in BLOCKED_PACKET_STATUSES:
            return False
        if bool(browser.get("manual_takeover_required", False)):
            return False
    return True


def _is_blocked_packet(packet: dict[str, Any]) -> bool:
    status = _packet_status(packet)
    if status in BLOCKED_PACKET_STATUSES:
        return True
    execution = _execution_result(packet)
    if execution:
        result_status = _clean_text(execution.get("status"), limit=32, lower=True)
        if result_status in BLOCKED_PACKET_STATUSES:
            return True
        if _coerce_int(execution.get("exit_code"), 0) != 0:
            return True
    browser = _browser_result(packet)
    if browser:
        result_status = _clean_text(browser.get("status"), limit=32, lower=True)
        last_status = _clean_text(browser.get("last_action_status"), limit=64, lower=True)
        if result_status in BLOCKED_PACKET_STATUSES or last_status == "manual_takeover_required":
            return True
        if bool(browser.get("manual_takeover_required", False)):
            return True
    if bool(_browser_preview(packet).get("requires_manual_takeover", False)):
        return True
    return False


def _common_preconditions(packet: dict[str, Any]) -> list[str]:
    out = []
    if packet.get("execution_spec") or packet.get("execution_preview"):
        out.append("workspace_root available")
    if packet.get("browser_execution_preview") or packet.get("browser_execution_result"):
        out.append("browser profile available")
    if bool(packet.get("requires_approval", False)):
        out.append("approval granted")
    return out


def _common_boundary_notes(packet: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if bool(packet.get("requires_approval", False)):
        notes.append("requires approval before execution")
    block_reason = _clean_text(packet.get("block_reason"), limit=220)
    if block_reason:
        notes.append(block_reason)
    execution_error = _clean_text(_execution_result(packet).get("error_summary"), limit=220)
    if execution_error:
        notes.append(execution_error)
    browser = _browser_result(packet)
    if bool(browser.get("manual_takeover_required", False)) or _clean_text(
        browser.get("last_action_status"),
        limit=64,
        lower=True,
    ) == "manual_takeover_required":
        notes.append("manual browser takeover required")
    browser_error = _clean_text(browser.get("error_summary"), limit=220)
    if browser_error:
        notes.append(browser_error)
    return _clean_text_list(notes, limit=8)


def _sandbox_trace(packet: dict[str, Any]) -> dict[str, Any]:
    execution = _execution_result(packet)
    spec = _dict_or_empty(packet.get("execution_spec"))
    blocked = _is_blocked_packet(packet)
    trace_kind = "blocked_boundary_pattern" if blocked else "sandbox_execution_pattern"
    profile = _clean_text(spec.get("profile"), limit=64, lower=True)
    steps = (
        ["inspect cwd", "run bounded command", "read stdout/artifact"]
        if not blocked
        else ["preserve command preview", "read failure trace", "adjust bounded next step"]
    )
    reuse = ["similar workspace command"]
    if profile:
        reuse.append(f"{profile} command profile")
    tool_args = _dict_or_empty(packet.get("tool_args"))
    planning = _dict_or_empty(tool_args.get("procedural_planning"))
    return normalize_procedural_trace(
        {
            "trace_id": planning.get("trace_id"),
            "trace_kind": trace_kind,
            "source_proposal_id": packet.get("proposal_id"),
            "source_run_id": execution.get("run_id") or packet.get("proposal_id"),
            "source_tool_name": packet.get("tool_name") or "execute_workspace_command",
            "status": "blocked" if blocked else "completed",
            "preconditions": _common_preconditions(packet),
            "procedure_steps": steps,
            "result_summary": packet.get("result_summary") or execution.get("error_summary"),
            "reuse_conditions": reuse,
            "boundary_notes": _common_boundary_notes(packet),
            "confidence": 0.62 if blocked else 0.74,
        }
    )


def _browser_trace(packet: dict[str, Any]) -> dict[str, Any]:
    browser = _browser_result(packet)
    preview = _browser_preview(packet)
    blocked = _is_blocked_packet(packet)
    manual = bool(browser.get("manual_takeover_required", False) or preview.get("requires_manual_takeover", False))
    trace_kind = "blocked_boundary_pattern" if blocked else "browser_runtime_pattern"
    steps = (
        ["preserve current page/profile", "hand off sensitive step", "resume after manual takeover"]
        if manual
        else ["open/select live page", "perform browser action", "preserve page/tab continuity"]
    )
    notes = _common_boundary_notes(packet)
    if manual and "manual browser takeover required" not in notes:
        notes.append("manual browser takeover required")
    tool_args = _dict_or_empty(packet.get("tool_args"))
    planning = _dict_or_empty(tool_args.get("procedural_planning"))
    return normalize_procedural_trace(
        {
            "trace_id": planning.get("trace_id"),
            "trace_kind": trace_kind,
            "source_proposal_id": packet.get("proposal_id"),
            "source_run_id": browser.get("run_id") or packet.get("proposal_id"),
            "source_tool_name": packet.get("tool_name"),
            "status": "blocked" if blocked else "completed",
            "preconditions": _common_preconditions(packet),
            "procedure_steps": steps,
            "result_summary": packet.get("result_summary") or browser.get("error_summary"),
            "reuse_conditions": ["same browser profile/page family"],
            "boundary_notes": notes,
            "confidence": 0.6 if blocked else 0.72,
        }
    )


def _skill_effects(packet: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for item in _list_or_empty(packet.get("skill_effects")):
        if isinstance(item, dict):
            out.append(dict(item))
    return out[:8]


def _is_skill_usage_packet(packet: dict[str, Any]) -> bool:
    effects = _skill_effects(packet)
    if not effects:
        return False
    for effect in effects:
        operation = _clean_text(effect.get("operation"), limit=80, lower=True)
        status = _clean_text(effect.get("status"), limit=80, lower=True)
        if operation in _SKILL_MUTATION_OPERATIONS:
            continue
        if operation == "use" or _clean_text(effect.get("use_kind"), limit=120, lower=True):
            return status in {"", "completed"}
    return False


def _skill_trace(packet: dict[str, Any]) -> dict[str, Any]:
    effects = _skill_effects(packet)
    first = effects[0] if effects else {}
    skill_label = _clean_text(first.get("skill_id") or first.get("name"), limit=120)
    return normalize_procedural_trace(
        {
            "trace_kind": "skill_usage_pattern",
            "source_proposal_id": packet.get("proposal_id"),
            "source_run_id": packet.get("proposal_id"),
            "source_tool_name": packet.get("tool_name") or first.get("tool_name"),
            "status": "completed",
            "preconditions": ["active skill matched"] if skill_label else [],
            "procedure_steps": ["match active skill", "apply skill guidance", "preserve artifact continuity"],
            "result_summary": packet.get("result_summary") or f"used skill {skill_label}",
            "reuse_conditions": ["similar skill-supported task"],
            "boundary_notes": ["skill registry truth stays outside autobiographical memory"],
            "confidence": 0.7,
        }
    )


def _workspace_trace(packet: dict[str, Any]) -> dict[str, Any]:
    tool_name = _clean_text(packet.get("tool_name"), limit=120, lower=True)
    mutation = {
        "write_workspace_file": "write file",
        "append_workspace_file": "append file",
        "replace_workspace_text": "replace text",
        "replace_workspace_lines": "replace lines",
    }.get(tool_name, "workspace procedure")
    return normalize_procedural_trace(
        {
            "trace_kind": "workspace_procedure",
            "source_proposal_id": packet.get("proposal_id"),
            "source_run_id": packet.get("proposal_id"),
            "source_tool_name": tool_name,
            "status": "completed",
            "preconditions": _common_preconditions(packet),
            "procedure_steps": ["inspect artifact context", mutation, "preserve workspace artifact continuity"],
            "result_summary": packet.get("result_summary"),
            "reuse_conditions": ["same workspace artifact family"],
            "boundary_notes": _common_boundary_notes(packet),
            "confidence": 0.68,
        }
    )


def extract_procedural_traces_from_action_packets(action_packets: Any) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    workspace_tools = {
        "write_workspace_file",
        "append_workspace_file",
        "replace_workspace_text",
        "replace_workspace_lines",
    }
    for item in _list_or_empty(action_packets):
        packet = _packet_with_raw_extras(item)
        if not packet:
            continue
        status = _packet_status(packet)
        if status in NON_FACT_PACKET_STATUSES:
            continue
        trace: dict[str, Any] = {}
        if _is_sandbox_packet(packet) and (_is_completed_packet(packet) or _is_blocked_packet(packet)):
            trace = _sandbox_trace(packet)
        elif _is_browser_packet(packet) and (_is_completed_packet(packet) or _is_blocked_packet(packet)):
            trace = _browser_trace(packet)
        elif _is_completed_packet(packet) and _is_skill_usage_packet(packet):
            trace = _skill_trace(packet)
        elif _is_completed_packet(packet) and _clean_text(packet.get("tool_name"), limit=120, lower=True) in workspace_tools:
            trace = _workspace_trace(packet)
        if trace:
            traces.append(trace)
    return normalize_procedural_traces(traces)


def _outcomes_from_context_or_packets(
    context: dict[str, Any],
    *,
    action_packets: Any = None,
    traces: Any = None,
    procedural_planning: Any = None,
) -> list[dict[str, Any]]:
    existing = normalize_procedural_outcomes(context.get("procedural_outcomes"))
    if existing:
        return existing
    return derive_procedural_outcomes_from_action_packets(
        action_packets,
        planning_bias=procedural_planning or context.get("procedural_planning"),
        traces=traces,
    )


def build_procedural_hint(traces: Any) -> dict[str, Any]:
    candidates = [
        trace
        for trace in normalize_procedural_traces(traces)
        if float(trace.get("confidence") or 0.0) >= 0.35
    ]
    if not candidates:
        return {}
    candidates.sort(key=lambda item: (float(item.get("confidence") or 0.0), str(item.get("trace_id") or "")), reverse=True)
    trace = candidates[0]
    steps = trace.get("procedure_steps") if isinstance(trace.get("procedure_steps"), list) else []
    boundary_notes = trace.get("boundary_notes") if isinstance(trace.get("boundary_notes"), list) else []
    trace_kind = str(trace.get("trace_kind") or "")
    first_note = ""
    if boundary_notes:
        preferred_note = next(
            (
                str(note)
                for note in boundary_notes
                if "takeover" in str(note).lower() or "manual" in str(note).lower()
            ),
            "",
        )
        if not preferred_note and trace_kind == "blocked_boundary_pattern":
            preferred_note = next(
                (
                    str(note)
                    for note in boundary_notes
                    if "approval" not in str(note).lower()
                ),
                "",
            )
        first_note = preferred_note or str(boundary_notes[0])
    source_status = _clean_text(trace.get("status"), limit=32, lower=True)
    must_request_approval = any(
        "approval" in str(note).lower()
        or "manual" in str(note).lower()
        or "takeover" in str(note).lower()
        for note in boundary_notes
    ) or trace_kind in {
        "sandbox_execution_pattern",
        "browser_runtime_pattern",
    }
    capability_claim = bool(source_status == "completed" and trace_kind != "blocked_boundary_pattern")
    if trace_kind == "blocked_boundary_pattern":
        suggested = first_note or "respect the previous boundary before continuing"
    else:
        suggested = str(steps[0]) if steps else "reuse prior procedural trace as a planning hint"
    return {
        "trace_id": str(trace.get("trace_id") or ""),
        "trace_kind": trace_kind,
        "suggested_first_step": suggested,
        "source_run_id": str(trace.get("source_run_id") or ""),
        "confidence": float(trace.get("confidence") or 0.0),
        "must_request_approval": bool(must_request_approval),
        "boundary_note": first_note,
        "capability_claim": capability_claim,
        "source_status": source_status,
    }


def summarize_procedural_growth(traces: Any) -> dict[str, Any]:
    normalized = normalize_procedural_traces(traces)
    if not normalized:
        return {"procedural_growth": False, "traces": [], "procedural_hint": {}}
    return {
        "procedural_growth": True,
        "traces": normalized,
        "procedural_hint": build_procedural_hint(normalized),
    }


def _existing_traces_from_context(value: Any) -> list[dict[str, Any]]:
    row = _dict_or_empty(value)
    continuity = _dict_or_empty(row.get("procedural_continuity"))
    return normalize_procedural_traces(
        [
            *(
                row.get("procedural_traces")
                if isinstance(row.get("procedural_traces"), list)
                else []
            ),
            *(
                continuity.get("traces")
                if isinstance(continuity.get("traces"), list)
                else []
            ),
        ]
    )


def _procedure_family_from_trace(trace: dict[str, Any]) -> str:
    kind = _clean_text(trace.get("trace_kind"), limit=80, lower=True)
    tool_name = _clean_text(trace.get("source_tool_name"), limit=120, lower=True)
    if kind == "skill_usage_pattern":
        return "skill"
    if kind == "sandbox_execution_pattern" or tool_name == "execute_workspace_command":
        return "sandbox"
    if kind == "browser_runtime_pattern" or tool_name.startswith("browser_"):
        return "browser"
    if kind == "workspace_procedure":
        return "workspace"
    return ""


def _procedure_pattern_from_trace(trace: dict[str, Any]) -> str:
    tool_name = _clean_text(trace.get("source_tool_name"), limit=120, lower=True)
    if tool_name == "execute_workspace_command":
        for condition in _list_or_empty(trace.get("reuse_conditions")):
            text = _clean_text(condition, limit=120, lower=True)
            if text.endswith(" command profile"):
                return text.removesuffix(" command profile").strip()
        return "workspace_command"
    if tool_name.startswith("browser_"):
        return tool_name.removeprefix("browser_") or "browser_action"
    if tool_name in {"write_workspace_file", "append_workspace_file", "replace_workspace_text", "replace_workspace_lines"}:
        return {
            "write_workspace_file": "write",
            "append_workspace_file": "append",
            "replace_workspace_text": "replace",
            "replace_workspace_lines": "replace",
        }.get(tool_name, "workspace")
    if tool_name:
        return tool_name
    return _clean_text(trace.get("trace_kind"), limit=120, lower=True)


def _continuity_with_traces(context: dict[str, Any], traces: list[dict[str, Any]]) -> dict[str, Any]:
    continuity = _dict_or_empty(context.get("procedural_continuity"))
    out: dict[str, Any] = {}
    family = _clean_text(continuity.get("capability_family"), limit=80, lower=True)
    pattern = _clean_text(continuity.get("pattern"), limit=160, lower=True)
    identity_safe = bool(continuity.get("identity_safe", False))
    completed_trace = next(
        (
            trace
            for trace in traces
            if _clean_text(trace.get("status"), limit=32, lower=True) == "completed"
            and _clean_text(trace.get("trace_kind"), limit=80, lower=True) != "blocked_boundary_pattern"
        ),
        {},
    )
    if not family and completed_trace:
        family = _procedure_family_from_trace(completed_trace)
    if not pattern and completed_trace:
        pattern = _procedure_pattern_from_trace(completed_trace)
    if family in {"skill", "sandbox", "browser", "workspace"} and pattern and (identity_safe or completed_trace):
        out.update(
            {
                "capability_family": family,
                "pattern": pattern,
                "confidence": _clamp01(
                    continuity.get("confidence")
                    if "confidence" in continuity
                    else completed_trace.get("confidence"),
                    0.1,
                )
                or 0.1,
                "evidence_count": max(1, min(999, _coerce_int(continuity.get("evidence_count"), 1))),
                "last_success_ref": _clean_text(
                    continuity.get("last_success_ref")
                    or completed_trace.get("source_run_id")
                    or completed_trace.get("source_proposal_id"),
                    limit=180,
                ),
                "identity_safe": True,
            }
        )
    if traces:
        out["traces"] = traces
    return out


def enrich_digital_body_consequence_with_procedural_growth(
    consequence: Any,
    *,
    action_packets: Any = None,
    procedural_planning: Any = None,
) -> dict[str, Any]:
    row = _dict_or_empty(consequence)
    existing_traces = _existing_traces_from_context(row)
    traces = existing_traces or extract_procedural_traces_from_action_packets(action_packets)
    outcomes = _outcomes_from_context_or_packets(
        row,
        action_packets=action_packets,
        traces=traces,
        procedural_planning=procedural_planning,
    )
    if traces and outcomes:
        traces = calibrate_procedural_traces_with_outcomes(traces, outcomes)
    recoveries = normalize_procedural_recoveries(row.get("procedural_recoveries"))
    if not recoveries and outcomes:
        recoveries = derive_procedural_recoveries_from_outcomes(outcomes)
    if traces and recoveries:
        traces = apply_recovery_markers_to_traces(traces, recoveries)
    if not traces:
        return row
    completed_trace_present = any(
        _clean_text(trace.get("status"), limit=32, lower=True) == "completed"
        and _clean_text(trace.get("trace_kind"), limit=80, lower=True) != "blocked_boundary_pattern"
        for trace in traces
    )
    enriched = dict(row)
    if not enriched:
        first_trace = traces[0]
        enriched["kind"] = "embodied_growth" if completed_trace_present else "environmental_friction"
        enriched["summary"] = _clean_text(first_trace.get("result_summary"), limit=220)
        if not completed_trace_present:
            enriched["environmental_friction"] = True
    enriched["procedural_growth"] = bool(completed_trace_present)
    enriched["procedural_traces"] = traces
    if outcomes:
        enriched["procedural_outcomes"] = outcomes
        enriched["procedural_outcome_summary"] = summarize_procedural_outcomes(outcomes)
    if recoveries:
        enriched["procedural_recoveries"] = recoveries
        enriched["procedural_recovery_summary"] = summarize_procedural_recoveries(recoveries)
    continuity = _continuity_with_traces(enriched, traces)
    if continuity:
        enriched["procedural_continuity"] = continuity
    hint = build_procedural_hint(traces)
    if hint:
        enriched["procedural_hint"] = hint
    return enriched


def enrich_interaction_carryover_with_procedural_traces(
    carryover: Any,
    *,
    traces: Any = None,
) -> dict[str, Any]:
    row = _dict_or_empty(carryover)
    if not row:
        return {}
    embodied = _dict_or_empty(row.get("embodied_context"))
    normalized_traces = normalize_procedural_traces(traces) or _existing_traces_from_context(embodied)
    if not normalized_traces:
        return row
    enriched = dict(row)
    enriched["embodied_context"] = enrich_digital_body_consequence_with_procedural_growth(
        embodied,
        action_packets=None,
        procedural_planning=None,
    )
    if not enriched["embodied_context"].get("procedural_traces"):
        enriched["embodied_context"]["procedural_traces"] = normalized_traces
        enriched["embodied_context"]["procedural_continuity"] = _continuity_with_traces(
            enriched["embodied_context"],
            normalized_traces,
        )
        hint = build_procedural_hint(normalized_traces)
        if hint:
            enriched["embodied_context"]["procedural_hint"] = hint
    return enriched


__all__ = [
    "ALLOWED_PROCEDURAL_TRACE_KINDS",
    "BLOCKED_PACKET_STATUSES",
    "COMPLETED_PACKET_STATUSES",
    "NON_FACT_PACKET_STATUSES",
    "build_procedural_hint",
    "enrich_digital_body_consequence_with_procedural_growth",
    "enrich_interaction_carryover_with_procedural_traces",
    "extract_procedural_traces_from_action_packets",
    "normalize_procedural_trace",
    "normalize_procedural_traces",
    "summarize_procedural_growth",
]
