import unittest

from amadeus_thread0.graph_parts.persona_runtime import (
    _is_external_probe_context,
    _science_mode_from_context,
    _tsundere_next,
)


class PersonaRuntimeTests(unittest.TestCase):
    def test_science_mode_infers_from_recent_context_when_user_reopens_gently(self):
        self.assertTrue(
            _science_mode_from_context(
                "按平时那样带我一下。",
                previous_user_text="我想把这个实验方案拆成三步，顺便解释一下统计检验怎么选。",
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
