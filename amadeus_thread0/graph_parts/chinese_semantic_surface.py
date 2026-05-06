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
    replacements = {
        "teacherly_scold": "acknowledge repair without grading the counterpart",
        "meta_persona_proof": "state the judgment directly without proving personhood",
        "generic_assistant_tone": "answer from familiar shared presence instead of service framing",
        "hardline_autonomy_overreach": "set distance without punitive deletion or humiliation",
        "scene_script_residue": "keep ordinary present context without staged canon props",
        "taskization_of_daily_chat": "allow no-agenda co-presence without turning it into work",
        "repair_scorekeeping": "retain guardedness without promising retaliation",
        "boundary_threat_excess": "name boundary consequences without threats",
    }
    return {"family": normalized, "replacement_semantic": replacements.get(normalized, "")}


def compare_legacy_and_semantic_detection(text: str) -> dict[str, list[str]]:
    semantic = classify_chinese_surface_semantics(text)
    return {
        "legacy_detected_families": [],
        "semantic_detected_families": semantic,
        "semantic_only_matches": semantic,
        "legacy_only_matches": [],
    }


__all__ = [
    "FAMILIES",
    "candidate_replacement_semantics",
    "classify_chinese_surface_semantics",
    "compare_legacy_and_semantic_detection",
]
