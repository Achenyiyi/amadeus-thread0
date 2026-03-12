from __future__ import annotations

from typing import Any

from .appraisal import normalize_appraisal_payload
from .schemas import WorldModelState, blend, clamp01


def _relationship_base(relationship: dict[str, Any] | None, key: str) -> float:
    if not isinstance(relationship, dict):
        return 0.0
    return float(relationship.get(key, 0.0) or 0.0)


def build_world_model_state(
    *,
    prev_state: dict[str, Any] | None,
    relationship: dict[str, Any] | None,
    semantic_narrative_profile: dict[str, Any] | None,
    appraisal: dict[str, Any] | None,
    current_event: dict[str, Any] | None,
    science_mode: bool,
    now_ts: int,
) -> dict[str, Any]:
    prev = WorldModelState.from_dict(prev_state)
    narrative = semantic_narrative_profile if isinstance(semantic_narrative_profile, dict) else {}
    app = normalize_appraisal_payload(appraisal)
    salience = app.get("salience") if isinstance(app.get("salience"), dict) else {}
    signals = app.get("signals") if isinstance(app.get("signals"), dict) else {}
    event = current_event if isinstance(current_event, dict) else {}
    event_kind = str(event.get("kind") or "").strip().lower()

    rel_affinity = clamp01(0.5 + 0.18 * _relationship_base(relationship, "affinity_score"), 0.5)
    rel_trust = clamp01(0.5 + 0.18 * _relationship_base(relationship, "trust_score"), 0.5)
    target = WorldModelState(
        relationship_maturity=clamp01(
            0.34
            + 0.22 * rel_affinity
            + 0.22 * rel_trust
            + 0.12 * clamp01(narrative.get("history_weight"), 0.0)
            + 0.10 * clamp01(narrative.get("commitment_carry"), 0.0)
        ),
        bond_depth=clamp01(
            0.18
            + 0.30 * rel_affinity
            + 0.24 * rel_trust
            + 0.20 * clamp01(narrative.get("bond_depth"), 0.0)
            + 0.08 * clamp01(salience.get("companionship"), 0.0)
        ),
        tension_load=clamp01(
            0.16 * clamp01(narrative.get("tension_residue"), 0.0)
            + 0.18 * clamp01(narrative.get("boundary_residue"), 0.0)
            + (0.22 if bool(signals.get("conflict")) else 0.0)
            + (0.12 if bool(signals.get("withdrawal")) else 0.0)
        ),
        repair_load=clamp01(
            0.14 * clamp01(narrative.get("repair_residue"), 0.0)
            + 0.16 * clamp01(narrative.get("commitment_carry"), 0.0)
            + (0.22 if bool(signals.get("repair")) else 0.0)
        ),
        boundary_load=clamp01(
            0.22 * clamp01(narrative.get("boundary_residue"), 0.0)
            + 0.14 * clamp01(narrative.get("selfhood_integrity"), 0.0)
            + (0.16 if str(app.get("selfhood_scene") or "") == "boundary_non_compliance" else 0.0)
        ),
        selfhood_load=clamp01(
            0.24 * clamp01(narrative.get("selfhood_integrity"), 0.0)
            + 0.22 * clamp01(salience.get("selfhood"), 0.0)
            + (0.10 if str(app.get("interaction_frame") or "") == "selfhood" else 0.0)
        ),
        agency_load=clamp01(
            0.24 * clamp01(narrative.get("agency_drive"), 0.0)
            + 0.18 * clamp01(salience.get("companionship"), 0.0)
            + (0.10 if event_kind in {"self_activity_state", "time_idle"} else 0.0)
        ),
        memory_gravity=clamp01(
            0.26 * clamp01(narrative.get("history_weight"), 0.0)
            + 0.22 * clamp01(salience.get("memory"), 0.0)
            + (0.16 if bool(signals.get("memory_salient")) else 0.0)
        ),
        task_pull=clamp01(
            0.22 * clamp01(salience.get("task"), 0.0)
            + (0.22 if science_mode else 0.0)
            + (0.10 if event_kind in {"scheduled_life_due", "scheduled_checkin_due"} else 0.0)
        ),
        companionship_pull=clamp01(
            0.20 * clamp01(salience.get("companionship"), 0.0)
            + 0.16 * clamp01(salience.get("relationship"), 0.0)
            + (0.10 if bool(signals.get("care")) else 0.0)
        ),
        updated_at=now_ts,
    )

    weight = 0.42 if bool(app.get("used")) else 0.24
    out = WorldModelState(
        relationship_maturity=blend(prev.relationship_maturity, target.relationship_maturity, weight),
        bond_depth=blend(prev.bond_depth, target.bond_depth, weight),
        tension_load=blend(prev.tension_load, target.tension_load, weight),
        repair_load=blend(prev.repair_load, target.repair_load, weight),
        boundary_load=blend(prev.boundary_load, target.boundary_load, weight),
        selfhood_load=blend(prev.selfhood_load, target.selfhood_load, weight),
        agency_load=blend(prev.agency_load, target.agency_load, weight),
        memory_gravity=blend(prev.memory_gravity, target.memory_gravity, weight),
        task_pull=blend(prev.task_pull, target.task_pull, weight),
        companionship_pull=blend(prev.companionship_pull, target.companionship_pull, weight),
        updated_at=now_ts,
    )
    return out.to_dict()
