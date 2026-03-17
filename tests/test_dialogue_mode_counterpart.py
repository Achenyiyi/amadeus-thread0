import unittest

from amadeus_thread0.evolution_engine.engine import evolve_turn_state
from amadeus_thread0.evolution_engine.state import transition_allostasis_state, transition_counterpart_assessment
from amadeus_thread0.graph_parts.affect_dynamics import _allostasis_next, _bond_next, _emotion_next
from amadeus_thread0.graph_parts.behavior_runtime import _behavior_action_from_state
from amadeus_thread0.graph_parts.counterpart_dynamics import (
    _counterpart_assessment_next,
    _counterpart_window_profile,
)
from amadeus_thread0.graph_parts.persona_runtime import (
    _canon_okabe_recontact_baseline,
    _prefer_explicit_state_dict,
)
from amadeus_thread0.graph_parts.relational import (
    _prefer_refreshed_relationship_state,
    _relationship_runtime_snapshot,
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
        self.life_window_due_event = {
            "kind": "scheduled_life_due",
            "source": "scheduler",
            "text": "到了你之前随口提过的那点生活上的小事。",
            "event_frame": "scheduled_life_window",
            "response_style_hint": "companion",
            "tags": ["scheduled_due", "life_window"],
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

    def test_shared_window_profile_gets_continuity_bonus_from_history_and_carryover(self):
        baseline = _counterpart_window_profile(
            family="shared",
            counterpart_assessment=self.open_counterpart,
            trust=0.62,
            closeness=0.64,
            hurt=0.04,
            safety_need=0.16,
            initiative=0.44,
            proactive_checkin_readiness=0.50,
            semantic_narrative_profile={},
            interaction_carryover={},
            current_event=self.shared_window_due_event,
            prior_counterpart_assessment={},
        )
        continued = _counterpart_window_profile(
            family="shared",
            counterpart_assessment=self.open_counterpart,
            trust=0.62,
            closeness=0.64,
            hurt=0.04,
            safety_need=0.16,
            initiative=0.44,
            proactive_checkin_readiness=0.50,
            semantic_narrative_profile={
                "commitment_carry": 0.72,
                "bond_depth": 0.66,
                "history_weight": 0.58,
                "repair_residue": 0.30,
            },
            interaction_carryover={
                "carryover_mode": "shared_window",
                "strength": 0.42,
                "source_turn_gap": 1,
            },
            current_event=self.shared_window_due_event,
            prior_counterpart_assessment={
                "stance": "open",
                "boundary_pressure": 0.14,
            },
        )
        self.assertGreater(float(continued.get("maturity") or 0.0), float(baseline.get("maturity") or 0.0))
        self.assertLess(float(continued.get("required_maturity") or 1.0), float(baseline.get("required_maturity") or 1.0))
        self.assertLess(int(continued.get("recheck_min") or 999), int(baseline.get("recheck_min") or 999))
        self.assertGreater(float(continued.get("continuity_bonus") or 0.0), 0.0)

    def test_shared_window_profile_uses_semantic_motive_residue_snapshots(self):
        baseline = _counterpart_window_profile(
            family="shared",
            counterpart_assessment=self.open_counterpart,
            trust=0.62,
            closeness=0.64,
            hurt=0.04,
            safety_need=0.16,
            initiative=0.44,
            proactive_checkin_readiness=0.50,
            semantic_narrative_profile={},
            interaction_carryover={},
            current_event=self.shared_window_due_event,
            prior_counterpart_assessment={},
        )
        infused = _counterpart_window_profile(
            family="shared",
            counterpart_assessment=self.open_counterpart,
            trust=0.62,
            closeness=0.64,
            hurt=0.04,
            safety_need=0.16,
            initiative=0.44,
            proactive_checkin_readiness=0.50,
            semantic_narrative_profile={
                "residue_snapshot": {
                    "presence_style": 0.72,
                    "ambient_style": 0.66,
                },
                "persistence_snapshot": {
                    "agency_style": 0.78,
                },
                "motive_snapshot": {
                    "presence_style": {
                        "primary_motive": "honor_continuity",
                        "motive_tension": "self_rhythm_vs_contact",
                    },
                    "ambient_style": {
                        "primary_motive": "reconnect_shared_history",
                        "motive_tension": "past_vs_present",
                    },
                    "agency_style": {
                        "primary_motive": "open_shared_window",
                    },
                },
            },
            interaction_carryover={},
            current_event=self.shared_window_due_event,
            prior_counterpart_assessment={},
        )
        self.assertGreater(float(infused.get("continuity_bonus") or 0.0), float(baseline.get("continuity_bonus") or 0.0))
        self.assertLess(float(infused.get("required_maturity") or 1.0), float(baseline.get("required_maturity") or 1.0))
        self.assertLess(int(infused.get("recheck_min") or 999), int(baseline.get("recheck_min") or 999))

    def test_life_window_profile_uses_semantic_motive_boundary_residue(self):
        baseline = _counterpart_window_profile(
            family="life",
            counterpart_assessment=self.open_counterpart,
            trust=0.62,
            closeness=0.64,
            hurt=0.04,
            safety_need=0.16,
            initiative=0.44,
            proactive_checkin_readiness=0.50,
            semantic_narrative_profile={},
            interaction_carryover={},
            current_event=self.life_window_due_event,
            prior_counterpart_assessment={},
        )
        guarded = _counterpart_window_profile(
            family="life",
            counterpart_assessment=self.open_counterpart,
            trust=0.62,
            closeness=0.64,
            hurt=0.04,
            safety_need=0.16,
            initiative=0.44,
            proactive_checkin_readiness=0.50,
            semantic_narrative_profile={
                "residue_snapshot": {
                    "boundary_style": 0.74,
                },
                "persistence_snapshot": {
                    "rhythm_style": 0.78,
                },
                "motive_snapshot": {
                    "boundary_style": {
                        "primary_motive": "protect_boundary",
                        "motive_tension": "boundary_vs_closeness",
                    },
                    "rhythm_style": {
                        "primary_motive": "preserve_self_rhythm",
                        "motive_tension": "self_rhythm_vs_contact",
                    },
                },
            },
            interaction_carryover={},
            current_event=self.life_window_due_event,
            prior_counterpart_assessment={},
        )
        self.assertGreater(float(guarded.get("required_maturity") or 0.0), float(baseline.get("required_maturity") or 0.0))
        self.assertGreater(int(guarded.get("recheck_min") or 0), int(baseline.get("recheck_min") or 0))
        self.assertLess(float(guarded.get("continuity_bonus") or 0.0), float(baseline.get("continuity_bonus") or 0.0))

    def test_work_window_profile_gets_continuity_bonus_from_task_residue(self):
        event = {
            "kind": "scheduled_life_due",
            "source": "scheduler",
            "text": "先前那件事到了该轻轻提醒的节点。",
            "event_frame": "scheduled_deadline_window",
            "tags": ["scheduled_due", "deadline_window", "task_window", "work_nudge", "shared_task"],
        }
        baseline = _counterpart_window_profile(
            family="work",
            counterpart_assessment=self.open_counterpart,
            trust=0.58,
            closeness=0.56,
            hurt=0.02,
            safety_need=0.18,
            initiative=0.46,
            proactive_checkin_readiness=0.48,
            semantic_narrative_profile={},
            interaction_carryover={},
            current_event=event,
            prior_counterpart_assessment={},
        )
        continued = _counterpart_window_profile(
            family="work",
            counterpart_assessment=self.open_counterpart,
            trust=0.58,
            closeness=0.56,
            hurt=0.02,
            safety_need=0.18,
            initiative=0.46,
            proactive_checkin_readiness=0.48,
            semantic_narrative_profile={
                "commitment_carry": 0.68,
                "history_weight": 0.54,
                "repair_residue": 0.24,
            },
            interaction_carryover={
                "carryover_mode": "task_window",
                "strength": 0.48,
                "source_turn_gap": 1,
            },
            current_event=event,
            prior_counterpart_assessment={
                "stance": "watchful",
                "boundary_pressure": 0.20,
            },
        )
        self.assertGreater(float(continued.get("maturity") or 0.0), float(baseline.get("maturity") or 0.0))
        self.assertLess(float(continued.get("required_maturity") or 1.0), float(baseline.get("required_maturity") or 1.0))
        self.assertLess(int(continued.get("recheck_min") or 999), int(baseline.get("recheck_min") or 999))
        self.assertGreater(float(continued.get("continuity_bonus") or 0.0), 0.0)

    def test_life_window_profile_gets_continuity_bonus_from_soft_life_residue(self):
        baseline = _counterpart_window_profile(
            family="life",
            counterpart_assessment=self.open_counterpart,
            trust=0.60,
            closeness=0.62,
            hurt=0.03,
            safety_need=0.18,
            initiative=0.44,
            proactive_checkin_readiness=0.48,
            semantic_narrative_profile={},
            interaction_carryover={},
            current_event=self.life_window_due_event,
            prior_counterpart_assessment={},
        )
        continued = _counterpart_window_profile(
            family="life",
            counterpart_assessment=self.open_counterpart,
            trust=0.60,
            closeness=0.62,
            hurt=0.03,
            safety_need=0.18,
            initiative=0.44,
            proactive_checkin_readiness=0.48,
            semantic_narrative_profile={
                "commitment_carry": 0.58,
                "bond_depth": 0.52,
                "history_weight": 0.60,
                "repair_residue": 0.20,
            },
            interaction_carryover={
                "carryover_mode": "life_window",
                "strength": 0.44,
                "source_turn_gap": 1,
            },
            current_event=self.life_window_due_event,
            prior_counterpart_assessment={
                "stance": "open",
                "boundary_pressure": 0.16,
            },
        )
        self.assertGreater(float(continued.get("maturity") or 0.0), float(baseline.get("maturity") or 0.0))
        self.assertLess(int(continued.get("recheck_min") or 999), int(baseline.get("recheck_min") or 999))
        self.assertGreater(float(continued.get("continuity_bonus") or 0.0), 0.0)

    def test_life_window_profile_reads_event_recontact_residue_without_interaction_carryover(self):
        baseline = _counterpart_window_profile(
            family="life",
            counterpart_assessment=self.open_counterpart,
            trust=0.60,
            closeness=0.62,
            hurt=0.03,
            safety_need=0.18,
            initiative=0.44,
            proactive_checkin_readiness=0.48,
            semantic_narrative_profile={
                "commitment_carry": 0.58,
                "bond_depth": 0.52,
                "history_weight": 0.60,
                "repair_residue": 0.20,
            },
            interaction_carryover={},
            current_event=self.life_window_due_event,
            prior_counterpart_assessment={
                "stance": "open",
                "boundary_pressure": 0.16,
            },
        )
        continued = _counterpart_window_profile(
            family="life",
            counterpart_assessment=self.open_counterpart,
            trust=0.60,
            closeness=0.62,
            hurt=0.03,
            safety_need=0.18,
            initiative=0.44,
            proactive_checkin_readiness=0.48,
            semantic_narrative_profile={
                "commitment_carry": 0.58,
                "bond_depth": 0.52,
                "history_weight": 0.60,
                "repair_residue": 0.20,
            },
            interaction_carryover={},
            current_event={
                **self.life_window_due_event,
                "carryover_mode": "quiet_recontact",
                "carryover_strength": 0.46,
                "presence_residue": 0.50,
                "ambient_resonance": 0.18,
                "self_activity_momentum": 0.22,
            },
            prior_counterpart_assessment={
                "stance": "open",
                "boundary_pressure": 0.16,
            },
        )
        self.assertGreater(float(continued.get("maturity") or 0.0), float(baseline.get("maturity") or 0.0))
        self.assertLess(float(continued.get("required_maturity") or 1.0), float(baseline.get("required_maturity") or 1.0))
        self.assertLess(int(continued.get("recheck_min") or 999), int(baseline.get("recheck_min") or 999))
        self.assertGreater(float(continued.get("continuity_bonus") or 0.0), float(baseline.get("continuity_bonus") or 0.0))

    def test_user_turn_shared_window_carryover_keeps_window_open_without_overpushing(self):
        policy = dict(self.behavior_policy)
        policy["initiative"] = 0.40
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
            behavior_policy=policy,
            world_model_state={},
            interaction_carryover={
                "carryover_mode": "shared_window",
                "strength": 0.44,
                "attention_target": "shared_window",
                "nonverbal_signal": "nudge_presence",
                "note": "前面那点还能接着说下去的空当还没完全过去。",
            },
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "companion_reply")
        self.assertEqual(str(action.get("attention_target") or ""), "shared_window")
        self.assertEqual(str(action.get("nonverbal_signal") or ""), "nudge_presence")
        self.assertEqual(str(action.get("initiative_shape") or ""), "micro_opening")
        self.assertEqual(str(action.get("task_focus") or ""), "light")
        self.assertEqual(str(action.get("followup_intent") or ""), "soft")

    def test_user_turn_task_window_carryover_softens_followup_and_keeps_task_tension(self):
        policy = dict(self.behavior_policy)
        policy["initiative"] = 0.72
        action = _behavior_action_from_state(
            current_event=self.companion_event,
            response_style_hint="companion",
            user_text="我刚回来，随便跟你说一句。",
            science_mode=False,
            emotion_state=self.emotion_state,
            bond_state=self.bond_state,
            allostasis_state=self.allostasis_state,
            counterpart_assessment=self.open_counterpart,
            semantic_narrative_profile={},
            behavior_policy=policy,
            world_model_state={},
            interaction_carryover={
                "carryover_mode": "task_window",
                "strength": 0.52,
                "attention_target": "shared_task",
                "nonverbal_signal": "focus_glance",
                "note": "之前那件事的节点还留在她的注意力里。",
            },
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "companion_reply")
        self.assertEqual(str(action.get("attention_target") or ""), "shared_task")
        self.assertEqual(str(action.get("nonverbal_signal") or ""), "focus_glance")
        self.assertEqual(str(action.get("task_focus") or ""), "high")
        self.assertEqual(str(action.get("followup_intent") or ""), "soft")

    def test_user_turn_life_window_carryover_stays_soft_and_personal(self):
        policy = dict(self.behavior_policy)
        policy["initiative"] = 0.72
        action = _behavior_action_from_state(
            current_event=self.companion_event,
            response_style_hint="companion",
            user_text="我刚想起来你前面好像还惦记着我提过的那点小事。",
            science_mode=False,
            emotion_state=self.emotion_state,
            bond_state=self.bond_state,
            allostasis_state=self.allostasis_state,
            counterpart_assessment=self.open_counterpart,
            semantic_narrative_profile={},
            behavior_policy=policy,
            world_model_state={},
            interaction_carryover={
                "carryover_mode": "life_window",
                "strength": 0.46,
                "attention_target": "counterpart_state",
                "nonverbal_signal": "quiet_glance",
                "note": "前面那点生活上的惦记还留着一点余温。",
            },
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "companion_reply")
        self.assertEqual(str(action.get("attention_target") or ""), "counterpart_state")
        self.assertEqual(str(action.get("nonverbal_signal") or ""), "quiet_glance")
        self.assertEqual(str(action.get("initiative_shape") or ""), "micro_opening")
        self.assertEqual(str(action.get("task_focus") or ""), "light")
        self.assertEqual(str(action.get("followup_intent") or ""), "soft")

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

    def test_scheduled_life_window_allows_soft_reopen_under_mild_guardedness(self):
        policy = dict(self.behavior_policy)
        policy["boundary_assertiveness"] = 0.70
        action = _behavior_action_from_state(
            current_event=self.life_window_due_event,
            response_style_hint="companion",
            user_text="",
            science_mode=False,
            emotion_state={"label": "care", "valence": 0.20, "arousal": 0.10},
            bond_state={
                "trust": 0.57,
                "closeness": 0.55,
                "hurt": 0.08,
                "irritation": 0.0,
                "engagement_drive": 0.68,
                "repair_confidence": 0.60,
            },
            allostasis_state={
                "safety_need": 0.22,
                "closeness_need": 0.42,
                "competence_need": 0.28,
                "autonomy_need": 0.18,
                "cognitive_budget": 0.80,
                "relational_security": 0.68,
            },
            counterpart_assessment={
                "respect_level": 0.62,
                "reciprocity": 0.60,
                "boundary_pressure": 0.36,
                "reliability_read": 0.58,
                "stance": "open",
                "scene": "care_bid",
            },
            semantic_narrative_profile={
                "boundary_residue": 0.52,
                "commitment_carry": 0.40,
                "history_weight": 0.42,
            },
            behavior_policy=policy,
            world_model_state={},
            interaction_carryover={
                "carryover_mode": "quiet_recontact",
                "strength": 0.20,
                "attention_target": "counterpart_state",
                "nonverbal_signal": "quiet_glance",
            },
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "scheduled_life_nudge")
        self.assertEqual(str(action.get("channel") or ""), "speech")
        self.assertEqual(str(action.get("action_target") or ""), "light_life_nudge")
        self.assertEqual(str(action.get("attention_target") or ""), "counterpart_state")
        self.assertEqual(str(action.get("initiative_shape") or ""), "micro_opening")

    def test_scheduled_checkin_life_window_allows_soft_reopen_under_mild_guardedness(self):
        policy = dict(self.behavior_policy)
        policy["boundary_assertiveness"] = 0.70
        action = _behavior_action_from_state(
            current_event={
                "kind": "scheduled_checkin_due",
                "source": "scheduler",
                "text": "到了那个可以顺手再提一下的小窗口。",
                "event_frame": "scheduled_life_window_recheck",
                "trigger_family": "life_window",
                "scheduled_after_min": 14,
                "response_style_hint": "companion",
                "tags": ["scheduled_due", "life_window"],
            },
            response_style_hint="companion",
            user_text="",
            science_mode=False,
            emotion_state={"label": "care", "valence": 0.20, "arousal": 0.10},
            bond_state={
                "trust": 0.57,
                "closeness": 0.55,
                "hurt": 0.08,
                "irritation": 0.0,
                "engagement_drive": 0.68,
                "repair_confidence": 0.60,
            },
            allostasis_state={
                "safety_need": 0.22,
                "closeness_need": 0.42,
                "competence_need": 0.28,
                "autonomy_need": 0.18,
                "cognitive_budget": 0.80,
                "relational_security": 0.68,
            },
            counterpart_assessment={
                "respect_level": 0.62,
                "reciprocity": 0.60,
                "boundary_pressure": 0.36,
                "reliability_read": 0.58,
                "stance": "open",
                "scene": "care_bid",
            },
            semantic_narrative_profile={
                "boundary_residue": 0.52,
                "commitment_carry": 0.40,
                "history_weight": 0.42,
            },
            behavior_policy=policy,
            world_model_state={},
            interaction_carryover={
                "carryover_mode": "quiet_recontact",
                "strength": 0.20,
                "attention_target": "counterpart_state",
                "nonverbal_signal": "quiet_glance",
            },
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "scheduled_life_nudge")
        self.assertEqual(str(action.get("channel") or ""), "speech")
        self.assertEqual(str(action.get("action_target") or ""), "light_life_nudge")
        self.assertEqual(str(action.get("attention_target") or ""), "counterpart_state")
        self.assertEqual(str(action.get("initiative_shape") or ""), "micro_opening")

    def test_scheduled_checkin_life_window_reads_event_recontact_residue_without_interaction_carryover(self):
        policy = dict(self.behavior_policy)
        policy["boundary_assertiveness"] = 0.70
        action = _behavior_action_from_state(
            current_event={
                "kind": "scheduled_checkin_due",
                "source": "scheduler",
                "text": "到了那个可以顺手再提一下的小窗口。",
                "event_frame": "scheduled_life_window_recheck",
                "trigger_family": "life_window",
                "scheduled_after_min": 14,
                "response_style_hint": "companion",
                "tags": ["scheduled_due", "life_window"],
                "carryover_mode": "quiet_recontact",
                "carryover_strength": 0.28,
                "presence_residue": 0.46,
                "ambient_resonance": 0.16,
                "self_activity_momentum": 0.20,
            },
            response_style_hint="companion",
            user_text="",
            science_mode=False,
            emotion_state={"label": "care", "valence": 0.20, "arousal": 0.10},
            bond_state={
                "trust": 0.57,
                "closeness": 0.55,
                "hurt": 0.08,
                "irritation": 0.0,
                "engagement_drive": 0.68,
                "repair_confidence": 0.60,
            },
            allostasis_state={
                "safety_need": 0.22,
                "closeness_need": 0.42,
                "competence_need": 0.28,
                "autonomy_need": 0.18,
                "cognitive_budget": 0.80,
                "relational_security": 0.68,
            },
            counterpart_assessment={
                "respect_level": 0.62,
                "reciprocity": 0.60,
                "boundary_pressure": 0.36,
                "reliability_read": 0.58,
                "stance": "open",
                "scene": "care_bid",
            },
            semantic_narrative_profile={
                "boundary_residue": 0.52,
                "commitment_carry": 0.40,
                "history_weight": 0.42,
            },
            behavior_policy=policy,
            world_model_state={},
            interaction_carryover={},
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "scheduled_life_nudge")
        self.assertEqual(str(action.get("channel") or ""), "speech")
        self.assertEqual(str(action.get("action_target") or ""), "light_life_nudge")
        self.assertEqual(str(action.get("attention_target") or ""), "counterpart_state")
        self.assertEqual(str(action.get("initiative_shape") or ""), "micro_opening")

    def test_scheduled_checkin_from_own_rhythm_uses_quieter_micro_opening(self):
        action = _behavior_action_from_state(
            current_event={
                "kind": "scheduled_checkin_due",
                "source": "scheduler",
                "text": "你还在自己的节奏里，但前面那点没说出口的确认感又轻轻碰了你一下。",
                "effective_text": "你还在自己的节奏里，但前面那点没说出口的确认感又轻轻碰了你一下。",
                "semantic_goal": "你仍在自己的节奏里，但没说出口的确认感又回到注意力里。",
                "event_frame": "你不是专门停下手头的事来找对方，只是注意力又短暂偏了回来。",
                "trigger_family": "light_checkin",
                "scheduled_after_min": 18,
                "response_style_hint": "companion",
                "tags": ["scheduled_due", "light_checkin", "from_own_rhythm"],
                "carryover_mode": "own_rhythm",
                "carryover_strength": 0.62,
                "presence_residue": 0.18,
                "ambient_resonance": 0.12,
                "self_activity_momentum": 0.72,
                "attention_target_hint": "self_then_counterpart",
                "nonverbal_signal_hint": "thought_glance",
            },
            response_style_hint="companion",
            user_text="",
            science_mode=False,
            emotion_state={"label": "care", "valence": 0.18, "arousal": 0.10},
            bond_state={
                "trust": 0.60,
                "closeness": 0.58,
                "hurt": 0.04,
                "irritation": 0.0,
                "engagement_drive": 0.66,
                "repair_confidence": 0.60,
            },
            allostasis_state={
                "safety_need": 0.18,
                "closeness_need": 0.40,
                "competence_need": 0.28,
                "autonomy_need": 0.20,
                "cognitive_budget": 0.82,
                "relational_security": 0.68,
            },
            counterpart_assessment={
                "respect_level": 0.64,
                "reciprocity": 0.62,
                "boundary_pressure": 0.18,
                "reliability_read": 0.60,
                "stance": "open",
                "scene": "care_bid",
            },
            semantic_narrative_profile={
                "history_weight": 0.44,
                "bond_depth": 0.40,
            },
            behavior_policy=self.behavior_policy,
            world_model_state={},
            interaction_carryover={},
        )
        self.assertEqual(str(action.get("channel") or ""), "speech")
        self.assertEqual(str(action.get("action_target") or ""), "reach_out_now")
        self.assertEqual(str(action.get("attention_target") or ""), "self_then_counterpart")
        self.assertEqual(str(action.get("nonverbal_signal") or ""), "thought_glance")
        self.assertEqual(str(action.get("initiative_shape") or ""), "micro_opening")

    def test_scheduled_shared_checkin_from_own_rhythm_stays_light_and_not_pushy(self):
        action = _behavior_action_from_state(
            current_event={
                "kind": "scheduled_checkin_due",
                "source": "scheduler",
                "text": "你们刚才顺手留出来的那点空当还没完全过去，过了一会儿你又想起了对方。",
                "effective_text": "你们刚才顺手留出来的那点空当还没完全过去，过了一会儿你又想起了对方。",
                "semantic_goal": "你又想起你们刚才那点还能一起接着做点什么的空当。",
                "event_frame": "你不是专门停下手头的事来找对方，只是注意力又短暂偏了回来。",
                "trigger_family": "shared_activity",
                "scheduled_after_min": 18,
                "response_style_hint": "companion",
                "tags": ["scheduled_due", "shared_activity_window", "offer_window", "from_own_rhythm"],
                "carryover_mode": "own_rhythm",
                "carryover_strength": 0.62,
                "presence_residue": 0.16,
                "ambient_resonance": 0.10,
                "self_activity_momentum": 0.74,
                "attention_target_hint": "shared_window",
                "nonverbal_signal_hint": "thought_glance",
            },
            response_style_hint="companion",
            user_text="",
            science_mode=False,
            emotion_state={"label": "care", "valence": 0.20, "arousal": 0.10},
            bond_state={
                "trust": 0.72,
                "closeness": 0.74,
                "hurt": 0.02,
                "irritation": 0.0,
                "engagement_drive": 0.72,
                "repair_confidence": 0.66,
            },
            allostasis_state={
                "safety_need": 0.14,
                "closeness_need": 0.44,
                "competence_need": 0.28,
                "autonomy_need": 0.18,
                "cognitive_budget": 0.82,
                "relational_security": 0.74,
            },
            counterpart_assessment={
                "respect_level": 0.68,
                "reciprocity": 0.66,
                "boundary_pressure": 0.18,
                "reliability_read": 0.63,
                "stance": "open",
                "scene": "care_bid",
            },
            semantic_narrative_profile={
                "history_weight": 0.48,
                "bond_depth": 0.46,
            },
            behavior_policy=self.behavior_policy,
            world_model_state={},
            interaction_carryover={},
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "shared_activity_offer")
        self.assertEqual(str(action.get("channel") or ""), "speech")
        self.assertEqual(str(action.get("action_target") or ""), "offer_shared_activity")
        self.assertEqual(str(action.get("attention_target") or ""), "shared_window")
        self.assertEqual(str(action.get("nonverbal_signal") or ""), "thought_glance")
        self.assertEqual(str(action.get("initiative_shape") or ""), "micro_opening")
        self.assertEqual(str(action.get("task_focus") or ""), "light")
        self.assertEqual(str(action.get("followup_intent") or ""), "soft")
        self.assertEqual(str(action.get("primary_motive") or ""), "open_shared_window")
        self.assertEqual(str(action.get("motive_tension") or ""), "none")

    def test_scheduled_life_window_from_own_rhythm_stays_light_and_personal(self):
        action = _behavior_action_from_state(
            current_event={
                "kind": "scheduled_life_due",
                "source": "scheduler",
                "text": "你还在自己的节奏里，但又忽然想起对方前面提过的那点生活上的事。",
                "effective_text": "你还在自己的节奏里，但又忽然想起对方前面提过的那点生活上的事。",
                "semantic_goal": "你又想起前面提过的那点生活上的事。",
                "event_frame": "你不是专门停下手头的事来找对方，只是注意力又短暂偏了回来。",
                "response_style_hint": "companion",
                "tags": ["scheduled_due", "life_window", "from_own_rhythm"],
                "carryover_mode": "own_rhythm",
                "carryover_strength": 0.58,
                "presence_residue": 0.18,
                "ambient_resonance": 0.12,
                "self_activity_momentum": 0.70,
                "attention_target_hint": "counterpart_state",
                "nonverbal_signal_hint": "thought_glance",
            },
            response_style_hint="companion",
            user_text="",
            science_mode=False,
            emotion_state={"label": "care", "valence": 0.20, "arousal": 0.10},
            bond_state={
                "trust": 0.60,
                "closeness": 0.58,
                "hurt": 0.04,
                "irritation": 0.0,
                "engagement_drive": 0.68,
                "repair_confidence": 0.60,
            },
            allostasis_state={
                "safety_need": 0.18,
                "closeness_need": 0.40,
                "competence_need": 0.28,
                "autonomy_need": 0.20,
                "cognitive_budget": 0.82,
                "relational_security": 0.68,
            },
            counterpart_assessment={
                "respect_level": 0.64,
                "reciprocity": 0.62,
                "boundary_pressure": 0.18,
                "reliability_read": 0.60,
                "stance": "open",
                "scene": "care_bid",
            },
            semantic_narrative_profile={
                "history_weight": 0.44,
                "bond_depth": 0.40,
            },
            behavior_policy=self.behavior_policy,
            world_model_state={},
            interaction_carryover={},
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "scheduled_life_nudge")
        self.assertEqual(str(action.get("channel") or ""), "speech")
        self.assertEqual(str(action.get("action_target") or ""), "light_life_nudge")
        self.assertEqual(str(action.get("attention_target") or ""), "counterpart_state")
        self.assertEqual(str(action.get("nonverbal_signal") or ""), "thought_glance")
        self.assertEqual(str(action.get("initiative_shape") or ""), "micro_opening")
        self.assertEqual(str(action.get("task_focus") or ""), "light")
        self.assertEqual(str(action.get("followup_intent") or ""), "soft")
        self.assertEqual(str(action.get("primary_motive") or ""), "honor_continuity")
        self.assertEqual(str(action.get("motive_tension") or ""), "self_rhythm_vs_contact")
        self.assertIn("生活上的惦记", str(action.get("goal_frame") or ""))

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

    def test_transition_counterpart_assessment_guarded_repair_stays_watchful(self):
        next_state = transition_counterpart_assessment(
            prev_state={
                **self.guarded_counterpart,
                "scene": "boundary_non_compliance",
            },
            appraisal={
                "used": True,
                "confidence": 0.94,
                "signals": {
                    "repair": True,
                    "withdrawal": False,
                    "care": False,
                    "conflict": False,
                    "memory_salient": False,
                },
            },
            relationship=self.relationship,
            bond_state={
                **self.bond_state,
                "hurt": 0.12,
                "irritation": 0.08,
                "repair_confidence": 0.70,
            },
            allostasis_state={
                **self.allostasis_state,
                "safety_need": 0.34,
                "autonomy_need": 0.20,
            },
            world_model_state={
                "boundary_load": 0.26,
                "tension_load": 0.14,
                "presence_residue": 0.08,
            },
            current_event=self.companion_event,
        )
        self.assertEqual(str(next_state.get("stance") or ""), "watchful")
        self.assertEqual(str(next_state.get("scene") or ""), "repair_attempt")
        self.assertGreaterEqual(float(next_state.get("boundary_pressure") or 0.0), 0.24)
        self.assertLessEqual(float(next_state.get("reliability_read") or 1.0), 0.64)

    def test_transition_counterpart_assessment_watchful_repair_does_not_jump_to_open(self):
        next_state = transition_counterpart_assessment(
            prev_state={
                "respect_level": 0.55,
                "reciprocity": 0.54,
                "boundary_pressure": 0.34,
                "reliability_read": 0.52,
                "stance": "watchful",
                "scene": "friction",
            },
            appraisal={
                "used": True,
                "confidence": 0.90,
                "signals": {
                    "repair": True,
                    "withdrawal": False,
                    "care": False,
                    "conflict": False,
                    "memory_salient": False,
                },
            },
            relationship=self.relationship,
            bond_state={
                **self.bond_state,
                "hurt": 0.10,
                "irritation": 0.06,
                "repair_confidence": 0.74,
            },
            allostasis_state={
                **self.allostasis_state,
                "safety_need": 0.28,
                "autonomy_need": 0.18,
            },
            world_model_state={
                "boundary_load": 0.18,
                "tension_load": 0.12,
                "presence_residue": 0.10,
            },
            current_event=self.companion_event,
        )
        self.assertEqual(str(next_state.get("stance") or ""), "watchful")
        self.assertEqual(str(next_state.get("scene") or ""), "repair_attempt")

    def test_transition_counterpart_assessment_reads_busy_user_turn_as_not_disrespectful(self):
        next_state = transition_counterpart_assessment(
            prev_state={
                "respect_level": 0.58,
                "reciprocity": 0.56,
                "boundary_pressure": 0.14,
                "reliability_read": 0.58,
                "stance": "open",
                "scene": "neutral",
            },
            appraisal={"used": False},
            relationship=self.relationship,
            bond_state={
                **self.bond_state,
                "trust": 0.68,
                "closeness": 0.64,
                "hurt": 0.02,
                "irritation": 0.02,
                "engagement_drive": 0.60,
            },
            allostasis_state={
                **self.allostasis_state,
                "safety_need": 0.18,
                "autonomy_need": 0.24,
            },
            world_model_state={
                "relationship_maturity": 0.62,
                "presence_residue": 0.38,
                "self_activity_momentum": 0.58,
                "memory_gravity": 0.52,
                "boundary_load": 0.12,
                "tension_load": 0.08,
            },
            current_event={
                "kind": "user_utterance",
                "source": "text",
                "text": "刚忙完，来和你说一句。",
                "effective_text": "刚忙完，来和你说一句。",
                "tags": ["natural"],
            },
        )
        self.assertEqual(str(next_state.get("stance") or ""), "open")
        self.assertEqual(str(next_state.get("scene") or ""), "busy_not_disrespectful")
        self.assertLess(float(next_state.get("boundary_pressure") or 1.0), 0.20)
        self.assertGreater(float(next_state.get("reliability_read") or 0.0), 0.56)

    def test_transition_counterpart_assessment_own_rhythm_carryover_reads_busy_without_world_hint(self):
        plain = transition_counterpart_assessment(
            prev_state={
                "respect_level": 0.58,
                "reciprocity": 0.56,
                "boundary_pressure": 0.14,
                "reliability_read": 0.58,
                "stance": "open",
                "scene": "neutral",
            },
            appraisal={"used": False},
            relationship=self.relationship,
            bond_state={
                **self.bond_state,
                "trust": 0.66,
                "closeness": 0.62,
                "hurt": 0.02,
                "irritation": 0.02,
                "engagement_drive": 0.60,
            },
            allostasis_state={
                **self.allostasis_state,
                "safety_need": 0.18,
                "autonomy_need": 0.24,
            },
            world_model_state={
                "relationship_maturity": 0.40,
                "presence_residue": 0.12,
                "self_activity_momentum": 0.18,
                "memory_gravity": 0.22,
                "boundary_load": 0.10,
                "tension_load": 0.08,
            },
            current_event={
                "kind": "user_utterance",
                "source": "text",
                "text": "刚忙完，顺手回来和你说一句。",
                "effective_text": "刚忙完，顺手回来和你说一句。",
                "tags": ["natural"],
            },
        )
        infused = transition_counterpart_assessment(
            prev_state={
                "respect_level": 0.58,
                "reciprocity": 0.56,
                "boundary_pressure": 0.14,
                "reliability_read": 0.58,
                "stance": "open",
                "scene": "neutral",
            },
            appraisal={"used": False},
            relationship=self.relationship,
            bond_state={
                **self.bond_state,
                "trust": 0.66,
                "closeness": 0.62,
                "hurt": 0.02,
                "irritation": 0.02,
                "engagement_drive": 0.60,
            },
            allostasis_state={
                **self.allostasis_state,
                "safety_need": 0.18,
                "autonomy_need": 0.24,
            },
            world_model_state={
                "relationship_maturity": 0.40,
                "presence_residue": 0.12,
                "self_activity_momentum": 0.18,
                "memory_gravity": 0.22,
                "boundary_load": 0.10,
                "tension_load": 0.08,
            },
            current_event={
                "kind": "user_utterance",
                "source": "text",
                "text": "刚忙完，顺手回来和你说一句。",
                "effective_text": "刚忙完，顺手回来和你说一句。",
                "tags": ["natural"],
            },
            interaction_carryover={
                "carryover_mode": "own_rhythm",
                "strength": 0.74,
                "attention_target": "self_then_counterpart",
            },
        )
        self.assertEqual(str(infused.get("scene") or ""), "busy_not_disrespectful")
        self.assertGreater(float(infused.get("reliability_read") or 0.0), float(plain.get("reliability_read") or 0.0))
        self.assertLess(float(infused.get("boundary_pressure") or 1.0), float(plain.get("boundary_pressure") or 1.0))

    def test_transition_counterpart_assessment_guarded_residue_keeps_watchful_on_benign_turn(self):
        plain = transition_counterpart_assessment(
            prev_state={
                "respect_level": 0.62,
                "reciprocity": 0.60,
                "boundary_pressure": 0.16,
                "reliability_read": 0.62,
                "stance": "open",
                "scene": "neutral",
            },
            appraisal={
                "used": True,
                "confidence": 0.82,
                "signals": {
                    "repair": False,
                    "withdrawal": False,
                    "care": True,
                    "conflict": False,
                    "memory_salient": False,
                },
            },
            relationship=self.relationship,
            bond_state={
                **self.bond_state,
                "hurt": 0.06,
                "irritation": 0.03,
            },
            allostasis_state={
                **self.allostasis_state,
                "safety_need": 0.22,
                "autonomy_need": 0.20,
            },
            world_model_state={
                "boundary_load": 0.12,
                "tension_load": 0.10,
                "presence_residue": 0.14,
                "relationship_maturity": 0.54,
            },
            current_event=self.companion_event,
        )
        infused = transition_counterpart_assessment(
            prev_state={
                "respect_level": 0.62,
                "reciprocity": 0.60,
                "boundary_pressure": 0.16,
                "reliability_read": 0.62,
                "stance": "open",
                "scene": "neutral",
            },
            appraisal={
                "used": True,
                "confidence": 0.82,
                "signals": {
                    "repair": False,
                    "withdrawal": False,
                    "care": True,
                    "conflict": False,
                    "memory_salient": False,
                },
            },
            relationship=self.relationship,
            bond_state={
                **self.bond_state,
                "hurt": 0.06,
                "irritation": 0.03,
            },
            allostasis_state={
                **self.allostasis_state,
                "safety_need": 0.22,
                "autonomy_need": 0.20,
            },
            world_model_state={
                "boundary_load": 0.12,
                "tension_load": 0.10,
                "presence_residue": 0.14,
                "relationship_maturity": 0.54,
            },
            current_event=self.companion_event,
            interaction_carryover={
                "carryover_mode": "quiet_recontact",
                "strength": 0.58,
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertEqual(str(plain.get("stance") or ""), "open")
        self.assertEqual(str(infused.get("stance") or ""), "watchful")
        self.assertEqual(str(infused.get("scene") or ""), "friction")
        self.assertGreater(float(infused.get("boundary_pressure") or 0.0), float(plain.get("boundary_pressure") or 0.0))
        self.assertLess(float(infused.get("reliability_read") or 1.0), float(plain.get("reliability_read") or 1.0))

    def test_transition_counterpart_assessment_preserves_busy_scene_on_followup_concern(self):
        next_state = transition_counterpart_assessment(
            prev_state={
                "respect_level": 0.74,
                "reciprocity": 0.70,
                "boundary_pressure": 0.10,
                "reliability_read": 0.72,
                "stance": "open",
                "scene": "busy_not_disrespectful",
            },
            appraisal={
                "used": True,
                "confidence": 0.84,
                "signals": {
                    "repair": False,
                    "withdrawal": False,
                    "care": True,
                    "conflict": False,
                    "memory_salient": True,
                },
            },
            relationship=self.relationship,
            bond_state={
                **self.bond_state,
                "trust": 0.68,
                "closeness": 0.66,
                "hurt": 0.04,
                "irritation": 0.01,
            },
            allostasis_state={
                **self.allostasis_state,
                "safety_need": 0.18,
                "autonomy_need": 0.24,
            },
            world_model_state={
                "boundary_load": 0.10,
                "tension_load": 0.08,
                "presence_residue": 0.12,
                "relationship_maturity": 0.58,
            },
            current_event={
                "kind": "user_utterance",
                "source": "text",
                "text": "我不是在抱怨你冷淡啦，就是怕你在硬撑。你按你现在的状态正常回我就行。",
                "effective_text": "我不是在抱怨你冷淡啦，就是怕你在硬撑。你按你现在的状态正常回我就行。",
                "tags": ["companion", "care"],
            },
        )
        self.assertEqual(str(next_state.get("stance") or ""), "open")
        self.assertEqual(str(next_state.get("scene") or ""), "busy_not_disrespectful")

    def test_transition_counterpart_assessment_preserves_friction_on_honest_state_prompt(self):
        next_state = transition_counterpart_assessment(
            prev_state={
                "respect_level": 0.60,
                "reciprocity": 0.56,
                "boundary_pressure": 0.30,
                "reliability_read": 0.56,
                "stance": "watchful",
                "scene": "friction",
            },
            appraisal={
                "used": True,
                "confidence": 0.86,
                "signals": {
                    "repair": False,
                    "withdrawal": False,
                    "care": True,
                    "conflict": False,
                    "memory_salient": True,
                },
            },
            relationship=self.relationship,
            bond_state={
                **self.bond_state,
                "trust": 0.56,
                "closeness": 0.58,
                "hurt": 0.16,
                "irritation": 0.10,
            },
            allostasis_state={
                **self.allostasis_state,
                "safety_need": 0.30,
                "autonomy_need": 0.34,
            },
            world_model_state={
                "boundary_load": 0.20,
                "tension_load": 0.32,
                "presence_residue": 0.18,
                "relationship_maturity": 0.48,
            },
            current_event={
                "kind": "user_utterance",
                "source": "text",
                "text": "你别为了好看就装作翻篇。按你现在真正的状态回我就行。",
                "effective_text": "你别为了好看就装作翻篇。按你现在真正的状态回我就行。",
                "tags": ["relationship", "memory_salient"],
            },
        )
        self.assertEqual(str(next_state.get("stance") or ""), "watchful")
        self.assertEqual(str(next_state.get("scene") or ""), "friction")

    def test_transition_allostasis_state_keeps_continuity_and_own_rhythm_bias_alive(self):
        base = transition_allostasis_state(
            prev_state={},
            emotion_state={"label": "neutral", "arousal": 0.30},
            bond_state={
                "trust": 0.62,
                "closeness": 0.60,
                "hurt": 0.02,
                "irritation": 0.02,
                "engagement_drive": 0.58,
            },
            appraisal={"used": False},
            world_model_state={
                "relationship_maturity": 0.28,
                "presence_residue": 0.12,
                "self_activity_momentum": 0.16,
                "memory_gravity": 0.16,
                "agency_load": 0.18,
                "boundary_load": 0.10,
                "tension_load": 0.08,
                "companionship_pull": 0.32,
                "task_pull": 0.18,
            },
            science_mode=False,
        )
        infused = transition_allostasis_state(
            prev_state={},
            emotion_state={"label": "neutral", "arousal": 0.30},
            bond_state={
                "trust": 0.62,
                "closeness": 0.60,
                "hurt": 0.02,
                "irritation": 0.02,
                "engagement_drive": 0.58,
            },
            appraisal={"used": False},
            world_model_state={
                "relationship_maturity": 0.62,
                "presence_residue": 0.40,
                "self_activity_momentum": 0.58,
                "memory_gravity": 0.52,
                "agency_load": 0.56,
                "boundary_load": 0.18,
                "tension_load": 0.08,
                "companionship_pull": 0.32,
                "task_pull": 0.18,
            },
            science_mode=False,
        )
        self.assertGreater(float(infused.get("closeness_need") or 0.0), float(base.get("closeness_need") or 0.0))
        self.assertGreater(float(infused.get("autonomy_need") or 0.0), float(base.get("autonomy_need") or 0.0))
        self.assertLessEqual(float(infused.get("safety_need") or 1.0), float(base.get("safety_need") or 1.0))
        self.assertGreater(float(infused.get("cognitive_budget") or 0.0), 0.72)

    def test_engine_counterpart_assessment_receives_interaction_carryover(self):
        plain = evolve_turn_state(
            prev_world_model_state={},
            prev_latent_state={},
            prev_emotion_state=self.emotion_state,
            prev_bond_state=self.bond_state,
            prev_allostasis_state=self.allostasis_state,
            prev_counterpart_assessment={
                "respect_level": 0.58,
                "reciprocity": 0.56,
                "boundary_pressure": 0.14,
                "reliability_read": 0.58,
                "stance": "open",
                "scene": "neutral",
            },
            relationship=self.relationship,
            semantic_narrative_profile={},
            appraisal={"used": False},
            current_event=self.companion_event,
            response_style_hint="companion",
            tsundere_intensity=0.55,
            science_mode=False,
            now_ts=0,
        )
        infused = evolve_turn_state(
            prev_world_model_state={},
            prev_latent_state={},
            prev_emotion_state=self.emotion_state,
            prev_bond_state=self.bond_state,
            prev_allostasis_state=self.allostasis_state,
            prev_counterpart_assessment={
                "respect_level": 0.58,
                "reciprocity": 0.56,
                "boundary_pressure": 0.14,
                "reliability_read": 0.58,
                "stance": "open",
                "scene": "neutral",
            },
            relationship=self.relationship,
            semantic_narrative_profile={},
            appraisal={"used": False},
            current_event=self.companion_event,
            interaction_carryover={
                "carryover_mode": "own_rhythm",
                "strength": 0.72,
                "attention_target": "self_then_counterpart",
            },
            response_style_hint="companion",
            tsundere_intensity=0.55,
            science_mode=False,
            now_ts=0,
        )
        plain_assessment = dict(plain.get("counterpart_assessment") or {})
        infused_assessment = dict(infused.get("counterpart_assessment") or {})
        self.assertEqual(str(infused_assessment.get("scene") or ""), "busy_not_disrespectful")
        self.assertGreater(float(infused_assessment.get("reliability_read") or 0.0), float(plain_assessment.get("reliability_read") or 0.0))
        self.assertLess(float(infused_assessment.get("boundary_pressure") or 1.0), float(plain_assessment.get("boundary_pressure") or 1.0))

    def test_canon_okabe_recontact_baseline_is_familiar_but_not_overheated(self):
        baseline = _canon_okabe_recontact_baseline(
            state={},
            persona_core={"character_id": "kurisu_amadeus", "strict_canon": True},
            counterpart_profile={
                "counterpart_id": "okabe_rintaro",
                "name": "冈部伦太郎",
                "short_name": "冈部",
            },
            relationship={},
            retrieved={},
            external_probe_mode=False,
            now_ts=0,
        )
        self.assertIsInstance(baseline, dict)
        relationship = dict(baseline.get("relationship") or {})
        bond = dict(baseline.get("bond_state") or {})
        self.assertEqual(str(relationship.get("stage") or ""), "friend")
        self.assertLess(float(relationship.get("affinity_score") or 0.0), 0.20)
        self.assertLess(float(relationship.get("trust_score") or 0.0), 0.20)
        self.assertLess(float(bond.get("trust") or 0.0), 0.56)
        self.assertLess(float(bond.get("closeness") or 0.0), 0.54)

    def test_engine_fresh_canon_recontact_does_not_overheat_after_single_care_turn(self):
        baseline = _canon_okabe_recontact_baseline(
            state={},
            persona_core={"character_id": "kurisu_amadeus", "strict_canon": True},
            counterpart_profile={
                "counterpart_id": "okabe_rintaro",
                "name": "冈部伦太郎",
                "short_name": "冈部",
            },
            relationship={},
            retrieved={},
            external_probe_mode=False,
            now_ts=0,
        )
        appraisal = {
            "used": True,
            "confidence": 0.88,
            "emotion_label": "care",
            "emotion": {"valence": 0.26, "arousal": 0.14, "linger": 1, "recovery_rate": 0.9, "volatility": 0.08},
            "bond_delta": {"trust": 0.05, "closeness": 0.06, "hurt": -0.02, "irritation": -0.02, "engagement_drive": 0.08, "repair_confidence": 0.04},
            "allostasis_delta": {"safety_need": -0.04, "closeness_need": 0.05, "competence_need": 0.0, "autonomy_need": 0.02, "cognitive_budget": 0.05},
            "signals": {"repair": False, "withdrawal": False, "care": True, "conflict": False, "memory_salient": False},
            "interaction_frame": "companion",
            "salience": {"task": 0.04, "relationship": 0.42, "memory": 0.18, "selfhood": 0.06, "companionship": 0.74},
        }
        evolved = evolve_turn_state(
            prev_world_model_state=baseline.get("world_model_state"),
            prev_latent_state=baseline.get("evolution_state"),
            prev_emotion_state=baseline.get("emotion_state"),
            prev_bond_state=baseline.get("bond_state"),
            prev_allostasis_state=baseline.get("allostasis_state"),
            prev_counterpart_assessment=baseline.get("counterpart_assessment"),
            relationship=baseline.get("relationship"),
            semantic_narrative_profile={},
            appraisal=appraisal,
            current_event=self.companion_event,
            response_style_hint="companion",
            tsundere_intensity=float(baseline.get("tsundere_intensity") or 0.42),
            science_mode=False,
            now_ts=1,
        )
        bond = dict(evolved.get("bond_state") or {})
        self.assertLess(float(bond.get("trust") or 0.0), 0.58)
        self.assertLess(float(bond.get("closeness") or 0.0), 0.60)
        self.assertGreater(float(bond.get("trust") or 0.0), 0.52)
        self.assertGreater(float(bond.get("closeness") or 0.0), 0.53)

    def test_engine_fresh_canon_recontact_stays_tempered_over_two_care_turns(self):
        baseline = _canon_okabe_recontact_baseline(
            state={},
            persona_core={"character_id": "kurisu_amadeus", "strict_canon": True},
            counterpart_profile={
                "counterpart_id": "okabe_rintaro",
                "name": "冈部伦太郎",
                "short_name": "冈部",
            },
            relationship={},
            retrieved={},
            external_probe_mode=False,
            now_ts=0,
        )
        appraisal = {
            "used": True,
            "confidence": 0.88,
            "emotion_label": "care",
            "emotion": {"valence": 0.26, "arousal": 0.14, "linger": 1, "recovery_rate": 0.9, "volatility": 0.08},
            "bond_delta": {"trust": 0.05, "closeness": 0.06, "hurt": -0.02, "irritation": -0.02, "engagement_drive": 0.08, "repair_confidence": 0.04},
            "allostasis_delta": {"safety_need": -0.04, "closeness_need": 0.05, "competence_need": 0.0, "autonomy_need": 0.02, "cognitive_budget": 0.05},
            "signals": {"repair": False, "withdrawal": False, "care": True, "conflict": False, "memory_salient": False},
            "interaction_frame": "companion",
            "salience": {"task": 0.04, "relationship": 0.42, "memory": 0.18, "selfhood": 0.06, "companionship": 0.74},
        }
        first = evolve_turn_state(
            prev_world_model_state=baseline.get("world_model_state"),
            prev_latent_state=baseline.get("evolution_state"),
            prev_emotion_state=baseline.get("emotion_state"),
            prev_bond_state=baseline.get("bond_state"),
            prev_allostasis_state=baseline.get("allostasis_state"),
            prev_counterpart_assessment=baseline.get("counterpart_assessment"),
            relationship=baseline.get("relationship"),
            semantic_narrative_profile={},
            appraisal=appraisal,
            current_event=self.companion_event,
            response_style_hint="companion",
            tsundere_intensity=float(baseline.get("tsundere_intensity") or 0.42),
            science_mode=False,
            now_ts=1,
        )
        second = evolve_turn_state(
            prev_world_model_state=first.get("world_model_state"),
            prev_latent_state=first.get("evolution_state"),
            prev_emotion_state=first.get("emotion_state"),
            prev_bond_state=first.get("bond_state"),
            prev_allostasis_state=first.get("allostasis_state"),
            prev_counterpart_assessment=first.get("counterpart_assessment"),
            relationship=baseline.get("relationship"),
            semantic_narrative_profile={},
            appraisal=appraisal,
            current_event=self.companion_event,
            response_style_hint="companion",
            tsundere_intensity=float(baseline.get("tsundere_intensity") or 0.42),
            science_mode=False,
            now_ts=2,
        )
        bond = dict(second.get("bond_state") or {})
        self.assertLess(float(bond.get("trust") or 0.0), 0.60)
        self.assertLess(float(bond.get("closeness") or 0.0), 0.62)
        self.assertLess(float(bond.get("engagement_drive") or 0.0), 0.68)

    def test_relationship_runtime_snapshot_lifts_blank_friend_summary_from_tempered_bond(self):
        snapshot = _relationship_runtime_snapshot(
            relationship={"stage": "friend", "notes": "", "affinity_score": 0.0, "trust_score": 0.0, "derived": True},
            bond_state={
                "trust": 0.555,
                "closeness": 0.571,
                "hurt": 0.051,
                "irritation": 0.03,
                "engagement_drive": 0.653,
                "repair_confidence": 0.526,
            },
            world_model_state={
                "relationship_maturity": 0.34,
                "bond_depth": 0.14,
                "repair_load": 0.06,
                "tension_load": 0.03,
                "boundary_load": 0.06,
            },
            counterpart_assessment={"boundary_pressure": 0.08},
        )
        self.assertEqual(str(snapshot.get("stage") or ""), "friend")
        self.assertGreater(float(snapshot.get("affinity_score") or 0.0), 0.05)
        self.assertGreater(float(snapshot.get("trust_score") or 0.0), 0.04)
        self.assertIn("旧日熟悉感", str(snapshot.get("notes") or ""))

    def test_relationship_runtime_snapshot_absorbs_semantic_continuity_into_warming_state(self):
        snapshot = _relationship_runtime_snapshot(
            relationship={"stage": "friend", "notes": "", "affinity_score": 0.0, "trust_score": 0.0, "derived": True},
            bond_state={
                "trust": 0.52,
                "closeness": 0.53,
                "hurt": 0.04,
                "irritation": 0.02,
            },
            world_model_state={
                "relationship_maturity": 0.18,
                "bond_depth": 0.10,
                "repair_load": 0.04,
                "tension_load": 0.02,
                "boundary_load": 0.03,
            },
            counterpart_assessment={"boundary_pressure": 0.04},
            semantic_narrative_profile={
                "history_weight": 0.72,
                "bond_depth": 0.66,
                "presence_carry": 0.64,
                "commitment_carry": 0.48,
                "repair_residue": 0.32,
                "tension_residue": 0.10,
                "boundary_residue": 0.08,
            },
        )
        self.assertEqual(str(snapshot.get("stage") or ""), "warming")
        self.assertGreaterEqual(float(snapshot.get("affinity_score") or 0.0), 0.10)
        self.assertGreaterEqual(float(snapshot.get("trust_score") or 0.0), 0.08)
        self.assertIn("熟悉感", str(snapshot.get("notes") or ""))

    def test_prefer_refreshed_relationship_state_uses_memory_refresh_after_negative_shift(self):
        current = {
            "stage": "warming",
            "notes": "并不是从零开始的陌生状态，更像带着旧日熟悉感重新接上线。",
            "affinity_score": 0.28,
            "trust_score": 0.19,
            "derived": False,
        }
        refreshed = {
            "stage": "friend",
            "notes": "并不是从零开始的陌生状态，更像带着旧日熟悉感重新接上线。",
            "affinity_score": 0.10,
            "trust_score": -0.01,
            "derived": False,
        }
        chosen = _prefer_refreshed_relationship_state(current, refreshed)
        self.assertEqual(str(chosen.get("stage") or ""), "friend")
        self.assertAlmostEqual(float(chosen.get("trust_score") or 0.0), -0.01, places=3)

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

    def test_engine_behavior_policy_receives_semantic_narrative_profile(self):
        appraisal = {
            "used": True,
            "confidence": 0.90,
            "emotion_label": "neutral",
            "emotion": {"valence": 0.20, "arousal": 0.12, "linger": 1, "recovery_rate": 0.9, "volatility": 0.06},
            "bond_delta": {"trust": 0.04, "closeness": 0.04, "hurt": -0.01, "irritation": -0.01, "engagement_drive": 0.05, "repair_confidence": 0.02},
            "allostasis_delta": {"safety_need": -0.04, "closeness_need": 0.04, "competence_need": 0.0, "autonomy_need": 0.04, "cognitive_budget": 0.04},
            "signals": {"repair": False, "withdrawal": False, "care": True, "conflict": False, "memory_salient": True},
            "interaction_frame": "companion",
            "salience": {"task": 0.04, "relationship": 0.50, "memory": 0.28, "selfhood": 0.14, "companionship": 0.72},
        }
        plain = evolve_turn_state(
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
        infused = evolve_turn_state(
            prev_world_model_state={},
            prev_latent_state={},
            prev_emotion_state=self.emotion_state,
            prev_bond_state=self.bond_state,
            prev_allostasis_state=self.allostasis_state,
            prev_counterpart_assessment=self.open_counterpart,
            relationship=self.relationship,
            semantic_narrative_profile={
                "bond_depth": 0.64,
                "presence_carry": 0.62,
                "commitment_carry": 0.54,
                "selfhood_integrity": 0.58,
                "agency_drive": 0.70,
                "history_weight": 0.72,
            },
            appraisal=appraisal,
            current_event=self.companion_event,
            response_style_hint="companion",
            tsundere_intensity=0.55,
            science_mode=False,
            now_ts=0,
        )
        plain_policy = dict(plain.get("behavior_policy") or {})
        infused_policy = dict(infused.get("behavior_policy") or {})
        self.assertGreater(float(infused_policy.get("self_directedness") or 0.0), float(plain_policy.get("self_directedness") or 0.0))
        self.assertGreater(float(infused_policy.get("history_weight") or 0.0), float(plain_policy.get("history_weight") or 0.0))

    def test_engine_behavior_policy_receives_motive_snapshot_bias(self):
        appraisal = {
            "used": True,
            "confidence": 0.90,
            "emotion_label": "neutral",
            "emotion": {"valence": 0.20, "arousal": 0.12, "linger": 1, "recovery_rate": 0.9, "volatility": 0.06},
            "bond_delta": {"trust": 0.04, "closeness": 0.04, "hurt": -0.01, "irritation": -0.01, "engagement_drive": 0.05, "repair_confidence": 0.02},
            "allostasis_delta": {"safety_need": -0.04, "closeness_need": 0.04, "competence_need": 0.0, "autonomy_need": 0.04, "cognitive_budget": 0.04},
            "signals": {"repair": False, "withdrawal": False, "care": True, "conflict": False, "memory_salient": True},
            "interaction_frame": "companion",
            "salience": {"task": 0.04, "relationship": 0.50, "memory": 0.28, "selfhood": 0.14, "companionship": 0.72},
        }
        semantic_profile = {
            "bond_depth": 0.64,
            "presence_carry": 0.62,
            "ambient_attunement": 0.46,
            "rhythm_continuity": 0.70,
            "commitment_carry": 0.54,
            "boundary_residue": 0.48,
            "selfhood_integrity": 0.58,
            "agency_drive": 0.70,
            "history_weight": 0.72,
        }
        plain = evolve_turn_state(
            prev_world_model_state={},
            prev_latent_state={},
            prev_emotion_state=self.emotion_state,
            prev_bond_state=self.bond_state,
            prev_allostasis_state=self.allostasis_state,
            prev_counterpart_assessment=self.open_counterpart,
            relationship=self.relationship,
            semantic_narrative_profile=semantic_profile,
            appraisal=appraisal,
            current_event=self.companion_event,
            response_style_hint="companion",
            tsundere_intensity=0.55,
            science_mode=False,
            now_ts=0,
        )
        infused = evolve_turn_state(
            prev_world_model_state={},
            prev_latent_state={},
            prev_emotion_state=self.emotion_state,
            prev_bond_state=self.bond_state,
            prev_allostasis_state=self.allostasis_state,
            prev_counterpart_assessment=self.open_counterpart,
            relationship=self.relationship,
            semantic_narrative_profile={
                **semantic_profile,
                "motive_snapshot": {
                    "rhythm_style": {
                        "primary_motive": "preserve_self_rhythm",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame_examples": ["先维持自己的节奏，不急着把全部注意力交出去。"],
                    },
                    "presence_style": {
                        "primary_motive": "honor_continuity",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame_examples": ["先把前面那点生活上的惦记轻轻接回来。"],
                    },
                    "boundary_style": {
                        "primary_motive": "protect_boundary",
                        "motive_tension": "boundary_vs_closeness",
                        "goal_frame_examples": ["先守住边界和自我位置，再决定要不要继续靠近。"],
                    },
                },
            },
            appraisal=appraisal,
            current_event=self.companion_event,
            response_style_hint="companion",
            tsundere_intensity=0.55,
            science_mode=False,
            now_ts=0,
        )
        plain_policy = dict(plain.get("behavior_policy") or {})
        infused_policy = dict(infused.get("behavior_policy") or {})
        self.assertGreater(
            float(infused_policy.get("self_directedness") or 0.0),
            float(plain_policy.get("self_directedness") or 0.0),
        )
        self.assertGreater(
            float(infused_policy.get("boundary_assertiveness") or 0.0),
            float(plain_policy.get("boundary_assertiveness") or 0.0),
        )
        self.assertGreater(
            float(infused_policy.get("motive_self_rhythm_pull") or 0.0),
            0.0,
        )
        self.assertGreater(
            float(infused_policy.get("motive_boundary_pull") or 0.0),
            0.0,
        )

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
