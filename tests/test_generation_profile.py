import unittest

from amadeus_thread0.graph_parts.generation_profile import _generation_profile


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
                "self_directedness": 0.34,
            },
            "world_model_state": {},
            "behavior_action": {
                "interaction_mode": "companion_reply",
                "task_focus": "balanced",
                "followup_intent": "active",
                "attention_target": "counterpart_state",
            },
            "interaction_carryover": {},
            "semantic_narrative_profile": {},
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

    def test_long_term_rhythm_memory_keeps_daily_turn_measured_without_explicit_carryover(self):
        baseline = _generation_profile(**self._base_kwargs())
        profile = _generation_profile(
            **{
                **self._base_kwargs(),
                "behavior_policy": {
                    **self._base_kwargs()["behavior_policy"],
                    "self_directedness": 0.62,
                },
                "behavior_action": {
                    "interaction_mode": "companion_reply",
                    "task_focus": "balanced",
                    "followup_intent": "soft",
                    "attention_target": "counterpart_state",
                },
                "semantic_narrative_profile": {
                    "agency_drive": 0.68,
                    "rhythm_continuity": 0.82,
                    "presence_carry": 0.34,
                    "history_weight": 0.58,
                    "motive_snapshot": {
                        "rhythm_style": {
                            "primary_motive": "preserve_self_rhythm",
                            "motive_tension": "self_rhythm_vs_contact",
                        }
                    },
                },
            }
        )
        self.assertIsNone(baseline.get("max_tokens"))
        self.assertIsNone(baseline.get("temperature"))
        self.assertLessEqual(int(profile.get("max_tokens") or 999), 148)
        self.assertLessEqual(float(profile.get("top_p") or 1.0), 0.78)
        self.assertIsNotNone(profile.get("temperature"))

    def test_guarded_relationship_weather_keeps_sampling_measured(self):
        profile = _generation_profile(
            **{
                **self._base_kwargs(),
                "user_text": "我知道刚才那句有点过界，但我还是想和你好好说。",
                "emotion_state": {"label": "hurt"},
                "bond_state": {"trust": 0.64, "closeness": 0.60, "hurt": 0.20},
                "behavior_action": {
                    "interaction_mode": "relationship_sensitive",
                    "task_focus": "balanced",
                    "followup_intent": "soft",
                    "attention_target": "counterpart_state",
                    "relationship_weather": "guarded_residue",
                },
                "interaction_carryover": {
                    "carryover_mode": "quiet_recontact",
                    "strength": 0.56,
                    "relationship_weather": "guarded_residue",
                },
            }
        )
        self.assertLessEqual(int(profile.get("max_tokens") or 999), 148)
        self.assertLessEqual(float(profile.get("temperature") or 1.0), 0.22)
        self.assertLessEqual(float(profile.get("top_p") or 1.0), 0.78)
        self.assertIsNotNone(profile.get("frequency_penalty"))

    def test_warm_and_repair_relationship_weather_keep_nondefault_sampling(self):
        warm_profile = _generation_profile(
            **{
                **self._base_kwargs(),
                "user_text": "现在心里顺一点了，我又想和你说话。",
                "behavior_action": {
                    "interaction_mode": "companion_reply",
                    "task_focus": "balanced",
                    "followup_intent": "soft",
                    "attention_target": "counterpart_state",
                    "relationship_weather": "warm_residue",
                },
                "interaction_carryover": {
                    "carryover_mode": "small_opening",
                    "strength": 0.52,
                    "relationship_weather": "warm_residue",
                },
            }
        )
        repair_profile = _generation_profile(
            **{
                **self._base_kwargs(),
                "user_text": "别一下子当什么都没发生，我只是想继续把话说完。",
                "behavior_action": {
                    "interaction_mode": "relationship_sensitive",
                    "task_focus": "balanced",
                    "followup_intent": "soft",
                    "attention_target": "counterpart_state",
                    "relationship_weather": "repair_residue",
                },
                "interaction_carryover": {
                    "carryover_mode": "brief_presence",
                    "strength": 0.54,
                    "relationship_weather": "repair_residue",
                },
            }
        )
        self.assertIsNotNone(warm_profile.get("temperature"))
        self.assertIsNotNone(repair_profile.get("temperature"))
        self.assertLessEqual(int(repair_profile.get("max_tokens") or 999), int(warm_profile.get("max_tokens") or 0))
        self.assertGreaterEqual(float(warm_profile.get("top_p") or 0.0), float(repair_profile.get("top_p") or 1.0))

    def test_busy_not_disrespectful_scene_prevents_default_sampling(self):
        baseline = _generation_profile(**self._base_kwargs())
        profile = _generation_profile(
            **{
                **self._base_kwargs(),
                "user_text": "你刚才是在忙吗？",
                "counterpart_assessment": {
                    "boundary_pressure": 0.12,
                    "stance": "open",
                    "scene": "busy_not_disrespectful",
                },
            }
        )
        self.assertIsNone(baseline.get("max_tokens"))
        self.assertIsNotNone(profile.get("max_tokens"))
        self.assertLessEqual(int(profile.get("max_tokens") or 999), 156)
        self.assertLessEqual(float(profile.get("temperature") or 1.0), 0.22)
        self.assertLessEqual(float(profile.get("top_p") or 1.0), 0.80)

    def test_repair_attempt_scene_stays_tighter_than_care_bid(self):
        repair_profile = _generation_profile(
            **{
                **self._base_kwargs(),
                "user_text": "我不是想随便糊弄过去，我是认真来跟你道歉的。",
                "emotion_state": {"label": "hurt"},
                "bond_state": {"trust": 0.6, "closeness": 0.58, "hurt": 0.18},
                "counterpart_assessment": {
                    "boundary_pressure": 0.3,
                    "stance": "guarded",
                    "scene": "repair_attempt",
                },
                "behavior_action": {
                    "interaction_mode": "relationship_sensitive",
                    "task_focus": "balanced",
                    "followup_intent": "soft",
                    "attention_target": "counterpart_state",
                },
            }
        )
        care_profile = _generation_profile(
            **{
                **self._base_kwargs(),
                "user_text": "我就是突然有点想靠近你一点，所以来找你说话。",
                "emotion_state": {"label": "care"},
                "counterpart_assessment": {
                    "boundary_pressure": 0.1,
                    "stance": "open",
                    "scene": "care_bid",
                },
                "behavior_action": {
                    "interaction_mode": "companion_reply",
                    "task_focus": "balanced",
                    "followup_intent": "soft",
                    "attention_target": "counterpart_state",
                },
            }
        )
        self.assertIsNotNone(repair_profile.get("temperature"))
        self.assertIsNotNone(care_profile.get("temperature"))
        self.assertLessEqual(int(repair_profile.get("max_tokens") or 999), int(care_profile.get("max_tokens") or 0))
        self.assertLessEqual(float(repair_profile.get("top_p") or 1.0), float(care_profile.get("top_p") or 0.0))
        self.assertLessEqual(float(repair_profile.get("temperature") or 1.0), float(care_profile.get("temperature") or 0.0))

    def test_friction_scene_forces_measured_nondefault_sampling(self):
        profile = _generation_profile(
            **{
                **self._base_kwargs(),
                "user_text": "我知道你现在对我那句还不太高兴，但我不想装作没发生。",
                "emotion_state": {"label": "stress"},
                "bond_state": {"trust": 0.5, "closeness": 0.54, "hurt": 0.16},
                "counterpart_assessment": {
                    "boundary_pressure": 0.32,
                    "stance": "watchful",
                    "scene": "friction",
                },
                "behavior_action": {
                    "interaction_mode": "relationship_sensitive",
                    "task_focus": "balanced",
                    "followup_intent": "soft",
                    "attention_target": "counterpart_state",
                },
            }
        )
        self.assertLessEqual(int(profile.get("max_tokens") or 999), 144)
        self.assertLessEqual(float(profile.get("temperature") or 1.0), 0.20)
        self.assertLessEqual(float(profile.get("top_p") or 1.0), 0.76)
        self.assertIsNotNone(profile.get("frequency_penalty"))


if __name__ == "__main__":
    unittest.main()
