from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "evals" / "reports"

BASELINES = {
    "digital_embodiment": "digital-embodiment-audit-",
    "skills_ecosystem": "skills-ecosystem-audit-",
    "live_browser_runtime": "live-browser-runtime-audit-",
    "sandbox_phase2": "sandbox-phase2-audit-",
}

EXPECTED_READY = {
    "digital_embodiment": "digital_embodiment_phase2_ready",
    "skills_ecosystem": "skills_ecosystem_ready",
    "live_browser_runtime": "live_browser_runtime_phase1_ready",
    "sandbox_phase2": "sandbox_embodied_execution_phase2_ready",
}


def load_latest_report(report_dir: Path, prefix: str) -> dict:
    reports = sorted(Path(report_dir).glob(f"{prefix}*.json"))
    if not reports:
        raise FileNotFoundError(f"No audit reports found for prefix: {prefix}")
    path = reports[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Audit report is not a JSON object: {path}")
    payload = dict(payload)
    payload["report_path"] = str(path)
    return payload


def status_from_report(report: dict) -> dict:
    readiness = report.get("readiness_status")
    if readiness is None:
        readiness = report.get("readiness")
    return {
        "run_id": str(report.get("run_id") or Path(str(report.get("report_path") or "")).stem),
        "generated_at": str(report.get("generated_at") or ""),
        "overall_status": str(report.get("overall_status") or ""),
        "readiness": str(readiness or ""),
        "report_path": str(report.get("report_path") or ""),
    }


def evaluate_preserved_baselines(statuses: dict[str, dict]) -> dict:
    rows: dict[str, dict[str, Any]] = {}
    failed = 0
    for baseline in BASELINES:
        status = dict(statuses.get(baseline) or {})
        expected = EXPECTED_READY[baseline]
        overall_status = str(status.get("overall_status") or "")
        readiness = str(status.get("readiness") or "")
        failure_reasons: list[str] = []
        if overall_status != "passed":
            failure_reasons.append(f"overall_status={overall_status or 'missing'}")
        if readiness != expected:
            failure_reasons.append(f"readiness={readiness or 'missing'} expected={expected}")
        row_status = "passed" if not failure_reasons else "failed"
        if row_status == "failed":
            failed += 1
        rows[baseline] = {
            "status": row_status,
            "overall_status": overall_status,
            "readiness": readiness,
            "expected_readiness": expected,
            "run_id": str(status.get("run_id") or ""),
            "generated_at": str(status.get("generated_at") or ""),
            "report_path": str(status.get("report_path") or ""),
            "failure_reasons": failure_reasons,
        }
    total = len(BASELINES)
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": "passed" if failed == 0 else "failed",
        "readiness_status": "preserved_baselines_ready" if failed == 0 else "preserved_baselines_regressed",
        "summary": {"total": total, "passed": total - failed, "failed": failed},
        "baselines": rows,
    }


def render_markdown(summary: dict) -> str:
    lines = [
        "# Preserved Baselines Audit",
        "",
        f"Generated at: {summary.get('generated_at', '')}",
        f"Overall Status: `{summary.get('overall_status', 'unknown')}`",
        f"Readiness: `{summary.get('readiness_status', 'unknown')}`",
        "",
        "## Summary",
        "",
        f"- Total baselines: `{summary.get('summary', {}).get('total', 0)}`",
        f"- Passed: `{summary.get('summary', {}).get('passed', 0)}`",
        f"- Failed: `{summary.get('summary', {}).get('failed', 0)}`",
        "",
        "## Baselines",
        "",
        "| Baseline | Status | Overall | Readiness | Expected | Report |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for baseline, row in (summary.get("baselines") or {}).items():
        lines.append(
            f"| `{baseline}` | `{row.get('status', '')}` | `{row.get('overall_status', '')}` | "
            f"`{row.get('readiness', '')}` | `{row.get('expected_readiness', '')}` | "
            f"`{row.get('report_path', '')}` |"
        )
    failures = [
        (baseline, reason)
        for baseline, row in (summary.get("baselines") or {}).items()
        for reason in (row.get("failure_reasons") or [])
    ]
    if failures:
        lines.extend(["", "## Failures", ""])
        for baseline, reason in failures:
            lines.append(f"- `{baseline}`: `{reason}`")
    return "\n".join(lines) + "\n"


def _load_statuses(report_dir: Path) -> dict[str, dict]:
    statuses: dict[str, dict] = {}
    for baseline, prefix in BASELINES.items():
        try:
            statuses[baseline] = status_from_report(load_latest_report(report_dir, prefix))
        except Exception as exc:
            statuses[baseline] = {
                "overall_status": "missing",
                "readiness": "",
                "report_path": "",
                "failure": str(exc),
            }
    return statuses


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize the latest preserved baseline audit reports.")
    parser.add_argument("--reports-dir", default=str(REPORT_DIR))
    args = parser.parse_args()

    report_dir = Path(args.reports_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    summary = evaluate_preserved_baselines(_load_statuses(report_dir))
    run_id = time.strftime("%Y%m%d-%H%M%S")
    json_path = report_dir / f"preserved-baselines-audit-{run_id}.json"
    md_path = report_dir / f"preserved-baselines-audit-{run_id}.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(summary), encoding="utf-8")
    print(f"[preserved-baselines] json={json_path}")
    print(f"[preserved-baselines] md={md_path}")
    print(f"[preserved-baselines] overall_status={summary.get('overall_status', 'unknown')}")
    print(f"[preserved-baselines] readiness={summary.get('readiness_status', 'unknown')}")
    return 0 if str(summary.get("overall_status") or "") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
