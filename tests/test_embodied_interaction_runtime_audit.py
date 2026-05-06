from __future__ import annotations

from evals.run_embodied_interaction_runtime_audit import build_report, render_markdown


def test_build_report_returns_phase1_ready():
    report = build_report(run_id="unit")

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "embodied_interaction_runtime_phase1_ready"
    assert report["summary"]["available_source_count"] >= 3
    assert report["summary"]["blocked_source_count"] == 1
    assert report["summary"]["semantic_floor_applied"] is True


def test_render_markdown_includes_source_and_semantic_status():
    rendered = render_markdown(build_report(run_id="unit-md"))

    assert "# Embodied Interaction Runtime Phase 1 Audit" in rendered
    assert "`embodied_interaction_runtime_phase1_ready`" in rendered
    assert "| `image_file_source_enters_perception` | `passed` |" in rendered
    assert "| `blocked_live_capture_stays_blocked` | `passed` |" in rendered
    assert "| `chinese_semantic_surface_runtime_floor` | `passed` |" in rendered
