import unittest

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


if __name__ == "__main__":
    unittest.main()
