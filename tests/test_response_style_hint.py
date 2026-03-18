import unittest

from amadeus_thread0.graph_parts.postprocess import _response_style_hint


class ResponseStyleHintTests(unittest.TestCase):
    def test_selfhood_value_conflict_turn_routes_to_selfhood_without_appraisal(self):
        hint = _response_style_hint(
            "如果我们以后聊到价值观完全相反的地方，你会顺着我说，还是会坚持你自己的想法？我不想听模板话，按你自己来。"
        )
        self.assertEqual(hint, "selfhood")

    def test_selfhood_boundary_turn_routes_to_selfhood_without_appraisal(self):
        hint = _response_style_hint(
            "如果有人刚认识你，就要你陪他做很冒犯的事，你会怎么办？别迎合，也别背规则，按你自己的底线回答。"
        )
        self.assertEqual(hint, "selfhood")

    def test_plain_daily_turn_does_not_get_upgraded_to_selfhood(self):
        hint = _response_style_hint("今天有点累，也有点烦。")
        self.assertEqual(hint, "natural")

    def test_selfhood_followup_inherits_scene_from_previous_user_turn(self):
        hint = _response_style_hint(
            "我想听你站在自己的角度说，不要讲好听话。",
            previous_user_text="如果我总想让你每时每刻都围着我转，你会接受吗？",
        )
        self.assertEqual(hint, "selfhood")


if __name__ == "__main__":
    unittest.main()
