import json
import tempfile
import unittest
from pathlib import Path

from evals.run_live_browser_runtime_audit import (
    _aggregate_overall_status,
    _apply_historical_readiness,
    _build_check_specs,
    _compute_pass_streak,
    _finalize_report,
    _parse_skills_baseline,
    _parse_smokes,
    _recent_audit_history,
)


class LiveBrowserRuntimeAuditTests(unittest.TestCase):
    def test_parse_skills_baseline_extracts_readiness_stack(self):
        with tempfile.TemporaryDirectory() as td:
            report_path = Path(td) / "skills.json"
            report_path.write_text(
                json.dumps(
                    {
                        "freeze_gate_readiness": "freeze_gate_ready",
                        "companion_readiness": "companion_autonomy_ready",
                        "digital_embodiment_readiness": "digital_embodiment_phase2_ready",
                        "sandbox_readiness": "sandbox_embodied_execution_phase1_ready",
                        "readiness_status": "skills_ecosystem_ready",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            stdout = "\n".join(
                [
                    f"[skills-ecosystem] json={report_path}",
                    f"[skills-ecosystem] md={Path(td) / 'skills.md'}",
                    "[skills-ecosystem] overall_status=passed",
                    "[skills-ecosystem] readiness=skills_ecosystem_ready",
                ]
            )
            parsed = _parse_skills_baseline(stdout)

        self.assertEqual(parsed["json"], str(report_path))
        self.assertEqual(parsed["overall_status"], "passed")
        self.assertEqual(parsed["skills_readiness"], "skills_ecosystem_ready")
        self.assertEqual(parsed["sandbox_readiness"], "sandbox_embodied_execution_phase1_ready")

    def test_parse_smokes_extracts_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            report_path = Path(td) / "smokes.json"
            report_path.write_text(json.dumps({"passed": 6, "failed": 0}, ensure_ascii=False), encoding="utf-8")
            stdout = "\n".join(
                [
                    f"[live-browser-runtime-smokes] json={report_path}",
                    f"[live-browser-runtime-smokes] md={Path(td) / 'smokes.md'}",
                    "[live-browser-runtime-smokes] overall_status=passed",
                ]
            )
            parsed = _parse_smokes(stdout)

        self.assertEqual(parsed["json"], str(report_path))
        self.assertEqual(parsed["overall_status"], "passed")
        self.assertEqual(parsed["passed"], "6")
        self.assertEqual(parsed["failed"], "0")

    def test_compute_pass_streak_counts_only_trailing_green_runs(self):
        self.assertEqual(_compute_pass_streak(["passed", "passed", "passed"]), 3)
        self.assertEqual(_compute_pass_streak(["passed", "failed", "passed"]), 1)
        self.assertEqual(_compute_pass_streak(["failed"]), 0)

    def test_aggregate_overall_status_blocks_on_failed_check(self):
        aggregate = _aggregate_overall_status(
            [
                {"id": "baseline", "status": "passed", "blocking": True},
                {"id": "smokes", "status": "failed", "blocking": True},
            ]
        )
        self.assertEqual(aggregate["overall_status"], "failed")
        self.assertEqual(aggregate["readiness_status"], "live_browser_runtime_phase1_in_progress")
        self.assertEqual(aggregate["blocking_failure_ids"], ["smokes"])

    def test_apply_historical_readiness_requires_full_baseline_and_streak(self):
        report = {"overall_status": "passed", "summary": {"total": 4, "passed": 4, "failed": 0}}
        baseline = {
            "freeze_gate_readiness": "freeze_gate_ready",
            "companion_readiness": "companion_autonomy_ready",
            "digital_embodiment_readiness": "digital_embodiment_phase2_ready",
            "sandbox_readiness": "sandbox_embodied_execution_phase1_ready",
            "skills_readiness": "skills_ecosystem_ready",
        }
        candidate = _apply_historical_readiness(dict(report), historical_pass_streak=2, baseline=baseline)
        ready = _apply_historical_readiness(dict(report), historical_pass_streak=3, baseline=baseline)
        self.assertEqual(candidate["readiness_status"], "live_browser_runtime_phase1_in_progress")
        self.assertEqual(ready["readiness_status"], "live_browser_runtime_phase1_ready")

    def test_recent_history_uses_current_report_status(self):
        history = _recent_audit_history(
            previous_rows=[
                {"run_id": "r1", "generated_at": "2026-04-05 00:00:00", "overall_status": "passed", "readiness_status": "live_browser_runtime_phase1_in_progress"},
                {"run_id": "r2", "generated_at": "2026-04-05 00:05:00", "overall_status": "passed", "readiness_status": "live_browser_runtime_phase1_in_progress"},
            ],
            current_report={"run_id": "r3", "generated_at": "2026-04-05 00:10:00", "overall_status": "passed", "readiness_status": "live_browser_runtime_phase1_ready"},
        )
        self.assertEqual(history["historical_pass_streak"], 3)
        self.assertEqual(history["recent_audits"][-1]["readiness_status"], "live_browser_runtime_phase1_ready")

    def test_finalize_report_keeps_top_level_and_recent_history_readiness_aligned(self):
        preliminary = {
            "run_id": "r3",
            "generated_at": "2026-04-05 00:10:00",
            "overall_status": "passed",
            "readiness_status": "live_browser_runtime_phase1_in_progress",
            "summary": {"total": 4, "passed": 4, "failed": 0},
        }
        baseline = {
            "freeze_gate_readiness": "freeze_gate_ready",
            "companion_readiness": "companion_autonomy_ready",
            "digital_embodiment_readiness": "digital_embodiment_phase2_ready",
            "sandbox_readiness": "sandbox_embodied_execution_phase1_ready",
            "skills_readiness": "skills_ecosystem_ready",
        }
        finalized = _finalize_report(
            preliminary,
            previous_rows=[
                {"run_id": "r1", "generated_at": "2026-04-05 00:00:00", "overall_status": "passed", "readiness_status": "live_browser_runtime_phase1_in_progress"},
                {"run_id": "r2", "generated_at": "2026-04-05 00:05:00", "overall_status": "passed", "readiness_status": "live_browser_runtime_phase1_in_progress"},
            ],
            baseline=baseline,
        )
        self.assertEqual(finalized["readiness_status"], "live_browser_runtime_phase1_ready")
        self.assertEqual(finalized["recent_audits"][-1]["readiness_status"], "live_browser_runtime_phase1_ready")
        self.assertEqual(finalized["historical_pass_streak"], 3)

    def test_build_check_specs_covers_live_browser_phase_one_surfaces(self):
        specs = _build_check_specs(run_id="demo")
        ids = {item["id"] for item in specs}
        self.assertIn("baseline_skills_ecosystem_gate", ids)
        self.assertIn("live_browser_manual_smokes", ids)
        self.assertIn("browser_runner_and_runtime_contract", ids)
        self.assertIn("browser_backend_writeback_regressions", ids)


if __name__ == "__main__":
    unittest.main()
