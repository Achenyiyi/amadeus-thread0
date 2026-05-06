from __future__ import annotations

from amadeus_thread0.runtime.artifact_motive_bridge import build_artifact_motive_readback


def _access_friction_appraisal() -> dict:
    return {
        "status": "ready",
        "evidence_items": [
            {
                "evidence_id": "artifact-evidence-img-runtime-appraisal-1",
                "source_ref_id": "img-runtime-appraisal-1",
                "source_kind": "image_file",
                "semantic_label": "login_prompt",
                "summary": "A login dialog with an expired session warning.",
                "appraisal_axes": ["task_relevance", "access_friction"],
                "suggested_appraisal_delta": {
                    "scene": "artifact_review",
                    "task_relevance": "high",
                    "access_friction": True,
                    "boundary_condition": "access_or_session_friction",
                },
                "authority": {
                    "source": "approved_metadata",
                    "model_api_called": False,
                    "memory_write_allowed": False,
                    "writeback_ready": False,
                },
            }
        ],
    }


def test_access_friction_appraisal_evidence_creates_restore_access_hint():
    readback = build_artifact_motive_readback(_access_friction_appraisal())

    hint = readback["motive_hints"][0]
    assert readback["schema"] == "artifact_motive_bridge.v1"
    assert readback["status"] == "ready"
    assert readback["readiness_status"] == "artifact_motive_bridge_ready"
    assert readback["hint_count"] == 1
    assert hint["hint_id"] == "artifact-motive-img-runtime-appraisal-1"
    assert hint["source_evidence_id"] == "artifact-evidence-img-runtime-appraisal-1"
    assert hint["source_ref_id"] == "img-runtime-appraisal-1"
    assert hint["primary_motive_hint"] == "restore_access_continuity"
    assert hint["motive_tension_hint"] == "task_continuity_vs_access_friction"
    assert (
        hint["goal_frame_hint"]
        == "Treat the artifact as an access/session condition to resolve before continuing the task."
    )
    assert hint["derived_from_axes"] == ["task_relevance", "access_friction"]
    assert hint["authority"]["source"] == "artifact_appraisal_evidence"
    assert hint["authority"]["model_api_called"] is False
    assert hint["authority"]["memory_write_allowed"] is False
    assert hint["authority"]["writeback_ready"] is False
    assert hint["authority"]["behavior_mutation_allowed"] is False
    assert readback["motive_summary"]["primary_motive_hint"] == "restore_access_continuity"
    assert readback["motive_summary"]["motive_tension_hint"] == "task_continuity_vs_access_friction"
    assert readback["motive_summary"]["goal_bias"] == "resolve_access_before_task_continuation"
    assert readback["motive_summary"]["should_mutate_behavior"] is False
    assert readback["motive_summary"]["should_write_memory"] is False
    assert readback["authority_boundary"]["behavior_mutation_allowed"] is False
    assert readback["authority_boundary"]["memory_write_allowed"] is False
    assert readback["model_api_called"] is False
    assert readback["writeback_ready_count"] == 0


def test_task_relevance_without_access_friction_creates_artifact_review_hint():
    appraisal = {
        "status": "ready",
        "evidence_items": [
            {
                "evidence_id": "artifact-evidence-img-task-1",
                "source_ref_id": "img-task-1",
                "source_kind": "image_file",
                "semantic_label": "dashboard_panel",
                "summary": "A dashboard panel with the current task checklist.",
                "appraisal_axes": ["task_relevance"],
                "suggested_appraisal_delta": {
                    "scene": "artifact_review",
                    "task_relevance": "high",
                    "access_friction": False,
                },
                "authority": {
                    "source": "approved_metadata",
                    "model_api_called": False,
                    "memory_write_allowed": False,
                    "writeback_ready": False,
                },
            }
        ],
    }

    readback = build_artifact_motive_readback(appraisal)

    hint = readback["motive_hints"][0]
    assert hint["primary_motive_hint"] == "continue_artifact_review"
    assert hint["motive_tension_hint"] == "task_relevance_vs_uncertainty"
    assert hint["goal_frame_hint"] == "Use the approved artifact evidence as task context while keeping behavior unchanged."
    assert readback["motive_summary"]["goal_bias"] == "continue_task_with_artifact_context"
    assert readback["motive_summary"]["should_mutate_behavior"] is False


def test_empty_and_blocked_appraisal_return_inert_readbacks():
    empty = build_artifact_motive_readback({"status": "empty", "evidence_items": []})
    blocked = build_artifact_motive_readback({"status": "blocked", "evidence_items": []})

    assert empty["status"] == "empty"
    assert empty["readiness_status"] == "artifact_motive_bridge_empty"
    assert empty["motive_hints"] == []
    assert empty["motive_summary"]["primary_motive_hint"] == ""
    assert empty["motive_summary"]["should_write_memory"] is False
    assert blocked["status"] == "blocked"
    assert blocked["readiness_status"] == "artifact_motive_bridge_blocked"
    assert blocked["motive_hints"] == []
    assert blocked["authority_boundary"]["external_mutation_allowed"] is False


def test_inadmissible_evidence_is_blocked_and_never_becomes_motive_hint():
    appraisal = _access_friction_appraisal()
    appraisal["evidence_items"][0]["authority"]["writeback_ready"] = True
    appraisal["evidence_items"].append(
        {
            "evidence_id": "artifact-evidence-model-called",
            "source_ref_id": "img-model-called",
            "summary": "Model-generated image reading.",
            "appraisal_axes": ["task_relevance"],
            "suggested_appraisal_delta": {"task_relevance": "high"},
            "authority": {
                "source": "approved_metadata",
                "model_api_called": True,
                "memory_write_allowed": False,
                "writeback_ready": False,
            },
        }
    )

    readback = build_artifact_motive_readback(appraisal)

    assert readback["status"] == "empty"
    assert readback["motive_hints"] == []
    assert readback["blocked_evidence_count"] == 2
    assert "writeback_ready" in readback["blocked_reasons"]
    assert "model_api_called" in readback["blocked_reasons"]
    assert readback["model_api_called"] is False
    assert readback["writeback_ready_count"] == 0
