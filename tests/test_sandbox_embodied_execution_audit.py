import json
import tempfile
import unittest
from pathlib import Path

from evals.run_sandbox_embodied_execution_audit import (
    _build_check_specs,
    _finalize,
    _parse_digital_embodiment,
    _parse_smokes,
    _pass_streak,
    _render,
)


class SandboxEmbodiedExecutionAuditTests(unittest.TestCase):
    def test_parse_digital_embodiment_extracts_baselines(self):
        with tempfile.TemporaryDirectory() as td:
            report_path = Path(td) / "digital.json"
            report_path.write_text(
                json.dumps(
                    {
                        "freeze_gate_readiness": "freeze_gate_ready",
                        "companion_readiness": "companion_autonomy_ready",
                        "readiness_status": "digital_embodiment_phase2_ready",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            parsed = _parse_digital_embodiment(
                "\n".join(
                    [
                        f"[digital-embodiment] json={report_path}",
                        f"[digital-embodiment] md={Path(td) / 'digital.md'}",
                        "[digital-embodiment] overall_status=passed",
                        "[digital-embodiment] readiness=digital_embodiment_phase2_ready",
                    ]
                )
            )
        self.assertEqual(parsed["freeze_gate_readiness"], "freeze_gate_ready")
        self.assertEqual(parsed["companion_readiness"], "companion_autonomy_ready")
        self.assertEqual(parsed["digital_embodiment_readiness"], "digital_embodiment_phase2_ready")

    def test_parse_smokes_extracts_report_paths(self):
        with tempfile.TemporaryDirectory() as td:
            report_path = Path(td) / "smokes.json"
            report_path.write_text(json.dumps({"passed": 4, "failed": 0}, ensure_ascii=False), encoding="utf-8")
            parsed = _parse_smokes(
                "\n".join(
                    [
                        f"[sandbox-embodied-execution-smokes] json={report_path}",
                        f"[sandbox-embodied-execution-smokes] md={Path(td) / 'smokes.md'}",
                        "[sandbox-embodied-execution-smokes] overall_status=passed",
                    ]
                )
            )
        self.assertEqual(parsed["json"], str(report_path))
        self.assertEqual(parsed["overall_status"], "passed")
        self.assertEqual(parsed["passed"], "4")

    def test_pass_streak_counts_only_trailing_passes(self):
        self.assertEqual(_pass_streak(["passed", "passed", "passed"]), 3)
        self.assertEqual(_pass_streak(["passed", "failed", "passed"]), 1)
        self.assertEqual(_pass_streak(["failed"]), 0)

    def test_finalize_requires_baselines_and_streak(self):
        report = {
            "run_id": "sandbox-3",
            "generated_at": "2026-04-04 10:00:00",
            "overall_status": "passed",
            "readiness_status": "sandbox_embodied_execution_phase1_in_progress",
            "summary": {"total": 4, "passed": 4, "failed": 0},
        }
        finalized = _finalize(
            report,
            [
                {"run_id": "sandbox-1", "generated_at": "2026-04-04 09:00:00", "overall_status": "passed", "readiness_status": "sandbox_embodied_execution_phase1_in_progress"},
                {"run_id": "sandbox-2", "generated_at": "2026-04-04 09:30:00", "overall_status": "passed", "readiness_status": "sandbox_embodied_execution_phase1_in_progress"},
            ],
            {
                "freeze_gate_readiness": "freeze_gate_ready",
                "companion_readiness": "companion_autonomy_ready",
                "digital_embodiment_readiness": "digital_embodiment_phase2_ready",
            },
        )
        self.assertEqual(finalized["readiness_status"], "sandbox_embodied_execution_phase1_ready")
        self.assertEqual(finalized["recent_audits"][-1]["readiness_status"], "sandbox_embodied_execution_phase1_ready")
        self.assertEqual(finalized["historical_pass_streak"], 3)

    def test_build_check_specs_covers_phase_one_contract(self):
        ids = {item["id"] for item in _build_check_specs("demo")}
        self.assertEqual(
            ids,
            {
                "baseline_digital_embodiment_gate",
                "sandbox_embodied_execution_manual_smokes",
                "sandbox_runtime_contract",
                "sandbox_backend_writeback_residue",
            },
        )

    def test_render_includes_all_baseline_readiness_lines(self):
        rendered = _render(
            {
                "run_id": "sandbox-1",
                "generated_at": "2026-04-04 10:00:00",
                "overall_status": "failed",
                "readiness_status": "sandbox_embodied_execution_phase1_in_progress",
                "freeze_gate_readiness": "freeze_gate_ready",
                "companion_readiness": "companion_autonomy_ready",
                "digital_embodiment_readiness": "digital_embodiment_phase2_ready",
                "summary": {"total": 1, "passed": 0, "failed": 1, "historical_pass_streak": 0},
                "recent_audits": [
                    {"run_id": "sandbox-1", "generated_at": "2026-04-04 10:00:00", "overall_status": "failed", "readiness_status": "sandbox_embodied_execution_phase1_in_progress"}
                ],
                "checks": [
                    {"id": "baseline_digital_embodiment_gate", "title": "Baseline", "status": "failed", "duration_s": 1.2, "command": "python ...", "failure_reasons": ["x"], "artifacts": {"json": "E:/repo/report.json"}},
                ],
            }
        )
        self.assertIn("Freeze Gate Readiness: `freeze_gate_ready`", rendered)
        self.assertIn("Companion Autonomy Readiness: `companion_autonomy_ready`", rendered)
        self.assertIn("Digital Embodiment Readiness: `digital_embodiment_phase2_ready`", rendered)


if __name__ == "__main__":
    unittest.main()
