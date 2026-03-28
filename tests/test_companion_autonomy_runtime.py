from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from langchain_core.messages import AIMessage, ToolMessage

from amadeus_thread0.graph_parts.autonomy_runtime import derive_autonomy_runtime, refresh_autonomy_intent_from_packets
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
        self.assertEqual(runtime["action_trace"][0]["event"], "derived_from_embodied_carryover")
        self.assertIn("plan.md", str(runtime["autonomy_intent"]["reason"]))

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
        self.assertEqual(out["digital_body_state"]["resource_state"]["artifact_continuity"], "attached")
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
        self.assertEqual(out["digital_body_state"]["resource_state"]["artifact_continuity"], "attached")
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
