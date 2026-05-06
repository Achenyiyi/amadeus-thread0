from __future__ import annotations

from typing import Any


ARTIFACT_MOTIVE_BRIDGE_READY = "artifact_motive_bridge_ready"
ARTIFACT_MOTIVE_BRIDGE_EMPTY = "artifact_motive_bridge_empty"
ARTIFACT_MOTIVE_BRIDGE_BLOCKED = "artifact_motive_bridge_blocked"

AUTHORITY_BOUNDARY = {
    "persona_core_mutation_allowed": False,
    "memory_write_allowed": False,
    "behavior_mutation_allowed": False,
    "external_mutation_allowed": False,
    "live_capture_enabled": False,
    "multimodal_model_api_called": False,
    "writeback_allowed": False,
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _clean(value: Any, *, limit: int = 640) -> str:
    return str(value or "").strip()[: max(1, int(limit))]


def _safe_id(value: Any, *, fallback: str) -> str:
    text = _clean(value, limit=120)
    if text:
        return text
    return fallback


def _axes(evidence: dict[str, Any], delta: dict[str, Any]) -> list[str]:
    axes = [
        _clean(item, limit=120)
        for item in _list_or_empty(evidence.get("appraisal_axes"))
        if _clean(item, limit=120)
    ]
    if not axes and _clean(delta.get("task_relevance")):
        axes.append("task_relevance")
    if bool(delta.get("access_friction", False)) and "access_friction" not in axes:
        axes.append("access_friction")
    return axes


def _is_admissible_evidence(evidence: dict[str, Any]) -> tuple[bool, str]:
    authority = _dict_or_empty(evidence.get("authority"))
    if _clean(authority.get("source")) != "approved_metadata":
        return False, "source_not_approved_metadata"
    if bool(authority.get("model_api_called", False)) or bool(evidence.get("model_api_called", False)):
        return False, "model_api_called"
    if bool(authority.get("memory_write_allowed", False)) or bool(evidence.get("memory_write_allowed", False)):
        return False, "memory_write_allowed"
    if bool(authority.get("writeback_ready", False)) or bool(evidence.get("writeback_ready", False)):
        return False, "writeback_ready"
    if not _clean(evidence.get("source_ref_id")):
        return False, "missing_source_ref_id"
    delta = _dict_or_empty(evidence.get("suggested_appraisal_delta"))
    axes = _axes(evidence, delta)
    if "task_relevance" not in axes and _clean(delta.get("task_relevance")) != "high":
        return False, "missing_task_relevance"
    return True, ""


def _hint_for_evidence(evidence: dict[str, Any], index: int) -> dict[str, Any]:
    source_ref_id = _safe_id(evidence.get("source_ref_id"), fallback=f"artifact-{index + 1}")
    source_evidence_id = _safe_id(
        evidence.get("evidence_id"),
        fallback=f"artifact-evidence-{source_ref_id}",
    )
    delta = _dict_or_empty(evidence.get("suggested_appraisal_delta"))
    axes = _axes(evidence, delta)
    access_friction = bool(delta.get("access_friction", False)) or "access_friction" in axes
    if access_friction:
        primary_motive = "restore_access_continuity"
        tension = "task_continuity_vs_access_friction"
        goal_frame = "Treat the artifact as an access/session condition to resolve before continuing the task."
    else:
        primary_motive = "continue_artifact_review"
        tension = "task_relevance_vs_uncertainty"
        goal_frame = "Use the approved artifact evidence as task context while keeping behavior unchanged."
    return {
        "hint_id": f"artifact-motive-{source_ref_id}",
        "source_evidence_id": source_evidence_id,
        "source_ref_id": source_ref_id,
        "source_kind": _clean(evidence.get("source_kind"), limit=120) or "unknown",
        "semantic_label": _clean(evidence.get("semantic_label"), limit=160),
        "summary": _clean(evidence.get("summary")),
        "primary_motive_hint": primary_motive,
        "motive_tension_hint": tension,
        "goal_frame_hint": goal_frame,
        "derived_from_axes": axes,
        "authority": {
            "source": "artifact_appraisal_evidence",
            "model_api_called": False,
            "memory_write_allowed": False,
            "writeback_ready": False,
            "behavior_mutation_allowed": False,
        },
    }


def _motive_summary(hints: list[dict[str, Any]]) -> dict[str, Any]:
    if not hints:
        return {
            "primary_motive_hint": "",
            "motive_tension_hint": "",
            "goal_bias": "none",
            "should_mutate_behavior": False,
            "should_write_memory": False,
        }
    first = hints[0]
    primary = _clean(first.get("primary_motive_hint"), limit=120)
    if primary == "restore_access_continuity":
        goal_bias = "resolve_access_before_task_continuation"
    else:
        goal_bias = "continue_task_with_artifact_context"
    return {
        "primary_motive_hint": primary,
        "motive_tension_hint": _clean(first.get("motive_tension_hint"), limit=160),
        "goal_bias": goal_bias,
        "should_mutate_behavior": False,
        "should_write_memory": False,
    }


def build_artifact_motive_readback(artifact_appraisal: dict[str, Any] | None) -> dict[str, Any]:
    appraisal = _dict_or_empty(artifact_appraisal)
    evidence_items = [
        _dict_or_empty(item)
        for item in _list_or_empty(appraisal.get("evidence_items"))
        if isinstance(item, dict)
    ]
    hints: list[dict[str, Any]] = []
    blocked_reasons: list[str] = []
    blocked_count = 0
    for index, evidence in enumerate(evidence_items):
        admissible, reason = _is_admissible_evidence(evidence)
        if not admissible:
            blocked_count += 1
            if reason:
                blocked_reasons.append(reason)
            continue
        hints.append(_hint_for_evidence(evidence, index))

    appraisal_status = _clean(appraisal.get("status"))
    if hints:
        status = "ready"
        readiness = ARTIFACT_MOTIVE_BRIDGE_READY
    elif appraisal_status == "blocked":
        status = "blocked"
        readiness = ARTIFACT_MOTIVE_BRIDGE_BLOCKED
    else:
        status = "empty"
        readiness = ARTIFACT_MOTIVE_BRIDGE_EMPTY

    return {
        "schema": "artifact_motive_bridge.v1",
        "status": status,
        "readiness_status": readiness,
        "motive_hints": hints,
        "hint_count": len(hints),
        "blocked_evidence_count": blocked_count,
        "blocked_reasons": blocked_reasons,
        "motive_summary": _motive_summary(hints),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "model_api_called": False,
        "writeback_ready_count": 0,
    }


__all__ = [
    "ARTIFACT_MOTIVE_BRIDGE_BLOCKED",
    "ARTIFACT_MOTIVE_BRIDGE_EMPTY",
    "ARTIFACT_MOTIVE_BRIDGE_READY",
    "AUTHORITY_BOUNDARY",
    "build_artifact_motive_readback",
]
