from __future__ import annotations

from typing import Any


def _metric(value: Any, default: float = 0.0) -> float:
    try:
        return round(float(value), 3)
    except Exception:
        return round(float(default), 3)


def _clean_list(values: Any, *, limit: int = 4) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if not text:
            continue
        out.append(text)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _focus_preview(worldline_focus: Any, *, limit: int = 3) -> list[str]:
    if not isinstance(worldline_focus, list):
        return []
    out: list[str] = []
    for item in worldline_focus:
        if not isinstance(item, dict):
            continue
        text = str(item.get("summary") or item.get("text") or item.get("label") or "").strip()
        if not text:
            continue
        out.append(text[:120])
        if len(out) >= max(1, int(limit)):
            break
    return out


def _top_narrative_preview(top_narratives: Any, *, limit: int = 3) -> list[dict[str, Any]]:
    if not isinstance(top_narratives, list):
        return []
    out: list[dict[str, Any]] = []
    for item in top_narratives:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "category": str(item.get("category") or "").strip(),
                "score": _metric(item.get("score"), 0.0),
                "reactivated": bool(item.get("reactivated", False)),
                "text": str(item.get("text") or "").strip()[:120],
            }
        )
        if len(out) >= max(1, int(limit)):
            break
    return out


def build_evolution_cli_summary(
    *,
    relationship: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
    emotion_state: dict[str, Any] | None = None,
    bond_state: dict[str, Any] | None = None,
    counterpart_assessment: dict[str, Any] | None = None,
    behavior_action: dict[str, Any] | None = None,
    interaction_carryover: dict[str, Any] | None = None,
    worldline_focus: list[dict[str, Any]] | None = None,
    reconsolidation_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    relationship = dict(relationship or {})
    semantic = dict(semantic_narrative_profile or {})
    world = dict(world_model_state or {})
    emotion = dict(emotion_state or {})
    bond = dict(bond_state or {})
    counterpart = dict(counterpart_assessment or {})
    behavior = dict(behavior_action or {})
    carryover = dict(interaction_carryover or {})
    recon = dict(reconsolidation_snapshot or {})

    return {
        "relationship": {
            "stage": str(relationship.get("stage") or "").strip(),
            "affinity_score": _metric(relationship.get("affinity_score"), 0.0),
            "trust_score": _metric(relationship.get("trust_score"), 0.0),
            "notes": str(relationship.get("notes") or "").strip(),
        },
        "continuity_vector": {
            "presence": {
                "semantic": _metric(semantic.get("presence_carry"), 0.0),
                "world": _metric(world.get("presence_residue"), 0.0),
            },
            "ambient": {
                "semantic": _metric(semantic.get("ambient_attunement"), 0.0),
                "world": _metric(world.get("ambient_resonance"), 0.0),
            },
            "rhythm": {
                "semantic": _metric(semantic.get("rhythm_continuity"), 0.0),
                "world": _metric(world.get("self_activity_momentum"), 0.0),
            },
        },
        "semantic_continuity": {
            "history_weight": _metric(semantic.get("history_weight"), 0.0),
            "dominant_category": str(semantic.get("dominant_category") or "").strip(),
            "active_categories": _clean_list(semantic.get("active_categories"), limit=6),
            "reactivated_categories": _clean_list(semantic.get("reactivated_categories"), limit=6),
            "summary_lines": _clean_list(semantic.get("summary_lines"), limit=3),
            "top_narratives": _top_narrative_preview(semantic.get("top_narratives"), limit=3),
        },
        "world_dynamics": {
            "bond_depth": _metric(world.get("bond_depth"), 0.0),
            "tension_load": _metric(world.get("tension_load"), 0.0),
            "selfhood_load": _metric(world.get("selfhood_load"), 0.0),
            "agency_load": _metric(world.get("agency_load"), 0.0),
            "memory_gravity": _metric(world.get("memory_gravity"), 0.0),
            "companionship_pull": _metric(world.get("companionship_pull"), 0.0),
            "task_pull": _metric(world.get("task_pull"), 0.0),
        },
        "current_turn": {
            "emotion_label": str(emotion.get("label") or "neutral").strip(),
            "trust": _metric(bond.get("trust"), 0.0),
            "closeness": _metric(bond.get("closeness"), 0.0),
            "hurt": _metric(bond.get("hurt"), 0.0),
            "counterpart_stance": str(counterpart.get("stance") or "").strip(),
            "counterpart_scene": str(counterpart.get("scene") or "").strip(),
            "behavior_mode": str(behavior.get("interaction_mode") or "").strip(),
            "action_target": str(behavior.get("action_target") or "").strip(),
            "carryover_mode": str(carryover.get("carryover_mode") or "").strip(),
            "carryover_strength": _metric(carryover.get("strength"), 0.0),
            "recon_event_kind": str(recon.get("event_kind") or "").strip(),
            "recon_interaction_frame": str(recon.get("interaction_frame") or "").strip(),
        },
        "worldline_focus_preview": _focus_preview(worldline_focus, limit=3),
    }


def build_evolution_summary_line(summary: dict[str, Any] | None) -> str:
    if not isinstance(summary, dict):
        return "-"
    continuity = summary.get("continuity_vector") if isinstance(summary.get("continuity_vector"), dict) else {}
    current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
    world = summary.get("world_dynamics") if isinstance(summary.get("world_dynamics"), dict) else {}

    def _axis_text(name: str) -> str:
        axis = continuity.get(name) if isinstance(continuity.get(name), dict) else {}
        return (
            f"{name}="
            f"{_metric(axis.get('semantic'), 0.0):.3f}/{_metric(axis.get('world'), 0.0):.3f}"
        )

    parts = [
        _axis_text("presence"),
        _axis_text("ambient"),
        _axis_text("rhythm"),
    ]
    mode = str(current_turn.get("behavior_mode") or "").strip()
    if mode:
        parts.append(f"mode={mode}")
    carry_mode = str(current_turn.get("carryover_mode") or "").strip()
    if carry_mode:
        parts.append(f"carry={carry_mode}:{_metric(current_turn.get('carryover_strength'), 0.0):.3f}")
    stance = str(current_turn.get("counterpart_stance") or "").strip()
    if stance:
        parts.append(f"stance={stance}")
    bond_depth = _metric(world.get("bond_depth"), 0.0)
    tension = _metric(world.get("tension_load"), 0.0)
    parts.append(f"bond={bond_depth:.3f}")
    parts.append(f"tension={tension:.3f}")
    return " | ".join(parts)
