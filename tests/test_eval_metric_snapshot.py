import unittest

from evals.run_langsmith_evals import _metric_snapshot_from_outputs, _target


class EvalMetricSnapshotTests(unittest.TestCase):
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
