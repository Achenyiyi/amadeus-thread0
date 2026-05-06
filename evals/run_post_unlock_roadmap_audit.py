from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

LANE_SPECS = {
    "multimodal_capture_phase1": ("multimodal-capture-audit-", "multimodal_capture_phase1_ready"),
    "dynamic_skills_phase1": ("dynamic-skills-audit-", "dynamic_skills_phase1_ready"),
    "external_executor_harness_phase1": ("external-executor-harness-audit-", "external_executor_harness_phase1_ready"),
    "frontend_runtime_shell_phase1": ("frontend-runtime-shell-audit-", "frontend_runtime_shell_phase1_ready"),
    "chinese_semantic_descaffolding_phase1": ("chinese-surface-de-scaffold-audit-", "chinese_semantic_descaffolding_phase1_ready"),
    "capability_growth_phase5": ("capability-growth-phase5-audit-", "capability_growth_phase5_ready"),
    "natural_long_horizon_calibration_phase1": ("natural-long-horizon-calibration-audit-", "natural_long_horizon_calibration_phase1_ready"),
}


def _readiness(report: dict[str, Any]) -> str:
    return str(report.get("readiness_status") or report.get("readiness") or "")


def evaluate_post_unlock_roadmap(statuses: dict[str, dict[str, Any]] | None) -> dict[str, Any]:
    rows: dict[str, dict[str, Any]] = {}
    ready_count = 0
    regressed = 0
    supplied = statuses or {}
    for lane, (_, expected) in LANE_SPECS.items():
        status = dict(supplied.get(lane) or {})
        if not status:
            state = "planned"
        elif str(status.get("overall_status") or "") == "passed" and _readiness(status) == expected:
            state = "ready"
            ready_count += 1
        elif str(status.get("overall_status") or "") == "failed":
            state = "regressed"
            regressed += 1
        else:
            state = "in_progress"
        rows[lane] = {
            "status": state,
            "overall_status": str(status.get("overall_status") or ""),
            "readiness_status": _readiness(status),
            "expected_readiness": expected,
            "report_path": str(status.get("report_path") or ""),
        }
    if ready_count == len(LANE_SPECS):
        overall = "passed"
        readiness = "post_unlock_roadmap_ready"
    elif regressed:
        overall = "failed"
        readiness = "post_unlock_roadmap_regressed"
    else:
        overall = "in_progress"
        readiness = "post_unlock_roadmap_in_progress"
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": overall,
        "readiness_status": readiness,
        "summary": {"total": len(rows), "ready": ready_count, "regressed": regressed},
        "lanes": rows,
    }


def _load_latest_reports(report_dir: Path) -> dict[str, dict[str, Any]]:
    statuses: dict[str, dict[str, Any]] = {}
    for lane, (prefix, _) in LANE_SPECS.items():
        reports = sorted(Path(report_dir).glob(f"{prefix}*.json"))
        if not reports:
            continue
        payload = json.loads(reports[-1].read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            row = dict(payload)
            row["report_path"] = str(reports[-1])
            statuses[lane] = row
    return statuses


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Post-Unlock Roadmap Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "| Lane | Status | Readiness |",
        "| --- | --- | --- |",
    ]
    for lane, row in (report.get("lanes") or {}).items():
        lines.append(f"| `{lane}` | `{row.get('status', '')}` | `{row.get('readiness_status', '')}` |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run post-unlock roadmap audit.")
    parser.add_argument("--reports-dir", default=str(REPORT_DIR))
    args = parser.parse_args()
    report_dir = Path(args.reports_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    report = evaluate_post_unlock_roadmap(_load_latest_reports(report_dir))
    run_id = time.strftime("%Y%m%d-%H%M%S")
    json_path = report_dir / f"post-unlock-roadmap-audit-{run_id}.json"
    md_path = report_dir / f"post-unlock-roadmap-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[post-unlock-roadmap] json={json_path}")
    print(f"[post-unlock-roadmap] md={md_path}")
    print(f"[post-unlock-roadmap] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[post-unlock-roadmap] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") in {"passed", "in_progress"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
