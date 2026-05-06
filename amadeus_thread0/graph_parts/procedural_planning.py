from __future__ import annotations

from typing import Any

from .procedural_outcome import calibrate_procedural_traces_with_outcomes, normalize_procedural_outcomes
from .procedural_growth import build_procedural_hint, normalize_procedural_trace, normalize_procedural_traces


ALLOWED_PROCEDURAL_PLANNING_BIAS_KINDS = {
    "sandbox_execute",
    "browser_manual_takeover",
    "skill_guidance",
    "workspace_guidance",
    "boundary_only",
}

_SANDBOX_PATTERN_ALIASES = {
    "pytest": ("pytest", "test", "tests", "测试", "检查"),
    "rg_search": ("rg", "search", "grep", "检索", "搜索", "查找"),
    "git_status": ("git status", "状态"),
    "git_diff": ("git diff", "diff", "差异"),
}

_SANDBOX_PATTERN_COMMANDS = {
    "pytest": ("pytest", ["pytest"]),
    "rg_search": ("rg", ["rg", "."]),
    "git_status": ("git", ["git", "status", "--short"]),
    "git_diff": ("git", ["git", "diff", "--stat"]),
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


def _clean_text_list(value: Any, *, limit: int = 8, item_limit: int = 160) -> list[str]:
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


def _path_key(value: Any) -> str:
    return _clean_text(value, limit=320).replace("\\", "/").rstrip("/").lower()


def _event_text(current_event: Any) -> str:
    event = _dict_or_empty(current_event)
    return " ".join(
        _clean_text(event.get(key), limit=320, lower=True)
        for key in ("text", "effective_text", "semantic_goal", "event_frame")
        if _clean_text(event.get(key), limit=320)
    )


def _first_boundary_note(trace: dict[str, Any]) -> str:
    notes = _clean_text_list(trace.get("boundary_notes"), limit=8)
    if not notes:
        return ""
    preferred = next(
        (
            note
            for note in notes
            if "takeover" in note.lower()
            or "manual" in note.lower()
            or "blocked" in note.lower()
            or "拦" in note
        ),
        "",
    )
    return preferred or notes[0]


def _trace_is_manual_browser_takeover(trace: dict[str, Any]) -> bool:
    tool = _clean_text(trace.get("source_tool_name"), limit=120, lower=True)
    text = " ".join(
        [
            tool,
            _clean_text(trace.get("result_summary"), limit=260, lower=True),
            " ".join(note.lower() for note in _clean_text_list(trace.get("boundary_notes"), limit=8)),
            " ".join(step.lower() for step in _clean_text_list(trace.get("procedure_steps"), limit=8)),
        ]
    )
    return bool(tool.startswith("browser_") and ("manual" in text or "takeover" in text or "登录" in text))


def _pattern_from_trace(trace: dict[str, Any]) -> str:
    tool = _clean_text(trace.get("source_tool_name"), limit=120, lower=True)
    if tool == "execute_workspace_command":
        for condition in _clean_text_list(trace.get("reuse_conditions"), limit=8):
            text = condition.lower().strip()
            if text.endswith(" command profile"):
                pattern = text.removesuffix(" command profile").strip()
                if pattern:
                    return pattern
        for pattern, aliases in _SANDBOX_PATTERN_ALIASES.items():
            haystack = " ".join(
                [
                    " ".join(_clean_text_list(trace.get("procedure_steps"), limit=8)).lower(),
                    " ".join(_clean_text_list(trace.get("reuse_conditions"), limit=8)).lower(),
                    _clean_text(trace.get("result_summary"), limit=260, lower=True),
                ]
            )
            if any(alias in haystack for alias in aliases):
                return pattern
        return "workspace_command"
    if tool in {"write_workspace_file", "append_workspace_file", "replace_workspace_text", "replace_workspace_lines"}:
        return {
            "write_workspace_file": "write",
            "append_workspace_file": "append",
            "replace_workspace_text": "replace",
            "replace_workspace_lines": "replace",
        }.get(tool, "workspace")
    if tool:
        return tool.removeprefix("browser_")
    return _clean_text(trace.get("trace_kind"), limit=80, lower=True)


def _request_matches_trace(current_event: Any, trace: dict[str, Any], pattern: str) -> bool:
    text = _event_text(current_event)
    if not text:
        return False
    recovery_kind = _clean_text(trace.get("recovery_kind"), limit=80, lower=True)
    recovery_bias = _clean_text(trace.get("recovery_allowed_bias_kind"), limit=80, lower=True)
    if bool(trace.get("recovery_required", False)) and recovery_bias == "workspace_guidance":
        haystack = " ".join(
            [
                pattern,
                recovery_kind,
                _clean_text(trace.get("last_outcome_kind"), limit=80, lower=True),
                _clean_text(trace.get("recovery_suggested_next_step"), limit=260, lower=True),
                _clean_text(trace.get("result_summary"), limit=260, lower=True),
                " ".join(_clean_text_list(trace.get("reuse_conditions"), limit=8)).lower(),
            ]
        )
        return any(token and token in text for token in ("pytest", "test", "tests", "rg", "git", "workspace", "文件", "工作区")) or any(
            token and token in haystack and token in text
            for token in ("pytest", "test", "rg", "git", "workspace", "文件", "工作区")
        )
    trace_kind = _clean_text(trace.get("trace_kind"), limit=80, lower=True)
    if trace_kind == "blocked_boundary_pattern":
        return any(token in text for token in ("blocked", "boundary", "拦", "边界", "别再", "不要", "manual", "takeover", "登录", "browser", "浏览器"))
    if trace_kind == "skill_usage_pattern":
        return any(token in text for token in ("skill", "source", "anchor", "资料", "锚点", "继续", "查", "检索", "搜索"))
    if _trace_is_manual_browser_takeover(trace):
        return any(token in text for token in ("browser", "login", "manual", "takeover", "浏览器", "登录", "接管", "继续"))
    if trace_kind == "workspace_procedure":
        return any(token in text for token in ("file", "workspace", "artifact", "文件", "工作区", "继续"))
    if pattern in _SANDBOX_PATTERN_ALIASES:
        return any(alias in text for alias in _SANDBOX_PATTERN_ALIASES[pattern])
    return bool(pattern and pattern in text)


def _access_boundary_allows_execution(*, embodied_context: dict[str, Any], access_hints: dict[str, Any]) -> bool:
    trace_root = _path_key(embodied_context.get("workspace_root"))
    current_root = _path_key(access_hints.get("workspace_root"))
    if trace_root and trace_root != current_root:
        return False
    sandbox = _dict_or_empty(access_hints.get("sandbox_state"))
    trace_network = _clean_text(embodied_context.get("sandbox_network_policy"), limit=32, lower=True)
    current_network = _clean_text(access_hints.get("sandbox_network_policy") or sandbox.get("network_policy"), limit=32, lower=True)
    if trace_network and current_network and trace_network != current_network:
        return False
    trace_runner = _clean_text(embodied_context.get("sandbox_runner_kind"), limit=80, lower=True)
    current_runner = _clean_text(access_hints.get("sandbox_runner_kind") or sandbox.get("runner_kind"), limit=80, lower=True)
    if trace_runner and current_runner and trace_runner != current_runner:
        return False
    trace_isolation = _clean_text(embodied_context.get("sandbox_isolation_level"), limit=80, lower=True)
    current_isolation = _clean_text(
        access_hints.get("sandbox_isolation_level") or sandbox.get("isolation_level"),
        limit=80,
        lower=True,
    )
    if trace_isolation and current_isolation and trace_isolation != current_isolation:
        return False
    return bool(current_root)


def _candidate_traces(embodied_context: Any) -> list[dict[str, Any]]:
    embodied = _dict_or_empty(embodied_context)
    continuity = _dict_or_empty(embodied.get("procedural_continuity"))
    raw_traces = [
        *(embodied.get("procedural_traces") if isinstance(embodied.get("procedural_traces"), list) else []),
        *(continuity.get("traces") if isinstance(continuity.get("traces"), list) else []),
    ]
    traces = [trace for trace in (normalize_procedural_trace(item) for item in raw_traces) if trace]
    outcomes = normalize_procedural_outcomes(embodied.get("procedural_outcomes"))
    if outcomes:
        traces = calibrate_procedural_traces_with_outcomes(traces, outcomes)
    if not traces and isinstance(embodied.get("procedural_hint"), dict):
        hint = _dict_or_empty(embodied.get("procedural_hint"))
        trace_from_hint = {
            "trace_id": hint.get("trace_id"),
            "trace_kind": hint.get("trace_kind"),
            "source_run_id": hint.get("source_run_id"),
            "source_tool_name": hint.get("source_tool_name"),
            "status": hint.get("source_status") or "completed",
            "procedure_steps": [hint.get("suggested_first_step")],
            "boundary_notes": [hint.get("boundary_note")],
            "confidence": hint.get("confidence"),
        }
        traces = normalize_procedural_traces([trace_from_hint], limit=1)
    by_id: dict[str, dict[str, Any]] = {}
    for trace in traces:
        trace_id = _clean_text(trace.get("trace_id"), limit=80)
        confidence = _clamp01(trace.get("confidence"), 0.0)
        if confidence < 0.35:
            continue
        existing = by_id.get(trace_id)
        if not existing or confidence > _clamp01(existing.get("confidence"), 0.0):
            by_id[trace_id] = trace
    return list(by_id.values())


def normalize_procedural_planning(value: Any) -> dict[str, Any]:
    row = _dict_or_empty(value)
    if not row:
        return {}
    bias_kind = _clean_text(row.get("bias_kind"), limit=80, lower=True)
    if bias_kind not in ALLOWED_PROCEDURAL_PLANNING_BIAS_KINDS:
        return {}
    normalized: dict[str, Any] = {
        "planning_bias": bool(row.get("planning_bias", True)),
        "bias_kind": bias_kind,
        "trace_id": _clean_text(row.get("trace_id"), limit=80),
        "trace_kind": _clean_text(row.get("trace_kind"), limit=80, lower=True),
        "source_run_id": _clean_text(row.get("source_run_id"), limit=128),
        "source_proposal_id": _clean_text(row.get("source_proposal_id"), limit=128),
        "source_tool_name": _clean_text(row.get("source_tool_name"), limit=120, lower=True),
        "suggested_capability_family": _clean_text(row.get("suggested_capability_family"), limit=80, lower=True),
        "suggested_pattern": _clean_text(row.get("suggested_pattern"), limit=120, lower=True),
        "suggested_first_step": _clean_text(row.get("suggested_first_step"), limit=180),
        "must_request_approval": bool(row.get("must_request_approval", False)),
        "requires_approval": bool(row.get("requires_approval", False)),
        "capability_claim": bool(row.get("capability_claim", False)),
        "avoid_repeating_boundary": bool(row.get("avoid_repeating_boundary", False)),
        "boundary_note": _clean_text(row.get("boundary_note"), limit=220),
        "confidence": _clamp01(row.get("confidence"), 0.0),
        "reason": _clean_text(row.get("reason"), limit=220),
    }
    if bias_kind == "sandbox_execute":
        executor = _clean_text(row.get("suggested_executor"), limit=64, lower=True)
        argv = _clean_text_list(row.get("suggested_argv"), limit=16, item_limit=120)
        profile = _clean_text(row.get("suggested_profile"), limit=64, lower=True)
        if executor in {"pytest", "rg", "git"} and argv:
            normalized["suggested_executor"] = executor
            normalized["suggested_argv"] = argv
            normalized["suggested_profile"] = profile or normalized["suggested_pattern"] or executor
    return {
        key: value
        for key, value in normalized.items()
        if value not in ("", [], {}) and value is not None
    }


def _bias_from_trace(
    *,
    trace: dict[str, Any],
    pattern: str,
    embodied_context: dict[str, Any],
    access_hints: dict[str, Any],
) -> dict[str, Any]:
    trace_kind = _clean_text(trace.get("trace_kind"), limit=80, lower=True)
    boundary_note = _first_boundary_note(trace)
    hint = build_procedural_hint([trace])
    first_step = _clean_text(
        hint.get("suggested_first_step")
        or (_clean_text_list(trace.get("procedure_steps"), limit=1) or [""])[0],
        limit=180,
    )
    common = {
        "planning_bias": True,
        "trace_id": trace.get("trace_id"),
        "trace_kind": trace_kind,
        "source_run_id": trace.get("source_run_id"),
        "source_proposal_id": trace.get("source_proposal_id"),
        "source_tool_name": trace.get("source_tool_name"),
        "suggested_pattern": pattern,
        "suggested_first_step": first_step,
        "boundary_note": boundary_note,
        "confidence": trace.get("confidence"),
    }
    if bool(trace.get("recovery_required", False)):
        recovery_kind = _clean_text(trace.get("recovery_kind"), limit=80, lower=True)
        allowed_bias = _clean_text(trace.get("recovery_allowed_bias_kind"), limit=80, lower=True)
        next_step = _clean_text(trace.get("recovery_suggested_next_step"), limit=180) or first_step
        if allowed_bias == "browser_manual_takeover":
            return normalize_procedural_planning(
                {
                    **common,
                    "bias_kind": "browser_manual_takeover",
                    "suggested_capability_family": "browser",
                    "suggested_first_step": next_step,
                    "must_request_approval": True,
                    "requires_approval": True,
                    "capability_claim": False,
                    "avoid_repeating_boundary": True,
                    "boundary_note": boundary_note or next_step,
                    "reason": "preserve procedural recovery manual-takeover boundary",
                }
            )
        if allowed_bias == "boundary_only":
            return normalize_procedural_planning(
                {
                    **common,
                    "bias_kind": "boundary_only",
                    "suggested_first_step": next_step,
                    "must_request_approval": True,
                    "requires_approval": True,
                    "capability_claim": False,
                    "avoid_repeating_boundary": True,
                    "boundary_note": boundary_note or next_step or recovery_kind,
                    "reason": "avoid repeating a procedural recovery boundary",
                }
            )
        if allowed_bias == "hold":
            return normalize_procedural_planning(
                {
                    **common,
                    "bias_kind": "boundary_only",
                    "suggested_first_step": next_step,
                    "must_request_approval": True,
                    "requires_approval": True,
                    "capability_claim": False,
                    "avoid_repeating_boundary": True,
                    "boundary_note": boundary_note or next_step or "prior attempt has not executed",
                    "reason": "hold unresolved procedural recovery until approval or execution happens",
                }
            )
        return normalize_procedural_planning(
            {
                **common,
                "bias_kind": "workspace_guidance",
                "suggested_capability_family": "workspace",
                "suggested_first_step": next_step,
                "must_request_approval": False,
                "requires_approval": False,
                "capability_claim": False,
                "avoid_repeating_boundary": False,
                "reason": "inspect procedural recovery evidence before reusing execution",
            }
        )
    if _trace_is_manual_browser_takeover(trace):
        return normalize_procedural_planning(
            {
                **common,
                "bias_kind": "browser_manual_takeover",
                "suggested_capability_family": "browser",
                "must_request_approval": True,
                "requires_approval": True,
                "capability_claim": False,
                "avoid_repeating_boundary": True,
                "reason": "preserve manual browser takeover boundary before continuing",
            }
        )
    if bool(trace.get("boundary_reinforced", False)):
        note = boundary_note or _clean_text(trace.get("last_outcome_kind"), limit=80, lower=True)
        return normalize_procedural_planning(
            {
                **common,
                "bias_kind": "boundary_only",
                "must_request_approval": bool(hint.get("must_request_approval", False)),
                "requires_approval": bool(hint.get("must_request_approval", False)),
                "capability_claim": False,
                "avoid_repeating_boundary": True,
                "boundary_note": note or "prior outcome reinforced this boundary",
                "reason": "avoid repeating a boundary-reinforced procedural outcome",
            }
        )
    if trace_kind == "blocked_boundary_pattern":
        return normalize_procedural_planning(
            {
                **common,
                "bias_kind": "boundary_only",
                "must_request_approval": bool(hint.get("must_request_approval", False)),
                "requires_approval": bool(hint.get("must_request_approval", False)),
                "capability_claim": False,
                "avoid_repeating_boundary": True,
                "reason": "avoid repeating a blocked procedural boundary",
            }
        )
    if trace_kind == "skill_usage_pattern":
        return normalize_procedural_planning(
            {
                **common,
                "bias_kind": "skill_guidance",
                "suggested_capability_family": "skill",
                "must_request_approval": bool(hint.get("must_request_approval", False)),
                "requires_approval": bool(hint.get("must_request_approval", False)),
                "capability_claim": True,
                "avoid_repeating_boundary": False,
                "reason": "reuse skill-guided procedural continuity without registry mutation",
            }
        )
    if trace_kind == "workspace_procedure":
        return normalize_procedural_planning(
            {
                **common,
                "bias_kind": "workspace_guidance",
                "suggested_capability_family": "workspace",
                "must_request_approval": bool(hint.get("must_request_approval", False)),
                "requires_approval": bool(hint.get("must_request_approval", False)),
                "capability_claim": True,
                "avoid_repeating_boundary": False,
                "reason": "reuse workspace procedural continuity as planning guidance",
            }
        )
    command = _SANDBOX_PATTERN_COMMANDS.get(pattern)
    if (
        trace_kind == "sandbox_execution_pattern"
        and command
        and _access_boundary_allows_execution(embodied_context=embodied_context, access_hints=access_hints)
    ):
        executor, argv = command
        return normalize_procedural_planning(
            {
                **common,
                "bias_kind": "sandbox_execute",
                "suggested_capability_family": "sandbox",
                "suggested_executor": executor,
                "suggested_argv": argv,
                "suggested_profile": pattern,
                "must_request_approval": True,
                "requires_approval": True,
                "capability_claim": True,
                "avoid_repeating_boundary": False,
                "reason": f"reuse a completed bounded sandbox {pattern} procedure",
            }
        )
    return {}


def build_procedural_planning_bias(
    *,
    current_event: Any,
    embodied_context: Any,
    access_hints: Any,
) -> dict[str, Any]:
    embodied = _dict_or_empty(embodied_context)
    access = _dict_or_empty(access_hints)
    candidates: list[tuple[int, float, str, dict[str, Any], str]] = []
    for trace in _candidate_traces(embodied):
        pattern = _pattern_from_trace(trace)
        if not _request_matches_trace(current_event, trace, pattern):
            continue
        trace_kind = _clean_text(trace.get("trace_kind"), limit=80, lower=True)
        priority = 0
        if trace_kind == "sandbox_execution_pattern":
            priority = 4
        elif trace_kind in {"skill_usage_pattern", "workspace_procedure"}:
            priority = 3
        elif _trace_is_manual_browser_takeover(trace):
            priority = 2
        elif trace_kind == "blocked_boundary_pattern":
            priority = 1
        candidates.append((priority, _clamp01(trace.get("confidence"), 0.0), _clean_text(trace.get("trace_id")), trace, pattern))
    if not candidates:
        return {}
    candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    for _, _, _, trace, pattern in candidates:
        bias = _bias_from_trace(trace=trace, pattern=pattern, embodied_context=embodied, access_hints=access)
        if bias:
            return bias
    return {}


__all__ = [
    "ALLOWED_PROCEDURAL_PLANNING_BIAS_KINDS",
    "build_procedural_planning_bias",
    "normalize_procedural_planning",
]
