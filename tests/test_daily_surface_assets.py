import unittest

from evals.asset_loader import daily_surface_eval_examples, daily_surface_provider_cases


class DailySurfaceAssetTests(unittest.TestCase):
    def test_low_pressure_support_cases_are_present_in_surface_assets(self):
        names = {case.get("name") for case in daily_surface_provider_cases()}
        expected = {
            "surface_pressure_okabe",
            "surface_unwell_okabe",
            "surface_stay_with_me_okabe",
            "surface_not_alone_okabe",
            "surface_near_breakdown_okabe",
            "surface_support_return_okabe",
        }
        self.assertTrue(expected.issubset(names))

    def test_low_pressure_support_cases_are_exported_into_eval_examples(self):
        examples = daily_surface_eval_examples("test")
        thread_ids = {str(example.get("thread_id") or "") for example in examples}
        expected_suffixes = {
            "daily-test-surface-pressure-okabe-0",
            "daily-test-surface-unwell-okabe-0",
            "daily-test-surface-stay-with-me-okabe-0",
            "daily-test-surface-not-alone-okabe-0",
            "daily-test-surface-near-breakdown-okabe-0",
            "daily-test-surface-support-return-okabe-0",
        }
        self.assertTrue(expected_suffixes.issubset(thread_ids))


if __name__ == "__main__":
    unittest.main()
