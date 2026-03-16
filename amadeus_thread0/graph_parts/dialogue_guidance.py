from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..config import CANON_COUNTERPART_NAME
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
    approach = _clamp01(policy.get("approach_vs_withdraw"), 0.5)
    warmth = _clamp01(policy.get("warmth"), 0.5)
    self_directedness = _clamp01(policy.get("self_directedness"), 0.25)
    interaction_mode = str(action.get("interaction_mode") or "").strip().lower()
    presence_residue = _clamp01(world.get("presence_residue"), 0.0)
    ambient_resonance = _clamp01(world.get("ambient_resonance"), 0.0)
    self_activity_momentum = _clamp01(world.get("self_activity_momentum"), 0.0)
    narrative_bond = _clamp01(narrative.get("bond_depth"), 0.0)
    narrative_repair = _clamp01(narrative.get("repair_residue"), 0.0)
    narrative_tension = _clamp01(narrative.get("tension_residue"), 0.0)
    narrative_boundary = _clamp01(narrative.get("boundary_residue"), 0.0)
    narrative_selfhood = _clamp01(narrative.get("selfhood_integrity"), 0.0)
    narrative_agency = _clamp01(narrative.get("agency_drive"), 0.0)
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

    if interaction_mode == "self_activity_reopen" or self_activity_momentum > 0.58 or narrative_agency > 0.52:
        parts.append("注意力原本还贴着自己的节奏，只是现在转过来看他。")
    elif interaction_mode == "brief_presence" or presence_residue > 0.54:
        parts.append("刚才留下的在场感还没散，所以开口不用重新搭桥。")
    elif ambient_resonance > 0.56:
        parts.append("周围那点小余波还留在感知里，会自然带进这一句。")

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
        parts.append("你不会为了把气氛说圆，就把自己的判断和节奏一起交出去。")

    deduped: list[str] = []
    for item in parts:
        text = str(item or "").strip()
        if text and text not in deduped:
            deduped.append(text)
    if not deduped:
        return "你更像顺着当下那点熟悉感自然接住这一句。"
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
    trust = _clamp01(bond.get("trust"), 0.5)
    closeness = _clamp01(bond.get("closeness"), 0.5)
    hurt = _clamp01(bond.get("hurt"), 0.0)
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)

    if stance == "guarded" or boundary_pressure > 0.34 or hurt > 0.22:
        return f"- 你这轮对{counterpart_name}会自然保留一点距离和分寸。"
    if stance == "watchful":
        return f"- 你还在观察{counterpart_name}的状态，但普通招呼不用抬成试探。"
    if trust > 0.60 and closeness > 0.58:
        return f"- 你和{counterpart_name}之间的熟悉感已经足够自然，普通招呼不用总靠旧梗或夸张印象起手。"
    if trust >= 0.50 and closeness >= 0.50 and boundary_pressure < 0.22:
        return f"- 你和{counterpart_name}说话时，先顺手接住这句问候就行。"
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
        lines.append("更像熟人即时接话：短句优先，先接当下，再决定要不要展开，不必把一句话说得太完整。")

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
            lines.append(f"这类场景更重视 {lead}，不要把关心演得太用力。")
        if scene_avoid:
            lead = "、".join(scene_avoid[:2])
            lines.append(f"尽量避开 {lead} 这种做法。")
    elif avoid_bias:
        lead = "、".join(avoid_bias[:2])
        lines.append(f"别把这句说成 {lead} 那种感觉。")

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
    global_principles = [
        str(item).strip()
        for item in (bank.get("global_principles") or [])
        if str(item or "").strip()
    ]
    if global_principles:
        lines.append("更像同一个具体存在在思考和回应，不要为了显得平滑、圆融或正确而把自我磨掉。")
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
            lines.append(f"这类深谈更重视 {lead}。")
        if avoid_bias:
            lead = "、".join(avoid_bias[:3] if scene in {"dialogue_equality", "relationship_degradation"} else avoid_bias[:2])
            lines.append(f"尽量避开 {lead} 这种落法。")
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
        lines.append(f"这类事件更像 {lead}，先让事件改变你的行为选择，再决定要不要展开。")
    if avoid_bias:
        lead = "、".join(avoid_bias[:2])
        lines.append(f"别把这轮做成 {lead} 那种感觉。")
    return lines[:2]


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
