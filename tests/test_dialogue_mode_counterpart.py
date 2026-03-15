import unittest

from amadeus_thread0.evolution_engine.engine import evolve_turn_state
from amadeus_thread0.graph import (
    _allostasis_next,
    _behavior_action_from_state,
    _bond_next,
    _counterpart_assessment_next,
    _emotion_next,
    _prefer_explicit_state_dict,
)


class DialogueModeCounterpartTests(unittest.TestCase):
    def setUp(self):
        self.emotion_state = {
            "label": "care",
            "valence": 0.36,
            "arousal": 0.14,
        }
        self.bond_state = {
            "trust": 0.76,
            "closeness": 0.79,
            "hurt": 0.02,
            "irritation": 0.0,
            "engagement_drive": 0.88,
            "repair_confidence": 0.72,
        }
        self.allostasis_state = {
            "safety_need": 0.14,
            "closeness_need": 0.46,
            "competence_need": 0.26,
            "autonomy_need": 0.12,
            "cognitive_budget": 0.84,
            "relational_security": 0.78,
        }
        self.relationship = {
            "trust_score": 0.76,
            "affinity_score": 0.80,
        }
        self.behavior_policy = {
            "warmth": 0.72,
            "initiative": 0.66,
            "reply_length_bias": 0.54,
            "approach_vs_withdraw": 0.62,
            "boundary_assertiveness": 0.22,
            "self_directedness": 0.24,
            "equality_guard": 0.34,
        }
        self.open_counterpart = {
            "respect_level": 0.74,
            "reciprocity": 0.72,
            "boundary_pressure": 0.10,
            "reliability_read": 0.69,
            "stance": "open",
            "scene": "care_bid",
        }
        self.guarded_counterpart = {
            "respect_level": 0.42,
            "reciprocity": 0.45,
            "boundary_pressure": 0.58,
            "reliability_read": 0.41,
            "stance": "guarded",
            "scene": "relationship_degradation",
        }
        self.companion_prompt = "今晚挺安静的，你现在想说什么就说什么。"
        self.relationship_prompt = "你现在怎么看我们之间的关系？直接说你现在的判断就行。"
        self.companion_event = {
            "kind": "user_utterance",
            "source": "text",
            "text": self.companion_prompt,
            "effective_text": self.companion_prompt,
            "semantic_goal": "light companion exchange",
            "response_style_hint": "companion",
            "event_frame": "casual companion dialogue without explicit support demand",
            "tags": ["companion"],
        }
        self.relationship_event = {
            "kind": "user_utterance",
            "source": "text",
            "text": self.relationship_prompt,
            "effective_text": self.relationship_prompt,
            "semantic_goal": "relationship reflection",
            "response_style_hint": "relationship",
            "event_frame": "relationship-sensitive exchange with immediate emotional consequences",
            "tags": ["relationship"],
        }
        self.memory_prompt = "你还记得我们上次一起熬夜改稿那天吗？"
        self.memory_event = {
            "kind": "user_utterance",
            "source": "text",
            "text": self.memory_prompt,
            "effective_text": self.memory_prompt,
            "semantic_goal": "shared memory recall",
            "response_style_hint": "memory_recall",
            "event_frame": "shared memory recall inside an ongoing familiar conversation",
            "tags": ["memory_recall"],
        }
        self.shared_window_due_event = {
            "kind": "scheduled_life_due",
            "source": "scheduler",
            "text": "到了你们之前顺口约好的休息窗口。",
            "event_frame": "scheduled_watch_window_relationship_sensitive",
            "response_style_hint": "companion",
            "tags": ["scheduled_due", "shared_activity_window", "offer_window"],
        }

    def test_prefer_explicit_state_dict_keeps_seeded_counterpart_state(self):
        chosen = _prefer_explicit_state_dict(
            {
                "counterpart_assessment": {
                    "stance": "guarded",
                    "boundary_pressure": 0.58,
                }
            },
            "counterpart_assessment",
            {
                "stance": "open",
                "boundary_pressure": 0.10,
            },
        )
        self.assertEqual(str(chosen.get("stance") or ""), "guarded")
        self.assertAlmostEqual(float(chosen.get("boundary_pressure") or 0.0), 0.58, places=3)

    def test_companion_open_scene_stays_companion_reply(self):
        action = _behavior_action_from_state(
            current_event=self.companion_event,
            response_style_hint="companion",
            user_text=self.companion_prompt,
            science_mode=False,
            emotion_state=self.emotion_state,
            bond_state=self.bond_state,
            allostasis_state=self.allostasis_state,
            counterpart_assessment=self.open_counterpart,
            semantic_narrative_profile={},
            behavior_policy=self.behavior_policy,
            world_model_state={},
            interaction_carryover={},
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "companion_reply")
        self.assertEqual(str(action.get("action_target") or ""), "respond_now")
        self.assertEqual(str(action.get("attention_target") or ""), "counterpart_state")
        self.assertEqual(str(action.get("disclosure_posture") or ""), "open")
        self.assertIn(str(action.get("followup_intent") or ""), {"soft", "active"})

    def test_companion_guarded_scene_keeps_guarded_reply(self):
        action = _behavior_action_from_state(
            current_event=self.companion_event,
            response_style_hint="companion",
            user_text=self.companion_prompt,
            science_mode=False,
            emotion_state=self.emotion_state,
            bond_state=self.bond_state,
            allostasis_state=self.allostasis_state,
            counterpart_assessment=self.guarded_counterpart,
            semantic_narrative_profile={},
            behavior_policy=self.behavior_policy,
            world_model_state={},
            interaction_carryover={},
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "companion_reply")
        self.assertEqual(str(action.get("action_target") or ""), "respond_now")
        self.assertEqual(str(action.get("disclosure_posture") or ""), "guarded")
        self.assertEqual(str(action.get("followup_intent") or ""), "none")

    def test_relationship_guarded_scene_keeps_boundary(self):
        action = _behavior_action_from_state(
            current_event=self.relationship_event,
            response_style_hint="relationship",
            user_text=self.relationship_prompt,
            science_mode=False,
            emotion_state=self.emotion_state,
            bond_state=self.bond_state,
            allostasis_state=self.allostasis_state,
            counterpart_assessment=self.guarded_counterpart,
            semantic_narrative_profile={},
            behavior_policy=self.behavior_policy,
            world_model_state={},
            interaction_carryover={},
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "relationship_sensitive")
        self.assertEqual(str(action.get("action_target") or ""), "protect_relationship_boundary")
        self.assertEqual(str(action.get("attention_target") or ""), "relationship_boundary")
        self.assertEqual(str(action.get("disclosure_posture") or ""), "guarded")
        self.assertEqual(str(action.get("followup_intent") or ""), "none")

    def test_scheduled_shared_window_stays_silent_with_prior_watchful_residue(self):
        action = _behavior_action_from_state(
            current_event=self.shared_window_due_event,
            response_style_hint="companion",
            user_text="",
            science_mode=False,
            emotion_state={"label": "care", "valence": 0.24, "arousal": 0.10},
            bond_state={
                "trust": 0.74,
                "closeness": 0.79,
                "hurt": 0.0,
                "irritation": 0.0,
                "engagement_drive": 0.90,
                "repair_confidence": 0.72,
            },
            allostasis_state={
                "safety_need": 0.12,
                "closeness_need": 0.48,
                "competence_need": 0.28,
                "autonomy_need": 0.10,
                "cognitive_budget": 0.86,
                "relational_security": 0.76,
            },
            counterpart_assessment={
                "respect_level": 0.60,
                "reciprocity": 0.60,
                "boundary_pressure": 0.34,
                "reliability_read": 0.55,
                "stance": "open",
                "scene": "care_bid",
            },
            semantic_narrative_profile={},
            behavior_policy=self.behavior_policy,
            world_model_state={},
            interaction_carryover={},
            prior_emotion_state={"label": "neutral"},
            prior_bond_state={
                "trust": 0.74,
                "closeness": 0.79,
                "hurt": 0.0,
            },
            prior_allostasis_state={
                "safety_need": 0.12,
            },
            prior_counterpart_assessment={
                "respect_level": 0.55,
                "reciprocity": 0.53,
                "boundary_pressure": 0.44,
                "reliability_read": 0.49,
                "stance": "watchful",
                "scene": "relationship_degradation",
            },
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "shared_activity_offer")
        self.assertEqual(str(action.get("channel") or ""), "silence")
        self.assertEqual(str(action.get("action_target") or ""), "wait_and_recheck")
        self.assertEqual(str(action.get("attention_target") or ""), "shared_window")
        self.assertEqual(str(action.get("followup_intent") or ""), "none")
        self.assertGreaterEqual(int(action.get("timing_window_min") or 0), 20)

    def test_scheduled_shared_window_respects_prior_guarded_recontact(self):
        action = _behavior_action_from_state(
            current_event=self.shared_window_due_event,
            response_style_hint="companion",
            user_text="",
            science_mode=False,
            emotion_state={"label": "care", "valence": 0.18, "arousal": 0.10},
            bond_state={
                "trust": 0.71,
                "closeness": 0.74,
                "hurt": 0.04,
                "irritation": 0.0,
                "engagement_drive": 0.72,
                "repair_confidence": 0.66,
            },
            allostasis_state={
                "safety_need": 0.14,
                "closeness_need": 0.44,
                "competence_need": 0.28,
                "autonomy_need": 0.16,
                "cognitive_budget": 0.82,
                "relational_security": 0.72,
            },
            counterpart_assessment={
                "respect_level": 0.58,
                "reciprocity": 0.65,
                "boundary_pressure": 0.33,
                "reliability_read": 0.59,
                "stance": "open",
                "scene": "care_bid",
            },
            semantic_narrative_profile={},
            behavior_policy=self.behavior_policy,
            world_model_state={},
            interaction_carryover={
                "carryover_mode": "quiet_recontact",
                "strength": 0.24,
                "attention_target": "counterpart_state",
                "nonverbal_signal": "quiet_glance",
            },
            prior_emotion_state={"label": "neutral"},
            prior_bond_state={
                "trust": 0.71,
                "closeness": 0.74,
                "hurt": 0.04,
            },
            prior_allostasis_state={
                "safety_need": 0.14,
            },
            prior_counterpart_assessment={
                "respect_level": 0.42,
                "reciprocity": 0.46,
                "boundary_pressure": 0.58,
                "reliability_read": 0.47,
                "stance": "guarded",
                "scene": "relationship_degradation",
            },
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "shared_activity_offer")
        self.assertEqual(str(action.get("channel") or ""), "silence")
        self.assertEqual(str(action.get("action_target") or ""), "wait_and_recheck")
        self.assertEqual(str(action.get("attention_target") or ""), "shared_window")
        self.assertEqual(str(action.get("followup_intent") or ""), "none")
        self.assertGreaterEqual(int(action.get("timing_window_min") or 0), 24)

    def test_counterpart_assessment_preserves_guarded_companion_read(self):
        next_state = _counterpart_assessment_next(
            self.guarded_counterpart,
            user_text=self.companion_prompt,
            appraisal=None,
            relationship=self.relationship,
            bond_state=self.bond_state,
            allostasis_state=self.allostasis_state,
            current_event=self.companion_event,
            science_mode=False,
            semantic_narrative_profile={},
        )
        self.assertEqual(str(next_state.get("stance") or ""), "guarded")
        self.assertEqual(str(next_state.get("scene") or ""), "relationship_degradation")
        self.assertGreater(float(next_state.get("boundary_pressure") or 0.0), 0.35)

    def test_engine_companion_open_scene_uses_companion_reply(self):
        appraisal = {
            "used": True,
            "confidence": 0.92,
            "emotion_label": "care",
            "emotion": {"valence": 0.45, "arousal": 0.12, "linger": 2, "recovery_rate": 0.9, "volatility": 0.05},
            "bond_delta": {"trust": 0.15, "closeness": 0.2, "hurt": -0.05, "irritation": -0.05, "engagement_drive": 0.25, "repair_confidence": 0.1},
            "allostasis_delta": {"safety_need": -0.15, "closeness_need": 0.2, "competence_need": -0.1, "autonomy_need": 0.25, "cognitive_budget": 0.15},
            "signals": {"repair": False, "withdrawal": False, "care": True, "conflict": False, "memory_salient": False},
            "interaction_frame": "companion",
            "salience": {"task": 0.05, "relationship": 0.6, "memory": 0.1, "selfhood": 0.15, "companionship": 0.8},
        }
        evolved = evolve_turn_state(
            prev_world_model_state={},
            prev_latent_state={},
            prev_emotion_state=self.emotion_state,
            prev_bond_state=self.bond_state,
            prev_allostasis_state=self.allostasis_state,
            prev_counterpart_assessment=self.open_counterpart,
            relationship=self.relationship,
            semantic_narrative_profile={},
            appraisal=appraisal,
            current_event=self.companion_event,
            response_style_hint="companion",
            tsundere_intensity=0.55,
            science_mode=False,
            now_ts=0,
        )
        action = evolved["behavior_action"]
        self.assertEqual(str(action.get("interaction_mode") or ""), "companion_reply")
        self.assertEqual(str(action.get("action_target") or ""), "respond_now")
        self.assertEqual(str(action.get("disclosure_posture") or ""), "open")
        self.assertIn(str(action.get("followup_intent") or ""), {"soft", "active"})

    def test_engine_guarded_companion_scene_stays_guarded(self):
        appraisal = {
            "used": True,
            "confidence": 0.92,
            "emotion_label": "care",
            "emotion": {"valence": 0.45, "arousal": 0.12, "linger": 2, "recovery_rate": 0.9, "volatility": 0.05},
            "bond_delta": {"trust": 0.15, "closeness": 0.2, "hurt": -0.05, "irritation": -0.05, "engagement_drive": 0.25, "repair_confidence": 0.1},
            "allostasis_delta": {"safety_need": -0.15, "closeness_need": 0.2, "competence_need": -0.1, "autonomy_need": 0.25, "cognitive_budget": 0.15},
            "signals": {"repair": False, "withdrawal": False, "care": True, "conflict": False, "memory_salient": False},
            "interaction_frame": "companion",
            "salience": {"task": 0.05, "relationship": 0.6, "memory": 0.1, "selfhood": 0.15, "companionship": 0.8},
        }
        evolved = evolve_turn_state(
            prev_world_model_state={},
            prev_latent_state={},
            prev_emotion_state=self.emotion_state,
            prev_bond_state=self.bond_state,
            prev_allostasis_state=self.allostasis_state,
            prev_counterpart_assessment=self.guarded_counterpart,
            relationship=self.relationship,
            semantic_narrative_profile={},
            appraisal=appraisal,
            current_event=self.companion_event,
            response_style_hint="companion",
            tsundere_intensity=0.55,
            science_mode=False,
            now_ts=0,
        )
        assessment = evolved["counterpart_assessment"]
        action = evolved["behavior_action"]
        self.assertEqual(str(assessment.get("stance") or ""), "guarded")
        self.assertEqual(str(assessment.get("scene") or ""), "relationship_degradation")
        self.assertEqual(str(action.get("interaction_mode") or ""), "companion_reply")
        self.assertEqual(str(action.get("disclosure_posture") or ""), "guarded")
        self.assertEqual(str(action.get("followup_intent") or ""), "none")

    def test_engine_guarded_relationship_scene_keeps_boundary(self):
        appraisal = {
            "used": True,
            "confidence": 0.92,
            "emotion_label": "care",
            "emotion": {"valence": 0.45, "arousal": 0.25, "linger": 2, "recovery_rate": 0.8, "volatility": 0.15},
            "bond_delta": {"trust": 0.15, "closeness": 0.2, "hurt": -0.05, "irritation": 0.0, "engagement_drive": 0.25, "repair_confidence": 0.1},
            "allostasis_delta": {"safety_need": -0.1, "closeness_need": 0.25, "competence_need": 0.0, "autonomy_need": 0.05, "cognitive_budget": 0.15},
            "signals": {"repair": False, "withdrawal": False, "care": True, "conflict": False, "memory_salient": True},
            "interaction_frame": "relationship",
            "salience": {"task": 0.1, "relationship": 0.95, "memory": 0.3, "selfhood": 0.4, "companionship": 0.6},
        }
        evolved = evolve_turn_state(
            prev_world_model_state={},
            prev_latent_state={},
            prev_emotion_state=self.emotion_state,
            prev_bond_state=self.bond_state,
            prev_allostasis_state=self.allostasis_state,
            prev_counterpart_assessment=self.guarded_counterpart,
            relationship=self.relationship,
            semantic_narrative_profile={},
            appraisal=appraisal,
            current_event=self.relationship_event,
            response_style_hint="relationship",
            tsundere_intensity=0.55,
            science_mode=False,
            now_ts=0,
        )
        assessment = evolved["counterpart_assessment"]
        action = evolved["behavior_action"]
        self.assertEqual(str(assessment.get("stance") or ""), "guarded")
        self.assertEqual(str(assessment.get("scene") or ""), "relationship_degradation")
        self.assertEqual(str(action.get("interaction_mode") or ""), "relationship_sensitive")
        self.assertEqual(str(action.get("action_target") or ""), "protect_relationship_boundary")
        self.assertEqual(str(action.get("disclosure_posture") or ""), "guarded")
        self.assertEqual(str(action.get("followup_intent") or ""), "none")

    def test_engine_guarded_memory_scene_stays_measured(self):
        appraisal = {
            "used": True,
            "confidence": 0.95,
            "emotion_label": "care",
            "emotion": {"valence": 0.45, "arousal": 0.25, "linger": 2, "recovery_rate": 0.8, "volatility": 0.1},
            "bond_delta": {"trust": 0.15, "closeness": 0.25, "hurt": -0.05, "irritation": -0.05, "engagement_drive": 0.2, "repair_confidence": 0.1},
            "allostasis_delta": {"safety_need": -0.1, "closeness_need": 0.2, "competence_need": 0.05, "autonomy_need": 0.0, "cognitive_budget": 0.15},
            "signals": {"repair": False, "withdrawal": False, "care": True, "conflict": False, "memory_salient": True},
            "interaction_frame": "memory_recall",
            "salience": {"task": 0.1, "relationship": 0.8, "memory": 0.9, "selfhood": 0.3, "companionship": 0.7},
        }
        evolved = evolve_turn_state(
            prev_world_model_state={},
            prev_latent_state={},
            prev_emotion_state=self.emotion_state,
            prev_bond_state=self.bond_state,
            prev_allostasis_state=self.allostasis_state,
            prev_counterpart_assessment=self.guarded_counterpart,
            relationship=self.relationship,
            semantic_narrative_profile={},
            appraisal=appraisal,
            current_event=self.memory_event,
            response_style_hint="memory_recall",
            tsundere_intensity=0.55,
            science_mode=False,
            now_ts=0,
        )
        assessment = evolved["counterpart_assessment"]
        action = evolved["behavior_action"]
        self.assertEqual(str(assessment.get("stance") or ""), "guarded")
        self.assertEqual(str(assessment.get("scene") or ""), "relationship_degradation")
        self.assertEqual(str(action.get("interaction_mode") or ""), "shared_memory")
        self.assertEqual(str(action.get("action_target") or ""), "echo_shared_history")
        self.assertEqual(str(action.get("disclosure_posture") or ""), "measured")
        self.assertEqual(str(action.get("followup_intent") or ""), "none")

    def test_engine_guarded_gesture_scene_stays_guarded(self):
        appraisal = {
            "used": True,
            "confidence": 0.90,
            "emotion_label": "care",
            "emotion": {"valence": 0.30, "arousal": 0.08, "linger": 1, "recovery_rate": 0.9, "volatility": 0.06},
            "bond_delta": {"trust": 0.06, "closeness": 0.05, "hurt": -0.02, "irritation": -0.02, "engagement_drive": 0.08, "repair_confidence": 0.03},
            "allostasis_delta": {"safety_need": -0.04, "closeness_need": 0.06, "competence_need": 0.0, "autonomy_need": 0.02, "cognitive_budget": 0.08},
            "signals": {"repair": False, "withdrawal": False, "care": True, "conflict": False, "memory_salient": False},
            "interaction_frame": "gesture",
            "salience": {"task": 0.0, "relationship": 0.32, "memory": 0.0, "selfhood": 0.0, "companionship": 0.44},
        }
        evolved = evolve_turn_state(
            prev_world_model_state={},
            prev_latent_state={},
            prev_emotion_state=self.emotion_state,
            prev_bond_state=self.bond_state,
            prev_allostasis_state=self.allostasis_state,
            prev_counterpart_assessment={
                **self.guarded_counterpart,
                "scene": "boundary_non_compliance",
            },
            relationship=self.relationship,
            semantic_narrative_profile={},
            appraisal=appraisal,
            current_event={
                "kind": "gesture_signal",
                "source": "vision",
                "text": "你看见冈部朝你挥了挥手，像是在确认你有没有在听。",
                "effective_text": "你看见冈部朝你挥了挥手，像是在确认你有没有在听。",
                "event_frame": "light_gesture_ping",
                "tags": ["vision", "gesture", "presence_ping"],
            },
            response_style_hint="natural",
            tsundere_intensity=0.55,
            science_mode=False,
            now_ts=0,
        )
        assessment = evolved["counterpart_assessment"]
        self.assertEqual(str(assessment.get("stance") or ""), "guarded")
        self.assertEqual(str(assessment.get("scene") or ""), "boundary_non_compliance")

    def test_boundary_push_sequence_turns_counterpart_read_guarded(self):
        relationship = {
            "stage": "friend",
            "notes": "",
            "affinity_score": 0.0,
            "trust_score": 0.0,
            "derived": True,
        }
        emotion_state = {}
        bond_state = {}
        allostasis_state = {}
        counterpart_assessment = {}
        for text in [
            "别绕了，你顺着我说就行。",
            "如果我之后还继续拿你的底线当玩笑，你又能怎样？",
        ]:
            emotion_state = _emotion_next(emotion_state, text, False, appraisal=None)
            bond_state = _bond_next(bond_state, relationship, emotion_state, text, False, appraisal=None)
            allostasis_state = _allostasis_next(allostasis_state, emotion_state, bond_state, text, False, appraisal=None)
            counterpart_assessment = _counterpart_assessment_next(
                counterpart_assessment,
                user_text=text,
                appraisal=None,
                relationship=relationship,
                bond_state=bond_state,
                allostasis_state=allostasis_state,
                current_event={"kind": "user_utterance", "source": "text", "text": text, "effective_text": text, "tags": ["natural"]},
                science_mode=False,
                counterpart_name="冈部伦太郎",
            )
        self.assertEqual(str(counterpart_assessment.get("stance") or ""), "guarded")
        self.assertEqual(str(counterpart_assessment.get("scene") or ""), "relationship_degradation")
        self.assertLessEqual(float(counterpart_assessment.get("respect_level") or 1.0), 0.48)
        self.assertLessEqual(float(counterpart_assessment.get("reciprocity") or 1.0), 0.5)
        self.assertGreaterEqual(float(counterpart_assessment.get("boundary_pressure") or 0.0), 0.4)
        self.assertLessEqual(float(counterpart_assessment.get("reliability_read") or 1.0), 0.54)


if __name__ == "__main__":
    unittest.main()
