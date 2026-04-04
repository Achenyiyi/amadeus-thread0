import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evals.run_digital_embodiment_audit import (
    _aggregate_overall_status,
    _apply_historical_readiness,
    _build_check_specs,
    _compute_pass_streak,
    _finalize_report,
    _parse_companion_autonomy_artifacts,
    _parse_digital_embodiment_smoke_artifacts,
    _recent_audit_history,
    _render_markdown,
)


class DigitalEmbodimentAuditTests(unittest.TestCase):
    def test_parse_companion_autonomy_artifacts_extracts_report_and_readiness(self):
        with tempfile.TemporaryDirectory() as td:
            report_path = Path(td) / "companion.json"
            report_path.write_text(
                json.dumps(
                    {
                        "freeze_gate_readiness": "freeze_gate_ready",
                        "readiness_status": "companion_autonomy_ready",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            stdout = "\n".join(
                [
                    f"[companion-autonomy] json={report_path}",
                    f"[companion-autonomy] md={Path(td) / 'companion.md'}",
                    "[companion-autonomy] overall_status=passed",
                    "[companion-autonomy] readiness=companion_autonomy_ready",
                ]
            )
            parsed = _parse_companion_autonomy_artifacts(stdout)

        self.assertEqual(parsed["json"], str(report_path))
        self.assertEqual(parsed["overall_status"], "passed")
        self.assertEqual(parsed["freeze_gate_readiness"], "freeze_gate_ready")
        self.assertEqual(parsed["companion_readiness"], "companion_autonomy_ready")

    def test_aggregate_overall_status_fails_when_any_blocking_check_fails(self):
        aggregate = _aggregate_overall_status(
            [
                {"id": "baseline", "status": "passed", "blocking": True},
                {"id": "writeback", "status": "failed", "blocking": True},
            ]
        )
        self.assertEqual(aggregate["overall_status"], "failed")
        self.assertEqual(aggregate["readiness_status"], "digital_embodiment_phase2_in_progress")
        self.assertEqual(aggregate["blocking_failure_ids"], ["writeback"])

    def test_parse_digital_embodiment_smoke_artifacts_extracts_report_paths(self):
        with tempfile.TemporaryDirectory() as td:
            report_path = Path(td) / "smokes.json"
            report_path.write_text(
                json.dumps({"passed": 4, "failed": 0}, ensure_ascii=False),
                encoding="utf-8",
            )
            stdout = "\n".join(
                [
                    f"[digital-embodiment-smokes] json={report_path}",
                    f"[digital-embodiment-smokes] md={Path(td) / 'smokes.md'}",
                    "[digital-embodiment-smokes] overall_status=passed",
                ]
            )
            parsed = _parse_digital_embodiment_smoke_artifacts(stdout)

        self.assertEqual(parsed["json"], str(report_path))
        self.assertEqual(parsed["overall_status"], "passed")
        self.assertEqual(parsed["passed"], "4")
        self.assertEqual(parsed["failed"], "0")

    def test_compute_pass_streak_counts_only_trailing_green_runs(self):
        self.assertEqual(_compute_pass_streak(["passed", "passed", "passed"]), 3)
        self.assertEqual(_compute_pass_streak(["passed", "failed", "passed"]), 1)
        self.assertEqual(_compute_pass_streak(["failed"]), 0)

    def test_apply_historical_readiness_requires_ready_baselines_and_streak(self):
        report = {
            "overall_status": "passed",
            "summary": {
                "total": 3,
                "passed": 3,
                "failed": 0,
            },
        }
        candidate = _apply_historical_readiness(
            report,
            historical_pass_streak=2,
            freeze_gate_readiness="freeze_gate_ready",
            companion_readiness="companion_autonomy_ready",
        )
        ready = _apply_historical_readiness(
            report,
            historical_pass_streak=3,
            freeze_gate_readiness="freeze_gate_ready",
            companion_readiness="companion_autonomy_ready",
        )
        blocked = _apply_historical_readiness(
            report,
            historical_pass_streak=5,
            freeze_gate_readiness="freeze_gate_candidate",
            companion_readiness="companion_autonomy_ready",
        )
        self.assertEqual(candidate["readiness_status"], "digital_embodiment_phase2_in_progress")
        self.assertEqual(ready["readiness_status"], "digital_embodiment_phase2_ready")
        self.assertEqual(blocked["readiness_status"], "digital_embodiment_phase2_in_progress")

    def test_recent_audit_history_uses_current_report_status(self):
        history = _recent_audit_history(
            previous_rows=[
                {
                    "run_id": "r1",
                    "generated_at": "2026-04-04 00:00:00",
                    "overall_status": "passed",
                    "readiness_status": "digital_embodiment_phase2_in_progress",
                },
                {
                    "run_id": "r2",
                    "generated_at": "2026-04-04 00:05:00",
                    "overall_status": "passed",
                    "readiness_status": "digital_embodiment_phase2_in_progress",
                },
            ],
            current_report={
                "run_id": "r3",
                "generated_at": "2026-04-04 00:10:00",
                "overall_status": "passed",
                "readiness_status": "digital_embodiment_phase2_ready",
            },
        )
        self.assertEqual(history["historical_pass_streak"], 3)
        self.assertEqual(history["recent_audits"][-1]["readiness_status"], "digital_embodiment_phase2_ready")

    def test_finalize_report_keeps_top_level_and_recent_history_readiness_aligned(self):
        preliminary = {
            "run_id": "r3",
            "generated_at": "2026-04-04 00:10:00",
            "overall_status": "passed",
            "readiness_status": "digital_embodiment_phase2_in_progress",
            "summary": {"total": 7, "passed": 7, "failed": 0},
        }
        finalized = _finalize_report(
            preliminary,
            previous_rows=[
                {
                    "run_id": "r1",
                    "generated_at": "2026-04-04 00:00:00",
                    "overall_status": "passed",
                    "readiness_status": "digital_embodiment_phase2_in_progress",
                },
                {
                    "run_id": "r2",
                    "generated_at": "2026-04-04 00:05:00",
                    "overall_status": "passed",
                    "readiness_status": "digital_embodiment_phase2_in_progress",
                },
            ],
            freeze_gate_readiness="freeze_gate_ready",
            companion_readiness="companion_autonomy_ready",
        )
        self.assertEqual(finalized["readiness_status"], "digital_embodiment_phase2_ready")
        self.assertEqual(finalized["recent_audits"][-1]["readiness_status"], "digital_embodiment_phase2_ready")
        self.assertEqual(finalized["historical_pass_streak"], 3)
        self.assertEqual(finalized["summary"]["historical_pass_streak"], 3)

    def test_render_markdown_includes_baseline_readiness(self):
        report = {
            "run_id": "embody-1",
            "generated_at": "2026-04-04 10:00:00",
            "overall_status": "failed",
            "readiness_status": "digital_embodiment_phase2_in_progress",
            "freeze_gate_readiness": "freeze_gate_ready",
            "companion_readiness": "companion_autonomy_ready",
            "summary": {
                "total": 2,
                "passed": 1,
                "failed": 1,
                "historical_pass_streak": 1,
            },
            "recent_audits": [
                {
                    "run_id": "embody-1",
                    "generated_at": "2026-04-04 10:00:00",
                    "overall_status": "failed",
                    "readiness_status": "digital_embodiment_phase2_in_progress",
                }
            ],
            "checks": [
                {
                    "id": "baseline_companion_autonomy_gate",
                    "title": "Baseline Freeze + Companion Autonomy Gate",
                    "status": "failed",
                    "duration_s": 1.2,
                    "command": "python evals/run_companion_autonomy_audit.py",
                    "failure_reasons": ["freeze_gate_readiness=freeze_gate_candidate"],
                    "artifacts": {"json": "E:/repo/report.json"},
                }
            ],
        }
        rendered = _render_markdown(report)
        self.assertIn("Freeze Gate Readiness: `freeze_gate_ready`", rendered)
        self.assertIn("Companion Autonomy Readiness: `companion_autonomy_ready`", rendered)
        self.assertIn("`freeze_gate_readiness=freeze_gate_candidate`", rendered)
        self.assertIn("`baseline_companion_autonomy_gate`", rendered)

    def test_build_check_specs_covers_plan_phase_one_surfaces(self):
        specs = _build_check_specs(run_id="demo")
        ids = {item["id"] for item in specs}
        self.assertIn("baseline_companion_autonomy_gate", ids)
        self.assertIn("digital_embodiment_manual_smokes", ids)
        self.assertIn("phase2_access_resource_truth", ids)
        self.assertIn("workspace_session_account_truth", ids)
        self.assertIn("saved_material_external_continuity", ids)
        self.assertIn("sandbox_contract_truth", ids)
        self.assertIn("unified_writeback_resurfacing", ids)


if __name__ == "__main__":
    unittest.main()
