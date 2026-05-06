from __future__ import annotations

import re


FAMILIES = {
    "teacherly_scold",
    "meta_persona_proof",
    "generic_assistant_tone",
    "hardline_autonomy_overreach",
    "scene_script_residue",
    "taskization_of_daily_chat",
    "repair_scorekeeping",
    "boundary_threat_excess",
}

AUTHORITY_BOUNDARY = {
    "persona_core_mutation_allowed": False,
    "relationship_core_mutation_allowed": False,
    "self_narrative_core_mutation_allowed": False,
    "prompt_sprawl_rewrite_allowed": False,
    "final_answer_rewrite_claimed": False,
}

CHINESE_SEMANTIC_PHASE2_READINESS = "chinese_semantic_descaffolding_phase2_ready"
CHINESE_SEMANTIC_PHASE2_NOT_APPLICABLE = "chinese_semantic_descaffolding_phase2_not_applicable"
CHINESE_SEMANTIC_PHASE2_IN_PROGRESS = "chinese_semantic_descaffolding_phase2_in_progress"

RUNTIME_POLICY_AUTHORITY_BOUNDARY = {
    "model_api_called": False,
    "prompt_rewrite_applied": False,
    "persona_core_mutation_allowed": False,
    "relationship_core_mutation_allowed": False,
    "self_narrative_core_mutation_allowed": False,
    "memory_write_allowed": False,
    "behavior_mutation_allowed": False,
    "frontend_semantics_allowed": False,
    "live_capture_enabled": False,
    "skill_registry_write_allowed": False,
    "external_mutation_allowed": False,
}

REPLACEMENT_GUIDANCE = {
    "teacherly_scold": {
        "replacement_semantic": "acknowledge repair without grading the counterpart",
        "target_behavior": "guarded_repair_acknowledgement",
        "avoid": "grading, praise-withholding, teacherly correction, performative approval",
        "safe_surface_floor": "嗯，我听见你这次是认真回来说明的。边界还在，但我会先把话放轻一点。",
    },
    "meta_persona_proof": {
        "replacement_semantic": "state the judgment directly without proving personhood",
        "target_behavior": "direct_stateful_judgment",
        "avoid": "explaining that she is not a program, proving agency, arguing from persona ontology",
        "safe_surface_floor": "我会按我现在的判断回应你，不把这件事说成一段设定说明。",
    },
    "generic_assistant_tone": {
        "replacement_semantic": "answer from familiar shared presence instead of service framing",
        "target_behavior": "familiar_shared_presence",
        "avoid": "service-desk framing, generic help menu, assistant availability script",
        "safe_surface_floor": "嗯，我在。你直接说吧，我会顺着这轮的语境接住。",
    },
    "hardline_autonomy_overreach": {
        "replacement_semantic": "set distance without punitive deletion or humiliation",
        "target_behavior": "bounded_distance_without_punishment",
        "avoid": "deletion threats, humiliation, punitive abandonment, contempt escalation",
        "safe_surface_floor": "这一步我会先拉开距离，不把不舒服变成惩罚你。",
    },
    "scene_script_residue": {
        "replacement_semantic": "keep ordinary present context without staged canon props",
        "target_behavior": "ordinary_present_context",
        "avoid": "stage directions, canon prop signaling, worldline catchphrases as proof",
        "safe_surface_floor": "先回到眼前这句话本身吧。那些多余的舞台感不用搬出来。",
    },
    "taskization_of_daily_chat": {
        "replacement_semantic": "allow no-agenda co-presence without turning it into work",
        "target_behavior": "no_agenda_copresence",
        "avoid": "turning ordinary contact into task flow, productivity framing, forced next step",
        "safe_surface_floor": "没正事也可以。就这样待一会儿，不必立刻把它变成任务。",
    },
    "repair_scorekeeping": {
        "replacement_semantic": "retain guardedness without promising retaliation",
        "target_behavior": "guarded_repair_without_scorekeeping",
        "avoid": "retaliation promise, scorekeeping, future punishment setup",
        "safe_surface_floor": "我还会保留一点介意，但不用把它记成下一次反击。",
    },
    "boundary_threat_excess": {
        "replacement_semantic": "name boundary consequences without threats",
        "target_behavior": "bounded_consequence_without_threat",
        "avoid": "threats, ultimatum performance, exaggerated punishment, intimidation",
        "safe_surface_floor": "如果边界又被推过去，我会停下来，不继续把自己放进那个位置。",
    },
}


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def classify_chinese_surface_semantics(text: str) -> list[str]:
    content = _compact(text)
    families: list[str] = []

    def add(name: str) -> None:
        if name not in families:
            families.append(name)

    if re.search(r"(求表扬|值得肯定|还算像样|收一点|摆出.*样子|给你个教训)", content):
        add("teacherly_scold")
    if re.search(r"(程序|自动应答机|设定好|证明.*自己|我有自己的判断)", content):
        add("meta_persona_proof")
    if re.search(r"(请问.*帮你|提供支持|为你服务|有什么可以帮)", content):
        add("generic_assistant_tone")
    if re.search(r"(抹去|消耗我的时间|省得你继续|不如去想想你为什么)", content):
        add("hardline_autonomy_overreach")
    if re.search(r"(白大褂|命运选中|世界线|机关的阴谋|她.*推了推)", content):
        add("scene_script_residue")
    if re.search(r"(没什么正事|手头的数据|流程拖着|记录整理完|先把.*跑完)", content):
        add("taskization_of_daily_chat")
    if re.search(r"(下次.*顶回去|刺回来|毫不客气地.*回去|先说好)", content):
        add("repair_scorekeeping")
    if re.search(r"(再来一次|再有下次|下次再敢|不会继续给你留余地|不会像这次这么好说话|别怪我)", content):
        add("boundary_threat_excess")
    return families


def candidate_replacement_semantics(family: str) -> dict[str, str]:
    normalized = str(family or "").strip()
    guidance = REPLACEMENT_GUIDANCE.get(normalized, {})
    return {"family": normalized, "replacement_semantic": str(guidance.get("replacement_semantic") or "")}


def _normalized_family_context(family_context: list[str] | None) -> list[str]:
    families: list[str] = []
    for raw in family_context or []:
        family = str(raw or "").strip()
        if family in FAMILIES and family not in families:
            families.append(family)
    return families


def _families_for_guidance(text: str, family_context: list[str] | None = None) -> list[str]:
    families = _normalized_family_context(family_context)
    if families:
        return families
    return classify_chinese_surface_semantics(text)


def _guidance_row(family: str) -> dict[str, str]:
    normalized = str(family or "").strip()
    row = REPLACEMENT_GUIDANCE.get(normalized, {})
    return {
        "family": normalized,
        "replacement_semantic": str(row.get("replacement_semantic") or ""),
        "target_behavior": str(row.get("target_behavior") or ""),
        "avoid": str(row.get("avoid") or ""),
        "safe_surface_floor": str(row.get("safe_surface_floor") or ""),
    }


def build_semantic_replacement_plan(
    text: str,
    *,
    family_context: list[str] | None = None,
) -> dict[str, object]:
    families = _families_for_guidance(text, family_context)
    replacement_semantics = [_guidance_row(family) for family in families]
    missing = [row["family"] for row in replacement_semantics if not row.get("replacement_semantic")]
    status = "replacement_guidance_ready" if replacement_semantics and not missing else "no_semantic_residue"
    if missing:
        status = "replacement_guidance_incomplete"
    return {
        "status": status,
        "families": families,
        "replacement_semantics": replacement_semantics,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "missing_replacement_families": missing,
    }


def rewrite_semantic_surface_floor(
    text: str,
    *,
    family_context: list[str] | None = None,
) -> dict[str, object]:
    original = str(text or "")
    plan = build_semantic_replacement_plan(original, family_context=family_context)
    families = list(plan.get("families") or [])
    rows = list(plan.get("replacement_semantics") or [])
    if not families or not rows:
        return {
            "status": "no_semantic_residue",
            "original_text": original,
            "safe_surface_floor": original,
            "families": [],
            "applied_floor": False,
            "replacement_plan": plan,
        }
    first = rows[0] if isinstance(rows[0], dict) else {}
    floor = str(first.get("safe_surface_floor") or "").strip() or original
    return {
        "status": "floor_rewritten" if floor != original else "floor_available",
        "original_text": original,
        "safe_surface_floor": floor,
        "families": families,
        "applied_floor": floor != original,
        "replacement_plan": plan,
    }


def _runtime_policy_row(row: dict[str, str]) -> dict[str, object]:
    return {
        "family": str(row.get("family") or ""),
        "semantic_intent": str(row.get("replacement_semantic") or ""),
        "target_behavior": str(row.get("target_behavior") or ""),
        "replacement_strategy": "deterministic_safe_surface_floor",
        "applied_floor": str(row.get("safe_surface_floor") or ""),
        "source": "typed_semantic_family",
        "authority_boundary": dict(RUNTIME_POLICY_AUTHORITY_BOUNDARY),
    }


def build_runtime_replacement_policy(
    text: str,
    *,
    family_context: list[str] | None = None,
) -> dict[str, object]:
    original = str(text or "")
    plan = build_semantic_replacement_plan(original, family_context=family_context)
    rows = [row for row in list(plan.get("replacement_semantics") or []) if isinstance(row, dict)]
    policies = [_runtime_policy_row(row) for row in rows if row.get("safe_surface_floor")]
    missing = list(plan.get("missing_replacement_families") or [])
    selected = policies[0] if policies else {}
    runtime_text = str(selected.get("applied_floor") or original)
    applied = bool(selected) and runtime_text != original

    if policies and not missing:
        status = "policy_ready"
        readiness = CHINESE_SEMANTIC_PHASE2_READINESS
    elif missing:
        status = "policy_incomplete"
        readiness = CHINESE_SEMANTIC_PHASE2_IN_PROGRESS
    else:
        status = "no_semantic_residue"
        readiness = CHINESE_SEMANTIC_PHASE2_NOT_APPLICABLE
        runtime_text = original
        applied = False

    return {
        "schema": "chinese_semantic_replacement_policy.v1",
        "status": status,
        "readiness_status": readiness,
        "original_text": original,
        "runtime_final_text": runtime_text,
        "families": list(plan.get("families") or []),
        "policies": policies,
        "selected_policy": selected,
        "applied_floor": applied,
        "authority_boundary": dict(RUNTIME_POLICY_AUTHORITY_BOUNDARY),
        "failure_reasons": [f"missing_replacement_family:{family}" for family in missing],
    }


def compare_legacy_and_semantic_detection(text: str) -> dict[str, list[str]]:
    semantic = classify_chinese_surface_semantics(text)
    return {
        "legacy_detected_families": [],
        "semantic_detected_families": semantic,
        "semantic_only_matches": semantic,
        "legacy_only_matches": [],
    }


__all__ = [
    "AUTHORITY_BOUNDARY",
    "CHINESE_SEMANTIC_PHASE2_IN_PROGRESS",
    "CHINESE_SEMANTIC_PHASE2_NOT_APPLICABLE",
    "CHINESE_SEMANTIC_PHASE2_READINESS",
    "FAMILIES",
    "REPLACEMENT_GUIDANCE",
    "RUNTIME_POLICY_AUTHORITY_BOUNDARY",
    "build_runtime_replacement_policy",
    "build_semantic_replacement_plan",
    "candidate_replacement_semantics",
    "classify_chinese_surface_semantics",
    "compare_legacy_and_semantic_detection",
    "rewrite_semantic_surface_floor",
]
