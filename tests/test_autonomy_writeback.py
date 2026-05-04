from __future__ import annotations

import unittest

from amadeus_thread0.evolution_engine.reconsolidation import build_reconsolidation_snapshot
from amadeus_thread0.graph_parts.action_packets import build_tool_action_packet
from amadeus_thread0.runtime.final_state import (
    resolve_action_packets,
    resolve_action_trace,
    resolve_autonomy_block_reason,
    resolve_autonomy_intent,
    resolve_digital_body_consequence,
    resolve_digital_body_state,
    resolve_pending_action_proposal,
)


class AutonomyWritebackTests(unittest.TestCase):
    def test_reconsolidation_snapshot_distinguishes_sandbox_completed_blocked_and_pending(self):
        base_body = {
            "active_surface": "tooling",
            "perception_channels": ["dialogue", "filesystem"],
            "action_channels": ["language", "structured_action", "tooling"],
            "world_surfaces": ["filesystem", "sandbox"],
            "access_state": {
                "mode": "tool_enabled",
                "filesystem_state": "writable",
                "sandbox_mode": "restricted",
                "sandbox_state": {
                    "availability": "restricted",
                    "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
                    "execution_policy": "approval_required",
                    "runner_kind": "local_restricted_runner",
                    "isolation_level": "host_local_restricted",
                },
            },
            "resource_state": {
                "artifact_continuity": "attached",
                "active_artifact_kind": "file",
                "active_artifact_ref": "E:/runtime/workspaces/lab-notes/.amadeus/sandbox-runs/ap/stdout.txt",
                "active_artifact_label": "stdout.txt",
                "artifact_carrier": "filesystem",
                "workspace_root": "E:/runtime/workspaces/lab-notes",
            },
        }

        def _snapshot_for(status: str, *, exit_code: int, run_id: str) -> dict[str, object]:
            packet = build_tool_action_packet(
                tool_name="execute_workspace_command",
                proposal_id=run_id,
                args={"argv": ["python", "emit.py"]},
                action="approve",
                status=status,
                result_summary="sandbox done" if status == "completed" else "sandbox blocked",
                block_reason="sandbox blocked" if status == "blocked" else "",
                execution_spec={
                    "executor": "python",
                    "profile": "python_script",
                    "argv": ["python", "emit.py"],
                    "cwd": "E:/runtime/workspaces/lab-notes",
                    "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
                    "timeout_s": 25,
                    "writes_expected": False,
                    "expected_artifacts": [],
                },
                execution_preview={
                    "runner_kind": "local_restricted_runner",
                    "isolation_level": "host_local_restricted",
                    "argv": ["python", "emit.py"],
                    "cwd": "E:/runtime/workspaces/lab-notes",
                    "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
                    "timeout_s": 25,
                    "writes_expected": False,
                    "expected_artifacts": [],
                },
                execution_result={
                    "run_id": run_id,
                    "status": status if status in {"completed", "blocked"} else "",
                    "exit_code": exit_code,
                    "duration_ms": 42,
                    "stdout_log_ref": f"E:/runtime/workspaces/lab-notes/.amadeus/sandbox-runs/{run_id}/stdout.txt",
                    "stderr_log_ref": f"E:/runtime/workspaces/lab-notes/.amadeus/sandbox-runs/{run_id}/stderr.txt",
                    "produced_artifacts": [],
                    "error_summary": "" if status == "completed" else "process exited with code 2",
                },
            )
            return build_reconsolidation_snapshot(
                current_event={"kind": "user_utterance"},
                appraisal={"interaction_frame": "task"},
                world_model_state={},
                semantic_narrative_profile={},
                latent_state={"self_coherence": 0.82},
                emotion_state={"label": "focused"},
                bond_state={"trust": 0.6},
                behavior_action={"interaction_mode": "tooling"},
                action_packets=[packet],
                digital_body_state=base_body,
            )

        completed = _snapshot_for("completed", exit_code=0, run_id="ap-sandbox-completed")
        blocked = _snapshot_for("blocked", exit_code=2, run_id="ap-sandbox-blocked")
        pending_packet = build_tool_action_packet(
            tool_name="execute_workspace_command",
            proposal_id="ap-sandbox-pending",
            args={"argv": ["python", "emit.py"]},
            action="approve",
            status="awaiting_approval",
            execution_spec={
                "executor": "python",
                "profile": "python_script",
                "argv": ["python", "emit.py"],
                "cwd": "E:/runtime/workspaces/lab-notes",
                "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
                "timeout_s": 25,
                "writes_expected": False,
                "expected_artifacts": [],
            },
            execution_preview={
                "runner_kind": "local_restricted_runner",
                "isolation_level": "host_local_restricted",
                "argv": ["python", "emit.py"],
                "cwd": "E:/runtime/workspaces/lab-notes",
                "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
                "timeout_s": 25,
                "writes_expected": False,
                "expected_artifacts": [],
            },
        )
        pending = build_reconsolidation_snapshot(
            current_event={"kind": "user_utterance"},
            appraisal={"interaction_frame": "task"},
            world_model_state={},
            semantic_narrative_profile={},
            latent_state={"self_coherence": 0.82},
            emotion_state={"label": "focused"},
            bond_state={"trust": 0.6},
            behavior_action={"interaction_mode": "tooling"},
            action_packets=[pending_packet],
            digital_body_state={
                **base_body,
                "active_surface": "approval_gate",
                "action_channels": ["language", "structured_action", "approval_gate", "tooling"],
                "access_state": {
                    **base_body["access_state"],
                    "mode": "approval_pending",
                    "pending_approval_count": 1,
                    "external_mutation_pending": True,
                },
            },
        )

        self.assertEqual(completed["digital_body_consequence"]["kind"], "sandbox_execution_completed")
        self.assertEqual(completed["digital_body_consequence"]["sandbox_exit_code"], 0)
        self.assertEqual(blocked["digital_body_consequence"]["kind"], "sandbox_execution_blocked")
        self.assertEqual(blocked["digital_body_consequence"]["sandbox_exit_code"], 2)
        self.assertEqual(pending["digital_body_consequence"]["kind"], "access_request_pending")
        self.assertEqual(pending["digital_body_consequence"]["primary_status"], "awaiting_approval")

    def test_reconsolidation_snapshot_distinguishes_browser_completed_blocked_and_takeover(self):
        base_body = {
            "active_surface": "tooling",
            "perception_channels": ["dialogue", "browser"],
            "action_channels": ["language", "structured_action", "tooling"],
            "world_surfaces": ["browser", "filesystem"],
            "access_state": {
                "mode": "tool_enabled",
                "browser_session": "present",
                "filesystem_state": "writable",
                "browser_runtime_state": {
                    "availability": "available",
                    "profile_root": "E:/runtime/browser/profiles/thread-browser",
                    "context_status": "active",
                    "active_page_id": "page-1",
                    "active_tab_count": 1,
                    "downloads_dir": "E:/runtime/browser/downloads/thread-browser",
                    "last_action_status": "completed",
                    "last_run_id": "ap-browser-open-1",
                    "manual_takeover_required": False,
                    "runner_kind": "playwright_persistent_context",
                    "isolation_level": "persistent_profile_runtime",
                },
            },
            "resource_state": {
                "artifact_continuity": "attached",
                "active_artifact_kind": "page",
                "active_artifact_ref": "page:page-1",
                "active_artifact_label": "Docs",
                "artifact_carrier": "browser_page",
                "artifact_source_url": "https://example.com/docs",
                "browser_profile_id": "thread-browser",
                "browser_tab_id": "tab-1",
                "workspace_root": "E:/runtime/workspaces/lab-notes",
            },
        }

        def _snapshot_for(*, proposal_id: str, tool_name: str, intent: str, status: str, action_kind: str, manual_takeover_required: bool, error_summary: str) -> dict[str, object]:
            packet = build_tool_action_packet(
                tool_name=tool_name,
                proposal_id=proposal_id,
                args={"target_ref": "e2"},
                action="approve",
                status=status,
                result_summary="browser done" if status == "completed" else error_summary,
                block_reason=error_summary if status == "blocked" else "",
                browser_execution_spec={
                    "operation": action_kind,
                    "profile_id": "thread-browser",
                    "page_ref": "page:page-1",
                    "target_ref": "e2",
                    "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
                    "browser_downloads_root": "E:/runtime/browser/downloads/thread-browser",
                    "timeout_s": 20,
                    "wait_until": "load",
                },
                browser_execution_preview={
                    "runner_kind": "playwright_persistent_context",
                    "isolation_level": "persistent_profile_runtime",
                    "operation": action_kind,
                    "profile_id": "thread-browser",
                    "page_ref": "page:page-1",
                    "page_url": "https://example.com/docs",
                    "page_title": "Docs",
                    "target_ref": "e2",
                    "target_label": "Approve action",
                    "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
                    "downloads_root": "E:/runtime/browser/downloads/thread-browser",
                    "timeout_s": 20,
                    "verification_summary": "browser preview",
                },
                browser_execution_result={
                    "run_id": proposal_id,
                    "status": status,
                    "profile_id": "thread-browser",
                    "page_id": "page-1",
                    "tab_id": "tab-1",
                    "url": "https://example.com/docs",
                    "title": "Docs",
                    "action_kind": action_kind,
                    "target_ref": "e2",
                    "duration_ms": 45,
                    "active_tab_count": 1,
                    "last_action_status": status,
                    "download_path": "",
                    "upload_source": "",
                    "error_summary": error_summary,
                    "manual_takeover_required": manual_takeover_required,
                },
            )
            packet["intent"] = intent
            body = {
                **base_body,
                "access_state": {
                    **base_body["access_state"],
                    "browser_runtime_state": {
                        **base_body["access_state"]["browser_runtime_state"],
                        "last_action_status": status,
                        "last_run_id": proposal_id,
                        "manual_takeover_required": manual_takeover_required,
                        "context_status": "manual_takeover" if manual_takeover_required else "active",
                    },
                },
            }
            return build_reconsolidation_snapshot(
                current_event={"kind": "user_utterance"},
                appraisal={"interaction_frame": "task"},
                world_model_state={},
                semantic_narrative_profile={},
                latent_state={"self_coherence": 0.82},
                emotion_state={"label": "focused"},
                bond_state={"trust": 0.6},
                behavior_action={"interaction_mode": "tooling"},
                action_packets=[packet],
                digital_body_state=body,
            )

        completed = _snapshot_for(
            proposal_id="ap-browser-open-1",
            tool_name="browser_open_url",
            intent="browser:open_url",
            status="completed",
            action_kind="open_url",
            manual_takeover_required=False,
            error_summary="",
        )
        blocked = _snapshot_for(
            proposal_id="ap-browser-click-1",
            tool_name="browser_click",
            intent="browser:click",
            status="blocked",
            action_kind="click",
            manual_takeover_required=False,
            error_summary="browser action timed out after 20s",
        )
        takeover = _snapshot_for(
            proposal_id="ap-browser-fill-1",
            tool_name="browser_fill",
            intent="browser:fill",
            status="blocked",
            action_kind="fill",
            manual_takeover_required=True,
            error_summary="sensitive credential entry requires manual browser takeover",
        )
        explicit_takeover = _snapshot_for(
            proposal_id="ap-browser-takeover-1",
            tool_name="browser_begin_manual_takeover",
            intent="browser:begin_manual_takeover",
            status="completed",
            action_kind="begin_manual_takeover",
            manual_takeover_required=True,
            error_summary="manual browser takeover requested",
        )

        self.assertEqual(completed["digital_body_consequence"]["kind"], "browser_navigation_completed")
        self.assertEqual(completed["digital_body_consequence"]["browser_run_id"], "ap-browser-open-1")
        self.assertEqual(blocked["digital_body_consequence"]["kind"], "browser_action_blocked")
        self.assertEqual(blocked["digital_body_consequence"]["browser_last_exit_status"], "blocked")
        self.assertEqual(takeover["digital_body_consequence"]["kind"], "browser_takeover_requested")
        self.assertTrue(takeover["digital_body_consequence"]["browser_runtime_state"]["manual_takeover_required"])
        self.assertEqual(explicit_takeover["digital_body_consequence"]["kind"], "browser_takeover_requested")
        self.assertEqual(explicit_takeover["action_packets"][0]["status"], "completed")
        self.assertEqual(explicit_takeover["digital_body_consequence"]["primary_status"], "blocked")
        self.assertEqual(explicit_takeover["digital_body_consequence"]["browser_last_exit_status"], "blocked")
        self.assertTrue(bool(explicit_takeover["digital_body_consequence"]["requested_help"]))
        self.assertTrue(bool(explicit_takeover["digital_body_consequence"]["environmental_friction"]))

    def test_reconsolidation_snapshot_does_not_let_stale_takeover_state_override_completed_browser_result(self):
        stale_runtime_body = {
            "active_surface": "tooling",
            "perception_channels": ["dialogue", "browser"],
            "action_channels": ["language", "structured_action", "tooling"],
            "world_surfaces": ["browser", "filesystem"],
            "access_state": {
                "mode": "tool_enabled",
                "browser_session": "present",
                "filesystem_state": "writable",
                "browser_runtime_state": {
                    "availability": "available",
                    "profile_root": "E:/runtime/browser/profiles/thread-browser",
                    "context_status": "manual_takeover",
                    "active_page_id": "page-1",
                    "active_tab_count": 1,
                    "downloads_dir": "E:/runtime/browser/downloads/thread-browser",
                    "last_action_status": "manual_takeover_required",
                    "last_run_id": "ap-browser-old-takeover",
                    "manual_takeover_required": True,
                    "runner_kind": "playwright_persistent_context",
                    "isolation_level": "persistent_profile_runtime",
                },
            },
            "resource_state": {
                "artifact_continuity": "attached",
                "active_artifact_kind": "page",
                "active_artifact_ref": "page:page-1",
                "active_artifact_label": "Docs",
                "artifact_carrier": "browser_page",
                "browser_profile_id": "thread-browser",
                "browser_tab_id": "tab-1",
            },
        }
        packet = build_tool_action_packet(
            tool_name="browser_click",
            proposal_id="ap-browser-click-after-takeover",
            args={"target_ref": "button-submit"},
            action="approve",
            status="completed",
            result_summary="clicked after manual takeover was resolved",
            browser_execution_preview={
                "operation": "click",
                "profile_id": "thread-browser",
                "page_ref": "page:page-1",
                "page_url": "https://example.com/docs",
                "page_title": "Docs",
                "target_ref": "button-submit",
                "requires_manual_takeover": False,
            },
            browser_execution_result={
                "run_id": "ap-browser-click-after-takeover",
                "status": "completed",
                "profile_id": "thread-browser",
                "page_id": "page-1",
                "tab_id": "tab-1",
                "url": "https://example.com/docs",
                "title": "Docs",
                "action_kind": "click",
                "target_ref": "button-submit",
                "duration_ms": 41,
                "active_tab_count": 1,
                "last_action_status": "completed",
                "manual_takeover_required": False,
            },
        )
        snapshot = build_reconsolidation_snapshot(
            current_event={"kind": "user_utterance"},
            appraisal={"interaction_frame": "task"},
            world_model_state={},
            semantic_narrative_profile={},
            latent_state={"self_coherence": 0.82},
            emotion_state={"label": "focused"},
            bond_state={"trust": 0.6},
            behavior_action={"interaction_mode": "tooling"},
            action_packets=[packet],
            digital_body_state=stale_runtime_body,
        )

        consequence = snapshot["digital_body_consequence"]
        self.assertEqual(consequence["kind"], "browser_interaction_completed")
        self.assertEqual(consequence["primary_status"], "completed")
        self.assertEqual(consequence["browser_last_exit_status"], "completed")
        self.assertFalse(bool(consequence["requested_help"]))

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
                    "browser_session": "present",
                    "account_state": "logged_in",
                    "cookie_state": "present",
                    "api_key_state": "missing",
                    "quota_state": "ok",
                    "sandbox_mode": "restricted",
                    "missing_access": ["api_key"],
                    "requestable_access": ["api_key", "human_approval"],
                    "selected_access_proposal": {
                        "target": "api_key",
                        "mode": "operator_provide_api_key",
                        "summary": "先补一个可用 API key。",
                        "operator_action": "填入一个可用 key。",
                        "grants": ["api_key"],
                        "pending_grants": ["api_key"],
                        "completion_ratio": 0.0,
                        "requires_operator": True,
                    },
                    "sandbox_state": {
                        "availability": "restricted",
                        "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
                        "execution_policy": "approval_required",
                        "last_status": "gated",
                    },
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
        access_state = snapshot["digital_body_state"]["access_state"]
        self.assertEqual(access_state["session_state"]["continuity"], "stable")
        self.assertEqual(access_state["account_state_detail"]["login_state"], "logged_in")
        self.assertEqual(access_state["account_state_detail"]["api_key_state"], "missing")
        self.assertEqual(access_state["quota_state_detail"]["provider_state"], "ok")
        self.assertEqual(access_state["permission_state"]["approval_state"], "approval_pending")
        self.assertEqual(access_state["permission_state"]["pending_grants"], ["api_key"])
        self.assertEqual(access_state["sandbox_state"]["availability"], "restricted")
        self.assertEqual(access_state["sandbox_state"]["allowed_roots"], ["E:/runtime/workspaces/lab-notes"])
        self.assertEqual(snapshot["digital_body_consequence"]["kind"], "access_request_pending")
        self.assertIn("human_approval", snapshot["digital_body_consequence"]["requested_access"])
        self.assertEqual(snapshot["digital_body_consequence"]["artifact_carrier"], "source_ref")
        self.assertEqual(snapshot["digital_body_consequence"]["artifact_source_ref_ids"], [17])
        self.assertIn("docs.langchain.com", snapshot["digital_body_consequence"]["artifact_source_url"])
        self.assertEqual(
            snapshot["digital_body_consequence"]["artifact_source_query"],
            "langgraph persistence checkpointer thread",
        )
        consequence = snapshot["digital_body_consequence"]
        self.assertEqual(consequence["session_state"]["continuity"], "stable")
        self.assertEqual(consequence["account_state_detail"]["login_state"], "logged_in")
        self.assertEqual(consequence["account_state_detail"]["api_key_state"], "missing")
        self.assertEqual(consequence["quota_state_detail"]["provider_state"], "ok")
        self.assertEqual(consequence["permission_state"]["approval_state"], "approval_pending")
        self.assertEqual(consequence["permission_state"]["pending_grants"], ["api_key"])
        self.assertEqual(consequence["sandbox_state"]["availability"], "restricted")

    def test_reconsolidation_snapshot_preserves_workspace_root_for_completed_workspace_artifact(self):
        snapshot = build_reconsolidation_snapshot(
            current_event={"kind": "user_utterance"},
            appraisal={"interaction_frame": "task"},
            world_model_state={},
            semantic_narrative_profile={},
            latent_state={"self_coherence": 0.81},
            emotion_state={"label": "neutral"},
            bond_state={"trust": 0.55},
            behavior_action={"interaction_mode": "tooling", "primary_motive": "restore_workspace_continuity"},
            action_packets=[
                {
                    "proposal_id": "ap-ws-1",
                    "origin": "counterpart_request",
                    "intent": "artifact:reopen_file",
                    "status": "completed",
                    "risk": "read",
                    "requires_approval": False,
                    "tool_name": "reacquire_artifact",
                    "result_summary": "已重新接回文件 plan.md。",
                    "writeback_ready": True,
                    "artifact_context": {
                        "carrier": "filesystem",
                        "artifact_kind": "file",
                        "artifact_ref": "notes/plan.md",
                        "artifact_label": "plan.md",
                        "workspace_root": "E:/runtime/workspaces/lab-notes",
                        "reacquisition_mode": "reopen_file",
                        "preview": "# plan\nkeep going\n",
                        "exists": True,
                    },
                }
            ],
            digital_body_state={
                "active_surface": "tooling",
                "perception_channels": ["dialogue"],
                "action_channels": ["language", "tooling"],
                "access_state": {"mode": "tool_enabled"},
                "resource_state": {
                    "action_packet_count": 1,
                    "completed_packet_count": 1,
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "file",
                    "active_artifact_ref": "notes/plan.md",
                    "active_artifact_label": "plan.md",
                    "artifact_reacquisition_mode": "reopen_file",
                    "workspace_root": "E:/runtime/workspaces/lab-notes",
                },
            },
        )
        artifact_context = snapshot["action_packets"][0].get("artifact_context") if isinstance(snapshot["action_packets"][0].get("artifact_context"), dict) else {}
        self.assertEqual(artifact_context.get("workspace_root"), "E:/runtime/workspaces/lab-notes")
        self.assertEqual(snapshot["digital_body_consequence"]["kind"], "artifact_reacquired")
        self.assertEqual(snapshot["digital_body_consequence"]["workspace_root"], "E:/runtime/workspaces/lab-notes")

    def test_reconsolidation_snapshot_preserves_workspace_root_for_completed_workspace_mutation_packet(self):
        snapshot = build_reconsolidation_snapshot(
            current_event={"kind": "user_utterance"},
            appraisal={"interaction_frame": "task"},
            world_model_state={},
            semantic_narrative_profile={},
            latent_state={"self_coherence": 0.82},
            emotion_state={"label": "neutral"},
            bond_state={"trust": 0.56},
            behavior_action={"interaction_mode": "tooling", "primary_motive": "continue_workspace_task"},
            action_packets=[
                {
                    "proposal_id": "ap-mutate-1",
                    "origin": "counterpart_request",
                    "intent": "artifact:append_file",
                    "status": "completed",
                    "risk": "external_mutation",
                    "requires_approval": True,
                    "tool_name": "append_workspace_file",
                    "result_summary": "已继续写入文件 plan.md。",
                    "writeback_ready": True,
                    "artifact_context": {
                        "carrier": "filesystem",
                        "artifact_kind": "file",
                        "artifact_ref": "notes/plan.md",
                        "artifact_label": "plan.md",
                        "workspace_root": "E:/runtime/workspaces/lab-notes",
                        "reacquisition_mode": "reopen_file",
                        "preview": "# plan\nmore notes\n",
                        "exists": True,
                    },
                }
            ],
            digital_body_state={
                "active_surface": "tooling",
                "perception_channels": ["dialogue"],
                "action_channels": ["language", "tooling"],
                "access_state": {"mode": "tool_enabled"},
                "resource_state": {
                    "action_packet_count": 1,
                    "completed_packet_count": 1,
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "file",
                    "active_artifact_ref": "notes/plan.md",
                    "active_artifact_label": "plan.md",
                    "artifact_reacquisition_mode": "reopen_file",
                    "artifact_mutation_mode": "append",
                    "workspace_root": "E:/runtime/workspaces/lab-notes",
                },
            },
        )
        artifact_context = snapshot["action_packets"][0].get("artifact_context") if isinstance(snapshot["action_packets"][0].get("artifact_context"), dict) else {}
        self.assertEqual(artifact_context.get("workspace_root"), "E:/runtime/workspaces/lab-notes")
        self.assertEqual(snapshot["digital_body_consequence"]["kind"], "workspace_file_updated")
        self.assertEqual(snapshot["digital_body_consequence"]["workspace_root"], "E:/runtime/workspaces/lab-notes")
        self.assertEqual(snapshot["digital_body_consequence"]["artifact_mutation_mode"], "append")

    def test_reconsolidation_snapshot_normalizes_resource_state_source_ref_identity_fields(self):
        snapshot = build_reconsolidation_snapshot(
            current_event={"kind": "user_utterance"},
            appraisal={"interaction_frame": "relationship"},
            world_model_state={},
            semantic_narrative_profile={},
            latent_state={"self_coherence": 0.8},
            emotion_state={"label": "care"},
            bond_state={"trust": 0.62},
            behavior_action={"interaction_mode": "checkin", "primary_motive": "honor_continuity"},
            action_packets=[
                {
                    "proposal_id": "ap-src-identity-1",
                    "origin": "counterpart_request",
                    "intent": "artifact:rerun_search",
                    "status": "completed",
                    "risk": "read",
                    "requires_approval": False,
                    "tool_name": "reacquire_artifact",
                    "result_summary": "已重新接回检索结果 Persistence v2。",
                    "writeback_ready": True,
                }
            ],
            digital_body_state={
                "active_surface": "tooling",
                "perception_channels": ["dialogue"],
                "action_channels": ["language", "tooling"],
                "access_state": {"mode": "tool_enabled"},
                "resource_state": {
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "search_result",
                    "active_artifact_label": "Persistence",
                    "artifact_carrier": " source_ref ",
                    "artifact_source_ref_ids": ["21", "21", "17", "0", -1],
                    "preferred_source_ref_id": "21",
                    "preferred_anchor_reason": " Primary_More_Current ",
                    "artifact_source_url": " https://docs.langchain.com/oss/python/langgraph/persistence ",
                    "artifact_source_query": " langgraph persistence checkpointer thread recovery ",
                    "artifact_source_title": " Persistence v2 ",
                    "artifact_source_tool_name": " search_web ",
                },
            },
        )

        consequence = snapshot["digital_body_consequence"]
        self.assertEqual(consequence["artifact_carrier"], "source_ref")
        self.assertEqual(consequence["artifact_source_ref_ids"], [21, 17])
        self.assertEqual(consequence["preferred_source_ref_id"], 21)
        self.assertEqual(consequence["preferred_anchor_reason"], "primary_more_current")
        self.assertEqual(
            consequence["artifact_source_url"],
            "https://docs.langchain.com/oss/python/langgraph/persistence",
        )
        self.assertEqual(
            consequence["artifact_source_query"],
            "langgraph persistence checkpointer thread recovery",
        )
        self.assertEqual(consequence["artifact_source_title"], "Persistence v2")
        self.assertEqual(consequence["artifact_source_tool_name"], "search_web")

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
                    "workspace_root": "E:/runtime/workspaces/lab-notes",
                    "reacquisition_mode": "reopen_file",
                    "preview": "# plan\nkeep going\n",
                    "exists": True,
                },
            }
        ],
            "action_trace": [{"proposal_id": "ap-1", "status": "completed", "event": "completed"}],
            "autonomy_block_reason": "",
            "digital_body_consequence": {
                "kind": "artifact_reacquired",
                "summary": "已经把 plan.md 重新接回当前上下文。",
                "artifact_continuity": "attached",
                "active_artifact_kind": "file",
                "active_artifact_ref": "notes/plan.md",
                "active_artifact_label": "plan.md",
                "artifact_reacquisition_mode": "reopen_file",
                "workspace_root": "E:/runtime/workspaces/lab-notes",
            },
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
        self.assertEqual(resolved_artifact_context["workspace_root"], "E:/runtime/workspaces/lab-notes")
        self.assertEqual(resolve_action_trace(action_trace=[], reconsolidation_snapshot=reconsolidation_snapshot)[0]["event"], "completed")
        self.assertEqual(
            resolve_digital_body_consequence(
                digital_body_consequence={},
                reconsolidation_snapshot=reconsolidation_snapshot,
            )["workspace_root"],
            "E:/runtime/workspaces/lab-notes",
        )
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

    def test_reconsolidation_snapshot_distinguishes_skill_install_usage_and_blocked_mutation(self):
        source_body = {
            "active_surface": "tooling",
            "perception_channels": ["dialogue", "source_ref"],
            "action_channels": ["language", "structured_action", "tooling"],
            "world_surfaces": ["source_ref", "saved_material"],
            "access_state": {"mode": "tool_enabled", "network_access": "enabled"},
            "resource_state": {
                "artifact_continuity": "attached",
                "active_artifact_kind": "search_result",
                "active_artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                "active_artifact_label": "LangGraph Persistence",
                "artifact_carrier": "source_ref",
                "artifact_source_ref_ids": [21, 17],
                "preferred_source_ref_id": 21,
                "preferred_anchor_reason": "primary_more_current",
                "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                "artifact_source_query": "langgraph persistence checkpointer thread",
                "artifact_source_title": "LangGraph Persistence",
                "artifact_source_tool_name": "search_web",
            },
        }
        session_skill_state = {
            "catalog_version": "skills-v1",
            "catalog_entries": [
                {
                    "skill_id": "source-ref-anchor-review",
                    "name": "source-ref-anchor-review",
                    "description": "Read continuity-focused source materials",
                    "version": "1.0.0",
                    "status": "authored_local",
                }
            ],
            "active_skill_ids": ["source-ref-anchor-review"],
            "active_skill_entries": [
                {
                    "skill_id": "source-ref-anchor-review",
                    "name": "source-ref-anchor-review",
                    "description": "Read continuity-focused source materials",
                    "version": "1.0.0",
                    "status": "authored_local",
                    "allowed_tools": ["search_web", "inspect_source_ref"],
                }
            ],
        }

        install_snapshot = build_reconsolidation_snapshot(
            current_event={"kind": "user_utterance"},
            appraisal={"interaction_frame": "task"},
            world_model_state={},
            semantic_narrative_profile={},
            latent_state={"self_coherence": 0.8},
            emotion_state={"label": "focused"},
            bond_state={"trust": 0.6},
            behavior_action={"interaction_mode": "tooling"},
            action_packets=[
                build_tool_action_packet(
                    tool_name="install_skill",
                    proposal_id="ap-skill-install-1",
                    args={
                        "skill_id": "source-ref-anchor-review",
                        "resolved_version": "1.0.0",
                        "source": "local_authored",
                        "hash": "abc123",
                        "requested_permissions": ["filesystem_read"],
                        "sandbox_profiles": [],
                        "verification_summary": "local authored skill",
                    },
                    action="approve",
                    status="completed",
                    result_summary="installed source-ref-anchor-review@1.0.0",
                )
            ],
            digital_body_state=source_body,
            session_skill_state=session_skill_state,
        )
        blocked_snapshot = build_reconsolidation_snapshot(
            current_event={"kind": "user_utterance"},
            appraisal={"interaction_frame": "task"},
            world_model_state={},
            semantic_narrative_profile={},
            latent_state={"self_coherence": 0.8},
            emotion_state={"label": "focused"},
            bond_state={"trust": 0.6},
            behavior_action={"interaction_mode": "tooling"},
            action_packets=[
                build_tool_action_packet(
                    tool_name="install_skill",
                    proposal_id="ap-skill-blocked-1",
                    args={
                        "skill_id": "blocked-anchor-pack",
                        "resolved_version": "1.0.0",
                        "source": "official_registry",
                        "hash": "blocked123",
                        "requested_permissions": ["filesystem_read"],
                        "sandbox_profiles": [],
                        "verification_summary": "registry verified",
                    },
                    action="approve",
                    status="blocked",
                    result_summary="skill install blocked",
                    block_reason="operator rejected mutation",
                )
            ],
            digital_body_state=source_body,
            session_skill_state={},
        )
        usage_snapshot = build_reconsolidation_snapshot(
            current_event={"kind": "user_utterance"},
            appraisal={"interaction_frame": "task"},
            world_model_state={},
            semantic_narrative_profile={},
            latent_state={"self_coherence": 0.8},
            emotion_state={"label": "focused"},
            bond_state={"trust": 0.6},
            behavior_action={"interaction_mode": "tooling"},
            action_packets=[
                {
                    **build_tool_action_packet(
                        tool_name="search_web",
                        proposal_id="ap-skill-usage-1",
                        args={"query": "langgraph persistence checkpointer"},
                        status="completed",
                        result_summary="searched continuity materials",
                    ),
                    "artifact_context": {
                        "carrier": "source_ref",
                        "artifact_kind": "search_result",
                        "artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                        "artifact_label": "LangGraph Persistence",
                        "source_ref_ids": [21, 17],
                        "preferred_source_ref_id": 21,
                        "preferred_anchor_reason": "primary_more_current",
                        "source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                        "source_query": "langgraph persistence checkpointer thread",
                        "source_title": "LangGraph Persistence",
                        "source_tool_name": "search_web",
                    },
                }
            ],
            digital_body_state=source_body,
            session_skill_state=session_skill_state,
        )

        self.assertEqual(install_snapshot["digital_body_consequence"]["kind"], "skill_install_completed")
        self.assertEqual(install_snapshot["digital_body_consequence"]["skill_effects"][0]["skill_id"], "source-ref-anchor-review")
        self.assertEqual(blocked_snapshot["digital_body_consequence"]["kind"], "skill_mutation_blocked")
        self.assertEqual(blocked_snapshot["digital_body_consequence"]["skill_effects"][0]["status"], "blocked")
        self.assertEqual(usage_snapshot["digital_body_consequence"]["kind"], "skill_usage_completed")
        self.assertEqual(usage_snapshot["skill_effects"][0]["operation"], "use")
        self.assertEqual(usage_snapshot["digital_body_consequence"]["skill_effects"][0]["skill_id"], "source-ref-anchor-review")

    def test_reconsolidation_snapshot_preserves_sandbox_phase2_isolated_runner_identity(self):
        packet = build_tool_action_packet(
            tool_name="execute_workspace_command",
            proposal_id="ap-sandbox-phase2-writeback",
            args={"argv": ["pytest", "-q", "tests/test_sandbox_phase2_repo_fixture.py"]},
            action="approve",
            status="completed",
            result_summary="sandbox phase2 done",
            execution_spec={
                "executor": "pytest",
                "profile": "pytest",
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
            execution_preview={
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
            execution_result={
                "run_id": "ap-sandbox-phase2-writeback",
                "status": "completed",
                "exit_code": 0,
                "duration_ms": 52,
                "stdout_log_ref": "E:/repo/amadeus-thread0/.amadeus/sandbox-runs/ap-sandbox-phase2-writeback/stdout.txt",
                "stderr_log_ref": "E:/repo/amadeus-thread0/.amadeus/sandbox-runs/ap-sandbox-phase2-writeback/stderr.txt",
                "produced_artifacts": [],
                "error_summary": "",
            },
        )
        snapshot = build_reconsolidation_snapshot(
            current_event={"kind": "user_utterance"},
            appraisal={"interaction_frame": "task"},
            world_model_state={},
            semantic_narrative_profile={},
            latent_state={"self_coherence": 0.82},
            emotion_state={"label": "focused"},
            bond_state={"trust": 0.6},
            behavior_action={"interaction_mode": "tooling"},
            action_packets=[packet],
            digital_body_state={
                "active_surface": "tooling",
                "perception_channels": ["dialogue", "filesystem"],
                "action_channels": ["language", "structured_action", "tooling"],
                "world_surfaces": ["filesystem", "sandbox"],
                "access_state": {
                    "mode": "tool_enabled",
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
                    },
                },
                "resource_state": {
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "workspace",
                    "active_artifact_ref": "E:/repo/amadeus-thread0",
                    "active_artifact_label": "amadeus-thread0",
                    "artifact_carrier": "filesystem",
                    "workspace_root": "E:/repo/amadeus-thread0",
                },
            },
        )

        consequence = snapshot["digital_body_consequence"]
        self.assertEqual(consequence["kind"], "sandbox_execution_completed")
        self.assertEqual(consequence["sandbox_runner_kind"], "docker_isolated_runner")
        self.assertEqual(consequence["sandbox_network_policy"], "none")
        self.assertEqual(consequence["workspace_root_kind"], "attached_repo_root")


if __name__ == "__main__":
    unittest.main()
