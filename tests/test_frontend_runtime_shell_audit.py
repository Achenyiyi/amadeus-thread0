from __future__ import annotations

from evals.run_frontend_runtime_shell_audit import evaluate_checks


def test_frontend_runtime_shell_ready_when_contract_and_build_pass():
    report = evaluate_checks([{"command": "pytest", "status": "passed"}, {"command": "npm build", "status": "passed"}])
    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "frontend_runtime_shell_phase1_ready"
