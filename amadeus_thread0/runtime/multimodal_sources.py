from __future__ import annotations

import hashlib
import json
from typing import Any


MULTIMODAL_PERCEPTION_PHASE2_READY = "multimodal_perception_phase2_ready"
MULTIMODAL_PERCEPTION_PHASE2_IN_PROGRESS = "multimodal_perception_phase2_in_progress"

PHASE1_MODALITIES = {
    "text_attachment",
    "image_file_observation",
    "audio_file_observation",
    "screen_snapshot_file_observation",
    "browser_capture_ref_observation",
}

ALLOWED_PHASE1_CAPTURE_METHODS = {
    "operator_attached_file",
    "saved_source_ref_capture",
    "browser_runtime_capture_ref",
}

BLOCKED_CAPTURE_METHODS = {
    "background_microphone",
    "background_camera",
    "background_screen",
    "unconsented_browser_capture",
}

_MODALITY_ALIASES = {
    "text": "text",
    "text_attachment": "text",
    "image": "image",
    "image_file_observation": "image",
    "audio": "audio",
    "audio_file_observation": "audio",
    "screen": "screen",
    "screen_snapshot": "screen",
    "screen_snapshot_file_observation": "screen",
    "browser_capture": "browser_capture",
    "browser_capture_ref": "browser_capture",
    "browser_capture_ref_observation": "browser_capture",
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _clean_text(value: Any, *, limit: int = 320, lower: bool = False) -> str:
    text = str(value or "").strip()[: max(1, int(limit))]
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


def _coerce_confidence(value: Any) -> float:
    try:
        number = float(value)
    except Exception:
        return 0.0
    return max(0.0, min(1.0, number))


def _tags(value: Any) -> list[str]:
    if isinstance(value, str):
        rows = [item.strip() for item in value.split(",")]
    else:
        rows = [str(item or "").strip() for item in _list_or_empty(value)]
    out: list[str] = []
    for item in rows:
        if item and item not in out:
            out.append(item)
        if len(out) >= 12:
            break
    return out


def _digest_payload(payload: dict[str, Any]) -> str:
    digest_base = {
        key: value
        for key, value in payload.items()
        if key not in {"payload_digest", "block_reasons"}
    }
    raw = json.dumps(digest_base, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _proposal_id(*parts: Any) -> str:
    seed = "|".join(_clean_text(part, limit=160) for part in parts if _clean_text(part, limit=160))
    if not seed:
        seed = "multimodal-inspection"
    digest = hashlib.sha1(seed.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"ap-{digest}"


def normalize_multimodal_source(raw: dict[str, Any] | None) -> dict[str, Any]:
    row = _dict_or_empty(raw)
    source_id = _clean_text(row.get("source_id") or row.get("id"), limit=120)
    capture_method = _clean_text(row.get("capture_method"), limit=80, lower=True)
    consent_scope = _clean_text(row.get("consent_scope"), limit=80, lower=True)
    modality = _MODALITY_ALIASES.get(_clean_text(row.get("modality"), limit=80, lower=True), "")
    source_role = _clean_text(row.get("source_role"), limit=80, lower=True)
    if not source_role:
        if capture_method == "browser_runtime_capture_ref":
            source_role = "runtime"
        elif capture_method == "saved_source_ref_capture":
            source_role = "saved_material"
        else:
            source_role = "operator"
    artifact_ref = _clean_text(row.get("artifact_ref") or row.get("path") or row.get("uri"), limit=320)
    artifact_label = _clean_text(row.get("label") or row.get("artifact_label") or artifact_ref.rsplit("/", 1)[-1], limit=160)
    artifact_carrier = "browser_page" if modality == "browser_capture" else "multimodal_source"
    block_reasons: list[str] = []
    if not source_id:
        block_reasons.append("missing_source_id")
    if modality not in {"text", "image", "audio", "screen", "browser_capture"}:
        block_reasons.append("unsupported_phase1_modality")
    if not consent_scope:
        block_reasons.append("missing_explicit_consent")
    elif consent_scope not in {"single_turn", "session", "saved_material_review"}:
        block_reasons.append("unsupported_consent_scope")
    if capture_method in BLOCKED_CAPTURE_METHODS:
        block_reasons.append("blocked_capture_method")
    elif capture_method not in ALLOWED_PHASE1_CAPTURE_METHODS:
        block_reasons.append("unsupported_capture_method")
    if not artifact_ref:
        block_reasons.append("missing_artifact_ref")
    status = "blocked" if block_reasons else "available"
    normalized = {
        "source_id": source_id,
        "modality": modality,
        "source_role": source_role,
        "consent_scope": consent_scope,
        "capture_method": capture_method,
        "artifact_ref": artifact_ref,
        "artifact_label": artifact_label,
        "artifact_carrier": artifact_carrier,
        "payload_digest": "",
        "trust_tier": "medium",
        "status": status,
        "block_reasons": block_reasons,
        "writeback_ready": False,
    }
    normalized["payload_digest"] = _digest_payload(normalized)
    return normalized


def normalize_multimodal_inspection_spec(value: Any) -> dict[str, Any]:
    row = _dict_or_empty(value)
    if not row:
        return {}
    source_ref_id = _clean_text(row.get("source_ref_id") or row.get("source_id"), limit=120)
    modality = _MODALITY_ALIASES.get(_clean_text(row.get("modality"), limit=80, lower=True), "")
    artifact_ref = _clean_text(row.get("artifact_ref") or row.get("path") or row.get("uri"), limit=320)
    artifact_label = _clean_text(row.get("artifact_label") or row.get("label") or artifact_ref.rsplit("/", 1)[-1], limit=160)
    consent_scope = _clean_text(row.get("consent_scope"), limit=80, lower=True)
    capture_method = _clean_text(row.get("capture_method"), limit=80, lower=True)
    normalized = {
        "source_ref_id": source_ref_id,
        "modality": modality,
        "artifact_ref": artifact_ref,
        "artifact_label": artifact_label,
        "consent_scope": consent_scope,
        "capture_method": capture_method,
        "inspection_mode": _clean_text(
            row.get("inspection_mode") or "model_assisted_artifact_inspection",
            limit=120,
            lower=True,
        ),
        "approved_result_required": _coerce_bool(row.get("approved_result_required"), True),
        "model_api_call_allowed": False,
        "live_capture_allowed": False,
    }
    if any(
        (
            normalized["source_ref_id"],
            normalized["modality"],
            normalized["artifact_ref"],
            normalized["artifact_label"],
            normalized["consent_scope"],
            normalized["capture_method"],
        )
    ):
        return normalized
    return {}


def normalize_multimodal_inspection_preview(value: Any) -> dict[str, Any]:
    row = _dict_or_empty(value)
    if not row:
        return {}
    source_ref_id = _clean_text(row.get("source_ref_id") or row.get("source_id"), limit=120)
    block_reasons = [
        _clean_text(item, limit=120)
        for item in _list_or_empty(row.get("block_reasons"))
        if _clean_text(item, limit=120)
    ][:8]
    blocked = _coerce_bool(row.get("blocked"), bool(block_reasons))
    normalized = {
        "source_ref_id": source_ref_id,
        "modality": _MODALITY_ALIASES.get(_clean_text(row.get("modality"), limit=80, lower=True), ""),
        "artifact_ref": _clean_text(row.get("artifact_ref"), limit=320),
        "artifact_label": _clean_text(row.get("artifact_label") or row.get("label"), limit=160),
        "requires_approval": _coerce_bool(row.get("requires_approval"), not blocked),
        "auto_execute": False,
        "model_api_call_planned": False,
        "live_capture_allowed": False,
        "blocked": blocked,
        "block_reasons": block_reasons,
        "summary": _clean_text(row.get("summary"), limit=360),
    }
    if any(
        (
            normalized["source_ref_id"],
            normalized["modality"],
            normalized["artifact_ref"],
            normalized["artifact_label"],
            normalized["blocked"],
            normalized["summary"],
        )
    ):
        return normalized
    return {}


def normalize_multimodal_inspection_result(value: Any) -> dict[str, Any]:
    row = _dict_or_empty(value)
    if not row:
        return {}
    status = _clean_text(row.get("status"), limit=40, lower=True)
    approval_status = _clean_text(row.get("approval_status"), limit=40, lower=True)
    if not approval_status and status == "completed":
        approval_status = "approved"
    source_ref_id = _clean_text(row.get("source_ref_id") or row.get("source_id"), limit=120)
    modality = _MODALITY_ALIASES.get(_clean_text(row.get("modality"), limit=80, lower=True), "")
    semantic_summary = _clean_text(row.get("semantic_summary") or row.get("operator_summary"), limit=640)
    caption = _clean_text(row.get("caption"), limit=640)
    observed_text = _clean_text(row.get("observed_text"), limit=640)
    ocr_text = _clean_text(row.get("ocr_text"), limit=640)
    transcript = _clean_text(row.get("transcript"), limit=640)
    normalized = {
        "status": status,
        "approval_status": approval_status,
        "source_ref_id": source_ref_id,
        "modality": modality,
        "artifact_ref": _clean_text(row.get("artifact_ref") or row.get("path") or row.get("uri"), limit=320),
        "artifact_label": _clean_text(row.get("artifact_label") or row.get("label"), limit=160),
        "semantic_summary": semantic_summary,
        "caption": caption,
        "observed_text": observed_text,
        "ocr_text": ocr_text,
        "transcript": transcript,
        "tags": _tags(row.get("tags") or row.get("semantic_tags")),
        "confidence": _coerce_confidence(row.get("confidence")),
        "source": _clean_text(row.get("source") or "approved_inspection_result", limit=80, lower=True),
        "model_api_called": False,
        "writeback_ready": False,
    }
    if any(
        (
            normalized["status"],
            normalized["approval_status"],
            normalized["source_ref_id"],
            normalized["modality"],
            normalized["artifact_ref"],
            normalized["artifact_label"],
            normalized["semantic_summary"],
            normalized["caption"],
            normalized["observed_text"],
            normalized["ocr_text"],
            normalized["transcript"],
            normalized["tags"],
        )
    ):
        return normalized
    return {}


def build_multimodal_inspection_packet(
    source: dict[str, Any] | None,
    *,
    origin: str = "counterpart_request",
    status: str = "awaiting_approval",
    approved_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    artifact = normalize_multimodal_source(source)
    packet_status = _clean_text(status, limit=40, lower=True) or "awaiting_approval"
    if artifact.get("status") == "blocked":
        packet_status = "blocked"
    elif packet_status not in {"awaiting_approval", "approved", "rejected", "completed", "blocked"}:
        packet_status = "awaiting_approval"
    packet_origin = _clean_text(origin, limit=80, lower=True)
    if packet_origin not in {"motive_goal", "own_rhythm", "counterpart_request", "capability_upgrade"}:
        packet_origin = "counterpart_request"

    spec = normalize_multimodal_inspection_spec(
        {
            "source_ref_id": artifact.get("source_id"),
            "modality": artifact.get("modality"),
            "artifact_ref": artifact.get("artifact_ref"),
            "artifact_label": artifact.get("artifact_label"),
            "consent_scope": artifact.get("consent_scope"),
            "capture_method": artifact.get("capture_method"),
        }
    )
    blocked_reasons = list(artifact.get("block_reasons") or [])
    blocked = packet_status == "blocked"
    target = artifact.get("artifact_ref") or artifact.get("source_id") or artifact.get("artifact_label")
    summary = (
        f"Blocked multimodal inspection for {artifact.get('artifact_label') or artifact.get('source_id')}."
        if blocked
        else f"Await approval before inspecting {artifact.get('artifact_label') or artifact.get('source_id')}."
    )
    preview = normalize_multimodal_inspection_preview(
        {
            "source_ref_id": artifact.get("source_id"),
            "modality": artifact.get("modality"),
            "artifact_ref": artifact.get("artifact_ref"),
            "artifact_label": artifact.get("artifact_label"),
            "requires_approval": packet_status == "awaiting_approval",
            "blocked": blocked,
            "block_reasons": blocked_reasons,
            "summary": summary,
        }
    )

    result: dict[str, Any] = {}
    if packet_status == "completed":
        result = normalize_multimodal_inspection_result(
            {
                "status": "completed",
                "approval_status": "approved",
                "source_ref_id": artifact.get("source_id"),
                "modality": artifact.get("modality"),
                "artifact_ref": artifact.get("artifact_ref"),
                "artifact_label": artifact.get("artifact_label"),
                **_dict_or_empty(approved_result),
            }
        )
    elif approved_result:
        result = normalize_multimodal_inspection_result(
            {
                "status": packet_status,
                "approval_status": "rejected" if packet_status == "rejected" else "",
                "source_ref_id": artifact.get("source_id"),
                "modality": artifact.get("modality"),
                "artifact_ref": artifact.get("artifact_ref"),
                "artifact_label": artifact.get("artifact_label"),
                **_dict_or_empty(approved_result),
            }
        )

    requires_approval = packet_status == "awaiting_approval"
    writeback_ready = (
        packet_status == "completed"
        and result.get("status") == "completed"
        and result.get("approval_status") == "approved"
    )
    return {
        "proposal_id": _proposal_id(
            "artifact",
            "inspect_multimodal",
            artifact.get("source_id"),
            artifact.get("artifact_ref"),
            packet_origin,
        ),
        "origin": packet_origin,
        "intent": "artifact:inspect_multimodal",
        "status": packet_status,
        "risk": "external_mutation",
        "requires_approval": requires_approval,
        "capability_steps": [
            {
                "kind": "artifact",
                "name": "inspect_multimodal_artifact",
                "target": target,
                "status": "blocked" if blocked else "pending" if packet_status == "awaiting_approval" else packet_status,
                "requires_approval": requires_approval,
                "note": summary,
            }
        ],
        "expected_effect": summary,
        "result_summary": _clean_text(result.get("semantic_summary") or result.get("caption") or ""),
        "writeback_ready": writeback_ready,
        "tool_name": "inspect_multimodal_artifact",
        "tool_args": {
            "source_ref_id": artifact.get("source_id"),
            "artifact_ref": artifact.get("artifact_ref"),
            "artifact_label": artifact.get("artifact_label"),
        },
        "block_reason": _clean_text(blocked_reasons[0] if blocked_reasons else ""),
        "multimodal_inspection_spec": spec,
        "multimodal_inspection_preview": preview,
        "multimodal_inspection_result": result,
    }


def build_multimodal_perception_event(source: dict[str, Any] | None) -> dict[str, Any]:
    artifact = normalize_multimodal_source(source)
    hints = {
        "artifact_continuity": "attached" if artifact["status"] == "available" else "blocked",
        "active_artifact_kind": artifact["modality"],
        "active_artifact_ref": artifact["artifact_ref"],
        "active_artifact_label": artifact["artifact_label"],
        "artifact_carrier": artifact["artifact_carrier"],
        "multimodal_source": artifact,
    }
    return {
        "kind": "multimodal_observation",
        "source": "multimodal_source",
        "text": artifact["artifact_label"] or artifact["source_id"],
        "effective_text": artifact["artifact_label"] or artifact["source_id"],
        "digital_body_hints": hints,
        "perception": {
            "channel": artifact["modality"],
            "modality": artifact["modality"],
            "source_role": artifact["source_role"],
            "trust_tier": artifact["trust_tier"],
            "delivery_mode": "external",
            "interruptibility": "passive",
            "digital_body_hints": hints,
        },
    }


__all__ = [
    "ALLOWED_PHASE1_CAPTURE_METHODS",
    "BLOCKED_CAPTURE_METHODS",
    "MULTIMODAL_PERCEPTION_PHASE2_IN_PROGRESS",
    "MULTIMODAL_PERCEPTION_PHASE2_READY",
    "PHASE1_MODALITIES",
    "build_multimodal_inspection_packet",
    "build_multimodal_perception_event",
    "normalize_multimodal_inspection_preview",
    "normalize_multimodal_inspection_result",
    "normalize_multimodal_inspection_spec",
    "normalize_multimodal_source",
]
