import unittest

from amadeus_thread0.graph_parts.persona_runtime import (
    _is_external_probe_context,
    _science_mode_from_context,
    _tsundere_next,
)


class PersonaRuntimeTests(unittest.TestCase):
    def test_science_mode_ignores_lab_environment_mentions_without_task_intent(self):
        self.assertFalse(_science_mode_from_context("今天实验室居然安静得让人发毛。"))
        self.assertFalse(_science_mode_from_context("我今天在实验室待到现在。"))

    def test_science_mode_requires_explicit_problem_solving_signal(self):
        self.assertTrue(_science_mode_from_context("实验又卡住了，你轻轻拎我一下。"))
        self.assertTrue(_science_mode_from_context("我想把这个实验方案拆成三步，顺便解释一下统计检验怎么选。"))
        self.assertTrue(_science_mode_from_context("模型怎么还是不收敛。"))

    def test_science_mode_infers_from_recent_context_when_user_reopens_gently(self):
        self.assertTrue(
            _science_mode_from_context(
                "按平时那样带我一下。",
                previous_user_text="我想把这个实验方案拆成三步，顺便解释一下统计检验怎么选。",
            )
        )

    def test_science_mode_does_not_inherit_from_assistant_technical_wording_alone(self):
        self.assertFalse(
            _science_mode_from_context(
                "你别装普通寒暄，正常回我嘛。",
                previous_user_text="其实也没别的事。",
                previous_assistant_text="别误会，我只是刚好也没在忙什么重要的实验而已。",
            )
        )

    def test_external_probe_detects_rolebench_and_probe_counterpart(self):
        self.assertTrue(
            _is_external_probe_context(
                persona_core={"character_id": "rolebench_kurisu"},
                counterpart_profile={"counterpart_id": "okabe"},
            )
        )
        self.assertTrue(
            _is_external_probe_context(
                persona_core={"character_id": "kurisu_amadeus"},
                counterpart_profile={"counterpart_id": "external_probe_user"},
            )
        )
        self.assertTrue(
            _is_external_probe_context(
                persona_core={"character_id": "charactereval_amadeus"},
                counterpart_profile={"counterpart_id": "okabe"},
            )
        )

    def test_tsundere_next_reflects_care_vs_conflict_pressure(self):
        caring = _tsundere_next(
            0.55,
            emotion_label="care",
            appraisal={"signals": {"care": True}},
            bond_state={"closeness": 0.78, "hurt": 0.02},
            world_model_state={"tension_load": 0.12, "boundary_load": 0.10},
        )
        conflict = _tsundere_next(
            0.55,
            emotion_label="angry",
            appraisal={"signals": {"conflict": True}},
            bond_state={"closeness": 0.46, "hurt": 0.20},
            world_model_state={"tension_load": 0.64, "boundary_load": 0.58},
        )
        self.assertLess(caring, 0.55)
        self.assertGreater(conflict, 0.55)


if __name__ == "__main__":
    unittest.main()
