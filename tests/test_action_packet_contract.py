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
        self.assertEqual(risk_from_tool_name("write_diary"), "external_mutation")


if __name__ == "__main__":
    unittest.main()
