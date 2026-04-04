from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from amadeus_thread0.evolution_engine.reconsolidation import build_reconsolidation_snapshot  # noqa: E402
from amadeus_thread0.graph_parts.action_packets import build_tool_action_packet  # noqa: E402
from amadeus_thread0.utils.tools import (  # noqa: E402
    build_workspace_command_execution_spec,
    execute_workspace_command,
    inspect_workspace_path,
    preview_workspace_command_execution,
)

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
TMP_ROOT = PROJECT_ROOT / "evals" / "_tmp" / "sandbox-embodied-execution"
TMP_ROOT.mkdir(parents=True, exist_ok=True)


def _dict(v: Any) -> dict[str, Any]:
    return dict(v) if isinstance(v, dict) else {}


def _list(v: Any) -> list[Any]:
    return list(v) if isinstance(v, list) else []


def _env(runtime_dir: Path) -> dict[str, str]:
    return {"AMADEUS_DATA_DIR": str(runtime_dir), "AMADEUS_MODEL_PROVIDER": "openai_compatible"}


def _invoke(tool: Any, args: dict[str, Any], *, runtime_dir: Path) -> dict[str, Any]:
    with patch.dict(os.environ, _env(runtime_dir), clear=False):
        return tool.invoke(args)


def _workspace_hints(workspace: Path) -> dict[str, Any]:
    return {
        "filesystem_state": "writable",
        "sandbox_mode": "restricted",
        "active_artifact_kind": "workspace",
        "active_artifact_ref": str(workspace),
        "active_artifact_label": workspace.name,
        "workspace_root": str(workspace),
        "sandbox_state": {
            "availability": "restricted",
            "allowed_roots": [str(workspace)],
            "execution_policy": "approval_required",
            "runner_kind": "local_restricted_runner",
            "isolation_level": "host_local_restricted",
            "arbitrary_execution": False,
        },
    }


def _body_from_tool(payload: dict[str, Any], *, surface: str = "tooling") -> dict[str, Any]:
    access = _dict(payload.get("access_state"))
    resource = _dict(payload.get("resource_state"))
    if _dict(access.get("sandbox_state")):
        access["mode"] = "tool_enabled"
        access["missing_access"] = []
        access["requestable_access"] = []
        access["access_acquire_proposals"] = []
        access["selected_access_proposal"] = {}
        access["external_mutation_pending"] = False
        permission = _dict(access.get("permission_state"))
        permission["approval_state"] = "open"
        permission["pending_approval_count"] = 0
        permission["external_mutation_pending"] = False
        permission["missing_access"] = []
        permission["requestable_access"] = []
        permission["access_acquire_proposals"] = []
        permission["selected_access_proposal"] = {}
        permission["resolved_grants"] = _list(permission.get("resolved_grants"))
        permission["pending_grants"] = []
        access["permission_state"] = permission
    channels = ["language", "structured_action", "tooling"]
    if str(access.get("mode") or "").strip().lower() == "approval_pending":
        surface = "approval_gate"
        channels = ["language", "structured_action", "approval_gate", "tooling"]
    worlds = ["filesystem"]
    if _dict(access.get("sandbox_state")):
        worlds.append("sandbox")
    return {
        "active_surface": surface,
        "perception_channels": ["dialogue", "filesystem"],
        "action_channels": channels,
        "world_surfaces": worlds,
        "access_state": access,
        "resource_state": resource,
    }


def _pending_body(workspace: Path, preview: dict[str, Any], *, mode: str = "approval_pending", status: str = "awaiting_operator_approval") -> dict[str, Any]:
    pending_count = 1 if mode == "approval_pending" else 0
    body = _body_from_tool(
        {
            "access_state": {
                "mode": mode,
                "pending_approval_count": pending_count,
                "external_mutation_pending": mode == "approval_pending",
                "filesystem_state": "writable",
                "sandbox_mode": "restricted",
                "permission_state": {
                    "approval_state": "approval_pending" if mode == "approval_pending" else "open",
                    "pending_approval_count": pending_count,
                    "external_mutation_pending": mode == "approval_pending",
                },
                "sandbox_state": {
                    "availability": "restricted",
                    "allowed_roots": _list(preview.get("allowed_roots")) or [str(workspace)],
                    "execution_policy": "approval_required",
                    "last_status": status,
                    "runner_kind": str(preview.get("runner_kind") or "local_restricted_runner"),
                    "isolation_level": str(preview.get("isolation_level") or "host_local_restricted"),
                    "last_command_profile": "",
                    "last_exit_code": 0,
                    "last_run_id": "",
                    "arbitrary_execution": False,
                },
            },
            "resource_state": {
                "action_packet_count": 1,
                "pending_approval_count": pending_count,
                "completed_packet_count": 0,
                "artifact_continuity": "attached",
                "active_artifact_kind": "workspace",
                "active_artifact_ref": str(workspace),
                "active_artifact_label": workspace.name,
                "artifact_carrier": "filesystem",
                "workspace_root": str(workspace),
            },
        }
    )
    body["access_state"]["mode"] = mode
    return body


def _intent(proposal_id: str, mode: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "origin": "counterpart_request",
        "reason": "sandbox embodied execution phase 1",
        "primary_proposal_id": proposal_id,
    }


def _turn_summary(body: dict[str, Any], consequence: dict[str, Any], carryover: dict[str, Any]) -> dict[str, Any]:
    access = _dict(body.get("access_state"))
    resource = _dict(body.get("resource_state"))
    sandbox = _dict(access.get("sandbox_state"))
    return {
        "current_turn": {
            "digital_body_surface": str(body.get("active_surface") or ""),
            "digital_body_access_mode": str(access.get("mode") or ""),
            "digital_body_workspace_root": str(resource.get("workspace_root") or ""),
            "digital_body_active_artifact_ref": str(resource.get("active_artifact_ref") or ""),
            "digital_body_consequence_kind": str(consequence.get("kind") or ""),
            "digital_body_consequence_summary": str(consequence.get("summary") or ""),
            "sandbox_last_run_id": str(sandbox.get("last_run_id") or ""),
            "sandbox_last_exit_code": int(sandbox.get("last_exit_code") or 0),
        },
        "interaction_carryover": dict(carryover or {}),
    }


def _step(step_id: str, final_text: str, body: dict[str, Any], packet: dict[str, Any], *, mode: str, trace: list[dict[str, Any]] | None = None, pending: dict[str, Any] | None = None, carryover: dict[str, Any] | None = None) -> dict[str, Any]:
    carry = dict(carryover or {})
    snapshot = build_reconsolidation_snapshot(
        current_event={"kind": "user_utterance"},
        appraisal={"interaction_frame": "task"},
        world_model_state={},
        semantic_narrative_profile={},
        latent_state={"self_coherence": 0.82},
        emotion_state={"label": "focused"},
        bond_state={"trust": 0.60},
        behavior_action={"interaction_mode": "tooling"},
        interaction_carryover=carry,
        autonomy_intent=_intent(str(packet.get("proposal_id") or ""), mode),
        action_packets=[packet],
        action_trace=trace or [],
        digital_body_state=body,
    )
    consequence = _dict(snapshot.get("digital_body_consequence"))
    autonomy = {
        "intent": _intent(str(packet.get("proposal_id") or ""), mode),
        "action_packets": [packet],
        "pending_approval": dict(pending or {}),
        "execution_trace": list(trace or []),
        "block_reason": str(packet.get("block_reason") or ""),
    }
    return {
        "id": step_id,
        "final_text": final_text,
        "autonomy": autonomy,
        "digital_body": body,
        "digital_body_consequence": consequence,
        "key_packet_trace": [packet],
        "turn_summary": _turn_summary(body, consequence, carry),
        "reconsolidation_snapshot": snapshot,
        "interaction_carryover": carry,
    }


def _sc_workspace_pytest_after_approval(run_root: Path) -> dict[str, Any]:
    root = run_root / "workspace_pytest_after_approval"
    workspace = root / "runtime" / "workspaces" / "lab-notes"
    (workspace / "tests").mkdir(parents=True, exist_ok=True)
    (workspace / "tests" / "test_smoke_case.py").write_text("def test_workspace_smoke_case():\n    assert 2 + 2 == 4\n", encoding="utf-8")
    proposal_id = "ap-sandbox-pytest-1"
    args = {"argv": ["pytest", "-q", "tests/test_smoke_case.py"], "cwd": ".", "writes_expected": False, "expected_artifacts": [], "proposal_id": proposal_id, "access_hints": _workspace_hints(workspace)}
    payload = _invoke(execute_workspace_command, args, runtime_dir=root / "runtime")
    preview = _dict(payload.get("execution_preview")) or preview_workspace_command_execution("execute_workspace_command", args)
    spec = _dict(payload.get("execution_spec")) or build_workspace_command_execution_spec(args)
    pending_packet = build_tool_action_packet(tool_name="execute_workspace_command", proposal_id=proposal_id, args={"argv": args["argv"], "cwd": args["cwd"]}, action="approve", status="awaiting_approval", result_summary="Awaiting approval before running pytest.", execution_spec=spec, execution_preview=preview)
    pending = _step("awaiting_approval", "这次受限执行先挂在审批里，命令预览已经固定下来了。", _pending_body(workspace, preview), pending_packet, mode="approval_pending", trace=[{"proposal_id": proposal_id, "event": "approval_requested", "tool_name": "execute_workspace_command", "status": "awaiting_approval"}], pending=pending_packet)
    completed_packet = build_tool_action_packet(tool_name="execute_workspace_command", proposal_id=proposal_id, args={"argv": args["argv"], "cwd": args["cwd"]}, action="approve", status="completed", result_summary=str(payload.get("summary") or ""), execution_spec=_dict(payload.get("execution_spec")), execution_preview=_dict(payload.get("execution_preview")), execution_result=_dict(payload.get("execution_result")))
    completed = _step("completed", "pytest 已经在当前 workspace 里跑完了，结果可以顺着日志继续看。", _body_from_tool(payload), completed_packet, mode="execute", trace=[{"proposal_id": proposal_id, "event": "approval_requested", "tool_name": "execute_workspace_command", "status": "awaiting_approval"}, {"proposal_id": proposal_id, "event": "approval_resolved", "tool_name": "execute_workspace_command", "status": "approved"}, {"proposal_id": proposal_id, "event": "tool_completed", "tool_name": "execute_workspace_command", "status": "completed"}])
    return {"id": "workspace_pytest_after_approval", "title": "workspace_pytest_after_approval", "focus": "Approval-gated pytest should execute in-place with the same preview/spec carried through resume.", "steps": [pending, completed]}


def _sc_workspace_script_generates_artifact(run_root: Path) -> dict[str, Any]:
    root = run_root / "workspace_script_generates_artifact"
    workspace = root / "runtime" / "workspaces" / "lab-notes"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "emit_artifact.py").write_text("from pathlib import Path\nout = Path('notes/generated.txt')\nout.parent.mkdir(parents=True, exist_ok=True)\nout.write_text('sandbox artifact\\n', encoding='utf-8')\nprint('generated artifact')\n", encoding="utf-8")
    proposal_id = "ap-sandbox-artifact-1"
    args = {"argv": ["python", "emit_artifact.py"], "cwd": ".", "writes_expected": True, "expected_artifacts": ["notes/generated.txt"], "proposal_id": proposal_id, "access_hints": _workspace_hints(workspace)}
    payload = _invoke(execute_workspace_command, args, runtime_dir=root / "runtime")
    preview = _dict(payload.get("execution_preview")) or preview_workspace_command_execution("execute_workspace_command", args)
    spec = _dict(payload.get("execution_spec")) or build_workspace_command_execution_spec(args)
    pending_packet = build_tool_action_packet(tool_name="execute_workspace_command", proposal_id=proposal_id, args={"argv": args["argv"], "cwd": args["cwd"]}, action="approve", status="awaiting_approval", result_summary="Artifact-generating script is waiting for approval.", execution_spec=spec, execution_preview=preview)
    pending = _step("awaiting_approval", "会写文件的执行先停在审批前面，预览已经固定好了。", _pending_body(workspace, preview), pending_packet, mode="approval_pending", trace=[{"proposal_id": proposal_id, "event": "approval_requested", "tool_name": "execute_workspace_command", "status": "awaiting_approval"}], pending=pending_packet)
    completed_packet = build_tool_action_packet(tool_name="execute_workspace_command", proposal_id=proposal_id, args={"argv": args["argv"], "cwd": args["cwd"]}, action="approve", status="completed", result_summary=str(payload.get("summary") or ""), execution_spec=_dict(payload.get("execution_spec")), execution_preview=_dict(payload.get("execution_preview")), execution_result=_dict(payload.get("execution_result")))
    completed = _step("completed", "脚本已经真实执行完成，产物和日志都落在同一个 workspace 里。", _body_from_tool(payload), completed_packet, mode="execute", trace=[{"proposal_id": proposal_id, "event": "approval_requested", "tool_name": "execute_workspace_command", "status": "awaiting_approval"}, {"proposal_id": proposal_id, "event": "approval_resolved", "tool_name": "execute_workspace_command", "status": "approved"}, {"proposal_id": proposal_id, "event": "tool_completed", "tool_name": "execute_workspace_command", "status": "completed"}])
    return {"id": "workspace_script_generates_artifact", "title": "workspace_script_generates_artifact", "focus": "A workspace-local script should produce a real artifact and promote it into the active filesystem surface.", "steps": [pending, completed]}


def _sc_disallowed_command_or_outside_root_blocked(run_root: Path) -> dict[str, Any]:
    root = run_root / "disallowed_command_or_outside_root_blocked"
    workspace = root / "runtime" / "workspaces" / "lab-notes"
    workspace.mkdir(parents=True, exist_ok=True)
    proposal_id = "ap-sandbox-blocked-1"
    args = {"argv": ["python", "../outside.py"], "cwd": ".", "writes_expected": False, "expected_artifacts": [], "proposal_id": proposal_id, "access_hints": _workspace_hints(workspace)}
    preview = preview_workspace_command_execution("execute_workspace_command", args)
    packet = build_tool_action_packet(tool_name="execute_workspace_command", proposal_id=proposal_id, args={"argv": args["argv"], "cwd": args["cwd"]}, action="approve", status="blocked", result_summary="The runner rejected the command because it would escape the approved workspace root.", block_reason=str(preview.get("validation_error") or ""), execution_preview=preview)
    blocked = _step("blocked", "这个命令越过了当前 workspace 边界，所以在执行前就被挡住了。", _pending_body(workspace, preview, mode="blocked", status="blocked"), packet, mode="blocked", trace=[{"proposal_id": proposal_id, "event": "sandbox_validation_blocked", "tool_name": "execute_workspace_command", "status": "blocked"}])
    return {"id": "disallowed_command_or_outside_root_blocked", "title": "disallowed_command_or_outside_root_blocked", "focus": "Commands that escape the approved workspace must block before any execution fact is written.", "steps": [blocked]}


def _sc_followup_continue_from_last_run_log_or_artifact(run_root: Path) -> dict[str, Any]:
    root = run_root / "followup_continue_from_last_run_log_or_artifact"
    workspace = root / "runtime" / "workspaces" / "lab-notes"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "emit_followup_artifact.py").write_text("from pathlib import Path\nout = Path('notes/followup.txt')\nout.parent.mkdir(parents=True, exist_ok=True)\nout.write_text('followup-ready\\n', encoding='utf-8')\nprint('followup artifact emitted')\n", encoding="utf-8")
    proposal_id = "ap-sandbox-followup-1"
    args = {"argv": ["python", "emit_followup_artifact.py"], "cwd": ".", "writes_expected": True, "expected_artifacts": ["notes/followup.txt"], "proposal_id": proposal_id, "access_hints": _workspace_hints(workspace)}
    payload = _invoke(execute_workspace_command, args, runtime_dir=root / "runtime")
    preview = _dict(payload.get("execution_preview")) or preview_workspace_command_execution("execute_workspace_command", args)
    spec = _dict(payload.get("execution_spec")) or build_workspace_command_execution_spec(args)
    pending_packet = build_tool_action_packet(tool_name="execute_workspace_command", proposal_id=proposal_id, args={"argv": args["argv"], "cwd": args["cwd"]}, action="approve", status="awaiting_approval", result_summary="The run is waiting for approval before writing its artifact.", execution_spec=spec, execution_preview=preview)
    pending = _step("awaiting_approval", "写出产物的执行还在审批前。", _pending_body(workspace, preview), pending_packet, mode="approval_pending", trace=[{"proposal_id": proposal_id, "event": "approval_requested", "tool_name": "execute_workspace_command", "status": "awaiting_approval"}], pending=pending_packet)
    executed_packet = build_tool_action_packet(tool_name="execute_workspace_command", proposal_id=proposal_id, args={"argv": args["argv"], "cwd": args["cwd"]}, action="approve", status="completed", result_summary=str(payload.get("summary") or ""), execution_spec=_dict(payload.get("execution_spec")), execution_preview=_dict(payload.get("execution_preview")), execution_result=_dict(payload.get("execution_result")))
    executed = _step("executed", "刚才那次受限执行已经跑完了，后面可以顺着它留下的产物继续。", _body_from_tool(payload), executed_packet, mode="execute", trace=[{"proposal_id": proposal_id, "event": "approval_requested", "tool_name": "execute_workspace_command", "status": "awaiting_approval"}, {"proposal_id": proposal_id, "event": "approval_resolved", "tool_name": "execute_workspace_command", "status": "approved"}, {"proposal_id": proposal_id, "event": "tool_completed", "tool_name": "execute_workspace_command", "status": "completed"}])
    rel = (_list(payload.get("produced_artifact_relpaths")) or [".amadeus/sandbox-runs/ap-sandbox-followup-1/stdout.txt"])[0]
    inspect_payload = _invoke(inspect_workspace_path, {"relative_path": rel, "access_hints": _dict(payload.get("access_hints"))}, runtime_dir=root / "runtime")
    inspect_packet = build_tool_action_packet(tool_name="inspect_workspace_path", proposal_id="ap-followup-inspect-1", args={"relative_path": rel}, status="completed", result_summary=str(inspect_payload.get("summary") or ""))
    followup = _step("followup_continue", "我先把刚才那次运行留下的文件重新接回当前工作面。", _body_from_tool(inspect_payload), inspect_packet, mode="continue", trace=[{"proposal_id": proposal_id, "event": "tool_completed", "tool_name": "execute_workspace_command", "status": "completed"}, {"proposal_id": "ap-followup-inspect-1", "event": "tool_completed", "tool_name": "inspect_workspace_path", "status": "completed"}], carryover={"mode": "task_window", "note": "Continue from the last sandbox execution artifact.", "embodied_context": _dict(executed.get("digital_body_consequence"))})
    return {"id": "followup_continue_from_last_run_log_or_artifact", "title": "followup_continue_from_last_run_log_or_artifact", "focus": "A later turn should keep the last run identity and continue from its real artifact or logs.", "steps": [pending, executed, followup]}


def _scenario_specs(run_root: Path) -> list[dict[str, Any]]:
    return [
        _sc_workspace_pytest_after_approval(run_root),
        _sc_workspace_script_generates_artifact(run_root),
        _sc_disallowed_command_or_outside_root_blocked(run_root),
        _sc_followup_continue_from_last_run_log_or_artifact(run_root),
    ]


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def _evaluate(result: dict[str, Any]) -> dict[str, Any]:
    sid = str(result.get("id") or "")
    steps = _list(result.get("steps"))
    if sid == "workspace_pytest_after_approval":
        pending, completed = _dict(steps[0]), _dict(steps[-1])
        p = _dict((_list(_dict(pending.get("autonomy")).get("action_packets")) or [{}])[0])
        c = _dict((_list(_dict(completed.get("autonomy")).get("action_packets")) or [{}])[0])
        er = _dict(c.get("execution_result"))
        checks = [
            _check("approval_preview_present", bool(_dict(_dict(pending.get("autonomy")).get("pending_approval")).get("execution_preview")), str(_dict(pending.get("autonomy")).get("pending_approval"))),
            _check("proposal_and_spec_stable", p.get("proposal_id") == c.get("proposal_id") and _dict(p.get("execution_spec")) == _dict(c.get("execution_spec")), f"pending={p} completed={c}"),
            _check("final_execution_completed", c.get("status") == "completed" and _dict(completed.get("digital_body_consequence")).get("kind") == "sandbox_execution_completed" and int(er.get("exit_code", -1)) == 0, str(completed)),
            _check("logs_exist", Path(str(er.get("stdout_log_ref") or "")).exists() and Path(str(er.get("stderr_log_ref") or "")).exists(), str(er)),
        ]
    elif sid == "workspace_script_generates_artifact":
        completed = _dict(steps[-1])
        packet = _dict((_list(_dict(completed.get("autonomy")).get("action_packets")) or [{}])[0])
        er = _dict(packet.get("execution_result"))
        resource = _dict(_dict(completed.get("digital_body")).get("resource_state"))
        produced = _list(er.get("produced_artifacts"))
        checks = [
            _check("produced_artifact_exists", bool(produced) and all(Path(path).exists() for path in produced), str(produced)),
            _check("active_artifact_promoted", resource.get("active_artifact_kind") == "file" and str(resource.get("active_artifact_ref") or "") in produced, str(resource)),
            _check("sandbox_consequence_completed", _dict(completed.get("digital_body_consequence")).get("kind") == "sandbox_execution_completed", str(completed.get("digital_body_consequence"))),
            _check("turn_summary_matches_artifact", _dict(_dict(completed.get("turn_summary")).get("current_turn")).get("digital_body_consequence_kind") == "sandbox_execution_completed", str(completed.get("turn_summary"))),
        ]
    elif sid == "disallowed_command_or_outside_root_blocked":
        blocked = _dict(steps[-1])
        autonomy = _dict(blocked.get("autonomy"))
        packet = _dict((_list(autonomy.get("action_packets")) or [{}])[0])
        preview = _dict(packet.get("execution_preview"))
        checks = [
            _check("validation_context_present", bool(_list(preview.get("argv"))) and bool(str(packet.get("block_reason") or "").strip()), f"preview={preview}, block_reason={packet.get('block_reason')}"),
            _check("execution_not_started", not _dict(packet.get("execution_result")) and not _dict(autonomy.get("pending_approval")), str(packet)),
            _check("blocked_fact_is_honest", packet.get("status") == "blocked" and _dict(blocked.get("digital_body_consequence")).get("kind") == "sandbox_execution_blocked", str(blocked.get("digital_body_consequence"))),
            _check("sandbox_state_blocked", _dict(_dict(blocked.get("digital_body")).get("access_state")).get("mode") == "blocked", str(blocked.get("digital_body"))),
        ]
    else:
        executed, followup = _dict(steps[1]), _dict(steps[-1])
        ep = _dict((_list(_dict(executed.get("autonomy")).get("action_packets")) or [{}])[0])
        fp = _dict((_list(_dict(followup.get("autonomy")).get("action_packets")) or [{}])[0])
        er = _dict(ep.get("execution_result"))
        access = _dict(_dict(followup.get("digital_body")).get("access_state"))
        resource = _dict(_dict(followup.get("digital_body")).get("resource_state"))
        produced = _list(er.get("produced_artifacts"))
        expected_ref = produced[0] if produced else str(er.get("stdout_log_ref") or "")
        checks = [
            _check("run_identity_preserved", str(_dict(access.get("sandbox_state")).get("last_run_id") or "") == str(er.get("run_id") or ""), str(access)),
            _check("followup_reads_real_artifact_or_log", str(resource.get("active_artifact_ref") or "") == expected_ref, str(resource)),
            _check("followup_is_read_not_reexecute", fp.get("tool_name") == "inspect_workspace_path" and _dict(followup.get("digital_body_consequence")).get("kind") == "workspace_path_inspected", str(followup.get("digital_body_consequence"))),
            _check("followup_keeps_workspace_and_exit_code", bool(str(resource.get("workspace_root") or "").strip()) and int(_dict(access.get("sandbox_state")).get("last_exit_code", -1)) == 0, str(access)),
        ]
    return {"passed": all(item["passed"] for item in checks), "checks": checks}


def _run_single_scenario(spec: dict[str, Any]) -> dict[str, Any]:
    start = time.time()
    result = {k: spec[k] for k in ("id", "title", "focus")}
    result["duration_s"] = round(time.time() - start, 3)
    result["steps"] = list(spec.get("steps") or [])
    final_step = _dict(result["steps"][-1]) if result["steps"] else {}
    result["final_text"] = str(final_step.get("final_text") or "")
    result["autonomy"] = _dict(final_step.get("autonomy"))
    result["digital_body"] = _dict(final_step.get("digital_body"))
    result["digital_body_consequence"] = _dict(final_step.get("digital_body_consequence"))
    result["key_packet_trace"] = _list(final_step.get("key_packet_trace"))
    result["evaluation"] = _evaluate(result)
    return result


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [f"# Sandbox Embodied Execution Smokes ({report['run_id']})", "", f"Generated at: {report['generated_at']}", f"Overall Status: `{report['overall_status']}`", f"Passed: `{report['passed']}`", f"Failed: `{report['failed']}`", "", "## Scenario Summary", "", "| Scenario | Status | Duration (s) |", "| --- | --- | ---: |"]
    for result in report.get("results") or []:
        status = "passed" if _dict(result.get("evaluation")).get("passed") else "failed"
        lines.append(f"| `{result.get('id', '')}` | `{status}` | {float(result.get('duration_s') or 0.0):.3f} |")
    for result in report.get("results") or []:
        evaluation = _dict(result.get("evaluation"))
        lines.extend(["", f"## {result.get('title', result.get('id', 'scenario'))}", "", f"- Focus: {result.get('focus', '')}", f"- Status: `{'passed' if evaluation.get('passed') else 'failed'}`", f"- Final Text: `{str(result.get('final_text') or '').strip()}`", f"- Autonomy: `{json.dumps(_dict(result.get('autonomy')), ensure_ascii=False)}`", f"- Digital Body: `{json.dumps(_dict(result.get('digital_body')), ensure_ascii=False)}`", f"- Digital Body Consequence: `{json.dumps(_dict(result.get('digital_body_consequence')), ensure_ascii=False)}`", f"- Key Packet Trace: `{json.dumps(_list(result.get('key_packet_trace')), ensure_ascii=False)}`", "- Checks:"])
        for check in evaluation.get("checks") or []:
            lines.append(f"  - `{'pass' if check.get('passed') else 'fail'}` {check.get('name', '')}: {check.get('detail', '')}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run sandbox embodied execution smoke scenarios.")
    parser.add_argument("--run-tag", default="")
    parser.add_argument("--scenario", action="append", default=[])
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    run_root = TMP_ROOT / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    requested = {str(item or "").strip() for item in _list(args.scenario) if str(item or "").strip()}
    specs = _scenario_specs(run_root)
    if requested:
        specs = [spec for spec in specs if str(spec.get("id") or "") in requested]
        if not specs:
            available = ", ".join(sorted(str(spec.get("id") or "") for spec in _scenario_specs(run_root)))
            raise SystemExit(f"No sandbox smoke scenarios matched {sorted(requested)!r}. Available: {available}")
    results = [_run_single_scenario(spec) for spec in specs]
    passed = len([result for result in results if _dict(result.get("evaluation")).get("passed")])
    failed = len(results) - passed
    report = {"run_id": run_id, "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "overall_status": "passed" if failed == 0 else "failed", "passed": passed, "failed": failed, "results": results, "scenario_artifact_references": [{"id": str(result.get("id") or ""), "title": str(result.get("title") or ""), "status": "passed" if _dict(result.get("evaluation")).get("passed") else "failed"} for result in results]}
    json_path = REPORT_DIR / f"sandbox-embodied-execution-smokes-{run_id}.json"
    md_path = REPORT_DIR / f"sandbox-embodied-execution-smokes-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[sandbox-embodied-execution-smokes] json={json_path}")
    print(f"[sandbox-embodied-execution-smokes] md={md_path}")
    print(f"[sandbox-embodied-execution-smokes] overall_status={report['overall_status']}")


if __name__ == "__main__":
    main()
