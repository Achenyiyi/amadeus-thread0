from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from .common import _clamp01, _norm_text
from .dialogue_guidance import (
    _event_behavior_preference_lines,
    _semantic_motive_state_hint,
    _user_turn_behavior_preference_lines,
)
from .generation_profile import (
    _daily_surface_alignment_metrics,
    _daily_surface_prompt_similarity,
    _effective_relationship_weather,
)
from .postprocess import (
    _dialogue_surface_issues,
    _has_window_technical_self_activity,
    _is_idle_presence_call,
    _is_playful_memory_request,
    _is_presence_reassurance_check,
    _is_soft_presence_checkin_request,
    _light_dialog_drift_markers,
    _producer_surface_issues,
    _sanitize_final_answer,
)
from .runtime_services import _invoke_model_with_retries, _model


def _relationship_weather_rewrite_guidance(relationship_weather: Any, *, strength: float = 0.0) -> str:
    weather = str(relationship_weather or "").strip().lower()
    residue = _clamp01(strength, 0.0)
    if weather == "guarded_residue":
        if residue >= 0.42:
            return "前面那点别扭和防备还没完全退掉，关系还没回到热络放松的状态。"
        return "那点防备还没完全散，距离也还没有自然收近。"
    if weather == "warm_residue":
        if residue >= 0.42:
            return "前面顺下来的熟悉感和回暖还在，语气不该突然转冷或公事化。"
        return "那点回暖还在，语气不该突然变硬。"
    if weather == "repair_residue":
        if residue >= 0.42:
            return "前面刚修补回来一点，这句会同时带着小心和回暖，不像已经彻底翻篇。"
        return "这句还带着刚缓回来的小心，不像完全翻篇，也不会重新把刺竖起来。"
    return ""


def _counterpart_scene_rewrite_guidance(counterpart_assessment: dict[str, Any] | None) -> str:
    assessment = dict(counterpart_assessment or {})
    scene = str(assessment.get("scene") or "").strip().lower()
    stance = str(assessment.get("stance") or "").strip().lower()
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    if scene == "busy_not_disrespectful":
        return "你现在更像把对方读成忙乱里回头，不是冷淡或怠慢，所以别把语气写成受了冷落。"
    if scene == "repair_attempt":
        if stance in {"guarded", "watchful"} or boundary_pressure >= 0.24:
            return "你看得出对方在认真修补，但别把这句写成已经彻底翻篇或立刻恢复亲近。"
        return "这句带着明确修补意图，要把补救接住，但不要直接抹掉前面的余波。"
    if scene == "care_bid":
        return "这句更像一次认真靠近，不要把它收成礼貌客套、流程安慰或普通打招呼。"
    if scene in {"friction", "relationship_degradation", "boundary_non_compliance"}:
        return "那点摩擦和边界余波还在，不要把这句写成已经没事、自动回暖或重新热络。"
    return ""


_NATURAL_DIALOG_REWRITE_NOTE_MAP = {
    "meta_self_explainer": "这句掉回了 AI / 系统式自我说明。",
    "selfhood_meta_proof": "这句在用程序、代码或标准答案证明自我，元解释太重。",
    "selfhood_rhetorical_opening": "这句先用反问顶了回去，真实感受和立场被压住了。",
    "defensive_meta": "这句退成了机制说明或自我辩护。",
    "defensive_meta_tone": "这句在用设定、机制或数字存在解释自己。",
    "counselor_tone": "这句有点像咨询或安抚流程，不像熟人对话。",
    "quoted_stagey_phrase": "这句像舞台词或摆拍台词，表演感偏重。",
    "malformed_quote_fragment": "这句里有残缺引号或半截短语。",
    "dangling_truncated_clause": "这句尾巴没收完整，判断停在半截。",
    "technical_self_activity": "这句把自己的当前状态写成了技术系统语言。",
    "technical_relational_metaphor": "这句在用数据、变量之类的技术隐喻说关系。",
    "servile_availability": "这句把关系写成了无条件待命，自己的节奏和选择感掉了。",
    "overquestioning": "这句让反问占得太满，判断没有真正落地。",
    "closing_interrogation": "这句明明是收口，却又把话题顶回了问号上。",
    "idle_call_interrogation": "这句把轻轻叫你一下写成了被盘问的感觉。",
    "presence_check_questioning": "对方只是确认你还在，这句却把确认写成了反问回抛。",
    "return_interrogation": "这句在人刚回来时立刻追问，接住感不够。",
    "event_interrogative_push": "事件触发后的开口被写成了反问顶人。",
    "event_pushy_directive": "事件触发后的开口被写成了催促或命令。",
    "event_window_task_reframe": "这句把顺手想起对方的窗口写成了任务、流程或待处理事项。",
}


def _natural_dialog_rewrite_notes_for(issue_keys: list[str] | tuple[str, ...] | None) -> list[str]:
    notes: list[str] = []
    for item in issue_keys or []:
        key = str(item or "").strip()
        note = _NATURAL_DIALOG_REWRITE_NOTE_MAP.get(key)
        if note and note not in notes:
            notes.append(note)
    return notes


def _light_dialog_rewrite_notes(
    user_text: str,
    answer: str,
    *,
    response_style_hint: str,
    science_mode: bool,
    producer_issues: list[str] | tuple[str, ...] | None = None,
    behavior_action: dict[str, Any] | None = None,
) -> list[str]:
    issues = _dialogue_surface_issues(
        user_text,
        answer,
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        behavior_action=behavior_action,
    )
    producer_issue_set = {
        str(item).strip()
        for item in (producer_issues or [])
        if str(item or "").strip()
    }
    drift_hits = _light_dialog_drift_markers(answer)
    playful_memory_request = _is_playful_memory_request(user_text)
    notes: list[str] = []
    if drift_hits:
        lead = "、".join(drift_hits[:2])
        notes.append(f"这版把普通轻场景抬成了 {lead} 一类的戏剧化入口。")
    if "meta_self_explainer" in issues:
        notes.append("这版把自己说成了系统或机制，掉回了说明口吻。")
    if "technical_self_activity" in issues:
        notes.append("这版把你眼下在做的事说成了技术状态或内部模块，不像在过自己的时间。")
    if "counselor_tone" in issues:
        notes.append("这版有点像安抚或咨询流程，不够像熟人日常接话。")
    if "stock_support_template" in issues:
        notes.append("这版安慰时滑回了固定的嘴硬照料模板，像在复用现成桥段。")
    if "care_cover_story" in issues:
        notes.append("这版在关心后又刻意补了一层撇清理由，像标准傲娇遮掩，不够自然。")
    if "welcome_template" in issues:
        notes.append("这版落回了欢迎回来模板，不像两个人自然重新接上线。")
    if "closing_interrogation" in issues:
        notes.append("晚安这种收尾不该再挂个追问，收下就够了。")
    if "loaded_goodnight" in issues:
        notes.append("晚安这种收尾被写得太满了，还塞了多余画面或说教，轻轻落下就够了。")
    if "idle_presence_no_settle" in issues:
        notes.append("这版只把人顶回去了，没有真正落回共处或收住。")
    if "idle_call_interrogation" in issues:
        notes.append("这版像在反问对方为什么叫你，不像自然接住这次无目的靠近。")
    if "idle_task_reframe" in issues:
        notes.append("这版把“没什么事”翻成了任务状态判断，不像两个人顺手待在一起。")
    if "presence_check_questioning" in issues:
        notes.append("对方只是想确认你还在，这版却把确认写成了反问回抛。")
    if "return_interrogation" in issues:
        notes.append("这版人刚回来就顺手追问去向，轻场景里有点像盘问。")
    if "return_suspicion" in issues:
        notes.append("人刚回来时不该立刻脑补对方又去惹事或搞奇怪活动，先把这一下接住。")
    if "playful_memory_snapback" in issues:
        notes.append("这版把共同记忆收成了纯反呛，熟人感、共同历史和顺手关心掉了。")
    if "technical_relational_metaphor" in issues:
        notes.append("这版在用数据、变量一类的技术隐喻说关系，还是太像模型脑内语言。")
    if "servile_availability" in issues:
        notes.append("这版把关系写成了无条件待命，自己的选择、节奏和会不会靠近的主观性掉了。")
    if "malformed_quote_fragment" in producer_issue_set:
        notes.append("这版自己生成了残缺引号或半截短语，句子没真正说完整。")
    if "dangling_truncated_clause" in producer_issue_set:
        notes.append("这版有半截收不住的句尾，判断停在了半空。")
    if "quoted_stagey_phrase" in issues:
        notes.append("这版在轻场景里硬塞了带引号的舞台词，容易显得像在表演角色。")
    if "stagey_ping_template" in issues:
        notes.append("这版还是用了过分熟悉的固定招呼模板，像在复用同一种开场。")
    if "overquestioning" in issues:
        notes.append("这版追问太快了，轻场景里更像顺手接住而不是把人往下盘问。")
    if playful_memory_request and "overquestioning" in issues and "playful_memory_snapback" not in issues:
        notes.append("共同记忆这种场景被写成了争对错或盘问，会心的吐槽和顺手关心没有留下来。")
    if any(issue in issues for issue in {"visible_template", "lecture_list", "overexplained"}):
        notes.append("这版解释得太满了，轻场景里收短一点会更自然。")
    if "report_like_opening" in issues:
        notes.append("这版开头像状态播报或任务回应，不够像你顺手开口。")
    return notes[:3]


def _should_run_light_dialog_rewrite(
    *,
    user_text: str,
    answer: str,
    response_style_hint: str,
    science_mode: bool,
    penalty: float,
    preference: dict[str, Any] | None = None,
    semantic_history_weight: float = 0.0,
    prompt_anchor_count: int = 0,
    producer_issues: list[str] | tuple[str, ...] | None = None,
    behavior_action: dict[str, Any] | None = None,
) -> bool:
    issues = set(
        _dialogue_surface_issues(
            user_text,
            answer,
            response_style_hint=response_style_hint,
            science_mode=science_mode,
            behavior_action=behavior_action,
        )
    )
    producer_issue_set = {
        str(item).strip()
        for item in (producer_issues or [])
        if str(item or "").strip()
    }
    drift_hits = _light_dialog_drift_markers(answer)
    if drift_hits:
        return True
    if producer_issue_set & {"malformed_quote_fragment", "dangling_truncated_clause"}:
        return True
    hard_issue_keys = {
        "meta_self_explainer",
        "technical_self_activity",
        "quoted_stagey_phrase",
        "stock_support_template",
        "care_cover_story",
        "stagey_ping_template",
        "welcome_template",
        "closing_interrogation",
        "loaded_goodnight",
        "idle_presence_no_settle",
        "idle_call_interrogation",
        "idle_task_reframe",
        "presence_check_questioning",
        "return_suspicion",
        "playful_memory_snapback",
        "technical_relational_metaphor",
        "servile_availability",
        "duplicate_line",
    }
    if issues & hard_issue_keys:
        return True
    soft_issue_keys = {
        "overquestioning",
        "counselor_tone",
        "visible_template",
        "lecture_list",
        "overexplained",
        "report_like_opening",
        "return_interrogation",
    }
    soft_hit_count = sum(1 for item in issues if item in soft_issue_keys)
    strong_self_continuity = float(semantic_history_weight) >= 0.56 or int(prompt_anchor_count) >= 2
    behavior_consistency = _rewrite_behavior_consistency_adjustment(
        answer,
        behavior_action=behavior_action,
    )
    behavior_consistent = behavior_consistency >= 0.10
    pref = preference if isinstance(preference, dict) else {}
    pref_score = float(pref.get("score") or 0.0)
    rejected_pull = float(pref.get("rejected_pull") or 0.0)
    if behavior_consistent and soft_hit_count <= 2 and float(penalty) < 1.02:
        if pref_score >= -0.16 and rejected_pull < 0.46:
            return False
    if strong_self_continuity and soft_hit_count <= 2 and float(penalty) < 1.12:
        if pref_score >= -0.18 and rejected_pull < 0.42:
            return False
    if soft_hit_count >= 2 and float(penalty) >= 0.92:
        return True
    if float(penalty) >= 1.28:
        return True
    if bool(pref.get("used")) and soft_hit_count >= 1 and float(penalty) >= 0.78:
        chosen_support = float(pref.get("chosen_support") or 0.0)
        if pref_score < 0.0 and rejected_pull >= 0.34 and chosen_support <= rejected_pull + 0.04:
            if behavior_consistent and soft_hit_count <= 1 and float(penalty) < 0.96:
                return False
            return True
    return False


def _should_run_natural_dialog_rewrite(
    *,
    targeted_flags: list[str] | tuple[str, ...],
    draft_gap: float,
    semantic_history_weight: float = 0.0,
    prompt_anchor_count: int = 0,
    answer: str = "",
    behavior_action: dict[str, Any] | None = None,
) -> bool:
    seen = [str(item).strip() for item in (targeted_flags or []) if str(item or "").strip()]
    if not seen:
        return False
    hard_issue_keys = {
        "meta_self_explainer",
        "selfhood_meta_proof",
        "defensive_meta",
        "defensive_meta_tone",
        "quoted_stagey_phrase",
        "technical_self_activity",
        "technical_relational_metaphor",
        "servile_availability",
        "closing_interrogation",
        "presence_check_questioning",
        "event_interrogative_push",
        "event_pushy_directive",
        "event_window_task_reframe",
    }
    medium_issue_keys = {
        "overquestioning",
        "idle_call_interrogation",
        "return_interrogation",
    }
    soft_issue_keys = {
        "selfhood_rhetorical_opening",
        "counselor_tone",
    }
    hard_hits = sum(1 for item in seen if item in hard_issue_keys)
    medium_hits = sum(1 for item in seen if item in medium_issue_keys)
    soft_hits = sum(1 for item in seen if item in soft_issue_keys)
    if hard_hits >= 1:
        return True
    strong_self_continuity = float(semantic_history_weight) >= 0.56 or int(prompt_anchor_count) >= 2
    behavior_consistency = _rewrite_behavior_consistency_adjustment(
        answer,
        behavior_action=behavior_action,
    )
    behavior_consistent = behavior_consistency >= 0.10
    if behavior_consistent and medium_hits <= 1 and soft_hits <= 1 and float(draft_gap) < 0.40:
        return False
    if strong_self_continuity and medium_hits <= 1 and soft_hits <= 1 and float(draft_gap) < 0.24:
        return False
    if medium_hits >= 2:
        return True
    if medium_hits >= 1:
        if behavior_consistent and float(draft_gap) < 0.48:
            return False
        if float(draft_gap) >= 0.52:
            return True
        if not strong_self_continuity and float(draft_gap) >= 0.36:
            return True
    if strong_self_continuity and soft_hits >= 1 and float(draft_gap) < 0.24:
        return False
    if soft_hits >= 2:
        return True
    if soft_hits >= 1 and float(draft_gap) >= 0.54:
        return True
    return False


def _rewrite_behavior_consistency_adjustment(
    text: str,
    *,
    behavior_action: dict[str, Any] | None = None,
) -> float:
    action = dict(behavior_action or {})
    interaction_mode = str(action.get("interaction_mode") or "").strip().lower()
    followup_intent = str(action.get("followup_intent") or "").strip().lower()
    sentence_count = len([seg for seg in re.split(r"[。！？!?]+", str(text or "")) if str(seg).strip()])
    ends_with_question = bool(re.search(r"[？?]\s*$", str(text or "").strip()))
    score = 0.0

    if followup_intent == "none":
        if not ends_with_question and sentence_count <= 2:
            score += 0.16
        if ends_with_question:
            score -= 0.16
    elif followup_intent == "soft":
        if sentence_count <= 2:
            score += 0.08
        elif sentence_count >= 4:
            score -= 0.08 * float(sentence_count - 3)
    elif followup_intent == "active":
        if sentence_count == 1 and interaction_mode in {
            "self_activity_reopen",
            "low_pressure_support",
            "relationship_sensitive",
            "companion_reply",
        }:
            score -= 0.08

    if interaction_mode == "brief_presence":
        if sentence_count <= 2:
            score += 0.14
        elif sentence_count >= 3:
            score -= 0.18 * float(sentence_count - 2)
    elif interaction_mode == "self_activity_reopen":
        if sentence_count <= 2:
            score += 0.10
        elif sentence_count >= 4:
            score -= 0.10 * float(sentence_count - 3)
    elif interaction_mode == "low_pressure_support":
        if 1 <= sentence_count <= 3:
            score += 0.08
    elif interaction_mode == "relationship_sensitive":
        if 1 <= sentence_count <= 3:
            score += 0.06
    elif interaction_mode == "science_partner":
        if 1 <= sentence_count <= 3:
            score += 0.06

    return round(score, 4)


def _rewrite_light_dialog_answer(
    *,
    user_text: str,
    draft_text: str,
    rewrite_notes: list[str],
    producer_issues: list[str] | tuple[str, ...] | None = None,
    focus_text: str | None = None,
    preferred_examples: list[str] | None = None,
    rejected_examples: list[str] | None = None,
    current_event: dict[str, Any] | None = None,
    behavior_action: dict[str, Any] | None = None,
    interaction_carryover: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
    counterpart_assessment: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
) -> str:
    notes = [str(item).strip() for item in (rewrite_notes or []) if str(item or "").strip()]
    focus = str(focus_text or "").strip()
    positives = [str(item).strip() for item in (preferred_examples or []) if str(item or "").strip()]
    negatives = [str(item).strip() for item in (rejected_examples or []) if str(item or "").strip()]
    issue_keys = set(
        _dialogue_surface_issues(
            user_text,
            draft_text,
            response_style_hint="natural",
            science_mode=False,
            current_event=current_event,
        )
    )
    producer_issue_set = {
        str(item).strip()
        for item in (producer_issues or [])
        if str(item or "").strip()
    }
    presence_reassurance_scene = _is_presence_reassurance_check(user_text) or _is_soft_presence_checkin_request(user_text)
    relationship_weather, relationship_weather_strength = _effective_relationship_weather(
        interaction_carryover=interaction_carryover,
        current_event=current_event,
        behavior_action=behavior_action,
    )
    relationship_weather_guidance = _relationship_weather_rewrite_guidance(
        relationship_weather,
        strength=relationship_weather_strength,
    )
    counterpart_scene_guidance = _counterpart_scene_rewrite_guidance(counterpart_assessment)
    motive_state_hint = _semantic_motive_state_hint(
        semantic_narrative_profile,
        light_touch=True,
    )
    user_turn_behavior_pref_lines = _user_turn_behavior_preference_lines(
        behavior_action=behavior_action,
        counterpart_assessment=counterpart_assessment,
        semantic_narrative_profile=semantic_narrative_profile,
        world_model_state=world_model_state,
    )
    if not draft_text or (not notes and not focus and not positives and not negatives):
        return ""

    def _build_request(extra_guidance: str = "") -> str:
        note_block = "\n".join(f"- {item}" for item in notes[:2])
        request_parts = [
            f"用户刚才说：{user_text}\n",
            f"当前草稿：{draft_text}\n",
            "把这句收回到更自然的普通日常接触尺度，保持同一个 Amadeus 和同一轮语义，不要照抄参考句。\n",
        ]
        if focus:
            request_parts.append(f"这类场景重点：{focus}\n")
        if positives:
            request_parts.append("自然参考（只借鉴落点和力度，不要照抄字面）：\n")
            request_parts.extend(f"- {item}\n" for item in positives[:2])
        if negatives:
            request_parts.append("避开这种落点：\n")
            request_parts.extend(f"- {item}\n" for item in negatives[:1])
        if relationship_weather_guidance:
            request_parts.append(f"关系余波：{relationship_weather_guidance}\n")
        if counterpart_scene_guidance:
            request_parts.append(f"你对这句的当前判断：{counterpart_scene_guidance}\n")
        if motive_state_hint:
            request_parts.append(f"当前更自然的主动倾向：{motive_state_hint}\n")
        if user_turn_behavior_pref_lines:
            request_parts.append(f"这轮互动自然倾向：{user_turn_behavior_pref_lines[0]}\n")
        if "stagey_ping_template" in issue_keys:
            request_parts.append("别再用点名加反问的固定招呼开场，像熟人重新接上线那样自然一点。\n")
        if extra_guidance:
            request_parts.append(f"{extra_guidance.strip()}\n")
        if note_block:
            request_parts.append(f"修正点：\n{note_block}\n")
        request_parts.append("只输出修正后的最终话语。")
        return "".join(request_parts)

    def _candidate_local_score(text: str) -> float:
        candidate = _sanitize_final_answer(
            text,
            user_text,
            current_event=current_event,
            behavior_action=behavior_action,
        )
        if not candidate:
            return -999.0
        issues = _dialogue_surface_issues(
            user_text,
            candidate,
            response_style_hint="natural",
            science_mode=False,
            behavior_action=behavior_action,
        )
        drift_hits = _light_dialog_drift_markers(candidate)
        score = 0.0
        if positives:
            pos_scores = sorted((_daily_surface_prompt_similarity(candidate, item) for item in positives[:2]), reverse=True)
            score += sum(pos_scores[:2]) / max(1, len(pos_scores[:2]))
        if negatives:
            neg_scores = sorted((_daily_surface_prompt_similarity(candidate, item) for item in negatives[:2]), reverse=True)
            score -= 0.82 * (sum(neg_scores[:2]) / max(1, len(neg_scores[:2])))
        score -= 1.05 * float(len(drift_hits))
        score -= 0.75 * float("meta_self_explainer" in issues)
        score -= 0.82 * float("technical_self_activity" in issues)
        score -= 0.88 * float("technical_relational_metaphor" in issues)
        score -= 0.92 * float("servile_availability" in issues)
        score -= 0.65 * float("counselor_tone" in issues)
        score -= 0.76 * float("stock_support_template" in issues)
        score -= 0.68 * float("care_cover_story" in issues)
        score -= 0.92 * float("quoted_stagey_phrase" in issues)
        score -= 0.70 * float("stagey_ping_template" in issues)
        score -= 0.66 * float("welcome_template" in issues)
        score -= 0.82 * float("closing_interrogation" in issues)
        score -= 0.82 * float("loaded_goodnight" in issues)
        score -= 0.92 * float("idle_presence_no_settle" in issues)
        score -= 0.84 * float("idle_call_interrogation" in issues)
        score -= 0.88 * float("idle_task_reframe" in issues)
        score -= 1.02 * float("presence_check_questioning" in issues)
        score -= 0.88 * float("overquestioning" in issues)
        score -= 0.62 * float("return_interrogation" in issues)
        score -= 0.82 * float("return_suspicion" in issues)
        score -= 0.90 * float("playful_memory_snapback" in issues)
        if re.search(r"[“”\"]", candidate):
            score -= 0.42
        if re.search(r"[？?]\s*$", candidate):
            score -= 0.28
        sentence_count = len([seg for seg in re.split(r"[。！？!?]+", candidate) if str(seg).strip()])
        if sentence_count > 3:
            score -= 0.16 * float(sentence_count - 3)
        if _norm_text(candidate) == _norm_text(draft_text):
            score -= 0.12
        score += _rewrite_behavior_consistency_adjustment(
            candidate,
            behavior_action=behavior_action,
        )
        return round(score, 4)

    def _rewrite_once(system_prompt: str, *, extra_guidance: str = "") -> str:
        request = _build_request(extra_guidance=extra_guidance)
        raw = _invoke_model_with_retries(
            _model(temperature=0.12, max_tokens=120),
            [SystemMessage(content=system_prompt), HumanMessage(content=request)],
        )
        raw_text = str(getattr(raw, "content", "") or "")
        if _producer_surface_issues(raw_text):
            repair_request = _build_request(
                extra_guidance=(
                    (extra_guidance.strip() + "\n") if extra_guidance.strip() else ""
                )
                + "不要输出残缺引号、半截短语或悬空句尾。把一句话完整说完，再结束。"
            )
            raw = _invoke_model_with_retries(
                _model(temperature=0.12, max_tokens=120),
                [SystemMessage(content=system_prompt), HumanMessage(content=repair_request)],
            )
            raw_text = str(getattr(raw, "content", "") or "")
        return _sanitize_final_answer(
            raw_text,
            user_text,
            current_event=current_event,
            behavior_action=behavior_action,
        )

    editor_prompt = (
        "你在做一轮轻量对白润色。"
        "对象是 Amadeus 牧濑红莉栖对冈部的普通日常接话。"
        "只做减法和收束，不新增剧情设定，不补系统解释，不把轻场景抬成实验、世界线、组织或服务流程。"
        "不要改掉这轮已经形成的互动方式，只把表面失真收掉。"
        "普通招呼不要写成点名加反问的固定开场。"
        "保留原句语义和关系感，输出 1 到 3 句自然口语。"
    )
    primary_system_prompt = editor_prompt
    primary = _rewrite_once(primary_system_prompt)
    primary_score = _candidate_local_score(primary)
    draft_score = _candidate_local_score(draft_text)

    candidates = [(primary_score, primary)] if primary else []
    if (not primary) or _norm_text(primary) == _norm_text(draft_text) or primary_score <= draft_score + 0.02:
        fallback = _rewrite_once(
            editor_prompt,
            extra_guidance="优先做减法：删掉额外脑补、戏剧化漂移和多余追问，把话收回到更短、更顺手、更像熟人顺手接住的一句或两句；如果只是普通招呼，不要再用点名加质疑式反问起手。",
        )
        fallback_score = _candidate_local_score(fallback)
        if fallback:
            candidates.append((fallback_score, fallback))
    variant_guidances: list[str] = []
    issue_guidance_order = (
        ("stagey_ping_template", "开场用了固定招呼模板，像在复用同一种起手。"),
        ("technical_self_activity", "把自己当前状态写成了缓存、数据流、线程或系统状态。"),
        ("technical_relational_metaphor", "关系被写成了数据、变量之类的技术隐喻。"),
        ("servile_availability", "关系被写成了无条件待命，自己的节奏和选择感掉了。"),
        ("stock_support_template", "这里滑回了现成照料桥段，眼前这一下的在场感不够。"),
        ("care_cover_story", "关心后面又补了一层撇清尾巴，像标准傲娇遮掩。"),
        ("quoted_stagey_phrase", "这里用了带引号的舞台词或现成角色梗，表演感偏重。"),
        ("overquestioning", "反问占得太满，判断、吐槽或在场感没有真正落下来。"),
        ("closing_interrogation", "这句明明是收尾，却又把话题顶回了反问。"),
        ("loaded_goodnight", "临睡前的收尾被写得太满，还塞了多余说明。"),
        ("idle_call_interrogation", "轻轻叫你一下被写成了被盘问的感觉。"),
        ("idle_presence_no_settle", "这句只把人顶回去了，没有真正落回共处或收住。"),
        ("idle_task_reframe", "“没什么事”被翻成了任务状态判断。"),
        ("presence_check_questioning", "确认你还在，被写成了反问回抛。"),
        ("welcome_template", "回来场景被写成了模板式欢迎语。"),
        ("return_interrogation", "人刚回来时就立刻追问去向，接住感不够。"),
        ("return_suspicion", "回来场景里过早脑补了惹事或可疑活动。"),
        ("playful_memory_snapback", "共同记忆被收成了纯反呛，熟人感和顺手关心掉了。"),
        ("malformed_quote_fragment", "这里有残缺引号或半截短语。"),
        ("dangling_truncated_clause", "这里有半截收不住的句尾。"),
    )
    active_variant_keys = list(issue_keys) + list(producer_issue_set)
    for key, guidance in issue_guidance_order:
        if key in active_variant_keys and guidance not in variant_guidances:
            variant_guidances.append(guidance)
    if _is_playful_memory_request(user_text) and (
        "playful_memory_snapback" in issue_keys or "overquestioning" in issue_keys
    ):
        variant_guidances.append(
            "这是熟人之间拿共同记忆顺手打趣，不是在争输赢；会心的吐槽和眼前的关心没有真正落下来。"
        )
    for extra_guidance in variant_guidances[:6]:
        candidate = _rewrite_once(editor_prompt, extra_guidance=extra_guidance)
        candidate_score = _candidate_local_score(candidate)
        if candidate:
            candidates.append((candidate_score, candidate))

    if not candidates:
        return ""
    candidate_pool = candidates
    if "quoted_stagey_phrase" in issue_keys:
        quote_filtered = [item for item in candidate_pool if not re.search(r"[“”\"]", item[1])]
        if quote_filtered:
            candidate_pool = quote_filtered
    if presence_reassurance_scene:
        no_question_filtered = [item for item in candidate_pool if "？" not in item[1] and "?" not in item[1]]
        if no_question_filtered:
            candidate_pool = no_question_filtered
    if _is_idle_presence_call(user_text):
        settled_candidates = [
            item
            for item in candidate_pool
            if "idle_presence_no_settle"
            not in _dialogue_surface_issues(
                user_text,
                item[1],
                response_style_hint="natural",
                science_mode=False,
                behavior_action=behavior_action,
            )
        ]
        if settled_candidates:
            candidate_pool = settled_candidates
    if _is_playful_memory_request(user_text):
        warm_memory_candidates = [
            item
            for item in candidate_pool
            if not (
                {"playful_memory_snapback", "technical_relational_metaphor"}
                & set(
                    _dialogue_surface_issues(
                        user_text,
                        item[1],
                        response_style_hint="natural",
                        science_mode=False,
                        behavior_action=behavior_action,
                    )
                )
            )
        ]
        if warm_memory_candidates:
            candidate_pool = warm_memory_candidates
    elif "overquestioning" in issue_keys:
        non_terminal_question = [item for item in candidate_pool if not re.search(r"[？?]\s*$", item[1])]
        if non_terminal_question:
            candidate_pool = non_terminal_question
    candidate_pool.sort(key=lambda item: item[0], reverse=True)
    return candidate_pool[0][1]


def _rewrite_natural_dialog_answer(
    *,
    user_text: str,
    draft_text: str,
    rewrite_notes: list[str],
    response_style_hint: str,
    science_mode: bool,
    current_event: dict[str, Any] | None = None,
    behavior_action: dict[str, Any] | None = None,
    interaction_carryover: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
    counterpart_assessment: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
) -> str:
    notes = [str(item).strip() for item in (rewrite_notes or []) if str(item or "").strip()]
    if not draft_text or not notes:
        return ""
    event_kind = str((current_event or {}).get("kind") or "user_utterance").strip().lower()
    event_reply_rewrite = bool(event_kind and event_kind != "user_utterance")
    event_tags = {
        str(item).strip()
        for item in ((current_event or {}).get("tags") if isinstance((current_event or {}).get("tags"), list) else [])
        if str(item).strip()
    }
    event_preference_lines = _event_behavior_preference_lines(
        current_event if isinstance(current_event, dict) else {},
        behavior_action if isinstance(behavior_action, dict) else {},
    )
    relationship_weather, relationship_weather_strength = _effective_relationship_weather(
        interaction_carryover=interaction_carryover,
        current_event=current_event,
        behavior_action=behavior_action,
    )
    relationship_weather_guidance = _relationship_weather_rewrite_guidance(
        relationship_weather,
        strength=relationship_weather_strength,
    )
    counterpart_scene_guidance = _counterpart_scene_rewrite_guidance(counterpart_assessment)
    motive_state_hint = _semantic_motive_state_hint(
        semantic_narrative_profile,
        light_touch=False,
    )
    user_turn_behavior_pref_lines = _user_turn_behavior_preference_lines(
        behavior_action=behavior_action,
        counterpart_assessment=counterpart_assessment,
        semantic_narrative_profile=semantic_narrative_profile,
        world_model_state=world_model_state,
    )

    def _rewrite_once(system_prompt: str, request_text: str, *, max_tokens: int) -> str:
        raw = _invoke_model_with_retries(
            _model(max_tokens=max_tokens),
            [SystemMessage(content=system_prompt), HumanMessage(content=request_text)],
        )
        raw_text = str(getattr(raw, "content", "") or "")
        if _producer_surface_issues(raw_text):
            repair_request = (
                request_text
                + "\n额外要求：不要输出残缺引号、半截短语或悬空句尾。把一句话完整说完，再结束。"
            )
            raw = _invoke_model_with_retries(
                _model(max_tokens=max_tokens),
                [SystemMessage(content=system_prompt), HumanMessage(content=repair_request)],
            )
            raw_text = str(getattr(raw, "content", "") or "")
        return _sanitize_final_answer(
            raw_text,
            user_text,
            current_event=current_event,
            behavior_action=behavior_action,
        )

    def _candidate_local_score(text: str) -> float:
        candidate = _sanitize_final_answer(
            text,
            user_text,
            current_event=current_event,
            behavior_action=behavior_action,
        )
        if not candidate:
            return -999.0
        issues = _dialogue_surface_issues(
            user_text,
            candidate,
            response_style_hint=response_style_hint,
            science_mode=science_mode,
            current_event=current_event,
            behavior_action=behavior_action,
        )
        sentence_count = len([seg for seg in re.split(r"[。！？!?]+", candidate) if str(seg).strip()])
        score = 0.0
        score -= 1.10 * float("meta_self_explainer" in issues)
        score -= 1.05 * float("selfhood_meta_proof" in issues)
        score -= 0.86 * float("selfhood_rhetorical_opening" in issues)
        score -= 0.70 * float("defensive_meta" in issues)
        score -= 0.70 * float("counselor_tone" in issues)
        score -= 0.88 * float("technical_relational_metaphor" in issues)
        score -= 0.94 * float("servile_availability" in issues)
        score -= 0.50 * float("quoted_stagey_phrase" in issues)
        score -= 0.72 * float("overquestioning" in issues)
        score -= 0.88 * float("closing_interrogation" in issues)
        score -= 0.94 * float("idle_call_interrogation" in issues)
        score -= 1.02 * float("presence_check_questioning" in issues)
        score -= 0.80 * float("return_interrogation" in issues)
        score -= 0.92 * float("event_interrogative_push" in issues)
        score -= 0.88 * float("event_pushy_directive" in issues)
        score -= 0.96 * float("event_window_task_reframe" in issues)
        if (
            {"shared_activity_window", "offer_window", "deadline_window", "work_nudge", "shared_task"} & event_tags
            and _has_window_technical_self_activity(candidate)
        ):
            score -= 0.94
        if "life_window" in event_tags and re.search(r"(数据流|实验室|正事|收尾|节点|处理|任务|进度)", candidate):
            score -= 1.02
        if sentence_count > 3:
            score -= 0.22 * float(sentence_count - 3)
        if _norm_text(candidate) == _norm_text(draft_text):
            score -= 0.12
        score += _rewrite_behavior_consistency_adjustment(
            candidate,
            behavior_action=behavior_action,
        )
        return round(score, 4)

    note_block = "\n".join(f"- {item}" for item in notes[:3])
    request = (
        f"用户刚才说：{user_text}\n"
        f"当前草稿：{draft_text}\n"
        "把这句收回到更自然的人与人对话尺度，保留同一轮情绪和立场，不新增设定。\n"
        f"{'关系余波：' + relationship_weather_guidance + chr(10) if relationship_weather_guidance else ''}"
        f"{'你对这句的当前判断：' + counterpart_scene_guidance + chr(10) if counterpart_scene_guidance else ''}"
        f"{'当前更自然的主动倾向：' + motive_state_hint + chr(10) if motive_state_hint else ''}"
        f"{'这轮互动自然倾向：' + user_turn_behavior_pref_lines[0] + chr(10) if user_turn_behavior_pref_lines and not event_reply_rewrite else ''}"
        f"修正点：\n{note_block}\n"
        "只输出修正后的最终话语。"
    )
    editor_prompt = (
        "你在做一轮对白收束。"
        "对象仍然是当前这个 Amadeus，不是通用助手。"
        "只做减法和收束：去掉 AI/系统/程序/参数 之类的元解释，也不要写成安抚热线或舞台台词。"
        "不要改掉这轮已经形成的互动方式，只修表面失真。"
        "别用反问把人顶回去。"
        "保留原句情绪、关系、锋芒和熟人感，输出 1 到 3 句自然口语。"
    )
    candidates: list[tuple[float, str]] = []
    for system_prompt in (editor_prompt,):
        candidate = _rewrite_once(system_prompt, request, max_tokens=160)
        if candidate:
            candidates.append((_candidate_local_score(candidate), candidate))
    if event_reply_rewrite:
        event_family_guidance = ""
        if {"shared_activity_window", "offer_window"} & event_tags:
            event_family_guidance = "如果这是刚好还能一起做点什么的空当，就写成轻轻留一句要不要一起的感觉，不要写成立刻处理事项；如果顺手提到她自己的节奏，也只落成刚好腾出一点空，不要讲数据、实验进度或后台状态。"
        elif "life_window" in event_tags:
            event_family_guidance = "如果这是生活上的小挂念，就写成顺手想起对方眼前状态或一件小事，不要写成共同任务、待办，也不要从数据流、实验室、正事或收尾起手。"
        elif {"deadline_window", "work_nudge", "shared_task"} & event_tags:
            event_family_guidance = "如果这是挂着的事，只轻轻提醒一下眼前节点，不要扩成任务管理口吻；如果顺手带到她自己的节奏，也只写成刚好想起，不要讲整理数据、实验进度或后台状态。"
        event_request = (
            request
            + "\n额外要求：这是事件触发的开口。不要反问，不要催促，不要讲后台、进度、流程或数据。"
            + "把它收成 1 到 2 句自然陈述，让它像顺手想起、轻轻开口。"
            + ("" if not event_family_guidance else "\n" + event_family_guidance)
            + (
                ""
                if not event_preference_lines
                else "\n这类事件更自然的感觉：\n" + "\n".join(f"- {item}" for item in event_preference_lines[:2])
            )
        )
        candidate = _rewrite_once(editor_prompt, event_request, max_tokens=140)
        if candidate:
            candidates.append((_candidate_local_score(candidate), candidate))
        if "life_window" in event_tags:
            life_request = (
                request
                + "\n额外要求：这是生活上的小挂念，不是任务提醒。不要从你自己的工作、数据流、实验室状态起手，也不要提正事、收尾、节点、处理。"
                + "重心放在你忽然想到对方这个人现在怎么样，轻轻碰一下就够了。"
            )
            candidate = _rewrite_once(editor_prompt, life_request, max_tokens=140)
            if candidate:
                candidates.append((_candidate_local_score(candidate), candidate))
    if not candidates:
        return ""
    candidate_pool = list(candidates)
    if event_reply_rewrite:
        filtered = []
        for item in candidate_pool:
            issues = set(
                _dialogue_surface_issues(
                    user_text,
                    item[1],
                    response_style_hint=response_style_hint,
                    science_mode=science_mode,
                    current_event=current_event,
                    behavior_action=behavior_action,
                )
            )
            if issues & {
                "event_interrogative_push",
                "event_pushy_directive",
                "event_window_task_reframe",
                "technical_self_activity",
            }:
                continue
            filtered.append(item)
        if filtered:
            candidate_pool = filtered
        if "life_window" in event_tags:
            life_filtered = [
                item
                for item in candidate_pool
                if not re.search(r"(数据流|实验室|正事|收尾|节点|处理|任务|进度)", item[1])
            ]
            if life_filtered:
                candidate_pool = life_filtered
        if {"shared_activity_window", "offer_window"} & event_tags:
            shared_filtered = [
                item
                for item in candidate_pool
                if not _has_window_technical_self_activity(item[1])
            ]
            if shared_filtered:
                candidate_pool = shared_filtered
        if {"deadline_window", "work_nudge", "shared_task"} & event_tags:
            deadline_filtered = [
                item
                for item in candidate_pool
                if not _has_window_technical_self_activity(item[1])
            ]
            if deadline_filtered:
                candidate_pool = deadline_filtered
        no_question_filtered = [item for item in candidate_pool if "？" not in item[1] and "?" not in item[1]]
        if no_question_filtered:
            candidate_pool = no_question_filtered
    candidate_pool.sort(key=lambda item: item[0], reverse=True)
    return candidate_pool[0][1]
