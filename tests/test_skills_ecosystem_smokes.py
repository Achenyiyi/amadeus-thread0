import tempfile
import unittest
from pathlib import Path

from evals.run_skills_ecosystem_smokes import _run_single_scenario, _scenario_specs


class SkillsEcosystemSmokesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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
                "local_skill_discovery_and_progressive_disclosure",
                "remote_install_proposal_approval_install_enable",
                "auto_match_with_manual_disable_and_pin_precedence",
                "blocked_or_rejected_skill_mutation_does_not_become_capability",
                "completed_skill_usage_resurfaces_in_followup_continuity",
            },
        )

    def test_all_skills_smoke_scenarios_pass(self):
        for scenario_id, result in self.results.items():
            with self.subTest(scenario=scenario_id):
                self.assertTrue(result["evaluation"]["passed"])

    def test_remote_install_proposal_approval_install_enable_keeps_payload_stable(self):
        result = self.results["remote_install_proposal_approval_install_enable"]
        pending = result["steps"][0]["skills"]["pending_approval"]
        installed = result["steps"][1]["autonomy"]["action_packets"][0]
        self.assertEqual(pending["resolved_version"], installed["tool_args"]["resolved_version"])
        self.assertEqual(pending["hash"], installed["tool_args"]["hash"])
        self.assertEqual(result["steps"][1]["digital_body_consequence"]["kind"], "skill_install_completed")
        self.assertEqual(result["steps"][2]["digital_body_consequence"]["kind"], "skill_activation_changed")

    def test_auto_match_with_manual_disable_and_pin_precedence(self):
        result = self.results["auto_match_with_manual_disable_and_pin_precedence"]
        auto_active = result["steps"][0]["skills"]["active"][0]["skill_id"]
        disabled_active = result["steps"][1]["skills"]["active"]
        pinned_active = result["steps"][2]["skills"]["active"][0]["skill_id"]
        self.assertEqual(auto_active, "workspace-regression-triage")
        self.assertEqual(disabled_active, [])
        self.assertEqual(pinned_active, "source-ref-anchor-review")

    def test_blocked_or_rejected_skill_mutation_does_not_become_capability(self):
        result = self.results["blocked_or_rejected_skill_mutation_does_not_become_capability"]
        consequence = result["steps"][0]["digital_body_consequence"]
        self.assertEqual(consequence["kind"], "skill_mutation_blocked")
        self.assertEqual(consequence["skill_effects"][0]["status"], "blocked")
        self.assertFalse(result["runtime_after"]["active"])
        self.assertFalse(result["installed_after"])

    def test_completed_skill_usage_resurfaces_in_followup_continuity(self):
        result = self.results["completed_skill_usage_resurfaces_in_followup_continuity"]
        usage = result["steps"][0]["digital_body_consequence"]
        carryover = result["steps"][1]["interaction_carryover"]
        self.assertEqual(usage["kind"], "skill_usage_completed")
        self.assertEqual(usage["skill_effects"][0]["skill_id"], "source-ref-anchor-review")
        self.assertIn("skill:source-ref-anchor-review", carryover["source_tags"])
        self.assertEqual(carryover["embodied_context"]["kind"], "skill_usage_completed")


if __name__ == "__main__":
    unittest.main()
