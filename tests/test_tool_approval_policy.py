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

    def test_summarize_tool_approval_request_surfaces_access_acquire_proposals(self):
        batch = summarize_tool_approval_request(
            source="access",
            tool_calls=[
                {
                    "name": "access_request_help",
                    "args": {
                        "requested_access": ["api_key", "human_approval"],
                        "missing_access": ["api_key"],
                        "expected_effect": "这一步需要先补一个可用 API key。",
                        "access_acquire_proposals": [
                            {
                                "target": "api_key",
                                "mode": "operator_provide_api_key",
                                "path_kind": "create_new",
                                "summary": "先补一个可用 API key。",
                                "operator_action": "填入一个可用 key。",
                                "grants": ["api_key"],
                                "requires_operator": True,
                            }
                        ],
                        "selected_access_proposal": {
                            "target": "api_key",
                            "mode": "operator_provide_api_key",
                            "path_kind": "create_new",
                            "summary": "先补一个可用 API key。",
                            "operator_action": "填入一个可用 key。",
                            "grants": ["api_key"],
                            "requires_operator": True,
                        },
                    },
                }
            ],
            hide_memory_logs=True,
            max_calls=3,
            toolset_upgrade_ttl_s=180,
            assist_request={
                "kind": "grant_access",
                "message": "喂，先把 API key 给我，我接上就继续。",
                "resume_mode": "auto_continue",
            },
        )

        self.assertTrue(batch.show_logs)
        self.assertEqual(batch.assist_request["kind"], "grant_access")
        self.assertIn("API key", batch.assist_request["message"])
        preview = batch.visible_tool_calls[0]
        self.assertEqual(preview.name, "access_request_help")
        self.assertEqual(preview.reason, "这一步需要先补一个可用 API key。")
        self.assertEqual(preview.access_acquire_proposals[0]["target"], "api_key")
        self.assertEqual(preview.access_acquire_proposals[0]["path_kind"], "create_new")
        self.assertEqual(preview.selected_access_proposal["mode"], "operator_provide_api_key")
        self.assertEqual(preview.selected_access_proposal["path_kind"], "create_new")
        self.assertIn("不代表外部入口已经补齐", preview.note)

    def test_summarize_tool_approval_request_surfaces_workspace_mutation_preview(self):
        batch = summarize_tool_approval_request(
            source="dialog",
            tool_calls=[
                {
                    "name": "replace_workspace_lines",
                    "args": {
                        "relative_path": "notes/todo.md",
                        "start_line": 2,
                        "end_line": 2,
                        "new_text": "beta v2",
                    },
                    "mutation_preview": {
                        "tool_name": "replace_workspace_lines",
                        "can_apply": True,
                        "mutation_mode": "replace",
                        "workspace_name": "lab",
                        "relative_path": "notes/todo.md",
                        "file_name": "todo.md",
                        "summary": "todo.md 的 patch 预览已生成，审批通过后会只在当前 workspace 内落地。",
                        "diff_preview": "--- a/notes/todo.md\n+++ b/notes/todo.md\n@@\n-beta\n+beta v2\n",
                    },
                }
            ],
            hide_memory_logs=True,
            max_calls=3,
            toolset_upgrade_ttl_s=180,
        )

        preview = batch.visible_tool_calls[0]
        self.assertEqual(preview.name, "replace_workspace_lines")
        self.assertEqual(preview.reason, "todo.md 的 patch 预览已生成，审批通过后会只在当前 workspace 内落地。")
        self.assertEqual(preview.mutation_preview["mutation_mode"], "replace")
        self.assertEqual(preview.mutation_preview["relative_path"], "notes/todo.md")
        self.assertIn("-beta", preview.mutation_preview["diff_preview"])
        self.assertIn("当前 runtime workspace", preview.note)

    def test_summarize_tool_approval_request_surfaces_sandbox_execution_preview(self):
        batch = summarize_tool_approval_request(
            source="dialog",
            tool_calls=[
                {
                    "name": "execute_workspace_command",
                    "args": {
                        "argv": ["python", "emit_artifact.py"],
                        "cwd": ".",
                    },
                    "execution_preview": {
                        "runner_kind": "local_restricted_runner",
                        "isolation_level": "host_local_restricted",
                        "argv": ["python", "emit_artifact.py"],
                        "cwd": "E:/runtime/workspaces/lab-notes",
                        "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
                        "timeout_s": 25,
                        "writes_expected": True,
                        "expected_artifacts": ["notes/generated.txt"],
                    },
                }
            ],
            hide_memory_logs=True,
            max_calls=3,
            toolset_upgrade_ttl_s=180,
        )

        preview = batch.visible_tool_calls[0]
        self.assertEqual(preview.name, "execute_workspace_command")
        self.assertEqual(preview.execution_preview["runner_kind"], "local_restricted_runner")
        self.assertEqual(preview.execution_preview["allowed_roots"], ["E:/runtime/workspaces/lab-notes"])
        self.assertEqual(preview.reason, "python emit_artifact.py")
        self.assertIn("受限命令规格执行", preview.note)

    def test_summarize_tool_approval_request_surfaces_sandbox_phase2_docker_preview(self):
        batch = summarize_tool_approval_request(
            source="dialog",
            tool_calls=[
                {
                    "name": "execute_workspace_command",
                    "args": {
                        "argv": ["pytest", "-q", "tests/test_sandbox_phase2_repo_fixture.py"],
                        "cwd": ".",
                    },
                    "execution_preview": {
                        "runner_kind": "docker_isolated_runner",
                        "isolation_level": "docker_local_isolated",
                        "image_ref": "amadeus-thread0/sandbox-phase2:py312",
                        "network_policy": "none",
                        "workspace_root_kind": "attached_repo_root",
                        "argv": ["pytest", "-q", "tests/test_sandbox_phase2_repo_fixture.py"],
                        "cwd": "E:/repo/amadeus-thread0",
                        "allowed_roots": ["E:/repo/amadeus-thread0"],
                        "timeout_s": 60,
                        "writes_expected": False,
                        "expected_artifacts": [],
                    },
                }
            ],
            hide_memory_logs=True,
            max_calls=3,
            toolset_upgrade_ttl_s=180,
        )

        preview = batch.visible_tool_calls[0]
        self.assertEqual(preview.execution_preview["runner_kind"], "docker_isolated_runner")
        self.assertEqual(preview.execution_preview["network_policy"], "none")
        self.assertEqual(preview.execution_preview["workspace_root_kind"], "attached_repo_root")

    def test_summarize_tool_approval_request_surfaces_browser_execution_preview(self):
        batch = summarize_tool_approval_request(
            source="dialog",
            tool_calls=[
                {
                    "name": "browser_download_click",
                    "args": {"target_ref": "e3"},
                    "browser_execution_preview": {
                        "runner_kind": "playwright_persistent_context",
                        "isolation_level": "persistent_profile_runtime",
                        "operation": "download_click",
                        "profile_id": "thread-browser",
                        "page_ref": "page:page-1",
                        "page_url": "https://example.com/report",
                        "page_title": "Report",
                        "target_ref": "e3",
                        "target_label": "Download payload",
                        "download_target": "E:/runtime/workspaces/lab-notes/downloads/payload.txt",
                        "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
                        "downloads_root": "E:/runtime/browser/downloads/thread-browser",
                        "timeout_s": 20,
                        "verification_summary": "download into the runtime-controlled browser directory",
                    },
                }
            ],
            hide_memory_logs=True,
            max_calls=3,
            toolset_upgrade_ttl_s=180,
        )

        preview = batch.visible_tool_calls[0]
        self.assertEqual(preview.name, "browser_download_click")
        self.assertEqual(preview.browser_execution_preview["runner_kind"], "playwright_persistent_context")
        self.assertEqual(preview.browser_execution_preview["download_target"], "E:/runtime/workspaces/lab-notes/downloads/payload.txt")
        self.assertEqual(preview.reason, "download_click https://example.com/report")
        self.assertEqual(preview.note, "download into the runtime-controlled browser directory")

    def test_summarize_tool_approval_request_surfaces_skill_mutation_preview(self):
        batch = summarize_tool_approval_request(
            source="skills",
            tool_calls=[
                {
                    "name": "install_skill",
                    "args": {
                        "skill_id": "pytest-helper",
                        "resolved_version": "1.1.0",
                        "source": "official_registry",
                    },
                    "skill_preview": {
                        "operation": "install_skill",
                        "skill_id": "pytest-helper",
                        "resolved_version": "1.1.0",
                        "source": "official_registry",
                        "hash": "abc123",
                        "requested_permissions": ["filesystem_read"],
                        "sandbox_profiles": ["workspace_write"],
                        "verification_summary": "registry verified",
                    },
                }
            ],
            hide_memory_logs=True,
            max_calls=3,
            toolset_upgrade_ttl_s=180,
        )

        preview = batch.visible_tool_calls[0]
        self.assertEqual(preview.name, "install_skill")
        self.assertEqual(preview.reason, "install_skill pytest-helper@1.1.0")
        self.assertEqual(preview.skill_preview["hash"], "abc123")
        self.assertIn("permissions=filesystem_read", preview.note)
        self.assertIn("profiles=workspace_write", preview.note)

    def test_summarize_tool_approval_request_surfaces_skill_activation_preview(self):
        batch = summarize_tool_approval_request(
            source="skills",
            tool_calls=[
                {
                    "name": "enable_skill",
                    "args": {"skill_id": "source-ref-anchor-review"},
                    "skill_preview": {
                        "operation": "enable_skill",
                        "skill_id": "source-ref-anchor-review",
                        "resolved_version": "1.0.0",
                        "source": "local_authored",
                        "hash": "local123",
                        "requested_permissions": [],
                        "sandbox_profiles": [],
                        "verification_summary": "local authored skill",
                    },
                }
            ],
            hide_memory_logs=True,
            max_calls=3,
            toolset_upgrade_ttl_s=180,
        )

        preview = batch.visible_tool_calls[0]
        self.assertEqual(preview.name, "enable_skill")
        self.assertEqual(preview.reason, "enable_skill source-ref-anchor-review@1.0.0")
        self.assertEqual(preview.skill_preview["source"], "local_authored")
        self.assertIn("local authored skill", preview.note)


if __name__ == "__main__":
    unittest.main()
