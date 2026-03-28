from __future__ import annotations

import unittest

from amadeus_thread0.runtime.tool_approval import (
    auto_approve_decisions,
    needs_second_confirmation,
    should_auto_resume_memory_approval,
    summarize_tool_approval_request,
)


class ToolApprovalPolicyTests(unittest.TestCase):
    def test_should_auto_resume_memory_approval_for_whitelisted_memory_tools(self):
        payload = {
            "source": "memory",
            "tool_calls": [
                {"name": "set_profile", "args": {"key": "nickname", "value": "助手"}},
                {"name": "add_moment", "args": {"summary": "一起熬夜"}},
            ],
        }
        self.assertTrue(
            should_auto_resume_memory_approval(
                payload,
                user_facing_mode=True,
                auto_approve_memory_writes=True,
            )
        )

    def test_should_not_auto_resume_when_non_whitelisted_tool_present(self):
        payload = {
            "source": "memory",
            "tool_calls": [
                {"name": "set_profile", "args": {"key": "nickname", "value": "助手"}},
                {"name": "rollback_memory_change", "args": {"change_id": "chg-1"}},
            ],
        }
        self.assertFalse(
            should_auto_resume_memory_approval(
                payload,
                user_facing_mode=True,
                auto_approve_memory_writes=True,
            )
        )

    def test_should_auto_resume_memory_approval_ignores_proposal_id_metadata(self):
        payload = {
            "source": "memory",
            "tool_calls": [
                {
                    "name": "set_profile",
                    "proposal_id": "ap-memory-1",
                    "args": {"key": "nickname", "value": "助手"},
                }
            ],
        }
        self.assertTrue(
            should_auto_resume_memory_approval(
                payload,
                user_facing_mode=True,
                auto_approve_memory_writes=True,
            )
        )

    def test_needs_second_confirmation_for_risky_memory_updates(self):
        self.assertTrue(needs_second_confirmation("memory", "correct_profile", {"key": "timezone"}))
        self.assertTrue(needs_second_confirmation("memory", "set_profile", {"key": "likes", "mode": "merge"}))
        self.assertTrue(needs_second_confirmation("memory", "set_profile", {"key": "city", "mode": "overwrite"}))
        self.assertFalse(needs_second_confirmation("memory", "set_profile", {"key": "city", "mode": "merge"}))
        self.assertFalse(needs_second_confirmation("dialog", "set_profile", {"key": "likes"}))

    def test_summarize_tool_approval_request_builds_preview_and_clips_hidden_calls(self):
        batch = summarize_tool_approval_request(
            source="memory",
            tool_calls=[
                {
                    "name": "request_toolset_upgrade",
                    "args": {
                        "requested_tools": ["web_search", "search_langchain_docs"],
                        "reason": "需要查资料",
                        "meta": {
                            "source_text": "x" * 260,
                            "confidence": 0.92,
                            "confirmed_by": "human_approval",
                        },
                    },
                },
                {
                    "name": "set_profile",
                    "args": {"key": "timezone", "value": "Asia/Shanghai", "mode": "merge"},
                },
                {"name": "add_moment", "args": {"summary": "一起吃饭"}},
            ],
            hide_memory_logs=True,
            max_calls=2,
            toolset_upgrade_ttl_s=180,
        )

        self.assertEqual(batch.source, "memory")
        self.assertFalse(batch.show_logs)
        self.assertEqual(batch.total_tool_call_count, 3)
        self.assertEqual(batch.hidden_tool_call_count, 1)
        self.assertEqual(len(batch.visible_tool_calls), 2)

        upgrade = batch.visible_tool_calls[0]
        self.assertEqual(upgrade.name, "request_toolset_upgrade")
        self.assertEqual(upgrade.requested_tools, ["web_search", "search_langchain_docs"])
        self.assertEqual(upgrade.reason, "需要查资料")
        self.assertEqual(upgrade.note, "approve 将临时解锁上述工具，预计有效期约 180s")
        self.assertEqual(upgrade.meta_preview.get("confidence"), 0.92)
        self.assertTrue(str(upgrade.meta_preview.get("source_text", "")).endswith("..."))

        profile = batch.visible_tool_calls[1]
        self.assertEqual(profile.name, "set_profile")
        self.assertTrue(profile.needs_second_confirmation)

    def test_auto_approve_decisions_matches_normalized_tool_call_count(self):
        decisions = auto_approve_decisions(
            [
                {"name": "set_profile", "args": {}},
                None,
                {"name": "add_moment", "args": {}},
            ]
        )
        self.assertEqual(decisions, [{"action": "approve"}, {"action": "approve"}])


if __name__ == "__main__":
    unittest.main()
