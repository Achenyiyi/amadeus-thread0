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

from amadeus_thread0.runtime.runtime_status_dashboard import (  # noqa: E402
    build_runtime_status_dashboard,
    compact_runtime_status_line,
)
from amadeus_thread0.runtime.technical_preview_rc import (  # noqa: E402
    build_technical_preview_rc_readiness,
    compact_technical_preview_rc_line,
)


INPUT_SPECS = {
    "preserved_baselines": ("preserved-baselines-audit-", "preserved_baselines_ready"),
    "runtime_productization_phase3": (
        "runtime-productization-phase3-audit-",
        "runtime_productization_phase3_ready",
    ),
    "http_transport": ("http-transport-audit-", "http_transport_thin_wrapper_phase1_ready"),
    "approved_artifact_multimodal_runtime": (
        "approved-artifact-multimodal-runtime-phase1-audit-",
        "approved_artifact_multimodal_runtime_phase1_ready",
    ),
    "chinese_semantic_naturalness": (
        "chinese-semantic-naturalness-phase1-audit-",
        "chinese_semantic_naturalness_phase1_ready",
    ),
    "dynamic_skill_candidate_runtime": (
        "dynamic-skill-candidate-runtime-audit-",
        "dynamic_skill_candidate_runtime_phase1_ready",
    ),
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
        key: _load_latest_ready(Path(report_dir), prefix, expected)
        for key, (prefix, expected) in INPUT_SPECS.items()
    }


def _source_reports(inputs: dict[str, dict[str, Any]]) -> dict[str, str]:
    return {
        key: str(value.get("report_path") or "")
        for key, value in inputs.items()
        if str(value.get("report_path") or "")
    }


def evaluate_technical_preview_rc_phase1_audit(
    *,
    preserved_baselines: dict[str, Any] | None,
    runtime_productization_phase3: dict[str, Any] | None,
    http_transport: dict[str, Any] | None,
    approved_artifact_multimodal_runtime: dict[str, Any] | None,
    chinese_semantic_naturalness: dict[str, Any] | None,
    dynamic_skill_candidate_runtime: dict[str, Any] | None,
) -> dict[str, Any]:
    preserved = _dict_or_empty(preserved_baselines)
    productization = _dict_or_empty(runtime_productization_phase3)
    dashboard = build_runtime_status_dashboard(
        preserved_baselines=preserved,
        post_unlock_roadmap={"overall_status": "passed", "readiness_status": "post_unlock_roadmap_ready"},
        runtime_productization={
            "overall_status": "passed",
            "readiness_status": "runtime_productization_phase2_ready",
        },
        source_reports={
            "preserved_baselines": str(preserved.get("report_path") or ""),
            "post_unlock_roadmap": "embedded:post_unlock_roadmap_ready",
            "runtime_productization": "embedded:runtime_productization_phase2_ready",
        },
    )
    rc = build_technical_preview_rc_readiness(
        preserved_baselines=preserved,
        runtime_status_dashboard=dashboard,
        runtime_productization_phase3=productization,
        http_transport=http_transport,
        approved_artifact_multimodal_runtime=approved_artifact_multimodal_runtime,
        chinese_semantic_naturalness=chinese_semantic_naturalness,
        dynamic_skill_candidate_runtime=dynamic_skill_candidate_runtime,
    )
    report = dict(rc)
    report["runtime_status_dashboard"] = dashboard
    report["runtime_status_line"] = compact_runtime_status_line(dashboard)
    report["technical_preview_rc_line"] = compact_technical_preview_rc_line(rc)
    return report


def render_markdown(report: dict[str, Any]) -> str:
    summary = _dict_or_empty(report.get("summary"))
    lines = [
        "# Technical Preview RC Phase 1 Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Summary",
        "",
        f"- Evidence: `{summary.get('ready_evidence_count', 0)}/{summary.get('total_evidence_count', 0)}`",
        f"- Next specs: `{summary.get('next_spec_count', 0)}`",
        f"- Blocked lanes preserved: `{summary.get('blocked_lanes_preserved', False)}`",
        f"- Runtime status line: `{report.get('runtime_status_line', '')}`",
        f"- RC line: `{report.get('technical_preview_rc_line', '')}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Readiness | Expected | Report |",
        "| --- | --- | --- | --- | --- |",
    ]
    for key, row in _dict_or_empty(report.get("checks")).items():
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| `{key}` | `{row.get('status', '')}` | `{row.get('readiness_status', '')}` | "
            f"`{row.get('expected_readiness', '')}` | `{row.get('report_path', '')}` |"
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
    for key, value in _dict_or_empty(report.get("authority_boundary")).items():
        lines.append(f"| `{key}` | `{value}` |")
    failures = [str(reason) for reason in report.get("failure_reasons", []) if str(reason)]
    if failures:
        lines.extend(["", "## Failure Reasons", ""])
        lines.extend(f"- `{reason}`" for reason in failures)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Technical Preview RC Phase 1 audit.")
    parser.add_argument("--reports-dir", default=str(REPORT_DIR))
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    report_dir = Path(args.reports_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    inputs = load_input_reports(report_dir)
    report = evaluate_technical_preview_rc_phase1_audit(**inputs)
    report["source_reports"] = _source_reports(inputs)
    run_id = time.strftime("%Y%m%d-%H%M%S")
    if str(args.run_tag).strip():
        run_id = f"{run_id}-{str(args.run_tag).strip()}"
    json_path = report_dir / f"technical-preview-rc-phase1-audit-{run_id}.json"
    md_path = report_dir / f"technical-preview-rc-phase1-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[technical-preview-rc-phase1] json={json_path}")
    print(f"[technical-preview-rc-phase1] md={md_path}")
    print(f"[technical-preview-rc-phase1] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[technical-preview-rc-phase1] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
