import unittest
from unittest.mock import patch

from amadeus_thread0.graph_parts.nodes import _node_prepare_turn


class NodePrepareTurnTests(unittest.TestCase):
    def test_node_prepare_turn_does_not_let_empty_runtime_mappings_clobber_prepared_values(self):
        prepared_turn = {
            "counterpart_trace": {},
            "persona_trace": {},
            "agenda_lifecycle_residue": {},
            "pending": "",
            "pending_user_goal": "",
            "science_mode": False,
            "response_style_hint": "natural",
            "appraisal": {},
            "current_event": {
                "kind": "user_utterance",
                "text": "我回来了。",
                "effective_text": "我回来了。",
                "carryover_mode": "small_opening",
                "created_at": 123,
            },
            "interaction_carryover": {
                "carryover_mode": "life_window",
                "strength": 0.58,
                "relationship_weather": "warm_residue",
            },
            "recent_events": [],
        }
        runtime_state = {
            "current_event": {},
            "interaction_carryover": {},
            "retrieved": {},
            "relationship": {"stage": "friend"},
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
            "tsundere": 0.4,
        }
        state = {
            "persona_state": {},
            "recent_events": [],
            "evidence_pack": [],
            "last_external_tools": [],
            "toolset_unlocks": {},
        }

        with patch("amadeus_thread0.graph_parts.nodes._get_store", return_value=object()):
            with patch("amadeus_thread0.graph_parts.nodes._now_ts", return_value=123):
                with patch(
                    "amadeus_thread0.graph_parts.nodes._prepare_turn_context",
                    return_value=prepared_turn,
                ):
                    with patch(
                        "amadeus_thread0.graph_parts.nodes._prepare_turn_runtime",
                        return_value=runtime_state,
                    ):
                        result = _node_prepare_turn(state)

        self.assertEqual(str((result.get("current_event") or {}).get("kind") or ""), "user_utterance")
        self.assertEqual(str((result.get("current_event") or {}).get("carryover_mode") or ""), "small_opening")
        self.assertEqual(str((result.get("interaction_carryover") or {}).get("carryover_mode") or ""), "life_window")
        self.assertAlmostEqual(float((result.get("interaction_carryover") or {}).get("strength") or 0.0), 0.58, places=3)

    def test_node_prepare_turn_rebuilds_recent_events_from_runtime_current_event(self):
        prepared_turn = {
            "counterpart_trace": {},
            "persona_trace": {},
            "agenda_lifecycle_residue": {},
            "pending": "",
            "pending_user_goal": "",
            "science_mode": False,
            "response_style_hint": "natural",
            "appraisal": {},
            "current_event": {
                "kind": "user_utterance",
                "text": "我回来了。",
                "effective_text": "我回来了。",
                "created_at": 123,
            },
            "interaction_carryover": {},
            "recent_events": [
                {
                    "kind": "user_utterance",
                    "text": "我回来了。",
                    "effective_text": "我回来了。",
                    "created_at": 123,
                }
            ],
        }
        runtime_state = {
            "current_event": {
                "kind": "user_utterance",
                "text": "我回来了。",
                "effective_text": "我回来了。",
                "carryover_mode": "small_opening",
                "presence_residue": 0.34,
                "created_at": 123,
            },
            "interaction_carryover": {"carryover_mode": "life_window", "strength": 0.58},
            "retrieved": {},
            "relationship": {"stage": "friend"},
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
            "tsundere": 0.4,
        }
        state = {
            "persona_state": {},
            "recent_events": [
                {
                    "kind": "user_utterance",
                    "text": "上一次的事。",
                    "effective_text": "上一次的事。",
                    "created_at": 100,
                }
            ],
            "evidence_pack": [],
            "last_external_tools": [],
            "toolset_unlocks": {},
        }

        with patch("amadeus_thread0.graph_parts.nodes._get_store", return_value=object()):
            with patch("amadeus_thread0.graph_parts.nodes._now_ts", return_value=123):
                with patch(
                    "amadeus_thread0.graph_parts.nodes._prepare_turn_context",
                    return_value=prepared_turn,
                ):
                    with patch(
                        "amadeus_thread0.graph_parts.nodes._prepare_turn_runtime",
                        return_value=runtime_state,
                    ):
                        result = _node_prepare_turn(state)

        recent_events = result.get("recent_events") if isinstance(result.get("recent_events"), list) else []
        self.assertEqual(len(recent_events), 2)
        self.assertEqual(str(recent_events[-1].get("carryover_mode") or ""), "small_opening")
        self.assertAlmostEqual(float(recent_events[-1].get("presence_residue") or 0.0), 0.34, places=3)
        self.assertEqual(str((result.get("current_event") or {}).get("carryover_mode") or ""), "small_opening")

    def test_node_prepare_turn_uses_runtime_reconsolidation_snapshot(self):
        prepared_turn = {
            "counterpart_trace": {},
            "persona_trace": {},
            "agenda_lifecycle_residue": {},
            "pending": "",
            "pending_user_goal": "",
            "science_mode": False,
            "response_style_hint": "natural",
            "appraisal": {},
            "current_event": {
                "kind": "user_utterance",
                "text": "你刚刚那句话我记住了。",
                "effective_text": "你刚刚那句话我记住了。",
                "created_at": 456,
            },
            "interaction_carryover": {},
            "recent_events": [],
        }
        final_snapshot = {
            "event_kind": "user_utterance",
            "interaction_frame": "relationship",
            "primary_motive": "gentle_recontact",
            "motive_tension": "self_rhythm_vs_contact",
            "goal_frame": "先从自己的节奏里回头，留一个不压迫对方的小开口。",
            "behavior_consequence": {
                "kind": "leave_small_opening",
                "summary": "她回头了，但只留了一个轻一点的小开口。",
            },
            "agenda_lifecycle_consequence": {
                "kind": "released_to_self_activity",
                "carryover_mode": "own_rhythm",
            },
        }
        runtime_state = {
            "current_event": prepared_turn["current_event"],
            "interaction_carryover": {},
            "retrieved": {},
            "relationship": {"stage": "friend"},
            "worldline_focus": [],
            "persona_state": {},
            "world_model_state": {},
            "evolution_state": {},
            "reconsolidation_snapshot": final_snapshot,
            "emotion_state": {},
            "bond_state": {},
            "allostasis_state": {},
            "counterpart_assessment": {},
            "semantic_narrative_profile": {},
            "behavior_policy": {},
            "behavior_action": {},
            "behavior_plan": {},
            "behavior_agenda": [],
            "tsundere": 0.4,
        }
        state = {
            "persona_state": {},
            "recent_events": [],
            "evidence_pack": [],
            "last_external_tools": [],
            "toolset_unlocks": {},
        }

        with patch("amadeus_thread0.graph_parts.nodes._get_store", return_value=object()):
            with patch("amadeus_thread0.graph_parts.nodes._now_ts", return_value=456):
                with patch(
                    "amadeus_thread0.graph_parts.nodes._prepare_turn_context",
                    return_value=prepared_turn,
                ):
                    with patch(
                        "amadeus_thread0.graph_parts.nodes._prepare_turn_runtime",
                        return_value=runtime_state,
                    ):
                        result = _node_prepare_turn(state)

        self.assertEqual(result.get("reconsolidation_snapshot"), final_snapshot)
        snapshot = result.get("reconsolidation_snapshot") if isinstance(result.get("reconsolidation_snapshot"), dict) else {}
        self.assertEqual(str((snapshot.get("behavior_consequence") or {}).get("kind") or ""), "leave_small_opening")
        self.assertEqual(str((snapshot.get("agenda_lifecycle_consequence") or {}).get("carryover_mode") or ""), "own_rhythm")

    def test_node_prepare_turn_persists_runtime_semantic_narrative_profile(self):
        prepared_turn = {
            "counterpart_trace": {},
            "persona_trace": {},
            "agenda_lifecycle_residue": {},
            "pending": "",
            "pending_user_goal": "",
            "science_mode": False,
            "response_style_hint": "natural",
            "appraisal": {},
            "current_event": {
                "kind": "user_utterance",
                "text": "你还记得刚才那件事吗？",
                "effective_text": "你还记得刚才那件事吗？",
                "created_at": 789,
            },
            "interaction_carryover": {},
            "recent_events": [],
        }
        fresh_profile = {
            "history_weight": 0.78,
            "presence_carry": 0.62,
            "summary_lines": ["她会把刚刚真正发生过的行动沉到长期连续性里。"],
            "anchor_lines": ["这种连续性来自已经写回的最终行为，而不是旧检索副本。"],
            "active_categories": ["agency_style", "presence_style"],
        }
        runtime_state = {
            "current_event": prepared_turn["current_event"],
            "interaction_carryover": {},
            "retrieved": {
                "semantic_self_narratives": [
                    {
                        "id": "retrieved-stale",
                        "text": "这只是检索阶段遗留的旧叙事。",
                    }
                ]
            },
            "relationship": {"stage": "friend"},
            "worldline_focus": [],
            "persona_state": {},
            "world_model_state": {},
            "evolution_state": {},
            "reconsolidation_snapshot": {},
            "emotion_state": {},
            "bond_state": {},
            "allostasis_state": {},
            "counterpart_assessment": {},
            "semantic_narrative_profile": fresh_profile,
            "behavior_policy": {},
            "behavior_action": {},
            "behavior_plan": {},
            "behavior_agenda": [],
            "tsundere": 0.4,
        }
        state = {
            "semantic_narrative_profile": {
                "history_weight": 0.12,
                "summary_lines": ["这是一份上一轮遗留的旧 profile。"],
            },
            "recent_events": [],
            "evidence_pack": [],
            "last_external_tools": [],
            "toolset_unlocks": {},
        }

        with patch("amadeus_thread0.graph_parts.nodes._get_store", return_value=object()):
            with patch("amadeus_thread0.graph_parts.nodes._now_ts", return_value=789):
                with patch(
                    "amadeus_thread0.graph_parts.nodes._prepare_turn_context",
                    return_value=prepared_turn,
                ):
                    with patch(
                        "amadeus_thread0.graph_parts.nodes._prepare_turn_runtime",
                        return_value=runtime_state,
                    ):
                        result = _node_prepare_turn(state)

        self.assertEqual(result.get("semantic_narrative_profile"), fresh_profile)
        self.assertEqual(
            result.get("retrieved_context", {}).get("semantic_self_narratives", [])[0].get("id"),
            "retrieved-stale",
        )


if __name__ == "__main__":
    unittest.main()
