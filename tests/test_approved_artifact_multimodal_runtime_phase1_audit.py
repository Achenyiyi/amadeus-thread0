from __future__ import annotations

from evals.run_approved_artifact_multimodal_runtime_phase1_audit import (
    build_report,
    render_markdown,
)


def test_phase1_audit_passes_with_exact_result_ingestion_and_blocked_unsafe_paths():
    report = build_report(run_id="unit")

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "approved_artifact_multimodal_runtime_phase1_ready"
    assert set(report["scenarios"]) == {
        "approved_result_ingestion",
        "proposal_or_source_drift_rejected",
        "model_api_or_live_capture_rejected",
        "backend_payload_packet_completion",
    }
    assert report["summary"]["scenario_count"] == 4
    assert report["summary"]["semantic_observation_count"] >= 1
    assert report["summary"]["completed_packet_count"] >= 1
    assert report["authority_boundary"]["live_capture_allowed"] is False
    assert report["authority_boundary"]["multimodal_model_api_called"] is False
    assert report["authority_boundary"]["memory_write_allowed"] is False
    assert report["authority_boundary"]["external_mutation_allowed"] is False


def test_phase1_audit_markdown_names_readiness_and_scenarios():
    report = {
        "generated_at": "2026-05-07 12:00:00",
        "overall_status": "passed",
        "readiness_status": "approved_artifact_multimodal_runtime_phase1_ready",
        "summary": {
            "scenario_count": 4,
            "semantic_observation_count": 1,
            "completed_packet_count": 2,
            "model_api_called": False,
            "live_capture_enabled": False,
            "memory_write_allowed": False,
            "external_mutation_allowed": False,
        },
        "authority_boundary": {
            "live_capture_allowed": False,
            "multimodal_model_api_called": False,
        },
        "scenarios": {
            "approved_result_ingestion": {"status": "passed", "semantic_observation_count": 1},
        },
        "failure_reasons": [],
    }

    rendered = render_markdown(report)

    assert "# Approved Artifact Multimodal Runtime Phase 1 Audit" in rendered
    assert "approved_artifact_multimodal_runtime_phase1_ready" in rendered
    assert "approved_result_ingestion" in rendered
