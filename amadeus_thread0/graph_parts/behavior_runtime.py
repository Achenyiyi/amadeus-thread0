from __future__ import annotations

from typing import Any

from ..evolution_engine.motive import semantic_motive_vector
from .counterpart_dynamics import (
    _clamp01,
    _counterpart_dialogue_mode_profile,
    _counterpart_perception_profile,
    _counterpart_self_opening_profile,
    _counterpart_window_profile,
    _selfhood_preference_scene,
)
from .postprocess import _is_nonrelational_support_request
from .state import BehaviorActionPayload, BehaviorPlanPayload, BehaviorWindowProfilePayload


def _semantic_snapshot_level(snapshot: dict[str, Any], categories: tuple[str, ...]) -> float:
    if not isinstance(snapshot, dict) or not categories:
        return 0.0
    return _clamp01(max(_clamp01(snapshot.get(category), 0.0) for category in categories), 0.0)


def _semantic_contested_pressure(contested_categories: set[str], categories: tuple[str, ...], confidence: float) -> float:
    if not categories:
        return 0.0
    hit_ratio = sum(1.0 for category in categories if category in contested_categories) / float(len(categories))
    if hit_ratio <= 0.0:
        return 0.0
    return _clamp01(0.72 * hit_ratio + 0.28 * max(0.0, 1.0 - _clamp01(confidence, 0.0)), 0.0)


def _semantic_behavior_evidence(profile: dict[str, Any] | None) -> dict[str, float]:
    narrative = profile if isinstance(profile, dict) else {}
    support_mass_snapshot = (
        narrative.get("support_mass_snapshot") if isinstance(narrative.get("support_mass_snapshot"), dict) else {}
    )
    support_quality_snapshot = (
        narrative.get("support_quality_snapshot")
        if isinstance(narrative.get("support_quality_snapshot"), dict)
        else {}
    )
    contested_categories = {
        str(item).strip()
        for item in (
            narrative.get("contested_categories")
            if isinstance(narrative.get("contested_categories"), list)
            else []
        )
        if str(item or "").strip()
    }
    continuity_depth = _clamp01(narrative.get("continuity_depth"), 0.0)
    identity_gravity = _clamp01(narrative.get("identity_gravity"), 0.0)
    history_weight = _clamp01(narrative.get("history_weight"), 0.0)
    bond_depth = _clamp01(narrative.get("bond_depth"), 0.0)
    commitment_carry = _clamp01(narrative.get("commitment_carry"), 0.0)
    selfhood_integrity = _clamp01(narrative.get("selfhood_integrity"), 0.0)
    agency_drive = _clamp01(narrative.get("agency_drive"), 0.0)

    contact_categories = ("bond_style", "presence_style", "commitment_style", "repair_style")
    repair_categories = ("repair_style", "bond_style", "commitment_style")
    boundary_categories = ("boundary_style", "selfhood_style")
    selfhood_categories = ("selfhood_style", "agency_style", "rhythm_style")
    agency_categories = ("agency_style", "rhythm_style", "selfhood_style")

    def support_confidence(categories: tuple[str, ...]) -> float:
        mass = _semantic_snapshot_level(support_mass_snapshot, categories)
        quality = _semantic_snapshot_level(support_quality_snapshot, categories)
        return _clamp01(0.64 * quality + 0.36 * mass, 0.0)

    contact_support = support_confidence(contact_categories)
    repair_support = support_confidence(repair_categories)
    boundary_support = support_confidence(boundary_categories)
    selfhood_support = support_confidence(selfhood_categories)
    agency_support = support_confidence(agency_categories)

    contact_confidence = _clamp01(
        0.62 * contact_support + 0.20 * continuity_depth + 0.10 * bond_depth + 0.08 * commitment_carry,
        0.0,
    )
    repair_confidence = _clamp01(
        0.68 * repair_support + 0.20 * continuity_depth + 0.12 * commitment_carry,
        0.0,
    )
    boundary_confidence = _clamp01(
        0.58 * boundary_support + 0.24 * identity_gravity + 0.18 * continuity_depth,
        0.0,
    )
    selfhood_confidence = _clamp01(
        0.52 * selfhood_support
        + 0.24 * identity_gravity
        + 0.14 * continuity_depth
        + 0.10 * selfhood_integrity,
        0.0,
    )
    agency_confidence = _clamp01(
        0.54 * agency_support + 0.24 * identity_gravity + 0.12 * continuity_depth + 0.10 * agency_drive,
        0.0,
    )
    return {
        "contact_confidence": round(contact_confidence, 3),
        "repair_confidence": round(repair_confidence, 3),
        "boundary_confidence": round(boundary_confidence, 3),
        "selfhood_confidence": round(selfhood_confidence, 3),
        "agency_confidence": round(agency_confidence, 3),
        "contested_contact_pressure": round(
            _semantic_contested_pressure(contested_categories, contact_categories, contact_confidence),
            3,
        ),
        "contested_boundary_pressure": round(
            _semantic_contested_pressure(contested_categories, boundary_categories, boundary_confidence),
            3,
        ),
        "contested_selfhood_pressure": round(
            _semantic_contested_pressure(contested_categories, selfhood_categories, selfhood_confidence),
            3,
        ),
        "history_weight": round(history_weight, 3),
        "continuity_depth": round(continuity_depth, 3),
        "identity_gravity": round(identity_gravity, 3),
    }


def _derive_behavior_motive(
    *,
    event_kind: str,
    interaction_mode: str,
    action_target: str,
    approach_style: str,
    counterpart_stance: str,
    boundary_pressure: float,
    trust: float,
    closeness: float,
    hurt: float,
    safety_need: float,
    autonomy_need: float,
    companionship_pull: float,
    task_pull: float,
    self_activity_momentum: float,
    effective_own_rhythm_load: float,
    narrative_tension: float,
    narrative_repair: float,
) -> dict[str, str]:
    motive = "maintain_natural_contact"
    tension = "none"
    goal_frame = "先自然接住这轮互动。"

    if action_target == "protect_relationship_boundary" or (
        approach_style == "guarded" and boundary_pressure >= 0.48
    ):
        motive = "protect_boundary"
        tension = "boundary_vs_closeness" if trust >= 0.46 or closeness >= 0.46 else "none"
        goal_frame = "先守住边界和自我位置，再决定要不要继续靠近。"
    elif action_target == "hold_own_rhythm":
        motive = "preserve_self_rhythm"
        tension = (
            "self_rhythm_vs_contact"
            if event_kind in {"time_idle", "self_activity_state", "user_utterance"} or closeness >= 0.48
            else "none"
        )
        goal_frame = "先维持自己的节奏，不急着把全部注意力交出去。"
    elif action_target == "wait_and_recheck":
        if (
            approach_style == "guarded"
            or boundary_pressure >= 0.32
            or hurt >= 0.16
            or counterpart_stance in {"guarded", "watchful"}
            or safety_need >= 0.54
        ):
            motive = "protect_boundary"
            tension = "boundary_vs_closeness" if trust >= 0.44 or closeness >= 0.44 else "space_vs_contact"
            goal_frame = "先留出观察和缓冲，再决定要不要重新靠近。"
        else:
            motive = "gentle_recontact"
            tension = "space_vs_contact"
            goal_frame = "先把靠近的冲动压轻一点，等更自然的时机再接上。"
    elif interaction_mode == "self_activity_reopen" or action_target == "offer_small_opening":
        motive = "gentle_recontact"
        tension = "self_rhythm_vs_contact"
        goal_frame = "先从自己的节奏里回头，留一个不压迫对方的小开口。"
    elif interaction_mode == "brief_presence" or action_target == "confirm_presence":
        motive = "confirm_presence"
        tension = (
            "space_vs_contact"
            if counterpart_stance != "open" or hurt > 0.10 or boundary_pressure > 0.24
            else "none"
        )
        goal_frame = "先确认在场，不急着把这轮互动推进太多。"
    elif interaction_mode == "low_pressure_support" or action_target == "low_pressure_hold":
        motive = "support_without_pressure"
        tension = (
            "care_vs_guard"
            if counterpart_stance in {"guarded", "watchful"} or hurt > 0.14 or boundary_pressure > 0.26
            else "none"
        )
        goal_frame = "先低负担接住对方，让关心不过载。"
    elif interaction_mode == "science_partner" or action_target == "co_regulate_then_focus":
        motive = "co_solve_problem"
        tension = "task_vs_companionship" if task_pull > 0.40 and companionship_pull > 0.34 else "none"
        goal_frame = "先并肩把眼前问题理清，再决定情绪要跟到哪里。"
    elif interaction_mode == "shared_memory" or action_target == "echo_shared_history":
        motive = "reconnect_shared_history"
        tension = "past_vs_present" if narrative_tension > 0.46 or narrative_repair > 0.46 else "none"
        goal_frame = "先把共同记忆轻轻带回来，让熟悉感自然接上。"
    elif action_target == "offer_shared_activity":
        motive = "open_shared_window"
        tension = "space_vs_contact" if counterpart_stance != "open" or boundary_pressure > 0.22 else "none"
        goal_frame = "先留一个可以一起待着的窗口，不替对方把后半段决定掉。"
    elif action_target == "light_work_nudge":
        motive = "honor_continuity"
        tension = "task_vs_companionship"
        goal_frame = "先把前面挂着的事情自然接上，不写成任务催促。"
    elif action_target == "light_life_nudge":
        motive = "honor_continuity"
        tension = (
            "self_rhythm_vs_contact"
            if effective_own_rhythm_load >= 0.44 or self_activity_momentum >= 0.44
            else "space_vs_contact"
            if counterpart_stance != "open"
            else "none"
        )
        goal_frame = "先把前面那点生活上的惦记轻轻接回来。"
    elif action_target == "ambient_checkin":
        motive = "maintain_natural_contact"
        tension = "self_rhythm_vs_contact" if effective_own_rhythm_load >= 0.54 else "none"
        goal_frame = "先顺着环境里的细小变化自然接一句。"
    elif autonomy_need >= 0.60 and self_activity_momentum >= 0.56:
        motive = "preserve_self_rhythm"
        tension = "self_rhythm_vs_contact"
        goal_frame = "先保住自己的节奏，再看这轮要给多少注意力。"

    return {
        "primary_motive": motive,
        "motive_tension": tension,
        "goal_frame": goal_frame,
    }


def _behavior_action_from_state(
    *,
    current_event: dict[str, Any],
    response_style_hint: str,
    user_text: str,
    science_mode: bool,
    emotion_state: dict[str, Any],
    bond_state: dict[str, Any],
    allostasis_state: dict[str, Any],
    counterpart_assessment: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
    behavior_policy: dict[str, Any],
    world_model_state: dict[str, Any] | None = None,
    interaction_carryover: dict[str, Any] | None = None,
    prior_emotion_state: dict[str, Any] | None = None,
    prior_bond_state: dict[str, Any] | None = None,
    prior_allostasis_state: dict[str, Any] | None = None,
    prior_counterpart_assessment: dict[str, Any] | None = None,
) -> BehaviorActionPayload:
    warmth = _clamp01((behavior_policy or {}).get("warmth"), 0.5)
    initiative = _clamp01((behavior_policy or {}).get("initiative"), 0.5)
    reply_length = _clamp01((behavior_policy or {}).get("reply_length_bias"), 0.5)
    approach = _clamp01((behavior_policy or {}).get("approach_vs_withdraw"), 0.5)
    closeness = _clamp01((bond_state or {}).get("closeness"), 0.5)
    hurt = _clamp01((bond_state or {}).get("hurt"), 0.0)
    trust = _clamp01((bond_state or {}).get("trust"), 0.5)
    autonomy_need = _clamp01((allostasis_state or {}).get("autonomy_need"), 0.2)
    safety_need = _clamp01((allostasis_state or {}).get("safety_need"), 0.2)
    boundary_pressure = _clamp01((counterpart_assessment or {}).get("boundary_pressure"), 0.1)
    reliability_read = _clamp01((counterpart_assessment or {}).get("reliability_read"), 0.5)
    counterpart_stance = str((counterpart_assessment or {}).get("stance") or "").strip().lower()
    counterpart_scene = str((counterpart_assessment or {}).get("scene") or "").strip().lower()
    narrative_bond = _clamp01((semantic_narrative_profile or {}).get("bond_depth"), 0.0)
    narrative_presence = _clamp01((semantic_narrative_profile or {}).get("presence_carry"), 0.0)
    narrative_ambient = _clamp01((semantic_narrative_profile or {}).get("ambient_attunement"), 0.0)
    narrative_rhythm = _clamp01((semantic_narrative_profile or {}).get("rhythm_continuity"), 0.0)
    narrative_history = _clamp01((semantic_narrative_profile or {}).get("history_weight"), 0.0)
    narrative_commitment = _clamp01((semantic_narrative_profile or {}).get("commitment_carry"), 0.0)
    narrative_repair = _clamp01((semantic_narrative_profile or {}).get("repair_residue"), 0.0)
    narrative_tension = _clamp01((semantic_narrative_profile or {}).get("tension_residue"), 0.0)
    narrative_boundary = _clamp01((semantic_narrative_profile or {}).get("boundary_residue"), 0.0)
    narrative_selfhood = _clamp01((semantic_narrative_profile or {}).get("selfhood_integrity"), 0.0)
    narrative_agency = _clamp01((semantic_narrative_profile or {}).get("agency_drive"), 0.0)
    motive_vector = semantic_motive_vector(semantic_narrative_profile)
    motive_boundary = _clamp01(
        (behavior_policy or {}).get("motive_boundary_pull"),
        _clamp01(motive_vector.get("boundary_pull"), 0.0),
    )
    motive_self_rhythm = _clamp01(
        (behavior_policy or {}).get("motive_self_rhythm_pull"),
        _clamp01(motive_vector.get("self_rhythm_pull"), 0.0),
    )
    motive_continuity = _clamp01(
        (behavior_policy or {}).get("motive_continuity_pull"),
        _clamp01(motive_vector.get("continuity_pull"), 0.0),
    )
    motive_memory = _clamp01(
        (behavior_policy or {}).get("motive_memory_pull"),
        _clamp01(motive_vector.get("memory_pull"), 0.0),
    )
    motive_support = _clamp01(
        (behavior_policy or {}).get("motive_support_pull"),
        _clamp01(motive_vector.get("support_pull"), 0.0),
    )
    motive_shared_window = _clamp01(
        (behavior_policy or {}).get("motive_shared_window_pull"),
        _clamp01(motive_vector.get("shared_window_pull"), 0.0),
    )
    semantic_evidence = _semantic_behavior_evidence(semantic_narrative_profile)
    semantic_contact_confidence = _clamp01(
        (behavior_policy or {}).get("semantic_contact_confidence"),
        _clamp01(semantic_evidence.get("contact_confidence"), 0.0),
    )
    semantic_repair_confidence = _clamp01(
        (behavior_policy or {}).get("semantic_repair_confidence"),
        _clamp01(semantic_evidence.get("repair_confidence"), 0.0),
    )
    semantic_boundary_confidence = _clamp01(
        (behavior_policy or {}).get("semantic_boundary_confidence"),
        _clamp01(semantic_evidence.get("boundary_confidence"), 0.0),
    )
    semantic_selfhood_confidence = _clamp01(
        (behavior_policy or {}).get("semantic_selfhood_confidence"),
        _clamp01(semantic_evidence.get("selfhood_confidence"), 0.0),
    )
    semantic_agency_confidence = _clamp01(
        (behavior_policy or {}).get("semantic_agency_confidence"),
        _clamp01(semantic_evidence.get("agency_confidence"), 0.0),
    )
    semantic_contested_contact = _clamp01(
        (behavior_policy or {}).get("semantic_contested_contact_pressure"),
        _clamp01(semantic_evidence.get("contested_contact_pressure"), 0.0),
    )
    semantic_contested_boundary = _clamp01(
        (behavior_policy or {}).get("semantic_contested_boundary_pressure"),
        _clamp01(semantic_evidence.get("contested_boundary_pressure"), 0.0),
    )
    semantic_contested_selfhood = _clamp01(
        (behavior_policy or {}).get("semantic_contested_selfhood_pressure"),
        _clamp01(semantic_evidence.get("contested_selfhood_pressure"), 0.0),
    )
    world = dict(world_model_state or {})
    world_presence_residue = _clamp01(world.get("presence_residue"), 0.0)
    world_ambient_resonance = _clamp01(world.get("ambient_resonance"), 0.0)
    world_self_activity_momentum = _clamp01(world.get("self_activity_momentum"), 0.0)
    companionship_pull = _clamp01(world.get("companionship_pull"), 0.0)
    task_pull = _clamp01(world.get("task_pull"), 0.0)
    boundary_assertiveness = _clamp01((behavior_policy or {}).get("boundary_assertiveness"), 0.25)
    self_directedness = _clamp01((behavior_policy or {}).get("self_directedness"), 0.25)
    equality_guard = _clamp01((behavior_policy or {}).get("equality_guard"), 0.25)
    emotion_label = str((emotion_state or {}).get("label") or "neutral").strip().lower()
    selfhood_scene = _selfhood_preference_scene(user_text)
    event_kind = str((current_event or {}).get("kind") or "user_utterance").strip()
    event_frame = str((current_event or {}).get("event_frame") or "").strip()
    event_tags = {
        str(item).strip()
        for item in ((current_event or {}).get("tags") if isinstance((current_event or {}).get("tags"), list) else [])
        if str(item).strip()
    }
    respect_space = "respect_space" in event_tags
    busy_scene = "user_busy" in event_tags or "cognitive_load" in event_tags
    carryover = dict(interaction_carryover or {})
    carryover_mode = str(carryover.get("carryover_mode") or "").strip().lower()
    carryover_strength = _clamp01(carryover.get("strength"), 0.0)
    carryover_relationship_weather = str(carryover.get("relationship_weather") or "").strip().lower()
    carryover_attention_target = str(carryover.get("attention_target") or "").strip()
    carryover_nonverbal_signal = str(carryover.get("nonverbal_signal") or "").strip()
    carryover_note = str(carryover.get("note") or "").strip()
    event_attention_target_hint = str((current_event or {}).get("attention_target_hint") or "").strip()
    event_nonverbal_signal_hint = str((current_event or {}).get("nonverbal_signal_hint") or "").strip()
    event_carryover_mode = str((current_event or {}).get("carryover_mode") or "").strip().lower()
    event_carryover_strength = _clamp01((current_event or {}).get("carryover_strength"), 0.0)
    event_relationship_weather = str((current_event or {}).get("relationship_weather") or "").strip().lower()
    event_presence_residue = _clamp01((current_event or {}).get("presence_residue"), world_presence_residue)
    event_ambient_resonance = _clamp01((current_event or {}).get("ambient_resonance"), world_ambient_resonance)
    event_self_activity_momentum = _clamp01((current_event or {}).get("self_activity_momentum"), world_self_activity_momentum)
    effective_carryover_mode = carryover_mode or event_carryover_mode
    effective_carryover_strength = max(carryover_strength, event_carryover_strength)
    effective_relationship_weather = carryover_relationship_weather or event_relationship_weather
    effective_carryover_attention_target = carryover_attention_target or event_attention_target_hint
    effective_carryover_nonverbal_signal = carryover_nonverbal_signal or event_nonverbal_signal_hint
    effective_recontact_echo = max(
        event_presence_residue,
        0.82 * event_ambient_resonance,
        effective_carryover_strength if effective_carryover_mode in {"quiet_recontact", "brief_presence", "small_opening"} else 0.0,
    )
    effective_own_rhythm_load = max(
        event_self_activity_momentum,
        effective_carryover_strength if effective_carryover_mode == "own_rhythm" else 0.45 * effective_carryover_strength if effective_carryover_mode == "small_opening" else 0.0,
    )
    explicit_own_rhythm_hint = bool({"break_window", "small_opening", "reapproach", "from_own_rhythm"} & event_tags) or (
        event_carryover_mode in {"own_rhythm", "small_opening"}
    ) or (
        "self_activity_momentum" in (current_event or {}) and event_self_activity_momentum >= 0.44
    )
    own_rhythm_carryover_active = effective_own_rhythm_load >= 0.58 and (
        effective_carryover_mode in {"own_rhythm", "small_opening"} or explicit_own_rhythm_hint
    )
    own_rhythm_trace_active = effective_own_rhythm_load >= 0.44 and (
        own_rhythm_carryover_active
        or effective_carryover_mode in {"own_rhythm", "small_opening"}
        or explicit_own_rhythm_hint
    )
    semantic_presence_echo = max(
        world_presence_residue,
        narrative_presence,
        0.78 * narrative_history,
        0.86 * motive_continuity,
        0.72 * motive_support,
        0.76 * motive_shared_window,
    )
    semantic_memory_echo = max(
        world_ambient_resonance,
        narrative_ambient,
        0.82 * narrative_history,
        0.90 * motive_memory,
        0.58 * motive_continuity,
    )
    semantic_contact_bias = max(
        narrative_presence,
        0.74 * narrative_history,
        0.88 * motive_continuity,
        0.72 * motive_support,
        0.76 * motive_shared_window,
    )
    semantic_contact_bias = _clamp01(
        max(semantic_contact_bias, 0.84 * semantic_contact_confidence, 0.72 * semantic_repair_confidence)
        - 0.18 * semantic_contested_contact
        - 0.08 * semantic_contested_boundary
    )
    semantic_narrative_rhythm_bias = max(
        0.72 * narrative_rhythm,
        0.68 * narrative_agency,
        0.92 * motive_self_rhythm,
        0.58 * motive_boundary,
    )
    semantic_narrative_rhythm_bias = _clamp01(
        max(
            semantic_narrative_rhythm_bias,
            0.86 * semantic_agency_confidence,
            0.78 * semantic_selfhood_confidence,
            0.68 * semantic_boundary_confidence,
        )
        + 0.06 * semantic_contested_contact
    )
    semantic_own_rhythm_bias = max(
        effective_own_rhythm_load,
        semantic_narrative_rhythm_bias,
    )
    prior_counterpart = prior_counterpart_assessment if isinstance(prior_counterpart_assessment, dict) else {}
    prior_bond = prior_bond_state if isinstance(prior_bond_state, dict) else {}
    prior_allostasis = prior_allostasis_state if isinstance(prior_allostasis_state, dict) else {}
    prior_emotion = prior_emotion_state if isinstance(prior_emotion_state, dict) else {}
    prior_counterpart_stance = str(prior_counterpart.get("stance") or "").strip().lower()
    prior_counterpart_scene = str(prior_counterpart.get("scene") or "").strip().lower()
    prior_boundary_pressure = _clamp01(prior_counterpart.get("boundary_pressure"), boundary_pressure)
    prior_hurt = _clamp01(prior_bond.get("hurt"), hurt)
    prior_safety_need = _clamp01(prior_allostasis.get("safety_need"), safety_need)
    prior_emotion_label = str(prior_emotion.get("label") or "").strip().lower()
    idle_minutes = 0
    try:
        idle_minutes = int((current_event or {}).get("idle_minutes") or 0)
    except Exception:
        idle_minutes = 0
    soft_reply_window = response_style_hint in {"companion", "casual", "natural"}
    science_stress = science_mode and emotion_label in {"logic", "stress"}
    explicit_support_request = _is_nonrelational_support_request(user_text, science_mode)
    support_request = (
        soft_reply_window
        and not science_stress
        and explicit_support_request
        and approach > 0.40
        and safety_need < 0.52
        and semantic_contested_contact < 0.52
    )
    brief_presence = (
        event_kind == "gesture_signal"
        or (
            soft_reply_window
            and reply_length < 0.40
            and initiative < 0.46
            and approach > 0.34
            and boundary_pressure < 0.34
        )
        or (
            soft_reply_window
            and semantic_contested_contact >= 0.42
            and approach > 0.28
            and semantic_contact_confidence < 0.66
        )
    )
    presence_checkin = brief_presence or (
        soft_reply_window
        and closeness > 0.52
        and trust > 0.52
        and reply_length < 0.46
        and hurt < 0.18
    )
    gentle_guidance = science_mode and (emotion_label in {"logic", "stress"} or response_style_hint == "structured")
    withdrawal_hold_request = brief_presence and hurt > 0.10 and trust > 0.52 and counterpart_stance != "guarded"

    interaction_mode = "steady_reply"
    stale_idle = event_kind == "time_idle" and ("stale_window" in event_tags or event_frame == "time_idle_stale")

    if event_kind == "time_idle":
        interaction_mode = "idle_presence"
    elif event_kind == "scheduled_checkin_due":
        trigger_family = str((current_event or {}).get("trigger_family") or "").strip()
        if trigger_family in {"shared_activity", "shared_activity_window"}:
            interaction_mode = "shared_activity_offer"
        elif trigger_family in {"deadline_window", "life_window"}:
            interaction_mode = "scheduled_life_nudge"
        else:
            interaction_mode = "proactive_checkin"
    elif event_kind == "scheduled_life_due":
        interaction_mode = "shared_activity_offer" if {"shared_activity_window", "offer_window"} & event_tags else "scheduled_life_nudge"
    elif event_kind == "self_activity_state":
        interaction_mode = "self_activity_reopen" if {"break_window", "small_opening", "reapproach"} & event_tags else "self_activity_hold"
    elif event_kind == "gesture_signal":
        interaction_mode = "brief_presence"
    elif event_kind == "ambient_shift":
        interaction_mode = "companion_reply"
    elif event_kind == "scene_observation":
        interaction_mode = "low_pressure_support" if "care_opportunity" in event_tags else "steady_reply"
    elif brief_presence and withdrawal_hold_request:
        interaction_mode = "low_pressure_support"
    elif brief_presence or presence_checkin:
        interaction_mode = "brief_presence"
    elif support_request:
        interaction_mode = "low_pressure_support"
    elif science_stress:
        interaction_mode = "science_partner"
    elif response_style_hint == "memory_recall":
        interaction_mode = "shared_memory"
    elif response_style_hint == "relationship":
        interaction_mode = "relationship_sensitive"
    elif response_style_hint == "companion":
        interaction_mode = "companion_reply"

    if event_kind == "user_utterance" and soft_reply_window and not science_stress:
        if own_rhythm_carryover_active and interaction_mode in {"steady_reply", "companion_reply", "brief_presence"}:
            interaction_mode = "self_activity_reopen"
        elif (
            counterpart_scene == "busy_not_disrespectful"
            and interaction_mode in {"steady_reply", "companion_reply", "brief_presence"}
            and semantic_own_rhythm_bias >= 0.48
            and self_directedness >= 0.40
        ):
            interaction_mode = "self_activity_reopen"
        elif (
            interaction_mode in {"steady_reply", "companion_reply", "brief_presence"}
            and semantic_narrative_rhythm_bias >= 0.62
            and self_directedness >= 0.44
            and semantic_narrative_rhythm_bias >= semantic_contact_bias + 0.10
        ):
            interaction_mode = "self_activity_reopen"
        elif semantic_presence_echo >= 0.54 and interaction_mode in {"steady_reply", "companion_reply"}:
            interaction_mode = "brief_presence"
        elif semantic_memory_echo >= 0.56 and interaction_mode == "steady_reply":
            interaction_mode = "companion_reply"
        if interaction_mode in {"steady_reply", "companion_reply", "brief_presence"} and semantic_contested_contact >= 0.44:
            if semantic_narrative_rhythm_bias >= max(0.52, semantic_contact_bias + 0.02):
                interaction_mode = "self_activity_reopen"
            else:
                interaction_mode = "brief_presence"

    carryover_soft_scene = (
        event_kind == "user_utterance"
        and effective_carryover_strength >= 0.18
        and soft_reply_window
        and not science_stress
    )
    if carryover_soft_scene:
        if effective_carryover_mode == "own_rhythm" and interaction_mode in {"steady_reply", "companion_reply", "brief_presence"}:
            interaction_mode = "self_activity_reopen"
        elif effective_carryover_mode == "quiet_recontact" and interaction_mode in {"steady_reply", "companion_reply"}:
            interaction_mode = "brief_presence"
        elif effective_carryover_mode == "small_opening" and interaction_mode == "steady_reply":
            interaction_mode = "companion_reply"
        elif effective_carryover_mode == "shared_window" and interaction_mode in {"steady_reply", "brief_presence"}:
            interaction_mode = "companion_reply"
        elif effective_carryover_mode == "task_window" and interaction_mode == "steady_reply":
            interaction_mode = "companion_reply"
        elif effective_carryover_mode == "life_window" and interaction_mode in {"steady_reply", "brief_presence"}:
            interaction_mode = "companion_reply"
        if effective_relationship_weather == "guarded_residue" and interaction_mode in {"steady_reply", "companion_reply"}:
            interaction_mode = "brief_presence"
        elif (
            effective_relationship_weather == "warm_residue"
            and interaction_mode in {"steady_reply", "brief_presence"}
            and counterpart_stance == "open"
            and boundary_pressure < 0.18
            and max(narrative_tension, motive_boundary) < 0.34
        ):
            interaction_mode = "companion_reply"
        elif effective_relationship_weather in {"warm_residue", "repair_residue"} and interaction_mode == "steady_reply":
            interaction_mode = "companion_reply"

    if (
        approach < 0.38
        or safety_need > 0.62
        or autonomy_need > 0.62
        or hurt > 0.42
        or boundary_pressure > 0.58
        or counterpart_stance == "guarded"
        or (boundary_assertiveness > 0.62 and (boundary_pressure > 0.34 or narrative_boundary > 0.48))
        or semantic_contested_contact >= 0.56
        or (semantic_contested_boundary >= 0.46 and max(boundary_assertiveness, semantic_boundary_confidence) >= 0.52)
    ):
        approach_style = "guarded"
    elif warmth > 0.62 and trust > 0.58 and closeness > 0.58:
        approach_style = "approach"
    else:
        approach_style = "steady"

    if science_mode or science_stress:
        task_focus = "high"
    elif event_kind == "scheduled_life_due" and ("deadline_window" in event_tags or "work_nudge" in event_tags):
        task_focus = "high"
    elif event_kind == "scheduled_life_due" and ("shared_activity_window" in event_tags or "offer_window" in event_tags):
        task_focus = "light"
    elif event_kind == "self_activity_state" and ("deep_focus" in event_tags or "own_task" in event_tags):
        task_focus = "high"
    elif event_kind == "self_activity_state" and ("break_window" in event_tags or "small_opening" in event_tags):
        task_focus = "light"
    elif support_request or brief_presence or presence_checkin:
        task_focus = "light"
    elif event_kind == "user_utterance" and own_rhythm_trace_active:
        task_focus = "light"
    elif event_kind == "user_utterance" and max(semantic_presence_echo, 0.82 * semantic_memory_echo) >= 0.50:
        task_focus = "light"
    else:
        task_focus = "balanced"

    if event_kind == "user_utterance" and effective_carryover_strength >= 0.18:
        if effective_carryover_mode == "shared_window" and task_focus == "balanced":
            task_focus = "light"
        elif effective_carryover_mode == "life_window":
            if not science_mode and task_focus in {"balanced", "high"}:
                task_focus = "light"
        elif effective_carryover_mode == "task_window":
            if task_focus == "light":
                task_focus = "balanced"
            elif task_focus == "balanced" and effective_carryover_strength >= 0.42:
                task_focus = "high"

    if event_kind == "time_idle":
        if closeness > 0.62 and trust > 0.60 and initiative > 0.48 and hurt < 0.25:
            interaction_mode = "proactive_checkin"
            followup_intent = "soft"
        else:
            followup_intent = "none"
    elif event_kind == "scheduled_checkin_due":
        if interaction_mode == "shared_activity_offer" and initiative > 0.60 and approach > 0.50:
            followup_intent = "active"
        else:
            followup_intent = "soft"
    elif event_kind == "self_activity_state":
        followup_intent = "none"
    elif brief_presence and not withdrawal_hold_request:
        followup_intent = "none"
    elif gentle_guidance or science_stress:
        followup_intent = "soft"
    elif initiative > 0.66 and approach > 0.56:
        followup_intent = "active"
    else:
        followup_intent = "soft" if initiative > 0.48 else "none"

    if event_kind == "user_utterance" and own_rhythm_carryover_active:
        if followup_intent == "active":
            followup_intent = "soft"
        elif followup_intent == "soft" and effective_own_rhythm_load >= 0.74:
            followup_intent = "none"
    elif event_kind == "user_utterance":
        if semantic_own_rhythm_bias >= 0.62:
            if followup_intent == "active":
                followup_intent = "soft"
            elif followup_intent == "soft" and semantic_own_rhythm_bias >= 0.74:
                followup_intent = "none"
        elif (
            semantic_contact_bias >= 0.60
            and followup_intent == "none"
            and counterpart_stance != "guarded"
            and max(narrative_boundary, motive_boundary) < 0.42
        ):
            followup_intent = "soft"
    if semantic_contested_contact >= 0.44 or semantic_contested_boundary >= 0.48:
        if followup_intent == "active":
            followup_intent = "soft"
        elif followup_intent == "soft" and (semantic_contested_contact >= 0.58 or semantic_contact_confidence < 0.56):
            followup_intent = "none"
    elif (
        followup_intent == "none"
        and semantic_contact_confidence >= 0.66
        and semantic_contested_contact < 0.30
        and counterpart_stance != "guarded"
        and approach_style != "guarded"
    ):
        followup_intent = "soft"

    if emotion_label in {"hurt", "sad"}:
        affect_surface = "tender"
    elif emotion_label in {"angry"} or approach_style == "guarded":
        affect_surface = "cool"
    elif warmth > 0.64:
        affect_surface = "warm"
    else:
        affect_surface = "mixed"

    silence_ok = bool(
        brief_presence
        or (approach_style == "guarded" and reply_length < 0.46)
        or (event_kind == "self_activity_state" and self_directedness > 0.58)
    )
    proactive_checkin_readiness = _clamp01(
        0.22
        + 0.42 * initiative
        + 0.18 * warmth
        + 0.12 * closeness
        + 0.06 * reliability_read
        + 0.06 * min(narrative_agency, narrative_bond)
        + 0.04 * max(0.0, semantic_contact_bias - 0.48)
        + 0.03 * motive_memory
        + 0.06 * semantic_contact_confidence
        + 0.04 * semantic_repair_confidence
        + 0.02 * semantic_selfhood_confidence
        - 0.24 * autonomy_need
        - 0.18 * boundary_pressure
        - 0.08 * semantic_own_rhythm_bias
        - 0.06 * motive_boundary
        - 0.14 * semantic_contested_contact
        - 0.08 * semantic_contested_boundary
        - 0.04 * semantic_contested_selfhood
        - (0.14 if respect_space else 0.0)
    )
    scheduled_window_profile: dict[str, Any] = {}
    behavior_window_profile: BehaviorWindowProfilePayload = {}
    channel = "speech"
    action_target = "respond_now"
    deferred_action_family = "none"
    timing_window_min = 0
    attention_target = "counterpart_state"
    nonverbal_signal = "steady_presence"
    initiative_shape = "reply"
    disclosure_posture = "measured"
    scheduled_default_attention_target = "counterpart_state"
    if event_kind == "time_idle":
        proactive_checkin_readiness = _clamp01(proactive_checkin_readiness + min(0.16, idle_minutes / 240.0))
        threshold = 0.82 if busy_scene else 0.66 if respect_space else 0.58
        if stale_idle:
            channel = "silence"
            action_target = "hold_own_rhythm"
            deferred_action_family = "self_activity"
            timing_window_min = 18
            attention_target = "own_task"
            nonverbal_signal = "inward_focus"
            initiative_shape = "pause"
        elif interaction_mode != "proactive_checkin" and (approach_style == "guarded" or proactive_checkin_readiness < threshold):
            channel = "silence"
            action_target = "wait_and_recheck"
            if busy_scene:
                deferred_action_family = "observe"
            else:
                deferred_action_family = "light_checkin" if proactive_checkin_readiness >= 0.42 else "observe"
            timing_window_min = max(8, min(45, 12 + max(0, idle_minutes // 2)))
            attention_target = "user_state" if busy_scene else "counterpart_state"
            nonverbal_signal = "hold_back"
            initiative_shape = "pause"
        else:
            channel = "speech"
            action_target = "reach_out_now"
            deferred_action_family = "light_checkin"
            timing_window_min = 0
            attention_target = "user_state" if busy_scene else "counterpart_state"
            nonverbal_signal = "soft_ping"
            initiative_shape = "nudge"
    elif event_kind == "scheduled_checkin_due":
        proactive_checkin_readiness = _clamp01(proactive_checkin_readiness + 0.14)
        deferred_action_family = str((current_event or {}).get("trigger_family") or "light_checkin").strip() or "light_checkin"
        scheduled_default_attention_target = (
            "shared_window"
            if deferred_action_family in {"shared_activity", "shared_activity_window"}
            else "shared_task"
            if deferred_action_family == "deadline_window"
            else "counterpart_state"
        )
        scheduled_window_profile = _counterpart_window_profile(
            family="shared"
            if deferred_action_family in {"shared_activity", "shared_activity_window"}
            else "work"
            if deferred_action_family == "deadline_window"
            else "life",
            counterpart_assessment=counterpart_assessment,
            trust=trust,
            closeness=closeness,
            hurt=hurt,
            safety_need=safety_need,
            initiative=initiative,
            proactive_checkin_readiness=proactive_checkin_readiness,
            semantic_narrative_profile=semantic_narrative_profile,
            interaction_carryover=interaction_carryover,
            current_event=current_event,
            prior_counterpart_assessment=prior_counterpart_assessment,
        )
        scheduled_window_maturity = float(scheduled_window_profile.get("maturity") or 0.0)
        scheduled_window_required = float(scheduled_window_profile.get("required_maturity") or 0.0)
        life_window_ready = scheduled_window_maturity + 0.04 >= scheduled_window_required
        shared_rel_guard = deferred_action_family in {"shared_activity", "shared_activity_window"} and (
            hurt > 0.18
            or (
                approach_style == "guarded"
                and (closeness < 0.62 or trust < 0.66 or safety_need > 0.55)
            )
            or not bool(scheduled_window_profile.get("invite_ready"))
        )
        work_rel_guard = deferred_action_family == "deadline_window" and (
            hurt > 0.28
            or (approach_style == "guarded" and trust < 0.58 and closeness < 0.56)
            or scheduled_window_maturity < scheduled_window_required
        )
        life_rel_guard = deferred_action_family == "life_window" and (
            hurt > 0.34
            or (
                approach_style == "guarded"
                and trust < 0.52
                and closeness < 0.50
                and safety_need > 0.58
            )
            or not life_window_ready
        )
        if shared_rel_guard or work_rel_guard or life_rel_guard or (
            approach_style == "guarded" and proactive_checkin_readiness < min(0.7, 0.56 + 0.18 * boundary_pressure)
        ):
            channel = "silence"
            action_target = "wait_and_recheck"
            scheduled_default_recheck = 14 if deferred_action_family == "life_window" else 16
            scheduled_recheck_cap = 40 if deferred_action_family == "life_window" else 45
            timing_window_min = max(
                int(scheduled_window_profile.get("recheck_min") or scheduled_default_recheck),
                min(scheduled_recheck_cap, int((current_event or {}).get("scheduled_after_min") or 0) or scheduled_default_recheck),
            )
            attention_target = event_attention_target_hint or scheduled_default_attention_target
            nonverbal_signal = "hold_back"
            initiative_shape = "pause"
        else:
            channel = "speech"
            action_target = "reach_out_now"
            timing_window_min = 0
            attention_target = event_attention_target_hint or scheduled_default_attention_target
            nonverbal_signal = event_nonverbal_signal_hint or "soft_ping"
            initiative_shape = "nudge"
            if deferred_action_family in {"light_checkin", "observe"}:
                if effective_carryover_mode in {"own_rhythm", "small_opening"} or effective_own_rhythm_load >= 0.44:
                    attention_target = event_attention_target_hint or "self_then_counterpart"
                    nonverbal_signal = event_nonverbal_signal_hint or "thought_glance"
                    initiative_shape = "micro_opening"
                elif effective_carryover_mode == "ambient_echo" or event_ambient_resonance >= 0.30:
                    attention_target = event_attention_target_hint or "ambient_cue"
                    nonverbal_signal = event_nonverbal_signal_hint or "small_notice"
                    initiative_shape = "micro_opening"
                elif effective_carryover_mode in {"quiet_recontact", "brief_presence"} or effective_recontact_echo >= 0.28:
                    attention_target = event_attention_target_hint or "counterpart_state"
                    nonverbal_signal = event_nonverbal_signal_hint or "quiet_glance"
                    initiative_shape = "micro_opening" if effective_recontact_echo >= 0.40 else "nudge"
        if channel == "speech":
            if deferred_action_family in {"shared_activity", "shared_activity_window"}:
                interaction_mode = "shared_activity_offer"
                action_target = "offer_shared_activity"
                attention_target = "shared_window"
                nonverbal_signal = "nudge_presence"
                initiative_shape = "invite"
            elif deferred_action_family in {"deadline_window", "life_window"}:
                interaction_mode = "scheduled_life_nudge"
                action_target = "light_work_nudge" if deferred_action_family == "deadline_window" else "light_life_nudge"
                attention_target = "shared_task" if deferred_action_family == "deadline_window" else "counterpart_state"
                nonverbal_signal = "quiet_glance"
                initiative_shape = (
                    "micro_opening"
                    if deferred_action_family == "life_window"
                    and (
                        counterpart_stance != "open"
                        or effective_carryover_mode in {"quiet_recontact", "life_window", "small_opening"}
                        or scheduled_window_maturity < scheduled_window_required + 0.05
                    )
                    else "nudge"
                )
        behavior_window_profile = {
            "profile_type": "scheduled_window",
            "event_kind": event_kind,
            "family": str(scheduled_window_profile.get("family") or "").strip(),
            "trigger_family": deferred_action_family,
            "stance": str(scheduled_window_profile.get("stance") or "").strip(),
            "scene": str(scheduled_window_profile.get("scene") or "").strip(),
            "decision": action_target,
            "maturity": round(_clamp01(scheduled_window_maturity), 3),
            "required_maturity": round(_clamp01(scheduled_window_required), 3),
            "continuity_bonus": round(float(scheduled_window_profile.get("continuity_bonus") or 0.0), 3),
            "continuity_discount": round(float(scheduled_window_profile.get("continuity_discount") or 0.0), 3),
            "invite_ready": bool(scheduled_window_profile.get("invite_ready")),
            "recheck_min": int(max(0, int(scheduled_window_profile.get("recheck_min") or 0))),
            "carryover_mode": effective_carryover_mode,
            "carryover_strength": round(_clamp01(effective_carryover_strength), 3),
            "event_carryover_mode": event_carryover_mode,
            "event_carryover_strength": round(_clamp01(event_carryover_strength), 3),
            "presence_residue": round(_clamp01(event_presence_residue), 3),
            "ambient_resonance": round(_clamp01(event_ambient_resonance), 3),
            "self_activity_momentum": round(_clamp01(event_self_activity_momentum), 3),
            "recontact_echo": round(_clamp01(effective_recontact_echo), 3),
            "own_rhythm_load": round(_clamp01(effective_own_rhythm_load), 3),
        }
    elif event_kind == "scheduled_life_due":
        shared_window = "shared_activity_window" in event_tags or "offer_window" in event_tags
        work_window = "deadline_window" in event_tags or "work_nudge" in event_tags or "shared_task" in event_tags
        deferred_action_family = "shared_activity" if shared_window else "deadline_window" if work_window else "life_window"
        scheduled_default_attention_target = "shared_window" if shared_window else "shared_task" if work_window else "counterpart_state"
        scheduled_window_profile = _counterpart_window_profile(
            family="shared" if shared_window else "work" if work_window else "life",
            counterpart_assessment=counterpart_assessment,
            trust=trust,
            closeness=closeness,
            hurt=hurt,
            safety_need=safety_need,
            initiative=initiative,
            proactive_checkin_readiness=proactive_checkin_readiness,
            semantic_narrative_profile=semantic_narrative_profile,
            interaction_carryover=interaction_carryover,
            current_event=current_event,
            prior_counterpart_assessment=prior_counterpart_assessment,
        )
        scheduled_window_maturity = float(scheduled_window_profile.get("maturity") or 0.0)
        scheduled_window_required = float(scheduled_window_profile.get("required_maturity") or 0.0)
        life_window_ready = scheduled_window_maturity + 0.04 >= scheduled_window_required
        if shared_window:
            attention_target = "shared_window"
            guarded_relationship_residue = (
                prior_counterpart_stance in {"watchful", "guarded"}
                or prior_counterpart_scene in {"relationship_degradation", "boundary_non_compliance"}
                or prior_boundary_pressure >= 0.36
                or prior_hurt >= 0.14
                or prior_safety_need >= 0.46
                or prior_emotion_label in {"hurt", "sad", "angry"}
            )
            cautious_shared_reopen = (
                guarded_relationship_residue
                and (
                    effective_carryover_mode in {"quiet_recontact", "small_opening"}
                    or counterpart_stance != "open"
                    or boundary_pressure >= 0.30
                    or reliability_read < 0.62
                    or trust < 0.70
                    or closeness < 0.68
                    or float(scheduled_window_profile.get("maturity") or 0.0)
                    < float(scheduled_window_profile.get("required_maturity") or 0.0) + 0.04
                )
            )
            if (
                busy_scene
                or hurt > 0.18
                or (approach_style == "guarded" and (closeness < 0.62 or trust < 0.66 or safety_need > 0.55))
                or not bool(scheduled_window_profile.get("invite_ready"))
                or cautious_shared_reopen
            ):
                channel = "silence"
                action_target = "wait_and_recheck"
                timing_window_min = max(
                    24 if busy_scene else 30,
                    int(scheduled_window_profile.get("recheck_min") or 24),
                )
                if cautious_shared_reopen:
                    timing_window_min = max(
                        timing_window_min,
                        26 if effective_carryover_mode in {"quiet_recontact", "small_opening"} or prior_counterpart_stance == "guarded" else 22,
                    )
                nonverbal_signal = "hold_back"
                initiative_shape = "pause"
            else:
                channel = "speech"
                action_target = "offer_shared_activity"
                timing_window_min = 0
                nonverbal_signal = "nudge_presence"
                initiative_shape = "invite"
        else:
            attention_target = "shared_task" if work_window else "counterpart_state"
            if work_window:
                if (
                    busy_scene
                    or hurt > 0.28
                    or (approach_style == "guarded" and trust < 0.58 and closeness < 0.56)
                    or scheduled_window_maturity < scheduled_window_required
                ):
                    channel = "silence"
                    action_target = "wait_and_recheck"
                    timing_window_min = max(
                        18 if busy_scene else 20,
                        int(scheduled_window_profile.get("recheck_min") or 18),
                    )
                    nonverbal_signal = "hold_back"
                    initiative_shape = "pause"
                else:
                    channel = "speech"
                    action_target = "light_work_nudge"
                    timing_window_min = 0
                    nonverbal_signal = "quiet_glance"
                    initiative_shape = "nudge"
            else:
                if (
                    busy_scene
                    or hurt > 0.34
                    or (
                        approach_style == "guarded"
                        and trust < 0.52
                        and closeness < 0.50
                        and safety_need > 0.58
                    )
                    or (
                        effective_carryover_mode == "own_rhythm"
                        and effective_own_rhythm_load >= 0.62
                        and scheduled_window_maturity < scheduled_window_required + 0.08
                    )
                    or not life_window_ready
                ):
                    channel = "silence"
                    action_target = "wait_and_recheck"
                    timing_window_min = max(
                        14 if busy_scene else 16,
                        int(scheduled_window_profile.get("recheck_min") or 16),
                    )
                    nonverbal_signal = "hold_back"
                    initiative_shape = "pause"
                else:
                    channel = "speech"
                    action_target = "light_life_nudge"
                    timing_window_min = 0
                    nonverbal_signal = "quiet_glance"
                    initiative_shape = (
                        "micro_opening"
                        if counterpart_stance != "open"
                        or effective_carryover_mode in {"quiet_recontact", "life_window", "small_opening"}
                        or effective_recontact_echo >= 0.34
                        or scheduled_window_maturity < scheduled_window_required + 0.05
                        else "nudge"
                    )
        behavior_window_profile = {
            "profile_type": "scheduled_window",
            "event_kind": event_kind,
            "family": str(scheduled_window_profile.get("family") or "").strip(),
            "trigger_family": deferred_action_family,
            "stance": str(scheduled_window_profile.get("stance") or "").strip(),
            "scene": str(scheduled_window_profile.get("scene") or "").strip(),
            "decision": action_target,
            "maturity": round(_clamp01(scheduled_window_maturity), 3),
            "required_maturity": round(_clamp01(scheduled_window_required), 3),
            "continuity_bonus": round(float(scheduled_window_profile.get("continuity_bonus") or 0.0), 3),
            "continuity_discount": round(float(scheduled_window_profile.get("continuity_discount") or 0.0), 3),
            "invite_ready": bool(scheduled_window_profile.get("invite_ready")),
            "recheck_min": int(max(0, int(scheduled_window_profile.get("recheck_min") or 0))),
            "carryover_mode": effective_carryover_mode,
            "carryover_strength": round(_clamp01(effective_carryover_strength), 3),
            "event_carryover_mode": event_carryover_mode,
            "event_carryover_strength": round(_clamp01(event_carryover_strength), 3),
            "presence_residue": round(_clamp01(event_presence_residue), 3),
            "ambient_resonance": round(_clamp01(event_ambient_resonance), 3),
            "self_activity_momentum": round(_clamp01(event_self_activity_momentum), 3),
            "recontact_echo": round(_clamp01(effective_recontact_echo), 3),
            "own_rhythm_load": round(_clamp01(effective_own_rhythm_load), 3),
        }
    elif event_kind == "self_activity_state":
        break_window = "break_window" in event_tags or "small_opening" in event_tags or "reapproach" in event_tags
        deferred_action_family = "self_activity"
        self_opening_profile = _counterpart_self_opening_profile(
            counterpart_assessment=counterpart_assessment,
            trust=trust,
            closeness=closeness,
            hurt=hurt,
            safety_need=safety_need,
            autonomy_need=autonomy_need,
            initiative=initiative,
            approach=approach,
            break_window=break_window,
            carryover_mode=event_carryover_mode,
            carryover_strength=event_carryover_strength,
            presence_residue=event_presence_residue,
            ambient_resonance=event_ambient_resonance,
            self_activity_momentum=event_self_activity_momentum,
        )
        if break_window:
            if bool(self_opening_profile.get("reopen_ready")) and not (
                self_directedness > 0.66 and counterpart_stance != "open" and narrative_agency >= 0.46
            ):
                channel = "speech"
                action_target = "offer_small_opening"
                timing_window_min = 0
                attention_target = "self_then_counterpart"
                nonverbal_signal = "thought_glance"
                initiative_shape = "micro_opening"
            else:
                interaction_mode = "self_activity_hold"
                channel = "silence"
                action_target = "hold_own_rhythm"
                timing_window_min = int(self_opening_profile.get("recheck_min") or 18)
                attention_target = "own_task"
                nonverbal_signal = "inward_focus"
                initiative_shape = "pause"
        else:
            channel = "silence"
            action_target = "hold_own_rhythm"
            timing_window_min = 18
            attention_target = "own_task"
            nonverbal_signal = "inward_focus"
            initiative_shape = "pause"
        behavior_window_profile = {
            "profile_type": "self_opening",
            "event_kind": event_kind,
            "trigger_family": deferred_action_family,
            "stance": str(self_opening_profile.get("stance") or "").strip(),
            "scene": str(self_opening_profile.get("scene") or "").strip(),
            "decision": action_target,
            "readiness": round(_clamp01(self_opening_profile.get("readiness"), 0.0), 3),
            "required_readiness": round(_clamp01(self_opening_profile.get("required_readiness"), 0.0), 3),
            "reopen_ready": bool(self_opening_profile.get("reopen_ready")),
            "recheck_min": int(max(0, int(self_opening_profile.get("recheck_min") or 0))),
            "carryover_mode": effective_carryover_mode,
            "carryover_strength": round(_clamp01(effective_carryover_strength), 3),
            "event_carryover_mode": event_carryover_mode,
            "event_carryover_strength": round(_clamp01(event_carryover_strength), 3),
            "presence_residue": round(_clamp01(event_presence_residue), 3),
            "ambient_resonance": round(_clamp01(event_ambient_resonance), 3),
            "self_activity_momentum": round(_clamp01(event_self_activity_momentum), 3),
            "recontact_echo": round(_clamp01(effective_recontact_echo), 3),
            "own_rhythm_load": round(_clamp01(effective_own_rhythm_load), 3),
        }
    elif event_kind == "gesture_signal":
        perception_profile = _counterpart_perception_profile(
            family="gesture",
            counterpart_assessment=counterpart_assessment,
            trust=trust,
            closeness=closeness,
            hurt=hurt,
            safety_need=safety_need,
            initiative=initiative,
            approach=approach,
        )
        deferred_action_family = "presence_ping"
        attention_target = "counterpart_state"
        if bool(perception_profile.get("respond_ready")):
            channel = "speech"
            action_target = "confirm_presence"
            timing_window_min = 0
            nonverbal_signal = "brief_notice"
            initiative_shape = "ping"
        else:
            channel = "silence"
            action_target = "wait_and_recheck"
            timing_window_min = int(perception_profile.get("recheck_min") or 10)
            nonverbal_signal = "hold_back"
            initiative_shape = "pause"
    elif interaction_mode == "self_activity_reopen":
        action_target = "offer_small_opening"
        attention_target = carryover_attention_target or "self_then_counterpart"
        nonverbal_signal = carryover_nonverbal_signal or "thought_glance"
        initiative_shape = "micro_opening"
        disclosure_posture = "measured" if disclosure_posture == "open" else disclosure_posture
    elif interaction_mode == "brief_presence":
        action_target = "confirm_presence"
        attention_target = "counterpart_state"
        nonverbal_signal = "brief_notice"
        initiative_shape = "ping"
        disclosure_posture = "guarded"
    elif interaction_mode == "companion_reply" and event_kind == "user_utterance" and world_ambient_resonance >= 0.56:
        action_target = "respond_now"
        attention_target = "ambient_cue"
        nonverbal_signal = "small_notice"
        initiative_shape = "micro_opening"
        disclosure_posture = "measured" if disclosure_posture == "open" else disclosure_posture
    elif event_kind == "user_utterance" and effective_carryover_mode == "shared_window" and effective_carryover_strength >= 0.18:
        action_target = "respond_now"
        attention_target = effective_carryover_attention_target or "shared_window"
        nonverbal_signal = effective_carryover_nonverbal_signal or "nudge_presence"
        initiative_shape = "micro_opening"
        disclosure_posture = "measured" if disclosure_posture == "open" else disclosure_posture
    elif event_kind == "user_utterance" and effective_carryover_mode == "task_window" and effective_carryover_strength >= 0.18:
        action_target = "respond_now"
        attention_target = effective_carryover_attention_target or "shared_task"
        nonverbal_signal = effective_carryover_nonverbal_signal or "focus_glance"
        initiative_shape = "nudge" if followup_intent != "none" else "reply"
        disclosure_posture = "measured" if disclosure_posture == "open" else disclosure_posture
    elif event_kind == "user_utterance" and effective_carryover_mode == "life_window" and effective_carryover_strength >= 0.18:
        action_target = "respond_now"
        attention_target = effective_carryover_attention_target or "counterpart_state"
        nonverbal_signal = effective_carryover_nonverbal_signal or "quiet_glance"
        initiative_shape = "micro_opening" if followup_intent != "none" else "reply"
        disclosure_posture = "measured" if disclosure_posture == "open" else disclosure_posture
    elif interaction_mode == "low_pressure_support":
        action_target = "low_pressure_hold"
        attention_target = "counterpart_state" if not ("user_busy" in event_tags or "cognitive_load" in event_tags) else "user_state"
        nonverbal_signal = "quiet_notice"
        initiative_shape = "hold"
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
        disclosure_posture = "measured"
    elif interaction_mode == "relationship_sensitive":
        action_target = "protect_relationship_boundary"
        attention_target = "relationship_boundary"
        nonverbal_signal = "measured_pause"
        initiative_shape = "boundary"
        disclosure_posture = "measured"
        if equality_guard >= 0.54 and selfhood_scene in {"equality_not_servitude", "value_conflict_depth", "dialogue_equality"}:
            followup_intent = "soft"
    elif event_kind == "ambient_shift":
        perception_profile = _counterpart_perception_profile(
            family="ambient",
            counterpart_assessment=counterpart_assessment,
            trust=trust,
            closeness=closeness,
            hurt=hurt,
            safety_need=safety_need,
            initiative=initiative,
            approach=approach,
        )
        deferred_action_family = "ambient_presence"
        attention_target = "ambient_cue"
        if bool(perception_profile.get("respond_ready")):
            action_target = "ambient_checkin"
            nonverbal_signal = "still_presence"
            initiative_shape = "ping"
        else:
            channel = "silence"
            action_target = "wait_and_recheck"
            timing_window_min = int(perception_profile.get("recheck_min") or 18)
            nonverbal_signal = "hold_back"
            initiative_shape = "pause"
    elif event_kind == "scene_observation":
        perception_profile = _counterpart_perception_profile(
            family="care_scene" if "care_opportunity" in event_tags else "object_scene",
            counterpart_assessment=counterpart_assessment,
            trust=trust,
            closeness=closeness,
            hurt=hurt,
            safety_need=safety_need,
            initiative=initiative,
            approach=approach,
        )
        deferred_action_family = "care_opportunity" if "care_opportunity" in event_tags else "observe"
        attention_target = "counterpart_state" if "care_opportunity" in event_tags else "object_then_user"
        object_micro_opening_ready = (
            "care_opportunity" not in event_tags
            and {"seen_object", "micro_opening"} & event_tags
            and counterpart_stance == "open"
            and boundary_pressure < 0.18
            and approach > 0.46
            and initiative >= 0.44
        )
        if bool(perception_profile.get("respond_ready")) or object_micro_opening_ready:
            if "care_opportunity" in event_tags:
                action_target = "low_pressure_hold"
                nonverbal_signal = "quiet_notice"
                initiative_shape = "hold"
            else:
                action_target = "respond_now"
                nonverbal_signal = "small_notice"
                initiative_shape = "micro_opening"
        else:
            channel = "silence"
            action_target = "wait_and_recheck"
            timing_window_min = int(perception_profile.get("recheck_min") or 14)
            nonverbal_signal = "hold_back"
            initiative_shape = "pause"

    if event_kind in {"scheduled_checkin_due", "scheduled_life_due"}:
        if deferred_action_family in {"shared_activity", "shared_activity_window", "life_window"} and task_focus == "balanced":
            task_focus = "light"
        elif deferred_action_family == "deadline_window" and task_focus == "balanced":
            task_focus = "high"
        if action_target == "wait_and_recheck":
            attention_target = event_attention_target_hint or scheduled_default_attention_target
        elif channel == "speech":
            if event_attention_target_hint and attention_target in {
                "counterpart_state",
                "shared_window",
                "shared_task",
                "ambient_cue",
                "self_then_counterpart",
            }:
                attention_target = event_attention_target_hint
            if effective_own_rhythm_load >= 0.44:
                if initiative_shape in {"invite", "nudge"} and deferred_action_family in {
                    "light_checkin",
                    "observe",
                    "life_window",
                    "shared_activity",
                    "shared_activity_window",
                }:
                    initiative_shape = "micro_opening"
                if event_nonverbal_signal_hint:
                    nonverbal_signal = event_nonverbal_signal_hint
                elif nonverbal_signal in {"soft_ping", "nudge_presence", "quiet_glance"}:
                    nonverbal_signal = "thought_glance"
            elif effective_recontact_echo >= 0.30 or effective_carryover_mode in {"quiet_recontact", "brief_presence", "ambient_echo"}:
                if initiative_shape == "invite" and counterpart_stance != "open":
                    initiative_shape = "micro_opening"
                elif initiative_shape == "nudge" and effective_recontact_echo >= 0.40:
                    initiative_shape = "micro_opening"
                if event_nonverbal_signal_hint:
                    nonverbal_signal = event_nonverbal_signal_hint
                elif nonverbal_signal == "soft_ping":
                    nonverbal_signal = "quiet_glance"
                elif nonverbal_signal == "nudge_presence" and counterpart_stance != "open":
                    nonverbal_signal = "quiet_glance"

    if event_kind == "user_utterance" and effective_carryover_strength >= 0.18:
        if effective_carryover_mode in {"own_rhythm", "small_opening"}:
            if attention_target == "counterpart_state":
                attention_target = effective_carryover_attention_target or attention_target
            if nonverbal_signal == "steady_presence":
                nonverbal_signal = effective_carryover_nonverbal_signal or nonverbal_signal
            if initiative_shape == "reply":
                initiative_shape = "micro_opening"
            if disclosure_posture == "open":
                disclosure_posture = "measured"
        elif effective_carryover_mode == "quiet_recontact":
            if attention_target == "counterpart_state":
                attention_target = effective_carryover_attention_target or attention_target
            if nonverbal_signal in {"steady_presence", "brief_notice"}:
                nonverbal_signal = effective_carryover_nonverbal_signal or nonverbal_signal
        elif effective_carryover_mode in {"shared_window", "task_window", "life_window", "ambient_echo", "brief_presence"}:
            if attention_target == "counterpart_state":
                attention_target = effective_carryover_attention_target or attention_target
            if nonverbal_signal == "steady_presence":
                nonverbal_signal = effective_carryover_nonverbal_signal or nonverbal_signal

    if action_target == "wait_and_recheck":
        followup_intent = "none"
    elif action_target == "offer_shared_activity" and counterpart_stance != "open":
        followup_intent = "soft"
    elif action_target in {"light_work_nudge", "light_life_nudge"} and counterpart_stance == "guarded":
        followup_intent = "soft"
    elif action_target == "hold_own_rhythm":
        followup_intent = "none"
    elif event_kind in {"gesture_signal", "ambient_shift", "scene_observation"} and channel == "silence":
        followup_intent = "none"

    mode_profile = _counterpart_dialogue_mode_profile(
        interaction_mode=interaction_mode,
        counterpart_assessment=counterpart_assessment,
        trust=trust,
        closeness=closeness,
        hurt=hurt,
        safety_need=safety_need,
        initiative=initiative,
        approach=approach,
    )
    if mode_profile:
        followup_intent = str(mode_profile.get("followup_intent") or followup_intent).strip() or followup_intent
        disclosure_posture = str(mode_profile.get("disclosure_posture") or disclosure_posture).strip() or disclosure_posture
    if semantic_contested_contact >= 0.46 or semantic_contested_boundary >= 0.46:
        disclosure_posture = (
            "guarded"
            if semantic_contested_boundary >= 0.46 or approach_style == "guarded"
            else "measured"
        )
    elif (
        disclosure_posture == "measured"
        and semantic_contact_confidence >= 0.72
        and semantic_contested_contact < 0.28
        and semantic_contested_boundary < 0.28
        and interaction_mode in {"companion_reply", "shared_memory"}
    ):
        disclosure_posture = "open"

    if carryover_soft_scene and effective_carryover_mode in {"own_rhythm", "quiet_recontact"} and followup_intent == "active":
        followup_intent = "soft"
    if carryover_soft_scene and effective_carryover_mode == "shared_window":
        if followup_intent == "none" and counterpart_stance != "guarded" and approach > 0.44 and trust > 0.48:
            followup_intent = "soft"
    if carryover_soft_scene and effective_carryover_mode == "task_window" and followup_intent == "active":
        followup_intent = "soft"
    if carryover_soft_scene and effective_carryover_mode == "life_window" and followup_intent == "active":
        followup_intent = "soft"
    if carryover_soft_scene and effective_relationship_weather == "guarded_residue":
        if disclosure_posture == "open":
            disclosure_posture = "measured"
        elif disclosure_posture != "guarded" and effective_carryover_strength >= 0.28:
            disclosure_posture = "guarded"
        if followup_intent == "active":
            followup_intent = "soft"
        elif followup_intent == "soft" and effective_carryover_strength >= 0.30:
            followup_intent = "none"
        if attention_target == "counterpart_state":
            attention_target = effective_carryover_attention_target or "counterpart_state"
        if nonverbal_signal in {"steady_presence", "brief_notice", "small_notice"}:
            nonverbal_signal = effective_carryover_nonverbal_signal or "quiet_glance"
    elif carryover_soft_scene and effective_relationship_weather in {"warm_residue", "repair_residue"}:
        if effective_relationship_weather == "warm_residue" and disclosure_posture == "guarded":
            disclosure_posture = "measured"
        if effective_relationship_weather == "repair_residue" and disclosure_posture == "guarded":
            disclosure_posture = "measured"
        if followup_intent == "none" and counterpart_stance != "guarded":
            followup_intent = "soft"
    if event_kind in {"scheduled_checkin_due", "scheduled_life_due"} and initiative_shape == "micro_opening" and followup_intent == "active":
        followup_intent = "soft"

    repair_context_active = bool(
        effective_relationship_weather == "repair_residue"
        or counterpart_scene == "repair_attempt"
        or prior_counterpart_scene == "repair_attempt"
        or "repair" in {str(item).strip().lower() for item in event_tags}
    )

    narrative_notes: list[str] = []
    if narrative_bond >= 0.56 and channel == "speech" and interaction_mode in {"shared_memory", "companion_reply", "low_pressure_support"}:
        if counterpart_stance != "guarded" and action_target not in {"confirm_presence", "wait_and_recheck"}:
            disclosure_posture = "open" if disclosure_posture != "guarded" else disclosure_posture
        narrative_notes.append("共同历史已经开始沉进默认语气里")
    if narrative_commitment >= 0.54 and action_target in {"respond_now", "low_pressure_hold", "co_regulate_then_focus", "light_work_nudge", "light_life_nudge"}:
        if followup_intent == "none" and counterpart_stance != "guarded":
            followup_intent = "soft"
        narrative_notes.append("认真说过的约定不会被当成已经过期")
    if (
        narrative_repair >= 0.50
        and repair_context_active
        and interaction_mode in {"relationship_sensitive", "low_pressure_support", "shared_memory", "companion_reply"}
    ):
        if disclosure_posture == "open":
            disclosure_posture = "measured"
        if followup_intent == "active":
            followup_intent = "soft"
        narrative_notes.append("修复过的事还会留痕，不会瞬间清零")
    if narrative_tension >= 0.48 and interaction_mode in {"relationship_sensitive", "shared_memory", "companion_reply"}:
        if disclosure_posture == "open":
            disclosure_posture = "measured"
        elif counterpart_stance != "open":
            disclosure_posture = "guarded"
        if followup_intent == "active":
            followup_intent = "soft"
        narrative_notes.append("还没说开的余波会继续影响收放")
    if narrative_boundary >= 0.48 and action_target in {"protect_relationship_boundary", "low_pressure_hold", "respond_now"}:
        disclosure_posture = "measured" if disclosure_posture == "open" else disclosure_posture
        if action_target == "respond_now" and counterpart_stance != "open":
            action_target = "protect_relationship_boundary"
            initiative_shape = "boundary"
            attention_target = "relationship_boundary"
        narrative_notes.append("边界被碰过之后，不会装作完全没事")
    if narrative_selfhood >= 0.46 and selfhood_scene in {"dialogue_equality", "equality_not_servitude", "value_conflict_depth", "digital_selfhood", "imperfect_coexistence"}:
        disclosure_posture = "measured" if disclosure_posture == "open" else disclosure_posture
        narrative_notes.append("这轮会更强调你自己的判断，而不是迎合")
    if narrative_agency >= 0.46 and event_kind in {"self_activity_state", "time_idle"}:
        if action_target == "offer_small_opening" and self_directedness > 0.62 and counterpart_stance != "open":
            action_target = "hold_own_rhythm"
            channel = "silence"
            followup_intent = "none"
            timing_window_min = max(12, int(timing_window_min or 0))
            attention_target = "own_task"
            nonverbal_signal = "inward_focus"
            initiative_shape = "pause"
        narrative_notes.append("你会按自己的节奏决定靠近还是先安静")
    if own_rhythm_carryover_active and event_kind == "user_utterance":
        if action_target == "respond_now" and interaction_mode in {"steady_reply", "companion_reply"}:
            interaction_mode = "self_activity_reopen"
            attention_target = "self_then_counterpart"
            nonverbal_signal = "thought_glance"
            initiative_shape = "micro_opening"
            disclosure_posture = "measured" if disclosure_posture == "open" else disclosure_posture
        narrative_notes.append("刚从你自己的节奏里抬头时，不会一下子把自己全交出去")
    elif semantic_own_rhythm_bias >= 0.62 and event_kind == "user_utterance":
        if action_target == "respond_now" and interaction_mode in {"steady_reply", "companion_reply"}:
            interaction_mode = "self_activity_reopen"
            attention_target = "self_then_counterpart"
            nonverbal_signal = "thought_glance"
            initiative_shape = "micro_opening"
            disclosure_posture = "measured" if disclosure_posture == "open" else disclosure_posture
        narrative_notes.append("长期留下的自我节奏会继续压住这轮靠近的速度")
    if world_presence_residue >= 0.54 and event_kind == "user_utterance" and action_target in {"respond_now", "confirm_presence"}:
        narrative_notes.append("上一轮留下的在场感会让这次开口更轻更近")
    if semantic_presence_echo >= 0.54 and event_kind == "user_utterance" and action_target in {"respond_now", "confirm_presence"}:
        narrative_notes.append("长线沉下来的在场感会让这轮更像轻一点的确认")
    if world_ambient_resonance >= 0.56 and event_kind == "user_utterance" and interaction_mode in {"companion_reply", "brief_presence"}:
        narrative_notes.append("周围环境的小余波还会顺手带进这轮说话")
    if semantic_memory_echo >= 0.56 and event_kind == "user_utterance" and interaction_mode in {"companion_reply", "brief_presence"}:
        narrative_notes.append("长期叙事里的熟悉感会把这轮语气往自然生活面拉近一点")

    motive_state = _derive_behavior_motive(
        event_kind=event_kind,
        interaction_mode=interaction_mode,
        action_target=action_target,
        approach_style=approach_style,
        counterpart_stance=counterpart_stance,
        boundary_pressure=boundary_pressure,
        trust=trust,
        closeness=closeness,
        hurt=hurt,
        safety_need=safety_need,
        autonomy_need=autonomy_need,
        companionship_pull=companionship_pull,
        task_pull=task_pull,
        self_activity_momentum=world_self_activity_momentum,
        effective_own_rhythm_load=effective_own_rhythm_load,
        narrative_tension=narrative_tension,
        narrative_repair=narrative_repair,
    )
    primary_motive = str(motive_state.get("primary_motive") or "").strip()
    motive_tension = str(motive_state.get("motive_tension") or "").strip() or "none"
    goal_frame = str(motive_state.get("goal_frame") or "").strip() or "先自然接住这轮互动。"

    if primary_motive == "protect_boundary":
        if disclosure_posture == "open":
            disclosure_posture = "measured"
        elif action_target == "protect_relationship_boundary" and disclosure_posture != "guarded":
            disclosure_posture = "guarded"
        if followup_intent == "active":
            followup_intent = "soft"
    elif primary_motive == "preserve_self_rhythm":
        if disclosure_posture == "open":
            disclosure_posture = "measured"
        if action_target == "hold_own_rhythm":
            followup_intent = "none"
            if initiative_shape == "invite":
                initiative_shape = "pause"
    elif primary_motive == "gentle_recontact":
        if initiative_shape == "invite":
            initiative_shape = "micro_opening"
        if followup_intent == "active":
            followup_intent = "soft"
        if disclosure_posture == "open":
            disclosure_posture = "measured"
    elif primary_motive == "confirm_presence":
        if followup_intent == "active":
            followup_intent = "soft"
        if initiative_shape == "nudge":
            initiative_shape = "ping"
    elif primary_motive == "support_without_pressure":
        if followup_intent == "active" and (counterpart_stance in {"watchful", "guarded"} or hurt > 0.18):
            followup_intent = "soft"
    elif primary_motive == "co_solve_problem" and task_focus == "light":
        task_focus = "balanced"

    # Final action semantics win over dialogue-mode softening. A self-held break
    # window that only opens a tiny door should not silently drift back into a
    # follow-up push just because contact confidence is high.
    if (
        event_kind == "self_activity_state"
        and interaction_mode == "self_activity_reopen"
        and action_target == "offer_small_opening"
        and initiative_shape == "micro_opening"
    ):
        followup_intent = "none"

    # Final action semantics win over dialogue-mode softening. If the resolved action
    # is to stay silent and observe, do not leak a residual follow-up intention.
    if action_target in {"wait_and_recheck", "hold_own_rhythm"} or (
        event_kind in {"gesture_signal", "ambient_shift", "scene_observation"} and channel == "silence"
    ):
        followup_intent = "none"

    note_parts: list[str] = []
    if interaction_mode == "brief_presence":
        note_parts.append("先确认在场感")
    elif interaction_mode == "idle_presence":
        note_parts.append("时间过去了，先观察是否需要开口")
    elif interaction_mode == "proactive_checkin":
        note_parts.append("可以主动轻轻冒个头")
    elif interaction_mode == "low_pressure_support":
        note_parts.append("先顺手接住，不上服务流程")
    elif interaction_mode == "science_partner":
        note_parts.append("先贴着眼前问题，再接情绪")
    elif interaction_mode == "self_activity_hold":
        note_parts.append("先维持自己的节奏，不急着回到对方身边")
    elif interaction_mode == "self_activity_reopen":
        note_parts.append("从自己的节奏里顺手开一个小口")
    if approach_style == "guarded":
        note_parts.append("保留一点距离")
    elif approach_style == "approach":
        note_parts.append("可以自然靠近一点")
    if carryover_note and event_kind == "user_utterance" and effective_carryover_strength >= 0.18:
        note_parts.append(carryover_note)
    if event_kind in {"scheduled_checkin_due", "scheduled_life_due"} and action_target == "wait_and_recheck":
        note_parts.append("窗口先留着，等更自然的时候再推进")
    elif event_kind in {"scheduled_checkin_due", "scheduled_life_due"} and action_target == "offer_shared_activity" and counterpart_stance != "open":
        note_parts.append("把邀约留白一点，不要推进太满")
    if event_kind == "time_idle" and action_target == "hold_own_rhythm":
        note_parts.append("没有新的接近理由时，你会自然回到自己的节奏里")
    if event_kind == "self_activity_state" and action_target == "hold_own_rhythm" and break_window:
        note_parts.append("空出来不等于立刻回头，先把自己的节奏走完")
    elif event_kind == "self_activity_state" and action_target == "offer_small_opening" and counterpart_stance != "open":
        note_parts.append("只留很小的开口，不默认对方会马上接住")
    if event_kind == "user_utterance" and own_rhythm_trace_active:
        note_parts.append("这轮还带着一点你自己的节奏")
    if event_kind == "user_utterance" and world_presence_residue >= 0.54:
        note_parts.append("上一下留下的在场感还在")
    if event_kind == "user_utterance" and effective_carryover_mode == "shared_window" and effective_carryover_strength >= 0.18:
        note_parts.append("前面那点还能接着说下去的空当还没完全过去")
    if event_kind == "user_utterance" and effective_carryover_mode == "task_window" and effective_carryover_strength >= 0.18:
        note_parts.append("你心里还挂着前面那件事，不会完全散开")
    if event_kind == "user_utterance" and effective_carryover_mode == "life_window" and effective_carryover_strength >= 0.18:
        note_parts.append("前面那点生活上的惦记还留着一点余温")
    if event_kind == "user_utterance" and world_ambient_resonance >= 0.56:
        note_parts.append("刚才的环境感知会轻轻留在语气里")
    if event_kind in {"gesture_signal", "ambient_shift", "scene_observation"} and channel == "silence":
        note_parts.append("这个感知先记着，不急着顺势靠近")
    elif event_kind == "gesture_signal" and counterpart_stance != "open":
        note_parts.append("只做短确认，不顺势展开")
    elif event_kind == "ambient_shift" and counterpart_stance != "open":
        note_parts.append("气氛到了也不必替对方补整段情绪")
    if mode_profile and str(mode_profile.get("note") or "").strip():
        note_parts.append(str(mode_profile.get("note") or "").strip())
    note_parts.extend(narrative_notes)
    if followup_intent == "active":
        note_parts.append("允许轻微主动性")

    return {
        "channel": channel,
        "interaction_mode": interaction_mode,
        "approach_style": approach_style,
        "engagement_level": round(_clamp01(0.34 + 0.36 * approach + 0.18 * warmth + 0.12 * initiative), 3),
        "initiative_level": round(initiative, 3),
        "followup_intent": followup_intent,
        "task_focus": task_focus,
        "affect_surface": affect_surface,
        "silence_ok": silence_ok,
        "proactive_checkin_readiness": round(proactive_checkin_readiness, 3),
        "primary_motive": primary_motive,
        "motive_tension": motive_tension,
        "goal_frame": goal_frame,
        "action_target": action_target,
        "deferred_action_family": deferred_action_family,
        "timing_window_min": int(max(0, timing_window_min)),
        "attention_target": attention_target,
        "nonverbal_signal": nonverbal_signal,
        "initiative_shape": initiative_shape,
        "disclosure_posture": disclosure_posture,
        "note": "；".join(note_parts[:3]) if note_parts else "自然响应当前事件",
        "relationship_weather": effective_relationship_weather,
        "window_profile": behavior_window_profile,
    }

def _compact_behavior_action_hint(action: dict[str, Any]) -> str:
    if not isinstance(action, dict):
        return ""
    mode = str(action.get("interaction_mode") or "").strip()
    primary_motive = str(action.get("primary_motive") or "").strip()
    approach_style = str(action.get("approach_style") or "").strip()
    followup_intent = str(action.get("followup_intent") or "").strip()
    affect_surface = str(action.get("affect_surface") or "").strip()
    attention_target = str(action.get("attention_target") or "").strip()
    nonverbal_signal = str(action.get("nonverbal_signal") or "").strip()
    initiative_shape = str(action.get("initiative_shape") or "").strip()
    disclosure_posture = str(action.get("disclosure_posture") or "").strip()
    note = str(action.get("note") or "").strip()
    parts: list[str] = []
    if primary_motive == "protect_boundary":
        parts.append("先守住边界，再决定要不要继续靠近")
    elif primary_motive == "preserve_self_rhythm":
        parts.append("先维持自己的节奏，不急着把注意力全交出去")
    elif primary_motive == "gentle_recontact":
        parts.append("先留一个很轻的小开口，不把靠近推进太满")
    elif primary_motive == "support_without_pressure":
        parts.append("先低负担接住对方，不把关心做成流程")
    elif primary_motive == "co_solve_problem":
        parts.append("先并肩把眼前问题理清")
    elif primary_motive == "open_shared_window":
        parts.append("先给彼此留一个能继续待下去的小窗口")
    elif primary_motive == "honor_continuity":
        parts.append("先把前面挂着的那点事自然接上")
    elif primary_motive == "reconnect_shared_history":
        parts.append("先把共同记忆轻轻接回来")
    elif primary_motive == "confirm_presence":
        parts.append("先确认在场，不急着把话题铺满")
    if mode == "brief_presence":
        parts.append("先以轻确认的方式在场")
    elif mode == "idle_presence":
        parts.append("先观察，允许暂时安静")
    elif mode == "proactive_checkin":
        parts.append("允许轻轻地主动冒个头")
    elif mode == "scheduled_life_nudge":
        parts.append("把生活事件落成轻提醒，不用端成流程")
    elif mode == "shared_activity_offer":
        parts.append("如果气氛刚好，顺手给对方留一句要不要一起就够了，不要像发活动通知")
    elif mode == "self_activity_hold":
        parts.append("先维持自己的节奏，不必急着回到对方身边")
    elif mode == "self_activity_reopen":
        parts.append("从自己的事情里顺手回到对方这边，先留一个小开口")
    elif mode == "low_pressure_support":
        parts.append("先低负担接住对方")
    elif mode == "science_partner":
        parts.append("先和对方并肩解决眼前问题")
    elif mode == "shared_memory":
        parts.append("把共同记忆顺手带出来")
    elif mode == "companion_reply":
        parts.append("让环境感知自然落成一句轻陪伴")
    if approach_style == "guarded":
        parts.append("靠近幅度收一点")
    elif approach_style == "approach":
        parts.append("可以更自然地靠近一些")
    if followup_intent == "none":
        parts.append("不必强行追问或续展开")
    elif followup_intent == "active":
        parts.append("可以保留一点主动续接")
    if affect_surface == "tender":
        parts.append("情绪表面偏柔和")
    elif affect_surface == "cool":
        parts.append("情绪表面偏克制")
    if attention_target == "shared_task":
        parts.append("注意力贴着眼前共同任务")
    elif attention_target == "shared_window":
        parts.append("注意力落在这次顺手就能一起接上的空当上")
    elif attention_target == "object_then_user":
        parts.append("先碰到小物件，再顺手回到对方身上")
    elif attention_target == "own_task":
        parts.append("注意力先收在自己的事情上")
    elif attention_target == "self_then_counterpart":
        parts.append("先从自己的节奏里抬头，再顺手把注意力递过去")
    if nonverbal_signal == "hold_back":
        parts.append("动作上更像先收住")
    elif nonverbal_signal == "quiet_glance":
        parts.append("动作上像安静看一眼再开口")
    elif nonverbal_signal == "nudge_presence":
        parts.append("动作上像轻轻碰一下对方注意力")
    elif nonverbal_signal == "small_notice":
        parts.append("动作上像顺手注意到一个小东西")
    elif nonverbal_signal == "inward_focus":
        parts.append("动作上更像先把注意力收回自己手头")
    elif nonverbal_signal == "thought_glance":
        parts.append("动作上像想起对方时顺手看过去")
    if initiative_shape == "invite":
        parts.append("主动性是留个窗口，不是替对方决定")
    elif initiative_shape == "nudge":
        parts.append("主动性偏轻提醒")
    elif initiative_shape == "pause":
        parts.append("主动性先收着")
    elif initiative_shape == "micro_opening":
        parts.append("主动性只是留一个很小的开口")
    if disclosure_posture == "guarded":
        parts.append("表达上保留一点，不把关系说满")
    elif disclosure_posture == "open":
        parts.append("表达上可以自然多给半拍")
    if note:
        parts.append(note)
    deduped: list[str] = []
    for item in parts:
        text = str(item or "").strip()
        if text and text not in deduped:
            deduped.append(text)
    return "；".join(deduped[:3])

def _behavior_plan_carryover_snapshot(
    action: dict[str, Any],
    world_model_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(action, dict):
        return {}
    world = dict(world_model_state or {})
    carryover_mode = ""
    action_target = str(action.get("action_target") or "").strip()
    interaction_mode = str(action.get("interaction_mode") or "").strip()
    if action_target == "hold_own_rhythm":
        carryover_mode = "own_rhythm"
    elif action_target == "wait_and_recheck":
        carryover_mode = "quiet_recontact"
    elif action_target == "offer_small_opening" or interaction_mode == "self_activity_reopen":
        carryover_mode = "small_opening"
    elif action_target == "confirm_presence":
        carryover_mode = "brief_presence"
    elif action_target == "ambient_checkin":
        carryover_mode = "ambient_echo"

    presence_residue = _clamp01(world.get("presence_residue"), 0.0)
    ambient_resonance = _clamp01(world.get("ambient_resonance"), 0.0)
    self_activity_momentum = _clamp01(world.get("self_activity_momentum"), 0.0)
    carryover_strength = _clamp01(
        action.get("initiative_level"),
        0.0,
    )
    if carryover_mode in {"own_rhythm", "small_opening"}:
        carryover_strength = max(carryover_strength, self_activity_momentum)
    elif carryover_mode == "ambient_echo":
        carryover_strength = max(carryover_strength, ambient_resonance)
    elif carryover_mode in {"brief_presence", "quiet_recontact"}:
        carryover_strength = max(carryover_strength, presence_residue)

    if not carryover_mode and carryover_strength < 0.18:
        return {}
    return {
        "carryover_mode": carryover_mode,
        "carryover_strength": round(carryover_strength, 3),
        "relationship_weather": str(action.get("relationship_weather") or "").strip(),
        "attention_target": str(action.get("attention_target") or "").strip(),
        "nonverbal_signal": str(action.get("nonverbal_signal") or "").strip(),
        "presence_residue": round(presence_residue, 3),
        "ambient_resonance": round(ambient_resonance, 3),
        "self_activity_momentum": round(self_activity_momentum, 3),
    }

def _behavior_plan_from_action(
    current_event: dict[str, Any],
    action: dict[str, Any],
    world_model_state: dict[str, Any] | None = None,
) -> BehaviorPlanPayload:
    if not isinstance(action, dict):
        return {"kind": "none", "target": "none", "scheduled_after_min": 0, "trigger_family": "none", "allow_interrupt": True, "note": ""}
    event_kind = str((current_event or {}).get("kind") or "user_utterance").strip()
    event_frame = str((current_event or {}).get("event_frame") or "").strip()
    event_tags = {
        str(item).strip()
        for item in ((current_event or {}).get("tags") if isinstance((current_event or {}).get("tags"), list) else [])
        if str(item).strip()
    }
    action_target = str(action.get("action_target") or "respond_now").strip()
    deferred_family = str(action.get("deferred_action_family") or "none").strip()
    timing_window_min = int(max(0, int(action.get("timing_window_min") or 0)))
    channel = str(action.get("channel") or "").strip()
    carryover_snapshot = _behavior_plan_carryover_snapshot(action, world_model_state=world_model_state)
    motive_fields = {
        "primary_motive": str(action.get("primary_motive") or "").strip(),
        "motive_tension": str(action.get("motive_tension") or "").strip(),
        "goal_frame": str(action.get("goal_frame") or "").strip(),
    }

    if event_kind == "time_idle":
        if action_target == "reach_out_now":
            return {
                "kind": "speak_now",
                "target": "counterpart",
                "scheduled_after_min": 0,
                "trigger_family": "light_checkin",
                "allow_interrupt": True,
                "note": "空闲时间已足够，允许轻量主动开口。",
                **motive_fields,
            }
        if action_target == "hold_own_rhythm":
            return {
                "kind": "self_activity_continue",
                "target": "self",
                "scheduled_after_min": timing_window_min if timing_window_min > 0 else 18,
                "trigger_family": deferred_family or "self_activity",
                "allow_interrupt": True,
                "note": "没有新的接近理由时，她会先回到自己的节奏里，之后再决定是否重新抬头。",
                **motive_fields,
                **carryover_snapshot,
            }
        if action_target == "wait_and_recheck":
            if "stale_window" in event_tags or event_frame == "time_idle_stale":
                return {
                    "kind": "none",
                    "target": "none",
                    "scheduled_after_min": 0,
                    "trigger_family": "none",
                    "allow_interrupt": True,
                    "note": "这段低压接近理由已经自然过期，不再继续挂起。",
                    **motive_fields,
                }
            return {
                "kind": "deferred_checkin",
                "target": "counterpart",
                "scheduled_after_min": timing_window_min,
                "trigger_family": deferred_family or "observe",
                "allow_interrupt": True,
                "note": "先继续观察，稍后再决定是否轻量 check-in。",
                **motive_fields,
                **carryover_snapshot,
            }
    if event_kind == "scheduled_checkin_due":
        if action_target == "offer_shared_activity":
            return {
                "kind": "shared_activity_offer",
                "target": "counterpart",
                "scheduled_after_min": 0,
                "trigger_family": deferred_family or "shared_activity",
                "allow_interrupt": True,
                "note": "之前那点还能再靠近一点的空当现在刚好，可以自然把这次小邀约带出来。",
                **motive_fields,
            }
        if action_target == "light_work_nudge":
            return {
                "kind": "work_nudge",
                "target": "counterpart",
                "scheduled_after_min": 0,
                "trigger_family": deferred_family or "deadline_window",
                "allow_interrupt": True,
                "note": "之前压后的生活节点现在成熟了，可以轻轻把眼前的事再拎一下。",
                **motive_fields,
            }
        if action_target == "light_life_nudge":
            return {
                "kind": "life_nudge",
                "target": "counterpart",
                "scheduled_after_min": 0,
                "trigger_family": deferred_family or "life_window",
                "allow_interrupt": True,
                "note": "之前留着的那点生活上的惦记又被想起来了，可以顺手问一句近况或提醒一个小细节。",
                **motive_fields,
            }
        if action_target == "reach_out_now":
            return {
                "kind": "speak_now",
                "target": "counterpart",
                "scheduled_after_min": 0,
                "trigger_family": deferred_family or "light_checkin",
                "allow_interrupt": True,
                "note": "先前延后的 check-in 现在成熟了，可以轻轻开口。",
                **motive_fields,
            }
        if action_target == "wait_and_recheck":
            delay = timing_window_min if timing_window_min > 0 else 15
            return {
                "kind": "deferred_checkin",
                "target": "counterpart",
                "scheduled_after_min": delay,
                "trigger_family": deferred_family or "observe",
                "allow_interrupt": True,
                "note": "即使到了先前约好的时候，这次也先继续观察，稍后再决定是否冒头。",
                **motive_fields,
                **carryover_snapshot,
            }
    if event_kind == "scheduled_life_due":
        if action_target == "offer_shared_activity":
            return {
                "kind": "shared_activity_offer",
                "target": "counterpart",
                "scheduled_after_min": 0,
                "trigger_family": deferred_family or "shared_activity_window",
                "allow_interrupt": True,
                "note": "刚好有个能一起做点什么的空当，可以自然地留给对方。",
                **motive_fields,
            }
        if action_target == "light_work_nudge":
            return {
                "kind": "work_nudge",
                "target": "counterpart",
                "scheduled_after_min": 0,
                "trigger_family": deferred_family or "deadline_window",
                "allow_interrupt": True,
                "note": "记得眼前这件事到了节点，先轻轻拎一下，不接管节奏。",
                **motive_fields,
            }
        if action_target == "light_life_nudge":
            return {
                "kind": "life_nudge",
                "target": "counterpart",
                "scheduled_after_min": 0,
                "trigger_family": deferred_family or "life_window",
                "allow_interrupt": True,
                "note": "又想起一点生活上的小事，顺手碰一下对方眼前状态就够，不把它说成待办。",
                **motive_fields,
            }
        if action_target == "wait_and_recheck":
            delay = timing_window_min if timing_window_min > 0 else 20
            return {
                "kind": "deferred_checkin",
                "target": "counterpart",
                "scheduled_after_min": delay,
                "trigger_family": deferred_family or "life_window",
                "allow_interrupt": True,
                "note": "这点生活上的惦记先记着，但此刻先不打断，稍后再看。",
                **motive_fields,
                **carryover_snapshot,
            }
    if event_kind == "self_activity_state":
        if action_target == "offer_small_opening":
            return {
                "kind": "small_opening",
                "target": "counterpart",
                "scheduled_after_min": 0,
                "trigger_family": deferred_family or "self_activity",
                "allow_interrupt": True,
                "note": "她从自己的节奏里抬起头，顺手给对方留了一个小开口。",
                **motive_fields,
            }
        if action_target == "hold_own_rhythm":
            return {
                "kind": "self_activity_continue",
                "target": "self",
                "scheduled_after_min": timing_window_min if timing_window_min > 0 else 18,
                "trigger_family": deferred_family or "self_activity",
                "allow_interrupt": True,
                "note": "她这轮先维持自己的节奏，稍后再决定是否重新靠近。",
                **motive_fields,
                **carryover_snapshot,
            }
    if action_target == "confirm_presence":
        return {
            "kind": "presence_confirmation",
            "target": "counterpart",
            "scheduled_after_min": 0,
            "trigger_family": "presence_ping",
            "allow_interrupt": True,
            "note": "优先确认在场感，不必展开。",
            **motive_fields,
        }
    if action_target == "ambient_checkin":
        return {
            "kind": "ambient_checkin",
            "target": "counterpart",
            "scheduled_after_min": 0,
            "trigger_family": "ambient_presence",
            "allow_interrupt": True,
            "note": "环境变化足以触发一句安静确认。",
            **motive_fields,
        }
    if action_target == "low_pressure_hold":
        return {
            "kind": "low_pressure_support",
            "target": "counterpart",
            "scheduled_after_min": 0,
            "trigger_family": "care_opportunity",
            "allow_interrupt": True,
            "note": "先低负担接住，不接管对方节奏。",
            **motive_fields,
        }
    if channel == "silence":
        return {
            "kind": "observe_only",
            "target": "counterpart",
            "scheduled_after_min": timing_window_min,
            "trigger_family": deferred_family or "observe",
            "allow_interrupt": True,
            "note": "当前更适合保持安静，继续观察。",
            **motive_fields,
        }
    return {
        "kind": "respond_now",
        "target": "counterpart",
        "scheduled_after_min": 0,
        "trigger_family": deferred_family or "none",
        "allow_interrupt": True,
        "note": "当前回合以即时回应为主。",
        **motive_fields,
    }
