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

from amadeus_thread0.graph_parts.procedural_growth import (  # noqa: E402
    build_procedural_hint,
    extract_procedural_traces_from_action_packets,
)
from amadeus_thread0.runtime.final_state import resolve_digital_body_consequence  # noqa: E402
from amadeus_thread0.utils.cli_views import build_evolution_cli_summary, build_evolution_summary_line  # noqa: E402


REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _check(name: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": str(detail or "").strip()}


def _sandbox_body(*, blocked: bool = False) -> dict[str, Any]:
    return {
        "active_surface": "tooling",
        "perception_channels": ["dialogue", "filesystem"],
        "action_channels": ["language", "structured_action", "tooling"],
        "world_surfaces": ["filesystem", "sandbox"],
        "access_state": {
            "mode": "tool_enabled",
            "filesystem_state": "writable",
            "sandbox_mode": "restricted",
            "sandbox_state": {
                "availability": "restricted",
                "execution_policy": "approval_required",
                "runner_kind": "docker_isolated_runner",
                "isolation_level": "docker_local_isolated",
                "image_ref": "amadeus-thread0/sandbox-phase2:py312",
                "network_policy": "none",
                "workspace_root_kind": "attached_repo_root",
            },
        },
        "resource_state": {
            "completed_packet_count": 0 if blocked else 1,
            "blocked_packet_count": 1 if blocked else 0,
            "artifact_continuity": "attached",
            "active_artifact_kind": "workspace",
            "active_artifact_ref": "E:/repo/amadeus-thread0",
            "active_artifact_label": "amadeus-thread0",
            "artifact_carrier": "filesystem",
            "workspace_root": "E:/repo/amadeus-thread0",
        },
    }


def _sandbox_packet(*, proposal_id: str, status: str, exit_code: int = 0) -> dict[str, Any]:
    return {
        "proposal_id": proposal_id,
        "origin": "motive_goal",
        "intent": "sandbox:execute_workspace_command",
        "status": status,
        "risk": "external_mutation",
        "requires_approval": True,
        "tool_name": "execute_workspace_command",
        "result_summary": "pytest passed" if status == "completed" else "pytest failed",
        "execution_spec": {
            "executor": "pytest",
            "profile": "pytest",
            "runner_kind": "docker_isolated_runner",
            "isolation_level": "docker_local_isolated",
            "image_ref": "amadeus-thread0/sandbox-phase2:py312",
            "network_policy": "none",
            "workspace_root_kind": "attached_repo_root",
            "argv": ["pytest", "-q", "tests/test_demo.py"],
            "cwd": "E:/repo/amadeus-thread0",
            "allowed_roots": ["E:/repo/amadeus-thread0"],
        },
        "execution_result": {
            "run_id": f"{proposal_id}-run",
            "status": status,
            "exit_code": int(exit_code),
            "stdout_log_ref": f"E:/repo/.amadeus/sandbox-runs/{proposal_id}/stdout.txt",
            "stderr_log_ref": f"E:/repo/.amadeus/sandbox-runs/{proposal_id}/stderr.txt",
            "error_summary": "" if int(exit_code) == 0 else f"process exited with code {exit_code}",
        },
    }


def _browser_takeover_packet() -> dict[str, Any]:
    return {
        "proposal_id": "ap-browser-takeover-smoke",
        "origin": "motive_goal",
        "intent": "browser:fill",
        "status": "blocked",
        "risk": "external_mutation",
        "requires_approval": True,
        "tool_name": "browser_fill",
        "block_reason": "sensitive credential entry requires manual browser takeover",
        "browser_execution_preview": {
            "operation": "fill",
            "profile_id": "thread-browser",
            "page_ref": "page:page-1",
            "requires_manual_takeover": True,
        },
        "browser_execution_result": {
            "run_id": "browser-takeover-run",
            "status": "blocked",
            "profile_id": "thread-browser",
            "page_id": "page-1",
            "tab_id": "tab-1",
            "last_action_status": "manual_takeover_required",
            "manual_takeover_required": True,
            "error_summary": "manual browser takeover required",
        },
    }


def _skill_usage_packet() -> dict[str, Any]:
    return {
        "proposal_id": "ap-skill-usage-smoke",
        "origin": "motive_goal",
        "intent": "tool:search_web",
        "status": "completed",
        "risk": "read",
        "requires_approval": False,
        "tool_name": "search_web",
        "result_summary": "searched source material",
        "skill_effects": [
            {
                "skill_id": "source-ref-anchor-review",
                "name": "Source Ref Anchor Review",
                "status": "completed",
                "operation": "use",
                "use_kind": "source_ref_continuity",
                "tool_name": "search_web",
            }
        ],
    }


def _scenario_specs() -> list[dict[str, Any]]:
    return [
        {
            "id": "completed_sandbox_run_becomes_reusable_procedure",
            "title": "completed_sandbox_run_becomes_reusable_procedure",
            "packets": [_sandbox_packet(proposal_id="ap-sandbox-completed-smoke", status="completed")],
            "body": _sandbox_body(),
        },
        {
            "id": "blocked_command_becomes_boundary_note_not_capability",
            "title": "blocked_command_becomes_boundary_note_not_capability",
            "packets": [_sandbox_packet(proposal_id="ap-sandbox-blocked-smoke", status="blocked", exit_code=3)],
            "body": _sandbox_body(blocked=True),
        },
        {
            "id": "browser_takeover_boundary_resurfaces_as_procedure",
            "title": "browser_takeover_boundary_resurfaces_as_procedure",
            "packets": [_browser_takeover_packet()],
            "body": {
                "active_surface": "tooling",
                "world_surfaces": ["browser", "filesystem"],
                "access_state": {
                    "mode": "native_only",
                    "browser_session": "present",
                    "browser_runtime_state": {
                        "availability": "available",
                        "context_status": "manual_takeover",
                        "last_action_status": "manual_takeover_required",
                        "last_run_id": "browser-takeover-run",
                        "manual_takeover_required": True,
                    },
                },
                "resource_state": {
                    "blocked_packet_count": 1,
                    "artifact_carrier": "browser_page",
                    "active_artifact_kind": "page",
                    "active_artifact_ref": "page:page-1",
                    "active_artifact_label": "Login",
                    "browser_profile_id": "thread-browser",
                    "browser_tab_id": "tab-1",
                },
            },
        },
        {
            "id": "skill_usage_resurfaces_without_registry_pollution",
            "title": "skill_usage_resurfaces_without_registry_pollution",
            "packets": [_skill_usage_packet()],
            "body": {
                "active_surface": "tooling",
                "world_surfaces": ["source_ref"],
                "access_state": {"mode": "tool_enabled"},
                "resource_state": {
                    "completed_packet_count": 1,
                    "artifact_carrier": "source_ref",
                    "active_artifact_kind": "search_result",
                    "active_artifact_ref": "https://docs.example/proc",
                    "active_artifact_label": "Procedural Docs",
                },
            },
        },
        {
            "id": "followup_uses_procedural_hint_but_keeps_approval_required",
            "title": "followup_uses_procedural_hint_but_keeps_approval_required",
            "packets": [_sandbox_packet(proposal_id="ap-followup-procedural-smoke", status="completed")],
            "body": _sandbox_body(),
        },
    ]


def _evaluate_result(result: dict[str, Any]) -> dict[str, Any]:
    scenario_id = str(result.get("id") or "")
    consequence = _dict(result.get("digital_body_consequence"))
    continuity = _dict(consequence.get("procedural_continuity"))
    traces = list(consequence.get("procedural_traces") or continuity.get("traces") or [])
    hint = _dict(consequence.get("procedural_hint"))
    checks: dict[str, dict[str, Any]] = {
        "trace_present": _check("trace_present", bool(traces), f"traces={traces}"),
        "backend_summary_agrees": _check(
            "backend_summary_agrees",
            _dict(_dict(result.get("turn_summary")).get("procedural_growth")).get("traces") == traces,
            "turn_summary procedural traces should match consequence traces",
        ),
    }
    if scenario_id == "completed_sandbox_run_becomes_reusable_procedure":
        checks["completed_sandbox_trace"] = _check(
            "completed_sandbox_trace",
            bool(consequence.get("procedural_growth"))
            and traces[0].get("trace_kind") == "sandbox_execution_pattern"
            and hint.get("must_request_approval") is True
            and hint.get("capability_claim") is True,
            f"consequence={consequence}",
        )
    elif scenario_id == "blocked_command_becomes_boundary_note_not_capability":
        checks["blocked_not_capability"] = _check(
            "blocked_not_capability",
            not bool(consequence.get("procedural_growth"))
            and traces[0].get("trace_kind") == "blocked_boundary_pattern"
            and hint.get("capability_claim") is False,
            f"consequence={consequence}",
        )
    elif scenario_id == "browser_takeover_boundary_resurfaces_as_procedure":
        checks["manual_takeover_preserved"] = _check(
            "manual_takeover_preserved",
            traces[0].get("trace_kind") == "blocked_boundary_pattern"
            and "takeover" in str(hint.get("boundary_note") or "").lower()
            and hint.get("must_request_approval") is True,
            f"hint={hint}",
        )
    elif scenario_id == "skill_usage_resurfaces_without_registry_pollution":
        checks["skill_usage_trace_only"] = _check(
            "skill_usage_trace_only",
            traces[0].get("trace_kind") == "skill_usage_pattern"
            and "skill_registry" not in consequence
            and "installed" not in consequence,
            f"consequence={consequence}",
        )
    elif scenario_id == "followup_uses_procedural_hint_but_keeps_approval_required":
        line = str(result.get("summary_line") or "")
        checks["hint_keeps_approval"] = _check(
            "hint_keeps_approval",
            "procedure=sandbox_execution_pattern" in line
            and "approval" in line
            and hint.get("must_request_approval") is True,
            f"summary_line={line}",
        )
    else:
        checks["known_scenario"] = _check("known_scenario", False, scenario_id)
    return {
        "passed": all(bool(row.get("passed")) for row in checks.values()),
        "checks": checks,
    }


def _run_single_scenario(spec: dict[str, Any]) -> dict[str, Any]:
    started = time.time()
    packets = list(spec.get("packets") or [])
    body = _dict(spec.get("body"))
    consequence = resolve_digital_body_consequence(
        digital_body_state=body,
        action_packets=packets,
    )
    traces = extract_procedural_traces_from_action_packets(packets)
    hint = build_procedural_hint(traces)
    turn_summary = build_evolution_cli_summary(
        action_packets=packets,
        digital_body_state=body,
        digital_body_consequence=consequence,
    )
    result = {
        "id": str(spec.get("id") or ""),
        "title": str(spec.get("title") or ""),
        "duration_s": round(time.time() - started, 3),
        "action_packets": packets,
        "digital_body_consequence": consequence,
        "extracted_traces": traces,
        "extracted_hint": hint,
        "turn_summary": turn_summary,
        "summary_line": build_evolution_summary_line(turn_summary),
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
        f"# Procedural Growth Smokes ({report.get('run_id', 'unknown')})",
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
    for result in report.get("results") or []:
        if not isinstance(result, dict):
            continue
        lines.extend(["", f"## {result.get('title', result.get('id', 'scenario'))}", ""])
        lines.append(f"- Summary Line: `{result.get('summary_line', '')}`")
        checks = _dict(_dict(result.get("evaluation")).get("checks"))
        for check in checks.values():
            if isinstance(check, dict):
                lines.append(f"- `{'pass' if check.get('passed') else 'fail'}` {check.get('name')}: {check.get('detail')}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic procedural growth smoke scenarios.")
    parser.add_argument("--run-tag", default="", help="Optional suffix for report filenames.")
    args = parser.parse_args()

    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    results = [_run_single_scenario(spec) for spec in _scenario_specs()]
    report = _aggregate_smoke_report(run_id=run_id, results=results)
    json_path = REPORT_DIR / f"procedural-growth-smokes-{run_id}.json"
    md_path = REPORT_DIR / f"procedural-growth-smokes-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[procedural-growth-smokes] json={json_path}")
    print(f"[procedural-growth-smokes] md={md_path}")
    print(f"[procedural-growth-smokes] overall_status={report.get('overall_status', 'unknown')}")
    return 0 if str(report.get("overall_status") or "") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
