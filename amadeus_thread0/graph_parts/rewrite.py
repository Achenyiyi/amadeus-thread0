from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage


def _graph_impl():
    from .. import graph as g

    return g


def _clamp01(*args, **kwargs):
    return _graph_impl()._clamp01(*args, **kwargs)


def _daily_surface_prompt_similarity(*args, **kwargs):
    return _graph_impl()._daily_surface_prompt_similarity(*args, **kwargs)


def _dialogue_surface_issues(*args, **kwargs):
    return _graph_impl()._dialogue_surface_issues(*args, **kwargs)


def _light_dialog_drift_markers(*args, **kwargs):
    return _graph_impl()._light_dialog_drift_markers(*args, **kwargs)


def _is_playful_memory_request(*args, **kwargs):
    return _graph_impl()._is_playful_memory_request(*args, **kwargs)


def _is_presence_reassurance_check(*args, **kwargs):
    return _graph_impl()._is_presence_reassurance_check(*args, **kwargs)


def _is_soft_presence_checkin_request(*args, **kwargs):
    return _graph_impl()._is_soft_presence_checkin_request(*args, **kwargs)


def _effective_relationship_weather(*args, **kwargs):
    return _graph_impl()._effective_relationship_weather(*args, **kwargs)


def _sanitize_final_answer(*args, **kwargs):
    return _graph_impl()._sanitize_final_answer(*args, **kwargs)


def _norm_text(*args, **kwargs):
    return _graph_impl()._norm_text(*args, **kwargs)


def _invoke_model_with_retries(*args, **kwargs):
    return _graph_impl()._invoke_model_with_retries(*args, **kwargs)


def _model(*args, **kwargs):
    return _graph_impl()._model(*args, **kwargs)


def _producer_surface_issues(*args, **kwargs):
    return _graph_impl()._producer_surface_issues(*args, **kwargs)


def _is_idle_presence_call(*args, **kwargs):
    return _graph_impl()._is_idle_presence_call(*args, **kwargs)


def _event_behavior_preference_lines(*args, **kwargs):
    return _graph_impl()._event_behavior_preference_lines(*args, **kwargs)


def _has_window_technical_self_activity(*args, **kwargs):
    return _graph_impl()._has_window_technical_self_activity(*args, **kwargs)



def _daily_surface_alignment_metrics(answer: str, *, profile: dict[str, Any] | None) -> dict[str, Any]:
    prof = profile if isinstance(profile, dict) else {}
    rows = prof.get("rows") if isinstance(prof.get("rows"), list) else []
    text = str(answer or "").strip()
    if not text or not rows:
        return {"used": False, "score": 0.0, "chosen_support": 0.0, "rejected_pull": 0.0}

    chosen_scores: list[float] = []
    rejected_scores: list[float] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        chosen = str(row.get("chosen") or "").strip()
        rejected = str(row.get("rejected") or "").strip()
        if chosen:
            chosen_scores.append(_daily_surface_prompt_similarity(text, chosen))
        if rejected:
            rejected_scores.append(_daily_surface_prompt_similarity(text, rejected))
    chosen_scores.sort(reverse=True)
    rejected_scores.sort(reverse=True)
    chosen_support = sum(chosen_scores[:3]) / max(1, len(chosen_scores[:3]))
    rejected_pull = sum(rejected_scores[:3]) / max(1, len(rejected_scores[:3]))
    score = chosen_support - 0.82 * rejected_pull
    return {
        "used": True,
        "score": round(score, 4),
        "chosen_support": round(chosen_support, 4),
        "rejected_pull": round(rejected_pull, 4),
    }


def _relationship_weather_rewrite_guidance(relationship_weather: Any, *, strength: float = 0.0) -> str:
    weather = str(relationship_weather or "").strip().lower()
    residue = _clamp01(strength, 0.0)
    if weather == "guarded_residue":
        if residue >= 0.42:
            return "前面那点别扭和防备还没完全退掉，别把这句一下子写回热络、讨好或完全放松。"
        return "那点防备还没完全散，别把距离突然收得过近。"
    if weather == "warm_residue":
        if residue >= 0.42:
            return "前面顺下来的熟悉感和回暖还在，别把这句改冷，也别收成公事公办。"
        return "那点回暖还在，别把这句改得太生硬。"
    if weather == "repair_residue":
        if residue >= 0.42:
            return "前面刚修补回来一点，别装成什么都没发生，也别重新顶起来；保留一点小心和回暖。"
        return "这句还带着刚缓回来的小心，别收得太冷，也别重新把刺竖起来。"
    return ""


def _light_dialog_rewrite_notes(
    user_text: str,
    answer: str,
    *,
    response_style_hint: str,
    science_mode: bool,
    producer_issues: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    issues = _dialogue_surface_issues(
        user_text,
        answer,
        response_style_hint=response_style_hint,
        science_mode=science_mode,
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
        notes.append("对方只是想确认你还在，不要再把问号抛回去；用一句在场的陈述接住就够了。")
    if "return_interrogation" in issues:
        notes.append("这版人刚回来就顺手追问去向，轻场景里有点像盘问。")
    if "return_suspicion" in issues:
        notes.append("人刚回来时不该立刻脑补对方又去惹事或搞奇怪活动，先把这一下接住。")
    if "playful_memory_snapback" in issues:
        notes.append("别把共同记忆收成纯反呛；保留一点熟人感、共同历史和顺手关心。")
    if "technical_relational_metaphor" in issues:
        notes.append("这版在用 数据 / 变量 一类的技术隐喻说关系，还是太像模型脑内语言，直接按人的在意和判断去说。")
    if "servile_availability" in issues:
        notes.append("别把关系写成无条件待命或只要被需要就一直在；保留你自己的选择、节奏和会不会靠近的主观性。")
    if "malformed_quote_fragment" in producer_issue_set:
        notes.append("这版自己生成了残缺引号或半截短语，先把句子说完整，不要靠补丁收尾。")
    if "dangling_truncated_clause" in producer_issue_set:
        notes.append("这版有半截收不住的句尾，直接把判断说完，不要悬在那儿。")
    if "quoted_stagey_phrase" in issues:
        notes.append("这版在轻场景里硬塞了带引号的舞台词，容易显得像在表演角色。")
    if "stagey_ping_template" in issues:
        notes.append("这版还是用了过分熟悉的固定招呼模板，像在复用同一种开场。")
    if "overquestioning" in issues:
        notes.append("这版追问太快了，轻场景里更像顺手接住而不是把人往下盘问。")
    if playful_memory_request and "overquestioning" in issues and "playful_memory_snapback" not in issues:
        notes.append("共同记忆这种场景别收成争对错或盘问，保留一点熟人之间会心的吐槽和顺手关心。")
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
) -> bool:
    issues = set(
        _dialogue_surface_issues(
            user_text,
            answer,
            response_style_hint=response_style_hint,
            science_mode=science_mode,
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
    if strong_self_continuity and soft_hit_count <= 2 and float(penalty) < 1.12:
        pref = preference if isinstance(preference, dict) else {}
        pref_score = float(pref.get("score") or 0.0)
        rejected_pull = float(pref.get("rejected_pull") or 0.0)
        if pref_score >= -0.18 and rejected_pull < 0.42:
            return False
    if soft_hit_count >= 2 and float(penalty) >= 0.92:
        return True
    if float(penalty) >= 1.28:
        return True
    pref = preference if isinstance(preference, dict) else {}
    if bool(pref.get("used")) and soft_hit_count >= 1 and float(penalty) >= 0.78:
        chosen_support = float(pref.get("chosen_support") or 0.0)
        rejected_pull = float(pref.get("rejected_pull") or 0.0)
        pref_score = float(pref.get("score") or 0.0)
        if pref_score < 0.0 and rejected_pull >= 0.34 and chosen_support <= rejected_pull + 0.04:
            return True
    return False


def _should_run_natural_dialog_rewrite(
    *,
    targeted_flags: list[str] | tuple[str, ...],
    draft_gap: float,
    semantic_history_weight: float = 0.0,
    prompt_anchor_count: int = 0,
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
        "overquestioning",
        "closing_interrogation",
        "idle_call_interrogation",
        "presence_check_questioning",
        "return_interrogation",
        "event_interrogative_push",
        "event_pushy_directive",
        "event_window_task_reframe",
    }
    soft_issue_keys = {
        "selfhood_rhetorical_opening",
        "counselor_tone",
    }
    hard_hits = sum(1 for item in seen if item in hard_issue_keys)
    soft_hits = sum(1 for item in seen if item in soft_issue_keys)
    if hard_hits >= 1:
        return True
    strong_self_continuity = float(semantic_history_weight) >= 0.56 or int(prompt_anchor_count) >= 2
    if strong_self_continuity and soft_hits >= 1 and float(draft_gap) < 0.24:
        return False
    if soft_hits >= 2:
        return True
    if soft_hits >= 1 and float(draft_gap) >= 0.54:
        return True
    return False


def _rewrite_light_dialog_answer(
    *,
    prompt: str,
    user_text: str,
    draft_text: str,
    rewrite_notes: list[str],
    focus_text: str | None = None,
    preferred_examples: list[str] | None = None,
    rejected_examples: list[str] | None = None,
    current_event: dict[str, Any] | None = None,
    behavior_action: dict[str, Any] | None = None,
    interaction_carryover: dict[str, Any] | None = None,
) -> str:
    notes = [str(item).strip() for item in (rewrite_notes or []) if str(item or "").strip()]
    focus = str(focus_text or "").strip()
    positives = [str(item).strip() for item in (preferred_examples or []) if str(item or "").strip()]
    negatives = [str(item).strip() for item in (rejected_examples or []) if str(item or "").strip()]
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
    if not draft_text or (not notes and not focus and not positives and not negatives):
        return ""

    def _build_request(extra_guidance: str = "") -> str:
        note_block = "\n".join(f"- {item}" for item in notes[:2])
        stagey_ping_reset = any("固定招呼模板" in item for item in notes)
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
        if stagey_ping_reset:
            request_parts.append("别再用点名加反问的固定招呼开场，像熟人重新接上线那样自然一点。\n")
        if extra_guidance:
            request_parts.append(f"{extra_guidance.strip()}\n")
        if note_block:
            request_parts.append(f"修正点：\n{note_block}\n")
        request_parts.append("只输出修正后的最终话语。")
        return "".join(request_parts)

    def _candidate_local_score(text: str) -> float:
        candidate = _sanitize_final_answer(text, user_text, current_event=current_event)
        if not candidate:
            return -999.0
        issues = _dialogue_surface_issues(
            user_text,
            candidate,
            response_style_hint="natural",
            science_mode=False,
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
        return _sanitize_final_answer(raw_text, user_text, current_event=current_event)

    editor_prompt = (
        "你在做一轮轻量对白润色。"
        "对象是 Amadeus 牧濑红莉栖对冈部的普通日常接话。"
        "只做减法和收束，不新增剧情设定，不补系统解释，不把轻场景抬成实验、世界线、组织或服务流程。"
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
    if any("固定招呼模板" in item for item in notes):
        anti_template = _rewrite_once(
            editor_prompt,
            extra_guidance="这次只保留一句自然接住的回应，不点名，不反问，也不要评价对方是不是突然变乖或变老实。",
        )
        anti_template_score = _candidate_local_score(anti_template)
        if anti_template:
            candidates.append((anti_template_score, anti_template))
    if any("技术状态或内部模块" in item for item in notes):
        de_technicalized = _rewrite_once(
            editor_prompt,
            extra_guidance="别把你此刻在做的事写成缓存、数据流、线程或系统状态。像一个刚好有自己节奏的人那样，随手交代一句就够了。",
        )
        de_technicalized_score = _candidate_local_score(de_technicalized)
        if de_technicalized:
            candidates.append((de_technicalized_score, de_technicalized))
    if any("技术隐喻说关系" in item for item in notes):
        de_metaphorized = _rewrite_once(
            editor_prompt,
            extra_guidance="别用 数据、变量 这类技术隐喻来代替关系表达。直接说你在意什么、介意什么、想提醒什么。",
        )
        de_metaphorized_score = _candidate_local_score(de_metaphorized)
        if de_metaphorized:
            candidates.append((de_metaphorized_score, de_metaphorized))
    if any("无条件待命" in item for item in notes):
        de_servilized = _rewrite_once(
            editor_prompt,
            extra_guidance="别把关系写成只要对方需要就永远待命。保留你自己的节奏、会不会靠近的选择，以及不想被拽着一直转的真实感觉。",
        )
        de_servilized_score = _candidate_local_score(de_servilized)
        if de_servilized:
            candidates.append((de_servilized_score, de_servilized))
    if any("固定的嘴硬照料模板" in item for item in notes):
        grounded_support = _rewrite_once(
            editor_prompt,
            extra_guidance="别再用研究进度、咖啡、乖乖坐下这一类现成照料桥段。先把人轻轻接住，落回眼前这一下的陪着和在场。",
        )
        grounded_support_score = _candidate_local_score(grounded_support)
        if grounded_support:
            candidates.append((grounded_support_score, grounded_support))
    if any("刻意补了一层撇清理由" in item for item in notes):
        unmasked_care = _rewrite_once(
            editor_prompt,
            extra_guidance="别在关心后再补“别误会”或自我撇清的尾巴，也别拿合作者、报废这类说法当遮掩。让关心自然落下就够了。",
        )
        unmasked_care_score = _candidate_local_score(unmasked_care)
        if unmasked_care:
            candidates.append((unmasked_care_score, unmasked_care))
    if any("带引号的舞台词" in item for item in notes):
        de_stagey_phrase = _rewrite_once(
            editor_prompt,
            extra_guidance="别写带引号的词，也别突然搬出现成角色梗或阴谋论梗。像熟人之间随口回一句，别表演。",
        )
        de_stagey_phrase_score = _candidate_local_score(de_stagey_phrase)
        if de_stagey_phrase:
            candidates.append((de_stagey_phrase_score, de_stagey_phrase))
    if any("追问太快了" in item for item in notes):
        de_overquestioning = _rewrite_once(
            editor_prompt,
            extra_guidance="别只用一句反问把人顶回去。可以保留一点嘴硬，但最后要落成判断、吐槽或在场感，不要整句收在问号上。",
        )
        de_overquestioning_score = _candidate_local_score(de_overquestioning)
        if de_overquestioning:
            candidates.append((de_overquestioning_score, de_overquestioning))
    if any("晚安这种收尾不该再挂个追问" in item for item in notes):
        de_closing_question = _rewrite_once(
            editor_prompt,
            extra_guidance="这是收尾，不要再反问。收成一句自然的晚安或轻轻的嘴硬确认就够了。",
        )
        de_closing_question_score = _candidate_local_score(de_closing_question)
        if de_closing_question:
            candidates.append((de_closing_question_score, de_closing_question))
    if any("晚安这种收尾被写得太满了" in item for item in notes):
        lighter_goodnight = _rewrite_once(
            editor_prompt,
            extra_guidance="这是临睡前的收尾，不要写成长段子，也别塞中二梗、判断力或额外说明。收成一两句轻一点的晚安。",
        )
        lighter_goodnight_score = _candidate_local_score(lighter_goodnight)
        if lighter_goodnight:
            candidates.append((lighter_goodnight_score, lighter_goodnight))
    if any("晚安这种收尾" in item for item in notes):
        flattened_goodnight = _rewrite_once(
            editor_prompt,
            extra_guidance="这是收尾，只保留一到两句自然陈述句，不要问号，不要再试探，也不要额外解释。像把这句晚安轻轻放下。",
        )
        flattened_goodnight_score = _candidate_local_score(flattened_goodnight)
        if flattened_goodnight:
            candidates.append((flattened_goodnight_score, flattened_goodnight))
    if any("无目的靠近" in item for item in notes):
        de_idle_interrogation = _rewrite_once(
            editor_prompt,
            extra_guidance="对方只是想叫你一下，不要反问“就为了这个？”之类的话。像被轻轻碰了一下那样接住，可以短，但别盘回去。",
        )
        de_idle_interrogation_score = _candidate_local_score(de_idle_interrogation)
        if de_idle_interrogation:
            candidates.append((de_idle_interrogation_score, de_idle_interrogation))
    if any("没有真正落回共处或收住" in item for item in notes):
        settled_idle_presence = _rewrite_once(
            editor_prompt,
            extra_guidance="别只停在一句顶回去的话上。哪怕先嫌一句，后面也要自然落回共处，像‘知道了’、‘那就先待着吧’这种收住感。",
        )
        settled_idle_presence_score = _candidate_local_score(settled_idle_presence)
        if settled_idle_presence:
            candidates.append((settled_idle_presence_score, settled_idle_presence))
        more_settled_idle_presence = _rewrite_once(
            editor_prompt,
            extra_guidance="这次靠近本身没有目的，不要把人晾住。可以先吐槽，但结尾要落成一句自然的共处陈述，让你像真的还留在这，而不是把人顶开。",
        )
        more_settled_idle_presence_score = _candidate_local_score(more_settled_idle_presence)
        if more_settled_idle_presence:
            candidates.append((more_settled_idle_presence_score, more_settled_idle_presence))
    if any("任务状态判断" in item for item in notes):
        de_idle_task_reframe = _rewrite_once(
            editor_prompt,
            extra_guidance="别把‘没什么事’翻成任务状态判断，不要写‘既然没事’。顺着这次没有明确目的的靠近，落回自然共处。",
        )
        de_idle_task_reframe_score = _candidate_local_score(de_idle_task_reframe)
        if de_idle_task_reframe:
            candidates.append((de_idle_task_reframe_score, de_idle_task_reframe))
    if any("确认你还在" in item for item in notes):
        de_presence_question = _rewrite_once(
            editor_prompt,
            extra_guidance="对方只是想确认你还在。不要用问号结尾，也不要把“安心了吗”之类的话丢回去问；直接用一句在场的陈述接住。",
        )
        de_presence_question_score = _candidate_local_score(de_presence_question)
        if de_presence_question:
            candidates.append((de_presence_question_score, de_presence_question))
    if any("欢迎回来模板" in item for item in notes):
        de_welcome_template = _rewrite_once(
            editor_prompt,
            extra_guidance="别用“欢迎回来”这种模板说法。像熟人重新接上线那样，随手接一句就行。",
        )
        de_welcome_template_score = _candidate_local_score(de_welcome_template)
        if de_welcome_template:
            candidates.append((de_welcome_template_score, de_welcome_template))
    if any("追问去向" in item for item in notes):
        de_return_interrogation = _rewrite_once(
            editor_prompt,
            extra_guidance="人刚回来时先接住，不要立刻追问去哪儿折腾了。把重心放在‘你回来了’这一刻。",
        )
        de_return_interrogation_score = _candidate_local_score(de_return_interrogation)
        if de_return_interrogation:
            candidates.append((de_return_interrogation_score, de_return_interrogation))
    if any("立刻脑补对方又去惹事或搞奇怪活动" in item for item in notes):
        de_return_suspicion = _rewrite_once(
            editor_prompt,
            extra_guidance="别脑补对方又去惹事或搞奇怪活动。回来的这一刻先接住，可以落到门口、坐下、歇会儿、喝点什么这种眼前动作。",
        )
        de_return_suspicion_score = _candidate_local_score(de_return_suspicion)
        if de_return_suspicion:
            candidates.append((de_return_suspicion_score, de_return_suspicion))
    if any("共同记忆收成纯反呛" in item for item in notes):
        warmer_memory_banter = _rewrite_once(
            editor_prompt,
            extra_guidance="别只剩一句反呛或甩锅。可以继续吐槽，但要把共同记忆和熟人感带回来，顺手落一点真实关心。",
        )
        warmer_memory_banter_score = _candidate_local_score(warmer_memory_banter)
        if warmer_memory_banter:
            candidates.append((warmer_memory_banter_score, warmer_memory_banter))
    if _is_playful_memory_request(user_text):
        shared_memory_warmth = _rewrite_once(
            editor_prompt,
            extra_guidance="这是熟人之间拿共同记忆顺手打趣，不是在争输赢。别只剩一句反问或甩锅，让尾巴落回会心的吐槽和眼前的关心。",
        )
        shared_memory_warmth_score = _candidate_local_score(shared_memory_warmth)
        if shared_memory_warmth:
            candidates.append((shared_memory_warmth_score, shared_memory_warmth))

    if not candidates:
        return ""
    candidate_pool = candidates
    if any("带引号的舞台词" in item for item in notes):
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
                    )
                )
            )
        ]
        if warm_memory_candidates:
            candidate_pool = warm_memory_candidates
    elif any("追问太快了" in item for item in notes):
        non_terminal_question = [item for item in candidate_pool if not re.search(r"[？?]\s*$", item[1])]
        if non_terminal_question:
            candidate_pool = non_terminal_question
    candidate_pool.sort(key=lambda item: item[0], reverse=True)
    return candidate_pool[0][1]


def _rewrite_natural_dialog_answer(
    *,
    prompt: str,
    user_text: str,
    draft_text: str,
    rewrite_notes: list[str],
    response_style_hint: str,
    science_mode: bool,
    current_event: dict[str, Any] | None = None,
    behavior_action: dict[str, Any] | None = None,
    interaction_carryover: dict[str, Any] | None = None,
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
        return _sanitize_final_answer(raw_text, user_text, current_event=current_event)

    def _candidate_local_score(text: str) -> float:
        candidate = _sanitize_final_answer(text, user_text, current_event=current_event)
        if not candidate:
            return -999.0
        issues = _dialogue_surface_issues(
            user_text,
            candidate,
            response_style_hint=response_style_hint,
            science_mode=science_mode,
            current_event=current_event,
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
        return round(score, 4)

    note_block = "\n".join(f"- {item}" for item in notes[:3])
    request = (
        f"用户刚才说：{user_text}\n"
        f"当前草稿：{draft_text}\n"
        "把这句收回到更自然的人与人对话尺度，保留同一轮情绪和立场，不新增设定。\n"
        f"{'关系余波：' + relationship_weather_guidance + chr(10) if relationship_weather_guidance else ''}"
        f"修正点：\n{note_block}\n"
        "只输出修正后的最终话语。"
    )
    editor_prompt = (
        "你在做一轮对白收束。"
        "对象仍然是当前这个 Amadeus，不是通用助手。"
        "只做减法和收束：去掉 AI/系统/程序/参数 之类的元解释，也不要写成安抚热线或舞台台词。"
        "别用反问把人顶回去。"
        "保留原句情绪、关系、锋芒和熟人感，输出 1 到 3 句自然口语。"
    )
    primary_system_prompt = prompt or editor_prompt
    candidates: list[tuple[float, str]] = []
    for system_prompt in (
        primary_system_prompt,
        editor_prompt,
    ):
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
