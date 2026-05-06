import json
import tempfile
import unittest
from pathlib import Path

from evals.run_preserved_baselines_audit import (
    BASELINES,
    EXPECTED_READY,
    evaluate_preserved_baselines,
    load_statuses,
    load_latest_report,
    render_markdown,
    status_from_report,
)


class PreservedBaselinesAuditTests(unittest.TestCase):
    def test_expected_ready_covers_current_preserved_backend_chain(self):
        expected_ids = {
            "backend_freeze_gate",
            "companion_autonomy",
            "digital_embodiment",
            "sandbox_embodied_execution",
            "skills_ecosystem",
            "live_browser_runtime",
            "sandbox_phase2",
            "post_baseline_closure",
            "tts_presence_timing",
            "procedural_growth_phase1",
            "procedural_growth_phase2",
            "procedural_growth_phase3",
            "procedural_growth_phase4",
            "post_unlock_roadmap",
            "runtime_productization_phase1",
            "runtime_productization_phase2",
            "residual_living_loop_phase1",
            "living_loop_runtime_realism_phase1",
            "living_loop_runtime_realism_phase2",
            "embodied_interaction_runtime_phase1",
            "embodied_interaction_runtime_phase2",
        }

        self.assertEqual(set(EXPECTED_READY), expected_ids)
        self.assertEqual(set(BASELINES), expected_ids)

    def test_load_latest_report_uses_latest_ready_report_when_later_failed_probe_exists(self):
        with tempfile.TemporaryDirectory() as td:
            report_dir = Path(td)
            older_ready = report_dir / "sandbox-embodied-execution-audit-20260404-233428-phase1-closeout-d.json"
            later_failed = report_dir / "sandbox-embodied-execution-audit-20260405-123556-baseline.json"
            non_json = report_dir / "sandbox-embodied-execution-audit-20260405-130800-closeout-fix-f.md"
            older_ready.write_text(
                json.dumps(
                    {
                        "run_id": "older-ready",
                        "overall_status": "passed",
                        "readiness_status": "sandbox_embodied_execution_phase1_ready",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            later_failed.write_text(
                json.dumps(
                    {
                        "run_id": "later-failed-probe",
                        "overall_status": "failed",
                        "readiness_status": "sandbox_embodied_execution_phase1_in_progress",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            non_json.write_text("# not json\n", encoding="utf-8")

            selected = load_latest_report(
                report_dir,
                "sandbox-embodied-execution-audit-",
                expected_readiness="sandbox_embodied_execution_phase1_ready",
            )

        self.assertEqual(selected["run_id"], "older-ready")
        self.assertEqual(selected["report_path"], str(older_ready))

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
        self.assertEqual(summary["summary"]["total"], len(EXPECTED_READY))
        self.assertEqual(summary["summary"]["failed"], 1)
        self.assertEqual(summary["baselines"]["sandbox_phase2"]["status"], "failed")
        self.assertEqual(summary["baselines"]["sandbox_phase2"]["category"], "sandbox")
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
        self.assertEqual(summary["summary"]["passed"], len(EXPECTED_READY))
        self.assertEqual(summary["summary"]["failed"], 0)
        self.assertEqual(summary["summary"]["categories"]["procedural_growth"]["passed"], 4)
        self.assertEqual(summary["summary"]["categories"]["procedural_growth"]["failed"], 0)
        self.assertEqual(summary["summary"]["categories"]["post_unlock"]["passed"], 1)
        self.assertEqual(summary["summary"]["categories"]["productization"]["passed"], 2)
        self.assertEqual(summary["summary"]["categories"]["residual_closure"]["passed"], 1)
        self.assertEqual(summary["summary"]["categories"]["living_loop_realism"]["passed"], 2)
        self.assertEqual(summary["summary"]["categories"]["embodied_interaction"]["passed"], 2)

    def test_load_statuses_marks_missing_reports_explicitly(self):
        with tempfile.TemporaryDirectory() as td:
            statuses = load_statuses(Path(td))

        first_baseline = next(iter(BASELINES))
        first_prefix = BASELINES[first_baseline]
        self.assertEqual(statuses[first_baseline]["overall_status"], "missing")
        self.assertIn(f"missing_report:{first_prefix}", statuses[first_baseline]["failure_reasons"])

    def test_render_markdown_includes_compact_baseline_table(self):
        summary = {
            "generated_at": "2026-05-04 12:00:00",
            "overall_status": "failed",
            "readiness_status": "preserved_baselines_regressed",
            "summary": {
                "total": 2,
                "passed": 1,
                "failed": 1,
                "categories": {
                    "embodiment": {"total": 1, "passed": 1, "failed": 0},
                    "skills": {"total": 1, "passed": 0, "failed": 1},
                },
            },
            "baselines": {
                "digital_embodiment": {
                    "category": "embodiment",
                    "status": "passed",
                    "overall_status": "passed",
                    "readiness": "digital_embodiment_phase2_ready",
                    "expected_readiness": "digital_embodiment_phase2_ready",
                    "report_path": "digital.json",
                    "failure_reasons": [],
                },
                "skills_ecosystem": {
                    "category": "skills",
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
        self.assertIn("| Baseline | Category | Status | Overall | Readiness | Expected | Report |", rendered)
        self.assertIn("| `embodiment` | `1` | `1` | `0` |", rendered)
        self.assertIn("| `digital_embodiment` | `embodiment` | `passed` | `passed` | `digital_embodiment_phase2_ready`", rendered)
        self.assertIn("| `skills_ecosystem` | `skills` | `failed` | `passed` | `skills_ecosystem_in_progress`", rendered)
        self.assertIn("readiness=skills_ecosystem_in_progress expected=skills_ecosystem_ready", rendered)


if __name__ == "__main__":
    unittest.main()
