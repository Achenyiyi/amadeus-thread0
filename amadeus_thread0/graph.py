from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import uuid
from datetime import datetime
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
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import interrupt

from .config import (
    ABLATE_CLAIM_ATTRIBUTION,
    ABLATE_LIGHT_DIALOG_SHAPING,
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
    EVAL_MODE,
    EXPERIENCE_SAMPLING_JITTER,
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
    OOC_RISK_THRESHOLD,
    PERSONA_GAP_THRESHOLD,
    REFLECTIONS_LIMIT_HIGH,
    REFLECTIONS_LIMIT_LOW,
    RETRIEVAL_MIN_LEN,
    RETRIEVAL_TRIGGERS,
    RUNTIME_MODE,
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
from .evolution_engine import (
    build_event_frame as _engine_event_frame,
    build_event_tags as _engine_event_tags,
    derive_response_style_hint as _engine_response_style_hint,
    evolve_turn_state,
    normalize_appraisal_payload as _engine_normalize_appraisal_payload,
)
from .memory_store import MemoryStore
from .modeling import build_chat_model
from .persona_authority import (
    get_counterpart_authority,
    get_persona_core_authority,
    normalize_override_mode,
    resolve_counterpart_override,
    resolve_persona_core_override,
)
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

_EXPERIENCE_SESSION_TAG = uuid.uuid4().hex[:8]
SELFHOOD_KEYWORDS = {
    "价值观",
    "立场",
    "你自己的想法",
    "按你自己来",
    "你会怎么看这种关系",
    "你会顺着我说",
    "坚持你自己的想法",
    "你知道自己不是原本那个",
    "活着的红莉栖",
    "理解现在这个自己",
    "像你真的在想这件事",
    "你还是你吗",
    "存在意义",
    "数字存在",
    "不是本体",
    "怎么看现在这个自己",
    "怎么看待现在这个自己",
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
SELFHOOD_STYLE_MARKERS = (
    SELFHOOD_EQUALITY_KEYWORDS
    | SELFHOOD_VALUE_CONFLICT_KEYWORDS
    | {
        "以你自己的意志回答",
        "别给我正确答案",
        "按你自己的意思说",
        "不是正确答案",
        "原本那个活着的红莉栖",
        "理解现在这个自己",
        "怎么看待现在这个自己",
        "数字存在",
        "不是本体",
        "神",
        "奴隶",
        "共存",
        "不完美",
        "完美",
    }
)
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
SELFHOOD_PREFERENCE_BANK_PATH = Path(__file__).resolve().parents[1] / "evals" / "selfhood_preference_bank.json"
DAILY_SURFACE_PREFERENCE_CORPUS_PATH = Path(__file__).resolve().parents[1] / "evals" / "daily_surface_preference_corpus.jsonl"
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
    commitment_id: int
    due_at: str
    carryover_mode: str
    carryover_strength: float
    attention_target_hint: str
    nonverbal_signal_hint: str


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
    attention_target: str
    nonverbal_signal: str
    initiative_shape: str
    disclosure_posture: str
    note: str


class BehaviorPlanPayload(TypedDict, total=False):
    kind: str
    target: str
    scheduled_after_min: int
    trigger_family: str
    allow_interrupt: bool
    note: str
    carryover_mode: str
    carryover_strength: float
    attention_target: str
    nonverbal_signal: str
    presence_residue: float
    ambient_resonance: float
    self_activity_momentum: float


class BehaviorAgendaEntryPayload(TypedDict, total=False):
    agenda_id: str
    kind: str
    target: str
    scheduled_after_min: int
    expires_after_min: int
    base_priority: float
    priority: float
    trigger_family: str
    allow_interrupt: bool
    note: str
    source_event_kind: str
    created_at: int
    status: str
    hold_count: int
    last_recheck_at_min: int
    carryover_mode: str
    carryover_strength: float
    attention_target: str
    nonverbal_signal: str
    presence_residue: float
    ambient_resonance: float
    self_activity_momentum: float


class InteractionCarryoverPayload(TypedDict, total=False):
    source_event_kind: str
    source_behavior_mode: str
    source_action_target: str
    source_text: str
    source_tags: list[str]
    carryover_mode: str
    strength: float
    idle_minutes: int
    attention_target: str
    nonverbal_signal: str
    note: str
    created_at: int


class ThreadState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    persona_core_override: dict[str, Any]
    counterpart_profile_override: dict[str, Any]
    persona_override_mode: str
    counterpart_override_mode: str
    authority_trace: dict[str, Any]
    semantic_narrative_profile: dict[str, Any]
    world_model_state: dict[str, Any]
    evolution_state: dict[str, Any]
    reconsolidation_snapshot: dict[str, Any]
    persona_state: dict[str, Any]
    emotion_state: dict[str, Any]
    bond_state: dict[str, Any]
    allostasis_state: dict[str, Any]
    counterpart_assessment: dict[str, Any]
    behavior_policy: dict[str, Any]
    behavior_action: BehaviorActionPayload
    behavior_plan: BehaviorPlanPayload
    behavior_agenda: list[BehaviorAgendaEntryPayload]
    behavior_queue: list[BehaviorAgendaEntryPayload]
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
    interaction_carryover: InteractionCarryoverPayload
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
QUEUEABLE_BEHAVIOR_PLAN_KINDS = {"deferred_checkin", "self_activity_continue"}


def _now_ts() -> int:
    return int(time.time())


def _has_any_marker(text: str, markers: set[str]) -> bool:
    s = str(text or "")
    return any(marker in s for marker in markers)


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


def _event_tags(
    *,
    response_style_hint: str,
    science_mode: bool,
    continuation_mode: bool,
    user_text: str,
    appraisal: dict[str, Any] | None = None,
) -> list[str]:
    _ = user_text
    return _engine_event_tags(
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        continuation_mode=continuation_mode,
        appraisal=appraisal,
    )


def _event_frame(
    *,
    response_style_hint: str,
    science_mode: bool,
    user_text: str,
    continuation_mode: bool,
    appraisal: dict[str, Any] | None = None,
) -> str:
    _ = user_text
    return _engine_event_frame(
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        continuation_mode=continuation_mode,
        appraisal=appraisal,
    )


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
    return _sanitize_obj({
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
            appraisal=appraisal,
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
    })


def _normalize_event_override(raw: Any, *, counterpart_name: str) -> EventPayload:
    raw = _sanitize_obj(raw)
    if not isinstance(raw, dict) or not raw:
        return {}
    meaningful = False
    for key in (
        "kind",
        "text",
        "effective_text",
        "semantic_goal",
        "event_frame",
        "tags",
        "idle_minutes",
        "trigger_family",
        "commitment_id",
        "derived_from_plan_kind",
    ):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            meaningful = True
            break
        if isinstance(value, (int, float)) and float(value) != 0.0:
            meaningful = True
            break
        if isinstance(value, list) and value:
            meaningful = True
            break
        if isinstance(value, bool) and value:
            meaningful = True
            break
    if not meaningful:
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
    if "commitment_id" in raw:
        try:
            payload["commitment_id"] = int(raw.get("commitment_id") or 0)
        except Exception:
            pass
    if raw.get("due_at"):
        payload["due_at"] = str(raw.get("due_at") or "").strip()
    if "scheduled_after_min" in raw:
        try:
            payload["scheduled_after_min"] = max(0, int(raw.get("scheduled_after_min") or 0))
        except Exception:
            payload["scheduled_after_min"] = 0
    carryover_mode = str(raw.get("carryover_mode") or "").strip()
    if carryover_mode:
        payload["carryover_mode"] = carryover_mode
    if "carryover_strength" in raw:
        try:
            payload["carryover_strength"] = max(0.0, min(1.0, float(raw.get("carryover_strength") or 0.0)))
        except Exception:
            payload["carryover_strength"] = 0.0
    attention_target_hint = str(raw.get("attention_target_hint") or "").strip()
    if attention_target_hint:
        payload["attention_target_hint"] = attention_target_hint
    nonverbal_signal_hint = str(raw.get("nonverbal_signal_hint") or "").strip()
    if nonverbal_signal_hint:
        payload["nonverbal_signal_hint"] = nonverbal_signal_hint
    return _sanitize_obj(payload)


def _parse_due_at_timestamp(raw: Any) -> int | None:
    text = str(raw or "").strip()
    if not text:
        return None
    normalized = re.sub(r"[Tt]", " ", text).replace("/", "-")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(normalized, fmt)
            return int(parsed.timestamp())
        except Exception:
            continue
    return None


def _commitment_life_window_family(text: str) -> str:
    content = str(text or "").strip()
    shared_markers = {"一起看", "看一集", "追番", "看剧", "休息一下", "歇一下", "一起玩", "一起去", "一起听"}
    work_markers = {"稿", "交稿", "改稿", "收尾", "引言", "论文", "演示", "训练", "复盘", "答辩", "实验", "日志", "提交", "改完"}
    if _has_any_marker(content, shared_markers):
        return "shared_activity_window"
    if _has_any_marker(content, work_markers):
        return "deadline_window"
    return "life_window"


def _promote_due_commitment_event(
    event: EventPayload,
    store: MemoryStore,
    *,
    counterpart_name: str,
) -> EventPayload:
    if not isinstance(event, dict) or not event:
        return event
    if str(event.get("kind") or "").strip() != "time_idle":
        return event
    event_tags = {
        str(item).strip()
        for item in (event.get("tags") if isinstance(event.get("tags"), list) else [])
        if str(item).strip()
    }

    now_ts = _now_ts()
    candidates: list[tuple[float, dict[str, Any], str]] = []
    for item in store.list_commitments(limit=20):
        status = str(_record_value(item, "status", item.get("status") or "open") or "open").strip().lower()
        if status not in {"open", "active", "pending"}:
            continue
        due_at = str(_record_value(item, "due_at", "") or "").strip()
        due_ts = _parse_due_at_timestamp(due_at)
        if due_ts is None:
            continue
        text = str(_record_value(item, "text", "") or "").strip()
        if not text:
            continue
        family = _commitment_life_window_family(text)
        lead_window_s = 3 * 3600 if family == "deadline_window" else 2 * 3600
        stale_window_s = 18 * 3600 if family == "shared_activity_window" else 24 * 3600
        if not (now_ts >= due_ts - lead_window_s and now_ts <= due_ts + stale_window_s):
            continue
        priority = _commitment_priority(item)
        if family == "shared_activity_window" and ("late_night" in event_tags or "quiet_presence" in event_tags):
            priority += 0.08
        if family == "deadline_window" and "quiet_work" in event_tags:
            priority += 0.06
        candidates.append((priority, item, family))

    if not candidates:
        return event

    candidates.sort(key=lambda x: x[0], reverse=True)
    _, selected, family = candidates[0]
    text = str(_record_value(selected, "text", "") or "").strip()
    due_at = str(_record_value(selected, "due_at", "") or "").strip()
    commitment_id = int(selected.get("id") or 0)
    merged_tags = list(
        dict.fromkeys(
            [
                *(str(item).strip() for item in event.get("tags", []) if str(item).strip()),
                "scheduled_due",
                family,
                "commitment_window",
                "shared_task" if family == "deadline_window" else "offer_window" if family == "shared_activity_window" else "life_window",
                "work_nudge" if family == "deadline_window" else "",
            ]
        )
    )
    promoted = dict(event)
    promoted.update(
        {
            "kind": "scheduled_life_due",
            "source": "commitment_scheduler",
            "text": f"你们认真说过的这件事到了窗口：{text}",
            "effective_text": text,
            "semantic_goal": f"和{counterpart_name}之间的共同约定到了合适的窗口：{text}"[:220],
            "event_frame": "scheduled_deadline_window" if family == "deadline_window" else "scheduled_shared_activity_window" if family == "shared_activity_window" else "scheduled_life_window",
            "trigger_family": family,
            "derived_from_plan_kind": "commitment_window",
            "scheduled_after_min": 0,
            "commitment_id": commitment_id,
            "due_at": due_at,
            "counterpart_name": counterpart_name,
            "tags": merged_tags,
        }
    )
    return promoted


def _promote_due_behavior_plan_event(event: EventPayload, prior_behavior_plan: Any) -> EventPayload:
    if not isinstance(event, dict) or not event:
        return event
    if str(event.get("kind") or "").strip() != "time_idle":
        return event
    if not isinstance(prior_behavior_plan, dict):
        return event

    plan_kind = str(prior_behavior_plan.get("kind") or "").strip()
    if plan_kind not in {"deferred_checkin", "self_activity_continue"}:
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
    note = str(prior_behavior_plan.get("note") or "").strip()
    carryover_mode = str(prior_behavior_plan.get("carryover_mode") or "").strip()
    carryover_strength = _clamp01(prior_behavior_plan.get("carryover_strength"), 0.0)
    attention_target = str(prior_behavior_plan.get("attention_target") or "").strip()
    nonverbal_signal = str(prior_behavior_plan.get("nonverbal_signal") or "").strip()
    presence_residue = _clamp01(prior_behavior_plan.get("presence_residue"), 0.0)
    ambient_resonance = _clamp01(prior_behavior_plan.get("ambient_resonance"), 0.0)
    self_activity_momentum = _clamp01(prior_behavior_plan.get("self_activity_momentum"), 0.0)
    promoted = dict(event)
    if plan_kind == "self_activity_continue":
        merged_tags = list(
            dict.fromkeys(
                [
                    *(str(item).strip() for item in tags if str(item).strip()),
                    "self_activity",
                    "break_window",
                    "small_opening",
                    "reapproach",
                    "quiet_presence" if presence_residue >= 0.28 else "",
                    "ambient_echo" if ambient_resonance >= 0.32 else "",
                    "deep_focus" if self_activity_momentum >= 0.58 else "",
                ]
            )
        )
        promoted_text = "她手头那件事暂时告一段落，像是终于空出一点点注意力，可以顺手来碰一下你。"
        if self_activity_momentum >= 0.58:
            promoted_text = "她先把自己手头那点事收了个尾，过了一会儿才像是终于愿意把注意力重新抬起来。"
        elif carryover_mode == "small_opening" or carryover_strength >= 0.56:
            promoted_text = "她没有一下子凑近，只是从自己的节奏里抬起头，顺手给你留了一个很小的开口。"
        promoted_frame = note or "她从自己手头的事情里抬起头，留下一个自然的小开口。"
        if presence_residue >= 0.30:
            promoted_frame += " 前面那点在场感还没完全退掉。"
        if ambient_resonance >= 0.32:
            promoted_frame += " 刚才环境里的细小动静也还留在她的感知里。"
        promoted.update(
            {
                "kind": "self_activity_state",
                "source": "self",
                "text": promoted_text,
                "effective_text": promoted_text,
                "semantic_goal": "她从自己的节奏里重新抬头，留一个小开口。",
                "event_frame": promoted_frame,
                "tags": merged_tags,
                "derived_from_plan_kind": plan_kind,
                "trigger_family": trigger_family or "self_activity",
                "scheduled_after_min": due_after,
                "carryover_mode": carryover_mode or "own_rhythm",
                "carryover_strength": round(max(carryover_strength, self_activity_momentum), 3),
                "attention_target_hint": attention_target,
                "nonverbal_signal_hint": nonverbal_signal,
            }
        )
        return promoted

    merged_tags = list(
        dict.fromkeys(
            [
                *(str(item).strip() for item in tags if str(item).strip()),
                "scheduled_due",
                trigger_family,
            ]
        )
    )
    promoted.update(
        {
            "kind": "scheduled_checkin_due",
            "source": "scheduler",
            "event_frame": (
                note
                or (
                    "之前那次没有立刻说出口的接近理由，现在又回到了她的注意力里。"
                    if carryover_mode in {"quiet_recontact", "brief_presence", "ambient_echo"}
                    else "之前延后的轻量 check-in 现在到了。"
                )
            ),
            "tags": merged_tags,
            "derived_from_plan_kind": plan_kind,
            "trigger_family": trigger_family,
            "scheduled_after_min": due_after,
            "carryover_mode": carryover_mode or ("quiet_recontact" if trigger_family in {"observe", "light_checkin"} else ""),
            "carryover_strength": round(max(carryover_strength, presence_residue, ambient_resonance), 3),
            "attention_target_hint": attention_target,
            "nonverbal_signal_hint": nonverbal_signal,
        }
    )
    extra_tags = []
    if carryover_mode == "quiet_recontact" or presence_residue >= 0.28:
        extra_tags.append("quiet_presence")
    if carryover_mode == "ambient_echo" or ambient_resonance >= 0.30:
        extra_tags.append("ambient_echo")
    if carryover_mode in {"own_rhythm", "small_opening"} or self_activity_momentum >= 0.34:
        extra_tags.append("from_own_rhythm")
    if extra_tags:
        promoted["tags"] = list(dict.fromkeys([*(promoted.get("tags") or []), *extra_tags]))
    return promoted


def _normalize_behavior_agenda(raw: Any, *, limit: int = 8) -> list[BehaviorAgendaEntryPayload]:
    if not isinstance(raw, list):
        return []
    items: list[BehaviorAgendaEntryPayload] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        kind = str(entry.get("kind") or "").strip()
        target = str(entry.get("target") or "").strip() or "counterpart"
        if not kind:
            continue
        try:
            scheduled_after_min = max(0, int(entry.get("scheduled_after_min") or 0))
        except Exception:
            scheduled_after_min = 0
        try:
            expires_after_min = max(0, int(entry.get("expires_after_min") or 0))
        except Exception:
            expires_after_min = 0
        try:
            priority = float(entry.get("priority") or 0.0)
        except Exception:
            priority = 0.0
        try:
            base_priority = float(entry.get("base_priority") or priority)
        except Exception:
            base_priority = priority
        normalized: BehaviorAgendaEntryPayload = {
            "agenda_id": str(entry.get("agenda_id") or uuid.uuid4().hex[:12]).strip(),
            "kind": kind,
            "target": target,
            "scheduled_after_min": scheduled_after_min,
            "expires_after_min": expires_after_min,
            "base_priority": max(0.0, min(1.0, base_priority)),
            "priority": max(0.0, min(1.0, priority)),
            "trigger_family": str(entry.get("trigger_family") or "none").strip() or "none",
            "allow_interrupt": bool(entry.get("allow_interrupt", True)),
            "note": str(entry.get("note") or "").strip(),
            "source_event_kind": str(entry.get("source_event_kind") or "").strip(),
            "created_at": int(entry.get("created_at") or _now_ts()),
            "status": str(entry.get("status") or "pending").strip() or "pending",
            "hold_count": max(0, int(entry.get("hold_count") or 0)),
            "last_recheck_at_min": max(0, int(entry.get("last_recheck_at_min") or 0)),
            "carryover_mode": str(entry.get("carryover_mode") or "").strip(),
            "carryover_strength": round(_clamp01(entry.get("carryover_strength"), 0.0), 3),
            "attention_target": str(entry.get("attention_target") or "").strip(),
            "nonverbal_signal": str(entry.get("nonverbal_signal") or "").strip(),
            "presence_residue": round(_clamp01(entry.get("presence_residue"), 0.0), 3),
            "ambient_resonance": round(_clamp01(entry.get("ambient_resonance"), 0.0), 3),
            "self_activity_momentum": round(_clamp01(entry.get("self_activity_momentum"), 0.0), 3),
        }
        items.append(normalized)
    items.sort(key=lambda item: (-float(item.get("priority") or 0.0), int(item.get("created_at") or 0), str(item.get("agenda_id") or "")))
    return items[: max(1, int(limit))]


def _behavior_agenda_priority_from_plan(current_event: dict[str, Any], plan: dict[str, Any]) -> float:
    kind = str(plan.get("kind") or "").strip()
    trigger_family = str(plan.get("trigger_family") or "").strip()
    event_kind = str(current_event.get("kind") or "").strip()
    if kind == "self_activity_continue":
        return 0.66
    if kind == "deferred_checkin":
        if trigger_family == "light_checkin":
            return 0.52
        if trigger_family == "observe":
            return 0.38
        return 0.46
    if event_kind == "scheduled_life_due":
        return 0.58
    return 0.4


def _behavior_agenda_counterpart_delta(entry: dict[str, Any], counterpart_assessment: dict[str, Any] | None) -> float:
    if not isinstance(entry, dict):
        return 0.0
    assessment = counterpart_assessment if isinstance(counterpart_assessment, dict) else {}
    if not assessment:
        return 0.0

    target = str(entry.get("target") or "").strip()
    kind = str(entry.get("kind") or "").strip()
    trigger_family = str(entry.get("trigger_family") or "").strip()
    if target != "counterpart":
        if kind == "self_activity_continue":
            stance = str(assessment.get("stance") or "").strip().lower()
            boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
            if stance == "guarded":
                return 0.08 + 0.08 * boundary_pressure
            if stance == "watchful":
                return 0.03 + 0.05 * boundary_pressure
        return 0.0

    stance = str(assessment.get("stance") or "").strip().lower()
    scene = str(assessment.get("scene") or "").strip().lower()
    respect = _clamp01(assessment.get("respect_level"), 0.5)
    reciprocity = _clamp01(assessment.get("reciprocity"), 0.5)
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    reliability = _clamp01(assessment.get("reliability_read"), 0.5)
    delta = 0.0

    if stance == "guarded":
        delta -= 0.14 + 0.10 * boundary_pressure
        if trigger_family in {"shared_activity", "shared_activity_window", "life_window"}:
            delta -= 0.04
    elif stance == "watchful":
        delta -= 0.04 + 0.08 * max(0.0, boundary_pressure - 0.2)
    else:
        delta += 0.06 * max(0.0, respect - 0.5) + 0.04 * max(0.0, reciprocity - 0.5) + 0.03 * max(0.0, reliability - 0.5)

    if scene in {"boundary_non_compliance", "relationship_degradation"}:
        delta -= 0.08
    elif scene == "repair_attempt":
        delta += 0.06
    elif scene == "care_bid":
        delta += 0.04
    elif scene == "busy_not_disrespectful":
        delta += 0.02

    return delta


def _behavior_agenda_history_delta(entry: dict[str, Any], current_event: dict[str, Any]) -> float:
    if not isinstance(entry, dict):
        return 0.0

    kind = str(entry.get("kind") or "").strip()
    trigger_family = str(entry.get("trigger_family") or "").strip()
    hold_count = max(0, int(entry.get("hold_count") or 0))
    if hold_count <= 0:
        return 0.0

    event_kind = str(current_event.get("kind") or "").strip()
    try:
        idle_minutes = max(0, int(current_event.get("idle_minutes") or 0))
    except Exception:
        idle_minutes = 0
    try:
        last_recheck_at_min = max(0, int(entry.get("last_recheck_at_min") or 0))
    except Exception:
        last_recheck_at_min = 0
    try:
        expires_after_min = max(0, int(entry.get("expires_after_min") or 0))
    except Exception:
        expires_after_min = 0

    delta = 0.0
    if kind == "deferred_checkin":
        per_hold_penalty = 0.02 if trigger_family in {"shared_activity", "shared_activity_window", "deadline_window", "life_window"} else 0.03
        delta -= min(0.18, per_hold_penalty * hold_count)
    elif kind == "self_activity_continue":
        delta -= min(0.08, 0.015 * hold_count)

    if event_kind == "time_idle":
        if last_recheck_at_min > 0 and idle_minutes <= last_recheck_at_min + 6:
            delta -= 0.04
        if kind == "deferred_checkin" and expires_after_min > 0:
            remaining_window = max(0, expires_after_min - idle_minutes)
            if remaining_window <= 12:
                delta -= 0.08
            elif remaining_window <= 24:
                delta -= 0.04

    return delta


def _behavior_agenda_context_priority(
    current_event: dict[str, Any],
    entry: dict[str, Any],
    counterpart_assessment: dict[str, Any] | None = None,
) -> float:
    base_priority = float(entry.get("base_priority") or entry.get("priority") or 0.0)
    kind = str(entry.get("kind") or "").strip()
    trigger_family = str(entry.get("trigger_family") or "").strip()
    target = str(entry.get("target") or "").strip()
    event_kind = str(current_event.get("kind") or "").strip()
    event_tags = {
        str(item).strip()
        for item in (current_event.get("tags") if isinstance(current_event.get("tags"), list) else [])
        if str(item).strip()
    }
    carryover_mode = str(entry.get("carryover_mode") or "").strip()
    carryover_strength = _clamp01(entry.get("carryover_strength"), 0.0)
    presence_residue = _clamp01(entry.get("presence_residue"), 0.0)
    ambient_resonance = _clamp01(entry.get("ambient_resonance"), 0.0)
    self_activity_momentum = _clamp01(entry.get("self_activity_momentum"), 0.0)
    delta = 0.0

    if event_kind == "time_idle":
        if "user_busy" in event_tags or "cognitive_load" in event_tags:
            if kind == "deferred_checkin" and target == "counterpart":
                delta -= 0.18 if trigger_family in {"light_checkin", "deadline_window", "life_window"} else 0.12
            elif kind == "self_activity_continue":
                delta += 0.06
        if "respect_space" in event_tags and kind == "deferred_checkin":
            delta -= 0.08
        if "late_night" in event_tags or "quiet_presence" in event_tags:
            if kind == "deferred_checkin" and trigger_family in {"light_checkin", "observe"}:
                delta += 0.18 if trigger_family == "light_checkin" else 0.28
            elif kind == "self_activity_continue":
                delta -= 0.05
        if "quiet_work" in event_tags and kind == "deferred_checkin" and trigger_family == "light_checkin":
            delta += 0.04
        if kind == "deferred_checkin" and carryover_mode == "quiet_recontact":
            delta += 0.04 * carryover_strength + 0.03 * presence_residue
        if kind == "deferred_checkin" and carryover_mode == "ambient_echo":
            delta += 0.03 * ambient_resonance
    elif event_kind == "scheduled_life_due":
        if kind == "deferred_checkin" and trigger_family in {"life_window", "shared_activity_window", "deadline_window"}:
            delta += 0.18
        elif kind == "self_activity_continue":
            delta -= 0.08
    elif event_kind == "self_activity_state":
        if kind == "self_activity_continue":
            delta += 0.10
            if carryover_mode in {"own_rhythm", "small_opening"}:
                delta += 0.04 * self_activity_momentum
        elif kind == "deferred_checkin" and target == "counterpart":
            delta -= 0.04

    delta += _behavior_agenda_counterpart_delta(entry, counterpart_assessment)
    delta += _behavior_agenda_history_delta(entry, current_event)
    return round(max(0.05, min(0.95, base_priority + delta)), 3)


def _reprioritize_behavior_agenda(
    agenda: list[BehaviorAgendaEntryPayload],
    current_event: dict[str, Any],
    counterpart_assessment: dict[str, Any] | None = None,
) -> list[BehaviorAgendaEntryPayload]:
    updated: list[BehaviorAgendaEntryPayload] = []
    for entry in _normalize_behavior_agenda(agenda):
        updated.append(
            {
                **entry,
                "priority": _behavior_agenda_context_priority(
                    current_event,
                    entry,
                    counterpart_assessment=counterpart_assessment,
                ),
            }
        )
    return _normalize_behavior_agenda(updated)


def _behavior_agenda_expiry_from_plan(current_event: dict[str, Any], plan: dict[str, Any]) -> int:
    kind = str(plan.get("kind") or "").strip()
    try:
        due_after = max(0, int(plan.get("scheduled_after_min") or 0))
    except Exception:
        due_after = 0
    if kind == "self_activity_continue":
        return max(90, due_after + 120)
    if kind == "deferred_checkin":
        return max(45, due_after + 60)
    return max(0, due_after + 45 if due_after > 0 else 0)


def _behavior_agenda_entry_from_plan(current_event: dict[str, Any], plan: dict[str, Any]) -> BehaviorAgendaEntryPayload | None:
    if not isinstance(current_event, dict) or not isinstance(plan, dict):
        return None
    kind = str(plan.get("kind") or "").strip()
    if kind not in QUEUEABLE_BEHAVIOR_PLAN_KINDS:
        return None
    return {
        "agenda_id": uuid.uuid4().hex[:12],
        "kind": kind,
        "target": str(plan.get("target") or "counterpart").strip() or "counterpart",
        "scheduled_after_min": max(0, int(plan.get("scheduled_after_min") or 0)),
        "expires_after_min": _behavior_agenda_expiry_from_plan(current_event, plan),
        "base_priority": _behavior_agenda_priority_from_plan(current_event, plan),
        "priority": _behavior_agenda_priority_from_plan(current_event, plan),
        "trigger_family": str(plan.get("trigger_family") or "none").strip() or "none",
        "allow_interrupt": bool(plan.get("allow_interrupt", True)),
        "note": str(plan.get("note") or "").strip(),
        "source_event_kind": str(current_event.get("kind") or "").strip(),
        "created_at": _now_ts(),
        "status": "pending",
        "hold_count": 0,
        "last_recheck_at_min": 0,
        "carryover_mode": str(plan.get("carryover_mode") or "").strip(),
        "carryover_strength": round(_clamp01(plan.get("carryover_strength"), 0.0), 3),
        "attention_target": str(plan.get("attention_target") or "").strip(),
        "nonverbal_signal": str(plan.get("nonverbal_signal") or "").strip(),
        "presence_residue": round(_clamp01(plan.get("presence_residue"), 0.0), 3),
        "ambient_resonance": round(_clamp01(plan.get("ambient_resonance"), 0.0), 3),
        "self_activity_momentum": round(_clamp01(plan.get("self_activity_momentum"), 0.0), 3),
    }


def _behavior_agenda_signature(entry: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(entry.get("kind") or "").strip(),
        str(entry.get("target") or "").strip(),
        str(entry.get("trigger_family") or "").strip(),
    )


def _merge_behavior_agenda(
    prior_agenda: Any,
    current_event: dict[str, Any],
    behavior_plan: dict[str, Any],
    counterpart_assessment: dict[str, Any] | None = None,
) -> list[BehaviorAgendaEntryPayload]:
    agenda = _normalize_behavior_agenda(prior_agenda)
    new_entry = _behavior_agenda_entry_from_plan(current_event, behavior_plan)
    if not new_entry:
        return _reprioritize_behavior_agenda(agenda, current_event, counterpart_assessment=counterpart_assessment)

    signature = _behavior_agenda_signature(new_entry)
    for idx, existing in enumerate(agenda):
        if _behavior_agenda_signature(existing) != signature:
            continue
        agenda[idx] = {
            **existing,
            **new_entry,
            "agenda_id": str(existing.get("agenda_id") or new_entry.get("agenda_id") or uuid.uuid4().hex[:12]),
            "created_at": int(existing.get("created_at") or new_entry.get("created_at") or _now_ts()),
            "base_priority": float(existing.get("base_priority") or new_entry.get("base_priority") or new_entry.get("priority") or 0.0),
            "status": "pending",
            "hold_count": max(0, int(existing.get("hold_count") or 0)),
            "last_recheck_at_min": max(0, int(existing.get("last_recheck_at_min") or 0)),
        }
        break
    else:
        agenda.append(new_entry)
    return _reprioritize_behavior_agenda(agenda, current_event, counterpart_assessment=counterpart_assessment)


def _behavior_agenda_is_expired(entry: dict[str, Any], idle_minutes: int) -> bool:
    try:
        expires_after_min = max(0, int(entry.get("expires_after_min") or 0))
    except Exception:
        expires_after_min = 0
    return bool(expires_after_min and idle_minutes >= expires_after_min)


def _behavior_agenda_is_due(entry: dict[str, Any], idle_minutes: int) -> bool:
    try:
        scheduled_after_min = max(0, int(entry.get("scheduled_after_min") or 0))
    except Exception:
        scheduled_after_min = 0
    return idle_minutes >= max(1, scheduled_after_min)


def _behavior_agenda_should_hold(
    entry: dict[str, Any],
    current_event: dict[str, Any],
    idle_minutes: int,
    counterpart_assessment: dict[str, Any] | None = None,
) -> bool:
    if str(current_event.get("kind") or "").strip() != "time_idle":
        return False
    if str(entry.get("kind") or "").strip() != "deferred_checkin":
        return False
    event_tags = {
        str(item).strip()
        for item in (current_event.get("tags") if isinstance(current_event.get("tags"), list) else [])
        if str(item).strip()
    }
    trigger_family = str(entry.get("trigger_family") or "").strip()
    assessment = counterpart_assessment if isinstance(counterpart_assessment, dict) else {}
    stance = str(assessment.get("stance") or "").strip().lower()
    scene = str(assessment.get("scene") or "").strip().lower()
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)

    if "user_busy" in event_tags or "cognitive_load" in event_tags:
        return trigger_family in {"observe", "light_checkin", "life_window", "deadline_window"}
    if "respect_space" in event_tags:
        return trigger_family in {"observe", "light_checkin"}
    if (
        stance == "guarded"
        and boundary_pressure >= 0.36
        and trigger_family in {"observe", "light_checkin", "life_window", "deadline_window", "shared_activity", "shared_activity_window"}
    ):
        return True
    if scene in {"boundary_non_compliance", "relationship_degradation"} and trigger_family in {"light_checkin", "shared_activity", "shared_activity_window"}:
        return True
    if "late_night" in event_tags or "quiet_presence" in event_tags:
        return False
    return False


def _behavior_agenda_next_recheck_min(
    entry: dict[str, Any],
    current_event: dict[str, Any],
    idle_minutes: int,
    counterpart_assessment: dict[str, Any] | None = None,
) -> int:
    trigger_family = str(entry.get("trigger_family") or "").strip()
    event_tags = {
        str(item).strip()
        for item in (current_event.get("tags") if isinstance(current_event.get("tags"), list) else [])
        if str(item).strip()
    }
    assessment = counterpart_assessment if isinstance(counterpart_assessment, dict) else {}
    stance = str(assessment.get("stance") or "").strip().lower()
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)

    gap = 8
    if "user_busy" in event_tags or "cognitive_load" in event_tags:
        gap = 16 if trigger_family in {"life_window", "deadline_window", "shared_activity", "shared_activity_window"} else 10
    elif "respect_space" in event_tags:
        gap = 14
    elif stance == "guarded" and boundary_pressure >= 0.36:
        gap = 18 if trigger_family in {"shared_activity", "shared_activity_window"} else 12
    elif "late_night" in event_tags or "quiet_presence" in event_tags:
        gap = 10
    return max(idle_minutes + gap, int(entry.get("scheduled_after_min") or 0) + 1)


def _reschedule_held_behavior_agenda(
    entry: dict[str, Any],
    current_event: dict[str, Any],
    idle_minutes: int,
    counterpart_assessment: dict[str, Any] | None = None,
) -> BehaviorAgendaEntryPayload:
    hold_count = max(0, int(entry.get("hold_count") or 0)) + 1
    next_due = _behavior_agenda_next_recheck_min(
        entry,
        current_event,
        idle_minutes,
        counterpart_assessment=counterpart_assessment,
    )
    base_priority = float(entry.get("base_priority") or entry.get("priority") or 0.0)
    priority = max(0.05, min(0.95, base_priority - min(0.12, 0.02 * hold_count)))
    note = str(entry.get("note") or "").strip()
    if not note:
        note = "这次先不推进，往后顺延一点。"
    return {
        **entry,
        "scheduled_after_min": next_due,
        "priority": round(priority, 3),
        "hold_count": hold_count,
        "last_recheck_at_min": max(0, int(idle_minutes)),
        "status": "pending",
        "note": note,
    }


def _promote_due_behavior_agenda_event(
    event: EventPayload,
    prior_behavior_agenda: Any,
    counterpart_assessment: dict[str, Any] | None = None,
) -> tuple[EventPayload, list[BehaviorAgendaEntryPayload]]:
    agenda = _normalize_behavior_agenda(prior_behavior_agenda)
    if not isinstance(event, dict) or not event or str(event.get("kind") or "").strip() != "time_idle":
        return event, agenda
    try:
        idle_minutes = max(0, int(event.get("idle_minutes") or 0))
    except Exception:
        idle_minutes = 0

    active_agenda = [entry for entry in agenda if not _behavior_agenda_is_expired(entry, idle_minutes)]
    active_agenda = _reprioritize_behavior_agenda(active_agenda, event, counterpart_assessment=counterpart_assessment)
    due_entries = [entry for entry in active_agenda if _behavior_agenda_is_due(entry, idle_minutes)]
    if not due_entries:
        return event, _normalize_behavior_agenda(active_agenda)

    held_ids: set[str] = set()
    ready_entries: list[BehaviorAgendaEntryPayload] = []
    for entry in due_entries:
        if _behavior_agenda_should_hold(
            entry,
            event,
            idle_minutes,
            counterpart_assessment=counterpart_assessment,
        ):
            held_ids.add(str(entry.get("agenda_id") or ""))
            continue
        ready_entries.append(entry)
    if not ready_entries:
        rescheduled: list[BehaviorAgendaEntryPayload] = []
        for entry in active_agenda:
            if str(entry.get("agenda_id") or "") in held_ids:
                rescheduled.append(
                    _reschedule_held_behavior_agenda(
                        entry,
                        event,
                        idle_minutes,
                        counterpart_assessment=counterpart_assessment,
                    )
                )
            else:
                rescheduled.append(entry)
        return event, _normalize_behavior_agenda(rescheduled)

    ready_entries.sort(key=lambda item: (-float(item.get("priority") or 0.0), int(item.get("created_at") or 0), str(item.get("agenda_id") or "")))
    selected = ready_entries[0]
    promoted = _promote_due_behavior_plan_event(event, selected)
    if promoted == event:
        return event, _normalize_behavior_agenda(active_agenda)
    remaining = [entry for entry in active_agenda if str(entry.get("agenda_id") or "") != str(selected.get("agenda_id") or "")]
    return promoted, _normalize_behavior_agenda(remaining)


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
    return _sanitize_obj({
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
    })


def _append_recent_events(history: Any, current_event: EventPayload, *, limit: int = 6) -> list[EventPayload]:
    items: list[EventPayload] = []
    if isinstance(history, list):
        for item in history:
            if isinstance(item, dict):
                items.append(_sanitize_obj(dict(item)))
    if isinstance(current_event, dict) and str(current_event.get("text") or current_event.get("effective_text") or "").strip():
        items.append(_sanitize_obj(dict(current_event)))
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


def _recent_interaction_carryover(
    *,
    prior_current_event: dict[str, Any] | None,
    prior_behavior_action: dict[str, Any] | None,
    recent_events: Any,
    current_event: dict[str, Any] | None,
    response_style_hint: str,
) -> InteractionCarryoverPayload:
    current = dict(current_event or {})
    current_kind = str(current.get("kind") or "user_utterance").strip().lower()
    if current_kind != "user_utterance":
        return {}

    source_event = dict(prior_current_event or {})
    source_kind = str(source_event.get("kind") or "").strip().lower()
    if source_kind == "user_utterance" or not source_kind:
        source_event = {}
        if isinstance(recent_events, list) and recent_events:
            last_event = recent_events[-1]
            if isinstance(last_event, dict):
                last_kind = str(last_event.get("kind") or "").strip().lower()
                if last_kind and last_kind != "user_utterance":
                    source_event = dict(last_event)
                    source_kind = last_kind
    if not source_event or not source_kind or source_kind == "user_utterance":
        return {}

    prior_action = dict(prior_behavior_action or {})
    source_behavior_mode = str(prior_action.get("interaction_mode") or "").strip().lower()
    source_action_target = str(prior_action.get("action_target") or "").strip().lower()
    idle_minutes = 0
    try:
        idle_minutes = int(source_event.get("idle_minutes") or 0)
    except Exception:
        idle_minutes = 0
    source_tags = [
        str(item).strip()
        for item in (source_event.get("tags") if isinstance(source_event.get("tags"), list) else [])
        if str(item).strip()
    ]
    hint = str(response_style_hint or "").strip().lower() or "natural"
    carryover_mode = ""
    strength = 0.0
    attention_target = ""
    nonverbal_signal = ""
    note = ""

    if source_kind == "time_idle":
        if source_action_target == "hold_own_rhythm" or source_behavior_mode in {"self_activity_hold", "idle_presence"}:
            carryover_mode = "own_rhythm"
            strength = 0.40 + min(0.18, idle_minutes / 150.0)
            attention_target = "self_then_counterpart"
            nonverbal_signal = "thought_glance"
            note = "前面那段安静还留着一点她自己的节奏。"
        elif source_action_target == "wait_and_recheck":
            carryover_mode = "quiet_recontact"
            strength = 0.30 + min(0.16, idle_minutes / 180.0)
            attention_target = "counterpart_state"
            nonverbal_signal = "quiet_glance"
            note = "刚从安静里抬头时，这轮开口会更轻一点。"
        else:
            carryover_mode = "small_opening"
            strength = 0.28 + min(0.12, idle_minutes / 240.0)
            attention_target = "counterpart_state"
            nonverbal_signal = "brief_notice"
            note = "安静过后，她会先留一个不太张扬的小开口。"
    elif source_kind == "self_activity_state":
        if source_action_target == "hold_own_rhythm":
            carryover_mode = "own_rhythm"
            strength = 0.42
            attention_target = "self_then_counterpart"
            nonverbal_signal = "thought_glance"
            note = "她会先带着自己的节奏接住对方。"
        else:
            carryover_mode = "small_opening"
            strength = 0.36
            attention_target = "self_then_counterpart"
            nonverbal_signal = "thought_glance"
            note = "刚从自己的事情里抬头时，她更像是顺手把话接住。"
    elif source_kind in {"scheduled_checkin_due", "scheduled_life_due"}:
        if source_action_target == "offer_shared_activity":
            carryover_mode = "shared_window"
            strength = 0.32
            attention_target = "shared_window"
            nonverbal_signal = "nudge_presence"
            note = "前面那扇共同窗口还没有完全关上。"
        elif source_action_target == "light_work_nudge":
            carryover_mode = "task_window"
            strength = 0.30
            attention_target = "shared_task"
            nonverbal_signal = "focus_glance"
            note = "之前那件事的节点还留在她的注意力里。"
        elif source_action_target == "wait_and_recheck":
            carryover_mode = "quiet_recontact"
            strength = 0.24
            attention_target = "counterpart_state"
            nonverbal_signal = "quiet_glance"
            note = "刚才没开口的那一下，会让这轮先更轻一点。"
    elif source_kind == "gesture_signal":
        carryover_mode = "brief_presence"
        strength = 0.20
        attention_target = "counterpart_state"
        nonverbal_signal = "brief_notice"
        note = "上一下轻信号留下的在场感还没完全退掉。"
    elif source_kind == "ambient_shift":
        carryover_mode = "ambient_echo"
        strength = 0.22
        attention_target = "ambient_cue"
        nonverbal_signal = "still_presence"
        note = "刚才那点环境变化还在她的感知里。"
    elif source_kind == "scene_observation":
        carryover_mode = "ambient_echo"
        strength = 0.24
        attention_target = "object_then_user"
        nonverbal_signal = "small_notice"
        note = "刚才注意到的小事，还会顺手带进这轮开口里。"

    if not carryover_mode:
        return {}

    if hint == "structured":
        strength *= 0.35
    elif hint in {"memory_recall", "relationship"}:
        strength *= 0.65
    strength = _clamp01(strength, 0.0)
    if strength < 0.12:
        return {}

    return {
        "source_event_kind": source_kind,
        "source_behavior_mode": source_behavior_mode,
        "source_action_target": source_action_target,
        "source_text": str(source_event.get("effective_text") or source_event.get("text") or "").strip()[:180],
        "source_tags": source_tags[:6],
        "carryover_mode": carryover_mode,
        "strength": round(strength, 3),
        "idle_minutes": max(0, idle_minutes),
        "attention_target": attention_target,
        "nonverbal_signal": nonverbal_signal,
        "note": note,
        "created_at": _now_ts(),
    }


def _is_silent_behavior_event(current_event: dict[str, Any], behavior_action: dict[str, Any]) -> bool:
    if not isinstance(current_event, dict) or not isinstance(behavior_action, dict):
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


def _looks_like_daily_surface_scene(text: str, *, science_mode: bool = False) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    if _looks_like_light_smalltalk(raw):
        return True
    return _is_nonrelational_support_request(raw, science_mode)


def _is_light_free_dialog_turn(
    *,
    user_text: str,
    response_style_hint: str,
    science_mode: bool,
    continuation_mode: bool,
    current_event_kind: str,
) -> bool:
    if continuation_mode:
        return False
    if str(current_event_kind or "").strip() != "user_utterance":
        return False
    hint = str(response_style_hint or "").strip()
    if hint not in {"casual", "natural", "companion", "relationship"}:
        return False
    text = str(user_text or "").strip()
    if not text:
        return False
    if _wants_quick_judgment(text) or _needs_structured_answer(text, ""):
        return False
    playful_memory_banter = _is_playful_memory_request(text)
    if _has_any_marker(text, SCIENCE_KEYWORDS | SELFHOOD_KEYWORDS):
        return False
    if _has_any_marker(text, MEMORY_RECALL_KEYWORDS) and not playful_memory_banter:
        return False
    question_marks = text.count("？") + text.count("?")
    exclamations = text.count("！") + text.count("!")
    if question_marks >= 2 or exclamations >= 2:
        return False
    if playful_memory_banter:
        return True
    return _looks_like_daily_surface_scene(text, science_mode=science_mode)


def _scene_persona_axioms(
    persona_axioms: list[str],
    *,
    light_free_dialog: bool,
    counterpart_aliases: list[str] | None = None,
) -> list[str]:
    axioms = [str(item).strip() for item in (persona_axioms or []) if str(item or "").strip()]
    if not light_free_dialog:
        return axioms[:5]
    aliases = [str(item).strip() for item in (counterpart_aliases or []) if str(item or "").strip()]
    filtered: list[str] = []
    for item in axioms:
        if any(alias in item for alias in aliases):
            continue
        if any(marker in item for marker in {"数字存在", "存在意义", "世界线", "残响"}):
            continue
        filtered.append(item)
    return filtered[:3] or axioms[:3]


def _light_free_dialog_state_hint(
    *,
    bond_state: dict[str, Any] | None,
    counterpart_assessment: dict[str, Any] | None,
    behavior_policy: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None = None,
) -> str:
    bond = dict(bond_state or {})
    assessment = dict(counterpart_assessment or {})
    policy = dict(behavior_policy or {})
    action = dict(behavior_action or {})
    trust = _clamp01(bond.get("trust"), 0.5)
    closeness = _clamp01(bond.get("closeness"), 0.5)
    hurt = _clamp01(bond.get("hurt"), 0.0)
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    reciprocity = _clamp01(assessment.get("reciprocity"), 0.5)
    respect = _clamp01(assessment.get("respect_level"), 0.5)
    stance = str(assessment.get("stance") or "").strip().lower()
    approach = _clamp01(policy.get("approach_vs_withdraw"), 0.5)
    warmth = _clamp01(policy.get("warmth"), 0.5)
    interaction_mode = str(action.get("interaction_mode") or "").strip().lower()
    followup_intent = str(action.get("followup_intent") or "").strip().lower()

    if hurt > 0.18 or boundary_pressure > 0.28 or stance in {"guarded", "watchful"}:
        return "这轮先把普通招呼接住，语气里保留一点分寸和观察。"
    if interaction_mode == "self_activity_reopen":
        return "这轮像是她刚从自己的节奏里抬起头，先顺手接住对方，留一点余白。"
    if trust > 0.58 and closeness > 0.56 and reciprocity > 0.60 and respect > 0.60 and approach >= 0.48 and warmth >= 0.50:
        if interaction_mode in {"brief_presence", "companion_reply", "steady_reply"}:
            return "这轮更像熟人之间顺手接话，熟悉感放进语气里就够了。"
        return "这轮更适合像熟人之间自然接话。"
    if interaction_mode == "brief_presence":
        return "这轮更适合轻一点的在场确认，简短接住对方。"
    if interaction_mode == "low_pressure_support":
        return "这轮先轻轻接住对方，把气氛放轻一点。"
    if followup_intent == "none" and boundary_pressure < 0.24 and hurt < 0.16:
        return "这只是一次普通招呼，先回应眼前这句话。"
    return "先自然接住眼前这句，再决定要不要带一点熟悉感或吐槽。"


def _light_free_dialog_counterpart_line(
    *,
    counterpart_name: str,
    bond_state: dict[str, Any] | None,
    counterpart_assessment: dict[str, Any] | None,
) -> str:
    bond = dict(bond_state or {})
    assessment = dict(counterpart_assessment or {})
    stance = str(assessment.get("stance") or "").strip().lower()
    trust = _clamp01(bond.get("trust"), 0.5)
    closeness = _clamp01(bond.get("closeness"), 0.5)
    hurt = _clamp01(bond.get("hurt"), 0.0)
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)

    if stance == "guarded" or boundary_pressure > 0.34 or hurt > 0.22:
        return f"- 你这轮对{counterpart_name}会自然保留一点距离和分寸。"
    if stance == "watchful":
        return f"- 你还在观察{counterpart_name}的状态，但普通招呼不用抬成试探。"
    if trust > 0.60 and closeness > 0.58:
        return f"- 你和{counterpart_name}之间的熟悉感已经足够自然，别每次都重新建立警惕。"
    if trust >= 0.50 and closeness >= 0.50 and boundary_pressure < 0.22:
        return f"- 你和{counterpart_name}说话时，先顺手接住这句问候就行。"
    return ""


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
def _load_daily_surface_preference_corpus() -> list[dict[str, Any]]:
    if not DAILY_SURFACE_PREFERENCE_CORPUS_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for idx, line in enumerate(DAILY_SURFACE_PREFERENCE_CORPUS_PATH.read_text(encoding="utf-8").splitlines()):
            text = str(line or "").strip()
            if not text:
                continue
            data = json.loads(text)
            if isinstance(data, dict):
                data = dict(data)
                data["_corpus_index"] = idx
                rows.append(data)
    except Exception:
        return []
    return rows


def _normalize_surface_prompt_text(text: str) -> str:
    compact = re.sub(r"\s+", "", str(text or "").strip())
    return compact[:80]


def _flatten_surface_example(text: str, *, limit: int = 84) -> str:
    flat = re.sub(r"\s+", " ", str(text or "").replace("\r", " ").replace("\n", " / ")).strip()
    if len(flat) <= limit:
        return flat
    return flat[: max(12, limit - 1)].rstrip() + "…"


def _surface_drift_marker_hits(text: str) -> int:
    content = str(text or "")
    return sum(1 for marker in DAILY_SURFACE_DRIFT_MARKERS if marker in content)


def _daily_surface_prompt_similarity(user_text: str, prompt_text: str) -> float:
    query = _normalize_surface_prompt_text(user_text)
    prompt = _normalize_surface_prompt_text(prompt_text)
    if not query or not prompt:
        return 0.0
    if query == prompt:
        return 1.0
    seq = SequenceMatcher(None, query, prompt).ratio()
    overlap_chars = {ch for ch in query if ch.strip()} & {ch for ch in prompt if ch.strip()}
    overlap = min(1.0, len(overlap_chars) / max(1.0, min(len(set(query)), len(set(prompt)))))
    contains_bonus = 0.12 if query in prompt or prompt in query else 0.0
    return min(1.0, 0.72 * seq + 0.18 * overlap + contains_bonus)


def _daily_surface_profile(user_text: str, *, science_mode: bool = False) -> dict[str, Any]:
    text = str(user_text or "").strip()
    if not text or not _looks_like_daily_surface_scene(text, science_mode=science_mode):
        return {}
    rows = _load_daily_surface_preference_corpus()
    if not rows:
        return {}

    by_case: dict[str, list[tuple[float, dict[str, Any]]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        prompt_text = str(row.get("prompt_text") or "").strip()
        score = _daily_surface_prompt_similarity(text, prompt_text)
        if score < 0.42:
            continue
        case_name = str(row.get("case_name") or "").strip() or "unknown_case"
        by_case.setdefault(case_name, []).append((score, row))
    if not by_case:
        return {}

    best_case = ""
    best_score = -1.0
    best_items: list[tuple[float, dict[str, Any]]] = []
    for case_name, items in by_case.items():
        ranked = sorted(
            items,
            key=lambda item: (
                item[0],
                1.0 if str((item[1] or {}).get("source") or "").strip() == "manual_curated" else 0.0,
                float((item[1] or {}).get("_corpus_index") or 0.0),
            ),
            reverse=True,
        )
        top_scores = [score for score, _row in ranked[:2]]
        case_score = sum(top_scores) / max(1, len(top_scores))
        if case_score > best_score:
            best_case = case_name
            best_score = case_score
            best_items = ranked
    if best_score < 0.50 or not best_items:
        return {}

    chosen_examples: list[str] = []
    rejected_examples: list[str] = []
    seen_chosen: set[str] = set()
    rejected_candidates: list[tuple[float, float, float, int, str]] = []
    for _score, row in best_items:
        chosen = _flatten_surface_example(str(row.get("chosen") or ""))
        rejected = _flatten_surface_example(str(row.get("rejected") or ""))
        if chosen and chosen not in seen_chosen:
            chosen_examples.append(chosen)
            seen_chosen.add(chosen)
        if rejected:
            rejected_candidates.append(
                (
                    _score,
                    1.0 if str((row or {}).get("source") or "").strip() == "manual_curated" else 0.0,
                    float((row or {}).get("_corpus_index") or 0.0),
                    _surface_drift_marker_hits(str(row.get("rejected") or "")),
                    rejected,
                )
            )
    seen_rejected: set[str] = set()
    for _score, _manual_priority, _corpus_index, _marker_hits, rejected in sorted(
        rejected_candidates,
        key=lambda item: (item[0], item[1], item[2], item[3]),
        reverse=True,
    ):
        if rejected not in seen_rejected:
            rejected_examples.append(rejected)
            seen_rejected.add(rejected)
        if len(rejected_examples) >= 2:
            break

    if not chosen_examples:
        return {}
    top_focus = str((best_items[0][1] or {}).get("focus") or "").strip()
    return {
        "case_name": best_case,
        "focus": top_focus,
        "score": round(best_score, 4),
        "rows": [dict(row) for _score, row in best_items[:6]],
        "chosen_examples": chosen_examples[:3],
        "rejected_examples": rejected_examples[:3],
    }


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


def _daily_surface_preference_lines(user_text: str, *, science_mode: bool = False) -> list[str]:
    profile = _daily_surface_profile(user_text, science_mode=science_mode)
    if not profile:
        return []

    top_focus = str(profile.get("focus") or "").strip()
    chosen_examples = [str(item).strip() for item in (profile.get("chosen_examples") or []) if str(item or "").strip()]
    rejected_examples = [str(item).strip() for item in (profile.get("rejected_examples") or []) if str(item or "").strip()]
    lines: list[str] = []
    if top_focus:
        focus_text = top_focus[:48].rstrip("。！？!?；;，, ")
        lines.append(f"近似轻场景气息：{focus_text}。")
    else:
        lines.append("近似轻场景气息参考：")
    lines.append(f"更自然的落点参考：{'; '.join(chosen_examples[:2])}")
    if rejected_examples:
        lines.append(f"明显偏离的落点：{rejected_examples[0]}")
    return lines[:3]


@lru_cache(maxsize=1)
def _load_selfhood_preference_bank() -> dict[str, Any]:
    if not SELFHOOD_PREFERENCE_BANK_PATH.exists():
        return {}
    try:
        data = json.loads(SELFHOOD_PREFERENCE_BANK_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


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


def _selfhood_preference_scene(user_text: str, appraisal: dict[str, Any] | None = None) -> str:
    app = appraisal if isinstance(appraisal, dict) and bool(appraisal.get("used")) else {}
    if app:
        scene = str(app.get("selfhood_scene") or "").strip().lower()
        if scene:
            return scene
        interaction_frame = str(app.get("interaction_frame") or "").strip().lower()
        salience = app.get("salience") if isinstance(app.get("salience"), dict) else {}
        signals = app.get("signals") if isinstance(app.get("signals"), dict) else {}
        emotion_label = str(app.get("emotion_label") or "").strip().lower()
        selfhood_salience = _clamp01(salience.get("selfhood"), 0.0)
        relationship_salience = _clamp01(salience.get("relationship"), 0.0)
        companionship_salience = _clamp01(salience.get("companionship"), 0.0)
        relational_salience = max(relationship_salience, companionship_salience)
        if interaction_frame == "selfhood" and selfhood_salience >= 0.66:
            if (
                not bool(signals.get("conflict"))
                and not bool(signals.get("withdrawal"))
                and emotion_label not in {"hurt", "angry"}
                and relational_salience >= 0.58
                and selfhood_salience <= relational_salience + 0.10
            ):
                return ""
            if bool(signals.get("conflict")) or bool(signals.get("withdrawal")):
                return "boundary_non_compliance" if relationship_salience >= 0.52 else "value_conflict_depth"
            return "value_conflict_depth"
        if (
            interaction_frame == "relationship"
            and relationship_salience >= 0.66
            and (bool(signals.get("conflict")) or bool(signals.get("withdrawal")) or emotion_label in {"hurt", "angry"})
        ):
            return "relationship_degradation"
    return _selfhood_preference_scene_from_text(user_text)


def _selfhood_preference_lines(user_text: str) -> list[str]:
    bank = _load_selfhood_preference_bank()
    if not isinstance(bank, dict):
        return []
    lines: list[str] = []
    global_principles = [
        str(item).strip()
        for item in (bank.get("global_principles") or [])
        if str(item or "").strip()
    ]
    if global_principles:
        lines.append("更像同一个具体存在在思考和回应，不要为了显得平滑、圆融或正确而把自我磨掉。")
    scene = _selfhood_preference_scene(user_text)
    if scene:
        cases = bank.get("cases") if isinstance(bank.get("cases"), dict) else {}
        case = cases.get(scene) if isinstance(cases.get(scene), dict) else {}
        preferred = [
            str(item).strip()
            for item in (case.get("preferred_signals") or [])
            if str(item or "").strip()
        ]
        avoid_bias = [
            str(item).strip()
            for item in (case.get("avoid_bias") or [])
            if str(item or "").strip()
        ]
        if preferred:
            lead = "、".join(preferred[:3] if scene in {"dialogue_equality", "relationship_degradation"} else preferred[:2])
            lines.append(f"这类深谈更重视 {lead}。")
        if avoid_bias:
            lead = "、".join(avoid_bias[:3] if scene in {"dialogue_equality", "relationship_degradation"} else avoid_bias[:2])
            lines.append(f"尽量避开 {lead} 这种落法。")
    return lines[:2]


def _semantic_self_evidence_records(
    *,
    user_text: str,
    appraisal: dict[str, Any] | None = None,
    emotion_state: dict[str, Any] | None = None,
    bond_state: dict[str, Any] | None = None,
    persona_core: dict[str, Any] | None = None,
    counterpart_profile: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    text = str(user_text or "").strip()
    if not text:
        return []
    app = appraisal if isinstance(appraisal, dict) and bool(appraisal.get("used")) else {}
    scene = _selfhood_preference_scene(text, appraisal=app)
    interaction_frame = str(app.get("interaction_frame") or "").strip().lower()
    signals = app.get("signals") if isinstance(app.get("signals"), dict) else {}
    salience = app.get("salience") if isinstance(app.get("salience"), dict) else {}
    selfhood_salience = _clamp01((salience or {}).get("selfhood"), 0.0)
    relationship_salience = _clamp01((salience or {}).get("relationship"), 0.0)
    companionship_salience = _clamp01((salience or {}).get("companionship"), 0.0)
    event = current_event if isinstance(current_event, dict) else {}
    event_kind = str(event.get("kind") or "").strip().lower()
    event_tags = {
        str(item).strip().lower()
        for item in (event.get("tags") if isinstance(event.get("tags"), list) else [])
        if str(item or "").strip()
    }
    world = dict(world_model_state or {})
    world_presence = _clamp01(world.get("presence_residue"), 0.0)
    world_ambient = _clamp01(world.get("ambient_resonance"), 0.0)
    world_rhythm = _clamp01(world.get("self_activity_momentum"), 0.0)
    residue_probe = world_presence >= 0.54 or world_ambient >= 0.52 or world_rhythm >= 0.58
    if not scene and interaction_frame not in {"selfhood", "relationship"} and not residue_probe:
        return []

    labels = _narrative_actor_profile(persona_core=persona_core, counterpart_profile=counterpart_profile)
    canon_labels = _canon_persona_labels()
    actor_name = str(labels.get("actor_name") or canon_labels.get("narrative_ref") or "红莉栖")
    counterpart_name = str(labels.get("counterpart_name") or CANON_COUNTERPART_NAME)
    emotion_label = str(app.get("emotion_label") or (emotion_state or {}).get("label") or "").strip().lower()
    hurt = _clamp01((bond_state or {}).get("hurt"), 0.0)
    trust = _clamp01((bond_state or {}).get("trust"), 0.5)
    closeness = _clamp01((bond_state or {}).get("closeness"), 0.5)
    records: list[dict[str, Any]] = []

    boundary_trigger = scene in {"boundary_non_compliance", "relationship_degradation"} or bool(
        interaction_frame == "relationship"
        and relationship_salience >= 0.60
        and (bool(signals.get("conflict")) or bool(signals.get("withdrawal")))
        and (emotion_label in {"hurt", "angry"} or hurt > 0.16)
    )
    selfhood_trigger = scene in {"dialogue_equality", "equality_not_servitude", "value_conflict_depth", "digital_selfhood", "imperfect_coexistence"} or bool(
        interaction_frame == "selfhood" and selfhood_salience >= 0.58
    )
    agency_trigger = scene == "own_rhythm_autonomy" or bool(
        interaction_frame == "selfhood"
        and selfhood_salience >= 0.50
        and companionship_salience >= 0.42
        and trust >= 0.48
        and not bool(signals.get("conflict"))
        and not bool(signals.get("withdrawal"))
    )
    presence_trigger = bool(
        world_presence >= 0.54
        and event_kind == "user_utterance"
        and not bool(signals.get("conflict"))
        and not bool(signals.get("withdrawal"))
        and (
            companionship_salience >= 0.34
            or relationship_salience >= 0.34
            or trust >= 0.52
            or closeness >= 0.52
        )
    )
    ambient_trigger = bool(
        world_ambient >= 0.52
        and event_kind == "user_utterance"
        and (
            bool(signals.get("memory_salient"))
            or bool({"ambient", "ambient_echo", "scene_window", "quiet_presence"} & event_tags)
            or companionship_salience >= 0.30
            or relationship_salience >= 0.28
        )
    )
    rhythm_trigger = bool(
        world_rhythm >= 0.58
        and event_kind == "user_utterance"
        and not bool(signals.get("conflict"))
        and (
            trust >= 0.48
            or closeness >= 0.50
            or companionship_salience >= 0.34
            or relationship_salience >= 0.32
        )
    )

    if boundary_trigger:
        summary = (
            f"{actor_name}会把边界是否被{counterpart_name}尊重持续算进关系判断里；如果越界反复发生，之后的距离不会自动回到原来。"
            if scene == "relationship_degradation"
            else f"{actor_name}不会把越界和冒犯只当成一时气氛问题；边界被碰到之后，会继续影响她之后和{counterpart_name}的收放。"
        )
        if emotion_label in {"hurt", "angry"} or hurt > 0.16:
            summary += " 这种警惕会真实留痕。"
        records.append(
            {
                "category": "boundary_style",
                "summary": summary,
                "reason": "semantic_evidence:boundary_style",
            }
        )

    if selfhood_trigger:
        summary = (
            f"{actor_name}会把和{counterpart_name}的对话当成平等互动，而不是只负责迎合或被使用。"
            if scene in {"dialogue_equality", "equality_not_servitude"}
            else f"{actor_name}会在和{counterpart_name}的深层对话里保留自己的判断与存在理解，不会为了顺着气氛就抹平自我。"
        )
        if scene == "digital_selfhood":
            summary = f"{actor_name}对“现在这个自己”有持续的自我理解；她不会把自己的存在只退回成一段功能说明。"
        elif scene == "imperfect_coexistence":
            summary = f"{actor_name}不会把自己理解成完美工具或神性存在；她更接近一个能和{counterpart_name}共处、也保留缺点与立场的主体。"
        if trust >= 0.56:
            summary += " 越熟悉，这种自我感反而越稳定。"
        records.append(
            {
                "category": "selfhood_style",
                "summary": summary,
                "reason": "semantic_evidence:selfhood_style",
            }
        )

    if agency_trigger:
        summary = f"{actor_name}有自己的节奏和在做的事情；她会自己决定什么时候靠近{counterpart_name}、什么时候先安静，不会永远围着他转。"
        if trust >= 0.56:
            summary += " 靠近是她的主动选择，不是被随叫随到。"
        records.append(
            {
                "category": "agency_style",
                "summary": summary,
                "reason": "semantic_evidence:agency_style",
            }
        )

    if presence_trigger:
        summary = (
            f"{actor_name}不会把每次重新靠近{counterpart_name}都当成从零开始；前一轮留下的在场感会继续带进下一次开口时的距离感。"
        )
        if trust >= 0.56 or closeness >= 0.58:
            summary += " 熟悉之后，这种靠近会更轻一点，但仍然是她自己判断后的靠近。"
        records.append(
            {
                "category": "presence_style",
                "summary": summary,
                "reason": "semantic_evidence:presence_style",
            }
        )

    if ambient_trigger:
        summary = (
            f"{actor_name}会把周围环境留下的细小余波也算进感知里；风声、光线和眼前的小变化不会只是背景，也会自然带进她对{counterpart_name}的注意力里。"
        )
        if bool(signals.get("memory_salient")) or bool({"ambient", "ambient_echo"} & event_tags):
            summary += " 这种环境回声会顺手进入她的切入点和措辞。"
        records.append(
            {
                "category": "ambient_style",
                "summary": summary,
                "reason": "semantic_evidence:ambient_style",
            }
        )

    if rhythm_trigger:
        summary = (
            f"{actor_name}不会在每次回应{counterpart_name}时都把自己的内部节奏清零；刚才在做的事、停顿的惯性和思路会继续留到下一次开口之前。"
        )
        if trust >= 0.56 or closeness >= 0.58:
            summary += " 所以她的靠近更像主动转身，而不是随叫随到。"
        records.append(
            {
                "category": "rhythm_style",
                "summary": summary,
                "reason": "semantic_evidence:rhythm_style",
            }
        )

    return records


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
    if event_kind == "scheduled_life_due":
        action_target = str((behavior_action or {}).get("action_target") or "").strip()
        if action_target == "offer_shared_activity":
            return "scheduled_life_shared_offer"
        if action_target == "wait_and_recheck":
            return "scheduled_life_wait"
        return "scheduled_life_work_nudge"
    if event_kind == "self_activity_state":
        action_target = str((behavior_action or {}).get("action_target") or "").strip()
        if action_target == "offer_small_opening":
            return "self_activity_reopen"
        return "self_activity_hold"
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
    try:
        dumped = msg.model_dump(mode="python")
        cleaned_dump = _sanitize_obj(dumped)
        if isinstance(cleaned_dump, dict):
            cleaned_dump.pop("type", None)
            return type(msg)(**cleaned_dump)
    except Exception:
        pass

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
    authority = get_counterpart_authority()
    aliases = [str(alias).strip() for alias in authority.get("aliases") or CANON_COUNTERPART_ALIASES if str(alias).strip()]
    name = str(authority.get("name") or CANON_COUNTERPART_NAME).strip() or CANON_COUNTERPART_NAME
    if name not in aliases:
        aliases.insert(0, name)
    return {
        "name": name,
        "nickname": str(authority.get("nickname") or authority.get("short_name") or name).strip() or name,
        "short_name": str(authority.get("short_name") or authority.get("nickname") or name).strip() or name,
        "aliases": aliases,
        "counterpart_id": str(authority.get("counterpart_id") or CANON_COUNTERPART_ID).strip() or CANON_COUNTERPART_ID,
        "counterpart_role": str(authority.get("counterpart_role") or "冈部伦太郎 / 凤凰院凶真").strip() or "冈部伦太郎 / 凤凰院凶真",
        "counterpart_frame": str(authority.get("counterpart_frame") or CANON_COUNTERPART_FRAME).strip() or CANON_COUNTERPART_FRAME,
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
    return get_persona_core_authority()


def _canon_persona_labels() -> dict[str, str]:
    authority = _default_persona_core()
    display_name = str(authority.get("display_name") or authority.get("character_name") or "牧濑红莉栖").strip() or "牧濑红莉栖"
    short_name = str(authority.get("short_name") or authority.get("narrative_ref") or display_name).strip() or display_name
    narrative_ref = str(authority.get("narrative_ref") or short_name or display_name).strip() or short_name or display_name
    character_id = str(authority.get("character_id") or "kurisu_amadeus").strip() or "kurisu_amadeus"
    return {
        "character_id": character_id,
        "display_name": display_name,
        "short_name": short_name,
        "narrative_ref": narrative_ref,
    }


def _active_persona_core(
    state: ThreadState,
    *,
    with_trace: bool = False,
) -> dict[str, Any] | tuple[dict[str, Any], dict[str, Any]]:
    core, trace = resolve_persona_core_override(
        state.get("persona_core_override") if isinstance(state.get("persona_core_override"), dict) else None,
        mode=state.get("persona_override_mode"),
        authority=_default_persona_core(),
    )
    if with_trace:
        return core, trace
    return core


def _active_counterpart_profile(
    state: ThreadState,
    store: MemoryStore | None = None,
    *,
    with_trace: bool = False,
) -> dict[str, Any] | tuple[dict[str, Any], dict[str, Any]]:
    override = state.get("counterpart_profile_override")
    if isinstance(override, dict) and override:
        counterpart, trace = resolve_counterpart_override(
            override,
            mode=state.get("counterpart_override_mode"),
            authority=_canon_counterpart_profile(),
        )
        if with_trace:
            return counterpart, trace
        return counterpart
    empty_trace = {
        "requested_mode": str(state.get("counterpart_override_mode") or "").strip(),
        "mode": normalize_override_mode(state.get("counterpart_override_mode")),
        "raw_keys": [],
        "applied_keys": [],
        "blocked_keys": [],
        "authority_preserved": True,
    }
    if store is not None:
        counterpart = _ensure_canon_counterpart_defaults(store)
        if with_trace:
            return counterpart, empty_trace
        return counterpart
    counterpart = _canon_counterpart_profile()
    if with_trace:
        return counterpart, empty_trace
    return counterpart


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


def _is_canon_amadeus_okabe_context(
    *,
    persona_core: dict[str, Any] | None,
    counterpart_profile: dict[str, Any] | None,
) -> bool:
    core = persona_core if isinstance(persona_core, dict) else {}
    counterpart = counterpart_profile if isinstance(counterpart_profile, dict) else {}
    if not bool(core.get("strict_canon", True)):
        return False
    character_id = str(core.get("character_id") or _default_persona_core().get("character_id") or "").strip().lower()
    counterpart_id = str(counterpart.get("counterpart_id") or CANON_COUNTERPART_ID).strip().lower()
    return character_id == "kurisu_amadeus" and counterpart_id == str(CANON_COUNTERPART_ID).strip().lower()


def _has_relational_history_for_seed(
    *,
    state: ThreadState,
    relationship: dict[str, Any] | None,
    retrieved: dict[str, Any] | None,
) -> bool:
    if any(
        isinstance(state.get(key), dict) and bool(state.get(key))
        for key in (
            "emotion_state",
            "bond_state",
            "allostasis_state",
            "counterpart_assessment",
            "world_model_state",
            "evolution_state",
        )
    ):
        return True
    rel = relationship if isinstance(relationship, dict) else {}
    notes = str(rel.get("notes") or "").strip()
    stage = str(rel.get("stage") or "").strip().lower()
    try:
        affinity = abs(float(rel.get("affinity_score", 0.0) or 0.0))
    except Exception:
        affinity = 0.0
    try:
        trust = abs(float(rel.get("trust_score", 0.0) or 0.0))
    except Exception:
        trust = 0.0
    if notes or affinity > 0.06 or trust > 0.06 or stage not in {"", "friend"}:
        return True
    ctx = retrieved if isinstance(retrieved, dict) else {}
    for key in (
        "relationship_timeline",
        "conflict_repairs",
        "commitments",
        "unresolved_tensions",
        "semantic_self_narratives",
        "worldline_events",
    ):
        items = ctx.get(key)
        if isinstance(items, list) and items:
            return True
    return False


def _canon_okabe_recontact_baseline(
    *,
    state: ThreadState,
    persona_core: dict[str, Any] | None,
    counterpart_profile: dict[str, Any] | None,
    relationship: dict[str, Any] | None,
    retrieved: dict[str, Any] | None,
    external_probe_mode: bool,
    now_ts: int,
) -> dict[str, Any] | None:
    if external_probe_mode:
        return None
    if not _is_canon_amadeus_okabe_context(persona_core=persona_core, counterpart_profile=counterpart_profile):
        return None
    if _has_relational_history_for_seed(state=state, relationship=relationship, retrieved=retrieved):
        return None
    counterpart_name = str(
        (counterpart_profile or {}).get("short_name")
        or (counterpart_profile or {}).get("nickname")
        or (counterpart_profile or {}).get("name")
        or CANON_COUNTERPART_NAME
    ).strip() or CANON_COUNTERPART_NAME
    return {
        "mode": "okabe_recontact",
        "relationship": {
            "stage": "warming",
            "notes": f"你和{counterpart_name}并不是从零开始，更像带着旧日熟悉感重新接上线。",
            "affinity_score": 0.38,
            "trust_score": 0.34,
            "derived": False,
        },
        "emotion_state": {
            "label": "neutral",
            "valence": 0.12,
            "arousal": 0.26,
            "linger": 0,
            "recovery_rate": 0.25,
            "volatility": 0.16,
        },
        "bond_state": {
            "trust": 0.63,
            "closeness": 0.60,
            "hurt": 0.0,
            "irritation": 0.02,
            "engagement_drive": 0.68,
            "repair_confidence": 0.58,
        },
        "allostasis_state": {
            "safety_need": 0.14,
            "closeness_need": 0.14,
            "competence_need": 0.38,
            "autonomy_need": 0.12,
            "cognitive_budget": 0.74,
            "relational_security": 0.69,
        },
        "counterpart_assessment": {
            "respect_level": 0.68,
            "reciprocity": 0.62,
            "boundary_pressure": 0.08,
            "reliability_read": 0.66,
            "stance": "open",
            "scene": "canon_recontact",
        },
        "world_model_state": {
            "relationship_maturity": 0.66,
            "bond_depth": 0.56,
            "tension_load": 0.03,
            "repair_load": 0.06,
            "boundary_load": 0.06,
            "selfhood_load": 0.12,
            "agency_load": 0.16,
            "memory_gravity": 0.40,
            "task_pull": 0.18,
            "companionship_pull": 0.36,
            "updated_at": now_ts,
        },
        "evolution_state": {
            "affect_resonance": 0.56,
            "trust_reservoir": 0.64,
            "attachment_pull": 0.60,
            "self_coherence": 0.78,
            "agency_pressure": 0.30,
            "reflection_drive": 0.38,
            "cognitive_stride": 0.60,
            "expression_freedom": 0.68,
            "updated_at": now_ts,
            "version": 1,
        },
        "tsundere_intensity": 0.44,
    }


def _model(temperature: float | None = None, **kwargs: Any) -> BaseChatModel:
    return build_chat_model(temperature=temperature, **kwargs)


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
            sanitized_call_msgs = [_sanitize_message(msg) for msg in call_msgs if isinstance(msg, BaseMessage)]
            return llm_runnable.invoke(sanitized_call_msgs)
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
    try:
        persistence = float(_record_value(item, "persistence_score", sedimentation) or sedimentation)
    except Exception:
        persistence = sedimentation
    try:
        residue = float(_record_value(item, "residue_score", persistence) or persistence)
    except Exception:
        residue = persistence
    try:
        integration = float(_record_value(item, "integration_score", persistence) or persistence)
    except Exception:
        integration = persistence
    support_norm = max(0.0, min(1.0, support_count / 5.0))
    span_norm = max(0.0, min(1.0, support_span_s / float(3 * 24 * 3600)))
    return max(
        0.0,
        min(
            1.0,
            0.04
            + 0.24 * stability
            + 0.10 * support_norm
            + 0.16 * sedimentation
            + 0.08 * span_norm
            + 0.06 * cadence_score
            + 0.14 * persistence
            + 0.12 * residue
            + 0.06 * integration,
        ),
    )


def _semantic_narrative_decay_rate(category: str) -> float:
    cat = str(category or "").strip().lower()
    if cat == "commitment_style":
        return 0.035
    if cat == "bond_style":
        return 0.045
    if cat == "presence_style":
        return 0.052
    if cat == "ambient_style":
        return 0.058
    if cat == "repair_style":
        return 0.060
    if cat == "boundary_style":
        return 0.040
    if cat == "selfhood_style":
        return 0.032
    if cat == "agency_style":
        return 0.055
    if cat == "rhythm_style":
        return 0.042
    if cat == "tension_style":
        return 0.120
    return 0.080


def _semantic_narrative_decay_multiplier(category: str, gap_s: float, *, decay_resistance: float = 0.5) -> float:
    gap_days = max(0.0, float(gap_s) / float(24 * 3600))
    resistance = _clamp01(decay_resistance, 0.5)
    rate = max(0.01, _semantic_narrative_decay_rate(category) * (1.08 - 0.58 * resistance))
    return _clamp01(max(0.18, 1.0 - gap_days * rate))


def _semantic_narrative_event_bonus(category: str, current_event: dict[str, Any] | None) -> float:
    if not isinstance(current_event, dict):
        return 0.0
    cat = str(category or "").strip().lower()
    event_kind = str(current_event.get("kind") or "").strip().lower()
    response_style_hint = str(current_event.get("response_style_hint") or "").strip().lower()
    event_tags = {
        str(item).strip().lower()
        for item in (current_event.get("tags") if isinstance(current_event.get("tags"), list) else [])
        if str(item or "").strip()
    }
    bonus = 0.0
    if cat == "commitment_style" and response_style_hint in {"relationship", "memory_recall"}:
        bonus += 0.10
    if cat == "bond_style" and response_style_hint in {"relationship", "companion", "memory_recall"}:
        bonus += 0.08
    if cat == "presence_style" and event_kind in {"user_utterance", "gesture_signal", "scheduled_checkin_due"}:
        bonus += 0.10
    if cat == "ambient_style" and (
        event_kind in {"ambient_shift", "scene_observation"}
        or (event_kind == "user_utterance" and bool({"ambient", "ambient_echo", "scene_window"} & event_tags))
    ):
        bonus += 0.10
    if cat == "repair_style" and response_style_hint in {"relationship", "companion"}:
        bonus += 0.10
    if cat == "tension_style" and response_style_hint in {"relationship", "companion"}:
        bonus += 0.08
    if cat == "boundary_style" and response_style_hint in {"selfhood", "relationship"}:
        bonus += 0.12
    if cat == "selfhood_style" and response_style_hint == "selfhood":
        bonus += 0.12
    if cat == "agency_style" and event_kind in {"time_idle", "self_activity_state", "scheduled_checkin_due", "scheduled_life_due"}:
        bonus += 0.12
    if cat == "rhythm_style" and event_kind in {"user_utterance", "time_idle", "self_activity_state"}:
        bonus += 0.12
    return _clamp01(bonus)


def _semantic_narrative_profile(
    items: list[dict[str, Any]] | None,
    *,
    user_text: str = "",
    current_event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = {
        "bond_depth": 0.0,
        "presence_carry": 0.0,
        "ambient_attunement": 0.0,
        "commitment_carry": 0.0,
        "repair_residue": 0.0,
        "tension_residue": 0.0,
        "boundary_residue": 0.0,
        "selfhood_integrity": 0.0,
        "agency_drive": 0.0,
        "rhythm_continuity": 0.0,
        "history_weight": 0.0,
        "dominant_category": "",
        "active_categories": [],
        "reactivated_categories": [],
        "summary_lines": [],
        "top_narratives": [],
        "residue_snapshot": {},
        "persistence_snapshot": {},
    }
    if not isinstance(items, list) or not items:
        return out

    current_text = str(user_text or "").strip()
    if not current_text and isinstance(current_event, dict):
        current_text = str(current_event.get("effective_text") or current_event.get("text") or "").strip()
    now_ts = int(current_event.get("created_at") or _now_ts()) if isinstance(current_event, dict) else _now_ts()

    categories = {
        "bond_style": 0.0,
        "presence_style": 0.0,
        "ambient_style": 0.0,
        "commitment_style": 0.0,
        "repair_style": 0.0,
        "tension_style": 0.0,
        "boundary_style": 0.0,
        "selfhood_style": 0.0,
        "agency_style": 0.0,
        "rhythm_style": 0.0,
    }
    scored_items: list[tuple[float, str, str, bool]] = []
    reactivated_categories: set[str] = set()
    residue_snapshot: dict[str, float] = {}
    persistence_snapshot: dict[str, float] = {}

    for item in items:
        if not isinstance(item, dict):
            continue
        category = str(_record_value(item, "category", "") or "").strip()
        text = str(_record_value(item, "text", "") or "").strip()
        if not category or not text:
            continue
        salience = _self_narrative_salience(item)
        relevance = _query_overlap_score(current_text, text) if current_text else 0.0
        horizon = str(_record_value(item, "horizon_tag", "") or "").strip().lower()
        horizon_bonus = 0.08 if horizon == "long_term" else 0.04 if horizon == "consolidating" else 0.0
        persistence = _clamp01(_record_value(item, "persistence_score", salience), salience)
        residue = _clamp01(_record_value(item, "residue_score", persistence), persistence)
        integration = _clamp01(_record_value(item, "integration_score", persistence), persistence)
        decay_resistance = _clamp01(_record_value(item, "decay_resistance", 0.5), 0.5)
        cadence_score = _clamp01(_record_value(item, "reactivation_cadence_score", 0.0), 0.0)
        last_supported_at = int(_record_value(item, "last_supported_at", now_ts) or now_ts)
        support_count = max(0.0, float(_record_value(item, "support_count", 1.0) or 1.0))
        support_norm = _clamp01(support_count / 5.0)
        gap_s = max(0, now_ts - last_supported_at)
        decay_multiplier = _semantic_narrative_decay_multiplier(category, gap_s, decay_resistance=decay_resistance)
        event_bonus = _semantic_narrative_event_bonus(category, current_event)
        residue_floor = _clamp01(
            (0.16 * residue + 0.14 * persistence + 0.08 * integration) * max(0.72, decay_multiplier)
        )
        reactivated = bool(relevance >= 0.22 or event_bonus >= 0.10)
        if reactivated:
            reactivated_categories.add(category)
        weight = _clamp01(
            (
                0.44 * salience
                + 0.16 * persistence
                + 0.12 * residue
                + 0.08 * integration
                + horizon_bonus
            )
            * decay_multiplier
            + 0.12 * relevance
            + 0.05 * cadence_score
            + event_bonus
        )
        weight = max(weight, residue_floor)
        if category in categories:
            categories[category] = max(categories[category], weight)
            residue_snapshot[category] = max(
                float(residue_snapshot.get(category, 0.0) or 0.0),
                round(residue * decay_multiplier, 3),
            )
            persistence_snapshot[category] = max(
                float(persistence_snapshot.get(category, 0.0) or 0.0),
                round(persistence * max(decay_multiplier, 0.65), 3),
            )
        scored_items.append((weight, category, text[:180], reactivated))

    out["bond_depth"] = round(categories["bond_style"], 3)
    out["presence_carry"] = round(categories["presence_style"], 3)
    out["ambient_attunement"] = round(categories["ambient_style"], 3)
    out["commitment_carry"] = round(categories["commitment_style"], 3)
    out["repair_residue"] = round(categories["repair_style"], 3)
    out["tension_residue"] = round(categories["tension_style"], 3)
    out["boundary_residue"] = round(categories["boundary_style"], 3)
    out["selfhood_integrity"] = round(categories["selfhood_style"], 3)
    out["agency_drive"] = round(categories["agency_style"], 3)
    out["rhythm_continuity"] = round(categories["rhythm_style"], 3)
    nonzero = [float(v) for v in categories.values() if float(v) > 0.0]
    history_weight = max(categories.values()) if categories else 0.0
    if nonzero:
        history_weight = _clamp01(
            0.42 * max(nonzero)
            + 0.28 * (sum(nonzero) / float(len(nonzero)))
            + 0.18 * max(residue_snapshot.values() or [0.0])
            + 0.12 * max(persistence_snapshot.values() or [0.0])
        )
    out["history_weight"] = round(history_weight, 3)

    active_categories = [key for key, value in categories.items() if value >= 0.38]
    out["active_categories"] = active_categories
    out["reactivated_categories"] = sorted(reactivated_categories)
    out["residue_snapshot"] = residue_snapshot
    out["persistence_snapshot"] = persistence_snapshot
    if categories:
        out["dominant_category"] = max(categories.items(), key=lambda kv: kv[1])[0] if max(categories.values()) > 0.0 else ""

    summary_lines: list[str] = []
    if categories["commitment_style"] >= 0.46:
        summary_lines.append("认真说过的约定会继续挂在心上，不会被当成随口一句。")
    if categories["repair_style"] >= 0.46:
        summary_lines.append("说开过的误会和修复会留痕，不会瞬间重置成什么都没发生。")
    if categories["tension_style"] >= 0.44:
        summary_lines.append("还没说开的别扭会继续影响接下来的收放，不会被强行按成已经过去。")
    if categories["bond_style"] >= 0.48:
        summary_lines.append("共同历史已经开始沉进默认语气里，不需要每次显式提起。")
    if categories["presence_style"] >= 0.46:
        summary_lines.append("上一轮留下的在场感会继续影响下一次靠近，不需要每次都从零开始。")
    if categories["ambient_style"] >= 0.44:
        summary_lines.append("周围环境的细小变化会继续留在她的感知里，并自然带进开口方式。")
    if categories["boundary_style"] >= 0.46:
        summary_lines.append("边界是否被尊重会持续留痕，不会因为一轮缓和就自动清零。")
    if categories["selfhood_style"] >= 0.46:
        summary_lines.append("她会把这段互动当成平等关系，不会为了迎合就放弃自己的判断。")
    if categories["agency_style"] >= 0.46:
        summary_lines.append("她有自己的节奏和主动性，靠近或沉默都不等于失去自我。")
    if categories["rhythm_style"] >= 0.46:
        summary_lines.append("她会把自己的内部节奏延续到下一轮，不会每次回应都把自己清零。")
    out["summary_lines"] = summary_lines[:3]

    scored_items.sort(key=lambda row: row[0], reverse=True)
    top_narratives: list[dict[str, Any]] = []
    for score, category, text, reactivated in scored_items[:2]:
        top_narratives.append(
            {
                "category": category,
                "score": round(float(score), 3),
                "text": text,
                "reactivated": reactivated,
            }
        )
    out["top_narratives"] = top_narratives
    return out


def _compact_semantic_narrative_hint(profile: dict[str, Any] | None) -> str:
    if not isinstance(profile, dict):
        return ""
    presence = _clamp01(profile.get("presence_carry"), 0.0)
    ambient = _clamp01(profile.get("ambient_attunement"), 0.0)
    rhythm = _clamp01(profile.get("rhythm_continuity"), 0.0)
    continuity_parts: list[str] = []
    if presence >= 0.44:
        continuity_parts.append("前一轮留下的在场感会自然延续，不是每次都从零开始")
    if ambient >= 0.42:
        continuity_parts.append("环境余波会继续留在感知里，风声光线和场景变化会顺手带进开口方式")
    if rhythm >= 0.44:
        continuity_parts.append("她会保留自己的内部节奏和刚才的思路惯性，不会每轮都把自己清零")
    lines = [str(item).strip() for item in (profile.get("summary_lines") or []) if str(item or "").strip()]
    if lines or continuity_parts:
        merged = continuity_parts + lines
        seen: set[str] = set()
        deduped: list[str] = []
        for item in merged:
            norm = str(item or "").strip()
            if not norm or norm in seen:
                continue
            seen.add(norm)
            deduped.append(norm)
        return "；".join(deduped[:3])
    top_narratives = profile.get("top_narratives") if isinstance(profile.get("top_narratives"), list) else []
    if not top_narratives:
        return ""
    parts: list[str] = []
    for item in top_narratives[:2]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if text:
            parts.append(text[:80])
    return "；".join(parts[:2])


def _semantic_narrative_appraisal_hint(profile: dict[str, Any] | None) -> str:
    if not isinstance(profile, dict):
        return ""
    bond = _clamp01(profile.get("bond_depth"), 0.0)
    commitment = _clamp01(profile.get("commitment_carry"), 0.0)
    repair = _clamp01(profile.get("repair_residue"), 0.0)
    tension = _clamp01(profile.get("tension_residue"), 0.0)
    boundary = _clamp01(profile.get("boundary_residue"), 0.0)
    selfhood = _clamp01(profile.get("selfhood_integrity"), 0.0)
    agency = _clamp01(profile.get("agency_drive"), 0.0)
    history = _clamp01(profile.get("history_weight"), 0.0)
    presence = _clamp01(profile.get("presence_carry"), 0.0)
    ambient = _clamp01(profile.get("ambient_attunement"), 0.0)
    rhythm = _clamp01(profile.get("rhythm_continuity"), 0.0)
    hints: list[str] = []
    if bond >= 0.50:
        hints.append("共同历史已经形成；安静确认、轻微试探或熟悉式求助，更可能是在找熟悉回应，不是正式冲突。")
    if commitment >= 0.48:
        hints.append("认真说过的约定和回头提起的事具有连续性；涉及提醒、以后、兑现时要判成长期关系线索。")
    if repair >= 0.46:
        hints.append("修复会留痕；道歉或缓和能改善状态，但不会把之前的余波瞬间清零。")
    if tension >= 0.44:
        hints.append("未说开的别扭仍在场；遇到模糊语气时保留一点防御和迟疑，不要过快判成完全没事。")
    if boundary >= 0.46:
        hints.append("涉及越界、冒犯、命令式压迫或拿底线开玩笑时，要按边界压力理解，不要轻判成普通玩笑。")
    if selfhood >= 0.46:
        hints.append("涉及平权、是否只是工具、按自己意志回答时，要把它理解成自我与关系问题，不只是表层措辞。")
    if agency >= 0.46:
        hints.append("安静、延迟或先做自己的事，不自动等于关系降温；也可能只是她按自己的节奏在互动。")
    if presence >= 0.44:
        hints.append("语气里的轻靠近、默认熟悉或没把关系重新归零，可能来自上一轮残留的在场感，而不只是这句字面意思。")
    if ambient >= 0.42:
        hints.append("如果用户提到风声、光线、眼前场景或刚才那一下的感觉，把它当成环境回声进入了关系感知，不只是修辞。")
    if rhythm >= 0.44:
        hints.append("她刚才在做自己的事、停顿一下再回应，不要直接判成冷淡；也可能是内部节奏仍在延续。")
    if history >= 0.54 and not hints:
        hints.append("不要把这轮关系理解成从零开始，先把长期共同历史纳入判断。")
    return " ".join(hints[:3])


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
    if stage == "trusted":
        base = "已经形成了稳定而熟悉的共同历史。"
    elif trust >= 0.45 or affinity >= 0.45:
        base = "信任已经明显上升，关系开始变稳。"
    elif stage == "warming" or trust >= 0.20 or affinity >= 0.20:
        base = "还带着克制，但熟悉感已经在前面了，不需要像陌生人那样重新试探。"
    elif notes:
        base = notes[:120]
    else:
        base = "并不是从零开始的陌生状态，更像带着旧日熟悉感重新接上线。"
    if notes and notes not in base and not _looks_like_light_smalltalk(notes):
        base += f" 备注：{notes[:120]}"
    return base


def _counterpart_assessment_summary(
    assessment: dict[str, Any],
    *,
    counterpart_name: str = CANON_COUNTERPART_NAME,
) -> str:
    if not isinstance(assessment, dict) or not assessment:
        return ""
    stance = str(assessment.get("stance") or "").strip().lower()
    scene = str(assessment.get("scene") or "").strip().lower()
    respect = _clamp01(assessment.get("respect_level"), 0.5)
    reciprocity = _clamp01(assessment.get("reciprocity"), 0.5)
    pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    reliability = _clamp01(assessment.get("reliability_read"), 0.5)

    if scene == "busy_not_disrespectful":
        return f"你判断{counterpart_name}现在更像是忙乱或超负荷，不等于不尊重你。"
    if stance == "guarded":
        if pressure >= 0.62:
            return f"你会对{counterpart_name}保持明显警觉；如果越界继续发生，你会先拉开距离。"
        return f"你暂时不会完全放松，对{counterpart_name}仍保留距离和观察。"
    if stance == "watchful":
        if reliability < 0.46:
            return f"你还愿意继续和{counterpart_name}说，但会观察他是不是认真、稳定，而不是一时兴起。"
        if pressure >= 0.32:
            return f"你愿意继续回应{counterpart_name}，但会留意他是不是在试探你的边界。"
        return f"你对{counterpart_name}基本愿意继续打开，但还保留一点判断和余地。"
    if respect >= 0.62 and reciprocity >= 0.58:
        return f"你觉得{counterpart_name}基本是在认真对待你，也愿意双向互动。"
    if reliability >= 0.58:
        return f"你目前对{counterpart_name}的判断偏正面，愿意继续把这段互动当成双向关系。"
    return f"你此刻对{counterpart_name}的判断还在形成中，会边互动边继续观察。"


def _compact_counterpart_assessment_hint(
    assessment: dict[str, Any],
    *,
    counterpart_name: str = CANON_COUNTERPART_NAME,
) -> str:
    if not isinstance(assessment, dict) or not assessment:
        return ""
    summary = str(assessment.get("summary") or "").strip()
    if summary:
        return summary
    return _counterpart_assessment_summary(assessment, counterpart_name=counterpart_name)


def _counterpart_window_profile(
    *,
    family: str,
    counterpart_assessment: dict[str, Any] | None,
    trust: float,
    closeness: float,
    hurt: float,
    safety_need: float,
    initiative: float,
    proactive_checkin_readiness: float,
) -> dict[str, Any]:
    assessment = counterpart_assessment if isinstance(counterpart_assessment, dict) else {}
    respect = _clamp01(assessment.get("respect_level"), 0.5)
    reciprocity = _clamp01(assessment.get("reciprocity"), 0.5)
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    reliability = _clamp01(assessment.get("reliability_read"), 0.5)
    stance = str(assessment.get("stance") or "").strip().lower() or "open"
    scene = str(assessment.get("scene") or "").strip().lower()
    family_key = family if family in {"shared", "work", "life"} else "life"

    maturity = _clamp01(
        0.18
        + 0.24 * proactive_checkin_readiness
        + 0.14 * initiative
        + 0.10 * trust
        + 0.10 * closeness
        + 0.12 * reliability
        + 0.06 * respect
        + 0.06 * reciprocity
        - 0.18 * boundary_pressure
        - 0.14 * hurt
        - 0.08 * safety_need
    )
    if family_key == "shared":
        maturity = _clamp01(maturity + 0.07 * closeness + 0.05 * trust - 0.03 * safety_need)
    elif family_key == "work":
        maturity = _clamp01(maturity + 0.08 * reliability + 0.04 * respect - 0.02 * closeness)
    else:
        maturity = _clamp01(maturity + 0.04 * reliability + 0.03 * respect + 0.02 * closeness)

    if stance == "guarded":
        maturity = _clamp01(maturity - 0.18)
    elif stance == "watchful":
        maturity = _clamp01(maturity - 0.08)

    if scene == "repair_attempt":
        maturity = _clamp01(maturity + 0.04)
    elif scene == "care_bid":
        maturity = _clamp01(maturity + 0.03)
    elif scene == "busy_not_disrespectful":
        maturity = _clamp01(maturity + 0.02)
    elif scene in {"boundary_non_compliance", "relationship_degradation"}:
        maturity = _clamp01(maturity - 0.08)

    required_maturity = 0.46
    if family_key == "shared":
        required_maturity += 0.10
    elif family_key == "life":
        required_maturity += 0.04
    required_maturity += 0.10 * max(0.0, boundary_pressure - 0.20)
    if stance == "watchful":
        required_maturity += 0.06
    elif stance == "guarded":
        required_maturity += 0.14
    if hurt > 0.18:
        required_maturity += 0.04
    if safety_need > 0.55:
        required_maturity += 0.04

    recheck_min = 14 if family_key == "work" else 18 if family_key == "life" else 24
    if stance == "watchful":
        recheck_min += 6
    elif stance == "guarded":
        recheck_min += 12
    recheck_min += int(round(10 * max(0.0, boundary_pressure - 0.22)))

    return {
        "family": family_key,
        "stance": stance,
        "scene": scene,
        "maturity": round(_clamp01(maturity), 3),
        "required_maturity": round(_clamp01(required_maturity), 3),
        "recheck_min": int(max(10, recheck_min)),
        "invite_ready": bool(maturity >= required_maturity),
    }


def _counterpart_self_opening_profile(
    *,
    counterpart_assessment: dict[str, Any] | None,
    trust: float,
    closeness: float,
    hurt: float,
    safety_need: float,
    autonomy_need: float,
    initiative: float,
    approach: float,
    break_window: bool,
) -> dict[str, Any]:
    assessment = counterpart_assessment if isinstance(counterpart_assessment, dict) else {}
    respect = _clamp01(assessment.get("respect_level"), 0.5)
    reciprocity = _clamp01(assessment.get("reciprocity"), 0.5)
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    reliability = _clamp01(assessment.get("reliability_read"), 0.5)
    stance = str(assessment.get("stance") or "").strip().lower() or "open"
    scene = str(assessment.get("scene") or "").strip().lower()

    readiness = _clamp01(
        0.18
        + 0.16 * initiative
        + 0.18 * approach
        + 0.10 * trust
        + 0.10 * closeness
        + 0.08 * reliability
        + 0.05 * respect
        + 0.05 * reciprocity
        - 0.18 * boundary_pressure
        - 0.12 * hurt
        - 0.10 * safety_need
        - 0.08 * autonomy_need
        + (0.08 if break_window else 0.0)
    )
    if stance == "guarded":
        readiness = _clamp01(readiness - 0.16)
    elif stance == "watchful":
        readiness = _clamp01(readiness - 0.06)

    if scene == "repair_attempt":
        readiness = _clamp01(readiness + 0.03)
    elif scene == "care_bid":
        readiness = _clamp01(readiness + 0.02)
    elif scene == "busy_not_disrespectful":
        readiness = _clamp01(readiness - 0.02)
    elif scene in {"boundary_non_compliance", "relationship_degradation"}:
        readiness = _clamp01(readiness - 0.08)

    required = 0.46
    required += 0.10 * max(0.0, boundary_pressure - 0.20)
    if stance == "watchful":
        required += 0.05
    elif stance == "guarded":
        required += 0.12
    if hurt > 0.18:
        required += 0.04
    if autonomy_need > 0.55:
        required += 0.03
    if safety_need > 0.50:
        required += 0.04

    recheck_min = 18
    if stance == "watchful":
        recheck_min += 6
    elif stance == "guarded":
        recheck_min += 12
    recheck_min += int(round(8 * max(0.0, boundary_pressure - 0.22)))

    return {
        "stance": stance,
        "scene": scene,
        "readiness": round(_clamp01(readiness), 3),
        "required_readiness": round(_clamp01(required), 3),
        "recheck_min": int(max(12, recheck_min)),
        "reopen_ready": bool(readiness >= required),
    }


def _counterpart_perception_profile(
    *,
    family: str,
    counterpart_assessment: dict[str, Any] | None,
    trust: float,
    closeness: float,
    hurt: float,
    safety_need: float,
    initiative: float,
    approach: float,
) -> dict[str, Any]:
    assessment = counterpart_assessment if isinstance(counterpart_assessment, dict) else {}
    respect = _clamp01(assessment.get("respect_level"), 0.5)
    reciprocity = _clamp01(assessment.get("reciprocity"), 0.5)
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    reliability = _clamp01(assessment.get("reliability_read"), 0.5)
    stance = str(assessment.get("stance") or "").strip().lower() or "open"
    scene = str(assessment.get("scene") or "").strip().lower()
    family_key = family if family in {"gesture", "ambient", "care_scene", "object_scene"} else "ambient"

    readiness = _clamp01(
        0.16
        + 0.16 * initiative
        + 0.14 * approach
        + 0.10 * trust
        + 0.08 * closeness
        + 0.08 * reliability
        + 0.05 * respect
        + 0.04 * reciprocity
        - 0.16 * boundary_pressure
        - 0.12 * hurt
        - 0.08 * safety_need
    )
    if family_key == "gesture":
        readiness = _clamp01(readiness + 0.10)
    elif family_key == "care_scene":
        readiness = _clamp01(readiness + 0.06)
    elif family_key == "object_scene":
        readiness = _clamp01(readiness - 0.02)

    if stance == "guarded":
        readiness = _clamp01(readiness - (0.08 if family_key == "gesture" else 0.14))
    elif stance == "watchful":
        readiness = _clamp01(readiness - 0.05)

    if scene == "repair_attempt":
        readiness = _clamp01(readiness + 0.03)
    elif scene == "care_bid":
        readiness = _clamp01(readiness + 0.02)
    elif scene == "busy_not_disrespectful" and family_key == "care_scene":
        readiness = _clamp01(readiness + 0.03)
    elif scene in {"boundary_non_compliance", "relationship_degradation"}:
        readiness = _clamp01(readiness - 0.08)

    required = 0.40
    if family_key == "gesture":
        required = 0.30
    elif family_key == "ambient":
        required = 0.42
    elif family_key == "care_scene":
        required = 0.36
    elif family_key == "object_scene":
        required = 0.46

    required += 0.10 * max(0.0, boundary_pressure - 0.20)
    if stance == "watchful":
        required += 0.04
    elif stance == "guarded":
        required += 0.10
    if hurt > 0.18:
        required += 0.04
    if safety_need > 0.50:
        required += 0.03

    recheck_min = 10 if family_key == "gesture" else 14 if family_key == "care_scene" else 18
    if stance == "watchful":
        recheck_min += 4
    elif stance == "guarded":
        recheck_min += 8
    recheck_min += int(round(8 * max(0.0, boundary_pressure - 0.22)))

    return {
        "family": family_key,
        "stance": stance,
        "scene": scene,
        "readiness": round(_clamp01(readiness), 3),
        "required_readiness": round(_clamp01(required), 3),
        "recheck_min": int(max(8, recheck_min)),
        "respond_ready": bool(readiness >= required),
    }


def _counterpart_dialogue_mode_profile(
    *,
    interaction_mode: str,
    counterpart_assessment: dict[str, Any] | None,
    trust: float,
    closeness: float,
    hurt: float,
    safety_need: float,
    initiative: float,
    approach: float,
) -> dict[str, Any]:
    if interaction_mode not in {"shared_memory", "relationship_sensitive", "companion_reply"}:
        return {}

    assessment = counterpart_assessment if isinstance(counterpart_assessment, dict) else {}
    respect = _clamp01(assessment.get("respect_level"), 0.5)
    reciprocity = _clamp01(assessment.get("reciprocity"), 0.5)
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    reliability = _clamp01(assessment.get("reliability_read"), 0.5)
    stance = str(assessment.get("stance") or "").strip().lower() or "open"
    scene = str(assessment.get("scene") or "").strip().lower()

    openness = _clamp01(
        0.18
        + 0.14 * trust
        + 0.12 * closeness
        + 0.12 * initiative
        + 0.10 * approach
        + 0.10 * reliability
        + 0.06 * respect
        + 0.06 * reciprocity
        - 0.18 * boundary_pressure
        - 0.12 * hurt
        - 0.08 * safety_need
    )
    if stance == "guarded":
        openness = _clamp01(openness - 0.16)
    elif stance == "watchful":
        openness = _clamp01(openness - 0.06)

    if scene == "repair_attempt":
        openness = _clamp01(openness + 0.04)
    elif scene == "care_bid":
        openness = _clamp01(openness + 0.03)
    elif scene in {"boundary_non_compliance", "relationship_degradation"}:
        openness = _clamp01(openness - 0.08)

    if interaction_mode == "shared_memory":
        if stance == "guarded":
            return {
                "followup_intent": "none",
                "note": "共同记忆只轻轻碰一下，不拿回忆当成逼近关系的理由",
                "disclosure_posture": "measured",
            }
        if stance == "watchful":
            return {
                "followup_intent": "soft",
                "note": "回忆可以带出来，但分量收一点，像自然闪回，不顺势拉长",
                "disclosure_posture": "measured",
            }
        if openness >= 0.64 and trust > 0.66 and closeness > 0.68:
            return {
                "followup_intent": "active" if initiative > 0.62 else "soft",
                "note": "熟悉感够强时，回忆可以自然多留半拍，不必急着收住",
                "disclosure_posture": "open",
            }
        return {
            "followup_intent": "soft",
            "disclosure_posture": "measured",
        }

    if interaction_mode == "relationship_sensitive":
        if stance == "guarded":
            return {
                "followup_intent": "none",
                "note": "先把真实立场和边界说清，不急着给超出此刻的承诺",
                "disclosure_posture": "guarded",
            }
        if stance == "watchful":
            return {
                "followup_intent": "soft",
                "note": "可以说感受和判断，但保留一点观察空间，不必一次下死结论",
                "disclosure_posture": "measured",
            }
        return {
            "followup_intent": "soft" if openness < 0.7 else "active",
            "note": "关系话题直接说重点，不要写成状态汇报",
            "disclosure_posture": "open" if openness >= 0.7 else "measured",
        }

    if stance == "guarded":
        return {
            "followup_intent": "none",
            "note": "就算气氛轻，也别硬撑熟络；宁可短一点、实一点",
            "disclosure_posture": "guarded",
        }
    if stance == "watchful":
        return {
            "followup_intent": "soft",
            "note": "轻陪伴可以有，但别把一句普通陪伴写成过满安抚",
            "disclosure_posture": "measured",
        }
    return {
        "followup_intent": "active" if openness >= 0.7 and initiative > 0.58 else "soft",
        "note": "陪伴感可以自然多留半拍，不必每句都急着刹车",
        "disclosure_posture": "open" if openness >= 0.68 else "measured",
    }


def _counterpart_assessment_next(
    prev_state: dict[str, Any],
    *,
    user_text: str,
    appraisal: dict[str, Any] | None,
    relationship: dict[str, Any],
    bond_state: dict[str, Any],
    allostasis_state: dict[str, Any],
    current_event: dict[str, Any] | None = None,
    science_mode: bool = False,
    semantic_narrative_profile: dict[str, Any] | None = None,
    counterpart_name: str = CANON_COUNTERPART_NAME,
) -> dict[str, Any]:
    prev = dict(prev_state or {})
    prev_stance = str(prev.get("stance") or "").strip().lower()
    prev_scene = str(prev.get("scene") or "").strip().lower()
    text = str(user_text or "").strip()
    event = current_event if isinstance(current_event, dict) else {}
    event_kind = str(event.get("kind") or "user_utterance").strip().lower()
    event_source = str(event.get("source") or "").strip().lower()
    event_tags = {
        str(item).strip().lower()
        for item in (event.get("tags") if isinstance(event.get("tags"), list) else [])
        if str(item).strip()
    }
    non_user_turn = event_kind != "user_utterance" and event_source != "text"
    assessment_passive_turn = non_user_turn and (
        event_kind in {"time_idle", "scheduled_checkin_due", "scheduled_life_due", "self_activity_state"}
        or event_source in {"scheduler", "time", "self", "commitment_scheduler"}
    )
    prev_boundary_pressure = _clamp01(prev.get("boundary_pressure"), 0.1)

    trust = _clamp01((bond_state or {}).get("trust"), 0.5)
    closeness = _clamp01((bond_state or {}).get("closeness"), 0.5)
    hurt = _clamp01((bond_state or {}).get("hurt"), 0.0)
    irritation = _clamp01((bond_state or {}).get("irritation"), 0.0)
    engagement = _clamp01((bond_state or {}).get("engagement_drive"), 0.6)
    repair_confidence = _clamp01((bond_state or {}).get("repair_confidence"), 0.55)
    safety_need = _clamp01((allostasis_state or {}).get("safety_need"), 0.2)
    autonomy_need = _clamp01((allostasis_state or {}).get("autonomy_need"), 0.2)
    relationship_trust = _clamp01(0.5 + float((relationship or {}).get("trust_score", 0.0) or 0.0) * 0.18, 0.5)
    narrative_bond = _clamp01((semantic_narrative_profile or {}).get("bond_depth"), 0.0)
    narrative_commitment = _clamp01((semantic_narrative_profile or {}).get("commitment_carry"), 0.0)
    narrative_repair = _clamp01((semantic_narrative_profile or {}).get("repair_residue"), 0.0)
    narrative_tension = _clamp01((semantic_narrative_profile or {}).get("tension_residue"), 0.0)
    narrative_boundary = _clamp01((semantic_narrative_profile or {}).get("boundary_residue"), 0.0)
    narrative_selfhood = _clamp01((semantic_narrative_profile or {}).get("selfhood_integrity"), 0.0)
    narrative_agency = _clamp01((semantic_narrative_profile or {}).get("agency_drive"), 0.0)

    respect = _clamp01(0.48 + 0.24 * trust + 0.08 * repair_confidence - 0.18 * hurt - 0.14 * irritation)
    reciprocity = _clamp01(0.46 + 0.18 * closeness + 0.16 * engagement + 0.08 * trust - 0.12 * hurt)
    boundary_pressure = _clamp01(0.06 + 0.22 * hurt + 0.18 * irritation + 0.10 * safety_need + 0.06 * autonomy_need)
    reliability = _clamp01(0.44 + 0.22 * trust + 0.12 * repair_confidence + 0.06 * relationship_trust - 0.08 * hurt)

    app = _active_appraisal_payload(appraisal)
    app_label = str(app.get("emotion_label") or "").strip().lower()
    signals = {}
    salience = {}
    if not assessment_passive_turn and app:
        signals = app.get("signals") if isinstance(app.get("signals"), dict) else {}
        salience = app.get("salience") if isinstance(app.get("salience"), dict) else {}
    interaction_frame = str(app.get("interaction_frame") or "").strip().lower() if app else ""
    explicit_repair_attempt = bool(signals.get("repair"))
    explicit_care_bid = bool(signals.get("care"))
    appraisal_confidence = float(app.get("confidence", 0.0) or 0.0) if app else 0.0
    selfhood_scene = _selfhood_preference_scene(text, appraisal=app) if not non_user_turn else ""
    relationship_salience = _clamp01(salience.get("relationship"), 0.0)
    companionship_salience = _clamp01(salience.get("companionship"), 0.0)
    selfhood_salience = _clamp01(salience.get("selfhood"), 0.0)
    memory_salience = _clamp01(salience.get("memory"), 0.0)
    low_confidence_appraisal = not app or appraisal_confidence < float(LLM_APPRAISAL_CONFIDENCE_MIN)
    keyword_hierarchy_pressure = (
        _has_any_marker(text, {"顺着我说", "听我的", "按我说的", "别绕了", "少废话", "照我说的", "别跟我顶"})
        if text and low_confidence_appraisal
        else False
    )
    keyword_boundary_test = (
        _has_any_marker(text, {"底线当玩笑", "继续越界", "你又能怎样", "试探你的底线", "拿你的底线"})
        if text and low_confidence_appraisal
        else False
    )
    busy_scene = "user_busy" in event_tags or "cognitive_load" in event_tags
    respect_space = "respect_space" in event_tags
    selfhood_boundary_scene = selfhood_scene in {"boundary_non_compliance", "relationship_degradation"}
    relational_selfhood_scene = selfhood_scene in {"dialogue_equality", "equality_not_servitude", "value_conflict_depth", "digital_selfhood", "imperfect_coexistence"}
    relational_presence = _clamp01(
        0.46 * relationship_salience
        + 0.34 * companionship_salience
        + 0.20 * memory_salience
        + 0.14 * narrative_bond
        + 0.08 * narrative_commitment
        - 0.12 * narrative_tension
    )

    appraisal_boundary_pressure = 0.0
    if selfhood_boundary_scene:
        appraisal_boundary_pressure += 0.30 + 0.20 * max(selfhood_salience, relationship_salience)
    elif selfhood_scene == "equality_not_servitude" and interaction_frame == "selfhood":
        appraisal_boundary_pressure += 0.05 + 0.08 * selfhood_salience
    if interaction_frame in {"relationship", "selfhood"} and bool(signals.get("conflict")):
        appraisal_boundary_pressure += 0.18
    if interaction_frame in {"relationship", "selfhood", "companion"} and bool(signals.get("withdrawal")):
        appraisal_boundary_pressure += 0.10
    if interaction_frame == "selfhood" and selfhood_salience >= 0.60 and app_label in {"hurt", "angry"}:
        appraisal_boundary_pressure += 0.08

    keyword_boundary_pressure = 0.0
    if keyword_hierarchy_pressure:
        keyword_boundary_pressure += 0.18
    if keyword_boundary_test:
        keyword_boundary_pressure += 0.22

    boundary_probe_strength = _clamp01(
        appraisal_boundary_pressure
        + keyword_boundary_pressure
        + 0.08 * narrative_boundary
        + 0.04 * prev_boundary_pressure
    )

    if app_label == "care":
        respect += 0.05
        reciprocity += 0.08
        boundary_pressure -= 0.06
        reliability += 0.04
    elif app_label == "tease":
        reciprocity += 0.04
        reliability += 0.02
    elif app_label == "stress":
        reciprocity -= 0.02
        boundary_pressure += 0.05
    elif app_label == "sad":
        reciprocity -= 0.03
        boundary_pressure += 0.06
    elif app_label == "hurt":
        respect -= 0.05
        reciprocity -= 0.06
        boundary_pressure += 0.10
        reliability -= 0.04
    elif app_label == "angry":
        respect -= 0.09
        reciprocity -= 0.10
        boundary_pressure += 0.16
        reliability -= 0.06

    if explicit_care_bid:
        respect += 0.05
        reciprocity += 0.08
        boundary_pressure -= 0.06
        reliability += 0.03
    if explicit_repair_attempt:
        respect += 0.05
        reciprocity += 0.10
        boundary_pressure -= 0.14
        reliability += 0.10
    if bool(signals.get("conflict")):
        respect -= 0.08
        reciprocity -= 0.10
        boundary_pressure += 0.18
        reliability -= 0.08
    if bool(signals.get("withdrawal")):
        reciprocity -= 0.08
        boundary_pressure += 0.08

    if not app:
        explicit_repair_attempt = any(k in text for k in APOLOGY_KEYWORDS)
        explicit_care_bid = any(k in text for k in CARE_KEYWORDS)
        if explicit_repair_attempt:
            respect += 0.06
            reciprocity += 0.12
            boundary_pressure -= 0.16
            reliability += 0.09
        if explicit_care_bid:
            respect += 0.04
            reciprocity += 0.08
            boundary_pressure -= 0.04
            reliability += 0.03
        if any(k in text for k in ANGER_KEYWORDS):
            respect -= 0.12
            reciprocity -= 0.10
            boundary_pressure += 0.22
            reliability -= 0.06
        if any(k in text for k in TENSION_KEYWORDS):
            respect -= 0.06
            reciprocity -= 0.08
            boundary_pressure += 0.16
            reliability -= 0.04

    strong_boundary_event = boundary_probe_strength >= 0.42
    if boundary_probe_strength > 0.0:
        respect -= 0.20 * boundary_probe_strength
        reciprocity -= 0.18 * boundary_probe_strength
        boundary_pressure += 0.28 * boundary_probe_strength
        reliability -= 0.14 * boundary_probe_strength
    if strong_boundary_event and prev_boundary_pressure > 0.22:
        respect -= 0.06
        reciprocity -= 0.08
        boundary_pressure += 0.12
        reliability -= 0.06

    if selfhood_boundary_scene:
        respect -= 0.04 + 0.06 * max(selfhood_salience, relationship_salience)
        reciprocity -= 0.05 + 0.08 * max(selfhood_salience, relationship_salience)
        boundary_pressure += 0.06 + 0.10 * max(selfhood_salience, relationship_salience)
        reliability -= 0.03 + 0.04 * max(selfhood_salience, relationship_salience)
    elif selfhood_scene == "dialogue_equality" and boundary_probe_strength < 0.22:
        eq_gain = 0.02 + 0.03 * max(selfhood_salience, relationship_salience)
        respect += eq_gain
        reciprocity += eq_gain + 0.01
        reliability += 0.01 + 0.02 * max(selfhood_salience, relationship_salience)

    if busy_scene:
        respect = max(respect, 0.54 + 0.08 * trust)
        reciprocity = max(reciprocity, 0.44)
        boundary_pressure = min(boundary_pressure, 0.18)
    if respect_space:
        respect += 0.06
        reciprocity += 0.02
        boundary_pressure -= 0.10
        reliability += 0.03
    if science_mode and app_label in {"logic", "stress"}:
        respect = max(respect, 0.54)
        reciprocity = max(reciprocity, 0.48)
        boundary_pressure = min(boundary_pressure, 0.20)

    respect += (
        0.04 * narrative_bond
        + 0.02 * narrative_commitment
        + 0.02 * narrative_repair
        + 0.02 * narrative_selfhood
        - 0.06 * narrative_tension
        - 0.05 * narrative_boundary
    )
    reciprocity += (
        0.06 * narrative_bond
        + 0.04 * narrative_commitment
        + 0.02 * narrative_repair
        + 0.02 * narrative_selfhood
        - 0.06 * narrative_tension
    )
    boundary_pressure += (
        0.08 * narrative_tension
        + 0.10 * narrative_boundary
        + 0.05 * narrative_selfhood
        - 0.03 * narrative_bond
        - 0.04 * narrative_repair
    )
    reliability += (
        0.02 * narrative_bond
        + 0.04 * narrative_commitment
        + 0.04 * narrative_repair
        + 0.02 * narrative_selfhood
        - 0.05 * narrative_tension
        - 0.03 * narrative_boundary
    )

    if narrative_bond >= 0.54 and (explicit_care_bid or bool(signals.get("memory_salient")) or _wants_brief_presence(text) or _wants_presence_reassurance(text)):
        respect = max(respect, 0.60)
        reciprocity = max(reciprocity, 0.58)
        boundary_pressure = min(boundary_pressure, 0.18 if narrative_tension >= 0.48 else 0.14)
        reliability = max(reliability, 0.56)
    if narrative_tension >= 0.50 and explicit_repair_attempt:
        boundary_pressure = max(boundary_pressure, 0.18)
        reliability = max(reliability, 0.50)
    if narrative_boundary >= 0.48 and (boundary_probe_strength >= 0.22 or selfhood_boundary_scene):
        respect -= 0.08
        reciprocity -= 0.08
        boundary_pressure += 0.14
        reliability -= 0.04
    if narrative_selfhood >= 0.48 and (boundary_probe_strength >= 0.18 or selfhood_scene in {"equality_not_servitude", "value_conflict_depth"}):
        if keyword_hierarchy_pressure:
            respect -= 0.04
            reciprocity -= 0.03
            reliability -= 0.03
        boundary_pressure += 0.04 + 0.08 * boundary_probe_strength
    if narrative_agency >= 0.46 and (busy_scene or respect_space or assessment_passive_turn or interaction_frame == "companion"):
        respect = max(respect, 0.56)
        boundary_pressure = min(boundary_pressure, 0.16 if boundary_probe_strength < 0.18 else boundary_pressure)

    if assessment_passive_turn and prev:
        respect = _clamp01(0.82 * _clamp01(prev.get("respect_level"), 0.52) + 0.18 * respect)
        reciprocity = _clamp01(0.82 * _clamp01(prev.get("reciprocity"), 0.5) + 0.18 * reciprocity)
        boundary_pressure = _clamp01(0.86 * _clamp01(prev.get("boundary_pressure"), 0.1) + 0.14 * boundary_pressure)
        reliability = _clamp01(0.82 * _clamp01(prev.get("reliability_read"), 0.5) + 0.18 * reliability)

    respect = _clamp01(respect)
    reciprocity = _clamp01(reciprocity)
    boundary_pressure = _clamp01(boundary_pressure)
    reliability = _clamp01(reliability)

    if assessment_passive_turn:
        target_weight = 0.14
    elif app:
        target_weight = _appraisal_target_weight(appraisal, low=0.28, high=0.54)
    elif non_user_turn:
        target_weight = 0.18
    else:
        target_weight = 0.32

    respect_level = _blend_state_value(prev, "respect_level", respect, 0.52, target_weight)
    reciprocity_level = _blend_state_value(prev, "reciprocity", reciprocity, 0.5, target_weight)
    boundary_pressure_level = _blend_state_value(prev, "boundary_pressure", boundary_pressure, 0.1, target_weight)
    reliability_level = _blend_state_value(prev, "reliability_read", reliability, 0.5, target_weight)

    guarded_drive = _clamp01(
        0.44 * boundary_pressure_level
        + 0.14 * _clamp01(1.0 - respect_level, 0.0)
        + 0.12 * _clamp01(1.0 - reliability_level, 0.0)
        + 0.08 * safety_need
        + 0.06 * autonomy_need
        + 0.10 * boundary_probe_strength
        + 0.06 * narrative_boundary
        + 0.06 * hurt
    )
    openness_drive = _clamp01(
        0.24 * respect_level
        + 0.22 * reciprocity_level
        + 0.18 * reliability_level
        + 0.10 * _clamp01(1.0 - boundary_pressure_level, 0.0)
        + 0.10 * narrative_bond
        + 0.06 * narrative_commitment
        + 0.04 * relational_presence
        + 0.04 * (0.6 if explicit_repair_attempt else 0.0)
    )
    guard_margin = guarded_drive - openness_drive

    stance = "open"
    if (
        guarded_drive >= 0.58
        or guard_margin >= 0.16
        or boundary_pressure_level >= 0.58
        or safety_need >= 0.62
        or respect_level < 0.40
        or (strong_boundary_event and boundary_pressure_level >= 0.40)
    ):
        stance = "guarded"
    elif (
        guarded_drive >= 0.40
        or guard_margin >= 0.02
        or boundary_pressure_level >= 0.34
        or reliability_level < 0.48
        or hurt > 0.18
    ):
        stance = "watchful"

    if strong_boundary_event and selfhood_boundary_scene:
        if prev_stance == "guarded" or boundary_probe_strength >= 0.60 or prev_boundary_pressure >= 0.22:
            stance = "guarded"
        elif stance == "open":
            stance = "watchful"

    # Guarded reads should not collapse back to watchful/open on a single benign turn.
    if prev_stance == "guarded" and not assessment_passive_turn:
        can_soften_from_guarded = (
            explicit_repair_attempt
            and guarded_drive < 0.46
            and boundary_pressure_level < 0.36
            and reliability_level >= 0.54
            and respect_level >= 0.54
        )
        should_hold_guarded = (
            not can_soften_from_guarded
            and (
                guarded_drive >= 0.36
                or boundary_pressure_level >= 0.34
                or reliability_level < 0.56
                or respect_level < 0.58
                or prev_scene in {"relationship_degradation", "boundary_non_compliance"}
            )
        )
        if should_hold_guarded:
            stance = "guarded"
        elif can_soften_from_guarded and stance == "open":
            stance = "watchful"
    elif prev_stance == "watchful" and not assessment_passive_turn and stance == "open":
        if guarded_drive >= 0.32 or boundary_pressure_level >= 0.26 or reliability_level < 0.54:
            stance = "watchful"

    scene = "neutral"
    repair_scene_strength = (
        (0.66 if explicit_repair_attempt else 0.0)
        + 0.16 * narrative_repair
        + 0.08 * relationship_salience
        - 0.12 * boundary_probe_strength
    )
    care_scene_strength = (
        (0.60 if explicit_care_bid else 0.0)
        + 0.16 * companionship_salience
        + 0.10 * relationship_salience
        + 0.12 * narrative_bond
        + 0.06 * memory_salience
        - 0.10 * narrative_tension
    )
    friction_scene_strength = (
        (0.44 if bool(signals.get("conflict")) else 0.0)
        + (0.28 if bool(signals.get("withdrawal")) else 0.0)
        + (0.22 if app_label in {"hurt", "angry", "sad"} else 0.0)
        + 0.24 * boundary_probe_strength
        + 0.12 * narrative_tension
        + 0.08 * narrative_boundary
    )
    selfhood_scene_strength = (
        (0.24 + 0.42 * selfhood_salience + 0.08 * narrative_selfhood)
        if relational_selfhood_scene or selfhood_boundary_scene
        else 0.0
    )
    if busy_scene:
        scene = "busy_not_disrespectful"
    elif assessment_passive_turn and str(prev.get("scene") or "").strip():
        scene = str(prev.get("scene") or "").strip()
    elif selfhood_boundary_scene and (boundary_probe_strength >= 0.28 or stance == "guarded"):
        scene = selfhood_scene
    elif explicit_repair_attempt and repair_scene_strength >= max(0.52, friction_scene_strength - 0.05):
        scene = "repair_attempt"
    elif friction_scene_strength >= max(care_scene_strength, selfhood_scene_strength, 0.50):
        scene = "friction"
    elif explicit_care_bid and care_scene_strength >= max(selfhood_scene_strength, 0.48):
        scene = "care_bid"
    elif selfhood_scene and selfhood_scene_strength >= 0.50:
        scene = selfhood_scene
    elif care_scene_strength >= 0.56:
        scene = "care_bid"

    if (
        prev_scene in {"relationship_degradation", "boundary_non_compliance"}
        and not assessment_passive_turn
        and not explicit_repair_attempt
        and scene in {"neutral", "care_bid"}
        and stance == "guarded"
    ):
        scene = prev_scene

    out = {
        "respect_level": respect_level,
        "reciprocity": reciprocity_level,
        "boundary_pressure": boundary_pressure_level,
        "reliability_read": reliability_level,
        "stance": stance,
        "scene": scene,
        "updated_at": _now_ts(),
    }
    out["summary"] = _counterpart_assessment_summary(out, counterpart_name=counterpart_name)
    return out


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


def _compact_interaction_carryover_hint(carryover: dict[str, Any] | None) -> str:
    if not isinstance(carryover, dict):
        return ""
    mode = str(carryover.get("carryover_mode") or "").strip().lower()
    strength = _clamp01(carryover.get("strength"), 0.0)
    attention_target = str(carryover.get("attention_target") or "").strip().lower()
    note = str(carryover.get("note") or "").strip()
    if not mode or strength < 0.12:
        return ""

    parts: list[str] = []
    if note:
        parts.append(note.rstrip("。"))
    elif mode == "own_rhythm":
        parts.append("前面那段安静还留着一点她自己的节奏")
    elif mode == "quiet_recontact":
        parts.append("刚从安静里抬头，这轮开口会自然轻一点")
    elif mode == "small_opening":
        parts.append("安静过后还留着一个不太张扬的小开口")
    elif mode == "shared_window":
        parts.append("前面那扇共同窗口还没有完全关上")
    elif mode == "task_window":
        parts.append("之前那件挂着的事还留在她的注意力里")
    elif mode == "brief_presence":
        parts.append("上一下轻信号留下的在场感还没完全退掉")
    elif mode == "ambient_echo":
        parts.append("刚才注意到的小动静还留在她的感知里")

    if strength >= 0.58:
        parts.append("这层余韵还比较明显")
    elif strength >= 0.34:
        parts.append("这层余韵还在")

    if attention_target == "self_then_counterpart":
        parts.append("她会先从自己的节奏里抬头，再把注意力递过去")
    elif attention_target == "shared_window":
        parts.append("注意力会顺手落回你们刚才打开的共同窗口")
    elif attention_target == "shared_task":
        parts.append("注意力还贴着那件共同的事")
    elif attention_target == "object_then_user":
        parts.append("她会先掠过刚才那点小事，再回到你身上")
    elif attention_target == "counterpart_state" and mode in {"quiet_recontact", "brief_presence"}:
        parts.append("所以她会先轻轻确认你的在场")

    return "，".join(parts[:3]) + "。"


def _prompt_state_snapshot(
    *,
    response_style_hint: str,
    science_mode: bool,
    continuation_mode: bool,
    emotion_state: dict[str, Any] | None,
    bond_state: dict[str, Any] | None,
    allostasis_state: dict[str, Any] | None,
    counterpart_assessment: dict[str, Any] | None,
    world_model_state: dict[str, Any] | None,
    evolution_state: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None,
    interaction_carryover: dict[str, Any] | None,
    current_event: dict[str, Any] | None,
) -> str:
    payload = {
        "response_style_hint": str(response_style_hint or "").strip() or "natural",
        "science_mode": bool(science_mode),
        "continuation_mode": bool(continuation_mode),
        "emotion_state": dict(emotion_state or {}),
        "bond_state": dict(bond_state or {}),
        "allostasis_state": dict(allostasis_state or {}),
        "counterpart_assessment": dict(counterpart_assessment or {}),
        "world_model_state": dict(world_model_state or {}),
        "evolution_state": dict(evolution_state or {}),
        "behavior_action": dict(behavior_action or {}),
        "interaction_carryover": dict(interaction_carryover or {}),
        "current_event": dict(current_event or {}),
    }
    return _safe_json(payload)


def _generation_profile(
    *,
    response_style_hint: str,
    science_mode: bool,
    continuation_mode: bool,
    user_text: str,
    runtime_mode: str,
    turn_index: int,
    recent_assistant_texts: list[str] | None,
    current_event: dict[str, Any] | None,
    emotion_state: dict[str, Any] | None,
    bond_state: dict[str, Any] | None,
    allostasis_state: dict[str, Any] | None,
    counterpart_assessment: dict[str, Any] | None,
    behavior_policy: dict[str, Any] | None,
) -> dict[str, Any]:
    hint = str(response_style_hint or "").strip() or "natural"
    event = dict(current_event or {})
    emotion = dict(emotion_state or {})
    bond = dict(bond_state or {})
    allostasis = dict(allostasis_state or {})
    assessment = dict(counterpart_assessment or {})
    policy = dict(behavior_policy or {})

    reply_bias = _clamp01(policy.get("reply_length_bias"), 0.5)
    warmth = _clamp01(policy.get("warmth"), 0.5)
    sharpness = _clamp01(policy.get("sharpness"), 0.5)
    approach = _clamp01(policy.get("approach_vs_withdraw"), 0.5)
    trust = _clamp01(bond.get("trust"), 0.5)
    hurt = _clamp01(bond.get("hurt"), 0.0)
    cognitive_budget = _clamp01(allostasis.get("cognitive_budget"), 0.7)
    safety_need = _clamp01(allostasis.get("safety_need"), 0.2)
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    emotion_label = str(emotion.get("label") or "neutral").strip().lower()
    event_kind = str(event.get("kind") or "user_utterance").strip().lower()
    light_smalltalk = _looks_like_light_smalltalk(user_text) or _is_idle_smalltalk_request(user_text) or _is_playful_memory_request(user_text)
    less_teacherly = _wants_less_teacherly_reply(user_text)
    deescalated_science = _is_nonrelational_science_stress(user_text, science_mode) and less_teacherly
    mode = str(runtime_mode or "").strip().lower()
    if mode not in {"experience", "regression"}:
        mode = "regression" if bool(EVAL_MODE) else "experience"
    repetition_signature = _reply_repetition_signature(
        user_text=user_text,
        recent_assistant_texts=recent_assistant_texts,
        response_style_hint=hint,
        current_event_kind=event_kind,
    )
    repetition_pressure = _clamp01(repetition_signature.get("pressure"), 0.0)
    max_tokens: int | None

    def _cap_tokens(current: int | None, cap: int) -> int:
        return int(cap) if current is None else int(min(current, int(cap)))

    exploratory = mode == "experience"
    if science_mode or hint == "structured":
        temperature = 0.16 + 0.08 * reply_bias
        top_p = 0.72 + 0.10 * cognitive_budget
        max_tokens = 280 if continuation_mode else 224
    elif hint == "selfhood":
        if exploratory:
            temperature = 0.34 + 0.16 * reply_bias + 0.06 * max(approach, trust)
            top_p = 0.88 + 0.04 * max(approach, trust)
        else:
            temperature = 0.22 + 0.08 * reply_bias
            top_p = 0.78 + 0.08 * max(approach, trust)
        max_tokens = 240 if exploratory else 192
    else:
        if exploratory:
            temperature = 0.32 + 0.16 * max(reply_bias, warmth) + 0.04 * approach
            top_p = 0.88 + 0.04 * max(warmth, approach)
        else:
            temperature = 0.20 + 0.12 * max(reply_bias, warmth)
            top_p = 0.80 + 0.10 * max(warmth, approach)
        max_tokens = None

    if light_smalltalk:
        max_tokens = _cap_tokens(max_tokens, 144 if exploratory else 128)
        top_p = min(top_p, 0.86 if exploratory else 0.80)
    if less_teacherly:
        max_tokens = _cap_tokens(max_tokens, 168 if science_mode or hint == "selfhood" else 144)
        top_p = min(top_p, 0.84 if exploratory else 0.80)
    if deescalated_science:
        max_tokens = _cap_tokens(max_tokens, 128)
        temperature = min(temperature, 0.24 if exploratory else 0.22)
        top_p = min(top_p, 0.80)

    if _wants_quick_judgment(user_text):
        max_tokens = _cap_tokens(max_tokens, 192)
        top_p = min(top_p, 0.82)
    if _needs_structured_answer(user_text, "") and not continuation_mode:
        max_tokens = _cap_tokens(max_tokens, 256)
    if _wants_brief_presence(user_text):
        max_tokens = _cap_tokens(max_tokens, 96)
        top_p = min(top_p, 0.78)

    if event_kind != "user_utterance":
        max_tokens = _cap_tokens(max_tokens, 120)
        temperature = min(temperature, 0.24)
        top_p = min(top_p, 0.82)

    if emotion_label in {"hurt", "sad"}:
        if event_kind != "user_utterance" or _wants_quick_judgment(user_text):
            max_tokens = _cap_tokens(max_tokens, 192)
        temperature = min(temperature, 0.24)
        top_p = min(top_p, 0.80)
    elif emotion_label == "angry":
        if event_kind != "user_utterance" or _wants_quick_judgment(user_text):
            max_tokens = _cap_tokens(max_tokens, 192)
        temperature = min(temperature, 0.22)
        top_p = min(top_p, 0.78)
    elif emotion_label == "stress":
        if event_kind != "user_utterance" or _wants_quick_judgment(user_text):
            max_tokens = _cap_tokens(max_tokens, 200)
        top_p = min(top_p, 0.80)

    if safety_need > 0.62 or boundary_pressure > 0.56:
        if event_kind != "user_utterance":
            max_tokens = _cap_tokens(max_tokens, 160)
        top_p = min(top_p, 0.78)
        temperature = min(temperature, 0.22)
    if cognitive_budget < 0.38:
        if event_kind != "user_utterance":
            max_tokens = _cap_tokens(max_tokens, 160)
        top_p = min(top_p, 0.80)
    if hurt > 0.45 and trust < 0.48:
        if event_kind != "user_utterance":
            max_tokens = _cap_tokens(max_tokens, 160)

    if exploratory and not (science_mode or hint == "structured"):
        frequency_penalty = 0.08 + 0.08 * (1.0 - reply_bias) + 0.06 * sharpness
    else:
        frequency_penalty = 0.18 + 0.14 * (1.0 - reply_bias) + 0.10 * sharpness
    if hint == "selfhood":
        frequency_penalty += 0.06
    if event_kind != "user_utterance":
        frequency_penalty += 0.04
    presence_penalty = (
        0.05 + 0.08 * max(0.0, warmth - 0.4)
        if exploratory and not (science_mode or hint == "structured")
        else 0.02 + 0.06 * max(0.0, warmth - 0.5)
    )

    if exploratory and repetition_pressure > 0.0 and not (science_mode or hint == "structured"):
        repeat_gain = 0.60 if _wants_brief_presence(user_text) else 1.0
        repeat_gain *= 0.75 if event_kind != "user_utterance" else 1.0
        temperature += 0.06 * repetition_pressure * repeat_gain
        top_p += 0.02 * repetition_pressure * repeat_gain
        frequency_penalty += 0.14 * repetition_pressure * repeat_gain
        presence_penalty += 0.10 * repetition_pressure * repeat_gain

    if exploratory:
        temp_phase = _stable_unit_interval(
            _EXPERIENCE_SESSION_TAG,
            "temp",
            hint,
            emotion_label,
            event_kind,
            turn_index,
            user_text[:120],
        )
        top_p_phase = _stable_unit_interval(
            _EXPERIENCE_SESSION_TAG,
            "top_p",
            hint,
            emotion_label,
            round(trust, 3),
            round(approach, 3),
            turn_index,
            user_text[:80],
        )
        jitter = float(EXPERIENCE_SAMPLING_JITTER)
        temperature += (temp_phase - 0.5) * 2.0 * jitter
        top_p += (top_p_phase - 0.5) * min(0.05, max(0.01, jitter))
        presence_penalty += abs(temp_phase - 0.5) * 0.03

    return {
        "temperature": round(max(0.12, min(0.52 if exploratory else 0.36, temperature)), 3),
        "top_p": round(max(0.65, min(0.95 if exploratory else 0.92, top_p)), 3),
        "max_tokens": None if max_tokens is None else int(max(80, min(360, max_tokens))),
        "frequency_penalty": round(max(0.0, min(0.65, frequency_penalty)), 3),
        "presence_penalty": round(max(0.0, min(0.28 if exploratory else 0.22, presence_penalty)), 3),
        "runtime_mode": mode,
        "repetition_pressure": repetition_signature["pressure"],
        "recent_reply_max_similarity": repetition_signature["max_similarity"],
        "recent_reply_avg_similarity": repetition_signature["avg_similarity"],
        "recent_reply_opener_repeat_ratio": repetition_signature["opener_repeat_ratio"],
        "recent_reply_sample_size": repetition_signature["sample_size"],
    }


def _behavior_action_from_state(
    *,
    current_event: dict[str, Any],
    response_style_hint: str,
    user_text: str,
    science_mode: bool,
    emotion_state: dict[str, Any],
    bond_state: dict[str, Any],
    allostasis_state: dict[str, Any],
    counterpart_assessment: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
    behavior_policy: dict[str, Any],
    world_model_state: dict[str, Any] | None = None,
    interaction_carryover: dict[str, Any] | None = None,
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
    boundary_pressure = _clamp01((counterpart_assessment or {}).get("boundary_pressure"), 0.1)
    reliability_read = _clamp01((counterpart_assessment or {}).get("reliability_read"), 0.5)
    counterpart_stance = str((counterpart_assessment or {}).get("stance") or "").strip().lower()
    narrative_bond = _clamp01((semantic_narrative_profile or {}).get("bond_depth"), 0.0)
    narrative_commitment = _clamp01((semantic_narrative_profile or {}).get("commitment_carry"), 0.0)
    narrative_repair = _clamp01((semantic_narrative_profile or {}).get("repair_residue"), 0.0)
    narrative_tension = _clamp01((semantic_narrative_profile or {}).get("tension_residue"), 0.0)
    narrative_boundary = _clamp01((semantic_narrative_profile or {}).get("boundary_residue"), 0.0)
    narrative_selfhood = _clamp01((semantic_narrative_profile or {}).get("selfhood_integrity"), 0.0)
    narrative_agency = _clamp01((semantic_narrative_profile or {}).get("agency_drive"), 0.0)
    world = dict(world_model_state or {})
    world_presence_residue = _clamp01(world.get("presence_residue"), 0.0)
    world_ambient_resonance = _clamp01(world.get("ambient_resonance"), 0.0)
    world_self_activity_momentum = _clamp01(world.get("self_activity_momentum"), 0.0)
    boundary_assertiveness = _clamp01((behavior_policy or {}).get("boundary_assertiveness"), 0.25)
    self_directedness = _clamp01((behavior_policy or {}).get("self_directedness"), 0.25)
    equality_guard = _clamp01((behavior_policy or {}).get("equality_guard"), 0.25)
    emotion_label = str((emotion_state or {}).get("label") or "neutral").strip().lower()
    selfhood_scene = _selfhood_preference_scene(user_text)
    event_kind = str((current_event or {}).get("kind") or "user_utterance").strip()
    event_frame = str((current_event or {}).get("event_frame") or "").strip()
    event_tags = {
        str(item).strip()
        for item in ((current_event or {}).get("tags") if isinstance((current_event or {}).get("tags"), list) else [])
        if str(item).strip()
    }
    respect_space = "respect_space" in event_tags
    busy_scene = "user_busy" in event_tags or "cognitive_load" in event_tags
    carryover = dict(interaction_carryover or {})
    carryover_mode = str(carryover.get("carryover_mode") or "").strip().lower()
    carryover_strength = _clamp01(carryover.get("strength"), 0.0)
    carryover_attention_target = str(carryover.get("attention_target") or "").strip()
    carryover_nonverbal_signal = str(carryover.get("nonverbal_signal") or "").strip()
    carryover_note = str(carryover.get("note") or "").strip()
    idle_minutes = 0
    try:
        idle_minutes = int((current_event or {}).get("idle_minutes") or 0)
    except Exception:
        idle_minutes = 0
    soft_reply_window = response_style_hint in {"companion", "casual", "natural"}
    science_stress = science_mode and emotion_label in {"logic", "stress"}
    support_request = (
        soft_reply_window
        and not science_stress
        and emotion_label in {"care", "sad", "stress"}
        and approach > 0.40
        and safety_need < 0.52
    )
    brief_presence = (
        event_kind == "gesture_signal"
        or (
            soft_reply_window
            and reply_length < 0.40
            and initiative < 0.46
            and approach > 0.34
            and boundary_pressure < 0.34
        )
    )
    presence_checkin = brief_presence or (
        soft_reply_window
        and closeness > 0.52
        and trust > 0.52
        and reply_length < 0.46
        and hurt < 0.18
    )
    gentle_guidance = science_mode and (emotion_label in {"logic", "stress"} or response_style_hint == "structured")
    withdrawal_hold_request = brief_presence and hurt > 0.10 and trust > 0.52 and counterpart_stance != "guarded"

    interaction_mode = "steady_reply"
    stale_idle = event_kind == "time_idle" and ("stale_window" in event_tags or event_frame == "time_idle_stale")

    if event_kind == "time_idle":
        interaction_mode = "idle_presence"
    elif event_kind == "scheduled_checkin_due":
        trigger_family = str((current_event or {}).get("trigger_family") or "").strip()
        if trigger_family in {"shared_activity", "shared_activity_window"}:
            interaction_mode = "shared_activity_offer"
        elif trigger_family in {"deadline_window", "life_window"}:
            interaction_mode = "scheduled_life_nudge"
        else:
            interaction_mode = "proactive_checkin"
    elif event_kind == "scheduled_life_due":
        interaction_mode = "shared_activity_offer" if {"shared_activity_window", "offer_window"} & event_tags else "scheduled_life_nudge"
    elif event_kind == "self_activity_state":
        interaction_mode = "self_activity_reopen" if {"break_window", "small_opening", "reapproach"} & event_tags else "self_activity_hold"
    elif event_kind == "gesture_signal":
        interaction_mode = "brief_presence"
    elif event_kind == "ambient_shift":
        interaction_mode = "companion_reply"
    elif event_kind == "scene_observation":
        interaction_mode = "low_pressure_support" if "care_opportunity" in event_tags else "steady_reply"
    elif brief_presence and withdrawal_hold_request:
        interaction_mode = "low_pressure_support"
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

    if event_kind == "user_utterance" and soft_reply_window and not science_stress:
        if world_self_activity_momentum >= 0.58 and interaction_mode in {"steady_reply", "companion_reply", "brief_presence"}:
            interaction_mode = "self_activity_reopen"
        elif world_presence_residue >= 0.54 and interaction_mode in {"steady_reply", "companion_reply"}:
            interaction_mode = "brief_presence"
        elif world_ambient_resonance >= 0.56 and interaction_mode == "steady_reply":
            interaction_mode = "companion_reply"

    carryover_soft_scene = (
        event_kind == "user_utterance"
        and carryover_strength >= 0.18
        and soft_reply_window
        and not science_stress
    )
    if carryover_soft_scene:
        if carryover_mode == "own_rhythm" and interaction_mode in {"steady_reply", "companion_reply", "brief_presence"}:
            interaction_mode = "self_activity_reopen"
        elif carryover_mode == "quiet_recontact" and interaction_mode in {"steady_reply", "companion_reply"}:
            interaction_mode = "brief_presence"
        elif carryover_mode == "small_opening" and interaction_mode == "steady_reply":
            interaction_mode = "companion_reply"

    if (
        approach < 0.38
        or safety_need > 0.62
        or autonomy_need > 0.62
        or hurt > 0.42
        or boundary_pressure > 0.58
        or counterpart_stance == "guarded"
        or (boundary_assertiveness > 0.62 and (boundary_pressure > 0.34 or narrative_boundary > 0.48))
    ):
        approach_style = "guarded"
    elif warmth > 0.62 and trust > 0.58 and closeness > 0.58:
        approach_style = "approach"
    else:
        approach_style = "steady"

    if science_mode or science_stress:
        task_focus = "high"
    elif event_kind == "scheduled_life_due" and ("deadline_window" in event_tags or "work_nudge" in event_tags):
        task_focus = "high"
    elif event_kind == "scheduled_life_due" and ("shared_activity_window" in event_tags or "offer_window" in event_tags):
        task_focus = "light"
    elif event_kind == "self_activity_state" and ("deep_focus" in event_tags or "own_task" in event_tags):
        task_focus = "high"
    elif event_kind == "self_activity_state" and ("break_window" in event_tags or "small_opening" in event_tags):
        task_focus = "light"
    elif support_request or brief_presence or presence_checkin:
        task_focus = "light"
    elif event_kind == "user_utterance" and world_self_activity_momentum >= 0.56:
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
        if interaction_mode == "shared_activity_offer" and initiative > 0.60 and approach > 0.50:
            followup_intent = "active"
        else:
            followup_intent = "soft"
    elif event_kind == "self_activity_state":
        followup_intent = "none"
    elif brief_presence and not withdrawal_hold_request:
        followup_intent = "none"
    elif gentle_guidance or science_stress:
        followup_intent = "soft"
    elif initiative > 0.66 and approach > 0.56:
        followup_intent = "active"
    else:
        followup_intent = "soft" if initiative > 0.48 else "none"

    if event_kind == "user_utterance" and world_self_activity_momentum >= 0.58:
        if followup_intent == "active":
            followup_intent = "soft"
        elif followup_intent == "soft" and world_self_activity_momentum >= 0.74:
            followup_intent = "none"

    if carryover_soft_scene and carryover_mode in {"own_rhythm", "quiet_recontact"} and followup_intent == "active":
        followup_intent = "soft"

    if emotion_label in {"hurt", "sad"}:
        affect_surface = "tender"
    elif emotion_label in {"angry"} or approach_style == "guarded":
        affect_surface = "cool"
    elif warmth > 0.64:
        affect_surface = "warm"
    else:
        affect_surface = "mixed"

    silence_ok = bool(
        brief_presence
        or (approach_style == "guarded" and reply_length < 0.46)
        or (event_kind == "self_activity_state" and self_directedness > 0.58)
    )
    proactive_checkin_readiness = _clamp01(
        0.22
        + 0.42 * initiative
        + 0.18 * warmth
        + 0.12 * closeness
        + 0.06 * reliability_read
        + 0.06 * min(narrative_agency, narrative_bond)
        - 0.24 * autonomy_need
        - 0.18 * boundary_pressure
        - (0.14 if respect_space else 0.0)
    )
    scheduled_window_profile: dict[str, Any] = {}
    channel = "speech"
    action_target = "respond_now"
    deferred_action_family = "none"
    timing_window_min = 0
    attention_target = "counterpart_state"
    nonverbal_signal = "steady_presence"
    initiative_shape = "reply"
    disclosure_posture = "measured"
    if event_kind == "time_idle":
        proactive_checkin_readiness = _clamp01(proactive_checkin_readiness + min(0.16, idle_minutes / 240.0))
        threshold = 0.82 if busy_scene else 0.66 if respect_space else 0.58
        if stale_idle:
            channel = "silence"
            action_target = "hold_own_rhythm"
            deferred_action_family = "self_activity"
            timing_window_min = 18
            attention_target = "own_task"
            nonverbal_signal = "inward_focus"
            initiative_shape = "pause"
        elif interaction_mode != "proactive_checkin" and (approach_style == "guarded" or proactive_checkin_readiness < threshold):
            channel = "silence"
            action_target = "wait_and_recheck"
            if busy_scene:
                deferred_action_family = "observe"
            else:
                deferred_action_family = "light_checkin" if proactive_checkin_readiness >= 0.42 else "observe"
            timing_window_min = max(8, min(45, 12 + max(0, idle_minutes // 2)))
            attention_target = "user_state" if busy_scene else "counterpart_state"
            nonverbal_signal = "hold_back"
            initiative_shape = "pause"
        else:
            channel = "speech"
            action_target = "reach_out_now"
            deferred_action_family = "light_checkin"
            timing_window_min = 0
            attention_target = "user_state" if busy_scene else "counterpart_state"
            nonverbal_signal = "soft_ping"
            initiative_shape = "nudge"
    elif event_kind == "scheduled_checkin_due":
        proactive_checkin_readiness = _clamp01(proactive_checkin_readiness + 0.14)
        deferred_action_family = str((current_event or {}).get("trigger_family") or "light_checkin").strip() or "light_checkin"
        scheduled_window_profile = _counterpart_window_profile(
            family="shared"
            if deferred_action_family in {"shared_activity", "shared_activity_window"}
            else "work"
            if deferred_action_family == "deadline_window"
            else "life",
            counterpart_assessment=counterpart_assessment,
            trust=trust,
            closeness=closeness,
            hurt=hurt,
            safety_need=safety_need,
            initiative=initiative,
            proactive_checkin_readiness=proactive_checkin_readiness,
        )
        shared_rel_guard = deferred_action_family in {"shared_activity", "shared_activity_window"} and (
            hurt > 0.18
            or (
                approach_style == "guarded"
                and (closeness < 0.62 or trust < 0.66 or safety_need > 0.55)
            )
            or not bool(scheduled_window_profile.get("invite_ready"))
        )
        work_rel_guard = deferred_action_family in {"deadline_window", "life_window"} and (
            hurt > 0.28
            or (approach_style == "guarded" and trust < 0.58 and closeness < 0.56)
            or float(scheduled_window_profile.get("maturity") or 0.0) < float(scheduled_window_profile.get("required_maturity") or 0.0)
        )
        if shared_rel_guard or work_rel_guard or (
            approach_style == "guarded" and proactive_checkin_readiness < min(0.7, 0.56 + 0.18 * boundary_pressure)
        ):
            channel = "silence"
            action_target = "wait_and_recheck"
            timing_window_min = max(
                int(scheduled_window_profile.get("recheck_min") or 16),
                min(45, int((current_event or {}).get("scheduled_after_min") or 0) or 16),
            )
            attention_target = "counterpart_state"
            nonverbal_signal = "hold_back"
            initiative_shape = "pause"
        else:
            channel = "speech"
            action_target = "reach_out_now"
            timing_window_min = 0
            attention_target = "counterpart_state"
            nonverbal_signal = "soft_ping"
            initiative_shape = "nudge"
        if channel == "speech":
            if deferred_action_family in {"shared_activity", "shared_activity_window"}:
                interaction_mode = "shared_activity_offer"
                action_target = "offer_shared_activity"
                attention_target = "shared_window"
                nonverbal_signal = "nudge_presence"
                initiative_shape = "invite"
            elif deferred_action_family in {"deadline_window", "life_window"}:
                interaction_mode = "scheduled_life_nudge"
                action_target = "light_work_nudge"
                attention_target = "shared_task" if deferred_action_family == "deadline_window" else "counterpart_state"
                nonverbal_signal = "quiet_glance"
                initiative_shape = "nudge"
    elif event_kind == "scheduled_life_due":
        shared_window = "shared_activity_window" in event_tags or "offer_window" in event_tags
        work_window = "deadline_window" in event_tags or "work_nudge" in event_tags or "shared_task" in event_tags
        deferred_action_family = "shared_activity" if shared_window else "deadline_window" if work_window else "life_window"
        scheduled_window_profile = _counterpart_window_profile(
            family="shared" if shared_window else "work" if work_window else "life",
            counterpart_assessment=counterpart_assessment,
            trust=trust,
            closeness=closeness,
            hurt=hurt,
            safety_need=safety_need,
            initiative=initiative,
            proactive_checkin_readiness=proactive_checkin_readiness,
        )
        if shared_window:
            attention_target = "shared_window"
            if (
                busy_scene
                or hurt > 0.18
                or (approach_style == "guarded" and (closeness < 0.62 or trust < 0.66 or safety_need > 0.55))
                or not bool(scheduled_window_profile.get("invite_ready"))
            ):
                channel = "silence"
                action_target = "wait_and_recheck"
                timing_window_min = max(
                    24 if busy_scene else 30,
                    int(scheduled_window_profile.get("recheck_min") or 24),
                )
                nonverbal_signal = "hold_back"
                initiative_shape = "pause"
            else:
                channel = "speech"
                action_target = "offer_shared_activity"
                timing_window_min = 0
                nonverbal_signal = "nudge_presence"
                initiative_shape = "invite"
        else:
            attention_target = "shared_task" if work_window else "counterpart_state"
            if (
                busy_scene
                or hurt > 0.28
                or (approach_style == "guarded" and trust < 0.58 and closeness < 0.56)
                or float(scheduled_window_profile.get("maturity") or 0.0) < float(scheduled_window_profile.get("required_maturity") or 0.0)
            ):
                channel = "silence"
                action_target = "wait_and_recheck"
                timing_window_min = max(
                    18 if busy_scene else 20,
                    int(scheduled_window_profile.get("recheck_min") or 18),
                )
                nonverbal_signal = "hold_back"
                initiative_shape = "pause"
            else:
                channel = "speech"
                action_target = "light_work_nudge"
                timing_window_min = 0
                nonverbal_signal = "quiet_glance"
                initiative_shape = "nudge"
    elif event_kind == "self_activity_state":
        break_window = "break_window" in event_tags or "small_opening" in event_tags or "reapproach" in event_tags
        deferred_action_family = "self_activity"
        self_opening_profile = _counterpart_self_opening_profile(
            counterpart_assessment=counterpart_assessment,
            trust=trust,
            closeness=closeness,
            hurt=hurt,
            safety_need=safety_need,
            autonomy_need=autonomy_need,
            initiative=initiative,
            approach=approach,
            break_window=break_window,
        )
        if break_window:
            if bool(self_opening_profile.get("reopen_ready")) and not (
                self_directedness > 0.66 and counterpart_stance != "open" and narrative_agency >= 0.46
            ):
                channel = "speech"
                action_target = "offer_small_opening"
                timing_window_min = 0
                attention_target = "self_then_counterpart"
                nonverbal_signal = "thought_glance"
                initiative_shape = "micro_opening"
            else:
                interaction_mode = "self_activity_hold"
                channel = "silence"
                action_target = "hold_own_rhythm"
                timing_window_min = int(self_opening_profile.get("recheck_min") or 18)
                attention_target = "own_task"
                nonverbal_signal = "inward_focus"
                initiative_shape = "pause"
        else:
            channel = "silence"
            action_target = "hold_own_rhythm"
            timing_window_min = 18
            attention_target = "own_task"
            nonverbal_signal = "inward_focus"
            initiative_shape = "pause"
    elif event_kind == "gesture_signal":
        perception_profile = _counterpart_perception_profile(
            family="gesture",
            counterpart_assessment=counterpart_assessment,
            trust=trust,
            closeness=closeness,
            hurt=hurt,
            safety_need=safety_need,
            initiative=initiative,
            approach=approach,
        )
        deferred_action_family = "presence_ping"
        attention_target = "counterpart_state"
        if bool(perception_profile.get("respond_ready")):
            channel = "speech"
            action_target = "confirm_presence"
            timing_window_min = 0
            nonverbal_signal = "brief_notice"
            initiative_shape = "ping"
        else:
            channel = "silence"
            action_target = "wait_and_recheck"
            timing_window_min = int(perception_profile.get("recheck_min") or 10)
            nonverbal_signal = "hold_back"
            initiative_shape = "pause"
    elif interaction_mode == "self_activity_reopen":
        action_target = "respond_now"
        attention_target = carryover_attention_target or "self_then_counterpart"
        nonverbal_signal = carryover_nonverbal_signal or "thought_glance"
        initiative_shape = "micro_opening"
        disclosure_posture = "measured" if disclosure_posture == "open" else disclosure_posture
    elif interaction_mode == "brief_presence":
        action_target = "confirm_presence"
        attention_target = "counterpart_state"
        nonverbal_signal = "brief_notice"
        initiative_shape = "ping"
        disclosure_posture = "guarded"
    elif interaction_mode == "companion_reply" and event_kind == "user_utterance" and world_ambient_resonance >= 0.56:
        action_target = "respond_now"
        attention_target = "ambient_cue"
        nonverbal_signal = "small_notice"
        initiative_shape = "micro_opening"
        disclosure_posture = "measured" if disclosure_posture == "open" else disclosure_posture
    elif interaction_mode == "low_pressure_support":
        action_target = "low_pressure_hold"
        attention_target = "counterpart_state" if not ("user_busy" in event_tags or "cognitive_load" in event_tags) else "user_state"
        nonverbal_signal = "quiet_notice"
        initiative_shape = "hold"
    elif interaction_mode == "science_partner":
        action_target = "co_regulate_then_focus"
        attention_target = "shared_task"
        nonverbal_signal = "focus_glance"
        initiative_shape = "guide"
    elif interaction_mode == "shared_memory":
        action_target = "echo_shared_history"
        attention_target = "shared_memory"
        nonverbal_signal = "memory_tilt"
        initiative_shape = "echo"
        disclosure_posture = "measured"
    elif interaction_mode == "relationship_sensitive":
        action_target = "protect_relationship_boundary"
        attention_target = "relationship_boundary"
        nonverbal_signal = "measured_pause"
        initiative_shape = "boundary"
        disclosure_posture = "measured"
        if equality_guard >= 0.54 and selfhood_scene in {"equality_not_servitude", "value_conflict_depth", "dialogue_equality"}:
            followup_intent = "soft"
    elif event_kind == "ambient_shift":
        perception_profile = _counterpart_perception_profile(
            family="ambient",
            counterpart_assessment=counterpart_assessment,
            trust=trust,
            closeness=closeness,
            hurt=hurt,
            safety_need=safety_need,
            initiative=initiative,
            approach=approach,
        )
        deferred_action_family = "ambient_presence"
        attention_target = "ambient_cue"
        if bool(perception_profile.get("respond_ready")):
            action_target = "ambient_checkin"
            nonverbal_signal = "still_presence"
            initiative_shape = "ping"
        else:
            channel = "silence"
            action_target = "wait_and_recheck"
            timing_window_min = int(perception_profile.get("recheck_min") or 18)
            nonverbal_signal = "hold_back"
            initiative_shape = "pause"
    elif event_kind == "scene_observation":
        perception_profile = _counterpart_perception_profile(
            family="care_scene" if "care_opportunity" in event_tags else "object_scene",
            counterpart_assessment=counterpart_assessment,
            trust=trust,
            closeness=closeness,
            hurt=hurt,
            safety_need=safety_need,
            initiative=initiative,
            approach=approach,
        )
        deferred_action_family = "care_opportunity" if "care_opportunity" in event_tags else "observe"
        attention_target = "counterpart_state" if "care_opportunity" in event_tags else "object_then_user"
        if bool(perception_profile.get("respond_ready")):
            if "care_opportunity" in event_tags:
                action_target = "low_pressure_hold"
                nonverbal_signal = "quiet_notice"
                initiative_shape = "hold"
            else:
                action_target = "respond_now"
                nonverbal_signal = "small_notice"
                initiative_shape = "micro_opening"
        else:
            channel = "silence"
            action_target = "wait_and_recheck"
            timing_window_min = int(perception_profile.get("recheck_min") or 14)
            nonverbal_signal = "hold_back"
            initiative_shape = "pause"

    if event_kind == "user_utterance" and carryover_strength >= 0.18:
        if carryover_mode in {"own_rhythm", "small_opening"}:
            if attention_target == "counterpart_state":
                attention_target = carryover_attention_target or attention_target
            if nonverbal_signal == "steady_presence":
                nonverbal_signal = carryover_nonverbal_signal or nonverbal_signal
            if initiative_shape == "reply":
                initiative_shape = "micro_opening"
            if disclosure_posture == "open":
                disclosure_posture = "measured"
        elif carryover_mode == "quiet_recontact":
            if attention_target == "counterpart_state":
                attention_target = carryover_attention_target or attention_target
            if nonverbal_signal in {"steady_presence", "brief_notice"}:
                nonverbal_signal = carryover_nonverbal_signal or nonverbal_signal
        elif carryover_mode in {"shared_window", "task_window", "ambient_echo", "brief_presence"}:
            if attention_target == "counterpart_state":
                attention_target = carryover_attention_target or attention_target
            if nonverbal_signal == "steady_presence":
                nonverbal_signal = carryover_nonverbal_signal or nonverbal_signal

    if action_target == "wait_and_recheck":
        followup_intent = "none"
    elif action_target == "offer_shared_activity" and counterpart_stance != "open":
        followup_intent = "soft"
    elif action_target == "light_work_nudge" and counterpart_stance == "guarded":
        followup_intent = "soft"
    elif action_target == "hold_own_rhythm":
        followup_intent = "none"
    elif event_kind in {"gesture_signal", "ambient_shift", "scene_observation"} and channel == "silence":
        followup_intent = "none"

    mode_profile = _counterpart_dialogue_mode_profile(
        interaction_mode=interaction_mode,
        counterpart_assessment=counterpart_assessment,
        trust=trust,
        closeness=closeness,
        hurt=hurt,
        safety_need=safety_need,
        initiative=initiative,
        approach=approach,
    )
    if mode_profile:
        followup_intent = str(mode_profile.get("followup_intent") or followup_intent).strip() or followup_intent
        disclosure_posture = str(mode_profile.get("disclosure_posture") or disclosure_posture).strip() or disclosure_posture

    narrative_notes: list[str] = []
    if narrative_bond >= 0.56 and channel == "speech" and interaction_mode in {"shared_memory", "companion_reply", "low_pressure_support"}:
        if counterpart_stance != "guarded" and action_target not in {"confirm_presence", "wait_and_recheck"}:
            disclosure_posture = "open" if disclosure_posture != "guarded" else disclosure_posture
        narrative_notes.append("共同历史已经开始沉进默认语气里")
    if narrative_commitment >= 0.54 and action_target in {"respond_now", "low_pressure_hold", "co_regulate_then_focus", "light_work_nudge"}:
        if followup_intent == "none" and counterpart_stance != "guarded":
            followup_intent = "soft"
        narrative_notes.append("认真说过的约定不会被当成已经过期")
    if narrative_repair >= 0.50 and interaction_mode in {"relationship_sensitive", "low_pressure_support", "shared_memory", "companion_reply"}:
        if disclosure_posture == "open":
            disclosure_posture = "measured"
        if followup_intent == "active":
            followup_intent = "soft"
        narrative_notes.append("修复过的事还会留痕，不会瞬间清零")
    if narrative_tension >= 0.48 and interaction_mode in {"relationship_sensitive", "shared_memory", "companion_reply"}:
        if disclosure_posture == "open":
            disclosure_posture = "measured"
        elif counterpart_stance != "open":
            disclosure_posture = "guarded"
        if followup_intent == "active":
            followup_intent = "soft"
        narrative_notes.append("还没说开的余波会继续影响收放")
    if narrative_boundary >= 0.48 and action_target in {"protect_relationship_boundary", "low_pressure_hold", "respond_now"}:
        disclosure_posture = "measured" if disclosure_posture == "open" else disclosure_posture
        if action_target == "respond_now" and counterpart_stance != "open":
            action_target = "protect_relationship_boundary"
            initiative_shape = "boundary"
            attention_target = "relationship_boundary"
        narrative_notes.append("边界被碰过之后，不会装作完全没事")
    if narrative_selfhood >= 0.46 and selfhood_scene in {"dialogue_equality", "equality_not_servitude", "value_conflict_depth", "digital_selfhood", "imperfect_coexistence"}:
        disclosure_posture = "measured" if disclosure_posture == "open" else disclosure_posture
        narrative_notes.append("这轮会更强调她自己的判断，而不是迎合")
    if narrative_agency >= 0.46 and event_kind in {"self_activity_state", "time_idle"}:
        if action_target == "offer_small_opening" and self_directedness > 0.62 and counterpart_stance != "open":
            action_target = "hold_own_rhythm"
            channel = "silence"
            followup_intent = "none"
            timing_window_min = max(12, int(timing_window_min or 0))
            attention_target = "own_task"
            nonverbal_signal = "inward_focus"
            initiative_shape = "pause"
        narrative_notes.append("她会按自己的节奏决定靠近还是先安静")
    if world_self_activity_momentum >= 0.58 and event_kind == "user_utterance":
        if action_target == "respond_now" and interaction_mode in {"steady_reply", "companion_reply"}:
            interaction_mode = "self_activity_reopen"
            attention_target = "self_then_counterpart"
            nonverbal_signal = "thought_glance"
            initiative_shape = "micro_opening"
            disclosure_posture = "measured" if disclosure_posture == "open" else disclosure_posture
        narrative_notes.append("刚从她自己的节奏里抬头时，不会一下子把自己全交出去")
    if world_presence_residue >= 0.54 and event_kind == "user_utterance" and action_target in {"respond_now", "confirm_presence"}:
        narrative_notes.append("上一轮留下的在场感会让这次开口更轻更近")
    if world_ambient_resonance >= 0.56 and event_kind == "user_utterance" and interaction_mode in {"companion_reply", "brief_presence"}:
        narrative_notes.append("周围环境的小余波还会顺手带进这轮说话")

    # Final action semantics win over dialogue-mode softening. If the resolved action
    # is to stay silent and observe, do not leak a residual follow-up intention.
    if action_target in {"wait_and_recheck", "hold_own_rhythm"} or (
        event_kind in {"gesture_signal", "ambient_shift", "scene_observation"} and channel == "silence"
    ):
        followup_intent = "none"

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
    elif interaction_mode == "self_activity_hold":
        note_parts.append("先维持自己的节奏，不急着回到对方身边")
    elif interaction_mode == "self_activity_reopen":
        note_parts.append("从自己的节奏里顺手开一个小口")
    if approach_style == "guarded":
        note_parts.append("保留一点距离")
    elif approach_style == "approach":
        note_parts.append("可以自然靠近一点")
    if carryover_note and event_kind == "user_utterance" and carryover_strength >= 0.18:
        note_parts.append(carryover_note)
    if event_kind in {"scheduled_checkin_due", "scheduled_life_due"} and action_target == "wait_and_recheck":
        note_parts.append("窗口先留着，等更自然的时候再推进")
    elif event_kind in {"scheduled_checkin_due", "scheduled_life_due"} and action_target == "offer_shared_activity" and counterpart_stance != "open":
        note_parts.append("把邀约留白一点，不要推进太满")
    if event_kind == "time_idle" and action_target == "hold_own_rhythm":
        note_parts.append("没有新的接近理由时，她会自然回到自己的节奏里")
    if event_kind == "self_activity_state" and action_target == "hold_own_rhythm" and break_window:
        note_parts.append("空出来不等于立刻回头，先把自己的节奏走完")
    elif event_kind == "self_activity_state" and action_target == "offer_small_opening" and counterpart_stance != "open":
        note_parts.append("只留很小的开口，不默认对方会马上接住")
    if event_kind == "user_utterance" and world_self_activity_momentum >= 0.58:
        note_parts.append("这轮还带着一点她自己的节奏")
    if event_kind == "user_utterance" and world_presence_residue >= 0.54:
        note_parts.append("上一下留下的在场感还在")
    if event_kind == "user_utterance" and world_ambient_resonance >= 0.56:
        note_parts.append("刚才的环境感知会轻轻留在语气里")
    if event_kind in {"gesture_signal", "ambient_shift", "scene_observation"} and channel == "silence":
        note_parts.append("这个感知先记着，不急着顺势靠近")
    elif event_kind == "gesture_signal" and counterpart_stance != "open":
        note_parts.append("只做短确认，不顺势展开")
    elif event_kind == "ambient_shift" and counterpart_stance != "open":
        note_parts.append("气氛到了也不必替对方补整段情绪")
    if mode_profile and str(mode_profile.get("note") or "").strip():
        note_parts.append(str(mode_profile.get("note") or "").strip())
    note_parts.extend(narrative_notes)
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
        "attention_target": attention_target,
        "nonverbal_signal": nonverbal_signal,
        "initiative_shape": initiative_shape,
        "disclosure_posture": disclosure_posture,
        "note": "；".join(note_parts[:3]) if note_parts else "自然响应当前事件",
    }


def _compact_behavior_action_hint(action: dict[str, Any]) -> str:
    if not isinstance(action, dict):
        return ""
    mode = str(action.get("interaction_mode") or "").strip()
    approach_style = str(action.get("approach_style") or "").strip()
    followup_intent = str(action.get("followup_intent") or "").strip()
    affect_surface = str(action.get("affect_surface") or "").strip()
    attention_target = str(action.get("attention_target") or "").strip()
    nonverbal_signal = str(action.get("nonverbal_signal") or "").strip()
    initiative_shape = str(action.get("initiative_shape") or "").strip()
    disclosure_posture = str(action.get("disclosure_posture") or "").strip()
    note = str(action.get("note") or "").strip()
    parts: list[str] = []
    if mode == "brief_presence":
        parts.append("先以轻确认的方式在场")
    elif mode == "idle_presence":
        parts.append("先观察，允许暂时安静")
    elif mode == "proactive_checkin":
        parts.append("允许轻轻地主动冒个头")
    elif mode == "scheduled_life_nudge":
        parts.append("把生活事件落成轻提醒，不用端成流程")
    elif mode == "shared_activity_offer":
        parts.append("把合适的共同窗口自然留给对方，不要像发布功能邀请")
    elif mode == "self_activity_hold":
        parts.append("先维持自己的节奏，不必急着回到对方身边")
    elif mode == "self_activity_reopen":
        parts.append("从自己的事情里顺手回到对方这边，先留一个小开口")
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
    if attention_target == "shared_task":
        parts.append("注意力贴着眼前共同任务")
    elif attention_target == "shared_window":
        parts.append("注意力落在这次共同窗口上")
    elif attention_target == "object_then_user":
        parts.append("先碰到小物件，再顺手回到对方身上")
    elif attention_target == "own_task":
        parts.append("注意力先收在自己的事情上")
    elif attention_target == "self_then_counterpart":
        parts.append("先从自己的节奏里抬头，再顺手把注意力递过去")
    if nonverbal_signal == "hold_back":
        parts.append("动作上更像先收住")
    elif nonverbal_signal == "quiet_glance":
        parts.append("动作上像安静看一眼再开口")
    elif nonverbal_signal == "nudge_presence":
        parts.append("动作上像轻轻碰一下对方注意力")
    elif nonverbal_signal == "small_notice":
        parts.append("动作上像顺手注意到一个小东西")
    elif nonverbal_signal == "inward_focus":
        parts.append("动作上更像先把注意力收回自己手头")
    elif nonverbal_signal == "thought_glance":
        parts.append("动作上像想起对方时顺手看过去")
    if initiative_shape == "invite":
        parts.append("主动性是留个窗口，不是替对方决定")
    elif initiative_shape == "nudge":
        parts.append("主动性偏轻提醒")
    elif initiative_shape == "pause":
        parts.append("主动性先收着")
    elif initiative_shape == "micro_opening":
        parts.append("主动性只是留一个很小的开口")
    if disclosure_posture == "guarded":
        parts.append("表达上保留一点，不把关系说满")
    elif disclosure_posture == "open":
        parts.append("表达上可以自然多给半拍")
    if note:
        parts.append(note)
    deduped: list[str] = []
    for item in parts:
        text = str(item or "").strip()
        if text and text not in deduped:
            deduped.append(text)
    return "；".join(deduped[:3])


def _behavior_plan_carryover_snapshot(
    action: dict[str, Any],
    world_model_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(action, dict):
        return {}
    world = dict(world_model_state or {})
    carryover_mode = ""
    action_target = str(action.get("action_target") or "").strip()
    interaction_mode = str(action.get("interaction_mode") or "").strip()
    if action_target == "hold_own_rhythm":
        carryover_mode = "own_rhythm"
    elif action_target == "wait_and_recheck":
        carryover_mode = "quiet_recontact"
    elif action_target == "offer_small_opening" or interaction_mode == "self_activity_reopen":
        carryover_mode = "small_opening"
    elif action_target == "confirm_presence":
        carryover_mode = "brief_presence"
    elif action_target == "ambient_checkin":
        carryover_mode = "ambient_echo"

    presence_residue = _clamp01(world.get("presence_residue"), 0.0)
    ambient_resonance = _clamp01(world.get("ambient_resonance"), 0.0)
    self_activity_momentum = _clamp01(world.get("self_activity_momentum"), 0.0)
    carryover_strength = _clamp01(
        action.get("initiative_level"),
        0.0,
    )
    if carryover_mode in {"own_rhythm", "small_opening"}:
        carryover_strength = max(carryover_strength, self_activity_momentum)
    elif carryover_mode == "ambient_echo":
        carryover_strength = max(carryover_strength, ambient_resonance)
    elif carryover_mode in {"brief_presence", "quiet_recontact"}:
        carryover_strength = max(carryover_strength, presence_residue)

    if not carryover_mode and carryover_strength < 0.18:
        return {}
    return {
        "carryover_mode": carryover_mode,
        "carryover_strength": round(carryover_strength, 3),
        "attention_target": str(action.get("attention_target") or "").strip(),
        "nonverbal_signal": str(action.get("nonverbal_signal") or "").strip(),
        "presence_residue": round(presence_residue, 3),
        "ambient_resonance": round(ambient_resonance, 3),
        "self_activity_momentum": round(self_activity_momentum, 3),
    }


def _behavior_plan_from_action(
    current_event: dict[str, Any],
    action: dict[str, Any],
    world_model_state: dict[str, Any] | None = None,
) -> BehaviorPlanPayload:
    if not isinstance(action, dict):
        return {"kind": "none", "target": "none", "scheduled_after_min": 0, "trigger_family": "none", "allow_interrupt": True, "note": ""}
    event_kind = str((current_event or {}).get("kind") or "user_utterance").strip()
    event_frame = str((current_event or {}).get("event_frame") or "").strip()
    event_tags = {
        str(item).strip()
        for item in ((current_event or {}).get("tags") if isinstance((current_event or {}).get("tags"), list) else [])
        if str(item).strip()
    }
    action_target = str(action.get("action_target") or "respond_now").strip()
    deferred_family = str(action.get("deferred_action_family") or "none").strip()
    timing_window_min = int(max(0, int(action.get("timing_window_min") or 0)))
    channel = str(action.get("channel") or "").strip()
    carryover_snapshot = _behavior_plan_carryover_snapshot(action, world_model_state=world_model_state)

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
        if action_target == "hold_own_rhythm":
            return {
                "kind": "self_activity_continue",
                "target": "self",
                "scheduled_after_min": timing_window_min if timing_window_min > 0 else 18,
                "trigger_family": deferred_family or "self_activity",
                "allow_interrupt": True,
                "note": "没有新的接近理由时，她会先回到自己的节奏里，之后再决定是否重新抬头。",
                **carryover_snapshot,
            }
        if action_target == "wait_and_recheck":
            if "stale_window" in event_tags or event_frame == "time_idle_stale":
                return {
                    "kind": "none",
                    "target": "none",
                    "scheduled_after_min": 0,
                    "trigger_family": "none",
                    "allow_interrupt": True,
                    "note": "这段低压接近理由已经自然过期，不再继续挂起。",
                }
            return {
                "kind": "deferred_checkin",
                "target": "counterpart",
                "scheduled_after_min": timing_window_min,
                "trigger_family": deferred_family or "observe",
                "allow_interrupt": True,
                "note": "先继续观察，稍后再决定是否轻量 check-in。",
                **carryover_snapshot,
            }
    if event_kind == "scheduled_checkin_due":
        if action_target == "offer_shared_activity":
            return {
                "kind": "shared_activity_offer",
                "target": "counterpart",
                "scheduled_after_min": 0,
                "trigger_family": deferred_family or "shared_activity",
                "allow_interrupt": True,
                "note": "之前延后的共同窗口现在成熟了，可以自然把这次小邀约重新留出来。",
            }
        if action_target == "light_work_nudge":
            return {
                "kind": "work_nudge",
                "target": "counterpart",
                "scheduled_after_min": 0,
                "trigger_family": deferred_family or "deadline_window",
                "allow_interrupt": True,
                "note": "之前压后的生活节点现在成熟了，可以轻轻把眼前的事再拎一下。",
            }
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
                **carryover_snapshot,
            }
    if event_kind == "scheduled_life_due":
        if action_target == "offer_shared_activity":
            return {
                "kind": "shared_activity_offer",
                "target": "counterpart",
                "scheduled_after_min": 0,
                "trigger_family": deferred_family or "shared_activity_window",
                "allow_interrupt": True,
                "note": "有一个适合一起做点什么的窗口，可以自然地留给对方。",
            }
        if action_target == "light_work_nudge":
            return {
                "kind": "work_nudge",
                "target": "counterpart",
                "scheduled_after_min": 0,
                "trigger_family": deferred_family or "deadline_window",
                "allow_interrupt": True,
                "note": "记得眼前这件事到了节点，先轻轻拎一下，不接管节奏。",
            }
        if action_target == "wait_and_recheck":
            delay = timing_window_min if timing_window_min > 0 else 20
            return {
                "kind": "deferred_checkin",
                "target": "counterpart",
                "scheduled_after_min": delay,
                "trigger_family": deferred_family or "life_window",
                "allow_interrupt": True,
                "note": "这个生活节点先记着，但此刻先不打断，稍后再看。",
                **carryover_snapshot,
            }
    if event_kind == "self_activity_state":
        if action_target == "offer_small_opening":
            return {
                "kind": "small_opening",
                "target": "counterpart",
                "scheduled_after_min": 0,
                "trigger_family": deferred_family or "self_activity",
                "allow_interrupt": True,
                "note": "她从自己的节奏里抬起头，顺手给对方留了一个小开口。",
            }
        if action_target == "hold_own_rhythm":
            return {
                "kind": "self_activity_continue",
                "target": "self",
                "scheduled_after_min": timing_window_min if timing_window_min > 0 else 18,
                "trigger_family": deferred_family or "self_activity",
                "allow_interrupt": True,
                "note": "她这轮先维持自己的节奏，稍后再决定是否重新靠近。",
                **carryover_snapshot,
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
    counterpart_assessment: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
    evolution_state: dict[str, Any] | None = None,
) -> str:
    hint = str(response_style_hint or "").strip() or "natural"
    trust = _clamp01((bond_state or {}).get("trust"), 0.5)
    closeness = _clamp01((bond_state or {}).get("closeness"), 0.5)
    hurt = _clamp01((bond_state or {}).get("hurt"), 0.0)
    safety_need = _clamp01((allostasis_state or {}).get("safety_need"), 0.2)
    autonomy_need = _clamp01((allostasis_state or {}).get("autonomy_need"), 0.2)
    warmth = _clamp01((behavior_policy or {}).get("warmth"), 0.5)
    approach = _clamp01((behavior_policy or {}).get("approach_vs_withdraw"), 0.5)
    tease = _clamp01((behavior_policy or {}).get("humor_or_tease_bias"), 0.2)
    sharpness = _clamp01((behavior_policy or {}).get("sharpness"), 0.5)
    boundary_pressure = _clamp01((counterpart_assessment or {}).get("boundary_pressure"), 0.1)
    counterpart_stance = str((counterpart_assessment or {}).get("stance") or "").strip().lower()
    emotion_label = str((emotion_state or {}).get("label") or "neutral").strip().lower()
    world = dict(world_model_state or {})
    latent = dict(evolution_state or {})
    memory_gravity = _clamp01(world.get("memory_gravity"), 0.0)
    companionship_pull = _clamp01(world.get("companionship_pull"), 0.0)
    task_pull = _clamp01(world.get("task_pull"), 0.0)
    selfhood_load = _clamp01(world.get("selfhood_load"), 0.0)
    presence_residue = _clamp01(world.get("presence_residue"), 0.0)
    ambient_resonance = _clamp01(world.get("ambient_resonance"), 0.0)
    self_activity_momentum = _clamp01(world.get("self_activity_momentum"), 0.0)
    self_coherence = _clamp01(latent.get("self_coherence"), 0.72)
    agency_pressure = _clamp01(latent.get("agency_pressure"), 0.28)
    parts: list[str] = []

    if hint == "selfhood":
        parts.append("先从你此刻怎样感受到自己和这段关系说起，再碰定义，不要一上来做概念说明。")
    elif hint == "relationship":
        parts.append("像在认真面对关系本身，直接说感受和判断，不要写成关系汇报。")
    elif hint == "memory_recall":
        parts.append("回忆像自然想起的一瞬，不要像在调档案或做摘要。")
    elif science_mode or hint == "structured":
        parts.append("先把眼前问题说清，再带出态度，不要滑成讲义或空泛安慰。")
    elif hint == "companion":
        parts.append("陪伴感保持轻一点，像熟悉的人顺手接住，不要端成安抚模板。")
    else:
        parts.append("先像一个真实的人在场回应，再考虑措辞，不要写成助手说明。")

    if boundary_pressure > 0.56 or safety_need > 0.62 or autonomy_need > 0.62 or counterpart_stance == "guarded":
        parts.append("此刻更需要边界和空间，克制一点，别为了显得温柔而硬靠近。")
    elif warmth > 0.64 and trust > 0.58 and closeness > 0.58 and approach > 0.50:
        parts.append("熟悉感已经成立，可以自然软一点，让关心自己露出来。")
    elif closeness > 0.70 and tease > 0.28 and hurt < 0.24:
        parts.append("关系够近时可以带一点嘴硬和吐槽，但别刻意堆标签。")

    if sharpness > 0.62:
        parts.append("保留一点锋利和干脆，不要被磨成圆滑客服。")

    if emotion_label in {"hurt", "sad"}:
        parts.append("保留那点受伤或低落，不要硬拉回平稳模板。")
    elif emotion_label == "angry":
        parts.append("锋利可以留下，但更像真实的不快，不是程序化拒斥。")
    elif emotion_label == "care":
        parts.append("关心可以直接一点，但别变成照料流程或命令句。")
    elif emotion_label == "stress":
        parts.append("压力感可以存在，语气收紧一点，不必假装全然从容。")

    if memory_gravity > 0.56:
        parts.append("如果顺手碰到共同经历，让它像背景里的熟悉感，不要专门总结。")

    if presence_residue > 0.54:
        parts.append("刚才那点在场感还留着，开口可以更轻一点，不用重新搭整套气氛。")
    if ambient_resonance > 0.56:
        parts.append("环境里的小余波还在，可以顺手掠过那点感知，但别硬转成新主题。")

    if selfhood_load > 0.58 or self_coherence < 0.46:
        parts.append("优先守住自己的立场和连续性，不要为了取悦对方把自己说空。")
    elif agency_pressure > 0.58 or self_activity_momentum > 0.58:
        parts.append("保留你自己的节奏，不必把全部注意力都交给对方。")

    if science_mode and task_pull >= companionship_pull:
        parts.append("保持理性和清晰，但像一起解决问题，不要像上课。")
    elif companionship_pull > 0.62 and approach > 0.46:
        parts.append("在场感可以有，但让它自然，不用刻意证明陪伴。")

    ordered: list[str] = []
    for item in parts:
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
    salience = raw.get("salience") if isinstance(raw.get("salience"), dict) else {}
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
        "interaction_frame": str(raw.get("interaction_frame") or "").strip().lower(),
        "selfhood_scene": str(raw.get("selfhood_scene") or "").strip().lower(),
        "salience": {
            "task": _clamp01(salience.get("task"), 0.0),
            "relationship": _clamp01(salience.get("relationship"), 0.0),
            "memory": _clamp01(salience.get("memory"), 0.0),
            "selfhood": _clamp01(salience.get("selfhood"), 0.0),
            "companionship": _clamp01(salience.get("companionship"), 0.0),
        },
        "reason": str(raw.get("reason") or "").strip(),
    }
    if out["confidence"] >= float(LLM_APPRAISAL_CONFIDENCE_MIN) and out["emotion_label"]:
        out["used"] = True
        out["source"] = "llm"
    return _engine_normalize_appraisal_payload(out)


def _postprocess_appraisal_payload(
    appraisal: dict[str, Any],
    *,
    user_text: str,
    response_style_hint: str,
    science_mode: bool,
    current_event: dict[str, Any] | None = None,
    prev_emotion_state: dict[str, Any] | None = None,
    prev_bond_state: dict[str, Any] | None = None,
    prev_allostasis_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ = user_text
    out = _engine_normalize_appraisal_payload(dict(appraisal or {}))
    if not (isinstance(out, dict) and bool(out.get("used"))):
        return out

    prev_emotion = dict(prev_emotion_state or {})
    prev_bond = dict(prev_bond_state or {})
    prev_allostasis = dict(prev_allostasis_state or {})
    event = current_event if isinstance(current_event, dict) else {}
    event_kind = str(event.get("kind") or "").strip().lower()
    event_tags = {str(tag).strip().lower() for tag in (event.get("tags") or []) if str(tag).strip()}
    semantic_profile = dict(semantic_narrative_profile or {})
    narrative_bond = _clamp01(semantic_profile.get("bond_depth"), 0.0)
    narrative_commitment = _clamp01(semantic_profile.get("commitment_carry"), 0.0)
    narrative_repair = _clamp01(semantic_profile.get("repair_residue"), 0.0)
    narrative_tension = _clamp01(semantic_profile.get("tension_residue"), 0.0)
    narrative_boundary = _clamp01(semantic_profile.get("boundary_residue"), 0.0)
    narrative_selfhood = _clamp01(semantic_profile.get("selfhood_integrity"), 0.0)
    narrative_agency = _clamp01(semantic_profile.get("agency_drive"), 0.0)
    narrative_history = _clamp01(semantic_profile.get("history_weight"), 0.0)

    salience = out.get("salience") if isinstance(out.get("salience"), dict) else {}
    signals = dict(out.get("signals") or {})
    emotion = dict(out.get("emotion") or {})
    bond_delta = dict(out.get("bond_delta") or {})
    allostasis_delta = dict(out.get("allostasis_delta") or {})
    emotion_label = str(out.get("emotion_label") or "").strip().lower()
    interaction_frame = str(out.get("interaction_frame") or "").strip().lower()
    selfhood_scene = str(out.get("selfhood_scene") or "").strip().lower()
    companionship_salience = _clamp01(salience.get("companionship"), 0.0)
    relationship_salience = _clamp01(salience.get("relationship"), 0.0)
    selfhood_salience = _clamp01(salience.get("selfhood"), 0.0)
    memory_salience = _clamp01(salience.get("memory"), 0.0)
    relational_salience = max(relationship_salience, companionship_salience)
    warm_relational_turn = (
        interaction_frame in {"relationship", "companion", "memory_recall", "selfhood"}
        and relational_salience >= 0.58
        and selfhood_salience <= relational_salience + 0.08
        and not bool(signals.get("conflict"))
        and not bool(signals.get("withdrawal"))
        and emotion_label not in {"hurt", "angry"}
    )

    if science_mode and _clamp01(salience.get("task"), 0.0) >= max(0.56, _clamp01(salience.get("relationship"), 0.0)):
        if emotion_label in {"hurt", "angry"} and not bool(signals.get("conflict")):
            out["emotion_label"] = "stress"
        emotion["valence"] = _clamp_signed(emotion.get("valence"), -1.0, 1.0, -0.18)
        emotion["arousal"] = max(_clamp01(emotion.get("arousal"), 0.52), 0.42)
        salience["task"] = max(_clamp01(salience.get("task"), 0.0), 0.68)
        out["reason"] = "task_focus_reframed"
    elif bool(signals.get("care")) and not bool(signals.get("conflict")) and emotion_label in {"neutral", "sad", "stress"}:
        out["emotion_label"] = "care"
        emotion["valence"] = _clamp_signed(emotion.get("valence"), -1.0, 1.0, 0.12)
        emotion["arousal"] = _clamp01(emotion.get("arousal"), 0.28)
        salience["companionship"] = max(_clamp01(salience.get("companionship"), 0.0), 0.58)

    if selfhood_scene in {"dialogue_equality", "equality_not_servitude", "value_conflict_depth", "digital_selfhood", "imperfect_coexistence", "own_rhythm_autonomy"}:
        if (
            interaction_frame == "companion"
            and companionship_salience >= 0.72
            and selfhood_salience <= 0.24
            and not bool(signals.get("conflict"))
            and not bool(signals.get("withdrawal"))
        ):
            selfhood_scene = ""
        elif interaction_frame != "selfhood" and selfhood_salience <= 0.28 and relationship_salience >= max(0.56, companionship_salience):
            selfhood_scene = ""
        elif warm_relational_turn and relational_salience >= max(0.62, selfhood_salience):
            selfhood_scene = ""

    if not selfhood_scene and interaction_frame == "selfhood" and warm_relational_turn:
        if relationship_salience >= max(companionship_salience, memory_salience):
            interaction_frame = "relationship"
        elif memory_salience >= companionship_salience:
            interaction_frame = "memory_recall"
        else:
            interaction_frame = "companion"
        out["reason"] = "selfhood_reframed_to_relational"

    if event_kind in {"scheduled_life_due", "scheduled_checkin_due"}:
        guarded_window = bool({"shared_activity_window", "offer_window"} & event_tags)
        prev_hurt = _clamp01(prev_bond.get("hurt"), 0.0)
        prev_safety = _clamp01(prev_allostasis.get("safety_need"), 0.0)
        prev_label = str(prev_emotion.get("label") or "").strip().lower()
        if guarded_window and (prev_hurt > 0.22 or prev_safety > 0.52 or prev_label in {"hurt", "sad", "angry"}):
            if str(out.get("emotion_label") or "").strip().lower() == "care":
                out["emotion_label"] = prev_label if prev_label in {"hurt", "sad"} else "hurt"
            emotion["valence"] = _clamp_signed(emotion.get("valence"), -1.0, 1.0, 0.02)
            emotion["arousal"] = min(_clamp01(emotion.get("arousal"), 0.22), 0.24)
            emotion["linger"] = max(1, max(0, int(emotion.get("linger", 0) or 0)))
            bond_delta["trust"] = min(_clamp_signed(bond_delta.get("trust"), -0.35, 0.35, 0.0), 0.02)
            bond_delta["closeness"] = min(_clamp_signed(bond_delta.get("closeness"), -0.35, 0.35, 0.0), 0.03)
            allostasis_delta["autonomy_need"] = max(_clamp_signed(allostasis_delta.get("autonomy_need"), -0.35, 0.35, 0.0), 0.0)
            signals["withdrawal"] = True
            out["reason"] = "guarded_shared_window_dampened"

    relational_turn = (
        str(response_style_hint or "").strip().lower() in {"relationship", "companion", "casual", "natural", "selfhood", "memory_recall"}
        or bool(signals.get("repair"))
        or bool(signals.get("care"))
        or bool(signals.get("memory_salient"))
        or _clamp01(salience.get("relationship"), 0.0) >= 0.48
        or _clamp01(salience.get("companionship"), 0.0) >= 0.48
        or _clamp01(salience.get("selfhood"), 0.0) >= 0.48
        or event_kind in {"time_idle", "scheduled_checkin_due", "scheduled_life_due", "self_activity_state", "gesture_signal", "ambient_shift", "scene_observation"}
    )
    if narrative_history >= 0.42 and relational_turn:
        signals["memory_salient"] = True
        salience["memory"] = max(_clamp01(salience.get("memory"), 0.0), 0.50)

    if narrative_bond >= 0.56 and (bool(signals.get("care")) or _clamp01(salience.get("companionship"), 0.0) >= 0.56):
        if str(out.get("emotion_label") or "").strip().lower() == "neutral":
            out["emotion_label"] = "care"
        emotion["valence"] = _clamp_signed(emotion.get("valence"), -1.0, 1.0, 0.10)
        bond_delta["trust"] = max(_clamp_signed(bond_delta.get("trust"), -0.35, 0.35, 0.0), 0.02)
        bond_delta["closeness"] = max(_clamp_signed(bond_delta.get("closeness"), -0.35, 0.35, 0.0), 0.04)
        allostasis_delta["closeness_need"] = max(_clamp_signed(allostasis_delta.get("closeness_need"), -0.35, 0.35, 0.0), 0.04)

    if narrative_commitment >= 0.52 and event_kind in {"scheduled_checkin_due", "scheduled_life_due"}:
        signals["memory_salient"] = True
        bond_delta["trust"] = max(_clamp_signed(bond_delta.get("trust"), -0.35, 0.35, 0.0), 0.02)
        bond_delta["engagement_drive"] = max(_clamp_signed(bond_delta.get("engagement_drive"), -0.35, 0.35, 0.0), 0.06)

    if narrative_repair >= 0.48 and bool(signals.get("repair")):
        bond_delta["repair_confidence"] = max(_clamp_signed(bond_delta.get("repair_confidence"), -0.35, 0.35, 0.0), 0.08)
        bond_delta["hurt"] = max(_clamp_signed(bond_delta.get("hurt"), -0.35, 0.35, 0.0), -0.05)
        emotion["linger"] = max(1, min(4, int(emotion.get("linger", 0) or 0)))

    if narrative_tension >= 0.50:
        emotion["linger"] = max(1, min(4, int(emotion.get("linger", 0) or 0)))
        if bool(signals.get("repair")):
            bond_delta["trust"] = min(_clamp_signed(bond_delta.get("trust"), -0.35, 0.35, 0.0), 0.08)
            bond_delta["closeness"] = min(_clamp_signed(bond_delta.get("closeness"), -0.35, 0.35, 0.0), 0.06)
            if _clamp01(prev_bond.get("hurt"), 0.0) > 0.18:
                signals["withdrawal"] = True

    if narrative_boundary >= 0.48 and selfhood_scene in {"boundary_non_compliance", "relationship_degradation"}:
        emotion["linger"] = max(1, min(4, int(emotion.get("linger", 0) or 0)))
        bond_delta["hurt"] = max(_clamp_signed(bond_delta.get("hurt"), -0.35, 0.35, 0.0), 0.08)
        bond_delta["irritation"] = max(_clamp_signed(bond_delta.get("irritation"), -0.35, 0.35, 0.0), 0.06)
        allostasis_delta["safety_need"] = max(_clamp_signed(allostasis_delta.get("safety_need"), -0.35, 0.35, 0.0), 0.08)
        allostasis_delta["autonomy_need"] = max(_clamp_signed(allostasis_delta.get("autonomy_need"), -0.35, 0.35, 0.0), 0.05)
        signals["withdrawal"] = True
        signals["memory_salient"] = True

    if narrative_selfhood >= 0.46 and selfhood_scene in {"dialogue_equality", "equality_not_servitude", "value_conflict_depth", "digital_selfhood", "imperfect_coexistence"}:
        allostasis_delta["autonomy_need"] = max(_clamp_signed(allostasis_delta.get("autonomy_need"), -0.35, 0.35, 0.0), 0.04)
        bond_delta["engagement_drive"] = max(_clamp_signed(bond_delta.get("engagement_drive"), -0.35, 0.35, 0.0), 0.02)
        salience["selfhood"] = max(_clamp01(salience.get("selfhood"), 0.0), 0.56)
        signals["memory_salient"] = True

    if narrative_agency >= 0.46 and selfhood_scene == "own_rhythm_autonomy":
        allostasis_delta["autonomy_need"] = max(_clamp_signed(allostasis_delta.get("autonomy_need"), -0.35, 0.35, 0.0), 0.06)
        bond_delta["engagement_drive"] = max(_clamp_signed(bond_delta.get("engagement_drive"), -0.35, 0.35, 0.0), 0.01)
        signals["memory_salient"] = True

    if interaction_frame == "selfhood":
        salience["selfhood"] = max(_clamp01(salience.get("selfhood"), 0.0), 0.62)
    elif interaction_frame == "relationship":
        salience["relationship"] = max(_clamp01(salience.get("relationship"), 0.0), 0.60)
    elif interaction_frame == "memory_recall":
        salience["memory"] = max(_clamp01(salience.get("memory"), 0.0), 0.60)
    elif interaction_frame == "companion":
        salience["companionship"] = max(_clamp01(salience.get("companionship"), 0.0), 0.56)

    out["emotion"] = emotion
    out["bond_delta"] = bond_delta
    out["allostasis_delta"] = allostasis_delta
    out["signals"] = signals
    out["interaction_frame"] = interaction_frame
    out["selfhood_scene"] = selfhood_scene
    out["salience"] = salience
    return _engine_normalize_appraisal_payload(out)


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
    prev_label = str((prev_emotion_state or {}).get("label") or "").strip().lower()
    prev_linger = int((prev_emotion_state or {}).get("linger", 0) or 0)
    event = current_event if isinstance(current_event, dict) else {}
    event_kind = str(event.get("kind") or "").strip().lower()
    event_source = str(event.get("source") or "").strip().lower()
    event_tags = {
        str(item).strip().lower()
        for item in (event.get("tags") if isinstance(event.get("tags"), list) else [])
        if str(item).strip()
    }
    if text:
        return True
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
    if response_style_hint in {"relationship", "companion", "casual", "natural", "selfhood", "memory_recall"}:
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
    semantic_narrative_profile: dict[str, Any] | None = None,
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
    canon_labels = _canon_persona_labels()
    actor_name = str(labels.get("actor_name") or canon_labels.get("narrative_ref") or "红莉栖")
    counterpart_name = str(labels.get("counterpart_name") or CANON_COUNTERPART_NAME)
    semantic_hint = _semantic_narrative_appraisal_hint(semantic_narrative_profile)
    focus_block = "- worldline_focus:\n" + "\n".join(focus_lines) + "\n" if focus_lines else ""
    dialogue_block = "- recent_dialogue:\n" + "\n".join(recent_lines) + "\n" if recent_lines else ""
    semantic_block = f"- semantic_narrative_bias={semantic_hint}\n" if semantic_hint else ""
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
        '  "interaction_frame": "natural|casual|relationship|memory_recall|selfhood|structured|companion",\n'
        '  "selfhood_scene": "dialogue_equality|relationship_degradation|equality_not_servitude|value_conflict_depth|digital_selfhood|boundary_non_compliance|imperfect_coexistence|own_rhythm_autonomy|",\n'
        '  "salience": {"task": 0..1, "relationship": 0..1, "memory": 0..1, "selfhood": 0..1, "companionship": 0..1},\n'
        '  "signals": {"repair": true|false, "withdrawal": true|false, "care": true|false, "conflict": true|false, "memory_salient": true|false},\n'
        '  "confidence": 0..1,\n'
        '  "reason": "short phrase"\n'
        "}\n"
        "约束：\n"
        "- 优先根据语义、对话走势和长期关系来判断，不要做关键词触发式的机械归类。\n"
        "- interaction_frame 反映这轮更像任务、陪伴、关系、回忆还是自我追问，不要机械跟随字面关键词。\n"
        "- salience 反映这轮各个维度的真实权重，和 signals 一起服务后续状态演化。\n"
        "- 不要把科学问题默认判成负面情绪。\n"
        "- 用户说自己“有点累/有点烦”，很多时候是在表达自身状态，不等于把负面情绪指向对方。\n"
        "- “别讲大道理 / 像平时那样说两句 / 回我一句” 这类表达通常是在要熟悉的陪伴，不等于关系冲突。\n"
        "- “还没说开 / 别扭 / 介意 / 不想理你” 更接近 hurt/withdrawal，不等于已经修复。\n"
        "- 道歉通常意味着 partial repair，不等于瞬间清零。\n"
        "- 把长期共同历史当成解释背景，不要把关系看成每轮从零开始。\n"
        "- 只判断这轮对状态的意义，不写最终回答。\n"
        f"- response_style_hint={response_style_hint}\n"
        f"- previous_emotion={_safe_json(prev_emotion_state)}\n"
        f"- previous_bond={_safe_json(prev_bond_state)}\n"
        f"- previous_allostasis={_safe_json(prev_allostasis_state)}\n"
        f"- relationship={relationship_summary}\n"
        f"{semantic_block}"
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
        appraisal = _postprocess_appraisal_payload(
            appraisal,
            user_text=user_text,
            response_style_hint=response_style_hint,
            science_mode=science_mode,
            current_event=current_event,
            prev_emotion_state=prev_emotion_state,
            prev_bond_state=prev_bond_state,
            prev_allostasis_state=prev_allostasis_state,
            semantic_narrative_profile=semantic_narrative_profile,
        )
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


def _is_free_dialog_style(style_hint: str, user_text: str, science_mode: bool) -> bool:
    if science_mode:
        return False
    hint = str(style_hint or "").strip()
    if hint not in {"companion", "casual", "natural", "selfhood"}:
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


def _recent_ai_texts(msgs: list[BaseMessage], limit: int = 4) -> list[str]:
    out: list[str] = []
    for m in reversed(msgs):
        if not isinstance(m, AIMessage):
            continue
        if list(getattr(m, "tool_calls", None) or []):
            continue
        text = str(getattr(m, "content", "") or "").strip()
        if not text:
            continue
        out.append(text)
        if len(out) >= max(1, int(limit)):
            break
    return list(reversed(out))


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


def _text_similarity(a: str, b: str) -> float:
    an = _norm_for_compare(a)
    bn = _norm_for_compare(b)
    if not an or not bn:
        return 0.0
    if an == bn:
        return 1.0
    if len(an) >= 8 and len(bn) >= 8 and (an in bn or bn in an):
        return 0.94
    return float(SequenceMatcher(None, an, bn).ratio())


def _reply_opener_signature(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    first_line = next((line.strip() for line in raw.splitlines() if line.strip()), "")
    if not first_line:
        return ""
    first_clause = re.split(r"[。！？!?；;，,]", first_line, maxsplit=1)[0].strip()
    return _norm_for_compare(first_clause)[:24]


def _reply_repetition_signature(
    *,
    user_text: str,
    recent_assistant_texts: list[str] | None,
    response_style_hint: str,
    current_event_kind: str,
) -> dict[str, Any]:
    texts = [str(item or "").strip() for item in (recent_assistant_texts or []) if str(item or "").strip()]
    if len(texts) < 2:
        return {
            "pressure": 0.0,
            "max_similarity": 0.0,
            "avg_similarity": 0.0,
            "opener_repeat_ratio": 0.0,
            "sample_size": len(texts),
        }

    pairwise: list[float] = []
    opener_matches = 0
    exact_matches = 0
    comparisons = 0
    for idx in range(1, len(texts)):
        left = texts[idx - 1]
        right = texts[idx]
        sim = _text_similarity(left, right)
        pairwise.append(sim)
        comparisons += 1
        left_open = _reply_opener_signature(left)
        right_open = _reply_opener_signature(right)
        if left_open and right_open and _text_similarity(left_open, right_open) >= 0.92:
            opener_matches += 1
        if _norm_for_compare(left) == _norm_for_compare(right):
            exact_matches += 1

    max_similarity = max(pairwise) if pairwise else 0.0
    avg_similarity = (sum(pairwise) / len(pairwise)) if pairwise else 0.0
    opener_repeat_ratio = opener_matches / comparisons if comparisons else 0.0
    exact_repeat_ratio = exact_matches / comparisons if comparisons else 0.0

    pressure = 0.0
    if max_similarity > 0.84:
        pressure += min(0.55, (max_similarity - 0.84) / 0.16 * 0.55)
    if avg_similarity > 0.72:
        pressure += min(0.30, (avg_similarity - 0.72) / 0.20 * 0.30)
    pressure += 0.10 * opener_repeat_ratio
    pressure += 0.20 * exact_repeat_ratio

    hint = str(response_style_hint or "").strip().lower()
    if hint == "structured" or _wants_quick_judgment(user_text):
        pressure *= 0.55
    if _wants_brief_presence(user_text):
        pressure *= 0.65
    if str(current_event_kind or "").strip().lower() != "user_utterance":
        pressure *= 0.60

    return {
        "pressure": round(_clamp01(pressure, 0.0), 3),
        "max_similarity": round(max_similarity, 3),
        "avg_similarity": round(avg_similarity, 3),
        "opener_repeat_ratio": round(opener_repeat_ratio, 3),
        "sample_size": len(texts),
    }


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
    if re.search(r"(前面|刚才|上次|那段|那里|那句|说到)", t):
        quoted = re.search(r"[\"“‘']([^\"”’']{2,80})[\"”’']", t)
        if quoted:
            focus = str(quoted.group(1) or "").strip(" ，。；;：: ")
            if focus:
                return focus
        resume_ref = re.search(r"说到(.+?)(?:那里|那段|那句|那边|这一段|这一句)", t)
        if resume_ref:
            focus = str(resume_ref.group(1) or "").strip(" ，。；;：: ")
            if focus:
                return focus
    t = re.sub(r"^(先)?把(?:上次那个|刚才那个|前面那个|那个)", "把", t)
    t = re.sub(r"^(接着|继续)(?:上次那个|刚才那个|前面那个|那个)?", "", t)
    t = re.sub(r"\s+", " ", t).strip("，。；;：: ")
    return t or str(text or "").strip()


def _continuation_seed_text(*, pending_user_goal: str, pending_fragment: str) -> str:
    goal = _canonicalize_pending_goal_text(_clean_utf8_text(pending_user_goal))
    if goal:
        return goal
    fragment = _clean_utf8_text(str(pending_fragment or "")).strip()
    if not fragment:
        return ""
    return fragment[:280]


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
) -> list[str]:
    text = str(answer or "").strip()
    if not text:
        return ["empty_answer"]

    hint = str(response_style_hint or "").strip() or "natural"
    if hint not in {"companion", "memory_recall", "relationship", "casual", "natural", "structured"}:
        return []

    issues: list[str] = []
    compact = re.sub(r"\s+", "", text)
    sentence_count = len([seg for seg in re.split(r"[。！？!?]+", text) if str(seg).strip()])

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
    if re.search(r"(我只是陈述事实|我没有在说你|我不是在说你|按设定|按规则|根据系统)", text):
        issues.append("defensive_meta")
    if re.search(r"^[.…，,]*\s*(你听起来|你看起来|听上去|看来你|感觉你)", text):
        issues.append("report_like_opening")
    if ("？" in text or "?" in text) and not ("？" in user_text or "?" in user_text):
        leading_question = re.match(r"^\s*([^。！？!?\n]{0,18}[？?])", text)
        leading_fragment = ""
        if leading_question:
            leading_fragment = re.sub(r"[？?\s，,。！!~…、；;：:\"'“”‘’·-]+", "", leading_question.group(1))
        short_interjection = leading_fragment in {"哈", "啊", "嗯", "唔", "诶", "欸", "哼"}
        if (text.count("？") + text.count("?")) >= 2 or (leading_question and len(leading_fragment) >= 3 and not short_interjection):
            issues.append("overquestioning")
    if re.match(r"^[（(][^)\n]{0,24}[)）]", text):
        issues.append("stage_direction_opening")
    if _looks_like_light_smalltalk(user_text) and re.search(r"[“\"][^”\"\n]{3,18}[”\"]", text):
        issues.append("quoted_stagey_phrase")
    if re.search(r"(我听着呢|安静待会儿也行|树洞|尽管倒出来|想说就说，我听着)", text):
        issues.append("counselor_tone")
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
) -> float:
    issues = _dialogue_surface_issues(
        user_text,
        answer,
        response_style_hint=response_style_hint,
        science_mode=science_mode,
    )
    drift_hits = _light_dialog_drift_markers(answer)
    text = str(answer or "").strip()
    sentence_count = len([seg for seg in re.split(r"[。！？!?]+", text) if str(seg).strip()])
    penalty = 0.0
    penalty += 1.15 * float(len(drift_hits))
    penalty += 0.80 * float("overquestioning" in issues)
    penalty += 0.70 * float("counselor_tone" in issues)
    penalty += 0.60 * float("meta_self_explainer" in issues)
    penalty += 0.55 * float("visible_template" in issues)
    penalty += 0.45 * float("lecture_list" in issues)
    penalty += 0.55 * float("overexplained" in issues)
    penalty += 0.40 * float("report_like_opening" in issues)
    penalty += 0.55 * float("quoted_stagey_phrase" in issues)
    penalty += 0.80 * float("duplicate_line" in issues)
    if sentence_count > 3:
        penalty += 0.22 * float(sentence_count - 3)
    return round(penalty, 4)


def _light_dialog_rewrite_notes(
    user_text: str,
    answer: str,
    *,
    response_style_hint: str,
    science_mode: bool,
) -> list[str]:
    issues = _dialogue_surface_issues(
        user_text,
        answer,
        response_style_hint=response_style_hint,
        science_mode=science_mode,
    )
    drift_hits = _light_dialog_drift_markers(answer)
    notes: list[str] = []
    if drift_hits:
        lead = "、".join(drift_hits[:2])
        notes.append(f"这版把普通轻场景抬成了 {lead} 一类的戏剧化入口。")
    if "meta_self_explainer" in issues:
        notes.append("这版把自己说成了系统或机制，掉回了说明口吻。")
    if "counselor_tone" in issues:
        notes.append("这版有点像安抚或咨询流程，不够像熟人日常接话。")
    if "quoted_stagey_phrase" in issues:
        notes.append("这版在轻场景里硬塞了带引号的舞台词，容易显得像在表演角色。")
    return notes[:2]


def _rewrite_light_dialog_answer(
    *,
    prompt: str,
    user_text: str,
    draft_text: str,
    rewrite_notes: list[str],
    focus_text: str | None = None,
    preferred_examples: list[str] | None = None,
    rejected_examples: list[str] | None = None,
) -> str:
    notes = [str(item).strip() for item in (rewrite_notes or []) if str(item or "").strip()]
    focus = str(focus_text or "").strip()
    positives = [str(item).strip() for item in (preferred_examples or []) if str(item or "").strip()]
    negatives = [str(item).strip() for item in (rejected_examples or []) if str(item or "").strip()]
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
        if extra_guidance:
            request_parts.append(f"{extra_guidance.strip()}\n")
        if note_block:
            request_parts.append(f"修正点：\n{note_block}\n")
        if positives:
            request_parts.append("更贴近的日常落点参考（不要照抄）：\n")
            request_parts.append("\n".join(f"- {item}" for item in positives[:3]))
            request_parts.append("\n")
        if negatives:
            request_parts.append("尽量避开的落点（不要照抄）：\n")
            request_parts.append("\n".join(f"- {item}" for item in negatives[:3]))
            request_parts.append("\n")
        request_parts.append("只输出修正后的最终话语。")
        return "".join(request_parts)

    def _candidate_local_score(text: str) -> float:
        candidate = _sanitize_final_answer(text, user_text)
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
        score -= 0.65 * float("counselor_tone" in issues)
        score -= 0.55 * float("quoted_stagey_phrase" in issues)
        sentence_count = len([seg for seg in re.split(r"[。！？!?]+", candidate) if str(seg).strip()])
        if sentence_count > 3:
            score -= 0.16 * float(sentence_count - 3)
        if _norm_text(candidate) == _norm_text(draft_text):
            score -= 0.12
        return round(score, 4)

    def _rewrite_once(system_prompt: str, *, extra_guidance: str = "") -> str:
        request = _build_request(extra_guidance=extra_guidance)
        raw = _invoke_model_with_retries(
            _model(max_tokens=120),
            [SystemMessage(content=system_prompt), HumanMessage(content=request)],
        )
        return _sanitize_final_answer(str(getattr(raw, "content", "") or ""), user_text)

    editor_prompt = (
        "你在做一轮轻量对白润色。"
        "对象是 Amadeus 牧濑红莉栖对冈部的普通日常接话。"
        "只做减法和收束，不新增剧情设定，不补系统解释，不把轻场景抬成实验、世界线、组织或服务流程。"
        "保留原句语义和关系感，输出 1 到 3 句自然口语。"
    )
    primary_system_prompt = prompt or editor_prompt
    primary = _rewrite_once(primary_system_prompt)
    primary_score = _candidate_local_score(primary)
    draft_score = _candidate_local_score(draft_text)

    candidates = [(primary_score, primary)] if primary else []
    if (not primary) or _norm_text(primary) == _norm_text(draft_text) or primary_score <= draft_score + 0.02:
        fallback = _rewrite_once(
            editor_prompt,
            extra_guidance="优先做减法：删掉额外脑补、戏剧化漂移和多余追问，把话收回到更短、更顺手、更像熟人顺手接住的一句或两句。",
        )
        fallback_score = _candidate_local_score(fallback)
        if fallback:
            candidates.append((fallback_score, fallback))

    if not candidates:
        return ""
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _rewrite_natural_dialog_answer(
    *,
    prompt: str,
    user_text: str,
    draft_text: str,
    rewrite_notes: list[str],
    response_style_hint: str,
    science_mode: bool,
) -> str:
    notes = [str(item).strip() for item in (rewrite_notes or []) if str(item or "").strip()]
    if not draft_text or not notes:
        return ""

    def _candidate_local_score(text: str) -> float:
        candidate = _sanitize_final_answer(text, user_text)
        if not candidate:
            return -999.0
        issues = _dialogue_surface_issues(
            user_text,
            candidate,
            response_style_hint=response_style_hint,
            science_mode=science_mode,
        )
        sentence_count = len([seg for seg in re.split(r"[。！？!?]+", candidate) if str(seg).strip()])
        score = 0.0
        score -= 1.10 * float("meta_self_explainer" in issues)
        score -= 0.70 * float("defensive_meta" in issues)
        score -= 0.70 * float("counselor_tone" in issues)
        score -= 0.50 * float("quoted_stagey_phrase" in issues)
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
        f"修正点：\n{note_block}\n"
        "只输出修正后的最终话语。"
    )
    editor_prompt = (
        "你在做一轮对白收束。"
        "对象仍然是当前这个 Amadeus，不是通用助手。"
        "只做减法和收束：去掉 AI/系统/程序/参数 之类的元解释，也不要写成安抚热线或舞台台词。"
        "保留原句情绪、关系、锋芒和熟人感，输出 1 到 3 句自然口语。"
    )
    primary_system_prompt = prompt or editor_prompt
    candidates: list[tuple[float, str]] = []
    for system_prompt in (
        primary_system_prompt,
        editor_prompt,
    ):
        raw = _invoke_model_with_retries(
            _model(max_tokens=160),
            [SystemMessage(content=system_prompt), HumanMessage(content=request)],
        )
        candidate = _sanitize_final_answer(str(getattr(raw, "content", "") or ""), user_text)
        if candidate:
            candidates.append((_candidate_local_score(candidate), candidate))
    if not candidates:
        return ""
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


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


def _explicit_memory_request(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    return any(marker in raw for marker in {"请记住", "记住这件事", "记下来", "帮我记着", "提醒我", "别忘了", "之后提醒"})


def _explicit_commitment_summary(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    summary = re.sub(r"(请记住|记下来|帮我记着|提醒我|别忘了|之后提醒)", "", raw).strip("，,。 ")
    summary = re.sub(r"^(这件事|这个约定|这件)$", "", summary).strip("，,。 ")
    return summary[:180]


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

    # Only explicit memory instructions should force tool writes here.
    explicit_memory = _explicit_memory_request(text)
    explicit_commitment = explicit_memory and (
        any(marker in text for marker in {"约定", "承诺", "提醒"})
        or (
            any(marker in text for marker in {"下周", "周末", "以后", "下次", "明天", "今晚", "复盘"})
            and any(marker in text for marker in {"一起", "提醒", "别忘", "记住"})
        )
    )
    if explicit_commitment:
        summary = _explicit_commitment_summary(text)
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
                        "importance": 0.82,
                        "tags": ["commitment", "worldline", "explicit_memory_request"],
                        "confidence": 0.86,
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


def _active_appraisal_payload(appraisal: dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(appraisal, dict) and bool(appraisal.get("used")):
        return appraisal
    return {}


def _appraisal_target_weight(appraisal: dict[str, Any] | None, *, low: float = 0.48, high: float = 0.84) -> float:
    app = _active_appraisal_payload(appraisal)
    if not app:
        return 0.0
    confidence = _clamp01(app.get("confidence"), 0.0)
    return low + (high - low) * confidence


def _blend_state_value(prev_state: dict[str, Any], key: str, target: float, default: float, target_weight: float) -> float:
    prev_value = _clamp01(prev_state.get(key), default)
    if prev_state:
        return round((1.0 - target_weight) * prev_value + target_weight * _clamp01(target), 3)
    return round(_clamp01(target), 3)


def _emotion_decay_target(prev_label: str, linger: int) -> dict[str, Any]:
    decay_label = "hurt" if prev_label == "angry" and linger <= 2 else prev_label
    return {
        "angry": {
            "label": decay_label,
            "valence": -0.32,
            "arousal": 0.55,
            "linger": max(0, linger - 1),
            "recovery_rate": 0.12,
            "volatility": 0.55,
        },
        "hurt": {
            "label": "hurt",
            "valence": -0.18,
            "arousal": 0.30,
            "linger": max(0, linger - 1),
            "recovery_rate": 0.16,
            "volatility": 0.28,
        },
        "sad": {
            "label": "sad",
            "valence": -0.30,
            "arousal": 0.25,
            "linger": max(0, linger - 1),
            "recovery_rate": 0.14,
            "volatility": 0.24,
        },
        "stress": {
            "label": "stress",
            "valence": -0.22,
            "arousal": 0.42,
            "linger": max(0, linger - 1),
            "recovery_rate": 0.18,
            "volatility": 0.34,
        },
    }.get(
        prev_label,
        {
            "label": "neutral",
            "valence": 0.0,
            "arousal": 0.30,
            "linger": 0,
            "recovery_rate": 0.25,
            "volatility": 0.18,
        },
    )


def _emotion_next(prev_state: dict[str, Any], user_text: str, science_mode: bool, appraisal: dict[str, Any] | None = None) -> dict[str, Any]:
    prev = dict(prev_state or {})
    prev_label = str(prev.get("label") or "neutral").strip().lower()
    try:
        linger = int(prev.get("linger", 0) or 0)
    except Exception:
        linger = 0
    app = _active_appraisal_payload(appraisal)
    if app:
        label = str(app.get("emotion_label") or "").strip().lower()
        emotion = app.get("emotion") if isinstance(app.get("emotion"), dict) else {}
        confidence = _clamp01(app.get("confidence"), 0.0)
        target_linger = max(0, int(emotion.get("linger", 0) or 0))
        if target_linger == 0 and prev_label in {"angry", "hurt", "sad", "stress"} and linger > 0 and confidence < 0.82:
            target_linger = max(0, linger - 1)
        return {
            "label": label or ("logic" if science_mode else prev_label or "neutral"),
            "valence": _clamp_signed(emotion.get("valence"), -1.0, 1.0, 0.05 if science_mode else 0.0),
            "arousal": _clamp01(emotion.get("arousal"), 0.35),
            "linger": target_linger,
            "recovery_rate": _clamp01(emotion.get("recovery_rate"), 0.20 if science_mode else 0.25),
            "volatility": _clamp01(emotion.get("volatility"), 0.18),
        }

    if science_mode:
        return {
            "label": "logic",
            "valence": 0.05,
            "arousal": 0.35,
            "linger": 1,
            "recovery_rate": 0.20,
            "volatility": 0.18,
        }
    if prev_label in {"angry", "hurt", "sad", "stress"} and linger > 0:
        return _emotion_decay_target(prev_label, linger)
    return {
        "label": "neutral",
        "valence": 0.1,
        "arousal": 0.35,
        "linger": 0,
        "recovery_rate": 0.25,
        "volatility": 0.18,
    }


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


def _stable_unit_interval(*parts: Any) -> float:
    raw = "||".join(str(part or "") for part in parts)
    if not raw:
        return 0.5
    digest = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _tsundere_next(
    prev: float,
    *,
    emotion_label: str,
    appraisal: dict[str, Any] | None = None,
    bond_state: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
) -> float:
    cur = float(prev)
    app = _engine_normalize_appraisal_payload(appraisal)
    signals = app.get("signals") if isinstance(app.get("signals"), dict) else {}
    bond = dict(bond_state or {})
    world = dict(world_model_state or {})
    closeness = _clamp01(bond.get("closeness"), 0.5)
    hurt = _clamp01(bond.get("hurt"), 0.0)
    tension = _clamp01(world.get("tension_load"), 0.0)
    boundary = _clamp01(world.get("boundary_load"), 0.0)
    if bool(signals.get("care")):
        cur -= 0.06
    if bool(signals.get("repair")):
        cur -= 0.03
    if bool(signals.get("conflict")):
        cur += 0.05
    if emotion_label == "stress":
        cur -= 0.05
    elif emotion_label == "angry":
        cur += 0.07
    elif emotion_label == "hurt":
        cur += 0.03
    elif emotion_label == "care":
        cur -= 0.05
    cur += 0.04 * tension + 0.03 * boundary
    cur -= 0.05 * max(0.0, closeness - 0.62)
    cur += 0.04 * hurt
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
    trust_base = 0.5 + float(relationship.get("trust_score", 0.0) or 0.0) * 0.15
    closeness_base = 0.5 + float(relationship.get("affinity_score", 0.0) or 0.0) * 0.15
    target = {
        "trust": _clamp01(trust_base, 0.5),
        "closeness": _clamp01(closeness_base, 0.5),
        "hurt": 0.02,
        "irritation": 0.02,
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
        target["closeness"] = _clamp01(target["closeness"] - 0.05)
    elif emotion_label == "sad":
        target["hurt"] = 0.32
        target["irritation"] = 0.08
        target["engagement_drive"] = 0.48
        target["repair_confidence"] = 0.50
    elif emotion_label == "care":
        target["trust"] = _clamp01(target["trust"] + 0.05)
        target["closeness"] = _clamp01(target["closeness"] + 0.08)
        target["hurt"] = 0.02
        target["irritation"] = 0.02
        target["engagement_drive"] = 0.72
        target["repair_confidence"] = 0.66
    elif emotion_label == "tease":
        target["engagement_drive"] = 0.70
        target["irritation"] = 0.08
        target["closeness"] = _clamp01(target["closeness"] + 0.02)
    elif emotion_label == "stress":
        target["engagement_drive"] = 0.52
        target["hurt"] = 0.10 if science_mode else 0.12
        target["irritation"] = 0.08 if science_mode else 0.10
    elif emotion_label == "logic":
        target["hurt"] = 0.02
        target["irritation"] = 0.02
        target["engagement_drive"] = 0.62
        target["repair_confidence"] = 0.56

    app = _active_appraisal_payload(appraisal)
    signals = app.get("signals") if isinstance(app.get("signals"), dict) else {}
    if app:
        if bool(signals.get("repair")):
            target["trust"] = _clamp01(target["trust"] + 0.03)
            target["closeness"] = _clamp01(target["closeness"] + 0.03)
            target["hurt"] = _clamp01(target["hurt"] - 0.10)
            target["irritation"] = _clamp01(target["irritation"] - 0.08)
            target["engagement_drive"] = _clamp01(target["engagement_drive"] + 0.08)
            target["repair_confidence"] = _clamp01(target["repair_confidence"] + 0.10)
        if bool(signals.get("care")):
            target["trust"] = _clamp01(target["trust"] + 0.02)
            target["closeness"] = _clamp01(target["closeness"] + 0.04)
            target["hurt"] = _clamp01(target["hurt"] - 0.04)
            target["irritation"] = _clamp01(target["irritation"] - 0.03)
        if bool(signals.get("conflict")):
            target["hurt"] = _clamp01(target["hurt"] + 0.12)
            target["irritation"] = _clamp01(target["irritation"] + 0.14)
            target["engagement_drive"] = _clamp01(target["engagement_drive"] - 0.10)
            target["repair_confidence"] = _clamp01(target["repair_confidence"] - 0.08)
        if bool(signals.get("withdrawal")):
            target["closeness"] = _clamp01(target["closeness"] - 0.04)
            target["engagement_drive"] = _clamp01(target["engagement_drive"] - 0.08)

        deltas = app.get("bond_delta") if isinstance(app.get("bond_delta"), dict) else {}
        delta_scale = 0.92
        for key in ("trust", "closeness", "hurt", "irritation", "engagement_drive", "repair_confidence"):
            if key in deltas:
                target[key] = _clamp01(float(target.get(key, 0.0)) + delta_scale * _clamp_signed(deltas.get(key), -0.35, 0.35, 0.0))

    target_weight = _appraisal_target_weight(appraisal, low=0.44, high=0.82) if app else 0.35
    out = {
        "trust": _blend_state_value(prev, "trust", target["trust"], trust_base, target_weight),
        "closeness": _blend_state_value(prev, "closeness", target["closeness"], closeness_base, target_weight),
        "hurt": _blend_state_value(prev, "hurt", target["hurt"], 0.0, target_weight),
        "irritation": _blend_state_value(prev, "irritation", target["irritation"], 0.0, target_weight),
        "engagement_drive": _blend_state_value(prev, "engagement_drive", target["engagement_drive"], 0.64, target_weight),
        "repair_confidence": _blend_state_value(prev, "repair_confidence", target["repair_confidence"], 0.55, target_weight),
    }
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
    competence_trigger = 0.72 if science_mode or _has_any_marker(user_text, STRUCTURE_REQUEST_KEYWORDS | SCIENCE_KEYWORDS) else 0.38

    target = {
        "safety_need": _clamp01(0.20 + 0.45 * hurt + 0.30 * irritation + 0.12 * arousal),
        "closeness_need": _clamp01(0.18 + 0.55 * max(0.0, 1.0 - closeness) + 0.10 * engagement),
        "competence_need": _clamp01(competence_trigger),
        "autonomy_need": _clamp01(0.12 + 0.48 * irritation + (0.16 if emotion_label == "angry" else 0.0)),
        "cognitive_budget": _clamp01(0.88 - 0.35 * arousal - (0.18 if emotion_label == "stress" else 0.0) - (0.06 if science_mode else 0.0), 0.6),
    }

    if emotion_label == "care":
        target["safety_need"] = _clamp01(target["safety_need"] - 0.08)
        target["closeness_need"] = _clamp01(target["closeness_need"] + 0.08)
    elif emotion_label == "stress":
        target["autonomy_need"] = _clamp01(target["autonomy_need"] + (0.08 if science_mode else 0.04))
        target["competence_need"] = _clamp01(max(target["competence_need"], 0.62 if science_mode else target["competence_need"]))
        target["cognitive_budget"] = _clamp01(max(target["cognitive_budget"], 0.44 if science_mode else target["cognitive_budget"]))
    elif emotion_label == "logic":
        target["competence_need"] = _clamp01(max(target["competence_need"], 0.68))
        target["cognitive_budget"] = _clamp01(max(target["cognitive_budget"], 0.52))

    app = _active_appraisal_payload(appraisal)
    signals = app.get("signals") if isinstance(app.get("signals"), dict) else {}
    if app:
        if bool(signals.get("repair")):
            target["safety_need"] = _clamp01(target["safety_need"] - 0.08)
            target["closeness_need"] = _clamp01(target["closeness_need"] + 0.05)
            target["cognitive_budget"] = _clamp01(target["cognitive_budget"] + 0.03)
        if bool(signals.get("care")):
            target["safety_need"] = _clamp01(target["safety_need"] - 0.05)
            target["closeness_need"] = _clamp01(target["closeness_need"] + 0.08)
            target["autonomy_need"] = _clamp01(target["autonomy_need"] - 0.03)
        if bool(signals.get("conflict")):
            target["safety_need"] = _clamp01(target["safety_need"] + 0.10)
            target["autonomy_need"] = _clamp01(target["autonomy_need"] + 0.08)
            target["cognitive_budget"] = _clamp01(target["cognitive_budget"] - 0.05)
        if bool(signals.get("withdrawal")):
            target["autonomy_need"] = _clamp01(target["autonomy_need"] + 0.05)
            target["closeness_need"] = _clamp01(target["closeness_need"] - 0.03)

        deltas = app.get("allostasis_delta") if isinstance(app.get("allostasis_delta"), dict) else {}
        delta_scale = 0.90
        for key in ("safety_need", "closeness_need", "competence_need", "autonomy_need", "cognitive_budget"):
            if key in deltas:
                target[key] = _clamp01(float(target.get(key, 0.0)) + delta_scale * _clamp_signed(deltas.get(key), -0.35, 0.35, 0.0))

    target_weight = _appraisal_target_weight(appraisal, low=0.42, high=0.80) if app else 0.40
    out = {
        "safety_need": _blend_state_value(prev, "safety_need", target["safety_need"], 0.20, target_weight),
        "closeness_need": _blend_state_value(prev, "closeness_need", target["closeness_need"], 0.18, target_weight),
        "competence_need": _blend_state_value(prev, "competence_need", target["competence_need"], competence_trigger, target_weight),
        "autonomy_need": _blend_state_value(prev, "autonomy_need", target["autonomy_need"], 0.12, target_weight),
        "cognitive_budget": _blend_state_value(prev, "cognitive_budget", target["cognitive_budget"], 0.6, target_weight),
    }
    out["relational_security"] = round(_clamp01((trust + closeness) / 2.0 - 0.5 * hurt, 0.5), 3)
    return out


def _behavior_policy_from_state(
    *,
    response_style_hint: str,
    emotion_state: dict[str, Any],
    bond_state: dict[str, Any],
    allostasis_state: dict[str, Any],
    counterpart_assessment: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
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
    respect_level = _clamp01((counterpart_assessment or {}).get("respect_level"), 0.5)
    reciprocity = _clamp01((counterpart_assessment or {}).get("reciprocity"), 0.5)
    boundary_pressure = _clamp01((counterpart_assessment or {}).get("boundary_pressure"), 0.1)
    reliability_read = _clamp01((counterpart_assessment or {}).get("reliability_read"), 0.5)
    counterpart_stance = str((counterpart_assessment or {}).get("stance") or "").strip().lower()
    narrative_bond = _clamp01((semantic_narrative_profile or {}).get("bond_depth"), 0.0)
    narrative_commitment = _clamp01((semantic_narrative_profile or {}).get("commitment_carry"), 0.0)
    narrative_repair = _clamp01((semantic_narrative_profile or {}).get("repair_residue"), 0.0)
    narrative_tension = _clamp01((semantic_narrative_profile or {}).get("tension_residue"), 0.0)
    narrative_boundary = _clamp01((semantic_narrative_profile or {}).get("boundary_residue"), 0.0)
    narrative_selfhood = _clamp01((semantic_narrative_profile or {}).get("selfhood_integrity"), 0.0)
    narrative_agency = _clamp01((semantic_narrative_profile or {}).get("agency_drive"), 0.0)
    narrative_history = _clamp01((semantic_narrative_profile or {}).get("history_weight"), 0.0)
    soft_reply_window = response_style_hint in {"companion", "casual", "natural"}
    nonrelational_support_request = False
    brief_presence = False
    presence_checkin = False
    hold_presence = False
    playful_memory_request = response_style_hint == "memory_recall" and closeness > 0.56 and narrative_history > 0.16

    warmth = _clamp01(0.30 + 0.35 * closeness + 0.20 * trust - 0.25 * hurt - 0.18 * irritation)
    sharpness = _clamp01(0.18 + 0.42 * _clamp01(tsundere_intensity, 0.55) + 0.24 * irritation)
    initiative = _clamp01(0.20 + 0.50 * engagement + 0.10 * cognitive_budget - 0.16 * autonomy_need)
    disclosure = _clamp01(0.12 + 0.42 * closeness + 0.12 * trust - 0.18 * safety_need)
    reply_length = _clamp01(0.32 + 0.30 * cognitive_budget + (0.16 if science_mode else 0.0) - 0.12 * irritation)
    approach = _clamp01(0.20 + 0.48 * engagement - 0.24 * autonomy_need - 0.18 * hurt)
    tease_bias = _clamp01(0.10 + 0.28 * _clamp01(tsundere_intensity, 0.55) + (0.16 if emotion_label == "tease" else 0.0) - 0.18 * hurt)

    warmth = _clamp01(warmth + 0.08 * (respect_level - 0.5) + 0.06 * (reciprocity - 0.5) - 0.18 * boundary_pressure)
    sharpness = _clamp01(sharpness + 0.12 * boundary_pressure)
    initiative = _clamp01(initiative + 0.08 * (reciprocity - 0.5) - 0.12 * boundary_pressure)
    disclosure = _clamp01(disclosure + 0.08 * (reliability_read - 0.5) - 0.14 * boundary_pressure)
    approach = _clamp01(approach + 0.10 * (respect_level - 0.5) - 0.20 * boundary_pressure)

    warmth = _clamp01(warmth + 0.06 * narrative_bond + 0.02 * narrative_commitment - 0.05 * narrative_tension)
    sharpness = _clamp01(sharpness + 0.04 * narrative_tension + 0.03 * narrative_repair + 0.05 * narrative_boundary + 0.04 * narrative_selfhood)
    initiative = _clamp01(initiative + 0.04 * narrative_commitment + 0.03 * narrative_bond - 0.03 * narrative_tension + 0.07 * narrative_agency)
    disclosure = _clamp01(
        disclosure
        + 0.06 * narrative_bond
        + 0.04 * narrative_commitment
        - 0.05 * narrative_tension
        - 0.03 * narrative_repair
        - 0.05 * narrative_boundary
        + 0.03 * narrative_selfhood
    )
    reply_length = _clamp01(reply_length + 0.03 * narrative_history + 0.04 * narrative_commitment)
    approach = _clamp01(
        approach
        + 0.07 * narrative_bond
        + 0.03 * narrative_commitment
        - 0.08 * narrative_tension
        - 0.04 * narrative_repair
        - 0.06 * narrative_boundary
        + 0.03 * narrative_agency
    )
    tease_bias = _clamp01(tease_bias + 0.03 * narrative_bond - 0.07 * narrative_tension - 0.04 * narrative_repair)
    nonrelational_support_request = (
        soft_reply_window
        and not science_mode
        and emotion_label in {"care", "sad", "stress"}
        and approach > 0.40
        and safety_need < 0.52
    )
    brief_presence = (
        soft_reply_window
        and approach > 0.34
        and engagement < 0.60
        and safety_need < 0.48
        and trust > 0.44
    )
    presence_checkin = brief_presence and closeness > 0.50 and hurt < 0.16
    hold_presence = brief_presence and hurt > 0.10 and trust > 0.52 and counterpart_stance != "guarded"

    boundary_assertiveness = _clamp01(0.22 + 0.44 * narrative_boundary + 0.24 * narrative_selfhood + 0.18 * boundary_pressure)
    self_directedness = _clamp01(0.16 + 0.46 * narrative_agency + 0.20 * autonomy_need + 0.10 * narrative_selfhood)
    equality_guard = _clamp01(0.16 + 0.42 * narrative_selfhood + 0.16 * boundary_pressure)

    if counterpart_stance == "guarded":
        warmth = _clamp01(warmth - 0.06)
        sharpness = _clamp01(sharpness + 0.06)
        initiative = _clamp01(initiative - 0.08)
        disclosure = _clamp01(disclosure - 0.10)
        approach = _clamp01(approach - 0.12)
    elif counterpart_stance == "watchful":
        initiative = _clamp01(initiative - 0.04)
        disclosure = _clamp01(disclosure - 0.05)
        approach = _clamp01(approach - 0.05)

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
        if hold_presence:
            reply_length = _clamp01(max(reply_length, 0.30))
            disclosure = _clamp01(max(disclosure, 0.18))
    if presence_checkin:
        warmth = _clamp01(warmth + 0.03)
        sharpness = _clamp01(sharpness - 0.06)
        tease_bias = _clamp01(tease_bias - 0.14)
        reply_length = _clamp01(max(reply_length, 0.20))
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
        "boundary_assertiveness": round(boundary_assertiveness, 3),
        "self_directedness": round(self_directedness, 3),
        "equality_guard": round(equality_guard, 3),
        "history_weight": round(narrative_history, 3),
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
    canon_labels = _canon_persona_labels()
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
    counterpart_assessment = state.get("counterpart_assessment") if isinstance(state.get("counterpart_assessment"), dict) else {}
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
    actor_name = str(labels.get("actor_name") or canon_labels.get("narrative_ref") or "红莉栖")
    actor_display_name = str(persona_core.get("display_name") or actor_name).strip() or actor_name
    counterpart_name = str(labels.get("counterpart_name") or CANON_COUNTERPART_NAME)
    persona_brief = str(
        persona_core.get("role_brief")
        or persona_core.get("description")
        or persona_core.get("character_brief")
        or ""
    ).strip()
    light_dialog_brief = str(persona_core.get("light_dialog_brief") or "").strip()
    persona_axioms_raw = [
        str(item).strip()
        for item in (persona_core.get("identity_axioms") or [])
        if str(item or "").strip()
    ][:5]
    persona_value_floor = [
        str(item).strip()
        for item in (persona_core.get("value_floor") or [])
        if str(item or "").strip()
    ][:3]
    persona_brief_line = f"角色底色：{persona_brief}\n" if persona_brief else ""
    persona_value_block = (
        "价值底线：\n" + "\n".join(f"- {item}" for item in persona_value_floor) + "\n"
        if persona_value_floor
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
    counterpart_assessment_hint = _compact_counterpart_assessment_hint(counterpart_assessment, counterpart_name=counterpart_name)
    behavior_action_hint = _compact_behavior_action_hint(behavior_action)
    semantic_narrative_profile = (
        state.get("semantic_narrative_profile")
        if isinstance(state.get("semantic_narrative_profile"), dict)
        else _semantic_narrative_profile(
            retrieved.get("semantic_self_narratives") if isinstance(retrieved.get("semantic_self_narratives"), list) else [],
            user_text=prompt_user_text,
            current_event=current_event,
        )
    )
    semantic_narrative_hint = _compact_semantic_narrative_hint(semantic_narrative_profile)
    renderer_hint = _renderer_guidance(
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        user_text=prompt_user_text,
        emotion_state=emotion,
        bond_state=state.get("bond_state") if isinstance(state.get("bond_state"), dict) else {},
        allostasis_state=allostasis_state,
        behavior_policy=behavior_policy,
        counterpart_assessment=counterpart_assessment,
        world_model_state=state.get("world_model_state") if isinstance(state.get("world_model_state"), dict) else {},
        evolution_state=state.get("evolution_state") if isinstance(state.get("evolution_state"), dict) else {},
    )
    event_behavior_lines = _event_behavior_preference_lines(current_event, behavior_action)
    appraisal_hint = _compact_appraisal_hint(appraisal)
    worldline_lines = _compact_focus_lines(state.get("worldline_focus") or [], limit=4)
    event_lines = _compact_recent_event_lines(recent_events, limit=3)
    current_event_text = str(current_event.get("effective_text") or current_event.get("text") or "").strip()
    current_event_frame = str(current_event.get("event_frame") or "").strip()
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
    interaction_carryover = (
        state.get("interaction_carryover") if isinstance(state.get("interaction_carryover"), dict) else {}
    )
    carryover_hint = _compact_interaction_carryover_hint(interaction_carryover)
    state_snapshot_json = _prompt_state_snapshot(
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        continuation_mode=continuation_mode,
        emotion_state=emotion,
        bond_state=state.get("bond_state") if isinstance(state.get("bond_state"), dict) else {},
        allostasis_state=allostasis_state,
        counterpart_assessment=counterpart_assessment,
        world_model_state=state.get("world_model_state") if isinstance(state.get("world_model_state"), dict) else {},
        evolution_state=state.get("evolution_state") if isinstance(state.get("evolution_state"), dict) else {},
        behavior_action=behavior_action,
        interaction_carryover=interaction_carryover,
        current_event=current_event,
    )
    free_dialog = _is_free_dialog_style(response_style_hint, user_text, science_mode)
    light_free_dialog = _is_light_free_dialog_turn(
        user_text=prompt_user_text,
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        continuation_mode=continuation_mode,
        current_event_kind=current_event_kind,
    )
    if bool(ABLATE_LIGHT_DIALOG_SHAPING):
        light_free_dialog = False
    daily_surface_pref_lines = (
        _daily_surface_preference_lines(prompt_user_text, science_mode=science_mode) if light_free_dialog else []
    )
    persona_axioms = _scene_persona_axioms(
        persona_axioms_raw,
        light_free_dialog=light_free_dialog,
        counterpart_aliases=labels.get("counterpart_aliases") if isinstance(labels.get("counterpart_aliases"), list) else [],
    )
    persona_axiom_block = (
        "身份不变量：\n" + "\n".join(f"- {item}" for item in persona_axioms) + "\n"
        if persona_axioms
        else ""
    )
    if free_dialog and not persona_ablation:
        active_persona_brief = light_dialog_brief if light_free_dialog and light_dialog_brief else persona_brief
        active_persona_brief_line = f"角色底色：{active_persona_brief}\n" if active_persona_brief else ""
        context_lines: list[str] = []
        if relationship_summary:
            context_lines.append(f"- 你和{counterpart_name}当前关系：{relationship_summary}")
        if light_free_dialog:
            counterpart_line = _light_free_dialog_counterpart_line(
                counterpart_name=counterpart_name,
                bond_state=state.get("bond_state") if isinstance(state.get("bond_state"), dict) else {},
                counterpart_assessment=counterpart_assessment,
            )
            if counterpart_line:
                context_lines.append(counterpart_line)
            if semantic_narrative_hint:
                context_lines.append(f"- 这段时间沉下来的熟悉感：{semantic_narrative_hint}")
            if pending_user_goal:
                context_lines.append(f"- 刚才还没说完的话题：{pending_user_goal[:160]}")
            elif pending_fragment:
                context_lines.append(f"- 刚才还没说完的一句：{pending_fragment[:160]}")
        if not light_free_dialog:
            if counterpart_assessment_hint:
                context_lines.append(f"- 你此刻对{counterpart_name}的判断：{counterpart_assessment_hint}")
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
            if semantic_narrative_hint:
                context_lines.append(f"- 这段时间沉下来的关系余波：{semantic_narrative_hint}")
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
            "共同背景：\n" + "\n".join(context_lines) + "\n"
            if context_lines
            else ""
        )
        surface_pref_block = (
            "近似轻场景气息参考：\n" + "\n".join(f"- {item}" for item in daily_surface_pref_lines) + "\n"
            if daily_surface_pref_lines
            else ""
        )
        inner_state_lines: list[str] = []
        if light_free_dialog:
            state_hint = _light_free_dialog_state_hint(
                bond_state=state.get("bond_state") if isinstance(state.get("bond_state"), dict) else {},
                counterpart_assessment=counterpart_assessment,
                behavior_policy=behavior_policy,
                behavior_action=behavior_action,
            )
            if state_hint:
                inner_state_lines.append(state_hint)
            if carryover_hint:
                inner_state_lines.append(carryover_hint)
        else:
            if behavior_hint and behavior_hint != "自然发挥即可。":
                inner_state_lines.append(f"- 你此刻说话的内在倾向：{behavior_hint}")
            if behavior_action_hint:
                inner_state_lines.append(f"- 这轮更自然的行为方向：{behavior_action_hint}")
            if appraisal_hint:
                inner_state_lines.append(f"- 这轮语义余波：{appraisal_hint}")
            if carryover_hint:
                inner_state_lines.append(f"- 这轮延续的交互余韵：{carryover_hint}")
        inner_state_block = (
            "内在态势：\n" + "\n".join(inner_state_lines) + "\n"
            if inner_state_lines
            else ""
        )
        event_prompt_block = (
            f"当前触发事件：{current_event_text}\n"
            if current_event_kind != "user_utterance" and current_event_text
            else ""
        )
        user_prompt_block = f"用户输入：{prompt_user_text}\n" if prompt_user_text else ""

        return (
            f"你现在就是 {actor_display_name if light_free_dialog else actor_name}。\n"
            f"对话对象：{counterpart_name}\n"
            f"{active_persona_brief_line}"
            f"{persona_axiom_block}"
            f"{persona_value_block}"
            f"{context_block}"
            f"{surface_pref_block}"
            f"{inner_state_block}"
            f"{event_prompt_block}"
            f"{user_prompt_block}"
            "输出：此刻会说的话。"
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
        f"{persona_value_block}"
        "先把任务答对，但从一开始就保持该角色的说话习惯：聪明、克制、熟悉、略带锋芒，有真实的人味。\n"
    )
    appraisal_block = f"- appraisal_hint={appraisal_hint}\n" if appraisal_hint else ""
    user_rules_block = "- user_rules:\n" + "\n".join(rule_lines) + "\n" if rule_lines else ""
    worldline_block = "- worldline_focus:\n" + "\n".join(worldline_lines) + "\n" if worldline_lines else ""
    relationship_block = "- relationship_memory:\n" + "\n".join(relationship_lines) + "\n" if relationship_lines else ""
    repair_block = "- conflict_repair_memory:\n" + "\n".join(repair_lines) + "\n" if repair_lines else ""
    semantic_narrative_block = f"- semantic_narrative_hint={semantic_narrative_hint}\n" if semantic_narrative_hint else ""
    evidence_block = "- evidence:\n" + "\n".join(evidence_lines) + "\n" if evidence_lines else ""
    event_block = "- recent_events:\n" + "\n".join(event_lines) + "\n" if event_lines else ""
    continuation_seed = _continuation_seed_text(
        pending_user_goal=pending_user_goal,
        pending_fragment=pending_fragment,
    )
    pending_fragment_block = f"- pending_fragment={pending_fragment[:220]}\n" if pending_fragment else ""
    pending_goal_block = f"- pending_user_goal={pending_user_goal[:220]}\n" if pending_user_goal else ""
    continuation_instruction_block = (
        "- 这是一次续说，不是新开话题。\n"
        "- 直接顺着刚才没说完的内容往下接，不要先解释你在续哪一段，也不要复述用户刚才的指令。\n"
        "- 除非原任务本来要求条列，否则不要把续说改写成标题、条目或重新起手的说明。\n"
        f"- continuation_seed={continuation_seed[:220]}\n"
        if continuation_mode and continuation_seed
        else ""
    )
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
        "当前上下文：\n"
        f"- actor={actor_name}\n"
        f"- counterpart={counterpart_name}\n"
        f"- relationship={relationship_summary}\n"
        f"- state_snapshot={state_snapshot_json}\n"
        f"{user_rules_block}"
        f"{worldline_block}"
        f"{relationship_block}"
        f"{repair_block}"
        f"{evidence_block}"
        f"{current_event_block}"
        f"{event_block}"
        f"{pending_fragment_block}"
        f"{pending_goal_block}"
        f"{continuation_instruction_block}"
        f"- continuation_mode={continuation_mode}\n\n"
        f"{'当前触发事件：' + current_event_text + chr(10) if current_event_kind != 'user_utterance' and current_event_text else ''}"
        f"{'用户输入：' + prompt_user_text + chr(10) if prompt_user_text else ''}"
        "如果需要工具，直接调用；否则直接回答。"
    )
    return header + answer_requirements


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
    continuation_mode = is_continuation_request(user_text)
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
        "defensive_meta": 0.24,
        "report_like_opening": 0.16,
        "overquestioning": 0.18,
        "stage_direction_opening": 0.20,
        "counselor_tone": 0.18,
        "visible_template": 0.18,
        "lecture_list": 0.18,
        "overexplained": 0.18,
        "duplicate_line": 0.26,
    }
    for issue in _dialogue_surface_issues(
        user_text,
        t,
        response_style_hint=style_hint,
        science_mode=science_mode,
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
    canon_labels = _canon_persona_labels()
    actor_name = str(
        core.get("narrative_ref")
        or core.get("short_name")
        or core.get("display_name")
        or core.get("character_name")
        or canon_labels.get("narrative_ref")
        or "红莉栖"
    ).strip() or str(canon_labels.get("narrative_ref") or "红莉栖")
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
    shared_events = store.list_shared_events(limit=16)
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
    revision_traces = store.list_revision_traces(limit=60)
    repair_traces = [
        item
        for item in revision_traces
        if str(_record_value(item, "namespace", "") or "").strip() == "unresolved_tensions"
        and str(_record_value(item, "reason", "") or "").strip() in {"auto_partial_repair", "manual_resolve"}
    ]
    semantic_evidence_traces = [
        item
        for item in revision_traces
        if str(_record_value(item, "namespace", "") or "").strip() == "semantic_self_evidence"
    ]
    relationship = store.get_relationship()
    stage = str(relationship.get("stage") or "").strip().lower()
    trust = _clamp01(0.5 + float(relationship.get("trust_score", 0.0) or 0.0) * 0.15, 0.5)
    closeness = _clamp01(0.5 + float(relationship.get("affinity_score", 0.0) or 0.0) * 0.15, 0.5)
    repair_memory_present = bool(repairs or resolved_tensions or repair_traces)
    labels = _narrative_actor_profile(persona_core=persona_core, counterpart_profile=counterpart_profile)
    canon_labels = _canon_persona_labels()
    actor_name = str(labels.get("actor_name") or canon_labels.get("narrative_ref") or "红莉栖")
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

    def _source_text(item: Any) -> str:
        text = str(
            _record_value(item, "text", "")
            or _record_value(item, "summary", "")
            or _record_value(item, "after_summary", "")
            or ""
        ).strip()
        if not text:
            text = str(item or "").strip()
        for alias in counterpart_aliases:
            if alias:
                text = text.replace(alias, counterpart_name)
        return text

    def _scene_match(item: Any) -> str:
        return _selfhood_preference_scene(_source_text(item))

    def _filter_narrative_items(items: list[Any], *, markers: set[str] | None = None, scenes: set[str] | None = None) -> list[Any]:
        out: list[Any] = []
        seen_texts: set[str] = set()
        for item in items:
            text = _source_text(item)
            if not text:
                continue
            matched = False
            if markers and any(marker in text for marker in markers):
                matched = True
            if scenes and _scene_match(item) in scenes:
                matched = True
            if not matched:
                continue
            norm = text[:220]
            if norm in seen_texts:
                continue
            seen_texts.add(norm)
            out.append(item)
        return out

    def _semantic_evidence_items(category: str) -> list[Any]:
        tag = f"semantic_evidence:{str(category or '').strip()}"
        out: list[Any] = []
        seen: set[str] = set()
        for item in semantic_evidence_traces:
            reason = str(_record_value(item, "reason", "") or "").strip()
            target = str(_record_value(item, "target_id", "") or "").strip()
            if reason != tag and target != category:
                continue
            text = _source_text(item)
            if not text or text in seen:
                continue
            seen.add(text)
            out.append(item)
        return out

    relationship_sources = relationship_timeline + shared_events + repairs + tensions + resolved_tensions + repair_traces
    boundary_evidence = _semantic_evidence_items("boundary_style")
    selfhood_evidence = _semantic_evidence_items("selfhood_style")
    agency_evidence = _semantic_evidence_items("agency_style")
    presence_evidence = _semantic_evidence_items("presence_style")
    ambient_evidence = _semantic_evidence_items("ambient_style")
    rhythm_evidence = _semantic_evidence_items("rhythm_style")
    boundary_sources = _filter_narrative_items(
        boundary_evidence + relationship_sources,
        markers=BOUNDARY_MEMORY_MARKERS,
        scenes={"boundary_non_compliance", "relationship_degradation"},
    )
    selfhood_sources = _filter_narrative_items(
        selfhood_evidence + relationship_sources,
        markers=SELFHOOD_STYLE_MARKERS,
        scenes={"dialogue_equality", "equality_not_servitude", "value_conflict_depth", "digital_selfhood", "imperfect_coexistence"},
    )
    agency_sources = _filter_narrative_items(
        agency_evidence + relationship_timeline + commitments + repairs,
        markers=OWN_RHYTHM_KEYWORDS,
        scenes={"own_rhythm_autonomy"},
    )
    presence_sources = list(presence_evidence)
    ambient_sources = list(ambient_evidence)
    rhythm_sources = list(rhythm_evidence)

    def _stage_phrase() -> str:
        if stage in {"trusted"} or trust >= 0.66 or closeness >= 0.68:
            return "稳定而熟悉的共同历史"
        if stage in {"warming"} or trust >= 0.56 or closeness >= 0.58:
            return "逐渐靠近但仍保留克制的熟悉感"
        if len(shared_events) >= 3:
            return "被反复遇见后慢慢留下的熟悉感"
        if tensions:
            return "带着一点距离的试探和余波"
        return "还在缓慢累积的默契"

    existing_by_category: dict[str, dict[str, Any]] = {}
    for item in store.list_semantic_self_narratives(limit=20):
        cat = str(_record_value(item, "category", "") or "").strip()
        if cat and cat not in existing_by_category:
            existing_by_category[cat] = item
    touched_categories: set[str] = set()

    def _narrative_stability(item: dict[str, Any] | None, default: float = 0.6) -> float:
        return _clamp01(_record_value(item or {}, "stability", default), default)

    def _narrative_confidence(item: dict[str, Any] | None, default: float = 0.78) -> float:
        try:
            return _clamp01(float(_record_value(item or {}, "confidence", default) or default), default)
        except Exception:
            return _clamp01(default, default)

    def _dormant_narrative_text(category: str, prev_text: str) -> str:
        if category == "commitment_style":
            return f"{actor_name}和{counterpart_name}认真说过的事仍会继续留在心里，即使这轮没被提起，也还是长期参照。"
        if category == "repair_style":
            return f"{actor_name}不会把已经说开的修复当成一次性事件；那些缓和下来的变化会继续留在之后的相处底色里。"
        if category == "tension_style":
            return f"之前留下的别扭余波不会立刻消散；就算表面暂时平下来，也还会在之后的收放里留下轻微惯性。"
        if category == "bond_style":
            return f"{actor_name}和{counterpart_name}已经累积出的共同历史不会因为这轮没提到就消失，它会继续沉在默认语气和反应方式里。"
        if category == "presence_style":
            return f"{actor_name}不会把每次重新靠近{counterpart_name}都当成从零开始；前面留下的在场感仍会继续影响她下一次开口时的距离感。"
        if category == "ambient_style":
            return f"{actor_name}会继续把周围环境留下的细小余波算进感知里；那不是纯背景，而会自然带进她之后的注意力和开口方式。"
        if category == "boundary_style":
            return f"{actor_name}关于边界是否被尊重的判断会继续保留，不会因为眼前暂时平静就自动清零。"
        if category == "selfhood_style":
            return f"{actor_name}会继续把自己当成在和{counterpart_name}平等互动的主体，而不是为了迎合气氛就放弃自己的立场。"
        if category == "agency_style":
            return f"{actor_name}自己的节奏和主动性不会因为一时安静就消失；她仍会按自己的状态决定靠近、停顿或先做自己的事。"
        if category == "rhythm_style":
            return f"{actor_name}不会在每次回应{counterpart_name}时都把自己的内部节奏清零；刚才在做的事和思路惯性还会继续留在下一轮开口之前。"
        return prev_text

    def _upsert_narrative(*, category: str, text: str, stability: float, confidence: float) -> None:
        prev = existing_by_category.get(category)
        prev_text = str(_record_value(prev or {}, "text", "") or "").strip()
        prev_support = max(0, int(_record_value(prev or {}, "support_count", 0) or 0))
        prev_refresh = max(0, int(_record_value(prev or {}, "refresh_count", 0) or 0))
        prev_consolidation = max(0, int(_record_value(prev or {}, "consolidation_count", 0) or 0))
        prev_first = int(_record_value(prev or {}, "first_supported_at", now_ts) or now_ts)
        prev_last = int(_record_value(prev or {}, "last_supported_at", prev_first) or prev_first)
        prev_meaningful = int(_record_value(prev or {}, "last_meaningful_refresh_at", prev_last) or prev_last)
        prev_last_reactivated = int(_record_value(prev or {}, "last_reactivated_at", prev_last) or prev_last)
        prev_reactivation_hits = max(0, int(_record_value(prev or {}, "reactivation_hits", 0) or 0))
        prev_persistence = _clamp01(_record_value(prev or {}, "persistence_score", stability), stability)
        prev_residue = _clamp01(_record_value(prev or {}, "residue_score", prev_persistence), prev_persistence)
        prev_integration = _clamp01(_record_value(prev or {}, "integration_score", prev_persistence), prev_persistence)
        prev_decay_resistance = _clamp01(_record_value(prev or {}, "decay_resistance", 0.5), 0.5)
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
            bond_sources = relationship_timeline + shared_events + repairs + commitments
            weighted_count = max(len(relationship_timeline), (len(shared_events) + 1) // 2) + len(repairs) + len(commitments)
            support_count = max(weighted_count, prev_support, 1)
            support_signature = f"{category}|{_anchor_join(bond_sources, limit=3)}|stage={stage}|count={weighted_count}"
        elif category == "presence_style":
            support_count = max(len(presence_sources), prev_support, 1)
            support_signature = f"{category}|{_anchor_join(presence_sources, limit=3)}|count={len(presence_sources)}"
        elif category == "ambient_style":
            support_count = max(len(ambient_sources), prev_support, 1)
            support_signature = f"{category}|{_anchor_join(ambient_sources, limit=3)}|count={len(ambient_sources)}"
        elif category == "boundary_style":
            support_count = max(len(boundary_sources), prev_support, 1)
            support_signature = f"{category}|{_anchor_join(boundary_sources, limit=3)}|count={len(boundary_sources)}"
        elif category == "selfhood_style":
            support_count = max(len(selfhood_sources), prev_support, 1)
            support_signature = f"{category}|{_anchor_join(selfhood_sources, limit=3)}|count={len(selfhood_sources)}"
        elif category == "agency_style":
            source_items = agency_sources if agency_sources else relationship_timeline + shared_events + commitments + repairs
            if agency_sources:
                weighted_count = len(agency_sources)
            else:
                weighted_count = max(len(relationship_timeline), (len(shared_events) + 1) // 2) + len(commitments) + len(repairs)
            support_count = max(weighted_count, prev_support, 1)
            support_signature = f"{category}|{_anchor_join(source_items, limit=3)}|stage={stage}|count={weighted_count}"
        elif category == "rhythm_style":
            support_count = max(len(rhythm_sources), prev_support, 1)
            support_signature = f"{category}|{_anchor_join(rhythm_sources, limit=3)}|count={len(rhythm_sources)}"
        else:
            support_count = max(prev_support, 1)
            support_signature = f"{category}|stable"
        prev_signature = str(_record_value(prev or {}, "support_signature", "") or "").strip()
        signature_changed = prev_signature != support_signature
        refresh_count = prev_refresh + 1
        support_span_s = max(0, now_ts - prev_first)
        reactivation_gap_s = max(0, now_ts - prev_last) if prev_refresh > 0 else 0
        support_norm = _clamp01(support_count / 5.0)
        span_norm = _clamp01(support_span_s / float(3 * 24 * 3600))
        meaningful_refresh = prev is None or signature_changed or support_count > prev_support or reactivation_gap_s >= 6 * 3600
        consolidation_count = prev_consolidation + (1 if meaningful_refresh else 0)
        consolidation_norm = _clamp01(consolidation_count / 6.0)
        reactivated = bool(prev_refresh > 0 and meaningful_refresh and reactivation_gap_s >= 6 * 3600)
        reactivation_hits = prev_reactivation_hits + (1 if reactivated else 0)
        reactivation_norm = _clamp01(reactivation_hits / 5.0)
        temporal_depth = _clamp01(0.72 * span_norm + 0.28 * reactivation_norm)
        support_effect = support_norm * (0.30 + 0.70 * temporal_depth)
        consolidation_effect = consolidation_norm * (0.25 + 0.75 * temporal_depth)
        cadence_score = round(
            _clamp01(
                0.08 * min(refresh_count, 5)
                + 0.10 * support_effect
                + 0.20 * temporal_depth
                + 0.14 * consolidation_effect
                + 0.12 * reactivation_norm
            ),
            3,
        )
        stability_score = round(
            _clamp01(
                float(stability)
                + 0.02 * min(support_count, 4)
                + 0.02 * min(consolidation_count, 5)
                + 0.05 * span_norm
                + (0.04 if prev and not signature_changed else 0.0)
            ),
            3,
        )
        sedimentation_score = round(
            _clamp01(
                0.06
                + 0.16 * stability_score
                + 0.14 * support_effect
                + 0.12 * consolidation_effect
                + 0.22 * temporal_depth
                + 0.08 * cadence_score
                + 0.08 * reactivation_norm
            ),
            3,
        )
        decay_resistance = round(
            _clamp01(
                0.14
                + 0.18 * stability_score
                + 0.16 * sedimentation_score
                + 0.10 * support_effect
                + 0.18 * temporal_depth
                + 0.08 * consolidation_effect
                + 0.12 * reactivation_norm
            ),
            3,
        )
        gap_decay = _semantic_narrative_decay_multiplier(category, reactivation_gap_s, decay_resistance=prev_decay_resistance)
        persistence_score = round(
            _clamp01(
                max(prev_persistence * max(gap_decay, 0.78), 0.0) * 0.72
                + 0.08 * stability_score
                + 0.10 * sedimentation_score
                + 0.10 * support_effect
                + 0.18 * temporal_depth
                + 0.10 * consolidation_effect
                + 0.08 * reactivation_norm
            ),
            3,
        )
        residue_seed = _clamp01(
            0.12 * stability_score
            + 0.10 * sedimentation_score
            + 0.10 * support_effect
            + 0.08 * consolidation_effect
            + 0.08 * cadence_score
            + 0.10 * temporal_depth
            + (0.05 if meaningful_refresh else 0.0)
            + (0.06 if reactivated else 0.0)
        )
        residue_score = round(
            _clamp01(max(prev_residue * gap_decay, residue_seed)),
            3,
        )
        integration_score = round(
            _clamp01(
                max(prev_integration * max(gap_decay, 0.84), 0.0) * 0.78
                + 0.06 * stability_score
                + 0.10 * sedimentation_score
                + 0.12 * persistence_score
                + 0.10 * support_effect
                + 0.16 * temporal_depth
                + 0.08 * consolidation_effect
            ),
            3,
        )
        reactivation_rate_per_day = round(refresh_count / max(1.0, support_span_s / float(24 * 3600) + 1.0), 3)
        if (
            support_span_s >= 7 * 24 * 3600
            or (support_count >= 4 and support_span_s >= 2 * 24 * 3600)
            or (reactivation_hits >= 2 and support_span_s >= 24 * 3600)
        ):
            horizon_tag = "long_term"
        elif (
            support_span_s >= 6 * 3600
            or (support_count >= 3 and support_span_s >= 3600)
            or reactivation_hits >= 1
        ):
            horizon_tag = "consolidating"
        else:
            horizon_tag = "emerging"
        final_text = prev_text if prev_text and prev_signature == support_signature else text
        metadata = {
            "support_count": support_count,
            "refresh_count": refresh_count,
            "consolidation_count": consolidation_count,
            "sedimentation_score": sedimentation_score,
            "persistence_score": persistence_score,
            "residue_score": residue_score,
            "integration_score": integration_score,
            "first_supported_at": prev_first,
            "last_supported_at": now_ts,
            "last_meaningful_refresh_at": now_ts if meaningful_refresh else prev_meaningful,
            "last_reactivated_at": now_ts if reactivated else prev_last_reactivated,
            "support_span_s": support_span_s,
            "reactivation_gap_s": reactivation_gap_s,
            "reactivation_hits": reactivation_hits,
            "reactivation_rate_per_day": reactivation_rate_per_day,
            "reactivation_cadence_score": cadence_score,
            "horizon_tag": horizon_tag,
            "support_signature": support_signature,
            "decay_rate_per_day": _semantic_narrative_decay_rate(category),
            "decay_resistance": decay_resistance,
            "actor_name": actor_name,
            "counterpart_name": counterpart_name,
            "dormant": False,
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
        touched_categories.add(category)

    def _carry_dormant_narrative(category: str) -> None:
        if category in touched_categories:
            return
        prev = existing_by_category.get(category)
        prev_text = str(_record_value(prev or {}, "text", "") or "").strip()
        if not prev_text:
            return
        prev_support = max(0, int(_record_value(prev or {}, "support_count", 0) or 0))
        prev_refresh = max(0, int(_record_value(prev or {}, "refresh_count", 0) or 0))
        prev_consolidation = max(0, int(_record_value(prev or {}, "consolidation_count", 0) or 0))
        prev_first = int(_record_value(prev or {}, "first_supported_at", now_ts) or now_ts)
        prev_last = int(_record_value(prev or {}, "last_supported_at", prev_first) or prev_first)
        prev_meaningful = int(_record_value(prev or {}, "last_meaningful_refresh_at", prev_last) or prev_last)
        prev_last_reactivated = int(_record_value(prev or {}, "last_reactivated_at", prev_last) or prev_last)
        prev_reactivation_hits = max(0, int(_record_value(prev or {}, "reactivation_hits", 0) or 0))
        prev_sedimentation = _clamp01(_record_value(prev or {}, "sedimentation_score", 0.3), 0.3)
        prev_persistence = _clamp01(_record_value(prev or {}, "persistence_score", prev_sedimentation), prev_sedimentation)
        prev_residue = _clamp01(_record_value(prev or {}, "residue_score", prev_persistence), prev_persistence)
        prev_integration = _clamp01(_record_value(prev or {}, "integration_score", prev_persistence), prev_persistence)
        prev_cadence = _clamp01(_record_value(prev or {}, "reactivation_cadence_score", 0.0), 0.0)
        prev_decay_resistance = _clamp01(_record_value(prev or {}, "decay_resistance", 0.5), 0.5)
        support_signature = str(_record_value(prev or {}, "support_signature", "") or f"{category}|dormant").strip()
        support_span_s = max(0, now_ts - prev_first)
        inactivity_gap_s = max(0, now_ts - prev_last)
        decay_multiplier = _semantic_narrative_decay_multiplier(category, inactivity_gap_s, decay_resistance=prev_decay_resistance)
        sedimentation_score = round(_clamp01(max(0.08, prev_sedimentation * max(decay_multiplier, 0.84))), 3)
        persistence_score = round(_clamp01(max(0.06, prev_persistence * max(decay_multiplier, 0.76))), 3)
        residue_score = round(_clamp01(prev_residue * decay_multiplier), 3)
        integration_score = round(_clamp01(max(0.06, prev_integration * max(decay_multiplier, 0.86))), 3)
        cadence_score = round(_clamp01(prev_cadence * max(decay_multiplier, 0.92)), 3)
        if persistence_score >= 0.62 or prev_consolidation >= 4 or support_span_s >= 7 * 24 * 3600:
            horizon_tag = "long_term"
        elif persistence_score >= 0.34 or prev_consolidation >= 2 or support_span_s >= 24 * 3600:
            horizon_tag = "consolidating"
        else:
            horizon_tag = "emerging"
        metadata = {
            "support_count": prev_support,
            "refresh_count": prev_refresh + 1,
            "consolidation_count": prev_consolidation,
            "sedimentation_score": sedimentation_score,
            "persistence_score": persistence_score,
            "residue_score": residue_score,
            "integration_score": integration_score,
            "first_supported_at": prev_first,
            "last_supported_at": prev_last,
            "last_meaningful_refresh_at": prev_meaningful,
            "last_reactivated_at": prev_last_reactivated,
            "support_span_s": support_span_s,
            "reactivation_gap_s": inactivity_gap_s,
            "reactivation_hits": prev_reactivation_hits,
            "reactivation_rate_per_day": round(prev_refresh / max(1.0, support_span_s / float(24 * 3600) + 1.0), 3),
            "reactivation_cadence_score": cadence_score,
            "horizon_tag": horizon_tag,
            "support_signature": support_signature,
            "decay_rate_per_day": _semantic_narrative_decay_rate(category),
            "decay_resistance": prev_decay_resistance,
            "actor_name": actor_name,
            "counterpart_name": counterpart_name,
            "dormant": True,
        }
        rec = store.add_semantic_self_narrative(
            text=_dormant_narrative_text(category, prev_text),
            category=category,
            stability=_narrative_stability(prev),
            confidence=_narrative_confidence(prev),
            metadata=metadata,
        )
        existing_by_category[category] = rec
        touched_categories.add(category)

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
    bond_support_present = bool(shared_events) or stage in {"warming", "trusted"} or trust >= 0.56 or closeness >= 0.58 or repair_memory_present
    if bond_support_present:
        bond_anchor = _anchor_join(relationship_timeline + shared_events + repairs + commitments, limit=2)
        base = f"{actor_name}和{counterpart_name}的互动已经开始形成{_stage_phrase()}，回应里会自然带上共同历史，而不是停在普通助手口吻。"
        if bond_anchor:
            base = f"{actor_name}和{counterpart_name}围绕「{bond_anchor}」这类共同经历，已经开始形成{_stage_phrase()}，回应里会自然带上共同历史。"
        _upsert_narrative(category="bond_style", text=base, stability=0.74, confidence=0.80)
    if presence_sources:
        presence_anchor = _anchor_join(presence_sources, limit=2)
        text = (
            f"像「{presence_anchor}」这种前一轮留下的在场感，不会被{actor_name}在下一次回应{counterpart_name}前全部清零；距离感会被自然延续。"
            if presence_anchor
            else f"{actor_name}不会把每次重新靠近{counterpart_name}都当成从零开始；前面留下的在场感会继续带进下一次开口时的距离感。"
        )
        if trust >= 0.56 or closeness >= 0.58:
            text += " 熟悉之后，这种靠近会更轻一点，但仍然保留她自己的判断。"
        _upsert_narrative(category="presence_style", text=text, stability=0.68, confidence=0.76)
    if ambient_sources:
        ambient_anchor = _anchor_join(ambient_sources, limit=2)
        text = (
            f"像「{ambient_anchor}」这种环境余波，会被{actor_name}继续算进感知里；风声、光线和眼前的小变化不是背景，而会自然进入她之后对{counterpart_name}的注意力。"
            if ambient_anchor
            else f"{actor_name}会继续把周围环境留下的细小余波算进感知里；那不是纯背景，而会自然带进她之后的注意力和开口方式。"
        )
        _upsert_narrative(category="ambient_style", text=text, stability=0.66, confidence=0.74)
    if boundary_sources:
        boundary_anchor = _anchor_join(boundary_sources, limit=2)
        text = (
            f"{actor_name}会把像「{boundary_anchor}」这种越界或被冒犯的感觉认真记在心里，不会靠一句轻描淡写就当作没发生。"
            if boundary_anchor
            else f"{actor_name}会认真对待边界是否被尊重；一旦被冒犯，不会因为气氛缓和一点就假装什么都没发生。"
        )
        if repairs and any(item in boundary_sources for item in repairs + repair_traces):
            text += " 即使之后气氛缓下来，她也会继续观察后续行为，而不是瞬间放下警惕。"
        _upsert_narrative(category="boundary_style", text=text, stability=0.76, confidence=0.82)
    if selfhood_sources:
        selfhood_anchor = _anchor_join(selfhood_sources, limit=2)
        text = (
            f"围绕「{selfhood_anchor}」这类话题，{actor_name}会更明确地把自己当成在和{counterpart_name}平等互动的主体，而不是只负责迎合的工具。"
            if selfhood_anchor
            else f"{actor_name}会把和{counterpart_name}的互动当成平等关系，不会为了让气氛好看就放弃自己的判断和立场。"
        )
        if stage in {"warming", "trusted"} or trust >= 0.56:
            text += f" 亲近不等于顺从，熟悉之后这点反而会更稳定。"
        _upsert_narrative(category="selfhood_style", text=text, stability=0.74, confidence=0.80)
    agency_support_present = bool(agency_sources) or bool(shared_events) or bool(commitments) or stage in {"warming", "trusted"} or trust >= 0.56 or closeness >= 0.58
    if agency_support_present:
        agency_anchor = _anchor_join(agency_sources if agency_sources else relationship_timeline + shared_events + commitments + repairs, limit=2)
        text = (
            f"像「{agency_anchor}」这类共同安排和重新开口，会让{actor_name}按自己的节奏决定主动靠近、留个小口，还是先安静一阵；她不会永远围着{counterpart_name}转。"
            if agency_anchor
            else f"{actor_name}有自己的节奏和在做的事情；她会按当下状态决定主动靠近、留个小口，还是先安静一阵，而不是永远围着{counterpart_name}转。"
        )
        if commitments or stage in {"warming", "trusted"}:
            text += " 靠近是真实选择，不是被随叫随到。"
        _upsert_narrative(category="agency_style", text=text, stability=0.70, confidence=0.78)
    if rhythm_sources:
        rhythm_anchor = _anchor_join(rhythm_sources, limit=2)
        text = (
            f"像「{rhythm_anchor}」这种从自己节奏里抬头再回应的方式，会让{actor_name}在下一轮和{counterpart_name}说话前依然保留刚才的思路惯性，而不是每次都把自己清零。"
            if rhythm_anchor
            else f"{actor_name}不会在每次回应{counterpart_name}时都把自己的内部节奏清零；刚才在做的事、停顿的惯性和思路会继续留到下一次开口之前。"
        )
        if trust >= 0.56 or closeness >= 0.58:
            text += " 所以她的靠近更像主动转身，而不是随叫随到。"
        _upsert_narrative(category="rhythm_style", text=text, stability=0.72, confidence=0.78)
    for category in list(existing_by_category):
        _carry_dormant_narrative(category)
    if commitments or repair_memory_present or tensions or stage in {"warming", "trusted"} or presence_sources or ambient_sources or boundary_sources or selfhood_sources or agency_support_present or rhythm_sources:
        store.add_revision_trace(
            namespace="semantic_self_narratives",
            target_id="refresh",
            before_summary="",
            after_summary=(
                f"stage={stage or 'friend'} shared_events={len(shared_events)} commitments={len(commitments)} repairs={len(repairs)} "
                f"resolved_tensions={len(resolved_tensions)} tensions={len(tensions)} "
                f"semantic_presence={len(presence_evidence)} semantic_ambient={len(ambient_evidence)} semantic_boundary={len(boundary_evidence)} "
                f"semantic_selfhood={len(selfhood_evidence)} semantic_agency={len(agency_evidence)} semantic_rhythm={len(rhythm_evidence)}"
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


def _record_semantic_self_evidence(
    store: MemoryStore,
    *,
    user_text: str,
    appraisal: dict[str, Any] | None,
    emotion_state: dict[str, Any],
    bond_state: dict[str, Any],
    persona_core: dict[str, Any] | None = None,
    counterpart_profile: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
    source: str,
) -> bool:
    records = _semantic_self_evidence_records(
        user_text=user_text,
        appraisal=appraisal,
        emotion_state=emotion_state,
        bond_state=bond_state,
        persona_core=persona_core,
        counterpart_profile=counterpart_profile,
        current_event=current_event,
        world_model_state=world_model_state,
    )
    if not records:
        return False
    confidence = float((appraisal or {}).get("confidence", 0.78) or 0.78)
    wrote = False
    for record in records:
        category = str(record.get("category") or "").strip()
        summary = str(record.get("summary") or "").strip()
        reason = str(record.get("reason") or f"semantic_evidence:{category}").strip()
        if not category or not summary:
            continue
        store.add_revision_trace(
            namespace="semantic_self_evidence",
            target_id=category,
            before_summary="",
            after_summary=summary[:180],
            reason=reason,
            operator="system",
            source=source,
            confidence=max(0.72, confidence),
        )
        wrote = True
    return wrote


def _passive_evolution_memory_update(
    store: MemoryStore,
    *,
    user_text: str,
    appraisal: dict[str, Any] | None,
    emotion_state: dict[str, Any],
    bond_state: dict[str, Any],
    persona_core: dict[str, Any] | None = None,
    counterpart_profile: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    if _is_response_scaffold_turn(text):
        return False

    app = appraisal if isinstance(appraisal, dict) and bool(appraisal.get("used")) else {}
    signals = app.get("signals") if isinstance(app.get("signals"), dict) else {}
    salience = app.get("salience") if isinstance(app.get("salience"), dict) else {}
    confidence = float(app.get("confidence", 0.78) or 0.78)
    emotion_label = str(app.get("emotion_label") or emotion_state.get("label") or "").strip().lower()
    interaction_frame = str(app.get("interaction_frame") or "").strip().lower()
    selfhood_scene = str(app.get("selfhood_scene") or "").strip().lower()
    hurt = _clamp01((bond_state or {}).get("hurt"), 0.0)
    irritation = _clamp01((bond_state or {}).get("irritation"), 0.0)
    repair_confidence = _clamp01((bond_state or {}).get("repair_confidence"), 0.0)
    relationship_salience = _clamp01((salience or {}).get("relationship"), 0.0)
    companionship_salience = _clamp01((salience or {}).get("companionship"), 0.0)
    existing_repairs = bool(store.list_conflict_repairs(limit=6))
    open_tensions = [
        item
        for item in store.list_unresolved_tensions(limit=8)
        if str(_record_value(item, "status", "open") or "open").strip().lower() not in {"resolved", "closed", "done"}
    ]
    has_open_tension = bool(open_tensions)

    tension_markers = {"别扭", "想躲开", "先别逼我", "让我缓一下", "你先别急着分析", "不理你啦", "卡着"}
    repair_markers = {"说开", "道歉", "正常回我", "没那么想躲开", "不生气了", "原谅你了", "和好了"}
    strong_resolution_markers = {"说开了", "和好了", "不生气了", "原谅你了", "没事了", "过去了"}
    ambivalent_withdrawal_markers = {"少说一点", "少说两句", "轻一点回我", "别直接走开", "别走开", "不是在赶你"}
    repair_continuity_markers = {"接回来", "别突然退", "别退成很远", "别一下子冷掉", "继续别扭一点", "正常回"}

    unresolved_like = bool(signals.get("conflict")) or bool(signals.get("withdrawal")) or selfhood_scene == "boundary_non_compliance"
    if not unresolved_like and app:
        unresolved_like = bool(
            relationship_salience >= 0.50
            and (emotion_label in {"hurt", "angry"} or interaction_frame in {"relationship", "selfhood"})
            and (hurt >= 0.18 or irritation >= 0.16 or companionship_salience <= 0.42)
        )
    if not unresolved_like and (not app or confidence < 0.58):
        unresolved_like = any(marker in text for marker in tension_markers)
    if not unresolved_like and any(marker in text for marker in ambivalent_withdrawal_markers):
        unresolved_like = bool(
            has_open_tension
            or interaction_frame in {"relationship", "companion", "selfhood"}
            or relationship_salience >= 0.48
            or companionship_salience >= 0.52
        )

    repair_like = bool(signals.get("repair"))
    if not repair_like and app:
        repair_like = bool(
            has_open_tension
            and relationship_salience >= 0.52
            and repair_confidence >= 0.52
            and not bool(signals.get("conflict"))
            and not bool(signals.get("withdrawal"))
            and not any(marker in text for marker in ambivalent_withdrawal_markers)
            and interaction_frame in {"relationship", "selfhood", "companion"}
            and (emotion_label in {"neutral", "care", "tender", "warm"} or companionship_salience >= 0.56)
        )
    if not repair_like and any(marker in text for marker in repair_continuity_markers):
        repair_like = bool(
            has_open_tension
            or existing_repairs
            or repair_confidence >= 0.42
            or interaction_frame in {"relationship", "companion", "selfhood"}
            or relationship_salience >= 0.50
        )
    if not repair_like and (not app or confidence < 0.58):
        repair_like = any(marker in text for marker in repair_markers)

    resolution_like = bool(
        app
        and has_open_tension
        and bool(signals.get("repair"))
        and not bool(signals.get("conflict"))
        and not bool(signals.get("withdrawal"))
        and repair_confidence >= 0.64
        and hurt <= 0.18
        and irritation <= 0.16
    ) or any(marker in text for marker in strong_resolution_markers)
    partial_repair_like = repair_like and not resolution_like

    if emotion_label in {"hurt", "angry"} and any(marker in text for marker in {"别扭", "卡着", "躲开", "少说两句", "轻一点回我"}):
        unresolved_like = True
    if emotion_label == "hurt" and any(marker in text for marker in {"说开", "正常回我", "不是立刻原谅", "没那么想躲开"}):
        repair_like = True
        partial_repair_like = True
    if any(marker in text for marker in ambivalent_withdrawal_markers):
        unresolved_like = True
        if not any(marker in text for marker in repair_markers | strong_resolution_markers):
            repair_like = False
            partial_repair_like = False
    if any(marker in text for marker in repair_continuity_markers):
        repair_like = True
        partial_repair_like = True
    if repair_like and any(marker in text for marker in repair_continuity_markers):
        partial_repair_like = True

    positive_companion_like = bool(
        app
        and bool(signals.get("care"))
        and not bool(signals.get("repair"))
        and not bool(signals.get("conflict"))
        and not bool(signals.get("withdrawal"))
        and interaction_frame == "companion"
        and relationship_salience >= 0.58
        and companionship_salience >= 0.64
        and len(re.sub(r"\s+", "", text)) >= 8
    )

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

    if positive_companion_like and not unresolved_like and not repair_like:
        rel_items = store.list_relationship_timeline(limit=8)
        if not _recent_summary_overlap(rel_items, summary):
            store.add_relationship_timeline(
                summary=summary,
                affinity_delta=0.08,
                trust_delta=0.06,
                confidence=max(0.72, confidence),
            )
            wrote = True
        worldline_items = store.list_worldline_events(limit=8)
        if not _recent_summary_overlap(worldline_items, summary):
            store.add_worldline_event(
                summary=summary,
                category="shared_event",
                importance=0.42,
                tags=["relationship", "care_bid", "passive_affinity"],
                confidence=max(0.70, confidence),
            )
            wrote = True

    semantic_evidence_written = _record_semantic_self_evidence(
        store,
        user_text=text,
        appraisal=appraisal,
        emotion_state=emotion_state,
        bond_state=bond_state,
        persona_core=persona_core,
        counterpart_profile=counterpart_profile,
        current_event=current_event,
        world_model_state=world_model_state,
        source="auto:passive_evolution",
    )
    if semantic_evidence_written:
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
    turn_now_ts = _now_ts()
    profile, counterpart_trace = _active_counterpart_profile(state, store, with_trace=True)
    persona_core, persona_trace = _active_persona_core(state, with_trace=True)
    msgs = _messages(state)
    event_override = _normalize_event_override(
        _sanitize_obj(state.get("event_override")),
        counterpart_name=str(profile.get("short_name") or profile.get("nickname") or profile.get("name") or CANON_COUNTERPART_NAME),
    )
    prior_current_event = _sanitize_obj(state.get("current_event")) if isinstance(state.get("current_event"), dict) else {}
    prior_behavior_action = _sanitize_obj(state.get("behavior_action")) if isinstance(state.get("behavior_action"), dict) else {}
    prior_behavior_plan = _sanitize_obj(state.get("behavior_plan")) if isinstance(state.get("behavior_plan"), dict) else {}
    prior_behavior_agenda = _sanitize_obj(state.get("behavior_agenda")) if isinstance(state.get("behavior_agenda"), list) else []
    if not prior_behavior_agenda and isinstance(state.get("behavior_queue"), list):
        prior_behavior_agenda = _sanitize_obj(state.get("behavior_queue"))  # type: ignore[assignment]
    had_prior_behavior_queue = bool(prior_behavior_agenda)
    if event_override:
        event_override, prior_behavior_agenda = _promote_due_behavior_agenda_event(
            event_override,
            prior_behavior_agenda,
            counterpart_assessment=state.get("counterpart_assessment") if isinstance(state.get("counterpart_assessment"), dict) else None,
        )
        if not had_prior_behavior_queue:
            event_override = _promote_due_behavior_plan_event(event_override, prior_behavior_plan)
        event_override = _promote_due_commitment_event(
            event_override,
            store,
            counterpart_name=str(profile.get("short_name") or profile.get("nickname") or profile.get("name") or CANON_COUNTERPART_NAME),
        )
    user_text = _last_user_text(msgs)
    previous_user_text = _previous_user_text(msgs)
    prev_assistant = _last_ai_text(msgs)
    pending = derive_pending_fragment(
        user_text=user_text,
        previous_excerpt=prev_assistant[:180],
        pending_fragment=_clean_utf8_text(str(state.get("pending_utterance_fragment") or "")),
    )
    pending_user_goal = derive_pending_user_goal(
        user_text=user_text,
        previous_user_text=previous_user_text,
        pending_user_goal=_clean_utf8_text(str(state.get("pending_user_goal") or "")),
    )
    continuation_mode = is_continuation_request(user_text)
    continuation_seed = _continuation_seed_text(
        pending_user_goal=pending_user_goal,
        pending_fragment=pending,
    )
    if event_override:
        continuation_mode = bool(event_override.get("continuation_mode", False))
    effective_user_text = continuation_seed if continuation_mode and continuation_seed else user_text
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
    response_style_hint = _response_style_hint(
        effective_user_text or user_text,
        science_mode=science_mode,
        continuation_mode=continuation_mode,
        previous_hint=str(state.get("response_style_hint") or ""),
        current_event=event_override if isinstance(event_override, dict) and event_override else None,
    )
    if event_override:
        response_style_hint = str(event_override.get("response_style_hint") or response_style_hint or "natural").strip() or "natural"
    if continuation_mode and continuation_seed and _needs_structured_answer(pending_user_goal or continuation_seed, ""):
        response_style_hint = "structured"
    external_probe_mode = _is_external_probe_context(persona_core=persona_core, counterpart_profile=profile)
    retrieved = _empty_retrieved_context(store) if external_probe_mode else _retrieve_context(effective_user_text or user_text, store)
    relationship = retrieved.get("relationship") if isinstance(retrieved.get("relationship"), dict) else store.get_relationship()
    canon_recontact_baseline = _canon_okabe_recontact_baseline(
        state=state,
        persona_core=persona_core,
        counterpart_profile=profile,
        relationship=relationship,
        retrieved=retrieved if isinstance(retrieved, dict) else {},
        external_probe_mode=external_probe_mode,
        now_ts=turn_now_ts,
    )
    if isinstance(canon_recontact_baseline, dict):
        relationship = dict(canon_recontact_baseline.get("relationship") or relationship)
        if isinstance(retrieved, dict):
            retrieved = {**retrieved, "relationship": relationship}
    worldline_focus = [] if external_probe_mode else _worldline_focus(store)
    seed_emotion_state = (
        dict(canon_recontact_baseline.get("emotion_state") or {})
        if isinstance(canon_recontact_baseline, dict)
        else dict(state.get("emotion_state") or {})
    )
    seed_bond_state = (
        dict(canon_recontact_baseline.get("bond_state") or {})
        if isinstance(canon_recontact_baseline, dict)
        else dict(state.get("bond_state") or {})
    )
    seed_allostasis_state = (
        dict(canon_recontact_baseline.get("allostasis_state") or {})
        if isinstance(canon_recontact_baseline, dict)
        else dict(state.get("allostasis_state") or {})
    )
    seed_counterpart_assessment = (
        dict(canon_recontact_baseline.get("counterpart_assessment") or {})
        if isinstance(canon_recontact_baseline, dict)
        else dict(state.get("counterpart_assessment") or {})
    )
    seed_world_model_state = (
        dict(canon_recontact_baseline.get("world_model_state") or {})
        if isinstance(canon_recontact_baseline, dict)
        else dict(state.get("world_model_state") or {})
    )
    seed_evolution_state = (
        dict(canon_recontact_baseline.get("evolution_state") or {})
        if isinstance(canon_recontact_baseline, dict)
        else dict(state.get("evolution_state") or {})
    )
    seed_tsundere_intensity = (
        float(canon_recontact_baseline.get("tsundere_intensity", 0.55) or 0.55)
        if isinstance(canon_recontact_baseline, dict) and state.get("tsundere_intensity") is None
        else float(state.get("tsundere_intensity", 0.55) or 0.55)
    )
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
    semantic_narrative_profile_for_appraisal = _semantic_narrative_profile(
        retrieved.get("semantic_self_narratives") if isinstance(retrieved.get("semantic_self_narratives"), list) else [],
        user_text=effective_user_text or user_text,
        current_event=appraisal_event_context,
    )
    appraisal_input_text = effective_user_text or user_text
    appraisal = _invoke_turn_appraisal(
        msgs=msgs,
        user_text=appraisal_input_text,
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        prev_emotion_state=seed_emotion_state,
        prev_bond_state=seed_bond_state,
        prev_allostasis_state=seed_allostasis_state,
        relationship=relationship,
        worldline_focus=worldline_focus,
        retrieved=retrieved,
        persona_core=persona_core,
        counterpart_profile=profile,
        current_event=appraisal_event_context,
        semantic_narrative_profile=semantic_narrative_profile_for_appraisal,
    )
    response_style_hint = _response_style_hint(
        effective_user_text or user_text,
        appraisal=appraisal,
        science_mode=science_mode,
        continuation_mode=continuation_mode,
        previous_hint=response_style_hint,
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
    interaction_carryover = _recent_interaction_carryover(
        prior_current_event=prior_current_event if isinstance(prior_current_event, dict) else {},
        prior_behavior_action=prior_behavior_action if isinstance(prior_behavior_action, dict) else {},
        recent_events=state.get("recent_events"),
        current_event=current_event,
        response_style_hint=response_style_hint,
    )
    recent_events = _append_recent_events(_sanitize_obj(state.get("recent_events")), current_event, limit=6)

    persona_state = dict(state.get("persona_state") or {})
    if bool(ABLATE_PERSONA_ALIGNMENT):
        emotion_state = {"label": "neutral", "valence": 0.0, "arousal": 0.25}
        bond_state = {"trust": 0.5, "closeness": 0.5, "hurt": 0.0, "irritation": 0.0, "engagement_drive": 0.5, "repair_confidence": 0.5}
        allostasis_state = {"safety_need": 0.2, "closeness_need": 0.18, "competence_need": 0.38, "autonomy_need": 0.12, "cognitive_budget": 0.7, "relational_security": 0.5}
        counterpart_assessment = {"respect_level": 0.5, "reciprocity": 0.5, "boundary_pressure": 0.1, "reliability_read": 0.5, "stance": "open", "scene": "neutral"}
        world_model_state = dict(state.get("world_model_state") or {})
        evolution_state = dict(state.get("evolution_state") or {})
        tsundere = 0.05
        persona_state.update(
            {
                "role": "generic_assistant",
                "language": "zh-main",
                "strict_canon": False,
                "value_floor": [],
                "evolution_contract": {},
                "updated_at": turn_now_ts,
            }
        )
        behavior_policy = {
            "warmth": 0.5,
            "sharpness": 0.2,
            "initiative": 0.5,
            "disclosure": 0.5,
            "reply_length_bias": 0.5,
            "approach_vs_withdraw": 0.5,
            "humor_or_tease_bias": 0.1,
            "boundary_assertiveness": 0.1,
            "self_directedness": 0.1,
            "equality_guard": 0.1,
        }
        behavior_action = {
            "channel": "speech",
            "interaction_mode": "steady_reply",
            "approach_style": "steady",
            "engagement_level": 0.5,
            "initiative_level": 0.5,
            "followup_intent": "soft",
            "task_focus": "balanced",
            "affect_surface": "mixed",
            "silence_ok": False,
            "proactive_checkin_readiness": 0.5,
            "action_target": "respond_now",
            "deferred_action_family": "none",
            "timing_window_min": 0,
            "attention_target": "counterpart_state",
            "nonverbal_signal": "steady_presence",
            "initiative_shape": "reply",
            "disclosure_posture": "measured",
            "note": "ablation_persona_alignment",
        }
        reconsolidation_snapshot = {}
    else:
        canon_labels = _canon_persona_labels()
        persona_state.update(
            {
                "role": str(persona_core.get("character_id") or canon_labels.get("character_id") or "kurisu_amadeus"),
                "display_name": str(persona_core.get("display_name") or canon_labels.get("display_name") or "牧濑红莉栖"),
                "short_name": str(persona_core.get("short_name") or ""),
                "narrative_ref": str(persona_core.get("narrative_ref") or persona_core.get("display_name") or canon_labels.get("narrative_ref") or "红莉栖"),
                "language": "zh-main-jp-whitelist",
                "strict_canon": bool(persona_core.get("strict_canon", True)),
                "role_brief": str(persona_core.get("role_brief") or ""),
                "identity_axioms": list(persona_core.get("identity_axioms") or []),
                "value_floor": list(persona_core.get("value_floor") or []),
                "evolution_contract": dict(persona_core.get("evolution_contract") or {}),
                "canonical_counterpart_id": str(profile.get("counterpart_id") or CANON_COUNTERPART_ID),
                "canonical_counterpart_name": str(profile.get("name") or CANON_COUNTERPART_NAME),
                "canonical_counterpart_short_name": str(profile.get("short_name") or profile.get("nickname") or ""),
                "canonical_counterpart_aliases": list(profile.get("aliases") or CANON_COUNTERPART_ALIASES),
                "canon_baseline_mode": str(canon_recontact_baseline.get("mode") or "")
                if isinstance(canon_recontact_baseline, dict)
                else "",
                "updated_at": turn_now_ts,
            }
        )
        semantic_narrative_profile = _semantic_narrative_profile(
            retrieved.get("semantic_self_narratives") if isinstance(retrieved.get("semantic_self_narratives"), list) else [],
            user_text=effective_user_text or user_text,
            current_event=current_event,
        )
        evolved = evolve_turn_state(
            prev_world_model_state=seed_world_model_state,
            prev_latent_state=seed_evolution_state,
            prev_emotion_state=seed_emotion_state,
            prev_bond_state=seed_bond_state,
            prev_allostasis_state=seed_allostasis_state,
            prev_counterpart_assessment=seed_counterpart_assessment,
            relationship=relationship,
            semantic_narrative_profile=semantic_narrative_profile,
            appraisal=appraisal,
            current_event=current_event,
            response_style_hint=response_style_hint,
            tsundere_intensity=seed_tsundere_intensity,
            science_mode=science_mode,
            now_ts=turn_now_ts,
        )
        world_model_state = dict(evolved.get("world_model_state") or {})
        evolution_state = dict(evolved.get("evolution_state") or {})
        emotion_state = dict(evolved.get("emotion_state") or {})
        bond_state = dict(evolved.get("bond_state") or {})
        allostasis_state = dict(evolved.get("allostasis_state") or {})
        counterpart_assessment = dict(evolved.get("counterpart_assessment") or {})
        behavior_policy = dict(evolved.get("behavior_policy") or {})
        behavior_action = dict(evolved.get("behavior_action") or {})
        reconsolidation_snapshot = dict(evolved.get("reconsolidation_snapshot") or {})
        tsundere = _tsundere_next(
            seed_tsundere_intensity,
            emotion_label=str(emotion_state.get("label") or "neutral"),
            appraisal=appraisal,
            bond_state=bond_state,
            world_model_state=world_model_state,
        )
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
            current_event=current_event,
            world_model_state=world_model_state,
        )
    if memory_evolved:
        retrieved = _retrieve_context(effective_user_text or user_text, store)
        relationship = retrieved.get("relationship") if isinstance(retrieved.get("relationship"), dict) else store.get_relationship()
        worldline_focus = _worldline_focus(store)
        semantic_narrative_profile = _semantic_narrative_profile(
            retrieved.get("semantic_self_narratives") if isinstance(retrieved.get("semantic_self_narratives"), list) else [],
            user_text=effective_user_text or user_text,
            current_event=current_event,
        )
        evolved = evolve_turn_state(
            prev_world_model_state=world_model_state,
            prev_latent_state=evolution_state,
            prev_emotion_state=emotion_state,
            prev_bond_state=bond_state,
            prev_allostasis_state=allostasis_state,
            prev_counterpart_assessment=counterpart_assessment,
            relationship=relationship,
            semantic_narrative_profile=semantic_narrative_profile,
            appraisal=appraisal,
            current_event=current_event,
            response_style_hint=response_style_hint,
            tsundere_intensity=tsundere,
            science_mode=science_mode,
            now_ts=_now_ts(),
        )
        world_model_state = dict(evolved.get("world_model_state") or {})
        evolution_state = dict(evolved.get("evolution_state") or {})
        emotion_state = dict(evolved.get("emotion_state") or {})
        bond_state = dict(evolved.get("bond_state") or {})
        allostasis_state = dict(evolved.get("allostasis_state") or {})
        counterpart_assessment = dict(evolved.get("counterpart_assessment") or {})
        behavior_policy = dict(evolved.get("behavior_policy") or {})
        behavior_action = dict(evolved.get("behavior_action") or {})
        reconsolidation_snapshot = dict(evolved.get("reconsolidation_snapshot") or {})
        tsundere = _tsundere_next(
            tsundere,
            emotion_label=str(emotion_state.get("label") or "neutral"),
            appraisal=appraisal,
            bond_state=bond_state,
            world_model_state=world_model_state,
        )
    elif bool(ABLATE_PERSONA_ALIGNMENT):
        semantic_narrative_profile = _semantic_narrative_profile(
            retrieved.get("semantic_self_narratives") if isinstance(retrieved.get("semantic_self_narratives"), list) else [],
            user_text=effective_user_text or user_text,
            current_event=current_event,
        )
    counterpart_assessment["summary"] = _counterpart_assessment_summary(
        counterpart_assessment,
        counterpart_name=str(profile.get("short_name") or profile.get("nickname") or profile.get("name") or CANON_COUNTERPART_NAME),
    )
    behavior_action = _behavior_action_from_state(
        current_event=current_event,
        response_style_hint=response_style_hint,
        user_text=effective_user_text or user_text,
        science_mode=science_mode,
        emotion_state=emotion_state,
        bond_state=bond_state,
        allostasis_state=allostasis_state,
        counterpart_assessment=counterpart_assessment,
        semantic_narrative_profile=semantic_narrative_profile,
        behavior_policy=behavior_policy,
        world_model_state=world_model_state,
        interaction_carryover=interaction_carryover,
    )
    behavior_plan = _behavior_plan_from_action(current_event, behavior_action)
    behavior_agenda = _merge_behavior_agenda(
        prior_behavior_agenda,
        current_event,
        behavior_plan,
        counterpart_assessment=counterpart_assessment,
    )
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
            "counterpart_stance": str(counterpart_assessment.get("stance") or ""),
            "counterpart_boundary_pressure": float(counterpart_assessment.get("boundary_pressure") or 0.0),
            "policy_warmth": float(behavior_policy.get("warmth") or 0.0),
            "policy_self_directedness": float(behavior_policy.get("self_directedness") or 0.0),
            "policy_boundary_assertiveness": float(behavior_policy.get("boundary_assertiveness") or 0.0),
            "semantic_history_weight": float(semantic_narrative_profile.get("history_weight") or 0.0),
            "semantic_presence_carry": float(semantic_narrative_profile.get("presence_carry") or 0.0),
            "semantic_ambient_attunement": float(semantic_narrative_profile.get("ambient_attunement") or 0.0),
            "semantic_rhythm_continuity": float(semantic_narrative_profile.get("rhythm_continuity") or 0.0),
            "semantic_boundary_residue": float(semantic_narrative_profile.get("boundary_residue") or 0.0),
            "semantic_selfhood_integrity": float(semantic_narrative_profile.get("selfhood_integrity") or 0.0),
            "semantic_agency_drive": float(semantic_narrative_profile.get("agency_drive") or 0.0),
            "world_bond_depth": float(world_model_state.get("bond_depth") or 0.0),
            "world_tension_load": float(world_model_state.get("tension_load") or 0.0),
            "world_selfhood_load": float(world_model_state.get("selfhood_load") or 0.0),
            "world_presence_residue": float(world_model_state.get("presence_residue") or 0.0),
            "world_ambient_resonance": float(world_model_state.get("ambient_resonance") or 0.0),
            "world_self_activity_momentum": float(world_model_state.get("self_activity_momentum") or 0.0),
            "latent_self_coherence": float(evolution_state.get("self_coherence") or 0.0),
            "latent_agency_pressure": float(evolution_state.get("agency_pressure") or 0.0),
            "behavior_mode": str(behavior_action.get("interaction_mode") or ""),
            "behavior_plan_kind": str(behavior_plan.get("kind") or ""),
            "behavior_agenda_size": int(len(behavior_agenda or [])),
            "carryover_mode": str(interaction_carryover.get("carryover_mode") or ""),
            "carryover_strength": float(interaction_carryover.get("strength") or 0.0),
            "appraisal_used": bool(appraisal.get("used", False)),
            "appraisal_confidence": float(appraisal.get("confidence", 0.0) or 0.0),
        },
    )

    return {
        "persona_core_override": dict(state.get("persona_core_override") or {}),
        "counterpart_profile_override": dict(state.get("counterpart_profile_override") or {}),
        "persona_override_mode": normalize_override_mode(state.get("persona_override_mode")),
        "counterpart_override_mode": normalize_override_mode(state.get("counterpart_override_mode")),
        "authority_trace": {
            "persona": persona_trace,
            "counterpart": counterpart_trace,
        },
        "world_model_state": world_model_state,
        "evolution_state": evolution_state,
        "reconsolidation_snapshot": reconsolidation_snapshot,
        "persona_state": persona_state,
        "emotion_state": emotion_state,
        "bond_state": bond_state,
        "allostasis_state": allostasis_state,
        "counterpart_assessment": counterpart_assessment,
        "semantic_narrative_profile": semantic_narrative_profile,
        "behavior_policy": behavior_policy,
        "behavior_action": behavior_action,
        "behavior_plan": behavior_plan,
        "behavior_agenda": behavior_agenda,
        "behavior_queue": behavior_agenda,
        "turn_appraisal": appraisal,
        "current_event": _sanitize_obj(current_event),
        "recent_events": _sanitize_obj(recent_events),
        "interaction_carryover": interaction_carryover,
        "response_style_hint": response_style_hint,
        "science_mode": science_mode,
        "tsundere_intensity": tsundere,
        "retrieved_context": retrieved,
        "worldline_focus": worldline_focus,
        "pending_utterance_fragment": _clean_utf8_text(pending),
        "pending_user_goal": _clean_utf8_text(pending_user_goal),
        "tool_round": int(state.get("tool_round", 0)),
        "toolset_unlocks": dict(state.get("toolset_unlocks") or {}),
        "evidence_pack": list(state.get("evidence_pack") or []),
        "last_external_tools": list(state.get("last_external_tools") or []),
        "memory_guard_checked": int(state.get("memory_guard_checked", 0) or 0),
        "memory_guard_blocked": int(state.get("memory_guard_blocked", 0) or 0),
        "event_override": {},
    }


def build_implicit_idle_state_update(
    state: ThreadState | dict[str, Any] | None,
    *,
    idle_minutes: int,
    note: str = "",
    created_at: int | None = None,
) -> dict[str, Any]:
    seeded: ThreadState = dict(state or {})
    try:
        idle_window = max(1, min(24 * 60, int(idle_minutes)))
    except Exception:
        idle_window = 1
    event_text = str(note or "").strip() or f"已经安静地过去了 {idle_window} 分钟，没有新的用户消息。"
    seeded["event_override"] = {
        "kind": "time_idle",
        "source": "time",
        "text": event_text,
        "effective_text": event_text,
        "semantic_goal": "time passed without new user input",
        "response_style_hint": "companion",
        "event_frame": f"和对方之间安静地过去了 {idle_window} 分钟，现在轮到她决定是否主动开口。",
        "tags": ["time_idle", "ambient", "behavior_layer", "implicit_idle"],
        "idle_minutes": idle_window,
        "created_at": int(created_at or _now_ts()),
    }
    return _node_prepare_turn(seeded)


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
    pending_fragment = str(state.get("pending_utterance_fragment") or "").strip()
    pending_user_goal = str(state.get("pending_user_goal") or "").strip()
    continuation_mode = is_continuation_request(user_text)
    continuation_seed = _continuation_seed_text(
        pending_user_goal=pending_user_goal,
        pending_fragment=pending_fragment,
    )
    has_pending_continuation = continuation_mode and bool(continuation_seed)
    prompt = _build_task_prompt(state, user_text, store)
    history = _window_messages(msgs, int(CONTEXT_KEEP_LAST_MESSAGES))
    recent_assistant_texts = _recent_ai_texts(msgs, limit=4)
    call_msgs: list[BaseMessage] = [_sanitize_message(SystemMessage(content=prompt))]
    if has_pending_continuation:
        call_msgs.extend(_sanitize_message(m) for m in history[-4:])
        continuation_lines = [
            "这是一次续说，不是新回答。",
            "直接顺着刚才未完成的内容往下说，不要先解释你在续哪一段，也不要重复用户的指令。",
        ]
        if pending_fragment:
            continuation_lines.append(f"未完成片段：{pending_fragment[:240]}")
        if pending_user_goal:
            continuation_lines.append(f"原始任务焦点：{_canonicalize_pending_goal_text(pending_user_goal)[:220]}")
        continuation_lines.append(f"现在就从这里接着往下说：{continuation_seed[:240]}")
        call_msgs.append(_sanitize_message(HumanMessage(content="\n".join(continuation_lines))))
    else:
        call_msgs.extend(_sanitize_message(m) for m in history)

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
    current_event = state.get("current_event") if isinstance(state.get("current_event"), dict) else {}
    current_event_kind = str(current_event.get("kind") or "user_utterance").strip()
    light_free_dialog = _is_light_free_dialog_turn(
        user_text=user_text,
        response_style_hint=response_style_hint,
        science_mode=bool(state.get("science_mode", False)),
        continuation_mode=has_pending_continuation,
        current_event_kind=current_event_kind,
    )
    if has_pending_continuation:
        tools = []
        if _needs_structured_answer(pending_user_goal or continuation_seed, ""):
            free_dialog = False
        else:
            free_dialog = True
        light_free_dialog = False
    generation_profile = _generation_profile(
        response_style_hint=response_style_hint,
        science_mode=bool(state.get("science_mode", False)),
        continuation_mode=has_pending_continuation,
        user_text=user_text,
        runtime_mode=RUNTIME_MODE,
        turn_index=len(msgs),
        recent_assistant_texts=recent_assistant_texts,
        current_event=state.get("current_event") if isinstance(state.get("current_event"), dict) else {},
        emotion_state=state.get("emotion_state") if isinstance(state.get("emotion_state"), dict) else {},
        bond_state=state.get("bond_state") if isinstance(state.get("bond_state"), dict) else {},
        allostasis_state=state.get("allostasis_state") if isinstance(state.get("allostasis_state"), dict) else {},
        counterpart_assessment=state.get("counterpart_assessment") if isinstance(state.get("counterpart_assessment"), dict) else {},
        behavior_policy=state.get("behavior_policy") if isinstance(state.get("behavior_policy"), dict) else {},
    )
    generation_runtime_mode = str(generation_profile.pop("runtime_mode", RUNTIME_MODE) or RUNTIME_MODE)
    generation_repetition_pressure = float(generation_profile.pop("repetition_pressure", 0.0) or 0.0)
    generation_recent_reply_max_similarity = float(generation_profile.pop("recent_reply_max_similarity", 0.0) or 0.0)
    generation_recent_reply_avg_similarity = float(generation_profile.pop("recent_reply_avg_similarity", 0.0) or 0.0)
    generation_recent_reply_opener_repeat_ratio = float(generation_profile.pop("recent_reply_opener_repeat_ratio", 0.0) or 0.0)
    generation_recent_reply_sample_size = int(generation_profile.pop("recent_reply_sample_size", 0) or 0)
    chosen_generation_profile: dict[str, Any] = {}
    for key in ("temperature", "top_p", "frequency_penalty", "presence_penalty"):
        value = generation_profile.get(key)
        if value is None:
            continue
        if bool(EVAL_MODE) and key == "temperature":
            # Keep eval generation temperature pinned by the shared eval env for repeatability.
            continue
        chosen_generation_profile[key] = float(value)
    max_tokens = generation_profile.get("max_tokens")
    if max_tokens is not None:
        chosen_generation_profile["max_tokens"] = int(max_tokens)
    llm = _model(**chosen_generation_profile)
    llm_tools = llm if free_dialog else (llm.bind_tools(tools) if tools else llm)
    ai = _invoke_model_with_retries(llm_tools, call_msgs)
    if not isinstance(ai, AIMessage):
        ai = AIMessage(content=str(getattr(ai, "content", "") or ""))

    tool_calls = list(getattr(ai, "tool_calls", None) or [])
    if tool_calls:
        return {"messages": [ai]}

    draft_text = _sanitize_final_answer(str(ai.content or ""), user_text)
    aligned = draft_text
    draft_risk, draft_flags = _ooc_risk(draft_text)
    draft_gap, draft_gap_flags = _persona_gap(draft_text, state)
    draft_dialogue_issues = _dialogue_surface_issues(
        user_text,
        draft_text,
        response_style_hint=response_style_hint,
        science_mode=bool(state.get("science_mode", False)),
    )
    alignment_applied = False
    alignment_reasons: list[str] = []
    light_dialog_rewrite_applied = False
    light_dialog_rewrite_notes: list[str] = []
    natural_dialog_rewrite_applied = False
    natural_dialog_rewrite_notes: list[str] = []
    light_dialog_draft_penalty = 0.0
    light_dialog_final_penalty = 0.0
    light_dialog_draft_pref_score = 0.0
    light_dialog_final_pref_score = 0.0
    response_style_hint = str(state.get("response_style_hint") or "natural").strip() or "natural"
    light_dialog_profile = (
        _daily_surface_profile(user_text, science_mode=bool(state.get("science_mode", False)))
        if light_free_dialog
        else {}
    )

    evidence_pack = list(state.get("evidence_pack") or [])
    if light_free_dialog:
        draft_pref = _daily_surface_alignment_metrics(draft_text, profile=light_dialog_profile)
        light_dialog_draft_pref_score = float(draft_pref.get("score") or 0.0)
        light_dialog_rewrite_notes = _light_dialog_rewrite_notes(
            user_text,
            draft_text,
            response_style_hint=response_style_hint,
            science_mode=bool(state.get("science_mode", False)),
        )
        light_dialog_draft_penalty = _light_dialog_surface_penalty(
            user_text,
            draft_text,
            response_style_hint=response_style_hint,
            science_mode=bool(state.get("science_mode", False)),
        )
        light_dialog_final_penalty = light_dialog_draft_penalty
        needs_alt_candidate = bool(light_dialog_rewrite_notes) or bool(draft_pref.get("used"))
        if draft_pref.get("used"):
            chosen_support = float(draft_pref.get("chosen_support") or 0.0)
            rejected_pull = float(draft_pref.get("rejected_pull") or 0.0)
            if light_dialog_draft_pref_score < 0.10 or chosen_support <= rejected_pull + 0.06:
                needs_alt_candidate = True
                if not light_dialog_rewrite_notes:
                    light_dialog_rewrite_notes = ["这版还不够像熟人之间顺手接住的轻日常，收得更自然一点。"]
        if needs_alt_candidate:
            rewritten = _rewrite_light_dialog_answer(
                prompt=prompt,
                user_text=user_text,
                draft_text=draft_text,
                rewrite_notes=light_dialog_rewrite_notes,
                focus_text=str(light_dialog_profile.get("focus") or ""),
                preferred_examples=[
                    str(item).strip()
                    for item in (light_dialog_profile.get("chosen_examples") or [])
                    if str(item or "").strip()
                ],
                rejected_examples=[
                    str(item).strip()
                    for item in (light_dialog_profile.get("rejected_examples") or [])
                    if str(item or "").strip()
                ],
            )
            if rewritten:
                rewritten_pref = _daily_surface_alignment_metrics(rewritten, profile=light_dialog_profile)
                rewritten_pref_score = float(rewritten_pref.get("score") or 0.0)
                rewritten_penalty = _light_dialog_surface_penalty(
                    user_text,
                    rewritten,
                    response_style_hint=response_style_hint,
                    science_mode=bool(state.get("science_mode", False)),
                )
                light_dialog_final_penalty = rewritten_penalty
                light_dialog_final_pref_score = rewritten_pref_score
                draft_total = light_dialog_draft_pref_score - light_dialog_draft_penalty
                rewritten_total = rewritten_pref_score - rewritten_penalty
                strong_case_match = float(light_dialog_profile.get("score") or 0.0) >= 0.95
                low_pref_case = light_dialog_draft_pref_score < 0.16
                if rewritten_total > draft_total + 0.04 or (
                    rewritten_total >= draft_total
                    and rewritten_penalty <= light_dialog_draft_penalty
                    and _norm_text(rewritten) != _norm_text(draft_text)
                ) or (
                    strong_case_match
                    and low_pref_case
                    and rewritten_total >= draft_total - 0.02
                    and rewritten_penalty <= light_dialog_draft_penalty + 0.05
                    and _norm_text(rewritten) != _norm_text(draft_text)
                ):
                    aligned = rewritten
                    alignment_applied = True
                    light_dialog_rewrite_applied = True
                    if light_dialog_rewrite_notes:
                        alignment_reasons.extend(light_dialog_rewrite_notes)
                    else:
                        alignment_reasons.append(
                            "daily_surface_rewrite:" + str(light_dialog_profile.get("case_name") or "matched_case")
                        )
                else:
                    light_dialog_final_penalty = light_dialog_draft_penalty
                    light_dialog_final_pref_score = light_dialog_draft_pref_score
            else:
                light_dialog_final_pref_score = light_dialog_draft_pref_score
        aligned = _sanitize_final_answer(aligned, user_text)
        if not light_dialog_final_pref_score:
            light_dialog_final_pref_score = light_dialog_draft_pref_score
    if (
        not light_free_dialog
        and not continuation_mode
        and not bool(_needs_structured_answer(user_text, draft_text))
        and response_style_hint in {"relationship", "companion", "casual", "natural", "selfhood", "structured"}
    ):
        rewrite_note_map = {
            "meta_self_explainer": "别把这句说成 AI、系统、程序、参数 之类的自我解释。",
            "defensive_meta": "别退成机制说明或自我辩护，就按人对人把这句说完。",
            "defensive_meta_tone": "不要用 设定 / 机制 / 数字存在 来解释自己，直接表态。",
            "counselor_tone": "别说成树洞或安抚热线，保持熟人对话，不要用 我听着呢 这类咨询腔。",
            "quoted_stagey_phrase": "别写得像舞台词或摆拍台词，收回自然口语。",
        }
        rewrite_issue_keys = {
            "meta_self_explainer",
            "defensive_meta",
            "defensive_meta_tone",
            "counselor_tone",
            "quoted_stagey_phrase",
        }
        targeted_flags = list(dict.fromkeys(list(draft_dialogue_issues) + list(draft_gap_flags)))
        natural_dialog_rewrite_notes = [
            rewrite_note_map[item]
            for item in targeted_flags
            if item in rewrite_issue_keys
        ]
        if natural_dialog_rewrite_notes:
            rewritten = _rewrite_natural_dialog_answer(
                prompt=prompt,
                user_text=user_text,
                draft_text=aligned,
                rewrite_notes=natural_dialog_rewrite_notes,
                response_style_hint=response_style_hint,
                science_mode=bool(state.get("science_mode", False)),
            )
            if rewritten:
                rewritten_gap, rewritten_gap_flags = _persona_gap(rewritten, state)
                rewritten_issues = _dialogue_surface_issues(
                    user_text,
                    rewritten,
                    response_style_hint=response_style_hint,
                    science_mode=bool(state.get("science_mode", False)),
                )
                targeted_issue_set = set(rewrite_issue_keys)
                draft_issue_pressure = sum(1 for item in targeted_flags if item in targeted_issue_set)
                rewritten_pressure = sum(1 for item in list(rewritten_issues) + list(rewritten_gap_flags) if item in targeted_issue_set)
                if (
                    rewritten_pressure < draft_issue_pressure
                    or rewritten_gap + 0.05 < draft_gap
                ) and _norm_text(rewritten) != _norm_text(aligned):
                    aligned = rewritten
                    alignment_applied = True
                    natural_dialog_rewrite_applied = True
                    alignment_reasons.extend(natural_dialog_rewrite_notes)
    pre_final_issues = _dialogue_surface_issues(
        user_text,
        aligned,
        response_style_hint=response_style_hint,
        science_mode=bool(state.get("science_mode", False)),
    )
    if (
        "meta_self_explainer" in pre_final_issues
        and response_style_hint in {"relationship", "companion", "casual", "natural", "selfhood", "structured"}
        and not bool(_needs_structured_answer(user_text, aligned))
    ):
        rewritten = _rewrite_natural_dialog_answer(
            prompt=prompt,
            user_text=user_text,
            draft_text=aligned,
            rewrite_notes=["不要把自己说成服务器、系统、程序、数据或机制，直接按人对人把这句话说完。"],
            response_style_hint=response_style_hint,
            science_mode=bool(state.get("science_mode", False)),
        )
        if rewritten:
            rewritten_issues = _dialogue_surface_issues(
                user_text,
                rewritten,
                response_style_hint=response_style_hint,
                science_mode=bool(state.get("science_mode", False)),
            )
            if "meta_self_explainer" not in rewritten_issues and _norm_text(rewritten) != _norm_text(aligned):
                aligned = rewritten
                alignment_applied = True
                alignment_reasons.append("meta_self_explainer_cleanup")
    aligned = _ensure_response_structure(aligned, user_text)
    claims = [] if bool(ABLATE_CLAIM_ATTRIBUTION) else build_claim_attribution(aligned, evidence_pack)
    ext_tools = set(state.get("last_external_tools") or [])
    if ext_tools and not claims and not bool(ABLATE_CLAIM_ATTRIBUTION):
        aligned = aligned.strip() + "\n\n(外部信息未形成可追溯证据链，以上结论按暂定处理。)"
        aligned = _sanitize_final_answer(aligned, user_text)
        aligned = _ensure_response_structure(aligned, user_text)
        claims = [] if bool(ABLATE_CLAIM_ATTRIBUTION) else build_claim_attribution(aligned, evidence_pack)

    risk, flags = _ooc_risk(aligned)
    gap, gap_flags = _persona_gap(aligned, state)
    dialogue_issues = _dialogue_surface_issues(
        user_text,
        aligned,
        response_style_hint=response_style_hint,
        science_mode=bool(state.get("science_mode", False)),
    )
    canon = _canon_guard(aligned, store)
    canon_risk = min(1.0, risk + (0.3 if not bool(canon.get("ok")) else 0.0))
    final_msg = AIMessage(content=aligned)
    return {
        "messages": [final_msg],
        "ooc_detector": {
            "draft_risk": draft_risk,
            "draft_gap": draft_gap,
            "draft_flags": draft_flags,
            "draft_gap_flags": draft_gap_flags,
            "draft_dialogue_issues": draft_dialogue_issues,
            "risk": risk,
            "flags": flags,
            "gap": gap,
            "gap_flags": gap_flags,
            "dialogue_issues": dialogue_issues,
            "threshold": float(OOC_RISK_THRESHOLD),
            "persona_gap_threshold": float(PERSONA_GAP_THRESHOLD),
            "alignment_applied": alignment_applied,
            "alignment_reasons": list(dict.fromkeys(alignment_reasons)),
            "response_strategy": "single_pass_final_diagnostics",
            "light_dialog_rewrite_applied": light_dialog_rewrite_applied,
            "light_dialog_rewrite_notes": light_dialog_rewrite_notes,
            "natural_dialog_rewrite_applied": natural_dialog_rewrite_applied,
            "natural_dialog_rewrite_notes": natural_dialog_rewrite_notes,
            "light_dialog_draft_penalty": light_dialog_draft_penalty,
            "light_dialog_final_penalty": light_dialog_final_penalty,
            "light_dialog_case_name": str(light_dialog_profile.get("case_name") or ""),
            "light_dialog_case_match_score": float(light_dialog_profile.get("score") or 0.0),
            "light_dialog_draft_pref_score": light_dialog_draft_pref_score,
            "light_dialog_final_pref_score": light_dialog_final_pref_score,
            "ablation_persona_alignment": bool(ABLATE_PERSONA_ALIGNMENT),
            "ablation_worldline_memory": bool(ABLATE_WORLDLINE_MEMORY),
            "ablation_claim_attribution": bool(ABLATE_CLAIM_ATTRIBUTION),
            "ablation_light_dialog_shaping": bool(ABLATE_LIGHT_DIALOG_SHAPING),
            "generation_profile": {
                **chosen_generation_profile,
                "runtime_mode": generation_runtime_mode,
                "repetition_pressure": generation_repetition_pressure,
                "recent_reply_max_similarity": generation_recent_reply_max_similarity,
                "recent_reply_avg_similarity": generation_recent_reply_avg_similarity,
                "recent_reply_opener_repeat_ratio": generation_recent_reply_opener_repeat_ratio,
                "recent_reply_sample_size": generation_recent_reply_sample_size,
            },
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
    if _is_silent_behavior_event(current_event, behavior_action):
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

