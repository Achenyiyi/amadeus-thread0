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
                    "respect_level": 0.76,
                    "reciprocity": 0.72,
                    "boundary_pressure": 0.08,
                    "reliability_read": 0.80,
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
                    "primary_motive": "preserve_self_rhythm",
                    "motive_tension": "self_rhythm_vs_contact",
                    "goal_frame": "先让这段窗口自然过去，把注意力收回自己的节奏。",
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

    def list_relationship_timeline(self, limit=30):
        return list(self._timeline[:limit])

    def list_conflict_repairs(self, limit=30):
        return list(self._repairs[:limit])

    def list_counterpart_assessment_history(self, limit=30):
        return list(self._counterpart_history[:limit])

    def list_proactive_continuity_history(self, limit=30):
        return list(self._proactive_history[:limit])

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

    def test_extract_final_text_prefers_explicit_final_text_field(self):
        session = BackendSession(graph=object(), memory_store=FakeMemoryStore(), thread_id="thread-a")
        text = session.extract_final_text(
            {
                "final_text": "finalized-answer",
                "messages": [SimpleNamespace(content="stale-answer")],
            }
        )
        self.assertEqual(text, "finalized-answer")

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
        self.assertEqual(worldline["counterpart_assessment_history"][0]["scene"], "care_bid")
        self.assertEqual(worldline["proactive_continuity_history"][0]["carryover_mode"], "own_rhythm")
        self.assertEqual(worldline["proactive_continuity_preview"][0]["trace_family"], "own_rhythm_busy_window")

        persona = session.persona_view()
        self.assertEqual(persona["persona_state"]["role"], "kurisu_amadeus")
        self.assertEqual(persona["behavior_queue_summary"][0]["agenda_id"], "a1")

        bond = session.bond_view()
        self.assertEqual(bond["relationship_state"]["stage"], "warming")
        self.assertEqual(bond["bond_state"]["trust"], 0.7)
        self.assertEqual(bond["counterpart_assessment_history"][0]["scene"], "care_bid")
        self.assertEqual(bond["counterpart_assessment_preview"][0]["stance"], "open")
        self.assertEqual(bond["proactive_continuity_history"][0]["kind"], "released_to_self_activity")
        self.assertEqual(bond["proactive_continuity_preview"][0]["carryover_mode"], "own_rhythm")

        sources = session.sources_view()
        self.assertEqual(sources["sources"][0]["tool_name"], "web_search")
        self.assertEqual(sources["claim_links"][0]["source_ids"], [9])

    def test_session_views_use_final_reconsolidation_snapshot_for_evolution_summary(self):
        final_snapshot = {
            "event_kind": "user_utterance",
            "interaction_frame": "relationship",
            "primary_motive": "gentle_recontact",
            "motive_tension": "self_rhythm_vs_contact",
            "goal_frame": "先从自己的节奏里回头，留一个不压迫对方的小开口。",
            "interaction_carryover": {
                "source": "reconsolidation",
                "strength": 0.67,
                "carryover_mode": "warm_residue",
                "relationship_weather": "steady_warmth",
                "note": "final carryover should win",
            },
            "counterpart": {
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
            "behavior_plan": {"kind": "deferred_checkin"},
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
        self.assertEqual(persona["interaction_carryover"]["source"], "reconsolidation")
        self.assertEqual(persona["interaction_carryover"]["relationship_weather"], "steady_warmth")

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
                    "relationship_weather": "warm_residue",
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
        self.assertEqual(persona["behavior_action"]["primary_motive"], "honor_continuity")
        self.assertEqual(persona["behavior_action"]["timing_window_min"], 30)
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
