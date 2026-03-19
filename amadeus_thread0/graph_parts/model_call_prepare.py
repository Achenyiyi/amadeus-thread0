from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from ..config import CONTEXT_KEEP_LAST_MESSAGES, EVAL_MODE, RUNTIME_MODE
from ..memory_store import MemoryStore
from ..runtime.session_orchestrator import (
    canonicalize_pending_goal_text,
    continuation_seed_text,
    has_pending_continuation as has_active_continuation,
)
from .generation_profile import (
    _generation_profile,
    _is_free_dialog_style,
    _is_light_free_dialog_turn,
)
from .messages import (
    _last_ai_text,
    _last_user_text,
    _messages,
    _recent_ai_texts,
    _sanitize_message,
    _window_messages,
)
from .postprocess import _clean_utf8_text, _needs_structured_answer
from .prompting import _build_task_prompt
from .state import ThreadState
from .tool_nodes import _available_tools_for_state
from .tooling import _infer_memory_tool_calls, _parse_explicit_tool_call


def _prepare_model_call(state: ThreadState, store: MemoryStore) -> dict[str, Any]:
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
    generation_user_text = (
        canonicalize_pending_goal_text(pending_user_goal)
        if active_continuation and pending_user_goal
        else user_text
    )
    prompt = _build_task_prompt(state, user_text, store)
    history = _window_messages(msgs, int(CONTEXT_KEEP_LAST_MESSAGES))
    recent_assistant_texts = _recent_ai_texts(msgs, limit=4)
    previous_assistant_text = _last_ai_text(msgs).strip()
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
    forced_tool_calls: list[dict[str, Any]] = []
    if msgs and isinstance(msgs[-1], HumanMessage):
        forced_tool_calls = _parse_explicit_tool_call(user_text, tools) or []
        if not forced_tool_calls:
            forced_tool_calls = _infer_memory_tool_calls(user_text)
        else:
            forced_tool_calls = list(forced_tool_calls)

    response_style_hint = str(state.get("response_style_hint") or "natural").strip() or "natural"
    science_mode = bool(state.get("science_mode", False))
    free_dialog = _is_free_dialog_style(response_style_hint, user_text, science_mode)
    current_event = state.get("current_event") if isinstance(state.get("current_event"), dict) else {}
    behavior_action = state.get("behavior_action") if isinstance(state.get("behavior_action"), dict) else {}
    emotion_state = state.get("emotion_state") if isinstance(state.get("emotion_state"), dict) else {}
    bond_state = state.get("bond_state") if isinstance(state.get("bond_state"), dict) else {}
    allostasis_state = state.get("allostasis_state") if isinstance(state.get("allostasis_state"), dict) else {}
    counterpart_assessment = (
        state.get("counterpart_assessment") if isinstance(state.get("counterpart_assessment"), dict) else {}
    )
    behavior_policy = state.get("behavior_policy") if isinstance(state.get("behavior_policy"), dict) else {}
    world_model_state = state.get("world_model_state") if isinstance(state.get("world_model_state"), dict) else {}
    interaction_carryover = (
        state.get("interaction_carryover") if isinstance(state.get("interaction_carryover"), dict) else {}
    )
    semantic_narrative_profile = (
        state.get("semantic_narrative_profile") if isinstance(state.get("semantic_narrative_profile"), dict) else {}
    )
    current_event_kind = str(current_event.get("kind") or "user_utterance").strip()
    light_free_dialog = _is_light_free_dialog_turn(
        user_text=user_text,
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        continuation_mode=active_continuation,
        current_event_kind=current_event_kind,
    )
    if active_continuation:
        tools = []
        free_dialog = not _needs_structured_answer(pending_user_goal or continuation_seed, "")
        light_free_dialog = False

    generation_profile = _generation_profile(
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        continuation_mode=active_continuation,
        user_text=generation_user_text,
        runtime_mode=RUNTIME_MODE,
        turn_index=len(msgs),
        recent_assistant_texts=recent_assistant_texts,
        current_event=current_event,
        emotion_state=emotion_state,
        bond_state=bond_state,
        allostasis_state=allostasis_state,
        counterpart_assessment=counterpart_assessment,
        behavior_policy=behavior_policy,
        world_model_state=world_model_state,
        behavior_action=behavior_action,
        interaction_carryover=interaction_carryover,
        semantic_narrative_profile=semantic_narrative_profile,
    )
    generation_runtime_mode = str(generation_profile.pop("runtime_mode", RUNTIME_MODE) or RUNTIME_MODE)
    generation_repetition_pressure = float(generation_profile.pop("repetition_pressure", 0.0) or 0.0)
    generation_recent_reply_max_similarity = float(
        generation_profile.pop("recent_reply_max_similarity", 0.0) or 0.0
    )
    generation_recent_reply_avg_similarity = float(
        generation_profile.pop("recent_reply_avg_similarity", 0.0) or 0.0
    )
    generation_recent_reply_opener_repeat_ratio = float(
        generation_profile.pop("recent_reply_opener_repeat_ratio", 0.0) or 0.0
    )
    generation_recent_reply_sample_size = int(generation_profile.pop("recent_reply_sample_size", 0) or 0)
    chosen_generation_profile: dict[str, Any] = {}
    for key in ("temperature", "top_p", "frequency_penalty", "presence_penalty"):
        value = generation_profile.get(key)
        if value is None:
            continue
        if bool(EVAL_MODE) and key == "temperature":
            continue
        chosen_generation_profile[key] = float(value)
    max_tokens = generation_profile.get("max_tokens")
    if max_tokens is not None:
        chosen_generation_profile["max_tokens"] = int(max_tokens)

    return {
        "call_msgs": call_msgs,
        "current_event": current_event,
        "active_continuation": active_continuation,
        "forced_tool_calls": forced_tool_calls,
        "behavior_action": behavior_action,
        "user_text": user_text,
        "response_style_hint": response_style_hint,
        "light_free_dialog": light_free_dialog,
        "free_dialog": free_dialog,
        "tools": tools,
        "previous_assistant_text": previous_assistant_text,
        "chosen_generation_profile": chosen_generation_profile,
        "generation_runtime_mode": generation_runtime_mode,
        "generation_repetition_pressure": generation_repetition_pressure,
        "generation_recent_reply_max_similarity": generation_recent_reply_max_similarity,
        "generation_recent_reply_avg_similarity": generation_recent_reply_avg_similarity,
        "generation_recent_reply_opener_repeat_ratio": generation_recent_reply_opener_repeat_ratio,
        "generation_recent_reply_sample_size": generation_recent_reply_sample_size,
    }
