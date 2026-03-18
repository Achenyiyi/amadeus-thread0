import unittest
from unittest.mock import patch

from amadeus_thread0.graph_parts.prepare_turn_runtime import _prepare_turn_runtime


class _StopAfterPlan(RuntimeError):
    pass


class PrepareTurnRuntimeTests(unittest.TestCase):
    def test_prepare_turn_runtime_passes_world_model_state_into_behavior_plan(self):
        captured: dict[str, object] = {}

        def _fake_behavior_plan_from_action(current_event, behavior_action, world_model_state=None):
            captured["current_event"] = current_event
            captured["behavior_action"] = behavior_action
            captured["world_model_state"] = world_model_state
            raise _StopAfterPlan

        prepared_turn = {
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

        evolved = {
            "world_model_state": {
                "self_activity_momentum": 0.74,
                "presence_residue": 0.34,
                "ambient_resonance": 0.28,
            },
            "evolution_state": {},
            "emotion_state": {"label": "neutral"},
            "bond_state": prepared_turn["seed_bond_state"],
            "allostasis_state": prepared_turn["seed_allostasis_state"],
            "counterpart_assessment": prepared_turn["seed_counterpart_assessment"],
            "behavior_policy": {},
            "behavior_action": {},
            "reconsolidation_snapshot": {},
        }

        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", return_value=evolved):
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update", return_value=False):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot", side_effect=lambda **kwargs: kwargs["relationship"]):
                            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary", return_value="summary"):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                    return_value={
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
                                    },
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
        self.assertEqual(
            captured["world_model_state"],
            {
                "self_activity_momentum": 0.74,
                "presence_residue": 0.34,
                "ambient_resonance": 0.28,
            },
        )


if __name__ == "__main__":
    unittest.main()
