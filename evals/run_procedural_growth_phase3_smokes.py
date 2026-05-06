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

from amadeus_thread0.graph_parts.procedural_outcome import (  # noqa: E402
    calibrate_procedural_traces_with_outcomes,
    derive_procedural_outcomes_from_action_packets,
    summarize_procedural_outcomes,
)
from amadeus_thread0.graph_parts.procedural_planning import build_procedural_planning_bias  # noqa: E402
from amadeus_thread0.runtime.final_state import resolve_digital_body_consequence  # noqa: E402


REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _check(name: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": str(detail or "").strip()}


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


def _sandbox_trace(**overrides: Any) -> dict[str, Any]:
    trace = {
        "trace_id": "proc_phase3_pytest_smoke",
        "trace_kind": "sandbox_execution_pattern",
        "source_proposal_id": "ap-phase3-prior",
        "source_run_id": "run-phase3-prior",
        "source_tool_name": "execute_workspace_command",
        "status": "completed",
        "procedure_steps": ["inspect cwd", "run bounded command", "read stdout/artifact"],
        "result_summary": "pytest passed",
        "reuse_conditions": ["similar workspace command", "pytest command profile"],
        "boundary_notes": ["requires approval before execution"],
        "confidence": 0.7,
    }
    trace.update(overrides)
    return trace


def _planning(trace: dict[str, Any]) -> dict[str, Any]:
    return {
        "planning_bias": True,
        "bias_kind": "sandbox_execute",
        "trace_id": trace.get("trace_id"),
        "trace_kind": trace.get("trace_kind"),
        "source_run_id": trace.get("source_run_id"),
        "source_tool_name": trace.get("source_tool_name"),
        "suggested_capability_family": "sandbox",
        "suggested_pattern": "pytest",
        "suggested_executor": "pytest",
        "suggested_argv": ["pytest"],
        "must_request_approval": True,
        "requires_approval": True,
        "capability_claim": True,
        "confidence": trace.get("confidence"),
    }


def _sandbox_packet(
    *,
    trace: dict[str, Any],
    proposal_id: str,
    status: str = "completed",
    exit_code: int = 0,
) -> dict[str, Any]:
    return {
        "proposal_id": proposal_id,
        "origin": "motive_goal",
        "intent": "sandbox:execute_workspace_command",
        "status": status,
        "risk": "external_mutation",
        "requires_approval": True,
        "tool_name": "execute_workspace_command",
        "result_summary": "pytest passed" if exit_code == 0 else "pytest failed",
        "tool_args": {"procedural_planning": _planning(trace)},
        "execution_spec": {
            "executor": "pytest",
            "profile": "pytest",
            "argv": ["pytest"],
            "cwd": "E:/repo/amadeus-thread0",
            "allowed_roots": ["E:/repo/amadeus-thread0"],
        },
        "execution_result": {
            "run_id": f"{proposal_id}-run",
            "status": "completed" if exit_code == 0 else "failed",
            "exit_code": exit_code,
            "stdout_log_ref": f"E:/repo/.amadeus/sandbox-runs/{proposal_id}/stdout.txt",
            "stderr_log_ref": f"E:/repo/.amadeus/sandbox-runs/{proposal_id}/stderr.txt",
            "error_summary": "" if exit_code == 0 else "process exited with code 2",
        },
    }


def _scenario_specs() -> list[dict[str, Any]]:
    return [
        {
            "id": "calibrated_sandbox_success_boosts_reuse",
            "title": "calibrated_sandbox_success_boosts_reuse",
        },
        {
            "id": "failed_sandbox_attempt_reduces_reuse",
            "title": "failed_sandbox_attempt_reduces_reuse",
        },
        {
            "id": "manual_takeover_preserves_boundary",
            "title": "manual_takeover_preserves_boundary",
        },
        {
            "id": "pending_attempt_does_not_become_fact",
            "title": "pending_attempt_does_not_become_fact",
        },
    ]


def _run_success_scenario() -> dict[str, Any]:
    trace = _sandbox_trace(confidence=0.69)
    packet = _sandbox_packet(trace=trace, proposal_id="ap-phase3-success")
    outcomes = derive_procedural_outcomes_from_action_packets([packet], traces=[trace])
    calibrated = calibrate_procedural_traces_with_outcomes([trace], outcomes)
    bias = build_procedural_planning_bias(
        current_event={"text": "继续跑 pytest。"},
        embodied_context={
            "workspace_root": "E:/repo/amadeus-thread0",
            "sandbox_runner_kind": "docker_isolated_runner",
            "sandbox_isolation_level": "docker_local_isolated",
            "sandbox_network_policy": "none",
            "procedural_traces": calibrated,
            "procedural_outcomes": outcomes,
        },
        access_hints=_access_hints(),
    )
    return {"trace": trace, "packet": packet, "outcomes": outcomes, "calibrated": calibrated, "bias": bias}


def _run_failed_scenario() -> dict[str, Any]:
    trace = _sandbox_trace(trace_id="proc_phase3_failed_smoke", confidence=0.74)
    packet = _sandbox_packet(trace=trace, proposal_id="ap-phase3-failed", exit_code=2)
    consequence = resolve_digital_body_consequence(action_packets=[packet])
    return {
        "trace": trace,
        "packet": packet,
        "consequence": consequence,
        "summary": summarize_procedural_outcomes(consequence.get("procedural_outcomes")),
    }


def _run_manual_scenario() -> dict[str, Any]:
    packet = {
        "proposal_id": "ap-phase3-manual",
        "origin": "motive_goal",
        "intent": "browser:fill",
        "status": "blocked",
        "risk": "external_mutation",
        "requires_approval": True,
        "tool_name": "browser_fill",
        "block_reason": "sensitive credential entry requires manual browser takeover",
        "browser_execution_preview": {"operation": "fill", "requires_manual_takeover": True},
        "browser_execution_result": {
            "run_id": "browser-phase3-manual-run",
            "status": "blocked",
            "last_action_status": "manual_takeover_required",
            "manual_takeover_required": True,
        },
    }
    outcomes = derive_procedural_outcomes_from_action_packets(
        [packet],
        planning_bias={"bias_kind": "browser_manual_takeover", "trace_id": "proc_phase3_manual"},
    )
    return {"packet": packet, "outcomes": outcomes, "summary": summarize_procedural_outcomes(outcomes)}


def _run_pending_scenario() -> dict[str, Any]:
    trace = _sandbox_trace(trace_id="proc_phase3_pending_smoke")
    packet = _sandbox_packet(trace=trace, proposal_id="ap-phase3-pending", status="awaiting_approval")
    packet.pop("execution_result", None)
    consequence = resolve_digital_body_consequence(action_packets=[packet])
    outcomes = derive_procedural_outcomes_from_action_packets([packet], traces=[trace])
    return {"packet": packet, "consequence": consequence, "outcomes": outcomes}


def _evaluate_result(result: dict[str, Any]) -> dict[str, Any]:
    scenario_id = str(result.get("id") or "")
    checks: dict[str, dict[str, Any]] = {}
    if scenario_id == "calibrated_sandbox_success_boosts_reuse":
        payload = _dict(result.get("payload"))
        outcomes = list(payload.get("outcomes") or [])
        calibrated = list(payload.get("calibrated") or [])
        bias = _dict(payload.get("bias"))
        outcome = _dict(outcomes[0]) if outcomes else {}
        trace = _dict(calibrated[0]) if calibrated else {}
        checks["success_outcome"] = _check(
            "success_outcome",
            outcome.get("outcome_kind") == "confirmed_success"
            and outcome.get("reuse_allowed") is True
            and float(trace.get("confidence") or 0.0) > 0.69
            and bias.get("bias_kind") == "sandbox_execute"
            and bias.get("requires_approval") is True,
            f"payload={payload}",
        )
    elif scenario_id == "failed_sandbox_attempt_reduces_reuse":
        payload = _dict(result.get("payload"))
        summary = _dict(payload.get("summary"))
        consequence = _dict(payload.get("consequence"))
        trace = _dict((consequence.get("procedural_traces") or [{}])[0])
        checks["failed_outcome"] = _check(
            "failed_outcome",
            summary.get("last_outcome_kind") == "failed_execution"
            and summary.get("reuse_allowed") is False
            and float(trace.get("confidence") or 1.0) < 0.74,
            f"payload={payload}",
        )
    elif scenario_id == "manual_takeover_preserves_boundary":
        payload = _dict(result.get("payload"))
        summary = _dict(payload.get("summary"))
        checks["manual_boundary"] = _check(
            "manual_boundary",
            summary.get("last_outcome_kind") == "manual_takeover_required"
            and summary.get("boundary_reinforced") is True
            and summary.get("reuse_allowed") is False,
            f"payload={payload}",
        )
    elif scenario_id == "pending_attempt_does_not_become_fact":
        payload = _dict(result.get("payload"))
        consequence = _dict(payload.get("consequence"))
        outcomes = list(payload.get("outcomes") or [])
        outcome = _dict(outcomes[0]) if outcomes else {}
        checks["pending_no_fact"] = _check(
            "pending_no_fact",
            outcome.get("outcome_kind") == "no_executed_attempt"
            and outcome.get("reuse_allowed") is False
            and consequence.get("procedural_growth") in (None, False),
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
    if scenario_id == "calibrated_sandbox_success_boosts_reuse":
        payload = _run_success_scenario()
    elif scenario_id == "failed_sandbox_attempt_reduces_reuse":
        payload = _run_failed_scenario()
    elif scenario_id == "manual_takeover_preserves_boundary":
        payload = _run_manual_scenario()
    elif scenario_id == "pending_attempt_does_not_become_fact":
        payload = _run_pending_scenario()
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
        f"# Procedural Growth Phase 3 Smokes ({report.get('run_id', 'unknown')})",
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
    parser = argparse.ArgumentParser(description="Run Procedural Growth Phase 3 smokes.")
    parser.add_argument("--run-tag", default="", help="Optional suffix for report filenames.")
    args = parser.parse_args()
    run_id = str(args.run_tag or "").strip() or f"phase3-{uuid.uuid4().hex[:8]}"
    results = [_run_single_scenario(spec) for spec in _scenario_specs()]
    report = _aggregate_smoke_report(run_id=run_id, results=results)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    suffix = f"-{run_id}" if run_id else ""
    json_path = REPORT_DIR / f"procedural-growth-phase3-smokes-{timestamp}{suffix}.json"
    md_path = REPORT_DIR / f"procedural-growth-phase3-smokes-{timestamp}{suffix}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[procedural-growth-phase3-smokes] json={json_path}")
    print(f"[procedural-growth-phase3-smokes] md={md_path}")
    print(f"[procedural-growth-phase3-smokes] overall_status={report['overall_status']}")
    return 0 if report["overall_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
