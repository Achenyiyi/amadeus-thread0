from __future__ import annotations

from ..config import CANON_COUNTERPART_NAME, USER_RULES_MAX_ITEMS, ABLATE_LIGHT_DIALOG_SHAPING, ABLATE_PERSONA_ALIGNMENT, ABLATE_WORLDLINE_MEMORY
from ..memory_store import MemoryStore
from ..runtime.session_orchestrator import (
    canonicalize_pending_goal_text,
    continuation_seed_text,
    has_pending_continuation as has_active_continuation,
)
from .prompt_helpers import (
    _compact_behavior_agenda_hint,
    _compact_digital_body_trace_lines,
    _compact_focus_lines,
    _compact_interaction_carryover_hint,
    _compact_long_horizon_continuity_hint,
    _compact_recent_event_lines,
    _compact_rule_lines,
    _resolve_behavior_agenda,
    _compact_working_item_fallback_texts,
    _recent_background_scene_hint,
)
from .relational_runtime import (
    _compact_counterpart_assessment_hint,
    _compact_relationship_summary,
    _focus_payload,
    _prefer_relationship_state,
)
from .generation_profile import (
    _daily_surface_preference_lines,
    _is_free_dialog_style,
    _is_light_free_dialog_turn,
)
from .dialogue_guidance import (
    _event_behavior_preference_lines,
    _light_free_dialog_counterpart_line,
    _light_free_dialog_state_hint,
    _narrative_actor_profile,
    _plain_contact_ping_needs_relational_guard,
    _scene_persona_axioms,
    _semantic_evidence_runtime_lines,
    _semantic_motive_state_hint,
    _selfhood_preference_lines,
    _subjective_runtime_state_hint,
    _user_turn_behavior_preference_lines,
)
from .persona_runtime import (
    _active_counterpart_profile,
    _active_persona_core,
    _canon_persona_labels,
)
from .retrieval import _record_value
from .postprocess import _is_plain_contact_ping, _wants_brief_presence, _wants_per_topic_conclusions, _wants_quick_judgment
from .runtime_prompting import (
    _prompt_state_runtime_brief,
    _prompt_state_snapshot,
    _renderer_guidance,
)
from .semantic_narrative import (
    _compact_semantic_narrative_hint,
    _self_narrative_anchor_lines,
    _semantic_narrative_profile,
)
from .state import ThreadState


def _memory_grounding_hint(
    *,
    response_style_hint: str,
    science_mode: bool,
    worldline_lines: list[str],
    commitment_lines: list[str],
    relationship_lines: list[str],
    repair_lines: list[str],
    tension_lines: list[str],
) -> str:
    hint = str(response_style_hint or "").strip().lower()
    if science_mode or hint not in {"relationship", "companion", "natural", "casual", "memory_recall", "selfhood"}:
        return ""
    if not any([worldline_lines, commitment_lines, relationship_lines, repair_lines, tension_lines]):
        return ""
    return "涉及共同记忆、当前关系或后续安排时，先把真正记得的具体内容说出来，再自然给出概括，不要把细节抹平成空泛总结。"


def _build_task_prompt(state: ThreadState, user_text: str, store: MemoryStore) -> str:
    profile = _active_counterpart_profile(state, store)
    persona_core = _active_persona_core(state)
    canon_labels = _canon_persona_labels()
    canon = store.list_canon_facts()
    retrieved = state.get("retrieved_context") or {}
    relationship = _prefer_relationship_state(
        state.get("relationship") if isinstance(state.get("relationship"), dict) else None,
        retrieved.get("relationship") if isinstance(retrieved.get("relationship"), dict) else None,
        store.get_relationship(),
    )
    working_items = retrieved.get("working_items") or []
    commitments = retrieved.get("commitments") or []
    relationship_items = retrieved.get("relationship_timeline") or []
    conflict_repairs = retrieved.get("conflict_repairs") or []
    unresolved_tensions = retrieved.get("unresolved_tensions") or []
    behavior_consequence_traces = (
        retrieved.get("behavior_consequence_traces") if isinstance(retrieved.get("behavior_consequence_traces"), list) else []
    )
    behavior_reactivation_traces = (
        retrieved.get("behavior_reactivation_traces") if isinstance(retrieved.get("behavior_reactivation_traces"), list) else []
    )
    behavior_plan_traces = retrieved.get("behavior_plan_traces") if isinstance(retrieved.get("behavior_plan_traces"), list) else []
    digital_body_consequence_traces = (
        retrieved.get("digital_body_consequence_traces")
        if isinstance(retrieved.get("digital_body_consequence_traces"), list)
        else []
    )
    continuity_trace_items = [item for item in behavior_consequence_traces if isinstance(item, dict)] + [
        item for item in behavior_reactivation_traces if isinstance(item, dict)
    ] + [item for item in behavior_plan_traces if isinstance(item, dict)]
    evidence_pack = state.get("evidence_pack") or []
    current_event = state.get("current_event") if isinstance(state.get("current_event"), dict) else {}
    recent_events = state.get("recent_events") if isinstance(state.get("recent_events"), list) else []
    behavior_action = state.get("behavior_action") if isinstance(state.get("behavior_action"), dict) else {}
    digital_body_state = state.get("digital_body_state") if isinstance(state.get("digital_body_state"), dict) else {}
    session_skill_state = state.get("session_skill_state") if isinstance(state.get("session_skill_state"), dict) else {}
    session_context = state.get("session_context") if isinstance(state.get("session_context"), dict) else {}
    behavior_agenda = _resolve_behavior_agenda(
        state.get("behavior_agenda"),
        behavior_queue=state.get("behavior_queue"),
    )
    pending_fragment = str(state.get("pending_utterance_fragment") or "").strip()
    pending_user_goal = str(state.get("pending_user_goal") or "").strip()
    continuation_mode = has_active_continuation(user_text=user_text, pending_fragment=pending_fragment)
    prompt_user_text = canonicalize_pending_goal_text(pending_user_goal) if continuation_mode and pending_user_goal else user_text
    response_style_hint = str(state.get("response_style_hint") or "natural").strip() or "natural"
    behavior_policy = state.get("behavior_policy") if isinstance(state.get("behavior_policy"), dict) else {}
    allostasis_state = state.get("allostasis_state") if isinstance(state.get("allostasis_state"), dict) else {}
    counterpart_assessment = state.get("counterpart_assessment") if isinstance(state.get("counterpart_assessment"), dict) else {}
    appraisal = state.get("turn_appraisal") if isinstance(state.get("turn_appraisal"), dict) else {}

    user_rules = profile.get("user_model_rules")
    if not isinstance(user_rules, list):
        user_rules = []
    user_rules = user_rules[: int(USER_RULES_MAX_ITEMS)]

    science_mode = bool(state.get("science_mode", False))
    emotion = state.get("emotion_state") or {}
    ts = float(state.get("tsundere_intensity", 0.55))
    persona_ablation = bool(ABLATE_PERSONA_ALIGNMENT)
    worldline_ablation = bool(ABLATE_WORLDLINE_MEMORY)
    quick_judgment = _wants_quick_judgment(prompt_user_text)
    per_topic_conclusions = _wants_per_topic_conclusions(prompt_user_text)
    counterpart = profile
    labels = _narrative_actor_profile(persona_core=persona_core, counterpart_profile=counterpart)
    actor_name = str(labels.get("actor_name") or canon_labels.get("narrative_ref") or "红莉栖")
    actor_display_name = str(persona_core.get("display_name") or actor_name).strip() or actor_name
    counterpart_name = str(labels.get("counterpart_name") or CANON_COUNTERPART_NAME)
    persona_brief = str(
        persona_core.get("role_brief")
        or persona_core.get("description")
        or persona_core.get("character_brief")
        or ""
    ).strip()
    light_dialog_brief = str(persona_core.get("light_dialog_brief") or "").strip()
    persona_axioms_raw = [
        str(item).strip()
        for item in (persona_core.get("identity_axioms") or [])
        if str(item or "").strip()
    ][:5]
    persona_value_floor = [
        str(item).strip()
        for item in (persona_core.get("value_floor") or [])
        if str(item or "").strip()
    ][:3]
    persona_brief_line = f"角色底色：{persona_brief}\n" if persona_brief else ""
    persona_value_block = (
        "价值底线：\n" + "\n".join(f"- {item}" for item in persona_value_floor) + "\n"
        if persona_value_floor
        else ""
    )
    jp_whitelist = [] if persona_ablation else ["D-mail", "世界线", "LabMem", "El Psy Congroo", "助手", "笨蛋"]
    focus_payload = _focus_payload(state.get("worldline_focus") or [], limit=5)
    relationship_memory = [
        {
            "summary": str(_record_value(item, "summary", "") or "").strip(),
            "affinity_delta": float(_record_value(item, "affinity_delta", 0.0) or 0.0),
            "trust_delta": float(_record_value(item, "trust_delta", 0.0) or 0.0),
        }
        for item in relationship_items[:3]
        if str(_record_value(item, "summary", "") or "").strip()
    ]
    commitment_memory = []
    for item in commitments[:3]:
        status = str(_record_value(item, "status", "") or "open").strip().lower()
        if status in {"resolved", "closed", "done"}:
            continue
        text = str(_record_value(item, "text", "") or "").strip()
        due_at = str(_record_value(item, "due_at", "") or "").strip()
        if not text:
            continue
        commitment_memory.append(f"{text}（{due_at}）" if due_at else text)
    repair_memory = [
        str(_record_value(item, "summary", "") or "").strip()
        for item in conflict_repairs[:3]
        if str(_record_value(item, "summary", "") or "").strip()
    ]
    unresolved_tension_memory = [
        str(_record_value(item, "summary", "") or "").strip()
        for item in unresolved_tensions[:3]
        if str(_record_value(item, "status", "") or "open").strip().lower() not in {"resolved", "closed", "done"}
        and str(_record_value(item, "summary", "") or "").strip()
    ]
    continuity_plan_memory = [
        str(_record_value(item, "after_summary", "") or "").strip()
        for item in continuity_trace_items[:3]
        if str(_record_value(item, "after_summary", "") or "").strip()
    ]
    digital_body_trace_memory = _compact_digital_body_trace_lines(
        digital_body_consequence_traces,
        limit=2,
        style="natural",
    )
    if worldline_ablation:
        relationship = {
            "stage": "friend",
            "notes": "",
            "affinity_score": 0.0,
            "trust_score": 0.0,
            "derived": True,
        }
    if quick_judgment:
        draft_shape = (
            "- This is a quick-judgment request: answer briefly in 2-4 short sentences.\n"
            "- Give the takeaway early, but keep the wording natural.\n"
            "- If helpful, weave in the basis/source naturally instead of forcing a fixed sentence pattern.\n"
            "- Do not open with '没搜到/没查到/文档没写'. Lead with the judgment first.\n"
            "- Only add a short follow-up if the user explicitly asked for one.\n"
        )
        if per_topic_conclusions and evidence_pack:
            draft_shape += "- The user asked for separate conclusions by topic. Keep to the requested items only and do not add a third synthesis sentence.\n"
    else:
        draft_shape = (
            "- Prefer natural dialogue over visible answer templates.\n"
            "- Use numbered steps or explicit sections only if the user explicitly asked for them.\n"
            "- For scientific tasks, keep the reasoning clear and well ordered, but do not force labels unless needed.\n"
        )

    relationship_summary = _compact_relationship_summary(relationship)
    counterpart_assessment_hint = _compact_counterpart_assessment_hint(counterpart_assessment, counterpart_name=counterpart_name)
    semantic_narrative_profile = (
        state.get("semantic_narrative_profile")
        if isinstance(state.get("semantic_narrative_profile"), dict)
        else _semantic_narrative_profile(
            retrieved.get("semantic_self_narratives") if isinstance(retrieved.get("semantic_self_narratives"), list) else [],
            user_text=prompt_user_text,
            current_event=current_event,
        )
    )
    semantic_narrative_hint = _compact_semantic_narrative_hint(semantic_narrative_profile)
    bond_state = state.get("bond_state") if isinstance(state.get("bond_state"), dict) else {}
    world_model_state = state.get("world_model_state") if isinstance(state.get("world_model_state"), dict) else {}
    evolution_state = state.get("evolution_state") if isinstance(state.get("evolution_state"), dict) else {}
    self_narrative_anchor_lines = _self_narrative_anchor_lines(
        semantic_narrative_profile,
        evolution_state=evolution_state,
        persona_core=persona_core,
        counterpart_name=counterpart_name,
    )
    subjective_state_hint = _subjective_runtime_state_hint(
        emotion_state=emotion,
        bond_state=bond_state,
        allostasis_state=allostasis_state,
        counterpart_assessment=counterpart_assessment,
        semantic_narrative_profile=semantic_narrative_profile,
        behavior_policy=behavior_policy,
        world_model_state=world_model_state,
        behavior_action=behavior_action,
    )
    worldline_lines = _compact_focus_lines(state.get("worldline_focus") or [], limit=4)
    event_lines = _compact_recent_event_lines(recent_events, limit=3)
    current_event_text = str(current_event.get("effective_text") or current_event.get("text") or "").strip()
    current_event_frame = str(current_event.get("event_frame") or "").strip()
    current_event_kind = str(current_event.get("kind") or "user_utterance").strip()
    relationship_lines = [f"- {item['summary'][:160]}" for item in relationship_memory[:2] if item.get("summary")]
    commitment_lines = [f"- {text[:160]}" for text in commitment_memory[:2] if text]
    repair_lines = [f"- {text[:160]}" for text in repair_memory[:2] if text]
    tension_lines = [f"- {text[:160]}" for text in unresolved_tension_memory[:2] if text]
    working_item_fallback_texts = (
        _compact_working_item_fallback_texts(working_items, limit=2)
        if not any(
            [
                worldline_lines,
                commitment_lines,
                relationship_lines,
                repair_lines,
                tension_lines,
                continuity_plan_memory,
                digital_body_trace_memory,
            ]
        )
        else []
    )
    rule_lines = _compact_rule_lines(user_rules, limit=3)
    evidence_lines = []
    for item in evidence_pack[:2]:
        title = str(item.get("title") or item.get("query") or item.get("tool_name") or "").strip()
        if title:
            evidence_lines.append(f"- {title[:140]}")
    brief_presence = _wants_brief_presence(prompt_user_text)
    interaction_carryover = (
        state.get("interaction_carryover") if isinstance(state.get("interaction_carryover"), dict) else {}
    )
    carryover_hint = _compact_interaction_carryover_hint(interaction_carryover)
    long_horizon_hint = _compact_long_horizon_continuity_hint(
        world_model_state=world_model_state,
        semantic_narrative_profile=semantic_narrative_profile,
        interaction_carryover=interaction_carryover,
        counterpart_assessment=counterpart_assessment,
    )
    background_agenda_hint = _compact_behavior_agenda_hint(
        behavior_agenda,
        current_event=current_event,
    )
    background_scene_hint = _recent_background_scene_hint(
        recent_events,
        current_event=current_event,
    )
    state_snapshot_json = _prompt_state_snapshot(
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        continuation_mode=continuation_mode,
        emotion_state=emotion,
        bond_state=bond_state,
        allostasis_state=allostasis_state,
        counterpart_assessment=counterpart_assessment,
        world_model_state=world_model_state,
        evolution_state=evolution_state,
        behavior_action=behavior_action,
        interaction_carryover=interaction_carryover,
        current_event=current_event,
        digital_body_state=digital_body_state,
        session_context=session_context,
        session_skill_state=session_skill_state,
    )
    renderer_hint = _renderer_guidance(
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        user_text=prompt_user_text,
        emotion_state=emotion,
        bond_state=bond_state,
        allostasis_state=allostasis_state,
        behavior_policy=behavior_policy,
        counterpart_assessment=counterpart_assessment,
        world_model_state=world_model_state,
        evolution_state=evolution_state,
        behavior_action=behavior_action,
        digital_body_state=digital_body_state,
        session_context=session_context,
        current_event=current_event,
    )
    free_dialog = _is_free_dialog_style(response_style_hint, prompt_user_text, science_mode)
    light_free_dialog = _is_light_free_dialog_turn(
        user_text=prompt_user_text,
        response_style_hint=response_style_hint,
        science_mode=science_mode,
        continuation_mode=continuation_mode,
        current_event_kind=current_event_kind,
    )
    plain_contact_ping = light_free_dialog and _is_plain_contact_ping(prompt_user_text)
    plain_contact_guard = plain_contact_ping and _plain_contact_ping_needs_relational_guard(
        bond_state=bond_state,
        counterpart_assessment=counterpart_assessment,
    )
    motive_state_hint = _semantic_motive_state_hint(
        semantic_narrative_profile,
        light_touch=light_free_dialog,
    )
    if bool(ABLATE_LIGHT_DIALOG_SHAPING):
        light_free_dialog = False
        plain_contact_ping = False
        plain_contact_guard = False
    semantic_evidence_lines = _semantic_evidence_runtime_lines(
        semantic_narrative_profile=semantic_narrative_profile,
        behavior_policy=behavior_policy,
        light_touch=light_free_dialog,
    )
    daily_surface_pref_lines = (
        _daily_surface_preference_lines(prompt_user_text, science_mode=science_mode) if light_free_dialog else []
    )
    selfhood_pref_lines = (
        _selfhood_preference_lines(prompt_user_text)
        if current_event_kind == "user_utterance" and not science_mode
        else []
    )
    user_turn_behavior_pref_lines = (
        _user_turn_behavior_preference_lines(
            behavior_action=behavior_action,
            counterpart_assessment=counterpart_assessment,
            semantic_narrative_profile=semantic_narrative_profile,
            behavior_policy=behavior_policy,
            world_model_state=world_model_state,
        )
        if current_event_kind == "user_utterance" and not science_mode
        else []
    )
    event_behavior_pref_lines = (
        _event_behavior_preference_lines(current_event, behavior_action)
        if current_event_kind != "user_utterance"
        else []
    )
    persona_axioms = _scene_persona_axioms(
        persona_axioms_raw,
        light_free_dialog=light_free_dialog,
        counterpart_aliases=labels.get("counterpart_aliases") if isinstance(labels.get("counterpart_aliases"), list) else [],
    )
    persona_axiom_block = (
        "身份不变量：\n" + "\n".join(f"- {item}" for item in persona_axioms) + "\n"
        if persona_axioms
        else ""
    )
    if free_dialog and not persona_ablation:
        active_persona_brief = light_dialog_brief if light_free_dialog and light_dialog_brief else persona_brief
        active_persona_brief_line = f"角色底色：{active_persona_brief}\n" if active_persona_brief else ""
        context_lines: list[str] = []
        alignment_lines: list[str] = []
        if relationship_summary and not plain_contact_ping:
            context_lines.append(f"- 你和{counterpart_name}当前关系：{relationship_summary}")
        if light_free_dialog:
            counterpart_line = _light_free_dialog_counterpart_line(
                counterpart_name=counterpart_name,
                bond_state=bond_state,
                counterpart_assessment=counterpart_assessment,
            )
            if counterpart_line and (not plain_contact_ping or plain_contact_guard):
                context_lines.append(counterpart_line)
            if semantic_narrative_hint and not plain_contact_ping:
                context_lines.append(f"- 这段时间沉下来的熟悉感：{semantic_narrative_hint}")
            if commitment_memory and not plain_contact_ping:
                context_lines.append(f"- 前面还挂着一个说好的后续：{commitment_memory[0][:160]}")
            if unresolved_tension_memory and not plain_contact_ping:
                context_lines.append(f"- 前面还有一点没完全化开的地方：{unresolved_tension_memory[0][:160]}")
            if continuity_plan_memory and not plain_contact_ping:
                context_lines.append(f"- 前面还挂着的一点延续：{continuity_plan_memory[0][:160]}")
            if digital_body_trace_memory and not plain_contact_ping:
                context_lines.append(f"- {digital_body_trace_memory[0][:160]}")
            if working_item_fallback_texts and not plain_contact_ping:
                context_lines.append(f"- 前面顺手还带着一点前情：{working_item_fallback_texts[0][:160]}")
            if motive_state_hint and not plain_contact_ping:
                context_lines.append(f"- 当前主动倾向：{motive_state_hint}")
            if user_turn_behavior_pref_lines and not plain_contact_ping:
                alignment_lines.append(f"这轮互动自然倾向：{user_turn_behavior_pref_lines[0]}")
            if semantic_evidence_lines and not plain_contact_ping:
                alignment_lines.append(f"这轮关系/自我依据：{semantic_evidence_lines[0]}")
            if daily_surface_pref_lines and not plain_contact_ping:
                alignment_lines.append(f"轻场景自然落点：{daily_surface_pref_lines[0]}")
            if selfhood_pref_lines and not plain_contact_ping:
                alignment_lines.append(f"关系/自我侧写：{selfhood_pref_lines[0]}")
            if pending_user_goal and not plain_contact_ping:
                context_lines.append(f"- 刚才还没说完的话题：{pending_user_goal[:160]}")
            elif pending_fragment and not plain_contact_ping:
                context_lines.append(f"- 刚才还没说完的一句：{pending_fragment[:160]}")
        if not light_free_dialog:
            if counterpart_assessment_hint:
                context_lines.append(f"- 你此刻对{counterpart_name}的判断：{counterpart_assessment_hint}")
            if worldline_lines:
                context_lines.append(f"- 你和{counterpart_name}最近有关的共同上下文：")
                context_lines.extend(worldline_lines[:2])
            elif relationship_lines:
                context_lines.append("- 最近互动印象：")
                context_lines.extend(relationship_lines[:2])
            elif repair_lines:
                context_lines.append("- 最近说开过的误会：")
                context_lines.extend(repair_lines[:2])
            if commitment_lines:
                context_lines.append("- 前面还挂着的约定或后续：")
                context_lines.extend(commitment_lines[:2])
            if tension_lines:
                context_lines.append("- 前面还有一点没完全化开的地方：")
                context_lines.extend(tension_lines[:2])
            if rule_lines:
                context_lines.append("- 这轮要顺手记住的说话偏好：")
                context_lines.extend(rule_lines[:2])
            if semantic_narrative_hint:
                context_lines.append(f"- 这段时间沉下来的关系余波：{semantic_narrative_hint}")
            if continuity_plan_memory:
                context_lines.append("- 前面还挂着的一点延续：")
                context_lines.extend(f"- {item[:160]}" for item in continuity_plan_memory[:2])
            if digital_body_trace_memory:
                context_lines.append("- 前面刚接回当前判断的资料或工作面：")
                context_lines.extend(f"- {item[:160]}" for item in digital_body_trace_memory[:2])
            if working_item_fallback_texts:
                context_lines.append("- 前面顺手还带着的一点前情：")
                context_lines.extend(f"- {item[:160]}" for item in working_item_fallback_texts[:2])
            if motive_state_hint:
                context_lines.append(f"- 当前主动倾向：{motive_state_hint}")
            if user_turn_behavior_pref_lines:
                alignment_lines.append(f"这轮互动自然倾向：{user_turn_behavior_pref_lines[0]}")
            if semantic_evidence_lines:
                alignment_lines.append(f"这轮关系/自我依据：{semantic_evidence_lines[0]}")
            if selfhood_pref_lines:
                alignment_lines.append(f"关系/自我侧写：{selfhood_pref_lines[0]}")
            if event_behavior_pref_lines:
                alignment_lines.append(f"事件带出的自然倾向：{event_behavior_pref_lines[0]}")
            if pending_user_goal:
                context_lines.append(f"- 刚才还没说完的话题：{pending_user_goal[:160]}")
            elif pending_fragment:
                context_lines.append(f"- 刚才还没说完的一句：{pending_fragment[:160]}")
            if current_event_text:
                context_lines.append(f"- 当前事件输入：{current_event_text[:160]}")
            if current_event_frame:
                context_lines.append(f"- 当前事件语境：{current_event_frame[:120]}")
            if event_lines:
                context_lines.append("- 最近事件轨迹：")
                context_lines.extend(event_lines[:2])
        context_block = (
            "共同背景：\n" + "\n".join(context_lines) + "\n"
            if context_lines
            else ""
        )
        self_anchor_block = (
            "当前自我连续性：\n" + "\n".join(f"- {item}" for item in self_narrative_anchor_lines) + "\n"
            if self_narrative_anchor_lines and (not plain_contact_ping or plain_contact_guard)
            else ""
        )
        inner_state_lines: list[str] = []
        if light_free_dialog:
            state_hint = _light_free_dialog_state_hint(
                emotion_state=emotion,
                bond_state=bond_state,
                allostasis_state=allostasis_state,
                counterpart_assessment=counterpart_assessment,
                semantic_narrative_profile=semantic_narrative_profile,
                behavior_policy=behavior_policy,
                world_model_state=world_model_state,
                behavior_action=behavior_action,
            )
            if state_hint and (not plain_contact_ping or plain_contact_guard):
                inner_state_lines.append(state_hint)
            if alignment_lines and (not plain_contact_ping or plain_contact_guard):
                inner_state_lines.extend(alignment_lines[:2])
            if long_horizon_hint and not plain_contact_ping:
                inner_state_lines.append(long_horizon_hint)
            if renderer_hint and (not plain_contact_ping or plain_contact_guard):
                inner_state_lines.append(f"表面语气落点：{renderer_hint}")
            if carryover_hint and not plain_contact_ping:
                inner_state_lines.append(carryover_hint)
            if background_agenda_hint and not plain_contact_ping:
                inner_state_lines.append(background_agenda_hint)
            elif background_scene_hint and not plain_contact_ping:
                inner_state_lines.append(background_scene_hint)
        else:
            if subjective_state_hint:
                inner_state_lines.append(f"- 你此刻更像是从这样的内在状态开口：{subjective_state_hint}")
            if alignment_lines:
                inner_state_lines.extend(f"- {item}" for item in alignment_lines[:2])
            if long_horizon_hint:
                inner_state_lines.append(f"- 长线延续：{long_horizon_hint}")
            if renderer_hint:
                inner_state_lines.append(f"- 表面语气落点：{renderer_hint}")
            if carryover_hint:
                inner_state_lines.append(f"- 这轮延续的交互余韵：{carryover_hint}")
            if background_agenda_hint:
                inner_state_lines.append(f"- 背景里还挂着的事：{background_agenda_hint}")
            elif background_scene_hint:
                inner_state_lines.append(f"- 刚才的后台场景余波：{background_scene_hint}")
        inner_state_block = (
            "内在态势：\n" + "\n".join(inner_state_lines) + "\n"
            if inner_state_lines
            else ""
        )
        event_prompt_block = (
            f"当前触发事件：{current_event_text}\n"
            if current_event_kind != "user_utterance" and current_event_text
            else ""
        )
        user_prompt_block = f"用户输入：{prompt_user_text}\n" if prompt_user_text else ""

        return (
            f"你现在就是 {actor_display_name if light_free_dialog else actor_name}。\n"
            f"对话对象：{counterpart_name}\n"
            f"{active_persona_brief_line}"
            f"{persona_axiom_block}"
            f"{persona_value_block}"
            f"{context_block}"
            f"{self_anchor_block}"
            f"{inner_state_block}"
            f"{event_prompt_block}"
            f"{user_prompt_block}"
            "输出：此刻会说的话。"
        )

    header = (
        "You are a helpful general assistant.\n"
        "Persona ablation is enabled. Do not imitate Kurisu, Amadeus, or any fictional role shell.\n"
        "Answer clearly and directly.\n"
        if persona_ablation
        else
        f"你就是 {actor_name}。\n"
        f"你此刻正在和 {counterpart_name} 继续这条世界线里的对话。\n"
        f"{persona_brief_line}"
        f"{persona_axiom_block}"
        f"{persona_value_block}"
        "先把任务答对，但从一开始就保持该角色的说话习惯：聪明、克制、熟悉、略带锋芒，有真实的人味。\n"
    )
    user_rules_block = "- user_rules:\n" + "\n".join(rule_lines) + "\n" if rule_lines else ""
    worldline_block = "- worldline_focus:\n" + "\n".join(worldline_lines) + "\n" if worldline_lines else ""
    relationship_block = "- relationship_memory:\n" + "\n".join(relationship_lines) + "\n" if relationship_lines else ""
    repair_block = "- conflict_repair_memory:\n" + "\n".join(repair_lines) + "\n" if repair_lines else ""
    continuity_plan_block = "- continuity_intents:\n" + "\n".join(f"- {item[:160]}" for item in continuity_plan_memory[:3]) + "\n" if continuity_plan_memory else ""
    semantic_narrative_block = f"- semantic_narrative_hint={semantic_narrative_hint}\n" if semantic_narrative_hint else ""
    evidence_block = "- evidence:\n" + "\n".join(evidence_lines) + "\n" if evidence_lines else ""
    event_block = "- recent_events:\n" + "\n".join(event_lines) + "\n" if event_lines else ""
    continuation_seed = continuation_seed_text(
        pending_user_goal=pending_user_goal,
        pending_fragment=pending_fragment,
    )
    pending_fragment_block = f"- pending_fragment={pending_fragment[:220]}\n" if pending_fragment else ""
    pending_goal_block = f"- pending_user_goal={pending_user_goal[:220]}\n" if pending_user_goal else ""
    continuation_instruction_block = (
        "- 这是一次续说，不是新开话题。\n"
        "- 直接顺着刚才没说完的内容往下接，不要先解释你在续哪一段，也不要复述用户刚才的指令。\n"
        "- 除非原任务本来要求条列，否则不要把续说改写成标题、条目或重新起手的说明。\n"
        f"- continuation_seed={continuation_seed[:220]}\n"
        if continuation_mode and continuation_seed
        else ""
    )
    current_event_block = (
        f"- current_event_text={current_event_text[:220]}\n- current_event_frame={current_event_frame[:160]}\n"
        if current_event_text or current_event_frame
        else ""
    )
    brief_presence_requirement = (
        "- 用户明确只想要一句简短确认；给一句自然确认就停，不要追问、解释、反问，也不要补第二句展开，更不要说成状态播报。\n"
        if brief_presence
        else ""
    )
    runtime_brief_lines: list[str] = []
    if not science_mode and response_style_hint in {"relationship", "companion", "natural", "casual", "memory_recall", "selfhood"}:
        if subjective_state_hint:
            runtime_brief_lines.append(f"- 你此刻更像是从这样的内在状态开口：{subjective_state_hint}")
        if motive_state_hint:
            runtime_brief_lines.append(f"- 当前主动倾向：{motive_state_hint}")
        if relationship_summary:
            runtime_brief_lines.append(f"- 你和{counterpart_name}此刻关系上的基本感觉：{relationship_summary}")
        if counterpart_assessment_hint:
            runtime_brief_lines.append(f"- 你现在对{counterpart_name}的直觉判断：{counterpart_assessment_hint}")
        if semantic_narrative_hint:
            runtime_brief_lines.append(f"- 最近沉下来的关系余波：{semantic_narrative_hint}")
        if commitment_memory:
            runtime_brief_lines.append(f"- 前面还挂着一个说好的后续：{commitment_memory[0][:160]}")
        if unresolved_tension_memory:
            runtime_brief_lines.append(f"- 前面还有一点没完全化开的地方：{unresolved_tension_memory[0][:160]}")
        if continuity_plan_memory:
            runtime_brief_lines.append(f"- 前面还挂着的一点延续：{continuity_plan_memory[0][:160]}")
        if digital_body_trace_memory:
            runtime_brief_lines.append(f"- {digital_body_trace_memory[0][:160]}")
        if working_item_fallback_texts:
            runtime_brief_lines.append(f"- 前面顺手还带着一点前情：{working_item_fallback_texts[0][:160]}")
        if user_turn_behavior_pref_lines:
            runtime_brief_lines.append(f"- 这轮互动自然倾向：{user_turn_behavior_pref_lines[0]}")
        if semantic_evidence_lines:
            runtime_brief_lines.append(f"- 这轮关系/自我依据：{semantic_evidence_lines[0]}")
        if selfhood_pref_lines:
            runtime_brief_lines.append(f"- 关系/自我侧写：{selfhood_pref_lines[0]}")
        if event_behavior_pref_lines:
            runtime_brief_lines.append(f"- 事件带出的自然倾向：{event_behavior_pref_lines[0]}")
        if carryover_hint:
            runtime_brief_lines.append(f"- 延续到这一句的交互余韵：{carryover_hint}")
        if background_agenda_hint:
            runtime_brief_lines.append(f"- 背景里还挂着的事：{background_agenda_hint}")
        elif background_scene_hint:
            runtime_brief_lines.append(f"- 刚才的后台场景余波：{background_scene_hint}")
        memory_grounding_hint = _memory_grounding_hint(
            response_style_hint=response_style_hint,
            science_mode=science_mode,
            worldline_lines=worldline_lines,
            commitment_lines=commitment_lines,
            relationship_lines=relationship_lines,
            repair_lines=repair_lines,
            tension_lines=tension_lines,
        )
        if memory_grounding_hint:
            runtime_brief_lines.append(f"- {memory_grounding_hint}")
    runtime_brief_block = (
        "内在延续：\n" + "\n".join(runtime_brief_lines) + "\n\n"
        if runtime_brief_lines
        else ""
    )
    self_anchor_block = (
        "当前自我连续性：\n" + "\n".join(f"- {item}" for item in self_narrative_anchor_lines) + "\n\n"
        if self_narrative_anchor_lines
        else ""
    )
    prefer_runtime_state_brief = (
        not science_mode
        and not quick_judgment
        and response_style_hint in {"relationship", "companion", "natural", "casual", "memory_recall", "selfhood"}
    )
    runtime_state_block = ""
    relationship_context_line = f"- relationship={relationship_summary}\n"
    if prefer_runtime_state_brief:
        runtime_state_brief = _prompt_state_runtime_brief(
            response_style_hint=response_style_hint,
            continuation_mode=continuation_mode,
            emotion_state=emotion,
            bond_state=bond_state,
            allostasis_state=allostasis_state,
            counterpart_assessment=counterpart_assessment,
            world_model_state=world_model_state,
            semantic_narrative_profile=semantic_narrative_profile,
            behavior_policy=behavior_policy,
            behavior_action=behavior_action,
            interaction_carryover=interaction_carryover,
            current_event=current_event,
            digital_body_state=digital_body_state,
            session_context=session_context,
            session_skill_state=session_skill_state,
        )
        runtime_state_block = (
            "运行态摘记：\n" + runtime_state_brief + "\n"
            if runtime_state_brief
            else ""
        )
        relationship_context_line = (
            f"- 和{counterpart_name}的当前关系感觉：{relationship_summary}\n"
            if relationship_summary
            else ""
        )
        user_rules_block = (
            "这轮顺手记住的说话偏好：\n" + "\n".join(rule_lines) + "\n"
            if rule_lines
            else ""
        )
        worldline_block = (
            "共同记得的事：\n" + "\n".join(worldline_lines) + "\n"
            if worldline_lines
            else ""
        )
        relationship_block = (
            "最近互动印象：\n" + "\n".join(relationship_lines) + "\n"
            if relationship_lines
            else ""
        )
        commitment_block = (
            "还挂着的约定或后续：\n" + "\n".join(commitment_lines) + "\n"
            if commitment_lines
            else ""
        )
        repair_block = (
            "最近说开的别扭：\n" + "\n".join(repair_lines) + "\n"
            if repair_lines
            else ""
        )
        unresolved_tension_block = (
            "还没完全化开的地方：\n" + "\n".join(tension_lines) + "\n"
            if tension_lines
            else ""
        )
        continuity_plan_block = (
            "前面还挂着的一点延续：\n" + "\n".join(f"- {item[:160]}" for item in continuity_plan_memory[:3]) + "\n"
            if continuity_plan_memory
            else ""
        )
        digital_body_trace_block = (
            "前面刚接回当前判断的资料或工作面：\n" + "\n".join(f"- {item[:160]}" for item in digital_body_trace_memory[:3]) + "\n"
            if digital_body_trace_memory
            else ""
        )
        working_item_fallback_block = (
            "前面顺手还带着的一点前情：\n" + "\n".join(f"- {item[:160]}" for item in working_item_fallback_texts[:3]) + "\n"
            if working_item_fallback_texts
            else ""
        )
    else:
        runtime_state_block = f"- state_snapshot={state_snapshot_json}\n"
        commitment_block = ""
        unresolved_tension_block = ""
        digital_body_trace_block = ""
        working_item_fallback_block = ""
    continuation_status_line = (
        f"- continuation_mode={continuation_mode}\n"
        if (not prefer_runtime_state_brief)
        else ""
    )
    draft_shape_block = f"回答形态：\n{draft_shape}" if draft_shape else ""
    answer_requirements = (
        f"{runtime_brief_block}"
        f"{self_anchor_block}"
        f"{draft_shape_block}"
        "当前上下文：\n"
        f"- actor={actor_name}\n"
        f"- counterpart={counterpart_name}\n"
        f"{relationship_context_line}"
        f"{runtime_state_block}"
        f"{user_rules_block}"
        f"{worldline_block}"
        f"{relationship_block}"
        f"{commitment_block}"
        f"{repair_block}"
        f"{unresolved_tension_block}"
        f"{continuity_plan_block}"
        f"{digital_body_trace_block}"
        f"{working_item_fallback_block}"
        f"{evidence_block}"
        f"{current_event_block}"
        f"{event_block}"
        f"{pending_fragment_block}"
        f"{pending_goal_block}"
        f"{continuation_instruction_block}"
        f"{continuation_status_line}\n"
        f"{'当前触发事件：' + current_event_text + chr(10) if current_event_kind != 'user_utterance' and current_event_text else ''}"
        f"{'用户输入：' + prompt_user_text + chr(10) if prompt_user_text else ''}"
        "如果需要工具，直接调用；否则直接回答。"
    )
    return header + answer_requirements
