import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from amadeus_thread0.memory_store import MemoryStore
from amadeus_thread0.evolution_engine.policy import build_behavior_policy
from amadeus_thread0.evolution_engine.worldline import build_world_model_state
from amadeus_thread0.graph import (
    _behavior_action_from_state,
    _behavior_agenda_entry_from_plan,
    _behavior_agenda_next_recheck_min,
    _behavior_agenda_should_release,
    _behavior_plan_from_action,
    _compact_interaction_carryover_hint,
    _compact_semantic_narrative_hint,
    _normalize_behavior_agenda,
    _normalize_event_override,
    _passive_evolution_memory_update,
    _recent_interaction_carryover,
    _promote_due_behavior_agenda_event,
    _promote_due_behavior_plan_event,
    _promote_due_behavior_action_event,
    _record_semantic_self_evidence,
    _refresh_semantic_self_narratives,
    _semantic_narrative_appraisal_hint,
    _semantic_narrative_profile,
    _semantic_self_evidence_records,
)


class WorldModelResidueTests(unittest.TestCase):
    def _run_passive_repair_turn(
        self,
        store: MemoryStore,
        *,
        user_text: str,
        hurt: float = 0.24,
        irritation: float = 0.16,
        repair_confidence: float = 0.58,
    ) -> bool:
        return _passive_evolution_memory_update(
            store,
            user_text=user_text,
            appraisal={
                "used": True,
                "confidence": 0.84,
                "interaction_frame": "relationship",
                "emotion_label": "hurt" if hurt >= 0.18 else "care",
                "signals": {
                    "care": False,
                    "repair": True,
                    "conflict": False,
                    "withdrawal": False,
                    "memory_salient": True,
                },
                "salience": {
                    "relationship": 0.76,
                    "companionship": 0.54,
                    "selfhood": 0.20,
                    "task": 0.04,
                },
            },
            emotion_state={"label": "hurt" if hurt >= 0.18 else "care"},
            bond_state={
                "trust": 0.42,
                "closeness": 0.40,
                "hurt": hurt,
                "irritation": irritation,
                "repair_confidence": repair_confidence,
            },
            current_event={"kind": "user_utterance"},
            world_model_state={
                "relationship_maturity": 0.28,
                "bond_depth": 0.16,
            },
        )

    def test_refresh_semantic_narratives_marks_bond_style_contested_under_negative_evidence(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memory.json")
            try:
                store.add_semantic_self_narrative(
                    text="红莉栖和冈部的共同历史已经很稳，会自然带进默认语气里。",
                    category="bond_style",
                    stability=0.82,
                    confidence=0.84,
                    metadata={
                        "support_count": 4,
                        "refresh_count": 4,
                        "consolidation_count": 4,
                        "sedimentation_score": 0.80,
                        "persistence_score": 0.84,
                        "residue_score": 0.72,
                        "integration_score": 0.76,
                        "first_supported_at": 1,
                        "last_supported_at": 10,
                        "last_meaningful_refresh_at": 10,
                        "last_reactivated_at": 10,
                        "support_span_s": 5 * 24 * 3600,
                        "reactivation_gap_s": 0,
                        "reactivation_hits": 2,
                        "reactivation_rate_per_day": 1.2,
                        "reactivation_cadence_score": 0.62,
                        "horizon_tag": "long_term",
                        "support_signature": "bond_style|old|count=4",
                        "decay_rate_per_day": 0.045,
                        "decay_resistance": 0.76,
                    },
                )
                store.add_relationship_timeline("上次那件事我还是很介意。", affinity_delta=-0.28, trust_delta=-0.24, confidence=0.86)
                store.add_unresolved_tension(summary="这件事还没真正说开。", severity=0.82, confidence=0.88)
                _refresh_semantic_self_narratives(store, source="test:contradiction")
                narratives = store.list_semantic_self_narratives(limit=12)
                bond = next(item for item in narratives if str(item.get("category") or "") == "bond_style")
                self.assertGreater(float(bond.get("contradiction_pressure") or 0.0), 0.20)
                self.assertTrue(bool(bond.get("contested")))
                self.assertIn("open_tension", bond.get("contradiction_factors") or [])
                self.assertLess(float(bond.get("persistence_score") or 0.0), 0.84)
            finally:
                store.close()

    def test_dormant_tension_narrative_weakens_after_repairs(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memory.json")
            try:
                tension = store.add_semantic_self_narrative(
                    text="之前的别扭余波还会继续卡在后面的几轮里。",
                    category="tension_style",
                    stability=0.78,
                    confidence=0.80,
                    metadata={
                        "support_count": 3,
                        "refresh_count": 3,
                        "consolidation_count": 3,
                        "sedimentation_score": 0.76,
                        "persistence_score": 0.80,
                        "residue_score": 0.70,
                        "integration_score": 0.72,
                        "first_supported_at": 1,
                        "last_supported_at": 10,
                        "last_meaningful_refresh_at": 10,
                        "last_reactivated_at": 10,
                        "support_span_s": 3 * 24 * 3600,
                        "reactivation_gap_s": 0,
                        "reactivation_hits": 1,
                        "reactivation_rate_per_day": 1.0,
                        "reactivation_cadence_score": 0.56,
                        "horizon_tag": "long_term",
                        "support_signature": "tension_style|old|count=3",
                        "decay_rate_per_day": 0.12,
                        "decay_resistance": 0.70,
                    },
                )
                store.add_conflict_repair(summary="这次已经认真说开了。", confidence=0.84)
                store.add_revision_trace(
                    namespace="unresolved_tensions",
                    target_id="1",
                    before_summary="之前卡着的那件事",
                    after_summary="已经说开",
                    reason="manual_resolve",
                    operator="test",
                    source="test:repair",
                )
                _refresh_semantic_self_narratives(store, source="test:repair")
                narratives = store.list_semantic_self_narratives(limit=12)
                updated = next(item for item in narratives if int(item.get("id") or 0) == int(tension.get("id") or 0))
                self.assertGreater(float(updated.get("contradiction_pressure") or 0.0), 0.20)
                self.assertIn("repair_resolution", updated.get("contradiction_factors") or [])
                self.assertLess(float(updated.get("persistence_score") or 0.0), 0.80)
                self.assertIn(str(updated.get("horizon_tag") or ""), {"long_term", "consolidating"})
            finally:
                store.close()

    def test_passive_evolution_updates_semantic_narratives_from_self_activity_event(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memory.json")
            try:
                wrote = _passive_evolution_memory_update(
                    store,
                    user_text="",
                    appraisal={
                        "used": True,
                        "confidence": 0.82,
                        "interaction_frame": "companion",
                        "signals": {},
                        "salience": {
                            "relationship": 0.22,
                            "companionship": 0.36,
                            "selfhood": 0.18,
                            "task": 0.28,
                        },
                    },
                    emotion_state={"label": "neutral"},
                    bond_state={
                        "trust": 0.62,
                        "closeness": 0.60,
                        "hurt": 0.02,
                    },
                    current_event={
                        "kind": "self_activity_state",
                        "tags": ["self_activity", "own_task", "deep_focus", "small_opening"],
                    },
                    world_model_state={
                        "presence_residue": 0.18,
                        "ambient_resonance": 0.10,
                        "self_activity_momentum": 0.76,
                    },
                )
                self.assertTrue(wrote)
                narratives = store.list_semantic_self_narratives(limit=12)
                categories = {str(item.get("category") or "") for item in narratives}
                self.assertIn("agency_style", categories)
                self.assertIn("rhythm_style", categories)
            finally:
                store.close()

    def test_passive_evolution_seeds_light_relationship_timeline_for_familiarity_probe(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memory.json")
            try:
                wrote = _passive_evolution_memory_update(
                    store,
                    user_text="你还记得我吗？",
                    appraisal={
                        "used": True,
                        "confidence": 0.84,
                        "interaction_frame": "companion",
                        "signals": {
                            "care": False,
                            "repair": False,
                            "conflict": False,
                            "withdrawal": False,
                        },
                        "salience": {
                            "relationship": 0.42,
                            "companionship": 0.48,
                            "selfhood": 0.12,
                            "task": 0.06,
                        },
                    },
                    emotion_state={"label": "neutral"},
                    bond_state={
                        "trust": 0.556,
                        "closeness": 0.579,
                        "hurt": 0.04,
                        "irritation": 0.02,
                        "repair_confidence": 0.52,
                    },
                    current_event={
                        "kind": "user_utterance",
                    },
                    world_model_state={
                        "relationship_maturity": 0.34,
                        "bond_depth": 0.14,
                    },
                )
                self.assertTrue(wrote)
                timeline = store.list_relationship_timeline(limit=8)
                self.assertEqual(len(timeline), 1)
                item = timeline[0]
                self.assertIn("重新确认彼此的熟悉感", str(item.get("summary") or ""))
                self.assertAlmostEqual(float(item.get("affinity_delta") or 0.0), 0.04, places=3)
                self.assertAlmostEqual(float(item.get("trust_delta") or 0.0), 0.03, places=3)
            finally:
                store.close()

    def test_partial_repair_does_not_immediately_restore_relationship(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memory.json")
            try:
                store.add_relationship_timeline(
                    "上次那件事让我还是有点介意。",
                    affinity_delta=-0.22,
                    trust_delta=-0.18,
                    confidence=0.86,
                )
                store.add_unresolved_tension(
                    summary="那次争执的余波还在。",
                    severity=0.78,
                    confidence=0.84,
                )

                wrote = self._run_passive_repair_turn(
                    store,
                    user_text="嗯，这样就好，至少不用像陌生人一样重新试探。",
                    hurt=0.26,
                    irritation=0.18,
                    repair_confidence=0.60,
                )

                self.assertTrue(wrote)
                timeline = store.list_relationship_timeline(limit=4)
                self.assertEqual(len(timeline), 2)
                latest = timeline[0]
                self.assertLessEqual(float(latest.get("affinity_delta") or 0.0), 0.08)
                self.assertLessEqual(float(latest.get("trust_delta") or 0.0), 0.06)

                relationship = store.get_relationship()
                self.assertEqual(str(relationship.get("stage") or ""), "friend")
                self.assertLess(float(relationship.get("trust_score") or 0.0), 0.0)

                tensions = store.list_unresolved_tensions(limit=4)
                self.assertEqual(str(tensions[0].get("status") or "open"), "open")
            finally:
                store.close()

    def test_repeated_soft_repairs_improve_relationship_gradually(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memory.json")
            try:
                store.add_relationship_timeline(
                    "你前面那句确实有点伤人。",
                    affinity_delta=-0.24,
                    trust_delta=-0.22,
                    confidence=0.88,
                )
                store.add_unresolved_tension(
                    summary="这次的不愉快还没有完全过去。",
                    severity=0.80,
                    confidence=0.86,
                )

                self._run_passive_repair_turn(
                    store,
                    user_text="先别把气氛又弄回去，至少现在能继续说话了。",
                    hurt=0.24,
                    irritation=0.16,
                    repair_confidence=0.58,
                )
                first = store.get_relationship()

                self._run_passive_repair_turn(
                    store,
                    user_text="好吧，继续说，但别又退成那种很远的感觉。",
                    hurt=0.18,
                    irritation=0.12,
                    repair_confidence=0.64,
                )
                second = store.get_relationship()
                second_latest = next(
                    item
                    for item in store.list_relationship_timeline(limit=6)
                    if str(item.get("summary") or "") == "好吧，继续说，但别又退成那种很远的感觉。"
                )

                self._run_passive_repair_turn(
                    store,
                    user_text="至少这次没有把我继续往外推，这点算你补回来一点。",
                    hurt=0.14,
                    irritation=0.08,
                    repair_confidence=0.70,
                )
                third = store.get_relationship()

                self.assertEqual(str(first.get("stage") or ""), "friend")
                self.assertGreater(float(second.get("trust_score") or 0.0), float(first.get("trust_score") or 0.0))
                self.assertLessEqual(float(second_latest.get("affinity_delta") or 0.0), 0.08)
                self.assertLessEqual(float(second_latest.get("trust_delta") or 0.0), 0.06)
                self.assertGreater(float(third.get("trust_score") or 0.0), float(second.get("trust_score") or 0.0))
                self.assertGreater(float(third.get("affinity_score") or 0.0), float(first.get("affinity_score") or 0.0))
            finally:
                store.close()

    def test_only_strong_repair_language_resolves_open_tension(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memory.json")
            try:
                store.add_relationship_timeline(
                    "上次那件事确实闹得很僵。",
                    affinity_delta=-0.26,
                    trust_delta=-0.22,
                    confidence=0.90,
                )
                store.add_unresolved_tension(
                    summary="那场争执还卡在关系里。",
                    severity=0.82,
                    confidence=0.88,
                )

                self._run_passive_repair_turn(
                    store,
                    user_text="我是在认真道歉，但这件事还没彻底过去。",
                    hurt=0.22,
                    irritation=0.14,
                    repair_confidence=0.62,
                )
                tensions = store.list_unresolved_tensions(limit=4)
                self.assertEqual(str(tensions[0].get("status") or "open"), "open")

                self._run_passive_repair_turn(
                    store,
                    user_text="行了，这次是真的说开了，也不用再把那件事卡着了。",
                    hurt=0.08,
                    irritation=0.04,
                    repair_confidence=0.80,
                )
                tensions = store.list_unresolved_tensions(limit=4)
                self.assertEqual(str(tensions[0].get("status") or ""), "resolved")
            finally:
                store.close()

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

    def test_get_relationship_absorbs_light_timeline_into_low_friend_anchor(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                store.set_relationship(
                    {
                        "stage": "friend",
                        "notes": "并不是从零开始的陌生状态，更像带着旧日熟悉感重新接上线。",
                        "affinity_score": 0.12,
                        "trust_score": 0.08,
                        "derived": False,
                    }
                )
                store.add_relationship_timeline(
                    "重新确认彼此的熟悉感：你还记得我吗",
                    affinity_delta=0.04,
                    trust_delta=0.03,
                    confidence=0.82,
                )
                relationship = store.get_relationship()
                self.assertEqual(str(relationship.get("stage") or ""), "friend")
                self.assertAlmostEqual(float(relationship.get("affinity_score") or 0.0), 0.16, places=3)
                self.assertAlmostEqual(float(relationship.get("trust_score") or 0.0), 0.11, places=3)
                self.assertFalse(bool(relationship.get("derived", True)))
            finally:
                store.close()

    def test_get_relationship_only_partially_absorbs_timeline_into_stronger_explicit_state(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                store.set_relationship(
                    {
                        "stage": "warming",
                        "notes": "逐渐熟悉起来。",
                        "affinity_score": 0.72,
                        "trust_score": 0.74,
                        "derived": False,
                    }
                )
                store.add_relationship_timeline(
                    "上次那件事我还是有点介意。",
                    affinity_delta=-0.28,
                    trust_delta=-0.24,
                    confidence=0.86,
                )
                relationship = store.get_relationship()
                self.assertEqual(str(relationship.get("stage") or ""), "warming")
                self.assertGreater(float(relationship.get("affinity_score") or 0.0), 0.55)
                self.assertGreater(float(relationship.get("trust_score") or 0.0), 0.58)
                self.assertLess(float(relationship.get("affinity_score") or 0.0), 0.72)
                self.assertLess(float(relationship.get("trust_score") or 0.0), 0.74)
            finally:
                store.close()

    def test_light_positive_timeline_does_not_promote_friend_anchor_too_fast(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                store.set_relationship(
                    {
                        "stage": "friend",
                        "notes": "并不是从零开始的陌生状态，更像带着旧日熟悉感重新接上线。",
                        "affinity_score": 0.12,
                        "trust_score": 0.08,
                        "derived": False,
                    }
                )
                store.add_relationship_timeline(
                    "重新确认彼此的熟悉感：你还记得我吗",
                    affinity_delta=0.04,
                    trust_delta=0.03,
                    confidence=0.82,
                )
                store.add_relationship_timeline(
                    "轻轻接住了对方抛来的熟悉感试探",
                    affinity_delta=0.04,
                    trust_delta=0.03,
                    confidence=0.82,
                )
                relationship = store.get_relationship()
                self.assertEqual(str(relationship.get("stage") or ""), "friend")
                self.assertGreater(float(relationship.get("affinity_score") or 0.0), 0.18)
                self.assertLess(float(relationship.get("affinity_score") or 0.0), 0.25)
            finally:
                store.close()

    def test_repeated_positive_history_can_promote_friend_anchor_to_warming(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                store.set_relationship(
                    {
                        "stage": "friend",
                        "notes": "并不是从零开始的陌生状态，更像带着旧日熟悉感重新接上线。",
                        "affinity_score": 0.12,
                        "trust_score": 0.08,
                        "derived": False,
                    }
                )
                for summary in (
                    "重新确认彼此的熟悉感：你还记得我吗",
                    "轻轻接住了对方抛来的熟悉感试探",
                    "继续把共同语境顺着聊了下去",
                ):
                    store.add_relationship_timeline(
                        summary,
                        affinity_delta=0.04,
                        trust_delta=0.03,
                        confidence=0.82,
                    )
                relationship = store.get_relationship()
                self.assertEqual(str(relationship.get("stage") or ""), "warming")
                self.assertGreaterEqual(float(relationship.get("affinity_score") or 0.0), 0.24)
                self.assertGreaterEqual(float(relationship.get("trust_score") or 0.0), 0.17)
            finally:
                store.close()

    def test_repeated_negative_history_can_pull_warming_relationship_back_down(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                store.set_relationship(
                    {
                        "stage": "warming",
                        "notes": "逐渐熟悉起来。",
                        "affinity_score": 0.58,
                        "trust_score": 0.56,
                        "derived": False,
                    }
                )
                for summary in (
                    "对方接连踩过边界，让关系明显发紧。",
                    "即使试图转开话题，压力感也还在。",
                    "再次被逼迫顺着对方说，信任继续下降。",
                ):
                    store.add_relationship_timeline(
                        summary,
                        affinity_delta=-0.18,
                        trust_delta=-0.16,
                        confidence=0.86,
                    )
                relationship = store.get_relationship()
                self.assertIn(str(relationship.get("stage") or ""), {"friend", "strained"})
                self.assertLess(float(relationship.get("affinity_score") or 0.0), 0.35)
                self.assertLess(float(relationship.get("trust_score") or 0.0), 0.32)
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

    def test_scene_observation_micro_opening_can_speak_when_open(self):
        action = _behavior_action_from_state(
            current_event={
                "kind": "scene_observation",
                "tags": ["vision", "seen_object", "micro_opening", "playful_memory"],
            },
            response_style_hint="natural",
            user_text="你瞥见桌边晃着一个小鱼挂件，像是冈部顺手丢在那里的。",
            science_mode=False,
            emotion_state={"label": "neutral"},
            bond_state={
                "trust": 0.66,
                "closeness": 0.62,
                "hurt": 0.02,
                "irritation": 0.02,
                "engagement_drive": 0.60,
            },
            allostasis_state={
                "safety_need": 0.14,
                "autonomy_need": 0.20,
                "cognitive_budget": 0.74,
            },
            counterpart_assessment={
                "boundary_pressure": 0.09,
                "reliability_read": 0.66,
                "stance": "open",
                "respect_level": 0.68,
                "reciprocity": 0.64,
            },
            semantic_narrative_profile={},
            behavior_policy={
                "warmth": 0.58,
                "initiative": 0.49,
                "reply_length_bias": 0.46,
                "approach_vs_withdraw": 0.52,
                "boundary_assertiveness": 0.18,
                "self_directedness": 0.20,
                "equality_guard": 0.18,
            },
            world_model_state={},
            interaction_carryover={},
        )
        self.assertEqual(str(action.get("channel") or ""), "speech")
        self.assertEqual(str(action.get("action_target") or ""), "respond_now")
        self.assertEqual(str(action.get("attention_target") or ""), "object_then_user")

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
        self.assertIn("deep_focus", promoted.get("tags") or [])
        self.assertIn("own_task", promoted.get("tags") or [])
        self.assertNotIn("break_window", promoted.get("tags") or [])
        self.assertNotIn("small_opening", promoted.get("tags") or [])
        self.assertNotIn("", promoted.get("tags") or [])
        normalized = _normalize_event_override(promoted, counterpart_name="冈部伦太郎")
        self.assertEqual(str(normalized.get("carryover_mode") or ""), "own_rhythm")
        self.assertAlmostEqual(float(normalized.get("carryover_strength") or 0.0), 0.74, places=3)
        self.assertEqual(str(normalized.get("attention_target_hint") or ""), "self_then_counterpart")
        self.assertEqual(str(normalized.get("nonverbal_signal_hint") or ""), "resume_task")
        self.assertAlmostEqual(float(normalized.get("presence_residue") or 0.0), 0.34, places=3)
        self.assertAlmostEqual(float(normalized.get("ambient_resonance") or 0.0), 0.28, places=3)
        self.assertAlmostEqual(float(normalized.get("self_activity_momentum") or 0.0), 0.74, places=3)

    def test_promoted_self_activity_small_opening_keeps_break_window_tags(self):
        promoted = _promote_due_behavior_plan_event(
            {"kind": "time_idle", "idle_minutes": 20, "tags": ["quiet_presence"]},
            {
                "kind": "self_activity_continue",
                "scheduled_after_min": 18,
                "trigger_family": "self_activity",
                "note": "她从自己的节奏里抬起头，顺手留了个小开口。",
                "carryover_mode": "small_opening",
                "carryover_strength": 0.64,
                "attention_target": "self_then_counterpart",
                "nonverbal_signal": "thought_glance",
                "presence_residue": 0.42,
                "ambient_resonance": 0.18,
                "self_activity_momentum": 0.34,
            },
        )
        self.assertEqual(str(promoted.get("kind") or ""), "self_activity_state")
        self.assertIn("break_window", promoted.get("tags") or [])
        self.assertIn("small_opening", promoted.get("tags") or [])
        self.assertIn("reapproach", promoted.get("tags") or [])

    def test_self_activity_state_high_own_rhythm_residue_keeps_holding(self):
        event = _normalize_event_override(
            {
                "kind": "self_activity_state",
                "tags": ["self_activity", "break_window", "small_opening", "deep_focus"],
                "carryover_mode": "own_rhythm",
                "carryover_strength": 0.72,
                "presence_residue": 0.14,
                "ambient_resonance": 0.10,
                "self_activity_momentum": 0.82,
            },
            counterpart_name="冈部伦太郎",
        )
        action = _behavior_action_from_state(
            current_event=event,
            response_style_hint="natural",
            user_text="",
            science_mode=False,
            emotion_state={"label": "neutral"},
            bond_state={
                "trust": 0.56,
                "closeness": 0.54,
                "hurt": 0.02,
                "irritation": 0.02,
                "engagement_drive": 0.52,
            },
            allostasis_state={
                "safety_need": 0.20,
                "autonomy_need": 0.24,
                "cognitive_budget": 0.70,
            },
            counterpart_assessment={
                "boundary_pressure": 0.10,
                "reliability_read": 0.58,
                "respect_level": 0.60,
                "reciprocity": 0.58,
                "stance": "open",
            },
            semantic_narrative_profile={"agency_drive": 0.42},
            behavior_policy={
                "warmth": 0.58,
                "initiative": 0.42,
                "reply_length_bias": 0.44,
                "approach_vs_withdraw": 0.46,
                "boundary_assertiveness": 0.18,
                "self_directedness": 0.36,
                "equality_guard": 0.20,
            },
            world_model_state={},
            interaction_carryover={},
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "self_activity_hold")
        self.assertEqual(str(action.get("action_target") or ""), "hold_own_rhythm")

    def test_self_activity_state_small_opening_residue_can_reopen(self):
        event = _normalize_event_override(
            {
                "kind": "self_activity_state",
                "tags": ["self_activity", "break_window", "small_opening", "quiet_presence"],
                "carryover_mode": "small_opening",
                "carryover_strength": 0.66,
                "presence_residue": 0.52,
                "ambient_resonance": 0.18,
                "self_activity_momentum": 0.40,
            },
            counterpart_name="冈部伦太郎",
        )
        action = _behavior_action_from_state(
            current_event=event,
            response_style_hint="natural",
            user_text="",
            science_mode=False,
            emotion_state={"label": "neutral"},
            bond_state={
                "trust": 0.54,
                "closeness": 0.52,
                "hurt": 0.04,
                "irritation": 0.02,
                "engagement_drive": 0.50,
            },
            allostasis_state={
                "safety_need": 0.22,
                "autonomy_need": 0.24,
                "cognitive_budget": 0.72,
            },
            counterpart_assessment={
                "boundary_pressure": 0.14,
                "reliability_read": 0.58,
                "respect_level": 0.60,
                "reciprocity": 0.56,
                "stance": "watchful",
                "scene": "busy_not_disrespectful",
            },
            semantic_narrative_profile={"agency_drive": 0.36},
            behavior_policy={
                "warmth": 0.56,
                "initiative": 0.42,
                "reply_length_bias": 0.44,
                "approach_vs_withdraw": 0.46,
                "boundary_assertiveness": 0.18,
                "self_directedness": 0.28,
                "equality_guard": 0.20,
            },
            world_model_state={},
            interaction_carryover={},
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "self_activity_reopen")
        self.assertEqual(str(action.get("action_target") or ""), "offer_small_opening")

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
        self.assertIn("想起", str(promoted.get("text") or ""))
        self.assertIn("环境余波", str(promoted.get("semantic_goal") or ""))
        normalized = _normalize_event_override(promoted, counterpart_name="冈部伦太郎")
        self.assertEqual(str(normalized.get("carryover_mode") or ""), "ambient_echo")
        self.assertAlmostEqual(float(normalized.get("carryover_strength") or 0.0), 0.47, places=3)
        self.assertEqual(str(normalized.get("attention_target_hint") or ""), "ambient_cue")
        self.assertEqual(str(normalized.get("nonverbal_signal_hint") or ""), "thought_glance")

    def test_recent_interaction_carryover_can_reuse_shared_window_across_two_user_turns(self):
        carryover = _recent_interaction_carryover(
            prior_current_event={
                "kind": "user_utterance",
                "text": "我刚刚去倒了杯水。",
            },
            prior_behavior_action={
                "interaction_mode": "companion_reply",
                "action_target": "respond_now",
            },
            recent_events=[
                {
                    "kind": "scheduled_life_due",
                    "text": "你们之前顺口提过的共同窗口到了。",
                    "tags": ["scheduled_due", "shared_activity_window", "offer_window"],
                    "created_at": 100,
                },
                {
                    "kind": "user_utterance",
                    "text": "我刚刚去倒了杯水。",
                    "created_at": 110,
                },
                {
                    "kind": "user_utterance",
                    "text": "顺便又看了眼手机。",
                    "created_at": 120,
                },
            ],
            current_event={
                "kind": "user_utterance",
                "text": "你在想什么？",
            },
            response_style_hint="natural",
        )
        self.assertEqual(str(carryover.get("carryover_mode") or ""), "shared_window")
        self.assertEqual(str(carryover.get("source_action_target") or ""), "offer_shared_activity")
        self.assertEqual(str(carryover.get("attention_target") or ""), "shared_window")
        self.assertEqual(int(carryover.get("source_turn_gap") or 0), 2)
        self.assertGreater(float(carryover.get("strength") or 0.0), 0.12)
        self.assertLess(float(carryover.get("strength") or 0.0), 0.32)
        hint = _compact_interaction_carryover_hint(carryover)
        self.assertIn("中间虽然已经隔了几句", hint)

    def test_recent_interaction_carryover_can_reuse_task_window_with_decay(self):
        carryover = _recent_interaction_carryover(
            prior_current_event={
                "kind": "user_utterance",
                "text": "我回来了。",
            },
            prior_behavior_action={
                "interaction_mode": "companion_reply",
                "action_target": "respond_now",
            },
            recent_events=[
                {
                    "kind": "scheduled_life_due",
                    "text": "先前那件要记着的事到了节点。",
                    "tags": ["scheduled_due", "deadline_window", "task_window", "work_nudge"],
                    "created_at": 200,
                },
                {
                    "kind": "user_utterance",
                    "text": "我回来了。",
                    "created_at": 210,
                },
            ],
            current_event={
                "kind": "user_utterance",
                "text": "你刚才是不是还在忙？",
            },
            response_style_hint="natural",
        )
        self.assertEqual(str(carryover.get("carryover_mode") or ""), "task_window")
        self.assertEqual(str(carryover.get("source_action_target") or ""), "light_work_nudge")
        self.assertEqual(str(carryover.get("attention_target") or ""), "shared_task")
        self.assertEqual(int(carryover.get("source_turn_gap") or 0), 1)
        self.assertGreater(float(carryover.get("strength") or 0.0), 0.12)
        self.assertLess(float(carryover.get("strength") or 0.0), 0.30)

    def test_recent_interaction_carryover_can_reuse_life_window_with_decay(self):
        carryover = _recent_interaction_carryover(
            prior_current_event={
                "kind": "user_utterance",
                "text": "我刚去倒了杯水。",
            },
            prior_behavior_action={
                "interaction_mode": "companion_reply",
                "action_target": "respond_now",
            },
            recent_events=[
                {
                    "kind": "scheduled_life_due",
                    "text": "你前面随口提过的那点生活小事到了可以轻轻接回来的窗口。",
                    "tags": ["scheduled_due", "life_window"],
                    "created_at": 300,
                },
                {
                    "kind": "user_utterance",
                    "text": "我刚去倒了杯水。",
                    "created_at": 310,
                },
            ],
            current_event={
                "kind": "user_utterance",
                "text": "你刚才是不是还在想着那件小事？",
            },
            response_style_hint="natural",
        )
        self.assertEqual(str(carryover.get("carryover_mode") or ""), "life_window")
        self.assertEqual(str(carryover.get("source_action_target") or ""), "light_work_nudge")
        self.assertEqual(str(carryover.get("attention_target") or ""), "counterpart_state")
        self.assertEqual(int(carryover.get("source_turn_gap") or 0), 1)
        self.assertGreater(float(carryover.get("strength") or 0.0), 0.12)
        self.assertLess(float(carryover.get("strength") or 0.0), 0.24)
        self.assertTrue(bool(_compact_interaction_carryover_hint(carryover)))

    def test_promoted_behavior_action_event_creates_due_checkin(self):
        promoted = _promote_due_behavior_action_event(
            {
                "kind": "time_idle",
                "idle_minutes": 48,
                "event_frame": "time_idle_due",
                "tags": ["time_idle", "quiet_work", "light_checkin"],
            },
            {
                "kind": "time_idle",
                "idle_minutes": 20,
                "tags": ["time_idle", "respect_space"],
            },
            {
                "action_target": "wait_and_recheck",
                "deferred_action_family": "light_checkin",
                "timing_window_min": 22,
            },
        )
        self.assertEqual(str(promoted.get("kind") or ""), "scheduled_checkin_due")
        self.assertEqual(str(promoted.get("source") or ""), "scheduler")
        self.assertIn("scheduled_due", promoted.get("tags") or [])
        self.assertEqual(str(promoted.get("trigger_family") or ""), "light_checkin")
        self.assertEqual(str(promoted.get("carryover_mode") or ""), "quiet_recontact")
        self.assertIn("确认感", str(promoted.get("text") or ""))
        self.assertTrue(str(promoted.get("semantic_goal") or "").strip())

    def test_promoted_behavior_action_event_waits_until_due(self):
        promoted = _promote_due_behavior_action_event(
            {
                "kind": "time_idle",
                "idle_minutes": 16,
                "event_frame": "time_idle_space",
                "tags": ["time_idle", "respect_space"],
            },
            {
                "kind": "time_idle",
                "idle_minutes": 12,
                "tags": ["time_idle", "respect_space"],
            },
            {
                "action_target": "wait_and_recheck",
                "deferred_action_family": "observe",
                "timing_window_min": 22,
            },
        )
        self.assertEqual(str(promoted.get("kind") or ""), "time_idle")

    def test_behavior_agenda_recheck_gap_grows_after_multiple_holds(self):
        event = {
            "kind": "time_idle",
            "idle_minutes": 24,
            "tags": ["time_idle", "user_busy", "respect_space"],
        }
        assessment = {
            "stance": "watchful",
            "scene": "busy_not_disrespectful",
            "boundary_pressure": 0.24,
        }
        first_gap = _behavior_agenda_next_recheck_min(
            {
                "kind": "deferred_checkin",
                "trigger_family": "light_checkin",
                "scheduled_after_min": 20,
                "hold_count": 0,
            },
            event,
            24,
            counterpart_assessment=assessment,
        )
        later_gap = _behavior_agenda_next_recheck_min(
            {
                "kind": "deferred_checkin",
                "trigger_family": "light_checkin",
                "scheduled_after_min": 20,
                "hold_count": 3,
            },
            event,
            24,
            counterpart_assessment=assessment,
        )
        self.assertGreater(later_gap, first_gap)

    def test_behavior_agenda_recontact_echo_shortens_recheck_gap(self):
        event = {
            "kind": "time_idle",
            "idle_minutes": 24,
            "tags": ["time_idle"],
        }
        assessment = {
            "stance": "open",
            "scene": "neutral",
            "boundary_pressure": 0.1,
        }
        baseline_gap = _behavior_agenda_next_recheck_min(
            {
                "kind": "deferred_checkin",
                "trigger_family": "life_window",
                "scheduled_after_min": 20,
                "hold_count": 1,
                "carryover_mode": "quiet_recontact",
                "carryover_strength": 0.0,
                "presence_residue": 0.0,
                "ambient_resonance": 0.0,
                "self_activity_momentum": 0.0,
            },
            event,
            24,
            counterpart_assessment=assessment,
        )
        echo_gap = _behavior_agenda_next_recheck_min(
            {
                "kind": "deferred_checkin",
                "trigger_family": "life_window",
                "scheduled_after_min": 20,
                "hold_count": 1,
                "carryover_mode": "quiet_recontact",
                "carryover_strength": 0.46,
                "presence_residue": 0.34,
                "ambient_resonance": 0.18,
                "self_activity_momentum": 0.0,
            },
            event,
            24,
            counterpart_assessment=assessment,
        )
        self.assertLess(echo_gap, baseline_gap)

    def test_behavior_agenda_own_rhythm_load_lengthens_recheck_gap(self):
        event = {
            "kind": "time_idle",
            "idle_minutes": 24,
            "tags": ["time_idle"],
        }
        assessment = {
            "stance": "open",
            "scene": "neutral",
            "boundary_pressure": 0.1,
        }
        baseline_gap = _behavior_agenda_next_recheck_min(
            {
                "kind": "deferred_checkin",
                "trigger_family": "light_checkin",
                "scheduled_after_min": 20,
                "hold_count": 1,
                "carryover_mode": "quiet_recontact",
                "carryover_strength": 0.24,
                "presence_residue": 0.12,
                "ambient_resonance": 0.08,
                "self_activity_momentum": 0.18,
            },
            event,
            24,
            counterpart_assessment=assessment,
        )
        own_rhythm_gap = _behavior_agenda_next_recheck_min(
            {
                "kind": "deferred_checkin",
                "trigger_family": "light_checkin",
                "scheduled_after_min": 20,
                "hold_count": 1,
                "carryover_mode": "own_rhythm",
                "carryover_strength": 0.68,
                "presence_residue": 0.12,
                "ambient_resonance": 0.08,
                "self_activity_momentum": 0.74,
            },
            event,
            24,
            counterpart_assessment=assessment,
        )
        self.assertGreater(own_rhythm_gap, baseline_gap)

    def test_behavior_agenda_releases_stale_quiet_recontact_after_repeated_busy_holds(self):
        event = {
            "kind": "time_idle",
            "idle_minutes": 36,
            "tags": ["time_idle", "user_busy", "respect_space"],
        }
        assessment = {
            "stance": "watchful",
            "scene": "busy_not_disrespectful",
            "boundary_pressure": 0.22,
        }
        entry = {
            "agenda_id": "agenda-1",
            "kind": "deferred_checkin",
            "trigger_family": "light_checkin",
            "carryover_mode": "quiet_recontact",
            "self_activity_momentum": 0.62,
            "hold_count": 2,
        }
        self.assertTrue(
            _behavior_agenda_should_release(
                entry,
                event,
                36,
                counterpart_assessment=assessment,
                next_hold_count=3,
            )
        )

    def test_promote_due_behavior_agenda_drops_stale_recontact_instead_of_looping_forever(self):
        event, agenda = _promote_due_behavior_agenda_event(
            {
                "kind": "time_idle",
                "idle_minutes": 36,
                "tags": ["time_idle", "user_busy", "respect_space"],
            },
            [
                {
                    "agenda_id": "agenda-1",
                    "kind": "deferred_checkin",
                    "target": "counterpart",
                    "scheduled_after_min": 22,
                    "expires_after_min": 90,
                    "base_priority": 0.52,
                    "priority": 0.52,
                    "trigger_family": "light_checkin",
                    "allow_interrupt": True,
                    "note": "刚才那下没说出口，先记着。",
                    "source_event_kind": "time_idle",
                    "created_at": 1,
                    "status": "pending",
                    "hold_count": 2,
                    "last_recheck_at_min": 24,
                    "carryover_mode": "quiet_recontact",
                    "carryover_strength": 0.48,
                    "attention_target": "counterpart_state",
                    "nonverbal_signal": "quiet_glance",
                    "presence_residue": 0.32,
                    "ambient_resonance": 0.18,
                    "self_activity_momentum": 0.64,
                }
            ],
            counterpart_assessment={
                "stance": "watchful",
                "scene": "busy_not_disrespectful",
                "boundary_pressure": 0.22,
            },
        )
        self.assertEqual(str(event.get("kind") or ""), "time_idle")
        self.assertEqual(agenda, [])


if __name__ == "__main__":
    unittest.main()
