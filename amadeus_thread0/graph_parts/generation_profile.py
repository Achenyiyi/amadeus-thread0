from __future__ import annotations

import hashlib
import json
import re
import uuid
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from ..config import EVAL_MODE, EXPERIENCE_SAMPLING_JITTER
from ..evolution_engine.motive import semantic_motive_vector
from .postprocess import (
    DAILY_SURFACE_DRIFT_MARKERS,
    MEMORY_RECALL_KEYWORDS,
    SCIENCE_KEYWORDS,
    _has_any_marker,
    _is_presence_reassurance_check,
    _is_idle_smalltalk_request,
    _is_nonrelational_science_stress,
    _is_nonrelational_support_request,
    _is_playful_memory_request,
    _is_soft_presence_checkin_request,
    _looks_like_light_smalltalk,
    _needs_structured_answer,
    _norm_for_compare,
    _normalize_log_tone,
    _response_style_hint,
    _soften_natural_answer,
    _wants_brief_presence,
    _wants_presence_reassurance,
    _wants_less_teacherly_reply,
    _wants_quick_judgment,
)

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

TOOL_OR_RESEARCH_KEYWORDS = {"工具", "检索", "搜索", "查询", "调用", "文档", *SCIENCE_KEYWORDS}
DAILY_SURFACE_PREFERENCE_CORPUS_PATH = Path(__file__).resolve().parents[2] / "evals" / "daily_surface_preference_corpus.jsonl"


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except Exception:
        number = float(default)
    return max(0.0, min(1.0, number))


def _stable_unit_interval(*parts: Any) -> float:
    raw = "||".join(str(part or "") for part in parts)
    if not raw:
        return 0.5
    digest = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _effective_relationship_weather(
    *,
    interaction_carryover: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
    behavior_action: dict[str, Any] | None = None,
) -> tuple[str, float]:
    carryover = dict(interaction_carryover or {})
    event = dict(current_event or {})
    action = dict(behavior_action or {})
    carryover_weather = str(carryover.get("relationship_weather") or "").strip().lower()
    event_weather = str(event.get("relationship_weather") or "").strip().lower()
    action_weather = str(action.get("relationship_weather") or "").strip().lower()
    weather = carryover_weather or event_weather or action_weather
    strength = max(
        _clamp01(carryover.get("strength"), 0.0),
        _clamp01(event.get("carryover_strength"), 0.0),
        0.24 if weather and action_weather else 0.0,
    )
    return weather, strength


def _looks_like_daily_surface_scene(text: str, *, science_mode: bool = False) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    if _looks_like_light_smalltalk(raw):
        return True
    if _is_soft_presence_checkin_request(raw) or _wants_presence_reassurance(raw):
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
    for score, row in best_items:
        chosen = _flatten_surface_example(str(row.get("chosen") or ""))
        rejected = _flatten_surface_example(str(row.get("rejected") or ""))
        if chosen and chosen not in seen_chosen:
            chosen_examples.append(chosen)
            seen_chosen.add(chosen)
        if rejected:
            rejected_candidates.append(
                (
                    score,
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
        return {
            "used": False,
            "case_name": "",
            "score": 0.0,
            "chosen_support": 0.0,
            "rejected_pull": 0.0,
            "brevity_penalty": 0.0,
            "length_ratio": 1.0,
        }

    chosen_scores: list[float] = []
    chosen_lengths: list[int] = []
    rejected_scores: list[float] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        chosen = str(row.get("chosen") or "").strip()
        rejected = str(row.get("rejected") or "").strip()
        if chosen:
            chosen_scores.append(_daily_surface_prompt_similarity(text, chosen))
            chosen_lengths.append(len(_norm_for_compare(chosen)))
        if rejected:
            rejected_scores.append(_daily_surface_prompt_similarity(text, rejected))
    chosen_scores.sort(reverse=True)
    rejected_scores.sort(reverse=True)
    chosen_support = sum(chosen_scores[:3]) / max(1, len(chosen_scores[:3]))
    rejected_pull = sum(rejected_scores[:3]) / max(1, len(rejected_scores[:3]))
    chosen_length_anchor = (
        sum(chosen_lengths[:3]) / max(1, len(chosen_lengths[:3]))
        if chosen_lengths
        else 0.0
    )
    compact_length = len(_norm_for_compare(text))
    length_ratio = compact_length / max(1.0, chosen_length_anchor) if chosen_length_anchor else 1.0
    brevity_penalty = 0.0
    if chosen_length_anchor >= 8 and compact_length > 0:
        if length_ratio < 0.42:
            brevity_penalty = min(0.34, (0.42 - length_ratio) / 0.42 * 0.34)
        elif length_ratio < 0.56 and chosen_support < 0.80:
            brevity_penalty = min(0.12, (0.56 - length_ratio) / 0.14 * 0.12)
    score = chosen_support - 0.82 * rejected_pull - brevity_penalty
    return {
        "used": True,
        "case_name": str(prof.get("case_name") or "").strip(),
        "score": round(score, 4),
        "chosen_support": round(chosen_support, 4),
        "rejected_pull": round(rejected_pull, 4),
        "brevity_penalty": round(brevity_penalty, 4),
        "length_ratio": round(length_ratio, 4),
    }


def _daily_surface_preference_lines(user_text: str, *, science_mode: bool = False) -> list[str]:
    profile = _daily_surface_profile(user_text, science_mode=science_mode)
    if not profile:
        return []

    top_focus = str(profile.get("focus") or "").strip()
    if not top_focus:
        return []
    focus_text = top_focus[:72].rstrip("。！？!?；;，, ")
    if not focus_text:
        return []
    return [f"这类轻场景常见的自然落点是：{focus_text}。"]


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
    world_model_state: dict[str, Any] | None = None,
    behavior_action: dict[str, Any] | None = None,
    interaction_carryover: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hint = str(response_style_hint or "").strip() or "natural"
    event = dict(current_event or {})
    emotion = dict(emotion_state or {})
    bond = dict(bond_state or {})
    allostasis = dict(allostasis_state or {})
    assessment = dict(counterpart_assessment or {})
    policy = dict(behavior_policy or {})
    world = dict(world_model_state or {})
    action = dict(behavior_action or {})
    carryover = dict(interaction_carryover or {})
    narrative = dict(semantic_narrative_profile or {})

    reply_bias = _clamp01(policy.get("reply_length_bias"), 0.5)
    warmth = _clamp01(policy.get("warmth"), 0.5)
    sharpness = _clamp01(policy.get("sharpness"), 0.5)
    approach = _clamp01(policy.get("approach_vs_withdraw"), 0.5)
    self_directedness = _clamp01(policy.get("self_directedness"), 0.25)
    trust = _clamp01(bond.get("trust"), 0.5)
    hurt = _clamp01(bond.get("hurt"), 0.0)
    cognitive_budget = _clamp01(allostasis.get("cognitive_budget"), 0.7)
    safety_need = _clamp01(allostasis.get("safety_need"), 0.2)
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    counterpart_stance = str(assessment.get("stance") or "").strip().lower()
    counterpart_scene = str(assessment.get("scene") or "").strip().lower()
    emotion_label = str(emotion.get("label") or "neutral").strip().lower()
    event_kind = str(event.get("kind") or "user_utterance").strip().lower()
    task_focus = str(action.get("task_focus") or "").strip().lower()
    interaction_mode = str(action.get("interaction_mode") or "").strip().lower()
    followup_intent = str(action.get("followup_intent") or "").strip().lower()
    attention_target = str(action.get("attention_target") or "").strip().lower()
    carryover_mode = str(carryover.get("carryover_mode") or "").strip().lower()
    carryover_strength = _clamp01(carryover.get("strength"), 0.0)
    narrative_presence = _clamp01(narrative.get("presence_carry"), 0.0)
    narrative_history = _clamp01(narrative.get("history_weight"), 0.0)
    narrative_agency = _clamp01(narrative.get("agency_drive"), 0.0)
    narrative_rhythm = _clamp01(narrative.get("rhythm_continuity"), 0.0)
    motive_vector = semantic_motive_vector(narrative)
    motive_self_rhythm = _clamp01(motive_vector.get("self_rhythm_pull"), 0.0)
    motive_continuity = _clamp01(motive_vector.get("continuity_pull"), 0.0)
    relationship_weather, relationship_weather_strength = _effective_relationship_weather(
        interaction_carryover=carryover,
        current_event=event,
        behavior_action=action,
    )
    self_activity_momentum = _clamp01(world.get("self_activity_momentum"), 0.0)
    light_smalltalk = (
        _looks_like_light_smalltalk(user_text)
        or _is_idle_smalltalk_request(user_text)
        or _is_playful_memory_request(user_text)
    )
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
    own_rhythm_load = max(
        self_activity_momentum,
        carryover_strength if carryover_mode in {"own_rhythm", "small_opening", "quiet_recontact"} else 0.0,
        0.84 * narrative_rhythm,
        0.74 * narrative_agency,
        0.92 * motive_self_rhythm,
    )
    background_window_load = max(
        carryover_strength if carryover_mode in {"shared_window", "task_window", "life_window"} else 0.0,
        self_activity_momentum if attention_target in {"shared_task"} else 0.0,
        0.72 * max(narrative_presence, narrative_history, motive_continuity),
    )
    focused_user_turn = (
        event_kind == "user_utterance"
        and task_focus == "high"
        and (
            interaction_mode in {"self_activity_reopen", "self_activity_hold", "scheduled_life_nudge", "science_partner"}
            or attention_target in {"own_task", "self_then_counterpart", "shared_task"}
            or own_rhythm_load >= 0.56
        )
    )
    semantic_own_rhythm_turn = (
        event_kind == "user_utterance"
        and not science_mode
        and interaction_mode in {"steady_reply", "companion_reply", "brief_presence", "self_activity_reopen"}
        and followup_intent in {"none", "soft"}
        and own_rhythm_load >= 0.56
        and self_directedness >= 0.46
    )
    background_window_turn = (
        event_kind == "user_utterance"
        and (
            carryover_mode in {"shared_window", "task_window"}
            or attention_target in {"shared_window", "shared_task"}
        )
        and background_window_load >= 0.24
    )
    life_window_turn = (
        event_kind == "user_utterance"
        and carryover_mode == "life_window"
        and background_window_load >= 0.22
    )
    relational_weather_turn = (
        event_kind == "user_utterance"
        and relationship_weather in {"guarded_residue", "warm_residue", "repair_residue"}
        and relationship_weather_strength >= 0.22
    )
    presence_reassurance_turn = (
        event_kind == "user_utterance"
        and (
            _wants_presence_reassurance(user_text)
            or _is_presence_reassurance_check(user_text)
            or _is_soft_presence_checkin_request(user_text)
        )
    )
    brief_presence_turn = event_kind == "user_utterance" and interaction_mode == "brief_presence"
    busy_scene_turn = event_kind == "user_utterance" and counterpart_scene == "busy_not_disrespectful"
    repair_scene_turn = event_kind == "user_utterance" and counterpart_scene == "repair_attempt"
    care_scene_turn = event_kind == "user_utterance" and counterpart_scene == "care_bid"
    friction_scene_turn = event_kind == "user_utterance" and counterpart_scene in {
        "friction",
        "relationship_degradation",
        "boundary_non_compliance",
    }
    low_followup_turn = event_kind == "user_utterance" and followup_intent == "none"
    default_sampling_candidate = (
        event_kind == "user_utterance"
        and not science_mode
        and hint not in {"structured", "selfhood"}
        and not continuation_mode
        and emotion_label not in {"hurt", "sad", "angry", "stress"}
        and safety_need <= 0.38
        and boundary_pressure <= 0.32
        and cognitive_budget >= 0.42
        and repetition_pressure < 0.18
        and not focused_user_turn
        and not semantic_own_rhythm_turn
        and not background_window_turn
        and not life_window_turn
        and not relational_weather_turn
        and not presence_reassurance_turn
        and not brief_presence_turn
        and not busy_scene_turn
        and not repair_scene_turn
        and not care_scene_turn
        and not friction_scene_turn
        and not low_followup_turn
        and not _wants_quick_judgment(user_text)
        and not _needs_structured_answer(user_text, "")
        and not deescalated_science
    )

    def _cap_tokens(current: int | None, cap: int) -> int:
        return int(cap) if current is None else int(min(current, int(cap)))

    exploratory = mode == "experience"
    if science_mode or hint == "structured":
        temperature = 0.16 + 0.08 * reply_bias
        top_p = 0.72 + 0.10 * cognitive_budget
        max_tokens = 280 if continuation_mode else 224
    elif hint == "selfhood":
        if exploratory:
            temperature = 0.32 + 0.14 * reply_bias + 0.05 * max(approach, trust)
            top_p = 0.84 + 0.03 * max(approach, trust)
        else:
            temperature = 0.20 + 0.07 * reply_bias
            top_p = 0.76 + 0.06 * max(approach, trust)
        max_tokens = 200 if exploratory else 148
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
    if presence_reassurance_turn:
        max_tokens = _cap_tokens(max_tokens, 96)
        temperature = min(temperature, 0.22)
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
    if hurt > 0.45 and trust < 0.48 and event_kind != "user_utterance":
        max_tokens = _cap_tokens(max_tokens, 160)
    if focused_user_turn:
        max_tokens = _cap_tokens(max_tokens, 168 if exploratory else 136)
        top_p = min(top_p, 0.80 if exploratory else 0.76)
        if own_rhythm_load >= 0.64 or attention_target in {"own_task", "self_then_counterpart"}:
            temperature = min(temperature, 0.26 if exploratory else 0.20)
    elif semantic_own_rhythm_turn:
        max_tokens = _cap_tokens(max_tokens, 156 if exploratory else 132)
        top_p = min(top_p, 0.80 if exploratory else 0.76)
        temperature = min(temperature, 0.26 if exploratory else 0.20)
    elif background_window_turn:
        max_tokens = _cap_tokens(max_tokens, 192 if exploratory else 164)
        top_p = min(top_p, 0.82 if exploratory else 0.78)
    elif life_window_turn:
        max_tokens = _cap_tokens(max_tokens, 208 if exploratory else 180)
        top_p = min(top_p, 0.84 if exploratory else 0.80)
    if relational_weather_turn:
        if relationship_weather == "guarded_residue":
            max_tokens = _cap_tokens(max_tokens, 152 if exploratory else 128)
            temperature = min(temperature, 0.24 if exploratory else 0.20)
            top_p = min(top_p, 0.80 if exploratory else 0.76)
        elif relationship_weather == "repair_residue":
            max_tokens = _cap_tokens(max_tokens, 164 if exploratory else 136)
            temperature = min(temperature, 0.26 if exploratory else 0.22)
            top_p = min(top_p, 0.80 if exploratory else 0.78)
        elif relationship_weather == "warm_residue":
            max_tokens = _cap_tokens(max_tokens, 184 if exploratory else 160)
            top_p = min(top_p, 0.82 if exploratory else 0.80)
    if brief_presence_turn:
        max_tokens = _cap_tokens(max_tokens, 112 if exploratory else 96)
        temperature = min(temperature, 0.24 if exploratory else 0.22)
        top_p = min(top_p, 0.80 if exploratory else 0.78)
    if busy_scene_turn:
        max_tokens = _cap_tokens(max_tokens, 168 if exploratory else 144)
        temperature = min(temperature, 0.26 if exploratory else 0.20)
        top_p = min(top_p, 0.82 if exploratory else 0.78)
    if repair_scene_turn:
        max_tokens = _cap_tokens(max_tokens, 156 if exploratory else 132)
        temperature = min(temperature, 0.26 if exploratory else 0.20)
        top_p = min(top_p, 0.80 if exploratory else 0.76)
    if care_scene_turn:
        max_tokens = _cap_tokens(max_tokens, 192 if exploratory else 164)
        temperature = min(temperature, 0.28 if exploratory else 0.22)
        top_p = min(top_p, 0.84 if exploratory else 0.80)
    if friction_scene_turn:
        max_tokens = _cap_tokens(max_tokens, 160 if exploratory else 132)
        temperature = min(temperature, 0.24 if exploratory else 0.18)
        top_p = min(top_p, 0.78 if exploratory else 0.74)
    if low_followup_turn and not science_mode:
        max_tokens = _cap_tokens(max_tokens, 160 if exploratory else 136)
        top_p = min(top_p, 0.80)

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
    if focused_user_turn:
        frequency_penalty += 0.05
        presence_penalty = max(0.0, presence_penalty - 0.02)
    elif semantic_own_rhythm_turn:
        frequency_penalty += 0.04
        presence_penalty = max(0.0, presence_penalty - 0.02)
    elif background_window_turn:
        frequency_penalty += 0.03
        presence_penalty = max(0.0, presence_penalty - 0.01)
    elif life_window_turn:
        frequency_penalty += 0.02
    if relational_weather_turn:
        if relationship_weather == "guarded_residue":
            frequency_penalty += 0.04
            presence_penalty = max(0.0, presence_penalty - 0.02)
        elif relationship_weather == "repair_residue":
            frequency_penalty += 0.02
        elif relationship_weather == "warm_residue":
            presence_penalty += 0.01
    if busy_scene_turn:
        frequency_penalty += 0.02
    if repair_scene_turn:
        frequency_penalty += 0.03
        presence_penalty = max(0.0, presence_penalty - 0.01)
    if care_scene_turn:
        presence_penalty += 0.01
    if friction_scene_turn:
        frequency_penalty += 0.04
        presence_penalty = max(0.0, presence_penalty - 0.02)
        if counterpart_stance in {"guarded", "watchful"}:
            frequency_penalty += 0.01
    if low_followup_turn:
        frequency_penalty += 0.03
        presence_penalty = max(0.0, presence_penalty - 0.02)

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

    if default_sampling_candidate:
        temperature_out = None
        top_p_out = None
        frequency_penalty_out = None
        presence_penalty_out = None
    else:
        temperature_out = round(max(0.12, min(0.52 if exploratory else 0.36, temperature)), 3)
        top_p_out = round(max(0.65, min(0.95 if exploratory else 0.92, top_p)), 3)
        frequency_penalty_out = round(max(0.0, min(0.65, frequency_penalty)), 3)
        presence_penalty_out = round(max(0.0, min(0.28 if exploratory else 0.22, presence_penalty)), 3)

    return {
        "temperature": temperature_out,
        "top_p": top_p_out,
        "max_tokens": None if max_tokens is None else int(max(80, min(360, max_tokens))),
        "frequency_penalty": frequency_penalty_out,
        "presence_penalty": presence_penalty_out,
        "runtime_mode": mode,
        "repetition_pressure": repetition_signature["pressure"],
        "recent_reply_max_similarity": repetition_signature["max_similarity"],
        "recent_reply_avg_similarity": repetition_signature["avg_similarity"],
        "recent_reply_opener_repeat_ratio": repetition_signature["opener_repeat_ratio"],
        "recent_reply_sample_size": repetition_signature["sample_size"],
    }
