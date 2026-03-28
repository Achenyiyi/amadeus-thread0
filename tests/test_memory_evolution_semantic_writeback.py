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

    def test_record_behavior_consequence_prefers_frozen_behavior_action_over_live_action(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                wrote = _record_behavior_consequence(
                    store,
                    current_event={
                        "kind": "time_idle",
                        "trigger_family": "life_window",
                    },
                    behavior_action={
                        "action_target": "hold_own_rhythm",
                        "interaction_mode": "self_activity_hold",
                        "primary_motive": "preserve_self_rhythm",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "stale live action should not win",
                    },
                    reconsolidation_snapshot={
                        "primary_motive": "honor_continuity",
                        "motive_tension": "contact_without_pressure",
                        "goal_frame": "顺着之前留下的惦记等更自然的时候再接回来。",
                        "semantic_anchor_bundle": {
                            "continuity_anchor": 0.66,
                            "own_rhythm_anchor": 0.58,
                            "recontact_anchor": 0.62,
                            "boundary_anchor": 0.28,
                            "memory_anchor": 0.54,
                            "semantic_continuity_depth": 0.71,
                            "semantic_identity_gravity": 0.64,
                            "lineage_gravity": 0.68,
                            "contact_lineage": 0.61,
                            "repair_lineage": 0.36,
                            "boundary_lineage": 0.30,
                            "selfhood_lineage": 0.46,
                            "agency_lineage": 0.63,
                            "long_term_axis_count": 4,
                        },
                        "behavior_action": {
                            "action_target": "wait_and_recheck",
                            "interaction_mode": "steady_reply",
                            "primary_motive": "honor_continuity",
                            "motive_tension": "contact_without_pressure",
                            "goal_frame": "顺着之前留下的惦记等更自然的时候再接回来。",
                            "timing_window_min": 30,
                            "embodied_context": {
                                "kind": "access_request_pending",
                                "primary_status": "awaiting_approval",
                                "requested_access": ["workspace_write", "human_approval"],
                                "requested_help": True,
                            },
                        },
                    },
                    source="test:frozen_behavior_action_priority",
                    confidence=0.9,
                )
                self.assertTrue(wrote)

                traces = [
                    item
                    for item in store.list_revision_traces(limit=10)
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "behavior_consequence"
                ]
                self.assertEqual(len(traces), 1)
                trace = traces[0]
                self.assertEqual(
                    str(trace.get("target_id") or trace.get("content", {}).get("target_id") or ""),
                    "defer_recontact",
                )
                self.assertIn(
                    "生活上的惦记先轻轻压住",
                    str(trace.get("after_summary") or trace.get("content", {}).get("after_summary") or ""),
                )
                self.assertEqual(
                    str(trace.get("primary_motive") or trace.get("content", {}).get("primary_motive") or ""),
                    "honor_continuity",
                )
                self.assertEqual(float(trace.get("continuity_anchor") or trace.get("content", {}).get("continuity_anchor") or 0.0), 0.66)
                self.assertEqual(float(trace.get("own_rhythm_anchor") or trace.get("content", {}).get("own_rhythm_anchor") or 0.0), 0.58)
                self.assertEqual(float(trace.get("recontact_anchor") or trace.get("content", {}).get("recontact_anchor") or 0.0), 0.62)
                self.assertEqual(float(trace.get("memory_anchor") or trace.get("content", {}).get("memory_anchor") or 0.0), 0.54)
                self.assertEqual(float(trace.get("semantic_identity_gravity") or trace.get("content", {}).get("semantic_identity_gravity") or 0.0), 0.64)
                self.assertEqual(int(trace.get("long_term_axis_count") or trace.get("content", {}).get("long_term_axis_count") or 0), 4)
                embodied_context = trace.get("content", {}).get("embodied_context") if isinstance(trace.get("content"), dict) else {}
                self.assertEqual(str(embodied_context.get("kind") or ""), "access_request_pending")
                self.assertEqual(str(embodied_context.get("primary_status") or ""), "awaiting_approval")
                self.assertIn("workspace_write", embodied_context.get("requested_access") or [])
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
                        "hold_count": 2,
                        "own_rhythm_bias": 0.10,
                    },
                    "reconsolidation_snapshot": None,
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
                proactive = store.list_proactive_continuity_history(limit=10)
                self.assertEqual(len(proactive), 1)
                self.assertEqual(
                    str(proactive[0].get("kind") or proactive[0].get("content", {}).get("kind") or ""),
                    "held",
                )
                self.assertEqual(
                    str(proactive[0].get("carryover_mode") or proactive[0].get("content", {}).get("carryover_mode") or ""),
                    "quiet_recontact",
                )
            finally:
                store.close()

    def test_record_agenda_lifecycle_consequence_prefers_frozen_reconsolidation_snapshot(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                wrote = _record_agenda_lifecycle_consequence(
                    store,
                    agenda_lifecycle_residue={
                        "kind": "promoted",
                        "note": "stale residue should not win",
                        "carryover_mode": "quiet_recontact",
                        "carryover_strength": 0.81,
                        "hold_count": 4,
                    },
                    reconsolidation_snapshot={
                        "agenda_lifecycle_consequence": {
                            "kind": "released_to_self_activity",
                            "summary": "前面挂着的窗口没有继续往前推，注意力被自然收回到了自己的节奏里。",
                            "source_event_kind": "self_activity_state",
                            "trigger_family": "life_window",
                            "relationship_weather": "stable",
                            "carryover_mode": "own_rhythm",
                            "carryover_strength": 0.53,
                            "hold_count": 2,
                            "recontact_cooldown": 0.47,
                            "presence_residue": 0.33,
                            "ambient_resonance": 0.24,
                            "self_activity_momentum": 0.58,
                            "own_rhythm_bias": 0.61,
                            "continuity_anchor": 0.66,
                            "own_rhythm_anchor": 0.72,
                            "recontact_anchor": 0.34,
                            "boundary_anchor": 0.22,
                            "memory_anchor": 0.30,
                            "semantic_continuity_depth": 0.68,
                            "semantic_identity_gravity": 0.64,
                            "long_term_axis_count": 3,
                            "lineage_gravity": 0.70,
                            "contact_lineage": 0.44,
                            "repair_lineage": 0.28,
                            "boundary_lineage": 0.36,
                            "selfhood_lineage": 0.32,
                            "agency_lineage": 0.78,
                            "counterpart_scene_bias": "busy_not_disrespectful",
                            "counterpart_boundary_delta": -0.04,
                            "primary_motive": "preserve_self_rhythm",
                            "motive_tension": "self_rhythm_vs_contact",
                            "goal_frame": "先把自己的节奏走稳，再看那点窗口之后要不要接回来。",
                        }
                    },
                    source="test:agenda_lifecycle_frozen_snapshot",
                    confidence=0.91,
                )
                self.assertTrue(wrote)

                traces = [
                    item
                    for item in store.list_revision_traces(limit=10)
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "agenda_lifecycle"
                ]
                self.assertEqual(len(traces), 1)
                trace = traces[0]
                self.assertEqual(
                    str(trace.get("after_summary") or trace.get("content", {}).get("after_summary") or ""),
                    "前面挂着的窗口没有继续往前推，注意力被自然收回到了自己的节奏里。",
                )
                self.assertEqual(
                    str(trace.get("target_id") or trace.get("content", {}).get("target_id") or ""),
                    "released_to_self_activity",
                )
                self.assertEqual(float(trace.get("continuity_anchor") or trace.get("content", {}).get("continuity_anchor") or 0.0), 0.66)
                self.assertEqual(float(trace.get("own_rhythm_anchor") or trace.get("content", {}).get("own_rhythm_anchor") or 0.0), 0.72)
                self.assertEqual(float(trace.get("lineage_gravity") or trace.get("content", {}).get("lineage_gravity") or 0.0), 0.70)
                self.assertEqual(float(trace.get("agency_lineage") or trace.get("content", {}).get("agency_lineage") or 0.0), 0.78)

                proactive = store.list_proactive_continuity_history(limit=10)
                self.assertEqual(len(proactive), 1)
                record = proactive[0]
                self.assertEqual(
                    str(record.get("kind") or record.get("content", {}).get("kind") or ""),
                    "released_to_self_activity",
                )
                self.assertEqual(
                    str(record.get("trace_family") or record.get("content", {}).get("trace_family") or ""),
                    "own_rhythm_busy_window",
                )
                self.assertEqual(
                    str(record.get("counterpart_scene_bias") or record.get("content", {}).get("counterpart_scene_bias") or ""),
                    "busy_not_disrespectful",
                )
                self.assertEqual(
                    str(record.get("primary_motive") or record.get("content", {}).get("primary_motive") or ""),
                    "preserve_self_rhythm",
                )
                self.assertEqual(float(record.get("continuity_anchor") or record.get("content", {}).get("continuity_anchor") or 0.0), 0.66)
                self.assertEqual(float(record.get("own_rhythm_anchor") or record.get("content", {}).get("own_rhythm_anchor") or 0.0), 0.72)
                self.assertEqual(float(record.get("lineage_gravity") or record.get("content", {}).get("lineage_gravity") or 0.0), 0.70)
                self.assertEqual(float(record.get("agency_lineage") or record.get("content", {}).get("agency_lineage") or 0.0), 0.78)
            finally:
                store.close()

    def test_record_semantic_self_evidence_prefers_frozen_reconsolidation_semantics(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                wrote = _record_semantic_self_evidence(
                    store,
                    user_text="刚才那阵风过去之后，我还是能感觉到你就在这儿。",
                    appraisal={
                        "used": True,
                        "interaction_frame": "relationship",
                        "signals": {"memory_salient": True},
                        "salience": {
                            "relationship": 0.46,
                            "companionship": 0.54,
                            "selfhood": 0.10,
                        },
                    },
                    emotion_state={"label": "neutral"},
                    bond_state={"trust": 0.66, "closeness": 0.64, "hurt": 0.02},
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
                    reconsolidation_snapshot={
                        "primary_motive": "gentle_recontact",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "顺着刚刚留下的余温，轻轻回头一下。",
                        "semantic_anchor_bundle": {
                            "continuity_anchor": 0.64,
                            "own_rhythm_anchor": 0.70,
                            "recontact_anchor": 0.59,
                            "boundary_anchor": 0.24,
                            "memory_anchor": 0.56,
                            "semantic_continuity_depth": 0.72,
                            "semantic_identity_gravity": 0.67,
                            "lineage_gravity": 0.65,
                            "contact_lineage": 0.60,
                            "repair_lineage": 0.32,
                            "boundary_lineage": 0.28,
                            "selfhood_lineage": 0.48,
                            "agency_lineage": 0.66,
                            "long_term_axis_count": 3,
                        },
                        "counterpart": {
                            "stance": "open",
                            "scene": "care_bid",
                            "assessment_profile": {
                                "openness_drive": 0.76,
                                "guarded_drive": 0.18,
                                "guard_margin": -0.58,
                                "dominant_scene_signal": "care",
                                "scene_strengths": {
                                    "care": 0.84,
                                    "repair": 0.18,
                                    "friction": 0.06,
                                    "selfhood": 0.12,
                                    "busy": 0.22,
                                },
                            },
                        },
                    },
                    source="test:reconsolidation_semantics",
                    allow_behavior_action_inference=True,
                    allow_event_behavior_fallback=True,
                )
                self.assertTrue(wrote)
                traces = [
                    item
                    for item in store.list_revision_traces(limit=20)
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "semantic_self_evidence"
                ]
                self.assertTrue(traces)
                self.assertTrue(all(str(item.get("primary_motive") or "") == "gentle_recontact" for item in traces))
                self.assertTrue(all(str(item.get("motive_tension") or "") == "self_rhythm_vs_contact" for item in traces))
                self.assertTrue(all(str(item.get("behavior_semantics_source") or "") == "reconsolidation_snapshot" for item in traces))
                self.assertTrue(all(str(item.get("counterpart_stance") or "") == "open" for item in traces))
                self.assertTrue(all(str(item.get("counterpart_scene") or "") == "care_bid" for item in traces))
                self.assertTrue(all(str(item.get("counterpart_dominant_scene_signal") or "") == "care" for item in traces))
                self.assertTrue(all(float(item.get("counterpart_openness_drive") or 0.0) == 0.76 for item in traces))
                self.assertTrue(all(float(item.get("counterpart_scene_care_strength") or 0.0) == 0.84 for item in traces))
                self.assertTrue(all(float(item.get("counterpart_scene_repair_strength") or 0.0) == 0.18 for item in traces))
                self.assertTrue(all(float(item.get("counterpart_scene_friction_strength") or 0.0) == 0.06 for item in traces))
                self.assertTrue(all(float(item.get("counterpart_scene_selfhood_strength") or 0.0) == 0.12 for item in traces))
                self.assertTrue(all(float(item.get("counterpart_scene_busy_strength") or 0.0) == 0.22 for item in traces))
                self.assertTrue(all(float(item.get("continuity_anchor") or 0.0) == 0.64 for item in traces))
                self.assertTrue(all(float(item.get("own_rhythm_anchor") or 0.0) == 0.70 for item in traces))
                self.assertTrue(all(float(item.get("recontact_anchor") or 0.0) == 0.59 for item in traces))
                self.assertTrue(all(float(item.get("memory_anchor") or 0.0) == 0.56 for item in traces))
                self.assertTrue(all(float(item.get("semantic_identity_gravity") or 0.0) == 0.67 for item in traces))
                self.assertTrue(all(int(item.get("long_term_axis_count") or 0) == 3 for item in traces))
            finally:
                store.close()

    def test_record_behavior_plan_long_horizon_memory_uses_frozen_busy_counterpart_scene(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                wrote = _record_behavior_trace_writeback(
                    store,
                    current_event={"kind": "self_activity_state", "tags": ["self_activity", "own_task"]},
                    behavior_action={
                        "action_target": "hold_own_rhythm",
                        "interaction_mode": "self_activity_hold",
                        "primary_motive": "preserve_self_rhythm",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "先把自己这边的节奏走完，再自然地把注意力转回来。",
                    },
                    behavior_plan={
                        "kind": "self_activity_continue",
                        "target": "self",
                        "primary_motive": "preserve_self_rhythm",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "先把自己这边的节奏走完，再自然地把注意力转回来。",
                    },
                    interaction_carryover=None,
                    agenda_lifecycle_residue=None,
                    reconsolidation_snapshot={
                        "counterpart": {
                            "stance": "open",
                            "scene": "busy_not_disrespectful",
                            "respect_level": 0.76,
                            "reciprocity": 0.72,
                            "boundary_pressure": 0.08,
                            "reliability_read": 0.78,
                        }
                    },
                    source="test:busy_counterpart_writeback",
                    confidence=0.9,
                )
                self.assertTrue(wrote)
                relationship = store.list_relationship_timeline(limit=5)
                summaries = [
                    str(item.get("summary") or item.get("content", {}).get("summary") or "")
                    for item in relationship
                ]
                self.assertIn(
                    "当对方当下更像忙着别的事时，她不会把沉默直接误判成冷淡；她会先收回自己的节奏，等更自然的时候再接回来。",
                    summaries,
                )
            finally:
                store.close()

    def test_record_behavior_plan_long_horizon_memory_prefers_frozen_snapshot_over_live_plan(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                wrote = _record_behavior_trace_writeback(
                    store,
                    current_event={"kind": "user_utterance"},
                    behavior_action={
                        "action_target": "hold_own_rhythm",
                        "interaction_mode": "self_activity_hold",
                        "primary_motive": "preserve_self_rhythm",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "stale live action should not win",
                    },
                    behavior_plan={
                        "kind": "self_activity_continue",
                        "target": "self",
                        "trigger_family": "self_activity",
                        "carryover_mode": "own_rhythm",
                        "note": "stale live plan should not win",
                        "primary_motive": "preserve_self_rhythm",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "stale live plan should not win",
                    },
                    interaction_carryover=None,
                    agenda_lifecycle_residue=None,
                    reconsolidation_snapshot={
                        "behavior_plan": {
                            "kind": "deferred_checkin",
                            "target": "care",
                            "trigger_family": "observe",
                            "carryover_mode": "life_window",
                            "note": "final frozen plan should win",
                            "primary_motive": "honor_continuity",
                            "motive_tension": "contact_without_pressure",
                            "goal_frame": "顺着之前留下的惦记自然接回来。",
                            "embodied_context": {
                                "kind": "access_request_pending",
                                "primary_status": "awaiting_approval",
                                "requested_access": ["workspace_write", "human_approval"],
                                "requested_help": True,
                            },
                        }
                    },
                    source="test:frozen_behavior_plan_priority",
                    confidence=0.91,
                )
                self.assertTrue(wrote)

                traces = [
                    item
                    for item in store.list_revision_traces(limit=12)
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "behavior_plan"
                ]
                self.assertEqual(len(traces), 1)
                trace = traces[0]
                self.assertEqual(str(trace.get("target_id") or trace.get("content", {}).get("target_id") or ""), "deferred_checkin")
                self.assertEqual(
                    str(trace.get("after_summary") or trace.get("content", {}).get("after_summary") or ""),
                    "final frozen plan should win",
                )
                embodied_context = trace.get("content", {}).get("embodied_context") if isinstance(trace.get("content"), dict) else {}
                self.assertEqual(str(embodied_context.get("kind") or ""), "access_request_pending")
                self.assertEqual(str(embodied_context.get("primary_status") or ""), "awaiting_approval")
                self.assertIn("workspace_write", embodied_context.get("requested_access") or [])

                worldline = [
                    item
                    for item in store.list_worldline_events(limit=10)
                    if "behavior_plan"
                    in (
                        (item.get("tags") if isinstance(item.get("tags"), list) else [])
                        or ((item.get("content") or {}).get("tags") if isinstance(item.get("content"), dict) else [])
                    )
                ]
                self.assertEqual(len(worldline), 1)
                tags = worldline[0].get("tags") if isinstance(worldline[0].get("tags"), list) else worldline[0].get("content", {}).get("tags", [])
                self.assertIn("deferred_checkin", tags)
                self.assertIn("life_window", tags)
                self.assertNotIn("own_rhythm", tags)

                relationship = store.list_relationship_timeline(limit=5)
                summaries = [
                    str(item.get("summary") or item.get("content", {}).get("summary") or "")
                    for item in relationship
                ]
                self.assertIn(
                    "这段关系里的靠近不需要每次都当场说完；她会把一部分惦记留到之后再自然接回来。",
                    summaries,
                )
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

        def _fake_record_behavior_plan_long_horizon_memory(_store, *, behavior_plan, reconsolidation_snapshot=None, source, confidence):
            seen["plan_kind"] = str(behavior_plan.get("kind") or "")
            return False

        def _fake_record_retrieved_continuity_reactivation(
            _store,
            *,
            interaction_carryover,
            behavior_action,
            behavior_plan,
            reconsolidation_snapshot=None,
            source,
            confidence,
        ):
            seen["carryover_mode"] = str(interaction_carryover.get("carryover_mode") or "")
            seen["action_target"] = str(behavior_action.get("action_target") or "")
            seen["reactivation_plan_kind"] = str(behavior_plan.get("kind") or "")
            return False

        def _fake_record_agenda_lifecycle_consequence(
            _store,
            *,
            agenda_lifecycle_residue,
            reconsolidation_snapshot=None,
            source,
            confidence,
        ):
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

    def test_record_behavior_trace_writeback_prefers_frozen_reactivation_inputs(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                wrote = _record_behavior_trace_writeback(
                    store,
                    current_event={"kind": "user_utterance"},
                    behavior_action={
                        "action_target": "hold_own_rhythm",
                        "interaction_mode": "self_activity_hold",
                        "primary_motive": "preserve_self_rhythm",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "stale action should not win",
                    },
                    behavior_plan={
                        "kind": "self_activity_continue",
                        "trigger_family": "self_activity",
                        "carryover_mode": "own_rhythm",
                        "note": "stale plan should not win",
                    },
                    interaction_carryover={
                        "source": "retrieved_behavior_plan",
                        "strength": 0.61,
                        "carryover_mode": "own_rhythm",
                        "relationship_weather": "guarded_residue",
                        "note": "stale carryover should not win",
                        "source_tags": [
                            "plan_kind:self_activity_continue",
                            "trigger_family:self_activity",
                        ],
                    },
                    agenda_lifecycle_residue={},
                    reconsolidation_snapshot={
                        "behavior_mode": "steady_reply",
                        "primary_motive": "honor_continuity",
                        "motive_tension": "contact_without_pressure",
                        "goal_frame": "顺着之前留下的惦记自然接回来。",
                        "behavior_action": {
                            "action_target": "wait_and_recheck",
                            "interaction_mode": "steady_reply",
                            "primary_motive": "honor_continuity",
                            "motive_tension": "contact_without_pressure",
                            "goal_frame": "顺着之前留下的惦记自然接回来。",
                        },
                        "behavior_plan": {
                            "kind": "deferred_checkin",
                            "trigger_family": "observe",
                            "carryover_mode": "life_window",
                            "note": "final frozen carryover path",
                            "primary_motive": "honor_continuity",
                            "motive_tension": "contact_without_pressure",
                            "goal_frame": "顺着之前留下的惦记自然接回来。",
                        },
                        "interaction_carryover": {
                            "source": "retrieved_behavior_plan",
                            "strength": 0.44,
                            "carryover_mode": "life_window",
                            "relationship_weather": "warm_residue",
                            "note": "final frozen carryover path",
                            "source_tags": [
                                "plan_kind:deferred_checkin",
                                "trigger_family:observe",
                            ],
                        },
                    },
                    source="test:reactivation_frozen_snapshot",
                    confidence=0.92,
                )
                self.assertTrue(wrote)

                traces = [
                    item
                    for item in store.list_revision_traces(limit=12)
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "behavior_reactivation"
                ]
                self.assertEqual(len(traces), 1)
                trace = traces[0]
                self.assertEqual(str(trace.get("target_id") or trace.get("content", {}).get("target_id") or ""), "deferred_checkin")
                self.assertEqual(str(trace.get("carryover_mode") or trace.get("content", {}).get("carryover_mode") or ""), "life_window")
                self.assertEqual(str(trace.get("current_plan_kind") or trace.get("content", {}).get("current_plan_kind") or ""), "deferred_checkin")
                self.assertEqual(str(trace.get("current_action_target") or trace.get("content", {}).get("current_action_target") or ""), "wait_and_recheck")
                self.assertEqual(str(trace.get("current_interaction_mode") or trace.get("content", {}).get("current_interaction_mode") or ""), "steady_reply")
                self.assertEqual(str(trace.get("source_note") or trace.get("content", {}).get("source_note") or ""), "final frozen carryover path")
                self.assertEqual(str(trace.get("primary_motive") or trace.get("content", {}).get("primary_motive") or ""), "honor_continuity")
                self.assertEqual(
                    str(trace.get("goal_frame") or trace.get("content", {}).get("goal_frame") or ""),
                    "顺着之前留下的惦记自然接回来。",
                )

                worldline = [
                    item
                    for item in store.list_worldline_events(limit=10)
                    if "retrieved_reactivation"
                    in (
                        (item.get("tags") if isinstance(item.get("tags"), list) else [])
                        or ((item.get("content") or {}).get("tags") if isinstance(item.get("content"), dict) else [])
                    )
                ]
                self.assertEqual(len(worldline), 1)
                tags = worldline[0].get("tags") if isinstance(worldline[0].get("tags"), list) else worldline[0].get("content", {}).get("tags", [])
                self.assertIn("life_window", tags)
                self.assertIn("deferred_checkin", tags)
                self.assertNotIn("own_rhythm", tags)
            finally:
                store.close()

    def test_record_behavior_trace_writeback_persists_counterpart_assessment_history_from_frozen_snapshot(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                kwargs = {
                    "current_event": {"kind": "user_utterance"},
                    "behavior_action": {
                        "interaction_mode": "self_activity_reopen",
                        "primary_motive": "gentle_recontact",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "顺着余温轻轻回头。",
                    },
                    "behavior_plan": {},
                    "interaction_carryover": {},
                    "agenda_lifecycle_residue": {},
                    "reconsolidation_snapshot": {
                        "event_kind": "user_utterance",
                        "interaction_frame": "relationship",
                        "primary_motive": "gentle_recontact",
                        "motive_tension": "self_rhythm_vs_contact",
                        "goal_frame": "顺着余温轻轻回头。",
                        "counterpart": {
                            "stance": "open",
                            "scene": "care_bid",
                            "respect_level": 0.76,
                            "reciprocity": 0.72,
                            "boundary_pressure": 0.08,
                            "reliability_read": 0.80,
                            "assessment_profile": {
                                "openness_drive": 0.78,
                                "guarded_drive": 0.16,
                                "guard_margin": -0.62,
                                "dominant_scene_signal": "care",
                                "scene_strengths": {"care": 0.84, "repair": 0.18, "busy": 0.22},
                            },
                        },
                    },
                    "source": "test:counterpart_history",
                    "confidence": 0.9,
                }
                self.assertTrue(_record_behavior_trace_writeback(store, **kwargs))
                self.assertFalse(_record_behavior_trace_writeback(store, **kwargs))

                history = store.list_counterpart_assessment_history(limit=10)
                self.assertEqual(len(history), 1)
                record = history[0]
                self.assertEqual(str(record.get("scene") or record.get("content", {}).get("scene") or ""), "care_bid")
                self.assertEqual(str(record.get("stance") or record.get("content", {}).get("stance") or ""), "open")
                self.assertEqual(
                    str(record.get("primary_motive") or record.get("content", {}).get("primary_motive") or ""),
                    "gentle_recontact",
                )
                profile = record.get("assessment_profile")
                if not isinstance(profile, dict):
                    profile = record.get("content", {}).get("assessment_profile")
                self.assertIsInstance(profile, dict)
                self.assertEqual(str(profile.get("dominant_scene_signal") or ""), "care")
                self.assertEqual(float(profile.get("openness_drive") or 0.0), 0.78)
                self.assertIn(
                    "认真靠近",
                    str(record.get("summary") or record.get("content", {}).get("summary") or ""),
                )
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
                    reconsolidation_snapshot={
                        "counterpart": {
                            "stance": "open",
                            "scene": "care_bid",
                            "respect_level": 0.74,
                            "reciprocity": 0.70,
                            "boundary_pressure": 0.08,
                            "reliability_read": 0.78,
                            "assessment_profile": {
                                "openness_drive": 0.76,
                                "guarded_drive": 0.18,
                                "guard_margin": -0.58,
                                "dominant_scene_signal": "care",
                                "scene_strengths": {
                                    "care": 0.84,
                                    "repair": 0.18,
                                    "friction": 0.06,
                                    "selfhood": 0.12,
                                    "busy": 0.22,
                                },
                            },
                        }
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
                self.assertEqual(str(presence.get("dominant_counterpart_stance") or ""), "open")
                self.assertEqual(str(presence.get("dominant_counterpart_scene") or ""), "care_bid")
                self.assertEqual(str(presence.get("counterpart_dominant_scene_signal") or ""), "care")
                self.assertEqual(float(presence.get("counterpart_openness_drive") or 0.0), 0.76)
                self.assertEqual(float(presence.get("counterpart_scene_care_strength") or 0.0), 0.84)
                self.assertEqual(float(presence.get("counterpart_scene_repair_strength") or 0.0), 0.18)
                self.assertEqual(float(presence.get("counterpart_scene_friction_strength") or 0.0), 0.06)
                self.assertEqual(float(presence.get("counterpart_scene_selfhood_strength") or 0.0), 0.12)
                self.assertEqual(float(presence.get("counterpart_scene_busy_strength") or 0.0), 0.22)
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

    def test_refresh_semantic_narratives_absorbs_embodied_access_constraints(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                wrote = _passive_evolution_memory_update(
                    store,
                    user_text="",
                    appraisal={
                        "used": True,
                        "confidence": 0.88,
                        "interaction_frame": "task",
                        "salience": {
                            "relationship": 0.10,
                            "companionship": 0.12,
                            "selfhood": 0.06,
                            "task": 0.82,
                        },
                        "signals": {},
                    },
                    emotion_state={"label": "neutral"},
                    bond_state={
                        "trust": 0.52,
                        "closeness": 0.48,
                        "hurt": 0.0,
                    },
                    current_event={
                        "kind": "self_activity_state",
                        "tags": ["self_activity", "tool_attempt", "approval_gate"],
                    },
                    world_model_state={
                        "presence_residue": 0.08,
                        "ambient_resonance": 0.03,
                        "self_activity_momentum": 0.50,
                    },
                    digital_body_state={
                        "active_surface": "approval_gate",
                        "perception_channels": ["dialogue"],
                        "action_channels": ["language", "structured_action", "approval_gate"],
                        "world_surfaces": ["dialogue", "browser", "network"],
                        "available_toolsets": ["search_web"],
                        "access_state": {
                            "mode": "approval_pending",
                            "conditions": ["human_approval_required", "cookie_access_missing"],
                            "pending_approval_count": 1,
                            "external_mutation_pending": True,
                            "missing_access": ["cookies"],
                            "requestable_access": ["cookies", "human_approval"],
                            "cookie_state": "missing",
                            "network_access": "available",
                        },
                        "resource_state": {
                            "action_packet_count": 1,
                            "pending_approval_count": 1,
                        },
                        "body_constraints": ["human_approval_required", "cookie_access_missing"],
                    },
                )
                self.assertTrue(wrote)

                _refresh_semantic_self_narratives(store, source="test:embodied_access_refresh")
                narratives = store.list_semantic_self_narratives(limit=16)
                agency = next(item for item in narratives if str(item.get("category") or "") == "agency_style")
                boundary = next(item for item in narratives if str(item.get("category") or "") == "boundary_style")
                presence = next(item for item in narratives if str(item.get("category") or "") == "presence_style")

                self.assertIn("入口", str(agency.get("text") or ""))
                self.assertTrue(any(term in str(agency.get("text") or "") for term in ("申请", "换路", "没做到")))
                self.assertTrue(any(term in str(boundary.get("text") or "") for term in ("数字环境", "入口条件", "cookies", "审批")))
                self.assertTrue(any(term in str(presence.get("text") or "") for term in ("待申请", "入口", "动作")))
                self.assertGreater(float(agency.get("support_mass") or 0.0), 0.0)
                self.assertGreater(float(boundary.get("support_mass") or 0.0), 0.0)
            finally:
                store.close()

    def test_refresh_semantic_narratives_absorbs_embodied_growth(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                wrote = _passive_evolution_memory_update(
                    store,
                    user_text="",
                    appraisal={
                        "used": True,
                        "confidence": 0.86,
                        "interaction_frame": "task",
                        "salience": {
                            "relationship": 0.08,
                            "companionship": 0.10,
                            "selfhood": 0.08,
                            "task": 0.84,
                        },
                        "signals": {},
                    },
                    emotion_state={"label": "neutral"},
                    bond_state={
                        "trust": 0.50,
                        "closeness": 0.46,
                        "hurt": 0.0,
                    },
                    current_event={
                        "kind": "self_activity_state",
                        "tags": ["self_activity", "tool_attempt", "tool_success"],
                    },
                    world_model_state={
                        "presence_residue": 0.04,
                        "ambient_resonance": 0.02,
                        "self_activity_momentum": 0.56,
                    },
                    digital_body_state={
                        "active_surface": "tooling",
                        "perception_channels": ["dialogue"],
                        "action_channels": ["language", "structured_action", "tooling"],
                        "world_surfaces": ["dialogue", "network", "sandbox"],
                        "available_toolsets": ["search_web", "workspace_fs"],
                        "active_tools": ["search_web"],
                        "access_state": {
                            "mode": "tool_enabled",
                            "granted_toolsets": ["search_web", "workspace_fs"],
                            "network_access": "available",
                            "sandbox_mode": "workspace_scoped",
                        },
                        "resource_state": {
                            "action_packet_count": 1,
                            "completed_packet_count": 1,
                            "external_tool_count": 1,
                        },
                    },
                )
                self.assertTrue(wrote)

                _refresh_semantic_self_narratives(store, source="test:embodied_growth_refresh")
                narratives = store.list_semantic_self_narratives(limit=16)
                agency = next(item for item in narratives if str(item.get("category") or "") == "agency_style")
                presence = next(item for item in narratives if str(item.get("category") or "") == "presence_style")

                self.assertTrue(any(term in str(agency.get("text") or "") for term in ("环境路径", "从零摸索", "身体部分")))
                self.assertTrue(any(term in str(presence.get("text") or "") for term in ("环境入口", "身体部分", "只亮这一轮")))
                self.assertGreater(float(agency.get("support_mass") or 0.0), 0.0)
            finally:
                store.close()

    def test_record_agenda_lifecycle_preserves_compact_artifact_identity_in_proactive_history(self):
        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                wrote = _record_agenda_lifecycle_consequence(
                    store,
                    agenda_lifecycle_residue={"kind": "held"},
                    reconsolidation_snapshot={
                        "agenda_lifecycle_consequence": {
                            "kind": "held",
                            "summary": "先把这条小窗口留住，等更自然的时候再续上。",
                            "trigger_family": "life_window",
                            "carryover_mode": "quiet_recontact",
                            "carryover_strength": 0.42,
                            "hold_count": 1,
                        },
                        "digital_body_consequence": {
                            "kind": "environmental_friction",
                            "summary": "和刚才那条检索结果的连续性断了，得先把它接回来。",
                            "artifact_continuity": "missing",
                            "active_artifact_kind": "search_result",
                            "active_artifact_label": "Persistence",
                            "artifact_reacquisition_mode": "rerun_search",
                            "artifact_carrier": "source_ref",
                            "artifact_source_ref_ids": [17],
                            "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                            "artifact_source_query": "langgraph persistence checkpointer thread",
                            "artifact_source_title": "Persistence",
                            "artifact_source_tool_name": "search_web",
                            "environmental_friction": True,
                        },
                    },
                    source="test:artifact_identity_writeback",
                    confidence=0.9,
                )
                self.assertTrue(wrote)

                proactive = store.list_proactive_continuity_history(limit=10)
                self.assertEqual(len(proactive), 1)
                embodied = proactive[0].get("embodied_context") if isinstance(proactive[0].get("embodied_context"), dict) else {}
                self.assertEqual(embodied.get("artifact_carrier"), "source_ref")
                self.assertEqual(embodied.get("artifact_source_ref_ids"), [17])
                self.assertEqual(
                    embodied.get("artifact_source_query"),
                    "langgraph persistence checkpointer thread",
                )
                self.assertIn("docs.langchain.com", str(embodied.get("artifact_source_url") or ""))
                self.assertNotIn("preview", embodied)
            finally:
                store.close()
