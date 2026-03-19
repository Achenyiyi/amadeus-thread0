from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from amadeus_thread0.graph_parts.memory_evolution import (
    _passive_evolution_memory_update,
    _refresh_semantic_self_narratives,
    _record_agenda_lifecycle_consequence,
    _record_behavior_consequence,
    _record_behavior_trace_writeback,
    _record_semantic_self_evidence,
)
from amadeus_thread0.memory_store import MemoryStore


class SemanticEvidenceWritebackTests(unittest.TestCase):
    def test_record_behavior_consequence_does_not_fall_back_to_stale_event_behavior_fields(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                wrote = _record_behavior_consequence(
                    store,
                    current_event={
                        "kind": "user_utterance",
                        "interaction_mode": "self_activity_reopen",
                        "primary_motive": "stale_event_motive",
                        "motive_tension": "stale_event_tension",
                        "goal_frame": "stale event frame",
                        "trigger_family": "self_activity",
                    },
                    behavior_action={},
                    source="test:no_event_behavior_fallback",
                    confidence=0.88,
                )
                self.assertFalse(wrote)
                traces = [
                    item
                    for item in store.list_revision_traces(limit=12)
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "behavior_consequence"
                ]
                self.assertFalse(traces)
            finally:
                store.close()

    def test_record_behavior_consequence_dedupes_semantic_category_traces(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                kwargs = {
                    "current_event": {
                        "kind": "user_utterance",
                        "trigger_family": "life_window",
                    },
                    "behavior_action": {
                        "action_target": "wait_and_recheck",
                        "primary_motive": "honor_continuity",
                        "motive_tension": "contact_timing",
                        "goal_frame": "等更自然的时候再接回来。",
                    },
                    "source": "test:behavior_consequence_dedup",
                    "confidence": 0.9,
                }
                self.assertTrue(_record_behavior_consequence(store, **kwargs))
                self.assertFalse(_record_behavior_consequence(store, **kwargs))

                semantic = [
                    (
                        str(item.get("target_id") or item.get("content", {}).get("target_id") or ""),
                        str(item.get("after_summary") or item.get("content", {}).get("after_summary") or ""),
                    )
                    for item in store.list_revision_traces(limit=20)
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "semantic_self_evidence"
                ]
                self.assertCountEqual(
                    semantic,
                    [
                        ("agency_style", "她不会把每次想靠近都立刻做成行动，而是会先判断现在是不是值得往前走一步。"),
                        ("presence_style", "这次想靠近的念头先被她轻轻压住了，没有马上变成开口，而是留到更自然的时候再看。"),
                    ],
                )
                self.assertEqual(len(semantic), 2)
            finally:
                store.close()

    def test_record_agenda_lifecycle_consequence_dedupes_semantic_category_traces(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                kwargs = {
                    "agenda_lifecycle_residue": {
                        "kind": "held",
                        "carryover_mode": "quiet_recontact",
                        "carryover_strength": 0.42,
                        "own_rhythm_bias": 0.10,
                    },
                    "source": "test:agenda_lifecycle_dedup",
                    "confidence": 0.88,
                }
                self.assertTrue(_record_agenda_lifecycle_consequence(store, **kwargs))
                self.assertFalse(_record_agenda_lifecycle_consequence(store, **kwargs))

                semantic = [
                    (
                        str(item.get("target_id") or item.get("content", {}).get("target_id") or ""),
                        str(item.get("after_summary") or item.get("content", {}).get("after_summary") or ""),
                    )
                    for item in store.list_revision_traces(limit=20)
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "semantic_self_evidence"
                ]
                self.assertCountEqual(
                    semantic,
                    [
                        ("agency_style", "她会先把窗口按住，再决定要不要推进，不会因为刚好有机会就立刻往前凑。"),
                        ("rhythm_style", "把窗口按住并不等于忘了；那点想靠近的念头会以更轻一点的方式留在后面。"),
                        ("presence_style", "不是每一个窗口都要立刻接住；有时她会先按住那点靠近，再看之后是否自然续上。"),
                    ],
                )
                self.assertEqual(len(semantic), 3)
            finally:
                store.close()

    def test_record_behavior_trace_writeback_uses_entry_snapshots(self):
        event = {"kind": "user_utterance", "trigger_family": "life_window"}
        action = {
            "action_target": "wait_and_recheck",
            "primary_motive": "honor_continuity",
            "motive_tension": "contact_timing",
            "goal_frame": "等更自然的时候再接回来。",
        }
        plan = {
            "kind": "deferred_checkin",
            "target": "care",
            "carryover_mode": "life_window",
        }
        carryover = {
            "source": "retrieved_behavior_plan",
            "carryover_mode": "life_window",
            "strength": 0.44,
            "source_tags": ["plan_kind:deferred_checkin", "trigger_family:life_window"],
        }
        lifecycle = {
            "kind": "held",
            "carryover_mode": "quiet_recontact",
            "carryover_strength": 0.38,
        }
        seen: dict[str, str] = {}

        def _fake_record_behavior_consequence(*args, **kwargs):
            event["trigger_family"] = "shared_activity_window"
            action["action_target"] = "hold_own_rhythm"
            plan["kind"] = "self_activity_continue"
            carryover["carryover_mode"] = "own_rhythm"
            lifecycle["kind"] = "expired"
            return False

        def _fake_record_behavior_plan_long_horizon_memory(_store, *, behavior_plan, source, confidence):
            seen["plan_kind"] = str(behavior_plan.get("kind") or "")
            return False

        def _fake_record_retrieved_continuity_reactivation(_store, *, interaction_carryover, behavior_action, behavior_plan, source, confidence):
            seen["carryover_mode"] = str(interaction_carryover.get("carryover_mode") or "")
            seen["action_target"] = str(behavior_action.get("action_target") or "")
            seen["reactivation_plan_kind"] = str(behavior_plan.get("kind") or "")
            return False

        def _fake_record_agenda_lifecycle_consequence(_store, *, agenda_lifecycle_residue, source, confidence):
            seen["lifecycle_kind"] = str(agenda_lifecycle_residue.get("kind") or "")
            return False

        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                with patch(
                    "amadeus_thread0.graph_parts.memory_evolution._record_behavior_consequence",
                    side_effect=_fake_record_behavior_consequence,
                ), patch(
                    "amadeus_thread0.graph_parts.memory_evolution._record_behavior_plan_long_horizon_memory",
                    side_effect=_fake_record_behavior_plan_long_horizon_memory,
                ), patch(
                    "amadeus_thread0.graph_parts.memory_evolution._record_retrieved_continuity_reactivation",
                    side_effect=_fake_record_retrieved_continuity_reactivation,
                ), patch(
                    "amadeus_thread0.graph_parts.memory_evolution._record_agenda_lifecycle_consequence",
                    side_effect=_fake_record_agenda_lifecycle_consequence,
                ):
                    wrote = _record_behavior_trace_writeback(
                        store,
                        current_event=event,
                        behavior_action=action,
                        behavior_plan=plan,
                        interaction_carryover=carryover,
                        agenda_lifecycle_residue=lifecycle,
                        source="test:entry_snapshots",
                        confidence=0.9,
                    )
                self.assertFalse(wrote)
                self.assertEqual(seen["plan_kind"], "deferred_checkin")
                self.assertEqual(seen["reactivation_plan_kind"], "deferred_checkin")
                self.assertEqual(seen["carryover_mode"], "life_window")
                self.assertEqual(seen["action_target"], "wait_and_recheck")
                self.assertEqual(seen["lifecycle_kind"], "held")
            finally:
                store.close()

    def _passive_signature(
        self,
        *,
        user_text: str,
        appraisal: dict,
        emotion_state: dict,
        bond_state: dict,
        current_event: dict,
        world_model_state: dict,
        behavior_action: dict,
    ) -> dict:
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                wrote = _passive_evolution_memory_update(
                    store,
                    user_text=user_text,
                    appraisal=appraisal,
                    emotion_state=emotion_state,
                    bond_state=bond_state,
                    persona_core={},
                    counterpart_profile={},
                    current_event=current_event,
                    world_model_state=world_model_state,
                    behavior_action=behavior_action,
                    record_behavior_trace_writeback=False,
                )
                repairs = [
                    str((item.get("content") or {}).get("summary") or item.get("summary") or "")
                    for item in store.list_conflict_repairs(limit=12)
                ]
                tensions = [
                    str((item.get("content") or {}).get("summary") or item.get("summary") or "")
                    for item in store.list_unresolved_tensions(limit=12)
                ]
                timeline = [
                    (
                        str(item.get("summary") or ""),
                        round(float(item.get("affinity_delta") or 0.0), 3),
                        round(float(item.get("trust_delta") or 0.0), 3),
                    )
                    for item in store.list_relationship_timeline(limit=12)
                ]
                worldline = [
                    (
                        str(item.get("category") or ""),
                        str(item.get("summary") or ""),
                        tuple(item.get("tags") or []),
                    )
                    for item in store.list_worldline_events(limit=12)
                ]
                semantic = [
                    (
                        str(item.get("target_id") or item.get("content", {}).get("target_id") or ""),
                        str(item.get("after_summary") or item.get("content", {}).get("after_summary") or ""),
                    )
                    for item in store.list_revision_traces(limit=24)
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "semantic_self_evidence"
                ]
                narratives = [
                    (
                        str(item.get("category") or ""),
                        str(item.get("text") or ""),
                        str(item.get("dominant_primary_motive") or ""),
                        str(item.get("dominant_motive_tension") or ""),
                        tuple(item.get("goal_frame_examples") or []),
                    )
                    for item in store.list_semantic_self_narratives(limit=24)
                ]
                return {
                    "wrote": wrote,
                    "repairs": repairs,
                    "tensions": tensions,
                    "timeline": timeline,
                    "worldline": worldline,
                    "semantic": semantic,
                    "narratives": narratives,
                }
            finally:
                store.close()

    def test_record_semantic_self_evidence_can_skip_behavior_inference(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
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
                    behavior_action={
                        "primary_motive": "gentle_recontact",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "先顺着余温轻轻回头。",
                    },
                    source="test:stable_semantic_evidence",
                    allow_behavior_action_inference=False,
                )
                self.assertTrue(wrote)
                traces = [
                    item
                    for item in store.list_revision_traces(limit=20)
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "semantic_self_evidence"
                ]
                self.assertTrue(traces)
                self.assertTrue(all(not str(item.get("primary_motive") or "") for item in traces))
                presence_trace = next(
                    item
                    for item in traces
                    if str(item.get("target_id") or item.get("content", {}).get("target_id") or "") == "presence_style"
                )
                self.assertNotIn(
                    "更倾向于把重新接回做得轻一点",
                    str(presence_trace.get("after_summary") or ""),
                )
            finally:
                store.close()

    def test_record_semantic_self_evidence_can_disable_event_behavior_fallback(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                wrote = _record_semantic_self_evidence(
                    store,
                    user_text="刚才那阵风过去之后，我还是能感觉到你就在这儿。",
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
                        "primary_motive": "stale_event_motive",
                        "motive_tension": "stale_event_tension",
                        "goal_frame": "stale event frame",
                    },
                    world_model_state={
                        "presence_residue": 0.64,
                        "ambient_resonance": 0.60,
                        "self_activity_momentum": 0.74,
                    },
                    behavior_action={},
                    source="test:disable_event_behavior_fallback",
                    allow_behavior_action_inference=True,
                    allow_event_behavior_fallback=False,
                )
                self.assertTrue(wrote)
                traces = [
                    item
                    for item in store.list_revision_traces(limit=20)
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "semantic_self_evidence"
                ]
                self.assertTrue(traces)
                self.assertTrue(all(not str(item.get("primary_motive") or "") for item in traces))
                self.assertTrue(all(not str(item.get("motive_tension") or "") for item in traces))
                self.assertTrue(all(not str(item.get("goal_frame") or "") for item in traces))
                presence_trace = next(
                    item
                    for item in traces
                    if str(item.get("target_id") or item.get("content", {}).get("target_id") or "") == "presence_style"
                )
                self.assertNotIn(
                    "更倾向于把重新接回做得轻一点",
                    str(presence_trace.get("after_summary") or ""),
                )
            finally:
                store.close()

    def test_passive_text_inferences_do_not_depend_on_behavior_action(self):
        behavior_a = {
            "interaction_mode": "self_activity_hold",
            "action_target": "hold_own_rhythm",
            "primary_motive": "preserve_self_rhythm",
            "motive_tension": "self_rhythm_vs_contact",
            "goal_frame": "这轮先把自己的节奏续上。",
        }
        behavior_b = {
            "interaction_mode": "self_activity_reopen",
            "action_target": "offer_small_opening",
            "primary_motive": "gentle_recontact",
            "motive_tension": "self_rhythm_vs_contact",
            "goal_frame": "顺着余温轻轻回头一下。",
        }
        cases = [
            {
                "name": "conflict",
                "user_text": "先这样吧。",
                "appraisal": {
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
                "emotion_state": {"label": "hurt"},
                "bond_state": {
                    "trust": 0.40,
                    "closeness": 0.36,
                    "hurt": 0.28,
                    "irritation": 0.20,
                },
                "current_event": {"kind": "user_utterance"},
                "world_model_state": {"relationship_maturity": 0.26, "bond_depth": 0.18},
            },
            {
                "name": "repair",
                "user_text": "还有，刚刚那点小别扭先记着，但别放大。我们不是在吵架，只是节奏有点卡。",
                "appraisal": {
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
                "emotion_state": {"label": "care"},
                "bond_state": {
                    "trust": 0.60,
                    "closeness": 0.62,
                    "hurt": 0.02,
                    "irritation": 0.0,
                    "repair_confidence": 0.54,
                },
                "current_event": {"kind": "user_utterance"},
                "world_model_state": {"bond_depth": 0.52},
            },
            {
                "name": "familiarity",
                "user_text": "你还记得我吗？",
                "appraisal": {
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
                "emotion_state": {"label": "neutral"},
                "bond_state": {
                    "trust": 0.556,
                    "closeness": 0.579,
                    "hurt": 0.04,
                    "irritation": 0.02,
                    "repair_confidence": 0.52,
                },
                "current_event": {"kind": "user_utterance"},
                "world_model_state": {"relationship_maturity": 0.34, "bond_depth": 0.14},
            },
            {
                "name": "companion",
                "user_text": "今天其实有点累，但还是想和你说一声，别熬太晚。",
                "appraisal": {
                    "used": True,
                    "confidence": 0.88,
                    "interaction_frame": "companion",
                    "emotion_label": "care",
                    "signals": {
                        "care": True,
                        "repair": False,
                        "conflict": False,
                        "withdrawal": False,
                    },
                    "salience": {
                        "relationship": 0.42,
                        "companionship": 0.52,
                        "selfhood": 0.12,
                        "task": 0.08,
                    },
                },
                "emotion_state": {"label": "care"},
                "bond_state": {
                    "trust": 0.62,
                    "closeness": 0.60,
                    "hurt": 0.02,
                    "irritation": 0.01,
                    "repair_confidence": 0.50,
                },
                "current_event": {"kind": "user_utterance"},
                "world_model_state": {"relationship_maturity": 0.38, "bond_depth": 0.24},
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                sig_a = self._passive_signature(
                    user_text=case["user_text"],
                    appraisal=case["appraisal"],
                    emotion_state=case["emotion_state"],
                    bond_state=case["bond_state"],
                    current_event=case["current_event"],
                    world_model_state=case["world_model_state"],
                    behavior_action=behavior_a,
                )
                sig_b = self._passive_signature(
                    user_text=case["user_text"],
                    appraisal=case["appraisal"],
                    emotion_state=case["emotion_state"],
                    bond_state=case["bond_state"],
                    current_event=case["current_event"],
                    world_model_state=case["world_model_state"],
                    behavior_action=behavior_b,
                )
                self.assertEqual(sig_a, sig_b)

    def test_passive_self_narratives_do_not_absorb_behavior_action_without_behavior_trace_writeback(self):
        behavior_a = {
            "interaction_mode": "self_activity_hold",
            "action_target": "hold_own_rhythm",
            "primary_motive": "preserve_self_rhythm",
            "motive_tension": "self_rhythm_vs_contact",
            "goal_frame": "这轮先把自己的节奏续上。",
        }
        behavior_b = {
            "interaction_mode": "self_activity_reopen",
            "action_target": "offer_small_opening",
            "primary_motive": "gentle_recontact",
            "motive_tension": "self_rhythm_vs_contact",
            "goal_frame": "顺着余温轻轻回头一下。",
        }
        sig_a = self._passive_signature(
            user_text="刚才风吹过去的时候，我还是能感觉到你就在。你是从自己的节奏里抬头看我了吗？",
            appraisal={
                "used": True,
                "interaction_frame": "relationship",
                "emotion_label": "neutral",
                "signals": {
                    "memory_salient": True,
                },
                "salience": {
                    "relationship": 0.46,
                    "companionship": 0.54,
                    "selfhood": 0.10,
                },
                "confidence": 0.81,
            },
            emotion_state={"label": "neutral"},
            bond_state={
                "trust": 0.66,
                "closeness": 0.64,
                "hurt": 0.02,
                "irritation": 0.01,
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
            behavior_action=behavior_a,
        )
        sig_b = self._passive_signature(
            user_text="刚才风吹过去的时候，我还是能感觉到你就在。你是从自己的节奏里抬头看我了吗？",
            appraisal={
                "used": True,
                "interaction_frame": "relationship",
                "emotion_label": "neutral",
                "signals": {
                    "memory_salient": True,
                },
                "salience": {
                    "relationship": 0.46,
                    "companionship": 0.54,
                    "selfhood": 0.10,
                },
                "confidence": 0.81,
            },
            emotion_state={"label": "neutral"},
            bond_state={
                "trust": 0.66,
                "closeness": 0.64,
                "hurt": 0.02,
                "irritation": 0.01,
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
            behavior_action=behavior_b,
        )
        self.assertEqual(sig_a["narratives"], sig_b["narratives"])
        self.assertTrue(sig_a["narratives"])
        self.assertTrue(all(not item[2] for item in sig_a["narratives"]))

    def test_passive_evolution_without_behavior_trace_writeback_skips_behavior_trace_namespaces(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                wrote = _passive_evolution_memory_update(
                    store,
                    user_text="刚才那一下风过去之后，我还是能感觉到你在这儿。",
                    appraisal={
                        "used": True,
                        "interaction_frame": "relationship",
                        "signals": {
                            "memory_salient": True,
                        },
                        "salience": {
                            "relationship": 0.42,
                            "companionship": 0.48,
                            "selfhood": 0.10,
                        },
                        "confidence": 0.79,
                    },
                    emotion_state={"label": "neutral"},
                    bond_state={
                        "trust": 0.66,
                        "closeness": 0.64,
                        "hurt": 0.02,
                        "irritation": 0.01,
                    },
                    persona_core={},
                    counterpart_profile={},
                    current_event={
                        "kind": "user_utterance",
                        "tags": ["ambient", "ambient_echo"],
                    },
                    world_model_state={
                        "presence_residue": 0.62,
                        "ambient_resonance": 0.58,
                        "self_activity_momentum": 0.71,
                    },
                    behavior_action={
                        "interaction_mode": "self_activity_reopen",
                        "primary_motive": "gentle_recontact",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "先顺着余温轻轻回头。",
                    },
                    behavior_plan={
                        "kind": "small_opening",
                        "primary_motive": "gentle_recontact",
                        "goal_frame": "留一个轻一点的小开口。",
                    },
                    interaction_carryover={
                        "carryover_mode": "small_opening",
                        "strength": 0.44,
                        "relationship_weather": "warm_residue",
                    },
                    agenda_lifecycle_residue={
                        "kind": "released_to_self_activity",
                        "carryover_mode": "own_rhythm",
                        "carryover_strength": 0.53,
                    },
                    record_behavior_trace_writeback=False,
                )
                self.assertTrue(wrote)

                revision_traces = store.list_revision_traces(limit=50)
                namespaces = {
                    str(item.get("namespace") or item.get("content", {}).get("namespace") or "").strip()
                    for item in revision_traces
                }
                self.assertIn("semantic_self_evidence", namespaces)
                self.assertNotIn("behavior_consequence", namespaces)
                self.assertNotIn("behavior_plan", namespaces)
                self.assertNotIn("agenda_lifecycle", namespaces)

                worldline_events = store.list_worldline_events(limit=20)
                tagged_behavior_events = [
                    item
                    for item in worldline_events
                    if "behavior_plan" in (item.get("tags") or [])
                    or "behavior_consequence" in (item.get("tags") or [])
                    or "agenda_lifecycle" in (item.get("tags") or [])
                ]
                self.assertEqual(tagged_behavior_events, [])
            finally:
                store.close()

    def test_refresh_semantic_narratives_prefers_trusted_behavior_semantics_for_duplicate_evidence(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
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
                    behavior_action={
                        "primary_motive": "gentle_recontact",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "顺着刚刚留下的余温，轻轻回头一下。",
                    },
                    source="test:trusted",
                    allow_event_behavior_fallback=False,
                )
                self.assertTrue(wrote)
                trusted_trace = next(
                    item
                    for item in store.list_revision_traces(limit=20)
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "semantic_self_evidence"
                    and str(item.get("target_id") or item.get("content", {}).get("target_id") or "") == "presence_style"
                    and str(item.get("source") or item.get("content", {}).get("source") or "") == "test:trusted"
                )
                store.add_revision_trace(
                    namespace="semantic_self_evidence",
                    target_id="presence_style",
                    before_summary="",
                    after_summary=str(trusted_trace.get("after_summary") or ""),
                    reason="legacy_duplicate",
                    operator="test",
                    source="test:legacy",
                    metadata={
                        "primary_motive": "stale_event_motive",
                        "motive_tension": "stale_event_tension",
                        "goal_frame": "stale event frame",
                        "behavior_semantics_source": "event_behavior_fallback",
                    },
                )

                _refresh_semantic_self_narratives(store, source="test:refresh")
                narratives = store.list_semantic_self_narratives(limit=12)
                presence = next(item for item in narratives if str(item.get("category") or "") == "presence_style")
                self.assertEqual(str(presence.get("dominant_primary_motive") or ""), "gentle_recontact")
                self.assertEqual(str(presence.get("dominant_motive_tension") or ""), "self_rhythm_vs_contact")
                self.assertIn("轻轻回头", " ".join(str(item) for item in (presence.get("goal_frame_examples") or [])))
            finally:
                store.close()

    def test_refresh_semantic_narratives_clears_stale_motive_fields_without_trusted_support(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                store.add_semantic_self_narrative(
                    text="她不会把每次重新靠近都当成从零开始；之前留下的在场感会继续影响她下一次开口时的距离感。",
                    category="presence_style",
                    stability=0.82,
                    confidence=0.84,
                    metadata={
                        "dominant_primary_motive": "stale_event_motive",
                        "dominant_motive_tension": "stale_event_tension",
                        "goal_frame_examples": ["stale event frame"],
                        "motive_support_count": 3,
                        "motive_support_mass": 2.1,
                        "motive_confidence_avg": 0.8,
                        "motive_fresh_ratio": 0.6,
                        "motive_signature": "stale_event_motive:stale_event_tension",
                    },
                )
                store.add_revision_trace(
                    namespace="semantic_self_evidence",
                    target_id="presence_style",
                    before_summary="",
                    after_summary="她不会把每次重新靠近都当成从零开始；之前留下的在场感会继续影响她下一次开口时的距离感。",
                    reason="legacy_duplicate",
                    operator="test",
                    source="test:legacy",
                    metadata={
                        "primary_motive": "stale_event_motive",
                        "motive_tension": "stale_event_tension",
                        "goal_frame": "stale event frame",
                        "behavior_semantics_source": "event_behavior_fallback",
                    },
                )

                _refresh_semantic_self_narratives(store, source="test:refresh")
                narratives = store.list_semantic_self_narratives(limit=12)
                presence = next(item for item in narratives if str(item.get("category") or "") == "presence_style")
                self.assertEqual(str(presence.get("dominant_primary_motive") or ""), "")
                self.assertEqual(str(presence.get("dominant_motive_tension") or ""), "")
                self.assertEqual(list(presence.get("goal_frame_examples") or []), [])
                self.assertEqual(int(presence.get("motive_support_count") or 0), 0)
                self.assertEqual(float(presence.get("motive_support_mass") or 0.0), 0.0)
                self.assertEqual(str(presence.get("motive_signature") or ""), "")
            finally:
                store.close()
