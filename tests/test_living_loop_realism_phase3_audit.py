from __future__ import annotations

from evals.run_living_loop_realism_phase3_audit import build_report, render_markdown


def test_phase3_report_returns_ready_with_artifact_alignment_visible():
    report = build_report(run_id="test-run")

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "living_loop_runtime_realism_phase3_ready"
    assert report["summary"]["scenario_count"] == 4
    assert report["summary"]["alignment_visible_count"] >= 2
    assert report["summary"]["causally_aligned_count"] >= 1
    assert report["summary"]["advisory_not_reflected_count"] >= 1
    assert report["summary"]["model_api_called"] is False
    assert report["summary"]["writeback_ready_count"] == 0
    assert report["summary"]["behavior_mutation_applied"] is False
    assert report["failure_reasons"] == []


def test_phase3_markdown_renders_artifact_alignment_status():
    rendered = render_markdown(build_report(run_id="render-test"))

    assert "# Living Loop Runtime Realism Phase 3 Audit" in rendered
    assert "`living_loop_runtime_realism_phase3_ready`" in rendered
    assert "artifact_alignment_causally_aligned_visible" in rendered
    assert "artifact_alignment_advisory_not_reflected_visible" in rendered

