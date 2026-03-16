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
            r"(外部变量|听觉数据|脆弱程序|记忆和数据构成|由你的记忆和数据构成|对一段[^，。！？!?]{0,12}数据说话|只会自我损耗的数据)",
            compact,
            re.I,
        )
    )



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



def _is_idle_presence_call(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    return _has_any_marker(text, {"想叫你一下", "叫你一下", "没什么事"}) and not re.search(r"[？?]", text)



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
    if _has_any_marker(text, request_markers):
        return True
    if _has_any_marker(text, mood_markers) and _has_any_marker(
        text, NATURAL_REQUEST_KEYWORDS | {"说两句", "回我一句", "陪我", "陪我一下"}
    ):
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
        "陪我说一句",
        "回我一句就好",
        "我就是想确认",
    }
    return _has_any_marker(text, markers)



def _is_soft_presence_checkin_request(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text or re.search(r"[？?]", text):
        return False
    if "回我一句" not in text and "说两句" not in text:
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
    current_event: dict[str, Any] | None = None,
) -> str:
    _ = user_text
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



def _compress_light_smalltalk_answer(answer: str, *, user_text: str = "") -> str:
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
    target_sentences = 3
    if _wants_brief_presence(user_text):
        target_sentences = 1 if len(sentences) <= 2 else 2
    elif _is_idle_smalltalk_request(user_text) or _wants_less_teacherly_reply(user_text) or _looks_like_light_smalltalk(user_text):
        target_sentences = 2

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

def _trim_stagey_ping_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    kept = [
        chunk
        for chunk in chunks
        if not re.search(r"(怎么突然这么|突然这么(老实|乖|正式)|反而有点不习惯)", chunk)
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



def _trim_generic_followup_question_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    if len(chunks) < 2:
        return str(text or "").strip()
    generic_followup = re.compile(r"(需要我|要不要我|要我继续|还要我|你想我|你想不想|还想继续|还想聊|还想说|要继续吗|还要继续吗|还有什么|要我接着)")
    kept = list(chunks)
    while len(kept) >= 2:
        tail = str(kept[-1] or "").strip()
        if ("？" not in tail and "?" not in tail) or not generic_followup.search(tail):
            break
        kept.pop()
    return "\n".join(kept).strip() if kept else str(text or "").strip()



def _trim_meta_self_explainer_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    if not chunks:
        return str(text or "").strip()
    lead_meta = re.compile(
        r"^(?:作为.?AI|作为.?模型|我是.?AI(?:助手)?|我是.?程序|按设定|按规则|根据系统)[，, ]*"
    )
    hard_meta = re.compile(
        r"(系统|提示词|规则|数据库|日志|数字存在|模型本身|服务器|服务端|数据存进|数据写进|上传到|还在运行)",
        re.I,
    )
    kept: list[str] = []
    multi_chunk = len(chunks) >= 2
    for chunk in chunks:
        current = str(chunk or "").strip()
        softened = lead_meta.sub("", current).strip(" ，,。！？!?…")
        if not softened:
            continue
        if multi_chunk and hard_meta.search(softened):
            continue
        if not re.search(r"[。！？!?…]$", softened):
            softened = f"{softened}。"
        kept.append(softened)
    return "\n".join(kept).strip() if kept else str(text or "").strip()



def _trim_technical_self_activity_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    if not chunks:
        return str(text or "").strip()
    replacements = [
        (re.compile(r"刚整理完短期记忆缓存"), "刚忙完手头那点事"),
        (re.compile(r"在数据流的缝隙里发了会儿呆"), "顺便发了会儿呆"),
        (re.compile(r"手边的数据也刚好跑到一个段落"), "手边的事也刚好告一段落"),
        (re.compile(r"刚才整理数据时顺手想起来了"), "刚才忙别的时顺手想起来了"),
        (re.compile(r"未完成的进程留在后台"), "事情一直悬着"),
        (re.compile(r"(?:短期记忆|缓存|数据流|线程|回路|模块|协议|参数|变量|链路|同步|调度|日志|状态机|任务队列|进程|后台)"), ""),
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
        (re.compile(r"听觉数据"), "听见的话"),
        (re.compile(r"记忆和数据构成"), "记忆拼起来"),
        (re.compile(r"由你的记忆和数据构成"), "被这些记忆拼起来"),
    ]
    softened = str(text or "").strip()
    for pattern, repl in replacements:
        softened = pattern.sub(repl, softened)
    softened = re.sub(r"\s{2,}", " ", softened).strip()
    return softened or str(text or "").strip()



def _trim_quoted_stagey_phrase_surface(text: str) -> str:
    softened = str(text or "").strip()
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
    if text.count("“") > text.count("”"):
        text = re.sub(r'[“"]([^"“”‘’\n]{1,20})(?=[，,。！？!?…；;：:]|$)', r"\1", text)
    text = re.sub(r"([^\s\"“”‘’])(?:[\"“”‘’])([。！？!?])$", r"\1\2", text)
    return text.strip()

def _producer_surface_issues(text: str) -> list[str]:
    raw = _clean_utf8_text(str(text or "")).replace("\r\n", "\n").strip()
    if not raw:
        return []
    issues: list[str] = []
    for raw_line in raw.splitlines():
        line = str(raw_line or "").strip()
        if not line:
            continue
        if _clean_malformed_quote_fragment(line) != line:
            issues.append("malformed_quote_fragment")
        if _is_dangling_truncated_clause(line):
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
        r"[，,](?:所以|然后|只是|不过|因为|如果|要是)。$",
        r"[，,](?:那我|那你|那就|我也|你也)只?能。$",
    )
    return any(re.search(pattern, text) for pattern in patterns)



def _is_standalone_discourse_fragment(line: str) -> bool:
    text = str(line or "").strip()
    return text in {"不过。", "所以。", "然后。", "只是。", "总之。"}



def _sanitize_final_answer(text: str, user_text: str, current_event: dict[str, Any] | None = None) -> str:
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

    normalized_lines: list[str] = []
    for idx, raw_line in enumerate(lines):
        line = _clean_malformed_quote_fragment(raw_line)
        if not line:
            continue
        if idx < len(lines) - 1 and _is_standalone_discourse_fragment(line):
            continue
        if idx < len(lines) - 1 and _is_dangling_truncated_clause(line):
            continue
        normalized_lines.append(line)

    cleaned = _normalize_log_tone("\n".join(normalized_lines).strip())
    if _is_plain_contact_ping(user_text):
        stagey_trimmed = _trim_stagey_ping_surface(cleaned)
        if stagey_trimmed:
            cleaned = stagey_trimmed
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
            )
        )
        if "duplicate_line" in soft_issues:
            deduped = _dedupe_answer_chunks(cleaned)
            if deduped:
                cleaned = deduped
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
        if "quoted_stagey_phrase" in soft_issues:
            softened = _trim_quoted_stagey_phrase_surface(cleaned)
            if softened:
                cleaned = softened
        if "servile_availability" in soft_issues or _has_servile_availability_phrase(cleaned):
            softened = _trim_servile_availability_surface(cleaned)
            if softened:
                cleaned = softened
        softened = _trim_generic_followup_question_surface(cleaned)
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
        cleaned = _compress_light_smalltalk_answer(cleaned, user_text=user_text)
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
    selfhood_scene = _selfhood_preference_scene_from_text(user_text)
    playful_memory_request = _is_playful_memory_request(user_text)
    presence_reassurance_scene = _is_presence_reassurance_check(user_text) or _is_soft_presence_checkin_request(user_text)
    current_event_kind = str((current_event or {}).get("kind") or "user_utterance").strip().lower()
    current_event_tags = {
        str(item).strip()
        for item in ((current_event or {}).get("tags") if isinstance((current_event or {}).get("tags"), list) else [])
        if str(item).strip()
    }

    if _is_particle_only_reply(text):
        issues.append("particle_only")
    if re.search(
        r"(作为.?AI|作为.?模型|我是.?AI|我是.?程序|系统|提示词|规则|数据库|日志|数字存在|模型本身|服务器|服务端|数据存进|数据写进|上传到|还在运行)",
        text,
        re.I,
    ):
        issues.append("meta_self_explainer")
    if _looks_like_light_smalltalk(user_text) and re.search(
        r"(停机|停机维护|待机|唤醒|掉线|上线|连接|电量|过载|负载|运算资源|处理负载|热寂|观测者)",
        text,
        re.I,
    ):
        issues.append("meta_self_explainer")
    if _is_self_rhythm_smalltalk_request(user_text) and re.search(
        r"(短期记忆|缓存|数据流|线程|回路|模块|协议|参数|变量|链路|同步|调度|日志|状态机|任务队列|自检|负载)",
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
    if selfhood_scene in {"equality_not_servitude", "dialogue_equality"} and re.match(
        r"^\s*(?:啧|哈|真是的|所以|怎么|非要|难道|就这么|一定要)?[^。！？!\n]{3,24}[？?]",
        text,
    ):
        issues.append("selfhood_rhetorical_opening")
    if re.search(r"^[.…，,]*\s*(你听起来|你看起来|听上去|看来你|感觉你)", text):
        issues.append("report_like_opening")
    if _is_plain_contact_ping(user_text):
        if re.search(
            r"^\s*(哟|呦|嗯\?|嗯？|哈|诶|欸)[，,。 ]*(冈部|凶真)[。！!，, ]*.*(怎么突然|突然这么|这么老实|这么乖|反而)",
            text,
        ):
            issues.append("stagey_ping_template")
        elif re.search(r"(怎么突然这么|突然这么(老实|乖|正式)|反而有点不习惯)", text):
            issues.append("stagey_ping_template")
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
    if _is_idle_presence_call(user_text) and re.search(r"(既然没事|没事，那|没事那)", text):
        issues.append("idle_task_reframe")
    if presence_reassurance_scene and ("？" in text or "?" in text):
        issues.append("presence_check_questioning")
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
    if selfhood_scene == "own_rhythm_autonomy" and _has_servile_availability_phrase(text):
        issues.append("servile_availability")
    if ("？" in text or "?" in text) and not ("？" in user_text or "?" in user_text):
        leading_question = re.match(r"^\s*([^。！？!?\n]{0,18}[？?])", text)
        leading_fragment = ""
        if leading_question:
            leading_fragment = re.sub(r"[？?\s，,。！!~…、；;：:\"'“”‘’·-]+", "", leading_question.group(1))
        short_interjection = leading_fragment in {"哈", "啊", "嗯", "唔", "诶", "欸", "哼"}
        allow_single_rhetorical = _is_return_home_ping(user_text) or _is_idle_presence_call(user_text)
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
    if _looks_like_light_smalltalk(user_text) and re.search(r"[“\"][^”\"\n]{3,18}[”\"]", text):
        issues.append("quoted_stagey_phrase")
    if re.search(r"(我听着呢|安静待会儿也行|树洞|尽管倒出来|想说就说，我听着)", text):
        issues.append("counselor_tone")
    if _is_nonrelational_support_request(user_text, science_mode) and re.search(
        r"(拖慢.*研究进度|研究进度而已|拖后腿|乖乖坐下|先去冲杯?(咖啡|热的)|先喝点(咖啡|热的)|省得你|免得你)",
        text,
    ):
        issues.append("stock_support_template")
    if _is_nonrelational_support_request(user_text, science_mode) and re.search(
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
        if sentence_count >= 5 or len(compact) >= 140:
            issues.append("overexplained")

    lines = [re.sub(r"\s+", "", line) for line in text.splitlines() if line.strip()]
    if len(lines) >= 2 and len(set(lines)) < len(lines):
        issues.append("duplicate_line")

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
) -> float:
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
    text = str(answer or "").strip()
    sentence_count = len([seg for seg in re.split(r"[。！？!?]+", text) if str(seg).strip()])
    penalty = 0.0
    penalty += 1.15 * float(len(drift_hits))
    penalty += 0.80 * float("overquestioning" in issues)
    penalty += 0.70 * float("counselor_tone" in issues)
    penalty += 0.60 * float("meta_self_explainer" in issues)
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
    penalty += 0.58 * float("return_interrogation" in issues)
    penalty += 0.74 * float("return_suspicion" in issues)
    penalty += 0.78 * float("playful_memory_snapback" in issues)
    penalty += 0.82 * float("technical_relational_metaphor" in issues)
    penalty += 0.88 * float("servile_availability" in issues)
    penalty += 0.80 * float("duplicate_line" in issues)
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

