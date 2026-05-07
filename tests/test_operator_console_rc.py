from __future__ import annotations

from amadeus_thread0.runtime.operator_console_rc import (
    OPERATOR_CONSOLE_RC_PHASE1_READY,
    build_operator_console_rc_readback,
    compact_operator_console_rc_line,
)


def _rc(*, next_specs: int = 0, live_capture_enabled: bool = False) -> dict:
    return {
        "schema": "technical_preview_rc.v1",
        "overall_status": "passed",
        "readiness_status": "technical_preview_rc_phase1_ready",
        "summary": {
            "ready_evidence_count": 7,
            "total_evidence_count": 7,
            "next_spec_count": next_specs,
            "blocked_lanes_preserved": not live_capture_enabled,
        },
        "authority_boundary": {
            "live_capture_enabled": live_capture_enabled,
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


def _dashboard(*, next_specs: int = 0) -> dict:
    return {
        "schema": "runtime_status_dashboard.v1",
        "overall_status": "passed",
        "readiness_status": "runtime_status_dashboard_ready",
        "summary": {
            "ready_gates": 3,
            "total_gates": 3,
            "missing_source_reports": 0,
            "next_spec_count": next_specs,
            "blocked_lane_count": 2,
        },
        "lanes": {
            "frontend_runtime_shell": {
                "status": "phase2_ready",
                "runtime_authority": "consumer_only",
            },
            "live_capture": {
                "status": "blocked",
                "runtime_authority": "blocked_by_contract",
            },
            "dynamic_skill_generation": {
                "status": "phase1_ready",
                "runtime_authority": "readback_audit_only",
            },
        },
        "next_specs": [{"id": "future"}] if next_specs else [],
    }


def _operator() -> dict:
    return {
        "schema": "operator_readback.v2",
        "overall_status": "passed",
        "readiness_status": "runtime_productization_phase2_ready",
        "console_summary": {
            "health": "ready",
            "mode": "readback_only",
            "next_action": "monitor_runtime_readback",
            "pending_approval_count": 0,
        },
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


def test_operator_console_rc_ready_when_rc_dashboard_and_operator_readbacks_are_closed():
    report = build_operator_console_rc_readback(
        technical_preview_rc=_rc(),
        runtime_status_dashboard=_dashboard(),
        operator_readback=_operator(),
    )

    assert report["schema"] == "operator_console_rc.v1"
    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == OPERATOR_CONSOLE_RC_PHASE1_READY
    assert report["console_mode"] == "readback_only"
    assert report["release_posture"] == "technical_preview_rc"
    assert report["summary"]["demo_ready"] is True
    assert report["summary"]["ready_evidence_count"] == 7
    assert report["summary"]["route_count"] == 3
    assert report["readback_refs"]["technical_preview_rc"]["schema"] == "technical_preview_rc.v1"
    assert report["operator_panels"]["rc_evidence"]["status"] == "passed"
    assert report["operator_panels"]["authority_boundary"]["status"] == "passed"
    assert report["route_inventory"]["mutation_routes"] == []
    assert report["authority_boundary"]["live_capture_enabled"] is False
    assert "open_operator_console" in report["next_actions"]


def test_operator_console_rc_fails_closed_when_next_specs_are_open():
    report = build_operator_console_rc_readback(
        technical_preview_rc=_rc(next_specs=1),
        runtime_status_dashboard=_dashboard(next_specs=1),
        operator_readback=_operator(),
    )

    assert report["overall_status"] == "failed"
    assert report["readiness_status"] == "operator_console_rc_phase1_blocked"
    assert report["summary"]["demo_ready"] is False
    assert "next_specs_not_empty" in report["failure_reasons"]
    assert report["operator_panels"]["runtime_status"]["status"] == "failed"


def test_operator_console_rc_fails_closed_when_blocked_authority_widens():
    report = build_operator_console_rc_readback(
        technical_preview_rc=_rc(live_capture_enabled=True),
        runtime_status_dashboard=_dashboard(),
        operator_readback=_operator(),
    )

    assert report["overall_status"] == "failed"
    assert report["readiness_status"] == "operator_console_rc_phase1_blocked"
    assert "authority_widened:live_capture" in report["failure_reasons"]
    assert report["operator_panels"]["authority_boundary"]["status"] == "failed"


def test_compact_operator_console_rc_line_is_short_and_actionable():
    report = build_operator_console_rc_readback(
        technical_preview_rc=_rc(),
        runtime_status_dashboard=_dashboard(),
        operator_readback=_operator(),
    )

    line = compact_operator_console_rc_line(report)

    assert "operator_console_rc=operator_console_rc_phase1_ready" in line
    assert "demo_ready=True" in line
    assert "evidence=7/7" in line
    assert "next_specs=0" in line
    assert "routes=3" in line
