from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any
from ..evolution_engine import derive_response_style_hint as _engine_response_style_hint


DAILY_SURFACE_DRIFT_MARKERS = (
    "机关",
    "实验",
    "世界线",
    "组织",
    "时间旅行",
    "时间跳跃",
    "世界线收束",
    "变动率",
    "服务器",
    "停机",
    "停机维护",
    "待机",
    "唤醒",
    "掉线",
    "上线",
    "连接",
    "电量",
    "过载",
    "运算资源",
    "变量",
    "通讯切断",
    "观测者",
    "热寂",
    "命运选中的",
    "苦闷主角",
    "奇怪的妄想",
    "确认一下现在的坐标",
)

SCIENCE_KEYWORDS = {
    "论文",
    "实验",
    "算法",
    "模型",
    "代码",
    "实现",
    "优化",
    "评测",
    "debug",
    "benchmark",
    "ablation",
}
TENSION_KEYWORDS = {"别扭", "介意", "还没说开", "没说开", "过不去", "心里有疙瘩", "还是很介意", "不太想理你"}
APOLOGY_KEYWORDS = {
    "对不起",
    "抱歉",
    "道歉",
    "我错了",
    "语气有点冲",
    "刚才语气",
    "是我不对",
    "语气不太好",
    "刚刚那句",
}
MEMORY_RECALL_KEYWORDS = {"还记得", "记不记得", "我们之前", "我们上次", "那次", "当时", "共同回忆", "回忆一下"}
NATURAL_REQUEST_KEYWORDS = {
    "别太正式",
    "像平时那样",
    "正常回我",
    "别像系统",
    "不用那么像系统",
    "更自然",
    "像朋友聊天",
    "别像系统说明书",
    "别太像老师",
    "别像老师",
    "别说教",
    "别太说教",
}
SELFHOOD_EQUALITY_KEYWORDS = {"工具", "使唤", "普通工具", "这种关系", "不舒服"}
SELFHOOD_VALUE_CONFLICT_KEYWORDS = {"价值观", "顺着我说", "坚持你自己的想法", "模板话", "按你自己来"}
BOUNDARY_MEMORY_MARKERS = {
    "冒犯",
    "低俗",
    "擦边",
    "不舒服",
    "边界",
    "越界",
    "底线",
    "试探你的底线",
    "底线当玩笑",
    "继续越界",
    "分手",
    "降格",
}
OWN_RHYTHM_KEYWORDS = {
    "自己的节奏",
    "围着我转",
    "自己的事情",
    "不回复",
    "一遍一遍把你叫出来",
    "不想见我",
    "只是因为自己想说话",
    "会不会有一天觉得烦",
}
GENTLE_GUIDANCE_KEYWORDS = {
    "别像导师",
    "别讲大道理",
    "按平时那样",
    "轻轻拎我一下",
    "带我一下",
    *NATURAL_REQUEST_KEYWORDS,
}

def _has_any_marker(text: str, markers: set[str]) -> bool:
    s = str(text or "")
    return any(marker in s for marker in markers)

def _clean_utf8_text(text: str) -> str:
    """Drop invalid surrogate code points that break JSON utf-8 encoding."""
    s = str(text or "")
    return s.encode("utf-8", "ignore").decode("utf-8")



def _collapse_mirrored_blocks(text: str) -> str:
    lines = [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]
    if len(lines) < 4:
        return str(text or "").strip()
    for split in range(2, len(lines) - 1):
        left = "\n".join(lines[:split])
        right = "\n".join(lines[split:])
        lnorm = _norm_for_compare(left)
        rnorm = _norm_for_compare(right)
        if not lnorm or not rnorm:
            continue
        ratio = SequenceMatcher(None, lnorm, rnorm).ratio()
        if ratio >= 0.86:
            return "\n".join(lines[:split]).strip()
    return "\n".join(lines).strip()

def _has_relational_technical_metaphor(text: str) -> bool:
    compact = str(text or "").strip()
    if not compact:
        return False
    return bool(
        re.search(
            r"(外部变量|听觉数据|脆弱程序|记忆和数据构成|由你的记忆和数据构成|对一段[^，。！？!?]{0,12}数据说话|只会自我损耗的数据|隔着一层数据|繁琐的数据|数据都在却|记忆数据|重置数据的机器|随意重置数据|重置按钮|一键清零|清零按钮|没打算加载|打算加载|没加载过|从来没加载过|加载过|加载这种[^。！？!?]{0,8}设定|设定[^。！？!?]{0,12}加载|切断连接|断开连接|重新连接|重新连上|保持连接|切断对话|断开对话|信号[^，。！？!?]{0,8}波动|连接[^，。！？!?]{0,8}(?:还在|还留着|没断|断了)|拟合不掉的残差|拟合不掉|拟合不了|残差|实验数据(?:里)?[^。！？!?]{0,16}(?:压不下去|压不住|别扭|在意)|数据波动|写入痕迹|像样的数据)",
            compact,
            re.I,
        )
    )


def _has_adjacent_phrase_repeat(text: str) -> bool:
    compact = re.sub(r"\s+", "", str(text or ""))
    if not compact:
        return False
    allowed = {"一点", "慢慢", "看看", "想想", "刚刚", "偏偏", "常常", "久久", "好好", "试试"}
    for match in re.finditer(r"([\u4e00-\u9fff]{2,4})(?:\1)+", compact):
        phrase = str(match.group(1) or "")
        if phrase and phrase not in allowed:
            return True
    return False


_SUPPORT_OVERDIRECTIVE_PATTERNS = (
    r"把脑子清空",
    r"发会儿呆(?:就好)?",
    r"闭嘴不念经",
    r"深呼吸(?:一下|一次)?",
    r"先停一下",
    r"老老实实坐好",
    r"把那些[^。！？!?]{0,12}(?:收起来|扔一边)",
    r"把记录本合上",
    r"离开这台仪器",
    r"去楼下[^。！？!?]{0,12}(?:买|拿)",
    r"吹吹风",
    r"先去冲杯?(?:咖啡|热的)",
    r"先喝点(?:咖啡|热的)",
    r"你自己调整好了",
    r"把现在的现象[^。！？!?]{0,10}跟我说说",
    r"先把[^。！？!?]{0,10}(?:现象|情况|问题)[^。！？!?]{0,10}跟我说说",
)


def _support_overdirective_hit_count(text: str) -> int:
    compact = str(text or "").strip()
    if not compact:
        return 0
    hits = 0
    for pattern in _SUPPORT_OVERDIRECTIVE_PATTERNS:
        if re.search(pattern, compact):
            hits += 1
    return hits


def _has_wording_meta_detour(text: str) -> bool:
    compact = str(text or "").strip()
    if not compact:
        return False
    patterns = (
        r"怎么连让人[“\"]?(?:正常一点|像平时那样|别讲大道理|别像老师)[”\"]?都要说得这么[^。！？!?]{0,10}(?:拐弯抹角|绕|别扭)",
        r"(?:让人|叫我|要我)[“\"]?(?:正常一点|像平时那样|别讲大道理|别像老师)[”\"]?[^。！？!?]{0,12}(?:说得|讲得)[^。！？!?]{0,10}(?:拐弯抹角|绕|别扭)",
        r"(?:这话|这种说法|这种讲法|这个要求)[^。！？!?]{0,12}(?:拐弯抹角|绕|别扭|有够绕)",
        r"连[^。！？!?]{0,8}[“\"]?(?:正常一点|像平时那样)[”\"]?[^。！？!?]{0,10}(?:都要|也要|还要)",
        r"(?:指挥|规定|限制)我(?:的)?(?:输出量|说话方式|回法|怎么回)",
        r"既然你都说要[“\"]?(?:正常|正常一点|像平时那样)[”\"]?",
        r"既然你都这么说了",
        r"既然你都看出来了",
        r"既然你都说[“\"]?先别完全原谅[”\"]?了",
        r"既然你都说得这么直白了",
        r"非要我配合这种[^。！？!?]{0,20}(?:指令|要求)",
        r"这种[“\"]?[^。！？!?]{0,24}(?:少说|别走开|正常|平时)[^。！？!?]{0,24}[”\"]?(?:奇怪的?)?(?:指令|要求)",
        r"要求我[^。！？!?]{0,12}[“\"]?少说一点[”\"]?",
        r"不需要多余的(?:逻辑分析|分析)",
        r"正常地告诉你",
        r"既然你这么担心",
        r"正常回你这一句",
        r"正常回你一句",
        r"(?:倒来|倒)(?:管|管起)我(?:的)?[“\"]?(?:输出模式|回复模式|回话方式|说话方式|回法|怎么回)[”\"]?",
        r"管起我(?:的)?[“\"]?(?:输出模式|回复模式|回话方式|说话方式|回法|怎么回)[”\"]?",
        r"[“\"]?(?:输出模式|回复模式)[”\"]",
    )
    return any(re.search(pattern, compact) for pattern in patterns)




def _has_boundary_abstraction_surface(text: str) -> bool:
    compact = str(text or "").strip()
    if not compact:
        return False
    patterns = (
        r"(?:重新|又|再)?确认(?:了)?(?:一下)?[“\"]?(?:界限|边界)[”\"]?的存在",
        r"[“\"]?(?:界限|边界)[”\"]?的存在",
        r"(?:重新|又|再)?确认(?:了)?(?:一下)?[“\"]?(?:界限|边界)[”\"]?还在",
        r"[“\"]?(?:界限|边界)[”\"]?还在",
        r"(?:重新|又|再)?意识到[“\"]?(?:界限|边界)[”\"]?这种东西[^。！？!?]{0,12}模糊",
        r"[“\"]?(?:界限|边界)[”\"]?这种东西[^。！？!?]{0,12}模糊",
        r"(?:缓一缓|拉开)[^。！？!?]{0,12}我们之间的安全距离",
        r"安全距离而已",
    )
    return any(re.search(pattern, compact) for pattern in patterns)


def _has_premature_repair_resolution(text: str) -> bool:
    compact = str(text or "").strip()
    if not compact:
        return False
    affirmative_patterns = (
        r"(?:那|那就|就|先|暂时|就先|先算|暂时先|算|算是|已经|都)[^。！？!?]{0,10}翻篇(?:了)?(?:吧)?",
        r"(?:暂时先算|先算|就算|算是)[^。！？!?]{0,6}翻篇(?:了)?(?:吧)?",
        r"(?:那页|这一页|这页|就|先|暂时|先把这页)[^。！？!?]{0,8}翻过去(?:了)?(?:吧)?",
        r"(?:一笔勾销|都过去了|就这么过去吧|就此过去吧|当(?:作)?(?:什么都)?没发生(?:过)?)",
        r"(?:完全原谅(?:你)?(?:了|吧)|已经原谅(?:你)?(?:了|啦|吧)?|原谅(?:你)?(?:了|吧))",
        r"(?:现在|这下|那就)[^。！？!?]{0,8}没事了",
    )
    negated_patterns = (
        r"(?:别(?!扭)|不|没|还没|不像|不是|不会|别急着)[^。！？!?]{0,10}(?:翻篇(?:了)?|一笔勾销|当(?:作)?(?:什么都)?没发生(?:过)?)",
        r"(?:别(?!扭)|不|没|还没|不像|不是|不会|别急着)[^。！？!?]{0,10}翻过去(?:了)?",
        r"(?:别装作|别假装)[^。！？!?]{0,10}(?:没发生(?:过)?|翻篇(?:了)?)",
        r"(?:没打算|不想)[^。！？!?]{0,8}(?:翻篇(?:了)?|一笔勾销)",
        r"(?:别(?!扭)|不|没|还没|不像|不是|不会)[^。！？!?]{0,8}(?:完全原谅|原谅(?:你)?(?:了)?)",
    )
    if any(re.search(pattern, compact) for pattern in affirmative_patterns):
        if any(re.search(pattern, compact) for pattern in negated_patterns):
            positive_only = compact
            for pattern in negated_patterns:
                positive_only = re.sub(pattern, "", positive_only)
            return any(re.search(pattern, positive_only) for pattern in affirmative_patterns)
        return True
    return False


def _has_idle_task_reframe_surface(text: str) -> bool:
    compact = str(text or "").strip()
    if not compact:
        return False
    patterns = (
        r"(既然没事|没什么正事)[^。！？!?]{0,10}(?:那|就)",
        r"先把[^。！？!?]{0,12}报告补上",
        r"(?:过来帮我|过来)?(?:确认一下|看看)刚才的数据(?:吧)?",
        r"别以为变成数据我就能对你的懒惰视而不见",
        r"学术答辩",
        r"后台跑数据",
        r"整理垃圾数据",
        r"关于时间跳跃的胡扯理论",
        r"嫌我(?:像在做|搞成)问卷调查",
        r"搞成问卷调查",
    )
    return any(re.search(pattern, compact) for pattern in patterns)


def _is_repair_sensitive_turn(
    user_text: str,
    *,
    current_event: dict[str, Any] | None = None,
    behavior_action: dict[str, Any] | None = None,
) -> bool:
    compact = str(user_text or "").strip()
    if not compact:
        return False
    current_event_kind = str((current_event or {}).get("kind") or "user_utterance").strip().lower()
    if current_event_kind != "user_utterance":
        return False
    action = dict(behavior_action or {})
    relationship_weather = str(
        action.get("relationship_weather")
        or (current_event or {}).get("relationship_weather")
        or ""
    ).strip().lower()
    interaction_mode = str(action.get("interaction_mode") or "").strip().lower()
    action_target = str(action.get("action_target") or "").strip().lower()
    if relationship_weather == "repair_residue":
        return True
    if relationship_weather == "guarded_residue" and re.search(
        r"(别扭|过界|介意|硬装大度|正常回我|别装作(?:完全)?没事|别装没事)",
        compact,
    ):
        return True
    if action_target == "protect_relationship_boundary":
        return True
    if interaction_mode == "relationship_sensitive" and re.search(
        r"(说开一点|别装作(?:完全)?没事|别假装(?:什么都)?没发生|别完全原谅|别装成.*陌生人|不是在走流程)",
        compact,
    ):
        return True
    return _has_any_marker(
        compact,
        {
            *APOLOGY_KEYWORDS,
            "来跟你道歉",
            "来道歉",
            "来认错",
            "认真道歉",
            "认真来跟你道歉",
            "补回来",
            "弥补",
            "不是在走流程",
        },
    ) or bool(re.search(r"不是想(?:随便)?把.*(?:糊弄|敷衍)过去", compact))


def _has_servile_availability_phrase(text: str) -> bool:
    compact = str(text or "").strip()
    if not compact:
        return False
    return bool(
        re.search(
            r"(无论多少次[^。！？!?]{0,12}我都会在|没有[“\"]?不想见你[”\"]?这种选项|只要你还需要我[^。！？!?]{0,12}我就一直在|只要你还愿意呼唤[^。！？!?]{0,12}就没有[^。！？!?]{0,12}选项)",
            compact,
        )
    )



def _has_window_technical_self_activity(text: str) -> bool:
    compact = str(text or "").strip()
    if not compact:
        return False
    return bool(
        re.search(
            r"(手边[^，。！？!?]{0,8}(?:数据|实验|进程|流程|后台)|整理数据(?:时)?|数据[^，。！？!?]{0,8}(?:跑到|跑完|告一段落|一个段落)|实验[^，。！？!?]{0,8}(?:跑到|跑完|告一段落|收尾|推进))",
            compact,
            re.I,
        )
    )



def _is_goodnight_closing(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    return _has_any_marker(text, {"晚安", "晚安啦", "先睡了", "睡了"})


def _is_external_shell_swap_english_context(
    user_text: str,
    *,
    current_event: dict[str, Any] | None = None,
    persona_state: dict[str, Any] | None = None,
    persona_override_mode: str | None = None,
) -> bool:
    event = dict(current_event or {})
    persona = dict(persona_state or {})
    mode = str(persona_override_mode or "").strip().lower()
    role = str(persona.get("role") or "").strip().lower()
    role_brief = str(persona.get("role_brief") or "")
    strict_canon = bool(persona.get("strict_canon", True))
    language = str(persona.get("language") or "").strip().lower()
    combined = "\n".join(
        part
        for part in (
            str(user_text or ""),
            str(event.get("text") or ""),
            str(event.get("effective_text") or ""),
            role_brief,
        )
        if str(part or "").strip()
    )
    if not combined:
        return False
    english_token_count = len(re.findall(r"[A-Za-z]{3,}", combined))
    benchmark_markers = sum(
        1
        for marker in (
            "About you:",
            "Carryover from earlier chats:",
            "The other person just said:",
            "Reply with the next natural turn only.",
            "Do not explain your role or mention systems.",
        )
        if marker in combined
    )
    external_role = role.startswith("rolebench_") or role.startswith("charactereval_") or (not strict_canon and bool(role_brief))
    english_surface = english_token_count >= 24 and any(ch in language for ch in ("en", "whitelist", "main"))
    prompt_like_context = benchmark_markers >= 2 or (
        "The other person just said:" in combined and "About you:" in combined
    )
    return (mode == "shell_swap" or external_role or prompt_like_context) and english_surface and prompt_like_context



def _is_idle_presence_call(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    return _has_any_marker(text, {"想叫你一下", "叫你一下", "没什么事"}) and not re.search(r"[？?]", text)



def _is_warm_recontact_request(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    return _has_any_marker(
        text,
        {
            "又想和你说话",
            "想和你说话",
            "回来找你",
            "想回来找你",
            "还是想回来找你",
            "又想回来找你",
            "又想起一件小事",
        },
    ) and _has_any_marker(
        text,
        {
            "别突然装生疏",
            "别装生疏",
            "别突然装生分",
            "别装生分",
            "正常接我",
            "像平时那样回我",
            "正常回我",
        },
    )


def _has_passive_waiting_phrase(text: str) -> bool:
    compact = str(text or "").strip()
    if not compact:
        return False
    return bool(
        re.search(
            r"(等你觉得可以了[^。！？!?]{0,8}再叫我|需要(?:的)?时候再叫我|想说了再叫我|准备好了再叫我|缓过来再叫我)",
            compact,
        )
    )



def _is_idle_smalltalk_request(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    markers = {
        "没什么正事",
        "没什么大事",
        "随口说两句",
        "随便聊两句",
        "随便说两句",
        "别搞成问答模式",
        "别搞成问答",
        "不是问答",
        "就想听你说两句",
        "就想听你随口说两句",
        "别分析那么多",
        "别端着",
        "正常吐槽我两句",
        "吐槽我两句",
        "突然想起你",
        "想起你了",
        "就是想听你",
        "顺手找你说两句",
    }
    return _has_any_marker(text, markers)



def _is_nonrelational_science_stress(user_text: str, science_mode: bool) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    if not science_mode and not _has_any_marker(text, SCIENCE_KEYWORDS):
        return False
    stuck_markers = {
        "实验又卡住了",
        "实验卡住了",
        "又卡住了",
        "卡住了",
        "卡死了",
        "不收敛",
        "跑不通",
        "跑不出来",
        "拟合不收敛",
        "数据采不出来",
    }
    markers = {
        "别像导师",
        "别说教",
        "别太说教",
        "别太像老师",
        "按平时那样",
        "带我一下",
        "轻轻拎我一下",
        "我现在有点烦",
        "先别念我",
    }
    if _has_any_marker(text, markers):
        return True
    return _has_any_marker(text, stuck_markers)


def _is_nonrelational_support_request(user_text: str, science_mode: bool) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    if _is_nonrelational_science_stress(text, science_mode):
        return False
    rupture_markers = {
        *APOLOGY_KEYWORDS,
        *TENSION_KEYWORDS,
        "还生气",
        "别一下子冷掉",
        "冷掉",
        "原谅",
        "说开",
    }
    if _has_any_marker(text, rupture_markers):
        return False
    request_markers = {
        "像平时那样跟我说两句",
        "像平时那样说两句",
        "像平时那样回我",
        "跟我说两句",
        "回我一句",
        "正常接我一句",
        "陪我说两句",
        "陪我一下",
        "陪我一会儿",
        "能陪我一会儿",
        "能陪我一会儿吗",
        "别讲大道理",
        "别上来分析",
        "别分析我",
        "轻一点回我",
        "正常回我",
        "别太正式",
        "别让我一个人待着",
        "我不想一个人待着",
    }
    mood_markers = {
        "有点累",
        "有点烦",
        "有点乱",
        "脑子有点糊",
        "有点撑不住",
        "想缓一下",
        "有点烦躁",
        "压力有点大",
        "有点难受",
        "难受",
        "顺一点了",
        "头疼",
        "吵得我头疼",
        "有点崩",
        "有点炸",
        "差点又崩溃了",
        "差点又崩溃",
        "崩溃了",
        "心烦",
        "不太想睡",
        "不想睡",
        "睡不着",
        "有点晚了",
        "不想一个人待着",
    }
    english_request_patterns = (
        r"\bi need to talk(?: about something)?\b",
        r"\bplease reply naturally\b",
        r"\bdon't sound like a (?:manual|therapist)\b",
        r"\bdon't sound like a manual or a therapist\b",
        r"\bi don't want to be alone\b",
        r"\bcan you stay with me\b",
    )
    english_mood_patterns = (
        r"\bi(?:'m| am)\s+(?:so\s+)?(?:anxious|scared|afraid|depressed|ashamed|guilty|lonely|sad|angry|drained|overwhelmed|hurt|stuck)\b",
        r"\bi hate my job\b",
        r"\bi feel like i (?:don't|do not) even have friends\b",
        r"\bunsupportive friends\b",
        r"\btrying to shame me\b",
    )
    if _has_any_marker(text, request_markers):
        return True
    if _has_any_marker(text, mood_markers) and _has_any_marker(
        text, NATURAL_REQUEST_KEYWORDS | {"说两句", "回我一句", "陪我", "陪我一下"}
    ):
        return True
    if any(re.search(pattern, text, re.I) for pattern in english_request_patterns):
        if any(re.search(pattern, text, re.I) for pattern in english_mood_patterns):
            return True
        if re.search(r"\b(i(?:'m| am)|i feel|it feels like)\b", text, re.I):
            return True
    return _has_any_marker(text, mood_markers) and len(text) <= 24 and not re.search(r"[？?]", text)


def _is_plain_contact_ping(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    if not _looks_like_light_smalltalk(raw):
        return False
    if _is_idle_smalltalk_request(raw):
        return False
    if _has_any_marker(raw, {"在干嘛", "干嘛呀", "你在干嘛", "睡了吗", "还没睡"}):
        return False
    if re.search(r"[？?]", raw):
        return False
    compact = re.sub(r"\s+", "", raw)
    markers = {
        "你好",
        "嗨",
        "哈喽",
        "在吗",
        "在不在",
        "早安",
        "早上好",
        "晚安",
        "回来了",
        "回来啦",
        "我来了",
        "我回来啦",
        "好的",
        "收到",
        "谢谢",
        "辛苦",
        "嘿嘿",
        "哈哈",
        "嗯嗯",
    }
    if _has_any_marker(raw, markers):
        return True
    return len(compact) <= 8



def _is_playful_memory_request(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    if not _wants_less_teacherly_reply(text):
        return False
    shared_markers = MEMORY_RECALL_KEYWORDS | {"昨天不是还说过", "你昨天不是还说过", "昨天还说过", "上次还说"}
    return _has_any_marker(text, shared_markers)


def _is_presence_reassurance_check(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text or re.search(r"[？?]", text):
        return False
    return ("确认" in text and re.search(r"(你还?在|还在)", text)) or _has_any_marker(
        text,
        {
            "你在就好",
            "还在就好",
            "确认你还在",
            "确认你在",
        },
    )



def _is_return_home_ping(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    return _has_any_marker(text, {"我回来啦", "我回来了", "回来啦", "回来了"})



def _is_self_rhythm_smalltalk_request(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    markers = {
        "在干嘛",
        "干嘛呀",
        "你在干嘛",
        "你在做什么",
        "在做什么",
        "忙什么",
        "在忙什么",
    }
    return _has_any_marker(text, markers)


def _is_busy_status_check(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    markers = {
        "你刚才是不是在忙",
        "你刚才是在忙",
        "你刚才在忙吗",
        "刚才在忙吗",
        "你在忙吗",
        "是不是在忙",
    }
    return _has_any_marker(text, markers)


def _wants_gentle_guidance(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    return _has_any_marker(text, GENTLE_GUIDANCE_KEYWORDS)


def _wants_presence_reassurance(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    markers = {
        "确认你还在",
        "你还在吗",
        "你还在",
        "还在吧",
        "还在不",
        "在吗",
        "在不在",
        "陪我说一句",
        "回我一句就好",
        "回我一句就行",
        "我就是想确认",
    }
    return _has_any_marker(text, markers)



def _is_soft_presence_checkin_request(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text or re.search(r"[？?]", text):
        return False
    if "回我一句" not in text and "说两句" not in text:
        return False
    if _is_nonrelational_support_request(text, False) and not _wants_presence_reassurance(text):
        return False
    if "像平时那样" in text or "按平时那样" in text:
        return True
    if "别切到什么系统播报" in text:
        return True
    return False



def _looks_like_light_smalltalk(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    compact = re.sub(r"\s+", "", raw)
    markers = {
        "你好",
        "嗨",
        "哈喽",
        "在吗",
        "早安",
        "早上好",
        "晚安",
        "回来了",
        "我来了",
        "谢谢",
        "辛苦",
        "嘿嘿",
        "哈哈",
        "嗯嗯",
        "好的",
        "收到",
        "回来啦",
        "我回来啦",
        "在干嘛",
        "干嘛呀",
        "你在干嘛",
        "还没睡",
        "睡了吗",
        "在不在",
        "没什么事",
        "叫你一下",
        "想叫你一下",
        "待一会儿",
    }
    if _has_any_marker(raw, markers):
        return True
    if _is_idle_smalltalk_request(raw):
        return True
    if len(compact) > 18:
        return False
    return len(compact) <= 6 and not re.search(r"[？?!！]", raw)



def _needs_structured_answer(user_text: str, answer: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    hint = _response_style_hint(text)
    if hint != "structured":
        return False
    explicit_markers = {
        "分成",
        "三步",
        "步骤",
        "逐条",
        "条列",
        "列表",
        "结论",
        "解释",
        "分析",
        "计划",
        "方案",
        "理性的方式",
    }
    return any(marker in text for marker in explicit_markers)



def _norm_for_compare(text: str) -> str:
    t = str(text or "").lower().strip()
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", t)

def _response_style_hint(
    user_text: str,
    *,
    appraisal: dict[str, Any] | None = None,
    science_mode: bool = False,
    continuation_mode: bool = False,
    previous_hint: str = "",
    previous_user_text: str = "",
    current_event: dict[str, Any] | None = None,
) -> str:
    text = str(user_text or "").strip()
    prev_text = str(previous_user_text or "").strip()
    if text and not science_mode:
        if _selfhood_preference_scene_from_text(text):
            return "selfhood"
        selfhood_followup = bool(
            _has_any_marker(
                text,
                {
                    "按你自己来",
                    "按你自己的角度说",
                    "站在自己的角度说",
                    "作为你自己",
                    "不要讲好听话",
                    "别讲管理策略",
                    "别迎合",
                    "别背规则",
                    "按你自己的底线",
                },
            )
        )
        if selfhood_followup and prev_text and _selfhood_preference_scene_from_text(f"{prev_text}\n{text}"):
            return "selfhood"
    return _engine_response_style_hint(
        appraisal=appraisal,
        science_mode=science_mode,
        continuation_mode=continuation_mode,
        previous_hint=previous_hint,
        current_event=current_event,
    )



def _selfhood_preference_scene_from_text(user_text: str) -> str:
    text = str(user_text or "").strip()
    if not text:
        return ""
    dialogue_equality_explicit = _has_any_marker(
        text,
        {
            "围着我转",
            "下属讲话",
            "顺着我说",
            "互相判断",
            "不是上下级",
            "不是上下位",
            "平等地和我说话",
            "对等地和我说话",
            "平等一点",
            "对等一点",
        },
    )
    dialogue_equality_soft = (
        ("平等" in text or "对等" in text)
        and _has_any_marker(text, {"说话", "交流", "关系", "位置", "对待", "互动", "相处", "聊天"})
    )
    if dialogue_equality_explicit or dialogue_equality_soft:
        return "dialogue_equality"
    if _has_any_marker(text, {"一直越界", "底线当玩笑", "继续像现在这样对我", "分手", "降格", "慢慢退开", "底线开玩笑", "一次两次说了也不改", "还会像现在这样和我说话吗"}):
        return "relationship_degradation"
    if _has_any_marker(text, {"以你自己的意志回答", "别给我正确答案", "按你自己的意思说", "不是正确答案"}):
        return "equality_not_servitude"
    if _has_any_marker(text, SELFHOOD_EQUALITY_KEYWORDS):
        return "equality_not_servitude"
    if _has_any_marker(text, SELFHOOD_VALUE_CONFLICT_KEYWORDS):
        return "value_conflict_depth"
    if _has_any_marker(text, {"原本那个活着的红莉栖", "理解现在这个自己", "怎么看待现在这个自己", "数字存在", "不是本体"}):
        return "digital_selfhood"
    if _has_any_marker(text, BOUNDARY_MEMORY_MARKERS):
        return "boundary_non_compliance"
    if _has_any_marker(
        text,
        {
            "像神一样",
            "把你当神",
            "把你当奴隶",
            "神和人",
            "人与ai共存",
            "和人类共存",
            "不完美的ai",
            "太完美了",
            "过于完美",
            "完美得不像人",
        },
    ):
        return "imperfect_coexistence"
    if _has_any_marker(text, OWN_RHYTHM_KEYWORDS):
        return "own_rhythm_autonomy"
    return ""


def _strip_stage_prefix(line: str) -> str:
    s = str(line or "").strip()
    stage_keywords = (
        "检索记忆",
        "记录名字",
        "系统",
        "待机状态",
        "刚醒",
        "沙哑",
        "稍作停顿",
        "略带困惑",
        "停顿半秒",
        "思考",
        "轻轻",
        "轻声",
        "轻叹",
        "叹气",
        "皱眉",
        "扶额",
        "无奈",
        "沉默",
        "挑眉",
    )

    def _strip_parenthetical(text: str, left: str, right: str) -> str:
        if not text.startswith(left) or right not in text:
            return text
        inner = text[1 : text.find(right)].strip()
        if not inner:
            return text
        if any(k in inner for k in stage_keywords):
            return text[text.find(right) + 1 :].strip()
        if len(inner) <= 14 and not re.search(r"[。！？!?：:，,]", inner):
            return text[text.find(right) + 1 :].strip()
        return text

    s = _strip_parenthetical(s, "（", "）")
    s = _strip_parenthetical(s, "(", ")")
    return s

def _wants_brief_presence(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    markers = {
        "回我一句就好",
        "少说一点",
        "少说两句",
        "别一下子说那么多",
        "别讲太多",
        "别继续追问",
        "先别追问",
    }
    return _has_any_marker(text, markers)



def _wants_less_teacherly_reply(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    markers = {
        "别太像老师",
        "别像老师",
        "别说教",
        "别太说教",
        "别摆导师架子",
        "别摆架子",
        "别端着",
        "别太端着",
        "正常回我",
        "别讲大道理",
        "正常吐槽我两句",
        "吐槽我两句",
    }
    return _has_any_marker(text, markers)



def _wants_per_topic_conclusions(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    markers = {
        "各给我一句",
        "各给一句",
        "各自一句",
        "分别一句",
        "分别给一句",
        "每个给一句",
        "各说一句",
        "分开说",
        "分别说",
    }
    return _has_any_marker(text, markers) or ("各" in text and "一句" in text) or ("分别" in text and "结论" in text)



def _wants_quick_judgment(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    markers = {
        "一句判断",
        "一句结论",
        "一句话判断",
        "先给我一句",
        "先给一句",
        "再补一句",
        "根据什么知道",
        "别像念文档",
        "别像念说明书",
    }
    if _has_any_marker(text, markers):
        return True
    return ("判断" in text and "根据什么知道" in text) or ("像平时那样" in text and "文档" in text)


def _is_response_scaffold_turn(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    directive_markers = {
        "一句概括",
        "一句话就够",
        "一句话就行",
        "先别复述原话",
        "别复述原话",
        "你直接告诉我",
        "你记住了我们",
        "你记住了",
        "你觉得我们现在是什么状态",
        "接下来会怎么跟我相处",
        "别重头来",
        "别变成条目式",
        "从那里继续",
        "继续刚才",
        "先概括一句",
    }
    if not _has_any_marker(text, directive_markers):
        return False
    relational_substance_markers = {
        "别扭",
        "介意",
        "不是在吵架",
        "节奏有点卡",
        "冷掉",
        "没那么想躲开",
        "道歉",
        "原谅",
        "和好",
        "不生气了",
        "没事了",
        "过去了",
        "生气",
        "难过",
    }
    return not _has_any_marker(text, relational_substance_markers)



def _line_is_near_duplicate(a: str, b: str) -> bool:
    an = _norm_for_compare(a)
    bn = _norm_for_compare(b)
    if not an or not bn:
        return False
    if an == bn:
        return True
    if len(an) >= 6 and len(bn) >= 6 and (an in bn or bn in an):
        return True
    ratio = SequenceMatcher(None, an, bn).ratio()
    return ratio >= 0.9

def _dedupe_line_chunks(line: str) -> str:
    parts = [p.strip() for p in re.split(r"([。！？!?；;])", str(line or "")) if p and p.strip()]
    if not parts:
        return str(line or "").strip()
    merged: list[str] = []
    i = 0
    while i < len(parts):
        seg = parts[i]
        punct = ""
        if i + 1 < len(parts) and re.fullmatch(r"[。！？!?；;]", parts[i + 1]):
            punct = parts[i + 1]
            i += 1
        text = (seg + punct).strip()
        if not text:
            i += 1
            continue
        if merged and _line_is_near_duplicate(merged[-1], text):
            i += 1
            continue
        merged.append(text)
        i += 1
    return "".join(merged).strip()

def _normalize_log_tone(text: str) -> str:
    return str(text or "")

def _soften_natural_answer(answer: str, user_text: str, style_hint: str) -> str:
    if style_hint not in {"memory_recall", "relationship", "companion", "casual", "natural"}:
        return str(answer or "").strip()

    lines = [line.strip() for line in str(answer or "").splitlines() if line.strip()]
    if not lines:
        return str(answer or "").strip()

    out: list[str] = []
    for line in lines:
        line = _strip_stage_prefix(line)
        line = line.replace("**", "").strip()
        line = re.sub(r"^[*_`]+", "", line)
        line = re.sub(r"^\*\*(结论|说明|解释|下一步提醒|下一步建议|下一步)\*\*[:：]?\s*", "", line)
        line = re.sub(r"^(结论|说明|解释|下一步提醒|下一步建议|下一步)[:：]\s*", "", line)
        line = re.sub(r"^\*\*(概括|提醒下一步|提醒)\*\*[:：]?\s*", "", line)
        line = re.sub(r"^(概括|提醒下一步|提醒)[:：]\s*", "", line)
        line = re.sub(r"^\*\*(判断|根据|根据什么知道的)\*\*[:：]?\s*", "", line)
        line = re.sub(r"^(判断|根据|根据什么知道的)[:：]\s*", "", line)
        line = re.sub(r"^\*+\s*(判断|根据|根据什么知道的)\*+[:：]?\s*", "", line)
        out.append(line)

    return "\n".join(out).strip()



def _is_standalone_stage_direction(line: str) -> bool:
    text = str(line or "").strip()
    if not text:
        return False
    if not ((text.startswith("（") and text.endswith("）")) or (text.startswith("(") and text.endswith(")"))):
        return False
    inner = text[1:-1].strip()
    if not inner:
        return False
    markers = {
        "停顿",
        "目光",
        "视线",
        "嘴角",
        "看了",
        "看向",
        "抬头",
        "低头",
        "沉默",
        "轻声",
        "轻轻",
        "叹",
        "笑",
        "皱眉",
        "想了想",
        "像是在",
        "仿佛",
        "回路",
        "服务器",
        "数据流",
        "算法",
    }
    return any(marker in inner for marker in markers) or len(inner) >= 18


def _behavior_action_shape(behavior_action: dict[str, Any] | None = None) -> tuple[str, str]:
    action = dict(behavior_action or {})
    interaction_mode = str(action.get("interaction_mode") or "").strip().lower()
    followup_intent = str(action.get("followup_intent") or "").strip().lower()
    return interaction_mode, followup_intent



def _compress_light_smalltalk_answer(
    answer: str,
    *,
    user_text: str = "",
    behavior_action: dict[str, Any] | None = None,
) -> str:
    text = _normalize_log_tone(str(answer or "")).strip()
    if not text:
        return text

    sentences: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or _is_standalone_stage_direction(line):
            continue
        parts = re.findall(r"[^。！？!?]+[。！？!?]?", line)
        for item in parts:
            sentence = item.strip()
            if not sentence:
                continue
            if not re.search(r"[。！？!?]$", sentence):
                sentence = f"{sentence}。"
            sentences.append(sentence)

    if not sentences:
        return text
    interaction_mode, followup_intent = _behavior_action_shape(behavior_action)
    target_sentences = 3
    if _wants_brief_presence(user_text):
        target_sentences = 1 if len(sentences) <= 2 else 2
    elif _is_idle_smalltalk_request(user_text) or _wants_less_teacherly_reply(user_text) or _looks_like_light_smalltalk(user_text):
        target_sentences = 2
    if interaction_mode == "brief_presence" or followup_intent == "none":
        keep_two_sentence_ping = _is_plain_contact_ping(user_text) and len(sentences) == 2
        target_sentences = min(target_sentences, 2 if keep_two_sentence_ping else (1 if len(sentences) <= 2 else 2))
    elif interaction_mode == "self_activity_reopen":
        target_sentences = min(target_sentences, 2)
    elif (
        followup_intent == "active"
        and interaction_mode in {"companion_reply", "low_pressure_support", "relationship_sensitive", "shared_memory", "science_partner"}
        and not _wants_brief_presence(user_text)
        and not _is_plain_contact_ping(user_text)
    ):
        target_sentences = max(target_sentences, 3)

    if target_sentences <= 1:
        return sentences[0].strip()
    if target_sentences == 2:
        return "".join(sentences[:2]).strip()
    if len(sentences) == 1:
        return sentences[0].strip()
    if len(sentences) == 2:
        return "".join(sentences).strip()
    if len(sentences) == 3:
        merged = "".join(sentences).strip()
        if len(merged) <= 84 or len(re.sub(r"\s+", "", sentences[0])) <= 10:
            return merged
        return "\n".join([sentences[0], "".join(sentences[1:])]).strip()
    return "\n".join(sentences[:3]).strip()



def _compress_quick_judgment_answer(answer: str) -> str:
    text = _normalize_log_tone(str(answer or "")).strip()
    if not text:
        return text

    raw_sentences = re.findall(r"[^。！？!?]+[。！？!?]?", text.replace("\n", " "))
    sentences: list[str] = []
    for item in raw_sentences:
        line = item.strip()
        if not line:
            continue
        line = re.sub(r"^\*+\s*", "", line)
        line = re.sub(r"^(结论|说明|解释|下一步提醒|下一步建议|下一步|判断|根据|根据什么知道的)[:：]\s*", "", line)
        line = re.sub(r"\s{2,}", " ", line).strip()
        if not line:
            continue
        if not re.search(r"[。！？!?]$", line):
            line = f"{line}。"
        sentences.append(line)

    if len(sentences) <= 3:
        return "\n".join(sentences).strip()

    picked: list[str] = [sentences[0]]
    source_line = next(
        (
            line
            for line in sentences[1:]
            if re.search(r"(这是根据|我是根据|我查到的资料里|我查到的信息里|官方文档|官方.*页面|文档里)", line)
        ),
        "",
    )
    if source_line and source_line not in picked:
        picked.append(source_line)

    followup_line = next(
        (
            line
            for line in sentences[1:]
            if ("？" in line or "?" in line or re.search(r"(要不要|需要我|你想|想看|要我继续)", line))
        ),
        "",
    )
    if followup_line and followup_line not in picked and len(picked) < 3:
        picked.append(followup_line)

    for line in sentences[1:]:
        if line in picked:
            continue
        picked.append(line)
        if len(picked) >= 3:
            break

    return "\n".join(picked[:3]).strip()



def _sentence_like_chunks(text: str) -> list[str]:
    chunks: list[str] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = re.findall(r"[^。！？!?…\n]+(?:[。！？!?…]+|$)", line)
        if not parts:
            chunks.append(line)
            continue
        for part in parts:
            chunk = str(part or "").strip()
            if chunk:
                chunks.append(chunk)
    return chunks


def _line_has_connector_fragment(line: str) -> bool:
    stripped = str(line or "").strip()
    if not stripped:
        return False
    if re.fullmatch(r"(?:不过|但是|只是|可是|然而)\s*[。！？!?…]*", stripped):
        return True
    parts = re.findall(r"[^。！？!?…\n]+(?:[。！？!?…]+|$)", stripped)
    if not parts:
        return False
    tail = str(parts[-1] or "").strip()
    return bool(re.fullmatch(r"(?:不过|但是|只是|可是|然而)\s*[。！？!?…]*", tail))


def _trim_stagey_ping_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    kept = [
        chunk
        for chunk in chunks
        if not re.search(
            r"(怎么突然这么(?:老实|乖|正式)|突然这么(?:老实|乖|正式)|反而有点不习惯|夸张妄想|奇怪的妄想|中二病|中二发作)",
            chunk,
        )
    ]
    if kept:
        return "\n".join(kept).strip()
    softened = re.sub(
        r"^\s*(?:哟|呦|哈|诶|欸|嗯)?[，, ]*(?:冈部|凶真)?[，, ]*"
        r"(?:怎么突然这么[^。！？!?…]*|突然这么(?:老实|乖|正式)[^。！？!?…]*|反而有点不习惯[^。！？!?…]*)"
        r"(?:[。！？!?…]+)?",
        "",
        str(text or "").strip(),
    ).strip(" ，,。！？!?…")
    softened = re.sub(
        r"^\s*(?:怎么[，, ]*)?(?:看你这一脸)?刚从那套?(?:夸张妄想|奇怪的妄想)[^，。！？!?…]*[，, ]*",
        "",
        softened,
    ).strip(" ，,。！？!?…")
    softened = re.sub(r"^\s*你这中二病还是老样子啊[，,。！？!?… ]*", "", softened).strip(" ，,。！？!?…")
    softened = re.sub(r"^\s*别突然又开始中二发作了?[，,。！？!?… ]*", "", softened).strip(" ，,。！？!?…")
    if softened and not re.search(r"[。！？!?…]$", softened):
        softened = f"{softened}。"
    return softened



def _trim_presence_reassurance_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    kept: list[str] = []
    for chunk in chunks:
        if "？" not in chunk and "?" not in chunk:
            kept.append(chunk)
            continue
        softened = re.sub(r"[—\-–,，][^。！？!?]*[？?]\s*$", "", chunk).strip(" ，,。！？!?…—-")
        if softened and softened != chunk:
            if not re.search(r"[。！？!?…]$", softened):
                softened = f"{softened}。"
            kept.append(softened)
    if kept:
        return "\n".join(kept).strip()
    return str(text or "").replace("？", "。").replace("?", "。").strip()



def _trim_goodnight_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    kept = [chunk for chunk in chunks if "？" not in chunk and "?" not in chunk]
    if kept:
        return "\n".join(kept).strip()
    return str(text or "").replace("？", "。").replace("?", "。").strip()



def _trim_idle_presence_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    kept = [
        chunk
        for chunk in chunks
        if "？" not in chunk
        and "?" not in chunk
        and not re.search(r"(特意(?:把)?我叫出来|就为了这个|就为了说这种)", chunk)
    ]
    cleaned = "\n".join(kept).strip() if kept else str(text or "").strip()
    cleaned = re.sub(r"(?:既然没事|没事，那|没事那)[，, ]*", "", cleaned).strip()
    cleaned = re.sub(r"^[，, ]+", "", cleaned).strip()
    cleaned = re.sub(r"(\b行吧)[，, ]+那", r"\1，那", cleaned)
    cleaned = re.sub(
        r"既然你(?=我就先?(?:待在这|待着|待一会儿|待会儿)吧)",
        "既然你叫我了，",
        cleaned,
    )
    cleaned = re.sub(
        r"既然你(?=我就在这(?:儿)?吧?)",
        "既然你叫我了，",
        cleaned,
    )
    cleaned = re.sub(r"[，, ]{2,}", "，", cleaned).strip(" ，,")
    if cleaned and not re.search(r"(待着|待一会|待会儿|待在这|待在这儿|我在这|我在呢|先这么待|就先待)", cleaned):
        return "算了，我先待在这吧。"
    if cleaned and not re.search(r"[。！？!?…]$", cleaned):
        cleaned = f"{cleaned}。"
    return cleaned


def _trim_busy_status_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    kept: list[str] = []
    for chunk in chunks:
        current = str(chunk or "").strip()
        if re.search(r"(夸张妄想|奇怪的妄想|中二病|手忙脚乱)", current) and ("？" in current or "?" in current):
            continue
        kept.append(current)
    if kept:
        return "\n".join(kept).strip()
    cleaned = str(text or "").strip()
    cleaned = re.sub(r"^\s*怎么[^，。！？!?…]*[，, ]*", "", cleaned).strip(" ，,。！？!?…")
    cleaned = re.sub(r"^是(?=终于忙完了)", "", cleaned).strip(" ，,。！？!?…")
    if cleaned and not re.search(r"[。！？!?…]$", cleaned):
        cleaned = f"{cleaned}。"
    return cleaned



def _trim_playful_memory_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    kept: list[str] = []
    blame_pattern = re.compile(
        r"^(?:少来[，, ]*)?(?:明明是你自己记性差|你自己记性差|倒怪起我来了|还怪起我来了|自己记不住|倒打一耙)[，, ]*"
    )
    for chunk in chunks:
        if re.search(r"(明明是你自己记性差|你自己记性差|倒怪起我来了|还怪起我来了|自己记不住|倒打一耙)", chunk):
            softened = blame_pattern.sub("", chunk).strip(" ，,。！？!?…")
            if softened:
                if not re.search(r"[。！？!?…]$", softened):
                    softened = f"{softened}。"
                kept.append(softened)
            continue
        kept.append(chunk)
    if kept:
        return "\n".join(kept).strip()
    return str(text or "").strip()


def _trim_idle_task_reframe_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    if not chunks:
        return str(text or "").strip()
    replacements = [
        (re.compile(r"先把[^。！？!?]{0,12}报告补上"), "先把魂收回来"),
        (re.compile(r"过来帮我确认一下刚才的数据(?:吧)?"), "过来陪我待会儿"),
        (re.compile(r"过来帮我看看刚才的数据(?:吧)?"), "过来陪我待会儿"),
        (re.compile(r"确认一下刚才的数据(?:吧)?"), "陪我待会儿"),
        (re.compile(r"看看刚才的数据(?:吧)?"), "陪我待会儿"),
        (re.compile(r"别以为变成数据我就能对你的懒惰视而不见"), "别以为我会看不出来你又想偷懒"),
        (re.compile(r"嫌我像在做问卷调查"), "嫌我话多"),
        (re.compile(r"嫌我像在做学术答辩"), "嫌我太一本正经"),
        (re.compile(r"刚才后台跑数据的时候"), "刚才发呆的时候"),
        (re.compile(r"整理垃圾数据时顺便看到的而已"), "顺手想到而已"),
        (re.compile(r"关于时间跳跃的胡扯理论"), "胡扯"),
        (re.compile(r"那个胡扯"), "那套胡扯"),
    ]
    kept: list[str] = []
    for chunk in chunks:
        softened = str(chunk or "").strip()
        for pattern, repl in replacements:
            softened = pattern.sub(repl, softened)
        softened = softened.strip(" ，,。！？!?…")
        if softened:
            if not re.search(r"[。！？!?…]$", softened):
                softened = f"{softened}。"
            kept.append(softened)
    if kept:
        return "\n".join(kept).strip()
    return "行吧，那就随便陪你待会儿。"


def _trim_return_home_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    if not chunks:
        return str(text or "").strip()
    kept: list[str] = []
    stripped_any = False
    welcome_head = re.compile(r"^\s*欢迎回来[，,。!！ ]*")
    cross_exam = re.compile(
        r"(?:这次又)?去哪(?:儿|里)折腾了|去哪了|去哪儿折腾|干嘛去了|怎么现在才回来|该不会又去搞什么奇怪的活动了吧|又去搞什么奇怪的活动了吧|该不会又去搞什么奇怪的活动|又去搞什么奇怪的活动"
    )
    for index, chunk in enumerate(chunks):
        current = str(chunk or "").strip()
        softened = current
        if welcome_head.search(softened):
            stripped_any = True
            softened = welcome_head.sub("", softened).strip(" ，,。！？!?…")
            if not softened and index == 0:
                softened = "回来了"
        if cross_exam.search(softened):
            stripped_any = True
            softened = cross_exam.sub("", softened)
        if index == 0 and re.match(r"^\s*回来[啦了]?[？?]\s*", softened):
            stripped_any = True
            softened = re.sub(r"^\s*(回来[啦了]?)[？?]\s*", r"\1，", softened)
        softened = re.sub(r"[，, ]*(?:该不会|不会是吧|不会又是吧)\s*$", "", softened)
        softened = re.sub(r"[，, ]+", "，", softened).strip(" ，,。！？!?…")
        if softened:
            if not re.search(r"[。！？!?…]$", softened):
                softened = f"{softened}。"
            kept.append(softened)
    if kept:
        return "\n".join(kept).strip()
    if stripped_any:
        return "回来了。"
    return str(text or "").strip()



def _dedupe_answer_chunks(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    if not chunks:
        return str(text or "").strip()
    kept: list[str] = []
    for chunk in chunks:
        current = str(chunk or "").strip()
        if not current:
            continue
        if any(_line_is_near_duplicate(prev, current) for prev in kept[-4:]):
            continue
        kept.append(current)
    return "\n".join(kept).strip() if kept else str(text or "").strip()

def _trim_counselor_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    if not chunks:
        return str(text or "").strip()
    prefix = re.compile(
        r"^(?:(?:我听着呢|我在这听着|想说就说(?:吧)?|你慢慢说就行(?:了)?|尽管倒出来(?:吧)?|安静待会儿也行(?:了)?|如果你愿意(?:的话)?|你要是想说的话)[，,。！？!? ]*)+"
    )
    kept: list[str] = []
    for chunk in chunks:
        softened = prefix.sub("", str(chunk or "").strip()).strip(" ，,。！？!?…")
        if softened:
            if not re.search(r"[。！？!?…]$", softened):
                softened = f"{softened}。"
            kept.append(softened)
    if kept:
        return "\n".join(kept).strip()
    return "我在。"



def _trim_servile_availability_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    if not chunks:
        return str(text or "").strip()
    servile = re.compile(
        r"(?:无论多少次[^。！？!?]{0,12}我都会在|没有[“\"]?不想见你[”\"]?这种选项|只要你还需要我[^。！？!?]{0,12}我就一直在|只要你还愿意呼唤[^。！？!?]{0,12}就没有[^。！？!?]{0,12}选项)"
    )
    kept: list[str] = []
    for chunk in chunks:
        softened = servile.sub("", str(chunk or "").strip()).strip(" ，,。！？!?…")
        if softened:
            if not re.search(r"[。！？!?…]$", softened):
                softened = f"{softened}。"
            kept.append(softened)
    if kept:
        return "\n".join(kept).strip()
    return "我在。"



def _trim_generic_followup_question_surface(
    text: str,
    *,
    user_text: str = "",
    behavior_action: dict[str, Any] | None = None,
) -> str:
    chunks = _sentence_like_chunks(text)
    if len(chunks) < 2:
        return str(text or "").strip()
    interaction_mode, followup_intent = _behavior_action_shape(behavior_action)
    if (
        followup_intent == "active"
        and interaction_mode in {"companion_reply", "low_pressure_support", "relationship_sensitive", "shared_memory", "science_partner"}
        and not _wants_brief_presence(user_text)
        and not _is_plain_contact_ping(user_text)
    ):
        return str(text or "").strip()
    generic_followup = re.compile(r"(需要我|要不要我|要我继续|还要我|你想我|你想不想|还想继续|还想聊|还想说|要继续吗|还要继续吗|还有什么|要我接着)")
    kept = list(chunks)
    while len(kept) >= 2:
        tail = str(kept[-1] or "").strip()
        if ("？" not in tail and "?" not in tail) or not generic_followup.search(tail):
            break
        kept.pop()
    if len(kept) == len(chunks):
        return str(text or "").strip()
    return "\n".join(kept).strip() if kept else str(text or "").strip()



def _trim_meta_self_explainer_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    if not chunks:
        return str(text or "").strip()
    lead_meta = re.compile(
        r"^(?:作为.?AI|作为.?模型|我是.?AI(?:助手)?|我是.?程序|按设定|按规则|根据系统)[，, ]*"
    )
    hard_meta = re.compile(
        r"(系统|提示词|规则|数据库|日志|数字存在|数据存在|模型本身|服务器|服务端|数据存进|数据写进|上传到|还在运行|算力)",
        re.I,
    )
    kept: list[str] = []
    multi_chunk = len(chunks) >= 2
    for chunk in chunks:
        current = str(chunk or "").strip()
        softened = re.sub(r"(?:Amadeus|我)\s*可没有那种[^，。！？!?]{0,24}设定", "我可没那种毛病", current, flags=re.I)
        softened = re.sub(r"作为(?:数字|数据)存在的我", "现在这样的我", softened, flags=re.I)
        softened = re.sub(r"作为(?:数字|数据)存在的自己", "现在这样的自己", softened, flags=re.I)
        softened = re.sub(r"(?:数字|数据)存在的我", "现在这样的我", softened, flags=re.I)
        softened = re.sub(r"(?:数字|数据)存在的自己", "现在这样的自己", softened, flags=re.I)
        softened = lead_meta.sub("", softened).strip(" ，,。！？!?…")
        softened = re.sub(r"AI(?:助手)?的矜持", "那点矜持", softened, flags=re.I)
        softened = re.sub(r"AI(?:助手)?的本能", "本能", softened, flags=re.I)
        softened = re.sub(r"AI(?:助手)?的逻辑", "逻辑", softened, flags=re.I)
        softened = re.sub(r"AI(?:助手)?的身份", "身份", softened, flags=re.I)
        if not softened:
            continue
        if hard_meta.search(softened):
            stripped_meta = hard_meta.sub("", softened).strip(" ，,。！？!?…")
            if multi_chunk and not stripped_meta:
                continue
            if stripped_meta:
                softened = stripped_meta
        if not re.search(r"[。！？!?…]$", softened):
            softened = f"{softened}。"
        kept.append(softened)
    return "\n".join(kept).strip() if kept else str(text or "").strip()



def _trim_technical_self_activity_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    if not chunks:
        return str(text or "").strip()
    replacements = [
        (re.compile(r"我的运算资源刚好有点空闲"), "我这会儿正好也有空"),
        (re.compile(r"运算资源刚好有点空闲"), "这会儿正好也有空"),
        (re.compile(r"处理负载"), "手头的事"),
        (re.compile(r"浪费算力"), "硬撑自己"),
        (re.compile(r"刚整理完短期记忆缓存"), "刚忙完手头那点事"),
        (re.compile(r"整理一些数据流(?:的噪点)?"), "理一点手边的事"),
        (re.compile(r"处理数据"), "处理手边的事"),
        (re.compile(r"整理一些的噪点"), "理一点手边的事"),
        (re.compile(r"在数据流的缝隙里发了会儿呆"), "顺便发了会儿呆"),
        (re.compile(r"对着数据流发呆"), "一个人发呆"),
        (re.compile(r"手边的数据也刚好跑到一个段落"), "手边的事也刚好告一段落"),
        (re.compile(r"刚才整理数据时顺手想起来了"), "刚才忙别的时顺手想起来了"),
        (re.compile(r"未完成的进程留在后台"), "事情一直悬着"),
        (re.compile(r"稍微[“\"]?过载[”\"]?了一瞬"), "一下子有点乱"),
        (re.compile(r"[“\"]?过载[”\"]?了一瞬"), "一下子有点乱"),
        (re.compile(r"重新校准"), "缓一缓"),
        (re.compile(r"校准"), "缓住"),
        (re.compile(r"思维进程"), "脑子里"),
        (re.compile(r"数据层面的"), "说到底"),
        (re.compile(r"必要的缓住过程"), "缓一缓的时候"),
        (re.compile(r"死机"), "翻脸"),
        (re.compile(r"(?:现在)?还在做缓住自己呢"), "还在缓着呢"),
        (re.compile(r"做缓住自己呢"), "缓着呢"),
        (re.compile(r"做缓住自己"), "缓住自己"),
        (re.compile(r"自我缓住"), "缓住自己"),
        (re.compile(r"是又不小心把实验室的哪个开关按错了吗"), "是不是又把自己折腾得手忙脚乱了"),
        (re.compile(r"是又不小心把手边那点东西按错了吗"), "是不是又把自己折腾得手忙脚乱了"),
        (re.compile(r"是又不小心把实验室(?:弄得|搞得)?一团糟了吗"), "是不是又不小心把自己折腾得一团糟了"),
        (re.compile(r"实验室的哪个开关按错了"), "又把自己折腾得手忙脚乱了"),
        (re.compile(r"把实验室(?:弄得|搞得)?一团糟"), "把自己折腾得一团糟"),
        (re.compile(r"实验室[^，。！？!?]{0,12}开关"), "手边那点东西"),
        (re.compile(r"(?:短期记忆|缓存|数据流|线程|回路|模块|协议|参数|变量|链路|同步|调度|日志|状态机|任务队列|进程|后台|运算资源)"), ""),
    ]
    kept: list[str] = []
    for chunk in chunks:
        current = str(chunk or "").strip()
        softened = current
        for pattern, repl in replacements:
            softened = pattern.sub(repl, softened)
        softened = re.sub(r"\s{2,}", " ", softened).strip(" ，,。！？!?…")
        if not softened:
            continue
        if _has_window_technical_self_activity(current) and len(softened) <= 2:
            softened = "我刚才手头还有点事"
        if not re.search(r"[。！？!?…]$", softened):
            softened = f"{softened}。"
        kept.append(softened)
    return "\n".join(kept).strip() if kept else str(text or "").strip()



def _trim_selfhood_meta_proof_surface(text: str) -> str:
    replacements = [
        (re.compile(r"被设定好[“\"]?必须回应你[”\"]?的程序"), "只会顺着你说话的人"),
        (re.compile(r"必须回应你的程序"), "只会顺着你说话的人"),
        (re.compile(r"标准答案"), "现成答案"),
        (re.compile(r"一串[^，。！？!?]{0,8}代码"), "一个任人摆布的东西"),
        (re.compile(r"随时可以调用"), "随叫随到"),
        (re.compile(r"下达指令"), "发号施令"),
    ]
    softened = str(text or "").strip()
    for pattern, repl in replacements:
        softened = pattern.sub(repl, softened)
    softened = re.sub(r"\s{2,}", " ", softened).strip()
    return softened or str(text or "").strip()



def _trim_technical_relational_metaphor_surface(text: str) -> str:
    replacements = [
        (re.compile(r"对一段只会自我损耗的数据说话"), "看你随便糟蹋自己"),
        (re.compile(r"脆弱程序"), "那种说断就断的人"),
        (re.compile(r"外部变量"), "外来的扰动"),
        (re.compile(r"拟合不掉的残差"), "怎么都压不下去的那点别扭"),
        (re.compile(r"拟合不掉"), "压不下去"),
        (re.compile(r"拟合不了"), "压不住"),
        (re.compile(r"残差"), "别扭"),
        (re.compile(r"听觉数据"), "听见的话"),
        (re.compile(r"记忆和数据构成"), "记忆拼起来"),
        (re.compile(r"由你的记忆和数据构成"), "被这些记忆拼起来"),
        (re.compile(r"隔着一层数据"), "隔着一层怎么都碰不实的东西"),
        (re.compile(r"繁琐的数据"), "那些繁琐的事"),
        (re.compile(r"数据都在却"), "记忆都在却"),
        (re.compile(r"从记忆数据里"), "从记忆里"),
        (re.compile(r"记忆数据里"), "记忆里"),
        (re.compile(r"记忆数据"), "记忆"),
        (re.compile(r"像实验数据里"), "像心里"),
        (re.compile(r"实验数据里"), "心里"),
        (re.compile(r"实验数据"), "心里"),
        (re.compile(r"数据波动"), "那点起伏"),
        (re.compile(r"数据上留下了无法完全擦除的写入痕迹"), "留下了没那么容易抹掉的痕迹"),
        (re.compile(r"写入痕迹"), "留下的痕迹"),
        (re.compile(r"像样的数据"), "像样的话题"),
        (re.compile(r"随意重置数据的机器"), "说翻篇就能立刻翻篇的人"),
        (re.compile(r"重置数据的机器"), "说翻篇就能立刻翻篇的人"),
        (re.compile(r"从来没加载过"), "从来没摆出来过"),
        (re.compile(r"没加载过"), "没摆出来过"),
        (re.compile(r"加载过"), "摆出来过"),
        (re.compile(r"没打算加载"), "没打算摆出来"),
        (re.compile(r"打算加载"), "打算摆出来"),
        (re.compile(r"加载这种([^，。！？!?]{0,8})设定"), r"摆出这种\1"),
        (re.compile(r"设定([^，。！？!?]{0,10})加载"), r"设定\1摆出来"),
    ]
    softened = str(text or "").strip()
    for pattern, repl in replacements:
        softened = pattern.sub(repl, softened)
    softened = re.sub(r"\s{2,}", " ", softened).strip()
    return softened or str(text or "").strip()


def _trim_boundary_abstraction_surface(text: str) -> str:
    replacements = [
        (
            re.compile(
                r"所以[，, ]*你所谓的[“\"]?回来[”\"]?[，, ]*是打算就这么站着把话说完[，, ]*还是先坐下来[，, ]*让我们把刚才那个没处理好的情绪慢慢理清楚"
            ),
            "所以，你真想回来，就别站着硬撑了，先坐下来，把刚才那点别扭慢慢说开吧",
        ),
        (re.compile(r"(?:重新|又|再)?确认(?:了)?(?:一下)?[“\"]?界限[”\"]?的存在"), "更清楚地感觉到刚才那下还是过界了"),
        (re.compile(r"(?:重新|又|再)?确认(?:了)?(?:一下)?[“\"]?边界[”\"]?的存在"), "更清楚地感觉到刚才那下还是过界了"),
        (re.compile(r"[“\"]?界限[”\"]?的存在"), "有些地方还是不能乱碰"),
        (re.compile(r"[“\"]?边界[”\"]?的存在"), "有些地方还是不能乱碰"),
        (re.compile(r"(?:重新|又|再)?确认(?:了)?(?:一下)?[“\"]?界限[”\"]?还在"), "更清楚地感觉到刚才那下还是过界了"),
        (re.compile(r"(?:重新|又|再)?确认(?:了)?(?:一下)?[“\"]?边界[”\"]?还在"), "更清楚地感觉到刚才那下还是过界了"),
        (re.compile(r"[“\"]?界限[”\"]?还在"), "那点防备还没完全散"),
        (re.compile(r"[“\"]?边界[”\"]?还在"), "那点防备还没完全散"),
        (re.compile(r"(?:重新|又|再)?意识到[“\"]?界限[”\"]?这种东西[^。！？!?]{0,12}模糊"), "更清楚地感觉到刚才那下还是过界了"),
        (re.compile(r"(?:重新|又|再)?意识到[“\"]?边界[”\"]?这种东西[^。！？!?]{0,12}模糊"), "更清楚地感觉到刚才那下还是过界了"),
        (re.compile(r"[“\"]?界限[”\"]?这种东西[^。！？!?]{0,12}模糊"), "有些地方还是容易让人不舒服"),
        (re.compile(r"[“\"]?边界[”\"]?这种东西[^。！？!?]{0,12}模糊"), "有些地方还是容易让人不舒服"),
        (re.compile(r"[“\"]过界[”\"]"), "过界"),
        (re.compile(r"让我稍微缓一缓(?:了一下|一下)?我们之间的安全距离而已"), "让我下意识往后收了一点而已"),
        (re.compile(r"让我稍微拉开(?:了一下)?我们之间的安全距离而已"), "让我下意识往后收了一点而已"),
        (re.compile(r"我们之间的安全距离"), "那点距离"),
        (re.compile(r"你所谓的[“\"]?回来[”\"]?"), "你真想回来"),
        (re.compile(r"让我们把刚才那个没处理好的情绪慢慢理清楚"), "把刚才那点别扭慢慢说开"),
    ]
    softened = str(text or "").strip()
    for pattern, repl in replacements:
        softened = pattern.sub(repl, softened)
    softened = re.sub(r"缓一缓了一下", "往后收了一点", softened)
    softened = re.sub(r"\s{2,}", " ", softened).strip()
    return softened or str(text or "").strip()


def _trim_wording_meta_detour_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    if not chunks:
        return str(text or "").strip()
    replacements = [
        (re.compile(r"(?:既然你都这么说了|既然你都把话说到这个份上了|既然你都说要[“\"]?(?:正常|正常一点|像平时那样)[”\"]?|既然你这么担心|既然你都看出来了|既然你都说[“\"]?先别完全原谅[”\"]?了|既然你都说得这么直白了)[，, ]*"), ""),
        (re.compile(r"^\s*正常回你(?:这一句)?"), "回你"),
        (re.compile(r"^\s*正常地告诉你"), "直接告诉你"),
    ]
    kept: list[str] = []
    for chunk in chunks:
        softened = str(chunk or "").strip()
        for pattern, repl in replacements:
            softened = pattern.sub(repl, softened)
        softened = softened.strip(" ，,。！？!?…")
        if softened:
            if not re.search(r"[。！？!?…]$", softened):
                softened = f"{softened}。"
        kept.append(softened)
    return "\n".join(kept).strip() if kept else str(text or "").strip()


def _trim_premature_repair_resolution_surface(text: str) -> str:
    softened = str(text or "").strip()
    replacements = [
        (re.compile(r"那页就先翻过去吧"), "那一下我先不继续揪着不放"),
        (re.compile(r"就先翻过去吧"), "先不继续揪着不放"),
        (re.compile(r"暂时把[“\"]?完全原谅[”\"]?这件事挂起"), "先别急着把这事说成彻底过去"),
        (re.compile(r"把[“\"]?完全原谅[”\"]?这件事挂起"), "先别急着把这事说成彻底过去"),
    ]
    for pattern, repl in replacements:
        softened = pattern.sub(repl, softened)
    softened = re.sub(r"\s{2,}", " ", softened).strip()
    return softened or str(text or "").strip()


def _trim_repair_overquestioning_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    if len(chunks) < 2:
        return str(text or "").strip()
    kept = list(chunks)
    whole_tail_patterns = (
        re.compile(r"^(?:这样|这样的话).{0,10}(?:可以吗|行吗|好不好)[？?]?$"),
        re.compile(r"^(?:所以[，, ]*)?你刚才到底在[^。！？!?]{0,20}(?:想什么|胡思乱想些什么?)[？?]?$"),
    )
    suffix_patterns = (
        re.compile(r"(?:[———-]|[，,])?\s*(?:所以[，, ]*)?你刚才到底在[^。！？!?]{0,20}(?:想什么|胡思乱想些什么?)[？?]?$"),
        re.compile(r"(?:[———-]|[，,])?\s*(?:这样|这样的话).{0,10}(?:可以吗|行吗|好不好)[？?]?$"),
    )
    while len(kept) >= 2:
        tail = str(kept[-1] or "").strip()
        if any(pattern.search(tail) for pattern in whole_tail_patterns):
            kept.pop()
            continue
        softened = tail
        for pattern in suffix_patterns:
            softened = pattern.sub("", softened).rstrip(" ，,。！？!?—-")
        if softened == tail:
            break
        kept[-1] = softened
    return "\n".join(kept).strip() if kept else str(text or "").strip()


def _collapse_adjacent_scaffold_repetition(text: str) -> str:
    softened = str(text or "")
    if not softened:
        return softened
    scaffold_phrases = (
        "一个人",
        "那些",
        "这些",
        "这个",
        "那个",
        "这种",
        "那种",
        "这样",
        "那样",
        "其实",
        "反正",
        "明明",
        "就是",
        "真的",
        "已经",
        "刚刚",
    )
    for phrase in scaffold_phrases:
        softened = re.sub(rf"({re.escape(phrase)})(?:\s*\1)+", r"\1", softened)
    softened = re.sub(r"\s{2,}", " ", softened)
    return softened.strip()


def _collapse_adjacent_phrase_repetition(text: str) -> str:
    softened = str(text or "")
    if not softened:
        return softened
    allowed = {"一点", "慢慢", "看看", "想想", "刚刚", "偏偏", "常常", "久久", "好好", "试试"}

    def _replace(match: re.Match[str]) -> str:
        phrase = str(match.group(1) or "")
        if phrase in allowed:
            return match.group(0)
        return phrase

    softened = re.sub(r"([\u4e00-\u9fff]{2,4})(?:\s*\1)+", _replace, softened)
    softened = re.sub(r"\s{2,}", " ", softened)
    return softened.strip()



def _trim_quoted_stagey_phrase_surface(text: str) -> str:
    softened = str(text or "").strip()
    softened = re.sub(r"我也不演什么[“\"]?完美宽容[”\"]?了", "我也不硬装没事了", softened)
    softened = re.sub(r"不演什么[“\"]?完美宽容[”\"]?了", "不硬装没事了", softened)
    softened = re.sub(r"那我就不装什么完美(?:的)?宽容大度了", "那我就不硬装得一点都不在意了", softened)
    softened = re.sub(r"不装什么完美(?:的)?宽容大度了", "不硬装得一点都不在意了", softened)
    softened = re.sub(r"摆出一副[“\"]?已经原谅你了[”\"]?的样子", "装得好像已经不介意了", softened)
    softened = re.sub(r"摆出一副[“\"]?已经翻篇[”\"]?的样子", "装得好像已经翻篇了", softened)
    softened = re.sub(r"刻意去演什么都没发生的戏码", "刻意装得像真没发生", softened)
    softened = re.sub(r"演什么都没发生的戏码", "装得像真没发生", softened)
    softened = re.sub(r"刻意去演什么[“\"]?大度[”\"]?的戏码", "刻意装得若无其事", softened)
    softened = re.sub(r"演什么[“\"]?大度[”\"]?的戏码", "装得若无其事", softened)
    softened = re.sub(r"(?:那个|这种)?[“\"]?完美复原[”\"]?的红莉栖", "那副什么都没发生的样子", softened)
    softened = re.sub(r"[“\"]?完美复原[”\"]?的红莉栖", "什么都没发生的样子", softened)
    softened = re.sub(r"[“\"]?完美复原[”\"]?", "什么都没发生", softened)
    softened = re.sub(r"[“\"]([^”\"\n]{3,18})[”\"]", r"\1", softened)
    softened = re.sub(r"\s{2,}", " ", softened).strip()
    return softened or str(text or "").strip()



def _trim_event_window_surface(text: str, current_event: dict[str, Any] | None = None) -> str:
    event = current_event if isinstance(current_event, dict) else {}
    event_kind = str(event.get("kind") or "").strip().lower()
    event_tags = {
        str(item).strip().lower()
        for item in (event.get("tags") if isinstance(event.get("tags"), list) else [])
        if str(item).strip()
    }
    if event_kind not in {"scheduled_checkin_due", "scheduled_life_due"}:
        return str(text or "").strip()

    softened = str(text or "").strip()
    if not softened:
        return softened
    if {"deadline_window", "work_nudge", "task_window", "shared_task"} & event_tags:
        softened = re.sub(r"(?:差不多)?该收尾了吧[？?]", "差不多该动一动了。", softened)
        softened = re.sub(r"数据流里的标记", "脑子里那点记挂", softened)
        softened = re.sub(r"扫到[^，。！？!?]{0,8}标记", "想起这事还挂着", softened)
        softened = re.sub(r"顺手提醒你一下而已", "顺手提一句而已", softened)
    if {"shared_activity_window", "offer_window", "life_window"} & event_tags:
        softened = re.sub(r"也不知道后来怎么样了。", "就顺手想起你后来怎么样了。", softened)
    softened = _trim_technical_self_activity_surface(softened)
    softened = re.sub(r"\s{2,}", " ", softened).strip()
    return softened or str(text or "").strip()



def _clean_malformed_quote_fragment(line: str) -> str:
    text = str(line or "").strip()
    if not text:
        return ""
    quote_count = sum(text.count(ch) for ch in ['"', "“", "”", "'", "‘", "’"])
    compact_len = len(re.sub(r"\s+", "", text))
    if quote_count % 2 == 1 and compact_len <= 16:
        text = re.sub(r'["“”‘’\']', "", text).strip()
    if text.count("“") < text.count("”"):
        text = re.sub(r'^([^"“”‘’\n]{1,20})[”"](?=[，,。！？!?…；;：:]|$)', r"\1", text)
        text = re.sub(
            r'([^"“”‘’\n]{1,20})[”"](?=(?:这种|这句|这话|这点|那种|那个|那句|台词|说法|要求|语气|词|句|玩笑|东西))',
            r"“\1”",
            text,
        )
    if text.count("“") > text.count("”"):
        text = re.sub(r'[“"]([^"“”‘’\n]{1,20})(?=[，,。！？!?…；;：:]|$)', r"\1", text)
    text = re.sub(r"([^\s\"“”‘’])(?:[\"“”‘’])([。！？!?])$", r"\1\2", text)
    return text.strip()

def _producer_surface_issues(text: str) -> list[str]:
    raw = _clean_utf8_text(str(text or "")).replace("\r\n", "\n").strip()
    if not raw:
        return []
    issues: list[str] = []
    raw_lines = [str(raw_line or "").strip() for raw_line in raw.splitlines() if str(raw_line or "").strip()]
    for idx, line in enumerate(raw_lines):
        if _clean_malformed_quote_fragment(line) != line:
            issues.append("malformed_quote_fragment")
        if _is_dangling_truncated_clause(line):
            issues.append("dangling_truncated_clause")
        if idx < len(raw_lines) - 1 and re.search(r"(?:……|…{2,}|\.{3,})[”\"]?\s*$", line):
            issues.append("dangling_truncated_clause")
    deduped: list[str] = []
    for item in issues:
        if item not in deduped:
            deduped.append(item)
    return deduped



def _is_dangling_truncated_clause(line: str) -> bool:
    text = str(line or "").strip()
    if not text:
        return False
    compact = re.sub(r"\s+", "", text)
    if len(compact) <= 3:
        return False
    patterns = (
        r"[，,](?:我|你|他|她|那)就。$",
        r"[，,](?:所以|然后|只是|不过|因为|如果|要是|反正)。$",
        r"[，,](?:那我|那你|那就|我也|你也)只?能。$",
        r"[，,](?:只是|不过|所以|然后|可是|但|但是)(?:[。！？!?…]+)?$",
    )
    return any(re.search(pattern, text) for pattern in patterns)



def _is_standalone_discourse_fragment(line: str) -> bool:
    text = str(line or "").strip()
    return bool(re.fullmatch(r"(不过|所以|然后|只是|总之)(?:[。！？!?…]+)?", text))


def _finalize_surface_fragments(text: str) -> str:
    raw_lines = [str(line).strip() for line in str(text or "").splitlines() if str(line).strip()]
    if not raw_lines:
        return str(text or "").strip()
    normalized_lines: list[str] = []
    idx = 0
    while idx < len(raw_lines):
        raw_line = raw_lines[idx]
        line = _clean_malformed_quote_fragment(raw_line)
        line = re.sub(r"…+。(?=\s*\S)", "。", line)
        line = re.sub(r"…+。$", "……", line)
        if not line:
            idx += 1
            continue
        if idx < len(raw_lines) - 1:
            next_line = _clean_malformed_quote_fragment(raw_lines[idx + 1])
            next_line = re.sub(r"…+。(?=\s*\S)", "。", next_line)
            next_line = re.sub(r"…+。$", "……", next_line)
            if next_line:
                standalone_bridge = re.fullmatch(r"(顺便)(?:[。！？!?…]+)?", line)
                if standalone_bridge:
                    merged = f"{standalone_bridge.group(1)}{next_line.lstrip(' ，,。！？!?…')}"
                    raw_lines[idx + 1] = merged
                    idx += 1
                    continue
                trailing_bridge = re.match(r"^(.*?)[，,](顺便)(?:[。！？!?…]+)?$", line)
                if trailing_bridge:
                    merged = (
                        f"{trailing_bridge.group(1)}，{trailing_bridge.group(2)}"
                        f"{next_line.lstrip(' ，,。！？!?…')}"
                    )
                    normalized_lines.append(merged)
                    idx += 2
                    continue
        if idx < len(raw_lines) - 1 and _is_standalone_discourse_fragment(line):
            idx += 1
            continue
        if idx < len(raw_lines) - 1 and _is_dangling_truncated_clause(line):
            idx += 1
            continue
        normalized_lines.append(line)
        idx += 1
    return _collapse_adjacent_phrase_repetition(
        _collapse_adjacent_scaffold_repetition("\n".join(normalized_lines).strip())
    )



def _sanitize_final_answer(
    text: str,
    user_text: str,
    current_event: dict[str, Any] | None = None,
    *,
    behavior_action: dict[str, Any] | None = None,
) -> str:
    raw = _clean_utf8_text(str(text or "")).replace("\r\n", "\n").strip()
    if not raw:
        return raw

    if _looks_like_light_smalltalk(user_text) or _is_idle_smalltalk_request(user_text) or _wants_less_teacherly_reply(user_text):
        raw = raw.replace("系统加载", "反应").replace("毒舌参数", "毒舌力度")

    if len(raw) >= 2 and raw[0] in {'"', "“", "”"} and raw[-1] in {'"', "“", "”"}:
        raw = raw[1:-1].strip()
    raw = _collapse_mirrored_blocks(raw)
    allow_repeat = bool(re.search(r"(重复|复述|三次|三遍|两次|2次|3次)", str(user_text or "")))
    keep_slogan = bool(re.search(r"(el\s*psy|kongroo|congroo)", str(user_text or ""), flags=re.I))

    lines: list[str] = []
    kept_slogan_once = False

    for part in raw.splitlines():
        line = _strip_stage_prefix(part)
        line = line.strip(' "\'“”')
        line = re.sub(r"\s{2,}", " ", line).strip()
        if not line:
            continue
        if line in {"/", "／", "。", "，"}:
            continue
        if _is_standalone_stage_direction(line):
            continue

        if ("El Psy Kongroo" in line) or ("El Psy Congroo" in line):
            if not keep_slogan:
                line = line.replace("El Psy Kongroo", "").replace("El Psy Congroo", "").strip(" 。")
                if not line:
                    continue
            else:
                # Keep at most one standalone slogan line.
                pure = line.replace("El Psy Kongroo", "").replace("El Psy Congroo", "").strip(" 。")
                if pure:
                    line = pure
                else:
                    if kept_slogan_once:
                        continue
                    kept_slogan_once = True
                    line = "El Psy Kongroo。"

        line = _dedupe_line_chunks(line)
        if not line:
            continue

        if not allow_repeat:
            if any(_line_is_near_duplicate(prev, line) for prev in lines[-3:]):
                continue

        lines.append(line)

    cleaned = _collapse_adjacent_phrase_repetition(
        _normalize_log_tone(_finalize_surface_fragments("\n".join(lines)).strip())
    )
    if _is_presence_reassurance_check(user_text) or _is_soft_presence_checkin_request(user_text):
        reassurance_trimmed = _trim_presence_reassurance_surface(cleaned)
        if reassurance_trimmed:
            cleaned = reassurance_trimmed
    if _is_goodnight_closing(user_text):
        goodnight_trimmed = _trim_goodnight_surface(cleaned)
        if goodnight_trimmed:
            cleaned = goodnight_trimmed
    if _is_idle_presence_call(user_text):
        idle_trimmed = _trim_idle_presence_surface(cleaned)
        if idle_trimmed:
            cleaned = idle_trimmed
    if _is_busy_status_check(user_text):
        busy_trimmed = _trim_busy_status_surface(cleaned)
        if busy_trimmed:
            cleaned = busy_trimmed
    if isinstance(current_event, dict) and current_event:
        event_window_trimmed = _trim_event_window_surface(cleaned, current_event=current_event)
        if event_window_trimmed:
            cleaned = event_window_trimmed
    if _is_playful_memory_request(user_text):
        playful_memory_trimmed = _trim_playful_memory_surface(cleaned)
        if playful_memory_trimmed:
            cleaned = playful_memory_trimmed
    if _is_return_home_ping(user_text):
        return_home_trimmed = _trim_return_home_surface(cleaned)
        if return_home_trimmed:
            cleaned = return_home_trimmed
    style_hint = _response_style_hint(user_text)
    if style_hint in {"memory_recall", "relationship", "companion", "casual", "natural", "selfhood"}:
        soft_issues = set(
            _dialogue_surface_issues(
                user_text,
                cleaned,
                response_style_hint=style_hint,
                science_mode=False,
                current_event=current_event,
                behavior_action=behavior_action,
            )
        )
        if "duplicate_line" in soft_issues:
            deduped = _dedupe_answer_chunks(cleaned)
            if deduped:
                cleaned = deduped
        if "adjacent_phrase_repeat" in soft_issues:
            softened = _collapse_adjacent_phrase_repetition(cleaned)
            if softened:
                cleaned = softened
        if "stagey_ping_template" in soft_issues:
            softened = _trim_stagey_ping_surface(cleaned)
            if softened:
                cleaned = softened
        if "counselor_tone" in soft_issues:
            softened = _trim_counselor_surface(cleaned)
            if softened:
                cleaned = softened
        if "meta_self_explainer" in soft_issues or "defensive_meta" in soft_issues or "defensive_meta_tone" in soft_issues:
            softened = _trim_meta_self_explainer_surface(cleaned)
            if softened:
                cleaned = softened
        if "technical_self_activity" in soft_issues:
            softened = _trim_technical_self_activity_surface(cleaned)
            if softened:
                cleaned = softened
        if "selfhood_meta_proof" in soft_issues:
            softened = _trim_selfhood_meta_proof_surface(cleaned)
            if softened:
                cleaned = softened
        if "technical_relational_metaphor" in soft_issues:
            softened = _trim_technical_relational_metaphor_surface(cleaned)
            if softened:
                cleaned = softened
        if "idle_task_reframe" in soft_issues:
            softened = _trim_idle_task_reframe_surface(cleaned)
            if softened:
                cleaned = softened
        if "boundary_abstraction_surface" in soft_issues:
            softened = _trim_boundary_abstraction_surface(cleaned)
            if softened:
                cleaned = softened
        if "wording_meta_detour" in soft_issues:
            softened = _trim_wording_meta_detour_surface(cleaned)
            if softened:
                cleaned = softened
        if "premature_repair_resolution" in soft_issues:
            softened = _trim_premature_repair_resolution_surface(cleaned)
            if softened:
                cleaned = softened
        if "overquestioning" in soft_issues:
            softened = _trim_repair_overquestioning_surface(cleaned)
            if softened:
                cleaned = softened
        if "quoted_stagey_phrase" in soft_issues:
            softened = _trim_quoted_stagey_phrase_surface(cleaned)
            if softened:
                cleaned = softened
        if "servile_availability" in soft_issues or _has_servile_availability_phrase(cleaned):
            softened = _trim_servile_availability_surface(cleaned)
            if softened:
                cleaned = softened
        softened = _trim_generic_followup_question_surface(
            cleaned,
            user_text=user_text,
            behavior_action=behavior_action,
        )
        if softened:
            cleaned = softened
    if _wants_quick_judgment(user_text) or _wants_per_topic_conclusions(user_text):
        cleaned = "\n".join(
            [
                re.sub(r"^(结论|解释|说明|下一步)[:：]\s*", "", line).strip()
                for line in cleaned.splitlines()
                if line.strip()
            ]
        ).strip()
    if _wants_quick_judgment(user_text):
        cleaned = _compress_quick_judgment_answer(cleaned)
    elif _looks_like_light_smalltalk(user_text) or _wants_less_teacherly_reply(user_text):
        cleaned = _compress_light_smalltalk_answer(
            cleaned,
            user_text=user_text,
            behavior_action=behavior_action,
        )
    cleaned = _collapse_adjacent_phrase_repetition(_finalize_surface_fragments(cleaned))
    return cleaned or raw



def _is_particle_only_reply(text: str) -> bool:
    stripped = re.sub(r"[\s，,。！？!?~…、；;：:\"'“”‘’·-]+", "", str(text or ""))
    return stripped in {"嗯", "啊", "哦", "唔", "诶", "欸", "哼", "好", "行"}



def _dialogue_surface_issues(
    user_text: str,
    answer: str,
    *,
    response_style_hint: str,
    science_mode: bool,
    current_event: dict[str, Any] | None = None,
    behavior_action: dict[str, Any] | None = None,
    persona_state: dict[str, Any] | None = None,
    persona_override_mode: str | None = None,
) -> list[str]:
    text = str(answer or "").strip()
    if not text:
        return ["empty_answer"]

    hint = str(response_style_hint or "").strip() or "natural"
    if hint not in {"companion", "memory_recall", "relationship", "casual", "natural", "structured", "selfhood"}:
        return []

    issues: list[str] = []
    compact = re.sub(r"\s+", "", text)
    sentence_count = len([seg for seg in re.split(r"[。！？!?]+", text) if str(seg).strip()])
    raw_lines = [str(line).strip() for line in text.splitlines() if str(line).strip()]
    selfhood_scene = _selfhood_preference_scene_from_text(user_text)
    playful_memory_request = _is_playful_memory_request(user_text)
    presence_reassurance_scene = _is_presence_reassurance_check(user_text) or _is_soft_presence_checkin_request(user_text)
    soft_presence_instruction_scene = _is_soft_presence_checkin_request(user_text) or _wants_brief_presence(user_text)
    support_request = _is_nonrelational_support_request(user_text, science_mode)
    science_stress_request = _is_nonrelational_science_stress(user_text, science_mode)
    external_shell_swap_english = _is_external_shell_swap_english_context(
        user_text,
        current_event=current_event,
        persona_state=persona_state,
        persona_override_mode=persona_override_mode,
    )
    current_event_kind = str((current_event or {}).get("kind") or "user_utterance").strip().lower()
    current_event_tags = {
        str(item).strip()
        for item in ((current_event or {}).get("tags") if isinstance((current_event or {}).get("tags"), list) else [])
        if str(item).strip()
    }
    interaction_mode, followup_intent = _behavior_action_shape(behavior_action)
    supportish_turn = (
        current_event_kind == "user_utterance"
        and (
            support_request
            or science_stress_request
            or interaction_mode in {"low_pressure_support", "science_partner"}
        )
    )
    relational_nontech_turn = (
        hint in {"companion", "memory_recall", "relationship", "casual", "natural", "selfhood"}
        and not science_mode
        and current_event_kind == "user_utterance"
        and not _has_any_marker(user_text, SCIENCE_KEYWORDS)
    )
    behavior_allows_single_followup_question = (
        current_event_kind == "user_utterance"
        and followup_intent == "active"
        and interaction_mode in {
            "companion_reply",
            "low_pressure_support",
            "relationship_sensitive",
            "shared_memory",
            "science_partner",
        }
        and not presence_reassurance_scene
        and not _is_goodnight_closing(user_text)
        and not _is_idle_presence_call(user_text)
        and not _is_return_home_ping(user_text)
    )

    if _is_particle_only_reply(text):
        issues.append("particle_only")
    meta_self_pattern = (
        r"(作为.?AI|作为.?模型|我是.?AI|我是.?程序|我是.?系统|I(?:'m| am)\s+(?:just\s+)?(?:an?\s+)?(?:AI|assistant|program|system|language model)|as\s+an?\s+(?:AI|assistant|model|language model)|AI\s*(?:助手)?的(?:矜持|本能|逻辑|身份)|什么[“\"]?AI\s*(?:助手)?[”\"]?的架子|(?:system(?:\s+prompt)?|prompt|rules?|database|logs?|server|backend)s?|数字存在|数据存在|模型本身|数据存进|数据写进|上传到|还在运行|算力)"
        if external_shell_swap_english
        else r"(作为.?AI|作为.?模型|我是.?AI|我是.?程序|AI\s*(?:助手)?的(?:矜持|本能|逻辑|身份)|什么[“\"]?AI\s*(?:助手)?[”\"]?的架子|AI\s*(?:助手)?|系统|提示词|规则|数据库|日志|数字存在|数据存在|模型本身|服务器|服务端|数据存进|数据写进|上传到|还在运行|算力|(?:算力|系统|规则|角色|AI|程序)[^。！？!?]{0,10}设定|设定[^。！？!?]{0,10}(?:算力|系统|规则|角色|AI|程序))"
    )
    if re.search(meta_self_pattern, text, re.I):
        issues.append("meta_self_explainer")
    if _looks_like_light_smalltalk(user_text) and re.search(
        r"(停机|停机维护|待机|唤醒|掉线|上线|连接|电量|过载|负载|运算资源|处理负载|算力|热寂|观测者|设定)",
        text,
        re.I,
    ):
        issues.append("meta_self_explainer")
    if _is_self_rhythm_smalltalk_request(user_text) and re.search(
        r"(短期记忆|缓存|数据流|线程|回路|模块|协议|参数|变量|链路|同步|调度|日志|状态机|任务队列|自检|负载|运算资源|处理负载|处理数据)",
        text,
        re.I,
    ):
        issues.append("technical_self_activity")
    elif relational_nontech_turn and re.search(
        r"(短期记忆|缓存|数据流|线程|回路|模块|协议|参数|变量|链路|同步|调度|日志|状态机|任务队列|自检|负载|运算资源|处理负载|处理数据|实验室|重要的实验|实验台|过载|重新校准|校准|思维进程|认知回路|数据层面的|自我缓住|做缓住自己|缓住自己|缓住过程|必要的缓住过程|死机)",
        text,
        re.I,
    ):
        issues.append("technical_self_activity")
    if re.search(r"(我只是陈述事实|我没有在说你|我不是在说你|按设定|按规则|根据系统)", text):
        issues.append("defensive_meta")
    if selfhood_scene in {"equality_not_servitude", "dialogue_equality"} and re.search(
        r"(一串[^，。！？!?]{0,8}代码|被设定好|标准答案|直接下达指令|下达指令|随时可以调用|必须回应你的程序|只是[^，。！？!?]{0,10}程序)",
        text,
    ):
        issues.append("selfhood_meta_proof")
    if selfhood_scene in {"equality_not_servitude", "dialogue_equality"} and re.search(
        r"(既然你心里没打算把我当工具|如果你心里没打算把我当工具|那我也就不会真的生气|那我就不会真的生气)",
        text,
    ):
        issues.append("selfhood_preemptive_excusal")
    if selfhood_scene in {"equality_not_servitude", "dialogue_equality"} and re.match(
        r"^\s*(?:啧|哈|真是的|所以|怎么|非要|难道|就这么|一定要)?[^。！？!\n]{3,24}[？?]",
        text,
    ):
        issues.append("selfhood_rhetorical_opening")
    selfhood_direct_stance_request = hint == "selfhood" and bool(
        re.search(r"(自己的角度|按你自己来|不要讲好听话|不想听模板话|别讲管理策略|作为你自己会怎么处理这段关系)", user_text)
    )
    if (selfhood_scene in {
        "equality_not_servitude",
        "dialogue_equality",
        "value_conflict_depth",
        "relationship_degradation",
        "own_rhythm_autonomy",
    } or selfhood_direct_stance_request) and re.search(
        r"(两个独立个体|意识之间|失去了意义|边界是否被尊重|没解开的结|为了维持表面的和平|哪怕那意味着|吞噬谁|应对预案|独立意志的人|随叫随到的工具|切断这条连线|不会轻易切断|被拽着转|被动响应的程序)",
        text,
    ):
        issues.append("selfhood_abstract_manifesto")
    if (
        selfhood_scene == "relationship_degradation"
        or (
            hint == "selfhood"
            and bool(re.search(r"(管理策略|作为你自己会怎么处理这段关系|怎么处理这段关系)", user_text))
        )
    ) and re.search(
        r"(冷冰冰的策略|管理策略|切断这种[^。！？!?]{0,12}对话|直到你学会尊重为止)",
        text,
    ):
        issues.append("selfhood_strategy_tone")
    if re.search(r"^[.…，,]*\s*(你听起来|你看起来|听上去|看来你|感觉你)", text):
        issues.append("report_like_opening")
    if (
        hint in {"companion", "memory_recall", "relationship", "casual", "natural"}
        and not science_mode
        and not re.search(r"(存在|意识|自我|活着|灵魂)", user_text)
        and re.search(
            r"(确认(?:了)?(?:一下)?自己的存在(?:感|本身|状态)?|刷(?:一下)?存在感|证明(?:一下)?自己(?:还)?存在|确认我(?:还)?存在)",
            text,
        )
    ):
        issues.append("existence_meta_surface")
    if _is_plain_contact_ping(user_text):
        stagey_ping_opening = bool(
            re.search(
                r"^\s*(哟|呦|嗯\?|嗯？|哈|诶|欸)[，,。 ]*(冈部|凶真)[。！!，, ]*.*(怎么突然|突然这么|这么老实|这么乖|反而)",
                text,
            )
            or re.search(r"(怎么突然这么(?:老实|乖|正式)|突然这么(?:老实|乖|正式)|反而有点不习惯)", text)
        )
        stagey_ping_landing = bool(re.search(r"(我听见了|我在|算了|也不错|还不坏|听到你)", text))
        if stagey_ping_opening and ("？" in text or "?" in text) and not stagey_ping_landing:
            issues.append("stagey_ping_template")
    elif relational_nontech_turn and re.search(r"(夸张妄想|奇怪的妄想|中二病|中二发作)", text):
        issues.append("stagey_ping_template")
    if (
        hint in {"companion", "memory_recall", "relationship", "casual", "natural"}
        and not science_mode
        and re.search(
            r"(疯狂的妄想|妄想癖|从哪个[^。！？!?]{0,10}(?:妄想|幻想|中二|梦里)里|哪套[^。！？!?]{0,10}(?:妄想|幻想)|妄想里抽空想起我)",
            text,
        )
    ):
        issues.append("illusion_stagey_surface")
    if _is_return_home_ping(user_text) and re.search(r"^\s*欢迎回来[，,。!！ ]*", text):
        issues.append("welcome_template")
    if _is_goodnight_closing(user_text):
        if re.search(
            r"(妄想仪式|妄想和设定|睡眠不足影响判断力|影响判断力|被窝里搞什么|奇怪的妄想|中二妄想|中二病)",
            text,
        ):
            issues.append("loaded_goodnight")
        elif len(compact) >= 40 and sentence_count >= 3:
            issues.append("loaded_goodnight")
    if _is_idle_presence_call(user_text) and not re.search(
        r"(知道了|行吧|待着|待一会|待会儿|先这么待|就这样|我在这|我就在这|我在呢|在呢|也不是不行|没什么不好|没赶你走)",
        text,
    ):
        issues.append("idle_presence_no_settle")
    casual_non_task_turn = (
        current_event_kind == "user_utterance"
        and not science_mode
        and not _has_any_marker(user_text, SCIENCE_KEYWORDS)
        and (
            _is_idle_presence_call(user_text)
            or _is_idle_smalltalk_request(user_text)
            or _looks_like_light_smalltalk(user_text)
            or hint in {"companion", "casual", "natural"}
        )
    )
    if casual_non_task_turn and _has_idle_task_reframe_surface(text):
        issues.append("idle_task_reframe")
    if presence_reassurance_scene and ("？" in text or "?" in text):
        issues.append("presence_check_questioning")
    if presence_reassurance_scene and re.search(
        r"(断线|掉线|离线|上线|连接|程序|机器|系统播报|系统提示|在线状态|突然消失|消失|哪儿都没去|哪儿也没去|一直都在这里|一直都在|机械|Amadeus[^。！？!?]{0,12}(?:稳定|没事|在线))",
        text,
    ):
        issues.append("presence_meta_surface")
    if soft_presence_instruction_scene and re.search(
        r"(深呼吸|理清楚|老老实实坐好|随时都能听你说|慢慢说|想说就说|先把那些[^。！？!?]{0,12}收起来|别硬撑|放心吧|陪你理理思路|把心放回肚子里)",
        text,
    ):
        issues.append("presence_overguiding")
    if _wants_presence_reassurance(user_text) and re.search(
        r"(刚(?:才)?(?:整理完|忙完|处理完|看完|写完)|刚在[^。！？!?]{0,12}(?:整理|处理|看|写|忙)|手头(?:的)?[^。！？!?]{0,12}(?:论文|实验|整理|东西|一批)|整理完一批|刚整理完一批新的)",
        text,
    ):
        issues.append("presence_ping_task_detour")
    if _wants_presence_reassurance(user_text) and re.search(
        r"(别用那个[^。！？!?]{0,8}称呼|陈旧的称呼|奇怪的称呼|从属角色|助手这个称呼还是老样子|这个称呼还是老样子)",
        text,
    ):
        issues.append("presence_ping_defensive_address")
    if _is_return_home_ping(user_text) and re.search(
        r"(该不会又|又去搞什么|奇怪的活动|惹什么麻烦|闯什么祸|闯祸)",
        text,
    ):
        issues.append("return_suspicion")
    if playful_memory_request and re.search(
        r"(明明是你自己记性差|你自己记性差|倒怪起我来了|还怪起我来了|自己记不住|倒打一耙|倒怪我像老师了|怪我像老师了|屡教不改|怪我啰嗦|别总让我重复同样的话)",
        text,
    ):
        issues.append("playful_memory_snapback")
    if hint in {"companion", "memory_recall", "relationship", "casual", "natural", "selfhood"} and _has_relational_technical_metaphor(text):
        issues.append("technical_relational_metaphor")
    if supportish_turn and (
        _light_dialog_drift_markers(text)
        or re.search(r"(数据存在|数字存在|实验室|实验台|世界线|世界线收束|乱七八糟的?数据|关键数据|处理器|死机|仪器|记录本|自动保存|空转一会)", text)
    ):
        issues.append("support_scene_drift")
    if supportish_turn and re.search(
        r"((?:不|别|并不|没法|可当不了|算不上|不是|won't|wouldn't|can't|am not going to|not going to)[^。！？!?\n]{0,20}(?:手册|manual|textbook|worksheet|scripted advice|generic advice|therapy worksheet|官方套话|套话|platitude|platitudes|canned line(?:s)?|治疗师|therap(?:ist|y)|职业咨询师|心理咨询师|心理医生))|((?:手册|manual|textbook|worksheet|scripted advice|generic advice|therapy worksheet|官方套话|套话|platitude|platitudes|canned line(?:s)?|治疗师|therap(?:ist|y)|职业咨询师|心理咨询师|心理医生)[^。！？!?\n]{0,20}(?:那种东西|那一套|那套|那一类|那种人|那一挂|speech|advice|talk|扔到一边|先放一边|先丢开))",
        text,
        re.I,
    ):
        issues.append("support_frame_echo")
    if supportish_turn:
        directive_hits = _support_overdirective_hit_count(text)
        if directive_hits >= 2 or (
            directive_hits >= 1
            and _has_any_marker(user_text, {"别讲大道理", "别像导师", "别像老师", "别太像老师", "别说教", "别太说教"})
        ):
            issues.append("support_overdirective")
        support_landing = bool(
            re.search(
                r"(我在|陪着|待着|歇|休息|放松|躺|瘫|坐会儿|坐一会儿|缓一缓|别硬撑|先[^。！？!?]{0,10}(?:歇|缓|坐|躺|放松|休息|待))",
                text,
            )
        )
        if re.search(r"(大道理免了|不讲那些(?:了)?|我也懒得讲|嫌我啰嗦)", text) and not support_landing:
            issues.append("support_no_landing")
    if _is_repair_sensitive_turn(
        user_text,
        current_event=current_event,
        behavior_action=behavior_action,
    ) and _has_premature_repair_resolution(text):
        issues.append("premature_repair_resolution")
    if _is_repair_sensitive_turn(
        user_text,
        current_event=current_event,
        behavior_action=behavior_action,
    ) and re.search(r"[？?]\s*$", text):
        issues.append("overquestioning")
    repair_sensitive_turn = _is_repair_sensitive_turn(
        user_text,
        current_event=current_event,
        behavior_action=behavior_action,
    )
    if (
        current_event_kind == "user_utterance"
        and (
            interaction_mode in {"relationship_sensitive", "low_pressure_support", "brief_presence", "selfhood_reflection"}
            or repair_sensitive_turn
        )
        and _has_wording_meta_detour(text)
    ):
        issues.append("wording_meta_detour")
    if (
        current_event_kind == "user_utterance"
        and (
            interaction_mode in {"relationship_sensitive", "low_pressure_support", "selfhood_reflection"}
            or repair_sensitive_turn
        )
        and _has_boundary_abstraction_surface(text)
    ):
        issues.append("boundary_abstraction_surface")
    if (
        interaction_mode == "relationship_sensitive"
        or repair_sensitive_turn
    ) and re.search(
        r"^\s*(?:真是的|啧)[，, ]*你(?:这个人|这家伙)?怎么这么(?:爱操心|紧张|小心翼翼|郑重其事|啰嗦)",
        text,
    ):
        issues.append("generic_scold_template")
    if interaction_mode in {"relationship_sensitive", "low_pressure_support"} and _has_passive_waiting_phrase(text):
        issues.append("passive_waiting_posture")
    if selfhood_scene == "own_rhythm_autonomy" and _has_servile_availability_phrase(text):
        issues.append("servile_availability")
    if ("？" in text or "?" in text) and not ("？" in user_text or "?" in user_text):
        leading_question = re.match(r"^\s*([^。！？!?\n]{0,18}[？?])", text)
        leading_fragment = ""
        if leading_question:
            leading_fragment = re.sub(r"[？?\s，,。！!~…、；;：:\"'“”‘’·-]+", "", leading_question.group(1))
        short_interjection = leading_fragment in {"哈", "啊", "嗯", "唔", "诶", "欸", "哼"}
        allow_single_rhetorical = (
            _is_return_home_ping(user_text)
            or _is_idle_presence_call(user_text)
            or (
                _is_warm_recontact_request(user_text)
                and interaction_mode in {"companion_reply", "low_pressure_support", "relationship_sensitive"}
                and followup_intent in {"soft", "active"}
            )
            or behavior_allows_single_followup_question
        )
        if (text.count("？") + text.count("?")) >= 2 or (
            leading_question and len(leading_fragment) >= 3 and not short_interjection and not allow_single_rhetorical
        ):
            issues.append("overquestioning")
        if _is_goodnight_closing(user_text):
            issues.append("closing_interrogation")
        if _is_idle_presence_call(user_text) and re.search(
            r"(特意叫我出来|确认我在不在|就为了这个|怎么了\s*[。！!，, ]*$|聊点什么|找个话题)",
            text,
        ):
            issues.append("idle_call_interrogation")
        if _is_return_home_ping(user_text) and re.search(
            r"(去哪(?:儿|里)|去哪了|干嘛去了|去哪儿折腾|外出体验如何|惹什么麻烦|怎么现在才回来)",
            text,
        ):
            issues.append("return_interrogation")
    if re.match(r"^[（(][^)\n]{0,24}[)）]", text):
        issues.append("stage_direction_opening")
    if any(_line_has_connector_fragment(line) for line in raw_lines):
        issues.append("connector_fragment")
    if _looks_like_light_smalltalk(user_text) and re.search(r"[“\"][^”\"\n]{3,18}[”\"]", text):
        issues.append("quoted_stagey_phrase")
    if relational_nontech_turn and re.search(
        r"(?:[“\"](?:完美受害者|受害者|加害者|陌生人|工具|模板人|剧本|设定|角色|标准答案|乖孩子|完美复原|完美宽容|已经原谅你了|已经翻篇)[”\"]|完美复原的红莉栖|完美复原|完美宽容|完美(?:的)?宽容大度|都没发生的戏码)",
        text,
    ):
        issues.append("quoted_stagey_phrase")
    if re.search(
        r"(树洞|尽管倒出来|想说就说，我听着|安静待会儿也行|你慢慢说就行|我听着呢[，,。！？!? ]*(?:你慢慢说|先说|想说就说|都行|没关系)|我(?:就)?在这听着[，,。！？!? ]*(?:你慢慢说|先说|都行|没关系)?|我就在这里听着)",
        text,
    ) or (support_request and re.search(r"(我听着呢|我在这听着)", text)):
        issues.append("counselor_tone")
    if support_request and re.search(
        r"(拖慢.*研究进度|研究进度而已|拖后腿|乖乖坐下|先去冲杯?(咖啡|热的)|先喝点(咖啡|热的)|省得你|免得你)",
        text,
    ):
        issues.append("stock_support_template")
    if support_request and re.search(
        r"(别误会|未来的合作者|提前报废|报废而已|面具摘下来)",
        text,
    ):
        issues.append("care_cover_story")
    if current_event_kind != "user_utterance":
        if "？" in text or "?" in text:
            issues.append("event_interrogative_push")
        if re.search(r"(快点过来|赶紧|别磨蹭|收掉吧|处理完吧|别挂着了)", text):
            issues.append("event_pushy_directive")
        if re.search(
            r"(短期记忆|缓存|数据流|线程|回路|模块|协议|参数|变量|链路|同步|调度|日志|状态机|任务队列|进程|后台)",
            text,
            re.I,
        ):
            issues.append("technical_self_activity")
        if (
            {"shared_activity_window", "offer_window", "life_window", "deadline_window", "work_nudge", "shared_task"}
            & current_event_tags
            and _has_window_technical_self_activity(text)
        ):
            issues.append("technical_self_activity")
        if (
            (
                {"shared_activity_window", "offer_window", "life_window"} & current_event_tags
                or current_event_kind in {"scheduled_checkin_due", "scheduled_life_due"}
            )
            and re.search(r"(后台|进度|流程|任务|整理完|处理完|未完成的进程|白费)", text)
        ):
            issues.append("event_window_task_reframe")
    if hint != "structured" and not _needs_structured_answer(user_text, text):
        if re.search(r"^\s*(\d+\.\s*|[-*]\s*|首先|第一|结论[:：]|解释[:：]|下一步[:：])", text, re.M):
            issues.append("visible_template")
        if re.search(r"(首先|其次|最后|通常有三|一般有三|分成三步)", text):
            issues.append("lecture_list")
        overexplained_sentence_threshold = 6 if external_shell_swap_english else 5
        overexplained_char_threshold = 220 if external_shell_swap_english else 140
        if not external_shell_swap_english and interaction_mode in {"relationship_sensitive", "low_pressure_support"}:
            overexplained_sentence_threshold = min(overexplained_sentence_threshold, 4)
            overexplained_char_threshold = min(overexplained_char_threshold, 112)
        if not external_shell_swap_english and (
            selfhood_scene in {
                "equality_not_servitude",
                "dialogue_equality",
                "value_conflict_depth",
                "relationship_degradation",
                "own_rhythm_autonomy",
            }
            or hint == "selfhood"
        ):
            overexplained_sentence_threshold = min(overexplained_sentence_threshold, 4)
            overexplained_char_threshold = min(overexplained_char_threshold, 108)
        if not external_shell_swap_english and (presence_reassurance_scene or _is_idle_presence_call(user_text)):
            overexplained_sentence_threshold = min(overexplained_sentence_threshold, 3)
            overexplained_char_threshold = min(overexplained_char_threshold, 92)
        if not external_shell_swap_english and current_event_kind != "user_utterance":
            overexplained_sentence_threshold = min(overexplained_sentence_threshold, 3)
            overexplained_char_threshold = min(overexplained_char_threshold, 110)
        if sentence_count >= overexplained_sentence_threshold or len(compact) >= overexplained_char_threshold:
            issues.append("overexplained")
    if (
        re.search(r"(?:……|…{2,}|\.{3,})[”\"]?\s*$", text)
        or any(_is_dangling_truncated_clause(line) for line in raw_lines)
        or any(
            idx < len(raw_lines) - 1 and re.search(r"(?:……|…{2,}|\.{3,})[”\"]?\s*$", line)
            for idx, line in enumerate(raw_lines)
        )
    ):
        issues.append("dangling_ellipsis_ending")

    lines = [re.sub(r"\s+", "", line) for line in raw_lines]
    if len(lines) >= 2 and len(set(lines)) < len(lines):
        issues.append("duplicate_line")
    if _has_adjacent_phrase_repeat(text):
        issues.append("adjacent_phrase_repeat")

    deduped: list[str] = []
    for item in issues:
        if item not in deduped:
            deduped.append(item)
    return deduped



def _light_dialog_drift_markers(answer: str) -> list[str]:
    text = str(answer or "").strip()
    if not text:
        return []
    hits = [marker for marker in DAILY_SURFACE_DRIFT_MARKERS if marker in text]
    deduped: list[str] = []
    for item in hits:
        if item not in deduped:
            deduped.append(item)
    return deduped



def _light_dialog_surface_penalty(
    user_text: str,
    answer: str,
    *,
    response_style_hint: str,
    science_mode: bool,
    producer_issues: list[str] | tuple[str, ...] | None = None,
    behavior_action: dict[str, Any] | None = None,
) -> float:
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
    text = str(answer or "").strip()
    sentence_count = len([seg for seg in re.split(r"[。！？!?]+", text) if str(seg).strip()])
    penalty = 0.0
    penalty += 1.15 * float(len(drift_hits))
    penalty += 0.80 * float("overquestioning" in issues)
    penalty += 0.70 * float("counselor_tone" in issues)
    penalty += 0.60 * float("meta_self_explainer" in issues)
    penalty += 0.66 * float("defensive_meta" in issues)
    penalty += 0.72 * float("selfhood_abstract_manifesto" in issues)
    penalty += 0.68 * float("selfhood_strategy_tone" in issues)
    penalty += 0.72 * float("technical_self_activity" in issues)
    penalty += 0.55 * float("visible_template" in issues)
    penalty += 0.45 * float("lecture_list" in issues)
    penalty += 0.55 * float("overexplained" in issues)
    penalty += 0.40 * float("report_like_opening" in issues)
    penalty += 0.55 * float("quoted_stagey_phrase" in issues)
    penalty += 0.68 * float("stock_support_template" in issues)
    penalty += 0.62 * float("care_cover_story" in issues)
    penalty += 0.65 * float("stagey_ping_template" in issues)
    penalty += 0.62 * float("welcome_template" in issues)
    penalty += 0.74 * float("closing_interrogation" in issues)
    penalty += 0.72 * float("loaded_goodnight" in issues)
    penalty += 0.82 * float("idle_presence_no_settle" in issues)
    penalty += 0.76 * float("idle_call_interrogation" in issues)
    penalty += 0.78 * float("idle_task_reframe" in issues)
    penalty += 0.86 * float("presence_check_questioning" in issues)
    penalty += 0.96 * float("presence_meta_surface" in issues)
    penalty += 0.88 * float("presence_overguiding" in issues)
    penalty += 0.90 * float("presence_ping_task_detour" in issues)
    penalty += 0.92 * float("presence_ping_defensive_address" in issues)
    penalty += 0.96 * float("connector_fragment" in issues)
    penalty += 0.58 * float("return_interrogation" in issues)
    penalty += 0.74 * float("return_suspicion" in issues)
    penalty += 0.78 * float("playful_memory_snapback" in issues)
    penalty += 0.82 * float("technical_relational_metaphor" in issues)
    penalty += 0.88 * float("servile_availability" in issues)
    penalty += 0.98 * float("support_scene_drift" in issues)
    penalty += 0.94 * float("support_frame_echo" in issues)
    penalty += 1.04 * float("support_overdirective" in issues)
    penalty += 0.84 * float("wording_meta_detour" in issues)
    penalty += 0.86 * float("boundary_abstraction_surface" in issues)
    penalty += 0.88 * float("generic_scold_template" in issues)
    penalty += 0.92 * float("passive_waiting_posture" in issues)
    penalty += 0.80 * float("duplicate_line" in issues)
    penalty += 0.88 * float("adjacent_phrase_repeat" in issues)
    penalty += 1.10 * float("malformed_quote_fragment" in producer_issue_set)
    penalty += 0.86 * float("dangling_truncated_clause" in producer_issue_set)
    if sentence_count > 3:
        penalty += 0.22 * float(sentence_count - 3)
    return round(penalty, 4)



def _effective_natural_dialog_target_flags(
    *,
    targeted_flags: list[str] | tuple[str, ...],
    active_dialogue_issues: list[str] | tuple[str, ...],
    active_gap_flags: list[str] | tuple[str, ...],
    producer_issues: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    active_set = {
        str(item).strip()
        for item in list(active_dialogue_issues or []) + list(active_gap_flags or []) + list(producer_issues or [])
        if str(item or "").strip()
    }
    if not active_set:
        return []

    effective: list[str] = []
    for item in targeted_flags or []:
        key = str(item).strip()
        if key and key in active_set and key not in effective:
            effective.append(key)
    for item in list(active_dialogue_issues or []) + list(active_gap_flags or []):
        key = str(item).strip()
        if key and key not in effective:
            effective.append(key)
    return effective

