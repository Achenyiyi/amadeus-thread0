from __future__ import annotations

from typing import Any


ARTIFACT_APPRAISAL_BRIDGE_READY = "artifact_appraisal_bridge_ready"
ARTIFACT_APPRAISAL_BRIDGE_EMPTY = "artifact_appraisal_bridge_empty"
ARTIFACT_APPRAISAL_BRIDGE_BLOCKED = "artifact_appraisal_bridge_blocked"

AUTHORITY_BOUNDARY = {
    "persona_core_mutation_allowed": False,
    "memory_write_allowed": False,
    "external_mutation_allowed": False,
    "live_microphone_enabled": False,
    "live_camera_enabled": False,
    "background_screen_capture_enabled": False,
    "multimodal_model_api_called": False,
    "writeback_allowed": False,
}

ACCESS_FRICTION_MARKERS = (
    "login",
    "log in",
    "sign in",
    "sign-in",
    "signin",
    "session",
    "expired",
    "access",
    "credential",
    "permission",
    "account",
    "登录",
    "登入",
    "会话",
    "过期",
    "凭证",
    "权限",
    "账号",
    "账户",
)


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


def _tags_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return " ".join(_clean(item, limit=120) for item in _list_or_empty(value))


def _has_access_friction(observation: dict[str, Any]) -> bool:
    haystack = " ".join(
        [
            _clean(observation.get("semantic_label"), limit=240),
            _clean(observation.get("summary"), limit=960),
            _clean(observation.get("observed_text"), limit=960),
            _tags_text(observation.get("tags")),
        ]
    ).lower()
    return any(marker in haystack for marker in ACCESS_FRICTION_MARKERS)


def _is_admissible_observation(observation: dict[str, Any]) -> tuple[bool, str]:
    if _clean(observation.get("source")) != "approved_metadata":
        return False, "source_not_approved_metadata"
    if bool(observation.get("model_api_called", False)):
        return False, "model_api_called"
    if bool(observation.get("writeback_ready", False)):
        return False, "writeback_ready"
    if not _clean(observation.get("source_ref_id")):
        return False, "missing_source_ref_id"
    if not (_clean(observation.get("summary")) or _clean(observation.get("observed_text"))):
        return False, "missing_semantic_content"
    return True, ""


def _evidence_item(observation: dict[str, Any], index: int) -> dict[str, Any]:
    source_ref_id = _safe_id(observation.get("source_ref_id"), fallback=f"artifact-{index + 1}")
    summary = _clean(observation.get("summary") or observation.get("observed_text"))
    access_friction = _has_access_friction(observation)
    axes = ["task_relevance"]
    if access_friction:
        axes.append("access_friction")
    delta: dict[str, Any] = {
        "scene": "artifact_review",
        "task_relevance": "high",
        "access_friction": access_friction,
    }
    if access_friction:
        delta["boundary_condition"] = "access_or_session_friction"
    return {
        "evidence_id": f"artifact-evidence-{source_ref_id}",
        "source_ref_id": source_ref_id,
        "source_kind": _clean(observation.get("source_kind"), limit=120) or "unknown",
        "semantic_label": _clean(observation.get("semantic_label"), limit=160),
        "summary": summary,
        "appraisal_axes": axes,
        "suggested_appraisal_delta": delta,
        "authority": {
            "source": "approved_metadata",
            "model_api_called": False,
            "memory_write_allowed": False,
            "writeback_ready": False,
        },
    }


def _influence_summary(evidence_items: list[dict[str, Any]]) -> dict[str, Any]:
    access_friction = any(
        bool(_dict_or_empty(item.get("suggested_appraisal_delta")).get("access_friction", False))
        for item in evidence_items
    )
    return {
        "artifact_relevance": "high" if evidence_items else "none",
        "access_friction_observed": access_friction,
        "should_request_live_capture": False,
        "should_write_memory": False,
    }


def build_artifact_appraisal_readback(artifact_semantics: dict[str, Any] | None) -> dict[str, Any]:
    semantics = _dict_or_empty(artifact_semantics)
    observations = [
        _dict_or_empty(item)
        for item in _list_or_empty(semantics.get("semantic_observations"))
        if isinstance(item, dict)
    ]
    evidence_items: list[dict[str, Any]] = []
    blocked_reasons: list[str] = []
    blocked_count = 0
    for index, observation in enumerate(observations):
        admissible, reason = _is_admissible_observation(observation)
        if not admissible:
            blocked_count += 1
            if reason:
                blocked_reasons.append(reason)
            continue
        evidence_items.append(_evidence_item(observation, index))

    semantic_status = _clean(semantics.get("status"))
    if evidence_items:
        status = "ready"
        readiness = ARTIFACT_APPRAISAL_BRIDGE_READY
    elif semantic_status == "blocked":
        status = "blocked"
        readiness = ARTIFACT_APPRAISAL_BRIDGE_BLOCKED
    else:
        status = "empty"
        readiness = ARTIFACT_APPRAISAL_BRIDGE_EMPTY

    return {
        "schema": "artifact_appraisal_bridge.v1",
        "status": status,
        "readiness_status": readiness,
        "evidence_items": evidence_items,
        "evidence_count": len(evidence_items),
        "blocked_observation_count": blocked_count,
        "blocked_reasons": blocked_reasons,
        "influence_summary": _influence_summary(evidence_items),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "model_api_called": False,
        "writeback_ready_count": 0,
    }


__all__ = [
    "ARTIFACT_APPRAISAL_BRIDGE_BLOCKED",
    "ARTIFACT_APPRAISAL_BRIDGE_EMPTY",
    "ARTIFACT_APPRAISAL_BRIDGE_READY",
    "AUTHORITY_BOUNDARY",
    "build_artifact_appraisal_readback",
]
