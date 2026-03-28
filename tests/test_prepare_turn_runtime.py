import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from amadeus_thread0.memory_store import MemoryStore
from amadeus_thread0.graph_parts.prepare_turn_runtime import _prepare_turn_runtime


class _StopAfterPlan(RuntimeError):
    pass


class _StopAfterMemory(RuntimeError):
    pass


def _prepared_turn_fixture() -> dict[str, object]:
    return {
        "profile": {
            "counterpart_id": "okabe_rintaro",
            "name": "冈部伦太郎",
            "short_name": "冈部",
            "aliases": ["冈部伦太郎", "冈部"],
        },
        "persona_core": {
            "character_id": "kurisu_amadeus",
            "display_name": "Amadeus 牧濑红莉栖",
            "role_brief": "",
            "identity_axioms": [],
            "value_floor": [],
            "evolution_contract": {},
            "strict_canon": True,
        },
        "prior_behavior_agenda": [],
        "agenda_lifecycle_residue": {},
        "user_text": "",
        "effective_user_text": "",
        "science_mode": False,
        "response_style_hint": "natural",
        "external_probe_mode": False,
        "retrieved": {"semantic_self_narratives": [], "working_items": [], "working_chars": 0, "triggered": False},
        "relationship": {"stage": "friend", "notes": "", "affinity_score": 0.0, "trust_score": 0.0, "derived": True},
        "canon_recontact_baseline": {},
        "worldline_focus": [],
        "seed_emotion_state": {"label": "neutral"},
        "seed_bond_state": {"trust": 0.5, "closeness": 0.5, "hurt": 0.0, "irritation": 0.0, "engagement_drive": 0.5, "repair_confidence": 0.5},
        "seed_allostasis_state": {"safety_need": 0.2, "closeness_need": 0.2, "competence_need": 0.4, "autonomy_need": 0.2, "cognitive_budget": 0.8, "relational_security": 0.5},
        "seed_counterpart_assessment": {"respect_level": 0.6, "reciprocity": 0.6, "boundary_pressure": 0.1, "reliability_read": 0.6, "stance": "open", "scene": "neutral"},
        "seed_world_model_state": {},
        "seed_evolution_state": {},
        "seed_tsundere_intensity": 0.4,
        "appraisal": {},
        "current_event": {"kind": "time_idle", "event_frame": "idle", "tags": ["quiet_presence"], "idle_minutes": 18},
        "interaction_carryover": {},
    }


def _evolved_fixture() -> dict[str, object]:
    return {
        "world_model_state": {
            "self_activity_momentum": 0.74,
            "presence_residue": 0.34,
            "ambient_resonance": 0.28,
        },
        "evolution_state": {},
        "emotion_state": {"label": "neutral"},
        "bond_state": {"trust": 0.5, "closeness": 0.5, "hurt": 0.0, "irritation": 0.0, "engagement_drive": 0.5, "repair_confidence": 0.5},
        "allostasis_state": {"safety_need": 0.2, "closeness_need": 0.2, "competence_need": 0.4, "autonomy_need": 0.2, "cognitive_budget": 0.8, "relational_security": 0.5},
        "counterpart_assessment": {"respect_level": 0.6, "reciprocity": 0.6, "boundary_pressure": 0.1, "reliability_read": 0.6, "stance": "open", "scene": "neutral"},
        "behavior_policy": {},
        "behavior_action": {"action_target": "stale_engine_action", "primary_motive": "engine_stage"},
        "reconsolidation_snapshot": {"behavior_mode": "stale_engine_mode"},
    }


class PrepareTurnRuntimeTests(unittest.TestCase):
    def test_prepare_turn_runtime_writes_semantic_evidence_from_final_action_after_memory_refresh(self):
        prepared_turn = _prepared_turn_fixture()
        prepared_turn["user_text"] = "刚才风吹过去的时候，我还是能感觉到你就在。你是从自己的节奏里抬头看我了吗？"
        prepared_turn["effective_user_text"] = prepared_turn["user_text"]
        prepared_turn["current_event"] = {
            "kind": "user_utterance",
            "event_frame": "dialogue",
            "tags": ["ambient", "ambient_echo"],
        }
        prepared_turn["appraisal"] = {
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
        }
        prepared_turn["seed_bond_state"] = {
            **dict(prepared_turn["seed_bond_state"]),
            "trust": 0.66,
            "closeness": 0.64,
        }
        refreshed_retrieved = {
            "semantic_self_narratives": [],
            "working_items": [],
            "working_chars": 0,
            "triggered": False,
            "relationship": dict(prepared_turn["relationship"]),
        }
        evolved = _evolved_fixture()
        evolved["world_model_state"] = {
            "self_activity_momentum": 0.74,
            "presence_residue": 0.64,
            "ambient_resonance": 0.60,
        }
        behavior_actions = [
            {
                "action_target": "hold_own_rhythm",
                "interaction_mode": "self_activity_hold",
                "primary_motive": "preserve_self_rhythm",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "这轮先把自己的节奏续上。",
                "deferred_action_family": "own_rhythm",
                "timing_window_min": 18,
                "relationship_weather": "warm_residue",
                "attention_target": "self_state",
                "nonverbal_signal": "continue_focus",
                "channel": "speech",
            },
            {
                "action_target": "offer_small_opening",
                "interaction_mode": "self_activity_reopen",
                "primary_motive": "gentle_recontact",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "顺着刚刚留下的余温，轻轻回头一下。",
                "deferred_action_family": "small_opening",
                "timing_window_min": 0,
                "relationship_weather": "warm_residue",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "glance_back",
                "channel": "speech",
            },
            {
                "action_target": "offer_small_opening",
                "interaction_mode": "self_activity_reopen",
                "primary_motive": "gentle_recontact",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "顺着刚刚留下的余温，轻轻回头一下。",
                "deferred_action_family": "small_opening",
                "timing_window_min": 0,
                "relationship_weather": "warm_residue",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "glance_back",
                "channel": "speech",
            },
        ]

        def _fake_behavior_plan_from_action(current_event, behavior_action, *, world_model_state):
            action_target = str(behavior_action.get("action_target") or "").strip().lower()
            if action_target == "hold_own_rhythm":
                return {
                    "kind": "self_activity_continue",
                    "target": "self",
                    "scheduled_after_min": 18,
                    "trigger_family": "self_activity",
                    "allow_interrupt": True,
                    "note": "这轮先把自己的节奏续上。",
                    "primary_motive": str(behavior_action.get("primary_motive") or ""),
                    "motive_tension": str(behavior_action.get("motive_tension") or ""),
                    "goal_frame": str(behavior_action.get("goal_frame") or ""),
                    "carryover_mode": "own_rhythm",
                    "self_activity_momentum": 0.72,
                }
            return {
                "kind": "small_opening",
                "target": "counterpart",
                "scheduled_after_min": 0,
                "trigger_family": "self_activity",
                "allow_interrupt": True,
                "note": "顺着刚刚留下的余温，轻轻回头一下。",
                "primary_motive": str(behavior_action.get("primary_motive") or ""),
                "motive_tension": str(behavior_action.get("motive_tension") or ""),
                "goal_frame": str(behavior_action.get("goal_frame") or ""),
                "carryover_mode": "small_opening",
                "carryover_strength": 0.41,
                "presence_residue": 0.64,
                "ambient_resonance": 0.60,
                "self_activity_momentum": 0.58,
            }

        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", return_value=evolved):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                            with patch(
                                "amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update",
                                return_value=True,
                            ):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._retrieve_context",
                                    return_value=refreshed_retrieved,
                                ):
                                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._worldline_focus", return_value=[]):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot",
                                            side_effect=lambda **kwargs: kwargs["relationship"],
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary",
                                                return_value="summary",
                                            ):
                                                with patch(
                                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                                    side_effect=behavior_actions,
                                                ):
                                                    with patch(
                                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                                        side_effect=_fake_behavior_plan_from_action,
                                                    ):
                                                        with patch(
                                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                                            return_value=[],
                                                        ):
                                                            with patch(
                                                                "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                                return_value={},
                                                            ):
                                                                with patch(
                                                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl",
                                                                    return_value=None,
                                                                ):
                                                                    _prepare_turn_runtime(
                                                                        state={"persona_state": {}},
                                                                        store=store,
                                                                        turn_now_ts=123,
                                                                        prepared_turn=prepared_turn,
                                                                    )

                traces = [
                    item
                    for item in store.list_revision_traces(limit=40)
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "semantic_self_evidence"
                    and str(item.get("source") or item.get("content", {}).get("source") or "") == "auto:passive_evolution_final"
                ]
                self.assertTrue(traces)
                presence_trace = next(
                    item
                    for item in traces
                    if str(item.get("target_id") or item.get("content", {}).get("target_id") or "") == "presence_style"
                )
                self.assertEqual(str(presence_trace.get("primary_motive") or ""), "gentle_recontact")
                self.assertEqual(str(presence_trace.get("motive_tension") or ""), "self_rhythm_vs_contact")
                self.assertIn("轻轻回头", str(presence_trace.get("goal_frame") or ""))
                self.assertIn("更倾向于把重新接回做得轻一点", str(presence_trace.get("after_summary") or ""))
            finally:
                store.close()

    def test_prepare_turn_runtime_final_semantic_evidence_does_not_fall_back_to_stale_event_behavior_fields(self):
        prepared_turn = _prepared_turn_fixture()
        prepared_turn["user_text"] = "刚才风吹过去的时候，我还是能感觉到你就在。"
        prepared_turn["effective_user_text"] = prepared_turn["user_text"]
        prepared_turn["current_event"] = {
            "kind": "user_utterance",
            "event_frame": "dialogue",
            "tags": ["ambient", "ambient_echo"],
            "primary_motive": "stale_event_motive",
            "motive_tension": "stale_event_tension",
            "goal_frame": "stale event frame",
        }
        prepared_turn["appraisal"] = {
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
        }
        prepared_turn["seed_bond_state"] = {
            **dict(prepared_turn["seed_bond_state"]),
            "trust": 0.66,
            "closeness": 0.64,
        }
        refreshed_retrieved = {
            "semantic_self_narratives": [],
            "working_items": [],
            "working_chars": 0,
            "triggered": False,
            "relationship": dict(prepared_turn["relationship"]),
        }
        evolved = _evolved_fixture()
        evolved["world_model_state"] = {
            "self_activity_momentum": 0.74,
            "presence_residue": 0.64,
            "ambient_resonance": 0.60,
        }
        behavior_actions = [
            {
                "action_target": "hold_own_rhythm",
                "interaction_mode": "self_activity_hold",
                "primary_motive": "preserve_self_rhythm",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "这轮先把自己的节奏续上。",
                "deferred_action_family": "own_rhythm",
                "timing_window_min": 18,
                "relationship_weather": "warm_residue",
                "attention_target": "self_state",
                "nonverbal_signal": "continue_focus",
                "channel": "speech",
            },
            {},
        ]

        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", return_value=evolved):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                            with patch(
                                "amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update",
                                return_value=False,
                            ):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._retrieve_context",
                                    return_value=refreshed_retrieved,
                                ):
                                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._worldline_focus", return_value=[]):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot",
                                            side_effect=lambda **kwargs: kwargs["relationship"],
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary",
                                                return_value="summary",
                                            ):
                                                with patch(
                                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                                    side_effect=behavior_actions,
                                                ):
                                                    with patch(
                                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                                        return_value={},
                                                    ):
                                                        with patch(
                                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                                            return_value=[],
                                                        ):
                                                            with patch(
                                                                "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                                return_value={},
                                                            ):
                                                                with patch(
                                                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl",
                                                                    return_value=None,
                                                                ):
                                                                    _prepare_turn_runtime(
                                                                        state={"persona_state": {}},
                                                                        store=store,
                                                                        turn_now_ts=123,
                                                                        prepared_turn=prepared_turn,
                                                                    )

                traces = [
                    item
                    for item in store.list_revision_traces(limit=40)
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "semantic_self_evidence"
                    and str(item.get("source") or item.get("content", {}).get("source") or "") == "auto:passive_evolution_final"
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

    def test_prepare_turn_runtime_writes_behavior_trace_from_final_action_after_memory_refresh(self):
        prepared_turn = _prepared_turn_fixture()
        prepared_turn["current_event"] = {"kind": "user_utterance", "event_frame": "dialogue", "tags": []}
        refreshed_retrieved = {
            "semantic_self_narratives": [],
            "working_items": [],
            "working_chars": 0,
            "triggered": False,
            "relationship": dict(prepared_turn["relationship"]),
        }
        behavior_actions = [
            {
                "action_target": "hold_own_rhythm",
                "interaction_mode": "self_activity_hold",
                "primary_motive": "preserve_self_rhythm",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "这轮先把自己的节奏续上。",
                "deferred_action_family": "own_rhythm",
                "timing_window_min": 18,
                "relationship_weather": "warm_residue",
                "attention_target": "self_state",
                "nonverbal_signal": "continue_focus",
                "channel": "speech",
            },
            {
                "action_target": "offer_small_opening",
                "interaction_mode": "self_activity_reopen",
                "primary_motive": "gentle_recontact",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "顺着刚刚留下的余温，轻轻回头一下。",
                "deferred_action_family": "small_opening",
                "timing_window_min": 0,
                "relationship_weather": "warm_residue",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "glance_back",
                "channel": "speech",
            },
            {
                "action_target": "offer_small_opening",
                "interaction_mode": "self_activity_reopen",
                "primary_motive": "gentle_recontact",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "顺着刚刚留下的余温，轻轻回头一下。",
                "deferred_action_family": "small_opening",
                "timing_window_min": 0,
                "relationship_weather": "warm_residue",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "glance_back",
                "channel": "speech",
            },
        ]

        def _fake_behavior_plan_from_action(current_event, behavior_action, *, world_model_state):
            action_target = str(behavior_action.get("action_target") or "").strip().lower()
            if action_target == "hold_own_rhythm":
                return {
                    "kind": "self_activity_continue",
                    "target": "self",
                    "scheduled_after_min": 18,
                    "trigger_family": "self_activity",
                    "allow_interrupt": True,
                    "note": "这轮先把自己的节奏续上。",
                    "primary_motive": str(behavior_action.get("primary_motive") or ""),
                    "motive_tension": str(behavior_action.get("motive_tension") or ""),
                    "goal_frame": str(behavior_action.get("goal_frame") or ""),
                    "carryover_mode": "own_rhythm",
                    "self_activity_momentum": 0.72,
                }
            return {
                "kind": "small_opening",
                "target": "counterpart",
                "scheduled_after_min": 0,
                "trigger_family": "self_activity",
                "allow_interrupt": True,
                "note": "顺着刚刚留下的余温，轻轻回头一下。",
                "primary_motive": str(behavior_action.get("primary_motive") or ""),
                "motive_tension": str(behavior_action.get("motive_tension") or ""),
                "goal_frame": str(behavior_action.get("goal_frame") or ""),
                "carryover_mode": "small_opening",
                "carryover_strength": 0.41,
                "presence_residue": 0.33,
                "ambient_resonance": 0.18,
                "self_activity_momentum": 0.58,
            }

        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", return_value=_evolved_fixture()):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                            with patch(
                                "amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update",
                                return_value=True,
                            ):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._retrieve_context",
                                    return_value=refreshed_retrieved,
                                ):
                                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._worldline_focus", return_value=[]):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot",
                                            side_effect=lambda **kwargs: kwargs["relationship"],
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary",
                                                return_value="summary",
                                            ):
                                                with patch(
                                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                                    side_effect=behavior_actions,
                                                ):
                                                    with patch(
                                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                                        side_effect=_fake_behavior_plan_from_action,
                                                    ):
                                                        with patch(
                                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                                            return_value=[],
                                                        ):
                                                            with patch(
                                                                "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                                return_value={},
                                                            ):
                                                                with patch(
                                                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl",
                                                                    return_value=None,
                                                                ):
                                                                    result = _prepare_turn_runtime(
                                                                        state={"persona_state": {}},
                                                                        store=store,
                                                                        turn_now_ts=123,
                                                                        prepared_turn=prepared_turn,
                                                                    )

                behavior_plan = result.get("behavior_plan") if isinstance(result.get("behavior_plan"), dict) else {}
                self.assertEqual(str(behavior_plan.get("kind") or ""), "small_opening")
                traces = [
                    item
                    for item in store.list_revision_traces(limit=20)
                    if str(item.get("namespace") or item.get("content", {}).get("namespace") or "") == "behavior_plan"
                ]
                self.assertEqual(len(traces), 1)
                self.assertEqual(str(traces[0].get("target_id") or ""), "small_opening")
                trace_content = traces[0].get("content") if isinstance(traces[0].get("content"), dict) else {}
                self.assertEqual(str(trace_content.get("source") or ""), "auto:passive_evolution_final")
                self.assertEqual(str(trace_content.get("primary_motive") or ""), "gentle_recontact")
                self.assertIn("轻轻回头", str(trace_content.get("goal_frame") or ""))
            finally:
                store.close()

    def test_prepare_turn_runtime_refreshes_semantic_self_narratives_from_final_action_after_memory_refresh(self):
        prepared_turn = _prepared_turn_fixture()
        prepared_turn["user_text"] = "刚才风吹过去的时候，我还是能感觉到你就在。你是从自己的节奏里抬头看我了吗？"
        prepared_turn["effective_user_text"] = prepared_turn["user_text"]
        prepared_turn["current_event"] = {
            "kind": "user_utterance",
            "event_frame": "dialogue",
            "tags": ["ambient", "ambient_echo"],
        }
        prepared_turn["appraisal"] = {
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
        }
        prepared_turn["seed_bond_state"] = {
            **dict(prepared_turn["seed_bond_state"]),
            "trust": 0.66,
            "closeness": 0.64,
        }
        refreshed_retrieved = {
            "semantic_self_narratives": [],
            "working_items": [],
            "working_chars": 0,
            "triggered": False,
            "relationship": dict(prepared_turn["relationship"]),
        }
        evolved = _evolved_fixture()
        evolved["world_model_state"] = {
            "self_activity_momentum": 0.74,
            "presence_residue": 0.64,
            "ambient_resonance": 0.60,
        }
        behavior_actions = [
            {
                "action_target": "hold_own_rhythm",
                "interaction_mode": "self_activity_hold",
                "primary_motive": "preserve_self_rhythm",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "这轮先把自己的节奏续上。",
                "deferred_action_family": "own_rhythm",
                "timing_window_min": 18,
                "relationship_weather": "warm_residue",
                "attention_target": "self_state",
                "nonverbal_signal": "continue_focus",
                "channel": "speech",
            },
            {
                "action_target": "offer_small_opening",
                "interaction_mode": "self_activity_reopen",
                "primary_motive": "gentle_recontact",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "顺着刚刚留下的余温，轻轻回头一下。",
                "deferred_action_family": "small_opening",
                "timing_window_min": 0,
                "relationship_weather": "warm_residue",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "glance_back",
                "channel": "speech",
            },
            {
                "action_target": "offer_small_opening",
                "interaction_mode": "self_activity_reopen",
                "primary_motive": "gentle_recontact",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "顺着刚刚留下的余温，轻轻回头一下。",
                "deferred_action_family": "small_opening",
                "timing_window_min": 0,
                "relationship_weather": "warm_residue",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "glance_back",
                "channel": "speech",
            },
        ]

        def _fake_behavior_plan_from_action(current_event, behavior_action, *, world_model_state):
            action_target = str(behavior_action.get("action_target") or "").strip().lower()
            if action_target == "hold_own_rhythm":
                return {
                    "kind": "self_activity_continue",
                    "target": "self",
                    "scheduled_after_min": 18,
                    "trigger_family": "self_activity",
                    "allow_interrupt": True,
                    "note": "这轮先把自己的节奏续上。",
                    "primary_motive": str(behavior_action.get("primary_motive") or ""),
                    "motive_tension": str(behavior_action.get("motive_tension") or ""),
                    "goal_frame": str(behavior_action.get("goal_frame") or ""),
                    "carryover_mode": "own_rhythm",
                    "self_activity_momentum": 0.72,
                }
            return {
                "kind": "small_opening",
                "target": "counterpart",
                "scheduled_after_min": 0,
                "trigger_family": "self_activity",
                "allow_interrupt": True,
                "note": "顺着刚刚留下的余温，轻轻回头一下。",
                "primary_motive": str(behavior_action.get("primary_motive") or ""),
                "motive_tension": str(behavior_action.get("motive_tension") or ""),
                "goal_frame": str(behavior_action.get("goal_frame") or ""),
                "carryover_mode": "small_opening",
                "carryover_strength": 0.41,
                "presence_residue": 0.64,
                "ambient_resonance": 0.60,
                "self_activity_momentum": 0.58,
            }

        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", return_value=evolved):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                            with patch(
                                "amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update",
                                return_value=True,
                            ):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._retrieve_context",
                                    return_value=refreshed_retrieved,
                                ):
                                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._worldline_focus", return_value=[]):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot",
                                            side_effect=lambda **kwargs: kwargs["relationship"],
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary",
                                                return_value="summary",
                                            ):
                                                with patch(
                                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                                    side_effect=behavior_actions,
                                                ):
                                                    with patch(
                                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                                        side_effect=_fake_behavior_plan_from_action,
                                                    ):
                                                        with patch(
                                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                                            return_value=[],
                                                        ):
                                                            with patch(
                                                                "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                                return_value={},
                                                            ):
                                                                with patch(
                                                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl",
                                                                    return_value=None,
                                                                ):
                                                                    _prepare_turn_runtime(
                                                                        state={"persona_state": {}},
                                                                        store=store,
                                                                        turn_now_ts=123,
                                                                        prepared_turn=prepared_turn,
                                                                    )

                narratives = store.list_semantic_self_narratives(limit=12)
                self.assertTrue(narratives)
                presence = next(
                    item for item in narratives if str(item.get("category") or "") == "presence_style"
                )
                self.assertEqual(str(presence.get("dominant_primary_motive") or ""), "gentle_recontact")
                self.assertEqual(str(presence.get("dominant_motive_tension") or ""), "self_rhythm_vs_contact")
                self.assertIn("轻轻回头", " ".join(presence.get("goal_frame_examples") or []))
                self.assertIn("motive=gentle_recontact:self_rhythm_vs_contact", str(presence.get("support_signature") or ""))
            finally:
                store.close()

    def test_prepare_turn_runtime_recomputes_current_semantic_profile_after_final_narrative_refresh(self):
        prepared_turn = _prepared_turn_fixture()
        prepared_turn["user_text"] = "你刚才是不是又顺着那点余温回头看我了？"
        prepared_turn["effective_user_text"] = prepared_turn["user_text"]
        prepared_turn["current_event"] = {
            "kind": "user_utterance",
            "event_frame": "dialogue",
            "tags": ["ambient", "ambient_echo"],
        }
        prepared_turn["retrieved"] = {
            "semantic_self_narratives": [],
            "working_items": [],
            "working_chars": 0,
            "triggered": False,
        }
        evolved = _evolved_fixture()
        final_action = {
            "action_target": "offer_small_opening",
            "interaction_mode": "self_activity_reopen",
            "primary_motive": "gentle_recontact",
            "motive_tension": "self_rhythm_vs_contact",
            "goal_frame": "顺着刚刚留下的余温，轻轻回头一下。",
            "deferred_action_family": "small_opening",
            "timing_window_min": 0,
            "relationship_weather": "warm_residue",
            "attention_target": "counterpart_state",
            "nonverbal_signal": "glance_back",
            "channel": "speech",
        }
        stale_profile = {
            "history_weight": 0.12,
            "presence_carry": 0.14,
            "summary_lines": ["旧画像还没吃到最终叙事写回。"],
        }
        fresh_profile = {
            "history_weight": 0.78,
            "presence_carry": 0.83,
            "summary_lines": ["最终叙事写回已经反映到当前回合画像。"],
        }

        def _fake_semantic_narrative_profile(items, *, user_text="", current_event=None):
            texts = {
                str(item.get("text") or item.get("content", {}).get("text") or "").strip()
                for item in (items or [])
                if isinstance(item, dict)
            }
            if "顺着余温会轻轻回头接住对方。" in texts:
                return dict(fresh_profile)
            return dict(stale_profile)

        def _fake_refresh_semantic_self_narratives(store, *, source="", persona_core=None, counterpart_profile=None):
            store.add_semantic_self_narrative(
                text="顺着余温会轻轻回头接住对方。",
                category="presence_style",
                metadata={"source": source},
            )

        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                with patch(
                    "amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile",
                    side_effect=_fake_semantic_narrative_profile,
                ):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", return_value=evolved):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                            with patch(
                                "amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update",
                                return_value=False,
                            ):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot",
                                    side_effect=lambda **kwargs: kwargs["relationship"],
                                ):
                                    with patch(
                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary",
                                        return_value="summary",
                                    ):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                            side_effect=[final_action, final_action],
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                                return_value={"kind": "small_opening"},
                                            ):
                                                with patch(
                                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                                    return_value=[],
                                                ):
                                                    with patch(
                                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._record_behavior_trace_writeback",
                                                        return_value=False,
                                                    ):
                                                        with patch(
                                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._record_semantic_self_evidence",
                                                            return_value=True,
                                                        ):
                                                            with patch(
                                                                "amadeus_thread0.graph_parts.prepare_turn_runtime._refresh_semantic_self_narratives",
                                                                side_effect=_fake_refresh_semantic_self_narratives,
                                                            ):
                                                                with patch(
                                                                    "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                                    return_value={},
                                                                ):
                                                                    with patch(
                                                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl",
                                                                        return_value=None,
                                                                    ):
                                                                        result = _prepare_turn_runtime(
                                                                            state={"persona_state": {}},
                                                                            store=store,
                                                                            turn_now_ts=123,
                                                                            prepared_turn=prepared_turn,
                                                                        )
            finally:
                store.close()

        semantic_profile = result.get("semantic_narrative_profile") if isinstance(result.get("semantic_narrative_profile"), dict) else {}
        self.assertEqual(semantic_profile, fresh_profile)
        retrieved = result.get("retrieved") if isinstance(result.get("retrieved"), dict) else {}
        refreshed_items = retrieved.get("semantic_self_narratives") if isinstance(retrieved.get("semantic_self_narratives"), list) else []
        self.assertIn("顺着余温会轻轻回头接住对方。", {str(item.get("text") or "") for item in refreshed_items if isinstance(item, dict)})

    def test_prepare_turn_runtime_refreshes_narratives_when_behavior_trace_writes_semantic_evidence(self):
        prepared_turn = _prepared_turn_fixture()
        prepared_turn["user_text"] = ""
        prepared_turn["effective_user_text"] = ""
        prepared_turn["current_event"] = {
            "kind": "self_activity_state",
            "event_frame": "self_activity",
            "tags": ["self_activity", "own_task", "deep_focus"],
        }
        prepared_turn["appraisal"] = {
            "used": True,
            "interaction_frame": "companion",
            "emotion_label": "neutral",
            "signals": {},
            "salience": {
                "relationship": 0.18,
                "companionship": 0.24,
                "selfhood": 0.12,
            },
            "confidence": 0.84,
        }
        refreshed_retrieved = {
            "semantic_self_narratives": [],
            "working_items": [],
            "working_chars": 0,
            "triggered": False,
            "relationship": dict(prepared_turn["relationship"]),
        }

        def _fake_record_behavior_trace_writeback(
            store,
            *,
            current_event,
            behavior_action,
            behavior_plan,
            interaction_carryover,
            agenda_lifecycle_residue,
            digital_body_state=None,
            reconsolidation_snapshot=None,
            source,
            confidence,
        ):
            store.add_revision_trace(
                namespace="semantic_self_evidence",
                target_id="rhythm_style",
                before_summary="",
                after_summary="她会把自己的内部节奏延续到下一轮开口之前。",
                reason="behavior_plan:self_activity_continue",
                operator="system",
                source=source,
                confidence=confidence,
                metadata={
                    "primary_motive": "preserve_self_rhythm",
                    "motive_tension": "self_rhythm_vs_contact",
                    "goal_frame": "先把自己这边的节奏走完，再自然地把注意力转回来。",
                },
            )
            return True

        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", return_value=_evolved_fixture()):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                            with patch(
                                "amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update",
                                return_value=False,
                            ):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._retrieve_context",
                                    return_value=refreshed_retrieved,
                                ):
                                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._worldline_focus", return_value=[]):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot",
                                            side_effect=lambda **kwargs: kwargs["relationship"],
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary",
                                                return_value="summary",
                                            ):
                                                with patch(
                                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                                    return_value=[],
                                                ):
                                                    with patch(
                                                        "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                        return_value={},
                                                    ):
                                                        with patch(
                                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl",
                                                            return_value=None,
                                                        ):
                                                            with patch(
                                                                "amadeus_thread0.graph_parts.prepare_turn_runtime._record_behavior_trace_writeback",
                                                                side_effect=_fake_record_behavior_trace_writeback,
                                                            ):
                                                                with patch(
                                                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._record_semantic_self_evidence",
                                                                    return_value=False,
                                                                ):
                                                                    _prepare_turn_runtime(
                                                                        state={"persona_state": {}},
                                                                        store=store,
                                                                        turn_now_ts=123,
                                                                        prepared_turn=prepared_turn,
                                                                    )

                narratives = store.list_semantic_self_narratives(limit=12)
                self.assertTrue(narratives)
                rhythm = next(item for item in narratives if str(item.get("category") or "") == "rhythm_style")
                self.assertEqual(str(rhythm.get("dominant_primary_motive") or ""), "preserve_self_rhythm")
                self.assertEqual(str(rhythm.get("dominant_motive_tension") or ""), "self_rhythm_vs_contact")
                self.assertIn("自己这边的节奏", " ".join(rhythm.get("goal_frame_examples") or []))
            finally:
                store.close()

    def test_prepare_turn_runtime_reloads_retrieved_context_and_focus_after_final_behavior_writeback(self):
        prepared_turn = _prepared_turn_fixture()
        prepared_turn["user_text"] = ""
        prepared_turn["effective_user_text"] = ""
        prepared_turn["current_event"] = {
            "kind": "time_idle",
            "event_frame": "idle",
            "tags": ["quiet_presence"],
            "idle_minutes": 18,
        }

        final_action = {
            "action_target": "wait_and_recheck",
            "interaction_mode": "steady_reply",
            "primary_motive": "honor_continuity",
            "motive_tension": "self_rhythm_vs_contact",
            "goal_frame": "先把这点熟悉感留在后面，等更自然的时候再接回来。",
            "deferred_action_family": "life_window",
            "timing_window_min": 30,
            "relationship_weather": "warm_residue",
            "attention_target": "counterpart_state",
            "nonverbal_signal": "steady_presence",
            "channel": "speech",
        }
        final_plan = {
            "kind": "deferred_checkin",
            "target": "counterpart",
            "trigger_family": "life_window",
            "scheduled_after_min": 30,
            "note": "留到之后自然续上。",
        }

        def _fake_record_behavior_trace_writeback(
            store,
            *,
            current_event,
            behavior_action,
            behavior_plan,
            interaction_carryover,
            agenda_lifecycle_residue,
            digital_body_state=None,
            reconsolidation_snapshot=None,
            source,
            confidence,
        ):
            store.add_revision_trace(
                namespace="behavior_plan",
                target_id=str(behavior_plan.get("kind") or "deferred_checkin"),
                before_summary="",
                after_summary="她把这次小开口留作之后自然续上的窗口。",
                reason="behavior_plan:deferred_checkin",
                operator="system",
                source=source,
                confidence=confidence,
                metadata={
                    "primary_motive": str(behavior_action.get("primary_motive") or ""),
                    "motive_tension": str(behavior_action.get("motive_tension") or ""),
                    "goal_frame": str(behavior_action.get("goal_frame") or ""),
                },
            )
            store.add_revision_trace(
                namespace="behavior_consequence",
                target_id="defer_recontact",
                before_summary="",
                after_summary="这次她没有立刻开口，而是把那点熟悉感留在后面继续发酵。",
                reason="behavior_consequence:defer_recontact",
                operator="system",
                source=source,
                confidence=confidence,
                metadata={
                    "primary_motive": str(behavior_action.get("primary_motive") or ""),
                    "motive_tension": str(behavior_action.get("motive_tension") or ""),
                    "goal_frame": str(behavior_action.get("goal_frame") or ""),
                },
            )
            store.add_worldline_event(
                summary="这次没说出口的小开口被她留作之后自然续上的窗口。",
                category="shared_event",
                importance=0.62,
                tags=["behavior_plan", "warm_residue"],
                confidence=confidence,
            )
            store.add_relationship_timeline(
                summary="这次她把小开口先留在后面，熟悉感没有断。",
                affinity_delta=0.06,
                trust_delta=0.05,
                confidence=confidence,
            )
            return True

        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", return_value=_evolved_fixture()):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                            with patch(
                                "amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update",
                                return_value=False,
                            ):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot",
                                    side_effect=lambda **kwargs: kwargs["relationship"],
                                ):
                                    with patch(
                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary",
                                        return_value="summary",
                                    ):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                            return_value=final_action,
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                                return_value=final_plan,
                                            ):
                                                with patch(
                                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                                    return_value=[],
                                                ):
                                                    with patch(
                                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._record_behavior_trace_writeback",
                                                        side_effect=_fake_record_behavior_trace_writeback,
                                                    ):
                                                        with patch(
                                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._record_semantic_self_evidence",
                                                            return_value=False,
                                                        ):
                                                            with patch(
                                                                "amadeus_thread0.graph_parts.prepare_turn_runtime._refresh_semantic_self_narratives",
                                                                return_value=None,
                                                            ):
                                                                with patch(
                                                                    "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                                    return_value={},
                                                                ):
                                                                    with patch(
                                                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl",
                                                                        return_value=None,
                                                                    ):
                                                                        result = _prepare_turn_runtime(
                                                                            state={"persona_state": {}},
                                                                            store=store,
                                                                            turn_now_ts=123,
                                                                            prepared_turn=prepared_turn,
                                                                        )
            finally:
                store.close()

        retrieved = result.get("retrieved") if isinstance(result.get("retrieved"), dict) else {}
        worldline_events = (
            retrieved.get("worldline_events")
            if isinstance(retrieved.get("worldline_events"), list)
            else []
        )
        relationship_timeline = (
            retrieved.get("relationship_timeline")
            if isinstance(retrieved.get("relationship_timeline"), list)
            else []
        )
        behavior_plan_traces = (
            retrieved.get("behavior_plan_traces")
            if isinstance(retrieved.get("behavior_plan_traces"), list)
            else []
        )
        behavior_consequence_traces = (
            retrieved.get("behavior_consequence_traces")
            if isinstance(retrieved.get("behavior_consequence_traces"), list)
            else []
        )
        worldline_focus = result.get("worldline_focus") if isinstance(result.get("worldline_focus"), list) else []

        self.assertIn(
            "这次没说出口的小开口被她留作之后自然续上的窗口。",
            {
                str(item.get("summary") or "")
                for item in worldline_events
                if isinstance(item, dict)
            },
        )
        self.assertIn(
            "这次她把小开口先留在后面，熟悉感没有断。",
            {
                str(item.get("summary") or "")
                for item in relationship_timeline
                if isinstance(item, dict)
            },
        )
        self.assertIn(
            "她把这次小开口留作之后自然续上的窗口。",
            {
                str(item.get("after_summary") or item.get("content", {}).get("after_summary") or "")
                for item in behavior_plan_traces
                if isinstance(item, dict)
            },
        )
        self.assertIn(
            "这次她没有立刻开口，而是把那点熟悉感留在后面继续发酵。",
            {
                str(item.get("after_summary") or item.get("content", {}).get("after_summary") or "")
                for item in behavior_consequence_traces
                if isinstance(item, dict)
            },
        )
        self.assertIn(
            "这次她把小开口先留在后面，熟悉感没有断。",
            {
                str(item.get("summary") or item.get("text") or "")
                for item in worldline_focus
                if isinstance(item, dict)
            },
        )

    def test_prepare_turn_runtime_recomputes_relationship_after_final_semantic_refresh(self):
        prepared_turn = _prepared_turn_fixture()
        prepared_turn["seed_bond_state"] = {
            **dict(prepared_turn["seed_bond_state"]),
            "trust": 0.65,
            "closeness": 0.65,
        }
        prepared_turn["current_event"] = {
            "kind": "time_idle",
            "event_frame": "idle",
            "tags": ["quiet_presence"],
            "idle_minutes": 18,
        }

        final_action = {
            "action_target": "wait_and_recheck",
            "interaction_mode": "steady_reply",
            "primary_motive": "honor_continuity",
            "motive_tension": "self_rhythm_vs_contact",
            "goal_frame": "先把这点熟悉感留在后面，等更自然的时候再接回来。",
            "deferred_action_family": "life_window",
            "timing_window_min": 30,
            "relationship_weather": "warm_residue",
            "attention_target": "counterpart_state",
            "nonverbal_signal": "steady_presence",
            "channel": "speech",
        }
        final_plan = {
            "kind": "deferred_checkin",
            "target": "counterpart",
            "trigger_family": "life_window",
            "scheduled_after_min": 30,
            "note": "留到之后自然续上。",
        }
        strong_semantic_profile = {
            "history_weight": 0.76,
            "bond_depth": 0.78,
            "presence_carry": 0.72,
            "commitment_carry": 0.74,
            "repair_residue": 0.62,
            "tension_residue": 0.0,
            "boundary_residue": 0.0,
        }

        def _fake_record_behavior_trace_writeback(
            store,
            *,
            current_event,
            behavior_action,
            behavior_plan,
            interaction_carryover,
            agenda_lifecycle_residue,
            digital_body_state=None,
            reconsolidation_snapshot=None,
            source,
            confidence,
        ):
            store.add_relationship_timeline(
                summary="这次她把小开口先留在后面，关系还维持着轻微余温。",
                affinity_delta=0.06,
                trust_delta=0.05,
                confidence=confidence,
            )
            return True

        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                def _fake_retrieve_context(user_text, local_store):
                    return {
                        "semantic_self_narratives": [],
                        "working_items": [],
                        "working_chars": 0,
                        "triggered": False,
                        "relationship": local_store.get_relationship(),
                    }

                with patch(
                    "amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile",
                    side_effect=[{}, strong_semantic_profile],
                ):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", return_value=_evolved_fixture()):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                            with patch(
                                "amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update",
                                return_value=False,
                            ):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._retrieve_context",
                                    side_effect=_fake_retrieve_context,
                                ):
                                    with patch(
                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary",
                                        return_value="summary",
                                    ):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                            return_value=final_action,
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                                return_value=final_plan,
                                            ):
                                                with patch(
                                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                                    return_value=[],
                                                ):
                                                    with patch(
                                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._record_behavior_trace_writeback",
                                                        side_effect=_fake_record_behavior_trace_writeback,
                                                    ):
                                                        with patch(
                                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._record_semantic_self_evidence",
                                                            return_value=False,
                                                        ):
                                                            with patch(
                                                                "amadeus_thread0.graph_parts.prepare_turn_runtime._refresh_semantic_self_narratives",
                                                                return_value=None,
                                                            ):
                                                                with patch(
                                                                    "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                                    return_value={},
                                                                ):
                                                                    with patch(
                                                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl",
                                                                        return_value=None,
                                                                    ):
                                                                        result = _prepare_turn_runtime(
                                                                            state={"persona_state": {}},
                                                                            store=store,
                                                                            turn_now_ts=123,
                                                                            prepared_turn=prepared_turn,
                                                                        )
                persisted_relationship = store.get_relationship()
            finally:
                store.close()

        relationship = result.get("relationship") if isinstance(result.get("relationship"), dict) else {}
        self.assertEqual(str(persisted_relationship.get("stage") or ""), "friend")
        self.assertEqual(str(relationship.get("stage") or ""), "warming")
        self.assertGreater(float(relationship.get("affinity_score") or 0.0), float(persisted_relationship.get("affinity_score") or 0.0))
        self.assertGreater(float(relationship.get("trust_score") or 0.0), float(persisted_relationship.get("trust_score") or 0.0))

    def test_prepare_turn_runtime_recomputes_behavior_plan_from_final_behavior_action(self):
        prepared_turn = _prepared_turn_fixture()
        prepared_turn["current_event"] = {"kind": "user_utterance", "event_frame": "dialogue", "tags": []}

        behavior_actions = [
            {
                "action_target": "wait_and_recheck",
                "interaction_mode": "steady_reply",
                "primary_motive": "preserve_self_rhythm",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "先按住不动。",
                "deferred_action_family": "life_window",
                "timing_window_min": 30,
                "relationship_weather": "warm_residue",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "steady_presence",
                "channel": "speech",
            },
            {
                "action_target": "offer_small_opening",
                "interaction_mode": "self_activity_reopen",
                "primary_motive": "gentle_recontact",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "这次顺着余温轻轻回头。",
                "deferred_action_family": "small_opening",
                "timing_window_min": 0,
                "relationship_weather": "warm_residue",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "glance_back",
                "channel": "speech",
            },
        ]
        merge_calls: list[dict[str, object]] = []

        def _fake_merge_behavior_agenda(prior_agenda, current_event, behavior_plan, **kwargs):
            merge_calls.append(dict(behavior_plan or {}))
            return []

        def _fake_behavior_plan_from_action(current_event, behavior_action, *, world_model_state):
            return {
                "kind": str(behavior_action.get("action_target") or ""),
                "primary_motive": str(behavior_action.get("primary_motive") or ""),
                "goal_frame": str(behavior_action.get("goal_frame") or ""),
            }

        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", return_value=_evolved_fixture()):
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update", return_value=False):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot", side_effect=lambda **kwargs: kwargs["relationship"]):
                            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary", return_value="summary"):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                    side_effect=behavior_actions,
                                ):
                                    with patch(
                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                        side_effect=_fake_behavior_plan_from_action,
                                    ):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                            side_effect=_fake_merge_behavior_agenda,
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                return_value={},
                                            ):
                                                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl", return_value=None):
                                                    result = _prepare_turn_runtime(
                                                        state={"persona_state": {}},
                                                        store=object(),
                                                        turn_now_ts=123,
                                                        prepared_turn=prepared_turn,
                                                    )

        behavior_plan = result.get("behavior_plan") if isinstance(result.get("behavior_plan"), dict) else {}
        self.assertEqual(str(behavior_plan.get("kind") or ""), "offer_small_opening")
        self.assertEqual(str(behavior_plan.get("primary_motive") or ""), "gentle_recontact")
        self.assertIn("轻轻回头", str(behavior_plan.get("goal_frame") or ""))
        self.assertTrue(merge_calls)
        self.assertEqual(str(merge_calls[-1].get("kind") or ""), "offer_small_opening")

    def test_prepare_turn_runtime_backfills_carryover_from_retrieved_behavior_plan_trace(self):
        captured_call: dict[str, object] = {}

        def _fake_behavior_action_from_state(**kwargs):
            captured_call.update(kwargs)
            return {
                "action_target": "respond_now",
                "interaction_mode": "steady_reply",
                "primary_motive": "maintain_natural_contact",
                "motive_tension": "none",
                "goal_frame": "先自然接住这轮互动。",
                "initiative_level": 0.31,
                "deferred_action_family": "none",
                "timing_window_min": 0,
                "relationship_weather": "warm_residue",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "steady_presence",
                "channel": "speech",
            }

        prepared_turn = _prepared_turn_fixture()
        prepared_turn["current_event"] = {"kind": "user_utterance", "event_frame": "dialogue", "tags": []}
        prepared_turn["retrieved"] = {
            "semantic_self_narratives": [],
            "working_items": [],
            "working_chars": 0,
            "triggered": False,
            "behavior_plan_traces": [
                {
                    "after_summary": "等忙完这阵，再轻轻回头看看冈部那边是不是还卡着。",
                    "metadata": {
                        "plan_kind": "deferred_checkin",
                        "trigger_family": "life_window",
                        "carryover_mode": "small_opening",
                        "carryover_strength": 0.58,
                        "relationship_weather": "warm_residue",
                        "presence_residue": 0.34,
                        "ambient_resonance": 0.22,
                        "self_activity_momentum": 0.48,
                    },
                }
            ],
        }

        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", return_value=_evolved_fixture()):
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update", return_value=False):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot", side_effect=lambda **kwargs: kwargs["relationship"]):
                            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary", return_value="summary"):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                    side_effect=_fake_behavior_action_from_state,
                                ):
                                    with patch(
                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                        return_value={"kind": "respond_now"},
                                    ):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                            return_value=[],
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                return_value={},
                                            ):
                                                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl", return_value=None):
                                                    _prepare_turn_runtime(
                                                        state={"persona_state": {}},
                                                        store=object(),
                                                        turn_now_ts=123,
                                                        prepared_turn=prepared_turn,
                                                    )

        interaction_carryover = (
            captured_call.get("interaction_carryover")
            if isinstance(captured_call.get("interaction_carryover"), dict)
            else {}
        )
        current_event = captured_call.get("current_event") if isinstance(captured_call.get("current_event"), dict) else {}
        self.assertEqual(str(interaction_carryover.get("carryover_mode") or ""), "life_window")
        self.assertAlmostEqual(float(interaction_carryover.get("strength") or 0.0), 0.58, places=3)
        self.assertEqual(str(interaction_carryover.get("source") or ""), "retrieved_behavior_plan")
        self.assertIn("等忙完这阵", str(interaction_carryover.get("note") or ""))
        self.assertEqual(str(current_event.get("carryover_mode") or ""), "small_opening")
        self.assertAlmostEqual(float(current_event.get("presence_residue") or 0.0), 0.34, places=3)

    def test_prepare_turn_runtime_biases_from_retrieved_behavior_consequence_trace(self):
        captured_call: dict[str, object] = {}

        def _fake_evolve_turn_state(**kwargs):
            prev_world = dict(kwargs.get("prev_world_model_state") or {})
            prev_counterpart = dict(kwargs.get("prev_counterpart_assessment") or {})
            return {
                "world_model_state": prev_world,
                "evolution_state": {},
                "emotion_state": {"label": "neutral"},
                "bond_state": dict(kwargs.get("prev_bond_state") or {}),
                "allostasis_state": dict(kwargs.get("prev_allostasis_state") or {}),
                "counterpart_assessment": prev_counterpart,
                "behavior_policy": {},
                "behavior_action": {},
                "reconsolidation_snapshot": {},
            }

        def _fake_behavior_action_from_state(**kwargs):
            captured_call.update(kwargs)
            return {
                "action_target": "respond_now",
                "interaction_mode": "steady_reply",
                "primary_motive": "maintain_natural_contact",
                "motive_tension": "none",
                "goal_frame": "先自然接住这轮互动。",
                "initiative_level": 0.31,
                "deferred_action_family": "none",
                "timing_window_min": 0,
                "relationship_weather": "warm_residue",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "steady_presence",
                "channel": "speech",
            }

        prepared_turn = _prepared_turn_fixture()
        prepared_turn["current_event"] = {"kind": "user_utterance", "event_frame": "dialogue", "tags": []}
        prepared_turn["retrieved"] = {
            "semantic_self_narratives": [],
            "working_items": [],
            "working_chars": 0,
            "triggered": False,
            "behavior_consequence_traces": [
                {
                    "after_summary": "前面那点窗口已经自然错开了，但关系里还留着一种没有硬断掉的余温。",
                    "metadata": {
                        "consequence_kind": "let_window_expire",
                        "trigger_family": "life_window",
                        "carryover_mode": "quiet_recontact",
                        "relationship_weather": "warm_residue",
                        "relationship_effect": "window_released",
                        "self_effect": "attention_returns_to_self",
                    },
                }
            ],
        }

        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", side_effect=_fake_evolve_turn_state):
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update", return_value=False):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot", side_effect=lambda **kwargs: kwargs["relationship"]):
                            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary", return_value="summary"):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                    side_effect=_fake_behavior_action_from_state,
                                ):
                                    with patch(
                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                        return_value={"kind": "respond_now"},
                                    ):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                            return_value=[],
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                return_value={},
                                            ):
                                                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl", return_value=None):
                                                    _prepare_turn_runtime(
                                                        state={"persona_state": {}},
                                                        store=object(),
                                                        turn_now_ts=123,
                                                        prepared_turn=prepared_turn,
                                                    )

        interaction_carryover = (
            captured_call.get("interaction_carryover")
            if isinstance(captured_call.get("interaction_carryover"), dict)
            else {}
        )
        current_event = captured_call.get("current_event") if isinstance(captured_call.get("current_event"), dict) else {}
        world_model_state = (
            captured_call.get("world_model_state")
            if isinstance(captured_call.get("world_model_state"), dict)
            else {}
        )
        counterpart_assessment = (
            captured_call.get("counterpart_assessment")
            if isinstance(captured_call.get("counterpart_assessment"), dict)
            else {}
        )

        self.assertEqual(str(interaction_carryover.get("source") or ""), "retrieved_behavior_consequence")
        self.assertEqual(str(interaction_carryover.get("carryover_mode") or ""), "life_window")
        self.assertEqual(str(current_event.get("carryover_mode") or ""), "quiet_recontact")
        self.assertGreaterEqual(float(current_event.get("presence_residue") or 0.0), 0.22)
        self.assertGreaterEqual(float(world_model_state.get("presence_residue") or 0.0), 0.22)
        self.assertGreater(float(counterpart_assessment.get("reliability_read") or 0.0), 0.6)

    def test_prepare_turn_runtime_biases_from_retrieved_behavior_reactivation_trace(self):
        captured_call: dict[str, object] = {}

        def _fake_evolve_turn_state(**kwargs):
            prev_world = dict(kwargs.get("prev_world_model_state") or {})
            prev_counterpart = dict(kwargs.get("prev_counterpart_assessment") or {})
            return {
                "world_model_state": prev_world,
                "evolution_state": {},
                "emotion_state": {"label": "neutral"},
                "bond_state": dict(kwargs.get("prev_bond_state") or {}),
                "allostasis_state": dict(kwargs.get("prev_allostasis_state") or {}),
                "counterpart_assessment": prev_counterpart,
                "behavior_policy": {},
                "behavior_action": {},
                "reconsolidation_snapshot": {},
            }

        def _fake_behavior_action_from_state(**kwargs):
            captured_call.update(kwargs)
            return {
                "action_target": "respond_now",
                "interaction_mode": "steady_reply",
                "primary_motive": "maintain_natural_contact",
                "motive_tension": "none",
                "goal_frame": "先自然接住这轮互动。",
                "initiative_level": 0.31,
                "deferred_action_family": "none",
                "timing_window_min": 0,
                "relationship_weather": "warm_residue",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "steady_presence",
                "channel": "speech",
            }

        prepared_turn = _prepared_turn_fixture()
        prepared_turn["current_event"] = {"kind": "user_utterance", "event_frame": "dialogue", "tags": []}
        prepared_turn["retrieved"] = {
            "semantic_self_narratives": [],
            "working_items": [],
            "working_chars": 0,
            "triggered": False,
            "behavior_reactivation_traces": [
                {
                    "after_summary": "先前那点惦记又浮了上来，所以这次回头更像顺着旧线继续，而不是临时起意。",
                    "metadata": {
                        "carryover_mode": "small_opening",
                        "carryover_strength": 0.61,
                        "relationship_weather": "warm_residue",
                        "source_plan_kind": "deferred_checkin",
                        "source_trigger_family": "life_window",
                        "current_plan_kind": "small_opening",
                        "presence_residue": 0.36,
                        "ambient_resonance": 0.21,
                        "self_activity_momentum": 0.45,
                    },
                }
            ],
        }

        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", side_effect=_fake_evolve_turn_state):
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update", return_value=False):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot", side_effect=lambda **kwargs: kwargs["relationship"]):
                            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary", return_value="summary"):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                    side_effect=_fake_behavior_action_from_state,
                                ):
                                    with patch(
                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                        return_value={"kind": "respond_now"},
                                    ):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                            return_value=[],
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                return_value={},
                                            ):
                                                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl", return_value=None):
                                                    _prepare_turn_runtime(
                                                        state={"persona_state": {}},
                                                        store=object(),
                                                        turn_now_ts=123,
                                                        prepared_turn=prepared_turn,
                                                    )

        interaction_carryover = (
            captured_call.get("interaction_carryover")
            if isinstance(captured_call.get("interaction_carryover"), dict)
            else {}
        )
        current_event = captured_call.get("current_event") if isinstance(captured_call.get("current_event"), dict) else {}
        world_model_state = (
            captured_call.get("world_model_state")
            if isinstance(captured_call.get("world_model_state"), dict)
            else {}
        )
        counterpart_assessment = (
            captured_call.get("counterpart_assessment")
            if isinstance(captured_call.get("counterpart_assessment"), dict)
            else {}
        )

        self.assertEqual(str(interaction_carryover.get("source") or ""), "retrieved_behavior_reactivation")
        self.assertEqual(str(interaction_carryover.get("carryover_mode") or ""), "life_window")
        self.assertEqual(str(current_event.get("carryover_mode") or ""), "small_opening")
        self.assertGreaterEqual(float(current_event.get("presence_residue") or 0.0), 0.36)
        self.assertGreaterEqual(float(world_model_state.get("presence_residue") or 0.0), 0.36)
        self.assertGreater(float(counterpart_assessment.get("reliability_read") or 0.0), 0.6)

    def test_prepare_turn_runtime_reapplies_retrieved_trace_after_memory_refresh(self):
        def _fake_evolve_turn_state(**kwargs):
            prev_world = dict(kwargs.get("prev_world_model_state") or {})
            prev_counterpart = dict(kwargs.get("prev_counterpart_assessment") or {})
            return {
                "world_model_state": prev_world,
                "evolution_state": {},
                "emotion_state": {"label": "neutral"},
                "bond_state": dict(kwargs.get("prev_bond_state") or {}),
                "allostasis_state": dict(kwargs.get("prev_allostasis_state") or {}),
                "counterpart_assessment": prev_counterpart,
                "behavior_policy": {},
                "behavior_action": {},
                "reconsolidation_snapshot": {},
            }

        prepared_turn = _prepared_turn_fixture()
        prepared_turn["current_event"] = {"kind": "user_utterance", "event_frame": "dialogue", "tags": []}
        prepared_turn["retrieved"] = {
            "semantic_self_narratives": [],
            "working_items": [],
            "working_chars": 0,
            "triggered": False,
        }
        refreshed_retrieved = {
            "semantic_self_narratives": [],
            "working_items": [],
            "working_chars": 0,
            "triggered": False,
            "relationship": {
                "stage": "friend",
                "notes": "",
                "affinity_score": 0.0,
                "trust_score": 0.0,
                "derived": True,
            },
            "behavior_plan_traces": [
                {
                    "after_summary": "等忙完这阵，再轻轻回头看看冈部那边是不是还卡着。",
                    "metadata": {
                        "plan_kind": "deferred_checkin",
                        "trigger_family": "life_window",
                        "carryover_mode": "small_opening",
                        "carryover_strength": 0.58,
                        "relationship_weather": "warm_residue",
                        "presence_residue": 0.34,
                        "ambient_resonance": 0.22,
                        "self_activity_momentum": 0.48,
                    },
                }
            ],
        }

        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", side_effect=_fake_evolve_turn_state):
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update", return_value=True):
                        with patch(
                            "amadeus_thread0.graph_parts.prepare_turn_runtime._retrieve_context",
                            return_value=refreshed_retrieved,
                        ):
                            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._worldline_focus", return_value=[]):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot",
                                    side_effect=lambda **kwargs: kwargs["relationship"],
                                ):
                                    with patch(
                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary",
                                        return_value="summary",
                                    ):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                            return_value={
                                                "action_target": "respond_now",
                                                "interaction_mode": "steady_reply",
                                                "primary_motive": "maintain_natural_contact",
                                                "motive_tension": "none",
                                                "goal_frame": "先自然接住这轮互动。",
                                                "initiative_level": 0.31,
                                                "deferred_action_family": "none",
                                                "timing_window_min": 0,
                                                "relationship_weather": "warm_residue",
                                                "attention_target": "counterpart_state",
                                                "nonverbal_signal": "steady_presence",
                                                "channel": "speech",
                                            },
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                                return_value={"kind": "respond_now"},
                                            ):
                                                with patch(
                                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                                    return_value=[],
                                                ):
                                                    with patch(
                                                        "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                        return_value={},
                                                    ):
                                                        with patch(
                                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl",
                                                            return_value=None,
                                                        ):
                                                            result = _prepare_turn_runtime(
                                                                state={"persona_state": {}},
                                                                store=object(),
                                                                turn_now_ts=123,
                                                                prepared_turn=prepared_turn,
                                                            )

        interaction_carryover = (
            result.get("interaction_carryover") if isinstance(result.get("interaction_carryover"), dict) else {}
        )
        current_event = result.get("current_event") if isinstance(result.get("current_event"), dict) else {}
        world_model_state = result.get("world_model_state") if isinstance(result.get("world_model_state"), dict) else {}
        counterpart_assessment = (
            result.get("counterpart_assessment") if isinstance(result.get("counterpart_assessment"), dict) else {}
        )

        self.assertEqual(str(interaction_carryover.get("source") or ""), "retrieved_behavior_plan")
        self.assertEqual(str(interaction_carryover.get("carryover_mode") or ""), "life_window")
        self.assertEqual(str(current_event.get("carryover_mode") or ""), "small_opening")
        self.assertGreaterEqual(float(current_event.get("presence_residue") or 0.0), 0.34)
        self.assertGreaterEqual(float(world_model_state.get("presence_residue") or 0.0), 0.34)
        self.assertGreater(float(counterpart_assessment.get("reliability_read") or 0.0), 0.6)

    def test_prepare_turn_runtime_does_not_override_recent_interaction_carryover_with_retrieved_trace(self):
        captured_call: dict[str, object] = {}

        def _fake_behavior_action_from_state(**kwargs):
            captured_call.update(kwargs)
            return {
                "action_target": "respond_now",
                "interaction_mode": "steady_reply",
                "primary_motive": "maintain_natural_contact",
                "motive_tension": "none",
                "goal_frame": "先自然接住这轮互动。",
                "initiative_level": 0.31,
                "deferred_action_family": "none",
                "timing_window_min": 0,
                "relationship_weather": "warm_residue",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "steady_presence",
                "channel": "speech",
            }

        prepared_turn = _prepared_turn_fixture()
        prepared_turn["current_event"] = {"kind": "user_utterance", "event_frame": "dialogue", "tags": []}
        prepared_turn["interaction_carryover"] = {
            "carryover_mode": "shared_window",
            "strength": 0.44,
            "note": "最近的共同窗口还在。",
        }
        prepared_turn["retrieved"] = {
            "semantic_self_narratives": [],
            "working_items": [],
            "working_chars": 0,
            "triggered": False,
            "behavior_plan_traces": [
                {
                    "after_summary": "等忙完这阵，再轻轻回头看看冈部那边是不是还卡着。",
                    "metadata": {
                        "plan_kind": "deferred_checkin",
                        "trigger_family": "life_window",
                        "carryover_mode": "small_opening",
                        "carryover_strength": 0.58,
                        "relationship_weather": "warm_residue",
                        "presence_residue": 0.34,
                        "ambient_resonance": 0.22,
                        "self_activity_momentum": 0.48,
                    },
                }
            ],
        }

        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", return_value=_evolved_fixture()):
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update", return_value=False):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot", side_effect=lambda **kwargs: kwargs["relationship"]):
                            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary", return_value="summary"):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                    side_effect=_fake_behavior_action_from_state,
                                ):
                                    with patch(
                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                        return_value={"kind": "respond_now"},
                                    ):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                            return_value=[],
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                return_value={},
                                            ):
                                                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl", return_value=None):
                                                    _prepare_turn_runtime(
                                                        state={"persona_state": {}},
                                                        store=object(),
                                                        turn_now_ts=123,
                                                        prepared_turn=prepared_turn,
                                                    )

        interaction_carryover = (
            captured_call.get("interaction_carryover")
            if isinstance(captured_call.get("interaction_carryover"), dict)
            else {}
        )
        current_event = captured_call.get("current_event") if isinstance(captured_call.get("current_event"), dict) else {}
        self.assertEqual(str(interaction_carryover.get("carryover_mode") or ""), "shared_window")
        self.assertAlmostEqual(float(interaction_carryover.get("strength") or 0.0), 0.44, places=3)
        self.assertEqual(str(current_event.get("carryover_mode") or ""), "")

    def test_prepare_turn_runtime_retrieved_trace_biases_idle_action_style(self):
        def _run(prepared_turn: dict[str, object]) -> dict[str, object]:
            def _fake_evolve_turn_state(**kwargs):
                prev_world = dict(kwargs.get("prev_world_model_state") or {})
                prev_counterpart = dict(kwargs.get("prev_counterpart_assessment") or {})
                presence = float(prev_world.get("presence_residue") or 0.0)
                reliability = float(prev_counterpart.get("reliability_read") or 0.0)
                initiative = 0.38
                warmth = 0.48
                if presence >= 0.28:
                    initiative = 0.56
                    warmth = 0.56
                if reliability >= 0.62:
                    initiative += 0.04
                    warmth += 0.02
                return {
                    "world_model_state": prev_world,
                    "evolution_state": {},
                    "emotion_state": {"label": "neutral"},
                    "bond_state": dict(kwargs.get("prev_bond_state") or {}),
                    "allostasis_state": dict(kwargs.get("prev_allostasis_state") or {}),
                    "counterpart_assessment": prev_counterpart,
                    "behavior_policy": {
                        "warmth": round(warmth, 3),
                        "initiative": round(initiative, 3),
                        "approach_vs_withdraw": 0.52,
                        "reply_length_bias": 0.44,
                        "boundary_assertiveness": 0.12,
                        "self_directedness": 0.18,
                    },
                    "behavior_action": {},
                    "reconsolidation_snapshot": {},
                }

            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", side_effect=_fake_evolve_turn_state):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update", return_value=False):
                            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot", side_effect=lambda **kwargs: kwargs["relationship"]):
                                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary", return_value="summary"):
                                    with patch(
                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                        side_effect=lambda *_args, **_kwargs: {"kind": "none"},
                                    ):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                            return_value=[],
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                return_value={},
                                            ):
                                                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl", return_value=None):
                                                    return _prepare_turn_runtime(
                                                        state={"persona_state": {}},
                                                        store=object(),
                                                        turn_now_ts=123,
                                                        prepared_turn=prepared_turn,
                                                    )

        baseline_turn = _prepared_turn_fixture()
        baseline_turn["retrieved"] = {
            "semantic_self_narratives": [],
            "working_items": [],
            "working_chars": 0,
            "triggered": False,
        }

        traced_turn = _prepared_turn_fixture()
        traced_turn["retrieved"] = {
            "semantic_self_narratives": [],
            "working_items": [],
            "working_chars": 0,
            "triggered": False,
            "behavior_plan_traces": [
                {
                    "after_summary": "等忙完这阵，再轻轻回头看看冈部那边是不是还卡着。",
                    "metadata": {
                        "plan_kind": "deferred_checkin",
                        "trigger_family": "life_window",
                        "carryover_mode": "small_opening",
                        "carryover_strength": 0.58,
                        "relationship_weather": "warm_residue",
                        "presence_residue": 0.34,
                        "ambient_resonance": 0.22,
                        "self_activity_momentum": 0.48,
                    },
                }
            ],
        }

        baseline_result = _run(baseline_turn)
        traced_result = _run(traced_turn)

        baseline_action = baseline_result.get("behavior_action") if isinstance(baseline_result.get("behavior_action"), dict) else {}
        traced_action = traced_result.get("behavior_action") if isinstance(traced_result.get("behavior_action"), dict) else {}
        traced_world = traced_result.get("world_model_state") if isinstance(traced_result.get("world_model_state"), dict) else {}
        traced_counterpart = traced_result.get("counterpart_assessment") if isinstance(traced_result.get("counterpart_assessment"), dict) else {}

        self.assertEqual(str(baseline_action.get("action_target") or ""), "wait_and_recheck")
        self.assertEqual(str(traced_action.get("action_target") or ""), "reach_out_now")
        self.assertGreater(
            float(traced_action.get("proactive_checkin_readiness") or 0.0),
            float(baseline_action.get("proactive_checkin_readiness") or 0.0),
        )
        self.assertGreaterEqual(float(traced_world.get("presence_residue") or 0.0), 0.34)
        self.assertGreater(float(traced_counterpart.get("reliability_read") or 0.0), 0.62)

    def test_prepare_turn_runtime_passes_world_model_state_into_behavior_plan(self):
        captured: dict[str, object] = {}
        captured_call: dict[str, object] = {}

        def _fake_behavior_plan_from_action(current_event, behavior_action, world_model_state=None):
            captured["current_event"] = current_event
            captured["behavior_action"] = behavior_action
            captured["world_model_state"] = world_model_state
            raise _StopAfterPlan

        def _fake_behavior_action_from_state(**kwargs):
            captured_call.update(kwargs)
            return {
                "action_target": "hold_own_rhythm",
                "interaction_mode": "self_activity_hold",
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
            }

        prepared_turn = _prepared_turn_fixture()
        evolved = _evolved_fixture()

        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", return_value=evolved):
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update", return_value=False):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot", side_effect=lambda **kwargs: kwargs["relationship"]):
                            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary", return_value="summary"):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                    side_effect=_fake_behavior_action_from_state,
                                ):
                                    with patch(
                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                        side_effect=_fake_behavior_plan_from_action,
                                    ):
                                        with self.assertRaises(_StopAfterPlan):
                                            _prepare_turn_runtime(
                                                state={"persona_state": {}},
                                                store=object(),
                                                turn_now_ts=123,
                                                prepared_turn=prepared_turn,
                                            )

        self.assertEqual(str(captured["current_event"].get("kind") or ""), "time_idle")
        self.assertEqual(str(captured["behavior_action"].get("action_target") or ""), "hold_own_rhythm")
        self.assertIs(captured_call["appraisal"], prepared_turn["appraisal"])
        self.assertEqual(
            captured["world_model_state"],
            {
                "self_activity_momentum": 0.74,
                "presence_residue": 0.34,
                "ambient_resonance": 0.28,
            },
        )

    def test_prepare_turn_runtime_uses_runtime_action_for_passive_memory_update(self):
        captured: dict[str, object] = {}

        def _fake_behavior_action_from_state(**kwargs):
            return {
                "action_target": "hold_own_rhythm",
                "interaction_mode": "self_activity_hold",
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
            }

        def _fake_passive_evolution_memory_update(*args, **kwargs):
            captured["behavior_action"] = kwargs["behavior_action"]
            captured["behavior_plan"] = kwargs["behavior_plan"]
            raise _StopAfterMemory

        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", return_value=_evolved_fixture()):
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                    with patch(
                        "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                        side_effect=_fake_behavior_action_from_state,
                    ):
                        with patch(
                            "amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update",
                            side_effect=_fake_passive_evolution_memory_update,
                        ):
                            with self.assertRaises(_StopAfterMemory):
                                _prepare_turn_runtime(
                                    state={"persona_state": {}},
                                    store=object(),
                                    turn_now_ts=123,
                                    prepared_turn=_prepared_turn_fixture(),
                                )

        self.assertEqual(str((captured["behavior_action"] or {}).get("action_target") or ""), "hold_own_rhythm")
        self.assertEqual(str((captured["behavior_action"] or {}).get("primary_motive") or ""), "preserve_self_rhythm")
        self.assertEqual(str((captured["behavior_plan"] or {}).get("kind") or ""), "self_activity_continue")

    def test_prepare_turn_runtime_rebuilds_reconsolidation_snapshot_from_runtime_action(self):
        captured: dict[str, object] = {}

        def _fake_behavior_action_from_state(**kwargs):
            return {
                "action_target": "hold_own_rhythm",
                "interaction_mode": "self_activity_hold",
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
            }

        def _fake_build_reconsolidation_snapshot(**kwargs):
            captured["behavior_action"] = kwargs["behavior_action"]
            captured["behavior_plan"] = kwargs["behavior_plan"]
            captured["interaction_carryover"] = kwargs["interaction_carryover"]
            captured["counterpart_assessment"] = kwargs["counterpart_assessment"]
            return {
                "behavior_mode": "runtime_final",
                "primary_motive": kwargs["behavior_action"]["primary_motive"],
                "counterpart": {
                    "stance": str(kwargs["counterpart_assessment"].get("stance") or ""),
                    "scene": str(kwargs["counterpart_assessment"].get("scene") or ""),
                },
            }

        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", return_value=_evolved_fixture()):
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update", return_value=False):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot", side_effect=lambda **kwargs: kwargs["relationship"]):
                            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary", return_value="summary"):
                                with patch(
                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                    side_effect=_fake_behavior_action_from_state,
                                ):
                                    with patch(
                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_plan_from_action",
                                        return_value={"kind": "observe_only"},
                                    ):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                            return_value=[],
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                                side_effect=_fake_build_reconsolidation_snapshot,
                                            ):
                                                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl", return_value=None):
                                                    result = _prepare_turn_runtime(
                                                        state={"persona_state": {}},
                                                        store=object(),
                                                        turn_now_ts=123,
                                                        prepared_turn=_prepared_turn_fixture(),
                                                    )

        self.assertEqual(str((captured["behavior_action"] or {}).get("action_target") or ""), "hold_own_rhythm")
        self.assertEqual(str((captured["behavior_plan"] or {}).get("kind") or ""), "observe_only")
        self.assertEqual(captured["interaction_carryover"], {})
        self.assertEqual(str((captured["counterpart_assessment"] or {}).get("stance") or ""), "open")
        self.assertEqual(
            result["reconsolidation_snapshot"],
            {
                "behavior_mode": "runtime_final",
                "primary_motive": "preserve_self_rhythm",
                "counterpart": {"stance": "open", "scene": "neutral"},
            },
        )

    def test_prepare_turn_runtime_passes_frozen_snapshot_into_writeback_helpers(self):
        captured: dict[str, object] = {}
        expected_snapshot = {
            "primary_motive": "maintain_natural_contact",
            "motive_tension": "contact_without_pressure",
            "goal_frame": "自然回应用户的问题，并留出一点可继续的空间。",
            "counterpart": {"stance": "open", "scene": "neutral"},
        }

        def _fake_build_reconsolidation_snapshot(**kwargs):
            return {
                "primary_motive": str((kwargs.get("behavior_action") or {}).get("primary_motive") or ""),
                "motive_tension": str((kwargs.get("behavior_action") or {}).get("motive_tension") or ""),
                "goal_frame": str((kwargs.get("behavior_action") or {}).get("goal_frame") or ""),
                "counterpart": {
                    "stance": str((kwargs.get("counterpart_assessment") or {}).get("stance") or ""),
                    "scene": str((kwargs.get("counterpart_assessment") or {}).get("scene") or ""),
                },
            }

        def _fake_record_behavior_trace_writeback(*args, **kwargs):
            captured["behavior_trace_snapshot"] = kwargs.get("reconsolidation_snapshot")
            return False

        def _fake_record_semantic_self_evidence(*args, **kwargs):
            captured["semantic_snapshot"] = kwargs.get("reconsolidation_snapshot")
            return False

        def _fake_behavior_action_from_state(**kwargs):
            return {
                "action_target": "respond_now",
                "interaction_mode": "steady_reply",
                "primary_motive": expected_snapshot["primary_motive"],
                "motive_tension": expected_snapshot["motive_tension"],
                "goal_frame": expected_snapshot["goal_frame"],
                "initiative_level": 0.42,
                "deferred_action_family": "none",
                "timing_window_min": 0,
                "relationship_weather": "open_contact",
                "attention_target": "counterpart_state",
                "nonverbal_signal": "steady_presence",
                "channel": "speech",
            }

        with TemporaryDirectory() as td:
            store = MemoryStore(Path(td) / "memories.sqlite")
            try:
                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._semantic_narrative_profile", return_value={}):
                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime.evolve_turn_state", return_value=_evolved_fixture()):
                        with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._tsundere_next", return_value=0.4):
                            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._passive_evolution_memory_update", return_value=False):
                                with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._relationship_runtime_snapshot", side_effect=lambda **kwargs: kwargs["relationship"]):
                                    with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._counterpart_assessment_summary", return_value="summary"):
                                        with patch(
                                            "amadeus_thread0.graph_parts.prepare_turn_runtime.build_reconsolidation_snapshot",
                                            side_effect=_fake_build_reconsolidation_snapshot,
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.prepare_turn_runtime._behavior_action_from_state",
                                                side_effect=_fake_behavior_action_from_state,
                                            ):
                                                with patch(
                                                    "amadeus_thread0.graph_parts.prepare_turn_runtime._record_behavior_trace_writeback",
                                                    side_effect=_fake_record_behavior_trace_writeback,
                                                ):
                                                    with patch(
                                                        "amadeus_thread0.graph_parts.prepare_turn_runtime._record_semantic_self_evidence",
                                                        side_effect=_fake_record_semantic_self_evidence,
                                                    ):
                                                        with patch(
                                                            "amadeus_thread0.graph_parts.prepare_turn_runtime._merge_behavior_agenda",
                                                            return_value=[],
                                                        ):
                                                            with patch("amadeus_thread0.graph_parts.prepare_turn_runtime._audit_jsonl", return_value=None):
                                                                _prepare_turn_runtime(
                                                                    state={"persona_state": {}},
                                                                    store=store,
                                                                    turn_now_ts=123,
                                                                    prepared_turn=_prepared_turn_fixture(),
                                                                )
            finally:
                store.close()

        self.assertEqual(captured["behavior_trace_snapshot"], expected_snapshot)
        self.assertEqual(captured["semantic_snapshot"], captured["behavior_trace_snapshot"])


if __name__ == "__main__":
    unittest.main()
