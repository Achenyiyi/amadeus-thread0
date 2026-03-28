from __future__ import annotations

import unittest
from unittest.mock import patch

from amadeus_thread0.runtime.final_state import (
    resolve_behavior_payloads,
    resolve_counterpart_assessment,
    resolve_digital_body_consequence,
    resolve_agenda_lifecycle_residue,
    resolve_interaction_carryover,
)


class FinalStateTests(unittest.TestCase):
    def test_resolve_behavior_payloads_prefers_persisted_plan_when_present(self):
        behavior_action = {
            "action_target": "offer_small_opening",
            "primary_motive": "gentle_recontact",
            "motive_tension": "self_rhythm_vs_contact",
            "goal_frame": "顺着余温轻轻回头。",
            "deferred_action_family": "small_opening",
            "relationship_weather": "warm_residue",
        }
        behavior_plan = {
            "kind": "deferred_checkin",
            "target": "counterpart",
            "trigger_family": "observe",
            "scheduled_after_min": 45,
            "legacy_hint": "keep-me",
        }

        with patch("amadeus_thread0.runtime.final_state._behavior_plan_from_action") as mock_derive:
            action, plan = resolve_behavior_payloads(
                behavior_action=behavior_action,
                behavior_plan=behavior_plan,
                current_event={"kind": "self_activity_state"},
                world_model_state={"presence_residue": 0.42},
            )

        self.assertEqual(action, behavior_action)
        self.assertEqual(plan, behavior_plan)
        mock_derive.assert_not_called()

    def test_resolve_behavior_payloads_derives_plan_only_when_final_plan_is_missing(self):
        behavior_action = {
            "action_target": "offer_small_opening",
            "primary_motive": "gentle_recontact",
            "motive_tension": "self_rhythm_vs_contact",
            "goal_frame": "顺着余温轻轻回头。",
            "deferred_action_family": "small_opening",
            "relationship_weather": "warm_residue",
        }
        partial_plan = {"legacy_hint": "keep-me"}

        with patch(
            "amadeus_thread0.runtime.final_state._behavior_plan_from_action",
            return_value={
                "kind": "small_opening",
                "target": "counterpart",
                "trigger_family": "small_opening",
                "scheduled_after_min": 0,
                "primary_motive": "gentle_recontact",
            },
        ) as mock_derive:
            _, plan = resolve_behavior_payloads(
                behavior_action=behavior_action,
                behavior_plan=partial_plan,
                current_event={"kind": "self_activity_state"},
                world_model_state={"presence_residue": 0.42},
            )

        self.assertEqual(plan["kind"], "small_opening")
        self.assertEqual(plan["trigger_family"], "small_opening")
        self.assertEqual(plan["legacy_hint"], "keep-me")
        mock_derive.assert_called_once()

    def test_resolve_behavior_payloads_prefers_frozen_reconsolidation_action_and_plan(self):
        live_action = {
            "action_target": "hold_own_rhythm",
            "interaction_mode": "self_activity_hold",
            "primary_motive": "preserve_self_rhythm",
            "goal_frame": "stale live action should not win",
        }
        live_plan = {
            "kind": "self_activity_continue",
            "trigger_family": "self_activity",
            "scheduled_after_min": 0,
        }
        reconsolidation_snapshot = {
            "behavior_action": {
                "action_target": "wait_and_recheck",
                "interaction_mode": "deferred_watch",
                "primary_motive": "honor_continuity",
                "motive_tension": "contact_without_pressure",
                "goal_frame": "顺着前面的惦记等更自然的时候再接回来。",
                "deferred_action_family": "life_window",
                "timing_window_min": 30,
                "relationship_weather": "warm_residue",
            },
            "behavior_plan": {
                "kind": "deferred_checkin",
                "target": "counterpart",
                "trigger_family": "observe",
                "scheduled_after_min": 30,
            },
        }

        with patch("amadeus_thread0.runtime.final_state._behavior_plan_from_action") as mock_derive:
            action, plan = resolve_behavior_payloads(
                behavior_action=live_action,
                behavior_plan=live_plan,
                reconsolidation_snapshot=reconsolidation_snapshot,
                current_event={"kind": "self_activity_state"},
                world_model_state={"presence_residue": 0.42},
            )

        self.assertEqual(action["action_target"], "wait_and_recheck")
        self.assertEqual(action["interaction_mode"], "deferred_watch")
        self.assertEqual(action["timing_window_min"], 30)
        self.assertEqual(plan["kind"], "deferred_checkin")
        self.assertEqual(plan["scheduled_after_min"], 30)
        mock_derive.assert_not_called()

    def test_resolve_behavior_payloads_derives_plan_from_frozen_action_before_live_plan(self):
        live_action = {
            "action_target": "hold_own_rhythm",
            "interaction_mode": "self_activity_hold",
            "primary_motive": "preserve_self_rhythm",
            "goal_frame": "stale live action should not win",
        }
        live_plan = {
            "kind": "self_activity_continue",
            "target": "self",
            "trigger_family": "self_activity",
            "scheduled_after_min": 45,
            "legacy_hint": "stale-live-plan",
        }
        reconsolidation_snapshot = {
            "behavior_action": {
                "action_target": "wait_and_recheck",
                "interaction_mode": "deferred_watch",
                "primary_motive": "honor_continuity",
                "motive_tension": "contact_without_pressure",
                "goal_frame": "顺着前面的惦记等更自然的时候再接回来。",
                "deferred_action_family": "life_window",
                "timing_window_min": 30,
                "relationship_weather": "warm_residue",
            }
        }

        with patch(
            "amadeus_thread0.runtime.final_state._behavior_plan_from_action",
            return_value={
                "kind": "deferred_checkin",
                "target": "counterpart",
                "trigger_family": "life_window",
                "scheduled_after_min": 30,
                "primary_motive": "honor_continuity",
            },
        ) as mock_derive:
            action, plan = resolve_behavior_payloads(
                behavior_action=live_action,
                behavior_plan=live_plan,
                reconsolidation_snapshot=reconsolidation_snapshot,
                current_event={"kind": "self_activity_state"},
                world_model_state={"presence_residue": 0.42},
            )

        self.assertEqual(action["action_target"], "wait_and_recheck")
        self.assertEqual(plan["kind"], "deferred_checkin")
        self.assertEqual(plan["trigger_family"], "life_window")
        self.assertEqual(plan["scheduled_after_min"], 30)
        self.assertNotIn("legacy_hint", plan)
        mock_derive.assert_called_once()

    def test_resolve_behavior_payloads_preserves_frozen_behavior_action_embodied_context_only_signal(self):
        action, plan = resolve_behavior_payloads(
            behavior_action={},
            behavior_plan={},
            reconsolidation_snapshot={
                "behavior_action": {
                    "embodied_context": {
                        "kind": "access_request_pending",
                        "summary": "这一步还在等审批。",
                        "requested_access": ["workspace_write"],
                        "requested_help": True,
                        "primary_status": "awaiting_approval",
                    }
                }
            },
        )

        embodied = action.get("embodied_context") if isinstance(action.get("embodied_context"), dict) else {}
        self.assertEqual(embodied.get("kind"), "access_request_pending")
        self.assertEqual(embodied.get("requested_access"), ["workspace_write"])
        self.assertTrue(bool(embodied.get("requested_help")))
        self.assertEqual(embodied.get("primary_status"), "awaiting_approval")
        self.assertEqual(plan, {})

    def test_resolve_behavior_payloads_preserves_frozen_behavior_plan_embodied_context_only_signal(self):
        action, plan = resolve_behavior_payloads(
            behavior_action={},
            behavior_plan={},
            reconsolidation_snapshot={
                "behavior_plan": {
                    "embodied_context": {
                        "kind": "environmental_friction",
                        "summary": "浏览器会话还没准备好。",
                        "missing_access": ["browser_session"],
                        "environmental_friction": True,
                    }
                }
            },
        )

        embodied = plan.get("embodied_context") if isinstance(plan.get("embodied_context"), dict) else {}
        self.assertEqual(embodied.get("kind"), "environmental_friction")
        self.assertEqual(embodied.get("missing_access"), ["browser_session"])
        self.assertTrue(bool(embodied.get("environmental_friction")))
        self.assertEqual(action, {})

    def test_resolve_interaction_carryover_prefers_frozen_reconsolidation_snapshot(self):
        live_carryover = {
            "source": "live",
            "strength": 0.18,
            "carryover_mode": "fading_residue",
            "relationship_weather": "thin_residue",
        }
        reconsolidation_snapshot = {
            "interaction_carryover": {
                "source": "reconsolidation",
                "strength": 0.53,
                "carryover_mode": "own_rhythm",
                "relationship_weather": "warm_residue",
                "note": "final carryover should win",
            }
        }

        carryover = resolve_interaction_carryover(
            interaction_carryover=live_carryover,
            reconsolidation_snapshot=reconsolidation_snapshot,
        )

        self.assertEqual(carryover["source"], "reconsolidation")
        self.assertEqual(carryover["carryover_mode"], "own_rhythm")
        self.assertEqual(carryover["strength"], 0.53)
        self.assertEqual(carryover["relationship_weather"], "warm_residue")

    def test_resolve_interaction_carryover_preserves_embodied_context_signal(self):
        carryover = resolve_interaction_carryover(
            interaction_carryover={},
            reconsolidation_snapshot={
                "interaction_carryover": {
                    "embodied_context": {
                        "kind": "access_request_pending",
                        "summary": "她把窗口推进到了需要审批的位置。",
                        "requested_access": ["workspace_write", "human_approval"],
                        "requested_help": True,
                        "primary_status": "awaiting_approval",
                    }
                }
            },
        )

        embodied = carryover.get("embodied_context") if isinstance(carryover.get("embodied_context"), dict) else {}
        self.assertEqual(embodied.get("kind"), "access_request_pending")
        self.assertEqual(embodied.get("requested_access"), ["workspace_write", "human_approval"])
        self.assertTrue(bool(embodied.get("requested_help")))
        self.assertEqual(embodied.get("primary_status"), "awaiting_approval")

    def test_resolve_agenda_lifecycle_residue_preserves_embodied_context_signal(self):
        residue = resolve_agenda_lifecycle_residue(
            agenda_lifecycle_residue={},
            reconsolidation_snapshot={
                "agenda_lifecycle_consequence": {
                    "kind": "released_to_self_activity",
                    "summary": "她把注意力收回到了自己的节奏里。",
                    "carryover_mode": "own_rhythm",
                    "carryover_strength": 0.58,
                    "embodied_context": {
                        "kind": "access_request_pending",
                        "summary": "她把窗口推进到了需要审批的位置。",
                        "requested_access": ["workspace_write", "human_approval"],
                        "requested_help": True,
                        "primary_status": "awaiting_approval",
                    },
                }
            },
        )

        self.assertEqual(residue["kind"], "released_to_self_activity")
        embodied = residue.get("embodied_context") if isinstance(residue.get("embodied_context"), dict) else {}
        self.assertEqual(embodied.get("kind"), "access_request_pending")
        self.assertEqual(embodied.get("requested_access"), ["workspace_write", "human_approval"])
        self.assertTrue(bool(embodied.get("requested_help")))
        self.assertEqual(embodied.get("primary_status"), "awaiting_approval")

    def test_resolve_counterpart_assessment_normalizes_extended_profile_axes(self):
        assessment = resolve_counterpart_assessment(
            counterpart_assessment={
                "stance": "watchful",
                "scene": "repair_attempt",
                "respect_level": 0.63,
                "reciprocity": 0.58,
                "boundary_pressure": 0.24,
                "reliability_read": 0.71,
            }
        )

        profile = assessment.get("assessment_profile") if isinstance(assessment.get("assessment_profile"), dict) else {}
        self.assertEqual(assessment["scene"], "repair_attempt")
        self.assertEqual(profile["dominant_scene_signal"], "repair")
        self.assertGreaterEqual(profile["repairability"], 0.6)
        self.assertGreaterEqual(profile["predictability"], 0.5)
        self.assertGreaterEqual(profile["safety_read"], 0.5)
        self.assertGreaterEqual(profile["closeness_read"], 0.45)

    def test_resolve_counterpart_assessment_prefers_frozen_snapshot_and_preserves_normalized_profile(self):
        assessment = resolve_counterpart_assessment(
            counterpart_assessment={"stance": "open", "scene": "care_bid"},
            reconsolidation_snapshot={
                "counterpart": {
                    "summary": "她会先把这次靠近当成一次谨慎但可修复的重新接近。",
                    "stance": "watchful",
                    "scene": "repair_attempt",
                    "respect_level": 0.63,
                    "reciprocity": 0.58,
                    "boundary_pressure": 0.24,
                    "reliability_read": 0.71,
                }
            },
        )

        profile = assessment.get("assessment_profile") if isinstance(assessment.get("assessment_profile"), dict) else {}
        self.assertEqual(assessment["scene"], "repair_attempt")
        self.assertEqual(profile["dominant_scene_signal"], "repair")
        self.assertIn("repairability", profile)
        self.assertIn("dependency_risk", profile)

    def test_resolve_digital_body_consequence_prefers_frozen_reconsolidation_snapshot(self):
        consequence = resolve_digital_body_consequence(
            digital_body_state={
                "active_surface": "tooling",
                "access_state": {
                    "mode": "approval_pending",
                    "requestable_access": ["workspace_write"],
                    "pending_approval_count": 1,
                },
                "resource_state": {"pending_approval_count": 1},
            },
            action_packets=[
                {
                    "proposal_id": "ap-live-1",
                    "origin": "counterpart_request",
                    "intent": "write_file",
                    "status": "awaiting_approval",
                    "risk": "external_mutation",
                    "requires_approval": True,
                }
            ],
            reconsolidation_snapshot={
                "digital_body_consequence": {
                    "kind": "environmental_friction",
                    "summary": "这轮真正留下的是环境阻力，不是待审批入口。",
                    "environmental_friction": True,
                    "missing_access": ["cookies"],
                    "block_reason": "browser session missing",
                }
            },
        )

        self.assertEqual(consequence["kind"], "environmental_friction")
        self.assertEqual(consequence["summary"], "这轮真正留下的是环境阻力，不是待审批入口。")
        self.assertTrue(bool(consequence["environmental_friction"]))
        self.assertEqual(consequence["missing_access"], ["cookies"])
        self.assertEqual(consequence["block_reason"], "browser session missing")

    def test_resolve_digital_body_consequence_derives_pending_access_from_live_body_state(self):
        consequence = resolve_digital_body_consequence(
            digital_body_state={
                "active_surface": "approval_gate",
                "world_surfaces": ["filesystem", "network"],
                "active_tools": ["write_file"],
                "access_state": {
                    "mode": "approval_pending",
                    "requestable_access": ["workspace_write"],
                    "pending_approval_count": 1,
                    "block_reason": "waiting for approval",
                },
                "resource_state": {"pending_approval_count": 1},
            },
            action_packets=[
                {
                    "proposal_id": "ap-live-2",
                    "origin": "counterpart_request",
                    "intent": "write_file",
                    "status": "awaiting_approval",
                    "risk": "external_mutation",
                    "requires_approval": True,
                    "tool_name": "write_file",
                }
            ],
        )

        self.assertEqual(consequence["kind"], "access_request_pending")
        self.assertIn("human_approval", consequence["requested_access"])
        self.assertEqual(consequence["primary_proposal_id"], "ap-live-2")
        self.assertEqual(consequence["primary_status"], "awaiting_approval")
        self.assertEqual(consequence["primary_tool_name"], "write_file")
        self.assertTrue(bool(consequence["requested_help"]))

    def test_resolve_digital_body_consequence_derives_cooldown_from_live_body_state(self):
        consequence = resolve_digital_body_consequence(
            digital_body_state={
                "active_surface": "cooldown_gate",
                "world_surfaces": ["network"],
                "access_state": {
                    "mode": "cooldown",
                    "quota_state": "exhausted",
                    "retry_after_s": 300,
                    "cooldown_scope": "provider",
                    "block_reason": "provider rate limited",
                    "requestable_access": ["api_quota"],
                    "missing_access": ["api_quota"],
                },
                "resource_state": {},
            },
            action_packets=[],
        )

        self.assertEqual(consequence["kind"], "environmental_friction")
        self.assertEqual(consequence["retry_after_s"], 300)
        self.assertEqual(consequence["cooldown_scope"], "provider")
        self.assertTrue(bool(consequence["environmental_friction"]))
        self.assertIn("300秒后", consequence["summary"])
        self.assertEqual(consequence["block_reason"], "provider rate limited")

    def test_resolve_digital_body_consequence_derives_session_expiry_recovery_from_live_body_state(self):
        consequence = resolve_digital_body_consequence(
            digital_body_state={
                "active_surface": "dialogue",
                "world_surfaces": ["browser"],
                "access_state": {
                    "mode": "tool_enabled",
                    "browser_session": "expired",
                    "account_state": "logged_in",
                    "cookie_state": "present",
                    "session_continuity": "expired",
                    "session_recovery_mode": "refresh_session",
                },
                "resource_state": {},
            },
            action_packets=[],
        )

        self.assertEqual(consequence["kind"], "environmental_friction")
        self.assertEqual(consequence["session_continuity"], "expired")
        self.assertEqual(consequence["session_recovery_mode"], "refresh_session")
        self.assertTrue(bool(consequence["environmental_friction"]))
        self.assertIn("刷新", consequence["summary"])

    def test_resolve_digital_body_consequence_derives_access_request_resolved_from_live_body_state(self):
        consequence = resolve_digital_body_consequence(
            digital_body_state={
                "active_surface": "tooling",
                "world_surfaces": ["network"],
                "access_state": {
                    "mode": "tool_enabled",
                    "api_key_state": "present",
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
                },
                "resource_state": {"completed_packet_count": 1},
            },
            action_packets=[
                {
                    "proposal_id": "ap-live-arrival-1",
                    "origin": "counterpart_request",
                    "intent": "access:request_help",
                    "status": "completed",
                    "risk": "external_mutation",
                    "requires_approval": False,
                    "result_summary": "模型入口已经补回来了，这条路径现在可以继续。",
                    "writeback_ready": True,
                    "selected_access_proposal": {
                        "target": "api_key",
                        "mode": "operator_provide_api_key",
                        "summary": "先补一个可用 API key。",
                        "operator_action": "填入一个可用 key。",
                        "grants": ["api_key"],
                        "requires_operator": True,
                    },
                }
            ],
        )

        self.assertEqual(consequence["kind"], "access_request_resolved")
        self.assertEqual(consequence["primary_status"], "completed")
        self.assertEqual(consequence["selected_access_proposal"]["target"], "api_key")
        self.assertIn("可以继续", consequence["summary"])

    def test_resolve_digital_body_consequence_derives_workspace_access_resolved_from_live_body_state(self):
        consequence = resolve_digital_body_consequence(
            digital_body_state={
                "active_surface": "tooling",
                "world_surfaces": ["filesystem"],
                "access_state": {
                    "mode": "tool_enabled",
                    "filesystem_state": "writable",
                    "access_acquire_proposals": [
                        {
                            "target": "filesystem",
                            "mode": "operator_create_workspace",
                            "path_kind": "create_new",
                            "summary": "先新建一个可写工作区。",
                            "operator_action": "新建一个可写工作区。",
                            "grants": ["filesystem", "workspace_write"],
                            "requires_operator": True,
                        }
                    ],
                    "selected_access_proposal": {
                        "target": "filesystem",
                        "mode": "operator_create_workspace",
                        "path_kind": "create_new",
                        "summary": "先新建一个可写工作区。",
                        "operator_action": "新建一个可写工作区。",
                        "grants": ["filesystem", "workspace_write"],
                        "requires_operator": True,
                    },
                },
                "resource_state": {
                    "completed_packet_count": 1,
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "workspace",
                    "active_artifact_ref": "E:/runtime/workspaces/lab-notes",
                    "active_artifact_label": "lab-notes",
                },
            },
            action_packets=[
                {
                    "proposal_id": "ap-workspace-create-1",
                    "origin": "counterpart_request",
                    "intent": "access:request_help",
                    "status": "completed",
                    "risk": "external_mutation",
                    "requires_approval": True,
                    "tool_name": "create_workspace_access",
                    "writeback_ready": True,
                    "selected_access_proposal": {
                        "target": "filesystem",
                        "mode": "operator_create_workspace",
                        "path_kind": "create_new",
                        "summary": "先新建一个可写工作区。",
                        "operator_action": "新建一个可写工作区。",
                        "grants": ["filesystem", "workspace_write"],
                        "requires_operator": True,
                    },
                }
            ],
        )

        self.assertEqual(consequence["kind"], "workspace_access_resolved")
        self.assertEqual(consequence["primary_tool_name"], "create_workspace_access")
        self.assertEqual(consequence["active_artifact_kind"], "workspace")
        self.assertEqual(consequence["active_artifact_label"], "lab-notes")
        self.assertIn("lab-notes", consequence["summary"])

    def test_resolve_digital_body_consequence_derives_workspace_file_updated_from_live_body_state(self):
        consequence = resolve_digital_body_consequence(
            digital_body_state={
                "active_surface": "tooling",
                "world_surfaces": ["filesystem"],
                "access_state": {
                    "mode": "tool_enabled",
                    "filesystem_state": "writable",
                },
                "resource_state": {
                    "completed_packet_count": 1,
                    "external_tool_count": 1,
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "file",
                    "active_artifact_ref": "E:/runtime/workspaces/lab-notes/notes/today.md",
                    "active_artifact_label": "today.md",
                },
            },
            action_packets=[
                {
                    "proposal_id": "ap-file-write-1",
                    "origin": "counterpart_request",
                    "intent": "artifact:write_file",
                    "status": "completed",
                    "risk": "external_mutation",
                    "requires_approval": True,
                    "tool_name": "write_workspace_file",
                    "result_summary": "已把内容写入 today.md，这条文件工作面现在接上了。",
                    "writeback_ready": True,
                    "artifact_context": {
                        "carrier": "filesystem",
                        "artifact_kind": "file",
                        "artifact_ref": "E:/runtime/workspaces/lab-notes/notes/today.md",
                        "artifact_label": "today.md",
                        "reacquisition_mode": "reopen_file",
                        "exists": True,
                    },
                }
            ],
        )

        self.assertEqual(consequence["kind"], "workspace_file_updated")
        self.assertEqual(consequence["primary_tool_name"], "write_workspace_file")
        self.assertEqual(consequence["artifact_mutation_mode"], "write")
        self.assertEqual(consequence["active_artifact_kind"], "file")
        self.assertEqual(consequence["active_artifact_label"], "today.md")
        self.assertTrue(bool(consequence["procedural_growth"]))
        self.assertIn("today.md", consequence["summary"])

    def test_resolve_digital_body_consequence_derives_workspace_path_inspected_from_live_body_state(self):
        consequence = resolve_digital_body_consequence(
            digital_body_state={
                "active_surface": "tooling",
                "world_surfaces": ["filesystem"],
                "access_state": {
                    "mode": "tool_enabled",
                    "filesystem_state": "writable",
                },
                "resource_state": {
                    "completed_packet_count": 1,
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "file",
                    "active_artifact_ref": "E:/runtime/workspaces/lab-notes/notes/today.md",
                    "active_artifact_label": "today.md",
                },
            },
            action_packets=[
                {
                    "proposal_id": "ap-inspect-file-1",
                    "origin": "counterpart_request",
                    "intent": "artifact:inspect_path",
                    "status": "completed",
                    "risk": "read",
                    "requires_approval": False,
                    "tool_name": "inspect_workspace_path",
                    "result_summary": "已查看文件 today.md，当前内容已经重新接回工作面。",
                    "writeback_ready": True,
                    "artifact_context": {
                        "carrier": "filesystem",
                        "artifact_kind": "file",
                        "artifact_ref": "E:/runtime/workspaces/lab-notes/notes/today.md",
                        "artifact_label": "today.md",
                        "reacquisition_mode": "reopen_file",
                        "exists": True,
                    },
                }
            ],
        )

        self.assertEqual(consequence["kind"], "workspace_path_inspected")
        self.assertEqual(consequence["primary_tool_name"], "inspect_workspace_path")
        self.assertEqual(consequence["active_artifact_kind"], "file")
        self.assertEqual(consequence["active_artifact_label"], "today.md")
        self.assertFalse(bool(consequence["procedural_growth"]))
        self.assertIn("today.md", consequence["summary"])

    def test_resolve_digital_body_consequence_derives_artifact_reacquired_from_source_ref_surface(self):
        consequence = resolve_digital_body_consequence(
            digital_body_state={
                "active_surface": "tooling",
                "world_surfaces": ["browser", "source_ref"],
                "access_state": {
                    "mode": "native_only",
                    "network_access": "enabled",
                },
                "resource_state": {
                    "completed_packet_count": 1,
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "search_result",
                    "active_artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "active_artifact_label": "Persistence",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [17],
                    "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "artifact_source_query": "langgraph persistence checkpointer thread",
                    "artifact_source_title": "Persistence",
                    "artifact_source_tool_name": "search_web",
                },
            },
            action_packets=[
                {
                    "proposal_id": "ap-source-reattach-1",
                    "origin": "counterpart_request",
                    "intent": "artifact:rerun_search",
                    "status": "completed",
                    "risk": "read",
                    "requires_approval": False,
                    "tool_name": "reacquire_artifact",
                    "result_summary": "已重新接回检索结果 Persistence。",
                    "writeback_ready": True,
                    "artifact_context": {
                        "carrier": "source_ref",
                        "artifact_kind": "search_result",
                        "artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                        "artifact_label": "Persistence",
                        "reacquisition_mode": "rerun_search",
                        "source_ref_ids": [17],
                        "source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                        "source_query": "langgraph persistence checkpointer thread",
                        "source_title": "Persistence",
                        "source_tool_name": "search_web",
                    },
                }
            ],
        )

        self.assertEqual(consequence["kind"], "artifact_reacquired")
        self.assertEqual(consequence["primary_tool_name"], "reacquire_artifact")
        self.assertEqual(consequence["active_artifact_kind"], "search_result")
        self.assertEqual(consequence["artifact_carrier"], "source_ref")
        self.assertEqual(consequence["artifact_source_ref_ids"], [17])
        self.assertEqual(consequence["artifact_source_tool_name"], "search_web")
        self.assertFalse(bool(consequence["procedural_growth"]))
        self.assertIn("Persistence", consequence["summary"])

    def test_resolve_digital_body_consequence_derives_access_state_refreshed_when_refresh_packet_stabilizes_runtime(self):
        consequence = resolve_digital_body_consequence(
            digital_body_state={
                "active_surface": "tooling",
                "world_surfaces": ["network", "filesystem"],
                "access_state": {
                    "mode": "tool_enabled",
                    "api_key_state": "present",
                    "filesystem_state": "writable",
                    "network_access": "enabled",
                    "session_continuity": "stable",
                    "session_recovery_mode": "refresh_session",
                },
                "resource_state": {
                    "completed_packet_count": 1,
                },
            },
            action_packets=[
                {
                    "proposal_id": "ap-refresh-access-1",
                    "origin": "motive_goal",
                    "intent": "access:refresh_state",
                    "status": "completed",
                    "risk": "read",
                    "requires_approval": False,
                    "tool_name": "refresh_access_state",
                    "result_summary": "已重新检查当前入口状态，眼下这条路径是稳定的。",
                    "writeback_ready": True,
                }
            ],
        )

        self.assertEqual(consequence["kind"], "access_state_refreshed")
        self.assertEqual(consequence["primary_tool_name"], "refresh_access_state")
        self.assertEqual(consequence["access_mode"], "tool_enabled")
        self.assertEqual(consequence["session_continuity"], "stable")
        self.assertFalse(bool(consequence["procedural_growth"]))
        self.assertIn("稳定", consequence["summary"])

    def test_resolve_digital_body_consequence_derives_replace_mutation_mode_from_live_body_state(self):
        consequence = resolve_digital_body_consequence(
            digital_body_state={
                "active_surface": "tooling",
                "world_surfaces": ["filesystem"],
                "access_state": {
                    "mode": "tool_enabled",
                    "filesystem_state": "writable",
                },
                "resource_state": {
                    "completed_packet_count": 1,
                    "external_tool_count": 1,
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "file",
                    "active_artifact_ref": "E:/runtime/workspaces/lab-notes/notes/today.md",
                    "active_artifact_label": "today.md",
                },
            },
            action_packets=[
                {
                    "proposal_id": "ap-file-replace-1",
                    "origin": "counterpart_request",
                    "intent": "artifact:replace_text",
                    "status": "completed",
                    "risk": "external_mutation",
                    "requires_approval": True,
                    "tool_name": "replace_workspace_text",
                    "result_summary": "已在 today.md 里精确替换 1 处文本，这条文件工作面现在接上了。",
                    "writeback_ready": True,
                    "artifact_context": {
                        "carrier": "filesystem",
                        "artifact_kind": "file",
                        "artifact_ref": "E:/runtime/workspaces/lab-notes/notes/today.md",
                        "artifact_label": "today.md",
                        "reacquisition_mode": "reopen_file",
                        "exists": True,
                    },
                }
            ],
        )

        self.assertEqual(consequence["kind"], "workspace_file_updated")
        self.assertEqual(consequence["primary_tool_name"], "replace_workspace_text")
        self.assertEqual(consequence["artifact_mutation_mode"], "replace")
        self.assertEqual(consequence["active_artifact_kind"], "file")
        self.assertTrue(bool(consequence["procedural_growth"]))

    def test_resolve_digital_body_consequence_derives_replace_mode_for_workspace_line_replace(self):
        consequence = resolve_digital_body_consequence(
            digital_body_state={
                "active_surface": "tooling",
                "world_surfaces": ["filesystem"],
                "access_state": {
                    "mode": "tool_enabled",
                    "filesystem_state": "writable",
                },
                "resource_state": {
                    "completed_packet_count": 1,
                    "external_tool_count": 1,
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "file",
                    "active_artifact_ref": "E:/runtime/workspaces/lab-notes/notes/today.md",
                    "active_artifact_label": "today.md",
                },
            },
            action_packets=[
                {
                    "proposal_id": "ap-file-lines-1",
                    "origin": "counterpart_request",
                    "intent": "artifact:replace_lines",
                    "status": "completed",
                    "risk": "external_mutation",
                    "requires_approval": True,
                    "tool_name": "replace_workspace_lines",
                    "result_summary": "已在 today.md 里替换第 2 行，这条文件工作面现在接上了。",
                    "writeback_ready": True,
                    "artifact_context": {
                        "carrier": "filesystem",
                        "artifact_kind": "file",
                        "artifact_ref": "E:/runtime/workspaces/lab-notes/notes/today.md",
                        "artifact_label": "today.md",
                        "reacquisition_mode": "reopen_file",
                        "exists": True,
                    },
                }
            ],
        )

        self.assertEqual(consequence["kind"], "workspace_file_updated")
        self.assertEqual(consequence["primary_tool_name"], "replace_workspace_lines")
        self.assertEqual(consequence["artifact_mutation_mode"], "replace")
        self.assertEqual(consequence["active_artifact_kind"], "file")
        self.assertTrue(bool(consequence["procedural_growth"]))

    def test_resolve_digital_body_consequence_derives_detached_artifact_reacquisition_from_live_body_state(self):
        consequence = resolve_digital_body_consequence(
            digital_body_state={
                "active_surface": "dialogue",
                "world_surfaces": ["filesystem"],
                "access_state": {
                    "mode": "native_only",
                },
                "resource_state": {
                    "artifact_continuity": "detached",
                    "active_artifact_kind": "file",
                    "active_artifact_ref": "notes/plan.md",
                    "active_artifact_label": "plan.md",
                    "artifact_age_s": 7200,
                    "artifact_reacquisition_mode": "reopen_file",
                },
            },
            action_packets=[],
        )

        self.assertEqual(consequence["kind"], "environmental_friction")
        self.assertEqual(consequence["artifact_continuity"], "detached")
        self.assertEqual(consequence["active_artifact_kind"], "file")
        self.assertEqual(consequence["active_artifact_label"], "plan.md")
        self.assertEqual(consequence["artifact_reacquisition_mode"], "reopen_file")
        self.assertIn("重新打开", consequence["summary"])

    def test_resolve_digital_body_consequence_preserves_compact_artifact_identity(self):
        consequence = resolve_digital_body_consequence(
            digital_body_state={
                "active_surface": "approval_gate",
                "access_state": {
                    "mode": "approval_pending",
                    "requestable_access": ["human_approval"],
                    "pending_approval_count": 1,
                },
                "resource_state": {},
            },
            action_packets=[
                {
                    "proposal_id": "ap-source-1",
                    "origin": "counterpart_request",
                    "intent": "artifact:rerun_search",
                    "status": "awaiting_approval",
                    "risk": "read",
                    "requires_approval": False,
                    "artifact_context": {
                        "carrier": "source_ref",
                        "artifact_kind": "search_result",
                        "artifact_label": "Persistence",
                        "reacquisition_mode": "rerun_search",
                        "source_ref_ids": [17],
                        "source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                        "source_query": "langgraph persistence checkpointer thread",
                        "source_title": "Persistence",
                        "source_tool_name": "search_web",
                    },
                }
            ],
        )

        self.assertEqual(consequence["artifact_carrier"], "source_ref")
        self.assertEqual(consequence["artifact_source_ref_ids"], [17])
        self.assertIn("docs.langchain.com", consequence["artifact_source_url"])
        self.assertEqual(consequence["artifact_source_title"], "Persistence")
        self.assertEqual(consequence["artifact_source_tool_name"], "search_web")

    def test_resolve_digital_body_consequence_does_not_materialize_expiring_session_only(self):
        consequence = resolve_digital_body_consequence(
            digital_body_state={
                "active_surface": "dialogue",
                "access_state": {
                    "mode": "native_only",
                    "browser_session": "present",
                    "account_state": "logged_in",
                    "cookie_state": "present",
                    "session_continuity": "expiring",
                    "session_expires_in_s": 600,
                    "session_recovery_mode": "refresh_session",
                },
                "resource_state": {},
            },
            action_packets=[],
        )

        self.assertEqual(consequence, {})

    def test_resolve_digital_body_consequence_does_not_materialize_stale_artifact_only(self):
        consequence = resolve_digital_body_consequence(
            digital_body_state={
                "active_surface": "dialogue",
                "access_state": {
                    "mode": "native_only",
                },
                "resource_state": {
                    "artifact_continuity": "stale",
                    "active_artifact_kind": "page",
                    "active_artifact_label": "lab-notes",
                    "artifact_age_s": 600,
                    "artifact_reacquisition_mode": "reopen_page",
                },
            },
            action_packets=[],
        )

        self.assertEqual(consequence, {})


if __name__ == "__main__":
    unittest.main()
