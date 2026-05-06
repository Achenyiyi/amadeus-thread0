from __future__ import annotations

from evals.run_multimodal_capture_audit import evaluate_checks


def test_multimodal_audit_ready_when_checks_pass():
    report = evaluate_checks([{"command": "pytest", "status": "passed"}])
    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "multimodal_capture_phase1_ready"
