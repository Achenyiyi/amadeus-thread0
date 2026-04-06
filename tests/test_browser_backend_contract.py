from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from amadeus_thread0.runtime.backend_api import BackendAPI


class _MinimalMemoryStore:
    def list_revision_traces(self, limit: int = 60):
        return []

    def list_semantic_self_narratives(self, limit: int = 20):
        return []

    def list_counterpart_assessment_history(self, limit: int = 12):
        return []

    def list_proactive_continuity_history(self, limit: int = 12):
        return []


class _BrowserBackendSession:
    def __init__(self) -> None:
        self.memory_store = _MinimalMemoryStore()

    def build_evolution_summary(self, *, state_values=None):
        values = state_values if isinstance(state_values, dict) else {}
        digital_body = values.get("digital_body_state") if isinstance(values.get("digital_body_state"), dict) else {}
        consequence = values.get("digital_body_consequence") if isinstance(values.get("digital_body_consequence"), dict) else {}
        return {
            "digital_body": dict(digital_body),
            "digital_body_consequence": dict(consequence),
            "current_turn": {
                "digital_body_surface": str(digital_body.get("active_surface") or "").strip(),
                "digital_body_access_mode": str((digital_body.get("access_state") or {}).get("mode") or "").strip()
                if isinstance(digital_body.get("access_state"), dict)
                else "",
                "digital_body_consequence_kind": str(consequence.get("kind") or "").strip(),
                "digital_body_consequence_summary": str(consequence.get("summary") or "").strip(),
            },
        }

    def extract_final_text(self, values, *, streamed_text=""):
        data = values if isinstance(values, dict) else {}
        return str(data.get("final_text") or "").strip() or str(streamed_text or "").strip()


class BrowserBackendContractTests(unittest.TestCase):
    def _build_api(self) -> BackendAPI:
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        root = Path(tempdir.name)
        checkpoint_db = root / "checkpoints.sqlite"
        checkpoint_db.write_bytes(b"x")
        runtime_bundle = SimpleNamespace(
            thread_id="thread-browser",
            backend_session=_BrowserBackendSession(),
            memory_admin=SimpleNamespace(snapshot_view=lambda: {}),
            settings=SimpleNamespace(
                checkpoint_db_path=checkpoint_db,
                data_dir=root,
                model_provider="synthetic",
                model_name="browser-contract",
                model_base_url="",
                runtime_mode="eval",
            ),
        )
        return BackendAPI(runtime_bundle=runtime_bundle, base_data_dir=root, cwd=root)

    def test_turn_and_event_responses_surface_completed_browser_fields(self):
        api = self._build_api()
        state_values = {
            "final_text": "The live browser page is open and continuous.",
            "current_event": {"kind": "user_utterance"},
            "digital_body_state": {
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
                    "action_packet_count": 1,
                    "completed_packet_count": 1,
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "page",
                    "active_artifact_ref": "page:page-1",
                    "active_artifact_label": "Next Page",
                    "artifact_carrier": "browser_page",
                    "artifact_source_url": "file:///tmp/next.html",
                    "browser_profile_id": "thread-browser",
                    "browser_tab_id": "tab-1",
                    "workspace_root": "E:/runtime/workspace",
                },
            },
            "action_packets": [
                {
                    "proposal_id": "ap-browser-open-1",
                    "origin": "motive_goal",
                    "intent": "browser:open_url",
                    "status": "completed",
                    "risk": "read",
                    "requires_approval": False,
                    "tool_name": "browser_open_url",
                    "result_summary": "Opened the live browser page and kept the page continuity attached.",
                    "writeback_ready": True,
                    "browser_execution_spec": {
                        "operation": "open_url",
                        "profile_id": "thread-browser",
                        "navigation_url": "file:///tmp/next.html",
                        "allowed_roots": ["E:/runtime/workspace"],
                        "browser_downloads_root": "E:/runtime/browser/downloads/thread-browser",
                        "timeout_s": 20,
                        "wait_until": "load",
                    },
                    "browser_execution_preview": {
                        "runner_kind": "playwright_persistent_context",
                        "isolation_level": "persistent_profile_runtime",
                        "operation": "open_url",
                        "profile_id": "thread-browser",
                        "page_url": "file:///tmp/next.html",
                        "page_title": "Next Page",
                        "allowed_roots": ["E:/runtime/workspace"],
                        "downloads_root": "E:/runtime/browser/downloads/thread-browser",
                        "timeout_s": 20,
                        "verification_summary": "open the requested page in the persistent browser profile",
                    },
                    "browser_execution_result": {
                        "run_id": "ap-browser-open-1",
                        "status": "completed",
                        "profile_id": "thread-browser",
                        "page_id": "page-1",
                        "tab_id": "tab-1",
                        "url": "file:///tmp/next.html",
                        "title": "Next Page",
                        "action_kind": "open_url",
                        "target_ref": "",
                        "duration_ms": 42,
                        "active_tab_count": 1,
                        "last_action_status": "completed",
                        "download_path": "",
                        "upload_source": "",
                        "error_summary": "",
                        "manual_takeover_required": False,
                    },
                }
            ],
            "digital_body_consequence": {
                "kind": "browser_navigation_completed",
                "summary": "The requested page is now open in the live browser runtime.",
                "browser_run_id": "ap-browser-open-1",
                "browser_profile_id": "thread-browser",
                "browser_page_id": "page-1",
                "browser_tab_id": "tab-1",
                "browser_url": "file:///tmp/next.html",
                "browser_title": "Next Page",
                "browser_last_action_kind": "open_url",
                "browser_last_exit_status": "completed",
            },
        }

        turn = api.build_turn_response(state_values=state_values, streamed_text="ignored").payload
        event = api.build_event_round_response(state_values=state_values, final_text="The live browser page is open and continuous.").payload

        for payload in (turn, event):
            packet = payload["autonomy"]["action_packets"][0]
            self.assertEqual(packet["intent"], "browser:open_url")
            self.assertEqual(packet["browser_execution_result"]["run_id"], "ap-browser-open-1")
            self.assertEqual(payload["digital_body"]["access_state"]["browser_runtime_state"]["last_run_id"], "ap-browser-open-1")
            self.assertEqual(payload["digital_body"]["resource_state"]["browser_profile_id"], "thread-browser")
            self.assertEqual(payload["digital_body_consequence"]["kind"], "browser_navigation_completed")
            self.assertEqual(payload["digital_body_consequence"]["browser_tab_id"], "tab-1")

    def test_turn_response_surfaces_pending_browser_approval_preview(self):
        api = self._build_api()
        state_values = {
            "current_event": {"kind": "user_utterance"},
            "autonomy_intent": {"mode": "approval_pending", "origin": "counterpart_request", "primary_proposal_id": "ap-browser-click-1"},
            "action_packets": [
                {
                    "proposal_id": "ap-browser-click-1",
                    "origin": "counterpart_request",
                    "intent": "browser:click",
                    "status": "awaiting_approval",
                    "risk": "external_mutation",
                    "requires_approval": True,
                    "tool_name": "browser_click",
                    "browser_execution_spec": {
                        "operation": "click",
                        "profile_id": "thread-browser",
                        "page_ref": "page:page-1",
                        "target_ref": "e2",
                        "allowed_roots": ["E:/runtime/workspace"],
                        "browser_downloads_root": "E:/runtime/browser/downloads/thread-browser",
                        "timeout_s": 20,
                    },
                    "browser_execution_preview": {
                        "runner_kind": "playwright_persistent_context",
                        "isolation_level": "persistent_profile_runtime",
                        "operation": "click",
                        "profile_id": "thread-browser",
                        "page_ref": "page:page-1",
                        "page_url": "file:///tmp/index.html",
                        "page_title": "Start Page",
                        "target_ref": "e2",
                        "target_label": "Approve action",
                        "allowed_roots": ["E:/runtime/workspace"],
                        "downloads_root": "E:/runtime/browser/downloads/thread-browser",
                        "timeout_s": 20,
                        "verification_summary": "click the requested page element in the current persistent browser context",
                    },
                }
            ],
            "pending_action_proposal": {
                "proposal_id": "ap-browser-click-1",
                "origin": "counterpart_request",
                "intent": "browser:click",
                "status": "awaiting_approval",
                "risk": "external_mutation",
                "requires_approval": True,
                "browser_execution_preview": {
                    "runner_kind": "playwright_persistent_context",
                    "isolation_level": "persistent_profile_runtime",
                    "operation": "click",
                    "profile_id": "thread-browser",
                    "page_ref": "page:page-1",
                    "page_url": "file:///tmp/index.html",
                    "page_title": "Start Page",
                    "target_ref": "e2",
                    "target_label": "Approve action",
                    "allowed_roots": ["E:/runtime/workspace"],
                    "downloads_root": "E:/runtime/browser/downloads/thread-browser",
                    "timeout_s": 20,
                    "verification_summary": "click the requested page element in the current persistent browser context",
                },
            },
            "digital_body_state": {
                "active_surface": "approval_gate",
                "perception_channels": ["dialogue", "browser"],
                "action_channels": ["language", "structured_action", "approval_gate", "tooling"],
                "world_surfaces": ["browser", "filesystem"],
                "access_state": {
                    "mode": "approval_pending",
                    "pending_approval_count": 1,
                    "external_mutation_pending": True,
                    "browser_session": "present",
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
                    "action_packet_count": 1,
                    "pending_approval_count": 1,
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "page",
                    "active_artifact_ref": "page:page-1",
                    "active_artifact_label": "Start Page",
                    "artifact_carrier": "browser_page",
                    "artifact_source_url": "file:///tmp/index.html",
                    "browser_profile_id": "thread-browser",
                    "browser_tab_id": "tab-1",
                },
            },
        }

        payload = api.build_turn_response(state_values=state_values, streamed_text="ignored").payload

        self.assertEqual(payload["autonomy"]["intent"]["mode"], "approval_pending")
        self.assertEqual(payload["autonomy"]["pending_approval"]["proposal_id"], "ap-browser-click-1")
        self.assertEqual(payload["autonomy"]["pending_approval"]["browser_execution_preview"]["operation"], "click")
        self.assertEqual(payload["digital_body"]["access_state"]["mode"], "approval_pending")
        self.assertEqual(payload["digital_body"]["resource_state"]["artifact_carrier"], "browser_page")


if __name__ == "__main__":
    unittest.main()
