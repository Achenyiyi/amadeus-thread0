from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from amadeus_thread0.runtime.backend_api import BackendAPI


class _FakeSession:
    def __init__(self):
        self.memory_store = None

    def build_evolution_summary(self, *, state_values=None):
        return {
            "relationship": {"stage": "warming"},
            "current_turn": {"autonomy_mode": "approval_pending", "action_packet_count": 1},
        }

    def extract_final_text(self, values, *, streamed_text=""):
        return str(values.get("final_text") or streamed_text or "").strip()


class _FakeMemoryAdmin:
    def snapshot_view(self):
        return {}


class AutonomyBackendContractTests(unittest.TestCase):
    def test_turn_and_event_envelopes_expose_autonomy_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            session = _FakeSession()
            runtime_bundle = SimpleNamespace(
                thread_id="thread-a",
                backend_session=session,
                memory_admin=_FakeMemoryAdmin(),
                settings=SimpleNamespace(
                    checkpoint_db_path=checkpoint_db,
                    data_dir=root,
                    model_provider="dashscope",
                    model_name="qwen3.5-plus",
                    model_base_url="",
                    runtime_mode="cli",
                ),
            )
            api = BackendAPI(runtime_bundle=runtime_bundle, base_data_dir=root, cwd=root)
            state_values = {
                "final_text": "我在。",
                "current_event": {"kind": "user_utterance"},
                "autonomy_intent": {
                    "mode": "approval_pending",
                    "origin": "motive_goal",
                    "reason": "先申请，再决定是否执行。",
                    "confidence": 0.62,
                    "primary_proposal_id": "ap-1",
                },
                "action_packets": [
                    {
                        "proposal_id": "ap-1",
                        "origin": "motive_goal",
                        "intent": "tool:write_diary",
                        "status": "awaiting_approval",
                        "risk": "external_mutation",
                        "requires_approval": True,
                        "capability_steps": [],
                        "expected_effect": "写一条外部记录",
                        "artifact_context": {
                            "carrier": "source_ref",
                            "artifact_kind": "search_result",
                            "artifact_ref": "https://example.com/result",
                            "artifact_label": "Example Result",
                            "reacquisition_mode": "rerun_search",
                            "preview": "cached result snippet",
                            "source_ref_ids": [9],
                            "source_url": "https://example.com/result",
                            "source_query": "example query",
                        },
                        "mutation_preview": {
                            "tool_name": "replace_workspace_lines",
                            "can_apply": True,
                            "mutation_mode": "replace",
                            "relative_path": "notes/todo.md",
                            "summary": "审批通过后会在当前 workspace 内应用 patch。",
                            "diff_preview": "--- a/notes/todo.md\n+++ b/notes/todo.md\n@@\n-beta\n+beta v2\n",
                        },
                    }
                ],
                "pending_action_proposal": {
                    "proposal_id": "ap-1",
                    "origin": "motive_goal",
                    "intent": "tool:write_diary",
                    "status": "awaiting_approval",
                    "risk": "external_mutation",
                    "requires_approval": True,
                    "capability_steps": [],
                    "mutation_preview": {
                        "tool_name": "replace_workspace_lines",
                        "can_apply": True,
                        "mutation_mode": "replace",
                        "relative_path": "notes/todo.md",
                        "summary": "审批通过后会在当前 workspace 内应用 patch。",
                        "diff_preview": "--- a/notes/todo.md\n+++ b/notes/todo.md\n@@\n-beta\n+beta v2\n",
                    },
                },
                "action_trace": [{"proposal_id": "ap-1", "status": "awaiting_approval", "event": "tool_gate_decision"}],
                "autonomy_block_reason": "",
            }

            turn = api.build_turn_response(state_values=state_values, streamed_text="")
            event = api.build_event_round_response(state_values=state_values, final_text="我在。")

            for envelope in (turn, event):
                autonomy = envelope.payload["autonomy"]
                self.assertEqual(autonomy["intent"]["mode"], "approval_pending")
                self.assertEqual(autonomy["action_packets"][0]["proposal_id"], "ap-1")
                artifact_context = autonomy["action_packets"][0].get("artifact_context") if isinstance(autonomy["action_packets"][0].get("artifact_context"), dict) else {}
                self.assertEqual(artifact_context.get("carrier"), "source_ref")
                self.assertEqual(artifact_context.get("artifact_kind"), "search_result")
                self.assertEqual(artifact_context.get("artifact_label"), "Example Result")
                self.assertEqual(artifact_context.get("source_ref_ids"), [9])
                self.assertEqual(autonomy["action_packets"][0]["mutation_preview"]["relative_path"], "notes/todo.md")
                self.assertEqual(autonomy["pending_approval"]["proposal_id"], "ap-1")
                self.assertEqual(autonomy["pending_approval"]["mutation_preview"]["mutation_mode"], "replace")
                self.assertIn("+beta v2", autonomy["pending_approval"]["mutation_preview"]["diff_preview"])
                self.assertEqual(autonomy["execution_trace"][0]["event"], "tool_gate_decision")
                self.assertEqual(autonomy["block_reason"], "")

    def test_turn_envelope_keeps_non_tool_access_request_pending_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            session = _FakeSession()
            runtime_bundle = SimpleNamespace(
                thread_id="thread-b",
                backend_session=session,
                memory_admin=_FakeMemoryAdmin(),
                settings=SimpleNamespace(
                    checkpoint_db_path=checkpoint_db,
                    data_dir=root,
                    model_provider="dashscope",
                    model_name="qwen3.5-plus",
                    model_base_url="",
                    runtime_mode="cli",
                ),
            )
            api = BackendAPI(runtime_bundle=runtime_bundle, base_data_dir=root, cwd=root)
            packet = {
                "proposal_id": "ap-access-help-1",
                "origin": "counterpart_request",
                "intent": "access:request_help",
                "status": "awaiting_approval",
                "risk": "external_mutation",
                "requires_approval": True,
                "capability_steps": [
                    {
                        "kind": "access",
                        "name": "request_help",
                        "target": "account_login / cookies",
                        "status": "awaiting_approval",
                        "requires_approval": True,
                    }
                ],
                "expected_effect": "这一步需要先向你请求账号入口和 cookies。",
                "access_acquire_proposals": [
                    {
                        "target": "account_login",
                        "mode": "operator_login",
                        "summary": "先把账号登录补回来。",
                        "operator_action": "登录目标账号。",
                        "grants": ["account_login", "browser_session"],
                        "requires_operator": True,
                    }
                ],
            }
            state_values = {
                "final_text": "这一步我得先向你要入口。",
                "current_event": {"kind": "user_utterance"},
                "autonomy_intent": {
                    "mode": "approval_pending",
                    "origin": "counterpart_request",
                    "reason": "这一步需要先向你请求账号入口和 cookies。",
                    "confidence": 0.71,
                    "primary_proposal_id": "ap-access-help-1",
                },
                "action_packets": [packet],
                "pending_action_proposal": dict(packet),
                "action_trace": [
                    {
                        "proposal_id": "ap-access-help-1",
                        "intent": "access:request_help",
                        "origin": "counterpart_request",
                        "status": "awaiting_approval",
                        "event": "derived_from_access_request",
                        "risk": "external_mutation",
                        "source": "prepare_turn_runtime",
                        "requires_approval": True,
                    }
                ],
                "autonomy_block_reason": "",
            }

            turn = api.build_turn_response(state_values=state_values, streamed_text="")
            autonomy = turn.payload["autonomy"]
            access_state = turn.payload["digital_body"]["access_state"]

            self.assertEqual(autonomy["intent"]["mode"], "approval_pending")
            self.assertEqual(autonomy["action_packets"][0]["intent"], "access:request_help")
            proposals = autonomy["action_packets"][0].get("access_acquire_proposals") if isinstance(autonomy["action_packets"][0].get("access_acquire_proposals"), list) else []
            self.assertTrue(proposals)
            self.assertEqual(proposals[0]["target"], "account_login")
            body_proposals = access_state.get("access_acquire_proposals") if isinstance(access_state.get("access_acquire_proposals"), list) else []
            self.assertTrue(body_proposals)
            self.assertEqual(body_proposals[0]["mode"], "operator_login")
            self.assertEqual(autonomy["pending_approval"]["proposal_id"], "ap-access-help-1")
            self.assertEqual(autonomy["execution_trace"][0]["event"], "derived_from_access_request")
            self.assertEqual(autonomy["block_reason"], "")


if __name__ == "__main__":
    unittest.main()
