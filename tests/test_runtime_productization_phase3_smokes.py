from __future__ import annotations

from evals.run_runtime_productization_phase3_smokes import run_runtime_productization_phase3_smokes


def test_phase3_smokes_prove_route_adapter_consumes_backend_owned_envelopes():
    report = run_runtime_productization_phase3_smokes()

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "runtime_productization_phase3_smokes_ready"
    assert report["scenarios"]["operator_readback_route"]["status"] == "passed"
    assert report["scenarios"]["assistant_turn_finalize"]["status"] == "passed"
    assert report["scenarios"]["event_round_finalize"]["status"] == "passed"
    assert report["scenarios"]["frontend_consumer_boundary"]["status"] == "passed"
    assert report["authority_boundary"]["frontend_semantics_owner"] is False
    assert report["authority_boundary"]["http_server_semantics_owner"] is False
