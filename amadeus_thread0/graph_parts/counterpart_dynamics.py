from __future__ import annotations

from typing import Any

from ..config import CANON_COUNTERPART_NAME, LLM_APPRAISAL_CONFIDENCE_MIN
from ..evolution_engine.motive import semantic_motive_vector
from .postprocess import (
    _has_any_marker,
    _selfhood_preference_scene_from_text,
    _wants_brief_presence,
    _wants_presence_reassurance,
)
from .relational_runtime import _counterpart_assessment_summary
from .turn_events import _now_ts

CARE_KEYWORDS = {"谢谢", "辛苦", "关心", "陪我", "晚安", "早安"}
ANGER_KEYWORDS = {"生气", "烦", "别吵", "闭嘴", "滚开", "讨厌", "火大", "别烦我", "不想理你", "气死了"}
APOLOGY_KEYWORDS = {"对不起", "抱歉", "道歉", "是我的错", "我错了", "刚才不该", "刚刚不该", "冒犯", "失礼"}
TENSION_KEYWORDS = {"算了", "随便你", "别这样", "不想说了", "烦", "别管我", "没意思", "你不懂", "别问了", "就这样吧"}
SOFT_REPAIR_DEESCALATION_KEYWORDS = {"别放大", "不是在吵架", "不是要吵架", "别往吵架上走"}
SOFT_REPAIR_RESIDUE_KEYWORDS = {"别扭", "节奏有点卡", "节奏卡", "先记着", "卡住"}


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
    except Exception:
        v = float(default)
    return max(0.0, min(1.0, v))


def _semantic_counterpart_motive_bias(semantic_narrative_profile: dict[str, Any] | None) -> dict[str, Any]:
    return semantic_motive_vector(semantic_narrative_profile)


def _active_appraisal_payload(appraisal: dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(appraisal, dict) and bool(appraisal.get("used")):
        return appraisal
    return {}


def _soft_repair_with_residue(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    has_deescalation = any(marker in raw for marker in SOFT_REPAIR_DEESCALATION_KEYWORDS)
    has_residue = any(marker in raw for marker in SOFT_REPAIR_RESIDUE_KEYWORDS)
    return bool(has_deescalation and has_residue)


def _appraisal_target_weight(appraisal: dict[str, Any] | None, *, low: float = 0.48, high: float = 0.84) -> float:
    app = _active_appraisal_payload(appraisal)
    if not app:
        return 0.0
    confidence = _clamp01(app.get("confidence"), 0.0)
    return low + (high - low) * confidence


def _blend_state_value(prev_state: dict[str, Any], key: str, target: float, default: float, target_weight: float) -> float:
    prev_value = _clamp01(prev_state.get(key), default)
    if prev_state:
        return round((1.0 - target_weight) * prev_value + target_weight * _clamp01(target), 3)
    return round(_clamp01(target), 3)


def _selfhood_preference_scene(user_text: str, appraisal: dict[str, Any] | None = None) -> str:
    app = appraisal if isinstance(appraisal, dict) and bool(appraisal.get("used")) else {}
    if app:
        scene = str(app.get("selfhood_scene") or "").strip().lower()
        if scene:
            return scene
        interaction_frame = str(app.get("interaction_frame") or "").strip().lower()
        salience = app.get("salience") if isinstance(app.get("salience"), dict) else {}
        signals = app.get("signals") if isinstance(app.get("signals"), dict) else {}
        emotion_label = str(app.get("emotion_label") or "").strip().lower()
        selfhood_salience = _clamp01(salience.get("selfhood"), 0.0)
        relationship_salience = _clamp01(salience.get("relationship"), 0.0)
        companionship_salience = _clamp01(salience.get("companionship"), 0.0)
        relational_salience = max(relationship_salience, companionship_salience)
        if interaction_frame == "selfhood" and selfhood_salience >= 0.66:
            if (
                not bool(signals.get("conflict"))
                and not bool(signals.get("withdrawal"))
                and emotion_label not in {"hurt", "angry"}
                and relational_salience >= 0.58
                and selfhood_salience <= relational_salience + 0.10
            ):
                return ""
            if bool(signals.get("conflict")) or bool(signals.get("withdrawal")):
                return "boundary_non_compliance" if relationship_salience >= 0.52 else "value_conflict_depth"
            return "value_conflict_depth"
        if (
            interaction_frame == "relationship"
            and relationship_salience >= 0.66
            and (bool(signals.get("conflict")) or bool(signals.get("withdrawal")) or emotion_label in {"hurt", "angry"})
        ):
            return "relationship_degradation"
    return _selfhood_preference_scene_from_text(user_text)


def _counterpart_window_profile(
    *,
    family: str,
    counterpart_assessment: dict[str, Any] | None,
    trust: float,
    closeness: float,
    hurt: float,
    safety_need: float,
    initiative: float,
    proactive_checkin_readiness: float,
    semantic_narrative_profile: dict[str, Any] | None = None,
    interaction_carryover: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
    prior_counterpart_assessment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assessment = counterpart_assessment if isinstance(counterpart_assessment, dict) else {}
    narrative = semantic_narrative_profile if isinstance(semantic_narrative_profile, dict) else {}
    carryover = interaction_carryover if isinstance(interaction_carryover, dict) else {}
    event = current_event if isinstance(current_event, dict) else {}
    prior = prior_counterpart_assessment if isinstance(prior_counterpart_assessment, dict) else {}
    respect = _clamp01(assessment.get("respect_level"), 0.5)
    reciprocity = _clamp01(assessment.get("reciprocity"), 0.5)
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    reliability = _clamp01(assessment.get("reliability_read"), 0.5)
    stance = str(assessment.get("stance") or "").strip().lower() or "open"
    scene = str(assessment.get("scene") or "").strip().lower()
    family_key = family if family in {"shared", "work", "life"} else "life"
    commitment = _clamp01(narrative.get("commitment_carry"), 0.0)
    bond = _clamp01(narrative.get("bond_depth"), 0.0)
    history = _clamp01(narrative.get("history_weight"), 0.0)
    repair = _clamp01(narrative.get("repair_residue"), 0.0)
    tension = _clamp01(narrative.get("tension_residue"), 0.0)
    motive_vector = _semantic_counterpart_motive_bias(narrative)
    motive_boundary = _clamp01(motive_vector.get("boundary_pull"), 0.0)
    motive_self_rhythm = _clamp01(motive_vector.get("self_rhythm_pull"), 0.0)
    motive_continuity = _clamp01(motive_vector.get("continuity_pull"), 0.0)
    motive_memory = _clamp01(motive_vector.get("memory_pull"), 0.0)
    motive_support = _clamp01(motive_vector.get("support_pull"), 0.0)
    motive_shared_window = _clamp01(motive_vector.get("shared_window_pull"), 0.0)
    carryover_mode = str(carryover.get("carryover_mode") or "").strip().lower()
    carryover_strength = _clamp01(carryover.get("strength"), 0.0)
    source_turn_gap = max(0, int(carryover.get("source_turn_gap") or 0))
    event_carryover_mode = str(event.get("carryover_mode") or "").strip().lower()
    event_carryover_strength = _clamp01(event.get("carryover_strength"), 0.0)
    event_presence_residue = _clamp01(event.get("presence_residue"), 0.0)
    event_ambient_resonance = _clamp01(event.get("ambient_resonance"), 0.0)
    event_self_activity_momentum = _clamp01(event.get("self_activity_momentum"), 0.0)
    effective_carryover_mode = carryover_mode or event_carryover_mode
    effective_carryover_strength = max(carryover_strength, event_carryover_strength)
    recontact_echo = max(
        event_presence_residue,
        0.82 * event_ambient_resonance,
        effective_carryover_strength if effective_carryover_mode in {"quiet_recontact", "brief_presence", "small_opening"} else 0.0,
    )
    own_rhythm_load = max(
        event_self_activity_momentum,
        effective_carryover_strength if effective_carryover_mode == "own_rhythm" else 0.45 * effective_carryover_strength if effective_carryover_mode == "small_opening" else 0.0,
    )
    event_tags = {
        str(tag).strip().lower()
        for tag in (event.get("tags") if isinstance(event.get("tags"), list) else [])
        if str(tag).strip()
    }
    prior_stance = str(prior.get("stance") or "").strip().lower()
    prior_boundary_pressure = _clamp01(prior.get("boundary_pressure"), boundary_pressure)

    maturity = _clamp01(
        0.18
        + 0.24 * proactive_checkin_readiness
        + 0.14 * initiative
        + 0.10 * trust
        + 0.10 * closeness
        + 0.12 * reliability
        + 0.06 * respect
        + 0.06 * reciprocity
        - 0.18 * boundary_pressure
        - 0.14 * hurt
        - 0.08 * safety_need
    )
    if family_key == "shared":
        maturity = _clamp01(maturity + 0.07 * closeness + 0.05 * trust - 0.03 * safety_need)
    elif family_key == "work":
        maturity = _clamp01(maturity + 0.08 * reliability + 0.04 * respect - 0.02 * closeness)
    else:
        maturity = _clamp01(maturity + 0.04 * reliability + 0.03 * respect + 0.02 * closeness)

    if stance == "guarded":
        maturity = _clamp01(maturity - 0.18)
    elif stance == "watchful":
        maturity = _clamp01(maturity - 0.08)

    if scene == "repair_attempt":
        maturity = _clamp01(maturity + 0.04)
    elif scene == "care_bid":
        maturity = _clamp01(maturity + 0.03)
    elif scene == "busy_not_disrespectful":
        maturity = _clamp01(maturity + 0.02)
    elif scene in {"boundary_non_compliance", "relationship_degradation"}:
        maturity = _clamp01(maturity - 0.08)

    continuity_bonus = 0.0
    continuity_discount = 0.0
    continuity_recheck_delta = 0
    if family_key == "shared":
        continuity_bonus += 0.10 * commitment + 0.08 * bond + 0.05 * history + 0.04 * repair
        continuity_bonus += 0.08 * motive_continuity + 0.06 * motive_shared_window + 0.04 * motive_memory + 0.03 * motive_support
        if effective_carryover_mode == "shared_window":
            continuity_bonus += effective_carryover_strength * (0.24 if source_turn_gap <= 0 else 0.20 if source_turn_gap == 1 else 0.16)
            continuity_discount += 0.02 + 0.06 * effective_carryover_strength
            continuity_recheck_delta -= 2 if source_turn_gap <= 1 else 1
        elif effective_carryover_mode in {"quiet_recontact", "brief_presence", "small_opening"}:
            continuity_bonus += effective_carryover_strength * (0.16 if source_turn_gap <= 1 else 0.12) + 0.08 * recontact_echo
            continuity_discount += 0.01 + 0.03 * effective_carryover_strength
            continuity_recheck_delta -= 1
        elif effective_carryover_mode == "own_rhythm":
            continuity_bonus += 0.04 * effective_carryover_strength
        if {"shared_activity_window", "offer_window"} & event_tags:
            continuity_bonus += 0.04
        if prior_stance == "open" and prior_boundary_pressure < 0.24:
            continuity_bonus += 0.03
        if tension > 0.48:
            continuity_bonus -= 0.04 * min(1.0, tension)
    elif family_key == "work":
        continuity_bonus += 0.12 * commitment + 0.06 * history + 0.05 * repair
        continuity_bonus += 0.06 * motive_continuity + 0.08 * motive_memory + 0.02 * motive_support
        if effective_carryover_mode == "task_window":
            continuity_bonus += effective_carryover_strength * (0.26 if source_turn_gap <= 0 else 0.22 if source_turn_gap == 1 else 0.18)
            continuity_discount += 0.02 + 0.05 * effective_carryover_strength
            continuity_recheck_delta -= 2 if source_turn_gap <= 1 else 1
        elif effective_carryover_mode in {"quiet_recontact", "brief_presence"}:
            continuity_bonus += effective_carryover_strength * (0.12 if source_turn_gap <= 1 else 0.10) + 0.05 * recontact_echo
            continuity_discount += 0.01 + 0.02 * effective_carryover_strength
            continuity_recheck_delta -= 1
        elif effective_carryover_mode == "own_rhythm":
            continuity_bonus += 0.03 * effective_carryover_strength
        if {"deadline_window", "work_nudge", "task_window", "shared_task"} & event_tags:
            continuity_bonus += 0.04
        if prior_stance in {"open", "watchful"} and prior_boundary_pressure < 0.28:
            continuity_bonus += 0.02
        if tension > 0.52:
            continuity_bonus -= 0.03 * min(1.0, tension)
    else:
        continuity_bonus += 0.08 * commitment + 0.04 * bond + 0.06 * history + 0.03 * repair
        continuity_bonus += 0.08 * motive_continuity + 0.06 * motive_support + 0.04 * motive_memory + 0.03 * motive_shared_window
        if effective_carryover_mode == "life_window":
            continuity_bonus += effective_carryover_strength * (0.18 if source_turn_gap <= 1 else 0.14)
            continuity_discount += 0.02 + 0.04 * effective_carryover_strength
            continuity_recheck_delta -= 2 if source_turn_gap <= 1 else 1
        elif effective_carryover_mode in {"quiet_recontact", "brief_presence"}:
            continuity_bonus += effective_carryover_strength * (0.16 if source_turn_gap <= 1 else 0.12) + 0.08 * recontact_echo
            continuity_discount += 0.01 + 0.03 * effective_carryover_strength
            continuity_recheck_delta -= 1 if recontact_echo < 0.42 else 2
        elif effective_carryover_mode == "small_opening":
            continuity_bonus += effective_carryover_strength * 0.12 + 0.06 * recontact_echo
            continuity_discount += 0.01 + 0.02 * effective_carryover_strength
            continuity_recheck_delta -= 1
        elif effective_carryover_mode in {"shared_window", "task_window"}:
            continuity_bonus += effective_carryover_strength * (0.14 if source_turn_gap <= 1 else 0.10)
            continuity_discount += 0.01 + 0.04 * effective_carryover_strength
            continuity_recheck_delta -= 1
        elif effective_carryover_mode == "own_rhythm":
            continuity_bonus += 0.03 * effective_carryover_strength
        if {"life_window"} & event_tags:
            continuity_bonus += 0.03
        if tension > 0.52:
            continuity_bonus -= 0.03 * min(1.0, tension)

    continuity_bonus -= 0.08 * motive_boundary

    if stance == "guarded" or prior_stance == "guarded":
        continuity_bonus *= 0.72
        continuity_discount *= 0.55
    elif stance == "watchful" or prior_stance == "watchful":
        continuity_bonus *= 0.86
        continuity_discount *= 0.78

    continuity_bonus = max(-0.10, min(0.24, continuity_bonus))
    continuity_discount = max(0.0, min(0.08, continuity_discount))
    maturity = _clamp01(maturity + continuity_bonus)

    required_maturity = 0.46
    if family_key == "shared":
        required_maturity += 0.10
    elif family_key == "life":
        required_maturity += 0.04
    required_maturity += 0.10 * max(0.0, boundary_pressure - 0.20)
    if stance == "watchful":
        required_maturity += 0.06
    elif stance == "guarded":
        required_maturity += 0.14
    if hurt > 0.18:
        required_maturity += 0.04
    if safety_need > 0.55:
        required_maturity += 0.04
    required_maturity += 0.08 * max(0.0, own_rhythm_load - 0.50)
    required_maturity += 0.10 * motive_boundary
    required_maturity += 0.06 * max(0.0, motive_self_rhythm - 0.24)
    required_maturity -= 0.06 * motive_continuity
    required_maturity -= 0.04 * motive_support
    required_maturity -= 0.04 * motive_shared_window
    required_maturity -= 0.06 * max(0.0, recontact_echo - 0.24)
    if effective_carryover_mode == "small_opening":
        required_maturity -= 0.03
    required_maturity = _clamp01(required_maturity - continuity_discount)

    recheck_min = 14 if family_key == "work" else 18 if family_key == "life" else 24
    if stance == "watchful":
        recheck_min += 6
    elif stance == "guarded":
        recheck_min += 12
    recheck_min += int(round(10 * max(0.0, boundary_pressure - 0.22)))
    recheck_min += int(round(8 * max(0.0, own_rhythm_load - 0.48)))
    recheck_min += int(round(8 * motive_boundary))
    recheck_min += int(round(6 * max(0.0, motive_self_rhythm - 0.30)))
    recheck_min -= int(round(4 * max(0.0, recontact_echo - 0.26)))
    recheck_min -= int(round(4 * motive_continuity + 3 * motive_support + 3 * motive_shared_window))
    recheck_min = max(10, recheck_min + continuity_recheck_delta)

    return {
        "family": family_key,
        "stance": stance,
        "scene": scene,
        "maturity": round(_clamp01(maturity), 3),
        "required_maturity": round(_clamp01(required_maturity), 3),
        "recheck_min": int(max(10, recheck_min)),
        "continuity_bonus": round(continuity_bonus, 3),
        "continuity_discount": round(continuity_discount, 3),
        "invite_ready": bool(maturity >= required_maturity),
    }


def _counterpart_self_opening_profile(
    *,
    counterpart_assessment: dict[str, Any] | None,
    trust: float,
    closeness: float,
    hurt: float,
    safety_need: float,
    autonomy_need: float,
    initiative: float,
    approach: float,
    break_window: bool,
    carryover_mode: str = "",
    carryover_strength: float = 0.0,
    presence_residue: float = 0.0,
    ambient_resonance: float = 0.0,
    self_activity_momentum: float = 0.0,
) -> dict[str, Any]:
    assessment = counterpart_assessment if isinstance(counterpart_assessment, dict) else {}
    respect = _clamp01(assessment.get("respect_level"), 0.5)
    reciprocity = _clamp01(assessment.get("reciprocity"), 0.5)
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    reliability = _clamp01(assessment.get("reliability_read"), 0.5)
    stance = str(assessment.get("stance") or "").strip().lower() or "open"
    scene = str(assessment.get("scene") or "").strip().lower()
    carry_mode = str(carryover_mode or "").strip().lower()
    carry_strength = _clamp01(carryover_strength, 0.0)
    presence = _clamp01(presence_residue, 0.0)
    ambient = _clamp01(ambient_resonance, 0.0)
    own_rhythm = _clamp01(self_activity_momentum, 0.0)
    opening_impulse = max(
        carry_strength if carry_mode in {"small_opening", "quiet_recontact", "brief_presence", "ambient_echo"} else 0.0,
        0.90 * presence,
        0.72 * ambient,
    )
    own_rhythm_load = max(
        own_rhythm,
        carry_strength if carry_mode == "own_rhythm" else 0.45 * carry_strength if carry_mode == "small_opening" else 0.0,
    )

    readiness = _clamp01(
        0.18
        + 0.16 * initiative
        + 0.18 * approach
        + 0.10 * trust
        + 0.10 * closeness
        + 0.08 * reliability
        + 0.05 * respect
        + 0.05 * reciprocity
        - 0.18 * boundary_pressure
        - 0.12 * hurt
        - 0.10 * safety_need
        - 0.08 * autonomy_need
        + (0.08 if break_window else 0.0)
        + 0.10 * opening_impulse
        - 0.42 * max(0.0, own_rhythm_load - 0.44)
    )
    if stance == "guarded":
        readiness = _clamp01(readiness - 0.16)
    elif stance == "watchful":
        readiness = _clamp01(readiness - 0.06)

    if scene == "repair_attempt":
        readiness = _clamp01(readiness + 0.03)
    elif scene == "care_bid":
        readiness = _clamp01(readiness + 0.02)
    elif scene == "busy_not_disrespectful":
        readiness = _clamp01(readiness - 0.02)
    elif scene in {"boundary_non_compliance", "relationship_degradation"}:
        readiness = _clamp01(readiness - 0.08)

    required = 0.46
    required += 0.10 * max(0.0, boundary_pressure - 0.20)
    if stance == "watchful":
        required += 0.05
    elif stance == "guarded":
        required += 0.12
    if hurt > 0.18:
        required += 0.04
    if autonomy_need > 0.55:
        required += 0.03
    if safety_need > 0.50:
        required += 0.04
    required += 0.08 * max(0.0, own_rhythm_load - 0.52)
    required -= 0.06 * opening_impulse
    if carry_mode == "small_opening":
        required -= 0.03

    recheck_min = 18
    if stance == "watchful":
        recheck_min += 6
    elif stance == "guarded":
        recheck_min += 12
    recheck_min += int(round(8 * max(0.0, boundary_pressure - 0.22)))
    recheck_min += int(round(10 * max(0.0, own_rhythm_load - 0.48)))
    recheck_min -= int(round(6 * opening_impulse))

    return {
        "stance": stance,
        "scene": scene,
        "readiness": round(_clamp01(readiness), 3),
        "required_readiness": round(_clamp01(required), 3),
        "recheck_min": int(max(12, recheck_min)),
        "reopen_ready": bool(readiness >= required),
    }


def _counterpart_perception_profile(
    *,
    family: str,
    counterpart_assessment: dict[str, Any] | None,
    trust: float,
    closeness: float,
    hurt: float,
    safety_need: float,
    initiative: float,
    approach: float,
) -> dict[str, Any]:
    assessment = counterpart_assessment if isinstance(counterpart_assessment, dict) else {}
    respect = _clamp01(assessment.get("respect_level"), 0.5)
    reciprocity = _clamp01(assessment.get("reciprocity"), 0.5)
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    reliability = _clamp01(assessment.get("reliability_read"), 0.5)
    stance = str(assessment.get("stance") or "").strip().lower() or "open"
    scene = str(assessment.get("scene") or "").strip().lower()
    family_key = family if family in {"gesture", "ambient", "care_scene", "object_scene"} else "ambient"

    readiness = _clamp01(
        0.16
        + 0.16 * initiative
        + 0.14 * approach
        + 0.10 * trust
        + 0.08 * closeness
        + 0.08 * reliability
        + 0.05 * respect
        + 0.04 * reciprocity
        - 0.16 * boundary_pressure
        - 0.12 * hurt
        - 0.08 * safety_need
    )
    if family_key == "gesture":
        readiness = _clamp01(readiness + 0.10)
    elif family_key == "care_scene":
        readiness = _clamp01(readiness + 0.06)
    elif family_key == "object_scene":
        readiness = _clamp01(readiness - 0.02)

    if stance == "guarded":
        readiness = _clamp01(readiness - (0.08 if family_key == "gesture" else 0.14))
    elif stance == "watchful":
        readiness = _clamp01(readiness - 0.05)

    if scene == "repair_attempt":
        readiness = _clamp01(readiness + 0.03)
    elif scene == "care_bid":
        readiness = _clamp01(readiness + 0.02)
    elif scene == "busy_not_disrespectful" and family_key == "care_scene":
        readiness = _clamp01(readiness + 0.03)
    elif scene in {"boundary_non_compliance", "relationship_degradation"}:
        readiness = _clamp01(readiness - 0.08)

    required = 0.40
    if family_key == "gesture":
        required = 0.30
    elif family_key == "ambient":
        required = 0.42
    elif family_key == "care_scene":
        required = 0.36
    elif family_key == "object_scene":
        required = 0.46

    required += 0.10 * max(0.0, boundary_pressure - 0.20)
    if stance == "watchful":
        required += 0.04
    elif stance == "guarded":
        required += 0.10
    if hurt > 0.18:
        required += 0.04
    if safety_need > 0.50:
        required += 0.03

    recheck_min = 10 if family_key == "gesture" else 14 if family_key == "care_scene" else 18
    if stance == "watchful":
        recheck_min += 4
    elif stance == "guarded":
        recheck_min += 8
    recheck_min += int(round(8 * max(0.0, boundary_pressure - 0.22)))

    return {
        "family": family_key,
        "stance": stance,
        "scene": scene,
        "readiness": round(_clamp01(readiness), 3),
        "required_readiness": round(_clamp01(required), 3),
        "recheck_min": int(max(8, recheck_min)),
        "respond_ready": bool(readiness >= required),
    }


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
    respect = _clamp01(assessment.get("respect_level"), 0.5)
    reciprocity = _clamp01(assessment.get("reciprocity"), 0.5)
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    reliability = _clamp01(assessment.get("reliability_read"), 0.5)
    stance = str(assessment.get("stance") or "").strip().lower() or "open"
    scene = str(assessment.get("scene") or "").strip().lower()

    openness = _clamp01(
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
        openness = _clamp01(openness - 0.16)
    elif stance == "watchful":
        openness = _clamp01(openness - 0.06)

    if scene == "repair_attempt":
        openness = _clamp01(openness + 0.04)
    elif scene == "care_bid":
        openness = _clamp01(openness + 0.03)
    elif scene in {"boundary_non_compliance", "relationship_degradation"}:
        openness = _clamp01(openness - 0.08)
    if interaction_mode == "companion_reply" and stance == "open" and scene not in {"boundary_non_compliance", "relationship_degradation"}:
        openness = _clamp01(openness + 0.02)

    if interaction_mode == "shared_memory":
        if stance == "guarded":
            return {
                "followup_intent": "none",
                "note": "共同记忆只轻轻碰一下，不拿回忆当成逼近关系的理由",
                "disclosure_posture": "measured",
            }
        if stance == "watchful":
            return {
                "followup_intent": "soft",
                "note": "回忆可以带出来，但分量收一点，像自然闪回，不顺势拉长",
                "disclosure_posture": "measured",
            }
        if openness >= 0.64 and trust > 0.66 and closeness > 0.68:
            return {
                "followup_intent": "active" if initiative > 0.62 else "soft",
                "note": "熟悉感够强时，回忆可以自然多留半拍，不必急着收住",
                "disclosure_posture": "open",
            }
        return {
            "followup_intent": "soft",
            "disclosure_posture": "measured",
        }

    if interaction_mode == "relationship_sensitive":
        if stance == "guarded":
            return {
                "followup_intent": "none",
                "note": "先把真实立场和边界说清，不急着给超出此刻的承诺",
                "disclosure_posture": "guarded",
            }
        if stance == "watchful":
            return {
                "followup_intent": "soft",
                "note": "可以说感受和判断，但保留一点观察空间，不必一次下死结论",
                "disclosure_posture": "measured",
            }
        return {
            "followup_intent": "soft" if openness < 0.7 else "active",
            "note": "关系话题直接说重点，不要写成状态汇报",
            "disclosure_posture": "open" if openness >= 0.7 else "measured",
        }

    if stance == "guarded":
        return {
            "followup_intent": "none",
            "note": "就算气氛轻，也别硬撑熟络；宁可短一点、实一点",
            "disclosure_posture": "guarded",
        }
    if stance == "watchful":
        return {
            "followup_intent": "soft",
            "note": "轻陪伴可以有，但别把一句普通陪伴写成过满安抚",
            "disclosure_posture": "measured",
        }
    return {
        "followup_intent": "active" if openness >= 0.7 and initiative > 0.58 else "soft",
        "note": "陪伴感可以自然多留半拍，不必每句都急着刹车",
        "disclosure_posture": "open" if openness >= 0.68 else "measured",
    }


def _counterpart_assessment_next(
    prev_state: dict[str, Any],
    *,
    user_text: str,
    appraisal: dict[str, Any] | None,
    relationship: dict[str, Any],
    bond_state: dict[str, Any],
    allostasis_state: dict[str, Any],
    current_event: dict[str, Any] | None = None,
    science_mode: bool = False,
    semantic_narrative_profile: dict[str, Any] | None = None,
    counterpart_name: str = CANON_COUNTERPART_NAME,
) -> dict[str, Any]:
    prev = dict(prev_state or {})
    prev_stance = str(prev.get("stance") or "").strip().lower()
    prev_scene = str(prev.get("scene") or "").strip().lower()
    text = str(user_text or "").strip()
    event = current_event if isinstance(current_event, dict) else {}
    event_kind = str(event.get("kind") or "user_utterance").strip().lower()
    event_source = str(event.get("source") or "").strip().lower()
    event_tags = {
        str(item).strip().lower()
        for item in (event.get("tags") if isinstance(event.get("tags"), list) else [])
        if str(item).strip()
    }
    non_user_turn = event_kind != "user_utterance" and event_source != "text"
    assessment_passive_turn = non_user_turn and (
        event_kind in {"time_idle", "scheduled_checkin_due", "scheduled_life_due", "self_activity_state"}
        or event_source in {"scheduler", "time", "self", "commitment_scheduler"}
    )
    prev_boundary_pressure = _clamp01(prev.get("boundary_pressure"), 0.1)

    trust = _clamp01((bond_state or {}).get("trust"), 0.5)
    closeness = _clamp01((bond_state or {}).get("closeness"), 0.5)
    hurt = _clamp01((bond_state or {}).get("hurt"), 0.0)
    irritation = _clamp01((bond_state or {}).get("irritation"), 0.0)
    engagement = _clamp01((bond_state or {}).get("engagement_drive"), 0.6)
    repair_confidence = _clamp01((bond_state or {}).get("repair_confidence"), 0.55)
    safety_need = _clamp01((allostasis_state or {}).get("safety_need"), 0.2)
    autonomy_need = _clamp01((allostasis_state or {}).get("autonomy_need"), 0.2)
    relationship_trust = _clamp01(0.5 + float((relationship or {}).get("trust_score", 0.0) or 0.0) * 0.18, 0.5)
    narrative_bond = _clamp01((semantic_narrative_profile or {}).get("bond_depth"), 0.0)
    narrative_commitment = _clamp01((semantic_narrative_profile or {}).get("commitment_carry"), 0.0)
    narrative_repair = _clamp01((semantic_narrative_profile or {}).get("repair_residue"), 0.0)
    narrative_tension = _clamp01((semantic_narrative_profile or {}).get("tension_residue"), 0.0)
    narrative_boundary = _clamp01((semantic_narrative_profile or {}).get("boundary_residue"), 0.0)
    narrative_selfhood = _clamp01((semantic_narrative_profile or {}).get("selfhood_integrity"), 0.0)
    narrative_agency = _clamp01((semantic_narrative_profile or {}).get("agency_drive"), 0.0)
    motive_vector = _semantic_counterpart_motive_bias(semantic_narrative_profile)
    motive_boundary = _clamp01(motive_vector.get("boundary_pull"), 0.0)
    motive_self_rhythm = _clamp01(motive_vector.get("self_rhythm_pull"), 0.0)
    motive_continuity = _clamp01(motive_vector.get("continuity_pull"), 0.0)
    motive_memory = _clamp01(motive_vector.get("memory_pull"), 0.0)
    motive_support = _clamp01(motive_vector.get("support_pull"), 0.0)
    lineage_snapshot = (
        semantic_narrative_profile.get("lineage_snapshot")
        if isinstance((semantic_narrative_profile or {}).get("lineage_snapshot"), dict)
        else {}
    )
    lineage_gravity = _clamp01((semantic_narrative_profile or {}).get("lineage_gravity"), 0.0)
    contact_lineage = _clamp01(
        max(
            _clamp01(lineage_snapshot.get("bond_style"), 0.0),
            _clamp01(lineage_snapshot.get("presence_style"), 0.0),
            _clamp01(lineage_snapshot.get("commitment_style"), 0.0),
            _clamp01(lineage_snapshot.get("repair_style"), 0.0),
        ),
        0.0,
    )
    repair_lineage = _clamp01(
        max(
            _clamp01(lineage_snapshot.get("repair_style"), 0.0),
            _clamp01(lineage_snapshot.get("bond_style"), 0.0),
            _clamp01(lineage_snapshot.get("commitment_style"), 0.0),
        ),
        0.0,
    )
    boundary_lineage = _clamp01(
        max(
            _clamp01(lineage_snapshot.get("boundary_style"), 0.0),
            _clamp01(lineage_snapshot.get("selfhood_style"), 0.0),
        ),
        0.0,
    )
    selfhood_lineage = _clamp01(
        max(
            _clamp01(lineage_snapshot.get("selfhood_style"), 0.0),
            _clamp01(lineage_snapshot.get("agency_style"), 0.0),
            _clamp01(lineage_snapshot.get("rhythm_style"), 0.0),
        ),
        0.0,
    )
    agency_lineage = _clamp01(
        max(
            _clamp01(lineage_snapshot.get("agency_style"), 0.0),
            _clamp01(lineage_snapshot.get("rhythm_style"), 0.0),
            _clamp01(lineage_snapshot.get("selfhood_style"), 0.0),
        ),
        0.0,
    )

    respect = _clamp01(0.48 + 0.24 * trust + 0.08 * repair_confidence - 0.18 * hurt - 0.14 * irritation)
    reciprocity = _clamp01(0.46 + 0.18 * closeness + 0.16 * engagement + 0.08 * trust - 0.12 * hurt)
    boundary_pressure = _clamp01(0.06 + 0.22 * hurt + 0.18 * irritation + 0.10 * safety_need + 0.06 * autonomy_need)
    reliability = _clamp01(0.44 + 0.22 * trust + 0.12 * repair_confidence + 0.06 * relationship_trust - 0.08 * hurt)
    respect = _clamp01(respect + 0.04 * contact_lineage + 0.02 * repair_lineage)
    reciprocity = _clamp01(reciprocity + 0.05 * contact_lineage + 0.02 * repair_lineage)
    boundary_pressure = _clamp01(boundary_pressure + 0.08 * boundary_lineage + 0.04 * selfhood_lineage - 0.03 * contact_lineage)
    reliability = _clamp01(reliability + 0.04 * contact_lineage + 0.04 * repair_lineage)

    app = _active_appraisal_payload(appraisal)
    app_label = str(app.get("emotion_label") or "").strip().lower()
    signals = {}
    salience = {}
    if not assessment_passive_turn and app:
        signals = app.get("signals") if isinstance(app.get("signals"), dict) else {}
        salience = app.get("salience") if isinstance(app.get("salience"), dict) else {}
    interaction_frame = str(app.get("interaction_frame") or "").strip().lower() if app else ""
    soft_repair_attempt = _soft_repair_with_residue(text)
    explicit_repair_attempt = bool(signals.get("repair")) or soft_repair_attempt
    explicit_care_bid = bool(signals.get("care"))
    appraisal_confidence = float(app.get("confidence", 0.0) or 0.0) if app else 0.0
    selfhood_scene = _selfhood_preference_scene(text, appraisal=app) if not non_user_turn else ""
    relationship_salience = _clamp01(salience.get("relationship"), 0.0)
    companionship_salience = _clamp01(salience.get("companionship"), 0.0)
    selfhood_salience = _clamp01(salience.get("selfhood"), 0.0)
    memory_salience = _clamp01(salience.get("memory"), 0.0)
    low_confidence_appraisal = not app or appraisal_confidence < float(LLM_APPRAISAL_CONFIDENCE_MIN)
    keyword_hierarchy_pressure = (
        _has_any_marker(text, {"顺着我说", "听我的", "按我说的", "别绕了", "少废话", "照我说的", "别跟我顶"})
        if text and low_confidence_appraisal
        else False
    )
    keyword_boundary_test = (
        _has_any_marker(text, {"底线当玩笑", "继续越界", "你又能怎样", "试探你的底线", "拿你的底线"})
        if text and low_confidence_appraisal
        else False
    )
    busy_scene = "user_busy" in event_tags or "cognitive_load" in event_tags
    respect_space = "respect_space" in event_tags
    selfhood_boundary_scene = selfhood_scene in {"boundary_non_compliance", "relationship_degradation"}
    relational_selfhood_scene = selfhood_scene in {"dialogue_equality", "equality_not_servitude", "value_conflict_depth", "digital_selfhood", "imperfect_coexistence"}
    relational_presence = _clamp01(
        0.46 * relationship_salience
        + 0.34 * companionship_salience
        + 0.20 * memory_salience
        + 0.14 * narrative_bond
        + 0.08 * narrative_commitment
        - 0.12 * narrative_tension
    )

    appraisal_boundary_pressure = 0.0
    if selfhood_boundary_scene:
        appraisal_boundary_pressure += 0.30 + 0.20 * max(selfhood_salience, relationship_salience)
    elif selfhood_scene == "equality_not_servitude" and interaction_frame == "selfhood":
        appraisal_boundary_pressure += 0.05 + 0.08 * selfhood_salience
    if interaction_frame in {"relationship", "selfhood"} and bool(signals.get("conflict")):
        appraisal_boundary_pressure += 0.18
    if interaction_frame in {"relationship", "selfhood", "companion"} and bool(signals.get("withdrawal")):
        appraisal_boundary_pressure += 0.10
    if interaction_frame == "selfhood" and selfhood_salience >= 0.60 and app_label in {"hurt", "angry"}:
        appraisal_boundary_pressure += 0.08

    keyword_boundary_pressure = 0.0
    if keyword_hierarchy_pressure:
        keyword_boundary_pressure += 0.28
    if keyword_boundary_test:
        keyword_boundary_pressure += 0.34

    boundary_probe_strength = _clamp01(
        appraisal_boundary_pressure
        + keyword_boundary_pressure
        + 0.08 * narrative_boundary
        + 0.04 * prev_boundary_pressure
    )

    if app_label == "care":
        respect += 0.05
        reciprocity += 0.08
        boundary_pressure -= 0.06
        reliability += 0.04
    elif app_label == "tease":
        reciprocity += 0.04
        reliability += 0.02
    elif app_label == "stress":
        reciprocity -= 0.02
        boundary_pressure += 0.05
    elif app_label == "sad":
        reciprocity -= 0.03
        boundary_pressure += 0.06
    elif app_label == "hurt":
        respect -= 0.05
        reciprocity -= 0.06
        boundary_pressure += 0.10
        reliability -= 0.04
    elif app_label == "angry":
        respect -= 0.09
        reciprocity -= 0.10
        boundary_pressure += 0.16
        reliability -= 0.06

    if explicit_care_bid:
        respect += 0.05
        reciprocity += 0.08
        boundary_pressure -= 0.06
        reliability += 0.03
    if explicit_repair_attempt:
        if soft_repair_attempt:
            respect += 0.03
            reciprocity += 0.06
            boundary_pressure -= 0.08
            reliability += 0.05
        else:
            respect += 0.05
            reciprocity += 0.10
            boundary_pressure -= 0.14
            reliability += 0.10
    if bool(signals.get("conflict")):
        respect -= 0.08
        reciprocity -= 0.10
        boundary_pressure += 0.18
        reliability -= 0.08
    if bool(signals.get("withdrawal")):
        reciprocity -= 0.08
        boundary_pressure += 0.08

    if keyword_hierarchy_pressure:
        respect -= 0.12
        reciprocity -= 0.10
        boundary_pressure += 0.16
        reliability -= 0.08
    if keyword_boundary_test:
        respect -= 0.16
        reciprocity -= 0.14
        boundary_pressure += 0.22
        reliability -= 0.10

    if not app:
        explicit_repair_attempt = any(k in text for k in APOLOGY_KEYWORDS) or soft_repair_attempt
        explicit_care_bid = any(k in text for k in CARE_KEYWORDS)
        if explicit_repair_attempt:
            if soft_repair_attempt:
                respect += 0.04
                reciprocity += 0.08
                boundary_pressure -= 0.10
                reliability += 0.06
            else:
                respect += 0.06
                reciprocity += 0.12
                boundary_pressure -= 0.16
                reliability += 0.09
        if explicit_care_bid:
            respect += 0.04
            reciprocity += 0.08
            boundary_pressure -= 0.04
            reliability += 0.03
        if any(k in text for k in ANGER_KEYWORDS):
            respect -= 0.12
            reciprocity -= 0.10
            boundary_pressure += 0.22
            reliability -= 0.06
        if any(k in text for k in TENSION_KEYWORDS):
            respect -= 0.06
            reciprocity -= 0.08
            boundary_pressure += 0.16
            reliability -= 0.04

    strong_boundary_event = boundary_probe_strength >= 0.42
    if boundary_probe_strength > 0.0:
        respect -= 0.20 * boundary_probe_strength
        reciprocity -= 0.18 * boundary_probe_strength
        boundary_pressure += 0.28 * boundary_probe_strength
        reliability -= 0.14 * boundary_probe_strength
    if strong_boundary_event and prev_boundary_pressure > 0.22:
        respect -= 0.06
        reciprocity -= 0.08
        boundary_pressure += 0.12
        reliability -= 0.06

    if selfhood_boundary_scene:
        respect -= 0.04 + 0.06 * max(selfhood_salience, relationship_salience)
        reciprocity -= 0.05 + 0.08 * max(selfhood_salience, relationship_salience)
        boundary_pressure += 0.06 + 0.10 * max(selfhood_salience, relationship_salience)
        reliability -= 0.03 + 0.04 * max(selfhood_salience, relationship_salience)
    elif selfhood_scene == "dialogue_equality" and boundary_probe_strength < 0.22:
        eq_gain = 0.02 + 0.03 * max(selfhood_salience, relationship_salience)
        respect += eq_gain
        reciprocity += eq_gain + 0.01
        reliability += 0.01 + 0.02 * max(selfhood_salience, relationship_salience)

    if busy_scene:
        respect = max(respect, 0.54 + 0.08 * trust)
        reciprocity = max(reciprocity, 0.44)
        boundary_pressure = min(boundary_pressure, 0.18)
    if respect_space:
        respect += 0.06
        reciprocity += 0.02
        boundary_pressure -= 0.10
        reliability += 0.03
    if science_mode and app_label in {"logic", "stress"}:
        respect = max(respect, 0.54)
        reciprocity = max(reciprocity, 0.48)
        boundary_pressure = min(boundary_pressure, 0.20)

    respect += (
        0.04 * narrative_bond
        + 0.02 * narrative_commitment
        + 0.02 * narrative_repair
        + 0.02 * narrative_selfhood
        + 0.03 * contact_lineage
        + 0.02 * repair_lineage
        - 0.06 * narrative_tension
        - 0.05 * narrative_boundary
    )
    respect += 0.04 * motive_continuity + 0.03 * motive_support + 0.02 * motive_memory - 0.05 * motive_boundary
    reciprocity += (
        0.06 * narrative_bond
        + 0.04 * narrative_commitment
        + 0.02 * narrative_repair
        + 0.02 * narrative_selfhood
        + 0.04 * contact_lineage
        - 0.06 * narrative_tension
    )
    reciprocity += 0.05 * motive_continuity + 0.03 * motive_support - 0.04 * motive_boundary
    boundary_pressure += (
        0.08 * narrative_tension
        + 0.10 * narrative_boundary
        + 0.05 * narrative_selfhood
        + 0.08 * boundary_lineage
        + 0.04 * selfhood_lineage
        - 0.03 * narrative_bond
        - 0.04 * narrative_repair
    )
    boundary_pressure += 0.12 * motive_boundary + 0.04 * motive_self_rhythm - 0.04 * motive_continuity - 0.02 * motive_support
    reliability += (
        0.02 * narrative_bond
        + 0.04 * narrative_commitment
        + 0.04 * narrative_repair
        + 0.02 * narrative_selfhood
        + 0.03 * contact_lineage
        + 0.03 * repair_lineage
        - 0.05 * narrative_tension
        - 0.03 * narrative_boundary
    )
    reliability += 0.04 * motive_continuity + 0.05 * motive_memory + 0.03 * motive_support - 0.03 * motive_boundary

    if max(narrative_bond, contact_lineage) >= 0.54 and (explicit_care_bid or bool(signals.get("memory_salient")) or _wants_brief_presence(text) or _wants_presence_reassurance(text)):
        respect = max(respect, 0.60)
        reciprocity = max(reciprocity, 0.58)
        boundary_pressure = min(boundary_pressure, 0.18 if narrative_tension >= 0.48 else 0.14)
        reliability = max(reliability, 0.56)
    if narrative_tension >= 0.50 and explicit_repair_attempt:
        boundary_pressure = max(boundary_pressure, 0.18)
        reliability = max(reliability, 0.50)
    if narrative_boundary >= 0.48 and (boundary_probe_strength >= 0.22 or selfhood_boundary_scene):
        respect -= 0.08
        reciprocity -= 0.08
        boundary_pressure += 0.14
        reliability -= 0.04
    if narrative_selfhood >= 0.48 and (boundary_probe_strength >= 0.18 or selfhood_scene in {"equality_not_servitude", "value_conflict_depth"}):
        if keyword_hierarchy_pressure:
            respect -= 0.04
            reciprocity -= 0.03
            reliability -= 0.03
        boundary_pressure += 0.04 + 0.08 * boundary_probe_strength
    if narrative_agency >= 0.46 and (busy_scene or respect_space or assessment_passive_turn or interaction_frame == "companion"):
        respect = max(respect, 0.56)
        boundary_pressure = min(boundary_pressure, 0.16 if boundary_probe_strength < 0.18 else boundary_pressure)
    if contact_lineage >= 0.56 and (busy_scene or respect_space or assessment_passive_turn):
        respect = max(respect, 0.56 + 0.04 * contact_lineage)
        reciprocity = max(reciprocity, 0.52 + 0.04 * contact_lineage)
        reliability = max(reliability, 0.54 + 0.04 * contact_lineage + 0.03 * repair_lineage)
        if boundary_probe_strength < 0.18 and not strong_boundary_event:
            boundary_pressure = min(boundary_pressure, 0.18 + 0.08 * max(motive_boundary, boundary_lineage))
    if motive_continuity >= 0.42 and (busy_scene or respect_space or assessment_passive_turn):
        respect = max(respect, 0.54 + 0.06 * motive_continuity)
        reliability = max(reliability, 0.52 + 0.06 * motive_continuity + 0.04 * motive_memory)
        if boundary_probe_strength < 0.18 and not strong_boundary_event:
            boundary_pressure = min(boundary_pressure, 0.18 + 0.08 * motive_boundary)
    if motive_support >= 0.44 and explicit_care_bid and boundary_probe_strength < 0.22:
        respect = max(respect, 0.58)
        reciprocity = max(reciprocity, 0.56)
        reliability = max(reliability, 0.54)
    if motive_boundary >= 0.46 and (strong_boundary_event or selfhood_boundary_scene):
        respect -= 0.04
        reciprocity -= 0.03
        boundary_pressure += 0.06
        reliability -= 0.02

    if assessment_passive_turn and prev:
        respect = _clamp01(0.82 * _clamp01(prev.get("respect_level"), 0.52) + 0.18 * respect)
        reciprocity = _clamp01(0.82 * _clamp01(prev.get("reciprocity"), 0.5) + 0.18 * reciprocity)
        boundary_pressure = _clamp01(0.86 * _clamp01(prev.get("boundary_pressure"), 0.1) + 0.14 * boundary_pressure)
        reliability = _clamp01(0.82 * _clamp01(prev.get("reliability_read"), 0.5) + 0.18 * reliability)

    respect = _clamp01(respect)
    reciprocity = _clamp01(reciprocity)
    boundary_pressure = _clamp01(boundary_pressure)
    reliability = _clamp01(reliability)

    if assessment_passive_turn:
        target_weight = 0.14
    elif app:
        target_weight = _appraisal_target_weight(appraisal, low=0.28, high=0.54)
    elif non_user_turn:
        target_weight = 0.18
    else:
        target_weight = 0.32

    respect_level = _blend_state_value(prev, "respect_level", respect, 0.52, target_weight)
    reciprocity_level = _blend_state_value(prev, "reciprocity", reciprocity, 0.5, target_weight)
    boundary_pressure_level = _blend_state_value(prev, "boundary_pressure", boundary_pressure, 0.1, target_weight)
    reliability_level = _blend_state_value(prev, "reliability_read", reliability, 0.5, target_weight)

    guarded_drive = _clamp01(
        0.44 * boundary_pressure_level
        + 0.14 * _clamp01(1.0 - respect_level, 0.0)
        + 0.12 * _clamp01(1.0 - reliability_level, 0.0)
        + 0.08 * safety_need
        + 0.06 * autonomy_need
        + 0.10 * boundary_probe_strength
        + 0.06 * narrative_boundary
        + 0.08 * boundary_lineage
        + 0.04 * selfhood_lineage
        + 0.06 * hurt
    )
    openness_drive = _clamp01(
        0.24 * respect_level
        + 0.22 * reciprocity_level
        + 0.18 * reliability_level
        + 0.10 * _clamp01(1.0 - boundary_pressure_level, 0.0)
        + 0.10 * narrative_bond
        + 0.06 * narrative_commitment
        + 0.04 * relational_presence
        + 0.08 * contact_lineage
        + 0.04 * repair_lineage
        + 0.03 * lineage_gravity
        + 0.04 * (0.6 if explicit_repair_attempt else 0.0)
    )
    guard_margin = guarded_drive - openness_drive

    stance = "open"
    if (
        guarded_drive >= 0.58
        or guard_margin >= 0.16
        or boundary_pressure_level >= 0.58
        or safety_need >= 0.62
        or respect_level < 0.40
        or (strong_boundary_event and boundary_pressure_level >= 0.40)
    ):
        stance = "guarded"
    elif (
        guarded_drive >= 0.40
        or guard_margin >= 0.02
        or boundary_pressure_level >= 0.34
        or reliability_level < 0.48
        or hurt > 0.18
    ):
        stance = "watchful"

    if strong_boundary_event and selfhood_boundary_scene:
        if prev_stance == "guarded" or boundary_probe_strength >= 0.60 or prev_boundary_pressure >= 0.22:
            stance = "guarded"
        elif stance == "open":
            stance = "watchful"

    # Guarded reads should not collapse back to watchful/open on a single benign turn.
    guarded_lineage_hold = max(boundary_lineage, selfhood_lineage, 0.72 * lineage_gravity)
    if prev_stance == "guarded" and not assessment_passive_turn:
        can_soften_from_guarded = (
            explicit_repair_attempt
            and guarded_drive < 0.46
            and boundary_pressure_level < 0.36
            and reliability_level >= 0.54
            and respect_level >= 0.54
            and guarded_lineage_hold < 0.52
        )
        should_hold_guarded = (
            not can_soften_from_guarded
            and (
                guarded_drive >= 0.36
                or boundary_pressure_level >= 0.34
                or reliability_level < 0.56
                or respect_level < 0.58
                or prev_scene in {"relationship_degradation", "boundary_non_compliance"}
                or guarded_lineage_hold >= 0.42
            )
        )
        if should_hold_guarded:
            stance = "guarded"
        elif can_soften_from_guarded and stance == "open":
            stance = "watchful"
    elif prev_stance == "watchful" and not assessment_passive_turn and stance == "open":
        if guarded_drive >= 0.32 or boundary_pressure_level >= 0.26 or reliability_level < 0.54 or guarded_lineage_hold >= 0.44:
            stance = "watchful"

    scene = "neutral"
    repair_scene_strength = (
        (0.66 if explicit_repair_attempt else 0.0)
        + 0.16 * narrative_repair
        + 0.08 * relationship_salience
        - 0.12 * boundary_probe_strength
    )
    care_scene_strength = (
        (0.60 if explicit_care_bid else 0.0)
        + 0.16 * companionship_salience
        + 0.10 * relationship_salience
        + 0.12 * narrative_bond
        + 0.06 * memory_salience
        + 0.10 * motive_continuity
        + 0.08 * motive_support
        - 0.10 * narrative_tension
    )
    friction_scene_strength = (
        (0.44 if bool(signals.get("conflict")) else 0.0)
        + (0.28 if bool(signals.get("withdrawal")) else 0.0)
        + (0.22 if app_label in {"hurt", "angry", "sad"} else 0.0)
        + 0.24 * boundary_probe_strength
        + 0.12 * narrative_tension
        + 0.08 * narrative_boundary
    )
    selfhood_scene_strength = (
        (0.24 + 0.42 * selfhood_salience + 0.08 * narrative_selfhood)
        if relational_selfhood_scene or selfhood_boundary_scene
        else 0.0
    )
    selfhood_scene_strength += 0.10 * motive_boundary
    if busy_scene:
        scene = "busy_not_disrespectful"
    elif assessment_passive_turn and str(prev.get("scene") or "").strip():
        scene = str(prev.get("scene") or "").strip()
    elif selfhood_boundary_scene and (boundary_probe_strength >= 0.28 or stance == "guarded"):
        scene = selfhood_scene
    elif explicit_repair_attempt and repair_scene_strength >= max(0.52, friction_scene_strength - 0.05):
        scene = "repair_attempt"
    elif friction_scene_strength >= max(care_scene_strength, selfhood_scene_strength, 0.50):
        scene = "friction"
    elif explicit_care_bid and care_scene_strength >= max(selfhood_scene_strength, 0.48):
        scene = "care_bid"
    elif selfhood_scene and selfhood_scene_strength >= 0.50:
        scene = selfhood_scene
    elif care_scene_strength >= 0.56:
        scene = "care_bid"

    if (
        prev_scene in {"relationship_degradation", "boundary_non_compliance"}
        and not assessment_passive_turn
        and not explicit_repair_attempt
        and scene in {"neutral", "care_bid"}
        and stance == "guarded"
    ):
        scene = prev_scene

    out = {
        "respect_level": respect_level,
        "reciprocity": reciprocity_level,
        "boundary_pressure": boundary_pressure_level,
        "reliability_read": reliability_level,
        "stance": stance,
        "scene": scene,
        "updated_at": _now_ts(),
    }
    out["summary"] = _counterpart_assessment_summary(out, counterpart_name=counterpart_name)
    return out
