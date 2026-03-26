from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from ..persona_authority import normalize_override_mode
from .messages import (
    _latest_ai,
)
from .model_call_prepare import _prepare_model_call
from .prepare_turn_runtime import _prepare_turn_runtime
from .runtime_services import _get_store
from .postprocess import _clean_utf8_text
from .prepare_turn_context import _prepare_turn_context
from .response_finalize import _finalize_text_response
from .rewrite import _invoke_model_with_retries, _model
from .session_context import resolve_session_context
from .state import ThreadState
from .tool_nodes import (
    _node_tool_execute,
    _node_tool_gate,
    _node_tool_limit,
    _route_after_model,
)
from .turn_events import (
    _append_recent_events,
    _now_ts,
    _sanitize_obj,
)


def _prefer_nonempty_mapping(preferred: Any, fallback: Any) -> dict[str, Any]:
    if isinstance(preferred, dict) and preferred:
        return preferred
    if isinstance(fallback, dict):
        return fallback
    return {}


def _node_prepare_turn(state: ThreadState, config: RunnableConfig | None = None) -> dict[str, Any]:

    store = _get_store()
    turn_now_ts = _now_ts()
    session_context = resolve_session_context(state=state, config=config, turn_now_ts=turn_now_ts)
    prepared_turn = _prepare_turn_context(
        state=state,
        store=store,
        turn_now_ts=turn_now_ts,
        session_context=session_context,
    )
    counterpart_trace = prepared_turn["counterpart_trace"]
    persona_trace = prepared_turn["persona_trace"]
    agenda_lifecycle_residue = prepared_turn["agenda_lifecycle_residue"]
    pending = prepared_turn["pending"]
    pending_user_goal = prepared_turn["pending_user_goal"]
    science_mode = prepared_turn["science_mode"]
    response_style_hint = prepared_turn["response_style_hint"]
    appraisal = prepared_turn["appraisal"]
    current_event = prepared_turn["current_event"]
    interaction_carryover = prepared_turn["interaction_carryover"]
    recent_events = prepared_turn["recent_events"]
    runtime_state = _prepare_turn_runtime(
        state=state,
        store=store,
        turn_now_ts=turn_now_ts,
        prepared_turn=prepared_turn,
    )
    current_event = _prefer_nonempty_mapping(runtime_state.get("current_event"), current_event)
    interaction_carryover = _prefer_nonempty_mapping(
        runtime_state.get("interaction_carryover"),
        interaction_carryover,
    )
    recent_events = _append_recent_events(_sanitize_obj(state.get("recent_events")), current_event, limit=6)
    retrieved = runtime_state["retrieved"]
    relationship = runtime_state["relationship"]
    worldline_focus = runtime_state["worldline_focus"]
    persona_state = runtime_state["persona_state"]
    world_model_state = runtime_state["world_model_state"]
    evolution_state = runtime_state["evolution_state"]
    reconsolidation_snapshot = runtime_state["reconsolidation_snapshot"]
    emotion_state = runtime_state["emotion_state"]
    bond_state = runtime_state["bond_state"]
    allostasis_state = runtime_state["allostasis_state"]
    counterpart_assessment = runtime_state["counterpart_assessment"]
    semantic_narrative_profile = runtime_state["semantic_narrative_profile"]
    behavior_policy = runtime_state["behavior_policy"]
    behavior_action = runtime_state["behavior_action"]
    behavior_plan = runtime_state["behavior_plan"]
    behavior_agenda = runtime_state["behavior_agenda"]
    tsundere = runtime_state["tsundere"]

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
        "session_context": _sanitize_obj(session_context),
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
def _node_call_model(state: ThreadState) -> dict[str, Any]:
    store = _get_store()
    prepared = _prepare_model_call(state, store)
    if prepared["forced_tool_calls"]:
        return {"messages": [AIMessage(content="", tool_calls=list(prepared["forced_tool_calls"] or []))]}
    user_text = str(prepared["user_text"] or "")
    current_event = prepared["current_event"] if isinstance(prepared["current_event"], dict) else {}
    behavior_action = prepared["behavior_action"] if isinstance(prepared["behavior_action"], dict) else {}
    response_style_hint = str(prepared["response_style_hint"] or "natural")
    llm = _model(**dict(prepared["chosen_generation_profile"] or {}))
    tools = list(prepared["tools"] or [])
    free_dialog = bool(prepared["free_dialog"])
    llm_tools = llm if free_dialog else (llm.bind_tools(tools) if tools else llm)
    ai = _invoke_model_with_retries(llm_tools, list(prepared["call_msgs"] or []))
    if not isinstance(ai, AIMessage):
        ai = AIMessage(content=str(getattr(ai, "content", "") or ""))

    tool_calls = list(getattr(ai, "tool_calls", None) or [])
    if tool_calls:
        return {"messages": [ai]}

    return _finalize_text_response(
        state=state,
        store=store,
        user_text=user_text,
        raw_draft_text=str(ai.content or ""),
        current_event=current_event,
        behavior_action=behavior_action,
        response_style_hint=response_style_hint,
        continuation_mode=bool(prepared["active_continuation"]),
        light_free_dialog=bool(prepared["light_free_dialog"]),
        previous_assistant_text=str(prepared["previous_assistant_text"] or ""),
        chosen_generation_profile=dict(prepared["chosen_generation_profile"] or {}),
        generation_runtime_mode=str(prepared["generation_runtime_mode"] or ""),
        generation_repetition_pressure=float(prepared["generation_repetition_pressure"] or 0.0),
        generation_recent_reply_max_similarity=float(prepared["generation_recent_reply_max_similarity"] or 0.0),
        generation_recent_reply_avg_similarity=float(prepared["generation_recent_reply_avg_similarity"] or 0.0),
        generation_recent_reply_opener_repeat_ratio=float(prepared["generation_recent_reply_opener_repeat_ratio"] or 0.0),
        generation_recent_reply_sample_size=int(prepared["generation_recent_reply_sample_size"] or 0),
    )
