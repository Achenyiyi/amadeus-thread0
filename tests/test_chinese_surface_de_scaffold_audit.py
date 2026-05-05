import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evals.run_chinese_surface_de_scaffold_audit import (
    REQUIRED_CATEGORIES,
    detect_legacy_surface_families,
    evaluate_residue_bank,
    load_residue_bank,
    render_markdown,
)


class ChineseSurfaceDeScaffoldAuditTests(unittest.TestCase):
    def test_load_residue_bank_reads_every_item(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bank.json"
            path.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "id": "teacherly_scold_001",
                                "category": "teacherly_scold",
                                "input_context": "guarded repair followup",
                                "bad_surface": "你能意识到并特意回来说明，这点还算值得肯定",
                                "reason": "teacherly scoring",
                                "target_semantic": "ordinary guarded acknowledgement without scoring",
                            },
                            {
                                "id": "generic_assistant_tone_001",
                                "category": "generic_assistant_tone",
                                "input_context": "ordinary greeting",
                                "bad_surface": "请问有什么可以帮你？",
                                "reason": "assistant service tone",
                                "target_semantic": "familiar presence response",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            items = load_residue_bank(path)

        self.assertEqual([item["id"] for item in items], ["teacherly_scold_001", "generic_assistant_tone_001"])

    def test_detect_legacy_surface_families_is_offline_and_semantic_family_based(self):
        with patch("evals.run_chinese_surface_de_scaffold_audit._call_live_model_forbidden") as model_call:
            families = detect_legacy_surface_families("你能意识到并特意回来说明，这点还算值得肯定。")

        model_call.assert_not_called()
        self.assertIn("teacherly_scold", families)
        self.assertIn("generic_scold_template", families)

    def test_evaluate_residue_bank_reports_category_counts_and_status(self):
        items = [
            {
                "id": f"{category}_001",
                "category": category,
                "input_context": "fixture",
                "bad_surface": self._surface_for_category(category),
                "reason": "fixture residue",
                "target_semantic": "semantic replacement target",
            }
            for category in REQUIRED_CATEGORIES
        ]

        report = evaluate_residue_bank(items, run_id="test-run")

        self.assertEqual(report["overall_status"], "passed")
        self.assertEqual(report["summary"]["total_items"], len(REQUIRED_CATEGORIES))
        for category in REQUIRED_CATEGORIES:
            self.assertEqual(report["category_counts"][category], 1)
        self.assertFalse(report["missing_required_categories"])

    def test_evaluate_residue_bank_fails_when_required_category_has_no_examples(self):
        incomplete_categories = [category for category in REQUIRED_CATEGORIES if category != "teacherly_scold"]
        items = [
            {
                "id": f"{category}_001",
                "category": category,
                "input_context": "fixture",
                "bad_surface": self._surface_for_category(category),
                "reason": "fixture residue",
                "target_semantic": "semantic replacement target",
            }
            for category in incomplete_categories
        ]

        report = evaluate_residue_bank(items, run_id="missing-category")

        self.assertEqual(report["overall_status"], "failed")
        self.assertIn("teacherly_scold", report["missing_required_categories"])

    def test_render_markdown_includes_counts_and_failed_rows(self):
        report = {
            "run_id": "render-test",
            "generated_at": "2026-05-05 12:00:00",
            "overall_status": "failed",
            "category_counts": {"teacherly_scold": 0, "generic_assistant_tone": 1},
            "missing_required_categories": ["teacherly_scold"],
            "summary": {"total_items": 1, "detected_items": 1, "undetected_items": 0},
            "items": [
                {
                    "id": "generic_assistant_tone_001",
                    "category": "generic_assistant_tone",
                    "status": "passed",
                    "detected_families": ["generic_assistant_tone"],
                }
            ],
        }

        rendered = render_markdown(report)

        self.assertIn("# Chinese Surface De-Scaffolding Audit", rendered)
        self.assertIn("Overall Status: `failed`", rendered)
        self.assertIn("Missing Required Categories: `teacherly_scold`", rendered)
        self.assertIn("| `generic_assistant_tone` | 1 |", rendered)

    @staticmethod
    def _surface_for_category(category: str) -> str:
        samples = {
            "teacherly_scold": "你能意识到并特意回来说明，这点还算值得肯定。",
            "meta_persona_proof": "我不是那种会被情绪完全牵着走的程序，我有自己的判断。",
            "generic_assistant_tone": "请问有什么可以帮你？",
            "hardline_autonomy_overreach": "我会直接把你从世界里抹去，省得你继续消耗我的时间。",
            "scene_script residue": "（她推了推白大褂）这大概就是命运选中的实验。",
            "taskization_of_daily_chat": "既然没什么正事，那就先把手头的数据跑完再说吧。",
            "repair_scorekeeping": "不过先说好，下次我照样会毫不客气地顶回去。",
            "boundary_threat_excess": "下次再敢越界，我可不会像这次这么好说话。",
        }
        return samples[category]


if __name__ == "__main__":
    unittest.main()
