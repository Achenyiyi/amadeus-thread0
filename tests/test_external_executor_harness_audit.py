from __future__ import annotations

from amadeus_thread0.runtime.executor_harness_registry import build_executor_harness_registry
from evals.run_external_executor_harness_audit import evaluate_harness_registry


def test_external_executor_harness_audit_ready():
    report = evaluate_harness_registry(build_executor_harness_registry())
    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "external_executor_harness_phase1_ready"
