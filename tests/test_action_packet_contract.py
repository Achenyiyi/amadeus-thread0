from __future__ import annotations

import unittest

from amadeus_thread0.graph_parts.action_packets import (
    build_behavior_action_packet,
    build_tool_action_packet,
    normalize_action_packet,
    normalize_action_packets,
    risk_from_tool_name,
)


class ActionPacketContractTests(unittest.TestCase):
    def test_normalize_action_packet_enforces_contract_defaults(self):
        packet = normalize_action_packet(
            {
                "origin": "unknown",
                "intent": " Respond ",
                "status": "mystery",
                "risk": "danger",
                "expected_effect": "keep talking",
            }
        )
        self.assertEqual(packet["origin"], "motive_goal")
        self.assertEqual(packet["intent"], "respond")
        self.assertEqual(packet["status"], "proposed")
        self.assertEqual(packet["risk"], "read")
        self.assertFalse(packet["requires_approval"])
        self.assertTrue(str(packet["proposal_id"]).startswith("ap-"))

    def test_normalize_action_packet_preserves_structured_artifact_context(self):
        packet = normalize_action_packet(
            {
                "proposal_id": "ap-artifact-1",
                "origin": "counterpart_request",
                "intent": "artifact:reopen_file",
                "status": "completed",
                "risk": "read",
                "result_summary": "已重新接回文件 plan.md。",
                "writeback_ready": True,
                "artifact_context": {
                    "carrier": "filesystem",
                    "artifact_kind": "file",
                    "artifact_ref": "notes/plan.md",
                    "artifact_label": "plan.md",
                    "reacquisition_mode": "reopen_file",
                    "preview": "hello" * 400,
                    "exists": True,
                    "size_bytes": 128,
                    "updated_at": 1712345678,
                },
            }
        )
        artifact_context = packet.get("artifact_context") if isinstance(packet.get("artifact_context"), dict) else {}
        self.assertEqual(artifact_context["carrier"], "filesystem")
        self.assertEqual(artifact_context["artifact_kind"], "file")
        self.assertEqual(artifact_context["artifact_label"], "plan.md")
        self.assertEqual(artifact_context["reacquisition_mode"], "reopen_file")
        self.assertTrue(artifact_context["exists"])
        self.assertEqual(artifact_context["size_bytes"], 128)
        self.assertEqual(artifact_context["updated_at"], 1712345678)
        self.assertEqual(len(artifact_context["preview"]), 1200)
        self.assertTrue(artifact_context["preview_truncated"])

    def test_normalize_action_packet_dedupes_source_ref_identity_fields(self):
        packet = normalize_action_packet(
            {
                "proposal_id": "ap-artifact-2",
                "origin": "counterpart_request",
                "intent": "artifact:rerun_search",
                "status": "completed",
                "risk": "read",
                "result_summary": "已重新接回检索结果 Persistence v2。",
                "writeback_ready": True,
                "artifact_context": {
                    "carrier": " source_ref ",
                    "artifact_kind": "search_result",
                    "artifact_label": "Persistence v2",
                    "source_ref_ids": ["21", "21", "17", "0", -1],
                    "preferred_source_ref_id": "21",
                    "preferred_anchor_reason": " Primary_More_Current ",
                    "source_url": " https://docs.langchain.com/oss/python/langgraph/persistence ",
                    "source_query": " langgraph persistence checkpointer thread recovery ",
                    "source_title": " Persistence v2 ",
                    "source_tool_name": " search_web ",
                },
            }
        )
        artifact_context = packet.get("artifact_context") if isinstance(packet.get("artifact_context"), dict) else {}
        self.assertEqual(artifact_context["carrier"], "source_ref")
        self.assertEqual(artifact_context["source_ref_ids"], [21, 17])
        self.assertEqual(artifact_context["preferred_source_ref_id"], 21)
        self.assertEqual(artifact_context["preferred_anchor_reason"], "primary_more_current")
        self.assertEqual(
            artifact_context["source_url"],
            "https://docs.langchain.com/oss/python/langgraph/persistence",
        )
        self.assertEqual(
            artifact_context["source_query"],
            "langgraph persistence checkpointer thread recovery",
        )
        self.assertEqual(artifact_context["source_title"], "Persistence v2")
        self.assertEqual(artifact_context["source_tool_name"], "search_web")

    def test_normalize_action_packet_promotes_preferred_source_ref_to_front(self):
        packet = normalize_action_packet(
            {
                "proposal_id": "ap-artifact-3",
                "origin": "counterpart_request",
                "intent": "artifact:compare_source_refs",
                "status": "completed",
                "risk": "read",
                "writeback_ready": True,
                "artifact_context": {
                    "carrier": "source_ref",
                    "artifact_kind": "search_result",
                    "artifact_label": "Persistence v2",
                    "source_ref_ids": ["17", "21", "15"],
                    "preferred_source_ref_id": "21",
                    "preferred_anchor_reason": "primary_more_current",
                    "source_title": "Persistence v2",
                },
            }
        )
        artifact_context = packet.get("artifact_context") if isinstance(packet.get("artifact_context"), dict) else {}
        self.assertEqual(artifact_context["source_ref_ids"], [21, 17, 15])
        self.assertEqual(artifact_context["preferred_source_ref_id"], 21)

    def test_normalize_action_packet_preserves_tool_args_for_backend_execution(self):
        packet = normalize_action_packet(
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
                    "access_hints": {
                        "active_artifact_kind": "workspace",
                        "active_artifact_label": "lab",
                    },
                },
            }
        )
        self.assertEqual(packet["tool_name"], "write_workspace_file")
        self.assertEqual(packet["tool_args"]["relative_path"], "notes/todo.md")
        self.assertEqual(packet["tool_args"]["content"], "buy bananas")
        self.assertEqual(packet["tool_args"]["access_hints"]["active_artifact_kind"], "workspace")

    def test_normalize_action_packet_preserves_mutation_preview(self):
        packet = normalize_action_packet(
            {
                "proposal_id": "ap-file-lines-1",
                "origin": "counterpart_request",
                "intent": "artifact:replace_lines",
                "status": "awaiting_approval",
                "risk": "external_mutation",
                "requires_approval": True,
                "tool_name": "replace_workspace_lines",
                "mutation_preview": {
                    "tool_name": "replace_workspace_lines",
                    "can_apply": True,
                    "mutation_mode": "replace",
                    "relative_path": "notes/todo.md",
                    "summary": "审批通过后会把第二行替换成 beta v2。",
                    "diff_preview": "--- a/notes/todo.md\n+++ b/notes/todo.md\n@@\n-beta\n+beta v2\n",
                },
            }
        )
        self.assertEqual(packet["mutation_preview"]["tool_name"], "replace_workspace_lines")
        self.assertTrue(packet["mutation_preview"]["can_apply"])
        self.assertEqual(packet["mutation_preview"]["mutation_mode"], "replace")
        self.assertEqual(packet["mutation_preview"]["relative_path"], "notes/todo.md")
        self.assertIn("+beta v2", packet["mutation_preview"]["diff_preview"])

    def test_normalize_action_packet_preserves_access_acquire_proposals(self):
        packet = normalize_action_packet(
            {
                "proposal_id": "ap-access-help-1",
                "origin": "counterpart_request",
                "intent": "access:request_help",
                "status": "approved",
                "risk": "external_mutation",
                "requires_approval": True,
                "access_acquire_proposals": [
                    {
                        "target": "api_key",
                        "mode": "operator_provide_api_key",
                        "path_kind": "create_new",
                        "summary": "需要先提供可用 API key。",
                        "operator_action": "填入一个可用 key。",
                        "grants": ["api_key"],
                        "requires_operator": True,
                    }
                ],
                "selected_access_proposal": {
                    "target": "api_key",
                    "mode": "operator_provide_api_key",
                    "path_kind": "create_new",
                    "summary": "需要先提供可用 API key。",
                    "operator_action": "填入一个可用 key。",
                    "grants": ["api_key"],
                    "requires_operator": True,
                    "resolved_grants": ["api_key"],
                    "pending_grants": [],
                    "completion_ratio": 1.0,
                },
            }
        )
        proposals = packet.get("access_acquire_proposals") if isinstance(packet.get("access_acquire_proposals"), list) else []
        selected = packet.get("selected_access_proposal") if isinstance(packet.get("selected_access_proposal"), dict) else {}
        self.assertEqual(proposals[0]["target"], "api_key")
        self.assertEqual(proposals[0]["mode"], "operator_provide_api_key")
        self.assertEqual(proposals[0]["path_kind"], "create_new")
        self.assertEqual(proposals[0]["grants"], ["api_key"])
        self.assertEqual(selected["target"], "api_key")
        self.assertEqual(selected["mode"], "operator_provide_api_key")
        self.assertEqual(selected["path_kind"], "create_new")
        self.assertEqual(selected["resolved_grants"], ["api_key"])
        self.assertEqual(selected["pending_grants"], [])
        self.assertEqual(selected["completion_ratio"], 1.0)

    def test_build_behavior_action_packet_links_behavior_queue(self):
        packet = build_behavior_action_packet(
            current_event={"kind": "scheduled_life_due"},
            behavior_action={
                "interaction_mode": "self_activity_reopen",
                "action_target": "counterpart",
                "goal_frame": "先把前面那点窗口留住。",
            },
            behavior_plan={
                "kind": "deferred_checkin",
                "target": "counterpart",
                "trigger_family": "life_window",
                "goal_frame": "等更自然的时候再接回来。",
            },
            behavior_queue=[{"agenda_id": "agenda-1", "kind": "deferred_checkin", "status": "queued"}],
            agenda_lifecycle_residue={"note": "窗口还在。"},
        )
        self.assertEqual(packet["origin"], "own_rhythm")
        self.assertEqual(packet["status"], "queued")
        self.assertEqual(packet["linked_queue_id"], "agenda-1")
        self.assertEqual(packet["capability_steps"][1]["kind"], "queue")

    def test_build_tool_action_packet_respects_risk_contract(self):
        upgrade = build_tool_action_packet(
            tool_name="request_toolset_upgrade",
            proposal_id="ap-upgrade",
            args={"requested_tools": ["search_langchain_docs"], "reason": "need docs"},
            action="approve",
            status="completed",
            result_summary="upgrade accepted",
        )
        self.assertEqual(upgrade["origin"], "capability_upgrade")
        self.assertEqual(upgrade["risk"], "read")
        self.assertFalse(upgrade["requires_approval"])
        self.assertTrue(upgrade["writeback_ready"])

        external = build_tool_action_packet(
            tool_name="write_diary",
            proposal_id="ap-diary",
            args={"target": "lab_note"},
            action="approve",
        )
        self.assertEqual(external["risk"], "external_mutation")
        self.assertTrue(external["requires_approval"])

    def test_build_tool_action_packet_uses_sandbox_intent_for_workspace_execution(self):
        packet = build_tool_action_packet(
            tool_name="execute_workspace_command",
            proposal_id="ap-sandbox-1",
            args={
                "argv": ["python", "scripts/emit.py"],
                "cwd": ".",
            },
            action="approve",
            status="awaiting_approval",
            execution_spec={
                "executor": "python",
                "profile": "python_script",
                "argv": ["python", "scripts/emit.py"],
                "cwd": "E:/runtime/workspaces/lab-notes",
                "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
                "timeout_s": 25,
                "writes_expected": True,
                "expected_artifacts": ["notes/out.txt"],
            },
        )
        self.assertEqual(packet["intent"], "sandbox:execute_workspace_command")
        self.assertEqual(packet["risk"], "external_mutation")
        self.assertTrue(packet["requires_approval"])
        self.assertEqual(packet["execution_spec"]["profile"], "python_script")

    def test_normalize_action_packet_preserves_multimodal_inspection_contract(self):
        packet = normalize_action_packet(
            {
                "proposal_id": "ap-mm-inspect-1",
                "origin": "counterpart_request",
                "intent": "artifact:inspect_multimodal",
                "status": "awaiting_approval",
                "risk": "external_mutation",
                "requires_approval": True,
                "tool_name": "inspect_multimodal_artifact",
                "multimodal_inspection_spec": {
                    "source_ref_id": "img-contract-1",
                    "modality": "image",
                    "artifact_ref": "fixtures/panel.png",
                    "artifact_label": "panel.png",
                    "consent_scope": "single_turn",
                    "capture_method": "operator_attached_file",
                    "approved_result_required": True,
                    "model_api_call_allowed": True,
                    "live_capture_allowed": True,
                },
                "multimodal_inspection_preview": {
                    "source_ref_id": "img-contract-1",
                    "modality": "image",
                    "artifact_ref": "fixtures/panel.png",
                    "artifact_label": "panel.png",
                    "requires_approval": True,
                    "auto_execute": True,
                    "model_api_call_planned": True,
                    "live_capture_allowed": True,
                },
            }
        )

        self.assertEqual(packet["intent"], "artifact:inspect_multimodal")
        self.assertEqual(packet["risk"], "external_mutation")
        self.assertTrue(packet["requires_approval"])
        self.assertEqual(packet["multimodal_inspection_spec"]["source_ref_id"], "img-contract-1")
        self.assertFalse(packet["multimodal_inspection_spec"]["model_api_call_allowed"])
        self.assertFalse(packet["multimodal_inspection_spec"]["live_capture_allowed"])
        self.assertFalse(packet["multimodal_inspection_preview"]["auto_execute"])
        self.assertFalse(packet["multimodal_inspection_preview"]["model_api_call_planned"])
        self.assertFalse(packet["multimodal_inspection_preview"]["live_capture_allowed"])

    def test_normalize_action_packets_deduplicates_by_proposal_id(self):
        packets = normalize_action_packets(
            [
                {"proposal_id": "ap-1", "intent": "respond", "status": "proposed", "expected_effect": "first"},
                {"proposal_id": "ap-1", "intent": "respond", "status": "completed", "expected_effect": "second"},
            ]
        )
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0]["status"], "completed")
        self.assertEqual(packets[0]["expected_effect"], "second")

    def test_risk_from_tool_name_matches_autonomy_policy(self):
        self.assertEqual(risk_from_tool_name("set_profile"), "memory_write")
        self.assertEqual(risk_from_tool_name("request_toolset_upgrade"), "read")
        self.assertEqual(risk_from_tool_name("create_workspace_access"), "external_mutation")
        self.assertEqual(risk_from_tool_name("inspect_source_ref"), "read")
        self.assertEqual(risk_from_tool_name("compare_source_refs"), "read")
        self.assertEqual(risk_from_tool_name("inspect_workspace_path"), "read")
        self.assertEqual(risk_from_tool_name("write_workspace_file"), "external_mutation")
        self.assertEqual(risk_from_tool_name("append_workspace_file"), "external_mutation")
        self.assertEqual(risk_from_tool_name("replace_workspace_text"), "external_mutation")
        self.assertEqual(risk_from_tool_name("replace_workspace_lines"), "external_mutation")
        self.assertEqual(risk_from_tool_name("write_diary"), "external_mutation")


if __name__ == "__main__":
    unittest.main()
