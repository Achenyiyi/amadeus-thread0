from __future__ import annotations

from typing import Any

from .appraisal import normalize_appraisal_payload
from .schemas import EvolutionLatentState, blend, clamp01, clamp_signed


def _appraisal_weight(appraisal: dict[str, Any] | None, low: float, high: float) -> float:
    app = normalize_appraisal_payload(appraisal)
    if not bool(app.get("used")):
        return 0.0
    confidence = clamp01(app.get("confidence"), 0.0)
    return low + (high - low) * confidence


def transition_emotion_state(
    *,
    prev_state: dict[str, Any] | None,
    appraisal: dict[str, Any] | None,
    science_mode: bool,
    world_model_state: dict[str, Any] | None,
) -> dict[str, Any]:
    prev = dict(prev_state or {})
    prev_label = str(prev.get("label") or "neutral").strip().lower()
    prev_linger = max(0, int(prev.get("linger", 0) or 0))
    world = dict(world_model_state or {})
    app = normalize_appraisal_payload(appraisal)
    if bool(app.get("used")):
        emotion = app.get("emotion") if isinstance(app.get("emotion"), dict) else {}
        label = str(app.get("emotion_label") or "").strip().lower() or ("logic" if science_mode else prev_label or "neutral")
        valence = clamp_signed(emotion.get("valence"), -1.0, 1.0, 0.05 if science_mode else 0.0)
        valence += 0.10 * clamp01(world.get("repair_load"), 0.0)
        valence -= 0.12 * clamp01(world.get("tension_load"), 0.0)
        valence -= 0.08 * clamp01(world.get("boundary_load"), 0.0)
        arousal = clamp01(emotion.get("arousal"), 0.35)
        arousal += 0.08 * clamp01(world.get("task_pull"), 0.0)
        arousal += 0.10 * clamp01(world.get("tension_load"), 0.0)
        linger = max(0, int(emotion.get("linger", 0) or 0))
        if linger == 0 and prev_label in {"angry", "hurt", "sad", "stress"} and prev_linger > 0:
            linger = max(0, prev_linger - 1)
        return {
            "label": label,
            "valence": clamp_signed(valence, -1.0, 1.0, 0.0),
            "arousal": clamp01(arousal, 0.35),
            "linger": linger,
            "recovery_rate": clamp01(emotion.get("recovery_rate"), 0.20 if science_mode else 0.25),
            "volatility": clamp01(emotion.get("volatility"), 0.18),
        }
    if science_mode:
        return {
            "label": "logic",
            "valence": 0.05,
            "arousal": 0.35,
            "linger": 1 if prev_linger else 0,
            "recovery_rate": 0.20,
            "volatility": 0.18,
        }
    if prev_label in {"angry", "hurt", "sad", "stress"} and prev_linger > 0:
        return {
            "label": prev_label if prev_label != "angry" or prev_linger > 1 else "hurt",
            "valence": clamp_signed(float(prev.get("valence", 0.0) or 0.0) * 0.72, -1.0, 1.0, -0.18),
            "arousal": clamp01(float(prev.get("arousal", 0.35) or 0.35) * 0.74, 0.28),
            "linger": max(0, prev_linger - 1),
            "recovery_rate": clamp01(prev.get("recovery_rate"), 0.18),
            "volatility": clamp01(float(prev.get("volatility", 0.18) or 0.18) * 0.82, 0.18),
        }
    return {
        "label": "neutral",
        "valence": 0.08,
        "arousal": 0.32,
        "linger": 0,
        "recovery_rate": 0.25,
        "volatility": 0.18,
    }


def transition_bond_state(
    *,
    prev_state: dict[str, Any] | None,
    relationship: dict[str, Any] | None,
    emotion_state: dict[str, Any] | None,
    appraisal: dict[str, Any] | None,
    world_model_state: dict[str, Any] | None,
) -> dict[str, Any]:
    prev = dict(prev_state or {})
    world = dict(world_model_state or {})
    emotion = dict(emotion_state or {})
    emotion_label = str(emotion.get("label") or "neutral").strip().lower()
    relationship = relationship if isinstance(relationship, dict) else {}
    base_trust = clamp01(0.5 + 0.15 * float(relationship.get("trust_score", 0.0) or 0.0), 0.5)
    base_closeness = clamp01(0.5 + 0.15 * float(relationship.get("affinity_score", 0.0) or 0.0), 0.5)
    target = {
        "trust": clamp01(base_trust + 0.10 * clamp01(world.get("repair_load"), 0.0) - 0.16 * clamp01(world.get("tension_load"), 0.0)),
        "closeness": clamp01(base_closeness + 0.12 * clamp01(world.get("bond_depth"), 0.0) - 0.12 * clamp01(world.get("boundary_load"), 0.0)),
        "hurt": clamp01(0.04 + 0.22 * clamp01(world.get("tension_load"), 0.0) + 0.18 * clamp01(world.get("boundary_load"), 0.0)),
        "irritation": clamp01(0.03 + 0.18 * clamp01(world.get("tension_load"), 0.0) + (0.14 if emotion_label == "angry" else 0.0)),
        "engagement_drive": clamp01(0.50 + 0.18 * clamp01(world.get("companionship_pull"), 0.0) + 0.14 * clamp01(world.get("bond_depth"), 0.0) - 0.14 * clamp01(world.get("boundary_load"), 0.0)),
        "repair_confidence": clamp01(0.46 + 0.18 * clamp01(world.get("repair_load"), 0.0) + 0.10 * clamp01(world.get("relationship_maturity"), 0.0) - 0.08 * clamp01(world.get("tension_load"), 0.0)),
    }
    if emotion_label == "care":
        target["trust"] = clamp01(target["trust"] + 0.04)
        target["closeness"] = clamp01(target["closeness"] + 0.06)
    elif emotion_label == "tease":
        target["engagement_drive"] = clamp01(target["engagement_drive"] + 0.05)
    elif emotion_label in {"hurt", "sad"}:
        target["hurt"] = clamp01(target["hurt"] + 0.10)
        target["engagement_drive"] = clamp01(target["engagement_drive"] - 0.08)
    elif emotion_label == "angry":
        target["hurt"] = clamp01(target["hurt"] + 0.12)
        target["irritation"] = clamp01(target["irritation"] + 0.12)
        target["engagement_drive"] = clamp01(target["engagement_drive"] - 0.12)
    app = normalize_appraisal_payload(appraisal)
    signals = app.get("signals") if isinstance(app.get("signals"), dict) else {}
    deltas = app.get("bond_delta") if isinstance(app.get("bond_delta"), dict) else {}
    if bool(signals.get("repair")):
        target["trust"] = clamp01(target["trust"] + 0.04)
        target["closeness"] = clamp01(target["closeness"] + 0.03)
        target["hurt"] = clamp01(target["hurt"] - 0.10)
        target["irritation"] = clamp01(target["irritation"] - 0.08)
        target["repair_confidence"] = clamp01(target["repair_confidence"] + 0.10)
    if bool(signals.get("care")):
        target["trust"] = clamp01(target["trust"] + 0.02)
        target["closeness"] = clamp01(target["closeness"] + 0.04)
        target["engagement_drive"] = clamp01(target["engagement_drive"] + 0.06)
    if bool(signals.get("conflict")):
        target["hurt"] = clamp01(target["hurt"] + 0.12)
        target["irritation"] = clamp01(target["irritation"] + 0.12)
        target["trust"] = clamp01(target["trust"] - 0.08)
    if bool(signals.get("withdrawal")):
        target["closeness"] = clamp01(target["closeness"] - 0.05)
        target["engagement_drive"] = clamp01(target["engagement_drive"] - 0.08)
    for key in ("trust", "closeness", "hurt", "irritation", "engagement_drive", "repair_confidence"):
        if key in deltas:
            target[key] = clamp01(float(target.get(key, 0.0)) + 0.92 * clamp_signed(deltas.get(key), -0.35, 0.35, 0.0))
    weight = _appraisal_weight(appraisal, 0.44, 0.82) or 0.34
    return {
        "trust": blend(float(prev.get("trust", base_trust) or base_trust), target["trust"], weight),
        "closeness": blend(float(prev.get("closeness", base_closeness) or base_closeness), target["closeness"], weight),
        "hurt": blend(float(prev.get("hurt", 0.0) or 0.0), target["hurt"], weight),
        "irritation": blend(float(prev.get("irritation", 0.0) or 0.0), target["irritation"], weight),
        "engagement_drive": blend(float(prev.get("engagement_drive", 0.64) or 0.64), target["engagement_drive"], weight),
        "repair_confidence": blend(float(prev.get("repair_confidence", 0.55) or 0.55), target["repair_confidence"], weight),
    }


def transition_allostasis_state(
    *,
    prev_state: dict[str, Any] | None,
    emotion_state: dict[str, Any] | None,
    bond_state: dict[str, Any] | None,
    appraisal: dict[str, Any] | None,
    world_model_state: dict[str, Any] | None,
    science_mode: bool,
) -> dict[str, Any]:
    prev = dict(prev_state or {})
    emotion = dict(emotion_state or {})
    bond = dict(bond_state or {})
    world = dict(world_model_state or {})
    arousal = clamp01(emotion.get("arousal"), 0.35)
    hurt = clamp01(bond.get("hurt"), 0.0)
    irritation = clamp01(bond.get("irritation"), 0.0)
    closeness = clamp01(bond.get("closeness"), 0.5)
    trust = clamp01(bond.get("trust"), 0.5)
    engagement = clamp01(bond.get("engagement_drive"), 0.6)
    target = {
        "safety_need": clamp01(0.18 + 0.42 * hurt + 0.26 * irritation + 0.10 * clamp01(world.get("boundary_load"), 0.0)),
        "closeness_need": clamp01(0.16 + 0.42 * (1.0 - closeness) + 0.12 * clamp01(world.get("companionship_pull"), 0.0) + 0.10 * clamp01(world.get("presence_residue"), 0.0)),
        "competence_need": clamp01(0.34 + 0.38 * clamp01(world.get("task_pull"), 0.0) + 0.10 * clamp01(world.get("self_activity_momentum"), 0.0) + (0.10 if science_mode else 0.0)),
        "autonomy_need": clamp01(0.12 + 0.34 * clamp01(world.get("agency_load"), 0.0) + 0.20 * clamp01(world.get("boundary_load"), 0.0) + 0.14 * clamp01(world.get("self_activity_momentum"), 0.0) + 0.12 * irritation),
        "cognitive_budget": clamp01(0.84 - 0.28 * arousal - 0.16 * clamp01(world.get("tension_load"), 0.0) + 0.10 * trust + 0.06 * engagement - 0.08 * clamp01(world.get("self_activity_momentum"), 0.0), 0.60),
    }
    app = normalize_appraisal_payload(appraisal)
    signals = app.get("signals") if isinstance(app.get("signals"), dict) else {}
    deltas = app.get("allostasis_delta") if isinstance(app.get("allostasis_delta"), dict) else {}
    if bool(signals.get("repair")):
        target["safety_need"] = clamp01(target["safety_need"] - 0.08)
        target["closeness_need"] = clamp01(target["closeness_need"] + 0.05)
    if bool(signals.get("care")):
        target["safety_need"] = clamp01(target["safety_need"] - 0.05)
        target["closeness_need"] = clamp01(target["closeness_need"] + 0.08)
        target["autonomy_need"] = clamp01(target["autonomy_need"] - 0.03)
    if bool(signals.get("conflict")):
        target["safety_need"] = clamp01(target["safety_need"] + 0.10)
        target["autonomy_need"] = clamp01(target["autonomy_need"] + 0.08)
        target["cognitive_budget"] = clamp01(target["cognitive_budget"] - 0.06)
    for key in ("safety_need", "closeness_need", "competence_need", "autonomy_need", "cognitive_budget"):
        if key in deltas:
            target[key] = clamp01(float(target.get(key, 0.0)) + 0.90 * clamp_signed(deltas.get(key), -0.35, 0.35, 0.0))
    weight = _appraisal_weight(appraisal, 0.42, 0.80) or 0.38
    out = {
        "safety_need": blend(float(prev.get("safety_need", 0.20) or 0.20), target["safety_need"], weight),
        "closeness_need": blend(float(prev.get("closeness_need", 0.18) or 0.18), target["closeness_need"], weight),
        "competence_need": blend(float(prev.get("competence_need", 0.38) or 0.38), target["competence_need"], weight),
        "autonomy_need": blend(float(prev.get("autonomy_need", 0.12) or 0.12), target["autonomy_need"], weight),
        "cognitive_budget": blend(float(prev.get("cognitive_budget", 0.7) or 0.7), target["cognitive_budget"], weight),
    }
    out["relational_security"] = round(clamp01((trust + closeness) / 2.0 - 0.5 * hurt, 0.5), 3)
    return out


def transition_counterpart_assessment(
    *,
    prev_state: dict[str, Any] | None,
    appraisal: dict[str, Any] | None,
    relationship: dict[str, Any] | None,
    bond_state: dict[str, Any] | None,
    allostasis_state: dict[str, Any] | None,
    world_model_state: dict[str, Any] | None,
    current_event: dict[str, Any] | None,
) -> dict[str, Any]:
    prev = dict(prev_state or {})
    relationship = relationship if isinstance(relationship, dict) else {}
    bond = dict(bond_state or {})
    allostasis = dict(allostasis_state or {})
    world = dict(world_model_state or {})
    app = normalize_appraisal_payload(appraisal)
    signals = app.get("signals") if isinstance(app.get("signals"), dict) else {}
    event = current_event if isinstance(current_event, dict) else {}
    event_kind = str(event.get("kind") or "user_utterance").strip().lower()

    trust = clamp01(bond.get("trust"), 0.5)
    closeness = clamp01(bond.get("closeness"), 0.5)
    hurt = clamp01(bond.get("hurt"), 0.0)
    irritation = clamp01(bond.get("irritation"), 0.0)
    engagement = clamp01(bond.get("engagement_drive"), 0.6)
    repair_confidence = clamp01(bond.get("repair_confidence"), 0.55)
    safety_need = clamp01(allostasis.get("safety_need"), 0.2)
    autonomy_need = clamp01(allostasis.get("autonomy_need"), 0.2)
    relationship_trust = clamp01(0.5 + 0.18 * float(relationship.get("trust_score", 0.0) or 0.0), 0.5)

    respect = clamp01(0.48 + 0.22 * trust + 0.10 * relationship_trust + 0.06 * repair_confidence - 0.16 * hurt - 0.14 * irritation)
    reciprocity = clamp01(0.46 + 0.20 * closeness + 0.14 * engagement + 0.06 * trust - 0.12 * hurt)
    boundary_pressure = clamp01(0.06 + 0.20 * hurt + 0.18 * irritation + 0.12 * safety_need + 0.08 * autonomy_need + 0.14 * clamp01(world.get("boundary_load"), 0.0))
    reliability = clamp01(0.44 + 0.22 * trust + 0.12 * repair_confidence + 0.06 * relationship_trust - 0.08 * hurt)

    if bool(signals.get("care")):
        respect = clamp01(respect + 0.05)
        reciprocity = clamp01(reciprocity + 0.07)
        boundary_pressure = clamp01(boundary_pressure - 0.06)
        reliability = clamp01(reliability + 0.03)
    if bool(signals.get("repair")):
        respect = clamp01(respect + 0.06)
        reciprocity = clamp01(reciprocity + 0.10)
        boundary_pressure = clamp01(boundary_pressure - 0.12)
        reliability = clamp01(reliability + 0.10)
    if bool(signals.get("conflict")):
        respect = clamp01(respect - 0.10)
        reciprocity = clamp01(reciprocity - 0.10)
        boundary_pressure = clamp01(boundary_pressure + 0.18)
        reliability = clamp01(reliability - 0.08)
    if bool(signals.get("withdrawal")):
        reciprocity = clamp01(reciprocity - 0.08)
        boundary_pressure = clamp01(boundary_pressure + 0.08)
    if event_kind in {"time_idle", "self_activity_state"}:
        boundary_pressure = clamp01(boundary_pressure - 0.02)
    if clamp01(world.get("presence_residue"), 0.0) >= 0.42 and event_kind == "user_utterance":
        respect = clamp01(respect + 0.03)
        reciprocity = clamp01(reciprocity + 0.04)
        boundary_pressure = clamp01(boundary_pressure - 0.03)
    if clamp01(world.get("self_activity_momentum"), 0.0) >= 0.46 and event_kind == "user_utterance":
        boundary_pressure = clamp01(boundary_pressure + 0.03)
        reliability = clamp01(reliability + 0.01)

    weight = 0.14 if event_kind != "user_utterance" else (_appraisal_weight(appraisal, 0.28, 0.54) or 0.30)
    respect_level = blend(float(prev.get("respect_level", 0.52) or 0.52), respect, weight)
    reciprocity_level = blend(float(prev.get("reciprocity", 0.5) or 0.5), reciprocity, weight)
    boundary_level = blend(float(prev.get("boundary_pressure", 0.1) or 0.1), boundary_pressure, weight)
    reliability_level = blend(float(prev.get("reliability_read", 0.5) or 0.5), reliability, weight)

    stance = "open"
    if boundary_level >= 0.58 or safety_need >= 0.62 or respect_level < 0.40 or clamp01(world.get("boundary_load"), 0.0) >= 0.52:
        stance = "guarded"
    elif boundary_level >= 0.34 or reliability_level < 0.48 or hurt > 0.18 or clamp01(world.get("tension_load"), 0.0) >= 0.36:
        stance = "watchful"

    scene = "neutral"
    if bool(signals.get("repair")):
        scene = "repair_attempt"
    elif bool(signals.get("care")):
        scene = "care_bid"
    elif bool(signals.get("conflict")) or bool(signals.get("withdrawal")) or clamp01(world.get("tension_load"), 0.0) >= 0.42:
        scene = "friction"
    elif clamp01(world.get("selfhood_load"), 0.0) >= 0.58:
        scene = str(app.get("selfhood_scene") or "selfhood_reflection")
    elif event_kind == "time_idle":
        scene = "idle_presence"

    return {
        "respect_level": respect_level,
        "reciprocity": reciprocity_level,
        "boundary_pressure": boundary_level,
        "reliability_read": reliability_level,
        "stance": stance,
        "scene": scene,
    }


def transition_latent_state(
    *,
    prev_state: dict[str, Any] | None,
    appraisal: dict[str, Any] | None,
    world_model_state: dict[str, Any] | None,
    emotion_state: dict[str, Any] | None,
    bond_state: dict[str, Any] | None,
    allostasis_state: dict[str, Any] | None,
    now_ts: int,
) -> dict[str, Any]:
    prev = EvolutionLatentState.from_dict(prev_state)
    world = dict(world_model_state or {})
    emotion = dict(emotion_state or {})
    bond = dict(bond_state or {})
    allostasis = dict(allostasis_state or {})
    app = normalize_appraisal_payload(appraisal)
    valence = clamp_signed(emotion.get("valence"), -1.0, 1.0, 0.0)
    arousal = clamp01(emotion.get("arousal"), 0.35)
    target = EvolutionLatentState(
        affect_resonance=clamp01(0.5 + 0.24 * valence + 0.10 * clamp01(world.get("repair_load"), 0.0) - 0.16 * clamp01(world.get("tension_load"), 0.0), 0.5),
        trust_reservoir=clamp01(0.28 + 0.34 * clamp01(bond.get("trust"), 0.5) + 0.18 * clamp01(world.get("relationship_maturity"), 0.5) - 0.12 * clamp01(world.get("boundary_load"), 0.0)),
        attachment_pull=clamp01(0.24 + 0.30 * clamp01(bond.get("closeness"), 0.5) + 0.18 * clamp01(world.get("bond_depth"), 0.0) + 0.10 * clamp01(world.get("memory_gravity"), 0.0)),
        self_coherence=clamp01(0.54 + 0.18 * clamp01(world.get("selfhood_load"), 0.0) + 0.10 * clamp01(world.get("relationship_maturity"), 0.5) - 0.10 * clamp01(world.get("tension_load"), 0.0)),
        agency_pressure=clamp01(0.18 + 0.34 * clamp01(world.get("agency_load"), 0.0) + 0.18 * clamp01(allostasis.get("autonomy_need"), 0.2) + 0.10 * clamp01(world.get("boundary_load"), 0.0) + 0.12 * clamp01(world.get("self_activity_momentum"), 0.0)),
        reflection_drive=clamp01(0.20 + 0.20 * clamp01(world.get("selfhood_load"), 0.0) + 0.18 * clamp01(world.get("memory_gravity"), 0.0) + 0.10 * clamp01(world.get("ambient_resonance"), 0.0) + 0.14 * arousal),
        cognitive_stride=clamp01(0.32 + 0.30 * clamp01(allostasis.get("cognitive_budget"), 0.7) + 0.22 * clamp01(world.get("task_pull"), 0.0) - 0.10 * arousal),
        expression_freedom=clamp01(0.36 + 0.20 * clamp01(bond.get("trust"), 0.5) + 0.16 * clamp01(world.get("bond_depth"), 0.0) + 0.08 * clamp01(world.get("presence_residue"), 0.0) - 0.18 * clamp01(world.get("boundary_load"), 0.0)),
        updated_at=now_ts,
        version=max(1, prev.version + (1 if bool(app.get("used")) else 0)),
    )
    weight = _appraisal_weight(appraisal, 0.20, 0.44) or 0.16
    return EvolutionLatentState(
        affect_resonance=blend(prev.affect_resonance, target.affect_resonance, weight),
        trust_reservoir=blend(prev.trust_reservoir, target.trust_reservoir, weight),
        attachment_pull=blend(prev.attachment_pull, target.attachment_pull, weight),
        self_coherence=blend(prev.self_coherence, target.self_coherence, weight),
        agency_pressure=blend(prev.agency_pressure, target.agency_pressure, weight),
        reflection_drive=blend(prev.reflection_drive, target.reflection_drive, weight),
        cognitive_stride=blend(prev.cognitive_stride, target.cognitive_stride, weight),
        expression_freedom=blend(prev.expression_freedom, target.expression_freedom, weight),
        updated_at=now_ts,
        version=target.version,
    ).to_dict()
