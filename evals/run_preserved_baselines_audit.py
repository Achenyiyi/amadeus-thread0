from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "evals" / "reports"

BASELINE_SPECS = [
    {
        "id": "backend_freeze_gate",
        "prefix": "backend-freeze-gate-audit-",
        "expected_readiness": "freeze_gate_ready",
        "category": "core_loop",
    },
    {
        "id": "companion_autonomy",
        "prefix": "companion-autonomy-audit-",
        "expected_readiness": "companion_autonomy_ready",
        "category": "autonomy",
    },
    {
        "id": "digital_embodiment",
        "prefix": "digital-embodiment-audit-",
        "expected_readiness": "digital_embodiment_phase2_ready",
        "category": "embodiment",
    },
    {
        "id": "sandbox_embodied_execution",
        "prefix": "sandbox-embodied-execution-audit-",
        "expected_readiness": "sandbox_embodied_execution_phase1_ready",
        "category": "sandbox",
    },
    {
        "id": "skills_ecosystem",
        "prefix": "skills-ecosystem-audit-",
        "expected_readiness": "skills_ecosystem_ready",
        "category": "skills",
    },
    {
        "id": "dynamic_skills_phase2",
        "prefix": "dynamic-skills-phase2-audit-",
        "expected_readiness": "dynamic_skills_phase2_ready",
        "category": "skills",
    },
    {
        "id": "frontend_runtime_shell_phase2",
        "prefix": "frontend-runtime-shell-phase2-audit-",
        "expected_readiness": "frontend_runtime_shell_phase2_ready",
        "category": "frontend",
    },
    {
        "id": "live_browser_runtime",
        "prefix": "live-browser-runtime-audit-",
        "expected_readiness": "live_browser_runtime_phase1_ready",
        "category": "browser",
    },
    {
        "id": "sandbox_phase2",
        "prefix": "sandbox-phase2-audit-",
        "expected_readiness": "sandbox_embodied_execution_phase2_ready",
        "category": "sandbox",
    },
    {
        "id": "post_baseline_closure",
        "prefix": "post-baseline-closure-audit-",
        "expected_readiness": "post_baseline_closure_ready",
        "category": "post_baseline",
    },
    {
        "id": "tts_presence_timing",
        "prefix": "tts-presence-timing-audit-",
        "expected_readiness": "tts_presence_timing_ready",
        "category": "presence",
    },
    {
        "id": "procedural_growth_phase1",
        "prefix": "procedural-growth-audit-",
        "expected_readiness": "procedural_growth_phase1_ready",
        "category": "procedural_growth",
    },
    {
        "id": "procedural_growth_phase2",
        "prefix": "procedural-growth-phase2-audit-",
        "expected_readiness": "procedural_growth_phase2_ready",
        "category": "procedural_growth",
    },
    {
        "id": "procedural_growth_phase3",
        "prefix": "procedural-growth-phase3-audit-",
        "expected_readiness": "procedural_growth_phase3_ready",
        "category": "procedural_growth",
    },
    {
        "id": "procedural_growth_phase4",
        "prefix": "procedural-growth-phase4-audit-",
        "expected_readiness": "procedural_growth_phase4_ready",
        "category": "procedural_growth",
    },
    {
        "id": "post_unlock_roadmap",
        "prefix": "post-unlock-roadmap-audit-",
        "expected_readiness": "post_unlock_roadmap_ready",
        "category": "post_unlock",
    },
    {
        "id": "chinese_semantic_descaffolding_phase2",
        "prefix": "chinese-semantic-descaffolding-phase2-audit-",
        "expected_readiness": "chinese_semantic_descaffolding_phase2_ready",
        "category": "chinese_semantic",
    },
    {
        "id": "multimodal_perception_phase2",
        "prefix": "multimodal-perception-phase2-audit-",
        "expected_readiness": "multimodal_perception_phase2_ready",
        "category": "multimodal_perception",
    },
    {
        "id": "runtime_productization_phase1",
        "prefix": "runtime-productization-audit-",
        "expected_readiness": "runtime_productization_phase1_ready",
        "category": "productization",
    },
    {
        "id": "runtime_productization_phase2",
        "prefix": "runtime-productization-phase2-audit-",
        "expected_readiness": "runtime_productization_phase2_ready",
        "category": "productization",
    },
    {
        "id": "residual_living_loop_phase1",
        "prefix": "residual-living-loop-audit-",
        "expected_readiness": "residual_living_loop_phase1_ready",
        "category": "residual_closure",
    },
    {
        "id": "living_loop_runtime_realism_phase1",
        "prefix": "living-loop-realism-audit-",
        "expected_readiness": "living_loop_runtime_realism_phase1_ready",
        "category": "living_loop_realism",
    },
    {
        "id": "living_loop_runtime_realism_phase2",
        "prefix": "living-loop-realism-phase2-audit-",
        "expected_readiness": "living_loop_runtime_realism_phase2_ready",
        "category": "living_loop_realism",
    },
    {
        "id": "living_loop_runtime_realism_phase3",
        "prefix": "living-loop-realism-phase3-audit-",
        "expected_readiness": "living_loop_runtime_realism_phase3_ready",
        "category": "living_loop_realism",
    },
    {
        "id": "embodied_interaction_runtime_phase1",
        "prefix": "embodied-interaction-runtime-audit-",
        "expected_readiness": "embodied_interaction_runtime_phase1_ready",
        "category": "embodied_interaction",
    },
    {
        "id": "embodied_interaction_runtime_phase2",
        "prefix": "embodied-interaction-runtime-phase2-audit-",
        "expected_readiness": "embodied_interaction_runtime_phase2_ready",
        "category": "embodied_interaction",
    },
    {
        "id": "embodied_interaction_runtime_phase3",
        "prefix": "embodied-interaction-runtime-phase3-audit-",
        "expected_readiness": "embodied_interaction_runtime_phase3_ready",
        "category": "embodied_interaction",
    },
    {
        "id": "embodied_interaction_runtime_phase4",
        "prefix": "embodied-interaction-runtime-phase4-audit-",
        "expected_readiness": "embodied_interaction_runtime_phase4_ready",
        "category": "embodied_interaction",
    },
    {
        "id": "embodied_interaction_runtime_phase5",
        "prefix": "embodied-interaction-runtime-phase5-audit-",
        "expected_readiness": "embodied_interaction_runtime_phase5_ready",
        "category": "embodied_interaction",
    },
]

BASELINES = {str(spec["id"]): str(spec["prefix"]) for spec in BASELINE_SPECS}
EXPECTED_READY = {str(spec["id"]): str(spec["expected_readiness"]) for spec in BASELINE_SPECS}
BASELINE_CATEGORIES = {str(spec["id"]): str(spec["category"]) for spec in BASELINE_SPECS}


def _read_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Audit report is not a JSON object: {path}")
    row = dict(payload)
    row["report_path"] = str(path)
    return row


def _report_readiness(report: dict[str, Any]) -> str:
    readiness = report.get("readiness_status")
    if readiness is None:
        readiness = report.get("readiness")
    return str(readiness or "")


def load_latest_report(report_dir: Path, prefix: str, *, expected_readiness: str = "") -> dict:
    reports = sorted(Path(report_dir).glob(f"{prefix}*.json"))
    if not reports:
        raise FileNotFoundError(f"No audit reports found for prefix: {prefix}")
    if expected_readiness:
        for path in reversed(reports):
            payload = _read_report(path)
            if str(payload.get("overall_status") or "") == "passed" and _report_readiness(payload) == expected_readiness:
                return payload
    return _read_report(reports[-1])


def status_from_report(report: dict) -> dict:
    return {
        "run_id": str(report.get("run_id") or Path(str(report.get("report_path") or "")).stem),
        "generated_at": str(report.get("generated_at") or ""),
        "overall_status": str(report.get("overall_status") or ""),
        "readiness": _report_readiness(report),
        "report_path": str(report.get("report_path") or ""),
    }


def evaluate_preserved_baselines(statuses: dict[str, dict]) -> dict:
    rows: dict[str, dict[str, Any]] = {}
    categories: dict[str, dict[str, int]] = {}
    failed = 0
    for baseline in BASELINES:
        status = dict(statuses.get(baseline) or {})
        expected = EXPECTED_READY[baseline]
        category = BASELINE_CATEGORIES.get(baseline, "uncategorized")
        overall_status = str(status.get("overall_status") or "")
        readiness = str(status.get("readiness") or "")
        failure_reasons: list[str] = [str(reason) for reason in (status.get("failure_reasons") or []) if str(reason)]
        if overall_status != "passed":
            failure_reasons.append(f"overall_status={overall_status or 'missing'}")
        if readiness != expected:
            failure_reasons.append(f"readiness={readiness or 'missing'} expected={expected}")
        row_status = "passed" if not failure_reasons else "failed"
        if row_status == "failed":
            failed += 1
        category_row = categories.setdefault(category, {"total": 0, "passed": 0, "failed": 0})
        category_row["total"] += 1
        category_row[row_status] += 1
        rows[baseline] = {
            "category": category,
            "status": row_status,
            "overall_status": overall_status,
            "readiness": readiness,
            "expected_readiness": expected,
            "run_id": str(status.get("run_id") or ""),
            "generated_at": str(status.get("generated_at") or ""),
            "report_path": str(status.get("report_path") or ""),
            "source_error": str(status.get("failure") or status.get("source_error") or ""),
            "failure_reasons": failure_reasons,
        }
    total = len(BASELINES)
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": "passed" if failed == 0 else "failed",
        "readiness_status": "preserved_baselines_ready" if failed == 0 else "preserved_baselines_regressed",
        "summary": {"total": total, "passed": total - failed, "failed": failed, "categories": categories},
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
        "## Categories",
        "",
        "| Category | Total | Passed | Failed |",
        "| --- | ---: | ---: | ---: |",
    ]
    for category, row in (summary.get("summary", {}).get("categories") or {}).items():
        lines.append(
            f"| `{category}` | `{row.get('total', 0)}` | `{row.get('passed', 0)}` | `{row.get('failed', 0)}` |"
        )
    lines.extend([
        "",
        "## Baselines",
        "",
        "| Baseline | Category | Status | Overall | Readiness | Expected | Report |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ])
    for baseline, row in (summary.get("baselines") or {}).items():
        lines.append(
            f"| `{baseline}` | `{row.get('category', '')}` | `{row.get('status', '')}` | `{row.get('overall_status', '')}` | "
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


def load_statuses(report_dir: Path) -> dict[str, dict]:
    statuses: dict[str, dict] = {}
    for baseline, prefix in BASELINES.items():
        try:
            statuses[baseline] = status_from_report(
                load_latest_report(report_dir, prefix, expected_readiness=EXPECTED_READY[baseline])
            )
        except Exception as exc:
            statuses[baseline] = {
                "overall_status": "missing",
                "readiness": "",
                "report_path": "",
                "failure": str(exc),
                "failure_reasons": [f"missing_report:{prefix}"],
            }
    return statuses


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize the latest preserved baseline audit reports.")
    parser.add_argument("--reports-dir", default=str(REPORT_DIR))
    args = parser.parse_args()

    report_dir = Path(args.reports_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    summary = evaluate_preserved_baselines(load_statuses(report_dir))
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
