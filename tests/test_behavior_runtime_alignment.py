import unittest

from amadeus_thread0.graph_parts.behavior_runtime import _behavior_action_from_state


class BehaviorRuntimeAlignmentTests(unittest.TestCase):
    def test_boundary_promotion_realigns_interaction_mode(self):
        action = _behavior_action_from_state(
            current_event={
                "kind": "user_utterance",
                "text": "我知道你不太舒服，但我还是想继续靠近你。",
                "tags": [],
            },
            response_style_hint="natural",
            user_text="我知道你不太舒服，但我还是想继续靠近你。",
            science_mode=False,
            emotion_state={"label": "hurt"},
            bond_state={
                "trust": 0.62,
                "closeness": 0.60,
                "hurt": 0.20,
                "irritation": 0.06,
            },
            allostasis_state={
                "autonomy_need": 0.30,
                "safety_need": 0.48,
                "cognitive_budget": 0.70,
            },
            counterpart_assessment={
                "stance": "watchful",
                "scene": "friction",
                "boundary_pressure": 0.34,
                "reliability_read": 0.58,
            },
            semantic_narrative_profile={
                "boundary_residue": 0.62,
                "selfhood_integrity": 0.58,
                "tension_residue": 0.46,
                "bond_depth": 0.48,
                "presence_carry": 0.36,
            },
            behavior_policy={
                "warmth": 0.56,
                "initiative": 0.54,
                "reply_length_bias": 0.48,
                "approach_vs_withdraw": 0.50,
                "boundary_assertiveness": 0.52,
                "self_directedness": 0.36,
                "equality_guard": 0.42,
            },
            world_model_state={
                "presence_residue": 0.20,
                "ambient_resonance": 0.08,
                "self_activity_momentum": 0.16,
                "companionship_pull": 0.42,
                "task_pull": 0.08,
            },
            interaction_carryover={},
            prior_emotion_state={},
            prior_bond_state={},
            prior_allostasis_state={},
            prior_counterpart_assessment={},
            appraisal={},
        )
        self.assertEqual(str(action.get("action_target") or ""), "protect_relationship_boundary")
        self.assertEqual(str(action.get("interaction_mode") or ""), "relationship_sensitive")
        self.assertEqual(str(action.get("attention_target") or ""), "relationship_boundary")
        self.assertEqual(str(action.get("initiative_shape") or ""), "boundary")
        self.assertEqual(str(action.get("primary_motive") or ""), "protect_boundary")

    def test_repair_residue_realigns_generic_reply_into_low_pressure_hold(self):
        action = _behavior_action_from_state(
            current_event={
                "kind": "user_utterance",
                "text": "之前那件事我一直记着，我不想装作没发生。我们能慢慢聊吗？",
                "tags": ["repair"],
            },
            response_style_hint="natural",
            user_text="之前那件事我一直记着，我不想装作没发生。我们能慢慢聊吗？",
            science_mode=False,
            emotion_state={"label": "hurt"},
            bond_state={
                "trust": 0.60,
                "closeness": 0.59,
                "hurt": 0.14,
                "irritation": 0.08,
            },
            allostasis_state={
                "autonomy_need": 0.38,
                "safety_need": 0.42,
                "cognitive_budget": 0.70,
            },
            counterpart_assessment={
                "stance": "watchful",
                "scene": "repair_attempt",
                "boundary_pressure": 0.18,
                "reliability_read": 0.60,
            },
            semantic_narrative_profile={
                "repair_residue": 0.76,
                "commitment_carry": 0.64,
                "bond_depth": 0.62,
                "presence_carry": 0.44,
                "continuity_depth": 0.68,
                "tension_residue": 0.42,
            },
            behavior_policy={
                "warmth": 0.58,
                "initiative": 0.50,
                "reply_length_bias": 0.46,
                "approach_vs_withdraw": 0.50,
                "boundary_assertiveness": 0.42,
                "self_directedness": 0.34,
                "equality_guard": 0.42,
            },
            world_model_state={
                "presence_residue": 0.30,
                "ambient_resonance": 0.10,
                "self_activity_momentum": 0.16,
                "companionship_pull": 0.58,
                "task_pull": 0.08,
            },
            interaction_carryover={
                "relationship_weather": "repair_residue",
                "strength": 0.62,
                "mode": "quiet_recontact",
            },
            prior_emotion_state={},
            prior_bond_state={},
            prior_allostasis_state={},
            prior_counterpart_assessment={},
            appraisal={},
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "low_pressure_support")
        self.assertEqual(str(action.get("action_target") or ""), "low_pressure_hold")
        self.assertEqual(str(action.get("initiative_shape") or ""), "hold")
        self.assertEqual(str(action.get("primary_motive") or ""), "support_without_pressure")
        self.assertEqual(str(action.get("followup_intent") or ""), "soft")

    def test_life_window_user_turn_keeps_continuity_motive(self):
        action = _behavior_action_from_state(
            current_event={
                "kind": "user_utterance",
                "text": "我刚刚忙完，突然想起你之前提醒我的那件生活小事。",
                "tags": [],
            },
            response_style_hint="natural",
            user_text="我刚刚忙完，突然想起你之前提醒我的那件生活小事。",
            science_mode=False,
            emotion_state={"label": "calm"},
            bond_state={
                "trust": 0.68,
                "closeness": 0.66,
                "hurt": 0.04,
                "irritation": 0.02,
            },
            allostasis_state={
                "autonomy_need": 0.34,
                "safety_need": 0.28,
                "cognitive_budget": 0.72,
            },
            counterpart_assessment={
                "stance": "open",
                "scene": "daily_contact",
                "boundary_pressure": 0.08,
                "reliability_read": 0.74,
            },
            semantic_narrative_profile={
                "commitment_carry": 0.76,
                "continuity_depth": 0.74,
                "bond_depth": 0.66,
                "presence_carry": 0.48,
            },
            behavior_policy={
                "warmth": 0.62,
                "initiative": 0.56,
                "reply_length_bias": 0.44,
                "approach_vs_withdraw": 0.56,
                "boundary_assertiveness": 0.28,
                "self_directedness": 0.38,
                "equality_guard": 0.40,
            },
            world_model_state={
                "presence_residue": 0.24,
                "ambient_resonance": 0.12,
                "self_activity_momentum": 0.18,
                "companionship_pull": 0.58,
                "task_pull": 0.12,
            },
            interaction_carryover={
                "carryover_mode": "life_window",
                "strength": 0.68,
                "relationship_weather": "warm_residue",
                "attention_target": "counterpart_state",
            },
            prior_emotion_state={},
            prior_bond_state={},
            prior_allostasis_state={},
            prior_counterpart_assessment={},
            appraisal={},
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "companion_reply")
        self.assertEqual(str(action.get("action_target") or ""), "respond_now")
        self.assertEqual(str(action.get("primary_motive") or ""), "honor_continuity")
        self.assertIn("生活上的惦记", str(action.get("goal_frame") or ""))

    def test_high_commitment_idle_reachout_uses_continuity_motive(self):
        action = _behavior_action_from_state(
            current_event={
                "kind": "time_idle",
                "tags": ["time_idle"],
                "idle_minutes": 120,
            },
            response_style_hint="natural",
            user_text="",
            science_mode=False,
            emotion_state={"label": "calm"},
            bond_state={
                "trust": 0.70,
                "closeness": 0.68,
                "hurt": 0.02,
                "irritation": 0.01,
            },
            allostasis_state={
                "autonomy_need": 0.30,
                "safety_need": 0.24,
                "cognitive_budget": 0.74,
            },
            counterpart_assessment={
                "stance": "open",
                "scene": "daily_contact",
                "boundary_pressure": 0.04,
                "reliability_read": 0.78,
            },
            semantic_narrative_profile={
                "commitment_carry": 0.82,
                "continuity_depth": 0.80,
                "bond_depth": 0.68,
                "presence_carry": 0.56,
            },
            behavior_policy={
                "warmth": 0.62,
                "initiative": 0.58,
                "reply_length_bias": 0.42,
                "approach_vs_withdraw": 0.58,
                "boundary_assertiveness": 0.24,
                "self_directedness": 0.40,
                "equality_guard": 0.42,
            },
            world_model_state={
                "presence_residue": 0.22,
                "ambient_resonance": 0.08,
                "self_activity_momentum": 0.24,
                "companionship_pull": 0.62,
                "task_pull": 0.10,
            },
            interaction_carryover={},
            prior_emotion_state={},
            prior_bond_state={},
            prior_allostasis_state={},
            prior_counterpart_assessment={},
            appraisal={},
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "proactive_checkin")
        self.assertEqual(str(action.get("action_target") or ""), "reach_out_now")
        self.assertEqual(str(action.get("primary_motive") or ""), "honor_continuity")
        self.assertIn("没散掉的惦记", str(action.get("goal_frame") or ""))


if __name__ == "__main__":
    unittest.main()
