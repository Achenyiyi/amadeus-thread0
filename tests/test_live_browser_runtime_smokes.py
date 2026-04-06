import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from evals.run_live_browser_runtime_smokes import _run_single_scenario, _scenario_specs


class LiveBrowserRuntimeSmokesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = TemporaryDirectory()
        run_root = Path(cls._tmpdir.name) / "live-browser-runtime-smokes"
        cls.specs = {spec["id"]: spec for spec in _scenario_specs(run_root)}
        cls.results = {scenario_id: _run_single_scenario(spec) for scenario_id, spec in cls.specs.items()}

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    def test_scenario_catalog_is_fixed_to_six_required_ids(self):
        self.assertEqual(
            set(self.specs),
            {
                "open_follow_continue",
                "login_takeover_resume",
                "interaction_after_approval",
                "download_boundary",
                "upload_boundary",
                "capture_to_source_ref",
            },
        )

    def test_all_live_browser_smokes_pass(self):
        for scenario_id, result in self.results.items():
            with self.subTest(scenario=scenario_id):
                self.assertTrue(result["evaluation"]["passed"])

    def test_login_takeover_resume_uses_same_profile(self):
        result = self.results["login_takeover_resume"]
        blocked = result["steps"][1]["digital_body_consequence"]
        resumed_resource = result["steps"][-1]["digital_body"]["resource_state"]
        self.assertEqual(blocked["kind"], "browser_takeover_requested")
        self.assertEqual(blocked["browser_profile_id"], resumed_resource["browser_profile_id"])

    def test_download_boundary_promotes_downloaded_file(self):
        result = self.results["download_boundary"]
        final_step = result["steps"][-1]
        consequence = final_step["digital_body_consequence"]
        resource = final_step["digital_body"]["resource_state"]
        packet = final_step["autonomy"]["action_packets"][0]
        browser_result = packet["browser_execution_result"]
        self.assertEqual(consequence["kind"], "browser_download_completed")
        self.assertEqual(resource["artifact_carrier"], "filesystem")
        self.assertEqual(resource["active_artifact_ref"], browser_result["download_path"])

    def test_capture_to_source_ref_preserves_live_and_saved_paths(self):
        result = self.results["capture_to_source_ref"]
        capture_step = result["steps"][0]
        inspect_step = result["steps"][1]
        capture_resource = capture_step["digital_body"]["resource_state"]
        self.assertEqual(capture_resource["artifact_carrier"], "browser_page")
        self.assertGreater(capture_resource["preferred_source_ref_id"], 0)
        self.assertEqual(inspect_step["digital_body_consequence"]["kind"], "source_material_inspected")


if __name__ == "__main__":
    unittest.main()
