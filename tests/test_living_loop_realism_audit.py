from __future__ import annotations

from evals.run_living_loop_realism_audit import (
    build_deterministic_turn_fixture,
    build_report,
    render_markdown,
)


def test_build_report_returns_phase1_ready():
    report = build_report(run_id="test-run")

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "living_loop_runtime_realism_phase1_ready"
    assert report["readback"]["causality"]["status"] == "ready"
    assert report["chinese_semantic_replacement"]["status"] == "floor_rewritten"


def test_fixture_contains_causal_loop_surfaces():
    turn = build_deterministic_turn_fixture()

    for key in (
        "turn_appraisal",
        "emotion_state",
        "bond_state",
        "allostasis_state",
        "counterpart_assessment",
        "semantic_narrative_profile",
        "behavior_action",
        "behavior_plan",
        "digital_body_consequence",
        "reconsolidation_snapshot",
        "writeback_trace",
    ):
        assert key in turn


def test_markdown_renders_causality_and_chinese_guidance():
    rendered = render_markdown(build_report(run_id="render-test"))

    assert "# Living Loop Runtime Realism Audit" in rendered
    assert "`living_loop_runtime_realism_phase1_ready`" in rendered
    assert "| `appraisal_to_motive` | `ready` |" in rendered
    assert "Chinese Semantic Replacement" in rendered
