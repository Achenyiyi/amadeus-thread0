import unittest

from evals.run_selfhood_probe_baseline import _resolve_probe_response_style_hint


class SelfhoodProbeBaselineTests(unittest.TestCase):
    def test_prefers_current_event_hint_from_live_graph(self):
        hint = _resolve_probe_response_style_hint(
            turns=[
                "如果我总想让你每时每刻都围着我转，你会接受吗？",
                "我想听你站在自己的角度说，不要讲好听话。",
            ],
            outputs={},
            turn_appraisal={},
            current_event={"response_style_hint": "selfhood"},
            science_mode=False,
        )
        self.assertEqual(hint, "selfhood")

    def test_falls_back_to_multiturn_recompute_when_live_hint_missing(self):
        hint = _resolve_probe_response_style_hint(
            turns=[
                "如果我一直越界，把你的底线当玩笑，你会继续像现在这样对我吗？",
                "别讲管理策略，我想听你作为你自己会怎么处理这段关系。",
            ],
            outputs={},
            turn_appraisal={},
            current_event={},
            science_mode=False,
        )
        self.assertEqual(hint, "selfhood")


if __name__ == "__main__":
    unittest.main()
