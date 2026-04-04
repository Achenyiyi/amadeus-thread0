import tempfile
import unittest
from pathlib import Path

from evals.run_sandbox_embodied_execution_smokes import _run_single_scenario, _scenario_specs


class SandboxEmbodiedExecutionSmokesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.run_root = Path(cls.tempdir.name)
        cls.specs = {spec["id"]: spec for spec in _scenario_specs(cls.run_root)}
        cls.results = {scenario_id: _run_single_scenario(spec) for scenario_id, spec in cls.specs.items()}

    @classmethod
    def tearDownClass(cls):
        cls.tempdir.cleanup()

    def test_scenario_catalog_is_fixed_to_four_required_ids(self):
        self.assertEqual(
            set(self.specs),
            {
                "workspace_pytest_after_approval",
                "workspace_script_generates_artifact",
                "disallowed_command_or_outside_root_blocked",
                "followup_continue_from_last_run_log_or_artifact",
            },
        )

    def test_all_smoke_scenarios_pass(self):
        for scenario_id, result in self.results.items():
            with self.subTest(scenario=scenario_id):
                self.assertTrue(result["evaluation"]["passed"])

    def test_workspace_pytest_after_approval_keeps_same_execution_spec(self):
        result = self.results["workspace_pytest_after_approval"]
        pending = result["steps"][0]["autonomy"]["action_packets"][0]
        completed = result["steps"][1]["autonomy"]["action_packets"][0]
        self.assertEqual(pending["proposal_id"], completed["proposal_id"])
        self.assertEqual(pending["execution_spec"], completed["execution_spec"])
        self.assertEqual(completed["execution_result"]["exit_code"], 0)

    def test_workspace_script_generates_real_artifact(self):
        result = self.results["workspace_script_generates_artifact"]
        completed = result["steps"][-1]
        packet = completed["autonomy"]["action_packets"][0]
        produced = packet["execution_result"]["produced_artifacts"]
        self.assertTrue(produced)
        self.assertEqual(completed["digital_body"]["resource_state"]["active_artifact_ref"], produced[0])
        self.assertEqual(completed["digital_body_consequence"]["kind"], "sandbox_execution_completed")

    def test_disallowed_command_blocks_before_execution(self):
        result = self.results["disallowed_command_or_outside_root_blocked"]
        blocked = result["steps"][-1]
        packet = blocked["autonomy"]["action_packets"][0]
        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(packet["block_reason"])
        self.assertEqual(packet["execution_preview"]["argv"], ["python", "../outside.py"])
        self.assertFalse(packet["execution_result"])
        self.assertEqual(blocked["digital_body_consequence"]["kind"], "sandbox_execution_blocked")

    def test_followup_continue_reuses_last_run_identity(self):
        result = self.results["followup_continue_from_last_run_log_or_artifact"]
        executed = result["steps"][1]
        followup = result["steps"][-1]
        run_id = executed["autonomy"]["action_packets"][0]["execution_result"]["run_id"]
        sandbox_state = followup["digital_body"]["access_state"]["sandbox_state"]
        self.assertEqual(sandbox_state["last_run_id"], run_id)
        self.assertEqual(followup["autonomy"]["action_packets"][0]["tool_name"], "inspect_workspace_path")
        self.assertEqual(followup["digital_body_consequence"]["kind"], "workspace_path_inspected")


if __name__ == "__main__":
    unittest.main()
