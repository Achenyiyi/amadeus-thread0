from __future__ import annotations

from amadeus_thread0.runtime.runtime_status_dashboard import (
    build_runtime_status_dashboard,
    compact_runtime_status_line,
)


def test_dashboard_distinguishes_ready_runtime_enabled_and_blocked_lanes():
    dashboard = build_runtime_status_dashboard(
        preserved_baselines={
            "overall_status": "passed",
            "readiness_status": "preserved_baselines_ready",
            "summary": {"total": 29, "passed": 29, "failed": 0},
        },
        post_unlock_roadmap={
            "overall_status": "passed",
            "readiness_status": "post_unlock_roadmap_ready",
            "summary": {"total": 7, "ready": 7, "regressed": 0},
        },
        runtime_productization={
            "overall_status": "passed",
            "readiness_status": "runtime_productization_phase2_ready",
        },
        source_reports={
            "preserved_baselines": "evals/reports/preserved-baselines-audit-ready.json",
            "post_unlock_roadmap": "evals/reports/post-unlock-roadmap-audit-ready.json",
            "runtime_productization": "evals/reports/runtime-productization-phase2-audit-ready.json",
        },
    )

    assert dashboard["schema"] == "runtime_status_dashboard.v1"
    assert dashboard["overall_status"] == "passed"
    assert dashboard["readiness_status"] == "runtime_status_dashboard_ready"
    assert dashboard["summary"]["ready_gates"] == 3
    assert dashboard["summary"]["total_gates"] == 3
    assert dashboard["lanes"]["frontend_runtime_shell"]["runtime_authority"] == "consumer_only"
    assert dashboard["lanes"]["http_transport"]["status"] == "phase1_ready"
    assert dashboard["lanes"]["http_transport"]["runtime_authority"] == "thin_wrapper"
    assert dashboard["lanes"]["multimodal_artifact_inspection"]["status"] == "phase1_ready"
    assert dashboard["lanes"]["multimodal_artifact_inspection"]["runtime_authority"] == "approved_result_ingestion_only"
    assert dashboard["lanes"]["live_capture"]["runtime_authority"] == "blocked_by_contract"
    assert dashboard["lanes"]["dynamic_skill_generation"]["runtime_authority"] == "next_spec_required"
    assert dashboard["next_specs"][0]["id"] == "chinese_semantic_naturalness"
    assert dashboard["stale_plan_hygiene"]["status"] == "attention_recommended"


def test_dashboard_reports_missing_source_reports_without_calling_it_runtime_regression():
    dashboard = build_runtime_status_dashboard(
        preserved_baselines={
            "overall_status": "failed",
            "readiness_status": "preserved_baselines_regressed",
            "summary": {"total": 29, "passed": 0, "failed": 29},
            "baselines": {
                "backend_freeze_gate": {
                    "status": "failed",
                    "failure_reasons": ["missing_report:backend-freeze-gate-audit-"],
                }
            },
        },
        post_unlock_roadmap={
            "overall_status": "missing",
            "readiness_status": "",
            "failure_reasons": ["missing_report:post-unlock-roadmap-audit-"],
        },
        runtime_productization={
            "overall_status": "missing",
            "readiness_status": "",
            "failure_reasons": ["missing_report:runtime-productization-phase2-audit-"],
        },
        source_reports={},
    )

    assert dashboard["overall_status"] == "attention_required"
    assert dashboard["readiness_status"] == "runtime_status_dashboard_attention_required"
    assert dashboard["summary"]["missing_source_reports"] == 3
    assert dashboard["diagnostics"]["state_interpretation"] == "source_reports_missing"
    assert "missing_report:backend-freeze-gate-audit-" in dashboard["diagnostics"]["sample_failures"]


def test_compact_runtime_status_line_is_short_and_explicit():
    dashboard = build_runtime_status_dashboard(
        preserved_baselines={"overall_status": "passed", "readiness_status": "preserved_baselines_ready"},
        post_unlock_roadmap={"overall_status": "passed", "readiness_status": "post_unlock_roadmap_ready"},
        runtime_productization={"overall_status": "passed", "readiness_status": "runtime_productization_phase2_ready"},
        source_reports={},
    )

    line = compact_runtime_status_line(dashboard)

    assert "runtime_status=runtime_status_dashboard_ready" in line
    assert "gates=3/3" in line
    assert "next_specs=2" in line
    assert "blocked=2" in line
