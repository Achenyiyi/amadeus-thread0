from __future__ import annotations

from typing import Any

from .appraisal import normalize_appraisal_payload
from .motive import semantic_motive_vector
from .schemas import WorldModelState, blend, clamp01


def _relationship_base(relationship: dict[str, Any] | None, key: str) -> float:
    if not isinstance(relationship, dict):
        return 0.0
    return float(relationship.get(key, 0.0) or 0.0)


def _event_tags(event: dict[str, Any] | None) -> set[str]:
    if not isinstance(event, dict):
        return set()
    return {
        str(item).strip().lower()
        for item in (event.get("tags") if isinstance(event.get("tags"), list) else [])
        if str(item or "").strip()
    }


def _lineage_level(snapshot: dict[str, Any], *categories: str) -> float:
    if not isinstance(snapshot, dict) or not categories:
        return 0.0
    return clamp01(max(clamp01(snapshot.get(category), 0.0) for category in categories), 0.0)


def _residue_targets(
    *,
    event_kind: str,
    event_tags: set[str],
    salience: dict[str, Any],
    signals: dict[str, Any],
    science_mode: bool,
) -> tuple[float, float, float]:
    companionship_salience = clamp01(salience.get("companionship"), 0.0)
    relationship_salience = clamp01(salience.get("relationship"), 0.0)
    memory_salience = clamp01(salience.get("memory"), 0.0)
    task_salience = clamp01(salience.get("task"), 0.0)

    presence = 0.0
    ambient = 0.0
    self_activity = 0.0

    if event_kind == "gesture_signal":
        presence += 0.64
    elif event_kind == "ambient_shift":
        ambient += 0.68
        presence += 0.10
    elif event_kind == "scene_observation":
        ambient += 0.50 if "care_opportunity" in event_tags else 0.60
        presence += 0.18 if "care_opportunity" in event_tags else 0.08
    elif event_kind == "time_idle":
        self_activity += 0.48 if {"respect_space", "stale_window"} & event_tags else 0.34
        ambient += 0.10 if "ambient" in event_tags else 0.0
        presence += 0.14
    elif event_kind == "self_activity_state":
        if {"deep_focus", "own_task"} & event_tags:
            self_activity += 0.74
        elif {"break_window", "small_opening", "reapproach"} & event_tags:
            self_activity += 0.52
            presence += 0.20
        else:
            self_activity += 0.62
    elif event_kind in {"scheduled_checkin_due", "scheduled_life_due"}:
        presence += 0.14 if {"shared_activity_window", "offer_window", "presence_ping"} & event_tags else 0.06
    elif event_kind == "user_utterance":
        presence += 0.20 * companionship_salience + 0.14 * relationship_salience
        ambient += 0.10 * memory_salience
        self_activity += 0.06 * task_salience + (0.04 if science_mode else 0.0)

    if bool(signals.get("care")):
        presence += 0.12
    if bool(signals.get("repair")):
        presence += 0.08
    if bool(signals.get("memory_salient")):
        ambient += 0.10
        presence += 0.04
    if bool(signals.get("conflict")) or bool(signals.get("withdrawal")):
        presence -= 0.14
        ambient -= 0.04
        self_activity += 0.06

    return (
        clamp01(presence, 0.0),
        clamp01(ambient, 0.0),
        clamp01(self_activity, 0.0),
    )


def _residue_decays(
    *,
    event_kind: str,
    salience: dict[str, Any],
) -> tuple[float, float, float]:
    companionship_salience = clamp01(salience.get("companionship"), 0.0)
    relationship_salience = clamp01(salience.get("relationship"), 0.0)
    if event_kind == "user_utterance":
        presence_decay = 0.78
        ambient_decay = 0.86
        self_decay = max(0.62, 0.92 - 0.10 * companionship_salience - 0.08 * relationship_salience)
    elif event_kind in {"gesture_signal", "ambient_shift", "scene_observation"}:
        presence_decay = 0.84
        ambient_decay = 0.88
        self_decay = 0.92
    elif event_kind in {"self_activity_state", "time_idle"}:
        presence_decay = 0.78
        ambient_decay = 0.86
        self_decay = 0.94
    else:
        presence_decay = 0.76
        ambient_decay = 0.84
        self_decay = 0.90
    return presence_decay, ambient_decay, self_decay


def _residue_weights(event_kind: str) -> tuple[float, float, float]:
    if event_kind == "gesture_signal":
        return 0.86, 0.24, 0.20
    if event_kind in {"ambient_shift", "scene_observation"}:
        return 0.54, 0.84, 0.24
    if event_kind in {"self_activity_state", "time_idle"}:
        return 0.44, 0.28, 0.82
    if event_kind == "user_utterance":
        return 0.30, 0.24, 0.24
    return 0.40, 0.32, 0.30


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
    residue_snapshot = narrative.get("residue_snapshot") if isinstance(narrative.get("residue_snapshot"), dict) else {}
    persistence_snapshot = narrative.get("persistence_snapshot") if isinstance(narrative.get("persistence_snapshot"), dict) else {}
    lineage_snapshot = narrative.get("lineage_snapshot") if isinstance(narrative.get("lineage_snapshot"), dict) else {}
    reactivated_categories = {
        str(item).strip()
        for item in (narrative.get("reactivated_categories") if isinstance(narrative.get("reactivated_categories"), list) else [])
        if str(item or "").strip()
    }
    app = normalize_appraisal_payload(appraisal)
    salience = app.get("salience") if isinstance(app.get("salience"), dict) else {}
    signals = app.get("signals") if isinstance(app.get("signals"), dict) else {}
    event = current_event if isinstance(current_event, dict) else {}
    event_kind = str(event.get("kind") or "").strip().lower()
    event_tags = _event_tags(event)

    presence_target, ambient_target, self_activity_target = _residue_targets(
        event_kind=event_kind,
        event_tags=event_tags,
        salience=salience,
        signals=signals,
        science_mode=science_mode,
    )

    rel_affinity = clamp01(0.5 + 0.18 * _relationship_base(relationship, "affinity_score"), 0.5)
    rel_trust = clamp01(0.5 + 0.18 * _relationship_base(relationship, "trust_score"), 0.5)
    max_persistence = max((clamp01(v, 0.0) for v in persistence_snapshot.values()), default=0.0)
    max_residue = max((clamp01(v, 0.0) for v in residue_snapshot.values()), default=0.0)
    reactivation_charge = clamp01(len(reactivated_categories) / 3.0, 0.0)
    presence_carry = clamp01(narrative.get("presence_carry"), 0.0)
    ambient_attunement = clamp01(narrative.get("ambient_attunement"), 0.0)
    rhythm_continuity = clamp01(narrative.get("rhythm_continuity"), 0.0)
    agency_drive = clamp01(narrative.get("agency_drive"), 0.0)
    narrative_bond_depth = clamp01(narrative.get("bond_depth"), 0.0)
    history_weight = clamp01(narrative.get("history_weight"), 0.0)
    continuity_depth = clamp01(narrative.get("continuity_depth"), 0.0)
    identity_gravity = clamp01(narrative.get("identity_gravity"), 0.0)
    lineage_gravity = clamp01(narrative.get("lineage_gravity"), 0.0)
    contact_lineage = _lineage_level(lineage_snapshot, "bond_style", "presence_style", "commitment_style", "repair_style")
    repair_lineage = _lineage_level(lineage_snapshot, "repair_style", "bond_style", "commitment_style")
    boundary_lineage = _lineage_level(lineage_snapshot, "boundary_style", "selfhood_style")
    selfhood_lineage = _lineage_level(lineage_snapshot, "selfhood_style", "agency_style", "rhythm_style")
    agency_lineage = _lineage_level(lineage_snapshot, "agency_style", "rhythm_style", "selfhood_style")
    motive_vector = semantic_motive_vector(narrative)
    motive_boundary = clamp01(motive_vector.get("boundary_pull"), 0.0)
    motive_self_rhythm = clamp01(motive_vector.get("self_rhythm_pull"), 0.0)
    motive_continuity = clamp01(motive_vector.get("continuity_pull"), 0.0)
    motive_memory = clamp01(motive_vector.get("memory_pull"), 0.0)
    motive_support = clamp01(motive_vector.get("support_pull"), 0.0)
    motive_shared_window = clamp01(motive_vector.get("shared_window_pull"), 0.0)
    presence_persistence = clamp01(persistence_snapshot.get("presence_style"), 0.0)
    ambient_persistence = clamp01(persistence_snapshot.get("ambient_style"), 0.0)
    rhythm_persistence = clamp01(persistence_snapshot.get("rhythm_style"), 0.0)
    presence_residue_hint = clamp01(residue_snapshot.get("presence_style"), 0.0)
    ambient_residue_hint = clamp01(residue_snapshot.get("ambient_style"), 0.0)
    rhythm_residue_hint = clamp01(residue_snapshot.get("rhythm_style"), 0.0)

    # Long-term semantic narratives should bias the short-term world residue,
    # but only gently: they provide a floor and a small target shift rather than
    # hard-setting the next behavior.
    presence_floor = clamp01(
        0.10 * presence_carry
        + 0.08 * presence_persistence
        + 0.06 * presence_residue_hint
        + 0.05 * continuity_depth
        + 0.04 * narrative_bond_depth
        + 0.04 * motive_continuity
        + 0.03 * motive_support
        + 0.02 * motive_shared_window
        + 0.04 * contact_lineage
        + 0.02 * lineage_gravity
        - 0.04 * motive_boundary
        + (0.04 if "presence_style" in reactivated_categories else 0.0)
    )
    ambient_floor = clamp01(
        0.10 * ambient_attunement
        + 0.08 * ambient_persistence
        + 0.06 * ambient_residue_hint
        + 0.04 * continuity_depth
        + 0.04 * history_weight
        + 0.05 * motive_memory
        + 0.02 * motive_continuity
        + 0.03 * lineage_gravity
        + (0.04 if "ambient_style" in reactivated_categories else 0.0)
    )
    self_activity_floor = clamp01(
        0.12 * rhythm_continuity
        + 0.08 * rhythm_persistence
        + 0.06 * rhythm_residue_hint
        + 0.04 * continuity_depth
        + 0.05 * agency_drive
        + 0.05 * identity_gravity
        + 0.08 * motive_self_rhythm
        + 0.05 * agency_lineage
        + 0.03 * selfhood_lineage
        + 0.02 * motive_boundary
        + (0.04 if "rhythm_style" in reactivated_categories else 0.0)
    )
    presence_target = clamp01(
        presence_target
        + 0.10 * presence_carry
        + 0.05 * presence_persistence
        + 0.03 * presence_residue_hint
        + 0.04 * continuity_depth
        + 0.06 * motive_continuity
        + 0.04 * motive_support
        + 0.03 * motive_shared_window
        + 0.05 * contact_lineage
        + 0.02 * lineage_gravity
        - 0.06 * motive_boundary
    )
    ambient_target = clamp01(
        ambient_target
        + 0.10 * ambient_attunement
        + 0.05 * ambient_persistence
        + 0.03 * ambient_residue_hint
        + 0.03 * continuity_depth
        + 0.06 * motive_memory
        + 0.02 * motive_continuity
        + 0.03 * lineage_gravity
    )
    self_activity_target = clamp01(
        self_activity_target
        + 0.12 * rhythm_continuity
        + 0.05 * rhythm_persistence
        + 0.03 * rhythm_residue_hint
        + 0.05 * continuity_depth
        + 0.04 * agency_drive
        + 0.05 * identity_gravity
        + 0.10 * motive_self_rhythm
        + 0.06 * agency_lineage
        + 0.03 * selfhood_lineage
        + 0.04 * motive_boundary
    )

    target = WorldModelState(
        relationship_maturity=clamp01(
            0.34
            + 0.22 * rel_affinity
            + 0.22 * rel_trust
            + 0.12 * clamp01(narrative.get("history_weight"), 0.0)
            + 0.08 * continuity_depth
            + 0.10 * clamp01(narrative.get("commitment_carry"), 0.0)
            + 0.08 * max_persistence
            + 0.05 * contact_lineage
            + 0.03 * lineage_gravity
            + 0.05 * motive_continuity
            + 0.03 * motive_memory
        ),
        bond_depth=clamp01(
            0.18
            + 0.30 * rel_affinity
            + 0.24 * rel_trust
            + 0.20 * clamp01(narrative.get("bond_depth"), 0.0)
            + 0.08 * clamp01(salience.get("companionship"), 0.0)
            + 0.08 * clamp01(residue_snapshot.get("bond_style"), 0.0)
            + 0.05 * continuity_depth
            + 0.06 * presence_target
            + 0.05 * contact_lineage
            + 0.03 * motive_continuity
            + 0.03 * motive_support
            + (0.08 if "bond_style" in reactivated_categories else 0.0)
        ),
        tension_load=clamp01(
            0.16 * clamp01(narrative.get("tension_residue"), 0.0)
            + 0.18 * clamp01(narrative.get("boundary_residue"), 0.0)
            + 0.10 * clamp01(residue_snapshot.get("tension_style"), 0.0)
            + (0.22 if bool(signals.get("conflict")) else 0.0)
            + (0.12 if bool(signals.get("withdrawal")) else 0.0)
            + (0.08 if "tension_style" in reactivated_categories else 0.0)
        ),
        repair_load=clamp01(
            0.14 * clamp01(narrative.get("repair_residue"), 0.0)
            + 0.16 * clamp01(narrative.get("commitment_carry"), 0.0)
            + 0.10 * clamp01(residue_snapshot.get("repair_style"), 0.0)
            + 0.06 * repair_lineage
            + (0.22 if bool(signals.get("repair")) else 0.0)
            + (0.08 if "repair_style" in reactivated_categories else 0.0)
        ),
        boundary_load=clamp01(
            0.22 * clamp01(narrative.get("boundary_residue"), 0.0)
            + 0.14 * clamp01(narrative.get("selfhood_integrity"), 0.0)
            + 0.10 * clamp01(residue_snapshot.get("boundary_style"), 0.0)
            + 0.10 * identity_gravity
            + 0.08 * boundary_lineage
            + 0.04 * selfhood_lineage
            + 0.16 * motive_boundary
            + (0.16 if str(app.get("selfhood_scene") or "") == "boundary_non_compliance" else 0.0)
            + (0.08 if "boundary_style" in reactivated_categories else 0.0)
        ),
        selfhood_load=clamp01(
            0.24 * clamp01(narrative.get("selfhood_integrity"), 0.0)
            + 0.22 * clamp01(salience.get("selfhood"), 0.0)
            + 0.10 * clamp01(persistence_snapshot.get("selfhood_style"), 0.0)
            + 0.12 * identity_gravity
            + 0.04 * continuity_depth
            + 0.06 * self_activity_target
            + 0.08 * selfhood_lineage
            + 0.08 * motive_boundary
            + (0.10 if str(app.get("interaction_frame") or "") == "selfhood" else 0.0)
            + (0.08 if "selfhood_style" in reactivated_categories else 0.0)
        ),
        agency_load=clamp01(
            0.24 * clamp01(narrative.get("agency_drive"), 0.0)
            + 0.18 * clamp01(salience.get("companionship"), 0.0)
            + 0.10 * clamp01(persistence_snapshot.get("agency_style"), 0.0)
            + 0.08 * identity_gravity
            + 0.04 * continuity_depth
            + 0.16 * self_activity_target
            + 0.08 * agency_lineage
            + 0.14 * motive_self_rhythm
            + 0.05 * motive_shared_window
            + (0.10 if event_kind in {"self_activity_state", "time_idle"} else 0.0)
            + (0.06 if "agency_style" in reactivated_categories else 0.0)
        ),
        memory_gravity=clamp01(
            0.26 * clamp01(narrative.get("history_weight"), 0.0)
            + 0.22 * clamp01(salience.get("memory"), 0.0)
            + 0.14 * max_persistence
            + 0.10 * max_residue
            + 0.08 * continuity_depth
            + 0.04 * ambient_target
            + 0.04 * lineage_gravity
            + 0.14 * motive_memory
            + 0.04 * motive_continuity
            + (0.16 if bool(signals.get("memory_salient")) else 0.0)
            + 0.06 * reactivation_charge
        ),
        task_pull=clamp01(
            0.22 * clamp01(salience.get("task"), 0.0)
            + 0.10 * self_activity_target
            + (0.22 if science_mode else 0.0)
            + (0.10 if event_kind in {"scheduled_life_due", "scheduled_checkin_due"} else 0.0)
        ),
        companionship_pull=clamp01(
            0.20 * clamp01(salience.get("companionship"), 0.0)
            + 0.16 * clamp01(salience.get("relationship"), 0.0)
            + 0.10 * clamp01(residue_snapshot.get("bond_style"), 0.0)
            + 0.05 * continuity_depth
            + 0.12 * presence_target
            + 0.06 * ambient_target
            + 0.06 * contact_lineage
            + 0.10 * motive_continuity
            + 0.10 * motive_support
            + 0.10 * motive_shared_window
            - 0.10 * motive_boundary
            + (0.10 if bool(signals.get("care")) else 0.0)
            + (0.08 if "bond_style" in reactivated_categories or "repair_style" in reactivated_categories else 0.0)
        ),
        updated_at=now_ts,
    )

    weight = 0.42 if bool(app.get("used")) else 0.24
    presence_decay, ambient_decay, self_decay = _residue_decays(event_kind=event_kind, salience=salience)
    presence_weight, ambient_weight, self_weight = _residue_weights(event_kind)
    presence_base = max(clamp01(prev.presence_residue * presence_decay, 0.0), presence_floor)
    ambient_base = max(clamp01(prev.ambient_resonance * ambient_decay, 0.0), ambient_floor)
    self_base = max(clamp01(prev.self_activity_momentum * self_decay, 0.0), self_activity_floor)

    out = WorldModelState(
        relationship_maturity=blend(prev.relationship_maturity, target.relationship_maturity, weight),
        bond_depth=blend(prev.bond_depth, target.bond_depth, weight),
        tension_load=blend(prev.tension_load, target.tension_load, weight),
        repair_load=blend(prev.repair_load, target.repair_load, weight),
        boundary_load=blend(prev.boundary_load, target.boundary_load, weight),
        selfhood_load=blend(prev.selfhood_load, target.selfhood_load, weight),
        agency_load=blend(prev.agency_load, target.agency_load, weight),
        memory_gravity=blend(prev.memory_gravity, target.memory_gravity, weight),
        lineage_gravity=blend(prev.lineage_gravity, lineage_gravity, weight),
        contact_lineage=blend(prev.contact_lineage, contact_lineage, weight),
        repair_lineage=blend(prev.repair_lineage, repair_lineage, weight),
        boundary_lineage=blend(prev.boundary_lineage, boundary_lineage, weight),
        selfhood_lineage=blend(prev.selfhood_lineage, selfhood_lineage, weight),
        agency_lineage=blend(prev.agency_lineage, agency_lineage, weight),
        task_pull=blend(prev.task_pull, target.task_pull, weight),
        companionship_pull=blend(prev.companionship_pull, target.companionship_pull, weight),
        presence_residue=blend(presence_base, presence_target, presence_weight),
        ambient_resonance=blend(ambient_base, ambient_target, ambient_weight),
        self_activity_momentum=blend(self_base, self_activity_target, self_weight),
        updated_at=now_ts,
    )
    return out.to_dict()
