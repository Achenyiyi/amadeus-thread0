from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from amadeus_thread0.evolution_engine.reconsolidation import build_reconsolidation_snapshot
from amadeus_thread0.graph_parts.action_packets import build_tool_action_packet
from amadeus_thread0.runtime.final_state import resolve_digital_body_consequence
from amadeus_thread0.utils.tools import execute_workspace_command


def _sandbox_env(runtime_dir: Path) -> dict[str, str]:
    return {
        "AMADEUS_DATA_DIR": str(runtime_dir),
        "AMADEUS_MODEL_PROVIDER": "openai_compatible",
    }


def _workspace_hints(workspace: Path) -> dict[str, str]:
    return {
        "filesystem_state": "writable",
        "sandbox_mode": "restricted",
        "active_artifact_kind": "workspace",
        "active_artifact_ref": str(workspace),
        "active_artifact_label": workspace.name,
        "workspace_root": str(workspace),
    }


def _digital_body_from_payload(payload: dict[str, object]) -> dict[str, object]:
    return {
        "active_surface": "tooling",
        "perception_channels": ["dialogue", "filesystem"],
        "action_channels": ["language", "structured_action", "tooling"],
        "world_surfaces": ["filesystem", "sandbox"],
        "access_state": dict(payload.get("access_state") or {}),
        "resource_state": dict(payload.get("resource_state") or {}),
    }


def test_execute_workspace_command_generates_artifact_and_updates_runtime_surfaces():
    with TemporaryDirectory() as td:
        runtime_dir = Path(td) / "runtime"
        workspace = runtime_dir / "workspaces" / "lab-notes"
        workspace.mkdir(parents=True)
        (workspace / "emit_artifact.py").write_text(
            "\n".join(
                [
                    "from pathlib import Path",
                    "out = Path('notes/generated.txt')",
                    "out.parent.mkdir(parents=True, exist_ok=True)",
                    "out.write_text('sandbox result\\n', encoding='utf-8')",
                    "print('generated artifact')",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        with patch.dict(os.environ, _sandbox_env(runtime_dir), clear=True):
            payload = execute_workspace_command.invoke(
                {
                    "argv": ["python", "emit_artifact.py"],
                    "cwd": ".",
                    "writes_expected": True,
                    "expected_artifacts": ["notes/generated.txt"],
                    "proposal_id": "ap-sandbox-run-1",
                    "access_hints": _workspace_hints(workspace),
                }
            )

        assert payload["execution_spec"]["profile"] == "python_script"
        assert payload["execution_preview"]["runner_kind"] == "local_restricted_runner"
        assert payload["execution_preview"]["isolation_level"] == "host_local_restricted"
        assert payload["execution_result"]["status"] == "completed"
        assert payload["execution_result"]["run_id"] == "ap-sandbox-run-1"
        assert payload["execution_result"]["exit_code"] == 0
        assert Path(payload["execution_result"]["stdout_log_ref"]).exists()
        assert Path(payload["execution_result"]["stderr_log_ref"]).exists()
        assert payload["artifact_context"]["artifact_kind"] == "file"
        assert payload["artifact_context"]["artifact_ref"].endswith("notes\\generated.txt") or payload["artifact_context"]["artifact_ref"].endswith("notes/generated.txt")
        assert payload["sandbox_state"]["runner_kind"] == "local_restricted_runner"
        assert payload["sandbox_state"]["isolation_level"] == "host_local_restricted"
        assert payload["sandbox_state"]["last_command_profile"] == "python_script"
        assert payload["sandbox_state"]["last_run_id"] == "ap-sandbox-run-1"
        assert payload["resource_state"]["active_artifact_kind"] == "file"
        assert payload["resource_state"]["workspace_root"] == str(workspace)


def test_execute_workspace_command_uses_stdout_log_as_active_artifact_when_no_output_file_is_expected():
    with TemporaryDirectory() as td:
        runtime_dir = Path(td) / "runtime"
        workspace = runtime_dir / "workspaces" / "lab-notes"
        workspace.mkdir(parents=True)
        (workspace / "print_only.py").write_text("print('hello from stdout only')\n", encoding="utf-8")
        with patch.dict(os.environ, _sandbox_env(runtime_dir), clear=True):
            payload = execute_workspace_command.invoke(
                {
                    "argv": ["python", "print_only.py"],
                    "cwd": ".",
                    "writes_expected": False,
                    "proposal_id": "ap-sandbox-run-stdout",
                    "access_hints": _workspace_hints(workspace),
                }
            )

        stdout_log_ref = payload["execution_result"]["stdout_log_ref"]
        assert payload["execution_result"]["status"] == "completed"
        assert payload["artifact_context"]["artifact_ref"] == stdout_log_ref
        assert payload["resource_state"]["active_artifact_ref"] == stdout_log_ref
        assert payload["resource_state"]["active_artifact_kind"] == "file"
        assert "hello from stdout only" in Path(stdout_log_ref).read_text(encoding="utf-8")


def test_sandbox_execution_writeback_distinguishes_completed_and_blocked_runs():
    with TemporaryDirectory() as td:
        runtime_dir = Path(td) / "runtime"
        workspace = runtime_dir / "workspaces" / "lab-notes"
        workspace.mkdir(parents=True)
        success_script = workspace / "emit_ok.py"
        success_script.write_text("print('ok')\n", encoding="utf-8")
        fail_script = workspace / "emit_fail.py"
        fail_script.write_text("import sys\nprint('fail')\nsys.exit(3)\n", encoding="utf-8")

        with patch.dict(os.environ, _sandbox_env(runtime_dir), clear=True):
            completed_payload = execute_workspace_command.invoke(
                {
                    "argv": ["python", "emit_ok.py"],
                    "cwd": ".",
                    "writes_expected": False,
                    "proposal_id": "ap-sandbox-completed",
                    "access_hints": _workspace_hints(workspace),
                }
            )
            blocked_payload = execute_workspace_command.invoke(
                {
                    "argv": ["python", "emit_fail.py"],
                    "cwd": ".",
                    "writes_expected": False,
                    "proposal_id": "ap-sandbox-blocked",
                    "access_hints": _workspace_hints(workspace),
                }
            )

        completed_packet = build_tool_action_packet(
            tool_name="execute_workspace_command",
            proposal_id="ap-sandbox-completed",
            args={"argv": ["python", "emit_ok.py"]},
            action="approve",
            status="completed",
            result_summary=str(completed_payload.get("summary") or ""),
            execution_spec=dict(completed_payload.get("execution_spec") or {}),
            execution_preview=dict(completed_payload.get("execution_preview") or {}),
            execution_result=dict(completed_payload.get("execution_result") or {}),
        )
        blocked_packet = build_tool_action_packet(
            tool_name="execute_workspace_command",
            proposal_id="ap-sandbox-blocked",
            args={"argv": ["python", "emit_fail.py"]},
            action="approve",
            status="blocked",
            result_summary=str(blocked_payload.get("summary") or ""),
            block_reason=str(blocked_payload.get("execution_result", {}).get("error_summary") or ""),
            execution_spec=dict(blocked_payload.get("execution_spec") or {}),
            execution_preview=dict(blocked_payload.get("execution_preview") or {}),
            execution_result=dict(blocked_payload.get("execution_result") or {}),
        )

        completed_snapshot = build_reconsolidation_snapshot(
            current_event={"kind": "user_utterance"},
            appraisal={"interaction_frame": "task"},
            world_model_state={},
            semantic_narrative_profile={},
            latent_state={"self_coherence": 0.82},
            emotion_state={"label": "focused"},
            bond_state={"trust": 0.6},
            behavior_action={"interaction_mode": "tooling"},
            action_packets=[completed_packet],
            digital_body_state=_digital_body_from_payload(completed_payload),
        )
        blocked_snapshot = build_reconsolidation_snapshot(
            current_event={"kind": "user_utterance"},
            appraisal={"interaction_frame": "task"},
            world_model_state={},
            semantic_narrative_profile={},
            latent_state={"self_coherence": 0.82},
            emotion_state={"label": "focused"},
            bond_state={"trust": 0.6},
            behavior_action={"interaction_mode": "tooling"},
            action_packets=[blocked_packet],
            digital_body_state=_digital_body_from_payload(blocked_payload),
        )

        completed_consequence = resolve_digital_body_consequence(
            digital_body_consequence={},
            digital_body_state=_digital_body_from_payload(completed_payload),
            action_packets=[completed_packet],
            reconsolidation_snapshot=completed_snapshot,
        )
        blocked_consequence = resolve_digital_body_consequence(
            digital_body_consequence={},
            digital_body_state=_digital_body_from_payload(blocked_payload),
            action_packets=[blocked_packet],
            reconsolidation_snapshot=blocked_snapshot,
        )

        assert completed_consequence["kind"] == "sandbox_execution_completed"
        assert completed_consequence["sandbox_run_id"] == "ap-sandbox-completed"
        assert completed_consequence["sandbox_command_profile"] == "python_script"
        assert completed_consequence["sandbox_exit_code"] == 0
        assert blocked_consequence["kind"] == "sandbox_execution_blocked"
        assert blocked_consequence["sandbox_run_id"] == "ap-sandbox-blocked"
        assert blocked_consequence["sandbox_exit_code"] == 3
        assert blocked_consequence["sandbox_error_summary"] == "process exited with code 3"
