import unittest

from amadeus_thread0.graph import _generation_profile


class GenerationProfileRhythmTests(unittest.TestCase):
    def _base_kwargs(self) -> dict:
        return {
            "response_style_hint": "natural",
            "science_mode": False,
            "continuation_mode": False,
            "user_text": "你刚刚在忙什么？",
            "runtime_mode": "regression",
            "turn_index": 12,
            "recent_assistant_texts": ["刚才我在看一点东西。"],
            "current_event": {"kind": "user_utterance"},
            "emotion_state": {"label": "neutral"},
            "bond_state": {"trust": 0.68, "closeness": 0.66, "hurt": 0.02},
            "allostasis_state": {"cognitive_budget": 0.74, "safety_need": 0.18},
            "counterpart_assessment": {"boundary_pressure": 0.12},
            "behavior_policy": {
                "reply_length_bias": 0.52,
                "warmth": 0.62,
                "sharpness": 0.42,
                "approach_vs_withdraw": 0.58,
            },
            "world_model_state": {},
            "behavior_action": {
                "interaction_mode": "companion_reply",
                "task_focus": "balanced",
                "followup_intent": "active",
                "attention_target": "counterpart_state",
            },
            "interaction_carryover": {},
        }

    def test_self_activity_reopen_caps_generation_span(self):
        baseline = _generation_profile(**self._base_kwargs())
        focused = _generation_profile(
            **{
                **self._base_kwargs(),
                "world_model_state": {"self_activity_momentum": 0.78},
                "behavior_action": {
                    "interaction_mode": "self_activity_reopen",
                    "task_focus": "high",
                    "followup_intent": "soft",
                    "attention_target": "self_then_counterpart",
                },
                "interaction_carryover": {
                    "carryover_mode": "own_rhythm",
                    "strength": 0.74,
                },
            }
        )
        self.assertIsNone(baseline.get("max_tokens"))
        self.assertIsNone(baseline.get("temperature"))
        self.assertIsNone(baseline.get("top_p"))
        self.assertIsNone(baseline.get("frequency_penalty"))
        self.assertIsNone(baseline.get("presence_penalty"))
        self.assertLessEqual(int(focused.get("max_tokens") or 999), 152)
        self.assertIsNotNone(focused.get("top_p"))
        self.assertIsNotNone(focused.get("temperature"))

    def test_followup_none_keeps_user_turn_shorter(self):
        profile = _generation_profile(
            **{
                **self._base_kwargs(),
                "user_text": "嗯，我知道了。",
                "behavior_action": {
                    "interaction_mode": "companion_reply",
                    "task_focus": "balanced",
                    "followup_intent": "none",
                    "attention_target": "counterpart_state",
                },
            }
        )
        self.assertLessEqual(int(profile.get("max_tokens") or 999), 136)
        self.assertLessEqual(float(profile.get("top_p") or 1.0), 0.80)

    def test_shared_window_carryover_limits_sprawl(self):
        baseline = _generation_profile(**self._base_kwargs())
        profile = _generation_profile(
            **{
                **self._base_kwargs(),
                "user_text": "你现在想不想顺便聊聊刚才那件事？",
                "behavior_action": {
                    "interaction_mode": "companion_reply",
                    "task_focus": "light",
                    "followup_intent": "soft",
                    "attention_target": "shared_window",
                },
                "interaction_carryover": {
                    "carryover_mode": "shared_window",
                    "strength": 0.58,
                },
            }
        )
        self.assertIsNone(baseline.get("max_tokens"))
        self.assertIsNone(baseline.get("top_p"))
        self.assertLessEqual(int(profile.get("max_tokens") or 999), 176)
        self.assertIsNotNone(profile.get("top_p"))

    def test_life_window_carryover_limits_sprawl_more_gently_than_task_window(self):
        task_profile = _generation_profile(
            **{
                **self._base_kwargs(),
                "user_text": "你刚才是不是还记着那件得处理的事？",
                "behavior_action": {
                    "interaction_mode": "companion_reply",
                    "task_focus": "high",
                    "followup_intent": "soft",
                    "attention_target": "shared_task",
                },
                "interaction_carryover": {
                    "carryover_mode": "task_window",
                    "strength": 0.56,
                },
            }
        )
        life_profile = _generation_profile(
            **{
                **self._base_kwargs(),
                "user_text": "你刚才是不是还惦记着我提过的那点小事？",
                "behavior_action": {
                    "interaction_mode": "companion_reply",
                    "task_focus": "light",
                    "followup_intent": "soft",
                    "attention_target": "counterpart_state",
                },
                "interaction_carryover": {
                    "carryover_mode": "life_window",
                    "strength": 0.56,
                },
            }
        )
        self.assertLessEqual(int(task_profile.get("max_tokens") or 999), 176)
        self.assertLessEqual(int(life_profile.get("max_tokens") or 999), 192)
        self.assertGreater(int(life_profile.get("max_tokens") or 0), int(task_profile.get("max_tokens") or 0))
        self.assertGreaterEqual(float(life_profile.get("top_p") or 0.0), float(task_profile.get("top_p") or 0.0))

    def test_plain_natural_turn_uses_model_default_sampling(self):
        profile = _generation_profile(**self._base_kwargs())
        self.assertIsNone(profile.get("temperature"))
        self.assertIsNone(profile.get("top_p"))
        self.assertIsNone(profile.get("frequency_penalty"))
        self.assertIsNone(profile.get("presence_penalty"))


if __name__ == "__main__":
    unittest.main()
