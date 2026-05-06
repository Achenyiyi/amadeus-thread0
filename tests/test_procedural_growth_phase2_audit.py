from __future__ import annotations

from evals.run_procedural_growth_phase2_audit import (
    _aggregate_report,
    _build_check_specs,
    _parse_smoke_stdout,
    render_markdown,
)
from evals.run_procedural_growth_phase2_smokes import (
    _aggregate_smoke_report,
    _scenario_specs,
)


def test_smoke_scenarios_cover_phase2_contract():
    ids = {item["id"] for item in _scenario_specs()}

    assert ids == {
        "completed_sandbox_trace_guides_pytest_packet_with_approval",
        "blocked_trace_becomes_boundary_bias_not_execution",
        "browser_takeover_trace_surfaces_manual_boundary",
        "skill_usage_trace_guides_without_registry_mutation",
        "low_confidence_or_mismatched_trace_is_ignored",
    }


def test_aggregate_smoke_report_counts_failures():
    report = _aggregate_smoke_report(
        run_id="phase2-smoke-demo",
        results=[
            {"id": "a", "evaluation": {"passed": True}},
            {"id": "b", "evaluation": {"passed": False}},
        ],
    )

    assert report["overall_status"] == "failed"
    assert report["passed"] == 1
    assert report["failed"] == 1


def test_parse_smoke_stdout_extracts_phase2_report_artifacts():
    parsed = _parse_smoke_stdout(
        "\n".join(
            [
                "[procedural-growth-phase2-smokes] json=E:/repo/evals/reports/procedural-growth-phase2-smokes-demo.json",
                "[procedural-growth-phase2-smokes] md=E:/repo/evals/reports/procedural-growth-phase2-smokes-demo.md",
                "[procedural-growth-phase2-smokes] overall_status=passed",
            ]
        )
    )

    assert parsed["json"].endswith("procedural-growth-phase2-smokes-demo.json")
    assert parsed["overall_status"] == "passed"


def test_build_check_specs_cover_phase2_units_integration_readback_and_smokes():
    ids = {item["id"] for item in _build_check_specs("phase2-audit-demo")}

    assert ids == {
        "procedural_planning_unit_tests",
        "procedural_planning_autonomy_tests",
        "procedural_planning_backend_readback_tests",
        "procedural_growth_phase2_smokes",
    }


def test_aggregate_report_sets_phase2_ready_when_blocking_checks_pass():
    report = _aggregate_report(
        [
            {"id": "procedural_planning_unit_tests", "status": "passed", "blocking": True},
            {"id": "procedural_planning_autonomy_tests", "status": "passed", "blocking": True},
            {"id": "procedural_planning_backend_readback_tests", "status": "passed", "blocking": True},
            {"id": "procedural_growth_phase2_smokes", "status": "passed", "blocking": True},
        ]
    )

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "procedural_growth_phase2_ready"
    assert report["blocking_failure_ids"] == []


def test_aggregate_report_blocks_on_failed_required_check():
    report = _aggregate_report(
        [
            {"id": "procedural_planning_unit_tests", "status": "passed", "blocking": True},
            {"id": "procedural_planning_autonomy_tests", "status": "failed", "blocking": True},
            {"id": "procedural_planning_backend_readback_tests", "status": "passed", "blocking": True},
            {"id": "procedural_growth_phase2_smokes", "status": "passed", "blocking": True},
        ]
    )

    assert report["overall_status"] == "failed"
    assert report["readiness_status"] == "procedural_growth_phase2_in_progress"
    assert report["blocking_failure_ids"] == ["procedural_planning_autonomy_tests"]


def test_render_markdown_includes_phase2_readiness_and_checks():
    rendered = render_markdown(
        {
            "run_id": "procedural-growth-phase2-demo",
            "generated_at": "2026-05-06 12:00:00",
            "overall_status": "passed",
            "readiness_status": "procedural_growth_phase2_ready",
            "summary": {"checks_total": 1, "checks_passed": 1, "checks_failed": 0},
            "checks": [
                {
                    "id": "procedural_planning_unit_tests",
                    "title": "Planning",
                    "status": "passed",
                    "blocking": True,
                    "duration_s": 0.1,
                    "command": "python -m pytest",
                }
            ],
        }
    )

    assert "# Procedural Growth Phase 2 Audit" in rendered
    assert "procedural_growth_phase2_ready" in rendered
    assert "| `procedural_planning_unit_tests` | `passed` | `True` | 0.100 |" in rendered
