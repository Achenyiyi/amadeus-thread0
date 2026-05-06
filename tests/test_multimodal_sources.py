from __future__ import annotations

from amadeus_thread0.runtime.multimodal_sources import (
    build_multimodal_perception_event,
    normalize_multimodal_source,
)


def test_source_artifact_requires_consent_and_digest():
    artifact = normalize_multimodal_source(
        {
            "source_id": "img-1",
            "modality": "image",
            "path": "fixtures/panel.png",
            "consent_scope": "single_turn",
            "capture_method": "operator_attached_file",
        }
    )
    assert artifact["source_id"] == "img-1"
    assert artifact["modality"] == "image"
    assert artifact["consent_scope"] == "single_turn"
    assert artifact["writeback_ready"] is False
    assert artifact["payload_digest"]


def test_source_artifact_blocks_secret_capture():
    artifact = normalize_multimodal_source(
        {
            "source_id": "mic-live",
            "modality": "audio",
            "capture_method": "background_microphone",
            "consent_scope": "",
        }
    )
    assert artifact["status"] == "blocked"
    assert "missing_explicit_consent" in artifact["block_reasons"]
    assert "blocked_capture_method" in artifact["block_reasons"]


def test_multimodal_perception_event_carries_body_hints():
    source = normalize_multimodal_source(
        {
            "source_id": "screen-1",
            "modality": "screen",
            "path": "fixtures/screen.png",
            "consent_scope": "single_turn",
            "capture_method": "operator_attached_file",
            "label": "screen.png",
        }
    )

    event = build_multimodal_perception_event(source)

    assert event["kind"] == "multimodal_observation"
    assert event["perception"]["modality"] == "screen"
    assert event["perception"]["source_role"] == "operator"
    assert event["perception"]["digital_body_hints"]["active_artifact_kind"] == "screen"
    assert event["perception"]["digital_body_hints"]["artifact_carrier"] == "multimodal_source"
    assert event["digital_body_hints"]["multimodal_source"]["source_id"] == "screen-1"


def test_browser_capture_ref_preserves_browser_boundary():
    source = normalize_multimodal_source(
        {
            "source_id": "browser-cap-1",
            "modality": "browser_capture",
            "artifact_ref": "browser-capture:page-1",
            "consent_scope": "saved_material_review",
            "capture_method": "browser_runtime_capture_ref",
            "source_role": "runtime",
        }
    )

    assert source["status"] == "available"
    assert source["source_role"] == "runtime"
    assert source["artifact_carrier"] == "browser_page"
    assert source["writeback_ready"] is False
