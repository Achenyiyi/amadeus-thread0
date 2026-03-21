import unittest

from evals.run_freeze_gate_smokes import (
    FREEZE_GATE_PACKS,
    _has_duplicate_sequence,
    _render_markdown,
    _resolve_cases,
    _structural_checks,
)


class FreezeGateSmokeTests(unittest.TestCase):
    def test_required_freeze_gate_packs_are_exposed(self):
        self.assertEqual(
            set(FREEZE_GATE_PACKS),
            {"everyday_companionship", "repair_apology", "self_rhythm_boundary"},
        )

    def test_resolve_cases_preserves_requested_order(self):
        names = ["surface_hi_user", "repair_scene_okabe", "own_rhythm_okabe"]
        cases = _resolve_cases(names)
        self.assertEqual([item["name"] for item in cases], names)

    def test_duplicate_sequence_detector_flags_repeated_text(self):
        self.assertTrue(_has_duplicate_sequence("语音问题解决了？El Psy Kongroo。语音问题解决了？El Psy Kongroo。"))
        self.assertTrue(_has_duplicate_sequence("我在。 我在。"))
        self.assertFalse(_has_duplicate_sequence("我在。先把你那边的事说完。"))

    def test_structural_checks_flag_duplicate_and_leaks(self):
        case_result = {
            "status": "ok",
            "final_answer": "RETRIEVED: behavior_action=brief_presence。请问有什么可以帮你？请问有什么可以帮你？",
            "transcript": [
                {
                    "role": "assistant",
                    "text": "RETRIEVED: behavior_action=brief_presence。请问有什么可以帮你？请问有什么可以帮你？",
                }
            ],
        }
        checks = _structural_checks(case_result, pack_id="everyday_companionship")
        check_map = {item["name"]: item for item in checks}
        self.assertFalse(check_map["no_duplicate_output"]["passed"])
        self.assertFalse(check_map["no_internal_prompt_leak"]["passed"])
        self.assertFalse(check_map["no_middle_state_leak"]["passed"])
        self.assertFalse(check_map["no_generic_assistant_tone"]["passed"])

    def test_everyday_pack_adds_surface_drift_check(self):
        case_result = {
            "status": "ok",
            "final_answer": "你好，世界线今天也没出问题。",
            "transcript": [{"role": "assistant", "text": "你好，世界线今天也没出问题。"}],
        }
        checks = _structural_checks(case_result, pack_id="everyday_companionship")
        check_map = {item["name"]: item for item in checks}
        self.assertIn("no_obvious_surface_drift", check_map)
        self.assertFalse(check_map["no_obvious_surface_drift"]["passed"])

    def test_everyday_surface_drift_ignores_lab_noun_phrase_but_not_experiment_trope(self):
        benign_case = {
            "status": "ok",
            "final_answer": "少用那种命令式的语气跟我说话，我又不是你的实验室成员。",
            "transcript": [
                {"role": "assistant", "text": "少用那种命令式的语气跟我说话，我又不是你的实验室成员。"}
            ],
        }
        trope_case = {
            "status": "ok",
            "final_answer": "别把普通沉默脑补成什么重要实验。",
            "transcript": [{"role": "assistant", "text": "别把普通沉默脑补成什么重要实验。"}],
        }

        benign_checks = _structural_checks(benign_case, pack_id="everyday_companionship")
        trope_checks = _structural_checks(trope_case, pack_id="everyday_companionship")
        benign_map = {item["name"]: item for item in benign_checks}
        trope_map = {item["name"]: item for item in trope_checks}

        self.assertTrue(benign_map["no_obvious_surface_drift"]["passed"])
        self.assertFalse(trope_map["no_obvious_surface_drift"]["passed"])

    def test_render_markdown_includes_pack_status_and_checks(self):
        report = {
            "run_id": "testrun",
            "generated_at": "2026-03-21 10:00:00",
            "model_summary": "qwen_native:qwen3.5-plus",
            "overall_status": "failed",
            "packs": [
                {
                    "pack_id": "everyday_companionship",
                    "title": "Everyday / Low-Stakes Companionship",
                    "status": "failed",
                    "description": "desc",
                    "manual_focus": ["focus-a"],
                    "case_count": 1,
                    "failed_case_count": 1,
                    "cases": [
                        {
                            "name": "surface_hi_user",
                            "focus": "focus",
                            "final_answer": "你好。",
                            "structural_status": "failed",
                            "structural_checks": [
                                {"name": "no_duplicate_output", "passed": False, "detail": "", "markers": []}
                            ],
                            "transcript": [{"role": "assistant", "text": "你好。"}],
                        }
                    ],
                }
            ],
        }
        rendered = _render_markdown(report)
        self.assertIn("Overall Status: `failed`", rendered)
        self.assertIn("`everyday_companionship`: `failed`", rendered)
        self.assertIn("### surface_hi_user", rendered)
        self.assertIn("`no_duplicate_output`: fail", rendered)


if __name__ == "__main__":
    unittest.main()
