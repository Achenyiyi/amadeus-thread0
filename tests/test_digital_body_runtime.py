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
        self.assertIn("session_expiring_soon", body["access_state"]["conditions"])
        self.assertIn("session_refresh_available", body["access_state"]["conditions"])
        self.assertIn("session_refresh", body["access_state"]["requestable_access"])
        self.assertEqual(body["access_state"]["mode"], "native_only")

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
        self.assertIn("cooldown_active", body["access_state"]["conditions"])
        self.assertIn("provider_cooldown_active", body["access_state"]["conditions"])
        self.assertIn("api_quota", body["access_state"]["missing_access"])
        self.assertIn("api_quota", body["access_state"]["requestable_access"])
        self.assertIn("network", body["world_surfaces"])


if __name__ == "__main__":
    unittest.main()
