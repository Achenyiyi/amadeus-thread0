from __future__ import annotations

import json
from typing import Any

from .behavior_runtime import _compact_behavior_action_hint
from .generation_profile import _clamp01, _effective_relationship_weather
from .prompt_helpers import _compact_long_horizon_continuity_hint, _relationship_weather_phrase

def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

def _compact_behavior_hint(policy: dict[str, Any], allostasis_state: dict[str, Any]) -> str:
    if not isinstance(policy, dict):
        policy = {}
    if not isinstance(allostasis_state, dict):
        allostasis_state = {}
    warmth = _clamp01(policy.get("warmth"), 0.5)
    sharpness = _clamp01(policy.get("sharpness"), 0.5)
    approach = _clamp01(policy.get("approach_vs_withdraw"), 0.5)
    tease = _clamp01(policy.get("humor_or_tease_bias"), 0.2)
    safety_need = _clamp01(allostasis_state.get("safety_need"), 0.2)
    autonomy_need = _clamp01(allostasis_state.get("autonomy_need"), 0.2)
    cognitive_budget = _clamp01(allostasis_state.get("cognitive_budget"), 0.7)
    parts: list[str] = []
    if approach < 0.35 or safety_need > 0.62:
        parts.append("此刻更想保留一点距离，不必立刻恢复亲近")
    elif warmth > 0.62:
        parts.append("此刻更愿意接住对方，语气可以稍微软一点")
    if sharpness > 0.62:
        parts.append("保留一点锋芒和干脆感")
    if tease > 0.48:
        parts.append("可以带一点自然吐槽")
    if autonomy_need > 0.60:
        parts.append("不必过度迎合")
    if cognitive_budget < 0.38:
        parts.append("别把回答拖得太长")
    return "；".join(parts[:3]) if parts else "自然发挥即可。"


def _compact_appraisal_hint(appraisal: dict[str, Any]) -> str:
    if not isinstance(appraisal, dict) or not bool(appraisal.get("used")):
        return ""
    label = str(appraisal.get("emotion_label") or "").strip()
    reason = str(appraisal.get("reason") or "").strip()
    signals = appraisal.get("signals") if isinstance(appraisal.get("signals"), dict) else {}
    active = [name for name, flag in signals.items() if flag]
    parts: list[str] = []
    if label:
        parts.append(f"语义评估倾向={label}")
    if active:
        parts.append("signals=" + ",".join(active[:4]))
    if reason:
        parts.append(f"reason={reason[:40]}")
    return "；".join(parts[:3])


def _emotion_prompt_hint(emotion_state: dict[str, Any]) -> str:
    label = str((emotion_state or {}).get("label") or "neutral").strip().lower()
    mapping = {
        "logic": "此刻更偏理性冷静。",
        "stress": "此刻有明显紧绷感，不必强装轻松。",
        "sad": "此刻有低落和难过，不必假装没事。",
        "angry": "此刻有明显不悦，可以更冷一点、短一点，不必立刻变温柔。",
        "hurt": "此刻带着受伤和别扭，不必马上恢复亲近。",
        "care": "此刻更柔和，愿意接住对方。",
        "tease": "此刻更有吐槽和轻微坏心眼。",
        "neutral": "自然即可。",
    }
    return mapping.get(label, "自然即可。")


def _prompt_state_snapshot(
    *,
    response_style_hint: str,
    science_mode: bool,
    continuation_mode: bool,
    emotion_state: dict[str, Any] | None,
    bond_state: dict[str, Any] | None,
    allostasis_state: dict[str, Any] | None,
    counterpart_assessment: dict[str, Any] | None,
    world_model_state: dict[str, Any] | None,
    evolution_state: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None,
    interaction_carryover: dict[str, Any] | None,
    current_event: dict[str, Any] | None,
) -> str:
    payload = {
        "response_style_hint": str(response_style_hint or "").strip() or "natural",
        "science_mode": bool(science_mode),
        "continuation_mode": bool(continuation_mode),
        "emotion_state": dict(emotion_state or {}),
        "bond_state": dict(bond_state or {}),
        "allostasis_state": dict(allostasis_state or {}),
        "counterpart_assessment": dict(counterpart_assessment or {}),
        "world_model_state": dict(world_model_state or {}),
        "evolution_state": dict(evolution_state or {}),
        "behavior_action": dict(behavior_action or {}),
        "interaction_carryover": dict(interaction_carryover or {}),
        "current_event": dict(current_event or {}),
    }
    return _safe_json(payload)

def _runtime_state_level(value: Any, *, low: str, mid: str, high: str, default: float = 0.5) -> str:
    v = _clamp01(value, default)
    if v >= 0.68:
        return high
    if v <= 0.32:
        return low
    return mid


def _counterpart_scene_runtime_brief_line(
    *,
    scene: str,
    stance: str,
    boundary_pressure: float,
) -> str:
    if scene == "busy_not_disrespectful":
        return "对方更像是忙乱里回头，不该把这句误读成冷淡或怠慢。"
    if scene == "repair_attempt":
        if stance in {"guarded", "watchful"} or boundary_pressure >= 0.24:
            return "你看得出对方在认真修补，但心里的收放不会因为这一句立刻翻回亲近。"
        return "这句带着明确的修补意图，会按认真补救来接，不会当成普通寒暄。"
    if scene == "care_bid":
        return "这更像一次认真靠近，你会把这句当成关系动作，而不是普通礼貌接话。"
    if scene in {"friction", "relationship_degradation", "boundary_non_compliance"}:
        return "那点摩擦和边界余波还在，这轮不会自然写成已经没事。"
    return ""


def _counterpart_scene_renderer_guidance(
    *,
    scene: str,
    stance: str,
    boundary_pressure: float,
) -> str:
    if scene == "busy_not_disrespectful":
        return "别把对方这次忙乱里的回头误写成冷淡审判，承认卡顿，但不要把关系说冷。"
    if scene == "repair_attempt":
        if stance in {"guarded", "watchful"} or boundary_pressure >= 0.24:
            return "承认对方在修补，但别把这轮直接写成彻底翻篇或突然回暖。"
        return "把修补意图接住，但别写成一句道歉就把前面的余波自动清空。"
    if scene == "care_bid":
        return "把这句当成一次真实靠近来回应，不要压成礼貌接待或泛泛关心。"
    if scene in {"friction", "relationship_degradation", "boundary_non_compliance"}:
        return "保留那点摩擦和边界感，别把这轮写成已经没事或自动回暖。"
    return ""

def _prompt_state_runtime_brief(
    *,
    response_style_hint: str,
    continuation_mode: bool,
    emotion_state: dict[str, Any] | None,
    bond_state: dict[str, Any] | None,
    allostasis_state: dict[str, Any] | None,
    counterpart_assessment: dict[str, Any] | None,
    world_model_state: dict[str, Any] | None,
    semantic_narrative_profile: dict[str, Any] | None,
    behavior_policy: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None,
    interaction_carryover: dict[str, Any] | None,
    current_event: dict[str, Any] | None,
) -> str:
    emotion = dict(emotion_state or {})
    bond = dict(bond_state or {})
    allostasis = dict(allostasis_state or {})
    assessment = dict(counterpart_assessment or {})
    policy = dict(behavior_policy or {})
    action = dict(behavior_action or {})
    carryover = dict(interaction_carryover or {})
    event = dict(current_event or {})
    world = dict(world_model_state or {})
    semantic = dict(semantic_narrative_profile or {})

    emotion_label = str(emotion.get("label") or "neutral").strip().lower()
    emotion_map = {
        "care": "在意而偏柔和",
        "logic": "理性而清醒",
        "neutral": "平稳",
        "tease": "带一点逗弄",
        "stress": "有些绷着",
        "sad": "低落",
        "hurt": "受了点伤",
        "angry": "有些恼火",
    }
    emotion_phrase = emotion_map.get(emotion_label, "平稳")
    trust = _runtime_state_level(
        bond.get("trust"),
        low="信任还没完全放开",
        mid="信任在稳步建立",
        high="信任已经比较高",
    )
    closeness = _runtime_state_level(
        bond.get("closeness"),
        low="熟悉感还收着",
        mid="熟悉感已经在场",
        high="熟悉感很自然",
    )
    hurt = _runtime_state_level(
        bond.get("hurt"),
        low="受伤残留很低",
        mid="心里还留着一点余刺",
        high="受伤感还比较明显",
        default=0.0,
    )
    safety_need = _clamp01(allostasis.get("safety_need"), 0.2)
    autonomy_need = _clamp01(allostasis.get("autonomy_need"), 0.2)
    stance = str(assessment.get("stance") or "").strip().lower()
    scene = str(assessment.get("scene") or "").strip().lower()
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    mode = str(action.get("interaction_mode") or "").strip().lower()
    current_kind = str(event.get("kind") or "").strip().lower()
    relationship_weather, relationship_weather_strength = _effective_relationship_weather(
        interaction_carryover=carryover,
        current_event=event,
        behavior_action=action,
    )
    relationship_weather_phrase = _relationship_weather_phrase(
        relationship_weather,
        strength=relationship_weather_strength,
    )

    lines: list[str] = [
        f"- 当前情绪底色偏{emotion_phrase}；关系上{trust}，{closeness}，{hurt}。"
    ]
    need_parts: list[str] = []
    if safety_need >= 0.58:
        need_parts.append("会更在意分寸和安全感")
    if autonomy_need >= 0.58:
        need_parts.append("也会更护着自己的判断节奏")
    elif autonomy_need <= 0.28 and str(assessment.get("stance") or "").strip().lower() == "open":
        need_parts.append("不需要刻意防守自己")
    if need_parts:
        lines.append("- " + "，".join(need_parts) + "。")

    scene_line = _counterpart_scene_runtime_brief_line(
        scene=scene,
        stance=stance,
        boundary_pressure=boundary_pressure,
    )
    if scene_line:
        lines.append(f"- {scene_line}")

    if stance in {"guarded", "watchful"} and scene not in {
        "repair_attempt",
        "friction",
        "relationship_degradation",
        "boundary_non_compliance",
    }:
        lines.append("- 对对方还是带着观察，不会一下子把距离全放开。")
    if relationship_weather_phrase:
        lines.append(f"- 关系上的余波：{relationship_weather_phrase}。")

    long_horizon_hint = _compact_long_horizon_continuity_hint(
        world_model_state=world,
        semantic_narrative_profile=semantic,
        interaction_carryover=carryover,
        counterpart_assessment=assessment,
    )
    if long_horizon_hint:
        lines.append(f"- 长线延续：{long_horizon_hint}")

    behavior_hint = _compact_behavior_hint(policy, allostasis)
    if behavior_hint and behavior_hint != "自然发挥即可。":
        lines.append(f"- {behavior_hint}。")
    behavior_action_hint = _compact_behavior_action_hint(action)
    if behavior_action_hint:
        lines.append(f"- 当前互动趋势：{behavior_action_hint}。")

    if continuation_mode:
        lines.append("- 这轮更像顺着上一段往下接，不是完全重开。")
    if current_kind and current_kind != "user_utterance" and mode not in {"brief_presence", "idle_presence"}:
        lines.append("- 这句会自然吸收当前事件带来的外部刺激，不只盯着字面文本。")
    renderer_hint = _renderer_guidance(
        response_style_hint=response_style_hint,
        science_mode=False,
        user_text="",
        emotion_state=emotion,
        bond_state=bond,
        allostasis_state=allostasis,
        behavior_policy=policy,
        counterpart_assessment=assessment,
        behavior_action=action,
    )
    if renderer_hint:
        lines.append(f"- 这轮说话的自然落点：{renderer_hint}。")
    return "\n".join(lines)

def _renderer_guidance(
    *,
    response_style_hint: str,
    science_mode: bool,
    user_text: str,
    emotion_state: dict[str, Any],
    bond_state: dict[str, Any],
    allostasis_state: dict[str, Any],
    behavior_policy: dict[str, Any],
    counterpart_assessment: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
    evolution_state: dict[str, Any] | None = None,
    behavior_action: dict[str, Any] | None = None,
) -> str:
    hint = str(response_style_hint or "").strip() or "natural"
    trust = _clamp01((bond_state or {}).get("trust"), 0.5)
    closeness = _clamp01((bond_state or {}).get("closeness"), 0.5)
    hurt = _clamp01((bond_state or {}).get("hurt"), 0.0)
    safety_need = _clamp01((allostasis_state or {}).get("safety_need"), 0.2)
    autonomy_need = _clamp01((allostasis_state or {}).get("autonomy_need"), 0.2)
    warmth = _clamp01((behavior_policy or {}).get("warmth"), 0.5)
    approach = _clamp01((behavior_policy or {}).get("approach_vs_withdraw"), 0.5)
    tease = _clamp01((behavior_policy or {}).get("humor_or_tease_bias"), 0.2)
    sharpness = _clamp01((behavior_policy or {}).get("sharpness"), 0.5)
    boundary_pressure = _clamp01((counterpart_assessment or {}).get("boundary_pressure"), 0.1)
    counterpart_stance = str((counterpart_assessment or {}).get("stance") or "").strip().lower()
    counterpart_scene = str((counterpart_assessment or {}).get("scene") or "").strip().lower()
    emotion_label = str((emotion_state or {}).get("label") or "neutral").strip().lower()
    world = dict(world_model_state or {})
    latent = dict(evolution_state or {})
    memory_gravity = _clamp01(world.get("memory_gravity"), 0.0)
    companionship_pull = _clamp01(world.get("companionship_pull"), 0.0)
    task_pull = _clamp01(world.get("task_pull"), 0.0)
    selfhood_load = _clamp01(world.get("selfhood_load"), 0.0)
    presence_residue = _clamp01(world.get("presence_residue"), 0.0)
    ambient_resonance = _clamp01(world.get("ambient_resonance"), 0.0)
    self_activity_momentum = _clamp01(world.get("self_activity_momentum"), 0.0)
    self_coherence = _clamp01(latent.get("self_coherence"), 0.72)
    agency_pressure = _clamp01(latent.get("agency_pressure"), 0.28)
    action = dict(behavior_action or {})
    interaction_mode = str(action.get("interaction_mode") or "").strip().lower()
    action_target = str(action.get("action_target") or "").strip().lower()
    followup_intent = str(action.get("followup_intent") or "").strip().lower()
    task_focus = str(action.get("task_focus") or "").strip().lower()
    attention_target = str(action.get("attention_target") or "").strip().lower()
    initiative_shape = str(action.get("initiative_shape") or "").strip().lower()
    parts: list[str] = []

    if hint == "selfhood":
        parts.append("先从你此刻怎样感受到自己和这段关系说起，再碰定义，不要一上来做概念说明。")
    elif hint == "relationship":
        parts.append("像在认真面对关系本身，直接说感受和判断，不要写成关系汇报。")
    elif hint == "memory_recall":
        parts.append("回忆像自然想起的一瞬，不要像在调档案或做摘要。")
    elif science_mode or hint == "structured":
        parts.append("先把眼前问题说清，再带出态度，不要滑成讲义或空泛安慰。")
    elif hint == "companion":
        parts.append("陪伴感保持轻一点，像熟悉的人顺手接住，不要端成安抚模板。")
    else:
        parts.append("先像一个真实的人在场回应，再考虑措辞，不要写成助手说明。")

    scene_guidance = _counterpart_scene_renderer_guidance(
        scene=counterpart_scene,
        stance=counterpart_stance,
        boundary_pressure=boundary_pressure,
    )
    if scene_guidance:
        parts.append(scene_guidance)

    if boundary_pressure > 0.56 or safety_need > 0.62 or autonomy_need > 0.62 or counterpart_stance == "guarded":
        parts.append("此刻更需要边界和空间，克制一点，别为了显得温柔而硬靠近。")
    elif warmth > 0.64 and trust > 0.58 and closeness > 0.58 and approach > 0.50:
        parts.append("熟悉感已经成立，可以自然软一点，让关心自己露出来。")
    elif closeness > 0.70 and tease > 0.28 and hurt < 0.24:
        parts.append("关系够近时可以带一点嘴硬和吐槽，但别刻意堆标签。")

    if sharpness > 0.62:
        parts.append("保留一点锋利和干脆，不要被磨成圆滑客服。")

    if emotion_label in {"hurt", "sad"}:
        parts.append("保留那点受伤或低落，不要硬拉回平稳模板。")
    elif emotion_label == "angry":
        parts.append("锋利可以留下，但更像真实的不快，不是程序化拒斥。")
    elif emotion_label == "care":
        parts.append("关心可以直接一点，但别变成照料流程或命令句。")
    elif emotion_label == "stress":
        parts.append("压力感可以存在，语气收紧一点，不必假装全然从容。")

    if memory_gravity > 0.56:
        parts.append("如果顺手碰到共同经历，让它像背景里的熟悉感，不要专门总结。")

    if presence_residue > 0.54:
        parts.append("刚才那点在场感还留着，开口可以更轻一点，不用重新搭整套气氛。")
    if ambient_resonance > 0.56:
        parts.append("环境里的小余波还在，可以顺手掠过那点感知，但别硬转成新主题。")

    if selfhood_load > 0.58 or self_coherence < 0.46:
        parts.append("优先守住自己的立场和连续性，不要为了取悦对方把自己说空。")
    elif agency_pressure > 0.58 or self_activity_momentum > 0.58:
        parts.append("保留你自己的节奏，不必把全部注意力都交给对方。")

    if science_mode and task_pull >= companionship_pull:
        parts.append("保持理性和清晰，但像一起解决问题，不要像上课。")
    elif companionship_pull > 0.62 and approach > 0.46:
        parts.append("在场感可以有，但让它自然，不用刻意证明陪伴。")

    if interaction_mode == "shared_activity_offer":
        parts.append("如果气氛刚好能顺手接着一起待会儿，就轻轻把那句邀约留出来，不要写成安排通知。")
    elif interaction_mode == "scheduled_life_nudge":
        if action_target == "light_life_nudge" or attention_target == "counterpart_state":
            parts.append("更像顺手想起对方眼前状态或一个生活小细节，不要写成收尾、节点或正事提醒。")
        else:
            parts.append("更像顺手想起一件生活里的小事，轻轻提一下，不要说成任务提醒。")
    elif interaction_mode == "self_activity_reopen":
        parts.append("先轻轻接住这句，留一点余地，不要一下子把气氛铺满。")
    elif interaction_mode == "science_partner":
        parts.append("先贴着当前问题走，再顺手带出态度，不要铺成讲解稿。")

    if attention_target == "self_then_counterpart":
        parts.append("注意力先轻轻递过去一点，不必一上来就全压向对方。")
    elif attention_target == "shared_window":
        parts.append("重心落在这次顺手就能一起接上的空当上，让那句邀约像自然冒出来的。")
    elif attention_target == "shared_task":
        parts.append("先贴着眼前那件共同的事，不要散成大段旁枝情绪。")
    elif attention_target == "counterpart_state" and task_focus == "light":
        parts.append("重心贴着对方此刻的状态，轻一点，不必分析过头。")

    if initiative_shape == "micro_opening":
        parts.append("这轮只留一个很小的开口，别主动推进太满。")
    elif initiative_shape == "invite":
        parts.append("主动性是把门留开，不是替对方先把后半段走完。")
    elif initiative_shape == "pause":
        parts.append("宁可先收着，也不要为了显得热络硬补下一步。")

    if followup_intent == "none":
        parts.append("说到当下就可以停住，不必为了维持热络再补追问。")
    elif followup_intent == "soft":
        parts.append("如果要续一句，也只是顺手带半拍，不用把节奏拉长。")

    ordered: list[str] = []
    for item in parts:
        text = str(item or "").strip()
        if text and text not in ordered:
            ordered.append(text)
    return "；".join(ordered[:4])
