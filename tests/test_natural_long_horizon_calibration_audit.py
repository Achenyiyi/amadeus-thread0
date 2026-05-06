from __future__ import annotations

from pathlib import Path

from evals.run_natural_long_horizon_calibration_audit import (
    evaluate_calibration_results,
    load_calibration_bank,
)


def test_calibration_bank_contains_required_packs():
    bank = load_calibration_bank(Path("evals/long_horizon_calibration_bank.json"))
    assert set(bank["packs"]) >= {
        "everyday_low_stakes_7_turns",
        "repair_after_tension_9_turns",
        "self_rhythm_boundary_8_turns",
        "shared_work_continuity_10_turns",
        "embodied_artifact_resume_8_turns",
        "silence_and_deferred_return_6_turns",
    }


def test_audit_fails_on_middle_state_leak():
    report = evaluate_calibration_results(
        [{"pack": "repair_after_tension_9_turns", "middle_state_leak": True}]
    )
    assert report["overall_status"] == "failed"
    assert "middle_state_leak" in report["failure_reasons"]
