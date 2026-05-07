from __future__ import annotations

import time
from typing import Any


ADVISOR_DEMO_READINESS_PHASE1_READY = "advisor_demo_readiness_phase1_ready"
ADVISOR_DEMO_READINESS_PHASE1_BLOCKED = "advisor_demo_readiness_phase1_blocked"

READINESS_SCOPE = "package_ready_not_live_demo_certification"

REQUIRED_ASSETS = [
    "docs/ADVISOR_REPRO_RUNBOOK.md",
    "docs/DEMO_SCRIPT.md",
    "docs/TECHNICAL_PREVIEW_CHECKLIST.md",
    "docs/FINAL_DELIVERY_MANIFEST.md",
    "docs/EVAL_BASELINE.md",
    "docs/ABLATION_RESULTS.md",
    "docs/FAILURE_TAXONOMY.md",
    "user_study/README.md",
    "user_study/PROTOCOL.md",
    "user_study/FACILITATOR_SCRIPT.md",
    "user_study/EXECUTION_CHECKLIST.md",
    "user_study/CONSENT_TEMPLATE.md",
]

REQUIRED_COMMANDS = [
    "python evals\\run_technical_preview_rc_phase1_audit.py",
    "python evals\\run_operator_console_rc_phase1_audit.py",
    "python evals\\run_preserved_baselines_audit.py",
    "python evals\\run_langsmith_evals.py --local-only",
    "python evals\\run_probe_variance.py",
]

REQUIRED_DEMO_SIGNALS = [
    {"id": "role_persona_consistency", "required_text": "科研问答 + 角色一致性"},
    {"id": "worldline_commitment", "required_text": "世界线承诺"},
    {"id": "conflict_repair", "required_text": "冲突修复与关系演化"},
    {"id": "source_traceable_retrieval", "required_text": "可追溯知识检索"},
    {"id": "interruption_recovery", "required_text": "打断恢复"},
    {"id": "memory_guard_interception", "required_text": "记忆安全拦截"},
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


def _operator_ref(operator_console_rc: dict[str, Any]) -> dict[str, str]:
    return {
        "schema": str(operator_console_rc.get("schema") or "operator_console_rc.v1"),
        "overall_status": str(operator_console_rc.get("overall_status") or "missing"),
        "readiness_status": str(
            operator_console_rc.get("readiness_status")
            or operator_console_rc.get("readiness")
            or ""
        ),
    }


def _authority_boundary(operator_console_rc: dict[str, Any]) -> dict[str, bool]:
    boundary = _dict_or_empty(operator_console_rc.get("authority_boundary"))
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


def _command_inventory(asset_texts: dict[str, str]) -> dict[str, dict[str, Any]]:
    corpus = "\n".join(str(text) for text in asset_texts.values())
    inventory: dict[str, dict[str, Any]] = {}
    for command in REQUIRED_COMMANDS:
        present = command in corpus
        inventory[command] = {
            "status": "present" if present else "missing",
            "required": True,
        }
    return inventory


def _demo_script_inventory(asset_texts: dict[str, str]) -> dict[str, dict[str, Any]]:
    corpus = "\n".join(str(text) for text in asset_texts.values())
    inventory: dict[str, dict[str, Any]] = {}
    for signal in REQUIRED_DEMO_SIGNALS:
        signal_id = str(signal["id"])
        required_text = str(signal["required_text"])
        present = required_text in corpus
        inventory[signal_id] = {
            "status": "present" if present else "missing",
            "required_text": required_text,
        }
    return inventory


def _count_status(rows: dict[str, dict[str, Any]], status: str) -> int:
    return sum(1 for row in rows.values() if str(row.get("status") or "") == status)


def build_advisor_demo_readiness(
    *,
    operator_console_rc: dict[str, Any] | None,
    asset_texts: dict[str, str] | None,
) -> dict[str, Any]:
    operator = _dict_or_empty(operator_console_rc)
    texts = {str(key): str(value) for key, value in _dict_or_empty(asset_texts).items()}
    assets = _asset_inventory(texts)
    commands = _command_inventory(texts)
    demo_signals = _demo_script_inventory(texts)
    authority = _authority_boundary(operator)

    operator_ready = _ready(operator, "operator_console_rc_phase1_ready")
    ready_asset_count = _count_status(assets, "present")
    ready_command_count = _count_status(commands, "present")
    ready_demo_signal_count = _count_status(demo_signals, "present")

    failures: list[str] = []
    if not operator_ready:
        failures.append("operator_console_rc_not_ready")
    failures.extend(f"missing_asset:{path}" for path, row in assets.items() if row["status"] != "present")
    failures.extend(
        f"missing_command:{command}" for command, row in commands.items() if row["status"] != "present"
    )
    failures.extend(
        f"missing_demo_signal:{signal_id}"
        for signal_id, row in demo_signals.items()
        if row["status"] != "present"
    )
    failures.extend(_closed_authority_failures(authority))
    failures.extend(str(reason) for reason in _list_or_empty(operator.get("failure_reasons")) if str(reason))
    failures = list(dict.fromkeys(failures))

    overall = "failed" if failures else "passed"
    package_ready = overall == "passed"
    return {
        "schema": "advisor_demo_readiness.v1",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": overall,
        "readiness_status": (
            ADVISOR_DEMO_READINESS_PHASE1_READY
            if package_ready
            else ADVISOR_DEMO_READINESS_PHASE1_BLOCKED
        ),
        "readiness_scope": READINESS_SCOPE,
        "live_demo_observed": False,
        "manual_demo_required": True,
        "summary": {
            "package_ready": package_ready,
            "operator_console_ready": operator_ready,
            "ready_asset_count": ready_asset_count,
            "total_asset_count": len(REQUIRED_ASSETS),
            "ready_command_count": ready_command_count,
            "total_command_count": len(REQUIRED_COMMANDS),
            "ready_demo_signal_count": ready_demo_signal_count,
            "total_demo_signal_count": len(REQUIRED_DEMO_SIGNALS),
        },
        "operator_console_rc_ref": _operator_ref(operator),
        "asset_inventory": assets,
        "command_inventory": commands,
        "demo_script_inventory": demo_signals,
        "authority_boundary": authority,
        "next_actions": (
            [
                "run_advisor_demo_readiness_audit",
                "follow_advisor_repro_runbook",
                "archive_demo_artifacts",
            ]
            if package_ready
            else [
                "inspect_advisor_readiness_failures",
                "rerun_operator_console_rc_audit",
                "repair_demo_package_docs",
            ]
        ),
        "failure_reasons": failures,
    }


def compact_advisor_demo_readiness_line(readback: dict[str, Any] | None) -> str:
    data = _dict_or_empty(readback)
    summary = _dict_or_empty(data.get("summary"))
    return " | ".join(
        [
            f"advisor_demo_readiness={str(data.get('readiness_status') or 'unknown')}",
            f"assets={summary.get('ready_asset_count', 0)}/{summary.get('total_asset_count', 0)}",
            f"commands={summary.get('ready_command_count', 0)}/{summary.get('total_command_count', 0)}",
            (
                "demo_signals="
                f"{summary.get('ready_demo_signal_count', 0)}/{summary.get('total_demo_signal_count', 0)}"
            ),
            f"scope={str(data.get('readiness_scope') or READINESS_SCOPE)}",
        ]
    )


__all__ = [
    "ADVISOR_DEMO_READINESS_PHASE1_BLOCKED",
    "ADVISOR_DEMO_READINESS_PHASE1_READY",
    "READINESS_SCOPE",
    "REQUIRED_ASSETS",
    "REQUIRED_COMMANDS",
    "REQUIRED_DEMO_SIGNALS",
    "build_advisor_demo_readiness",
    "compact_advisor_demo_readiness_line",
]
