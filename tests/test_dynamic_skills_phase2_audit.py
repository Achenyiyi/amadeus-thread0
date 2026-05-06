from __future__ import annotations

from evals.run_dynamic_skills_phase2_audit import evaluate_scenarios, run_scenarios


def test_dynamic_skills_phase2_audit_reaches_ready():
    report = evaluate_scenarios(run_scenarios())

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "dynamic_skills_phase2_ready"
