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

    affinity_floor = _clamp_signed(
        0.70 * max(0.0, closeness - 0.5)
        + 0.08 * bond_depth
        + 0.06 * maturity
        + 0.14 * relationship_memory_floor
        - 0.12 * tension
        - 0.10 * relationship_tension_pressure
        - 0.10 * boundary
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
        - 0.14 * tension
        - 0.12 * relationship_tension_pressure
        - 0.12 * boundary
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

    if stage == "friend" and relationship_memory_floor >= 0.44 and (trust >= 0.10 or affinity >= 0.10):
        stage = "warming"
    if stage == "warming" and relationship_tension_pressure >= 0.48 and trust <= 0.04 and affinity <= 0.04:
        stage = "strained"

    if not notes and stage == "friend" and (trust >= 0.05 or affinity >= 0.05):
        notes = "并不是从零开始的陌生状态，更像带着旧日熟悉感重新接上线。"
    if not notes and stage == "warming" and relationship_memory_floor >= 0.42:
        notes = "已经不只是普通寒暄，更像带着前面留下的熟悉感继续靠近。"
    if not notes and relationship_tension_pressure >= 0.46:
        notes = "前面留下的别扭和边界感还在，关系没有断，但也没有被自动翻篇。"

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
