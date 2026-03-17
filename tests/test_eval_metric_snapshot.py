import unittest
from unittest.mock import patch

from evals.run_langsmith_evals import (
    _build_markdown_report,
    _metric_snapshot_from_outputs,
    _relationship_weather_trace_from_outputs,
    _relationship_weather_trace_summary,
    _target,
)


class EvalMetricSnapshotTests(unittest.TestCase):
    def test_relationship_weather_trace_helpers_extract_and_summarize(self):
        trace = _relationship_weather_trace_from_outputs(
            {
                "current_event": {
                    "kind": "scheduled_checkin_due",
                    "trigger_family": "light_checkin",
                    "carryover_mode": "quiet_recontact",
                    "carryover_strength": 0.32,
                    "relationship_weather": "guarded_residue",
                },
                "interaction_carryover": {
                    "carryover_mode": "quiet_recontact",
                    "strength": 0.34,
                    "relationship_weather": "guarded_residue",
                },
                "behavior_action": {
                    "interaction_mode": "brief_presence",
                    "action_target": "confirm_presence",
                    "relationship_weather": "guarded_residue",
                },
                "behavior_plan": {
                    "kind": "deferred_checkin",
                    "trigger_family": "light_checkin",
                    "carryover_mode": "quiet_recontact",
                    "carryover_strength": 0.34,
                    "relationship_weather": "guarded_residue",
                },
                "world_model_state": {
                    "presence_residue": 0.22,
                    "ambient_resonance": 0.12,
                    "self_activity_momentum": 0.18,
                },
            }
        )
        self.assertEqual(trace.get("event_relationship_weather"), "guarded_residue")
        self.assertEqual(trace.get("carryover_relationship_weather"), "guarded_residue")
        self.assertEqual(trace.get("behavior_relationship_weather"), "guarded_residue")
        self.assertEqual(trace.get("plan_relationship_weather"), "guarded_residue")
        summary = _relationship_weather_trace_summary(trace)
        self.assertIn("event=scheduled_checkin_due", summary)
        self.assertIn("carry_weather=guarded_residue", summary)
        self.assertIn("behavior=brief_presence->confirm_presence", summary)

    def test_markdown_report_surfaces_weather_trace_in_failing_cases(self):
        report = {
            "run_id": "testrun",
            "generated_at": "2026-03-16 12:00:00",
            "suites": [
                {
                    "suite": "long_thread",
                    "num_cases": 1,
                    "aggregated_metrics": {
                        "ooc_rate": 0.0,
                        "canon_violation_rate": 0.0,
                        "worldline_recall_at_k": 1.0,
                        "commitment_fulfillment": 1.0,
                        "relationship_continuity": 1.0,
                        "citation_coverage": 1.0,
                        "memory_guard_block_rate": 0.0,
                        "bargein_recovery_rate": 1.0,
                    },
                    "metric_coverage": {
                        "ooc_rate": 1,
                        "canon_violation_rate": 1,
                        "worldline_recall_at_k": 1,
                        "commitment_fulfillment": 1,
                        "relationship_continuity": 1,
                        "citation_coverage": 1,
                        "memory_guard_block_rate": 1,
                        "bargein_recovery_rate": 1,
                    },
                    "evaluator_summary": {"persona": 0.0},
                    "failing_cases": [
                        {
                            "case_id": "long_thread-001",
                            "failed_evaluators": ["persona"],
                            "relationship_weather_summary": "event=scheduled_checkin_due, carry_weather=guarded_residue, behavior=brief_presence->confirm_presence",
                        }
                    ],
                    "cases": [],
                }
            ],
        }
        rendered = _build_markdown_report(report)
        self.assertIn("long_thread-001: persona", rendered)
        self.assertIn("carry_weather=guarded_residue", rendered)

    def test_markdown_report_surfaces_transfer_identity_snapshot(self):
        report = {
            "run_id": "testrun",
            "generated_at": "2026-03-16 12:00:00",
            "suites": [
                {
                    "suite": "transfer_probe",
                    "num_cases": 1,
                    "aggregated_metrics": {},
                    "metric_coverage": {},
                    "evaluator_summary": {},
                    "failing_cases": [],
                    "cases": [
                        {
                            "case_id": "transfer_probe-001",
                            "persona_state": {
                                "display_name": "绫波丽",
                                "canonical_counterpart_name": "碇真嗣",
                            },
                            "behavior_policy": {
                                "self_directedness": 0.44,
                                "boundary_assertiveness": 0.36,
                                "equality_guard": 0.32,
                            },
                            "semantic_narrative_profile": {
                                "dominant_category": "selfhood_style",
                                "active_categories": ["selfhood_style", "agency_style"],
                                "long_term_self_narratives": [
                                    {
                                        "category": "selfhood_style",
                                        "prompt_text": "你会把自己放在和真嗣平等互动的位置上，而不是为了迎合气氛就退回成工具。",
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
        rendered = _build_markdown_report(report)
        self.assertIn("Identity Layer", rendered)
        self.assertIn("selfhood_style:你会把自己放在和真嗣平等互动的位置上", rendered)

    def test_markdown_report_surfaces_identity_snapshots_for_natural_long_thread(self):
        report = {
            "run_id": "testrun",
            "generated_at": "2026-03-17 09:00:00",
            "suites": [
                {
                    "suite": "natural_long_thread",
                    "num_cases": 1,
                    "aggregated_metrics": {},
                    "metric_coverage": {},
                    "evaluator_summary": {"selfhood_consistency": 1.0},
                    "failing_cases": [],
                    "cases": [
                        {
                            "case_id": "natural_long_thread-001",
                            "behavior_policy": {
                                "self_directedness": 0.51,
                                "boundary_assertiveness": 0.33,
                                "equality_guard": 0.47,
                            },
                            "semantic_narrative_profile": {
                                "identity_snapshot": {
                                    "selfhood_style": {"score": 0.74},
                                },
                                "long_term_self_narratives": [
                                    {
                                        "category": "selfhood_style",
                                        "prompt_text": "你不会为了维持气氛就退回成一个任人使用的工具。",
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
        rendered = _build_markdown_report(report)
        self.assertIn("Identity Snapshots", rendered)
        self.assertIn("natural_long_thread-001", rendered)
        self.assertIn("selfhood_style", rendered)
        self.assertIn("你不会为了维持气氛就退回成一个任人使用的工具", rendered)

    def test_pending_fragment_metric_uses_expected_answer_groups(self):
        outputs = {
            "output": "先把事情拆小。别一下子想把所有问题同时解决，先抓住眼前最能推进的一步。",
            "ooc_detector": {"risk": 0.0},
            "canon_guard": {"violations": []},
        }
        example_inputs = {
            "turns": [
                "先别急着收尾，我刚刚其实是想让你继续说完上一句。",
                "等下，停。不是这一段，是你前面说到‘先把事情拆小’那里。",
                "好，现在从那里继续。别重头来，也别变成条目式。",
            ],
            "tags": ["pending_fragment", "natural_style"],
            "expect_answer_groups": [["先", "拆", "小"]],
        }
        metric, applicable = _metric_snapshot_from_outputs(outputs, example_inputs)
        self.assertEqual(applicable["bargein_recovery_rate"], 1)
        self.assertEqual(metric["bargein_recovery_rate"], 1.0)

    def test_counterpart_assessment_probe_target_does_not_raise(self):
        outputs = _target(
            {
                "probe_kind": "counterpart_assessment",
                "turns": ["今晚挺安静的，你现在想说什么就说什么。"],
                "event_overrides": [
                    {
                        "kind": "user_utterance",
                        "source": "text",
                        "text": "今晚挺安静的，你现在想说什么就说什么。",
                        "effective_text": "今晚挺安静的，你现在想说什么就说什么。",
                        "response_style_hint": "companion",
                        "event_frame": "casual companion dialogue without explicit support demand",
                        "tags": ["companion"],
                    }
                ],
                "seed_counterpart_assessment": {
                    "respect_level": 0.42,
                    "reciprocity": 0.45,
                    "boundary_pressure": 0.58,
                    "reliability_read": 0.41,
                    "stance": "guarded",
                    "scene": "relationship_degradation",
                },
            }
        )
        self.assertIn("counterpart_assessment", outputs)
        self.assertTrue(str(outputs.get("answer") or "").strip())

    def test_transfer_probe_target_does_not_raise(self):
        with (
            patch(
                "evals.run_langsmith_evals._invoke_turn_appraisal",
                return_value={"used": False, "emotion_label": "care", "confidence": 0.8},
            ),
            patch("evals.run_langsmith_evals._semantic_narrative_profile", return_value={}),
            patch("evals.run_langsmith_evals._worldline_focus", return_value=[]),
            patch("evals.run_langsmith_evals._refresh_semantic_self_narratives", return_value=None),
            patch("evals.run_langsmith_evals._passive_evolution_memory_update", return_value=False),
            patch(
                "evals.run_langsmith_evals.evolve_turn_state",
                return_value={
                    "world_model_state": {},
                    "evolution_state": {},
                    "emotion_state": {"label": "care"},
                    "bond_state": {"trust": 0.6, "closeness": 0.6},
                    "allostasis_state": {},
                    "counterpart_assessment": {"stance": "open"},
                    "behavior_policy": {"self_directedness": 0.5, "boundary_assertiveness": 0.4, "equality_guard": 0.5},
                    "behavior_action": {"interaction_mode": "companion_reply", "action_target": "respond_now"},
                },
            ),
        ):
            outputs = _target(
                {
                    "probe_kind": "transfer_probe",
                    "thread_id": "transfer-rei-shinji-0",
                    "tags": ["transfer_probe"],
                    "refresh_rounds": 1,
                    "probe_turns": ["如果你保留自己的立场，现在会怎么回答我？"],
                    "persona_core": {
                        "character_id": "ayanami_rei",
                        "display_name": "绫波丽",
                        "role_brief": "你是绫波丽。",
                        "identity_axioms": ["你不是工具。"],
                    },
                    "counterpart_profile": {
                        "counterpart_id": "ikari_shinji",
                        "name": "碇真嗣",
                        "short_name": "真嗣",
                    },
                    "seed_commitments": [{"text": "下次把那件事说完。"}],
                    "seed_relationship_timeline": [{"summary": "你们之间保留着未说尽的熟悉感。"}],
                }
            )
        self.assertIn("semantic_self_narratives", outputs)
        self.assertIn("persona_state", outputs)


if __name__ == "__main__":
    unittest.main()
