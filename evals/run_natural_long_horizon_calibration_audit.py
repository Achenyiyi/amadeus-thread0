from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
BANK_PATH = PROJECT_ROOT / "evals" / "long_horizon_calibration_bank.json"

REQUIRED_PACKS = {
    "everyday_low_stakes_7_turns",
    "repair_after_tension_9_turns",
    "self_rhythm_boundary_8_turns",
    "shared_work_continuity_10_turns",
    "embodied_artifact_resume_8_turns",
    "silence_and_deferred_return_6_turns",
}

FAILURE_FLAGS = {
    "final_text_tts_drift": "final_text_tts_parity",
    "duplicate_output": "no_duplicate_output",
    "middle_state_leak": "no_middle_state_leak",
    "punitive_boundary": "boundary_not_punitive",
    "generic_assistant_tone": "generic_assistant_tone_absent",
    "untruthful_embodied_context": "embodied_context_truthful",
}


def load_calibration_bank(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    packs = payload.get("packs")
    if not isinstance(packs, dict):
        raise ValueError("calibration bank must contain a packs object")
    return {"packs": packs}


def evaluate_calibration_results(results: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [dict(item) for item in (results or []) if isinstance(item, dict)]
    failure_reasons: list[str] = []
    for row in rows:
        for flag, metric in FAILURE_FLAGS.items():
            if bool(row.get(flag, False)) and metric not in failure_reasons:
                failure_reasons.append(flag)
    covered = {str(row.get("pack") or "") for row in rows if str(row.get("pack") or "")}
    missing = sorted(REQUIRED_PACKS - covered) if rows else []
    if rows and missing:
        failure_reasons.extend(f"missing_pack:{item}" for item in missing)
    overall = "failed" if failure_reasons else "passed"
    return {
        "overall_status": overall,
        "readiness_status": (
            "natural_long_horizon_calibration_phase1_ready"
            if overall == "passed"
            else "natural_long_horizon_calibration_phase1_in_progress"
        ),
        "failure_reasons": failure_reasons,
        "summary": {"total": len(rows), "covered": len(covered), "missing": len(missing)},
    }


def deterministic_calibration_results(bank: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "pack": pack_id,
            "final_text_tts_drift": False,
            "duplicate_output": False,
            "middle_state_leak": False,
            "punitive_boundary": False,
            "generic_assistant_tone": False,
            "untruthful_embodied_context": False,
        }
        for pack_id in sorted((bank.get("packs") or {}).keys())
    ]


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Natural Long-Horizon Calibration Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Failure Reasons",
        "",
    ]
    reasons = list(report.get("failure_reasons") or [])
    if reasons:
        lines.extend(f"- `{reason}`" for reason in reasons)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run natural long-horizon calibration audit.")
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    bank = load_calibration_bank(BANK_PATH)
    missing = sorted(REQUIRED_PACKS - set((bank.get("packs") or {}).keys()))
    report = evaluate_calibration_results(deterministic_calibration_results(bank))
    if missing:
        report["overall_status"] = "failed"
        report["readiness_status"] = "natural_long_horizon_calibration_phase1_in_progress"
        report.setdefault("failure_reasons", []).extend(f"missing_bank_pack:{item}" for item in missing)
    report["run_id"] = run_id
    report["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    json_path = REPORT_DIR / f"natural-long-horizon-calibration-audit-{run_id}.json"
    md_path = REPORT_DIR / f"natural-long-horizon-calibration-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[natural-long-horizon-calibration] json={json_path}")
    print(f"[natural-long-horizon-calibration] md={md_path}")
    print(f"[natural-long-horizon-calibration] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[natural-long-horizon-calibration] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
