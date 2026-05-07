from __future__ import annotations

from amadeus_thread0.runtime.advisor_demo_dry_run import (
    ADVISOR_DEMO_DRY_RUN_PHASE1_READY,
    REQUIRED_ARCHIVE_MARKERS,
    REQUIRED_DEMO_SCENARIOS,
    REQUIRED_RUNBOOK_MARKERS,
    build_advisor_demo_dry_run,
    compact_advisor_demo_dry_run_line,
)


def _advisor_readiness(*, live_capture_enabled: bool = False) -> dict:
    return {
        "schema": "advisor_demo_readiness.v1",
        "overall_status": "passed",
        "readiness_status": "advisor_demo_readiness_phase1_ready",
        "readiness_scope": "package_ready_not_live_demo_certification",
        "authority_boundary": {
            "live_capture_enabled": live_capture_enabled,
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


def _asset_texts() -> dict[str, str]:
    scenario_text = "\n".join(
        f"{row['heading']}\n用户输入：\n预期信号：\n{row['representative_text']}"
        for row in REQUIRED_DEMO_SCENARIOS
    )
    runbook_text = "\n".join(REQUIRED_RUNBOOK_MARKERS)
    archive_text = "\n".join(REQUIRED_ARCHIVE_MARKERS)
    corpus = f"{scenario_text}\n{runbook_text}\n{archive_text}\n"
    return {
        "docs/DEMO_SCRIPT.md": corpus,
        "docs/ADVISOR_REPRO_RUNBOOK.md": corpus,
        "docs/TECHNICAL_PREVIEW_CHECKLIST.md": corpus,
        "docs/FINAL_DELIVERY_MANIFEST.md": corpus,
    }


def test_advisor_demo_dry_run_passes_when_rehearsal_assets_are_ready():
    report = build_advisor_demo_dry_run(
        advisor_demo_readiness=_advisor_readiness(),
        asset_texts=_asset_texts(),
    )

    assert report["schema"] == "advisor_demo_dry_run.v1"
    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == ADVISOR_DEMO_DRY_RUN_PHASE1_READY
    assert report["dry_run_scope"] == "scripted_rehearsal_ready_not_live_demo_observed"
    assert report["live_demo_observed"] is False
    assert report["manual_demo_required"] is True
    assert report["summary"]["ready_scenario_count"] == len(REQUIRED_DEMO_SCENARIOS)
    assert report["summary"]["ready_runbook_marker_count"] == len(REQUIRED_RUNBOOK_MARKERS)
    assert report["summary"]["ready_archive_marker_count"] == len(REQUIRED_ARCHIVE_MARKERS)
    assert "follow_demo_script_manually" in report["next_actions"]


def test_advisor_demo_dry_run_blocks_when_required_scenario_is_missing():
    texts = _asset_texts()
    scenario = REQUIRED_DEMO_SCENARIOS[0]
    texts["docs/DEMO_SCRIPT.md"] = texts["docs/DEMO_SCRIPT.md"].replace(
        str(scenario["heading"]),
        "",
    )

    report = build_advisor_demo_dry_run(
        advisor_demo_readiness=_advisor_readiness(),
        asset_texts=texts,
    )

    assert report["overall_status"] == "failed"
    assert report["readiness_status"] == "advisor_demo_dry_run_phase1_blocked"
    assert f"missing_demo_scenario:{scenario['id']}" in report["failure_reasons"]
    assert report["demo_scenario_inventory"][scenario["id"]]["status"] == "missing"


def test_advisor_demo_dry_run_blocks_when_inherited_authority_widens():
    report = build_advisor_demo_dry_run(
        advisor_demo_readiness=_advisor_readiness(live_capture_enabled=True),
        asset_texts=_asset_texts(),
    )

    assert report["overall_status"] == "failed"
    assert "authority_widened:live_capture" in report["failure_reasons"]
    assert report["authority_boundary"]["live_capture_enabled"] is True


def test_compact_advisor_demo_dry_run_line_summarizes_rehearsal_scope():
    report = build_advisor_demo_dry_run(
        advisor_demo_readiness=_advisor_readiness(),
        asset_texts=_asset_texts(),
    )

    line = compact_advisor_demo_dry_run_line(report)

    assert "advisor_demo_dry_run=advisor_demo_dry_run_phase1_ready" in line
    assert f"scenarios={len(REQUIRED_DEMO_SCENARIOS)}/{len(REQUIRED_DEMO_SCENARIOS)}" in line
    assert f"runbook={len(REQUIRED_RUNBOOK_MARKERS)}/{len(REQUIRED_RUNBOOK_MARKERS)}" in line
    assert f"archive={len(REQUIRED_ARCHIVE_MARKERS)}/{len(REQUIRED_ARCHIVE_MARKERS)}" in line
    assert "scope=scripted_rehearsal_ready_not_live_demo_observed" in line
