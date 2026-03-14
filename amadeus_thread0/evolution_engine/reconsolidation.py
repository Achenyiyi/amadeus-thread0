from __future__ import annotations

from typing import Any

from .appraisal import normalize_appraisal_payload
from .schemas import clamp01


def build_reconsolidation_snapshot(
    *,
    current_event: dict[str, Any] | None,
    appraisal: dict[str, Any] | None,
    world_model_state: dict[str, Any] | None,
    latent_state: dict[str, Any] | None,
    emotion_state: dict[str, Any] | None,
    bond_state: dict[str, Any] | None,
) -> dict[str, Any]:
    event = current_event if isinstance(current_event, dict) else {}
    app = normalize_appraisal_payload(appraisal)
    world = dict(world_model_state or {})
    latent = dict(latent_state or {})
    emotion = dict(emotion_state or {})
    bond = dict(bond_state or {})
    salience = app.get("salience") if isinstance(app.get("salience"), dict) else {}
    return {
        "event_kind": str(event.get("kind") or "user_utterance"),
        "interaction_frame": str(app.get("interaction_frame") or ""),
        "selfhood_scene": str(app.get("selfhood_scene") or ""),
        "salience": dict(salience),
        "world_model": {
            "bond_depth": clamp01(world.get("bond_depth"), 0.0),
            "tension_load": clamp01(world.get("tension_load"), 0.0),
            "repair_load": clamp01(world.get("repair_load"), 0.0),
            "selfhood_load": clamp01(world.get("selfhood_load"), 0.0),
            "agency_load": clamp01(world.get("agency_load"), 0.0),
            "memory_gravity": clamp01(world.get("memory_gravity"), 0.0),
            "presence_residue": clamp01(world.get("presence_residue"), 0.0),
            "ambient_resonance": clamp01(world.get("ambient_resonance"), 0.0),
            "self_activity_momentum": clamp01(world.get("self_activity_momentum"), 0.0),
        },
        "latent": {
            "self_coherence": clamp01(latent.get("self_coherence"), 0.72),
            "agency_pressure": clamp01(latent.get("agency_pressure"), 0.28),
            "reflection_drive": clamp01(latent.get("reflection_drive"), 0.35),
            "expression_freedom": clamp01(latent.get("expression_freedom"), 0.62),
        },
        "emotion_label": str(emotion.get("label") or "neutral"),
        "bond_trust": clamp01(bond.get("trust"), 0.5),
        "bond_closeness": clamp01(bond.get("closeness"), 0.5),
        "bond_hurt": clamp01(bond.get("hurt"), 0.0),
    }
