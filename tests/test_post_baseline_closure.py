from __future__ import annotations

from amadeus_thread0.runtime.post_baseline_closure import (
    POST_BASELINE_ITEMS,
    describe_post_baseline_item,
    evaluate_post_baseline_status,
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


def test_evaluate_post_baseline_status_fails_if_required_runtime_item_missing():
    result = evaluate_post_baseline_status({"executor_adapter": {"status": "missing"}})

    assert result["overall_status"] == "failed"
    assert result["readiness_status"] == "post_baseline_closure_in_progress"
    assert "executor_adapter" in result["blocking_failure_ids"]

