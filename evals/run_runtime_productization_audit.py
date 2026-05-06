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

from amadeus_thread0.runtime.runtime_productization import (
    RUNTIME_PRODUCTIZATION_READINESS,
    build_runtime_productization_readback,
    evaluate_runtime_productization_contract,
)


REPORT_DIR = PROJECT_ROOT / "evals" / "reports"

INPUT_SPECS = {
    "post_baseline": ("post-baseline-closure-audit-", "post_baseline_closure_ready"),
    "preserved_baselines": ("preserved-baselines-audit-", "preserved_baselines_ready"),
    "post_unlock_roadmap": ("post-unlock-roadmap-audit-", "post_unlock_roadmap_ready"),
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


def _load_latest_ready(report_dir: Path, prefix: str, expected_readiness: str) -> dict[str, Any]:
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


def load_input_reports(report_dir: Path) -> dict[str, dict[str, Any]]:
    return {
        key: _load_latest_ready(report_dir, prefix, expected)
        for key, (prefix, expected) in INPUT_SPECS.items()
    }


def evaluate_runtime_productization_audit(inputs: dict[str, dict[str, Any]] | None) -> dict[str, Any]:
    rows = dict(inputs or {})
    readback = build_runtime_productization_readback(
        post_baseline_status=rows.get("post_baseline"),
        preserved_baselines=rows.get("preserved_baselines"),
        post_unlock_roadmap=rows.get("post_unlock_roadmap"),
        current_turn={},
    )
    contract = evaluate_runtime_productization_contract(readback)
    input_checks = []
    for key, (_, expected_readiness) in INPUT_SPECS.items():
        row = rows.get(key) or {}
        overall_status = str(row.get("overall_status") or "")
        readiness_status = _readiness(row)
        input_checks.append(
            {
                "id": key,
                "status": "passed"
                if overall_status == "passed" and readiness_status == expected_readiness
                else "failed",
                "overall_status": overall_status,
                "readiness_status": readiness_status,
                "expected_readiness": expected_readiness,
                "report_path": str(row.get("report_path") or ""),
            }
        )
    checks = [
        *input_checks,
        {
            "id": "runtime_productization_contract",
            "status": str(contract.get("overall_status") or ""),
            "readiness_status": str(contract.get("readiness_status") or ""),
            "expected_readiness": RUNTIME_PRODUCTIZATION_READINESS,
            "failure_reasons": list(contract.get("failure_reasons") or []),
        },
    ]
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": contract["overall_status"],
        "readiness_status": contract["readiness_status"],
        "inputs": {
            key: {
                "overall_status": str((rows.get(key) or {}).get("overall_status") or ""),
                "readiness_status": _readiness(rows.get(key) or {}),
                "report_path": str((rows.get(key) or {}).get("report_path") or ""),
            }
            for key in INPUT_SPECS
        },
        "checks": checks,
        "operator_readback": readback,
        "contract": contract,
    }


def render_markdown(report: dict[str, Any]) -> str:
    readback = report.get("operator_readback") if isinstance(report.get("operator_readback"), dict) else {}
    boundary = readback.get("authority_boundary") if isinstance(readback.get("authority_boundary"), dict) else {}
    lines = [
        "# Runtime Productization Phase 2 Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Inputs",
        "",
        "| Input | Overall | Readiness | Report |",
        "| --- | --- | --- | --- |",
    ]
    for key, row in (report.get("inputs") or {}).items():
        lines.append(
            f"| `{key}` | `{row.get('overall_status', '')}` | `{row.get('readiness_status', '')}` | `{row.get('report_path', '')}` |"
        )
    lines.extend(["", "## Checks", "", "| Check | Status | Readiness | Expected |", "| --- | --- | --- | --- |"])
    for row in report.get("checks") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| `{row.get('id', '')}` | `{row.get('status', '')}` | `{row.get('readiness_status', '')}` | `{row.get('expected_readiness', '')}` |"
        )
    lines.extend(
        [
            "",
            "## Authority Boundary",
            "",
            "| Boundary | Value |",
            "| --- | --- |",
        ]
    )
    for key, value in boundary.items():
        lines.append(f"| `{key}` | `{value}` |")
    failures = (report.get("contract") or {}).get("failure_reasons") if isinstance(report.get("contract"), dict) else []
    if failures:
        lines.extend(["", "## Failure Reasons", ""])
        lines.extend(f"- `{reason}`" for reason in failures)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run runtime productization phase 2 audit.")
    parser.add_argument("--reports-dir", default=str(REPORT_DIR))
    args = parser.parse_args()
    report_dir = Path(args.reports_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    report = evaluate_runtime_productization_audit(load_input_reports(report_dir))
    run_id = time.strftime("%Y%m%d-%H%M%S")
    json_path = report_dir / f"runtime-productization-phase2-audit-{run_id}.json"
    md_path = report_dir / f"runtime-productization-phase2-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[runtime-productization] json={json_path}")
    print(f"[runtime-productization] md={md_path}")
    print(f"[runtime-productization] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[runtime-productization] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
