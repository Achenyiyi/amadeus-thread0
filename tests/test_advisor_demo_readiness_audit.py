from __future__ import annotations

import json
from pathlib import Path

from amadeus_thread0.runtime.advisor_demo_readiness import (
    REQUIRED_ASSETS,
    REQUIRED_COMMANDS,
    REQUIRED_DEMO_SIGNALS,
)
from evals.run_advisor_demo_readiness_phase1_audit import (
    evaluate_advisor_demo_readiness_phase1_audit,
    load_asset_texts,
    load_latest_operator_console_rc,
    render_markdown,
)


def _operator_report(readiness: str = "operator_console_rc_phase1_ready") -> dict:
    return {
        "schema": "operator_console_rc.v1",
        "overall_status": "passed" if readiness == "operator_console_rc_phase1_ready" else "failed",
        "readiness_status": readiness,
        "console_mode": "readback_only",
        "summary": {"demo_ready": readiness == "operator_console_rc_phase1_ready"},
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


def _write_operator_report(report_dir: Path, stamp: str, report: dict) -> Path:
    path = report_dir / f"operator-console-rc-phase1-audit-{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_required_assets(project_root: Path) -> None:
    corpus = "\n".join(
        [
            *REQUIRED_COMMANDS,
            *(signal["required_text"] for signal in REQUIRED_DEMO_SIGNALS),
        ]
    )
    for rel_path in REQUIRED_ASSETS:
        path = project_root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{rel_path}\n{corpus}\n", encoding="utf-8")


def test_load_latest_operator_console_rc_prefers_latest_ready_report(tmp_path: Path):
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    _write_operator_report(report_dir, "20260507-100000-blocked", _operator_report("operator_console_rc_phase1_blocked"))
    ready = _write_operator_report(report_dir, "20260507-110000-ready", _operator_report())

    loaded = load_latest_operator_console_rc(report_dir)

    assert loaded["readiness_status"] == "operator_console_rc_phase1_ready"
    assert loaded["report_path"] == str(ready)


def test_advisor_demo_readiness_audit_passes_with_ready_rc_and_required_assets(tmp_path: Path):
    report_dir = tmp_path / "reports"
    project_root = tmp_path / "repo"
    report_dir.mkdir()
    project_root.mkdir()
    _write_operator_report(report_dir, "20260507-110000-ready", _operator_report())
    _write_required_assets(project_root)

    report = evaluate_advisor_demo_readiness_phase1_audit(
        operator_console_rc=load_latest_operator_console_rc(report_dir),
        asset_texts=load_asset_texts(project_root),
    )

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "advisor_demo_readiness_phase1_ready"
    assert report["summary"]["ready_asset_count"] == len(REQUIRED_ASSETS)
    assert report["advisor_demo_readiness_line"].startswith(
        "advisor_demo_readiness=advisor_demo_readiness_phase1_ready"
    )


def test_advisor_demo_readiness_markdown_lists_assets_and_authority_boundary(tmp_path: Path):
    report = evaluate_advisor_demo_readiness_phase1_audit(
        operator_console_rc=_operator_report(),
        asset_texts={path: "\n".join(REQUIRED_COMMANDS) for path in REQUIRED_ASSETS},
    )

    markdown = render_markdown(report)

    assert "# Advisor Demo Readiness Phase 1 Audit" in markdown
    assert "advisor_demo_readiness_phase1" in markdown
    assert "docs/ADVISOR_REPRO_RUNBOOK.md" in markdown
    assert "live_capture_enabled" in markdown
