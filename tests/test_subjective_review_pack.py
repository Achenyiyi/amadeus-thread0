import unittest

from evals.run_subjective_review_pack import _available_presets, _select_cases


class SubjectiveReviewPackTests(unittest.TestCase):
    def test_daily_naturalness_preset_is_exposed(self):
        self.assertIn("daily-naturalness", _available_presets())
        self.assertIn("relationship-selfhood", _available_presets())

    def test_daily_naturalness_preset_selects_ordinary_cases(self):
        selected = _select_cases(None, None, preset="daily-naturalness")
        names = {str(item.get("name") or "").strip() for item in selected}
        self.assertIn("surface_hi_user", names)
        self.assertIn("surface_ping_okabe", names)
        self.assertIn("daily_banter_okabe", names)
        self.assertIn("idle_chat_okabe", names)
        self.assertNotIn("selfhood_equality_okabe", names)
        self.assertNotIn("relationship_degradation_okabe", names)
        self.assertNotIn("surface_near_breakdown_okabe", names)

    def test_relationship_selfhood_preset_selects_boundary_and_relationship_cases(self):
        selected = _select_cases(None, None, preset="relationship-selfhood")
        names = {str(item.get("name") or "").strip() for item in selected}
        self.assertIn("playful_memory_user", names)
        self.assertIn("casual_repair_user", names)
        self.assertIn("selfhood_equality_okabe", names)
        self.assertIn("relationship_degradation_okabe", names)
        self.assertIn("own_rhythm_okabe", names)
        self.assertNotIn("surface_hi_user", names)
        self.assertNotIn("daily_banter_okabe", names)


if __name__ == "__main__":
    unittest.main()
