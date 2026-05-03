import json
import tempfile
import unittest
from pathlib import Path

from evals.run_preserved_baselines_audit import (
    EXPECTED_READY,
    evaluate_preserved_baselines,
    load_latest_report,
    render_markdown,
    status_from_report,
)


class PreservedBaselinesAuditTests(unittest.TestCase):
    def test_load_latest_report_uses_lexical_filename_order(self):
        with tempfile.TemporaryDirectory() as td:
            report_dir = Path(td)
            older = report_dir / "skills-ecosystem-audit-20260405-130543-closeout-fix-c.json"
            latest = report_dir / "skills-ecosystem-audit-20260405-130706-closeout-fix-e.json"
            non_json = report_dir / "skills-ecosystem-audit-20260405-130800-closeout-fix-f.md"
            older.write_text(json.dumps({"run_id": "older"}, ensure_ascii=False), encoding="utf-8")
            latest.write_text(json.dumps({"run_id": "latest"}, ensure_ascii=False), encoding="utf-8")
            non_json.write_text("# not json\n", encoding="utf-8")

            selected = load_latest_report(report_dir, "skills-ecosystem-audit-")

        self.assertEqual(selected["run_id"], "latest")
        self.assertEqual(selected["report_path"], str(latest))

    def test_status_from_report_extracts_status_and_readiness_variants(self):
        readiness_status = status_from_report(
            {
                "run_id": "digital",
                "overall_status": "passed",
                "readiness_status": "digital_embodiment_phase2_ready",
                "report_path": "digital.json",
            }
        )
        readiness = status_from_report(
            {
                "run_id": "browser",
                "overall_status": "passed",
                "readiness": "live_browser_runtime_phase1_ready",
                "report_path": "browser.json",
            }
        )

        self.assertEqual(readiness_status["overall_status"], "passed")
        self.assertEqual(readiness_status["readiness"], "digital_embodiment_phase2_ready")
        self.assertEqual(readiness["readiness"], "live_browser_runtime_phase1_ready")

    def test_evaluate_preserved_baselines_fails_when_any_baseline_is_not_ready(self):
        statuses = {
            baseline: {
                "overall_status": "passed",
                "readiness": expected,
                "report_path": f"{baseline}.json",
            }
            for baseline, expected in EXPECTED_READY.items()
        }
        statuses["sandbox_phase2"] = {
            "overall_status": "failed",
            "readiness": "sandbox_embodied_execution_phase2_in_progress",
            "report_path": "sandbox.json",
        }

        summary = evaluate_preserved_baselines(statuses)

        self.assertEqual(summary["overall_status"], "failed")
        self.assertEqual(summary["readiness_status"], "preserved_baselines_regressed")
        self.assertEqual(summary["summary"]["total"], 4)
        self.assertEqual(summary["summary"]["failed"], 1)
        self.assertEqual(summary["baselines"]["sandbox_phase2"]["status"], "failed")
        self.assertIn("overall_status=failed", summary["baselines"]["sandbox_phase2"]["failure_reasons"])
        self.assertIn(
            "readiness=sandbox_embodied_execution_phase2_in_progress expected=sandbox_embodied_execution_phase2_ready",
            summary["baselines"]["sandbox_phase2"]["failure_reasons"],
        )

    def test_evaluate_preserved_baselines_passes_when_all_latest_reports_are_ready(self):
        statuses = {
            baseline: {
                "overall_status": "passed",
                "readiness": expected,
                "report_path": f"{baseline}.json",
            }
            for baseline, expected in EXPECTED_READY.items()
        }

        summary = evaluate_preserved_baselines(statuses)

        self.assertEqual(summary["overall_status"], "passed")
        self.assertEqual(summary["readiness_status"], "preserved_baselines_ready")
        self.assertEqual(summary["summary"]["passed"], 4)
        self.assertEqual(summary["summary"]["failed"], 0)

    def test_render_markdown_includes_compact_baseline_table(self):
        summary = {
            "generated_at": "2026-05-04 12:00:00",
            "overall_status": "failed",
            "readiness_status": "preserved_baselines_regressed",
            "summary": {"total": 2, "passed": 1, "failed": 1},
            "baselines": {
                "digital_embodiment": {
                    "status": "passed",
                    "overall_status": "passed",
                    "readiness": "digital_embodiment_phase2_ready",
                    "expected_readiness": "digital_embodiment_phase2_ready",
                    "report_path": "digital.json",
                    "failure_reasons": [],
                },
                "skills_ecosystem": {
                    "status": "failed",
                    "overall_status": "passed",
                    "readiness": "skills_ecosystem_in_progress",
                    "expected_readiness": "skills_ecosystem_ready",
                    "report_path": "skills.json",
                    "failure_reasons": [
                        "readiness=skills_ecosystem_in_progress expected=skills_ecosystem_ready"
                    ],
                },
            },
        }

        rendered = render_markdown(summary)

        self.assertIn("# Preserved Baselines Audit", rendered)
        self.assertIn("| Baseline | Status | Overall | Readiness | Expected | Report |", rendered)
        self.assertIn("| `digital_embodiment` | `passed` | `passed` | `digital_embodiment_phase2_ready`", rendered)
        self.assertIn("| `skills_ecosystem` | `failed` | `passed` | `skills_ecosystem_in_progress`", rendered)
        self.assertIn("readiness=skills_ecosystem_in_progress expected=skills_ecosystem_ready", rendered)


if __name__ == "__main__":
    unittest.main()
