from __future__ import annotations

from amadeus_thread0.runtime.runtime_productization import (
    RUNTIME_PRODUCTIZATION_READINESS,
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

    assert readback["readiness_status"] == RUNTIME_PRODUCTIZATION_READINESS
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

    assert "productization=runtime_productization_phase1_ready" in line
    assert "autonomy=assist" in line
    assert "packets=1" in line
    assert "bodyfx=browser_takeover_requested" in line
