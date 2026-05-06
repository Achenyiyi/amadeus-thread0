from __future__ import annotations

from typing import Any

from .multimodal_sources import normalize_multimodal_source


ARTIFACT_PERCEPTION_SEMANTICS_READY = "artifact_perception_semantics_ready"
ARTIFACT_PERCEPTION_SEMANTICS_EMPTY = "artifact_perception_semantics_empty"
ARTIFACT_PERCEPTION_SEMANTICS_BLOCKED = "artifact_perception_semantics_blocked"

SOURCE_KIND_BY_MODALITY = {
    "text": "text",
    "image": "image_file",
    "audio": "audio_file",
    "screen": "screen_snapshot_file",
    "browser_capture": "browser_capture_ref",
}

AUTHORITY_BOUNDARY = {
    "persona_core_mutation_allowed": False,
    "memory_write_allowed": False,
    "external_mutation_allowed": False,
    "live_microphone_enabled": False,
    "live_camera_enabled": False,
    "background_screen_capture_enabled": False,
    "secret_capture_enabled": False,
    "multimodal_model_api_called": False,
}

SUMMARY_FIELDS = ("semantic_summary", "operator_summary", "caption")
TEXT_FIELDS = ("observed_text", "ocr_text", "transcript")
KIND_BY_FIELD = {
    "semantic_summary": "operator_provided_artifact_semantics",
    "operator_summary": "operator_provided_artifact_semantics",
    "caption": "operator_provided_artifact_semantics",
    "observed_text": "provided_observed_text",
    "ocr_text": "provided_ocr_text",
    "transcript": "provided_transcript",
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _clean(value: Any, *, limit: int = 640) -> str:
    return str(value or "").strip()[: max(1, int(limit))]


def _tags(value: Any) -> list[str]:
    if isinstance(value, str):
        rows = [item.strip() for item in value.split(",")]
    else:
        rows = [str(item or "").strip() for item in _list_or_empty(value)]
    return [item for item in rows if item][:12]


def _confidence(value: Any) -> float:
    try:
        number = float(value)
    except Exception:
        return 0.0
    if number < 0.0:
        return 0.0
    if number > 1.0:
        return 1.0
    return number


def _semantic_field(raw: dict[str, Any]) -> tuple[str, str]:
    for key in SUMMARY_FIELDS + TEXT_FIELDS:
        text = _clean(raw.get(key))
        if text:
            return key, text
    return "", ""


def _observation(raw: dict[str, Any], normalized: dict[str, Any]) -> dict[str, Any] | None:
    field, text = _semantic_field(raw)
    if not field or not text:
        return None
    modality = _clean(normalized.get("modality"))
    source_id = _clean(normalized.get("source_id") or raw.get("source_ref_id"), limit=120)
    observed_text = text if field in TEXT_FIELDS else _clean(raw.get("observed_text"))
    semantic_label = _clean(raw.get("semantic_label") or raw.get("label") or normalized.get("artifact_label"), limit=160)
    return {
        "source_ref_id": source_id,
        "source_kind": SOURCE_KIND_BY_MODALITY.get(modality, modality or "unknown"),
        "modality": modality,
        "observation_kind": KIND_BY_FIELD.get(field, "operator_provided_artifact_semantics"),
        "semantic_label": semantic_label,
        "summary": text,
        "observed_text": observed_text,
        "tags": _tags(raw.get("semantic_tags") or raw.get("tags")),
        "confidence": _confidence(raw.get("confidence")),
        "source": "approved_metadata",
        "model_api_called": False,
        "writeback_ready": False,
    }


def build_artifact_semantics_readback(raw_sources: list[dict[str, Any]] | None) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    blocked_reasons: list[str] = []
    seen: set[str] = set()
    blocked_count = 0
    for raw_value in _list_or_empty(raw_sources):
        raw = _dict_or_empty(raw_value)
        if not raw:
            continue
        normalized = normalize_multimodal_source(raw)
        if normalized.get("status") != "available":
            blocked_count += 1
            for reason in _list_or_empty(normalized.get("block_reasons")):
                text = _clean(reason, limit=120)
                if text:
                    blocked_reasons.append(text)
            continue
        observation = _observation(raw, normalized)
        if not observation:
            continue
        key = (
            observation.get("source_ref_id"),
            observation.get("observation_kind"),
            observation.get("summary"),
        )
        digest = "|".join(str(part or "") for part in key)
        if digest in seen:
            continue
        seen.add(digest)
        observations.append(observation)

    if observations:
        status = "ready"
        readiness = ARTIFACT_PERCEPTION_SEMANTICS_READY
    elif blocked_count:
        status = "blocked"
        readiness = ARTIFACT_PERCEPTION_SEMANTICS_BLOCKED
    else:
        status = "empty"
        readiness = ARTIFACT_PERCEPTION_SEMANTICS_EMPTY

    return {
        "schema": "artifact_perception_semantics.v1",
        "status": status,
        "readiness_status": readiness,
        "semantic_observations": observations,
        "observation_count": len(observations),
        "blocked_source_count": blocked_count,
        "blocked_reasons": blocked_reasons,
        "model_api_called": False,
        "writeback_ready_count": 0,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


__all__ = [
    "ARTIFACT_PERCEPTION_SEMANTICS_BLOCKED",
    "ARTIFACT_PERCEPTION_SEMANTICS_EMPTY",
    "ARTIFACT_PERCEPTION_SEMANTICS_READY",
    "AUTHORITY_BOUNDARY",
    "build_artifact_semantics_readback",
]
