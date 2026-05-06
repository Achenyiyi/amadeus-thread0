from __future__ import annotations

from amadeus_thread0.runtime.post_baseline_closure import (
    POST_BASELINE_ITEMS,
    describe_post_baseline_item,
    evaluate_post_baseline_status,
    post_unlock_overrides_from_roadmap,
)


def test_post_baseline_items_cover_requested_tail_set():
    assert set(POST_BASELINE_ITEMS) == {
        "callable_transport_adapter",
        "tts_presence_timing",
        "multimodal_input_capture",
        "executor_adapter",
        "external_executor_harnesses",
        "dynamic_skill_generation",
        "chinese_de_scaffolding",
        "bounded_capability_growth",
        "natural_long_horizon_calibration",
        "frontend_runtime_shell",
    }


def test_formerly_deferred_surfaces_are_unlocked_planned_not_runtime_available():
    multimodal = describe_post_baseline_item("multimodal_input_capture")
    skill_generation = describe_post_baseline_item("dynamic_skill_generation")
    chinese = describe_post_baseline_item("chinese_de_scaffolding")
    frontend = describe_post_baseline_item("frontend_runtime_shell")
    external_executors = describe_post_baseline_item("external_executor_harnesses")

    assert multimodal["status"] == "unlocked_planned"
    assert multimodal["runtime_available"] is False
    assert "capture_without_consent" in multimodal["blocked_surfaces"]
    assert skill_generation["status"] == "unlocked_planned"
    assert skill_generation["runtime_available"] is False
    assert "persona_core_skill_patch" in skill_generation["blocked_surfaces"]
    assert chinese["status"] == "unlocked_planned"
    assert frontend["status"] == "unlocked_planned"
    assert external_executors["status"] == "unlocked_planned"
    assert "arbitrary_host_shell" in external_executors["blocked_surfaces"]


def test_evaluate_post_baseline_status_reports_ready_for_closed_mix():
    result = evaluate_post_baseline_status(
        {
            "callable_transport_adapter": {"status": "implemented_ready"},
            "tts_presence_timing": {"status": "preserved_ready"},
            "executor_adapter": {"status": "implemented_ready"},
        }
    )

    assert result["overall_status"] == "passed"
    assert result["readiness_status"] == "post_baseline_closure_ready"
    assert result["summary"]["unlocked_planned"] >= 5


def test_post_unlock_roadmap_ready_lanes_upgrade_closure_items_without_widening_disabled_runtime():
    roadmap = {
        "lanes": {
            "multimodal_capture_phase1": {
                "status": "ready",
                "overall_status": "passed",
                "readiness_status": "multimodal_capture_phase1_ready",
            },
            "dynamic_skills_phase1": {
                "status": "ready",
                "overall_status": "passed",
                "readiness_status": "dynamic_skills_phase1_ready",
            },
            "external_executor_harness_phase1": {
                "status": "ready",
                "overall_status": "passed",
                "readiness_status": "external_executor_harness_phase1_ready",
            },
            "frontend_runtime_shell_phase1": {
                "status": "ready",
                "overall_status": "passed",
                "readiness_status": "frontend_runtime_shell_phase1_ready",
            },
            "chinese_semantic_descaffolding_phase1": {
                "status": "ready",
                "overall_status": "passed",
                "readiness_status": "chinese_semantic_descaffolding_phase1_ready",
            },
            "capability_growth_phase5": {
                "status": "ready",
                "overall_status": "passed",
                "readiness_status": "capability_growth_phase5_ready",
            },
            "natural_long_horizon_calibration_phase1": {
                "status": "ready",
                "overall_status": "passed",
                "readiness_status": "natural_long_horizon_calibration_phase1_ready",
            },
        }
    }

    overrides = post_unlock_overrides_from_roadmap(roadmap)
    assert overrides["multimodal_input_capture"]["status"] == "implemented_ready"
    assert overrides["external_executor_harnesses"]["status"] == "implemented_ready"
    assert overrides["external_executor_harnesses"]["runtime_available"] is False
    assert overrides["natural_long_horizon_calibration"]["runtime_available"] is False

    result = evaluate_post_baseline_status(post_unlock_roadmap=roadmap)
    assert result["items"]["multimodal_input_capture"]["status"] == "implemented_ready"
    assert result["items"]["dynamic_skill_generation"]["status"] == "implemented_ready"
    assert result["items"]["external_executor_harnesses"]["runtime_available"] is False
    assert result["summary"]["implemented_ready"] >= 7


def test_evaluate_post_baseline_status_fails_if_required_runtime_item_missing():
    result = evaluate_post_baseline_status({"executor_adapter": {"status": "missing"}})

    assert result["overall_status"] == "failed"
    assert result["readiness_status"] == "post_baseline_closure_in_progress"
    assert "executor_adapter" in result["blocking_failure_ids"]

