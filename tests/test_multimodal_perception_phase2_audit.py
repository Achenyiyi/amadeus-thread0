from __future__ import annotations

from evals.run_multimodal_perception_phase2_audit import build_report, render_markdown


def test_phase2_audit_reports_ready():
    report = build_report(run_id="unit")

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "multimodal_perception_phase2_ready"
    assert report["summary"]["scenario_count"] == 4
    assert report["summary"]["model_api_called"] is False
    assert report["summary"]["live_capture_enabled"] is False
    assert report["summary"]["memory_write_allowed"] is False
    assert report["summary"]["external_mutation_allowed"] is False


def test_phase2_audit_markdown_names_ready_status():
    rendered = render_markdown(
        {
            "overall_status": "passed",
            "readiness_status": "multimodal_perception_phase2_ready",
            "summary": {"scenario_count": 4},
            "scenarios": [
                {
                    "name": "pending_approval",
                    "status": "passed",
                    "readiness_status": "multimodal_perception_phase2_ready",
                }
            ],
            "failure_reasons": [],
        }
    )

    assert "Multimodal Perception Phase 2 Audit" in rendered
    assert "multimodal_perception_phase2_ready" in rendered
