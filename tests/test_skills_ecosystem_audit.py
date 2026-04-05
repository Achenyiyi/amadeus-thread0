import json
import tempfile
import unittest
from pathlib import Path

from evals.print_latest_sandbox_baseline import _select_authoritative_report
from evals.run_skills_ecosystem_audit import (
    _build_check_specs,
    _finalize,
    _parse_baseline,
    _parse_smokes,
    _pass_streak,
    _render,
)


class SkillsEcosystemAuditTests(unittest.TestCase):
    def test_select_authoritative_report_prefers_latest_ready_pass(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "sandbox-embodied-execution-audit-20260405-100000-failed.json"
            ready = root / "sandbox-embodied-execution-audit-20260405-090000-ready.json"
            older_ready = root / "sandbox-embodied-execution-audit-20260405-080000-ready.json"
            older_ready.write_text(json.dumps({"overall_status": "passed", "readiness_status": "sandbox_embodied_execution_phase1_ready"}, ensure_ascii=False), encoding="utf-8")
            ready.write_text(json.dumps({"overall_status": "passed", "readiness_status": "sandbox_embodied_execution_phase1_ready"}, ensure_ascii=False), encoding="utf-8")
            failed.write_text(json.dumps({"overall_status": "failed", "readiness_status": "sandbox_embodied_execution_phase1_in_progress"}, ensure_ascii=False), encoding="utf-8")

            selected = _select_authoritative_report([older_ready, ready, failed])

        self.assertEqual(selected, ready)

    def test_parse_baseline_extracts_all_preserved_readiness_fields(self):
        with tempfile.TemporaryDirectory() as td:
            report_path = Path(td) / "sandbox.json"
            report_path.write_text(
                json.dumps(
                    {
                        "freeze_gate_readiness": "freeze_gate_ready",
                        "companion_readiness": "companion_autonomy_ready",
                        "digital_embodiment_readiness": "digital_embodiment_phase2_ready",
                        "readiness_status": "sandbox_embodied_execution_phase1_ready",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            parsed = _parse_baseline(
                "\n".join(
                    [
                        f"[sandbox-embodied-execution] json={report_path}",
                        f"[sandbox-embodied-execution] md={Path(td) / 'sandbox.md'}",
                        "[sandbox-embodied-execution] overall_status=passed",
                        "[sandbox-embodied-execution] readiness=sandbox_embodied_execution_phase1_ready",
                    ]
                )
            )
        self.assertEqual(parsed["freeze_gate_readiness"], "freeze_gate_ready")
        self.assertEqual(parsed["companion_readiness"], "companion_autonomy_ready")
        self.assertEqual(parsed["digital_embodiment_readiness"], "digital_embodiment_phase2_ready")
        self.assertEqual(parsed["sandbox_readiness"], "sandbox_embodied_execution_phase1_ready")

    def test_parse_smokes_extracts_artifact_paths(self):
        with tempfile.TemporaryDirectory() as td:
            report_path = Path(td) / "smokes.json"
            report_path.write_text(json.dumps({"passed": 5, "failed": 0}, ensure_ascii=False), encoding="utf-8")
            parsed = _parse_smokes(
                "\n".join(
                    [
                        f"[skills-ecosystem-smokes] json={report_path}",
                        f"[skills-ecosystem-smokes] md={Path(td) / 'smokes.md'}",
                        "[skills-ecosystem-smokes] overall_status=passed",
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

    def test_finalize_requires_preserved_baselines_and_streak(self):
        report = {
            "run_id": "skills-3",
            "generated_at": "2026-04-05 12:00:00",
            "overall_status": "passed",
            "readiness_status": "skills_ecosystem_in_progress",
            "summary": {"total": 8, "passed": 8, "failed": 0},
        }
        finalized = _finalize(
            report,
            [
                {"run_id": "skills-1", "generated_at": "2026-04-05 11:00:00", "overall_status": "passed", "readiness_status": "skills_ecosystem_in_progress"},
                {"run_id": "skills-2", "generated_at": "2026-04-05 11:30:00", "overall_status": "passed", "readiness_status": "skills_ecosystem_in_progress"},
            ],
            {
                "freeze_gate_readiness": "freeze_gate_ready",
                "companion_readiness": "companion_autonomy_ready",
                "digital_embodiment_readiness": "digital_embodiment_phase2_ready",
                "sandbox_readiness": "sandbox_embodied_execution_phase1_ready",
            },
        )
        self.assertEqual(finalized["readiness_status"], "skills_ecosystem_ready")
        self.assertEqual(finalized["recent_audits"][-1]["readiness_status"], "skills_ecosystem_ready")
        self.assertEqual(finalized["historical_pass_streak"], 3)

    def test_build_check_specs_covers_formal_closure_contract(self):
        ids = {item["id"] for item in _build_check_specs("demo")}
        self.assertEqual(
            ids,
            {
                "baseline_sandbox_execution_gate",
                "skills_registry_lock_truth",
                "skills_progressive_disclosure",
                "skills_approval_payload_immutability",
                "skills_auto_match_manual_override_precedence",
                "skills_persona_core_isolation",
                "skills_legacy_compatibility_isolation",
                "skills_manual_smokes",
            },
        )

    def test_render_includes_all_preserved_baseline_lines(self):
        rendered = _render(
            {
                "run_id": "skills-1",
                "generated_at": "2026-04-05 12:00:00",
                "overall_status": "failed",
                "readiness_status": "skills_ecosystem_in_progress",
                "freeze_gate_readiness": "freeze_gate_ready",
                "companion_readiness": "companion_autonomy_ready",
                "digital_embodiment_readiness": "digital_embodiment_phase2_ready",
                "sandbox_readiness": "sandbox_embodied_execution_phase1_ready",
                "summary": {"total": 1, "passed": 0, "failed": 1, "historical_pass_streak": 0},
                "recent_audits": [
                    {"run_id": "skills-1", "generated_at": "2026-04-05 12:00:00", "overall_status": "failed", "readiness_status": "skills_ecosystem_in_progress"}
                ],
                "checks": [
                    {"id": "skills_manual_smokes", "title": "Skills Manual Smokes", "status": "failed", "duration_s": 1.2, "command": "python ..."}
                ],
            }
        )
        self.assertIn("Freeze Gate Readiness: `freeze_gate_ready`", rendered)
        self.assertIn("Companion Autonomy Readiness: `companion_autonomy_ready`", rendered)
        self.assertIn("Digital Embodiment Readiness: `digital_embodiment_phase2_ready`", rendered)
        self.assertIn("Sandbox Readiness: `sandbox_embodied_execution_phase1_ready`", rendered)


if __name__ == "__main__":
    unittest.main()
