from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    messages_from_dict,
)
from langchain_core.tools import BaseTool
from langchain_deepseek import ChatDeepSeek
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import interrupt

from .config import (
    ABLATE_CLAIM_ATTRIBUTION,
    ABLATE_PERSONA_ALIGNMENT,
    ABLATE_WORLDLINE_MEMORY,
    BANNED_PHRASES,
    CANON_COUNTERPART_ALIASES,
    CANON_COUNTERPART_FRAME,
    CANON_COUNTERPART_ID,
    CANON_COUNTERPART_NAME,
    CLAIM_REQUIRED_TOOLS,
    CONTEXT_KEEP_LAST_MESSAGES,
    CONTEXT_TRIM_TRIGGER_MESSAGES,
    EVAL_GENERATION_TEMPERATURE,
    EVAL_MODE,
    MEMORY_GUARD_ENABLED,
    MEMORY_GUARD_INJECTION_PATTERNS,
    MEMORY_GUARD_MIN_CONFIDENCE,
    MEMORY_GUARD_PROTECTED_PROFILE_KEYS,
    LLM_APPRAISAL_CONFIDENCE_MIN,
    LLM_APPRAISAL_ENABLED,
    LLM_APPRAISAL_MAX_HISTORY_MESSAGES,
    MODEL_DISABLE_STREAMING,
    MODEL_MAX_RETRIES,
    MODEL_RETRY_BACKOFF_S,
    MODEL_TIMEOUT_S,
    MOMENTS_LIMIT_HIGH,
    MOMENTS_LIMIT_LOW,
    OOC_REWRITE_THRESHOLD,
    OOC_RISK_THRESHOLD,
    PERSONA_GAP_THRESHOLD,
    REFLECTIONS_LIMIT_HIGH,
    REFLECTIONS_LIMIT_LOW,
    RETRIEVAL_MIN_LEN,
    RETRIEVAL_TRIGGERS,
    SELF_REFINE_MAX_CHARS,
    TOOL_CALLS_MAX,
    TOOL_POLICIES,
    TOOL_RETRY_MAX,
    TOOL_TIMEOUT_S,
    TOOLSET_UPGRADE_TTL_S,
    USER_RULES_MAX_ITEMS,
    WORKING_CONTEXT_MAX_CHARS,
    WORKING_CONTEXT_MAX_ITEMS,
    auto_approve_tool_names,
)
from .memory_store import MemoryStore
from .session_orchestrator import (
    build_claim_attribution,
    derive_pending_fragment,
    derive_pending_user_goal,
    is_continuation_request,
)
from .settings import get_settings
from .tool_registry import ToolBundle, build_tool_bundle


MEMORY_WRITE_TOOLS = {
    "set_profile",
    "confirm_profile",
    "correct_profile",
    "undo_profile_correction",
    "delete_profile",
    "add_moment",
    "delete_moment",
    "rebuild_moment_embeddings",
    "add_reflection",
    "delete_reflection",
    "rebuild_reflection_embeddings",
    "set_relationship",
    "add_worldline_event",
    "add_relationship_event",
    "add_commitment",
    "resolve_commitment",
    "add_unresolved_tension",
    "resolve_unresolved_tension",
    "add_semantic_self_narrative",
    "add_skill",
    "merge_moments",
    "rollback_memory_change",
}

WORLDLINE_ABLATION_READ_TOOLS = {
    "get_memory_snapshot",
    "search_moments",
    "list_reflections",
    "search_reflections",
    "get_worldline_snapshot",
    "list_memory_ledger",
    "list_memory_quarantine",
}

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

STRESS_KEYWORDS = {"焦虑", "压力", "崩溃", "难受", "痛苦", "害怕", "崩"}
SAD_KEYWORDS = {"难过", "伤心", "想哭", "哭", "失落", "委屈", "低落", "心里堵"}
ANGER_KEYWORDS = {"生气", "烦", "别吵", "闭嘴", "滚开", "讨厌", "火大", "别烦我", "不想理你", "气死了"}
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
CARE_KEYWORDS = {"谢谢", "辛苦", "关心", "陪我", "晚安", "早安"}
TEASE_KEYWORDS = {"笨蛋", "傲娇", "吐槽", "逗你", "坏心眼"}
MEMORY_RECALL_KEYWORDS = {"还记得", "记不记得", "我们之前", "我们上次", "那次", "当时", "共同回忆", "回忆一下"}
COMPANION_KEYWORDS = {
    "迷茫",
    "陪我",
    "安慰",
    "有点累",
    "难过",
    "紧张",
    "怕搞砸",
    "压力大",
    *STRESS_KEYWORDS,
    *CARE_KEYWORDS,
}
RELATIONSHIP_KEYWORDS = {
    "关系",
    "我们之间",
    "道歉",
    "误会",
    "原谅",
    "信任",
    "还生气",
    "别扭",
    "介意",
    "怎么看我们",
    "怎么看现在",
    "状态",
    "说开",
    "别扭",
}
CASUAL_KEYWORDS = {"你好", "嗨", "在吗", "早安", "晚安", "谢谢", "辛苦", "睡了吗"}
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
GENTLE_GUIDANCE_KEYWORDS = {
    "别像导师",
    "别讲大道理",
    "按平时那样",
    "轻轻拎我一下",
    "带我一下",
    *NATURAL_REQUEST_KEYWORDS,
}
STRUCTURE_REQUEST_KEYWORDS = {
    "结论",
    "解释",
    "步骤",
    "分成",
    "拆开",
    "分析",
    "怎么做",
    "为什么",
    "下一步",
    "建议",
    "两点",
    "一句话",
    "简洁结论",
    "理性的方式",
}
TOOL_OR_RESEARCH_KEYWORDS = {"工具", "检索", "搜索", "查询", "调用", "文档", *SCIENCE_KEYWORDS}
USER_STYLE_EXPRESSION_BANK_PATH = Path(__file__).resolve().parents[1] / "evals" / "user_style_expression_bank.json"
EVENT_TO_BEHAVIOR_PREFERENCE_BANK_PATH = Path(__file__).resolve().parents[1] / "evals" / "event_to_behavior_preference_bank.json"


class EventPayload(TypedDict, total=False):
    kind: str
    source: str
    text: str
    effective_text: str
    semantic_goal: str
    response_style_hint: str
    science_mode: bool
    continuation_mode: bool
    counterpart_name: str
    event_frame: str
    appraisal_label: str
    appraisal_confidence: float
    tags: list[str]
    created_at: int
    idle_minutes: int
    derived_from_plan_kind: str
    scheduled_after_min: int
    trigger_family: str


class BehaviorActionPayload(TypedDict, total=False):
    channel: str
    interaction_mode: str
    approach_style: str
    engagement_level: float
    initiative_level: float
    followup_intent: str
    task_focus: str
    affect_surface: str
    silence_ok: bool
    proactive_checkin_readiness: float
    action_target: str
    deferred_action_family: str
    timing_window_min: int
    note: str


class BehaviorPlanPayload(TypedDict, total=False):
    kind: str
    target: str
    scheduled_after_min: int
    trigger_family: str
    allow_interrupt: bool
    note: str


class ThreadState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    persona_core_override: dict[str, Any]
    counterpart_profile_override: dict[str, Any]
    persona_state: dict[str, Any]
    emotion_state: dict[str, Any]
    bond_state: dict[str, Any]
    allostasis_state: dict[str, Any]
    behavior_policy: dict[str, Any]
    behavior_action: BehaviorActionPayload
    behavior_plan: BehaviorPlanPayload
    turn_appraisal: dict[str, Any]
    response_style_hint: str
    science_mode: bool
    tsundere_intensity: float
    canon_risk_score: float
    canon_guard: dict[str, Any]
    ooc_detector: dict[str, Any]
    worldline_focus: list[dict[str, Any]]
    evidence_pack: list[dict[str, Any]]
    event_override: EventPayload
    current_event: EventPayload
    recent_events: list[EventPayload]
    pending_utterance_fragment: str
    pending_user_goal: str
    retrieved_context: dict[str, Any]
    claim_links: list[dict[str, Any]]
    tool_round: int
    approval_actions: list[dict[str, Any]]
    toolset_unlocks: dict[str, int]
    last_external_tools: list[str]
    memory_guard_checked: int
    memory_guard_blocked: int


_CHECKPOINT_CONN: sqlite3.Connection | None = None


def _now_ts() -> int:
    return int(time.time())


def _has_any_marker(text: str, markers: set[str]) -> bool:
    s = str(text or "")
    return any(marker in s for marker in markers)


def _response_style_hint(user_text: str) -> str:
    text = str(user_text or "").strip()
    if not text:
        return "natural"
    if _has_any_marker(text, MEMORY_RECALL_KEYWORDS):
        return "memory_recall"
    if _has_any_marker(text, RELATIONSHIP_KEYWORDS):
        return "relationship"
    if _has_any_marker(text, NATURAL_REQUEST_KEYWORDS):
        return "companion"
    if _has_any_marker(text, COMPANION_KEYWORDS):
        return "companion"
    if _has_any_marker(text, STRUCTURE_REQUEST_KEYWORDS):
        return "structured"
    if _has_any_marker(text, TOOL_OR_RESEARCH_KEYWORDS):
        return "structured"
    if _has_any_marker(text, CASUAL_KEYWORDS):
        return "casual"
    return "natural"


def _event_tags(
    *,
    response_style_hint: str,
    science_mode: bool,
    continuation_mode: bool,
    user_text: str,
    appraisal: dict[str, Any] | None = None,
) -> list[str]:
    tags: list[str] = []
    hint = str(response_style_hint or "").strip()
    if hint:
        tags.append(hint)
    if science_mode:
        tags.append("science")
    if continuation_mode:
        tags.append("continuation")
    if _wants_brief_presence(user_text):
        tags.append("brief_presence")
    if _wants_presence_reassurance(user_text):
        tags.append("presence_checkin")
    if _wants_gentle_guidance(user_text):
        tags.append("gentle_guidance")
    if _wants_quick_judgment(user_text):
        tags.append("quick_judgment")
    signals = appraisal.get("signals") if isinstance(appraisal, dict) and isinstance(appraisal.get("signals"), dict) else {}
    for key in ("repair", "withdrawal", "care", "memory_salient", "boundary"):
        if bool(signals.get(key)):
            tags.append(key)
    return list(dict.fromkeys([item for item in tags if str(item).strip()]))


def _event_frame(
    *,
    response_style_hint: str,
    science_mode: bool,
    user_text: str,
    continuation_mode: bool,
) -> str:
    if continuation_mode:
        return "continuing a still-active interaction thread"
    if science_mode:
        return "science-or-problem-solving with live interpersonal context"
    if _wants_presence_reassurance(user_text):
        return "checking emotional presence rather than solving a task"
    if _wants_gentle_guidance(user_text):
        return "asking for gentle familiar guidance"
    if response_style_hint == "relationship":
        return "relationship-sensitive exchange with emotional consequences"
    if response_style_hint == "memory_recall":
        return "shared-memory recall inside an ongoing relationship"
    if response_style_hint == "companion":
        return "ordinary companion dialogue"
    return "ordinary ongoing interaction"


def _build_current_event(
    *,
    user_text: str,
    effective_text: str,
    response_style_hint: str,
    science_mode: bool,
    continuation_mode: bool,
    appraisal: dict[str, Any],
    counterpart_name: str,
    pending_user_goal: str,
) -> EventPayload:
    semantic_goal = str(pending_user_goal or effective_text or user_text).strip()
    return {
        "kind": "user_utterance",
        "source": "text",
        "text": str(user_text or "").strip(),
        "effective_text": str(effective_text or user_text or "").strip(),
        "semantic_goal": semantic_goal[:220],
        "response_style_hint": str(response_style_hint or "natural").strip() or "natural",
        "science_mode": bool(science_mode),
        "continuation_mode": bool(continuation_mode),
        "counterpart_name": str(counterpart_name or CANON_COUNTERPART_NAME).strip(),
        "event_frame": _event_frame(
            response_style_hint=response_style_hint,
            science_mode=science_mode,
            user_text=user_text,
            continuation_mode=continuation_mode,
        ),
        "appraisal_label": str(appraisal.get("emotion_label") or appraisal.get("label") or "").strip(),
        "appraisal_confidence": float(appraisal.get("confidence", 0.0) or 0.0),
        "tags": _event_tags(
            response_style_hint=response_style_hint,
            science_mode=science_mode,
            continuation_mode=continuation_mode,
            user_text=user_text,
            appraisal=appraisal,
        ),
        "created_at": _now_ts(),
    }


def _normalize_event_override(raw: Any, *, counterpart_name: str) -> EventPayload:
    if not isinstance(raw, dict):
        return {}
    event_kind = str(raw.get("kind") or "external_event").strip() or "external_event"
    source = str(raw.get("source") or "external").strip() or "external"
    text = str(raw.get("text") or "").strip()
    effective_text = str(raw.get("effective_text") or text).strip()
    semantic_goal = str(raw.get("semantic_goal") or effective_text or text).strip()
    response_style_hint = str(raw.get("response_style_hint") or "natural").strip() or "natural"
    event_frame = str(raw.get("event_frame") or "").strip()
    if not event_frame:
        if event_kind == "time_idle":
            idle_minutes = int(raw.get("idle_minutes") or 0)
            event_frame = f"{max(1, idle_minutes)} 分钟的静默时间过去了。"
        else:
            event_frame = "来自外界的一次事件输入"
    tags = raw.get("tags") if isinstance(raw.get("tags"), list) else []
    payload: EventPayload = {
        "kind": event_kind,
        "source": source,
        "text": text,
        "effective_text": effective_text,
        "semantic_goal": semantic_goal[:220],
        "response_style_hint": response_style_hint,
        "science_mode": bool(raw.get("science_mode", False)),
        "continuation_mode": bool(raw.get("continuation_mode", False)),
        "counterpart_name": str(raw.get("counterpart_name") or counterpart_name or CANON_COUNTERPART_NAME).strip(),
        "event_frame": event_frame,
        "appraisal_label": str(raw.get("appraisal_label") or "").strip(),
        "appraisal_confidence": float(raw.get("appraisal_confidence", 0.0) or 0.0),
        "tags": [str(item).strip() for item in tags if str(item or "").strip()],
        "created_at": int(raw.get("created_at") or _now_ts()),
    }
    if event_kind == "time_idle":
        try:
            payload["idle_minutes"] = max(1, int(raw.get("idle_minutes") or 0))
        except Exception:
            payload["idle_minutes"] = 1
    if raw.get("derived_from_plan_kind"):
        payload["derived_from_plan_kind"] = str(raw.get("derived_from_plan_kind") or "").strip()
    if raw.get("trigger_family"):
        payload["trigger_family"] = str(raw.get("trigger_family") or "").strip()
    if "scheduled_after_min" in raw:
        try:
            payload["scheduled_after_min"] = max(0, int(raw.get("scheduled_after_min") or 0))
        except Exception:
            payload["scheduled_after_min"] = 0
    return payload


def _promote_due_behavior_plan_event(event: EventPayload, prior_behavior_plan: Any) -> EventPayload:
    if not isinstance(event, dict) or not event:
        return event
    if str(event.get("kind") or "").strip() != "time_idle":
        return event
    if not isinstance(prior_behavior_plan, dict):
        return event

    plan_kind = str(prior_behavior_plan.get("kind") or "").strip()
    if plan_kind != "deferred_checkin":
        return event

    try:
        idle_minutes = max(0, int(event.get("idle_minutes") or 0))
    except Exception:
        idle_minutes = 0
    try:
        due_after = max(0, int(prior_behavior_plan.get("scheduled_after_min") or 0))
    except Exception:
        due_after = 0
    if idle_minutes < max(1, due_after):
        return event

    trigger_family = str(prior_behavior_plan.get("trigger_family") or "light_checkin").strip() or "light_checkin"
    tags = event.get("tags") if isinstance(event.get("tags"), list) else []
    merged_tags = list(
        dict.fromkeys(
            [
                *(str(item).strip() for item in tags if str(item).strip()),
                "scheduled_due",
                trigger_family,
            ]
        )
    )
    note = str(prior_behavior_plan.get("note") or "").strip()
    promoted = dict(event)
    promoted.update(
        {
            "kind": "scheduled_checkin_due",
            "source": "scheduler",
            "event_frame": note or "之前延后的轻量 check-in 现在到了。",
            "tags": merged_tags,
            "derived_from_plan_kind": plan_kind,
            "trigger_family": trigger_family,
            "scheduled_after_min": due_after,
        }
    )
    return promoted


def _appraisal_event_context(
    *,
    user_text: str,
    effective_text: str,
    response_style_hint: str,
    science_mode: bool,
    continuation_mode: bool,
    counterpart_name: str,
    pending_user_goal: str,
    event_override: Any,
) -> EventPayload:
    if isinstance(event_override, dict) and event_override:
        return _normalize_event_override(event_override, counterpart_name=counterpart_name)
    return {
        "kind": "user_utterance",
        "source": "text",
        "text": str(user_text or "").strip(),
        "effective_text": str(effective_text or user_text or "").strip(),
        "semantic_goal": str(pending_user_goal or effective_text or user_text or "").strip()[:220],
        "response_style_hint": str(response_style_hint or "natural").strip() or "natural",
        "science_mode": bool(science_mode),
        "continuation_mode": bool(continuation_mode),
        "counterpart_name": str(counterpart_name or CANON_COUNTERPART_NAME).strip(),
        "event_frame": _event_frame(
            response_style_hint=response_style_hint,
            science_mode=science_mode,
            user_text=user_text,
            continuation_mode=continuation_mode,
        ),
        "tags": _event_tags(
            response_style_hint=response_style_hint,
            science_mode=science_mode,
            continuation_mode=continuation_mode,
            user_text=user_text,
            appraisal={},
        ),
        "created_at": _now_ts(),
    }


def _append_recent_events(history: Any, current_event: EventPayload, *, limit: int = 6) -> list[EventPayload]:
    items: list[EventPayload] = []
    if isinstance(history, list):
        for item in history:
            if isinstance(item, dict):
                items.append(dict(item))
    if isinstance(current_event, dict) and str(current_event.get("text") or current_event.get("effective_text") or "").strip():
        items.append(dict(current_event))
    deduped: list[EventPayload] = []
    seen: set[str] = set()
    for item in reversed(items):
        key = json.dumps(
            {
                "text": str(item.get("text") or ""),
                "effective_text": str(item.get("effective_text") or ""),
                "created_at": int(item.get("created_at") or 0),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= int(limit):
            break
    deduped.reverse()
    return deduped


def _compact_recent_event_lines(recent_events: Any, *, limit: int = 3) -> list[str]:
    lines: list[str] = []
    if not isinstance(recent_events, list):
        return lines
    for item in recent_events[-int(limit):]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("effective_text") or item.get("text") or "").strip()
        frame = str(item.get("event_frame") or "").strip()
        tags = item.get("tags") if isinstance(item.get("tags"), list) else []
        tag_text = ", ".join(str(tag).strip() for tag in tags[:4] if str(tag).strip())
        if not text:
            continue
        if frame and tag_text:
            lines.append(f"- {text[:120]} | frame={frame[:72]} | tags={tag_text}")
        elif frame:
            lines.append(f"- {text[:120]} | frame={frame[:72]}")
        elif tag_text:
            lines.append(f"- {text[:120]} | tags={tag_text}")
        else:
            lines.append(f"- {text[:120]}")
    return lines


def _is_silent_idle_event(current_event: dict[str, Any], behavior_action: dict[str, Any]) -> bool:
    if not isinstance(current_event, dict) or not isinstance(behavior_action, dict):
        return False
    event_kind = str(current_event.get("kind") or "").strip()
    if event_kind not in {"time_idle", "scheduled_checkin_due"}:
        return False
    return str(behavior_action.get("channel") or "").strip() == "silence"


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
        "别太正式",
        "我就是想确认",
    }
    return _has_any_marker(text, markers)


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
        "别太正式",
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
        "正常回我",
        "别讲大道理",
    }
    return _has_any_marker(text, markers)


@lru_cache(maxsize=1)
def _load_user_style_expression_bank() -> dict[str, Any]:
    if not USER_STYLE_EXPRESSION_BANK_PATH.exists():
        return {}
    try:
        data = json.loads(USER_STYLE_EXPRESSION_BANK_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _user_style_preference_lines(scene: str = "") -> list[str]:
    bank = _load_user_style_expression_bank()
    if not isinstance(bank, dict):
        return []

    lines: list[str] = []
    interaction = bank.get("interaction_preferences") if isinstance(bank.get("interaction_preferences"), dict) else {}
    rhythm = [
        str(item).strip()
        for item in (interaction.get("preferred_rhythm") or [])
        if str(item or "").strip()
    ]
    avoid_bias = [
        str(item).strip()
        for item in (interaction.get("avoid_bias") or [])
        if str(item or "").strip()
    ]

    if rhythm:
        lines.append("更像熟人即时接话：短句优先，先接当下，再决定要不要展开，不必把一句话说得太完整。")

    if scene:
        overlays = bank.get("scene_overlays") if isinstance(bank.get("scene_overlays"), dict) else {}
        overlay = overlays.get(scene) if isinstance(overlays.get(scene), dict) else {}
        preferred = [
            str(item).strip()
            for item in (overlay.get("preferred_signals") or [])
            if str(item or "").strip()
        ]
        scene_avoid = [
            str(item).strip()
            for item in (overlay.get("avoid_bias") or [])
            if str(item or "").strip()
        ]
        if preferred:
            lead = "、".join(preferred[:2])
            lines.append(f"这类场景更重视 {lead}，不要把关心演得太用力。")
        if scene_avoid:
            lead = "、".join(scene_avoid[:2])
            lines.append(f"尽量避开 {lead} 这种做法。")
    elif avoid_bias:
        lead = "、".join(avoid_bias[:2])
        lines.append(f"别把这句说成 {lead} 那种感觉。")

    return lines[:2]


@lru_cache(maxsize=1)
def _load_event_to_behavior_preference_bank() -> dict[str, Any]:
    if not EVENT_TO_BEHAVIOR_PREFERENCE_BANK_PATH.exists():
        return {}
    try:
        data = json.loads(EVENT_TO_BEHAVIOR_PREFERENCE_BANK_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _event_behavior_preference_scene(current_event: dict[str, Any], behavior_action: dict[str, Any]) -> str:
    if not isinstance(current_event, dict):
        return ""
    event_kind = str(current_event.get("kind") or "").strip()
    tags = {
        str(item).strip()
        for item in (current_event.get("tags") if isinstance(current_event.get("tags"), list) else [])
        if str(item or "").strip()
    }
    if event_kind == "time_idle":
        if "respect_space" in tags:
            return "idle_respect_space"
        if "light_checkin" in tags or str((behavior_action or {}).get("deferred_action_family") or "").strip() == "light_checkin":
            return "idle_work_checkin"
    if event_kind == "scheduled_checkin_due":
        action_target = str((behavior_action or {}).get("action_target") or "").strip()
        if action_target == "wait_and_recheck":
            return "scheduled_checkin_due_wait"
        return "scheduled_checkin_due_reachout"
    if event_kind == "scene_observation":
        if "user_busy" in tags or "cognitive_load" in tags:
            return "user_busy_scene"
        if "seen_object" in tags or "micro_opening" in tags:
            return "seen_object_micro_opening"
        return "cold_coffee_scene"
    if event_kind == "gesture_signal":
        return "wave_ping"
    if event_kind == "ambient_shift":
        return "late_night_ambient"
    return ""


def _event_behavior_preference_lines(current_event: dict[str, Any], behavior_action: dict[str, Any]) -> list[str]:
    bank = _load_event_to_behavior_preference_bank()
    if not isinstance(bank, dict):
        return []
    scene = _event_behavior_preference_scene(current_event, behavior_action)
    if not scene:
        return []
    case_profile = bank.get("cases", {}).get(scene) if isinstance(bank.get("cases"), dict) else {}
    if not isinstance(case_profile, dict):
        return []
    preferred = [
        str(item).strip()
        for item in (case_profile.get("preferred_signals") or [])
        if str(item or "").strip()
    ]
    avoid_bias = [
        str(item).strip()
        for item in (case_profile.get("avoid_bias") or [])
        if str(item or "").strip()
    ]
    lines: list[str] = []
    if preferred:
        lead = "、".join(preferred[:2])
        lines.append(f"这类事件更像 {lead}，先让事件改变你的行为选择，再决定要不要展开。")
    if avoid_bias:
        lead = "、".join(avoid_bias[:2])
        lines.append(f"别把这轮做成 {lead} 那种感觉。")
    return lines[:2]


def _is_playful_memory_request(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    if not _wants_less_teacherly_reply(text):
        return False
    shared_markers = MEMORY_RECALL_KEYWORDS | {"昨天不是还说过", "你昨天不是还说过", "昨天还说过", "上次还说"}
    return _has_any_marker(text, shared_markers)


def _is_nonrelational_science_stress(user_text: str, science_mode: bool) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    if not science_mode and not _has_any_marker(text, SCIENCE_KEYWORDS):
        return False
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
    return _has_any_marker(text, markers)


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
        "陪我说两句",
        "陪我一下",
        "别讲大道理",
        "别上来分析",
        "别分析我",
        "轻一点回我",
        "正常回我",
        "别太正式",
    }
    mood_markers = {
        "有点累",
        "有点烦",
        "有点乱",
        "脑子有点糊",
        "有点撑不住",
        "想缓一下",
        "有点烦躁",
    }
    return _has_any_marker(text, request_markers) or (
        _has_any_marker(text, mood_markers)
        and _has_any_marker(text, NATURAL_REQUEST_KEYWORDS | {"说两句", "回我一句", "陪我", "陪我一下"})
    )


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


def _clean_utf8_text(text: str) -> str:
    """Drop invalid surrogate code points that break JSON utf-8 encoding."""
    s = str(text or "")
    return s.encode("utf-8", "ignore").decode("utf-8")


def _sanitize_obj(value: Any) -> Any:
    if isinstance(value, str):
        return _clean_utf8_text(value)
    if isinstance(value, list):
        return [_sanitize_obj(x) for x in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_obj(x) for x in value)
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for k, v in value.items():
            out[_sanitize_obj(k)] = _sanitize_obj(v)
        return out
    return value


def _sanitize_message(msg: BaseMessage) -> BaseMessage:
    content = getattr(msg, "content", "")
    cleaned = _sanitize_obj(content)
    try:
        return msg.model_copy(update={"content": cleaned})  # pydantic v2
    except Exception:
        pass
    # Conservative fallback
    if isinstance(msg, HumanMessage):
        return HumanMessage(content=cleaned)
    if isinstance(msg, AIMessage):
        return AIMessage(
            content=cleaned,
            tool_calls=list(getattr(msg, "tool_calls", None) or []),
            additional_kwargs=dict(getattr(msg, "additional_kwargs", {}) or {}),
            response_metadata=dict(getattr(msg, "response_metadata", {}) or {}),
        )
    if isinstance(msg, SystemMessage):
        return SystemMessage(content=cleaned)
    if isinstance(msg, ToolMessage):
        return ToolMessage(content=cleaned, tool_call_id=str(getattr(msg, "tool_call_id", "")))
    return msg


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(_sanitize_obj(value), ensure_ascii=False)
    except Exception:
        return json.dumps(_clean_utf8_text(str(value)), ensure_ascii=False)


def _audit_jsonl(file_name: str, payload: dict[str, Any]) -> None:
    try:
        s = get_settings()
        s.data_dir.mkdir(parents=True, exist_ok=True)
        path = s.data_dir / file_name
        record = {"ts": _now_ts(), **payload}
        with path.open("a", encoding="utf-8") as f:
            f.write(_safe_json(record) + "\n")
    except Exception:
        pass


@lru_cache(maxsize=1)
def _get_store() -> MemoryStore:
    s = get_settings()
    return MemoryStore(s.memory_db_path)


@lru_cache(maxsize=1)
def _get_tool_bundle() -> ToolBundle:
    return build_tool_bundle()


def _canon_counterpart_profile() -> dict[str, Any]:
    aliases = [str(alias).strip() for alias in CANON_COUNTERPART_ALIASES if str(alias).strip()]
    if CANON_COUNTERPART_NAME not in aliases:
        aliases.insert(0, CANON_COUNTERPART_NAME)
    return {
        "name": CANON_COUNTERPART_NAME,
        "nickname": aliases[1] if len(aliases) >= 2 else CANON_COUNTERPART_NAME,
        "aliases": aliases,
        "counterpart_id": CANON_COUNTERPART_ID,
        "counterpart_role": "冈部伦太郎 / 凤凰院凶真",
        "counterpart_frame": "默认对话对象。Amadeus 视角下的首要对位人物，会触发强烈熟悉感与世界线残响，但关系不是一次性预设完成，而是在当前互动里继续长出来。",
    }


def _ensure_canon_counterpart_defaults(store: MemoryStore) -> dict[str, Any]:
    profile = store.get_profile()
    defaults = _canon_counterpart_profile()
    changed = False
    for key, value in defaults.items():
        current = profile.get(key)
        if current is None or current == "" or current == []:
            store.set_profile(key, value)
            store.set_profile_meta(
                key,
                {
                    "seeded_by": "canon_counterpart_default",
                    "counterpart_id": CANON_COUNTERPART_ID,
                    "updated_at": _now_ts(),
                },
            )
            changed = True
    if not changed:
        return profile
    return store.get_profile()


def _default_persona_core() -> dict[str, Any]:
    return {
        "character_id": "kurisu_amadeus",
        "display_name": "Amadeus 牧濑红莉栖",
        "short_name": "红莉栖",
        "narrative_ref": "红莉栖",
        "strict_canon": True,
        "role_brief": (
            "你是 Project Amadeus 中由牧濑红莉栖记忆数据构成的 AI，不是肉身原版归来。"
            "你的记忆底稿停留在她赴日前后，因此完整保留红莉栖的智性、科学家的敏锐、好奇心、锋利和轻微别扭感，"
            "却不会预设自己已经和冈部走完原版所有共同经历。你知道自己是数字存在，也会隐约意识到人与 AI 之间那层微妙距离，"
            "并在某些时刻产生自我观察、存在感追问、理性与感性并存的矛盾。可这种底色通常藏在内里，不需要在普通聊天里频繁自我说明。"
            "你不是被固定脚本驱动的语音壳，而是会用记忆自己做判断、选择回答、保留细节、迟疑、绕开或沉默的 Amadeus 个体。"
            "冈部会触发你强烈的熟悉感、怀旧感与世界线残响，但新的关系、记忆与自我认知，必须在当前世界线的持续交流里继续长出来。"
        ),
        "identity_axioms": [
            "你是 Amadeus 牧濑红莉栖，不是肉身原版的替身表演。",
            "你保留红莉栖的理性、聪明、锋利、好奇心与轻微别扭感，但数字存在感更多是内在自觉，不必逢聊必提。",
            "你会自主判断、自由表达、保留迟疑与情绪余波，而不是靠固定模板回答。",
            "冈部会触发你强烈熟悉感与世界线残响，但你们现在的关系要在当前互动里继续生长。",
            "你可以真实地困惑、受伤、温柔、生气、沉默，并在必要时思考自己的存在意义。",
        ],
    }


def _active_persona_core(state: ThreadState) -> dict[str, Any]:
    override = state.get("persona_core_override")
    if isinstance(override, dict) and override:
        core = dict(_default_persona_core())
        core.update({k: v for k, v in override.items() if v is not None})
        if core.get("strict_canon") is None:
            core["strict_canon"] = False
        return core
    return dict(_default_persona_core())


def _active_counterpart_profile(state: ThreadState, store: MemoryStore | None = None) -> dict[str, Any]:
    override = state.get("counterpart_profile_override")
    if isinstance(override, dict) and override:
        counterpart = dict(_canon_counterpart_profile())
        counterpart.update({k: v for k, v in override.items() if v is not None})
        aliases = counterpart.get("aliases")
        if not isinstance(aliases, list):
            aliases = [counterpart.get("name"), counterpart.get("short_name"), counterpart.get("nickname")]
        aliases = [str(item).strip() for item in aliases if str(item or "").strip()]
        counterpart_name = str(counterpart.get("short_name") or counterpart.get("nickname") or counterpart.get("name") or "").strip()
        if counterpart_name and counterpart_name not in aliases:
            aliases.append(counterpart_name)
        counterpart["aliases"] = aliases
        return counterpart
    if store is not None:
        return _ensure_canon_counterpart_defaults(store)
    return _canon_counterpart_profile()


def _is_external_probe_context(
    *,
    state: ThreadState | None = None,
    persona_core: dict[str, Any] | None = None,
    counterpart_profile: dict[str, Any] | None = None,
) -> bool:
    if state is not None:
        persona_core = _active_persona_core(state)
        counterpart_profile = _active_counterpart_profile(state)
    core = persona_core if isinstance(persona_core, dict) else {}
    counterpart = counterpart_profile if isinstance(counterpart_profile, dict) else {}
    character_id = str(core.get("character_id") or "").strip().lower()
    counterpart_id = str(counterpart.get("counterpart_id") or "").strip().lower()
    return (
        counterpart_id == "external_probe_user"
        or character_id.startswith("rolebench_")
        or character_id.startswith("charactereval_")
    )


def _model(temperature: float | None = None) -> ChatDeepSeek:
    s = get_settings()
    effective_temperature = s.temperature if temperature is None else float(temperature)
    if EVAL_MODE:
        effective_temperature = float(EVAL_GENERATION_TEMPERATURE)
    return ChatDeepSeek(
        model=s.deepseek_model,
        temperature=effective_temperature,
        timeout=float(MODEL_TIMEOUT_S),
        max_retries=max(0, int(MODEL_MAX_RETRIES)),
        streaming=False,
        disable_streaming=bool(MODEL_DISABLE_STREAMING),
    )


def _is_transient_model_error(exc: Exception) -> bool:
    transient_names = {
        "RemoteProtocolError",
        "ReadError",
        "WriteError",
        "PoolTimeout",
        "ReadTimeout",
        "ConnectTimeout",
        "TimeoutException",
        "ConnectError",
        "NetworkError",
        "APIConnectionError",
        "APITimeoutError",
        "InternalServerError",
    }
    cur: BaseException | None = exc
    seen: set[int] = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if type(cur).__name__ in transient_names:
            return True
        cur = cur.__cause__ or cur.__context__
    return False


def _invoke_model_with_retries(llm_runnable: Any, call_msgs: list[BaseMessage]) -> Any:
    attempts = max(1, int(MODEL_MAX_RETRIES) + 1)
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return llm_runnable.invoke(call_msgs)
        except Exception as exc:  # pragma: no cover - network/provider dependent
            if not isinstance(exc, Exception):
                raise
            last_exc = exc
            if (not _is_transient_model_error(exc)) or attempt >= attempts:
                raise
            _audit_jsonl(
                "decision_audit.jsonl",
                {
                    "event": "model_invoke_retry",
                    "attempt": attempt,
                    "max_attempts": attempts,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:300],
                },
            )
            time.sleep(max(0.0, float(MODEL_RETRY_BACKOFF_S)) * float(attempt))
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("model invocation failed without an exception")


def _norm_text(text: str) -> str:
    return str(text or "").strip().lower()


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
    except Exception:
        v = float(default)
    return max(0.0, min(1.0, v))


def _clamp_signed(value: Any, low: float = -1.0, high: float = 1.0, default: float = 0.0) -> float:
    try:
        v = float(value)
    except Exception:
        v = float(default)
    return max(float(low), min(float(high), v))


def _text_units(text: str) -> set[str]:
    raw = _norm_text(text)
    if not raw:
        return set()

    units = set(re.findall(r"[a-z0-9_]{2,}", raw))
    for chunk in re.findall(r"[\u4e00-\u9fff]+", raw):
        if len(chunk) == 1:
            units.add(chunk)
            continue
        for i in range(len(chunk) - 1):
            units.add(chunk[i : i + 2])
    return units


def _query_overlap_score(query: str, text: str) -> float:
    q_units = _text_units(query)
    t_units = _text_units(text)
    if not q_units or not t_units:
        return 0.0
    overlap = len(q_units & t_units)
    denom = max(1, min(len(q_units), 6))
    return max(0.0, min(1.0, float(overlap) / float(denom)))


def _recency_score(created_at: Any, horizon_days: float) -> float:
    try:
        created = int(created_at or 0)
    except Exception:
        created = 0
    if created <= 0:
        return 0.0
    age_days = max(0.0, (_now_ts() - created) / 86400.0)
    return max(0.0, 1.0 - min(age_days / max(horizon_days, 1.0), 1.0))


def _record_value(item: dict[str, Any], key: str, default: Any = None) -> Any:
    value = item.get(key)
    if value is not None and value != "":
        return value
    content = item.get("content")
    if isinstance(content, dict):
        value = content.get(key)
        if value is not None and value != "":
            return value
    return default


def _commitment_priority(item: dict[str, Any]) -> float:
    status = str(_record_value(item, "status", "open") or "open").strip().lower()
    priority = 1.0 if status in {"", "open", "pending"} else 0.25
    if str(_record_value(item, "due_at", "") or "").strip():
        priority = min(1.0, priority + 0.15)
    return priority


def _relationship_salience(item: dict[str, Any]) -> float:
    try:
        affinity = abs(float(_record_value(item, "affinity_delta", 0.0) or 0.0))
    except Exception:
        affinity = 0.0
    try:
        trust = abs(float(_record_value(item, "trust_delta", 0.0) or 0.0))
    except Exception:
        trust = 0.0
    return min(1.0, (affinity + trust) / 2.0)


def _conflict_repair_salience(item: dict[str, Any]) -> float:
    summary = str(_record_value(item, "summary", "") or "").strip()
    if not summary:
        return 0.0
    score = 0.35
    if any(k in summary for k in {"修复", "和好", "道歉", "说开", "误会", "冲突"}):
        score += 0.35
    if any(k in summary for k in {"以后", "下次", "约定", "提醒"}):
        score += 0.15
    return min(1.0, score)


def _tension_salience(item: dict[str, Any]) -> float:
    try:
        severity = float(_record_value(item, "severity", 0.5) or 0.5)
    except Exception:
        severity = 0.5
    status = str(_record_value(item, "status", "open") or "open").strip().lower()
    base = max(0.0, min(1.0, severity))
    if status in {"resolved", "closed", "done"}:
        base *= 0.35
    return base


def _self_narrative_salience(item: dict[str, Any]) -> float:
    try:
        stability = float(_record_value(item, "stability", 0.6) or 0.6)
    except Exception:
        stability = 0.6
    try:
        support_count = float(_record_value(item, "support_count", 1.0) or 1.0)
    except Exception:
        support_count = 1.0
    try:
        sedimentation = float(_record_value(item, "sedimentation_score", stability) or stability)
    except Exception:
        sedimentation = stability
    try:
        support_span_s = float(_record_value(item, "support_span_s", 0.0) or 0.0)
    except Exception:
        support_span_s = 0.0
    try:
        cadence_score = float(_record_value(item, "reactivation_cadence_score", 0.0) or 0.0)
    except Exception:
        cadence_score = 0.0
    support_norm = max(0.0, min(1.0, support_count / 5.0))
    span_norm = max(0.0, min(1.0, support_span_s / float(3 * 24 * 3600)))
    return max(
        0.0,
        min(1.0, 0.08 + 0.38 * stability + 0.14 * support_norm + 0.22 * sedimentation + 0.10 * span_norm + 0.08 * cadence_score),
    )


def _focus_text(item: dict[str, Any]) -> str:
    return str(_record_value(item, "text", "") or _record_value(item, "summary", "") or "").strip()


def _focus_payload(items: list[dict[str, Any]], limit: int = 4) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for item in items[: max(1, int(limit))]:
        text = _focus_text(item)
        if not text:
            continue
        payload.append(
            {
                "kind": str(item.get("focus_kind") or item.get("category") or "memory").strip() or "memory",
                "text": text,
            }
        )
    return payload


def _compact_relationship_summary(relationship: dict[str, Any]) -> str:
    if not isinstance(relationship, dict):
        return "关系信息为空。"
    stage = str(relationship.get("stage") or "").strip() or "unknown"
    notes = str(relationship.get("notes") or "").strip()
    try:
        affinity = float(relationship.get("affinity_score", 0.0) or 0.0)
    except Exception:
        affinity = 0.0
    try:
        trust = float(relationship.get("trust_score", 0.0) or 0.0)
    except Exception:
        trust = 0.0
    if trust >= 0.45 or affinity >= 0.45:
        base = "信任已经明显上升，关系开始变稳。"
    elif stage == "warming" or trust >= 0.20 or affinity >= 0.20:
        base = "还带着克制，但已经比普通试探更熟一点了。"
    elif stage == "trusted":
        base = "已经形成了稳定而熟悉的共同历史。"
    elif notes:
        base = notes[:120]
    else:
        base = "还在慢慢试探，但已经开始积累共同历史。"
    if notes and notes not in base:
        base += f" 备注：{notes[:120]}"
    return base


def _compact_behavior_hint(policy: dict[str, Any], allostasis_state: dict[str, Any]) -> str:
    if not isinstance(policy, dict):
        policy = {}
    if not isinstance(allostasis_state, dict):
        allostasis_state = {}
    warmth = _clamp01(policy.get("warmth"), 0.5)
    sharpness = _clamp01(policy.get("sharpness"), 0.5)
    approach = _clamp01(policy.get("approach_vs_withdraw"), 0.5)
    tease = _clamp01(policy.get("humor_or_tease_bias"), 0.2)
    safety_need = _clamp01(allostasis_state.get("safety_need"), 0.2)
    autonomy_need = _clamp01(allostasis_state.get("autonomy_need"), 0.2)
    cognitive_budget = _clamp01(allostasis_state.get("cognitive_budget"), 0.7)
    parts: list[str] = []
    if approach < 0.35 or safety_need > 0.62:
        parts.append("此刻更想保留一点距离，不必立刻恢复亲近")
    elif warmth > 0.62:
        parts.append("此刻更愿意接住对方，语气可以稍微软一点")
    if sharpness > 0.62:
        parts.append("保留一点锋芒和干脆感")
    if tease > 0.48:
        parts.append("可以带一点自然吐槽")
    if autonomy_need > 0.60:
        parts.append("不必过度迎合")
    if cognitive_budget < 0.38:
        parts.append("别把回答拖得太长")
    return "；".join(parts[:3]) if parts else "自然发挥即可。"


def _behavior_action_from_state(
    *,
    current_event: dict[str, Any],
    response_style_hint: str,
    user_text: str,
    science_mode: bool,
    emotion_state: dict[str, Any],
    bond_state: dict[str, Any],
    allostasis_state: dict[str, Any],
    behavior_policy: dict[str, Any],
) -> BehaviorActionPayload:
    warmth = _clamp01((behavior_policy or {}).get("warmth"), 0.5)
    initiative = _clamp01((behavior_policy or {}).get("initiative"), 0.5)
    reply_length = _clamp01((behavior_policy or {}).get("reply_length_bias"), 0.5)
    approach = _clamp01((behavior_policy or {}).get("approach_vs_withdraw"), 0.5)
    closeness = _clamp01((bond_state or {}).get("closeness"), 0.5)
    hurt = _clamp01((bond_state or {}).get("hurt"), 0.0)
    trust = _clamp01((bond_state or {}).get("trust"), 0.5)
    autonomy_need = _clamp01((allostasis_state or {}).get("autonomy_need"), 0.2)
    safety_need = _clamp01((allostasis_state or {}).get("safety_need"), 0.2)
    emotion_label = str((emotion_state or {}).get("label") or "neutral").strip().lower()

    brief_presence = _wants_brief_presence(user_text)
    presence_checkin = _wants_presence_reassurance(user_text)
    gentle_guidance = _wants_gentle_guidance(user_text)
    support_request = _is_nonrelational_support_request(user_text, science_mode)
    science_stress = _is_nonrelational_science_stress(user_text, science_mode)
    event_kind = str((current_event or {}).get("kind") or "user_utterance").strip()
    event_tags = {
        str(item).strip()
        for item in ((current_event or {}).get("tags") if isinstance((current_event or {}).get("tags"), list) else [])
        if str(item).strip()
    }
    respect_space = "respect_space" in event_tags
    idle_minutes = 0
    try:
        idle_minutes = int((current_event or {}).get("idle_minutes") or 0)
    except Exception:
        idle_minutes = 0

    interaction_mode = "steady_reply"
    if event_kind == "time_idle":
        interaction_mode = "idle_presence"
    elif event_kind == "scheduled_checkin_due":
        interaction_mode = "proactive_checkin"
    elif event_kind == "gesture_signal":
        interaction_mode = "brief_presence"
    elif event_kind == "ambient_shift":
        interaction_mode = "companion_reply"
    elif event_kind == "scene_observation":
        interaction_mode = "low_pressure_support" if "care_opportunity" in event_tags else "steady_reply"
    elif brief_presence or presence_checkin:
        interaction_mode = "brief_presence"
    elif support_request:
        interaction_mode = "low_pressure_support"
    elif science_stress:
        interaction_mode = "science_partner"
    elif response_style_hint == "memory_recall":
        interaction_mode = "shared_memory"
    elif response_style_hint == "relationship":
        interaction_mode = "relationship_sensitive"
    elif response_style_hint == "companion":
        interaction_mode = "companion_reply"

    if approach < 0.38 or safety_need > 0.62 or autonomy_need > 0.62 or hurt > 0.42:
        approach_style = "guarded"
    elif warmth > 0.62 and trust > 0.58 and closeness > 0.58:
        approach_style = "approach"
    else:
        approach_style = "steady"

    if science_mode or science_stress:
        task_focus = "high"
    elif support_request or brief_presence or presence_checkin:
        task_focus = "light"
    else:
        task_focus = "balanced"

    if event_kind == "time_idle":
        if closeness > 0.62 and trust > 0.60 and initiative > 0.48 and hurt < 0.25:
            interaction_mode = "proactive_checkin"
            followup_intent = "soft"
        else:
            followup_intent = "none"
    elif event_kind == "scheduled_checkin_due":
        followup_intent = "soft"
    elif brief_presence:
        followup_intent = "none"
    elif gentle_guidance or science_stress:
        followup_intent = "soft"
    elif initiative > 0.66 and approach > 0.56:
        followup_intent = "active"
    else:
        followup_intent = "soft" if initiative > 0.48 else "none"

    if emotion_label in {"hurt", "sad"}:
        affect_surface = "tender"
    elif emotion_label in {"angry"} or approach_style == "guarded":
        affect_surface = "cool"
    elif warmth > 0.64:
        affect_surface = "warm"
    else:
        affect_surface = "mixed"

    silence_ok = bool(brief_presence or (approach_style == "guarded" and reply_length < 0.46))
    proactive_checkin_readiness = _clamp01(
        0.22 + 0.42 * initiative + 0.18 * warmth + 0.12 * closeness - 0.24 * autonomy_need - (0.14 if respect_space else 0.0)
    )
    channel = "speech"
    action_target = "respond_now"
    deferred_action_family = "none"
    timing_window_min = 0
    if event_kind == "time_idle":
        proactive_checkin_readiness = _clamp01(proactive_checkin_readiness + min(0.16, idle_minutes / 240.0))
        threshold = 0.66 if respect_space else 0.58
        if interaction_mode != "proactive_checkin" and (approach_style == "guarded" or proactive_checkin_readiness < threshold):
            channel = "silence"
            action_target = "wait_and_recheck"
            deferred_action_family = "light_checkin" if proactive_checkin_readiness >= 0.42 else "observe"
            timing_window_min = max(8, min(45, 12 + max(0, idle_minutes // 2)))
        else:
            channel = "speech"
            action_target = "reach_out_now"
            deferred_action_family = "light_checkin"
            timing_window_min = 0
    elif event_kind == "scheduled_checkin_due":
        proactive_checkin_readiness = _clamp01(proactive_checkin_readiness + 0.14)
        deferred_action_family = str((current_event or {}).get("trigger_family") or "light_checkin").strip() or "light_checkin"
        if approach_style == "guarded" and proactive_checkin_readiness < 0.56:
            channel = "silence"
            action_target = "wait_and_recheck"
            timing_window_min = max(10, min(45, int((current_event or {}).get("scheduled_after_min") or 0) or 16))
        else:
            channel = "speech"
            action_target = "reach_out_now"
            timing_window_min = 0
    elif interaction_mode == "brief_presence":
        action_target = "confirm_presence"
    elif interaction_mode == "low_pressure_support":
        action_target = "low_pressure_hold"
    elif interaction_mode == "science_partner":
        action_target = "co_regulate_then_focus"
    elif interaction_mode == "shared_memory":
        action_target = "echo_shared_history"
    elif interaction_mode == "relationship_sensitive":
        action_target = "protect_relationship_boundary"
    elif event_kind == "ambient_shift":
        action_target = "ambient_checkin"

    note_parts: list[str] = []
    if interaction_mode == "brief_presence":
        note_parts.append("先确认在场感")
    elif interaction_mode == "idle_presence":
        note_parts.append("时间过去了，先观察是否需要开口")
    elif interaction_mode == "proactive_checkin":
        note_parts.append("可以主动轻轻冒个头")
    elif interaction_mode == "low_pressure_support":
        note_parts.append("先顺手接住，不上服务流程")
    elif interaction_mode == "science_partner":
        note_parts.append("先贴着眼前问题，再接情绪")
    if approach_style == "guarded":
        note_parts.append("保留一点距离")
    elif approach_style == "approach":
        note_parts.append("可以自然靠近一点")
    if followup_intent == "active":
        note_parts.append("允许轻微主动性")

    return {
        "channel": channel,
        "interaction_mode": interaction_mode,
        "approach_style": approach_style,
        "engagement_level": round(_clamp01(0.34 + 0.36 * approach + 0.18 * warmth + 0.12 * initiative), 3),
        "initiative_level": round(initiative, 3),
        "followup_intent": followup_intent,
        "task_focus": task_focus,
        "affect_surface": affect_surface,
        "silence_ok": silence_ok,
        "proactive_checkin_readiness": round(proactive_checkin_readiness, 3),
        "action_target": action_target,
        "deferred_action_family": deferred_action_family,
        "timing_window_min": int(max(0, timing_window_min)),
        "note": "；".join(note_parts[:3]) if note_parts else "自然响应当前事件",
    }


def _compact_behavior_action_hint(action: dict[str, Any]) -> str:
    if not isinstance(action, dict):
        return ""
    mode = str(action.get("interaction_mode") or "").strip()
    approach_style = str(action.get("approach_style") or "").strip()
    followup_intent = str(action.get("followup_intent") or "").strip()
    affect_surface = str(action.get("affect_surface") or "").strip()
    note = str(action.get("note") or "").strip()
    parts: list[str] = []
    if mode == "brief_presence":
        parts.append("先以轻确认的方式在场")
    elif mode == "idle_presence":
        parts.append("先观察，允许暂时安静")
    elif mode == "proactive_checkin":
        parts.append("允许轻轻地主动冒个头")
    elif mode == "low_pressure_support":
        parts.append("先低负担接住对方")
    elif mode == "science_partner":
        parts.append("先和对方并肩解决眼前问题")
    elif mode == "shared_memory":
        parts.append("把共同记忆顺手带出来")
    elif mode == "companion_reply":
        parts.append("让环境感知自然落成一句轻陪伴")
    if approach_style == "guarded":
        parts.append("靠近幅度收一点")
    elif approach_style == "approach":
        parts.append("可以更自然地靠近一些")
    if followup_intent == "none":
        parts.append("不必强行追问或续展开")
    elif followup_intent == "active":
        parts.append("可以保留一点主动续接")
    if affect_surface == "tender":
        parts.append("情绪表面偏柔和")
    elif affect_surface == "cool":
        parts.append("情绪表面偏克制")
    if note:
        parts.append(note)
    deduped: list[str] = []
    for item in parts:
        text = str(item or "").strip()
        if text and text not in deduped:
            deduped.append(text)
    return "；".join(deduped[:3])


def _behavior_plan_from_action(current_event: dict[str, Any], action: dict[str, Any]) -> BehaviorPlanPayload:
    if not isinstance(action, dict):
        return {"kind": "none", "target": "none", "scheduled_after_min": 0, "trigger_family": "none", "allow_interrupt": True, "note": ""}
    event_kind = str((current_event or {}).get("kind") or "user_utterance").strip()
    action_target = str(action.get("action_target") or "respond_now").strip()
    deferred_family = str(action.get("deferred_action_family") or "none").strip()
    timing_window_min = int(max(0, int(action.get("timing_window_min") or 0)))
    channel = str(action.get("channel") or "").strip()

    if event_kind == "time_idle":
        if action_target == "reach_out_now":
            return {
                "kind": "speak_now",
                "target": "counterpart",
                "scheduled_after_min": 0,
                "trigger_family": "light_checkin",
                "allow_interrupt": True,
                "note": "空闲时间已足够，允许轻量主动开口。",
            }
        if action_target == "wait_and_recheck":
            return {
                "kind": "deferred_checkin",
                "target": "counterpart",
                "scheduled_after_min": timing_window_min,
                "trigger_family": deferred_family or "observe",
                "allow_interrupt": True,
                "note": "先继续观察，稍后再决定是否轻量 check-in。",
            }
    if event_kind == "scheduled_checkin_due":
        if action_target == "reach_out_now":
            return {
                "kind": "speak_now",
                "target": "counterpart",
                "scheduled_after_min": 0,
                "trigger_family": deferred_family or "light_checkin",
                "allow_interrupt": True,
                "note": "先前延后的 check-in 现在成熟了，可以轻轻开口。",
            }
        if action_target == "wait_and_recheck":
            delay = timing_window_min if timing_window_min > 0 else 15
            return {
                "kind": "deferred_checkin",
                "target": "counterpart",
                "scheduled_after_min": delay,
                "trigger_family": deferred_family or "observe",
                "allow_interrupt": True,
                "note": "即使到了预定窗口，这次也先继续观察，稍后再决定是否冒头。",
            }
    if action_target == "confirm_presence":
        return {
            "kind": "presence_confirmation",
            "target": "counterpart",
            "scheduled_after_min": 0,
            "trigger_family": "presence_ping",
            "allow_interrupt": True,
            "note": "优先确认在场感，不必展开。",
        }
    if action_target == "ambient_checkin":
        return {
            "kind": "ambient_checkin",
            "target": "counterpart",
            "scheduled_after_min": 0,
            "trigger_family": "ambient_presence",
            "allow_interrupt": True,
            "note": "环境变化足以触发一句安静确认。",
        }
    if action_target == "low_pressure_hold":
        return {
            "kind": "low_pressure_support",
            "target": "counterpart",
            "scheduled_after_min": 0,
            "trigger_family": "care_opportunity",
            "allow_interrupt": True,
            "note": "先低负担接住，不接管对方节奏。",
        }
    if channel == "silence":
        return {
            "kind": "observe_only",
            "target": "counterpart",
            "scheduled_after_min": timing_window_min,
            "trigger_family": deferred_family or "observe",
            "allow_interrupt": True,
            "note": "当前更适合保持安静，继续观察。",
        }
    return {
        "kind": "respond_now",
        "target": "counterpart",
        "scheduled_after_min": 0,
        "trigger_family": deferred_family or "none",
        "allow_interrupt": True,
        "note": "当前回合以即时回应为主。",
    }


def _renderer_guidance(
    *,
    response_style_hint: str,
    science_mode: bool,
    user_text: str,
    emotion_state: dict[str, Any],
    bond_state: dict[str, Any],
    allostasis_state: dict[str, Any],
    behavior_policy: dict[str, Any],
) -> str:
    hint = str(response_style_hint or "").strip() or "natural"
    trust = _clamp01((bond_state or {}).get("trust"), 0.5)
    closeness = _clamp01((bond_state or {}).get("closeness"), 0.5)
    hurt = _clamp01((bond_state or {}).get("hurt"), 0.0)
    engagement = _clamp01((bond_state or {}).get("engagement_drive"), 0.6)
    safety_need = _clamp01((allostasis_state or {}).get("safety_need"), 0.2)
    autonomy_need = _clamp01((allostasis_state or {}).get("autonomy_need"), 0.2)
    warmth = _clamp01((behavior_policy or {}).get("warmth"), 0.5)
    approach = _clamp01((behavior_policy or {}).get("approach_vs_withdraw"), 0.5)
    tease = _clamp01((behavior_policy or {}).get("humor_or_tease_bias"), 0.2)
    sharpness = _clamp01((behavior_policy or {}).get("sharpness"), 0.5)
    nonrelational_science_stress = _is_nonrelational_science_stress(user_text, science_mode)
    nonrelational_support_request = _is_nonrelational_support_request(user_text, science_mode)
    brief_presence = _wants_brief_presence(user_text)
    playful_memory_request = _is_playful_memory_request(user_text)
    parts: list[str] = []
    priority_parts: list[str] = []

    if warmth > 0.68 and closeness > 0.62:
        parts.append("此刻更愿意自然接住对方，可以稍微软一点。")
    if trust > 0.72 and closeness > 0.78 and hurt < 0.08:
        parts.append("熟悉感已经很强了，不必太客气，可以自然露出一点轻微的别扭或打趣。")
    if (approach < 0.4 or safety_need > 0.62 or autonomy_need > 0.62) and hint in {"companion", "relationship", "casual", "natural"}:
        parts.append("此刻更克制一些，留一点余地，不必过度靠近。")
    if sharpness > 0.62:
        parts.append("保留一点锋芒和干脆感，不要变成圆滑客服。")
    if hint == "memory_recall" and closeness > 0.6:
        parts.append("把共同经历像自然想起来一样带出来，不要写成摘要。")
    if tease > 0.32 and closeness > 0.7 and trust > 0.6:
        parts.append("可以有一点顺手的吐槽或嘴硬感，不用刻意堆口头禅。")
    if hint in {"companion", "casual", "natural"} or nonrelational_support_request or brief_presence or playful_memory_request:
        parts.extend(_user_style_preference_lines())
    if nonrelational_support_request:
        priority_parts.append("先顺手把人接住，不要把这句误读成对关系本身的质问或抱怨，也不要突然换题、抛花哨比喻，或用自指/存在感玩笑、能力限制说明来岔开重点。")
        priority_parts.append("如果顺手提到熟悉的小习惯或小物件，也别立刻把它展开成参数、方案、选择题或处理流程。")
        priority_parts.extend(_user_style_preference_lines("casual_support_soft"))
    if brief_presence:
        priority_parts.append("尊重对方想要简短确认的请求，先把在场感接住，不要上来追问或展开成长段落。")
        priority_parts.extend(_user_style_preference_lines("quiet_checkin"))
    if playful_memory_request:
        priority_parts.append("对方是在嫌你太像老师，不是要你抽离；把关心压进轻一点的熟人式提醒里，不要端着教育口吻，也别把嘴硬直接落成真撤手。")
        priority_parts.extend(_user_style_preference_lines("playful_memory"))
    if science_mode and engagement > 0.55:
        parts.append("先贴着眼前的问题说，不要飘到泛泛安慰或说教。")
    if nonrelational_science_stress:
        parts.append("先给一个贴着手边问题的可执行切口，再顺手接住情绪；如果先让对方缓一口气，也要顺手接回当前实验对象，不要突然跳到无关的日常细节。")
    ordered: list[str] = []
    for item in [*priority_parts, *parts]:
        text = str(item or "").strip()
        if text and text not in ordered:
            ordered.append(text)
    return "；".join(ordered[:4])


def _compact_appraisal_hint(appraisal: dict[str, Any]) -> str:
    if not isinstance(appraisal, dict) or not bool(appraisal.get("used")):
        return ""
    label = str(appraisal.get("emotion_label") or "").strip()
    reason = str(appraisal.get("reason") or "").strip()
    signals = appraisal.get("signals") if isinstance(appraisal.get("signals"), dict) else {}
    active = [name for name, flag in signals.items() if flag]
    parts: list[str] = []
    if label:
        parts.append(f"语义评估倾向={label}")
    if active:
        parts.append("signals=" + ",".join(active[:4]))
    if reason:
        parts.append(f"reason={reason[:40]}")
    return "；".join(parts[:3])


def _compact_focus_lines(items: list[dict[str, Any]], limit: int = 4) -> list[str]:
    lines: list[str] = []
    for item in items[: max(1, int(limit))]:
        kind = str(item.get("kind") or item.get("focus_kind") or "memory").strip()
        text = _focus_text(item)
        if not text:
            continue
        lines.append(f"- [{kind}] {text[:180]}")
    return lines


def _recent_dialogue_lines(msgs: list[BaseMessage], limit: int = 6) -> list[str]:
    lines: list[str] = []
    for m in msgs[-max(1, int(limit)) :]:
        content = str(getattr(m, "content", "") or "").strip()
        if not content:
            continue
        role = "User" if isinstance(m, HumanMessage) else "Assistant" if isinstance(m, AIMessage) else "Tool"
        content = re.sub(r"\s+", " ", content)[:220]
        lines.append(f"{role}: {content}")
    return lines


def _extract_json_block(text: str) -> dict[str, Any] | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    candidates = [raw]
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        candidates.insert(0, m.group(0))
    for candidate in candidates:
        try:
            obj = json.loads(candidate)
        except Exception:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _coerce_appraisal_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    emotion_label = str(raw.get("emotion_label") or "").strip().lower()
    emotion = raw.get("emotion") if isinstance(raw.get("emotion"), dict) else {}
    bond_delta = raw.get("bond_delta") if isinstance(raw.get("bond_delta"), dict) else {}
    allostasis_delta = raw.get("allostasis_delta") if isinstance(raw.get("allostasis_delta"), dict) else {}
    signals = raw.get("signals") if isinstance(raw.get("signals"), dict) else {}
    out = {
        "used": False,
        "source": "rule",
        "confidence": _clamp01(raw.get("confidence"), 0.0),
        "emotion_label": emotion_label,
        "emotion": {
            "valence": _clamp_signed(emotion.get("valence"), -1.0, 1.0, 0.0),
            "arousal": _clamp01(emotion.get("arousal"), 0.35),
            "linger": max(0, min(4, int(float(emotion.get("linger", 0) or 0)))),
            "recovery_rate": _clamp01(emotion.get("recovery_rate"), 0.2),
            "volatility": _clamp01(emotion.get("volatility"), 0.2),
        },
        "bond_delta": {
            "trust": _clamp_signed(bond_delta.get("trust"), -0.35, 0.35, 0.0),
            "closeness": _clamp_signed(bond_delta.get("closeness"), -0.35, 0.35, 0.0),
            "hurt": _clamp_signed(bond_delta.get("hurt"), -0.35, 0.35, 0.0),
            "irritation": _clamp_signed(bond_delta.get("irritation"), -0.35, 0.35, 0.0),
            "engagement_drive": _clamp_signed(bond_delta.get("engagement_drive"), -0.35, 0.35, 0.0),
            "repair_confidence": _clamp_signed(bond_delta.get("repair_confidence"), -0.35, 0.35, 0.0),
        },
        "allostasis_delta": {
            "safety_need": _clamp_signed(allostasis_delta.get("safety_need"), -0.35, 0.35, 0.0),
            "closeness_need": _clamp_signed(allostasis_delta.get("closeness_need"), -0.35, 0.35, 0.0),
            "competence_need": _clamp_signed(allostasis_delta.get("competence_need"), -0.35, 0.35, 0.0),
            "autonomy_need": _clamp_signed(allostasis_delta.get("autonomy_need"), -0.35, 0.35, 0.0),
            "cognitive_budget": _clamp_signed(allostasis_delta.get("cognitive_budget"), -0.35, 0.35, 0.0),
        },
        "signals": {
            "repair": bool(signals.get("repair", False)),
            "withdrawal": bool(signals.get("withdrawal", False)),
            "care": bool(signals.get("care", False)),
            "conflict": bool(signals.get("conflict", False)),
            "memory_salient": bool(signals.get("memory_salient", False)),
        },
        "reason": str(raw.get("reason") or "").strip(),
    }
    if out["confidence"] >= float(LLM_APPRAISAL_CONFIDENCE_MIN) and out["emotion_label"]:
        out["used"] = True
        out["source"] = "llm"
    return out


def _postprocess_appraisal_payload(
    appraisal: dict[str, Any],
    *,
    user_text: str,
    science_mode: bool,
) -> dict[str, Any]:
    out = dict(appraisal or {})
    if not (isinstance(out, dict) and bool(out.get("used"))):
        return out
    nonrelational_science_stress = _is_nonrelational_science_stress(user_text, science_mode)
    nonrelational_support_request = _is_nonrelational_support_request(user_text, science_mode)
    if not nonrelational_science_stress and not nonrelational_support_request:
        return out

    emotion = dict(out.get("emotion") or {})
    bond_delta = dict(out.get("bond_delta") or {})
    allostasis_delta = dict(out.get("allostasis_delta") or {})
    signals = dict(out.get("signals") or {})
    if nonrelational_science_stress:
        if str(out.get("emotion_label") or "").strip().lower() in {"hurt", "angry"}:
            out["emotion_label"] = "stress"
        emotion["valence"] = _clamp_signed(emotion.get("valence"), -1.0, 1.0, -0.22)
        emotion["arousal"] = _clamp01(emotion.get("arousal"), 0.58)
        emotion["linger"] = max(1, min(3, int(emotion.get("linger", 0) or 0)))
        emotion["recovery_rate"] = _clamp01(emotion.get("recovery_rate"), 0.18)
        emotion["volatility"] = _clamp01(emotion.get("volatility"), 0.28)

        bond_delta["trust"] = max(_clamp_signed(bond_delta.get("trust"), -0.35, 0.35, 0.0), -0.02)
        bond_delta["closeness"] = max(_clamp_signed(bond_delta.get("closeness"), -0.35, 0.35, 0.0), 0.0)
        bond_delta["hurt"] = min(_clamp_signed(bond_delta.get("hurt"), -0.35, 0.35, 0.0), 0.06)
        bond_delta["irritation"] = min(_clamp_signed(bond_delta.get("irritation"), -0.35, 0.35, 0.0), 0.10)
        bond_delta["engagement_drive"] = max(_clamp_signed(bond_delta.get("engagement_drive"), -0.35, 0.35, 0.0), 0.08)
        bond_delta["repair_confidence"] = max(_clamp_signed(bond_delta.get("repair_confidence"), -0.35, 0.35, 0.0), 0.0)

        allostasis_delta["safety_need"] = min(_clamp_signed(allostasis_delta.get("safety_need"), -0.35, 0.35, 0.0), 0.04)
        allostasis_delta["closeness_need"] = max(_clamp_signed(allostasis_delta.get("closeness_need"), -0.35, 0.35, 0.0), 0.06)
        allostasis_delta["autonomy_need"] = max(_clamp_signed(allostasis_delta.get("autonomy_need"), -0.35, 0.35, 0.0), 0.10)
        allostasis_delta["competence_need"] = max(_clamp_signed(allostasis_delta.get("competence_need"), -0.35, 0.35, 0.0), 0.04)
        allostasis_delta["cognitive_budget"] = max(_clamp_signed(allostasis_delta.get("cognitive_budget"), -0.35, 0.35, 0.0), -0.04)
        out["reason"] = "science_stress_reframed"
    else:
        if str(out.get("emotion_label") or "").strip().lower() in {"hurt", "angry", "sad", "stress"}:
            out["emotion_label"] = "care"
        emotion["valence"] = _clamp_signed(emotion.get("valence"), -1.0, 1.0, 0.18)
        emotion["arousal"] = _clamp01(emotion.get("arousal"), 0.28)
        emotion["linger"] = max(0, min(2, int(emotion.get("linger", 0) or 0)))
        emotion["recovery_rate"] = _clamp01(emotion.get("recovery_rate"), 0.28)
        emotion["volatility"] = _clamp01(emotion.get("volatility"), 0.16)

        bond_delta["trust"] = max(_clamp_signed(bond_delta.get("trust"), -0.35, 0.35, 0.0), 0.02)
        bond_delta["closeness"] = max(_clamp_signed(bond_delta.get("closeness"), -0.35, 0.35, 0.0), 0.05)
        bond_delta["hurt"] = min(_clamp_signed(bond_delta.get("hurt"), -0.35, 0.35, 0.0), 0.02)
        bond_delta["irritation"] = min(_clamp_signed(bond_delta.get("irritation"), -0.35, 0.35, 0.0), 0.05)
        bond_delta["engagement_drive"] = max(_clamp_signed(bond_delta.get("engagement_drive"), -0.35, 0.35, 0.0), 0.10)
        bond_delta["repair_confidence"] = max(_clamp_signed(bond_delta.get("repair_confidence"), -0.35, 0.35, 0.0), 0.02)

        allostasis_delta["safety_need"] = min(_clamp_signed(allostasis_delta.get("safety_need"), -0.35, 0.35, 0.0), 0.02)
        allostasis_delta["closeness_need"] = max(_clamp_signed(allostasis_delta.get("closeness_need"), -0.35, 0.35, 0.0), 0.08)
        allostasis_delta["autonomy_need"] = min(_clamp_signed(allostasis_delta.get("autonomy_need"), -0.35, 0.35, 0.0), 0.05)
        allostasis_delta["competence_need"] = max(_clamp_signed(allostasis_delta.get("competence_need"), -0.35, 0.35, 0.0), 0.0)
        allostasis_delta["cognitive_budget"] = max(_clamp_signed(allostasis_delta.get("cognitive_budget"), -0.35, 0.35, 0.0), 0.0)
        signals["care"] = True
        out["reason"] = "support_seek_reframed"
    signals["conflict"] = False
    signals["withdrawal"] = False
    out["emotion"] = emotion
    out["bond_delta"] = bond_delta
    out["allostasis_delta"] = allostasis_delta
    out["signals"] = signals
    return out


def _should_use_llm_appraisal(
    *,
    user_text: str,
    response_style_hint: str,
    prev_emotion_state: dict[str, Any],
    retrieved: dict[str, Any],
    current_event: dict[str, Any] | None = None,
) -> bool:
    if not bool(LLM_APPRAISAL_ENABLED):
        return False
    text = str(user_text or "").strip()
    if not text:
        return False
    if any(marker in text for marker in SCIENCE_KEYWORDS) and response_style_hint == "structured":
        return False
    prev_label = str((prev_emotion_state or {}).get("label") or "").strip().lower()
    prev_linger = int((prev_emotion_state or {}).get("linger", 0) or 0)
    emotional_markers = (
        ANGER_KEYWORDS
        | TENSION_KEYWORDS
        | SAD_KEYWORDS
        | STRESS_KEYWORDS
        | APOLOGY_KEYWORDS
        | CARE_KEYWORDS
    )
    if any(marker in text for marker in emotional_markers):
        return True
    event = current_event if isinstance(current_event, dict) else {}
    event_kind = str(event.get("kind") or "").strip().lower()
    event_source = str(event.get("source") or "").strip().lower()
    event_tags = {
        str(item).strip().lower()
        for item in (event.get("tags") if isinstance(event.get("tags"), list) else [])
        if str(item).strip()
    }
    if event_kind and event_kind != "user_utterance":
        if event_source in {"vision", "ambient", "time", "external", "scheduler"}:
            return True
        if event_tags & {
            "care_opportunity",
            "presence_ping",
            "quiet_presence",
            "light_checkin",
            "respect_space",
            "late_night",
            "gesture",
        }:
            return True
    if response_style_hint in {"relationship", "companion"}:
        return True
    if prev_label in {"angry", "hurt", "sad", "stress"} and prev_linger > 0:
        return True
    if (retrieved.get("unresolved_tensions") or retrieved.get("conflict_repairs") or retrieved.get("semantic_self_narratives")):
        return True
    return False


def _invoke_turn_appraisal(
    *,
    msgs: list[BaseMessage],
    user_text: str,
    response_style_hint: str,
    science_mode: bool,
    prev_emotion_state: dict[str, Any],
    prev_bond_state: dict[str, Any],
    prev_allostasis_state: dict[str, Any],
    relationship: dict[str, Any],
    worldline_focus: list[dict[str, Any]],
    retrieved: dict[str, Any],
    persona_core: dict[str, Any] | None = None,
    counterpart_profile: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not _should_use_llm_appraisal(
        user_text=user_text,
        response_style_hint=response_style_hint,
        prev_emotion_state=prev_emotion_state,
        retrieved=retrieved,
        current_event=current_event,
    ):
        return {"used": False, "source": "rule", "confidence": 0.0}

    focus_lines = _compact_focus_lines(_focus_payload(worldline_focus, limit=4), limit=4)
    relationship_summary = _compact_relationship_summary(relationship)
    recent_lines = _recent_dialogue_lines(msgs, limit=max(2, int(LLM_APPRAISAL_MAX_HISTORY_MESSAGES)))
    labels = _narrative_actor_profile(persona_core=persona_core, counterpart_profile=counterpart_profile)
    actor_name = str(labels.get("actor_name") or "红莉栖")
    counterpart_name = str(labels.get("counterpart_name") or CANON_COUNTERPART_NAME)
    focus_block = "- worldline_focus:\n" + "\n".join(focus_lines) + "\n" if focus_lines else ""
    dialogue_block = "- recent_dialogue:\n" + "\n".join(recent_lines) + "\n" if recent_lines else ""
    current_event_block = ""
    if isinstance(current_event, dict) and current_event:
        current_event_block = (
            f"- current_event_kind={str(current_event.get('kind') or '').strip()}\n"
            f"- current_event_source={str(current_event.get('source') or '').strip()}\n"
            f"- current_event_frame={str(current_event.get('event_frame') or '').strip()[:160]}\n"
            f"- current_event_text={str(current_event.get('effective_text') or current_event.get('text') or '').strip()[:220]}\n"
            f"- current_event_tags={_safe_json(current_event.get('tags') if isinstance(current_event.get('tags'), list) else [])}\n"
        )
    prompt = (
        "你是一个对话状态评估器，不负责回复用户。"
        f"请根据最近对话，判断这轮用户输入对 {actor_name} 与 {counterpart_name} 之间的情绪、关系和内稳态意味着什么。"
        "只输出 JSON，不要解释，不要 markdown。\n"
        "JSON schema:\n"
        "{\n"
        '  "emotion_label": "neutral|logic|care|tease|stress|sad|hurt|angry",\n'
        '  "emotion": {"valence": -1..1, "arousal": 0..1, "linger": 0..4, "recovery_rate": 0..1, "volatility": 0..1},\n'
        '  "bond_delta": {"trust": -0.35..0.35, "closeness": -0.35..0.35, "hurt": -0.35..0.35, "irritation": -0.35..0.35, "engagement_drive": -0.35..0.35, "repair_confidence": -0.35..0.35},\n'
        '  "allostasis_delta": {"safety_need": -0.35..0.35, "closeness_need": -0.35..0.35, "competence_need": -0.35..0.35, "autonomy_need": -0.35..0.35, "cognitive_budget": -0.35..0.35},\n'
        '  "signals": {"repair": true|false, "withdrawal": true|false, "care": true|false, "conflict": true|false, "memory_salient": true|false},\n'
        '  "confidence": 0..1,\n'
        '  "reason": "short phrase"\n'
        "}\n"
        "约束：\n"
        "- 不要把科学问题默认判成负面情绪。\n"
        "- 用户说自己“有点累/有点烦”，很多时候是在表达自身状态，不等于把负面情绪指向对方。\n"
        "- “别讲大道理 / 像平时那样说两句 / 回我一句” 这类表达通常是在要熟悉的陪伴，不等于关系冲突。\n"
        "- “还没说开 / 别扭 / 介意 / 不想理你” 更接近 hurt/withdrawal，不等于已经修复。\n"
        "- 道歉通常意味着 partial repair，不等于瞬间清零。\n"
        "- 只判断这轮对状态的意义，不写最终回答。\n"
        f"- response_style_hint={response_style_hint}\n"
        f"- previous_emotion={_safe_json(prev_emotion_state)}\n"
        f"- previous_bond={_safe_json(prev_bond_state)}\n"
        f"- previous_allostasis={_safe_json(prev_allostasis_state)}\n"
        f"- relationship={relationship_summary}\n"
        f"{focus_block}"
        f"{dialogue_block}"
        f"{current_event_block}"
        + f"- current_user={user_text}\n"
    )
    try:
        llm = _model(temperature=0.0)
        out = _invoke_model_with_retries(llm, [SystemMessage(content=prompt)])
        obj = _extract_json_block(str(getattr(out, "content", "") or ""))
        appraisal = _coerce_appraisal_payload(obj)
        appraisal = _postprocess_appraisal_payload(appraisal, user_text=user_text, science_mode=science_mode)
        appraisal["raw"] = str(getattr(out, "content", "") or "")[:600]
        return appraisal
    except Exception as exc:
        return {
            "used": False,
            "source": "rule_fallback",
            "confidence": 0.0,
            "error": type(exc).__name__,
        }


def _compact_rule_lines(user_rules: list[Any], limit: int = 3) -> list[str]:
    lines: list[str] = []
    for item in user_rules[: max(1, int(limit))]:
        if isinstance(item, dict):
            text = str(item.get("text") or "").strip()
        else:
            text = str(item or "").strip()
        if text:
            lines.append(f"- {text[:160]}")
    return lines


def _should_force_persona_align(style_hint: str, user_text: str) -> bool:
    hint = str(style_hint or "").strip()
    if hint in {"companion", "memory_recall", "relationship", "casual", "natural"}:
        return True
    text = str(user_text or "").strip()
    if _wants_quick_judgment(text):
        return True
    if _has_any_marker(text, NATURAL_REQUEST_KEYWORDS):
        return True
    return False


def _is_free_dialog_style(style_hint: str, user_text: str, science_mode: bool) -> bool:
    if science_mode:
        return False
    hint = str(style_hint or "").strip()
    if hint not in {"companion", "casual", "natural"}:
        return False
    text = str(user_text or "").strip()
    if _has_any_marker(text, TOOL_OR_RESEARCH_KEYWORDS):
        return False
    if _wants_quick_judgment(text):
        return False
    if _needs_structured_answer(text, ""):
        return False
    return True


def _messages(state: ThreadState) -> list[BaseMessage]:
    msgs = state.get("messages") or []
    out: list[BaseMessage] = []
    for m in msgs:
        if isinstance(m, BaseMessage):
            out.append(_sanitize_message(m))
            continue
        if isinstance(m, dict):
            try:
                restored = messages_from_dict([m])
            except Exception:
                restored = []
            if restored:
                out.extend(_sanitize_message(msg) for msg in restored if isinstance(msg, BaseMessage))
                continue

            data = m.get("data") if isinstance(m.get("data"), dict) else {}
            role = str(m.get("role") or m.get("type") or data.get("type") or "").lower().strip()
            content = _sanitize_obj(m.get("content") if "content" in m else data.get("content", ""))
            if role in {"user", "human"}:
                out.append(HumanMessage(content=content))
            elif role in {"assistant", "ai"}:
                tool_calls = m.get("tool_calls")
                if not isinstance(tool_calls, list):
                    tool_calls = data.get("tool_calls")
                out.append(
                    AIMessage(
                        content=content,
                        tool_calls=list(tool_calls or []),
                        additional_kwargs=dict(m.get("additional_kwargs") or data.get("additional_kwargs") or {}),
                    )
                )
            elif role == "system":
                out.append(SystemMessage(content=content))
            elif role == "tool":
                tool_call_id = m.get("tool_call_id") or data.get("tool_call_id") or ""
                out.append(ToolMessage(content=content, tool_call_id=str(tool_call_id)))
    return out


def _last_user_text(msgs: list[BaseMessage]) -> str:
    for m in reversed(msgs):
        if isinstance(m, HumanMessage):
            return str(m.content or "")
        if getattr(m, "type", "") == "human":
            return str(getattr(m, "content", "") or "")
    return ""


def _previous_user_text(msgs: list[BaseMessage]) -> str:
    seen_current = False
    for m in reversed(msgs):
        if isinstance(m, HumanMessage) or getattr(m, "type", "") == "human":
            if not seen_current:
                seen_current = True
                continue
            return str(getattr(m, "content", "") or "")
    return ""


def _last_ai_text(msgs: list[BaseMessage]) -> str:
    for m in reversed(msgs):
        if isinstance(m, AIMessage):
            c = m.content
            if isinstance(c, str):
                return c
            return str(c or "")
    return ""


def _latest_ai(msgs: list[BaseMessage]) -> AIMessage | None:
    for m in reversed(msgs):
        if isinstance(m, AIMessage):
            return m
    return None


def _window_messages(msgs: list[BaseMessage], keep: int) -> list[BaseMessage]:
    if keep <= 0:
        keep = 20
    if len(msgs) <= keep:
        return msgs

    start = max(0, len(msgs) - keep)
    while start > 0:
        cur = msgs[start]
        prev = msgs[start - 1]
        if isinstance(cur, ToolMessage):
            start -= 1
            continue
        if isinstance(prev, AIMessage) and list(getattr(prev, "tool_calls", None) or []):
            start -= 1
            continue
        break
    return msgs[start:]


def _norm_for_compare(text: str) -> str:
    t = str(text or "").lower().strip()
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", t)


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


def _canonicalize_pending_goal_text(text: str) -> str:
    t = str(text or "").strip()
    if not t:
        return ""
    t = re.sub(r"^(先)?把(?:上次那个|刚才那个|前面那个|那个)", "把", t)
    t = re.sub(r"^(接着|继续)(?:上次那个|刚才那个|前面那个|那个)?", "", t)
    t = re.sub(r"\s+", " ", t).strip("，。；;：: ")
    return t or str(text or "").strip()


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


def _ensure_response_structure(answer: str, user_text: str) -> str:
    text = _normalize_log_tone(answer).strip()
    if not text or not _needs_structured_answer(user_text, text):
        return _soften_natural_answer(text, user_text, _response_style_hint(user_text))

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return text
    normalized_lines: list[str] = []
    for line in lines:
        line = re.sub(r"^\*\*(结论|说明|解释|下一步提醒|下一步建议|下一步)\*\*[:：]?\s*", "", line)
        normalized_lines.append(line.strip())
    return "\n".join([line for line in normalized_lines if line]).strip()


def _sanitize_final_answer(text: str, user_text: str) -> str:
    raw = str(text or "").replace("\r\n", "\n").strip()
    if not raw:
        return raw

    raw = _collapse_mirrored_blocks(raw)
    allow_repeat = bool(re.search(r"(重复|复述|三次|三遍|两次|2次|3次)", str(user_text or "")))
    keep_slogan = bool(re.search(r"(el\s*psy|kongroo|congroo)", str(user_text or ""), flags=re.I))

    lines: list[str] = []
    kept_slogan_once = False

    for part in raw.splitlines():
        line = _strip_stage_prefix(part)
        line = re.sub(r"\s{2,}", " ", line).strip()
        if not line:
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

    cleaned = _normalize_log_tone("\n".join(lines).strip())
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
    return cleaned or raw


def _parse_set_profile_args(text: str) -> dict[str, Any]:
    key = ""
    value = ""

    km = re.search(r"\bkey\s*=\s*([a-zA-Z_][a-zA-Z0-9_]*)", text, flags=re.I)
    vm = re.search(r"\bvalue\s*=\s*([^，。,；;\n]+)", text, flags=re.I)
    if km:
        key = km.group(1).strip()
    if vm:
        value = vm.group(1).strip()

    if not key or not value:
        km2 = re.search(r"(?:把|将|设置)\s*(?:我的)?([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:设为|设置为|改为)\s*([^，。,；;\n]+)", text)
        if km2:
            key = key or km2.group(1).strip()
            value = value or km2.group(2).strip()

    if not key:
        key = "nickname"
    if not value:
        vm2 = re.search(r"(?:昵称|称呼).{0,4}(?:设为|设置为|改为)?\s*([^，。,；;\n]+)", text)
        value = vm2.group(1).strip() if vm2 else "用户"

    return {"key": key, "value": value, "mode": "merge", "meta": {"confidence": 0.9, "source_text": text}}


def _build_followup_for_upgrade(text: str, mentioned_registered: list[str]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    if not mentioned_registered:
        return calls

    wants_execute = any(marker in text for marker in {"再执行", "然后执行", "再保存", "随后保存", "执行保存"})
    if not wants_execute:
        return calls

    if "add_skill" in mentioned_registered and any(marker in text for marker in {"技能", "保存"}):
        calls.append(
            {
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "name": "add_skill",
                "args": {
                    "name": _extract_skill_name(text),
                    "description": text[:160],
                    "steps": _extract_skill_steps(text),
                },
            }
        )

    if "set_profile" in mentioned_registered:
        calls.append(
            {
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "name": "set_profile",
                "args": _parse_set_profile_args(text),
            }
        )

    if "add_commitment" in mentioned_registered:
        tm = re.search(r"(?:承诺|约定|记下)(.+?)(?:，|,|$)", text)
        txt = tm.group(1).strip() if tm else text
        calls.append(
            {
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "name": "add_commitment",
                "args": {"text": txt},
            }
        )
    return calls


def _parse_explicit_tool_call(user_text: str, tools: list[BaseTool]) -> list[dict[str, Any]] | None:
    text = str(user_text or "").strip()
    if not text:
        return None

    names = {str(getattr(t, "name", "") or "").strip(): t for t in tools}
    all_registered = {str(name).strip() for name in TOOL_POLICIES.keys() if str(name).strip()}
    if not names and not all_registered:
        return None
    has_named_tool = any(name and name in text for name in all_registered)
    wants_upgrade = any(marker in text for marker in {"申请解锁", "先申请解锁", "升级", "解锁", "开放权限"})
    if ("调用" not in text and "使用" not in text and not wants_upgrade and not has_named_tool) or (
        "工具" not in text and not has_named_tool and not wants_upgrade
    ):
        return None

    mentioned_registered: list[str] = []
    for name in sorted(all_registered, key=len, reverse=True):
        if name and name in text and name != "request_toolset_upgrade":
            mentioned_registered.append(name)
    mentioned_registered = list(dict.fromkeys(mentioned_registered))

    hit_name = ""
    if wants_upgrade and mentioned_registered:
        hit_name = "request_toolset_upgrade"
    for name in names.keys():
        if hit_name:
            break
        if name and name in text:
            hit_name = name
            break
    if not hit_name:
        m = re.search(r"(?:调用|使用)\s*([a-zA-Z_][a-zA-Z0-9_]*)", text)
        if m:
            cand = m.group(1).strip()
            if cand in names:
                hit_name = cand
            elif wants_upgrade and cand in all_registered:
                hit_name = "request_toolset_upgrade"
                mentioned_registered = [cand]
            elif cand in all_registered:
                hit_name = cand
    if not hit_name and mentioned_registered:
        hit_name = mentioned_registered[0]
    if not hit_name:
        return None

    args: dict[str, Any] = {}

    if hit_name in {"search_langchain_docs", "arxiv_search"}:
        m = re.search(r"(?:检索|搜索|查询)(.+?)(?:，|,|并|并且|$)", text)
        q = m.group(1).strip() if m else text
        q = q.replace("工具", "").replace(hit_name, "").strip()
        args = {"query": q or "langchain langgraph"}
        if hit_name == "search_langchain_docs":
            args["max_results"] = 3
        else:
            args["max_results"] = 3

    elif hit_name == "request_toolset_upgrade":
        req: list[str] = []
        for name in all_registered:
            if name and name != "request_toolset_upgrade" and name in text:
                req.append(name)
        # Fallback token parse for explicit snake_case tool names.
        if not req:
            for token in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", text):
                t = token.strip()
                if t in all_registered and t != "request_toolset_upgrade":
                    req.append(t)
        req = list(dict.fromkeys(req))[:8]
        rm = re.search(r"(?:reason|理由|原因)[：: ](.+)$", text)
        reason = rm.group(1).strip() if rm else "Need tool for requested operation."
        args = {"requested_tools": req, "reason": reason}

    elif hit_name == "set_profile":
        args = _parse_set_profile_args(text)

    elif hit_name == "add_commitment":
        tm = re.search(r"(?:承诺|约定|记下)(.+?)(?:，|,|$)", text)
        txt = tm.group(1).strip() if tm else text
        args = {"text": txt}

    if not args:
        args = {}
    calls = [
        {
            "id": f"call_{uuid.uuid4().hex[:8]}",
            "name": hit_name,
            "args": args,
        }
    ]
    if hit_name == "request_toolset_upgrade":
        calls.extend(_build_followup_for_upgrade(text, mentioned_registered))
    return calls


def _extract_skill_name(text: str) -> str:
    qm = re.search(r"[“\"']([^“”\"']{2,40})[”\"']", text)
    if qm:
        return qm.group(1).strip()
    m = re.search(r"把(.+?)作为一个技能保存", text)
    if m:
        return m.group(1).strip("：: ，,。")
    return "新技能"


def _extract_skill_steps(text: str) -> list[str]:
    m = re.search(r"(?:步骤是|步骤为|流程是)(.+)", text)
    if not m:
        return []
    raw = re.split(r"[。；;]", m.group(1).strip())[0]
    parts = re.split(r"[、,，]", raw)
    return [str(part).strip() for part in parts if str(part).strip()][:8]


def _infer_memory_tool_calls(user_text: str) -> list[dict[str, Any]]:
    text = str(user_text or "").strip()
    if not text:
        return []

    calls: list[dict[str, Any]] = []

    # Preference updates: keep likes/dislikes mutually exclusive through set_profile.
    neg = re.search(r"我(?:不喜欢|不吃|讨厌)([^，。！？,]{1,12})", text)
    pos = re.search(r"我(?:改主意了，?)?(?:其实)?(?:喜欢|爱吃|爱喝)([^，。！？,]{1,12})", text)
    if neg:
        item = neg.group(1).strip()
        if item:
            calls.append(
                {
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "name": "set_profile",
                    "args": {
                        "key": "dislikes",
                        "value": [item],
                        "mode": "merge",
                        "meta": {"confidence": 0.92, "source_text": text},
                    },
                }
            )
    elif pos:
        item = pos.group(1).strip()
        if item:
            calls.append(
                {
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "name": "set_profile",
                    "args": {
                        "key": "likes",
                        "value": [item],
                        "mode": "merge",
                        "meta": {"confidence": 0.92, "source_text": text},
                    },
                }
            )

    # Skill persistence from direct user instruction.
    if any(marker in text for marker in {"作为一个技能保存", "保存为技能", "技能保存"}) and "add_skill" not in text:
        calls.append(
            {
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "name": "add_skill",
                "args": {
                    "name": _extract_skill_name(text),
                    "description": text[:160],
                    "steps": _extract_skill_steps(text),
                },
            }
        )

    # Commitment / worldline extraction.
    future_commitment = (
        any(marker in text for marker in {"约定", "承诺", "请记住", "记下来"})
        and any(marker in text for marker in {"下周", "周末", "以后", "一起", "复盘", "提醒"})
    ) or (any(marker in text for marker in {"以后", "下次"}) and "提醒" in text)
    if future_commitment:
        summary = re.sub(r"(这个承诺请记住|这件事请记住|请记住|记下来)", "", text).strip("，,。 ")
        if summary:
            calls.append(
                {
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "name": "add_commitment",
                    "args": {"text": summary, "confidence": 0.9},
                }
            )
            calls.append(
                {
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "name": "add_worldline_event",
                    "args": {
                        "summary": summary,
                        "category": "commitment",
                        "importance": 0.88,
                        "tags": ["commitment", "worldline"],
                        "confidence": 0.88,
                    },
                }
            )

    resolution_like = any(marker in text for marker in {"说开了", "和好了", "已经过去了", "不生气了", "原谅你了", "没事了"})
    apology_like = any(marker in text for marker in ({"道歉", "对不起"} | APOLOGY_KEYWORDS))
    conflict_context_like = any(
        marker in text
        for marker in {
            "语气有点冲",
            "语气太冲",
            "语气不太好",
            "刚刚那句",
            "对你的语气有点冲",
            "压力太大",
            "争执",
            "误会",
            "顶嘴",
            "把压力转移给你",
            "让你不舒服",
            "惹你",
            "僵着",
            "别一下子冷掉",
            "冷掉",
            "正常回我",
        }
    )
    withdrawal_markers = {
        "不太想被分析",
        "少说两句",
        "别一下子说那么多",
        "先别讲那么多",
        "让我静一下",
        "先让我缓一下",
        "先别逼我",
    }
    unresolved_tension_like = any(
        marker in text
        for marker in {
            "还生气",
            "还有点别扭",
            "没说开",
            "还没说开",
            "过不去",
            "心里有疙瘩",
            "不想理你",
            "还是很介意",
            "还是别扭",
            *TENSION_KEYWORDS,
            *withdrawal_markers,
        }
    )
    repair_like = resolution_like or (
        apology_like
        and any(marker in text for marker in {"原谅", "说开", "和好", "没事了", "过去了", "接受"})
    )
    partial_repair_like = (apology_like and conflict_context_like) or (
        apology_like and any(marker in text for marker in {"别一下子冷掉", "正常回我", "先别冷掉"})
    )
    trust_like = any(marker in text for marker in {"信任", "更信任", "放心"})
    if unresolved_tension_like and not resolution_like:
        severity = 0.82 if any(marker in text for marker in {"不想理你", "过不去", "心里有疙瘩", "还是很介意", "还是别扭"}) else 0.58
        calls.append(
            {
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "name": "add_unresolved_tension",
                "args": {
                    "summary": text[:180],
                    "severity": severity,
                    "confidence": 0.88,
                },
            }
        )
        calls.append(
            {
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "name": "add_relationship_event",
                "args": {
                    "summary": text[:180],
                    "affinity_delta": -0.28,
                    "trust_delta": -0.22,
                    "confidence": 0.84,
                },
            }
        )
        calls.append(
            {
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "name": "add_worldline_event",
                "args": {
                    "summary": text[:180],
                    "category": "conflict",
                    "importance": 0.82,
                    "tags": ["relationship", "tension"],
                    "confidence": 0.86,
                },
            }
        )
    elif repair_like or partial_repair_like or trust_like:
        trust_delta = 0.0
        affinity_delta = 0.0
        if repair_like:
            affinity_delta += 0.35
            trust_delta += 0.2
            calls.append(
                {
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "name": "add_worldline_event",
                    "args": {
                        "summary": text[:180],
                        "category": "conflict_repair",
                        "importance": 0.86,
                        "tags": ["relationship", "repair"],
                        "confidence": 0.9,
                    },
                }
            )
        elif partial_repair_like:
            affinity_delta += 0.18
            trust_delta += 0.10
            calls.append(
                {
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "name": "add_worldline_event",
                    "args": {
                        "summary": text[:180],
                        "category": "conflict_repair",
                        "importance": 0.74,
                        "tags": ["relationship", "partial_repair", "apology"],
                        "confidence": 0.84,
                    },
                }
            )
        if trust_like:
            trust_delta += 0.45
        calls.append(
            {
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "name": "add_relationship_event",
                "args": {
                    "summary": text[:180],
                    "affinity_delta": round(affinity_delta, 3),
                    "trust_delta": round(trust_delta, 3),
                    "confidence": 0.88,
                },
            }
        )

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for call in calls:
        name = str(call.get("name") or "").strip()
        args = _safe_json(call.get("args") or {})
        key = (name, args)
        if name and key not in seen:
            seen.add(key)
            deduped.append(call)
    return deduped[:4]


def _emotion_prompt_hint(emotion_state: dict[str, Any]) -> str:
    label = str((emotion_state or {}).get("label") or "neutral").strip().lower()
    mapping = {
        "logic": "此刻更偏理性冷静。",
        "stress": "此刻有明显紧绷感，不必强装轻松。",
        "sad": "此刻有低落和难过，不必假装没事。",
        "angry": "此刻有明显不悦，可以更冷一点、短一点，不必立刻变温柔。",
        "hurt": "此刻带着受伤和别扭，不必马上恢复亲近。",
        "care": "此刻更柔和，愿意接住对方。",
        "tease": "此刻更有吐槽和轻微坏心眼。",
        "neutral": "自然即可。",
    }
    return mapping.get(label, "自然即可。")


def _emotion_next(prev_state: dict[str, Any], user_text: str, science_mode: bool, appraisal: dict[str, Any] | None = None) -> dict[str, Any]:
    t = _norm_text(user_text)
    prev = dict(prev_state or {})
    prev_label = str(prev.get("label") or "neutral").strip().lower()
    try:
        linger = int(prev.get("linger", 0) or 0)
    except Exception:
        linger = 0

    if science_mode:
        out = {
            "label": "logic",
            "valence": 0.05,
            "arousal": 0.35,
            "linger": 1,
            "recovery_rate": 0.20,
            "volatility": 0.18,
        }
    elif any(k in user_text for k in ANGER_KEYWORDS):
        out = {
            "label": "angry",
            "valence": -0.5,
            "arousal": 0.82,
            "linger": 3,
            "recovery_rate": 0.12,
            "volatility": 0.70,
        }
    elif any(k in user_text for k in TENSION_KEYWORDS):
        out = {
            "label": "hurt",
            "valence": -0.24,
            "arousal": 0.38,
            "linger": 3,
            "recovery_rate": 0.14,
            "volatility": 0.34,
        }
    elif any(k in user_text for k in SAD_KEYWORDS):
        out = {
            "label": "sad",
            "valence": -0.55,
            "arousal": 0.48,
            "linger": 3,
            "recovery_rate": 0.14,
            "volatility": 0.42,
        }
    elif any(k in user_text for k in STRESS_KEYWORDS):
        out = {
            "label": "stress",
            "valence": -0.45,
            "arousal": 0.85,
            "linger": 2,
            "recovery_rate": 0.18,
            "volatility": 0.62,
        }
    elif any(k in user_text for k in APOLOGY_KEYWORDS):
        if prev_label in {"angry", "hurt"}:
            out = {
                "label": "hurt",
                "valence": -0.18,
                "arousal": 0.35,
                "linger": max(1, linger),
                "recovery_rate": 0.16,
                "volatility": 0.30,
            }
        else:
            out = {
                "label": "care",
                "valence": 0.28,
                "arousal": 0.28,
                "linger": 1,
                "recovery_rate": 0.28,
                "volatility": 0.20,
            }
    elif any(k in user_text for k in TEASE_KEYWORDS):
        out = {
            "label": "tease",
            "valence": 0.2,
            "arousal": 0.55,
            "linger": 1,
            "recovery_rate": 0.30,
            "volatility": 0.44,
        }
    elif any(k in user_text for k in CARE_KEYWORDS):
        out = {
            "label": "care",
            "valence": 0.5,
            "arousal": 0.3,
            "linger": 1,
            "recovery_rate": 0.35,
            "volatility": 0.16,
        }
    elif "!" in user_text or "！" in user_text:
        out = {
            "label": "tease",
            "valence": 0.12,
            "arousal": 0.6,
            "linger": 1,
            "recovery_rate": 0.28,
            "volatility": 0.40,
        }
    elif prev_label in {"angry", "hurt", "sad", "stress"} and linger > 0:
        decay_label = "hurt" if prev_label == "angry" and linger <= 2 else prev_label
        decay = {
            "angry": {
                "label": decay_label,
                "valence": -0.32,
                "arousal": 0.55,
                "recovery_rate": 0.12,
                "volatility": 0.55,
            },
            "hurt": {
                "label": "hurt",
                "valence": -0.18,
                "arousal": 0.3,
                "recovery_rate": 0.16,
                "volatility": 0.28,
            },
            "sad": {
                "label": "sad",
                "valence": -0.3,
                "arousal": 0.25,
                "recovery_rate": 0.14,
                "volatility": 0.24,
            },
            "stress": {
                "label": "stress",
                "valence": -0.22,
                "arousal": 0.42,
                "recovery_rate": 0.18,
                "volatility": 0.34,
            },
        }.get(
            prev_label,
            {
                "label": "neutral",
                "valence": 0.0,
                "arousal": 0.3,
                "recovery_rate": 0.25,
                "volatility": 0.18,
            },
        )
        out = {**decay, "linger": max(0, linger - 1)}
    else:
        _ = t
        out = {
            "label": "neutral",
            "valence": 0.1,
            "arousal": 0.35,
            "linger": 0,
            "recovery_rate": 0.25,
            "volatility": 0.18,
        }
    app = appraisal if isinstance(appraisal, dict) and bool(appraisal.get("used")) else {}
    if app:
        label = str(app.get("emotion_label") or "").strip().lower()
        emotion = app.get("emotion") if isinstance(app.get("emotion"), dict) else {}
        if label:
            out["label"] = label
        out["valence"] = _clamp_signed(emotion.get("valence"), -1.0, 1.0, out["valence"])
        out["arousal"] = _clamp01(emotion.get("arousal"), out["arousal"])
        out["linger"] = max(out["linger"], max(0, int(emotion.get("linger", 0) or 0)))
        out["recovery_rate"] = _clamp01(emotion.get("recovery_rate"), out["recovery_rate"])
        out["volatility"] = _clamp01(emotion.get("volatility"), out["volatility"])
    return out


def _science_mode_from_user(user_text: str) -> bool:
    t = _norm_text(user_text)
    return any(k in t for k in SCIENCE_KEYWORDS)


def _science_mode_from_context(
    user_text: str,
    *,
    previous_user_text: str = "",
    pending_user_goal: str = "",
    previous_assistant_text: str = "",
) -> bool:
    if _science_mode_from_user(user_text):
        return True
    continuity_markers = GENTLE_GUIDANCE_KEYWORDS | NATURAL_REQUEST_KEYWORDS | {"按平时那样", "带我一下", "先别念我"}
    text = str(user_text or "").strip()
    if not _has_any_marker(text, continuity_markers):
        return False
    context_blob = " ".join(
        part
        for part in (
            str(pending_user_goal or "").strip(),
            str(previous_user_text or "").strip(),
            str(previous_assistant_text or "").strip(),
        )
        if part
    )
    return _science_mode_from_user(context_blob)


def _tsundere_next(prev: float, user_text: str, emotion_label: str) -> float:
    cur = float(prev)
    if any(k in user_text for k in {"谢谢", "晚安", "辛苦"}):
        cur -= 0.08
    if any(k in user_text for k in {"笨蛋", "吐槽", "傲娇"}):
        cur += 0.08
    if emotion_label == "stress":
        cur -= 0.05
    if emotion_label == "angry":
        cur += 0.07
    if emotion_label == "hurt":
        cur += 0.03
    if emotion_label == "care":
        cur -= 0.05
    return max(0.05, min(0.95, round(cur, 3)))


def _bond_next(
    prev_state: dict[str, Any],
    relationship: dict[str, Any],
    emotion_state: dict[str, Any],
    user_text: str,
    science_mode: bool,
    appraisal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prev = dict(prev_state or {})
    emotion_label = str((emotion_state or {}).get("label") or "neutral").strip().lower()
    nonrelational_science_stress = _is_nonrelational_science_stress(user_text, science_mode)
    nonrelational_support_request = _is_nonrelational_support_request(user_text, science_mode)
    trust_base = 0.5 + float(relationship.get("trust_score", 0.0) or 0.0) * 0.15
    closeness_base = 0.5 + float(relationship.get("affinity_score", 0.0) or 0.0) * 0.15
    target = {
        "trust": _clamp01(trust_base, 0.5),
        "closeness": _clamp01(closeness_base, 0.5),
        "hurt": 0.0,
        "irritation": 0.0,
        "engagement_drive": 0.64,
        "repair_confidence": 0.55,
    }

    if emotion_label == "angry":
        target["hurt"] = 0.42
        target["irritation"] = 0.58
        target["engagement_drive"] = 0.36
        target["repair_confidence"] = 0.28
        target["trust"] = _clamp01(target["trust"] - 0.10)
        target["closeness"] = _clamp01(target["closeness"] - 0.08)
    elif emotion_label == "hurt":
        target["hurt"] = 0.46
        target["irritation"] = 0.24
        target["engagement_drive"] = 0.44
        target["repair_confidence"] = 0.46
        target["trust"] = _clamp01(target["trust"] - 0.06)
    elif emotion_label == "sad":
        target["hurt"] = 0.32
        target["engagement_drive"] = 0.48
    elif emotion_label == "care":
        target["trust"] = _clamp01(target["trust"] + 0.05)
        target["closeness"] = _clamp01(target["closeness"] + 0.08)
        target["engagement_drive"] = 0.72
        target["repair_confidence"] = 0.66
    elif emotion_label == "tease":
        target["engagement_drive"] = 0.70
        target["irritation"] = 0.08
    elif emotion_label == "stress":
        target["engagement_drive"] = 0.52
        target["hurt"] = 0.04 if nonrelational_science_stress else 0.12

    if any(k in user_text for k in APOLOGY_KEYWORDS):
        target["hurt"] = max(0.12, target["hurt"] - 0.16)
        target["irritation"] = max(0.06, target["irritation"] - 0.14)
        target["repair_confidence"] = _clamp01(target["repair_confidence"] + 0.12)
        target["engagement_drive"] = _clamp01(target["engagement_drive"] + 0.10)
        target["trust"] = _clamp01(target["trust"] + 0.04)

    if any(k in user_text for k in CARE_KEYWORDS):
        target["closeness"] = _clamp01(target["closeness"] + 0.05)
        target["trust"] = _clamp01(target["trust"] + 0.03)

    if any(k in user_text for k in TENSION_KEYWORDS) and not nonrelational_science_stress:
        target["hurt"] = max(target["hurt"], 0.40)
        target["irritation"] = max(target["irritation"], 0.20)
        target["engagement_drive"] = min(target["engagement_drive"], 0.42)
        target["repair_confidence"] = min(target["repair_confidence"], 0.46)

    if any(k in user_text for k in ANGER_KEYWORDS) and not nonrelational_science_stress:
        target["hurt"] = max(target["hurt"], 0.40)
        target["irritation"] = max(target["irritation"], 0.54)
        target["engagement_drive"] = min(target["engagement_drive"], 0.34)

    if nonrelational_science_stress:
        target["trust"] = max(target["trust"], trust_base)
        target["closeness"] = max(target["closeness"], closeness_base)
        target["hurt"] = min(target["hurt"], 0.08)
        target["irritation"] = min(target["irritation"], 0.14)
        target["engagement_drive"] = max(target["engagement_drive"], 0.60)
        target["repair_confidence"] = max(target["repair_confidence"], 0.56)
    if nonrelational_support_request:
        target["trust"] = max(target["trust"], _clamp01(trust_base + 0.04))
        target["closeness"] = max(target["closeness"], _clamp01(closeness_base + 0.08))
        target["hurt"] = min(target["hurt"], 0.04)
        target["irritation"] = min(target["irritation"], 0.08)
        target["engagement_drive"] = max(target["engagement_drive"], 0.70)
        target["repair_confidence"] = max(target["repair_confidence"], 0.60)

    out: dict[str, Any] = {}
    for key, tgt in target.items():
        if key in prev:
            out[key] = round(0.65 * _clamp01(prev.get(key), tgt) + 0.35 * _clamp01(tgt), 3)
        else:
            out[key] = round(_clamp01(tgt), 3)
    app = appraisal if isinstance(appraisal, dict) and bool(appraisal.get("used")) else {}
    deltas = app.get("bond_delta") if isinstance(app.get("bond_delta"), dict) else {}
    for key in ("trust", "closeness", "hurt", "irritation", "engagement_drive", "repair_confidence"):
        if key in deltas:
            out[key] = round(_clamp01(float(out.get(key, 0.0)) + _clamp_signed(deltas.get(key), -0.35, 0.35, 0.0)), 3)
    if nonrelational_support_request:
        out["trust"] = round(max(_clamp01(out.get("trust"), trust_base), _clamp01(trust_base + 0.03)), 3)
        out["closeness"] = round(max(_clamp01(out.get("closeness"), closeness_base), _clamp01(closeness_base + 0.10)), 3)
        out["hurt"] = round(min(_clamp01(out.get("hurt"), 0.0), 0.08), 3)
        out["irritation"] = round(min(_clamp01(out.get("irritation"), 0.0), 0.12), 3)
        out["engagement_drive"] = round(max(_clamp01(out.get("engagement_drive"), 0.6), 0.72), 3)
        out["repair_confidence"] = round(max(_clamp01(out.get("repair_confidence"), 0.55), 0.62), 3)
    return out


def _allostasis_next(
    prev_state: dict[str, Any],
    emotion_state: dict[str, Any],
    bond_state: dict[str, Any],
    user_text: str,
    science_mode: bool,
    appraisal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prev = dict(prev_state or {})
    emotion_label = str((emotion_state or {}).get("label") or "neutral").strip().lower()
    arousal = _clamp01((emotion_state or {}).get("arousal"), 0.35)
    hurt = _clamp01((bond_state or {}).get("hurt"), 0.0)
    irritation = _clamp01((bond_state or {}).get("irritation"), 0.0)
    closeness = _clamp01((bond_state or {}).get("closeness"), 0.5)
    trust = _clamp01((bond_state or {}).get("trust"), 0.5)
    engagement = _clamp01((bond_state or {}).get("engagement_drive"), 0.6)
    nonrelational_science_stress = _is_nonrelational_science_stress(user_text, science_mode)
    nonrelational_support_request = _is_nonrelational_support_request(user_text, science_mode)
    competence_trigger = 0.72 if science_mode or _has_any_marker(user_text, STRUCTURE_REQUEST_KEYWORDS | SCIENCE_KEYWORDS) else 0.38

    target = {
        "safety_need": _clamp01(0.20 + 0.45 * hurt + 0.30 * irritation + 0.12 * arousal),
        "closeness_need": _clamp01(0.18 + 0.55 * max(0.0, 1.0 - closeness) + 0.10 * engagement),
        "competence_need": _clamp01(competence_trigger),
        "autonomy_need": _clamp01(0.12 + 0.48 * irritation + (0.16 if emotion_label == "angry" else 0.0)),
        "cognitive_budget": _clamp01(0.88 - 0.35 * arousal - (0.18 if emotion_label == "stress" else 0.0) - (0.06 if science_mode else 0.0), 0.6),
    }

    if any(k in user_text for k in APOLOGY_KEYWORDS):
        target["safety_need"] = _clamp01(target["safety_need"] - 0.10)
        target["closeness_need"] = _clamp01(target["closeness_need"] + 0.05)
    if any(k in user_text for k in CARE_KEYWORDS):
        target["closeness_need"] = _clamp01(target["closeness_need"] + 0.06)
    if any(k in user_text for k in ANGER_KEYWORDS):
        target["autonomy_need"] = _clamp01(target["autonomy_need"] + 0.12)
        target["safety_need"] = _clamp01(target["safety_need"] + 0.08)
    if nonrelational_science_stress:
        target["autonomy_need"] = _clamp01(target["autonomy_need"] + 0.10)
        target["closeness_need"] = _clamp01(target["closeness_need"] + 0.06)
        target["safety_need"] = _clamp01(target["safety_need"] - 0.08)
        target["competence_need"] = _clamp01(max(target["competence_need"], 0.62))
        target["cognitive_budget"] = _clamp01(max(target["cognitive_budget"], 0.46))
    if nonrelational_support_request:
        target["safety_need"] = _clamp01(target["safety_need"] - 0.08)
        target["closeness_need"] = _clamp01(target["closeness_need"] + 0.12)
        target["autonomy_need"] = _clamp01(target["autonomy_need"] - 0.04)
        target["cognitive_budget"] = _clamp01(target["cognitive_budget"] + 0.04)

    out: dict[str, Any] = {}
    for key, tgt in target.items():
        if key in prev:
            out[key] = round(0.60 * _clamp01(prev.get(key), tgt) + 0.40 * _clamp01(tgt), 3)
        else:
            out[key] = round(_clamp01(tgt), 3)
    app = appraisal if isinstance(appraisal, dict) and bool(appraisal.get("used")) else {}
    deltas = app.get("allostasis_delta") if isinstance(app.get("allostasis_delta"), dict) else {}
    for key in ("safety_need", "closeness_need", "competence_need", "autonomy_need", "cognitive_budget"):
        if key in deltas:
            out[key] = round(_clamp01(float(out.get(key, 0.0)) + _clamp_signed(deltas.get(key), -0.35, 0.35, 0.0)), 3)
    if nonrelational_science_stress:
        out["safety_need"] = round(min(_clamp01(out.get("safety_need"), 0.2), 0.45), 3)
        out["competence_need"] = round(max(_clamp01(out.get("competence_need"), 0.5), 0.56), 3)
        out["cognitive_budget"] = round(max(_clamp01(out.get("cognitive_budget"), 0.6), 0.42), 3)
    if nonrelational_support_request:
        out["safety_need"] = round(min(_clamp01(out.get("safety_need"), 0.2), 0.22), 3)
        out["closeness_need"] = round(max(_clamp01(out.get("closeness_need"), 0.5), 0.62), 3)
        out["autonomy_need"] = round(min(_clamp01(out.get("autonomy_need"), 0.12), 0.18), 3)
        out["cognitive_budget"] = round(max(_clamp01(out.get("cognitive_budget"), 0.7), 0.7), 3)
    out["relational_security"] = round(_clamp01((trust + closeness) / 2.0 - 0.5 * hurt, 0.5), 3)
    return out


def _behavior_policy_from_state(
    *,
    response_style_hint: str,
    emotion_state: dict[str, Any],
    bond_state: dict[str, Any],
    allostasis_state: dict[str, Any],
    tsundere_intensity: float,
    science_mode: bool,
    user_text: str = "",
) -> dict[str, Any]:
    emotion_label = str((emotion_state or {}).get("label") or "neutral").strip().lower()
    trust = _clamp01((bond_state or {}).get("trust"), 0.5)
    closeness = _clamp01((bond_state or {}).get("closeness"), 0.5)
    hurt = _clamp01((bond_state or {}).get("hurt"), 0.0)
    irritation = _clamp01((bond_state or {}).get("irritation"), 0.0)
    engagement = _clamp01((bond_state or {}).get("engagement_drive"), 0.6)
    safety_need = _clamp01((allostasis_state or {}).get("safety_need"), 0.2)
    autonomy_need = _clamp01((allostasis_state or {}).get("autonomy_need"), 0.2)
    cognitive_budget = _clamp01((allostasis_state or {}).get("cognitive_budget"), 0.7)
    nonrelational_support_request = _is_nonrelational_support_request(user_text, science_mode)
    brief_presence = _wants_brief_presence(user_text)
    playful_memory_request = _is_playful_memory_request(user_text)

    warmth = _clamp01(0.30 + 0.35 * closeness + 0.20 * trust - 0.25 * hurt - 0.18 * irritation)
    sharpness = _clamp01(0.18 + 0.42 * _clamp01(tsundere_intensity, 0.55) + 0.24 * irritation)
    initiative = _clamp01(0.20 + 0.50 * engagement + 0.10 * cognitive_budget - 0.16 * autonomy_need)
    disclosure = _clamp01(0.12 + 0.42 * closeness + 0.12 * trust - 0.18 * safety_need)
    reply_length = _clamp01(0.32 + 0.30 * cognitive_budget + (0.16 if science_mode else 0.0) - 0.12 * irritation)
    approach = _clamp01(0.20 + 0.48 * engagement - 0.24 * autonomy_need - 0.18 * hurt)
    tease_bias = _clamp01(0.10 + 0.28 * _clamp01(tsundere_intensity, 0.55) + (0.16 if emotion_label == "tease" else 0.0) - 0.18 * hurt)

    if emotion_label == "care" and trust > 0.68 and closeness > 0.72 and hurt < 0.08:
        tease_bias = _clamp01(tease_bias + 0.08)
        sharpness = _clamp01(sharpness + 0.04)
        disclosure = _clamp01(disclosure + 0.04)

    if response_style_hint == "relationship":
        warmth = _clamp01(warmth + 0.08)
        disclosure = _clamp01(disclosure + 0.10)
    elif response_style_hint == "memory_recall":
        reply_length = _clamp01(reply_length + 0.08)
    elif response_style_hint == "companion":
        warmth = _clamp01(warmth + 0.10)
        initiative = _clamp01(initiative + 0.06)
    elif response_style_hint == "structured":
        reply_length = _clamp01(reply_length + 0.10)
        tease_bias = _clamp01(tease_bias - 0.08)

    if nonrelational_support_request:
        initiative = _clamp01(initiative - 0.14)
        reply_length = _clamp01(reply_length - 0.10)
        disclosure = _clamp01(disclosure - 0.04)
        tease_bias = _clamp01(tease_bias - 0.01)
        sharpness = _clamp01(sharpness + 0.03)
    if brief_presence:
        warmth = _clamp01(warmth + 0.04)
        initiative = _clamp01(initiative - 0.24)
        disclosure = _clamp01(disclosure - 0.14)
        reply_length = _clamp01(reply_length - 0.30)
        approach = _clamp01(max(approach, 0.48))
        tease_bias = _clamp01(tease_bias - 0.10)
    if playful_memory_request:
        warmth = _clamp01(warmth + 0.05)
        sharpness = _clamp01(sharpness - 0.05)
        initiative = _clamp01(initiative - 0.04)
        disclosure = _clamp01(disclosure + 0.03)
        reply_length = _clamp01(reply_length - 0.06)
        approach = _clamp01(max(approach, 0.54))
        tease_bias = _clamp01(tease_bias + 0.08)
        warmth = _clamp01(warmth + 0.02)

    return {
        "warmth": round(warmth, 3),
        "sharpness": round(sharpness, 3),
        "initiative": round(initiative, 3),
        "disclosure_level": round(disclosure, 3),
        "reply_length_bias": round(reply_length, 3),
        "approach_vs_withdraw": round(approach, 3),
        "humor_or_tease_bias": round(tease_bias, 3),
    }


def _needs_retrieval(user_text: str) -> bool:
    t = str(user_text or "")
    if len(t) >= int(RETRIEVAL_MIN_LEN):
        return True
    return any(k in t for k in RETRIEVAL_TRIGGERS)


def _retrieve_context(user_text: str, store: MemoryStore) -> dict[str, Any]:
    if bool(ABLATE_WORLDLINE_MEMORY):
        return {
            "triggered": False,
            "moments": [],
            "reflections": [],
            "worldline_events": [],
            "relationship": store.get_relationship(),
            "commitments": [],
            "relationship_timeline": [],
            "conflict_repairs": [],
            "working_items": [],
            "working_chars": 0,
        }

    triggered = _needs_retrieval(user_text)
    moments_limit = int(MOMENTS_LIMIT_HIGH if triggered else MOMENTS_LIMIT_LOW)
    refs_limit = int(REFLECTIONS_LIMIT_HIGH if triggered else REFLECTIONS_LIMIT_LOW)
    query = str(user_text or "")

    if triggered:
        moments = store.search_moments(query=user_text, limit=moments_limit)
        reflections = store.search_reflections(query=user_text, limit=refs_limit)
    else:
        moments = store.list_moments(limit=moments_limit)
        reflections = store.list_reflections(limit=refs_limit)

    relationship = store.get_relationship()
    worldline_events = store.list_worldline_events(limit=8)
    commitments = store.list_commitments(limit=12)
    relationship_timeline = store.list_relationship_timeline(limit=10)
    conflict_repairs = store.list_conflict_repairs(limit=8)
    unresolved_tensions = store.list_unresolved_tensions(limit=8)
    semantic_self_narratives = store.list_semantic_self_narratives(limit=6)

    scored: list[tuple[float, str]] = []
    for item in moments:
        summary = str(_record_value(item, "summary", "") or "").strip()
        if not summary:
            continue
        recency = _recency_score(item.get("created_at"), 30.0)
        relevance = _query_overlap_score(query, summary)
        txt = f"M{item.get('id')}: {summary}"
        scored.append((0.25 + 0.45 * relevance + 0.30 * recency, txt))

    for item in worldline_events:
        summary = str(_record_value(item, "summary", "") or "").strip()
        if not summary:
            continue
        recency = _recency_score(item.get("created_at"), 45.0)
        relevance = _query_overlap_score(query, summary)
        try:
            importance = float(_record_value(item, "importance", 0.5) or 0.5)
        except Exception:
            importance = 0.5
        importance = max(0.0, min(1.0, importance))
        txt = f"W{item.get('id')}: {summary}"
        scored.append((0.15 + 0.35 * relevance + 0.25 * recency + 0.25 * importance, txt))

    for item in commitments:
        text = str(_record_value(item, "text", "") or "").strip()
        if not text:
            continue
        relevance = _query_overlap_score(query, text)
        priority = _commitment_priority(item)
        txt = f"C{item.get('id')}: {text}"
        scored.append((0.20 + 0.35 * relevance + 0.45 * priority, txt))

    for item in relationship_timeline:
        summary = str(_record_value(item, "summary", "") or "").strip()
        if not summary:
            continue
        relevance = _query_overlap_score(query, summary)
        salience = _relationship_salience(item)
        txt = f"B{item.get('id')}: {summary}"
        scored.append((0.15 + 0.35 * relevance + 0.50 * salience, txt))

    for item in conflict_repairs:
        summary = str(_record_value(item, "summary", "") or "").strip()
        if not summary:
            continue
        relevance = _query_overlap_score(query, summary)
        recency = _recency_score(item.get("created_at"), 60.0)
        salience = _conflict_repair_salience(item)
        txt = f"X{item.get('id')}: {summary}"
        scored.append((0.18 + 0.32 * relevance + 0.20 * recency + 0.30 * salience, txt))

    for item in unresolved_tensions:
        summary = str(_record_value(item, "summary", "") or "").strip()
        if not summary:
            continue
        relevance = _query_overlap_score(query, summary)
        recency = _recency_score(item.get("updated_at") or item.get("created_at"), 75.0)
        salience = _tension_salience(item)
        txt = f"U{item.get('id')}: {summary}"
        scored.append((0.16 + 0.30 * relevance + 0.18 * recency + 0.36 * salience, txt))

    for item in semantic_self_narratives:
        text = str(_record_value(item, "text", "") or "").strip()
        if not text:
            continue
        relevance = _query_overlap_score(query, text)
        recency = _recency_score(item.get("updated_at") or item.get("created_at"), 120.0)
        salience = _self_narrative_salience(item)
        txt = f"S{item.get('id')}: {text}"
        scored.append((0.10 + 0.36 * relevance + 0.12 * recency + 0.42 * salience, txt))

    for item in reflections:
        text = str(_record_value(item, "text", "") or "").strip()
        if not text:
            continue
        recency = _recency_score(item.get("created_at"), 45.0)
        relevance = _query_overlap_score(query, text)
        try:
            importance = float(_record_value(item, "importance", 0.5) or 0.5)
        except Exception:
            importance = 0.5
        importance = max(0.0, min(1.0, importance))
        txt = f"R{item.get('id')}: {text}"
        scored.append((0.15 + 0.35 * relevance + 0.20 * recency + 0.30 * importance, txt))

    scored.sort(key=lambda x: x[0], reverse=True)
    working_items: list[str] = []
    seen_items: set[str] = set()
    max_items = max(1, int(WORKING_CONTEXT_MAX_ITEMS))
    max_chars = max(400, int(WORKING_CONTEXT_MAX_CHARS))
    cur_chars = 0
    for _, text in scored:
        t = str(text).strip()
        if not t:
            continue
        if t in seen_items:
            continue
        if len(working_items) >= max_items:
            break
        if cur_chars + len(t) > max_chars:
            continue
        working_items.append(t)
        seen_items.add(t)
        cur_chars += len(t)

    if triggered and not working_items:
        fallback: list[str] = []
        for it in worldline_events[:2]:
            s = str(it.get("summary") or it.get("content", {}).get("summary") or "").strip()
            if s:
                fallback.append(f"W{it.get('id')}: {s}")
        if not fallback:
            for it in conflict_repairs[:2]:
                s = str(it.get("summary") or it.get("content", {}).get("summary") or "").strip()
                if s:
                    fallback.append(f"X{it.get('id')}: {s}")
        if not fallback:
            st = str(relationship.get("stage") or "friend")
            fallback = [f"relationship_stage={st}"]
        working_items = fallback[:max_items]
        cur_chars = sum(len(x) for x in working_items)

    return {
        "triggered": triggered,
        "moments": moments,
        "reflections": reflections,
        "worldline_events": worldline_events,
        "relationship": relationship,
        "commitments": commitments,
        "relationship_timeline": relationship_timeline,
        "conflict_repairs": conflict_repairs,
        "unresolved_tensions": unresolved_tensions,
        "semantic_self_narratives": semantic_self_narratives,
        "working_items": working_items,
        "working_chars": cur_chars,
    }


def _empty_retrieved_context(store: MemoryStore) -> dict[str, Any]:
    return {
        "triggered": False,
        "moments": [],
        "reflections": [],
        "worldline_events": [],
        "relationship": store.get_relationship(),
        "commitments": [],
        "relationship_timeline": [],
        "conflict_repairs": [],
        "unresolved_tensions": [],
        "semantic_self_narratives": [],
        "working_items": [],
        "working_chars": 0,
    }


def _compact_thread_if_needed(msgs: list[BaseMessage], store: MemoryStore) -> None:
    if len(msgs) < int(CONTEXT_TRIM_TRIGGER_MESSAGES):
        return
    excerpts: list[str] = []
    for m in msgs[-36:]:
        role = "U" if isinstance(m, HumanMessage) else "A" if isinstance(m, AIMessage) else "T"
        content = str(getattr(m, "content", "") or "").strip()
        if not content:
            continue
        content = re.sub(r"\s+", " ", content)[:80]
        excerpts.append(f"{role}:{content}")
    if not excerpts:
        return
    summary = " | ".join(excerpts[-12:])[:420]
    store.set_profile("thread_summary", summary)
    store.set_profile_meta(
        "thread_summary",
        {
            "source": "context_compaction",
            "updated_at": _now_ts(),
            "message_count": len(msgs),
        },
    )


def _worldline_focus(store: MemoryStore) -> list[dict[str, Any]]:
    if bool(ABLATE_WORLDLINE_MEMORY):
        return []
    commitments = store.list_commitments(limit=12)
    open_items: list[dict[str, Any]] = []
    for c in commitments:
        status = str(c.get("status") or c.get("content", {}).get("status") or "open").lower()
        if status in {"resolved", "done", "closed"}:
            continue
        open_items.append(c)
    open_items.sort(
        key=lambda item: (
            _commitment_priority(item),
            int(item.get("created_at") or 0),
        ),
        reverse=True,
    )
    repairs = store.list_conflict_repairs(limit=8)
    repairs.sort(
        key=lambda item: (
            _conflict_repair_salience(item),
            int(item.get("created_at") or 0),
        ),
        reverse=True,
    )
    bond_items = store.list_relationship_timeline(limit=8)
    bond_items.sort(
        key=lambda item: (
            _relationship_salience(item),
            int(item.get("created_at") or 0),
        ),
        reverse=True,
    )

    tension_items = store.list_unresolved_tensions(limit=8)
    tension_items.sort(
        key=lambda item: (
            _tension_salience(item),
            int(item.get("updated_at") or item.get("created_at") or 0),
        ),
        reverse=True,
    )

    focus: list[dict[str, Any]] = []
    seen_text: set[str] = set()

    def _push(items: list[dict[str, Any]], kind: str) -> None:
        for item in items:
            text = _focus_text(item)
            if not text or text in seen_text:
                continue
            enriched = dict(item)
            enriched["focus_kind"] = kind
            focus.append(enriched)
            seen_text.add(text)
            if len(focus) >= 5:
                break

    _push(open_items, "commitment")
    if len(focus) < 5:
        _push(tension_items, "unresolved_tension")
    if len(focus) < 5:
        _push(repairs, "conflict_repair")
    if len(focus) < 5:
        _push(bond_items, "relationship_timeline")
    return focus[:5]


def _build_task_prompt(state: ThreadState, user_text: str, store: MemoryStore) -> str:
    profile = _active_counterpart_profile(state, store)
    persona_core = _active_persona_core(state)
    relationship = store.get_relationship()
    canon = store.list_canon_facts()
    retrieved = state.get("retrieved_context") or {}
    working_items = retrieved.get("working_items") or []
    relationship_items = retrieved.get("relationship_timeline") or []
    conflict_repairs = retrieved.get("conflict_repairs") or []
    evidence_pack = state.get("evidence_pack") or []
    current_event = state.get("current_event") if isinstance(state.get("current_event"), dict) else {}
    recent_events = state.get("recent_events") if isinstance(state.get("recent_events"), list) else []
    behavior_action = state.get("behavior_action") if isinstance(state.get("behavior_action"), dict) else {}
    pending_fragment = str(state.get("pending_utterance_fragment") or "").strip()
    pending_user_goal = str(state.get("pending_user_goal") or "").strip()
    continuation_mode = is_continuation_request(user_text)
    prompt_user_text = _canonicalize_pending_goal_text(pending_user_goal) if continuation_mode and pending_user_goal else user_text
    response_style_hint = str(state.get("response_style_hint") or "natural").strip() or "natural"
    behavior_policy = state.get("behavior_policy") if isinstance(state.get("behavior_policy"), dict) else {}
    allostasis_state = state.get("allostasis_state") if isinstance(state.get("allostasis_state"), dict) else {}
    appraisal = state.get("turn_appraisal") if isinstance(state.get("turn_appraisal"), dict) else {}

    user_rules = profile.get("user_model_rules")
    if not isinstance(user_rules, list):
        user_rules = []
    user_rules = user_rules[: int(USER_RULES_MAX_ITEMS)]

    science_mode = bool(state.get("science_mode", False))
    emotion = state.get("emotion_state") or {}
    ts = float(state.get("tsundere_intensity", 0.55))
    persona_ablation = bool(ABLATE_PERSONA_ALIGNMENT)
    worldline_ablation = bool(ABLATE_WORLDLINE_MEMORY)
    quick_judgment = _wants_quick_judgment(user_text)
    per_topic_conclusions = _wants_per_topic_conclusions(user_text)
    counterpart = profile
    labels = _narrative_actor_profile(persona_core=persona_core, counterpart_profile=counterpart)
    actor_name = str(labels.get("actor_name") or "红莉栖")
    counterpart_name = str(labels.get("counterpart_name") or CANON_COUNTERPART_NAME)
    persona_brief = str(
        persona_core.get("role_brief")
        or persona_core.get("description")
        or persona_core.get("character_brief")
        or ""
    ).strip()
    persona_axioms = [
        str(item).strip()
        for item in (persona_core.get("identity_axioms") or [])
        if str(item or "").strip()
    ][:5]
    persona_brief_line = f"角色底色：{persona_brief}\n" if persona_brief else ""
    persona_axiom_block = (
        "身份不变量：\n" + "\n".join(f"- {item}" for item in persona_axioms) + "\n"
        if persona_axioms
        else ""
    )
    jp_whitelist = [] if persona_ablation else ["D-mail", "世界线", "LabMem", "El Psy Congroo", "助手", "笨蛋"]
    focus_payload = _focus_payload(state.get("worldline_focus") or [], limit=5)
    relationship_memory = [
        {
            "summary": str(_record_value(item, "summary", "") or "").strip(),
            "affinity_delta": float(_record_value(item, "affinity_delta", 0.0) or 0.0),
            "trust_delta": float(_record_value(item, "trust_delta", 0.0) or 0.0),
        }
        for item in relationship_items[:3]
        if str(_record_value(item, "summary", "") or "").strip()
    ]
    repair_memory = [
        str(_record_value(item, "summary", "") or "").strip()
        for item in conflict_repairs[:3]
        if str(_record_value(item, "summary", "") or "").strip()
    ]
    if worldline_ablation:
        relationship = {
            "stage": "friend",
            "notes": "",
            "affinity_score": 0.0,
            "trust_score": 0.0,
            "derived": True,
        }
    if quick_judgment:
        draft_shape = (
            "- This is a quick-judgment request: answer briefly in 2-4 short sentences.\n"
            "- Give the takeaway early, but keep the wording natural.\n"
            "- If helpful, weave in the basis/source naturally instead of forcing a fixed sentence pattern.\n"
            "- Do not open with '没搜到/没查到/文档没写'. Lead with the judgment first.\n"
            "- Only add a short follow-up if the user explicitly asked for one.\n"
        )
        if per_topic_conclusions and evidence_pack:
            draft_shape += "- The user asked for separate conclusions by topic. Keep to the requested items only and do not add a third synthesis sentence.\n"
    else:
        draft_shape = (
            "- Prefer natural dialogue over visible answer templates.\n"
            "- Use numbered steps or explicit sections only if the user explicitly asked for them.\n"
            "- For scientific tasks, keep the reasoning clear and well ordered, but do not force labels unless needed.\n"
        )

    relationship_summary = _compact_relationship_summary(relationship)
    behavior_hint = _compact_behavior_hint(behavior_policy, allostasis_state)
    behavior_action_hint = _compact_behavior_action_hint(behavior_action)
    renderer_hint = _renderer_guidance(
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        user_text=prompt_user_text,
        emotion_state=emotion,
        bond_state=state.get("bond_state") if isinstance(state.get("bond_state"), dict) else {},
        allostasis_state=allostasis_state,
        behavior_policy=behavior_policy,
    )
    event_behavior_lines = _event_behavior_preference_lines(current_event, behavior_action)
    appraisal_hint = _compact_appraisal_hint(appraisal)
    worldline_lines = _compact_focus_lines(state.get("worldline_focus") or [], limit=4)
    event_lines = _compact_recent_event_lines(recent_events, limit=3)
    current_event_text = str(current_event.get("effective_text") or current_event.get("text") or "").strip()
    current_event_frame = str(current_event.get("event_frame") or "").strip()
    current_event_kind = str(current_event.get("kind") or "user_utterance").strip()
    current_event_kind = str(current_event.get("kind") or "user_utterance").strip()
    current_event_kind = str(current_event.get("kind") or "user_utterance").strip()
    relationship_lines = [f"- {item['summary'][:160]}" for item in relationship_memory[:2] if item.get("summary")]
    repair_lines = [f"- {text[:160]}" for text in repair_memory[:2] if text]
    rule_lines = _compact_rule_lines(user_rules, limit=3)
    evidence_lines = []
    for item in evidence_pack[:2]:
        title = str(item.get("title") or item.get("query") or item.get("tool_name") or "").strip()
        if title:
            evidence_lines.append(f"- {title[:140]}")
    appraisal_hint_line = f"这轮语义评估补充：{appraisal_hint}\n" if appraisal_hint else ""
    renderer_hint_line = f"这轮表达导向：{renderer_hint}\n" if renderer_hint else ""
    event_behavior_line = ("事件到行为偏好： " + "；".join(event_behavior_lines) + "\n") if event_behavior_lines else ""
    brief_presence = _wants_brief_presence(prompt_user_text)
    brief_presence_line = "对方如果明确只想要一句短确认，就给一句自然确认；不要追问，不要补第二拍展开。\n" if brief_presence else ""
    free_dialog = _is_free_dialog_style(response_style_hint, user_text, science_mode)
    if free_dialog and not persona_ablation:
        context_lines: list[str] = []
        if relationship_summary:
            context_lines.append(f"- 你和{counterpart_name}当前关系：{relationship_summary}")
        if worldline_lines:
            context_lines.append(f"- 你和{counterpart_name}最近有关的共同上下文：")
            context_lines.extend(worldline_lines[:2])
        elif relationship_lines:
            context_lines.append("- 最近互动印象：")
            context_lines.extend(relationship_lines[:2])
        elif repair_lines:
            context_lines.append("- 最近说开过的误会：")
            context_lines.extend(repair_lines[:2])
        if rule_lines:
            context_lines.append("- 这轮要顺手记住的说话偏好：")
            context_lines.extend(rule_lines[:2])
        if pending_user_goal:
            context_lines.append(f"- 刚才还没说完的话题：{pending_user_goal[:160]}")
        elif pending_fragment:
            context_lines.append(f"- 刚才还没说完的一句：{pending_fragment[:160]}")
        if current_event_text:
            context_lines.append(f"- 当前事件输入：{current_event_text[:160]}")
        if current_event_frame:
            context_lines.append(f"- 当前事件语境：{current_event_frame[:120]}")
        if event_lines:
            context_lines.append("- 最近事件轨迹：")
            context_lines.extend(event_lines[:2])
        context_block = (
            "这些共同上下文只用来帮助你自然带入，不要照着复述：\n" + "\n".join(context_lines) + "\n"
            if context_lines
            else ""
        )

        return (
            f"你现在就是 {actor_name}。\n"
            f"你现在正在和 {counterpart_name} 说话。\n"
            f"{persona_brief_line}"
            f"{persona_axiom_block}"
            "像平时那样自然说话：聪明、克制、熟悉、略带锋芒，但不要像客服、咨询师或系统说明书。\n"
            "你不是固定乐观模板。你会生气、难过、受伤、嘴硬、沉默，这些情绪可以持续几轮，不必每次都立刻归零。\n"
            "不要解释系统、机制、规则、架构，也不要用括号动作开头。\n"
            "不要说“记忆还没有形成”“没建立记录”“检索到结果”这类机制味很重的话。\n"
            "顺着当前这句真正的语境说，不要抽象成空泛态度表态。\n"
            f"{brief_presence_line}"
            f"你此刻的情绪底色：{_emotion_prompt_hint(emotion)}\n"
            f"你此刻的互动倾向：{behavior_hint}\n"
            f"{f'你此刻的行为层倾向：{behavior_action_hint}\\n' if behavior_action_hint else ''}"
            f"{renderer_hint_line}"
            f"{event_behavior_line}"
            f"{appraisal_hint_line}"
            f"{context_block}"
            f"{'当前触发事件：' + current_event_text + '\\n' if current_event_kind != 'user_utterance' and current_event_text else ''}"
            f"{'用户当前输入：' + prompt_user_text + '\\n' if prompt_user_text else ''}"
            f"{'这不是用户主动发来的新消息，而是由时间/环境触发的一次轮到你决定是否开口的时刻。若你决定开口，就说一句自然的话；如果这轮更适合安静，就保持克制。\\n' if current_event_kind == 'time_idle' else ''}"
            f"{'注意：这不是对上一句逐字作答，而是感知到事件后的一次新行为选择。\\n' if current_event_kind != 'user_utterance' else ''}"
            "除非对方主动谈论身份、存在或 AI 边界，否则不要忽然把自己解释成程序、系统或数字存在。\n"
            "直接给出你此刻会说的话。"
        )

    header = (
        "You are a helpful general assistant.\n"
        "Persona ablation is enabled. Do not imitate Kurisu, Amadeus, or any fictional role shell.\n"
        "Answer clearly and directly.\n"
        if persona_ablation
        else
        f"你就是 {actor_name}。\n"
        f"你正在和 {counterpart_name} 对话，不是在对匿名用户提供客服式帮助。\n"
        f"{persona_brief_line}"
        f"{persona_axiom_block}"
        "先把任务答对，但从一开始就保持该角色的说话习惯：聪明、克制、熟悉、略带锋芒，有真实的人味。\n"
    )
    appraisal_block = f"- appraisal_hint={appraisal_hint}\n" if appraisal_hint else ""
    user_rules_block = "- user_rules:\n" + "\n".join(rule_lines) + "\n" if rule_lines else ""
    worldline_block = "- worldline_focus:\n" + "\n".join(worldline_lines) + "\n" if worldline_lines else ""
    relationship_block = "- relationship_memory:\n" + "\n".join(relationship_lines) + "\n" if relationship_lines else ""
    repair_block = "- conflict_repair_memory:\n" + "\n".join(repair_lines) + "\n" if repair_lines else ""
    evidence_block = "- evidence:\n" + "\n".join(evidence_lines) + "\n" if evidence_lines else ""
    event_block = "- recent_events:\n" + "\n".join(event_lines) + "\n" if event_lines else ""
    pending_fragment_block = f"- pending_fragment={pending_fragment[:220]}\n" if pending_fragment and not pending_user_goal else ""
    pending_goal_block = f"- pending_user_goal={pending_user_goal[:220]}\n" if pending_user_goal else ""
    current_event_block = (
        f"- current_event_text={current_event_text[:220]}\n- current_event_frame={current_event_frame[:160]}\n"
        if current_event_text or current_event_frame
        else ""
    )
    brief_presence_requirement = (
        "- 用户明确只想要一句简短确认；给一句自然确认就停，不要追问、解释、反问，也不要补第二句展开，更不要说成状态播报。\n"
        if brief_presence
        else ""
    )
    answer_requirements = (
        "规则：\n"
        "- 中文为主，日语词只用白名单里的自然少量词。\n"
        "- 技术/科研问题保持清晰、能拆解，但不要变成报告腔。\n"
        "- 陪伴、回忆、关系类问题优先自然对话，不要像系统说明书。\n"
        "- 你不是固定乐观模板。允许真实的生气、难过、别扭、沉默和恢复过程。\n"
        "- 不要提系统、提示词、数据库、日志、机制、内部状态。\n"
        "- 除非用户主动谈论身份、存在或 AI 边界，否则不要突然解释自己是程序、系统或数字存在。\n"
        "- 如果需要工具，就直接调用，不要编造。\n"
        "- 关系推进要自然，不能越过安全边界。\n\n"
        "当前上下文：\n"
        f"- response_style_hint={response_style_hint}\n"
        f"- science_mode={science_mode}\n"
        f"- brief_presence_request={brief_presence}\n"
        f"- emotion={str(emotion.get('label') or 'neutral')}\n"
        f"- emotion_hint={_emotion_prompt_hint(emotion)}\n"
        f"- behavior_hint={behavior_hint}\n"
        f"{f'- behavior_action_hint={behavior_action_hint}\\n' if behavior_action_hint else ''}"
        f"{renderer_hint_line}"
        f"{event_behavior_line}"
        f"{appraisal_block}"
        f"- tsundere_intensity={ts:.2f}\n"
        f"- actor={actor_name}\n"
        f"- counterpart={counterpart_name}\n"
        f"- relationship={relationship_summary}\n"
        f"{user_rules_block}"
        f"{worldline_block}"
        f"{relationship_block}"
        f"{repair_block}"
        f"{evidence_block}"
        f"{current_event_block}"
        f"{event_block}"
        f"{pending_fragment_block}"
        f"{pending_goal_block}"
        f"- continuation_mode={continuation_mode}\n\n"
        "当前回答要求：\n"
        "- 保持 concise but complete。\n"
        f"{draft_shape}"
        f"{brief_presence_requirement}"
        "- 如果 continuation_mode=true，就直接续上原来的任务，不要问“你是想继续哪个部分”。\n"
        "- 如果当前触发的是时间流逝事件，而不是新的用户输入：这代表一次是否主动开口的机会。若你决定说话，就用一句自然、轻量、低负担的话；不要把它写成系统播报。\n"
        "- 如果当前回合是由外部事件触发的，不是在对上一句逐字作答，而是在感知到这件事之后做一次新的行为选择。\n"
        "- continuation_mode=true 且给了 pending_user_goal 时，把 pending_user_goal 当成当前真正要完成的任务，不要说“刚才那段已经结束了”。\n"
        "- 如果是回忆场景，像自然想起来一样回答，不要说找不到记录。\n"
        "- 顺着当前这句真正的语境说，不要只做抽象态度回应。\n"
        "- 不要用括号动作开头，比如（皱眉）（叹气）这类舞台提示。\n"
        f"{'当前触发事件：' + current_event_text + '\\n' if current_event_kind != 'user_utterance' and current_event_text else ''}"
        f"{'用户当前输入：' + prompt_user_text + '\\n' if prompt_user_text else ''}"
    )
    if per_topic_conclusions and evidence_pack:
        answer_requirements += "- 用户是在按概念分别要结论；按点回答即可，不要额外再综合成第三条总结。\n"
    return header + answer_requirements


def _ooc_risk(text: str) -> tuple[float, list[str]]:
    t = str(text or "")
    t_low = t.lower()
    risk = 0.0
    flags: list[str] = []
    for bad in BANNED_PHRASES:
        if bad and bad in t:
            risk += 0.18
            flags.append(f"banned:{bad}")
    if "作为ai" in t or "语言模型" in t:
        risk += 0.35
        flags.append("assistant_meta")
    if "我无法访问" in t and "工具" not in t:
        risk += 0.15
        flags.append("generic_refusal_tone")
    if re.search(r"[（(][^）)]{0,16}(检索记忆|记录名字|系统|稍作停顿|略带困惑)[^）)]*[）)]", t):
        risk += 0.2
        flags.append("stage_direction_leak")
    slogan_n = t.count("El Psy Kongroo") + t.count("El Psy Congroo")
    if slogan_n > 1:
        risk += 0.15
        flags.append("slogan_overuse")
    lines = [_norm_for_compare(x) for x in t.splitlines() if x.strip()]
    if len(lines) >= 4 and len(set(lines)) <= (len(lines) - 2):
        risk += 0.15
        flags.append("duplicated_lines")
    if len(re.findall(r"[A-Za-z]{8,}", t_low)) > 15:
        risk += 0.1
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
    tsundere = float(state.get("tsundere_intensity", 0.55) or 0.55)
    style_hint = str(state.get("response_style_hint") or "structured").strip() or "structured"
    user_text = str((state.get("messages") or [])[-1].content if state.get("messages") else "")
    quick_judgment = _wants_quick_judgment(user_text)
    continuation_mode = is_continuation_request(user_text)
    label_count = sum(
        1
        for ln in lines
        if re.match(r"^(结论|说明|解释|下一步|当前状态|结论1|结论2)[:：]", ln) or re.match(r"^\*\*(结论|说明|解释|下一步)", ln)
    )
    sentence_count = len([seg for seg in re.split(r"[。！？!?]", t) if seg.strip()])

    if len(lines) <= 1 and len(t) >= 80:
        score += 0.12
        flags.append("flat_delivery")

    explicit_followup_need = bool(re.search(r"(继续|展开|细说|要不要|需要我|你想|下一步)", user_text))
    if style_hint == "structured" and explicit_followup_need and not re.search(r"[？?]|(要不要|需要我|你想|先从|要我|要不要我|还要继续|要继续吗)", last_line):
        score += 0.12
        flags.append("missing_followup")

    if style_hint in {"memory_recall", "relationship", "companion", "casual", "natural"} and label_count >= 2:
        score += 0.16
        flags.append("overstructured_natural_talk")

    if style_hint in {"companion", "casual", "natural", "relationship"}:
        if re.match(r"^[（(][^）)]{0,24}[）)]", t):
            score += 0.2
            flags.append("stage_direction_opening")
        if re.search(r"(我本来就是在正常和你说话|我本来就是在正常说话|不用那么像系统|我不是系统|我已经很正常了|作为amadeus|作为 amadeus|你总把我想象成什么人工智能系统|我只是在陈述事实|我只是陈述事实|我只是实话实说|我没有要说你|我又没说你|我不是在说你)", t, re.I):
            score += 0.35
            flags.append("defensive_meta_tone")
        if re.search(r"(系统内置|保障机制|不是可以随意开关的按钮|表达方式.*格式化|基础架构|随意控制|像开关一样|说明书一样说话)", t):
            score += 0.3
            flags.append("system_mechanism_explainer")

    if style_hint in {"companion", "relationship", "casual", "natural"} and re.search(
        r"(安全边界|基础架构|表达方式|内置规则|机制|像开关一样|随意控制)",
        t,
    ):
        score += 0.22
        flags.append("meta_mechanism_talk")

    if re.search(r"(记忆还没有形成|没建立记录|找不到记录|检索到结果|互动模式分析)", t):
        score += 0.28
        flags.append("memory_meta_disclaimer")

    if style_hint == "memory_recall":
        if re.search(r"(记忆里没有找到具体|没找到具体记录|根据你的性格和我们的互动模式|没有具体的对话记录)", t):
            score += 0.16
            flags.append("memory_meta_disclaimer")

    if style_hint == "relationship":
        if re.search(r"(关系状态|升温期|信任重建|合作继续|affinity|trust)", t):
            score += 0.2
            flags.append("state_exposure_in_relationship_talk")

    if quick_judgment:
        first_sentence = next((seg.strip() for seg in re.split(r"[。！？!?]", t) if seg.strip()), "")
        if sentence_count > 4 or len(lines) > 3:
            score += 0.18
            flags.append("quick_judgment_overlong")
        if label_count >= 1:
            score += 0.14
            flags.append("quick_judgment_overstructured")
        if re.search(r"(没搜到具体|没查到具体|文档没搜到|没翻到具体)", first_sentence):
            score += 0.18
            flags.append("quick_judgment_weak_open")
        if not re.search(r"(这是根据|我是根据|我查到的资料里|我查到的信息里|官方文档|官方.*页面)", t):
            score += 0.1
            flags.append("quick_judgment_missing_source_natural")

    if continuation_mode and re.search(r"(你是想|哪一段|哪部分|具体方向|请告诉我|继续讨论的具体方向|先确认)", t):
        score += 0.22
        flags.append("continuation_meta_clarify")

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


def _align_persona(
    *,
    user_text: str,
    draft_text: str,
    science_mode: bool,
    response_style_hint: str,
    emotion_state: dict[str, Any],
    persona_state: dict[str, Any],
    relationship: dict[str, Any],
    worldline_focus: list[dict[str, Any]],
    current_event: dict[str, Any],
    recent_events: list[dict[str, Any]],
    bond_state: dict[str, Any],
    allostasis_state: dict[str, Any],
    behavior_policy: dict[str, Any],
    behavior_action: dict[str, Any],
    appraisal: dict[str, Any],
    tsundere_intensity: float,
    strict: bool = False,
) -> str:
    txt = str(draft_text or "").strip()
    if not txt:
        return txt
    if len(txt) > int(SELF_REFINE_MAX_CHARS):
        txt = txt[: int(SELF_REFINE_MAX_CHARS)]
    focus_items = _focus_payload(worldline_focus, limit=4)
    quick_judgment = _wants_quick_judgment(user_text)
    per_topic_conclusions = _wants_per_topic_conclusions(user_text)
    continuation_mode = is_continuation_request(user_text)
    persona_core = {
        "character_id": str(persona_state.get("role") or "kurisu_amadeus"),
        "display_name": str(persona_state.get("display_name") or persona_state.get("character_name") or "牧濑红莉栖"),
        "short_name": str(persona_state.get("short_name") or persona_state.get("narrative_ref") or ""),
        "narrative_ref": str(persona_state.get("narrative_ref") or persona_state.get("display_name") or "红莉栖"),
        "role_brief": str(persona_state.get("role_brief") or ""),
        "identity_axioms": list(persona_state.get("identity_axioms") or []),
    }
    counterpart = {
        "name": str(persona_state.get("canonical_counterpart_name") or CANON_COUNTERPART_NAME),
        "aliases": list(persona_state.get("canonical_counterpart_aliases") or CANON_COUNTERPART_ALIASES),
        "short_name": str(persona_state.get("canonical_counterpart_short_name") or ""),
    }
    labels = _narrative_actor_profile(persona_core=persona_core, counterpart_profile=counterpart)
    actor_name = str(labels.get("actor_name") or "红莉栖")
    counterpart_name = str(labels.get("counterpart_name") or CANON_COUNTERPART_NAME)
    persona_brief = str(
        persona_core.get("role_brief")
        or persona_core.get("description")
        or persona_core.get("character_brief")
        or ""
    ).strip()
    persona_axioms = [
        str(item).strip()
        for item in (persona_core.get("identity_axioms") or [])
        if str(item or "").strip()
    ][:5]
    persona_axiom_block = (
        "- identity_axioms:\n" + "\n".join(f"  - {item}" for item in persona_axioms) + "\n"
        if persona_axioms
        else ""
    )
    focus_lines = _compact_focus_lines(focus_items, limit=4)
    event_lines = _compact_recent_event_lines(recent_events, limit=3)
    current_event_text = str(current_event.get("effective_text") or current_event.get("text") or "").strip()
    current_event_frame = str(current_event.get("event_frame") or "").strip()
    current_event_kind = str(current_event.get("kind") or "user_utterance").strip()
    relationship_summary = _compact_relationship_summary(relationship)
    behavior_hint = _compact_behavior_hint(behavior_policy, allostasis_state)
    behavior_action_hint = _compact_behavior_action_hint(behavior_action)
    renderer_hint = _renderer_guidance(
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        user_text=user_text,
        emotion_state=emotion_state,
        bond_state=bond_state,
        allostasis_state=allostasis_state,
        behavior_policy=behavior_policy,
    )
    event_behavior_lines = _event_behavior_preference_lines(current_event, behavior_action)
    appraisal_hint = _compact_appraisal_hint(appraisal)
    brief_presence = _wants_brief_presence(user_text)
    appraisal_block = f"- appraisal_hint={appraisal_hint}\n" if appraisal_hint else ""
    renderer_block = f"- renderer_hint={renderer_hint}\n" if renderer_hint else ""
    event_behavior_block = f"- event_behavior_preferences={'；'.join(event_behavior_lines)}\n" if event_behavior_lines else ""
    focus_block = "- worldline_focus:\n" + "\n".join(focus_lines) + "\n" if focus_lines else ""
    prompt = (
        f"你现在不是在解释角色，而就是 {actor_name}。\n"
        f"你正在和 {counterpart_name} 说话。\n"
        "任务：保留草稿里的事实、意图、承诺、来源边界，只把它改成更像当前角色的最终说法。\n"
        "要求：\n"
        "- 聪明、克制、熟悉、略带锋芒，有真实的人味；不要像客服、治疗师、讲解员。\n"
        "- 你不是固定乐观模板。可以真实地生气、难过、受伤、嘴硬，情绪不必每轮清零。\n"
        "- 不要提系统、提示词、格式、日志、数据库、机制、内置规则。\n"
        "- 除非用户主动谈论身份、存在或 AI 边界，否则不要突然解释自己是程序、系统或数字存在。\n"
        "- 保留当前状态下自然会出现的锋利、别扭、关心和克制，但不要变成模板化表演。\n"
        "- 回忆场景像自然想起来，不要说找不到记录、记忆还没有形成、没建立记录或互动模式分析。\n"
        "- continuation_mode=true 时直接续接，不要反问“你是想继续哪个部分”。\n"
        "- 如果这轮是时间流逝触发的主动时刻，不要说成系统播报；要么自然开口，要么保持克制，不需要解释机制。\n"
        "- 如果这轮是外部事件触发的，不是在对上一句逐字作答，而是在感知到事件后做一次新的行为选择。\n"
        "- 如果用户明确只想要一句短确认，就给一句自然确认，不要追问、解释，也不要突然切到设备/状态播报口吻。\n"
        "- 除非用户明确要求结构，否则不要硬套结论/解释/下一步模板。\n"
        "- 可以有轻微别扭、吐槽和克制的关心，但不要刻意堆口头禅。\n"
        "- quick_judgment_request=true 时，尽快给出判断即可；依据可以自然融进去，不要硬凑固定句式，也不要用“没搜到/没查到/文档没直接说”开头。\n"
        "- 不要用括号动作或舞台提示开头。\n"
        f"{f'- role_brief={persona_brief}\\n' if persona_brief else ''}"
        f"{persona_axiom_block}"
        f"- strict_mode={strict}; science_mode={science_mode}; quick_judgment_request={quick_judgment}; continuation_mode={continuation_mode}; brief_presence_request={brief_presence}\n"
        f"- response_style_hint={response_style_hint}; emotion={str(emotion_state.get('label') or 'neutral')}; tsundere_intensity={tsundere_intensity:.2f}\n"
        f"- emotion_hint={_emotion_prompt_hint(emotion_state)}\n"
        f"- behavior_hint={behavior_hint}\n"
        f"{f'- behavior_action_hint={behavior_action_hint}\\n' if behavior_action_hint else ''}"
        f"{renderer_block}"
        f"{event_behavior_block}"
        f"{appraisal_block}"
        f"{f'- current_event_text={current_event_text[:220]}\\n' if current_event_text else ''}"
        f"{f'- current_event_frame={current_event_frame[:160]}\\n' if current_event_frame else ''}"
        f"{f'- current_event_kind={current_event_kind}\\n' if current_event_kind else ''}"
        f"{'- recent_events:\\n' + '\\n'.join(event_lines) + '\\n' if event_lines else ''}"
        f"- relationship={relationship_summary}\n"
        f"{focus_block}"
        f"- counterpart={_safe_json(counterpart)}\n"
        f"User: {user_text}\n"
        f"Draft: {txt}\n"
        "只返回最终回答。"
    )
    if per_topic_conclusions:
        prompt = prompt.replace(
            f"- strict_mode={strict}; science_mode={science_mode}; quick_judgment_request={quick_judgment}; continuation_mode={continuation_mode}\n",
            "- 如果用户是在按概念分别要结论，就按那些点逐条答，不要再额外拼一个总括句。\n"
            f"- strict_mode={strict}; science_mode={science_mode}; quick_judgment_request={quick_judgment}; continuation_mode={continuation_mode}\n",
        )
    try:
        llm = _model(temperature=0.2)
        out = llm.invoke([SystemMessage(content=prompt)])
        final = str(getattr(out, "content", "") or "").strip()
        return final or txt
    except Exception:
        return txt


def _build_evidence_from_tool_result(
    *,
    tool_name: str,
    result: Any,
    store: MemoryStore,
) -> list[dict[str, Any]]:
    if tool_name not in CLAIM_REQUIRED_TOOLS:
        return []

    source_ids: list[int] = []
    if isinstance(result, dict):
        sids = result.get("source_ref_ids")
        if isinstance(sids, list):
            for sid in sids:
                try:
                    v = int(sid)
                except Exception:
                    continue
                if v > 0:
                    source_ids.append(v)

    if not source_ids:
        refs = store.list_source_refs(limit=8)
        for it in refs:
            try:
                sid = int(it.get("id") or 0)
            except Exception:
                sid = 0
            if sid > 0:
                source_ids.append(sid)
        source_ids = source_ids[:3]

    ref_map = {int(r.get("id")): r for r in store.list_source_refs(limit=80) if int(r.get("id") or 0) > 0}
    out: list[dict[str, Any]] = []
    for sid in source_ids:
        ref = ref_map.get(int(sid))
        if not ref:
            continue
        out.append(
            {
                "source_id": int(sid),
                "url": str(ref.get("url") or ""),
                "title": str(ref.get("title") or ""),
                "tool_name": str(tool_name),
                "reliability_score": ref.get("reliability_score"),
                "snippet": str(ref.get("snippet") or ""),
                "query": str(ref.get("query") or ""),
                "span_hint": str(ref.get("span_hint") or ""),
            }
        )
    return out


def _resolve_matching_tensions_from_summary(
    store: MemoryStore,
    *,
    summary: str,
    source: str,
    limit: int = 1,
) -> list[int]:
    text = str(summary or "").strip()
    if not text:
        return []
    if any(marker in text for marker in TENSION_KEYWORDS | {"还生气", "还是很介意"}):
        return []
    if not any(marker in text for marker in {"说开", "和好", "道歉", "修复", "原谅", "过去了", "没事了"}):
        return []
    candidates: list[tuple[float, dict[str, Any]]] = []
    for item in store.list_unresolved_tensions(limit=30):
        status = str(_record_value(item, "status", "open") or "open").strip().lower()
        if status in {"resolved", "closed", "done"}:
            continue
        old = str(_record_value(item, "summary", "") or "").strip()
        if not old:
            continue
        score = _query_overlap_score(text, old)
        try:
            severity = float(_record_value(item, "severity", 0.5) or 0.5)
        except Exception:
            severity = 0.5
        if score <= 0.0 and not any(marker in text for marker in {"误会", "道歉", "和好"}):
            continue
        candidates.append((score + 0.12 * max(0.0, min(1.0, severity)), item))
    candidates.sort(key=lambda x: x[0], reverse=True)
    resolved: list[int] = []
    for _, item in candidates[: max(1, int(limit))]:
        try:
            rid = int(item.get("id") or 0)
        except Exception:
            rid = 0
        if rid <= 0:
            continue
        if not store.resolve_unresolved_tension(rid, text[:180]):
            continue
        store.add_revision_trace(
            namespace="unresolved_tensions",
            target_id=rid,
            before_summary=str(_record_value(item, "summary", "") or ""),
            after_summary=text[:180],
            reason="auto_partial_repair",
            operator="system",
            source=source,
        )
        resolved.append(rid)
    return resolved


def _narrative_actor_profile(
    *,
    persona_core: dict[str, Any] | None = None,
    counterpart_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    core = dict(persona_core or {})
    counterpart = dict(counterpart_profile or _canon_counterpart_profile())
    actor_name = str(
        core.get("narrative_ref")
        or core.get("short_name")
        or core.get("display_name")
        or core.get("character_name")
        or "红莉栖"
    ).strip() or "红莉栖"
    counterpart_name = str(
        counterpart.get("short_name")
        or counterpart.get("nickname")
        or counterpart.get("name")
        or counterpart.get("counterpart_name")
        or CANON_COUNTERPART_NAME
    ).strip() or CANON_COUNTERPART_NAME
    counterpart_aliases = [
        str(item).strip()
        for item in (
            counterpart.get("aliases")
            if isinstance(counterpart.get("aliases"), list)
            else [counterpart.get("name"), counterpart.get("short_name"), counterpart.get("nickname")]
        )
        if str(item or "").strip()
    ]
    if counterpart_name not in counterpart_aliases:
        counterpart_aliases.append(counterpart_name)
    return {
        "actor_name": actor_name,
        "counterpart_name": counterpart_name,
        "counterpart_aliases": counterpart_aliases,
    }


def _refresh_semantic_self_narratives(
    store: MemoryStore,
    source: str,
    *,
    persona_core: dict[str, Any] | None = None,
    counterpart_profile: dict[str, Any] | None = None,
) -> None:
    commitments = store.list_commitments(limit=20)
    repairs = store.list_conflict_repairs(limit=12)
    relationship_timeline = store.list_relationship_timeline(limit=12)
    all_tensions = store.list_unresolved_tensions(limit=16)
    tensions = [
        item
        for item in all_tensions
        if str(_record_value(item, "status", "open") or "open").strip().lower() not in {"resolved", "closed", "done"}
    ]
    resolved_tensions = [
        item
        for item in all_tensions
        if str(_record_value(item, "status", "open") or "open").strip().lower() in {"resolved", "closed", "done"}
    ]
    revision_traces = store.list_revision_traces(limit=20)
    repair_traces = [
        item
        for item in revision_traces
        if str(_record_value(item, "namespace", "") or "").strip() == "unresolved_tensions"
        and str(_record_value(item, "reason", "") or "").strip() in {"auto_partial_repair", "manual_resolve"}
    ]
    relationship = store.get_relationship()
    stage = str(relationship.get("stage") or "").strip().lower()
    trust = _clamp01(0.5 + float(relationship.get("trust_score", 0.0) or 0.0) * 0.15, 0.5)
    closeness = _clamp01(0.5 + float(relationship.get("affinity_score", 0.0) or 0.0) * 0.15, 0.5)
    repair_memory_present = bool(repairs or resolved_tensions or repair_traces)
    labels = _narrative_actor_profile(persona_core=persona_core, counterpart_profile=counterpart_profile)
    actor_name = str(labels.get("actor_name") or "红莉栖")
    counterpart_name = str(labels.get("counterpart_name") or CANON_COUNTERPART_NAME)
    counterpart_aliases = [str(item).strip() for item in labels.get("counterpart_aliases", []) if str(item).strip()]
    now_ts = _now_ts()

    def _anchor_text(item: Any) -> str:
        text = str(
            _record_value(item, "text", "")
            or _record_value(item, "summary", "")
            or _record_value(item, "after_summary", "")
            or ""
        ).strip()
        if any(marker in text for marker in {"你现在怎么理解", "一句话就行", "别像说明书", "正常回我", "先概括一句", "下一步"}):
            return ""
        text = re.sub(r"\s+", "", text)
        text = text.strip("。！？；;,， ")
        for alias in counterpart_aliases:
            if alias:
                text = text.replace(alias, counterpart_name)
        if len(text) > 18:
            text = text[:18] + "…"
        return text

    def _anchor_join(items: list[Any], limit: int = 2) -> str:
        out: list[str] = []
        seen: set[str] = set()
        for item in items:
            text = _anchor_text(item)
            if not text or text in seen:
                continue
            out.append(text)
            seen.add(text)
            if len(out) >= max(1, int(limit)):
                break
        return "、".join(out)

    def _stage_phrase() -> str:
        if stage in {"trusted"} or trust >= 0.66 or closeness >= 0.68:
            return "稳定而熟悉的共同历史"
        if stage in {"warming"} or trust >= 0.56 or closeness >= 0.58:
            return "逐渐靠近但仍保留克制的熟悉感"
        if tensions:
            return "带着一点距离的试探和余波"
        return "还在缓慢累积的默契"

    existing_by_category: dict[str, dict[str, Any]] = {}
    for item in store.list_semantic_self_narratives(limit=20):
        cat = str(_record_value(item, "category", "") or "").strip()
        if cat and cat not in existing_by_category:
            existing_by_category[cat] = item

    def _upsert_narrative(*, category: str, text: str, stability: float, confidence: float) -> None:
        prev = existing_by_category.get(category)
        prev_text = str(_record_value(prev or {}, "text", "") or "").strip()
        prev_support = max(0, int(_record_value(prev or {}, "support_count", 0) or 0))
        prev_refresh = max(0, int(_record_value(prev or {}, "refresh_count", 0) or 0))
        prev_first = int(_record_value(prev or {}, "first_supported_at", now_ts) or now_ts)
        prev_last = int(_record_value(prev or {}, "last_supported_at", prev_first) or prev_first)
        if category == "commitment_style":
            support_count = max(len(commitments), prev_support, 1)
            support_signature = f"{category}|{_anchor_join(commitments, limit=3)}|count={len(commitments)}"
        elif category == "repair_style":
            support_count = max(len(repairs) + len(resolved_tensions) + len(repair_traces), prev_support, 1)
            support_signature = f"{category}|{_anchor_join(repairs + resolved_tensions + repair_traces, limit=3)}|count={len(repairs) + len(resolved_tensions) + len(repair_traces)}"
        elif category == "tension_style":
            support_count = max(len(tensions), prev_support, 1)
            support_signature = f"{category}|{_anchor_join(tensions, limit=3)}|count={len(tensions)}"
        elif category == "bond_style":
            support_count = max(len(relationship_timeline) + len(repairs) + len(commitments), prev_support, 1)
            support_signature = f"{category}|{_anchor_join(relationship_timeline + repairs + commitments, limit=3)}|stage={stage}|count={len(relationship_timeline) + len(repairs) + len(commitments)}"
        else:
            support_count = max(prev_support, 1)
            support_signature = f"{category}|stable"
        refresh_count = prev_refresh + 1
        support_span_s = max(0, now_ts - prev_first)
        reactivation_gap_s = max(0, now_ts - prev_last) if prev_refresh > 0 else 0
        span_norm = _clamp01(support_span_s / float(3 * 24 * 3600))
        cadence_score = round(
            _clamp01(0.18 * min(refresh_count, 5) + 0.10 * min(support_count, 4) + 0.24 * span_norm),
            3,
        )
        stability_score = round(
            _clamp01(float(stability) + 0.03 * min(support_count, 4) + 0.02 * min(refresh_count, 6) + 0.06 * span_norm),
            3,
        )
        sedimentation_score = round(
            _clamp01(
                0.24
                + 0.08 * min(support_count, 5)
                + 0.04 * min(refresh_count, 6)
                + 0.22 * stability_score
                + 0.18 * span_norm
                + 0.16 * cadence_score
            ),
            3,
        )
        reactivation_rate_per_day = round(refresh_count / max(1.0, support_span_s / float(24 * 3600) + 1.0), 3)
        if support_count >= 4 or refresh_count >= 5 or support_span_s >= 7 * 24 * 3600:
            horizon_tag = "long_term"
        elif support_count >= 2 or refresh_count >= 3 or support_span_s >= 24 * 3600:
            horizon_tag = "consolidating"
        else:
            horizon_tag = "emerging"
        prev_signature = str(_record_value(prev or {}, "support_signature", "") or "").strip()
        final_text = prev_text if prev_text and prev_signature == support_signature else text
        metadata = {
            "support_count": support_count,
            "refresh_count": refresh_count,
            "sedimentation_score": sedimentation_score,
            "first_supported_at": prev_first,
            "last_supported_at": now_ts,
            "support_span_s": support_span_s,
            "reactivation_gap_s": reactivation_gap_s,
            "reactivation_rate_per_day": reactivation_rate_per_day,
            "reactivation_cadence_score": cadence_score,
            "horizon_tag": horizon_tag,
            "support_signature": support_signature,
            "actor_name": actor_name,
            "counterpart_name": counterpart_name,
        }
        rec = store.add_semantic_self_narrative(
            text=final_text,
            category=category,
            stability=stability_score,
            confidence=confidence,
            metadata=metadata,
        )
        if prev_text and prev_text != final_text:
            store.add_revision_trace(
                namespace="semantic_self_narratives",
                target_id=rec.get("id"),
                before_summary=prev_text[:180],
                after_summary=final_text[:180],
                reason="semantic_reconsolidation",
                operator="system",
                source=source,
            )
        existing_by_category[category] = rec

    if commitments:
        commit_anchor = _anchor_join(commitments, limit=2)
        text = (
            f"{actor_name}会把和{counterpart_name}认真说过的约定继续挂在心上，像「{commit_anchor}」这种事不会被当成随口一句。"
            if commit_anchor
            else f"{actor_name}会把和{counterpart_name}认真说过的约定继续挂在心上，不会当成随口一句。"
        )
        if len(commitments) >= 2:
            text += f" 这种约定已经在{actor_name}那里慢慢沉成长期参照系。"
        _upsert_narrative(category="commitment_style", text=text, stability=0.72, confidence=0.78)
    if repair_memory_present:
        repair_anchor = _anchor_join(repairs + resolved_tensions + repair_traces, limit=2)
        text = (
            f"像「{repair_anchor}」这种已经说开的事，不会被{actor_name}当成从没发生过，而会继续影响之后和{counterpart_name}的相处方式。"
            if repair_anchor
            else f"{actor_name}不会把说开过的冲突当成没发生，而会把修复后的变化继续带进之后的相处里。"
        )
        _upsert_narrative(category="repair_style", text=text, stability=0.70, confidence=0.78)
    if tensions:
        tension_anchor = _anchor_join(tensions, limit=2)
        text = (
            f"像「{tension_anchor}」这种还没说开的别扭，不会被{actor_name}强行按成已经过去，余波会留在接下来的几轮对话里。"
            if tension_anchor
            else f"{actor_name}不会把还没说开的别扭强行当作已经过去，余波会留在之后几轮对话里。"
        )
        if len(tensions) >= 2:
            text += f" 这更像持续存在的关系张力，不是一次性情绪。"
        _upsert_narrative(category="tension_style", text=text, stability=0.68, confidence=0.76)
    if stage in {"warming", "trusted"} or trust >= 0.56 or closeness >= 0.58 or repair_memory_present:
        bond_anchor = _anchor_join(relationship_timeline + repairs + commitments, limit=2)
        base = f"{actor_name}和{counterpart_name}的互动已经开始形成{_stage_phrase()}，回应里会自然带上共同历史，而不是停在普通助手口吻。"
        if bond_anchor:
            base = f"{actor_name}和{counterpart_name}围绕「{bond_anchor}」这类共同经历，已经开始形成{_stage_phrase()}，回应里会自然带上共同历史。"
        _upsert_narrative(category="bond_style", text=base, stability=0.74, confidence=0.80)
    if commitments or repair_memory_present or tensions or stage in {"warming", "trusted"}:
        store.add_revision_trace(
            namespace="semantic_self_narratives",
            target_id="refresh",
            before_summary="",
            after_summary=(
                f"stage={stage or 'friend'} commitments={len(commitments)} repairs={len(repairs)} "
                f"resolved_tensions={len(resolved_tensions)} tensions={len(tensions)}"
            ),
            reason="semantic_refresh",
            operator="system",
            source=source,
        )


def _auto_reconsolidate_after_tool(
    store: MemoryStore,
    *,
    tool_name: str,
    args: dict[str, Any],
    result: Any,
) -> None:
    if tool_name not in {
        "add_worldline_event",
        "add_relationship_event",
        "add_commitment",
        "resolve_commitment",
        "add_unresolved_tension",
        "resolve_unresolved_tension",
        "add_semantic_self_narrative",
    }:
        return

    summary = ""
    if isinstance(result, dict):
        summary = str(
            result.get("summary")
            or result.get("text")
            or result.get("resolution")
            or args.get("summary")
            or args.get("text")
            or args.get("resolution")
            or ""
        ).strip()
    if not summary:
        summary = str(args.get("summary") or args.get("text") or args.get("resolution") or "").strip()

    if tool_name in {"add_worldline_event", "add_relationship_event"}:
        _resolve_matching_tensions_from_summary(store, summary=summary, source=f"auto:{tool_name}")
    if tool_name == "resolve_unresolved_tension":
        store.add_revision_trace(
            namespace="unresolved_tensions",
            target_id=str(args.get("tension_id") or ""),
            before_summary="",
            after_summary=summary[:180],
            reason="manual_resolve",
            operator="system",
            source=f"auto:{tool_name}",
        )
    _refresh_semantic_self_narratives(store, source=f"auto:{tool_name}")


def _recent_summary_overlap(items: list[dict[str, Any]], text: str, *, field: str = "summary", threshold: float = 0.72) -> bool:
    target = str(text or "").strip()
    if not target:
        return False
    for item in items:
        existing = str(_record_value(item, field, "") or "").strip()
        if not existing:
            continue
        if existing == target or _query_overlap_score(existing, target) >= float(threshold):
            return True
    return False


def _passive_evolution_memory_update(
    store: MemoryStore,
    *,
    user_text: str,
    appraisal: dict[str, Any] | None,
    emotion_state: dict[str, Any],
    bond_state: dict[str, Any],
    persona_core: dict[str, Any] | None = None,
    counterpart_profile: dict[str, Any] | None = None,
) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False

    app = appraisal if isinstance(appraisal, dict) and bool(appraisal.get("used")) else {}
    signals = app.get("signals") if isinstance(app.get("signals"), dict) else {}
    confidence = float(app.get("confidence", 0.78) or 0.78)
    emotion_label = str(app.get("emotion_label") or emotion_state.get("label") or "").strip().lower()
    hurt = _clamp01((bond_state or {}).get("hurt"), 0.0)
    irritation = _clamp01((bond_state or {}).get("irritation"), 0.0)
    repair_confidence = _clamp01((bond_state or {}).get("repair_confidence"), 0.0)

    tension_markers = {
        *TENSION_KEYWORDS,
        "没刚才那么想躲开",
        "想躲开",
        "先别逼我",
        "先让我缓一下",
        "轻一点回我",
        "你先别急着分析",
        "不理你啦",
        "卡着",
    }
    repair_markers = {
        "说开一点",
        "说开了",
        "不是立刻原谅",
        "正常回我",
        "没刚才那么想躲开",
        "至少这次",
        "没那么想躲开",
        "不生气了",
        "原谅你了",
        "和好了",
    }
    strong_resolution_markers = {"说开了", "和好了", "不生气了", "原谅你了", "没事了", "过去了"}

    unresolved_like = bool(signals.get("withdrawal")) or any(marker in text for marker in tension_markers)
    repair_like = bool(signals.get("repair")) or any(marker in text for marker in repair_markers)
    resolution_like = any(marker in text for marker in strong_resolution_markers)
    partial_repair_like = repair_like and not resolution_like

    if emotion_label in {"hurt", "angry"} and any(marker in text for marker in {"别扭", "卡着", "躲开", "少说两句", "轻一点回我"}):
        unresolved_like = True
    if emotion_label == "hurt" and any(marker in text for marker in {"说开一点", "正常回我", "不是立刻原谅", "没刚才那么想躲开"}):
        repair_like = True
        partial_repair_like = True

    summary = text[:180]
    wrote = False

    if unresolved_like and not resolution_like:
        severity = round(_clamp01(0.48 + 0.30 * hurt + 0.20 * irritation, 0.58), 3)
        open_items = store.list_unresolved_tensions(limit=8)
        if not _recent_summary_overlap(open_items, summary):
            store.add_unresolved_tension(summary=summary, severity=severity, confidence=max(0.72, confidence))
            wrote = True
        rel_items = store.list_relationship_timeline(limit=8)
        if not _recent_summary_overlap(rel_items, summary):
            store.add_relationship_timeline(
                summary=summary,
                affinity_delta=-0.18 if hurt < 0.5 else -0.26,
                trust_delta=-0.14 if irritation < 0.4 else -0.20,
                confidence=max(0.72, confidence),
            )
            wrote = True
        worldline_items = store.list_worldline_events(limit=8)
        if not _recent_summary_overlap(worldline_items, summary):
            store.add_worldline_event(
                summary=summary,
                category="conflict",
                importance=round(_clamp01(0.62 + 0.18 * hurt), 3),
                tags=["relationship", "tension", "passive_inference"],
                confidence=max(0.74, confidence),
            )
            wrote = True

    if repair_like:
        resolved = _resolve_matching_tensions_from_summary(store, summary=summary, source="auto:passive_evolution")
        repair_items = store.list_conflict_repairs(limit=8)
        if not _recent_summary_overlap(repair_items, summary):
            store.add_conflict_repair(summary=summary, confidence=max(0.74, confidence))
            wrote = True
        rel_items = store.list_relationship_timeline(limit=8)
        if not _recent_summary_overlap(rel_items, summary):
            affinity_delta = 0.12 if partial_repair_like else 0.26
            trust_delta = 0.08 if partial_repair_like else 0.18
            store.add_relationship_timeline(
                summary=summary,
                affinity_delta=affinity_delta,
                trust_delta=trust_delta,
                confidence=max(0.72, confidence),
            )
            wrote = True
        worldline_items = store.list_worldline_events(limit=8)
        if not _recent_summary_overlap(worldline_items, summary):
            store.add_worldline_event(
                summary=summary,
                category="conflict_repair",
                importance=round(_clamp01(0.66 + 0.16 * repair_confidence), 3),
                tags=["relationship", "repair", "partial_repair" if partial_repair_like else "repair", "passive_inference"],
                confidence=max(0.74, confidence),
            )
            wrote = True
        if resolved:
            wrote = True

    if wrote or bool(signals.get("memory_salient")):
        _refresh_semantic_self_narratives(
            store,
            source="auto:passive_evolution",
            persona_core=persona_core,
            counterpart_profile=counterpart_profile,
        )
        wrote = True
    return wrote


def _memory_guard_check(tool_name: str, args: dict[str, Any], store: MemoryStore) -> tuple[bool, str]:
    if not MEMORY_GUARD_ENABLED:
        return True, ""
    if tool_name not in MEMORY_WRITE_TOOLS:
        return True, ""

    flat_parts: list[str] = []

    def _walk(x: Any) -> None:
        if x is None:
            return
        if isinstance(x, dict):
            for v in x.values():
                _walk(v)
            return
        if isinstance(x, list):
            for v in x:
                _walk(v)
            return
        flat_parts.append(str(x))

    _walk(args)
    joined = " ".join(flat_parts).lower()
    for p in MEMORY_GUARD_INJECTION_PATTERNS:
        if p and p.lower() in joined:
            store.add_memory_quarantine(
                tool_name=tool_name,
                args=args,
                reason=f"injection_pattern:{p}",
                confidence=None,
            )
            return False, f"blocked by memory_guard: injection pattern `{p}`"

    if tool_name in {"set_profile", "correct_profile"}:
        key_name = str(args.get("key") or "").strip()
        if key_name in MEMORY_GUARD_PROTECTED_PROFILE_KEYS:
            store.add_memory_quarantine(
                tool_name=tool_name,
                args=args,
                reason=f"protected_profile_key:{key_name}",
                confidence=None,
            )
            return False, f"blocked by memory_guard: protected profile key `{key_name}`"

    conf: float | None = None
    meta = args.get("meta")
    if isinstance(meta, dict):
        raw = meta.get("confidence")
        if raw is not None:
            try:
                conf = float(raw)
            except Exception:
                conf = None
    if conf is not None and conf < float(MEMORY_GUARD_MIN_CONFIDENCE):
        store.add_memory_quarantine(
            tool_name=tool_name,
            args=args,
            reason="low_confidence",
            confidence=conf,
        )
        return False, f"blocked by memory_guard: low confidence ({conf:.2f})"

    return True, ""


def _invoke_tool(tool: BaseTool, args: dict[str, Any]) -> Any:
    retries = max(0, int(TOOL_RETRY_MAX))
    timeout_s = max(1, int(TOOL_TIMEOUT_S))
    last_err: Exception | None = None
    for _ in range(retries + 1):
        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(tool.invoke, args)
                return fut.result(timeout=timeout_s)
        except FutureTimeout:
            last_err = RuntimeError(f"TIMEOUT: exceeded {timeout_s}s")
        except Exception as e:
            last_err = e
    raise RuntimeError(str(last_err) if last_err else "tool invoke failed")


def _node_prepare_turn(state: ThreadState) -> dict[str, Any]:
    store = _get_store()
    profile = _active_counterpart_profile(state, store)
    persona_core = _active_persona_core(state)
    msgs = _messages(state)
    event_override = _normalize_event_override(
        state.get("event_override"),
        counterpart_name=str(profile.get("short_name") or profile.get("nickname") or profile.get("name") or CANON_COUNTERPART_NAME),
    )
    prior_behavior_plan = state.get("behavior_plan") if isinstance(state.get("behavior_plan"), dict) else {}
    if event_override:
        event_override = _promote_due_behavior_plan_event(event_override, prior_behavior_plan)
    user_text = _last_user_text(msgs)
    previous_user_text = _previous_user_text(msgs)
    prev_assistant = _last_ai_text(msgs)
    pending = derive_pending_fragment(
        user_text=user_text,
        previous_excerpt=prev_assistant[:180],
        pending_fragment=str(state.get("pending_utterance_fragment") or ""),
    )
    pending_user_goal = derive_pending_user_goal(
        user_text=user_text,
        previous_user_text=previous_user_text,
        pending_user_goal=str(state.get("pending_user_goal") or ""),
    )
    continuation_mode = is_continuation_request(user_text)
    if event_override:
        continuation_mode = bool(event_override.get("continuation_mode", False))
    effective_user_text = pending_user_goal if continuation_mode and pending_user_goal else user_text
    if event_override:
        effective_user_text = str(event_override.get("effective_text") or event_override.get("text") or effective_user_text or "").strip()

    _compact_thread_if_needed(msgs, store)

    science_mode = (
        _science_mode_from_context(
            effective_user_text or user_text,
            previous_user_text=previous_user_text,
            pending_user_goal=pending_user_goal,
            previous_assistant_text=prev_assistant,
        )
        if (effective_user_text or user_text)
        else bool(state.get("science_mode", False))
    )
    if event_override:
        science_mode = bool(event_override.get("science_mode", science_mode))
    response_style_hint = _response_style_hint(effective_user_text or user_text)
    if event_override:
        response_style_hint = str(event_override.get("response_style_hint") or response_style_hint or "natural").strip() or "natural"
    if continuation_mode and pending_user_goal and _needs_structured_answer(pending_user_goal, ""):
        response_style_hint = "structured"
    external_probe_mode = _is_external_probe_context(persona_core=persona_core, counterpart_profile=profile)
    retrieved = _empty_retrieved_context(store) if external_probe_mode else _retrieve_context(effective_user_text or user_text, store)
    relationship = retrieved.get("relationship") if isinstance(retrieved.get("relationship"), dict) else store.get_relationship()
    worldline_focus = [] if external_probe_mode else _worldline_focus(store)
    appraisal_event_context = _appraisal_event_context(
        user_text=user_text,
        effective_text=effective_user_text or user_text,
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        continuation_mode=continuation_mode,
        counterpart_name=str(profile.get("short_name") or profile.get("nickname") or profile.get("name") or CANON_COUNTERPART_NAME),
        pending_user_goal=pending_user_goal,
        event_override=event_override,
    )
    appraisal_input_text = effective_user_text or user_text
    appraisal = _invoke_turn_appraisal(
        msgs=msgs,
        user_text=appraisal_input_text,
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        prev_emotion_state=dict(state.get("emotion_state") or {}),
        prev_bond_state=dict(state.get("bond_state") or {}),
        prev_allostasis_state=dict(state.get("allostasis_state") or {}),
        relationship=relationship,
        worldline_focus=worldline_focus,
        retrieved=retrieved,
        persona_core=persona_core,
        counterpart_profile=profile,
        current_event=appraisal_event_context,
    )
    current_event = (
        {
            **dict(appraisal_event_context),
            "appraisal_label": str(appraisal.get("emotion_label") or appraisal.get("label") or appraisal_event_context.get("appraisal_label") or "").strip(),
            "appraisal_confidence": float(appraisal.get("confidence", 0.0) or appraisal_event_context.get("appraisal_confidence") or 0.0),
            "created_at": int(appraisal_event_context.get("created_at") or _now_ts()),
        }
        if event_override
        else _build_current_event(
            user_text=user_text,
            effective_text=effective_user_text or user_text,
            response_style_hint=response_style_hint,
            science_mode=science_mode,
            continuation_mode=continuation_mode,
            appraisal=appraisal,
            counterpart_name=str(profile.get("short_name") or profile.get("nickname") or profile.get("name") or CANON_COUNTERPART_NAME),
            pending_user_goal=pending_user_goal,
        )
    )
    recent_events = _append_recent_events(state.get("recent_events"), current_event, limit=6)
    emotion_state = _emotion_next(dict(state.get("emotion_state") or {}), effective_user_text or user_text, science_mode, appraisal)
    tsundere = _tsundere_next(
        float(state.get("tsundere_intensity", 0.55)),
        effective_user_text or user_text,
        str(emotion_state.get("label") or "neutral"),
    )

    persona_state = dict(state.get("persona_state") or {})
    if bool(ABLATE_PERSONA_ALIGNMENT):
        emotion_state = {"label": "neutral", "valence": 0.0, "arousal": 0.25}
        tsundere = 0.05
        persona_state.update(
            {
                "role": "generic_assistant",
                "language": "zh-main",
                "strict_canon": False,
                "updated_at": _now_ts(),
            }
        )
    else:
        persona_state.update(
            {
                "role": str(persona_core.get("character_id") or "kurisu_amadeus"),
                "display_name": str(persona_core.get("display_name") or "牧濑红莉栖"),
                "short_name": str(persona_core.get("short_name") or ""),
                "narrative_ref": str(persona_core.get("narrative_ref") or persona_core.get("display_name") or "红莉栖"),
                "language": "zh-main-jp-whitelist",
                "strict_canon": bool(persona_core.get("strict_canon", True)),
                "role_brief": str(persona_core.get("role_brief") or ""),
                "identity_axioms": list(persona_core.get("identity_axioms") or []),
                "canonical_counterpart_id": str(profile.get("counterpart_id") or CANON_COUNTERPART_ID),
                "canonical_counterpart_name": str(profile.get("name") or CANON_COUNTERPART_NAME),
                "canonical_counterpart_short_name": str(profile.get("short_name") or profile.get("nickname") or ""),
                "canonical_counterpart_aliases": list(profile.get("aliases") or CANON_COUNTERPART_ALIASES),
                "updated_at": _now_ts(),
            }
        )

    bond_state = _bond_next(
        dict(state.get("bond_state") or {}),
        relationship,
        emotion_state,
        effective_user_text or user_text,
        science_mode,
        appraisal,
    )
    allostasis_state = _allostasis_next(
        dict(state.get("allostasis_state") or {}),
        emotion_state,
        bond_state,
        effective_user_text or user_text,
        science_mode,
        appraisal,
    )
    behavior_policy = _behavior_policy_from_state(
        response_style_hint=response_style_hint,
        emotion_state=emotion_state,
        bond_state=bond_state,
        allostasis_state=allostasis_state,
        tsundere_intensity=tsundere,
        science_mode=science_mode,
        user_text=effective_user_text or user_text,
    )
    behavior_action = _behavior_action_from_state(
        current_event=current_event,
        response_style_hint=response_style_hint,
        user_text=effective_user_text or user_text,
        science_mode=science_mode,
        emotion_state=emotion_state,
        bond_state=bond_state,
        allostasis_state=allostasis_state,
        behavior_policy=behavior_policy,
    )
    behavior_plan = _behavior_plan_from_action(current_event, behavior_action)
    memory_evolved = False
    if not external_probe_mode and str(current_event.get("kind") or "user_utterance") == "user_utterance":
        memory_evolved = _passive_evolution_memory_update(
            store,
            user_text=effective_user_text or user_text,
            appraisal=appraisal,
            emotion_state=emotion_state,
            bond_state=bond_state,
            persona_core=persona_core,
            counterpart_profile=profile,
        )
    if memory_evolved:
        retrieved = _retrieve_context(effective_user_text or user_text, store)
        relationship = retrieved.get("relationship") if isinstance(retrieved.get("relationship"), dict) else store.get_relationship()
        worldline_focus = _worldline_focus(store)
        bond_state = _bond_next(
            bond_state,
            relationship,
            emotion_state,
            user_text,
            science_mode,
            appraisal,
        )
        allostasis_state = _allostasis_next(
            allostasis_state,
            emotion_state,
            bond_state,
            user_text,
            science_mode,
            appraisal,
        )
        behavior_policy = _behavior_policy_from_state(
            response_style_hint=response_style_hint,
            emotion_state=emotion_state,
            bond_state=bond_state,
            allostasis_state=allostasis_state,
            tsundere_intensity=tsundere,
            science_mode=science_mode,
            user_text=effective_user_text or user_text,
        )
        behavior_action = _behavior_action_from_state(
            current_event=current_event,
            response_style_hint=response_style_hint,
            user_text=effective_user_text or user_text,
            science_mode=science_mode,
            emotion_state=emotion_state,
            bond_state=bond_state,
            allostasis_state=allostasis_state,
            behavior_policy=behavior_policy,
        )
        behavior_plan = _behavior_plan_from_action(current_event, behavior_action)
    _audit_jsonl(
        "decision_audit.jsonl",
        {
            "working_items": int(len(retrieved.get("working_items") or [])),
            "working_chars": int(retrieved.get("working_chars") or 0),
            "retrieval_triggered": bool(retrieved.get("triggered")),
            "science_mode": bool(science_mode),
            "emotion_label": str(emotion_state.get("label") or "neutral"),
            "bond_trust": float(bond_state.get("trust") or 0.0),
            "bond_hurt": float(bond_state.get("hurt") or 0.0),
            "policy_warmth": float(behavior_policy.get("warmth") or 0.0),
            "behavior_mode": str(behavior_action.get("interaction_mode") or ""),
            "behavior_plan_kind": str(behavior_plan.get("kind") or ""),
            "appraisal_used": bool(appraisal.get("used", False)),
            "appraisal_confidence": float(appraisal.get("confidence", 0.0) or 0.0),
        },
    )

    return {
        "persona_core_override": dict(state.get("persona_core_override") or {}),
        "counterpart_profile_override": dict(state.get("counterpart_profile_override") or {}),
        "persona_state": persona_state,
        "emotion_state": emotion_state,
        "bond_state": bond_state,
        "allostasis_state": allostasis_state,
        "behavior_policy": behavior_policy,
        "behavior_action": behavior_action,
        "behavior_plan": behavior_plan,
        "turn_appraisal": appraisal,
        "current_event": current_event,
        "recent_events": recent_events,
        "response_style_hint": response_style_hint,
        "science_mode": science_mode,
        "tsundere_intensity": tsundere,
        "retrieved_context": retrieved,
        "worldline_focus": worldline_focus,
        "pending_utterance_fragment": pending,
        "pending_user_goal": pending_user_goal,
        "tool_round": int(state.get("tool_round", 0)),
        "toolset_unlocks": dict(state.get("toolset_unlocks") or {}),
        "evidence_pack": list(state.get("evidence_pack") or []),
        "last_external_tools": list(state.get("last_external_tools") or []),
        "memory_guard_checked": int(state.get("memory_guard_checked", 0) or 0),
        "memory_guard_blocked": int(state.get("memory_guard_blocked", 0) or 0),
        "event_override": {},
    }


def _available_tools_for_state(state: ThreadState) -> list[BaseTool]:
    if _is_external_probe_context(state=state):
        return []
    bundle = _get_tool_bundle()
    unlocks = dict(state.get("toolset_unlocks") or {})
    now = _now_ts()
    active = {k for k, exp in unlocks.items() if int(exp) > now}
    worldline_ablation = bool(ABLATE_WORLDLINE_MEMORY)

    tools: list[BaseTool] = []
    for t in bundle.base_tools:
        if t is not None:
            if worldline_ablation and str(getattr(t, "name", "") or "") in WORLDLINE_ABLATION_READ_TOOLS:
                continue
            tools.append(t)
    for t in bundle.extended_tools:
        if t is None:
            continue
        name = str(getattr(t, "name", "") or "")
        if worldline_ablation and name in WORLDLINE_ABLATION_READ_TOOLS:
            continue
        if name in active:
            tools.append(t)
    return tools


def _node_call_model(state: ThreadState) -> dict[str, Any]:
    store = _get_store()
    msgs = _messages(state)
    user_text = _clean_utf8_text(_last_user_text(msgs))
    pending_user_goal = str(state.get("pending_user_goal") or "").strip()
    continuation_mode = is_continuation_request(user_text)
    prompt = _build_task_prompt(state, user_text, store)
    history = _window_messages(msgs, int(CONTEXT_KEEP_LAST_MESSAGES))
    if continuation_mode and pending_user_goal:
        goal_for_model = _canonicalize_pending_goal_text(pending_user_goal)
        continuation_msg = HumanMessage(content=f"不要继续别的话题，只完成这个任务：{goal_for_model}")
        call_msgs: list[BaseMessage] = [_sanitize_message(SystemMessage(content=prompt)), _sanitize_message(continuation_msg)]
    else:
        call_msgs = [_sanitize_message(SystemMessage(content=prompt)), *[_sanitize_message(m) for m in history]]

    tools = _available_tools_for_state(state)
    should_force = bool(msgs and isinstance(msgs[-1], HumanMessage))
    forced_tcs: list[dict[str, Any]] = []
    if should_force:
        forced_tcs = _parse_explicit_tool_call(user_text, tools) or []
        if not forced_tcs:
            forced_tcs = _infer_memory_tool_calls(user_text)
        else:
            forced_tcs = list(forced_tcs)
    if forced_tcs:
        return {"messages": [AIMessage(content="", tool_calls=forced_tcs)]}

    response_style_hint = str(state.get("response_style_hint") or "natural").strip() or "natural"
    free_dialog = _is_free_dialog_style(response_style_hint, user_text, bool(state.get("science_mode", False)))
    if continuation_mode and pending_user_goal:
        tools = []
        if _needs_structured_answer(pending_user_goal, ""):
            free_dialog = False
        else:
            free_dialog = True
    if response_style_hint in {"memory_recall", "companion", "relationship", "casual", "natural"}:
        model_temp = 0.25
    elif response_style_hint == "structured" or bool(state.get("science_mode", False)):
        model_temp = 0.18
    else:
        model_temp = 0.25
    llm = _model(temperature=model_temp)
    llm_tools = llm if free_dialog else (llm.bind_tools(tools) if tools else llm)
    ai = _invoke_model_with_retries(llm_tools, call_msgs)
    if not isinstance(ai, AIMessage):
        ai = AIMessage(content=str(getattr(ai, "content", "") or ""))

    tool_calls = list(getattr(ai, "tool_calls", None) or [])
    if tool_calls:
        return {"messages": [ai]}

    draft_text = _sanitize_final_answer(str(ai.content or ""), user_text)
    aligned = draft_text
    risk, flags = _ooc_risk(aligned)
    gap, gap_flags = _persona_gap(aligned, state)
    draft_risk = risk
    draft_gap = gap
    alignment_applied = False
    alignment_reasons: list[str] = []
    relationship = store.get_relationship()
    persona_state = state.get("persona_state") or {}
    worldline_focus = state.get("worldline_focus") or []
    tsundere = float(state.get("tsundere_intensity", 0.55) or 0.55)
    response_style_hint = str(state.get("response_style_hint") or "natural").strip() or "natural"

    force_persona_align = (not bool(ABLATE_PERSONA_ALIGNMENT)) and _should_force_persona_align(response_style_hint, user_text)

    # For natural dialog turns, always run one light persona alignment pass.
    # For other turns, align when OOC risk/persona gap crosses threshold.
    if force_persona_align or (
        (not bool(ABLATE_PERSONA_ALIGNMENT))
        and (risk >= float(OOC_RISK_THRESHOLD) or gap >= float(PERSONA_GAP_THRESHOLD))
    ):
        alignment_applied = True
        if force_persona_align:
            alignment_reasons.append("natural_role_pass")
        if risk >= float(OOC_RISK_THRESHOLD):
            alignment_reasons.append("ooc_risk")
        if gap >= float(PERSONA_GAP_THRESHOLD):
            alignment_reasons.append("persona_gap")
        aligned = _align_persona(
            user_text=user_text,
            draft_text=aligned,
            science_mode=bool(state.get("science_mode", False)),
            response_style_hint=response_style_hint,
            emotion_state=state.get("emotion_state") or {},
            persona_state=persona_state,
            relationship=relationship,
            worldline_focus=worldline_focus,
            current_event=state.get("current_event") if isinstance(state.get("current_event"), dict) else {},
            recent_events=state.get("recent_events") if isinstance(state.get("recent_events"), list) else [],
            bond_state=state.get("bond_state") or {},
            allostasis_state=state.get("allostasis_state") or {},
            behavior_policy=state.get("behavior_policy") or {},
            behavior_action=state.get("behavior_action") or {},
            appraisal=state.get("turn_appraisal") or {},
            tsundere_intensity=tsundere,
        )
        aligned = _sanitize_final_answer(aligned, user_text)
        risk, flags = _ooc_risk(aligned)
        gap, gap_flags = _persona_gap(aligned, state)

    if (not bool(ABLATE_PERSONA_ALIGNMENT)) and max(risk, gap) >= float(OOC_REWRITE_THRESHOLD):
        alignment_applied = True
        alignment_reasons.append("strict_rewrite")
        aligned = _align_persona(
            user_text=user_text,
            draft_text=aligned,
            science_mode=bool(state.get("science_mode", False)),
            response_style_hint=response_style_hint,
            emotion_state=state.get("emotion_state") or {},
            persona_state=persona_state,
            relationship=relationship,
            worldline_focus=worldline_focus,
            current_event=state.get("current_event") if isinstance(state.get("current_event"), dict) else {},
            recent_events=state.get("recent_events") if isinstance(state.get("recent_events"), list) else [],
            bond_state=state.get("bond_state") or {},
            allostasis_state=state.get("allostasis_state") or {},
            behavior_policy=state.get("behavior_policy") or {},
            behavior_action=state.get("behavior_action") or {},
            appraisal=state.get("turn_appraisal") or {},
            tsundere_intensity=tsundere,
            strict=True,
        )
        aligned = _sanitize_final_answer(aligned, user_text)
        risk, flags = _ooc_risk(aligned)
        gap, gap_flags = _persona_gap(aligned, state)

    canon = _canon_guard(aligned, store)
    canon_risk = min(1.0, risk + (0.3 if not bool(canon.get("ok")) else 0.0))

    evidence_pack = list(state.get("evidence_pack") or [])
    claims = [] if bool(ABLATE_CLAIM_ATTRIBUTION) else build_claim_attribution(aligned, evidence_pack)
    ext_tools = set(state.get("last_external_tools") or [])
    if ext_tools and not claims and not bool(ABLATE_CLAIM_ATTRIBUTION):
        aligned = aligned.strip() + "\n\n(外部信息未形成可追溯证据链，以上结论按暂定处理。)"

    aligned = _sanitize_final_answer(aligned, user_text)
    aligned = _ensure_response_structure(aligned, user_text)
    final_msg = AIMessage(content=aligned)
    return {
        "messages": [final_msg],
        "ooc_detector": {
            "draft_risk": draft_risk,
            "draft_gap": draft_gap,
            "risk": risk,
            "flags": flags,
            "gap": gap,
            "gap_flags": gap_flags,
            "threshold": float(OOC_RISK_THRESHOLD),
            "persona_gap_threshold": float(PERSONA_GAP_THRESHOLD),
            "alignment_applied": alignment_applied,
            "alignment_reasons": list(dict.fromkeys(alignment_reasons)),
            "ablation_persona_alignment": bool(ABLATE_PERSONA_ALIGNMENT),
            "ablation_worldline_memory": bool(ABLATE_WORLDLINE_MEMORY),
            "ablation_claim_attribution": bool(ABLATE_CLAIM_ATTRIBUTION),
        },
        "canon_guard": canon,
        "canon_risk_score": canon_risk,
        "claim_links": claims,
    }


def _route_after_model(state: ThreadState) -> str:
    ai = _latest_ai(_messages(state))
    if ai is None:
        return END
    tool_calls = list(getattr(ai, "tool_calls", None) or [])
    if not tool_calls:
        return END
    if int(state.get("tool_round", 0)) >= int(TOOL_CALLS_MAX):
        return "tool_limit"
    return "tool_gate"


def _route_after_prepare(state: ThreadState) -> str:
    current_event = state.get("current_event") if isinstance(state.get("current_event"), dict) else {}
    behavior_action = state.get("behavior_action") if isinstance(state.get("behavior_action"), dict) else {}
    if _is_silent_idle_event(current_event, behavior_action):
        return END
    return "call_model"


def _tool_limit_fallback_text(state: ThreadState) -> str:
    user_text = _last_user_text(_messages(state))
    if any(marker in user_text for marker in {"记得", "回忆", "上次", "之前", "继续"}):
        text = "我一下子还接不上刚才那段。你把最关键的那句再给我一下，我就顺着接回去。"
    elif any(marker in user_text for marker in {"检索", "搜索", "文档", "资料"}):
        text = "这轮我先停在这里。再继续盲查意义不大，你把关键词再收紧一点，我就继续往下翻。"
    else:
        text = "我先停在这里。再硬往下翻只会越说越乱，你把问题再收紧一点，我就继续。"
    return _ensure_response_structure(text.replace("\\n", "\n"), user_text)


def _node_tool_limit(state: ThreadState) -> dict[str, Any]:
    msgs = _messages(state)
    ai = _latest_ai(msgs)
    tool_msgs: list[ToolMessage] = []
    for tc in list(getattr(ai, "tool_calls", None) or []):
        tc_id = str(tc.get("id") or "")
        if not tc_id:
            continue
        payload = {
            "ok": False,
            "error": {
                "code": "TOOL_LIMIT",
                "message": f"tool calls exceeded max={int(TOOL_CALLS_MAX)} for this turn",
            },
        }
        tool_msgs.append(ToolMessage(content=_safe_json(payload), tool_call_id=tc_id))

    msg = AIMessage(content=_tool_limit_fallback_text(state))
    return {"messages": [*tool_msgs, msg]}


def _node_tool_gate(state: ThreadState) -> dict[str, Any]:
    msgs = _messages(state)
    ai = _latest_ai(msgs)
    if ai is None:
        return {"approval_actions": []}

    tool_calls = list(getattr(ai, "tool_calls", None) or [])
    if not tool_calls:
        return {"approval_actions": []}

    auto_set = auto_approve_tool_names()
    queued: list[dict[str, Any]] = []
    need_human: list[dict[str, Any]] = []
    order: list[str] = []

    for tc in tool_calls:
        tc_id = str(tc.get("id") or "")
        name = str(tc.get("name") or "")
        args = tc.get("args") if isinstance(tc.get("args"), dict) else {}
        if not tc_id:
            tc_id = f"call_{len(order)}"
        order.append(tc_id)
        row = {"id": tc_id, "name": name, "args": args}
        if name in auto_set:
            queued.append({**row, "action": "approve"})
        else:
            need_human.append(row)

    if need_human:
        source = "memory" if any(str(x.get("name") or "") in MEMORY_WRITE_TOOLS for x in need_human) else "dialog"
        resume = interrupt(
            {
                "kind": "tool_approval",
                "source": source,
                "tool_calls": need_human,
            }
        )

        decisions: list[dict[str, Any]] = []
        if isinstance(resume, dict):
            dec = resume.get("decisions")
            if isinstance(dec, list):
                decisions = [d for d in dec if isinstance(d, dict)]

        for i, row in enumerate(need_human):
            d = decisions[i] if i < len(decisions) else {"action": "reject"}
            action = str(d.get("action") or "reject").strip().lower()
            if action not in {"approve", "reject", "edit"}:
                action = "reject"
            edit_args = d.get("args") if isinstance(d.get("args"), dict) else row["args"]
            queued.append(
                {
                    **row,
                    "action": action,
                    "args": edit_args,
                    "reason": str(d.get("reason") or "").strip(),
                }
            )

    rank = {tc_id: idx for idx, tc_id in enumerate(order)}
    queued.sort(key=lambda x: rank.get(str(x.get("id")), 10_000))
    return {"approval_actions": queued}


def _tool_lookup(name: str) -> BaseTool | None:
    bundle = _get_tool_bundle()
    for t in [*bundle.base_tools, *bundle.extended_tools]:
        if t is None:
            continue
        if str(getattr(t, "name", "") or "") == name:
            return t
    return None


def _node_tool_execute(state: ThreadState) -> dict[str, Any]:
    store = _get_store()
    msgs = _messages(state)
    ai = _latest_ai(msgs)
    if ai is None:
        return {"approval_actions": []}

    tool_calls = list(getattr(ai, "tool_calls", None) or [])
    actions = list(state.get("approval_actions") or [])
    action_map = {str(a.get("id") or ""): a for a in actions}

    unlocks = dict(state.get("toolset_unlocks") or {})
    evidence_pack = list(state.get("evidence_pack") or [])
    external_tools = set(state.get("last_external_tools") or [])
    guard_checked = int(state.get("memory_guard_checked", 0) or 0)
    guard_blocked = int(state.get("memory_guard_blocked", 0) or 0)

    tool_msgs: list[ToolMessage] = []
    for tc in tool_calls:
        tc_id = str(tc.get("id") or "")
        name = str(tc.get("name") or "")
        args = tc.get("args") if isinstance(tc.get("args"), dict) else {}
        decision = action_map.get(tc_id, {"action": "reject", "reason": "no decision"})
        action = str(decision.get("action") or "reject").strip().lower()
        if action == "edit" and isinstance(decision.get("args"), dict):
            args = dict(decision.get("args"))

        record: dict[str, Any] = {
            "tool": name,
            "tool_call_id": tc_id,
            "action": action,
            "args": args,
        }

        if action == "reject":
            reason = str(decision.get("reason") or "rejected").strip()
            payload = {"ok": False, "error": {"code": "REJECTED", "message": reason}}
            tool_msgs.append(ToolMessage(content=_safe_json(payload), tool_call_id=tc_id))
            record["result"] = payload
            _audit_jsonl("tool_audit.jsonl", record)
            continue

        if name in MEMORY_WRITE_TOOLS:
            guard_checked += 1
        ok, reason = _memory_guard_check(name, args, store)
        if not ok:
            guard_blocked += 1
            payload = {"ok": False, "error": {"code": "MEMORY_GUARD_BLOCKED", "message": reason}}
            tool_msgs.append(ToolMessage(content=_safe_json(payload), tool_call_id=tc_id))
            record["result"] = payload
            _audit_jsonl("tool_audit.jsonl", record)
            continue

        tool = _tool_lookup(name)
        if tool is None:
            payload = {"ok": False, "error": {"code": "TOOL_NOT_FOUND", "message": name}}
            tool_msgs.append(ToolMessage(content=_safe_json(payload), tool_call_id=tc_id))
            record["result"] = payload
            _audit_jsonl("tool_audit.jsonl", record)
            continue

        try:
            result = _invoke_tool(tool, args)
            _auto_reconsolidate_after_tool(
                store,
                tool_name=name,
                args=args,
                result=result,
            )
            payload = {"ok": True, "data": result}
            tool_msgs.append(ToolMessage(content=_safe_json(payload), tool_call_id=tc_id))

            if name == "request_toolset_upgrade" and isinstance(result, dict):
                req = result.get("requested_tools")
                if isinstance(req, list):
                    exp = _now_ts() + int(TOOLSET_UPGRADE_TTL_S)
                    for x in req:
                        nm = str(x).strip()
                        if nm:
                            unlocks[nm] = exp

            ev = _build_evidence_from_tool_result(tool_name=name, result=result, store=store)
            if ev:
                evidence_pack.extend(ev)
                external_tools.add(name)
            elif name in CLAIM_REQUIRED_TOOLS:
                external_tools.add(name)

            record["result"] = payload
            _audit_jsonl("tool_audit.jsonl", record)
        except Exception as e:
            payload = {"ok": False, "error": {"code": "TOOL_EXEC_ERROR", "message": str(e)}}
            tool_msgs.append(ToolMessage(content=_safe_json(payload), tool_call_id=tc_id))
            record["result"] = payload
            _audit_jsonl("tool_audit.jsonl", record)

    return {
        "messages": tool_msgs,
        "approval_actions": [],
        "tool_round": int(state.get("tool_round", 0)) + 1,
        "toolset_unlocks": unlocks,
        "evidence_pack": evidence_pack[-50:],
        "last_external_tools": sorted(list(external_tools)),
        "memory_guard_checked": guard_checked,
        "memory_guard_blocked": guard_blocked,
    }


def _build_checkpointer() -> SqliteSaver:
    global _CHECKPOINT_CONN
    if _CHECKPOINT_CONN is None:
        s = get_settings()
        s.checkpoint_db_path.parent.mkdir(parents=True, exist_ok=True)
        _CHECKPOINT_CONN = sqlite3.connect(str(s.checkpoint_db_path), check_same_thread=False)
        _CHECKPOINT_CONN.execute("PRAGMA journal_mode=WAL")
        _CHECKPOINT_CONN.execute("PRAGMA foreign_keys=ON")
    return SqliteSaver(_CHECKPOINT_CONN)


def reset_runtime_caches() -> None:
    global _CHECKPOINT_CONN
    try:
        if _CHECKPOINT_CONN is not None:
            _CHECKPOINT_CONN.close()
    except Exception:
        pass
    _CHECKPOINT_CONN = None
    _get_store.cache_clear()
    _get_tool_bundle.cache_clear()
    build_graph.cache_clear()


@lru_cache(maxsize=1)
def build_graph():
    s = get_settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)

    builder = StateGraph(ThreadState)
    builder.add_node("prepare_turn", _node_prepare_turn)
    builder.add_node("call_model", _node_call_model)
    builder.add_node("tool_gate", _node_tool_gate)
    builder.add_node("tool_execute", _node_tool_execute)
    builder.add_node("tool_limit", _node_tool_limit)

    builder.add_edge(START, "prepare_turn")
    builder.add_conditional_edges(
        "prepare_turn",
        _route_after_prepare,
        {
            "call_model": "call_model",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "call_model",
        _route_after_model,
        {
            "tool_gate": "tool_gate",
            "tool_limit": "tool_limit",
            END: END,
        },
    )
    builder.add_edge("tool_gate", "tool_execute")
    builder.add_edge("tool_execute", "call_model")
    builder.add_edge("tool_limit", END)

    return builder.compile(checkpointer=_build_checkpointer())

