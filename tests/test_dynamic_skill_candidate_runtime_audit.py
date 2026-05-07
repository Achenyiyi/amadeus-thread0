from __future__ import annotations

from evals.run_dynamic_skill_candidate_runtime_audit import evaluate_scenarios, run_scenarios


def test_dynamic_skill_candidate_runtime_audit_reaches_ready():
    report = evaluate_scenarios(run_scenarios())

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "dynamic_skill_candidate_runtime_phase1_ready"

