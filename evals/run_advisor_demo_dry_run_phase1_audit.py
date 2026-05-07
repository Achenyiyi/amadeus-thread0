from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from amadeus_thread0.runtime.advisor_demo_dry_run import (  # noqa: E402
    REQUIRED_ASSETS,
    build_advisor_demo_dry_run,
    compact_advisor_demo_dry_run_line,
)


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _readiness(report: dict[str, Any]) -> str:
    return str(report.get("readiness_status") or report.get("readiness") or "").strip()


def _read_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Audit report is not a JSON object: {path}")
    row = dict(payload)
    row["report_path"] = str(path)
    return row


def load_latest_advisor_demo_readiness(report_dir: Path) -> dict[str, Any]:
    reports = sorted(Path(report_dir).glob("advisor-demo-readiness-phase1-audit-*.json"))
    if not reports:
        return {
            "overall_status": "missing",
            "readiness_status": "",
            "failure_reasons": ["missing_report:advisor-demo-readiness-phase1-audit-"],
        }
    for path in reversed(reports):
        row = _read_report(path)
        if str(row.get("overall_status") or "") == "passed" and _readiness(row) == "advisor_demo_readiness_phase1_ready":
            return row
    return _read_report(reports[-1])


def load_asset_texts(project_root: Path) -> dict[str, str]:
    root = Path(project_root)
    texts: dict[str, str] = {}
    for rel_path in REQUIRED_ASSETS:
        path = root / rel_path
        if path.exists() and path.is_file():
            texts[rel_path] = path.read_text(encoding="utf-8")
    return texts


def evaluate_advisor_demo_dry_run_phase1_audit(
    *,
    advisor_demo_readiness: dict[str, Any] | None,
    asset_texts: dict[str, str] | None,
) -> dict[str, Any]:
    dry_run = build_advisor_demo_dry_run(
        advisor_demo_readiness=advisor_demo_readiness,
        asset_texts=asset_texts,
    )
    report = dict(dry_run)
    report["advisor_demo_dry_run"] = dry_run
    report["advisor_demo_readiness"] = _dict_or_empty(advisor_demo_readiness)
    report["advisor_demo_dry_run_line"] = compact_advisor_demo_dry_run_line(dry_run)
    report["failure_reasons"] = list(dry_run.get("failure_reasons") or [])
    return report


def render_markdown(report: dict[str, Any]) -> str:
    dry_run = _dict_or_empty(report.get("advisor_demo_dry_run")) or _dict_or_empty(report)
    summary = _dict_or_empty(dry_run.get("summary"))
    lines = [
        "# Advisor Demo Dry Run Phase 1 Audit",
        "",
        f"Generated at: {report.get('generated_at', dry_run.get('generated_at', ''))}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        f"Scope: `{dry_run.get('dry_run_scope', '')}`",
        "",
        "## Summary",
        "",
        f"- Dry run ready: `{summary.get('dry_run_ready', False)}`",
        f"- Advisor demo readiness ready: `{summary.get('advisor_demo_readiness_ready', False)}`",
        f"- Assets: `{summary.get('ready_asset_count', 0)}/{summary.get('total_asset_count', 0)}`",
        f"- Scenarios: `{summary.get('ready_scenario_count', 0)}/{summary.get('total_scenario_count', 0)}`",
        (
            "- Runbook markers: "
            f"`{summary.get('ready_runbook_marker_count', 0)}/"
            f"{summary.get('total_runbook_marker_count', 0)}`"
        ),
        (
            "- Archive markers: "
            f"`{summary.get('ready_archive_marker_count', 0)}/"
            f"{summary.get('total_archive_marker_count', 0)}`"
        ),
        f"- Dry-run line: `{report.get('advisor_demo_dry_run_line', '')}`",
        "",
        "## Demo Scenarios",
        "",
        "| Scenario | Status | Heading |",
        "| --- | --- | --- |",
    ]
    for scenario_id, row in _dict_or_empty(dry_run.get("demo_scenario_inventory")).items():
        if isinstance(row, dict):
            lines.append(f"| `{scenario_id}` | `{row.get('status', '')}` | `{row.get('heading', '')}` |")
    lines.extend(
        [
            "",
            "## Runbook Markers",
            "",
            "| Marker | Status |",
            "| --- | --- |",
        ]
    )
    for marker, row in _dict_or_empty(dry_run.get("runbook_inventory")).items():
        if isinstance(row, dict):
            lines.append(f"| `{marker}` | `{row.get('status', '')}` |")
    lines.extend(
        [
            "",
            "## Archive Markers",
            "",
            "| Marker | Status |",
            "| --- | --- |",
        ]
    )
    for marker, row in _dict_or_empty(dry_run.get("archive_inventory")).items():
        if isinstance(row, dict):
            lines.append(f"| `{marker}` | `{row.get('status', '')}` |")
    lines.extend(["", "## Authority Boundary", "", "| Boundary | Value |", "| --- | --- |"])
    for key, value in _dict_or_empty(dry_run.get("authority_boundary")).items():
        lines.append(f"| `{key}` | `{value}` |")
    failures = [str(reason) for reason in dry_run.get("failure_reasons", []) if str(reason)]
    if failures:
        lines.extend(["", "## Failure Reasons", ""])
        lines.extend(f"- `{reason}`" for reason in failures)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Advisor Demo Dry Run Phase 1 audit.")
    parser.add_argument("--reports-dir", default=str(REPORT_DIR))
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    report_dir = Path(args.reports_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    report = evaluate_advisor_demo_dry_run_phase1_audit(
        advisor_demo_readiness=load_latest_advisor_demo_readiness(report_dir),
        asset_texts=load_asset_texts(Path(args.project_root)),
    )
    run_id = time.strftime("%Y%m%d-%H%M%S")
    if str(args.run_tag).strip():
        run_id = f"{run_id}-{str(args.run_tag).strip()}"
    json_path = report_dir / f"advisor-demo-dry-run-phase1-audit-{run_id}.json"
    md_path = report_dir / f"advisor-demo-dry-run-phase1-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[advisor-demo-dry-run-phase1] json={json_path}")
    print(f"[advisor-demo-dry-run-phase1] md={md_path}")
    print(f"[advisor-demo-dry-run-phase1] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[advisor-demo-dry-run-phase1] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
