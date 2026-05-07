from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from amadeus_thread0.graph_parts.skill_runtime import derive_procedural_continuity, derive_skill_effects
from amadeus_thread0.runtime.dynamic_skill_candidate_runtime import (
    AUTHORITY_BOUNDARY,
    DYNAMIC_SKILL_CANDIDATE_RUNTIME_READY,
    build_dynamic_skill_candidate_runtime_readback,
)
from amadeus_thread0.runtime.dynamic_skill_candidates import (
    build_candidate_install_packet,
    freeze_skill_candidate_payload,
    propose_skill_candidate_from_trace,
)
from amadeus_thread0.runtime.skill_registry import SkillRegistryManager

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

READY = DYNAMIC_SKILL_CANDIDATE_RUNTIME_READY
IN_PROGRESS = "dynamic_skill_candidate_runtime_phase1_in_progress"


def _candidate() -> dict[str, Any]:
    return propose_skill_candidate_from_trace(
        {
            "trace_id": "trace-dynamic-runtime",
            "status": "completed",
            "summary": "Use rg to inspect pytest failures before editing.",
            "skill_id": "pytest-failure-review",
            "requested_permissions": ["filesystem_read"],
            "sandbox_profiles": ["docker_local_isolated"],
        }
    )


def _frozen() -> dict[str, Any]:
    return freeze_skill_candidate_payload(_candidate())


def _row(scenario_id: str, passed: bool, **evidence: Any) -> dict[str, Any]:
    return {
        "id": scenario_id,
        "status": "passed" if passed else "failed",
        "evidence": evidence,
    }


def scenario_pending_candidate_visible_without_activation() -> dict[str, Any]:
    frozen = _frozen()
    packet = build_candidate_install_packet(frozen)
    readback = build_dynamic_skill_candidate_runtime_readback(
        {
            "autonomy": {"action_packets": [packet], "pending_approval": packet},
            "skills": {"installed": [], "active": [], "pending_approval": {"dynamic_candidate": True, "candidate_id": frozen["candidate_id"]}},
        }
    )
    candidate = readback["candidates"][0]
    passed = bool(
        readback.get("readiness_status") == READY
        and candidate.get("candidate_state") == "pending_approval"
        and candidate.get("requires_approval") is True
        and candidate.get("registry_written") is False
        and candidate.get("active_after_install") is False
    )
    return _row(
        "pending_candidate_visible_without_activation",
        passed,
        readiness=readback.get("readiness_status"),
        candidate_state=candidate.get("candidate_state"),
        registry_written=candidate.get("registry_written"),
    )


def scenario_blocked_candidate_not_written() -> dict[str, Any]:
    packet = build_candidate_install_packet(_frozen())
    packet["status"] = "blocked"
    readback = build_dynamic_skill_candidate_runtime_readback(
        {"autonomy": {"action_packets": [packet]}, "skills": {"installed": [], "active": []}}
    )
    candidate = readback["candidates"][0]
    passed = bool(
        readback.get("readiness_status") == READY
        and candidate.get("candidate_state") == "blocked"
        and candidate.get("registry_written") is False
        and candidate.get("writeback_ready") is False
    )
    return _row(
        "blocked_candidate_not_written",
        passed,
        candidate_state=candidate.get("candidate_state"),
        failure_reasons=candidate.get("failure_reasons"),
    )


def scenario_approved_install_visible_after_registry_evidence() -> dict[str, Any]:
    frozen = _frozen()
    packet = build_candidate_install_packet(frozen)
    packet["status"] = "completed"
    packet["writeback_ready"] = True
    with tempfile.TemporaryDirectory() as tmp:
        manager = SkillRegistryManager(base_dir=Path(tmp) / "repo", data_dir=Path(tmp) / "data")
        manager.install_candidate(frozen, frozen, thread_id="thread-runtime", enable=True)
        runtime = manager.list_runtime(thread_id="thread-runtime", query_text="")
    readback = build_dynamic_skill_candidate_runtime_readback(
        {
            "autonomy": {"action_packets": [packet]},
            "skills": runtime,
            "digital_body_consequence": {
                "kind": "skill_install_completed",
                "primary_status": "completed",
                "primary_tool_name": "install_skill",
            },
        }
    )
    candidate = readback["candidates"][0]
    passed = bool(
        candidate.get("candidate_state") == "installed_active"
        and candidate.get("registry_written") is True
        and candidate.get("active_after_install") is True
        and candidate.get("writeback_ready") is True
    )
    return _row(
        "approved_install_visible_after_registry_evidence",
        passed,
        candidate_state=candidate.get("candidate_state"),
        summary=readback.get("summary"),
    )


def scenario_manual_disable_keeps_dynamic_skill_inactive() -> dict[str, Any]:
    frozen = _frozen()
    with tempfile.TemporaryDirectory() as tmp:
        manager = SkillRegistryManager(base_dir=Path(tmp) / "repo", data_dir=Path(tmp) / "data")
        manager.install_candidate(frozen, frozen, thread_id="thread-runtime", enable=True)
        manager.disable(skill_id=frozen["skill_id"], thread_id="thread-runtime")
        runtime = manager.list_runtime(thread_id="thread-runtime", query_text="pytest failures")
    readback = build_dynamic_skill_candidate_runtime_readback({"skills": runtime})
    candidate = readback["candidates"][0]
    passed = bool(
        candidate.get("candidate_state") == "installed_inactive"
        and candidate.get("registry_written") is True
        and candidate.get("active_after_install") is False
        and frozen["skill_id"] in runtime.get("manual_overrides", {}).get("disabled", [])
    )
    return _row(
        "manual_disable_keeps_dynamic_skill_inactive",
        passed,
        candidate_state=candidate.get("candidate_state"),
        manual_overrides=runtime.get("manual_overrides"),
    )


def scenario_completed_use_only_continuity() -> dict[str, Any]:
    frozen = _frozen()
    state = {
        "active_skill_entries": [
            {
                "skill_id": frozen["skill_id"],
                "name": frozen["skill_id"],
                "version": frozen["version"],
                "source": "dynamic_candidate",
                "trust_tier": "approved_candidate",
                "allowed_tools": ["execute_workspace_command"],
            }
        ]
    }
    effects = derive_skill_effects(
        state,
        [{"tool_name": "execute_workspace_command", "status": "completed", "proposal_id": "ap-runtime-use"}],
    )
    continuity = derive_procedural_continuity(
        {
            "kind": "skill_usage_completed",
            "primary_status": "completed",
            "primary_tool_name": "execute_workspace_command",
            "primary_proposal_id": "ap-runtime-use",
            "skill_effects": effects,
        }
    )
    readback = build_dynamic_skill_candidate_runtime_readback(
        {
            "skills": {
                "active": [
                    {
                        "skill_id": frozen["skill_id"],
                        "version": frozen["version"],
                        "source": "dynamic_candidate",
                        "trust_tier": "approved_candidate",
                    }
                ]
            },
            "digital_body_consequence": {
                "kind": "skill_usage_completed",
                "primary_status": "completed",
                "primary_tool_name": "execute_workspace_command",
                "skill_effects": effects,
                "procedural_continuity": continuity,
            },
        }
    )
    passed = bool(
        readback.get("continuity", {}).get("status") == "completed_use_only"
        and readback.get("continuity", {}).get("identity_safe") is True
    )
    return _row(
        "completed_use_only_continuity",
        passed,
        continuity=readback.get("continuity"),
    )


def scenario_authority_boundary_not_widened() -> dict[str, Any]:
    readback = build_dynamic_skill_candidate_runtime_readback({"autonomy": {"action_packets": [build_candidate_install_packet(_frozen())]}})
    boundary = readback.get("authority_boundary", {})
    passed = bool(
        boundary == AUTHORITY_BOUNDARY
        and boundary.get("registry_auto_write_allowed") is False
        and boundary.get("memory_write_allowed") is False
        and boundary.get("persona_core_mutation_allowed") is False
        and boundary.get("model_api_called") is False
    )
    return _row("authority_boundary_not_widened", passed, boundary=boundary)


def run_scenarios() -> list[dict[str, Any]]:
    return [
        scenario_pending_candidate_visible_without_activation(),
        scenario_blocked_candidate_not_written(),
        scenario_approved_install_visible_after_registry_evidence(),
        scenario_manual_disable_keeps_dynamic_skill_inactive(),
        scenario_completed_use_only_continuity(),
        scenario_authority_boundary_not_widened(),
    ]


def evaluate_scenarios(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [str(row.get("id") or "") for row in scenarios if row.get("status") != "passed"]
    overall = "failed" if failed else "passed"
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": overall,
        "readiness_status": READY if overall == "passed" else IN_PROGRESS,
        "failure_reasons": failed,
        "scenarios": scenarios,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Dynamic Skill Candidate Runtime Phase 1 Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Status |",
        "| --- | --- |",
    ]
    for row in report.get("scenarios") or []:
        lines.append(f"| `{row.get('id', '')}` | `{row.get('status', '')}` |")
    failures = [str(item) for item in report.get("failure_reasons") or [] if str(item)]
    if failures:
        lines.extend(["", "## Failures", ""])
        for failure in failures:
            lines.append(f"- `{failure}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    report = {"run_id": run_id, **evaluate_scenarios(run_scenarios())}
    json_path = REPORT_DIR / f"dynamic-skill-candidate-runtime-audit-{run_id}.json"
    md_path = REPORT_DIR / f"dynamic-skill-candidate-runtime-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[dynamic-skill-candidate-runtime] json={json_path}")
    print(f"[dynamic-skill-candidate-runtime] md={md_path}")
    print(f"[dynamic-skill-candidate-runtime] overall_status={report['overall_status']}")
    print(f"[dynamic-skill-candidate-runtime] readiness={report['readiness_status']}")
    return 0 if report["overall_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

