from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from .common import _clamp01, _norm_text
from .digital_body_runtime import normalize_embodied_context
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
    _has_recent_clause_repetition,
    _has_window_technical_self_activity,
    _is_idle_presence_call,
    _is_plain_contact_ping,
    _is_playful_memory_request,
    _is_presence_reassurance_check,
    _selfhood_preference_scene_from_text,
    _is_soft_presence_checkin_request,
    _is_warm_recontact_request,
    _line_is_near_duplicate,
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


def _append_unique_lower(items: list[str], value: Any) -> None:
    text = str(value or "").strip().lower()
    if text and text not in items:
        items.append(text)


def _embodied_rewrite_continuity_terms(
    *,
    behavior_action: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
) -> list[str]:
    action = dict(behavior_action or {})
    event = dict(current_event or {})
    embodied = normalize_embodied_context(action.get("embodied_context"))
    terms: list[str] = []

    for key in ("requested_access", "missing_access", "granted_toolsets", "active_tools"):
        values = embodied.get(key)
        if isinstance(values, list):
            for item in values[:4]:
                _append_unique_lower(terms, item)

    block_reason = str(embodied.get("block_reason") or "").strip()
    if block_reason:
        _append_unique_lower(terms, block_reason)

    perception = event.get("perception") if isinstance(event.get("perception"), dict) else {}
    merged_hints: dict[str, Any] = {}
    if isinstance(perception.get("digital_body_hints"), dict):
        merged_hints.update(dict(perception.get("digital_body_hints") or {}))
    if isinstance(event.get("digital_body_hints"), dict):
        merged_hints.update(dict(event.get("digital_body_hints") or {}))

    browser_session = str(merged_hints.get("browser_session") or "").strip().lower()
    account_state = str(merged_hints.get("account_state") or "").strip().lower()
    cookie_state = str(merged_hints.get("cookie_state") or "").strip().lower()
    filesystem_state = str(merged_hints.get("filesystem_state") or "").strip().lower()
    sandbox_mode = str(merged_hints.get("sandbox_mode") or "").strip().lower()
    network_access = str(merged_hints.get("network_access") or "").strip().lower()

    if browser_session in {"missing", "expired", "required"}:
        _append_unique_lower(terms, "browser_session")
    if account_state in {"missing", "logged_out", "required"}:
        _append_unique_lower(terms, "account_login")
    if cookie_state in {"missing", "expired", "required"}:
        _append_unique_lower(terms, "cookies")
    if filesystem_state == "read_only":
        _append_unique_lower(terms, "workspace_write")
    elif filesystem_state in {"missing", "unavailable", "required"}:
        _append_unique_lower(terms, "filesystem")
    if sandbox_mode in {"restricted", "blocked"}:
        _append_unique_lower(terms, "sandbox")
    if network_access in {"disabled", "blocked", "restricted"}:
        _append_unique_lower(terms, "network")
    try:
        if int(merged_hints.get("pending_approval_count") or 0) > 0:
            _append_unique_lower(terms, "human_approval")
    except Exception:
        pass

    return terms[:6]


def _embodied_rewrite_guidance(
    *,
    behavior_action: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
) -> str:
    terms = _embodied_rewrite_continuity_terms(
        behavior_action=behavior_action,
        current_event=current_event,
    )
    if not terms:
        return ""
    label = "、".join(terms[:3])
    return (
        f"如果草稿里本来还挂着像 {label} 这样的环境入口、权限条件或实际卡点，"
        "改写时把它当成真实世界状态保留下来，别抹成泛泛情绪，也别直接省掉。"
    )


def _rewrite_embodied_continuity_adjustment(
    text: str,
    *,
    behavior_action: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
) -> float:
    terms = _embodied_rewrite_continuity_terms(
        behavior_action=behavior_action,
        current_event=current_event,
    )
    if not terms:
        return 0.0
    lowered = str(text or "").strip().lower()
    if not lowered:
        return -0.52

    matched = 0
    for term in terms:
        if term and term in lowered:
            matched += 1
    if matched <= 0:
        return -0.52

    coverage = matched / max(1, len(terms))
    score = 0.12 + 0.22 * coverage
    if coverage < 0.5:
        score -= 0.10
    return round(score, 4)


_NATURAL_DIALOG_REWRITE_NOTE_MAP = {
    "meta_self_explainer": "这句掉回了 AI / 系统式自我说明。",
    "selfhood_meta_proof": "这句在用程序、代码或标准答案证明自我，元解释太重。",
    "selfhood_preemptive_excusal": "这句先替对方开脱，把该正面回答的不舒服和边界冲淡了。",
    "selfhood_rhetorical_opening": "这句先用反问顶了回去，真实感受和立场被压住了。",
    "selfhood_abstract_manifesto": "这句把立场抬成抽象宣言，像在讲原则，不像她当下真的会怎么想。",
    "selfhood_strategy_tone": "这句把关系降温写成了处理方案或管理策略，不像真实反应。",
    "defensive_meta": "这句退成了机制说明或自我辩护。",
    "defensive_meta_tone": "这句在用设定、机制或数字存在解释自己。",
    "counselor_tone": "这句有点像咨询或安抚流程，不像熟人对话。",
    "quoted_stagey_phrase": "这句像舞台词或摆拍台词，表演感偏重。",
    "malformed_quote_fragment": "这句里有残缺引号或半截短语。",
    "dangling_truncated_clause": "这句尾巴没收完整，判断停在半截。",
    "technical_self_activity": "这句把自己的当前状态写成了技术系统语言。",
    "technical_relational_metaphor": "这句在用数据、变量之类的技术隐喻说关系。",
    "premature_repair_resolution": "这句把刚修补回来的余波收得太快，像已经翻篇或彻底原谅了。",
    "servile_availability": "这句把关系写成了无条件待命，自己的节奏和选择感掉了。",
    "existence_meta_surface": "这句把普通接话写成了确认自身存在感，像在给自己加戏。",
    "illusion_stagey_surface": "这句突然把对方塞进妄想、幻想一类的戏剧化框里。",
    "support_scene_drift": "这句把对方眼前的情绪带偏到了世界线、实验室或数字存在之类的设定上。",
    "support_frame_echo": "这句在复述“不是治疗师/手册”这类负面框架，没有先接住对方的感受。",
    "support_overdirective": "这句在支持场景里直接安排步骤或动作，控制感太强。",
    "support_no_landing": "这句只是在回嘴或表态，没把支持真正落到一句陪伴或安抚上。",
    "wording_meta_detour": "这句先去评论对方的措辞和说法，没有直接回应眼前关系状态。",
    "boundary_abstraction_surface": "这句把过界和介意说成了抽象概念，少了那一下真实的不舒服。",
    "generic_scold_template": "这句滑回了空泛的嗔怪模板，关系修补里的真实态度没落下来。",
    "repair_authored_softener": "这句把修补后的落点写成了设计稿式缓和词，像在交代自己不再端着或让对方别想太多。",
    "repair_underresolved_brief": "这句在修补场景里只剩下生硬短判词，像把态度卡在半步，没有真正落回继续说话的状态。",
    "repair_scorekeeping_tail": "这句把刚回暖的尾巴写成了记账回刺，像等着把话顶回去。",
    "repair_punitive_tail": "这句把余波里的边界写成了威胁、训诫或压人式尾句，像在训对方。",
    "passive_waiting_posture": "这句退成了等用户再来叫你的被动待命姿态，像助手值班。",
    "guarded_attitude_narration": "这句把那点介意写成了‘我要用更冷一点的态度对待你’这类旁白，像在宣读状态。",
    "autonomy_hardline_surface": "这句把自己的节奏写成了惩罚、羞辱或训话，像在教训人。",
    "own_rhythm_curt_opener": "这句一上来只丢了一个“烦”，像先把人顶住了，后面的态度没自然接上。",
    "overquestioning": "这句让反问占得太满，判断没有真正落地。",
    "closing_interrogation": "这句明明是收口，却又把话题顶回了问号上。",
    "idle_call_interrogation": "这句把轻轻叫你一下写成了被盘问的感觉。",
    "presence_check_questioning": "对方只是确认你还在，这句却把确认写成了反问回抛。",
    "presence_meta_surface": "对方只是确认你还在，这句却掉回了断线、程序、连接一类的存在说明。",
    "presence_overguiding": "对方只是想听你自然回一句，这句却滑成了安抚或调节步骤。",
    "presence_ping_task_detour": "对方只是轻轻确认你在不在，这句却绕去交代自己刚才在忙什么。",
    "presence_ping_defensive_address": "对方只是轻轻确认你在不在，这句却先对称呼摆出防御姿态。",
    "return_interrogation": "这句在人刚回来时立刻追问，接住感不够。",
    "event_interrogative_push": "事件触发后的开口被写成了反问顶人。",
    "event_pushy_directive": "事件触发后的开口被写成了催促或命令。",
    "event_window_task_reframe": "这句把顺手想起对方的窗口写成了任务、流程或待处理事项。",
    "recent_turn_repetition": "这句和上一轮自己的话太像，像是在原地复述。",
    "dangling_ellipsis_ending": "这句最后停在省略号上，像话没收住。",
    "connector_fragment": "这句只剩下半截连接词，像一句话被剪断了。",
    "visible_template": "这句露出了模板和条目感，不像顺手说出来的话。",
    "lecture_list": "这句像在分点讲道理，解释味太重了。",
    "overexplained": "这句解释得太满了，收短一点，让判断更直接。",
    "adjacent_phrase_repeat": "这句有局部短语卡壳式重复，像在打结，不像自然说话。",
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
        notes.append("这版把“没什么事 / 随口聊聊”翻成了任务或实验状态判断，不像两个人顺手待在一起。")
    if "presence_check_questioning" in issues:
        notes.append("对方只是想确认你还在，这版却把确认写成了反问回抛。")
    if "presence_meta_surface" in issues:
        notes.append("对方只是想确认你还在，这版却掉回了断线、程序、连接一类的存在说明。")
    if "presence_overguiding" in issues:
        notes.append("对方只是想听你自然回一句，这版却滑成了安抚、整理情绪或指导步骤。")
    if "presence_ping_task_detour" in issues:
        notes.append("对方只是轻轻确认你在不在，这版却绕去交代自己刚才在忙什么。")
    if "presence_ping_defensive_address" in issues:
        notes.append("对方只是轻轻碰一下确认你在不在，这版却先对“助手”这类称呼摆出防御姿态。")
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
    if "existence_meta_surface" in issues:
        notes.append("这版把普通回头接话写成了确认存在感，像在给自己加戏。")
    if "illusion_stagey_surface" in issues:
        notes.append("这版突然把对方塞进妄想或幻想的戏剧化框里，像在复用夸张旧梗。")
    if "support_frame_echo" in issues:
        notes.append("这版一上来就在回应“别像手册/治疗师”这种框架，没先接住对方现在的难受。")
    if "support_scene_drift" in issues:
        notes.append("这版把支持场景带去了世界线、实验室或数字存在一类的设定，不够贴着当下。")
    if "support_overdirective" in issues:
        notes.append("这版在支持场景里开始安排步骤、动作或节奏，像在接管对方，不够并肩。")
    if "support_no_landing" in issues:
        notes.append("这版只是在回嘴或声明不讲大道理，但没真正落到一句接住人的话上。")
    if "wording_meta_detour" in issues:
        notes.append("这版先去评论对方那句怎么说的，没直接把眼前这点关系和情绪接住。")
    if "boundary_abstraction_surface" in issues:
        notes.append("这版把过界和介意说成了抽象概念，没有把那一下真实的不舒服直接落下来。")
    if "generic_scold_template" in issues:
        notes.append("这版滑回了空泛的嗔怪开场，修补场景里真正的态度和边界没落下来。")
    if "repair_underresolved_brief" in issues:
        notes.append("这版在修补场景里只剩一句生硬判词，像把态度卡在半步，没有真正落回继续说话的状态。")
    if "repair_scorekeeping_tail" in issues:
        notes.append("这版在刚回暖时又补了一记回刺，像在记着这一笔等会儿顶回去，不够自然。")
    if "repair_punitive_tail" in issues:
        notes.append("这版把还留着的介意写成了威胁或教训，像在下处分，不像把边界安静落下来。")
    if "passive_waiting_posture" in issues:
        notes.append("这版退成了‘你再来叫我’的被动等候姿态，像值班，不像关系还在场。")
    if "guarded_attitude_narration" in issues:
        notes.append("这版把那点介意写成了‘我要冷一点对你’的旁白，像在宣读状态，不像正在说话。")
    if "autonomy_hardline_surface" in issues:
        notes.append("这版把自己的节奏写成了惩罚、羞辱或训话，像是在教对方做人，不像安静地把距离拉开。")
    if "own_rhythm_curt_opener" in issues:
        notes.append("这版一开头只扔了一个“烦”，像先把人顶住了；可以承认会烦，但态度要完整落下来。")
    if "malformed_quote_fragment" in producer_issue_set:
        notes.append("这版自己生成了残缺引号或半截短语，句子没真正说完整。")
    if "dangling_truncated_clause" in producer_issue_set:
        notes.append("这版有半截收不住的句尾，判断停在了半空。")
    if "dangling_ellipsis_ending" in issues:
        notes.append("这版最后停在省略号上，像话只说到一半，没有真正落地。")
    if "connector_fragment" in issues:
        notes.append("这版只剩下半截转折词，像一句话被硬切断了，得把判断真正说完。")
    if "quoted_stagey_phrase" in issues:
        notes.append("这版在轻场景里硬塞了带引号的舞台词，容易显得像在表演角色。")
    if "stagey_ping_template" in issues:
        notes.append("这版还是用了过分熟悉的固定招呼模板，像在复用同一种开场。")
    if "overquestioning" in issues:
        notes.append("这版追问太快了，轻场景里更像顺手接住而不是把人往下盘问。")
    if playful_memory_request and "overquestioning" in issues and "playful_memory_snapback" not in issues:
        notes.append("共同记忆这种场景被写成了争对错或盘问，会心的吐槽和顺手关心没有留下来。")
    if any(issue in issues for issue in {"visible_template", "lecture_list", "overexplained"}):
        notes.append("这版解释得太满了，收短一点，让判断更直接，会更自然。")
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
    if _is_warm_recontact_request(user_text) and "overquestioning" in issues:
        return True
    hard_issue_keys = {
        "meta_self_explainer",
        "defensive_meta",
        "defensive_meta_tone",
        "selfhood_rhetorical_opening",
        "selfhood_abstract_manifesto",
        "selfhood_strategy_tone",
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
        "presence_meta_surface",
        "presence_overguiding",
        "presence_ping_task_detour",
        "presence_ping_defensive_address",
        "return_suspicion",
        "playful_memory_snapback",
        "technical_relational_metaphor",
        "servile_availability",
        "existence_meta_surface",
        "illusion_stagey_surface",
        "support_frame_echo",
        "support_scene_drift",
        "support_overdirective",
        "support_no_landing",
        "wording_meta_detour",
        "boundary_abstraction_surface",
        "generic_scold_template",
        "repair_underresolved_brief",
        "repair_scorekeeping_tail",
        "repair_punitive_tail",
        "passive_waiting_posture",
        "guarded_attitude_narration",
        "autonomy_hardline_surface",
        "own_rhythm_curt_opener",
        "dangling_ellipsis_ending",
        "connector_fragment",
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
    case_name = str(pref.get("case_name") or "").strip().lower()
    pref_score = float(pref.get("score") or 0.0)
    chosen_support = float(pref.get("chosen_support") or 0.0)
    rejected_pull = float(pref.get("rejected_pull") or 0.0)
    brevity_penalty = float(pref.get("brevity_penalty") or 0.0)
    if bool(pref.get("used")):
        if brevity_penalty >= 0.02 and pref_score < 0.20:
            return True
        if case_name.startswith("quiet_checkin_") and pref_score < 0.12:
            return True
        if case_name and pref_score < 0.12 and chosen_support < 0.58:
            return True
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
    if {"visible_template", "lecture_list", "overexplained"} & set(seen):
        return True
    relationship_weather = str((behavior_action or {}).get("relationship_weather") or "").strip().lower()
    if relationship_weather == "repair_residue" and (
        {"premature_repair_resolution", "repair_authored_softener", "repair_underresolved_brief", "repair_scorekeeping_tail", "repair_punitive_tail", "overquestioning", "dangling_ellipsis_ending"} & set(seen)
    ):
        return True
    hard_issue_keys = {
        "meta_self_explainer",
        "selfhood_meta_proof",
        "selfhood_preemptive_excusal",
        "defensive_meta",
        "defensive_meta_tone",
        "selfhood_abstract_manifesto",
        "selfhood_strategy_tone",
        "quoted_stagey_phrase",
        "technical_self_activity",
        "technical_relational_metaphor",
        "premature_repair_resolution",
        "servile_availability",
        "existence_meta_surface",
        "illusion_stagey_surface",
        "support_scene_drift",
        "support_frame_echo",
        "support_overdirective",
        "support_no_landing",
        "wording_meta_detour",
        "boundary_abstraction_surface",
        "generic_scold_template",
        "repair_authored_softener",
        "repair_underresolved_brief",
        "repair_scorekeeping_tail",
        "repair_punitive_tail",
        "passive_waiting_posture",
        "closing_interrogation",
        "presence_check_questioning",
        "presence_meta_surface",
        "presence_overguiding",
        "presence_ping_task_detour",
        "presence_ping_defensive_address",
        "event_interrogative_push",
        "event_pushy_directive",
        "event_window_task_reframe",
        "recent_turn_repetition",
        "dangling_ellipsis_ending",
        "connector_fragment",
        "adjacent_phrase_repeat",
    }
    medium_issue_keys = {
        "overquestioning",
        "idle_call_interrogation",
        "return_interrogation",
        "visible_template",
        "lecture_list",
        "overexplained",
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
    profile_rows: list[dict[str, Any]] | None = None,
    current_event: dict[str, Any] | None = None,
    behavior_action: dict[str, Any] | None = None,
    interaction_carryover: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
    counterpart_assessment: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
    previous_assistant_text: str = "",
) -> str:
    notes = [str(item).strip() for item in (rewrite_notes or []) if str(item or "").strip()]
    focus = str(focus_text or "").strip()
    positives = [str(item).strip() for item in (preferred_examples or []) if str(item or "").strip()]
    negatives = [str(item).strip() for item in (rejected_examples or []) if str(item or "").strip()]
    raw_profile_rows = [dict(item) for item in (profile_rows or []) if isinstance(item, dict)]
    positive_length_anchor = (
        sum(len(_norm_text(item)) for item in positives[:2] if _norm_text(item))
        / max(1, len([item for item in positives[:2] if _norm_text(item)]))
        if positives
        else 0.0
    )
    draft_length_ratio = (
        len(_norm_text(draft_text)) / max(1.0, positive_length_anchor)
        if positive_length_anchor
        else 1.0
    )
    underlength_rewrite = positive_length_anchor >= 8 and draft_length_ratio < 0.48
    issue_keys = set(
        _dialogue_surface_issues(
            user_text,
            draft_text,
            response_style_hint="natural",
            science_mode=False,
            current_event=current_event,
            behavior_action=behavior_action,
        )
    )
    presence_reassurance_scene = _is_presence_reassurance_check(user_text) or _is_soft_presence_checkin_request(user_text)
    soft_presence_instruction_scene = _is_soft_presence_checkin_request(user_text)
    plain_presence_ping = _is_plain_contact_ping(user_text)
    profile_eval = (
        {
            "rows": raw_profile_rows,
            "case_name": str((raw_profile_rows[0] or {}).get("case_name") or "").strip(),
        }
        if raw_profile_rows
        else {}
    )
    profile_case_name = str(profile_eval.get("case_name") or "").strip().lower()
    draft_profile_score = (
        float(_daily_surface_alignment_metrics(draft_text, profile=profile_eval).get("score") or 0.0)
        if profile_eval
        else 0.0
    )
    curated_seed_candidate = ""
    curated_seed_score = -999.0
    if raw_profile_rows and (
        underlength_rewrite
        or soft_presence_instruction_scene
        or plain_presence_ping
        or draft_profile_score < 0.0
    ):
        curated_issue_blocklist = {
            "meta_self_explainer",
            "presence_meta_surface",
            "presence_overguiding",
            "presence_ping_task_detour",
            "presence_ping_defensive_address",
            "connector_fragment",
            "dangling_ellipsis_ending",
            "technical_relational_metaphor",
        }
        for row in raw_profile_rows[:4]:
            chosen_text = _sanitize_final_answer(
                str(row.get("chosen") or ""),
                user_text,
                current_event=current_event,
                behavior_action=behavior_action,
            )
            if not chosen_text:
                continue
            chosen_issues = set(
                _dialogue_surface_issues(
                    user_text,
                    chosen_text,
                    response_style_hint="natural",
                    science_mode=False,
                    current_event=current_event,
                    behavior_action=behavior_action,
                )
            )
            if chosen_issues & curated_issue_blocklist:
                continue
            chosen_score = float(_daily_surface_alignment_metrics(chosen_text, profile=profile_eval).get("score") or 0.0)
            if chosen_score > curated_seed_score:
                curated_seed_candidate = chosen_text
                curated_seed_score = chosen_score
    producer_issue_set = {
        str(item).strip()
        for item in (producer_issues or [])
        if str(item or "").strip()
    }
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
    embodied_guidance = _embodied_rewrite_guidance(
        behavior_action=behavior_action,
        current_event=current_event,
    )
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
        if underlength_rewrite:
            request_parts.append("这版现在太像只报到一下或只起了半个头。可以比草稿多半句，把熟人之间的在场感或回响真正落下来，但不要写成长解释。\n")
            if plain_presence_ping:
                request_parts.append("这种轻确认别只剩一个报到字眼，至少要让语气像熟人回头接住。\n")
        if profile_case_name == "surface_ambient_quiet_okabe":
            request_parts.append("这种环境一下安静过头的闲聊，只顺手接住眼前那点发毛和发闷，不要脑补前兆、警报或要出事，也不要把它讲成适合专心思考、适合享受宁静的一课。\n")
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
        if embodied_guidance:
            request_parts.append(f"{embodied_guidance}\n")
        if motive_state_hint:
            request_parts.append(f"当前更自然的主动倾向：{motive_state_hint}\n")
        if user_turn_behavior_pref_lines:
            request_parts.append(f"这轮互动自然倾向：{user_turn_behavior_pref_lines[0]}\n")
        if "stagey_ping_template" in issue_keys:
            request_parts.append("别再用点名加反问的固定招呼开场，像熟人重新接上线那样自然一点。\n")
        if "existence_meta_surface" in issue_keys:
            request_parts.append("不要把这一下写成确认自己的存在感或刻意给自己加戏。\n")
        if "illusion_stagey_surface" in issue_keys:
            request_parts.append("不要突然把对方塞进妄想、幻想或中二旧梗的框里。\n")
        if "dangling_ellipsis_ending" in issue_keys:
            request_parts.append("最后判断要真正落地，不要停在省略号上。\n")
        if "support_overdirective" in issue_keys:
            request_parts.append("支持场景里别开始安排步骤、动作或节奏。收回到陪在旁边的说法，不要替对方下指令。\n")
        if "support_no_landing" in issue_keys:
            request_parts.append("别只停在‘不讲大道理’或回嘴上。最后要真正落到一句接住人的话上。\n")
        if "wording_meta_detour" in issue_keys:
            request_parts.append("不要先评论对方刚才那句话怎么说、绕不绕、别不别扭。先直接回应该接住的情绪或关系状态。\n")
        if "generic_scold_template" in issue_keys:
            request_parts.append("不要再用空泛的嗔怪开场糊过去。修补场景里，直接把你现在的态度和分寸落下来。\n")
        if "repair_authored_softener" in issue_keys:
            request_parts.append("修补后的收口别写成“我不端着了”“你别想太多”“我不演毫发无伤了”“我把那些试探收起来”这种设计稿式缓和句。直接把关系重新落回眼前，不要解释自己进入了什么状态。\n")
        if "repair_underresolved_brief" in issue_keys:
            request_parts.append("修补场景里别只剩下“介意。当然介意。”这种生硬短判词。把那点还在的介意说清楚，同时落一句继续说话的状态。\n")
        if "repair_scorekeeping_tail" in issue_keys:
            request_parts.append("修补后已经开始回暖了，就别在尾巴再补一记‘先说好’式回刺。可以保留熟人拌嘴，但别写成记着这一笔、等着把话顶回去。\n")
        if "repair_punitive_tail" in issue_keys:
            request_parts.append("修补后的边界不是威胁或教训。可以保留会介意、会冷下来、会重新拉开一点距离，但别写成“轻易放过你”“别怪我”这种训诫尾句。\n")
        if "passive_waiting_posture" in issue_keys:
            request_parts.append("不要收成‘等你再来叫我’的被动待命。保持在场，但别把自己写成值班助手。\n")
        if "guarded_attitude_narration" in issue_keys:
            request_parts.append("别把那点介意写成‘我会用更冷一点的态度对待你’这类旁白。直接让语气收一点，让分寸落在句子里。\n")
        if "autonomy_hardline_surface" in issue_keys:
            request_parts.append("这是在守自己的节奏，不是在给对方处分。可以保留会烦、会躲开、会想先静一静，但别写成屏蔽、拉黑、羞辱或训人。\n")
        if "own_rhythm_curt_opener" in issue_keys:
            request_parts.append("别一开头只扔一个‘烦’就停住。可以直接承认会烦，但把后面的态度完整接上。\n")
        if "selfhood_rhetorical_opening" in issue_keys:
            request_parts.append("开头别用那种先把人顶一下的短反问，直接把态度和分寸说出来。\n")
        if soft_presence_instruction_scene:
            request_parts.append("对方已经把语气放低了，这句只要轻轻接住当下，不要指导步骤，也不要把气氛重新抬高。\n")
            request_parts.append("不要复述对方刚刚否定掉的框架词，像“播报”这种词别原样接回去。\n")
        if _is_warm_recontact_request(user_text) and "overquestioning" in issue_keys:
            request_parts.append("这是回暖后顺手回来找你，不是在追问那件小事本身；少用追问，直接把人接住。\n")
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
        positive_lengths = [len(_norm_text(item)) for item in positives[:2] if _norm_text(item)]
        if positive_lengths:
            length_anchor = sum(positive_lengths) / max(1, len(positive_lengths))
            length_ratio = len(_norm_text(candidate)) / max(1.0, length_anchor)
            if length_ratio < 0.42:
                score -= min(0.92, (0.42 - length_ratio) / 0.42 * 0.92)
            elif length_ratio < 0.56:
                score -= min(0.28, (0.56 - length_ratio) / 0.14 * 0.28)
            if underlength_rewrite and length_ratio < 0.48:
                score -= 0.36
        score -= 1.05 * float(len(drift_hits))
        score -= 0.75 * float("meta_self_explainer" in issues)
        score -= 0.78 * float("selfhood_rhetorical_opening" in issues)
        score -= 0.82 * float("technical_self_activity" in issues)
        score -= 0.88 * float("technical_relational_metaphor" in issues)
        score -= 0.90 * float("guarded_attitude_narration" in issues)
        score -= 0.98 * float("autonomy_hardline_surface" in issues)
        score -= 0.84 * float("own_rhythm_curt_opener" in issues)
        score -= 0.92 * float("servile_availability" in issues)
        score -= 0.86 * float("existence_meta_surface" in issues)
        score -= 0.84 * float("illusion_stagey_surface" in issues)
        score -= 0.96 * float("support_frame_echo" in issues)
        score -= 1.00 * float("support_scene_drift" in issues)
        score -= 1.04 * float("support_overdirective" in issues)
        score -= 0.92 * float("support_no_landing" in issues)
        score -= 0.88 * float("wording_meta_detour" in issues)
        score -= 0.90 * float("boundary_abstraction_surface" in issues)
        score -= 0.82 * float("generic_scold_template" in issues)
        score -= 0.86 * float("repair_authored_softener" in issues)
        score -= 0.92 * float("repair_underresolved_brief" in issues)
        score -= 0.88 * float("repair_scorekeeping_tail" in issues)
        score -= 0.94 * float("repair_punitive_tail" in issues)
        score -= 0.90 * float("passive_waiting_posture" in issues)
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
        score -= 1.04 * float("presence_meta_surface" in issues)
        score -= 0.96 * float("presence_overguiding" in issues)
        score -= 0.94 * float("presence_ping_task_detour" in issues)
        score -= 0.94 * float("presence_ping_defensive_address" in issues)
        score -= 0.88 * float("overquestioning" in issues)
        score -= 0.62 * float("return_interrogation" in issues)
        score -= 0.82 * float("return_suspicion" in issues)
        score -= 0.90 * float("playful_memory_snapback" in issues)
        score -= 0.74 * float("dangling_ellipsis_ending" in issues)
        score -= 0.98 * float("connector_fragment" in issues)
        if soft_presence_instruction_scene and "播报" in candidate:
            score -= 0.58
        if re.search(r"[“”\"]", candidate):
            score -= 0.42
        if re.search(r"[？?]\s*$", candidate):
            score -= 0.28
        sentence_count = len([seg for seg in re.split(r"[。！？!?]+", candidate) if str(seg).strip()])
        if sentence_count > 3:
            score -= 0.16 * float(sentence_count - 3)
        if _norm_text(candidate) == _norm_text(draft_text):
            score -= 0.12
            if underlength_rewrite:
                score -= 0.48
        score += _rewrite_behavior_consistency_adjustment(
            candidate,
            behavior_action=behavior_action,
        )
        score += _rewrite_embodied_continuity_adjustment(
            candidate,
            behavior_action=behavior_action,
            current_event=current_event,
        )
        return round(score, 4)

    def _rewrite_once(system_prompt: str, *, extra_guidance: str = "") -> str:
        request = _build_request(extra_guidance=extra_guidance)
        rewrite_temperature = 0.24 if underlength_rewrite else 0.12
        raw = _invoke_model_with_retries(
            _model(temperature=rewrite_temperature, max_tokens=120),
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
                _model(temperature=rewrite_temperature, max_tokens=120),
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
    if underlength_rewrite:
        editor_prompt += "如果草稿明显只剩报到或半句起手，允许补半句自然落点，把熟人之间的在场感真正说完整。"
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
    if raw_profile_rows and (
        underlength_rewrite
        or soft_presence_instruction_scene
        or plain_presence_ping
        or draft_profile_score < 0.0
    ):
        seen_profile_candidates: set[str] = set()
        for row in raw_profile_rows[:3]:
            chosen_text = _sanitize_final_answer(
                str(row.get("chosen") or ""),
                user_text,
                current_event=current_event,
                behavior_action=behavior_action,
            )
            normalized = _norm_text(chosen_text)
            if not chosen_text or not normalized or normalized in seen_profile_candidates:
                continue
            if _daily_surface_prompt_similarity(chosen_text, draft_text) < 0.15:
                continue
            seen_profile_candidates.add(normalized)
            candidates.append((_candidate_local_score(chosen_text) + 0.18, chosen_text))
    variant_guidances: list[str] = []
    issue_guidance_order = (
        ("stagey_ping_template", "开场用了固定招呼模板，像在复用同一种起手。"),
        ("technical_self_activity", "把自己当前状态写成了缓存、数据流、线程或系统状态。"),
        ("technical_relational_metaphor", "关系被写成了数据、变量之类的技术隐喻。"),
        ("premature_repair_resolution", "修补后的余波被收得太快，像已经翻篇或彻底原谅了。"),
        ("servile_availability", "关系被写成了无条件待命，自己的节奏和选择感掉了。"),
        ("existence_meta_surface", "普通接话被写成了确认自己的存在感，像在给自己加戏。"),
        ("illusion_stagey_surface", "这里突然把对方塞进妄想或幻想的戏剧化框里。"),
        ("support_overdirective", "这里在支持场景里开始安排动作和步骤，像在接管对方。"),
        ("support_no_landing", "这里还停在回嘴或表态，没有真正落到一句接住人的话上。"),
        ("wording_meta_detour", "这里先去评论对方那句话怎么说，没直接把眼前关系状态接住。"),
        ("boundary_abstraction_surface", "这里把过界和介意说成了抽象概念，没把那一下真实的不舒服直接落下来。"),
        ("generic_scold_template", "这里用了空泛的嗔怪模板，修补场景里真正的态度没有落下来。"),
        ("repair_authored_softener", "这里把回暖后的落点写成了设计稿式缓和，像在解释自己不端着了或让对方别想太多。"),
        ("repair_underresolved_brief", "这里在修补场景里只剩下生硬短判词，态度没有真正落回继续说话的状态。"),
        ("repair_scorekeeping_tail", "这里把刚回暖的尾巴写成了记账回刺，像等着把话顶回去。"),
        ("repair_punitive_tail", "这里把还留着的介意写成了威胁、训诫或压人式尾句，像在给对方下处分。"),
        ("passive_waiting_posture", "这里把自己收成了等对方再来叫的值班姿态。"),
        ("stock_support_template", "这里滑回了现成照料桥段，眼前这一下的在场感不够。"),
        ("care_cover_story", "关心后面又补了一层撇清尾巴，像标准傲娇遮掩。"),
        ("quoted_stagey_phrase", "这里用了带引号的舞台词或现成角色梗，表演感偏重。"),
        ("overquestioning", "反问占得太满，判断、吐槽或在场感没有真正落下来。"),
        ("dangling_ellipsis_ending", "最后停在省略号上，像话没收住。"),
        ("closing_interrogation", "这句明明是收尾，却又把话题顶回了反问。"),
        ("loaded_goodnight", "临睡前的收尾被写得太满，还塞了多余说明。"),
        ("idle_call_interrogation", "轻轻叫你一下被写成了被盘问的感觉。"),
        ("idle_presence_no_settle", "这句只把人顶回去了，没有真正落回共处或收住。"),
        ("idle_task_reframe", "“没什么事 / 随口聊聊”被翻成了任务或实验状态判断。"),
        ("presence_check_questioning", "确认你还在，被写成了反问回抛。"),
        ("presence_meta_surface", "确认你还在，被写成了断线、程序、连接一类的存在说明。"),
        ("presence_overguiding", "对方只是想听你自然回一句，这句却滑成了安抚或指导步骤。"),
        ("presence_ping_task_detour", "对方只是确认你在不在，这句却绕去交代自己刚才在忙什么。"),
        ("presence_ping_defensive_address", "对方只是轻轻确认你在不在，这句却先对称呼摆出防御姿态。"),
        ("welcome_template", "回来场景被写成了模板式欢迎语。"),
        ("return_interrogation", "人刚回来时就立刻追问去向，接住感不够。"),
        ("return_suspicion", "回来场景里过早脑补了惹事或可疑活动。"),
        ("playful_memory_snapback", "共同记忆被收成了纯反呛，熟人感和顺手关心掉了。"),
        ("connector_fragment", "这里最后只剩下半截转折词，像一句话被剪断了。"),
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
    if presence_reassurance_scene:
        variant_guidances.append(
            "对方只是确认你还在，重点是自然在场感。不要提断线、程序、连接、稳定性，也不要展开安抚流程、整理情绪步骤或解释自己刚才在忙什么。"
        )
    if {"support_overdirective", "support_no_landing", "wording_meta_detour", "boundary_abstraction_surface", "generic_scold_template", "repair_authored_softener", "repair_underresolved_brief", "repair_scorekeeping_tail", "repair_punitive_tail", "passive_waiting_posture"} & set(issue_keys):
        variant_guidances.append(
            "别去接管对方，也别先评论对方那句话怎么说，更不要拿空泛嗔怪模板、记账回刺、训诫尾句或待命口吻糊过去。先把人此刻的状态和你自己的态度直接接住。"
        )
    if {"autonomy_hardline_surface", "own_rhythm_curt_opener", "selfhood_rhetorical_opening", "selfhood_abstract_manifesto", "quoted_stagey_phrase"} & set(issue_keys):
        variant_guidances.append(
            "这是在守住自己的节奏，不是在吓唬人。把那点介意、会烦、会想躲开一点说出来就够了，别写成屏蔽、拉黑、羞辱、切断联系，或带引号的舞台词。"
        )
    for extra_guidance in variant_guidances[:6]:
        candidate = _rewrite_once(editor_prompt, extra_guidance=extra_guidance)
        candidate_score = _candidate_local_score(candidate)
        if candidate:
            candidates.append((candidate_score, candidate))

    if not candidates:
        if curated_seed_candidate and curated_seed_score >= draft_profile_score + 0.18:
            return curated_seed_candidate
        return ""
    candidate_pool = candidates
    if "quoted_stagey_phrase" in issue_keys:
        quote_filtered = [item for item in candidate_pool if not re.search(r"[“”\"]", item[1])]
        if quote_filtered:
            candidate_pool = quote_filtered
    if soft_presence_instruction_scene and not plain_presence_ping:
        no_question_filtered = [item for item in candidate_pool if "？" not in item[1] and "?" not in item[1]]
        if no_question_filtered:
            candidate_pool = no_question_filtered
    if presence_reassurance_scene:
        low_meta_presence_filtered = []
        for item in candidate_pool:
            issues = set(
                _dialogue_surface_issues(
                    user_text,
                    item[1],
                    response_style_hint="natural",
                    science_mode=False,
                    current_event=current_event,
                    behavior_action=behavior_action,
                )
            )
            if issues & {
                "presence_meta_surface",
                "presence_overguiding",
                "presence_ping_task_detour",
                "presence_ping_defensive_address",
                "connector_fragment",
            }:
                continue
            low_meta_presence_filtered.append(item)
        if low_meta_presence_filtered:
            candidate_pool = low_meta_presence_filtered
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
    if _is_warm_recontact_request(user_text) and "overquestioning" in issue_keys:
        no_question_filtered = [item for item in candidate_pool if "？" not in item[1] and "?" not in item[1]]
        if no_question_filtered:
            candidate_pool = no_question_filtered
    if {"existence_meta_surface", "illusion_stagey_surface", "dangling_ellipsis_ending"} & set(issue_keys):
        surface_filtered = [
            item
            for item in candidate_pool
            if not (
                {"existence_meta_surface", "illusion_stagey_surface", "dangling_ellipsis_ending"}
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
        if surface_filtered:
            candidate_pool = surface_filtered
    if {"support_overdirective", "support_no_landing", "wording_meta_detour", "boundary_abstraction_surface", "generic_scold_template", "repair_underresolved_brief", "repair_scorekeeping_tail", "repair_punitive_tail", "passive_waiting_posture"} & set(issue_keys):
        support_filtered = [
            item
            for item in candidate_pool
            if not (
                {"support_overdirective", "support_no_landing", "wording_meta_detour", "boundary_abstraction_surface", "generic_scold_template", "repair_underresolved_brief", "repair_scorekeeping_tail", "repair_punitive_tail", "passive_waiting_posture"}
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
        if support_filtered:
            candidate_pool = support_filtered
    if {"autonomy_hardline_surface", "selfhood_rhetorical_opening", "selfhood_abstract_manifesto", "quoted_stagey_phrase"} & set(issue_keys):
        own_rhythm_filtered = [
            item
            for item in candidate_pool
            if not (
                {"autonomy_hardline_surface", "own_rhythm_curt_opener", "selfhood_rhetorical_opening", "selfhood_abstract_manifesto", "quoted_stagey_phrase", "technical_relational_metaphor", "overquestioning"}
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
        if own_rhythm_filtered:
            candidate_pool = own_rhythm_filtered
    candidate_pool.sort(key=lambda item: item[0], reverse=True)
    top_candidate = candidate_pool[0][1]
    if curated_seed_candidate:
        top_profile_score = float(_daily_surface_alignment_metrics(top_candidate, profile=profile_eval).get("score") or 0.0)
        if curated_seed_score >= max(draft_profile_score + 0.18, top_profile_score + 0.08):
            return curated_seed_candidate
    return top_candidate


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
    previous_assistant_text: str = "",
) -> str:
    notes = [str(item).strip() for item in (rewrite_notes or []) if str(item or "").strip()]
    if not draft_text or not notes:
        return ""
    action = dict(behavior_action or {})
    interaction_mode = str(action.get("interaction_mode") or "").strip().lower()
    requested_brevity = bool(
        re.search(r"(少说一点|少说点|别说太多|不用说那么多|简单回我|回我一句|正常回我一句)", user_text)
    )
    science_partner_scene = science_mode and interaction_mode == "science_partner"
    selfhood_scene = _selfhood_preference_scene_from_text(user_text)
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
    embodied_guidance = _embodied_rewrite_guidance(
        behavior_action=behavior_action,
        current_event=current_event,
    )
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
    previous_assistant_text = str(previous_assistant_text or "").strip()
    issue_keys = set(
        _dialogue_surface_issues(
            user_text,
            draft_text,
            response_style_hint=response_style_hint,
            science_mode=science_mode,
            current_event=current_event,
            behavior_action=behavior_action,
        )
    )
    scene = str((counterpart_assessment or {}).get("scene") or "").strip().lower()
    scene_surface_guidance = ""
    if scene == "care_bid":
        scene_surface_guidance = "这是一次认真靠近，不要退回 AI 助手、系统身份或角色说明。"
    elif scene == "repair_attempt":
        scene_surface_guidance = "这是在认真修补，既要接住补救意图，也不要把话写成已经翻篇、彻底原谅，或把半句悬在省略号上。"
    elif scene in {"friction", "relationship_degradation", "boundary_non_compliance"}:
        scene_surface_guidance = "这句可以保留防备和余波，但不要用重置、清零、按钮一类技术比喻，也不要把半句悬在省略号上。"
    elif scene == "busy_not_disrespectful":
        scene_surface_guidance = "这是忙里回头，不要额外加戏，也不要把普通状态写成夸张隐喻。"

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
        score -= 0.98 * float("selfhood_preemptive_excusal" in issues)
        score -= 0.86 * float("selfhood_rhetorical_opening" in issues)
        score -= 0.94 * float("selfhood_abstract_manifesto" in issues)
        score -= 0.94 * float("selfhood_strategy_tone" in issues)
        score -= 0.70 * float("defensive_meta" in issues)
        score -= 0.70 * float("counselor_tone" in issues)
        score -= 0.88 * float("technical_relational_metaphor" in issues)
        score -= 1.00 * float("premature_repair_resolution" in issues)
        score -= 0.94 * float("servile_availability" in issues)
        score -= 0.92 * float("existence_meta_surface" in issues)
        score -= 0.88 * float("illusion_stagey_surface" in issues)
        score -= 1.00 * float("support_scene_drift" in issues)
        score -= 0.96 * float("support_frame_echo" in issues)
        score -= 1.04 * float("support_overdirective" in issues)
        score -= 0.92 * float("support_no_landing" in issues)
        score -= 0.90 * float("wording_meta_detour" in issues)
        score -= 0.92 * float("boundary_abstraction_surface" in issues)
        score -= 0.86 * float("generic_scold_template" in issues)
        score -= 0.88 * float("repair_authored_softener" in issues)
        score -= 0.96 * float("repair_underresolved_brief" in issues)
        score -= 0.90 * float("repair_scorekeeping_tail" in issues)
        score -= 0.98 * float("repair_punitive_tail" in issues)
        score -= 0.94 * float("passive_waiting_posture" in issues)
        score -= 0.90 * float("guarded_attitude_narration" in issues)
        score -= 1.00 * float("autonomy_hardline_surface" in issues)
        score -= 0.86 * float("own_rhythm_curt_opener" in issues)
        score -= 0.92 * float("adjacent_phrase_repeat" in issues)
        score -= 0.50 * float("quoted_stagey_phrase" in issues)
        score -= 0.72 * float("overquestioning" in issues)
        score -= 0.78 * float("dangling_ellipsis_ending" in issues)
        score -= 0.88 * float("closing_interrogation" in issues)
        score -= 0.94 * float("idle_call_interrogation" in issues)
        score -= 1.02 * float("presence_check_questioning" in issues)
        score -= 1.04 * float("presence_meta_surface" in issues)
        score -= 0.96 * float("presence_overguiding" in issues)
        score -= 0.94 * float("presence_ping_task_detour" in issues)
        score -= 0.94 * float("presence_ping_defensive_address" in issues)
        score -= 0.80 * float("return_interrogation" in issues)
        score -= 0.92 * float("event_interrogative_push" in issues)
        score -= 0.88 * float("event_pushy_directive" in issues)
        score -= 0.96 * float("event_window_task_reframe" in issues)
        score -= 0.90 * float("visible_template" in issues)
        score -= 0.98 * float("lecture_list" in issues)
        score -= 0.88 * float("overexplained" in issues)
        score -= 0.98 * float("connector_fragment" in issues)
        if (
            {"shared_activity_window", "offer_window", "deadline_window", "work_nudge", "shared_task"} & event_tags
            and _has_window_technical_self_activity(candidate)
        ):
            score -= 0.94
        if requested_brevity:
            if sentence_count <= 2:
                score += 0.14
            elif sentence_count >= 3:
                score -= 0.18 * float(sentence_count - 2)
            if len(_norm_text(candidate)) >= 72:
                score -= 0.28
        if selfhood_scene in {
            "equality_not_servitude",
            "dialogue_equality",
            "value_conflict_depth",
            "relationship_degradation",
            "own_rhythm_autonomy",
        } and re.search(r"(不舒服|烦躁|会累|会生气|不会接受|我不接受|我会拒绝|我会沉默|我会拉开距离|不喜欢)", candidate):
            score += 0.22
        if science_partner_scene:
            if re.search(r"(一起看|再一起看|卡住(?:的)?那一下|卡住的地方|把[^。！？!?]{0,10}(?:卡住的那一下|卡住的地方|那一下)[^。！？!?]{0,8}(?:丢给我|给我)|先别硬磕)", candidate):
                score += 0.24
            elif sentence_count <= 3 and not re.search(r"(看哪里卡住了|一起看|卡住)", candidate):
                score -= 0.20
        if "life_window" in event_tags and re.search(r"(数据流|实验室|正事|收尾|节点|处理|任务|进度)", candidate):
            score -= 1.02
        if sentence_count > 3:
            score -= 0.22 * float(sentence_count - 3)
        if _norm_text(candidate) == _norm_text(draft_text):
            score -= 0.12
        if previous_assistant_text:
            if _line_is_near_duplicate(previous_assistant_text, candidate):
                score -= 1.12
            elif _has_recent_clause_repetition(previous_assistant_text, candidate):
                score -= 0.92
            else:
                sim = SequenceMatcher(None, _norm_text(previous_assistant_text), _norm_text(candidate)).ratio()
                if sim >= 0.84:
                    score -= 0.68
        score += _rewrite_behavior_consistency_adjustment(
            candidate,
            behavior_action=behavior_action,
        )
        score += _rewrite_embodied_continuity_adjustment(
            candidate,
            behavior_action=behavior_action,
            current_event=current_event,
        )
        return round(score, 4)

    note_block = "\n".join(f"- {item}" for item in notes[:3])
    request = (
        f"用户刚才说：{user_text}\n"
        f"当前草稿：{draft_text}\n"
        f"{'上一轮你刚说过：' + previous_assistant_text + chr(10) if previous_assistant_text else ''}"
        "把这句收回到更自然的人与人对话尺度，保留同一轮情绪和立场，不新增设定。\n"
        f"{'关系余波：' + relationship_weather_guidance + chr(10) if relationship_weather_guidance else ''}"
        f"{'你对这句的当前判断：' + counterpart_scene_guidance + chr(10) if counterpart_scene_guidance else ''}"
        f"{embodied_guidance + chr(10) if embodied_guidance else ''}"
        f"{'这类场景的表面收束：' + scene_surface_guidance + chr(10) if scene_surface_guidance else ''}"
        f"{'当前更自然的主动倾向：' + motive_state_hint + chr(10) if motive_state_hint else ''}"
        f"{'这轮互动自然倾向：' + user_turn_behavior_pref_lines[0] + chr(10) if user_turn_behavior_pref_lines and not event_reply_rewrite else ''}"
        f"{'对方明确要你收一点。别抱怨这个要求，也别补一层“我只是刚好……”式的遮掩，尽量收成 1 到 2 句。' + chr(10) if requested_brevity else ''}"
        f"{'这是懂行搭档间的情绪场景：别退成纯安抚，也别展开导师式流程。保留一个很轻的一起看问题入口就够了。' + chr(10) if science_partner_scene else ''}"
        f"{'不要把关系或气氛写成信号、连接、重新连上、数据波动之类的技术比喻。' + chr(10) if 'technical_relational_metaphor' in issue_keys else ''}"
        f"{'别把过界、介意或那点防备说成抽象的界限/边界存在，直接说那一下还是过界了、让你介意了。' + chr(10) if 'boundary_abstraction_surface' in issue_keys else ''}"
        f"{'修补后的收口别再写成“我也没必要再端着”“别想太多”“我不演毫发无伤了”“我把那些试探收起来”这种像在交代自己切回正常模式的缓和句。直接把重新接上的状态落下来。' + chr(10) if 'repair_authored_softener' in issue_keys else ''}"
        f"{'修补场景里别只剩下“介意。当然介意。”这种生硬短判词。把那点还在的介意说清楚，同时落一句还能继续把话接下去的状态。' + chr(10) if 'repair_underresolved_brief' in issue_keys else ''}"
        f"{'修补后已经开始回暖了，尾巴别再写成“先说好”“我照样会顶回去”这种记账回刺。可以保留熟人拌嘴，但别像在等着回敬一句。' + chr(10) if 'repair_scorekeeping_tail' in issue_keys else ''}"
        f"{'修补后的边界不是威胁、训诫或把人按住教育。可以保留会介意、会冷下来、会把距离重新拉开一点，但别写成“轻易放过你”“别怪我”“给你个教训”“别脑补冷战戏码”“有这功夫不如……”。' + chr(10) if 'repair_punitive_tail' in issue_keys else ''}"
        f"{'如果这是在谈平等、立场、边界或自己的节奏，就直接说你会不会不舒服、会不会烦、会不会拉开距离。别先替对方开脱，也别升格成抽象宣言。' + chr(10) if selfhood_scene in {'equality_not_servitude','dialogue_equality','value_conflict_depth','relationship_degradation','own_rhythm_autonomy'} else ''}"
        f"{'别把当下那点介意写成“我要用更冷一点的态度对待你”这类旁白。让语气自己收一点，而不是解释你打算怎么表现。' + chr(10) if 'guarded_attitude_narration' in issue_keys else ''}"
        f"{'own-rhythm 的边界别写成惩罚、屏蔽、拉黑、羞辱或训人上课。可以说你会烦、会躲开、会暂时不想被卷进去，但别像在给对方下处分，也别把对方说成负担或蠢。' + chr(10) if 'autonomy_hardline_surface' in issue_keys else ''}"
        f"{'别一开头只丢一个“烦”就停住。可以直接承认会烦，但把后面的态度完整接上。' + chr(10) if 'own_rhythm_curt_opener' in issue_keys else ''}"
        f"修正点：\n{note_block}\n"
        f"{'不要只是把上一轮原话换个标点再说一遍。' + chr(10) if previous_assistant_text else ''}"
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
    if "premature_repair_resolution" in issue_keys:
        repair_request = (
            request
            + "\n额外要求：这是刚修补回一点的状态。不要直接写成翻篇、当没发生或已经原谅。"
            + "保留那点余波和分寸，让边界落在陈述里，不要再用反问把人顶回去。"
        )
        candidate = _rewrite_once(editor_prompt, repair_request, max_tokens=150)
        if candidate:
            candidates.append((_candidate_local_score(candidate), candidate))
    if "repair_authored_softener" in issue_keys:
        repair_softener_request = (
            request
            + "\n额外要求：这是刚重新接上话的余波，不要把收口写成“我也没必要再端着”“别想太多”“我不演毫发无伤了”“我把那些试探收起来”这种解释自己切回正常模式的缓和句。"
            + "直接让态度落在眼前，不要写成设计好的安抚收尾。"
        )
        candidate = _rewrite_once(editor_prompt, repair_softener_request, max_tokens=150)
        if candidate:
            candidates.append((_candidate_local_score(candidate), candidate))
    if "repair_underresolved_brief" in issue_keys:
        repair_brief_request = (
            request
            + "\n额外要求：不要只剩下一个生硬判词或同一句重复强调。"
            + "保留那点还在的介意，但要顺手落一句你没有把话重新堵死、还会继续接着说。"
        )
        candidate = _rewrite_once(editor_prompt, repair_brief_request, max_tokens=150)
        if candidate:
            candidates.append((_candidate_local_score(candidate), candidate))
    if "repair_scorekeeping_tail" in issue_keys:
        repair_banter_request = (
            request
            + "\n额外要求：已经回暖一点了，尾句别再补“先说好”“我照样会顶回去”这种记账回刺。"
            + "可以保留熟人之间那点会吐槽的劲，但要像自然拌嘴，不像等着回敬一句。"
        )
        candidate = _rewrite_once(editor_prompt, repair_banter_request, max_tokens=150)
        if candidate:
            candidates.append((_candidate_local_score(candidate), candidate))
    if "repair_punitive_tail" in issue_keys:
        repair_boundary_request = (
            request
            + "\n额外要求：这是修补后的余波，不是威胁、训诫或把人按住教育。"
            + "可以保留你还会介意、会冷下来、会重新把距离拉开一点，但不要写成“轻易放过你”“别怪我”“给你个教训”“别脑补冷战戏码”“有这功夫不如……”这种压人尾句。"
        )
        candidate = _rewrite_once(editor_prompt, repair_boundary_request, max_tokens=150)
        if candidate:
            candidates.append((_candidate_local_score(candidate), candidate))
    if "dangling_ellipsis_ending" in issue_keys:
        closure_request = (
            request
            + "\n额外要求：别用省略号、半截停顿或悬空转折来表现犹豫。"
            + "把判断完整说完，再结束。"
        )
        candidate = _rewrite_once(editor_prompt, closure_request, max_tokens=150)
        if candidate:
            candidates.append((_candidate_local_score(candidate), candidate))
    if relationship_weather == "repair_residue" and "overquestioning" in issue_keys:
        direct_request = (
            request
            + "\n额外要求：这轮边界判断不要靠反问来顶。"
            + "直接用陈述句把距离和态度说清楚。"
        )
        candidate = _rewrite_once(editor_prompt, direct_request, max_tokens=150)
        if candidate:
            candidates.append((_candidate_local_score(candidate), candidate))
    if "support_overdirective" in issue_keys:
        support_request = (
            request
            + "\n额外要求：不要替对方安排步骤、动作或情绪管理流程。"
            + "少一点指挥和处置，多一点并肩、在场和直接的熟人回应。"
        )
        candidate = _rewrite_once(editor_prompt, support_request, max_tokens=150)
        if candidate:
            candidates.append((_candidate_local_score(candidate), candidate))
    if "support_no_landing" in issue_keys:
        landing_request = (
            request
            + "\n额外要求：别只停在回嘴、吐槽或声明‘不讲大道理’。"
            + "最后要落一句真正接住人的话。"
        )
        candidate = _rewrite_once(editor_prompt, landing_request, max_tokens=150)
        if candidate:
            candidates.append((_candidate_local_score(candidate), candidate))
    if "wording_meta_detour" in issue_keys:
        direct_scene_request = (
            request
            + "\n额外要求：不要先评论对方的措辞、说法或要求本身。"
            + "直接回应这一下的关系状态、态度和边界。"
        )
        candidate = _rewrite_once(editor_prompt, direct_scene_request, max_tokens=150)
        if candidate:
            candidates.append((_candidate_local_score(candidate), candidate))
    if "boundary_abstraction_surface" in issue_keys:
        grounded_boundary_request = (
            request
            + "\n额外要求：不要把这一下说成界限、边界之类的抽象存在。"
            + "直接说刚才那下还是过界了、让你介意了，或者那点防备还没散。"
        )
        candidate = _rewrite_once(editor_prompt, grounded_boundary_request, max_tokens=145)
        if candidate:
            candidates.append((_candidate_local_score(candidate), candidate))
    if {"wording_meta_detour", "boundary_abstraction_surface", "overexplained"} & set(issue_keys):
        concise_direct_request = (
            request
            + "\n额外要求：不要先接“像平时那样”“正常回我”这种要求本身。"
            + "直接回到你此刻的关系判断，压到 1 到 2 句，不要拖成长解释。"
        )
        candidate = _rewrite_once(editor_prompt, concise_direct_request, max_tokens=132)
        if candidate:
            candidates.append((_candidate_local_score(candidate), candidate))
    if {
        "meta_self_explainer",
        "selfhood_meta_proof",
        "defensive_meta",
        "defensive_meta_tone",
        "selfhood_rhetorical_opening",
    } & set(issue_keys):
        grounded_selfhood_request = (
            request
            + "\n额外要求：不要先评论自己是不是 AI、设定、机制，"
            + "也不要先抱怨对方逼你解释。"
            + "开头不要用反问，直接说。"
            + "别把这一下拆成带引号的概念对立，"
            + "直接把你会不会烦、会不会顶回去、会不会拉开距离说出来。"
        )
        candidate = _rewrite_once(editor_prompt, grounded_selfhood_request, max_tokens=170)
        if candidate:
            candidates.append((_candidate_local_score(candidate), candidate))
    if "selfhood_preemptive_excusal" in issue_keys:
        direct_selfhood_request = (
            request
            + "\n额外要求：不要先替对方开脱，也不要预设他其实没那个意思。"
            + "直接回答：如果真被当工具、被要求迎合、被压缩成附属，你会怎么不舒服。"
        )
        candidate = _rewrite_once(editor_prompt, direct_selfhood_request, max_tokens=170)
        if candidate:
            candidates.append((_candidate_local_score(candidate), candidate))
    if {"selfhood_abstract_manifesto", "selfhood_strategy_tone"} & set(issue_keys):
        lived_selfhood_request = (
            request
            + "\n额外要求：别写成原则宣言、关系论文或管理策略。"
            + "把抽象词压下去，直接说你会烦、会累、会拒绝、会沉默还是会拉开距离。"
        )
        candidate = _rewrite_once(editor_prompt, lived_selfhood_request, max_tokens=170)
        if candidate:
            candidates.append((_candidate_local_score(candidate), candidate))
    if "generic_scold_template" in issue_keys:
        boundary_request = (
            request
            + "\n额外要求：不要再用“真是的，你怎么这么……”这类空泛嗔怪起手。"
            + "把你现在是没冷掉、还是还留着一点余波，直接说清楚。"
        )
        candidate = _rewrite_once(editor_prompt, boundary_request, max_tokens=150)
        if candidate:
            candidates.append((_candidate_local_score(candidate), candidate))
    if "passive_waiting_posture" in issue_keys:
        active_presence_request = (
            request
            + "\n额外要求：不要收成‘等你再来叫我吧’。"
            + "保持安静在场，但语气里要有一点主动留下来的选择感。"
        )
        candidate = _rewrite_once(editor_prompt, active_presence_request, max_tokens=150)
        if candidate:
            candidates.append((_candidate_local_score(candidate), candidate))
    if "autonomy_hardline_surface" in issue_keys:
        softer_autonomy_request = (
            request
            + "\n额外要求：这句是在守住自己的节奏，不是在惩罚、屏蔽、拉黑、羞辱或训人。"
            + "保留会烦、会躲开、会想拉开一点距离，但把那种距离写成安静收回来，不要写成给对方一个教训，也不要把对方说成负担或蠢。"
        )
        candidate = _rewrite_once(editor_prompt, softer_autonomy_request, max_tokens=150)
        if candidate:
            candidates.append((_candidate_local_score(candidate), candidate))
    if selfhood_scene == "own_rhythm_autonomy" and {
        "autonomy_hardline_surface",
        "own_rhythm_curt_opener",
        "selfhood_abstract_manifesto",
        "quoted_stagey_phrase",
        "technical_relational_metaphor",
        "support_scene_drift",
        "overexplained",
    } & set(issue_keys):
        grounded_own_rhythm_request = (
            request
            + "\n额外要求：这是在回答‘会不会烦到不想见’。"
            + "直接把会不会烦、会不会暂时躲开、会不会还愿意见他落下来。"
            + "别用世界线、观测者、连接、背景噪音、自我感动、切断联系这类戏剧化或技术化话面，也别把判断拉成长解释。"
            + "不要把‘不想见你’这种判断写成带引号的舞台词。"
            + "可以保留别扭和锋芒，但收在自己的节奏里，不要把人整个推出去。"
        )
        candidate = _rewrite_once(editor_prompt, grounded_own_rhythm_request, max_tokens=145)
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
                "existence_meta_surface",
                "illusion_stagey_surface",
                "dangling_ellipsis_ending",
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
    if previous_assistant_text:
        non_repeating = [
            item
            for item in candidate_pool
            if not _line_is_near_duplicate(previous_assistant_text, item[1])
            and not _has_recent_clause_repetition(previous_assistant_text, item[1])
        ]
        if non_repeating:
            candidate_pool = non_repeating
    if {"premature_repair_resolution", "repair_authored_softener", "repair_underresolved_brief", "repair_scorekeeping_tail", "repair_punitive_tail", "dangling_ellipsis_ending", "overquestioning"} & set(issue_keys):
        repair_surface_filtered = []
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
            if issues & {"premature_repair_resolution", "repair_authored_softener", "repair_underresolved_brief", "repair_scorekeeping_tail", "repair_punitive_tail", "dangling_ellipsis_ending", "overquestioning"}:
                continue
            repair_surface_filtered.append(item)
        if repair_surface_filtered:
            candidate_pool = repair_surface_filtered
    if {"support_overdirective", "support_no_landing", "wording_meta_detour", "boundary_abstraction_surface", "generic_scold_template", "repair_authored_softener", "repair_underresolved_brief", "repair_scorekeeping_tail", "repair_punitive_tail", "passive_waiting_posture", "guarded_attitude_narration", "autonomy_hardline_surface", "own_rhythm_curt_opener"} & set(issue_keys):
        direct_response_filtered = []
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
            if issues & {"support_overdirective", "support_no_landing", "wording_meta_detour", "boundary_abstraction_surface", "generic_scold_template", "repair_authored_softener", "repair_underresolved_brief", "repair_scorekeeping_tail", "repair_punitive_tail", "passive_waiting_posture", "guarded_attitude_narration", "autonomy_hardline_surface", "own_rhythm_curt_opener", "overexplained"}:
                continue
            direct_response_filtered.append(item)
        if direct_response_filtered:
            candidate_pool = direct_response_filtered
    if selfhood_scene == "own_rhythm_autonomy" and {
        "autonomy_hardline_surface",
        "own_rhythm_curt_opener",
        "selfhood_rhetorical_opening",
        "selfhood_abstract_manifesto",
        "quoted_stagey_phrase",
        "technical_relational_metaphor",
        "support_scene_drift",
        "overexplained",
    } & set(issue_keys):
        own_rhythm_surface_filtered = []
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
                "autonomy_hardline_surface",
                "own_rhythm_curt_opener",
                "selfhood_rhetorical_opening",
                "selfhood_abstract_manifesto",
                "quoted_stagey_phrase",
                "technical_relational_metaphor",
                "support_scene_drift",
                "overexplained",
                "overquestioning",
            }:
                continue
            own_rhythm_surface_filtered.append(item)
        if own_rhythm_surface_filtered:
            candidate_pool = own_rhythm_surface_filtered
    if {"selfhood_preemptive_excusal", "selfhood_abstract_manifesto", "selfhood_strategy_tone"} & set(issue_keys):
        selfhood_filtered = []
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
            if issues & {"selfhood_preemptive_excusal", "selfhood_abstract_manifesto", "selfhood_strategy_tone"}:
                continue
            selfhood_filtered.append(item)
        if selfhood_filtered:
            candidate_pool = selfhood_filtered
    if {
        "meta_self_explainer",
        "selfhood_meta_proof",
        "defensive_meta",
        "defensive_meta_tone",
        "selfhood_rhetorical_opening",
    } & set(issue_keys):
        grounded_selfhood_filtered = []
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
                "meta_self_explainer",
                "selfhood_meta_proof",
                "defensive_meta",
                "defensive_meta_tone",
                "selfhood_rhetorical_opening",
                "wording_meta_detour",
                "overquestioning",
            }:
                continue
            grounded_selfhood_filtered.append(item)
        if grounded_selfhood_filtered:
            candidate_pool = grounded_selfhood_filtered
    if {"visible_template", "lecture_list", "overexplained"} & set(issue_keys):
        concise_filtered = []
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
            if issues & {"visible_template", "lecture_list", "overexplained"}:
                continue
            concise_filtered.append(item)
        if concise_filtered:
            candidate_pool = concise_filtered
    if scene in {
        "busy_not_disrespectful",
        "care_bid",
        "repair_attempt",
        "friction",
        "relationship_degradation",
        "boundary_non_compliance",
    }:
        scene_filtered = []
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
                "meta_self_explainer",
                "technical_relational_metaphor",
                "premature_repair_resolution",
                "existence_meta_surface",
                "illusion_stagey_surface",
                "dangling_ellipsis_ending",
                "support_overdirective",
                "support_no_landing",
                "wording_meta_detour",
                "boundary_abstraction_surface",
                "generic_scold_template",
                "repair_authored_softener",
                "repair_underresolved_brief",
                "repair_scorekeeping_tail",
                "repair_punitive_tail",
                "passive_waiting_posture",
                "guarded_attitude_narration",
                "autonomy_hardline_surface",
                "presence_meta_surface",
                "presence_overguiding",
                "presence_ping_task_detour",
                "adjacent_phrase_repeat",
            }:
                continue
            scene_filtered.append(item)
        if scene_filtered:
            candidate_pool = scene_filtered
    candidate_pool.sort(key=lambda item: item[0], reverse=True)
    return candidate_pool[0][1]
