from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from amadeus_thread0.runtime.backend_session import BackendSession


class FakeState:
    def __init__(self, values, *, config=None, next_items=None):
        self.values = values
        self.config = config or {"configurable": {}}
        self.next = list(next_items or [])


class AIMessageChunk:
    def __init__(self, content: str):
        self.content = content


class FakeStreamGraph:
    def __init__(
        self,
        stream_rows,
        state_values,
        *,
        state_config=None,
        history_rows=None,
        state_values_by_checkpoint=None,
    ):
        self._stream_rows = list(stream_rows)
        self._state_values = dict(state_values)
        self._state_config = dict(state_config or {"configurable": {}})
        self._history_rows = list(history_rows or [])
        self._state_values_by_checkpoint = {
            str(key): dict(value)
            for key, value in (state_values_by_checkpoint or {}).items()
            if isinstance(value, dict)
        }
        self.updated_states = []
        self.get_state_calls = []
        self.get_state_history_calls = []

    def stream(self, payload, config=None, stream_mode=None):
        for row in self._stream_rows:
            yield row

    def get_state(self, config=None):
        self.get_state_calls.append(config)
        configurable = (config or {}).get("configurable") if isinstance(config, dict) else {}
        checkpoint_id = str((configurable or {}).get("checkpoint_id") or "").strip()
        snapshot_config = dict(self._state_config)
        base_configurable = (
            dict(snapshot_config.get("configurable") or {})
            if isinstance(snapshot_config.get("configurable"), dict)
            else {}
        )
        if isinstance(configurable, dict) and configurable:
            base_configurable.update(configurable)
        snapshot_config["configurable"] = base_configurable
        if checkpoint_id and checkpoint_id in self._state_values_by_checkpoint:
            return FakeState(self._state_values_by_checkpoint[checkpoint_id], config=snapshot_config)
        return FakeState(self._state_values, config=self._state_config if not checkpoint_id else snapshot_config)

    def get_state_history(self, config=None):
        self.get_state_history_calls.append(config)
        return list(self._history_rows)

    def update_state(self, config, values, as_node=None):
        self.updated_states.append((config, values, as_node))
        if isinstance(values, dict):
            merged = dict(self._state_values)
            merged.update(values)
            self._state_values = merged


class FakeInvokeGraph:
    def __init__(self, before_values, after_values, invoke_rows):
        self._states = [dict(before_values), dict(after_values)]
        self._invoke_rows = list(invoke_rows)
        self.invoke_calls = []

    def get_state(self, config=None):
        idx = 0 if len(self._states) == 1 else 0
        values = self._states.pop(0)
        return FakeState(values)

    def invoke(self, payload, config=None):
        self.invoke_calls.append((payload, config))
        return self._invoke_rows.pop(0)


class FakeMemoryStore:
    def __init__(self):
        self._relationship = {
            "stage": "warming",
            "affinity_score": 0.72,
            "trust_score": 0.74,
            "notes": "逐渐熟悉起来。",
        }
        self._snapshot = {
            "worldline_events": [{"id": 1, "summary": "一起熬夜。"}],
            "commitments": [{"id": 2, "text": "提醒他吃饭。"}],
            "conflict_repair": [{"id": 3, "summary": "误会后重新解释。"}],
            "unresolved_tensions": [{"id": 4, "summary": "还有一点别扭。"}],
            "counterpart_assessment_history": [
                {
                    "id": 10,
                    "summary": "你觉得冈部伦太郎这句是在认真靠近你，不是普通客套。",
                    "stance": "open",
                    "scene": "care_bid",
                    "created_at": 1710000003,
                    "respect_level": 0.76,
                    "reciprocity": 0.72,
                    "boundary_pressure": 0.08,
                    "reliability_read": 0.80,
                    "embodied_context": {
                        "kind": "access_request_pending",
                        "summary": "她已经把动作推进到了审批门口。",
                        "requested_access": ["workspace_write", "human_approval"],
                        "artifact_carrier": "source_ref",
                        "artifact_source_ref_ids": [17],
                        "preferred_source_ref_id": 17,
                        "preferred_anchor_reason": "primary_more_current",
                        "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                        "artifact_source_query": "langgraph persistence checkpointer thread",
                        "artifact_source_title": "Persistence",
                        "artifact_source_tool_name": "search_web",
                        "requested_help": True,
                        "primary_status": "awaiting_approval",
                    },
                }
            ],
            "proactive_continuity_history": [
                {
                    "id": 11,
                    "summary": "前面挂着的窗口没有继续往前推，注意力被自然收回到了自己的节奏里。",
                    "kind": "released_to_self_activity",
                    "trace_family": "own_rhythm_busy_window",
                    "trigger_family": "life_window",
                    "carryover_mode": "own_rhythm",
                    "hold_count": 2,
                    "carryover_strength": 0.53,
                    "recontact_cooldown": 0.47,
                    "presence_residue": 0.33,
                    "ambient_resonance": 0.24,
                    "self_activity_momentum": 0.58,
                    "own_rhythm_bias": 0.61,
                    "counterpart_scene_bias": "busy_not_disrespectful",
                    "semantic_continuity_depth": 0.68,
                    "semantic_identity_gravity": 0.64,
                    "created_at": 1710000004,
                    "primary_motive": "preserve_self_rhythm",
                    "motive_tension": "self_rhythm_vs_contact",
                    "goal_frame": "先让这段窗口自然过去，把注意力收回自己的节奏。",
                    "embodied_context": {
                        "kind": "access_request_pending",
                        "summary": "她已经把动作推进到了审批门口。",
                        "requested_access": ["workspace_write"],
                        "artifact_carrier": "source_ref",
                        "artifact_source_ref_ids": [17],
                        "preferred_source_ref_id": 17,
                        "preferred_anchor_reason": "primary_more_current",
                        "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                        "artifact_source_query": "langgraph persistence checkpointer thread",
                        "artifact_source_title": "Persistence",
                        "artifact_source_tool_name": "search_web",
                        "requested_help": True,
                        "primary_status": "awaiting_approval",
                    },
                }
            ],
            "semantic_self_narratives": [{"id": 5, "text": "她保留自己的判断。"}],
            "revision_traces": [{"id": 6, "reason": "semantic_refresh"}],
        }
        self._timeline = [{"id": 7, "summary": "关系变近", "affinity_delta": 0.1, "trust_delta": 0.2}]
        self._repairs = [{"id": 8, "summary": "慢慢和好"}]
        self._counterpart_history = list(self._snapshot["counterpart_assessment_history"])
        self._proactive_history = list(self._snapshot["proactive_continuity_history"])
        self._sources = [{"id": 9, "tool_name": "web_search", "title": "paper", "url": "https://example.com", "query": "query"}]

    def get_relationship(self):
        return dict(self._relationship)

    def snapshot(self):
        return dict(self._snapshot)

    def list_commitments(self, limit=50):
        return list(self._snapshot.get("commitments", [])[:limit])

    def list_relationship_timeline(self, limit=30):
        return list(self._timeline[:limit])

    def list_conflict_repairs(self, limit=30):
        return list(self._repairs[:limit])

    def list_unresolved_tensions(self, limit=30):
        return list(self._snapshot.get("unresolved_tensions", [])[:limit])

    def list_counterpart_assessment_history(self, limit=30):
        return list(self._counterpart_history[:limit])

    def list_proactive_continuity_history(self, limit=30):
        return list(self._proactive_history[:limit])

    def list_source_refs(self, limit=30):
        return list(self._sources[:limit])


class BackendSessionTests(unittest.TestCase):
    def _assert_backend_session_consequence_surface(self, *, values, expect):
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        summary = session.build_evolution_summary()
        worldline = session.worldline_view()
        persona = session.persona_view()

        summary_views = [
            summary,
            worldline["worldline_summary"],
            persona["evolution_summary"],
        ]
        for built_summary in summary_views:
            digital_body_consequence = (
                built_summary.get("digital_body_consequence")
                if isinstance(built_summary.get("digital_body_consequence"), dict)
                else {}
            )
            self.assertEqual(digital_body_consequence.get("kind"), expect["kind"])
            self.assertEqual(digital_body_consequence.get("primary_tool_name"), expect["primary_tool_name"])
            current_turn = built_summary.get("current_turn") if isinstance(built_summary.get("current_turn"), dict) else {}
            self.assertEqual(current_turn.get("digital_body_consequence_kind"), expect["kind"])
            self.assertEqual(
                current_turn.get("digital_body_consequence_summary"),
                digital_body_consequence.get("summary"),
            )
            self.assertTrue(bool(digital_body_consequence.get("summary")))
            event_residue = (
                built_summary.get("event_residue")
                if isinstance(built_summary.get("event_residue"), dict)
                else {}
            )
            event_bodyfx = (
                event_residue.get("digital_body_consequence")
                if isinstance(event_residue.get("digital_body_consequence"), dict)
                else {}
            )
            self.assertEqual(event_bodyfx.get("kind"), expect["kind"])

            for field in (
                "active_artifact_kind",
                "active_artifact_label",
                "artifact_carrier",
                "artifact_source_ref_ids",
                "artifact_source_tool_name",
                "preferred_source_ref_id",
                "preferred_anchor_reason",
                "session_continuity",
                "artifact_mutation_mode",
                "browser_run_id",
                "browser_profile_id",
                "browser_page_id",
                "browser_tab_id",
                "browser_url",
                "browser_title",
                "browser_last_action_kind",
                "browser_last_exit_status",
                "requested_help",
                "environmental_friction",
            ):
                if field in expect:
                    self.assertEqual(digital_body_consequence.get(field), expect[field])
                    if field in {"preferred_source_ref_id", "preferred_anchor_reason"}:
                        self.assertEqual(event_bodyfx.get(field), expect[field])

            if "preferred_source_ref_id" in expect:
                self.assertEqual(
                    current_turn.get("digital_body_preferred_source_ref_id"),
                    expect["preferred_source_ref_id"],
                )
                self.assertEqual(
                    current_turn.get("digital_body_consequence_preferred_source_ref_id"),
                    expect["preferred_source_ref_id"],
                )
            if "preferred_anchor_reason" in expect:
                self.assertEqual(
                    current_turn.get("digital_body_preferred_anchor_reason"),
                    expect["preferred_anchor_reason"],
                )
                self.assertEqual(
                    current_turn.get("digital_body_consequence_preferred_anchor_reason"),
                    expect["preferred_anchor_reason"],
                )
            if "procedural_growth" in expect:
                self.assertEqual(
                    bool(digital_body_consequence.get("procedural_growth")),
                    expect["procedural_growth"],
                )
                self.assertEqual(
                    bool(current_turn.get("digital_body_procedural_growth")),
                    expect["procedural_growth"],
                )
            if "workspace_root" in expect:
                self.assertEqual(
                    current_turn.get("digital_body_workspace_root"),
                    expect["workspace_root"],
                )

        persona_digital_body = persona.get("digital_body") if isinstance(persona.get("digital_body"), dict) else {}
        persona_bodyfx = (
            persona.get("digital_body_consequence")
            if isinstance(persona.get("digital_body_consequence"), dict)
            else {}
        )
        self.assertEqual(persona_bodyfx.get("kind"), expect["kind"])
        if "active_artifact_kind" in expect:
            self.assertEqual(
                (persona_digital_body.get("resource_state") or {}).get("active_artifact_kind"),
                expect["active_artifact_kind"],
            )
        if "active_artifact_label" in expect:
            self.assertEqual(
                (persona_digital_body.get("resource_state") or {}).get("active_artifact_label"),
                expect["active_artifact_label"],
            )
        if "workspace_root" in expect:
            self.assertEqual(
                (persona_digital_body.get("resource_state") or {}).get("workspace_root"),
                expect["workspace_root"],
            )
        if "preferred_source_ref_id" in expect:
            self.assertEqual(
                (persona_digital_body.get("resource_state") or {}).get("preferred_source_ref_id"),
                expect["preferred_source_ref_id"],
            )
        if "preferred_anchor_reason" in expect:
            self.assertEqual(
                (persona_digital_body.get("resource_state") or {}).get("preferred_anchor_reason"),
                expect["preferred_anchor_reason"],
            )
        if "session_continuity" in expect:
            self.assertEqual(
                (persona_digital_body.get("access_state") or {}).get("session_continuity"),
                expect["session_continuity"],
            )

    def test_build_run_config_consumes_pending_checkpoint_once(self):
        session = BackendSession(graph=object(), memory_store=FakeMemoryStore(), thread_id="thread-a", user_id="okabe")
        run_config, pending_after = session.build_run_config("cp-1")
        self.assertEqual(run_config["configurable"]["thread_id"], "thread-a")
        self.assertEqual(run_config["configurable"]["user_id"], "okabe")
        self.assertEqual(run_config["configurable"]["checkpoint_id"], "cp-1")
        self.assertIsNone(pending_after)

    def test_invoke_stream_collects_call_model_chunks_only(self):
        graph = FakeStreamGraph(
            stream_rows=[
                ("messages", (AIMessageChunk("ignored"), {"langgraph_node": "prepare_turn"})),
                ("messages", (AIMessageChunk("你"), {"langgraph_node": "call_model"})),
                ("messages", (AIMessageChunk("好"), {"langgraph_node": "call_model"})),
                ("values", {"messages": [SimpleNamespace(content="你好")], "emotion_state": {"label": "care"}}),
            ],
            state_values={"messages": [SimpleNamespace(content="你好")]},
        )
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")
        seen = []
        result = session.invoke_stream({"messages": [{"role": "user", "content": "hi"}]}, on_text=seen.append)
        self.assertEqual(result.streamed_text, "你好")
        self.assertEqual(seen, ["你", "好"])
        self.assertEqual(result.values.get("emotion_state"), {"label": "care"})
        self.assertIsNone(result.approval_request)

    def test_invoke_stream_surfaces_tool_approval_request(self):
        graph = FakeStreamGraph(
            stream_rows=[
                (
                    "values",
                    {
                        "__interrupt__": (
                            {
                                "value": {
                                    "kind": "tool_approval",
                                    "source": "memory",
                                    "tool_calls": [
                                        {
                                            "name": "set_profile",
                                            "args": {"key": "timezone", "value": "Asia/Shanghai"},
                                            "proposal_id": "ap-memory-1",
                                        }
                                    ],
                                }
                            },
                        )
                    },
                )
            ],
            state_values={},
        )
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")
        result = session.invoke_stream({"messages": [{"role": "user", "content": "hi"}]})
        self.assertIsNotNone(result.approval_request)
        assert result.approval_request is not None
        self.assertEqual(result.approval_request.kind, "tool_approval")
        self.assertEqual(result.approval_request.source, "memory")
        self.assertEqual(result.approval_request.tool_calls[0]["name"], "set_profile")
        self.assertEqual(result.approval_request.tool_calls[0]["proposal_id"], "ap-memory-1")
        self.assertEqual(result.values["pending_action_proposal"]["proposal_id"], "ap-memory-1")
        self.assertEqual(result.values["pending_action_proposal"]["status"], "awaiting_approval")
        self.assertEqual(result.values["pending_action_proposal"]["risk"], "memory_write")
        self.assertEqual(result.values["autonomy_intent"]["mode"], "approval_pending")
        self.assertEqual(result.values["autonomy_intent"]["primary_proposal_id"], "ap-memory-1")
        self.assertEqual(result.values["action_packets"][0]["proposal_id"], "ap-memory-1")

    def test_invoke_stream_preserves_workspace_mutation_preview_in_approval_request(self):
        graph = FakeStreamGraph(
            stream_rows=[
                (
                    "values",
                    {
                        "__interrupt__": (
                            {
                                "value": {
                                    "kind": "tool_approval",
                                    "source": "dialog",
                                    "tool_calls": [
                                        {
                                            "name": "replace_workspace_lines",
                                            "args": {
                                                "relative_path": "notes/todo.md",
                                                "start_line": 2,
                                                "end_line": 2,
                                                "new_text": "beta v2",
                                            },
                                            "proposal_id": "ap-file-lines-1",
                                            "mutation_preview": {
                                                "tool_name": "replace_workspace_lines",
                                                "can_apply": True,
                                                "mutation_mode": "replace",
                                                "relative_path": "notes/todo.md",
                                                "summary": "todo.md 的 patch 预览已生成，审批通过后会只在当前 workspace 内落地。",
                                                "diff_preview": "--- a/notes/todo.md\n+++ b/notes/todo.md\n@@\n-beta\n+beta v2\n",
                                            },
                                        }
                                    ],
                                }
                            },
                        )
                    },
                )
            ],
            state_values={},
        )
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        result = session.invoke_stream({"messages": [{"role": "user", "content": "hi"}]})

        self.assertIsNotNone(result.approval_request)
        assert result.approval_request is not None
        preview = result.approval_request.tool_calls[0]["mutation_preview"]
        self.assertTrue(preview["can_apply"])
        self.assertEqual(preview["mutation_mode"], "replace")
        self.assertIn("+beta v2", preview["diff_preview"])
        self.assertEqual(result.values["pending_action_proposal"]["proposal_id"], "ap-file-lines-1")
        self.assertEqual(result.values["pending_action_proposal"]["mutation_preview"]["relative_path"], "notes/todo.md")
        self.assertIn("+beta v2", result.values["pending_action_proposal"]["mutation_preview"]["diff_preview"])

    def test_invoke_stream_preserves_sandbox_execution_preview_in_approval_request(self):
        execution_spec = {
            "executor": "python",
            "profile": "python_script",
            "runner_kind": "local_restricted_runner",
            "isolation_level": "host_local_restricted",
            "image_ref": "",
            "network_policy": "host",
            "workspace_root_kind": "runtime_owned",
            "argv": ["python", "emit_artifact.py"],
            "cwd": "E:/runtime/workspaces/lab-notes",
            "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
            "timeout_s": 25,
            "writes_expected": True,
            "expected_artifacts": ["notes/generated.txt"],
        }
        execution_preview = {
            "runner_kind": "local_restricted_runner",
            "isolation_level": "host_local_restricted",
            "image_ref": "",
            "network_policy": "host",
            "workspace_root_kind": "runtime_owned",
            "argv": ["python", "emit_artifact.py"],
            "cwd": "E:/runtime/workspaces/lab-notes",
            "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
            "timeout_s": 25,
            "writes_expected": True,
            "expected_artifacts": ["notes/generated.txt"],
        }
        graph = FakeStreamGraph(
            stream_rows=[
                (
                    "values",
                    {
                        "__interrupt__": (
                            {
                                "value": {
                                    "kind": "tool_approval",
                                    "source": "dialog",
                                    "tool_calls": [
                                        {
                                            "name": "execute_workspace_command",
                                            "args": {
                                                "argv": ["python", "emit_artifact.py"],
                                                "cwd": ".",
                                                "expected_artifacts": ["notes/generated.txt"],
                                            },
                                            "proposal_id": "ap-sandbox-1",
                                            "execution_spec": execution_spec,
                                            "execution_preview": execution_preview,
                                        }
                                    ],
                                }
                            },
                        )
                    },
                )
            ],
            state_values={},
        )
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        result = session.invoke_stream({"messages": [{"role": "user", "content": "run tests"}]})

        self.assertIsNotNone(result.approval_request)
        assert result.approval_request is not None
        self.assertEqual(result.approval_request.tool_calls[0]["proposal_id"], "ap-sandbox-1")
        self.assertEqual(result.approval_request.tool_calls[0]["execution_preview"]["runner_kind"], "local_restricted_runner")
        self.assertEqual(
            result.values["pending_action_proposal"]["intent"],
            "sandbox:execute_workspace_command",
        )
        self.assertEqual(
            result.values["pending_action_proposal"]["execution_spec"]["allowed_roots"],
            ["E:/runtime/workspaces/lab-notes"],
        )
        self.assertEqual(
            result.values["pending_action_proposal"]["execution_preview"]["expected_artifacts"],
            ["notes/generated.txt"],
        )

    def test_resume_stream_keeps_same_execution_spec_for_sandbox_approval(self):
        execution_spec = {
            "executor": "python",
            "profile": "python_script",
            "runner_kind": "local_restricted_runner",
            "isolation_level": "host_local_restricted",
            "image_ref": "",
            "network_policy": "host",
            "workspace_root_kind": "runtime_owned",
            "argv": ["python", "emit_artifact.py"],
            "cwd": "E:/runtime/workspaces/lab-notes",
            "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
            "timeout_s": 25,
            "writes_expected": True,
            "expected_artifacts": ["notes/generated.txt"],
        }
        execution_preview = {
            "runner_kind": "local_restricted_runner",
            "isolation_level": "host_local_restricted",
            "image_ref": "",
            "network_policy": "host",
            "workspace_root_kind": "runtime_owned",
            "argv": ["python", "emit_artifact.py"],
            "cwd": "E:/runtime/workspaces/lab-notes",
            "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
            "timeout_s": 25,
            "writes_expected": True,
            "expected_artifacts": ["notes/generated.txt"],
        }
        completed_packet = {
            "proposal_id": "ap-sandbox-2",
            "origin": "motive_goal",
            "intent": "sandbox:execute_workspace_command",
            "status": "completed",
            "risk": "external_mutation",
            "requires_approval": True,
            "tool_name": "execute_workspace_command",
            "execution_spec": execution_spec,
            "execution_preview": execution_preview,
            "execution_result": {
                "run_id": "ap-sandbox-2",
                "status": "completed",
                "exit_code": 0,
                "duration_ms": 84,
                "stdout_log_ref": "E:/runtime/workspaces/lab-notes/.amadeus/sandbox-runs/ap-sandbox-2/stdout.txt",
                "stderr_log_ref": "E:/runtime/workspaces/lab-notes/.amadeus/sandbox-runs/ap-sandbox-2/stderr.txt",
                "produced_artifacts": ["E:/runtime/workspaces/lab-notes/notes/generated.txt"],
                "error_summary": "",
            },
            "writeback_ready": True,
        }

        class FakeResumableStreamGraph(FakeStreamGraph):
            def __init__(self):
                super().__init__(
                    stream_rows=[],
                    state_values={},
                )
                self.initial_rows = [
                    (
                        "values",
                        {
                            "__interrupt__": (
                                {
                                    "value": {
                                        "kind": "tool_approval",
                                        "source": "dialog",
                                        "tool_calls": [
                                            {
                                                "name": "execute_workspace_command",
                                                "args": {
                                                    "argv": ["python", "emit_artifact.py"],
                                                    "cwd": ".",
                                                    "expected_artifacts": ["notes/generated.txt"],
                                                },
                                                "proposal_id": "ap-sandbox-2",
                                                "execution_spec": execution_spec,
                                                "execution_preview": execution_preview,
                                            }
                                        ],
                                    }
                                },
                            )
                        },
                    )
                ]
                self.resume_rows = [("values", {"action_packets": [completed_packet], "pending_action_proposal": {}})]

            def stream(self, payload, config=None, stream_mode=None):
                rows = self.initial_rows if isinstance(payload, dict) else self.resume_rows
                for row in rows:
                    yield row

        graph = FakeResumableStreamGraph()
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        first = session.invoke_stream({"messages": [{"role": "user", "content": "run tests"}]})
        resumed = session.resume_stream([{"action": "approve"}])

        self.assertEqual(first.values["pending_action_proposal"]["execution_spec"], execution_spec)
        self.assertEqual(resumed.values["action_packets"][0]["execution_spec"], execution_spec)
        self.assertEqual(
            resumed.values["action_packets"][0]["execution_result"]["produced_artifacts"],
            ["E:/runtime/workspaces/lab-notes/notes/generated.txt"],
        )

    def test_invoke_stream_preserves_browser_execution_preview_in_approval_request(self):
        browser_execution_spec = {
            "operation": "click",
            "profile_id": "thread-browser",
            "page_ref": "page:page-1",
            "target_ref": "e2",
            "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
            "browser_downloads_root": "E:/runtime/browser/downloads/thread-browser",
            "timeout_s": 20,
            "wait_until": "load",
        }
        browser_execution_preview = {
            "runner_kind": "playwright_persistent_context",
            "isolation_level": "persistent_profile_runtime",
            "operation": "click",
            "profile_id": "thread-browser",
            "page_ref": "page:page-1",
            "page_url": "https://example.com/tasks",
            "page_title": "Task Board",
            "target_ref": "e2",
            "target_label": "Approve action",
            "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
            "downloads_root": "E:/runtime/browser/downloads/thread-browser",
            "timeout_s": 20,
            "verification_summary": "click the requested page element in the current persistent browser context",
        }
        graph = FakeStreamGraph(
            stream_rows=[
                (
                    "values",
                    {
                        "__interrupt__": (
                            {
                                "value": {
                                    "kind": "tool_approval",
                                    "source": "dialog",
                                    "tool_calls": [
                                        {
                                            "name": "browser_click",
                                            "args": {"target_ref": "e2"},
                                            "proposal_id": "ap-browser-click-approve-1",
                                            "browser_execution_spec": browser_execution_spec,
                                            "browser_execution_preview": browser_execution_preview,
                                        }
                                    ],
                                }
                            },
                        )
                    },
                )
            ],
            state_values={},
        )
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        result = session.invoke_stream({"messages": [{"role": "user", "content": "click it"}]})

        self.assertIsNotNone(result.approval_request)
        assert result.approval_request is not None
        self.assertEqual(result.approval_request.tool_calls[0]["proposal_id"], "ap-browser-click-approve-1")
        self.assertEqual(
            result.approval_request.tool_calls[0]["browser_execution_preview"]["runner_kind"],
            "playwright_persistent_context",
        )
        self.assertEqual(
            result.values["pending_action_proposal"]["intent"],
            "browser:click",
        )
        self.assertEqual(
            result.values["pending_action_proposal"]["browser_execution_spec"]["target_ref"],
            "e2",
        )
        self.assertEqual(
            result.values["pending_action_proposal"]["browser_execution_preview"]["page_title"],
            "Task Board",
        )

    def test_resume_stream_keeps_same_browser_execution_spec_for_browser_approval(self):
        browser_execution_spec = {
            "operation": "download_click",
            "profile_id": "thread-browser",
            "page_ref": "page:page-1",
            "target_ref": "e3",
            "download_target": "E:/runtime/workspaces/lab-notes/downloads/payload.txt",
            "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
            "browser_downloads_root": "E:/runtime/browser/downloads/thread-browser",
            "timeout_s": 20,
            "wait_until": "load",
        }
        browser_execution_preview = {
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
        }
        completed_packet = {
            "proposal_id": "ap-browser-download-approve-1",
            "origin": "motive_goal",
            "intent": "browser:download_click",
            "status": "completed",
            "risk": "external_mutation",
            "requires_approval": True,
            "tool_name": "browser_download_click",
            "browser_execution_spec": browser_execution_spec,
            "browser_execution_preview": browser_execution_preview,
            "browser_execution_result": {
                "run_id": "ap-browser-download-approve-1",
                "status": "completed",
                "profile_id": "thread-browser",
                "page_id": "page-1",
                "tab_id": "tab-1",
                "url": "https://example.com/report",
                "title": "Report",
                "action_kind": "download_click",
                "target_ref": "e3",
                "duration_ms": 55,
                "active_tab_count": 1,
                "last_action_status": "completed",
                "download_path": "E:/runtime/workspaces/lab-notes/downloads/payload.txt",
                "upload_source": "",
                "error_summary": "",
                "manual_takeover_required": False,
            },
            "writeback_ready": True,
        }

        class FakeBrowserResumableStreamGraph(FakeStreamGraph):
            def __init__(self):
                super().__init__(stream_rows=[], state_values={})
                self.initial_rows = [
                    (
                        "values",
                        {
                            "__interrupt__": (
                                {
                                    "value": {
                                        "kind": "tool_approval",
                                        "source": "dialog",
                                        "tool_calls": [
                                            {
                                                "name": "browser_download_click",
                                                "args": {"target_ref": "e3"},
                                                "proposal_id": "ap-browser-download-approve-1",
                                                "browser_execution_spec": browser_execution_spec,
                                                "browser_execution_preview": browser_execution_preview,
                                            }
                                        ],
                                    }
                                },
                            )
                        },
                    )
                ]
                self.resume_rows = [("values", {"action_packets": [completed_packet], "pending_action_proposal": {}})]

            def stream(self, payload, config=None, stream_mode=None):
                rows = self.initial_rows if isinstance(payload, dict) else self.resume_rows
                for row in rows:
                    yield row

        graph = FakeBrowserResumableStreamGraph()
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        first = session.invoke_stream({"messages": [{"role": "user", "content": "download it"}]})
        resumed = session.resume_stream([{"action": "approve"}])

        self.assertEqual(
            first.values["pending_action_proposal"]["browser_execution_spec"]["profile_id"],
            browser_execution_spec["profile_id"],
        )
        self.assertEqual(
            first.values["pending_action_proposal"]["browser_execution_spec"]["target_ref"],
            browser_execution_spec["target_ref"],
        )
        self.assertEqual(
            first.values["pending_action_proposal"]["browser_execution_spec"]["download_target"],
            browser_execution_spec["download_target"],
        )
        self.assertEqual(resumed.values["action_packets"][0]["browser_execution_spec"], browser_execution_spec)
        self.assertEqual(
            resumed.values["action_packets"][0]["browser_execution_result"]["download_path"],
            "E:/runtime/workspaces/lab-notes/downloads/payload.txt",
        )

    def test_resume_stream_keeps_same_resolved_payload_for_skill_install_approval(self):
        resolved_args = {
            "skill_id": "pytest-helper",
            "resolved_version": "1.1.0",
            "source": "official_registry",
            "hash": "abc123",
            "requested_permissions": ["filesystem_read"],
            "sandbox_profiles": ["workspace_write"],
            "verification_summary": "registry verified",
        }
        completed_packet = {
            "proposal_id": "ap-skill-install-1",
            "origin": "capability_upgrade",
            "intent": "skills:install",
            "status": "completed",
            "risk": "external_mutation",
            "requires_approval": True,
            "tool_name": "install_skill",
            "tool_args": resolved_args,
            "result_summary": "installed pytest-helper@1.1.0",
            "writeback_ready": True,
        }

        class FakeSkillResumableStreamGraph(FakeStreamGraph):
            def __init__(self):
                super().__init__(stream_rows=[], state_values={})
                self.initial_rows = [
                    (
                        "values",
                        {
                            "__interrupt__": (
                                {
                                    "value": {
                                        "kind": "tool_approval",
                                        "source": "skills",
                                        "tool_calls": [
                                            {
                                                "name": "install_skill",
                                                "args": resolved_args,
                                                "proposal_id": "ap-skill-install-1",
                                                "skill_preview": {
                                                    "operation": "install_skill",
                                                    **resolved_args,
                                                },
                                            }
                                        ],
                                    }
                                },
                            )
                        },
                    )
                ]
                self.resume_rows = [("values", {"action_packets": [completed_packet], "pending_action_proposal": {}})]

            def stream(self, payload, config=None, stream_mode=None):
                rows = self.initial_rows if isinstance(payload, dict) else self.resume_rows
                for row in rows:
                    yield row

        graph = FakeSkillResumableStreamGraph()
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        first = session.invoke_stream({"messages": [{"role": "user", "content": "install pytest helper"}]})
        resumed = session.resume_stream([{"action": "approve"}])

        self.assertIsNotNone(first.approval_request)
        assert first.approval_request is not None
        self.assertEqual(first.approval_request.source, "skills")
        self.assertEqual(first.approval_request.tool_calls[0]["proposal_id"], "ap-skill-install-1")
        self.assertEqual(first.approval_request.tool_calls[0]["skill_preview"]["hash"], "abc123")
        self.assertEqual(first.values["pending_action_proposal"]["proposal_id"], "ap-skill-install-1")
        self.assertEqual(first.values["pending_action_proposal"]["tool_args"]["resolved_version"], "1.1.0")
        self.assertEqual(resumed.values["action_packets"][0]["proposal_id"], "ap-skill-install-1")
        self.assertEqual(resumed.values["action_packets"][0]["tool_args"], resolved_args)

    def test_invoke_stream_synthesizes_access_request_from_pending_access_packet(self):
        packet = {
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
                    "target": "account_login / cookies",
                    "status": "awaiting_approval",
                    "requires_approval": True,
                    "note": "这一步需要先向你请求账号入口和 cookies。",
                }
            ],
            "expected_effect": "这一步需要先向你请求账号入口和 cookies。",
        }
        values = {
            "current_event": {"kind": "user_utterance"},
            "action_packets": [packet],
            "pending_action_proposal": dict(packet),
            "session_context": {
                "digital_body_hints": {
                    "browser_session": "missing",
                    "account_state": "logged_out",
                    "cookie_state": "expired",
                    "missing_access": ["account_login", "cookies"],
                    "requestable_access": ["account_login", "cookies", "human_approval"],
                    "requested_help": True,
                    "access_acquire_proposals": [
                        {
                            "target": "account_login",
                            "mode": "operator_login",
                            "summary": "先把账号登录补回来。",
                            "operator_action": "登录目标账号。",
                            "grants": ["account_login", "browser_session"],
                            "requires_operator": True,
                        }
                    ],
                    "selected_access_proposal": {
                        "target": "account_login",
                        "mode": "operator_login",
                        "summary": "先把账号登录补回来。",
                        "operator_action": "登录目标账号。",
                        "grants": ["account_login", "browser_session"],
                        "requires_operator": True,
                    },
                }
            },
            "digital_body_state": {
                "access_state": {
                    "mode": "approval_pending",
                    "requestable_access": ["account_login", "cookies", "human_approval"],
                    "missing_access": ["account_login", "cookies"],
                    "session_recovery_mode": "restore_cookies",
                    "browser_session": "missing",
                    "account_state": "logged_out",
                    "cookie_state": "expired",
                }
            },
        }
        graph = FakeStreamGraph(
            stream_rows=[("values", values)],
            state_values=values,
        )
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        result = session.invoke_stream({"messages": [{"role": "user", "content": "hi"}]})

        self.assertIsNotNone(result.approval_request)
        assert result.approval_request is not None
        self.assertEqual(result.approval_request.kind, "access_request")
        self.assertEqual(result.approval_request.source, "access")
        self.assertEqual(result.approval_request.payload["proposal_id"], "ap-access-help-1")
        self.assertEqual(result.approval_request.tool_calls[0]["name"], "access_request_help")
        self.assertIn("account_login", result.approval_request.tool_calls[0]["args"]["requested_access"])
        self.assertIn("cookies", result.approval_request.tool_calls[0]["args"]["missing_access"])
        proposals = result.approval_request.tool_calls[0]["args"].get("access_acquire_proposals") or []
        self.assertTrue(proposals)
        self.assertEqual(proposals[0]["target"], "account_login")
        self.assertEqual(proposals[0]["mode"], "operator_login")
        self.assertEqual(result.values["pending_action_proposal"]["proposal_id"], "ap-access-help-1")

    def test_invoke_stream_access_request_includes_assist_request(self):
        proposal = {
            "target": "api_key",
            "mode": "operator_provide_api_key",
            "summary": "先补一个可用 API key。",
            "operator_action": "填入一个可用 key。",
            "grants": ["api_key"],
            "requires_operator": True,
        }
        packet = {
            "proposal_id": "ap-access-help-assist",
            "origin": "counterpart_request",
            "intent": "access:request_help",
            "status": "awaiting_approval",
            "risk": "external_mutation",
            "requires_approval": True,
            "expected_effect": "先把缺的 API key 补齐。",
            "access_acquire_proposals": [proposal],
            "selected_access_proposal": proposal,
        }
        values = {
            "current_event": {"kind": "user_utterance"},
            "action_packets": [packet],
            "pending_action_proposal": dict(packet),
            "digital_body_state": {
                "access_state": {
                    "mode": "approval_pending",
                    "missing_access": ["api_key"],
                    "requestable_access": ["api_key", "human_approval"],
                    "selected_access_proposal": proposal,
                    "access_acquire_proposals": [proposal],
                },
                "resource_state": {},
            },
            "session_context": {"digital_body_hints": {"requested_help": True}},
        }
        graph = FakeStreamGraph(stream_rows=[("values", values)], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        result = session.invoke_stream({"messages": [{"role": "user", "content": "继续"}]})

        self.assertIsNotNone(result.approval_request)
        assert result.approval_request is not None
        assist = result.approval_request.payload.get("assist_request") if isinstance(result.approval_request.payload, dict) else {}
        self.assertEqual(assist.get("kind"), "grant_access")
        self.assertEqual(assist.get("resume_mode"), "auto_continue")
        self.assertEqual(assist.get("selected_access_proposal", {}).get("mode"), "operator_provide_api_key")
        self.assertIn("API key", assist.get("message", ""))

    def test_invoke_stream_defaults_selected_access_proposal_from_candidates(self):
        packet = {
            "proposal_id": "ap-access-help-1b",
            "origin": "counterpart_request",
            "intent": "access:request_help",
            "status": "awaiting_approval",
            "risk": "external_mutation",
            "requires_approval": True,
            "capability_steps": [
                {
                    "kind": "access",
                    "name": "request_help",
                    "target": "account_login",
                    "status": "awaiting_approval",
                    "requires_approval": True,
                    "note": "先决定走现有账号还是新注册账号。",
                }
            ],
            "expected_effect": "先决定走现有账号还是新注册账号。",
            "access_acquire_proposals": [
                {
                    "target": "account_login",
                    "mode": "operator_login",
                    "path_kind": "acquire_existing",
                    "summary": "先把现有账号登录补回来。",
                    "operator_action": "登录目标账号。",
                    "grants": ["account_login", "browser_session"],
                    "requires_operator": True,
                },
                {
                    "target": "account_login",
                    "mode": "operator_register_account",
                    "path_kind": "create_new",
                    "summary": "如果没有现成账号，也可以先注册一个新的可用入口。",
                    "operator_action": "注册一个新的账号入口。",
                    "grants": ["account_login", "browser_session"],
                    "requires_operator": True,
                },
            ],
        }
        values = {
            "current_event": {"kind": "user_utterance"},
            "action_packets": [packet],
            "pending_action_proposal": dict(packet),
            "session_context": {
                "digital_body_hints": {
                    "browser_session": "missing",
                    "account_state": "logged_out",
                    "missing_access": ["account_login", "browser_session"],
                    "requestable_access": ["account_login", "browser_session", "human_approval"],
                    "requested_help": True,
                    "access_acquire_proposals": list(packet["access_acquire_proposals"]),
                }
            },
        }
        graph = FakeStreamGraph(stream_rows=[("values", values)], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        result = session.invoke_stream({"messages": [{"role": "user", "content": "hi"}]})

        assert result.approval_request is not None
        selected = result.approval_request.tool_calls[0]["args"].get("selected_access_proposal") or {}
        self.assertEqual(selected.get("mode"), "operator_login")
        self.assertEqual(selected.get("path_kind"), "acquire_existing")

    def test_resume_stream_resolves_pending_access_request_without_graph_interrupt(self):
        packet = {
            "proposal_id": "ap-access-help-2",
            "origin": "counterpart_request",
            "intent": "access:request_help",
            "status": "awaiting_approval",
            "risk": "external_mutation",
            "requires_approval": True,
            "capability_steps": [
                {
                    "kind": "access",
                    "name": "request_help",
                    "target": "account_login / cookies",
                    "status": "awaiting_approval",
                    "requires_approval": True,
                    "note": "这一步需要先向你请求账号入口和 cookies。",
                }
            ],
            "expected_effect": "这一步需要先向你请求账号入口和 cookies。",
            "result_summary": "",
            "writeback_ready": False,
        }
        values = {
            "current_event": {"kind": "user_utterance"},
            "action_packets": [packet],
            "pending_action_proposal": dict(packet),
            "action_trace": [],
            "autonomy_intent": {
                "mode": "approval_pending",
                "origin": "counterpart_request",
                "reason": "这一步需要先向你请求账号入口和 cookies。",
                "primary_proposal_id": "ap-access-help-2",
            },
            "session_context": {
                "digital_body_hints": {
                    "browser_session": "missing",
                    "account_state": "logged_out",
                    "cookie_state": "expired",
                    "missing_access": ["account_login", "cookies"],
                    "requestable_access": ["account_login", "cookies", "human_approval"],
                    "requested_help": True,
                }
            },
            "interaction_carryover": {},
            "toolset_unlocks": {},
            "behavior_queue": [],
            "turn_appraisal": {},
            "world_model_state": {},
            "semantic_narrative_profile": {},
            "evolution_state": {},
            "emotion_state": {},
            "bond_state": {},
            "counterpart_assessment": {},
            "behavior_action": {},
            "behavior_plan": {},
            "agenda_lifecycle_residue": {},
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        result = session.resume_stream(
            [
                {
                    "action": "edit",
                    "reason": "operator restored session",
                    "args": {
                        "access_updates": {
                            "browser_session": "present",
                            "account_state": "logged_in",
                            "cookie_state": "present",
                            "missing_access": [],
                            "requestable_access": [],
                        }
                    },
                }
            ]
        )

        self.assertEqual(result.streamed_text, "")
        self.assertIsNone(result.approval_request)
        self.assertEqual(result.values["action_packets"][0]["status"], "completed")
        self.assertEqual(result.values["action_packets"][0]["result_summary"], "operator restored session")
        self.assertTrue(result.values["action_packets"][0]["writeback_ready"])
        self.assertEqual(result.values["autonomy_intent"]["mode"], "access_request_resolved")
        self.assertEqual(result.values["autonomy_intent"]["reason"], "operator restored session")
        self.assertEqual(result.values["pending_action_proposal"], {})
        self.assertFalse(result.values["session_context"]["digital_body_hints"]["requested_help"])
        self.assertEqual(result.values["session_context"]["digital_body_hints"]["browser_session"], "present")
        self.assertNotIn("selected_access_proposal", result.values["session_context"]["digital_body_hints"])
        self.assertEqual(result.values["action_trace"][-1]["event"], "resolved_by_user")
        self.assertEqual(len(graph.updated_states), 1)
        self.assertEqual(graph.updated_states[0][2], "prepare_turn")

    def test_resume_stream_can_approve_access_acquire_path_without_claiming_access_fixed(self):
        packet = {
            "proposal_id": "ap-access-help-3",
            "origin": "counterpart_request",
            "intent": "access:request_help",
            "status": "awaiting_approval",
            "risk": "external_mutation",
            "requires_approval": True,
            "capability_steps": [
                {
                    "kind": "access",
                    "name": "request_help",
                    "target": "api_key",
                    "status": "awaiting_approval",
                    "requires_approval": True,
                    "note": "这一步需要先补一个可用 API key。",
                }
            ],
            "expected_effect": "这一步需要先补一个可用 API key。",
            "result_summary": "",
            "writeback_ready": False,
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
        }
        values = {
            "current_event": {"kind": "user_utterance"},
            "action_packets": [packet],
            "pending_action_proposal": dict(packet),
            "action_trace": [],
            "autonomy_intent": {
                "mode": "approval_pending",
                "origin": "counterpart_request",
                "reason": "这一步需要先补一个可用 API key。",
                "primary_proposal_id": "ap-access-help-3",
            },
            "session_context": {
                "digital_body_hints": {
                    "api_key_state": "missing",
                    "missing_access": ["api_key"],
                    "requestable_access": ["api_key", "human_approval"],
                    "requested_help": True,
                    "access_acquire_proposals": list(packet["access_acquire_proposals"]),
                }
            },
            "interaction_carryover": {},
            "toolset_unlocks": {},
            "behavior_queue": [],
            "turn_appraisal": {},
            "world_model_state": {},
            "semantic_narrative_profile": {},
            "evolution_state": {},
            "emotion_state": {},
            "bond_state": {},
            "counterpart_assessment": {},
            "behavior_action": {},
            "behavior_plan": {},
            "agenda_lifecycle_residue": {},
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        result = session.resume_stream(
            [
                {
                    "action": "approve",
                    "reason": "operator accepted api key path",
                    "args": {
                        "selected_access_proposal": {
                            "target": "api_key",
                            "mode": "operator_provide_api_key",
                            "summary": "先补一个可用 API key。",
                            "operator_action": "填入一个可用 key。",
                            "grants": ["api_key"],
                            "requires_operator": True,
                        }
                    },
                }
            ]
        )

        self.assertEqual(result.streamed_text, "")
        self.assertIsNone(result.approval_request)
        self.assertEqual(result.values["action_packets"][0]["status"], "approved")
        self.assertFalse(result.values["action_packets"][0]["writeback_ready"])
        self.assertEqual(result.values["action_packets"][0]["result_summary"], "operator accepted api key path")
        selected = result.values["action_packets"][0].get("selected_access_proposal") if isinstance(result.values["action_packets"][0].get("selected_access_proposal"), dict) else {}
        self.assertEqual(selected.get("target"), "api_key")
        self.assertEqual(result.values["autonomy_intent"]["mode"], "access_acquire_planned")
        self.assertEqual(result.values["autonomy_intent"]["reason"], "先补一个可用 API key。")
        self.assertEqual(result.values["pending_action_proposal"], {})
        hints = result.values["session_context"]["digital_body_hints"]
        self.assertFalse(hints["requested_help"])
        self.assertEqual(hints["selected_access_proposal"]["mode"], "operator_provide_api_key")
        self.assertEqual(result.values["action_trace"][-1]["event"], "approved_by_user")

    def test_resume_stream_persists_operator_selected_access_path(self):
        proposals = [
            {
                "target": "account_login",
                "mode": "operator_login",
                "path_kind": "acquire_existing",
                "summary": "先把现有账号登录补回来。",
                "operator_action": "登录目标账号。",
                "grants": ["account_login", "browser_session"],
                "requires_operator": True,
            },
            {
                "target": "account_login",
                "mode": "operator_register_account",
                "path_kind": "create_new",
                "summary": "如果没有现成账号，也可以先注册一个新的可用入口。",
                "operator_action": "注册一个新的账号入口。",
                "grants": ["account_login", "browser_session"],
                "requires_operator": True,
            },
        ]
        packet = {
            "proposal_id": "ap-access-help-3b",
            "origin": "counterpart_request",
            "intent": "access:request_help",
            "status": "awaiting_approval",
            "risk": "external_mutation",
            "requires_approval": True,
            "capability_steps": [
                {
                    "kind": "access",
                    "name": "request_help",
                    "target": "account_login",
                    "status": "awaiting_approval",
                    "requires_approval": True,
                    "note": "先决定走现有账号还是新注册账号。",
                }
            ],
            "expected_effect": "先决定走现有账号还是新注册账号。",
            "result_summary": "",
            "writeback_ready": False,
            "access_acquire_proposals": proposals,
            "selected_access_proposal": proposals[0],
        }
        values = {
            "current_event": {"kind": "user_utterance"},
            "action_packets": [packet],
            "pending_action_proposal": dict(packet),
            "action_trace": [],
            "autonomy_intent": {
                "mode": "approval_pending",
                "origin": "counterpart_request",
                "reason": "先决定走现有账号还是新注册账号。",
                "primary_proposal_id": "ap-access-help-3b",
            },
            "session_context": {
                "digital_body_hints": {
                    "browser_session": "missing",
                    "account_state": "logged_out",
                    "missing_access": ["account_login", "browser_session"],
                    "requestable_access": ["account_login", "browser_session", "human_approval"],
                    "requested_help": True,
                    "access_acquire_proposals": proposals,
                    "selected_access_proposal": proposals[0],
                }
            },
            "interaction_carryover": {},
            "toolset_unlocks": {},
            "behavior_queue": [],
            "turn_appraisal": {},
            "world_model_state": {},
            "semantic_narrative_profile": {},
            "evolution_state": {},
            "emotion_state": {},
            "bond_state": {},
            "counterpart_assessment": {},
            "behavior_action": {},
            "behavior_plan": {},
            "agenda_lifecycle_residue": {},
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        result = session.resume_stream(
            [
                {
                    "action": "approve",
                    "reason": "operator selected fresh-account path",
                    "args": {
                        "selected_access_proposal": proposals[1],
                    },
                }
            ]
        )

        selected = result.values["action_packets"][0].get("selected_access_proposal") if isinstance(result.values["action_packets"][0].get("selected_access_proposal"), dict) else {}
        self.assertEqual(result.values["action_packets"][0]["status"], "approved")
        self.assertEqual(selected.get("mode"), "operator_register_account")
        self.assertEqual(selected.get("path_kind"), "create_new")
        self.assertEqual(result.values["session_context"]["digital_body_hints"]["selected_access_proposal"]["mode"], "operator_register_account")
        self.assertEqual(result.values["autonomy_intent"]["reason"], "如果没有现成账号，也可以先注册一个新的可用入口。")

    def test_resume_stream_approved_workspace_creation_path_persists_execution_binding(self):
        proposal = {
            "target": "filesystem",
            "mode": "operator_create_workspace",
            "path_kind": "create_new",
            "summary": "先新建一个可写工作区。",
            "operator_action": "新建一个可写工作区。",
            "grants": ["filesystem", "workspace_write"],
            "requires_operator": True,
        }
        packet = {
            "proposal_id": "ap-access-help-workspace",
            "origin": "counterpart_request",
            "intent": "access:request_help",
            "status": "awaiting_approval",
            "risk": "external_mutation",
            "requires_approval": True,
            "capability_steps": [
                {
                    "kind": "access",
                    "name": "request_help",
                    "target": "filesystem",
                    "status": "awaiting_approval",
                    "requires_approval": True,
                    "note": "先新建一个可写工作区。",
                }
            ],
            "expected_effect": "先新建一个可写工作区。",
            "result_summary": "",
            "writeback_ready": False,
            "access_acquire_proposals": [proposal],
            "selected_access_proposal": proposal,
        }
        values = {
            "current_event": {"kind": "user_utterance"},
            "action_packets": [packet],
            "pending_action_proposal": dict(packet),
            "action_trace": [],
            "autonomy_intent": {
                "mode": "approval_pending",
                "origin": "counterpart_request",
                "reason": "先新建一个可写工作区。",
                "primary_proposal_id": "ap-access-help-workspace",
            },
            "session_context": {
                "digital_body_hints": {
                    "filesystem_state": "missing",
                    "missing_access": ["filesystem", "workspace_write"],
                    "requestable_access": ["filesystem", "workspace_write", "human_approval"],
                    "requested_help": True,
                    "access_acquire_proposals": [proposal],
                    "selected_access_proposal": proposal,
                }
            },
            "interaction_carryover": {},
            "toolset_unlocks": {},
            "behavior_queue": [],
            "turn_appraisal": {},
            "world_model_state": {},
            "semantic_narrative_profile": {},
            "evolution_state": {},
            "emotion_state": {},
            "bond_state": {},
            "counterpart_assessment": {},
            "behavior_action": {},
            "behavior_plan": {},
            "agenda_lifecycle_residue": {},
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        result = session.resume_stream([{"action": "approve"}])

        packet_out = result.values["action_packets"][0]
        self.assertEqual(packet_out["status"], "approved")
        self.assertEqual(packet_out["tool_name"], "create_workspace_access")
        self.assertEqual(packet_out["tool_args"]["access_hints"]["selected_access_proposal"]["mode"], "operator_create_workspace")
        self.assertEqual(packet_out["tool_args"]["workspace_name"], "")
        self.assertEqual(result.values["autonomy_intent"]["mode"], "access_acquire_planned")

    def test_resume_stream_approved_repo_root_attach_path_persists_execution_binding(self):
        proposal = {
            "target": "filesystem",
            "mode": "operator_attach_repo_root",
            "path_kind": "acquire_existing",
            "summary": "先把当前仓库根目录挂成 workspace。",
            "operator_action": "批准把当前 git worktree 根目录挂接成 workspace。",
            "grants": ["filesystem", "workspace_write"],
            "requires_operator": True,
        }
        repo_root = "E:/repo/amadeus-thread0"
        packet = {
            "proposal_id": "ap-access-help-attach-root",
            "origin": "counterpart_request",
            "intent": "access:request_help",
            "status": "awaiting_approval",
            "risk": "external_mutation",
            "requires_approval": True,
            "capability_steps": [
                {
                    "kind": "access",
                    "name": "request_help",
                    "target": "filesystem",
                    "status": "awaiting_approval",
                    "requires_approval": True,
                    "note": "先把当前仓库根目录挂成 workspace。",
                }
            ],
            "expected_effect": "先把当前仓库根目录挂成 workspace。",
            "result_summary": "",
            "writeback_ready": False,
            "access_acquire_proposals": [proposal],
            "selected_access_proposal": proposal,
        }
        values = {
            "current_event": {"kind": "user_utterance"},
            "action_packets": [packet],
            "pending_action_proposal": dict(packet),
            "action_trace": [],
            "autonomy_intent": {
                "mode": "approval_pending",
                "origin": "counterpart_request",
                "reason": "先把当前仓库根目录挂成 workspace。",
                "primary_proposal_id": "ap-access-help-attach-root",
            },
            "session_context": {
                "digital_body_hints": {
                    "filesystem_state": "missing",
                    "workspace_root": repo_root,
                    "workspace_root_kind": "attached_repo_root",
                    "missing_access": ["filesystem", "workspace_write"],
                    "requestable_access": ["filesystem", "workspace_write", "human_approval"],
                    "requested_help": True,
                    "access_acquire_proposals": [proposal],
                    "selected_access_proposal": proposal,
                }
            },
            "interaction_carryover": {},
            "toolset_unlocks": {},
            "behavior_queue": [],
            "turn_appraisal": {},
            "world_model_state": {},
            "semantic_narrative_profile": {},
            "evolution_state": {},
            "emotion_state": {},
            "bond_state": {},
            "counterpart_assessment": {},
            "behavior_action": {},
            "behavior_plan": {},
            "agenda_lifecycle_residue": {},
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        result = session.resume_stream([{"action": "approve"}])

        packet_out = result.values["action_packets"][0]
        self.assertEqual(packet_out["status"], "approved")
        self.assertEqual(packet_out["tool_name"], "attach_repo_root_access")
        self.assertEqual(packet_out["tool_args"]["repo_root"], repo_root)
        self.assertEqual(packet_out["tool_args"]["access_hints"]["workspace_root_kind"], "attached_repo_root")
        self.assertEqual(
            packet_out["tool_args"]["access_hints"]["selected_access_proposal"]["mode"],
            "operator_attach_repo_root",
        )
        self.assertEqual(result.values["autonomy_intent"]["mode"], "access_acquire_planned")

    def test_resume_stream_keeps_partial_access_arrival_as_approved(self):
        proposal = {
            "target": "account_login",
            "mode": "operator_login",
            "summary": "先把账号登录补回来，这条外部入口才接得上后面。",
            "operator_action": "登录目标账号，或把现成登录态交给我。",
            "grants": ["account_login", "browser_session"],
            "requires_operator": True,
        }
        packet = {
            "proposal_id": "ap-access-help-4",
            "origin": "counterpart_request",
            "intent": "access:request_help",
            "status": "awaiting_approval",
            "risk": "external_mutation",
            "requires_approval": True,
            "capability_steps": [
                {
                    "kind": "access",
                    "name": "request_help",
                    "target": "account_login",
                    "status": "awaiting_approval",
                    "requires_approval": True,
                    "note": "需要先补回登录和会话。",
                }
            ],
            "expected_effect": "需要先补回登录和会话。",
            "result_summary": "",
            "writeback_ready": False,
            "access_acquire_proposals": [proposal],
        }
        values = {
            "current_event": {"kind": "user_utterance"},
            "action_packets": [packet],
            "pending_action_proposal": dict(packet),
            "action_trace": [],
            "autonomy_intent": {
                "mode": "approval_pending",
                "origin": "counterpart_request",
                "reason": "需要先补回登录和会话。",
                "primary_proposal_id": "ap-access-help-4",
            },
            "session_context": {
                "digital_body_hints": {
                    "browser_session": "missing",
                    "account_state": "logged_out",
                    "missing_access": ["account_login", "browser_session"],
                    "requestable_access": ["account_login", "browser_session", "human_approval"],
                    "requested_help": True,
                    "access_acquire_proposals": [proposal],
                }
            },
            "interaction_carryover": {},
            "toolset_unlocks": {},
            "behavior_queue": [],
            "turn_appraisal": {},
            "world_model_state": {},
            "semantic_narrative_profile": {},
            "evolution_state": {},
            "emotion_state": {},
            "bond_state": {},
            "counterpart_assessment": {},
            "behavior_action": {},
            "behavior_plan": {},
            "agenda_lifecycle_residue": {},
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        result = session.resume_stream(
            [
                {
                    "action": "edit",
                    "args": {
                        "access_updates": {
                            "account_state": "logged_in",
                            "browser_session": "missing",
                            "missing_access": ["browser_session"],
                            "requestable_access": ["browser_session"],
                            "selected_access_proposal": proposal,
                        }
                    },
                }
            ]
        )

        self.assertEqual(result.values["action_packets"][0]["status"], "approved")
        self.assertFalse(result.values["action_packets"][0]["writeback_ready"])
        self.assertEqual(result.values["autonomy_intent"]["mode"], "access_acquire_planned")
        self.assertEqual(result.values["action_trace"][-1]["event"], "approved_by_user")
        self.assertIn("还没完全接通", result.values["action_packets"][0]["result_summary"])
        selected = result.values["action_packets"][0].get("selected_access_proposal") if isinstance(result.values["action_packets"][0].get("selected_access_proposal"), dict) else {}
        self.assertEqual(selected.get("resolved_grants"), ["account_login"])
        self.assertEqual(selected.get("pending_grants"), ["browser_session"])
        self.assertEqual(selected.get("completion_ratio"), 0.5)
        hints = result.values["session_context"]["digital_body_hints"]
        self.assertFalse(hints["requested_help"])
        self.assertEqual(hints["missing_access"], ["browser_session"])
        self.assertIn("selected_access_proposal", hints)

    def test_resume_stream_completed_access_auto_continues_current_task(self):
        proposal = {
            "target": "filesystem",
            "mode": "operator_create_workspace",
            "summary": "先新建一个可写工作区。",
            "operator_action": "新建一个可写工作区。",
            "grants": ["filesystem", "workspace_write"],
            "requires_operator": True,
        }

        class AutoContinueGraph(FakeStreamGraph):
            def __init__(self):
                super().__init__(
                    stream_rows=[],
                    state_values={
                        "current_event": {
                            "kind": "user_utterance",
                            "text": "继续把 lab notes 写下去",
                            "effective_text": "继续把 lab notes 写下去",
                            "semantic_goal": "继续把 lab notes 写下去",
                        },
                        "action_packets": [
                            {
                                "proposal_id": "ap-access-auto-1",
                                "origin": "counterpart_request",
                                "intent": "access:request_help",
                                "status": "awaiting_approval",
                                "risk": "external_mutation",
                                "requires_approval": True,
                                "expected_effect": "先新建一个可写工作区。",
                                "access_acquire_proposals": [proposal],
                                "selected_access_proposal": proposal,
                            }
                        ],
                        "pending_action_proposal": {
                            "proposal_id": "ap-access-auto-1",
                            "origin": "counterpart_request",
                            "intent": "access:request_help",
                            "status": "awaiting_approval",
                            "risk": "external_mutation",
                            "requires_approval": True,
                            "expected_effect": "先新建一个可写工作区。",
                            "access_acquire_proposals": [proposal],
                            "selected_access_proposal": proposal,
                        },
                        "digital_body_state": {
                            "access_state": {
                                "mode": "approval_pending",
                                "missing_access": ["filesystem", "workspace_write"],
                                "requestable_access": ["filesystem", "workspace_write", "human_approval"],
                                "selected_access_proposal": proposal,
                                "access_acquire_proposals": [proposal],
                            },
                            "resource_state": {},
                        },
                        "session_context": {"digital_body_hints": {"requested_help": True}},
                    },
                )
                self.stream_payloads = []

            def stream(self, payload, config=None, stream_mode=None):
                self.stream_payloads.append(payload)
                yield (
                    "values",
                    {
                        "final_text": "我已经继续把那个工作区里的文件接着写下去了。",
                        "current_event": {
                            "kind": "access_resume",
                            "digital_body_hints": {
                                "just_resolved_access": {
                                    "proposal_id": "ap-access-auto-1",
                                    "selected_access_proposal": proposal,
                                }
                            },
                        },
                    },
                )

        graph = AutoContinueGraph()
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        result = session.resume_stream(
            [
                {
                    "action": "edit",
                    "args": {
                        "access_updates": {
                            "filesystem_state": "writable",
                            "missing_access": [],
                            "requestable_access": [],
                            "selected_access_proposal": proposal,
                        }
                    },
                }
            ]
        )

        self.assertTrue(graph.stream_payloads)
        event_override = graph.stream_payloads[-1].get("event_override") if isinstance(graph.stream_payloads[-1], dict) else {}
        self.assertEqual(event_override.get("kind"), "access_resume")
        self.assertEqual(event_override.get("semantic_goal"), "继续把 lab notes 写下去")
        final_text = session.extract_final_text(result.values, streamed_text=result.streamed_text)
        self.assertIn("已经接上了", final_text)
        self.assertIn("我已经继续把那个工作区里的文件接着写下去了。", final_text)

    def test_invoke_stream_short_takeover_confirmation_auto_continues(self):
        proposal = {
            "target": "account_login",
            "mode": "operator_login",
            "summary": "先把现有账号登录补回来。",
            "operator_action": "登录目标账号。",
            "grants": ["account_login", "browser_session"],
            "requires_operator": True,
        }

        class TakeoverContinueGraph(FakeStreamGraph):
            def __init__(self):
                super().__init__(
                    stream_rows=[],
                    state_values={
                        "current_event": {
                            "kind": "user_utterance",
                            "text": "去把订单页打开",
                            "effective_text": "去把订单页打开",
                            "semantic_goal": "去把订单页打开",
                        },
                        "action_packets": [
                            {
                                "proposal_id": "ap-browser-takeover-1",
                                "intent": "browser:fill",
                                "status": "blocked",
                                "risk": "external_mutation",
                                "requires_approval": True,
                                "tool_name": "browser_fill",
                                "browser_execution_preview": {
                                    "operation": "fill",
                                    "profile_id": "thread-browser",
                                    "page_ref": "page:page-1",
                                    "page_title": "Login",
                                    "target_ref": "password",
                                    "target_label": "密码输入框",
                                    "requires_manual_takeover": True,
                                },
                                "browser_execution_result": {
                                    "status": "blocked",
                                    "profile_id": "thread-browser",
                                    "page_id": "page-1",
                                    "tab_id": "tab-1",
                                    "title": "Login",
                                    "target_ref": "password",
                                    "manual_takeover_required": True,
                                },
                                "selected_access_proposal": proposal,
                            }
                        ],
                        "digital_body_state": {
                            "access_state": {
                                "browser_runtime_state": {
                                    "availability": "available",
                                    "context_status": "manual_takeover",
                                    "manual_takeover_required": True,
                                    "last_run_id": "ap-browser-takeover-1",
                                },
                                "selected_access_proposal": proposal,
                            },
                            "resource_state": {"active_artifact_label": "Login"},
                        },
                        "session_context": {
                            "digital_body_hints": {
                                "browser_runtime_state": {
                                    "availability": "available",
                                    "context_status": "manual_takeover",
                                    "manual_takeover_required": True,
                                    "last_run_id": "ap-browser-takeover-1",
                                }
                            }
                        },
                    },
                )
                self.stream_payloads = []

            def stream(self, payload, config=None, stream_mode=None):
                self.stream_payloads.append(payload)
                yield (
                    "values",
                    {
                        "final_text": "我已经接着把订单页往下看了。",
                        "current_event": {
                            "kind": "access_resume",
                            "digital_body_hints": {
                                "just_completed_takeover": {
                                    "proposal_id": "ap-browser-takeover-1",
                                    "profile_id": "thread-browser",
                                    "page_ref": "page:page-1",
                                    "tab_id": "tab-1",
                                }
                            },
                        },
                    },
                )

        graph = TakeoverContinueGraph()
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        result = session.invoke_stream({"messages": [{"role": "user", "content": "好了"}]})

        self.assertTrue(graph.stream_payloads)
        event_override = graph.stream_payloads[-1].get("event_override") if isinstance(graph.stream_payloads[-1], dict) else {}
        self.assertEqual(event_override.get("kind"), "access_resume")
        self.assertEqual(event_override.get("semantic_goal"), "去把订单页打开")
        final_text = session.extract_final_text(result.values, streamed_text=result.streamed_text)
        self.assertIn("浏览器这边已经接回来了", final_text)
        self.assertIn("我已经接着把订单页往下看了。", final_text)

    def test_extract_final_text_prefers_explicit_final_text_field(self):
        session = BackendSession(graph=object(), memory_store=FakeMemoryStore(), thread_id="thread-a")
        text = session.extract_final_text(
            {
                "final_text": "finalized-answer",
                "messages": [SimpleNamespace(content="stale-answer")],
            }
        )
        self.assertEqual(text, "finalized-answer")

    def test_extract_final_text_prefers_assist_request_message_when_access_is_pending(self):
        session = BackendSession(graph=object(), memory_store=FakeMemoryStore(), thread_id="thread-a")
        proposal = {
            "target": "filesystem",
            "mode": "operator_create_workspace",
            "summary": "先新建一个可写工作区。",
            "operator_action": "新建一个可写工作区。",
            "grants": ["filesystem", "workspace_write"],
            "requires_operator": True,
        }
        text = session.extract_final_text(
            {
                "final_text": "stale-final",
                "pending_action_proposal": {
                    "proposal_id": "ap-access-pending-text",
                    "intent": "access:request_help",
                    "status": "awaiting_approval",
                    "risk": "external_mutation",
                    "requires_approval": True,
                    "access_acquire_proposals": [proposal],
                    "selected_access_proposal": proposal,
                },
                "digital_body_state": {
                    "access_state": {
                        "mode": "approval_pending",
                        "missing_access": ["filesystem", "workspace_write"],
                        "requestable_access": ["filesystem", "workspace_write", "human_approval"],
                        "selected_access_proposal": proposal,
                        "access_acquire_proposals": [proposal],
                    },
                    "resource_state": {},
                },
            }
        )
        self.assertIn("工作区写入入口", text)
        self.assertIn("不用你再提醒", text)

    def test_extract_final_text_prefixes_resume_ack_after_access_resume(self):
        session = BackendSession(graph=object(), memory_store=FakeMemoryStore(), thread_id="thread-a")
        text = session.extract_final_text(
            {
                "final_text": "我已经继续把后面的检查做下去了。",
                "current_event": {
                    "kind": "access_resume",
                    "digital_body_hints": {
                        "just_resolved_access": {
                            "proposal_id": "ap-access-ack-1",
                            "selected_access_proposal": {
                                "mode": "operator_create_workspace",
                                "target": "filesystem",
                                "operator_action": "先把可写工作区开出来",
                            },
                        }
                    },
                },
            }
        )
        self.assertTrue(text.startswith("好，"))
        self.assertIn("我继续", text)
        self.assertIn("我已经继续把后面的检查做下去了。", text)

    def test_extract_final_text_prefers_manual_takeover_request_when_browser_is_blocked(self):
        session = BackendSession(graph=object(), memory_store=FakeMemoryStore(), thread_id="thread-a")
        text = session.extract_final_text(
            {
                "final_text": "stale",
                "action_packets": [
                    {
                        "proposal_id": "ap-browser-fill-1",
                        "intent": "browser:fill",
                        "status": "blocked",
                        "risk": "external_mutation",
                        "requires_approval": True,
                        "tool_name": "browser_fill",
                        "browser_execution_preview": {
                            "operation": "fill",
                            "profile_id": "thread-browser",
                            "page_ref": "page:page-1",
                            "page_title": "Login",
                            "target_ref": "password",
                            "target_label": "密码输入框",
                            "requires_manual_takeover": True,
                        },
                        "browser_execution_result": {
                            "status": "blocked",
                            "profile_id": "thread-browser",
                            "page_id": "page-1",
                            "tab_id": "tab-1",
                            "title": "Login",
                            "target_ref": "password",
                            "manual_takeover_required": True,
                            "error_summary": "sensitive credential entry requires manual browser takeover",
                        },
                    }
                ],
                "digital_body_state": {
                    "access_state": {
                        "browser_runtime_state": {
                            "availability": "available",
                            "context_status": "manual_takeover",
                            "manual_takeover_required": True,
                            "last_run_id": "ap-browser-fill-1",
                        }
                    },
                    "resource_state": {"active_artifact_label": "Login"},
                },
            }
        )
        self.assertIn("密码、OTP、passkey、验证码", text)
        self.assertIn("你接管一下", text)

    def test_invoke_event_round_auto_resumes_memory_interrupt(self):
        before_values = {"messages": [SimpleNamespace(content="before")]}
        after_values = {"messages": [SimpleNamespace(content="before"), SimpleNamespace(content="after")]}
        graph = FakeInvokeGraph(
            before_values=before_values,
            after_values=after_values,
            invoke_rows=[
                {"__interrupt__": [{"value": {"kind": "tool_approval", "source": "memory", "tool_calls": [{"name": "set_profile"}]}}]},
                {},
            ],
        )
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")
        result = session.invoke_event_round(
            run_config=session.config(),
            event_payload={"event_override": {"kind": "idle"}} ,
            auto_resume_memory_approval=lambda payload: str(payload.get("source") or "") == "memory",
        )
        self.assertEqual(result.final_text, "after")
        self.assertEqual(len(graph.invoke_calls), 2)
        decisions = getattr(graph.invoke_calls[1][0], "resume", {})
        self.assertEqual(decisions.get("decisions"), [{"action": "approve"}])

    def test_invoke_event_round_prefers_state_final_text_over_last_message(self):
        before_values = {"messages": [SimpleNamespace(content="before")]}
        after_values = {
            "final_text": "after-final",
            "messages": [SimpleNamespace(content="before"), SimpleNamespace(content="stale-after")],
        }
        graph = FakeInvokeGraph(
            before_values=before_values,
            after_values=after_values,
            invoke_rows=[{}],
        )
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")
        result = session.invoke_event_round(
            run_config=session.config(),
            event_payload={"event_override": {"kind": "idle"}},
        )
        self.assertEqual(result.final_text, "after-final")

    def test_invoke_event_round_resume_preserves_checkpoint_and_user_config(self):
        before_values = {"messages": [SimpleNamespace(content="before")]}
        after_values = {"messages": [SimpleNamespace(content="before"), SimpleNamespace(content="after")]}
        graph = FakeInvokeGraph(
            before_values=before_values,
            after_values=after_values,
            invoke_rows=[
                {"__interrupt__": [{"value": {"kind": "tool_approval", "source": "memory", "tool_calls": [{"name": "set_profile"}]}}]},
                {},
            ],
        )
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a", user_id="okabe")
        run_config = session.config(checkpoint_id="cp-7")

        session.invoke_event_round(
            run_config=run_config,
            event_payload={"event_override": {"kind": "idle"}},
            auto_resume_memory_approval=lambda payload: str(payload.get("source") or "") == "memory",
        )

        self.assertEqual(graph.invoke_calls[1][1], run_config)

    def test_session_views_expose_worldline_persona_and_sources(self):
        values = {
            "persona_state": {"role": "kurisu_amadeus"},
            "emotion_state": {"label": "care"},
            "bond_state": {"trust": 0.7},
            "allostasis_state": {"autonomy_need": 0.4},
            "counterpart_assessment": {"stance": "open"},
            "semantic_narrative_profile": {
                "presence_carry": 0.5,
                "top_narratives": [
                    {
                        "category": "rhythm_style",
                        "score": 0.74,
                        "reactivated": True,
                        "text": "她会把自己的内部节奏延续到下一轮。",
                        "primary_motive": "preserve_self_rhythm",
                        "motive_tension": "self_rhythm_vs_contact",
                        "counterpart_snapshot": {
                            "counterpart_stance": "watchful",
                            "counterpart_scene": "busy_not_disrespectful",
                            "counterpart_respect_level": 0.61,
                            "counterpart_profile": {"dominant_scene_signal": "busy"},
                        },
                        "proactive_continuity": {
                            "_score": 0.67,
                            "own_rhythm_anchor": 0.71,
                        },
                    }
                ],
                "long_term_self_narratives": [
                    {
                        "category": "selfhood_style",
                        "score": 0.79,
                        "horizon_tag": "long_term",
                        "text": "她会把自己放在平等互动的位置上。",
                        "prompt_text": "你会把自己放在平等互动的位置上。",
                        "primary_motive": "preserve_selfhood",
                        "motive_tension": "selfhood_vs_appeasement",
                        "sedimentation_score": 0.73,
                        "identity_strength": 0.82,
                    }
                ],
            },
            "world_model_state": {"presence_residue": 0.4},
            "evolution_state": {"stable": True},
            "reconsolidation_snapshot": {"event_kind": "user_utterance"},
            "turn_appraisal": {"selfhood_scene": "dialogue_equality"},
            "behavior_policy": {"self_directedness": 0.8},
            "behavior_action": {"interaction_mode": "selfhood_reflection"},
            "interaction_carryover": {"carryover_mode": "warm_residue"},
            "agenda_lifecycle_residue": {"kind": "held"},
            "behavior_plan": {"kind": "deferred_checkin"},
            "behavior_queue": [{"agenda_id": "a1", "kind": "deferred_checkin", "status": "pending"}],
            "worldline_focus": [
                {
                    "id": 21,
                    "focus_kind": "commitment",
                    "text": "记得提醒冈部吃饭。",
                    "status": "open",
                    "due_at": "今晚",
                }
            ],
            "science_mode": False,
            "tsundere_intensity": 0.6,
            "ooc_detector": {"risk": 0.1},
            "canon_guard": {"ok": True},
            "claim_links": [{"claim_excerpt": "claim", "source_ids": [9]}],
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        worldline = session.worldline_view()
        self.assertEqual(worldline["worldline_events"][0]["summary"], "一起熬夜。")
        self.assertEqual(worldline["worldline_summary"]["relationship"]["stage"], "warming")
        self.assertEqual(worldline["worldline_summary"]["worldline_focus_preview"][0], "记得提醒冈部吃饭。")
        self.assertEqual(worldline["worldline_summary"]["worldline_focus_items"][0]["kind"], "commitment")
        self.assertEqual(worldline["worldline_summary"]["worldline_focus_items"][0]["due_at"], "今晚")
        self.assertEqual(
            worldline["worldline_summary"]["semantic_continuity"]["top_narratives"][0]["primary_motive"],
            "preserve_self_rhythm",
        )
        self.assertEqual(
            worldline["worldline_summary"]["semantic_continuity"]["top_narratives"][0]["counterpart_snapshot"]["scene"],
            "busy_not_disrespectful",
        )
        self.assertEqual(
            worldline["worldline_summary"]["identity_continuity"]["long_term_self_narratives"][0]["identity_strength"],
            0.82,
        )
        self.assertEqual(worldline["counterpart_assessment_history"][0]["scene"], "care_bid")
        self.assertEqual(worldline["counterpart_assessment_preview"][0]["created_at"], 1710000003)
        self.assertEqual(worldline["counterpart_assessment_preview"][0]["embodied_context"]["kind"], "access_request_pending")
        self.assertEqual(worldline["counterpart_assessment_preview"][0]["embodied_context"]["artifact_carrier"], "source_ref")
        self.assertEqual(worldline["counterpart_assessment_preview"][0]["embodied_context"]["artifact_source_ref_ids"], [17])
        self.assertEqual(worldline["counterpart_assessment_preview"][0]["embodied_context"]["preferred_source_ref_id"], 17)
        self.assertEqual(
            worldline["counterpart_assessment_preview"][0]["embodied_context"]["preferred_anchor_reason"],
            "primary_more_current",
        )
        self.assertEqual(
            worldline["counterpart_assessment_preview"][0]["embodied_context"]["artifact_source_title"],
            "Persistence",
        )
        self.assertIn("bodyfx=access_request_pending", worldline["counterpart_assessment_preview"][0].get("preview_line") or "")
        self.assertIn("source=Persistence", worldline["counterpart_assessment_preview"][0].get("preview_line") or "")
        self.assertEqual(worldline["proactive_continuity_history"][0]["carryover_mode"], "own_rhythm")
        self.assertEqual(worldline["proactive_continuity_preview"][0]["trace_family"], "own_rhythm_busy_window")
        self.assertEqual(worldline["proactive_continuity_preview"][0]["semantic_continuity_depth"], 0.68)
        self.assertEqual(worldline["proactive_continuity_preview"][0]["semantic_identity_gravity"], 0.64)
        self.assertEqual(worldline["proactive_continuity_preview"][0]["created_at"], 1710000004)
        self.assertEqual(worldline["proactive_continuity_preview"][0]["embodied_context"]["kind"], "access_request_pending")
        self.assertEqual(worldline["proactive_continuity_preview"][0]["embodied_context"]["artifact_carrier"], "source_ref")
        self.assertEqual(worldline["proactive_continuity_preview"][0]["embodied_context"]["artifact_source_ref_ids"], [17])
        self.assertEqual(worldline["proactive_continuity_preview"][0]["embodied_context"]["preferred_source_ref_id"], 17)
        self.assertEqual(
            worldline["proactive_continuity_preview"][0]["embodied_context"]["preferred_anchor_reason"],
            "primary_more_current",
        )
        self.assertEqual(
            worldline["proactive_continuity_preview"][0]["embodied_context"]["artifact_source_title"],
            "Persistence",
        )
        self.assertIn("bodyfx=access_request_pending", worldline["proactive_continuity_preview"][0].get("preview_line") or "")
        self.assertIn("source=Persistence", worldline["proactive_continuity_preview"][0].get("preview_line") or "")

        persona = session.persona_view()
        self.assertEqual(persona["persona_state"]["role"], "kurisu_amadeus")
        self.assertEqual(persona["behavior_queue_summary"][0]["agenda_id"], "a1")

        bond = session.bond_view()
        self.assertEqual(bond["relationship_state"]["stage"], "warming")
        self.assertEqual(bond["bond_state"]["trust"], 0.7)
        self.assertEqual(bond["counterpart_assessment_history"][0]["scene"], "care_bid")
        self.assertEqual(bond["counterpart_assessment_preview"][0]["stance"], "open")
        self.assertEqual(bond["counterpart_assessment_preview"][0]["created_at"], 1710000003)
        self.assertEqual(bond["counterpart_assessment_preview"][0]["embodied_context"]["kind"], "access_request_pending")
        self.assertEqual(bond["counterpart_assessment_preview"][0]["embodied_context"]["artifact_carrier"], "source_ref")
        self.assertEqual(bond["counterpart_assessment_preview"][0]["embodied_context"]["artifact_source_ref_ids"], [17])
        self.assertEqual(bond["counterpart_assessment_preview"][0]["embodied_context"]["preferred_source_ref_id"], 17)
        self.assertEqual(
            bond["counterpart_assessment_preview"][0]["embodied_context"]["preferred_anchor_reason"],
            "primary_more_current",
        )
        self.assertIn("bodyfx=access_request_pending", bond["counterpart_assessment_preview"][0].get("preview_line") or "")
        self.assertIn("source=Persistence", bond["counterpart_assessment_preview"][0].get("preview_line") or "")
        self.assertEqual(bond["proactive_continuity_history"][0]["kind"], "released_to_self_activity")
        self.assertEqual(bond["proactive_continuity_preview"][0]["carryover_mode"], "own_rhythm")
        self.assertEqual(bond["proactive_continuity_preview"][0]["semantic_continuity_depth"], 0.68)
        self.assertEqual(bond["proactive_continuity_preview"][0]["semantic_identity_gravity"], 0.64)
        self.assertEqual(bond["proactive_continuity_preview"][0]["embodied_context"]["kind"], "access_request_pending")
        self.assertEqual(bond["proactive_continuity_preview"][0]["embodied_context"]["artifact_carrier"], "source_ref")
        self.assertEqual(bond["proactive_continuity_preview"][0]["embodied_context"]["artifact_source_ref_ids"], [17])
        self.assertEqual(bond["proactive_continuity_preview"][0]["embodied_context"]["preferred_source_ref_id"], 17)
        self.assertEqual(
            bond["proactive_continuity_preview"][0]["embodied_context"]["preferred_anchor_reason"],
            "primary_more_current",
        )
        self.assertIn("bodyfx=access_request_pending", bond["proactive_continuity_preview"][0].get("preview_line") or "")
        self.assertIn("source=Persistence", bond["proactive_continuity_preview"][0].get("preview_line") or "")

        sources = session.sources_view()
        self.assertEqual(sources["sources"][0]["tool_name"], "web_search")
        self.assertEqual(sources["claim_links"][0]["source_ids"], [9])

    def test_sources_view_normalizes_source_material_exports(self):
        store = FakeMemoryStore()
        store._sources = [
            {
                "id": "9",
                "content": {
                    "title": " paper ",
                    "url": " https://example.com/paper ",
                    "query": " amadeus source contract ",
                    "tool_name": " web_search ",
                    "snippet": " saved snippet ",
                    "embodied_context": {
                        "kind": "source_material_compared",
                        "artifact_carrier": "source_ref",
                        "artifact_source_ref_ids": ["9", "17", "9"],
                        "preferred_source_ref_id": "9",
                        "preferred_anchor_reason": "primary_more_current",
                        "artifact_source_title": " paper ",
                    },
                },
            }
        ]
        values = {
            "claim_links": [
                {
                    "content": {
                        "claim_excerpt": " 这一句需要引用 ",
                        "source_ids": ["9", "9", "0", -1],
                        "embodied_context": {
                            "kind": "source_material_compared",
                            "artifact_carrier": "source_ref",
                            "artifact_source_ref_ids": ["9", "17", "9"],
                            "preferred_source_ref_id": "9",
                            "preferred_anchor_reason": "primary_more_current",
                            "artifact_source_title": " paper ",
                        },
                        "sources": [
                            {
                                "source_id": "9",
                                "content": {
                                    "title": " paper ",
                                    "url": " https://example.com/paper ",
                                    "tool_name": " web_search ",
                                    "query": " amadeus source contract ",
                                    "snippet": " excerpt ",
                                    "embodied_context": {
                                        "kind": "source_material_compared",
                                        "artifact_carrier": "source_ref",
                                        "artifact_source_ref_ids": ["9", "17", "9"],
                                        "preferred_source_ref_id": "9",
                                        "preferred_anchor_reason": "primary_more_current",
                                        "artifact_source_title": " paper ",
                                    },
                                },
                            }
                        ],
                    },
                }
            ]
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=store, thread_id="thread-a")

        sources = session.sources_view()

        self.assertEqual(sources["sources"][0]["id"], 9)
        self.assertEqual(sources["sources"][0]["source_id"], 9)
        self.assertEqual(sources["sources"][0]["title"], "paper")
        self.assertEqual(sources["sources"][0]["tool_name"], "web_search")
        self.assertEqual(sources["sources"][0]["embodied_context"]["kind"], "source_material_compared")
        self.assertIn("bodyfx=source_material_compared", sources["sources"][0].get("preview_line") or "")
        self.assertIn("source=paper", sources["sources"][0].get("preview_line") or "")
        self.assertEqual(sources["claim_links"][0]["claim_excerpt"], "这一句需要引用")
        self.assertEqual(sources["claim_links"][0]["source_ids"], [9])
        self.assertEqual(sources["claim_links"][0]["embodied_context"]["preferred_source_ref_id"], 9)
        self.assertEqual(sources["claim_links"][0]["embodied_context"]["artifact_source_ref_ids"], [9, 17])
        self.assertEqual(sources["claim_links"][0]["embodied_context"]["preferred_anchor_reason"], "primary_more_current")
        self.assertIn("bodyfx=source_material_compared", sources["claim_links"][0].get("preview_line") or "")
        self.assertIn("source=paper", sources["claim_links"][0].get("preview_line") or "")
        self.assertEqual(sources["claim_links"][0]["sources"][0]["source_id"], 9)
        self.assertEqual(sources["claim_links"][0]["sources"][0]["title"], "paper")
        self.assertEqual(
            sources["claim_links"][0]["sources"][0]["embodied_context"]["preferred_source_ref_id"],
            9,
        )
        self.assertIn(
            "bodyfx=source_material_compared",
            sources["claim_links"][0]["sources"][0].get("preview_line") or "",
        )
        self.assertIn("source=paper", sources["claim_links"][0]["sources"][0].get("preview_line") or "")

    def test_session_preview_views_preserve_workspace_surface_embodied_context(self):
        store = FakeMemoryStore()
        work_surface_counterpart = {
            "id": 12,
            "summary": "她已经顺着那块文件工作面继续往前走了。",
            "stance": "open",
            "scene": "co_work",
            "created_at": 1710000103,
            "embodied_context": {
                "kind": "workspace_file_updated",
                "summary": "她已经在 today.md 上继续写了一段。",
                "artifact_continuity": "attached",
                "active_artifact_kind": "file",
                "active_artifact_ref": "notes/today.md",
                "active_artifact_label": "today.md",
                "workspace_root": "E:/runtime/workspaces/lab-notes",
                "artifact_mutation_mode": "append",
                "procedural_growth": True,
                "primary_status": "completed",
            },
        }
        work_surface_proactive = {
            "id": 13,
            "summary": "前面那块文件工作面已经重新接回当前上下文，后面的动作可以顺着它继续。",
            "kind": "promoted",
            "trace_family": "artifact_reacquired_followthrough",
            "carryover_mode": "continue_work_surface",
            "created_at": 1710000104,
            "embodied_context": {
                "kind": "artifact_reacquired",
                "summary": "她已经重新把 notes/today.md 接回当前上下文。",
                "artifact_continuity": "detached",
                "active_artifact_kind": "file",
                "active_artifact_ref": "notes/today.md",
                "active_artifact_label": "today.md",
                "workspace_root": "E:/runtime/workspaces/lab-notes",
                "artifact_reacquisition_mode": "reopen_file",
                "artifact_mutation_mode": "replace",
                "primary_status": "completed",
            },
        }
        store._snapshot["counterpart_assessment_history"] = [work_surface_counterpart]
        store._snapshot["proactive_continuity_history"] = [work_surface_proactive]
        store._counterpart_history = [work_surface_counterpart]
        store._proactive_history = [work_surface_proactive]

        session = BackendSession(
            graph=FakeStreamGraph(stream_rows=[], state_values={}),
            memory_store=store,
            thread_id="thread-a",
        )

        worldline = session.worldline_view()
        bond = session.bond_view()

        for preview in (
            worldline["counterpart_assessment_preview"][0],
            bond["counterpart_assessment_preview"][0],
        ):
            embodied = preview.get("embodied_context") if isinstance(preview.get("embodied_context"), dict) else {}
            self.assertEqual(embodied.get("kind"), "workspace_file_updated")
            self.assertEqual(embodied.get("workspace_root"), "E:/runtime/workspaces/lab-notes")
            self.assertEqual(embodied.get("artifact_mutation_mode"), "append")
            self.assertEqual(embodied.get("active_artifact_kind"), "file")
            self.assertEqual(embodied.get("active_artifact_label"), "today.md")
            self.assertTrue(bool(embodied.get("procedural_growth")))

        for preview in (
            worldline["proactive_continuity_preview"][0],
            bond["proactive_continuity_preview"][0],
        ):
            embodied = preview.get("embodied_context") if isinstance(preview.get("embodied_context"), dict) else {}
            self.assertEqual(embodied.get("kind"), "artifact_reacquired")
            self.assertEqual(embodied.get("workspace_root"), "E:/runtime/workspaces/lab-notes")
            self.assertEqual(embodied.get("artifact_reacquisition_mode"), "reopen_file")
            self.assertEqual(embodied.get("artifact_mutation_mode"), "replace")
            self.assertEqual(embodied.get("active_artifact_kind"), "file")
            self.assertEqual(embodied.get("active_artifact_label"), "today.md")

    def test_session_preview_views_preserve_workspace_path_inspection_embodied_context(self):
        store = FakeMemoryStore()
        work_surface_counterpart = {
            "id": 14,
            "summary": "她已经把那块文件工作面重新看过一遍了。",
            "stance": "open",
            "scene": "co_work",
            "created_at": 1710000105,
            "embodied_context": {
                "kind": "workspace_path_inspected",
                "summary": "她已经重新看过 today.md 的当前内容。",
                "artifact_continuity": "attached",
                "active_artifact_kind": "file",
                "active_artifact_ref": "notes/today.md",
                "active_artifact_label": "today.md",
                "workspace_root": "E:/runtime/workspaces/lab-notes",
                "primary_status": "completed",
            },
        }
        work_surface_proactive = {
            "id": 15,
            "summary": "前面那条文件工作面已经重新看过一遍，后面的动作可以顺着它继续。",
            "kind": "promoted",
            "trace_family": "workspace_path_inspected_followthrough",
            "carryover_mode": "continue_work_surface",
            "created_at": 1710000106,
            "embodied_context": {
                "kind": "workspace_path_inspected",
                "summary": "她已经重新看过 notes/today.md 的当前内容。",
                "artifact_continuity": "attached",
                "active_artifact_kind": "file",
                "active_artifact_ref": "notes/today.md",
                "active_artifact_label": "today.md",
                "workspace_root": "E:/runtime/workspaces/lab-notes",
                "primary_status": "completed",
            },
        }
        store._snapshot["counterpart_assessment_history"] = [work_surface_counterpart]
        store._snapshot["proactive_continuity_history"] = [work_surface_proactive]
        store._counterpart_history = [work_surface_counterpart]
        store._proactive_history = [work_surface_proactive]

        session = BackendSession(
            graph=FakeStreamGraph(stream_rows=[], state_values={}),
            memory_store=store,
            thread_id="thread-a",
        )

        worldline = session.worldline_view()
        bond = session.bond_view()

        for preview in (
            worldline["counterpart_assessment_preview"][0],
            bond["counterpart_assessment_preview"][0],
        ):
            embodied = preview.get("embodied_context") if isinstance(preview.get("embodied_context"), dict) else {}
            self.assertEqual(embodied.get("kind"), "workspace_path_inspected")
            self.assertEqual(embodied.get("workspace_root"), "E:/runtime/workspaces/lab-notes")
            self.assertEqual(embodied.get("active_artifact_kind"), "file")
            self.assertEqual(embodied.get("active_artifact_label"), "today.md")
            self.assertFalse(bool(embodied.get("artifact_mutation_mode")))

        for preview in (
            worldline["proactive_continuity_preview"][0],
            bond["proactive_continuity_preview"][0],
        ):
            embodied = preview.get("embodied_context") if isinstance(preview.get("embodied_context"), dict) else {}
            self.assertEqual(embodied.get("kind"), "workspace_path_inspected")
            self.assertEqual(embodied.get("workspace_root"), "E:/runtime/workspaces/lab-notes")
            self.assertEqual(embodied.get("artifact_continuity"), "attached")
            self.assertEqual(embodied.get("active_artifact_kind"), "file")
            self.assertEqual(embodied.get("active_artifact_label"), "today.md")
            self.assertFalse(bool(embodied.get("artifact_mutation_mode")))

    def test_session_preview_views_preserve_access_state_embodied_context(self):
        store = FakeMemoryStore()
        access_resolved_counterpart = {
            "id": 16,
            "summary": "权限已经接通，这次不是悬空的提案了。",
            "stance": "open",
            "scene": "co_work",
            "created_at": 1710000107,
            "embodied_context": {
                "kind": "workspace_access_resolved",
                "summary": "可写工作区 lab-notes 已经真的创建好并接入当前上下文。",
                "access_mode": "tool_enabled",
                "filesystem_state": "writable",
                "session_continuity": "stable",
                "session_recovery_mode": "refresh_session",
                "active_artifact_kind": "workspace",
                "active_artifact_ref": "E:/runtime/workspaces/lab-notes",
                "active_artifact_label": "lab-notes",
                "workspace_root": "E:/runtime/workspaces/lab-notes",
                "artifact_continuity": "attached",
                "access_acquire_proposals": [
                    {
                        "target": "filesystem",
                        "mode": "operator_create_workspace",
                        "summary": "先新建一个可写工作区。",
                        "grants": ["filesystem", "workspace_write"],
                        "requires_operator": True,
                    }
                ],
                "selected_access_proposal": {
                    "target": "filesystem",
                    "mode": "operator_create_workspace",
                    "summary": "先新建一个可写工作区。",
                    "grants": ["filesystem", "workspace_write"],
                    "requires_operator": True,
                },
                "primary_status": "completed",
            },
        }
        access_refreshed_proactive = {
            "id": 17,
            "summary": "她重新检查完入口状态，把这条稳定路径继续留在当前连续性里。",
            "kind": "promoted",
            "trace_family": "access_state_refresh_followthrough",
            "carryover_mode": "continue_work_surface",
            "created_at": 1710000108,
            "embodied_context": {
                "kind": "access_state_refreshed",
                "summary": "已重新检查当前入口状态，眼下这条路径是稳定的。",
                "access_mode": "tool_enabled",
                "api_key_state": "present",
                "filesystem_state": "writable",
                "network_access": "enabled",
                "session_continuity": "stable",
                "session_recovery_mode": "refresh_session",
                "access_acquire_proposals": [
                    {
                        "target": "filesystem",
                        "mode": "operator_create_workspace",
                        "summary": "如果要新的可写工作区，可以让你补一个。",
                        "grants": ["filesystem", "workspace_write"],
                        "requires_operator": True,
                    }
                ],
                "selected_access_proposal": {
                    "target": "filesystem",
                    "mode": "operator_create_workspace",
                    "summary": "如果要新的可写工作区，可以让你补一个。",
                    "grants": ["filesystem", "workspace_write"],
                    "requires_operator": True,
                },
                "primary_status": "completed",
            },
        }
        store._snapshot["counterpart_assessment_history"] = [access_resolved_counterpart]
        store._snapshot["proactive_continuity_history"] = [access_refreshed_proactive]
        store._counterpart_history = [access_resolved_counterpart]
        store._proactive_history = [access_refreshed_proactive]

        session = BackendSession(
            graph=FakeStreamGraph(stream_rows=[], state_values={}),
            memory_store=store,
            thread_id="thread-a",
        )

        worldline = session.worldline_view()
        bond = session.bond_view()

        for preview in (
            worldline["counterpart_assessment_preview"][0],
            bond["counterpart_assessment_preview"][0],
        ):
            embodied = preview.get("embodied_context") if isinstance(preview.get("embodied_context"), dict) else {}
            self.assertEqual(embodied.get("kind"), "workspace_access_resolved")
            self.assertEqual(embodied.get("filesystem_state"), "writable")
            self.assertEqual(embodied.get("session_continuity"), "stable")
            self.assertEqual(embodied.get("session_recovery_mode"), "refresh_session")
            self.assertEqual(embodied.get("workspace_root"), "E:/runtime/workspaces/lab-notes")
            self.assertEqual(embodied.get("selected_access_proposal", {}).get("mode"), "operator_create_workspace")
            self.assertEqual(embodied.get("access_acquire_proposals", [])[0]["target"], "filesystem")

        for preview in (
            worldline["proactive_continuity_preview"][0],
            bond["proactive_continuity_preview"][0],
        ):
            embodied = preview.get("embodied_context") if isinstance(preview.get("embodied_context"), dict) else {}
            self.assertEqual(embodied.get("kind"), "access_state_refreshed")
            self.assertEqual(embodied.get("api_key_state"), "present")
            self.assertEqual(embodied.get("filesystem_state"), "writable")
            self.assertEqual(embodied.get("network_access"), "enabled")
            self.assertEqual(embodied.get("session_continuity"), "stable")
            self.assertEqual(embodied.get("session_recovery_mode"), "refresh_session")
            self.assertEqual(embodied.get("selected_access_proposal", {}).get("mode"), "operator_create_workspace")
            self.assertEqual(embodied.get("access_acquire_proposals", [])[0]["target"], "filesystem")

    def test_session_history_views_normalize_content_only_embodied_context(self):
        store = FakeMemoryStore()
        content_only_counterpart = {
            "id": 18,
            "content": {
                "summary": "她确认这次工作面已经真的接回来了。",
                "stance": "open",
                "scene": "co_work",
                "created_at": 1710000109,
                "embodied_context": {
                    "kind": "workspace_access_resolved",
                    "workspace_root": "E:/runtime/workspaces/lab-notes",
                    "filesystem_state": "writable",
                    "session_continuity": "stable",
                    "session_recovery_mode": "refresh_session",
                },
            },
        }
        content_only_proactive = {
            "id": 19,
            "content": {
                "summary": "她把这条稳定入口继续带进后续连续性里。",
                "kind": "promoted",
                "trace_family": "access_state_refresh_followthrough",
                "carryover_mode": "continue_work_surface",
                "created_at": 1710000110,
                "embodied_context": {
                    "kind": "access_state_refreshed",
                    "api_key_state": "present",
                    "filesystem_state": "writable",
                    "network_access": "enabled",
                    "session_continuity": "stable",
                },
            },
        }
        store._snapshot["counterpart_assessment_history"] = [content_only_counterpart]
        store._snapshot["proactive_continuity_history"] = [content_only_proactive]
        store._counterpart_history = [content_only_counterpart]
        store._proactive_history = [content_only_proactive]

        session = BackendSession(
            graph=FakeStreamGraph(stream_rows=[], state_values={}),
            memory_store=store,
            thread_id="thread-a",
        )

        worldline = session.worldline_view()
        bond = session.bond_view()

        self.assertEqual(worldline["counterpart_assessment_history"][0]["scene"], "co_work")
        self.assertEqual(
            worldline["counterpart_assessment_history"][0]["embodied_context"]["kind"],
            "workspace_access_resolved",
        )
        self.assertEqual(
            worldline["counterpart_assessment_history"][0]["embodied_context"]["workspace_root"],
            "E:/runtime/workspaces/lab-notes",
        )
        self.assertIn(
            "bodyfx=workspace_access_resolved",
            worldline["counterpart_assessment_history"][0].get("preview_line") or "",
        )
        self.assertEqual(bond["counterpart_assessment_history"][0]["scene"], "co_work")
        self.assertEqual(
            bond["counterpart_assessment_history"][0]["embodied_context"]["session_recovery_mode"],
            "refresh_session",
        )
        self.assertIn(
            "root=E:/runtime/workspaces/lab-notes",
            bond["counterpart_assessment_history"][0].get("preview_line") or "",
        )
        self.assertEqual(worldline["proactive_continuity_history"][0]["trace_family"], "access_state_refresh_followthrough")
        self.assertEqual(
            worldline["proactive_continuity_history"][0]["embodied_context"]["kind"],
            "access_state_refreshed",
        )
        self.assertEqual(
            worldline["proactive_continuity_history"][0]["embodied_context"]["api_key_state"],
            "present",
        )
        self.assertEqual(bond["proactive_continuity_history"][0]["carryover_mode"], "continue_work_surface")
        self.assertEqual(
            bond["proactive_continuity_history"][0]["embodied_context"]["network_access"],
            "enabled",
        )
        self.assertIn(
            "bodyfx=access_state_refreshed",
            worldline["proactive_continuity_history"][0].get("preview_line") or "",
        )
        self.assertIn(
            "carry=continue_work_surface:0.00",
            bond["proactive_continuity_history"][0].get("preview_line") or "",
        )

    def test_worldline_and_bond_views_normalize_content_only_memory_rows(self):
        store = FakeMemoryStore()
        store._snapshot["worldline_events"] = [
            {
                "id": 20,
                "content": {
                    "summary": "她把这次入口接通记成了一次真实发生过的共事。",
                    "category": "shared_event",
                    "importance": 0.73,
                },
            }
        ]
        store._snapshot["commitments"] = [
            {
                "id": 21,
                "content": {
                    "text": "晚点继续看 lab-notes。",
                    "status": "open",
                },
            }
        ]
        store._snapshot["unresolved_tensions"] = [
            {
                "id": 22,
                "content": {
                    "summary": "还有一点收口前的不确定感。",
                    "severity": 0.31,
                    "status": "open",
                },
            }
        ]
        store._snapshot["semantic_self_narratives"] = [
            {
                "id": 23,
                "content": {
                    "text": "她会把真实接通的工作面沉淀回长期连续性。",
                    "category": "agency_style",
                },
            }
        ]
        store._timeline = [
            {
                "id": 24,
                "content": {
                    "summary": "关系因为真实共事而往前推了一点。",
                    "affinity_delta": 0.08,
                    "trust_delta": 0.11,
                },
            }
        ]
        store._repairs = [
            {
                "id": 25,
                "content": {
                    "summary": "误会已经解释清楚了一部分。",
                },
            }
        ]

        session = BackendSession(
            graph=FakeStreamGraph(stream_rows=[], state_values={}),
            memory_store=store,
            thread_id="thread-a",
        )

        worldline = session.worldline_view()
        bond = session.bond_view()

        self.assertEqual(worldline["worldline_events"][0]["summary"], "她把这次入口接通记成了一次真实发生过的共事。")
        self.assertEqual(worldline["worldline_events"][0]["category"], "shared_event")
        self.assertEqual(worldline["commitments"][0]["text"], "晚点继续看 lab-notes。")
        self.assertEqual(worldline["commitments"][0]["status"], "open")
        self.assertEqual(worldline["unresolved_tensions"][0]["summary"], "还有一点收口前的不确定感。")
        self.assertEqual(worldline["semantic_self_narratives"][0]["text"], "她会把真实接通的工作面沉淀回长期连续性。")
        self.assertEqual(worldline["semantic_self_narratives"][0]["category"], "agency_style")
        self.assertEqual(bond["relationship_timeline"][0]["summary"], "关系因为真实共事而往前推了一点。")
        self.assertEqual(bond["relationship_timeline"][0]["affinity_delta"], 0.08)
        self.assertEqual(bond["relationship_timeline"][0]["trust_delta"], 0.11)
        self.assertEqual(bond["conflict_repair"][0]["summary"], "误会已经解释清楚了一部分。")

    def test_worldline_view_normalizes_revision_trace_embodied_context(self):
        store = FakeMemoryStore()
        store._snapshot["revision_traces"] = [
            {
                "id": 18,
                "source": "auto:passive_evolution_final",
                "behavior_consequence": {
                    "embodied_context": {
                        "kind": "access_state_refreshed",
                        "api_key_state": "present",
                        "filesystem_state": "writable",
                        "network_access": "enabled",
                        "session_continuity": "stable",
                        "session_recovery_mode": "refresh_session",
                        "access_acquire_proposals": [
                            {
                                "target": "filesystem",
                                "mode": "operator_create_workspace",
                                "summary": "需要时可以补一个新工作区。",
                                "grants": ["filesystem", "workspace_write"],
                                "requires_operator": True,
                            }
                        ],
                        "selected_access_proposal": {
                            "target": "filesystem",
                            "mode": "operator_create_workspace",
                            "summary": "需要时可以补一个新工作区。",
                            "grants": ["filesystem", "workspace_write"],
                            "requires_operator": True,
                        },
                    }
                },
            }
        ]

        session = BackendSession(
            graph=FakeStreamGraph(stream_rows=[], state_values={}),
            memory_store=store,
            thread_id="thread-a",
        )

        worldline = session.worldline_view()
        trace = worldline["revision_traces"][0]
        embodied = trace.get("embodied_context") if isinstance(trace.get("embodied_context"), dict) else {}
        self.assertEqual(embodied.get("kind"), "access_state_refreshed")
        self.assertEqual(embodied.get("api_key_state"), "present")
        self.assertEqual(embodied.get("filesystem_state"), "writable")
        self.assertEqual(embodied.get("network_access"), "enabled")
        self.assertEqual(embodied.get("session_continuity"), "stable")
        self.assertEqual(embodied.get("session_recovery_mode"), "refresh_session")
        self.assertEqual(embodied.get("selected_access_proposal", {}).get("mode"), "operator_create_workspace")
        self.assertEqual(embodied.get("access_acquire_proposals", [])[0]["target"], "filesystem")
        self.assertIn("bodyfx=access_state_refreshed", trace.get("preview_line") or "")
        self.assertIn("proposal=operator_create_workspace@filesystem", trace.get("preview_line") or "")

    def test_build_evolution_summary_derives_worldline_focus_from_memory_when_state_is_missing_field(self):
        values = {
            "persona_state": {"role": "kurisu_amadeus"},
            "emotion_state": {"label": "care"},
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        summary = session.build_evolution_summary()

        self.assertEqual(summary["worldline_focus_preview"][0], "提醒他吃饭。")
        self.assertEqual(summary["worldline_focus_items"][0]["kind"], "commitment")

    def test_build_evolution_summary_preserves_explicit_empty_worldline_focus(self):
        values = {
            "persona_state": {"role": "kurisu_amadeus"},
            "emotion_state": {"label": "care"},
            "worldline_focus": [],
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        summary = session.build_evolution_summary()

        self.assertEqual(summary["worldline_focus_preview"], [])
        self.assertEqual(summary["worldline_focus_items"], [])

    def test_build_evolution_summary_normalizes_event_identity_from_session_context(self):
        values = {
            "session_context": {
                "thread_id": "thread-a",
                "turn_id": "thread-a:555",
            },
            "current_event": {
                "kind": "idle",
                "source": "scheduler",
                "created_at": 555,
                "perception": {},
            },
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        summary = session.build_evolution_summary()
        event_residue = summary.get("event_residue") if isinstance(summary.get("event_residue"), dict) else {}

        self.assertEqual(event_residue.get("thread_id"), "thread-a")
        self.assertEqual(event_residue.get("turn_id"), "thread-a:555")
        self.assertEqual(event_residue.get("event_id"), "thread-a:555:idle:scheduler")

    def test_build_evolution_summary_backfills_sparse_event_perception_from_session_context(self):
        values = {
            "session_context": {
                "thread_id": "thread-a",
                "turn_id": "thread-a:555",
                "channel": "system",
                "modality": "system",
                "source_role": "system",
                "trust_tier": "high",
                "salience": 0.58,
                "interruptibility": "soft",
                "delivery_mode": "scheduled",
                "is_proactive": False,
            },
            "current_event": {
                "kind": "idle",
                "source": "scheduler",
                "created_at": 555,
                "perception": {},
            },
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        summary = session.build_evolution_summary()
        event_residue = summary.get("event_residue") if isinstance(summary.get("event_residue"), dict) else {}

        self.assertEqual(event_residue.get("thread_id"), "thread-a")
        self.assertEqual(event_residue.get("turn_id"), "thread-a:555")
        self.assertEqual(event_residue.get("event_id"), "thread-a:555:idle:scheduler")
        self.assertEqual(event_residue.get("channel"), "system")
        self.assertEqual(event_residue.get("modality"), "system")
        self.assertEqual(event_residue.get("source_role"), "system")
        self.assertEqual(event_residue.get("trust_tier"), "high")
        self.assertEqual(event_residue.get("salience"), 0.58)
        self.assertEqual(event_residue.get("interruptibility"), "soft")
        self.assertEqual(event_residue.get("delivery_mode"), "scheduled")
        self.assertFalse(event_residue.get("is_proactive"))

    def test_persona_view_uses_same_normalized_current_event_as_evolution_summary_for_plan_derivation(self):
        values = {
            "session_context": {
                "thread_id": "thread-a",
                "turn_id": "thread-a:555",
            },
            "current_event": {
                "created_at": 555,
                "perception": {},
            },
            "reconsolidation_snapshot": {
                "behavior_action": {
                    "action_target": "wait_and_recheck",
                    "interaction_mode": "deferred_watch",
                    "primary_motive": "honor_continuity",
                    "goal_frame": "顺着余温等更自然的窗口。",
                    "deferred_action_family": "observe",
                }
            },
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        def _derive(current_event, action, world_model_state=None):
            kind = str((current_event or {}).get("kind") or "").strip() or "missing"
            return {
                "kind": f"derived:{kind}",
                "target": "counterpart",
                "scheduled_after_min": 12,
                "trigger_family": kind,
            }

        with patch("amadeus_thread0.runtime.final_state._behavior_plan_from_action", side_effect=_derive):
            worldline = session.worldline_view()
            persona = session.persona_view()

        self.assertEqual(worldline["worldline_summary"]["behavior_plan"]["kind"], "derived:external_event")
        self.assertEqual(worldline["worldline_summary"]["behavior_plan"]["trigger_family"], "external_event")
        self.assertEqual(persona["evolution_summary"]["behavior_plan"]["kind"], "derived:external_event")
        self.assertEqual(persona["behavior_plan"]["kind"], "derived:external_event")
        self.assertEqual(persona["behavior_plan"]["trigger_family"], "external_event")

    def test_build_evolution_summary_preserves_event_created_at_and_tags(self):
        values = {
            "current_event": {
                "kind": "scheduled_life_due",
                "response_style_hint": "relationship",
                "science_mode": False,
                "continuation_mode": True,
                "counterpart_name": "冈部伦太郎",
                "appraisal_label": "care",
                "appraisal_confidence": 0.61,
                "created_at": 1710000018,
                "tags": ["user_busy", "commitment_window", ""],
                "derived_from_plan_kind": "commitment_window",
                "commitment_id": 12,
                "due_at": "今晚",
                "attention_target_hint": "counterpart_state",
                "nonverbal_signal_hint": "quiet_glance",
            }
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        summary = session.build_evolution_summary()
        event_residue = summary.get("event_residue") if isinstance(summary.get("event_residue"), dict) else {}

        self.assertEqual(event_residue.get("created_at"), 1710000018)
        self.assertEqual(event_residue.get("tags"), ["user_busy", "commitment_window"])
        self.assertEqual(event_residue.get("response_style_hint"), "relationship")
        self.assertFalse(event_residue.get("science_mode"))
        self.assertTrue(event_residue.get("continuation_mode"))
        self.assertEqual(event_residue.get("counterpart_name"), "冈部伦太郎")
        self.assertEqual(event_residue.get("appraisal_label"), "care")
        self.assertEqual(event_residue.get("appraisal_confidence"), 0.61)
        self.assertEqual(event_residue.get("derived_from_plan_kind"), "commitment_window")
        self.assertEqual(event_residue.get("commitment_id"), 12)
        self.assertEqual(event_residue.get("due_at"), "今晚")
        self.assertEqual(event_residue.get("attention_target_hint"), "counterpart_state")
        self.assertEqual(event_residue.get("nonverbal_signal_hint"), "quiet_glance")

    def test_session_views_use_final_reconsolidation_snapshot_for_evolution_summary(self):
        final_snapshot = {
            "event_kind": "user_utterance",
            "interaction_frame": "relationship",
            "primary_motive": "gentle_recontact",
            "motive_tension": "self_rhythm_vs_contact",
            "goal_frame": "先从自己的节奏里回头，留一个不压迫对方的小开口。",
            "behavior_plan": {
                "kind": "deferred_checkin",
                "target": "counterpart",
                "trigger_family": "observe",
                "scheduled_after_min": 20,
                "relationship_weather": "steady_warmth",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "quiet_glance",
                "note": "先把窗口留着，再看要不要顺手接回来。",
                "carryover_mode": "warm_residue",
                "carryover_strength": 0.67,
                "presence_residue": 0.4,
                "ambient_resonance": 0.2,
                "self_activity_momentum": 0.3,
                "embodied_context": {
                    "kind": "access_request_pending",
                    "summary": "这一步还卡在审批门口。",
                    "requested_access": ["workspace_write"],
                    "requested_help": True,
                    "primary_status": "awaiting_approval",
                },
            },
            "interaction_carryover": {
                "source": "reconsolidation",
                "strength": 0.67,
                "carryover_mode": "warm_residue",
                "relationship_weather": "steady_warmth",
                "note": "final carryover should win",
                "embodied_context": {
                    "kind": "access_request_pending",
                    "summary": "她把动作推进到了审批门口。",
                    "requested_access": ["workspace_write"],
                    "requested_help": True,
                    "primary_status": "awaiting_approval",
                },
            },
            "counterpart": {
                "summary": "她会先把这次开口当成带着摩擦感的重新靠近，不会直接判成已经完全放松下来了。",
                "stance": "guarded",
                "scene": "relationship_degradation",
                "respect_level": 0.38,
                "reciprocity": 0.34,
                "boundary_pressure": 0.52,
                "reliability_read": 0.42,
                "assessment_profile": {
                    "openness_drive": 0.28,
                    "guarded_drive": 0.71,
                    "guard_margin": 0.43,
                    "dominant_scene_signal": "friction",
                    "scene_strengths": {"friction": 0.79, "care": 0.12},
                },
            },
            "behavior_consequence": {
                "kind": "leave_small_opening",
                "summary": "她回头了，但只留了一个轻一点的小开口。",
                "embodied_context": {
                    "kind": "environmental_friction",
                    "summary": "浏览器会话还没准备好。",
                    "missing_access": ["browser_session"],
                    "environmental_friction": True,
                },
            },
            "agenda_lifecycle_consequence": {
                "kind": "released_to_self_activity",
                "carryover_mode": "own_rhythm",
            },
        }
        values = {
            "persona_state": {"role": "kurisu_amadeus"},
            "emotion_state": {"label": "care"},
            "bond_state": {"trust": 0.7, "closeness": 0.68, "hurt": 0.02},
            "counterpart_assessment": {"stance": "open", "scene": "care_bid"},
            "semantic_narrative_profile": {"presence_carry": 0.5},
            "world_model_state": {"presence_residue": 0.4, "ambient_resonance": 0.2, "self_activity_momentum": 0.3},
            "reconsolidation_snapshot": final_snapshot,
            "behavior_action": {
                "interaction_mode": "self_activity_reopen",
                "primary_motive": "gentle_recontact",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "先从自己的节奏里回头。",
            },
            "behavior_plan": {"kind": "deferred_checkin", "relationship_weather": "stale_live_weather"},
            "behavior_queue": [],
            "interaction_carryover": {"carryover_mode": "own_rhythm", "strength": 0.53, "relationship_weather": "warm_residue"},
            "current_event": {"kind": "user_utterance"},
            "worldline_focus": [],
            "agenda_lifecycle_residue": {"kind": "held"},
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        worldline = session.worldline_view()
        worldline_turn = worldline["worldline_summary"]["current_turn"]
        self.assertEqual(worldline_turn["recon_event_kind"], "user_utterance")
        self.assertEqual(worldline_turn["recon_interaction_frame"], "relationship")
        self.assertEqual(worldline_turn["behavior_consequence_kind"], "leave_small_opening")
        self.assertIn("小开口", worldline_turn["behavior_consequence_summary"])
        self.assertEqual(
            worldline_turn["counterpart_summary"],
            "她会先把这次开口当成带着摩擦感的重新靠近，不会直接判成已经完全放松下来了。",
        )
        lifecycle = worldline["worldline_summary"]["agenda_lifecycle"]
        self.assertEqual(lifecycle["kind"], "released_to_self_activity")
        self.assertEqual(lifecycle["carryover_mode"], "own_rhythm")

        persona = session.persona_view()
        self.assertEqual(persona["reconsolidation_snapshot"], final_snapshot)
        persona_turn = persona["evolution_summary"]["current_turn"]
        self.assertEqual(persona_turn["behavior_consequence_kind"], "leave_small_opening")
        self.assertEqual(persona_turn["counterpart_stance"], "guarded")
        self.assertEqual(persona_turn["counterpart_scene"], "relationship_degradation")
        counterpart_profile = persona_turn.get("counterpart_profile") if isinstance(persona_turn.get("counterpart_profile"), dict) else {}
        self.assertEqual(counterpart_profile.get("dominant_scene_signal"), "friction")
        self.assertEqual(counterpart_profile.get("guarded_drive"), 0.71)
        self.assertEqual(worldline_turn["carryover_mode"], "warm_residue")
        self.assertEqual(worldline_turn["carryover_strength"], 0.67)
        self.assertEqual(worldline["worldline_summary"]["behavior_plan"]["relationship_weather"], "steady_warmth")
        self.assertEqual(worldline["worldline_summary"]["behavior_plan"]["attention_target"], "counterpart_state")
        self.assertEqual(worldline["worldline_summary"]["behavior_plan"]["nonverbal_signal"], "quiet_glance")
        self.assertEqual(
            (worldline["worldline_summary"]["behavior_plan"].get("embodied_context") or {}).get("kind"),
            "access_request_pending",
        )
        self.assertEqual(
            (worldline["worldline_summary"].get("behavior_consequence") or {}).get("embodied_context", {}).get("kind"),
            "environmental_friction",
        )
        self.assertEqual(persona["counterpart_assessment"]["scene"], "relationship_degradation")
        self.assertEqual(persona["counterpart_assessment"]["stance"], "guarded")
        self.assertIn("重新靠近", persona["counterpart_assessment"]["summary"])
        persona_profile = (
            persona["counterpart_assessment"].get("assessment_profile")
            if isinstance(persona["counterpart_assessment"].get("assessment_profile"), dict)
            else {}
        )
        self.assertEqual(persona_profile.get("dominant_scene_signal"), "friction")
        self.assertEqual(persona_profile.get("guarded_drive"), 0.71)
        self.assertEqual(persona_profile.get("safety_read"), counterpart_profile.get("safety_read"))
        self.assertEqual(persona_profile.get("repairability"), counterpart_profile.get("repairability"))
        self.assertEqual(persona_profile.get("predictability"), counterpart_profile.get("predictability"))
        self.assertEqual(persona_profile.get("dependency_risk"), counterpart_profile.get("dependency_risk"))
        self.assertEqual(persona_profile.get("closeness_read"), counterpart_profile.get("closeness_read"))
        self.assertEqual(persona["agenda_lifecycle_residue"]["kind"], "released_to_self_activity")
        self.assertEqual(persona["agenda_lifecycle_residue"]["carryover_mode"], "own_rhythm")
        self.assertEqual(persona["interaction_carryover"]["source"], "reconsolidation")
        self.assertEqual(persona["interaction_carryover"]["relationship_weather"], "steady_warmth")
        persona_carryover_embodied = (
            persona["interaction_carryover"].get("embodied_context")
            if isinstance(persona["interaction_carryover"].get("embodied_context"), dict)
            else {}
        )
        self.assertEqual(persona_carryover_embodied.get("kind"), "access_request_pending")
        self.assertEqual(persona_carryover_embodied.get("requested_access"), ["workspace_write"])
        summary_carryover = (
            persona["evolution_summary"].get("interaction_carryover")
            if isinstance(persona["evolution_summary"].get("interaction_carryover"), dict)
            else {}
        )
        self.assertEqual(summary_carryover.get("carryover_mode"), "warm_residue")
        self.assertEqual((summary_carryover.get("embodied_context") or {}).get("kind"), "access_request_pending")
        self.assertEqual(
            (
                persona["evolution_summary"]
                .get("current_turn", {})
                .get("behavior_consequence_embodied_context", {})
                .get("kind")
            ),
            "environmental_friction",
        )

    def test_persona_and_worldline_views_prefer_final_persisted_behavior_plan_over_derived_plan(self):
        values = {
            "world_model_state": {"presence_residue": 0.42},
            "current_event": {"kind": "self_activity_state"},
            "behavior_action": {
                "action_target": "offer_small_opening",
                "interaction_mode": "self_activity_reopen",
                "primary_motive": "gentle_recontact",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "顺着余温轻轻回头。",
                "deferred_action_family": "small_opening",
                "relationship_weather": "warm_residue",
            },
            "behavior_plan": {
                "kind": "deferred_checkin",
                "target": "counterpart",
                "trigger_family": "observe",
                "scheduled_after_min": 45,
                "legacy_hint": "keep-me",
            },
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        with patch(
            "amadeus_thread0.runtime.final_state._behavior_plan_from_action",
            return_value={
                "kind": "small_opening",
                "target": "counterpart",
                "scheduled_after_min": 0,
                "trigger_family": "small_opening",
                "primary_motive": "gentle_recontact",
            },
        ) as mock_derive:
            worldline = session.worldline_view()
            persona = session.persona_view()

        self.assertEqual(worldline["worldline_summary"]["behavior_plan"]["kind"], "deferred_checkin")
        self.assertEqual(worldline["worldline_summary"]["behavior_plan"]["scheduled_after_min"], 45)
        self.assertEqual(persona["behavior_plan"]["kind"], "deferred_checkin")
        self.assertEqual(persona["behavior_plan"]["trigger_family"], "observe")
        self.assertEqual(persona["behavior_plan"]["legacy_hint"], "keep-me")
        self.assertEqual(persona["evolution_summary"]["behavior_plan"]["kind"], "deferred_checkin")
        mock_derive.assert_not_called()

    def test_persona_and_worldline_views_prefer_frozen_behavior_plan_with_context_only_signal(self):
        values = {
            "world_model_state": {"presence_residue": 0.42},
            "current_event": {"kind": "self_activity_state"},
            "behavior_plan": {
                "kind": "deferred_checkin",
                "target": "counterpart",
                "trigger_family": "observe",
                "scheduled_after_min": 45,
            },
            "reconsolidation_snapshot": {
                "behavior_plan": {
                    "note": "final frozen context should win",
                    "attention_target": "counterpart_state",
                    "nonverbal_signal": "quiet_glance",
                    "carryover_strength": 0.46,
                    "presence_residue": 0.33,
                    "ambient_resonance": 0.22,
                    "self_activity_momentum": 0.58,
                    "allow_interrupt": False,
                }
            },
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        worldline = session.worldline_view()
        persona = session.persona_view()

        self.assertEqual(worldline["worldline_summary"]["behavior_plan"]["kind"], "")
        self.assertEqual(worldline["worldline_summary"]["behavior_plan"]["note"], "final frozen context should win")
        self.assertEqual(worldline["worldline_summary"]["behavior_plan"]["attention_target"], "counterpart_state")
        self.assertEqual(worldline["worldline_summary"]["behavior_plan"]["nonverbal_signal"], "quiet_glance")
        self.assertEqual(worldline["worldline_summary"]["behavior_plan"]["presence_residue"], 0.33)
        self.assertEqual(worldline["worldline_summary"]["behavior_plan"]["ambient_resonance"], 0.22)
        self.assertEqual(worldline["worldline_summary"]["behavior_plan"]["self_activity_momentum"], 0.58)
        self.assertFalse(worldline["worldline_summary"]["behavior_plan"]["allow_interrupt"])
        self.assertEqual(persona["behavior_plan"]["note"], "final frozen context should win")
        self.assertEqual(persona["behavior_plan"]["attention_target"], "counterpart_state")
        self.assertEqual(persona["behavior_plan"]["nonverbal_signal"], "quiet_glance")
        self.assertEqual(persona["behavior_plan"]["carryover_strength"], 0.46)
        self.assertFalse(persona["behavior_plan"]["allow_interrupt"])

    def test_persona_and_worldline_views_prefer_frozen_reconsolidation_behavior_action(self):
        values = {
            "world_model_state": {"presence_residue": 0.42},
            "current_event": {"kind": "self_activity_state"},
            "behavior_action": {
                "action_target": "hold_own_rhythm",
                "interaction_mode": "self_activity_hold",
                "primary_motive": "preserve_self_rhythm",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "stale live action should not win",
                "initiative_shape": "pause",
                "disclosure_posture": "tight",
                "initiative_level": 0.22,
                "window_profile": {
                    "profile_type": "self_opening",
                    "decision": "hold_own_rhythm",
                    "readiness": 0.22,
                    "required_readiness": 0.49,
                    "reopen_ready": False,
                },
            },
            "behavior_plan": {
                "kind": "self_activity_continue",
                "target": "self",
                "trigger_family": "self_activity",
            },
            "reconsolidation_snapshot": {
                "behavior_action": {
                    "action_target": "wait_and_recheck",
                    "interaction_mode": "deferred_watch",
                    "primary_motive": "honor_continuity",
                    "motive_tension": "contact_without_pressure",
                    "goal_frame": "顺着前面的惦记等更自然的时候再接回来。",
                    "deferred_action_family": "life_window",
                    "timing_window_min": 30,
                    "engagement_level": 0.61,
                    "initiative_level": 0.47,
                    "task_focus": "relationship",
                    "affect_surface": "gentle",
                    "silence_ok": True,
                    "proactive_checkin_readiness": 0.39,
                    "initiative_shape": "micro_opening",
                    "disclosure_posture": "measured",
                    "note": "顺着余温看一眼，但不立刻把距离拉近。",
                    "relationship_weather": "warm_residue",
                    "embodied_context": {
                        "kind": "access_request_pending",
                        "summary": "她把动作推进到了审批门口。",
                        "requested_access": ["workspace_write"],
                        "requested_help": True,
                        "primary_status": "awaiting_approval",
                    },
                    "window_profile": {
                        "profile_type": "self_opening",
                        "event_kind": "self_activity_state",
                        "family": "self_activity",
                        "trigger_family": "life_window",
                        "stance": "watchful",
                        "scene": "repair_attempt",
                        "decision": "wait_and_recheck",
                        "readiness": 0.41,
                        "required_readiness": 0.57,
                        "reopen_ready": False,
                        "recheck_min": 18,
                        "continuity_bonus": 0.14,
                        "carryover_mode": "own_rhythm",
                        "carryover_strength": 0.46,
                        "presence_residue": 0.33,
                        "ambient_resonance": 0.22,
                        "self_activity_momentum": 0.58,
                        "recontact_echo": 0.29,
                        "own_rhythm_load": 0.63,
                    },
                },
                "behavior_plan": {
                    "kind": "deferred_checkin",
                    "target": "counterpart",
                    "trigger_family": "observe",
                    "scheduled_after_min": 30,
                },
            },
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        worldline = session.worldline_view()
        persona = session.persona_view()

        self.assertEqual(worldline["worldline_summary"]["current_turn"]["action_target"], "wait_and_recheck")
        self.assertEqual(worldline["worldline_summary"]["current_turn"]["behavior_mode"], "deferred_watch")
        self.assertEqual(worldline["worldline_summary"]["current_turn"]["initiative_shape"], "micro_opening")
        self.assertEqual(worldline["worldline_summary"]["current_turn"]["initiative_level"], 0.47)
        self.assertEqual(worldline["worldline_summary"]["current_turn"]["engagement_level"], 0.61)
        self.assertEqual(worldline["worldline_summary"]["current_turn"]["disclosure_posture"], "measured")
        self.assertEqual(worldline["worldline_summary"]["current_turn"]["behavior_note"], "顺着余温看一眼，但不立刻把距离拉近。")
        self.assertEqual(
            (
                worldline["worldline_summary"]["current_turn"]
                .get("behavior_action_embodied_context", {})
                .get("kind")
            ),
            "access_request_pending",
        )
        self.assertEqual(persona["behavior_action"]["primary_motive"], "honor_continuity")
        self.assertEqual(persona["behavior_action"]["timing_window_min"], 30)
        self.assertEqual(persona["behavior_action"]["initiative_shape"], "micro_opening")
        self.assertEqual(persona["behavior_action"]["initiative_level"], 0.47)
        self.assertEqual(persona["behavior_action"]["engagement_level"], 0.61)
        self.assertEqual(persona["behavior_action"]["disclosure_posture"], "measured")
        self.assertTrue(persona["behavior_action"]["silence_ok"])
        self.assertEqual(persona["behavior_action"]["task_focus"], "relationship")
        self.assertEqual(persona["behavior_action"]["note"], "顺着余温看一眼，但不立刻把距离拉近。")
        self.assertEqual((persona["behavior_action"].get("embodied_context") or {}).get("kind"), "access_request_pending")
        window = worldline["worldline_summary"]["opening_window"]
        self.assertEqual(window["profile_type"], "self_opening")
        self.assertEqual(window["decision"], "wait_and_recheck")
        self.assertEqual(window["readiness"], 0.41)
        self.assertEqual(window["required_readiness"], 0.57)
        self.assertEqual(window["recheck_min"], 18)
        self.assertEqual(persona["behavior_action"]["window_profile"]["decision"], "wait_and_recheck")
        self.assertEqual(persona["behavior_action"]["window_profile"]["own_rhythm_load"], 0.63)
        self.assertEqual(persona["evolution_summary"]["behavior_plan"]["kind"], "deferred_checkin")
        self.assertEqual(
            (
                persona["evolution_summary"]["current_turn"]
                .get("behavior_action_embodied_context", {})
                .get("kind")
            ),
            "access_request_pending",
        )

    def test_persona_and_worldline_views_derive_plan_from_frozen_action_before_live_plan(self):
        values = {
            "world_model_state": {"presence_residue": 0.42},
            "current_event": {"kind": "self_activity_state"},
            "behavior_action": {
                "action_target": "hold_own_rhythm",
                "interaction_mode": "self_activity_hold",
                "primary_motive": "preserve_self_rhythm",
                "goal_frame": "stale live action should not win",
            },
            "behavior_plan": {
                "kind": "self_activity_continue",
                "target": "self",
                "trigger_family": "self_activity",
                "scheduled_after_min": 45,
                "legacy_hint": "stale-live-plan",
            },
            "reconsolidation_snapshot": {
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
            },
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        with patch(
            "amadeus_thread0.runtime.final_state._behavior_plan_from_action",
            return_value={
                "kind": "deferred_checkin",
                "target": "counterpart",
                "trigger_family": "life_window",
                "scheduled_after_min": 30,
                "primary_motive": "honor_continuity",
            },
        ):
            worldline = session.worldline_view()
            persona = session.persona_view()

        self.assertEqual(worldline["worldline_summary"]["current_turn"]["action_target"], "wait_and_recheck")
        self.assertEqual(worldline["worldline_summary"]["behavior_plan"]["kind"], "deferred_checkin")
        self.assertEqual(worldline["worldline_summary"]["behavior_plan"]["trigger_family"], "life_window")
        self.assertEqual(worldline["worldline_summary"]["behavior_plan"]["scheduled_after_min"], 30)
        self.assertNotIn("legacy_hint", worldline["worldline_summary"]["behavior_plan"])
        self.assertEqual(persona["behavior_action"]["interaction_mode"], "deferred_watch")
        self.assertEqual(persona["behavior_plan"]["kind"], "deferred_checkin")
        self.assertEqual(persona["behavior_plan"]["trigger_family"], "life_window")
        self.assertEqual(persona["behavior_plan"]["scheduled_after_min"], 30)
        self.assertNotIn("legacy_hint", persona["behavior_plan"])
        self.assertEqual(persona["evolution_summary"]["behavior_plan"]["kind"], "deferred_checkin")

    def test_worldline_view_uses_final_persisted_semantic_self_narratives_not_retrieved_copy(self):
        final_snapshot = {
            "event_kind": "user_utterance",
            "interaction_frame": "relationship",
            "primary_motive": "preserve_self_rhythm",
            "behavior_consequence": {
                "kind": "released_to_self_activity",
                "summary": "她把注意力收回到自己的节奏里，但没有切断关系。",
            },
        }
        values = {
            "retrieved": {
                "semantic_self_narratives": [
                    {
                        "id": "retrieved-stale",
                        "text": "这还是上一轮检索出来的旧自我叙事。",
                        "category": "selfhood_style",
                    }
                ]
            },
            "reconsolidation_snapshot": final_snapshot,
            "behavior_action": {
                "interaction_mode": "self_activity_return",
                "primary_motive": "preserve_self_rhythm",
            },
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        memory_store = FakeMemoryStore()
        memory_store._snapshot["semantic_self_narratives"] = [
            {
                "id": 42,
                "text": "她会把最终做出的行动沉淀回自己的长期叙事，而不是停留在检索副本里。",
                "category": "agency_style",
                "source": "prepare_turn_runtime",
            }
        ]
        session = BackendSession(graph=graph, memory_store=memory_store, thread_id="thread-a")

        worldline = session.worldline_view()
        narratives = worldline["semantic_self_narratives"]
        self.assertEqual(len(narratives), 1)
        self.assertEqual(narratives[0]["id"], 42)
        self.assertIn("最终做出的行动", narratives[0]["text"])
        self.assertNotIn("retrieved-stale", {item.get("id") for item in narratives})
        self.assertEqual(
            worldline["worldline_summary"]["current_turn"]["behavior_consequence_kind"],
            "released_to_self_activity",
        )

    def test_bond_view_prefers_final_persisted_relationship_state_not_stale_runtime_copy(self):
        values = {
            "relationship": {
                "stage": "friend",
                "affinity_score": 0.0,
                "trust_score": 0.0,
                "notes": "",
            },
            "bond_state": {"trust": 0.68, "closeness": 0.66},
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        memory_store = FakeMemoryStore()
        memory_store._relationship = {
            "stage": "trusted",
            "affinity_score": 0.84,
            "trust_score": 0.87,
            "notes": "已经形成稳定信赖。",
        }
        session = BackendSession(graph=graph, memory_store=memory_store, thread_id="thread-a")

        bond = session.bond_view()
        self.assertEqual(bond["relationship_state"]["stage"], "trusted")
        self.assertAlmostEqual(float(bond["relationship_state"]["trust_score"]), 0.87, places=3)
        self.assertIn("稳定信赖", bond["relationship_state"]["notes"])
        self.assertEqual(bond["relationship_timeline"][0]["summary"], "关系变近")

    def test_evolution_summary_and_bond_view_share_relationship_resolution_rule(self):
        values = {
            "relationship": {
                "stage": "trusted",
                "affinity_score": 0.81,
                "trust_score": 0.85,
                "notes": "这一轮里已经明显进入稳定信赖。",
            },
            "bond_state": {"trust": 0.82, "closeness": 0.79},
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        memory_store = FakeMemoryStore()
        memory_store._relationship = {
            "stage": "friend",
            "affinity_score": 0.0,
            "trust_score": 0.0,
            "notes": "",
        }
        session = BackendSession(graph=graph, memory_store=memory_store, thread_id="thread-a")

        summary = session.build_evolution_summary()
        worldline = session.worldline_view()
        persona = session.persona_view()
        bond = session.bond_view()

        for relationship_state in (
            summary["relationship"],
            worldline["worldline_summary"]["relationship"],
            persona["evolution_summary"]["relationship"],
            bond["relationship_state"],
        ):
            self.assertEqual(relationship_state["stage"], "trusted")
            self.assertAlmostEqual(float(relationship_state["affinity_score"]), 0.81, places=3)
            self.assertAlmostEqual(float(relationship_state["trust_score"]), 0.85, places=3)
            self.assertIn("稳定信赖", relationship_state["notes"])

    def test_build_evolution_summary_surfaces_resolved_digital_body(self):
        values = {
            "current_event": {
                "kind": "user_utterance",
                "perception": {"channel": "dialogue", "modality": "text"},
            },
            "digital_body_state": {
                "active_surface": "tooling",
                "available_toolsets": ["browser"],
                "active_tools": ["search_web"],
                "access_state": {
                    "mode": "tool_enabled",
                    "browser_session": "present",
                    "account_state": "logged_in",
                    "cookie_state": "present",
                    "api_key_state": "present",
                    "quota_state": "sufficient",
                    "session_state": {
                        "continuity": "stable",
                        "browser_session": "present",
                    },
                    "account_state_detail": {
                        "login_state": "logged_in",
                        "cookie_state": "present",
                        "api_key_state": "present",
                    },
                    "quota_state_detail": {
                        "provider_state": "sufficient",
                        "available": True,
                    },
                    "permission_state": {
                        "approval_state": "open",
                        "pending_approval_count": 0,
                    },
                    "sandbox_state": {
                        "availability": "restricted",
                        "execution_policy": "approval_required",
                    },
                },
                "resource_state": {
                    "action_packet_count": 1,
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "source_ref",
                    "active_artifact_ref": "src:17",
                    "active_artifact_label": "Persistence",
                    "artifact_reacquisition_mode": "reuse_saved_source",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [17],
                    "preferred_source_ref_id": 17,
                    "preferred_anchor_reason": "primary_more_current",
                    "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "artifact_source_query": "langgraph persistence checkpointer thread",
                    "artifact_source_title": "Persistence",
                    "artifact_source_tool_name": "search_web",
                }
            },
            "action_packets": [
                {
                    "proposal_id": "ap-1",
                    "tool_name": "search_web",
                    "status": "queued",
                    "risk": "read",
                    "requires_approval": False,
                }
            ],
            "toolset_unlocks": {"browser": 1},
            "reconsolidation_snapshot": {
                "digital_body_consequence": {
                    "kind": "access_request_pending",
                    "summary": "这轮留下的是一个待审批入口。",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [17],
                    "preferred_source_ref_id": 17,
                    "preferred_anchor_reason": "primary_more_current",
                    "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "artifact_source_query": "langgraph persistence checkpointer thread",
                    "artifact_source_title": "Persistence",
                    "artifact_source_tool_name": "search_web",
                    "requested_help": True,
                }
            },
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        summary = session.build_evolution_summary()
        digital_body = summary.get("digital_body") if isinstance(summary.get("digital_body"), dict) else {}
        self.assertEqual(digital_body.get("active_surface"), "tooling")
        self.assertEqual(digital_body.get("available_toolsets"), ["browser"])
        self.assertEqual(digital_body.get("active_tools"), ["search_web"])
        self.assertEqual(digital_body.get("access", {}).get("mode"), "tool_enabled")
        self.assertEqual(digital_body.get("access", {}).get("session_state", {}).get("continuity"), "stable")
        self.assertEqual(digital_body.get("access", {}).get("account_state_detail", {}).get("login_state"), "logged_in")
        self.assertEqual(digital_body.get("access", {}).get("quota_state_detail", {}).get("provider_state"), "sufficient")
        self.assertEqual(digital_body.get("access", {}).get("permission_state", {}).get("approval_state"), "open")
        self.assertEqual(digital_body.get("access", {}).get("sandbox_state", {}).get("execution_policy"), "approval_required")
        self.assertEqual(digital_body.get("resources", {}).get("action_packet_count"), 1)
        self.assertEqual(digital_body.get("resources", {}).get("artifact_carrier"), "source_ref")
        self.assertEqual(digital_body.get("resources", {}).get("artifact_source_ref_ids"), [17])
        self.assertEqual(digital_body.get("resources", {}).get("preferred_source_ref_id"), 17)
        self.assertEqual(digital_body.get("resources", {}).get("preferred_anchor_reason"), "primary_more_current")
        self.assertEqual(
            digital_body.get("resources", {}).get("artifact_source_title"),
            "Persistence",
        )
        summary_consequence = (
            summary.get("digital_body_consequence")
            if isinstance(summary.get("digital_body_consequence"), dict)
            else {}
        )
        self.assertEqual(summary_consequence.get("kind"), "access_request_pending")
        self.assertEqual(summary_consequence.get("artifact_carrier"), "source_ref")
        self.assertEqual(summary_consequence.get("artifact_source_ref_ids"), [17])
        self.assertEqual(summary_consequence.get("preferred_source_ref_id"), 17)
        self.assertEqual(summary_consequence.get("preferred_anchor_reason"), "primary_more_current")
        self.assertEqual(summary_consequence.get("artifact_source_title"), "Persistence")
        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        self.assertEqual(current_turn.get("digital_body_surface"), "tooling")
        self.assertEqual(current_turn.get("digital_body_access_mode"), "tool_enabled")
        self.assertEqual(current_turn.get("digital_body_consequence_kind"), "access_request_pending")
        self.assertEqual(current_turn.get("digital_body_consequence_summary"), "这轮留下的是一个待审批入口。")
        event_residue = summary.get("event_residue") if isinstance(summary.get("event_residue"), dict) else {}
        event_bodyfx = (
            event_residue.get("digital_body_consequence")
            if isinstance(event_residue.get("digital_body_consequence"), dict)
            else {}
        )
        self.assertEqual(event_bodyfx.get("kind"), "access_request_pending")
        self.assertEqual(event_bodyfx.get("artifact_carrier"), "source_ref")
        self.assertEqual(event_bodyfx.get("artifact_source_ref_ids"), [17])
        self.assertEqual(event_bodyfx.get("preferred_source_ref_id"), 17)
        self.assertEqual(event_bodyfx.get("preferred_anchor_reason"), "primary_more_current")
        self.assertEqual(event_bodyfx.get("artifact_source_title"), "Persistence")
        self.assertTrue(bool(event_bodyfx.get("requested_help")))
        self.assertIn("source=Persistence", event_residue.get("preview_line") or "")
        self.assertIn("bodyfx=access_request_pending", event_residue.get("preview_line") or "")

        persona = session.persona_view()
        digital_body_consequence = (
            persona.get("digital_body_consequence")
            if isinstance(persona.get("digital_body_consequence"), dict)
            else {}
        )
        self.assertEqual(digital_body_consequence.get("kind"), "access_request_pending")
        self.assertTrue(bool(digital_body_consequence.get("requested_help")))

    def test_build_evolution_summary_surfaces_procedural_growth_hint(self):
        values = {
            "digital_body_state": {
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
                        "execution_policy": "approval_required",
                        "runner_kind": "docker_isolated_runner",
                        "isolation_level": "docker_local_isolated",
                        "image_ref": "amadeus-thread0/sandbox-phase2:py312",
                        "network_policy": "none",
                        "workspace_root_kind": "attached_repo_root",
                    },
                },
                "resource_state": {
                    "completed_packet_count": 1,
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "workspace",
                    "active_artifact_ref": "E:/repo/amadeus-thread0",
                    "active_artifact_label": "amadeus-thread0",
                    "artifact_carrier": "filesystem",
                    "workspace_root": "E:/repo/amadeus-thread0",
                },
            },
            "action_packets": [
                {
                    "proposal_id": "ap-procedural-session",
                    "origin": "motive_goal",
                    "intent": "sandbox:execute_workspace_command",
                    "status": "completed",
                    "risk": "external_mutation",
                    "requires_approval": True,
                    "tool_name": "execute_workspace_command",
                    "result_summary": "pytest passed",
                    "execution_spec": {
                        "executor": "pytest",
                        "profile": "pytest",
                        "runner_kind": "docker_isolated_runner",
                        "isolation_level": "docker_local_isolated",
                        "image_ref": "amadeus-thread0/sandbox-phase2:py312",
                        "network_policy": "none",
                        "workspace_root_kind": "attached_repo_root",
                        "argv": ["pytest", "-q", "tests/test_demo.py"],
                        "cwd": "E:/repo/amadeus-thread0",
                        "allowed_roots": ["E:/repo/amadeus-thread0"],
                    },
                    "execution_result": {
                        "run_id": "run-procedural-session",
                        "status": "completed",
                        "exit_code": 0,
                        "stdout_log_ref": "E:/repo/.amadeus/sandbox-runs/run-procedural-session/stdout.txt",
                    },
                }
            ],
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        summary = session.build_evolution_summary()

        procedural = summary.get("procedural_growth") if isinstance(summary.get("procedural_growth"), dict) else {}
        self.assertTrue(procedural.get("procedural_growth"))
        self.assertEqual(procedural.get("traces", [])[0]["trace_kind"], "sandbox_execution_pattern")
        self.assertEqual(procedural.get("procedural_hint", {}).get("source_run_id"), "run-procedural-session")
        self.assertTrue(procedural.get("procedural_hint", {}).get("must_request_approval"))
        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        self.assertTrue(current_turn.get("digital_body_procedural_growth"))
        self.assertEqual(current_turn.get("procedural_hint", {}).get("source_run_id"), "run-procedural-session")

    def test_build_evolution_summary_surfaces_procedural_planning_bias(self):
        values = {
            "autonomy_intent": {
                "mode": "approval_pending",
                "origin": "counterpart_request",
                "requires_approval": True,
                "primary_proposal_id": "ap-phase2-session",
            },
            "procedural_planning": {
                "planning_bias": True,
                "bias_kind": "sandbox_execute",
                "trace_id": "proc_phase2_session",
                "trace_kind": "sandbox_execution_pattern",
                "source_run_id": "run-phase2-session",
                "source_tool_name": "execute_workspace_command",
                "suggested_capability_family": "sandbox",
                "suggested_pattern": "pytest",
                "suggested_executor": "pytest",
                "suggested_argv": ["pytest"],
                "must_request_approval": True,
                "requires_approval": True,
                "capability_claim": True,
                "confidence": 0.79,
            },
            "action_trace": [
                {
                    "proposal_id": "ap-phase2-session",
                    "event": "derived_from_procedural_planning",
                    "status": "awaiting_approval",
                    "procedural_planning": {
                        "planning_bias": True,
                        "bias_kind": "sandbox_execute",
                        "trace_id": "proc_phase2_session",
                        "trace_kind": "sandbox_execution_pattern",
                        "source_run_id": "run-phase2-session",
                        "source_tool_name": "execute_workspace_command",
                        "suggested_capability_family": "sandbox",
                        "suggested_pattern": "pytest",
                        "suggested_executor": "pytest",
                        "suggested_argv": ["pytest"],
                        "must_request_approval": True,
                        "requires_approval": True,
                        "capability_claim": True,
                        "confidence": 0.79,
                    },
                }
            ],
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        summary = session.build_evolution_summary()

        planning = summary.get("autonomy", {}).get("procedural_planning", {})
        current_turn = summary.get("current_turn", {})
        self.assertEqual(planning.get("bias_kind"), "sandbox_execute")
        self.assertEqual(planning.get("source_run_id"), "run-phase2-session")
        self.assertEqual(current_turn.get("procedural_planning", {}).get("trace_id"), "proc_phase2_session")

    def test_build_evolution_summary_surfaces_procedural_outcome(self):
        values = {
            "action_packets": [
                {
                    "proposal_id": "ap-phase3-session",
                    "origin": "motive_goal",
                    "intent": "sandbox:execute_workspace_command",
                    "status": "completed",
                    "risk": "external_mutation",
                    "requires_approval": True,
                    "tool_name": "execute_workspace_command",
                    "result_summary": "pytest passed",
                    "tool_args": {
                        "procedural_planning": {
                            "planning_bias": True,
                            "bias_kind": "sandbox_execute",
                            "trace_id": "proc_phase3_session",
                            "trace_kind": "sandbox_execution_pattern",
                            "source_run_id": "run-phase3-prior",
                            "source_tool_name": "execute_workspace_command",
                            "suggested_capability_family": "sandbox",
                            "suggested_pattern": "pytest",
                            "suggested_executor": "pytest",
                            "suggested_argv": ["pytest"],
                            "must_request_approval": True,
                            "requires_approval": True,
                            "capability_claim": True,
                            "confidence": 0.7,
                        }
                    },
                    "execution_spec": {
                        "executor": "pytest",
                        "profile": "pytest",
                        "argv": ["pytest"],
                        "cwd": "E:/repo/amadeus-thread0",
                        "allowed_roots": ["E:/repo/amadeus-thread0"],
                    },
                    "execution_result": {
                        "run_id": "run-phase3-session",
                        "status": "completed",
                        "exit_code": 0,
                        "stdout_log_ref": "E:/repo/.amadeus/sandbox-runs/run-phase3-session/stdout.txt",
                    },
                }
            ],
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        summary = session.build_evolution_summary()

        outcome = summary.get("procedural_outcome") if isinstance(summary.get("procedural_outcome"), dict) else {}
        current_turn = summary.get("current_turn", {})
        self.assertTrue(outcome.get("procedural_outcome"))
        self.assertEqual(outcome.get("last_outcome_kind"), "confirmed_success")
        self.assertEqual(current_turn.get("procedural_outcome", {}).get("source_run_id"), "run-phase3-session")
        self.assertEqual(current_turn.get("procedural_outcome", {}).get("outcome_kind"), "confirmed_success")

    def test_build_evolution_summary_surfaces_procedural_recovery(self):
        values = {
            "action_packets": [
                {
                    "proposal_id": "ap-phase4-session",
                    "origin": "motive_goal",
                    "intent": "sandbox:execute_workspace_command",
                    "status": "completed",
                    "risk": "external_mutation",
                    "requires_approval": True,
                    "tool_name": "execute_workspace_command",
                    "result_summary": "pytest failed",
                    "tool_args": {
                        "procedural_planning": {
                            "planning_bias": True,
                            "bias_kind": "sandbox_execute",
                            "trace_id": "proc_phase4_session",
                            "trace_kind": "sandbox_execution_pattern",
                            "source_run_id": "run-phase4-prior",
                            "source_tool_name": "execute_workspace_command",
                            "suggested_capability_family": "sandbox",
                            "suggested_pattern": "pytest",
                            "suggested_executor": "pytest",
                            "suggested_argv": ["pytest"],
                            "must_request_approval": True,
                            "requires_approval": True,
                            "capability_claim": True,
                            "confidence": 0.7,
                        }
                    },
                    "execution_spec": {
                        "executor": "pytest",
                        "profile": "pytest",
                        "argv": ["pytest"],
                        "cwd": "E:/repo/amadeus-thread0",
                        "allowed_roots": ["E:/repo/amadeus-thread0"],
                    },
                    "execution_result": {
                        "run_id": "run-phase4-session",
                        "status": "failed",
                        "exit_code": 2,
                        "stderr_log_ref": "E:/repo/.amadeus/sandbox-runs/run-phase4-session/stderr.txt",
                        "error_summary": "process exited with code 2",
                    },
                }
            ],
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        summary = session.build_evolution_summary()

        recovery = summary.get("procedural_recovery") if isinstance(summary.get("procedural_recovery"), dict) else {}
        current_turn = summary.get("current_turn", {})
        self.assertTrue(recovery.get("procedural_recovery"))
        self.assertEqual(recovery.get("last_recovery_kind"), "inspect_failure_artifact")
        self.assertEqual(current_turn.get("procedural_recovery", {}).get("source_run_id"), "run-phase4-session")
        self.assertEqual(
            current_turn.get("procedural_recovery", {}).get("recovery_kind"),
            "inspect_failure_artifact",
        )

    def test_build_evolution_summary_surfaces_tts_presence_timing(self):
        values = {
            "current_event": {
                "kind": "tts_presence_timing_observation",
                "source": "tts",
                "created_at": 1710000211,
                "perception": {
                    "channel": "voice",
                    "modality": "TTS_presence_timing",
                    "source_role": "runtime",
                    "trust_tier": "high_runtime_telemetry",
                    "delivery_mode": "spoken",
                },
            },
            "digital_body_state": {
                "active_surface": "voice",
                "perception_channels": ["voice", "TTS_presence_timing"],
                "action_channels": ["language", "voice"],
                "world_surfaces": ["tts"],
                "access_state": {
                    "mode": "native_only",
                    "tts_presence_state": {
                        "availability": "available",
                        "enabled": True,
                        "backend": "dashscope_realtime",
                        "voice_profile_id": "default",
                        "queue_state": "idle",
                        "last_status": "delivered",
                        "last_run_id": "evt_tts_20260505_0001",
                    },
                },
                "resource_state": {
                    "tts_presence_timing": {
                        "last_event_id": "evt_tts_20260505_0001",
                        "last_delivery_mode": "spoken",
                        "last_actual_start_delay_ms": 180,
                        "last_duration_ms": 3120,
                        "last_pause_profile": "direct",
                    }
                },
            },
            "reconsolidation_snapshot": {
                "digital_body_consequence": {
                    "kind": "tts_presence_delivered",
                    "summary": "TTS delivered the frozen final text.",
                    "tts_presence_timing": {
                        "delivery_mode": "spoken",
                        "actual_start_delay_ms": 180,
                        "duration_ms": 3120,
                        "pause_profile": "direct",
                    },
                }
            },
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        summary = session.build_evolution_summary()

        digital_body = summary.get("digital_body") if isinstance(summary.get("digital_body"), dict) else {}
        self.assertEqual(digital_body.get("access", {}).get("tts_presence_state", {}).get("last_status"), "delivered")
        self.assertEqual(digital_body.get("resources", {}).get("tts_presence_timing", {}).get("last_delivery_mode"), "spoken")
        digital_body_consequence = (
            summary.get("digital_body_consequence")
            if isinstance(summary.get("digital_body_consequence"), dict)
            else {}
        )
        self.assertEqual(digital_body_consequence.get("kind"), "tts_presence_delivered")
        self.assertEqual(digital_body_consequence.get("tts_presence_timing", {}).get("delivery_mode"), "spoken")
        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        self.assertEqual(current_turn.get("tts_presence_status"), "delivered")
        self.assertEqual(current_turn.get("tts_presence_delivery_mode"), "spoken")
        self.assertEqual(current_turn.get("tts_presence_duration_ms"), 3120)
        event_residue = summary.get("event_residue") if isinstance(summary.get("event_residue"), dict) else {}
        self.assertEqual(event_residue.get("modality"), "TTS_presence_timing")
        self.assertEqual(event_residue.get("digital_body_consequence", {}).get("tts_presence_timing", {}).get("duration_ms"), 3120)

    def test_build_evolution_summary_reuses_carried_embodied_context_for_digital_body(self):
        values = {
            "current_event": {
                "kind": "user_utterance",
                "perception": {"channel": "dialogue", "modality": "text"},
            },
            "interaction_carryover": {
                "source": "reconsolidation",
                "carryover_mode": "own_rhythm",
                "strength": 0.53,
                "embodied_context": {
                    "kind": "access_request_pending",
                    "summary": "她把动作推进到了审批门口。",
                    "requested_access": ["workspace_write"],
                    "missing_access": ["workspace_write"],
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [17],
                    "preferred_source_ref_id": 17,
                    "preferred_anchor_reason": "primary_more_current",
                    "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "artifact_source_query": "langgraph persistence checkpointer thread",
                    "artifact_source_title": "Persistence",
                    "artifact_source_tool_name": "search_web",
                    "requested_help": True,
                    "primary_status": "awaiting_approval",
                },
            },
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        summary = session.build_evolution_summary()
        digital_body = summary.get("digital_body") if isinstance(summary.get("digital_body"), dict) else {}
        self.assertEqual(digital_body.get("active_surface"), "approval_gate")
        self.assertEqual(digital_body.get("access", {}).get("mode"), "approval_pending")
        self.assertIn("workspace_write", digital_body.get("access", {}).get("missing_access") or [])
        self.assertIn("human_approval", digital_body.get("access", {}).get("requestable_access") or [])
        self.assertEqual(digital_body.get("resources", {}).get("artifact_carrier"), "source_ref")
        self.assertEqual(digital_body.get("resources", {}).get("artifact_source_ref_ids"), [17])
        self.assertEqual(digital_body.get("resources", {}).get("preferred_source_ref_id"), 17)
        self.assertEqual(digital_body.get("resources", {}).get("preferred_anchor_reason"), "primary_more_current")
        self.assertEqual(digital_body.get("resources", {}).get("artifact_source_title"), "Persistence")

    def test_build_evolution_summary_surfaces_digital_body_cooldown(self):
        values = {
            "current_event": {
                "kind": "user_utterance",
                "perception": {"channel": "dialogue", "modality": "text"},
            },
            "session_context": {
                "thread_id": "thread-a",
                "digital_body_hints": {
                    "quota_state": "exhausted",
                    "retry_after_s": 300,
                    "cooldown_scope": "provider",
                },
            },
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        summary = session.build_evolution_summary()
        digital_body = summary.get("digital_body") if isinstance(summary.get("digital_body"), dict) else {}
        self.assertEqual(digital_body.get("active_surface"), "cooldown_gate")
        self.assertEqual(digital_body.get("access", {}).get("mode"), "cooldown")
        self.assertEqual(digital_body.get("access", {}).get("retry_after_s"), 300)
        self.assertEqual(digital_body.get("access", {}).get("cooldown_scope"), "provider")
        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        self.assertEqual(current_turn.get("digital_body_retry_after_s"), 300)
        self.assertEqual(current_turn.get("digital_body_cooldown_scope"), "provider")

    def test_build_evolution_summary_surfaces_digital_body_session_lifecycle(self):
        values = {
            "current_event": {
                "kind": "user_utterance",
                "perception": {"channel": "dialogue", "modality": "text"},
            },
            "session_context": {
                "thread_id": "thread-a",
                "digital_body_hints": {
                    "browser_session": "present",
                    "account_state": "logged_in",
                    "cookie_state": "present",
                    "session_expires_in_s": 600,
                },
            },
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        summary = session.build_evolution_summary()
        digital_body = summary.get("digital_body") if isinstance(summary.get("digital_body"), dict) else {}
        self.assertEqual(digital_body.get("access", {}).get("session_continuity"), "expiring")
        self.assertEqual(digital_body.get("access", {}).get("session_expires_in_s"), 600)
        self.assertEqual(digital_body.get("access", {}).get("session_recovery_mode"), "refresh_session")
        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        self.assertEqual(current_turn.get("digital_body_session_continuity"), "expiring")
        self.assertEqual(current_turn.get("digital_body_session_expires_in_s"), 600)
        self.assertEqual(current_turn.get("digital_body_session_recovery_mode"), "refresh_session")

    def test_backend_session_surfaces_filesystem_digital_body_consequence_kinds(self):
        base_event = {
            "kind": "user_utterance",
            "perception": {"channel": "dialogue", "modality": "text"},
        }
        cases = [
            {
                "name": "workspace_access_resolved",
                "values": {
                    "current_event": dict(base_event),
                    "digital_body_state": {
                        "active_surface": "tooling",
                        "perception_channels": ["dialogue", "filesystem"],
                        "action_channels": ["language", "structured_action", "tooling"],
                        "world_surfaces": ["filesystem"],
                        "access_state": {
                            "mode": "tool_enabled",
                            "filesystem_state": "writable",
                        },
                        "resource_state": {
                            "artifact_continuity": "attached",
                            "active_artifact_kind": "workspace",
                            "active_artifact_ref": "E:/runtime/workspaces/lab-notes",
                            "active_artifact_label": "lab-notes",
                            "workspace_root": "E:/runtime/workspaces/lab-notes",
                        },
                    },
                    "reconsolidation_snapshot": {
                        "digital_body_consequence": {
                            "kind": "workspace_access_resolved",
                            "summary": "可写工作区 lab-notes 已经真的创建好并接入当前上下文，后面的落盘动作现在可以继续。",
                            "active_surface": "tooling",
                            "access_mode": "tool_enabled",
                            "world_surfaces": ["filesystem"],
                            "artifact_continuity": "attached",
                            "active_artifact_kind": "workspace",
                            "active_artifact_ref": "E:/runtime/workspaces/lab-notes",
                            "active_artifact_label": "lab-notes",
                            "primary_status": "completed",
                            "primary_intent": "access:request_help",
                            "primary_tool_name": "create_workspace_access",
                        }
                    },
                },
                "expect": {
                    "kind": "workspace_access_resolved",
                    "primary_tool_name": "create_workspace_access",
                    "active_artifact_kind": "workspace",
                    "active_artifact_label": "lab-notes",
                    "workspace_root": "E:/runtime/workspaces/lab-notes",
                },
            },
            {
                "name": "workspace_file_updated",
                "values": {
                    "current_event": dict(base_event),
                    "digital_body_state": {
                        "active_surface": "tooling",
                        "perception_channels": ["dialogue", "filesystem"],
                        "action_channels": ["language", "structured_action", "tooling"],
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
                            "workspace_root": "E:/runtime/workspaces/lab-notes",
                        },
                    },
                    "action_packets": [
                        {
                            "proposal_id": "ap-file-append-1",
                            "origin": "counterpart_request",
                            "intent": "artifact:append_file",
                            "status": "completed",
                            "risk": "external_mutation",
                            "requires_approval": True,
                            "tool_name": "append_workspace_file",
                            "result_summary": "已把内容续写进 today.md，这条文件工作面现在接上了。",
                            "writeback_ready": True,
                            "artifact_context": {
                                "carrier": "filesystem",
                                "artifact_kind": "file",
                                "artifact_ref": "E:/runtime/workspaces/lab-notes/notes/today.md",
                                "artifact_label": "today.md",
                                "workspace_root": "E:/runtime/workspaces/lab-notes",
                                "reacquisition_mode": "reopen_file",
                                "exists": True,
                            },
                        }
                    ],
                },
                "expect": {
                    "kind": "workspace_file_updated",
                    "primary_tool_name": "append_workspace_file",
                    "active_artifact_kind": "file",
                    "active_artifact_label": "today.md",
                    "workspace_root": "E:/runtime/workspaces/lab-notes",
                    "artifact_mutation_mode": "append",
                    "procedural_growth": True,
                },
            },
            {
                "name": "workspace_path_inspected",
                "values": {
                    "current_event": dict(base_event),
                    "digital_body_state": {
                        "active_surface": "tooling",
                        "perception_channels": ["dialogue", "filesystem"],
                        "action_channels": ["language", "structured_action", "tooling"],
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
                            "workspace_root": "E:/runtime/workspaces/lab-notes",
                        },
                    },
                    "action_packets": [
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
                                "workspace_root": "E:/runtime/workspaces/lab-notes",
                                "reacquisition_mode": "reopen_file",
                                "exists": True,
                            },
                        }
                    ],
                },
                "expect": {
                    "kind": "workspace_path_inspected",
                    "primary_tool_name": "inspect_workspace_path",
                    "active_artifact_kind": "file",
                    "active_artifact_label": "today.md",
                    "workspace_root": "E:/runtime/workspaces/lab-notes",
                    "procedural_growth": False,
                },
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                self._assert_backend_session_consequence_surface(
                    values=case["values"],
                    expect=case["expect"],
                )

    def test_backend_session_surfaces_source_material_and_access_consequence_kinds(self):
        base_event = {
            "kind": "user_utterance",
            "perception": {"channel": "dialogue", "modality": "text"},
        }
        cases = [
            {
                "name": "artifact_reacquired",
                "values": {
                    "current_event": dict(base_event),
                    "digital_body_state": {
                        "active_surface": "tooling",
                        "perception_channels": ["dialogue", "browser"],
                        "action_channels": ["language", "structured_action", "tooling"],
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
                    "action_packets": [
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
                },
                "expect": {
                    "kind": "artifact_reacquired",
                    "primary_tool_name": "reacquire_artifact",
                    "active_artifact_kind": "search_result",
                    "active_artifact_label": "Persistence",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [17],
                    "artifact_source_tool_name": "search_web",
                    "procedural_growth": False,
                },
            },
            {
                "name": "source_material_inspected",
                "values": {
                    "current_event": dict(base_event),
                    "digital_body_state": {
                        "active_surface": "tooling",
                        "perception_channels": ["dialogue", "browser"],
                        "action_channels": ["language", "structured_action", "tooling"],
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
                    "action_packets": [
                        {
                            "proposal_id": "ap-inspect-source-1",
                            "origin": "counterpart_request",
                            "intent": "artifact:inspect_source_ref",
                            "status": "completed",
                            "risk": "read",
                            "requires_approval": False,
                            "tool_name": "inspect_source_ref",
                            "result_summary": "已查看外部材料 Persistence，当前内容已经接回视野。",
                            "writeback_ready": True,
                            "artifact_context": {
                                "carrier": "source_ref",
                                "artifact_kind": "search_result",
                                "artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                                "artifact_label": "Persistence",
                                "reacquisition_mode": "inspect_source_ref",
                                "source_ref_ids": [17],
                                "source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                                "source_query": "langgraph persistence checkpointer thread",
                                "source_title": "Persistence",
                                "source_tool_name": "search_web",
                            },
                        }
                    ],
                },
                "expect": {
                    "kind": "source_material_inspected",
                    "primary_tool_name": "inspect_source_ref",
                    "active_artifact_kind": "search_result",
                    "active_artifact_label": "Persistence",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [17],
                    "artifact_source_tool_name": "search_web",
                    "procedural_growth": False,
                },
            },
            {
                "name": "source_material_compared",
                "values": {
                    "current_event": dict(base_event),
                    "digital_body_state": {
                        "active_surface": "tooling",
                        "perception_channels": ["dialogue", "browser"],
                        "action_channels": ["language", "structured_action", "tooling"],
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
                            "active_artifact_label": "Persistence v2",
                            "artifact_carrier": "source_ref",
                            "artifact_source_ref_ids": [21, 17],
                            "preferred_source_ref_id": 21,
                            "preferred_anchor_reason": "primary_more_current",
                            "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                            "artifact_source_query": "langgraph persistence checkpointer thread recovery",
                            "artifact_source_title": "Persistence v2",
                            "artifact_source_tool_name": "search_web",
                        },
                    },
                    "action_packets": [
                        {
                            "proposal_id": "ap-compare-source-1",
                            "origin": "counterpart_request",
                            "intent": "artifact:compare_source_refs",
                            "status": "completed",
                            "risk": "read",
                            "requires_approval": False,
                            "tool_name": "compare_source_refs",
                            "result_summary": "已把 Persistence v2 和 Persistence 对照过一遍，两条材料是紧邻的延续，当前判断会优先沿着这条相连线索继续。",
                            "writeback_ready": True,
                            "artifact_context": {
                                "carrier": "source_ref",
                                "artifact_kind": "search_result",
                                "artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                                "artifact_label": "Persistence v2",
                                "reacquisition_mode": "compare_source_refs",
                                "source_ref_ids": [21, 17],
                                "preferred_source_ref_id": 21,
                                "preferred_anchor_reason": "primary_more_current",
                                "source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                                "source_query": "langgraph persistence checkpointer thread recovery",
                                "source_title": "Persistence v2",
                                "source_tool_name": "search_web",
                            },
                        }
                    ],
                },
                "expect": {
                    "kind": "source_material_compared",
                    "primary_tool_name": "compare_source_refs",
                    "active_artifact_kind": "search_result",
                    "active_artifact_label": "Persistence v2",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [21, 17],
                    "artifact_source_tool_name": "search_web",
                    "preferred_source_ref_id": 21,
                    "preferred_anchor_reason": "primary_more_current",
                    "procedural_growth": False,
                },
            },
            {
                "name": "access_state_refreshed",
                "values": {
                    "current_event": dict(base_event),
                    "digital_body_state": {
                        "active_surface": "tooling",
                        "perception_channels": ["dialogue", "runtime"],
                        "action_channels": ["language", "structured_action", "tooling"],
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
                    "action_packets": [
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
                },
                "expect": {
                    "kind": "access_state_refreshed",
                    "primary_tool_name": "refresh_access_state",
                    "session_continuity": "stable",
                    "procedural_growth": False,
                },
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                self._assert_backend_session_consequence_surface(
                    values=case["values"],
                    expect=case["expect"],
                )

    def test_checkpoint_and_behavior_queue_views_use_backend_session_surface(self):
        values = {
            "behavior_queue": [{"agenda_id": "b1", "kind": "checkin", "status": "pending"}],
        }
        history_rows = [
            FakeState({}, config={"configurable": {"checkpoint_id": "cp-3"}}, next_items=["call_model"]),
            FakeState({}, config={"configurable": {"checkpoint_id": "cp-2"}}, next_items=["tool_gate"]),
        ]
        graph = FakeStreamGraph(
            stream_rows=[],
            state_values=values,
            state_config={"configurable": {"checkpoint_id": "cp-9"}},
            history_rows=history_rows,
        )
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        current = session.current_checkpoint_view()
        self.assertEqual(current["thread_id"], "thread-a")
        self.assertEqual(current["checkpoint_id"], "cp-9")

        history = session.checkpoint_history_view(limit=1)
        self.assertEqual(history["total"], 2)
        self.assertEqual(history["rows"][0]["checkpoint_id"], "cp-3")
        self.assertEqual(history["rows"][0]["next"], ["call_model"])

        queue = session.behavior_queue_view()
        self.assertEqual(queue["behavior_queue"][0]["agenda_id"], "b1")
        self.assertEqual(queue["behavior_queue_summary"][0]["agenda_id"], "b1")

    def test_operator_readback_view_surfaces_runtime_productization(self):
        values = {
            "autonomy_intent": {"mode": "assist"},
            "action_packets": [
                {
                    "proposal_id": "ap-operator-readback",
                    "intent": "browser:manual_takeover",
                    "status": "blocked",
                    "risk": "external_mutation",
                    "requires_approval": True,
                }
            ],
            "digital_body_consequence": {"kind": "browser_takeover_requested"},
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        readback = session.operator_readback_view()

        self.assertEqual(readback["readiness_status"], "runtime_productization_phase1_ready")
        self.assertEqual(readback["operator_snapshot"]["autonomy_mode"], "assist")
        self.assertEqual(readback["operator_snapshot"]["action_packet_count"], 1)
        self.assertEqual(readback["operator_snapshot"]["digital_body_consequence_kind"], "browser_takeover_requested")

    def test_checkpoint_scoped_views_preserve_checkpoint_config_during_readback(self):
        values = {
            "behavior_queue": [{"agenda_id": "latest", "kind": "checkin", "status": "pending"}],
        }
        history_rows = [
            FakeState({}, config={"configurable": {"checkpoint_id": "cp-old"}}, next_items=["call_model"]),
            FakeState({}, config={"configurable": {"checkpoint_id": "cp-new"}}, next_items=["tool_gate"]),
        ]
        graph = FakeStreamGraph(
            stream_rows=[],
            state_values=values,
            state_config={"configurable": {"checkpoint_id": "cp-new"}},
            history_rows=history_rows,
            state_values_by_checkpoint={
                "cp-old": {
                    "behavior_queue": [{"agenda_id": "older", "kind": "checkin", "status": "pending"}],
                }
            },
        )
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a", user_id="okabe")
        scoped_config = session.config(checkpoint_id="cp-old")

        queue = session.behavior_queue_view(config=scoped_config)
        current = session.current_checkpoint_view(config=scoped_config)
        history = session.checkpoint_history_view(limit=1, config=scoped_config)

        self.assertEqual(queue["behavior_queue"][0]["agenda_id"], "older")
        self.assertEqual(current["checkpoint_id"], "cp-old")
        self.assertEqual(history["rows"][0]["checkpoint_id"], "cp-old")
        self.assertEqual(graph.get_state_calls[-1]["configurable"]["checkpoint_id"], "cp-old")
        self.assertEqual(graph.get_state_calls[-1]["configurable"]["user_id"], "okabe")
        self.assertEqual(graph.get_state_history_calls[0]["configurable"]["checkpoint_id"], "cp-old")

    def test_session_views_prefer_nonempty_behavior_agenda_when_behavior_queue_is_empty(self):
        values = {
            "behavior_queue": [],
            "behavior_agenda": [{"agenda_id": "legacy-a1", "kind": "deferred_checkin", "status": "pending"}],
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        worldline = session.worldline_view()
        preview = worldline["worldline_summary"]["behavior_queue_preview"]
        self.assertEqual(preview[0]["agenda_id"], "legacy-a1")

        persona = session.persona_view()
        self.assertEqual(persona["behavior_queue"][0]["agenda_id"], "legacy-a1")
        self.assertEqual(persona["behavior_queue_summary"][0]["agenda_id"], "legacy-a1")

        queue = session.behavior_queue_view()
        self.assertEqual(queue["behavior_queue"][0]["agenda_id"], "legacy-a1")

    def test_session_views_preserve_behavior_queue_semantic_context_in_summary(self):
        values = {
            "behavior_queue": [
                {
                    "agenda_id": "queue-a1",
                    "kind": "deferred_checkin",
                    "target": "counterpart",
                    "status": "pending",
                    "trigger_family": "life_window",
                    "scheduled_after_min": 18,
                    "expires_after_min": 180,
                    "priority": 0.58,
                    "base_priority": 0.52,
                    "hold_count": 2,
                    "last_recheck_at_min": 6,
                    "allow_interrupt": False,
                    "primary_motive": "honor_continuity",
                    "motive_tension": "self_rhythm_vs_contact",
                    "goal_frame": "先把前面那点生活上的惦记轻轻接回来。",
                    "source_event_kind": "scheduled_life_due",
                    "created_at": 1710000018,
                    "carryover_mode": "small_opening",
                    "carryover_strength": 0.44,
                    "relationship_weather": "warm_residue",
                    "presence_residue": 0.38,
                    "ambient_resonance": 0.27,
                    "self_activity_momentum": 0.49,
                    "attention_target": "counterpart_state",
                    "nonverbal_signal": "quiet_glance",
                    "continuity_anchor": 0.61,
                    "own_rhythm_anchor": 0.72,
                    "recontact_anchor": 0.38,
                    "boundary_anchor": 0.27,
                    "memory_anchor": 0.33,
                    "semantic_continuity_depth": 0.68,
                    "semantic_identity_gravity": 0.64,
                    "lineage_gravity": 0.74,
                    "contact_lineage": 0.51,
                    "repair_lineage": 0.29,
                    "boundary_lineage": 0.36,
                    "selfhood_lineage": 0.63,
                    "agency_lineage": 0.77,
                    "long_term_axis_count": 4,
                    "note": "窗口先留着，等更自然的时候再推进",
                }
            ]
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        worldline = session.worldline_view()
        persona = session.persona_view()
        queue = session.behavior_queue_view()

        worldline_preview = worldline["worldline_summary"]["behavior_queue_preview"][0]
        self.assertFalse(worldline_preview["allow_interrupt"])
        self.assertEqual(worldline_preview["primary_motive"], "honor_continuity")
        self.assertEqual(worldline_preview["motive_tension"], "self_rhythm_vs_contact")
        self.assertEqual(worldline_preview["goal_frame"], "先把前面那点生活上的惦记轻轻接回来。")
        self.assertEqual(worldline_preview["source_event_kind"], "scheduled_life_due")
        self.assertEqual(worldline_preview["created_at"], 1710000018)
        self.assertEqual(worldline_preview["continuity_anchor"], 0.61)
        self.assertEqual(worldline_preview["semantic_continuity_depth"], 0.68)
        self.assertEqual(worldline_preview["semantic_identity_gravity"], 0.64)
        self.assertEqual(worldline_preview["lineage_gravity"], 0.74)
        self.assertEqual(worldline_preview["agency_lineage"], 0.77)
        self.assertEqual(worldline_preview["long_term_axis_count"], 4)

        persona_summary = persona["behavior_queue_summary"][0]
        self.assertEqual(persona_summary["source_event_kind"], "scheduled_life_due")
        self.assertEqual(persona_summary["goal_frame"], "先把前面那点生活上的惦记轻轻接回来。")
        self.assertEqual(persona_summary["memory_anchor"], 0.33)
        self.assertEqual(persona_summary["contact_lineage"], 0.51)

        queue_summary = queue["behavior_queue_summary"][0]
        self.assertFalse(queue_summary["allow_interrupt"])
        self.assertEqual(queue_summary["created_at"], 1710000018)
        self.assertEqual(queue_summary["repair_lineage"], 0.29)
        self.assertEqual(queue_summary["selfhood_lineage"], 0.63)

    def test_session_views_preserve_agenda_lifecycle_semantic_context_in_summary(self):
        values = {
            "agenda_lifecycle_residue": {
                "kind": "released_to_self_activity",
                "source_event_kind": "scheduled_life_due",
                "trigger_family": "life_window",
                "carryover_mode": "own_rhythm",
                "carryover_strength": 0.53,
                "relationship_weather": "warm_residue",
                "hold_count": 2,
                "idle_minutes": 18,
                "attention_target": "counterpart_state",
                "nonverbal_signal": "quiet_glance",
                "presence_residue": 0.33,
                "ambient_resonance": 0.24,
                "self_activity_momentum": 0.58,
                "continuity_anchor": 0.66,
                "own_rhythm_anchor": 0.72,
                "recontact_anchor": 0.34,
                "boundary_anchor": 0.22,
                "memory_anchor": 0.30,
                "semantic_continuity_depth": 0.68,
                "semantic_identity_gravity": 0.64,
                "lineage_gravity": 0.70,
                "contact_lineage": 0.44,
                "repair_lineage": 0.41,
                "boundary_lineage": 0.36,
                "selfhood_lineage": 0.69,
                "agency_lineage": 0.78,
                "long_term_axis_count": 4,
                "own_rhythm_bias": 0.61,
                "recontact_cooldown": 0.47,
                "counterpart_scene_bias": "busy_not_disrespectful",
                "counterpart_boundary_delta": -0.04,
                "created_at": 1710000099,
                "source_tags": ["user_busy", "agenda_lifecycle"],
                "note": "前面挂着的窗口没有继续往前推，注意力被自然收回到了自己的节奏里。",
            }
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        worldline = session.worldline_view()
        persona = session.persona_view()

        worldline_lifecycle = worldline["worldline_summary"]["agenda_lifecycle"]
        self.assertEqual(worldline_lifecycle["semantic_continuity_depth"], 0.68)
        self.assertEqual(worldline_lifecycle["semantic_identity_gravity"], 0.64)
        self.assertEqual(worldline_lifecycle["created_at"], 1710000099)
        self.assertEqual(worldline_lifecycle["repair_lineage"], 0.41)
        self.assertEqual(worldline_lifecycle["selfhood_lineage"], 0.69)

        persona_lifecycle = persona["evolution_summary"]["agenda_lifecycle"]
        self.assertEqual(persona_lifecycle["created_at"], 1710000099)
        self.assertEqual(persona_lifecycle["contact_lineage"], 0.44)
        self.assertEqual(persona_lifecycle["agency_lineage"], 0.78)

    def test_idle_helpers_and_emotion_label_use_backend_session_surface(self):
        values = {
            "emotion_state": {"label": "care"},
            "behavior_queue": [],
        }
        graph = FakeStreamGraph(stream_rows=[], state_values=values)
        session = BackendSession(graph=graph, memory_store=FakeMemoryStore(), thread_id="thread-a")

        self.assertEqual(session.emotion_label(default="neutral"), "care")

        with patch("amadeus_thread0.runtime.backend_session.build_implicit_idle_state_update") as mock_state_update:
            mock_state_update.return_value = {"idle_seed": True}
            updated = session.apply_implicit_idle_maturation(
                run_config=session.config(),
                last_conversation_touch_ts=100,
                trigger_minutes=5,
                now_ts=100 + 6 * 60,
            )
        self.assertTrue(updated)
        self.assertEqual(graph.updated_states[0][1], {"idle_seed": True})
        self.assertEqual(graph.updated_states[0][2], "prepare_turn")

        with patch("amadeus_thread0.runtime.backend_session.build_implicit_idle_event_override") as mock_event_override:
            mock_event_override.return_value = {"kind": "idle"}
            payload = session.build_idle_event_payload(
                run_config=session.config(),
                idle_minutes=30,
                note="quiet",
                created_at=123,
                extra_tags=["pulse"],
            )
        self.assertEqual(payload, {"event_override": {"kind": "idle"}})

    def test_backend_session_surfaces_completed_skill_usage_consequence(self):
        values = {
            "current_event": {"kind": "user_utterance", "text": "继续顺着刚才那条 skill 的资料线索走"},
            "session_skill_state": {
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
            },
            "digital_body_state": {
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
                    "artifact_source_tool_name": "search_web",
                },
            },
            "action_packets": [
                {
                    "proposal_id": "ap-skill-usage-1",
                    "origin": "motive_goal",
                    "intent": "tool:search_web",
                    "status": "completed",
                    "risk": "read",
                    "requires_approval": False,
                    "tool_name": "search_web",
                    "tool_args": {"query": "langgraph persistence checkpointer"},
                    "result_summary": "searched continuity materials",
                    "writeback_ready": True,
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
        }

        self._assert_backend_session_consequence_surface(
            values=values,
            expect={
                "kind": "skill_usage_completed",
                "primary_tool_name": "search_web",
                "active_artifact_kind": "search_result",
                "active_artifact_label": "LangGraph Persistence",
                "artifact_carrier": "source_ref",
                "artifact_source_ref_ids": [21, 17],
                "artifact_source_tool_name": "search_web",
                "preferred_source_ref_id": 21,
                "preferred_anchor_reason": "primary_more_current",
                "procedural_growth": False,
            },
        )

    def test_backend_session_surfaces_browser_matrix_consequence_families(self):
        base_event = {
            "kind": "user_utterance",
            "perception": {"channel": "dialogue", "modality": "text"},
        }

        def _case(*, name, tool_name, proposal_id, status, action_kind, kind, result_summary="", manual=False, block_reason="", download_path="", upload_source=""):
            return {
                "name": name,
                "values": {
                    "current_event": dict(base_event),
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
                                "context_status": "manual_takeover" if manual else "active",
                                "active_page_id": "page-1",
                                "active_tab_count": 1,
                                "downloads_dir": "E:/runtime/browser/downloads/thread-browser",
                                "last_action_status": "manual_takeover_required" if manual else status,
                                "last_run_id": proposal_id,
                                "manual_takeover_required": manual,
                                "runner_kind": "playwright_persistent_context",
                                "isolation_level": "persistent_profile_runtime",
                            },
                        },
                        "resource_state": {
                            "completed_packet_count": 1 if status == "completed" else 0,
                            "blocked_packet_count": 1 if status == "blocked" else 0,
                            "artifact_continuity": "attached",
                            "active_artifact_kind": "file" if download_path else "page",
                            "active_artifact_ref": download_path or "page:page-1",
                            "active_artifact_label": "payload.txt" if download_path else "Docs",
                            "artifact_carrier": "filesystem" if download_path else "browser_page",
                            "artifact_source_url": "https://example.com/docs",
                            "artifact_source_title": "Docs",
                            "artifact_source_tool_name": tool_name,
                            "workspace_root": "E:/runtime/workspaces/browser-smoke",
                            "browser_profile_id": "thread-browser",
                            "browser_tab_id": "tab-1",
                        },
                    },
                    "action_packets": [
                        {
                            "proposal_id": proposal_id,
                            "origin": "motive_goal",
                            "intent": f"browser:{tool_name.removeprefix('browser_')}",
                            "status": status,
                            "risk": "external_mutation",
                            "requires_approval": True,
                            "tool_name": tool_name,
                            "result_summary": result_summary,
                            "block_reason": block_reason,
                            "writeback_ready": status == "completed",
                            "browser_execution_spec": {
                                "operation": action_kind,
                                "profile_id": "thread-browser",
                                "page_ref": "page:page-1",
                                "target_ref": "e2",
                                "upload_source": upload_source,
                                "download_target": download_path,
                                "allowed_roots": ["E:/runtime/workspaces/browser-smoke"],
                                "browser_downloads_root": "E:/runtime/browser/downloads/thread-browser",
                                "timeout_s": 20,
                            },
                            "browser_execution_preview": {
                                "runner_kind": "playwright_persistent_context",
                                "isolation_level": "persistent_profile_runtime",
                                "operation": action_kind,
                                "profile_id": "thread-browser",
                                "page_ref": "page:page-1",
                                "page_url": "https://example.com/docs",
                                "page_title": "Docs",
                                "target_ref": "e2",
                                "target_label": "Approve action",
                                "download_target": download_path,
                                "upload_source": upload_source,
                                "allowed_roots": ["E:/runtime/workspaces/browser-smoke"],
                                "downloads_root": "E:/runtime/browser/downloads/thread-browser",
                                "timeout_s": 20,
                                "requires_manual_takeover": manual,
                            },
                            "browser_execution_result": {
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
                                "last_action_status": "manual_takeover_required" if manual else status,
                                "download_path": download_path,
                                "upload_source": upload_source,
                                "error_summary": block_reason,
                                "manual_takeover_required": manual,
                            },
                        }
                    ],
                },
                "expect": {
                    "kind": kind,
                    "primary_tool_name": tool_name,
                    "active_artifact_kind": "file" if download_path else "page",
                    "active_artifact_label": "payload.txt" if download_path else "Docs",
                    "artifact_carrier": "filesystem" if download_path else "browser_page",
                    "workspace_root": "E:/runtime/workspaces/browser-smoke",
                    "browser_run_id": proposal_id,
                    "browser_profile_id": "thread-browser",
                    "browser_page_id": "page-1",
                    "browser_tab_id": "tab-1",
                    "browser_url": "https://example.com/docs",
                    "browser_title": "Docs",
                    "browser_last_action_kind": action_kind,
                    "browser_last_exit_status": status,
                    "requested_help": manual,
                    "environmental_friction": bool(manual or status == "blocked"),
                    "procedural_growth": status == "completed",
                },
            }

        cases = [
            _case(
                name="browser_interaction_completed",
                tool_name="browser_click",
                proposal_id="ap-browser-click-session",
                status="completed",
                action_kind="click",
                kind="browser_interaction_completed",
                result_summary="clicked Docs button",
            ),
            _case(
                name="browser_download_completed",
                tool_name="browser_download_click",
                proposal_id="ap-browser-download-session",
                status="completed",
                action_kind="download_click",
                kind="browser_download_completed",
                result_summary="downloaded payload",
                download_path="E:/runtime/workspaces/browser-smoke/downloads/payload.txt",
            ),
            _case(
                name="browser_upload_completed",
                tool_name="browser_upload_file",
                proposal_id="ap-browser-upload-session",
                status="completed",
                action_kind="upload_file",
                kind="browser_upload_completed",
                result_summary="uploaded payload",
                upload_source="E:/runtime/workspaces/browser-smoke/payload.txt",
            ),
            _case(
                name="browser_takeover_requested",
                tool_name="browser_fill",
                proposal_id="ap-browser-takeover-session",
                status="blocked",
                action_kind="fill",
                kind="browser_takeover_requested",
                manual=True,
                block_reason="sensitive credential entry requires manual browser takeover",
            ),
            _case(
                name="browser_action_blocked",
                tool_name="browser_click",
                proposal_id="ap-browser-blocked-session",
                status="blocked",
                action_kind="click",
                kind="browser_action_blocked",
                block_reason="browser action timed out after 20s",
            ),
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                self._assert_backend_session_consequence_surface(
                    values=case["values"],
                    expect=case["expect"],
                )


if __name__ == "__main__":
    unittest.main()
