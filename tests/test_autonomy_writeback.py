from __future__ import annotations

import unittest

from amadeus_thread0.evolution_engine.reconsolidation import build_reconsolidation_snapshot
from amadeus_thread0.runtime.final_state import (
    resolve_action_packets,
    resolve_action_trace,
    resolve_autonomy_block_reason,
    resolve_autonomy_intent,
    resolve_digital_body_state,
    resolve_pending_action_proposal,
)


class AutonomyWritebackTests(unittest.TestCase):
    def test_build_reconsolidation_snapshot_compacts_autonomy_payload(self):
        snapshot = build_reconsolidation_snapshot(
            current_event={"kind": "user_utterance"},
            appraisal={"interaction_frame": "relationship"},
            world_model_state={"presence_residue": 0.32},
            semantic_narrative_profile={"continuity_depth": 0.54},
            latent_state={"self_coherence": 0.78},
            emotion_state={"label": "care"},
            bond_state={"trust": 0.7},
            counterpart_assessment={"stance": "watchful"},
            behavior_action={"interaction_mode": "checkin", "primary_motive": "honor_continuity"},
            behavior_plan={"kind": "deferred_checkin"},
            interaction_carryover={"strength": 0.44, "carryover_mode": "warm_residue"},
            agenda_lifecycle_residue={"kind": "held"},
            autonomy_intent={
                "mode": "approval_pending",
                "origin": "motive_goal",
                "reason": "先提出能力升级，再决定是否继续。",
                "confidence": 0.63,
                "primary_proposal_id": "ap-1",
            },
            action_packets=[
                {
                    "proposal_id": "ap-1",
                    "origin": "capability_upgrade",
                    "intent": "toolset_upgrade_proposal",
                    "status": "awaiting_approval",
                    "risk": "read",
                    "requires_approval": False,
                    "capability_steps": [],
                    "expected_effect": "申请临时能力",
                    "artifact_context": {
                        "carrier": "source_ref",
                        "artifact_kind": "search_result",
                        "artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                        "artifact_label": "Persistence",
                        "reacquisition_mode": "rerun_search",
                        "preview": "Persistence in LangGraph uses checkpointers and thread-scoped state." * 20,
                        "source_ref_ids": [17],
                        "source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                        "source_query": "langgraph persistence checkpointer thread",
                    },
                }
            ],
            action_trace=[{"proposal_id": "ap-1", "status": "awaiting_approval", "event": "tool_gate_decision"}],
            autonomy_block_reason="",
            digital_body_state={
                "active_surface": "approval_gate",
                "perception_channels": ["chat", "text"],
                "action_channels": ["language", "tooling", "approval_gate"],
                "available_toolsets": ["search_web"],
                "active_tools": ["write_diary"],
                "access_state": {
                    "mode": "approval_pending",
                    "conditions": ["human_approval_required", "external_mutation_gated"],
                    "pending_approval_count": 1,
                    "external_mutation_pending": True,
                },
                "resource_state": {"action_packet_count": 1, "pending_approval_count": 1},
                "body_constraints": ["human_approval_required", "external_mutation_gated"],
            },
        )
        self.assertEqual(snapshot["autonomy_intent"]["mode"], "approval_pending")
        self.assertEqual(snapshot["action_packets"][0]["proposal_id"], "ap-1")
        artifact_context = snapshot["action_packets"][0].get("artifact_context") if isinstance(snapshot["action_packets"][0].get("artifact_context"), dict) else {}
        self.assertEqual(artifact_context.get("carrier"), "source_ref")
        self.assertEqual(artifact_context.get("artifact_kind"), "search_result")
        self.assertEqual(artifact_context.get("artifact_label"), "Persistence")
        self.assertEqual(artifact_context.get("source_ref_ids"), [17])
        self.assertTrue(bool(artifact_context.get("preview_truncated")))
        self.assertEqual(snapshot["action_trace"][0]["event"], "tool_gate_decision")
        self.assertEqual(snapshot["digital_body_state"]["access_state"]["mode"], "approval_pending")
        self.assertEqual(snapshot["digital_body_consequence"]["kind"], "access_request_pending")
        self.assertIn("human_approval", snapshot["digital_body_consequence"]["requested_access"])
        self.assertEqual(snapshot["digital_body_consequence"]["artifact_carrier"], "source_ref")
        self.assertEqual(snapshot["digital_body_consequence"]["artifact_source_ref_ids"], [17])
        self.assertIn("docs.langchain.com", snapshot["digital_body_consequence"]["artifact_source_url"])
        self.assertEqual(
            snapshot["digital_body_consequence"]["artifact_source_query"],
            "langgraph persistence checkpointer thread",
        )

    def test_final_state_resolvers_prefer_frozen_terminal_packets(self):
        reconsolidation_snapshot = {
            "autonomy_intent": {
                "mode": "tool_completed",
                "origin": "capability_upgrade",
                "reason": "已经完成临时能力升级。",
                "confidence": 0.71,
                "primary_proposal_id": "ap-1",
            },
            "action_packets": [
                {
                    "proposal_id": "ap-1",
                    "origin": "capability_upgrade",
                    "intent": "toolset_upgrade_proposal",
                    "status": "completed",
                    "risk": "read",
                "requires_approval": False,
                "capability_steps": [],
                "expected_effect": "申请临时能力",
                "result_summary": "upgrade accepted",
                "writeback_ready": True,
                "artifact_context": {
                    "carrier": "filesystem",
                    "artifact_kind": "file",
                    "artifact_ref": "notes/plan.md",
                    "artifact_label": "plan.md",
                    "reacquisition_mode": "reopen_file",
                    "preview": "# plan\nkeep going\n",
                    "exists": True,
                },
            }
        ],
            "action_trace": [{"proposal_id": "ap-1", "status": "completed", "event": "completed"}],
            "autonomy_block_reason": "",
        }
        live_packets = [
            {
                "proposal_id": "ap-1",
                "origin": "capability_upgrade",
                "intent": "toolset_upgrade_proposal",
                "status": "executing",
                "risk": "read",
                "requires_approval": False,
                "capability_steps": [],
                "expected_effect": "stale live packet",
            }
        ]
        self.assertEqual(
            resolve_autonomy_intent(autonomy_intent={"mode": "autonomy_executing"}, reconsolidation_snapshot=reconsolidation_snapshot)["mode"],
            "tool_completed",
        )
        self.assertEqual(resolve_action_packets(action_packets=live_packets, reconsolidation_snapshot=reconsolidation_snapshot)[0]["status"], "completed")
        resolved_artifact_context = resolve_action_packets(action_packets=live_packets, reconsolidation_snapshot=reconsolidation_snapshot)[0].get("artifact_context")
        self.assertEqual(resolved_artifact_context["artifact_label"], "plan.md")
        self.assertEqual(resolved_artifact_context["carrier"], "filesystem")
        self.assertEqual(resolve_action_trace(action_trace=[], reconsolidation_snapshot=reconsolidation_snapshot)[0]["event"], "completed")
        self.assertEqual(
            resolve_digital_body_state(
                digital_body_state={},
                reconsolidation_snapshot={
                    **reconsolidation_snapshot,
                    "digital_body_state": {
                        "active_surface": "tooling",
                        "perception_channels": ["dialogue"],
                        "action_channels": ["language", "tooling"],
                        "access_state": {"mode": "tool_enabled"},
                        "resource_state": {"action_packet_count": 1},
                    },
                },
            )["access_state"]["mode"],
            "tool_enabled",
        )
        growth_snapshot = build_reconsolidation_snapshot(
            current_event={"kind": "user_utterance"},
            appraisal={"interaction_frame": "task"},
            world_model_state={},
            semantic_narrative_profile={},
            latent_state={"self_coherence": 0.8},
            emotion_state={"label": "neutral"},
            bond_state={"trust": 0.5},
            behavior_action={"interaction_mode": "tooling", "primary_motive": "solve_task"},
            action_packets=[
                {
                    "proposal_id": "ap-grow",
                    "origin": "capability_upgrade",
                    "intent": "toolset_upgrade_proposal",
                    "status": "completed",
                    "risk": "read",
                    "requires_approval": False,
                    "capability_steps": [],
                    "expected_effect": "unlock web",
                    "result_summary": "upgrade accepted",
                    "writeback_ready": True,
                    "tool_name": "search_web",
                }
            ],
            digital_body_state={
                "active_surface": "tooling",
                "perception_channels": ["dialogue"],
                "action_channels": ["language", "tooling"],
                "world_surfaces": ["dialogue", "browser"],
                "available_toolsets": ["search_web"],
                "active_tools": ["search_web"],
                "access_state": {
                    "mode": "tool_enabled",
                    "conditions": [],
                    "granted_toolsets": ["search_web"],
                },
                "resource_state": {"completed_packet_count": 1, "external_tool_count": 1},
            },
        )
        self.assertEqual(growth_snapshot["digital_body_consequence"]["kind"], "embodied_growth")
        self.assertTrue(bool(growth_snapshot["digital_body_consequence"]["procedural_growth"]))

    def test_pending_and_block_reason_resolution_use_live_signal_when_needed(self):
        live_packet = {
            "proposal_id": "ap-2",
            "origin": "motive_goal",
            "intent": "tool:write_diary",
            "status": "awaiting_approval",
            "risk": "external_mutation",
            "requires_approval": True,
            "capability_steps": [],
            "expected_effect": "写一条外部记录",
        }
        self.assertEqual(
            resolve_pending_action_proposal(
                pending_action_proposal={},
                action_packets=[live_packet],
                reconsolidation_snapshot={},
            )["proposal_id"],
            "ap-2",
        )
        resolved_intent = resolve_autonomy_intent(
            autonomy_intent={
                "mode": "queue_followthrough",
                "origin": "counterpart_request",
                "reason": "先守住边界和自我位置，再决定要不要继续靠近。",
                "primary_proposal_id": "ap-old",
            },
            action_packets=[live_packet],
            current_event={"kind": "user_utterance"},
            reconsolidation_snapshot={
                "autonomy_intent": {
                    "mode": "queue_followthrough",
                    "origin": "counterpart_request",
                    "reason": "先守住边界和自我位置，再决定要不要继续靠近。",
                    "primary_proposal_id": "ap-old",
                }
            },
        )
        self.assertEqual(resolved_intent["mode"], "approval_pending")
        self.assertEqual(resolved_intent["primary_proposal_id"], "ap-2")
        self.assertNotEqual(
            resolved_intent["reason"],
            "先守住边界和自我位置，再决定要不要继续靠近。",
        )
        self.assertEqual(
            resolve_autonomy_block_reason(
                autonomy_block_reason="",
                action_packets=[{**live_packet, "status": "blocked", "block_reason": "tool failed"}],
                reconsolidation_snapshot={},
            ),
            "tool failed",
        )


if __name__ == "__main__":
    unittest.main()
