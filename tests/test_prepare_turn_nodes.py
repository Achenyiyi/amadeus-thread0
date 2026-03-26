import unittest
from unittest.mock import patch

from amadeus_thread0.graph_parts.nodes import _node_prepare_turn


class PrepareTurnNodeTests(unittest.TestCase):
    def test_node_prepare_turn_prefers_runtime_event_and_carryover(self):
        prepared_turn = {
            "counterpart_trace": {},
            "persona_trace": {},
            "agenda_lifecycle_residue": {},
            "pending": "",
            "pending_user_goal": "",
            "science_mode": False,
            "response_style_hint": "natural",
            "appraisal": {},
            "current_event": {"kind": "user_utterance", "event_frame": "dialogue", "tags": []},
            "interaction_carryover": {},
            "recent_events": [],
        }
        runtime_state = {
            "current_event": {
                "kind": "user_utterance",
                "event_frame": "dialogue",
                "tags": [],
                "carryover_mode": "small_opening",
                "carryover_strength": 0.58,
            },
            "interaction_carryover": {
                "carryover_mode": "life_window",
                "strength": 0.58,
                "source": "retrieved_behavior_plan",
            },
            "retrieved": {},
            "relationship": {"stage": "friend", "notes": "", "affinity_score": 0.0, "trust_score": 0.0, "derived": True},
            "worldline_focus": [],
            "persona_state": {},
            "world_model_state": {},
            "evolution_state": {},
            "reconsolidation_snapshot": {},
            "emotion_state": {},
            "bond_state": {},
            "allostasis_state": {},
            "counterpart_assessment": {},
            "semantic_narrative_profile": {},
            "behavior_policy": {},
            "behavior_action": {},
            "behavior_plan": {},
            "behavior_agenda": [],
            "tsundere": 0.0,
        }

        with patch("amadeus_thread0.graph_parts.nodes._get_store", return_value=object()):
            with patch("amadeus_thread0.graph_parts.nodes._now_ts", return_value=123):
                with patch("amadeus_thread0.graph_parts.nodes._prepare_turn_context", return_value=prepared_turn):
                    with patch("amadeus_thread0.graph_parts.nodes._prepare_turn_runtime", return_value=runtime_state):
                        result = _node_prepare_turn({})

        self.assertEqual(str(result["current_event"].get("carryover_mode") or ""), "small_opening")
        self.assertEqual(str(result["interaction_carryover"].get("carryover_mode") or ""), "life_window")
        self.assertEqual(str(result["interaction_carryover"].get("source") or ""), "retrieved_behavior_plan")

    def test_node_prepare_turn_promotes_config_session_context(self):
        prepared_turn = {
            "counterpart_trace": {},
            "persona_trace": {},
            "agenda_lifecycle_residue": {},
            "pending": "",
            "pending_user_goal": "",
            "science_mode": False,
            "response_style_hint": "natural",
            "appraisal": {},
            "current_event": {"kind": "user_utterance", "event_frame": "dialogue", "tags": []},
            "interaction_carryover": {},
            "recent_events": [],
        }
        runtime_state = {
            "current_event": {},
            "interaction_carryover": {},
            "retrieved": {},
            "relationship": {"stage": "friend", "notes": "", "affinity_score": 0.0, "trust_score": 0.0, "derived": True},
            "worldline_focus": [],
            "persona_state": {},
            "world_model_state": {},
            "evolution_state": {},
            "reconsolidation_snapshot": {},
            "emotion_state": {},
            "bond_state": {},
            "allostasis_state": {},
            "counterpart_assessment": {},
            "semantic_narrative_profile": {},
            "behavior_policy": {},
            "behavior_action": {},
            "behavior_plan": {},
            "behavior_agenda": [],
            "tsundere": 0.0,
        }

        with patch("amadeus_thread0.graph_parts.nodes._get_store", return_value=object()):
            with patch("amadeus_thread0.graph_parts.nodes._now_ts", return_value=123):
                with patch("amadeus_thread0.graph_parts.nodes._prepare_turn_context", return_value=prepared_turn) as prepare_ctx:
                    with patch("amadeus_thread0.graph_parts.nodes._prepare_turn_runtime", return_value=runtime_state):
                        result = _node_prepare_turn(
                            {},
                            config={"configurable": {"thread_id": "thread-live", "user_id": "okabe", "checkpoint_id": "cp-7"}},
                        )

        session_context = prepare_ctx.call_args.kwargs["session_context"]
        self.assertEqual(session_context["thread_id"], "thread-live")
        self.assertEqual(session_context["turn_id"], "thread-live:123")
        self.assertEqual(session_context["turn_started_at"], 123)
        self.assertEqual(session_context["user_id"], "okabe")
        self.assertEqual(session_context["checkpoint_id"], "cp-7")
        self.assertEqual(result["session_context"]["thread_id"], "thread-live")
        self.assertEqual(result["session_context"]["turn_id"], "thread-live:123")


if __name__ == "__main__":
    unittest.main()
