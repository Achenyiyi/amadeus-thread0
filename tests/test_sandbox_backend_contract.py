from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from amadeus_thread0.runtime.backend_api import BackendAPI


class _MinimalMemoryStore:
    def list_revision_traces(self, limit: int = 60):
        return []

    def list_semantic_self_narratives(self, limit: int = 20):
        return []

    def list_counterpart_assessment_history(self, limit: int = 12):
        return []

    def list_proactive_continuity_history(self, limit: int = 12):
        return []


class _SandboxBackendSession:
    def __init__(self) -> None:
        self.memory_store = _MinimalMemoryStore()

    def build_evolution_summary(self, *, state_values=None):
        values = state_values if isinstance(state_values, dict) else {}
        digital_body = values.get("digital_body_state") if isinstance(values.get("digital_body_state"), dict) else {}
        consequence = values.get("digital_body_consequence") if isinstance(values.get("digital_body_consequence"), dict) else {}
        return {
            "digital_body": dict(digital_body),
            "digital_body_consequence": dict(consequence),
            "current_turn": {
                "digital_body_surface": str(digital_body.get("active_surface") or "").strip(),
                "digital_body_access_mode": str((digital_body.get("access_state") or {}).get("mode") or "").strip()
                if isinstance(digital_body.get("access_state"), dict)
                else "",
                "digital_body_consequence_kind": str(consequence.get("kind") or "").strip(),
                "digital_body_consequence_summary": str(consequence.get("summary") or "").strip(),
            },
        }

    def extract_final_text(self, values, *, streamed_text=""):
        data = values if isinstance(values, dict) else {}
        return str(data.get("final_text") or "").strip() or str(streamed_text or "").strip()


class SandboxBackendContractTests(unittest.TestCase):
    def _build_api(self) -> BackendAPI:
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        root = Path(tempdir.name)
        checkpoint_db = root / "checkpoints.sqlite"
        checkpoint_db.write_bytes(b"x")
        runtime_bundle = SimpleNamespace(
            thread_id="thread-sandbox",
            backend_session=_SandboxBackendSession(),
            memory_admin=SimpleNamespace(snapshot_view=lambda: {}),
            settings=SimpleNamespace(
                checkpoint_db_path=checkpoint_db,
                data_dir=root,
                model_provider="synthetic",
                model_name="sandbox-contract",
                model_base_url="",
                runtime_mode="eval",
            ),
        )
        return BackendAPI(runtime_bundle=runtime_bundle, base_data_dir=root, cwd=root)

    def test_turn_and_event_responses_surface_completed_sandbox_execution_fields(self):
        api = self._build_api()
        state_values = {
            "final_text": "我已经把受限执行跑完了。",
            "current_event": {"kind": "user_utterance"},
            "digital_body_state": {
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
                        "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
                        "execution_policy": "approval_required",
                        "last_status": "completed",
                        "runner_kind": "local_restricted_runner",
                        "isolation_level": "host_local_restricted",
                        "last_command_profile": "python_script",
                        "last_exit_code": 0,
                        "last_run_id": "ap-sandbox-1",
                        "arbitrary_execution": False,
                    },
                },
                "resource_state": {
                    "action_packet_count": 1,
                    "completed_packet_count": 1,
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "file",
                    "active_artifact_ref": "E:/runtime/workspaces/lab-notes/notes/generated.txt",
                    "active_artifact_label": "generated.txt",
                    "artifact_carrier": "filesystem",
                    "workspace_root": "E:/runtime/workspaces/lab-notes",
                },
            },
            "action_packets": [
                {
                    "proposal_id": "ap-sandbox-1",
                    "origin": "motive_goal",
                    "intent": "sandbox:execute_workspace_command",
                    "status": "completed",
                    "risk": "external_mutation",
                    "requires_approval": True,
                    "tool_name": "execute_workspace_command",
                    "result_summary": "已在当前 workspace 内完成一次受限执行，结果已经落成可续接的工作面。",
                    "writeback_ready": True,
                    "execution_spec": {
                        "executor": "python",
                        "profile": "python_script",
                        "argv": ["python", "emit_artifact.py"],
                        "cwd": "E:/runtime/workspaces/lab-notes",
                        "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
                        "timeout_s": 25,
                        "writes_expected": True,
                        "expected_artifacts": ["notes/generated.txt"],
                    },
                    "execution_preview": {
                        "runner_kind": "local_restricted_runner",
                        "isolation_level": "host_local_restricted",
                        "argv": ["python", "emit_artifact.py"],
                        "cwd": "E:/runtime/workspaces/lab-notes",
                        "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
                        "timeout_s": 25,
                        "writes_expected": True,
                        "expected_artifacts": ["notes/generated.txt"],
                    },
                    "execution_result": {
                        "run_id": "ap-sandbox-1",
                        "status": "completed",
                        "exit_code": 0,
                        "duration_ms": 84,
                        "stdout_log_ref": "E:/runtime/workspaces/lab-notes/.amadeus/sandbox-runs/ap-sandbox-1/stdout.txt",
                        "stderr_log_ref": "E:/runtime/workspaces/lab-notes/.amadeus/sandbox-runs/ap-sandbox-1/stderr.txt",
                        "produced_artifacts": ["E:/runtime/workspaces/lab-notes/notes/generated.txt"],
                        "error_summary": "",
                    },
                }
            ],
            "digital_body_consequence": {
                "kind": "sandbox_execution_completed",
                "summary": "当前这次受限执行已经真实完成，日志和产物都落回了同一个 workspace 表面。",
                "sandbox_run_id": "ap-sandbox-1",
                "sandbox_command_profile": "python_script",
                "sandbox_exit_code": 0,
                "workspace_root": "E:/runtime/workspaces/lab-notes",
            },
        }

        turn = api.build_turn_response(state_values=state_values, streamed_text="ignored").payload
        event = api.build_event_round_response(state_values=state_values, final_text="我已经把受限执行跑完了。").payload

        for payload in (turn, event):
            packet = payload["autonomy"]["action_packets"][0]
            self.assertEqual(packet["intent"], "sandbox:execute_workspace_command")
            self.assertEqual(packet["execution_preview"]["runner_kind"], "local_restricted_runner")
            self.assertEqual(packet["execution_result"]["run_id"], "ap-sandbox-1")
            self.assertEqual(
                payload["digital_body"]["access_state"]["sandbox_state"]["last_run_id"],
                "ap-sandbox-1",
            )
            self.assertEqual(
                payload["digital_body"]["access_state"]["sandbox_state"]["last_command_profile"],
                "python_script",
            )
            self.assertEqual(payload["digital_body_consequence"]["kind"], "sandbox_execution_completed")
            self.assertEqual(payload["turn_summary"]["current_turn"]["digital_body_consequence_kind"], "sandbox_execution_completed")

    def test_turn_response_surfaces_pending_sandbox_approval_preview(self):
        api = self._build_api()
        state_values = {
            "current_event": {"kind": "user_utterance"},
            "autonomy_intent": {
                "mode": "approval_pending",
                "origin": "counterpart_request",
                "primary_proposal_id": "ap-sandbox-pending",
            },
            "action_packets": [
                {
                    "proposal_id": "ap-sandbox-pending",
                    "origin": "counterpart_request",
                    "intent": "sandbox:execute_workspace_command",
                    "status": "awaiting_approval",
                    "risk": "external_mutation",
                    "requires_approval": True,
                    "tool_name": "execute_workspace_command",
                    "execution_spec": {
                        "executor": "pytest",
                        "profile": "pytest",
                        "argv": ["pytest", "-q", "tests/test_generation_profile.py"],
                        "cwd": "E:/runtime/workspaces/lab-notes",
                        "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
                        "timeout_s": 60,
                        "writes_expected": False,
                        "expected_artifacts": [],
                    },
                    "execution_preview": {
                        "runner_kind": "local_restricted_runner",
                        "isolation_level": "host_local_restricted",
                        "argv": ["pytest", "-q", "tests/test_generation_profile.py"],
                        "cwd": "E:/runtime/workspaces/lab-notes",
                        "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
                        "timeout_s": 60,
                        "writes_expected": False,
                        "expected_artifacts": [],
                    },
                }
            ],
            "pending_action_proposal": {
                "proposal_id": "ap-sandbox-pending",
                "origin": "counterpart_request",
                "intent": "sandbox:execute_workspace_command",
                "status": "awaiting_approval",
                "risk": "external_mutation",
                "requires_approval": True,
                "execution_preview": {
                    "runner_kind": "local_restricted_runner",
                    "isolation_level": "host_local_restricted",
                    "argv": ["pytest", "-q", "tests/test_generation_profile.py"],
                    "cwd": "E:/runtime/workspaces/lab-notes",
                    "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
                    "timeout_s": 60,
                    "writes_expected": False,
                    "expected_artifacts": [],
                },
            },
            "digital_body_state": {
                "active_surface": "approval_gate",
                "perception_channels": ["dialogue", "filesystem"],
                "action_channels": ["language", "structured_action", "approval_gate", "tooling"],
                "world_surfaces": ["filesystem", "sandbox"],
                "access_state": {
                    "mode": "approval_pending",
                    "pending_approval_count": 1,
                    "external_mutation_pending": True,
                    "filesystem_state": "writable",
                    "sandbox_mode": "restricted",
                    "sandbox_state": {
                        "availability": "restricted",
                        "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
                        "execution_policy": "approval_required",
                        "last_status": "awaiting_operator_approval",
                        "runner_kind": "local_restricted_runner",
                        "isolation_level": "host_local_restricted",
                        "arbitrary_execution": False,
                    },
                },
                "resource_state": {
                    "action_packet_count": 1,
                    "pending_approval_count": 1,
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "workspace",
                    "active_artifact_ref": "E:/runtime/workspaces/lab-notes",
                    "active_artifact_label": "lab-notes",
                    "artifact_carrier": "filesystem",
                    "workspace_root": "E:/runtime/workspaces/lab-notes",
                },
            },
        }

        payload = api.build_turn_response(state_values=state_values, streamed_text="ignored").payload

        self.assertEqual(payload["autonomy"]["intent"]["mode"], "approval_pending")
        self.assertEqual(payload["autonomy"]["pending_approval"]["proposal_id"], "ap-sandbox-pending")
        self.assertEqual(
            payload["autonomy"]["pending_approval"]["execution_preview"]["runner_kind"],
            "local_restricted_runner",
        )
        self.assertEqual(
            payload["digital_body"]["access_state"]["sandbox_state"]["last_status"],
            "awaiting_operator_approval",
        )
        self.assertEqual(payload["digital_body"]["access_state"]["mode"], "approval_pending")


if __name__ == "__main__":
    unittest.main()
