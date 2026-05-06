from __future__ import annotations

from evals.run_dynamic_skills_audit import evaluate_checks


def test_dynamic_skills_audit_ready_when_checks_pass():
    report = evaluate_checks([{"command": "pytest", "status": "passed"}])
    assert report["readiness_status"] == "dynamic_skills_phase1_ready"
