from __future__ import annotations

from amadeus_thread0.graph_parts.chinese_semantic_surface import (
    build_runtime_replacement_policy,
    build_semantic_replacement_plan,
    rewrite_semantic_surface_floor,
)


def test_replacement_plan_maps_detected_families_to_behavior_targets():
    plan = build_semantic_replacement_plan("请问有什么可以帮你？")

    assert plan["status"] == "replacement_guidance_ready"
    assert plan["families"] == ["generic_assistant_tone"]
    assert plan["replacement_semantics"][0]["target_behavior"] == "familiar_shared_presence"
    assert plan["authority_boundary"]["persona_core_mutation_allowed"] is False
    assert plan["authority_boundary"]["prompt_sprawl_rewrite_allowed"] is False


def test_safe_surface_floor_replaces_scaffold_without_claiming_full_rewrite():
    result = rewrite_semantic_surface_floor("你能意识到并特意回来说明，这点还算值得肯定。")

    assert result["status"] == "floor_rewritten"
    assert "值得肯定" not in result["safe_surface_floor"]
    assert result["families"] == ["teacherly_scold"]
    assert result["applied_floor"] is True


def test_no_detected_family_returns_noop_floor():
    result = rewrite_semantic_surface_floor("嗯，我听见了。")

    assert result["status"] == "no_semantic_residue"
    assert result["safe_surface_floor"] == "嗯，我听见了。"
    assert result["applied_floor"] is False


def test_family_context_can_drive_guidance_without_reclassifying_text():
    plan = build_semantic_replacement_plan("这句话本身很短。", family_context=["boundary_threat_excess"])

    assert plan["status"] == "replacement_guidance_ready"
    assert plan["families"] == ["boundary_threat_excess"]
    assert plan["replacement_semantics"][0]["target_behavior"] == "bounded_consequence_without_threat"


def test_runtime_policy_envelope_contains_typed_strategy_and_boundaries():
    policy = build_runtime_replacement_policy("请问有什么可以帮你？")

    assert policy["schema"] == "chinese_semantic_replacement_policy.v1"
    assert policy["readiness_status"] == "chinese_semantic_descaffolding_phase2_ready"
    assert policy["status"] == "policy_ready"
    assert policy["selected_policy"]["family"] == "generic_assistant_tone"
    assert (
        policy["selected_policy"]["semantic_intent"]
        == "answer from familiar shared presence instead of service framing"
    )
    assert policy["selected_policy"]["replacement_strategy"] == "deterministic_safe_surface_floor"
    assert policy["selected_policy"]["applied_floor"] == "嗯，我在。你直接说吧，我会顺着这轮的语境接住。"
    assert policy["selected_policy"]["authority_boundary"]["model_api_called"] is False
    assert policy["selected_policy"]["authority_boundary"]["prompt_rewrite_applied"] is False
    assert policy["selected_policy"]["authority_boundary"]["persona_core_mutation_allowed"] is False
    assert policy["applied_floor"] is True
    assert policy["runtime_final_text"] == "嗯，我在。你直接说吧，我会顺着这轮的语境接住。"


def test_runtime_policy_noop_preserves_text_without_claiming_rewrite():
    policy = build_runtime_replacement_policy("嗯，我听见了。")

    assert policy["status"] == "no_semantic_residue"
    assert policy["readiness_status"] == "chinese_semantic_descaffolding_phase2_not_applicable"
    assert policy["policies"] == []
    assert policy["selected_policy"] == {}
    assert policy["applied_floor"] is False
    assert policy["runtime_final_text"] == "嗯，我听见了。"
