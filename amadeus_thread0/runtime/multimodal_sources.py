from __future__ import annotations

import hashlib
import json
from typing import Any


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


def _clean_text(value: Any, *, limit: int = 320, lower: bool = False) -> str:
    text = str(value or "").strip()[: max(1, int(limit))]
    return text.lower() if lower else text


def _digest_payload(payload: dict[str, Any]) -> str:
    digest_base = {
        key: value
        for key, value in payload.items()
        if key not in {"payload_digest", "block_reasons"}
    }
    raw = json.dumps(digest_base, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


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
    "PHASE1_MODALITIES",
    "build_multimodal_perception_event",
    "normalize_multimodal_source",
]
