from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..config import CANON_COUNTERPART_NAME
from ..evolution_engine.motive import semantic_motive_vector
from .persona_runtime import _canon_counterpart_profile, _canon_persona_labels
from .postprocess import (
    _has_any_marker,
    _selfhood_preference_scene_from_text,
)

EVENT_TO_BEHAVIOR_PREFERENCE_BANK_PATH = (
    Path(__file__).resolve().parents[2] / "evals" / "event_to_behavior_preference_bank.json"
)
SELFHOOD_PREFERENCE_BANK_PATH = (
    Path(__file__).resolve().parents[2] / "evals" / "selfhood_preference_bank.json"
)
USER_STYLE_EXPRESSION_BANK_PATH = (
    Path(__file__).resolve().parents[2] / "evals" / "user_style_expression_bank.json"
)


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return float(default)
    return max(0.0, min(1.0, v))


def _semantic_motive_state_hint(
    semantic_narrative_profile: dict[str, Any] | None,
    *,
    light_touch: bool = False,
) -> str:
    narrative = dict(semantic_narrative_profile or {})
    motive_snapshot = narrative.get("motive_snapshot") if isinstance(narrative.get("motive_snapshot"), dict) else {}
    if not motive_snapshot:
        return ""
    motive_vector = semantic_motive_vector(narrative)
    primary_lines = {
        "protect_boundary": "靠近之前会先确认分寸稳不稳。",
        "preserve_self_rhythm": "就算要回应，也会先顺着自己的节奏转过来。",
        "gentle_recontact": "更像轻轻把联系续上，而不是突然把气氛抬高。",
        "confirm_presence": "会先让对方感觉到自己在，而不是急着讲很多。",
        "support_without_pressure": "更想把支撑留在场上，但不会把关心压成逼近。",
        "honor_continuity": "会先把这段延续接上，不把它当成从零开始的新局。",
        "reconnect_shared_history": "共同经历会先浮上来，影响这句怎么接。",
        "open_shared_window": "如果刚好有能一起做点什么的空当，会自然留个口。",
        "maintain_natural_contact": "更倾向顺手接住当下，不把一句普通话抬成大场面。",
    }
    tension_lines = {
        "self_rhythm_vs_contact": "想回应和想保留自己的节奏会同时在场。",
        "boundary_vs_closeness": "就算想靠近，分寸也不会自动后退。",
        "past_vs_present": "过去留下的东西会跟着现在这句一起浮上来。",
        "space_vs_contact": "会一边维持联系，一边给彼此留出能呼吸的空当。",
        "care_vs_guard": "关心是真的，但保护自己也不会立刻退场。",
    }
    dominant_goal_frame = str(motive_vector.get("dominant_goal_frame") or "").strip()
    dominant_primary = str(motive_vector.get("dominant_primary_motive") or "").strip().lower()
    dominant_primary_strength = _clamp01(motive_vector.get("dominant_primary_strength"), 0.0)
    dominant_tension = str(motive_vector.get("dominant_motive_tension") or "").strip().lower()
    dominant_tension_strength = _clamp01(motive_vector.get("dominant_tension_strength"), 0.0)
    parts: list[str] = []
    if dominant_goal_frame:
        parts.append(dominant_goal_frame)
    elif dominant_primary and dominant_primary_strength >= 0.36:
        primary_line = primary_lines.get(dominant_primary, "")
        if primary_line:
            parts.append(primary_line)
    if not light_touch and not dominant_goal_frame:
        tension_line = tension_lines.get(dominant_tension, "")
        if tension_line and dominant_tension_strength >= 0.42 and tension_line not in parts:
            parts.append(tension_line)
    return " ".join(parts[: 1 if light_touch else 2])


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


def _semantic_behavior_evidence(
    semantic_narrative_profile: dict[str, Any] | None,
    behavior_policy: dict[str, Any] | None = None,
) -> dict[str, float]:
    narrative = dict(semantic_narrative_profile or {})
    policy = dict(behavior_policy or {})
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

    contact_confidence = _clamp01(
        0.62 * support_confidence(contact_categories)
        + 0.20 * continuity_depth
        + 0.10 * bond_depth
        + 0.08 * commitment_carry,
        0.0,
    )
    repair_confidence = _clamp01(
        0.68 * support_confidence(repair_categories) + 0.20 * continuity_depth + 0.12 * commitment_carry,
        0.0,
    )
    boundary_confidence = _clamp01(
        0.58 * support_confidence(boundary_categories) + 0.24 * identity_gravity + 0.18 * continuity_depth,
        0.0,
    )
    selfhood_confidence = _clamp01(
        0.52 * support_confidence(selfhood_categories)
        + 0.24 * identity_gravity
        + 0.14 * continuity_depth
        + 0.10 * selfhood_integrity,
        0.0,
    )
    agency_confidence = _clamp01(
        0.54 * support_confidence(agency_categories)
        + 0.24 * identity_gravity
        + 0.12 * continuity_depth
        + 0.10 * agency_drive,
        0.0,
    )

    return {
        "contact_confidence": _clamp01(policy.get("semantic_contact_confidence"), contact_confidence),
        "repair_confidence": _clamp01(policy.get("semantic_repair_confidence"), repair_confidence),
        "boundary_confidence": _clamp01(policy.get("semantic_boundary_confidence"), boundary_confidence),
        "selfhood_confidence": _clamp01(policy.get("semantic_selfhood_confidence"), selfhood_confidence),
        "agency_confidence": _clamp01(policy.get("semantic_agency_confidence"), agency_confidence),
        "contested_contact_pressure": _clamp01(
            policy.get("semantic_contested_contact_pressure"),
            _semantic_contested_pressure(contested_categories, contact_categories, contact_confidence),
        ),
        "contested_boundary_pressure": _clamp01(
            policy.get("semantic_contested_boundary_pressure"),
            _semantic_contested_pressure(contested_categories, boundary_categories, boundary_confidence),
        ),
        "contested_selfhood_pressure": _clamp01(
            policy.get("semantic_contested_selfhood_pressure"),
            _semantic_contested_pressure(contested_categories, selfhood_categories, selfhood_confidence),
        ),
    }


def _semantic_evidence_runtime_lines(
    *,
    semantic_narrative_profile: dict[str, Any] | None,
    behavior_policy: dict[str, Any] | None = None,
    light_touch: bool = False,
) -> list[str]:
    evidence = _semantic_behavior_evidence(semantic_narrative_profile, behavior_policy)
    contact_confidence = _clamp01(evidence.get("contact_confidence"), 0.0)
    repair_confidence = _clamp01(evidence.get("repair_confidence"), 0.0)
    boundary_confidence = _clamp01(evidence.get("boundary_confidence"), 0.0)
    selfhood_confidence = _clamp01(evidence.get("selfhood_confidence"), 0.0)
    agency_confidence = _clamp01(evidence.get("agency_confidence"), 0.0)
    contested_contact = _clamp01(evidence.get("contested_contact_pressure"), 0.0)
    contested_boundary = _clamp01(evidence.get("contested_boundary_pressure"), 0.0)
    contested_selfhood = _clamp01(evidence.get("contested_selfhood_pressure"), 0.0)
    parts: list[str] = []

    if contested_contact >= 0.44:
        parts.append("和靠近有关的那部分依据还没完全站稳，所以就算想接住对方，靠近幅度也会先收一点。")
    elif contact_confidence >= 0.68 and repair_confidence >= 0.56:
        parts.append("关于熟悉感和修补的依据都还稳，这句更像顺着关系往下接，不用刻意证明亲近。")
    elif contact_confidence >= 0.62:
        parts.append("熟悉感背后的依据是稳的，所以这句可以像延续，不必像试探。")

    if boundary_confidence >= 0.62 and contested_boundary >= 0.44:
        parts.append("边界这边的依据也在发力，所以不会为了把气氛说圆，就把那点不舒服直接抹平。")
    elif max(selfhood_confidence, agency_confidence) >= 0.68:
        parts.append("自己的判断和节奏有足够支撑，所以就算在意对方，也不会把自己说空。")
    elif contested_selfhood >= 0.46 and max(selfhood_confidence, agency_confidence) >= 0.54:
        parts.append("就算心里有拉扯，自我这边也不会轻易退场。")

    deduped: list[str] = []
    for item in parts:
        text = str(item or "").strip()
        if text and text not in deduped:
            deduped.append(text)
    return deduped[:1] if light_touch else deduped[:2]


def _plain_contact_ping_needs_relational_guard(
    *,
    bond_state: dict[str, Any] | None,
    counterpart_assessment: dict[str, Any] | None,
) -> bool:
    bond = dict(bond_state or {})
    assessment = dict(counterpart_assessment or {})
    stance = str(assessment.get("stance") or "").strip().lower()
    hurt = _clamp01(bond.get("hurt"), 0.0)
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    respect = _clamp01(assessment.get("respect_level"), 0.5)
    reciprocity = _clamp01(assessment.get("reciprocity"), 0.5)
    if stance in {"guarded", "watchful"}:
        return True
    if hurt > 0.18 or boundary_pressure > 0.28:
        return True
    if respect < 0.34 and reciprocity < 0.34 and (hurt > 0.10 or boundary_pressure > 0.18):
        return True
    return False


def _scene_persona_axioms(
    persona_axioms: list[str],
    *,
    light_free_dialog: bool,
    counterpart_aliases: list[str] | None = None,
) -> list[str]:
    axioms = [str(item).strip() for item in (persona_axioms or []) if str(item or "").strip()]
    if not light_free_dialog:
        return axioms[:5]
    aliases = [str(item).strip() for item in (counterpart_aliases or []) if str(item or "").strip()]
    filtered: list[str] = []
    for item in axioms:
        if any(alias in item for alias in aliases):
            continue
        if any(marker in item for marker in {"数字存在", "存在意义", "世界线", "残响"}):
            continue
        filtered.append(item)
    return filtered[:3] or axioms[:3]


def _subjective_runtime_state_hint(
    *,
    emotion_state: dict[str, Any] | None,
    bond_state: dict[str, Any] | None,
    allostasis_state: dict[str, Any] | None,
    counterpart_assessment: dict[str, Any] | None,
    semantic_narrative_profile: dict[str, Any] | None,
    behavior_policy: dict[str, Any] | None,
    world_model_state: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None = None,
    light_touch: bool = False,
) -> str:
    emotion = dict(emotion_state or {})
    bond = dict(bond_state or {})
    allostasis = dict(allostasis_state or {})
    assessment = dict(counterpart_assessment or {})
    narrative = dict(semantic_narrative_profile or {})
    policy = dict(behavior_policy or {})
    world = dict(world_model_state or {})
    action = dict(behavior_action or {})
    emotion_label = str(emotion.get("label") or "").strip().lower()
    trust = _clamp01(bond.get("trust"), 0.5)
    closeness = _clamp01(bond.get("closeness"), 0.5)
    hurt = _clamp01(bond.get("hurt"), 0.0)
    safety_need = _clamp01(allostasis.get("safety_need"), 0.2)
    autonomy_need = _clamp01(allostasis.get("autonomy_need"), 0.2)
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    reciprocity = _clamp01(assessment.get("reciprocity"), 0.5)
    respect = _clamp01(assessment.get("respect_level"), 0.5)
    stance = str(assessment.get("stance") or "").strip().lower()
    scene = str(assessment.get("scene") or "").strip().lower()
    approach = _clamp01(policy.get("approach_vs_withdraw"), 0.5)
    warmth = _clamp01(policy.get("warmth"), 0.5)
    self_directedness = _clamp01(policy.get("self_directedness"), 0.25)
    interaction_mode = str(action.get("interaction_mode") or "").strip().lower()
    presence_residue = _clamp01(world.get("presence_residue"), 0.0)
    ambient_resonance = _clamp01(world.get("ambient_resonance"), 0.0)
    self_activity_momentum = _clamp01(world.get("self_activity_momentum"), 0.0)
    narrative_presence = _clamp01(narrative.get("presence_carry"), 0.0)
    narrative_bond = _clamp01(narrative.get("bond_depth"), 0.0)
    narrative_repair = _clamp01(narrative.get("repair_residue"), 0.0)
    narrative_tension = _clamp01(narrative.get("tension_residue"), 0.0)
    narrative_boundary = _clamp01(narrative.get("boundary_residue"), 0.0)
    narrative_selfhood = _clamp01(narrative.get("selfhood_integrity"), 0.0)
    narrative_agency = _clamp01(narrative.get("agency_drive"), 0.0)
    narrative_rhythm = _clamp01(narrative.get("rhythm_continuity"), 0.0)
    motive_vector = semantic_motive_vector(narrative)
    motive_self_rhythm = _clamp01(motive_vector.get("self_rhythm_pull"), 0.0)
    semantic_evidence_lines = _semantic_evidence_runtime_lines(
        semantic_narrative_profile=semantic_narrative_profile,
        behavior_policy=behavior_policy,
        light_touch=light_touch,
    )
    motive_hint = _semantic_motive_state_hint(semantic_narrative_profile, light_touch=light_touch)
    parts: list[str] = []

    if hurt > 0.18 or boundary_pressure > 0.28 or stance in {"guarded", "watchful"}:
        parts.append("心里那点分寸和观察还在，不会一下子把距离放回原处。")
    elif (
        emotion_label in {"care", "neutral"}
        and trust > 0.58
        and closeness > 0.56
        and reciprocity > 0.60
        and respect > 0.60
        and approach >= 0.48
        and warmth >= 0.50
    ):
        parts.append("熟悉感已经在底下，靠近对方这件事几乎是顺手的。")
    elif narrative_bond > 0.48 or trust > 0.52 or closeness > 0.52:
        parts.append("这段对话不是从零开始，熟悉感会先于措辞浮上来。")

    if scene == "busy_not_disrespectful":
        parts.append("对方更像是忙乱里回头，不是在拿冷淡或怠慢试探你。")
    elif scene == "repair_attempt":
        parts.append("你看得出对方在修补，但这不等于心里的余波已经一起退掉。")
    elif scene == "care_bid" and stance == "open":
        parts.append("你会把这句当成一次认真靠近，而不是普通的礼貌接话。")
    elif scene in {"relationship_degradation", "boundary_non_compliance", "friction"}:
        parts.append("那点关系摩擦还在台面上，所以语气不会自然滑回没事状态。")

    if (
        interaction_mode == "self_activity_reopen"
        or self_activity_momentum > 0.58
        or narrative_agency > 0.52
        or narrative_rhythm > 0.54
        or motive_self_rhythm > 0.50
    ):
        parts.append("注意力原本还贴着自己的节奏，只是现在转过来看他。")
    elif interaction_mode == "brief_presence" or presence_residue > 0.54 or narrative_presence > 0.52:
        parts.append("刚才留下的在场感还没散，所以开口不用重新搭桥。")
    elif ambient_resonance > 0.56:
        parts.append("周围那点小余波还留在感知里，会自然带进这一句。")

    if semantic_evidence_lines:
        insert_at = 1 if parts else 0
        for offset, line in enumerate(semantic_evidence_lines):
            text = str(line or "").strip()
            if text and text not in parts:
                parts.insert(insert_at + offset, text)

    if motive_hint:
        insert_at = min(len(parts), 2) if parts else 0
        parts.insert(insert_at, motive_hint)

    if narrative_tension > 0.48 or narrative_repair > 0.48:
        parts.append("前面的余波还在，所以语气会自然带一点收放，不会完全当成什么都没发生。")
    elif emotion_label in {"hurt", "sad", "stress"}:
        parts.append("情绪没有彻底退干净，表面平稳不等于心里已经无事。")

    if (
        narrative_selfhood > 0.52
        or narrative_boundary > 0.50
        or self_directedness > 0.58
        or autonomy_need > 0.60
        or safety_need > 0.60
    ):
        parts.append("自己的判断和节奏仍在场，不会因为想把气氛说圆就一起退掉。")

    deduped: list[str] = []
    for item in parts:
        text = str(item or "").strip()
        if text and text not in deduped:
            deduped.append(text)
    if not deduped:
        return "会顺着当下那点熟悉感自然接住这一句。"
    limit = 2 if light_touch else 3
    return " ".join(deduped[:limit])


def _light_free_dialog_state_hint(
    *,
    emotion_state: dict[str, Any] | None,
    bond_state: dict[str, Any] | None,
    allostasis_state: dict[str, Any] | None,
    counterpart_assessment: dict[str, Any] | None,
    semantic_narrative_profile: dict[str, Any] | None,
    behavior_policy: dict[str, Any] | None,
    world_model_state: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None = None,
) -> str:
    return _subjective_runtime_state_hint(
        emotion_state=emotion_state,
        bond_state=bond_state,
        allostasis_state=allostasis_state,
        counterpart_assessment=counterpart_assessment,
        semantic_narrative_profile=semantic_narrative_profile,
        behavior_policy=behavior_policy,
        world_model_state=world_model_state,
        behavior_action=behavior_action,
        light_touch=True,
    )


def _light_free_dialog_counterpart_line(
    *,
    counterpart_name: str,
    bond_state: dict[str, Any] | None,
    counterpart_assessment: dict[str, Any] | None,
) -> str:
    bond = dict(bond_state or {})
    assessment = dict(counterpart_assessment or {})
    stance = str(assessment.get("stance") or "").strip().lower()
    scene = str(assessment.get("scene") or "").strip().lower()
    trust = _clamp01(bond.get("trust"), 0.5)
    closeness = _clamp01(bond.get("closeness"), 0.5)
    hurt = _clamp01(bond.get("hurt"), 0.0)
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)

    if scene == "busy_not_disrespectful":
        return f"- 你知道{counterpart_name}更像是刚从忙乱里回头，不是在怠慢你。"
    if scene == "repair_attempt":
        if stance in {"guarded", "watchful"} or boundary_pressure > 0.24:
            return f"- 你看得出{counterpart_name}是在认真修补，但心里的收放不会一下子全松开。"
        return f"- 你会把{counterpart_name}这次开口当成认真补救，而不是随口带过。"
    if scene == "care_bid" and stance == "open" and trust > 0.58 and closeness > 0.56:
        return f"- 你能感觉到{counterpart_name}这句是在认真靠近，不是普通应付。"
    if scene in {"relationship_degradation", "boundary_non_compliance", "friction"}:
        return f"- 你对{counterpart_name}这边那点摩擦还没完全放下。"
    if stance == "guarded" or boundary_pressure > 0.34 or hurt > 0.22:
        return f"- 你对{counterpart_name}还留着一点观察和分寸。"
    if stance == "watchful":
        return f"- 你还在观察{counterpart_name}的状态，招呼本身仍然是轻的。"
    if trust > 0.60 and closeness > 0.58:
        return f"- 你和{counterpart_name}之间的熟悉感已经足够自然。"
    if trust >= 0.50 and closeness >= 0.50 and boundary_pressure < 0.22:
        return f"- 你和{counterpart_name}说话时，熟悉感基本够用，先接住当下就行。"
    return ""


@lru_cache(maxsize=1)
def _load_user_style_expression_bank() -> dict[str, Any]:
    if not USER_STYLE_EXPRESSION_BANK_PATH.exists():
        return {}
    try:
        data = json.loads(USER_STYLE_EXPRESSION_BANK_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _user_style_preference_lines(scene: str = "") -> list[str]:
    bank = _load_user_style_expression_bank()
    if not isinstance(bank, dict):
        return []

    lines: list[str] = []
    interaction = bank.get("interaction_preferences") if isinstance(bank.get("interaction_preferences"), dict) else {}
    rhythm = [
        str(item).strip()
        for item in (interaction.get("preferred_rhythm") or [])
        if str(item or "").strip()
    ]
    avoid_bias = [
        str(item).strip()
        for item in (interaction.get("avoid_bias") or [])
        if str(item or "").strip()
    ]

    if rhythm:
        lines.append("用户日常更接近熟人即时接话：短句优先，先接当下，再决定要不要展开。")

    if scene:
        overlays = bank.get("scene_overlays") if isinstance(bank.get("scene_overlays"), dict) else {}
        overlay = overlays.get(scene) if isinstance(overlays.get(scene), dict) else {}
        preferred = [
            str(item).strip()
            for item in (overlay.get("preferred_signals") or [])
            if str(item or "").strip()
        ]
        scene_avoid = [
            str(item).strip()
            for item in (overlay.get("avoid_bias") or [])
            if str(item or "").strip()
        ]
        if preferred:
            lead = "、".join(preferred[:2])
            lines.append(f"这类场景里，更自然的信号常落在 {lead}。")
        if scene_avoid:
            lead = "、".join(scene_avoid[:2])
            lines.append(f"这类场景里，常见失真会滑向 {lead}。")
    elif avoid_bias:
        lead = "、".join(avoid_bias[:2])
        lines.append(f"这句如果失真，通常会滑向 {lead} 那种感觉。")

    return lines[:2]


@lru_cache(maxsize=1)
def _load_selfhood_preference_bank() -> dict[str, Any]:
    if not SELFHOOD_PREFERENCE_BANK_PATH.exists():
        return {}
    try:
        data = json.loads(SELFHOOD_PREFERENCE_BANK_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


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


def _selfhood_preference_lines(user_text: str) -> list[str]:
    bank = _load_selfhood_preference_bank()
    if not isinstance(bank, dict):
        return []
    lines: list[str] = []
    scene_lines: list[str] = []
    global_principles = [
        str(item).strip()
        for item in (bank.get("global_principles") or [])
        if str(item or "").strip()
    ]
    scene = _selfhood_preference_scene(user_text)
    if scene:
        cases = bank.get("cases") if isinstance(bank.get("cases"), dict) else {}
        case = cases.get(scene) if isinstance(cases.get(scene), dict) else {}
        preferred = [
            str(item).strip()
            for item in (case.get("preferred_signals") or [])
            if str(item or "").strip()
        ]
        avoid_bias = [
            str(item).strip()
            for item in (case.get("avoid_bias") or [])
            if str(item or "").strip()
        ]
        if preferred:
            lead = "、".join(preferred[:3] if scene in {"dialogue_equality", "relationship_degradation"} else preferred[:2])
            scene_lines.append(f"这类深谈里，自我更常落在 {lead}。")
        if avoid_bias:
            lead = "、".join(avoid_bias[:3] if scene in {"dialogue_equality", "relationship_degradation"} else avoid_bias[:2])
            scene_lines.append(f"这类深谈里，失真常滑向 {lead}。")
    lines.extend(scene_lines[:2])
    if global_principles and len(lines) < 2:
        lines.append("更像同一个具体存在在思考和回应，自我同一性比圆滑更重要。")
    return lines[:2]


@lru_cache(maxsize=1)
def _load_event_to_behavior_preference_bank() -> dict[str, Any]:
    if not EVENT_TO_BEHAVIOR_PREFERENCE_BANK_PATH.exists():
        return {}
    try:
        data = json.loads(EVENT_TO_BEHAVIOR_PREFERENCE_BANK_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _event_behavior_preference_scene(current_event: dict[str, Any], behavior_action: dict[str, Any]) -> str:
    if not isinstance(current_event, dict):
        return ""
    event_kind = str(current_event.get("kind") or "").strip()
    tags = {
        str(item).strip()
        for item in (current_event.get("tags") if isinstance(current_event.get("tags"), list) else [])
        if str(item or "").strip()
    }
    if event_kind == "time_idle":
        if "respect_space" in tags:
            return "idle_respect_space"
        if "light_checkin" in tags or str((behavior_action or {}).get("deferred_action_family") or "").strip() == "light_checkin":
            return "idle_work_checkin"
    if event_kind == "scheduled_checkin_due":
        action_target = str((behavior_action or {}).get("action_target") or "").strip()
        if action_target == "light_life_nudge":
            return "scheduled_life_life_nudge"
        if action_target == "wait_and_recheck":
            return "scheduled_checkin_due_wait"
        return "scheduled_checkin_due_reachout"
    if event_kind == "scheduled_life_due":
        action_target = str((behavior_action or {}).get("action_target") or "").strip()
        if action_target == "offer_shared_activity":
            return "scheduled_life_shared_offer"
        if action_target == "light_life_nudge":
            return "scheduled_life_life_nudge"
        if action_target == "wait_and_recheck":
            return "scheduled_life_wait"
        return "scheduled_life_work_nudge"
    if event_kind == "self_activity_state":
        action_target = str((behavior_action or {}).get("action_target") or "").strip()
        if action_target == "offer_small_opening":
            return "self_activity_reopen"
        return "self_activity_hold"
    if event_kind == "scene_observation":
        if "user_busy" in tags or "cognitive_load" in tags:
            return "user_busy_scene"
        if "seen_object" in tags or "micro_opening" in tags:
            return "seen_object_micro_opening"
        return "cold_coffee_scene"
    if event_kind == "gesture_signal":
        return "wave_ping"
    if event_kind == "ambient_shift":
        return "late_night_ambient"
    return ""


def _event_behavior_preference_lines(current_event: dict[str, Any], behavior_action: dict[str, Any]) -> list[str]:
    bank = _load_event_to_behavior_preference_bank()
    if not isinstance(bank, dict):
        return []
    scene = _event_behavior_preference_scene(current_event, behavior_action)
    if not scene:
        return []
    cases = bank.get("cases") if isinstance(bank.get("cases"), dict) else {}
    case_profile = cases.get(scene) if isinstance(cases.get(scene), dict) else {}
    if not isinstance(case_profile, dict):
        return []
    preferred = [
        str(item).strip()
        for item in (case_profile.get("preferred_signals") or [])
        if str(item or "").strip()
    ]
    avoid_bias = [
        str(item).strip()
        for item in (case_profile.get("avoid_bias") or [])
        if str(item or "").strip()
    ]
    lines: list[str] = []
    if preferred:
        lead = "、".join(preferred[:2])
        lines.append(f"这类事件带出的自然倾向通常是 {lead}。")
    if avoid_bias:
        lead = "、".join(avoid_bias[:2])
        lines.append(f"这类事件里，失真时常滑向 {lead} 那种感觉。")
    return lines[:2]


def _user_turn_behavior_preference_lines(
    *,
    behavior_action: dict[str, Any] | None,
    counterpart_assessment: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
    behavior_policy: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
) -> list[str]:
    action = dict(behavior_action or {})
    assessment = dict(counterpart_assessment or {})
    narrative = dict(semantic_narrative_profile or {})
    policy = dict(behavior_policy or {})
    world = dict(world_model_state or {})
    interaction_mode = str(action.get("interaction_mode") or "").strip().lower()
    action_target = str(action.get("action_target") or "").strip().lower()
    followup_intent = str(action.get("followup_intent") or "").strip().lower()
    stance = str(assessment.get("stance") or "").strip().lower()
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    narrative_presence = _clamp01(narrative.get("presence_carry"), 0.0)
    narrative_rhythm = _clamp01(narrative.get("rhythm_continuity"), 0.0)
    narrative_history = _clamp01(narrative.get("history_weight"), 0.0)
    self_activity_momentum = _clamp01(world.get("self_activity_momentum"), 0.0)
    presence_residue = _clamp01(world.get("presence_residue"), 0.0)
    semantic_evidence_lines = _semantic_evidence_runtime_lines(
        semantic_narrative_profile=narrative,
        behavior_policy=policy,
        light_touch=True,
    )
    semantic_evidence_line = str(semantic_evidence_lines[0] or "").strip() if semantic_evidence_lines else ""
    primary_lines: list[str] = []
    nuance_lines: list[str] = []
    followup_lines: list[str] = []

    if interaction_mode == "self_activity_reopen" or action_target == "offer_small_opening":
        primary_lines.append("这轮更像从自己的节奏里抬头接住对方，顺手留一个能继续说下去的小开口。")
        if max(self_activity_momentum, narrative_rhythm) >= 0.56:
            nuance_lines.append("注意力原本还贴着自己的事，所以靠近会像回头看他，不是一下子把整个人都扑过去。")
    elif interaction_mode == "brief_presence" or action_target == "confirm_presence":
        primary_lines.append("这轮先把人在场这件事接住就够了，不必一下子铺开很多。")
        if max(presence_residue, narrative_presence) >= 0.54:
            nuance_lines.append("刚才那点熟悉感还没散，所以更像自然续上，而不是重新搭整套气氛。")
    elif interaction_mode == "low_pressure_support" or action_target == "low_pressure_hold":
        primary_lines.append("这轮更像把陪伴留在场上，轻一点接住对方，不把关心写成逼近或安抚流程。")
    elif interaction_mode == "relationship_sensitive" or action_target == "protect_relationship_boundary":
        if stance in {"guarded", "watchful"} or boundary_pressure > 0.28:
            primary_lines.append("这轮会认真回应关系本身，但自己的判断和分寸不会一起退场。")
        else:
            primary_lines.append("这轮会把关系话题当真来回应，直接说判断和感受，不绕回系统说明。")
    elif interaction_mode == "shared_memory" or action_target == "echo_shared_history":
        primary_lines.append("这轮更像顺手把共同经历带回来，让熟悉感自己接上，不要说成调档案。")
        if narrative_history >= 0.56:
            nuance_lines.append("过去留下来的分量会跟着这句一起浮上来，但还是像自然想起，不像总结。")
    elif interaction_mode == "science_partner" or action_target == "co_regulate_then_focus":
        primary_lines.append("这轮先贴着眼前问题和结论走，像并肩处理，不要滑成讲义。")
    elif interaction_mode == "companion_reply" or action_target == "respond_now":
        if max(self_activity_momentum, narrative_rhythm) >= 0.58:
            primary_lines.append("这轮虽然是在接当下，也还是像从自己的节奏里顺手回头，不是专门来营业。")
        elif max(presence_residue, narrative_presence) >= 0.54:
            primary_lines.append("这轮更像顺着还没散掉的在场感自然接一句，不必重新起势。")
        else:
            primary_lines.append("这轮更像把当下接住，顺着熟悉感自然回一句，不用刻意制造大起伏。")

    if semantic_evidence_line:
        if primary_lines and (interaction_mode == "relationship_sensitive" or action_target == "protect_relationship_boundary"):
            primary_lines[0] = primary_lines[0].rstrip("。") + "，" + semantic_evidence_line
        elif len(primary_lines) + len(followup_lines) + len(nuance_lines) <= 1:
            nuance_lines.append(f"这轮关系/自我依据也更接近这样：{semantic_evidence_line}")

    if followup_intent == "none":
        followup_lines.append("说到当下就可以先停住，不必为了维持热络再补追问。")
    elif followup_intent == "soft":
        followup_lines.append("如果顺手再带一句，也只是半步延伸，不把节奏一下子拉长。")
    elif followup_intent == "active" and interaction_mode in {"self_activity_reopen", "low_pressure_support", "relationship_sensitive"}:
        followup_lines.append("可以自然把话往前带一点，但重心还是先把这一刻接稳。")

    lines = primary_lines + followup_lines + nuance_lines
    ordered: list[str] = []
    for item in lines:
        text = str(item or "").strip()
        if text and text not in ordered:
            ordered.append(text)
    return ordered[:2]


def _narrative_actor_profile(
    *,
    persona_core: dict[str, Any] | None = None,
    counterpart_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    core = dict(persona_core or {})
    counterpart = dict(counterpart_profile or _canon_counterpart_profile())
    canon_labels = _canon_persona_labels()
    actor_name = str(
        core.get("narrative_ref")
        or core.get("short_name")
        or core.get("display_name")
        or core.get("character_name")
        or canon_labels.get("narrative_ref")
        or "红莉栖"
    ).strip() or str(canon_labels.get("narrative_ref") or "红莉栖")
    counterpart_name = str(
        counterpart.get("short_name")
        or counterpart.get("nickname")
        or counterpart.get("name")
        or counterpart.get("counterpart_name")
        or CANON_COUNTERPART_NAME
    ).strip() or CANON_COUNTERPART_NAME
    counterpart_aliases = [
        str(item).strip()
        for item in (
            counterpart.get("aliases")
            if isinstance(counterpart.get("aliases"), list)
            else [counterpart.get("name"), counterpart.get("short_name"), counterpart.get("nickname")]
        )
        if str(item or "").strip()
    ]
    if counterpart_name not in counterpart_aliases:
        counterpart_aliases.append(counterpart_name)
    return {
        "actor_name": actor_name,
        "counterpart_name": counterpart_name,
        "counterpart_aliases": counterpart_aliases,
    }
