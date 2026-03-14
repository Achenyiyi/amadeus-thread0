import unittest

from amadeus_thread0.graph import (
    _daily_surface_profile,
    _is_light_free_dialog_turn,
    _looks_like_daily_surface_scene,
)


class DailySurfaceGatingTests(unittest.TestCase):
    def test_support_scenes_count_as_daily_surface(self):
        prompts = [
            "今天压力有点大",
            "我现在有点难受",
            "能陪我一会儿吗",
            "我不想一个人待着",
            "刚刚差点又崩溃了",
        ]
        for text in prompts:
            with self.subTest(text=text):
                self.assertTrue(_looks_like_daily_surface_scene(text, science_mode=False))

    def test_light_free_dialog_accepts_low_pressure_support_scenes(self):
        prompts = [
            "今天压力有点大",
            "我现在有点难受",
            "能陪我一会儿吗",
            "我不想一个人待着",
            "刚刚差点又崩溃了",
        ]
        for text in prompts:
            with self.subTest(text=text):
                self.assertTrue(
                    _is_light_free_dialog_turn(
                        user_text=text,
                        response_style_hint="companion",
                        science_mode=False,
                        continuation_mode=False,
                        current_event_kind="user_utterance",
                    )
                )

    def test_daily_surface_profile_hits_new_support_cases(self):
        expectations = {
            "今天压力有点大": "surface_pressure_okabe",
            "我现在有点难受": "surface_unwell_okabe",
            "能陪我一会儿吗": "surface_stay_with_me_okabe",
            "我不想一个人待着": "surface_not_alone_okabe",
            "刚刚差点又崩溃了": "surface_near_breakdown_okabe",
            "……现在比刚才顺一点了。你正常接我一句，但别突然像什么都没发生。": "surface_support_return_okabe",
        }
        for text, case_name in expectations.items():
            with self.subTest(text=text):
                profile = _daily_surface_profile(text, science_mode=False)
                self.assertEqual(str(profile.get("case_name") or ""), case_name)
                self.assertGreaterEqual(float(profile.get("score") or 0.0), 0.5)


if __name__ == "__main__":
    unittest.main()
