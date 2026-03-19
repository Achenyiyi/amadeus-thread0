import unittest
from unittest.mock import patch

from amadeus_thread0.graph_parts.prepare_turn_runtime import _prepare_turn_runtime


class _StopAfterPlan(RuntimeError):
    pass


class _StopAfterMemory(RuntimeError):
    pass


def _prepared_turn_fixture() -> dict[str, object]:
    return {
        "profile": {
            "counterpart_id": "okabe_rintaro",
            "name": "冈部伦太郎",
            "short_name": "冈部",
            "aliases": ["冈部伦太郎", "冈部"],
        },
        "persona_core": {
            "character_id": "kurisu_amadeus",
            "display_name": "Amadeus 牧濑红莉栖",
            "role_brief": "",
            "identity_axioms": [],
            "value_floor": [],
            "evolution_contract": {},
            "strict_canon": True,
        },
        "prior_behavior_agenda": [],
        "agenda_lifecycle_residue": {},
        "user_text": "",
        "effective_user_text": "",
        "science_mode": False,
        "response_style_hint": "natural",
        "external_probe_mode": False,
        "retrieved": {"semantic_self_narratives": [], "working_items": [], "working_chars": 0, "triggered": False},
        "relationship": {"stage": "friend", "notes": "", "affinity_score": 0.0, "trust_score": 0.0, "derived": True},
        "canon_recontact_baseline": {},
        "worldline_focus": [],
        "seed_emotion_state": {"label": "neutral"},
        "seed_bond_state": {"trust": 0.5, "closeness": 0.5, "hurt": 0.0, "irritation": 0.0, "engagement_drive": 0.5, "repair_confidence": 0.5},
        "seed_allostasis_state": {"safety_need": 0.2, "closeness_need": 0.2, "competence_need": 0.4, "autonomy_need": 0.2, "cognitive_budget": 0.8, "relational_security": 0.5},
        "seed_counterpart_assessment": {"respect_level": 0.6, "reciprocity": 0.6, "boundary_pressure": 0.1, "reliability_read": 0.6, "stance": "open", "scene": "neutral"},
        "seed_world_model_state": {},
        "seed_evolution_state": {},
        "seed_tsundere_intensity": 0.4,
        "appraisal": {},
        "current_event": {"kind": "time_idle", "event_frame": "idle", "tags": ["quiet_presence"], "idle_minutes": 18},
        "interaction_carryover": {},
    }


def _evolved_fixture() -> dict[str, object]:
    return {
        "world_model_state": {
            "self_activity_momentum": 0.74,
            "presence_residue": 0.34,
            "ambient_resonance": 0.28,
        },
        "evolution_state": {},
        "emotion_state": {"label": "neutral"},
        "bond_state": {"trust": 0.5, "closeness": 0.5, "hurt": 0.0, "irritation": 0.0, "engagement_drive": 0.5, "repair_confidence": 0.5},
        "allostasis_state": {"safety_need": 0.2, "closeness_need": 0.2, "competence_need": 0.4, "autonomy_need": 0.2, "cognitive_budget": 0.8, "relational_security": 0.5},
        "counterpart_assessment": {"respect_level": 0.6, "reciprocity": 0.6, "boundary_pressure": 0.1, "reliability_read": 0.6, "stance": "open", "scene": "neutral"},
        "behavior_policy": {},
        "behavior_action": {"action_target": "stale_engine_action", "primary_motive": "engine_stage"},
        "reconsolidation_snapshot": {"behavior_mode": "stale_engine_mode"},
    }


class PrepareTurnRuntimeTests(unittest.TestCase):
    def test_prepare_turn_runtime_backfills_carryover_from_retrieved_behavior_plan_trace(self):
        captured_call: dict[str, object] = {}

        def _fake_behavior_action_from_state(**kwargs):
            captured_call.update(kwargs)
            return {
                "action_target": "respond_now",
                "interaction_mode": "steady_reply",
                "primary_motive": "maintain_natural_contact",
                "motive_tension": "none",
                "goal_frame": "先自然接住这轮互动。",
                "initiative_level": 0.31,
                "deferred_action_family": "none",
                "timing_window_min": 0,
                "relationship_weather": "warm_residue",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "steady_presence",
                "channel": "speech",
            }

        prepared_turn = _prepared_turn_fixture()
        prepared_turn["current_event"] = {"kind": "user_utterance", "event_frame": "dialogue", "tags": []}
        prepared_turn["retrieved"] = {
            "semantic_self_narratives": [],
            "working_items": [],
            "working_chars": 0,
            "triggered": False,
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

        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", return_value=_evolved_fixture()):
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update", return_value=False):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot", side_effect=lambda **kwargs: kwargs["relationship"]):
                            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary", return_value="summary"):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                    side_effect=_fake_behavior_action_from_state,
                                ):
                                    with patch(
                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                        return_value={"kind": "respond_now"},
                                    ):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                            return_value=[],
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                return_value={},
                                            ):
                                                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl", return_value=None):
                                                    _prepare_turn_runtime(
                                                        state={"persona_state": {}},
                                                        store=object(),
                                                        turn_now_ts=123,
                                                        prepared_turn=prepared_turn,
                                                    )

        interaction_carryover = (
            captured_call.get("interaction_carryover")
            if isinstance(captured_call.get("interaction_carryover"), dict)
            else {}
        )
        current_event = captured_call.get("current_event") if isinstance(captured_call.get("current_event"), dict) else {}
        self.assertEqual(str(interaction_carryover.get("carryover_mode") or ""), "life_window")
        self.assertAlmostEqual(float(interaction_carryover.get("strength") or 0.0), 0.58, places=3)
        self.assertEqual(str(interaction_carryover.get("source") or ""), "retrieved_behavior_plan")
        self.assertIn("等忙完这阵", str(interaction_carryover.get("note") or ""))
        self.assertEqual(str(current_event.get("carryover_mode") or ""), "small_opening")
        self.assertAlmostEqual(float(current_event.get("presence_residue") or 0.0), 0.34, places=3)

    def test_prepare_turn_runtime_biases_from_retrieved_behavior_consequence_trace(self):
        captured_call: dict[str, object] = {}

        def _fake_evolve_turn_state(**kwargs):
            prev_world = dict(kwargs.get("prev_world_model_state") or {})
            prev_counterpart = dict(kwargs.get("prev_counterpart_assessment") or {})
            return {
                "world_model_state": prev_world,
                "evolution_state": {},
                "emotion_state": {"label": "neutral"},
                "bond_state": dict(kwargs.get("prev_bond_state") or {}),
                "allostasis_state": dict(kwargs.get("prev_allostasis_state") or {}),
                "counterpart_assessment": prev_counterpart,
                "behavior_policy": {},
                "behavior_action": {},
                "reconsolidation_snapshot": {},
            }

        def _fake_behavior_action_from_state(**kwargs):
            captured_call.update(kwargs)
            return {
                "action_target": "respond_now",
                "interaction_mode": "steady_reply",
                "primary_motive": "maintain_natural_contact",
                "motive_tension": "none",
                "goal_frame": "先自然接住这轮互动。",
                "initiative_level": 0.31,
                "deferred_action_family": "none",
                "timing_window_min": 0,
                "relationship_weather": "warm_residue",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "steady_presence",
                "channel": "speech",
            }

        prepared_turn = _prepared_turn_fixture()
        prepared_turn["current_event"] = {"kind": "user_utterance", "event_frame": "dialogue", "tags": []}
        prepared_turn["retrieved"] = {
            "semantic_self_narratives": [],
            "working_items": [],
            "working_chars": 0,
            "triggered": False,
            "behavior_consequence_traces": [
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
            ],
        }

        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", side_effect=_fake_evolve_turn_state):
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update", return_value=False):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot", side_effect=lambda **kwargs: kwargs["relationship"]):
                            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary", return_value="summary"):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                    side_effect=_fake_behavior_action_from_state,
                                ):
                                    with patch(
                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                        return_value={"kind": "respond_now"},
                                    ):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                            return_value=[],
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                return_value={},
                                            ):
                                                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl", return_value=None):
                                                    _prepare_turn_runtime(
                                                        state={"persona_state": {}},
                                                        store=object(),
                                                        turn_now_ts=123,
                                                        prepared_turn=prepared_turn,
                                                    )

        interaction_carryover = (
            captured_call.get("interaction_carryover")
            if isinstance(captured_call.get("interaction_carryover"), dict)
            else {}
        )
        current_event = captured_call.get("current_event") if isinstance(captured_call.get("current_event"), dict) else {}
        world_model_state = (
            captured_call.get("world_model_state")
            if isinstance(captured_call.get("world_model_state"), dict)
            else {}
        )
        counterpart_assessment = (
            captured_call.get("counterpart_assessment")
            if isinstance(captured_call.get("counterpart_assessment"), dict)
            else {}
        )

        self.assertEqual(str(interaction_carryover.get("source") or ""), "retrieved_behavior_consequence")
        self.assertEqual(str(interaction_carryover.get("carryover_mode") or ""), "life_window")
        self.assertEqual(str(current_event.get("carryover_mode") or ""), "quiet_recontact")
        self.assertGreaterEqual(float(current_event.get("presence_residue") or 0.0), 0.22)
        self.assertGreaterEqual(float(world_model_state.get("presence_residue") or 0.0), 0.22)
        self.assertGreater(float(counterpart_assessment.get("reliability_read") or 0.0), 0.6)

    def test_prepare_turn_runtime_biases_from_retrieved_behavior_reactivation_trace(self):
        captured_call: dict[str, object] = {}

        def _fake_evolve_turn_state(**kwargs):
            prev_world = dict(kwargs.get("prev_world_model_state") or {})
            prev_counterpart = dict(kwargs.get("prev_counterpart_assessment") or {})
            return {
                "world_model_state": prev_world,
                "evolution_state": {},
                "emotion_state": {"label": "neutral"},
                "bond_state": dict(kwargs.get("prev_bond_state") or {}),
                "allostasis_state": dict(kwargs.get("prev_allostasis_state") or {}),
                "counterpart_assessment": prev_counterpart,
                "behavior_policy": {},
                "behavior_action": {},
                "reconsolidation_snapshot": {},
            }

        def _fake_behavior_action_from_state(**kwargs):
            captured_call.update(kwargs)
            return {
                "action_target": "respond_now",
                "interaction_mode": "steady_reply",
                "primary_motive": "maintain_natural_contact",
                "motive_tension": "none",
                "goal_frame": "先自然接住这轮互动。",
                "initiative_level": 0.31,
                "deferred_action_family": "none",
                "timing_window_min": 0,
                "relationship_weather": "warm_residue",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "steady_presence",
                "channel": "speech",
            }

        prepared_turn = _prepared_turn_fixture()
        prepared_turn["current_event"] = {"kind": "user_utterance", "event_frame": "dialogue", "tags": []}
        prepared_turn["retrieved"] = {
            "semantic_self_narratives": [],
            "working_items": [],
            "working_chars": 0,
            "triggered": False,
            "behavior_reactivation_traces": [
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
            ],
        }

        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", side_effect=_fake_evolve_turn_state):
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update", return_value=False):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot", side_effect=lambda **kwargs: kwargs["relationship"]):
                            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary", return_value="summary"):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                    side_effect=_fake_behavior_action_from_state,
                                ):
                                    with patch(
                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                        return_value={"kind": "respond_now"},
                                    ):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                            return_value=[],
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                return_value={},
                                            ):
                                                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl", return_value=None):
                                                    _prepare_turn_runtime(
                                                        state={"persona_state": {}},
                                                        store=object(),
                                                        turn_now_ts=123,
                                                        prepared_turn=prepared_turn,
                                                    )

        interaction_carryover = (
            captured_call.get("interaction_carryover")
            if isinstance(captured_call.get("interaction_carryover"), dict)
            else {}
        )
        current_event = captured_call.get("current_event") if isinstance(captured_call.get("current_event"), dict) else {}
        world_model_state = (
            captured_call.get("world_model_state")
            if isinstance(captured_call.get("world_model_state"), dict)
            else {}
        )
        counterpart_assessment = (
            captured_call.get("counterpart_assessment")
            if isinstance(captured_call.get("counterpart_assessment"), dict)
            else {}
        )

        self.assertEqual(str(interaction_carryover.get("source") or ""), "retrieved_behavior_reactivation")
        self.assertEqual(str(interaction_carryover.get("carryover_mode") or ""), "life_window")
        self.assertEqual(str(current_event.get("carryover_mode") or ""), "small_opening")
        self.assertGreaterEqual(float(current_event.get("presence_residue") or 0.0), 0.36)
        self.assertGreaterEqual(float(world_model_state.get("presence_residue") or 0.0), 0.36)
        self.assertGreater(float(counterpart_assessment.get("reliability_read") or 0.0), 0.6)

    def test_prepare_turn_runtime_reapplies_retrieved_trace_after_memory_refresh(self):
        def _fake_evolve_turn_state(**kwargs):
            prev_world = dict(kwargs.get("prev_world_model_state") or {})
            prev_counterpart = dict(kwargs.get("prev_counterpart_assessment") or {})
            return {
                "world_model_state": prev_world,
                "evolution_state": {},
                "emotion_state": {"label": "neutral"},
                "bond_state": dict(kwargs.get("prev_bond_state") or {}),
                "allostasis_state": dict(kwargs.get("prev_allostasis_state") or {}),
                "counterpart_assessment": prev_counterpart,
                "behavior_policy": {},
                "behavior_action": {},
                "reconsolidation_snapshot": {},
            }

        prepared_turn = _prepared_turn_fixture()
        prepared_turn["current_event"] = {"kind": "user_utterance", "event_frame": "dialogue", "tags": []}
        prepared_turn["retrieved"] = {
            "semantic_self_narratives": [],
            "working_items": [],
            "working_chars": 0,
            "triggered": False,
        }
        refreshed_retrieved = {
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

        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", side_effect=_fake_evolve_turn_state):
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update", return_value=True):
                        with patch(
                            "amadeus_thread0.graph_parts.prepare_turn_runtime._retrieve_context",
                            return_value=refreshed_retrieved,
                        ):
                            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._worldline_focus", return_value=[]):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot",
                                    side_effect=lambda **kwargs: kwargs["relationship"],
                                ):
                                    with patch(
                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary",
                                        return_value="summary",
                                    ):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                            return_value={
                                                "action_target": "respond_now",
                                                "interaction_mode": "steady_reply",
                                                "primary_motive": "maintain_natural_contact",
                                                "motive_tension": "none",
                                                "goal_frame": "先自然接住这轮互动。",
                                                "initiative_level": 0.31,
                                                "deferred_action_family": "none",
                                                "timing_window_min": 0,
                                                "relationship_weather": "warm_residue",
                                                "attention_target": "counterpart_state",
                                                "nonverbal_signal": "steady_presence",
                                                "channel": "speech",
                                            },
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                                return_value={"kind": "respond_now"},
                                            ):
                                                with patch(
                                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                                    return_value=[],
                                                ):
                                                    with patch(
                                                        "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                        return_value={},
                                                    ):
                                                        with patch(
                                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl",
                                                            return_value=None,
                                                        ):
                                                            result = _prepare_turn_runtime(
                                                                state={"persona_state": {}},
                                                                store=object(),
                                                                turn_now_ts=123,
                                                                prepared_turn=prepared_turn,
                                                            )

        interaction_carryover = (
            result.get("interaction_carryover") if isinstance(result.get("interaction_carryover"), dict) else {}
        )
        current_event = result.get("current_event") if isinstance(result.get("current_event"), dict) else {}
        world_model_state = result.get("world_model_state") if isinstance(result.get("world_model_state"), dict) else {}
        counterpart_assessment = (
            result.get("counterpart_assessment") if isinstance(result.get("counterpart_assessment"), dict) else {}
        )

        self.assertEqual(str(interaction_carryover.get("source") or ""), "retrieved_behavior_plan")
        self.assertEqual(str(interaction_carryover.get("carryover_mode") or ""), "life_window")
        self.assertEqual(str(current_event.get("carryover_mode") or ""), "small_opening")
        self.assertGreaterEqual(float(current_event.get("presence_residue") or 0.0), 0.34)
        self.assertGreaterEqual(float(world_model_state.get("presence_residue") or 0.0), 0.34)
        self.assertGreater(float(counterpart_assessment.get("reliability_read") or 0.0), 0.6)

    def test_prepare_turn_runtime_does_not_override_recent_interaction_carryover_with_retrieved_trace(self):
        captured_call: dict[str, object] = {}

        def _fake_behavior_action_from_state(**kwargs):
            captured_call.update(kwargs)
            return {
                "action_target": "respond_now",
                "interaction_mode": "steady_reply",
                "primary_motive": "maintain_natural_contact",
                "motive_tension": "none",
                "goal_frame": "先自然接住这轮互动。",
                "initiative_level": 0.31,
                "deferred_action_family": "none",
                "timing_window_min": 0,
                "relationship_weather": "warm_residue",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "steady_presence",
                "channel": "speech",
            }

        prepared_turn = _prepared_turn_fixture()
        prepared_turn["current_event"] = {"kind": "user_utterance", "event_frame": "dialogue", "tags": []}
        prepared_turn["interaction_carryover"] = {
            "carryover_mode": "shared_window",
            "strength": 0.44,
            "note": "最近的共同窗口还在。",
        }
        prepared_turn["retrieved"] = {
            "semantic_self_narratives": [],
            "working_items": [],
            "working_chars": 0,
            "triggered": False,
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

        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", return_value=_evolved_fixture()):
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update", return_value=False):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot", side_effect=lambda **kwargs: kwargs["relationship"]):
                            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary", return_value="summary"):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                    side_effect=_fake_behavior_action_from_state,
                                ):
                                    with patch(
                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                        return_value={"kind": "respond_now"},
                                    ):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                            return_value=[],
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                return_value={},
                                            ):
                                                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl", return_value=None):
                                                    _prepare_turn_runtime(
                                                        state={"persona_state": {}},
                                                        store=object(),
                                                        turn_now_ts=123,
                                                        prepared_turn=prepared_turn,
                                                    )

        interaction_carryover = (
            captured_call.get("interaction_carryover")
            if isinstance(captured_call.get("interaction_carryover"), dict)
            else {}
        )
        current_event = captured_call.get("current_event") if isinstance(captured_call.get("current_event"), dict) else {}
        self.assertEqual(str(interaction_carryover.get("carryover_mode") or ""), "shared_window")
        self.assertAlmostEqual(float(interaction_carryover.get("strength") or 0.0), 0.44, places=3)
        self.assertEqual(str(current_event.get("carryover_mode") or ""), "")

    def test_prepare_turn_runtime_retrieved_trace_biases_idle_action_style(self):
        def _run(prepared_turn: dict[str, object]) -> dict[str, object]:
            def _fake_evolve_turn_state(**kwargs):
                prev_world = dict(kwargs.get("prev_world_model_state") or {})
                prev_counterpart = dict(kwargs.get("prev_counterpart_assessment") or {})
                presence = float(prev_world.get("presence_residue") or 0.0)
                reliability = float(prev_counterpart.get("reliability_read") or 0.0)
                initiative = 0.38
                warmth = 0.48
                if presence >= 0.28:
                    initiative = 0.56
                    warmth = 0.56
                if reliability >= 0.62:
                    initiative += 0.04
                    warmth += 0.02
                return {
                    "world_model_state": prev_world,
                    "evolution_state": {},
                    "emotion_state": {"label": "neutral"},
                    "bond_state": dict(kwargs.get("prev_bond_state") or {}),
                    "allostasis_state": dict(kwargs.get("prev_allostasis_state") or {}),
                    "counterpart_assessment": prev_counterpart,
                    "behavior_policy": {
                        "warmth": round(warmth, 3),
                        "initiative": round(initiative, 3),
                        "approach_vs_withdraw": 0.52,
                        "reply_length_bias": 0.44,
                        "boundary_assertiveness": 0.12,
                        "self_directedness": 0.18,
                    },
                    "behavior_action": {},
                    "reconsolidation_snapshot": {},
                }

            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", side_effect=_fake_evolve_turn_state):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update", return_value=False):
                            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot", side_effect=lambda **kwargs: kwargs["relationship"]):
                                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary", return_value="summary"):
                                    with patch(
                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                        side_effect=lambda *_args, **_kwargs: {"kind": "none"},
                                    ):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                            return_value=[],
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                return_value={},
                                            ):
                                                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl", return_value=None):
                                                    return _prepare_turn_runtime(
                                                        state={"persona_state": {}},
                                                        store=object(),
                                                        turn_now_ts=123,
                                                        prepared_turn=prepared_turn,
                                                    )

        baseline_turn = _prepared_turn_fixture()
        baseline_turn["retrieved"] = {
            "semantic_self_narratives": [],
            "working_items": [],
            "working_chars": 0,
            "triggered": False,
        }

        traced_turn = _prepared_turn_fixture()
        traced_turn["retrieved"] = {
            "semantic_self_narratives": [],
            "working_items": [],
            "working_chars": 0,
            "triggered": False,
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

        baseline_result = _run(baseline_turn)
        traced_result = _run(traced_turn)

        baseline_action = baseline_result.get("behavior_action") if isinstance(baseline_result.get("behavior_action"), dict) else {}
        traced_action = traced_result.get("behavior_action") if isinstance(traced_result.get("behavior_action"), dict) else {}
        traced_world = traced_result.get("world_model_state") if isinstance(traced_result.get("world_model_state"), dict) else {}
        traced_counterpart = traced_result.get("counterpart_assessment") if isinstance(traced_result.get("counterpart_assessment"), dict) else {}

        self.assertEqual(str(baseline_action.get("action_target") or ""), "wait_and_recheck")
        self.assertEqual(str(traced_action.get("action_target") or ""), "reach_out_now")
        self.assertGreater(
            float(traced_action.get("proactive_checkin_readiness") or 0.0),
            float(baseline_action.get("proactive_checkin_readiness") or 0.0),
        )
        self.assertGreaterEqual(float(traced_world.get("presence_residue") or 0.0), 0.34)
        self.assertGreater(float(traced_counterpart.get("reliability_read") or 0.0), 0.62)

    def test_prepare_turn_runtime_passes_world_model_state_into_behavior_plan(self):
        captured: dict[str, object] = {}
        captured_call: dict[str, object] = {}

        def _fake_behavior_plan_from_action(current_event, behavior_action, world_model_state=None):
            captured["current_event"] = current_event
            captured["behavior_action"] = behavior_action
            captured["world_model_state"] = world_model_state
            raise _StopAfterPlan

        def _fake_behavior_action_from_state(**kwargs):
            captured_call.update(kwargs)
            return {
                "action_target": "hold_own_rhythm",
                "interaction_mode": "self_activity_hold",
                "primary_motive": "preserve_self_rhythm",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "先维持自己的节奏，不急着把全部注意力交出去。",
                "initiative_level": 0.31,
                "deferred_action_family": "none",
                "timing_window_min": 18,
                "relationship_weather": "guarded_residue",
                "attention_target": "self_then_counterpart",
                "nonverbal_signal": "resume_task",
                "channel": "none",
            }

        prepared_turn = _prepared_turn_fixture()
        evolved = _evolved_fixture()

        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", return_value=evolved):
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update", return_value=False):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot", side_effect=lambda **kwargs: kwargs["relationship"]):
                            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary", return_value="summary"):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                    side_effect=_fake_behavior_action_from_state,
                                ):
                                    with patch(
                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                        side_effect=_fake_behavior_plan_from_action,
                                    ):
                                        with self.assertRaises(_StopAfterPlan):
                                            _prepare_turn_runtime(
                                                state={"persona_state": {}},
                                                store=object(),
                                                turn_now_ts=123,
                                                prepared_turn=prepared_turn,
                                            )

        self.assertEqual(str(captured["current_event"].get("kind") or ""), "time_idle")
        self.assertEqual(str(captured["behavior_action"].get("action_target") or ""), "hold_own_rhythm")
        self.assertIs(captured_call["appraisal"], prepared_turn["appraisal"])
        self.assertEqual(
            captured["world_model_state"],
            {
                "self_activity_momentum": 0.74,
                "presence_residue": 0.34,
                "ambient_resonance": 0.28,
            },
        )

    def test_prepare_turn_runtime_uses_runtime_action_for_passive_memory_update(self):
        captured: dict[str, object] = {}

        def _fake_behavior_action_from_state(**kwargs):
            return {
                "action_target": "hold_own_rhythm",
                "interaction_mode": "self_activity_hold",
                "primary_motive": "preserve_self_rhythm",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "先维持自己的节奏，不急着把全部注意力交出去。",
                "initiative_level": 0.31,
                "deferred_action_family": "none",
                "timing_window_min": 18,
                "relationship_weather": "guarded_residue",
                "attention_target": "self_then_counterpart",
                "nonverbal_signal": "resume_task",
                "channel": "none",
            }

        def _fake_passive_evolution_memory_update(*args, **kwargs):
            captured["behavior_action"] = kwargs["behavior_action"]
            captured["behavior_plan"] = kwargs["behavior_plan"]
            raise _StopAfterMemory

        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", return_value=_evolved_fixture()):
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                    with patch(
                        "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                        side_effect=_fake_behavior_action_from_state,
                    ):
                        with patch(
                            "amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update",
                            side_effect=_fake_passive_evolution_memory_update,
                        ):
                            with self.assertRaises(_StopAfterMemory):
                                _prepare_turn_runtime(
                                    state={"persona_state": {}},
                                    store=object(),
                                    turn_now_ts=123,
                                    prepared_turn=_prepared_turn_fixture(),
                                )

        self.assertEqual(str((captured["behavior_action"] or {}).get("action_target") or ""), "hold_own_rhythm")
        self.assertEqual(str((captured["behavior_action"] or {}).get("primary_motive") or ""), "preserve_self_rhythm")
        self.assertEqual(str((captured["behavior_plan"] or {}).get("kind") or ""), "self_activity_continue")

    def test_prepare_turn_runtime_rebuilds_reconsolidation_snapshot_from_runtime_action(self):
        captured: dict[str, object] = {}

        def _fake_behavior_action_from_state(**kwargs):
            return {
                "action_target": "hold_own_rhythm",
                "interaction_mode": "self_activity_hold",
                "primary_motive": "preserve_self_rhythm",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "先维持自己的节奏，不急着把全部注意力交出去。",
                "initiative_level": 0.31,
                "deferred_action_family": "none",
                "timing_window_min": 18,
                "relationship_weather": "guarded_residue",
                "attention_target": "self_then_counterpart",
                "nonverbal_signal": "resume_task",
                "channel": "none",
            }

        def _fake_build_reconsolidation_snapshot(**kwargs):
            captured["behavior_action"] = kwargs["behavior_action"]
            return {"behavior_mode": "runtime_final", "primary_motive": kwargs["behavior_action"]["primary_motive"]}

        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", return_value=_evolved_fixture()):
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update", return_value=False):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot", side_effect=lambda **kwargs: kwargs["relationship"]):
                            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary", return_value="summary"):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                    side_effect=_fake_behavior_action_from_state,
                                ):
                                    with patch(
                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                        return_value={"kind": "observe_only"},
                                    ):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                            return_value=[],
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                side_effect=_fake_build_reconsolidation_snapshot,
                                            ):
                                                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl", return_value=None):
                                                    result = _prepare_turn_runtime(
                                                        state={"persona_state": {}},
                                                        store=object(),
                                                        turn_now_ts=123,
                                                        prepared_turn=_prepared_turn_fixture(),
                                                    )

        self.assertEqual(str((captured["behavior_action"] or {}).get("action_target") or ""), "hold_own_rhythm")
        self.assertEqual(result["reconsolidation_snapshot"], {"behavior_mode": "runtime_final", "primary_motive": "preserve_self_rhythm"})


if __name__ == "__main__":
    unittest.main()
