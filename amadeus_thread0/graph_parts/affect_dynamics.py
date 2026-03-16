from __future__ import annotations

from typing import Any

from .common import _clamp01, _clamp_signed
from .counterpart_dynamics import _active_appraisal_payload, _appraisal_target_weight, _blend_state_value
from .postprocess import SCIENCE_KEYWORDS, _has_any_marker, _is_nonrelational_support_request

STRUCTURE_REQUEST_KEYWORDS = {
    "结论",
    "解释",
    "步骤",
    "分成",
    "拆开",
    "分析",
    "怎么做",
    "为什么",
    "下一步",
    "建议",
    "两点",
    "一句话",
    "简洁结论",
    "理性的方式",
}

__all__ = [
    "_emotion_decay_target",
    "_emotion_next",
    "_bond_next",
    "_allostasis_next",
    "_behavior_policy_from_state",
]


def _emotion_decay_target(prev_label: str, linger: int) -> dict[str, Any]:
    decay_label = "hurt" if prev_label == "angry" and linger <= 2 else prev_label
    return {
        "angry": {
            "label": decay_label,
            "valence": -0.32,
            "arousal": 0.55,
            "linger": max(0, linger - 1),
            "recovery_rate": 0.12,
            "volatility": 0.55,
        },
        "hurt": {
            "label": "hurt",
            "valence": -0.18,
            "arousal": 0.30,
            "linger": max(0, linger - 1),
            "recovery_rate": 0.16,
            "volatility": 0.28,
        },
        "sad": {
            "label": "sad",
            "valence": -0.30,
            "arousal": 0.25,
            "linger": max(0, linger - 1),
            "recovery_rate": 0.14,
            "volatility": 0.24,
        },
        "stress": {
            "label": "stress",
            "valence": -0.22,
            "arousal": 0.42,
            "linger": max(0, linger - 1),
            "recovery_rate": 0.18,
            "volatility": 0.34,
        },
    }.get(
        prev_label,
        {
            "label": "neutral",
            "valence": 0.0,
            "arousal": 0.30,
            "linger": 0,
            "recovery_rate": 0.25,
            "volatility": 0.18,
        },
    )


def _emotion_next(prev_state: dict[str, Any], user_text: str, science_mode: bool, appraisal: dict[str, Any] | None = None) -> dict[str, Any]:
    prev = dict(prev_state or {})
    prev_label = str(prev.get("label") or "neutral").strip().lower()
    try:
        linger = int(prev.get("linger", 0) or 0)
    except Exception:
        linger = 0
    app = _active_appraisal_payload(appraisal)
    if app:
        label = str(app.get("emotion_label") or "").strip().lower()
        emotion = app.get("emotion") if isinstance(app.get("emotion"), dict) else {}
        confidence = _clamp01(app.get("confidence"), 0.0)
        target_linger = max(0, int(emotion.get("linger", 0) or 0))
        if target_linger == 0 and prev_label in {"angry", "hurt", "sad", "stress"} and linger > 0 and confidence < 0.82:
            target_linger = max(0, linger - 1)
        return {
            "label": label or ("logic" if science_mode else prev_label or "neutral"),
            "valence": _clamp_signed(emotion.get("valence"), -1.0, 1.0, 0.05 if science_mode else 0.0),
            "arousal": _clamp01(emotion.get("arousal"), 0.35),
            "linger": target_linger,
            "recovery_rate": _clamp01(emotion.get("recovery_rate"), 0.20 if science_mode else 0.25),
            "volatility": _clamp01(emotion.get("volatility"), 0.18),
        }

    if science_mode:
        return {
            "label": "logic",
            "valence": 0.05,
            "arousal": 0.35,
            "linger": 1,
            "recovery_rate": 0.20,
            "volatility": 0.18,
        }
    if prev_label in {"angry", "hurt", "sad", "stress"} and linger > 0:
        return _emotion_decay_target(prev_label, linger)
    return {
        "label": "neutral",
        "valence": 0.1,
        "arousal": 0.35,
        "linger": 0,
        "recovery_rate": 0.25,
        "volatility": 0.18,
    }


def _bond_next(
    prev_state: dict[str, Any],
    relationship: dict[str, Any],
    emotion_state: dict[str, Any],
    user_text: str,
    science_mode: bool,
    appraisal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prev = dict(prev_state or {})
    emotion_label = str((emotion_state or {}).get("label") or "neutral").strip().lower()
    trust_base = 0.5 + float(relationship.get("trust_score", 0.0) or 0.0) * 0.15
    closeness_base = 0.5 + float(relationship.get("affinity_score", 0.0) or 0.0) * 0.15
    trust_pull = max(0.0, min(1.0, (trust_base - 0.5) / 0.18))
    closeness_pull = max(0.0, min(1.0, (closeness_base - 0.5) / 0.20))
    positive_shift_scale = _clamp01(
        0.52
        + 0.48
        * (
            0.30 * _clamp01((appraisal or {}).get("relationship_maturity"), 0.0)
            + 0.22 * _clamp01((appraisal or {}).get("bond_depth"), 0.0)
            + 0.30 * trust_pull
            + 0.18 * closeness_pull
        ),
        0.68,
    )
    target = {
        "trust": _clamp01(trust_base, 0.5),
        "closeness": _clamp01(closeness_base, 0.5),
        "hurt": 0.02,
        "irritation": 0.02,
        "engagement_drive": 0.64,
        "repair_confidence": 0.55,
    }

    if emotion_label == "angry":
        target["hurt"] = 0.42
        target["irritation"] = 0.58
        target["engagement_drive"] = 0.36
        target["repair_confidence"] = 0.28
        target["trust"] = _clamp01(target["trust"] - 0.10)
        target["closeness"] = _clamp01(target["closeness"] - 0.08)
    elif emotion_label == "hurt":
        target["hurt"] = 0.46
        target["irritation"] = 0.24
        target["engagement_drive"] = 0.44
        target["repair_confidence"] = 0.46
        target["trust"] = _clamp01(target["trust"] - 0.06)
        target["closeness"] = _clamp01(target["closeness"] - 0.05)
    elif emotion_label == "sad":
        target["hurt"] = 0.32
        target["irritation"] = 0.08
        target["engagement_drive"] = 0.48
        target["repair_confidence"] = 0.50
    elif emotion_label == "care":
        target["trust"] = _clamp01(target["trust"] + 0.05 * positive_shift_scale)
        target["closeness"] = _clamp01(target["closeness"] + 0.08 * positive_shift_scale)
        target["hurt"] = 0.02
        target["irritation"] = 0.02
        target["engagement_drive"] = 0.72
        target["repair_confidence"] = 0.66
    elif emotion_label == "tease":
        target["engagement_drive"] = _clamp01(0.64 + 0.06 * positive_shift_scale)
        target["irritation"] = 0.08
        target["closeness"] = _clamp01(target["closeness"] + 0.02 * positive_shift_scale)
    elif emotion_label == "stress":
        target["engagement_drive"] = 0.52
        target["hurt"] = 0.10 if science_mode else 0.12
        target["irritation"] = 0.08 if science_mode else 0.10
    elif emotion_label == "logic":
        target["hurt"] = 0.02
        target["irritation"] = 0.02
        target["engagement_drive"] = 0.62
        target["repair_confidence"] = 0.56

    app = _active_appraisal_payload(appraisal)
    signals = app.get("signals") if isinstance(app.get("signals"), dict) else {}
    if app:
        positive_shift_scale = _clamp01(
            max(
                positive_shift_scale,
                0.52
                + 0.48
                * (
                    0.30 * _clamp01(app.get("relationship_maturity"), 0.0)
                    + 0.22 * _clamp01(app.get("bond_depth"), 0.0)
                    + 0.30 * trust_pull
                    + 0.18 * closeness_pull
                ),
            ),
            0.68,
        )
        if bool(signals.get("repair")):
            target["trust"] = _clamp01(target["trust"] + 0.03 * positive_shift_scale)
            target["closeness"] = _clamp01(target["closeness"] + 0.03 * positive_shift_scale)
            target["hurt"] = _clamp01(target["hurt"] - 0.10 * positive_shift_scale)
            target["irritation"] = _clamp01(target["irritation"] - 0.08 * positive_shift_scale)
            target["engagement_drive"] = _clamp01(target["engagement_drive"] + 0.08 * positive_shift_scale)
            target["repair_confidence"] = _clamp01(target["repair_confidence"] + 0.10 * positive_shift_scale)
        if bool(signals.get("care")):
            target["trust"] = _clamp01(target["trust"] + 0.02 * positive_shift_scale)
            target["closeness"] = _clamp01(target["closeness"] + 0.04 * positive_shift_scale)
            target["hurt"] = _clamp01(target["hurt"] - 0.04 * positive_shift_scale)
            target["irritation"] = _clamp01(target["irritation"] - 0.03 * positive_shift_scale)
        if bool(signals.get("conflict")):
            target["hurt"] = _clamp01(target["hurt"] + 0.12)
            target["irritation"] = _clamp01(target["irritation"] + 0.14)
            target["engagement_drive"] = _clamp01(target["engagement_drive"] - 0.10)
            target["repair_confidence"] = _clamp01(target["repair_confidence"] - 0.08)
        if bool(signals.get("withdrawal")):
            target["closeness"] = _clamp01(target["closeness"] - 0.04)
            target["engagement_drive"] = _clamp01(target["engagement_drive"] - 0.08)

        deltas = app.get("bond_delta") if isinstance(app.get("bond_delta"), dict) else {}
        delta_scale = 0.92
        for key in ("trust", "closeness", "hurt", "irritation", "engagement_drive", "repair_confidence"):
            if key in deltas:
                delta = delta_scale * _clamp_signed(deltas.get(key), -0.35, 0.35, 0.0)
                if key in {"trust", "closeness", "engagement_drive", "repair_confidence"} and delta > 0.0:
                    delta *= positive_shift_scale
                elif key in {"hurt", "irritation"} and delta < 0.0:
                    delta *= positive_shift_scale
                target[key] = _clamp01(float(target.get(key, 0.0)) + delta)

    target_weight = _appraisal_target_weight(appraisal, low=0.44, high=0.82) if app else 0.35
    out = {
        "trust": _blend_state_value(prev, "trust", target["trust"], trust_base, target_weight),
        "closeness": _blend_state_value(prev, "closeness", target["closeness"], closeness_base, target_weight),
        "hurt": _blend_state_value(prev, "hurt", target["hurt"], 0.0, target_weight),
        "irritation": _blend_state_value(prev, "irritation", target["irritation"], 0.0, target_weight),
        "engagement_drive": _blend_state_value(prev, "engagement_drive", target["engagement_drive"], 0.64, target_weight),
        "repair_confidence": _blend_state_value(prev, "repair_confidence", target["repair_confidence"], 0.55, target_weight),
    }
    evidence_level = _clamp01(
        0.32 * _clamp01((app or {}).get("relationship_maturity"), 0.0)
        + 0.24 * _clamp01((app or {}).get("bond_depth"), 0.0)
        + 0.20 * trust_pull
        + 0.16 * closeness_pull
    )
    companionship_pull = _clamp01(((app or {}).get("salience") or {}).get("companionship"), 0.0)
    trust_cap = _clamp01(trust_base + 0.03 + 0.08 * evidence_level)
    closeness_cap = _clamp01(closeness_base + 0.04 + 0.10 * evidence_level)
    engagement_cap = _clamp01(0.60 + 0.10 * evidence_level + 0.05 * companionship_pull)
    repair_cap = _clamp01(0.50 + 0.10 * evidence_level + 0.06 * _clamp01((app or {}).get("repair_load"), 0.0))
    out["trust"] = min(float(out.get("trust", trust_base) or trust_base), trust_cap)
    out["closeness"] = min(float(out.get("closeness", closeness_base) or closeness_base), closeness_cap)
    out["engagement_drive"] = min(float(out.get("engagement_drive", 0.64) or 0.64), engagement_cap)
    out["repair_confidence"] = min(float(out.get("repair_confidence", 0.55) or 0.55), repair_cap)
    return out


def _allostasis_next(
    prev_state: dict[str, Any],
    emotion_state: dict[str, Any],
    bond_state: dict[str, Any],
    user_text: str,
    science_mode: bool,
    appraisal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prev = dict(prev_state or {})
    emotion_label = str((emotion_state or {}).get("label") or "neutral").strip().lower()
    arousal = _clamp01((emotion_state or {}).get("arousal"), 0.35)
    hurt = _clamp01((bond_state or {}).get("hurt"), 0.0)
    irritation = _clamp01((bond_state or {}).get("irritation"), 0.0)
    closeness = _clamp01((bond_state or {}).get("closeness"), 0.5)
    trust = _clamp01((bond_state or {}).get("trust"), 0.5)
    engagement = _clamp01((bond_state or {}).get("engagement_drive"), 0.6)
    competence_trigger = 0.72 if science_mode or _has_any_marker(user_text, STRUCTURE_REQUEST_KEYWORDS | SCIENCE_KEYWORDS) else 0.38

    target = {
        "safety_need": _clamp01(0.20 + 0.45 * hurt + 0.30 * irritation + 0.12 * arousal),
        "closeness_need": _clamp01(0.18 + 0.55 * max(0.0, 1.0 - closeness) + 0.10 * engagement),
        "competence_need": _clamp01(competence_trigger),
        "autonomy_need": _clamp01(0.12 + 0.48 * irritation + (0.16 if emotion_label == "angry" else 0.0)),
        "cognitive_budget": _clamp01(0.88 - 0.35 * arousal - (0.18 if emotion_label == "stress" else 0.0) - (0.06 if science_mode else 0.0), 0.6),
    }

    if emotion_label == "care":
        target["safety_need"] = _clamp01(target["safety_need"] - 0.08)
        target["closeness_need"] = _clamp01(target["closeness_need"] + 0.08)
    elif emotion_label == "stress":
        target["autonomy_need"] = _clamp01(target["autonomy_need"] + (0.08 if science_mode else 0.04))
        target["competence_need"] = _clamp01(max(target["competence_need"], 0.62 if science_mode else target["competence_need"]))
        target["cognitive_budget"] = _clamp01(max(target["cognitive_budget"], 0.44 if science_mode else target["cognitive_budget"]))
    elif emotion_label == "logic":
        target["competence_need"] = _clamp01(max(target["competence_need"], 0.68))
        target["cognitive_budget"] = _clamp01(max(target["cognitive_budget"], 0.52))

    app = _active_appraisal_payload(appraisal)
    signals = app.get("signals") if isinstance(app.get("signals"), dict) else {}
    if app:
        if bool(signals.get("repair")):
            target["safety_need"] = _clamp01(target["safety_need"] - 0.08)
            target["closeness_need"] = _clamp01(target["closeness_need"] + 0.05)
            target["cognitive_budget"] = _clamp01(target["cognitive_budget"] + 0.03)
        if bool(signals.get("care")):
            target["safety_need"] = _clamp01(target["safety_need"] - 0.05)
            target["closeness_need"] = _clamp01(target["closeness_need"] + 0.08)
            target["autonomy_need"] = _clamp01(target["autonomy_need"] - 0.03)
        if bool(signals.get("conflict")):
            target["safety_need"] = _clamp01(target["safety_need"] + 0.10)
            target["autonomy_need"] = _clamp01(target["autonomy_need"] + 0.08)
            target["cognitive_budget"] = _clamp01(target["cognitive_budget"] - 0.05)
        if bool(signals.get("withdrawal")):
            target["autonomy_need"] = _clamp01(target["autonomy_need"] + 0.05)
            target["closeness_need"] = _clamp01(target["closeness_need"] - 0.03)

        deltas = app.get("allostasis_delta") if isinstance(app.get("allostasis_delta"), dict) else {}
        delta_scale = 0.90
        for key in ("safety_need", "closeness_need", "competence_need", "autonomy_need", "cognitive_budget"):
            if key in deltas:
                target[key] = _clamp01(float(target.get(key, 0.0)) + delta_scale * _clamp_signed(deltas.get(key), -0.35, 0.35, 0.0))

    target_weight = _appraisal_target_weight(appraisal, low=0.42, high=0.80) if app else 0.40
    out = {
        "safety_need": _blend_state_value(prev, "safety_need", target["safety_need"], 0.20, target_weight),
        "closeness_need": _blend_state_value(prev, "closeness_need", target["closeness_need"], 0.18, target_weight),
        "competence_need": _blend_state_value(prev, "competence_need", target["competence_need"], competence_trigger, target_weight),
        "autonomy_need": _blend_state_value(prev, "autonomy_need", target["autonomy_need"], 0.12, target_weight),
        "cognitive_budget": _blend_state_value(prev, "cognitive_budget", target["cognitive_budget"], 0.6, target_weight),
    }
    out["relational_security"] = round(_clamp01((trust + closeness) / 2.0 - 0.5 * hurt, 0.5), 3)
    return out


def _behavior_policy_from_state(
    *,
    response_style_hint: str,
    emotion_state: dict[str, Any],
    bond_state: dict[str, Any],
    allostasis_state: dict[str, Any],
    counterpart_assessment: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
    tsundere_intensity: float,
    science_mode: bool,
    user_text: str = "",
) -> dict[str, Any]:
    emotion_label = str((emotion_state or {}).get("label") or "neutral").strip().lower()
    trust = _clamp01((bond_state or {}).get("trust"), 0.5)
    closeness = _clamp01((bond_state or {}).get("closeness"), 0.5)
    hurt = _clamp01((bond_state or {}).get("hurt"), 0.0)
    irritation = _clamp01((bond_state or {}).get("irritation"), 0.0)
    engagement = _clamp01((bond_state or {}).get("engagement_drive"), 0.6)
    safety_need = _clamp01((allostasis_state or {}).get("safety_need"), 0.2)
    autonomy_need = _clamp01((allostasis_state or {}).get("autonomy_need"), 0.2)
    cognitive_budget = _clamp01((allostasis_state or {}).get("cognitive_budget"), 0.7)
    respect_level = _clamp01((counterpart_assessment or {}).get("respect_level"), 0.5)
    reciprocity = _clamp01((counterpart_assessment or {}).get("reciprocity"), 0.5)
    boundary_pressure = _clamp01((counterpart_assessment or {}).get("boundary_pressure"), 0.1)
    reliability_read = _clamp01((counterpart_assessment or {}).get("reliability_read"), 0.5)
    counterpart_stance = str((counterpart_assessment or {}).get("stance") or "").strip().lower()
    narrative_bond = _clamp01((semantic_narrative_profile or {}).get("bond_depth"), 0.0)
    narrative_commitment = _clamp01((semantic_narrative_profile or {}).get("commitment_carry"), 0.0)
    narrative_repair = _clamp01((semantic_narrative_profile or {}).get("repair_residue"), 0.0)
    narrative_tension = _clamp01((semantic_narrative_profile or {}).get("tension_residue"), 0.0)
    narrative_boundary = _clamp01((semantic_narrative_profile or {}).get("boundary_residue"), 0.0)
    narrative_selfhood = _clamp01((semantic_narrative_profile or {}).get("selfhood_integrity"), 0.0)
    narrative_agency = _clamp01((semantic_narrative_profile or {}).get("agency_drive"), 0.0)
    narrative_history = _clamp01((semantic_narrative_profile or {}).get("history_weight"), 0.0)
    soft_reply_window = response_style_hint in {"companion", "casual", "natural"}
    nonrelational_support_request = False
    brief_presence = False
    presence_checkin = False
    hold_presence = False
    playful_memory_request = response_style_hint == "memory_recall" and closeness > 0.56 and narrative_history > 0.16

    warmth = _clamp01(0.30 + 0.35 * closeness + 0.20 * trust - 0.25 * hurt - 0.18 * irritation)
    sharpness = _clamp01(0.18 + 0.42 * _clamp01(tsundere_intensity, 0.55) + 0.24 * irritation)
    initiative = _clamp01(0.20 + 0.50 * engagement + 0.10 * cognitive_budget - 0.16 * autonomy_need)
    disclosure = _clamp01(0.12 + 0.42 * closeness + 0.12 * trust - 0.18 * safety_need)
    reply_length = _clamp01(0.32 + 0.30 * cognitive_budget + (0.16 if science_mode else 0.0) - 0.12 * irritation)
    approach = _clamp01(0.20 + 0.48 * engagement - 0.24 * autonomy_need - 0.18 * hurt)
    tease_bias = _clamp01(0.10 + 0.28 * _clamp01(tsundere_intensity, 0.55) + (0.16 if emotion_label == "tease" else 0.0) - 0.18 * hurt)

    warmth = _clamp01(warmth + 0.08 * (respect_level - 0.5) + 0.06 * (reciprocity - 0.5) - 0.18 * boundary_pressure)
    sharpness = _clamp01(sharpness + 0.12 * boundary_pressure)
    initiative = _clamp01(initiative + 0.08 * (reciprocity - 0.5) - 0.12 * boundary_pressure)
    disclosure = _clamp01(disclosure + 0.08 * (reliability_read - 0.5) - 0.14 * boundary_pressure)
    approach = _clamp01(approach + 0.10 * (respect_level - 0.5) - 0.20 * boundary_pressure)

    warmth = _clamp01(warmth + 0.06 * narrative_bond + 0.02 * narrative_commitment - 0.05 * narrative_tension)
    sharpness = _clamp01(sharpness + 0.04 * narrative_tension + 0.03 * narrative_repair + 0.05 * narrative_boundary + 0.04 * narrative_selfhood)
    initiative = _clamp01(initiative + 0.04 * narrative_commitment + 0.03 * narrative_bond - 0.03 * narrative_tension + 0.07 * narrative_agency)
    disclosure = _clamp01(
        disclosure
        + 0.06 * narrative_bond
        + 0.04 * narrative_commitment
        - 0.05 * narrative_tension
        - 0.03 * narrative_repair
        - 0.05 * narrative_boundary
        + 0.03 * narrative_selfhood
    )
    reply_length = _clamp01(reply_length + 0.03 * narrative_history + 0.04 * narrative_commitment)
    approach = _clamp01(
        approach
        + 0.07 * narrative_bond
        + 0.03 * narrative_commitment
        - 0.08 * narrative_tension
        - 0.04 * narrative_repair
        - 0.06 * narrative_boundary
        + 0.03 * narrative_agency
    )
    tease_bias = _clamp01(tease_bias + 0.03 * narrative_bond - 0.07 * narrative_tension - 0.04 * narrative_repair)
    explicit_support_request = _is_nonrelational_support_request(user_text, science_mode)
    nonrelational_support_request = (
        soft_reply_window
        and not science_mode
        and explicit_support_request
        and approach > 0.40
        and safety_need < 0.52
    )
    brief_presence = (
        soft_reply_window
        and approach > 0.34
        and engagement < 0.60
        and safety_need < 0.48
        and trust > 0.44
    )
    presence_checkin = brief_presence and closeness > 0.50 and hurt < 0.16
    hold_presence = brief_presence and hurt > 0.10 and trust > 0.52 and counterpart_stance != "guarded"

    boundary_assertiveness = _clamp01(0.22 + 0.44 * narrative_boundary + 0.24 * narrative_selfhood + 0.18 * boundary_pressure)
    self_directedness = _clamp01(0.16 + 0.46 * narrative_agency + 0.20 * autonomy_need + 0.10 * narrative_selfhood)
    equality_guard = _clamp01(0.16 + 0.42 * narrative_selfhood + 0.16 * boundary_pressure)

    if counterpart_stance == "guarded":
        warmth = _clamp01(warmth - 0.06)
        sharpness = _clamp01(sharpness + 0.06)
        initiative = _clamp01(initiative - 0.08)
        disclosure = _clamp01(disclosure - 0.10)
        approach = _clamp01(approach - 0.12)
    elif counterpart_stance == "watchful":
        initiative = _clamp01(initiative - 0.04)
        disclosure = _clamp01(disclosure - 0.05)
        approach = _clamp01(approach - 0.05)

    if emotion_label == "care" and trust > 0.68 and closeness > 0.72 and hurt < 0.08:
        tease_bias = _clamp01(tease_bias + 0.08)
        sharpness = _clamp01(sharpness + 0.04)
        disclosure = _clamp01(disclosure + 0.04)

    if response_style_hint == "relationship":
        warmth = _clamp01(warmth + 0.08)
        disclosure = _clamp01(disclosure + 0.10)
    elif response_style_hint == "memory_recall":
        reply_length = _clamp01(reply_length + 0.08)
    elif response_style_hint == "companion":
        warmth = _clamp01(warmth + 0.10)
        initiative = _clamp01(initiative + 0.06)
    elif response_style_hint == "structured":
        reply_length = _clamp01(reply_length + 0.10)
        tease_bias = _clamp01(tease_bias - 0.08)

    if nonrelational_support_request:
        initiative = _clamp01(initiative - 0.14)
        reply_length = _clamp01(reply_length - 0.10)
        disclosure = _clamp01(disclosure - 0.04)
        tease_bias = _clamp01(tease_bias - 0.01)
        sharpness = _clamp01(sharpness + 0.03)
    if brief_presence:
        warmth = _clamp01(warmth + 0.04)
        initiative = _clamp01(initiative - 0.24)
        disclosure = _clamp01(disclosure - 0.14)
        reply_length = _clamp01(reply_length - 0.30)
        approach = _clamp01(max(approach, 0.48))
        tease_bias = _clamp01(tease_bias - 0.10)
        if hold_presence:
            reply_length = _clamp01(max(reply_length, 0.30))
            disclosure = _clamp01(max(disclosure, 0.18))
    if presence_checkin:
        warmth = _clamp01(warmth + 0.03)
        sharpness = _clamp01(sharpness - 0.06)
        tease_bias = _clamp01(tease_bias - 0.14)
        reply_length = _clamp01(max(reply_length, 0.20))
    if playful_memory_request:
        warmth = _clamp01(warmth + 0.05)
        sharpness = _clamp01(sharpness - 0.05)
        initiative = _clamp01(initiative - 0.04)
        disclosure = _clamp01(disclosure + 0.03)
        reply_length = _clamp01(reply_length - 0.06)
        approach = _clamp01(max(approach, 0.54))
        tease_bias = _clamp01(tease_bias + 0.08)
        warmth = _clamp01(warmth + 0.02)

    return {
        "warmth": round(warmth, 3),
        "sharpness": round(sharpness, 3),
        "initiative": round(initiative, 3),
        "disclosure_level": round(disclosure, 3),
        "reply_length_bias": round(reply_length, 3),
        "approach_vs_withdraw": round(approach, 3),
        "humor_or_tease_bias": round(tease_bias, 3),
        "boundary_assertiveness": round(boundary_assertiveness, 3),
        "self_directedness": round(self_directedness, 3),
        "equality_guard": round(equality_guard, 3),
        "history_weight": round(narrative_history, 3),
    }
