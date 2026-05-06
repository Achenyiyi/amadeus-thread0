from __future__ import annotations

from amadeus_thread0.runtime.artifact_appraisal_bridge import (
    build_artifact_appraisal_readback,
)


def _semantics(observations: list[dict]) -> dict:
    return {
        "schema": "artifact_perception_semantics.v1",
        "status": "ready" if observations else "empty",
        "readiness_status": (
            "artifact_perception_semantics_ready"
            if observations
            else "artifact_perception_semantics_empty"
        ),
        "semantic_observations": observations,
        "observation_count": len(observations),
        "model_api_called": False,
        "writeback_ready_count": 0,
    }


def test_login_semantic_observation_becomes_access_friction_evidence():
    readback = build_artifact_appraisal_readback(
        _semantics(
            [
                {
                    "source_ref_id": "img-runtime-sem-1",
                    "source_kind": "image_file",
                    "modality": "image",
                    "semantic_label": "login_prompt",
                    "summary": "A login dialog with an expired session warning.",
                    "source": "approved_metadata",
                    "model_api_called": False,
                    "writeback_ready": False,
                }
            ]
        )
    )

    evidence = readback["evidence_items"][0]
    assert readback["schema"] == "artifact_appraisal_bridge.v1"
    assert readback["status"] == "ready"
    assert readback["readiness_status"] == "artifact_appraisal_bridge_ready"
    assert evidence["evidence_id"] == "artifact-evidence-img-runtime-sem-1"
    assert evidence["source_ref_id"] == "img-runtime-sem-1"
    assert evidence["semantic_label"] == "login_prompt"
    assert evidence["summary"] == "A login dialog with an expired session warning."
    assert evidence["appraisal_axes"] == ["task_relevance", "access_friction"]
    assert evidence["suggested_appraisal_delta"]["scene"] == "artifact_review"
    assert evidence["suggested_appraisal_delta"]["task_relevance"] == "high"
    assert evidence["suggested_appraisal_delta"]["access_friction"] is True
    assert evidence["authority"]["source"] == "approved_metadata"
    assert evidence["authority"]["model_api_called"] is False
    assert evidence["authority"]["memory_write_allowed"] is False
    assert evidence["authority"]["writeback_ready"] is False
    assert readback["influence_summary"]["artifact_relevance"] == "high"
    assert readback["influence_summary"]["access_friction_observed"] is True
    assert readback["influence_summary"]["should_request_live_capture"] is False
    assert readback["influence_summary"]["should_write_memory"] is False


def test_transcript_and_ocr_semantics_create_readonly_evidence_without_live_capture():
    readback = build_artifact_appraisal_readback(
        _semantics(
            [
                {
                    "source_ref_id": "audio-sem-1",
                    "source_kind": "audio_file",
                    "modality": "audio",
                    "observation_kind": "provided_transcript",
                    "summary": "刚才那段音频里提到需要继续看登录错误。",
                    "observed_text": "刚才那段音频里提到需要继续看登录错误。",
                    "source": "approved_metadata",
                    "model_api_called": False,
                    "writeback_ready": False,
                },
                {
                    "source_ref_id": "screen-sem-1",
                    "source_kind": "screen_snapshot_file",
                    "modality": "screen",
                    "observation_kind": "provided_ocr_text",
                    "summary": "Session expired. Sign in again.",
                    "observed_text": "Session expired. Sign in again.",
                    "source": "approved_metadata",
                    "model_api_called": False,
                    "writeback_ready": False,
                },
            ]
        )
    )

    assert readback["evidence_count"] == 2
    assert readback["influence_summary"]["should_request_live_capture"] is False
    assert all(item["authority"]["writeback_ready"] is False for item in readback["evidence_items"])


def test_empty_or_blocked_semantics_return_inert_readback():
    empty = build_artifact_appraisal_readback(
        {
            "schema": "artifact_perception_semantics.v1",
            "status": "empty",
            "readiness_status": "artifact_perception_semantics_empty",
            "semantic_observations": [],
        }
    )
    blocked = build_artifact_appraisal_readback(
        {
            "schema": "artifact_perception_semantics.v1",
            "status": "blocked",
            "readiness_status": "artifact_perception_semantics_blocked",
            "semantic_observations": [],
        }
    )

    assert empty["status"] == "empty"
    assert empty["evidence_items"] == []
    assert empty["influence_summary"]["artifact_relevance"] == "none"
    assert blocked["status"] == "blocked"
    assert blocked["evidence_items"] == []
    assert blocked["influence_summary"]["should_write_memory"] is False
