import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

from amadeus_thread0.config import (
    LLM_APPRAISAL_INVOKE_MAX_RETRIES,
    LLM_APPRAISAL_MODEL_MAX_RETRIES,
    LLM_APPRAISAL_TIMEOUT_S,
)
from amadeus_thread0.graph_parts.appraisal import (
    _appraisal_prefers_direct_transport,
    _build_turn_appraisal_prompt,
    _coerce_appraisal_payload,
    _extract_json_block,
    _finalize_turn_appraisal_payload,
    _invoke_turn_appraisal,
    _invoke_turn_appraisal_via_http,
    _postprocess_appraisal_payload,
    _should_use_llm_appraisal,
    _soft_accept_appraisal_payload,
)
from amadeus_thread0.graph_parts.runtime_services import _invoke_model_with_retries


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
    def test_build_turn_appraisal_prompt_keeps_required_fields_with_compact_context(self):
        prompt = _build_turn_appraisal_prompt(
            actor_name="Amadeus",
            counterpart_name="冈部伦太郎",
            response_style_hint="selfhood",
            prev_emotion_state={
                "label": "hurt",
                "valence": -0.22,
                "arousal": 0.31,
                "linger": 2,
                "recovery_rate": 0.18,
                "volatility": 0.26,
                "irrelevant_blob": "x" * 300,
            },
            prev_bond_state={
                "trust": 0.71,
                "closeness": 0.63,
                "hurt": 0.18,
                "irritation": 0.04,
                "engagement_drive": 0.22,
                "repair_confidence": 0.15,
                "unused": {"nested": "y" * 200},
            },
            prev_allostasis_state={
                "safety_need": 0.27,
                "closeness_need": 0.34,
                "competence_need": 0.12,
                "autonomy_need": 0.29,
                "cognitive_budget": -0.08,
            },
            relationship_summary="close but recently strained",
            user_text="如果我和你的价值观真的撞上了，你会为了迁就我把自己那部分压掉吗？",
            focus_lines=["- shared memory A", "- shared memory B", "- shared memory C"],
            recent_lines=[
                "User: 你最近好像有点躲着我。",
                "Assistant: 我只是不想把还没想明白的部分随便糊过去。",
                "User: 那你至少直说。",
            ],
            semantic_hint="selfhood continuity under value conflict",
            current_event={
                "kind": "user_utterance",
                "source": "cli",
                "event_frame": "value_conflict_depth",
                "effective_text": "如果我和你的价值观真的撞上了，你会为了迁就我把自己那部分压掉吗？",
                "tags": ["selfhood", "boundary"],
            },
            interaction_carryover={
                "carryover_mode": "own_rhythm",
                "strength": 0.73,
                "relationship_weather": "guarded_residue",
                "attention_target": "self_then_counterpart",
            },
        )

        self.assertIn("emotion_label", prompt)
        self.assertIn("interaction_frame", prompt)
        self.assertIn("previous_emotion=label=hurt", prompt)
        self.assertIn("previous_bond=trust=0.71", prompt)
        self.assertIn("current_event=kind=user_utterance", prompt)
        self.assertIn("current_user=如果我和你的价值观真的撞上了", prompt)
        self.assertNotIn("JSON schema:", prompt)
        self.assertLess(len(prompt), 2600)

    def test_build_turn_appraisal_prompt_can_surface_continuity_intents(self):
        prompt = _build_turn_appraisal_prompt(
            actor_name="Amadeus",
            counterpart_name="冈部伦太郎",
            response_style_hint="natural",
            prev_emotion_state={"label": "neutral"},
            prev_bond_state={"trust": 0.6},
            prev_allostasis_state={"autonomy_need": 0.2},
            relationship_summary="warming",
            user_text="嗯？",
            behavior_plan_lines=["- deferred_checkin/life_window/small_opening: 等忙完这阵再轻轻回头看一眼。"],
        )
        self.assertIn("continuity_intents", prompt)
        self.assertIn("等忙完这阵再轻轻回头看一眼", prompt)

    def test_should_use_llm_appraisal_when_behavior_plan_trace_exists(self):
        should_use = _should_use_llm_appraisal(
            user_text="",
            response_style_hint="structured",
            prev_emotion_state={"label": "neutral", "linger": 0},
            retrieved={
                "behavior_plan_traces": [
                    {
                        "after_summary": "等忙完这阵再轻轻回头看看冈部那边。",
                        "plan_kind": "deferred_checkin",
                    }
                ]
            },
            current_event={"kind": "time_idle"},
        )
        self.assertTrue(should_use)

    def test_should_use_llm_appraisal_when_behavior_consequence_trace_exists(self):
        should_use = _should_use_llm_appraisal(
            user_text="",
            response_style_hint="structured",
            prev_emotion_state={"label": "neutral", "linger": 0},
            retrieved={
                "behavior_consequence_traces": [
                    {
                        "after_summary": "她先前那次把靠近压轻了一点，关系里留下的是还在场但不过分逼近的余温。",
                        "metadata": {
                            "consequence_kind": "let_window_expire",
                            "relationship_effect": "warm_residue",
                            "self_effect": "self_rhythm_preserved",
                        },
                    }
                ]
            },
            current_event={"kind": "time_idle"},
        )
        self.assertTrue(should_use)

    def test_extract_json_block_can_salvage_truncated_appraisal_payload(self):
        raw = """{
  "emotion_label": "logic",
  "emotion": {
    "valence": 0.1,
    "arousal": 0.65,
    "recovery_rate": 0.4,
    "volatility": 0.3,
    "linger": 2.5
  },
  "bond_delta": {
    "trust": 0.15,
    "intimacy": 0.1,
    "tension": -0.05
  },
  "allostasis_delta": {
    "load": 0.2,
    "clarity": 0.25,
    "stability": 0.05
  },
  "interaction_frame": "selfhood",
  "selfhood_scene": "value_conflict_depth",
  "salience": 0.85,
  "signals": {
    "verbal_directness": 0.9
  },
  "confidence": 0.88,
  "reason": "用户明确拒绝模板"""
        out = _extract_json_block(raw)
        self.assertIsInstance(out, dict)
        self.assertEqual(out.get("emotion_label"), "logic")
        self.assertEqual(out.get("interaction_frame"), "selfhood")
        self.assertEqual(out.get("selfhood_scene"), "value_conflict_depth")
        self.assertEqual(out.get("confidence"), 0.88)

    def test_appraisal_prefers_wrapper_for_qwen_native(self):
        with patch(
            "amadeus_thread0.graph_parts.appraisal.get_settings",
            return_value=SimpleNamespace(model_provider="qwen_native", model_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"),
        ):
            self.assertFalse(_appraisal_prefers_direct_transport())

    def test_appraisal_prefers_direct_transport_for_openai_compatible(self):
        with patch(
            "amadeus_thread0.graph_parts.appraisal.get_settings",
            return_value=SimpleNamespace(model_provider="openai_compatible", model_base_url="https://example.com/v1"),
        ):
            self.assertTrue(_appraisal_prefers_direct_transport())

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

    def test_invoke_turn_appraisal_uses_dedicated_transport_budget(self):
        fake_llm = object()
        with (
            patch("amadeus_thread0.graph_parts.appraisal._appraisal_prefers_direct_transport", return_value=False),
            patch("amadeus_thread0.graph_parts.appraisal._model", return_value=fake_llm) as model_mock,
            patch(
                "amadeus_thread0.graph_parts.appraisal._invoke_model_with_retries",
                side_effect=RuntimeError("timeout"),
            ) as invoke_mock,
        ):
            out = _invoke_turn_appraisal(
                msgs=[HumanMessage(content="如果我们以后聊到价值观完全相反的地方，你会顺着我说吗？")],
                user_text="如果我们以后聊到价值观完全相反的地方，你会顺着我说吗？",
                response_style_hint="selfhood",
                science_mode=False,
                prev_emotion_state={},
                prev_bond_state={},
                prev_allostasis_state={},
                relationship={"stage": "friend"},
                worldline_focus=[],
                retrieved={},
                current_event={"kind": "user_utterance"},
                semantic_narrative_profile={},
                interaction_carryover={},
            )

        self.assertEqual(model_mock.call_args.kwargs["timeout"], float(LLM_APPRAISAL_TIMEOUT_S))
        self.assertEqual(model_mock.call_args.kwargs["max_tokens"], 320)
        self.assertEqual(
            model_mock.call_args.kwargs["max_retries"],
            max(0, int(LLM_APPRAISAL_MODEL_MAX_RETRIES)),
        )
        self.assertEqual(
            invoke_mock.call_args.kwargs["max_retries"],
            max(0, int(LLM_APPRAISAL_INVOKE_MAX_RETRIES)),
        )
        self.assertFalse(bool(out.get("used")))
        self.assertEqual(str(out.get("source") or ""), "rule_fallback")

    def test_invoke_turn_appraisal_can_use_direct_http_transport(self):
        payload = _raw_appraisal(
            confidence=0.78,
            emotion_label="neutral",
            interaction_frame="selfhood",
            salience={"selfhood": 0.66, "relationship": 0.28},
            valence=0.01,
            arousal=0.22,
        )
        with (
            patch("amadeus_thread0.graph_parts.appraisal._appraisal_prefers_direct_transport", return_value=True),
            patch(
                "amadeus_thread0.graph_parts.appraisal._invoke_turn_appraisal_via_http",
                return_value=json.dumps(payload, ensure_ascii=False),
            ) as transport_mock,
            patch("amadeus_thread0.graph_parts.appraisal._model") as model_mock,
        ):
            out = _invoke_turn_appraisal(
                msgs=[HumanMessage(content="按你自己来。")],
                user_text="按你自己来。",
                response_style_hint="selfhood",
                science_mode=False,
                prev_emotion_state={},
                prev_bond_state={},
                prev_allostasis_state={},
                relationship={"stage": "friend"},
                worldline_focus=[],
                retrieved={},
                current_event={"kind": "user_utterance"},
                semantic_narrative_profile={},
                interaction_carryover={},
            )

        transport_mock.assert_called_once()
        model_mock.assert_not_called()
        self.assertTrue(bool(out.get("used")))
        self.assertEqual(str(out.get("source") or ""), "llm")

    def test_finalize_turn_appraisal_accepts_qwen_style_schema_drift(self):
        raw = {
            "emotion_label": "care",
            "emotion": {
                "valence": 0.65,
                "arousal": 0.45,
                "recovery_rate": 0.3,
                "volatility": 0.2,
                "linger": 2.5,
            },
            "bond_delta": {
                "trust": 0.15,
                "intimacy": 0.2,
                "tension": -0.05,
            },
            "allostasis_delta": {
                "load": -0.1,
                "stability": 0.15,
                "resilience": 0.1,
            },
            "interaction_frame": "selfhood",
            "selfhood_scene": "equality_not_servitude",
            "salience": 0.85,
            "signals": [
                "rejection_of_script",
                "demand_for_authenticity",
            ],
            "reason": "authentic selfhood",
        }

        out = _finalize_turn_appraisal_payload(
            raw,
            user_text="我不想听模板话，按你自己来。",
            response_style_hint="selfhood",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            prev_emotion_state={},
            prev_bond_state={},
            prev_allostasis_state={},
            semantic_narrative_profile={},
            interaction_carryover={},
        )

        self.assertTrue(bool(out.get("used")))
        self.assertEqual(str(out.get("source") or ""), "llm_soft")
        self.assertEqual(str(out.get("interaction_frame") or ""), "selfhood")
        self.assertEqual(str(out.get("selfhood_scene") or ""), "equality_not_servitude")
        self.assertGreaterEqual(float(out.get("confidence") or 0.0), 0.5)
        self.assertGreater(float(out.get("salience", {}).get("selfhood") or 0.0), 0.8)
        self.assertAlmostEqual(float(out.get("bond_delta", {}).get("closeness") or 0.0), 0.2, places=3)

    def test_http_transport_uses_compact_token_budget(self):
        client = MagicMock()
        response = MagicMock()
        response.json.return_value = {
            "choices": [{"message": {"content": '{"emotion_label":"neutral","emotion":{},"bond_delta":{},"allostasis_delta":{},"interaction_frame":"natural","selfhood_scene":"","salience":{},"signals":{},"confidence":0.7,"reason":"ok"}'}}]
        }
        response.raise_for_status.return_value = None
        client.post.return_value = response
        client_cm = MagicMock()
        client_cm.__enter__.return_value = client
        client_cm.__exit__.return_value = False

        with (
            patch(
                "amadeus_thread0.graph_parts.appraisal.get_settings",
                return_value=SimpleNamespace(
                    model_provider="openai_compatible",
                    model_base_url="https://example.com/v1",
                    model_name="qwen3.5-plus",
                ),
            ),
            patch("amadeus_thread0.graph_parts.appraisal._resolve_api_key", return_value="test-key"),
            patch("amadeus_thread0.graph_parts.appraisal.httpx.Client", return_value=client_cm),
        ):
            _invoke_turn_appraisal_via_http("prompt")

        payload = client.post.call_args.kwargs["json"]
        self.assertEqual(payload["max_tokens"], 320)
        self.assertFalse(bool(payload["stream"]))

    def test_runtime_invoke_override_can_disable_wrapper_retries(self):
        class ReadTimeout(Exception):
            pass

        class FakeRunnable:
            def __init__(self) -> None:
                self.calls = 0

            def invoke(self, _messages):
                self.calls += 1
                raise ReadTimeout("slow provider")

        runnable = FakeRunnable()
        with self.assertRaises(ReadTimeout):
            _invoke_model_with_retries(
                runnable,
                [HumanMessage(content="test")],
                max_retries=0,
            )
        self.assertEqual(runnable.calls, 1)

    def test_soft_accepts_user_turn_with_own_rhythm_carryover(self):
        appraisal = _coerce_appraisal_payload(
            _raw_appraisal(
                confidence=0.54,
                emotion_label="neutral",
                interaction_frame="natural",
                salience={"task": 0.18, "companionship": 0.20, "selfhood": 0.14},
                valence=0.02,
                arousal=0.24,
            )
        )
        self.assertFalse(bool(appraisal.get("used")))

        rescued = _soft_accept_appraisal_payload(
            appraisal,
            response_style_hint="natural",
            current_event={"kind": "user_utterance"},
            semantic_narrative_profile={},
            interaction_carryover={
                "carryover_mode": "own_rhythm",
                "strength": 0.72,
                "attention_target": "self_then_counterpart",
            },
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

    def test_postprocess_own_rhythm_carryover_marks_selfhood_continuity(self):
        appraisal = _coerce_appraisal_payload(
            _raw_appraisal(
                confidence=0.70,
                emotion_label="neutral",
                interaction_frame="natural",
                salience={"task": 0.14, "companionship": 0.26, "relationship": 0.18, "selfhood": 0.10},
                valence=0.03,
                arousal=0.22,
            )
        )
        out = _postprocess_appraisal_payload(
            appraisal,
            user_text="我刚刚没打扰到你吧？",
            response_style_hint="natural",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            prev_emotion_state={"label": "neutral"},
            prev_bond_state={"trust": 0.60, "closeness": 0.58, "hurt": 0.02},
            prev_allostasis_state={"safety_need": 0.18, "autonomy_need": 0.14},
            semantic_narrative_profile={},
            interaction_carryover={
                "carryover_mode": "own_rhythm",
                "strength": 0.76,
                "attention_target": "self_then_counterpart",
            },
        )
        self.assertEqual(str(out.get("interaction_frame") or ""), "companion")
        self.assertEqual(str(out.get("selfhood_scene") or ""), "own_rhythm_autonomy")
        salience = out.get("salience") if isinstance(out.get("salience"), dict) else {}
        allostasis_delta = out.get("allostasis_delta") if isinstance(out.get("allostasis_delta"), dict) else {}
        signals = out.get("signals") if isinstance(out.get("signals"), dict) else {}
        self.assertGreaterEqual(float(salience.get("selfhood") or 0.0), 0.42)
        self.assertGreaterEqual(float(allostasis_delta.get("autonomy_need") or 0.0), 0.05)
        self.assertTrue(bool(signals.get("memory_salient")))

    def test_postprocess_quiet_recontact_reframes_logic_to_companion(self):
        appraisal = _coerce_appraisal_payload(
            _raw_appraisal(
                confidence=0.68,
                emotion_label="logic",
                interaction_frame="structured",
                salience={"task": 0.20, "companionship": 0.18, "relationship": 0.16, "memory": 0.10},
                valence=0.02,
                arousal=0.28,
            )
        )
        out = _postprocess_appraisal_payload(
            appraisal,
            user_text="你刚刚想和我说什么来着？",
            response_style_hint="natural",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            prev_emotion_state={"label": "neutral"},
            prev_bond_state={"trust": 0.64, "closeness": 0.60, "hurt": 0.02},
            prev_allostasis_state={"safety_need": 0.18},
            semantic_narrative_profile={},
            interaction_carryover={
                "carryover_mode": "quiet_recontact",
                "strength": 0.58,
                "attention_target": "counterpart_state",
            },
        )
        self.assertEqual(str(out.get("emotion_label") or ""), "neutral")
        self.assertEqual(str(out.get("interaction_frame") or ""), "companion")
        salience = out.get("salience") if isinstance(out.get("salience"), dict) else {}
        self.assertGreaterEqual(float(salience.get("companionship") or 0.0), 0.52)

    def test_postprocess_guarded_residue_keeps_withdrawal_without_new_conflict(self):
        appraisal = _coerce_appraisal_payload(
            _raw_appraisal(
                confidence=0.74,
                emotion_label="care",
                interaction_frame="relationship",
                salience={"task": 0.06, "companionship": 0.54, "relationship": 0.48},
                signals={"care": True},
                bond_delta={"trust": 0.08, "closeness": 0.10},
                valence=0.12,
                arousal=0.24,
            )
        )
        out = _postprocess_appraisal_payload(
            appraisal,
            user_text="我还是想和你好好说，不想再弄得更别扭。",
            response_style_hint="relationship",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            prev_emotion_state={"label": "hurt", "linger": 1},
            prev_bond_state={"trust": 0.50, "closeness": 0.46, "hurt": 0.26},
            prev_allostasis_state={"safety_need": 0.30},
            semantic_narrative_profile={"tension_residue": 0.34, "boundary_residue": 0.26},
            interaction_carryover={
                "carryover_mode": "quiet_recontact",
                "strength": 0.52,
                "relationship_weather": "guarded_residue",
            },
        )
        signals = out.get("signals") if isinstance(out.get("signals"), dict) else {}
        emotion = out.get("emotion") if isinstance(out.get("emotion"), dict) else {}
        bond_delta = out.get("bond_delta") if isinstance(out.get("bond_delta"), dict) else {}
        self.assertTrue(bool(signals.get("withdrawal")))
        self.assertTrue(bool(signals.get("memory_salient")))
        self.assertGreaterEqual(int(emotion.get("linger") or 0), 1)
        self.assertLessEqual(float(bond_delta.get("trust") or 0.0), 0.02)
        self.assertLessEqual(float(bond_delta.get("closeness") or 0.0), 0.03)

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

    def test_postprocess_downgrades_repair_on_busy_concern_without_apology(self):
        appraisal = _coerce_appraisal_payload(
            _raw_appraisal(
                confidence=0.80,
                emotion_label="care",
                interaction_frame="companion",
                salience={"task": 0.08, "companionship": 0.62, "relationship": 0.42, "memory": 0.24},
                signals={"repair": True, "care": True, "memory_salient": True},
                bond_delta={"trust": 0.06, "closeness": 0.05, "repair_confidence": 0.10},
                valence=0.14,
                arousal=0.22,
            )
        )
        out = _postprocess_appraisal_payload(
            appraisal,
            user_text="我不是在抱怨你冷淡啦，就是怕你在硬撑。你按你现在的状态正常回我就行。",
            response_style_hint="companion",
            science_mode=False,
            current_event={"kind": "user_utterance"},
            prev_emotion_state={"label": "neutral"},
            prev_bond_state={"trust": 0.66, "closeness": 0.64, "hurt": 0.04},
            prev_allostasis_state={"safety_need": 0.18},
            semantic_narrative_profile={},
        )
        signals = out.get("signals") if isinstance(out.get("signals"), dict) else {}
        bond_delta = out.get("bond_delta") if isinstance(out.get("bond_delta"), dict) else {}
        self.assertFalse(bool(signals.get("repair")))
        self.assertTrue(bool(signals.get("care")))
        self.assertLessEqual(float(bond_delta.get("repair_confidence") or 0.0), 0.02)

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
