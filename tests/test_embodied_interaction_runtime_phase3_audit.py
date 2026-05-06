from __future__ import annotations

from evals.run_embodied_interaction_runtime_phase3_audit import build_report, render_markdown


def test_build_report_returns_phase3_ready():
    report = build_report(run_id="unit")

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "embodied_interaction_runtime_phase3_ready"
    assert report["summary"]["evidence_count"] >= 4
    assert report["summary"]["access_friction_observed"] is True
    assert report["summary"]["model_api_called"] is False
    assert report["summary"]["writeback_ready_count"] == 0
    assert report["summary"]["should_write_memory"] is False


def test_render_markdown_includes_phase3_scenarios():
    rendered = render_markdown(build_report(run_id="unit-md"))

    assert "# Embodied Interaction Runtime Phase 3 Audit" in rendered
    assert "`embodied_interaction_runtime_phase3_ready`" in rendered
    assert "| `artifact_semantics_becomes_appraisal_evidence` | `passed` |" in rendered
    assert "| `access_friction_observation_influences_appraisal_readback` | `passed` |" in rendered
    assert "| `backend_payload_carries_artifact_appraisal` | `passed` |" in rendered
    assert "| `blocked_live_capture_does_not_create_appraisal_evidence` | `passed` |" in rendered
