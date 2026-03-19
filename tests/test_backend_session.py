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
    def __init__(self, stream_rows, state_values, *, state_config=None, history_rows=None):
        self._stream_rows = list(stream_rows)
        self._state_values = dict(state_values)
        self._state_config = dict(state_config or {"configurable": {}})
        self._history_rows = list(history_rows or [])
        self.updated_states = []

    def stream(self, payload, config=None, stream_mode=None):
        for row in self._stream_rows:
            yield row

    def get_state(self, config=None):
        return FakeState(self._state_values, config=self._state_config)

    def get_state_history(self, config=None):
        return list(self._history_rows)

    def update_state(self, config, values, as_node=None):
        self.updated_states.append((config, values, as_node))


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
            "semantic_self_narratives": [{"id": 5, "text": "她保留自己的判断。"}],
            "revision_traces": [{"id": 6, "reason": "semantic_refresh"}],
        }
        self._timeline = [{"id": 7, "summary": "关系变近", "affinity_delta": 0.1, "trust_delta": 0.2}]
        self._repairs = [{"id": 8, "summary": "慢慢和好"}]
        self._sources = [{"id": 9, "tool_name": "web_search", "title": "paper", "url": "https://example.com", "query": "query"}]

    def get_relationship(self):
        return dict(self._relationship)

    def snapshot(self):
        return dict(self._snapshot)

    def list_relationship_timeline(self, limit=30):
        return list(self._timeline[:limit])

    def list_conflict_repairs(self, limit=30):
        return list(self._repairs[:limit])

    def list_source_refs(self, limit=30):
        return list(self._sources[:limit])


class BackendSessionTests(unittest.TestCase):
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
                        "__interrupt__": [
                            {
                                "value": {
                                    "kind": "tool_approval",
                                    "source": "memory",
                                    "tool_calls": [
                                        {"name": "set_profile", "args": {"key": "timezone", "value": "Asia/Shanghai"}}
                                    ],
                                }
                            }
                        ]
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

    def test_session_views_expose_worldline_persona_and_sources(self):
        values = {
            "persona_state": {"role": "kurisu_amadeus"},
            "emotion_state": {"label": "care"},
            "bond_state": {"trust": 0.7},
            "allostasis_state": {"autonomy_need": 0.4},
            "counterpart_assessment": {"stance": "open"},
            "semantic_narrative_profile": {"presence_carry": 0.5},
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

        persona = session.persona_view()
        self.assertEqual(persona["persona_state"]["role"], "kurisu_amadeus")
        self.assertEqual(persona["behavior_queue_summary"][0]["agenda_id"], "a1")

        bond = session.bond_view()
        self.assertEqual(bond["relationship_state"]["stage"], "warming")
        self.assertEqual(bond["bond_state"]["trust"], 0.7)

        sources = session.sources_view()
        self.assertEqual(sources["sources"][0]["tool_name"], "web_search")
        self.assertEqual(sources["claim_links"][0]["source_ids"], [9])

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


if __name__ == "__main__":
    unittest.main()
