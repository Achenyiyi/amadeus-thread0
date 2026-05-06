from __future__ import annotations

from evals.run_post_unlock_roadmap_audit import evaluate_post_unlock_roadmap


def test_lane_statuses_include_all_unlocked_lanes():
    report = evaluate_post_unlock_roadmap({})
    assert set(report["lanes"]) == {
        "multimodal_capture_phase1",
        "dynamic_skills_phase1",
        "external_executor_harness_phase1",
        "frontend_runtime_shell_phase1",
        "chinese_semantic_descaffolding_phase1",
        "capability_growth_phase5",
        "natural_long_horizon_calibration_phase1",
    }


def test_missing_lane_reports_keep_overall_in_progress():
    report = evaluate_post_unlock_roadmap({})
    assert report["overall_status"] == "in_progress"
    assert report["readiness_status"] == "post_unlock_roadmap_in_progress"


def test_all_ready_reports_pass():
    report = evaluate_post_unlock_roadmap(
        {
            "multimodal_capture_phase1": {"overall_status": "passed", "readiness_status": "multimodal_capture_phase1_ready"},
            "dynamic_skills_phase1": {"overall_status": "passed", "readiness_status": "dynamic_skills_phase1_ready"},
            "external_executor_harness_phase1": {"overall_status": "passed", "readiness_status": "external_executor_harness_phase1_ready"},
            "frontend_runtime_shell_phase1": {"overall_status": "passed", "readiness_status": "frontend_runtime_shell_phase1_ready"},
            "chinese_semantic_descaffolding_phase1": {"overall_status": "passed", "readiness_status": "chinese_semantic_descaffolding_phase1_ready"},
            "capability_growth_phase5": {"overall_status": "passed", "readiness_status": "capability_growth_phase5_ready"},
            "natural_long_horizon_calibration_phase1": {"overall_status": "passed", "readiness_status": "natural_long_horizon_calibration_phase1_ready"},
        }
    )
    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "post_unlock_roadmap_ready"
