from __future__ import annotations

from evals.run_http_transport_audit import evaluate_http_transport_audit


def test_http_transport_audit_passes_with_ready_smokes_and_closed_boundary():
    report = evaluate_http_transport_audit(
        smoke_report={
            "overall_status": "passed",
            "readiness_status": "http_transport_thin_wrapper_phase1_smokes_ready",
            "authority_boundary": {
                "transport_role": "thin_wrapper",
                "backend_semantics_owner": False,
                "frontend_semantics_owner": False,
                "sse_or_websocket_streaming_enabled": False,
            },
        }
    )

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "http_transport_thin_wrapper_phase1_ready"
    assert report["checks"]["smoke_readiness"]["status"] == "passed"
    assert report["checks"]["authority_boundary"]["status"] == "passed"


def test_http_transport_audit_fails_when_smoke_report_missing():
    report = evaluate_http_transport_audit(smoke_report={"overall_status": "missing", "readiness_status": ""})

    assert report["overall_status"] == "failed"
    assert report["readiness_status"] == "http_transport_thin_wrapper_phase1_blocked"
    assert report["checks"]["smoke_readiness"]["status"] == "failed"


def test_http_transport_audit_fails_when_boundary_widens():
    report = evaluate_http_transport_audit(
        smoke_report={
            "overall_status": "passed",
            "readiness_status": "http_transport_thin_wrapper_phase1_smokes_ready",
            "authority_boundary": {
                "transport_role": "thin_wrapper",
                "backend_semantics_owner": True,
                "frontend_semantics_owner": False,
                "sse_or_websocket_streaming_enabled": False,
            },
        }
    )

    assert report["overall_status"] == "failed"
    assert report["checks"]["authority_boundary"]["status"] == "failed"
    assert "backend_semantics_owner" in report["checks"]["authority_boundary"]["failure_reasons"][0]
