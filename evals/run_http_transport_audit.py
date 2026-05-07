from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from amadeus_thread0.runtime.http_transport import HTTP_TRANSPORT_AUTHORITY_BOUNDARY


REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
HTTP_TRANSPORT_READINESS = "http_transport_thin_wrapper_phase1_ready"
HTTP_TRANSPORT_SMOKE_READINESS = "http_transport_thin_wrapper_phase1_smokes_ready"

REQUIRED_BOUNDARY = {
    "transport_role": "thin_wrapper",
    "backend_semantics_owner": False,
    "frontend_semantics_owner": False,
    "sse_or_websocket_streaming_enabled": False,
}


def _readiness(report: dict[str, Any]) -> str:
    return str(report.get("readiness_status") or report.get("readiness") or "").strip()


def _read_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Audit report is not a JSON object: {path}")
    row = dict(payload)
    row["report_path"] = str(path)
    return row


def load_latest_smoke_report(report_dir: Path) -> dict[str, Any]:
    reports = sorted(Path(report_dir).glob("http-transport-smokes-*.json"))
    if not reports:
        return {
            "overall_status": "missing",
            "readiness_status": "",
            "failure_reasons": ["missing_report:http-transport-smokes-"],
        }
    for path in reversed(reports):
        row = _read_report(path)
        if str(row.get("overall_status") or "") == "passed" and _readiness(row) == HTTP_TRANSPORT_SMOKE_READINESS:
            return row
    return _read_report(reports[-1])


def _check_smoke_readiness(smoke_report: dict[str, Any]) -> dict[str, Any]:
    overall = str(smoke_report.get("overall_status") or "").strip() or "missing"
    readiness = _readiness(smoke_report)
    passed = overall == "passed" and readiness == HTTP_TRANSPORT_SMOKE_READINESS
    return {
        "status": "passed" if passed else "failed",
        "overall_status": overall,
        "readiness_status": readiness,
        "expected_readiness": HTTP_TRANSPORT_SMOKE_READINESS,
        "report_path": str(smoke_report.get("report_path") or ""),
        "failure_reasons": [str(reason) for reason in smoke_report.get("failure_reasons", []) if str(reason)],
    }


def _check_authority_boundary(smoke_report: dict[str, Any]) -> dict[str, Any]:
    boundary = dict(HTTP_TRANSPORT_AUTHORITY_BOUNDARY)
    if isinstance(smoke_report.get("authority_boundary"), dict):
        boundary.update(smoke_report["authority_boundary"])
    failures: list[str] = []
    for key, expected in REQUIRED_BOUNDARY.items():
        if boundary.get(key) != expected:
            failures.append(f"{key}={boundary.get(key)!r} expected={expected!r}")
    return {
        "status": "passed" if not failures else "failed",
        "expected": dict(REQUIRED_BOUNDARY),
        "actual": boundary,
        "failure_reasons": failures,
    }


def evaluate_http_transport_audit(smoke_report: dict[str, Any] | None) -> dict[str, Any]:
    smoke = dict(smoke_report or {})
    checks = {
        "smoke_readiness": _check_smoke_readiness(smoke),
        "authority_boundary": _check_authority_boundary(smoke),
    }
    failures = [key for key, row in checks.items() if row["status"] != "passed"]
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": "failed" if failures else "passed",
        "readiness_status": "http_transport_thin_wrapper_phase1_blocked"
        if failures
        else HTTP_TRANSPORT_READINESS,
        "checks": checks,
        "authority_boundary": checks["authority_boundary"]["actual"],
        "failure_reasons": failures,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# HTTP Transport Thin Wrapper Phase 1 Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Readiness | Expected |",
        "| --- | --- | --- | --- |",
    ]
    for key, row in (report.get("checks") or {}).items():
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| `{key}` | `{row.get('status', '')}` | `{row.get('readiness_status', '')}` | `{row.get('expected_readiness', '')}` |"
        )
    lines.extend(["", "## Authority Boundary", "", "| Boundary | Value |", "| --- | --- |"])
    for key, value in (report.get("authority_boundary") or {}).items():
        lines.append(f"| `{key}` | `{value}` |")
    failures = [str(reason) for reason in report.get("failure_reasons", []) if str(reason)]
    if failures:
        lines.extend(["", "## Failure Reasons", ""])
        lines.extend(f"- `{reason}`" for reason in failures)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run HTTP transport thin-wrapper phase 1 audit.")
    parser.add_argument("--reports-dir", default=str(REPORT_DIR))
    args = parser.parse_args()
    report_dir = Path(args.reports_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    report = evaluate_http_transport_audit(load_latest_smoke_report(report_dir))
    run_id = time.strftime("%Y%m%d-%H%M%S")
    json_path = report_dir / f"http-transport-audit-{run_id}.json"
    md_path = report_dir / f"http-transport-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[http-transport-audit] json={json_path}")
    print(f"[http-transport-audit] md={md_path}")
    print(f"[http-transport-audit] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[http-transport-audit] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
