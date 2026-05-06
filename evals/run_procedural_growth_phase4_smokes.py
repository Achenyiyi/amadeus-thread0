from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from amadeus_thread0.graph_parts.procedural_recovery import (  # noqa: E402
    derive_procedural_recoveries_from_outcomes,
    summarize_procedural_recoveries,
)
from amadeus_thread0.graph_parts.procedural_planning import build_procedural_planning_bias  # noqa: E402
from amadeus_thread0.runtime.final_state import resolve_digital_body_consequence  # noqa: E402


REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _check(name: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": str(detail or "").strip()}


def _scenario_specs() -> list[dict[str, Any]]:
    return [
        {
            "id": "failed_execution_suggests_failure_artifact_inspection",
            "title": "failed_execution_suggests_failure_artifact_inspection",
        },
        {
            "id": "blocked_boundary_recovery_does_not_repeat_blocked_action",
            "title": "blocked_boundary_recovery_does_not_repeat_blocked_action",
        },
        {
            "id": "manual_takeover_recovery_preserves_takeover_boundary",
            "title": "manual_takeover_recovery_preserves_takeover_boundary",
        },
        {
            "id": "stale_context_recovery_refreshes_workspace_context",
            "title": "stale_context_recovery_refreshes_workspace_context",
        },
        {
            "id": "no_executed_attempt_stays_hold",
            "title": "no_executed_attempt_stays_hold",
        },
    ]


def _access_hints(*, workspace_root: str = "E:/repo/amadeus-thread0") -> dict[str, Any]:
    return {
        "filesystem_state": "writable",
        "sandbox_mode": "restricted",
        "workspace_root": workspace_root,
        "workspace_root_kind": "attached_repo_root",
        "sandbox_state": {
            "availability": "restricted",
            "allowed_roots": [workspace_root],
            "execution_policy": "approval_required",
            "runner_kind": "docker_isolated_runner",
            "isolation_level": "docker_local_isolated",
            "image_ref": "amadeus-thread0/sandbox-phase2:py312",
            "network_policy": "none",
            "workspace_root_kind": "attached_repo_root",
            "arbitrary_execution": False,
        },
    }


def _sandbox_packet(*, proposal_id: str, exit_code: int = 2) -> dict[str, Any]:
    return {
        "proposal_id": proposal_id,
        "origin": "motive_goal",
        "intent": "sandbox:execute_workspace_command",
        "status": "completed",
        "risk": "external_mutation",
        "requires_approval": True,
        "tool_name": "execute_workspace_command",
        "result_summary": "pytest failed",
        "tool_args": {
            "procedural_planning": {
                "planning_bias": True,
                "bias_kind": "sandbox_execute",
                "trace_id": f"proc_{proposal_id}",
                "trace_kind": "sandbox_execution_pattern",
                "source_run_id": f"prior-{proposal_id}",
                "source_tool_name": "execute_workspace_command",
                "suggested_capability_family": "sandbox",
                "suggested_pattern": "pytest",
                "suggested_executor": "pytest",
                "suggested_argv": ["pytest"],
                "must_request_approval": True,
                "requires_approval": True,
                "capability_claim": True,
                "confidence": 0.74,
            }
        },
        "execution_spec": {
            "executor": "pytest",
            "profile": "pytest",
            "argv": ["pytest"],
            "cwd": "E:/repo/amadeus-thread0",
            "allowed_roots": ["E:/repo/amadeus-thread0"],
        },
        "execution_result": {
            "run_id": f"{proposal_id}-run",
            "status": "failed",
            "exit_code": exit_code,
            "stdout_log_ref": f"E:/repo/.amadeus/sandbox-runs/{proposal_id}/stdout.txt",
            "stderr_log_ref": f"E:/repo/.amadeus/sandbox-runs/{proposal_id}/stderr.txt",
            "error_summary": f"process exited with code {exit_code}",
        },
    }


def _run_failed_execution_scenario() -> dict[str, Any]:
    consequence = resolve_digital_body_consequence(
        action_packets=[_sandbox_packet(proposal_id="phase4-failed")]
    )
    trace = _dict((consequence.get("procedural_traces") or [{}])[0])
    bias = build_procedural_planning_bias(
        current_event={"text": "继续跑 pytest。"},
        embodied_context={
            "workspace_root": "E:/repo/amadeus-thread0",
            "sandbox_runner_kind": "docker_isolated_runner",
            "sandbox_isolation_level": "docker_local_isolated",
            "sandbox_network_policy": "none",
            "procedural_traces": [trace],
        },
        access_hints=_access_hints(),
    )
    return {
        "consequence": consequence,
        "trace": trace,
        "bias": bias,
        "summary": summarize_procedural_recoveries(consequence.get("procedural_recoveries")),
    }


def _run_blocked_boundary_scenario() -> dict[str, Any]:
    outcome = {
        "outcome_id": "proc_out_phase4_blocked",
        "source_trace_id": "proc_phase4_blocked",
        "source_proposal_id": "ap-phase4-blocked",
        "source_run_id": "run-phase4-blocked",
        "planning_bias_kind": "sandbox_execute",
        "source_tool_name": "execute_workspace_command",
        "attempt_status": "blocked",
        "outcome_kind": "blocked_boundary_reinforced",
        "confidence_delta": -0.08,
        "reuse_allowed": False,
        "boundary_reinforced": True,
        "recovery_hint": "package install is blocked in the sandbox",
        "evidence_refs": ["run-phase4-blocked"],
    }
    recoveries = derive_procedural_recoveries_from_outcomes([outcome])
    return {"outcome": outcome, "recoveries": recoveries, "summary": summarize_procedural_recoveries(recoveries)}


def _run_manual_takeover_scenario() -> dict[str, Any]:
    outcome = {
        "outcome_id": "proc_out_phase4_manual",
        "source_trace_id": "proc_phase4_manual",
        "source_proposal_id": "ap-phase4-manual",
        "source_run_id": "run-phase4-manual",
        "planning_bias_kind": "browser_manual_takeover",
        "source_tool_name": "browser_fill",
        "attempt_status": "blocked",
        "outcome_kind": "manual_takeover_required",
        "confidence_delta": 0.0,
        "reuse_allowed": False,
        "boundary_reinforced": True,
        "recovery_hint": "manual browser takeover is still required before continuing",
        "evidence_refs": ["run-phase4-manual"],
    }
    recoveries = derive_procedural_recoveries_from_outcomes([outcome])
    return {"outcome": outcome, "recoveries": recoveries, "summary": summarize_procedural_recoveries(recoveries)}


def _run_stale_context_scenario() -> dict[str, Any]:
    outcome = {
        "outcome_id": "proc_out_phase4_stale",
        "source_trace_id": "proc_phase4_stale",
        "source_proposal_id": "ap-phase4-stale",
        "source_run_id": "run-phase4-stale",
        "planning_bias_kind": "workspace_guidance",
        "source_tool_name": "execute_workspace_command",
        "attempt_status": "completed",
        "outcome_kind": "stale_or_mismatched_context",
        "confidence_delta": 0.0,
        "reuse_allowed": False,
        "boundary_reinforced": False,
        "recovery_hint": "current context no longer matches this procedural trace",
        "evidence_refs": ["run-phase4-stale"],
    }
    recoveries = derive_procedural_recoveries_from_outcomes([outcome])
    return {"outcome": outcome, "recoveries": recoveries, "summary": summarize_procedural_recoveries(recoveries)}


def _run_no_executed_attempt_scenario() -> dict[str, Any]:
    outcome = {
        "outcome_id": "proc_out_phase4_hold",
        "source_trace_id": "proc_phase4_hold",
        "source_proposal_id": "ap-phase4-hold",
        "source_run_id": "run-phase4-hold",
        "planning_bias_kind": "sandbox_execute",
        "source_tool_name": "execute_workspace_command",
        "attempt_status": "awaiting_approval",
        "outcome_kind": "no_executed_attempt",
        "confidence_delta": 0.0,
        "reuse_allowed": False,
        "boundary_reinforced": False,
        "recovery_hint": "attempt did not execute; keep it as an unfulfilled intention",
        "evidence_refs": ["run-phase4-hold"],
    }
    recoveries = derive_procedural_recoveries_from_outcomes([outcome])
    return {"outcome": outcome, "recoveries": recoveries, "summary": summarize_procedural_recoveries(recoveries)}


def _evaluate_result(result: dict[str, Any]) -> dict[str, Any]:
    scenario_id = str(result.get("id") or "")
    payload = _dict(result.get("payload"))
    checks: dict[str, dict[str, Any]] = {}
    if scenario_id == "failed_execution_suggests_failure_artifact_inspection":
        summary = _dict(payload.get("summary"))
        bias = _dict(payload.get("bias"))
        trace = _dict(payload.get("trace"))
        checks["failed_recovery"] = _check(
            "failed_recovery",
            summary.get("last_recovery_kind") == "inspect_failure_artifact"
            and summary.get("safe_to_reuse") is False
            and bias.get("bias_kind") == "workspace_guidance"
            and "suggested_executor" not in bias
            and trace.get("recovery_required") is True,
            f"payload={payload}",
        )
    elif scenario_id == "blocked_boundary_recovery_does_not_repeat_blocked_action":
        recovery = _dict((payload.get("recoveries") or [{}])[0])
        checks["blocked_boundary"] = _check(
            "blocked_boundary",
            recovery.get("recovery_kind") == "avoid_blocked_boundary"
            and recovery.get("allowed_bias_kind") == "boundary_only"
            and recovery.get("requires_approval") is True
            and any("package install" in str(item) for item in recovery.get("must_not_repeat") or []),
            f"payload={payload}",
        )
    elif scenario_id == "manual_takeover_recovery_preserves_takeover_boundary":
        recovery = _dict((payload.get("recoveries") or [{}])[0])
        checks["manual_takeover"] = _check(
            "manual_takeover",
            recovery.get("recovery_kind") == "preserve_manual_takeover"
            and recovery.get("allowed_bias_kind") == "browser_manual_takeover"
            and recovery.get("requires_approval") is True
            and "browser mutation" in (recovery.get("must_not_repeat") or []),
            f"payload={payload}",
        )
    elif scenario_id == "stale_context_recovery_refreshes_workspace_context":
        recovery = _dict((payload.get("recoveries") or [{}])[0])
        checks["stale_context"] = _check(
            "stale_context",
            recovery.get("recovery_kind") == "refresh_workspace_context"
            and recovery.get("allowed_bias_kind") == "workspace_guidance"
            and recovery.get("safe_to_reuse") is False,
            f"payload={payload}",
        )
    elif scenario_id == "no_executed_attempt_stays_hold":
        recovery = _dict((payload.get("recoveries") or [{}])[0])
        checks["hold"] = _check(
            "hold",
            recovery.get("recovery_kind") == "hold_for_approval"
            and recovery.get("allowed_bias_kind") == "hold"
            and recovery.get("requires_approval") is True,
            f"payload={payload}",
        )
    else:
        checks["known_scenario"] = _check("known_scenario", False, scenario_id)
    return {
        "passed": all(bool(row.get("passed")) for row in checks.values()),
        "checks": checks,
    }


def _run_single_scenario(spec: dict[str, Any]) -> dict[str, Any]:
    started = time.time()
    scenario_id = str(spec.get("id") or "")
    if scenario_id == "failed_execution_suggests_failure_artifact_inspection":
        payload = _run_failed_execution_scenario()
    elif scenario_id == "blocked_boundary_recovery_does_not_repeat_blocked_action":
        payload = _run_blocked_boundary_scenario()
    elif scenario_id == "manual_takeover_recovery_preserves_takeover_boundary":
        payload = _run_manual_takeover_scenario()
    elif scenario_id == "stale_context_recovery_refreshes_workspace_context":
        payload = _run_stale_context_scenario()
    elif scenario_id == "no_executed_attempt_stays_hold":
        payload = _run_no_executed_attempt_scenario()
    else:
        payload = {}
    result = {
        "id": scenario_id,
        "title": str(spec.get("title") or scenario_id),
        "duration_s": round(time.time() - started, 3),
        "payload": payload,
    }
    result["evaluation"] = _evaluate_result(result)
    return result


def _aggregate_smoke_report(*, run_id: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    passed = len([result for result in results if bool(_dict(result.get("evaluation")).get("passed"))])
    failed = len(results) - passed
    return {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": "passed" if failed == 0 else "failed",
        "passed": passed,
        "failed": failed,
        "results": results,
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Procedural Growth Phase 4 Smokes ({report.get('run_id', 'unknown')})",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Passed: `{report.get('passed', 0)}`",
        f"Failed: `{report.get('failed', 0)}`",
        "",
        "| Scenario | Status | Duration (s) |",
        "| --- | --- | ---: |",
    ]
    for result in report.get("results") or []:
        if not isinstance(result, dict):
            continue
        status = "passed" if bool(_dict(result.get("evaluation")).get("passed")) else "failed"
        lines.append(f"| `{result.get('id', '')}` | `{status}` | {float(result.get('duration_s') or 0.0):.3f} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Procedural Growth Phase 4 smokes.")
    parser.add_argument("--run-tag", default="", help="Optional suffix for report filenames.")
    args = parser.parse_args()
    run_id = str(args.run_tag or "").strip() or f"phase4-{uuid.uuid4().hex[:8]}"
    results = [_run_single_scenario(spec) for spec in _scenario_specs()]
    report = _aggregate_smoke_report(run_id=run_id, results=results)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    suffix = f"-{run_id}" if run_id else ""
    json_path = REPORT_DIR / f"procedural-growth-phase4-smokes-{timestamp}{suffix}.json"
    md_path = REPORT_DIR / f"procedural-growth-phase4-smokes-{timestamp}{suffix}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[procedural-growth-phase4-smokes] json={json_path}")
    print(f"[procedural-growth-phase4-smokes] md={md_path}")
    print(f"[procedural-growth-phase4-smokes] overall_status={report['overall_status']}")
    return 0 if report["overall_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
