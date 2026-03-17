from __future__ import annotations

from typing import Any

from .policy import build_behavior_action, build_behavior_policy
from .reconsolidation import build_reconsolidation_snapshot
from .state import (
    transition_allostasis_state,
    transition_bond_state,
    transition_counterpart_assessment,
    transition_emotion_state,
    transition_latent_state,
)
from .worldline import build_world_model_state


def evolve_turn_state(
    *,
    prev_world_model_state: dict[str, Any] | None,
    prev_latent_state: dict[str, Any] | None,
    prev_emotion_state: dict[str, Any] | None,
    prev_bond_state: dict[str, Any] | None,
    prev_allostasis_state: dict[str, Any] | None,
    prev_counterpart_assessment: dict[str, Any] | None,
    relationship: dict[str, Any] | None,
    semantic_narrative_profile: dict[str, Any] | None,
    appraisal: dict[str, Any] | None,
    current_event: dict[str, Any] | None,
    agenda_lifecycle_residue: dict[str, Any] | None = None,
    response_style_hint: str,
    tsundere_intensity: float,
    science_mode: bool,
    now_ts: int,
) -> dict[str, Any]:
    world_model_state = build_world_model_state(
        prev_state=prev_world_model_state,
        relationship=relationship,
        semantic_narrative_profile=semantic_narrative_profile,
        appraisal=appraisal,
        current_event=current_event,
        science_mode=science_mode,
        now_ts=now_ts,
    )
    emotion_state = transition_emotion_state(
        prev_state=prev_emotion_state,
        appraisal=appraisal,
        science_mode=science_mode,
        world_model_state=world_model_state,
    )
    bond_state = transition_bond_state(
        prev_state=prev_bond_state,
        relationship=relationship,
        emotion_state=emotion_state,
        appraisal=appraisal,
        world_model_state=world_model_state,
    )
    allostasis_state = transition_allostasis_state(
        prev_state=prev_allostasis_state,
        emotion_state=emotion_state,
        bond_state=bond_state,
        appraisal=appraisal,
        world_model_state=world_model_state,
        science_mode=science_mode,
    )
    counterpart_assessment = transition_counterpart_assessment(
        prev_state=prev_counterpart_assessment,
        appraisal=appraisal,
        relationship=relationship,
        bond_state=bond_state,
        allostasis_state=allostasis_state,
        world_model_state=world_model_state,
        current_event=current_event,
    )
    latent_state = transition_latent_state(
        prev_state=prev_latent_state,
        appraisal=appraisal,
        world_model_state=world_model_state,
        emotion_state=emotion_state,
        bond_state=bond_state,
        allostasis_state=allostasis_state,
        now_ts=now_ts,
    )
    behavior_policy = build_behavior_policy(
        response_style_hint=response_style_hint,
        emotion_state=emotion_state,
        bond_state=bond_state,
        allostasis_state=allostasis_state,
        counterpart_assessment=counterpart_assessment,
        world_model_state=world_model_state,
        latent_state=latent_state,
        semantic_narrative_profile=semantic_narrative_profile,
        tsundere_intensity=tsundere_intensity,
        science_mode=science_mode,
    )
    behavior_action = build_behavior_action(
        current_event=current_event,
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        emotion_state=emotion_state,
        bond_state=bond_state,
        allostasis_state=allostasis_state,
        counterpart_assessment=counterpart_assessment,
        world_model_state=world_model_state,
        latent_state=latent_state,
        semantic_narrative_profile=semantic_narrative_profile,
        behavior_policy=behavior_policy,
    )
    reconsolidation_snapshot = build_reconsolidation_snapshot(
        current_event=current_event,
        appraisal=appraisal,
        world_model_state=world_model_state,
        latent_state=latent_state,
        emotion_state=emotion_state,
        bond_state=bond_state,
        behavior_action=behavior_action,
        agenda_lifecycle_residue=agenda_lifecycle_residue,
    )
    return {
        "world_model_state": world_model_state,
        "evolution_state": latent_state,
        "emotion_state": emotion_state,
        "bond_state": bond_state,
        "allostasis_state": allostasis_state,
        "counterpart_assessment": counterpart_assessment,
        "behavior_policy": behavior_policy,
        "behavior_action": behavior_action,
        "reconsolidation_snapshot": reconsolidation_snapshot,
    }
