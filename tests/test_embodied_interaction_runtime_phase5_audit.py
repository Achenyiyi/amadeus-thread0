from __future__ import annotations

from evals.run_embodied_interaction_runtime_phase5_audit import build_report, render_markdown


def test_phase5_audit_reports_ready_without_behavior_mutation():
    report = build_report(run_id="phase5-test")

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "embodied_interaction_runtime_phase5_ready"
    assert report["summary"]["scenario_count"] == 6
    assert report["summary"]["alignment_count"] >= 1
    assert report["summary"]["advisory_not_reflected_count"] >= 1
    assert report["summary"]["causally_aligned_count"] >= 1
    assert report["summary"]["behavior_mutation_applied"] is False
    assert report["summary"]["model_api_called"] is False
    assert report["summary"]["writeback_ready_count"] == 0
    assert report["summary"]["should_write_memory"] is False
    assert report["failure_reasons"] == []


def test_phase5_audit_markdown_names_readiness_and_scenarios():
    rendered = render_markdown(build_report(run_id="phase5-md-test"))

    assert "# Embodied Interaction Runtime Phase 5 Audit" in rendered
    assert "embodied_interaction_runtime_phase5_ready" in rendered
    assert "artifact_motive_alignment_reports_not_reflected_without_mutation" in rendered
    assert "phase4_motive_contract_remains_preserved" in rendered

