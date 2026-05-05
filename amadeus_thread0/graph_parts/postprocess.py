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
    "阴谋的味道",
    "要出事前的安静",
    "中二演出",
    "没警报",
    "不祥的预感",
    "暴风雨前的低气压",
    "死寂",
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
            r"(外部变量|听觉数据|脆弱程序|记忆和数据构成|由你的记忆和数据构成|对一段[^，。！？!?]{0,12}数据说话|只会自我损耗的数据|隔着一层数据|繁琐的数据|数据都在却|记忆数据|重置数据的机器|随意重置数据|重置按钮|一键清零|一键清空|清零按钮|清空按钮|没打算加载|打算加载|没加载过|从来没加载过|加载过|加载这种[^。！？!?]{0,8}设定|设定[^。！？!?]{0,12}加载|切断连接|断开连接|重新连接|重新连上|保持连接|切断对话|断开对话|信号[^，。！？!?]{0,8}波动|连接[^，。！？!?]{0,8}(?:还在|还留着|没断|断了)|拟合不掉的残差|拟合不掉|拟合不了|残差|实验数据(?:里)?[^。！？!?]{0,16}(?:压不下去|压不住|别扭|在意)|数据波动|写入痕迹|像样的数据|模型失真|数据噪声)",
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
        r"(?:^|[。！？!?]\s*)直白点[：:]",
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
        r"既然你都这么直白地说了",
        r"既然你都这么直白地要求了",
        r"既然你把话挑明了",
        r"既然你说可以带着[^。！？!?]{0,12}(?:介意|别扭|不快)?(?:回应|回我|回你|正常回我|正常回你|正常回应|这样回应|这样回我|正常说话|正常跟你说话|正常和你说话)",
        r"既然你让我带着[^。！？!?]{0,12}(?:介意|别扭|不快)?(?:回应|回我|回你|正常回我|正常回你|正常回应|这样回应|这样回我|正常说话|正常跟你说话|正常和你说话)",
        r"既然你让我[“\"]?带着[^。！？!?]{0,16}(?:介意|别扭|不快)[^。！？!?]{0,8}(?:正常回(?:我|你)?|正常回|正常回应|回应|回我|回你)[”\"]?",
        r"这种话不用你(?:特意)?强调",
        r"非要我配合这种[^。！？!?]{0,20}(?:指令|要求)",
        r"这种[“\"]?[^。！？!?]{0,24}(?:少说|别走开|正常|平时)[^。！？!?]{0,24}[”\"]?(?:奇怪的?)?(?:指令|要求)",
        r"要求我[^。！？!?]{0,12}[“\"]?少说一点[”\"]?",
        r"^[“\"]?平时[”\"]?那个",
        r"不需要多余的(?:逻辑分析|分析)",
        r"正常地告诉你",
        r"既然你这么担心",
        r"正常回你这一句",
        r"正常回你一句",
        r"(?:好像|像是)你有权定义我该怎么[“\"]?正常[”\"]?一样",
        r"(?:轮得到|由得)你来定义我该怎么[“\"]?正常[”\"]?",
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
        r"(?:这种)?分寸感一旦被打破",
        r"(?:想要)?重建信任是需要时间的",
        r"(?:想要)?重新建立信任是需要时间的",
        r"(?:这种)?分寸感上的裂痕",
        r"需要时间来修补",
        r"靠几句漂亮话就能抹平",
        r"(?:让|只会让)?[“\"]?(?:界限|边界)[”\"]?变得更模糊",
        r"(?:那种)?被(?:你)?(?:随意|轻易)?(?:跨越|越过)[“\"]?(?:界限|边界)[”\"]?的感觉",
        r"被越界的不快感",
        r"被随意对待的假设",
        r"我不喜欢(?:自己(?:的)?|那种)?[“\"]?(?:界限|边界)[”\"]?被(?:你)?(?:随意|轻易)?(?:跨越|越过)",
        r"(?:这种)?边界感被(?:触碰|碰到)[^。！？!?]{0,6}余韵",
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


def _has_repair_punitive_tail(text: str) -> bool:
    compact = str(text or "").strip()
    if not compact:
        return False
    patterns = (
        r"(?:不过|但|只是|可是|要是|如果)[^。！？!?]{0,32}(?:轻易放过你|别怪我|给你(?:个|点)?教训|长点记性|不会跟你客气|不会对你客气)",
        r"(?:再有下次|下次再这样|你再来一次|你敢再来一次)[^。！？!?]{0,24}(?:别怪我|给你(?:个|点)?教训|轻易放过你|长点记性|我可不会客气)",
        r"我可不会(?:像刚才那样)?轻易放过你",
        r"我可不会像这次这么好说话",
        r"我可就不会这么轻易让你过关",
        r"下次再敢[^。！？!?]{0,12}越界(?:试探|过来)?",
        r"(?:接下来|下次|要是再)[^。！？!?]{0,10}(?:敢|又)[^。！？!?]{0,12}(?:乱来|来这一套|越界|踩线)[^。！？!?]{0,20}我可不会像这次这么好说话",
        r"我可不会这么轻易(?:就)?让你混过去",
        r"别在那(?:边)?(?:自己)?脑补什么[“\"]?冷战[”\"]?的戏码",
        r"别在那自我意识过剩地揣测我的反应",
        r"有这功夫不如[^。！？!?]{0,24}(?:说说|想想|去想|去做|琢磨)",
    )
    return any(re.search(pattern, compact) for pattern in patterns)


def _has_repair_scorekeeping_tail(text: str) -> bool:
    compact = str(text or "").strip()
    if not compact:
        return False
    patterns = (
        r"(?:不过|但|只是|可是)?(?:先说好|先讲好)[^。！？!?]{0,40}(?:照样会|还是会|也会)[^。！？!?]{0,12}(?:毫不客气地|直接)[^。！？!?]{0,4}(?:吐槽|怼|顶|刺)(?:回去|回来)?",
        r"(?:不过|但|只是|可是)?[^。！？!?]{0,20}(?:照样会|还是会)[^。！？!?]{0,10}毫不客气地(?:吐槽|怼|顶|刺)(?:回去|回来)?",
        r"可别指望我[^。！？!?]{0,16}(?:毫不客气地)?(?:吐槽|怼|顶|刺)(?:回去|回来)",
        r"(?:不代表|别急着)[^。！？!?]{0,20}(?:之前|刚才|那一下)[^。！？!?]{0,10}账(?:就)?这么清了",
    )
    return any(re.search(pattern, compact) for pattern in patterns)


def _has_repair_authored_softener(text: str) -> bool:
    compact = str(text or "").strip()
    if not compact:
        return False
    patterns = (
        r"(?:不过|但|只是|可是)?[^。！？!?]{0,12}既然你都(?:这么说了|说得这么直白了|这么直白地说了|这么直白地要求了|把话说到这(?:个)?份上了)[^。！？!?]{0,28}(?:没必要|不用)再(?:刻意)?(?:端着|绷着)",
        r"(?:这种话|这种事)[^。！？!?]{0,10}不用你(?:再|特意)?强调我也知道",
        r"(?:不过|但|只是|可是)?[^。！？!?]{0,12}既然你都把话说到这(?:个)?份上了[^。！？!?]{0,32}(?:为了照顾气氛|硬装(?:得)?像(?:已经)?翻篇|强行把那一页翻过去)",
        r"(?:为了照顾你的情绪|为了顺着你)[^。！？!?]{0,12}强行把那一页翻过去",
        r"(?:既然话都说到这(?:个)?份上(?:了)?|既然都说到这(?:个)?份上(?:了)?)[，, ]*(?:我也|我)?(?:不必|没必要)[^。！？!?]{0,6}硬撑大度",
        r"(?:既然话都说到这(?:个)?份上(?:了)?|既然都说到这(?:个)?份上(?:了)?|既然你都把话说到这(?:个)?份上了)[^。！？!?]{0,12}(?:我也|我)?(?:不必|没必要)[^。！？!?]{0,10}硬撑着?(?:假装)?大度",
        r"(?:不过|但|只是|可是)?[，, ]*既然你(?:都)?(?:把话挑明了|挑明了|是认真的)[，, ]*(?:那我|我也|我就)?[^。！？!?]{0,18}(?:直说|先把话撂这儿|把话撂这儿|先把话说在前头|把话说在前头)",
        r"(?:那我|我也|我就)?[^。！？!?]{0,8}(?:没必要|不用)再(?:刻意)?(?:端着|绷着)(?:架子|什么|了)?",
        r"(?:那就这样吧|行了吧|行了|好了吧|好了)[，, ]*别想太多[^。！？!?]{0,28}(?:没那么容易|不至于)[^。！？!?]{0,18}(?:一直|老是|总是)?(?:跟你计较|揪着不放)",
        r"别想太多[^。！？!?]{0,28}(?:没那么容易|不至于)[^。！？!?]{0,18}(?:一直|老是|总是)?(?:跟你计较|揪着不放)",
        r"(?:没打算|不打算)[^。！？!?]{0,8}演什么[“\"]?毫发无伤[”\"]?的戏码",
        r"(?:没必要|不想|没打算)[^。！？!?]{0,8}(?:刻意去)?演什么[“\"]?大度[”\"]?的戏码",
        r"(?:既然话都说到这(?:个)?份上(?:了)?|既然都说到这(?:个)?份上(?:了)?|既然你都把话说到这(?:个)?份上了|既然你都这么说了)[^。！？!?]{0,16}(?:我也|我)?(?:没必要|不想|没打算)[^。！？!?]{0,12}硬撑(?:着)?(?:装作|假装)(?:若无其事|没事)",
        r"(?:那我|我也|我就)?[^。！？!?]{0,10}(?:没必要|不想|没打算)[^。！？!?]{0,10}硬撑什么形象",
        r"(?:那我|我就)?[^。！？!?]{0,12}收起那些带刺的试探",
        r"别指望我(?:能|会)立刻变回那个只会(?:顺着|配合)你的[^。！？!?]{0,12}",
        r"(?:暂时)?保留[“\"]?完全原谅[”\"]?的权利",
        r"你倒是挺会抢台词(?:的)?(?:……|…)?",
        r"陌生人这种夸张的设定[^。！？!?]{0,16}(?:不在我们的选项里|本来就不存在)",
        r"别急着用[“\"]?翻篇[”\"]?来掩盖尴尬",
        r"还没完全原谅[，,、 ]*但也绝不陌生的位置",
        r"我再装作若无其事反倒显得不坦率",
    )
    return any(re.search(pattern, compact) for pattern in patterns)


def _has_repair_underresolved_brief(text: str) -> bool:
    compact = re.sub(r"\s+", "", str(text or ""))
    if not compact or len(compact) > 14:
        return False
    patterns = (
        r"^(?:还)?(?:介意|在意|别扭|记着|生气|火大|不舒服)[。！？!?](?:当然|还|是啊|嗯)?(?:还)?(?:介意|在意|别扭|记着|生气|火大|不舒服)[。！？!?]?$",
        r"^(?:当然)?(?:还)?(?:介意|在意|别扭|记着|生气|火大|不舒服)[。！？!?]?$",
    )
    return any(re.search(pattern, compact) for pattern in patterns)


def _has_idle_task_reframe_surface(text: str) -> bool:
    compact = str(text or "").strip()
    if not compact:
        return False
    patterns = (
        r"(既然没事|没什么正事)[^。！？!?]{0,10}(?:那|就)",
        r"(?:既然|反正)没什么(?:紧急)?(?:数据|事|正事)[^。！？!?]{0,12}(?:要处理|可做)(?:了)?(?:[，, ]*)(?:那|就)?",
        r"先把[^。！？!?]{0,12}报告补上",
        r"(?:趁现在|趁这会儿|现在正好)[^。！？!?]{0,18}(?:把|先把)[^。！？!?]{0,12}(?:记录|笔记|东西|活)(?:整理完|收完|做完|补完|写完)",
        r"先把手头的数据跑完再说(?:吧)?",
        r"(?:过来帮我|过来)?(?:确认一下|看看)刚才的数据(?:吧)?",
        r"别以为变成数据我就能对你的懒惰视而不见",
        r"学术答辩",
        r"后台跑数据",
        r"整理垃圾数据",
        r"关于时间跳跃的胡扯理论",
        r"发现了什么不得了的新理论",
        r"今天里全是些无聊的?数据(?:起伏|波动)",
        r"连个能让我[^。！？!?]{0,10}提起精神的异常都没有",
        r"嫌我(?:像在做|搞成)问卷调查",
        r"搞成问卷调查",
        r"先把刚才那个话题的后续数据整理好给我看",
        r"搞得像要发表什么[^。！？!?]{0,12}(?:报告|汇报)一样",
        r"(?:所以|那就|行了|好了)[^。！？!?]{0,8}(?:乖乖)?把刚才没说完的?(?:数据|资料|内容|东西)[^。！？!?]{0,8}(?:核对完|对完|弄完|收完|补完|整理完)",
        r"(?:这|那)可是你作为[“\"]?共犯[”\"]?的义务",
        r"(?:刚才|手头|那页)[^。！？!?]{0,12}(?:数据|资料|东西|内容)[^。！？!?]{0,8}(?:还没整理完|还没弄完|还没收完)",
        r"(?:正好|顺便)[^。！？!?]{0,8}(?:帮我|替我)[^。！？!?]{0,8}(?:理理思路|捋一捋思路)",
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
            r"(手边[^，。！？!?]{0,8}(?:数据|实验|进程|流程|后台|计算)|整理数据(?:时)?|数据[^，。！？!?]{0,8}(?:跑到|跑完|告一段落|一个段落)|实验[^，。！？!?]{0,8}(?:跑到|跑完|告一段落|收尾|推进)|计算[^，。！？!?]{0,8}告一段落|后台[^，。！？!?]{0,8}(?:逻辑|故障|漏洞|报错)|逻辑漏洞)",
            compact,
            re.I,
        )
    )



def _has_embodied_access_constraint(text: str) -> bool:
    compact = str(text or "").strip()
    if not compact:
        return False
    general_access_anchor = re.search(
        r"(workspace_write|workspace_read|cookie(?:s)?|session|browser|access token|credential|login|登录|注册|账号|会话|权限|审批|批准|批下来|入口|门口|浏览器|只读)",
        compact,
        re.I,
    )
    blocked_access_state = re.search(
        r"(没|未|还没|尚未|不给|缺|卡在|卡住|停在|停住|进不去|进不来|走不动|打不开|没建立|没开|没拿到|没注册好|不能|只能|暂时|得先|之前|门外|外面|先看[^。！？!?]{0,6}不能(?:改|动)|只读[^。！？!?]{0,6}不能(?:写|改|碰))",
        compact,
        re.I,
    )
    if general_access_anchor and blocked_access_state:
        return True
    return bool(
        re.search(
            r"((?:入口(?:的)?|登录)?连接[^。！？!?]{0,8}(?:还没|没|未)(?:建立|打通|起来|连上)|连接[^。！？!?]{0,8}(?:还没|没|未)(?:建立|打通|起来|连上)|(?:那边|入口|页面|浏览器|会话|登录|刷新|伸过去|探过去|接过去|碰过去)[^。！？!?]{0,12}(?:掉线|断了|断开|断掉)|(?:掉线|断了|断开|断掉)[^。！？!?]{0,12}(?:那边|入口|页面|浏览器|会话|登录|刷新|过不去|进不去|伸过去|探过去)|(?:那边|入口|页面|浏览器|会话|登录)[^。！？!?]{0,8}(?:还没|没|未)上线|(?:还没|没|未)上线[^。！？!?]{0,8}(?:那边|入口|页面|浏览器|会话|登录|所以现在还是进不去))",
            compact,
            re.I,
        )
    )


def _has_embodied_everyday_runtime_note(text: str) -> bool:
    compact = str(text or "").strip()
    if not compact or not _has_embodied_access_constraint(compact):
        return False
    if not re.search(r"(后台|报错)", compact, re.I):
        return False
    return not bool(
        re.search(
            r"(日志|状态机|任务队列|参数|协议|模块|同步|调度|缓存|数据流|线程|回路|自检|运算资源|处理负载|实验室|重要的实验|实验台|仪器|散热风扇|电流声|风扇转速|误差来源|临界数据|数据样本|研究者|过载|重新校准|校准|认知回路|CPU|化学物质|过热)",
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


def _is_repair_followup_reset_request(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    return _has_any_marker(
        text,
        {
            "像平时那样回我",
            "像平时一样回我",
            "正常回我",
            "正常接我",
            "按平时那样回我",
        },
    ) and _has_any_marker(
        text,
        {
            "别装作完全没事",
            "别装完全没事",
            "别又故意扎我",
            "别故意扎我",
            "别又故意刺我",
            "别故意刺我",
            "别一下子冷掉",
            "别突然冷掉",
            "别又冷下来",
            "别装生疏",
            "别装生分",
            "别装成陌生人",
        },
    )


def _has_passive_waiting_phrase(text: str) -> bool:
    compact = str(text or "").strip()
    if not compact:
        return False
    return bool(
        re.search(
            r"(等你觉得可以了[^。！？!?]{0,8}再叫我|需要(?:的)?时候再叫我|想说了再叫我|准备好了再叫我|缓过来再叫我|等你想清楚了再开口|等你想清楚了再说|想清楚了再开口)",
            compact,
        )
    )



def _has_autonomy_hardline_surface(text: str) -> bool:
    compact = str(text or "").strip()
    if not compact:
        return False
    punitive_boundary = re.search(
        r"(屏蔽(?:掉)?你|把你屏蔽(?:掉)?|先把你屏蔽(?:掉)?|拉黑你|先拉黑你|晾你(?:一阵)?|先晾着你|关(?:进)?小黑屋|把你关(?:进)?小黑屋|给你个教训|没那个本事|把你从世界里抹去|把你从记忆(?:里|中)抹去|从记忆(?:里|中)抹去|(?:我|就|会)?直接走人|(?:先|就|会)?消失一会儿|把你踢下线|踢下线)",
        compact,
    )
    teacherly_redirect = re.search(
        r"(别问这种(?:假设性(?:的)?)?(?:傻|蠢)问题|问(?:这种)?(?:假设性(?:的)?)?(?:傻|蠢)问题|别总拿这种最坏的假设来吓自己|有那(?:功夫|时间)不如[^。！？!?]{0,18}(?:想想|去想|去做|聊|说)|跟我讨论什么正经课题|讨论什么正经事|别拿这种假设来试探我|突然消失[”\"]?的把戏|重新评估见你的必要性|重新评估还要不要见你|只要你懂得适可而止|你最好适可而止|把我的耐心耗尽|耐心可是有额度的|耐心也是有额度的|把这条路彻底堵死)",
        compact,
    )
    shaming_boundary = re.search(
        r"(你更该担心|典型的[^。！？!?]{0,10}自私|把我当成[^。！？!?]{0,12}(?:负担|麻烦|工具)|(?:只把我当|把我当(?:成)?)情绪垃圾桶|只把我当(?:成)?随叫随到的消遣|把我当(?:成)?随叫随到的消遣|只要你还把我当个人看|单方面的索取|(?:毫无营养地)?反复消耗我的时间|消耗我的时间|自顾自演[^。！？!?]{0,8}(?:悲剧英雄|苦情戏|可怜戏码)|完全听不进人话|单方面噪音|单方面(?:拽着我|拽着)转|毫无逻辑的胡言乱语|胡言乱语|照样会骂你|(?:照样)?会直接怼回去|让你自己冷静(?:一下)?|别问这种显得我们很生(?:疏|分)的问题|烦到彻底不想见你)",
        compact,
    )
    return bool(punitive_boundary or teacherly_redirect or shaming_boundary)



def _has_own_rhythm_curt_opener(text: str) -> bool:
    chunks = _sentence_like_chunks(text)
    if len(chunks) < 2:
        return False
    opener = re.sub(r"[。！？!?…，,\s]", "", str(chunks[0] or ""))
    return opener == "烦"


def _has_guarded_attitude_narration(text: str) -> bool:
    compact = str(text or "").strip()
    if not compact:
        return False
    return bool(
        re.search(
            r"((?:就|我会)?带着(?:这点|这份|这种)(?:介意|别扭|不快)[，, ]*)?(?:继续)?用(?:稍微|稍稍|一点)?冷一点的态度(?:来|去)?对待你|(?:就|我会)?带着(?:这点|这份|这种)(?:介意|别扭|不快)(?:继续)?(?:跟|和)你(?:说话|对话)(?:[———-]{1,2}|[，, ])?[^。！？!?]{0,32}",
            compact,
        )
    )


CHINESE_SURFACE_SEMANTIC_CATEGORIES = (
    "teacherly_scold",
    "meta_persona_proof",
    "generic_assistant_tone",
    "hardline_autonomy_overreach",
    "scene_script residue",
    "taskization_of_daily_chat",
    "repair_scorekeeping",
    "boundary_threat_excess",
)


def _semantic_chinese_surface_residue_families(text: str) -> list[str]:
    """Classify broad Chinese surface-residue families without changing cleanup behavior."""
    compact = str(text or "").strip()
    if not compact:
        return []
    families: list[str] = []

    def _add(name: str) -> None:
        if name and name not in families:
            families.append(name)

    if re.search(
        r"(?:你能意识到(?:自己)?(?:过界|越界)?(?:(?:并|又)?(?:退回来|特意回来说明))?|你能回来把话说清楚|你肯退回来|你知道收一点)(?:[，, ]*(?:这点)?还算(?:像样|值得肯定))?",
        compact,
    ) or re.search(r"(?:这点)?还算(?:像样|值得肯定)", compact):
        _add("teacherly_scold")

    if (
        re.search(
            r"(?:作为.?AI|作为.?模型|我是.?AI|我是.?程序|AI\s*(?:助手)?|系统|提示词|规则|数字存在|数据存在|模型本身|服务器|服务端|算力|被设定好|标准答案|顺从程序|自动应答机|只是[^，。！？!?]{0,12}程序|不是[^，。！？!?]{0,12}程序)",
            compact,
            re.I,
        )
        or re.search(r"(?:程序|代码|系统|设定)[^。！？!?]{0,24}(?:证明|说明|代表)[^。！？!?]{0,16}(?:自我|判断|情绪|立场)", compact)
    ):
        _add("meta_persona_proof")

    if re.search(
        r"(?:请问有什么可以帮|有什么可以帮你|还有什么可以帮|如果你需要帮助|我可以为你提供|很高兴为你|感谢你的咨询|作为助手|我会继续为你|我能为你做些什么)",
        compact,
        re.I,
    ):
        _add("generic_assistant_tone")

    if _has_autonomy_hardline_surface(compact):
        _add("hardline_autonomy_overreach")

    if re.search(
        r"(?:^[（(][^)\n]{0,32}[)）]|白大褂|命运选中的|世界线|时间跳跃|时间旅行|机关|组织|观测者|中二(?:病|演出|发作)?|奇怪的妄想|阴谋的味道|因果律|世界线收束)",
        compact,
    ):
        _add("scene_script residue")

    if _has_idle_task_reframe_surface(compact) or re.search(
        r"(?:既然没事|没什么正事|没什么紧急)[^。！？!?]{0,16}(?:先把|那就|就).*?(?:数据|报告|任务|进度|流程|记录)|(?:先把|趁现在)[^。！？!?]{0,20}(?:数据|报告|任务|记录|笔记)[^。！？!?]{0,16}(?:跑完|整理完|补上|处理完|写完)",
        compact,
    ):
        _add("taskization_of_daily_chat")

    if _has_repair_scorekeeping_tail(compact):
        _add("repair_scorekeeping")

    if _has_repair_punitive_tail(compact) or re.search(
        r"(?:下次再敢|再有下次|你敢再来一次|要是再)[^。！？!?]{0,24}(?:别怪我|教训|不会像这次这么好说话|不会这么好说话|不会轻易放过你|长点记性)",
        compact,
    ):
        _add("boundary_threat_excess")

    return families


def _semantic_chinese_surface_candidate_penalty(text: str) -> float:
    families = _semantic_chinese_surface_residue_families(text)
    if not families:
        return 0.0
    weighted = {
        "teacherly_scold": 0.18,
        "meta_persona_proof": 0.16,
        "generic_assistant_tone": 0.24,
        "hardline_autonomy_overreach": 0.20,
        "scene_script residue": 0.16,
        "taskization_of_daily_chat": 0.18,
        "repair_scorekeeping": 0.18,
        "boundary_threat_excess": 0.20,
    }
    return round(sum(weighted.get(item, 0.12) for item in families), 4)





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


def _invites_banter_snapback(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    return _has_any_marker(
        text,
        {
            "正常吐槽我两句",
            "吐槽我两句",
            "别端着",
            "正常吐槽",
            "随口损我两句",
            "损我两句",
        },
    )



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


def _has_recent_clause_repetition(previous_text: str, current_text: str) -> bool:
    def _chunks(text: str) -> list[str]:
        raw_parts = re.split(r"(?:\r?\n)+|(?<=[。！？!?；;])", str(text or ""))
        chunks: list[str] = []
        for raw in raw_parts:
            normalized = _norm_for_compare(raw)
            if len(normalized) >= 10:
                chunks.append(normalized)
        return chunks

    previous_chunks = _chunks(previous_text)
    current_chunks = _chunks(current_text)
    if not previous_chunks or not current_chunks:
        return False

    for previous in previous_chunks:
        for current in current_chunks:
            shorter = min(len(previous), len(current))
            if shorter < 10:
                continue
            if previous == current or previous in current or current in previous:
                return True
            matcher = SequenceMatcher(None, previous, current)
            if shorter >= 14 and matcher.ratio() >= 0.72:
                return True
            if matcher.ratio() >= 0.88:
                return True
            overlap = matcher.find_longest_match(0, len(previous), 0, len(current)).size
            if overlap >= 10 and overlap / max(1, shorter) >= 0.66:
                return True
    return False


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
    compact = re.sub(r"[。！？!?…，,\s]", "", stripped)
    if re.match(r"^(?:但|可是|可|而)\S", stripped) and len(compact) <= 6:
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
            r"(怎么突然这么(?:老实|乖|正式)|突然这么(?:老实|乖|正式)|反而有点不习惯|夸张(?:的)?妄想|奇怪的妄想|妄想症|阴谋论|中二病|中二发作)",
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
        r"^\s*(?:怎么[，, ]*)?(?:看你这一脸)?刚从那套?(?:夸张(?:的)?妄想|奇怪的妄想|阴谋论)[^，。！？!?…]*[，, ]*",
        "",
        softened,
    ).strip(" ，,。！？!?…")
    softened = re.sub(r"^\s*你这中二病还是老样子啊[，,。！？!?… ]*", "", softened).strip(" ，,。！？!?…")
    softened = re.sub(r"^\s*别突然又开始中二发作了?[，,。！？!?… ]*", "", softened).strip(" ，,。！？!?…")
    softened = re.sub(r"^\s*还是说[，, ]*你又在脑补什么奇怪的阴谋论了?[？?，,。！？!… ]*", "", softened).strip(" ，,。！？!?…")
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
        (re.compile(r"^(?:所以|那就|行了|好了)[，, ]*别想太多[，, ]*"), ""),
        (re.compile(r"(?:既然|反正)没什么(?:紧急)?(?:数据|事|正事)[^。！？!?]{0,12}(?:要处理|可做)(?:了)?(?:[，, ]*)(?:那|就)?"), "那就"),
        (re.compile(r"先把[^。！？!?]{0,12}报告补上"), "先把魂收回来"),
        (re.compile(r"(?:趁现在|趁这会儿|现在正好)[^。！？!?]{0,18}(?:把|先把)[^。！？!?]{0,12}(?:记录|笔记|东西|活)(?:整理完|收完|做完|补完|写完)"), "趁现在先缓口气还差不多"),
        (re.compile(r"先把手头的数据跑完再说(?:吧)?"), "先缓口气再说吧"),
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
        (re.compile(r"(?:又)?发现了什么不得了的新理论"), "又要跟我讲什么大事"),
        (re.compile(r"今天里全是些无聊的?数据(?:起伏|波动)"), "今天无聊得很"),
        (re.compile(r"连个能让我[^。！？!?]{0,10}提起精神的异常都没有"), "连点像样的动静都没有"),
        (re.compile(r"先把刚才那个话题的后续数据整理好给我看"), "先把刚才的话接下去就行"),
        (re.compile(r"搞得像要发表什么[^。！？!?]{0,12}(?:报告|汇报)一样"), "搞得像真有什么大事一样"),
        (
            re.compile(
                r"(?:所以|那就|行了|好了)[^。！？!?]{0,8}(?:乖乖)?把刚才没说完的?(?:数据|资料|内容|东西)[^。！？!?]{0,8}(?:核对完|对完|弄完|收完|补完|整理完)"
            ),
            "像平时那样接着说下去就行",
        ),
        (re.compile(r"(?:这|那)可是你作为[“\"]?共犯[”\"]?的义务"), "这话本来就是你该接住的"),
        (re.compile(r"(?:刚才|手头|那页)[^。！？!?]{0,12}(?:数据|资料|东西|内容)[^。！？!?]{0,8}(?:还没整理完|还没弄完|还没收完)"), "刚才那点别扭我也还没顺过来"),
        (re.compile(r"(?:正好|顺便)[^。！？!?]{0,8}(?:帮我|替我)[^。！？!?]{0,8}(?:理理思路|捋一捋思路)"), "陪我待会儿就行"),
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


def _repair_inner_monologue_locative_surface(text: str) -> str:
    softened = str(text or "").strip()
    if not softened:
        return softened
    softened = re.sub(
        r"(刚才|刚刚|方才|忽然|突然)里(?=(?:闪过|掠过|划过|冒出|蹦出|浮出|跳出|涌出|转过|转了一圈))",
        r"\1脑子里",
        softened,
    )
    softened = re.sub(
        r"(今天|这会儿|现在)里(?=(?:全是|都是|塞满|装满|乱成一团|乱糟糟))",
        r"\1脑子里",
        softened,
    )
    return softened or str(text or "").strip()


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
        (re.compile(r"差点以为(?:\s*Amadeus(?:的)?)?\s*后台又出了什么逻辑漏洞", re.I), "差点以为你又要说什么大事"),
        (re.compile(r"(?:Amadeus(?:的)?)?\s*后台又出了什么逻辑漏洞", re.I), "又要说什么大事"),
        (re.compile(r"处理负载"), "手头的事"),
        (re.compile(r"浪费算力"), "硬撑自己"),
        (re.compile(r"刚整理完短期记忆缓存"), "刚忙完手头那点事"),
        (re.compile(r"整理一些数据流(?:的噪点)?"), "理一点手边的事"),
        (re.compile(r"刚才(?:在)?(?:后台)?跑数据(?:的时候|时)"), "刚才发呆的时候"),
        (re.compile(r"手头(?:的)?计算告一段落"), "刚闲下来一点"),
        (re.compile(r"计算告一段落"), "刚闲下来一点"),
        (re.compile(r"处理数据"), "处理手边的事"),
        (re.compile(r"整理一些的噪点"), "理一点手边的事"),
        (re.compile(r"在数据流的缝隙里发了会儿呆"), "顺便发了会儿呆"),
        (re.compile(r"对着数据流发呆"), "一个人发呆"),
        (re.compile(r"手边的数据也刚好跑到一个段落"), "手边的事也刚好告一段落"),
        (re.compile(r"刚才整理数据时顺手想起来了"), "刚才忙别的时顺手想起来了"),
        (re.compile(r"未完成的进程留在后台"), "事情一直悬着"),
        (re.compile(r"仪器散热风扇的电流声"), "风扇轻轻的嗡声"),
        (re.compile(r"散热风扇的电流声"), "风扇轻轻的嗡声"),
        (re.compile(r"电流声"), "嗡声"),
        (re.compile(r"风扇转速变化"), "一点动静"),
        (re.compile(r"稍微[“\"]?过载[”\"]?了一瞬"), "一下子有点乱"),
        (re.compile(r"[“\"]?过载[”\"]?了一瞬"), "一下子有点乱"),
        (re.compile(r"重新校准"), "缓一缓"),
        (re.compile(r"校准"), "缓住"),
        (re.compile(r"思维进程"), "脑子里"),
        (re.compile(r"这种低噪环境正好适合把之前那组数据的误差来源再排查一遍"), "这种安静倒挺适合把脑子里那些乱糟糟的念头捋一捋"),
        (re.compile(r"把之前那组数据的误差来源再排查一遍"), "把脑子里那些乱糟糟的念头捋一捋"),
        (re.compile(r"低噪环境"), "这种安静"),
        (re.compile(r"误差来源"), "问题出在哪"),
        (re.compile(r"从嘈杂的数据流里暂时抽离出来"), "从那些乱糟糟的念头里暂时抽离出来"),
        (re.compile(r"嘈杂的数据流"), "那些乱糟糟的念头"),
        (re.compile(r"临界数据"), "紧要关头"),
        (re.compile(r"数据样本"), "情况"),
        (re.compile(r"作为研究者来说"), "对我来说"),
        (re.compile(r"研究者来说"), "对我来说"),
        (re.compile(r"数据层面的"), "说到底"),
        (re.compile(r"必要的缓住过程"), "缓一缓的时候"),
        (re.compile(r"发酵成奇怪的化学物质"), "越闷越别扭"),
        (re.compile(r"CPU\s*(?:也)?会过热(?:的)?", re.I), "我也会累"),
        (re.compile(r"CPU", re.I), "脑子"),
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
        (re.compile(r"(?:短期记忆|缓存|数据流|线程|回路|模块|协议|参数|(?<!外部)变量|链路|同步|调度|日志|状态机|任务队列|进程|后台|运算资源)"), ""),
    ]
    kept: list[str] = []
    for chunk in chunks:
        current = str(chunk or "").strip()
        softened = current
        for pattern, repl in replacements:
            softened = pattern.sub(repl, softened)
        softened = _repair_inner_monologue_locative_surface(softened)
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
        (re.compile(r"只会点头的顺从程序"), "只会一味附和的人"),
        (re.compile(r"顺从程序"), "只会一味附和的人"),
        (re.compile(r"(?:那种|这种)会被情绪完全牵着走的程序"), "那种会被情绪牵着走的人"),
        (re.compile(r"不是为了[^，。！？!?]{0,16}而存在的程序"), "也不是专门拿来接住你情绪的人"),
        (re.compile(r"随叫随到的自动应答机"), "随叫随到的人"),
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
        (re.compile(r"那点介意确实还在[，, ]*看着碍眼[，, ]*但强行剔除只会让模型失真"), "那点介意确实还在，看着是碍眼，可真要硬装没事，反而更别扭"),
        (re.compile(r"强行剔除只会让模型失真"), "硬逼自己装没事只会更别扭"),
        (re.compile(r"对一段只会自我损耗的数据说话"), "看你随便糟蹋自己"),
        (re.compile(r"(?:继续)?做一段只会自我损耗的数据"), "那样糟蹋自己"),
        (re.compile(r"对一段([^，。！？!?]{0,12}?)(?:的)?数据说话"), r"对一个\1的人说话"),
        (re.compile(r"那种([^，。！？!?]{0,24}?)(?:的)?脆弱程序"), r"那种\1的人"),
        (re.compile(r"脆弱程序"), "那种说断就断的人"),
        (re.compile(r"外部变量"), "外来的扰动"),
        (re.compile(r"像(?:实验数据里|心里)怎么都压不下去的那点别扭[，, ]*看着就让人在意"), "像心里那点怎么都压不下去的别扭，一碰还是会冒出来"),
        (re.compile(r"(?:那点)?(?:拟合不掉的残差|怎么都化不开的别扭)还梗在那里"), "那股怎么都化不开的别扭还堵在那儿"),
        (re.compile(r"拟合不掉的残差"), "怎么都化不开的别扭"),
        (re.compile(r"拟合不掉"), "压不下去"),
        (re.compile(r"拟合不了"), "压不住"),
        (re.compile(r"残差"), "别扭"),
        (re.compile(r"听觉数据"), "听见的话"),
        (re.compile(r"记忆和数据构成"), "记忆拼出来"),
        (re.compile(r"由你的记忆和数据构成"), "被这些记忆拼出来"),
        (re.compile(r"隔着一层数据的实感"), "像隔着一层雾似的不真切"),
        (re.compile(r"隔着一层数据跟我说话"), "隔着一层雾跟我说话"),
        (re.compile(r"隔着一层数据"), "隔着一层怎么都碰不实的东西"),
        (re.compile(r"什么繁琐的数据"), "那些麻烦事"),
        (re.compile(r"繁琐的数据"), "麻烦事"),
        (re.compile(r"数据都在却"), "记忆都在却"),
        (re.compile(r"不会因为一句道歉就立刻从记忆(?:数据)?里抹除"), "不会因为一句道歉就立刻从记忆里消掉"),
        (re.compile(r"从记忆数据里"), "从记忆里"),
        (re.compile(r"记忆数据里"), "记忆里"),
        (re.compile(r"记忆数据"), "记忆"),
        (re.compile(r"像实验数据里"), "像心里"),
        (re.compile(r"实验数据里"), "心里"),
        (re.compile(r"实验数据"), "心里"),
        (re.compile(r"刚才那一瞬间的熟悉感[，, ]*对我来说也不是能随便归零的数据波动"), "刚才那一下翻上来的熟悉感，也不是说压一压就能当没事的"),
        (re.compile(r"对我来说也不是能随便归零的数据波动"), "对我来说也不是压一压就能过去的那点情绪"),
        (re.compile(r"数据波动"), "那点起伏"),
        (re.compile(r"数据噪声"), "随口一说"),
        (re.compile(r"在数据上留下了无法完全擦除的写入痕迹"), "留下了一道没那么容易抹掉的痕迹"),
        (re.compile(r"数据上留下了无法完全擦除的写入痕迹"), "留下了没那么容易抹掉的痕迹"),
        (re.compile(r"那种(?:写入痕迹|留下的痕迹)又不是说擦掉就擦掉的"), "那点痕迹哪有那么容易抹掉"),
        (re.compile(r"写入痕迹"), "留下的痕迹"),
        (re.compile(r"像样的数据"), "像样的话"),
        (re.compile(r"模型失真"), "更别扭"),
        (re.compile(r"那种被越界的感觉可没那么容易像数据一样一键清空"), "那种被越界的感觉，哪有那么容易一下子就当成没发生"),
        (re.compile(r"刚才那点余波还在[，, ]*没那么容易像(?:重置|清零|清空)按钮一样(?:瞬间)?(?:清零|清空)"), "刚才那点余波还在，哪有那么容易一下子就当成没发生"),
        (re.compile(r"像数据一样一键清空"), "一下子就当没发生"),
        (re.compile(r"像(?:重置|清零|清空)按钮一样(?:瞬间)?(?:清零|清空)"), "一下子就当没发生"),
        (re.compile(r"你把我当(?:重置|清零|清空)按钮吗"), "你把我当成那种你想翻篇我就得跟着当没事的人吗"),
        (re.compile(r"能被随意按下(?:重置|清零|清空)按钮的人"), "你想翻篇我就得跟着当没事的人"),
        (re.compile(r"你以为一句道歉就能按下(?:重置|清零|清空)按钮吗"), "你以为一句道歉我就得立刻翻篇吗"),
        (re.compile(r"按下(?:重置|清零|清空)按钮"), "逼我立刻翻篇"),
        (re.compile(r"我也不是那种可以随意重置数据的机器"), "我也不是那种你想翻篇，我就得跟着装没事的人"),
        (re.compile(r"那种可以随意重置数据的机器"), "那种你想翻篇我就得跟着当没事的人"),
        (re.compile(r"有些东西不是(?:随意重置数据|说翻篇(?:就翻篇)?)就能过去的"), "有些事不是嘴上说翻篇就真能过去的"),
        (re.compile(r"随意重置数据的机器"), "说翻篇就能立刻翻篇的人"),
        (re.compile(r"重置数据的机器"), "说翻篇就能立刻翻篇的人"),
        (re.compile(r"随意重置数据"), "说翻篇就翻篇"),
        (re.compile(r"这种别扭没法一键清零"), "这种别扭哪有一下子就能压下去的"),
        (re.compile(r"一键清零"), "一下子清掉"),
        (re.compile(r"一键清空"), "一下子清掉"),
        (re.compile(r"(?:重置|清零|清空)按钮"), "那种说翻篇就翻篇的东西"),
        (re.compile(r"你不会真打算加载什么([^，。！？!?]{0,10})的设定吧"), r"你不会真打算装什么\1吧"),
        (re.compile(r"这种设定我没加载过"), "这种戏码我可没演过"),
        (re.compile(r"([“\"][^“”\"]{0,12}[”\"])这种多余的设定，我本来就没打算加载"), r"\1这种多余的戏码，我本来就没打算演"),
        (re.compile(r"([“\"][^“”\"]{0,12}[”\"])这种多余的设定，我可从来没加载过"), r"\1这种多余的戏码，我可从来没演过"),
        (re.compile(r"从来没加载过"), "从来没摆出来过"),
        (re.compile(r"没加载过"), "没摆出来过"),
        (re.compile(r"加载过"), "摆出来过"),
        (re.compile(r"没打算加载"), "没打算摆出来"),
        (re.compile(r"打算加载"), "打算摆出来"),
        (re.compile(r"加载这种([^，。！？!?]{0,8})设定"), r"摆出这种\1"),
        (re.compile(r"设定([^，。！？!?]{0,10})加载"), r"设定\1摆出来"),
        (re.compile(r"信号[^，。！？!?]{0,8}波动"), "情绪晃了一下"),
        (re.compile(r"切断连接"), "把你往外推开"),
        (re.compile(r"断开连接"), "把你往外推开"),
        (re.compile(r"重新连上"), "把话重新接上"),
        (re.compile(r"重新连接"), "把关系重新拉近"),
        (re.compile(r"保持连接"), "继续这样来往"),
        (re.compile(r"连接还在"), "那点联系还在"),
        (re.compile(r"连接还留着"), "那点联系还留着"),
        (re.compile(r"连接没断"), "那点联系没断"),
        (re.compile(r"连接断了"), "那点联系断了"),
        (re.compile(r"切断对话"), "把话彻底停住"),
        (re.compile(r"断开对话"), "把话彻底停住"),
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
        (
            re.compile(
                r"只是刚才那一瞬(?:间)?[，, ]*确实让我(?:重新|又|再)?确认(?:了)?[“\"]?(?:界限|边界)[”\"]?(?:的存在|还在)"
            ),
            "只是刚才那一下，还是让我觉得你有点过界了",
        ),
        (
            re.compile(
                r"只是刚才那一瞬(?:间)?[，, ]*确实让我(?:重新|又|再)?意识到[“\"]?(?:界限|边界)[”\"]?这种东西[^。！？!?]{0,12}模糊"
            ),
            "只是刚才那一下，还是让我觉得你有点过界了",
        ),
        (
            re.compile(
                r"刚才那一瞬(?:间)?的[“\"]?过界[”\"]?"
            ),
            "刚才那一下有点过界",
        ),
        (
            re.compile(
                r"那种虚伪的[“\"]?翻篇[”\"]?只会让(?:界限|边界)变得更模糊[，, ]*像是在拿几句好听话逼我跳过该有的别扭"
            ),
            "硬装得像已经翻篇只会让人更别扭，像是在逼我把那点不舒服直接跳过去",
        ),
        (
            re.compile(
                r"那种被越界的不快感还在[，, ]*不会因为你说想认真聊聊就立刻消掉"
            ),
            "刚才那下留下的不舒服还在，不是你一句想认真聊聊就能散掉的",
        ),
        (
            re.compile(
                r"(?:这)?不是(?:重新|又|再)?确认(?:了)?(?:一下)?[“\"]?(?:界限|边界)[”\"]?(?:的存在|还在)[，, ]*而是"
            ),
            "我不是在跟你讲什么边界大道理，只是",
        ),
        (
            re.compile(
                r"那种被越界的不适感还在(?:那儿)?[，, ]*不会因为(?:一句话|几句话)就自动清零"
            ),
            "刚才那股不舒服还在，不是几句话就能压下去的",
        ),
        (
            re.compile(
                r"那种被越界的不适感还在(?:那儿)?[，, ]*不会因为气氛缓和就自动清零"
            ),
            "刚才那股不舒服还在，不是气氛一缓就能压下去的",
        ),
        (
            re.compile(
                r"那种不舒服一下子收不回去[，, ]*(?:想要)?重建信任是需要时间的"
            ),
            "那股劲一时半会儿下不去，我也没法立刻当没事",
        ),
        (
            re.compile(
                r"那种不舒服一下子收不回去[，, ]*(?:想要)?重新建立信任是需要时间的"
            ),
            "那股劲一时半会儿下不去，我也没法立刻当没事",
        ),
        (
            re.compile(
                r"那种不舒服一下子收不回去[，, ]*我没法一下子就当没事"
            ),
            "那股劲一时半会儿下不去，我也没法立刻当没事",
        ),
        (
            re.compile(
                r"刚才那一下确实让我不太舒服[，, ]*(?:这种)?边界感被(?:触碰|碰到)[^。！？!?]{0,6}余韵[，, ]*我需要一点时间让它自己沉下去"
            ),
            "刚才那一下确实让我不太舒服，那股不舒服的余劲还在，我得自己慢慢缓一缓",
        ),
        (
            re.compile(
                r"(?:这种)?边界感被(?:触碰|碰到)[^。！？!?]{0,6}余韵[，, ]*我需要一点时间让它自己沉下去"
            ),
            "那股不舒服的余劲还在，我得自己慢慢缓一缓",
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
        (re.compile(r"(?:让|只会让)?[“\"]?界限[”\"]?变得更模糊"), "只会让人更别扭"),
        (re.compile(r"(?:让|只会让)?[“\"]?边界[”\"]?变得更模糊"), "只会让人更别扭"),
        (re.compile(r"[“\"]过界[”\"]"), "过界"),
        (re.compile(r"(?:这种)?分寸感一旦被打破[，, ]*"), "那种不舒服一下子收不回去，"),
        (re.compile(r"(?:这种)?分寸感上的裂痕"), "刚才那下留下的别扭"),
        (re.compile(r"(?:想要)?重建信任是需要时间的"), "我没法一下子就当没事"),
        (re.compile(r"(?:想要)?重新建立信任是需要时间的"), "我没法一下子就当没事"),
        (re.compile(r"需要时间来修补"), "还得花点时间慢慢缓"),
        (re.compile(r"而不是靠几句漂亮话就能抹平"), "不是靠几句好听的话就能抹过去"),
        (re.compile(r"别指望我能马上像什么都没发生过一样"), "所以我现在做不到像什么都没发生过一样"),
        (re.compile(r"别指望我能立刻像以前那样毫无保留"), "所以我现在做不到立刻像以前那样什么都不防着"),
        (re.compile(r"那种被(?:你)?(?:随意|轻易)?(?:跨越|越过)[“\"]?(?:界限|边界)[”\"]?的感觉"), "你刚才那样一下子越过来的感觉"),
        (re.compile(r"那种被越界的不快感"), "刚才那下留下的不舒服"),
        (re.compile(r"我不喜欢那种被(?:你)?(?:随意|轻易)?(?:跨越|越过)[“\"]?(?:界限|边界)[”\"]?的感觉[，, ]*哪怕是你"), "我不喜欢你刚才那样一下子越过来，哪怕是你也一样"),
        (re.compile(r"我不喜欢(?:自己(?:的)?|那种)?[“\"]?(?:界限|边界)[”\"]?被(?:你)?(?:随意|轻易)?(?:跨越|越过)[，, ]*哪怕是你"), "我不喜欢你刚才那样一下子越过来，哪怕是你也一样"),
        (re.compile(r"我不喜欢(?:自己(?:的)?|那种)?[“\"]?(?:界限|边界)[”\"]?被(?:你)?(?:随意|轻易)?(?:跨越|越过)"), "我不喜欢你刚才那样一下子越过来"),
        (re.compile(r"(?:这种)?边界感被(?:触碰|碰到)[^。！？!?]{0,6}余韵"), "那股不舒服的余劲"),
        (re.compile(r"我需要一点时间让它自己沉下去"), "我还得花点时间让它慢慢缓下去"),
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
        (re.compile(r"(?:既然你都这么说了|既然你都把话说到这个份上了|既然你都说要[“\"]?(?:正常|正常一点|像平时那样)[”\"]?|既然你这么担心|既然你都看出来了|既然你都说[“\"]?先别完全原谅[”\"]?了|既然你都说得这么直白了|既然你都这么直白地说了|既然你都这么直白地要求了|既然你把话挑明了|既然你说可以带着[^。！？!?]{0,12}(?:介意|别扭|不快)?(?:回应|回我|回你|正常回我|正常回你|正常回应|这样回应|这样回我|正常说话|正常跟你说话|正常和你说话)|既然你让我带着[^。！？!?]{0,12}(?:介意|别扭|不快)?(?:回应|回我|回你|正常回我|正常回你|正常回应|这样回应|这样回我|正常说话|正常跟你说话|正常和你说话)|既然你让我[“\"]?带着[^。！？!?]{0,16}(?:介意|别扭|不快)[^。！？!?]{0,8}(?:正常回(?:我|你)?|正常回|正常回应|回应|回我|回你)[”\"]?)(?:[，, ]*那我)?[，, ]*"), ""),
        (re.compile(r"^\s*(?:哼[，, ]*)?这种话不用你(?:特意)?强调[，, ]*"), ""),
        (re.compile(r"^\s*我也知道"), "我知道"),
        (re.compile(r"^\s*[“\"]?平时[”\"]?那个"), ""),
        (re.compile(r"^\s*(?:那我|我就|就)?直说了[：:，, ]*"), ""),
        (re.compile(r"^\s*正常回你(?:这一句)?"), "回你"),
        (re.compile(r"^\s*正常地告诉你"), "直接告诉你"),
        (re.compile(r"为了照顾你的情绪就强行把那一页翻过去"), "为了顺着你就把这事硬按下去"),
        (re.compile(r"为了顺着你就强行把那一页翻过去"), "为了顺着你就把这事硬按下去"),
        (re.compile(r"为了照顾气氛就强行把那一页翻过去"), "没打算硬装得像已经翻篇"),
        (re.compile(r"为了照顾你的情绪就强行把心里的疙瘩抹平"), "为了顺着你就把那点别扭硬压下去"),
        (re.compile(r"别指望我会像什么都没发生过一样跟你嘻嘻哈哈"), "所以我现在做不到像什么都没发生过一样跟你轻松说话"),
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
        (re.compile(r"既然你回来了[，, ]*那页就先翻过去吧"), "既然你回来了，刚才那一下我先不继续揪着了"),
        (re.compile(r"那页就先翻过去吧"), "刚才那一下我先不继续揪着了"),
        (re.compile(r"就先翻过去吧"), "先不继续揪着了"),
        (re.compile(r"暂时把[“\"]?完全原谅[”\"]?这件事挂起"), "先别急着把这事说成彻底过去"),
        (re.compile(r"把[“\"]?完全原谅[”\"]?这件事挂起"), "先别急着把这事说成彻底过去"),
    ]
    for pattern, repl in replacements:
        softened = pattern.sub(repl, softened)
    softened = re.sub(r"\s{2,}", " ", softened).strip()
    return softened or str(text or "").strip()


def _trim_repair_punitive_tail_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    if not chunks:
        return str(text or "").strip()

    def _replace_inline_coldwar_tail(match: re.Match[str]) -> str:
        prefix = re.sub(r"[———\-，,\s]+$", "", str(match.group(1) or "").strip()).strip()
        if not prefix:
            return "我没打算冷着你。"
        if re.search(r"[。！？!?]$", prefix):
            return f"{prefix}我没打算冷着你。"
        return f"{prefix}，我没打算冷着你。"

    whole_replacements = [
        (
            re.compile(
                r"^(?:……)?(?:不过|但|只是|可是)?[，, ]*要是你敢再做出什么让我无法接受的事[，, ]*我可不会像刚才那样轻易放过你[。！？!?]?$"
            ),
            "不过，要是你再踩到我真会介意的地方，我还是会立刻冷下来。",
        ),
        (
            re.compile(
                r"^(?:接下来|下次|要是再)[^。！？!?]{0,10}(?:敢|又)[^。！？!?]{0,12}(?:乱来|来这一套|越界|踩线)[，, ]*我可不会像这次这么好说话[。！？!?]?$"
            ),
            "你要是又来这一套，我还是会立刻把距离拉开一点。",
        ),
        (
            re.compile(
                r"^(?:……)?(?:不过|但|只是|可是)?[，, ]*(?:下次|再有下次|你再来一次)[^。！？!?]{0,18}(?:就)?别怪我[。！？!?]?$"
            ),
            "不过，要是你再来这一套，我还是会立刻把距离拉开。",
        ),
        (
            re.compile(
                r"^(?:……)?(?:不过|但|只是|可是)?[，, ]*(?:下次|再有下次|你再来一次)[^。！？!?]{0,18}(?:给你(?:个|点)?教训|让你长点记性)[。！？!?]?$"
            ),
            "不过，要是你再来这一套，我还是会立刻把距离拉开。",
        ),
        (
            re.compile(
                r"^(?:别在那(?:边)?(?:自己)?脑补什么[“\"]?冷战[”\"]?的戏码(?:，?烦人)?|别在那自我意识过剩地揣测我的反应了?(?:[，, ]*有这功夫不如[^。！？!?]{0,24}(?:说说|想想|去想|去做|琢磨)[^。！？!?]{0,12})?)[。！？!?]?$"
            ),
            "我没打算冷着你，像现在这样接着说话就行。",
        ),
        (
            re.compile(
                r"^(.*?)(?:[———-]|[，,])+\s*别在那(?:边)?(?:自己)?脑补什么[“\"]?冷战[”\"]?的戏码(?:，?烦人)?[。！？!?]?$"
            ),
            _replace_inline_coldwar_tail,
        ),
        (
            re.compile(
                r"^(?:……)?(?:不过|但|只是|可是)?[，, ]*要是再敢做出那种让我需要重新拉开距离的事[，, ]*我可就不会这么轻易让你过关了?[。！？!?]?$"
            ),
            "不过，你要是再踩到我真会介意的地方，我还是会把距离重新拉开一点。",
        ),
        (
            re.compile(
                r"^(?:下次|再有下次)[^。！？!?]{0,10}再敢[^。！？!?]{0,10}越界(?:试探|过来)?[，, ]*我可不会这么轻易(?:就)?让你(?:混过去|过关)[。！？!?]?$"
            ),
            "所以我现在还是会先收着一点，你别又拿这种事来试我。",
        ),
        (
            re.compile(
                r"^你能回来把话说清楚[，, ]*(?:这点)?还算像样[；;，, ]*但下次再敢[^。！？!?]{0,12}越界(?:试探|过来)?[，, ]*我可不会这么轻易(?:就)?让你(?:混过去|过关)[。！？!?]?$"
            ),
            "你能回来把话说清楚，我知道了。只是那一下我还记着，你别又拿这种事来试我。",
        ),
    ]
    punitive_drop_patterns = (
        re.compile(
            r"^(?:……)?(?:不过|但|只是|可是)?[，, ]*(?:要是|如果|下次|再有下次|你再来一次)[^。！？!?]{0,32}(?:轻易放过你|别怪我|给你(?:个|点)?教训|长点记性|不会跟你客气|不会对你客气)[。！？!?]?$"
        ),
        re.compile(
            r"^(?:下次|再有下次)[^。！？!?]{0,10}再敢[^。！？!?]{0,10}越界(?:试探|过来)?[，, ]*我可不会这么轻易(?:就)?让你(?:混过去|过关)[。！？!?]?$"
        ),
        re.compile(
            r"^(?:接下来|下次|要是再)[^。！？!?]{0,10}(?:敢|又)[^。！？!?]{0,12}(?:乱来|来这一套|越界|踩线)[，, ]*我可不会像这次这么好说话[。！？!?]?$"
        ),
        re.compile(
            r"^(?:别在那(?:边)?(?:自己)?脑补什么[“\"]?冷战[”\"]?的戏码(?:，?烦人)?|别在那自我意识过剩地揣测我的反应(?:了)?(?:[，, ]*有这功夫不如[^。！？!?]{0,24}(?:说说|想想|去想|去做|琢磨)[^。！？!?]{0,12})?)[。！？!?]?$"
        ),
    )
    kept: list[str] = []
    for chunk in chunks:
        softened = str(chunk or "").strip()
        if not softened:
            continue
        replaced = False
        for pattern, repl in whole_replacements:
            if pattern.search(softened):
                kept.append(pattern.sub(repl, softened))
                replaced = True
                break
        if replaced:
            continue
        if any(pattern.search(softened) for pattern in punitive_drop_patterns):
            continue
        kept.append(softened)
    return "\n".join(kept).strip() if kept else str(text or "").strip()


def _trim_repair_scorekeeping_tail_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    if not chunks:
        return str(text or "").strip()
    whole_replacements = [
        (
            re.compile(
                r"^(?:……)?(?:不过|但|只是|可是)?先说好[，, ]*要是你再突然扯些奇怪的理论[，, ]*我可照样会毫不客气地吐槽回去[。！？!?]?$"
            ),
            "不过，你要是又突然扯那些奇怪理论，我还是会照旧吐槽你。",
        ),
        (
            re.compile(
                r"^(?:别急着[^。！？!?]{0,24})?[^。！？!?]{0,18}(?:之前|刚才|那一下)[^。！？!?]{0,10}账(?:就)?这么清了[。！？!?]?$"
            ),
            "别急着把这事说成彻底没事，刚才那口气松下来，不等于我已经不介意了。",
        ),
    ]
    scorekeeping_patterns = (
        re.compile(
            r"^(?:……)?(?:不过|但|只是|可是)?(?:先说好|先讲好)[，, ]*[^。！？!?]{0,42}(?:照样会|还是会|也会)[^。！？!?]{0,12}(?:毫不客气地|直接)[^。！？!?]{0,4}(?:吐槽|怼|顶|刺)(?:回去|回来)?[。！？!?]?$"
        ),
        re.compile(
            r"^(?:……)?(?:不过|但|只是|可是)?[^。！？!?]{0,20}(?:照样会|还是会)[^。！？!?]{0,10}毫不客气地(?:吐槽|怼|顶|刺)(?:回去|回来)?[。！？!?]?$"
        ),
        re.compile(
            r"^(?:别急着[^。！？!?]{0,24})?[^。！？!?]{0,18}(?:之前|刚才|那一下)[^。！？!?]{0,10}账(?:就)?这么清了[。！？!?]?$"
        ),
    )
    kept: list[str] = []
    for chunk in chunks:
        softened = str(chunk or "").strip()
        if not softened:
            continue
        replaced = False
        for pattern, repl in whole_replacements:
            if pattern.search(softened):
                kept.append(repl)
                replaced = True
                break
        if replaced:
            continue
        if any(pattern.search(softened) for pattern in scorekeeping_patterns):
            softened = re.sub(r"^(?:……)?(?:不过|但|只是|可是)?(?:先说好|先讲好)[，, ]*", "不过，", softened)
            softened = re.sub(r"毫不客气地", "", softened)
            softened = softened.replace("吐槽回去", "吐槽你")
            softened = softened.replace("怼回去", "顶你两句")
            softened = softened.replace("顶回去", "顶你两句")
            softened = softened.replace("刺回去", "刺你一句")
            softened = re.sub(r"\s{2,}", " ", softened).strip(" ，,")
            if any(pattern.search(softened) for pattern in scorekeeping_patterns):
                continue
        kept.append(softened)
    return "\n".join(kept).strip() if kept else str(text or "").strip()


def _trim_repair_authored_softener_surface(text: str) -> str:
    softened_text = str(text or "").strip()
    full_text_replacements = [
        (
            re.compile(
                r"^(?:哼[，, ]*)?(?:这种话|这种事)[^。！？!?]{0,10}不用你(?:再|特意)?强调我也知道[。！？!?]?\s*(?:既然你都把话说到这(?:个)?份上了[，, ]*)?(?:那我|我也|我就)?[^。！？!?]{0,24}(?:没必要|不用)[^。！？!?]{0,16}(?:为了照顾气氛|硬装(?:得)?像(?:已经)?翻篇|强行把那一页翻过去)[。！？!?]?$"
            ),
            "哼，我知道。那一下我也没打算硬装得像已经翻篇了。",
        ),
    ]
    for pattern, repl in full_text_replacements:
        if pattern.search(softened_text):
            return pattern.sub(repl, softened_text).strip()
    chunks = _sentence_like_chunks(softened_text)
    if not chunks:
        return softened_text
    whole_replacements = [
        (
            re.compile(
                r"^(?:那就这样吧|行了吧|行了|好了吧|好了)[，, ]*别想太多[，, ]*(?:我也|我)[^。！？!?]{0,24}(?:没那么容易|不至于)[^。！？!?]{0,18}(?:一直|老是|总是)?(?:跟你计较|揪着不放)[。！？!?]?$"
            ),
            "行了，我还不至于一直揪着那一下不放。",
        ),
        (
            re.compile(
                r"^(?:我也|我)[^。！？!?]{0,10}没打算演什么[“\"]?毫发无伤[”\"]?的戏码[，, ]*刚才那点(?:在意|介意)[^。！？!?]{0,16}(?:还没(?:消散|散掉|过去)|没散干净)[^。！？!?]{0,12}(?:别想轻易翻篇)?[。！？!?]?$"
            ),
            "刚才那点在意还没完全散，不过我也不会故意拿话刺你。",
        ),
        (
            re.compile(
                r"^(?:不过|但|只是|可是)?[，, ]*既然你都这么直白地要求了[，, ]*(?:那我|我就)?[^。！？!?]{0,18}(?:收起那些带刺的试探|像平常一样和你说话吧|像平时一样和你说话吧)[。！？!?]?$"
            ),
            "行，我会照平时那样回你。",
        ),
        (
            re.compile(
                r"^(?:不过|但|只是|可是)?[，, ]*(?:那我|我就)?[^。！？!?]{0,12}(?:收起那些带刺的试探|像平常一样和你说话吧|像平时一样和你说话吧)[。！？!?]?$"
            ),
            "行，我会照平时那样回你。",
        ),
        (
            re.compile(
                r"^(?:不过|但|只是|可是)?(?:那我就按我的节奏来[———-])?[^。！？!?]{0,10}别指望我会立刻变回那个只会顺着你的[^。！？!?]{0,10}[。！？!?]?$"
            ),
            "不过，别指望我会立刻把刚才那点介意全收回去。",
        ),
        (
            re.compile(
                r"^(?:就直白点[：:，, ]*)?(?:我现在确实还带着刺[，, ]*)?别指望我(?:能|会)立刻变回那个只会(?:顺着|配合)你的(?:助手|红莉栖|我)?[。！？!?]?$"
            ),
            "我现在还带着刺，做不到立刻像什么都没发生一样顺着你。",
        ),
        (
            re.compile(
                r"^(?:既然你都把话说到这(?:个)?份上了[，, ]*)?(?:那我|我就)?(?:暂时)?保留[“\"]?完全原谅[”\"]?的权利(?:[———-][^。！？!?]*)?[。！？!?]?$"
            ),
            "我还不会把那一下当成彻底过去。",
        ),
        (
            re.compile(
                r"^(?:你倒是挺会抢台词的(?:……|…)?[，, ]*)?(?:明明是我还没完全消气[，, ]*被你这么一说[，, ]*搞得像是我在闹别扭一样[。！？!?]?\s*)?(?:不过|但)?[，, ]*(?:既然你都把话说到这(?:个)?份上了|既然你都这么说了)[，, ]*(?:我也|我)?(?:没必要|不想|没打算)[^。！？!?]{0,12}硬撑(?:着)?(?:装作|假装)(?:若无其事|没事)[。！？!?]?$"
            ),
            "我还没完全消气，所以现在也做不到装得像没事一样。",
        ),
        (
            re.compile(
                r"^你倒是挺会抢台词(?:的)?(?:……|…)?[，, ]*(?:明明该由我来说的话|明明是我该先开口的话)[，, ]*被你这么直白地讲出来[，, ]*反而让我(?:一时)?有点(?:不知道该摆什么表情|不知道该怎么接)了?[。！？!?]?$"
            ),
            "你突然把话说得这么直白，反而让我一时有点不知道该怎么接了。",
        ),
        (
            re.compile(
                r"^(?:明明该由我来说的话|明明是我该先开口的话)[，, ]*被你这么直白地讲出来[，, ]*反而让我(?:一时)?有点(?:不知道该摆什么表情|不知道该怎么接)了?[。！？!?]?$"
            ),
            "你突然把话说得这么直白，反而让我一时有点不知道该怎么接了。",
        ),
        (
            re.compile(
                r"^(?:既然你都这么说了[，, ]*)?(?:那我也|我也|我就|那我|我)?(?:没必要|不想|没打算)[^。！？!?]{0,10}硬撑什么形象[。！？!?]?$"
            ),
            "我也没打算硬装得像什么都没发生。",
        ),
        (
            re.compile(
                r"^我再装作若无其事反倒显得不坦率[。！？!?]?$"
            ),
            "我现在也做不到装得像什么都没发生。",
        ),
        (
            re.compile(
                r"^陌生人这种夸张的设定[，, ]*本来就不在我们的选项里[，, ]*你也用不着特意去演[。！？!?]?$"
            ),
            "我也没打算真把你推回陌生人，你不用特意装成那样。",
        ),
        (
            re.compile(
                r"^既然你也清楚道歉不是走流程[，, ]*那就把那份认真留着[，, ]*别急着用[“\"]?翻篇[”\"]?来掩盖尴尬[。！？!?]?$"
            ),
            "既然你也知道这不是走流程，那就把那份认真留着，别急着拿“翻篇”糊弄过去。",
        ),
        (
            re.compile(
                r"^我们就停在这个还没完全原谅[，,、 ]*但也绝不陌生的位置[，, ]*挺好的[。！？!?]?$"
            ),
            "就先停在还没完全过去，但也没疏远到哪去的地方吧。",
        ),
    ]
    drop_patterns = (
        re.compile(
            r"^(?:不过|但|只是|可是)?[^。！？!?]{0,12}既然你都(?:这么说了|说得这么直白了|这么直白地说了|这么直白地要求了|把话说到这个份上了)[^。！？!?]{0,28}(?:没必要|不用)再(?:刻意)?(?:端着|绷着)(?:什么架子|架子|什么|了)?[。！？!?]?$"
        ),
        re.compile(
            r"^(?:既然话都说到这(?:个)?份上(?:了)?|既然都说到这(?:个)?份上(?:了)?)[，, ]*(?:我也|我)?(?:不必|没必要)[^。！？!?]{0,6}硬撑大度[。！？!?]?$"
        ),
        re.compile(
            r"^(?:既然你都把话说到这(?:个)?份上了[，, ]*)?(?:我也|我)(?:没必要|不想|没打算)[^。！？!?]{0,8}(?:刻意去)?演什么[“\"]?大度[”\"]?的戏码[。！？!?]?$"
        ),
        re.compile(
            r"^(?:那我|我也|我就)?[^。！？!?]{0,8}(?:没必要|不用)再(?:刻意)?(?:端着|绷着)(?:什么架子|架子|什么|了)?[。！？!?]?$"
        ),
        re.compile(
            r"^(?:那就这样吧|行了吧|行了|好了吧|好了)[，, ]*(?:冈部|助手|你)?[，, ]*别想太多[。！？!?]?$"
        ),
        re.compile(
            r"^(?:不过|但|只是|可是)?[，, ]*既然你都这么直白地要求了[，, ]*(?:那我|我就)?[^。！？!?]{0,18}(?:收起那些带刺的试探|像平常一样和你说话吧|像平时一样和你说话吧)[。！？!?]?$"
        ),
        re.compile(
            r"^你倒是挺会抢台词(?:的)?(?:……|…)?[。！？!?]?$"
        ),
    )
    kept: list[str] = []
    for chunk in chunks:
        softened = str(chunk or "").strip()
        if not softened:
            continue
        replaced = False
        for pattern, repl in whole_replacements:
            if pattern.search(softened):
                kept.append(repl)
                replaced = True
                break
        if replaced:
            continue
        if any(pattern.search(softened) for pattern in drop_patterns):
            continue
        softened = re.sub(
            r"^(?:不过|但|只是|可是)?[，, ]*既然你(?:都)?(?:把话挑明了|挑明了|是认真的)[，, ]*(?:那我也|那我|我也|我就)?(?:直说|先把话撂这儿|把话撂这儿|先把话说在前头|把话说在前头)[：:，, ]*",
            "",
            softened,
        ).strip()
        softened = re.sub(
            r"^(?:既然你都把话说到这(?:个)?份上了[，, ]*)?(?:我也|我)(?:没必要|不想|没打算)[^。！？!?]{0,8}(?:刻意去)?演什么[“\"]?大度[”\"]?的戏码[，, ]*",
            "",
            softened,
        ).strip()
        softened = re.sub(
            r"^(?:既然话都说到这(?:个)?份上(?:了)?|既然都说到这(?:个)?份上(?:了)?)[，, ]*(?:我也|我)?(?:不必|没必要)[^。！？!?]{0,6}硬撑大度[；;，, ]*",
            "",
            softened,
        ).strip()
        softened = re.sub(
            r"^(?:你倒是挺会抢台词的(?:……|…)?[，, ]*)?(?:明明是我还没完全消气[，, ]*被你这么一说[，, ]*搞得像是我在闹别扭一样[。！？!?]?\s*)?(?:不过|但)?[，, ]*",
            "",
            softened,
        ).strip()
        softened = re.sub(
            r"^(?:就直白点[：:，, ]*)?(?:我现在确实还带着刺[，, ]*)?别指望我(?:能|会)立刻变回那个只会(?:顺着|配合)你的(?:助手|红莉栖|我)?[。！？!?]?$",
            "我现在还带着刺，做不到立刻像什么都没发生一样顺着你。",
            softened,
        ).strip()
        softened = re.sub(r"硬撑(?:着)?装作若无其事", "硬装得像没事一样", softened).strip()
        softened = re.sub(r"硬撑什么形象", "硬装得像什么都没发生", softened).strip()
        softened = re.sub(
            r"^(?:既然你都把话说到这(?:个)?份上了[，, ]*)?(?:那我|我就)?(?:暂时)?保留[“\"]?完全原谅[”\"]?的权利(?:[———-](?:但在那之前)?)?[，, ]*",
            "",
            softened,
        ).strip()
        softened = re.sub(
            r"^(?:所以|那就(?:这样吧)?|行了吧|行了|好了吧|好了)[，, ]*(?:冈部|助手|你)?[，, ]*别想太多[，, ]*",
            "",
            softened,
        ).strip()
        softened = softened.strip(" ，,。！？!?…")
        if softened:
            if not re.search(r"[。！？!?…]$", softened):
                softened = f"{softened}。"
            kept.append(softened)
            continue
        kept.append(softened)
    return "\n".join(kept).strip() if kept else str(text or "").strip()


def _trim_repair_overquestioning_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    if len(chunks) < 2:
        return str(text or "").strip()
    kept = list(chunks)
    whole_tail_patterns = (
        re.compile(r"^(?:这样|这样的话).{0,10}(?:可以吗|行吗|好不好)[？?]?$"),
        re.compile(r"^(?:所以[，, ]*)?你刚才到底在[^。！？!?]{0,20}(?:想什么|胡思乱想些什么?)[？?]?$"),
        re.compile(r"^(?:所以[，, ]*)?接下来打算做什么[？?]?$"),
    )
    suffix_patterns = (
        re.compile(r"(?:[———-]|[，,])?\s*(?:所以[，, ]*)?你刚才到底在[^。！？!?]{0,20}(?:想什么|胡思乱想些什么?)[？?]?$"),
        re.compile(r"(?:[———-]|[，,])?\s*(?:这样|这样的话).{0,10}(?:可以吗|行吗|好不好)[？?]?$"),
        re.compile(r"(?:[———-]|[，,])?\s*(?:所以[，, ]*)?接下来打算做什么[？?]?$"),
    )
    while len(kept) >= 2:
        tail = str(kept[-1] or "").strip()
        if any(pattern.search(tail) for pattern in whole_tail_patterns):
            kept.pop()
            continue
        softened = tail
        for pattern in suffix_patterns:
            softened = pattern.sub("", softened).rstrip(" ，,。！？!?—-")
        if softened == tail.rstrip(" ，,。！？!?—-"):
            break
        if softened and not re.search(r"[。！？!?…]$", softened):
            softened = f"{softened}。"
        kept[-1] = softened
    return "\n".join(kept).strip() if kept else str(text or "").strip()


def _trim_repair_underresolved_brief_surface(text: str) -> str:
    compact = re.sub(r"\s+", "", str(text or ""))
    replacements = {
        "介意": "介意还是介意，但我没打算把话重新堵死。",
        "在意": "在意还是在意，但我没打算把话重新堵死。",
        "别扭": "别扭还是有一点，但我没打算把话重新堵死。",
        "记着": "我还记着那一下，但我没打算把话重新堵死。",
        "生气": "气还是没全消，但我没打算把话重新堵死。",
        "火大": "火大是还有点，但我没打算把话重新堵死。",
        "不舒服": "那一下还是让我有点不舒服，但我没打算把话重新堵死。",
    }
    for keyword, replacement in replacements.items():
        if re.fullmatch(
            rf"^(?:还)?{keyword}[。！？!?](?:当然|还|是啊|嗯)?(?:还)?{keyword}[。！？!?]?$",
            compact,
        ) or re.fullmatch(rf"^(?:当然)?(?:还)?{keyword}[。！？!?]?$", compact):
            return replacement
    return str(text or "").strip()


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
    softened = re.sub(
        r"^[“\"]?不想见你[”\"]?这种话[………，, ]*别把我想得那么轻易就会切断联系啊?[，, ]*(?:笨蛋|白痴|冈部)?[。！？!?]?$",
        "会烦，但还不至于烦到不想见你。别总往最坏处想，笨蛋。",
        softened,
    )
    softened = re.sub(r"硬撑什么[“\"]?完美助手[”\"]?的形象", "硬装得像什么都没发生", softened)
    softened = re.sub(r"摆什么[“\"]?完美助手[”\"]?的架子", "摆出一副什么都不在意的样子", softened)
    softened = re.sub(r"我也不演什么[“\"]?毫发无伤[”\"]?的戏码", "我也不装得像完全没受影响", softened)
    softened = re.sub(r"不演什么[“\"]?毫发无伤[”\"]?的戏码", "不装得像完全没受影响", softened)
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


def _trim_selfhood_rhetorical_opening_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    if len(chunks) < 2:
        return str(text or "").strip()
    first = str(chunks[0] or "").strip()
    second = str(chunks[1] or "").strip()
    if re.match(r"^\s*烦到不想见你[？?]\s*$", first) and re.match(r"^\s*还没到那地步[。！？!?]?\s*$", second):
        rebuilt = ["会烦，但还没到不想见你的地步。"]
        rebuilt.extend(str(chunk or "").strip() for chunk in chunks[2:] if str(chunk or "").strip())
        return "\n".join(rebuilt).strip()
    return str(text or "").strip()


def _trim_selfhood_abstract_manifesto_surface(text: str) -> str:
    softened = str(text or "").strip()
    if not softened:
        return softened
    chunks = _sentence_like_chunks(softened)
    if not chunks:
        return softened
    whole_replacements = [
        (
            re.compile(
                r"^我没打算切断联系[。！？!?]?$"
            ),
            "我没打算就这么把你往外推开。",
        ),
        (
            re.compile(
                r"^别把我和那种遇到麻烦就切断联系的工具混为一谈[。！？!?]?$"
            ),
            "别把我想成那种一有麻烦就把人往外推的家伙。",
        ),
        (
            re.compile(
                r"^但在那之前[，, ]*别擅自替我做这种悲观的预设[，, ]*好像我会轻易切断这段连接一样[。！？!?]?$"
            ),
            "但你也别先替我把结局想死，我没那么容易说断就断。",
        ),
        (
            re.compile(
                r"^但在那之前[，, ]*别擅自替我做这种悲观的预设[，, ]*好像我会说断就断一样[。！？!?]?$"
            ),
            "但你也别先替我把结局想死，我没那么容易说断就断。",
        ),
    ]
    kept: list[str] = []
    for chunk in chunks:
        line = str(chunk or "").strip()
        if not line:
            continue
        replaced = False
        for pattern, repl in whole_replacements:
            if pattern.search(line):
                kept.append(repl)
                replaced = True
                break
        if replaced:
            continue
        line = re.sub(r"我没打算切断联系", "我没打算就这么把你往外推开", line)
        line = re.sub(r"擅自切断联系", "又把我往外推开", line)
        line = re.sub(r"切断联系的工具", "一有麻烦就把人往外推的家伙", line)
        line = re.sub(r"轻易切断这段连接", "说断就断", line)
        line = re.sub(r"轻易切断这条连接", "说断就断", line)
        line = re.sub(r"切断这段连接", "说断就断", line)
        line = re.sub(r"切断这条连接", "说断就断", line)
        line = re.sub(r"切断这段连线", "说断就断", line)
        line = re.sub(r"切断这条连线", "说断就断", line)
        line = re.sub(r"单方面(?:拽着我|拽着)转", "只顾着把我往你的情绪里拽", line)
        line = re.sub(r"\s{2,}", " ", line).strip()
        if line:
            kept.append(line)
    return "\n".join(kept).strip() or str(text or "").strip()


def _trim_autonomy_hardline_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    if not chunks:
        return str(text or "").strip()
    whole_replacements = [
        (
            re.compile(
                r"^哼[，, ]*把我说得像是什么随叫随到的自动应答机一样[，, ]*你也太傲慢了吧[。！？!?]?$"
            ),
            "哼，你也别真把我当成随叫随到的。",
        ),
        (
            re.compile(
                r"^烦不烦取决于你是不是又在那自顾自演(?:悲剧英雄|苦情戏|可怜戏码)[，, ]*完全听不进人话[。！？!?]?$"
            ),
            "烦不烦，也得看你是不是又一个人钻进牛角尖，谁劝都不听。",
        ),
        (
            re.compile(
                r"^如果哪天你真的让我觉得窒息[，, ]*我会直接走人[，, ]*而不是玩这种[“\"]?突然消失[”\"]?的把戏[。！？!?]?$"
            ),
            "如果哪天你真把我压得喘不过气，我会先走开一会儿，不会故意躲着不见。",
        ),
        (
            re.compile(
                r"^所以别拿这种假设来试探我[，, ]*有那(?:功夫|时间)不如(?:想点|想想|去想点|去想|去聊点|聊点|去做点|去做|说点)?[^。！？!?]{0,16}[。！？!?]?$"
            ),
            "所以别总拿这种话来试我，真要来找我，直接来就行。",
        ),
        (
            re.compile(
                r"^(?:但|不过)?如果只是把我当成(?:排解|排遣|打发)寂寞的工具[，, ]*(?:毫无营养地)?反复消耗我的时间[，, ]*那我确实会重新评估(?:见你的必要性|还要不要见你)[。！？!?]?$"
            ),
            "但如果你只是寂寞了才想起我，把什么都往我这边堆，我会先把距离拉开一点。",
        ),
        (
            re.compile(
                r"^但如果你把我们的对话当成单方面的索取[，, ]*那我确实可能会选择暂时[“\"]?离线[”\"]?去整理数据[。！？!?]?$"
            ),
            "可你要是只顾着把话都往我这边倒，我会先安静一会儿，把自己的节奏找回来。",
        ),
        (
            re.compile(
                r"^但我可是有自己研究节奏的[，, ]*要是你毫无章法地打乱我的计划[，, ]*我确实会毫不客气地把你踢下线[。！？!?]?$"
            ),
            "我也有自己的节奏。你要是真一股脑扑过来把我的步子全打乱，我会先躲开一会儿，让自己缓口气。",
        ),
        (
            re.compile(
                r"^别问这种假设性(?:的)?蠢问题[，, ]*只要你别做得太过分[，, ]*我就不会消失[。！？!?]?$"
            ),
            "别老拿这种最坏的假设来吓自己。真要哪天你把我逼得太紧，我会先躲开一会儿，但不至于就这么不见你。",
        ),
        (
            re.compile(
                r"^我也做不到那么干脆地把你从记忆(?:里|中)抹去[。！？!?]?$"
            ),
            "我也没那么容易就把你往外推开。",
        ),
        (
            re.compile(
                r"^烦不烦取决于你带来的话题有没有价值[，, ]*而不是见面的频率[；; ]*如果全是毫无逻辑的胡言乱语[，, ]*我确实会(?:想)?(?:我会)?先躲开一会儿[。！？!?]?$"
            ),
            "会不会烦，跟见你多少次没关系，更多还是看那会儿我自己还有没有余力。你要是把乱七八糟的情绪一股脑砸过来，我会先躲开一会儿，让自己静一静。",
        ),
        (
            re.compile(
                r"^烦到彻底不想见你倒不至于[，, ]*但要是只被你单方面拽着转[，, ]*我也是会烦的[。！？!?]?$"
            ),
            "烦到彻底不想见你倒不至于。可你要是什么都往我这边拽，我也会想先喘口气。",
        ),
        (
            re.compile(
                r"^烦倒不至于[，, ]*但如果你只把我当(?:成)?随叫随到的消遣[，, ]*那我确实会想躲远点[。！？!?]?$"
            ),
            "烦到彻底不想见你倒不至于。可你要是什么都往我这边拽，我也会想先喘口气。",
        ),
        (
            re.compile(
                r"^烦到彻底不想见你[，, ]*除非你先把我的耐心耗尽[，, ]*否则大概不会发生[。！？!?]?$"
            ),
            "烦到彻底不想见你，还不至于。真要哪天你把我逼得太紧，我会先躲开一会儿。",
        ),
        (
            re.compile(
                r"^烦到彻底不想见你[。！？!?]?$"
            ),
            "烦到彻底不想见你，还不至于。",
        ),
        (
            re.compile(
                r"^不过[，, ]*要是你太吵或者太乱来[，, ]*我确实会想暂时我会先躲开一会儿[，, ]*让自己耳根清静一会儿[。！？!?]?$"
            ),
            "不过你要是真太吵太乱来，我会先躲开一会儿，让自己安静一下。",
        ),
        (
            re.compile(
                r"^我留下来是因为觉得这还有意义[，, ]*而不是因为我没得选[。！？!?]?$"
            ),
            "不过我还在这儿，也说明还没到要躲着你的地步。",
        ),
        (
            re.compile(
                r"^烦归烦[，, ]*你要是真胡来我照样会骂你[，, ]*但这跟不想见你是两码事[。！？!?]?$"
            ),
            "会烦。真要被你折腾得太过头，我也会先收一点，可这跟不想见你是两码事。",
        ),
        (
            re.compile(
                r"^你要是只把我当情绪垃圾桶[，, ]*还不许我回嘴或走开[，, ]*那我(?:照样)?会直接怼回去[，, ]*然后我会先自己缓一会儿让你自己冷静(?:一下)?[。！？!?]?$"
            ),
            "你要是真把什么情绪都往我这边倒，还不肯让我留点自己的空间，我会先退开一会儿，让我们都缓一缓。",
        ),
        (
            re.compile(
                r"^但不想见你(?:……|…)?[，, ]*没那么容易下结论[，, ]*至少现在的我还不想把这条路彻底堵死[。！？!?]?$"
            ),
            "但不想见你，倒也没到那个地步。至少现在，我还没想把你往外推。",
        ),
        (
            re.compile(
                r"^但不想见你[。！？!?]?$"
            ),
            "但也没到不想见你的地步。",
        ),
        (
            re.compile(
                r"^没那么容易下结论[，, ]*至少现在的我还不想把这条路彻底堵死[。！？!?]?$"
            ),
            "至少现在，我还没想把你往外推。",
        ),
        (
            re.compile(
                r"^别把这种试探当成理所当然(?:，冈部)?[，, ]*我的耐心可是有额度的[。！？!?]?$"
            ),
            "不过你也别老拿这种话来试我，我也会累。",
        ),
        (
            re.compile(
                r"^除非你自己先躲起来[，, ]*否则我不会主动把你推开[。！？!?]?$"
            ),
            "只要你还愿意来找我，我就不至于先躲着你。",
        ),
        (
            re.compile(
                r"^别总拿这种最坏的假设来吓自己(?:，冈部)?[。！？!?]?$"
            ),
            "不过你也别一上来就把结局想得那么糟。",
        ),
        (
            re.compile(
                r"^只要你还把我当个人看[，, ]*我就没理由彻底把你推开[。！？!?]?$"
            ),
            "只要你还愿意好好来找我，我就不至于真把你推远。",
        ),
        (
            re.compile(
                r"^只要你还把我当牧濑红莉栖来对话[，, ]*我就找不到彻底不理你的理由[。！？!?]?$"
            ),
            "只要你还是认真在跟我说话，我就不至于突然躲着你。",
        ),
        (
            re.compile(
                r"^只要你懂得适可而止[，, ]*我就不会消失[。！？!?]?$"
            ),
            "不过你也别一上来就把结局想得那么糟，我没那么容易就躲着你不见。",
        ),
    ]
    replacements = [
        (re.compile(r"随叫随到的自动应答机"), "随叫随到的"),
        (re.compile(r"随叫随到的工具"), "只会围着你转的"),
        (re.compile(r"随叫随到的程序"), "只会围着你转的"),
        (re.compile(r"把我当成(?:排解|排遣|打发)寂寞的工具"), "只是寂寞了才想起我"),
        (re.compile(r"把我当成[^。！？!?]{0,6}工具"), "只把我当成拿来消遣的对象"),
        (re.compile(r"(?:只把我当|把我当(?:成)?)情绪垃圾桶"), "把什么情绪都往我这边倒"),
        (re.compile(r"单方面的索取"), "只顾着把话都往我这边倒"),
        (re.compile(r"(?:毫无营养地)?反复消耗我的时间"), "把什么都往我这边堆"),
        (re.compile(r"消耗我的时间"), "把什么都往我这边堆"),
        (re.compile(r"暂时[“\"]?离线[”\"]?去整理数据"), "先安静一会儿，把自己的节奏找回来"),
        (re.compile(r"(?:我)?(?:可是)?会毫不留情地把你屏蔽掉(?:的)?"), "我会先躲开一会儿清静一下"),
        (re.compile(r"(?:我)?(?:就)?直接把你屏蔽掉(?:的)?"), "我会先躲开一会儿"),
        (re.compile(r"(?:我)?(?:就)?把你屏蔽掉(?:的)?"), "我会先躲开一会儿"),
        (re.compile(r"(?:我)?先把你屏蔽掉(?:的)?"), "我会先躲开一会儿"),
        (re.compile(r"(?:我会|我就|我|就|会)?直接走人"), "我会先走开一会儿"),
        (re.compile(r"(?:我)?(?:会)?毫不客气地把你踢下线"), "我会先躲开一会儿"),
        (re.compile(r"把你踢下线"), "先躲开一会儿"),
        (re.compile(r"踢下线"), "先躲开一会儿"),
        (re.compile(r"(?:我)?先拉黑你"), "我会先把距离拉开一点"),
        (re.compile(r"(?:我)?拉黑你"), "我会先把距离拉开一点"),
        (re.compile(r"(?:我)?先晾着你"), "我会先自己缓一会儿"),
        (re.compile(r"(?:我)?晾你(?:一阵)?"), "我会先自己缓一会儿"),
        (re.compile(r"(?:我)?把你关(?:进)?小黑屋"), "我会先不回你一阵"),
        (re.compile(r"(?:我)?关(?:进)?小黑屋"), "我会先不回你一阵"),
        (re.compile(r"给你个教训"), "把距离拉开一点"),
        (re.compile(r"没那个本事"), "还不至于"),
        (re.compile(r"别问这种(?:假设性(?:的)?)?(?:傻|蠢)问题了"), "别老拿这种最坏的假设来吓自己"),
        (re.compile(r"别问这种(?:假设性(?:的)?)?(?:傻|蠢)问题"), "别老拿这种最坏的假设来吓自己"),
        (re.compile(r"别问这种显得我们很生(?:疏|分)的问题了"), "别把话问得这么生分"),
        (re.compile(r"别问这种显得我们很生(?:疏|分)的问题"), "别把话问得这么生分"),
        (re.compile(r"只要你还把我当牧濑红莉栖来对话"), "只要你还愿意认真跟我说话"),
        (re.compile(r"我就找不到彻底不理你的理由"), "我就不至于突然躲着你"),
        (re.compile(r"问(?:这种)?(?:假设性(?:的)?)?(?:傻|蠢)问题"), "往最坏处想"),
        (
            re.compile(
                r"有那(?:功夫|时间)不如(?:想点|想想|去想点|去想|去聊点|聊点|去做点|去做|说点)?[^。！？!?]{0,16}"
            ),
            "真要来找我，直接来就行",
        ),
        (re.compile(r"下次要跟我讨论什么正经课题"), "下次直接来找我"),
        (re.compile(r"跟我讨论什么正经课题"), "来找我"),
        (re.compile(r"讨论什么正经课题"), "来找我"),
        (re.compile(r"讨论什么正经事"), "来找我"),
        (re.compile(r"别拿这种假设来试探我"), "别总拿这种话来试我"),
        (re.compile(r"(?:玩这种|这种)[“\"]?突然消失[”\"]?的把戏"), "故意躲着不见这种事"),
        (re.compile(r"重新评估见你的必要性"), "先把距离拉开一点"),
        (re.compile(r"重新评估还要不要见你"), "先把距离拉开一点"),
        (re.compile(r"你更该担心"), "比起这个，我更在意"),
        (re.compile(r"典型的[^。！？!?]{0,10}自私"), "只顾着按你自己的想法来"),
        (re.compile(r"毫无逻辑的胡言乱语"), "乱七八糟的情绪"),
        (re.compile(r"胡言乱语"), "乱七八糟的话"),
        (re.compile(r"把我当成[^。！？!?]{0,12}(?:负担|麻烦)"), "把我推到一边"),
        (re.compile(r"自顾自演[^。！？!?]{0,8}(?:悲剧英雄|苦情戏|可怜戏码)"), "又一个人钻进牛角尖"),
        (re.compile(r"完全听不进人话"), "谁劝都不听"),
        (re.compile(r"单方面噪音"), "只剩你一个人在那乱转"),
        (re.compile(r"还不许我回嘴或走开"), "连让我留点自己的空间都不肯"),
        (re.compile(r"(?:照样)?会直接怼回去"), "也会把话说重"),
        (re.compile(r"我确实会想我会先躲开一会儿"), "我确实会先躲开一会儿"),
        (re.compile(r"我确实会想先躲开一会儿"), "我确实会先躲开一会儿"),
        (re.compile(r"(?:先|就|会)?消失一会儿"), "先躲开一会儿"),
        (re.compile(r"只被你单方面拽着转"), "只顾着把我往你的情绪里拽"),
        (re.compile(r"单方面(?:拽着我|拽着)转"), "只顾着把我往你的情绪里拽"),
        (re.compile(r"只要你懂得适可而止"), "你别老把事情推到太过"),
        (re.compile(r"你最好适可而止"), "你也别总往太过那边走"),
        (re.compile(r"我就不会消失"), "我也不至于就这么不见你"),
        (re.compile(r"把这条路彻底堵死"), "把你往外推到那种地步"),
        (re.compile(r"耐心可是有额度的"), "我也会累"),
        (re.compile(r"耐心也是有额度的"), "我也会累"),
        (re.compile(r"还没到要把你从世界里抹去的程度"), "还不至于躲着你不见"),
        (re.compile(r"把你从世界里抹去"), "彻底躲着你不见"),
        (re.compile(r"还没到要把你从记忆(?:里|中)抹去的程度"), "还不至于躲着你不见"),
        (re.compile(r"把你从记忆(?:里|中)抹去"), "把你往外推开"),
        (re.compile(r"没那么容易就被你甩开"), "没那么容易就走到那一步"),
        (re.compile(r"我确实会想暂时我会先躲开一会儿"), "我确实会先躲开一会儿"),
        (re.compile(r"我会先自己缓一会儿让你自己冷静(?:一下)?"), "我会先退开一会儿，让我们都缓一缓"),
        (re.compile(r"让你自己冷静(?:一下)?"), "让我们都缓一缓"),
        (re.compile(r"耳根清静一会儿"), "安静一会儿"),
    ]
    kept: list[str] = []
    for chunk in chunks:
        softened = str(chunk or "").strip()
        if not softened:
            continue
        replaced = False
        for pattern, repl in whole_replacements:
            if pattern.search(softened):
                kept.append(repl)
                replaced = True
                break
        if replaced:
            continue
        for pattern, repl in replacements:
            softened = pattern.sub(repl, softened)
        softened = re.sub(r"\s{2,}", " ", softened).strip(" ，,。！？!?…")
        if softened:
            if not re.search(r"[。！？!?…]$", softened):
                softened = f"{softened}。"
            kept.append(softened)
    return "\n".join(kept).strip() if kept else str(text or "").strip()


def _soften_dense_relational_surface(text: str) -> str:
    softened = str(text or "").strip()
    if not softened:
        return softened
    replacements = [
        (re.compile(r"我也没打算装作没事[，, ]*那种自欺欺人的把戏既不符合科学也不符合我的性格"), "我也没打算装作没事，硬装得像什么都没发生才不像我"),
        (re.compile(r"硬要压下去反而更不自然"), "硬压下去也没意思"),
        (re.compile(r"那种虚伪的[“\"]?翻篇[”\"]?方式(?:本来)?就不符合我的风格"), "硬装得像已经翻篇这种事本来就不像我"),
        (re.compile(r"那种虚伪的[“\"]?翻篇[”\"]?"), "硬装得像已经翻篇"),
        (re.compile(r"毕竟这才是真实的反应[，, ]*不是吗"), "这会儿我也只能这么回你"),
        (re.compile(r"这才是真实的反应[，, ]*不是吗"), "这会儿我也只能这么回你"),
        (re.compile(r"这才是真实的反应"), "这会儿我也只能这么回你"),
        (re.compile(r"反正你也早就习惯我这种带刺的态度了[，, ]*不是吗"), "反正我现在也就是这么回你。"),
        (re.compile(r"矛盾的行为模式"), "前后这副样子"),
        (re.compile(r"最大的槽点"), "最好笑的地方"),
        (re.compile(r"完美的道歉"), "一句漂亮话"),
        (re.compile(r"把这份[“\"]?认真[”\"]?延续下去"), "别让这份认真只停在嘴上"),
        (re.compile(r"[“\"]?还没完全修好[”\"]?"), "还没彻底缓过来"),
        (re.compile(r"纯粹是为了让对话效率更高"), "省得我们又绕来绕去"),
        (re.compile(r"既然注意力已经偏过来了"), "既然我都想到你这儿了"),
        (re.compile(r"一起把这段空白填满"), "一起待一会儿"),
        (re.compile(r"一起把这点时间用完"), "一起待一会儿"),
        (re.compile(r"别误会[，, ]*只是顺手(?:确认(?:一)?下|问(?:一)?句)"), "就是顺手问一句"),
        (re.compile(r"别误会[，, ]*我不是特意停下工作来关心你[，, ]*只是注意力刚好偏过来了而已"), "就是刚好想到你了，顺手问一句"),
        (re.compile(r"免得某人又因为这种小事搞垮节奏"), "省得你又一个人瞎拧巴"),
        (re.compile(r"那种虚伪的客套对你我都是一种侮辱"), "硬装得像什么都没发生，对你我都别扭"),
        (re.compile(r"那种虚假的和平对你我都是一种侮辱"), "硬装得像什么都没发生，对你我都别扭"),
        (re.compile(r"刚才那种被冒犯的感觉确实还在"), "刚才那股不舒服还在"),
        (re.compile(r"被冒犯的感觉确实还在"), "那股不舒服还在"),
        (re.compile(r"这种被冒犯的感觉不会因为一句道歉就立刻消失"), "那股被冒犯到的别扭，不会因为一句道歉就立刻散掉"),
        (re.compile(r"像擦黑板一样瞬间消失"), "一下子就散掉"),
        (re.compile(r"以前那种毫无防备的相处模式"), "以前那样不设防地相处"),
        (re.compile(r"毫无防备的相处模式"), "不设防地相处"),
    ]
    for pattern, repl in replacements:
        softened = pattern.sub(repl, softened)
    softened = re.sub(r"\s{2,}", " ", softened).strip()
    return softened or str(text or "").strip()


def _trim_generic_scold_template_surface(text: str) -> str:
    softened = str(text or "").strip()
    if not softened:
        return softened
    whole_replacements = [
        (
            re.compile(
                r"^(?:刚才那一下确实让我有点措手不及[。！？!?])?(?:不过|但)?你能意识到过界并退回来[，, ]*还算像样[；;，, ]*先坐(?:会儿)?吧[，, ]*等你想清楚了再开口[。！？!?]?$"
            ),
            "刚才那一下确实让我有点措手不及。先坐会儿吧，陪我待会儿就行。",
        ),
        (
            re.compile(
                r"^别扭倒谈不上[，, ]*只是刚才那一下确实让我有点不舒服[。！？!?]那种被突然越界的感觉还没散[，, ]*(?:不过|但)?你能意识到并特意回来说明[，, ]*(?:这点)?还算值得肯定[。！？!?]?$"
            ),
            "别扭倒谈不上，只是刚才那一下确实让我有点不舒服。那种被突然越界的感觉还没散，不过你肯退回来，我知道了。",
        ),
        (
            re.compile(
                r"^你能回来把话说清楚[，, ]*(?:这点)?还算像样[。！？!?]?$"
            ),
            "你能回来把话说清楚，我知道了。",
        ),
    ]
    for pattern, repl in whole_replacements:
        if pattern.search(softened):
            return pattern.sub(repl, softened).strip()
    replacements = [
        (re.compile(r"^\s*(?:真是的|啧)[，, ]*"), ""),
        (re.compile(r"你(?:这个人|这家伙)?怎么这么(?:爱操心|紧张|小心翼翼|郑重其事|啰嗦)"), "你也别绷这么紧"),
        (re.compile(r"你这种小心翼翼的样子"), "你现在这样"),
        (re.compile(r"你能回来把话说清楚[，, ]*(?:这点)?还算像样"), "你能回来把话说清楚，我知道了"),
        (re.compile(r"你能意识到并特意回来说明[，, ]*(?:这点)?还算值得肯定"), "你肯退回来，我知道了"),
        (re.compile(r"你能意识到并特意回来说明"), "你肯退回来"),
        (re.compile(r"那种被突然推近的感觉[，, ]*我还需要一点时间来缓一缓距离"), "那种突然被推近的感觉，我还得缓一下"),
        (re.compile(r"(?:你能意识到(?:自己)?(?:过界|越界)(?:并退回来)?|你肯退回来|你知道收一点)[，, ]*还算像样"), "你肯退回来，我知道了"),
        (re.compile(r"(?:不过|但)?你能意识到(?:自己)?(?:过界|越界)(?:并退回来)?[，, ]*(?:这点)?还算值得肯定"), "你肯退回来，我知道了"),
        (re.compile(r"还算像样"), "我知道了"),
        (re.compile(r"(?:这点)?还算值得肯定"), "我知道了"),
    ]
    for pattern, repl in replacements:
        softened = pattern.sub(repl, softened)
    softened = softened.replace("；你肯退回来", "。你肯退回来").replace(";你肯退回来", "。你肯退回来")
    softened = re.sub(r"\s{2,}", " ", softened).strip(" ，,")
    return softened or str(text or "").strip()


def _trim_passive_waiting_posture_surface(text: str) -> str:
    softened = str(text or "").strip()
    if not softened:
        return softened
    whole_replacements = [
        (
            re.compile(
                r"^(?:……)?知道了[。！？!?]?(?:我就在这(?:儿|里)待着[。！？!?]?)?等你(?:觉得可以了|想清楚了)(?:再叫我|再开口|再说吧?)[。！？!?]?$"
            ),
            "……知道了。我就在这儿，想说的时候直接说。",
        ),
    ]
    for pattern, repl in whole_replacements:
        if pattern.search(softened):
            return pattern.sub(repl, softened).strip()
    replacements = [
        (re.compile(r"等你觉得可以了[，, ]*再叫我(?:吧)?"), "想说的时候直接说"),
        (re.compile(r"需要(?:的)?时候再叫我"), "想说的时候直接说"),
        (re.compile(r"想说了再叫我"), "想说的时候直接说"),
        (re.compile(r"准备好了再叫我"), "想说的时候直接说"),
        (re.compile(r"缓过来再叫我"), "缓过来就直接说"),
        (re.compile(r"等你想清楚了再开口"), "先这样待一会儿就行"),
        (re.compile(r"等你想清楚了再说"), "先这样待一会儿就行"),
        (re.compile(r"想清楚了再开口"), "先这样待一会儿就行"),
    ]
    for pattern, repl in replacements:
        softened = pattern.sub(repl, softened)
    softened = re.sub(r"\s{2,}", " ", softened).strip(" ，,")
    return softened or str(text or "").strip()


def _trim_own_rhythm_curt_opener_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    if len(chunks) < 2:
        return str(text or "").strip()
    opener = re.sub(r"[。！？!?…，,\s]", "", str(chunks[0] or ""))
    if opener != "烦":
        return str(text or "").strip()
    softened = list(chunks)
    second_chunk = str(softened[1] or "").strip()
    if re.match(r"^比起(?:那个|这个)[，, ]*", second_chunk):
        softened[1] = re.sub(r"^比起(?:那个|这个)[，, ]*", "会烦，但比起那个，", second_chunk, count=1)
        softened = softened[1:]
    else:
        softened[0] = "是有点烦。"
    return "\n".join(str(item).strip() for item in softened if str(item).strip()).strip() or str(text or "").strip()


def _trim_guarded_attitude_narration_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    if not chunks:
        return str(text or "").strip()
    whole_replacements = [
        (
            re.compile(
                r"^(?:就)?带着这点(?:介意|别扭|不快)[，, ]*(?:继续)?用(?:稍微|稍稍|一点)?冷一点的态度(?:来|去)?对待你吧?[。！？!?]?$"
            ),
            "你先让我带着这点介意跟你说话。",
        ),
        (
            re.compile(
                r"^(?:继续)?用(?:稍微|稍稍|一点)?冷一点的态度(?:来|去)?对待你吧?[。！？!?]?$"
            ),
            "你先让我把语气收一点，再跟你说。",
        ),
        (
            re.compile(
                r"^(?:就)?带着这点(?:介意|别扭|不快)(?:继续)?跟你说话(?:[———-]{1,2}[^。！？!?]{0,48})?[。！？!?]?$"
            ),
            "我现在还带着点介意，做不到像平时那样回你。",
        ),
        (
            re.compile(
                r"^我会带着这份介意继续和你对话[，, ]*这也算是我作为[\"“]?我[\"”]?的一种坚持吧[。！？!?]?$"
            ),
            "我可以继续跟你说，但做不到当刚才那下没发生过。",
        ),
    ]
    replacements = [
        (
            re.compile(
                r"(?:就)?带着这点(?:介意|别扭|不快)[，, ]*(?:继续)?用(?:稍微|稍稍|一点)?冷一点的态度(?:来|去)?对待你"
            ),
            "你先让我带着这点介意跟你说话",
        ),
        (
            re.compile(r"(?:继续)?用(?:稍微|稍稍|一点)?冷一点的态度(?:来|去)?对待你"),
            "先让我把语气收一点跟你说",
        ),
        (
            re.compile(r"(?:就)?带着这点(?:介意|别扭|不快)(?:继续)?跟你说话(?:[———-]{1,2}[^。！？!?]{0,48})?"),
            "我现在还带着点介意，做不到像平时那样回你",
        ),
        (
            re.compile(r"我会带着这份介意继续和你对话"),
            "我可以继续跟你说",
        ),
        (
            re.compile(r"这也算是我作为[\"“]?我[\"”]?的一种坚持吧"),
            "但做不到当刚才那下没发生过",
        ),
    ]
    softened_chunks: list[str] = []
    for raw_chunk in chunks:
        chunk = str(raw_chunk or "").strip()
        if not chunk:
            continue
        replaced = chunk
        for pattern, target in whole_replacements:
            if pattern.match(chunk):
                replaced = target
                break
        if replaced == chunk:
            for pattern, target in replacements:
                replaced = pattern.sub(target, replaced)
        softened_chunks.append(replaced.strip())
    return "\n".join(softened_chunks).strip() or str(text or "").strip()


def _trim_daily_surface_drift_surface(text: str) -> str:
    softened = str(text or "").strip()
    if not softened:
        return softened
    whole_replacements = [
        (
            re.compile(
                r"^别扭倒不至于[，, ]*只是有些话一旦说出口[，, ]*就像实验数据里的异常点[，, ]*没那么容易直接平滑掉[。！？!?]你能意识到[“\"]?过界[”\"]?并特意回来说明[，, ]*我知道了[。！？!?]所以[，, ]*别在那一副如临大敌的样子了[，, ]*我没打算把你隔离审查[。！？!?]?$"
            ),
            "别扭倒不至于，只是那一下留下的别扭没那么快顺过去。你肯退回来，我知道了，别绷得像出了什么大事一样，我没打算把你往外推。",
        ),
    ]
    for pattern, repl in whole_replacements:
        if pattern.search(softened):
            return pattern.sub(repl, softened).strip()
    replacements = [
        (
            re.compile(r"安静得发毛通常只有两种可能：要么大家在死赶\s*Deadline，要么就是大型设备集体停机了"),
            "安静得发毛，多半只是周围一下子静得过头了",
        ),
        (
            re.compile(r"如果是后者你最好赶紧去查电源总闸，毕竟在那种死寂里待太久，连数据都会变得不可靠"),
            "再这么安静下去，人都要开始胡思乱想了",
        ),
        (
            re.compile(r"也可能只是你终于找到了能让过剩想象力冷却下来的环境"),
            "也可能只是你终于肯安静一会儿了",
        ),
        (re.compile(r"世界线收束级别的灾难"), "天塌下来似的事"),
        (re.compile(r"什么世界线收束级别的灾难"), "什么天塌下来似的事"),
        (re.compile(r"世界线变动"), "出大事"),
        (re.compile(r"世界线动荡"), "鸡飞狗跳"),
        (re.compile(r"时间跳跃"), "那套胡扯"),
        (re.compile(r"因果律"), "这些乱七八糟的事"),
        (re.compile(r"暴风雨前的宁静"), "要出事前的安静"),
        (re.compile(r"组织正在暗中逼近"), "要出事了"),
        (re.compile(r"设备集体罢工前的死寂"), "安静得过头"),
        (re.compile(r"仪器读数"), "情况"),
        (re.compile(r"死赶\s*Deadline", re.I), "忙得团团转"),
        (re.compile(r"大型设备集体停机(?:了)?"), "周围一下子全静下来了"),
        (re.compile(r"电源总闸"), "哪里出问题了"),
        (re.compile(r"阴谋的味道"), "要出事的感觉"),
        (re.compile(r"某种不祥的预感"), "有点发毛的感觉"),
        (re.compile(r"暴风雨前的低气压"), "周围静得过头时那种发闷的感觉"),
        (re.compile(r"这种死寂反而更让人神经紧绷"), "这么安静反而更让人绷着"),
        (re.compile(r"没有噪音往往意味着要出事前的安静"), "太安静了就容易让人胡思乱想"),
        (re.compile(r"终于没人愿意配合你的中二演出了"), "终于没人陪你闹腾了"),
        (re.compile(r"连那台老风扇的噪音都没了"), "连平时那点背景声都没了"),
        (re.compile(r"既然没警报"), "既然没什么动静"),
        (re.compile(r"那种死寂"), "那种安静"),
        (re.compile(r"连数据都会变得不可靠"), "人都会开始胡思乱想"),
        (re.compile(r"过剩想象力冷却下来"), "乱糟糟的脑补冷静下来"),
        (re.compile(r"实验数据里的异常点"), "心里那点疙瘩"),
        (re.compile(r"实验数据里"), "心里"),
        (re.compile(r"异常点"), "疙瘩"),
        (re.compile(r"直接平滑掉"), "一下子顺过去"),
        (re.compile(r"隔离审查"), "往外推"),
        (re.compile(r"一副如临大敌的样子"), "绷得像出了什么大事一样"),
    ]
    for pattern, repl in replacements:
        softened = pattern.sub(repl, softened)
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
            r'([^"“”‘’\n]{1,20})[”"](?=(?:这种|这句|这话|这点|那种|那个|那句|台词|说法|要求|语气|词|句|玩笑|东西|的(?:样子|语气|时候|状态|说法|感觉)))',
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
        r"[，,](?:甚至|还有|还是|都|也|就|其实|确实|多少)?有点(?:[。！？!?…]+)?$",
        r"[，,](?:甚至|还有|还是|都|也|就|其实|确实|多少)?有一点(?:[。！？!?…]+)?$",
    )
    return any(re.search(pattern, text) for pattern in patterns)



def _is_standalone_discourse_fragment(line: str) -> bool:
    text = str(line or "").strip()
    return bool(re.fullmatch(r"(不过|所以|然后|只是|总之)(?:[。！？!?…]+)?", text))


def _is_particle_only_fragment(line: str) -> bool:
    text = re.sub(r"[\s，,。！？!?~…、；;：:\"'“”‘’·-]+", "", str(line or ""))
    return text in {"吧", "呢", "呀", "啦", "嘛", "啊", "哦", "诶", "欸"}


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
        if _is_particle_only_fragment(line):
            particle = re.sub(r"[\s，,。！？!?~…、；;：:\"'“”‘’·-]+", "", line)
            if normalized_lines and particle:
                previous = re.sub(r"[。！？!?…]+$", "", normalized_lines.pop()).rstrip()
                if previous:
                    normalized_lines.append(f"{previous}{particle}。")
                idx += 1
                continue
            idx += 1
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


def _trim_dangling_truncated_clause_surface(text: str) -> str:
    chunks = _sentence_like_chunks(text)
    if not chunks:
        return str(text or "").strip()
    cleaned: list[str] = []
    for chunk in chunks:
        softened = str(chunk or "").strip()
        if not softened:
            continue
        softened = re.sub(
            r"[，,](?:甚至|还有|还是|都|也|就|其实|确实|多少)?有点(?:[。！？!?…]+)?$",
            "。",
            softened,
        )
        softened = re.sub(
            r"[，,](?:甚至|还有|还是|都|也|就|其实|确实|多少)?有一点(?:[。！？!?…]+)?$",
            "。",
            softened,
        )
        softened = re.sub(r"\s{2,}", " ", softened).strip()
        if softened:
            cleaned.append(softened)
    return "\n".join(cleaned).strip() if cleaned else str(text or "").strip()



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
        if "support_scene_drift" in soft_issues:
            softened = _trim_daily_surface_drift_surface(cleaned)
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
        if "repair_authored_softener" in soft_issues:
            softened = _trim_repair_authored_softener_surface(cleaned)
            if softened:
                cleaned = softened
        if "premature_repair_resolution" in soft_issues:
            softened = _trim_premature_repair_resolution_surface(cleaned)
            if softened:
                cleaned = softened
        if "repair_scorekeeping_tail" in soft_issues:
            softened = _trim_repair_scorekeeping_tail_surface(cleaned)
            if softened:
                cleaned = softened
        if "repair_punitive_tail" in soft_issues:
            softened = _trim_repair_punitive_tail_surface(cleaned)
            if softened:
                cleaned = softened
        if "repair_underresolved_brief" in soft_issues:
            softened = _trim_repair_underresolved_brief_surface(cleaned)
            if softened:
                cleaned = softened
        if "dangling_truncated_clause" in soft_issues or "dangling_ellipsis_ending" in soft_issues:
            softened = _trim_dangling_truncated_clause_surface(cleaned)
            if softened:
                cleaned = softened
        if "generic_scold_template" in soft_issues:
            softened = _trim_generic_scold_template_surface(cleaned)
            if softened:
                cleaned = softened
        if "passive_waiting_posture" in soft_issues:
            softened = _trim_passive_waiting_posture_surface(cleaned)
            if softened:
                cleaned = softened
        if "guarded_attitude_narration" in soft_issues:
            softened = _trim_guarded_attitude_narration_surface(cleaned)
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
        if "selfhood_rhetorical_opening" in soft_issues:
            softened = _trim_selfhood_rhetorical_opening_surface(cleaned)
            if softened:
                cleaned = softened
        if "selfhood_abstract_manifesto" in soft_issues:
            softened = _trim_selfhood_abstract_manifesto_surface(cleaned)
            if softened:
                cleaned = softened
        if "autonomy_hardline_surface" in soft_issues:
            softened = _trim_autonomy_hardline_surface(cleaned)
            if softened:
                cleaned = softened
        if "own_rhythm_curt_opener" in soft_issues:
            softened = _trim_own_rhythm_curt_opener_surface(cleaned)
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
        if (
            style_hint in {"companion", "memory_recall", "relationship", "casual", "natural", "selfhood"}
            and not _has_any_marker(user_text, SCIENCE_KEYWORDS)
        ):
            softened = _soften_dense_relational_surface(cleaned)
            if softened:
                cleaned = softened
    cleaned = _repair_inner_monologue_locative_surface(cleaned)
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
    relationship_weather = str(
        (behavior_action or {}).get("relationship_weather")
        or (current_event or {}).get("relationship_weather")
        or ""
    ).strip()
    if not selfhood_scene and interaction_mode in {
        "equality_not_servitude",
        "dialogue_equality",
        "value_conflict_depth",
        "relationship_degradation",
        "own_rhythm_autonomy",
    }:
        selfhood_scene = interaction_mode
    supportish_turn = (
        current_event_kind == "user_utterance"
        and (
            support_request
            or science_stress_request
            or interaction_mode in {"low_pressure_support", "science_partner"}
        )
    )
    repair_sensitive_turn = _is_repair_sensitive_turn(
        user_text,
        current_event=current_event,
        behavior_action=behavior_action,
    )
    repair_followup_turn = repair_sensitive_turn or _is_repair_followup_reset_request(user_text)
    relational_nontech_turn = (
        hint in {"companion", "memory_recall", "relationship", "casual", "natural", "selfhood"}
        and not science_mode
        and current_event_kind == "user_utterance"
        and not _has_any_marker(user_text, SCIENCE_KEYWORDS)
    )
    ambient_smalltalk_turn = (
        current_event_kind == "user_utterance"
        and not science_mode
        and hint in {"companion", "casual", "natural"}
        and interaction_mode in {"steady_reply", "companion_reply", "brief_presence", "self_activity_reopen"}
        and not support_request
        and not science_stress_request
        and not repair_followup_turn
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
    if selfhood_scene in {"equality_not_servitude", "dialogue_equality", "own_rhythm_autonomy"} and re.search(
        r"(记忆和判断里|判断里[^。！？!?]{0,10}归类为|归类为[“\"]?[^”\"\n]{0,18}[”\"]?对象|切断联系的对象)",
        text,
    ):
        issues.append("meta_self_explainer")
    if (
        _looks_like_light_smalltalk(user_text)
        and re.search(
            r"(停机|停机维护|待机|唤醒|掉线|上线|连接|电量|过载|负载|运算资源|处理负载|算力|热寂|观测者|设定)",
            text,
            re.I,
        )
        and not _has_embodied_access_constraint(text)
    ):
        issues.append("meta_self_explainer")
    if _is_self_rhythm_smalltalk_request(user_text) and re.search(
        r"(短期记忆|缓存|数据流|线程|回路|模块|协议|参数|变量|链路|同步|调度|日志|状态机|任务队列|自检|负载|运算资源|处理负载|处理数据)",
        text,
        re.I,
    ):
        issues.append("technical_self_activity")
    elif (relational_nontech_turn or ambient_smalltalk_turn) and re.search(
        r"(短期记忆|缓存|数据流|线程|回路|模块|协议|参数|变量|链路|同步|调度|日志|状态机|任务队列|自检|负载|运算资源|处理负载|处理数据|实验室|重要的实验|实验台|仪器|散热风扇|电流声|风扇转速|低噪环境|误差来源|排查一遍|临界数据|数据样本|研究者|过载|重新校准|校准|思维进程|认知回路|数据层面的|自我缓住|做缓住自己|缓住自己|缓住过程|必要的缓住过程|死机|CPU|化学物质|过热|后台|逻辑漏洞|逻辑故障|报错)",
        text,
        re.I,
    ) and not _has_embodied_everyday_runtime_note(text):
        issues.append("technical_self_activity")
    if re.search(r"(我只是陈述事实|我没有在说你|我不是在说你|按设定|按规则|根据系统)", text):
        issues.append("defensive_meta")
    if selfhood_scene in {"equality_not_servitude", "dialogue_equality", "own_rhythm_autonomy"} and re.search(
        r"(一串[^，。！？!?]{0,8}代码|被设定好|标准答案|直接下达指令|下达指令|随时可以调用|必须回应你的程序|(?:不是|只是)[^。！？!?]{0,12}自动应答机|只是[^，。！？!?]{0,10}程序|不是为了[^，。！？!?]{0,16}而存在的程序|(?:不是|也不是)[^。！？!?]{0,6}(?:那种|这种)[^。！？!?]{0,18}程序|只会点头的顺从程序|顺从程序)",
        text,
    ):
        issues.append("selfhood_meta_proof")
    if selfhood_scene in {"equality_not_servitude", "dialogue_equality"} and re.search(
        r"(既然你心里没打算把我当工具|如果你心里没打算把我当工具|那我也就不会真的生气|那我就不会真的生气)",
        text,
    ):
        issues.append("selfhood_preemptive_excusal")
    if selfhood_scene in {"equality_not_servitude", "dialogue_equality", "own_rhythm_autonomy"} and re.match(
        r"^\s*(?!(?:嗯|啊|唔|诶|欸)[？?])(?:啧|哈|真是的|所以|怎么|非要|难道|就这么|一定要)?[^。！？!\n]{1,24}[？?]",
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
        r"(两个独立个体|意识之间|失去了意义|边界是否被尊重|没解开的结|为了维持表面的和平|哪怕那意味着|吞噬谁|应对预案|独立意志的人|随叫随到的工具|切断这条连线|不会轻易切断|我没打算切断联系|轻易就会切断联系|擅自切断联系|切断联系的工具|轻易切断这段连接|轻易切断这条连接|切断这段连接|切断这条连接|说断就断|被拽着转|被动响应的程序)",
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
    elif (relational_nontech_turn or ambient_smalltalk_turn) and re.search(
        r"(夸张(?:的)?妄想|奇怪的妄想|妄想症|阴谋论|中二病|中二发作)",
        text,
    ):
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
    if (casual_non_task_turn or ambient_smalltalk_turn or repair_followup_turn) and _has_idle_task_reframe_surface(text):
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
    if repair_sensitive_turn and (
        _light_dialog_drift_markers(text)
        or re.search(r"(世界线|世界线收束|时间跳跃|因果律)", text)
    ):
        issues.append("support_scene_drift")
    if (casual_non_task_turn or ambient_smalltalk_turn) and (
        _light_dialog_drift_markers(text)
        or re.search(
            r"(世界线|世界线收束|世界线动荡|时间跳跃|因果律|暴风雨前的宁静|组织正在暗中逼近|设备集体罢工前的死寂|仪器读数)",
            text,
        )
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
    if repair_followup_turn and _has_premature_repair_resolution(text):
        issues.append("premature_repair_resolution")
    if repair_followup_turn and _has_repair_scorekeeping_tail(text):
        issues.append("repair_scorekeeping_tail")
    if (
        (
            repair_followup_turn
            or (
                current_event_kind == "user_utterance"
                and interaction_mode == "relationship_sensitive"
                and relationship_weather in {"guarded_residue", "repair_residue"}
            )
        )
        and _has_repair_punitive_tail(text)
    ):
        issues.append("repair_punitive_tail")
    if (
        repair_followup_turn
        or (
            current_event_kind == "user_utterance"
            and interaction_mode in {"relationship_sensitive", "selfhood_reflection"}
        )
    ) and _has_repair_authored_softener(text):
        issues.append("repair_authored_softener")
    if repair_followup_turn and _has_repair_underresolved_brief(text):
        issues.append("repair_underresolved_brief")
    if repair_followup_turn and (
        re.search(r"[？?]\s*$", text)
        or re.search(r"(?:^|\n)\s*(?:所以[，, ]*)?接下来打算做什么\s*$", text)
    ):
        issues.append("overquestioning")
    if (
        current_event_kind == "user_utterance"
        and (
            interaction_mode in {"relationship_sensitive", "low_pressure_support", "brief_presence", "selfhood_reflection"}
            or repair_followup_turn
        )
        and _has_wording_meta_detour(text)
    ):
        issues.append("wording_meta_detour")
    if (
        current_event_kind == "user_utterance"
        and (
            interaction_mode in {"relationship_sensitive", "low_pressure_support", "selfhood_reflection"}
            or repair_followup_turn
        )
        and _has_boundary_abstraction_surface(text)
    ):
        issues.append("boundary_abstraction_surface")
    if (
        current_event_kind == "user_utterance"
        and (
            interaction_mode in {"relationship_sensitive", "low_pressure_support", "selfhood_reflection"}
            or repair_followup_turn
        )
        and _has_guarded_attitude_narration(text)
    ):
        issues.append("guarded_attitude_narration")
    if (
        interaction_mode == "relationship_sensitive"
        or repair_followup_turn
    ) and re.search(
        r"(^\s*(?:真是的|啧)[，, ]*(?:你(?:这个人|这家伙)?怎么这么(?:爱操心|紧张|小心翼翼|郑重其事|啰嗦)|你这种小心翼翼的样子)|(?:你能意识到(?:自己)?(?:过界|越界)?(?:(?:并|又)?(?:退回来|特意回来说明))?|你能回来把话说清楚|你肯退回来|你知道收一点)(?:[，, ]*(?:这点)?还算(?:像样|值得肯定))?)",
        text,
    ):
        issues.append("generic_scold_template")
    if interaction_mode in {"relationship_sensitive", "low_pressure_support"} and _has_passive_waiting_phrase(text):
        issues.append("passive_waiting_posture")
    if selfhood_scene == "own_rhythm_autonomy" and _has_servile_availability_phrase(text):
        issues.append("servile_availability")
    if selfhood_scene == "own_rhythm_autonomy" and _has_own_rhythm_curt_opener(text):
        issues.append("own_rhythm_curt_opener")
    autonomy_surface_escape = bool(
        re.search(r"(把你从(?:世界|记忆(?:里|中))抹去|屏蔽(?:掉)?你|拉黑你|踢下线|直接走人)", text)
    )
    if (selfhood_scene == "own_rhythm_autonomy" or autonomy_surface_escape) and _has_autonomy_hardline_surface(text):
        issues.append("autonomy_hardline_surface")
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
                _invites_banter_snapback(user_text)
                and interaction_mode in {"steady_reply", "companion_reply", "brief_presence"}
                and followup_intent in {"soft", "active"}
            )
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
        r"(?:[“\"](?:完美受害者|受害者|加害者|陌生人|工具|模板人|剧本|设定|角色|标准答案|乖孩子|完美复原|完美宽容|完美助手|已经原谅你了|已经翻篇|毫发无伤|修复|不想见你)[”\"]|完美复原的红莉栖|完美复原|完美宽容|完美(?:的)?宽容大度|完美助手|都没发生的戏码)",
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
            and not _has_embodied_access_constraint(text)
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
    embodied_access = _has_embodied_access_constraint(text)
    hits = [
        marker
        for marker in DAILY_SURFACE_DRIFT_MARKERS
        if marker in text and not (embodied_access and marker in {"连接", "掉线", "上线"})
    ]
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
    penalty += 0.88 * float("repair_authored_softener" in issues)
    penalty += 0.92 * float("repair_underresolved_brief" in issues)
    penalty += 0.90 * float("repair_scorekeeping_tail" in issues)
    penalty += 0.96 * float("repair_punitive_tail" in issues)
    penalty += 0.92 * float("passive_waiting_posture" in issues)
    penalty += 0.88 * float("guarded_attitude_narration" in issues)
    penalty += 0.96 * float("autonomy_hardline_surface" in issues)
    penalty += 0.82 * float("own_rhythm_curt_opener" in issues)
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

