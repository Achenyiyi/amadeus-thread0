import json
import tempfile
import unittest
from pathlib import Path

from evals.run_sandbox_phase2_audit import (
    _build_check_specs,
    _finalize,
    _parse_live_browser_baseline,
    _parse_smokes,
    _pass_streak,
    _render,
)


class SandboxPhase2AuditTests(unittest.TestCase):
    def test_parse_live_browser_baseline_extracts_preserved_readiness(self):
        with tempfile.TemporaryDirectory() as td:
            report_path = Path(td) / "live.json"
            report_path.write_text(
                json.dumps(
                    {
                        "freeze_gate_readiness": "freeze_gate_ready",
                        "companion_readiness": "companion_autonomy_ready",
                        "digital_embodiment_readiness": "digital_embodiment_phase2_ready",
                        "sandbox_readiness": "sandbox_embodied_execution_phase1_ready",
                        "skills_readiness": "skills_ecosystem_ready",
                        "readiness_status": "live_browser_runtime_phase1_ready",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            parsed = _parse_live_browser_baseline(
                "\n".join(
                    [
                        f"[live-browser-runtime] json={report_path}",
                        f"[live-browser-runtime] md={Path(td) / 'live.md'}",
                        "[live-browser-runtime] overall_status=passed",
                        "[live-browser-runtime] readiness=live_browser_runtime_phase1_ready",
                    ]
                )
            )
        self.assertEqual(parsed["freeze_gate_readiness"], "freeze_gate_ready")
        self.assertEqual(parsed["sandbox_readiness"], "sandbox_embodied_execution_phase1_ready")
        self.assertEqual(parsed["skills_readiness"], "skills_ecosystem_ready")
        self.assertEqual(parsed["live_browser_readiness"], "live_browser_runtime_phase1_ready")

    def test_parse_smokes_extracts_report_paths(self):
        with tempfile.TemporaryDirectory() as td:
            report_path = Path(td) / "smokes.json"
            report_path.write_text(json.dumps({"passed": 5, "failed": 0}, ensure_ascii=False), encoding="utf-8")
            parsed = _parse_smokes(
                "\n".join(
                    [
                        f"[sandbox-phase2-smokes] json={report_path}",
                        f"[sandbox-phase2-smokes] md={Path(td) / 'smokes.md'}",
                        "[sandbox-phase2-smokes] overall_status=passed",
                    ]
                )
            )
        self.assertEqual(parsed["json"], str(report_path))
        self.assertEqual(parsed["overall_status"], "passed")
        self.assertEqual(parsed["passed"], "5")

    def test_pass_streak_counts_only_trailing_passes(self):
        self.assertEqual(_pass_streak(["passed", "passed", "passed"]), 3)
        self.assertEqual(_pass_streak(["passed", "failed", "passed"]), 1)
        self.assertEqual(_pass_streak(["failed"]), 0)

    def test_finalize_requires_all_preserved_baselines_and_streak(self):
        report = {
            "run_id": "sandbox-phase2-3",
            "generated_at": "2026-04-07 10:00:00",
            "overall_status": "passed",
            "readiness_status": "sandbox_embodied_execution_phase2_in_progress",
            "summary": {"total": 4, "passed": 4, "failed": 0},
        }
        finalized = _finalize(
            report,
            [
                {
                    "run_id": "sandbox-phase2-1",
                    "generated_at": "2026-04-07 08:00:00",
                    "overall_status": "passed",
                    "readiness_status": "sandbox_embodied_execution_phase2_in_progress",
                },
                {
                    "run_id": "sandbox-phase2-2",
                    "generated_at": "2026-04-07 09:00:00",
                    "overall_status": "passed",
                    "readiness_status": "sandbox_embodied_execution_phase2_in_progress",
                },
            ],
            {
                "freeze_gate_readiness": "freeze_gate_ready",
                "companion_readiness": "companion_autonomy_ready",
                "digital_embodiment_readiness": "digital_embodiment_phase2_ready",
                "sandbox_readiness": "sandbox_embodied_execution_phase1_ready",
                "skills_readiness": "skills_ecosystem_ready",
                "live_browser_readiness": "live_browser_runtime_phase1_ready",
            },
        )
        self.assertEqual(finalized["readiness_status"], "sandbox_embodied_execution_phase2_ready")
        self.assertEqual(finalized["recent_audits"][-1]["readiness_status"], "sandbox_embodied_execution_phase2_ready")
        self.assertEqual(finalized["historical_pass_streak"], 3)

    def test_build_check_specs_covers_phase_two_contract(self):
        ids = {item["id"] for item in _build_check_specs("demo")}
        self.assertEqual(
            ids,
            {
                "baseline_live_browser_gate",
                "sandbox_phase2_manual_smokes",
                "sandbox_phase2_runtime_contract",
                "sandbox_phase2_backend_writeback_residue",
            },
        )

    def test_render_includes_all_preserved_readiness_lines(self):
        rendered = _render(
            {
                "run_id": "sandbox-phase2-1",
                "generated_at": "2026-04-07 10:00:00",
                "overall_status": "failed",
                "readiness_status": "sandbox_embodied_execution_phase2_in_progress",
                "freeze_gate_readiness": "freeze_gate_ready",
                "companion_readiness": "companion_autonomy_ready",
                "digital_embodiment_readiness": "digital_embodiment_phase2_ready",
                "sandbox_readiness": "sandbox_embodied_execution_phase1_ready",
                "skills_readiness": "skills_ecosystem_ready",
                "live_browser_readiness": "live_browser_runtime_phase1_ready",
                "summary": {"total": 1, "passed": 0, "failed": 1, "historical_pass_streak": 0},
                "recent_audits": [
                    {
                        "run_id": "sandbox-phase2-1",
                        "generated_at": "2026-04-07 10:00:00",
                        "overall_status": "failed",
                        "readiness_status": "sandbox_embodied_execution_phase2_in_progress",
                    }
                ],
                "checks": [
                    {
                        "id": "baseline_live_browser_gate",
                        "title": "Baseline",
                        "status": "failed",
                        "duration_s": 1.2,
                        "command": "python ...",
                        "failure_reasons": ["x"],
                        "artifacts": {"json": "E:/repo/report.json"},
                    },
                ],
            }
        )
        self.assertIn("Freeze Gate Readiness: `freeze_gate_ready`", rendered)
        self.assertIn("Sandbox Phase 1 Readiness: `sandbox_embodied_execution_phase1_ready`", rendered)
        self.assertIn("Skills Readiness: `skills_ecosystem_ready`", rendered)
        self.assertIn("Live Browser Readiness: `live_browser_runtime_phase1_ready`", rendered)


if __name__ == "__main__":
    unittest.main()
