from __future__ import annotations

from evals.run_embodied_interaction_runtime_phase4_audit import build_report, render_markdown


def test_phase4_audit_reports_ready_when_motive_hints_are_readonly():
    report = build_report(run_id="phase4-test")

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "embodied_interaction_runtime_phase4_ready"
    assert report["summary"]["scenario_count"] == 6
    assert report["summary"]["hint_count"] >= 1
    assert report["summary"]["behavior_mutation_allowed"] is False
    assert report["summary"]["model_api_called"] is False
    assert report["summary"]["writeback_ready_count"] == 0
    assert report["summary"]["should_write_memory"] is False
    assert report["failure_reasons"] == []


def test_phase4_audit_markdown_names_readiness_and_scenarios():
    rendered = render_markdown(build_report(run_id="phase4-md-test"))

    assert "# Embodied Interaction Runtime Phase 4 Audit" in rendered
    assert "embodied_interaction_runtime_phase4_ready" in rendered
    assert "artifact_appraisal_becomes_motive_hint" in rendered
    assert "phase3_appraisal_contract_remains_preserved" in rendered
