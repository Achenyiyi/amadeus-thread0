from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from langchain_core.messages import AIMessage, ToolMessage

from amadeus_thread0.graph_parts.autonomy_runtime import (
    _embodied_carryover_autonomy_signal,
    derive_autonomy_runtime,
    refresh_autonomy_intent_from_packets,
)
from amadeus_thread0.graph_parts.graph_builder import _route_after_prepare
from amadeus_thread0.graph_parts.tool_nodes import _node_autonomy_execute, _node_tool_execute, _node_tool_gate


class CompanionAutonomyRuntimeTests(unittest.TestCase):
    class _SourceRefStore:
        def __init__(self, refs):
            self._refs = list(refs)

        def list_source_refs(self, limit=120):
            return list(self._refs[:limit])

    def test_derive_autonomy_runtime_builds_queue_followthrough_packet(self):
        runtime = derive_autonomy_runtime(
            current_event={"kind": "scheduled_life_due", "self_activity_momentum": 0.63},
            behavior_action={
                "interaction_mode": "self_activity_reopen",
                "engagement_level": 0.52,
                "initiative_level": 0.41,
                "goal_frame": "先把前面的小窗口轻轻留住。",
                "action_target": "counterpart",
            },
            behavior_plan={
                "kind": "deferred_checkin",
                "target": "counterpart",
                "trigger_family": "life_window",
                "goal_frame": "等更自然的时候再续上。",
            },
            behavior_queue=[{"agenda_id": "agenda-1", "kind": "deferred_checkin", "status": "queued"}],
            world_model_state={"self_activity_momentum": 0.57},
            semantic_narrative_profile={"continuity_depth": 0.61, "history_weight": 0.48},
            interaction_carryover={"strength": 0.46},
            agenda_lifecycle_residue={"continuity_anchor": 0.68, "own_rhythm_anchor": 0.71},
        )
        self.assertEqual(runtime["autonomy_intent"]["mode"], "queue_followthrough")
        self.assertEqual(runtime["autonomy_intent"]["origin"], "own_rhythm")
        self.assertEqual(runtime["action_packets"][0]["linked_queue_id"], "agenda-1")
        self.assertEqual(runtime["action_trace"][0]["event"], "derived_from_behavior")

    def test_refresh_autonomy_intent_marks_approval_pending_from_packets(self):
        intent = refresh_autonomy_intent_from_packets(
            {"mode": "language_response", "origin": "counterpart_request", "confidence": 0.44},
            [
                {
                    "proposal_id": "ap-1",
                    "origin": "motive_goal",
                    "intent": "tool:write_diary",
                    "status": "awaiting_approval",
                    "risk": "external_mutation",
                    "requires_approval": True,
                    "expected_effect": "写一条外部记录",
                }
            ],
            current_event={"kind": "user_utterance"},
        )
        self.assertEqual(intent["mode"], "approval_pending")
        self.assertTrue(intent["requires_approval"])
        self.assertEqual(intent["primary_proposal_id"], "ap-1")

    def test_refresh_autonomy_intent_marks_completed_access_request_as_resolved(self):
        intent = refresh_autonomy_intent_from_packets(
            {"mode": "approval_pending", "origin": "counterpart_request", "primary_proposal_id": "ap-access-1"},
            [
                {
                    "proposal_id": "ap-access-1",
                    "origin": "counterpart_request",
                    "intent": "access:request_help",
                    "status": "completed",
                    "risk": "external_mutation",
                    "requires_approval": True,
                    "expected_effect": "这一步需要先向你请求账号入口和 cookies。",
                    "result_summary": "用户已经补上账号入口和 cookies。",
                }
            ],
            current_event={"kind": "user_utterance"},
        )
        self.assertEqual(intent["mode"], "access_request_resolved")
        self.assertEqual(intent["reason"], "用户已经补上账号入口和 cookies。")
        self.assertTrue(intent["requires_approval"])
        self.assertEqual(intent["primary_proposal_id"], "ap-access-1")

    def test_derive_autonomy_runtime_reuses_carried_embodied_access_request_for_pending_intent(self):
        runtime = derive_autonomy_runtime(
            current_event={"kind": "user_utterance"},
            behavior_action={},
            behavior_plan={},
            behavior_queue=[],
            interaction_carryover={
                "strength": 0.18,
                "embodied_context": {
                    "kind": "access_request_pending",
                    "primary_status": "awaiting_approval",
                    "primary_origin": "counterpart_request",
                    "requested_access": ["workspace_write"],
                    "requested_help": True,
                },
            },
        )
        self.assertEqual(runtime["autonomy_intent"]["mode"], "approval_pending")
        self.assertEqual(runtime["autonomy_intent"]["origin"], "counterpart_request")
        self.assertTrue(runtime["autonomy_intent"]["requires_approval"])
        self.assertGreaterEqual(float(runtime["autonomy_intent"]["continuity_weight"]), 0.46)
        self.assertIn("workspace_write", str(runtime["autonomy_intent"]["reason"]))
        self.assertEqual(str(runtime["autonomy_block_reason"]), "")

    def test_derive_autonomy_runtime_reuses_carried_embodied_friction_for_block_reason(self):
        runtime = derive_autonomy_runtime(
            current_event={"kind": "user_utterance"},
            behavior_action={},
            behavior_plan={},
            behavior_queue=[],
            interaction_carryover={
                "embodied_context": {
                    "kind": "environmental_friction",
                    "primary_origin": "capability_upgrade",
                    "missing_access": ["browser_session"],
                    "block_reason": "browser session missing",
                },
            },
        )
        self.assertEqual(runtime["autonomy_intent"]["mode"], "blocked")
        self.assertEqual(runtime["autonomy_intent"]["origin"], "capability_upgrade")
        self.assertIn("browser session missing", str(runtime["autonomy_intent"]["reason"]))
        self.assertEqual(str(runtime["autonomy_block_reason"]), "browser session missing")

    def test_derive_autonomy_runtime_turns_detached_artifact_into_reacquisition_packet(self):
        runtime = derive_autonomy_runtime(
            current_event={"kind": "user_utterance"},
            behavior_action={},
            behavior_plan={},
            behavior_queue=[],
            interaction_carryover={
                "strength": 0.28,
                "embodied_context": {
                    "artifact_continuity": "detached",
                    "active_artifact_kind": "file",
                    "active_artifact_label": "plan.md",
                    "artifact_reacquisition_mode": "reopen_file",
                    "primary_origin": "counterpart_request",
                },
            },
        )
        self.assertEqual(runtime["autonomy_intent"]["mode"], "reacquire_artifact")
        self.assertEqual(runtime["autonomy_intent"]["origin"], "counterpart_request")
        self.assertEqual(runtime["action_packets"][0]["intent"], "artifact:reopen_file")
        self.assertEqual(runtime["action_packets"][0]["risk"], "read")
        self.assertFalse(runtime["action_packets"][0]["requires_approval"])
        self.assertEqual(runtime["action_packets"][0]["tool_name"], "reacquire_artifact")
        self.assertEqual(runtime["action_packets"][0]["tool_args"]["mode"], "reopen_file")
        self.assertEqual(runtime["action_packets"][0]["tool_args"]["artifact_label"], "plan.md")
        self.assertEqual(runtime["action_trace"][0]["event"], "derived_from_embodied_carryover")
        self.assertIn("plan.md", str(runtime["autonomy_intent"]["reason"]))

    def test_derive_autonomy_runtime_binds_workspace_root_for_relative_workspace_artifact(self):
        runtime = derive_autonomy_runtime(
            current_event={"kind": "user_utterance"},
            behavior_action={},
            behavior_plan={},
            behavior_queue=[],
            interaction_carryover={
                "strength": 0.29,
                "embodied_context": {
                    "artifact_continuity": "detached",
                    "active_artifact_kind": "file",
                    "active_artifact_ref": "notes/plan.md",
                    "active_artifact_label": "plan.md",
                    "workspace_root": "E:/runtime/workspaces/lab-notes",
                    "artifact_reacquisition_mode": "reopen_file",
                    "primary_origin": "counterpart_request",
                },
            },
        )
        self.assertEqual(runtime["autonomy_intent"]["mode"], "reacquire_artifact")
        self.assertEqual(runtime["action_packets"][0]["intent"], "artifact:reopen_file")
        self.assertEqual(runtime["action_packets"][0]["tool_args"]["artifact_ref"], "notes/plan.md")
        self.assertEqual(
            runtime["action_packets"][0]["tool_args"]["workspace_root"],
            "E:/runtime/workspaces/lab-notes",
        )

    def test_derive_autonomy_runtime_turns_stale_saved_source_ref_into_inspection_packet(self):
        runtime = derive_autonomy_runtime(
            current_event={"kind": "user_utterance"},
            behavior_action={},
            behavior_plan={},
            behavior_queue=[],
            interaction_carryover={
                "strength": 0.31,
                "embodied_context": {
                    "artifact_continuity": "stale",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [17],
                    "active_artifact_kind": "search_result",
                    "active_artifact_label": "Persistence",
                    "active_artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "artifact_source_query": "langgraph persistence checkpointer thread",
                    "artifact_source_title": "Persistence",
                    "primary_origin": "counterpart_request",
                },
            },
        )

        self.assertEqual(runtime["autonomy_intent"]["mode"], "inspect_source_ref")
        self.assertEqual(runtime["autonomy_intent"]["origin"], "counterpart_request")
        self.assertEqual(runtime["action_packets"][0]["intent"], "artifact:inspect_source_ref")
        self.assertEqual(runtime["action_packets"][0]["tool_name"], "inspect_source_ref")
        self.assertEqual(runtime["action_packets"][0]["risk"], "read")
        self.assertFalse(runtime["action_packets"][0]["requires_approval"])
        self.assertEqual(runtime["action_packets"][0]["tool_args"]["source_ref_id"], 17)
        self.assertEqual(runtime["action_trace"][0]["event"], "derived_from_source_ref_refresh")
        self.assertIn("Persistence", str(runtime["autonomy_intent"]["reason"]))

    def test_derive_autonomy_runtime_turns_stale_saved_source_ref_pair_into_comparison_packet(self):
        runtime = derive_autonomy_runtime(
            current_event={"kind": "user_utterance"},
            behavior_action={},
            behavior_plan={},
            behavior_queue=[],
            interaction_carryover={
                "strength": 0.33,
                "embodied_context": {
                    "artifact_continuity": "stale",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [21, 17],
                    "active_artifact_kind": "search_result",
                    "active_artifact_label": "Persistence v2",
                    "active_artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "artifact_source_query": "langgraph persistence checkpointer thread recovery",
                    "artifact_source_title": "Persistence v2",
                    "primary_origin": "counterpart_request",
                },
            },
        )

        self.assertEqual(runtime["autonomy_intent"]["mode"], "compare_source_refs")
        self.assertEqual(runtime["autonomy_intent"]["origin"], "counterpart_request")
        self.assertEqual(runtime["action_packets"][0]["intent"], "artifact:compare_source_refs")
        self.assertEqual(runtime["action_packets"][0]["tool_name"], "compare_source_refs")
        self.assertEqual(runtime["action_packets"][0]["tool_args"]["source_ref_id"], 21)
        self.assertEqual(runtime["action_packets"][0]["tool_args"]["compare_source_ref_id"], 17)
        self.assertEqual(runtime["action_trace"][0]["event"], "derived_from_source_ref_compare")
        self.assertIn("Persistence v2", str(runtime["autonomy_intent"]["reason"]))

    def test_derive_autonomy_runtime_preserves_candidate_set_for_stale_saved_source_ref_comparison(self):
        runtime = derive_autonomy_runtime(
            current_event={"kind": "user_utterance"},
            behavior_action={},
            behavior_plan={},
            behavior_queue=[],
            interaction_carryover={
                "strength": 0.33,
                "embodied_context": {
                    "artifact_continuity": "stale",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [31, 33, 32],
                    "active_artifact_kind": "search_result",
                    "active_artifact_label": "Spec Draft",
                    "active_artifact_ref": "https://docs.example.com/spec",
                    "artifact_source_query": "amadeus source anchor draft",
                    "artifact_source_title": "Spec Draft",
                    "primary_origin": "counterpart_request",
                },
            },
        )

        self.assertEqual(runtime["autonomy_intent"]["mode"], "compare_source_refs")
        self.assertEqual(runtime["action_packets"][0]["tool_name"], "compare_source_refs")
        self.assertEqual(runtime["action_packets"][0]["tool_args"]["source_ref_id"], 31)
        self.assertEqual(runtime["action_packets"][0]["tool_args"]["source_ref_ids"], [31, 33, 32])
        self.assertNotIn("compare_source_ref_id", runtime["action_packets"][0]["tool_args"])
        self.assertEqual(runtime["action_trace"][0]["event"], "derived_from_source_ref_compare")

    def test_derive_autonomy_runtime_prefers_inspection_after_saved_source_ref_pair_is_reanchored(self):
        runtime = derive_autonomy_runtime(
            current_event={"kind": "user_utterance"},
            behavior_action={},
            behavior_plan={},
            behavior_queue=[],
            interaction_carryover={
                "strength": 0.33,
                "embodied_context": {
                    "kind": "source_material_compared",
                    "artifact_continuity": "stale",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [21, 17],
                    "preferred_source_ref_id": 21,
                    "preferred_anchor_reason": "primary_more_current",
                    "active_artifact_kind": "search_result",
                    "active_artifact_label": "Persistence v2",
                    "active_artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "artifact_source_query": "langgraph persistence checkpointer thread recovery",
                    "artifact_source_title": "Persistence v2",
                    "primary_origin": "counterpart_request",
                },
            },
        )

        self.assertEqual(runtime["autonomy_intent"]["mode"], "inspect_source_ref")
        self.assertEqual(runtime["action_packets"][0]["intent"], "artifact:inspect_source_ref")
        self.assertEqual(runtime["action_packets"][0]["tool_name"], "inspect_source_ref")
        self.assertEqual(runtime["action_packets"][0]["tool_args"]["source_ref_id"], 21)
        self.assertEqual(runtime["action_trace"][0]["event"], "derived_from_source_ref_refresh")

    def test_embodied_carryover_signal_prefers_inspection_after_source_ref_pair_is_reanchored(self):
        signal = _embodied_carryover_autonomy_signal(
            {
                "embodied_context": {
                    "kind": "source_material_compared",
                    "artifact_continuity": "stale",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [21, 17],
                    "preferred_source_ref_id": 21,
                    "preferred_anchor_reason": "primary_more_current",
                    "active_artifact_kind": "search_result",
                    "active_artifact_label": "Persistence v2",
                    "active_artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "primary_origin": "counterpart_request",
                }
            }
        )

        self.assertEqual(signal["mode"], "inspect_source_ref")
        self.assertEqual(signal["origin"], "counterpart_request")
        self.assertFalse(signal["requires_approval"])
        self.assertEqual(signal["artifact_continuity"], "stale")
        self.assertIn("Persistence v2", str(signal["reason"]))

    def test_derive_autonomy_runtime_turns_stale_session_source_ref_into_inspection_packet(self):
        runtime = derive_autonomy_runtime(
            current_event={"kind": "user_utterance"},
            behavior_action={},
            behavior_plan={},
            behavior_queue=[],
            session_context={
                "digital_body_hints": {
                    "artifact_continuity": "stale",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [17],
                    "active_artifact_kind": "search_result",
                    "active_artifact_label": "Persistence",
                    "active_artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "artifact_source_query": "langgraph persistence checkpointer thread",
                    "artifact_source_title": "Persistence",
                }
            },
        )

        self.assertEqual(runtime["autonomy_intent"]["mode"], "inspect_source_ref")
        self.assertEqual(runtime["action_packets"][0]["tool_name"], "inspect_source_ref")
        self.assertEqual(runtime["action_packets"][0]["tool_args"]["source_ref_id"], 17)
        self.assertEqual(runtime["action_trace"][0]["event"], "derived_from_source_ref_refresh")

    def test_derive_autonomy_runtime_turns_stale_session_source_ref_pair_into_comparison_packet(self):
        runtime = derive_autonomy_runtime(
            current_event={"kind": "user_utterance"},
            behavior_action={},
            behavior_plan={},
            behavior_queue=[],
            session_context={
                "digital_body_hints": {
                    "artifact_continuity": "stale",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [21, 17],
                    "active_artifact_kind": "search_result",
                    "active_artifact_label": "Persistence v2",
                    "active_artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "artifact_source_query": "langgraph persistence checkpointer thread recovery",
                    "artifact_source_title": "Persistence v2",
                }
            },
        )

        self.assertEqual(runtime["autonomy_intent"]["mode"], "compare_source_refs")
        self.assertEqual(runtime["action_packets"][0]["tool_name"], "compare_source_refs")
        self.assertEqual(runtime["action_packets"][0]["tool_args"]["source_ref_id"], 21)
        self.assertEqual(runtime["action_packets"][0]["tool_args"]["compare_source_ref_id"], 17)
        self.assertEqual(runtime["action_trace"][0]["event"], "derived_from_source_ref_compare")

    def test_derive_autonomy_runtime_preserves_candidate_set_for_stale_session_source_ref_comparison(self):
        runtime = derive_autonomy_runtime(
            current_event={"kind": "user_utterance"},
            behavior_action={},
            behavior_plan={},
            behavior_queue=[],
            session_context={
                "digital_body_hints": {
                    "artifact_continuity": "stale",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [31, 33, 32],
                    "active_artifact_kind": "search_result",
                    "active_artifact_label": "Spec Draft",
                    "active_artifact_ref": "https://docs.example.com/spec",
                    "artifact_source_query": "amadeus source anchor draft",
                    "artifact_source_title": "Spec Draft",
                }
            },
        )

        self.assertEqual(runtime["autonomy_intent"]["mode"], "compare_source_refs")
        self.assertEqual(runtime["action_packets"][0]["tool_name"], "compare_source_refs")
        self.assertEqual(runtime["action_packets"][0]["tool_args"]["source_ref_id"], 31)
        self.assertEqual(runtime["action_packets"][0]["tool_args"]["source_ref_ids"], [31, 33, 32])
        self.assertNotIn("compare_source_ref_id", runtime["action_packets"][0]["tool_args"])
        self.assertEqual(runtime["action_trace"][0]["event"], "derived_from_source_ref_compare")

    def test_derive_autonomy_runtime_prefers_inspection_after_session_source_ref_pair_is_reanchored(self):
        runtime = derive_autonomy_runtime(
            current_event={"kind": "user_utterance"},
            behavior_action={},
            behavior_plan={},
            behavior_queue=[],
            session_context={
                "digital_body_hints": {
                    "artifact_continuity": "stale",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [21, 17],
                    "preferred_source_ref_id": 21,
                    "preferred_anchor_reason": "primary_more_current",
                    "active_artifact_kind": "search_result",
                    "active_artifact_label": "Persistence v2",
                    "active_artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "artifact_source_query": "langgraph persistence checkpointer thread recovery",
                    "artifact_source_title": "Persistence v2",
                }
            },
        )

        self.assertEqual(runtime["autonomy_intent"]["mode"], "inspect_source_ref")
        self.assertEqual(runtime["action_packets"][0]["tool_name"], "inspect_source_ref")
        self.assertEqual(runtime["action_packets"][0]["tool_args"]["source_ref_id"], 21)
        self.assertEqual(runtime["action_trace"][0]["event"], "derived_from_source_ref_refresh")

    def test_derive_autonomy_runtime_uses_same_family_procedural_bias_without_expanding_approval_scope(self):
        runtime = derive_autonomy_runtime(
            current_event={
                "kind": "user_utterance",
                "text": "继续跑刚才那类 pytest 检查。",
                "digital_body_hints": {
                    "filesystem_state": "writable",
                    "sandbox_mode": "restricted",
                    "sandbox_state": {
                        "availability": "restricted",
                        "allowed_roots": ["E:/repo/amadeus-thread0"],
                        "execution_policy": "approval_required",
                        "runner_kind": "docker_isolated_runner",
                        "isolation_level": "docker_local_isolated",
                        "image_ref": "amadeus-thread0/sandbox-phase2:py312",
                        "network_policy": "none",
                        "workspace_root_kind": "attached_repo_root",
                        "arbitrary_execution": False,
                    },
                    "workspace_root": "E:/repo/amadeus-thread0",
                },
            },
            behavior_action={},
            behavior_plan={},
            behavior_queue=[],
            interaction_carryover={
                "strength": 0.31,
                "embodied_context": {
                    "kind": "sandbox_execution_completed",
                    "primary_status": "completed",
                    "primary_tool_name": "execute_workspace_command",
                    "workspace_root": "E:/repo/amadeus-thread0",
                    "sandbox_run_id": "ap-pytest",
                    "sandbox_command_profile": "pytest",
                    "sandbox_runner_kind": "docker_isolated_runner",
                    "sandbox_isolation_level": "docker_local_isolated",
                    "sandbox_image_ref": "amadeus-thread0/sandbox-phase2:py312",
                    "sandbox_network_policy": "none",
                    "workspace_root_kind": "attached_repo_root",
                    "procedural_continuity": {
                        "capability_family": "sandbox",
                        "pattern": "pytest",
                        "confidence": 0.72,
                        "evidence_count": 2,
                        "last_success_ref": "ap-pytest",
                        "identity_safe": True,
                    },
                },
            },
            session_context={
                "digital_body_hints": {
                    "filesystem_state": "writable",
                    "sandbox_mode": "restricted",
                    "workspace_root": "E:/repo/amadeus-thread0",
                    "workspace_root_kind": "attached_repo_root",
                }
            },
        )

        packet = runtime["action_packets"][0]
        self.assertEqual(runtime["autonomy_intent"]["mode"], "approval_pending")
        self.assertEqual(runtime["autonomy_intent"]["origin"], "counterpart_request")
        self.assertTrue(runtime["autonomy_intent"]["requires_approval"])
        self.assertEqual(packet["intent"], "sandbox:execute_workspace_command")
        self.assertEqual(packet["tool_name"], "execute_workspace_command")
        self.assertEqual(packet["status"], "awaiting_approval")
        self.assertEqual(packet["risk"], "external_mutation")
        self.assertTrue(packet["requires_approval"])
        self.assertEqual(packet["execution_spec"]["executor"], "pytest")
        self.assertEqual(packet["execution_spec"]["profile"], "pytest")
        self.assertEqual(packet["execution_spec"]["runner_kind"], "docker_isolated_runner")
        self.assertEqual(packet["execution_spec"]["network_policy"], "none")
        self.assertEqual(packet["execution_spec"]["allowed_roots"], ["E:/repo/amadeus-thread0"])
        self.assertEqual(runtime["pending_action_proposal"]["proposal_id"], packet["proposal_id"])
        self.assertEqual(runtime["action_trace"][0]["event"], "derived_from_procedural_continuity")

    def test_derive_autonomy_runtime_ignores_procedural_bias_when_access_claim_widens_current_body(self):
        runtime = derive_autonomy_runtime(
            current_event={
                "kind": "user_utterance",
                "text": "继续跑刚才那类 pytest 检查。",
                "digital_body_hints": {
                    "filesystem_state": "writable",
                    "sandbox_mode": "restricted",
                    "workspace_root": "E:/runtime/workspaces/current",
                },
            },
            behavior_action={},
            behavior_plan={},
            behavior_queue=[],
            interaction_carryover={
                "strength": 0.31,
                "embodied_context": {
                    "kind": "sandbox_execution_completed",
                    "primary_status": "completed",
                    "primary_tool_name": "execute_workspace_command",
                    "workspace_root": "E:/repo/amadeus-thread0",
                    "sandbox_command_profile": "pytest",
                    "procedural_continuity": {
                        "capability_family": "sandbox",
                        "pattern": "pytest",
                        "confidence": 0.72,
                        "evidence_count": 2,
                        "last_success_ref": "ap-pytest",
                        "identity_safe": True,
                    },
                },
            },
            session_context={
                "digital_body_hints": {
                    "filesystem_state": "writable",
                    "sandbox_mode": "restricted",
                    "workspace_root": "E:/runtime/workspaces/current",
                    "workspace_root_kind": "runtime_owned",
                }
            },
        )

        self.assertEqual(runtime["autonomy_intent"]["mode"], "refresh_access_state")
        self.assertEqual(runtime["action_packets"][0]["intent"], "access:refresh_state")
        self.assertNotEqual(runtime["action_packets"][0].get("tool_name"), "execute_workspace_command")
        self.assertEqual(runtime["pending_action_proposal"], {})
        self.assertEqual(runtime["action_trace"][0]["event"], "derived_from_access_refresh")

    def test_derive_autonomy_runtime_uses_phase2_procedural_trace_bias_for_pytest_packet(self):
        runtime = derive_autonomy_runtime(
            current_event={
                "kind": "user_utterance",
                "text": "继续跑刚才那类 pytest 检查。",
                "digital_body_hints": {
                    "filesystem_state": "writable",
                    "sandbox_mode": "restricted",
                    "sandbox_state": {
                        "availability": "restricted",
                        "allowed_roots": ["E:/repo/amadeus-thread0"],
                        "execution_policy": "approval_required",
                        "runner_kind": "docker_isolated_runner",
                        "isolation_level": "docker_local_isolated",
                        "image_ref": "amadeus-thread0/sandbox-phase2:py312",
                        "network_policy": "none",
                        "workspace_root_kind": "attached_repo_root",
                        "arbitrary_execution": False,
                    },
                    "workspace_root": "E:/repo/amadeus-thread0",
                },
            },
            behavior_action={},
            behavior_plan={},
            behavior_queue=[],
            interaction_carryover={
                "strength": 0.31,
                "embodied_context": {
                    "workspace_root": "E:/repo/amadeus-thread0",
                    "sandbox_runner_kind": "docker_isolated_runner",
                    "sandbox_isolation_level": "docker_local_isolated",
                    "sandbox_image_ref": "amadeus-thread0/sandbox-phase2:py312",
                    "sandbox_network_policy": "none",
                    "workspace_root_kind": "attached_repo_root",
                    "procedural_traces": [
                        {
                            "trace_id": "proc_phase2_pytest",
                            "trace_kind": "sandbox_execution_pattern",
                            "source_proposal_id": "ap-phase2-pytest",
                            "source_run_id": "run-phase2-pytest",
                            "source_tool_name": "execute_workspace_command",
                            "status": "completed",
                            "procedure_steps": ["inspect cwd", "run bounded command", "read stdout/artifact"],
                            "result_summary": "pytest passed",
                            "reuse_conditions": ["similar workspace command", "pytest command profile"],
                            "boundary_notes": ["requires approval before execution"],
                            "confidence": 0.78,
                        }
                    ],
                },
            },
            session_context={
                "digital_body_hints": {
                    "filesystem_state": "writable",
                    "sandbox_mode": "restricted",
                    "workspace_root": "E:/repo/amadeus-thread0",
                    "workspace_root_kind": "attached_repo_root",
                }
            },
        )

        packet = runtime["action_packets"][0]
        planning = runtime["procedural_planning"]
        self.assertEqual(planning["bias_kind"], "sandbox_execute")
        self.assertEqual(planning["trace_id"], "proc_phase2_pytest")
        self.assertEqual(runtime["autonomy_intent"]["mode"], "approval_pending")
        self.assertTrue(runtime["autonomy_intent"]["requires_approval"])
        self.assertEqual(packet["intent"], "sandbox:execute_workspace_command")
        self.assertEqual(packet["status"], "awaiting_approval")
        self.assertEqual(packet["risk"], "external_mutation")
        self.assertTrue(packet["requires_approval"])
        self.assertEqual(packet["execution_spec"]["executor"], "pytest")
        self.assertEqual(packet["execution_spec"]["profile"], "pytest")
        self.assertEqual(packet["tool_args"]["procedural_planning"]["trace_id"], "proc_phase2_pytest")
        self.assertEqual(runtime["action_trace"][0]["event"], "derived_from_procedural_planning")
        self.assertEqual(runtime["action_trace"][0]["procedural_planning"]["trace_id"], "proc_phase2_pytest")

    def test_derive_autonomy_runtime_keeps_blocked_procedural_trace_as_readback_only_planning(self):
        runtime = derive_autonomy_runtime(
            current_event={
                "kind": "user_utterance",
                "text": "别再重复刚才被拦住的命令。",
                "digital_body_hints": {
                    "filesystem_state": "writable",
                    "sandbox_mode": "restricted",
                    "workspace_root": "E:/repo/amadeus-thread0",
                },
            },
            behavior_action={},
            behavior_plan={},
            behavior_queue=[],
            interaction_carryover={
                "strength": 0.31,
                "embodied_context": {
                    "workspace_root": "E:/repo/amadeus-thread0",
                    "procedural_traces": [
                        {
                            "trace_id": "proc_phase2_blocked",
                            "trace_kind": "blocked_boundary_pattern",
                            "source_proposal_id": "ap-blocked",
                            "source_run_id": "run-blocked",
                            "source_tool_name": "execute_workspace_command",
                            "status": "blocked",
                            "procedure_steps": ["preserve command preview", "read failure trace"],
                            "result_summary": "pip install was blocked",
                            "reuse_conditions": ["similar workspace command"],
                            "boundary_notes": ["package install is blocked in the sandbox"],
                            "confidence": 0.67,
                        }
                    ],
                },
            },
            session_context={
                "digital_body_hints": {
                    "filesystem_state": "writable",
                    "sandbox_mode": "restricted",
                    "workspace_root": "E:/repo/amadeus-thread0",
                }
            },
        )

        self.assertEqual(runtime["procedural_planning"]["bias_kind"], "boundary_only")
        self.assertFalse(runtime["procedural_planning"]["capability_claim"])
        self.assertNotEqual(runtime["action_packets"][0].get("tool_name"), "execute_workspace_command")
        self.assertEqual(runtime["procedural_planning"]["avoid_repeating_boundary"], True)

    def test_derive_autonomy_runtime_keeps_browser_takeover_trace_as_readback_only_planning(self):
        runtime = derive_autonomy_runtime(
            current_event={
                "kind": "user_utterance",
                "text": "继续刚才浏览器登录那一步。",
                "digital_body_hints": {
                    "browser_session": "present",
                    "workspace_root": "E:/repo/amadeus-thread0",
                },
            },
            behavior_action={},
            behavior_plan={},
            behavior_queue=[],
            interaction_carryover={
                "strength": 0.31,
                "embodied_context": {
                    "workspace_root": "E:/repo/amadeus-thread0",
                    "procedural_traces": [
                        {
                            "trace_id": "proc_phase2_browser",
                            "trace_kind": "blocked_boundary_pattern",
                            "source_proposal_id": "ap-browser",
                            "source_run_id": "run-browser",
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
                        }
                    ],
                },
            },
        )

        self.assertEqual(runtime["procedural_planning"]["bias_kind"], "browser_manual_takeover")
        self.assertTrue(runtime["procedural_planning"]["must_request_approval"])
        self.assertTrue(all(packet.get("tool_name") != "browser_fill" for packet in runtime["action_packets"]))

    def test_derive_autonomy_runtime_builds_access_refresh_packet_from_session_hints(self):
        runtime = derive_autonomy_runtime(
            current_event={"kind": "user_utterance"},
            behavior_action={},
            behavior_plan={},
            behavior_queue=[],
            session_context={
                "digital_body_hints": {
                    "browser_session": "present",
                    "account_state": "logged_in",
                    "cookie_state": "present",
                    "session_expires_in_s": 600,
                    "api_key_state": "missing",
                }
            },
        )

        self.assertEqual(runtime["autonomy_intent"]["mode"], "refresh_access_state")
        self.assertEqual(runtime["action_packets"][0]["intent"], "access:refresh_state")
        self.assertEqual(runtime["action_packets"][0]["risk"], "read")
        self.assertEqual(runtime["action_packets"][0]["tool_name"], "refresh_access_state")
        self.assertEqual(runtime["action_packets"][0]["tool_args"]["access_hints"]["browser_session"], "present")
        self.assertEqual(runtime["action_trace"][0]["event"], "derived_from_access_refresh")

    def test_derive_autonomy_runtime_builds_access_request_help_packet_from_event_scoped_gap(self):
        runtime = derive_autonomy_runtime(
            current_event={
                "kind": "user_utterance",
                "digital_body_hints": {
                    "browser_session": "missing",
                    "account_state": "logged_out",
                    "cookie_state": "expired",
                    "missing_access": ["browser_session", "account_login", "cookies"],
                    "requestable_access": ["browser_session", "account_login", "cookies"],
                },
            },
            behavior_action={},
            behavior_plan={},
            behavior_queue=[],
            session_context={
                "digital_body_hints": {
                    "browser_session": "present",
                    "account_state": "logged_in",
                    "cookie_state": "present",
                }
            },
        )

        packet = runtime["action_packets"][0]
        self.assertEqual(runtime["autonomy_intent"]["mode"], "approval_pending")
        self.assertEqual(packet["intent"], "access:request_help")
        self.assertEqual(packet["status"], "awaiting_approval")
        self.assertEqual(packet["risk"], "external_mutation")
        self.assertTrue(packet["requires_approval"])
        self.assertEqual(runtime["pending_action_proposal"]["proposal_id"], packet["proposal_id"])
        self.assertEqual(runtime["action_trace"][0]["event"], "derived_from_access_request")
        self.assertTrue(bool(runtime["session_context"]["digital_body_hints"]["requested_help"]))
        self.assertIn("account_login", runtime["session_context"]["digital_body_hints"]["requestable_access"])
        self.assertIn("human_approval", runtime["session_context"]["digital_body_hints"]["requestable_access"])
        self.assertEqual(runtime["session_context"]["digital_body_hints"]["primary_intent"], "access:request_help")
        proposals = packet.get("access_acquire_proposals") if isinstance(packet.get("access_acquire_proposals"), list) else []
        selected = packet.get("selected_access_proposal") if isinstance(packet.get("selected_access_proposal"), dict) else {}
        self.assertTrue(proposals)
        self.assertEqual(proposals[0]["target"], "account_login")
        self.assertEqual(proposals[0]["mode"], "operator_login")
        self.assertEqual(selected.get("target"), "account_login")
        self.assertEqual(selected.get("mode"), "operator_login")
        self.assertEqual(runtime["session_context"]["digital_body_hints"]["selected_access_proposal"]["mode"], "operator_login")
        self.assertTrue(any(item.get("mode") == "operator_register_account" and item.get("path_kind") == "create_new" for item in proposals))

    def test_derive_autonomy_runtime_consolidates_resolved_selected_access_proposal(self):
        runtime = derive_autonomy_runtime(
            current_event={"kind": "user_utterance"},
            behavior_action={},
            behavior_plan={},
            behavior_queue=[],
            session_context={
                "digital_body_hints": {
                    "api_key_state": "present",
                    "missing_access": [],
                    "requestable_access": [],
                    "requested_help": False,
                    "primary_proposal_id": "ap-access-help-arrived-1",
                    "primary_status": "approved",
                    "primary_origin": "counterpart_request",
                    "primary_intent": "access:request_help",
                    "access_acquire_proposals": [
                        {
                            "target": "api_key",
                            "mode": "operator_provide_api_key",
                            "summary": "先补一个可用 API key。",
                            "operator_action": "填入一个可用 key。",
                            "grants": ["api_key"],
                            "requires_operator": True,
                        }
                    ],
                    "selected_access_proposal": {
                        "target": "api_key",
                        "mode": "operator_provide_api_key",
                        "summary": "先补一个可用 API key。",
                        "operator_action": "填入一个可用 key。",
                        "grants": ["api_key"],
                        "requires_operator": True,
                    },
                }
            },
        )

        packet = runtime["action_packets"][0]
        self.assertEqual(runtime["autonomy_intent"]["mode"], "access_request_resolved")
        self.assertEqual(packet["intent"], "access:request_help")
        self.assertEqual(packet["status"], "completed")
        self.assertTrue(packet["writeback_ready"])
        self.assertIn("已经补回来了", str(packet["result_summary"]))
        self.assertEqual(runtime["action_trace"][0]["event"], "derived_from_access_arrival")
        hints = runtime["session_context"]["digital_body_hints"]
        self.assertEqual(hints["primary_status"], "completed")
        self.assertNotIn("selected_access_proposal", hints)

    def test_derive_autonomy_runtime_surfaces_partial_selected_access_progress(self):
        proposal = {
            "target": "account_login",
            "mode": "operator_login",
            "summary": "先把账号登录补回来，这条外部入口才接得上后面。",
            "operator_action": "登录目标账号，或把现成登录态交给我。",
            "grants": ["account_login", "browser_session"],
            "requires_operator": True,
        }
        runtime = derive_autonomy_runtime(
            current_event={"kind": "user_utterance"},
            behavior_action={},
            behavior_plan={},
            behavior_queue=[],
            session_context={
                "digital_body_hints": {
                    "account_state": "logged_in",
                    "browser_session": "missing",
                    "missing_access": ["browser_session"],
                    "requestable_access": ["browser_session"],
                    "requested_help": False,
                    "primary_proposal_id": "ap-access-help-partial-1",
                    "primary_status": "approved",
                    "primary_origin": "counterpart_request",
                    "primary_intent": "access:request_help",
                    "access_acquire_proposals": [proposal],
                    "selected_access_proposal": proposal,
                }
            },
        )

        packet = runtime["action_packets"][0]
        self.assertEqual(packet["status"], "approved")
        self.assertFalse(packet["writeback_ready"])
        self.assertIn("还差", str(packet["result_summary"]))
        self.assertEqual(runtime["autonomy_intent"]["mode"], "access_acquire_planned")
        self.assertIn("还差", str(runtime["autonomy_intent"]["reason"]))
        self.assertEqual(runtime["action_trace"][0]["event"], "derived_from_access_partial_arrival")
        selected = packet.get("selected_access_proposal") if isinstance(packet.get("selected_access_proposal"), dict) else {}
        self.assertEqual(selected.get("resolved_grants"), ["account_login"])
        self.assertEqual(selected.get("pending_grants"), ["browser_session"])
        self.assertEqual(selected.get("completion_ratio"), 0.5)
        hints = runtime["session_context"]["digital_body_hints"]
        self.assertEqual(hints["primary_status"], "approved")
        self.assertIn("selected_access_proposal", hints)

    def test_derive_autonomy_runtime_does_not_override_meaningful_behavior_packet_with_artifact_bias(self):
        runtime = derive_autonomy_runtime(
            current_event={"kind": "scheduled_life_due", "self_activity_momentum": 0.63},
            behavior_action={
                "interaction_mode": "self_activity_reopen",
                "engagement_level": 0.52,
                "initiative_level": 0.41,
                "goal_frame": "先把前面的小窗口轻轻留住。",
                "action_target": "counterpart",
            },
            behavior_plan={
                "kind": "deferred_checkin",
                "target": "counterpart",
                "trigger_family": "life_window",
                "goal_frame": "等更自然的时候再续上。",
            },
            behavior_queue=[{"agenda_id": "agenda-1", "kind": "deferred_checkin", "status": "queued"}],
            world_model_state={"self_activity_momentum": 0.57},
            semantic_narrative_profile={"continuity_depth": 0.61, "history_weight": 0.48},
            interaction_carryover={
                "strength": 0.46,
                "embodied_context": {
                    "artifact_continuity": "detached",
                    "active_artifact_kind": "file",
                    "active_artifact_label": "plan.md",
                    "artifact_reacquisition_mode": "reopen_file",
                    "primary_origin": "counterpart_request",
                },
            },
            agenda_lifecycle_residue={"continuity_anchor": 0.68, "own_rhythm_anchor": 0.71},
        )
        self.assertEqual(runtime["autonomy_intent"]["mode"], "queue_followthrough")
        self.assertEqual(runtime["action_packets"][0]["linked_queue_id"], "agenda-1")
        self.assertNotEqual(runtime["action_packets"][0]["intent"], "artifact:reopen_file")
        self.assertEqual(runtime["action_trace"][0]["event"], "derived_from_behavior")

    def test_route_after_prepare_can_branch_into_autonomy_execute_for_artifact_packet(self):
        route = _route_after_prepare(
            {
                "current_event": {"kind": "user_utterance"},
                "behavior_action": {"channel": "speech"},
                "action_packets": [
                    {
                        "proposal_id": "ap-artifact-1",
                        "origin": "counterpart_request",
                        "intent": "artifact:reopen_file",
                        "status": "proposed",
                        "risk": "read",
                        "requires_approval": False,
                        "capability_steps": [
                            {"kind": "artifact", "name": "reopen_file", "target": "plan.md", "status": "pending"}
                        ],
                    }
                ],
            }
        )
        self.assertEqual(route, "autonomy_execute")

    def test_route_after_prepare_can_branch_into_autonomy_execute_for_access_packet(self):
        route = _route_after_prepare(
            {
                "current_event": {"kind": "user_utterance"},
                "behavior_action": {"channel": "speech"},
                "action_packets": [
                    {
                        "proposal_id": "ap-access-1",
                        "origin": "motive_goal",
                        "intent": "access:refresh_state",
                        "status": "proposed",
                        "risk": "read",
                        "requires_approval": False,
                        "capability_steps": [
                            {"kind": "access", "name": "refresh_state", "target": "session_refresh", "status": "pending"}
                        ],
                    }
                ],
            }
        )
        self.assertEqual(route, "autonomy_execute")

    def test_route_after_prepare_can_branch_into_autonomy_execute_for_workspace_file_mutation_packet(self):
        route = _route_after_prepare(
            {
                "current_event": {"kind": "user_utterance"},
                "behavior_action": {"channel": "speech"},
                "session_context": {
                    "digital_body_hints": {
                        "filesystem_state": "writable",
                        "active_artifact_kind": "workspace",
                        "active_artifact_ref": "E:/runtime/workspaces/lab",
                        "active_artifact_label": "lab",
                    }
                },
                "action_packets": [
                    {
                        "proposal_id": "ap-file-write-1",
                        "origin": "counterpart_request",
                        "intent": "artifact:write_file",
                        "status": "approved",
                        "risk": "external_mutation",
                        "requires_approval": True,
                        "tool_name": "write_workspace_file",
                        "tool_args": {
                            "relative_path": "notes/todo.md",
                            "content": "buy bananas",
                        },
                        "capability_steps": [
                            {"kind": "tool_call", "name": "write_workspace_file", "target": "notes/todo.md", "status": "approved"}
                        ],
                    }
                ],
            }
        )
        self.assertEqual(route, "autonomy_execute")

    def test_route_after_prepare_keeps_access_request_help_on_model_path(self):
        route = _route_after_prepare(
            {
                "current_event": {"kind": "user_utterance"},
                "behavior_action": {"channel": "speech"},
                "action_packets": [
                    {
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
                    }
                ],
            }
        )
        self.assertEqual(route, "call_model")

    def test_autonomy_execute_can_complete_local_file_reacquisition(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "plan.md"
            path.write_text("# plan\nartifact continuity test\n", encoding="utf-8")
            state = {
                "current_event": {"kind": "user_utterance", "text": "继续前面的计划。"},
                "interaction_carryover": {
                    "embodied_context": {
                        "artifact_continuity": "detached",
                        "active_artifact_kind": "file",
                        "active_artifact_ref": str(path),
                        "active_artifact_label": "plan.md",
                        "artifact_reacquisition_mode": "reopen_file",
                    }
                },
                "session_context": {"digital_body_hints": {"artifact_continuity": "detached"}},
                "autonomy_intent": {"mode": "reacquire_artifact", "origin": "counterpart_request"},
                "action_packets": [
                    {
                        "proposal_id": "ap-artifact-1",
                        "origin": "counterpart_request",
                        "intent": "artifact:reopen_file",
                        "status": "proposed",
                        "risk": "read",
                        "requires_approval": False,
                        "capability_steps": [
                            {
                                "kind": "artifact",
                                "name": "reopen_file",
                                "target": str(path),
                                "status": "pending",
                                "requires_approval": False,
                                "note": "先把 plan.md 重新打开，再继续往下做。",
                            }
                        ],
                        "expected_effect": "先把 plan.md 重新打开，再继续往下做。",
                    }
                ],
                "action_trace": [],
                "behavior_queue": [],
                "toolset_unlocks": {},
                "last_external_tools": [],
                "evidence_pack": [],
                "world_model_state": {},
                "semantic_narrative_profile": {},
                "turn_appraisal": {},
                "evolution_state": {},
                "emotion_state": {},
                "bond_state": {},
                "counterpart_assessment": {},
                "behavior_action": {},
                "behavior_plan": {},
                "agenda_lifecycle_residue": {},
            }
            out = _node_autonomy_execute(state)

        self.assertEqual(out["action_packets"][0]["status"], "completed")
        self.assertEqual(out["autonomy_intent"]["mode"], "reacquire_artifact")
        self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_continuity"], "attached")
        self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_carrier"], "filesystem")
        self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_source_ref_ids"], [])
        self.assertEqual(out["digital_body_state"]["resource_state"]["artifact_continuity"], "attached")
        self.assertEqual(out["digital_body_state"]["resource_state"]["artifact_carrier"], "filesystem")
        self.assertEqual(out["digital_body_state"]["resource_state"]["artifact_source_ref_ids"], [])
        self.assertIsInstance(out["messages"][0], AIMessage)
        self.assertIsInstance(out["messages"][1], ToolMessage)
        self.assertIn("plan.md", str(out["action_packets"][0]["result_summary"]))
        artifact_context = out["action_packets"][0].get("artifact_context") if isinstance(out["action_packets"][0].get("artifact_context"), dict) else {}
        self.assertEqual(artifact_context.get("carrier"), "filesystem")
        self.assertEqual(artifact_context.get("artifact_kind"), "file")
        self.assertEqual(artifact_context.get("artifact_label"), "plan.md")
        self.assertEqual(artifact_context.get("reacquisition_mode"), "reopen_file")
        self.assertTrue(bool(artifact_context.get("exists")))
        self.assertIn("artifact continuity test", str(artifact_context.get("preview") or ""))

    def test_autonomy_execute_can_reacquire_artifact_from_packet_binding_without_live_carryover(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "plan.md"
            path.write_text("# plan\nartifact continuity test\n", encoding="utf-8")
            state = {
                "current_event": {"kind": "user_utterance", "text": "继续前面的计划。"},
                "interaction_carryover": {},
                "session_context": {"digital_body_hints": {}},
                "autonomy_intent": {"mode": "reacquire_artifact", "origin": "counterpart_request"},
                "action_packets": [
                    {
                        "proposal_id": "ap-artifact-bound-1",
                        "origin": "counterpart_request",
                        "intent": "artifact:reopen_file",
                        "status": "approved",
                        "risk": "read",
                        "requires_approval": False,
                        "tool_name": "reacquire_artifact",
                        "tool_args": {
                            "mode": "reopen_file",
                            "artifact_kind": "file",
                            "artifact_ref": str(path),
                            "artifact_label": "plan.md",
                        },
                        "capability_steps": [
                            {
                                "kind": "artifact",
                                "name": "reopen_file",
                                "target": str(path),
                                "status": "approved",
                                "requires_approval": False,
                            }
                        ],
                    }
                ],
                "action_trace": [],
                "behavior_queue": [],
                "toolset_unlocks": {},
                "last_external_tools": [],
                "evidence_pack": [],
                "world_model_state": {},
                "semantic_narrative_profile": {},
                "turn_appraisal": {},
                "evolution_state": {},
                "emotion_state": {},
                "bond_state": {},
                "counterpart_assessment": {},
                "behavior_action": {},
                "behavior_plan": {},
                "agenda_lifecycle_residue": {},
            }
            out = _node_autonomy_execute(state)

        self.assertEqual(out["action_packets"][0]["status"], "completed")
        self.assertEqual(out["action_packets"][0]["tool_name"], "reacquire_artifact")
        self.assertEqual(out["action_packets"][0]["tool_args"]["artifact_ref"], str(path))
        self.assertEqual(out["autonomy_intent"]["mode"], "reacquire_artifact")
        artifact_context = out["action_packets"][0].get("artifact_context") if isinstance(out["action_packets"][0].get("artifact_context"), dict) else {}
        self.assertEqual(artifact_context.get("artifact_ref"), str(path))

    def test_autonomy_execute_can_reacquire_relative_workspace_file_from_live_carryover(self):
        with TemporaryDirectory() as td:
            workspace = Path(td) / "lab-notes"
            path = workspace / "notes" / "plan.md"
            path.parent.mkdir(parents=True)
            path.write_text("# plan\nrelative workspace continuity\n", encoding="utf-8")
            state = {
                "current_event": {"kind": "user_utterance", "text": "继续前面的文件。"},
                "interaction_carryover": {
                    "embodied_context": {
                        "artifact_continuity": "detached",
                        "active_artifact_kind": "file",
                        "active_artifact_ref": "notes/plan.md",
                        "active_artifact_label": "plan.md",
                        "workspace_root": str(workspace),
                        "artifact_reacquisition_mode": "reopen_file",
                    }
                },
                "session_context": {"digital_body_hints": {"artifact_continuity": "detached"}},
                "autonomy_intent": {"mode": "reacquire_artifact", "origin": "counterpart_request"},
                "action_packets": [
                    {
                        "proposal_id": "ap-artifact-relative-1",
                        "origin": "counterpart_request",
                        "intent": "artifact:reopen_file",
                        "status": "proposed",
                        "risk": "read",
                        "requires_approval": False,
                        "capability_steps": [
                            {
                                "kind": "artifact",
                                "name": "reopen_file",
                                "target": "notes/plan.md",
                                "status": "pending",
                                "requires_approval": False,
                            }
                        ],
                    }
                ],
                "action_trace": [],
                "behavior_queue": [],
                "toolset_unlocks": {},
                "last_external_tools": [],
                "evidence_pack": [],
                "world_model_state": {},
                "semantic_narrative_profile": {},
                "turn_appraisal": {},
                "evolution_state": {},
                "emotion_state": {},
                "bond_state": {},
                "counterpart_assessment": {},
                "behavior_action": {},
                "behavior_plan": {},
                "agenda_lifecycle_residue": {},
            }
            out = _node_autonomy_execute(state)

        self.assertEqual(out["action_packets"][0]["status"], "completed")
        self.assertEqual(out["session_context"]["digital_body_hints"]["workspace_root"], str(workspace))
        self.assertEqual(out["digital_body_state"]["resource_state"]["workspace_root"], str(workspace))
        artifact_context = out["action_packets"][0].get("artifact_context") if isinstance(out["action_packets"][0].get("artifact_context"), dict) else {}
        self.assertEqual(artifact_context.get("artifact_ref"), str(path))
        self.assertIn("relative workspace continuity", str(artifact_context.get("preview") or ""))

    def test_autonomy_execute_can_reacquire_relative_workspace_file_from_packet_binding(self):
        with TemporaryDirectory() as td:
            workspace = Path(td) / "lab-notes"
            path = workspace / "notes" / "plan.md"
            path.parent.mkdir(parents=True)
            path.write_text("# plan\nrelative packet binding\n", encoding="utf-8")
            state = {
                "current_event": {"kind": "user_utterance", "text": "继续前面的文件。"},
                "interaction_carryover": {},
                "session_context": {"digital_body_hints": {}},
                "autonomy_intent": {"mode": "reacquire_artifact", "origin": "counterpart_request"},
                "action_packets": [
                    {
                        "proposal_id": "ap-artifact-relative-bound-1",
                        "origin": "counterpart_request",
                        "intent": "artifact:reopen_file",
                        "status": "approved",
                        "risk": "read",
                        "requires_approval": False,
                        "tool_name": "reacquire_artifact",
                        "tool_args": {
                            "mode": "reopen_file",
                            "artifact_kind": "file",
                            "artifact_ref": "notes/plan.md",
                            "artifact_label": "plan.md",
                            "workspace_root": str(workspace),
                        },
                        "capability_steps": [
                            {
                                "kind": "artifact",
                                "name": "reopen_file",
                                "target": "notes/plan.md",
                                "status": "approved",
                                "requires_approval": False,
                            }
                        ],
                    }
                ],
                "action_trace": [],
                "behavior_queue": [],
                "toolset_unlocks": {},
                "last_external_tools": [],
                "evidence_pack": [],
                "world_model_state": {},
                "semantic_narrative_profile": {},
                "turn_appraisal": {},
                "evolution_state": {},
                "emotion_state": {},
                "bond_state": {},
                "counterpart_assessment": {},
                "behavior_action": {},
                "behavior_plan": {},
                "agenda_lifecycle_residue": {},
            }
            out = _node_autonomy_execute(state)

        self.assertEqual(out["action_packets"][0]["status"], "completed")
        self.assertEqual(out["session_context"]["digital_body_hints"]["workspace_root"], str(workspace))
        self.assertEqual(out["digital_body_state"]["resource_state"]["workspace_root"], str(workspace))
        artifact_context = out["action_packets"][0].get("artifact_context") if isinstance(out["action_packets"][0].get("artifact_context"), dict) else {}
        self.assertEqual(artifact_context.get("artifact_ref"), str(path))
        self.assertIn("relative packet binding", str(artifact_context.get("preview") or ""))

    def test_autonomy_execute_blocks_missing_local_file_reacquisition(self):
        state = {
            "current_event": {"kind": "user_utterance", "text": "继续前面的计划。"},
            "interaction_carryover": {
                "embodied_context": {
                    "artifact_continuity": "missing",
                    "active_artifact_kind": "file",
                    "active_artifact_ref": "missing-plan.md",
                    "active_artifact_label": "missing-plan.md",
                    "artifact_reacquisition_mode": "reopen_file",
                }
            },
            "session_context": {"digital_body_hints": {"artifact_continuity": "missing"}},
            "autonomy_intent": {"mode": "reacquire_artifact", "origin": "counterpart_request"},
            "action_packets": [
                {
                    "proposal_id": "ap-artifact-2",
                    "origin": "counterpart_request",
                    "intent": "artifact:reopen_file",
                    "status": "proposed",
                    "risk": "read",
                    "requires_approval": False,
                    "capability_steps": [
                        {
                            "kind": "artifact",
                            "name": "reopen_file",
                            "target": "missing-plan.md",
                            "status": "pending",
                            "requires_approval": False,
                        }
                    ],
                }
            ],
            "action_trace": [],
            "behavior_queue": [],
            "toolset_unlocks": {},
            "last_external_tools": [],
            "evidence_pack": [],
            "world_model_state": {},
            "semantic_narrative_profile": {},
            "turn_appraisal": {},
            "evolution_state": {},
            "emotion_state": {},
            "bond_state": {},
            "counterpart_assessment": {},
            "behavior_action": {},
            "behavior_plan": {},
            "agenda_lifecycle_residue": {},
        }
        out = _node_autonomy_execute(state)

        self.assertEqual(out["action_packets"][0]["status"], "blocked")
        self.assertIn("artifact path could not be resolved", str(out["autonomy_block_reason"]))
        self.assertEqual(out["digital_body_state"]["resource_state"]["artifact_continuity"], "missing")

    def test_autonomy_execute_can_reacquire_saved_search_surface_from_source_refs(self):
        store = self._SourceRefStore(
            [
                {
                    "id": 17,
                    "url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "title": "Persistence",
                    "query": "langgraph persistence checkpointer thread",
                    "tool_name": "search_langchain_docs",
                    "snippet": "Persistence in LangGraph uses checkpointers and thread-scoped state.",
                }
            ]
        )
        state = {
            "current_event": {"kind": "user_utterance", "text": "把刚才那条检索结果接回来。"},
            "interaction_carryover": {
                "embodied_context": {
                    "artifact_continuity": "missing",
                    "active_artifact_kind": "search_result",
                    "active_artifact_ref": "langgraph persistence checkpointer thread",
                    "active_artifact_label": "Persistence",
                    "artifact_reacquisition_mode": "rerun_search",
                }
            },
            "session_context": {"digital_body_hints": {"artifact_continuity": "missing"}},
            "autonomy_intent": {"mode": "reacquire_artifact", "origin": "counterpart_request"},
            "action_packets": [
                {
                    "proposal_id": "ap-artifact-3",
                    "origin": "counterpart_request",
                    "intent": "artifact:rerun_search",
                    "status": "proposed",
                    "risk": "read",
                    "requires_approval": False,
                    "capability_steps": [
                        {
                            "kind": "artifact",
                            "name": "rerun_search",
                            "target": "langgraph persistence checkpointer thread",
                            "status": "pending",
                            "requires_approval": False,
                        }
                    ],
                    "expected_effect": "先把前面的检索结果重新拿回来，再继续往下做。",
                }
            ],
            "action_trace": [],
            "behavior_queue": [],
            "toolset_unlocks": {},
            "last_external_tools": [],
            "evidence_pack": [],
            "world_model_state": {},
            "semantic_narrative_profile": {},
            "turn_appraisal": {},
            "evolution_state": {},
            "emotion_state": {},
            "bond_state": {},
            "counterpart_assessment": {},
            "behavior_action": {},
            "behavior_plan": {},
            "agenda_lifecycle_residue": {},
        }
        with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
            out = _node_autonomy_execute(state)

        self.assertEqual(out["action_packets"][0]["status"], "completed")
        self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_continuity"], "attached")
        self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_carrier"], "source_ref")
        self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_source_ref_ids"], [17])
        self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_source_title"], "Persistence")
        self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_source_tool_name"], "search_langchain_docs")
        self.assertEqual(out["digital_body_state"]["resource_state"]["artifact_continuity"], "attached")
        self.assertEqual(out["digital_body_state"]["resource_state"]["artifact_carrier"], "source_ref")
        self.assertEqual(out["digital_body_state"]["resource_state"]["artifact_source_ref_ids"], [17])
        self.assertEqual(out["digital_body_state"]["resource_state"]["artifact_source_title"], "Persistence")
        self.assertEqual(out["digital_body_state"]["resource_state"]["artifact_source_tool_name"], "search_langchain_docs")
        self.assertEqual(out["evidence_pack"][0]["source_id"], 17)
        self.assertIn("docs.langchain.com", str(out["evidence_pack"][0]["url"]))
        artifact_context = out["action_packets"][0].get("artifact_context") if isinstance(out["action_packets"][0].get("artifact_context"), dict) else {}
        self.assertEqual(artifact_context.get("carrier"), "source_ref")
        self.assertEqual(artifact_context.get("artifact_kind"), "search_result")
        self.assertEqual(artifact_context.get("artifact_label"), "Persistence")
        self.assertEqual(artifact_context.get("reacquisition_mode"), "rerun_search")
        self.assertEqual(artifact_context.get("source_ref_ids"), [17])
        self.assertIn("checkpointers", str(artifact_context.get("preview") or ""))
        self.assertIn("docs.langchain.com", str(artifact_context.get("source_url") or ""))

    def test_autonomy_execute_can_reacquire_saved_search_surface_from_content_only_source_refs(self):
        store = self._SourceRefStore(
            [
                {
                    "id": "17",
                    "content": {
                        "url": " https://docs.langchain.com/oss/python/langgraph/persistence ",
                        "title": " Persistence ",
                        "query": " langgraph persistence checkpointer thread ",
                        "tool_name": " search_langchain_docs ",
                        "snippet": " Persistence in LangGraph uses checkpointers and thread-scoped state. ",
                    },
                }
            ]
        )
        state = {
            "current_event": {"kind": "user_utterance", "text": "把刚才那条检索结果接回来。"},
            "interaction_carryover": {
                "embodied_context": {
                    "artifact_continuity": "missing",
                    "active_artifact_kind": "search_result",
                    "active_artifact_ref": "langgraph persistence checkpointer thread",
                    "active_artifact_label": "Persistence",
                    "artifact_reacquisition_mode": "rerun_search",
                }
            },
            "session_context": {"digital_body_hints": {"artifact_continuity": "missing"}},
            "autonomy_intent": {"mode": "reacquire_artifact", "origin": "counterpart_request"},
            "action_packets": [
                {
                    "proposal_id": "ap-artifact-3b",
                    "origin": "counterpart_request",
                    "intent": "artifact:rerun_search",
                    "status": "proposed",
                    "risk": "read",
                    "requires_approval": False,
                    "capability_steps": [
                        {
                            "kind": "artifact",
                            "name": "rerun_search",
                            "target": "langgraph persistence checkpointer thread",
                            "status": "pending",
                            "requires_approval": False,
                        }
                    ],
                    "expected_effect": "先把前面的检索结果重新拿回来，再继续往下做。",
                }
            ],
            "action_trace": [],
            "behavior_queue": [],
            "toolset_unlocks": {},
            "last_external_tools": [],
            "evidence_pack": [],
            "world_model_state": {},
            "semantic_narrative_profile": {},
            "turn_appraisal": {},
            "evolution_state": {},
            "emotion_state": {},
            "bond_state": {},
            "counterpart_assessment": {},
            "behavior_action": {},
            "behavior_plan": {},
            "agenda_lifecycle_residue": {},
        }
        with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
            out = _node_autonomy_execute(state)

        self.assertEqual(out["action_packets"][0]["status"], "completed")
        self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_source_ref_ids"], [17])
        self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_source_title"], "Persistence")
        self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_source_tool_name"], "search_langchain_docs")
        self.assertEqual(out["digital_body_state"]["resource_state"]["artifact_source_ref_ids"], [17])
        self.assertEqual(out["digital_body_state"]["resource_state"]["artifact_source_title"], "Persistence")
        self.assertEqual(out["evidence_pack"][0]["source_id"], 17)
        self.assertEqual(out["evidence_pack"][0]["title"], "Persistence")
        self.assertIn("docs.langchain.com", str(out["evidence_pack"][0]["url"]))
        self.assertIn("已重新接回检索结果", str(out["evidence_pack"][0]["query"]))

    def test_autonomy_execute_reacquire_saved_search_surface_preserves_preferred_anchor_hints(self):
        state = {
            "current_event": {"kind": "user_utterance", "text": "把刚才更合适的那条材料接回来。"},
            "interaction_carryover": {},
            "session_context": {"digital_body_hints": {}},
            "autonomy_intent": {"mode": "reacquire_artifact", "origin": "counterpart_request"},
            "action_packets": [
                {
                    "proposal_id": "ap-artifact-preferred-anchor-1",
                    "origin": "counterpart_request",
                    "intent": "artifact:rerun_search",
                    "status": "approved",
                    "risk": "read",
                    "requires_approval": False,
                    "tool_name": "reacquire_artifact",
                    "tool_args": {
                        "mode": "rerun_search",
                        "artifact_kind": "search_result",
                        "artifact_ref": "langgraph persistence checkpointer thread recovery",
                        "artifact_label": "Persistence v2",
                    },
                    "capability_steps": [
                        {
                            "kind": "artifact",
                            "name": "rerun_search",
                            "target": "langgraph persistence checkpointer thread recovery",
                            "status": "approved",
                            "requires_approval": False,
                        }
                    ],
                    "expected_effect": "先把之前更合适的材料重新接回来。",
                }
            ],
            "action_trace": [],
            "behavior_queue": [],
            "toolset_unlocks": {},
            "last_external_tools": [],
            "evidence_pack": [],
            "world_model_state": {},
            "semantic_narrative_profile": {},
            "turn_appraisal": {},
            "evolution_state": {},
            "emotion_state": {},
            "bond_state": {},
            "counterpart_assessment": {},
            "behavior_action": {},
            "behavior_plan": {},
            "agenda_lifecycle_residue": {},
        }
        with patch("amadeus_thread0.graph_parts.tool_nodes._tool_lookup", return_value=object()):
            with patch(
                "amadeus_thread0.graph_parts.tool_nodes._invoke_tool",
                return_value={
                    "artifact_continuity": "attached",
                    "artifact_kind": "search_result",
                    "artifact_ref": "langgraph persistence checkpointer thread recovery",
                    "artifact_label": "Persistence v2",
                    "artifact_reacquisition_mode": "rerun_search",
                    "artifact_preview": "Recovery keeps the same persistence thread coherent.",
                    "artifact_exists": True,
                    "source_ref_ids": [21, 17],
                    "preferred_source_ref_id": 21,
                    "preferred_anchor_reason": "primary_more_current",
                    "source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "source_query": "langgraph persistence checkpointer thread recovery",
                    "tool_name": "search_web",
                },
            ):
                out = _node_autonomy_execute(state)

        self.assertEqual(out["action_packets"][0]["status"], "completed")
        self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_source_ref_ids"], [21, 17])
        self.assertEqual(int(out["session_context"]["digital_body_hints"]["preferred_source_ref_id"]), 21)
        self.assertEqual(
            out["session_context"]["digital_body_hints"]["preferred_anchor_reason"],
            "primary_more_current",
        )
        self.assertEqual(out["digital_body_state"]["resource_state"]["artifact_source_ref_ids"], [21, 17])
        self.assertEqual(int(out["digital_body_state"]["resource_state"]["preferred_source_ref_id"]), 21)
        self.assertEqual(
            out["digital_body_state"]["resource_state"]["preferred_anchor_reason"],
            "primary_more_current",
        )
        artifact_context = out["action_packets"][0].get("artifact_context") if isinstance(out["action_packets"][0].get("artifact_context"), dict) else {}
        self.assertEqual(artifact_context.get("preferred_source_ref_id"), 21)
        self.assertEqual(artifact_context.get("preferred_anchor_reason"), "primary_more_current")

    def test_autonomy_execute_can_refresh_access_state_and_write_back_hints(self):
        with TemporaryDirectory() as td:
            runtime_dir = Path(td) / "runtime"
            runtime_dir.mkdir()
            state = {
                "current_event": {"kind": "user_utterance", "text": "先看看当前入口状态。"},
                "interaction_carryover": {},
                "session_context": {
                    "digital_body_hints": {
                        "browser_session": "present",
                        "account_state": "logged_in",
                        "cookie_state": "present",
                        "session_expires_in_s": 600,
                        "api_key_state": "missing",
                    }
                },
                "autonomy_intent": {"mode": "refresh_access_state", "origin": "motive_goal"},
                "action_packets": [
                    {
                        "proposal_id": "ap-access-2",
                        "origin": "motive_goal",
                        "intent": "access:refresh_state",
                        "status": "proposed",
                        "risk": "read",
                        "requires_approval": False,
                        "capability_steps": [
                            {
                                "kind": "access",
                                "name": "refresh_state",
                                "target": "session_refresh / api_key",
                                "status": "pending",
                                "requires_approval": False,
                                "note": "先把当前入口状态重新检查一遍。",
                            }
                        ],
                        "expected_effect": "先把当前入口状态重新检查一遍。",
                    }
                ],
                "action_trace": [],
                "behavior_queue": [],
                "toolset_unlocks": {},
                "last_external_tools": [],
                "evidence_pack": [],
                "world_model_state": {},
                "semantic_narrative_profile": {},
                "turn_appraisal": {},
                "evolution_state": {},
                "emotion_state": {},
                "bond_state": {},
                "counterpart_assessment": {},
                "behavior_action": {},
                "behavior_plan": {},
                "agenda_lifecycle_residue": {},
            }
            env = dict(os.environ)
            env.update(
                {
                    "AMADEUS_DATA_DIR": str(runtime_dir),
                    "AMADEUS_MODEL_PROVIDER": "openai_compatible",
                    "DASHSCOPE_API_KEY": "sk-test",
                    "AMADEUS_NETWORK_ACCESS": "restricted",
                }
            )
            with patch.dict(os.environ, env, clear=True):
                out = _node_autonomy_execute(state)

        self.assertEqual(out["action_packets"][0]["status"], "completed")
        self.assertEqual(out["autonomy_intent"]["mode"], "refresh_access_state")
        self.assertEqual(out["session_context"]["digital_body_hints"]["api_key_state"], "present")
        self.assertEqual(out["session_context"]["digital_body_hints"]["session_continuity"], "expiring")
        self.assertEqual(out["digital_body_state"]["access_state"]["api_key_state"], "present")
        self.assertEqual(out["digital_body_state"]["access_state"]["session_recovery_mode"], "refresh_session")
        self.assertIn("session_refresh", out["digital_body_state"]["access_state"]["requestable_access"])
        self.assertIsInstance(out["messages"][0], AIMessage)
        self.assertIsInstance(out["messages"][1], ToolMessage)

    def test_autonomy_execute_can_refresh_access_state_from_packet_binding_without_live_session_hints(self):
        with TemporaryDirectory() as td:
            runtime_dir = Path(td) / "runtime"
            runtime_dir.mkdir()
            state = {
                "current_event": {"kind": "user_utterance", "text": "先看看当前入口状态。"},
                "interaction_carryover": {},
                "session_context": {},
                "autonomy_intent": {"mode": "refresh_access_state", "origin": "motive_goal"},
                "action_packets": [
                    {
                        "proposal_id": "ap-access-bound-1",
                        "origin": "motive_goal",
                        "intent": "access:refresh_state",
                        "status": "approved",
                        "risk": "read",
                        "requires_approval": False,
                        "tool_name": "refresh_access_state",
                        "tool_args": {
                            "access_hints": {
                                "browser_session": "present",
                                "account_state": "logged_in",
                                "cookie_state": "present",
                                "session_expires_in_s": 600,
                                "api_key_state": "missing",
                            }
                        },
                        "capability_steps": [
                            {
                                "kind": "access",
                                "name": "refresh_state",
                                "target": "session_refresh / api_key",
                                "status": "approved",
                                "requires_approval": False,
                            }
                        ],
                    }
                ],
                "action_trace": [],
                "behavior_queue": [],
                "toolset_unlocks": {},
                "last_external_tools": [],
                "evidence_pack": [],
                "world_model_state": {},
                "semantic_narrative_profile": {},
                "turn_appraisal": {},
                "evolution_state": {},
                "emotion_state": {},
                "bond_state": {},
                "counterpart_assessment": {},
                "behavior_action": {},
                "behavior_plan": {},
                "agenda_lifecycle_residue": {},
            }
            env = {
                "AMADEUS_DATA_DIR": str(runtime_dir),
                "AMADEUS_MODEL_PROVIDER": "openai_compatible",
                "DASHSCOPE_API_KEY": "sk-test",
                "AMADEUS_NETWORK_ACCESS": "restricted",
            }
            with patch.dict(os.environ, env, clear=True):
                out = _node_autonomy_execute(state)

        self.assertEqual(out["action_packets"][0]["status"], "completed")
        self.assertEqual(out["action_packets"][0]["tool_name"], "refresh_access_state")
        self.assertEqual(out["action_packets"][0]["tool_args"]["access_hints"]["browser_session"], "present")
        self.assertEqual(out["autonomy_intent"]["mode"], "refresh_access_state")
        self.assertEqual(out["session_context"]["digital_body_hints"]["api_key_state"], "present")
        self.assertEqual(out["digital_body_state"]["access_state"]["network_access"], "restricted")

    def test_autonomy_execute_can_create_workspace_from_approved_access_path(self):
        proposal = {
            "target": "filesystem",
            "mode": "operator_create_workspace",
            "path_kind": "create_new",
            "summary": "先新建一个可写工作区。",
            "operator_action": "新建一个可写工作区。",
            "grants": ["filesystem", "workspace_write"],
            "requires_operator": True,
        }
        with TemporaryDirectory() as td:
            runtime_dir = Path(td) / "runtime"
            runtime_dir.mkdir()
            state = {
                "current_event": {"kind": "user_utterance", "text": "那就新建一个工作区继续。"},
                "interaction_carryover": {},
                "session_context": {
                    "digital_body_hints": {
                        "filesystem_state": "missing",
                        "missing_access": ["filesystem", "workspace_write"],
                        "requestable_access": ["filesystem", "workspace_write"],
                        "requested_help": False,
                        "primary_proposal_id": "ap-access-create-1",
                        "primary_status": "approved",
                        "primary_origin": "counterpart_request",
                        "primary_intent": "access:request_help",
                        "access_acquire_proposals": [proposal],
                        "selected_access_proposal": proposal,
                    }
                },
                "autonomy_intent": {"mode": "access_acquire_planned", "origin": "counterpart_request"},
                "action_packets": [
                    {
                        "proposal_id": "ap-access-create-1",
                        "origin": "counterpart_request",
                        "intent": "access:request_help",
                        "status": "approved",
                        "risk": "external_mutation",
                        "requires_approval": True,
                        "capability_steps": [
                            {
                                "kind": "access",
                                "name": "request_help",
                                "target": "filesystem",
                                "status": "approved",
                                "requires_approval": True,
                                "note": "先新建一个可写工作区。",
                            }
                        ],
                        "expected_effect": "先新建一个可写工作区。",
                        "selected_access_proposal": proposal,
                        "access_acquire_proposals": [proposal],
                    }
                ],
                "action_trace": [],
                "behavior_queue": [],
                "toolset_unlocks": {},
                "last_external_tools": [],
                "evidence_pack": [],
                "world_model_state": {},
                "semantic_narrative_profile": {},
                "turn_appraisal": {},
                "evolution_state": {},
                "emotion_state": {},
                "bond_state": {},
                "counterpart_assessment": {},
                "behavior_action": {},
                "behavior_plan": {},
                "agenda_lifecycle_residue": {},
            }
            env = {
                "AMADEUS_DATA_DIR": str(runtime_dir),
                "AMADEUS_MODEL_PROVIDER": "openai_compatible",
            }
            with patch.dict(os.environ, env, clear=True):
                out = _node_autonomy_execute(state)

        self.assertEqual(out["action_packets"][0]["status"], "completed")
        self.assertTrue(out["action_packets"][0]["writeback_ready"])
        self.assertEqual(out["digital_body_state"]["access_state"]["filesystem_state"], "writable")
        self.assertEqual(out["digital_body_state"]["resource_state"]["active_artifact_kind"], "workspace")
        self.assertNotIn("selected_access_proposal", out["session_context"]["digital_body_hints"])
        self.assertEqual(out["session_context"]["digital_body_hints"]["active_artifact_kind"], "workspace")
        self.assertEqual(out["autonomy_intent"]["mode"], "access_request_resolved")
        self.assertEqual(out["action_packets"][0]["tool_name"], "create_workspace_access")
        self.assertEqual(out["action_packets"][0]["tool_args"]["access_hints"]["selected_access_proposal"]["mode"], "operator_create_workspace")
        self.assertIsInstance(out["messages"][0], AIMessage)
        self.assertIsInstance(out["messages"][1], ToolMessage)

    def test_autonomy_execute_can_create_workspace_from_packet_binding_without_live_session_hints(self):
        proposal = {
            "target": "filesystem",
            "mode": "operator_create_workspace",
            "path_kind": "create_new",
            "summary": "先新建一个可写工作区。",
            "operator_action": "新建一个可写工作区。",
            "grants": ["filesystem", "workspace_write"],
            "requires_operator": True,
        }
        with TemporaryDirectory() as td:
            runtime_dir = Path(td) / "runtime"
            runtime_dir.mkdir()
            state = {
                "current_event": {"kind": "user_utterance", "text": "那就新建一个工作区继续。"},
                "interaction_carryover": {},
                "session_context": {},
                "autonomy_intent": {"mode": "access_acquire_planned", "origin": "counterpart_request"},
                "action_packets": [
                    {
                        "proposal_id": "ap-access-create-bound-1",
                        "origin": "counterpart_request",
                        "intent": "access:request_help",
                        "status": "approved",
                        "risk": "external_mutation",
                        "requires_approval": True,
                        "tool_name": "create_workspace_access",
                        "tool_args": {
                            "workspace_name": "lab",
                            "access_hints": {
                                "filesystem_state": "missing",
                                "missing_access": ["filesystem", "workspace_write"],
                                "requestable_access": ["filesystem", "workspace_write"],
                                "selected_access_proposal": proposal,
                                "access_acquire_proposals": [proposal],
                            },
                        },
                        "capability_steps": [
                            {
                                "kind": "access",
                                "name": "request_help",
                                "target": "filesystem",
                                "status": "approved",
                                "requires_approval": True,
                                "note": "先新建一个可写工作区。",
                            }
                        ],
                        "expected_effect": "先新建一个可写工作区。",
                        "selected_access_proposal": proposal,
                        "access_acquire_proposals": [proposal],
                    }
                ],
                "action_trace": [],
                "behavior_queue": [],
                "toolset_unlocks": {},
                "last_external_tools": [],
                "evidence_pack": [],
                "world_model_state": {},
                "semantic_narrative_profile": {},
                "turn_appraisal": {},
                "evolution_state": {},
                "emotion_state": {},
                "bond_state": {},
                "counterpart_assessment": {},
                "behavior_action": {},
                "behavior_plan": {},
                "agenda_lifecycle_residue": {},
            }
            env = {
                "AMADEUS_DATA_DIR": str(runtime_dir),
                "AMADEUS_MODEL_PROVIDER": "openai_compatible",
            }
            with patch.dict(os.environ, env, clear=True):
                out = _node_autonomy_execute(state)

        self.assertEqual(out["action_packets"][0]["status"], "completed")
        self.assertEqual(out["action_packets"][0]["tool_name"], "create_workspace_access")
        self.assertEqual(out["action_packets"][0]["tool_args"]["workspace_name"], "lab")
        self.assertEqual(out["digital_body_state"]["resource_state"]["active_artifact_label"], "lab")
        self.assertEqual(out["autonomy_intent"]["mode"], "access_request_resolved")

    def test_autonomy_execute_can_write_workspace_file_from_approved_packet(self):
        with TemporaryDirectory() as td:
            runtime_dir = Path(td) / "runtime"
            workspace = runtime_dir / "workspaces" / "lab"
            workspace.mkdir(parents=True)
            state = {
                "current_event": {"kind": "user_utterance", "text": "把待办记下来。"},
                "interaction_carryover": {},
                "session_context": {
                    "digital_body_hints": {
                        "filesystem_state": "writable",
                        "active_artifact_kind": "workspace",
                        "active_artifact_ref": str(workspace),
                        "active_artifact_label": "lab",
                    }
                },
                "autonomy_intent": {"mode": "queue_followthrough", "origin": "counterpart_request"},
                "action_packets": [
                    {
                        "proposal_id": "ap-file-write-1",
                        "origin": "counterpart_request",
                        "intent": "artifact:write_file",
                        "status": "approved",
                        "risk": "external_mutation",
                        "requires_approval": True,
                        "tool_name": "write_workspace_file",
                        "tool_args": {
                            "relative_path": "notes/todo.md",
                            "content": "buy bananas",
                        },
                        "capability_steps": [
                            {
                                "kind": "tool_call",
                                "name": "write_workspace_file",
                                "target": "notes/todo.md",
                                "status": "approved",
                                "requires_approval": True,
                            }
                        ],
                        "expected_effect": "把待办真正写进工作区文件里。",
                    }
                ],
                "action_trace": [],
                "behavior_queue": [],
                "toolset_unlocks": {},
                "last_external_tools": [],
                "evidence_pack": [],
                "world_model_state": {},
                "semantic_narrative_profile": {},
                "turn_appraisal": {},
                "evolution_state": {},
                "emotion_state": {},
                "bond_state": {},
                "counterpart_assessment": {},
                "behavior_action": {},
                "behavior_plan": {},
                "agenda_lifecycle_residue": {},
            }
            env = {
                "AMADEUS_DATA_DIR": str(runtime_dir),
                "AMADEUS_MODEL_PROVIDER": "openai_compatible",
            }
            with patch.dict(os.environ, env, clear=True):
                out = _node_autonomy_execute(state)

            target = workspace / "notes" / "todo.md"
            self.assertTrue(target.exists())
            self.assertEqual(target.read_text(encoding="utf-8"), "buy bananas")
            self.assertEqual(out["action_packets"][0]["status"], "completed")
            self.assertEqual(out["action_packets"][0]["tool_name"], "write_workspace_file")
            self.assertEqual(out["action_packets"][0]["artifact_context"]["artifact_kind"], "file")
            self.assertEqual(out["action_packets"][0]["artifact_context"]["workspace_root"], str(workspace))
            self.assertEqual(out["session_context"]["digital_body_hints"]["workspace_root"], str(workspace))
            self.assertEqual(out["session_context"]["digital_body_hints"]["active_artifact_kind"], "file")
            self.assertEqual(out["digital_body_state"]["resource_state"]["active_artifact_label"], "todo.md")
            self.assertEqual(out["digital_body_state"]["resource_state"]["workspace_root"], str(workspace))
            self.assertIsInstance(out["messages"][0], AIMessage)
            self.assertIsInstance(out["messages"][1], ToolMessage)

    def test_autonomy_execute_can_replace_workspace_text_from_approved_packet(self):
        with TemporaryDirectory() as td:
            runtime_dir = Path(td) / "runtime"
            workspace = runtime_dir / "workspaces" / "lab"
            target = workspace / "notes" / "todo.md"
            target.parent.mkdir(parents=True)
            target.write_text("buy bananas", encoding="utf-8")
            state = {
                "current_event": {"kind": "user_utterance", "text": "把 bananas 改成 apples。"},
                "interaction_carryover": {},
                "session_context": {
                    "digital_body_hints": {
                        "filesystem_state": "writable",
                        "active_artifact_kind": "file",
                        "active_artifact_ref": str(target),
                        "active_artifact_label": "todo.md",
                    }
                },
                "autonomy_intent": {"mode": "queue_followthrough", "origin": "counterpart_request"},
                "action_packets": [
                    {
                        "proposal_id": "ap-file-replace-1",
                        "origin": "counterpart_request",
                        "intent": "artifact:replace_text",
                        "status": "approved",
                        "risk": "external_mutation",
                        "requires_approval": True,
                        "tool_name": "replace_workspace_text",
                        "tool_args": {
                            "relative_path": "notes/todo.md",
                            "old_text": "bananas",
                            "new_text": "apples",
                        },
                        "capability_steps": [
                            {
                                "kind": "tool_call",
                                "name": "replace_workspace_text",
                                "target": "notes/todo.md",
                                "status": "approved",
                                "requires_approval": True,
                            }
                        ],
                        "expected_effect": "把文件里的旧文本精确替换掉。",
                    }
                ],
                "action_trace": [],
                "behavior_queue": [],
                "toolset_unlocks": {},
                "last_external_tools": [],
                "evidence_pack": [],
                "world_model_state": {},
                "semantic_narrative_profile": {},
                "turn_appraisal": {},
                "evolution_state": {},
                "emotion_state": {},
                "bond_state": {},
                "counterpart_assessment": {},
                "behavior_action": {},
                "behavior_plan": {},
                "agenda_lifecycle_residue": {},
            }
            env = {
                "AMADEUS_DATA_DIR": str(runtime_dir),
                "AMADEUS_MODEL_PROVIDER": "openai_compatible",
            }
            with patch.dict(os.environ, env, clear=True):
                out = _node_autonomy_execute(state)

            self.assertEqual(target.read_text(encoding="utf-8"), "buy apples")
            self.assertEqual(out["action_packets"][0]["status"], "completed")
            self.assertEqual(out["action_packets"][0]["tool_name"], "replace_workspace_text")
            self.assertEqual(out["action_packets"][0]["artifact_context"]["source_tool_name"], "replace_workspace_text")
            self.assertEqual(out["action_packets"][0]["artifact_context"]["workspace_root"], str(workspace))
            self.assertEqual(out["session_context"]["digital_body_hints"]["workspace_root"], str(workspace))
            self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_source_tool_name"], "replace_workspace_text")
            self.assertEqual(out["digital_body_state"]["resource_state"]["active_artifact_label"], "todo.md")
            self.assertEqual(out["digital_body_state"]["resource_state"]["workspace_root"], str(workspace))

    def test_autonomy_execute_can_replace_workspace_lines_from_approved_packet(self):
        with TemporaryDirectory() as td:
            runtime_dir = Path(td) / "runtime"
            workspace = runtime_dir / "workspaces" / "lab"
            target = workspace / "notes" / "todo.md"
            target.parent.mkdir(parents=True)
            target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
            state = {
                "current_event": {"kind": "user_utterance", "text": "把第二行改成 beta v2。"},
                "interaction_carryover": {},
                "session_context": {
                    "digital_body_hints": {
                        "filesystem_state": "writable",
                        "active_artifact_kind": "file",
                        "active_artifact_ref": str(target),
                        "active_artifact_label": "todo.md",
                    }
                },
                "autonomy_intent": {"mode": "queue_followthrough", "origin": "counterpart_request"},
                "action_packets": [
                    {
                        "proposal_id": "ap-file-lines-1",
                        "origin": "counterpart_request",
                        "intent": "artifact:replace_lines",
                        "status": "approved",
                        "risk": "external_mutation",
                        "requires_approval": True,
                        "tool_name": "replace_workspace_lines",
                        "tool_args": {
                            "relative_path": "notes/todo.md",
                            "start_line": 2,
                            "end_line": 2,
                            "new_text": "beta v2",
                        },
                        "capability_steps": [
                            {
                                "kind": "tool_call",
                                "name": "replace_workspace_lines",
                                "target": "notes/todo.md",
                                "status": "approved",
                                "requires_approval": True,
                            }
                        ],
                        "expected_effect": "把文件里指定行替换成新的版本。",
                    }
                ],
                "action_trace": [],
                "behavior_queue": [],
                "toolset_unlocks": {},
                "last_external_tools": [],
                "evidence_pack": [],
                "world_model_state": {},
                "semantic_narrative_profile": {},
                "turn_appraisal": {},
                "evolution_state": {},
                "emotion_state": {},
                "bond_state": {},
                "counterpart_assessment": {},
                "behavior_action": {},
                "behavior_plan": {},
                "agenda_lifecycle_residue": {},
            }
            env = {
                "AMADEUS_DATA_DIR": str(runtime_dir),
                "AMADEUS_MODEL_PROVIDER": "openai_compatible",
            }
            with patch.dict(os.environ, env, clear=True):
                out = _node_autonomy_execute(state)

            self.assertEqual(target.read_text(encoding="utf-8"), "alpha\nbeta v2\ngamma\n")
            self.assertEqual(out["action_packets"][0]["status"], "completed")
            self.assertEqual(out["action_packets"][0]["tool_name"], "replace_workspace_lines")
            self.assertEqual(out["action_packets"][0]["artifact_context"]["source_tool_name"], "replace_workspace_lines")
            self.assertEqual(out["action_packets"][0]["artifact_context"]["workspace_root"], str(workspace))
            self.assertEqual(out["session_context"]["digital_body_hints"]["workspace_root"], str(workspace))
            self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_source_tool_name"], "replace_workspace_lines")
            self.assertEqual(out["digital_body_state"]["resource_state"]["active_artifact_label"], "todo.md")
            self.assertEqual(out["digital_body_state"]["resource_state"]["workspace_root"], str(workspace))

    def test_autonomy_execute_can_inspect_workspace_path_from_packet_binding(self):
        with TemporaryDirectory() as td:
            runtime_dir = Path(td) / "runtime"
            workspace = runtime_dir / "workspaces" / "lab"
            target = workspace / "notes" / "todo.md"
            target.parent.mkdir(parents=True)
            target.write_text("hello from inspect\n" * 8, encoding="utf-8")
            state = {
                "current_event": {"kind": "user_utterance", "text": "先看看 todo.md 里面现在是什么。"},
                "interaction_carryover": {},
                "session_context": {
                    "digital_body_hints": {
                        "filesystem_state": "writable",
                        "active_artifact_kind": "workspace",
                        "active_artifact_ref": str(workspace),
                        "active_artifact_label": "lab",
                    }
                },
                "autonomy_intent": {"mode": "tool_completed", "origin": "counterpart_request"},
                "action_packets": [
                    {
                        "proposal_id": "ap-inspect-file-1",
                        "origin": "counterpart_request",
                        "intent": "artifact:inspect_path",
                        "status": "approved",
                        "risk": "read",
                        "requires_approval": False,
                        "tool_name": "inspect_workspace_path",
                        "tool_args": {
                            "relative_path": "notes/todo.md",
                            "access_hints": {
                                "filesystem_state": "writable",
                                "active_artifact_kind": "workspace",
                                "active_artifact_ref": str(workspace),
                                "active_artifact_label": "lab",
                            },
                        },
                        "capability_steps": [
                            {
                                "kind": "tool_call",
                                "name": "inspect_workspace_path",
                                "target": "notes/todo.md",
                                "status": "approved",
                                "requires_approval": False,
                            }
                        ],
                        "expected_effect": "把当前文件重新读回来，确认工作面状态。",
                    }
                ],
                "action_trace": [],
                "behavior_queue": [],
                "toolset_unlocks": {},
                "last_external_tools": [],
                "evidence_pack": [],
                "world_model_state": {},
                "semantic_narrative_profile": {},
                "turn_appraisal": {},
                "evolution_state": {},
                "emotion_state": {},
                "bond_state": {},
                "counterpart_assessment": {},
                "behavior_action": {},
                "behavior_plan": {},
                "agenda_lifecycle_residue": {},
            }
            env = {
                "AMADEUS_DATA_DIR": str(runtime_dir),
                "AMADEUS_MODEL_PROVIDER": "openai_compatible",
            }
            with patch.dict(os.environ, env, clear=True):
                out = _node_autonomy_execute(state)

            self.assertEqual(out["action_packets"][0]["status"], "completed")
            self.assertEqual(out["action_packets"][0]["tool_name"], "inspect_workspace_path")
            self.assertEqual(out["action_packets"][0]["artifact_context"]["artifact_kind"], "file")
            self.assertEqual(out["action_packets"][0]["artifact_context"]["source_tool_name"], "inspect_workspace_path")
            self.assertEqual(out["action_packets"][0]["artifact_context"]["workspace_root"], str(workspace))
            self.assertIn("hello from inspect", out["action_packets"][0]["artifact_context"]["preview"])
            self.assertEqual(out["autonomy_intent"]["mode"], "inspect_workspace_path")
            self.assertEqual(out["session_context"]["digital_body_hints"]["active_artifact_kind"], "file")
            self.assertEqual(out["session_context"]["digital_body_hints"]["workspace_root"], str(workspace))
            self.assertEqual(out["digital_body_state"]["resource_state"]["active_artifact_label"], "todo.md")
            self.assertEqual(out["digital_body_state"]["resource_state"]["workspace_root"], str(workspace))

    def test_tool_execute_create_workspace_updates_session_context(self):
        with TemporaryDirectory() as td:
            runtime_dir = Path(td) / "runtime"
            runtime_dir.mkdir()
            state = {
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[{"id": "tc-1", "name": "create_workspace_access", "args": {"workspace_name": "lab"}}],
                    )
                ],
                "approval_actions": [
                    {
                        "id": "tc-1",
                        "name": "create_workspace_access",
                        "args": {"workspace_name": "lab"},
                        "proposal_id": "ap-workspace-1",
                        "action": "approve",
                    }
                ],
                "session_context": {"digital_body_hints": {"filesystem_state": "missing", "missing_access": ["filesystem"]}},
                "toolset_unlocks": {},
                "evidence_pack": [],
                "last_external_tools": [],
                "memory_guard_checked": 0,
                "memory_guard_blocked": 0,
                "current_event": {"kind": "user_utterance"},
                "turn_appraisal": {},
                "world_model_state": {},
                "semantic_narrative_profile": {},
                "evolution_state": {},
                "emotion_state": {},
                "bond_state": {},
                "counterpart_assessment": {},
                "behavior_action": {},
                "behavior_plan": {},
                "interaction_carryover": {},
                "agenda_lifecycle_residue": {},
                "autonomy_intent": {"mode": "language_response", "origin": "counterpart_request"},
                "action_packets": [],
                "action_trace": [],
            }
            env = {
                "AMADEUS_DATA_DIR": str(runtime_dir),
                "AMADEUS_MODEL_PROVIDER": "openai_compatible",
            }
            with patch("amadeus_thread0.graph_parts.tool_nodes._get_store", return_value=object()):
                with patch.dict(os.environ, env, clear=True):
                    out = _node_tool_execute(state)

        self.assertEqual(out["action_packets"][0]["status"], "completed")
        self.assertEqual(out["action_packets"][0]["artifact_context"]["artifact_kind"], "workspace")
        self.assertEqual(out["action_packets"][0]["artifact_context"]["workspace_root"], str(runtime_dir / "workspaces" / "lab"))
        self.assertEqual(out["session_context"]["digital_body_hints"]["filesystem_state"], "writable")
        self.assertEqual(out["session_context"]["digital_body_hints"]["workspace_root"], str(runtime_dir / "workspaces" / "lab"))
        self.assertEqual(out["digital_body_state"]["access_state"]["filesystem_state"], "writable")
        self.assertEqual(out["digital_body_state"]["resource_state"]["active_artifact_kind"], "workspace")
        self.assertEqual(out["digital_body_state"]["resource_state"]["workspace_root"], str(runtime_dir / "workspaces" / "lab"))

    def test_tool_execute_inspect_workspace_path_updates_session_context(self):
        with TemporaryDirectory() as td:
            runtime_dir = Path(td) / "runtime"
            workspace = runtime_dir / "workspaces" / "lab"
            target = workspace / "notes" / "todo.md"
            target.parent.mkdir(parents=True)
            target.write_text("inspect me", encoding="utf-8")
            state = {
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tc-1",
                                "name": "inspect_workspace_path",
                                "args": {
                                    "relative_path": "notes/todo.md",
                                    "access_hints": {
                                        "filesystem_state": "writable",
                                        "active_artifact_kind": "workspace",
                                        "active_artifact_ref": str(workspace),
                                        "active_artifact_label": "lab",
                                    },
                                },
                            }
                        ],
                    )
                ],
                "approval_actions": [
                    {
                        "id": "tc-1",
                        "name": "inspect_workspace_path",
                        "args": {
                            "relative_path": "notes/todo.md",
                            "access_hints": {
                                "filesystem_state": "writable",
                                "active_artifact_kind": "workspace",
                                "active_artifact_ref": str(workspace),
                                "active_artifact_label": "lab",
                            },
                        },
                        "proposal_id": "ap-inspect-file-1",
                        "action": "approve",
                    }
                ],
                "session_context": {
                    "digital_body_hints": {
                        "filesystem_state": "writable",
                        "active_artifact_kind": "workspace",
                        "active_artifact_ref": str(workspace),
                        "active_artifact_label": "lab",
                    }
                },
                "toolset_unlocks": {},
                "evidence_pack": [],
                "last_external_tools": [],
                "memory_guard_checked": 0,
                "memory_guard_blocked": 0,
                "current_event": {"kind": "user_utterance"},
                "turn_appraisal": {},
                "world_model_state": {},
                "semantic_narrative_profile": {},
                "evolution_state": {},
                "emotion_state": {},
                "bond_state": {},
                "counterpart_assessment": {},
                "behavior_action": {},
                "behavior_plan": {},
                "interaction_carryover": {},
                "agenda_lifecycle_residue": {},
                "autonomy_intent": {"mode": "language_response", "origin": "counterpart_request"},
                "action_packets": [],
                "action_trace": [],
            }
            env = {
                "AMADEUS_DATA_DIR": str(runtime_dir),
                "AMADEUS_MODEL_PROVIDER": "openai_compatible",
            }
            with patch("amadeus_thread0.graph_parts.tool_nodes._get_store", return_value=object()):
                with patch.dict(os.environ, env, clear=True):
                    out = _node_tool_execute(state)

            self.assertEqual(out["action_packets"][0]["status"], "completed")
            self.assertEqual(out["action_packets"][0]["tool_name"], "inspect_workspace_path")
            self.assertEqual(out["action_packets"][0]["artifact_context"]["artifact_kind"], "file")
            self.assertEqual(out["action_packets"][0]["artifact_context"]["source_tool_name"], "inspect_workspace_path")
            self.assertEqual(out["autonomy_intent"]["mode"], "inspect_workspace_path")
            self.assertEqual(out["session_context"]["digital_body_hints"]["active_artifact_kind"], "file")
            self.assertEqual(out["session_context"]["digital_body_hints"]["active_artifact_ref"], str(target))
            self.assertEqual(out["session_context"]["digital_body_hints"]["workspace_root"], str(workspace))
            self.assertEqual(out["digital_body_state"]["resource_state"]["active_artifact_label"], "todo.md")
            self.assertEqual(out["digital_body_state"]["resource_state"]["workspace_root"], str(workspace))

    def test_tool_execute_inspect_source_ref_updates_session_context(self):
        state = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "tc-1",
                            "name": "inspect_source_ref",
                            "args": {
                                "source_ref_id": 17,
                                "access_hints": {
                                    "world_surfaces": ["source_ref"],
                                },
                            },
                        }
                    ],
                )
            ],
            "approval_actions": [
                {
                    "id": "tc-1",
                    "name": "inspect_source_ref",
                    "args": {
                        "source_ref_id": 17,
                        "access_hints": {
                            "world_surfaces": ["source_ref"],
                        },
                    },
                    "proposal_id": "ap-inspect-source-1",
                    "action": "approve",
                }
            ],
            "session_context": {
                "digital_body_hints": {
                    "world_surfaces": ["source_ref"],
                }
            },
            "toolset_unlocks": {},
            "evidence_pack": [],
            "last_external_tools": [],
            "memory_guard_checked": 0,
            "memory_guard_blocked": 0,
            "current_event": {"kind": "user_utterance"},
            "turn_appraisal": {},
            "world_model_state": {},
            "semantic_narrative_profile": {},
            "evolution_state": {},
            "emotion_state": {},
            "bond_state": {},
            "counterpart_assessment": {},
            "behavior_action": {},
            "behavior_plan": {},
            "interaction_carryover": {},
            "agenda_lifecycle_residue": {},
            "autonomy_intent": {"mode": "language_response", "origin": "counterpart_request"},
            "action_packets": [],
            "action_trace": [],
        }
        store = self._SourceRefStore(
            [
                {
                    "id": 17,
                    "url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "title": "Persistence",
                    "query": "langgraph persistence checkpointer thread",
                    "tool_name": "search_web",
                    "snippet": "checkpointers keep thread state stable",
                    "retrieved_at": 1712345678,
                }
            ]
        )
        with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
            with patch("amadeus_thread0.graph_parts.tool_nodes._get_store", return_value=object()):
                out = _node_tool_execute(state)

        self.assertEqual(out["action_packets"][0]["status"], "completed")
        self.assertEqual(out["action_packets"][0]["tool_name"], "inspect_source_ref")
        self.assertEqual(out["action_packets"][0]["artifact_context"]["carrier"], "source_ref")
        self.assertEqual(out["action_packets"][0]["artifact_context"]["artifact_kind"], "search_result")
        self.assertEqual(out["action_packets"][0]["artifact_context"]["source_ref_ids"], [17])
        self.assertEqual(out["autonomy_intent"]["mode"], "inspect_source_ref")
        self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_source_ref_ids"], [17])
        self.assertEqual(out["session_context"]["digital_body_hints"]["active_artifact_kind"], "search_result")
        self.assertEqual(out["digital_body_state"]["resource_state"]["active_artifact_label"], "Persistence")

    def test_tool_execute_inspect_source_ref_updates_session_context_from_content_only_source_ref(self):
        state = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "tc-1",
                            "name": "inspect_source_ref",
                            "args": {
                                "source_ref_id": 17,
                                "access_hints": {
                                    "world_surfaces": ["source_ref"],
                                },
                            },
                        }
                    ],
                )
            ],
            "approval_actions": [
                {
                    "id": "tc-1",
                    "name": "inspect_source_ref",
                    "args": {
                        "source_ref_id": 17,
                        "access_hints": {
                            "world_surfaces": ["source_ref"],
                        },
                    },
                    "proposal_id": "ap-inspect-source-1b",
                    "action": "approve",
                }
            ],
            "session_context": {
                "digital_body_hints": {
                    "world_surfaces": ["source_ref"],
                }
            },
            "toolset_unlocks": {},
            "evidence_pack": [],
            "last_external_tools": [],
            "memory_guard_checked": 0,
            "memory_guard_blocked": 0,
            "current_event": {"kind": "user_utterance"},
            "turn_appraisal": {},
            "world_model_state": {},
            "semantic_narrative_profile": {},
            "evolution_state": {},
            "emotion_state": {},
            "bond_state": {},
            "counterpart_assessment": {},
            "behavior_action": {},
            "behavior_plan": {},
            "interaction_carryover": {},
            "agenda_lifecycle_residue": {},
            "autonomy_intent": {"mode": "language_response", "origin": "counterpart_request"},
            "action_packets": [],
            "action_trace": [],
        }
        store = self._SourceRefStore(
            [
                {
                    "id": "17",
                    "content": {
                        "url": " https://docs.langchain.com/oss/python/langgraph/persistence ",
                        "title": " Persistence ",
                        "query": " langgraph persistence checkpointer thread ",
                        "tool_name": " search_web ",
                        "snippet": " checkpointers keep thread state stable ",
                    },
                    "retrieved_at": "1712345678",
                }
            ]
        )
        with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
            with patch("amadeus_thread0.graph_parts.tool_nodes._get_store", return_value=object()):
                out = _node_tool_execute(state)

        self.assertEqual(out["action_packets"][0]["status"], "completed")
        self.assertEqual(out["action_packets"][0]["artifact_context"]["source_ref_ids"], [17])
        self.assertEqual(out["action_packets"][0]["artifact_context"]["source_title"], "Persistence")
        self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_source_ref_ids"], [17])
        self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_source_title"], "Persistence")
        self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_source_tool_name"], "search_web")
        self.assertEqual(out["digital_body_state"]["resource_state"]["active_artifact_label"], "Persistence")

    def test_autonomy_execute_can_inspect_source_ref_from_packet_binding(self):
        state = {
            "messages": [],
            "session_context": {"digital_body_hints": {"world_surfaces": ["source_ref"]}},
            "current_event": {"kind": "user_utterance"},
            "autonomy_intent": {"mode": "inspect_source_ref", "origin": "counterpart_request"},
            "action_packets": [
                {
                    "proposal_id": "ap-inspect-source-1",
                    "origin": "counterpart_request",
                    "intent": "artifact:inspect_source_ref",
                    "status": "approved",
                    "risk": "read",
                    "requires_approval": False,
                    "tool_name": "inspect_source_ref",
                    "tool_args": {
                        "source_ref_id": 17,
                        "access_hints": {
                            "world_surfaces": ["source_ref"],
                        },
                    },
                    "capability_steps": [
                        {
                            "kind": "tool_call",
                            "name": "inspect_source_ref",
                            "target": "source_ref:17",
                            "status": "approved",
                            "requires_approval": False,
                        }
                    ],
                    "expected_effect": "把这条外部材料重新看一遍，确认当前判断依据。",
                }
            ],
            "action_trace": [],
            "behavior_queue": [],
            "toolset_unlocks": {},
            "last_external_tools": [],
            "evidence_pack": [],
            "world_model_state": {},
            "semantic_narrative_profile": {},
            "turn_appraisal": {},
            "evolution_state": {},
            "emotion_state": {},
            "bond_state": {},
            "counterpart_assessment": {},
            "behavior_action": {},
            "behavior_plan": {},
            "agenda_lifecycle_residue": {},
        }
        store = self._SourceRefStore(
            [
                {
                    "id": 17,
                    "url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "title": "Persistence",
                    "query": "langgraph persistence checkpointer thread",
                    "tool_name": "search_web",
                    "snippet": "checkpointers keep thread state stable",
                    "retrieved_at": 1712345678,
                }
            ]
        )
        with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
            with patch("amadeus_thread0.graph_parts.tool_nodes._get_store", return_value=object()):
                out = _node_autonomy_execute(state)

        self.assertEqual(out["action_packets"][0]["status"], "completed")
        self.assertEqual(out["action_packets"][0]["tool_name"], "inspect_source_ref")
        self.assertEqual(out["action_packets"][0]["artifact_context"]["carrier"], "source_ref")
        self.assertEqual(out["action_packets"][0]["artifact_context"]["artifact_kind"], "search_result")
        self.assertEqual(out["action_packets"][0]["artifact_context"]["source_ref_ids"], [17])
        self.assertEqual(out["autonomy_intent"]["mode"], "inspect_source_ref")
        self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_source_ref_ids"], [17])
        self.assertEqual(out["digital_body_state"]["resource_state"]["active_artifact_label"], "Persistence")

    def test_tool_execute_compare_source_refs_updates_session_context(self):
        state = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "tc-1",
                            "name": "compare_source_refs",
                            "args": {
                                "source_ref_id": 21,
                                "compare_source_ref_id": 17,
                                "access_hints": {
                                    "world_surfaces": ["source_ref"],
                                    "artifact_source_ref_ids": [21, 17],
                                },
                            },
                        }
                    ],
                )
            ],
            "approval_actions": [
                {
                    "id": "tc-1",
                    "name": "compare_source_refs",
                    "args": {
                        "source_ref_id": 21,
                        "compare_source_ref_id": 17,
                        "access_hints": {
                            "world_surfaces": ["source_ref"],
                            "artifact_source_ref_ids": [21, 17],
                        },
                    },
                    "proposal_id": "ap-compare-source-1",
                    "action": "approve",
                }
            ],
            "session_context": {
                "digital_body_hints": {
                    "world_surfaces": ["source_ref"],
                    "artifact_source_ref_ids": [21, 17],
                }
            },
            "toolset_unlocks": {},
            "evidence_pack": [],
            "last_external_tools": [],
            "memory_guard_checked": 0,
            "memory_guard_blocked": 0,
            "current_event": {"kind": "user_utterance"},
            "turn_appraisal": {},
            "world_model_state": {},
            "semantic_narrative_profile": {},
            "evolution_state": {},
            "emotion_state": {},
            "bond_state": {},
            "counterpart_assessment": {},
            "behavior_action": {},
            "behavior_plan": {},
            "interaction_carryover": {},
            "agenda_lifecycle_residue": {},
            "autonomy_intent": {"mode": "language_response", "origin": "counterpart_request"},
            "action_packets": [],
            "action_trace": [],
        }
        store = self._SourceRefStore(
            [
                {
                    "id": 21,
                    "url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "title": "Persistence v2",
                    "query": "langgraph persistence checkpointer thread recovery",
                    "tool_name": "search_web",
                    "snippet": "Recovery keeps the same persistence thread coherent.",
                    "retrieved_at": 1712345688,
                },
                {
                    "id": 17,
                    "url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "title": "Persistence",
                    "query": "langgraph persistence checkpointer thread",
                    "tool_name": "search_web",
                    "snippet": "checkpointers keep thread state stable",
                    "retrieved_at": 1712345678,
                },
            ]
        )
        with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
            with patch("amadeus_thread0.graph_parts.tool_nodes._get_store", return_value=object()):
                out = _node_tool_execute(state)

        self.assertEqual(out["action_packets"][0]["status"], "completed")
        self.assertEqual(out["action_packets"][0]["tool_name"], "compare_source_refs")
        self.assertEqual(out["action_packets"][0]["artifact_context"]["carrier"], "source_ref")
        self.assertEqual(out["action_packets"][0]["artifact_context"]["source_ref_ids"], [21, 17])
        self.assertEqual(out["action_packets"][0]["artifact_context"]["preferred_source_ref_id"], 21)
        self.assertEqual(out["autonomy_intent"]["mode"], "compare_source_refs")
        self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_source_ref_ids"], [21, 17])
        self.assertEqual(int(out["session_context"]["digital_body_hints"]["preferred_source_ref_id"]), 21)
        self.assertEqual(out["digital_body_state"]["resource_state"]["active_artifact_label"], "Persistence v2")

    def test_tool_execute_compare_source_refs_can_select_from_candidate_set(self):
        state = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "tc-1",
                            "name": "compare_source_refs",
                            "args": {
                                "source_ref_id": 31,
                                "source_ref_ids": [31, 33, 32],
                                "access_hints": {
                                    "world_surfaces": ["source_ref"],
                                    "artifact_source_ref_ids": [31, 33, 32],
                                },
                            },
                        }
                    ],
                )
            ],
            "approval_actions": [
                {
                    "id": "tc-1",
                    "name": "compare_source_refs",
                    "args": {
                        "source_ref_id": 31,
                        "source_ref_ids": [31, 33, 32],
                        "access_hints": {
                            "world_surfaces": ["source_ref"],
                            "artifact_source_ref_ids": [31, 33, 32],
                        },
                    },
                    "proposal_id": "ap-compare-source-candidate-set-1",
                    "action": "approve",
                }
            ],
            "session_context": {
                "digital_body_hints": {
                    "world_surfaces": ["source_ref"],
                    "artifact_source_ref_ids": [31, 33, 32],
                }
            },
            "toolset_unlocks": {},
            "evidence_pack": [],
            "last_external_tools": [],
            "memory_guard_checked": 0,
            "memory_guard_blocked": 0,
            "current_event": {"kind": "user_utterance"},
            "turn_appraisal": {},
            "world_model_state": {},
            "semantic_narrative_profile": {},
            "evolution_state": {},
            "emotion_state": {},
            "bond_state": {},
            "counterpart_assessment": {},
            "behavior_action": {},
            "behavior_plan": {},
            "interaction_carryover": {},
            "agenda_lifecycle_residue": {},
            "autonomy_intent": {"mode": "language_response", "origin": "counterpart_request"},
            "action_packets": [],
            "action_trace": [],
        }
        store = self._SourceRefStore(
            [
                {
                    "id": 31,
                    "url": "https://docs.example.com/spec",
                    "title": "Spec Draft",
                    "query": "amadeus source anchor draft",
                    "tool_name": "search_web",
                    "snippet": "Older draft with a short note.",
                    "retrieved_at": 1712000000,
                },
                {
                    "id": 32,
                    "url": "https://docs.example.com/spec",
                    "title": "Spec Final",
                    "query": "amadeus source anchor final",
                    "tool_name": "search_web",
                    "snippet": "Final spec with the stable anchor details and the longer resolved summary.",
                    "retrieved_at": 1712999999,
                },
                {
                    "id": 33,
                    "url": "https://docs.example.com/side-note",
                    "title": "Side Note",
                    "query": "amadeus unrelated note",
                    "tool_name": "search_web",
                    "snippet": "A weaker side note that should not outrank the final spec.",
                    "retrieved_at": 1712500000,
                },
            ]
        )
        with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
            with patch("amadeus_thread0.graph_parts.tool_nodes._get_store", return_value=object()):
                out = _node_tool_execute(state)

        self.assertEqual(out["action_packets"][0]["status"], "completed")
        self.assertEqual(out["action_packets"][0]["tool_name"], "compare_source_refs")
        self.assertEqual(out["action_packets"][0]["artifact_context"]["source_ref_ids"], [32, 31, 33])
        self.assertEqual(out["action_packets"][0]["artifact_context"]["preferred_source_ref_id"], 32)
        self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_source_ref_ids"], [32, 31, 33])
        self.assertEqual(int(out["session_context"]["digital_body_hints"]["preferred_source_ref_id"]), 32)
        self.assertEqual(out["digital_body_state"]["resource_state"]["active_artifact_label"], "Spec Final")

    def test_autonomy_execute_can_compare_source_refs_from_packet_binding(self):
        state = {
            "messages": [],
            "session_context": {"digital_body_hints": {"world_surfaces": ["source_ref"], "artifact_source_ref_ids": [21, 17]}},
            "current_event": {"kind": "user_utterance"},
            "autonomy_intent": {"mode": "compare_source_refs", "origin": "counterpart_request"},
            "action_packets": [
                {
                    "proposal_id": "ap-compare-source-1",
                    "origin": "counterpart_request",
                    "intent": "artifact:compare_source_refs",
                    "status": "approved",
                    "risk": "read",
                    "requires_approval": False,
                    "tool_name": "compare_source_refs",
                    "tool_args": {
                        "source_ref_id": 21,
                        "compare_source_ref_id": 17,
                        "access_hints": {
                            "world_surfaces": ["source_ref"],
                            "artifact_source_ref_ids": [21, 17],
                        },
                    },
                    "capability_steps": [
                        {
                            "kind": "tool_call",
                            "name": "compare_source_refs",
                            "target": "source_ref:21<->source_ref:17",
                            "status": "approved",
                            "requires_approval": False,
                        }
                    ],
                    "expected_effect": "把当前这条材料和前一条相关材料对一遍，确认现在该沿哪条线索继续判断。",
                }
            ],
            "action_trace": [],
            "behavior_queue": [],
            "toolset_unlocks": {},
            "last_external_tools": [],
            "evidence_pack": [],
            "world_model_state": {},
            "semantic_narrative_profile": {},
            "turn_appraisal": {},
            "evolution_state": {},
            "emotion_state": {},
            "bond_state": {},
            "counterpart_assessment": {},
            "behavior_action": {},
            "behavior_plan": {},
            "agenda_lifecycle_residue": {},
        }
        store = self._SourceRefStore(
            [
                {
                    "id": 21,
                    "url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "title": "Persistence v2",
                    "query": "langgraph persistence checkpointer thread recovery",
                    "tool_name": "search_web",
                    "snippet": "Recovery keeps the same persistence thread coherent.",
                    "retrieved_at": 1712345688,
                },
                {
                    "id": 17,
                    "url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "title": "Persistence",
                    "query": "langgraph persistence checkpointer thread",
                    "tool_name": "search_web",
                    "snippet": "checkpointers keep thread state stable",
                    "retrieved_at": 1712345678,
                },
            ]
        )
        with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
            with patch("amadeus_thread0.graph_parts.tool_nodes._get_store", return_value=object()):
                out = _node_autonomy_execute(state)

        self.assertEqual(out["action_packets"][0]["status"], "completed")
        self.assertEqual(out["action_packets"][0]["tool_name"], "compare_source_refs")
        self.assertEqual(out["action_packets"][0]["artifact_context"]["carrier"], "source_ref")
        self.assertEqual(out["action_packets"][0]["artifact_context"]["source_ref_ids"], [21, 17])
        self.assertEqual(out["action_packets"][0]["artifact_context"]["preferred_source_ref_id"], 21)
        self.assertEqual(out["autonomy_intent"]["mode"], "compare_source_refs")
        self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_source_ref_ids"], [21, 17])
        self.assertEqual(int(out["session_context"]["digital_body_hints"]["preferred_source_ref_id"]), 21)
        self.assertEqual(out["digital_body_state"]["resource_state"]["active_artifact_label"], "Persistence v2")

    def test_autonomy_execute_can_compare_source_refs_from_candidate_set_packet_binding(self):
        state = {
            "messages": [],
            "session_context": {"digital_body_hints": {"world_surfaces": ["source_ref"], "artifact_source_ref_ids": [31, 33, 32]}},
            "current_event": {"kind": "user_utterance"},
            "autonomy_intent": {"mode": "compare_source_refs", "origin": "counterpart_request"},
            "action_packets": [
                {
                    "proposal_id": "ap-compare-source-candidate-set-1",
                    "origin": "counterpart_request",
                    "intent": "artifact:compare_source_refs",
                    "status": "approved",
                    "risk": "read",
                    "requires_approval": False,
                    "tool_name": "compare_source_refs",
                    "tool_args": {
                        "source_ref_id": 31,
                        "source_ref_ids": [31, 33, 32],
                        "access_hints": {
                            "world_surfaces": ["source_ref"],
                            "artifact_source_ref_ids": [31, 33, 32],
                        },
                    },
                    "capability_steps": [
                        {
                            "kind": "tool_call",
                            "name": "compare_source_refs",
                            "target": "source_ref:31<->candidate_set:33,32",
                            "status": "approved",
                            "requires_approval": False,
                        }
                    ],
                    "expected_effect": "把当前这条材料和前一条相关材料对一遍，确认现在该沿哪条线索继续判断。",
                }
            ],
            "action_trace": [],
            "behavior_queue": [],
            "toolset_unlocks": {},
            "last_external_tools": [],
            "evidence_pack": [],
            "world_model_state": {},
            "semantic_narrative_profile": {},
            "turn_appraisal": {},
            "evolution_state": {},
            "emotion_state": {},
            "bond_state": {},
            "counterpart_assessment": {},
            "behavior_action": {},
            "behavior_plan": {},
            "agenda_lifecycle_residue": {},
        }
        store = self._SourceRefStore(
            [
                {
                    "id": 31,
                    "url": "https://docs.example.com/spec",
                    "title": "Spec Draft",
                    "query": "amadeus source anchor draft",
                    "tool_name": "search_web",
                    "snippet": "Older draft with a short note.",
                    "retrieved_at": 1712000000,
                },
                {
                    "id": 32,
                    "url": "https://docs.example.com/spec",
                    "title": "Spec Final",
                    "query": "amadeus source anchor final",
                    "tool_name": "search_web",
                    "snippet": "Final spec with the stable anchor details and the longer resolved summary.",
                    "retrieved_at": 1712999999,
                },
                {
                    "id": 33,
                    "url": "https://docs.example.com/side-note",
                    "title": "Side Note",
                    "query": "amadeus unrelated note",
                    "tool_name": "search_web",
                    "snippet": "A weaker side note that should not outrank the final spec.",
                    "retrieved_at": 1712500000,
                },
            ]
        )
        with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
            with patch("amadeus_thread0.graph_parts.tool_nodes._get_store", return_value=object()):
                out = _node_autonomy_execute(state)

        self.assertEqual(out["action_packets"][0]["status"], "completed")
        self.assertEqual(out["action_packets"][0]["tool_name"], "compare_source_refs")
        self.assertEqual(out["action_packets"][0]["artifact_context"]["source_ref_ids"], [32, 31, 33])
        self.assertEqual(out["action_packets"][0]["artifact_context"]["preferred_source_ref_id"], 32)
        self.assertEqual(out["autonomy_intent"]["mode"], "compare_source_refs")
        self.assertEqual(out["session_context"]["digital_body_hints"]["artifact_source_ref_ids"], [32, 31, 33])
        self.assertEqual(int(out["session_context"]["digital_body_hints"]["preferred_source_ref_id"]), 32)
        self.assertEqual(out["digital_body_state"]["resource_state"]["active_artifact_label"], "Spec Final")

    def test_tool_execute_write_workspace_file_updates_session_context(self):
        with TemporaryDirectory() as td:
            runtime_dir = Path(td) / "runtime"
            workspace = runtime_dir / "workspaces" / "lab"
            workspace.mkdir(parents=True)
            state = {
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tc-1",
                                "name": "write_workspace_file",
                                "args": {
                                    "relative_path": "notes/todo.md",
                                    "content": "buy bananas",
                                    "access_hints": {
                                        "filesystem_state": "writable",
                                        "active_artifact_kind": "workspace",
                                        "active_artifact_ref": str(workspace),
                                        "active_artifact_label": "lab",
                                    },
                                },
                            }
                        ],
                    )
                ],
                "approval_actions": [
                    {
                        "id": "tc-1",
                        "name": "write_workspace_file",
                        "args": {
                            "relative_path": "notes/todo.md",
                            "content": "buy bananas",
                            "access_hints": {
                                "filesystem_state": "writable",
                                "active_artifact_kind": "workspace",
                                "active_artifact_ref": str(workspace),
                                "active_artifact_label": "lab",
                            },
                        },
                        "proposal_id": "ap-write-workspace-file-1",
                        "action": "approve",
                    }
                ],
                "session_context": {
                    "digital_body_hints": {
                        "filesystem_state": "writable",
                        "active_artifact_kind": "workspace",
                        "active_artifact_ref": str(workspace),
                        "active_artifact_label": "lab",
                    }
                },
                "toolset_unlocks": {},
                "evidence_pack": [],
                "last_external_tools": [],
                "memory_guard_checked": 0,
                "memory_guard_blocked": 0,
                "current_event": {"kind": "user_utterance"},
                "turn_appraisal": {},
                "world_model_state": {},
                "semantic_narrative_profile": {},
                "evolution_state": {},
                "emotion_state": {},
                "bond_state": {},
                "counterpart_assessment": {},
                "behavior_action": {},
                "behavior_plan": {},
                "interaction_carryover": {},
                "agenda_lifecycle_residue": {},
                "autonomy_intent": {"mode": "language_response", "origin": "counterpart_request"},
                "action_packets": [],
                "action_trace": [],
            }
            env = {
                "AMADEUS_DATA_DIR": str(runtime_dir),
                "AMADEUS_MODEL_PROVIDER": "openai_compatible",
            }
            with patch("amadeus_thread0.graph_parts.tool_nodes._get_store", return_value=object()):
                with patch.dict(os.environ, env, clear=True):
                    out = _node_tool_execute(state)

            target = workspace / "notes" / "todo.md"
            self.assertTrue(target.exists())
            self.assertEqual(target.read_text(encoding="utf-8"), "buy bananas")
            self.assertEqual(out["action_packets"][0]["status"], "completed")
            self.assertEqual(out["action_packets"][0]["artifact_context"]["artifact_kind"], "file")
            self.assertEqual(out["session_context"]["digital_body_hints"]["active_artifact_kind"], "file")
            self.assertEqual(out["digital_body_state"]["access_state"]["filesystem_state"], "writable")
            self.assertEqual(out["digital_body_state"]["resource_state"]["active_artifact_kind"], "file")
            self.assertEqual(out["digital_body_state"]["resource_state"]["active_artifact_label"], "todo.md")

    def test_tool_execute_append_workspace_file_updates_session_context(self):
        with TemporaryDirectory() as td:
            runtime_dir = Path(td) / "runtime"
            workspace = runtime_dir / "workspaces" / "lab"
            target = workspace / "notes" / "todo.md"
            target.parent.mkdir(parents=True)
            target.write_text("buy", encoding="utf-8")
            state = {
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tc-1",
                                "name": "append_workspace_file",
                                "args": {
                                    "relative_path": "notes/todo.md",
                                    "content": " bananas",
                                    "access_hints": {
                                        "filesystem_state": "writable",
                                        "active_artifact_kind": "workspace",
                                        "active_artifact_ref": str(workspace),
                                        "active_artifact_label": "lab",
                                    },
                                },
                            }
                        ],
                    )
                ],
                "approval_actions": [
                    {
                        "id": "tc-1",
                        "name": "append_workspace_file",
                        "args": {
                            "relative_path": "notes/todo.md",
                            "content": " bananas",
                            "access_hints": {
                                "filesystem_state": "writable",
                                "active_artifact_kind": "workspace",
                                "active_artifact_ref": str(workspace),
                                "active_artifact_label": "lab",
                            },
                        },
                        "proposal_id": "ap-append-workspace-file-1",
                        "action": "approve",
                    }
                ],
                "session_context": {
                    "digital_body_hints": {
                        "filesystem_state": "writable",
                        "active_artifact_kind": "workspace",
                        "active_artifact_ref": str(workspace),
                        "active_artifact_label": "lab",
                    }
                },
                "toolset_unlocks": {},
                "evidence_pack": [],
                "last_external_tools": [],
                "memory_guard_checked": 0,
                "memory_guard_blocked": 0,
                "current_event": {"kind": "user_utterance"},
                "turn_appraisal": {},
                "world_model_state": {},
                "semantic_narrative_profile": {},
                "evolution_state": {},
                "emotion_state": {},
                "bond_state": {},
                "counterpart_assessment": {},
                "behavior_action": {},
                "behavior_plan": {},
                "interaction_carryover": {},
                "agenda_lifecycle_residue": {},
                "autonomy_intent": {"mode": "language_response", "origin": "counterpart_request"},
                "action_packets": [],
                "action_trace": [],
            }
            env = {
                "AMADEUS_DATA_DIR": str(runtime_dir),
                "AMADEUS_MODEL_PROVIDER": "openai_compatible",
            }
            with patch("amadeus_thread0.graph_parts.tool_nodes._get_store", return_value=object()):
                with patch.dict(os.environ, env, clear=True):
                    out = _node_tool_execute(state)

            self.assertEqual(target.read_text(encoding="utf-8"), "buy bananas")
            self.assertEqual(out["action_packets"][0]["status"], "completed")
            self.assertEqual(out["action_packets"][0]["artifact_context"]["artifact_kind"], "file")
            self.assertEqual(out["session_context"]["digital_body_hints"]["active_artifact_kind"], "file")
            self.assertEqual(out["digital_body_state"]["resource_state"]["active_artifact_label"], "todo.md")

    def test_tool_gate_attaches_proposal_id_and_keeps_external_mutation_human_gated(self):
        state = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[{"id": "tc-1", "name": "write_diary", "args": {"target": "lab", "reason": "记录结果"}}],
                )
            ],
            "current_event": {"kind": "user_utterance"},
            "turn_appraisal": {},
            "world_model_state": {},
            "semantic_narrative_profile": {},
            "evolution_state": {},
            "emotion_state": {},
            "bond_state": {},
            "counterpart_assessment": {},
            "behavior_action": {},
            "behavior_plan": {},
            "interaction_carryover": {},
            "agenda_lifecycle_residue": {},
            "autonomy_intent": {"mode": "language_response", "origin": "counterpart_request"},
            "action_packets": [],
            "action_trace": [],
        }
        with patch("amadeus_thread0.graph_parts.tool_nodes.auto_approve_tool_names", return_value={"write_diary"}):
            with patch(
                "amadeus_thread0.graph_parts.tool_nodes.interrupt",
                return_value={"decisions": [{"action": "approve"}]},
            ):
                out = _node_tool_gate(state)

        self.assertEqual(out["approval_actions"][0]["id"], "tc-1")
        self.assertTrue(str(out["approval_actions"][0]["proposal_id"]).startswith("ap-"))
        self.assertEqual(out["action_packets"][0]["status"], "approved")
        self.assertEqual(out["reconsolidation_snapshot"]["action_packets"][0]["proposal_id"], out["approval_actions"][0]["proposal_id"])

    def test_tool_gate_attaches_workspace_mutation_preview_before_human_approval(self):
        with TemporaryDirectory() as td:
            runtime_dir = Path(td) / "runtime"
            workspace = runtime_dir / "workspaces" / "lab"
            target = workspace / "notes" / "todo.md"
            target.parent.mkdir(parents=True)
            target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
            state = {
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tc-1",
                                "name": "replace_workspace_lines",
                                "args": {
                                    "relative_path": "notes/todo.md",
                                    "start_line": 2,
                                    "end_line": 2,
                                    "new_text": "beta v2",
                                    "access_hints": {
                                        "filesystem_state": "writable",
                                        "active_artifact_kind": "workspace",
                                        "active_artifact_ref": str(workspace),
                                        "active_artifact_label": "lab",
                                    },
                                },
                            }
                        ],
                    )
                ],
                "current_event": {"kind": "user_utterance"},
                "turn_appraisal": {},
                "world_model_state": {},
                "semantic_narrative_profile": {},
                "evolution_state": {},
                "emotion_state": {},
                "bond_state": {},
                "counterpart_assessment": {},
                "behavior_action": {},
                "behavior_plan": {},
                "interaction_carryover": {},
                "agenda_lifecycle_residue": {},
                "autonomy_intent": {"mode": "language_response", "origin": "counterpart_request"},
                "action_packets": [],
                "action_trace": [],
            }
            env = {
                "AMADEUS_DATA_DIR": str(runtime_dir),
                "AMADEUS_MODEL_PROVIDER": "openai_compatible",
            }
            with patch.dict(os.environ, env, clear=True):
                with patch(
                    "amadeus_thread0.graph_parts.tool_nodes.interrupt",
                    return_value={"decisions": [{"action": "approve"}]},
                ):
                    out = _node_tool_gate(state)

        preview = out["approval_actions"][0]["mutation_preview"]
        self.assertTrue(preview["can_apply"])
        self.assertEqual(preview["mutation_mode"], "replace")
        self.assertEqual(preview["relative_path"], "notes/todo.md")
        self.assertIn("-beta", preview["diff_preview"])
        self.assertIn("+beta v2", preview["diff_preview"])
        self.assertEqual(out["action_packets"][0]["tool_name"], "replace_workspace_lines")
        self.assertEqual(out["action_packets"][0]["status"], "approved")
        self.assertEqual(out["action_packets"][0]["mutation_preview"]["relative_path"], "notes/todo.md")
        self.assertIn("+beta v2", out["action_packets"][0]["mutation_preview"]["diff_preview"])

    def test_tool_execute_preserves_workspace_mutation_preview_on_completed_packet(self):
        with TemporaryDirectory() as td:
            runtime_dir = Path(td) / "runtime"
            workspace = runtime_dir / "workspaces" / "lab"
            target = workspace / "notes" / "todo.md"
            target.parent.mkdir(parents=True)
            target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
            state = {
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tc-1",
                                "name": "replace_workspace_lines",
                                "args": {
                                    "relative_path": "notes/todo.md",
                                    "start_line": 2,
                                    "end_line": 2,
                                    "new_text": "beta v2",
                                    "access_hints": {
                                        "filesystem_state": "writable",
                                        "active_artifact_kind": "workspace",
                                        "active_artifact_ref": str(workspace),
                                        "active_artifact_label": "lab",
                                    },
                                },
                            }
                        ],
                    )
                ],
                "approval_actions": [
                    {
                        "id": "tc-1",
                        "name": "replace_workspace_lines",
                        "args": {
                            "relative_path": "notes/todo.md",
                            "start_line": 2,
                            "end_line": 2,
                            "new_text": "beta v2",
                            "access_hints": {
                                "filesystem_state": "writable",
                                "active_artifact_kind": "workspace",
                                "active_artifact_ref": str(workspace),
                                "active_artifact_label": "lab",
                            },
                        },
                        "proposal_id": "ap-file-lines-1",
                        "action": "approve",
                    }
                ],
                "session_context": {
                    "digital_body_hints": {
                        "filesystem_state": "writable",
                        "active_artifact_kind": "workspace",
                        "active_artifact_ref": str(workspace),
                        "active_artifact_label": "lab",
                    }
                },
                "toolset_unlocks": {},
                "evidence_pack": [],
                "last_external_tools": [],
                "memory_guard_checked": 0,
                "memory_guard_blocked": 0,
                "current_event": {"kind": "user_utterance"},
                "turn_appraisal": {},
                "world_model_state": {},
                "semantic_narrative_profile": {},
                "evolution_state": {},
                "emotion_state": {},
                "bond_state": {},
                "counterpart_assessment": {},
                "behavior_action": {},
                "behavior_plan": {},
                "interaction_carryover": {},
                "agenda_lifecycle_residue": {},
                "autonomy_intent": {"mode": "language_response", "origin": "counterpart_request"},
                "action_packets": [
                    {
                        "proposal_id": "ap-file-lines-1",
                        "origin": "counterpart_request",
                        "intent": "artifact:replace_lines",
                        "status": "approved",
                        "risk": "external_mutation",
                        "requires_approval": True,
                        "tool_name": "replace_workspace_lines",
                        "tool_args": {
                            "relative_path": "notes/todo.md",
                            "start_line": 2,
                            "end_line": 2,
                            "new_text": "beta v2",
                        },
                        "mutation_preview": {
                            "tool_name": "replace_workspace_lines",
                            "can_apply": True,
                            "mutation_mode": "replace",
                            "relative_path": "notes/todo.md",
                            "summary": "todo.md 的 patch 预览已生成。",
                            "diff_preview": "--- a/notes/todo.md\n+++ b/notes/todo.md\n@@\n-beta\n+beta v2\n",
                        },
                    }
                ],
                "action_trace": [],
            }
            env = {
                "AMADEUS_DATA_DIR": str(runtime_dir),
                "AMADEUS_MODEL_PROVIDER": "openai_compatible",
            }
            with patch("amadeus_thread0.graph_parts.tool_nodes._get_store", return_value=object()):
                with patch.dict(os.environ, env, clear=True):
                    out = _node_tool_execute(state)

            self.assertEqual(target.read_text(encoding="utf-8"), "alpha\nbeta v2\ngamma\n")
            self.assertEqual(out["action_packets"][0]["status"], "completed")
            self.assertEqual(out["action_packets"][0]["mutation_preview"]["relative_path"], "notes/todo.md")
            self.assertIn("+beta v2", out["action_packets"][0]["mutation_preview"]["diff_preview"])

    def test_tool_execute_writes_completed_packet_and_trace(self):
        state = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[{"id": "tc-1", "name": "request_toolset_upgrade", "args": {"requested_tools": ["search_langchain_docs"]}}],
                )
            ],
            "approval_actions": [
                {
                    "id": "tc-1",
                    "name": "request_toolset_upgrade",
                    "args": {"requested_tools": ["search_langchain_docs"], "reason": "need docs"},
                    "proposal_id": "ap-upgrade-1",
                    "action": "approve",
                }
            ],
            "toolset_unlocks": {},
            "evidence_pack": [],
            "last_external_tools": [],
            "memory_guard_checked": 0,
            "memory_guard_blocked": 0,
            "current_event": {"kind": "user_utterance"},
            "turn_appraisal": {},
            "world_model_state": {},
            "semantic_narrative_profile": {},
            "evolution_state": {},
            "emotion_state": {},
            "bond_state": {},
            "counterpart_assessment": {},
            "behavior_action": {},
            "behavior_plan": {},
            "interaction_carryover": {},
            "agenda_lifecycle_residue": {},
            "autonomy_intent": {"mode": "language_response", "origin": "counterpart_request"},
            "action_packets": [],
            "action_trace": [],
        }
        with patch("amadeus_thread0.graph_parts.tool_nodes._get_store", return_value=object()):
            with patch("amadeus_thread0.graph_parts.tool_nodes._memory_guard_check", return_value=(True, "")):
                with patch("amadeus_thread0.graph_parts.tool_nodes._tool_lookup", return_value=object()):
                    with patch(
                        "amadeus_thread0.graph_parts.tool_nodes._invoke_tool",
                        return_value={"requested_tools": ["search_langchain_docs"]},
                    ):
                        with patch("amadeus_thread0.graph_parts.tool_nodes._auto_reconsolidate_after_tool"):
                            with patch("amadeus_thread0.graph_parts.tool_nodes._build_evidence_from_tool_result", return_value=[]):
                                out = _node_tool_execute(state)

        self.assertEqual(out["action_packets"][0]["proposal_id"], "ap-upgrade-1")
        self.assertEqual(out["action_packets"][0]["status"], "completed")
        self.assertEqual(out["autonomy_intent"]["mode"], "tool_completed")
        trace_events = [item["event"] for item in out["action_trace"]]
        self.assertIn("started", trace_events)
        self.assertIn("completed", trace_events)
        self.assertEqual(out["reconsolidation_snapshot"]["action_packets"][0]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
