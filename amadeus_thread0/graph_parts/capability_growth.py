from __future__ import annotations

import hashlib
from typing import Any


_FAMILIES = {"workspace", "sandbox", "browser", "skill", "multimodal"}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _clean_text(value: Any, *, limit: int = 220, lower: bool = False) -> str:
    text = str(value or "").strip()[: max(1, int(limit))]
    return text.lower() if lower else text


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        cast = float(value)
    except Exception:
        cast = float(default)
    return round(max(0.0, min(1.0, cast)), 3)


def _trace_id(trace: dict[str, Any]) -> str:
    return _clean_text(trace.get("trace_id") or trace.get("source_trace_id"), limit=120)


def derive_workflow_candidate(traces: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [dict(item) for item in _list_or_empty(traces) if isinstance(item, dict)]
    completed = [row for row in rows if _clean_text(row.get("status"), lower=True) == "completed" or bool(row.get("completed", False))]
    if not completed:
        return {
            "workflow_id": "workflow-blocked",
            "origin_trace_ids": [_trace_id(row) for row in rows if _trace_id(row)],
            "capability_family": "",
            "reuse_confidence": 0.0,
            "approval_requirements": [],
            "blocked_surfaces": ["no_completed_evidence"],
            "recommended_next_action": "hold",
            "status": "blocked",
            "block_reasons": ["no_completed_evidence"],
            "capability_claim": False,
        }
    family_counts: dict[str, int] = {}
    for row in completed:
        family = _clean_text(row.get("capability_family") or row.get("suggested_capability_family"), lower=True)
        if family in _FAMILIES:
            family_counts[family] = family_counts.get(family, 0) + 1
    family = max(family_counts, key=family_counts.get) if family_counts else "workspace"
    ids = [_trace_id(row) for row in completed if _trace_id(row)]
    confidence = sum(_clamp01(row.get("confidence"), 0.5) for row in completed) / max(1, len(completed))
    recommended = "propose_skill" if len(completed) >= 2 and confidence >= 0.8 else "reuse"
    if family == "browser":
        recommended = "ask_operator"
    if family == "multimodal":
        recommended = "reuse"
    seed = "|".join([family, *ids]) or family
    return {
        "workflow_id": "workflow-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12],
        "origin_trace_ids": ids,
        "capability_family": family,
        "reuse_confidence": round(confidence, 3),
        "approval_requirements": ["external_mutation"] if family in {"sandbox", "browser", "workspace"} else [],
        "blocked_surfaces": [],
        "recommended_next_action": recommended,
        "status": "candidate",
        "capability_claim": False,
    }


def workflow_candidate_to_planning_bias(candidate: dict[str, Any] | None, digital_body_state: dict[str, Any] | None) -> dict[str, Any]:
    row = dict(candidate) if isinstance(candidate, dict) else {}
    if row.get("status") != "candidate":
        return {}
    body = dict(digital_body_state or {}) if isinstance(digital_body_state, dict) else {}
    family = _clean_text(row.get("capability_family"), lower=True)
    access_state = body.get("access_state") if isinstance(body.get("access_state"), dict) else {}
    sandbox_state = access_state.get("sandbox_state") if isinstance(access_state.get("sandbox_state"), dict) else {}
    if family == "sandbox" and not sandbox_state:
        return {
            "planning_bias": True,
            "bias_kind": "boundary_only",
            "workflow_id": row.get("workflow_id", ""),
            "requires_approval": True,
            "capability_claim": False,
            "reason": "sandbox workflow candidate held until matching sandbox state is present",
        }
    return {
        "planning_bias": True,
        "bias_kind": f"{family}_workflow_guidance",
        "workflow_id": row.get("workflow_id", ""),
        "origin_trace_ids": list(row.get("origin_trace_ids") or []),
        "suggested_capability_family": family,
        "recommended_next_action": row.get("recommended_next_action", "hold"),
        "requires_approval": bool(row.get("approval_requirements")),
        "capability_claim": False,
        "confidence": row.get("reuse_confidence", 0.0),
    }


def summarize_workflow_candidate(candidate: dict[str, Any] | None) -> str:
    row = dict(candidate) if isinstance(candidate, dict) else {}
    if not row:
        return ""
    return (
        f"{row.get('status', 'candidate')}:{row.get('capability_family', 'unknown')}:"
        f"{row.get('recommended_next_action', 'hold')}:{row.get('workflow_id', '')}"
    )


__all__ = [
    "derive_workflow_candidate",
    "summarize_workflow_candidate",
    "workflow_candidate_to_planning_bias",
]
