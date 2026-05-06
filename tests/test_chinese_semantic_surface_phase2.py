from __future__ import annotations

from amadeus_thread0.graph_parts.chinese_semantic_surface import (
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
