from __future__ import annotations

from evals.run_runtime_productization_audit import evaluate_runtime_productization_audit, render_markdown


def test_evaluate_runtime_productization_audit_passes_with_ready_inputs():
    report = evaluate_runtime_productization_audit(
        {
            "post_baseline": {
                "overall_status": "passed",
                "readiness_status": "post_baseline_closure_ready",
                "items": {
                    "dynamic_skill_generation": {
                        "status": "implemented_ready",
                        "runtime_available": False,
                    }
                },
            },
            "preserved_baselines": {
                "overall_status": "passed",
                "readiness_status": "preserved_baselines_ready",
            },
            "post_unlock_roadmap": {
                "overall_status": "passed",
                "readiness_status": "post_unlock_roadmap_ready",
            },
        }
    )

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "runtime_productization_phase2_ready"
    assert report["operator_readback"]["schema"] == "operator_readback.v2"
    assert report["operator_readback"]["lanes"]["dynamic_skill_generation"]["runtime_available"] is False


def test_evaluate_runtime_productization_audit_fails_when_input_regresses():
    report = evaluate_runtime_productization_audit(
        {
            "post_baseline": {
                "overall_status": "passed",
                "readiness_status": "post_baseline_closure_ready",
                "items": {},
            },
            "preserved_baselines": {
                "overall_status": "failed",
                "readiness_status": "preserved_baselines_regressed",
            },
            "post_unlock_roadmap": {
                "overall_status": "passed",
                "readiness_status": "post_unlock_roadmap_ready",
            },
        }
    )

    assert report["overall_status"] == "failed"
    assert report["readiness_status"] == "runtime_productization_phase2_in_progress"
    assert "preserved_baselines_ready" in report["contract"]["failure_reasons"][0]


def test_render_markdown_includes_runtime_productization_readiness():
    report = evaluate_runtime_productization_audit(
        {
            "post_baseline": {
                "overall_status": "passed",
                "readiness_status": "post_baseline_closure_ready",
                "items": {},
            },
            "preserved_baselines": {
                "overall_status": "passed",
                "readiness_status": "preserved_baselines_ready",
            },
            "post_unlock_roadmap": {
                "overall_status": "passed",
                "readiness_status": "post_unlock_roadmap_ready",
            },
        }
    )

    rendered = render_markdown(report)

    assert "# Runtime Productization Phase 2 Audit" in rendered
    assert "runtime_productization_phase2_ready" in rendered
    assert "| `runtime_productization_contract` | `passed` | `runtime_productization_phase2_ready` | `runtime_productization_phase2_ready` |" in rendered
    assert "| `external_mutation_requires_approval` | `True` |" in rendered
