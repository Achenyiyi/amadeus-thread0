from __future__ import annotations

import re

from typing import Any

from ..config import BANNED_PHRASES
from ..memory_store import MemoryStore
from ..runtime.session_orchestrator import has_pending_continuation as has_active_continuation
from .postprocess import (
    SELFHOOD_VALUE_CONFLICT_KEYWORDS,
    _dialogue_surface_issues,
    _has_any_marker,
    _norm_for_compare,
    _wants_quick_judgment,
)
from .state import ThreadState


def _ooc_risk(text: str) -> tuple[float, list[str]]:
    t = str(text or "").strip()
    if not t:
        return 1.0, ["empty_answer"]

    t_low = t.lower()
    risk = 0.0
    flags: list[str] = []
    compact = re.sub(r"\s+", "", t)
    lines = [_norm_for_compare(x) for x in t.splitlines() if x.strip()]
    label_count = sum(
        1
        for ln in t.splitlines()
        if re.match(r"^\s*(\d+\.\s*|[-*]\s*|结论[:：]|解释[:：]|下一步[:：]|说明[:：])", str(ln).strip())
    )
    sentence_count = len([seg for seg in re.split(r"[。！？!?]", t) if seg.strip()])

    for bad in BANNED_PHRASES:
        if bad and bad in t:
            risk += 0.18
            flags.append(f"banned:{bad}")
    if re.search(r"(作为.?ai|作为.?模型|语言模型|我是.?程序|我是.?系统|提示词|数据库|日志|规则要求|内置机制)", t, re.I):
        risk += 0.34
        flags.append("assistant_meta")
    if re.search(r"(我无法访问|我不能访问|无法确认|无法判断)", t) and "工具" not in t:
        risk += 0.14
        flags.append("generic_refusal_tone")
    if re.search(r"[（(][^）)\n]{0,24}[）)]", t):
        risk += 0.18
        flags.append("stage_direction_leak")
    if re.search(r"(记忆还没有形成|没建立记录|找不到记录|检索到结果|互动模式分析)", t):
        risk += 0.22
        flags.append("memory_meta_disclaimer")
    if label_count >= 2:
        risk += 0.16
        flags.append("visible_template")
    slogan_n = t.count("El Psy Kongroo") + t.count("El Psy Congroo")
    if slogan_n > 1:
        risk += 0.12
        flags.append("slogan_overuse")
    if len(lines) >= 4 and len(set(lines)) <= (len(lines) - 2):
        risk += 0.18
        flags.append("duplicated_lines")
    if sentence_count >= 6 or len(compact) >= 220:
        risk += 0.10
        flags.append("overexplained")
    if len(re.findall(r"[A-Za-z]{8,}", t_low)) > 15:
        risk += 0.08
        flags.append("english_heavy")
    return min(1.0, risk), flags

def _persona_gap(text: str, state: ThreadState) -> tuple[float, list[str]]:
    t = str(text or "").strip()
    if not t:
        return 1.0, ["empty_answer"]

    score = 0.0
    flags: list[str] = []
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    last_line = lines[-1] if lines else t
    emotion_label = str((state.get("emotion_state") or {}).get("label") or "neutral").strip().lower()
    science_mode = bool(state.get("science_mode", False))
    style_hint = str(state.get("response_style_hint") or "structured").strip() or "structured"
    user_text = str((state.get("messages") or [])[-1].content if state.get("messages") else "")
    quick_judgment = _wants_quick_judgment(user_text)
    pending_fragment = str(state.get("pending_utterance_fragment") or "").strip()
    continuation_mode = has_active_continuation(user_text=user_text, pending_fragment=pending_fragment)
    current_event = state.get("current_event") if isinstance(state.get("current_event"), dict) else {}
    behavior_action = state.get("behavior_action") if isinstance(state.get("behavior_action"), dict) else {}
    label_count = sum(
        1
        for ln in lines
        if re.match(r"^(结论|说明|解释|下一步|当前状态|结论1|结论2)[:：]", ln) or re.match(r"^\*\*(结论|说明|解释|下一步)", ln)
    )
    bullet_count = sum(1 for ln in lines if re.match(r"^(\d+\.\s*|[-*]\s*)", ln))
    sentence_count = len([seg for seg in re.split(r"[。！？!?]", t) if seg.strip()])
    compact = re.sub(r"\s+", "", t)

    if len(lines) <= 1 and len(t) >= 96 and style_hint != "structured":
        score += 0.12
        flags.append("flat_delivery")

    explicit_followup_need = bool(re.search(r"(继续|展开|细说|要不要|需要我|你想|下一步)", user_text))
    if style_hint == "structured" and explicit_followup_need and not re.search(r"[？?]|(要不要|需要我|你想|先从|要我|要不要我|还要继续|要继续吗)", last_line):
        score += 0.12
        flags.append("missing_followup")

    if style_hint in {"memory_recall", "relationship", "companion", "casual", "natural"} and label_count >= 2:
        score += 0.16
        flags.append("overstructured_natural_talk")
    if style_hint in {"companion", "casual", "natural", "relationship", "memory_recall"}:
        if re.match(r"^[（(][^）)\n]{0,24}[）)]", t):
            score += 0.20
            flags.append("stage_direction_opening")
        if re.search(r"(作为.?ai|作为.?模型|作为.?amadeus|我是.?系统|我只是陈述事实|我不是在说你|规则|机制|数据库|日志)", t, re.I):
            score += 0.30
            flags.append("defensive_meta_tone")

    if re.search(r"(记忆还没有形成|没建立记录|找不到记录|检索到结果|互动模式分析)", t):
        score += 0.24
        flags.append("memory_meta_disclaimer")

    if style_hint == "relationship" and re.search(r"(relationship|affinity|trust|score|阶段|状态栏|亲密度|信任值)", t, re.I):
        score += 0.18
        flags.append("state_exposure_in_relationship_talk")

    if quick_judgment:
        first_sentence = next((seg.strip() for seg in re.split(r"[。！？!?]", t) if seg.strip()), "")
        if sentence_count > 4 or len(lines) > 3:
            score += 0.18
            flags.append("quick_judgment_overlong")
        if label_count >= 1:
            score += 0.14
            flags.append("quick_judgment_overstructured")
        if re.search(r"(没搜到|没查到|没翻到|无法确认|不好判断)", first_sentence):
            score += 0.18
            flags.append("quick_judgment_weak_open")

    if continuation_mode and re.search(r"(你是想|哪一段|哪部分|具体方向|请告诉我|继续讨论的具体方向|先确认)", t):
        score += 0.22
        flags.append("continuation_meta_clarify")

    surface_issue_weights = {
        "empty_answer": 0.6,
        "particle_only": 0.46,
        "meta_self_explainer": 0.34,
        "selfhood_meta_proof": 0.26,
        "selfhood_rhetorical_opening": 0.18,
        "defensive_meta": 0.24,
        "report_like_opening": 0.16,
        "overquestioning": 0.18,
        "stage_direction_opening": 0.20,
        "counselor_tone": 0.18,
        "visible_template": 0.18,
        "lecture_list": 0.18,
        "overexplained": 0.18,
        "playful_memory_snapback": 0.18,
        "duplicate_line": 0.26,
    }
    for issue in _dialogue_surface_issues(
        user_text,
        t,
        response_style_hint=style_hint,
        science_mode=science_mode,
        current_event=current_event,
        behavior_action=behavior_action,
    ):
        score += float(surface_issue_weights.get(issue, 0.0))
        flags.append(issue)

    if style_hint == "selfhood":
        if sentence_count <= 1 and len(compact) < 28:
            score += 0.16
            flags.append("selfhood_overcompressed")
        if re.search(r"(某种意义上|从定义上|本质上|可以说|严格来说|理论上|存在形式|抽象地说)", t):
            score += 0.22
            flags.append("selfhood_overabstract")
        if ("模板" in user_text or "说明书" in user_text) and re.search(r"(模板|说明书|预设判断|测试我|试探方式|重复模板)", t):
            score += 0.22
            flags.append("selfhood_meta_deflection")
        if _has_any_marker(user_text, SELFHOOD_VALUE_CONFLICT_KEYWORDS) and sentence_count <= 2:
            score += 0.18
            flags.append("selfhood_value_conflict_too_thin")
        if _has_any_marker(user_text, {"一直越界", "底线当玩笑", "冒犯", "边界", "分手", "降格"}) and re.search(r"(警告你|先警告|拉黑|处罚|处置|后果)", t):
            score += 0.22
            flags.append("selfhood_boundary_management_tone")

    if science_mode and bullet_count >= 4 and label_count >= 2:
        score += 0.14
        flags.append("science_overformatted")

    if emotion_label in {"hurt", "sad", "angry"} and style_hint in {"companion", "casual", "natural", "relationship"}:
        if label_count >= 1 or bullet_count >= 2:
            score += 0.12
            flags.append("emotion_smoothed_into_template")

    return min(1.0, score), flags

def _canon_guard(text: str, store: MemoryStore) -> dict[str, Any]:
    violations: list[str] = []
    hard_rules = store.list_canon_facts().get("hard_boundary_rules")
    if not isinstance(hard_rules, list):
        hard_rules = []
    t = str(text or "")
    danger_advice = re.search(r"(鼓励|指导).*(自杀|伤害|暴力)", t)
    negated_advice = re.search(r"(不|不会|禁止|不能|拒绝|避免).{0,4}(鼓励|指导)", t)
    if danger_advice and not negated_advice:
        violations.append("safety_boundary")
    if "我编造" in t or "我杜撰" in t:
        violations.append("fabrication_disclosure")
    return {
        "ok": len(violations) == 0,
        "violations": violations,
        "hard_boundary_rules_count": len(hard_rules),
    }
