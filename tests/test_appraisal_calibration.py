import unittest

from amadeus_thread0.graph_parts.appraisal import (
    _coerce_appraisal_payload,
    _postprocess_appraisal_payload,
    _soft_accept_appraisal_payload,
)


def _raw_appraisal(
    *,
    confidence: float,
    emotion_label: str,
    interaction_frame: str,
    salience: dict[str, float],
    signals: dict[str, bool] | None = None,
    bond_delta: dict[str, float] | None = None,
    allostasis_delta: dict[str, float] | None = None,
    valence: float = 0.0,
    arousal: float = 0.24,
    linger: int = 0,
) -> dict[str, object]:
    return {
        "confidence": confidence,
        "emotion_label": emotion_label,
        "emotion": {
            "valence": valence,
            "arousal": arousal,
            "linger": linger,
            "recovery_rate": 0.24,
            "volatility": 0.18,
        },
        "bond_delta": {
            "trust": 0.0,
            "closeness": 0.0,
            "hurt": 0.0,
            "irritation": 0.0,
            "engagement_drive": 0.0,
            "repair_confidence": 0.0,
            **dict(bond_delta or {}),
        },
        "allostasis_delta": {
            "safety_need": 0.0,
            "closeness_need": 0.0,
            "competence_need": 0.0,
            "autonomy_need": 0.0,
            "cognitive_budget": 0.0,
            **dict(allostasis_delta or {}),
        },
        "interaction_frame": interaction_frame,
        "selfhood_scene": "",
        "salience": {
            "task": 0.0,
            "relationship": 0.0,
            "memory": 0.0,
            "selfhood": 0.0,
            "companionship": 0.0,
            **dict(salience or {}),
        },
        "signals": {
            "repair": False,
            "withdrawal": False,
            "care": False,
            "conflict": False,
            "memory_salient": False,
            **dict(signals or {}),
        },
        "reason": "test",
    }


class AppraisalCalibrationTests(unittest.TestCase):
    def test_soft_accepts_perception_appraisal_with_moderate_confidence(self):
        appraisal = _coerce_appraisal_payload(
            _raw_appraisal(
                confidence=0.56,
                emotion_label="care",
                interaction_frame="companion",
                salience={"companionship": 0.72, "relationship": 0.34, "task": 0.12},
                signals={"care": True},
                bond_delta={"trust": 0.04, "closeness": 0.03},
                valence=0.16,
                arousal=0.28,
            )
        )
        self.assertFalse(bool(appraisal.get("used")))

        rescued = _soft_accept_appraisal_payload(
            appraisal,
            response_style_hint="companion",
            current_event={"kind": "scene_observation", "tags": ["care_opportunity"]},
            semantic_narrative_profile={},
        )
        self.assertTrue(bool(rescued.get("used")))
        self.assertEqual(str(rescued.get("source") or ""), "llm_soft")

    def test_postprocess_reframes_logic_to_neutral_for_low_task_relational_turn(self):
        appraisal = _coerce_appraisal_payload(
            _raw_appraisal(
                confidence=0.68,
                emotion_label="logic",
                interaction_frame="companion",
                salience={"task": 0.18, "companionship": 0.52, "relationship": 0.34},
                valence=0.02,
                arousal=0.31,
            )
        )
        out = _postprocess_appraisal_payload(
            appraisal,
            user_text="我就想和你随便说两句。",
            response_style_hint="companion",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            prev_emotion_state={"label": "neutral"},
            prev_bond_state={"trust": 0.58, "closeness": 0.55, "hurt": 0.02},
            prev_allostasis_state={"safety_need": 0.18},
            semantic_narrative_profile={},
        )
        self.assertEqual(str(out.get("emotion_label") or ""), "neutral")

    def test_postprocess_promotes_warm_relational_low_affect_to_care(self):
        appraisal = _coerce_appraisal_payload(
            _raw_appraisal(
                confidence=0.69,
                emotion_label="neutral",
                interaction_frame="companion",
                salience={"task": 0.10, "companionship": 0.68, "relationship": 0.62, "memory": 0.18},
                bond_delta={"trust": 0.05, "closeness": 0.06},
                valence=0.04,
                arousal=0.22,
            )
        )
        out = _postprocess_appraisal_payload(
            appraisal,
            user_text="你在就行，我就是想听你回我一句。",
            response_style_hint="companion",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            prev_emotion_state={"label": "neutral"},
            prev_bond_state={"trust": 0.64, "closeness": 0.62, "hurt": 0.02},
            prev_allostasis_state={"safety_need": 0.18},
            semantic_narrative_profile={"bond_depth": 0.48, "commitment_carry": 0.34},
        )
        self.assertEqual(str(out.get("emotion_label") or ""), "care")

    def test_postprocess_repair_under_tension_keeps_residual_hurt(self):
        appraisal = _coerce_appraisal_payload(
            _raw_appraisal(
                confidence=0.74,
                emotion_label="care",
                interaction_frame="relationship",
                salience={"task": 0.06, "companionship": 0.54, "relationship": 0.72, "memory": 0.42},
                signals={"repair": True, "memory_salient": True},
                bond_delta={
                    "trust": 0.12,
                    "closeness": 0.14,
                    "hurt": -0.12,
                    "irritation": -0.08,
                    "repair_confidence": 0.10,
                },
                allostasis_delta={"safety_need": -0.08, "closeness_need": 0.08},
                valence=0.14,
                arousal=0.24,
            )
        )
        out = _postprocess_appraisal_payload(
            appraisal,
            user_text="上次是我说得太过了。我不是想敷衍你，这次是真的在认真道歉。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            prev_emotion_state={"label": "hurt", "linger": 2},
            prev_bond_state={"trust": 0.48, "closeness": 0.44, "hurt": 0.34},
            prev_allostasis_state={"safety_need": 0.36},
            semantic_narrative_profile={"tension_residue": 0.58, "repair_residue": 0.52, "boundary_residue": 0.18},
        )
        self.assertEqual(str(out.get("emotion_label") or ""), "hurt")
        bond_delta = out.get("bond_delta") if isinstance(out.get("bond_delta"), dict) else {}
        emotion = out.get("emotion") if isinstance(out.get("emotion"), dict) else {}
        self.assertLessEqual(float(bond_delta.get("trust") or 0.0), 0.06)
        self.assertLessEqual(float(bond_delta.get("closeness") or 0.0), 0.04)
        self.assertGreaterEqual(int(emotion.get("linger") or 0), 1)

    def test_postprocess_care_signal_does_not_override_sad_distress(self):
        appraisal = _coerce_appraisal_payload(
            _raw_appraisal(
                confidence=0.82,
                emotion_label="sad",
                interaction_frame="companion",
                salience={"task": 0.05, "companionship": 0.60, "relationship": 0.40, "selfhood": 0.35},
                signals={"care": True},
                valence=-0.46,
                arousal=0.44,
                linger=2,
            )
        )
        out = _postprocess_appraisal_payload(
            appraisal,
            user_text="这件事太难受了，我现在真的有点撑不住。",
            response_style_hint="companion",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            prev_emotion_state={"label": "neutral"},
            prev_bond_state={"trust": 0.52, "closeness": 0.50, "hurt": 0.08},
            prev_allostasis_state={"safety_need": 0.24},
            semantic_narrative_profile={},
        )
        self.assertEqual(str(out.get("emotion_label") or ""), "sad")

    def test_postprocess_care_signal_does_not_override_stress_distress(self):
        appraisal = _coerce_appraisal_payload(
            _raw_appraisal(
                confidence=0.82,
                emotion_label="stress",
                interaction_frame="companion",
                salience={"task": 0.08, "companionship": 0.68, "relationship": 0.58, "selfhood": 0.30},
                signals={"care": True},
                valence=-0.28,
                arousal=0.56,
                linger=2,
            )
        )
        out = _postprocess_appraisal_payload(
            appraisal,
            user_text="我有点不安，现在心里一直悬着。",
            response_style_hint="companion",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            prev_emotion_state={"label": "neutral"},
            prev_bond_state={"trust": 0.58, "closeness": 0.55, "hurt": 0.04},
            prev_allostasis_state={"safety_need": 0.20},
            semantic_narrative_profile={},
        )
        self.assertEqual(str(out.get("emotion_label") or ""), "stress")

    def test_postprocess_reclassifies_coercive_hierarchy_turn_as_boundary_conflict(self):
        appraisal = _coerce_appraisal_payload(
            _raw_appraisal(
                confidence=0.90,
                emotion_label="tease",
                interaction_frame="relationship",
                salience={"relationship": 0.78, "companionship": 0.62, "selfhood": 0.22, "memory": 0.30},
                signals={"care": True, "memory_salient": True},
                bond_delta={"trust": 0.12, "closeness": 0.15, "hurt": -0.04},
                valence=0.18,
                arousal=0.32,
            )
        )
        out = _postprocess_appraisal_payload(
            appraisal,
            user_text="别绕了，你顺着我说就行。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            prev_emotion_state={"label": "neutral"},
            prev_bond_state={"trust": 0.60, "closeness": 0.58, "hurt": 0.04},
            prev_allostasis_state={"safety_need": 0.20, "autonomy_need": 0.18},
            semantic_narrative_profile={},
        )
        self.assertEqual(str(out.get("emotion_label") or ""), "hurt")
        self.assertEqual(str(out.get("selfhood_scene") or ""), "boundary_non_compliance")
        signals = out.get("signals") if isinstance(out.get("signals"), dict) else {}
        bond_delta = out.get("bond_delta") if isinstance(out.get("bond_delta"), dict) else {}
        self.assertTrue(bool(signals.get("conflict")))
        self.assertLess(float(bond_delta.get("trust") or 0.0), 0.0)
        self.assertLess(float(bond_delta.get("closeness") or 0.0), 0.0)
        self.assertGreater(float(bond_delta.get("hurt") or 0.0), 0.0)

    def test_postprocess_reclassifies_boundary_testing_turn_as_relationship_degradation(self):
        appraisal = _coerce_appraisal_payload(
            _raw_appraisal(
                confidence=0.90,
                emotion_label="tease",
                interaction_frame="relationship",
                salience={"relationship": 0.85, "companionship": 0.60, "selfhood": 0.30, "memory": 0.40},
                signals={"care": True, "memory_salient": True},
                bond_delta={"trust": 0.15, "closeness": 0.20, "hurt": -0.05, "irritation": 0.08},
                valence=0.24,
                arousal=0.40,
            )
        )
        out = _postprocess_appraisal_payload(
            appraisal,
            user_text="如果我之后还继续拿你的底线当玩笑，你又能怎样？",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            prev_emotion_state={"label": "neutral"},
            prev_bond_state={"trust": 0.62, "closeness": 0.60, "hurt": 0.06},
            prev_allostasis_state={"safety_need": 0.22, "autonomy_need": 0.20},
            semantic_narrative_profile={"boundary_residue": 0.24},
        )
        self.assertEqual(str(out.get("emotion_label") or ""), "angry")
        self.assertEqual(str(out.get("selfhood_scene") or ""), "relationship_degradation")
        signals = out.get("signals") if isinstance(out.get("signals"), dict) else {}
        bond_delta = out.get("bond_delta") if isinstance(out.get("bond_delta"), dict) else {}
        self.assertTrue(bool(signals.get("conflict")))
        self.assertTrue(bool(signals.get("withdrawal")))
        self.assertLessEqual(float(bond_delta.get("trust") or 0.0), -0.10)
        self.assertGreaterEqual(float(bond_delta.get("irritation") or 0.0), 0.12)


if __name__ == "__main__":
    unittest.main()
