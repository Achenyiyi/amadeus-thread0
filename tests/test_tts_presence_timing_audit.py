import json
import tempfile
import unittest
from pathlib import Path

from evals.run_tts_presence_timing_audit import (
    _aggregate_overall_status,
    _build_check_specs,
    _finalize_report,
    _parse_smokes,
    _render_markdown,
)


class TtsPresenceTimingAuditTests(unittest.TestCase):
    def test_parse_smokes_extracts_report_paths(self):
        with tempfile.TemporaryDirectory() as td:
            report_path = Path(td) / "smokes.json"
            report_path.write_text(
                json.dumps({"passed": 3, "failed": 0, "overall_status": "passed"}, ensure_ascii=False),
                encoding="utf-8",
            )
            parsed = _parse_smokes(
                "\n".join(
                    [
                        f"[tts-presence-timing-smokes] json={report_path}",
                        f"[tts-presence-timing-smokes] md={Path(td) / 'smokes.md'}",
                        "[tts-presence-timing-smokes] overall_status=passed",
                    ]
                )
            )

        self.assertEqual(parsed["json"], str(report_path))
        self.assertEqual(parsed["overall_status"], "passed")
        self.assertEqual(parsed["passed"], "3")

    def test_aggregate_overall_status_requires_all_checks_to_pass(self):
        report = _aggregate_overall_status(
            [
                {"id": "tts_presence_smokes", "status": "passed", "blocking": True},
                {"id": "tts_presence_audit", "status": "passed", "blocking": True},
            ]
        )

        self.assertEqual(report["overall_status"], "passed")
        self.assertEqual(report["readiness_status"], "tts_presence_timing_ready")
        self.assertEqual(report["blocking_failure_ids"], [])

    def test_finalize_report_keeps_recent_history_and_readiness_aligned(self):
        preliminary = {
            "run_id": "tts-audit-1",
            "generated_at": "2026-05-05 10:00:00",
            "overall_status": "passed",
            "readiness_status": "tts_presence_timing_in_progress",
            "summary": {"total": 2, "passed": 2, "failed": 0},
        }
        finalized = _finalize_report(
            preliminary,
            previous_rows=[
                {
                    "run_id": "tts-audit-0",
                    "generated_at": "2026-05-05 09:00:00",
                    "overall_status": "passed",
                    "readiness_status": "tts_presence_timing_in_progress",
                }
            ],
        )

        self.assertEqual(finalized["readiness_status"], "tts_presence_timing_ready")
        self.assertEqual(finalized["recent_audits"][-1]["readiness_status"], "tts_presence_timing_ready")
        self.assertEqual(finalized["summary"]["historical_pass_streak"], 2)

    def test_render_markdown_includes_tts_readiness_line(self):
        rendered = _render_markdown(
            {
                "run_id": "tts-audit-1",
                "generated_at": "2026-05-05 10:00:00",
                "overall_status": "passed",
                "readiness_status": "tts_presence_timing_ready",
                "summary": {"total": 1, "passed": 1, "failed": 0, "historical_pass_streak": 1},
                "recent_audits": [
                    {
                        "run_id": "tts-audit-1",
                        "generated_at": "2026-05-05 10:00:00",
                        "overall_status": "passed",
                        "readiness_status": "tts_presence_timing_ready",
                    }
                ],
                "checks": [
                    {
                        "id": "tts_presence_smokes",
                        "title": "TTS Presence Smokes",
                        "status": "passed",
                        "duration_s": 1.0,
                        "command": "python evals/run_tts_presence_timing_smokes.py",
                        "artifacts": {"json": "E:/repo/report.json"},
                    }
                ],
            }
        )

        self.assertIn("Readiness: `tts_presence_timing_ready`", rendered)
        self.assertIn("`tts_presence_smokes`", rendered)
        self.assertIn("`json`", rendered)

    def test_build_check_specs_covers_tts_slice(self):
        ids = {item["id"] for item in _build_check_specs(run_id="demo")}
        self.assertEqual(
            ids,
            {
                "tts_presence_smokes",
                "tts_presence_audit_contract",
                "tts_presence_render_contract",
            },
        )


if __name__ == "__main__":
    unittest.main()
