from __future__ import annotations

import json
from pathlib import Path

from amadeus_thread0.runtime.advisor_demo_dry_run import (
    REQUIRED_ARCHIVE_MARKERS,
    REQUIRED_DEMO_SCENARIOS,
    REQUIRED_RUNBOOK_MARKERS,
)
from evals.run_advisor_demo_dry_run_phase1_audit import (
    evaluate_advisor_demo_dry_run_phase1_audit,
    load_asset_texts,
    load_latest_advisor_demo_readiness,
    render_markdown,
)


def _advisor_report(readiness: str = "advisor_demo_readiness_phase1_ready") -> dict:
    return {
        "schema": "advisor_demo_readiness.v1",
        "overall_status": "passed" if readiness == "advisor_demo_readiness_phase1_ready" else "failed",
        "readiness_status": readiness,
        "readiness_scope": "package_ready_not_live_demo_certification",
        "authority_boundary": {
            "live_capture_enabled": False,
            "external_executor_auto_enabled": False,
            "dynamic_skill_registry_auto_write_enabled": False,
            "multimodal_model_auto_call_enabled": False,
            "frontend_semantics_owner": False,
            "persona_core_mutation_allowed": False,
            "memory_write_widened": False,
            "http_server_semantics_owner": False,
        },
        "failure_reasons": [],
    }


def _write_advisor_report(report_dir: Path, stamp: str, report: dict) -> Path:
    path = report_dir / f"advisor-demo-readiness-phase1-audit-{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_required_assets(project_root: Path) -> None:
    scenario_text = "\n".join(
        f"{row['heading']}\n用户输入：\n预期信号：\n{row['representative_text']}"
        for row in REQUIRED_DEMO_SCENARIOS
    )
    corpus = "\n".join(
        [
            scenario_text,
            *REQUIRED_RUNBOOK_MARKERS,
            *REQUIRED_ARCHIVE_MARKERS,
        ]
    )
    for rel_path in [
        "docs/DEMO_SCRIPT.md",
        "docs/ADVISOR_REPRO_RUNBOOK.md",
        "docs/TECHNICAL_PREVIEW_CHECKLIST.md",
        "docs/FINAL_DELIVERY_MANIFEST.md",
    ]:
        path = project_root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{rel_path}\n{corpus}\n", encoding="utf-8")


def test_load_latest_advisor_demo_readiness_prefers_latest_ready_report(tmp_path: Path):
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    _write_advisor_report(report_dir, "20260507-100000-blocked", _advisor_report("advisor_demo_readiness_phase1_blocked"))
    ready = _write_advisor_report(report_dir, "20260507-110000-ready", _advisor_report())

    loaded = load_latest_advisor_demo_readiness(report_dir)

    assert loaded["readiness_status"] == "advisor_demo_readiness_phase1_ready"
    assert loaded["report_path"] == str(ready)


def test_advisor_demo_dry_run_audit_passes_with_ready_readiness_and_required_assets(tmp_path: Path):
    report_dir = tmp_path / "reports"
    project_root = tmp_path / "repo"
    report_dir.mkdir()
    project_root.mkdir()
    _write_advisor_report(report_dir, "20260507-110000-ready", _advisor_report())
    _write_required_assets(project_root)

    report = evaluate_advisor_demo_dry_run_phase1_audit(
        advisor_demo_readiness=load_latest_advisor_demo_readiness(report_dir),
        asset_texts=load_asset_texts(project_root),
    )

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "advisor_demo_dry_run_phase1_ready"
    assert report["summary"]["ready_scenario_count"] == len(REQUIRED_DEMO_SCENARIOS)
    assert report["advisor_demo_dry_run_line"].startswith(
        "advisor_demo_dry_run=advisor_demo_dry_run_phase1_ready"
    )


def test_advisor_demo_dry_run_markdown_lists_rehearsal_inventory():
    asset_texts = {
        "docs/DEMO_SCRIPT.md": "\n".join(
            f"{row['heading']}\n用户输入：\n预期信号：\n{row['representative_text']}"
            for row in REQUIRED_DEMO_SCENARIOS
        ),
        "docs/ADVISOR_REPRO_RUNBOOK.md": "\n".join(REQUIRED_RUNBOOK_MARKERS),
        "docs/TECHNICAL_PREVIEW_CHECKLIST.md": "\n".join(REQUIRED_ARCHIVE_MARKERS),
        "docs/FINAL_DELIVERY_MANIFEST.md": "\n".join(REQUIRED_ARCHIVE_MARKERS),
    }
    report = evaluate_advisor_demo_dry_run_phase1_audit(
        advisor_demo_readiness=_advisor_report(),
        asset_texts=asset_texts,
    )

    markdown = render_markdown(report)

    assert "# Advisor Demo Dry Run Phase 1 Audit" in markdown
    assert "advisor_demo_dry_run_phase1" in markdown
    assert "role_persona_consistency" in markdown
    assert "Advisor Demo Dry Run" in markdown
    assert "live_capture_enabled" in markdown
