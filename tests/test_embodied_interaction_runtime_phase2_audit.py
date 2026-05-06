from __future__ import annotations

from evals.run_embodied_interaction_runtime_phase2_audit import build_report, render_markdown


def test_build_report_returns_phase2_ready():
    report = build_report(run_id="unit")

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "embodied_interaction_runtime_phase2_ready"
    assert report["summary"]["semantic_observation_count"] >= 5
    assert report["summary"]["model_api_called"] is False
    assert report["summary"]["writeback_ready_count"] == 0


def test_render_markdown_includes_phase2_scenarios():
    rendered = render_markdown(build_report(run_id="unit-md"))

    assert "# Embodied Interaction Runtime Phase 2 Audit" in rendered
    assert "`embodied_interaction_runtime_phase2_ready`" in rendered
    assert "| `image_artifact_metadata_enters_semantic_observation` | `passed` |" in rendered
    assert "| `blocked_live_capture_has_no_semantic_observation` | `passed` |" in rendered
    assert "| `semantic_observation_reaches_backend_payload` | `passed` |" in rendered
