from __future__ import annotations

from evals.run_procedural_growth_phase3_audit import (
    _aggregate_report,
    _build_check_specs,
    _parse_smoke_stdout,
    render_markdown,
)
from evals.run_procedural_growth_phase3_smokes import (
    _aggregate_smoke_report,
    _scenario_specs,
)


def test_smoke_scenarios_cover_phase3_contract():
    ids = {item["id"] for item in _scenario_specs()}

    assert ids == {
        "calibrated_sandbox_success_boosts_reuse",
        "failed_sandbox_attempt_reduces_reuse",
        "manual_takeover_preserves_boundary",
        "pending_attempt_does_not_become_fact",
    }


def test_aggregate_smoke_report_counts_failures():
    report = _aggregate_smoke_report(
        run_id="phase3-smoke-demo",
        results=[
            {"id": "a", "evaluation": {"passed": True}},
            {"id": "b", "evaluation": {"passed": False}},
        ],
    )

    assert report["overall_status"] == "failed"
    assert report["passed"] == 1
    assert report["failed"] == 1


def test_parse_smoke_stdout_extracts_phase3_report_artifacts():
    parsed = _parse_smoke_stdout(
        "\n".join(
            [
                "[procedural-growth-phase3-smokes] json=E:/repo/evals/reports/procedural-growth-phase3-smokes-demo.json",
                "[procedural-growth-phase3-smokes] md=E:/repo/evals/reports/procedural-growth-phase3-smokes-demo.md",
                "[procedural-growth-phase3-smokes] overall_status=passed",
            ]
        )
    )

    assert parsed["json"].endswith("procedural-growth-phase3-smokes-demo.json")
    assert parsed["overall_status"] == "passed"


def test_build_check_specs_cover_phase3_units_integration_readback_and_smokes():
    ids = {item["id"] for item in _build_check_specs("phase3-audit-demo")}

    assert ids == {
        "procedural_outcome_unit_tests",
        "procedural_outcome_planning_tests",
        "procedural_outcome_backend_readback_tests",
        "procedural_growth_phase3_smokes",
    }


def test_aggregate_report_sets_phase3_ready_when_blocking_checks_pass():
    report = _aggregate_report(
        [
            {"id": "procedural_outcome_unit_tests", "status": "passed", "blocking": True},
            {"id": "procedural_outcome_planning_tests", "status": "passed", "blocking": True},
            {"id": "procedural_outcome_backend_readback_tests", "status": "passed", "blocking": True},
            {"id": "procedural_growth_phase3_smokes", "status": "passed", "blocking": True},
        ]
    )

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "procedural_growth_phase3_ready"
    assert report["blocking_failure_ids"] == []


def test_aggregate_report_blocks_on_failed_required_check():
    report = _aggregate_report(
        [
            {"id": "procedural_outcome_unit_tests", "status": "passed", "blocking": True},
            {"id": "procedural_outcome_planning_tests", "status": "failed", "blocking": True},
            {"id": "procedural_outcome_backend_readback_tests", "status": "passed", "blocking": True},
            {"id": "procedural_growth_phase3_smokes", "status": "passed", "blocking": True},
        ]
    )

    assert report["overall_status"] == "failed"
    assert report["readiness_status"] == "procedural_growth_phase3_in_progress"
    assert report["blocking_failure_ids"] == ["procedural_outcome_planning_tests"]


def test_render_markdown_includes_phase3_readiness_and_checks():
    rendered = render_markdown(
        {
            "run_id": "procedural-growth-phase3-demo",
            "generated_at": "2026-05-06 12:00:00",
            "overall_status": "passed",
            "readiness_status": "procedural_growth_phase3_ready",
            "summary": {"checks_total": 1, "checks_passed": 1, "checks_failed": 0},
            "checks": [
                {
                    "id": "procedural_outcome_unit_tests",
                    "title": "Outcome",
                    "status": "passed",
                    "blocking": True,
                    "duration_s": 0.1,
                    "command": "python -m pytest",
                }
            ],
        }
    )

    assert "# Procedural Growth Phase 3 Audit" in rendered
    assert "procedural_growth_phase3_ready" in rendered
    assert "| `procedural_outcome_unit_tests` | `passed` | `True` | 0.100 |" in rendered
