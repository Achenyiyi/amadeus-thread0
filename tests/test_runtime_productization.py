from __future__ import annotations

from amadeus_thread0.runtime.runtime_productization import (
    RUNTIME_PRODUCTIZATION_READINESS,
    RUNTIME_PRODUCTIZATION_PHASE1_READINESS,
    RUNTIME_PRODUCTIZATION_PHASE2_READINESS,
    build_runtime_productization_readback,
    compact_operator_readback_line,
    evaluate_runtime_productization_contract,
)


def test_readback_reports_ready_lanes_without_widening_authority():
    readback = build_runtime_productization_readback(
        post_baseline_status={
            "overall_status": "passed",
            "readiness_status": "post_baseline_closure_ready",
            "items": {
                "multimodal_input_capture": {"status": "implemented_ready", "runtime_available": True},
                "dynamic_skill_generation": {"status": "implemented_ready", "runtime_available": False},
                "external_executor_harnesses": {"status": "implemented_ready", "runtime_available": False},
                "frontend_runtime_shell": {"status": "implemented_ready", "runtime_available": True},
            },
        },
        preserved_baselines={"overall_status": "passed", "readiness_status": "preserved_baselines_ready"},
        post_unlock_roadmap={"overall_status": "passed", "readiness_status": "post_unlock_roadmap_ready"},
        current_turn={
            "autonomy_mode": "assist",
            "action_packet_count": 2,
            "digital_body_consequence_kind": "sandbox_execution_completed",
            "procedural_recovery": {"recovery_kind": "adjust_bounded_command"},
        },
    )

    assert RUNTIME_PRODUCTIZATION_PHASE1_READINESS == "runtime_productization_phase1_ready"
    assert RUNTIME_PRODUCTIZATION_READINESS == RUNTIME_PRODUCTIZATION_PHASE2_READINESS
    assert readback["schema"] == "operator_readback.v2"
    assert readback["readiness_status"] == "runtime_productization_phase2_ready"
    assert readback["console_summary"]["health"] == "ready"
    assert readback["console_summary"]["mode"] == "readback_only"
    assert readback["console_summary"]["next_action"] == "monitor_runtime_readback"
    assert readback["evidence_summary"]["ready_inputs"] == 3
    assert readback["safe_routes"]["read_only_routes"] == [
        "/api/runtime-productization",
        "/api/environment-summary",
        "/api/runtime-layout",
    ]
    assert readback["authority_boundary"]["external_mutation_requires_approval"] is True
    assert readback["authority_boundary"]["persona_core_mutation_allowed"] is False
    assert readback["lanes"]["dynamic_skill_generation"]["runtime_available"] is False
    assert readback["operator_snapshot"]["action_packet_count"] == 2
    assert readback["operator_snapshot"]["procedural_recovery_kind"] == "adjust_bounded_command"


def test_contract_fails_when_preserved_baselines_are_not_ready():
    readback = build_runtime_productization_readback(
        post_baseline_status={"overall_status": "passed", "readiness_status": "post_baseline_closure_ready", "items": {}},
        preserved_baselines={"overall_status": "failed", "readiness_status": "preserved_baselines_regressed"},
        post_unlock_roadmap={"overall_status": "passed", "readiness_status": "post_unlock_roadmap_ready"},
    )

    contract = evaluate_runtime_productization_contract(readback)

    assert contract["overall_status"] == "failed"
    assert "preserved_baselines_ready" in contract["failure_reasons"][0]


def test_compact_operator_readback_line_is_short_and_actionable():
    readback = build_runtime_productization_readback(
        post_baseline_status={"overall_status": "passed", "readiness_status": "post_baseline_closure_ready", "items": {}},
        preserved_baselines={"overall_status": "passed", "readiness_status": "preserved_baselines_ready"},
        post_unlock_roadmap={"overall_status": "passed", "readiness_status": "post_unlock_roadmap_ready"},
        current_turn={
            "autonomy_mode": "assist",
            "action_packet_count": 1,
            "digital_body_consequence_kind": "browser_takeover_requested",
        },
    )

    line = compact_operator_readback_line(readback)

    assert "productization=runtime_productization_phase2_ready" in line
    assert "console=ready" in line
    assert "next=monitor_runtime_readback" in line
    assert "autonomy=assist" in line
    assert "packets=1" in line
    assert "bodyfx=browser_takeover_requested" in line


def test_console_next_action_surfaces_pending_operator_approval():
    readback = build_runtime_productization_readback(
        post_baseline_status={"overall_status": "passed", "readiness_status": "post_baseline_closure_ready", "items": {}},
        preserved_baselines={"overall_status": "passed", "readiness_status": "preserved_baselines_ready"},
        post_unlock_roadmap={"overall_status": "passed", "readiness_status": "post_unlock_roadmap_ready"},
        current_turn={
            "autonomy_mode": "assist",
            "digital_body_pending_approval_count": 2,
        },
    )

    line = compact_operator_readback_line(readback)

    assert readback["console_summary"]["next_action"] == "resolve_pending_operator_approval"
    assert "pending_approvals=2" in line
