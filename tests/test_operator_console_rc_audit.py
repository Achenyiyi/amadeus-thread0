from __future__ import annotations

from evals.run_operator_console_rc_phase1_audit import (
    evaluate_operator_console_rc_phase1_audit,
    render_markdown,
)


def _ready_rc() -> dict:
    return {
        "schema": "technical_preview_rc.v1",
        "overall_status": "passed",
        "readiness_status": "technical_preview_rc_phase1_ready",
        "summary": {
            "ready_evidence_count": 7,
            "total_evidence_count": 7,
            "next_spec_count": 0,
            "blocked_lanes_preserved": True,
        },
        "runtime_status_dashboard": {
            "schema": "runtime_status_dashboard.v1",
            "overall_status": "passed",
            "readiness_status": "runtime_status_dashboard_ready",
            "summary": {
                "ready_gates": 3,
                "total_gates": 3,
                "missing_source_reports": 0,
                "next_spec_count": 0,
                "blocked_lane_count": 2,
            },
            "lanes": {
                "live_capture": {
                    "status": "blocked",
                    "runtime_authority": "blocked_by_contract",
                }
            },
            "next_specs": [],
        },
        "authority_boundary": {
            "live_capture_enabled": False,
            "external_executor_auto_enabled": False,
            "dynamic_skill_registry_auto_write_enabled": False,
            "multimodal_model_auto_call_enabled": False,
            "frontend_semantics_owner": False,
            "persona_core_mutation_allowed": False,
            "memory_write_widened": False,
            "http_server_semantics_owner": False,
        },
        "failure_reasons": [],
    }


def _operator() -> dict:
    return {
        "schema": "operator_readback.v2",
        "overall_status": "passed",
        "readiness_status": "runtime_productization_phase2_ready",
        "safe_routes": {
            "read_only_routes": [
                "/api/runtime-productization",
                "/api/environment-summary",
                "/api/runtime-layout",
            ],
            "mutation_routes": [],
            "approval_required_for_external_mutation": True,
            "frontend_semantics_owner": False,
        },
        "authority_boundary": {
            "external_mutation_requires_approval": True,
            "memory_write_follows_existing_policy": True,
            "persona_core_mutation_allowed": False,
            "frontend_semantics_owner": False,
            "dynamic_registry_write_auto_allowed": False,
            "external_harness_runtime_auto_enabled": False,
            "live_capture_auto_enabled": False,
        },
        "evidence_summary": {
            "ready_inputs": 3,
            "total_inputs": 3,
            "missing_or_regressed_inputs": [],
        },
    }


def test_operator_console_rc_audit_passes_with_ready_rc_and_operator_readback():
    report = evaluate_operator_console_rc_phase1_audit(
        technical_preview_rc=_ready_rc(),
        operator_readback=_operator(),
    )

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "operator_console_rc_phase1_ready"
    assert report["operator_console_rc"]["schema"] == "operator_console_rc.v1"
    assert report["operator_console_rc_line"].startswith(
        "operator_console_rc=operator_console_rc_phase1_ready"
    )
    assert report["technical_preview_rc"]["readiness_status"] == "technical_preview_rc_phase1_ready"


def test_operator_console_rc_audit_blocks_when_rc_is_missing_or_regressed():
    rc = _ready_rc()
    rc["overall_status"] = "failed"
    rc["readiness_status"] = "technical_preview_rc_phase1_blocked"
    rc["failure_reasons"] = ["http_transport"]

    report = evaluate_operator_console_rc_phase1_audit(
        technical_preview_rc=rc,
        operator_readback=_operator(),
    )

    assert report["overall_status"] == "failed"
    assert report["readiness_status"] == "operator_console_rc_phase1_blocked"
    assert "technical_preview_rc_not_ready" in report["failure_reasons"]
    assert "http_transport" in report["failure_reasons"]


def test_operator_console_rc_markdown_lists_panels_and_authority_boundary():
    report = evaluate_operator_console_rc_phase1_audit(
        technical_preview_rc=_ready_rc(),
        operator_readback=_operator(),
    )

    markdown = render_markdown(report)

    assert "Operator Console RC Phase 1 Audit" in markdown
    assert "operator_console_rc_phase1_ready" in markdown
    assert "`rc_evidence`" in markdown
    assert "`authority_boundary`" in markdown
    assert "`live_capture_enabled`" in markdown
