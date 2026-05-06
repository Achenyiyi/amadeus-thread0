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
        "dynamic_skill_generation",
        "chinese_de_scaffolding",
        "bounded_capability_growth",
        "natural_long_horizon_calibration",
    }


def test_deferred_surfaces_are_fail_closed_not_available():
    multimodal = describe_post_baseline_item("multimodal_input_capture")
    skill_generation = describe_post_baseline_item("dynamic_skill_generation")

    assert multimodal["status"] == "deferred_fail_closed"
    assert "audio_input" in multimodal["blocked_surfaces"]
    assert "image_observation" in multimodal["blocked_surfaces"]
    assert skill_generation["status"] == "deferred_fail_closed"
    assert skill_generation["runtime_available"] is False


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
    assert result["summary"]["deferred_fail_closed"] >= 2


def test_evaluate_post_baseline_status_fails_if_required_runtime_item_missing():
    result = evaluate_post_baseline_status({"executor_adapter": {"status": "missing"}})

    assert result["overall_status"] == "failed"
    assert result["readiness_status"] == "post_baseline_closure_in_progress"
    assert "executor_adapter" in result["blocking_failure_ids"]

