from __future__ import annotations

import unittest

from amadeus_thread0.graph_parts.digital_body_runtime import (
    derive_digital_body_state,
    derive_session_lifecycle,
)


class DigitalBodyRuntimeTests(unittest.TestCase):
    def test_derive_session_lifecycle_distinguishes_expiring_and_recovery_paths(self):
        expiring = derive_session_lifecycle(
            browser_session="present",
            account_state="logged_in",
            cookie_state="present",
            session_expires_in_s=600,
        )
        self.assertEqual(expiring["session_continuity"], "expiring")
        self.assertEqual(expiring["session_expires_in_s"], 600)
        self.assertEqual(expiring["session_recovery_mode"], "refresh_session")

        restore = derive_session_lifecycle(
            browser_session="missing",
            account_state="logged_in",
            cookie_state="expired",
        )
        self.assertEqual(restore["session_continuity"], "expired")
        self.assertEqual(restore["session_recovery_mode"], "restore_cookies")

        relogin = derive_session_lifecycle(
            browser_session="missing",
            account_state="logged_out",
            cookie_state="missing",
        )
        self.assertEqual(relogin["session_continuity"], "missing")
        self.assertEqual(relogin["session_recovery_mode"], "relogin")

    def test_derive_digital_body_state_surfaces_access_and_tooling(self):
        body = derive_digital_body_state(
            current_event={
                "kind": "user_utterance",
                "perception": {"channel": "chat", "modality": "text"},
            },
            behavior_queue=[{"agenda_id": "q1"}],
            action_packets=[
                {
                    "proposal_id": "ap-1",
                    "origin": "motive_goal",
                    "intent": "tool:write_diary",
                    "status": "awaiting_approval",
                    "risk": "external_mutation",
                    "requires_approval": True,
                    "tool_name": "write_diary",
                    "capability_steps": [],
                }
            ],
            toolset_unlocks={"search_web": 1, "workspace_fs": 0},
            autonomy_block_reason="",
        )

        self.assertEqual(body["active_surface"], "approval_gate")
        self.assertIn("chat", body["perception_channels"])
        self.assertIn("language", body["action_channels"])
        self.assertIn("approval_gate", body["action_channels"])
        self.assertIn("tooling", body["action_channels"])
        self.assertEqual(body["access_state"]["mode"], "approval_pending")
        self.assertEqual(body["access_state"]["pending_approval_count"], 1)
        self.assertTrue(body["access_state"]["external_mutation_pending"])
        self.assertIn("human_approval_required", body["access_state"]["conditions"])
        self.assertIn("external_mutation_gated", body["access_state"]["conditions"])
        self.assertEqual(body["access_state"]["permission_state"]["pending_approval_count"], 1)
        self.assertTrue(body["access_state"]["permission_state"]["external_mutation_pending"])
        self.assertEqual(body["available_toolsets"], ["search_web"])
        self.assertEqual(body["active_tools"], ["write_diary"])
        self.assertEqual(body["resource_state"]["behavior_queue_depth"], 1)
        self.assertEqual(body["resource_state"]["action_packet_count"], 1)

    def test_derive_digital_body_state_surfaces_world_conditions_and_requestable_access(self):
        body = derive_digital_body_state(
            current_event={
                "kind": "user_utterance",
                "perception": {"channel": "chat", "modality": "text"},
            },
            behavior_queue=[],
            action_packets=[],
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context={
                "thread_id": "thread-a",
                "digital_body_hints": {
                    "world_surfaces": ["browser", "filesystem"],
                    "browser_session": "missing",
                    "account_state": "missing",
                    "cookie_state": "missing",
                    "api_key_state": "missing",
                    "quota_state": "exhausted",
                    "filesystem_state": "read_only",
                    "sandbox_mode": "restricted",
                    "network_access": "restricted",
                    "missing_access": ["browser_login"],
                    "requestable_access": ["workspace_write"],
                    "constraints": ["workspace_scoped"],
                },
            },
            last_external_tools=["search_langchain_docs"],
        )

        self.assertEqual(body["access_state"]["mode"], "limited")
        self.assertIn("browser", body["world_surfaces"])
        self.assertIn("filesystem", body["world_surfaces"])
        self.assertIn("network", body["world_surfaces"])
        self.assertIn("sandbox", body["world_surfaces"])
        self.assertEqual(body["access_state"]["browser_session"], "missing")
        self.assertEqual(body["access_state"]["account_state"], "missing")
        self.assertEqual(body["access_state"]["cookie_state"], "missing")
        self.assertEqual(body["access_state"]["api_key_state"], "missing")
        self.assertEqual(body["access_state"]["quota_state"], "exhausted")
        self.assertEqual(body["access_state"]["filesystem_state"], "read_only")
        self.assertEqual(body["access_state"]["sandbox_mode"], "restricted")
        self.assertEqual(body["access_state"]["network_access"], "restricted")
        self.assertEqual(body["access_state"]["account_state_detail"]["login_state"], "missing")
        self.assertEqual(body["access_state"]["account_state_detail"]["cookie_state"], "missing")
        self.assertEqual(body["access_state"]["quota_state_detail"]["provider_state"], "exhausted")
        self.assertEqual(body["access_state"]["quota_state_detail"]["cooldown_scope"], "")
        self.assertEqual(body["access_state"]["permission_state"]["approval_state"], "open")
        self.assertEqual(body["access_state"]["sandbox_state"]["availability"], "restricted")
        self.assertEqual(body["access_state"]["sandbox_state"]["execution_policy"], "approval_required")
        self.assertIn("browser_login", body["access_state"]["missing_access"])
        self.assertIn("browser_session", body["access_state"]["missing_access"])
        self.assertIn("account_login", body["access_state"]["missing_access"])
        self.assertIn("cookies", body["access_state"]["missing_access"])
        self.assertIn("api_key", body["access_state"]["missing_access"])
        self.assertIn("api_quota", body["access_state"]["missing_access"])
        self.assertIn("workspace_write", body["access_state"]["requestable_access"])
        self.assertIn("api_key", body["access_state"]["requestable_access"])
        self.assertIn("api_quota", body["access_state"]["requestable_access"])
        self.assertIn("network", body["access_state"]["requestable_access"])
        self.assertIn("api_key_missing", body["access_state"]["conditions"])
        self.assertIn("api_quota_exhausted", body["access_state"]["conditions"])
        self.assertIn("workspace_scoped", body["body_constraints"])
        self.assertEqual(body["resource_state"]["external_tool_count"], 1)

    def test_derive_digital_body_state_surfaces_session_lifecycle_and_refresh_path(self):
        body = derive_digital_body_state(
            current_event={
                "kind": "user_utterance",
                "perception": {"channel": "chat", "modality": "text"},
            },
            behavior_queue=[],
            action_packets=[],
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context={
                "thread_id": "thread-session",
                "digital_body_hints": {
                    "browser_session": "present",
                    "account_state": "logged_in",
                    "cookie_state": "present",
                    "session_expires_in_s": 600,
                },
            },
        )

        self.assertEqual(body["access_state"]["session_continuity"], "expiring")
        self.assertEqual(body["access_state"]["session_expires_in_s"], 600)
        self.assertEqual(body["access_state"]["session_recovery_mode"], "refresh_session")
        self.assertEqual(body["access_state"]["session_state"]["continuity"], "expiring")
        self.assertEqual(body["access_state"]["session_state"]["recovery_mode"], "refresh_session")
        self.assertIn("session_expiring_soon", body["access_state"]["conditions"])
        self.assertIn("session_refresh_available", body["access_state"]["conditions"])
        self.assertIn("session_refresh", body["access_state"]["requestable_access"])
        self.assertEqual(body["access_state"]["mode"], "native_only")

    def test_derive_digital_body_state_preserves_workspace_root_from_carried_embodied_context(self):
        body = derive_digital_body_state(
            current_event={
                "kind": "user_utterance",
                "perception": {"channel": "chat", "modality": "text"},
            },
            behavior_queue=[],
            action_packets=[],
            interaction_carryover={
                "source": "retrieved_digital_body_consequence",
                "carryover_mode": "task_window",
                "strength": 0.36,
                "embodied_context": {
                    "kind": "workspace_file_updated",
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "file",
                    "active_artifact_ref": "notes/today.md",
                    "active_artifact_label": "today.md",
                    "workspace_root": "E:/runtime/workspaces/lab-notes",
                    "artifact_mutation_mode": "append",
                    "procedural_growth": True,
                    "primary_status": "completed",
                },
            },
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context={"thread_id": "thread-workspace-carryover"},
        )

        self.assertEqual(body["resource_state"]["active_artifact_kind"], "file")
        self.assertEqual(body["resource_state"]["active_artifact_label"], "today.md")
        self.assertEqual(body["resource_state"]["workspace_root"], "E:/runtime/workspaces/lab-notes")
        self.assertEqual(body["resource_state"]["artifact_continuity"], "attached")

    def test_derive_digital_body_state_surfaces_multimodal_source_artifact(self):
        body = derive_digital_body_state(
            current_event={
                "kind": "multimodal_observation",
                "source": "multimodal_source",
                "perception": {
                    "channel": "image",
                    "modality": "image",
                    "digital_body_hints": {
                        "artifact_continuity": "attached",
                        "active_artifact_kind": "image",
                        "active_artifact_ref": "fixtures/panel.png",
                        "active_artifact_label": "panel.png",
                        "artifact_carrier": "multimodal_source",
                        "multimodal_source": {"source_id": "img-1", "status": "available"},
                    },
                },
            },
            behavior_queue=[],
            action_packets=[],
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context={"thread_id": "thread-mm"},
        )

        self.assertIn("image", body["perception_channels"])
        self.assertEqual(body["resource_state"]["artifact_carrier"], "multimodal_source")
        self.assertEqual(body["resource_state"]["active_artifact_kind"], "image")
        self.assertEqual(body["resource_state"]["active_artifact_label"], "panel.png")

    def test_derive_digital_body_state_surfaces_access_request_help_packet(self):
        body = derive_digital_body_state(
            current_event={
                "kind": "user_utterance",
                "perception": {"channel": "chat", "modality": "text"},
            },
            behavior_queue=[],
            action_packets=[
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
                            "target": "browser_session / account_login / cookies",
                            "status": "awaiting_approval",
                            "requires_approval": True,
                        }
                    ],
                }
            ],
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context={
                "thread_id": "thread-access-help",
                "digital_body_hints": {
                    "browser_session": "missing",
                    "account_state": "logged_out",
                    "cookie_state": "expired",
                    "missing_access": ["browser_session", "account_login", "cookies"],
                    "requestable_access": ["browser_session", "account_login", "cookies"],
                    "requested_help": True,
                },
            },
        )

        self.assertEqual(body["active_surface"], "approval_gate")
        self.assertEqual(body["access_state"]["mode"], "approval_pending")
        self.assertEqual(body["access_state"]["pending_approval_count"], 1)
        self.assertTrue(body["access_state"]["external_mutation_pending"])
        self.assertEqual(body["access_state"]["permission_state"]["approval_state"], "approval_pending")
        self.assertIn("browser_session", body["access_state"]["missing_access"])
        self.assertIn("account_login", body["access_state"]["requestable_access"])
        self.assertIn("human_approval", body["access_state"]["requestable_access"])
        self.assertIn("human_approval_required", body["access_state"]["conditions"])
        proposals = body["access_state"].get("access_acquire_proposals") if isinstance(body["access_state"].get("access_acquire_proposals"), list) else []
        selected = body["access_state"].get("selected_access_proposal") if isinstance(body["access_state"].get("selected_access_proposal"), dict) else {}
        self.assertTrue(proposals)
        self.assertEqual(proposals[0]["target"], "account_login")
        self.assertEqual(proposals[0]["mode"], "operator_login")
        self.assertEqual(selected.get("target"), "account_login")
        self.assertEqual(selected.get("mode"), "operator_login")
        self.assertTrue(any(item.get("mode") == "operator_register_account" and item.get("path_kind") == "create_new" for item in proposals))

    def test_derive_digital_body_state_preserves_selected_access_acquire_proposal(self):
        body = derive_digital_body_state(
            current_event={
                "kind": "user_utterance",
                "perception": {"channel": "chat", "modality": "text"},
            },
            behavior_queue=[],
            action_packets=[],
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context={
                "thread_id": "thread-access-plan",
                "digital_body_hints": {
                    "api_key_state": "missing",
                    "missing_access": ["api_key"],
                    "requestable_access": ["api_key"],
                    "selected_access_proposal": {
                        "target": "api_key",
                        "mode": "operator_provide_api_key",
                        "summary": "先补一个可用 API key。",
                        "operator_action": "填入一个可用 key。",
                        "grants": ["api_key"],
                        "requires_operator": True,
                    },
                },
            },
        )

        selected = body["access_state"].get("selected_access_proposal") if isinstance(body["access_state"].get("selected_access_proposal"), dict) else {}
        self.assertEqual(selected.get("target"), "api_key")
        self.assertEqual(selected.get("mode"), "operator_provide_api_key")
        self.assertIn("access_acquire_planned", body["access_state"]["conditions"])

    def test_derive_digital_body_state_honors_hint_pending_approval_for_selected_access_proposal(self):
        body = derive_digital_body_state(
            current_event={
                "kind": "user_utterance",
                "perception": {"channel": "chat", "modality": "text"},
            },
            behavior_queue=[],
            action_packets=[],
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context={
                "thread_id": "thread-access-hint-pending",
                "digital_body_hints": {
                    "mode": "approval_pending",
                    "pending_approval_count": 1,
                    "api_key_state": "missing",
                    "missing_access": ["api_key"],
                    "requestable_access": ["api_key", "human_approval"],
                    "selected_access_proposal": {
                        "target": "api_key",
                        "mode": "operator_provide_api_key",
                        "summary": "先补一个可用 API key。",
                        "operator_action": "填入一个可用 key。",
                        "grants": ["api_key"],
                        "requires_operator": True,
                    },
                },
            },
        )

        selected = body["access_state"].get("selected_access_proposal") if isinstance(body["access_state"].get("selected_access_proposal"), dict) else {}
        self.assertEqual(body["access_state"]["mode"], "approval_pending")
        self.assertEqual(body["access_state"]["pending_approval_count"], 1)
        self.assertEqual(selected.get("target"), "api_key")
        self.assertEqual(selected.get("mode"), "operator_provide_api_key")

    def test_derive_digital_body_state_honors_hint_block_reason_when_mode_blocked(self):
        body = derive_digital_body_state(
            current_event={
                "kind": "user_utterance",
                "perception": {"channel": "chat", "modality": "text"},
            },
            behavior_queue=[],
            action_packets=[],
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context={
                "thread_id": "thread-access-hint-blocked",
                "digital_body_hints": {
                    "mode": "blocked",
                    "block_reason": "browser session missing",
                    "missing_access": ["browser_session"],
                    "requestable_access": ["browser_session"],
                },
            },
        )

        self.assertEqual(body["access_state"]["mode"], "blocked")
        self.assertEqual(body["access_state"]["block_reason"], "browser session missing")
        self.assertIn("blocked_action_present", body["access_state"]["conditions"])

    def test_derive_digital_body_state_recovers_selected_access_proposal_from_carried_embodied_context(self):
        body = derive_digital_body_state(
            current_event={
                "kind": "user_utterance",
                "perception": {"channel": "chat", "modality": "text"},
            },
            behavior_queue=[],
            action_packets=[],
            toolset_unlocks={},
            autonomy_block_reason="",
            interaction_carryover={
                "embodied_context": {
                    "kind": "access_request_pending",
                    "requested_help": True,
                    "requested_access": ["api_key", "human_approval"],
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
            session_context={"thread_id": "thread-access-carry"},
        )

        selected = body["access_state"].get("selected_access_proposal") if isinstance(body["access_state"].get("selected_access_proposal"), dict) else {}
        proposals = body["access_state"].get("access_acquire_proposals") if isinstance(body["access_state"].get("access_acquire_proposals"), list) else []
        self.assertEqual(selected.get("target"), "api_key")
        self.assertEqual(selected.get("mode"), "operator_provide_api_key")
        self.assertTrue(proposals)
        self.assertIn("human_approval", body["access_state"]["requestable_access"])
        self.assertIn("access_acquire_planned", body["access_state"]["conditions"])

    def test_derive_digital_body_state_does_not_keep_planned_access_after_completed_arrival(self):
        body = derive_digital_body_state(
            current_event={
                "kind": "user_utterance",
                "perception": {"channel": "chat", "modality": "text"},
            },
            behavior_queue=[],
            action_packets=[
                {
                    "proposal_id": "ap-access-arrived-1",
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
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context={
                "thread_id": "thread-access-arrived",
                "digital_body_hints": {
                    "api_key_state": "present",
                    "primary_status": "completed",
                },
            },
        )

        self.assertNotIn("access_acquire_planned", body["access_state"]["conditions"])
        self.assertEqual(body["access_state"]["selected_access_proposal"]["target"], "api_key")

    def test_derive_digital_body_state_surfaces_partial_access_progress(self):
        proposal = {
            "target": "account_login",
            "mode": "operator_login",
            "summary": "先把账号登录补回来，这条外部入口才接得上后面。",
            "operator_action": "登录目标账号，或把现成登录态交给我。",
            "grants": ["account_login", "browser_session"],
            "requires_operator": True,
        }
        body = derive_digital_body_state(
            current_event={
                "kind": "user_utterance",
                "perception": {"channel": "chat", "modality": "text"},
            },
            behavior_queue=[],
            action_packets=[],
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context={
                "thread_id": "thread-access-partial",
                "digital_body_hints": {
                    "account_state": "logged_in",
                    "browser_session": "missing",
                    "missing_access": ["browser_session"],
                    "requestable_access": ["browser_session"],
                    "requested_help": False,
                    "primary_status": "approved",
                    "access_acquire_proposals": [proposal],
                    "selected_access_proposal": proposal,
                },
            },
        )

        selected = body["access_state"].get("selected_access_proposal") if isinstance(body["access_state"].get("selected_access_proposal"), dict) else {}
        proposals = body["access_state"].get("access_acquire_proposals") if isinstance(body["access_state"].get("access_acquire_proposals"), list) else []
        self.assertIn("access_acquire_planned", body["access_state"]["conditions"])
        self.assertEqual(selected.get("resolved_grants"), ["account_login"])
        self.assertEqual(selected.get("pending_grants"), ["browser_session"])
        self.assertEqual(selected.get("completion_ratio"), 0.5)
        self.assertEqual(proposals[0].get("resolved_grants"), ["account_login"])

    def test_derive_digital_body_state_surfaces_create_workspace_candidate(self):
        body = derive_digital_body_state(
            current_event={
                "kind": "user_utterance",
                "perception": {"channel": "chat", "modality": "text"},
            },
            behavior_queue=[],
            action_packets=[],
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context={
                "thread_id": "thread-create-workspace",
                "digital_body_hints": {
                    "filesystem_state": "missing",
                    "missing_access": ["filesystem", "workspace_write"],
                    "requestable_access": ["filesystem", "workspace_write"],
                },
            },
        )

        proposals = body["access_state"].get("access_acquire_proposals") if isinstance(body["access_state"].get("access_acquire_proposals"), list) else []
        self.assertTrue(any(item.get("mode") == "operator_create_workspace" and item.get("path_kind") == "create_new" for item in proposals))

    def test_derive_digital_body_state_surfaces_detached_artifact_and_reacquisition_path(self):
        body = derive_digital_body_state(
            current_event={
                "kind": "user_utterance",
                "perception": {"channel": "chat", "modality": "text"},
            },
            behavior_queue=[],
            action_packets=[],
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context={
                "thread_id": "thread-artifact",
                "digital_body_hints": {
                    "artifact_continuity": "detached",
                    "active_artifact_kind": "file",
                    "active_artifact_ref": "notes/plan.md",
                    "active_artifact_label": "plan.md",
                    "artifact_age_s": 7200,
                    "artifact_reacquisition_mode": "reopen_file",
                },
            },
        )

        self.assertIn("filesystem", body["world_surfaces"])
        self.assertIn("artifact_reacquisition_needed", body["access_state"]["conditions"])
        self.assertIn("artifact_reacquisition_available", body["access_state"]["conditions"])
        self.assertEqual(body["resource_state"]["artifact_continuity"], "detached")
        self.assertEqual(body["resource_state"]["active_artifact_kind"], "file")
        self.assertEqual(body["resource_state"]["active_artifact_label"], "plan.md")
        self.assertEqual(body["resource_state"]["artifact_age_s"], 7200)
        self.assertEqual(body["resource_state"]["artifact_reacquisition_mode"], "reopen_file")

    def test_derive_digital_body_state_reuses_carried_embodied_context(self):
        body = derive_digital_body_state(
            current_event={
                "kind": "user_utterance",
                "perception": {"channel": "chat", "modality": "text"},
            },
            behavior_queue=[],
            action_packets=[],
            interaction_carryover={
                "carryover_mode": "own_rhythm",
                "strength": 0.53,
                "embodied_context": {
                    "kind": "access_request_pending",
                    "summary": "她把动作推进到了审批门口。",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [17],
                    "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "artifact_source_query": "langgraph persistence checkpointer thread",
                    "artifact_source_title": "Persistence",
                    "artifact_source_tool_name": "search_web",
                    "requested_access": ["workspace_write"],
                    "missing_access": ["workspace_write"],
                    "requested_help": True,
                    "primary_status": "awaiting_approval",
                },
            },
            toolset_unlocks={},
            autonomy_block_reason="",
        )

        self.assertEqual(body["active_surface"], "approval_gate")
        self.assertEqual(body["access_state"]["mode"], "approval_pending")
        self.assertEqual(body["access_state"]["pending_approval_count"], 1)
        self.assertIn("workspace_write", body["access_state"]["missing_access"])
        self.assertIn("workspace_write", body["access_state"]["requestable_access"])
        self.assertIn("human_approval", body["access_state"]["requestable_access"])
        self.assertIn("approval_gate", body["world_surfaces"])
        self.assertEqual(body["resource_state"]["artifact_carrier"], "source_ref")
        self.assertEqual(body["resource_state"]["artifact_source_ref_ids"], [17])
        self.assertEqual(
            body["resource_state"]["artifact_source_query"],
            "langgraph persistence checkpointer thread",
        )
        self.assertIn("docs.langchain.com", body["resource_state"]["artifact_source_url"])

    def test_derive_digital_body_state_surfaces_temporary_cooldown(self):
        body = derive_digital_body_state(
            current_event={
                "kind": "user_utterance",
                "perception": {"channel": "chat", "modality": "text"},
            },
            behavior_queue=[],
            action_packets=[],
            toolset_unlocks={"search_web": 1},
            autonomy_block_reason="",
            session_context={
                "thread_id": "thread-cooldown",
                "digital_body_hints": {
                    "quota_state": "exhausted",
                    "retry_after_s": 300,
                    "cooldown_scope": "provider",
                },
            },
        )

        self.assertEqual(body["active_surface"], "cooldown_gate")
        self.assertIn("cooldown_gate", body["action_channels"])
        self.assertEqual(body["access_state"]["mode"], "cooldown")
        self.assertEqual(body["access_state"]["quota_state"], "exhausted")
        self.assertEqual(body["access_state"]["retry_after_s"], 300)
        self.assertEqual(body["access_state"]["cooldown_scope"], "provider")
        self.assertEqual(body["access_state"]["quota_state_detail"]["provider_state"], "exhausted")
        self.assertTrue(body["access_state"]["quota_state_detail"]["cooldown_active"])
        self.assertEqual(body["access_state"]["session_state"]["retry_after_s"], 300)
        self.assertIn("cooldown_active", body["access_state"]["conditions"])
        self.assertIn("provider_cooldown_active", body["access_state"]["conditions"])
        self.assertIn("api_quota", body["access_state"]["missing_access"])
        self.assertIn("api_quota", body["access_state"]["requestable_access"])
        self.assertIn("network", body["world_surfaces"])

    def test_derive_digital_body_state_surfaces_sandbox_allowed_roots_from_workspace_root(self):
        body = derive_digital_body_state(
            current_event={
                "kind": "user_utterance",
                "perception": {"channel": "chat", "modality": "text"},
            },
            behavior_queue=[],
            action_packets=[],
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context={
                "thread_id": "thread-sandbox-contract",
                "digital_body_hints": {
                    "sandbox_mode": "restricted",
                    "workspace_root": "E:/runtime/workspaces/lab-notes",
                },
            },
        )

        sandbox_state = body["access_state"]["sandbox_state"]
        self.assertEqual(sandbox_state["availability"], "restricted")
        self.assertEqual(sandbox_state["allowed_roots"], ["E:/runtime/workspaces/lab-notes"])
        self.assertEqual(sandbox_state["execution_policy"], "approval_required")
        self.assertFalse(sandbox_state["arbitrary_execution"])

    def test_derive_digital_body_state_uses_event_hints_only_to_fill_missing_session_truth(self):
        body = derive_digital_body_state(
            current_event={
                "kind": "sandbox_run_observation",
                "digital_body_hints": {
                    "workspace_root": "E:/runtime/workspaces/from-event",
                    "sandbox_state": {
                        "runner_kind": "local_restricted_runner",
                        "last_exit_code": 1,
                    },
                },
                "perception": {
                    "channel": "sandbox",
                    "modality": "sandbox",
                    "source_role": "environment",
                },
            },
            behavior_queue=[],
            action_packets=[],
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context={
                "thread_id": "thread-event-hints",
                "digital_body_hints": {
                    "workspace_root": "E:/runtime/workspaces/completed",
                    "sandbox_state": {
                        "runner_kind": "docker_isolated_runner",
                    },
                },
            },
        )

        sandbox_state = body["access_state"]["sandbox_state"]
        self.assertEqual(body["resource_state"]["workspace_root"], "E:/runtime/workspaces/completed")
        self.assertEqual(sandbox_state["runner_kind"], "docker_isolated_runner")
        self.assertEqual(sandbox_state["last_exit_code"], 1)


if __name__ == "__main__":
    unittest.main()
