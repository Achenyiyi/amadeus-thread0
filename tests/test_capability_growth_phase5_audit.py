from __future__ import annotations

from evals.run_capability_growth_phase5_audit import evaluate_checks


def test_capability_growth_phase5_audit_ready_when_checks_pass():
    report = evaluate_checks([{"command": "pytest", "status": "passed"}])
    assert report["readiness_status"] == "capability_growth_phase5_ready"
