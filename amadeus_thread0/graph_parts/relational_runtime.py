from __future__ import annotations

from typing import Any

from ..config import ABLATE_WORLDLINE_MEMORY, CANON_COUNTERPART_NAME
from ..memory_store import MemoryStore
from .common import _clamp01, _clamp_signed
from .postprocess import _looks_like_light_smalltalk
from .retrieval import (
    _commitment_priority,
    _conflict_repair_salience,
    _record_value,
    _relationship_salience,
    _tension_salience,
)


def _relationship_signal_strength(relationship: dict[str, Any] | None) -> float:
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
    stage_bonus = {
        "trusted": 0.28,
        "warming": 0.18,
        "strained": 0.24,
        "friend": 0.0,
        "": 0.0,
    }.get(stage, 0.10)
    notes_bonus = 0.08 if notes else 0.0
    return affinity + trust + stage_bonus + notes_bonus


def _relationship_has_meaningful_signal(relationship: dict[str, Any] | None) -> bool:
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
    return bool(notes or affinity > 0.06 or trust > 0.06 or stage not in {"", "friend"})


def _prefer_relationship_state(*candidates: dict[str, Any] | None) -> dict[str, Any]:
    best: dict[str, Any] = {}
    best_strength = -1.0
    for item in candidates:
        if not isinstance(item, dict) or not item:
            continue
        strength = _relationship_signal_strength(item)
        if strength > best_strength:
            best = dict(item)
            best_strength = strength
    return best


def _prefer_refreshed_relationship_state(
    current_relationship: dict[str, Any] | None,
    refreshed_relationship: dict[str, Any] | None,
) -> dict[str, Any]:
    refreshed = dict(refreshed_relationship or {})
    if _relationship_has_meaningful_signal(refreshed):
        return refreshed
    current = dict(current_relationship or {})
    if _relationship_has_meaningful_signal(current):
        return current
    return _prefer_relationship_state(refreshed, current)


def _relationship_runtime_snapshot(
    *,
    relationship: dict[str, Any] | None,
    bond_state: dict[str, Any] | None,
    world_model_state: dict[str, Any] | None,
    counterpart_assessment: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rel = dict(relationship or {})
    bond = dict(bond_state or {})
    world = dict(world_model_state or {})
    assessment = dict(counterpart_assessment or {})
    semantic = dict(semantic_narrative_profile or {})
    stage = str(rel.get("stage") or "").strip().lower() or "friend"
    notes = str(rel.get("notes") or "").strip()
    try:
        affinity = float(rel.get("affinity_score", 0.0) or 0.0)
    except Exception:
        affinity = 0.0
    try:
        trust = float(rel.get("trust_score", 0.0) or 0.0)
    except Exception:
        trust = 0.0

    closeness = _clamp01(bond.get("closeness"), 0.5)
    bond_trust = _clamp01(bond.get("trust"), 0.5)
    hurt = _clamp01(bond.get("hurt"), 0.0)
    irritation = _clamp01(bond.get("irritation"), 0.0)
    maturity = _clamp01(world.get("relationship_maturity"), 0.0)
    bond_depth = _clamp01(world.get("bond_depth"), 0.0)
    repair_load = _clamp01(world.get("repair_load"), 0.0)
    tension = _clamp01(world.get("tension_load"), 0.0)
    semantic_history = _clamp01(semantic.get("history_weight"), 0.0)
    semantic_bond = _clamp01(semantic.get("bond_depth"), 0.0)
    semantic_presence = _clamp01(semantic.get("presence_carry"), 0.0)
    semantic_commitment = _clamp01(semantic.get("commitment_carry"), 0.0)
    semantic_repair = _clamp01(semantic.get("repair_residue"), 0.0)
    semantic_tension = _clamp01(semantic.get("tension_residue"), 0.0)
    semantic_boundary = _clamp01(semantic.get("boundary_residue"), 0.0)
    counterpart_pressures = _counterpart_relationship_pressures(assessment)
    boundary = max(
        _clamp01(world.get("boundary_load"), 0.0),
        _clamp01(assessment.get("boundary_pressure"), 0.0),
    )
    relationship_memory_floor = _clamp01(
        0.28 * semantic_bond
        + 0.20 * semantic_presence
        + 0.18 * semantic_commitment
        + 0.18 * semantic_history
        + 0.16 * semantic_repair
    )
    relationship_tension_pressure = _clamp01(0.58 * semantic_tension + 0.42 * semantic_boundary)
    affinity_counterpart_support = float(counterpart_pressures.get("affinity_support", 0.0) or 0.0)
    trust_counterpart_support = float(counterpart_pressures.get("trust_support", 0.0) or 0.0)
    guarded_counterpart_pressure = float(counterpart_pressures.get("guarded_pressure", 0.0) or 0.0)
    unstable_counterpart_pressure = float(counterpart_pressures.get("instability_pressure", 0.0) or 0.0)
    positive_counterpart_signal = float(counterpart_pressures.get("positive_signal", 0.0) or 0.0)

    affinity_floor = _clamp_signed(
        0.70 * max(0.0, closeness - 0.5)
        + 0.08 * bond_depth
        + 0.06 * maturity
        + 0.14 * relationship_memory_floor
        + 0.28 * affinity_counterpart_support
        - 0.12 * tension
        - 0.10 * relationship_tension_pressure
        - 0.10 * boundary
        - 0.04 * guarded_counterpart_pressure
        - 0.03 * unstable_counterpart_pressure
        - 0.10 * hurt
        - 0.06 * irritation,
        -1.5,
        1.5,
        0.0,
    )
    trust_floor = _clamp_signed(
        0.72 * max(0.0, bond_trust - 0.5)
        + 0.08 * maturity
        + 0.06 * repair_load
        + 0.10 * relationship_memory_floor
        + 0.06 * max(semantic_commitment, semantic_repair)
        + 0.22 * trust_counterpart_support
        - 0.14 * tension
        - 0.12 * relationship_tension_pressure
        - 0.12 * boundary
        - 0.10 * guarded_counterpart_pressure
        - 0.14 * unstable_counterpart_pressure
        - 0.12 * hurt
        - 0.08 * irritation,
        -1.5,
        1.5,
        0.0,
    )

    if trust <= 0.06:
        trust = max(trust, trust_floor)
    if affinity <= 0.06:
        affinity = max(affinity, affinity_floor)
    if trust < -0.06:
        trust = min(trust, trust_floor)
    if affinity < -0.06:
        affinity = min(affinity, affinity_floor)

    if trust <= -0.20 or affinity <= -0.20:
        stage = "strained"
    elif trust >= 0.45 and affinity >= 0.45:
        stage = "trusted"
    elif stage == "trusted":
        stage = "trusted"
    elif stage == "warming" or trust >= 0.18 or affinity >= 0.18:
        stage = "warming"
    else:
        stage = "friend"

    if stage == "friend" and relationship_memory_floor >= 0.44 and (trust >= 0.09 or affinity >= 0.09):
        stage = "warming"
    if (
        stage == "friend"
        and positive_counterpart_signal >= 0.22
        and guarded_counterpart_pressure <= 0.18
        and unstable_counterpart_pressure <= 0.16
        and (trust >= 0.06 or affinity >= 0.06)
    ):
        stage = "warming"
    if stage == "warming" and relationship_tension_pressure >= 0.48 and trust <= 0.04 and affinity <= 0.04:
        stage = "strained"

    if not notes and stage == "friend" and (trust >= 0.05 or affinity >= 0.05):
        notes = "并不是从零开始的陌生状态，更像带着旧日熟悉感重新接上线。"
    if not notes and stage == "warming" and relationship_memory_floor >= 0.42:
        notes = "已经不只是普通寒暄，更像带着前面留下的熟悉感继续靠近。"
    if (
        not notes
        and stage == "warming"
        and positive_counterpart_signal >= 0.22
        and guarded_counterpart_pressure <= 0.18
    ):
        notes = "不只是记住了彼此，这次互动里也能感觉到尊重和配合感，关系在自然变稳。"
    if not notes and relationship_tension_pressure >= 0.46:
        notes = "前面留下的别扭和边界感还在，关系没有断，但也没有被自动翻篇。"
    if (
        not notes
        and unstable_counterpart_pressure >= 0.12
        and boundary < 0.24
    ):
        notes = "不一定是在强烈设防，但可靠感和互相接得住的感觉还没完全立住，所以关系还得慢一点。"

    return {
        "stage": stage,
        "notes": notes,
        "affinity_score": round(float(affinity), 3),
        "trust_score": round(float(trust), 3),
        "derived": bool(rel.get("derived", True)),
    }


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


def _counterpart_assessment_profile(
    assessment: dict[str, Any] | None,
) -> dict[str, Any]:
    item = assessment if isinstance(assessment, dict) else {}
    raw_profile = item.get("assessment_profile") if isinstance(item.get("assessment_profile"), dict) else {}
    stance = str(item.get("stance") or "").strip().lower()
    scene = str(item.get("scene") or "").strip().lower()
    respect = _clamp01(item.get("respect_level"), 0.5)
    reciprocity = _clamp01(item.get("reciprocity"), 0.5)
    pressure = _clamp01(item.get("boundary_pressure"), 0.1)
    reliability = _clamp01(item.get("reliability_read"), 0.5)

    derived_scene_strengths = {
        "care": _clamp01(
            (0.46 if scene == "care_bid" else 0.0)
            + 0.24 * respect
            + 0.20 * reciprocity
            + 0.12 * reliability
            - 0.10 * pressure
        ),
        "repair": _clamp01(
            (0.48 if scene == "repair_attempt" else 0.0)
            + 0.22 * reliability
            + 0.18 * respect
            + 0.08 * reciprocity
            - 0.10 * pressure
        ),
        "friction": _clamp01(
            (0.52 if scene in {"friction", "relationship_degradation", "boundary_non_compliance"} else 0.0)
            + 0.30 * pressure
            + 0.10 * _clamp01(1.0 - respect, 0.0)
            + 0.08 * _clamp01(1.0 - reliability, 0.0)
        ),
        "selfhood": _clamp01(
            (0.48 if scene in {"equality_not_servitude", "value_conflict_depth"} else 0.0)
            + 0.18 * pressure
            + 0.08 * _clamp01(1.0 - reciprocity, 0.0)
        ),
        "busy": _clamp01(
            (0.50 if scene == "busy_not_disrespectful" else 0.0)
            + 0.18 * reliability
            + 0.14 * respect
            + 0.10 * _clamp01(1.0 - pressure, 0.0)
        ),
    }
    raw_scene_strengths = raw_profile.get("scene_strengths") if isinstance(raw_profile.get("scene_strengths"), dict) else {}
    scene_strengths = {
        name: _clamp01(raw_scene_strengths.get(name), default)
        for name, default in derived_scene_strengths.items()
    }
    openness_drive = _clamp01(
        raw_profile.get("openness_drive"),
        0.28 * respect + 0.28 * reciprocity + 0.24 * reliability + 0.20 * _clamp01(1.0 - pressure, 0.0),
    )
    guarded_drive = _clamp01(
        raw_profile.get("guarded_drive"),
        0.50 * pressure
        + 0.18 * _clamp01(1.0 - respect, 0.0)
        + 0.18 * _clamp01(1.0 - reliability, 0.0)
        + 0.14 * _clamp01(1.0 - reciprocity, 0.0),
    )
    if stance == "guarded":
        guarded_drive = max(guarded_drive, 0.66)
    elif stance == "watchful":
        guarded_drive = max(guarded_drive, 0.46)
    if scene == "care_bid":
        openness_drive = max(openness_drive, 0.62)
    elif scene == "repair_attempt":
        scene_strengths["repair"] = max(scene_strengths["repair"], 0.62)
    elif scene in {"friction", "relationship_degradation", "boundary_non_compliance"}:
        scene_strengths["friction"] = max(scene_strengths["friction"], 0.62)
    elif scene in {"equality_not_servitude", "value_conflict_depth"}:
        scene_strengths["selfhood"] = max(scene_strengths["selfhood"], 0.62)
    elif scene == "busy_not_disrespectful":
        scene_strengths["busy"] = max(scene_strengths["busy"], 0.62)

    dominant_scene_signal = str(raw_profile.get("dominant_scene_signal") or "").strip().lower()
    if dominant_scene_signal not in scene_strengths:
        ranked_scene_signals = sorted(scene_strengths.items(), key=lambda item: (-item[1], item[0]))
        if ranked_scene_signals and ranked_scene_signals[0][1] >= 0.05:
            dominant_scene_signal = ranked_scene_signals[0][0]
        elif scene:
            dominant_scene_signal = scene
        else:
            dominant_scene_signal = ""

    guard_margin = _clamp_signed(
        raw_profile.get("guard_margin"),
        guarded_drive - openness_drive,
    )
    normalized = {
        "openness_drive": round(openness_drive, 3),
        "guarded_drive": round(guarded_drive, 3),
        "guard_margin": round(guard_margin, 3),
        "dominant_scene_signal": dominant_scene_signal,
        "scene_strengths": {name: round(score, 3) for name, score in scene_strengths.items()},
    }
    if any(
        (
            normalized["openness_drive"] > 0.0,
            normalized["guarded_drive"] > 0.0,
            abs(normalized["guard_margin"]) > 0.0,
            normalized["dominant_scene_signal"],
            any(score > 0.0 for score in normalized["scene_strengths"].values()),
        )
    ):
        return normalized
    return {}


def _counterpart_relationship_pressures(
    assessment: dict[str, Any] | None,
) -> dict[str, float]:
    item = assessment if isinstance(assessment, dict) else {}
    profile = _counterpart_assessment_profile(item)
    respect = _clamp01(item.get("respect_level"), 0.5)
    reciprocity = _clamp01(item.get("reciprocity"), 0.5)
    reliability = _clamp01(item.get("reliability_read"), 0.5)
    boundary = _clamp01(item.get("boundary_pressure"), 0.0)
    openness_drive = _clamp01(profile.get("openness_drive"), 0.0)
    guarded_drive = _clamp01(profile.get("guarded_drive"), 0.0)
    guard_margin = max(0.0, _clamp_signed(profile.get("guard_margin"), 0.0))
    scene_strengths = profile.get("scene_strengths") if isinstance(profile.get("scene_strengths"), dict) else {}
    care_signal = _clamp01(scene_strengths.get("care"), 0.0)
    repair_signal = _clamp01(scene_strengths.get("repair"), 0.0)
    friction_signal = _clamp01(scene_strengths.get("friction"), 0.0)
    busy_signal = _clamp01(scene_strengths.get("busy"), 0.0)
    selfhood_signal = _clamp01(scene_strengths.get("selfhood"), 0.0)

    affinity_support = _clamp01(
        0.44 * max(0.0, respect - 0.5)
        + 0.44 * max(0.0, reciprocity - 0.5)
        + 0.24 * max(0.0, openness_drive - 0.58)
        + 0.08 * max(0.0, care_signal - 0.55)
    )
    trust_support = _clamp01(
        0.52 * max(0.0, reliability - 0.5)
        + 0.30 * max(0.0, respect - 0.5)
        + 0.18 * max(0.0, reciprocity - 0.5)
        + 0.08 * max(0.0, busy_signal - 0.55)
        + 0.06 * max(0.0, repair_signal - 0.55)
    )
    guarded_pressure = _clamp01(
        0.36 * boundary
        + 0.24 * max(0.0, guarded_drive - 0.40)
        + 0.20 * guard_margin
        + 0.12 * max(0.0, friction_signal - 0.55)
        + 0.08 * max(0.0, selfhood_signal - 0.55)
    )
    instability_pressure = _clamp01(
        0.36 * max(0.0, 0.5 - reliability)
        + 0.24 * max(0.0, 0.5 - respect)
        + 0.20 * max(0.0, 0.5 - reciprocity)
        + 0.10 * max(0.0, friction_signal - 0.55)
        + 0.10 * guard_margin
    )
    positive_signal = _clamp01(max(affinity_support, trust_support))
    return {
        "affinity_support": round(affinity_support, 3),
        "trust_support": round(trust_support, 3),
        "guarded_pressure": round(guarded_pressure, 3),
        "instability_pressure": round(instability_pressure, 3),
        "positive_signal": round(positive_signal, 3),
    }


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
    if scene == "repair_attempt":
        if stance in {"guarded", "watchful"} or pressure >= 0.28:
            return f"你看得出{counterpart_name}是在认真补救，但这不等于现在就能当作已经翻篇。"
        return f"你判断{counterpart_name}这次是在认真修补，不是随口敷衍过去。"
    if scene == "care_bid":
        if respect >= 0.62 and reciprocity >= 0.58:
            return f"你觉得{counterpart_name}这句是在认真靠近你，不是普通客套。"
        return f"你会把{counterpart_name}这次开口当成一次真实靠近，而不是流程化回应。"
    if scene in {"relationship_degradation", "boundary_non_compliance", "friction"}:
        return f"你判断和{counterpart_name}之间那点摩擦还在，不会把这轮轻易读成已经没事。"
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
