from __future__ import annotations

from amadeus_thread0.runtime.advisor_demo_readiness import (
    ADVISOR_DEMO_READINESS_PHASE1_READY,
    REQUIRED_ASSETS,
    REQUIRED_COMMANDS,
    REQUIRED_DEMO_SIGNALS,
    build_advisor_demo_readiness,
    compact_advisor_demo_readiness_line,
)


def _operator_rc(*, live_capture_enabled: bool = False) -> dict:
    return {
        "schema": "operator_console_rc.v1",
        "overall_status": "passed",
        "readiness_status": "operator_console_rc_phase1_ready",
        "console_mode": "readback_only",
        "summary": {"demo_ready": True, "next_spec_count": 0},
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
    }


def _asset_texts() -> dict[str, str]:
    joined_commands = "\n".join(REQUIRED_COMMANDS)
    joined_signals = "\n".join(signal["required_text"] for signal in REQUIRED_DEMO_SIGNALS)
    return {
        path: f"{path}\n{joined_commands}\n{joined_signals}\n"
        for path in REQUIRED_ASSETS
    }


def test_advisor_demo_readiness_passes_when_rc_docs_commands_and_demo_signals_are_ready():
    report = build_advisor_demo_readiness(
        operator_console_rc=_operator_rc(),
        asset_texts=_asset_texts(),
    )

    assert report["schema"] == "advisor_demo_readiness.v1"
    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == ADVISOR_DEMO_READINESS_PHASE1_READY
    assert report["readiness_scope"] == "package_ready_not_live_demo_certification"
    assert report["summary"]["package_ready"] is True
    assert report["summary"]["ready_asset_count"] == len(REQUIRED_ASSETS)
    assert report["summary"]["ready_command_count"] == len(REQUIRED_COMMANDS)
    assert report["summary"]["ready_demo_signal_count"] == len(REQUIRED_DEMO_SIGNALS)
    assert report["live_demo_observed"] is False
    assert report["manual_demo_required"] is True
    assert "run_advisor_demo_readiness_audit" in report["next_actions"]


def test_advisor_demo_readiness_blocks_when_required_asset_is_missing():
    texts = _asset_texts()
    missing_path = REQUIRED_ASSETS[0]
    texts.pop(missing_path)

    report = build_advisor_demo_readiness(
        operator_console_rc=_operator_rc(),
        asset_texts=texts,
    )

    assert report["overall_status"] == "failed"
    assert report["readiness_status"] == "advisor_demo_readiness_phase1_blocked"
    assert f"missing_asset:{missing_path}" in report["failure_reasons"]
    assert report["asset_inventory"][missing_path]["status"] == "missing"


def test_advisor_demo_readiness_blocks_when_operator_authority_widens():
    report = build_advisor_demo_readiness(
        operator_console_rc=_operator_rc(live_capture_enabled=True),
        asset_texts=_asset_texts(),
    )

    assert report["overall_status"] == "failed"
    assert "authority_widened:live_capture" in report["failure_reasons"]
    assert report["authority_boundary"]["live_capture_enabled"] is True


def test_compact_advisor_demo_readiness_line_summarizes_package_scope():
    report = build_advisor_demo_readiness(
        operator_console_rc=_operator_rc(),
        asset_texts=_asset_texts(),
    )

    line = compact_advisor_demo_readiness_line(report)

    assert "advisor_demo_readiness=advisor_demo_readiness_phase1_ready" in line
    assert f"assets={len(REQUIRED_ASSETS)}/{len(REQUIRED_ASSETS)}" in line
    assert f"commands={len(REQUIRED_COMMANDS)}/{len(REQUIRED_COMMANDS)}" in line
    assert f"demo_signals={len(REQUIRED_DEMO_SIGNALS)}/{len(REQUIRED_DEMO_SIGNALS)}" in line
    assert "scope=package_ready_not_live_demo_certification" in line
