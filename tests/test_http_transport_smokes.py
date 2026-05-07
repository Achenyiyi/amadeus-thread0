from __future__ import annotations

from evals.run_http_transport_smokes import run_http_transport_smokes


def test_http_transport_smokes_cover_routes_and_boundary():
    report = run_http_transport_smokes()

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "http_transport_thin_wrapper_phase1_smokes_ready"
    assert report["scenarios"]["runtime_productization_get"]["status"] == "passed"
    assert report["scenarios"]["assistant_turn_finalize_post"]["status"] == "passed"
    assert report["scenarios"]["invalid_json_boundary"]["status"] == "passed"
    assert report["scenarios"]["method_not_allowed_boundary"]["status"] == "passed"
    assert report["scenarios"]["authority_boundary_closed"]["status"] == "passed"
    assert report["authority_boundary"]["transport_role"] == "thin_wrapper"
    assert report["authority_boundary"]["backend_semantics_owner"] is False
