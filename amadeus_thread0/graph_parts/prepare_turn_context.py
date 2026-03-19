from __future__ import annotations

from typing import Any

from ..config import CANON_COUNTERPART_NAME
from ..memory_store import MemoryStore
from ..runtime.session_orchestrator import (
    continuation_seed_text,
    derive_pending_fragment,
    derive_pending_user_goal,
    has_pending_continuation as has_active_continuation,
)
from .appraisal import _invoke_turn_appraisal
from .behavior_agenda import (
    _promote_due_behavior_action_event,
    _promote_due_behavior_agenda_event_with_residue,
    _promote_due_behavior_plan_event,
)
from .messages import (
    _compact_thread_if_needed,
    _last_ai_text,
    _last_user_text,
    _messages,
    _previous_user_text,
)
from .persona_runtime import (
    _active_counterpart_profile,
    _active_persona_core,
    _canon_okabe_recontact_baseline,
    _is_external_probe_context,
    _prefer_explicit_state_dict,
    _science_mode_from_context,
)
from .postprocess import _clean_utf8_text, _needs_structured_answer, _response_style_hint
from .relational_carryover import (
    _apply_agenda_lifecycle_residue_to_runtime_state,
    _apply_retrieved_behavior_trace_bridge,
    _hydrate_retrieved_agenda_lifecycle_residue,
    _recent_interaction_carryover,
    _seeded_interaction_carryover_from_state,
)
from .relational_runtime import (
    _prefer_relationship_state,
    _relationship_has_meaningful_signal,
    _relationship_runtime_snapshot,
    _worldline_focus,
)
from .retrieval import _empty_retrieved_context, _retrieve_context
from .semantic_narrative import _prefer_semantic_narrative_profile, _semantic_narrative_profile
from .state import ThreadState
from .turn_events import (
    _append_recent_events,
    _appraisal_event_context,
    _build_current_event,
    _normalize_event_override,
    _promote_due_commitment_event,
    _sanitize_obj,
)


def _prepare_turn_context(
    *,
    state: ThreadState,
    store: MemoryStore,
    turn_now_ts: int,
) -> dict[str, Any]:
    profile, counterpart_trace = _active_counterpart_profile(state, store, with_trace=True)
    persona_core, persona_trace = _active_persona_core(state, with_trace=True)
    msgs = _messages(state)
    counterpart_name = str(
        profile.get("short_name") or profile.get("nickname") or profile.get("name") or CANON_COUNTERPART_NAME
    )
    event_override = _normalize_event_override(
        _sanitize_obj(state.get("event_override")),
        counterpart_name=counterpart_name,
    )
    prior_current_event = _sanitize_obj(state.get("current_event")) if isinstance(state.get("current_event"), dict) else {}
    prior_behavior_action = (
        _sanitize_obj(state.get("behavior_action")) if isinstance(state.get("behavior_action"), dict) else {}
    )
    prior_behavior_plan = (
        _sanitize_obj(state.get("behavior_plan")) if isinstance(state.get("behavior_plan"), dict) else {}
    )
    prior_behavior_agenda = (
        _sanitize_obj(state.get("behavior_agenda")) if isinstance(state.get("behavior_agenda"), list) else []
    )
    agenda_lifecycle_residue: dict[str, Any] = {}
    if not prior_behavior_agenda and isinstance(state.get("behavior_queue"), list):
        prior_behavior_agenda = _sanitize_obj(state.get("behavior_queue"))  # type: ignore[assignment]
    had_prior_behavior_queue = bool(prior_behavior_agenda)
    if event_override:
        event_override, prior_behavior_agenda, agenda_lifecycle_residue = _promote_due_behavior_agenda_event_with_residue(
            event_override,
            prior_behavior_agenda,
            counterpart_assessment=state.get("counterpart_assessment")
            if isinstance(state.get("counterpart_assessment"), dict)
            else None,
            world_model_state=state.get("world_model_state")
            if isinstance(state.get("world_model_state"), dict)
            else None,
            semantic_narrative_profile=state.get("semantic_narrative_profile")
            if isinstance(state.get("semantic_narrative_profile"), dict)
            else None,
        )
        if not had_prior_behavior_queue:
            event_override = _promote_due_behavior_plan_event(event_override, prior_behavior_plan)
        event_override = _promote_due_behavior_action_event(
            event_override,
            prior_current_event,
            prior_behavior_action,
        )
        event_override = _promote_due_commitment_event(
            event_override,
            store,
            counterpart_name=counterpart_name,
        )

    user_text = _last_user_text(msgs)
    previous_user_text = _previous_user_text(msgs)
    prev_assistant = _last_ai_text(msgs)
    pending = derive_pending_fragment(
        user_text=user_text,
        previous_excerpt=prev_assistant[:180],
        pending_fragment=_clean_utf8_text(str(state.get("pending_utterance_fragment") or "")),
    )
    pending_user_goal = derive_pending_user_goal(
        user_text=user_text,
        previous_user_text=previous_user_text,
        pending_user_goal=_clean_utf8_text(str(state.get("pending_user_goal") or "")),
        pending_fragment=pending,
    )
    continuation_mode = has_active_continuation(user_text=user_text, pending_fragment=pending)
    continuation_seed = continuation_seed_text(
        pending_user_goal=pending_user_goal,
        pending_fragment=pending,
    )
    if event_override:
        continuation_mode = bool(event_override.get("continuation_mode", continuation_mode))
    effective_user_text = continuation_seed if continuation_mode and continuation_seed else user_text
    if event_override:
        effective_user_text = str(
            event_override.get("effective_text") or event_override.get("text") or effective_user_text or ""
        ).strip()

    _compact_thread_if_needed(msgs, store)

    science_mode = (
        _science_mode_from_context(
            effective_user_text or user_text,
            previous_user_text=previous_user_text,
            pending_user_goal=pending_user_goal,
            previous_assistant_text=prev_assistant,
        )
        if (effective_user_text or user_text)
        else bool(state.get("science_mode", False))
    )
    if event_override:
        science_mode = bool(event_override.get("science_mode", science_mode))
    response_style_hint = _response_style_hint(
        effective_user_text or user_text,
        science_mode=science_mode,
        continuation_mode=continuation_mode,
        previous_hint=str(state.get("response_style_hint") or ""),
        previous_user_text=previous_user_text,
        current_event=event_override if isinstance(event_override, dict) and event_override else None,
    )
    if event_override:
        response_style_hint = str(
            event_override.get("response_style_hint") or response_style_hint or "natural"
        ).strip() or "natural"
    if continuation_mode and continuation_seed and _needs_structured_answer(pending_user_goal or continuation_seed, ""):
        response_style_hint = "structured"

    external_probe_mode = _is_external_probe_context(persona_core=persona_core, counterpart_profile=profile)
    retrieved = _empty_retrieved_context(store) if external_probe_mode else _retrieve_context(effective_user_text or user_text, store)
    if not agenda_lifecycle_residue:
        agenda_lifecycle_residue = _hydrate_retrieved_agenda_lifecycle_residue(
            retrieved=retrieved if isinstance(retrieved, dict) else {},
        )
    retrieved_relationship = (
        retrieved.get("relationship") if isinstance(retrieved.get("relationship"), dict) else store.get_relationship()
    )
    relationship = _relationship_runtime_snapshot(
        relationship=_prefer_relationship_state(
            state.get("relationship") if isinstance(state.get("relationship"), dict) else None,
            retrieved_relationship,
        ),
        bond_state=state.get("bond_state") if isinstance(state.get("bond_state"), dict) else None,
        world_model_state=state.get("world_model_state") if isinstance(state.get("world_model_state"), dict) else None,
        counterpart_assessment=state.get("counterpart_assessment")
        if isinstance(state.get("counterpart_assessment"), dict)
        else None,
        semantic_narrative_profile=state.get("semantic_narrative_profile")
        if isinstance(state.get("semantic_narrative_profile"), dict)
        else None,
    )
    canon_recontact_baseline = _canon_okabe_recontact_baseline(
        state=state,
        persona_core=persona_core,
        counterpart_profile=profile,
        relationship=relationship,
        retrieved=retrieved if isinstance(retrieved, dict) else {},
        external_probe_mode=external_probe_mode,
        now_ts=turn_now_ts,
    )
    if isinstance(canon_recontact_baseline, dict):
        relationship = dict(canon_recontact_baseline.get("relationship") or relationship)
        if not _relationship_has_meaningful_signal(retrieved_relationship):
            store.set_relationship(relationship)
        if isinstance(retrieved, dict):
            retrieved = {**retrieved, "relationship": relationship}
    worldline_focus = [] if external_probe_mode else _worldline_focus(store)

    seed_emotion_state = _prefer_explicit_state_dict(
        state,
        "emotion_state",
        canon_recontact_baseline.get("emotion_state") if isinstance(canon_recontact_baseline, dict) else None,
    )
    seed_bond_state = _prefer_explicit_state_dict(
        state,
        "bond_state",
        canon_recontact_baseline.get("bond_state") if isinstance(canon_recontact_baseline, dict) else None,
    )
    seed_allostasis_state = _prefer_explicit_state_dict(
        state,
        "allostasis_state",
        canon_recontact_baseline.get("allostasis_state") if isinstance(canon_recontact_baseline, dict) else None,
    )
    seed_counterpart_assessment = _prefer_explicit_state_dict(
        state,
        "counterpart_assessment",
        canon_recontact_baseline.get("counterpart_assessment")
        if isinstance(canon_recontact_baseline, dict)
        else None,
    )
    seed_world_model_state = _prefer_explicit_state_dict(
        state,
        "world_model_state",
        canon_recontact_baseline.get("world_model_state") if isinstance(canon_recontact_baseline, dict) else None,
    )
    seed_world_model_state, seed_counterpart_assessment = _apply_agenda_lifecycle_residue_to_runtime_state(
        agenda_lifecycle_residue=agenda_lifecycle_residue,
        world_model_state=seed_world_model_state,
        counterpart_assessment=seed_counterpart_assessment,
    )
    seed_evolution_state = _prefer_explicit_state_dict(
        state,
        "evolution_state",
        canon_recontact_baseline.get("evolution_state") if isinstance(canon_recontact_baseline, dict) else None,
    )
    seed_tsundere_intensity = (
        float(canon_recontact_baseline.get("tsundere_intensity", 0.55) or 0.55)
        if isinstance(canon_recontact_baseline, dict) and state.get("tsundere_intensity") is None
        else float(state.get("tsundere_intensity", 0.55) or 0.55)
    )

    appraisal_event_context = _appraisal_event_context(
        user_text=user_text,
        effective_text=effective_user_text or user_text,
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        continuation_mode=continuation_mode,
        counterpart_name=counterpart_name,
        pending_user_goal=pending_user_goal,
        event_override=event_override,
    )
    semantic_narrative_profile_for_appraisal = _semantic_narrative_profile(
        retrieved.get("semantic_self_narratives")
        if isinstance(retrieved.get("semantic_self_narratives"), list)
        else [],
        user_text=effective_user_text or user_text,
        current_event=appraisal_event_context,
    )
    prior_semantic_narrative_profile = _prefer_semantic_narrative_profile(
        state.get("semantic_narrative_profile")
        if isinstance(state.get("semantic_narrative_profile"), dict)
        else None,
        semantic_narrative_profile_for_appraisal,
    )
    appraisal_interaction_carryover = _recent_interaction_carryover(
        prior_current_event=prior_current_event if isinstance(prior_current_event, dict) else {},
        prior_behavior_action=prior_behavior_action if isinstance(prior_behavior_action, dict) else {},
        prior_agenda_lifecycle_residue=agenda_lifecycle_residue,
        prior_counterpart_assessment=state.get("counterpart_assessment")
        if isinstance(state.get("counterpart_assessment"), dict)
        else {},
        recent_events=state.get("recent_events"),
        current_event=appraisal_event_context,
        response_style_hint=response_style_hint,
        world_model_state=seed_world_model_state,
        semantic_narrative_profile=prior_semantic_narrative_profile
        if isinstance(prior_semantic_narrative_profile, dict)
        else {},
    )
    if not appraisal_interaction_carryover:
        appraisal_interaction_carryover = _seeded_interaction_carryover_from_state(
            state=state,
            prior_current_event=prior_current_event if isinstance(prior_current_event, dict) else {},
            prior_behavior_action=prior_behavior_action if isinstance(prior_behavior_action, dict) else {},
            seed_world_model_state=seed_world_model_state,
            semantic_narrative_profile=prior_semantic_narrative_profile
            if isinstance(prior_semantic_narrative_profile, dict)
            else {},
            counterpart_assessment=seed_counterpart_assessment,
            current_event=appraisal_event_context,
            response_style_hint=response_style_hint,
        )
    appraisal_event_context, appraisal_interaction_carryover = _apply_retrieved_behavior_trace_bridge(
        retrieved=retrieved if isinstance(retrieved, dict) else {},
        current_event=appraisal_event_context if isinstance(appraisal_event_context, dict) else {},
        interaction_carryover=appraisal_interaction_carryover if isinstance(appraisal_interaction_carryover, dict) else {},
    )

    appraisal_input_text = effective_user_text or user_text
    appraisal = _invoke_turn_appraisal(
        msgs=msgs,
        user_text=appraisal_input_text,
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        prev_emotion_state=seed_emotion_state,
        prev_bond_state=seed_bond_state,
        prev_allostasis_state=seed_allostasis_state,
        relationship=relationship,
        worldline_focus=worldline_focus,
        retrieved=retrieved,
        persona_core=persona_core,
        counterpart_profile=profile,
        current_event=appraisal_event_context,
        semantic_narrative_profile=semantic_narrative_profile_for_appraisal,
        interaction_carryover=appraisal_interaction_carryover,
    )
    response_style_hint = _response_style_hint(
        effective_user_text or user_text,
        appraisal=appraisal,
        science_mode=science_mode,
        continuation_mode=continuation_mode,
        previous_hint=response_style_hint,
        previous_user_text=previous_user_text,
        current_event=appraisal_event_context,
    )
    current_event = (
        {
            **dict(appraisal_event_context),
            "appraisal_label": str(
                appraisal.get("emotion_label")
                or appraisal.get("label")
                or appraisal_event_context.get("appraisal_label")
                or ""
            ).strip(),
            "appraisal_confidence": float(
                appraisal.get("confidence", 0.0) or appraisal_event_context.get("appraisal_confidence") or 0.0
            ),
            "created_at": int(appraisal_event_context.get("created_at") or turn_now_ts),
        }
        if event_override
        else _build_current_event(
            user_text=user_text,
            effective_text=effective_user_text or user_text,
            response_style_hint=response_style_hint,
            science_mode=science_mode,
            continuation_mode=continuation_mode,
            appraisal=appraisal,
            counterpart_name=counterpart_name,
            pending_user_goal=pending_user_goal,
        )
    )
    interaction_carryover = _recent_interaction_carryover(
        prior_current_event=prior_current_event if isinstance(prior_current_event, dict) else {},
        prior_behavior_action=prior_behavior_action if isinstance(prior_behavior_action, dict) else {},
        prior_agenda_lifecycle_residue=agenda_lifecycle_residue,
        prior_counterpart_assessment=state.get("counterpart_assessment")
        if isinstance(state.get("counterpart_assessment"), dict)
        else {},
        recent_events=state.get("recent_events"),
        current_event=current_event,
        response_style_hint=response_style_hint,
        world_model_state=seed_world_model_state,
        semantic_narrative_profile=prior_semantic_narrative_profile
        if isinstance(prior_semantic_narrative_profile, dict)
        else {},
    )
    if not interaction_carryover:
        interaction_carryover = _seeded_interaction_carryover_from_state(
            state=state,
            prior_current_event=prior_current_event if isinstance(prior_current_event, dict) else {},
            prior_behavior_action=prior_behavior_action if isinstance(prior_behavior_action, dict) else {},
            seed_world_model_state=seed_world_model_state,
            semantic_narrative_profile=prior_semantic_narrative_profile
            if isinstance(prior_semantic_narrative_profile, dict)
            else {},
            counterpart_assessment=seed_counterpart_assessment,
            current_event=current_event,
            response_style_hint=response_style_hint,
        )
    current_event, interaction_carryover = _apply_retrieved_behavior_trace_bridge(
        retrieved=retrieved if isinstance(retrieved, dict) else {},
        current_event=current_event if isinstance(current_event, dict) else {},
        interaction_carryover=interaction_carryover if isinstance(interaction_carryover, dict) else {},
    )
    recent_events = _append_recent_events(_sanitize_obj(state.get("recent_events")), current_event, limit=6)

    return {
        "profile": profile,
        "counterpart_trace": counterpart_trace,
        "persona_core": persona_core,
        "persona_trace": persona_trace,
        "msgs": msgs,
        "event_override": event_override,
        "prior_current_event": prior_current_event,
        "prior_behavior_action": prior_behavior_action,
        "prior_behavior_plan": prior_behavior_plan,
        "prior_behavior_agenda": prior_behavior_agenda,
        "agenda_lifecycle_residue": agenda_lifecycle_residue,
        "user_text": user_text,
        "previous_user_text": previous_user_text,
        "prev_assistant": prev_assistant,
        "pending": pending,
        "pending_user_goal": pending_user_goal,
        "continuation_mode": continuation_mode,
        "continuation_seed": continuation_seed,
        "effective_user_text": effective_user_text,
        "science_mode": science_mode,
        "response_style_hint": response_style_hint,
        "external_probe_mode": external_probe_mode,
        "retrieved": retrieved,
        "relationship": relationship,
        "canon_recontact_baseline": canon_recontact_baseline,
        "worldline_focus": worldline_focus,
        "seed_emotion_state": seed_emotion_state,
        "seed_bond_state": seed_bond_state,
        "seed_allostasis_state": seed_allostasis_state,
        "seed_counterpart_assessment": seed_counterpart_assessment,
        "seed_world_model_state": seed_world_model_state,
        "seed_evolution_state": seed_evolution_state,
        "seed_tsundere_intensity": seed_tsundere_intensity,
        "appraisal_event_context": appraisal_event_context,
        "semantic_narrative_profile_for_appraisal": semantic_narrative_profile_for_appraisal,
        "prior_semantic_narrative_profile": prior_semantic_narrative_profile,
        "appraisal": appraisal,
        "current_event": current_event,
        "interaction_carryover": interaction_carryover,
        "recent_events": recent_events,
    }
