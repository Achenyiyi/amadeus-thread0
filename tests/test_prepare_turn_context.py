import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from amadeus_thread0.graph_parts.prepare_turn_context import _prepare_turn_context
from amadeus_thread0.graph_parts.relational_carryover import (
    _apply_retrieved_behavior_trace_bridge,
    _hydrate_retrieved_agenda_lifecycle_residue,
)


def _retrieved_trace_payload() -> dict[str, object]:
    return {
        "semantic_self_narratives": [],
        "working_items": [],
        "working_chars": 0,
        "triggered": False,
        "relationship": {
            "stage": "friend",
            "notes": "",
            "affinity_score": 0.0,
            "trust_score": 0.0,
            "derived": True,
        },
        "behavior_plan_traces": [
            {
                "after_summary": "等忙完这阵，再轻轻回头看看冈部那边是不是还卡着。",
                "metadata": {
                    "plan_kind": "deferred_checkin",
                    "trigger_family": "life_window",
                    "carryover_mode": "small_opening",
                    "carryover_strength": 0.58,
                    "relationship_weather": "warm_residue",
                    "presence_residue": 0.34,
                    "ambient_resonance": 0.22,
                    "self_activity_momentum": 0.48,
                },
            }
        ],
    }


def _retrieved_reactivation_payload() -> dict[str, object]:
    payload = _retrieved_trace_payload()
    payload["behavior_reactivation_traces"] = [
        {
            "after_summary": "先前那点惦记又浮了上来，所以这次回头更像顺着旧线继续，而不是临时起意。",
            "metadata": {
                "carryover_mode": "small_opening",
                "carryover_strength": 0.61,
                "relationship_weather": "warm_residue",
                "source_plan_kind": "deferred_checkin",
                "source_trigger_family": "life_window",
                "current_plan_kind": "small_opening",
                "presence_residue": 0.36,
                "ambient_resonance": 0.21,
                "self_activity_momentum": 0.45,
            },
        }
    ]
    return payload


def _retrieved_behavior_consequence_payload() -> dict[str, object]:
    payload = _retrieved_trace_payload()
    payload["behavior_plan_traces"] = []
    payload["behavior_consequence_traces"] = [
        {
            "after_summary": "前面那点窗口已经自然错开了，但关系里还留着一种没有硬断掉的余温。",
            "metadata": {
                "consequence_kind": "let_window_expire",
                "trigger_family": "life_window",
                "carryover_mode": "quiet_recontact",
                "relationship_weather": "warm_residue",
                "relationship_effect": "window_released",
                "self_effect": "attention_returns_to_self",
            },
        }
    ]
    return payload


def _retrieved_agenda_lifecycle_payload() -> dict[str, object]:
    payload = _retrieved_trace_payload()
    payload["behavior_plan_traces"] = []
    payload["agenda_lifecycle_traces"] = [
        {
            "after_summary": "这次先把窗口按住，没有顺势往前推进。",
            "metadata": {
                "lifecycle_kind": "held",
                "source_event_kind": "time_idle",
                "trigger_family": "life_window",
                "relationship_weather": "warm_residue",
                "carryover_mode": "quiet_recontact",
                "carryover_strength": 0.37,
                "hold_count": 2,
                "recontact_cooldown": 0.41,
                "presence_residue": 0.29,
                "ambient_resonance": 0.21,
                "self_activity_momentum": 0.46,
                "own_rhythm_bias": 0.53,
                "counterpart_scene_bias": "busy_not_disrespectful",
                "continuity_anchor": 0.58,
                "own_rhythm_anchor": 0.61,
                "recontact_anchor": 0.44,
                "boundary_anchor": 0.18,
                "memory_anchor": 0.42,
                "lineage_gravity": 0.47,
                "contact_lineage": 0.51,
                "repair_lineage": 0.33,
                "boundary_lineage": 0.19,
                "selfhood_lineage": 0.36,
                "agency_lineage": 0.54,
                "source_tags": ["agenda_lifecycle", "held", "life_window"],
            },
        }
    ]
    return payload


class RetrievedBehaviorTraceBridgeTests(unittest.TestCase):
    def test_bridge_backfills_user_turn_when_no_recent_carryover_exists(self):
        current_event, interaction_carryover = _apply_retrieved_behavior_trace_bridge(
            retrieved=_retrieved_trace_payload(),
            current_event={"kind": "user_utterance", "event_frame": "dialogue", "tags": []},
            interaction_carryover={},
        )

        self.assertEqual(str(current_event.get("carryover_mode") or ""), "small_opening")
        self.assertAlmostEqual(float(current_event.get("presence_residue") or 0.0), 0.34, places=3)
        self.assertEqual(str(interaction_carryover.get("carryover_mode") or ""), "life_window")
        self.assertAlmostEqual(float(interaction_carryover.get("strength") or 0.0), 0.58, places=3)
        self.assertEqual(str(interaction_carryover.get("source") or ""), "retrieved_behavior_plan")

    def test_bridge_does_not_override_existing_recent_carryover(self):
        current_event, interaction_carryover = _apply_retrieved_behavior_trace_bridge(
            retrieved=_retrieved_trace_payload(),
            current_event={"kind": "user_utterance", "event_frame": "dialogue", "tags": []},
            interaction_carryover={"carryover_mode": "shared_window", "strength": 0.44},
        )

        self.assertEqual(str(current_event.get("carryover_mode") or ""), "")
        self.assertEqual(str(interaction_carryover.get("carryover_mode") or ""), "shared_window")
        self.assertAlmostEqual(float(interaction_carryover.get("strength") or 0.0), 0.44, places=3)

    def test_bridge_prefers_behavior_reactivation_trace_before_raw_plan(self):
        current_event, interaction_carryover = _apply_retrieved_behavior_trace_bridge(
            retrieved=_retrieved_reactivation_payload(),
            current_event={"kind": "user_utterance", "event_frame": "dialogue", "tags": []},
            interaction_carryover={},
        )

        self.assertEqual(str(current_event.get("carryover_mode") or ""), "small_opening")
        self.assertAlmostEqual(float(current_event.get("presence_residue") or 0.0), 0.36, places=3)
        self.assertEqual(str(interaction_carryover.get("carryover_mode") or ""), "life_window")
        self.assertAlmostEqual(float(interaction_carryover.get("strength") or 0.0), 0.61, places=3)
        self.assertEqual(str(interaction_carryover.get("source") or ""), "retrieved_behavior_reactivation")
        self.assertIn("顺着旧线继续", str(interaction_carryover.get("note") or ""))

    def test_bridge_can_rehydrate_carryover_from_behavior_consequence_trace(self):
        current_event, interaction_carryover = _apply_retrieved_behavior_trace_bridge(
            retrieved=_retrieved_behavior_consequence_payload(),
            current_event={"kind": "user_utterance", "event_frame": "dialogue", "tags": []},
            interaction_carryover={},
        )

        self.assertEqual(str(current_event.get("carryover_mode") or ""), "quiet_recontact")
        self.assertGreaterEqual(float(current_event.get("presence_residue") or 0.0), 0.22)
        self.assertEqual(str(interaction_carryover.get("carryover_mode") or ""), "life_window")
        self.assertGreaterEqual(float(interaction_carryover.get("strength") or 0.0), 0.24)
        self.assertEqual(str(interaction_carryover.get("source") or ""), "retrieved_behavior_consequence")
        self.assertIn("relationship_effect:window_released", interaction_carryover.get("source_tags") or [])


class RetrievedAgendaLifecycleHydrationTests(unittest.TestCase):
    def test_hydrate_retrieved_agenda_lifecycle_restores_residue_payload(self):
        residue = _hydrate_retrieved_agenda_lifecycle_residue(
            retrieved=_retrieved_agenda_lifecycle_payload(),
        )

        self.assertEqual(str(residue.get("kind") or ""), "held")
        self.assertEqual(str(residue.get("carryover_mode") or ""), "quiet_recontact")
        self.assertAlmostEqual(float(residue.get("carryover_strength") or 0.0), 0.37, places=3)
        self.assertIn("retrieved_agenda_lifecycle", residue.get("source_tags") or [])


class PrepareTurnContextTests(unittest.TestCase):
    def test_prepare_turn_context_prefers_fresher_semantic_profile_for_carryover_seed(self):
        profile = {
            "counterpart_id": "okabe_rintaro",
            "name": "冈部伦太郎",
            "short_name": "冈部",
            "aliases": ["冈部伦太郎", "冈部"],
        }
        persona_core = {
            "character_id": "kurisu_amadeus",
            "display_name": "Amadeus 牧濑红莉栖",
            "role_brief": "",
            "identity_axioms": [],
            "value_floor": [],
            "evolution_contract": {},
            "strict_canon": True,
        }
        relationship = {
            "stage": "friend",
            "notes": "",
            "affinity_score": 0.0,
            "trust_score": 0.0,
            "derived": True,
        }
        store = Mock()
        store.get_relationship.return_value = relationship
        store.set_relationship.return_value = None
        stale_profile = {
            "history_weight": 0.04,
            "continuity_depth": 0.06,
            "bond_depth": 0.02,
            "active_categories": [],
            "summary_lines": [],
            "long_term_axis_count": 0,
        }
        fresh_profile = {
            "history_weight": 0.72,
            "continuity_depth": 0.76,
            "bond_depth": 0.68,
            "presence_carry": 0.55,
            "selfhood_integrity": 0.64,
            "active_categories": ["bond_style", "presence_style"],
            "summary_lines": ["前面的熟悉感已经沉下来，不是临时想起。"],
            "prompt_anchor_lines": ["这种熟悉感不是凭空冒出来的。"],
            "long_term_self_narratives": ["她会把这种关系延续当成真实历史的一部分。"],
            "long_term_axis_count": 2,
        }
        semantic_calls: list[dict[str, object]] = []

        def _capture_recent_interaction_carryover(**kwargs):
            semantic = kwargs.get("semantic_narrative_profile")
            semantic_calls.append(dict(semantic) if isinstance(semantic, dict) else {})
            return {}

        with ExitStack() as stack:
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._active_counterpart_profile", return_value=(profile, {}))
            )
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._active_persona_core", return_value=(persona_core, {}))
            )
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._messages", return_value=[]))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._normalize_event_override", return_value={}))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context.derive_pending_fragment", return_value=""))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context.derive_pending_user_goal", return_value=""))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context.has_active_continuation", return_value=False))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context.continuation_seed_text", return_value=""))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._compact_thread_if_needed", return_value=None))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._science_mode_from_context", return_value=False))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._response_style_hint", return_value="natural"))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._is_external_probe_context", return_value=False))
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._retrieve_context", return_value=_retrieved_trace_payload())
            )
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._relationship_runtime_snapshot", return_value=relationship)
            )
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._relationship_has_meaningful_signal", return_value=True)
            )
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._canon_okabe_recontact_baseline", return_value={}))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._worldline_focus", return_value=[]))
            stack.enter_context(
                patch(
                    "amadeus_thread0.graph_parts.prepare_turn_context._appraisal_event_context",
                    return_value={"kind": "user_utterance", "event_frame": "dialogue", "tags": []},
                )
            )
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._semantic_narrative_profile", return_value=fresh_profile)
            )
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._recent_interaction_carryover", side_effect=_capture_recent_interaction_carryover))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._seeded_interaction_carryover_from_state", return_value={}))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._invoke_turn_appraisal", return_value={}))
            stack.enter_context(
                patch(
                    "amadeus_thread0.graph_parts.prepare_turn_context._build_current_event",
                    return_value={"kind": "user_utterance", "event_frame": "dialogue", "tags": []},
                )
            )
            stack.enter_context(
                patch(
                    "amadeus_thread0.graph_parts.prepare_turn_context._append_recent_events",
                    side_effect=lambda recent, event, limit=6: [event],
                )
            )
            prepared = _prepare_turn_context(
                state={"semantic_narrative_profile": stale_profile},
                store=store,
                turn_now_ts=123,
            )

        self.assertEqual(prepared["prior_semantic_narrative_profile"], fresh_profile)
        self.assertGreaterEqual(len(semantic_calls), 2)
        self.assertEqual(semantic_calls[0], fresh_profile)
        self.assertEqual(semantic_calls[1], fresh_profile)

    def test_prepare_turn_context_passes_proactive_continuity_history_into_carryover(self):
        profile = {
            "counterpart_id": "okabe_rintaro",
            "name": "冈部伦太郎",
            "short_name": "冈部",
            "aliases": ["冈部伦太郎", "冈部"],
        }
        persona_core = {
            "character_id": "kurisu_amadeus",
            "display_name": "Amadeus 牧濑红莉栖",
            "role_brief": "",
            "identity_axioms": [],
            "value_floor": [],
            "evolution_contract": {},
            "strict_canon": True,
        }
        relationship = {
            "stage": "friend",
            "notes": "",
            "affinity_score": 0.0,
            "trust_score": 0.0,
            "derived": True,
        }
        store = Mock()
        store.get_relationship.return_value = relationship
        store.set_relationship.return_value = None
        proactive_history = [
            {
                "content": {
                    "summary": "她把窗口先按住，继续顺着自己的节奏走了一会儿。",
                    "kind": "held",
                    "trace_family": "own_rhythm",
                    "carryover_mode": "own_rhythm",
                }
            }
        ]
        store.list_proactive_continuity_history.return_value = proactive_history
        carryover_calls: list[object] = []

        def _capture_recent_interaction_carryover(**kwargs):
            carryover_calls.append(kwargs.get("proactive_continuity_history"))
            return {}

        with ExitStack() as stack:
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._active_counterpart_profile", return_value=(profile, {}))
            )
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._active_persona_core", return_value=(persona_core, {}))
            )
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._messages", return_value=[]))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._normalize_event_override", return_value={}))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context.derive_pending_fragment", return_value=""))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context.derive_pending_user_goal", return_value=""))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context.has_active_continuation", return_value=False))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context.continuation_seed_text", return_value=""))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._compact_thread_if_needed", return_value=None))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._science_mode_from_context", return_value=False))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._response_style_hint", return_value="natural"))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._is_external_probe_context", return_value=False))
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._retrieve_context", return_value=_retrieved_trace_payload())
            )
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._relationship_runtime_snapshot", return_value=relationship)
            )
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._relationship_has_meaningful_signal", return_value=True)
            )
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._canon_okabe_recontact_baseline", return_value={}))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._worldline_focus", return_value=[]))
            stack.enter_context(
                patch(
                    "amadeus_thread0.graph_parts.prepare_turn_context._appraisal_event_context",
                    return_value={"kind": "user_utterance", "event_frame": "dialogue", "tags": []},
                )
            )
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._semantic_narrative_profile", return_value={})
            )
            stack.enter_context(
                patch(
                    "amadeus_thread0.graph_parts.prepare_turn_context._recent_interaction_carryover",
                    side_effect=_capture_recent_interaction_carryover,
                )
            )
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._seeded_interaction_carryover_from_state", return_value={}))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._invoke_turn_appraisal", return_value={}))
            stack.enter_context(
                patch(
                    "amadeus_thread0.graph_parts.prepare_turn_context._build_current_event",
                    return_value={"kind": "user_utterance", "event_frame": "dialogue", "tags": []},
                )
            )
            stack.enter_context(
                patch(
                    "amadeus_thread0.graph_parts.prepare_turn_context._append_recent_events",
                    side_effect=lambda recent, event, limit=6: [event],
                )
            )
            _prepare_turn_context(
                state={"semantic_narrative_profile": {}},
                store=store,
                turn_now_ts=123,
            )

        self.assertEqual(store.list_proactive_continuity_history.call_count, 1)
        self.assertGreaterEqual(len(carryover_calls), 2)
        self.assertEqual(carryover_calls[0], proactive_history)
        self.assertEqual(carryover_calls[1], proactive_history)

    def test_prepare_turn_context_backfills_retrieved_behavior_trace_before_runtime(self):
        profile = {
            "counterpart_id": "okabe_rintaro",
            "name": "冈部伦太郎",
            "short_name": "冈部",
            "aliases": ["冈部伦太郎", "冈部"],
        }
        persona_core = {
            "character_id": "kurisu_amadeus",
            "display_name": "Amadeus 牧濑红莉栖",
            "role_brief": "",
            "identity_axioms": [],
            "value_floor": [],
            "evolution_contract": {},
            "strict_canon": True,
        }
        relationship = {
            "stage": "friend",
            "notes": "",
            "affinity_score": 0.0,
            "trust_score": 0.0,
            "derived": True,
        }
        store = Mock()
        store.get_relationship.return_value = relationship
        store.set_relationship.return_value = None

        with ExitStack() as stack:
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._active_counterpart_profile", return_value=(profile, {}))
            )
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._active_persona_core", return_value=(persona_core, {}))
            )
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._messages", return_value=[]))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._normalize_event_override", return_value={}))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context.derive_pending_fragment", return_value=""))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context.derive_pending_user_goal", return_value=""))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context.has_active_continuation", return_value=False))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context.continuation_seed_text", return_value=""))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._compact_thread_if_needed", return_value=None))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._science_mode_from_context", return_value=False))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._response_style_hint", return_value="natural"))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._is_external_probe_context", return_value=False))
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._retrieve_context", return_value=_retrieved_trace_payload())
            )
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._relationship_runtime_snapshot", return_value=relationship)
            )
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._relationship_has_meaningful_signal", return_value=True)
            )
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._canon_okabe_recontact_baseline", return_value={}))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._worldline_focus", return_value=[]))
            stack.enter_context(
                patch(
                    "amadeus_thread0.graph_parts.prepare_turn_context._appraisal_event_context",
                    return_value={"kind": "user_utterance", "event_frame": "dialogue", "tags": []},
                )
            )
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._semantic_narrative_profile", return_value={}))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._invoke_turn_appraisal", return_value={}))
            stack.enter_context(
                patch(
                    "amadeus_thread0.graph_parts.prepare_turn_context._build_current_event",
                    return_value={"kind": "user_utterance", "event_frame": "dialogue", "tags": []},
                )
            )
            stack.enter_context(
                patch(
                    "amadeus_thread0.graph_parts.prepare_turn_context._append_recent_events",
                    side_effect=lambda recent, event, limit=6: [event],
                )
            )
            prepared = _prepare_turn_context(
                state={},
                store=store,
                turn_now_ts=123,
            )

        self.assertEqual(str(prepared["current_event"].get("carryover_mode") or ""), "small_opening")
        self.assertAlmostEqual(float(prepared["current_event"].get("presence_residue") or 0.0), 0.34, places=3)
        self.assertEqual(str(prepared["interaction_carryover"].get("carryover_mode") or ""), "life_window")
        self.assertAlmostEqual(float(prepared["interaction_carryover"].get("strength") or 0.0), 0.58, places=3)
        self.assertEqual(str(prepared["interaction_carryover"].get("source") or ""), "retrieved_behavior_plan")

    def test_prepare_turn_context_backfills_retrieved_behavior_consequence_before_runtime(self):
        profile = {
            "counterpart_id": "okabe_rintaro",
            "name": "冈部伦太郎",
            "short_name": "冈部",
            "aliases": ["冈部伦太郎", "冈部"],
        }
        persona_core = {
            "character_id": "kurisu_amadeus",
            "display_name": "Amadeus 牧濑红莉栖",
            "role_brief": "",
            "identity_axioms": [],
            "value_floor": [],
            "evolution_contract": {},
            "strict_canon": True,
        }
        relationship = {
            "stage": "friend",
            "notes": "",
            "affinity_score": 0.0,
            "trust_score": 0.0,
            "derived": True,
        }
        store = Mock()
        store.get_relationship.return_value = relationship
        store.set_relationship.return_value = None

        with ExitStack() as stack:
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._active_counterpart_profile", return_value=(profile, {}))
            )
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._active_persona_core", return_value=(persona_core, {}))
            )
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._messages", return_value=[]))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._normalize_event_override", return_value={}))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context.derive_pending_fragment", return_value=""))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context.derive_pending_user_goal", return_value=""))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context.has_active_continuation", return_value=False))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context.continuation_seed_text", return_value=""))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._compact_thread_if_needed", return_value=None))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._science_mode_from_context", return_value=False))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._response_style_hint", return_value="natural"))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._is_external_probe_context", return_value=False))
            stack.enter_context(
                patch(
                    "amadeus_thread0.graph_parts.prepare_turn_context._retrieve_context",
                    return_value=_retrieved_behavior_consequence_payload(),
                )
            )
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._relationship_runtime_snapshot", return_value=relationship)
            )
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._relationship_has_meaningful_signal", return_value=True)
            )
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._canon_okabe_recontact_baseline", return_value={}))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._worldline_focus", return_value=[]))
            stack.enter_context(
                patch(
                    "amadeus_thread0.graph_parts.prepare_turn_context._appraisal_event_context",
                    return_value={"kind": "user_utterance", "event_frame": "dialogue", "tags": []},
                )
            )
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._semantic_narrative_profile", return_value={}))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._invoke_turn_appraisal", return_value={}))
            stack.enter_context(
                patch(
                    "amadeus_thread0.graph_parts.prepare_turn_context._build_current_event",
                    return_value={"kind": "user_utterance", "event_frame": "dialogue", "tags": []},
                )
            )
            stack.enter_context(
                patch(
                    "amadeus_thread0.graph_parts.prepare_turn_context._append_recent_events",
                    side_effect=lambda recent, event, limit=6: [event],
                )
            )
            prepared = _prepare_turn_context(
                state={},
                store=store,
                turn_now_ts=123,
            )

        self.assertEqual(str(prepared["current_event"].get("carryover_mode") or ""), "quiet_recontact")
        self.assertGreaterEqual(float(prepared["current_event"].get("presence_residue") or 0.0), 0.22)
        self.assertEqual(str(prepared["interaction_carryover"].get("carryover_mode") or ""), "life_window")
        self.assertGreaterEqual(float(prepared["interaction_carryover"].get("strength") or 0.0), 0.24)
        self.assertEqual(str(prepared["interaction_carryover"].get("source") or ""), "retrieved_behavior_consequence")

    def test_prepare_turn_context_rehydrates_retrieved_agenda_lifecycle_before_runtime(self):
        profile = {
            "counterpart_id": "okabe_rintaro",
            "name": "冈部伦太郎",
            "short_name": "冈部",
            "aliases": ["冈部伦太郎", "冈部"],
        }
        persona_core = {
            "character_id": "kurisu_amadeus",
            "display_name": "Amadeus 牧濑红莉栖",
            "role_brief": "",
            "identity_axioms": [],
            "value_floor": [],
            "evolution_contract": {},
            "strict_canon": True,
        }
        relationship = {
            "stage": "friend",
            "notes": "",
            "affinity_score": 0.0,
            "trust_score": 0.0,
            "derived": True,
        }
        store = Mock()
        store.get_relationship.return_value = relationship
        store.set_relationship.return_value = None

        with ExitStack() as stack:
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._active_counterpart_profile", return_value=(profile, {}))
            )
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._active_persona_core", return_value=(persona_core, {}))
            )
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._messages", return_value=[]))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._normalize_event_override", return_value={}))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context.derive_pending_fragment", return_value=""))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context.derive_pending_user_goal", return_value=""))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context.has_active_continuation", return_value=False))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context.continuation_seed_text", return_value=""))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._compact_thread_if_needed", return_value=None))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._science_mode_from_context", return_value=False))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._response_style_hint", return_value="natural"))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._is_external_probe_context", return_value=False))
            stack.enter_context(
                patch(
                    "amadeus_thread0.graph_parts.prepare_turn_context._retrieve_context",
                    return_value=_retrieved_agenda_lifecycle_payload(),
                )
            )
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._relationship_runtime_snapshot", return_value=relationship)
            )
            stack.enter_context(
                patch("amadeus_thread0.graph_parts.prepare_turn_context._relationship_has_meaningful_signal", return_value=True)
            )
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._canon_okabe_recontact_baseline", return_value={}))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._worldline_focus", return_value=[]))
            stack.enter_context(
                patch(
                    "amadeus_thread0.graph_parts.prepare_turn_context._appraisal_event_context",
                    return_value={"kind": "user_utterance", "event_frame": "dialogue", "tags": []},
                )
            )
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._semantic_narrative_profile", return_value={}))
            stack.enter_context(patch("amadeus_thread0.graph_parts.prepare_turn_context._invoke_turn_appraisal", return_value={}))
            stack.enter_context(
                patch(
                    "amadeus_thread0.graph_parts.prepare_turn_context._build_current_event",
                    return_value={"kind": "user_utterance", "event_frame": "dialogue", "tags": []},
                )
            )
            stack.enter_context(
                patch(
                    "amadeus_thread0.graph_parts.prepare_turn_context._append_recent_events",
                    side_effect=lambda recent, event, limit=6: [event],
                )
            )
            prepared = _prepare_turn_context(
                state={},
                store=store,
                turn_now_ts=123,
            )

        self.assertEqual(str(prepared["agenda_lifecycle_residue"].get("kind") or ""), "held")
        self.assertEqual(str(prepared["interaction_carryover"].get("source_event_kind") or ""), "agenda_lifecycle:held")
        self.assertEqual(str(prepared["interaction_carryover"].get("carryover_mode") or ""), "quiet_recontact")
        self.assertAlmostEqual(float(prepared["interaction_carryover"].get("strength") or 0.0), 0.37, places=3)
        self.assertAlmostEqual(float(prepared["seed_world_model_state"].get("self_activity_momentum") or 0.0), 0.53, places=3)
        self.assertAlmostEqual(float(prepared["seed_world_model_state"].get("presence_residue") or 0.0), 0.238, places=3)


if __name__ == "__main__":
    unittest.main()
