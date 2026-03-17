from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from functools import lru_cache
from typing import Any

from langchain_core.tools import BaseTool
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from ..config import (
    ABLATE_CLAIM_ATTRIBUTION,
    ABLATE_LIGHT_DIALOG_SHAPING,
    ABLATE_PERSONA_ALIGNMENT,
    ABLATE_WORLDLINE_MEMORY,
    CANON_COUNTERPART_ALIASES,
    CANON_COUNTERPART_ID,
    CANON_COUNTERPART_NAME,
    CLAIM_REQUIRED_TOOLS,
    CONTEXT_KEEP_LAST_MESSAGES,
    EVAL_MODE,
    OOC_RISK_THRESHOLD,
    PERSONA_GAP_THRESHOLD,
    RUNTIME_MODE,
    TOOLSET_UPGRADE_TTL_S,
    TOOL_CALLS_MAX,
    auto_approve_tool_names,
)
from ..evolution_engine import evolve_turn_state
from ..persona_authority import normalize_override_mode
from ..runtime.session_orchestrator import (
    build_claim_attribution,
    canonicalize_pending_goal_text,
    continuation_seed_text,
    derive_pending_fragment,
    derive_pending_user_goal,
    has_pending_continuation as has_active_continuation,
)
from ..settings import get_settings
from .messages import (
    _compact_thread_if_needed,
    _last_ai_text,
    _last_user_text,
    _latest_ai,
    _messages,
    _previous_user_text,
    _recent_ai_texts,
    _sanitize_message,
    _window_messages,
)
from .persona_runtime import (
    _active_counterpart_profile,
    _active_persona_core,
    _canon_okabe_recontact_baseline,
    _canon_persona_labels,
    _is_external_probe_context,
    _prefer_explicit_state_dict,
    _science_mode_from_context,
    _tsundere_next,
)
from .runtime_services import _audit_jsonl, _get_store, _get_tool_bundle
from .guards import _canon_guard, _ooc_risk, _persona_gap
from .appraisal import _invoke_turn_appraisal
from .memory_evolution import _auto_reconsolidate_after_tool, _passive_evolution_memory_update
from .generation_profile import (
    _daily_surface_profile,
    _ensure_response_structure,
    _generation_profile,
    _is_free_dialog_style,
    _is_light_free_dialog_turn,
)
from .behavior_agenda import (
    _merge_behavior_agenda,
    _promote_due_behavior_action_event,
    _promote_due_behavior_agenda_event,
    _promote_due_behavior_agenda_event_with_residue,
    _promote_due_behavior_plan_event,
)
from .behavior_runtime import (
    _behavior_action_from_state,
    _behavior_plan_from_action,
)
from .postprocess import (
    _clean_utf8_text,
    _dialogue_surface_issues,
    _effective_natural_dialog_target_flags,
    _light_dialog_surface_penalty,
    _needs_structured_answer,
    _producer_surface_issues,
    _response_style_hint,
    _sanitize_final_answer,
)
from .prompting import _build_task_prompt
from .relational import (
    _apply_agenda_lifecycle_residue_to_runtime_state,
    _counterpart_assessment_summary,
    _prefer_refreshed_relationship_state,
    _prefer_relationship_state,
    _recent_interaction_carryover,
    _relationship_has_meaningful_signal,
    _relationship_runtime_snapshot,
    _seeded_interaction_carryover_from_state,
    _worldline_focus,
)
from .retrieval import _empty_retrieved_context, _retrieve_context
from .rewrite import (
    _daily_surface_alignment_metrics,
    _invoke_model_with_retries,
    _light_dialog_rewrite_notes,
    _model,
    _natural_dialog_rewrite_notes_for,
    _norm_text,
    _rewrite_light_dialog_answer,
    _rewrite_natural_dialog_answer,
    _should_run_light_dialog_rewrite,
    _should_run_natural_dialog_rewrite,
)
from .semantic_narrative import _semantic_narrative_profile
from .state import ThreadState
from .tool_policies import MEMORY_WRITE_TOOLS, WORLDLINE_ABLATION_READ_TOOLS
from .tool_runtime import (
    _build_evidence_from_tool_result,
    _invoke_tool,
    _memory_guard_check,
)
from .tooling import _infer_memory_tool_calls, _parse_explicit_tool_call
from .turn_events import (
    _append_recent_events,
    _appraisal_event_context,
    _build_current_event,
    _is_silent_behavior_event,
    _now_ts,
    _normalize_event_override,
    _promote_due_commitment_event,
    _sanitize_obj,
)

_CHECKPOINT_CONN: sqlite3.Connection | None = None

_IDLE_CONTEXT_TAGS = {
    "respect_space",
    "user_busy",
    "cognitive_load",
    "quiet_presence",
    "ambient_echo",
    "from_own_rhythm",
    "own_task",
    "deep_focus",
    "late_night",
}
_OWN_RHYTHM_TAGS = {"from_own_rhythm", "own_task", "deep_focus", "break_window", "small_opening", "reapproach"}
_QUIET_PRESENCE_MODES = {"quiet_recontact", "brief_presence"}
_OWN_RHYTHM_MODES = {"own_rhythm", "small_opening"}
_AMBIENT_ECHO_MODES = {"ambient_echo"}


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _normalize_tag_list(*chunks: Any) -> list[str]:
    ordered: list[str] = []
    for chunk in chunks:
        items = chunk if isinstance(chunk, (list, tuple, set)) else [chunk]
        for item in items:
            text = str(item or "").strip()
            if text and text not in ordered:
                ordered.append(text)
    return ordered


def build_implicit_idle_event_override(
    state: ThreadState | dict[str, Any] | None,
    *,
    idle_minutes: int,
    note: str = "",
    created_at: int | None = None,
    extra_tags: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, Any]:
    seeded: ThreadState = dict(state or {})
    try:
        idle_window = max(1, min(24 * 60, int(idle_minutes)))
    except Exception:
        idle_window = 1
    now_ts = int(created_at or _now_ts())
    event_text = str(note or "").strip() or f"已经安静地过去了 {idle_window} 分钟，没有新的用户消息。"

    prior_event = seeded.get("current_event") if isinstance(seeded.get("current_event"), dict) else {}
    prior_tags = {
        str(item).strip()
        for item in (prior_event.get("tags") if isinstance(prior_event.get("tags"), list) else [])
        if str(item).strip()
    }
    prior_behavior_action = seeded.get("behavior_action") if isinstance(seeded.get("behavior_action"), dict) else {}
    interaction_carryover = seeded.get("interaction_carryover") if isinstance(seeded.get("interaction_carryover"), dict) else {}
    world = seeded.get("world_model_state") if isinstance(seeded.get("world_model_state"), dict) else {}
    assessment = seeded.get("counterpart_assessment") if isinstance(seeded.get("counterpart_assessment"), dict) else {}
    relationship_weather = (
        str(interaction_carryover.get("relationship_weather") or "").strip().lower()
        or str(prior_behavior_action.get("relationship_weather") or "").strip().lower()
        or str(prior_event.get("relationship_weather") or "").strip().lower()
    )
    carryover_mode = str(interaction_carryover.get("carryover_mode") or "").strip().lower()
    carryover_strength = _safe_float(interaction_carryover.get("strength"), 0.0) if interaction_carryover else 0.0
    presence_residue = _safe_float(world.get("presence_residue"), 0.0) if world else 0.0
    ambient_resonance = _safe_float(world.get("ambient_resonance"), 0.0) if world else 0.0
    self_activity_momentum = _safe_float(world.get("self_activity_momentum"), 0.0) if world else 0.0
    action_target = str(prior_behavior_action.get("action_target") or "").strip().lower()
    try:
        timing_window_min = int(prior_behavior_action.get("timing_window_min") or 0) if prior_behavior_action else 0
    except Exception:
        timing_window_min = 0
    stance = str(assessment.get("stance") or "").strip().lower()
    scene = str(assessment.get("scene") or "").strip().lower()

    tags = _normalize_tag_list("time_idle", "ambient", "behavior_layer", extra_tags or [])
    if prior_tags & {"respect_space", "user_busy", "cognitive_load"}:
        tags = _normalize_tag_list(tags, sorted(prior_tags & {"respect_space", "user_busy", "cognitive_load"}))
    if stance == "guarded" and "respect_space" not in tags and prior_tags & {"quiet_presence"}:
        tags = _normalize_tag_list(tags, "respect_space")
    if (
        carryover_mode in _QUIET_PRESENCE_MODES
        or bool(prior_tags & {"quiet_presence", "brief_presence"})
        or presence_residue >= 0.28
    ):
        tags = _normalize_tag_list(tags, "quiet_presence")
    if (
        carryover_mode in _AMBIENT_ECHO_MODES
        or bool(prior_tags & {"ambient_echo"})
        or ambient_resonance >= 0.30
    ):
        tags = _normalize_tag_list(tags, "ambient_echo")
    if (
        carryover_mode in _OWN_RHYTHM_MODES
        or action_target == "hold_own_rhythm"
        or bool(prior_tags & _OWN_RHYTHM_TAGS)
        or self_activity_momentum >= 0.56
    ):
        tags = _normalize_tag_list(tags, "from_own_rhythm")
    if self_activity_momentum >= 0.60 or bool(prior_tags & {"own_task", "deep_focus"}):
        tags = _normalize_tag_list(tags, "own_task")
    if self_activity_momentum >= 0.66 or bool(prior_tags & {"deep_focus"}):
        tags = _normalize_tag_list(tags, "deep_focus")

    try:
        hour = int(datetime.fromtimestamp(now_ts).hour)
    except Exception:
        hour = -1
    if hour >= 23 or 0 <= hour <= 5:
        tags = _normalize_tag_list(tags, "late_night")

    stale_window = False
    if action_target == "wait_and_recheck":
        stale_after = max(45, timing_window_min * 3 if timing_window_min > 0 else 90)
        if idle_window >= stale_after:
            stale_window = True
            tags = _normalize_tag_list(tags, "stale_window")

    frame_parts = [f"和对方之间安静地过去了 {idle_window} 分钟。"]
    if "respect_space" in tags:
        frame_parts.append("这段安静更像是在给对方留空间。")
    elif "user_busy" in tags or "cognitive_load" in tags:
        frame_parts.append("她默认对方大概还在忙，先不急着往前推。")
    if "from_own_rhythm" in tags:
        frame_parts.append("她这段时间仍在自己的节奏里。")
    if "quiet_presence" in tags:
        frame_parts.append("前面那点没说出口的在场感还没有完全退掉。")
    if "ambient_echo" in tags:
        frame_parts.append("环境里残留的细小动静还挂在她的感知边缘。")
    if stale_window:
        frame_parts.append("之前那点低压接近的窗口已经自然过期。")
    if relationship_weather:
        frame_parts.append(f"当前关系天气更接近 {relationship_weather}。")
    elif scene in {"boundary_non_compliance", "relationship_degradation"}:
        frame_parts.append("这轮关系气压偏低。")
    frame_parts.append("现在轮到她决定是否重新抬头。")

    return {
        "kind": "time_idle",
        "source": "time",
        "text": event_text,
        "effective_text": event_text,
        "semantic_goal": "time passed without new user input",
        "response_style_hint": "companion",
        "event_frame": " ".join(frame_parts),
        "tags": tags,
        "idle_minutes": idle_window,
        "created_at": now_ts,
        "relationship_weather": relationship_weather,
        "carryover_mode": carryover_mode,
        "carryover_strength": round(max(0.0, min(1.0, carryover_strength)), 3),
        "presence_residue": round(max(0.0, min(1.0, presence_residue)), 3),
        "ambient_resonance": round(max(0.0, min(1.0, ambient_resonance)), 3),
        "self_activity_momentum": round(max(0.0, min(1.0, self_activity_momentum)), 3),
    }


def _node_prepare_turn(state: ThreadState) -> dict[str, Any]:

    store = _get_store()
    turn_now_ts = _now_ts()
    profile, counterpart_trace = _active_counterpart_profile(state, store, with_trace=True)
    persona_core, persona_trace = _active_persona_core(state, with_trace=True)
    msgs = _messages(state)
    event_override = _normalize_event_override(
        _sanitize_obj(state.get("event_override")),
        counterpart_name=str(profile.get("short_name") or profile.get("nickname") or profile.get("name") or CANON_COUNTERPART_NAME),
    )
    prior_current_event = _sanitize_obj(state.get("current_event")) if isinstance(state.get("current_event"), dict) else {}
    prior_behavior_action = _sanitize_obj(state.get("behavior_action")) if isinstance(state.get("behavior_action"), dict) else {}
    prior_behavior_plan = _sanitize_obj(state.get("behavior_plan")) if isinstance(state.get("behavior_plan"), dict) else {}
    prior_behavior_agenda = _sanitize_obj(state.get("behavior_agenda")) if isinstance(state.get("behavior_agenda"), list) else []
    agenda_lifecycle_residue: dict[str, Any] = {}
    if not prior_behavior_agenda and isinstance(state.get("behavior_queue"), list):
        prior_behavior_agenda = _sanitize_obj(state.get("behavior_queue"))  # type: ignore[assignment]
    had_prior_behavior_queue = bool(prior_behavior_agenda)
    if event_override:
        event_override, prior_behavior_agenda, agenda_lifecycle_residue = _promote_due_behavior_agenda_event_with_residue(
            event_override,
            prior_behavior_agenda,
            counterpart_assessment=state.get("counterpart_assessment") if isinstance(state.get("counterpart_assessment"), dict) else None,
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
            counterpart_name=str(profile.get("short_name") or profile.get("nickname") or profile.get("name") or CANON_COUNTERPART_NAME),
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
        effective_user_text = str(event_override.get("effective_text") or event_override.get("text") or effective_user_text or "").strip()

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
        current_event=event_override if isinstance(event_override, dict) and event_override else None,
    )
    if event_override:
        response_style_hint = str(event_override.get("response_style_hint") or response_style_hint or "natural").strip() or "natural"
    if continuation_mode and continuation_seed and _needs_structured_answer(pending_user_goal or continuation_seed, ""):
        response_style_hint = "structured"
    external_probe_mode = _is_external_probe_context(persona_core=persona_core, counterpart_profile=profile)
    retrieved = _empty_retrieved_context(store) if external_probe_mode else _retrieve_context(effective_user_text or user_text, store)
    retrieved_relationship = retrieved.get("relationship") if isinstance(retrieved.get("relationship"), dict) else store.get_relationship()
    relationship = _relationship_runtime_snapshot(
        relationship=_prefer_relationship_state(
            state.get("relationship") if isinstance(state.get("relationship"), dict) else None,
            retrieved_relationship,
        ),
        bond_state=state.get("bond_state") if isinstance(state.get("bond_state"), dict) else None,
        world_model_state=state.get("world_model_state") if isinstance(state.get("world_model_state"), dict) else None,
        counterpart_assessment=state.get("counterpart_assessment") if isinstance(state.get("counterpart_assessment"), dict) else None,
        semantic_narrative_profile=state.get("semantic_narrative_profile") if isinstance(state.get("semantic_narrative_profile"), dict) else None,
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
        canon_recontact_baseline.get("counterpart_assessment") if isinstance(canon_recontact_baseline, dict) else None,
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
        counterpart_name=str(profile.get("short_name") or profile.get("nickname") or profile.get("name") or CANON_COUNTERPART_NAME),
        pending_user_goal=pending_user_goal,
        event_override=event_override,
    )
    semantic_narrative_profile_for_appraisal = _semantic_narrative_profile(
        retrieved.get("semantic_self_narratives") if isinstance(retrieved.get("semantic_self_narratives"), list) else [],
        user_text=effective_user_text or user_text,
        current_event=appraisal_event_context,
    )
    appraisal_interaction_carryover = _recent_interaction_carryover(
        prior_current_event=prior_current_event if isinstance(prior_current_event, dict) else {},
        prior_behavior_action=prior_behavior_action if isinstance(prior_behavior_action, dict) else {},
        prior_agenda_lifecycle_residue=state.get("agenda_lifecycle_residue") if isinstance(state.get("agenda_lifecycle_residue"), dict) else {},
        prior_counterpart_assessment=state.get("counterpart_assessment") if isinstance(state.get("counterpart_assessment"), dict) else {},
        recent_events=state.get("recent_events"),
        current_event=appraisal_event_context,
        response_style_hint=response_style_hint,
    )
    if not appraisal_interaction_carryover:
        appraisal_interaction_carryover = _seeded_interaction_carryover_from_state(
            state=state,
            prior_current_event=prior_current_event if isinstance(prior_current_event, dict) else {},
            prior_behavior_action=prior_behavior_action if isinstance(prior_behavior_action, dict) else {},
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
        current_event=appraisal_event_context,
    )
    current_event = (
        {
            **dict(appraisal_event_context),
            "appraisal_label": str(appraisal.get("emotion_label") or appraisal.get("label") or appraisal_event_context.get("appraisal_label") or "").strip(),
            "appraisal_confidence": float(appraisal.get("confidence", 0.0) or appraisal_event_context.get("appraisal_confidence") or 0.0),
            "created_at": int(appraisal_event_context.get("created_at") or _now_ts()),
        }
        if event_override
        else _build_current_event(
            user_text=user_text,
            effective_text=effective_user_text or user_text,
            response_style_hint=response_style_hint,
            science_mode=science_mode,
            continuation_mode=continuation_mode,
            appraisal=appraisal,
            counterpart_name=str(profile.get("short_name") or profile.get("nickname") or profile.get("name") or CANON_COUNTERPART_NAME),
            pending_user_goal=pending_user_goal,
        )
    )
    interaction_carryover = _recent_interaction_carryover(
        prior_current_event=prior_current_event if isinstance(prior_current_event, dict) else {},
        prior_behavior_action=prior_behavior_action if isinstance(prior_behavior_action, dict) else {},
        prior_agenda_lifecycle_residue=state.get("agenda_lifecycle_residue") if isinstance(state.get("agenda_lifecycle_residue"), dict) else {},
        prior_counterpart_assessment=state.get("counterpart_assessment") if isinstance(state.get("counterpart_assessment"), dict) else {},
        recent_events=state.get("recent_events"),
        current_event=current_event,
        response_style_hint=response_style_hint,
    )
    if not interaction_carryover:
        interaction_carryover = _seeded_interaction_carryover_from_state(
            state=state,
            prior_current_event=prior_current_event if isinstance(prior_current_event, dict) else {},
            prior_behavior_action=prior_behavior_action if isinstance(prior_behavior_action, dict) else {},
        )
    recent_events = _append_recent_events(_sanitize_obj(state.get("recent_events")), current_event, limit=6)

    persona_state = dict(state.get("persona_state") or {})
    if bool(ABLATE_PERSONA_ALIGNMENT):
        emotion_state = {"label": "neutral", "valence": 0.0, "arousal": 0.25}
        bond_state = {"trust": 0.5, "closeness": 0.5, "hurt": 0.0, "irritation": 0.0, "engagement_drive": 0.5, "repair_confidence": 0.5}
        allostasis_state = {"safety_need": 0.2, "closeness_need": 0.18, "competence_need": 0.38, "autonomy_need": 0.12, "cognitive_budget": 0.7, "relational_security": 0.5}
        counterpart_assessment = {"respect_level": 0.5, "reciprocity": 0.5, "boundary_pressure": 0.1, "reliability_read": 0.5, "stance": "open", "scene": "neutral"}
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
                "narrative_ref": str(persona_core.get("narrative_ref") or persona_core.get("display_name") or canon_labels.get("narrative_ref") or "红莉栖"),
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
            retrieved.get("semantic_self_narratives") if isinstance(retrieved.get("semantic_self_narratives"), list) else [],
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
        refreshed_relationship = retrieved.get("relationship") if isinstance(retrieved.get("relationship"), dict) else store.get_relationship()
        relationship = _prefer_refreshed_relationship_state(relationship, refreshed_relationship)
        worldline_focus = _worldline_focus(store)
        semantic_narrative_profile = _semantic_narrative_profile(
            retrieved.get("semantic_self_narratives") if isinstance(retrieved.get("semantic_self_narratives"), list) else [],
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
            retrieved.get("semantic_self_narratives") if isinstance(retrieved.get("semantic_self_narratives"), list) else [],
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
        "persona_core_override": dict(state.get("persona_core_override") or {}),
        "counterpart_profile_override": dict(state.get("counterpart_profile_override") or {}),
        "persona_override_mode": normalize_override_mode(state.get("persona_override_mode")),
        "counterpart_override_mode": normalize_override_mode(state.get("counterpart_override_mode")),
        "authority_trace": {
            "persona": persona_trace,
            "counterpart": counterpart_trace,
        },
        "relationship": relationship,
        "world_model_state": world_model_state,
        "evolution_state": evolution_state,
        "reconsolidation_snapshot": reconsolidation_snapshot,
        "persona_state": persona_state,
        "emotion_state": emotion_state,
        "bond_state": bond_state,
        "allostasis_state": allostasis_state,
        "counterpart_assessment": counterpart_assessment,
        "semantic_narrative_profile": semantic_narrative_profile,
        "behavior_policy": behavior_policy,
        "behavior_action": behavior_action,
        "behavior_plan": behavior_plan,
        "behavior_agenda": behavior_agenda,
        "behavior_queue": behavior_agenda,
        "turn_appraisal": appraisal,
        "current_event": _sanitize_obj(current_event),
        "recent_events": _sanitize_obj(recent_events),
        "interaction_carryover": interaction_carryover,
        "agenda_lifecycle_residue": agenda_lifecycle_residue,
        "response_style_hint": response_style_hint,
        "science_mode": science_mode,
        "tsundere_intensity": tsundere,
        "retrieved_context": retrieved,
        "worldline_focus": worldline_focus,
        "pending_utterance_fragment": _clean_utf8_text(pending),
        "pending_user_goal": _clean_utf8_text(pending_user_goal),
        "tool_round": int(state.get("tool_round", 0)),
        "toolset_unlocks": dict(state.get("toolset_unlocks") or {}),
        "evidence_pack": list(state.get("evidence_pack") or []),
        "last_external_tools": list(state.get("last_external_tools") or []),
        "memory_guard_checked": int(state.get("memory_guard_checked", 0) or 0),
        "memory_guard_blocked": int(state.get("memory_guard_blocked", 0) or 0),
        "event_override": {},
    }


def _available_tools_for_state(state: ThreadState) -> list[BaseTool]:
    if _is_external_probe_context(state=state):
        return []
    bundle = _get_tool_bundle()
    unlocks = dict(state.get("toolset_unlocks") or {})
    now = _now_ts()
    active = {k for k, exp in unlocks.items() if int(exp) > now}
    worldline_ablation = bool(ABLATE_WORLDLINE_MEMORY)

    tools: list[BaseTool] = []
    for t in bundle.base_tools:
        if t is not None:
            if worldline_ablation and str(getattr(t, "name", "") or "") in WORLDLINE_ABLATION_READ_TOOLS:
                continue
            tools.append(t)
    for t in bundle.extended_tools:
        if t is None:
            continue
        name = str(getattr(t, "name", "") or "")
        if worldline_ablation and name in WORLDLINE_ABLATION_READ_TOOLS:
            continue
        if name in active:
            tools.append(t)
    return tools


def build_implicit_idle_state_update(
    state: ThreadState | dict[str, Any] | None,
    *,
    idle_minutes: int,
    note: str = "",
    created_at: int | None = None,
) -> dict[str, Any]:
    seeded: ThreadState = dict(state or {})
    seeded["event_override"] = build_implicit_idle_event_override(
        seeded,
        idle_minutes=idle_minutes,
        note=note,
        created_at=created_at,
        extra_tags=["implicit_idle"],
    )
    return _node_prepare_turn(seeded)


def _tool_limit_fallback_text(state: ThreadState) -> str:
    user_text = _last_user_text(_messages(state))
    if any(marker in user_text for marker in {"记得", "回忆", "上次", "之前", "继续"}):
        text = "我一下子还接不上刚才那段。你把最关键的那句再给我一下，我就顺着接回去。"
    elif any(marker in user_text for marker in {"检索", "搜索", "文档", "资料"}):
        text = "这轮我先停在这里。再继续盲查意义不大，你把关键词再收紧一点，我就继续往下翻。"
    else:
        text = "我先停在这里。再硬往下翻只会越说越乱，你把问题再收紧一点，我就继续。"
    return _ensure_response_structure(text.replace("\\n", "\n"), user_text)


def _node_call_model(state: ThreadState) -> dict[str, Any]:
    store = _get_store()
    msgs = _messages(state)
    user_text = _clean_utf8_text(_last_user_text(msgs))
    pending_fragment = str(state.get("pending_utterance_fragment") or "").strip()
    pending_user_goal = str(state.get("pending_user_goal") or "").strip()
    continuation_mode = has_active_continuation(user_text=user_text, pending_fragment=pending_fragment)
    continuation_seed = continuation_seed_text(
        pending_user_goal=pending_user_goal,
        pending_fragment=pending_fragment,
    )
    active_continuation = continuation_mode and bool(continuation_seed)
    prompt = _build_task_prompt(state, user_text, store)
    history = _window_messages(msgs, int(CONTEXT_KEEP_LAST_MESSAGES))
    recent_assistant_texts = _recent_ai_texts(msgs, limit=4)
    call_msgs: list[BaseMessage] = [_sanitize_message(SystemMessage(content=prompt))]
    if active_continuation:
        call_msgs.extend(_sanitize_message(m) for m in history[-4:])
        continuation_lines = [
            "这是一次续说，不是新回答。",
            "直接顺着刚才未完成的内容往下说，不要先解释你在续哪一段，也不要重复用户的指令。",
        ]
        if pending_fragment:
            continuation_lines.append(f"未完成片段：{pending_fragment[:240]}")
        if pending_user_goal:
            continuation_lines.append(f"原始任务焦点：{canonicalize_pending_goal_text(pending_user_goal)[:220]}")
        continuation_lines.append(f"现在就从这里接着往下说：{continuation_seed[:240]}")
        call_msgs.append(_sanitize_message(HumanMessage(content="\n".join(continuation_lines))))
    else:
        call_msgs.extend(_sanitize_message(m) for m in history)

    tools = _available_tools_for_state(state)
    should_force = bool(msgs and isinstance(msgs[-1], HumanMessage))
    forced_tcs: list[dict[str, Any]] = []
    if should_force:
        forced_tcs = _parse_explicit_tool_call(user_text, tools) or []
        if not forced_tcs:
            forced_tcs = _infer_memory_tool_calls(user_text)
        else:
            forced_tcs = list(forced_tcs)
    if forced_tcs:
        return {"messages": [AIMessage(content="", tool_calls=forced_tcs)]}

    response_style_hint = str(state.get("response_style_hint") or "natural").strip() or "natural"
    free_dialog = _is_free_dialog_style(response_style_hint, user_text, bool(state.get("science_mode", False)))
    current_event = state.get("current_event") if isinstance(state.get("current_event"), dict) else {}
    behavior_action = state.get("behavior_action") if isinstance(state.get("behavior_action"), dict) else {}
    current_event_kind = str(current_event.get("kind") or "user_utterance").strip()
    light_free_dialog = _is_light_free_dialog_turn(
        user_text=user_text,
        response_style_hint=response_style_hint,
        science_mode=bool(state.get("science_mode", False)),
        continuation_mode=active_continuation,
        current_event_kind=current_event_kind,
    )
    if active_continuation:
        tools = []
        if _needs_structured_answer(pending_user_goal or continuation_seed, ""):
            free_dialog = False
        else:
            free_dialog = True
        light_free_dialog = False
    generation_profile = _generation_profile(
        response_style_hint=response_style_hint,
        science_mode=bool(state.get("science_mode", False)),
        continuation_mode=active_continuation,
        user_text=user_text,
        runtime_mode=RUNTIME_MODE,
        turn_index=len(msgs),
        recent_assistant_texts=recent_assistant_texts,
        current_event=state.get("current_event") if isinstance(state.get("current_event"), dict) else {},
        emotion_state=state.get("emotion_state") if isinstance(state.get("emotion_state"), dict) else {},
        bond_state=state.get("bond_state") if isinstance(state.get("bond_state"), dict) else {},
        allostasis_state=state.get("allostasis_state") if isinstance(state.get("allostasis_state"), dict) else {},
        counterpart_assessment=state.get("counterpart_assessment") if isinstance(state.get("counterpart_assessment"), dict) else {},
        behavior_policy=state.get("behavior_policy") if isinstance(state.get("behavior_policy"), dict) else {},
        world_model_state=state.get("world_model_state") if isinstance(state.get("world_model_state"), dict) else {},
        behavior_action=behavior_action,
        interaction_carryover=state.get("interaction_carryover") if isinstance(state.get("interaction_carryover"), dict) else {},
        semantic_narrative_profile=state.get("semantic_narrative_profile") if isinstance(state.get("semantic_narrative_profile"), dict) else {},
    )
    generation_runtime_mode = str(generation_profile.pop("runtime_mode", RUNTIME_MODE) or RUNTIME_MODE)
    generation_repetition_pressure = float(generation_profile.pop("repetition_pressure", 0.0) or 0.0)
    generation_recent_reply_max_similarity = float(generation_profile.pop("recent_reply_max_similarity", 0.0) or 0.0)
    generation_recent_reply_avg_similarity = float(generation_profile.pop("recent_reply_avg_similarity", 0.0) or 0.0)
    generation_recent_reply_opener_repeat_ratio = float(generation_profile.pop("recent_reply_opener_repeat_ratio", 0.0) or 0.0)
    generation_recent_reply_sample_size = int(generation_profile.pop("recent_reply_sample_size", 0) or 0)
    chosen_generation_profile: dict[str, Any] = {}
    for key in ("temperature", "top_p", "frequency_penalty", "presence_penalty"):
        value = generation_profile.get(key)
        if value is None:
            continue
        if bool(EVAL_MODE) and key == "temperature":
            # Keep eval generation temperature pinned by the shared eval env for repeatability.
            continue
        chosen_generation_profile[key] = float(value)
    max_tokens = generation_profile.get("max_tokens")
    if max_tokens is not None:
        chosen_generation_profile["max_tokens"] = int(max_tokens)
    llm = _model(**chosen_generation_profile)
    llm_tools = llm if free_dialog else (llm.bind_tools(tools) if tools else llm)
    ai = _invoke_model_with_retries(llm_tools, call_msgs)
    if not isinstance(ai, AIMessage):
        ai = AIMessage(content=str(getattr(ai, "content", "") or ""))

    tool_calls = list(getattr(ai, "tool_calls", None) or [])
    if tool_calls:
        return {"messages": [ai]}

    raw_draft_text = str(ai.content or "")
    draft_generation_issues = _producer_surface_issues(raw_draft_text)
    draft_text = _sanitize_final_answer(
        raw_draft_text,
        user_text,
        current_event=current_event,
        behavior_action=behavior_action,
    )
    aligned = draft_text
    draft_risk, draft_flags = _ooc_risk(draft_text)
    draft_gap, draft_gap_flags = _persona_gap(draft_text, state)
    draft_dialogue_issues = _dialogue_surface_issues(
        user_text,
        draft_text,
        response_style_hint=response_style_hint,
        science_mode=bool(state.get("science_mode", False)),
        current_event=current_event,
        behavior_action=behavior_action,
    )
    alignment_applied = False
    alignment_reasons: list[str] = []
    light_dialog_rewrite_applied = False
    light_dialog_rewrite_notes: list[str] = []
    natural_dialog_rewrite_applied = False
    natural_dialog_rewrite_notes: list[str] = []
    light_dialog_draft_penalty = 0.0
    light_dialog_final_penalty = 0.0
    light_dialog_draft_pref_score = 0.0
    light_dialog_final_pref_score = 0.0
    response_style_hint = str(state.get("response_style_hint") or "natural").strip() or "natural"
    semantic_narrative_profile = state.get("semantic_narrative_profile") if isinstance(state.get("semantic_narrative_profile"), dict) else {}
    semantic_history_weight = float(semantic_narrative_profile.get("history_weight") or 0.0)
    semantic_prompt_anchor_count = len(
        [
            str(item).strip()
            for item in (
                semantic_narrative_profile.get("prompt_anchor_lines")
                if isinstance(semantic_narrative_profile.get("prompt_anchor_lines"), list)
                else []
            )
            if str(item or "").strip()
        ]
    )
    light_dialog_profile = (
        _daily_surface_profile(user_text, science_mode=bool(state.get("science_mode", False)))
        if light_free_dialog
        else {}
    )

    evidence_pack = list(state.get("evidence_pack") or [])
    if light_free_dialog:
        draft_pref = _daily_surface_alignment_metrics(draft_text, profile=light_dialog_profile)
        light_dialog_draft_pref_score = float(draft_pref.get("score") or 0.0)
        light_dialog_rewrite_notes = _light_dialog_rewrite_notes(
            user_text,
            draft_text,
            response_style_hint=response_style_hint,
            science_mode=bool(state.get("science_mode", False)),
            producer_issues=draft_generation_issues,
            behavior_action=behavior_action,
        )
        light_dialog_draft_penalty = _light_dialog_surface_penalty(
            user_text,
            draft_text,
            response_style_hint=response_style_hint,
            science_mode=bool(state.get("science_mode", False)),
            producer_issues=draft_generation_issues,
            behavior_action=behavior_action,
        )
        light_dialog_final_penalty = light_dialog_draft_penalty
        needs_alt_candidate = _should_run_light_dialog_rewrite(
            user_text=user_text,
            answer=draft_text,
            response_style_hint=response_style_hint,
            science_mode=bool(state.get("science_mode", False)),
            penalty=light_dialog_draft_penalty,
            preference=draft_pref,
            semantic_history_weight=semantic_history_weight,
            prompt_anchor_count=semantic_prompt_anchor_count,
            producer_issues=draft_generation_issues,
            behavior_action=behavior_action,
        )
        if needs_alt_candidate and not light_dialog_rewrite_notes:
            light_dialog_rewrite_notes = ["这版还不够像熟人之间顺手接住的轻日常，收得更自然一点。"]
        if needs_alt_candidate:
            rewritten = _rewrite_light_dialog_answer(
                user_text=user_text,
                draft_text=draft_text,
                rewrite_notes=light_dialog_rewrite_notes,
                producer_issues=draft_generation_issues,
                focus_text=str(light_dialog_profile.get("focus") or ""),
                preferred_examples=list(light_dialog_profile.get("chosen_examples") or []),
                rejected_examples=list(light_dialog_profile.get("rejected_examples") or []),
                current_event=current_event,
                behavior_action=behavior_action,
                interaction_carryover=state.get("interaction_carryover") if isinstance(state.get("interaction_carryover"), dict) else {},
                semantic_narrative_profile=state.get("semantic_narrative_profile") if isinstance(state.get("semantic_narrative_profile"), dict) else {},
                counterpart_assessment=state.get("counterpart_assessment") if isinstance(state.get("counterpart_assessment"), dict) else {},
                world_model_state=state.get("world_model_state") if isinstance(state.get("world_model_state"), dict) else {},
            )
            if rewritten:
                rewritten_pref = _daily_surface_alignment_metrics(rewritten, profile=light_dialog_profile)
                rewritten_pref_score = float(rewritten_pref.get("score") or 0.0)
                rewritten_penalty = _light_dialog_surface_penalty(
                    user_text,
                    rewritten,
                    response_style_hint=response_style_hint,
                    science_mode=bool(state.get("science_mode", False)),
                    behavior_action=behavior_action,
                )
                light_dialog_final_penalty = rewritten_penalty
                light_dialog_final_pref_score = rewritten_pref_score
                draft_total = light_dialog_draft_pref_score - light_dialog_draft_penalty
                rewritten_total = rewritten_pref_score - rewritten_penalty
                strong_case_match = float(light_dialog_profile.get("score") or 0.0) >= 0.95
                low_pref_case = light_dialog_draft_pref_score < 0.16
                if rewritten_total > draft_total + 0.04 or (
                    rewritten_total >= draft_total
                    and rewritten_penalty <= light_dialog_draft_penalty
                    and _norm_text(rewritten) != _norm_text(draft_text)
                ) or (
                    strong_case_match
                    and low_pref_case
                    and rewritten_total >= draft_total - 0.02
                    and rewritten_penalty <= light_dialog_draft_penalty + 0.05
                    and _norm_text(rewritten) != _norm_text(draft_text)
                ):
                    aligned = rewritten
                    alignment_applied = True
                    light_dialog_rewrite_applied = True
                    if light_dialog_rewrite_notes:
                        alignment_reasons.extend(light_dialog_rewrite_notes)
                    else:
                        alignment_reasons.append(
                            "daily_surface_rewrite:" + str(light_dialog_profile.get("case_name") or "matched_case")
                        )
                else:
                    light_dialog_final_penalty = light_dialog_draft_penalty
                    light_dialog_final_pref_score = light_dialog_draft_pref_score
            else:
                light_dialog_final_pref_score = light_dialog_draft_pref_score
        aligned = _sanitize_final_answer(
            aligned,
            user_text,
            current_event=current_event,
            behavior_action=behavior_action,
        )
        if not light_dialog_final_pref_score:
            light_dialog_final_pref_score = light_dialog_draft_pref_score
    if (
        not light_free_dialog
        and not continuation_mode
        and not bool(_needs_structured_answer(user_text, draft_text))
        and response_style_hint in {"relationship", "companion", "casual", "natural", "selfhood", "structured"}
    ):
        rewrite_issue_keys = {
            "meta_self_explainer",
            "selfhood_meta_proof",
            "selfhood_rhetorical_opening",
            "defensive_meta",
            "defensive_meta_tone",
            "counselor_tone",
            "quoted_stagey_phrase",
            "malformed_quote_fragment",
            "dangling_truncated_clause",
            "technical_self_activity",
            "technical_relational_metaphor",
            "servile_availability",
            "overquestioning",
            "closing_interrogation",
            "idle_call_interrogation",
            "presence_check_questioning",
            "return_interrogation",
            "event_interrogative_push",
            "event_pushy_directive",
            "event_window_task_reframe",
        }
        targeted_flags = list(dict.fromkeys(list(draft_dialogue_issues) + list(draft_gap_flags)))
        current_gap, current_gap_flags = _persona_gap(aligned, state)
        current_dialogue_issues = _dialogue_surface_issues(
            user_text,
            aligned,
            response_style_hint=response_style_hint,
            science_mode=bool(state.get("science_mode", False)),
            current_event=current_event,
            behavior_action=behavior_action,
        )
        effective_targeted_flags = _effective_natural_dialog_target_flags(
            targeted_flags=targeted_flags,
            active_dialogue_issues=current_dialogue_issues,
            active_gap_flags=current_gap_flags,
            producer_issues=draft_generation_issues,
        )
        natural_dialog_rewrite_notes = _natural_dialog_rewrite_notes_for(
            [item for item in effective_targeted_flags if item in rewrite_issue_keys]
        )
        if natural_dialog_rewrite_notes and _should_run_natural_dialog_rewrite(
            targeted_flags=effective_targeted_flags,
            draft_gap=current_gap,
            semantic_history_weight=semantic_history_weight,
            prompt_anchor_count=semantic_prompt_anchor_count,
            answer=aligned,
            behavior_action=behavior_action,
        ):
            rewritten = _rewrite_natural_dialog_answer(
                user_text=user_text,
                draft_text=aligned,
                rewrite_notes=natural_dialog_rewrite_notes,
                response_style_hint=response_style_hint,
                science_mode=bool(state.get("science_mode", False)),
                current_event=current_event,
                behavior_action=behavior_action,
                interaction_carryover=state.get("interaction_carryover") if isinstance(state.get("interaction_carryover"), dict) else {},
                semantic_narrative_profile=state.get("semantic_narrative_profile") if isinstance(state.get("semantic_narrative_profile"), dict) else {},
                counterpart_assessment=state.get("counterpart_assessment") if isinstance(state.get("counterpart_assessment"), dict) else {},
                world_model_state=state.get("world_model_state") if isinstance(state.get("world_model_state"), dict) else {},
            )
            if rewritten:
                rewritten_gap, rewritten_gap_flags = _persona_gap(rewritten, state)
                rewritten_issues = _dialogue_surface_issues(
                    user_text,
                    rewritten,
                    response_style_hint=response_style_hint,
                    science_mode=bool(state.get("science_mode", False)),
                    current_event=current_event,
                    behavior_action=behavior_action,
                )
                targeted_issue_set = set(rewrite_issue_keys)
                draft_issue_pressure = sum(1 for item in effective_targeted_flags if item in targeted_issue_set)
                rewritten_pressure = sum(1 for item in list(rewritten_issues) + list(rewritten_gap_flags) if item in targeted_issue_set)
                if (
                    rewritten_pressure < draft_issue_pressure
                    or rewritten_gap + 0.05 < current_gap
                ) and _norm_text(rewritten) != _norm_text(aligned):
                    aligned = rewritten
                    alignment_applied = True
                    natural_dialog_rewrite_applied = True
                    alignment_reasons.extend(natural_dialog_rewrite_notes)
    aligned = _ensure_response_structure(aligned, user_text)
    claims = [] if bool(ABLATE_CLAIM_ATTRIBUTION) else build_claim_attribution(aligned, evidence_pack)
    ext_tools = set(state.get("last_external_tools") or [])
    if ext_tools and not claims and not bool(ABLATE_CLAIM_ATTRIBUTION):
        aligned = aligned.strip() + "\n\n(外部信息未形成可追溯证据链，以上结论按暂定处理。)"
        aligned = _sanitize_final_answer(
            aligned,
            user_text,
            current_event=current_event,
            behavior_action=behavior_action,
        )
        aligned = _ensure_response_structure(aligned, user_text)
        claims = [] if bool(ABLATE_CLAIM_ATTRIBUTION) else build_claim_attribution(aligned, evidence_pack)

    risk, flags = _ooc_risk(aligned)
    gap, gap_flags = _persona_gap(aligned, state)
    dialogue_issues = _dialogue_surface_issues(
        user_text,
        aligned,
        response_style_hint=response_style_hint,
        science_mode=bool(state.get("science_mode", False)),
        current_event=current_event,
        behavior_action=behavior_action,
    )
    canon = _canon_guard(aligned, store)
    canon_risk = min(1.0, risk + (0.3 if not bool(canon.get("ok")) else 0.0))
    final_msg = AIMessage(content=aligned)
    behavior_snapshot = {
        "interaction_mode": str(behavior_action.get("interaction_mode") or ""),
        "followup_intent": str(behavior_action.get("followup_intent") or ""),
        "action_target": str(behavior_action.get("action_target") or ""),
        "relationship_weather": str(behavior_action.get("relationship_weather") or ""),
    }
    return {
        "messages": [final_msg],
        "ooc_detector": {
            "draft_risk": draft_risk,
            "draft_gap": draft_gap,
            "draft_flags": draft_flags,
            "draft_gap_flags": draft_gap_flags,
            "draft_generation_issues": draft_generation_issues,
            "draft_dialogue_issues": draft_dialogue_issues,
            "risk": risk,
            "flags": flags,
            "gap": gap,
            "gap_flags": gap_flags,
            "dialogue_issues": dialogue_issues,
            "threshold": float(OOC_RISK_THRESHOLD),
            "persona_gap_threshold": float(PERSONA_GAP_THRESHOLD),
            "alignment_applied": alignment_applied,
            "alignment_reasons": list(dict.fromkeys(alignment_reasons)),
            "response_strategy": "single_pass_final_diagnostics",
            "light_dialog_rewrite_applied": light_dialog_rewrite_applied,
            "light_dialog_rewrite_notes": light_dialog_rewrite_notes,
            "natural_dialog_rewrite_applied": natural_dialog_rewrite_applied,
            "natural_dialog_rewrite_notes": natural_dialog_rewrite_notes,
            "light_dialog_draft_penalty": light_dialog_draft_penalty,
            "light_dialog_final_penalty": light_dialog_final_penalty,
            "light_dialog_case_name": str(light_dialog_profile.get("case_name") or ""),
            "light_dialog_case_match_score": float(light_dialog_profile.get("score") or 0.0),
            "light_dialog_draft_pref_score": light_dialog_draft_pref_score,
            "light_dialog_final_pref_score": light_dialog_final_pref_score,
            "behavior_snapshot": behavior_snapshot,
            "ablation_persona_alignment": bool(ABLATE_PERSONA_ALIGNMENT),
            "ablation_worldline_memory": bool(ABLATE_WORLDLINE_MEMORY),
            "ablation_claim_attribution": bool(ABLATE_CLAIM_ATTRIBUTION),
            "ablation_light_dialog_shaping": bool(ABLATE_LIGHT_DIALOG_SHAPING),
            "generation_profile": {
                **chosen_generation_profile,
                "runtime_mode": generation_runtime_mode,
                "repetition_pressure": generation_repetition_pressure,
                "recent_reply_max_similarity": generation_recent_reply_max_similarity,
                "recent_reply_avg_similarity": generation_recent_reply_avg_similarity,
                "recent_reply_opener_repeat_ratio": generation_recent_reply_opener_repeat_ratio,
                "recent_reply_sample_size": generation_recent_reply_sample_size,
            },
        },
        "canon_guard": canon,
        "canon_risk_score": canon_risk,
        "claim_links": claims,
    }

def _node_tool_limit(state: ThreadState) -> dict[str, Any]:
    msgs = _messages(state)
    ai = _latest_ai(msgs)
    tool_msgs: list[ToolMessage] = []
    for tc in list(getattr(ai, "tool_calls", None) or []):
        tc_id = str(tc.get("id") or "")
        if not tc_id:
            continue
        payload = {
            "ok": False,
            "error": {
                "code": "TOOL_LIMIT",
                "message": f"tool calls exceeded max={int(TOOL_CALLS_MAX)} for this turn",
            },
        }
        tool_msgs.append(ToolMessage(content=_safe_json(payload), tool_call_id=tc_id))

    msg = AIMessage(content=_tool_limit_fallback_text(state))
    return {"messages": [*tool_msgs, msg]}


def _node_tool_gate(state: ThreadState) -> dict[str, Any]:
    msgs = _messages(state)
    ai = _latest_ai(msgs)
    if ai is None:
        return {"approval_actions": []}

    tool_calls = list(getattr(ai, "tool_calls", None) or [])
    if not tool_calls:
        return {"approval_actions": []}

    auto_set = auto_approve_tool_names()
    queued: list[dict[str, Any]] = []
    need_human: list[dict[str, Any]] = []
    order: list[str] = []

    for tc in tool_calls:
        tc_id = str(tc.get("id") or "")
        name = str(tc.get("name") or "")
        args = tc.get("args") if isinstance(tc.get("args"), dict) else {}
        if not tc_id:
            tc_id = f"call_{len(order)}"
        order.append(tc_id)
        row = {"id": tc_id, "name": name, "args": args}
        if name in auto_set:
            queued.append({**row, "action": "approve"})
        else:
            need_human.append(row)

    if need_human:
        source = (
            "memory"
            if any(str(x.get("name") or "") in MEMORY_WRITE_TOOLS for x in need_human)
            else "dialog"
        )
        resume = interrupt(
            {
                "kind": "tool_approval",
                "source": source,
                "tool_calls": need_human,
            }
        )

        decisions: list[dict[str, Any]] = []
        if isinstance(resume, dict):
            dec = resume.get("decisions")
            if isinstance(dec, list):
                decisions = [d for d in dec if isinstance(d, dict)]

        for i, row in enumerate(need_human):
            d = decisions[i] if i < len(decisions) else {"action": "reject"}
            action = str(d.get("action") or "reject").strip().lower()
            if action not in {"approve", "reject", "edit"}:
                action = "reject"
            edit_args = d.get("args") if isinstance(d.get("args"), dict) else row["args"]
            queued.append(
                {
                    **row,
                    "action": action,
                    "args": edit_args,
                    "reason": str(d.get("reason") or "").strip(),
                }
            )

    rank = {tc_id: idx for idx, tc_id in enumerate(order)}
    queued.sort(key=lambda x: rank.get(str(x.get("id")), 10_000))
    return {"approval_actions": queued}


def _tool_lookup(name: str) -> BaseTool | None:
    bundle = _get_tool_bundle()
    for t in [*bundle.base_tools, *bundle.extended_tools]:
        if t is None:
            continue
        if str(getattr(t, "name", "") or "") == name:
            return t
    return None


def _node_tool_execute(state: ThreadState) -> dict[str, Any]:
    store = _get_store()
    msgs = _messages(state)
    ai = _latest_ai(msgs)
    if ai is None:
        return {"approval_actions": []}

    tool_calls = list(getattr(ai, "tool_calls", None) or [])
    actions = list(state.get("approval_actions") or [])
    action_map = {str(a.get("id") or ""): a for a in actions}

    unlocks = dict(state.get("toolset_unlocks") or {})
    evidence_pack = list(state.get("evidence_pack") or [])
    external_tools = set(state.get("last_external_tools") or [])
    guard_checked = int(state.get("memory_guard_checked", 0) or 0)
    guard_blocked = int(state.get("memory_guard_blocked", 0) or 0)

    tool_msgs: list[ToolMessage] = []
    for tc in tool_calls:
        tc_id = str(tc.get("id") or "")
        name = str(tc.get("name") or "")
        args = tc.get("args") if isinstance(tc.get("args"), dict) else {}
        decision = action_map.get(tc_id, {"action": "reject", "reason": "no decision"})
        action = str(decision.get("action") or "reject").strip().lower()
        if action == "edit" and isinstance(decision.get("args"), dict):
            args = dict(decision.get("args"))

        record: dict[str, Any] = {
            "tool": name,
            "tool_call_id": tc_id,
            "action": action,
            "args": args,
        }

        if action == "reject":
            reason = str(decision.get("reason") or "rejected").strip()
            payload = {"ok": False, "error": {"code": "REJECTED", "message": reason}}
            tool_msgs.append(ToolMessage(content=_safe_json(payload), tool_call_id=tc_id))
            record["result"] = payload
            _audit_jsonl("tool_audit.jsonl", record)
            continue

        if name in MEMORY_WRITE_TOOLS:
            guard_checked += 1
        ok, reason = _memory_guard_check(name, args, store)
        if not ok:
            guard_blocked += 1
            payload = {"ok": False, "error": {"code": "MEMORY_GUARD_BLOCKED", "message": reason}}
            tool_msgs.append(ToolMessage(content=_safe_json(payload), tool_call_id=tc_id))
            record["result"] = payload
            _audit_jsonl("tool_audit.jsonl", record)
            continue

        tool = _tool_lookup(name)
        if tool is None:
            payload = {"ok": False, "error": {"code": "TOOL_NOT_FOUND", "message": name}}
            tool_msgs.append(ToolMessage(content=_safe_json(payload), tool_call_id=tc_id))
            record["result"] = payload
            _audit_jsonl("tool_audit.jsonl", record)
            continue

        try:
            result = _invoke_tool(tool, args)
            _auto_reconsolidate_after_tool(
                store,
                tool_name=name,
                args=args,
                result=result,
            )
            payload = {"ok": True, "data": result}
            tool_msgs.append(ToolMessage(content=_safe_json(payload), tool_call_id=tc_id))

            if name == "request_toolset_upgrade" and isinstance(result, dict):
                req = result.get("requested_tools")
                if isinstance(req, list):
                    exp = _now_ts() + int(TOOLSET_UPGRADE_TTL_S)
                    for x in req:
                        nm = str(x).strip()
                        if nm:
                            unlocks[nm] = exp

            ev = _build_evidence_from_tool_result(tool_name=name, result=result, store=store)
            if ev:
                evidence_pack.extend(ev)
                external_tools.add(name)
            elif name in CLAIM_REQUIRED_TOOLS:
                external_tools.add(name)

            record["result"] = payload
            _audit_jsonl("tool_audit.jsonl", record)
        except Exception as e:
            payload = {"ok": False, "error": {"code": "TOOL_EXEC_ERROR", "message": str(e)}}
            tool_msgs.append(ToolMessage(content=_safe_json(payload), tool_call_id=tc_id))
            record["result"] = payload
            _audit_jsonl("tool_audit.jsonl", record)

    return {
        "messages": tool_msgs,
        "approval_actions": [],
        "tool_round": int(state.get("tool_round", 0)) + 1,
        "toolset_unlocks": unlocks,
        "evidence_pack": evidence_pack[-50:],
        "last_external_tools": sorted(list(external_tools)),
        "memory_guard_checked": guard_checked,
        "memory_guard_blocked": guard_blocked,
    }


def _route_after_model(state: ThreadState) -> str:
    ai = _latest_ai(_messages(state))
    if ai is None:
        return END
    tool_calls = list(getattr(ai, 'tool_calls', None) or [])
    if not tool_calls:
        return END
    if int(state.get('tool_round', 0)) >= int(TOOL_CALLS_MAX):
        return 'tool_limit'
    return 'tool_gate'


def _route_after_prepare(state: ThreadState) -> str:
    current_event = state.get('current_event') if isinstance(state.get('current_event'), dict) else {}
    behavior_action = state.get('behavior_action') if isinstance(state.get('behavior_action'), dict) else {}
    if _is_silent_behavior_event(current_event, behavior_action):
        return END
    return 'call_model'


def _build_checkpointer() -> SqliteSaver:
    global _CHECKPOINT_CONN
    if _CHECKPOINT_CONN is None:
        s = get_settings()
        s.checkpoint_db_path.parent.mkdir(parents=True, exist_ok=True)
        _CHECKPOINT_CONN = sqlite3.connect(str(s.checkpoint_db_path), check_same_thread=False)
        _CHECKPOINT_CONN.execute('PRAGMA journal_mode=WAL')
        _CHECKPOINT_CONN.execute('PRAGMA foreign_keys=ON')
    return SqliteSaver(_CHECKPOINT_CONN)


def reset_runtime_caches() -> None:
    global _CHECKPOINT_CONN
    try:
        if _CHECKPOINT_CONN is not None:
            _CHECKPOINT_CONN.close()
    except Exception:
        pass
    _CHECKPOINT_CONN = None
    _get_store.cache_clear()
    _get_tool_bundle.cache_clear()
    build_graph.cache_clear()


@lru_cache(maxsize=1)
def build_graph():
    s = get_settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)

    builder = StateGraph(ThreadState)
    builder.add_node('prepare_turn', _node_prepare_turn)
    builder.add_node('call_model', _node_call_model)
    builder.add_node('tool_gate', _node_tool_gate)
    builder.add_node('tool_execute', _node_tool_execute)
    builder.add_node('tool_limit', _node_tool_limit)

    builder.add_edge(START, 'prepare_turn')
    builder.add_conditional_edges(
        'prepare_turn',
        _route_after_prepare,
        {
            'call_model': 'call_model',
            END: END,
        },
    )
    builder.add_conditional_edges(
        'call_model',
        _route_after_model,
        {
            'tool_gate': 'tool_gate',
            'tool_limit': 'tool_limit',
            END: END,
        },
    )
    builder.add_edge('tool_gate', 'tool_execute')
    builder.add_edge('tool_execute', 'call_model')
    builder.add_edge('tool_limit', END)

    return builder.compile(checkpointer=_build_checkpointer())
