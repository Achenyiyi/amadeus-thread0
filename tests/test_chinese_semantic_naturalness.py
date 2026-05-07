from __future__ import annotations

from amadeus_thread0.runtime.chinese_semantic_naturalness import (
    build_chinese_semantic_naturalness_readback,
    compact_chinese_semantic_naturalness_line,
)
from amadeus_thread0.runtime.embodied_interaction_runtime import build_embodied_interaction_readback


def test_known_scaffold_family_gets_naturalness_ready_floor_without_service_framing():
    readback = build_chinese_semantic_naturalness_readback("请问有什么可以帮你？")

    assert readback["schema"] == "chinese_semantic_naturalness.v1"
    assert readback["readiness_status"] == "chinese_semantic_naturalness_phase1_ready"
    assert readback["selected_family"] == "generic_assistant_tone"
    assert readback["runtime_final_text"] == "嗯，我在。你直接说吧，我会顺着这轮的语境接住。"
    assert readback["tts_text"] == readback["runtime_final_text"]
    assert readback["diagnostics"]["service_frame_detected"] is False
    assert readback["diagnostics"]["scaffold_residue_leaked"] is False
    assert readback["authority_boundary"]["model_api_called"] is False
    assert readback["authority_boundary"]["prompt_rewrite_applied"] is False
    assert readback["authority_boundary"]["persona_core_mutation_allowed"] is False


def test_already_natural_text_is_noop_without_claiming_rewrite():
    readback = build_chinese_semantic_naturalness_readback("嗯，我在。你慢慢说。")

    assert readback["status"] == "no_semantic_residue"
    assert readback["readiness_status"] == "chinese_semantic_naturalness_phase1_not_applicable"
    assert readback["runtime_final_text"] == "嗯，我在。你慢慢说。"
    assert readback["applied_floor"] is False
    assert readback["diagnostics"]["duplicate_output_detected"] is False


def test_tts_drift_fails_closed_even_when_floor_is_available():
    readback = build_chinese_semantic_naturalness_readback(
        "下次再敢越界，我可不会像这次这么好说话。",
        tts_text="下次再敢越界，我可不会像这次这么好说话。",
    )

    assert readback["readiness_status"] == "chinese_semantic_naturalness_phase1_in_progress"
    assert readback["diagnostics"]["text_tts_drift"] is True
    assert "text_tts_drift" in readback["failure_reasons"]


def test_embodied_interaction_attaches_naturalness_readback_without_changing_existing_policy_shape():
    readback = build_embodied_interaction_readback(
        {
            "final_text": "既然没什么正事，那就先把手头的数据跑完再说吧。",
            "reconsolidation_snapshot": {
                "final_text": "既然没什么正事，那就先把手头的数据跑完再说吧。"
            },
        }
    )

    semantic = readback["chinese_semantic_surface"]
    naturalness = semantic["naturalness"]
    assert semantic["runtime_policy"]["readiness_status"] == "chinese_semantic_descaffolding_phase2_ready"
    assert naturalness["readiness_status"] == "chinese_semantic_naturalness_phase1_ready"
    assert naturalness["selected_family"] == "taskization_of_daily_chat"
    assert readback["final_text"] == naturalness["runtime_final_text"]
    assert readback["reconsolidation_snapshot"]["final_text"] == naturalness["runtime_final_text"]


def test_compact_naturalness_line_is_short_and_explicit():
    readback = build_chinese_semantic_naturalness_readback("你能意识到并特意回来说明，这点还算值得肯定。")

    line = compact_chinese_semantic_naturalness_line(readback)

    assert "chinese_naturalness=chinese_semantic_naturalness_phase1_ready" in line
    assert "family=teacherly_scold" in line
    assert "tts_drift=false" in line
