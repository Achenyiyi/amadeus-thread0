from __future__ import annotations

import json
from pathlib import Path

from evals.run_technical_preview_rc_phase1_audit import (
    evaluate_technical_preview_rc_phase1_audit,
    load_input_reports,
    render_markdown,
)


def _write_report(report_dir: Path, prefix: str, readiness: str, *, stamp: str = "ready") -> Path:
    path = report_dir / f"{prefix}20260507-150000-{stamp}.json"
    path.write_text(
        json.dumps(
            {
                "overall_status": "passed",
                "readiness_status": readiness,
                "report_path": str(path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def test_audit_loads_latest_ready_reports_and_passes(tmp_path: Path):
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    _write_report(report_dir, "preserved-baselines-audit-", "preserved_baselines_ready")
    _write_report(report_dir, "runtime-productization-phase3-audit-", "runtime_productization_phase3_ready")
    _write_report(report_dir, "http-transport-audit-", "http_transport_thin_wrapper_phase1_ready")
    _write_report(
        report_dir,
        "approved-artifact-multimodal-runtime-phase1-audit-",
        "approved_artifact_multimodal_runtime_phase1_ready",
    )
    _write_report(
        report_dir,
        "chinese-semantic-naturalness-phase1-audit-",
        "chinese_semantic_naturalness_phase1_ready",
    )
    _write_report(
        report_dir,
        "dynamic-skill-candidate-runtime-audit-",
        "dynamic_skill_candidate_runtime_phase1_ready",
    )

    inputs = load_input_reports(report_dir)
    report = evaluate_technical_preview_rc_phase1_audit(**inputs)

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "technical_preview_rc_phase1_ready"
    assert report["summary"]["ready_evidence_count"] == 7
    assert report["runtime_status_line"].startswith("runtime_status=runtime_status_dashboard_ready")
    assert report["technical_preview_rc_line"].startswith("technical_preview_rc=technical_preview_rc_phase1_ready")


def test_audit_fails_when_required_reports_are_missing(tmp_path: Path):
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    _write_report(report_dir, "preserved-baselines-audit-", "preserved_baselines_ready")

    inputs = load_input_reports(report_dir)
    report = evaluate_technical_preview_rc_phase1_audit(**inputs)

    assert report["overall_status"] == "failed"
    assert report["readiness_status"] == "technical_preview_rc_phase1_blocked"
    assert "runtime_productization_phase3" in report["failure_reasons"]
    assert report["checks"]["http_transport"]["status"] == "failed"


def test_render_markdown_names_rc_authority_boundary():
    report = evaluate_technical_preview_rc_phase1_audit(
        preserved_baselines={"overall_status": "passed", "readiness_status": "preserved_baselines_ready"},
        runtime_productization_phase3={
            "overall_status": "passed",
            "readiness_status": "runtime_productization_phase3_ready",
        },
        http_transport={"overall_status": "passed", "readiness_status": "http_transport_thin_wrapper_phase1_ready"},
        approved_artifact_multimodal_runtime={
            "overall_status": "passed",
            "readiness_status": "approved_artifact_multimodal_runtime_phase1_ready",
        },
        chinese_semantic_naturalness={
            "overall_status": "passed",
            "readiness_status": "chinese_semantic_naturalness_phase1_ready",
        },
        dynamic_skill_candidate_runtime={
            "overall_status": "passed",
            "readiness_status": "dynamic_skill_candidate_runtime_phase1_ready",
        },
    )

    markdown = render_markdown(report)

    assert "# Technical Preview RC Phase 1 Audit" in markdown
    assert "technical_preview_rc_phase1_ready" in markdown
    assert "live_capture_enabled" in markdown
    assert "dynamic_skill_registry_auto_write_enabled" in markdown
