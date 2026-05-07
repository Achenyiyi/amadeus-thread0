from __future__ import annotations

import re
from typing import Any

from ..graph_parts.chinese_semantic_surface import build_runtime_replacement_policy


CHINESE_SEMANTIC_NATURALNESS_PHASE1_READINESS = "chinese_semantic_naturalness_phase1_ready"
CHINESE_SEMANTIC_NATURALNESS_PHASE1_IN_PROGRESS = "chinese_semantic_naturalness_phase1_in_progress"
CHINESE_SEMANTIC_NATURALNESS_PHASE1_NOT_APPLICABLE = "chinese_semantic_naturalness_phase1_not_applicable"

AUTHORITY_BOUNDARY = {
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

SERVICE_FRAME_PATTERN = re.compile(r"(请问.*帮你|有什么可以帮|提供支持|为你服务)")
SCAFFOLD_RESIDUE_PATTERNS = {
    "generic_assistant_tone": SERVICE_FRAME_PATTERN,
    "teacherly_scold": re.compile(r"(值得肯定|还算像样|求表扬|给你个教训|收一点.*样子)"),
    "boundary_threat_excess": re.compile(r"(下次再敢|不会像这次这么好说话|别怪我|不会继续给你留余地)"),
    "taskization_of_daily_chat": re.compile(r"(没什么正事|手头的数据|流程拖着|记录整理完|先把.*跑完)"),
    "scene_script_residue": re.compile(r"(白大褂|命运选中|世界线|机关的阴谋|她.*推了推)"),
    "hardline_autonomy_overreach": re.compile(r"(抹去|消耗我的时间|省得你继续|不如去想想你为什么)"),
    "repair_scorekeeping": re.compile(r"(下次.*顶回去|刺回来|毫不客气地.*回去|先说好)"),
    "meta_persona_proof": re.compile(r"(程序|自动应答机|设定好|证明.*自己)"),
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def _has_duplicate_output(text: str) -> bool:
    compact = _compact(text)
    if not compact or len(compact) % 2:
        return False
    midpoint = len(compact) // 2
    return compact[:midpoint] == compact[midpoint:]


def _selected_family(policy: dict[str, Any]) -> str:
    selected = _dict_or_empty(policy.get("selected_policy"))
    family = _clean(selected.get("family"))
    if family:
        return family
    families = list(policy.get("families") or [])
    return _clean(families[0]) if families else ""


def _scaffold_residue_leaked(text: str, families: list[str]) -> bool:
    checks = families or list(SCAFFOLD_RESIDUE_PATTERNS)
    return any(
        bool(SCAFFOLD_RESIDUE_PATTERNS.get(family, re.compile(r"$^")).search(text))
        for family in checks
    )


def _authority_widened(*rows: dict[str, Any]) -> bool:
    for row in rows:
        for value in row.values():
            if isinstance(value, bool) and value:
                return True
    return False


def _diagnostics(runtime_text: str, tts_text: str, families: list[str]) -> dict[str, bool]:
    scaffold_residue = _scaffold_residue_leaked(runtime_text, families)
    return {
        "duplicate_output_detected": _has_duplicate_output(runtime_text),
        "service_frame_detected": bool(SERVICE_FRAME_PATTERN.search(runtime_text)),
        "scaffold_residue_leaked": scaffold_residue,
        "text_tts_drift": tts_text != runtime_text,
    }


def _failure_reasons(
    *,
    policy: dict[str, Any],
    diagnostics: dict[str, bool],
    authority_boundary: dict[str, Any],
    selected_authority: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    if _clean(policy.get("readiness_status")).endswith("_in_progress"):
        reasons.append("semantic_policy_in_progress")
    for key in (
        "duplicate_output_detected",
        "service_frame_detected",
        "scaffold_residue_leaked",
        "text_tts_drift",
    ):
        if bool(diagnostics.get(key, False)):
            reason = "text_tts_drift" if key == "text_tts_drift" else key
            reasons.append(reason)
    if _authority_widened(authority_boundary, selected_authority):
        reasons.append("authority_widened")
    return reasons


def build_chinese_semantic_naturalness_readback(
    text: str,
    *,
    family_context: list[str] | None = None,
    tts_text: str | None = None,
) -> dict[str, Any]:
    original = _clean(text)
    policy = build_runtime_replacement_policy(original, family_context=family_context)
    runtime_text = _clean(policy.get("runtime_final_text")) or original
    rendered_tts = runtime_text if tts_text is None else _clean(tts_text)
    selected = _dict_or_empty(policy.get("selected_policy"))
    selected_authority = _dict_or_empty(selected.get("authority_boundary"))
    families = [_clean(item) for item in list(policy.get("families") or []) if _clean(item)]
    selected_family = _selected_family(policy)
    diagnostics = _diagnostics(runtime_text, rendered_tts, families)
    authority_boundary = dict(AUTHORITY_BOUNDARY)
    failures = _failure_reasons(
        policy=policy,
        diagnostics=diagnostics,
        authority_boundary=authority_boundary,
        selected_authority=selected_authority,
    )
    applied_floor = bool(policy.get("applied_floor", False))
    no_residue = _clean(policy.get("status")) == "no_semantic_residue"
    if failures:
        status = "naturalness_in_progress"
        readiness = CHINESE_SEMANTIC_NATURALNESS_PHASE1_IN_PROGRESS
    elif no_residue:
        status = "no_semantic_residue"
        readiness = CHINESE_SEMANTIC_NATURALNESS_PHASE1_NOT_APPLICABLE
    else:
        status = "naturalness_ready"
        readiness = CHINESE_SEMANTIC_NATURALNESS_PHASE1_READINESS
    return {
        "schema": "chinese_semantic_naturalness.v1",
        "status": status,
        "readiness_status": readiness,
        "original_text": original,
        "runtime_final_text": runtime_text,
        "tts_text": rendered_tts,
        "selected_family": selected_family,
        "families": families,
        "applied_floor": applied_floor,
        "diagnostics": diagnostics,
        "runtime_policy": policy,
        "authority_boundary": authority_boundary,
        "failure_reasons": failures,
    }


def compact_chinese_semantic_naturalness_line(readback: dict[str, Any] | None) -> str:
    data = _dict_or_empty(readback)
    diagnostics = _dict_or_empty(data.get("diagnostics"))
    return " | ".join(
        [
            f"chinese_naturalness={_clean(data.get('readiness_status')) or 'unknown'}",
            f"family={_clean(data.get('selected_family')) or 'none'}",
            f"applied_floor={str(bool(data.get('applied_floor', False))).lower()}",
            f"tts_drift={str(bool(diagnostics.get('text_tts_drift', False))).lower()}",
            f"residue={str(bool(diagnostics.get('scaffold_residue_leaked', False))).lower()}",
        ]
    )


__all__ = [
    "AUTHORITY_BOUNDARY",
    "CHINESE_SEMANTIC_NATURALNESS_PHASE1_IN_PROGRESS",
    "CHINESE_SEMANTIC_NATURALNESS_PHASE1_NOT_APPLICABLE",
    "CHINESE_SEMANTIC_NATURALNESS_PHASE1_READINESS",
    "build_chinese_semantic_naturalness_readback",
    "compact_chinese_semantic_naturalness_line",
]
