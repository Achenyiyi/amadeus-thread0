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


def _graph_impl():
    from .. import graph as g

    return g


def _clamp01(*args, **kwargs):
    return _graph_impl()._clamp01(*args, **kwargs)


def _norm_text(*args, **kwargs):
    return _graph_impl()._norm_text(*args, **kwargs)


def _now_ts(*args, **kwargs):
    return _graph_impl()._now_ts(*args, **kwargs)


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

