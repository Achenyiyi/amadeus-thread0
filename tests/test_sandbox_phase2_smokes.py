import tempfile
import unittest
from pathlib import Path

from evals.run_sandbox_phase2_smokes import (
    _ensure_docker_ready,
    _run_single_scenario,
    _scenario_specs,
)


class SandboxPhase2SmokesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            _ensure_docker_ready()
        except Exception as exc:  # pragma: no cover - environment-specific skip
            raise unittest.SkipTest(f"Docker phase-2 smoke environment is unavailable: {exc}")
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.run_root = Path(cls.tempdir.name)
        cls.specs = {spec["id"]: spec for spec in _scenario_specs(cls.run_root)}
        cls.results = {scenario_id: _run_single_scenario(spec) for scenario_id, spec in cls.specs.items()}

    @classmethod
    def tearDownClass(cls):
        cls.tempdir.cleanup()

    def test_scenario_catalog_is_fixed_to_five_required_ids(self):
        self.assertEqual(
            set(self.specs),
            {
                "runtime_workspace_command_runs_in_docker",
                "attach_repo_root_pytest_git_readonly",
                "blocked_command_families_stay_blocked",
                "followup_continue_from_last_isolated_run",
                "attach_proposal_pending_or_rejected_not_owned",
            },
        )

    def test_all_phase2_smoke_scenarios_pass(self):
        for scenario_id, result in self.results.items():
            with self.subTest(scenario=scenario_id):
                self.assertTrue(result["evaluation"]["passed"])

    def test_runtime_workspace_command_runs_in_docker_uses_docker_runner(self):
        result = self.results["runtime_workspace_command_runs_in_docker"]
        completed = result["steps"][-1]
        packet = completed["autonomy"]["action_packets"][0]
        self.assertEqual(packet["execution_spec"]["runner_kind"], "docker_isolated_runner")
        self.assertEqual(packet["execution_spec"]["network_policy"], "none")
        self.assertEqual(packet["execution_result"]["status"], "completed")

    def test_attach_repo_root_pytest_git_readonly_keeps_attached_root_truth(self):
        result = self.results["attach_repo_root_pytest_git_readonly"]
        attached = result["steps"][1]
        pytest_step = result["steps"][-1]
        self.assertEqual(attached["digital_body_consequence"]["kind"], "workspace_root_attached")
        self.assertEqual(
            pytest_step["digital_body"]["access_state"]["sandbox_state"]["workspace_root_kind"],
            "attached_repo_root",
        )
        self.assertEqual(
            pytest_step["autonomy"]["action_packets"][0]["execution_spec"]["runner_kind"],
            "docker_isolated_runner",
        )

    def test_blocked_command_families_stay_blocked_with_expected_codes(self):
        result = self.results["blocked_command_families_stay_blocked"]
        validation_codes = {
            step["id"]: step["autonomy"]["action_packets"][0]["execution_preview"]["validation_code"]
            for step in result["steps"]
        }
        self.assertEqual(
            validation_codes,
            {
                "package_install_blocked": "PYTHON_MODULE_BLOCKED",
                "shell_wrapper_blocked": "SHELL_WRAPPER_BLOCKED",
                "git_write_blocked": "GIT_SUBCOMMAND_BLOCKED",
                "network_policy_blocked": "NETWORK_POLICY_BLOCKED",
            },
        )

    def test_followup_continue_from_last_isolated_run_preserves_run_identity(self):
        result = self.results["followup_continue_from_last_isolated_run"]
        executed = result["steps"][1]
        followup = result["steps"][-1]
        run_id = executed["autonomy"]["action_packets"][0]["execution_result"]["run_id"]
        sandbox_state = followup["digital_body"]["access_state"]["sandbox_state"]
        self.assertEqual(sandbox_state["last_run_id"], run_id)
        self.assertEqual(followup["autonomy"]["action_packets"][0]["tool_name"], "inspect_workspace_path")
        self.assertEqual(followup["digital_body_consequence"]["kind"], "workspace_path_inspected")

    def test_attach_proposal_pending_or_rejected_does_not_become_capability(self):
        result = self.results["attach_proposal_pending_or_rejected_not_owned"]
        pending = result["steps"][0]
        rejected = result["steps"][-1]
        self.assertEqual(pending["autonomy"]["action_packets"][0]["status"], "awaiting_approval")
        self.assertEqual(rejected["autonomy"]["action_packets"][0]["status"], "rejected")
        self.assertEqual(
            rejected["digital_body"]["access_state"]["selected_access_proposal"]["mode"],
            "operator_attach_repo_root",
        )
        self.assertFalse(rejected["digital_body"]["resource_state"]["workspace_root"])


if __name__ == "__main__":
    unittest.main()
