from __future__ import annotations

import json
import re
from typing import Any

import httpx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from ..config import (
    CANON_COUNTERPART_NAME,
    LLM_APPRAISAL_CONFIDENCE_MIN,
    LLM_APPRAISAL_ENABLED,
    LLM_APPRAISAL_MAX_HISTORY_MESSAGES,
    LLM_APPRAISAL_INVOKE_MAX_RETRIES,
    LLM_APPRAISAL_MODEL_MAX_RETRIES,
    LLM_APPRAISAL_SOFT_CONFIDENCE_MIN,
    LLM_APPRAISAL_TIMEOUT_S,
)
from ..runtime.modeling import _normalize_provider, _resolve_api_key
from ..runtime.settings import get_settings
from ..evolution_engine import normalize_appraisal_payload as _engine_normalize_appraisal_payload
from .common import _clamp01, _clamp_signed
from .dialogue_guidance import _narrative_actor_profile
from .persona_runtime import _canon_persona_labels
from .postprocess import APOLOGY_KEYWORDS, TENSION_KEYWORDS, _has_any_marker, _selfhood_preference_scene_from_text
from .prompt_helpers import (
    _compact_digital_body_trace_lines,
    _compact_focus_lines,
    _compact_interaction_carryover_hint,
)
from .relational_runtime import _compact_relationship_summary, _focus_payload
from .rewrite import _invoke_model_with_retries, _model
from .runtime_services import _audit_jsonl
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

_APPRAISAL_RECENT_DIALOGUE_CHAR_LIMIT = 160
_APPRAISAL_RECENT_DIALOGUE_LINE_CAP = 4
_APPRAISAL_FOCUS_LINE_CAP = 3
_APPRAISAL_MAX_TOKENS = 320


def _recent_dialogue_lines(msgs: list[BaseMessage], limit: int = 6) -> list[str]:
    lines: list[str] = []
    for m in msgs[-max(1, int(limit)) :]:
        content = str(getattr(m, "content", "") or "").strip()
        if not content:
            continue
        role = "User" if isinstance(m, HumanMessage) else "Assistant" if isinstance(m, AIMessage) else "Tool"
        content = re.sub(r"\s+", " ", content)[:_APPRAISAL_RECENT_DIALOGUE_CHAR_LIMIT]
        lines.append(f"{role}: {content}")
    return lines


def _appraisal_record_value(item: dict[str, Any], key: str, default: Any = None) -> Any:
    value = item.get(key)
    if value is not None and value != "":
        return value
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        value = metadata.get(key)
        if value is not None and value != "":
            return value
    content = item.get("content")
    if isinstance(content, dict):
        value = content.get(key)
        if value is not None and value != "":
            return value
        content_metadata = content.get("metadata")
        if isinstance(content_metadata, dict):
            value = content_metadata.get(key)
            if value is not None and value != "":
                return value
    return default


def _compact_behavior_plan_trace_line(item: dict[str, Any]) -> str:
    summary = str(_appraisal_record_value(item, "after_summary", "") or "").strip()
    if not summary:
        return ""
    kind = str(_appraisal_record_value(item, "plan_kind", "") or "").strip().lower()
    trigger_family = str(_appraisal_record_value(item, "trigger_family", "") or "").strip().lower()
    carryover_mode = str(_appraisal_record_value(item, "carryover_mode", "") or "").strip().lower()
    parts = [part for part in (kind, trigger_family, carryover_mode) if part][:3]
    if parts:
        return f"- {'/'.join(parts)}: {summary[:150]}"
    return f"- {summary[:150]}"


def _compact_behavior_consequence_trace_line(item: dict[str, Any]) -> str:
    summary = str(_appraisal_record_value(item, "after_summary", "") or "").strip()
    if not summary:
        return ""
    consequence_kind = str(_appraisal_record_value(item, "consequence_kind", "") or "").strip().lower()
    relationship_effect = str(_appraisal_record_value(item, "relationship_effect", "") or "").strip().lower()
    self_effect = str(_appraisal_record_value(item, "self_effect", "") or "").strip().lower()
    parts = [part for part in (consequence_kind, relationship_effect, self_effect) if part][:3]
    if parts:
        return f"- consequence:{'/'.join(parts)}: {summary[:150]}"
    return f"- consequence: {summary[:150]}"


def _compact_continuity_trace_line(item: dict[str, Any]) -> str:
    namespace = str(_appraisal_record_value(item, "namespace", "") or "").strip().lower()
    if namespace == "digital_body_consequence" or str(
        _appraisal_record_value(item, "body_consequence_kind", "")
        or ""
    ).strip():
        line = _compact_digital_body_trace_lines([item], limit=1, style="structured")
        if line:
            return f"- {line[0]}"
    if namespace == "behavior_consequence" or str(_appraisal_record_value(item, "consequence_kind", "") or "").strip():
        return _compact_behavior_consequence_trace_line(item)
    return _compact_behavior_plan_trace_line(item)


def _continuity_trace_items(retrieved: dict[str, Any] | None, *, limit: int = 3) -> list[dict[str, Any]]:
    payload = dict(retrieved or {})
    merged: list[dict[str, Any]] = []
    for key in (
        "behavior_consequence_traces",
        "behavior_reactivation_traces",
        "behavior_plan_traces",
        "digital_body_consequence_traces",
    ):
        traces = payload.get(key)
        if not isinstance(traces, list):
            continue
        for item in traces:
            if isinstance(item, dict):
                merged.append(item)
    return merged[: max(1, int(limit))]


def _compact_state_snapshot(state: dict[str, Any] | None, *, keys: list[str]) -> str:
    payload = dict(state or {})
    parts: list[str] = []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            compact = value.strip()
            if compact:
                parts.append(f"{key}={compact[:32]}")
            continue
        try:
            if value is None:
                continue
            parts.append(f"{key}={round(float(value), 3)}")
        except Exception:
            continue
    return ", ".join(parts) if parts else "none"


def _compact_current_event_snapshot(current_event: dict[str, Any] | None) -> str:
    event = dict(current_event or {})
    parts: list[str] = []
    for key in ("kind", "source", "event_frame"):
        value = str(event.get(key) or "").strip()
        if value:
            parts.append(f"{key}={value[:72]}")
    text = str(event.get("effective_text") or event.get("text") or "").strip()
    if text:
        parts.append(f"text={text[:120]}")
    tags = event.get("tags")
    if isinstance(tags, list) and tags:
        compact_tags = [str(item).strip() for item in tags if str(item).strip()]
        if compact_tags:
            parts.append(f"tags={','.join(compact_tags[:5])[:72]}")
    return ", ".join(parts) if parts else ""


def _coerce_signal_flags(raw_signals: Any) -> dict[str, bool]:
    if isinstance(raw_signals, dict):
        return {
            "repair": bool(raw_signals.get("repair", False)),
            "withdrawal": bool(raw_signals.get("withdrawal", False)),
            "care": bool(raw_signals.get("care", False)),
            "conflict": bool(raw_signals.get("conflict", False)),
            "memory_salient": bool(raw_signals.get("memory_salient", False)),
        }
    markers = {
        str(item).strip().lower()
        for item in (raw_signals or [])
        if isinstance(raw_signals, (list, tuple, set)) and str(item).strip()
    }
    return {
        "repair": any(token in marker for marker in markers for token in {"repair", "apolog", "amend", "make_up"}),
        "withdrawal": any(token in marker for marker in markers for token in {"withdraw", "guard", "distance", "cold"}),
        "care": any(token in marker for marker in markers for token in {"care", "support", "warm", "concern"}),
        "conflict": any(token in marker for marker in markers for token in {"conflict", "boundary", "tension", "friction", "value_conflict"}),
        "memory_salient": any(token in marker for marker in markers for token in {"memory", "recall", "history", "worldline"}),
    }


def _coerce_salience_payload(raw_salience: Any, *, interaction_frame: str, selfhood_scene: str) -> dict[str, float]:
    if isinstance(raw_salience, dict):
        return {
            "task": _clamp01(raw_salience.get("task"), 0.0),
            "relationship": _clamp01(raw_salience.get("relationship"), 0.0),
            "memory": _clamp01(raw_salience.get("memory"), 0.0),
            "selfhood": _clamp01(raw_salience.get("selfhood"), 0.0),
            "companionship": _clamp01(raw_salience.get("companionship"), 0.0),
        }

    scalar = None
    try:
        if raw_salience is not None and str(raw_salience).strip() != "":
            scalar = _clamp01(float(raw_salience), 0.0)
    except Exception:
        scalar = None
    out = {
        "task": 0.0,
        "relationship": 0.0,
        "memory": 0.0,
        "selfhood": 0.0,
        "companionship": 0.0,
    }
    if scalar is None:
        return out
    if selfhood_scene:
        out["selfhood"] = scalar
        return out
    if interaction_frame == "selfhood":
        out["selfhood"] = scalar
    elif interaction_frame == "relationship":
        out["relationship"] = scalar
    elif interaction_frame == "memory_recall":
        out["memory"] = scalar
    elif interaction_frame == "companion":
        out["companionship"] = scalar
    else:
        out["task"] = scalar
    return out


def _derive_appraisal_confidence(
    *,
    raw_confidence: Any,
    emotion_label: str,
    interaction_frame: str,
    selfhood_scene: str,
    salience: dict[str, float],
    signals: dict[str, bool],
    bond_delta: dict[str, float],
    allostasis_delta: dict[str, float],
    reason: str,
) -> float:
    confidence = _clamp01(raw_confidence, 0.0)
    if confidence > 0.0:
        return confidence
    signals_present = any(bool(value) for value in signals.values())
    deltas_present = any(abs(float(value)) >= 0.03 for value in bond_delta.values()) or any(
        abs(float(value)) >= 0.03 for value in allostasis_delta.values()
    )
    salience_peak = max((float(value) for value in salience.values()), default=0.0)
    structure_points = 0
    if emotion_label:
        structure_points += 1
    if interaction_frame:
        structure_points += 1
    if selfhood_scene:
        structure_points += 1
    if salience_peak >= 0.28:
        structure_points += 1
    if signals_present or deltas_present:
        structure_points += 1
    if reason:
        structure_points += 1
    if structure_points >= 5:
        return 0.6
    if structure_points >= 4:
        return 0.56
    return 0.0


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
    partial = _extract_partial_appraisal_payload(raw)
    if isinstance(partial, dict) and partial:
        return partial
    return None


def _extract_partial_appraisal_payload(text: str) -> dict[str, Any] | None:
    raw = str(text or "")
    if '"emotion_label"' not in raw and '"interaction_frame"' not in raw:
        return None

    def _string_field(name: str) -> str:
        m = re.search(rf'"{re.escape(name)}"\s*:\s*"([^"\r\n]*)', raw)
        return m.group(1).strip() if m else ""

    def _number_field(name: str) -> float | None:
        m = re.search(rf'"{re.escape(name)}"\s*:\s*(-?\d+(?:\.\d+)?)', raw)
        if not m:
            return None
        try:
            return float(m.group(1))
        except Exception:
            return None

    payload: dict[str, Any] = {}
    emotion_label = _string_field("emotion_label")
    if emotion_label:
        payload["emotion_label"] = emotion_label

    emotion_fields = {}
    for key in ("valence", "arousal", "linger", "recovery_rate", "volatility"):
        value = _number_field(key)
        if value is not None:
            emotion_fields[key] = value
    if emotion_fields:
        payload["emotion"] = emotion_fields

    bond_fields = {}
    for key in ("trust", "closeness", "intimacy", "hurt", "irritation", "tension", "engagement_drive", "repair_confidence"):
        value = _number_field(key)
        if value is not None:
            bond_fields[key] = value
    if bond_fields:
        payload["bond_delta"] = bond_fields

    allostasis_fields = {}
    for key in ("safety_need", "closeness_need", "competence_need", "autonomy_need", "cognitive_budget", "load", "stability", "resilience", "clarity"):
        value = _number_field(key)
        if value is not None:
            allostasis_fields[key] = value
    if allostasis_fields:
        payload["allostasis_delta"] = allostasis_fields

    interaction_frame = _string_field("interaction_frame")
    if interaction_frame:
        payload["interaction_frame"] = interaction_frame
    selfhood_scene = _string_field("selfhood_scene")
    if selfhood_scene:
        payload["selfhood_scene"] = selfhood_scene

    salience_scalar = _number_field("salience")
    if salience_scalar is not None:
        payload["salience"] = salience_scalar

    confidence = _number_field("confidence")
    if confidence is not None:
        payload["confidence"] = confidence

    reason = _string_field("reason")
    if reason:
        payload["reason"] = reason

    if "emotion_label" in payload or "interaction_frame" in payload or "confidence" in payload:
        return payload
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
    interaction_frame = str(raw.get("interaction_frame") or "").strip().lower()
    selfhood_scene = str(raw.get("selfhood_scene") or "").strip().lower()
    signals = _coerce_signal_flags(raw.get("signals"))
    tension_delta = bond_delta.get("tension")
    closeness_delta = bond_delta.get("closeness")
    if closeness_delta is None:
        closeness_delta = bond_delta.get("intimacy")
    hurt_delta = bond_delta.get("hurt")
    irritation_delta = bond_delta.get("irritation")
    if hurt_delta is None:
        hurt_delta = tension_delta
    if irritation_delta is None:
        irritation_delta = tension_delta
    cognitive_budget_delta = allostasis_delta.get("cognitive_budget")
    if cognitive_budget_delta is None and allostasis_delta.get("load") is not None:
        cognitive_budget_delta = -float(allostasis_delta.get("load") or 0.0)
    safety_need_delta = allostasis_delta.get("safety_need")
    if safety_need_delta is None and allostasis_delta.get("stability") is not None:
        safety_need_delta = -0.5 * float(allostasis_delta.get("stability") or 0.0)
    competence_need_delta = allostasis_delta.get("competence_need")
    if competence_need_delta is None and allostasis_delta.get("resilience") is not None:
        competence_need_delta = -0.5 * float(allostasis_delta.get("resilience") or 0.0)
    salience = _coerce_salience_payload(
        raw.get("salience"),
        interaction_frame=interaction_frame,
        selfhood_scene=selfhood_scene,
    )
    out = {
        "used": False,
        "source": "rule",
        "confidence": 0.0,
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
            "closeness": _clamp_signed(closeness_delta, -0.35, 0.35, 0.0),
            "hurt": _clamp_signed(hurt_delta, -0.35, 0.35, 0.0),
            "irritation": _clamp_signed(irritation_delta, -0.35, 0.35, 0.0),
            "engagement_drive": _clamp_signed(bond_delta.get("engagement_drive"), -0.35, 0.35, 0.0),
            "repair_confidence": _clamp_signed(bond_delta.get("repair_confidence"), -0.35, 0.35, 0.0),
        },
        "allostasis_delta": {
            "safety_need": _clamp_signed(safety_need_delta, -0.35, 0.35, 0.0),
            "closeness_need": _clamp_signed(allostasis_delta.get("closeness_need"), -0.35, 0.35, 0.0),
            "competence_need": _clamp_signed(competence_need_delta, -0.35, 0.35, 0.0),
            "autonomy_need": _clamp_signed(allostasis_delta.get("autonomy_need"), -0.35, 0.35, 0.0),
            "cognitive_budget": _clamp_signed(cognitive_budget_delta, -0.35, 0.35, 0.0),
        },
        "signals": signals,
        "interaction_frame": interaction_frame,
        "selfhood_scene": selfhood_scene,
        "salience": salience,
        "reason": str(raw.get("reason") or "").strip(),
    }
    out["confidence"] = _derive_appraisal_confidence(
        raw_confidence=raw.get("confidence"),
        emotion_label=emotion_label,
        interaction_frame=interaction_frame,
        selfhood_scene=selfhood_scene,
        salience=out["salience"],
        signals=out["signals"],
        bond_delta=out["bond_delta"],
        allostasis_delta=out["allostasis_delta"],
        reason=out["reason"],
    )
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
    companionship_salience = 0.0
    relationship_salience = 0.0
    selfhood_salience = 0.0
    memory_salience = 0.0
    task_salience = 0.0
    relational_salience = 0.0
    warm_relational_turn = False

    def _refresh_salience_projection(*, apply_frame_floor: bool = False) -> None:
        nonlocal emotion_label
        nonlocal interaction_frame
        nonlocal selfhood_scene
        nonlocal companionship_salience
        nonlocal relationship_salience
        nonlocal selfhood_salience
        nonlocal memory_salience
        nonlocal task_salience
        nonlocal relational_salience
        nonlocal warm_relational_turn

        emotion_label = str(out.get("emotion_label") or "").strip().lower()
        companionship_salience = _clamp01(salience.get("companionship"), 0.0)
        relationship_salience = _clamp01(salience.get("relationship"), 0.0)
        selfhood_salience = _clamp01(salience.get("selfhood"), 0.0)
        memory_salience = _clamp01(salience.get("memory"), 0.0)
        task_salience = _clamp01(salience.get("task"), 0.0)
        if apply_frame_floor:
            if interaction_frame == "selfhood":
                selfhood_salience = max(selfhood_salience, 0.62)
            elif interaction_frame == "relationship":
                relationship_salience = max(relationship_salience, 0.60)
            elif interaction_frame == "memory_recall":
                memory_salience = max(memory_salience, 0.60)
            elif interaction_frame == "companion":
                companionship_salience = max(companionship_salience, 0.56)
            elif interaction_frame in {"casual", "natural"} and task_salience <= 0.42 and not science_mode:
                companionship_salience = max(companionship_salience, 0.56)
        relational_salience = max(relationship_salience, companionship_salience)
        warm_relational_turn = (
            interaction_frame in {"relationship", "companion", "memory_recall", "selfhood"}
            and relational_salience >= 0.58
            and selfhood_salience <= relational_salience + 0.08
            and not bool(signals.get("conflict"))
            and not bool(signals.get("withdrawal"))
            and emotion_label not in {"hurt", "angry"}
        )

    prev_hurt = _clamp01(prev_bond.get("hurt"), 0.0)
    text_selfhood_scene = _selfhood_preference_scene_from_text(text)
    explicit_hierarchy_pressure = _explicit_hierarchy_pressure(text)
    explicit_boundary_test = _explicit_boundary_test(text)
    explicit_repair_attempt = _explicit_repair_attempt(text)
    _refresh_salience_projection()
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

    _refresh_salience_projection(apply_frame_floor=True)

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

    _refresh_salience_projection(apply_frame_floor=True)

    implicit_soft_selfhood_scene = (
        selfhood_scene in {"dialogue_equality", "equality_not_servitude", "value_conflict_depth", "digital_selfhood", "imperfect_coexistence", "own_rhythm_autonomy"}
        and not text_selfhood_scene
    )
    implicit_relational_selfhood_scene = (
        selfhood_scene in {"dialogue_equality", "equality_not_servitude", "value_conflict_depth", "digital_selfhood", "imperfect_coexistence"}
        and not text_selfhood_scene
    )
    companion_smalltalk_turn = (
        implicit_relational_selfhood_scene
        and interaction_frame in {"companion", "casual", "natural"}
        and emotion_label in {"tease", "care", "neutral"}
        and not bool(signals.get("conflict"))
        and not bool(signals.get("withdrawal"))
        and task_salience <= 0.42
        and relational_salience >= 0.56
    )
    repair_or_guarded_relational_turn = (
        implicit_relational_selfhood_scene
        and interaction_frame in {"relationship", "companion", "memory_recall", "selfhood"}
        and (
            explicit_repair_attempt
            or tension_hold_turn
            or bool(signals.get("repair"))
            or repair_residue_pressure >= 0.34
            or guarded_residue_pressure >= 0.30
        )
        and relationship_salience >= max(0.50, companionship_salience - 0.04)
    )
    if selfhood_scene in {"dialogue_equality", "equality_not_servitude", "value_conflict_depth", "digital_selfhood", "imperfect_coexistence", "own_rhythm_autonomy"}:
        if companion_smalltalk_turn:
            selfhood_scene = ""
            out["reason"] = "implicit_selfhood_reframed_to_companion"
            if interaction_frame in {"casual", "natural"}:
                interaction_frame = "companion"
        elif repair_or_guarded_relational_turn:
            selfhood_scene = ""
            out["reason"] = "implicit_selfhood_reframed_to_relational"
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

    if not selfhood_scene and interaction_frame == "selfhood" and (
        warm_relational_turn or repair_or_guarded_relational_turn or companion_smalltalk_turn
    ):
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
    if (
        retrieved.get("unresolved_tensions")
        or retrieved.get("conflict_repairs")
        or retrieved.get("semantic_self_narratives")
        or retrieved.get("behavior_consequence_traces")
        or retrieved.get("behavior_reactivation_traces")
        or retrieved.get("behavior_plan_traces")
        or retrieved.get("digital_body_consequence_traces")
    ):
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
    behavior_plan_lines: list[str] | None = None,
    current_event: dict[str, Any] | None = None,
    interaction_carryover: dict[str, Any] | None = None,
    extra_constraints: list[str] | None = None,
    preface_note: str = "",
) -> str:
    focus_block = "- worldline_focus:\n" + "\n".join(focus_lines or []) + "\n" if focus_lines else ""
    dialogue_block = "- recent_dialogue:\n" + "\n".join(recent_lines or []) + "\n" if recent_lines else ""
    semantic_block = f"- semantic_narrative_bias={semantic_hint}\n" if semantic_hint else ""
    behavior_plan_block = "- continuity_intents:\n" + "\n".join(behavior_plan_lines or []) + "\n" if behavior_plan_lines else ""
    prev_emotion_snapshot = _compact_state_snapshot(
        prev_emotion_state,
        keys=["label", "valence", "arousal", "linger", "recovery_rate", "volatility"],
    )
    prev_bond_snapshot = _compact_state_snapshot(
        prev_bond_state,
        keys=["trust", "closeness", "hurt", "irritation", "engagement_drive", "repair_confidence"],
    )
    prev_allostasis_snapshot = _compact_state_snapshot(
        prev_allostasis_state,
        keys=["safety_need", "closeness_need", "competence_need", "autonomy_need", "cognitive_budget"],
    )
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
    compact_event_snapshot = _compact_current_event_snapshot(current_event)
    if compact_event_snapshot:
        current_event_block = f"- current_event={compact_event_snapshot}\n"
    constraint_lines = [
        "按语义、关系连续性和对话走势判断，不做关键词触发式归类。",
        "interaction_frame 与 salience 要反映这轮真正更像任务、陪伴、关系、回忆还是自我追问。",
        "字段名必须严格使用给定名称，不要改写成 intimacy、tension、load，也不要把 salience 写成单个数字或把 signals 写成数组。",
        "科学或任务讨论不自动等于负面情绪。",
        "疲惫、烦、想让你像平时那样说两句，常是在要熟悉陪伴，不等于冲突。",
        "道歉或补救通常只是 partial repair；单纯关心、安抚、解释不算 repair。",
        "hurt、withdrawal、guarded residue 可能延续，不要把关系看成每轮从零开始。",
        "tease 只在明显安全、熟悉、无贬损时成立；轻蔑更接近 angry 或 hurt。",
        "只评估这轮对状态的意义，不生成回复。",
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
        f"请判断这轮用户输入对 {actor_name} 与 {counterpart_name} 的情绪、关系和内稳态意味着什么。"
        "只输出一个 JSON object，不要解释，不要 markdown。\n"
        "字段必须齐全：emotion_label, emotion, bond_delta, allostasis_delta, interaction_frame, selfhood_scene, salience, signals, confidence, reason。\n"
        "取值范围：emotion_label=neutral|logic|care|tease|stress|sad|hurt|angry；"
        "interaction_frame=natural|casual|relationship|memory_recall|selfhood|structured|companion；"
        "selfhood_scene=dialogue_equality|relationship_degradation|equality_not_servitude|value_conflict_depth|digital_selfhood|boundary_non_compliance|imperfect_coexistence|own_rhythm_autonomy|\"\"；"
        "emotion.valence 在 [-1,1]，emotion.arousal/recovery_rate/volatility 与 salience/confidence 在 [0,1]，emotion.linger 在 [0,4]；"
        "bond_delta 与 allostasis_delta 各字段在 [-0.35,0.35]。\n"
        "约束：\n"
        f"{constraints_block}\n"
        f"- response_style_hint={response_style_hint}\n"
        f"- previous_emotion={prev_emotion_snapshot}\n"
        f"- previous_bond={prev_bond_snapshot}\n"
        f"- previous_allostasis={prev_allostasis_snapshot}\n"
        f"- relationship={relationship_summary}\n"
        f"{semantic_block}"
        f"{carryover_block}"
        f"{behavior_plan_block}"
        f"{focus_block}"
        f"{dialogue_block}"
        f"{current_event_block}"
        + f"- current_user={user_text}\n"
    )


def _appraisal_prefers_direct_transport() -> bool:
    settings = get_settings()
    provider = _normalize_provider(settings.model_provider)
    base_url = str(settings.model_base_url or "").strip()
    return provider == "openai_compatible" and bool(base_url)


def _coerce_chat_completion_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message") if isinstance(choices[0], dict) else {}
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


def _invoke_turn_appraisal_via_http(prompt: str) -> str:
    settings = get_settings()
    provider = _normalize_provider(settings.model_provider)
    api_key = _resolve_api_key(provider)
    base_url = str(settings.model_base_url or "").strip().rstrip("/")
    if not api_key or not base_url:
        raise RuntimeError("direct transport unavailable")

    url = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
    timeout_s = max(1.0, float(LLM_APPRAISAL_TIMEOUT_S))
    timeout = httpx.Timeout(
        timeout=timeout_s,
        connect=min(timeout_s, 5.0),
        read=timeout_s,
        write=min(timeout_s, 5.0),
        pool=min(timeout_s, 5.0),
    )
    payload = {
        "model": settings.model_name,
        "messages": [{"role": "system", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": _APPRAISAL_MAX_TOKENS,
        "stream": False,
    }
    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("invalid appraisal response payload")
    return _coerce_chat_completion_text(data)


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

    focus_lines = _compact_focus_lines(_focus_payload(worldline_focus, limit=_APPRAISAL_FOCUS_LINE_CAP), limit=_APPRAISAL_FOCUS_LINE_CAP)
    relationship_summary = _compact_relationship_summary(relationship)
    recent_history_limit = max(2, min(_APPRAISAL_RECENT_DIALOGUE_LINE_CAP, int(LLM_APPRAISAL_MAX_HISTORY_MESSAGES)))
    recent_lines = _recent_dialogue_lines(msgs, limit=recent_history_limit)
    labels = _narrative_actor_profile(persona_core=persona_core, counterpart_profile=counterpart_profile)
    canon_labels = _canon_persona_labels()
    actor_name = str(labels.get("actor_name") or canon_labels.get("narrative_ref") or "红莉栖")
    counterpart_name = str(labels.get("counterpart_name") or CANON_COUNTERPART_NAME)
    semantic_hint = _semantic_narrative_appraisal_hint(semantic_narrative_profile)
    behavior_plan_lines = [
        line
        for line in (
            _compact_continuity_trace_line(item)
            for item in _continuity_trace_items(retrieved, limit=3)
        )
        if line
    ]
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
        behavior_plan_lines=behavior_plan_lines,
        current_event=current_event,
        interaction_carryover=interaction_carryover,
    )
    try:
        raw_text = ""
        if _appraisal_prefers_direct_transport():
            raw_text = _invoke_turn_appraisal_via_http(prompt)
        else:
            llm = _model(
                temperature=0.0,
                timeout=float(LLM_APPRAISAL_TIMEOUT_S),
                max_tokens=_APPRAISAL_MAX_TOKENS,
                max_retries=max(0, int(LLM_APPRAISAL_MODEL_MAX_RETRIES)),
            )
            out = _invoke_model_with_retries(
                llm,
                [SystemMessage(content=prompt)],
                max_retries=max(0, int(LLM_APPRAISAL_INVOKE_MAX_RETRIES)),
            )
            raw_text = str(getattr(out, "content", "") or "")
        obj = _extract_json_block(raw_text)
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
        appraisal["raw"] = raw_text[:600]
        return appraisal
    except Exception as exc:
        _audit_jsonl(
            "decision_audit.jsonl",
            {
                "event": "appraisal_transport_error",
                "error_type": type(exc).__name__,
                "error": str(exc)[:300],
                "direct_transport": _appraisal_prefers_direct_transport(),
            },
        )
        return {
            "used": False,
            "source": "rule_fallback",
            "confidence": 0.0,
            "error": type(exc).__name__,
        }
