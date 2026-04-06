from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from amadeus_thread0.runtime.backend_api import BackendAPI
from amadeus_thread0.runtime.sandbox_runner import DEFAULT_DOCKER_IMAGE_REF


class _MinimalMemoryStore:
    def list_revision_traces(self, limit: int = 60):
        return []

    def list_semantic_self_narratives(self, limit: int = 20):
        return []

    def list_counterpart_assessment_history(self, limit: int = 12):
        return []

    def list_proactive_continuity_history(self, limit: int = 12):
        return []


class _SandboxPhase2BackendSession:
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


class SandboxPhase2BackendContractTests(unittest.TestCase):
    def _build_api(self) -> BackendAPI:
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        root = Path(tempdir.name)
        checkpoint_db = root / "checkpoints.sqlite"
        checkpoint_db.write_bytes(b"x")
        runtime_bundle = SimpleNamespace(
            thread_id="thread-sandbox-phase2",
            backend_session=_SandboxPhase2BackendSession(),
            memory_admin=SimpleNamespace(snapshot_view=lambda: {}),
            settings=SimpleNamespace(
                checkpoint_db_path=checkpoint_db,
                data_dir=root,
                model_provider="synthetic",
                model_name="sandbox-phase2-contract",
                model_base_url="",
                runtime_mode="eval",
            ),
        )
        return BackendAPI(runtime_bundle=runtime_bundle, base_data_dir=root, cwd=root)

    def test_turn_response_surfaces_docker_execution_fields(self):
        api = self._build_api()
        repo_root = "E:/repo/amadeus-thread0"
        state_values = {
            "final_text": "我已经在隔离 runner 里把这一步跑完了。",
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
                        "allowed_roots": [repo_root],
                        "execution_policy": "approval_required",
                        "last_status": "completed",
                        "runner_kind": "docker_isolated_runner",
                        "isolation_level": "docker_local_isolated",
                        "image_ref": DEFAULT_DOCKER_IMAGE_REF,
                        "network_policy": "none",
                        "workspace_root_kind": "attached_repo_root",
                        "last_command_profile": "pytest",
                        "last_exit_code": 0,
                        "last_run_id": "ap-sandbox-phase2-1",
                        "arbitrary_execution": False,
                    },
                },
                "resource_state": {
                    "action_packet_count": 1,
                    "completed_packet_count": 1,
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "file",
                    "active_artifact_ref": f"{repo_root}/.amadeus/sandbox-runs/ap-sandbox-phase2-1/stdout.txt",
                    "active_artifact_label": "stdout.txt",
                    "artifact_carrier": "filesystem",
                    "workspace_root": repo_root,
                },
            },
            "action_packets": [
                {
                    "proposal_id": "ap-sandbox-phase2-1",
                    "origin": "motive_goal",
                    "intent": "sandbox:execute_workspace_command",
                    "status": "completed",
                    "risk": "external_mutation",
                    "requires_approval": True,
                    "tool_name": "execute_workspace_command",
                    "result_summary": "已在 docker 隔离执行面内完成这一步。",
                    "writeback_ready": True,
                    "execution_spec": {
                        "executor": "pytest",
                        "profile": "pytest",
                        "runner_kind": "docker_isolated_runner",
                        "isolation_level": "docker_local_isolated",
                        "image_ref": DEFAULT_DOCKER_IMAGE_REF,
                        "network_policy": "none",
                        "workspace_root_kind": "attached_repo_root",
                        "argv": ["pytest", "-q", "tests/test_sandbox_phase2_repo_fixture.py"],
                        "cwd": repo_root,
                        "allowed_roots": [repo_root],
                        "timeout_s": 60,
                        "writes_expected": False,
                        "expected_artifacts": [],
                    },
                    "execution_preview": {
                        "runner_kind": "docker_isolated_runner",
                        "isolation_level": "docker_local_isolated",
                        "image_ref": DEFAULT_DOCKER_IMAGE_REF,
                        "network_policy": "none",
                        "workspace_root_kind": "attached_repo_root",
                        "argv": ["pytest", "-q", "tests/test_sandbox_phase2_repo_fixture.py"],
                        "cwd": repo_root,
                        "allowed_roots": [repo_root],
                        "timeout_s": 60,
                        "writes_expected": False,
                        "expected_artifacts": [],
                    },
                    "execution_result": {
                        "run_id": "ap-sandbox-phase2-1",
                        "status": "completed",
                        "exit_code": 0,
                        "duration_ms": 123,
                        "stdout_log_ref": f"{repo_root}/.amadeus/sandbox-runs/ap-sandbox-phase2-1/stdout.txt",
                        "stderr_log_ref": f"{repo_root}/.amadeus/sandbox-runs/ap-sandbox-phase2-1/stderr.txt",
                        "produced_artifacts": [],
                        "error_summary": "",
                    },
                }
            ],
            "digital_body_consequence": {
                "kind": "sandbox_execution_completed",
                "summary": "Docker 隔离执行已经完成，后续会沿同一个 run 和 repo root 继续。",
                "sandbox_run_id": "ap-sandbox-phase2-1",
                "sandbox_command_profile": "pytest",
                "sandbox_exit_code": 0,
                "sandbox_runner_kind": "docker_isolated_runner",
                "sandbox_image_ref": DEFAULT_DOCKER_IMAGE_REF,
                "sandbox_network_policy": "none",
                "workspace_root": repo_root,
                "workspace_root_kind": "attached_repo_root",
            },
        }

        payload = api.build_turn_response(state_values=state_values, streamed_text="ignored").payload
        packet = payload["autonomy"]["action_packets"][0]
        sandbox_state = payload["digital_body"]["access_state"]["sandbox_state"]

        self.assertEqual(packet["execution_preview"]["runner_kind"], "docker_isolated_runner")
        self.assertEqual(packet["execution_spec"]["network_policy"], "none")
        self.assertEqual(packet["execution_spec"]["workspace_root_kind"], "attached_repo_root")
        self.assertEqual(sandbox_state["image_ref"], DEFAULT_DOCKER_IMAGE_REF)
        self.assertEqual(sandbox_state["network_policy"], "none")
        self.assertEqual(sandbox_state["workspace_root_kind"], "attached_repo_root")
        self.assertEqual(payload["digital_body_consequence"]["sandbox_runner_kind"], "docker_isolated_runner")

    def test_turn_response_surfaces_workspace_root_attached_consequence(self):
        api = self._build_api()
        repo_root = "E:/repo/amadeus-thread0"
        state_values = {
            "final_text": "仓库根目录已经挂上了。",
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
                        "allowed_roots": [repo_root],
                        "execution_policy": "approval_required",
                        "runner_kind": "docker_isolated_runner",
                        "isolation_level": "docker_local_isolated",
                        "image_ref": DEFAULT_DOCKER_IMAGE_REF,
                        "network_policy": "none",
                        "workspace_root_kind": "attached_repo_root",
                        "arbitrary_execution": False,
                    },
                },
                "resource_state": {
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "workspace",
                    "active_artifact_ref": repo_root,
                    "active_artifact_label": "amadeus-thread0",
                    "artifact_carrier": "filesystem",
                    "workspace_root": repo_root,
                },
            },
            "action_packets": [
                {
                    "proposal_id": "ap-attach-repo-1",
                    "origin": "counterpart_request",
                    "intent": "access:request_help",
                    "status": "completed",
                    "risk": "external_mutation",
                    "requires_approval": True,
                    "tool_name": "attach_repo_root_access",
                    "result_summary": "已把当前仓库根目录挂接成 workspace。",
                    "writeback_ready": True,
                    "selected_access_proposal": {
                        "target": "filesystem",
                        "mode": "operator_attach_repo_root",
                        "path_kind": "acquire_existing",
                        "summary": "把当前仓库根目录挂上去。",
                        "operator_action": "批准把当前 git worktree 根目录挂接成 workspace。",
                        "grants": ["filesystem", "workspace_write"],
                        "requires_operator": True,
                    },
                    "tool_args": {
                        "repo_root": repo_root,
                    },
                }
            ],
            "digital_body_consequence": {
                "kind": "workspace_root_attached",
                "summary": "当前仓库根目录已经正式成为 workspace。",
                "workspace_root": repo_root,
                "workspace_root_kind": "attached_repo_root",
                "artifact_carrier": "filesystem",
                "active_artifact_kind": "workspace",
            },
        }

        payload = api.build_turn_response(state_values=state_values, streamed_text="ignored").payload

        self.assertEqual(payload["digital_body_consequence"]["kind"], "workspace_root_attached")
        self.assertEqual(payload["digital_body_consequence"]["workspace_root"], repo_root)
        self.assertEqual(payload["digital_body"]["resource_state"]["workspace_root"], repo_root)
        self.assertEqual(payload["digital_body"]["access_state"]["sandbox_state"]["workspace_root_kind"], "attached_repo_root")


if __name__ == "__main__":
    unittest.main()
