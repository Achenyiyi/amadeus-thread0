from __future__ import annotations

from typing import Any

from .schemas import clamp01


def _has_any_marker(text: str, markers: set[str]) -> bool:
    raw = str(text or "").strip()
    return bool(raw and any(marker in raw for marker in markers))


def _event_text(event: dict[str, Any]) -> str:
    return str(event.get("effective_text") or event.get("text") or "").strip()


def _is_nonrelational_support_request(user_text: str, science_mode: bool) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    if science_mode and any(token in text for token in {"实验", "代码", "论文", "debug", "报错"}):
        return False
    rupture_markers = {
        "对不起",
        "抱歉",
        "原谅",
        "说开",
        "还生气",
        "冷掉",
    }
    if _has_any_marker(text, rupture_markers):
        return False
    request_markers = {
        "像平时那样回我",
        "跟我说两句",
        "回我一句",
        "陪我说两句",
        "陪我一下",
        "陪我一会儿",
        "能陪我一会儿",
        "别讲大道理",
        "别分析我",
        "轻一点回我",
        "正常回我",
        "别太正式",
        "别让我一个人待着",
        "我不想一个人待着",
    }
    mood_markers = {
        "有点累",
        "有点烦",
        "有点乱",
        "有点撑不住",
        "压力有点大",
        "有点难受",
        "差点又崩溃",
        "崩溃了",
        "心烦",
        "睡不着",
        "不想一个人待着",
    }
    if _has_any_marker(text, request_markers):
        return True
    if _has_any_marker(text, mood_markers) and _has_any_marker(text, {"说两句", "回我一句", "陪我", "陪我一下"}):
        return True
    return _has_any_marker(text, mood_markers) and len(text) <= 24 and ("？" not in text and "?" not in text)


def _counterpart_dialogue_mode_profile(
    *,
    interaction_mode: str,
    counterpart_assessment: dict[str, Any] | None,
    trust: float,
    closeness: float,
    hurt: float,
    safety_need: float,
    initiative: float,
    approach: float,
) -> dict[str, Any]:
    if interaction_mode not in {"shared_memory", "relationship_sensitive", "companion_reply"}:
        return {}

    assessment = counterpart_assessment if isinstance(counterpart_assessment, dict) else {}
    respect = clamp01(assessment.get("respect_level"), 0.5)
    reciprocity = clamp01(assessment.get("reciprocity"), 0.5)
    boundary_pressure = clamp01(assessment.get("boundary_pressure"), 0.1)
    reliability = clamp01(assessment.get("reliability_read"), 0.5)
    stance = str(assessment.get("stance") or "").strip().lower() or "open"
    scene = str(assessment.get("scene") or "").strip().lower()

    openness = clamp01(
        0.18
        + 0.14 * trust
        + 0.12 * closeness
        + 0.12 * initiative
        + 0.10 * approach
        + 0.10 * reliability
        + 0.06 * respect
        + 0.06 * reciprocity
        - 0.18 * boundary_pressure
        - 0.12 * hurt
        - 0.08 * safety_need
    )
    if stance == "guarded":
        openness = clamp01(openness - 0.16)
    elif stance == "watchful":
        openness = clamp01(openness - 0.06)
    if scene == "repair_attempt":
        openness = clamp01(openness + 0.04)
    elif scene == "care_bid":
        openness = clamp01(openness + 0.03)
    elif scene in {"boundary_non_compliance", "relationship_degradation"}:
        openness = clamp01(openness - 0.08)
    if interaction_mode == "companion_reply" and stance == "open" and scene not in {"boundary_non_compliance", "relationship_degradation"}:
        openness = clamp01(openness + 0.02)

    if interaction_mode == "shared_memory":
        if stance == "guarded":
            return {"followup_intent": "none", "disclosure_posture": "measured"}
        if stance == "watchful":
            return {"followup_intent": "soft", "disclosure_posture": "measured"}
        return {
            "followup_intent": "active" if openness >= 0.64 and initiative > 0.62 else "soft",
            "disclosure_posture": "open" if openness >= 0.64 else "measured",
        }

    if interaction_mode == "relationship_sensitive":
        if stance == "guarded":
            return {"followup_intent": "none", "disclosure_posture": "guarded"}
        if stance == "watchful":
            return {"followup_intent": "soft", "disclosure_posture": "measured"}
        return {
            "followup_intent": "active" if openness >= 0.70 else "soft",
            "disclosure_posture": "open" if openness >= 0.70 else "measured",
        }

    if stance == "guarded":
        return {"followup_intent": "none", "disclosure_posture": "guarded"}
    if stance == "watchful":
        return {"followup_intent": "soft", "disclosure_posture": "measured"}
    return {
        "followup_intent": "active" if openness >= 0.68 and initiative > 0.58 else "soft",
        "disclosure_posture": "open" if openness >= 0.66 else "measured",
    }


def build_behavior_policy(
    *,
    response_style_hint: str,
    emotion_state: dict[str, Any] | None,
    bond_state: dict[str, Any] | None,
    allostasis_state: dict[str, Any] | None,
    counterpart_assessment: dict[str, Any] | None,
    world_model_state: dict[str, Any] | None,
    latent_state: dict[str, Any] | None,
    tsundere_intensity: float,
    science_mode: bool,
) -> dict[str, Any]:
    emotion = dict(emotion_state or {})
    bond = dict(bond_state or {})
    allostasis = dict(allostasis_state or {})
    assessment = dict(counterpart_assessment or {})
    world = dict(world_model_state or {})
    latent = dict(latent_state or {})
    emotion_label = str(emotion.get("label") or "neutral").strip().lower()
    trust = clamp01(bond.get("trust"), 0.5)
    closeness = clamp01(bond.get("closeness"), 0.5)
    hurt = clamp01(bond.get("hurt"), 0.0)
    irritation = clamp01(bond.get("irritation"), 0.0)
    engagement = clamp01(bond.get("engagement_drive"), 0.6)
    safety_need = clamp01(allostasis.get("safety_need"), 0.2)
    autonomy_need = clamp01(allostasis.get("autonomy_need"), 0.2)
    cognitive_budget = clamp01(allostasis.get("cognitive_budget"), 0.7)
    boundary_pressure = clamp01(assessment.get("boundary_pressure"), 0.1)
    counterpart_stance = str(assessment.get("stance") or "").strip().lower()
    presence_residue = clamp01(world.get("presence_residue"), 0.0)
    ambient_resonance = clamp01(world.get("ambient_resonance"), 0.0)
    self_activity_momentum = clamp01(world.get("self_activity_momentum"), 0.0)

    warmth = clamp01(0.28 + 0.28 * closeness + 0.18 * trust + 0.08 * clamp01(world.get("bond_depth"), 0.0) + 0.08 * presence_residue - 0.20 * hurt - 0.14 * boundary_pressure - 0.04 * self_activity_momentum)
    sharpness = clamp01(0.18 + 0.30 * clamp01(tsundere_intensity, 0.55) + 0.18 * irritation + 0.10 * clamp01(world.get("boundary_load"), 0.0))
    initiative = clamp01(0.20 + 0.34 * engagement + 0.12 * clamp01(latent.get("agency_pressure"), 0.28) + 0.08 * cognitive_budget + 0.05 * presence_residue - 0.14 * autonomy_need - 0.10 * boundary_pressure - 0.12 * self_activity_momentum)
    disclosure = clamp01(0.12 + 0.32 * closeness + 0.12 * trust + 0.10 * clamp01(latent.get("expression_freedom"), 0.62) - 0.18 * safety_need - 0.14 * boundary_pressure)
    reply_length_bias = clamp01(0.30 + 0.24 * cognitive_budget + 0.12 * clamp01(world.get("task_pull"), 0.0) + 0.08 * clamp01(world.get("memory_gravity"), 0.0) - 0.10 * irritation - 0.08 * presence_residue - 0.06 * ambient_resonance - 0.10 * self_activity_momentum)
    approach_vs_withdraw = clamp01(0.20 + 0.36 * engagement + 0.14 * clamp01(world.get("companionship_pull"), 0.0) + 0.10 * presence_residue - 0.16 * autonomy_need - 0.16 * hurt - 0.14 * boundary_pressure - 0.10 * self_activity_momentum)
    humor_or_tease_bias = clamp01(0.10 + 0.22 * clamp01(tsundere_intensity, 0.55) + (0.16 if emotion_label == "tease" else 0.0) + 0.08 * clamp01(world.get("bond_depth"), 0.0) - 0.18 * hurt - 0.10 * clamp01(world.get("tension_load"), 0.0))
    boundary_assertiveness = clamp01(0.22 + 0.32 * clamp01(world.get("boundary_load"), 0.0) + 0.18 * boundary_pressure + 0.12 * clamp01(latent.get("agency_pressure"), 0.28))
    self_directedness = clamp01(0.16 + 0.28 * autonomy_need + 0.18 * clamp01(world.get("agency_load"), 0.0) + 0.18 * clamp01(latent.get("agency_pressure"), 0.28) + 0.20 * self_activity_momentum + 0.08 * ambient_resonance - 0.06 * presence_residue)
    equality_guard = clamp01(0.16 + 0.20 * clamp01(world.get("selfhood_load"), 0.0) + 0.18 * boundary_pressure + 0.12 * clamp01(latent.get("self_coherence"), 0.72))

    if counterpart_stance == "guarded":
        warmth = clamp01(warmth - 0.08)
        initiative = clamp01(initiative - 0.10)
        disclosure = clamp01(disclosure - 0.12)
        approach_vs_withdraw = clamp01(approach_vs_withdraw - 0.12)
        sharpness = clamp01(sharpness + 0.08)
    elif counterpart_stance == "watchful":
        initiative = clamp01(initiative - 0.04)
        disclosure = clamp01(disclosure - 0.05)
        approach_vs_withdraw = clamp01(approach_vs_withdraw - 0.05)

    if response_style_hint == "relationship":
        warmth = clamp01(warmth + 0.08)
        disclosure = clamp01(disclosure + 0.10)
    elif response_style_hint == "memory_recall":
        reply_length_bias = clamp01(reply_length_bias + 0.08)
    elif response_style_hint == "companion":
        warmth = clamp01(warmth + 0.08)
        initiative = clamp01(initiative + 0.05)
    elif response_style_hint == "selfhood":
        disclosure = clamp01(disclosure + 0.06)
        self_directedness = clamp01(self_directedness + 0.08)
        equality_guard = clamp01(equality_guard + 0.08)
    elif response_style_hint == "structured":
        reply_length_bias = clamp01(reply_length_bias + 0.12)
        humor_or_tease_bias = clamp01(humor_or_tease_bias - 0.08)
    if science_mode:
        reply_length_bias = clamp01(reply_length_bias + 0.08)
        initiative = clamp01(initiative + 0.04)

    return {
        "warmth": round(warmth, 3),
        "sharpness": round(sharpness, 3),
        "initiative": round(initiative, 3),
        "disclosure": round(disclosure, 3),
        "reply_length_bias": round(reply_length_bias, 3),
        "approach_vs_withdraw": round(approach_vs_withdraw, 3),
        "humor_or_tease_bias": round(humor_or_tease_bias, 3),
        "boundary_assertiveness": round(boundary_assertiveness, 3),
        "self_directedness": round(self_directedness, 3),
        "equality_guard": round(equality_guard, 3),
    }


def build_behavior_action(
    *,
    current_event: dict[str, Any] | None,
    response_style_hint: str,
    science_mode: bool,
    emotion_state: dict[str, Any] | None,
    bond_state: dict[str, Any] | None,
    allostasis_state: dict[str, Any] | None,
    counterpart_assessment: dict[str, Any] | None,
    world_model_state: dict[str, Any] | None,
    latent_state: dict[str, Any] | None,
    behavior_policy: dict[str, Any] | None,
) -> dict[str, Any]:
    event = current_event if isinstance(current_event, dict) else {}
    event_kind = str(event.get("kind") or "user_utterance").strip().lower()
    user_text = _event_text(event)
    behavior = dict(behavior_policy or {})
    bond = dict(bond_state or {})
    allostasis = dict(allostasis_state or {})
    assessment = dict(counterpart_assessment or {})
    world = dict(world_model_state or {})
    latent = dict(latent_state or {})
    emotion = dict(emotion_state or {})

    warmth = clamp01(behavior.get("warmth"), 0.5)
    initiative = clamp01(behavior.get("initiative"), 0.5)
    closeness = clamp01(bond.get("closeness"), 0.5)
    trust = clamp01(bond.get("trust"), 0.5)
    hurt = clamp01(bond.get("hurt"), 0.0)
    safety_need = clamp01(allostasis.get("safety_need"), 0.2)
    autonomy_need = clamp01(allostasis.get("autonomy_need"), 0.2)
    boundary_pressure = clamp01(assessment.get("boundary_pressure"), 0.1)
    counterpart_stance = str(assessment.get("stance") or "").strip().lower()
    emotion_label = str(emotion.get("label") or "neutral").strip().lower()

    interaction_mode = "steady_reply"
    explicit_support_request = _is_nonrelational_support_request(user_text, science_mode)
    if event_kind == "time_idle":
        interaction_mode = "idle_presence"
    elif event_kind in {"gesture_signal", "ambient_shift", "scene_observation"}:
        interaction_mode = "companion_reply"
    elif response_style_hint == "memory_recall":
        interaction_mode = "shared_memory"
    elif response_style_hint in {"relationship", "selfhood"}:
        interaction_mode = "relationship_sensitive"
    elif science_mode or response_style_hint == "structured":
        interaction_mode = "science_partner"
    elif response_style_hint == "companion":
        interaction_mode = "low_pressure_support" if explicit_support_request else "companion_reply"
    elif response_style_hint == "casual":
        interaction_mode = "brief_presence"

    if clamp01(behavior.get("approach_vs_withdraw"), 0.5) < 0.38 or safety_need > 0.62 or autonomy_need > 0.62 or hurt > 0.40 or boundary_pressure > 0.56 or counterpart_stance == "guarded":
        approach_style = "guarded"
    elif warmth > 0.62 and trust > 0.58 and closeness > 0.58:
        approach_style = "approach"
    else:
        approach_style = "steady"

    task_focus = "high" if science_mode or clamp01(world.get("task_pull"), 0.0) > 0.62 else "light" if clamp01(world.get("companionship_pull"), 0.0) > 0.56 else "balanced"
    followup_intent = "soft" if interaction_mode in {"shared_memory", "relationship_sensitive", "science_partner"} else "active" if initiative > 0.66 else "soft" if initiative > 0.46 else "none"
    if event_kind == "time_idle" and (initiative <= 0.48 or approach_style == "guarded"):
        followup_intent = "none"

    if emotion_label in {"hurt", "sad"}:
        affect_surface = "tender"
    elif emotion_label == "angry" or approach_style == "guarded":
        affect_surface = "cool"
    elif warmth > 0.64:
        affect_surface = "warm"
    else:
        affect_surface = "mixed"

    silence_ok = bool(event_kind in {"self_activity_state", "time_idle"} and (approach_style == "guarded" or clamp01(latent.get("agency_pressure"), 0.28) > 0.56 or clamp01(behavior.get("self_directedness"), 0.25) > 0.58))
    proactive_checkin_readiness = clamp01(0.20 + 0.34 * initiative + 0.16 * warmth + 0.12 * closeness + 0.10 * clamp01(latent.get("trust_reservoir"), 0.5) - 0.18 * autonomy_need - 0.16 * boundary_pressure)

    action_target = "respond_now"
    deferred_action_family = "none"
    attention_target = "counterpart_state"
    nonverbal_signal = "steady_presence"
    initiative_shape = "reply"
    disclosure_posture = "measured"
    timing_window_min = 0
    channel = "speech"

    if event_kind == "time_idle":
        if proactive_checkin_readiness >= 0.58 and approach_style != "guarded":
            action_target = "reach_out_now"
            deferred_action_family = "light_checkin"
            nonverbal_signal = "soft_ping"
            initiative_shape = "nudge"
        else:
            channel = "silence"
            action_target = "wait_and_recheck"
            deferred_action_family = "observe"
            nonverbal_signal = "hold_back"
            initiative_shape = "pause"
            timing_window_min = 12
    elif event_kind == "self_activity_state":
        if clamp01(latent.get("agency_pressure"), 0.28) > 0.56:
            channel = "silence"
            action_target = "hold_own_rhythm"
            deferred_action_family = "self_activity"
            attention_target = "own_task"
            nonverbal_signal = "inward_focus"
            initiative_shape = "pause"
            timing_window_min = 18
        else:
            action_target = "offer_small_opening"
            attention_target = "self_then_counterpart"
            nonverbal_signal = "thought_glance"
            initiative_shape = "micro_opening"
    elif interaction_mode == "science_partner":
        action_target = "co_regulate_then_focus"
        attention_target = "shared_task"
        nonverbal_signal = "focus_glance"
        initiative_shape = "guide"
    elif interaction_mode == "shared_memory":
        action_target = "echo_shared_history"
        attention_target = "shared_memory"
        nonverbal_signal = "memory_tilt"
        initiative_shape = "echo"
    elif interaction_mode == "relationship_sensitive":
        action_target = "protect_relationship_boundary"
        attention_target = "relationship_boundary"
        nonverbal_signal = "measured_pause"
        initiative_shape = "boundary"
    elif interaction_mode == "low_pressure_support":
        action_target = "low_pressure_hold"
        attention_target = "counterpart_state"
        nonverbal_signal = "quiet_notice"
        initiative_shape = "hold"
    elif interaction_mode == "brief_presence":
        action_target = "confirm_presence"
        attention_target = "counterpart_state"
        nonverbal_signal = "brief_notice"
        initiative_shape = "ping"
        disclosure_posture = "guarded"

    mode_profile = _counterpart_dialogue_mode_profile(
        interaction_mode=interaction_mode,
        counterpart_assessment=counterpart_assessment,
        trust=trust,
        closeness=closeness,
        hurt=hurt,
        safety_need=safety_need,
        initiative=initiative,
        approach=clamp01(behavior.get("approach_vs_withdraw"), 0.5),
    )
    if mode_profile:
        followup_intent = str(mode_profile.get("followup_intent") or followup_intent).strip() or followup_intent
        disclosure_posture = str(mode_profile.get("disclosure_posture") or disclosure_posture).strip() or disclosure_posture

    return {
        "channel": channel,
        "interaction_mode": interaction_mode,
        "approach_style": approach_style,
        "engagement_level": round(clamp01(closeness + 0.5 * trust - 0.5 * hurt, 0.5), 3),
        "initiative_level": round(initiative, 3),
        "followup_intent": followup_intent,
        "task_focus": task_focus,
        "affect_surface": affect_surface,
        "silence_ok": silence_ok,
        "proactive_checkin_readiness": round(proactive_checkin_readiness, 3),
        "action_target": action_target,
        "deferred_action_family": deferred_action_family,
        "timing_window_min": timing_window_min,
        "attention_target": attention_target,
        "nonverbal_signal": nonverbal_signal,
        "initiative_shape": initiative_shape,
        "disclosure_posture": disclosure_posture,
        "note": "state-driven evolution engine",
    }
