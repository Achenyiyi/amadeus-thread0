from __future__ import annotations

from evals.run_runtime_productization_phase3_audit import evaluate_runtime_productization_phase3_audit


def test_phase3_audit_passes_when_dashboard_and_product_runtime_smokes_are_ready():
    report = evaluate_runtime_productization_phase3_audit(
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
        smoke_report={
            "overall_status": "passed",
            "readiness_status": "runtime_productization_phase3_smokes_ready",
        },
        source_reports={
            "preserved_baselines": "evals/reports/preserved-baselines-audit-ready.json",
            "post_unlock_roadmap": "evals/reports/post-unlock-roadmap-audit-ready.json",
            "runtime_productization": "evals/reports/runtime-productization-phase2-audit-ready.json",
            "phase3_smokes": "evals/reports/runtime-productization-phase3-smokes-ready.json",
        },
    )

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "runtime_productization_phase3_ready"
    assert report["dashboard"]["readiness_status"] == "runtime_status_dashboard_ready"
    assert report["checks"]["phase3_smokes"]["status"] == "passed"
    assert report["authority_boundary"]["http_server_semantics_owner"] is False
    assert report["authority_boundary"]["live_capture_enabled"] is False


def test_phase3_audit_fails_honestly_when_preserved_baseline_sources_are_missing():
    report = evaluate_runtime_productization_phase3_audit(
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
        post_unlock_roadmap={"overall_status": "missing", "readiness_status": ""},
        runtime_productization={"overall_status": "missing", "readiness_status": ""},
        smoke_report={"overall_status": "passed", "readiness_status": "runtime_productization_phase3_smokes_ready"},
        source_reports={},
    )

    assert report["overall_status"] == "failed"
    assert report["readiness_status"] == "runtime_productization_phase3_blocked"
    assert report["dashboard"]["diagnostics"]["state_interpretation"] == "source_reports_missing"
    assert report["checks"]["preserved_baselines"]["status"] == "failed"
