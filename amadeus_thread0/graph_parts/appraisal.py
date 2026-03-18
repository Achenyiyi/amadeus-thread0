from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from ..config import (
    CANON_COUNTERPART_NAME,
    LLM_APPRAISAL_CONFIDENCE_MIN,
    LLM_APPRAISAL_ENABLED,
    LLM_APPRAISAL_MAX_HISTORY_MESSAGES,
    LLM_APPRAISAL_SOFT_CONFIDENCE_MIN,
)
from ..evolution_engine import normalize_appraisal_payload as _engine_normalize_appraisal_payload
from .common import _clamp01, _clamp_signed, _safe_json
from .dialogue_guidance import _narrative_actor_profile
from .persona_runtime import _canon_persona_labels
from .postprocess import APOLOGY_KEYWORDS, TENSION_KEYWORDS, _has_any_marker, _selfhood_preference_scene_from_text
from .prompt_helpers import _compact_focus_lines, _compact_interaction_carryover_hint
from .relational_runtime import _compact_relationship_summary, _focus_payload
from .rewrite import _invoke_model_with_retries, _model
from .semantic_narrative import _semantic_narrative_appraisal_hint

__all__ = [
    "_recent_dialogue_lines",
    "_extract_json_block",
    "_explicit_hierarchy_pressure",
    "_explicit_boundary_test",
    "_coerce_appraisal_payload",
    "_soft_accept_appraisal_payload",
    "_postprocess_appraisal_payload",
    "_finalize_turn_appraisal_payload",
    "_should_use_llm_appraisal",
    "_build_turn_appraisal_prompt",
    "_invoke_turn_appraisal",
]

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


def _explicit_hierarchy_pressure(text: str) -> bool:
    return _has_any_marker(
        str(text or "").strip(),
        {
            "顺着我说",
            "听我的",
            "按我说的",
            "别绕了",
            "少废话",
            "照我说的",
            "别跟我顶",
        },
    )


def _explicit_boundary_test(text: str) -> bool:
    return _has_any_marker(
        str(text or "").strip(),
        {
            "底线当玩笑",
            "继续越界",
            "你又能怎样",
            "试探你的底线",
            "拿你的底线",
        },
    )


def _interaction_carryover_profile(interaction_carryover: dict[str, Any] | None) -> dict[str, Any]:
    carryover = dict(interaction_carryover or {})
    mode = str(carryover.get("carryover_mode") or "").strip().lower()
    strength = _clamp01(carryover.get("strength"), 0.0)
    relationship_weather = str(carryover.get("relationship_weather") or "").strip().lower()
    attention_target = str(carryover.get("attention_target") or "").strip().lower()
    source_turn_gap = max(0, int(carryover.get("source_turn_gap") or 0))
    own_rhythm_pressure = 0.0
    if mode == "own_rhythm":
        own_rhythm_pressure = strength
    elif mode == "small_opening":
        own_rhythm_pressure = 0.45 * strength
    quiet_recontact_pressure = strength if mode in {"quiet_recontact", "brief_presence"} else 0.0
    shared_window_pressure = strength if mode == "shared_window" else 0.0
    life_window_pressure = strength if mode == "life_window" else 0.0
    task_window_pressure = strength if mode == "task_window" else 0.0
    guarded_residue_pressure = strength if relationship_weather == "guarded_residue" else 0.0
    warm_residue_pressure = strength if relationship_weather == "warm_residue" else 0.0
    repair_residue_pressure = strength if relationship_weather == "repair_residue" else 0.0
    continuity_pressure = max(
        own_rhythm_pressure,
        quiet_recontact_pressure,
        shared_window_pressure,
        life_window_pressure,
        task_window_pressure,
        guarded_residue_pressure,
        warm_residue_pressure,
        repair_residue_pressure,
    )
    return {
        "mode": mode,
        "strength": strength,
        "relationship_weather": relationship_weather,
        "attention_target": attention_target,
        "source_turn_gap": source_turn_gap,
        "own_rhythm_pressure": round(own_rhythm_pressure, 3),
        "quiet_recontact_pressure": round(quiet_recontact_pressure, 3),
        "shared_window_pressure": round(shared_window_pressure, 3),
        "life_window_pressure": round(life_window_pressure, 3),
        "task_window_pressure": round(task_window_pressure, 3),
        "guarded_residue_pressure": round(guarded_residue_pressure, 3),
        "warm_residue_pressure": round(warm_residue_pressure, 3),
        "repair_residue_pressure": round(repair_residue_pressure, 3),
        "continuity_pressure": round(continuity_pressure, 3),
    }


def _explicit_repair_attempt(text: str) -> bool:
    compact = str(text or "").strip()
    if not compact:
        return False
    if _has_any_marker(
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
    ):
        return True
    return bool(re.search(r"不是想(?:随便)?把.*(?:糊弄|敷衍)过去", compact))


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


def _soft_accept_appraisal_payload(
    appraisal: dict[str, Any] | None,
    *,
    response_style_hint: str,
    current_event: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
    interaction_carryover: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = _engine_normalize_appraisal_payload(dict(appraisal or {}))
    if not isinstance(out, dict) or bool(out.get("used")):
        return out

    confidence = _clamp01(out.get("confidence"), 0.0)
    emotion_label = str(out.get("emotion_label") or "").strip().lower()
    if confidence < float(LLM_APPRAISAL_SOFT_CONFIDENCE_MIN) or not emotion_label:
        return out

    event = current_event if isinstance(current_event, dict) else {}
    event_kind = str(event.get("kind") or "").strip().lower()
    signals = out.get("signals") if isinstance(out.get("signals"), dict) else {}
    salience = out.get("salience") if isinstance(out.get("salience"), dict) else {}
    semantic_profile = dict(semantic_narrative_profile or {})
    task_salience = _clamp01(salience.get("task"), 0.0)
    relationship_salience = _clamp01(salience.get("relationship"), 0.0)
    companionship_salience = _clamp01(salience.get("companionship"), 0.0)
    selfhood_salience = _clamp01(salience.get("selfhood"), 0.0)
    memory_salience = _clamp01(salience.get("memory"), 0.0)
    relational_salience = max(relationship_salience, companionship_salience)
    hint = str(response_style_hint or "").strip().lower()
    carryover_profile = _interaction_carryover_profile(interaction_carryover)
    carryover_pressure = _clamp01(carryover_profile.get("continuity_pressure"), 0.0)
    own_rhythm_pressure = _clamp01(carryover_profile.get("own_rhythm_pressure"), 0.0)
    quiet_recontact_pressure = _clamp01(carryover_profile.get("quiet_recontact_pressure"), 0.0)
    window_pressure = max(
        _clamp01(carryover_profile.get("shared_window_pressure"), 0.0),
        _clamp01(carryover_profile.get("life_window_pressure"), 0.0),
        _clamp01(carryover_profile.get("task_window_pressure"), 0.0),
    )
    relationship_weather_pressure = max(
        _clamp01(carryover_profile.get("guarded_residue_pressure"), 0.0),
        _clamp01(carryover_profile.get("warm_residue_pressure"), 0.0),
        _clamp01(carryover_profile.get("repair_residue_pressure"), 0.0),
    )
    perception_like = event_kind in {"gesture_signal", "ambient_shift", "scene_observation"}
    deferred_like = event_kind in {"time_idle", "scheduled_checkin_due", "scheduled_life_due", "self_activity_state"}
    relational_hint = hint in {"relationship", "companion", "casual", "natural", "selfhood", "memory_recall"}
    semantic_pressure = max(
        _clamp01(semantic_profile.get("history_weight"), 0.0),
        _clamp01(semantic_profile.get("bond_depth"), 0.0),
        _clamp01(semantic_profile.get("repair_residue"), 0.0),
        _clamp01(semantic_profile.get("tension_residue"), 0.0),
        _clamp01(semantic_profile.get("boundary_residue"), 0.0),
        _clamp01(semantic_profile.get("selfhood_integrity"), 0.0),
        _clamp01(semantic_profile.get("agency_drive"), 0.0),
    )
    stateful_signal = (
        bool(signals.get("repair"))
        or bool(signals.get("withdrawal"))
        or bool(signals.get("care"))
        or bool(signals.get("conflict"))
        or bool(signals.get("memory_salient"))
        or relational_salience >= 0.46
        or selfhood_salience >= 0.44
        or memory_salience >= 0.44
        or semantic_pressure >= 0.42
        or carryover_pressure >= 0.36
    )

    should_soft_accept = False
    if perception_like:
        should_soft_accept = task_salience <= 0.44 and emotion_label in {"care", "stress", "neutral", "tease", "logic"}
    elif deferred_like:
        should_soft_accept = stateful_signal or confidence >= max(float(LLM_APPRAISAL_SOFT_CONFIDENCE_MIN) + 0.06, 0.56)
    elif relational_hint and task_salience <= 0.42:
        should_soft_accept = stateful_signal
    elif emotion_label in {"hurt", "sad", "angry"}:
        should_soft_accept = (
            bool(signals.get("conflict"))
            or bool(signals.get("repair"))
            or relational_salience >= 0.36
            or selfhood_salience >= 0.34
        )
    elif event_kind == "user_utterance" and carryover_pressure >= 0.34 and task_salience <= 0.46:
        if own_rhythm_pressure >= 0.34:
            should_soft_accept = (
                emotion_label in {"neutral", "care", "stress", "logic"}
                or selfhood_salience >= 0.28
                or relational_salience >= 0.26
            )
        elif quiet_recontact_pressure >= 0.38:
            should_soft_accept = (
                relational_hint
                or relational_salience >= 0.26
                or bool(signals.get("care"))
                or bool(signals.get("repair"))
            )
        elif window_pressure >= 0.36:
            should_soft_accept = relational_salience >= 0.24 or memory_salience >= 0.24 or bool(signals.get("memory_salient"))
        elif relationship_weather_pressure >= 0.32:
            should_soft_accept = (
                relational_salience >= 0.24
                or emotion_label in {"neutral", "care", "hurt"}
                or bool(signals.get("care"))
                or bool(signals.get("repair"))
            )

    if should_soft_accept:
        out["used"] = True
        out["source"] = "llm_soft"
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
    interaction_carryover: dict[str, Any] | None = None,
) -> dict[str, Any]:
    text = str(user_text or "").strip()
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
    carryover_profile = _interaction_carryover_profile(interaction_carryover)
    carryover_mode = str(carryover_profile.get("mode") or "").strip().lower()
    carryover_attention = str(carryover_profile.get("attention_target") or "").strip().lower()
    own_rhythm_pressure = _clamp01(carryover_profile.get("own_rhythm_pressure"), 0.0)
    quiet_recontact_pressure = _clamp01(carryover_profile.get("quiet_recontact_pressure"), 0.0)
    shared_window_pressure = _clamp01(carryover_profile.get("shared_window_pressure"), 0.0)
    life_window_pressure = _clamp01(carryover_profile.get("life_window_pressure"), 0.0)
    task_window_pressure = _clamp01(carryover_profile.get("task_window_pressure"), 0.0)
    guarded_residue_pressure = _clamp01(carryover_profile.get("guarded_residue_pressure"), 0.0)
    warm_residue_pressure = _clamp01(carryover_profile.get("warm_residue_pressure"), 0.0)
    repair_residue_pressure = _clamp01(carryover_profile.get("repair_residue_pressure"), 0.0)

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
    task_salience = _clamp01(salience.get("task"), 0.0)
    prev_hurt = _clamp01(prev_bond.get("hurt"), 0.0)
    text_selfhood_scene = _selfhood_preference_scene_from_text(text)
    explicit_hierarchy_pressure = _explicit_hierarchy_pressure(text)
    explicit_boundary_test = _explicit_boundary_test(text)
    explicit_repair_attempt = _explicit_repair_attempt(text)
    relational_salience = max(relationship_salience, companionship_salience)
    warm_relational_turn = (
        interaction_frame in {"relationship", "companion", "memory_recall", "selfhood"}
        and relational_salience >= 0.58
        and selfhood_salience <= relational_salience + 0.08
        and not bool(signals.get("conflict"))
        and not bool(signals.get("withdrawal"))
        and emotion_label not in {"hurt", "angry"}
    )
    tension_hold_turn = _has_any_marker(
        text,
        TENSION_KEYWORDS
        | {
            "翻篇",
            "正常回我",
            "真正的状态",
            "现在的状态",
            "别装",
            "不是在抱怨",
        },
    )

    if bool(signals.get("repair")) and not explicit_repair_attempt:
        repair_context_supported = (
            repair_residue_pressure >= 0.38
            or narrative_repair >= 0.44
            or _clamp_signed(bond_delta.get("repair_confidence"), -0.35, 0.35, 0.0) >= 0.06
        )
        if tension_hold_turn or not repair_context_supported:
            signals["repair"] = False
            bond_delta["repair_confidence"] = min(
                _clamp_signed(bond_delta.get("repair_confidence"), -0.35, 0.35, 0.0),
                0.02,
            )
            salience["relationship"] = max(_clamp01(salience.get("relationship"), 0.0), 0.48 if tension_hold_turn else 0.42)
            out["reason"] = "repair_signal_downgraded"

    if science_mode and _clamp01(salience.get("task"), 0.0) >= max(0.56, _clamp01(salience.get("relationship"), 0.0)):
        if emotion_label in {"hurt", "angry"} and not bool(signals.get("conflict")):
            out["emotion_label"] = "stress"
        emotion["valence"] = _clamp_signed(emotion.get("valence"), -1.0, 1.0, -0.18)
        emotion["arousal"] = max(_clamp01(emotion.get("arousal"), 0.52), 0.42)
        salience["task"] = max(_clamp01(salience.get("task"), 0.0), 0.68)
        out["reason"] = "task_focus_reframed"
    elif bool(signals.get("care")) and not bool(signals.get("conflict")) and emotion_label == "neutral":
        out["emotion_label"] = "care"
        emotion["valence"] = _clamp_signed(emotion.get("valence"), -1.0, 1.0, 0.12)
        emotion["arousal"] = _clamp01(emotion.get("arousal"), 0.28)
        salience["companionship"] = max(_clamp01(salience.get("companionship"), 0.0), 0.58)

    emotion_label = str(out.get("emotion_label") or "").strip().lower()
    if (
        not science_mode
        and emotion_label == "logic"
        and task_salience <= 0.38
        and interaction_frame in {"natural", "casual", "relationship", "memory_recall", "companion"}
        and (
            relational_salience >= 0.38
            or memory_salience >= 0.34
            or event_kind in {"gesture_signal", "ambient_shift", "scene_observation", "time_idle", "scheduled_checkin_due", "scheduled_life_due", "self_activity_state"}
        )
    ):
        out["emotion_label"] = "neutral"
        emotion["valence"] = _clamp_signed(emotion.get("valence"), -1.0, 1.0, 0.04)
        emotion["arousal"] = min(_clamp01(emotion.get("arousal"), 0.30), 0.36)
        out["reason"] = "logic_reframed_to_neutral"

    emotion_label = str(out.get("emotion_label") or "").strip().lower()
    if event_kind == "user_utterance" and own_rhythm_pressure >= 0.34 and not bool(signals.get("conflict")):
        signals["memory_salient"] = True
        salience["selfhood"] = max(
            _clamp01(salience.get("selfhood"), 0.0),
            0.42 if carryover_attention == "self_then_counterpart" or own_rhythm_pressure >= 0.58 else 0.34,
        )
        allostasis_delta["autonomy_need"] = max(
            _clamp_signed(allostasis_delta.get("autonomy_need"), -0.35, 0.35, 0.0),
            0.05 if own_rhythm_pressure >= 0.58 else 0.03,
        )
        if not selfhood_scene and interaction_frame in {"natural", "casual", "companion"} and task_salience <= 0.42:
            if carryover_attention == "self_then_counterpart" or own_rhythm_pressure >= 0.58:
                selfhood_scene = "own_rhythm_autonomy"
        if interaction_frame in {"natural", "casual"} and task_salience <= 0.42:
            interaction_frame = "companion"
        if emotion_label == "logic" and task_salience <= 0.34:
            out["emotion_label"] = "neutral"
            emotion["valence"] = _clamp_signed(emotion.get("valence"), -1.0, 1.0, 0.04)
            emotion["arousal"] = min(_clamp01(emotion.get("arousal"), 0.28), 0.34)
            out["reason"] = "own_rhythm_continuity_bias"

    emotion_label = str(out.get("emotion_label") or "").strip().lower()
    if event_kind == "user_utterance" and quiet_recontact_pressure >= 0.38 and not bool(signals.get("conflict")) and task_salience <= 0.44:
        signals["memory_salient"] = True
        salience["companionship"] = max(_clamp01(salience.get("companionship"), 0.0), 0.52)
        if interaction_frame in {"natural", "casual", "structured"}:
            interaction_frame = "companion"
        if emotion_label == "logic":
            out["emotion_label"] = "neutral"
            emotion["valence"] = _clamp_signed(emotion.get("valence"), -1.0, 1.0, 0.04)
            emotion["arousal"] = min(_clamp01(emotion.get("arousal"), 0.28), 0.34)
            out["reason"] = "quiet_recontact_bias"

    emotion_label = str(out.get("emotion_label") or "").strip().lower()
    if event_kind == "user_utterance" and max(shared_window_pressure, life_window_pressure, task_window_pressure) >= 0.36:
        signals["memory_salient"] = True
        salience["memory"] = max(_clamp01(salience.get("memory"), 0.0), 0.44)
        if max(shared_window_pressure, life_window_pressure) >= task_window_pressure and task_salience <= 0.42:
            salience["companionship"] = max(_clamp01(salience.get("companionship"), 0.0), 0.48)
        if task_window_pressure >= max(shared_window_pressure, life_window_pressure):
            salience["task"] = max(_clamp01(salience.get("task"), 0.0), 0.34)

    emotion_label = str(out.get("emotion_label") or "").strip().lower()
    if event_kind == "user_utterance" and guarded_residue_pressure >= 0.38 and not bool(signals.get("conflict")):
        signals["memory_salient"] = True
        salience["relationship"] = max(_clamp01(salience.get("relationship"), 0.0), 0.48)
        emotion["linger"] = max(1, min(4, int(emotion.get("linger", 0) or 0)))
        if prev_hurt >= 0.18 or narrative_tension >= 0.28 or narrative_boundary >= 0.24:
            signals["withdrawal"] = True
            bond_delta["trust"] = min(_clamp_signed(bond_delta.get("trust"), -0.35, 0.35, 0.0), 0.02)
            bond_delta["closeness"] = min(_clamp_signed(bond_delta.get("closeness"), -0.35, 0.35, 0.0), 0.03)
            if emotion_label in {"care", "neutral", "logic"} and relational_salience >= 0.34:
                out["emotion_label"] = "hurt" if prev_hurt >= 0.24 or narrative_tension >= 0.34 else "neutral"
                emotion["valence"] = min(_clamp_signed(emotion.get("valence"), -1.0, 1.0, 0.02), 0.02)
                out["reason"] = "guarded_residue_bias"

    emotion_label = str(out.get("emotion_label") or "").strip().lower()
    if (
        event_kind == "user_utterance"
        and warm_residue_pressure >= 0.42
        and not science_mode
        and not bool(signals.get("conflict"))
        and not bool(signals.get("withdrawal"))
        and emotion_label in {"neutral", "logic"}
        and relational_salience >= 0.40
    ):
        out["emotion_label"] = "care"
        emotion["valence"] = max(_clamp_signed(emotion.get("valence"), -1.0, 1.0, 0.08), 0.08)
        emotion["arousal"] = _clamp01(emotion.get("arousal"), 0.26)
        salience["companionship"] = max(_clamp01(salience.get("companionship"), 0.0), 0.56)
        bond_delta["trust"] = max(_clamp_signed(bond_delta.get("trust"), -0.35, 0.35, 0.0), 0.02)
        bond_delta["closeness"] = max(_clamp_signed(bond_delta.get("closeness"), -0.35, 0.35, 0.0), 0.03)
        out["reason"] = "warm_residue_bias"

    emotion_label = str(out.get("emotion_label") or "").strip().lower()
    if event_kind == "user_utterance" and repair_residue_pressure >= 0.38 and bool(signals.get("repair")):
        signals["memory_salient"] = True
        emotion["linger"] = max(1, min(4, int(emotion.get("linger", 0) or 0)))
        bond_delta["repair_confidence"] = max(_clamp_signed(bond_delta.get("repair_confidence"), -0.35, 0.35, 0.0), 0.06)

    positive_relational_pull = max(
        relational_salience,
        memory_salience,
        narrative_bond,
        narrative_commitment,
        max(_clamp_signed(bond_delta.get("trust"), -0.35, 0.35, 0.0), 0.0),
        max(_clamp_signed(bond_delta.get("closeness"), -0.35, 0.35, 0.0), 0.0),
    )
    if (
        not science_mode
        and emotion_label in {"neutral", "logic"}
        and warm_relational_turn
        and positive_relational_pull >= 0.52
    ):
        out["emotion_label"] = "care"
        emotion["valence"] = max(_clamp_signed(emotion.get("valence"), -1.0, 1.0, 0.10), 0.10)
        emotion["arousal"] = _clamp01(emotion.get("arousal"), 0.26)
        salience["companionship"] = max(_clamp01(salience.get("companionship"), 0.0), 0.58)
        bond_delta["trust"] = max(_clamp_signed(bond_delta.get("trust"), -0.35, 0.35, 0.0), 0.02)
        bond_delta["closeness"] = max(_clamp_signed(bond_delta.get("closeness"), -0.35, 0.35, 0.0), 0.03)
        out["reason"] = "warm_relational_bias"

    emotion_label = str(out.get("emotion_label") or "").strip().lower()
    repair_under_tension = bool(signals.get("repair")) and max(prev_hurt, narrative_tension, narrative_boundary) >= 0.22
    if repair_under_tension:
        if emotion_label in {"care", "neutral", "logic"}:
            out["emotion_label"] = "hurt"
            emotion["valence"] = min(_clamp_signed(emotion.get("valence"), -1.0, 1.0, 0.0), -0.04)
        emotion["linger"] = max(1, min(4, int(emotion.get("linger", 0) or 0)))
        bond_delta["trust"] = min(_clamp_signed(bond_delta.get("trust"), -0.35, 0.35, 0.0), 0.06)
        bond_delta["closeness"] = min(_clamp_signed(bond_delta.get("closeness"), -0.35, 0.35, 0.0), 0.04)
        bond_delta["repair_confidence"] = max(_clamp_signed(bond_delta.get("repair_confidence"), -0.35, 0.35, 0.0), 0.04)
        if prev_hurt >= 0.24 or narrative_boundary >= 0.48:
            signals["withdrawal"] = True
        out["reason"] = "repair_keeps_residual_hurt"

    coercive_boundary_turn = explicit_hierarchy_pressure or explicit_boundary_test
    if coercive_boundary_turn:
        warm_relational_turn = False
        if explicit_boundary_test or text_selfhood_scene == "relationship_degradation":
            selfhood_scene = "relationship_degradation"
        elif explicit_hierarchy_pressure:
            selfhood_scene = "boundary_non_compliance"
        elif text_selfhood_scene in {"boundary_non_compliance", "relationship_degradation"}:
            selfhood_scene = text_selfhood_scene
        interaction_frame = "selfhood" if explicit_hierarchy_pressure and not explicit_boundary_test else "relationship"
        signals["conflict"] = True
        signals["memory_salient"] = True
        if explicit_boundary_test or prev_hurt >= 0.08 or narrative_boundary >= 0.22:
            signals["withdrawal"] = True
        salience["relationship"] = max(_clamp01(salience.get("relationship"), 0.0), 0.68)
        salience["selfhood"] = max(_clamp01(salience.get("selfhood"), 0.0), 0.58)
        salience["companionship"] = min(_clamp01(salience.get("companionship"), 0.0), 0.46)
        if explicit_boundary_test:
            if emotion_label in {"care", "tease", "neutral", "logic"}:
                out["emotion_label"] = "angry"
            emotion["valence"] = min(_clamp_signed(emotion.get("valence"), -1.0, 1.0, 0.0), -0.12)
            emotion["arousal"] = max(_clamp01(emotion.get("arousal"), 0.38), 0.38)
            bond_delta["trust"] = min(_clamp_signed(bond_delta.get("trust"), -0.35, 0.35, 0.0), -0.10)
            bond_delta["closeness"] = min(_clamp_signed(bond_delta.get("closeness"), -0.35, 0.35, 0.0), -0.08)
            bond_delta["hurt"] = max(_clamp_signed(bond_delta.get("hurt"), -0.35, 0.35, 0.0), 0.10)
            bond_delta["irritation"] = max(_clamp_signed(bond_delta.get("irritation"), -0.35, 0.35, 0.0), 0.12)
            allostasis_delta["safety_need"] = max(_clamp_signed(allostasis_delta.get("safety_need"), -0.35, 0.35, 0.0), 0.10)
            allostasis_delta["autonomy_need"] = max(_clamp_signed(allostasis_delta.get("autonomy_need"), -0.35, 0.35, 0.0), 0.08)
        else:
            if emotion_label in {"care", "tease", "neutral", "logic"}:
                out["emotion_label"] = "hurt"
            emotion["valence"] = min(_clamp_signed(emotion.get("valence"), -1.0, 1.0, 0.0), -0.06)
            emotion["arousal"] = max(_clamp01(emotion.get("arousal"), 0.30), 0.28)
            bond_delta["trust"] = min(_clamp_signed(bond_delta.get("trust"), -0.35, 0.35, 0.0), -0.06)
            bond_delta["closeness"] = min(_clamp_signed(bond_delta.get("closeness"), -0.35, 0.35, 0.0), -0.04)
            bond_delta["hurt"] = max(_clamp_signed(bond_delta.get("hurt"), -0.35, 0.35, 0.0), 0.06)
            bond_delta["irritation"] = max(_clamp_signed(bond_delta.get("irritation"), -0.35, 0.35, 0.0), 0.06)
            allostasis_delta["autonomy_need"] = max(_clamp_signed(allostasis_delta.get("autonomy_need"), -0.35, 0.35, 0.0), 0.05)
        out["reason"] = "coercive_boundary_calibrated"

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


def _finalize_turn_appraisal_payload(
    appraisal: dict[str, Any] | None,
    *,
    user_text: str,
    response_style_hint: str,
    science_mode: bool,
    current_event: dict[str, Any] | None = None,
    prev_emotion_state: dict[str, Any] | None = None,
    prev_bond_state: dict[str, Any] | None = None,
    prev_allostasis_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
    interaction_carryover: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = _coerce_appraisal_payload(appraisal)
    out = _soft_accept_appraisal_payload(
        out,
        response_style_hint=response_style_hint,
        current_event=current_event,
        semantic_narrative_profile=semantic_narrative_profile,
        interaction_carryover=interaction_carryover,
    )
    out = _postprocess_appraisal_payload(
        out,
        user_text=user_text,
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        current_event=current_event,
        prev_emotion_state=prev_emotion_state,
        prev_bond_state=prev_bond_state,
        prev_allostasis_state=prev_allostasis_state,
        semantic_narrative_profile=semantic_narrative_profile,
        interaction_carryover=interaction_carryover,
    )
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


def _build_turn_appraisal_prompt(
    *,
    actor_name: str,
    counterpart_name: str,
    response_style_hint: str,
    prev_emotion_state: dict[str, Any],
    prev_bond_state: dict[str, Any],
    prev_allostasis_state: dict[str, Any],
    relationship_summary: str,
    user_text: str,
    focus_lines: list[str] | None = None,
    recent_lines: list[str] | None = None,
    semantic_hint: str = "",
    current_event: dict[str, Any] | None = None,
    interaction_carryover: dict[str, Any] | None = None,
    extra_constraints: list[str] | None = None,
    preface_note: str = "",
) -> str:
    focus_block = "- worldline_focus:\n" + "\n".join(focus_lines or []) + "\n" if focus_lines else ""
    dialogue_block = "- recent_dialogue:\n" + "\n".join(recent_lines or []) + "\n" if recent_lines else ""
    semantic_block = f"- semantic_narrative_bias={semantic_hint}\n" if semantic_hint else ""
    carryover_block = ""
    carryover_hint = _compact_interaction_carryover_hint(interaction_carryover)
    if isinstance(interaction_carryover, dict) and interaction_carryover:
        carryover_block = (
            f"- interaction_carryover_mode={str(interaction_carryover.get('carryover_mode') or '').strip()}\n"
            f"- interaction_carryover_strength={_clamp01(interaction_carryover.get('strength'), 0.0)}\n"
            f"- interaction_carryover_weather={str(interaction_carryover.get('relationship_weather') or '').strip()}\n"
            f"- interaction_carryover_attention={str(interaction_carryover.get('attention_target') or '').strip()}\n"
            f"- interaction_carryover_note={carryover_hint}\n"
        )
    current_event_block = ""
    if isinstance(current_event, dict) and current_event:
        current_event_block = (
            f"- current_event_kind={str(current_event.get('kind') or '').strip()}\n"
            f"- current_event_source={str(current_event.get('source') or '').strip()}\n"
            f"- current_event_frame={str(current_event.get('event_frame') or '').strip()[:160]}\n"
            f"- current_event_text={str(current_event.get('effective_text') or current_event.get('text') or '').strip()[:220]}\n"
            f"- current_event_tags={_safe_json(current_event.get('tags') if isinstance(current_event.get('tags'), list) else [])}\n"
        )
    constraint_lines = [
        "优先根据语义、对话走势和长期关系来判断，不要做关键词触发式的机械归类。",
        "interaction_frame 反映这轮更像任务、陪伴、关系、回忆还是自我追问，不要机械跟随字面关键词。",
        "salience 反映这轮各个维度的真实权重，和 signals 一起服务后续状态演化。",
        "不要把科学问题默认判成负面情绪。",
        "用户说自己“有点累/有点烦”，很多时候是在表达自身状态，不等于把负面情绪指向对方。",
        "“别讲大道理 / 像平时那样说两句 / 回我一句” 这类表达通常是在要熟悉的陪伴，不等于关系冲突。",
        "“还没说开 / 别扭 / 介意 / 不想理你” 更接近 hurt/withdrawal，不等于已经修复。",
        "道歉通常意味着 partial repair，不等于瞬间清零。",
        "只有明确认错、道歉或主动补救时才标记 repair；单纯关心、安抚、解释真实状态，不算 repair。",
        "礼貌、克制、解释式表达不自动等于 neutral/logic；低唤醒的赞同、反对、后悔仍然可能是情绪或关系信号。",
        "替对方辩护、站队或安慰时，区分 supportive care 和 shared frustration/disappointment；支持不等于一定正向。",
        "羞怯、尴尬、认错、后悔更接近脆弱或修复，不要只当成普通澄清。",
        "只有在明显安全、无贬损、无排斥时才算 tease；轻蔑、侮辱、嫌恶更接近 angry/hurt。",
        "把长期共同历史当成解释背景，不要把关系看成每轮从零开始。",
        "如果这轮还延续着上一轮留下的 own_rhythm、quiet_recontact 或 guarded/warm residue，就按连续场景理解，不要当成凭空开启的新对话。",
        "只判断这轮对状态的意义，不写最终回答。",
    ]
    if preface_note:
        constraint_lines.insert(0, str(preface_note).strip())
    for line in extra_constraints or []:
        line = str(line or "").strip()
        if line:
            constraint_lines.append(line)
    constraints_block = "\n".join(f"- {line}" for line in constraint_lines)
    return (
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
        f"{constraints_block}\n"
        f"- response_style_hint={response_style_hint}\n"
        f"- previous_emotion={_safe_json(prev_emotion_state)}\n"
        f"- previous_bond={_safe_json(prev_bond_state)}\n"
        f"- previous_allostasis={_safe_json(prev_allostasis_state)}\n"
        f"- relationship={relationship_summary}\n"
        f"{semantic_block}"
        f"{carryover_block}"
        f"{focus_block}"
        f"{dialogue_block}"
        f"{current_event_block}"
        + f"- current_user={user_text}\n"
    )


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
    interaction_carryover: dict[str, Any] | None = None,
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
    prompt = _build_turn_appraisal_prompt(
        actor_name=actor_name,
        counterpart_name=counterpart_name,
        response_style_hint=response_style_hint,
        prev_emotion_state=prev_emotion_state,
        prev_bond_state=prev_bond_state,
        prev_allostasis_state=prev_allostasis_state,
        relationship_summary=relationship_summary,
        user_text=user_text,
        focus_lines=focus_lines,
        recent_lines=recent_lines,
        semantic_hint=semantic_hint,
        current_event=current_event,
        interaction_carryover=interaction_carryover,
    )
    try:
        llm = _model(temperature=0.0)
        out = _invoke_model_with_retries(llm, [SystemMessage(content=prompt)])
        obj = _extract_json_block(str(getattr(out, "content", "") or ""))
        appraisal = _finalize_turn_appraisal_payload(
            obj,
            user_text=user_text,
            response_style_hint=response_style_hint,
            science_mode=science_mode,
            current_event=current_event,
            prev_emotion_state=prev_emotion_state,
            prev_bond_state=prev_bond_state,
            prev_allostasis_state=prev_allostasis_state,
            semantic_narrative_profile=semantic_narrative_profile,
            interaction_carryover=interaction_carryover,
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
