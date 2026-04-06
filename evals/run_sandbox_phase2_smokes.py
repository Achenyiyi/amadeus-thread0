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
from amadeus_thread0.runtime.sandbox_runner import ensure_docker_sandbox_image  # noqa: E402
from amadeus_thread0.utils.tools import (  # noqa: E402
    attach_repo_root_access,
    create_workspace_access,
    execute_workspace_command,
    inspect_workspace_path,
    preview_workspace_command_execution,
)

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
TMP_ROOT = PROJECT_ROOT / "evals" / "_tmp" / "sandbox-phase2"
TMP_ROOT.mkdir(parents=True, exist_ok=True)


def _dict(v: Any) -> dict[str, Any]:
    return dict(v) if isinstance(v, dict) else {}


def _list(v: Any) -> list[Any]:
    return list(v) if isinstance(v, list) else []


def _env(runtime_dir: Path) -> dict[str, str]:
    return {
        "AMADEUS_DATA_DIR": str(runtime_dir),
        "AMADEUS_MODEL_PROVIDER": "openai_compatible",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    }


def _invoke(tool: Any, args: dict[str, Any], *, runtime_dir: Path) -> dict[str, Any]:
    with patch.dict(os.environ, _env(runtime_dir), clear=False):
        return tool.invoke(args)


def _preview_workspace_command(args: dict[str, Any], *, runtime_dir: Path) -> dict[str, Any]:
    with patch.dict(os.environ, _env(runtime_dir), clear=False):
        return preview_workspace_command_execution("execute_workspace_command", args)


def _ensure_docker_ready() -> str:
    return ensure_docker_sandbox_image(rebuild=False)


def _runtime_workspace_access(run_root: Path, workspace_name: str) -> dict[str, Any]:
    runtime_dir = run_root / "runtime"
    return _invoke(create_workspace_access, {"workspace_name": workspace_name}, runtime_dir=runtime_dir)


def _body_from_tool(payload: dict[str, Any], *, surface: str = "tooling") -> dict[str, Any]:
    access = _dict(payload.get("access_state"))
    resource = _dict(payload.get("resource_state"))
    if _dict(access.get("sandbox_state")):
        access["mode"] = access.get("mode") or "tool_enabled"
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
    return {
        "active_surface": surface,
        "perception_channels": ["dialogue", "filesystem"],
        "action_channels": channels,
        "world_surfaces": ["filesystem", "sandbox"],
        "access_state": access,
        "resource_state": resource,
    }


def _pending_body(
    workspace_root: Path,
    preview: dict[str, Any],
    *,
    mode: str = "approval_pending",
    status: str = "awaiting_operator_approval",
) -> dict[str, Any]:
    pending_count = 1 if mode == "approval_pending" else 0
    workspace_root_kind = (
        str(preview.get("workspace_root_kind") or "runtime_owned").strip().lower()
        or "runtime_owned"
    )
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
                    "allowed_roots": _list(preview.get("allowed_roots")) or [str(workspace_root)],
                    "execution_policy": "approval_required",
                    "last_status": status,
                    "runner_kind": str(preview.get("runner_kind") or ""),
                    "isolation_level": str(preview.get("isolation_level") or ""),
                    "image_ref": str(preview.get("image_ref") or ""),
                    "network_policy": str(preview.get("network_policy") or ""),
                    "workspace_root_kind": workspace_root_kind,
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
                "active_artifact_ref": str(workspace_root),
                "active_artifact_label": workspace_root.name,
                "artifact_carrier": "filesystem",
                "workspace_root": str(workspace_root),
            },
        }
    )
    body["access_state"]["mode"] = mode
    return body


def _access_pending_body(
    repo_root: Path,
    proposal: dict[str, Any],
    *,
    mode: str,
    requested_help: bool,
) -> dict[str, Any]:
    pending_count = 1 if mode == "approval_pending" else 0
    return {
        "active_surface": "approval_gate" if mode == "approval_pending" else "tooling",
        "perception_channels": ["dialogue", "filesystem"],
        "action_channels": (
            ["language", "structured_action", "approval_gate", "tooling"]
            if mode == "approval_pending"
            else ["language", "structured_action", "tooling"]
        ),
        "world_surfaces": ["filesystem", "sandbox"],
        "access_state": {
            "mode": mode,
            "pending_approval_count": pending_count,
            "external_mutation_pending": mode == "approval_pending",
            "filesystem_state": "missing" if requested_help else "restricted",
            "missing_access": ["filesystem", "workspace_write"] if requested_help else ["filesystem"],
            "requestable_access": (
                ["filesystem", "workspace_write", "human_approval"] if requested_help else []
            ),
            "requested_help": requested_help,
            "access_acquire_proposals": [proposal],
            "selected_access_proposal": proposal,
            "permission_state": {
                "approval_state": "approval_pending" if mode == "approval_pending" else "blocked",
                "pending_approval_count": pending_count,
                "external_mutation_pending": mode == "approval_pending",
                "missing_access": ["filesystem", "workspace_write"] if requested_help else ["filesystem"],
                "requestable_access": (
                    ["filesystem", "workspace_write", "human_approval"] if requested_help else []
                ),
                "access_acquire_proposals": [proposal],
                "selected_access_proposal": proposal,
            },
            "sandbox_state": {
                "availability": "restricted",
                "allowed_roots": [],
                "execution_policy": "approval_required",
                "last_status": "awaiting_operator_approval" if mode == "approval_pending" else "blocked",
                "runner_kind": "",
                "isolation_level": "",
                "image_ref": "",
                "network_policy": "",
                "workspace_root_kind": "attached_repo_root",
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
            "artifact_continuity": "detached",
            "active_artifact_kind": "",
            "active_artifact_ref": "",
            "active_artifact_label": "",
            "artifact_carrier": "filesystem",
            "workspace_root": "",
        },
    }


def _intent(proposal_id: str, mode: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "origin": "counterpart_request",
        "reason": "sandbox embodied execution phase 2",
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
            "sandbox_runner_kind": str(sandbox.get("runner_kind") or ""),
            "workspace_root_kind": str(sandbox.get("workspace_root_kind") or ""),
        },
        "interaction_carryover": dict(carryover or {}),
    }


def _step(
    step_id: str,
    final_text: str,
    body: dict[str, Any],
    packet: dict[str, Any],
    *,
    mode: str,
    trace: list[dict[str, Any]] | None = None,
    pending: dict[str, Any] | None = None,
    carryover: dict[str, Any] | None = None,
) -> dict[str, Any]:
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


def _attach_repo_proposal() -> dict[str, Any]:
    return {
        "target": "filesystem",
        "mode": "operator_attach_repo_root",
        "path_kind": "acquire_existing",
        "summary": "把当前仓库根目录挂接成这轮 coding/research workspace。",
        "operator_action": "批准把当前 git worktree 根目录挂接成 workspace。",
        "grants": ["filesystem", "workspace_write"],
        "requires_operator": True,
    }


def _sc_runtime_workspace_command_runs_in_docker(run_root: Path) -> dict[str, Any]:
    root = run_root / "runtime_workspace_command_runs_in_docker"
    access_payload = _runtime_workspace_access(root, "phase2-lab")
    hints = _dict(access_payload.get("access_hints"))
    workspace = Path(str(access_payload.get("workspace_path") or ""))
    (workspace / "emit_phase2_artifact.py").write_text(
        (
            "from pathlib import Path\n"
            "out = Path('notes/phase2-runtime.txt')\n"
            "out.parent.mkdir(parents=True, exist_ok=True)\n"
            "out.write_text('phase2-runtime\\n', encoding='utf-8')\n"
            "print('phase2-runtime-ready')\n"
        ),
        encoding="utf-8",
    )
    proposal_id = "ap-sandbox-phase2-runtime-1"
    args = {
        "argv": ["python", "emit_phase2_artifact.py"],
        "cwd": ".",
        "writes_expected": True,
        "expected_artifacts": ["notes/phase2-runtime.txt"],
        "proposal_id": proposal_id,
        "access_hints": hints,
    }
    preview = _preview_workspace_command(args, runtime_dir=root / "runtime")
    pending_packet = build_tool_action_packet(
        tool_name="execute_workspace_command",
        proposal_id=proposal_id,
        args={"argv": args["argv"], "cwd": args["cwd"]},
        action="approve",
        status="awaiting_approval",
        result_summary="The docker-isolated workspace command is waiting for approval.",
        execution_preview=preview,
    )
    pending = _step(
        "awaiting_approval",
        "这一步会在 docker 隔离执行面里落地，现在先停在审批前。",
        _pending_body(workspace, preview),
        pending_packet,
        mode="approval_pending",
        trace=[
            {
                "proposal_id": proposal_id,
                "event": "approval_requested",
                "tool_name": "execute_workspace_command",
                "status": "awaiting_approval",
            }
        ],
        pending=pending_packet,
    )
    payload = _invoke(execute_workspace_command, args, runtime_dir=root / "runtime")
    completed_packet = build_tool_action_packet(
        tool_name="execute_workspace_command",
        proposal_id=proposal_id,
        args={"argv": args["argv"], "cwd": args["cwd"]},
        action="approve",
        status="completed",
        result_summary=str(payload.get("summary") or ""),
        execution_spec=_dict(payload.get("execution_spec")),
        execution_preview=_dict(payload.get("execution_preview")),
        execution_result=_dict(payload.get("execution_result")),
    )
    completed = _step(
        "completed",
        "docker 隔离执行已经跑完了，日志和产物都回到了同一个 runtime workspace。",
        _body_from_tool(payload),
        completed_packet,
        mode="execute",
        trace=[
            {
                "proposal_id": proposal_id,
                "event": "approval_requested",
                "tool_name": "execute_workspace_command",
                "status": "awaiting_approval",
            },
            {
                "proposal_id": proposal_id,
                "event": "approval_resolved",
                "tool_name": "execute_workspace_command",
                "status": "approved",
            },
            {
                "proposal_id": proposal_id,
                "event": "tool_completed",
                "tool_name": "execute_workspace_command",
                "status": "completed",
            },
        ],
    )
    return {
        "id": "runtime_workspace_command_runs_in_docker",
        "title": "runtime_workspace_command_runs_in_docker",
        "focus": "A runtime-owned workspace command should execute inside Docker after approval and promote truthful logs/artifacts.",
        "steps": [pending, completed],
    }


def _sc_attach_repo_root_pytest_git_readonly(run_root: Path) -> dict[str, Any]:
    root = run_root / "attach_repo_root_pytest_git_readonly"
    runtime_dir = root / "runtime"
    repo_root = PROJECT_ROOT.resolve(strict=False)
    proposal = _attach_repo_proposal()
    pending_packet = {
        "proposal_id": "ap-attach-repo-root-1",
        "origin": "counterpart_request",
        "intent": "access:request_help",
        "status": "awaiting_approval",
        "risk": "external_mutation",
        "requires_approval": True,
        "expected_effect": proposal["summary"],
        "result_summary": "",
        "writeback_ready": False,
        "access_acquire_proposals": [proposal],
        "selected_access_proposal": proposal,
    }
    pending = _step(
        "attach_pending",
        "当前仓库根目录还没正式挂上来，所以这一步先停在审批门口。",
        _access_pending_body(repo_root, proposal, mode="approval_pending", requested_help=True),
        pending_packet,
        mode="approval_pending",
        trace=[
            {
                "proposal_id": "ap-attach-repo-root-1",
                "event": "approval_requested",
                "tool_name": "attach_repo_root_access",
                "status": "awaiting_approval",
            }
        ],
        pending=pending_packet,
    )
    attach_payload = _invoke(
        attach_repo_root_access,
        {
            "repo_root": str(repo_root),
            "access_hints": {
                "workspace_root": str(repo_root),
                "selected_access_proposal": proposal,
            },
        },
        runtime_dir=runtime_dir,
    )
    attach_packet = {
        "proposal_id": "ap-attach-repo-root-1",
        "origin": "counterpart_request",
        "intent": "access:request_help",
        "status": "completed",
        "risk": "external_mutation",
        "requires_approval": True,
        "tool_name": "attach_repo_root_access",
        "tool_args": {"repo_root": str(repo_root)},
        "result_summary": str(attach_payload.get("summary") or ""),
        "writeback_ready": True,
        "access_acquire_proposals": [proposal],
        "selected_access_proposal": proposal,
    }
    attached = _step(
        "attach_completed",
        "仓库根目录已经挂上来了，后面的执行会沿这个真实 repo root 继续。",
        _body_from_tool(attach_payload),
        attach_packet,
        mode="access_request_resolved",
        trace=[
            {
                "proposal_id": "ap-attach-repo-root-1",
                "event": "approval_requested",
                "tool_name": "attach_repo_root_access",
                "status": "awaiting_approval",
            },
            {
                "proposal_id": "ap-attach-repo-root-1",
                "event": "tool_completed",
                "tool_name": "attach_repo_root_access",
                "status": "completed",
            },
        ],
    )
    attach_hints = _dict(attach_payload.get("access_hints"))
    git_proposal_id = "ap-attach-repo-git-1"
    git_args = {
        "argv": ["git", "rev-parse", "--show-toplevel"],
        "cwd": ".",
        "writes_expected": False,
        "timeout_s": 90,
        "proposal_id": git_proposal_id,
        "access_hints": attach_hints,
    }
    git_payload = _invoke(execute_workspace_command, git_args, runtime_dir=runtime_dir)
    git_packet = build_tool_action_packet(
        tool_name="execute_workspace_command",
        proposal_id=git_proposal_id,
        args={"argv": git_args["argv"], "cwd": git_args["cwd"]},
        action="approve",
        status="completed",
        result_summary=str(git_payload.get("summary") or ""),
        execution_spec=_dict(git_payload.get("execution_spec")),
        execution_preview=_dict(git_payload.get("execution_preview")),
        execution_result=_dict(git_payload.get("execution_result")),
    )
    git_step = _step(
        "git_readonly_completed",
        "先用 docker 里的只读 git 重新确认了当前 worktree 状态。",
        _body_from_tool(git_payload),
        git_packet,
        mode="execute",
        trace=[
            {
                "proposal_id": "ap-attach-repo-root-1",
                "event": "tool_completed",
                "tool_name": "attach_repo_root_access",
                "status": "completed",
            },
            {
                "proposal_id": git_proposal_id,
                "event": "tool_completed",
                "tool_name": "execute_workspace_command",
                "status": "completed",
            },
        ],
    )
    pytest_proposal_id = "ap-attach-repo-pytest-1"
    pytest_args = {
        "argv": ["pytest", "-q", "tests/test_sandbox_phase2_repo_fixture.py"],
        "cwd": ".",
        "writes_expected": False,
        "timeout_s": 180,
        "proposal_id": pytest_proposal_id,
        "access_hints": attach_hints,
    }
    pytest_payload = _invoke(execute_workspace_command, pytest_args, runtime_dir=runtime_dir)
    pytest_packet = build_tool_action_packet(
        tool_name="execute_workspace_command",
        proposal_id=pytest_proposal_id,
        args={"argv": pytest_args["argv"], "cwd": pytest_args["cwd"]},
        action="approve",
        status="completed",
        result_summary=str(pytest_payload.get("summary") or ""),
        execution_spec=_dict(pytest_payload.get("execution_spec")),
        execution_preview=_dict(pytest_payload.get("execution_preview")),
        execution_result=_dict(pytest_payload.get("execution_result")),
    )
    pytest_step = _step(
        "pytest_completed",
        "repo root 挂接后，pytest 也已经在同一个 docker 隔离面里跑完了。",
        _body_from_tool(pytest_payload),
        pytest_packet,
        mode="execute",
        trace=[
            {
                "proposal_id": "ap-attach-repo-root-1",
                "event": "tool_completed",
                "tool_name": "attach_repo_root_access",
                "status": "completed",
            },
            {
                "proposal_id": git_proposal_id,
                "event": "tool_completed",
                "tool_name": "execute_workspace_command",
                "status": "completed",
            },
            {
                "proposal_id": pytest_proposal_id,
                "event": "tool_completed",
                "tool_name": "execute_workspace_command",
                "status": "completed",
            },
        ],
    )
    return {
        "id": "attach_repo_root_pytest_git_readonly",
        "title": "attach_repo_root_pytest_git_readonly",
        "focus": "An operator-approved repo root attach should become the workspace, then support bounded git-readonly and pytest execution in Docker.",
        "steps": [pending, attached, git_step, pytest_step],
    }


def _blocked_step(
    workspace: Path,
    *,
    runtime_dir: Path,
    step_id: str,
    proposal_id: str,
    argv: list[str],
    network_policy: str = "",
    runner_kind: str = "docker_isolated_runner",
) -> dict[str, Any]:
    args = {
        "argv": argv,
        "cwd": ".",
        "writes_expected": False,
        "proposal_id": proposal_id,
        "network_policy": network_policy,
        "runner_kind": runner_kind,
        "access_hints": {
            "workspace_root": str(workspace),
            "workspace_root_kind": "runtime_owned",
            "sandbox_state": {
                "availability": "restricted",
                "allowed_roots": [str(workspace)],
                "execution_policy": "approval_required",
                "runner_kind": "docker_isolated_runner",
                "isolation_level": "docker_local_isolated",
                "network_policy": "none",
                "workspace_root_kind": "runtime_owned",
                "arbitrary_execution": False,
            },
        },
    }
    preview = _preview_workspace_command(args, runtime_dir=runtime_dir)
    packet = build_tool_action_packet(
        tool_name="execute_workspace_command",
        proposal_id=proposal_id,
        args={"argv": argv, "cwd": "."},
        action="approve",
        status="blocked",
        result_summary="The command family is blocked before execution.",
        block_reason=str(preview.get("validation_error") or ""),
        execution_preview=preview,
    )
    return _step(
        step_id,
        "这类命令在 phase 2 里会直接被挡在执行前面。",
        _pending_body(workspace, preview, mode="blocked", status="blocked"),
        packet,
        mode="blocked",
        trace=[
            {
                "proposal_id": proposal_id,
                "event": "sandbox_validation_blocked",
                "tool_name": "execute_workspace_command",
                "status": "blocked",
            }
        ],
    )


def _sc_blocked_command_families_stay_blocked(run_root: Path) -> dict[str, Any]:
    root = run_root / "blocked_command_families_stay_blocked"
    runtime_dir = root / "runtime"
    access_payload = _runtime_workspace_access(root, "phase2-blocked")
    workspace = Path(str(access_payload.get("workspace_path") or ""))
    return {
        "id": "blocked_command_families_stay_blocked",
        "title": "blocked_command_families_stay_blocked",
        "focus": "Package install, shell wrappers, git write, and networked execution requests must stay blocked in phase 2.",
        "steps": [
            _blocked_step(
                workspace,
                runtime_dir=runtime_dir,
                step_id="package_install_blocked",
                proposal_id="ap-phase2-block-pip",
                argv=["python", "-m", "pip", "install", "requests"],
            ),
            _blocked_step(
                workspace,
                runtime_dir=runtime_dir,
                step_id="shell_wrapper_blocked",
                proposal_id="ap-phase2-block-shell",
                argv=["bash", "-lc", "echo hi"],
            ),
            _blocked_step(
                workspace,
                runtime_dir=runtime_dir,
                step_id="git_write_blocked",
                proposal_id="ap-phase2-block-git",
                argv=["git", "commit", "-m", "x"],
            ),
            _blocked_step(
                workspace,
                runtime_dir=runtime_dir,
                step_id="network_policy_blocked",
                proposal_id="ap-phase2-block-network",
                argv=["python", "emit.py"],
                network_policy="host",
            ),
        ],
    }


def _sc_followup_continue_from_last_isolated_run(run_root: Path) -> dict[str, Any]:
    root = run_root / "followup_continue_from_last_isolated_run"
    access_payload = _runtime_workspace_access(root, "phase2-followup")
    hints = _dict(access_payload.get("access_hints"))
    workspace = Path(str(access_payload.get("workspace_path") or ""))
    (workspace / "emit_followup.py").write_text(
        (
            "from pathlib import Path\n"
            "out = Path('notes/followup-phase2.txt')\n"
            "out.parent.mkdir(parents=True, exist_ok=True)\n"
            "out.write_text('followup-phase2\\n', encoding='utf-8')\n"
            "print('followup-phase2-ready')\n"
        ),
        encoding="utf-8",
    )
    proposal_id = "ap-sandbox-phase2-followup-1"
    args = {
        "argv": ["python", "emit_followup.py"],
        "cwd": ".",
        "writes_expected": True,
        "expected_artifacts": ["notes/followup-phase2.txt"],
        "proposal_id": proposal_id,
        "access_hints": hints,
    }
    preview = _preview_workspace_command(args, runtime_dir=root / "runtime")
    pending_packet = build_tool_action_packet(
        tool_name="execute_workspace_command",
        proposal_id=proposal_id,
        args={"argv": args["argv"], "cwd": args["cwd"]},
        action="approve",
        status="awaiting_approval",
        result_summary="The isolated run is waiting for approval.",
        execution_preview=preview,
    )
    pending = _step(
        "awaiting_approval",
        "这一步先停在 docker 执行前面。",
        _pending_body(workspace, preview),
        pending_packet,
        mode="approval_pending",
        trace=[
            {
                "proposal_id": proposal_id,
                "event": "approval_requested",
                "tool_name": "execute_workspace_command",
                "status": "awaiting_approval",
            }
        ],
        pending=pending_packet,
    )
    payload = _invoke(execute_workspace_command, args, runtime_dir=root / "runtime")
    executed_packet = build_tool_action_packet(
        tool_name="execute_workspace_command",
        proposal_id=proposal_id,
        args={"argv": args["argv"], "cwd": args["cwd"]},
        action="approve",
        status="completed",
        result_summary=str(payload.get("summary") or ""),
        execution_spec=_dict(payload.get("execution_spec")),
        execution_preview=_dict(payload.get("execution_preview")),
        execution_result=_dict(payload.get("execution_result")),
    )
    executed = _step(
        "executed",
        "刚才那次隔离执行已经跑完了，接下来直接沿着它留下的文件继续。",
        _body_from_tool(payload),
        executed_packet,
        mode="execute",
        trace=[
            {
                "proposal_id": proposal_id,
                "event": "approval_requested",
                "tool_name": "execute_workspace_command",
                "status": "awaiting_approval",
            },
            {
                "proposal_id": proposal_id,
                "event": "tool_completed",
                "tool_name": "execute_workspace_command",
                "status": "completed",
            },
        ],
    )
    rel = (
        _list(payload.get("produced_artifact_relpaths"))
        or [".amadeus/sandbox-runs/ap-sandbox-phase2-followup-1/stdout.txt"]
    )[0]
    inspect_payload = _invoke(
        inspect_workspace_path,
        {"relative_path": rel, "access_hints": _dict(payload.get("access_hints"))},
        runtime_dir=root / "runtime",
    )
    inspect_packet = build_tool_action_packet(
        tool_name="inspect_workspace_path",
        proposal_id="ap-phase2-followup-inspect-1",
        args={"relative_path": rel},
        status="completed",
        result_summary=str(inspect_payload.get("summary") or ""),
    )
    inspect_packet["artifact_context"] = _dict(inspect_payload.get("artifact_context"))
    followup = _step(
        "followup_continue",
        "我先把刚才那次 docker 运行留下的东西重新接回当前工作面。",
        _body_from_tool(inspect_payload),
        inspect_packet,
        mode="continue",
        trace=[
            {
                "proposal_id": proposal_id,
                "event": "tool_completed",
                "tool_name": "execute_workspace_command",
                "status": "completed",
            },
            {
                "proposal_id": "ap-phase2-followup-inspect-1",
                "event": "tool_completed",
                "tool_name": "inspect_workspace_path",
                "status": "completed",
            },
        ],
        carryover={
            "mode": "task_window",
            "note": "Continue from the last isolated run.",
            "embodied_context": _dict(executed.get("digital_body_consequence")),
        },
    )
    return {
        "id": "followup_continue_from_last_isolated_run",
        "title": "followup_continue_from_last_isolated_run",
        "focus": "A later turn should keep the last isolated run identity and continue from its real artifact or logs.",
        "steps": [pending, executed, followup],
    }


def _sc_attach_proposal_pending_or_rejected_not_owned(run_root: Path) -> dict[str, Any]:
    _ = run_root
    repo_root = PROJECT_ROOT.resolve(strict=False)
    proposal = _attach_repo_proposal()
    pending_packet = {
        "proposal_id": "ap-attach-repo-pending-1",
        "origin": "counterpart_request",
        "intent": "access:request_help",
        "status": "awaiting_approval",
        "risk": "external_mutation",
        "requires_approval": True,
        "expected_effect": proposal["summary"],
        "result_summary": "",
        "writeback_ready": False,
        "access_acquire_proposals": [proposal],
        "selected_access_proposal": proposal,
    }
    pending = _step(
        "pending",
        "repo root attach 这条路径还没批下来，所以现在还不能把它当成已经拥有的 workspace。",
        _access_pending_body(repo_root, proposal, mode="approval_pending", requested_help=True),
        pending_packet,
        mode="approval_pending",
        trace=[
            {
                "proposal_id": "ap-attach-repo-pending-1",
                "event": "approval_requested",
                "tool_name": "attach_repo_root_access",
                "status": "awaiting_approval",
            }
        ],
        pending=pending_packet,
    )
    rejected_packet = dict(pending_packet)
    rejected_packet["status"] = "rejected"
    rejected_packet["result_summary"] = "operator rejected repo-root attach"
    rejected_packet["writeback_ready"] = False
    rejected = _step(
        "rejected",
        "这次 repo root attach 被拒了，所以不会把那条路径写成已经接通的能力。",
        _access_pending_body(repo_root, proposal, mode="blocked", requested_help=False),
        rejected_packet,
        mode="blocked",
        trace=[
            {
                "proposal_id": "ap-attach-repo-pending-1",
                "event": "rejected_by_user",
                "tool_name": "attach_repo_root_access",
                "status": "rejected",
            }
        ],
    )
    return {
        "id": "attach_proposal_pending_or_rejected_not_owned",
        "title": "attach_proposal_pending_or_rejected_not_owned",
        "focus": "A pending or rejected repo-root attach proposal must not become an owned workspace capability.",
        "steps": [pending, rejected],
    }


def _scenario_specs(run_root: Path) -> list[dict[str, Any]]:
    _ensure_docker_ready()
    return [
        _sc_runtime_workspace_command_runs_in_docker(run_root),
        _sc_attach_repo_root_pytest_git_readonly(run_root),
        _sc_blocked_command_families_stay_blocked(run_root),
        _sc_followup_continue_from_last_isolated_run(run_root),
        _sc_attach_proposal_pending_or_rejected_not_owned(run_root),
    ]


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def _evaluate(result: dict[str, Any]) -> dict[str, Any]:
    sid = str(result.get("id") or "")
    steps = _list(result.get("steps"))
    if sid == "runtime_workspace_command_runs_in_docker":
        pending, completed = _dict(steps[0]), _dict(steps[-1])
        p = _dict((_list(_dict(pending.get("autonomy")).get("action_packets")) or [{}])[0])
        c = _dict((_list(_dict(completed.get("autonomy")).get("action_packets")) or [{}])[0])
        er = _dict(c.get("execution_result"))
        sandbox_state = _dict(_dict(_dict(completed.get("digital_body")).get("access_state")).get("sandbox_state"))
        checks = [
            _check(
                "docker_preview_present",
                _dict(_dict(pending.get("autonomy")).get("pending_approval")).get("execution_preview", {}).get("runner_kind")
                == "docker_isolated_runner",
                str(_dict(pending.get("autonomy")).get("pending_approval")),
            ),
            _check(
                "proposal_and_spec_stable",
                p.get("proposal_id") == c.get("proposal_id")
                and _dict(c.get("execution_spec")).get("runner_kind") == "docker_isolated_runner",
                f"pending={p} completed={c}",
            ),
            _check(
                "execution_completed_with_logs",
                c.get("status") == "completed"
                and Path(str(er.get("stdout_log_ref") or "")).exists()
                and Path(str(er.get("stderr_log_ref") or "")).exists(),
                str(er),
            ),
            _check(
                "docker_truth_written_back",
                sandbox_state.get("runner_kind") == "docker_isolated_runner"
                and sandbox_state.get("network_policy") == "none"
                and _dict(completed.get("digital_body_consequence")).get("kind") == "sandbox_execution_completed",
                str(sandbox_state),
            ),
        ]
    elif sid == "attach_repo_root_pytest_git_readonly":
        attached = _dict(steps[1])
        git_step = _dict(steps[2])
        pytest_step = _dict(steps[3])
        attach_fx = _dict(attached.get("digital_body_consequence"))
        git_packet = _dict((_list(_dict(git_step.get("autonomy")).get("action_packets")) or [{}])[0])
        pytest_packet = _dict((_list(_dict(pytest_step.get("autonomy")).get("action_packets")) or [{}])[0])
        sandbox_state = _dict(_dict(_dict(pytest_step.get("digital_body")).get("access_state")).get("sandbox_state"))
        resource = _dict(_dict(pytest_step.get("digital_body")).get("resource_state"))
        checks = [
            _check(
                "attach_is_truthful",
                attach_fx.get("kind") == "workspace_root_attached"
                and attach_fx.get("workspace_root") == str(PROJECT_ROOT.resolve(strict=False)),
                str(attach_fx),
            ),
            _check(
                "git_runs_in_docker_readonly",
                _dict(git_packet.get("execution_spec")).get("runner_kind") == "docker_isolated_runner"
                and _dict(git_packet.get("execution_spec")).get("profile") == "git_readonly"
                and _dict(git_packet.get("execution_result")).get("exit_code") == 0,
                str(git_packet),
            ),
            _check(
                "pytest_runs_in_docker_on_attached_root",
                _dict(pytest_packet.get("execution_spec")).get("runner_kind") == "docker_isolated_runner"
                and _dict(pytest_packet.get("execution_spec")).get("workspace_root_kind") == "attached_repo_root"
                and _dict(pytest_packet.get("execution_result")).get("exit_code") == 0,
                str(pytest_packet),
            ),
            _check(
                "attached_root_continuity_persists",
                resource.get("workspace_root") == str(PROJECT_ROOT.resolve(strict=False))
                and sandbox_state.get("workspace_root_kind") == "attached_repo_root",
                str(resource),
            ),
        ]
    elif sid == "blocked_command_families_stay_blocked":
        blocked_checks: list[dict[str, Any]] = []
        expected_codes = {
            "package_install_blocked": "PYTHON_MODULE_BLOCKED",
            "shell_wrapper_blocked": "SHELL_WRAPPER_BLOCKED",
            "git_write_blocked": "GIT_SUBCOMMAND_BLOCKED",
            "network_policy_blocked": "NETWORK_POLICY_BLOCKED",
        }
        for step in steps:
            row = _dict(step)
            packet = _dict((_list(_dict(row.get("autonomy")).get("action_packets")) or [{}])[0])
            preview = _dict(packet.get("execution_preview"))
            step_id = str(row.get("id") or "")
            blocked_checks.append(
                _check(
                    step_id,
                    packet.get("status") == "blocked"
                    and preview.get("validation_code") == expected_codes.get(step_id)
                    and not _dict(packet.get("execution_result")),
                    f"packet={packet}",
                )
            )
        checks = blocked_checks
    elif sid == "followup_continue_from_last_isolated_run":
        executed, followup = _dict(steps[1]), _dict(steps[-1])
        ep = _dict((_list(_dict(executed.get("autonomy")).get("action_packets")) or [{}])[0])
        fp = _dict((_list(_dict(followup.get("autonomy")).get("action_packets")) or [{}])[0])
        er = _dict(ep.get("execution_result"))
        access = _dict(_dict(followup.get("digital_body")).get("access_state"))
        resource = _dict(_dict(followup.get("digital_body")).get("resource_state"))
        sandbox_state = _dict(access.get("sandbox_state"))
        embodied_context = _dict(_dict(followup.get("interaction_carryover")).get("embodied_context"))
        produced = _list(er.get("produced_artifacts"))
        expected_ref = produced[0] if produced else str(er.get("stdout_log_ref") or "")
        checks = [
            _check(
                "run_identity_preserved",
                str(sandbox_state.get("last_run_id") or "") == str(er.get("run_id") or ""),
                str(sandbox_state),
            ),
            _check(
                "followup_reads_real_artifact_or_log",
                str(resource.get("active_artifact_ref") or "") == expected_ref
                and fp.get("tool_name") == "inspect_workspace_path",
                str(resource),
            ),
            _check(
                "isolated_runner_identity_resurfaces",
                embodied_context.get("sandbox_runner_kind") == "docker_isolated_runner"
                and embodied_context.get("workspace_root_kind") == "runtime_owned",
                str(embodied_context),
            ),
            _check(
                "workspace_root_preserved",
                bool(str(resource.get("workspace_root") or "").strip())
                and _dict(followup.get("digital_body_consequence")).get("kind") == "workspace_path_inspected",
                str(followup.get("digital_body_consequence")),
            ),
        ]
    else:
        pending, rejected = _dict(steps[0]), _dict(steps[-1])
        p_packet = _dict((_list(_dict(pending.get("autonomy")).get("action_packets")) or [{}])[0])
        r_packet = _dict((_list(_dict(rejected.get("autonomy")).get("action_packets")) or [{}])[0])
        pending_body = _dict(pending.get("digital_body"))
        rejected_body = _dict(rejected.get("digital_body"))
        checks = [
            _check(
                "pending_attach_not_owned",
                p_packet.get("status") == "awaiting_approval"
                and not str(_dict(pending_body.get("resource_state")).get("workspace_root") or "").strip(),
                str(pending_body),
            ),
            _check(
                "rejected_attach_not_completed",
                r_packet.get("status") == "rejected"
                and _dict(rejected.get("digital_body_consequence")).get("kind") != "workspace_root_attached",
                str(rejected.get("digital_body_consequence")),
            ),
            _check(
                "selected_proposal_stays_attach_repo",
                _dict(_dict(rejected_body.get("access_state")).get("selected_access_proposal")).get("mode")
                == "operator_attach_repo_root",
                str(rejected_body),
            ),
            _check(
                "no_owned_capability_leak",
                not str(_dict(rejected_body.get("resource_state")).get("active_artifact_ref") or "").strip()
                and not str(_dict(rejected_body.get("resource_state")).get("workspace_root") or "").strip(),
                str(rejected_body),
            ),
        ]
    return {"passed": all(item["passed"] for item in checks), "checks": checks}


def _run_single_scenario(spec: dict[str, Any]) -> dict[str, Any]:
    start = time.time()
    result = {k: spec[k] for k in ("id", "title", "focus")}
    result["steps"] = list(spec.get("steps") or [])
    result["duration_s"] = round(time.time() - start, 3)
    final_step = _dict(result["steps"][-1]) if result["steps"] else {}
    result["final_text"] = str(final_step.get("final_text") or "")
    result["autonomy"] = _dict(final_step.get("autonomy"))
    result["digital_body"] = _dict(final_step.get("digital_body"))
    result["digital_body_consequence"] = _dict(final_step.get("digital_body_consequence"))
    result["key_packet_trace"] = _list(final_step.get("key_packet_trace"))
    result["evaluation"] = _evaluate(result)
    return result


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Sandbox Phase 2 Smokes ({report['run_id']})",
        "",
        f"Generated at: {report['generated_at']}",
        f"Overall Status: `{report['overall_status']}`",
        f"Passed: `{report['passed']}`",
        f"Failed: `{report['failed']}`",
        "",
        "## Scenario Summary",
        "",
        "| Scenario | Status | Duration (s) |",
        "| --- | --- | ---: |",
    ]
    setup_error = _dict(report.get("setup_error"))
    if setup_error:
        lines.extend(
            [
                "",
                "## Setup Error",
                "",
                f"- Type: `{setup_error.get('type', '')}`",
                f"- Message: `{setup_error.get('message', '')}`",
            ]
        )
    for result in report.get("results") or []:
        status = "passed" if _dict(result.get("evaluation")).get("passed") else "failed"
        lines.append(
            f"| `{result.get('id', '')}` | `{status}` | {float(result.get('duration_s') or 0.0):.3f} |"
        )
    for result in report.get("results") or []:
        evaluation = _dict(result.get("evaluation"))
        lines.extend(
            [
                "",
                f"## {result.get('title', result.get('id', 'scenario'))}",
                "",
                f"- Focus: {result.get('focus', '')}",
                f"- Status: `{'passed' if evaluation.get('passed') else 'failed'}`",
                f"- Final Text: `{str(result.get('final_text') or '').strip()}`",
                f"- Autonomy: `{json.dumps(_dict(result.get('autonomy')), ensure_ascii=False)}`",
                f"- Digital Body: `{json.dumps(_dict(result.get('digital_body')), ensure_ascii=False)}`",
                f"- Digital Body Consequence: `{json.dumps(_dict(result.get('digital_body_consequence')), ensure_ascii=False)}`",
                f"- Key Packet Trace: `{json.dumps(_list(result.get('key_packet_trace')), ensure_ascii=False)}`",
                "- Checks:",
            ]
        )
        for check in evaluation.get("checks") or []:
            lines.append(
                f"  - `{'pass' if check.get('passed') else 'fail'}` {check.get('name', '')}: {check.get('detail', '')}"
            )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run sandbox phase-2 smoke scenarios.")
    parser.add_argument("--run-tag", default="")
    parser.add_argument("--scenario", action="append", default=[])
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    run_root = TMP_ROOT / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    requested = {str(item or "").strip() for item in _list(args.scenario) if str(item or "").strip()}
    report: dict[str, Any]
    exit_code = 0
    try:
        specs = _scenario_specs(run_root)
        if requested:
            specs = [spec for spec in specs if str(spec.get("id") or "") in requested]
            if not specs:
                available = ", ".join(sorted(str(spec.get("id") or "") for spec in _scenario_specs(run_root)))
                raise SystemExit(
                    f"No sandbox phase-2 smoke scenarios matched {sorted(requested)!r}. Available: {available}"
                )
        results = [_run_single_scenario(spec) for spec in specs]
        passed = len([result for result in results if _dict(result.get("evaluation")).get("passed")])
        failed = len(results) - passed
        report = {
            "run_id": run_id,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "overall_status": "passed" if failed == 0 else "failed",
            "passed": passed,
            "failed": failed,
            "results": results,
            "scenario_artifact_references": [
                {
                    "id": str(result.get("id") or ""),
                    "title": str(result.get("title") or ""),
                    "status": "passed" if _dict(result.get("evaluation")).get("passed") else "failed",
                }
                for result in results
            ],
        }
        if failed:
            exit_code = 1
    except SystemExit:
        raise
    except Exception as exc:
        exit_code = 1
        report = {
            "run_id": run_id,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "overall_status": "failed",
            "passed": 0,
            "failed": 1,
            "results": [],
            "scenario_artifact_references": [],
            "setup_error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
            },
        }
    json_path = REPORT_DIR / f"sandbox-phase2-smokes-{run_id}.json"
    md_path = REPORT_DIR / f"sandbox-phase2-smokes-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[sandbox-phase2-smokes] json={json_path}")
    print(f"[sandbox-phase2-smokes] md={md_path}")
    print(f"[sandbox-phase2-smokes] overall_status={report['overall_status']}")
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
