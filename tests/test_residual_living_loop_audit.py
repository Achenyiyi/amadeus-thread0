from __future__ import annotations

from evals.run_residual_living_loop_audit import (
    build_deterministic_turn_fixture,
    build_report,
    render_markdown,
)


def test_build_report_returns_phase1_ready():
    report = build_report(run_id="test-run")

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "residual_living_loop_phase1_ready"
    assert report["readback"]["residuals"]["living_loop_traceability"]["status"] == "ready"


def test_deterministic_fixture_contains_all_loop_surfaces():
    turn = build_deterministic_turn_fixture()

    for key in (
        "current_event",
        "turn_appraisal",
        "emotion_state",
        "bond_state",
        "allostasis_state",
        "behavior_action",
        "behavior_plan",
        "digital_body_consequence",
        "reconsolidation_snapshot",
        "writeback_trace",
    ):
        assert key in turn


def test_markdown_renders_residual_table():
    rendered = render_markdown(build_report(run_id="render-test"))

    assert "# Residual Living Loop Closure Audit" in rendered
    assert "`residual_living_loop_phase1_ready`" in rendered
    assert "| `living_loop_traceability` | `ready` |" in rendered
