from __future__ import annotations

from typing import Any


ARTIFACT_BEHAVIOR_ALIGNMENT_READY = "artifact_behavior_alignment_ready"
ARTIFACT_BEHAVIOR_ALIGNMENT_EMPTY = "artifact_behavior_alignment_empty"
ARTIFACT_BEHAVIOR_ALIGNMENT_BLOCKED = "artifact_behavior_alignment_blocked"

AUTHORITY_BOUNDARY = {
    "persona_core_mutation_allowed": False,
    "memory_write_allowed": False,
    "behavior_mutation_allowed": False,
    "external_mutation_allowed": False,
    "live_capture_enabled": False,
    "multimodal_model_api_called": False,
    "writeback_allowed": False,
}

_COMPATIBLE_MOTIVES = {
    "restore_access_continuity": {
        "restore_access_continuity",
        "request_access_help",
        "resolve_access_before_task",
        "resolve_access_before_task_continuation",
        "access_recovery",
        "continue_after_access_recovery",
    },
    "continue_artifact_review": {
        "continue_artifact_review",
        "continue_workspace_task",
        "continue_task_with_artifact_context",
        "inspect_artifact",
        "review_artifact",
        "solve_task",
    },
}

_CONFLICT_MOTIVES = {
    "restore_access_continuity": {
        "ignore_access_friction",
        "skip_access_resolution",
        "proceed_without_access_resolution",
    },
    "continue_artifact_review": {
        "ignore_artifact_context",
        "skip_artifact_review",
        "discard_artifact_context",
    },
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _clean(value: Any, *, limit: int = 240) -> str:
    return str(value or "").strip()[: max(1, int(limit))]


def _safe_id(value: Any, *, fallback: str) -> str:
    text = _clean(value, limit=120)
    return text or fallback


def _candidate_motives(behavior_action: dict[str, Any], behavior_plan: dict[str, Any]) -> set[str]:
    values = {
        _clean(behavior_action.get("primary_motive"), limit=120),
        _clean(behavior_action.get("motive"), limit=120),
        _clean(behavior_action.get("action_target"), limit=120),
        _clean(behavior_plan.get("primary_motive"), limit=120),
        _clean(behavior_plan.get("motive"), limit=120),
        _clean(behavior_plan.get("kind"), limit=120),
        _clean(behavior_plan.get("interaction_mode"), limit=120),
    }
    return {value for value in values if value}


def _is_admissible_hint(hint: dict[str, Any]) -> tuple[bool, str]:
    authority = _dict_or_empty(hint.get("authority"))
    if _clean(authority.get("source")) != "artifact_appraisal_evidence":
        return False, "source_not_artifact_appraisal_evidence"
    for key in (
        "model_api_called",
        "memory_write_allowed",
        "writeback_ready",
        "behavior_mutation_allowed",
        "behavior_mutation_applied",
    ):
        if bool(authority.get(key, False)) or bool(hint.get(key, False)):
            return False, key
    if not _clean(hint.get("source_ref_id")):
        return False, "missing_source_ref_id"
    if not _clean(hint.get("primary_motive_hint")):
        return False, "missing_primary_motive_hint"
    return True, ""


def _alignment_status(primary_hint: str, motives: set[str]) -> tuple[str, str]:
    if motives & _CONFLICT_MOTIVES.get(primary_hint, set()):
        return "behavior_conflict_observed", "behavior_plan_conflicts_with_artifact_motive_hint"
    compatible = _COMPATIBLE_MOTIVES.get(primary_hint, {primary_hint})
    if primary_hint in motives or bool(motives & compatible):
        return "causally_aligned", "artifact_motive_hint_reflected_in_behavior_plan"
    return "advisory_not_reflected", "artifact_motive_hint_not_reflected_in_behavior_plan"


def _alignment_item(
    hint: dict[str, Any],
    behavior_action: dict[str, Any],
    behavior_plan: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    source_ref_id = _safe_id(hint.get("source_ref_id"), fallback=f"artifact-{index + 1}")
    primary_hint = _clean(hint.get("primary_motive_hint"), limit=120)
    motives = _candidate_motives(behavior_action, behavior_plan)
    status, reason = _alignment_status(primary_hint, motives)
    return {
        "alignment_id": f"artifact-behavior-{source_ref_id}",
        "source_hint_id": _safe_id(hint.get("hint_id"), fallback=f"artifact-motive-{source_ref_id}"),
        "source_ref_id": source_ref_id,
        "primary_motive_hint": primary_hint,
        "behavior_primary_motive": _clean(behavior_action.get("primary_motive"), limit=120),
        "plan_primary_motive": _clean(behavior_plan.get("primary_motive"), limit=120),
        "alignment_status": status,
        "alignment_reason": reason,
        "behavior_mutation_applied": False,
        "authority": {
            "source": "artifact_motive_hint",
            "model_api_called": False,
            "memory_write_allowed": False,
            "writeback_ready": False,
            "behavior_mutation_allowed": False,
            "behavior_mutation_applied": False,
        },
    }


def _alignment_summary(items: list[dict[str, Any]], *, status: str) -> dict[str, Any]:
    aligned_count = sum(1 for item in items if item.get("alignment_status") == "causally_aligned")
    not_reflected_count = sum(
        1 for item in items if item.get("alignment_status") == "advisory_not_reflected"
    )
    conflict_count = sum(
        1 for item in items if item.get("alignment_status") == "behavior_conflict_observed"
    )
    if not items:
        alignment_status = status
    elif conflict_count:
        alignment_status = "behavior_conflict_observed"
    elif not_reflected_count:
        alignment_status = "advisory_not_reflected"
    else:
        alignment_status = "causally_aligned"
    return {
        "alignment_status": alignment_status,
        "aligned_count": aligned_count,
        "advisory_not_reflected_count": not_reflected_count,
        "conflict_count": conflict_count,
        "should_mutate_behavior": False,
        "should_write_memory": False,
    }


def build_artifact_behavior_alignment_readback(
    artifact_motive: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None,
    behavior_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    motive = _dict_or_empty(artifact_motive)
    action = _dict_or_empty(behavior_action)
    plan = _dict_or_empty(behavior_plan)
    raw_hints = [
        _dict_or_empty(item)
        for item in _list_or_empty(motive.get("motive_hints"))
        if isinstance(item, dict)
    ]
    items: list[dict[str, Any]] = []
    blocked_reasons: list[str] = []
    blocked_count = 0
    for index, hint in enumerate(raw_hints):
        admissible, reason = _is_admissible_hint(hint)
        if not admissible:
            blocked_count += 1
            if reason:
                blocked_reasons.append(reason)
            continue
        items.append(_alignment_item(hint, action, plan, index))

    motive_status = _clean(motive.get("status"))
    if items:
        status = "ready"
        readiness = ARTIFACT_BEHAVIOR_ALIGNMENT_READY
    elif motive_status == "blocked" or blocked_count:
        status = "blocked"
        readiness = ARTIFACT_BEHAVIOR_ALIGNMENT_BLOCKED
    else:
        status = "empty"
        readiness = ARTIFACT_BEHAVIOR_ALIGNMENT_EMPTY

    return {
        "schema": "artifact_behavior_alignment.v1",
        "status": status,
        "readiness_status": readiness,
        "alignment_items": items,
        "alignment_count": len(items),
        "blocked_hint_count": blocked_count,
        "blocked_reasons": blocked_reasons,
        "alignment_summary": _alignment_summary(items, status=status),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "model_api_called": False,
        "writeback_ready_count": 0,
    }


__all__ = [
    "ARTIFACT_BEHAVIOR_ALIGNMENT_BLOCKED",
    "ARTIFACT_BEHAVIOR_ALIGNMENT_EMPTY",
    "ARTIFACT_BEHAVIOR_ALIGNMENT_READY",
    "AUTHORITY_BOUNDARY",
    "build_artifact_behavior_alignment_readback",
]

