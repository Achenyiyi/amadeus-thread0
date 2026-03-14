import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from amadeus_thread0.memory_store import MemoryStore
from amadeus_thread0.evolution_engine.policy import build_behavior_policy
from amadeus_thread0.evolution_engine.worldline import build_world_model_state
from amadeus_thread0.graph import (
    _behavior_action_from_state,
    _behavior_agenda_entry_from_plan,
    _behavior_plan_from_action,
    _compact_semantic_narrative_hint,
    _normalize_behavior_agenda,
    _normalize_event_override,
    _promote_due_behavior_plan_event,
    _record_semantic_self_evidence,
    _refresh_semantic_self_narratives,
    _semantic_narrative_appraisal_hint,
    _semantic_narrative_profile,
    _semantic_self_evidence_records,
)


class WorldModelResidueTests(unittest.TestCase):
    def test_semantic_self_evidence_emits_presence_ambient_and_rhythm_style(self):
        records = _semantic_self_evidence_records(
            user_text="刚才那阵风过去之后，我还是能感觉到你就在这儿。你是在忙自己的事吗？",
            appraisal={
                "used": True,
                "interaction_frame": "relationship",
                "signals": {
                    "memory_salient": True,
                },
                "salience": {
                    "relationship": 0.44,
                    "companionship": 0.52,
                    "selfhood": 0.12,
                },
            },
            emotion_state={"label": "neutral"},
            bond_state={
                "trust": 0.64,
                "closeness": 0.62,
                "hurt": 0.02,
            },
            current_event={
                "kind": "user_utterance",
                "tags": ["ambient", "ambient_echo"],
            },
            world_model_state={
                "presence_residue": 0.61,
                "ambient_resonance": 0.58,
                "self_activity_momentum": 0.72,
            },
        )
        categories = {str(item.get("category") or "") for item in records}
        self.assertIn("presence_style", categories)
        self.assertIn("ambient_style", categories)
        self.assertIn("rhythm_style", categories)

    def test_semantic_narrative_profile_surfaces_residue_styles(self):
        items = [
            {
                "category": "presence_style",
                "text": "她不会把每次重新靠近都当成从零开始。",
                "stability": 0.70,
                "support_count": 3,
                "sedimentation_score": 0.68,
                "persistence_score": 0.74,
                "residue_score": 0.62,
                "integration_score": 0.66,
                "support_span_s": 2 * 24 * 3600,
                "reactivation_cadence_score": 0.52,
                "last_supported_at": 1_000,
                "horizon_tag": "consolidating",
            },
            {
                "category": "ambient_style",
                "text": "环境里的风声和光线会自然带进她的注意力。",
                "stability": 0.68,
                "support_count": 2,
                "sedimentation_score": 0.64,
                "persistence_score": 0.70,
                "residue_score": 0.60,
                "integration_score": 0.63,
                "support_span_s": 2 * 24 * 3600,
                "reactivation_cadence_score": 0.48,
                "last_supported_at": 1_000,
                "horizon_tag": "consolidating",
            },
            {
                "category": "rhythm_style",
                "text": "她会把自己的内部节奏延续到下一轮。",
                "stability": 0.74,
                "support_count": 4,
                "sedimentation_score": 0.72,
                "persistence_score": 0.78,
                "residue_score": 0.66,
                "integration_score": 0.70,
                "support_span_s": 3 * 24 * 3600,
                "reactivation_cadence_score": 0.56,
                "last_supported_at": 1_000,
                "horizon_tag": "long_term",
            },
        ]
        profile = _semantic_narrative_profile(
            items,
            user_text="刚才风一吹过去，我还在想你是不是正忙着别的事。",
            current_event={
                "kind": "user_utterance",
                "tags": ["ambient_echo"],
                "created_at": 2_000,
            },
        )
        self.assertGreater(float(profile.get("presence_carry", 0.0) or 0.0), 0.45)
        self.assertGreater(float(profile.get("ambient_attunement", 0.0) or 0.0), 0.42)
        self.assertGreater(float(profile.get("rhythm_continuity", 0.0) or 0.0), 0.48)
        residue_snapshot = profile.get("residue_snapshot") if isinstance(profile.get("residue_snapshot"), dict) else {}
        self.assertGreater(float(residue_snapshot.get("presence_style", 0.0) or 0.0), 0.0)
        self.assertGreater(float(residue_snapshot.get("ambient_style", 0.0) or 0.0), 0.0)
        self.assertGreater(float(residue_snapshot.get("rhythm_style", 0.0) or 0.0), 0.0)

    def test_semantic_narratives_bias_world_model_residue(self):
        semantic_profile = _semantic_narrative_profile(
            [
                {
                    "category": "presence_style",
                    "text": "她不会把重新靠近当成从零开始。",
                    "stability": 0.70,
                    "support_count": 3,
                    "sedimentation_score": 0.68,
                    "persistence_score": 0.74,
                    "residue_score": 0.62,
                    "integration_score": 0.66,
                    "support_span_s": 2 * 24 * 3600,
                    "reactivation_cadence_score": 0.52,
                    "last_supported_at": 1_000,
                    "horizon_tag": "consolidating",
                },
                {
                    "category": "ambient_style",
                    "text": "环境里的细小变化会留在她的感知里。",
                    "stability": 0.68,
                    "support_count": 2,
                    "sedimentation_score": 0.64,
                    "persistence_score": 0.70,
                    "residue_score": 0.60,
                    "integration_score": 0.63,
                    "support_span_s": 2 * 24 * 3600,
                    "reactivation_cadence_score": 0.48,
                    "last_supported_at": 1_000,
                    "horizon_tag": "consolidating",
                },
                {
                    "category": "rhythm_style",
                    "text": "她会把自己的节奏延续到下一轮开口前。",
                    "stability": 0.74,
                    "support_count": 4,
                    "sedimentation_score": 0.72,
                    "persistence_score": 0.78,
                    "residue_score": 0.66,
                    "integration_score": 0.70,
                    "support_span_s": 3 * 24 * 3600,
                    "reactivation_cadence_score": 0.56,
                    "last_supported_at": 1_000,
                    "horizon_tag": "long_term",
                },
            ],
            user_text="刚才那阵风过去之后，我想问你是不是又从自己的思路里抬头看我了。",
            current_event={
                "kind": "user_utterance",
                "tags": ["ambient", "ambient_echo"],
                "created_at": 2_000,
            },
        )
        current_event = {
            "kind": "user_utterance",
            "tags": ["ambient", "ambient_echo"],
        }
        appraisal = {
            "used": True,
            "salience": {
                "relationship": 0.36,
                "companionship": 0.42,
                "memory": 0.34,
                "task": 0.22,
            },
            "signals": {
                "memory_salient": True,
            },
        }
        baseline = build_world_model_state(
            prev_state=None,
            relationship={"affinity_score": 0.62, "trust_score": 0.64},
            semantic_narrative_profile={},
            appraisal=appraisal,
            current_event=current_event,
            science_mode=False,
            now_ts=2_000,
        )
        enriched = build_world_model_state(
            prev_state=None,
            relationship={"affinity_score": 0.62, "trust_score": 0.64},
            semantic_narrative_profile=semantic_profile,
            appraisal=appraisal,
            current_event=current_event,
            science_mode=False,
            now_ts=2_000,
        )
        self.assertGreater(
            float(enriched.get("presence_residue", 0.0) or 0.0),
            float(baseline.get("presence_residue", 0.0) or 0.0),
        )
        self.assertGreater(
            float(enriched.get("ambient_resonance", 0.0) or 0.0),
            float(baseline.get("ambient_resonance", 0.0) or 0.0),
        )
        self.assertGreater(
            float(enriched.get("self_activity_momentum", 0.0) or 0.0),
            float(baseline.get("self_activity_momentum", 0.0) or 0.0),
        )

    def test_semantic_evidence_refresh_pipeline_builds_narrative_profile(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                store.set_relationship(
                    {
                        "stage": "warming",
                        "notes": "逐渐熟悉起来。",
                        "affinity_score": 0.72,
                        "trust_score": 0.74,
                    }
                )
                wrote = _record_semantic_self_evidence(
                    store,
                    user_text="刚才风吹过去的时候，我还是能感觉到你就在。你是从自己的节奏里抬头看我了吗？",
                    appraisal={
                        "used": True,
                        "interaction_frame": "relationship",
                        "signals": {
                            "memory_salient": True,
                        },
                        "salience": {
                            "relationship": 0.46,
                            "companionship": 0.54,
                            "selfhood": 0.10,
                        },
                    },
                    emotion_state={"label": "neutral"},
                    bond_state={
                        "trust": 0.66,
                        "closeness": 0.64,
                        "hurt": 0.02,
                    },
                    current_event={
                        "kind": "user_utterance",
                        "tags": ["ambient", "ambient_echo"],
                    },
                    world_model_state={
                        "presence_residue": 0.64,
                        "ambient_resonance": 0.60,
                        "self_activity_momentum": 0.74,
                    },
                    source="test:semantic_pipeline",
                )
                self.assertTrue(wrote)
                _refresh_semantic_self_narratives(store, source="test:semantic_pipeline")
                narratives = store.list_semantic_self_narratives(limit=12)
                categories = {str(item.get("category") or "") for item in narratives}
                self.assertIn("presence_style", categories)
                self.assertIn("ambient_style", categories)
                self.assertIn("rhythm_style", categories)
                profile = _semantic_narrative_profile(
                    narratives,
                    user_text="刚才你安静了一会儿，我还是能接住你的在场感。",
                    current_event={
                        "kind": "user_utterance",
                        "tags": ["ambient_echo"],
                        "created_at": 2_000,
                    },
                )
                self.assertGreater(float(profile.get("presence_carry", 0.0) or 0.0), 0.0)
                self.assertGreater(float(profile.get("ambient_attunement", 0.0) or 0.0), 0.0)
                self.assertGreater(float(profile.get("rhythm_continuity", 0.0) or 0.0), 0.0)
            finally:
                store.close()

    def test_semantic_hint_mentions_presence_ambient_and_rhythm(self):
        profile = {
            "presence_carry": 0.58,
            "ambient_attunement": 0.46,
            "rhythm_continuity": 0.63,
            "summary_lines": [],
            "top_narratives": [],
        }
        compact_hint = _compact_semantic_narrative_hint(profile)
        appraisal_hint = _semantic_narrative_appraisal_hint(profile)
        self.assertIn("在场感", compact_hint)
        self.assertIn("环境", compact_hint)
        self.assertIn("内部节奏", compact_hint)
        self.assertIn("环境回声", appraisal_hint)
        self.assertIn("内部节奏", appraisal_hint)

    def test_continuity_axes_do_not_reset_across_plain_followup_turns(self):
        semantic_profile = _semantic_narrative_profile(
            [
                {
                    "category": "presence_style",
                    "text": "她不会把重新靠近当成从零开始。",
                    "stability": 0.72,
                    "support_count": 4,
                    "sedimentation_score": 0.70,
                    "persistence_score": 0.76,
                    "residue_score": 0.64,
                    "integration_score": 0.68,
                    "support_span_s": 3 * 24 * 3600,
                    "reactivation_cadence_score": 0.54,
                    "last_supported_at": 1_000,
                    "horizon_tag": "long_term",
                },
                {
                    "category": "ambient_style",
                    "text": "环境里的细小变化会留在她的感知里。",
                    "stability": 0.68,
                    "support_count": 3,
                    "sedimentation_score": 0.66,
                    "persistence_score": 0.72,
                    "residue_score": 0.62,
                    "integration_score": 0.64,
                    "support_span_s": 2 * 24 * 3600,
                    "reactivation_cadence_score": 0.50,
                    "last_supported_at": 1_000,
                    "horizon_tag": "consolidating",
                },
                {
                    "category": "rhythm_style",
                    "text": "她会把自己的节奏延续到下一轮开口前。",
                    "stability": 0.74,
                    "support_count": 4,
                    "sedimentation_score": 0.72,
                    "persistence_score": 0.78,
                    "residue_score": 0.66,
                    "integration_score": 0.70,
                    "support_span_s": 3 * 24 * 3600,
                    "reactivation_cadence_score": 0.56,
                    "last_supported_at": 1_000,
                    "horizon_tag": "long_term",
                },
            ],
            user_text="刚才那阵风过去之后，我还在想你是不是从自己的思路里抬头看了我一眼。",
            current_event={
                "kind": "user_utterance",
                "tags": ["ambient", "ambient_echo"],
                "created_at": 2_000,
            },
        )
        warm_appraisal = {
            "used": True,
            "salience": {
                "relationship": 0.40,
                "companionship": 0.46,
                "memory": 0.30,
                "task": 0.24,
            },
            "signals": {
                "memory_salient": True,
            },
        }
        plain_followup_appraisal = {
            "used": True,
            "salience": {
                "relationship": 0.16,
                "companionship": 0.18,
                "memory": 0.04,
                "task": 0.12,
            },
            "signals": {},
        }
        relationship = {"affinity_score": 0.62, "trust_score": 0.64}
        first_with_continuity = build_world_model_state(
            prev_state=None,
            relationship=relationship,
            semantic_narrative_profile=semantic_profile,
            appraisal=warm_appraisal,
            current_event={"kind": "user_utterance", "tags": ["ambient", "ambient_echo"]},
            science_mode=False,
            now_ts=2_000,
        )
        second_with_continuity = build_world_model_state(
            prev_state=first_with_continuity,
            relationship=relationship,
            semantic_narrative_profile=semantic_profile,
            appraisal=plain_followup_appraisal,
            current_event={"kind": "user_utterance", "tags": []},
            science_mode=False,
            now_ts=2_060,
        )
        first_without_continuity = build_world_model_state(
            prev_state=None,
            relationship=relationship,
            semantic_narrative_profile={},
            appraisal=warm_appraisal,
            current_event={"kind": "user_utterance", "tags": ["ambient", "ambient_echo"]},
            science_mode=False,
            now_ts=2_000,
        )
        second_without_continuity = build_world_model_state(
            prev_state=first_without_continuity,
            relationship=relationship,
            semantic_narrative_profile={},
            appraisal=plain_followup_appraisal,
            current_event={"kind": "user_utterance", "tags": []},
            science_mode=False,
            now_ts=2_060,
        )
        self.assertGreater(
            float(second_with_continuity.get("presence_residue", 0.0) or 0.0),
            float(second_without_continuity.get("presence_residue", 0.0) or 0.0),
        )
        self.assertGreater(
            float(second_with_continuity.get("ambient_resonance", 0.0) or 0.0),
            float(second_without_continuity.get("ambient_resonance", 0.0) or 0.0),
        )
        self.assertGreater(
            float(second_with_continuity.get("self_activity_momentum", 0.0) or 0.0),
            float(second_without_continuity.get("self_activity_momentum", 0.0) or 0.0),
        )
        self.assertGreater(float(second_with_continuity.get("presence_residue", 0.0) or 0.0), 0.08)
        self.assertGreater(float(second_with_continuity.get("ambient_resonance", 0.0) or 0.0), 0.06)
        self.assertGreater(float(second_with_continuity.get("self_activity_momentum", 0.0) or 0.0), 0.10)

    def test_gesture_event_builds_presence_residue(self):
        state = build_world_model_state(
            prev_state=None,
            relationship=None,
            semantic_narrative_profile=None,
            appraisal=None,
            current_event={
                "kind": "gesture_signal",
                "tags": ["vision", "gesture", "presence_ping"],
            },
            science_mode=False,
            now_ts=1,
        )
        self.assertGreater(float(state.get("presence_residue", 0.0) or 0.0), 0.45)

    def test_ambient_event_builds_ambient_resonance(self):
        state = build_world_model_state(
            prev_state=None,
            relationship=None,
            semantic_narrative_profile=None,
            appraisal=None,
            current_event={
                "kind": "ambient_shift",
                "tags": ["ambient"],
            },
            science_mode=False,
            now_ts=1,
        )
        self.assertGreater(float(state.get("ambient_resonance", 0.0) or 0.0), 0.45)

    def test_self_activity_momentum_persists_into_next_user_turn(self):
        first = build_world_model_state(
            prev_state=None,
            relationship=None,
            semantic_narrative_profile=None,
            appraisal=None,
            current_event={
                "kind": "self_activity_state",
                "tags": ["self_activity", "own_task", "deep_focus"],
            },
            science_mode=False,
            now_ts=1,
        )
        second = build_world_model_state(
            prev_state=first,
            relationship=None,
            semantic_narrative_profile=None,
            appraisal=None,
            current_event={
                "kind": "user_utterance",
                "tags": [],
            },
            science_mode=False,
            now_ts=2,
        )
        self.assertGreater(float(first.get("self_activity_momentum", 0.0) or 0.0), 0.45)
        self.assertGreater(float(second.get("self_activity_momentum", 0.0) or 0.0), 0.20)

    def test_behavior_action_reads_self_activity_momentum(self):
        world_model_state = {
            "self_activity_momentum": 0.78,
            "presence_residue": 0.18,
            "ambient_resonance": 0.10,
            "bond_depth": 0.56,
            "companionship_pull": 0.46,
            "task_pull": 0.22,
            "boundary_load": 0.08,
            "agency_load": 0.52,
            "selfhood_load": 0.24,
            "memory_gravity": 0.18,
            "tension_load": 0.08,
            "relationship_maturity": 0.62,
            "repair_load": 0.12,
        }
        behavior_policy = build_behavior_policy(
            response_style_hint="natural",
            emotion_state={"label": "neutral"},
            bond_state={
                "trust": 0.66,
                "closeness": 0.62,
                "hurt": 0.02,
                "irritation": 0.04,
                "engagement_drive": 0.58,
            },
            allostasis_state={
                "safety_need": 0.14,
                "autonomy_need": 0.22,
                "cognitive_budget": 0.72,
            },
            counterpart_assessment={
                "boundary_pressure": 0.08,
                "stance": "open",
            },
            world_model_state=world_model_state,
            latent_state={
                "agency_pressure": 0.44,
                "expression_freedom": 0.68,
                "self_coherence": 0.74,
            },
            tsundere_intensity=0.44,
            science_mode=False,
        )
        action = _behavior_action_from_state(
            current_event={"kind": "user_utterance", "tags": []},
            response_style_hint="natural",
            user_text="在干嘛？",
            science_mode=False,
            emotion_state={"label": "neutral"},
            bond_state={
                "trust": 0.66,
                "closeness": 0.62,
                "hurt": 0.02,
                "irritation": 0.04,
                "engagement_drive": 0.58,
            },
            allostasis_state={
                "safety_need": 0.14,
                "autonomy_need": 0.22,
                "cognitive_budget": 0.72,
            },
            counterpart_assessment={
                "boundary_pressure": 0.08,
                "reliability_read": 0.66,
                "stance": "open",
            },
            semantic_narrative_profile={},
            behavior_policy=behavior_policy,
            world_model_state=world_model_state,
            interaction_carryover={},
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "self_activity_reopen")

    def test_behavior_plan_captures_carryover_snapshot(self):
        plan = _behavior_plan_from_action(
            {"kind": "time_idle", "event_frame": "idle", "tags": ["quiet_presence"], "idle_minutes": 18},
            {
                "action_target": "hold_own_rhythm",
                "interaction_mode": "brief_presence",
                "initiative_level": 0.31,
                "deferred_action_family": "none",
                "timing_window_min": 18,
                "attention_target": "self_then_counterpart",
                "nonverbal_signal": "resume_task",
                "channel": "none",
            },
            world_model_state={
                "self_activity_momentum": 0.74,
                "presence_residue": 0.34,
                "ambient_resonance": 0.28,
            },
        )
        self.assertEqual(str(plan.get("kind") or ""), "self_activity_continue")
        self.assertEqual(str(plan.get("carryover_mode") or ""), "own_rhythm")
        self.assertAlmostEqual(float(plan.get("carryover_strength") or 0.0), 0.74, places=3)
        self.assertEqual(str(plan.get("attention_target") or ""), "self_then_counterpart")
        self.assertEqual(str(plan.get("nonverbal_signal") or ""), "resume_task")
        self.assertAlmostEqual(float(plan.get("presence_residue") or 0.0), 0.34, places=3)
        self.assertAlmostEqual(float(plan.get("ambient_resonance") or 0.0), 0.28, places=3)
        self.assertAlmostEqual(float(plan.get("self_activity_momentum") or 0.0), 0.74, places=3)

    def test_behavior_agenda_preserves_carryover_fields(self):
        plan = {
            "kind": "self_activity_continue",
            "target": "self",
            "scheduled_after_min": 18,
            "trigger_family": "none",
            "allow_interrupt": True,
            "note": "先回到自己的节奏里。",
            "carryover_mode": "own_rhythm",
            "carryover_strength": 0.74,
            "attention_target": "self_then_counterpart",
            "nonverbal_signal": "resume_task",
            "presence_residue": 0.34,
            "ambient_resonance": 0.28,
            "self_activity_momentum": 0.74,
        }
        entry = _behavior_agenda_entry_from_plan({"kind": "time_idle"}, plan)
        self.assertIsNotNone(entry)
        normalized = _normalize_behavior_agenda([entry])
        self.assertEqual(len(normalized), 1)
        agenda_entry = normalized[0]
        self.assertEqual(str(agenda_entry.get("carryover_mode") or ""), "own_rhythm")
        self.assertAlmostEqual(float(agenda_entry.get("carryover_strength") or 0.0), 0.74, places=3)
        self.assertEqual(str(agenda_entry.get("attention_target") or ""), "self_then_counterpart")
        self.assertEqual(str(agenda_entry.get("nonverbal_signal") or ""), "resume_task")
        self.assertAlmostEqual(float(agenda_entry.get("presence_residue") or 0.0), 0.34, places=3)
        self.assertAlmostEqual(float(agenda_entry.get("ambient_resonance") or 0.0), 0.28, places=3)
        self.assertAlmostEqual(float(agenda_entry.get("self_activity_momentum") or 0.0), 0.74, places=3)

    def test_promoted_self_activity_event_keeps_carryover_hints(self):
        promoted = _promote_due_behavior_plan_event(
            {"kind": "time_idle", "idle_minutes": 20, "tags": ["quiet_presence"]},
            {
                "kind": "self_activity_continue",
                "scheduled_after_min": 18,
                "trigger_family": "none",
                "note": "她先回到自己的节奏里。",
                "carryover_mode": "own_rhythm",
                "carryover_strength": 0.74,
                "attention_target": "self_then_counterpart",
                "nonverbal_signal": "resume_task",
                "presence_residue": 0.34,
                "ambient_resonance": 0.28,
                "self_activity_momentum": 0.74,
            },
        )
        self.assertEqual(str(promoted.get("kind") or ""), "self_activity_state")
        self.assertIn("self_activity", promoted.get("tags") or [])
        normalized = _normalize_event_override(promoted, counterpart_name="冈部伦太郎")
        self.assertEqual(str(normalized.get("carryover_mode") or ""), "own_rhythm")
        self.assertAlmostEqual(float(normalized.get("carryover_strength") or 0.0), 0.74, places=3)
        self.assertEqual(str(normalized.get("attention_target_hint") or ""), "self_then_counterpart")
        self.assertEqual(str(normalized.get("nonverbal_signal_hint") or ""), "resume_task")

    def test_promoted_deferred_checkin_keeps_ambient_carryover(self):
        promoted = _promote_due_behavior_plan_event(
            {"kind": "time_idle", "idle_minutes": 14, "tags": ["late_night"]},
            {
                "kind": "deferred_checkin",
                "scheduled_after_min": 12,
                "trigger_family": "light_checkin",
                "note": "刚才那阵风掠过去之后，她又想起你。",
                "carryover_mode": "ambient_echo",
                "carryover_strength": 0.41,
                "attention_target": "ambient_cue",
                "nonverbal_signal": "thought_glance",
                "presence_residue": 0.16,
                "ambient_resonance": 0.47,
                "self_activity_momentum": 0.22,
            },
        )
        self.assertEqual(str(promoted.get("kind") or ""), "scheduled_checkin_due")
        self.assertIn("ambient_echo", promoted.get("tags") or [])
        normalized = _normalize_event_override(promoted, counterpart_name="冈部伦太郎")
        self.assertEqual(str(normalized.get("carryover_mode") or ""), "ambient_echo")
        self.assertAlmostEqual(float(normalized.get("carryover_strength") or 0.0), 0.47, places=3)
        self.assertEqual(str(normalized.get("attention_target_hint") or ""), "ambient_cue")
        self.assertEqual(str(normalized.get("nonverbal_signal_hint") or ""), "thought_glance")


if __name__ == "__main__":
    unittest.main()
