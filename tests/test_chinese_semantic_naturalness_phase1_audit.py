from __future__ import annotations

from evals.run_chinese_semantic_naturalness_phase1_audit import build_report, render_markdown


def test_naturalness_phase1_audit_report_is_ready_and_covers_required_smokes():
    report = build_report(run_id="unit-naturalness")

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "chinese_semantic_naturalness_phase1_ready"
    assert report["summary"]["scenario_count"] == 6
    assert report["summary"]["ready_or_not_applicable_count"] == 6
    assert report["summary"]["duplicate_output_detected"] is False
    assert report["summary"]["scaffold_residue_leaked"] is False
    assert report["summary"]["text_tts_drift"] is False
    assert report["summary"]["model_api_called"] is False
    assert report["summary"]["memory_write_allowed"] is False
    assert report["summary"]["behavior_mutation_allowed"] is False
    assert report["summary"]["persona_core_mutation_allowed"] is False
    assert report["summary"]["frontend_semantics_allowed"] is False
    assert report["summary"]["live_capture_enabled"] is False
    assert report["summary"]["skill_registry_write_allowed"] is False
    assert report["summary"]["external_mutation_allowed"] is False
    assert {row["name"] for row in report["scenarios"]} == {
        "everyday_service_frame",
        "repair_teacherly_scold",
        "self_rhythm_boundary_threat",
        "no_agenda_taskization",
        "stage_residue",
        "already_natural_presence",
    }


def test_naturalness_phase1_audit_markdown_includes_scenario_table():
    rendered = render_markdown(build_report(run_id="render-naturalness"))

    assert "# Chinese Semantic Naturalness Phase 1 Audit" in rendered
    assert "Readiness: `chinese_semantic_naturalness_phase1_ready`" in rendered
    assert "| `everyday_service_frame` | `passed` | `generic_assistant_tone` |" in rendered
