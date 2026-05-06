import unittest

from evals.run_post_baseline_closure_audit import (
    _aggregate_report,
    _build_check_specs,
    _status_overrides_from_checks,
    _status_overrides_from_roadmap_audit,
    render_markdown,
)


class PostBaselineClosureAuditTests(unittest.TestCase):
    def test_build_check_specs_covers_post_baseline_closure_lanes(self):
        ids = {item["id"] for item in _build_check_specs("demo")}

        self.assertEqual(
            ids,
            {
                "post_baseline_unit_contract",
                "executor_adapter_audit",
                "tts_presence_timing_audit",
                "chinese_surface_tracking_audit",
            },
        )

    def test_status_overrides_map_runtime_checks_to_required_items(self):
        overrides = _status_overrides_from_checks(
            [
                {"id": "post_baseline_unit_contract", "status": "passed"},
                {"id": "executor_adapter_audit", "status": "passed"},
                {"id": "tts_presence_timing_audit", "status": "passed"},
            ]
        )

        self.assertEqual(overrides["callable_transport_adapter"]["status"], "implemented_ready")
        self.assertEqual(overrides["executor_adapter"]["status"], "implemented_ready")
        self.assertEqual(overrides["tts_presence_timing"]["status"], "preserved_ready")

    def test_aggregate_report_passes_when_blocking_runtime_checks_pass(self):
        report = _aggregate_report(
            [
                {"id": "post_baseline_unit_contract", "status": "passed", "blocking": True},
                {"id": "executor_adapter_audit", "status": "passed", "blocking": True},
                {"id": "tts_presence_timing_audit", "status": "passed", "blocking": True},
                {"id": "chinese_surface_tracking_audit", "status": "failed", "blocking": False},
            ]
        )

        self.assertEqual(report["overall_status"], "passed")
        self.assertEqual(report["readiness_status"], "post_baseline_closure_ready")
        self.assertGreaterEqual(report["summary"]["unlocked_planned"], 5)
        self.assertEqual(report["closure_items"]["chinese_de_scaffolding"]["status"], "unlocked_planned")

    def test_roadmap_audit_overrides_ready_unlocked_lanes(self):
        overrides = _status_overrides_from_roadmap_audit(
            {
                "overall_status": "passed",
                "readiness_status": "post_unlock_roadmap_ready",
                "lanes": {
                    "multimodal_capture_phase1": {"status": "ready", "readiness_status": "multimodal_capture_phase1_ready"},
                    "dynamic_skills_phase1": {"status": "ready", "readiness_status": "dynamic_skills_phase1_ready"},
                    "external_executor_harness_phase1": {"status": "ready", "readiness_status": "external_executor_harness_phase1_ready"},
                    "frontend_runtime_shell_phase1": {"status": "ready", "readiness_status": "frontend_runtime_shell_phase1_ready"},
                    "chinese_semantic_descaffolding_phase1": {
                        "status": "ready",
                        "readiness_status": "chinese_semantic_descaffolding_phase1_ready",
                    },
                    "capability_growth_phase5": {"status": "ready", "readiness_status": "capability_growth_phase5_ready"},
                    "natural_long_horizon_calibration_phase1": {
                        "status": "ready",
                        "readiness_status": "natural_long_horizon_calibration_phase1_ready",
                    },
                },
            }
        )

        self.assertEqual(overrides["multimodal_input_capture"]["status"], "implemented_ready")
        self.assertEqual(overrides["external_executor_harnesses"]["status"], "implemented_ready")
        self.assertFalse(overrides["external_executor_harnesses"]["runtime_available"])

    def test_aggregate_report_fails_when_required_runtime_check_fails(self):
        report = _aggregate_report(
            [
                {"id": "post_baseline_unit_contract", "status": "passed", "blocking": True},
                {"id": "executor_adapter_audit", "status": "failed", "blocking": True},
                {"id": "tts_presence_timing_audit", "status": "passed", "blocking": True},
            ]
        )

        self.assertEqual(report["overall_status"], "failed")
        self.assertEqual(report["readiness_status"], "post_baseline_closure_in_progress")
        self.assertIn("executor_adapter", report["blocking_failure_ids"])
        self.assertIn("executor_adapter_audit", report["blocking_failure_ids"])

    def test_render_markdown_includes_item_status_table(self):
        rendered = render_markdown(
            {
                "run_id": "post-baseline",
                "generated_at": "2026-05-06 12:00:00",
                "overall_status": "passed",
                "readiness_status": "post_baseline_closure_ready",
                "summary": {
                    "checks_total": 1,
                    "checks_passed": 1,
                    "checks_failed": 0,
                    "implemented_ready": 2,
                    "preserved_ready": 1,
                    "unlocked_planned": 5,
                },
                "closure_items": {
                    "callable_transport_adapter": {"status": "implemented_ready", "runtime_available": True},
                    "multimodal_input_capture": {"status": "unlocked_planned", "runtime_available": False},
                },
                "checks": [
                    {"id": "post_baseline_unit_contract", "title": "Unit", "status": "passed", "blocking": True, "duration_s": 0.1, "command": "python -m pytest"}
                ],
            }
        )

        self.assertIn("# Post-Baseline Closure Audit", rendered)
        self.assertIn("| Item | Status | Runtime Available |", rendered)
        self.assertIn("- Unlocked planned: `5`", rendered)
        self.assertIn("| `multimodal_input_capture` | `unlocked_planned` | `False` |", rendered)


if __name__ == "__main__":
    unittest.main()
