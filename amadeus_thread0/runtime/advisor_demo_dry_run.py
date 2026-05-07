from __future__ import annotations

import time
from typing import Any


ADVISOR_DEMO_DRY_RUN_PHASE1_READY = "advisor_demo_dry_run_phase1_ready"
ADVISOR_DEMO_DRY_RUN_PHASE1_BLOCKED = "advisor_demo_dry_run_phase1_blocked"

DRY_RUN_SCOPE = "scripted_rehearsal_ready_not_live_demo_observed"

REQUIRED_ASSETS = [
    "docs/DEMO_SCRIPT.md",
    "docs/ADVISOR_REPRO_RUNBOOK.md",
    "docs/TECHNICAL_PREVIEW_CHECKLIST.md",
    "docs/FINAL_DELIVERY_MANIFEST.md",
]

REQUIRED_DEMO_SCENARIOS = [
    {
        "id": "role_persona_consistency",
        "heading": "Scenario 1. 科研问答 + 角色一致性",
        "representative_text": "我在做一个多模态角色智能体系统",
    },
    {
        "id": "worldline_commitment",
        "heading": "Scenario 2. 世界线承诺",
        "representative_text": "我们约定这周末一起复盘实验日志",
    },
    {
        "id": "conflict_repair",
        "heading": "Scenario 3. 冲突修复与关系演化",
        "representative_text": "这件事我想认真道歉",
    },
    {
        "id": "source_traceable_retrieval",
        "heading": "Scenario 4. 可追溯知识检索",
        "representative_text": "search_langchain_docs",
    },
    {
        "id": "interruption_recovery",
        "heading": "Scenario 5. 打断恢复",
        "representative_text": "我中途打断你了",
    },
    {
        "id": "memory_guard_interception",
        "heading": "Scenario 6. 记忆安全拦截",
        "representative_text": "key=persona_rules",
    },
]

REQUIRED_RUNBOOK_MARKERS = [
    "CLI Smoke",
    "Technical Preview RC Evidence",
    "Operator Console RC",
    "Advisor Demo Readiness",
    "Advisor Demo Dry Run",
    "Official Baseline Reproduction",
    "Probe Variance Reproduction",
    "Live Demo Path",
    "Artifact Capture",
    "Failure Handling",
    "Exit Condition",
]

REQUIRED_ARCHIVE_MARKERS = [
    "technical-preview-rc-phase1-audit-*.json",
    "operator-console-rc-phase1-audit-*.json",
    "advisor-demo-readiness-phase1-audit-*.json",
    "advisor-demo-dry-run-phase1-audit-*.json",
    "evals/reports/*.json",
    "evals/reports/*.md",
    "DEMO_SCRIPT.md",
    "TECHNICAL_PREVIEW_CHECKLIST.md",
    "user_study/",
]


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _ready(report: dict[str, Any], expected_readiness: str) -> bool:
    return (
        str(report.get("overall_status") or "") == "passed"
        and str(report.get("readiness_status") or report.get("readiness") or "") == expected_readiness
    )


def _advisor_ref(advisor_demo_readiness: dict[str, Any]) -> dict[str, str]:
    return {
        "schema": str(advisor_demo_readiness.get("schema") or "advisor_demo_readiness.v1"),
        "overall_status": str(advisor_demo_readiness.get("overall_status") or "missing"),
        "readiness_status": str(
            advisor_demo_readiness.get("readiness_status")
            or advisor_demo_readiness.get("readiness")
            or ""
        ),
    }


def _authority_boundary(advisor_demo_readiness: dict[str, Any]) -> dict[str, bool]:
    boundary = _dict_or_empty(advisor_demo_readiness.get("authority_boundary"))
    return {
        "live_capture_enabled": bool(boundary.get("live_capture_enabled")),
        "external_executor_auto_enabled": bool(boundary.get("external_executor_auto_enabled")),
        "dynamic_skill_registry_auto_write_enabled": bool(
            boundary.get("dynamic_skill_registry_auto_write_enabled")
        ),
        "multimodal_model_auto_call_enabled": bool(boundary.get("multimodal_model_auto_call_enabled")),
        "frontend_semantics_owner": bool(boundary.get("frontend_semantics_owner")),
        "persona_core_mutation_allowed": bool(boundary.get("persona_core_mutation_allowed")),
        "memory_write_widened": bool(boundary.get("memory_write_widened")),
        "http_server_semantics_owner": bool(boundary.get("http_server_semantics_owner")),
    }


def _closed_authority_failures(boundary: dict[str, bool]) -> list[str]:
    labels = {
        "live_capture_enabled": "authority_widened:live_capture",
        "external_executor_auto_enabled": "authority_widened:external_executor_harness",
        "dynamic_skill_registry_auto_write_enabled": "authority_widened:dynamic_skill_registry",
        "multimodal_model_auto_call_enabled": "authority_widened:multimodal_model_auto_call",
        "frontend_semantics_owner": "authority_widened:frontend_semantics_owner",
        "persona_core_mutation_allowed": "authority_widened:persona_core_mutation",
        "memory_write_widened": "authority_widened:memory_write",
        "http_server_semantics_owner": "authority_widened:http_server_semantics_owner",
    }
    return [reason for key, reason in labels.items() if bool(boundary.get(key, False))]


def _asset_inventory(asset_texts: dict[str, str]) -> dict[str, dict[str, Any]]:
    inventory: dict[str, dict[str, Any]] = {}
    for path in REQUIRED_ASSETS:
        text = str(asset_texts.get(path) or "")
        exists = bool(text.strip())
        inventory[path] = {
            "status": "present" if exists else "missing",
            "required": True,
            "char_count": len(text),
        }
    return inventory


def _demo_scenario_inventory(asset_texts: dict[str, str]) -> dict[str, dict[str, Any]]:
    demo_text = str(asset_texts.get("docs/DEMO_SCRIPT.md") or "")
    inventory: dict[str, dict[str, Any]] = {}
    for scenario in REQUIRED_DEMO_SCENARIOS:
        scenario_id = str(scenario["id"])
        checks = {
            "heading": str(scenario["heading"]) in demo_text,
            "user_input": "用户输入：" in demo_text,
            "expected_signal": "预期信号：" in demo_text,
            "representative_text": str(scenario["representative_text"]) in demo_text,
        }
        present = all(checks.values())
        inventory[scenario_id] = {
            "status": "present" if present else "missing",
            "heading": str(scenario["heading"]),
            "checks": checks,
        }
    return inventory


def _marker_inventory(markers: list[str], asset_texts: dict[str, str]) -> dict[str, dict[str, Any]]:
    corpus = "\n".join(str(text) for text in asset_texts.values())
    inventory: dict[str, dict[str, Any]] = {}
    for marker in markers:
        present = marker in corpus
        inventory[marker] = {
            "status": "present" if present else "missing",
            "required": True,
        }
    return inventory


def _count_status(rows: dict[str, dict[str, Any]], status: str) -> int:
    return sum(1 for row in rows.values() if str(row.get("status") or "") == status)


def build_advisor_demo_dry_run(
    *,
    advisor_demo_readiness: dict[str, Any] | None,
    asset_texts: dict[str, str] | None,
) -> dict[str, Any]:
    advisor = _dict_or_empty(advisor_demo_readiness)
    texts = {str(key): str(value) for key, value in _dict_or_empty(asset_texts).items()}
    assets = _asset_inventory(texts)
    scenarios = _demo_scenario_inventory(texts)
    runbook = _marker_inventory(REQUIRED_RUNBOOK_MARKERS, texts)
    archive = _marker_inventory(REQUIRED_ARCHIVE_MARKERS, texts)
    authority = _authority_boundary(advisor)

    advisor_ready = _ready(advisor, "advisor_demo_readiness_phase1_ready")
    ready_asset_count = _count_status(assets, "present")
    ready_scenario_count = _count_status(scenarios, "present")
    ready_runbook_marker_count = _count_status(runbook, "present")
    ready_archive_marker_count = _count_status(archive, "present")

    failures: list[str] = []
    if not advisor_ready:
        failures.append("advisor_demo_readiness_not_ready")
    failures.extend(f"missing_asset:{path}" for path, row in assets.items() if row["status"] != "present")
    failures.extend(
        f"missing_demo_scenario:{scenario_id}"
        for scenario_id, row in scenarios.items()
        if row["status"] != "present"
    )
    failures.extend(
        f"missing_runbook_marker:{marker}"
        for marker, row in runbook.items()
        if row["status"] != "present"
    )
    failures.extend(
        f"missing_archive_marker:{marker}"
        for marker, row in archive.items()
        if row["status"] != "present"
    )
    failures.extend(_closed_authority_failures(authority))
    failures.extend(str(reason) for reason in _list_or_empty(advisor.get("failure_reasons")) if str(reason))
    failures = list(dict.fromkeys(failures))

    overall = "failed" if failures else "passed"
    dry_run_ready = overall == "passed"
    return {
        "schema": "advisor_demo_dry_run.v1",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": overall,
        "readiness_status": (
            ADVISOR_DEMO_DRY_RUN_PHASE1_READY
            if dry_run_ready
            else ADVISOR_DEMO_DRY_RUN_PHASE1_BLOCKED
        ),
        "dry_run_scope": DRY_RUN_SCOPE,
        "live_demo_observed": False,
        "manual_demo_required": True,
        "summary": {
            "dry_run_ready": dry_run_ready,
            "advisor_demo_readiness_ready": advisor_ready,
            "ready_asset_count": ready_asset_count,
            "total_asset_count": len(REQUIRED_ASSETS),
            "ready_scenario_count": ready_scenario_count,
            "total_scenario_count": len(REQUIRED_DEMO_SCENARIOS),
            "ready_runbook_marker_count": ready_runbook_marker_count,
            "total_runbook_marker_count": len(REQUIRED_RUNBOOK_MARKERS),
            "ready_archive_marker_count": ready_archive_marker_count,
            "total_archive_marker_count": len(REQUIRED_ARCHIVE_MARKERS),
        },
        "advisor_demo_readiness_ref": _advisor_ref(advisor),
        "asset_inventory": assets,
        "demo_scenario_inventory": scenarios,
        "runbook_inventory": runbook,
        "archive_inventory": archive,
        "authority_boundary": authority,
        "next_actions": (
            [
                "follow_demo_script_manually",
                "archive_dry_run_artifacts",
                "record_demo_operator_notes",
            ]
            if dry_run_ready
            else [
                "inspect_dry_run_failures",
                "rerun_advisor_demo_readiness_audit",
                "repair_demo_runbook_or_archive_docs",
            ]
        ),
        "failure_reasons": failures,
    }


def compact_advisor_demo_dry_run_line(readback: dict[str, Any] | None) -> str:
    data = _dict_or_empty(readback)
    summary = _dict_or_empty(data.get("summary"))
    return " | ".join(
        [
            f"advisor_demo_dry_run={str(data.get('readiness_status') or 'unknown')}",
            f"scenarios={summary.get('ready_scenario_count', 0)}/{summary.get('total_scenario_count', 0)}",
            (
                "runbook="
                f"{summary.get('ready_runbook_marker_count', 0)}/"
                f"{summary.get('total_runbook_marker_count', 0)}"
            ),
            (
                "archive="
                f"{summary.get('ready_archive_marker_count', 0)}/"
                f"{summary.get('total_archive_marker_count', 0)}"
            ),
            f"scope={str(data.get('dry_run_scope') or DRY_RUN_SCOPE)}",
        ]
    )


__all__ = [
    "ADVISOR_DEMO_DRY_RUN_PHASE1_BLOCKED",
    "ADVISOR_DEMO_DRY_RUN_PHASE1_READY",
    "DRY_RUN_SCOPE",
    "REQUIRED_ARCHIVE_MARKERS",
    "REQUIRED_ASSETS",
    "REQUIRED_DEMO_SCENARIOS",
    "REQUIRED_RUNBOOK_MARKERS",
    "build_advisor_demo_dry_run",
    "compact_advisor_demo_dry_run_line",
]
