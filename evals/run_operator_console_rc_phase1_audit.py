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

from amadeus_thread0.runtime.operator_console_rc import (  # noqa: E402
    build_operator_console_rc_readback,
    compact_operator_console_rc_line,
)
from amadeus_thread0.runtime.runtime_productization import (  # noqa: E402
    build_runtime_productization_readback,
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


def _load_latest_ready(
    report_dir: Path,
    prefix: str,
    expected_readiness: str,
) -> dict[str, Any]:
    reports = sorted(Path(report_dir).glob(f"{prefix}*.json"))
    if not reports:
        return {
            "overall_status": "missing",
            "readiness_status": "",
            "failure_reasons": [f"missing_report:{prefix}"],
        }
    for path in reversed(reports):
        row = _read_report(path)
        if str(row.get("overall_status") or "") == "passed" and _readiness(row) == expected_readiness:
            return row
    return _read_report(reports[-1])


def load_latest_technical_preview_rc(report_dir: Path) -> dict[str, Any]:
    return _load_latest_ready(
        Path(report_dir),
        "technical-preview-rc-phase1-audit-",
        "technical_preview_rc_phase1_ready",
    )


def _default_operator_readback() -> dict[str, Any]:
    return build_runtime_productization_readback(
        post_baseline_status={
            "overall_status": "passed",
            "readiness_status": "post_baseline_closure_ready",
        },
        preserved_baselines={
            "overall_status": "passed",
            "readiness_status": "preserved_baselines_ready",
        },
        post_unlock_roadmap={
            "overall_status": "passed",
            "readiness_status": "post_unlock_roadmap_ready",
        },
        current_turn={},
    )


def evaluate_operator_console_rc_phase1_audit(
    *,
    technical_preview_rc: dict[str, Any] | None,
    operator_readback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rc = _dict_or_empty(technical_preview_rc)
    dashboard = _dict_or_empty(rc.get("runtime_status_dashboard"))
    operator = _dict_or_empty(operator_readback) or _default_operator_readback()
    console = build_operator_console_rc_readback(
        technical_preview_rc=rc,
        runtime_status_dashboard=dashboard,
        operator_readback=operator,
    )
    report = dict(console)
    report["technical_preview_rc"] = rc
    report["runtime_status_dashboard"] = dashboard
    report["operator_readback"] = operator
    report["operator_console_rc"] = console
    report["operator_console_rc_line"] = compact_operator_console_rc_line(console)
    report["failure_reasons"] = list(console.get("failure_reasons") or [])
    return report


def render_markdown(report: dict[str, Any]) -> str:
    console = _dict_or_empty(report.get("operator_console_rc")) or _dict_or_empty(report)
    summary = _dict_or_empty(console.get("summary"))
    lines = [
        "# Operator Console RC Phase 1 Audit",
        "",
        f"Generated at: {report.get('generated_at', console.get('generated_at', ''))}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Summary",
        "",
        f"- Demo ready: `{summary.get('demo_ready', False)}`",
        f"- Evidence: `{summary.get('ready_evidence_count', 0)}/{summary.get('total_evidence_count', 0)}`",
        f"- Gates: `{summary.get('ready_gates', 0)}/{summary.get('total_gates', 0)}`",
        f"- Next specs: `{summary.get('next_spec_count', 0)}`",
        f"- Routes: `{summary.get('route_count', 0)}`",
        f"- Console line: `{report.get('operator_console_rc_line', '')}`",
        "",
        "## Panels",
        "",
        "| Panel | Status |",
        "| --- | --- |",
    ]
    for key, row in _dict_or_empty(console.get("operator_panels")).items():
        if isinstance(row, dict):
            lines.append(f"| `{key}` | `{row.get('status', '')}` |")
    lines.extend(["", "## Authority Boundary", "", "| Boundary | Value |", "| --- | --- |"])
    for key, value in _dict_or_empty(console.get("authority_boundary")).items():
        lines.append(f"| `{key}` | `{value}` |")
    failures = [str(reason) for reason in console.get("failure_reasons", []) if str(reason)]
    if failures:
        lines.extend(["", "## Failure Reasons", ""])
        lines.extend(f"- `{reason}`" for reason in failures)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Operator Console RC Phase 1 audit.")
    parser.add_argument("--reports-dir", default=str(REPORT_DIR))
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    report_dir = Path(args.reports_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    technical_preview_rc = load_latest_technical_preview_rc(report_dir)
    report = evaluate_operator_console_rc_phase1_audit(
        technical_preview_rc=technical_preview_rc,
        operator_readback=_default_operator_readback(),
    )
    run_id = time.strftime("%Y%m%d-%H%M%S")
    if str(args.run_tag).strip():
        run_id = f"{run_id}-{str(args.run_tag).strip()}"
    json_path = report_dir / f"operator-console-rc-phase1-audit-{run_id}.json"
    md_path = report_dir / f"operator-console-rc-phase1-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[operator-console-rc-phase1] json={json_path}")
    print(f"[operator-console-rc-phase1] md={md_path}")
    print(f"[operator-console-rc-phase1] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[operator-console-rc-phase1] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
