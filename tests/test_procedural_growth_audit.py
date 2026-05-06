from __future__ import annotations

from evals.run_procedural_growth_audit import (
    _aggregate_report,
    _build_check_specs,
    _parse_smoke_stdout,
    render_markdown,
)
from evals.run_procedural_growth_smokes import (
    _aggregate_smoke_report,
    _scenario_specs,
)


def test_smoke_scenarios_cover_phase1_contract():
    ids = {item["id"] for item in _scenario_specs()}

    assert ids == {
        "completed_sandbox_run_becomes_reusable_procedure",
        "blocked_command_becomes_boundary_note_not_capability",
        "browser_takeover_boundary_resurfaces_as_procedure",
        "skill_usage_resurfaces_without_registry_pollution",
        "followup_uses_procedural_hint_but_keeps_approval_required",
    }


def test_aggregate_smoke_report_counts_failures():
    report = _aggregate_smoke_report(
        run_id="smoke-demo",
        results=[
            {"id": "a", "evaluation": {"passed": True}},
            {"id": "b", "evaluation": {"passed": False}},
        ],
    )

    assert report["overall_status"] == "failed"
    assert report["passed"] == 1
    assert report["failed"] == 1


def test_parse_smoke_stdout_extracts_report_artifacts():
    parsed = _parse_smoke_stdout(
        "\n".join(
            [
                "[procedural-growth-smokes] json=E:/repo/evals/reports/procedural-growth-smokes-demo.json",
                "[procedural-growth-smokes] md=E:/repo/evals/reports/procedural-growth-smokes-demo.md",
                "[procedural-growth-smokes] overall_status=passed",
            ]
        )
    )

    assert parsed["json"].endswith("procedural-growth-smokes-demo.json")
    assert parsed["overall_status"] == "passed"


def test_build_check_specs_cover_units_backend_and_smokes():
    ids = {item["id"] for item in _build_check_specs("audit-demo")}

    assert ids == {
        "procedural_growth_core_tests",
        "procedural_growth_backend_readback_tests",
        "procedural_growth_smokes",
    }


def test_aggregate_report_sets_ready_when_blocking_checks_pass():
    report = _aggregate_report(
        [
            {"id": "procedural_growth_core_tests", "status": "passed", "blocking": True},
            {"id": "procedural_growth_backend_readback_tests", "status": "passed", "blocking": True},
            {"id": "procedural_growth_smokes", "status": "passed", "blocking": True},
        ]
    )

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "procedural_growth_phase1_ready"
    assert report["blocking_failure_ids"] == []


def test_aggregate_report_blocks_on_failed_required_check():
    report = _aggregate_report(
        [
            {"id": "procedural_growth_core_tests", "status": "passed", "blocking": True},
            {"id": "procedural_growth_backend_readback_tests", "status": "failed", "blocking": True},
            {"id": "procedural_growth_smokes", "status": "passed", "blocking": True},
        ]
    )

    assert report["overall_status"] == "failed"
    assert report["readiness_status"] == "procedural_growth_phase1_in_progress"
    assert report["blocking_failure_ids"] == ["procedural_growth_backend_readback_tests"]


def test_render_markdown_includes_readiness_and_checks():
    rendered = render_markdown(
        {
            "run_id": "procedural-growth-demo",
            "generated_at": "2026-05-06 12:00:00",
            "overall_status": "passed",
            "readiness_status": "procedural_growth_phase1_ready",
            "summary": {"checks_total": 1, "checks_passed": 1, "checks_failed": 0},
            "checks": [
                {
                    "id": "procedural_growth_core_tests",
                    "title": "Core",
                    "status": "passed",
                    "blocking": True,
                    "duration_s": 0.1,
                    "command": "python -m pytest",
                }
            ],
        }
    )

    assert "# Procedural Growth Phase 1 Audit" in rendered
    assert "procedural_growth_phase1_ready" in rendered
    assert "| `procedural_growth_core_tests` | `passed` | `True` | 0.100 |" in rendered
