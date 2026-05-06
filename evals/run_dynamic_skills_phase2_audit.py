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
from amadeus_thread0.runtime.dynamic_skill_candidates import freeze_skill_candidate_payload, propose_skill_candidate_from_trace
from amadeus_thread0.runtime.skill_registry import SkillRegistryError, SkillRegistryManager

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

READY = "dynamic_skills_phase2_ready"
IN_PROGRESS = "dynamic_skills_phase2_in_progress"


def _candidate(
    *,
    trace_id: str = "trace-dynamic-skill",
    skill_id: str = "pytest-failure-review",
    summary: str = "Use rg to inspect pytest failures before editing.",
    allowed_tools: list[str] | None = None,
) -> dict[str, Any]:
    candidate = propose_skill_candidate_from_trace(
        {
            "trace_id": trace_id,
            "status": "completed",
            "summary": summary,
            "skill_id": skill_id,
            "requested_permissions": ["filesystem_read"],
            "sandbox_profiles": ["docker_local_isolated"],
        }
    )
    tools = list(allowed_tools or [])
    if tools:
        insertion = f"allowed_tools: {json.dumps(tools, ensure_ascii=False)}"
        candidate["draft_skill_md"] = str(candidate.get("draft_skill_md") or "").replace(
            "trust_tier: proposed",
            "trust_tier: proposed\n" + insertion,
        )
    return candidate


def _manager(tmp: str) -> SkillRegistryManager:
    return SkillRegistryManager(base_dir=Path(tmp) / "repo", data_dir=Path(tmp) / "data")


def _row(scenario_id: str, passed: bool, **evidence: Any) -> dict[str, Any]:
    return {
        "id": scenario_id,
        "status": "passed" if passed else "failed",
        "evidence": evidence,
    }


def scenario_approved_install_enable_candidate() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        manager = _manager(tmp)
        frozen = freeze_skill_candidate_payload(_candidate())
        result = manager.install_candidate(frozen, frozen, thread_id="thread-approved", enable=True)
        state = manager.compute_session_skill_state(thread_id="thread-approved", query_text="pytest failures")
        registry = manager.registry_snapshot()
        passed = bool(
            result.get("status") == "installed"
            and result.get("enabled") is True
            and result.get("hash") == frozen.get("hash")
            and state.get("active_skill_ids") == [frozen.get("skill_id")]
            and registry.get("skills")
            and registry["skills"][0].get("source") == "dynamic_candidate"
        )
        return _row(
            "approved_install_enable_candidate",
            passed,
            active_skill_ids=state.get("active_skill_ids"),
            result_status=result.get("status"),
            registry_source=registry.get("skills", [{}])[0].get("source") if registry.get("skills") else "",
        )


def scenario_rejected_install_not_active() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        manager = _manager(tmp)
        frozen = freeze_skill_candidate_payload(_candidate())
        drifted = {**frozen, "hash": "sha256:" + "0" * 64}
        rejected = False
        try:
            manager.install_candidate(frozen, drifted, thread_id="thread-rejected", enable=True)
        except SkillRegistryError:
            rejected = True
        state = manager.compute_session_skill_state(thread_id="thread-rejected", query_text="pytest failures")
        passed = bool(rejected and manager.runtime_catalog() == [] and state.get("active_skill_ids") == [])
        return _row(
            "rejected_install_not_active",
            passed,
            rejected=rejected,
            active_skill_ids=state.get("active_skill_ids"),
            catalog_size=len(manager.runtime_catalog()),
        )


def scenario_manual_disable_precedence() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        manager = _manager(tmp)
        frozen = freeze_skill_candidate_payload(_candidate())
        manager.install_candidate(frozen, frozen, thread_id="thread-disable", enable=True)
        manager.disable(skill_id=str(frozen.get("skill_id") or ""), thread_id="thread-disable")
        state = manager.compute_session_skill_state(thread_id="thread-disable", query_text="pytest failure review")
        passed = bool(
            str(frozen.get("skill_id") or "") in state.get("manual_disabled", [])
            and str(frozen.get("skill_id") or "") not in state.get("active_skill_ids", [])
        )
        return _row(
            "manual_disable_precedence",
            passed,
            manual_disabled=state.get("manual_disabled"),
            active_skill_ids=state.get("active_skill_ids"),
        )


def scenario_pin_precedence() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        manager = _manager(tmp)
        first = freeze_skill_candidate_payload(_candidate(trace_id="trace-first", skill_id="first-dynamic-skill"))
        pinned = freeze_skill_candidate_payload(_candidate(trace_id="trace-pinned", skill_id="pinned-dynamic-skill"))
        manager.install_candidate(first, first, thread_id="thread-pin", enable=True)
        manager.install_candidate(pinned, pinned, thread_id="thread-pin", enable=True)
        manager.pin(skill_id=str(pinned.get("skill_id") or ""), thread_id="thread-pin")
        state = manager.compute_session_skill_state(thread_id="thread-pin", query_text="")
        active = list(state.get("active_skill_ids") or [])
        passed = bool(active and active[0] == "pinned-dynamic-skill" and "pinned-dynamic-skill" in state.get("pinned_skill_ids", []))
        return _row(
            "pin_precedence",
            passed,
            pinned=state.get("pinned_skill_ids"),
            active_skill_ids=active,
        )


def scenario_followup_continuity_from_completed_use() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        manager = _manager(tmp)
        frozen = freeze_skill_candidate_payload(
            _candidate(allowed_tools=["execute_workspace_command"])
        )
        manager.install_candidate(frozen, frozen, thread_id="thread-use", enable=True)
        state = manager.compute_session_skill_state(thread_id="thread-use", query_text="")
        effects = derive_skill_effects(
            state,
            [
                {
                    "tool_name": "execute_workspace_command",
                    "status": "completed",
                    "proposal_id": "ap-dynamic-use-1",
                }
            ],
        )
        continuity = derive_procedural_continuity(
            {
                "kind": "skill_usage_completed",
                "primary_status": "completed",
                "primary_tool_name": "execute_workspace_command",
                "primary_proposal_id": "ap-dynamic-use-1",
                "skill_effects": effects,
            }
        )
        passed = bool(
            effects
            and effects[0].get("source") == "dynamic_candidate"
            and effects[0].get("operation") == "use"
            and continuity.get("capability_family") == "skill"
            and continuity.get("identity_safe") is True
        )
        return _row(
            "followup_continuity_from_completed_use",
            passed,
            effects=effects,
            continuity=continuity,
        )


def run_scenarios() -> list[dict[str, Any]]:
    return [
        scenario_approved_install_enable_candidate(),
        scenario_rejected_install_not_active(),
        scenario_manual_disable_precedence(),
        scenario_pin_precedence(),
        scenario_followup_continuity_from_completed_use(),
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
        "# Dynamic Skills Phase 2 Audit",
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
    json_path = REPORT_DIR / f"dynamic-skills-phase2-audit-{run_id}.json"
    md_path = REPORT_DIR / f"dynamic-skills-phase2-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[dynamic-skills-phase2] json={json_path}")
    print(f"[dynamic-skills-phase2] md={md_path}")
    print(f"[dynamic-skills-phase2] overall_status={report['overall_status']}")
    print(f"[dynamic-skills-phase2] readiness={report['readiness_status']}")
    return 0 if report["overall_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
