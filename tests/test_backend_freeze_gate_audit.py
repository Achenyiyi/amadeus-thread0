import unittest

from evals.run_backend_freeze_gate_audit import (
    _apply_historical_readiness,
    _aggregate_overall_status,
    _build_check_specs,
    _compute_pass_streak,
    _parse_freeze_gate_artifacts,
    _recent_audit_history,
    _render_markdown,
)


class BackendFreezeGateAuditTests(unittest.TestCase):
    def test_parse_freeze_gate_artifacts_extracts_paths_and_status(self):
        stdout = "\n".join(
            [
                "[freeze-gate] json=E:/repo/evals/reports/freeze.json",
                "[freeze-gate] md=E:/repo/evals/reports/freeze.md",
                "[freeze-gate] overall_status=passed",
            ]
        )
        parsed = _parse_freeze_gate_artifacts(stdout)
        self.assertEqual(parsed["json"], "E:/repo/evals/reports/freeze.json")
        self.assertEqual(parsed["md"], "E:/repo/evals/reports/freeze.md")
        self.assertEqual(parsed["overall_status"], "passed")

    def test_aggregate_overall_status_distinguishes_blockers_and_warnings(self):
        aggregate = _aggregate_overall_status(
            [
                {"id": "compile", "status": "passed", "blocking": True},
                {"id": "smokes", "status": "failed", "blocking": True},
                {"id": "notes", "status": "failed", "blocking": False},
            ]
        )
        self.assertEqual(aggregate["overall_status"], "failed")
        self.assertEqual(aggregate["readiness_status"], "backend_maturation_required")
        self.assertEqual(aggregate["blocking_failure_ids"], ["smokes"])
        self.assertEqual(aggregate["warning_failure_ids"], ["notes"])
        self.assertEqual(aggregate["summary"]["failed"], 2)

    def test_compute_pass_streak_counts_only_trailing_green_runs(self):
        self.assertEqual(_compute_pass_streak(["passed", "passed", "passed"]), 3)
        self.assertEqual(_compute_pass_streak(["passed", "failed", "passed", "passed"]), 2)
        self.assertEqual(_compute_pass_streak(["failed", "passed"]), 1)
        self.assertEqual(_compute_pass_streak(["passed", "failed"]), 0)

    def test_apply_historical_readiness_promotes_after_three_green_runs(self):
        aggregate = _aggregate_overall_status(
            [
                {"id": "compile", "status": "passed", "blocking": True},
                {"id": "smokes", "status": "passed", "blocking": True},
            ]
        )
        candidate = _apply_historical_readiness(aggregate, historical_pass_streak=2)
        ready = _apply_historical_readiness(aggregate, historical_pass_streak=3)
        self.assertEqual(candidate["readiness_status"], "freeze_gate_candidate")
        self.assertEqual(ready["readiness_status"], "freeze_gate_ready")
        self.assertEqual(ready["summary"]["historical_pass_streak"], 3)

    def test_recent_audit_history_uses_final_current_readiness(self):
        previous_rows = [
            {
                "run_id": "r1",
                "generated_at": "2026-03-25 00:00:00",
                "overall_status": "passed",
                "readiness_status": "freeze_gate_candidate",
                "path": "one.json",
            },
            {
                "run_id": "r2",
                "generated_at": "2026-03-25 00:10:00",
                "overall_status": "passed",
                "readiness_status": "freeze_gate_candidate",
                "path": "two.json",
            },
        ]
        current_report = {
            "run_id": "r3",
            "generated_at": "2026-03-25 00:20:00",
            "overall_status": "passed",
            "readiness_status": "freeze_gate_ready",
        }
        history = _recent_audit_history(previous_rows=previous_rows, current_report=current_report)
        self.assertEqual(history["historical_pass_streak"], 3)
        self.assertEqual(history["recent_audits"][-1]["readiness_status"], "freeze_gate_ready")

    def test_render_markdown_includes_summary_and_artifacts(self):
        report = {
            "run_id": "testrun",
            "generated_at": "2026-03-25 10:00:00",
            "model_summary": "qwen",
            "overall_status": "failed",
            "readiness_status": "backend_maturation_required",
            "summary": {
                "total": 2,
                "passed": 1,
                "failed": 1,
                "blocking_failures": 1,
                "warning_failures": 0,
                "historical_pass_streak": 1,
            },
            "blocking_failure_ids": ["freeze_gate_smokes"],
            "warning_failure_ids": [],
            "recent_audits": [
                {
                    "run_id": "testrun",
                    "generated_at": "2026-03-25 10:00:00",
                    "overall_status": "failed",
                    "readiness_status": "backend_maturation_required",
                }
            ],
            "checks": [
                {
                    "id": "freeze_gate_smokes",
                    "title": "Freeze Gate Smoke Packs",
                    "category": "smoke",
                    "blocking": True,
                    "status": "failed",
                    "duration_s": 12.345,
                    "returncode": 1,
                    "command": "python evals/run_freeze_gate_smokes.py",
                    "artifacts": {
                        "json": "E:/repo/evals/reports/freeze.json",
                        "md": "E:/repo/evals/reports/freeze.md",
                        "overall_status": "failed",
                    },
                    "failure_reasons": ["freeze_gate_overall_status=failed"],
                    "stdout_tail": "tail",
                    "stderr_tail": "",
                }
            ],
        }
        rendered = _render_markdown(report)
        self.assertIn("Overall Status: `failed`", rendered)
        self.assertIn("Readiness: `backend_maturation_required`", rendered)
        self.assertIn("Historical pass streak: `1`", rendered)
        self.assertIn("## Recent Audit History", rendered)
        self.assertIn("`freeze_gate_smokes`", rendered)
        self.assertIn("`json`: `E:/repo/evals/reports/freeze.json`", rendered)
        self.assertIn("`freeze_gate_overall_status=failed`", rendered)

    def test_build_check_specs_covers_architecture_decision_gate(self):
        specs = _build_check_specs(case_timeout_s=120, smoke_run_tag="audit")
        ids = {item["id"] for item in specs}
        self.assertIn("session_fabric_perception_contract", ids)
        self.assertIn("final_semantics_writeback_traceability", ids)
        self.assertIn("capability_presence_runtime", ids)


if __name__ == "__main__":
    unittest.main()
