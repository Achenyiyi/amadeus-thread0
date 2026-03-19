import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage

from amadeus_thread0.graph_parts.model_call_prepare import _prepare_model_call
from amadeus_thread0.memory_store import MemoryStore


class ModelCallPrepareTests(unittest.TestCase):
    def test_prepare_model_call_uses_pending_goal_for_continuation_generation_profile(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                state = {
                    "messages": [
                        AIMessage(content="你把方案发我，我看一下。"),
                        HumanMessage(content="继续"),
                    ],
                    "response_style_hint": "structured",
                    "science_mode": False,
                    "emotion_state": {"label": "neutral"},
                    "bond_state": {"trust": 0.62, "closeness": 0.58, "hurt": 0.04},
                    "allostasis_state": {"safety_need": 0.18, "autonomy_need": 0.42},
                    "counterpart_assessment": {"stance": "open", "respect_level": 0.72, "reciprocity": 0.70},
                    "behavior_policy": {"warmth": 0.54, "approach_vs_withdraw": 0.56},
                    "behavior_action": {"interaction_mode": "science_partner", "followup_intent": "active"},
                    "pending_user_goal": "请你先给一句判断，并分别给出实验设计和风险控制的结论。",
                    "pending_utterance_fragment": "先说实验设计这边，",
                    "worldline_focus": [],
                    "retrieved_context": {},
                    "current_event": {"kind": "user_utterance", "response_style_hint": "structured"},
                    "recent_events": [],
                }
                prepared = _prepare_model_call(state, store)
            finally:
                store.close()
        self.assertTrue(prepared["active_continuation"])
        self.assertEqual(prepared["chosen_generation_profile"].get("max_tokens"), 192)

    def test_prepare_model_call_generation_profile_uses_fresh_state_semantic_profile(self):
        fresh_profile = {
            "history_weight": 0.81,
            "presence_carry": 0.64,
            "active_categories": ["agency_style", "presence_style"],
            "summary_lines": ["最终行为已经沉进长期连续性。"],
        }
        generation_calls = []
        state = {
            "messages": [
                AIMessage(content="我刚刚是认真说的。"),
                HumanMessage(content="你现在怎么想？"),
            ],
            "response_style_hint": "natural",
            "science_mode": False,
            "emotion_state": {"label": "care"},
            "bond_state": {"trust": 0.7, "closeness": 0.68, "hurt": 0.02},
            "allostasis_state": {"safety_need": 0.16, "autonomy_need": 0.44},
            "counterpart_assessment": {"stance": "open", "respect_level": 0.75, "reciprocity": 0.73},
            "behavior_policy": {"warmth": 0.58, "approach_vs_withdraw": 0.54},
            "behavior_action": {"interaction_mode": "self_activity_reopen", "primary_motive": "gentle_recontact"},
            "semantic_narrative_profile": fresh_profile,
            "retrieved_context": {
                "semantic_self_narratives": [
                    {
                        "id": "retrieved-stale",
                        "text": "这是一条旧检索副本，不该驱动当前 generation profile。",
                    }
                ]
            },
            "worldline_focus": [],
            "current_event": {"kind": "user_utterance", "response_style_hint": "natural"},
            "recent_events": [],
            "pending_user_goal": "",
            "pending_utterance_fragment": "",
        }

        def _capture_generation_profile(**kwargs):
            generation_calls.append(dict(kwargs))
            return {}

        with patch("amadeus_thread0.graph_parts.model_call_prepare._build_task_prompt", return_value="prompt"):
            with patch(
                "amadeus_thread0.graph_parts.model_call_prepare._generation_profile",
                side_effect=_capture_generation_profile,
            ):
                prepared = _prepare_model_call(state, object())

        self.assertEqual(prepared["call_msgs"][0].content, "prompt")
        self.assertEqual(len(generation_calls), 1)
        self.assertEqual(generation_calls[0]["semantic_narrative_profile"], fresh_profile)


if __name__ == "__main__":
    unittest.main()
