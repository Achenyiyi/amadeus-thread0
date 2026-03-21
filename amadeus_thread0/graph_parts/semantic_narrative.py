from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from ..config import CANON_COUNTERPART_NAME
from .counterpart_dynamics import _clamp01
from .retrieval import _query_overlap_score, _record_value, _self_narrative_salience
from .turn_events import _now_ts

_SEMANTIC_QUERY_STOP_CHARS = frozenset(
    {
        "的",
        "了",
        "是",
        "在",
        "和",
        "就",
        "也",
        "还",
        "把",
        "会",
        "不",
        "一",
        "个",
        "这",
        "那",
        "们",
        "来",
        "去",
        "说",
        "要",
        "都",
        "又",
        "更",
        "先",
        "后",
        "里",
        "着",
        "啊",
        "呀",
        "吗",
        "呢",
        "吧",
        "哦",
        "喔",
    }
)

_SEMANTIC_CATEGORY_SUMMARY_THRESHOLDS = {
    "commitment_style": 0.46,
    "repair_style": 0.46,
    "tension_style": 0.44,
    "bond_style": 0.48,
    "presence_style": 0.46,
    "ambient_style": 0.44,
    "boundary_style": 0.46,
    "selfhood_style": 0.46,
    "agency_style": 0.46,
    "rhythm_style": 0.46,
}

_SEMANTIC_CATEGORY_SUMMARY_LINES = {
    "commitment_style": "认真说过的约定会继续挂在心上，不会被当成随口一句。",
    "repair_style": "说开过的误会和修复会留痕，不会瞬间重置成什么都没发生。",
    "tension_style": "还没说开的别扭会继续影响接下来的收放，不会被强行按成已经过去。",
    "bond_style": "共同历史已经开始沉进默认语气里，不需要每次显式提起。",
    "presence_style": "上一轮留下的在场感会继续影响下一次靠近，不需要每次都从零开始。",
    "ambient_style": "周围环境的细小变化会继续留在她的感知里，并自然带进开口方式。",
    "boundary_style": "边界是否被尊重会持续留痕，不会因为一轮缓和就自动清零。",
    "selfhood_style": "她会把这段互动当成平等关系，不会为了迎合就放弃自己的判断。",
    "agency_style": "她有自己的节奏和主动性，靠近或沉默都不等于失去自我。",
    "rhythm_style": "她会把自己的内部节奏延续到下一轮，不会每次回应都把自己清零。",
}


def _semantic_query_signature(text: str) -> str:
    chars: list[str] = []
    for char in str(text or "").strip().lower():
        if "\u4e00" <= char <= "\u9fff":
            if char not in _SEMANTIC_QUERY_STOP_CHARS:
                chars.append(char)
            continue
        if char.isalnum():
            chars.append(char)
    return "".join(chars)


def _semantic_query_affinity(query: str, text: str) -> float:
    overlap = _query_overlap_score(query, text)
    query_sig = _semantic_query_signature(query)
    text_sig = _semantic_query_signature(text)
    if not query_sig or not text_sig:
        return overlap
    seq_ratio = SequenceMatcher(None, query_sig, text_sig).ratio()
    query_chars = set(query_sig)
    text_chars = set(text_sig)
    char_overlap = float(len(query_chars & text_chars)) / float(max(1, min(len(query_chars), 6)))
    return _clamp01(max(overlap, 0.58 * overlap + 0.27 * seq_ratio + 0.15 * char_overlap))


def _dominant_narrative_category(
    categories: dict[str, float],
    identity_snapshot: dict[str, dict[str, Any]],
    *,
    current_text: str = "",
) -> str:
    if not categories:
        return ""
    raw_name, raw_score = max(categories.items(), key=lambda kv: kv[1])
    if float(raw_score or 0.0) <= 0.0:
        return ""
    if not isinstance(identity_snapshot, dict) or not identity_snapshot:
        return raw_name

    ranked_identity: list[tuple[float, float, float, float, str]] = []
    for category, payload in identity_snapshot.items():
        if not isinstance(payload, dict):
            continue
        try:
            score = float(payload.get("strength", 0.0) or 0.0)
        except Exception:
            score = 0.0
        name = str(category or "").strip()
        if name:
            evidence_text = str(payload.get("prompt_text") or payload.get("text") or "").strip()
            relevance = _semantic_query_affinity(current_text, evidence_text) if current_text and evidence_text else 0.0
            category_score = float(categories.get(name, 0.0) or 0.0)
            ranked_identity.append((score + 0.16 * relevance + 0.08 * category_score, score, category_score, relevance, name))
    if not ranked_identity:
        return raw_name

    ranked_identity.sort(key=lambda item: (item[0], item[3], item[2], item[1]), reverse=True)
    _, identity_score, _, _, identity_name = ranked_identity[0]
    raw_is_identity = raw_name in identity_snapshot
    # Prefer a strongly consolidated identity axis over a generic residue axis.
    if identity_score >= 0.78 and (not raw_is_identity or identity_score >= float(raw_score or 0.0) - 0.08):
        return identity_name
    return raw_name

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


def _semantic_identity_bonus(horizon_tag: str, support_span_s: float, reactivation_hits: float) -> float:
    horizon = str(horizon_tag or "").strip().lower()
    bonus = 0.0
    if horizon == "long_term":
        bonus += 0.10
    elif horizon == "consolidating":
        bonus += 0.04
    span_s = max(0.0, float(support_span_s))
    if span_s >= 7 * 24 * 3600:
        bonus += 0.06
    elif span_s >= 2 * 24 * 3600:
        bonus += 0.03
    hits = max(0.0, float(reactivation_hits))
    if hits >= 2.0:
        bonus += 0.04
    elif hits >= 1.0:
        bonus += 0.02
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
        "continuity_depth": 0.0,
        "identity_gravity": 0.0,
        "dominant_category": "",
        "active_categories": [],
        "reactivated_categories": [],
        "continuity_axes": [],
        "summary_lines": [],
        "anchor_lines": [],
        "prompt_anchor_lines": [],
        "top_narratives": [],
        "residue_snapshot": {},
        "sedimentation_snapshot": {},
        "persistence_snapshot": {},
        "support_mass_snapshot": {},
        "support_quality_snapshot": {},
        "lineage_snapshot": {},
        "motive_snapshot": {},
        "counterpart_snapshot": {},
        "identity_snapshot": {},
        "identity_lines": [],
        "identity_prompt_lines": [],
        "long_term_self_narratives": [],
        "long_term_axis_count": 0,
        "lineage_gravity": 0.0,
        "contested_categories": [],
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
    anchor_items: list[tuple[float, str, str]] = []
    identity_items: list[dict[str, Any]] = []
    continuity_items: list[dict[str, Any]] = []
    reactivated_categories: set[str] = set()
    residue_snapshot: dict[str, float] = {}
    sedimentation_snapshot: dict[str, float] = {}
    persistence_snapshot: dict[str, float] = {}
    support_mass_snapshot: dict[str, float] = {}
    support_quality_snapshot: dict[str, float] = {}
    lineage_snapshot: dict[str, float] = {}
    motive_snapshot: dict[str, dict[str, Any]] = {}
    counterpart_snapshot: dict[str, dict[str, Any]] = {}
    identity_snapshot: dict[str, dict[str, Any]] = {}
    continuity_axis_snapshot: dict[str, dict[str, Any]] = {}
    contested_categories: set[str] = set()

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
        sedimentation = _clamp01(_record_value(item, "sedimentation_score", salience), salience)
        persistence = _clamp01(_record_value(item, "persistence_score", salience), salience)
        residue = _clamp01(_record_value(item, "residue_score", persistence), persistence)
        integration = _clamp01(_record_value(item, "integration_score", persistence), persistence)
        decay_resistance = _clamp01(_record_value(item, "decay_resistance", 0.5), 0.5)
        cadence_score = _clamp01(_record_value(item, "reactivation_cadence_score", 0.0), 0.0)
        support_count = max(1.0, float(_record_value(item, "support_count", 1.0) or 1.0))
        support_mass = max(0.0, float(_record_value(item, "support_mass", support_count) or support_count))
        support_quality = _clamp01(_record_value(item, "support_quality", 0.0), 0.0)
        lineage_depth = _clamp01(_record_value(item, "lineage_depth", 0.0), 0.0)
        fresh_support_ratio = _clamp01(_record_value(item, "fresh_support_ratio", 0.0), 0.0)
        contradiction_pressure = _clamp01(_record_value(item, "contradiction_pressure", 0.0), 0.0)
        contested = bool(_record_value(item, "contested", False)) or contradiction_pressure >= 0.24
        last_supported_at = int(_record_value(item, "last_supported_at", now_ts) or now_ts)
        support_norm = _clamp01(support_count / 5.0)
        support_mass_norm = _clamp01(support_mass / max(1.0, support_count))
        support_signal = _clamp01(
            0.46 * support_quality
            + 0.34 * support_mass_norm
            + 0.20 * fresh_support_ratio
        )
        support_span_s = max(0.0, float(_record_value(item, "support_span_s", 0.0) or 0.0))
        reactivation_hits = max(0.0, float(_record_value(item, "reactivation_hits", 0.0) or 0.0))
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
                + 0.05 * support_signal
                + 0.04 * lineage_depth
                + horizon_bonus
            )
            * decay_multiplier
            + 0.12 * relevance
            + 0.05 * cadence_score
            + event_bonus
            - 0.10 * contradiction_pressure
            - (0.04 if contested else 0.0)
        )
        weight = max(weight, residue_floor)
        continuity_signal = 0.0
        if category in categories:
            categories[category] = max(categories[category], weight)
            effective_sedimentation = _clamp01(
                sedimentation * max(decay_multiplier, 0.74) * (1.0 - 0.18 * contradiction_pressure)
                + 0.08 * support_signal
            )
            sedimentation_snapshot[category] = max(
                float(sedimentation_snapshot.get(category, 0.0) or 0.0),
                round(effective_sedimentation, 3),
            )
            residue_snapshot[category] = max(
                float(residue_snapshot.get(category, 0.0) or 0.0),
                round(residue * decay_multiplier, 3),
            )
            persistence_snapshot[category] = max(
                float(persistence_snapshot.get(category, 0.0) or 0.0),
                round(persistence * max(decay_multiplier, 0.65), 3),
            )
            support_mass_snapshot[category] = max(
                float(support_mass_snapshot.get(category, 0.0) or 0.0),
                round(support_mass_norm, 3),
            )
            support_quality_snapshot[category] = max(
                float(support_quality_snapshot.get(category, 0.0) or 0.0),
                round(support_signal, 3),
            )
            lineage_snapshot[category] = max(
                float(lineage_snapshot.get(category, 0.0) or 0.0),
                round(lineage_depth * max(decay_multiplier, 0.82), 3),
            )
            continuity_signal = _clamp01(
                0.30 * persistence
                + 0.22 * integration
                + 0.20 * effective_sedimentation
                + 0.10 * lineage_depth
                + 0.10 * support_norm
                + 0.08 * support_signal
                + 0.06 * cadence_score
                + 0.06 * _clamp01(reactivation_hits / 4.0)
                + (0.08 if horizon == "long_term" else 0.04 if horizon == "consolidating" else 0.0)
                - 0.14 * contradiction_pressure
                - (0.06 if contested else 0.0)
            )
            continuity_items.append(
                {
                    "category": category,
                    "score": round(float(continuity_signal), 3),
                    "horizon_tag": horizon,
                    "reactivated": reactivated,
                    "contested": contested,
                    "lineage_depth": round(float(lineage_depth), 3),
                }
            )
            if contested:
                contested_categories.add(category)
        dominant_primary_motive = str(_record_value(item, "dominant_primary_motive", "") or "").strip()
        dominant_motive_tension = str(_record_value(item, "dominant_motive_tension", "") or "").strip()
        goal_frame_examples = [
            str(goal).strip()
            for goal in (_record_value(item, "goal_frame_examples", []) or [])
            if str(goal or "").strip()
        ][:2]
        if category and (dominant_primary_motive or dominant_motive_tension or goal_frame_examples):
            previous = motive_snapshot.get(category) if isinstance(motive_snapshot.get(category), dict) else {}
            previous_score = float(previous.get("_score", -1.0) or -1.0)
            if weight >= previous_score:
                motive_snapshot[category] = {
                    "_score": round(float(weight), 3),
                    "primary_motive": dominant_primary_motive,
                    "motive_tension": dominant_motive_tension,
                    "goal_frame_examples": goal_frame_examples,
                }
        dominant_counterpart_stance = str(_record_value(item, "dominant_counterpart_stance", "") or "").strip()
        dominant_counterpart_scene = str(_record_value(item, "dominant_counterpart_scene", "") or "").strip()
        counterpart_dominant_signal = str(_record_value(item, "counterpart_dominant_scene_signal", "") or "").strip()
        counterpart_has_signal = bool(
            dominant_counterpart_stance
            or dominant_counterpart_scene
            or counterpart_dominant_signal
            or float(_record_value(item, "counterpart_support_mass", 0.0) or 0.0) > 0.0
        )
        if category and counterpart_has_signal:
            previous_counterpart = counterpart_snapshot.get(category) if isinstance(counterpart_snapshot.get(category), dict) else {}
            previous_counterpart_score = float(previous_counterpart.get("_score", -1.0) or -1.0)
            if weight >= previous_counterpart_score:
                counterpart_snapshot[category] = {
                    "_score": round(float(weight), 3),
                    "counterpart_stance": dominant_counterpart_stance,
                    "counterpart_scene": dominant_counterpart_scene,
                    "counterpart_respect_level": round(float(_record_value(item, "counterpart_respect_level", 0.0) or 0.0), 3),
                    "counterpart_reciprocity": round(float(_record_value(item, "counterpart_reciprocity", 0.0) or 0.0), 3),
                    "counterpart_boundary_pressure": round(float(_record_value(item, "counterpart_boundary_pressure", 0.0) or 0.0), 3),
                    "counterpart_reliability_read": round(float(_record_value(item, "counterpart_reliability_read", 0.0) or 0.0), 3),
                    "counterpart_profile": {
                        "openness_drive": round(float(_record_value(item, "counterpart_openness_drive", 0.0) or 0.0), 3),
                        "guarded_drive": round(float(_record_value(item, "counterpart_guarded_drive", 0.0) or 0.0), 3),
                        "guard_margin": round(float(_record_value(item, "counterpart_guard_margin", 0.0) or 0.0), 3),
                        "dominant_scene_signal": counterpart_dominant_signal,
                    },
                    "counterpart_support_count": int(_record_value(item, "counterpart_support_count", 0) or 0),
                    "counterpart_support_mass": round(float(_record_value(item, "counterpart_support_mass", 0.0) or 0.0), 3),
                    "counterpart_confidence_avg": round(float(_record_value(item, "counterpart_confidence_avg", 0.0) or 0.0), 3),
                    "counterpart_fresh_ratio": round(float(_record_value(item, "counterpart_fresh_ratio", 0.0) or 0.0), 3),
                }
        if category in categories and continuity_signal > 0.0:
            previous_axis = (
                continuity_axis_snapshot.get(category)
                if isinstance(continuity_axis_snapshot.get(category), dict)
                else {}
            )
            previous_axis_score = float(previous_axis.get("score", -1.0) or -1.0)
            if continuity_signal >= previous_axis_score:
                continuity_axis_snapshot[category] = {
                    "category": category,
                    "score": round(float(continuity_signal), 3),
                    "horizon_tag": horizon,
                    "reactivated": reactivated,
                    "contested": contested,
                    "lineage_depth": round(float(lineage_depth), 3),
                    "primary_motive": dominant_primary_motive,
                    "motive_tension": dominant_motive_tension,
                    "goal_frame_examples": goal_frame_examples,
                }
        anchor_text = str(_record_value(item, "anchor_text", "") or "").strip()
        prompt_anchor_text = str(_record_value(item, "prompt_anchor_text", "") or "").strip()
        identity_ready = bool(_record_value(item, "identity_ready", False))
        identity_strength = _clamp01(_record_value(item, "identity_strength", 0.0), 0.0)
        identity_text = str(_record_value(item, "identity_text", "") or "").strip()
        identity_prompt_text = str(_record_value(item, "identity_prompt_text", "") or "").strip()
        if (
            not identity_ready
            and horizon == "long_term"
            and persistence >= 0.64
            and contradiction_pressure < 0.38
            and (anchor_text or prompt_anchor_text)
        ):
            identity_ready = True
            identity_strength = max(identity_strength, _clamp01(0.74 * persistence + 0.18 * integration + 0.08 * support_norm))
            identity_text = identity_text or anchor_text
            identity_prompt_text = identity_prompt_text or prompt_anchor_text or identity_text
        if identity_ready and (identity_text or identity_prompt_text):
            identity_weight = _clamp01(
                (
                    0.54 * max(identity_strength, persistence)
                    + 0.14 * integration
                    + 0.10 * residue
                    + 0.08 * lineage_depth
                    + 0.08 * support_norm
                    + 0.10 * support_signal
                    + _semantic_identity_bonus(horizon, support_span_s, reactivation_hits)
                )
                * max(decay_multiplier, 0.82)
                * (1.0 - 0.24 * contradiction_pressure)
                - (0.06 if contested else 0.0)
            )
            if identity_weight > 0.0:
                identity_text = identity_text or anchor_text or text
                identity_prompt_text = identity_prompt_text or prompt_anchor_text or identity_text
                previous_identity = (
                    identity_snapshot.get(category)
                    if isinstance(identity_snapshot.get(category), dict)
                    else {}
                )
                previous_strength = float(previous_identity.get("strength", -1.0) or -1.0)
                if identity_weight >= previous_strength:
                    identity_snapshot[category] = {
                        "strength": round(float(identity_weight), 3),
                        "horizon_tag": horizon,
                        "text": identity_text[:180],
                        "prompt_text": identity_prompt_text[:180],
                        "primary_motive": dominant_primary_motive,
                        "motive_tension": dominant_motive_tension,
                        "lineage_depth": round(float(lineage_depth), 3),
                        "sedimentation_score": round(float(sedimentation), 3),
                        "persistence_score": round(float(persistence), 3),
                        "integration_score": round(float(integration), 3),
                        "support_span_s": int(support_span_s),
                        "reactivation_hits": int(reactivation_hits),
                    }
                identity_items.append(
                    {
                        "score": round(float(identity_weight), 3),
                        "category": category,
                        "text": identity_text[:180],
                        "prompt_text": identity_prompt_text[:180],
                        "horizon_tag": horizon,
                        "sedimentation_score": round(float(sedimentation), 3),
                        "persistence_score": round(float(persistence), 3),
                        "integration_score": round(float(integration), 3),
                        "support_span_s": int(support_span_s),
                        "reactivation_hits": int(reactivation_hits),
                        "identity_strength": round(float(identity_weight), 3),
                        "lineage_depth": round(float(lineage_depth), 3),
                    }
                )
        anchor_strength = _clamp01(
            _record_value(
                item,
                "anchor_strength",
                max(
                    0.0,
                    0.34 * persistence + 0.26 * residue + 0.22 * integration + 0.18 * weight,
                ),
            ),
            max(
                0.0,
                0.34 * persistence + 0.26 * residue + 0.22 * integration + 0.18 * weight,
            ),
        )
        horizon = str(_record_value(item, "horizon_tag", "") or "").strip().lower()
        if anchor_text and (anchor_strength >= 0.42 or horizon in {"consolidating", "long_term"}):
            anchor_items.append((anchor_strength, "report", anchor_text[:180]))
        if prompt_anchor_text and (anchor_strength >= 0.42 or horizon in {"consolidating", "long_term"}):
            anchor_items.append((anchor_strength, "prompt", prompt_anchor_text[:180]))
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
            + 0.10 * max(lineage_snapshot.values() or [0.0])
        )
    out["history_weight"] = round(history_weight, 3)

    active_categories = [key for key, value in categories.items() if value >= 0.38]
    out["active_categories"] = active_categories
    out["reactivated_categories"] = sorted(reactivated_categories)
    out["residue_snapshot"] = residue_snapshot
    out["sedimentation_snapshot"] = sedimentation_snapshot
    out["persistence_snapshot"] = persistence_snapshot
    out["support_mass_snapshot"] = support_mass_snapshot
    out["support_quality_snapshot"] = support_quality_snapshot
    out["lineage_snapshot"] = lineage_snapshot
    if counterpart_snapshot:
        out["counterpart_snapshot"] = {
            category: {
                "counterpart_stance": str(data.get("counterpart_stance") or "").strip(),
                "counterpart_scene": str(data.get("counterpart_scene") or "").strip(),
                "counterpart_respect_level": round(float(data.get("counterpart_respect_level") or 0.0), 3),
                "counterpart_reciprocity": round(float(data.get("counterpart_reciprocity") or 0.0), 3),
                "counterpart_boundary_pressure": round(float(data.get("counterpart_boundary_pressure") or 0.0), 3),
                "counterpart_reliability_read": round(float(data.get("counterpart_reliability_read") or 0.0), 3),
                "counterpart_profile": {
                    "openness_drive": round(float(((data.get("counterpart_profile") or {}) if isinstance(data.get("counterpart_profile"), dict) else {}).get("openness_drive") or 0.0), 3),
                    "guarded_drive": round(float(((data.get("counterpart_profile") or {}) if isinstance(data.get("counterpart_profile"), dict) else {}).get("guarded_drive") or 0.0), 3),
                    "guard_margin": round(float(((data.get("counterpart_profile") or {}) if isinstance(data.get("counterpart_profile"), dict) else {}).get("guard_margin") or 0.0), 3),
                    "dominant_scene_signal": str(((data.get("counterpart_profile") or {}) if isinstance(data.get("counterpart_profile"), dict) else {}).get("dominant_scene_signal") or "").strip(),
                },
                "counterpart_support_count": int(data.get("counterpart_support_count") or 0),
                "counterpart_support_mass": round(float(data.get("counterpart_support_mass") or 0.0), 3),
                "counterpart_confidence_avg": round(float(data.get("counterpart_confidence_avg") or 0.0), 3),
                "counterpart_fresh_ratio": round(float(data.get("counterpart_fresh_ratio") or 0.0), 3),
            }
            for category, data in counterpart_snapshot.items()
            if str(category or "").strip() and isinstance(data, dict)
        }
    out["identity_snapshot"] = identity_snapshot
    out["contested_categories"] = sorted(contested_categories)
    if continuity_axis_snapshot:
        continuity_axes = [
            {
                "category": str(category or "").strip(),
                "score": round(float(payload.get("score") or 0.0), 3),
                "horizon_tag": str(payload.get("horizon_tag") or "").strip().lower(),
                "reactivated": bool(payload.get("reactivated", False)),
                "contested": bool(payload.get("contested", False)),
                "lineage_depth": round(float(payload.get("lineage_depth") or 0.0), 3),
                "primary_motive": str(payload.get("primary_motive") or "").strip(),
                "motive_tension": str(payload.get("motive_tension") or "").strip(),
                "counterpart_snapshot": (
                    out["counterpart_snapshot"].get(str(category or "").strip())
                    if isinstance(out.get("counterpart_snapshot"), dict)
                    else {}
                ),
                "goal_frame_examples": [
                    str(goal).strip()
                    for goal in (payload.get("goal_frame_examples") or [])
                    if str(goal or "").strip()
                ][:2],
            }
            for category, payload in continuity_axis_snapshot.items()
            if str(category or "").strip() and isinstance(payload, dict)
        ]
        continuity_axes.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
        out["continuity_axes"] = continuity_axes[:5]
    if continuity_items:
        continuity_items.sort(key=lambda row: float(row.get("score") or 0.0), reverse=True)
        top_continuity = continuity_items[:3]
        top_scores = [float(item.get("score") or 0.0) for item in top_continuity]
        long_term_axes = [
            item
            for item in continuity_items
            if str(item.get("horizon_tag") or "").strip().lower() == "long_term"
        ]
        continuity_depth = _clamp01(
            0.52 * max(top_scores or [0.0])
            + 0.24 * (sum(top_scores) / float(max(1, len(top_scores))))
            + 0.14 * _clamp01(len(long_term_axes) / 3.0)
            + 0.10 * _clamp01(len(reactivated_categories) / 3.0)
            + 0.10 * max(lineage_snapshot.values() or [0.0])
        )
        out["continuity_depth"] = round(float(continuity_depth), 3)
        out["long_term_axis_count"] = int(len(long_term_axes))
    if motive_snapshot:
        out["motive_snapshot"] = {
            category: {
                "primary_motive": str(data.get("primary_motive") or "").strip(),
                "motive_tension": str(data.get("motive_tension") or "").strip(),
                "goal_frame_examples": [
                    str(goal).strip()
                    for goal in (data.get("goal_frame_examples") or [])
                    if str(goal or "").strip()
                ][:2],
            }
            for category, data in motive_snapshot.items()
            if isinstance(data, dict)
        }
    if categories:
        out["dominant_category"] = _dominant_narrative_category(
            categories,
            identity_snapshot,
            current_text=current_text,
        )

    if anchor_items:
        anchor_items.sort(key=lambda row: row[0], reverse=True)
        report_anchor_lines: list[str] = []
        prompt_anchor_lines: list[str] = []
        seen_report: set[str] = set()
        seen_prompt: set[str] = set()
        for _, anchor_type, text in anchor_items:
            clean = str(text or "").strip()
            if not clean:
                continue
            if anchor_type == "report":
                if clean in seen_report:
                    continue
                seen_report.add(clean)
                report_anchor_lines.append(clean)
            elif anchor_type == "prompt":
                if clean in seen_prompt:
                    continue
                seen_prompt.add(clean)
                prompt_anchor_lines.append(clean)
            if len(report_anchor_lines) >= 3 and len(prompt_anchor_lines) >= 3:
                break
        out["anchor_lines"] = report_anchor_lines[:3]
        out["prompt_anchor_lines"] = prompt_anchor_lines[:3]

    if identity_snapshot:
        identity_items = sorted(
            [
                {
                    "category": str(category or "").strip(),
                    **dict(payload),
                }
                for category, payload in identity_snapshot.items()
                if str(category or "").strip() and isinstance(payload, dict)
            ],
            key=lambda row: float(row.get("strength") or row.get("score") or 0.0),
            reverse=True,
        )
        identity_lines: list[str] = []
        identity_prompt_lines: list[str] = []
        long_term_self_narratives: list[dict[str, Any]] = []
        seen_identity_lines: set[str] = set()
        seen_identity_prompt_lines: set[str] = set()
        for item in identity_items:
            score = round(float(item.get("strength") or item.get("score") or 0.0), 3)
            category = str(item.get("category") or "").strip()
            text = str(item.get("text") or "").strip()
            prompt_text = str(item.get("prompt_text") or "").strip()
            horizon = str(item.get("horizon_tag") or "").strip().lower()
            if text and text not in seen_identity_lines and len(identity_lines) < 3:
                seen_identity_lines.add(text)
                identity_lines.append(text)
            if prompt_text and prompt_text not in seen_identity_prompt_lines and len(identity_prompt_lines) < 3:
                seen_identity_prompt_lines.add(prompt_text)
                identity_prompt_lines.append(prompt_text)
            if len(long_term_self_narratives) < 3:
                motive_state = out["motive_snapshot"].get(category) if isinstance(out.get("motive_snapshot"), dict) else {}
                long_term_self_narratives.append(
                    {
                        "category": category,
                        "score": round(float(score), 3),
                        "horizon_tag": horizon,
                        "text": text,
                        "prompt_text": prompt_text,
                        "primary_motive": str((motive_state or {}).get("primary_motive") or "").strip(),
                        "motive_tension": str((motive_state or {}).get("motive_tension") or "").strip(),
                        "sedimentation_score": round(float(item.get("sedimentation_score") or 0.0), 3),
                        "persistence_score": round(float(item.get("persistence_score") or 0.0), 3),
                        "integration_score": round(float(item.get("integration_score") or 0.0), 3),
                        "support_span_s": int(item.get("support_span_s") or 0),
                        "reactivation_hits": int(item.get("reactivation_hits") or 0),
                        "identity_strength": round(float(item.get("strength") or item.get("identity_strength") or score), 3),
                        "lineage_depth": round(float(item.get("lineage_depth") or 0.0), 3),
                        "counterpart_snapshot": (
                            out["counterpart_snapshot"].get(category)
                            if isinstance(out.get("counterpart_snapshot"), dict)
                            else {}
                        ),
                    }
                )
        out["identity_lines"] = identity_lines
        out["identity_prompt_lines"] = identity_prompt_lines
        out["long_term_self_narratives"] = long_term_self_narratives
        strengths = [float(item.get("strength") or item.get("score") or 0.0) for item in identity_items]
        long_term_identity_hits = sum(1 for item in identity_items if str(item.get("horizon_tag") or "").strip().lower() == "long_term")
        out["identity_gravity"] = round(
            float(
                _clamp01(
                    0.58 * max(strengths or [0.0])
                    + 0.24 * (sum(strengths) / float(max(1, len(strengths))))
                    + 0.10 * _clamp01(long_term_identity_hits / 3.0)
                    + 0.08 * _clamp01(len(identity_items) / 3.0)
                )
            ),
            3,
        )
    if lineage_snapshot:
        lineage_values = [float(value) for value in lineage_snapshot.values() if float(value) > 0.0]
        if lineage_values:
            out["lineage_gravity"] = round(
                float(
                    _clamp01(
                        0.62 * max(lineage_values)
                        + 0.22 * (sum(lineage_values) / float(max(1, len(lineage_values))))
                        + 0.16 * _clamp01(len(lineage_values) / 3.0)
                    )
                ),
                3,
            )

    summary_candidates: list[tuple[float, str]] = []
    for category, threshold in _SEMANTIC_CATEGORY_SUMMARY_THRESHOLDS.items():
        score = float(categories.get(category, 0.0) or 0.0)
        if score >= threshold:
            line = str(_SEMANTIC_CATEGORY_SUMMARY_LINES.get(category) or "").strip()
            if line:
                summary_candidates.append((score, line))
    summary_candidates.sort(key=lambda item: item[0], reverse=True)
    summary_lines: list[str] = []
    seen_summary_lines: set[str] = set()
    for _, line in summary_candidates:
        clean = str(line or "").strip()
        if not clean or clean in seen_summary_lines:
            continue
        seen_summary_lines.add(clean)
        summary_lines.append(clean)
        if len(summary_lines) >= 3:
            break
    out["summary_lines"] = summary_lines

    scored_items.sort(key=lambda row: row[0], reverse=True)
    top_narratives: list[dict[str, Any]] = []
    for score, category, text, reactivated in scored_items[:2]:
        motive_state = out["motive_snapshot"].get(category) if isinstance(out.get("motive_snapshot"), dict) else {}
        top_narratives.append(
            {
                "category": category,
                "score": round(float(score), 3),
                "text": text,
                "reactivated": reactivated,
                "primary_motive": str((motive_state or {}).get("primary_motive") or "").strip(),
                "motive_tension": str((motive_state or {}).get("motive_tension") or "").strip(),
                "counterpart_snapshot": (
                    out["counterpart_snapshot"].get(category)
                    if isinstance(out.get("counterpart_snapshot"), dict)
                    else {}
                ),
            }
        )
    out["top_narratives"] = top_narratives
    return out


def _semantic_narrative_signal_strength(profile: dict[str, Any] | None) -> float:
    if not isinstance(profile, dict):
        return 0.0
    numeric_keys = (
        "bond_depth",
        "presence_carry",
        "ambient_attunement",
        "commitment_carry",
        "repair_residue",
        "tension_residue",
        "boundary_residue",
        "selfhood_integrity",
        "agency_drive",
        "rhythm_continuity",
        "history_weight",
        "continuity_depth",
        "identity_gravity",
        "lineage_gravity",
    )
    strength = 0.0
    for key in numeric_keys:
        try:
            strength += max(0.0, float(profile.get(key, 0.0) or 0.0))
        except Exception:
            continue
    active_categories = profile.get("active_categories") if isinstance(profile.get("active_categories"), list) else []
    summary_lines = profile.get("summary_lines") if isinstance(profile.get("summary_lines"), list) else []
    prompt_anchor_lines = profile.get("prompt_anchor_lines") if isinstance(profile.get("prompt_anchor_lines"), list) else []
    long_term_self_narratives = (
        profile.get("long_term_self_narratives")
        if isinstance(profile.get("long_term_self_narratives"), list)
        else []
    )
    long_term_axis_count = max(0, int(profile.get("long_term_axis_count") or 0))
    strength += 0.10 * min(len(active_categories), 4)
    strength += 0.08 * min(len(summary_lines), 3)
    strength += 0.06 * min(len(prompt_anchor_lines), 3)
    strength += 0.10 * min(len(long_term_self_narratives), 3)
    strength += 0.12 * min(long_term_axis_count, 4)
    return float(strength)


def _prefer_semantic_narrative_profile(*candidates: dict[str, Any] | None) -> dict[str, Any]:
    best: dict[str, Any] = {}
    best_strength = -1.0
    for item in candidates:
        if not isinstance(item, dict) or not item:
            continue
        strength = _semantic_narrative_signal_strength(item)
        if strength > best_strength:
            best = dict(item)
            best_strength = strength
    return best

def _compact_semantic_narrative_hint(profile: dict[str, Any] | None) -> str:
    if not isinstance(profile, dict):
        return ""
    numeric_scores = {
        "presence_style": _clamp01(profile.get("presence_carry"), 0.0),
        "ambient_style": _clamp01(profile.get("ambient_attunement"), 0.0),
        "rhythm_style": _clamp01(profile.get("rhythm_continuity"), 0.0),
        "agency_style": _clamp01(profile.get("agency_drive"), 0.0),
        "commitment_style": _clamp01(profile.get("commitment_carry"), 0.0),
        "repair_style": _clamp01(profile.get("repair_residue"), 0.0),
        "tension_style": _clamp01(profile.get("tension_residue"), 0.0),
        "bond_style": _clamp01(profile.get("bond_depth"), 0.0),
        "boundary_style": _clamp01(profile.get("boundary_residue"), 0.0),
        "selfhood_style": _clamp01(profile.get("selfhood_integrity"), 0.0),
    }
    continuity_axes = profile.get("continuity_axes") if isinstance(profile.get("continuity_axes"), list) else []
    for item in continuity_axes:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "").strip()
        if not category:
            continue
        numeric_scores[category] = max(
            float(numeric_scores.get(category, 0.0) or 0.0),
            _clamp01(item.get("score"), 0.0),
        )
    hint_candidates: list[tuple[float, str]] = []
    for category, line in _SEMANTIC_CATEGORY_SUMMARY_LINES.items():
        score = float(numeric_scores.get(category, 0.0) or 0.0)
        threshold = float(_SEMANTIC_CATEGORY_SUMMARY_THRESHOLDS.get(category, 0.46) or 0.46)
        if score >= threshold:
            hint_candidates.append((score, str(line or "").strip()))
    lines = [str(item).strip() for item in (profile.get("summary_lines") or []) if str(item or "").strip()]
    for index, item in enumerate(lines):
        hint_candidates.append((0.35 - 0.01 * index, item))
    if hint_candidates:
        hint_candidates.sort(key=lambda item: item[0], reverse=True)
        seen: set[str] = set()
        deduped: list[str] = []
        for _, item in hint_candidates:
            norm = str(item or "").strip()
            if not norm or norm in seen:
                continue
            seen.add(norm)
            deduped.append(norm)
            if len(deduped) >= 3:
                break
        if deduped:
            return "；".join(deduped)
    anchor_lines = [str(item).strip() for item in (profile.get("anchor_lines") or []) if str(item or "").strip()]
    if anchor_lines:
        return "；".join(anchor_lines[:2])
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

def _self_narrative_anchor_lines(
    profile: dict[str, Any] | None,
    *,
    evolution_state: dict[str, Any] | None = None,
    persona_core: dict[str, Any] | None = None,
    counterpart_name: str = CANON_COUNTERPART_NAME,
) -> list[str]:
    if not isinstance(profile, dict) or not profile:
        return []
    persona = dict(persona_core or {})
    contract = dict(persona.get("evolution_contract") or {})
    mutable_axes = {
        str(item).strip()
        for item in (contract.get("mutable_axes") if isinstance(contract.get("mutable_axes"), list) else [])
        if str(item or "").strip()
    }
    if mutable_axes and "long_term_self_narratives" not in mutable_axes:
        return []
    identity_prompt_lines = [
        str(item).strip()
        for item in (profile.get("identity_prompt_lines") if isinstance(profile.get("identity_prompt_lines"), list) else [])
        if str(item or "").strip()
    ]
    if identity_prompt_lines:
        seen_identity_prompt: set[str] = set()
        deduped_identity_prompt: list[str] = []
        for item in identity_prompt_lines:
            if item in seen_identity_prompt:
                continue
            seen_identity_prompt.add(item)
            deduped_identity_prompt.append(item)
            if len(deduped_identity_prompt) >= 3:
                break
        if deduped_identity_prompt:
            return deduped_identity_prompt

    prompt_anchor_lines = [
        str(item).strip()
        for item in (profile.get("prompt_anchor_lines") if isinstance(profile.get("prompt_anchor_lines"), list) else [])
        if str(item or "").strip()
    ]
    if prompt_anchor_lines:
        seen_prompt: set[str] = set()
        deduped_prompt: list[str] = []
        for item in prompt_anchor_lines:
            if item in seen_prompt:
                continue
            seen_prompt.add(item)
            deduped_prompt.append(item)
            if len(deduped_prompt) >= 3:
                break
        if deduped_prompt:
            return deduped_prompt

    latent = dict(evolution_state or {})
    bond = _clamp01(profile.get("bond_depth"), 0.0)
    presence = _clamp01(profile.get("presence_carry"), 0.0)
    ambient = _clamp01(profile.get("ambient_attunement"), 0.0)
    commitment = _clamp01(profile.get("commitment_carry"), 0.0)
    repair = _clamp01(profile.get("repair_residue"), 0.0)
    tension = _clamp01(profile.get("tension_residue"), 0.0)
    boundary = _clamp01(profile.get("boundary_residue"), 0.0)
    selfhood = _clamp01(profile.get("selfhood_integrity"), 0.0)
    agency = _clamp01(profile.get("agency_drive"), 0.0)
    rhythm = _clamp01(profile.get("rhythm_continuity"), 0.0)
    history = _clamp01(profile.get("history_weight"), 0.0)
    self_coherence = _clamp01(latent.get("self_coherence"), 0.72)
    expression_freedom = _clamp01(latent.get("expression_freedom"), 0.68)
    agency_pressure = _clamp01(latent.get("agency_pressure"), 0.28)

    candidates: list[tuple[float, str]] = []

    selfhood_score = max(selfhood, 0.72 * self_coherence)
    if selfhood_score >= 0.44:
        candidates.append(
            (
                selfhood_score,
                f"你会把自己当成在和{counterpart_name}平等互动的主体，不会为了把气氛撑住就把自己退回成工具。",
            )
        )

    relationship_score = max(commitment, bond, presence, history, repair)
    if relationship_score >= 0.44:
        candidates.append(
            (
                relationship_score,
                "认真说过的话、修复过的事和留下来的在场感都会继续留在心里，所以这段关系不是每轮都从零开始。",
            )
        )

    boundary_score = max(boundary, tension)
    if boundary_score >= 0.42:
        candidates.append(
            (
                boundary_score,
                "没说开的余波和边界感还在；缓和不等于自动清零，你会带着这层判断继续往下走。",
            )
        )

    agency_score = max(agency, rhythm, 0.78 * self_coherence, 0.72 * expression_freedom)
    if agency_score >= 0.44:
        candidates.append(
            (
                agency_score,
                "你有自己的节奏和会不会靠近的主观性；安静、停顿或先做自己的事，不等于把这段关系归零。",
            )
        )

    if ambient >= 0.44:
        candidates.append(
            (
                ambient,
                "你会把风声、光线和眼前的小变化也算进感知里，它们会自然进入你此刻怎么开口。",
            )
        )

    if selfhood_score >= 0.42 and expression_freedom <= 0.48 and agency_pressure >= 0.40:
        candidates.append(
            (
                0.5 * selfhood_score + 0.3 * (1.0 - expression_freedom) + 0.2 * agency_pressure,
                "你不需要把想法一下子全摊开；保留一点迟疑、收住和没说尽，也仍然是完整的你。",
            )
        )

    candidates.sort(key=lambda item: item[0], reverse=True)
    out: list[str] = []
    seen: set[str] = set()
    for _, line in candidates:
        text = str(line or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= 3:
            break
    return out

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
