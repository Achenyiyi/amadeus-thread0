from __future__ import annotations

import re
from typing import Any

from ..config import (
    ABLATE_WORLDLINE_MEMORY,
    MOMENTS_LIMIT_HIGH,
    MOMENTS_LIMIT_LOW,
    REFLECTIONS_LIMIT_HIGH,
    REFLECTIONS_LIMIT_LOW,
    RETRIEVAL_MIN_LEN,
    RETRIEVAL_TRIGGERS,
    WORKING_CONTEXT_MAX_CHARS,
    WORKING_CONTEXT_MAX_ITEMS,
)
from ..memory_store import MemoryStore
from .common import _clamp01, _norm_text, _now_ts


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
    try:
        contradiction_pressure = float(_record_value(item, "contradiction_pressure", 0.0) or 0.0)
    except Exception:
        contradiction_pressure = 0.0
    support_norm = max(0.0, min(1.0, support_count / 5.0))
    span_norm = max(0.0, min(1.0, support_span_s / float(3 * 24 * 3600)))
    base = max(
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
    return _clamp01(base * max(0.55, 1.0 - 0.46 * _clamp01(contradiction_pressure, 0.0)))


def _behavior_plan_priority(item: dict[str, Any]) -> float:
    try:
        carryover_strength = float(_record_value(item, "carryover_strength", 0.0) or 0.0)
    except Exception:
        carryover_strength = 0.0
    try:
        presence_residue = float(_record_value(item, "presence_residue", 0.0) or 0.0)
    except Exception:
        presence_residue = 0.0
    try:
        ambient_resonance = float(_record_value(item, "ambient_resonance", 0.0) or 0.0)
    except Exception:
        ambient_resonance = 0.0
    try:
        self_activity_momentum = float(_record_value(item, "self_activity_momentum", 0.0) or 0.0)
    except Exception:
        self_activity_momentum = 0.0
    try:
        scheduled_after_min = int(_record_value(item, "scheduled_after_min", 0) or 0)
    except Exception:
        scheduled_after_min = 0
    kind = str(_record_value(item, "plan_kind", "") or "").strip().lower()
    carryover_mode = str(_record_value(item, "carryover_mode", "") or "").strip().lower()

    continuity_signal = max(
        _clamp01(carryover_strength, 0.0),
        _clamp01(presence_residue, 0.0),
        _clamp01(ambient_resonance, 0.0),
        _clamp01(self_activity_momentum, 0.0),
    )
    base = 0.12 + 0.34 * continuity_signal
    if scheduled_after_min > 0:
        base += 0.08
    if kind in {"deferred_checkin", "small_opening", "shared_activity_offer", "life_nudge", "work_nudge"}:
        base += 0.10
    if carryover_mode in {"small_opening", "own_rhythm", "repair_residue", "warm_residue"}:
        base += 0.10
    return _clamp01(base, 0.0)


def _behavior_reactivation_priority(item: dict[str, Any]) -> float:
    try:
        carryover_strength = float(_record_value(item, "carryover_strength", 0.0) or 0.0)
    except Exception:
        carryover_strength = 0.0
    try:
        presence_residue = float(_record_value(item, "presence_residue", 0.0) or 0.0)
    except Exception:
        presence_residue = 0.0
    try:
        ambient_resonance = float(_record_value(item, "ambient_resonance", 0.0) or 0.0)
    except Exception:
        ambient_resonance = 0.0
    try:
        self_activity_momentum = float(_record_value(item, "self_activity_momentum", 0.0) or 0.0)
    except Exception:
        self_activity_momentum = 0.0
    carryover_mode = str(_record_value(item, "carryover_mode", "") or "").strip().lower()
    source_plan_kind = str(_record_value(item, "source_plan_kind", "") or "").strip().lower()
    current_plan_kind = str(_record_value(item, "current_plan_kind", "") or "").strip().lower()
    primary_motive = str(_record_value(item, "primary_motive", "") or "").strip().lower()
    goal_frame = str(_record_value(item, "goal_frame", "") or "").strip()
    relationship_weather = str(_record_value(item, "relationship_weather", "") or "").strip().lower()

    continuity_signal = max(
        _clamp01(carryover_strength, 0.0),
        _clamp01(presence_residue, 0.0),
        _clamp01(0.82 * ambient_resonance, 0.0),
        _clamp01(self_activity_momentum, 0.0) if carryover_mode in {"own_rhythm", "small_opening"} else 0.0,
    )
    base = 0.16 + 0.40 * continuity_signal
    if carryover_mode in {"small_opening", "quiet_recontact", "own_rhythm", "life_window", "shared_window", "task_window"}:
        base += 0.10
    if source_plan_kind or current_plan_kind:
        base += 0.10
    if primary_motive or goal_frame:
        base += 0.08
    if relationship_weather in {"warm_residue", "guarded_residue", "repair_residue"}:
        base += 0.06
    return _clamp01(base, 0.0)


def _agenda_lifecycle_priority(item: dict[str, Any]) -> float:
    kind = str(_record_value(item, "lifecycle_kind", _record_value(item, "kind", "")) or "").strip().lower()
    trigger_family = str(_record_value(item, "trigger_family", "") or "").strip().lower()
    carryover_mode = str(_record_value(item, "carryover_mode", "") or "").strip().lower()
    try:
        carryover_strength = float(_record_value(item, "carryover_strength", 0.0) or 0.0)
    except Exception:
        carryover_strength = 0.0
    try:
        presence_residue = float(_record_value(item, "presence_residue", 0.0) or 0.0)
    except Exception:
        presence_residue = 0.0
    try:
        ambient_resonance = float(_record_value(item, "ambient_resonance", 0.0) or 0.0)
    except Exception:
        ambient_resonance = 0.0
    try:
        self_activity_momentum = float(_record_value(item, "self_activity_momentum", 0.0) or 0.0)
    except Exception:
        self_activity_momentum = 0.0
    try:
        own_rhythm_bias = float(_record_value(item, "own_rhythm_bias", 0.0) or 0.0)
    except Exception:
        own_rhythm_bias = 0.0
    try:
        recontact_cooldown = float(_record_value(item, "recontact_cooldown", 0.0) or 0.0)
    except Exception:
        recontact_cooldown = 0.0
    try:
        continuity_anchor = float(_record_value(item, "continuity_anchor", 0.0) or 0.0)
    except Exception:
        continuity_anchor = 0.0
    try:
        own_rhythm_anchor = float(_record_value(item, "own_rhythm_anchor", 0.0) or 0.0)
    except Exception:
        own_rhythm_anchor = 0.0
    try:
        recontact_anchor = float(_record_value(item, "recontact_anchor", 0.0) or 0.0)
    except Exception:
        recontact_anchor = 0.0
    try:
        boundary_anchor = float(_record_value(item, "boundary_anchor", 0.0) or 0.0)
    except Exception:
        boundary_anchor = 0.0
    try:
        memory_anchor = float(_record_value(item, "memory_anchor", 0.0) or 0.0)
    except Exception:
        memory_anchor = 0.0
    try:
        hold_count = int(_record_value(item, "hold_count", 0) or 0)
    except Exception:
        hold_count = 0

    continuity_signal = max(
        _clamp01(carryover_strength, 0.0),
        _clamp01(presence_residue, 0.0),
        _clamp01(0.82 * ambient_resonance, 0.0),
        _clamp01(self_activity_momentum, 0.0),
        _clamp01(own_rhythm_bias, 0.0),
        _clamp01(0.74 * continuity_anchor, 0.0),
        _clamp01(0.72 * own_rhythm_anchor, 0.0) if carryover_mode == "own_rhythm" else 0.0,
        _clamp01(0.72 * recontact_anchor, 0.0) if kind == "held" else 0.0,
    )
    base = 0.18 + 0.36 * continuity_signal
    if kind in {"held", "released_to_self_activity"}:
        base += 0.10
    elif kind in {"dropped", "expired"}:
        base += 0.04
    if trigger_family in {"life_window", "shared_activity", "shared_activity_window", "deadline_window"}:
        base += 0.08
    if carryover_mode in {"own_rhythm", "quiet_recontact"}:
        base += 0.08
    if hold_count > 0:
        base += min(0.08, 0.02 * hold_count)
    if recontact_cooldown >= 0.28:
        base += 0.06
    if max(boundary_anchor, memory_anchor) >= 0.36:
        base += 0.04
    return _clamp01(base, 0.0)


def _behavior_consequence_priority(item: dict[str, Any]) -> float:
    consequence_kind = str(_record_value(item, "consequence_kind", "") or "").strip().lower()
    relationship_effect = str(_record_value(item, "relationship_effect", "") or "").strip().lower()
    self_effect = str(_record_value(item, "self_effect", "") or "").strip().lower()
    carryover_mode = str(_record_value(item, "carryover_mode", "") or "").strip().lower()
    try:
        timing_window_min = int(_record_value(item, "timing_window_min", 0) or 0)
    except Exception:
        timing_window_min = 0
    delayed = bool(_record_value(item, "delayed", False))
    silent = bool(_record_value(item, "silent", False))
    stale_window = bool(_record_value(item, "stale_window", False))

    base = 0.18
    if consequence_kind:
        base += 0.10
    if relationship_effect or self_effect:
        base += 0.14
    if carryover_mode:
        base += 0.12
    if timing_window_min > 0:
        base += 0.08
    if delayed or silent:
        base += 0.08
    if stale_window:
        base -= 0.04
    return _clamp01(base, 0.0)


def _behavior_plan_trace_line(item: dict[str, Any]) -> str:
    summary = str(_record_value(item, "after_summary", "") or "").strip()
    if not summary:
        return ""
    item_id = str(item.get("id") or "").strip()
    plan_kind = str(_record_value(item, "plan_kind", "") or "").strip().lower()
    trigger_family = str(_record_value(item, "trigger_family", "") or "").strip().lower()
    carryover_mode = str(_record_value(item, "carryover_mode", "") or "").strip().lower()
    tags = [part for part in (plan_kind, trigger_family, carryover_mode) if part][:3]
    prefix = f"P{item_id}" if item_id else "P"
    if tags:
        return f"{prefix}({'/'.join(tags)}): {summary}"
    return f"{prefix}: {summary}"


def _behavior_reactivation_trace_line(item: dict[str, Any]) -> str:
    summary = str(_record_value(item, "after_summary", "") or "").strip()
    if not summary:
        return ""
    item_id = str(item.get("id") or "").strip()
    carryover_mode = str(_record_value(item, "carryover_mode", "") or "").strip().lower()
    source_plan_kind = str(_record_value(item, "source_plan_kind", "") or "").strip().lower()
    current_plan_kind = str(_record_value(item, "current_plan_kind", "") or "").strip().lower()
    tags = [part for part in (carryover_mode, source_plan_kind, current_plan_kind) if part][:3]
    prefix = f"RA{item_id}" if item_id else "RA"
    if tags:
        return f"{prefix}({'/'.join(tags)}): {summary}"
    return f"{prefix}: {summary}"


def _agenda_lifecycle_trace_line(item: dict[str, Any]) -> str:
    summary = str(_record_value(item, "after_summary", "") or "").strip()
    if not summary:
        return ""
    item_id = str(item.get("id") or "").strip()
    kind = str(_record_value(item, "lifecycle_kind", _record_value(item, "kind", "")) or "").strip().lower()
    trigger_family = str(_record_value(item, "trigger_family", "") or "").strip().lower()
    carryover_mode = str(_record_value(item, "carryover_mode", "") or "").strip().lower()
    tags = [part for part in (kind, trigger_family, carryover_mode) if part][:3]
    prefix = f"AL{item_id}" if item_id else "AL"
    if tags:
        return f"{prefix}({'/'.join(tags)}): {summary}"
    return f"{prefix}: {summary}"


def _behavior_consequence_trace_line(item: dict[str, Any]) -> str:
    summary = str(_record_value(item, "after_summary", "") or "").strip()
    if not summary:
        return ""
    item_id = str(item.get("id") or "").strip()
    consequence_kind = str(_record_value(item, "consequence_kind", "") or "").strip().lower()
    relationship_effect = str(_record_value(item, "relationship_effect", "") or "").strip().lower()
    self_effect = str(_record_value(item, "self_effect", "") or "").strip().lower()
    tags = [part for part in (consequence_kind, relationship_effect, self_effect) if part][:3]
    prefix = f"BC{item_id}" if item_id else "BC"
    if tags:
        return f"{prefix}({'/'.join(tags)}): {summary}"
    return f"{prefix}: {summary}"

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
            "behavior_reactivation_traces": [],
            "behavior_plan_traces": [],
            "agenda_lifecycle_traces": [],
            "behavior_consequence_traces": [],
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
    revision_traces = store.list_revision_traces(limit=40)
    behavior_reactivation_candidates = [
        item
        for item in revision_traces
        if str(_record_value(item, "namespace", "") or "").strip().lower() == "behavior_reactivation"
        and str(_record_value(item, "after_summary", "") or "").strip()
    ]
    behavior_plan_candidates = [
        item
        for item in revision_traces
        if str(_record_value(item, "namespace", "") or "").strip().lower() == "behavior_plan"
        and str(_record_value(item, "after_summary", "") or "").strip()
    ]
    agenda_lifecycle_candidates = [
        item
        for item in revision_traces
        if str(_record_value(item, "namespace", "") or "").strip().lower() == "agenda_lifecycle"
        and str(_record_value(item, "after_summary", "") or "").strip()
    ]
    behavior_consequence_candidates = [
        item
        for item in revision_traces
        if str(_record_value(item, "namespace", "") or "").strip().lower() == "behavior_consequence"
        and str(_record_value(item, "after_summary", "") or "").strip()
    ]
    behavior_reactivation_scored: list[tuple[float, dict[str, Any]]] = []
    behavior_plan_scored: list[tuple[float, dict[str, Any]]] = []
    agenda_lifecycle_scored: list[tuple[float, dict[str, Any]]] = []
    behavior_consequence_scored: list[tuple[float, dict[str, Any]]] = []

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

    for item in behavior_reactivation_candidates:
        summary = str(_record_value(item, "after_summary", "") or "").strip()
        if not summary:
            continue
        source_note = str(_record_value(item, "source_note", "") or "").strip()
        relevance = max(_query_overlap_score(query, summary), _query_overlap_score(query, source_note))
        recency = _recency_score(item.get("updated_at") or item.get("created_at"), 21.0)
        priority = _behavior_reactivation_priority(item)
        score = 0.16 + 0.28 * relevance + 0.24 * recency + 0.32 * priority
        if not query:
            score = max(score, 0.30 + 0.28 * recency + 0.42 * priority)
        behavior_reactivation_scored.append((score, item))
        txt = _behavior_reactivation_trace_line(item)
        if txt:
            scored.append((score, txt))

    for item in behavior_plan_candidates:
        summary = str(_record_value(item, "after_summary", "") or "").strip()
        if not summary:
            continue
        relevance = _query_overlap_score(query, summary)
        recency = _recency_score(item.get("updated_at") or item.get("created_at"), 14.0)
        priority = _behavior_plan_priority(item)
        score = 0.14 + 0.26 * relevance + 0.24 * recency + 0.36 * priority
        if not query:
            score = max(score, 0.28 + 0.30 * recency + 0.42 * priority)
        behavior_plan_scored.append((score, item))
        txt = _behavior_plan_trace_line(item)
        if txt:
            scored.append((score, txt))

    for item in agenda_lifecycle_candidates:
        summary = str(_record_value(item, "after_summary", "") or "").strip()
        if not summary:
            continue
        goal_frame = str(_record_value(item, "goal_frame", "") or "").strip()
        note = str(_record_value(item, "note", "") or "").strip()
        relevance = max(
            _query_overlap_score(query, summary),
            _query_overlap_score(query, goal_frame),
            _query_overlap_score(query, note),
        )
        recency = _recency_score(item.get("updated_at") or item.get("created_at"), 28.0)
        priority = _agenda_lifecycle_priority(item)
        score = 0.15 + 0.28 * relevance + 0.23 * recency + 0.34 * priority
        if not query:
            score = max(score, 0.30 + 0.28 * recency + 0.42 * priority)
        agenda_lifecycle_scored.append((score, item))
        txt = _agenda_lifecycle_trace_line(item)
        if txt:
            scored.append((score, txt))

    for item in behavior_consequence_candidates:
        summary = str(_record_value(item, "after_summary", "") or "").strip()
        if not summary:
            continue
        goal_frame = str(_record_value(item, "goal_frame", "") or "").strip()
        relationship_effect = str(_record_value(item, "relationship_effect", "") or "").strip()
        self_effect = str(_record_value(item, "self_effect", "") or "").strip()
        relevance = max(
            _query_overlap_score(query, summary),
            _query_overlap_score(query, goal_frame),
            _query_overlap_score(query, relationship_effect),
            _query_overlap_score(query, self_effect),
        )
        recency = _recency_score(item.get("updated_at") or item.get("created_at"), 18.0)
        priority = _behavior_consequence_priority(item)
        score = 0.16 + 0.30 * relevance + 0.24 * recency + 0.30 * priority
        if not query:
            score = max(score, 0.28 + 0.30 * recency + 0.42 * priority)
        behavior_consequence_scored.append((score, item))
        txt = _behavior_consequence_trace_line(item)
        if txt:
            scored.append((score, txt))

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

    behavior_reactivation_scored.sort(key=lambda row: row[0], reverse=True)
    behavior_reactivation_traces = [item for _, item in behavior_reactivation_scored[:6]]
    behavior_plan_scored.sort(key=lambda row: row[0], reverse=True)
    behavior_plan_traces = [item for _, item in behavior_plan_scored[:6]]
    agenda_lifecycle_scored.sort(key=lambda row: row[0], reverse=True)
    agenda_lifecycle_traces = [item for _, item in agenda_lifecycle_scored[:6]]
    behavior_consequence_scored.sort(key=lambda row: row[0], reverse=True)
    behavior_consequence_traces = [item for _, item in behavior_consequence_scored[:6]]

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
        "behavior_reactivation_traces": behavior_reactivation_traces,
        "behavior_plan_traces": behavior_plan_traces,
        "agenda_lifecycle_traces": agenda_lifecycle_traces,
        "behavior_consequence_traces": behavior_consequence_traces,
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
        "behavior_reactivation_traces": [],
        "behavior_plan_traces": [],
        "agenda_lifecycle_traces": [],
        "behavior_consequence_traces": [],
        "working_items": [],
        "working_chars": 0,
    }
