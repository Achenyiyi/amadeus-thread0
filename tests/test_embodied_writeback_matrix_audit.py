import unittest

import evals.run_embodied_writeback_matrix_audit as audit
from evals.run_embodied_writeback_matrix_audit import (
    CHECK_COVERAGE,
    FAMILY_TEST_NODES,
    MATRIX_FAMILIES,
    _overall,
    build_check_specs,
    family_coverage,
    missing_family_coverage,
    render_markdown,
)


class EmbodiedWritebackMatrixAuditTests(unittest.TestCase):
    def test_matrix_families_cover_required_consequence_kinds(self):
        required = {
            "workspace_path_inspected",
            "workspace_file_updated",
            "source_material_inspected",
            "source_material_compared",
            "artifact_reacquired",
            "access_state_refreshed",
            "workspace_root_attached",
            "sandbox_execution_completed",
            "sandbox_execution_blocked",
            "browser_navigation_completed",
            "browser_interaction_completed",
            "browser_download_completed",
            "browser_upload_completed",
            "browser_takeover_requested",
            "browser_action_blocked",
            "skill_usage_completed",
            "skill_mutation_blocked",
        }

        self.assertEqual(set(MATRIX_FAMILIES), required)
        self.assertFalse(missing_family_coverage())

    def test_build_check_specs_targets_matrix_contract_tests(self):
        specs = build_check_specs()

        commands = [" ".join(str(part) for part in spec["command"]) for spec in specs]
        joined = "\n".join(commands)
        check_ids = {str(spec["id"]) for spec in specs}
        broad_ids = set(CHECK_COVERAGE)
        self.assertTrue(broad_ids.issubset(check_ids))
        self.assertIn("matrix_family_node_coverage", check_ids)
        self.assertIn("tests/test_autonomy_writeback.py", joined)
        self.assertIn("tests/test_world_model_residue.py", joined)
        self.assertIn("tests/test_backend_session.py", joined)
        self.assertIn("tests/test_backend_api.py", joined)
        self.assertIn("tests/test_retrieval_continuity.py", joined)
        self.assertIn("embodied or sandbox or browser or skill or source or workspace", joined)
        family_specs = [spec for spec in specs if str(spec.get("id", "")) == "matrix_family_node_coverage"]
        self.assertEqual(len(family_specs), 1)
        broad_specs = [spec for spec in specs if str(spec.get("id", "")) in CHECK_COVERAGE]
        for spec in broad_specs:
            self.assertEqual(spec["covers"], CHECK_COVERAGE[spec["id"]])
        for spec in family_specs:
            self.assertEqual(spec["covers"], MATRIX_FAMILIES)
            command_text = " ".join(str(part) for part in spec["command"])
            for family in MATRIX_FAMILIES:
                for node in FAMILY_TEST_NODES[family]:
                    self.assertIn(node, command_text)

    def test_every_matrix_family_has_declared_blocking_coverage(self):
        coverage = family_coverage()

        for family in MATRIX_FAMILIES:
            with self.subTest(family=family):
                self.assertTrue(coverage.get(family))

    def test_every_matrix_family_has_executable_pytest_nodes(self):
        for family in MATRIX_FAMILIES:
            with self.subTest(family=family):
                nodes = FAMILY_TEST_NODES.get(family) or []
                self.assertTrue(nodes)
                for node in nodes:
                    self.assertIn("::", node)
                    self.assertTrue(node.startswith("tests/") or node.startswith("tests\\"))

        specs = build_check_specs()
        family_specs = [spec for spec in specs if str(spec.get("id", "")) == "matrix_family_node_coverage"]
        self.assertEqual(len(family_specs), 1)
        for spec in family_specs:
            self.assertEqual(spec["covers"], MATRIX_FAMILIES)
            command_text = " ".join(str(part) for part in spec["command"])
            for family in MATRIX_FAMILIES:
                for node in FAMILY_TEST_NODES[family]:
                    self.assertIn(node, command_text)

    def test_overall_fails_when_family_coverage_is_missing_from_passed_checks(self):
        summary = _overall(
            [
                {
                    "id": "matrix_core_writeback_residue",
                    "status": "passed",
                    "blocking": True,
                    "covers": ["workspace_path_inspected"],
                }
            ]
        )

        self.assertEqual(summary["overall_status"], "failed")
        self.assertIn("workspace_file_updated", summary["missing_family_coverage"])
        self.assertIn("missing_family:workspace_file_updated", summary["blocking_failure_ids"])

    def test_overall_fails_when_family_has_no_executable_node_declaration(self):
        original_nodes = audit.FAMILY_TEST_NODES["browser_upload_completed"]
        try:
            audit.FAMILY_TEST_NODES["browser_upload_completed"] = []
            summary = _overall(
                [
                    {
                        "id": "matrix_family_node_coverage",
                        "status": "passed",
                        "blocking": True,
                        "covers": list(MATRIX_FAMILIES),
                    }
                ]
            )
        finally:
            audit.FAMILY_TEST_NODES["browser_upload_completed"] = original_nodes

        self.assertEqual(summary["overall_status"], "failed")
        self.assertIn("browser_upload_completed", summary["missing_family_test_nodes"])
        self.assertIn("missing_family_test_nodes:browser_upload_completed", summary["blocking_failure_ids"])

    def test_overall_fails_when_any_blocking_check_fails(self):
        summary = _overall(
            [
                {
                    "id": "matrix_core_writeback_residue",
                    "status": "passed",
                    "blocking": True,
                    "covers": CHECK_COVERAGE["matrix_core_writeback_residue"],
                },
                {
                    "id": "matrix_backend_contract",
                    "status": "passed",
                    "blocking": True,
                    "covers": CHECK_COVERAGE["matrix_backend_contract"],
                },
                {
                    "id": "matrix_retrieval_continuity",
                    "status": "failed",
                    "blocking": True,
                    "covers": CHECK_COVERAGE["matrix_retrieval_continuity"],
                },
            ]
        )

        self.assertEqual(summary["overall_status"], "failed")
        self.assertEqual(summary["readiness_status"], "embodied_writeback_matrix_regressed")
        self.assertIn("matrix_retrieval_continuity", summary["blocking_failure_ids"])

    def test_render_markdown_includes_family_and_check_tables(self):
        report = {
            "run_id": "test-run",
            "generated_at": "2026-05-04 12:00:00",
            "overall_status": "passed",
            "readiness_status": "embodied_writeback_matrix_ready",
            "summary": {"total": 1, "passed": 1, "failed": 0},
            "matrix_families": ["browser_navigation_completed"],
            "family_coverage": {"browser_navigation_completed": ["matrix_retrieval_continuity"]},
            "missing_family_coverage": [],
            "checks": [
                {
                    "id": "matrix_retrieval_continuity",
                    "status": "passed",
                    "covers": ["browser_navigation_completed"],
                    "duration_s": 0.123,
                },
            ],
        }

        rendered = render_markdown(report)

        self.assertIn("# Embodied Writeback Matrix Audit", rendered)
        self.assertIn("`embodied_writeback_matrix_ready`", rendered)
        self.assertIn("`browser_navigation_completed`", rendered)
        self.assertIn("`matrix_retrieval_continuity`", rendered)
        self.assertIn("| `matrix_retrieval_continuity` | `passed` | 1 families | 0.123 |", rendered)


if __name__ == "__main__":
    unittest.main()
