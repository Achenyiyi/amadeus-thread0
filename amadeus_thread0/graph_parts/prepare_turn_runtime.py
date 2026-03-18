from __future__ import annotations

from typing import Any, Mapping

from ..config import (
    ABLATE_PERSONA_ALIGNMENT,
    CANON_COUNTERPART_ALIASES,
    CANON_COUNTERPART_ID,
    CANON_COUNTERPART_NAME,
)
from ..evolution_engine import evolve_turn_state
from ..memory_store import MemoryStore
from .behavior_agenda import _merge_behavior_agenda
from .behavior_runtime import _behavior_action_from_state, _behavior_plan_from_action
from .memory_evolution import _passive_evolution_memory_update
from .persona_runtime import _canon_persona_labels, _tsundere_next
from .relational_runtime import (
    _counterpart_assessment_summary,
    _prefer_refreshed_relationship_state,
    _relationship_runtime_snapshot,
    _worldline_focus,
)
from .retrieval import _retrieve_context
from .runtime_services import _audit_jsonl
from .semantic_narrative import _semantic_narrative_profile
from .state import ThreadState
from .turn_events import _now_ts


def _prepare_turn_runtime(
    *,
    state: ThreadState,
    store: MemoryStore,
    turn_now_ts: int,
    prepared_turn: Mapping[str, Any],
) -> dict[str, Any]:
    profile = prepared_turn["profile"]
    persona_core = prepared_turn["persona_core"]
    prior_behavior_agenda = prepared_turn["prior_behavior_agenda"]
    agenda_lifecycle_residue = prepared_turn["agenda_lifecycle_residue"]
    user_text = prepared_turn["user_text"]
    effective_user_text = prepared_turn["effective_user_text"]
    science_mode = prepared_turn["science_mode"]
    response_style_hint = prepared_turn["response_style_hint"]
    external_probe_mode = prepared_turn["external_probe_mode"]
    retrieved = prepared_turn["retrieved"]
    relationship = prepared_turn["relationship"]
    canon_recontact_baseline = prepared_turn["canon_recontact_baseline"]
    worldline_focus = prepared_turn["worldline_focus"]
    seed_emotion_state = prepared_turn["seed_emotion_state"]
    seed_bond_state = prepared_turn["seed_bond_state"]
    seed_allostasis_state = prepared_turn["seed_allostasis_state"]
    seed_counterpart_assessment = prepared_turn["seed_counterpart_assessment"]
    seed_world_model_state = prepared_turn["seed_world_model_state"]
    seed_evolution_state = prepared_turn["seed_evolution_state"]
    seed_tsundere_intensity = prepared_turn["seed_tsundere_intensity"]
    appraisal = prepared_turn["appraisal"]
    current_event = prepared_turn["current_event"]
    interaction_carryover = prepared_turn["interaction_carryover"]

    persona_state = dict(state.get("persona_state") or {})
    if bool(ABLATE_PERSONA_ALIGNMENT):
        emotion_state = {"label": "neutral", "valence": 0.0, "arousal": 0.25}
        bond_state = {
            "trust": 0.5,
            "closeness": 0.5,
            "hurt": 0.0,
            "irritation": 0.0,
            "engagement_drive": 0.5,
            "repair_confidence": 0.5,
        }
        allostasis_state = {
            "safety_need": 0.2,
            "closeness_need": 0.18,
            "competence_need": 0.38,
            "autonomy_need": 0.12,
            "cognitive_budget": 0.7,
            "relational_security": 0.5,
        }
        counterpart_assessment = {
            "respect_level": 0.5,
            "reciprocity": 0.5,
            "boundary_pressure": 0.1,
            "reliability_read": 0.5,
            "stance": "open",
            "scene": "neutral",
        }
        world_model_state = dict(state.get("world_model_state") or {})
        evolution_state = dict(state.get("evolution_state") or {})
        tsundere = 0.05
        persona_state.update(
            {
                "role": "generic_assistant",
                "language": "zh-main",
                "strict_canon": False,
                "value_floor": [],
                "evolution_contract": {},
                "updated_at": turn_now_ts,
            }
        )
        behavior_policy = {
            "warmth": 0.5,
            "sharpness": 0.2,
            "initiative": 0.5,
            "disclosure": 0.5,
            "reply_length_bias": 0.5,
            "approach_vs_withdraw": 0.5,
            "humor_or_tease_bias": 0.1,
            "boundary_assertiveness": 0.1,
            "self_directedness": 0.1,
            "equality_guard": 0.1,
        }
        behavior_action = {
            "channel": "speech",
            "interaction_mode": "steady_reply",
            "approach_style": "steady",
            "engagement_level": 0.5,
            "initiative_level": 0.5,
            "followup_intent": "soft",
            "task_focus": "balanced",
            "affect_surface": "mixed",
            "silence_ok": False,
            "proactive_checkin_readiness": 0.5,
            "action_target": "respond_now",
            "deferred_action_family": "none",
            "timing_window_min": 0,
            "attention_target": "counterpart_state",
            "nonverbal_signal": "steady_presence",
            "initiative_shape": "reply",
            "disclosure_posture": "measured",
            "note": "ablation_persona_alignment",
        }
        reconsolidation_snapshot = {}
    else:
        canon_labels = _canon_persona_labels()
        persona_state.update(
            {
                "role": str(persona_core.get("character_id") or canon_labels.get("character_id") or "kurisu_amadeus"),
                "display_name": str(persona_core.get("display_name") or canon_labels.get("display_name") or "牧濑红莉栖"),
                "short_name": str(persona_core.get("short_name") or ""),
                "narrative_ref": str(
                    persona_core.get("narrative_ref")
                    or persona_core.get("display_name")
                    or canon_labels.get("narrative_ref")
                    or "红莉栖"
                ),
                "language": "zh-main-jp-whitelist",
                "strict_canon": bool(persona_core.get("strict_canon", True)),
                "role_brief": str(persona_core.get("role_brief") or ""),
                "identity_axioms": list(persona_core.get("identity_axioms") or []),
                "value_floor": list(persona_core.get("value_floor") or []),
                "evolution_contract": dict(persona_core.get("evolution_contract") or {}),
                "canonical_counterpart_id": str(profile.get("counterpart_id") or CANON_COUNTERPART_ID),
                "canonical_counterpart_name": str(profile.get("name") or CANON_COUNTERPART_NAME),
                "canonical_counterpart_short_name": str(profile.get("short_name") or profile.get("nickname") or ""),
                "canonical_counterpart_aliases": list(profile.get("aliases") or CANON_COUNTERPART_ALIASES),
                "canon_baseline_mode": str(canon_recontact_baseline.get("mode") or "")
                if isinstance(canon_recontact_baseline, dict)
                else "",
                "updated_at": turn_now_ts,
            }
        )
        semantic_narrative_profile = _semantic_narrative_profile(
            retrieved.get("semantic_self_narratives")
            if isinstance(retrieved.get("semantic_self_narratives"), list)
            else [],
            user_text=effective_user_text or user_text,
            current_event=current_event,
        )
        evolved = evolve_turn_state(
            prev_world_model_state=seed_world_model_state,
            prev_latent_state=seed_evolution_state,
            prev_emotion_state=seed_emotion_state,
            prev_bond_state=seed_bond_state,
            prev_allostasis_state=seed_allostasis_state,
            prev_counterpart_assessment=seed_counterpart_assessment,
            relationship=relationship,
            semantic_narrative_profile=semantic_narrative_profile,
            appraisal=appraisal,
            current_event=current_event,
            interaction_carryover=interaction_carryover,
            agenda_lifecycle_residue=agenda_lifecycle_residue,
            response_style_hint=response_style_hint,
            tsundere_intensity=seed_tsundere_intensity,
            science_mode=science_mode,
            now_ts=turn_now_ts,
        )
        world_model_state = dict(evolved.get("world_model_state") or {})
        evolution_state = dict(evolved.get("evolution_state") or {})
        emotion_state = dict(evolved.get("emotion_state") or {})
        bond_state = dict(evolved.get("bond_state") or {})
        allostasis_state = dict(evolved.get("allostasis_state") or {})
        counterpart_assessment = dict(evolved.get("counterpart_assessment") or {})
        behavior_policy = dict(evolved.get("behavior_policy") or {})
        behavior_action = dict(evolved.get("behavior_action") or {})
        reconsolidation_snapshot = dict(evolved.get("reconsolidation_snapshot") or {})
        tsundere = _tsundere_next(
            seed_tsundere_intensity,
            emotion_label=str(emotion_state.get("label") or "neutral"),
            appraisal=appraisal,
            bond_state=bond_state,
            world_model_state=world_model_state,
        )

    memory_evolved = False
    current_event_kind = str(current_event.get("kind") or "user_utterance").strip().lower()
    if not external_probe_mode and current_event_kind in {
        "user_utterance",
        "gesture_signal",
        "ambient_shift",
        "scene_observation",
        "time_idle",
        "self_activity_state",
        "scheduled_checkin_due",
        "scheduled_life_due",
    }:
        memory_evolved = _passive_evolution_memory_update(
            store,
            user_text=effective_user_text or user_text,
            appraisal=appraisal,
            emotion_state=emotion_state,
            bond_state=bond_state,
            persona_core=persona_core,
            counterpart_profile=profile,
            current_event=current_event,
            world_model_state=world_model_state,
            behavior_action=behavior_action,
            agenda_lifecycle_residue=agenda_lifecycle_residue,
        )

    if memory_evolved:
        retrieved = _retrieve_context(effective_user_text or user_text, store)
        refreshed_relationship = (
            retrieved.get("relationship")
            if isinstance(retrieved.get("relationship"), dict)
            else store.get_relationship()
        )
        relationship = _prefer_refreshed_relationship_state(relationship, refreshed_relationship)
        worldline_focus = _worldline_focus(store)
        semantic_narrative_profile = _semantic_narrative_profile(
            retrieved.get("semantic_self_narratives")
            if isinstance(retrieved.get("semantic_self_narratives"), list)
            else [],
            user_text=effective_user_text or user_text,
            current_event=current_event,
        )
        evolved = evolve_turn_state(
            prev_world_model_state=world_model_state,
            prev_latent_state=evolution_state,
            prev_emotion_state=emotion_state,
            prev_bond_state=bond_state,
            prev_allostasis_state=allostasis_state,
            prev_counterpart_assessment=counterpart_assessment,
            relationship=relationship,
            semantic_narrative_profile=semantic_narrative_profile,
            appraisal=appraisal,
            current_event=current_event,
            interaction_carryover=interaction_carryover,
            agenda_lifecycle_residue=agenda_lifecycle_residue,
            response_style_hint=response_style_hint,
            tsundere_intensity=tsundere,
            science_mode=science_mode,
            now_ts=_now_ts(),
        )
        world_model_state = dict(evolved.get("world_model_state") or {})
        evolution_state = dict(evolved.get("evolution_state") or {})
        emotion_state = dict(evolved.get("emotion_state") or {})
        bond_state = dict(evolved.get("bond_state") or {})
        allostasis_state = dict(evolved.get("allostasis_state") or {})
        counterpart_assessment = dict(evolved.get("counterpart_assessment") or {})
        behavior_policy = dict(evolved.get("behavior_policy") or {})
        behavior_action = dict(evolved.get("behavior_action") or {})
        reconsolidation_snapshot = dict(evolved.get("reconsolidation_snapshot") or {})
        tsundere = _tsundere_next(
            tsundere,
            emotion_label=str(emotion_state.get("label") or "neutral"),
            appraisal=appraisal,
            bond_state=bond_state,
            world_model_state=world_model_state,
        )
    elif bool(ABLATE_PERSONA_ALIGNMENT):
        semantic_narrative_profile = _semantic_narrative_profile(
            retrieved.get("semantic_self_narratives")
            if isinstance(retrieved.get("semantic_self_narratives"), list)
            else [],
            user_text=effective_user_text or user_text,
            current_event=current_event,
        )

    relationship = _relationship_runtime_snapshot(
        relationship=relationship,
        bond_state=bond_state,
        world_model_state=world_model_state,
        counterpart_assessment=counterpart_assessment,
        semantic_narrative_profile=semantic_narrative_profile,
    )
    if isinstance(retrieved, dict):
        retrieved = {**retrieved, "relationship": relationship}
    counterpart_assessment["summary"] = _counterpart_assessment_summary(
        counterpart_assessment,
        counterpart_name=str(profile.get("short_name") or profile.get("nickname") or profile.get("name") or CANON_COUNTERPART_NAME),
    )
    behavior_action = _behavior_action_from_state(
        current_event=current_event,
        response_style_hint=response_style_hint,
        user_text=effective_user_text or user_text,
        science_mode=science_mode,
        emotion_state=emotion_state,
        bond_state=bond_state,
        allostasis_state=allostasis_state,
        counterpart_assessment=counterpart_assessment,
        semantic_narrative_profile=semantic_narrative_profile,
        behavior_policy=behavior_policy,
        world_model_state=world_model_state,
        interaction_carryover=interaction_carryover,
        prior_emotion_state=seed_emotion_state,
        prior_bond_state=seed_bond_state,
        prior_allostasis_state=seed_allostasis_state,
        prior_counterpart_assessment=seed_counterpart_assessment,
    )
    behavior_plan = _behavior_plan_from_action(current_event, behavior_action)
    behavior_agenda = _merge_behavior_agenda(
        prior_behavior_agenda,
        current_event,
        behavior_plan,
        counterpart_assessment=counterpart_assessment,
        world_model_state=world_model_state,
        semantic_narrative_profile=semantic_narrative_profile,
    )
    _audit_jsonl(
        "decision_audit.jsonl",
        {
            "working_items": int(len(retrieved.get("working_items") or [])),
            "working_chars": int(retrieved.get("working_chars") or 0),
            "retrieval_triggered": bool(retrieved.get("triggered")),
            "science_mode": bool(science_mode),
            "emotion_label": str(emotion_state.get("label") or "neutral"),
            "bond_trust": float(bond_state.get("trust") or 0.0),
            "bond_hurt": float(bond_state.get("hurt") or 0.0),
            "counterpart_stance": str(counterpart_assessment.get("stance") or ""),
            "counterpart_boundary_pressure": float(counterpart_assessment.get("boundary_pressure") or 0.0),
            "policy_warmth": float(behavior_policy.get("warmth") or 0.0),
            "policy_self_directedness": float(behavior_policy.get("self_directedness") or 0.0),
            "policy_boundary_assertiveness": float(behavior_policy.get("boundary_assertiveness") or 0.0),
            "semantic_history_weight": float(semantic_narrative_profile.get("history_weight") or 0.0),
            "semantic_presence_carry": float(semantic_narrative_profile.get("presence_carry") or 0.0),
            "semantic_ambient_attunement": float(semantic_narrative_profile.get("ambient_attunement") or 0.0),
            "semantic_rhythm_continuity": float(semantic_narrative_profile.get("rhythm_continuity") or 0.0),
            "semantic_boundary_residue": float(semantic_narrative_profile.get("boundary_residue") or 0.0),
            "semantic_selfhood_integrity": float(semantic_narrative_profile.get("selfhood_integrity") or 0.0),
            "semantic_agency_drive": float(semantic_narrative_profile.get("agency_drive") or 0.0),
            "world_bond_depth": float(world_model_state.get("bond_depth") or 0.0),
            "world_tension_load": float(world_model_state.get("tension_load") or 0.0),
            "world_selfhood_load": float(world_model_state.get("selfhood_load") or 0.0),
            "world_presence_residue": float(world_model_state.get("presence_residue") or 0.0),
            "world_ambient_resonance": float(world_model_state.get("ambient_resonance") or 0.0),
            "world_self_activity_momentum": float(world_model_state.get("self_activity_momentum") or 0.0),
            "latent_self_coherence": float(evolution_state.get("self_coherence") or 0.0),
            "latent_agency_pressure": float(evolution_state.get("agency_pressure") or 0.0),
            "behavior_mode": str(behavior_action.get("interaction_mode") or ""),
            "behavior_primary_motive": str(behavior_action.get("primary_motive") or ""),
            "behavior_motive_tension": str(behavior_action.get("motive_tension") or ""),
            "behavior_goal_frame": str(behavior_action.get("goal_frame") or "")[:120],
            "behavior_plan_kind": str(behavior_plan.get("kind") or ""),
            "behavior_plan_motive": str(behavior_plan.get("primary_motive") or ""),
            "behavior_plan_goal_frame": str(behavior_plan.get("goal_frame") or "")[:120],
            "behavior_agenda_size": int(len(behavior_agenda or [])),
            "agenda_lifecycle_kind": str(agenda_lifecycle_residue.get("kind") or ""),
            "agenda_lifecycle_cooldown": float(agenda_lifecycle_residue.get("recontact_cooldown") or 0.0),
            "carryover_mode": str(interaction_carryover.get("carryover_mode") or ""),
            "carryover_strength": float(interaction_carryover.get("strength") or 0.0),
            "carryover_source_motive": str(interaction_carryover.get("source_primary_motive") or ""),
            "appraisal_used": bool(appraisal.get("used", False)),
            "appraisal_confidence": float(appraisal.get("confidence", 0.0) or 0.0),
        },
    )

    return {
        "retrieved": retrieved,
        "relationship": relationship,
        "worldline_focus": worldline_focus,
        "persona_state": persona_state,
        "world_model_state": world_model_state,
        "evolution_state": evolution_state,
        "reconsolidation_snapshot": reconsolidation_snapshot,
        "emotion_state": emotion_state,
        "bond_state": bond_state,
        "allostasis_state": allostasis_state,
        "counterpart_assessment": counterpart_assessment,
        "semantic_narrative_profile": semantic_narrative_profile,
        "behavior_policy": behavior_policy,
        "behavior_action": behavior_action,
        "behavior_plan": behavior_plan,
        "behavior_agenda": behavior_agenda,
        "tsundere": tsundere,
    }
