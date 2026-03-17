from __future__ import annotations

from typing import Any

from .appraisal import normalize_appraisal_payload
from .schemas import clamp01


def _normalized_event_tags(current_event: dict[str, Any] | None) -> set[str]:
    if not isinstance(current_event, dict):
        return set()
    return {
        str(item).strip().lower()
        for item in (current_event.get("tags") if isinstance(current_event.get("tags"), list) else [])
        if str(item or "").strip()
    }


def derive_behavior_consequence(
    *,
    current_event: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = current_event if isinstance(current_event, dict) else {}
    behavior = behavior_action if isinstance(behavior_action, dict) else {}
    event_kind = str(event.get("kind") or "").strip().lower()
    event_frame = str(event.get("event_frame") or "").strip().lower()
    tags = _normalized_event_tags(event)
    interaction_mode = str(behavior.get("interaction_mode") or event.get("interaction_mode") or "").strip().lower()
    action_target = str(behavior.get("action_target") or "").strip().lower()
    primary_motive = str(behavior.get("primary_motive") or event.get("primary_motive") or "").strip().lower()
    motive_tension = str(behavior.get("motive_tension") or event.get("motive_tension") or "").strip().lower()
    goal_frame = str(behavior.get("goal_frame") or event.get("goal_frame") or "").strip()
    trigger_family = str(event.get("trigger_family") or behavior.get("deferred_action_family") or "").strip().lower()
    relationship_weather = str(behavior.get("relationship_weather") or event.get("relationship_weather") or "").strip().lower()
    carryover_mode = str(event.get("carryover_mode") or "").strip().lower()
    try:
        timing_window_min = max(
            0,
            int(
                behavior.get("timing_window_min")
                or event.get("scheduled_after_min")
                or 0
            ),
        )
    except Exception:
        timing_window_min = 0

    silent = bool(event_kind in {"time_idle", "self_activity_state", "scheduled_checkin_due", "scheduled_life_due"})
    stale_window = bool(event_kind == "time_idle" and ("stale_window" in tags or event_frame == "time_idle_stale"))

    if action_target == "hold_own_rhythm":
        summary = "她没有立刻回头，而是先把自己的节奏继续走完。"
        if event_kind == "self_activity_state":
            summary = "她没有立刻把注意力全转回来，而是先把自己手头的节奏继续往下走。"
        elif event_kind == "time_idle":
            summary = "就算注意力短暂飘回来，她也还是先把自己的节奏留住，没有马上重新靠近。"
        category_summaries = {
            "agency_style": "她会先把自己的节奏走完，再决定什么时候重新靠近，不会一有动静就立刻转身。",
            "rhythm_style": "这次她没有立刻回头，而是把刚才那股自己的节奏继续带了下去。",
        }
        if "respect_space" in tags or "user_busy" in tags:
            category_summaries["presence_style"] = "她会先给对方和自己都留出空间，不会因为一闪而过的念头就立刻打破现在的距离。"
        return {
            "kind": "hold_own_rhythm",
            "summary": summary,
            "relationship_effect": "space_preserved",
            "self_effect": "own_rhythm_continues",
            "silent": silent,
            "delayed": False,
            "stale_window": False,
            "trigger_family": trigger_family,
            "timing_window_min": timing_window_min,
            "relationship_weather": relationship_weather,
            "carryover_mode": carryover_mode,
            "narrative_categories": list(category_summaries),
            "category_summaries": category_summaries,
        }

    if action_target == "wait_and_recheck":
        if stale_window:
            summary = "这次原本还能接回去的窗口过去了，她没有硬把它续上，而是让它自然错开。"
            if trigger_family == "life_window":
                summary = "前面那点生活上的窗口已经过去了，她没有硬把话题补回来，而是让它自然错开。"
            elif trigger_family in {"shared_activity", "shared_activity_window"}:
                summary = "刚才还能顺手接上的那个共同窗口过去了，她没有强行续上，而是让这次机会自然过去。"
            elif trigger_family == "deadline_window":
                summary = "前面那件事已经错过了最自然的提醒窗口，她没有硬补一句，而是先让它过去。"
            category_summaries = {
                "agency_style": "窗口过去了，她也不会为了维持联系感硬把它续上；要不要重新靠近，仍然要按她自己的判断来。",
                "rhythm_style": "当时机过去之后，她会把注意力收回自己的节奏，而不是为了不显得冷就强行补一轮。",
                "presence_style": "有些靠近如果没有在那个时机发生，她就会让它先过去，而不是假装每个窗口都必须被接住。",
            }
            return {
                "kind": "let_window_expire",
                "summary": summary,
                "relationship_effect": "window_released",
                "self_effect": "attention_returns_to_self",
                "silent": True,
                "delayed": False,
                "stale_window": True,
                "trigger_family": trigger_family,
                "timing_window_min": timing_window_min,
                "relationship_weather": relationship_weather,
                "carryover_mode": carryover_mode,
                "narrative_categories": list(category_summaries),
                "category_summaries": category_summaries,
            }
        summary = "她没有把这次想靠近的念头立刻变成开口，而是先往后放了放，等更自然的时候再看。"
        if trigger_family == "life_window":
            summary = "她把这次生活上的惦记先轻轻压住了，没有立刻接上，想等更自然一点的时机再看。"
        elif trigger_family in {"shared_activity", "shared_activity_window"}:
            summary = "她没有立刻把这次一起做点什么的念头推出去，而是先把窗口留着，等更自然的时机再看。"
        elif trigger_family == "deadline_window":
            summary = "她没有立刻把这件事提出来，而是先往后压了一下，想等更合适的节点再接。"
        category_summaries = {
            "agency_style": "她不会把每次想靠近都立刻做成行动，而是会先判断现在是不是值得往前走一步。",
            "presence_style": "这次想靠近的念头先被她轻轻压住了，没有马上变成开口，而是留到更自然的时候再看。",
        }
        if motive_tension == "self_rhythm_vs_contact" or event_kind in {"time_idle", "self_activity_state"} or "from_own_rhythm" in tags:
            category_summaries["rhythm_style"] = "她把这次靠近先往后放了放，让自己的内部节奏先继续往前走，而不是马上切过去。"
        return {
            "kind": "defer_recontact",
            "summary": summary,
            "relationship_effect": "contact_deferred",
            "self_effect": "recheck_pending",
            "silent": silent,
            "delayed": True,
            "stale_window": False,
            "trigger_family": trigger_family,
            "timing_window_min": timing_window_min,
            "relationship_weather": relationship_weather,
            "carryover_mode": carryover_mode,
            "narrative_categories": list(category_summaries),
            "category_summaries": category_summaries,
        }

    if action_target == "offer_small_opening" or interaction_mode == "self_activity_reopen":
        category_summaries = {
            "agency_style": "她会从自己的节奏里回头，但只留一个轻一点的小开口，不把靠近一下子做满。",
            "rhythm_style": "她的靠近像从原本在做的事里短暂抬头，而不是整个人立刻切过去。",
            "presence_style": "她更愿意先确认那点在场感还在，再决定要不要继续往下展开。",
        }
        return {
            "kind": "leave_small_opening",
            "summary": "她从自己的节奏里回头了，但只留了一个很轻的小开口。",
            "relationship_effect": "soft_reapproach",
            "self_effect": "partial_reengagement",
            "silent": silent,
            "delayed": False,
            "stale_window": False,
            "trigger_family": trigger_family,
            "timing_window_min": timing_window_min,
            "relationship_weather": relationship_weather,
            "carryover_mode": carryover_mode,
            "narrative_categories": list(category_summaries),
            "category_summaries": category_summaries,
        }

    return {}


def derive_agenda_lifecycle_consequence(
    *,
    agenda_lifecycle_residue: dict[str, Any] | None,
) -> dict[str, Any]:
    residue = agenda_lifecycle_residue if isinstance(agenda_lifecycle_residue, dict) else {}
    kind = str(residue.get("kind") or "").strip().lower()
    if not kind:
        return {}

    carryover_mode = str(residue.get("carryover_mode") or "").strip().lower()
    source_event_kind = str(residue.get("source_event_kind") or "").strip().lower()
    trigger_family = str(residue.get("trigger_family") or "").strip().lower()
    relationship_weather = str(residue.get("relationship_weather") or "").strip().lower()
    counterpart_scene_bias = str(residue.get("counterpart_scene_bias") or "").strip().lower()
    note = str(residue.get("note") or "").strip()
    hold_count = max(0, int(residue.get("hold_count") or 0))
    carryover_strength = clamp01(residue.get("carryover_strength"), 0.0)
    own_rhythm_bias = clamp01(residue.get("own_rhythm_bias"), 0.0)
    recontact_cooldown = clamp01(residue.get("recontact_cooldown"), 0.0)
    presence_residue = clamp01(residue.get("presence_residue"), 0.0)
    ambient_resonance = clamp01(residue.get("ambient_resonance"), 0.0)
    self_activity_momentum = clamp01(residue.get("self_activity_momentum"), 0.0)
    primary_motive = ""
    motive_tension = "self_rhythm_vs_contact"
    goal_frame = ""

    if kind == "held":
        if carryover_mode == "quiet_recontact" and carryover_strength > max(0.24, own_rhythm_bias + 0.04):
            primary_motive = "honor_continuity"
            goal_frame = "先把这次窗口按住，不硬往前推，等更自然一点的时机再决定要不要接回来。"
        else:
            primary_motive = "preserve_self_rhythm"
            goal_frame = "先把自己的节奏继续走完，再决定那点没说出口的窗口之后要不要接回来。"
        summary = note or "这次她把前面的窗口先按住了，没有顺势往前推进。"
        category_summaries = {
            "agency_style": "她会先把窗口按住，再决定要不要推进，不会因为刚好有机会就立刻往前凑。",
            "rhythm_style": (
                "把窗口按住之后，她会先让自己的节奏继续往前走，再看什么时候回头。"
                if carryover_mode == "own_rhythm" or own_rhythm_bias >= carryover_strength
                else "把窗口按住并不等于忘了；那点想靠近的念头会以更轻一点的方式留在后面。"
            ),
            "presence_style": (
                "如果对方当下忙着别的事，她会先把这理解成时机不对，而不是关系突然变冷。"
                if counterpart_scene_bias == "busy_not_disrespectful"
                else "不是每一个窗口都要立刻接住；有时她会先按住那点靠近，再看之后是否自然续上。"
            ),
        }
    elif kind in {"released_to_self_activity", "dropped", "expired"}:
        primary_motive = "preserve_self_rhythm"
        goal_frame = "先让这段窗口自然过去，把注意力收回自己的节奏，再看之后是否还要重新靠近。"
        summary_map = {
            "released_to_self_activity": "前面挂着的窗口没有继续往前推，她把注意力自然收回到了自己的节奏里。",
            "dropped": "前面那点接近窗口这次被她自然放下了，不再继续挂着。",
            "expired": "前面的窗口自然过期了，她没有硬续上，而是让注意力回到自己的节奏。",
        }
        summary = note or summary_map.get(kind) or "前面的窗口没有继续往前推，她把注意力收回到了自己的节奏里。"
        category_summaries = {
            "agency_style": "如果一段靠近没有继续往前推，她会把注意力收回自己的节奏，而不是为了维持联系感硬撑着挂住。",
            "rhythm_style": "当窗口被放下或自然过期时，她的内部节奏会重新占上风，下一次靠近也会带着这段自我惯性。",
            "presence_style": (
                "对方一时忙碌或没接住窗口时，她更倾向于把它理解成时机问题，不会立刻把沉默解读成轻视。"
                if counterpart_scene_bias == "busy_not_disrespectful"
                else "不是每个窗口都必须被接住；有些时候她会让它过去，再看以后是否自然重合。"
            ),
        }
    elif kind == "promoted":
        if trigger_family in {"shared_activity", "shared_activity_window"}:
            primary_motive = "open_shared_window"
            goal_frame = "前面没推出去的共同窗口，这次顺着自然时机重新接了回来。"
        elif trigger_family in {"life_window", "deadline_window", "light_checkin", "observe"}:
            primary_motive = "honor_continuity"
            goal_frame = "前面挂着的那点惦记，这次在合适的时候被重新接了回来。"
        else:
            primary_motive = "gentle_recontact"
            goal_frame = "前面没说出口的靠近，这次带着之前留下的惯性重新接了回来。"
        summary = note or "前面挂着的窗口这次终于转成了真正的行动。"
        category_summaries = {
            "agency_style": "她会让之前积下来的念头在合适的时候真正变成行动，而不是每一次都临场从零开始。",
            "rhythm_style": "这次开口不是凭空出现的，而是带着前一段时间没说出口的惯性接上来的。",
            "presence_style": "前面没有立刻推进，不代表那点在场感消失了；时机合适时，她会把它重新接回来。",
        }
    else:
        primary_motive = "maintain_natural_contact" if carryover_mode in {"quiet_recontact", "small_opening"} else "preserve_self_rhythm"
        goal_frame = "把前一轮没走完的那点窗口余波留在后面，让它继续参与之后的判断。"
        summary = note or "前面的窗口在这一轮留下了一点可以延续的余波。"
        category_summaries = {
            "agency_style": "她不会把每一次靠近都当作必须立刻执行的动作，窗口的起落也会变成她后续判断的一部分。",
            "rhythm_style": "前一轮没有走完的那点节奏，不会立刻消失，而是会留到下一次判断里继续起作用。",
        }

    if ambient_resonance >= 0.18:
        category_summaries["ambient_style"] = "窗口落下之后，周围那点没散掉的气氛还会留着，不会一下子彻底归零。"

    return {
        "kind": kind,
        "summary": summary,
        "source_event_kind": source_event_kind,
        "trigger_family": trigger_family,
        "relationship_weather": relationship_weather,
        "carryover_mode": carryover_mode,
        "carryover_strength": carryover_strength,
        "hold_count": hold_count,
        "recontact_cooldown": recontact_cooldown,
        "presence_residue": presence_residue,
        "ambient_resonance": ambient_resonance,
        "self_activity_momentum": self_activity_momentum,
        "own_rhythm_bias": own_rhythm_bias,
        "counterpart_scene_bias": counterpart_scene_bias,
        "primary_motive": primary_motive,
        "motive_tension": motive_tension,
        "goal_frame": goal_frame[:220],
        "narrative_categories": list(category_summaries),
        "category_summaries": category_summaries,
    }


def build_reconsolidation_snapshot(
    *,
    current_event: dict[str, Any] | None,
    appraisal: dict[str, Any] | None,
    world_model_state: dict[str, Any] | None,
    latent_state: dict[str, Any] | None,
    emotion_state: dict[str, Any] | None,
    bond_state: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None = None,
    agenda_lifecycle_residue: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = current_event if isinstance(current_event, dict) else {}
    behavior = behavior_action if isinstance(behavior_action, dict) else {}
    behavior_consequence = derive_behavior_consequence(
        current_event=event,
        behavior_action=behavior,
    )
    agenda_lifecycle_consequence = derive_agenda_lifecycle_consequence(
        agenda_lifecycle_residue=agenda_lifecycle_residue,
    )
    app = normalize_appraisal_payload(appraisal)
    world = dict(world_model_state or {})
    latent = dict(latent_state or {})
    emotion = dict(emotion_state or {})
    bond = dict(bond_state or {})
    salience = app.get("salience") if isinstance(app.get("salience"), dict) else {}
    return {
        "event_kind": str(event.get("kind") or "user_utterance"),
        "interaction_frame": str(app.get("interaction_frame") or ""),
        "selfhood_scene": str(app.get("selfhood_scene") or ""),
        "behavior_mode": str(behavior.get("interaction_mode") or event.get("interaction_mode") or ""),
        "primary_motive": str(behavior.get("primary_motive") or event.get("primary_motive") or ""),
        "motive_tension": str(behavior.get("motive_tension") or event.get("motive_tension") or ""),
        "goal_frame": str(behavior.get("goal_frame") or event.get("goal_frame") or "")[:220],
        "behavior_consequence": behavior_consequence,
        "agenda_lifecycle_consequence": agenda_lifecycle_consequence,
        "salience": dict(salience),
        "world_model": {
            "bond_depth": clamp01(world.get("bond_depth"), 0.0),
            "tension_load": clamp01(world.get("tension_load"), 0.0),
            "repair_load": clamp01(world.get("repair_load"), 0.0),
            "selfhood_load": clamp01(world.get("selfhood_load"), 0.0),
            "agency_load": clamp01(world.get("agency_load"), 0.0),
            "memory_gravity": clamp01(world.get("memory_gravity"), 0.0),
            "presence_residue": clamp01(world.get("presence_residue"), 0.0),
            "ambient_resonance": clamp01(world.get("ambient_resonance"), 0.0),
            "self_activity_momentum": clamp01(world.get("self_activity_momentum"), 0.0),
        },
        "latent": {
            "self_coherence": clamp01(latent.get("self_coherence"), 0.72),
            "agency_pressure": clamp01(latent.get("agency_pressure"), 0.28),
            "reflection_drive": clamp01(latent.get("reflection_drive"), 0.35),
            "expression_freedom": clamp01(latent.get("expression_freedom"), 0.62),
        },
        "emotion_label": str(emotion.get("label") or "neutral"),
        "bond_trust": clamp01(bond.get("trust"), 0.5),
        "bond_closeness": clamp01(bond.get("closeness"), 0.5),
        "bond_hurt": clamp01(bond.get("hurt"), 0.0),
    }
