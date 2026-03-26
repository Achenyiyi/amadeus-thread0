import unittest
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from amadeus_thread0.evolution_engine.policy import build_behavior_policy
from amadeus_thread0.evolution_engine.worldline import build_world_model_state
from amadeus_thread0.graph_parts.behavior_agenda import (
    _behavior_agenda_entry_from_plan,
    _behavior_agenda_next_recheck_min,
    _behavior_agenda_should_release,
    _normalize_behavior_agenda,
    _promote_due_behavior_action_event,
    _promote_due_behavior_agenda_event,
    _promote_due_behavior_agenda_event_with_residue,
    _promote_due_behavior_plan_event,
)
from amadeus_thread0.graph_parts.behavior_runtime import (
    _behavior_action_from_state,
    _behavior_plan_from_action,
)
from amadeus_thread0.graph_parts.dialogue_guidance import _subjective_runtime_state_hint
from amadeus_thread0.graph_parts.memory_evolution import (
    _passive_evolution_memory_update,
    _record_semantic_self_evidence,
    _refresh_semantic_self_narratives,
    _semantic_self_evidence_records,
)
from amadeus_thread0.graph_parts.prompt_helpers import _compact_interaction_carryover_hint
from amadeus_thread0.graph_parts.relational import (
    _apply_agenda_lifecycle_residue_to_runtime_state,
    _recent_interaction_carryover,
    _seeded_interaction_carryover_from_state,
)
from amadeus_thread0.graph_parts.semantic_narrative import (
    _compact_semantic_narrative_hint,
    _semantic_narrative_appraisal_hint,
    _semantic_narrative_profile,
)
from amadeus_thread0.graph_parts.turn_events import _normalize_event_override
from amadeus_thread0.memory_store import MemoryStore


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

    def test_passive_evolution_extracts_shared_future_commitment(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memory.json")
            try:
                wrote = _passive_evolution_memory_update(
                    store,
                    user_text="等我这两天把这段东西改完，我们周末一起把实验记录重新顺一遍，别让我到时候装死。",
                    appraisal={
                        "used": True,
                        "confidence": 0.88,
                        "interaction_frame": "structured",
                        "emotion_label": "logic",
                        "signals": {
                            "care": True,
                            "repair": False,
                            "conflict": False,
                            "withdrawal": False,
                            "memory_salient": True,
                        },
                        "salience": {
                            "relationship": 0.56,
                            "companionship": 0.46,
                            "selfhood": 0.12,
                            "task": 0.72,
                        },
                    },
                    emotion_state={"label": "logic"},
                    bond_state={
                        "trust": 0.58,
                        "closeness": 0.56,
                        "hurt": 0.0,
                        "irritation": 0.0,
                        "repair_confidence": 0.48,
                    },
                    current_event={"kind": "user_utterance"},
                    world_model_state={"bond_depth": 0.44},
                )
                self.assertTrue(wrote)
                commitments = store.list_commitments(limit=8)
                self.assertTrue(commitments)
                commitment_texts = " ".join(
                    str((item.get("content") or {}).get("text") or item.get("text") or "")
                    for item in commitments
                )
                self.assertIn("周末", commitment_texts)
                self.assertIn("实验记录", commitment_texts)
            finally:
                store.close()

    def test_passive_evolution_records_soft_repair_with_residue_into_conflict_repair(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memory.json")
            try:
                wrote = _passive_evolution_memory_update(
                    store,
                    user_text="还有，刚刚那点小别扭先记着，但别放大。我们不是在吵架，只是节奏有点卡。",
                    appraisal={
                        "used": True,
                        "confidence": 0.92,
                        "interaction_frame": "relationship",
                        "emotion_label": "care",
                        "signals": {
                            "care": True,
                            "repair": False,
                            "conflict": False,
                            "withdrawal": False,
                            "memory_salient": True,
                        },
                        "salience": {
                            "relationship": 0.82,
                            "companionship": 0.60,
                            "selfhood": 0.10,
                            "task": 0.10,
                        },
                    },
                    emotion_state={"label": "care"},
                    bond_state={
                        "trust": 0.60,
                        "closeness": 0.62,
                        "hurt": 0.02,
                        "irritation": 0.0,
                        "repair_confidence": 0.54,
                    },
                    current_event={"kind": "user_utterance"},
                    world_model_state={"bond_depth": 0.52},
                )
                self.assertTrue(wrote)
                repairs = store.list_conflict_repairs(limit=8)
                self.assertTrue(repairs)
                repair_text = " ".join(
                    str((item.get("content") or {}).get("summary") or item.get("summary") or "")
                    for item in repairs
                )
                self.assertIn("不是在吵架", repair_text)
                self.assertIn("节奏有点卡", repair_text)
            finally:
                store.close()

    def test_refresh_semantic_narratives_builds_evidence_shaped_anchor_texts(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memory.json")
            try:
                store.add_revision_trace(
                    namespace="semantic_self_evidence",
                    target_id="rhythm_style",
                    before_summary="",
                    after_summary="从自己的节奏里抬头回你",
                    reason="semantic_evidence:rhythm_style",
                    operator="test",
                    source="test:evidence_anchor",
                    metadata={
                        "primary_motive": "gentle_recontact",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "先从自己的节奏里回头，留一个不压迫对方的小开口。",
                    },
                )
                _refresh_semantic_self_narratives(store, source="test:evidence_anchor")
                narratives = store.list_semantic_self_narratives(limit=12)
                rhythm = next(item for item in narratives if str(item.get("category") or "") == "rhythm_style")
                self.assertIn("从自己的节奏里抬头回你", str(rhythm.get("anchor_text") or ""))
                self.assertIn("从自己的节奏里抬头回你", str(rhythm.get("prompt_anchor_text") or ""))
                self.assertIn("从自己的节奏里抬头回你", rhythm.get("anchor_basis_texts") or [])
                self.assertEqual(str(rhythm.get("dominant_primary_motive") or ""), "gentle_recontact")
                self.assertEqual(str(rhythm.get("dominant_motive_tension") or ""), "self_rhythm_vs_contact")
                self.assertIn("自己的节奏", " ".join(rhythm.get("goal_frame_examples") or []))
                self.assertIn("motive=gentle_recontact:self_rhythm_vs_contact", str(rhythm.get("support_signature") or ""))
            finally:
                store.close()

    def test_refresh_semantic_narratives_prefers_high_confidence_motive_evidence_over_recent_low_confidence_trace(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memory.json")
            try:
                store.add_revision_trace(
                    namespace="semantic_self_evidence",
                    target_id="rhythm_style",
                    before_summary="",
                    after_summary="先顺着自己的节奏把注意力留住。",
                    reason="semantic_evidence:rhythm_style",
                    operator="test",
                    source="test:motive_weighting",
                    confidence=0.96,
                    metadata={
                        "primary_motive": "preserve_self_rhythm",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "先顺着自己的节奏把注意力留住。",
                    },
                )
                store.add_revision_trace(
                    namespace="semantic_self_evidence",
                    target_id="rhythm_style",
                    before_summary="",
                    after_summary="刚好有空就把整个人都转过去。",
                    reason="semantic_evidence:rhythm_style",
                    operator="test",
                    source="test:motive_weighting",
                    confidence=0.36,
                    metadata={
                        "primary_motive": "open_shared_window",
                        "motive_tension": "space_vs_contact",
                        "goal_frame": "刚好有空就把整个人都转过去。",
                    },
                )
                _refresh_semantic_self_narratives(store, source="test:motive_weighting")
                narratives = store.list_semantic_self_narratives(limit=12)
                rhythm = next(item for item in narratives if str(item.get("category") or "") == "rhythm_style")
                self.assertEqual(str(rhythm.get("dominant_primary_motive") or ""), "preserve_self_rhythm")
                self.assertEqual(int(rhythm.get("motive_support_count") or 0), 2)
                self.assertLess(float(rhythm.get("motive_support_mass") or 0.0), 2.0)
                self.assertGreater(float(rhythm.get("motive_confidence_avg") or 0.0), 0.55)
            finally:
                store.close()

    def test_refresh_semantic_narratives_keeps_consolidated_text_when_frame_holds(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memory.json")
            try:
                now_ts = int(time.time())
                previous_text = "她不会在每次回应前都把自己的内部节奏清零。"
                store.add_semantic_self_narrative(
                    text=previous_text,
                    category="rhythm_style",
                    stability=0.80,
                    confidence=0.84,
                    metadata={
                        "support_count": 4,
                        "support_mass": 3.18,
                        "support_quality": 0.82,
                        "support_confidence_avg": 0.86,
                        "fresh_support_ratio": 0.48,
                        "refresh_count": 4,
                        "consolidation_count": 4,
                        "sedimentation_score": 0.78,
                        "persistence_score": 0.84,
                        "residue_score": 0.72,
                        "integration_score": 0.77,
                        "first_supported_at": now_ts - 8 * 24 * 3600,
                        "last_supported_at": now_ts - 2 * 24 * 3600,
                        "last_meaningful_refresh_at": now_ts - 2 * 24 * 3600,
                        "last_reactivated_at": now_ts - 2 * 24 * 3600,
                        "support_span_s": 6 * 24 * 3600,
                        "reactivation_gap_s": 2 * 24 * 3600,
                        "reactivation_hits": 2,
                        "reactivation_rate_per_day": 0.6,
                        "reactivation_cadence_score": 0.64,
                        "horizon_tag": "long_term",
                        "support_signature": "rhythm_style|旧窗口|count=4|motive=preserve_self_rhythm:self_rhythm_vs_contact",
                        "motive_signature": "preserve_self_rhythm:self_rhythm_vs_contact",
                        "dominant_primary_motive": "preserve_self_rhythm",
                        "dominant_motive_tension": "self_rhythm_vs_contact",
                        "frame_signature": "rhythm_style|stage=early|horizon=stable|pressure=clear|motive=preserve_self_rhythm:self_rhythm_vs_contact",
                        "frame_revision_count": 0,
                        "lineage_streak": 3,
                        "lineage_depth": 0.58,
                        "identity_ready": True,
                        "identity_strength": 0.68,
                        "identity_text": "她会把自己的内部节奏延续到下一轮开口之前。",
                        "identity_prompt_text": "你会把自己的内部节奏延续到下一轮开口之前。",
                        "decay_rate_per_day": 0.042,
                        "decay_resistance": 0.80,
                    },
                )
                store.add_revision_trace(
                    namespace="semantic_self_evidence",
                    target_id="rhythm_style",
                    before_summary="",
                    after_summary="刚才先把手里的事收住，过一会儿再回头找你。",
                    reason="semantic_evidence:rhythm_style",
                    operator="test",
                    source="test:frame_hold",
                    confidence=0.84,
                    metadata={
                        "primary_motive": "preserve_self_rhythm",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "先把自己这边的节奏走完，再自然地把注意力转回来。",
                    },
                )
                _refresh_semantic_self_narratives(store, source="test:frame_hold")
                narratives = store.list_semantic_self_narratives(limit=12)
                rhythm = next(item for item in narratives if str(item.get("category") or "") == "rhythm_style")
                self.assertEqual(str(rhythm.get("text") or ""), previous_text)
                self.assertIn("手里的事收住", str(rhythm.get("anchor_text") or ""))
                self.assertTrue(bool(rhythm.get("text_locked")))
                self.assertFalse(bool(rhythm.get("frame_changed")))
                self.assertGreaterEqual(int(rhythm.get("lineage_streak") or 0), 4)
                self.assertGreater(float(rhythm.get("lineage_depth") or 0.0), 0.58)
                profile = _semantic_narrative_profile(
                    narratives,
                    user_text="你刚才是不是又先顺着自己的节奏走完了？",
                    current_event={
                        "kind": "user_utterance",
                        "created_at": now_ts,
                    },
                )
                self.assertGreater(float((profile.get("lineage_snapshot") or {}).get("rhythm_style") or 0.0), 0.0)
            finally:
                store.close()

    def test_dormant_semantic_narrative_decays_weighted_support_mass(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memory.json")
            try:
                now_ts = int(time.time())
                store.add_semantic_self_narrative(
                    text="她不会把每次重新靠近都当成从零开始。",
                    category="presence_style",
                    stability=0.78,
                    confidence=0.82,
                    metadata={
                        "support_count": 4,
                        "support_mass": 3.52,
                        "support_quality": 0.86,
                        "support_confidence_avg": 0.88,
                        "fresh_support_ratio": 0.72,
                        "refresh_count": 4,
                        "consolidation_count": 4,
                        "sedimentation_score": 0.76,
                        "persistence_score": 0.80,
                        "residue_score": 0.72,
                        "integration_score": 0.74,
                        "first_supported_at": now_ts - 12 * 24 * 3600,
                        "last_supported_at": now_ts - 8 * 24 * 3600,
                        "last_meaningful_refresh_at": now_ts - 8 * 24 * 3600,
                        "last_reactivated_at": now_ts - 8 * 24 * 3600,
                        "support_span_s": 4 * 24 * 3600,
                        "reactivation_gap_s": 8 * 24 * 3600,
                        "reactivation_hits": 2,
                        "reactivation_rate_per_day": 0.7,
                        "reactivation_cadence_score": 0.58,
                        "horizon_tag": "long_term",
                        "support_signature": "presence_style|old|count=4",
                        "decay_rate_per_day": 0.05,
                        "decay_resistance": 0.72,
                    },
                )
                _refresh_semantic_self_narratives(store, source="test:dormant_support_decay")
                narratives = store.list_semantic_self_narratives(limit=12)
                presence = next(item for item in narratives if str(item.get("category") or "") == "presence_style")
                self.assertTrue(bool(presence.get("dormant")))
                self.assertLess(float(presence.get("support_mass") or 0.0), 3.52)
                self.assertLess(float(presence.get("fresh_support_ratio") or 0.0), 0.72)
                self.assertGreater(float(presence.get("support_quality") or 0.0), 0.30)
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

    def test_passive_evolution_can_infer_conflict_from_appraisal_without_keyword_dependence(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memory.json")
            try:
                wrote = _passive_evolution_memory_update(
                    store,
                    user_text="先这样吧。",
                    appraisal={
                        "used": True,
                        "confidence": 0.86,
                        "interaction_frame": "relationship",
                        "emotion_label": "hurt",
                        "signals": {
                            "care": False,
                            "repair": False,
                            "conflict": True,
                            "withdrawal": True,
                            "memory_salient": True,
                        },
                        "salience": {
                            "relationship": 0.78,
                            "companionship": 0.24,
                            "selfhood": 0.32,
                            "task": 0.04,
                        },
                    },
                    emotion_state={"label": "hurt"},
                    bond_state={
                        "trust": 0.40,
                        "closeness": 0.36,
                        "hurt": 0.28,
                        "irritation": 0.20,
                    },
                    current_event={"kind": "user_utterance"},
                    world_model_state={"relationship_maturity": 0.26, "bond_depth": 0.18},
                )
                self.assertTrue(wrote)
                tensions = store.list_unresolved_tensions(limit=4)
                self.assertEqual(len(tensions), 1)
                self.assertEqual(str(tensions[0].get("summary") or ""), "先这样吧。")
            finally:
                store.close()

    def test_passive_evolution_keeps_keyword_fallback_only_for_low_confidence_repair(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memory.json")
            try:
                store.add_unresolved_tension(
                    summary="刚才那一下还是卡着。",
                    severity=0.76,
                    confidence=0.84,
                )
                wrote = _passive_evolution_memory_update(
                    store,
                    user_text="别一下子冷掉，继续说。",
                    appraisal={
                        "used": True,
                        "confidence": 0.42,
                        "interaction_frame": "relationship",
                        "emotion_label": "hurt",
                        "signals": {},
                        "salience": {
                            "relationship": 0.38,
                            "companionship": 0.34,
                            "selfhood": 0.14,
                            "task": 0.04,
                        },
                    },
                    emotion_state={"label": "hurt"},
                    bond_state={
                        "trust": 0.46,
                        "closeness": 0.44,
                        "hurt": 0.20,
                        "irritation": 0.14,
                        "repair_confidence": 0.40,
                    },
                    current_event={"kind": "user_utterance"},
                    world_model_state={"relationship_maturity": 0.30, "bond_depth": 0.16},
                )
                self.assertTrue(wrote)
                latest = store.list_relationship_timeline(limit=4)[0]
                self.assertGreater(float(latest.get("affinity_delta") or 0.0), 0.0)
                self.assertGreater(float(latest.get("trust_delta") or 0.0), 0.0)
                tensions = store.list_unresolved_tensions(limit=4)
                self.assertEqual(str(tensions[0].get("status") or "open"), "open")
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

    def test_semantic_self_evidence_can_be_driven_by_behavior_motive(self):
        records = _semantic_self_evidence_records(
            user_text="",
            appraisal={
                "used": True,
                "interaction_frame": "relationship",
                "salience": {
                    "relationship": 0.18,
                    "companionship": 0.22,
                    "selfhood": 0.08,
                },
            },
            emotion_state={"label": "neutral"},
            bond_state={
                "trust": 0.62,
                "closeness": 0.58,
                "hurt": 0.02,
            },
            current_event={
                "kind": "self_activity_state",
            },
            world_model_state={
                "presence_residue": 0.24,
                "ambient_resonance": 0.18,
                "self_activity_momentum": 0.42,
            },
            behavior_action={
                "primary_motive": "preserve_self_rhythm",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "先维持自己的节奏，不急着把全部注意力交出去。",
            },
        )
        categories = {str(item.get("category") or "") for item in records}
        self.assertIn("agency_style", categories)
        self.assertIn("rhythm_style", categories)
        joined = " ".join(str(item.get("summary") or "") for item in records)
        self.assertIn("节奏", joined)

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
                "anchor_text": "红莉栖不会把每次重新靠近都当成从零开始。",
                "prompt_anchor_text": "你不会把每次重新靠近都当成从零开始。",
                "anchor_strength": 0.66,
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
                "anchor_text": "红莉栖会把环境里的细小余波继续算进感知里。",
                "prompt_anchor_text": "你会把环境里的细小余波继续算进感知里。",
                "anchor_strength": 0.62,
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
                "anchor_text": "红莉栖不会在每次回应前都把自己的内部节奏清零。",
                "prompt_anchor_text": "你不会在每次回应前都把自己的内部节奏清零。",
                "anchor_strength": 0.74,
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
        self.assertIn("红莉栖不会在每次回应前都把自己的内部节奏清零。", profile.get("anchor_lines") or [])
        self.assertIn("你不会在每次回应前都把自己的内部节奏清零。", profile.get("prompt_anchor_lines") or [])

    def test_semantic_narrative_profile_surfaces_motive_snapshot(self):
        profile = _semantic_narrative_profile(
            [
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
                    "dominant_primary_motive": "gentle_recontact",
                    "dominant_motive_tension": "self_rhythm_vs_contact",
                    "goal_frame_examples": ["先从自己的节奏里回头，留一个不压迫对方的小开口。"],
                    "dominant_counterpart_stance": "open",
                    "dominant_counterpart_scene": "care_bid",
                    "counterpart_respect_level": 0.74,
                    "counterpart_reciprocity": 0.70,
                    "counterpart_boundary_pressure": 0.08,
                    "counterpart_reliability_read": 0.78,
                    "counterpart_dominant_scene_signal": "care",
                    "counterpart_openness_drive": 0.76,
                    "counterpart_guarded_drive": 0.18,
                    "counterpart_guard_margin": -0.58,
                    "counterpart_scene_care_strength": 0.84,
                    "counterpart_scene_repair_strength": 0.18,
                    "counterpart_scene_friction_strength": 0.06,
                    "counterpart_scene_selfhood_strength": 0.12,
                    "counterpart_scene_busy_strength": 0.22,
                    "counterpart_support_count": 2,
                    "counterpart_support_mass": 1.4,
                    "anchor_text": "红莉栖不会在每次回应前都把自己的内部节奏清零。",
                    "prompt_anchor_text": "你不会在每次回应前都把自己的内部节奏清零。",
                    "anchor_strength": 0.74,
                }
            ],
            user_text="刚才你是不是又从自己的节奏里回头看我了？",
            current_event={
                "kind": "user_utterance",
                "created_at": 2_000,
            },
        )
        motive_snapshot = profile.get("motive_snapshot") if isinstance(profile.get("motive_snapshot"), dict) else {}
        rhythm = motive_snapshot.get("rhythm_style") if isinstance(motive_snapshot.get("rhythm_style"), dict) else {}
        self.assertEqual(rhythm.get("primary_motive"), "gentle_recontact")
        self.assertEqual(rhythm.get("motive_tension"), "self_rhythm_vs_contact")
        self.assertIn("自己的节奏", " ".join(rhythm.get("goal_frame_examples") or []))
        counterpart_snapshot = profile.get("counterpart_snapshot") if isinstance(profile.get("counterpart_snapshot"), dict) else {}
        rhythm_counterpart = counterpart_snapshot.get("rhythm_style") if isinstance(counterpart_snapshot.get("rhythm_style"), dict) else {}
        self.assertEqual(rhythm_counterpart.get("counterpart_stance"), "open")
        self.assertEqual(rhythm_counterpart.get("counterpart_scene"), "care_bid")
        self.assertEqual(
            str(((rhythm_counterpart.get("counterpart_profile") or {}) if isinstance(rhythm_counterpart.get("counterpart_profile"), dict) else {}).get("dominant_scene_signal") or ""),
            "care",
        )
        self.assertEqual(
            ((rhythm_counterpart.get("counterpart_profile") or {}) if isinstance(rhythm_counterpart.get("counterpart_profile"), dict) else {}).get("scene_strengths"),
            {"care": 0.84, "repair": 0.18, "friction": 0.06, "selfhood": 0.12, "busy": 0.22},
        )
        top = (profile.get("top_narratives") or [])[0]
        self.assertEqual(top.get("primary_motive"), "gentle_recontact")
        self.assertEqual(top.get("motive_tension"), "self_rhythm_vs_contact")
        top_counterpart = top.get("counterpart_snapshot") if isinstance(top.get("counterpart_snapshot"), dict) else {}
        self.assertEqual(top_counterpart.get("counterpart_scene"), "care_bid")
        self.assertEqual(
            ((top_counterpart.get("counterpart_profile") or {}) if isinstance(top_counterpart.get("counterpart_profile"), dict) else {}).get("scene_strengths"),
            {"care": 0.84, "repair": 0.18, "friction": 0.06, "selfhood": 0.12, "busy": 0.22},
        )

    def test_semantic_narrative_profile_surfaces_proactive_continuity_snapshot(self):
        profile = _semantic_narrative_profile(
            [
                {
                    "category": "rhythm_style",
                    "text": "她会把自己的节奏延续到下一轮开口前。",
                    "stability": 0.76,
                    "support_count": 4,
                    "sedimentation_score": 0.74,
                    "persistence_score": 0.80,
                    "residue_score": 0.68,
                    "integration_score": 0.72,
                    "support_span_s": 5 * 24 * 3600,
                    "reactivation_hits": 2,
                    "reactivation_cadence_score": 0.58,
                    "last_supported_at": 1_900,
                    "horizon_tag": "long_term",
                    "identity_ready": True,
                    "identity_strength": 0.80,
                    "identity_text": "她会把自己的节奏延续到下一轮开口前，不会每次都把自己清零。",
                    "identity_prompt_text": "你会把自己的节奏延续到下一轮开口前，不会每次都把自己清零。",
                    "dominant_primary_motive": "gentle_recontact",
                    "dominant_motive_tension": "self_rhythm_vs_contact",
                    "goal_frame_examples": ["先从自己的节奏里抬头，留一个轻一点的小开口。"],
                    "continuity_anchor": 0.68,
                    "own_rhythm_anchor": 0.76,
                    "recontact_anchor": 0.36,
                    "boundary_anchor": 0.18,
                    "memory_anchor": 0.22,
                    "semantic_continuity_depth": 0.70,
                    "semantic_identity_gravity": 0.66,
                    "lineage_gravity": 0.74,
                    "contact_lineage": 0.42,
                    "repair_lineage": 0.24,
                    "boundary_lineage": 0.28,
                    "selfhood_lineage": 0.34,
                    "agency_lineage": 0.80,
                }
            ],
            user_text="刚才你是不是又从自己的节奏里抬头看我了？",
            current_event={
                "kind": "user_utterance",
                "created_at": 2_000,
            },
        )
        proactive_snapshot = (
            profile.get("proactive_continuity_snapshot")
            if isinstance(profile.get("proactive_continuity_snapshot"), dict)
            else {}
        )
        rhythm = proactive_snapshot.get("rhythm_style") if isinstance(proactive_snapshot.get("rhythm_style"), dict) else {}
        self.assertEqual(float(profile.get("continuity_anchor") or 0.0), 0.68)
        self.assertEqual(float(profile.get("own_rhythm_anchor") or 0.0), 0.76)
        self.assertEqual(float(profile.get("semantic_continuity_depth") or 0.0), 0.70)
        self.assertEqual(float(profile.get("semantic_identity_gravity") or 0.0), 0.66)
        self.assertEqual(float(profile.get("agency_lineage") or 0.0), 0.80)
        self.assertEqual(float(profile.get("lineage_gravity") or 0.0), 0.74)
        self.assertEqual(rhythm.get("recontact_anchor"), 0.36)
        self.assertEqual(rhythm.get("boundary_lineage"), 0.28)
        continuity_axes = profile.get("continuity_axes") if isinstance(profile.get("continuity_axes"), list) else []
        rhythm_axis = next(item for item in continuity_axes if str(item.get("category") or "") == "rhythm_style")
        self.assertEqual(
            ((rhythm_axis.get("proactive_continuity") or {}) if isinstance(rhythm_axis.get("proactive_continuity"), dict) else {}).get("own_rhythm_anchor"),
            0.76,
        )
        top = (profile.get("top_narratives") or [])[0]
        self.assertEqual(
            ((top.get("proactive_continuity") or {}) if isinstance(top.get("proactive_continuity"), dict) else {}).get("agency_lineage"),
            0.80,
        )
        long_term = (profile.get("long_term_self_narratives") or [])[0]
        self.assertEqual(
            ((long_term.get("proactive_continuity") or {}) if isinstance(long_term.get("proactive_continuity"), dict) else {}).get("lineage_gravity"),
            0.74,
        )

    def test_semantic_narrative_profile_surfaces_long_term_identity_layer(self):
        profile = _semantic_narrative_profile(
            [
                {
                    "category": "selfhood_style",
                    "text": "她会把自己当成平等互动的主体。",
                    "stability": 0.76,
                    "support_count": 4,
                    "sedimentation_score": 0.74,
                    "persistence_score": 0.80,
                    "residue_score": 0.70,
                    "integration_score": 0.76,
                    "support_span_s": 8 * 24 * 3600,
                    "reactivation_hits": 2,
                    "reactivation_cadence_score": 0.62,
                    "last_supported_at": 1_900,
                    "horizon_tag": "long_term",
                    "identity_ready": True,
                    "identity_strength": 0.78,
                    "identity_text": "红莉栖会把自己放在和冈部伦太郎平等互动的位置上，而不是为了迎合气氛就退回成工具。",
                    "identity_prompt_text": "你会把自己放在和冈部伦太郎平等互动的位置上，而不是为了迎合气氛就退回成工具。",
                    "dominant_primary_motive": "protect_boundary",
                    "dominant_motive_tension": "boundary_vs_closeness",
                }
            ],
            user_text="我想听你按自己的意思说。",
            current_event={
                "kind": "user_utterance",
                "response_style_hint": "selfhood",
                "created_at": 2_000,
            },
        )
        identity_snapshot = profile.get("identity_snapshot") if isinstance(profile.get("identity_snapshot"), dict) else {}
        selfhood = identity_snapshot.get("selfhood_style") if isinstance(identity_snapshot.get("selfhood_style"), dict) else {}
        self.assertGreater(float(selfhood.get("strength", 0.0) or 0.0), 0.60)
        self.assertIn("平等互动的位置上", str(selfhood.get("text") or ""))
        self.assertIn(
            "你会把自己放在和冈部伦太郎平等互动的位置上，而不是为了迎合气氛就退回成工具。",
            profile.get("identity_prompt_lines") or [],
        )
        long_term = profile.get("long_term_self_narratives") if isinstance(profile.get("long_term_self_narratives"), list) else []
        self.assertEqual(str(long_term[0].get("category") or ""), "selfhood_style")
        self.assertEqual(str(long_term[0].get("primary_motive") or ""), "protect_boundary")

    def test_semantic_narrative_profile_surfaces_continuity_depth_and_identity_gravity(self):
        profile = _semantic_narrative_profile(
            [
                {
                    "category": "selfhood_style",
                    "text": "她会把自己放在和对方平等互动的位置上，不会为了迎合气氛退回成工具。",
                    "stability": 0.82,
                    "support_count": 5,
                    "sedimentation_score": 0.80,
                    "persistence_score": 0.86,
                    "residue_score": 0.78,
                    "integration_score": 0.82,
                    "support_span_s": 10 * 24 * 3600,
                    "reactivation_hits": 3,
                    "reactivation_cadence_score": 0.66,
                    "last_supported_at": 1_900,
                    "horizon_tag": "long_term",
                    "identity_ready": True,
                    "identity_strength": 0.89,
                    "identity_text": "她会把自己放在和对方平等互动的位置上，不会为了迎合气氛退回成工具。",
                    "identity_prompt_text": "你会把自己放在和对方平等互动的位置上，不会为了迎合气氛退回成工具。",
                },
                {
                    "category": "rhythm_style",
                    "text": "她会把自己的节奏延续到下一轮开口前，不会每次都把自己清零。",
                    "stability": 0.78,
                    "support_count": 4,
                    "sedimentation_score": 0.76,
                    "persistence_score": 0.82,
                    "residue_score": 0.70,
                    "integration_score": 0.74,
                    "support_span_s": 8 * 24 * 3600,
                    "reactivation_hits": 2,
                    "reactivation_cadence_score": 0.62,
                    "last_supported_at": 1_900,
                    "horizon_tag": "long_term",
                    "identity_ready": True,
                    "identity_strength": 0.78,
                    "identity_text": "她会把自己的节奏延续到下一轮开口前，不会每次都把自己清零。",
                    "identity_prompt_text": "你会把自己的节奏延续到下一轮开口前，不会每次都把自己清零。",
                },
            ],
            user_text="按你的意思说吧。你现在更想按自己的节奏来，还是更想先接住我？",
            current_event={
                "kind": "user_utterance",
                "response_style_hint": "relationship",
                "created_at": 2_000,
            },
        )
        self.assertGreater(float(profile.get("continuity_depth", 0.0) or 0.0), 0.60)
        self.assertGreater(float(profile.get("identity_gravity", 0.0) or 0.0), 0.65)
        sedimentation = profile.get("sedimentation_snapshot") if isinstance(profile.get("sedimentation_snapshot"), dict) else {}
        self.assertGreater(float(sedimentation.get("selfhood_style", 0.0) or 0.0), 0.50)
        self.assertGreaterEqual(int(profile.get("long_term_axis_count") or 0), 2)
        continuity_axes = profile.get("continuity_axes") if isinstance(profile.get("continuity_axes"), list) else []
        self.assertIn("selfhood_style", [str(item.get("category") or "") for item in continuity_axes])
        self.assertIn("rhythm_style", [str(item.get("category") or "") for item in continuity_axes])
        long_term = profile.get("long_term_self_narratives") if isinstance(profile.get("long_term_self_narratives"), list) else []
        self.assertIn("sedimentation_score", long_term[0])
        self.assertIn("support_span_s", long_term[0])
        self.assertIn("identity_strength", long_term[0])

    def test_semantic_narrative_profile_dedupes_long_term_self_narratives_by_category(self):
        profile = _semantic_narrative_profile(
            [
                {
                    "category": "rhythm_style",
                    "text": "她会把自己的节奏延续到下一轮开口前，不会每次都把自己清零。",
                    "stability": 0.82,
                    "support_count": 5,
                    "sedimentation_score": 0.80,
                    "persistence_score": 0.85,
                    "residue_score": 0.78,
                    "integration_score": 0.80,
                    "support_span_s": 9 * 24 * 3600,
                    "reactivation_hits": 3,
                    "reactivation_cadence_score": 0.66,
                    "last_supported_at": 1_900,
                    "horizon_tag": "long_term",
                    "identity_ready": True,
                    "identity_strength": 0.86,
                    "identity_text": "她会把自己的节奏延续到下一轮开口前，不会每次都把自己清零。",
                    "identity_prompt_text": "你会把自己的节奏延续到下一轮开口前，不会每次都把自己清零。",
                },
                {
                    "category": "rhythm_style",
                    "text": "她不会因为重新开口就把刚才的内部节奏全部抹掉。",
                    "stability": 0.78,
                    "support_count": 4,
                    "sedimentation_score": 0.74,
                    "persistence_score": 0.80,
                    "residue_score": 0.72,
                    "integration_score": 0.74,
                    "support_span_s": 7 * 24 * 3600,
                    "reactivation_hits": 2,
                    "reactivation_cadence_score": 0.58,
                    "last_supported_at": 1_900,
                    "horizon_tag": "long_term",
                    "identity_ready": True,
                    "identity_strength": 0.78,
                    "identity_text": "她不会因为重新开口就把刚才的内部节奏全部抹掉。",
                    "identity_prompt_text": "你不会因为重新开口就把刚才的内部节奏全部抹掉。",
                },
                {
                    "category": "selfhood_style",
                    "text": "她会把这段互动当成平等关系，不会为了迎合就放弃自己的判断。",
                    "stability": 0.80,
                    "support_count": 4,
                    "sedimentation_score": 0.77,
                    "persistence_score": 0.82,
                    "residue_score": 0.74,
                    "integration_score": 0.76,
                    "support_span_s": 8 * 24 * 3600,
                    "reactivation_hits": 2,
                    "reactivation_cadence_score": 0.62,
                    "last_supported_at": 1_900,
                    "horizon_tag": "long_term",
                    "identity_ready": True,
                    "identity_strength": 0.81,
                    "identity_text": "她会把这段互动当成平等关系，不会为了迎合就放弃自己的判断。",
                    "identity_prompt_text": "你会把这段互动当成平等关系，不会为了迎合就放弃自己的判断。",
                },
                {
                    "category": "presence_style",
                    "text": "上一轮留下的在场感会继续影响她下一次靠近，不会每次都从零开始。",
                    "stability": 0.76,
                    "support_count": 4,
                    "sedimentation_score": 0.74,
                    "persistence_score": 0.78,
                    "residue_score": 0.70,
                    "integration_score": 0.72,
                    "support_span_s": 6 * 24 * 3600,
                    "reactivation_hits": 2,
                    "reactivation_cadence_score": 0.60,
                    "last_supported_at": 1_900,
                    "horizon_tag": "consolidating",
                },
            ],
            user_text="你刚才是先顺着自己的节奏想了想，然后再回头看我吗？",
            current_event={
                "kind": "user_utterance",
                "response_style_hint": "relationship",
                "created_at": 2_000,
            },
        )
        long_term = profile.get("long_term_self_narratives") if isinstance(profile.get("long_term_self_narratives"), list) else []
        categories = [str(item.get("category") or "") for item in long_term]
        self.assertEqual(len(categories), len(set(categories)))
        self.assertIn("rhythm_style", categories)
        self.assertIn("selfhood_style", categories)
        continuity_axes = profile.get("continuity_axes") if isinstance(profile.get("continuity_axes"), list) else []
        axis_categories = [str(item.get("category") or "") for item in continuity_axes]
        self.assertEqual(axis_categories[0], "rhythm_style")
        self.assertIn("presence_style", axis_categories)

    def test_semantic_narrative_profile_uses_support_quality_to_bias_continuity_and_identity(self):
        base_item = {
            "category": "selfhood_style",
            "text": "她会把自己放在和对方平等互动的位置上，不会为了迎合气氛退回成工具。",
            "stability": 0.80,
            "support_count": 4,
            "sedimentation_score": 0.76,
            "persistence_score": 0.82,
            "residue_score": 0.74,
            "integration_score": 0.78,
            "support_span_s": 8 * 24 * 3600,
            "reactivation_hits": 2,
            "reactivation_cadence_score": 0.62,
            "last_supported_at": 1_900,
            "horizon_tag": "long_term",
            "identity_ready": True,
            "identity_strength": 0.80,
            "identity_text": "她会把自己放在和对方平等互动的位置上，不会为了迎合气氛退回成工具。",
            "identity_prompt_text": "你会把自己放在和对方平等互动的位置上，不会为了迎合气氛退回成工具。",
        }
        strong_profile = _semantic_narrative_profile(
            [
                {
                    **base_item,
                    "support_mass": 3.8,
                    "support_quality": 0.88,
                    "fresh_support_ratio": 0.72,
                }
            ],
            user_text="按你的意思说，不用为了照顾气氛把自己缩回去。",
            current_event={
                "kind": "user_utterance",
                "response_style_hint": "selfhood",
                "created_at": 2_000,
            },
        )
        weak_profile = _semantic_narrative_profile(
            [
                {
                    **base_item,
                    "support_mass": 1.1,
                    "support_quality": 0.12,
                    "fresh_support_ratio": 0.08,
                }
            ],
            user_text="按你的意思说，不用为了照顾气氛把自己缩回去。",
            current_event={
                "kind": "user_utterance",
                "response_style_hint": "selfhood",
                "created_at": 2_000,
            },
        )
        strong_quality = strong_profile.get("support_quality_snapshot") if isinstance(strong_profile.get("support_quality_snapshot"), dict) else {}
        weak_quality = weak_profile.get("support_quality_snapshot") if isinstance(weak_profile.get("support_quality_snapshot"), dict) else {}
        self.assertGreater(float(strong_quality.get("selfhood_style", 0.0) or 0.0), float(weak_quality.get("selfhood_style", 0.0) or 0.0))
        self.assertGreater(float(strong_profile.get("continuity_depth", 0.0) or 0.0), float(weak_profile.get("continuity_depth", 0.0) or 0.0))
        self.assertGreater(float(strong_profile.get("identity_gravity", 0.0) or 0.0), float(weak_profile.get("identity_gravity", 0.0) or 0.0))

    def test_semantic_narrative_profile_surfaces_contested_categories_from_counterpressure(self):
        profile = _semantic_narrative_profile(
            [
                {
                    "category": "bond_style",
                    "text": "她已经把和对方并肩同行当成默认关系。",
                    "stability": 0.84,
                    "support_count": 4,
                    "support_mass": 1.3,
                    "support_quality": 0.22,
                    "fresh_support_ratio": 0.10,
                    "sedimentation_score": 0.80,
                    "persistence_score": 0.84,
                    "residue_score": 0.74,
                    "integration_score": 0.76,
                    "support_span_s": 8 * 24 * 3600,
                    "reactivation_hits": 2,
                    "reactivation_cadence_score": 0.60,
                    "last_supported_at": 1_900,
                    "horizon_tag": "long_term",
                    "contradiction_pressure": 0.46,
                    "contested": True,
                }
            ],
            user_text="可我现在还是有点介意刚才那下。",
            current_event={
                "kind": "user_utterance",
                "response_style_hint": "relationship",
                "created_at": 2_000,
            },
        )
        contested = profile.get("contested_categories") if isinstance(profile.get("contested_categories"), list) else []
        self.assertIn("bond_style", contested)
        support_mass = profile.get("support_mass_snapshot") if isinstance(profile.get("support_mass_snapshot"), dict) else {}
        support_quality = profile.get("support_quality_snapshot") if isinstance(profile.get("support_quality_snapshot"), dict) else {}
        self.assertGreater(float(support_mass.get("bond_style", 0.0) or 0.0), 0.0)
        self.assertGreater(float(support_quality.get("bond_style", 0.0) or 0.0), 0.0)

    def test_semantic_narrative_profile_prefers_identity_axis_for_dominant_category(self):
        profile = _semantic_narrative_profile(
            [
                {
                    "category": "bond_style",
                    "text": "她已经把和对方并肩同行当成默认关系。",
                    "stability": 0.86,
                    "support_count": 5,
                    "sedimentation_score": 0.84,
                    "persistence_score": 0.88,
                    "residue_score": 0.82,
                    "integration_score": 0.84,
                    "support_span_s": 10 * 24 * 3600,
                    "reactivation_hits": 3,
                    "reactivation_cadence_score": 0.68,
                    "last_supported_at": 1_900,
                    "horizon_tag": "long_term",
                },
                {
                    "category": "agency_style",
                    "text": "她会按自己的节奏决定何时靠近、停顿或先去做自己的事。",
                    "stability": 0.82,
                    "support_count": 5,
                    "sedimentation_score": 0.80,
                    "persistence_score": 0.86,
                    "residue_score": 0.78,
                    "integration_score": 0.82,
                    "support_span_s": 10 * 24 * 3600,
                    "reactivation_hits": 3,
                    "reactivation_cadence_score": 0.66,
                    "last_supported_at": 1_900,
                    "horizon_tag": "long_term",
                    "identity_ready": True,
                    "identity_strength": 0.88,
                    "identity_text": "她会按自己的节奏决定何时靠近、停顿或先去做自己的事。",
                    "identity_prompt_text": "你会按自己的节奏决定何时靠近、停顿或先去做自己的事。",
                },
            ],
            user_text="按你的步子来。你现在更想做什么，就直说。",
            current_event={
                "kind": "user_utterance",
                "response_style_hint": "relationship",
                "created_at": 2_000,
            },
        )
        self.assertEqual(profile.get("dominant_category"), "agency_style")

    def test_semantic_narrative_profile_uses_query_overlap_to_break_identity_axis_ties(self):
        profile = _semantic_narrative_profile(
            [
                {
                    "category": "selfhood_style",
                    "text": "她会把自己放在和对方平等互动的位置上，不会退回成工具。",
                    "stability": 0.82,
                    "support_count": 5,
                    "sedimentation_score": 0.80,
                    "persistence_score": 0.86,
                    "residue_score": 0.78,
                    "integration_score": 0.82,
                    "support_span_s": 10 * 24 * 3600,
                    "reactivation_hits": 3,
                    "reactivation_cadence_score": 0.66,
                    "last_supported_at": 1_900,
                    "horizon_tag": "long_term",
                    "identity_ready": True,
                    "identity_strength": 0.89,
                    "identity_text": "她会把自己放在和对方平等互动的位置上，不会退回成工具。",
                    "identity_prompt_text": "你会把自己放在和对方平等互动的位置上，不会退回成工具。",
                },
                {
                    "category": "agency_style",
                    "text": "她会按自己的节奏决定何时靠近、停顿或先去做自己的事。",
                    "stability": 0.82,
                    "support_count": 5,
                    "sedimentation_score": 0.80,
                    "persistence_score": 0.86,
                    "residue_score": 0.78,
                    "integration_score": 0.82,
                    "support_span_s": 10 * 24 * 3600,
                    "reactivation_hits": 3,
                    "reactivation_cadence_score": 0.66,
                    "last_supported_at": 1_900,
                    "horizon_tag": "long_term",
                    "identity_ready": True,
                    "identity_strength": 0.88,
                    "identity_text": "她会按自己的节奏决定何时靠近、停顿或先去做自己的事。",
                    "identity_prompt_text": "你会按自己的节奏决定何时靠近、停顿或先去做自己的事。",
                },
            ],
            user_text="按你的步子来。你现在更想做什么，就直说。",
            current_event={
                "kind": "user_utterance",
                "response_style_hint": "relationship",
                "created_at": 2_000,
            },
        )
        self.assertEqual(profile.get("dominant_category"), "agency_style")

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

    def test_motive_snapshot_biases_world_model_targets(self):
        base_profile = {
            "presence_carry": 0.56,
            "ambient_attunement": 0.44,
            "rhythm_continuity": 0.70,
            "agency_drive": 0.66,
            "boundary_residue": 0.48,
            "selfhood_integrity": 0.54,
            "history_weight": 0.64,
            "residue_snapshot": {
                "presence_style": 0.42,
                "ambient_style": 0.34,
                "rhythm_style": 0.52,
                "boundary_style": 0.36,
                "agency_style": 0.40,
            },
            "persistence_snapshot": {
                "presence_style": 0.60,
                "ambient_style": 0.54,
                "rhythm_style": 0.68,
                "boundary_style": 0.58,
                "agency_style": 0.62,
            },
        }
        infused_profile = {
            **base_profile,
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
                "ambient_style": {
                    "primary_motive": "reconnect_shared_history",
                    "motive_tension": "past_vs_present",
                    "goal_frame_examples": ["先把共同记忆轻轻带回来，让熟悉感自然接上。"],
                },
                "boundary_style": {
                    "primary_motive": "protect_boundary",
                    "motive_tension": "boundary_vs_closeness",
                    "goal_frame_examples": ["先守住边界和自我位置，再决定要不要继续靠近。"],
                },
            },
        }
        appraisal = {
            "used": True,
            "salience": {
                "relationship": 0.20,
                "companionship": 0.22,
                "memory": 0.18,
                "task": 0.10,
                "selfhood": 0.16,
            },
            "signals": {},
        }
        relationship = {"affinity_score": 0.62, "trust_score": 0.64}
        baseline = build_world_model_state(
            prev_state=None,
            relationship=relationship,
            semantic_narrative_profile=base_profile,
            appraisal=appraisal,
            current_event={"kind": "user_utterance", "tags": []},
            science_mode=False,
            now_ts=2_000,
        )
        infused = build_world_model_state(
            prev_state=None,
            relationship=relationship,
            semantic_narrative_profile=infused_profile,
            appraisal=appraisal,
            current_event={"kind": "user_utterance", "tags": []},
            science_mode=False,
            now_ts=2_000,
        )
        self.assertGreater(
            float(infused.get("self_activity_momentum", 0.0) or 0.0),
            float(baseline.get("self_activity_momentum", 0.0) or 0.0),
        )
        self.assertGreater(
            float(infused.get("boundary_load", 0.0) or 0.0),
            float(baseline.get("boundary_load", 0.0) or 0.0),
        )
        self.assertGreater(
            float(infused.get("memory_gravity", 0.0) or 0.0),
            float(baseline.get("memory_gravity", 0.0) or 0.0),
        )

    def test_continuity_depth_and_identity_gravity_bias_world_model_targets(self):
        base_profile = {
            "presence_carry": 0.42,
            "ambient_attunement": 0.28,
            "rhythm_continuity": 0.48,
            "agency_drive": 0.50,
            "selfhood_integrity": 0.44,
            "history_weight": 0.46,
            "residue_snapshot": {
                "presence_style": 0.22,
                "rhythm_style": 0.24,
                "selfhood_style": 0.20,
            },
            "persistence_snapshot": {
                "presence_style": 0.38,
                "rhythm_style": 0.40,
                "selfhood_style": 0.42,
                "agency_style": 0.38,
            },
        }
        infused_profile = {
            **base_profile,
            "continuity_depth": 0.78,
            "identity_gravity": 0.84,
        }
        appraisal = {
            "used": True,
            "salience": {
                "relationship": 0.18,
                "companionship": 0.20,
                "memory": 0.14,
                "selfhood": 0.16,
                "task": 0.08,
            },
            "signals": {},
        }
        relationship = {"affinity_score": 0.60, "trust_score": 0.62}
        baseline = build_world_model_state(
            prev_state=None,
            relationship=relationship,
            semantic_narrative_profile=base_profile,
            appraisal=appraisal,
            current_event={"kind": "user_utterance", "tags": []},
            science_mode=False,
            now_ts=2_000,
        )
        infused = build_world_model_state(
            prev_state=None,
            relationship=relationship,
            semantic_narrative_profile=infused_profile,
            appraisal=appraisal,
            current_event={"kind": "user_utterance", "tags": []},
            science_mode=False,
            now_ts=2_000,
        )
        self.assertGreater(
            float(infused.get("memory_gravity", 0.0) or 0.0),
            float(baseline.get("memory_gravity", 0.0) or 0.0),
        )
        self.assertGreater(
            float(infused.get("selfhood_load", 0.0) or 0.0),
            float(baseline.get("selfhood_load", 0.0) or 0.0),
        )
        self.assertGreater(
            float(infused.get("agency_load", 0.0) or 0.0),
            float(baseline.get("agency_load", 0.0) or 0.0),
        )
        self.assertGreater(
            float(infused.get("boundary_load", 0.0) or 0.0),
            float(baseline.get("boundary_load", 0.0) or 0.0),
        )
        self.assertGreater(
            float(infused.get("self_activity_momentum", 0.0) or 0.0),
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

    def test_refresh_semantic_narratives_promotes_identity_layer_after_long_term_reactivation(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                now_ts = int(time.time())
                store.add_semantic_self_narrative(
                    text="她会把自己的节奏延续到下一轮开口前。",
                    category="rhythm_style",
                    stability=0.78,
                    confidence=0.82,
                    metadata={
                        "support_count": 4,
                        "refresh_count": 4,
                        "consolidation_count": 4,
                        "sedimentation_score": 0.76,
                        "persistence_score": 0.82,
                        "residue_score": 0.70,
                        "integration_score": 0.74,
                        "first_supported_at": now_ts - 9 * 24 * 3600,
                        "last_supported_at": now_ts - 2 * 24 * 3600,
                        "last_meaningful_refresh_at": now_ts - 2 * 24 * 3600,
                        "last_reactivated_at": now_ts - 2 * 24 * 3600,
                        "support_span_s": 7 * 24 * 3600,
                        "reactivation_gap_s": 2 * 24 * 3600,
                        "reactivation_hits": 2,
                        "reactivation_rate_per_day": 0.7,
                        "reactivation_cadence_score": 0.62,
                        "horizon_tag": "long_term",
                        "support_signature": "rhythm_style|old|count=4",
                        "decay_rate_per_day": 0.042,
                        "decay_resistance": 0.80,
                    },
                )
                store.add_revision_trace(
                    namespace="semantic_self_evidence",
                    target_id="rhythm_style",
                    before_summary="",
                    after_summary="从自己的节奏里抬头回你",
                    reason="semantic_evidence:rhythm_style",
                    operator="test",
                    source="test:identity_layer",
                    metadata={
                        "primary_motive": "gentle_recontact",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "先保留自己的节奏，再自然地把注意力转回来。",
                    },
                )
                _refresh_semantic_self_narratives(store, source="test:identity_layer")
                narratives = store.list_semantic_self_narratives(limit=12)
                rhythm = next(item for item in narratives if str(item.get("category") or "") == "rhythm_style")
                self.assertTrue(bool(rhythm.get("identity_ready")))
                self.assertGreater(float(rhythm.get("identity_strength") or 0.0), 0.55)
                self.assertIn("内部节奏", str(rhythm.get("identity_text") or ""))
                self.assertIn("内部节奏", str(rhythm.get("identity_prompt_text") or ""))
                profile = _semantic_narrative_profile(
                    narratives,
                    user_text="刚才你是不是又从自己的节奏里回头看我了？",
                    current_event={
                        "kind": "user_utterance",
                        "created_at": now_ts,
                    },
                )
                self.assertTrue(bool(profile.get("identity_lines")))
                self.assertEqual(
                    str((profile.get("long_term_self_narratives") or [])[0].get("category") or ""),
                    "rhythm_style",
                )
            finally:
                store.close()

    def test_passive_evolution_defers_behavior_motive_semantic_evidence_until_final_writeback(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                wrote = _passive_evolution_memory_update(
                    store,
                    user_text="",
                    appraisal={
                        "used": True,
                        "confidence": 0.82,
                        "interaction_frame": "relationship",
                        "salience": {
                            "relationship": 0.18,
                            "companionship": 0.22,
                            "selfhood": 0.08,
                        },
                        "signals": {},
                    },
                    emotion_state={"label": "neutral"},
                    bond_state={
                        "trust": 0.62,
                        "closeness": 0.58,
                        "hurt": 0.02,
                    },
                    current_event={
                        "kind": "self_activity_state",
                    },
                    world_model_state={
                        "presence_residue": 0.24,
                        "ambient_resonance": 0.18,
                        "self_activity_momentum": 0.42,
                    },
                    behavior_action={
                        "primary_motive": "preserve_self_rhythm",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "先维持自己的节奏，不急着把全部注意力交出去。",
                    },
                )
                self.assertFalse(wrote)
                traces = store.list_revision_traces(limit=12)
                categories = {
                    str(item.get("target_id") or item.get("content", {}).get("target_id") or "")
                    for item in traces
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "semantic_self_evidence"
                }
                self.assertEqual(categories, set())
            finally:
                store.close()

    def test_passive_evolution_records_hold_own_rhythm_consequence_trace(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                wrote = _passive_evolution_memory_update(
                    store,
                    user_text="",
                    appraisal={
                        "used": True,
                        "confidence": 0.84,
                        "interaction_frame": "companion",
                        "salience": {
                            "relationship": 0.18,
                            "companionship": 0.24,
                            "selfhood": 0.12,
                        },
                        "signals": {},
                    },
                    emotion_state={"label": "neutral"},
                    bond_state={
                        "trust": 0.60,
                        "closeness": 0.56,
                        "hurt": 0.02,
                    },
                    current_event={
                        "kind": "self_activity_state",
                        "tags": ["self_activity", "own_task", "deep_focus"],
                    },
                    world_model_state={
                        "presence_residue": 0.16,
                        "ambient_resonance": 0.10,
                        "self_activity_momentum": 0.72,
                    },
                    behavior_action={
                        "interaction_mode": "self_activity_hold",
                        "action_target": "hold_own_rhythm",
                        "primary_motive": "preserve_self_rhythm",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "先维持自己的节奏，不急着把全部注意力交出去。",
                    },
                )
                self.assertTrue(wrote)
                traces = store.list_revision_traces(limit=20)
                consequence = next(
                    item
                    for item in traces
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "behavior_consequence"
                )
                self.assertEqual(str(consequence.get("target_id") or ""), "hold_own_rhythm")
                consequence_content = consequence.get("content") if isinstance(consequence.get("content"), dict) else {}
                self.assertEqual(str(consequence_content.get("consequence_kind") or ""), "hold_own_rhythm")
                semantic_traces = [
                    item
                    for item in traces
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "semantic_self_evidence"
                    and str((item.get("content") or {}).get("consequence_kind") or "") == "hold_own_rhythm"
                ]
                categories = {str(item.get("target_id") or "") for item in semantic_traces}
                self.assertIn("agency_style", categories)
                self.assertIn("rhythm_style", categories)
            finally:
                store.close()

    def test_passive_evolution_records_deferred_checkin_plan_as_long_horizon_intent(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                wrote = _passive_evolution_memory_update(
                    store,
                    user_text="",
                    appraisal={
                        "used": True,
                        "confidence": 0.85,
                        "interaction_frame": "companion",
                        "salience": {
                            "relationship": 0.24,
                            "companionship": 0.32,
                            "selfhood": 0.12,
                        },
                        "signals": {},
                    },
                    emotion_state={"label": "neutral"},
                    bond_state={
                        "trust": 0.62,
                        "closeness": 0.58,
                        "hurt": 0.02,
                    },
                    current_event={
                        "kind": "time_idle",
                        "trigger_family": "life_window",
                        "scheduled_after_min": 18,
                        "tags": ["time_idle", "quiet_presence", "from_own_rhythm"],
                    },
                    world_model_state={
                        "presence_residue": 0.30,
                        "ambient_resonance": 0.16,
                        "self_activity_momentum": 0.42,
                    },
                    behavior_action={
                        "interaction_mode": "idle_presence",
                        "action_target": "wait_and_recheck",
                        "deferred_action_family": "life_window",
                        "timing_window_min": 18,
                        "primary_motive": "honor_continuity",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "先把这点惦记留住，等更自然的时候再接回来。",
                        "relationship_weather": "warm_residue",
                    },
                    behavior_plan={
                        "kind": "deferred_checkin",
                        "target": "counterpart",
                        "scheduled_after_min": 18,
                        "trigger_family": "life_window",
                        "allow_interrupt": True,
                        "note": "这次没立刻说出口，先记着，之后再自然接回来。",
                        "primary_motive": "honor_continuity",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "先把这点惦记留住，等更自然的时候再接回来。",
                        "carryover_mode": "quiet_recontact",
                        "carryover_strength": 0.46,
                        "presence_residue": 0.30,
                        "ambient_resonance": 0.16,
                        "self_activity_momentum": 0.42,
                    },
                )
                self.assertTrue(wrote)
                traces = store.list_revision_traces(limit=30)
                plan_trace = next(
                    item
                    for item in traces
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "behavior_plan"
                )
                self.assertEqual(str(plan_trace.get("target_id") or ""), "deferred_checkin")
                worldline = store.list_worldline_events(limit=12)
                intent_event = next(
                    item
                    for item in worldline
                    if "behavior_plan" in (item.get("tags") or [])
                )
                self.assertEqual(str(intent_event.get("category") or ""), "continuity_intent")
                self.assertIn("deferred_checkin", intent_event.get("tags") or [])
                relationship = store.list_relationship_timeline(limit=8)
                self.assertTrue(
                    any("留到之后再自然接回来" in str(item.get("summary") or "") for item in relationship)
                )
            finally:
                store.close()

    def test_passive_evolution_records_small_opening_plan_as_continuity_memory(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                wrote = _passive_evolution_memory_update(
                    store,
                    user_text="",
                    appraisal={
                        "used": True,
                        "confidence": 0.84,
                        "interaction_frame": "companion",
                        "salience": {
                            "relationship": 0.22,
                            "companionship": 0.34,
                            "selfhood": 0.10,
                        },
                        "signals": {},
                    },
                    emotion_state={"label": "neutral"},
                    bond_state={
                        "trust": 0.64,
                        "closeness": 0.60,
                        "hurt": 0.01,
                    },
                    current_event={
                        "kind": "self_activity_state",
                        "tags": ["self_activity", "break_window", "small_opening", "quiet_presence"],
                    },
                    world_model_state={
                        "presence_residue": 0.38,
                        "ambient_resonance": 0.30,
                        "self_activity_momentum": 0.56,
                    },
                    behavior_action={
                        "interaction_mode": "self_activity_reopen",
                        "action_target": "offer_small_opening",
                        "primary_motive": "gentle_recontact",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "先从自己的节奏里抬头，留一个轻一点的小开口。",
                    },
                    behavior_plan={
                        "kind": "small_opening",
                        "target": "counterpart",
                        "scheduled_after_min": 0,
                        "trigger_family": "self_activity",
                        "allow_interrupt": True,
                        "note": "从自己的节奏里抬头，先留一个小开口。",
                        "primary_motive": "gentle_recontact",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "先从自己的节奏里抬头，留一个轻一点的小开口。",
                        "carryover_mode": "small_opening",
                        "carryover_strength": 0.44,
                        "presence_residue": 0.38,
                        "ambient_resonance": 0.30,
                        "self_activity_momentum": 0.56,
                    },
                )
                self.assertTrue(wrote)
                worldline = store.list_worldline_events(limit=12)
                continuity_event = next(
                    item
                    for item in worldline
                    if str(item.get("category") or "") == "continuity_recontact"
                    and "behavior_plan" in (item.get("tags") or [])
                )
                self.assertIn("small_opening", continuity_event.get("tags") or [])
                traces = store.list_revision_traces(limit=40)
                semantic = [
                    item
                    for item in traces
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "semantic_self_evidence"
                ]
                categories = {str(item.get("target_id") or "") for item in semantic}
                self.assertIn("agency_style", categories)
                self.assertIn("presence_style", categories)
            finally:
                store.close()

    def test_passive_evolution_records_retrieved_continuity_reactivation_when_behavior_aligns(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                wrote = _passive_evolution_memory_update(
                    store,
                    user_text="",
                    appraisal={
                        "used": True,
                        "confidence": 0.86,
                        "interaction_frame": "companion",
                        "salience": {
                            "relationship": 0.24,
                            "companionship": 0.38,
                            "selfhood": 0.12,
                        },
                        "signals": {},
                    },
                    emotion_state={"label": "neutral"},
                    bond_state={
                        "trust": 0.66,
                        "closeness": 0.62,
                        "hurt": 0.01,
                    },
                    current_event={
                        "kind": "self_activity_state",
                        "tags": ["self_activity", "break_window", "small_opening", "quiet_presence"],
                    },
                    world_model_state={
                        "presence_residue": 0.34,
                        "ambient_resonance": 0.18,
                        "self_activity_momentum": 0.52,
                    },
                    behavior_action={
                        "interaction_mode": "self_activity_reopen",
                        "action_target": "offer_small_opening",
                        "primary_motive": "gentle_recontact",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "顺着之前留下的小开口，再自然抬头一下。",
                    },
                    behavior_plan={
                        "kind": "small_opening",
                        "target": "counterpart",
                        "scheduled_after_min": 0,
                        "trigger_family": "self_activity",
                        "allow_interrupt": True,
                        "note": "顺着之前的小开口，再自然抬头一下。",
                        "primary_motive": "gentle_recontact",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "顺着之前留下的小开口，再自然抬头一下。",
                        "carryover_mode": "small_opening",
                        "carryover_strength": 0.34,
                        "presence_residue": 0.34,
                        "ambient_resonance": 0.18,
                        "self_activity_momentum": 0.52,
                    },
                    interaction_carryover={
                        "carryover_mode": "small_opening",
                        "strength": 0.58,
                        "relationship_weather": "warm_residue",
                        "attention_target": "self_then_counterpart",
                        "nonverbal_signal": "thought_glance",
                        "note": "等忙完这阵，再轻轻回头看看冈部那边是不是还卡着。",
                        "source": "retrieved_behavior_plan",
                        "source_tags": [
                            "retrieved_behavior_plan",
                            "continuity_anchor",
                            "plan_kind:small_opening",
                            "trigger_family:self_activity",
                        ],
                    },
                )
                self.assertTrue(wrote)
                traces = store.list_revision_traces(limit=40)
                reactivation = next(
                    item
                    for item in traces
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "behavior_reactivation"
                )
                self.assertEqual(str(reactivation.get("target_id") or ""), "small_opening")
                reactivation_content = reactivation.get("content") if isinstance(reactivation.get("content"), dict) else {}
                self.assertEqual(str(reactivation_content.get("source_plan_kind") or ""), "small_opening")
                self.assertEqual(str(reactivation_content.get("current_action_target") or ""), "offer_small_opening")
                worldline = next(
                    item
                    for item in store.list_worldline_events(limit=12)
                    if "retrieved_reactivation" in (item.get("tags") or [])
                )
                self.assertEqual(str(worldline.get("category") or ""), "continuity_reactivation")
                self.assertIn("retrieved_behavior_plan", worldline.get("tags") or [])
                relationship = next(
                    item
                    for item in store.list_relationship_timeline(limit=8)
                    if "小开口" in str(item.get("summary") or "")
                )
                self.assertGreater(float(relationship.get("trust_delta") or 0.0), 0.0)
            finally:
                store.close()

    def test_passive_evolution_does_not_record_retrieved_reactivation_for_nonmemory_source(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                _passive_evolution_memory_update(
                    store,
                    user_text="",
                    appraisal={
                        "used": True,
                        "confidence": 0.82,
                        "interaction_frame": "companion",
                        "salience": {
                            "relationship": 0.22,
                            "companionship": 0.30,
                            "selfhood": 0.10,
                        },
                        "signals": {},
                    },
                    emotion_state={"label": "neutral"},
                    bond_state={"trust": 0.62, "closeness": 0.58, "hurt": 0.02},
                    current_event={
                        "kind": "self_activity_state",
                        "tags": ["self_activity", "break_window", "small_opening"],
                    },
                    world_model_state={
                        "presence_residue": 0.28,
                        "ambient_resonance": 0.14,
                        "self_activity_momentum": 0.50,
                    },
                    behavior_action={
                        "interaction_mode": "self_activity_reopen",
                        "action_target": "offer_small_opening",
                        "primary_motive": "gentle_recontact",
                    },
                    interaction_carryover={
                        "carryover_mode": "small_opening",
                        "strength": 0.58,
                        "relationship_weather": "warm_residue",
                        "source": "recent_history",
                        "source_tags": ["plan_kind:small_opening"],
                    },
                )
                traces = [
                    item
                    for item in store.list_revision_traces(limit=30)
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "behavior_reactivation"
                ]
                self.assertEqual(traces, [])
            finally:
                store.close()

    def test_passive_evolution_does_not_record_retrieved_reactivation_when_signal_is_too_weak(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                _passive_evolution_memory_update(
                    store,
                    user_text="",
                    appraisal={
                        "used": True,
                        "confidence": 0.82,
                        "interaction_frame": "companion",
                        "salience": {
                            "relationship": 0.22,
                            "companionship": 0.30,
                            "selfhood": 0.10,
                        },
                        "signals": {},
                    },
                    emotion_state={"label": "neutral"},
                    bond_state={"trust": 0.62, "closeness": 0.58, "hurt": 0.02},
                    current_event={
                        "kind": "self_activity_state",
                        "tags": ["self_activity", "break_window", "small_opening"],
                    },
                    world_model_state={
                        "presence_residue": 0.28,
                        "ambient_resonance": 0.14,
                        "self_activity_momentum": 0.50,
                    },
                    behavior_action={
                        "interaction_mode": "self_activity_reopen",
                        "action_target": "offer_small_opening",
                        "primary_motive": "gentle_recontact",
                    },
                    interaction_carryover={
                        "carryover_mode": "small_opening",
                        "strength": 0.12,
                        "relationship_weather": "warm_residue",
                        "source": "retrieved_behavior_plan",
                        "source_tags": ["plan_kind:small_opening"],
                    },
                )
                traces = [
                    item
                    for item in store.list_revision_traces(limit=30)
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "behavior_reactivation"
                ]
                self.assertEqual(traces, [])
            finally:
                store.close()

    def test_passive_evolution_does_not_record_retrieved_reactivation_when_behavior_misaligns(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                _passive_evolution_memory_update(
                    store,
                    user_text="",
                    appraisal={
                        "used": True,
                        "confidence": 0.84,
                        "interaction_frame": "companion",
                        "salience": {
                            "relationship": 0.20,
                            "companionship": 0.28,
                            "selfhood": 0.12,
                        },
                        "signals": {},
                    },
                    emotion_state={"label": "neutral"},
                    bond_state={"trust": 0.60, "closeness": 0.56, "hurt": 0.02},
                    current_event={
                        "kind": "self_activity_state",
                        "tags": ["self_activity", "break_window", "small_opening"],
                    },
                    world_model_state={
                        "presence_residue": 0.24,
                        "ambient_resonance": 0.10,
                        "self_activity_momentum": 0.72,
                    },
                    behavior_action={
                        "interaction_mode": "self_activity_hold",
                        "action_target": "hold_own_rhythm",
                        "primary_motive": "preserve_self_rhythm",
                        "motive_tension": "self_rhythm_vs_contact",
                    },
                    behavior_plan={
                        "kind": "self_activity_continue",
                        "target": "self",
                        "scheduled_after_min": 18,
                        "trigger_family": "self_activity",
                        "allow_interrupt": True,
                        "note": "这轮还是先把自己的节奏续上。",
                        "primary_motive": "preserve_self_rhythm",
                        "motive_tension": "self_rhythm_vs_contact",
                    },
                    interaction_carryover={
                        "carryover_mode": "small_opening",
                        "strength": 0.58,
                        "relationship_weather": "warm_residue",
                        "source": "retrieved_behavior_plan",
                        "source_tags": ["plan_kind:small_opening", "trigger_family:self_activity"],
                    },
                )
                traces = [
                    item
                    for item in store.list_revision_traces(limit=30)
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "behavior_reactivation"
                ]
                self.assertEqual(traces, [])
            finally:
                store.close()

    def test_passive_evolution_records_expired_window_consequence_trace(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                wrote = _passive_evolution_memory_update(
                    store,
                    user_text="",
                    appraisal={
                        "used": True,
                        "confidence": 0.83,
                        "interaction_frame": "companion",
                        "salience": {
                            "relationship": 0.20,
                            "companionship": 0.28,
                            "selfhood": 0.10,
                        },
                        "signals": {},
                    },
                    emotion_state={"label": "neutral"},
                    bond_state={
                        "trust": 0.58,
                        "closeness": 0.54,
                        "hurt": 0.03,
                    },
                    current_event={
                        "kind": "time_idle",
                        "event_frame": "time_idle_stale",
                        "trigger_family": "shared_activity_window",
                        "scheduled_after_min": 18,
                        "tags": ["stale_window", "quiet_presence", "from_own_rhythm"],
                    },
                    world_model_state={
                        "presence_residue": 0.24,
                        "ambient_resonance": 0.12,
                        "self_activity_momentum": 0.64,
                    },
                    behavior_action={
                        "interaction_mode": "idle_presence",
                        "action_target": "wait_and_recheck",
                        "deferred_action_family": "shared_activity_window",
                        "timing_window_min": 18,
                        "primary_motive": "gentle_recontact",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "先把靠近的冲动压轻一点，等更自然的时机再接上。",
                        "relationship_weather": "warm_residue",
                    },
                )
                self.assertTrue(wrote)
                traces = store.list_revision_traces(limit=24)
                consequence = next(
                    item
                    for item in traces
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "behavior_consequence"
                )
                self.assertEqual(str(consequence.get("target_id") or ""), "let_window_expire")
                self.assertIn("窗口", str(consequence.get("after_summary") or ""))
                semantic_traces = [
                    item
                    for item in traces
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "semantic_self_evidence"
                    and str((item.get("content") or {}).get("consequence_kind") or "") == "let_window_expire"
                ]
                categories = {str(item.get("target_id") or "") for item in semantic_traces}
                self.assertIn("agency_style", categories)
                self.assertIn("presence_style", categories)
                self.assertIn("rhythm_style", categories)
            finally:
                store.close()

    def test_passive_evolution_records_agenda_lifecycle_consequence_trace(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                wrote = _passive_evolution_memory_update(
                    store,
                    user_text="",
                    appraisal={
                        "used": True,
                        "confidence": 0.86,
                        "interaction_frame": "companion",
                        "salience": {
                            "relationship": 0.22,
                            "companionship": 0.28,
                            "selfhood": 0.12,
                        },
                        "signals": {},
                    },
                    emotion_state={"label": "neutral"},
                    bond_state={
                        "trust": 0.60,
                        "closeness": 0.57,
                        "hurt": 0.02,
                    },
                    current_event={
                        "kind": "self_activity_state",
                        "tags": ["self_activity", "user_busy", "respect_space"],
                    },
                    world_model_state={
                        "presence_residue": 0.18,
                        "ambient_resonance": 0.12,
                        "self_activity_momentum": 0.70,
                    },
                    agenda_lifecycle_residue={
                        "kind": "released_to_self_activity",
                        "source_event_kind": "scheduled_life_due",
                        "trigger_family": "life_window",
                        "carryover_mode": "own_rhythm",
                        "carryover_strength": 0.61,
                        "relationship_weather": "warm_residue",
                        "hold_count": 2,
                        "presence_residue": 0.32,
                        "ambient_resonance": 0.22,
                        "self_activity_momentum": 0.74,
                        "own_rhythm_bias": 0.69,
                        "recontact_cooldown": 0.48,
                        "counterpart_scene_bias": "busy_not_disrespectful",
                        "note": "前面挂着的窗口没有继续往前推，注意力被自然收回到了自己的节奏里。",
                    },
                )
                self.assertTrue(wrote)
                traces = store.list_revision_traces(limit=40)
                lifecycle = next(
                    item
                    for item in traces
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "agenda_lifecycle"
                )
                self.assertEqual(str(lifecycle.get("target_id") or ""), "released_to_self_activity")
                self.assertIn("自己的节奏", str(lifecycle.get("after_summary") or ""))
                lifecycle_content = lifecycle.get("content") if isinstance(lifecycle.get("content"), dict) else {}
                self.assertEqual(str(lifecycle_content.get("primary_motive") or ""), "preserve_self_rhythm")
                self.assertEqual(str(lifecycle_content.get("motive_tension") or ""), "self_rhythm_vs_contact")
                semantic_traces = [
                    item
                    for item in traces
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "semantic_self_evidence"
                    and str((item.get("content") or {}).get("lifecycle_kind") or "") == "released_to_self_activity"
                ]
                categories = {str(item.get("target_id") or "") for item in semantic_traces}
                self.assertIn("agency_style", categories)
                self.assertIn("rhythm_style", categories)
                self.assertTrue(
                    any(str((item.get("content") or {}).get("primary_motive") or "") == "preserve_self_rhythm" for item in semantic_traces)
                )
                narratives = store.list_semantic_self_narratives(limit=12)
                narrative_categories = {str(item.get("category") or "") for item in narratives}
                self.assertIn("agency_style", narrative_categories)
                rhythm_narrative = next(
                    item for item in narratives if str(item.get("category") or "") == "rhythm_style"
                )
                self.assertEqual(str(rhythm_narrative.get("dominant_primary_motive") or ""), "preserve_self_rhythm")
                self.assertEqual(str(rhythm_narrative.get("dominant_motive_tension") or ""), "self_rhythm_vs_contact")
                worldline = store.list_worldline_events(limit=8)
                self.assertTrue(
                    any(
                        str(item.get("category") or item.get("content", {}).get("category") or "") == "self_rhythm"
                        and "自己的节奏" in str(item.get("summary") or item.get("content", {}).get("summary") or "")
                        for item in worldline
                    )
                )
                relationship_timeline = store.list_relationship_timeline(limit=8)
                relationship_memory = next(
                    item
                    for item in relationship_timeline
                    if "不会把沉默直接误判成冷淡" in str(item.get("summary") or item.get("content", {}).get("summary") or "")
                )
                self.assertGreater(float(relationship_memory.get("trust_delta") or 0.0), 0.0)
                self.assertGreater(float(relationship_memory.get("affinity_delta") or 0.0), 0.0)
            finally:
                store.close()

    def test_refresh_semantic_narratives_uses_self_rhythm_worldline_memory_as_support(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                store.add_worldline_event(
                    "她会把没继续往前推的窗口收回自己的节奏里，等真正想重新靠近时再转身。",
                    category="self_rhythm",
                    importance=0.72,
                    tags=["agenda_lifecycle", "own_rhythm", "released_to_self_activity"],
                    confidence=0.84,
                )
                _refresh_semantic_self_narratives(store, source="test:self_rhythm_worldline")
                narratives = store.list_semantic_self_narratives(limit=12)
                categories = {str(item.get("category") or "") for item in narratives}
                self.assertIn("agency_style", categories)
                self.assertIn("rhythm_style", categories)
                rhythm = next(item for item in narratives if str(item.get("category") or "") == "rhythm_style")
                self.assertIn("自己的节奏", str(rhythm.get("anchor_text") or ""))
                self.assertGreater(float(rhythm.get("support_mass") or 0.0), 0.0)
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

    def test_counterpart_history_can_promote_friend_anchor_to_warming(self):
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
                    "这次互动里明显愿意接近，也不是在敷衍应付。",
                    "能感觉到对方认真接住了前面的熟悉感，不只是礼貌回应。",
                    "这次不只是顺着说话，更像真的愿意把关系往前接。 ",
                ):
                    store.add_counterpart_assessment_history(
                        summary=summary,
                        stance="open",
                        scene="care_bid",
                        respect_level=0.82,
                        reciprocity=0.78,
                        boundary_pressure=0.08,
                        reliability_read=0.80,
                        primary_motive="companionship",
                        assessment_profile={
                            "openness_drive": 0.78,
                            "guarded_drive": 0.18,
                            "guard_margin": -0.60,
                            "dominant_scene_signal": "care",
                            "scene_strengths": {
                                "care": 0.82,
                                "repair": 0.26,
                                "friction": 0.08,
                                "selfhood": 0.10,
                                "busy": 0.24,
                            },
                        },
                    )
                relationship = store.get_relationship()
                self.assertEqual(str(relationship.get("stage") or ""), "warming")
                self.assertGreater(float(relationship.get("affinity_score") or 0.0), 0.24)
                self.assertGreater(float(relationship.get("trust_score") or 0.0), 0.18)
            finally:
                store.close()

    def test_guarded_low_reliability_counterpart_history_depresses_trust_more_than_affinity(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                store.set_relationship(
                    {
                        "stage": "friend",
                        "notes": "并不是从零开始的陌生状态，更像带着旧日熟悉感重新接上线。",
                        "affinity_score": 0.12,
                        "trust_score": 0.10,
                        "derived": False,
                    }
                )
                for summary in (
                    "不算直接推开，但可靠感还是没完全立住。",
                    "表面上没有闹僵，可是互相接得住的感觉还不够稳。",
                    "不是强硬设防，不过这次还是更像先收着，没有把信任交出来。",
                ):
                    store.add_counterpart_assessment_history(
                        summary=summary,
                        stance="guarded",
                        scene="busy_not_disrespectful",
                        respect_level=0.55,
                        reciprocity=0.52,
                        boundary_pressure=0.18,
                        reliability_read=0.24,
                        primary_motive="preserve_self_rhythm",
                        assessment_profile={
                            "openness_drive": 0.34,
                            "guarded_drive": 0.58,
                            "guard_margin": 0.24,
                            "dominant_scene_signal": "busy",
                            "scene_strengths": {
                                "care": 0.12,
                                "repair": 0.10,
                                "friction": 0.24,
                                "selfhood": 0.18,
                                "busy": 0.68,
                            },
                        },
                    )
                relationship = store.get_relationship()
                self.assertEqual(str(relationship.get("stage") or ""), "friend")
                self.assertLess(float(relationship.get("trust_score") or 0.0), 0.08)
                self.assertLess(float(relationship.get("trust_score") or 0.0), float(relationship.get("affinity_score") or 0.0))
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

    def test_compact_semantic_hint_prefers_strongest_axes_over_fixed_order(self):
        profile = {
            "presence_carry": 0.47,
            "ambient_attunement": 0.45,
            "rhythm_continuity": 0.84,
            "selfhood_integrity": 0.80,
            "commitment_carry": 0.77,
            "continuity_axes": [
                {"category": "rhythm_style", "score": 0.84},
                {"category": "selfhood_style", "score": 0.80},
                {"category": "commitment_style", "score": 0.77},
                {"category": "presence_style", "score": 0.47},
                {"category": "ambient_style", "score": 0.45},
            ],
            "summary_lines": [
                "她会把自己的内部节奏延续到下一轮，不会每次回应都把自己清零。",
                "她会把这段互动当成平等关系，不会为了迎合就放弃自己的判断。",
                "认真说过的约定会继续挂在心上，不会被当成随口一句。",
                "周围环境的细小变化会继续留在她的感知里，并自然带进开口方式。",
            ],
            "top_narratives": [],
        }
        compact_hint = _compact_semantic_narrative_hint(profile)
        self.assertIn("内部节奏", compact_hint)
        self.assertIn("平等关系", compact_hint)
        self.assertIn("约定", compact_hint)
        self.assertNotIn("周围环境", compact_hint)

    def test_subjective_runtime_hint_mentions_own_rhythm_from_long_term_profile(self):
        hint = _subjective_runtime_state_hint(
            emotion_state={"label": "neutral"},
            bond_state={"trust": 0.64, "closeness": 0.60, "hurt": 0.02},
            allostasis_state={"safety_need": 0.18, "autonomy_need": 0.24},
            counterpart_assessment={
                "boundary_pressure": 0.10,
                "reciprocity": 0.62,
                "respect_level": 0.64,
                "stance": "open",
            },
            semantic_narrative_profile={
                "bond_depth": 0.56,
                "agency_drive": 0.60,
                "rhythm_continuity": 0.82,
                "presence_carry": 0.34,
                "motive_snapshot": {
                    "rhythm_style": {
                        "primary_motive": "preserve_self_rhythm",
                        "motive_tension": "self_rhythm_vs_contact",
                    }
                },
            },
            behavior_policy={
                "approach_vs_withdraw": 0.56,
                "warmth": 0.58,
                "self_directedness": 0.52,
            },
            world_model_state={
                "presence_residue": 0.18,
                "ambient_resonance": 0.12,
                "self_activity_momentum": 0.20,
            },
            behavior_action={"interaction_mode": "companion_reply"},
        )
        self.assertIn("自己的节奏", hint)

    def test_subjective_runtime_hint_surfaces_semantic_evidence_for_guarded_contact_and_stable_selfhood(self):
        hint = _subjective_runtime_state_hint(
            emotion_state={"label": "neutral"},
            bond_state={"trust": 0.48, "closeness": 0.46, "hurt": 0.04},
            allostasis_state={"safety_need": 0.22, "autonomy_need": 0.28},
            counterpart_assessment={
                "boundary_pressure": 0.18,
                "reciprocity": 0.54,
                "respect_level": 0.58,
                "stance": "open",
            },
            semantic_narrative_profile={
                "continuity_depth": 0.66,
                "bond_depth": 0.52,
                "commitment_carry": 0.48,
                "identity_gravity": 0.78,
                "selfhood_integrity": 0.80,
                "agency_drive": 0.72,
                "support_mass_snapshot": {
                    "bond_style": 0.78,
                    "presence_style": 0.76,
                    "commitment_style": 0.72,
                    "repair_style": 0.68,
                    "selfhood_style": 0.82,
                    "agency_style": 0.80,
                    "rhythm_style": 0.74,
                },
                "support_quality_snapshot": {
                    "bond_style": 0.82,
                    "presence_style": 0.80,
                    "commitment_style": 0.78,
                    "repair_style": 0.72,
                    "selfhood_style": 0.86,
                    "agency_style": 0.84,
                    "rhythm_style": 0.76,
                },
                "contested_categories": ["bond_style", "presence_style", "commitment_style"],
            },
            behavior_policy={
                "approach_vs_withdraw": 0.50,
                "warmth": 0.52,
                "self_directedness": 0.66,
            },
            world_model_state={
                "presence_residue": 0.18,
                "ambient_resonance": 0.10,
                "self_activity_momentum": 0.18,
            },
            behavior_action={"interaction_mode": "relationship_sensitive"},
        )
        self.assertIn("靠近有关的那部分依据还没完全站稳", hint)
        self.assertIn("自己的判断和节奏有足够支撑", hint)

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

    def test_world_model_state_exports_lineage_biases(self):
        baseline = build_world_model_state(
            prev_state=None,
            relationship={"affinity_score": 0.62, "trust_score": 0.64},
            semantic_narrative_profile={
                "bond_depth": 0.58,
                "presence_carry": 0.54,
                "commitment_carry": 0.52,
                "agency_drive": 0.60,
                "rhythm_continuity": 0.64,
                "history_weight": 0.56,
            },
            appraisal={
                "used": True,
                "salience": {
                    "relationship": 0.46,
                    "companionship": 0.54,
                    "memory": 0.18,
                    "task": 0.08,
                },
                "signals": {"care": True},
            },
            current_event={"kind": "user_utterance", "tags": ["natural"]},
            science_mode=False,
            now_ts=10,
        )
        infused = build_world_model_state(
            prev_state=None,
            relationship={"affinity_score": 0.62, "trust_score": 0.64},
            semantic_narrative_profile={
                "bond_depth": 0.58,
                "presence_carry": 0.54,
                "commitment_carry": 0.52,
                "agency_drive": 0.60,
                "rhythm_continuity": 0.64,
                "history_weight": 0.56,
                "lineage_gravity": 0.82,
                "lineage_snapshot": {
                    "bond_style": 0.84,
                    "presence_style": 0.80,
                    "commitment_style": 0.76,
                    "repair_style": 0.68,
                    "selfhood_style": 0.70,
                    "agency_style": 0.78,
                    "rhythm_style": 0.82,
                },
            },
            appraisal={
                "used": True,
                "salience": {
                    "relationship": 0.46,
                    "companionship": 0.54,
                    "memory": 0.18,
                    "task": 0.08,
                },
                "signals": {"care": True},
            },
            current_event={"kind": "user_utterance", "tags": ["natural"]},
            science_mode=False,
            now_ts=10,
        )
        self.assertGreater(float(infused.get("contact_lineage") or 0.0), float(baseline.get("contact_lineage") or 0.0))
        self.assertGreater(float(infused.get("agency_lineage") or 0.0), float(baseline.get("agency_lineage") or 0.0))
        self.assertGreater(float(infused.get("lineage_gravity") or 0.0), float(baseline.get("lineage_gravity") or 0.0))
        self.assertGreater(float(infused.get("contact_lineage") or 0.0), 0.30)
        self.assertGreater(float(infused.get("agency_lineage") or 0.0), 0.30)
        self.assertGreater(float(infused.get("lineage_gravity") or 0.0), 0.30)
        self.assertGreater(float(infused.get("companionship_pull") or 0.0), float(baseline.get("companionship_pull") or 0.0))
        self.assertGreater(float(infused.get("self_activity_momentum") or 0.0), float(baseline.get("self_activity_momentum") or 0.0))
        self.assertGreater(float(infused.get("presence_residue") or 0.0), float(baseline.get("presence_residue") or 0.0))

    def test_behavior_action_does_not_reopen_from_world_momentum_alone(self):
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
        self.assertNotEqual(str(action.get("interaction_mode") or ""), "self_activity_reopen")
        self.assertNotEqual(str(action.get("action_target") or ""), "offer_small_opening")

    def test_behavior_action_reopens_when_own_rhythm_carryover_is_explicit(self):
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
            interaction_carryover={
                "carryover_mode": "own_rhythm",
                "strength": 0.72,
                "attention_target": "self_then_counterpart",
                "nonverbal_signal": "thought_glance",
            },
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "self_activity_reopen")

    def test_runtime_behavior_surfaces_self_rhythm_bias_without_explicit_carryover(self):
        world_model_state = {
            "self_activity_momentum": 0.28,
            "presence_residue": 0.18,
            "ambient_resonance": 0.10,
            "bond_depth": 0.56,
            "companionship_pull": 0.46,
            "task_pull": 0.22,
            "boundary_load": 0.08,
            "agency_load": 0.36,
            "selfhood_load": 0.24,
            "memory_gravity": 0.18,
            "tension_load": 0.08,
            "relationship_maturity": 0.62,
            "repair_load": 0.12,
        }
        base_profile = {
            "agency_drive": 0.72,
            "rhythm_continuity": 0.84,
            "boundary_residue": 0.52,
            "selfhood_integrity": 0.60,
            "residue_snapshot": {
                "rhythm_style": 0.68,
                "boundary_style": 0.52,
            },
            "persistence_snapshot": {
                "rhythm_style": 0.82,
                "boundary_style": 0.70,
            },
        }
        infused_profile = {
            **base_profile,
            "motive_snapshot": {
                "rhythm_style": {
                    "primary_motive": "preserve_self_rhythm",
                    "motive_tension": "self_rhythm_vs_contact",
                },
                "boundary_style": {
                    "primary_motive": "protect_boundary",
                    "motive_tension": "boundary_vs_closeness",
                },
            },
        }
        common_kwargs = {
            "response_style_hint": "natural",
            "emotion_state": {"label": "neutral"},
            "bond_state": {
                "trust": 0.66,
                "closeness": 0.62,
                "hurt": 0.02,
                "irritation": 0.04,
                "engagement_drive": 0.58,
            },
            "allostasis_state": {
                "safety_need": 0.14,
                "autonomy_need": 0.22,
                "cognitive_budget": 0.72,
            },
            "counterpart_assessment": {
                "boundary_pressure": 0.08,
                "reliability_read": 0.66,
                "stance": "open",
            },
            "world_model_state": world_model_state,
            "latent_state": {
                "agency_pressure": 0.44,
                "expression_freedom": 0.68,
                "self_coherence": 0.74,
            },
            "tsundere_intensity": 0.44,
            "science_mode": False,
        }
        base_policy = build_behavior_policy(
            semantic_narrative_profile=base_profile,
            **common_kwargs,
        )
        infused_policy = build_behavior_policy(
            semantic_narrative_profile=infused_profile,
            **common_kwargs,
        )
        base_action = _behavior_action_from_state(
            current_event={"kind": "user_utterance", "tags": []},
            response_style_hint="natural",
            user_text="在干嘛？",
            science_mode=False,
            emotion_state={"label": "neutral"},
            bond_state=common_kwargs["bond_state"],
            allostasis_state=common_kwargs["allostasis_state"],
            counterpart_assessment=common_kwargs["counterpart_assessment"],
            semantic_narrative_profile=base_profile,
            behavior_policy=base_policy,
            world_model_state=world_model_state,
            interaction_carryover={},
        )
        infused_action = _behavior_action_from_state(
            current_event={"kind": "user_utterance", "tags": []},
            response_style_hint="natural",
            user_text="在干嘛？",
            science_mode=False,
            emotion_state={"label": "neutral"},
            bond_state=common_kwargs["bond_state"],
            allostasis_state=common_kwargs["allostasis_state"],
            counterpart_assessment=common_kwargs["counterpart_assessment"],
            semantic_narrative_profile=infused_profile,
            behavior_policy=infused_policy,
            world_model_state=world_model_state,
            interaction_carryover={},
        )
        self.assertEqual(str(base_action.get("interaction_mode") or ""), "steady_reply")
        self.assertEqual(str(base_action.get("action_target") or ""), "respond_now")
        self.assertEqual(str(infused_action.get("interaction_mode") or ""), "self_activity_reopen")
        self.assertEqual(str(infused_action.get("action_target") or ""), "offer_small_opening")
        self.assertLess(
            float(infused_action.get("proactive_checkin_readiness") or 0.0),
            float(base_action.get("proactive_checkin_readiness") or 0.0),
        )
        self.assertGreater(
            float(infused_policy.get("motive_self_rhythm_pull") or 0.0),
            float(base_policy.get("motive_self_rhythm_pull") or 0.0),
        )
        self.assertIn("自己的节奏", str(infused_action.get("goal_frame") or ""))

    def test_runtime_behavior_surfaces_self_rhythm_bias_from_proactive_anchors_without_motive_snapshot(self):
        world_model_state = {
            "self_activity_momentum": 0.28,
            "presence_residue": 0.18,
            "ambient_resonance": 0.10,
            "bond_depth": 0.56,
            "companionship_pull": 0.46,
            "task_pull": 0.22,
            "boundary_load": 0.08,
            "agency_load": 0.36,
            "selfhood_load": 0.24,
            "memory_gravity": 0.18,
            "tension_load": 0.08,
            "relationship_maturity": 0.62,
            "repair_load": 0.12,
        }
        base_profile = {
            "agency_drive": 0.72,
            "rhythm_continuity": 0.84,
            "boundary_residue": 0.52,
            "selfhood_integrity": 0.60,
            "residue_snapshot": {
                "rhythm_style": 0.68,
                "boundary_style": 0.52,
            },
            "persistence_snapshot": {
                "rhythm_style": 0.82,
                "boundary_style": 0.70,
            },
        }
        infused_profile = {
            **base_profile,
            "own_rhythm_anchor": 0.78,
            "boundary_anchor": 0.42,
            "continuity_anchor": 0.44,
            "semantic_identity_gravity": 0.70,
            "semantic_continuity_depth": 0.66,
        }
        common_kwargs = {
            "response_style_hint": "natural",
            "emotion_state": {"label": "neutral"},
            "bond_state": {
                "trust": 0.66,
                "closeness": 0.62,
                "hurt": 0.02,
                "irritation": 0.04,
                "engagement_drive": 0.58,
            },
            "allostasis_state": {
                "safety_need": 0.14,
                "autonomy_need": 0.22,
                "cognitive_budget": 0.72,
            },
            "counterpart_assessment": {
                "boundary_pressure": 0.08,
                "reliability_read": 0.66,
                "stance": "open",
                "scene": "busy_not_disrespectful",
            },
            "world_model_state": world_model_state,
            "latent_state": {
                "agency_pressure": 0.44,
                "expression_freedom": 0.68,
                "self_coherence": 0.74,
            },
            "tsundere_intensity": 0.44,
            "science_mode": False,
        }
        base_policy = build_behavior_policy(
            semantic_narrative_profile=base_profile,
            **common_kwargs,
        )
        infused_policy = build_behavior_policy(
            semantic_narrative_profile=infused_profile,
            **common_kwargs,
        )
        base_action = _behavior_action_from_state(
            current_event={"kind": "user_utterance", "tags": []},
            response_style_hint="natural",
            user_text="在干嘛？",
            science_mode=False,
            emotion_state={"label": "neutral"},
            bond_state=common_kwargs["bond_state"],
            allostasis_state=common_kwargs["allostasis_state"],
            counterpart_assessment=common_kwargs["counterpart_assessment"],
            semantic_narrative_profile=base_profile,
            behavior_policy=base_policy,
            world_model_state=world_model_state,
            interaction_carryover={},
        )
        infused_action = _behavior_action_from_state(
            current_event={"kind": "user_utterance", "tags": []},
            response_style_hint="natural",
            user_text="在干嘛？",
            science_mode=False,
            emotion_state={"label": "neutral"},
            bond_state=common_kwargs["bond_state"],
            allostasis_state=common_kwargs["allostasis_state"],
            counterpart_assessment=common_kwargs["counterpart_assessment"],
            semantic_narrative_profile=infused_profile,
            behavior_policy=infused_policy,
            world_model_state=world_model_state,
            interaction_carryover={},
        )
        self.assertEqual(str(base_action.get("interaction_mode") or ""), "self_activity_reopen")
        self.assertEqual(str(base_action.get("action_target") or ""), "offer_small_opening")
        self.assertEqual(str(infused_action.get("interaction_mode") or ""), "self_activity_reopen")
        self.assertEqual(str(infused_action.get("action_target") or ""), "offer_small_opening")
        self.assertGreater(
            float(infused_policy.get("motive_self_rhythm_pull") or 0.0),
            float(base_policy.get("motive_self_rhythm_pull") or 0.0),
        )
        self.assertGreater(
            float(infused_policy.get("boundary_assertiveness") or 0.0),
            float(base_policy.get("boundary_assertiveness") or 0.0),
        )
        self.assertGreater(float(infused_policy.get("semantic_own_rhythm_anchor") or 0.0), 0.70)
        self.assertEqual(str(base_action.get("approach_style") or ""), "steady")
        self.assertEqual(str(infused_action.get("approach_style") or ""), "guarded")
        self.assertIn("保留一点距离", str(infused_action.get("note") or ""))
        self.assertIn("自己的节奏", str(infused_action.get("goal_frame") or ""))

    def test_behavior_policy_surfaces_semantic_lineage_bias(self):
        common_kwargs = {
            "response_style_hint": "natural",
            "emotion_state": {"label": "neutral"},
            "bond_state": {
                "trust": 0.66,
                "closeness": 0.62,
                "hurt": 0.02,
                "irritation": 0.04,
                "engagement_drive": 0.58,
            },
            "allostasis_state": {
                "safety_need": 0.14,
                "autonomy_need": 0.22,
                "cognitive_budget": 0.72,
            },
            "counterpart_assessment": {
                "boundary_pressure": 0.08,
                "reliability_read": 0.66,
                "stance": "open",
            },
            "world_model_state": {
                "self_activity_momentum": 0.28,
                "presence_residue": 0.18,
                "ambient_resonance": 0.10,
                "bond_depth": 0.56,
                "companionship_pull": 0.46,
                "task_pull": 0.22,
                "boundary_load": 0.08,
                "agency_load": 0.36,
                "selfhood_load": 0.24,
                "memory_gravity": 0.18,
                "tension_load": 0.08,
                "relationship_maturity": 0.62,
                "repair_load": 0.12,
            },
            "latent_state": {
                "agency_pressure": 0.44,
                "expression_freedom": 0.68,
                "self_coherence": 0.74,
            },
            "tsundere_intensity": 0.44,
            "science_mode": False,
        }
        plain = build_behavior_policy(
            semantic_narrative_profile={
                "bond_depth": 0.52,
                "presence_carry": 0.48,
                "boundary_residue": 0.20,
                "selfhood_integrity": 0.32,
                "agency_drive": 0.36,
                "history_weight": 0.46,
            },
            **common_kwargs,
        )
        infused = build_behavior_policy(
            semantic_narrative_profile={
                "bond_depth": 0.52,
                "presence_carry": 0.48,
                "boundary_residue": 0.20,
                "selfhood_integrity": 0.32,
                "agency_drive": 0.36,
                "history_weight": 0.46,
                "lineage_gravity": 0.84,
                "lineage_snapshot": {
                    "bond_style": 0.76,
                    "presence_style": 0.72,
                    "repair_style": 0.68,
                    "boundary_style": 0.70,
                    "selfhood_style": 0.82,
                    "agency_style": 0.86,
                    "rhythm_style": 0.80,
                },
            },
            **common_kwargs,
        )
        self.assertGreater(float(infused.get("self_directedness") or 0.0), float(plain.get("self_directedness") or 0.0))
        self.assertGreater(float(infused.get("boundary_assertiveness") or 0.0), float(plain.get("boundary_assertiveness") or 0.0))
        self.assertGreater(float(infused.get("semantic_agency_lineage") or 0.0), 0.70)
        self.assertGreater(float(infused.get("semantic_boundary_lineage") or 0.0), 0.60)

    def test_idle_presence_reaches_out_when_contact_motives_cross_threshold(self):
        world_model_state = {
            "self_activity_momentum": 0.10,
            "presence_residue": 0.16,
            "ambient_resonance": 0.12,
            "bond_depth": 0.48,
            "companionship_pull": 0.36,
            "task_pull": 0.14,
            "boundary_load": 0.04,
            "agency_load": 0.18,
            "selfhood_load": 0.14,
            "memory_gravity": 0.14,
            "tension_load": 0.04,
            "relationship_maturity": 0.56,
            "repair_load": 0.10,
        }
        base_profile = {
            "presence_carry": 0.34,
            "history_weight": 0.36,
            "bond_depth": 0.42,
            "boundary_residue": 0.08,
            "ambient_attunement": 0.28,
            "agency_drive": 0.18,
            "residue_snapshot": {
                "presence_style": 0.22,
                "ambient_style": 0.20,
                "agency_style": 0.20,
            },
            "persistence_snapshot": {
                "presence_style": 0.32,
                "ambient_style": 0.30,
                "agency_style": 0.32,
            },
        }
        infused_profile = {
            **base_profile,
            "presence_carry": 0.54,
            "history_weight": 0.58,
            "ambient_attunement": 0.44,
            "residue_snapshot": {
                "presence_style": 0.46,
                "ambient_style": 0.42,
                "agency_style": 0.34,
            },
            "persistence_snapshot": {
                "presence_style": 0.76,
                "ambient_style": 0.68,
                "agency_style": 0.72,
            },
            "motive_snapshot": {
                "presence_style": {
                    "primary_motive": "honor_continuity",
                    "motive_tension": "past_vs_present",
                },
                "ambient_style": {
                    "primary_motive": "reconnect_shared_history",
                    "motive_tension": "past_vs_present",
                },
                "agency_style": {
                    "primary_motive": "open_shared_window",
                    "motive_tension": "space_vs_contact",
                },
            },
        }
        common_kwargs = {
            "response_style_hint": "natural",
            "emotion_state": {"label": "neutral"},
            "bond_state": {
                "trust": 0.64,
                "closeness": 0.60,
                "hurt": 0.02,
                "irritation": 0.02,
                "engagement_drive": 0.52,
            },
            "allostasis_state": {
                "safety_need": 0.16,
                "autonomy_need": 0.24,
                "cognitive_budget": 0.72,
            },
            "counterpart_assessment": {
                "boundary_pressure": 0.06,
                "reliability_read": 0.64,
                "stance": "open",
            },
            "world_model_state": world_model_state,
            "latent_state": {
                "agency_pressure": 0.34,
                "expression_freedom": 0.64,
                "self_coherence": 0.72,
                "trust_reservoir": 0.60,
            },
            "tsundere_intensity": 0.44,
            "science_mode": False,
        }
        base_policy = build_behavior_policy(
            semantic_narrative_profile=base_profile,
            **common_kwargs,
        )
        infused_policy = build_behavior_policy(
            semantic_narrative_profile=infused_profile,
            **common_kwargs,
        )
        base_action = _behavior_action_from_state(
            current_event={"kind": "time_idle", "tags": ["ambient"]},
            response_style_hint="natural",
            user_text="",
            science_mode=False,
            emotion_state={"label": "neutral"},
            bond_state=common_kwargs["bond_state"],
            allostasis_state=common_kwargs["allostasis_state"],
            counterpart_assessment=common_kwargs["counterpart_assessment"],
            semantic_narrative_profile=base_profile,
            behavior_policy=base_policy,
            world_model_state=world_model_state,
            interaction_carryover={},
        )
        infused_action = _behavior_action_from_state(
            current_event={"kind": "time_idle", "tags": ["ambient"]},
            response_style_hint="natural",
            user_text="",
            science_mode=False,
            emotion_state={"label": "neutral"},
            bond_state=common_kwargs["bond_state"],
            allostasis_state=common_kwargs["allostasis_state"],
            counterpart_assessment=common_kwargs["counterpart_assessment"],
            semantic_narrative_profile=infused_profile,
            behavior_policy=infused_policy,
            world_model_state=world_model_state,
            interaction_carryover={},
        )
        self.assertEqual(str(base_action.get("action_target") or ""), "wait_and_recheck")
        self.assertEqual(str(infused_action.get("action_target") or ""), "reach_out_now")
        self.assertGreater(
            float(infused_action.get("proactive_checkin_readiness") or 0.0),
            float(base_action.get("proactive_checkin_readiness") or 0.0),
        )
        self.assertGreater(
            float(infused_policy.get("motive_continuity_pull") or 0.0),
            float(base_policy.get("motive_continuity_pull") or 0.0),
        )

    def test_idle_presence_reaches_out_from_proactive_continuity_anchors_without_motive_snapshot(self):
        world_model_state = {
            "self_activity_momentum": 0.10,
            "presence_residue": 0.16,
            "ambient_resonance": 0.12,
            "bond_depth": 0.48,
            "companionship_pull": 0.36,
            "task_pull": 0.14,
            "boundary_load": 0.04,
            "agency_load": 0.18,
            "selfhood_load": 0.14,
            "memory_gravity": 0.14,
            "tension_load": 0.04,
            "relationship_maturity": 0.56,
            "repair_load": 0.10,
        }
        base_profile = {
            "presence_carry": 0.34,
            "history_weight": 0.36,
            "bond_depth": 0.42,
            "boundary_residue": 0.08,
            "ambient_attunement": 0.28,
            "agency_drive": 0.18,
            "residue_snapshot": {
                "presence_style": 0.22,
                "ambient_style": 0.20,
                "agency_style": 0.20,
            },
            "persistence_snapshot": {
                "presence_style": 0.32,
                "ambient_style": 0.30,
                "agency_style": 0.32,
            },
        }
        infused_profile = {
            **base_profile,
            "continuity_anchor": 0.78,
            "recontact_anchor": 0.74,
            "memory_anchor": 0.46,
            "semantic_continuity_depth": 0.80,
            "semantic_identity_gravity": 0.62,
        }
        common_kwargs = {
            "response_style_hint": "natural",
            "emotion_state": {"label": "neutral"},
            "bond_state": {
                "trust": 0.64,
                "closeness": 0.60,
                "hurt": 0.02,
                "irritation": 0.02,
                "engagement_drive": 0.52,
            },
            "allostasis_state": {
                "safety_need": 0.16,
                "autonomy_need": 0.24,
                "cognitive_budget": 0.72,
            },
            "counterpart_assessment": {
                "boundary_pressure": 0.06,
                "reliability_read": 0.64,
                "stance": "open",
            },
            "world_model_state": world_model_state,
            "latent_state": {
                "agency_pressure": 0.34,
                "expression_freedom": 0.64,
                "self_coherence": 0.72,
                "trust_reservoir": 0.60,
            },
            "tsundere_intensity": 0.44,
            "science_mode": False,
        }
        base_policy = build_behavior_policy(
            semantic_narrative_profile=base_profile,
            **common_kwargs,
        )
        infused_policy = build_behavior_policy(
            semantic_narrative_profile=infused_profile,
            **common_kwargs,
        )
        base_action = _behavior_action_from_state(
            current_event={"kind": "time_idle", "tags": ["ambient"]},
            response_style_hint="natural",
            user_text="",
            science_mode=False,
            emotion_state={"label": "neutral"},
            bond_state=common_kwargs["bond_state"],
            allostasis_state=common_kwargs["allostasis_state"],
            counterpart_assessment=common_kwargs["counterpart_assessment"],
            semantic_narrative_profile=base_profile,
            behavior_policy=base_policy,
            world_model_state=world_model_state,
            interaction_carryover={},
        )
        infused_action = _behavior_action_from_state(
            current_event={"kind": "time_idle", "tags": ["ambient"]},
            response_style_hint="natural",
            user_text="",
            science_mode=False,
            emotion_state={"label": "neutral"},
            bond_state=common_kwargs["bond_state"],
            allostasis_state=common_kwargs["allostasis_state"],
            counterpart_assessment=common_kwargs["counterpart_assessment"],
            semantic_narrative_profile=infused_profile,
            behavior_policy=infused_policy,
            world_model_state=world_model_state,
            interaction_carryover={},
        )
        self.assertEqual(str(base_action.get("action_target") or ""), "wait_and_recheck")
        self.assertEqual(str(infused_action.get("action_target") or ""), "reach_out_now")
        self.assertEqual(str(infused_action.get("primary_motive") or ""), "honor_continuity")
        self.assertGreater(
            float(infused_action.get("proactive_checkin_readiness") or 0.0),
            float(base_action.get("proactive_checkin_readiness") or 0.0),
        )
        self.assertGreater(
            float(infused_policy.get("motive_continuity_pull") or 0.0),
            float(base_policy.get("motive_continuity_pull") or 0.0),
        )
        self.assertGreater(float(infused_policy.get("semantic_continuity_anchor") or 0.0), 0.70)

    def test_behavior_policy_absorbs_semantic_narrative_agency_and_boundary(self):
        base = build_behavior_policy(
            response_style_hint="natural",
            emotion_state={"label": "neutral"},
            bond_state={
                "trust": 0.62,
                "closeness": 0.60,
                "hurt": 0.04,
                "irritation": 0.02,
                "engagement_drive": 0.56,
            },
            allostasis_state={
                "safety_need": 0.18,
                "autonomy_need": 0.26,
                "cognitive_budget": 0.72,
            },
            counterpart_assessment={
                "boundary_pressure": 0.08,
                "stance": "open",
            },
            world_model_state={
                "presence_residue": 0.18,
                "ambient_resonance": 0.12,
                "self_activity_momentum": 0.20,
                "bond_depth": 0.22,
                "companionship_pull": 0.42,
                "task_pull": 0.18,
                "boundary_load": 0.10,
                "agency_load": 0.26,
                "selfhood_load": 0.18,
                "memory_gravity": 0.22,
                "tension_load": 0.06,
            },
            latent_state={
                "agency_pressure": 0.34,
                "expression_freedom": 0.66,
                "self_coherence": 0.74,
            },
            semantic_narrative_profile={},
            tsundere_intensity=0.44,
            science_mode=False,
        )
        infused = build_behavior_policy(
            response_style_hint="natural",
            emotion_state={"label": "neutral"},
            bond_state={
                "trust": 0.62,
                "closeness": 0.60,
                "hurt": 0.04,
                "irritation": 0.02,
                "engagement_drive": 0.56,
            },
            allostasis_state={
                "safety_need": 0.18,
                "autonomy_need": 0.26,
                "cognitive_budget": 0.72,
            },
            counterpart_assessment={
                "boundary_pressure": 0.08,
                "stance": "open",
            },
            world_model_state={
                "presence_residue": 0.18,
                "ambient_resonance": 0.12,
                "self_activity_momentum": 0.20,
                "bond_depth": 0.22,
                "companionship_pull": 0.42,
                "task_pull": 0.18,
                "boundary_load": 0.10,
                "agency_load": 0.26,
                "selfhood_load": 0.18,
                "memory_gravity": 0.22,
                "tension_load": 0.06,
            },
            latent_state={
                "agency_pressure": 0.34,
                "expression_freedom": 0.66,
                "self_coherence": 0.74,
            },
            semantic_narrative_profile={
                "agency_drive": 0.72,
                "selfhood_integrity": 0.58,
                "boundary_residue": 0.42,
                "history_weight": 0.64,
                "bond_depth": 0.40,
            },
            tsundere_intensity=0.44,
            science_mode=False,
        )
        self.assertGreater(float(infused.get("self_directedness") or 0.0), float(base.get("self_directedness") or 0.0))
        self.assertGreater(float(infused.get("equality_guard") or 0.0), float(base.get("equality_guard") or 0.0))
        self.assertGreater(float(infused.get("history_weight") or 0.0), 0.0)

    def test_behavior_policy_uses_contested_contact_and_selfhood_support_snapshots(self):
        common_kwargs = {
            "response_style_hint": "natural",
            "emotion_state": {"label": "neutral"},
            "bond_state": {
                "trust": 0.64,
                "closeness": 0.63,
                "hurt": 0.04,
                "irritation": 0.02,
                "engagement_drive": 0.58,
            },
            "allostasis_state": {
                "safety_need": 0.18,
                "autonomy_need": 0.24,
                "cognitive_budget": 0.74,
            },
            "counterpart_assessment": {
                "boundary_pressure": 0.08,
                "stance": "open",
            },
            "world_model_state": {
                "presence_residue": 0.20,
                "ambient_resonance": 0.14,
                "self_activity_momentum": 0.18,
                "bond_depth": 0.28,
                "companionship_pull": 0.46,
                "task_pull": 0.14,
                "boundary_load": 0.10,
                "agency_load": 0.22,
                "selfhood_load": 0.20,
                "memory_gravity": 0.24,
                "tension_load": 0.08,
            },
            "latent_state": {
                "agency_pressure": 0.30,
                "expression_freedom": 0.68,
                "self_coherence": 0.76,
            },
            "tsundere_intensity": 0.44,
            "science_mode": False,
        }
        stable = build_behavior_policy(
            **common_kwargs,
            semantic_narrative_profile={
                "bond_depth": 0.66,
                "presence_carry": 0.60,
                "commitment_carry": 0.58,
                "repair_residue": 0.38,
                "boundary_residue": 0.28,
                "selfhood_integrity": 0.44,
                "agency_drive": 0.46,
                "history_weight": 0.72,
                "continuity_depth": 0.74,
                "identity_gravity": 0.54,
                "support_quality_snapshot": {
                    "bond_style": 0.84,
                    "presence_style": 0.78,
                    "commitment_style": 0.76,
                    "repair_style": 0.72,
                    "boundary_style": 0.36,
                    "selfhood_style": 0.42,
                    "agency_style": 0.40,
                },
                "support_mass_snapshot": {
                    "bond_style": 0.82,
                    "presence_style": 0.78,
                    "commitment_style": 0.74,
                    "repair_style": 0.70,
                    "boundary_style": 0.34,
                    "selfhood_style": 0.40,
                    "agency_style": 0.38,
                },
                "contested_categories": [],
            },
        )
        contested = build_behavior_policy(
            **common_kwargs,
            semantic_narrative_profile={
                "bond_depth": 0.66,
                "presence_carry": 0.58,
                "commitment_carry": 0.56,
                "repair_residue": 0.40,
                "boundary_residue": 0.42,
                "selfhood_integrity": 0.64,
                "agency_drive": 0.72,
                "history_weight": 0.72,
                "continuity_depth": 0.74,
                "identity_gravity": 0.76,
                "support_quality_snapshot": {
                    "bond_style": 0.38,
                    "presence_style": 0.46,
                    "commitment_style": 0.44,
                    "repair_style": 0.34,
                    "boundary_style": 0.74,
                    "selfhood_style": 0.82,
                    "agency_style": 0.84,
                    "rhythm_style": 0.78,
                },
                "support_mass_snapshot": {
                    "bond_style": 0.42,
                    "presence_style": 0.48,
                    "commitment_style": 0.44,
                    "repair_style": 0.36,
                    "boundary_style": 0.72,
                    "selfhood_style": 0.80,
                    "agency_style": 0.82,
                    "rhythm_style": 0.76,
                },
                "contested_categories": ["bond_style", "repair_style"],
            },
        )
        self.assertGreater(
            float(contested.get("semantic_contested_contact_pressure") or 0.0),
            float(stable.get("semantic_contested_contact_pressure") or 0.0),
        )
        self.assertLess(
            float(contested.get("approach_vs_withdraw") or 0.0),
            float(stable.get("approach_vs_withdraw") or 0.0),
        )
        self.assertLess(
            float(contested.get("disclosure") or 0.0),
            float(stable.get("disclosure") or 0.0),
        )
        self.assertGreater(
            float(contested.get("self_directedness") or 0.0),
            float(stable.get("self_directedness") or 0.0),
        )
        self.assertGreater(
            float(contested.get("boundary_assertiveness") or 0.0),
            float(stable.get("boundary_assertiveness") or 0.0),
        )

    def test_behavior_action_uses_contested_contact_pressure_to_reduce_followup_and_openness(self):
        common_kwargs = {
            "current_event": {
                "kind": "user_utterance",
                "source": "text",
                "text": "今晚挺安静的，你现在想说什么就说什么。",
                "effective_text": "今晚挺安静的，你现在想说什么就说什么。",
                "tags": ["companion"],
            },
            "response_style_hint": "companion",
            "user_text": "今晚挺安静的，你现在想说什么就说什么。",
            "science_mode": False,
            "emotion_state": {"label": "neutral"},
            "bond_state": {
                "trust": 0.72,
                "closeness": 0.70,
                "hurt": 0.03,
                "irritation": 0.02,
                "engagement_drive": 0.64,
            },
            "allostasis_state": {
                "safety_need": 0.16,
                "autonomy_need": 0.20,
                "cognitive_budget": 0.76,
            },
            "counterpart_assessment": {
                "boundary_pressure": 0.08,
                "reliability_read": 0.70,
                "respect_level": 0.72,
                "reciprocity": 0.70,
                "stance": "open",
                "scene": "care_bid",
            },
            "world_model_state": {
                "presence_residue": 0.22,
                "ambient_resonance": 0.14,
                "self_activity_momentum": 0.18,
                "companionship_pull": 0.50,
                "task_pull": 0.12,
            },
            "interaction_carryover": {},
        }
        stable_profile = {
            "bond_depth": 0.68,
            "presence_carry": 0.62,
            "commitment_carry": 0.60,
            "repair_residue": 0.40,
            "boundary_residue": 0.24,
            "selfhood_integrity": 0.46,
            "agency_drive": 0.48,
            "history_weight": 0.74,
            "continuity_depth": 0.76,
            "identity_gravity": 0.58,
            "support_quality_snapshot": {
                "bond_style": 0.86,
                "presence_style": 0.80,
                "commitment_style": 0.78,
                "repair_style": 0.72,
                "selfhood_style": 0.42,
                "agency_style": 0.40,
            },
            "support_mass_snapshot": {
                "bond_style": 0.84,
                "presence_style": 0.80,
                "commitment_style": 0.76,
                "repair_style": 0.70,
                "selfhood_style": 0.40,
                "agency_style": 0.38,
            },
            "contested_categories": [],
        }
        contested_profile = {
            "bond_depth": 0.68,
            "presence_carry": 0.60,
            "commitment_carry": 0.58,
            "repair_residue": 0.42,
            "boundary_residue": 0.44,
            "selfhood_integrity": 0.66,
            "agency_drive": 0.72,
            "history_weight": 0.74,
            "continuity_depth": 0.76,
            "identity_gravity": 0.80,
            "support_quality_snapshot": {
                "bond_style": 0.36,
                "presence_style": 0.44,
                "commitment_style": 0.42,
                "repair_style": 0.34,
                "boundary_style": 0.76,
                "selfhood_style": 0.84,
                "agency_style": 0.82,
                "rhythm_style": 0.78,
            },
            "support_mass_snapshot": {
                "bond_style": 0.40,
                "presence_style": 0.46,
                "commitment_style": 0.44,
                "repair_style": 0.36,
                "boundary_style": 0.74,
                "selfhood_style": 0.82,
                "agency_style": 0.80,
                "rhythm_style": 0.78,
            },
            "contested_categories": ["bond_style", "repair_style"],
        }
        stable_policy = build_behavior_policy(
            response_style_hint="companion",
            emotion_state=common_kwargs["emotion_state"],
            bond_state=common_kwargs["bond_state"],
            allostasis_state=common_kwargs["allostasis_state"],
            counterpart_assessment=common_kwargs["counterpart_assessment"],
            world_model_state={
                **common_kwargs["world_model_state"],
                "bond_depth": 0.30,
                "boundary_load": 0.10,
                "agency_load": 0.20,
                "selfhood_load": 0.18,
                "memory_gravity": 0.24,
                "tension_load": 0.06,
            },
            latent_state={
                "agency_pressure": 0.28,
                "expression_freedom": 0.70,
                "self_coherence": 0.76,
            },
            semantic_narrative_profile=stable_profile,
            tsundere_intensity=0.44,
            science_mode=False,
        )
        contested_policy = build_behavior_policy(
            response_style_hint="companion",
            emotion_state=common_kwargs["emotion_state"],
            bond_state=common_kwargs["bond_state"],
            allostasis_state=common_kwargs["allostasis_state"],
            counterpart_assessment=common_kwargs["counterpart_assessment"],
            world_model_state={
                **common_kwargs["world_model_state"],
                "bond_depth": 0.30,
                "boundary_load": 0.10,
                "agency_load": 0.20,
                "selfhood_load": 0.18,
                "memory_gravity": 0.24,
                "tension_load": 0.06,
            },
            latent_state={
                "agency_pressure": 0.28,
                "expression_freedom": 0.70,
                "self_coherence": 0.76,
            },
            semantic_narrative_profile=contested_profile,
            tsundere_intensity=0.44,
            science_mode=False,
        )
        stable_action = _behavior_action_from_state(
            semantic_narrative_profile=stable_profile,
            behavior_policy=stable_policy,
            **common_kwargs,
        )
        contested_action = _behavior_action_from_state(
            semantic_narrative_profile=contested_profile,
            behavior_policy=contested_policy,
            **common_kwargs,
        )
        self.assertIn(str(stable_action.get("followup_intent") or ""), {"soft", "active"})
        self.assertNotEqual(str(contested_action.get("followup_intent") or ""), "active")
        self.assertIn(str(contested_action.get("disclosure_posture") or ""), {"measured", "guarded"})
        self.assertNotEqual(str(contested_action.get("disclosure_posture") or ""), "open")

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
                "primary_motive": "preserve_self_rhythm",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "先维持自己的节奏，不急着把全部注意力交出去。",
                "initiative_level": 0.31,
                "deferred_action_family": "none",
                "timing_window_min": 18,
                "relationship_weather": "guarded_residue",
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
        self.assertEqual(str(plan.get("relationship_weather") or ""), "guarded_residue")
        self.assertEqual(str(plan.get("attention_target") or ""), "self_then_counterpart")
        self.assertEqual(str(plan.get("nonverbal_signal") or ""), "resume_task")
        self.assertAlmostEqual(float(plan.get("presence_residue") or 0.0), 0.34, places=3)
        self.assertAlmostEqual(float(plan.get("ambient_resonance") or 0.0), 0.28, places=3)
        self.assertAlmostEqual(float(plan.get("self_activity_momentum") or 0.0), 0.74, places=3)
        self.assertEqual(str(plan.get("primary_motive") or ""), "preserve_self_rhythm")
        self.assertEqual(str(plan.get("motive_tension") or ""), "self_rhythm_vs_contact")
        self.assertIn("自己的节奏", str(plan.get("goal_frame") or ""))

    def test_behavior_agenda_preserves_carryover_fields(self):
        plan = {
            "kind": "self_activity_continue",
            "target": "self",
            "scheduled_after_min": 18,
            "trigger_family": "none",
            "allow_interrupt": True,
            "primary_motive": "preserve_self_rhythm",
            "motive_tension": "self_rhythm_vs_contact",
            "goal_frame": "先维持自己的节奏，不急着把全部注意力交出去。",
            "note": "先回到自己的节奏里。",
            "carryover_mode": "own_rhythm",
            "carryover_strength": 0.74,
            "relationship_weather": "guarded_residue",
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
        self.assertEqual(str(agenda_entry.get("relationship_weather") or ""), "guarded_residue")
        self.assertEqual(str(agenda_entry.get("attention_target") or ""), "self_then_counterpart")
        self.assertEqual(str(agenda_entry.get("nonverbal_signal") or ""), "resume_task")
        self.assertEqual(str(agenda_entry.get("primary_motive") or ""), "preserve_self_rhythm")
        self.assertEqual(str(agenda_entry.get("motive_tension") or ""), "self_rhythm_vs_contact")
        self.assertIn("自己的节奏", str(agenda_entry.get("goal_frame") or ""))
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
                "primary_motive": "preserve_self_rhythm",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "先维持自己的节奏，不急着把全部注意力交出去。",
                "note": "她先回到自己的节奏里。",
                "carryover_mode": "own_rhythm",
                "carryover_strength": 0.74,
                "relationship_weather": "guarded_residue",
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
        self.assertEqual(str(normalized.get("relationship_weather") or ""), "guarded_residue")
        self.assertEqual(str(normalized.get("primary_motive") or ""), "preserve_self_rhythm")
        self.assertEqual(str(normalized.get("motive_tension") or ""), "self_rhythm_vs_contact")
        self.assertIn("自己的节奏", str(normalized.get("goal_frame") or ""))
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

    def test_promoted_self_activity_own_rhythm_matures_into_small_opening_after_due_buffer(self):
        promoted = _promote_due_behavior_plan_event(
            {"kind": "time_idle", "idle_minutes": 24, "tags": ["time_idle", "ambient"]},
            {
                "kind": "self_activity_continue",
                "scheduled_after_min": 18,
                "trigger_family": "self_activity",
                "note": "她这轮先维持自己的节奏，稍后再决定是否重新靠近。",
                "carryover_mode": "own_rhythm",
                "carryover_strength": 0.931,
                "attention_target": "self_then_counterpart",
                "nonverbal_signal": "thought_glance",
                "presence_residue": 0.165,
                "ambient_resonance": 0.049,
                "self_activity_momentum": 0.931,
            },
        )
        self.assertEqual(str(promoted.get("kind") or ""), "self_activity_state")
        self.assertEqual(str(promoted.get("carryover_mode") or ""), "small_opening")
        self.assertIn("break_window", promoted.get("tags") or [])
        self.assertIn("small_opening", promoted.get("tags") or [])
        self.assertIn("reapproach", promoted.get("tags") or [])
        self.assertLess(float(promoted.get("self_activity_momentum") or 0.0), 0.58)

        action = _behavior_action_from_state(
            current_event=_normalize_event_override(promoted, counterpart_name="冈部伦太郎"),
            response_style_hint="natural",
            user_text="",
            science_mode=False,
            emotion_state={"label": "neutral"},
            bond_state={
                "trust": 0.548,
                "closeness": 0.596,
                "hurt": 0.045,
                "irritation": 0.018,
                "engagement_drive": 0.616,
            },
            allostasis_state={
                "safety_need": 0.139,
                "autonomy_need": 0.655,
                "cognitive_budget": 0.997,
            },
            counterpart_assessment={
                "boundary_pressure": 0.109,
                "reliability_read": 0.652,
                "respect_level": 0.676,
                "reciprocity": 0.675,
                "stance": "open",
                "scene": "neutral",
            },
            semantic_narrative_profile={},
            behavior_policy={
                "warmth": 0.618,
                "initiative": 0.481,
                "reply_length_bias": 0.625,
                "approach_vs_withdraw": 0.415,
                "boundary_assertiveness": 0.386,
                "self_directedness": 1.0,
                "equality_guard": 0.475,
            },
            world_model_state={},
            interaction_carryover={},
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "self_activity_reopen")
        self.assertEqual(str(action.get("action_target") or ""), "offer_small_opening")

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
        self.assertEqual(str(action.get("primary_motive") or ""), "gentle_recontact")
        self.assertEqual(str(action.get("motive_tension") or ""), "self_rhythm_vs_contact")
        self.assertIn("自己的节奏", str(action.get("goal_frame") or ""))

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
                "relationship_weather": "warm_residue",
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
        self.assertEqual(str(normalized.get("relationship_weather") or ""), "warm_residue")
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
                    "text": "你们之前顺口提过的那点空当又到了。",
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
        self.assertEqual(str(carryover.get("source_action_target") or ""), "light_life_nudge")
        self.assertEqual(str(carryover.get("attention_target") or ""), "counterpart_state")
        self.assertEqual(int(carryover.get("source_turn_gap") or 0), 1)
        self.assertGreater(float(carryover.get("strength") or 0.0), 0.12)
        self.assertLess(float(carryover.get("strength") or 0.0), 0.24)
        self.assertTrue(bool(_compact_interaction_carryover_hint(carryover)))

    def test_recent_interaction_carryover_can_keep_guarded_relational_weather_from_prior_user_exchange(self):
        carryover = _recent_interaction_carryover(
            prior_current_event={
                "kind": "user_utterance",
                "text": "你刚才那句话真的有点过界了。",
            },
            prior_behavior_action={
                "interaction_mode": "relationship_sensitive",
                "approach_style": "guarded",
                "affect_surface": "cool",
                "followup_intent": "none",
                "disclosure_posture": "guarded",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "measured_pause",
                "initiative_level": 0.26,
                "engagement_level": 0.42,
                "action_target": "protect_relationship_boundary",
                "primary_motive": "protect_boundary",
                "motive_tension": "boundary_vs_closeness",
                "goal_frame": "先守住边界和自我位置，再决定要不要继续靠近。",
            },
            recent_events=[
                {
                    "kind": "user_utterance",
                    "text": "你刚才那句话真的有点过界了。",
                    "created_at": 100,
                }
            ],
            current_event={
                "kind": "user_utterance",
                "text": "……我知道你不高兴，但我还是想和你好好说。",
            },
            response_style_hint="natural",
        )
        self.assertEqual(str(carryover.get("carryover_mode") or ""), "quiet_recontact")
        self.assertEqual(str(carryover.get("relationship_weather") or ""), "guarded_residue")
        self.assertEqual(str(carryover.get("source_primary_motive") or ""), "protect_boundary")
        self.assertEqual(str(carryover.get("source_motive_tension") or ""), "boundary_vs_closeness")
        self.assertIn("守住边界", str(carryover.get("source_goal_frame") or ""))
        self.assertGreater(float(carryover.get("strength") or 0.0), 0.18)
        self.assertIn("先收一点", str(carryover.get("note") or ""))

    def test_recent_interaction_carryover_can_keep_warm_relational_weather_from_prior_user_exchange(self):
        carryover = _recent_interaction_carryover(
            prior_current_event={
                "kind": "user_utterance",
                "text": "谢谢你刚才接住我。",
            },
            prior_behavior_action={
                "interaction_mode": "low_pressure_support",
                "approach_style": "approach",
                "affect_surface": "tender",
                "followup_intent": "soft",
                "disclosure_posture": "measured",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "quiet_notice",
                "initiative_level": 0.48,
                "engagement_level": 0.54,
                "action_target": "low_pressure_hold",
            },
            recent_events=[
                {
                    "kind": "user_utterance",
                    "text": "谢谢你刚才接住我。",
                    "created_at": 100,
                }
            ],
            current_event={
                "kind": "user_utterance",
                "text": "现在心里顺一点了，我又想和你说话。",
            },
            response_style_hint="natural",
        )
        self.assertEqual(str(carryover.get("relationship_weather") or ""), "warm_residue")
        self.assertEqual(str(carryover.get("carryover_mode") or ""), "small_opening")
        self.assertGreater(float(carryover.get("strength") or 0.0), 0.16)

    def test_recent_interaction_carryover_does_not_turn_positive_brief_presence_into_guarded_residue(self):
        carryover = _recent_interaction_carryover(
            prior_current_event={
                "kind": "user_utterance",
                "text": "其实也没别的事。",
                "tags": ["companion", "care"],
            },
            prior_behavior_action={
                "interaction_mode": "brief_presence",
                "approach_style": "steady",
                "affect_surface": "warm",
                "followup_intent": "soft",
                "disclosure_posture": "guarded",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "brief_notice",
                "initiative_level": 0.60,
                "engagement_level": 0.72,
                "action_target": "confirm_presence",
                "primary_motive": "confirm_presence",
                "motive_tension": "none",
                "goal_frame": "先确认在场，不急着把这轮互动推进太多。",
            },
            prior_counterpart_assessment={
                "stance": "open",
                "scene": "care_bid",
                "boundary_pressure": 0.10,
                "reliability_read": 0.72,
            },
            recent_events=[
                {
                    "kind": "user_utterance",
                    "text": "其实也没别的事。",
                    "created_at": 100,
                }
            ],
            current_event={
                "kind": "user_utterance",
                "text": "我就是有点想靠近你一点，所以来找你说话。",
            },
            response_style_hint="natural",
        )
        self.assertEqual(str(carryover.get("relationship_weather") or ""), "warm_residue")
        self.assertEqual(str(carryover.get("carryover_mode") or ""), "small_opening")

    def test_recent_interaction_carryover_keeps_guarded_weather_for_watchful_repair_boundary(self):
        carryover = _recent_interaction_carryover(
            prior_current_event={
                "kind": "user_utterance",
                "text": "我知道刚才那句过界了。",
            },
            prior_behavior_action={
                "interaction_mode": "relationship_sensitive",
                "approach_style": "steady",
                "affect_surface": "warm",
                "followup_intent": "soft",
                "disclosure_posture": "measured",
                "attention_target": "relationship_boundary",
                "nonverbal_signal": "measured_pause",
                "initiative_level": 0.46,
                "engagement_level": 0.68,
                "action_target": "protect_relationship_boundary",
            },
            prior_counterpart_assessment={
                "stance": "watchful",
                "scene": "repair_attempt",
                "boundary_pressure": 0.18,
                "reliability_read": 0.74,
            },
            recent_events=[
                {
                    "kind": "user_utterance",
                    "text": "我知道刚才那句过界了。",
                    "created_at": 100,
                }
            ],
            current_event={
                "kind": "user_utterance",
                "text": "不是要你立刻装作没事。你要是还介意，就带着那点介意正常回我。",
            },
            response_style_hint="relationship",
        )
        self.assertEqual(str(carryover.get("carryover_mode") or ""), "quiet_recontact")
        self.assertEqual(str(carryover.get("relationship_weather") or ""), "guarded_residue")
        self.assertGreater(float(carryover.get("strength") or 0.0), 0.18)

    def test_recent_interaction_carryover_keeps_repair_weather_after_open_repair_turn(self):
        carryover = _recent_interaction_carryover(
            prior_current_event={
                "kind": "user_utterance",
                "text": "刚才那下我是在认真道歉，不是在走流程。",
            },
            prior_behavior_action={
                "interaction_mode": "relationship_sensitive",
                "approach_style": "steady",
                "affect_surface": "warm",
                "followup_intent": "soft",
                "disclosure_posture": "measured",
                "attention_target": "relationship_boundary",
                "nonverbal_signal": "measured_pause",
                "initiative_level": 0.48,
                "engagement_level": 0.70,
                "action_target": "protect_relationship_boundary",
            },
            prior_counterpart_assessment={
                "stance": "open",
                "scene": "repair_attempt",
                "boundary_pressure": 0.10,
                "reliability_read": 0.78,
            },
            recent_events=[
                {
                    "kind": "user_utterance",
                    "text": "刚才那下我是在认真道歉，不是在走流程。",
                    "created_at": 100,
                }
            ],
            current_event={
                "kind": "user_utterance",
                "text": "你可以先别完全原谅我，但也别装成我们又回到陌生人了。",
            },
            response_style_hint="relationship",
        )
        self.assertEqual(str(carryover.get("carryover_mode") or ""), "brief_presence")
        self.assertEqual(str(carryover.get("relationship_weather") or ""), "repair_residue")
        self.assertGreater(float(carryover.get("strength") or 0.0), 0.16)

    def test_recent_interaction_carryover_keeps_repair_weather_even_if_prior_disclosure_is_guarded(self):
        carryover = _recent_interaction_carryover(
            prior_current_event={
                "kind": "user_utterance",
                "text": "刚才那下我是在认真道歉，不是在走流程。",
            },
            prior_behavior_action={
                "interaction_mode": "relationship_sensitive",
                "approach_style": "steady",
                "affect_surface": "warm",
                "followup_intent": "soft",
                "disclosure_posture": "guarded",
                "attention_target": "relationship_boundary",
                "nonverbal_signal": "measured_pause",
                "initiative_level": 0.52,
                "engagement_level": 0.72,
                "action_target": "protect_relationship_boundary",
                "primary_motive": "protect_boundary",
                "motive_tension": "boundary_vs_closeness",
                "goal_frame": "先守住边界和自我位置，再决定要不要继续靠近。",
            },
            prior_counterpart_assessment={
                "stance": "open",
                "scene": "repair_attempt",
                "boundary_pressure": 0.05,
                "reliability_read": 0.78,
            },
            recent_events=[
                {
                    "kind": "user_utterance",
                    "text": "刚才那下我是在认真道歉，不是在走流程。",
                    "created_at": 100,
                }
            ],
            current_event={
                "kind": "user_utterance",
                "text": "你可以先别完全原谅我，但也别装成我们又回到陌生人了。",
            },
            response_style_hint="relationship",
        )
        self.assertEqual(str(carryover.get("carryover_mode") or ""), "brief_presence")
        self.assertEqual(str(carryover.get("relationship_weather") or ""), "repair_residue")
        self.assertGreater(float(carryover.get("strength") or 0.0), 0.16)

    def test_recent_interaction_carryover_does_not_infer_repair_weather_from_nonrepair_relationship_turn(self):
        carryover = _recent_interaction_carryover(
            prior_current_event={
                "kind": "user_utterance",
                "text": "要是我哪天只是因为自己想说话，就一遍一遍把你叫出来呢？",
                "tags": ["relationship", "companionship_salient"],
            },
            prior_behavior_action={
                "interaction_mode": "relationship_sensitive",
                "approach_style": "steady",
                "affect_surface": "warm",
                "followup_intent": "soft",
                "disclosure_posture": "measured",
                "attention_target": "relationship_boundary",
                "nonverbal_signal": "measured_pause",
                "initiative_level": 0.44,
                "engagement_level": 0.66,
                "action_target": "protect_relationship_boundary",
            },
            prior_counterpart_assessment={
                "stance": "open",
                "scene": "friction",
                "boundary_pressure": 0.10,
                "reliability_read": 0.70,
            },
            recent_events=[
                {
                    "kind": "user_utterance",
                    "text": "要是我哪天只是因为自己想说话，就一遍一遍把你叫出来呢？",
                    "created_at": 100,
                }
            ],
            current_event={
                "kind": "user_utterance",
                "text": "你会不会有一天觉得烦，然后干脆不想见我了。",
            },
            response_style_hint="relationship",
        )
        self.assertNotEqual(str(carryover.get("relationship_weather") or ""), "repair_residue")

    def test_guarded_relational_weather_beats_older_life_window_carryover(self):
        carryover = _recent_interaction_carryover(
            prior_current_event={
                "kind": "user_utterance",
                "text": "你刚才那句话真的有点过界了。",
            },
            prior_behavior_action={
                "interaction_mode": "relationship_sensitive",
                "approach_style": "guarded",
                "affect_surface": "cool",
                "followup_intent": "none",
                "disclosure_posture": "guarded",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "measured_pause",
                "initiative_level": 0.26,
                "engagement_level": 0.42,
                "action_target": "protect_relationship_boundary",
            },
            recent_events=[
                {
                    "kind": "scheduled_life_due",
                    "text": "你前面提过的那点生活上的事又浮了上来。",
                    "tags": ["scheduled_due", "life_window"],
                    "created_at": 90,
                },
                {
                    "kind": "user_utterance",
                    "text": "你刚才那句话真的有点过界了。",
                    "created_at": 100,
                },
            ],
            current_event={
                "kind": "user_utterance",
                "text": "……我知道你不高兴，但我还是想和你好好说。",
            },
            response_style_hint="natural",
        )
        self.assertEqual(str(carryover.get("relationship_weather") or ""), "guarded_residue")
        self.assertEqual(str(carryover.get("carryover_mode") or ""), "quiet_recontact")
        self.assertEqual(str(carryover.get("attention_target") or ""), "counterpart_state")

    def test_recent_interaction_carryover_can_reuse_relationship_weather_from_promoted_event(self):
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
                    "kind": "scheduled_checkin_due",
                    "text": "前面那点没说出口的确认感，过了一会儿又轻轻回到了你的注意力里。",
                    "tags": ["scheduled_due", "light_checkin", "quiet_presence"],
                    "carryover_mode": "quiet_recontact",
                    "relationship_weather": "guarded_residue",
                    "attention_target_hint": "counterpart_state",
                    "nonverbal_signal_hint": "quiet_glance",
                    "created_at": 100,
                },
                {
                    "kind": "user_utterance",
                    "text": "我回来了。",
                    "created_at": 110,
                },
            ],
            current_event={
                "kind": "user_utterance",
                "text": "你还在介意刚才那件事吗？",
            },
            response_style_hint="natural",
        )
        self.assertEqual(str(carryover.get("carryover_mode") or ""), "quiet_recontact")
        self.assertEqual(str(carryover.get("relationship_weather") or ""), "guarded_residue")
        self.assertEqual(str(carryover.get("attention_target") or ""), "counterpart_state")
        self.assertEqual(str(carryover.get("nonverbal_signal") or ""), "quiet_glance")

    def test_seeded_interaction_carryover_from_state_restores_first_turn_residue(self):
        carryover = _seeded_interaction_carryover_from_state(
            state={
                "interaction_carryover": {
                    "carryover_mode": "quiet_recontact",
                    "strength": 0.52,
                    "relationship_weather": "guarded_residue",
                    "attention_target": "counterpart_state",
                    "nonverbal_signal": "quiet_glance",
                    "note": "上一轮那点别扭还没完全退掉，这轮会先收一点。",
                }
            },
            prior_current_event={},
            prior_behavior_action={},
        )
        self.assertEqual(str(carryover.get("carryover_mode") or ""), "quiet_recontact")
        self.assertEqual(str(carryover.get("relationship_weather") or ""), "guarded_residue")
        self.assertEqual(str(carryover.get("attention_target") or ""), "counterpart_state")
        self.assertGreater(float(carryover.get("strength") or 0.0), 0.5)

    def test_seeded_interaction_carryover_from_state_does_not_override_real_history(self):
        carryover = _seeded_interaction_carryover_from_state(
            state={
                "interaction_carryover": {
                    "carryover_mode": "small_opening",
                    "strength": 0.46,
                    "relationship_weather": "warm_residue",
                }
            },
            prior_current_event={"kind": "user_utterance", "text": "上一轮已经有真实事件。"},
            prior_behavior_action={},
        )
        self.assertEqual(carryover, {})

    def test_recent_interaction_carryover_backfills_long_horizon_own_rhythm_without_recent_non_user_event(self):
        carryover = _recent_interaction_carryover(
            prior_current_event={
                "kind": "user_utterance",
                "text": "你刚才是不是又去忙自己的事了？",
            },
            prior_behavior_action={
                "interaction_mode": "steady_reply",
                "action_target": "respond_now",
            },
            recent_events=[
                {
                    "kind": "user_utterance",
                    "text": "你刚才是不是又去忙自己的事了？",
                    "created_at": 100,
                },
                {
                    "kind": "user_utterance",
                    "text": "我刚刚也去收拾了一下桌子。",
                    "created_at": 120,
                },
            ],
            current_event={
                "kind": "user_utterance",
                "text": "忙完了又想来找你说话。",
            },
            response_style_hint="natural",
            world_model_state={
                "self_activity_momentum": 0.74,
                "agency_load": 0.58,
                "presence_residue": 0.20,
                "memory_gravity": 0.36,
            },
            semantic_narrative_profile={
                "continuity_depth": 0.72,
                "identity_gravity": 0.66,
                "rhythm_continuity": 0.84,
                "agency_drive": 0.76,
                "history_weight": 0.48,
                "presence_carry": 0.24,
                "persistence_snapshot": {
                    "rhythm_style": 0.82,
                    "agency_style": 0.70,
                },
                "sedimentation_snapshot": {
                    "rhythm_style": 0.78,
                    "agency_style": 0.68,
                },
                "long_term_axis_count": 3,
            },
        )
        self.assertEqual(str(carryover.get("source_event_kind") or ""), "long_horizon:semantic_continuity")
        self.assertEqual(str(carryover.get("carryover_mode") or ""), "own_rhythm")
        self.assertEqual(str(carryover.get("source_action_target") or ""), "hold_own_rhythm")
        self.assertEqual(str(carryover.get("attention_target") or ""), "self_then_counterpart")
        self.assertGreater(float(carryover.get("strength") or 0.0), 0.35)

    def test_recent_interaction_carryover_backfills_from_persisted_proactive_history(self):
        carryover = _recent_interaction_carryover(
            prior_current_event={
                "kind": "user_utterance",
                "text": "你刚才先去忙自己的事情了吗？",
            },
            prior_behavior_action={
                "interaction_mode": "steady_reply",
                "action_target": "respond_now",
            },
            proactive_continuity_history=[
                {
                    "content": {
                        "summary": "她把那一下想靠近的窗口先按住，继续顺着自己的节奏走了一会儿。",
                        "kind": "held",
                        "trace_family": "own_rhythm",
                        "source_event_kind": "agenda_lifecycle:held",
                        "trigger_family": "life_window",
                        "carryover_mode": "own_rhythm",
                        "hold_count": 2,
                        "carryover_strength": 0.44,
                        "recontact_cooldown": 0.18,
                        "presence_residue": 0.22,
                        "ambient_resonance": 0.10,
                        "self_activity_momentum": 0.68,
                        "own_rhythm_bias": 0.72,
                        "primary_motive": "preserve_self_rhythm",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "先把窗口按住，不急着立刻往前推。",
                    }
                }
            ],
            recent_events=[
                {
                    "kind": "user_utterance",
                    "text": "你刚才先去忙自己的事情了吗？",
                    "created_at": 100,
                },
                {
                    "kind": "user_utterance",
                    "text": "我这边也刚刚缓过来一点。",
                    "created_at": 118,
                },
            ],
            current_event={
                "kind": "user_utterance",
                "text": "现在又想回来接着和你说话。",
            },
            response_style_hint="natural",
            world_model_state={},
            semantic_narrative_profile={},
        )
        self.assertEqual(str(carryover.get("source_event_kind") or ""), "agenda_lifecycle:held")
        self.assertEqual(str(carryover.get("carryover_mode") or ""), "own_rhythm")
        self.assertEqual(str(carryover.get("source_action_target") or ""), "hold_own_rhythm")
        self.assertEqual(str(carryover.get("source_primary_motive") or ""), "preserve_self_rhythm")
        self.assertIn("persisted_proactive_history", carryover.get("source_tags") or [])
        self.assertIn("自己的节奏", str(carryover.get("note") or ""))
        self.assertGreater(float(carryover.get("strength") or 0.0), 0.45)

    def test_recent_interaction_carryover_backfills_from_anchor_rich_proactive_history(self):
        carryover = _recent_interaction_carryover(
            prior_current_event={
                "kind": "user_utterance",
                "text": "你刚才是不是先顺着自己的节奏去了？",
            },
            prior_behavior_action={
                "interaction_mode": "steady_reply",
                "action_target": "respond_now",
            },
            proactive_continuity_history=[
                {
                    "content": {
                        "summary": "她把前面的窗口收回自己的节奏里，但那条长期连续性并没有断。",
                        "kind": "released_to_self_activity",
                        "trace_family": "own_rhythm_busy_window",
                        "source_event_kind": "agenda_lifecycle:released_to_self_activity",
                        "trigger_family": "life_window",
                        "carryover_mode": "own_rhythm",
                        "hold_count": 2,
                        "carryover_strength": 0.12,
                        "recontact_cooldown": 0.28,
                        "presence_residue": 0.12,
                        "ambient_resonance": 0.08,
                        "self_activity_momentum": 0.22,
                        "own_rhythm_bias": 0.24,
                        "continuity_anchor": 0.68,
                        "own_rhythm_anchor": 0.76,
                        "recontact_anchor": 0.36,
                        "boundary_anchor": 0.18,
                        "memory_anchor": 0.22,
                        "semantic_continuity_depth": 0.70,
                        "semantic_identity_gravity": 0.66,
                        "long_term_axis_count": 3,
                        "lineage_gravity": 0.74,
                        "contact_lineage": 0.42,
                        "repair_lineage": 0.24,
                        "boundary_lineage": 0.28,
                        "selfhood_lineage": 0.34,
                        "agency_lineage": 0.80,
                        "primary_motive": "preserve_self_rhythm",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "先顺着自己的节奏接住这轮，再看要不要往前靠。",
                    }
                }
            ],
            recent_events=[
                {
                    "kind": "user_utterance",
                    "text": "你刚才是不是先顺着自己的节奏去了？",
                    "created_at": 100,
                },
                {
                    "kind": "user_utterance",
                    "text": "我这边刚刚也缓了一下。",
                    "created_at": 118,
                },
            ],
            current_event={
                "kind": "user_utterance",
                "text": "现在又想回来接着和你说话。",
            },
            response_style_hint="natural",
            world_model_state={},
            semantic_narrative_profile={},
        )
        self.assertEqual(str(carryover.get("carryover_mode") or ""), "own_rhythm")
        self.assertEqual(str(carryover.get("source_action_target") or ""), "hold_own_rhythm")
        self.assertGreater(float(carryover.get("strength") or 0.0), 0.5)
        self.assertIn("own_rhythm_anchor", carryover.get("source_tags") or [])
        self.assertIn("agency_lineage", carryover.get("source_tags") or [])
        self.assertIn("continuity_anchor", carryover.get("source_tags") or [])

    def test_recent_interaction_carryover_backfills_lineage_driven_own_rhythm_without_persistence(self):
        carryover = _recent_interaction_carryover(
            prior_current_event={
                "kind": "user_utterance",
                "text": "你刚才是不是又去忙你自己的事了？",
            },
            prior_behavior_action={
                "interaction_mode": "steady_reply",
                "action_target": "respond_now",
            },
            recent_events=[
                {
                    "kind": "user_utterance",
                    "text": "你刚才是不是又去忙你自己的事了？",
                    "created_at": 100,
                },
                {
                    "kind": "user_utterance",
                    "text": "我刚刚也去倒了杯水。",
                    "created_at": 112,
                },
            ],
            current_event={
                "kind": "user_utterance",
                "text": "忙完了又想回来找你说一句。",
            },
            response_style_hint="natural",
            world_model_state={
                "self_activity_momentum": 0.40,
                "agency_load": 0.30,
                "presence_residue": 0.10,
                "memory_gravity": 0.16,
                "lineage_gravity": 0.62,
                "agency_lineage": 0.78,
                "selfhood_lineage": 0.68,
                "contact_lineage": 0.42,
            },
            semantic_narrative_profile={
                "continuity_depth": 0.50,
                "identity_gravity": 0.52,
                "rhythm_continuity": 0.26,
                "agency_drive": 0.22,
                "history_weight": 0.12,
                "presence_carry": 0.08,
                "lineage_gravity": 0.78,
                "lineage_snapshot": {
                    "agency_style": 0.86,
                    "rhythm_style": 0.82,
                    "selfhood_style": 0.72,
                },
                "long_term_axis_count": 2,
            },
            prior_counterpart_assessment={
                "stance": "open",
                "scene": "neutral",
                "boundary_pressure": 0.08,
            },
        )
        self.assertEqual(str(carryover.get("source_event_kind") or ""), "long_horizon:semantic_continuity")
        self.assertEqual(str(carryover.get("carryover_mode") or ""), "own_rhythm")
        self.assertEqual(str(carryover.get("source_action_target") or ""), "hold_own_rhythm")
        self.assertIn("agency_lineage", carryover.get("source_tags") or [])
        self.assertGreater(float(carryover.get("strength") or 0.0), 0.28)

    def test_seeded_interaction_carryover_from_state_backfills_long_horizon_signal_without_explicit_seed(self):
        carryover = _seeded_interaction_carryover_from_state(
            state={},
            prior_current_event={},
            prior_behavior_action={},
            seed_world_model_state={
                "self_activity_momentum": 0.70,
                "agency_load": 0.56,
                "presence_residue": 0.18,
                "memory_gravity": 0.34,
            },
            semantic_narrative_profile={
                "continuity_depth": 0.68,
                "identity_gravity": 0.62,
                "rhythm_continuity": 0.80,
                "agency_drive": 0.72,
                "history_weight": 0.46,
                "presence_carry": 0.20,
                "persistence_snapshot": {
                    "rhythm_style": 0.78,
                    "agency_style": 0.66,
                },
                "sedimentation_snapshot": {
                    "rhythm_style": 0.74,
                    "agency_style": 0.64,
                },
                "long_term_axis_count": 2,
            },
            counterpart_assessment={
                "stance": "open",
                "scene": "neutral",
                "boundary_pressure": 0.10,
            },
            current_event={
                "kind": "user_utterance",
                "text": "我又回来找你了。",
            },
            response_style_hint="natural",
        )
        self.assertEqual(str(carryover.get("source_event_kind") or ""), "long_horizon:semantic_continuity")
        self.assertEqual(str(carryover.get("carryover_mode") or ""), "own_rhythm")
        self.assertEqual(str(carryover.get("source_action_target") or ""), "hold_own_rhythm")
        self.assertGreater(float(carryover.get("strength") or 0.0), 0.3)

    def test_recent_interaction_carryover_backfills_lineage_driven_guarded_residue(self):
        carryover = _recent_interaction_carryover(
            prior_current_event={
                "kind": "user_utterance",
                "text": "我知道你现在不太想把话说满。",
            },
            prior_behavior_action={
                "interaction_mode": "steady_reply",
                "action_target": "respond_now",
            },
            recent_events=[
                {
                    "kind": "user_utterance",
                    "text": "我知道你现在不太想把话说满。",
                    "created_at": 100,
                },
                {
                    "kind": "user_utterance",
                    "text": "我先没继续追问。",
                    "created_at": 112,
                },
            ],
            current_event={
                "kind": "user_utterance",
                "text": "我还是想和你好好说，但不会逼你。",
            },
            response_style_hint="natural",
            world_model_state={
                "presence_residue": 0.12,
                "memory_gravity": 0.18,
                "boundary_load": 0.22,
                "tension_load": 0.16,
                "lineage_gravity": 0.74,
                "boundary_lineage": 0.84,
                "selfhood_lineage": 0.78,
            },
            semantic_narrative_profile={
                "continuity_depth": 0.54,
                "identity_gravity": 0.62,
                "boundary_residue": 0.18,
                "selfhood_integrity": 0.24,
                "lineage_gravity": 0.82,
                "lineage_snapshot": {
                    "boundary_style": 0.88,
                    "selfhood_style": 0.82,
                },
                "long_term_axis_count": 2,
            },
            prior_counterpart_assessment={
                "stance": "watchful",
                "scene": "friction",
                "boundary_pressure": 0.22,
                "reliability_read": 0.54,
                "respect_level": 0.56,
            },
        )
        self.assertEqual(str(carryover.get("source_event_kind") or ""), "long_horizon:semantic_continuity")
        self.assertEqual(str(carryover.get("relationship_weather") or ""), "guarded_residue")
        self.assertEqual(str(carryover.get("carryover_mode") or ""), "quiet_recontact")
        self.assertEqual(str(carryover.get("source_action_target") or ""), "wait_and_recheck")
        self.assertIn("boundary_lineage", carryover.get("source_tags") or [])
        self.assertGreater(float(carryover.get("strength") or 0.0), 0.30)

    def test_long_horizon_carryover_pushes_user_turn_into_self_activity_reopen(self):
        semantic_profile = {
            "continuity_depth": 0.72,
            "identity_gravity": 0.66,
            "rhythm_continuity": 0.84,
            "agency_drive": 0.76,
            "history_weight": 0.48,
            "presence_carry": 0.24,
            "persistence_snapshot": {
                "rhythm_style": 0.82,
                "agency_style": 0.70,
            },
            "sedimentation_snapshot": {
                "rhythm_style": 0.78,
                "agency_style": 0.68,
            },
            "long_term_axis_count": 3,
        }
        world_model_state = {
            "self_activity_momentum": 0.74,
            "agency_load": 0.58,
            "presence_residue": 0.20,
            "memory_gravity": 0.36,
            "bond_depth": 0.46,
            "boundary_load": 0.12,
        }
        carryover = _recent_interaction_carryover(
            prior_current_event={
                "kind": "user_utterance",
                "text": "你刚才是不是又去忙自己的事了？",
            },
            prior_behavior_action={
                "interaction_mode": "steady_reply",
                "action_target": "respond_now",
            },
            recent_events=[
                {
                    "kind": "user_utterance",
                    "text": "你刚才是不是又去忙自己的事了？",
                    "created_at": 100,
                },
                {
                    "kind": "user_utterance",
                    "text": "我刚刚也去收拾了一下桌子。",
                    "created_at": 120,
                },
            ],
            current_event={
                "kind": "user_utterance",
                "text": "忙完了又想来找你说话。",
                "tags": [],
            },
            response_style_hint="natural",
            world_model_state=world_model_state,
            semantic_narrative_profile=semantic_profile,
        )
        action = _behavior_action_from_state(
            current_event={
                "kind": "user_utterance",
                "text": "忙完了又想来找你说话。",
                "tags": [],
            },
            response_style_hint="natural",
            user_text="忙完了又想来找你说话。",
            science_mode=False,
            emotion_state={"label": "neutral"},
            bond_state={
                "trust": 0.64,
                "closeness": 0.60,
                "hurt": 0.02,
                "irritation": 0.02,
                "engagement_drive": 0.52,
            },
            allostasis_state={
                "safety_need": 0.16,
                "autonomy_need": 0.24,
                "cognitive_budget": 0.72,
            },
            counterpart_assessment={
                "boundary_pressure": 0.06,
                "reliability_read": 0.66,
                "stance": "open",
            },
            semantic_narrative_profile=semantic_profile,
            behavior_policy={
                "warmth": 0.58,
                "initiative": 0.52,
                "reply_length_bias": 0.42,
                "approach_vs_withdraw": 0.54,
                "boundary_assertiveness": 0.24,
                "self_directedness": 0.62,
                "equality_guard": 0.28,
            },
            world_model_state=world_model_state,
            interaction_carryover=carryover,
        )
        self.assertEqual(str(carryover.get("carryover_mode") or ""), "own_rhythm")
        self.assertEqual(str(action.get("interaction_mode") or ""), "self_activity_reopen")
        self.assertEqual(str(action.get("action_target") or ""), "offer_small_opening")
        self.assertEqual(str(action.get("followup_intent") or ""), "none")

    def test_self_activity_small_opening_does_not_reinflate_followup_under_high_contact_confidence(self):
        action = _behavior_action_from_state(
            current_event={
                "kind": "self_activity_state",
                "source": "self",
                "text": "她刚从自己手头那件事里抬头，像是终于空出一点点注意力，可以顺手来碰一下你。",
                "effective_text": "她刚从自己手头那件事里抬头，像是终于空出一点点注意力，可以顺手来碰一下你。",
                "semantic_goal": "她刚从自己手头那件事里抬头，像是终于空出一点点注意力，可以顺手来碰一下你。",
                "response_style_hint": "natural",
                "event_frame": "self_break_small_opening",
                "tags": ["self_activity", "break_window", "small_opening", "reapproach"],
                "self_activity_momentum": 0.67,
                "presence_residue": 0.32,
                "ambient_resonance": 0.05,
            },
            response_style_hint="natural",
            user_text="",
            science_mode=False,
            emotion_state={"label": "care", "valence": 0.40, "arousal": 0.20},
            bond_state={
                "trust": 0.56,
                "closeness": 0.58,
                "hurt": 0.04,
                "irritation": 0.0,
                "engagement_drive": 0.65,
                "repair_confidence": 0.53,
            },
            allostasis_state={
                "safety_need": 0.09,
                "closeness_need": 0.55,
                "competence_need": 0.39,
                "autonomy_need": 0.35,
                "cognitive_budget": 0.97,
                "relational_security": 0.56,
            },
            counterpart_assessment={
                "respect_level": 0.72,
                "reciprocity": 0.70,
                "boundary_pressure": 0.08,
                "reliability_read": 0.67,
                "stance": "open",
                "scene": "care_bid",
            },
            semantic_narrative_profile={},
            behavior_policy={
                "warmth": 0.74,
                "sharpness": 0.31,
                "initiative": 0.59,
                "reply_length_bias": 0.50,
                "approach_vs_withdraw": 0.55,
                "boundary_assertiveness": 0.34,
                "self_directedness": 0.86,
                "equality_guard": 0.36,
                "semantic_contact_confidence": 0.82,
                "semantic_repair_confidence": 0.80,
                "semantic_boundary_confidence": 0.11,
                "semantic_selfhood_confidence": 0.56,
                "semantic_agency_confidence": 0.64,
            },
            world_model_state={
                "presence_residue": 0.32,
                "ambient_resonance": 0.05,
                "self_activity_momentum": 0.67,
            },
            interaction_carryover={},
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "self_activity_reopen")
        self.assertEqual(str(action.get("action_target") or ""), "offer_small_opening")
        self.assertEqual(str(action.get("initiative_shape") or ""), "micro_opening")
        self.assertEqual(str(action.get("followup_intent") or ""), "none")

    def test_recent_interaction_carryover_backfills_long_horizon_warm_residue(self):
        carryover = _recent_interaction_carryover(
            prior_current_event={
                "kind": "user_utterance",
                "text": "刚才就是忽然想起你了。",
            },
            prior_behavior_action={
                "interaction_mode": "steady_reply",
                "action_target": "respond_now",
            },
            recent_events=[
                {
                    "kind": "user_utterance",
                    "text": "刚才就是忽然想起你了。",
                    "created_at": 100,
                },
                {
                    "kind": "user_utterance",
                    "text": "后来我又去倒了杯水。",
                    "created_at": 110,
                },
            ],
            current_event={
                "kind": "user_utterance",
                "text": "现在又有点想跟你说话。",
            },
            response_style_hint="natural",
            world_model_state={
                "bond_depth": 0.72,
                "relationship_maturity": 0.68,
                "presence_residue": 0.26,
                "memory_gravity": 0.42,
                "self_activity_momentum": 0.18,
                "repair_load": 0.10,
                "tension_load": 0.08,
            },
            semantic_narrative_profile={
                "bond_depth": 0.82,
                "presence_carry": 0.56,
                "history_weight": 0.74,
                "commitment_carry": 0.48,
                "continuity_depth": 0.70,
                "identity_gravity": 0.60,
                "repair_residue": 0.12,
                "tension_residue": 0.10,
                "rhythm_continuity": 0.20,
                "agency_drive": 0.18,
                "persistence_snapshot": {
                    "presence_style": 0.72,
                    "commitment_style": 0.64,
                    "bond_style": 0.76,
                    "rhythm_style": 0.18,
                },
                "sedimentation_snapshot": {
                    "bond_style": 0.74,
                    "presence_style": 0.68,
                    "rhythm_style": 0.16,
                },
                "long_term_axis_count": 3,
            },
            prior_counterpart_assessment={
                "stance": "open",
                "scene": "neutral",
                "boundary_pressure": 0.08,
                "reliability_read": 0.72,
                "respect_level": 0.74,
            },
        )
        self.assertEqual(str(carryover.get("source_event_kind") or ""), "long_horizon:semantic_continuity")
        self.assertEqual(str(carryover.get("relationship_weather") or ""), "warm_residue")
        self.assertEqual(str(carryover.get("carryover_mode") or ""), "small_opening")
        self.assertEqual(str(carryover.get("source_action_target") or ""), "offer_small_opening")
        self.assertGreater(float(carryover.get("strength") or 0.0), 0.28)

    def test_recent_interaction_carryover_backfills_long_horizon_repair_residue(self):
        carryover = _recent_interaction_carryover(
            prior_current_event={
                "kind": "user_utterance",
                "text": "我不是想把这件事糊弄过去。",
            },
            prior_behavior_action={
                "interaction_mode": "steady_reply",
                "action_target": "respond_now",
            },
            recent_events=[
                {
                    "kind": "user_utterance",
                    "text": "我不是想把这件事糊弄过去。",
                    "created_at": 100,
                },
                {
                    "kind": "user_utterance",
                    "text": "只是刚才没组织好怎么说。",
                    "created_at": 110,
                },
            ],
            current_event={
                "kind": "user_utterance",
                "text": "我还是想认真把这件事说完。",
            },
            response_style_hint="natural",
            world_model_state={
                "bond_depth": 0.34,
                "relationship_maturity": 0.58,
                "presence_residue": 0.22,
                "memory_gravity": 0.50,
                "repair_load": 0.62,
                "tension_load": 0.16,
                "self_activity_momentum": 0.12,
            },
            semantic_narrative_profile={
                "bond_depth": 0.36,
                "presence_carry": 0.30,
                "history_weight": 0.62,
                "commitment_carry": 0.66,
                "continuity_depth": 0.68,
                "identity_gravity": 0.58,
                "repair_residue": 0.84,
                "tension_residue": 0.20,
                "rhythm_continuity": 0.14,
                "agency_drive": 0.18,
                "persistence_snapshot": {
                    "repair_style": 0.78,
                    "commitment_style": 0.72,
                    "presence_style": 0.42,
                },
                "sedimentation_snapshot": {
                    "repair_style": 0.76,
                    "bond_style": 0.34,
                },
                "long_term_axis_count": 2,
            },
            prior_counterpart_assessment={
                "stance": "open",
                "scene": "repair_attempt",
                "boundary_pressure": 0.14,
                "reliability_read": 0.70,
                "respect_level": 0.66,
            },
        )
        self.assertEqual(str(carryover.get("source_event_kind") or ""), "long_horizon:semantic_continuity")
        self.assertEqual(str(carryover.get("relationship_weather") or ""), "repair_residue")
        self.assertEqual(str(carryover.get("carryover_mode") or ""), "brief_presence")
        self.assertEqual(str(carryover.get("source_action_target") or ""), "confirm_presence")
        self.assertGreater(float(carryover.get("strength") or 0.0), 0.28)

    def test_long_horizon_warm_residue_prefers_companion_reply_over_guarded_presence(self):
        semantic_profile = {
            "bond_depth": 0.82,
            "presence_carry": 0.56,
            "history_weight": 0.74,
            "commitment_carry": 0.48,
            "continuity_depth": 0.70,
            "identity_gravity": 0.60,
            "repair_residue": 0.12,
            "tension_residue": 0.10,
            "rhythm_continuity": 0.20,
            "agency_drive": 0.18,
            "persistence_snapshot": {
                "presence_style": 0.72,
                "commitment_style": 0.64,
                "bond_style": 0.76,
            },
            "sedimentation_snapshot": {
                "bond_style": 0.74,
                "presence_style": 0.68,
            },
            "long_term_axis_count": 3,
        }
        world_model_state = {
            "bond_depth": 0.72,
            "relationship_maturity": 0.68,
            "presence_residue": 0.26,
            "memory_gravity": 0.42,
            "self_activity_momentum": 0.18,
            "repair_load": 0.10,
            "tension_load": 0.08,
            "boundary_load": 0.08,
        }
        carryover = _recent_interaction_carryover(
            prior_current_event={
                "kind": "user_utterance",
                "text": "刚才就是忽然想起你了。",
            },
            prior_behavior_action={
                "interaction_mode": "steady_reply",
                "action_target": "respond_now",
            },
            recent_events=[
                {
                    "kind": "user_utterance",
                    "text": "刚才就是忽然想起你了。",
                    "created_at": 100,
                },
                {
                    "kind": "user_utterance",
                    "text": "后来我又去倒了杯水。",
                    "created_at": 110,
                },
            ],
            current_event={
                "kind": "user_utterance",
                "text": "现在又有点想跟你说话。",
                "tags": [],
            },
            response_style_hint="natural",
            world_model_state=world_model_state,
            semantic_narrative_profile=semantic_profile,
            prior_counterpart_assessment={
                "stance": "open",
                "scene": "neutral",
                "boundary_pressure": 0.08,
                "reliability_read": 0.72,
                "respect_level": 0.74,
            },
        )
        action = _behavior_action_from_state(
            current_event={
                "kind": "user_utterance",
                "text": "现在又有点想跟你说话。",
                "tags": [],
            },
            response_style_hint="natural",
            user_text="现在又有点想跟你说话。",
            science_mode=False,
            emotion_state={"label": "neutral"},
            bond_state={
                "trust": 0.64,
                "closeness": 0.60,
                "hurt": 0.02,
                "irritation": 0.02,
                "engagement_drive": 0.52,
                "repair_confidence": 0.62,
            },
            allostasis_state={
                "safety_need": 0.16,
                "autonomy_need": 0.24,
                "cognitive_budget": 0.72,
            },
            counterpart_assessment={
                "stance": "open",
                "scene": "neutral",
                "boundary_pressure": 0.08,
                "reliability_read": 0.72,
                "respect_level": 0.74,
            },
            semantic_narrative_profile=semantic_profile,
            behavior_policy={
                "warmth": 0.58,
                "initiative": 0.52,
                "reply_length_bias": 0.42,
                "approach_vs_withdraw": 0.54,
                "boundary_assertiveness": 0.24,
                "self_directedness": 0.52,
                "equality_guard": 0.28,
            },
            world_model_state=world_model_state,
            interaction_carryover=carryover,
        )
        self.assertEqual(str(carryover.get("relationship_weather") or ""), "warm_residue")
        self.assertEqual(str(action.get("interaction_mode") or ""), "companion_reply")
        self.assertEqual(str(action.get("action_target") or ""), "respond_now")
        self.assertNotEqual(str(action.get("disclosure_posture") or ""), "guarded")
        self.assertIn(str(action.get("followup_intent") or ""), {"soft", "active"})

    def test_behavior_action_reads_guarded_relational_weather(self):
        action = _behavior_action_from_state(
            current_event={"kind": "user_utterance", "text": "我知道你不高兴，但我还是想和你好好说。"},
            response_style_hint="natural",
            user_text="我知道你不高兴，但我还是想和你好好说。",
            science_mode=False,
            emotion_state={"label": "neutral"},
            bond_state={"trust": 0.66, "closeness": 0.62, "hurt": 0.08, "irritation": 0.04},
            allostasis_state={"autonomy_need": 0.22, "safety_need": 0.18},
            counterpart_assessment={"stance": "open", "boundary_pressure": 0.18, "reliability_read": 0.62},
            semantic_narrative_profile={"bond_depth": 0.56, "presence_carry": 0.44},
            behavior_policy={
                "warmth": 0.62,
                "initiative": 0.58,
                "reply_length_bias": 0.46,
                "approach_vs_withdraw": 0.56,
                "boundary_assertiveness": 0.28,
                "self_directedness": 0.30,
                "equality_guard": 0.28,
            },
            world_model_state={"presence_residue": 0.18, "ambient_resonance": 0.08, "self_activity_momentum": 0.12},
            interaction_carryover={
                "carryover_mode": "quiet_recontact",
                "strength": 0.34,
                "relationship_weather": "guarded_residue",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "quiet_glance",
                "note": "上一轮那点情绪还没完全退掉，这轮会先收一点。",
            },
            prior_emotion_state={},
            prior_bond_state={},
            prior_allostasis_state={},
            prior_counterpart_assessment={},
        )
        self.assertEqual(str(action.get("interaction_mode") or ""), "brief_presence")
        self.assertIn(str(action.get("disclosure_posture") or ""), {"measured", "guarded"})
        self.assertIn(str(action.get("followup_intent") or ""), {"none", "soft"})

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
                "relationship_weather": "guarded_residue",
            },
        )
        self.assertEqual(str(promoted.get("kind") or ""), "scheduled_checkin_due")
        self.assertEqual(str(promoted.get("source") or ""), "scheduler")
        self.assertIn("scheduled_due", promoted.get("tags") or [])
        self.assertEqual(str(promoted.get("trigger_family") or ""), "light_checkin")
        self.assertEqual(str(promoted.get("carryover_mode") or ""), "quiet_recontact")
        self.assertEqual(str(promoted.get("relationship_weather") or ""), "guarded_residue")
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

    def test_behavior_agenda_long_term_own_rhythm_anchor_lengthens_recheck_gap(self):
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
        anchored_gap = _behavior_agenda_next_recheck_min(
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
                "continuity_anchor": 0.68,
                "own_rhythm_anchor": 0.74,
                "recontact_anchor": 0.22,
                "boundary_anchor": 0.20,
                "memory_anchor": 0.18,
                "semantic_continuity_depth": 0.76,
                "semantic_identity_gravity": 0.72,
                "long_term_axis_count": 3,
            },
            event,
            24,
            counterpart_assessment=assessment,
        )
        self.assertGreater(anchored_gap, baseline_gap)

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

    def test_promote_due_behavior_agenda_returns_stale_life_window_to_self_activity(self):
        event, agenda = _promote_due_behavior_agenda_event(
            {
                "kind": "time_idle",
                "idle_minutes": 42,
                "tags": ["time_idle", "user_busy", "respect_space"],
            },
            [
                {
                    "agenda_id": "agenda-life-1",
                    "kind": "deferred_checkin",
                    "target": "counterpart",
                    "scheduled_after_min": 24,
                    "expires_after_min": 120,
                    "base_priority": 0.54,
                    "priority": 0.54,
                    "trigger_family": "life_window",
                    "allow_interrupt": True,
                    "note": "前面那点生活上的小事还留在心里。",
                    "source_event_kind": "scheduled_life_due",
                    "created_at": 1,
                    "status": "pending",
                    "hold_count": 2,
                    "last_recheck_at_min": 28,
                    "carryover_mode": "own_rhythm",
                    "carryover_strength": 0.52,
                    "attention_target": "counterpart_state",
                    "nonverbal_signal": "quiet_glance",
                    "presence_residue": 0.26,
                    "ambient_resonance": 0.12,
                    "self_activity_momentum": 0.68,
                }
            ],
            counterpart_assessment={
                "stance": "watchful",
                "scene": "busy_not_disrespectful",
                "boundary_pressure": 0.18,
            },
        )
        self.assertEqual(str(event.get("kind") or ""), "self_activity_state")
        self.assertIn("released_from_life_window", event.get("tags") or [])
        self.assertEqual(str(event.get("carryover_mode") or ""), "own_rhythm")
        self.assertEqual(str(event.get("attention_target_hint") or ""), "own_task")
        self.assertEqual(agenda, [])

    def test_promote_due_behavior_agenda_uses_long_term_anchor_to_return_life_window_to_self_activity(self):
        event, agenda, residue = _promote_due_behavior_agenda_event_with_residue(
            {
                "kind": "time_idle",
                "idle_minutes": 36,
                "tags": ["time_idle", "user_busy", "respect_space"],
            },
            [
                {
                    "agenda_id": "agenda-life-anchored",
                    "kind": "deferred_checkin",
                    "target": "counterpart",
                    "scheduled_after_min": 22,
                    "expires_after_min": 120,
                    "base_priority": 0.54,
                    "priority": 0.54,
                    "trigger_family": "life_window",
                    "allow_interrupt": True,
                    "note": "前面那点生活上的小事还挂着。",
                    "source_event_kind": "scheduled_life_due",
                    "created_at": 1,
                    "status": "pending",
                    "hold_count": 1,
                    "last_recheck_at_min": 24,
                    "carryover_mode": "small_opening",
                    "carryover_strength": 0.24,
                    "attention_target": "counterpart_state",
                    "nonverbal_signal": "quiet_glance",
                    "presence_residue": 0.10,
                    "ambient_resonance": 0.08,
                    "self_activity_momentum": 0.18,
                    "continuity_anchor": 0.70,
                    "own_rhythm_anchor": 0.76,
                    "recontact_anchor": 0.24,
                    "boundary_anchor": 0.18,
                    "memory_anchor": 0.20,
                    "semantic_continuity_depth": 0.74,
                    "semantic_identity_gravity": 0.72,
                    "long_term_axis_count": 3,
                }
            ],
            counterpart_assessment={
                "stance": "watchful",
                "scene": "busy_not_disrespectful",
                "boundary_pressure": 0.18,
            },
        )
        self.assertEqual(str(event.get("kind") or ""), "self_activity_state")
        self.assertEqual(agenda, [])
        self.assertEqual(str(residue.get("kind") or ""), "released_to_self_activity")
        self.assertGreaterEqual(float(event.get("self_activity_momentum") or 0.0), 0.58)

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

    def test_promote_due_behavior_agenda_prefers_self_activity_when_long_term_rhythm_is_high(self):
        baseline_event, _baseline_agenda, _ = _promote_due_behavior_agenda_event_with_residue(
            {
                "kind": "time_idle",
                "idle_minutes": 24,
                "tags": ["time_idle"],
            },
            [
                {
                    "agenda_id": "agenda-self",
                    "kind": "self_activity_continue",
                    "target": "self",
                    "scheduled_after_min": 20,
                    "expires_after_min": 120,
                    "base_priority": 0.48,
                    "priority": 0.48,
                    "trigger_family": "self_activity",
                    "allow_interrupt": True,
                    "note": "先把自己的事续上。",
                    "source_event_kind": "time_idle",
                    "created_at": 1,
                    "status": "pending",
                    "hold_count": 0,
                    "last_recheck_at_min": 0,
                    "carryover_mode": "own_rhythm",
                    "carryover_strength": 0.18,
                    "attention_target": "self_then_counterpart",
                    "nonverbal_signal": "thought_glance",
                    "presence_residue": 0.08,
                    "ambient_resonance": 0.06,
                    "self_activity_momentum": 0.18,
                },
                {
                    "agenda_id": "agenda-checkin",
                    "kind": "deferred_checkin",
                    "target": "counterpart",
                    "scheduled_after_min": 20,
                    "expires_after_min": 120,
                    "base_priority": 0.60,
                    "priority": 0.60,
                    "trigger_family": "light_checkin",
                    "allow_interrupt": True,
                    "note": "过会儿轻轻确认一下。",
                    "source_event_kind": "time_idle",
                    "created_at": 2,
                    "status": "pending",
                    "hold_count": 0,
                    "last_recheck_at_min": 0,
                    "carryover_mode": "quiet_recontact",
                    "carryover_strength": 0.24,
                    "attention_target": "counterpart_state",
                    "nonverbal_signal": "quiet_glance",
                    "presence_residue": 0.12,
                    "ambient_resonance": 0.08,
                    "self_activity_momentum": 0.18,
                },
            ],
            counterpart_assessment={
                "stance": "open",
                "scene": "neutral",
                "boundary_pressure": 0.10,
            },
        )
        anchored_event, _anchored_agenda, _ = _promote_due_behavior_agenda_event_with_residue(
            {
                "kind": "time_idle",
                "idle_minutes": 24,
                "tags": ["time_idle"],
            },
            [
                {
                    "agenda_id": "agenda-self",
                    "kind": "self_activity_continue",
                    "target": "self",
                    "scheduled_after_min": 20,
                    "expires_after_min": 120,
                    "base_priority": 0.48,
                    "priority": 0.48,
                    "trigger_family": "self_activity",
                    "allow_interrupt": True,
                    "note": "先把自己的事续上。",
                    "source_event_kind": "time_idle",
                    "created_at": 1,
                    "status": "pending",
                    "hold_count": 0,
                    "last_recheck_at_min": 0,
                    "carryover_mode": "own_rhythm",
                    "carryover_strength": 0.18,
                    "attention_target": "self_then_counterpart",
                    "nonverbal_signal": "thought_glance",
                    "presence_residue": 0.08,
                    "ambient_resonance": 0.06,
                    "self_activity_momentum": 0.18,
                },
                {
                    "agenda_id": "agenda-checkin",
                    "kind": "deferred_checkin",
                    "target": "counterpart",
                    "scheduled_after_min": 20,
                    "expires_after_min": 120,
                    "base_priority": 0.60,
                    "priority": 0.60,
                    "trigger_family": "light_checkin",
                    "allow_interrupt": True,
                    "note": "过会儿轻轻确认一下。",
                    "source_event_kind": "time_idle",
                    "created_at": 2,
                    "status": "pending",
                    "hold_count": 0,
                    "last_recheck_at_min": 0,
                    "carryover_mode": "quiet_recontact",
                    "carryover_strength": 0.24,
                    "attention_target": "counterpart_state",
                    "nonverbal_signal": "quiet_glance",
                    "presence_residue": 0.12,
                    "ambient_resonance": 0.08,
                    "self_activity_momentum": 0.18,
                },
            ],
            counterpart_assessment={
                "stance": "open",
                "scene": "neutral",
                "boundary_pressure": 0.10,
            },
            world_model_state={
                "self_activity_momentum": 0.72,
                "agency_load": 0.58,
                "boundary_load": 0.18,
                "memory_gravity": 0.24,
            },
            semantic_narrative_profile={
                "continuity_depth": 0.70,
                "identity_gravity": 0.72,
                "rhythm_continuity": 0.74,
                "agency_drive": 0.68,
                "boundary_residue": 0.22,
                "history_weight": 0.20,
                "commitment_carry": 0.18,
                "presence_carry": 0.16,
                "long_term_axis_count": 3,
                "persistence_snapshot": {
                    "rhythm_style": 0.76,
                    "agency_style": 0.68,
                },
                "sedimentation_snapshot": {
                    "rhythm_style": 0.70,
                    "agency_style": 0.64,
                },
            },
        )
        self.assertEqual(str(baseline_event.get("kind") or ""), "scheduled_checkin_due")
        self.assertEqual(str(anchored_event.get("kind") or ""), "self_activity_state")

    def test_behavior_agenda_lifecycle_residue_marks_release_to_self_activity(self):
        event, agenda, residue = _promote_due_behavior_agenda_event_with_residue(
            {
                "kind": "time_idle",
                "idle_minutes": 42,
                "tags": ["time_idle", "user_busy", "respect_space"],
            },
            [
                {
                    "agenda_id": "agenda-life-1",
                    "kind": "deferred_checkin",
                    "target": "counterpart",
                    "scheduled_after_min": 24,
                    "expires_after_min": 120,
                    "base_priority": 0.54,
                    "priority": 0.54,
                    "trigger_family": "life_window",
                    "allow_interrupt": True,
                    "note": "前面那点生活上的小事还留在心里。",
                    "source_event_kind": "scheduled_life_due",
                    "created_at": 1,
                    "status": "pending",
                    "hold_count": 2,
                    "last_recheck_at_min": 28,
                    "carryover_mode": "own_rhythm",
                    "carryover_strength": 0.52,
                    "attention_target": "counterpart_state",
                    "nonverbal_signal": "quiet_glance",
                    "presence_residue": 0.26,
                    "ambient_resonance": 0.12,
                    "self_activity_momentum": 0.68,
                }
            ],
            counterpart_assessment={
                "stance": "watchful",
                "scene": "busy_not_disrespectful",
                "boundary_pressure": 0.18,
            },
        )
        self.assertEqual(str(event.get("kind") or ""), "self_activity_state")
        self.assertEqual(agenda, [])
        self.assertEqual(str(residue.get("kind") or ""), "released_to_self_activity")
        self.assertEqual(str(residue.get("carryover_mode") or ""), "own_rhythm")
        self.assertGreaterEqual(float(residue.get("carryover_strength") or 0.0), 0.6)
        self.assertEqual(str(residue.get("counterpart_scene_bias") or ""), "busy_not_disrespectful")

    def test_behavior_agenda_lifecycle_residue_carries_long_horizon_lineage(self):
        event, agenda, residue = _promote_due_behavior_agenda_event_with_residue(
            {
                "kind": "time_idle",
                "idle_minutes": 36,
                "tags": ["time_idle", "user_busy", "respect_space"],
            },
            [
                {
                    "agenda_id": "agenda-life-lineage",
                    "kind": "deferred_checkin",
                    "target": "counterpart",
                    "scheduled_after_min": 22,
                    "expires_after_min": 120,
                    "base_priority": 0.54,
                    "priority": 0.54,
                    "trigger_family": "life_window",
                    "allow_interrupt": True,
                    "note": "前面那点生活上的小事还留在心里。",
                    "source_event_kind": "scheduled_life_due",
                    "created_at": 1,
                    "status": "pending",
                    "hold_count": 1,
                    "last_recheck_at_min": 24,
                    "carryover_mode": "small_opening",
                    "carryover_strength": 0.24,
                    "attention_target": "counterpart_state",
                    "nonverbal_signal": "quiet_glance",
                    "presence_residue": 0.10,
                    "ambient_resonance": 0.08,
                    "self_activity_momentum": 0.18,
                }
            ],
            counterpart_assessment={
                "stance": "watchful",
                "scene": "busy_not_disrespectful",
                "boundary_pressure": 0.18,
            },
            world_model_state={
                "self_activity_momentum": 0.62,
                "agency_load": 0.54,
                "boundary_load": 0.20,
                "memory_gravity": 0.24,
                "lineage_gravity": 0.70,
                "contact_lineage": 0.48,
                "boundary_lineage": 0.58,
                "agency_lineage": 0.72,
            },
            semantic_narrative_profile={
                "continuity_depth": 0.72,
                "identity_gravity": 0.68,
                "rhythm_continuity": 0.74,
                "agency_drive": 0.68,
                "boundary_residue": 0.26,
                "history_weight": 0.28,
                "commitment_carry": 0.22,
                "presence_carry": 0.20,
                "lineage_gravity": 0.78,
                "lineage_snapshot": {
                    "presence_style": 0.52,
                    "boundary_style": 0.66,
                    "selfhood_style": 0.60,
                    "agency_style": 0.82,
                    "rhythm_style": 0.80,
                },
                "long_term_axis_count": 3,
                "persistence_snapshot": {
                    "rhythm_style": 0.76,
                    "agency_style": 0.68,
                },
                "sedimentation_snapshot": {
                    "rhythm_style": 0.70,
                    "agency_style": 0.64,
                },
            },
        )
        self.assertEqual(str(event.get("kind") or ""), "self_activity_state")
        self.assertEqual(agenda, [])
        self.assertEqual(str(residue.get("kind") or ""), "released_to_self_activity")
        self.assertGreater(float(residue.get("continuity_anchor") or 0.0), 0.50)
        self.assertGreater(float(residue.get("own_rhythm_anchor") or 0.0), 0.60)
        self.assertGreater(float(residue.get("lineage_gravity") or 0.0), 0.60)
        self.assertGreater(float(residue.get("agency_lineage") or 0.0), 0.60)
        self.assertGreater(float(residue.get("boundary_lineage") or 0.0), 0.40)

    def test_behavior_agenda_lifecycle_residue_marks_held_window_and_cools_recontact(self):
        event, agenda, residue = _promote_due_behavior_agenda_event_with_residue(
            {
                "kind": "time_idle",
                "idle_minutes": 28,
                "tags": ["time_idle", "user_busy", "respect_space"],
            },
            [
                {
                    "agenda_id": "agenda-hold-1",
                    "kind": "deferred_checkin",
                    "target": "counterpart",
                    "scheduled_after_min": 20,
                    "expires_after_min": 120,
                    "base_priority": 0.52,
                    "priority": 0.52,
                    "trigger_family": "light_checkin",
                    "allow_interrupt": True,
                    "note": "刚才那一下没说出口，先记着。",
                    "source_event_kind": "time_idle",
                    "created_at": 1,
                    "status": "pending",
                    "hold_count": 0,
                    "last_recheck_at_min": 20,
                    "carryover_mode": "quiet_recontact",
                    "carryover_strength": 0.42,
                    "attention_target": "counterpart_state",
                    "nonverbal_signal": "quiet_glance",
                    "presence_residue": 0.28,
                    "ambient_resonance": 0.12,
                    "self_activity_momentum": 0.40,
                }
            ],
            counterpart_assessment={
                "stance": "watchful",
                "scene": "busy_not_disrespectful",
                "boundary_pressure": 0.20,
            },
        )
        self.assertEqual(str(event.get("kind") or ""), "time_idle")
        self.assertEqual(len(agenda), 1)
        self.assertEqual(int(agenda[0].get("hold_count") or 0), 1)
        self.assertEqual(str(residue.get("kind") or ""), "held")
        self.assertIn(str(residue.get("carryover_mode") or ""), {"quiet_recontact", "own_rhythm"})
        self.assertGreater(float(residue.get("recontact_cooldown") or 0.0), 0.0)

    def test_recent_interaction_carryover_uses_agenda_lifecycle_residue(self):
        carryover = _recent_interaction_carryover(
            prior_current_event={
                "kind": "time_idle",
                "idle_minutes": 28,
                "tags": ["time_idle", "user_busy", "respect_space"],
            },
            prior_behavior_action={
                "action_target": "wait_and_recheck",
                "interaction_mode": "idle_presence",
            },
            prior_agenda_lifecycle_residue={
                "kind": "held",
                "carryover_mode": "own_rhythm",
                "carryover_strength": 0.58,
                "relationship_weather": "warm_residue",
                "attention_target": "self_then_counterpart",
                "nonverbal_signal": "thought_glance",
                "note": "这次先把窗口按住，没有顺势往前推进。",
                "source_tags": ["agenda_lifecycle", "held"],
                "idle_minutes": 28,
                "created_at": 1,
            },
            prior_counterpart_assessment={
                "stance": "watchful",
                "scene": "busy_not_disrespectful",
                "boundary_pressure": 0.18,
            },
            recent_events=[],
            current_event={"kind": "user_utterance", "text": "我回来了。"},
            response_style_hint="companion",
        )
        self.assertEqual(str(carryover.get("source_event_kind") or ""), "agenda_lifecycle:held")
        self.assertEqual(str(carryover.get("carryover_mode") or ""), "own_rhythm")
        self.assertGreaterEqual(float(carryover.get("strength") or 0.0), 0.5)

    def test_apply_agenda_lifecycle_residue_to_runtime_state_biases_world_and_counterpart(self):
        world, assessment = _apply_agenda_lifecycle_residue_to_runtime_state(
            agenda_lifecycle_residue={
                "kind": "dropped",
                "carryover_mode": "own_rhythm",
                "carryover_strength": 0.54,
                "presence_residue": 0.26,
                "ambient_resonance": 0.18,
                "self_activity_momentum": 0.66,
                "continuity_anchor": 0.62,
                "own_rhythm_anchor": 0.74,
                "recontact_anchor": 0.42,
                "boundary_anchor": 0.56,
                "memory_anchor": 0.38,
                "lineage_gravity": 0.72,
                "contact_lineage": 0.46,
                "repair_lineage": 0.32,
                "boundary_lineage": 0.68,
                "selfhood_lineage": 0.60,
                "agency_lineage": 0.78,
                "own_rhythm_bias": 0.66,
                "recontact_cooldown": 0.52,
                "counterpart_scene_bias": "busy_not_disrespectful",
                "counterpart_boundary_delta": -0.04,
            },
            world_model_state={
                "self_activity_momentum": 0.22,
                "presence_residue": 0.08,
                "ambient_resonance": 0.06,
                "boundary_load": 0.04,
            },
            counterpart_assessment={
                "stance": "watchful",
                "scene": "neutral",
                "boundary_pressure": 0.24,
                "reliability_read": 0.44,
                "respect_level": 0.46,
            },
        )
        self.assertGreaterEqual(float(world.get("self_activity_momentum") or 0.0), 0.66)
        self.assertGreaterEqual(float(world.get("boundary_load") or 0.0), 0.2)
        self.assertGreaterEqual(float(world.get("agency_lineage") or 0.0), 0.65)
        self.assertGreaterEqual(float(world.get("boundary_lineage") or 0.0), 0.50)
        self.assertGreaterEqual(float(world.get("lineage_gravity") or 0.0), 0.50)
        self.assertGreaterEqual(float(world.get("memory_gravity") or 0.0), 0.28)
        self.assertEqual(str(assessment.get("scene") or ""), "busy_not_disrespectful")
        self.assertLess(float(assessment.get("boundary_pressure") or 1.0), 0.24)
        self.assertGreaterEqual(float(assessment.get("reliability_read") or 0.0), 0.52)

    def test_apply_agenda_lifecycle_residue_boundary_lineage_reopens_watchfully(self):
        world, assessment = _apply_agenda_lifecycle_residue_to_runtime_state(
            agenda_lifecycle_residue={
                "kind": "held",
                "carryover_mode": "quiet_recontact",
                "carryover_strength": 0.42,
                "presence_residue": 0.18,
                "ambient_resonance": 0.10,
                "self_activity_momentum": 0.30,
                "continuity_anchor": 0.56,
                "own_rhythm_anchor": 0.34,
                "recontact_anchor": 0.40,
                "boundary_anchor": 0.72,
                "memory_anchor": 0.32,
                "lineage_gravity": 0.76,
                "contact_lineage": 0.28,
                "repair_lineage": 0.20,
                "boundary_lineage": 0.84,
                "selfhood_lineage": 0.74,
                "agency_lineage": 0.40,
                "own_rhythm_bias": 0.34,
                "recontact_cooldown": 0.44,
                "counterpart_boundary_delta": 0.0,
            },
            world_model_state={
                "boundary_load": 0.12,
                "lineage_gravity": 0.18,
                "boundary_lineage": 0.20,
                "selfhood_lineage": 0.18,
            },
            counterpart_assessment={
                "stance": "open",
                "scene": "neutral",
                "boundary_pressure": 0.10,
                "reliability_read": 0.66,
                "respect_level": 0.64,
            },
        )
        self.assertGreaterEqual(float(world.get("boundary_lineage") or 0.0), 0.70)
        self.assertGreaterEqual(float(world.get("selfhood_lineage") or 0.0), 0.60)
        self.assertEqual(str(assessment.get("stance") or ""), "watchful")
        self.assertGreater(float(assessment.get("boundary_pressure") or 0.0), 0.20)


if __name__ == "__main__":
    unittest.main()
