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

from amadeus_thread0.graph_parts.autonomy_runtime import derive_autonomy_runtime  # noqa: E402
from amadeus_thread0.graph_parts.procedural_planning import build_procedural_planning_bias  # noqa: E402


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
        "trace_id": "proc_phase2_pytest_smoke",
        "trace_kind": "sandbox_execution_pattern",
        "source_proposal_id": "ap-phase2-pytest-smoke",
        "source_run_id": "run-phase2-pytest-smoke",
        "source_tool_name": "execute_workspace_command",
        "status": "completed",
        "procedure_steps": ["inspect cwd", "run bounded command", "read stdout/artifact"],
        "result_summary": "pytest passed",
        "reuse_conditions": ["similar workspace command", "pytest command profile"],
        "boundary_notes": ["requires approval before execution"],
        "confidence": 0.78,
    }
    trace.update(overrides)
    return trace


def _runtime_for_trace(*, text: str, trace: dict[str, Any], access_hints: dict[str, Any] | None = None) -> dict[str, Any]:
    hints = access_hints or _access_hints()
    return derive_autonomy_runtime(
        current_event={
            "kind": "user_utterance",
            "text": text,
            "digital_body_hints": hints,
        },
        behavior_action={},
        behavior_plan={},
        behavior_queue=[],
        interaction_carryover={
            "strength": 0.34,
            "embodied_context": {
                "workspace_root": "E:/repo/amadeus-thread0",
                "sandbox_runner_kind": "docker_isolated_runner",
                "sandbox_isolation_level": "docker_local_isolated",
                "sandbox_image_ref": "amadeus-thread0/sandbox-phase2:py312",
                "sandbox_network_policy": "none",
                "workspace_root_kind": "attached_repo_root",
                "procedural_traces": [trace],
            },
        },
        session_context={"digital_body_hints": hints},
    )


def _scenario_specs() -> list[dict[str, Any]]:
    return [
        {
            "id": "completed_sandbox_trace_guides_pytest_packet_with_approval",
            "title": "completed_sandbox_trace_guides_pytest_packet_with_approval",
            "kind": "runtime",
            "text": "继续跑刚才那类 pytest 检查。",
            "trace": _sandbox_trace(),
        },
        {
            "id": "blocked_trace_becomes_boundary_bias_not_execution",
            "title": "blocked_trace_becomes_boundary_bias_not_execution",
            "kind": "runtime",
            "text": "别再重复刚才被拦住的命令。",
            "trace": _sandbox_trace(
                trace_id="proc_phase2_blocked_smoke",
                trace_kind="blocked_boundary_pattern",
                source_run_id="run-phase2-blocked-smoke",
                status="blocked",
                result_summary="pip install was blocked",
                reuse_conditions=["similar workspace command"],
                boundary_notes=["package install is blocked in the sandbox"],
                confidence=0.67,
            ),
        },
        {
            "id": "browser_takeover_trace_surfaces_manual_boundary",
            "title": "browser_takeover_trace_surfaces_manual_boundary",
            "kind": "runtime",
            "text": "继续刚才浏览器登录那一步。",
            "trace": {
                "trace_id": "proc_phase2_browser_smoke",
                "trace_kind": "blocked_boundary_pattern",
                "source_proposal_id": "ap-browser-smoke",
                "source_run_id": "run-browser-smoke",
                "source_tool_name": "browser_fill",
                "status": "blocked",
                "procedure_steps": [
                    "preserve current page/profile",
                    "hand off sensitive step",
                    "resume after manual takeover",
                ],
                "result_summary": "manual browser takeover required",
                "reuse_conditions": ["same browser profile/page family"],
                "boundary_notes": ["manual browser takeover required"],
                "confidence": 0.61,
            },
        },
        {
            "id": "skill_usage_trace_guides_without_registry_mutation",
            "title": "skill_usage_trace_guides_without_registry_mutation",
            "kind": "bias",
            "text": "继续用刚才那个资料锚点办法查下去。",
            "trace": {
                "trace_id": "proc_phase2_skill_smoke",
                "trace_kind": "skill_usage_pattern",
                "source_proposal_id": "ap-skill-smoke",
                "source_run_id": "ap-skill-smoke",
                "source_tool_name": "search_web",
                "status": "completed",
                "procedure_steps": ["match active skill", "apply skill guidance", "preserve artifact continuity"],
                "result_summary": "used source-ref skill guidance",
                "reuse_conditions": ["similar skill-supported task"],
                "boundary_notes": ["skill registry truth stays outside autobiographical memory"],
                "confidence": 0.7,
            },
        },
        {
            "id": "low_confidence_or_mismatched_trace_is_ignored",
            "title": "low_confidence_or_mismatched_trace_is_ignored",
            "kind": "bias_mismatch",
            "text": "继续跑 pytest。",
            "trace": _sandbox_trace(confidence=0.2),
        },
    ]


def _evaluate_result(result: dict[str, Any]) -> dict[str, Any]:
    scenario_id = str(result.get("id") or "")
    runtime = _dict(result.get("runtime"))
    bias = _dict(result.get("bias") or runtime.get("procedural_planning"))
    packets = list(runtime.get("action_packets") or [])
    first_packet = _dict(packets[0]) if packets else {}
    checks: dict[str, dict[str, Any]] = {
        "known_bias_shape": _check(
            "known_bias_shape",
            scenario_id == "low_confidence_or_mismatched_trace_is_ignored" or bool(bias.get("bias_kind")),
            f"bias={bias}",
        )
    }
    if scenario_id == "completed_sandbox_trace_guides_pytest_packet_with_approval":
        checks["pytest_packet_approval"] = _check(
            "pytest_packet_approval",
            bias.get("bias_kind") == "sandbox_execute"
            and first_packet.get("tool_name") == "execute_workspace_command"
            and first_packet.get("status") == "awaiting_approval"
            and bool(first_packet.get("requires_approval"))
            and first_packet.get("risk") == "external_mutation"
            and _dict(first_packet.get("execution_spec")).get("executor") == "pytest",
            f"runtime={runtime}",
        )
    elif scenario_id == "blocked_trace_becomes_boundary_bias_not_execution":
        checks["blocked_not_execution"] = _check(
            "blocked_not_execution",
            bias.get("bias_kind") == "boundary_only"
            and bias.get("capability_claim") is False
            and first_packet.get("tool_name") != "execute_workspace_command",
            f"runtime={runtime}",
        )
    elif scenario_id == "browser_takeover_trace_surfaces_manual_boundary":
        checks["manual_takeover_no_mutation"] = _check(
            "manual_takeover_no_mutation",
            bias.get("bias_kind") == "browser_manual_takeover"
            and bias.get("must_request_approval") is True
            and all(_dict(packet).get("tool_name") != "browser_fill" for packet in packets),
            f"runtime={runtime}",
        )
    elif scenario_id == "skill_usage_trace_guides_without_registry_mutation":
        checks["skill_guidance_no_registry_mutation"] = _check(
            "skill_guidance_no_registry_mutation",
            bias.get("bias_kind") == "skill_guidance"
            and "registry" not in bias
            and "skill_operation" not in bias,
            f"bias={bias}",
        )
    elif scenario_id == "low_confidence_or_mismatched_trace_is_ignored":
        checks["ignored"] = _check("ignored", bias == {}, f"bias={bias}")
    else:
        checks["known_scenario"] = _check("known_scenario", False, scenario_id)
    return {
        "passed": all(bool(row.get("passed")) for row in checks.values()),
        "checks": checks,
    }


def _run_single_scenario(spec: dict[str, Any]) -> dict[str, Any]:
    started = time.time()
    kind = str(spec.get("kind") or "")
    text = str(spec.get("text") or "")
    trace = _dict(spec.get("trace"))
    result = {
        "id": str(spec.get("id") or ""),
        "title": str(spec.get("title") or ""),
        "duration_s": 0.0,
        "bias": {},
        "runtime": {},
    }
    if kind == "runtime":
        result["runtime"] = _runtime_for_trace(text=text, trace=trace)
        result["bias"] = _dict(_dict(result["runtime"]).get("procedural_planning"))
    elif kind == "bias_mismatch":
        result["bias"] = build_procedural_planning_bias(
            current_event={"text": text},
            embodied_context={
                "workspace_root": "E:/repo/amadeus-thread0",
                "sandbox_runner_kind": "docker_isolated_runner",
                "sandbox_isolation_level": "docker_local_isolated",
                "sandbox_network_policy": "none",
                "procedural_traces": [trace],
            },
            access_hints=_access_hints(workspace_root="E:/runtime/workspaces/current"),
        )
    else:
        result["bias"] = build_procedural_planning_bias(
            current_event={"text": text},
            embodied_context={
                "workspace_root": "E:/repo/amadeus-thread0",
                "sandbox_runner_kind": "docker_isolated_runner",
                "sandbox_isolation_level": "docker_local_isolated",
                "sandbox_network_policy": "none",
                "procedural_traces": [trace],
            },
            access_hints=_access_hints(),
        )
    result["duration_s"] = round(time.time() - started, 3)
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
        f"# Procedural Growth Phase 2 Smokes ({report.get('run_id', 'unknown')})",
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
        lines.append(f"- Bias Kind: `{_dict(result.get('bias')).get('bias_kind', '')}`")
        checks = _dict(_dict(result.get("evaluation")).get("checks"))
        for check in checks.values():
            if isinstance(check, dict):
                lines.append(f"- `{'pass' if check.get('passed') else 'fail'}` {check.get('name')}: {check.get('detail')}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic procedural growth phase 2 smoke scenarios.")
    parser.add_argument("--run-tag", default="", help="Optional suffix for report filenames.")
    args = parser.parse_args()

    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    results = [_run_single_scenario(spec) for spec in _scenario_specs()]
    report = _aggregate_smoke_report(run_id=run_id, results=results)
    json_path = REPORT_DIR / f"procedural-growth-phase2-smokes-{run_id}.json"
    md_path = REPORT_DIR / f"procedural-growth-phase2-smokes-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[procedural-growth-phase2-smokes] json={json_path}")
    print(f"[procedural-growth-phase2-smokes] md={md_path}")
    print(f"[procedural-growth-phase2-smokes] overall_status={report.get('overall_status', 'unknown')}")
    return 0 if str(report.get("overall_status") or "") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
