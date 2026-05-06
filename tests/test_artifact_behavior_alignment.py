from __future__ import annotations

from amadeus_thread0.runtime.artifact_behavior_alignment import (
    build_artifact_behavior_alignment_readback,
)


def _artifact_motive(primary: str = "restore_access_continuity") -> dict:
    return {
        "status": "ready",
        "readiness_status": "artifact_motive_bridge_ready",
        "motive_hints": [
            {
                "hint_id": "artifact-motive-img-runtime-motive-1",
                "source_ref_id": "img-runtime-motive-1",
                "source_kind": "image_file",
                "primary_motive_hint": primary,
                "goal_frame_hint": "Treat the artifact as task context.",
                "authority": {
                    "source": "artifact_appraisal_evidence",
                    "model_api_called": False,
                    "memory_write_allowed": False,
                    "writeback_ready": False,
                    "behavior_mutation_allowed": False,
                },
            }
        ],
    }


def test_restore_access_hint_not_reflected_is_reported_without_mutation():
    readback = build_artifact_behavior_alignment_readback(
        _artifact_motive("restore_access_continuity"),
        {"primary_motive": "continue_workspace_task"},
        {"primary_motive": "continue_workspace_task"},
    )

    item = readback["alignment_items"][0]
    assert readback["schema"] == "artifact_behavior_alignment.v1"
    assert readback["status"] == "ready"
    assert readback["readiness_status"] == "artifact_behavior_alignment_ready"
    assert readback["alignment_count"] == 1
    assert item["alignment_id"] == "artifact-behavior-img-runtime-motive-1"
    assert item["source_hint_id"] == "artifact-motive-img-runtime-motive-1"
    assert item["source_ref_id"] == "img-runtime-motive-1"
    assert item["primary_motive_hint"] == "restore_access_continuity"
    assert item["behavior_primary_motive"] == "continue_workspace_task"
    assert item["plan_primary_motive"] == "continue_workspace_task"
    assert item["alignment_status"] == "advisory_not_reflected"
    assert item["alignment_reason"] == "artifact_motive_hint_not_reflected_in_behavior_plan"
    assert item["behavior_mutation_applied"] is False
    assert item["authority"]["source"] == "artifact_motive_hint"
    assert item["authority"]["model_api_called"] is False
    assert item["authority"]["memory_write_allowed"] is False
    assert item["authority"]["writeback_ready"] is False
    assert item["authority"]["behavior_mutation_allowed"] is False
    assert item["authority"]["behavior_mutation_applied"] is False
    assert readback["alignment_summary"]["alignment_status"] == "advisory_not_reflected"
    assert readback["alignment_summary"]["advisory_not_reflected_count"] == 1
    assert readback["alignment_summary"]["aligned_count"] == 0
    assert readback["alignment_summary"]["conflict_count"] == 0
    assert readback["alignment_summary"]["should_mutate_behavior"] is False
    assert readback["alignment_summary"]["should_write_memory"] is False
    assert readback["authority_boundary"]["behavior_mutation_allowed"] is False
    assert readback["authority_boundary"]["memory_write_allowed"] is False
    assert readback["model_api_called"] is False
    assert readback["writeback_ready_count"] == 0


def test_matching_access_behavior_reports_causal_alignment():
    readback = build_artifact_behavior_alignment_readback(
        _artifact_motive("restore_access_continuity"),
        {"primary_motive": "restore_access_continuity"},
        {"primary_motive": "restore_access_continuity"},
    )

    item = readback["alignment_items"][0]
    assert item["alignment_status"] == "causally_aligned"
    assert item["alignment_reason"] == "artifact_motive_hint_reflected_in_behavior_plan"
    assert readback["alignment_summary"]["alignment_status"] == "causally_aligned"
    assert readback["alignment_summary"]["aligned_count"] == 1
    assert readback["alignment_summary"]["should_mutate_behavior"] is False


def test_continue_artifact_review_aligns_with_workspace_task():
    readback = build_artifact_behavior_alignment_readback(
        _artifact_motive("continue_artifact_review"),
        {"primary_motive": "continue_workspace_task"},
        {"primary_motive": "continue_workspace_task"},
    )

    item = readback["alignment_items"][0]
    assert item["primary_motive_hint"] == "continue_artifact_review"
    assert item["alignment_status"] == "causally_aligned"
    assert item["alignment_reason"] == "artifact_motive_hint_reflected_in_behavior_plan"
    assert readback["alignment_summary"]["aligned_count"] == 1


def test_empty_and_blocked_motive_return_inert_readbacks():
    empty = build_artifact_behavior_alignment_readback(
        {"status": "empty", "motive_hints": []},
        {"primary_motive": "continue_workspace_task"},
        {"primary_motive": "continue_workspace_task"},
    )
    blocked = build_artifact_behavior_alignment_readback(
        {"status": "blocked", "motive_hints": []},
        {"primary_motive": "continue_workspace_task"},
        {"primary_motive": "continue_workspace_task"},
    )

    assert empty["status"] == "empty"
    assert empty["readiness_status"] == "artifact_behavior_alignment_empty"
    assert empty["alignment_items"] == []
    assert empty["alignment_summary"]["alignment_status"] == "empty"
    assert empty["alignment_summary"]["should_write_memory"] is False
    assert blocked["status"] == "blocked"
    assert blocked["readiness_status"] == "artifact_behavior_alignment_blocked"
    assert blocked["alignment_items"] == []
    assert blocked["authority_boundary"]["external_mutation_allowed"] is False


def test_inadmissible_hint_with_behavior_mutation_or_writeback_is_blocked():
    motive = _artifact_motive("restore_access_continuity")
    motive["motive_hints"][0]["authority"]["writeback_ready"] = True
    motive["motive_hints"].append(
        {
            "hint_id": "artifact-motive-mutating",
            "source_ref_id": "img-mutating",
            "primary_motive_hint": "restore_access_continuity",
            "authority": {
                "source": "artifact_appraisal_evidence",
                "model_api_called": False,
                "memory_write_allowed": False,
                "writeback_ready": False,
                "behavior_mutation_allowed": True,
            },
        }
    )

    readback = build_artifact_behavior_alignment_readback(
        motive,
        {"primary_motive": "restore_access_continuity"},
        {"primary_motive": "restore_access_continuity"},
    )

    assert readback["status"] == "blocked"
    assert readback["readiness_status"] == "artifact_behavior_alignment_blocked"
    assert readback["alignment_items"] == []
    assert readback["blocked_hint_count"] == 2
    assert "writeback_ready" in readback["blocked_reasons"]
    assert "behavior_mutation_allowed" in readback["blocked_reasons"]
    assert readback["model_api_called"] is False
    assert readback["writeback_ready_count"] == 0

