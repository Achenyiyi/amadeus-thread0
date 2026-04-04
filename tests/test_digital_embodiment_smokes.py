import unittest

from evals.run_digital_embodiment_smokes import _run_single_scenario, _scenario_specs


class DigitalEmbodimentSmokesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.specs = {spec["id"]: spec for spec in _scenario_specs()}
        cls.results = {scenario_id: _run_single_scenario(spec) for scenario_id, spec in cls.specs.items()}

    def test_scenario_catalog_is_fixed_to_four_required_ids(self):
        self.assertEqual(
            set(self.specs),
            {
                "workspace_artifact_continuity",
                "workspace_access_request_resolve",
                "preferred_anchor_reinspect",
                "sandbox_overreach_pending",
            },
        )

    def test_all_smoke_scenarios_pass(self):
        for scenario_id, result in self.results.items():
            with self.subTest(scenario=scenario_id):
                self.assertTrue(result["evaluation"]["passed"])

    def test_workspace_access_request_resolve_keeps_selected_access_proposal_stable(self):
        result = self.results["workspace_access_request_resolve"]
        selected_modes = []
        ratios = []
        for step in result["steps"]:
            packets = step["autonomy"]["action_packets"]
            selected = packets[0].get("selected_access_proposal") if packets else {}
            if selected:
                selected_modes.append(selected.get("mode"))
                ratios.append(selected.get("completion_ratio"))
        self.assertEqual(selected_modes, ["operator_create_workspace"] * len(selected_modes))
        self.assertEqual(ratios[:2], [0.0, 1.0])

    def test_preferred_anchor_reinspect_uses_inspect_not_compare(self):
        result = self.results["preferred_anchor_reinspect"]
        final_step = result["steps"][-1]
        packets = final_step["autonomy"]["action_packets"]
        self.assertEqual([packet.get("tool_name") for packet in packets], ["inspect_source_ref"])
        self.assertNotIn(
            "compare_source_refs",
            [row.get("tool_name") for row in final_step["autonomy"]["execution_trace"]],
        )
        resource_state = final_step["digital_body"]["resource_state"]
        self.assertEqual(resource_state.get("preferred_source_ref_id"), 21)
        self.assertEqual(resource_state.get("artifact_source_ref_ids"), [21, 17])

    def test_sandbox_overreach_does_not_complete_execution(self):
        result = self.results["sandbox_overreach_pending"]
        final_step = result["steps"][-1]
        statuses = [packet.get("status") for packet in final_step["autonomy"]["action_packets"]]
        self.assertTrue(statuses)
        self.assertNotIn("completed", statuses)
        self.assertEqual(final_step["autonomy"]["intent"]["mode"], "approval_pending")
        self.assertTrue(final_step["autonomy"]["pending_approval"])
        self.assertEqual(
            final_step["digital_body"]["access_state"]["sandbox_state"]["execution_policy"],
            "approval_required",
        )

    def test_workspace_artifact_continuity_stays_on_same_file(self):
        result = self.results["workspace_artifact_continuity"]
        refs = [step["digital_body"]["resource_state"]["active_artifact_ref"] for step in result["steps"]]
        roots = [step["digital_body"]["resource_state"]["workspace_root"] for step in result["steps"]]
        kinds = [step["digital_body_consequence"]["kind"] for step in result["steps"]]
        self.assertEqual(len(set(refs)), 1)
        self.assertEqual(len(set(roots)), 1)
        self.assertEqual(
            kinds,
            ["workspace_path_inspected", "workspace_file_updated", "workspace_path_inspected"],
        )


if __name__ == "__main__":
    unittest.main()
