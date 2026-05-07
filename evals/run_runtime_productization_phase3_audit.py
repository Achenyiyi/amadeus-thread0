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

from amadeus_thread0.runtime.runtime_status_dashboard import build_runtime_status_dashboard


REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
RUNTIME_PRODUCTIZATION_PHASE3_READINESS = "runtime_productization_phase3_ready"

INPUT_SPECS = {
    "preserved_baselines": ("preserved-baselines-audit-", "preserved_baselines_ready"),
    "post_unlock_roadmap": ("post-unlock-roadmap-audit-", "post_unlock_roadmap_ready"),
    "runtime_productization": ("runtime-productization-phase2-audit-", "runtime_productization_phase2_ready"),
    "phase3_smokes": ("runtime-productization-phase3-smokes-", "runtime_productization_phase3_smokes_ready"),
}

AUTHORITY_BOUNDARY = {
    "http_server_semantics_owner": False,
    "frontend_semantics_owner": False,
    "live_capture_enabled": False,
    "multimodal_model_auto_call_enabled": False,
    "dynamic_skill_registry_auto_write_enabled": False,
    "external_executor_auto_enabled": False,
    "persona_core_mutation_allowed": False,
}


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


def _load_latest_ready(report_dir: Path, prefix: str, expected_readiness: str) -> dict[str, Any]:
    reports = sorted(report_dir.glob(f"{prefix}*.json"))
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


def _check_row(report: dict[str, Any], expected_readiness: str, source_report: str = "") -> dict[str, Any]:
    overall = str(report.get("overall_status") or "").strip() or "missing"
    readiness = _readiness(report)
    passed = overall == "passed" and readiness == expected_readiness
    return {
        "status": "passed" if passed else "failed",
        "overall_status": overall,
        "readiness_status": readiness,
        "expected_readiness": expected_readiness,
        "report_path": source_report or str(report.get("report_path") or ""),
        "failure_reasons": [str(reason) for reason in report.get("failure_reasons", []) if str(reason)],
    }


def evaluate_runtime_productization_phase3_audit(
    *,
    preserved_baselines: dict[str, Any] | None,
    post_unlock_roadmap: dict[str, Any] | None,
    runtime_productization: dict[str, Any] | None,
    smoke_report: dict[str, Any] | None,
    source_reports: dict[str, str] | None = None,
) -> dict[str, Any]:
    sources = dict(source_reports or {})
    preserved = _dict_or_empty(preserved_baselines)
    roadmap = _dict_or_empty(post_unlock_roadmap)
    productization = _dict_or_empty(runtime_productization)
    smokes = _dict_or_empty(smoke_report)
    dashboard = build_runtime_status_dashboard(
        preserved_baselines=preserved,
        post_unlock_roadmap=roadmap,
        runtime_productization=productization,
        source_reports=sources,
    )
    checks = {
        "preserved_baselines": _check_row(
            preserved, "preserved_baselines_ready", sources.get("preserved_baselines", "")
        ),
        "post_unlock_roadmap": _check_row(
            roadmap, "post_unlock_roadmap_ready", sources.get("post_unlock_roadmap", "")
        ),
        "runtime_productization": _check_row(
            productization,
            "runtime_productization_phase2_ready",
            sources.get("runtime_productization", ""),
        ),
        "phase3_smokes": _check_row(
            smokes,
            "runtime_productization_phase3_smokes_ready",
            sources.get("phase3_smokes", ""),
        ),
        "runtime_status_dashboard": {
            "status": "passed" if dashboard["overall_status"] == "passed" else "failed",
            "overall_status": dashboard["overall_status"],
            "readiness_status": dashboard["readiness_status"],
            "expected_readiness": "runtime_status_dashboard_ready",
            "report_path": "",
            "failure_reasons": [],
        },
    }
    failures = [
        key
        for key, row in checks.items()
        if str(row.get("status") or "") != "passed"
    ]
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": "failed" if failures else "passed",
        "readiness_status": (
            "runtime_productization_phase3_blocked"
            if failures
            else RUNTIME_PRODUCTIZATION_PHASE3_READINESS
        ),
        "checks": checks,
        "dashboard": dashboard,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "failure_reasons": failures,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Runtime Productization Phase 3 Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Readiness | Expected | Report |",
        "| --- | --- | --- | --- | --- |",
    ]
    for key, row in (report.get("checks") or {}).items():
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| `{key}` | `{row.get('status', '')}` | `{row.get('readiness_status', '')}` | "
            f"`{row.get('expected_readiness', '')}` | `{row.get('report_path', '')}` |"
        )
    dashboard = _dict_or_empty(report.get("dashboard"))
    summary = _dict_or_empty(dashboard.get("summary"))
    lines.extend(
        [
            "",
            "## Runtime Status Dashboard",
            "",
            f"- Readiness: `{dashboard.get('readiness_status', '')}`",
            f"- Gates: `{summary.get('ready_gates', 0)}/{summary.get('total_gates', 0)}`",
            f"- Next specs: `{summary.get('next_spec_count', 0)}`",
            f"- Blocked lanes: `{summary.get('blocked_lane_count', 0)}`",
            "",
            "## Authority Boundary",
            "",
            "| Boundary | Value |",
            "| --- | --- |",
        ]
    )
    for key, value in _dict_or_empty(report.get("authority_boundary")).items():
        lines.append(f"| `{key}` | `{value}` |")
    failures = [str(reason) for reason in report.get("failure_reasons", []) if str(reason)]
    if failures:
        lines.extend(["", "## Failure Reasons", ""])
        lines.extend(f"- `{reason}`" for reason in failures)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run runtime productization phase 3 audit.")
    parser.add_argument("--reports-dir", default=str(REPORT_DIR))
    args = parser.parse_args()
    report_dir = Path(args.reports_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    inputs = load_input_reports(report_dir)
    report = evaluate_runtime_productization_phase3_audit(
        preserved_baselines=inputs.get("preserved_baselines"),
        post_unlock_roadmap=inputs.get("post_unlock_roadmap"),
        runtime_productization=inputs.get("runtime_productization"),
        smoke_report=inputs.get("phase3_smokes"),
        source_reports={
            key: str(value.get("report_path") or "")
            for key, value in inputs.items()
            if str(value.get("report_path") or "")
        },
    )
    run_id = time.strftime("%Y%m%d-%H%M%S")
    json_path = report_dir / f"runtime-productization-phase3-audit-{run_id}.json"
    md_path = report_dir / f"runtime-productization-phase3-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[runtime-productization-phase3] json={json_path}")
    print(f"[runtime-productization-phase3] md={md_path}")
    print(f"[runtime-productization-phase3] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[runtime-productization-phase3] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
