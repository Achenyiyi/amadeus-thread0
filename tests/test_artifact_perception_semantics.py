from __future__ import annotations

from amadeus_thread0.runtime.artifact_perception_semantics import (
    build_artifact_semantics_readback,
)


def test_image_summary_metadata_becomes_semantic_observation():
    readback = build_artifact_semantics_readback(
        [
            {
                "source_id": "img-sem-1",
                "modality": "image",
                "path": "fixtures/login.png",
                "consent_scope": "single_turn",
                "capture_method": "operator_attached_file",
                "label": "login.png",
                "semantic_label": "login_prompt",
                "semantic_summary": "A login dialog with an expired session warning.",
                "semantic_tags": ["login", "expired-session"],
                "confidence": 0.72,
            }
        ]
    )

    observation = readback["semantic_observations"][0]
    assert readback["status"] == "ready"
    assert readback["readiness_status"] == "artifact_perception_semantics_ready"
    assert observation["source_ref_id"] == "img-sem-1"
    assert observation["source_kind"] == "image_file"
    assert observation["observation_kind"] == "operator_provided_artifact_semantics"
    assert observation["semantic_label"] == "login_prompt"
    assert observation["summary"] == "A login dialog with an expired session warning."
    assert observation["tags"] == ["login", "expired-session"]
    assert observation["confidence"] == 0.72
    assert observation["source"] == "approved_metadata"
    assert observation["model_api_called"] is False
    assert observation["writeback_ready"] is False


def test_audio_transcript_becomes_transcript_observation():
    readback = build_artifact_semantics_readback(
        [
            {
                "source_id": "audio-sem-1",
                "modality": "audio",
                "path": "fixtures/voice.wav",
                "consent_scope": "single_turn",
                "capture_method": "operator_attached_file",
                "transcript": "刚才那段音频里提到需要继续看登录错误。",
            }
        ]
    )

    observation = readback["semantic_observations"][0]
    assert observation["source_kind"] == "audio_file"
    assert observation["observation_kind"] == "provided_transcript"
    assert observation["summary"] == "刚才那段音频里提到需要继续看登录错误。"
    assert observation["observed_text"] == "刚才那段音频里提到需要继续看登录错误。"


def test_screen_ocr_and_browser_summary_use_metadata_only():
    readback = build_artifact_semantics_readback(
        [
            {
                "source_id": "screen-sem-1",
                "modality": "screen",
                "path": "fixtures/screen.png",
                "consent_scope": "single_turn",
                "capture_method": "operator_attached_file",
                "ocr_text": "Session expired. Sign in again.",
            },
            {
                "source_id": "browser-sem-1",
                "modality": "browser_capture",
                "artifact_ref": "browser-capture:tab-7",
                "consent_scope": "saved_material_review",
                "capture_method": "browser_runtime_capture_ref",
                "operator_summary": "A saved browser capture of the account settings page.",
            },
        ]
    )

    screen_observation, browser_observation = readback["semantic_observations"]
    assert screen_observation["source_kind"] == "screen_snapshot_file"
    assert screen_observation["observation_kind"] == "provided_ocr_text"
    assert screen_observation["observed_text"] == "Session expired. Sign in again."
    assert browser_observation["source_kind"] == "browser_capture_ref"
    assert browser_observation["observation_kind"] == "operator_provided_artifact_semantics"
    assert browser_observation["summary"] == "A saved browser capture of the account settings page."
    assert readback["model_api_called"] is False


def test_blocked_live_capture_does_not_emit_semantic_observation():
    readback = build_artifact_semantics_readback(
        [
            {
                "source_id": "mic-live-sem",
                "modality": "audio",
                "artifact_ref": "live:microphone",
                "consent_scope": "single_turn",
                "capture_method": "background_microphone",
                "transcript": "This must not be admitted.",
            }
        ]
    )

    assert readback["status"] == "blocked"
    assert readback["semantic_observations"] == []
    assert readback["blocked_source_count"] == 1
    assert readback["authority_boundary"]["multimodal_model_api_called"] is False
    assert readback["authority_boundary"]["memory_write_allowed"] is False


def test_completed_approved_multimodal_inspection_result_becomes_semantic_observation():
    readback = build_artifact_semantics_readback(
        [
            {
                "source_id": "img-approved-artifact-1",
                "modality": "image",
                "path": "fixtures/panel.png",
                "consent_scope": "single_turn",
                "capture_method": "operator_attached_file",
                "multimodal_inspection_result": {
                    "status": "completed",
                    "approval_status": "approved",
                    "source_ref_id": "img-approved-artifact-1",
                    "semantic_summary": "The panel shows a failed login message.",
                    "tags": ["login", "failure"],
                    "confidence": 0.83,
                },
            }
        ]
    )

    observation = readback["semantic_observations"][0]
    assert readback["status"] == "ready"
    assert observation["source"] == "approved_inspection_result"
    assert observation["source_ref_id"] == "img-approved-artifact-1"
    assert observation["summary"] == "The panel shows a failed login message."
    assert observation["tags"] == ["login", "failure"]
    assert observation["confidence"] == 0.83
    assert observation["model_api_called"] is False
    assert observation["writeback_ready"] is False


def test_pending_or_rejected_multimodal_inspection_results_do_not_emit_semantic_observation():
    readback = build_artifact_semantics_readback(
        [
            {
                "source_id": "img-pending-artifact-1",
                "modality": "image",
                "path": "fixtures/pending.png",
                "consent_scope": "single_turn",
                "capture_method": "operator_attached_file",
                "multimodal_inspection_result": {
                    "status": "awaiting_approval",
                    "approval_status": "pending",
                    "semantic_summary": "Should not be admitted.",
                },
            },
            {
                "source_id": "img-rejected-artifact-1",
                "modality": "image",
                "path": "fixtures/rejected.png",
                "consent_scope": "single_turn",
                "capture_method": "operator_attached_file",
                "multimodal_inspection_result": {
                    "status": "rejected",
                    "approval_status": "rejected",
                    "semantic_summary": "Should not be admitted.",
                },
            },
        ]
    )

    assert readback["status"] == "empty"
    assert readback["semantic_observations"] == []
