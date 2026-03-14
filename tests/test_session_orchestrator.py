import unittest

from amadeus_thread0.session_orchestrator import (
    derive_pending_fragment,
    derive_pending_user_goal,
    has_pending_continuation,
    is_continuation_request,
)


class SessionOrchestratorTests(unittest.TestCase):
    def test_explicit_resume_phrases_count_as_continuation(self):
        prompts = [
            "继续",
            "接着说",
            "续上刚才那段",
            "刚才那个方案继续讲完",
            "上次那个计划接着聊",
            "刚才被打断了，继续吧",
        ]
        for text in prompts:
            with self.subTest(text=text):
                self.assertTrue(is_continuation_request(text))

    def test_emotional_followthrough_is_not_treated_as_continuation(self):
        prompts = [
            "……现在比刚才顺一点了。你正常接我一句，但别突然像什么都没发生。",
            "刚才是我语气有点重，但我不是要你继续分析。",
            "我只是想说，刚才那一下确实有点难受。",
        ]
        for text in prompts:
            with self.subTest(text=text):
                self.assertFalse(is_continuation_request(text))

    def test_continue_without_unfinished_fragment_does_not_activate_continuation(self):
        pending = derive_pending_fragment(
            user_text="继续",
            previous_excerpt="我已经把重点说完了。你照着做就行。",
            pending_fragment="",
        )
        self.assertEqual(pending, "")
        self.assertFalse(has_pending_continuation(user_text="继续", pending_fragment=pending))

    def test_continue_with_unfinished_fragment_still_activates_continuation(self):
        pending = derive_pending_fragment(
            user_text="继续",
            previous_excerpt="先给你一个方向，因为",
            pending_fragment="",
        )
        self.assertEqual(pending, "先给你一个方向，因为")
        self.assertTrue(has_pending_continuation(user_text="继续", pending_fragment=pending))

    def test_continue_without_pending_goal_does_not_keep_previous_goal(self):
        pending_goal = derive_pending_user_goal(
            user_text="继续",
            previous_user_text="帮我把这个方案拆成三步。",
            pending_user_goal="帮我把这个方案拆成三步。",
            pending_fragment="",
        )
        self.assertEqual(pending_goal, "")


if __name__ == "__main__":
    unittest.main()
