from __future__ import annotations

from evals.run_procedural_growth_phase4_audit import (
    _aggregate_report,
    _build_check_specs,
    _parse_smoke_stdout,
    render_markdown,
)
from evals.run_procedural_growth_phase4_smokes import (
    _aggregate_smoke_report,
    _scenario_specs,
)


def test_smoke_scenarios_cover_phase4_contract():
    ids = {item["id"] for item in _scenario_specs()}

    assert ids == {
        "failed_execution_suggests_failure_artifact_inspection",
        "blocked_boundary_recovery_does_not_repeat_blocked_action",
        "manual_takeover_recovery_preserves_takeover_boundary",
        "stale_context_recovery_refreshes_workspace_context",
        "no_executed_attempt_stays_hold",
    }


def test_aggregate_smoke_report_counts_failures():
    report = _aggregate_smoke_report(
        run_id="phase4-smoke-demo",
        results=[
            {"id": "a", "evaluation": {"passed": True}},
            {"id": "b", "evaluation": {"passed": False}},
        ],
    )

    assert report["overall_status"] == "failed"
    assert report["passed"] == 1
    assert report["failed"] == 1


def test_parse_smoke_stdout_extracts_phase4_report_artifacts():
    parsed = _parse_smoke_stdout(
        "\n".join(
            [
                "[procedural-growth-phase4-smokes] json=E:/repo/evals/reports/procedural-growth-phase4-smokes-demo.json",
                "[procedural-growth-phase4-smokes] md=E:/repo/evals/reports/procedural-growth-phase4-smokes-demo.md",
                "[procedural-growth-phase4-smokes] overall_status=passed",
            ]
        )
    )

    assert parsed["json"].endswith("procedural-growth-phase4-smokes-demo.json")
    assert parsed["overall_status"] == "passed"


def test_build_check_specs_cover_phase4_units_integration_readback_and_smokes():
    ids = {item["id"] for item in _build_check_specs("phase4-audit-demo")}

    assert ids == {
        "procedural_recovery_unit_tests",
        "procedural_recovery_planning_tests",
        "procedural_recovery_backend_readback_tests",
        "procedural_growth_phase4_smokes",
    }


def test_aggregate_report_sets_phase4_ready_when_blocking_checks_pass():
    report = _aggregate_report(
        [
            {"id": "procedural_recovery_unit_tests", "status": "passed", "blocking": True},
            {"id": "procedural_recovery_planning_tests", "status": "passed", "blocking": True},
            {"id": "procedural_recovery_backend_readback_tests", "status": "passed", "blocking": True},
            {"id": "procedural_growth_phase4_smokes", "status": "passed", "blocking": True},
        ]
    )

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "procedural_growth_phase4_ready"
    assert report["blocking_failure_ids"] == []


def test_aggregate_report_blocks_on_failed_required_check():
    report = _aggregate_report(
        [
            {"id": "procedural_recovery_unit_tests", "status": "passed", "blocking": True},
            {"id": "procedural_recovery_planning_tests", "status": "failed", "blocking": True},
            {"id": "procedural_recovery_backend_readback_tests", "status": "passed", "blocking": True},
            {"id": "procedural_growth_phase4_smokes", "status": "passed", "blocking": True},
        ]
    )

    assert report["overall_status"] == "failed"
    assert report["readiness_status"] == "procedural_growth_phase4_in_progress"
    assert report["blocking_failure_ids"] == ["procedural_recovery_planning_tests"]


def test_render_markdown_includes_phase4_readiness_and_checks():
    rendered = render_markdown(
        {
            "run_id": "procedural-growth-phase4-demo",
            "generated_at": "2026-05-06 12:00:00",
            "overall_status": "passed",
            "readiness_status": "procedural_growth_phase4_ready",
            "summary": {"checks_total": 1, "checks_passed": 1, "checks_failed": 0},
            "checks": [
                {
                    "id": "procedural_recovery_unit_tests",
                    "title": "Recovery",
                    "status": "passed",
                    "blocking": True,
                    "duration_s": 0.1,
                    "command": "python -m pytest",
                }
            ],
        }
    )

    assert "# Procedural Growth Phase 4 Audit" in rendered
    assert "procedural_growth_phase4_ready" in rendered
    assert "| `procedural_recovery_unit_tests` | `passed` | `True` | 0.100 |" in rendered
