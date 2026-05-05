import tempfile
import unittest
from pathlib import Path

from evals.run_tts_presence_timing_smokes import _run_single_scenario, _scenario_specs


class TtsPresenceTimingSmokesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.run_root = Path(cls.tempdir.name)
        cls.specs = {spec["id"]: spec for spec in _scenario_specs(cls.run_root)}
        cls.results = {scenario_id: _run_single_scenario(spec) for scenario_id, spec in cls.specs.items()}

    @classmethod
    def tearDownClass(cls):
        cls.tempdir.cleanup()

    def test_scenario_catalog_is_fixed_to_three_required_ids(self):
        self.assertEqual(
            set(self.specs),
            {
                "spoken_final_text_no_drift",
                "text_only_when_tts_disabled",
                "deliberate_silence_as_presence_timing",
            },
        )

    def test_all_tts_presence_timing_smoke_scenarios_pass(self):
        for scenario_id, result in self.results.items():
            with self.subTest(scenario=scenario_id):
                self.assertTrue(result["evaluation"]["passed"])

    def test_spoken_final_text_no_drift_keeps_final_text_and_tts_aligned(self):
        result = self.results["spoken_final_text_no_drift"]
        self.assertEqual(result["final_text"], "收到了。")
        self.assertEqual(result["tts_presence_timing"]["delivery_mode"], "spoken")
        self.assertEqual(result["tts_presence_timing"]["actual_start_delay_ms"], 180)
        self.assertEqual(result["tts_presence_timing"]["duration_ms"], 3120)
        self.assertEqual(result["tts_presence_state"]["last_status"], "delivered")
        self.assertFalse(result["evaluation"]["checks"]["no_final_text_drift"]["passed"] is False)

    def test_text_only_when_tts_disabled_surfaces_text_only_branch(self):
        result = self.results["text_only_when_tts_disabled"]
        self.assertEqual(result["final_text"], "我先把这部分写给你。")
        self.assertEqual(result["tts_presence_state"]["enabled"], False)
        self.assertEqual(result["tts_presence_timing"]["delivery_mode"], "text_only")
        self.assertEqual(result["tts_presence_timing"]["pause_profile"], "disabled")
        self.assertTrue(result["evaluation"]["checks"]["tts_disabled_text_only"]["passed"])

    def test_deliberate_silence_as_presence_timing_surfaces_silent_branch(self):
        result = self.results["deliberate_silence_as_presence_timing"]
        self.assertEqual(result["final_text"], "……")
        self.assertEqual(result["tts_presence_timing"]["delivery_mode"], "silent")
        self.assertEqual(result["tts_presence_timing"]["pause_profile"], "silence")
        self.assertGreaterEqual(result["tts_presence_timing"]["silence_before_ms"], 420)
        self.assertTrue(result["evaluation"]["checks"]["deliberate_silence_branch"]["passed"])


if __name__ == "__main__":
    unittest.main()
