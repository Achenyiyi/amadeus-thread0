from __future__ import annotations

from evals.run_chinese_semantic_descaffolding_phase2_audit import build_report, render_markdown


def test_phase2_audit_report_is_ready_and_covers_required_scenarios():
    report = build_report(run_id="unit-phase2")

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "chinese_semantic_descaffolding_phase2_ready"
    assert report["summary"]["scenario_count"] == 4
    assert report["summary"]["policy_ready_count"] == 4
    assert report["summary"]["duplicate_output_detected"] is False
    assert report["summary"]["scaffold_residue_leaked"] is False
    assert report["summary"]["text_tts_drift"] is False
    assert report["summary"]["model_api_called"] is False
    assert report["summary"]["memory_write_allowed"] is False
    assert report["summary"]["behavior_mutation_allowed"] is False
    assert report["summary"]["persona_core_mutation_allowed"] is False
    assert report["summary"]["frontend_semantics_allowed"] is False
    assert report["summary"]["skill_registry_write_allowed"] is False
    assert report["summary"]["external_mutation_allowed"] is False
    assert {row["name"] for row in report["scenarios"]} == {
        "everyday_generic_assistant",
        "repair_teacherly_scold",
        "self_rhythm_boundary_threat",
        "technical_task_taskization",
    }


def test_phase2_audit_markdown_includes_policy_table():
    rendered = render_markdown(build_report(run_id="render-phase2"))

    assert "# Chinese Semantic De-Scaffolding Phase 2 Audit" in rendered
    assert "Readiness: `chinese_semantic_descaffolding_phase2_ready`" in rendered
    assert "| `everyday_generic_assistant` | `passed` | `generic_assistant_tone` |" in rendered
