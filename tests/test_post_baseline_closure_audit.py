import unittest

from evals.run_post_baseline_closure_audit import (
    _aggregate_report,
    _build_check_specs,
    _status_overrides_from_checks,
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
        self.assertGreaterEqual(report["summary"]["deferred_fail_closed"], 2)
        self.assertEqual(report["closure_items"]["chinese_de_scaffolding"]["status"], "tracked_not_mainline")

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
                    "deferred_fail_closed": 2,
                    "tracked_not_mainline": 1,
                    "quality_backlog_tracked": 2,
                },
                "closure_items": {
                    "callable_transport_adapter": {"status": "implemented_ready", "runtime_available": True},
                    "multimodal_input_capture": {"status": "deferred_fail_closed", "runtime_available": False},
                },
                "checks": [
                    {"id": "post_baseline_unit_contract", "title": "Unit", "status": "passed", "blocking": True, "duration_s": 0.1, "command": "python -m pytest"}
                ],
            }
        )

        self.assertIn("# Post-Baseline Closure Audit", rendered)
        self.assertIn("| Item | Status | Runtime Available |", rendered)
        self.assertIn("| `multimodal_input_capture` | `deferred_fail_closed` | `False` |", rendered)


if __name__ == "__main__":
    unittest.main()
