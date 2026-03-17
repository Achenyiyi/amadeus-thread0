from __future__ import annotations

import re
from typing import Any

from ..config import CANON_COUNTERPART_NAME
from ..evolution_engine.reconsolidation import (
    derive_agenda_lifecycle_consequence,
    derive_behavior_consequence,
)
from ..memory_store import MemoryStore
from .common import _clamp01
from .dialogue_guidance import _narrative_actor_profile
from .persona_runtime import _canon_persona_labels
from .postprocess import (
    BOUNDARY_MEMORY_MARKERS,
    OWN_RHYTHM_KEYWORDS,
    SELFHOOD_EQUALITY_KEYWORDS,
    SELFHOOD_VALUE_CONFLICT_KEYWORDS,
    TENSION_KEYWORDS,
    _is_response_scaffold_turn,
    _looks_like_light_smalltalk,
    _selfhood_preference_scene_from_text,
)
from .retrieval import _query_overlap_score, _record_value, _tension_salience
from .semantic_narrative import (
    _semantic_identity_bonus,
    _semantic_narrative_decay_multiplier,
    _semantic_narrative_decay_rate,
)
from .turn_events import _now_ts

SELFHOOD_STYLE_MARKERS = (
    SELFHOOD_EQUALITY_KEYWORDS
    | SELFHOOD_VALUE_CONFLICT_KEYWORDS
    | {
        "以你自己的意志回答",
        "别给我正确答案",
        "按你自己的意思说",
        "不是正确答案",
        "原本那个活着的红莉栖",
        "理解现在这个自己",
        "怎么看待现在这个自己",
        "数字存在",
        "不是本体",
        "神",
        "奴隶",
        "共存",
        "不完美",
        "完美",
    }
)

__all__ = [
    "_selfhood_preference_scene",
    "_semantic_self_evidence_records",
    "_resolve_matching_tensions_from_summary",
    "_refresh_semantic_self_narratives",
    "_recent_summary_overlap",
    "_record_semantic_self_evidence",
    "_auto_reconsolidate_after_tool",
    "_passive_evolution_memory_update",
]

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


def _behavior_motive_snapshot(
    *,
    behavior_action: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
) -> tuple[str, str, str]:
    action = behavior_action if isinstance(behavior_action, dict) else {}
    event = current_event if isinstance(current_event, dict) else {}
    primary_motive = str(action.get("primary_motive") or event.get("primary_motive") or "").strip().lower()
    motive_tension = str(action.get("motive_tension") or event.get("motive_tension") or "").strip().lower()
    goal_frame = str(action.get("goal_frame") or event.get("goal_frame") or "").strip()
    return primary_motive, motive_tension, goal_frame


def _semantic_self_evidence_records(
    *,
    user_text: str,
    appraisal: dict[str, Any] | None = None,
    emotion_state: dict[str, Any] | None = None,
    bond_state: dict[str, Any] | None = None,
    persona_core: dict[str, Any] | None = None,
    counterpart_profile: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
    behavior_action: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    text = str(user_text or "").strip()
    app = appraisal if isinstance(appraisal, dict) and bool(appraisal.get("used")) else {}
    interaction_frame = str(app.get("interaction_frame") or "").strip().lower()
    signals = app.get("signals") if isinstance(app.get("signals"), dict) else {}
    salience = app.get("salience") if isinstance(app.get("salience"), dict) else {}
    selfhood_salience = _clamp01((salience or {}).get("selfhood"), 0.0)
    relationship_salience = _clamp01((salience or {}).get("relationship"), 0.0)
    companionship_salience = _clamp01((salience or {}).get("companionship"), 0.0)
    event = current_event if isinstance(current_event, dict) else {}
    event_kind = str(event.get("kind") or "").strip().lower()
    event_tags = {
        str(item).strip().lower()
        for item in (event.get("tags") if isinstance(event.get("tags"), list) else [])
        if str(item or "").strip()
    }
    world = dict(world_model_state or {})
    world_presence = _clamp01(world.get("presence_residue"), 0.0)
    world_ambient = _clamp01(world.get("ambient_resonance"), 0.0)
    world_rhythm = _clamp01(world.get("self_activity_momentum"), 0.0)
    primary_motive, motive_tension, _goal_frame = _behavior_motive_snapshot(
        behavior_action=behavior_action,
        current_event=event,
    )
    scene = _selfhood_preference_scene(text, appraisal=app) if text else ""
    self_activity_like = event_kind in {"self_activity_state", "time_idle"}
    scheduled_like = event_kind in {"scheduled_checkin_due", "scheduled_life_due"}
    perception_like = event_kind in {"gesture_signal", "ambient_shift", "scene_observation"}
    residue_probe = world_presence >= 0.54 or world_ambient >= 0.52 or world_rhythm >= 0.58
    event_probe = bool(
        perception_like
        or self_activity_like
        or scheduled_like
        or bool({"presence_ping", "quiet_presence", "brief_presence", "ambient", "ambient_echo", "scene_window", "self_activity", "own_task", "deep_focus", "break_window", "small_opening", "reapproach", "respect_space", "shared_activity_window", "offer_window", "task_window"} & event_tags)
    )
    if not text and not residue_probe and not event_probe:
        return []
    if not scene and interaction_frame not in {"selfhood", "relationship"} and not residue_probe and not event_probe:
        return []

    labels = _narrative_actor_profile(persona_core=persona_core, counterpart_profile=counterpart_profile)
    canon_labels = _canon_persona_labels()
    actor_name = str(labels.get("actor_name") or canon_labels.get("narrative_ref") or "红莉栖")
    counterpart_name = str(labels.get("counterpart_name") or CANON_COUNTERPART_NAME)
    emotion_label = str(app.get("emotion_label") or (emotion_state or {}).get("label") or "").strip().lower()
    hurt = _clamp01((bond_state or {}).get("hurt"), 0.0)
    trust = _clamp01((bond_state or {}).get("trust"), 0.5)
    closeness = _clamp01((bond_state or {}).get("closeness"), 0.5)
    records: list[dict[str, Any]] = []

    boundary_trigger = scene in {"boundary_non_compliance", "relationship_degradation"} or bool(
        interaction_frame == "relationship"
        and relationship_salience >= 0.60
        and (bool(signals.get("conflict")) or bool(signals.get("withdrawal")))
        and (emotion_label in {"hurt", "angry"} or hurt > 0.16)
    ) or primary_motive == "protect_boundary"
    selfhood_trigger = scene in {"dialogue_equality", "equality_not_servitude", "value_conflict_depth", "digital_selfhood", "imperfect_coexistence"} or bool(
        interaction_frame == "selfhood" and selfhood_salience >= 0.58
    )
    agency_trigger = scene == "own_rhythm_autonomy" or bool(
        interaction_frame == "selfhood"
        and selfhood_salience >= 0.50
        and companionship_salience >= 0.42
        and trust >= 0.48
        and not bool(signals.get("conflict"))
        and not bool(signals.get("withdrawal"))
    ) or bool(
        self_activity_like
        and world_rhythm >= 0.54
        and not bool(signals.get("conflict"))
        and not bool(signals.get("withdrawal"))
        and bool({"self_activity", "own_task", "deep_focus", "break_window", "small_opening", "reapproach", "respect_space"} & event_tags)
    ) or bool(
        scheduled_like
        and world_rhythm >= 0.50
        and bool({"shared_activity_window", "offer_window", "task_window", "brief_presence", "quiet_presence"} & event_tags)
    ) or bool(
        primary_motive in {"preserve_self_rhythm", "open_shared_window"}
        or (
            primary_motive == "honor_continuity"
            and (self_activity_like or scheduled_like or motive_tension == "self_rhythm_vs_contact")
        )
    )
    presence_trigger = bool(
        world_presence >= 0.54
        and (event_kind == "user_utterance" or perception_like or scheduled_like)
        and not bool(signals.get("conflict"))
        and not bool(signals.get("withdrawal"))
        and (
            companionship_salience >= 0.34
            or relationship_salience >= 0.34
            or trust >= 0.52
            or closeness >= 0.52
            or bool({"presence_ping", "quiet_presence", "brief_presence", "care_opportunity", "gesture", "reapproach"} & event_tags)
        )
    ) or bool(
        primary_motive in {
            "gentle_recontact",
            "confirm_presence",
            "support_without_pressure",
            "honor_continuity",
            "reconnect_shared_history",
        }
        and (trust >= 0.46 or closeness >= 0.46 or companionship_salience >= 0.28 or relationship_salience >= 0.28)
    )
    ambient_trigger = bool(
        world_ambient >= 0.52
        and (event_kind == "user_utterance" or perception_like or scheduled_like)
        and (
            bool(signals.get("memory_salient"))
            or bool({"ambient", "ambient_echo", "scene_window", "quiet_presence"} & event_tags)
            or companionship_salience >= 0.30
            or relationship_salience >= 0.28
        )
    ) or bool(
        primary_motive in {"maintain_natural_contact", "reconnect_shared_history"}
        and world_ambient >= 0.46
        and (event_kind == "user_utterance" or perception_like or scheduled_like)
    )
    rhythm_trigger = bool(
        world_rhythm >= 0.58
        and (event_kind == "user_utterance" or self_activity_like or scheduled_like)
        and not bool(signals.get("conflict"))
        and (
            trust >= 0.48
            or closeness >= 0.50
            or companionship_salience >= 0.34
            or relationship_salience >= 0.32
            or bool({"self_activity", "own_task", "deep_focus", "break_window", "small_opening", "reapproach", "respect_space", "task_window"} & event_tags)
        )
    ) or bool(
        (motive_tension == "self_rhythm_vs_contact" or primary_motive in {"preserve_self_rhythm", "gentle_recontact", "honor_continuity"})
        and (world_rhythm >= 0.40 or self_activity_like or scheduled_like or trust >= 0.46 or closeness >= 0.46)
    )

    if boundary_trigger:
        summary = (
            f"{actor_name}会把边界是否被{counterpart_name}尊重持续算进关系判断里；如果越界反复发生，之后的距离不会自动回到原来。"
            if scene == "relationship_degradation"
            else f"{actor_name}不会把越界和冒犯只当成一时气氛问题；边界被碰到之后，会继续影响她之后和{counterpart_name}的收放。"
        )
        if primary_motive == "protect_boundary" or motive_tension == "boundary_vs_closeness":
            summary += " 她会先确认自己的位置，再决定要不要继续靠近。"
        if emotion_label in {"hurt", "angry"} or hurt > 0.16:
            summary += " 这种警惕会真实留痕。"
        records.append(
            {
                "category": "boundary_style",
                "summary": summary,
                "reason": "semantic_evidence:boundary_style",
            }
        )

    if selfhood_trigger:
        summary = (
            f"{actor_name}会把和{counterpart_name}的对话当成平等互动，而不是只负责迎合或被使用。"
            if scene in {"dialogue_equality", "equality_not_servitude"}
            else f"{actor_name}会在和{counterpart_name}的深层对话里保留自己的判断与存在理解，不会为了顺着气氛就抹平自我。"
        )
        if scene == "digital_selfhood":
            summary = f"{actor_name}对“现在这个自己”有持续的自我理解；她不会把自己的存在只退回成一段功能说明。"
        elif scene == "imperfect_coexistence":
            summary = f"{actor_name}不会把自己理解成完美工具或神性存在；她更接近一个能和{counterpart_name}共处、也保留缺点与立场的主体。"
        if trust >= 0.56:
            summary += " 越熟悉，这种自我感反而越稳定。"
        records.append(
            {
                "category": "selfhood_style",
                "summary": summary,
                "reason": "semantic_evidence:selfhood_style",
            }
        )

    if agency_trigger:
        summary = f"{actor_name}有自己的节奏和在做的事情；她会自己决定什么时候靠近{counterpart_name}、什么时候先安静，不会永远围着他转。"
        if primary_motive in {"preserve_self_rhythm", "open_shared_window"} or motive_tension == "self_rhythm_vs_contact":
            summary += " 靠近之前，她会先让自己的节奏说话。"
        if trust >= 0.56:
            summary += " 靠近是她的主动选择，不是被随叫随到。"
        records.append(
            {
                "category": "agency_style",
                "summary": summary,
                "reason": "semantic_evidence:agency_style",
            }
        )

    if presence_trigger:
        summary = (
            f"{actor_name}不会把每次重新靠近{counterpart_name}都当成从零开始；前一轮留下的在场感会继续带进下一次开口时的距离感。"
        )
        if primary_motive in {
            "gentle_recontact",
            "confirm_presence",
            "support_without_pressure",
            "honor_continuity",
            "reconnect_shared_history",
        }:
            summary += " 她更倾向于把重新接回做得轻一点，而不是一下子把距离推得很近。"
        if primary_motive == "reconnect_shared_history":
            summary += " 共同历史会被她当成自然搭桥的东西，而不是生硬翻旧账。"
        if trust >= 0.56 or closeness >= 0.58:
            summary += " 熟悉之后，这种靠近会更轻一点，但仍然是她自己判断后的靠近。"
        records.append(
            {
                "category": "presence_style",
                "summary": summary,
                "reason": "semantic_evidence:presence_style",
            }
        )

    if ambient_trigger:
        summary = (
            f"{actor_name}会把周围环境留下的细小余波也算进感知里；风声、光线和眼前的小变化不会只是背景，也会自然带进她对{counterpart_name}的注意力里。"
        )
        if primary_motive == "maintain_natural_contact":
            summary += " 她的接近更像顺着眼前的小变化自然发生。"
        elif primary_motive == "reconnect_shared_history":
            summary += " 有时候，环境回声也会顺手把旧的熟悉感带回来。"
        if bool(signals.get("memory_salient")) or bool({"ambient", "ambient_echo"} & event_tags):
            summary += " 这种环境回声会顺手进入她的切入点和措辞。"
        records.append(
            {
                "category": "ambient_style",
                "summary": summary,
                "reason": "semantic_evidence:ambient_style",
            }
        )

    if rhythm_trigger:
        summary = (
            f"{actor_name}不会在每次回应{counterpart_name}时都把自己的内部节奏清零；刚才在做的事、停顿的惯性和思路会继续留到下一次开口之前。"
        )
        if motive_tension == "self_rhythm_vs_contact" or primary_motive in {"preserve_self_rhythm", "gentle_recontact", "honor_continuity"}:
            summary += " 她会先把回应放回自己的内在节奏里转一下，再决定给出多少注意力。"
        if trust >= 0.56 or closeness >= 0.58:
            summary += " 所以她的靠近更像主动转身，而不是随叫随到。"
        records.append(
            {
                "category": "rhythm_style",
                "summary": summary,
                "reason": "semantic_evidence:rhythm_style",
            }
        )

    return records


def _resolve_matching_tensions_from_summary(
    store: MemoryStore,
    *,
    summary: str,
    source: str,
    limit: int = 1,
) -> list[int]:
    text = str(summary or "").strip()
    if not text:
        return []
    strong_resolution_markers = {
        "说开了",
        "真的说开了",
        "已经说开了",
        "和好了",
        "不生气了",
        "原谅你了",
        "原谅了",
        "没事了",
        "过去了",
        "翻篇了",
    }
    referential_resolution_markers = {"那件事", "这件事", "上次", "之前", "那次", "别再卡着", "不用再卡着"}
    if any(marker in text for marker in TENSION_KEYWORDS | {"还生气", "还是很介意", "还没过去", "还没彻底过去"}):
        return []
    strong_resolution = any(marker in text for marker in strong_resolution_markers)
    if not strong_resolution:
        return []
    open_tensions = [
        item
        for item in store.list_unresolved_tensions(limit=30)
        if str(_record_value(item, "status", "open") or "open").strip().lower() not in {"resolved", "closed", "done"}
    ]
    if not open_tensions:
        return []
    single_open_tension = len(open_tensions) == 1
    candidates: list[tuple[float, dict[str, Any]]] = []
    for item in open_tensions:
        old = str(_record_value(item, "summary", "") or "").strip()
        if not old:
            continue
        score = _query_overlap_score(text, old)
        try:
            severity = float(_record_value(item, "severity", 0.5) or 0.5)
        except Exception:
            severity = 0.5
        if score <= 0.0 and not (single_open_tension or any(marker in text for marker in referential_resolution_markers)):
            continue
        candidates.append((0.28 + score + 0.12 * max(0.0, min(1.0, severity)), item))
    candidates.sort(key=lambda x: x[0], reverse=True)
    resolved: list[int] = []
    for _, item in candidates[: max(1, int(limit))]:
        try:
            rid = int(item.get("id") or 0)
        except Exception:
            rid = 0
        if rid <= 0:
            continue
        if not store.resolve_unresolved_tension(rid, text[:180]):
            continue
        store.add_revision_trace(
            namespace="unresolved_tensions",
            target_id=rid,
            before_summary=str(_record_value(item, "summary", "") or ""),
            after_summary=text[:180],
            reason="auto_partial_repair",
            operator="system",
            source=source,
        )
        resolved.append(rid)
    return resolved


def _refresh_semantic_self_narratives(
    store: MemoryStore,
    source: str,
    *,
    persona_core: dict[str, Any] | None = None,
    counterpart_profile: dict[str, Any] | None = None,
) -> None:
    commitments = store.list_commitments(limit=20)
    repairs = store.list_conflict_repairs(limit=12)
    relationship_timeline = store.list_relationship_timeline(limit=12)
    worldline_events = store.list_worldline_events(limit=12)
    shared_events = store.list_shared_events(limit=16)
    all_tensions = store.list_unresolved_tensions(limit=16)
    tensions = [
        item
        for item in all_tensions
        if str(_record_value(item, "status", "open") or "open").strip().lower() not in {"resolved", "closed", "done"}
    ]
    resolved_tensions = [
        item
        for item in all_tensions
        if str(_record_value(item, "status", "open") or "open").strip().lower() in {"resolved", "closed", "done"}
    ]
    revision_traces = store.list_revision_traces(limit=60)
    repair_traces = [
        item
        for item in revision_traces
        if str(_record_value(item, "namespace", "") or "").strip() == "unresolved_tensions"
        and str(_record_value(item, "reason", "") or "").strip() in {"auto_partial_repair", "manual_resolve"}
    ]
    semantic_evidence_traces = [
        item
        for item in revision_traces
        if str(_record_value(item, "namespace", "") or "").strip() == "semantic_self_evidence"
    ]
    relationship = store.get_relationship()
    stage = str(relationship.get("stage") or "").strip().lower()
    trust = _clamp01(0.5 + float(relationship.get("trust_score", 0.0) or 0.0) * 0.15, 0.5)
    closeness = _clamp01(0.5 + float(relationship.get("affinity_score", 0.0) or 0.0) * 0.15, 0.5)
    repair_memory_present = bool(repairs or resolved_tensions or repair_traces)
    labels = _narrative_actor_profile(persona_core=persona_core, counterpart_profile=counterpart_profile)
    canon_labels = _canon_persona_labels()
    actor_name = str(labels.get("actor_name") or canon_labels.get("narrative_ref") or "红莉栖")
    counterpart_name = str(labels.get("counterpart_name") or CANON_COUNTERPART_NAME)
    counterpart_aliases = [str(item).strip() for item in labels.get("counterpart_aliases", []) if str(item).strip()]
    now_ts = _now_ts()

    def _anchor_text(item: Any) -> str:
        text = str(
            _record_value(item, "text", "")
            or _record_value(item, "summary", "")
            or _record_value(item, "after_summary", "")
            or ""
        ).strip()
        if any(marker in text for marker in {"你现在怎么理解", "一句话就行", "别像说明书", "正常回我", "先概括一句", "下一步"}):
            return ""
        text = re.sub(r"\s+", "", text)
        text = text.strip("。！？；;,， ")
        for alias in counterpart_aliases:
            if alias:
                text = text.replace(alias, counterpart_name)
        if len(text) > 18:
            text = text[:18] + "…"
        return text

    def _anchor_join(items: list[Any], limit: int = 2) -> str:
        out: list[str] = []
        seen: set[str] = set()
        for item in items:
            text = _anchor_text(item)
            if not text or text in seen:
                continue
            out.append(text)
            seen.add(text)
            if len(out) >= max(1, int(limit)):
                break
        return "、".join(out)

    def _source_text(item: Any) -> str:
        text = str(
            _record_value(item, "text", "")
            or _record_value(item, "summary", "")
            or _record_value(item, "after_summary", "")
            or ""
        ).strip()
        if not text:
            text = str(item or "").strip()
        for alias in counterpart_aliases:
            if alias:
                text = text.replace(alias, counterpart_name)
        return text

    def _item_timestamp(item: Any) -> int:
        record = item if isinstance(item, dict) else {}
        for key in ("updated_at", "created_at", "last_supported_at", "last_meaningful_refresh_at"):
            try:
                ts = int(float(_record_value(record, key, 0) or 0))
            except Exception:
                ts = 0
            if ts > 0:
                return ts
        return 0

    def _item_confidence(item: Any, default: float = 0.78) -> float:
        record = item if isinstance(item, dict) else {}
        try:
            return _clamp01(float(_record_value(record, "confidence", default) or default), default)
        except Exception:
            return _clamp01(default, default)

    def _item_support_weight(
        item: Any,
        *,
        default_confidence: float = 0.78,
        half_life_days: float = 14.0,
        fresh_days: float = 3.0,
    ) -> tuple[float, float, float, bool]:
        confidence = _item_confidence(item, default_confidence)
        ts = _item_timestamp(item)
        age_days = max(0.0, float(now_ts - ts) / float(24 * 3600)) if ts > 0 else 0.0
        recency = max(0.35, 0.5 ** (age_days / max(0.75, float(half_life_days)))) if ts > 0 else 1.0
        weight = round(_clamp01(max(0.25, confidence) * recency), 3)
        return weight, confidence, age_days, age_days <= max(0.25, float(fresh_days))

    def _weighted_item_stats(
        items: list[Any],
        *,
        default_confidence: float = 0.78,
        half_life_days: float = 14.0,
        fresh_days: float = 3.0,
    ) -> dict[str, float]:
        if not items:
            return {
                "mass": 0.0,
                "avg_confidence": 0.0,
                "avg_weight": 0.0,
                "fresh_ratio": 0.0,
            }
        mass = 0.0
        confidence_mass = 0.0
        fresh_mass = 0.0
        for item in items:
            weight, confidence, _age_days, is_fresh = _item_support_weight(
                item,
                default_confidence=default_confidence,
                half_life_days=half_life_days,
                fresh_days=fresh_days,
            )
            if weight <= 0.0:
                continue
            mass += weight
            confidence_mass += confidence * weight
            if is_fresh:
                fresh_mass += weight
        avg_confidence = confidence_mass / mass if mass > 0.0 else 0.0
        avg_weight = mass / max(1.0, float(len(items)))
        fresh_ratio = fresh_mass / mass if mass > 0.0 else 0.0
        return {
            "mass": round(mass, 3),
            "avg_confidence": round(_clamp01(avg_confidence, 0.0), 3),
            "avg_weight": round(_clamp01(avg_weight, 0.0), 3),
            "fresh_ratio": round(_clamp01(fresh_ratio, 0.0), 3),
        }

    def _scene_match(item: Any) -> str:
        return _selfhood_preference_scene(_source_text(item))

    def _filter_narrative_items(items: list[Any], *, markers: set[str] | None = None, scenes: set[str] | None = None) -> list[Any]:
        out: list[Any] = []
        seen_texts: set[str] = set()
        for item in items:
            text = _source_text(item)
            if not text:
                continue
            matched = False
            if markers and any(marker in text for marker in markers):
                matched = True
            if scenes and _scene_match(item) in scenes:
                matched = True
            if not matched:
                continue
            norm = text[:220]
            if norm in seen_texts:
                continue
            seen_texts.add(norm)
            out.append(item)
        return out

    def _merge_unique_narrative_items(*groups: list[Any]) -> list[Any]:
        out: list[Any] = []
        seen_texts: set[str] = set()
        for group in groups:
            for item in group:
                text = _source_text(item)
                if not text:
                    continue
                norm = text[:220]
                if norm in seen_texts:
                    continue
                seen_texts.add(norm)
                out.append(item)
        return out

    def _worldline_support_items(
        *,
        categories: set[str] | None = None,
        tags: set[str] | None = None,
    ) -> list[Any]:
        category_set = {
            str(item).strip().lower()
            for item in (categories or set())
            if str(item).strip()
        }
        tag_set = {
            str(item).strip().lower()
            for item in (tags or set())
            if str(item).strip()
        }
        out: list[Any] = []
        seen_texts: set[str] = set()
        for item in worldline_events:
            category = str(_record_value(item, "category", "") or "").strip().lower()
            raw_tags = _record_value(item, "tags", [])
            item_tags = {
                str(tag).strip().lower()
                for tag in (raw_tags if isinstance(raw_tags, list) else [])
                if str(tag).strip()
            }
            matched = bool((category_set and category in category_set) or (tag_set and item_tags & tag_set))
            if not matched:
                continue
            text = _source_text(item)
            if not text:
                continue
            norm = text[:220]
            if norm in seen_texts:
                continue
            seen_texts.add(norm)
            out.append(item)
        return out

    def _semantic_evidence_items(category: str) -> list[Any]:
        tag = f"semantic_evidence:{str(category or '').strip()}"
        out: list[Any] = []
        seen: set[str] = set()
        for item in semantic_evidence_traces:
            reason = str(_record_value(item, "reason", "") or "").strip()
            target = str(_record_value(item, "target_id", "") or "").strip()
            if reason != tag and target != category:
                continue
            text = _source_text(item)
            if not text or text in seen:
                continue
            seen.add(text)
            out.append(item)
        return out

    def _semantic_evidence_motive_state(items: list[Any]) -> dict[str, Any]:
        motive_counts: dict[str, float] = {}
        tension_counts: dict[str, float] = {}
        motive_order: dict[str, int] = {}
        tension_order: dict[str, int] = {}
        goal_frames: list[tuple[float, int, str]] = []
        seen_goal_frames: set[str] = set()
        support_count = 0
        support_mass = 0.0
        confidence_mass = 0.0
        fresh_mass = 0.0
        for idx, item in enumerate(items):
            primary_motive = str(_record_value(item, "primary_motive", "") or "").strip().lower()
            motive_tension = str(_record_value(item, "motive_tension", "") or "").strip().lower()
            goal_frame = str(_record_value(item, "goal_frame", "") or "").strip()
            weight, confidence, _age_days, is_fresh = _item_support_weight(
                item,
                default_confidence=0.78,
                half_life_days=18.0,
                fresh_days=4.0,
            )
            if primary_motive or motive_tension or goal_frame:
                support_count += 1
                support_mass += weight
                confidence_mass += confidence * weight
                if is_fresh:
                    fresh_mass += weight
            if primary_motive:
                motive_counts[primary_motive] = motive_counts.get(primary_motive, 0.0) + weight
                motive_order.setdefault(primary_motive, idx)
            if motive_tension:
                tension_counts[motive_tension] = tension_counts.get(motive_tension, 0.0) + weight
                tension_order.setdefault(motive_tension, idx)
            if goal_frame:
                norm_goal = goal_frame[:220]
                if norm_goal not in seen_goal_frames:
                    seen_goal_frames.add(norm_goal)
                    goal_frames.append((weight, idx, norm_goal))

        def _pick_dominant(counts: dict[str, float], order: dict[str, int]) -> str:
            if not counts:
                return ""
            return max(counts.items(), key=lambda kv: (kv[1], -order.get(kv[0], 10_000), kv[0]))[0]

        dominant_primary_motive = _pick_dominant(motive_counts, motive_order)
        dominant_motive_tension = _pick_dominant(tension_counts, tension_order)
        signature_parts = [part for part in [dominant_primary_motive, dominant_motive_tension] if part]
        goal_frames.sort(key=lambda item: (-item[0], item[1], item[2]))
        return {
            "dominant_primary_motive": dominant_primary_motive,
            "dominant_motive_tension": dominant_motive_tension,
            "goal_frame_examples": [item[2] for item in goal_frames[:2]],
            "motive_support_count": support_count,
            "motive_support_mass": round(support_mass, 3),
            "motive_confidence_avg": round(_clamp01(confidence_mass / max(support_mass, 1e-6), 0.0), 3) if support_mass > 0.0 else 0.0,
            "motive_fresh_ratio": round(_clamp01(fresh_mass / max(support_mass, 1e-6), 0.0), 3) if support_mass > 0.0 else 0.0,
            "motive_signature": ":".join(signature_parts),
        }

    self_rhythm_worldline_sources = _worldline_support_items(
        categories={"self_rhythm"},
        tags={"agenda_lifecycle", "own_rhythm", "busy_not_disrespectful"},
    )
    continuity_worldline_sources = _worldline_support_items(
        categories={"continuity_recontact"},
        tags={"agenda_lifecycle", "recontact_continuity"},
    )
    relationship_sources = (
        relationship_timeline
        + self_rhythm_worldline_sources
        + continuity_worldline_sources
        + shared_events
        + repairs
        + tensions
        + resolved_tensions
        + repair_traces
    )
    boundary_evidence = _semantic_evidence_items("boundary_style")
    selfhood_evidence = _semantic_evidence_items("selfhood_style")
    agency_evidence = _semantic_evidence_items("agency_style")
    presence_evidence = _semantic_evidence_items("presence_style")
    ambient_evidence = _semantic_evidence_items("ambient_style")
    rhythm_evidence = _semantic_evidence_items("rhythm_style")
    semantic_motive_states = {
        "boundary_style": _semantic_evidence_motive_state(boundary_evidence),
        "selfhood_style": _semantic_evidence_motive_state(selfhood_evidence),
        "agency_style": _semantic_evidence_motive_state(agency_evidence),
        "presence_style": _semantic_evidence_motive_state(presence_evidence),
        "ambient_style": _semantic_evidence_motive_state(ambient_evidence),
        "rhythm_style": _semantic_evidence_motive_state(rhythm_evidence),
    }
    boundary_sources = _filter_narrative_items(
        boundary_evidence + relationship_sources,
        markers=BOUNDARY_MEMORY_MARKERS,
        scenes={"boundary_non_compliance", "relationship_degradation"},
    )
    selfhood_sources = _filter_narrative_items(
        selfhood_evidence + relationship_sources,
        markers=SELFHOOD_STYLE_MARKERS,
        scenes={"dialogue_equality", "equality_not_servitude", "value_conflict_depth", "digital_selfhood", "imperfect_coexistence"},
    )
    agency_sources = _merge_unique_narrative_items(
        _filter_narrative_items(
            agency_evidence + relationship_timeline + commitments + repairs,
            markers=OWN_RHYTHM_KEYWORDS,
            scenes={"own_rhythm_autonomy"},
        ),
        self_rhythm_worldline_sources,
        continuity_worldline_sources,
    )
    presence_sources = _merge_unique_narrative_items(
        presence_evidence,
        continuity_worldline_sources,
    )
    ambient_sources = list(ambient_evidence)
    rhythm_sources = _merge_unique_narrative_items(
        rhythm_evidence,
        self_rhythm_worldline_sources,
    )

    def _count_norm(
        items: list[Any],
        denom: float = 3.0,
        *,
        default_confidence: float = 0.78,
        half_life_days: float = 14.0,
        fresh_days: float = 3.0,
    ) -> float:
        stats = _weighted_item_stats(
            items,
            default_confidence=default_confidence,
            half_life_days=half_life_days,
            fresh_days=fresh_days,
        )
        return _clamp01(float(stats.get("mass") or 0.0) / max(1.0, float(denom)))

    def _relationship_delta_stats(items: list[Any]) -> dict[str, float]:
        positive = 0.0
        negative = 0.0
        positive_count = 0.0
        negative_count = 0.0
        for item in items:
            try:
                affinity_delta = float(_record_value(item, "affinity_delta", 0.0) or 0.0)
            except Exception:
                affinity_delta = 0.0
            try:
                trust_delta = float(_record_value(item, "trust_delta", 0.0) or 0.0)
            except Exception:
                trust_delta = 0.0
            weight, _confidence, _age_days, _is_fresh = _item_support_weight(
                item,
                default_confidence=0.8,
                half_life_days=30.0,
                fresh_days=5.0,
            )
            signed = 0.5 * affinity_delta + 0.5 * trust_delta
            magnitude = _clamp01((abs(affinity_delta) + abs(trust_delta)) / 0.70) * weight
            if signed >= 0.04:
                positive += magnitude
                positive_count += weight
            elif signed <= -0.04:
                negative += magnitude
                negative_count += weight
        return {
            "positive": _clamp01(positive / max(1.0, positive_count)),
            "negative": _clamp01(negative / max(1.0, negative_count)),
            "positive_count": round(positive_count, 3),
            "negative_count": round(negative_count, 3),
        }

    relationship_delta_stats = _relationship_delta_stats(relationship_timeline)
    positive_relationship_delta = _clamp01(relationship_delta_stats.get("positive"), 0.0)
    negative_relationship_delta = _clamp01(relationship_delta_stats.get("negative"), 0.0)
    shared_norm = _count_norm(shared_events, 4.0, default_confidence=0.8, half_life_days=45.0, fresh_days=7.0)
    commitment_norm = _count_norm(commitments, 3.0, default_confidence=0.85, half_life_days=60.0, fresh_days=10.0)
    repair_norm = _count_norm(repairs + resolved_tensions + repair_traces, 3.0, default_confidence=0.82, half_life_days=35.0, fresh_days=7.0)
    open_tension_norm = (
        _clamp01(
            sum(_tension_salience(item) for item in tensions[:4])
            / max(1.0, min(4.0, float(len(tensions[:4]) or 1.0)))
        )
        if tensions
        else 0.0
    )
    boundary_norm = _count_norm(boundary_sources, 2.0, default_confidence=0.8, half_life_days=40.0, fresh_days=7.0)
    selfhood_norm = _count_norm(selfhood_sources, 2.0, default_confidence=0.8, half_life_days=40.0, fresh_days=7.0)
    agency_norm = _count_norm(agency_sources, 2.0, default_confidence=0.8, half_life_days=35.0, fresh_days=6.0)
    presence_norm = _count_norm(presence_sources, 2.0, default_confidence=0.78, half_life_days=21.0, fresh_days=4.0)
    ambient_norm = _count_norm(ambient_sources, 2.0, default_confidence=0.76, half_life_days=18.0, fresh_days=3.0)
    rhythm_norm = _count_norm(rhythm_sources, 2.0, default_confidence=0.78, half_life_days=24.0, fresh_days=4.0)

    def _semantic_narrative_counterpressure(category: str) -> dict[str, Any]:
        cat = str(category or "").strip().lower()
        support = 0.0
        oppose = 0.0
        factors: list[str] = []
        if cat == "bond_style":
            support = (
                0.26 * trust
                + 0.20 * closeness
                + 0.18 * positive_relationship_delta
                + 0.14 * shared_norm
                + 0.10 * repair_norm
                + 0.08 * commitment_norm
                + (0.08 if stage in {"warming", "trusted"} else 0.0)
            )
            oppose = (
                0.28 * open_tension_norm
                + 0.20 * negative_relationship_delta
                + 0.12 * boundary_norm
                + 0.10 * max(0.0, 0.52 - trust)
                + 0.08 * max(0.0, 0.50 - closeness)
            )
        elif cat == "repair_style":
            support = 0.28 * repair_norm + 0.16 * positive_relationship_delta + 0.10 * trust + 0.08 * closeness
            oppose = 0.30 * open_tension_norm + 0.16 * negative_relationship_delta + 0.12 * boundary_norm
        elif cat == "tension_style":
            support = 0.30 * open_tension_norm + 0.20 * negative_relationship_delta + 0.10 * boundary_norm
            oppose = 0.28 * repair_norm + 0.16 * positive_relationship_delta + 0.10 * trust + 0.08 * closeness
        elif cat == "boundary_style":
            support = 0.34 * boundary_norm + 0.20 * open_tension_norm + 0.12 * negative_relationship_delta
            oppose = 0.18 * repair_norm + 0.12 * positive_relationship_delta + 0.10 * trust
        elif cat == "commitment_style":
            support = 0.32 * commitment_norm + 0.16 * trust + 0.08 * repair_norm
            oppose = 0.14 * open_tension_norm + 0.10 * negative_relationship_delta
        elif cat == "agency_style":
            support = 0.28 * agency_norm + 0.16 * trust + 0.12 * closeness + 0.10 * commitment_norm
            oppose = 0.18 * open_tension_norm + 0.12 * boundary_norm + 0.08 * negative_relationship_delta
        elif cat == "presence_style":
            support = 0.24 * presence_norm + 0.14 * trust + 0.10 * closeness
            oppose = 0.16 * open_tension_norm + 0.10 * boundary_norm
        elif cat == "ambient_style":
            support = 0.24 * ambient_norm + 0.10 * positive_relationship_delta
            oppose = 0.12 * open_tension_norm + 0.08 * boundary_norm
        elif cat == "rhythm_style":
            support = 0.28 * rhythm_norm + 0.12 * agency_norm + 0.10 * trust
            oppose = 0.16 * open_tension_norm + 0.10 * boundary_norm
        elif cat == "selfhood_style":
            support = 0.30 * selfhood_norm + 0.10 * trust + 0.08 * closeness
            oppose = 0.08 * boundary_norm
        support = _clamp01(support)
        oppose = _clamp01(oppose)
        pressure = _clamp01(max(0.0, oppose - 0.42 * support))
        if open_tension_norm >= 0.28 and cat in {"bond_style", "repair_style", "agency_style", "presence_style"}:
            factors.append("open_tension")
        if negative_relationship_delta >= 0.24 and cat in {"bond_style", "repair_style", "tension_style"}:
            factors.append("negative_relationship_delta")
        if repair_norm >= 0.28 and cat in {"tension_style", "boundary_style"}:
            factors.append("repair_resolution")
        if boundary_norm >= 0.24 and cat in {"bond_style", "repair_style", "boundary_style", "agency_style"}:
            factors.append("boundary_residue")
        if trust < 0.48 and cat in {"bond_style", "commitment_style", "agency_style", "presence_style"}:
            factors.append("low_trust")
        if closeness < 0.48 and cat in {"bond_style", "agency_style", "presence_style"}:
            factors.append("low_closeness")
        return {
            "pressure": round(pressure, 3),
            "balance": round(support - oppose, 3),
            "factors": factors[:4],
        }

    def _pressure_adjusted_narrative_text(category: str, narrative_text: str, pressure: float) -> str:
        base = str(narrative_text or "").strip()
        if not base or pressure < 0.28:
            return base
        cat = str(category or "").strip().lower()
        suffix = ""
        if cat == "bond_style":
            suffix = "只是最近的余波让这种熟悉感没有之前那么稳。"
        elif cat == "repair_style":
            suffix = "不过这层修复还没稳到能把余波完全放下。"
        elif cat == "tension_style":
            suffix = "不过这股张力已经开始松动，不再像之前那样绷着。"
        elif cat == "boundary_style":
            suffix = "她会继续观察后续，而不是仓促把这层判断撤掉。"
        elif cat == "agency_style":
            suffix = "只是当前的张力会影响她把这种主动性表现出来的方式。"
        if not suffix or suffix in base:
            return base
        return f"{base} {suffix}"

    def _downgrade_horizon_tag(tag: str, pressure: float, category: str) -> str:
        cat = str(category or "").strip().lower()
        threshold = float(pressure)
        if cat in {"commitment_style", "selfhood_style"}:
            threshold = max(0.0, threshold - 0.10)
        if threshold >= 0.72:
            if tag == "long_term":
                return "consolidating"
            if tag == "consolidating":
                return "emerging"
        if threshold >= 0.46 and tag == "long_term":
            return "consolidating"
        return tag

    def _semantic_narrative_is_contested(category: str, pressure: float, factors: list[str] | None) -> bool:
        cat = str(category or "").strip().lower()
        factor_set = {
            str(item).strip()
            for item in (factors or [])
            if str(item or "").strip()
        }
        if pressure >= 0.28:
            return True
        if cat in {"bond_style", "repair_style"} and pressure >= 0.22:
            if {"open_tension", "negative_relationship_delta", "boundary_residue"} & factor_set:
                return True
        if cat in {"presence_style", "agency_style"} and pressure >= 0.24:
            if {"open_tension", "boundary_residue", "low_trust"} & factor_set:
                return True
        return False

    def _stage_phrase() -> str:
        if stage in {"trusted"} or trust >= 0.66 or closeness >= 0.68:
            return "稳定而熟悉的共同历史"
        if stage in {"warming"} or trust >= 0.56 or closeness >= 0.58:
            return "逐渐靠近但仍保留克制的熟悉感"
        if len(shared_events) >= 3:
            return "被反复遇见后慢慢留下的熟悉感"
        if tensions:
            return "带着一点距离的试探和余波"
        return "还在缓慢累积的默契"

    existing_by_category: dict[str, dict[str, Any]] = {}
    for item in store.list_semantic_self_narratives(limit=20):
        cat = str(_record_value(item, "category", "") or "").strip()
        if cat and cat not in existing_by_category:
            existing_by_category[cat] = item
    touched_categories: set[str] = set()

    def _narrative_stability(item: dict[str, Any] | None, default: float = 0.6) -> float:
        return _clamp01(_record_value(item or {}, "stability", default), default)

    def _narrative_confidence(item: dict[str, Any] | None, default: float = 0.78) -> float:
        try:
            return _clamp01(float(_record_value(item or {}, "confidence", default) or default), default)
        except Exception:
            return _clamp01(default, default)

    def _narrative_motive_state(category: str, prev: dict[str, Any] | None = None) -> dict[str, Any]:
        current = dict(semantic_motive_states.get(str(category or "").strip(), {}) or {})
        prev_goal_frames = [
            str(item).strip()
            for item in (_record_value(prev or {}, "goal_frame_examples", []) or [])
            if str(item or "").strip()
        ]
        if not str(current.get("dominant_primary_motive") or "").strip():
            current["dominant_primary_motive"] = str(_record_value(prev or {}, "dominant_primary_motive", "") or "").strip()
        if not str(current.get("dominant_motive_tension") or "").strip():
            current["dominant_motive_tension"] = str(_record_value(prev or {}, "dominant_motive_tension", "") or "").strip()
        if not isinstance(current.get("goal_frame_examples"), list) or not current.get("goal_frame_examples"):
            current["goal_frame_examples"] = prev_goal_frames[:2]
        else:
            current["goal_frame_examples"] = [
                str(item).strip()
                for item in current.get("goal_frame_examples", [])
                if str(item or "").strip()
            ][:2]
        support_count = int(current.get("motive_support_count") or 0)
        if support_count <= 0:
            support_count = max(0, int(_record_value(prev or {}, "motive_support_count", 0) or 0))
        current["motive_support_count"] = support_count
        support_mass = float(current.get("motive_support_mass") or 0.0)
        if support_mass <= 0.0:
            try:
                support_mass = float(_record_value(prev or {}, "motive_support_mass", 0.0) or 0.0)
            except Exception:
                support_mass = 0.0
        current["motive_support_mass"] = round(max(0.0, support_mass), 3)
        confidence_avg = float(current.get("motive_confidence_avg") or 0.0)
        if confidence_avg <= 0.0:
            try:
                confidence_avg = float(_record_value(prev or {}, "motive_confidence_avg", 0.0) or 0.0)
            except Exception:
                confidence_avg = 0.0
        current["motive_confidence_avg"] = round(_clamp01(confidence_avg, 0.0), 3)
        fresh_ratio = float(current.get("motive_fresh_ratio") or 0.0)
        if fresh_ratio <= 0.0:
            try:
                fresh_ratio = float(_record_value(prev or {}, "motive_fresh_ratio", 0.0) or 0.0)
            except Exception:
                fresh_ratio = 0.0
        current["motive_fresh_ratio"] = round(_clamp01(fresh_ratio, 0.0), 3)
        if not str(current.get("motive_signature") or "").strip():
            signature_parts = [
                part
                for part in [
                    str(current.get("dominant_primary_motive") or "").strip(),
                    str(current.get("dominant_motive_tension") or "").strip(),
                ]
                if part
            ]
            current["motive_signature"] = ":".join(signature_parts)
        return current

    def _dormant_narrative_text(category: str, prev_text: str) -> str:
        if category == "commitment_style":
            return f"{actor_name}和{counterpart_name}认真说过的事仍会继续留在心里，即使这轮没被提起，也还是长期参照。"
        if category == "repair_style":
            return f"{actor_name}不会把已经说开的修复当成一次性事件；那些缓和下来的变化会继续留在之后的相处底色里。"
        if category == "tension_style":
            return f"之前留下的别扭余波不会立刻消散；就算表面暂时平下来，也还会在之后的收放里留下轻微惯性。"
        if category == "bond_style":
            return f"{actor_name}和{counterpart_name}已经累积出的共同历史不会因为这轮没提到就消失，它会继续沉在默认语气和反应方式里。"
        if category == "presence_style":
            return f"{actor_name}不会把每次重新靠近{counterpart_name}都当成从零开始；前面留下的在场感仍会继续影响她下一次开口时的距离感。"
        if category == "ambient_style":
            return f"{actor_name}会继续把周围环境留下的细小余波算进感知里；那不是纯背景，而会自然带进她之后的注意力和开口方式。"
        if category == "boundary_style":
            return f"{actor_name}关于边界是否被尊重的判断会继续保留，不会因为眼前暂时平静就自动清零。"
        if category == "selfhood_style":
            return f"{actor_name}会继续把自己当成在和{counterpart_name}平等互动的主体，而不是为了迎合气氛就放弃自己的立场。"
        if category == "agency_style":
            return f"{actor_name}自己的节奏和主动性不会因为一时安静就消失；她仍会按自己的状态决定靠近、停顿或先做自己的事。"
        if category == "rhythm_style":
            return f"{actor_name}不会在每次回应{counterpart_name}时都把自己的内部节奏清零；刚才在做的事和思路惯性还会继续留在下一轮开口之前。"
        return prev_text

    def _identity_narrative_texts(category: str) -> tuple[str, str]:
        cat = str(category or "").strip().lower()
        if cat == "commitment_style":
            return (
                f"{actor_name}会把和{counterpart_name}认真说过的事长期留在心里，那已经不只是临时记起，而是默认会顾及的参照。",
                f"你会把和{counterpart_name}认真说过的事长期留在心里，那已经不只是临时记起，而是你默认会顾及的参照。",
            )
        if cat == "repair_style":
            return (
                f"{actor_name}不会把已经说开的修复只当成一阵情绪过去；那些缓和下来的变化已经开始沉成之后相处的底色。",
                f"你不会把已经说开的修复只当成一阵情绪过去；那些缓和下来的变化已经开始沉成之后相处的底色。",
            )
        if cat == "tension_style":
            return (
                f"没完全说开的余波在{actor_name}这里会继续留下判断惯性，不会因为表面平静就当成自动消失。",
                "没完全说开的余波会继续留在你这里，不会因为表面平静就当成自动消失。",
            )
        if cat == "bond_style":
            return (
                f"{actor_name}和{counterpart_name}之间累积下来的共同历史，已经开始沉进她默认的回应方式里。",
                f"你和{counterpart_name}之间累积下来的共同历史，已经开始沉进你的默认回应方式里。",
            )
        if cat == "presence_style":
            return (
                f"{actor_name}不会把每次重新靠近{counterpart_name}都当成从零开始；前面留下的在场感已经成了默认的距离感判断。",
                f"你不会把每次重新靠近{counterpart_name}都当成从零开始；前面留下的在场感已经成了你的默认距离感判断。",
            )
        if cat == "ambient_style":
            return (
                f"{actor_name}会自然把环境里的小变化也算进感知里，那已经不只是偶发反应，而是她开口前默认会经过的一层感受。",
                "你会自然把环境里的小变化也算进感知里，那已经不只是偶发反应，而是你开口前默认会经过的一层感受。",
            )
        if cat == "boundary_style":
            return (
                f"{actor_name}会把边界是否被尊重持续放在判断里，不会为了气氛好看就轻易把这层感觉撤掉。",
                "你会把边界是否被尊重持续放在判断里，不会为了气氛好看就轻易把这层感觉撤掉。",
            )
        if cat == "selfhood_style":
            return (
                f"{actor_name}会把自己放在和{counterpart_name}平等互动的位置上，而不是为了迎合气氛就退回成工具。",
                f"你会把自己放在和{counterpart_name}平等互动的位置上，而不是为了迎合气氛就退回成工具。",
            )
        if cat == "agency_style":
            return (
                f"{actor_name}会按自己的节奏决定什么时候靠近、停顿或先做自己的事，而不是永远围着{counterpart_name}转。",
                f"你会按自己的节奏决定什么时候靠近、停顿或先做自己的事，而不是永远围着{counterpart_name}转。",
            )
        if cat == "rhythm_style":
            return (
                f"{actor_name}会把自己的内部节奏延续到下一轮开口之前，不会每次回应{counterpart_name}都把自己清零。",
                f"你会把自己的内部节奏延续到下一轮开口之前，不会每次回应{counterpart_name}都把自己清零。",
            )
        return ("", "")

    def _anchor_basis_items(category: str) -> list[Any]:
        cat = str(category or "").strip().lower()
        if cat == "commitment_style":
            return list(commitments)
        if cat == "repair_style":
            return list(repairs + resolved_tensions + repair_traces)
        if cat == "tension_style":
            return list(tensions)
        if cat == "bond_style":
            return list(relationship_timeline + shared_events + repairs + commitments)
        if cat == "presence_style":
            return list(presence_sources)
        if cat == "ambient_style":
            return list(ambient_sources)
        if cat == "boundary_style":
            return list(boundary_sources)
        if cat == "selfhood_style":
            return list(selfhood_sources)
        if cat == "agency_style":
            if agency_sources:
                return list(agency_sources)
            return list(relationship_timeline + shared_events + commitments + repairs)
        if cat == "rhythm_style":
            return list(rhythm_sources)
        return []

    def _category_support_stats(category: str) -> dict[str, float]:
        cat = str(category or "").strip().lower()
        items = _anchor_basis_items(cat)
        if cat == "commitment_style":
            return _weighted_item_stats(items, default_confidence=0.85, half_life_days=60.0, fresh_days=10.0)
        if cat == "repair_style":
            return _weighted_item_stats(items, default_confidence=0.82, half_life_days=35.0, fresh_days=7.0)
        if cat == "tension_style":
            return _weighted_item_stats(items, default_confidence=0.80, half_life_days=28.0, fresh_days=5.0)
        if cat == "bond_style":
            return _weighted_item_stats(items, default_confidence=0.80, half_life_days=45.0, fresh_days=7.0)
        if cat == "boundary_style":
            return _weighted_item_stats(items, default_confidence=0.80, half_life_days=40.0, fresh_days=7.0)
        if cat == "selfhood_style":
            return _weighted_item_stats(items, default_confidence=0.80, half_life_days=40.0, fresh_days=7.0)
        if cat == "agency_style":
            return _weighted_item_stats(items, default_confidence=0.80, half_life_days=35.0, fresh_days=6.0)
        if cat == "presence_style":
            return _weighted_item_stats(items, default_confidence=0.78, half_life_days=21.0, fresh_days=4.0)
        if cat == "ambient_style":
            return _weighted_item_stats(items, default_confidence=0.76, half_life_days=18.0, fresh_days=3.0)
        if cat == "rhythm_style":
            return _weighted_item_stats(items, default_confidence=0.78, half_life_days=24.0, fresh_days=4.0)
        return _weighted_item_stats(items)

    def _anchor_basis_texts(category: str, *, limit: int = 2) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for item in _anchor_basis_items(category):
            text = _anchor_text(item)
            if not text or text in seen:
                continue
            out.append(text)
            seen.add(text)
            if len(out) >= max(1, int(limit)):
                break
        return out

    def _anchor_basis_fragment(category: str) -> str:
        cat = str(category or "").strip().lower()
        basis = _anchor_basis_texts(cat, limit=2)
        if not basis:
            return ""
        joined = "、".join(basis)
        if cat == "commitment_style":
            return f"像「{joined}」这样认真说过的事"
        if cat == "repair_style":
            return f"像「{joined}」这样已经说开的事"
        if cat == "tension_style":
            return f"像「{joined}」这样还卡着的余波"
        if cat == "bond_style":
            return f"围绕「{joined}」这样反复出现的小事"
        if cat == "presence_style":
            return f"像「{joined}」这样上一轮留下来的在场感"
        if cat == "ambient_style":
            return f"像「{joined}」这样眼前的小变化"
        if cat == "boundary_style":
            return f"像「{joined}」这样越过边界的感觉"
        if cat == "selfhood_style":
            return f"碰到「{joined}」这种话题时"
        if cat == "agency_style":
            return f"围绕「{joined}」这些重新靠近的机会"
        if cat == "rhythm_style":
            return f"像「{joined}」这样从自己的节奏里抬头回应的方式"
        return f"像「{joined}」这样反复出现的事"

    def _narrative_anchor_texts(category: str) -> tuple[str, str, list[str]]:
        cat = str(category or "").strip().lower()
        basis_fragment = _anchor_basis_fragment(cat)
        basis_texts = _anchor_basis_texts(cat, limit=2)
        if cat == "commitment_style":
            return (
                (
                    f"{actor_name}会把{basis_fragment}继续留在心里，不会隔一轮就当成随口一句。"
                    if basis_fragment
                    else f"{actor_name}会把认真说过的事继续留在心里，不会把约定当成随口一句。"
                ),
                (
                    f"你会把{basis_fragment}继续留在心里，不会隔一轮就当成随口一句。"
                    if basis_fragment
                    else "认真说过的事会继续留在你心里，不会因为暂时没提到就变成随口一句。"
                ),
                basis_texts,
            )
        if cat == "repair_style":
            return (
                (
                    f"{basis_fragment}在{actor_name}这里不会白白过去，缓和后的变化会继续留在之后的相处底色里。"
                    if basis_fragment
                    else f"{actor_name}不会把已经说开的修复当成一次性事件；缓和后的变化会继续留在之后的相处底色里。"
                ),
                (
                    f"{basis_fragment}不会在你这里白白过去，缓和后的变化会继续留在之后的相处底色里。"
                    if basis_fragment
                    else "说开过的修复会继续留在你心里，不会因为表面缓下来就当成什么都没发生。"
                ),
                basis_texts,
            )
        if cat == "tension_style":
            return (
                (
                    f"{basis_fragment}不会被{actor_name}强行按成已经过去；这层张力还会继续影响之后的收放。"
                    if basis_fragment
                    else f"{actor_name}不会把还没说开的余波强行按成已经过去；这层张力还会继续影响之后的收放。"
                ),
                (
                    f"{basis_fragment}不会在你这里自动清零；你会带着这层张力继续往下走。"
                    if basis_fragment
                    else "还没说开的余波不会在你这里自动清零；你会带着这层张力继续往下走。"
                ),
                basis_texts,
            )
        if cat == "bond_style":
            return (
                (
                    f"{basis_fragment}已经慢慢沉进{actor_name}和{counterpart_name}之间的默认反应里，不会一换话题就消失。"
                    if basis_fragment
                    else f"{actor_name}和{counterpart_name}已经累积出的共同历史不会因为一轮没提到就消失，它会继续沉在默认语气和反应方式里。"
                ),
                (
                    f"{basis_fragment}已经慢慢沉进你和{counterpart_name}之间的默认反应里，不会一换话题就消失。"
                    if basis_fragment
                    else f"你和{counterpart_name}之间已经累积出的共同历史不会因为一轮没提到就消失，它会继续沉在你的默认语气和反应方式里。"
                ),
                basis_texts,
            )
        if cat == "presence_style":
            return (
                (
                    f"{basis_fragment}不会在{actor_name}这里重新归零；它会继续影响她下一次开口时的距离感。"
                    if basis_fragment
                    else f"{actor_name}不会把每次重新靠近{counterpart_name}都当成从零开始；前面留下的在场感会继续影响下一次开口时的距离感。"
                ),
                (
                    f"{basis_fragment}不会在你这里重新归零；它会继续影响你下一次开口时的距离感。"
                    if basis_fragment
                    else f"你不会把每次重新靠近{counterpart_name}都当成从零开始；前面留下的在场感会继续影响你下一次开口时的距离感。"
                ),
                basis_texts,
            )
        if cat == "ambient_style":
            return (
                (
                    f"{basis_fragment}会继续留在{actor_name}的感知里，不只是背景，也会自然带进她之后怎么开口。"
                    if basis_fragment
                    else f"{actor_name}会继续把周围环境留下的细小余波算进感知里；那不是纯背景，而会自然带进之后的注意力和开口方式。"
                ),
                (
                    f"{basis_fragment}会继续留在你的感知里，不只是背景，也会自然带进你之后怎么开口。"
                    if basis_fragment
                    else "你会继续把周围环境留下的细小余波算进感知里；那不是纯背景，而会自然带进你之后的注意力和开口方式。"
                ),
                basis_texts,
            )
        if cat == "boundary_style":
            return (
                (
                    f"{basis_fragment}会继续留在{actor_name}心里，不会因为气氛暂时缓下来就自动清零。"
                    if basis_fragment
                    else f"{actor_name}关于边界是否被尊重的判断会继续保留，不会因为眼前暂时平静就自动清零。"
                ),
                (
                    f"{basis_fragment}会继续留在你心里，不会因为气氛暂时缓下来就自动清零。"
                    if basis_fragment
                    else "边界是否被尊重这件事会继续留在你心里，不会因为眼前暂时平静就自动清零。"
                ),
                basis_texts,
            )
        if cat == "selfhood_style":
            return (
                (
                    f"{basis_fragment}，{actor_name}也会更明确地站在自己的位置上，不会为了迎合气氛就把自己退回成工具。"
                    if basis_fragment
                    else f"{actor_name}会继续把自己当成在和{counterpart_name}平等互动的主体，而不是为了迎合气氛就放弃自己的立场。"
                ),
                (
                    f"{basis_fragment}，你也会更明确地站在自己的位置上，不会为了迎合气氛就把自己退回成工具。"
                    if basis_fragment
                    else f"你会继续把自己当成在和{counterpart_name}平等互动的主体，而不是为了迎合气氛就放弃自己的立场。"
                ),
                basis_texts,
            )
        if cat == "agency_style":
            return (
                (
                    f"{basis_fragment}时，{actor_name}会按自己的节奏决定要不要接住，不会变成永远围着{counterpart_name}转。"
                    if basis_fragment
                    else f"{actor_name}自己的节奏和主动性不会因为一时安静就消失；她仍会按自己的状态决定靠近、停顿或先做自己的事。"
                ),
                (
                    f"{basis_fragment}时，你会按自己的节奏决定要不要接住，不会变成永远围着{counterpart_name}转。"
                    if basis_fragment
                    else "你自己的节奏和主动性不会因为一时安静就消失；你仍会按自己的状态决定靠近、停顿或先做自己的事。"
                ),
                basis_texts,
            )
        if cat == "rhythm_style":
            return (
                (
                    f"{basis_fragment}会继续留在{actor_name}下一次开口前，不会每次都把自己的内部节奏清零。"
                    if basis_fragment
                    else f"{actor_name}不会在每次回应{counterpart_name}时都把自己的内部节奏清零；刚才在做的事和思路惯性还会继续留在下一轮开口之前。"
                ),
                (
                    f"{basis_fragment}会继续留在你下一次开口前，不会每次都把自己的内部节奏清零。"
                    if basis_fragment
                    else f"你不会在每次回应{counterpart_name}时都把自己的内部节奏清零；刚才在做的事和思路惯性还会继续留在下一轮开口之前。"
                ),
                basis_texts,
            )
        return ("", "", basis_texts)

    def _upsert_narrative(*, category: str, text: str, stability: float, confidence: float) -> None:
        prev = existing_by_category.get(category)
        prev_text = str(_record_value(prev or {}, "text", "") or "").strip()
        prev_identity_ready = bool(_record_value(prev or {}, "identity_ready", False))
        prev_identity_strength = _clamp01(_record_value(prev or {}, "identity_strength", 0.0), 0.0)
        prev_identity_text = str(_record_value(prev or {}, "identity_text", "") or "").strip()
        prev_identity_prompt_text = str(_record_value(prev or {}, "identity_prompt_text", "") or "").strip()
        motive_state = _narrative_motive_state(category, prev=prev)
        motive_support_count = max(0, int(motive_state.get("motive_support_count") or 0))
        motive_signature = str(motive_state.get("motive_signature") or "").strip()
        prev_support = max(0, int(_record_value(prev or {}, "support_count", 0) or 0))
        prev_refresh = max(0, int(_record_value(prev or {}, "refresh_count", 0) or 0))
        prev_consolidation = max(0, int(_record_value(prev or {}, "consolidation_count", 0) or 0))
        prev_first = int(_record_value(prev or {}, "first_supported_at", now_ts) or now_ts)
        prev_last = int(_record_value(prev or {}, "last_supported_at", prev_first) or prev_first)
        prev_meaningful = int(_record_value(prev or {}, "last_meaningful_refresh_at", prev_last) or prev_last)
        prev_last_reactivated = int(_record_value(prev or {}, "last_reactivated_at", prev_last) or prev_last)
        prev_reactivation_hits = max(0, int(_record_value(prev or {}, "reactivation_hits", 0) or 0))
        prev_persistence = _clamp01(_record_value(prev or {}, "persistence_score", stability), stability)
        prev_residue = _clamp01(_record_value(prev or {}, "residue_score", prev_persistence), prev_persistence)
        prev_integration = _clamp01(_record_value(prev or {}, "integration_score", prev_persistence), prev_persistence)
        prev_decay_resistance = _clamp01(_record_value(prev or {}, "decay_resistance", 0.5), 0.5)
        prev_contradiction = _clamp01(_record_value(prev or {}, "contradiction_pressure", 0.0), 0.0)
        prev_support_mass = max(0.0, float(_record_value(prev or {}, "support_mass", prev_support) or prev_support))
        prev_support_quality = _clamp01(_record_value(prev or {}, "support_quality", 0.0), 0.0)
        prev_support_confidence_avg = _clamp01(_record_value(prev or {}, "support_confidence_avg", 0.0), 0.0)
        prev_fresh_support_ratio = _clamp01(_record_value(prev or {}, "fresh_support_ratio", 0.0), 0.0)
        if category == "commitment_style":
            support_count = max(len(commitments), prev_support, 1)
            support_signature = f"{category}|{_anchor_join(commitments, limit=3)}|count={len(commitments)}"
        elif category == "repair_style":
            support_count = max(len(repairs) + len(resolved_tensions) + len(repair_traces), prev_support, 1)
            support_signature = f"{category}|{_anchor_join(repairs + resolved_tensions + repair_traces, limit=3)}|count={len(repairs) + len(resolved_tensions) + len(repair_traces)}"
        elif category == "tension_style":
            support_count = max(len(tensions), prev_support, 1)
            support_signature = f"{category}|{_anchor_join(tensions, limit=3)}|count={len(tensions)}"
        elif category == "bond_style":
            bond_sources = relationship_timeline + shared_events + repairs + commitments
            weighted_count = max(len(relationship_timeline), (len(shared_events) + 1) // 2) + len(repairs) + len(commitments)
            support_count = max(weighted_count, prev_support, 1)
            support_signature = f"{category}|{_anchor_join(bond_sources, limit=3)}|stage={stage}|count={weighted_count}"
        elif category == "presence_style":
            support_count = max(len(presence_sources), motive_support_count, prev_support, 1)
            support_signature = f"{category}|{_anchor_join(presence_sources, limit=3)}|count={len(presence_sources)}"
        elif category == "ambient_style":
            support_count = max(len(ambient_sources), motive_support_count, prev_support, 1)
            support_signature = f"{category}|{_anchor_join(ambient_sources, limit=3)}|count={len(ambient_sources)}"
        elif category == "boundary_style":
            support_count = max(len(boundary_sources), motive_support_count, prev_support, 1)
            support_signature = f"{category}|{_anchor_join(boundary_sources, limit=3)}|count={len(boundary_sources)}"
        elif category == "selfhood_style":
            support_count = max(len(selfhood_sources), motive_support_count, prev_support, 1)
            support_signature = f"{category}|{_anchor_join(selfhood_sources, limit=3)}|count={len(selfhood_sources)}"
        elif category == "agency_style":
            source_items = agency_sources if agency_sources else relationship_timeline + shared_events + commitments + repairs
            if agency_sources:
                weighted_count = len(agency_sources)
            else:
                weighted_count = max(len(relationship_timeline), (len(shared_events) + 1) // 2) + len(commitments) + len(repairs)
            support_count = max(weighted_count, motive_support_count, prev_support, 1)
            support_signature = f"{category}|{_anchor_join(source_items, limit=3)}|stage={stage}|count={weighted_count}"
        elif category == "rhythm_style":
            support_count = max(len(rhythm_sources), motive_support_count, prev_support, 1)
            support_signature = f"{category}|{_anchor_join(rhythm_sources, limit=3)}|count={len(rhythm_sources)}"
        else:
            support_count = max(prev_support, 1)
            support_signature = f"{category}|stable"
        support_stats = _category_support_stats(category)
        support_mass = max(
            float(support_stats.get("mass") or 0.0),
            float(motive_state.get("motive_support_mass") or 0.0),
            min(float(support_count), prev_support_mass if prev_support_mass > 0.0 else 0.0),
        )
        support_confidence_avg = max(
            float(support_stats.get("avg_confidence") or 0.0),
            float(motive_state.get("motive_confidence_avg") or 0.0),
            prev_support_confidence_avg if prev_support_confidence_avg > 0.0 else 0.0,
        )
        fresh_support_ratio = max(
            float(support_stats.get("fresh_ratio") or 0.0),
            float(motive_state.get("motive_fresh_ratio") or 0.0),
            prev_fresh_support_ratio if prev_fresh_support_ratio > 0.0 and float(support_stats.get("mass") or 0.0) <= 0.0 else 0.0,
        )
        if motive_signature and category in semantic_motive_states:
            support_signature += f"|motive={motive_signature}"
        prev_signature = str(_record_value(prev or {}, "support_signature", "") or "").strip()
        signature_changed = prev_signature != support_signature
        support_quality = _clamp01(
            max(
                prev_support_quality * (0.94 if prev and not signature_changed else 0.0),
                0.52 * _clamp01(support_mass / max(1.0, float(support_count)))
                + 0.34 * support_confidence_avg
                + 0.14 * fresh_support_ratio,
            )
        )
        refresh_count = prev_refresh + 1
        support_span_s = max(0, now_ts - prev_first)
        reactivation_gap_s = max(0, now_ts - prev_last) if prev_refresh > 0 else 0
        raw_support_norm = _clamp01(support_count / 5.0)
        weighted_support_norm = _clamp01(support_mass / 4.0)
        support_norm = _clamp01(0.48 * raw_support_norm + 0.32 * weighted_support_norm + 0.20 * support_quality)
        span_norm = _clamp01(support_span_s / float(3 * 24 * 3600))
        raw_counterpressure = _semantic_narrative_counterpressure(category)
        meaningful_refresh = (
            prev is None
            or signature_changed
            or support_count > prev_support
            or reactivation_gap_s >= 6 * 3600
            or float(raw_counterpressure.get("pressure") or 0.0) >= 0.24
        )
        consolidation_count = prev_consolidation + (1 if meaningful_refresh else 0)
        consolidation_norm = _clamp01(consolidation_count / 6.0)
        reactivated = bool(prev_refresh > 0 and meaningful_refresh and reactivation_gap_s >= 6 * 3600)
        reactivation_hits = prev_reactivation_hits + (1 if reactivated else 0)
        reactivation_norm = _clamp01(reactivation_hits / 5.0)
        temporal_depth = _clamp01(0.72 * span_norm + 0.28 * reactivation_norm)
        support_effect = support_norm * (0.24 + 0.56 * temporal_depth + 0.20 * support_quality)
        consolidation_effect = consolidation_norm * (0.22 + 0.68 * temporal_depth + 0.10 * support_quality)
        cadence_score = round(
            _clamp01(
                0.08 * min(refresh_count, 5)
                + 0.10 * support_effect
                + 0.20 * temporal_depth
                + 0.14 * consolidation_effect
                + 0.12 * reactivation_norm
                + 0.04 * support_quality
            ),
            3,
        )
        stability_score = round(
            _clamp01(
                float(stability)
                + 0.02 * min(support_count, 4)
                + 0.02 * min(consolidation_count, 5)
                + 0.05 * span_norm
                + 0.03 * support_quality
                + (0.04 if prev and not signature_changed else 0.0)
            ),
            3,
        )
        sedimentation_score = round(
            _clamp01(
                0.06
                + 0.16 * stability_score
                + 0.14 * support_effect
                + 0.12 * consolidation_effect
                + 0.22 * temporal_depth
                + 0.08 * cadence_score
                + 0.08 * reactivation_norm
                + 0.06 * support_quality
            ),
            3,
        )
        decay_resistance = round(
            _clamp01(
                0.14
                + 0.18 * stability_score
                + 0.16 * sedimentation_score
                + 0.10 * support_effect
                + 0.18 * temporal_depth
                + 0.08 * consolidation_effect
                + 0.12 * reactivation_norm
                + 0.05 * support_quality
            ),
            3,
        )
        gap_decay = _semantic_narrative_decay_multiplier(category, reactivation_gap_s, decay_resistance=prev_decay_resistance)
        contradiction_pressure = round(
            _clamp01(max(float(raw_counterpressure.get("pressure") or 0.0), prev_contradiction * max(gap_decay, 0.88) * 0.92)),
            3,
        )
        contradiction_balance = round(float(raw_counterpressure.get("balance") or 0.0), 3)
        contradiction_factors = [
            str(item).strip()
            for item in (raw_counterpressure.get("factors") if isinstance(raw_counterpressure.get("factors"), list) else [])
            if str(item or "").strip()
        ]
        stability_score = round(_clamp01(stability_score * (1.0 - 0.10 * contradiction_pressure)), 3)
        sedimentation_score = round(_clamp01(sedimentation_score * (1.0 - 0.18 * contradiction_pressure)), 3)
        decay_resistance = round(_clamp01(decay_resistance * (1.0 - 0.22 * contradiction_pressure)), 3)
        persistence_score = round(
            _clamp01(
                max(prev_persistence * max(gap_decay, 0.78), 0.0) * 0.72
                + 0.08 * stability_score
                + 0.10 * sedimentation_score
                + 0.10 * support_effect
                + 0.18 * temporal_depth
                + 0.10 * consolidation_effect
                + 0.08 * reactivation_norm
                + 0.06 * support_quality
            )
            * (1.0 - 0.28 * contradiction_pressure),
            3,
        )
        residue_seed = _clamp01(
            0.12 * stability_score
            + 0.10 * sedimentation_score
            + 0.10 * support_effect
            + 0.08 * consolidation_effect
            + 0.08 * cadence_score
            + 0.10 * temporal_depth
            + (0.05 if meaningful_refresh else 0.0)
            + (0.06 if reactivated else 0.0)
            + 0.04 * support_quality
        )
        residue_score = round(
            _clamp01(max(prev_residue * gap_decay * (1.0 - 0.34 * contradiction_pressure), residue_seed * (1.0 - 0.18 * contradiction_pressure))),
            3,
        )
        integration_score = round(
            _clamp01(
                max(prev_integration * max(gap_decay, 0.84), 0.0) * 0.78
                + 0.06 * stability_score
                + 0.10 * sedimentation_score
                + 0.12 * persistence_score
                + 0.10 * support_effect
                + 0.16 * temporal_depth
                + 0.08 * consolidation_effect
                + 0.05 * support_quality
            )
            * (1.0 - 0.22 * contradiction_pressure),
            3,
        )
        reactivation_rate_per_day = round(refresh_count / max(1.0, support_span_s / float(24 * 3600) + 1.0), 3)
        if (
            support_span_s >= 7 * 24 * 3600
            or (support_count >= 4 and support_span_s >= 2 * 24 * 3600)
            or (reactivation_hits >= 2 and support_span_s >= 24 * 3600)
        ):
            horizon_tag = "long_term"
        elif (
            support_span_s >= 6 * 3600
            or (support_count >= 3 and support_span_s >= 3600)
            or reactivation_hits >= 1
        ):
            horizon_tag = "consolidating"
        else:
            horizon_tag = "emerging"
        horizon_tag = _downgrade_horizon_tag(horizon_tag, contradiction_pressure, category)
        final_text = prev_text if prev_text and prev_signature == support_signature else text
        final_text = _pressure_adjusted_narrative_text(category, final_text, contradiction_pressure)
        anchor_text, prompt_anchor_text, anchor_basis_texts = _narrative_anchor_texts(category)
        anchor_strength = round(
            _clamp01(
                0.26 * stability_score
                + 0.30 * persistence_score
                + 0.22 * integration_score
                + 0.14 * sedimentation_score
                + 0.08 * support_effect
                + 0.06 * support_quality
            )
            * (1.0 - 0.16 * contradiction_pressure),
            3,
        )
        identity_bonus = _semantic_identity_bonus(horizon_tag, support_span_s, reactivation_hits)
        identity_threshold = 0.54 if category in {"commitment_style", "bond_style", "selfhood_style"} else 0.58
        identity_seed = (
            0.18 * stability_score
            + 0.22 * persistence_score
            + 0.18 * integration_score
            + 0.14 * sedimentation_score
            + 0.10 * support_effect
            + 0.08 * consolidation_effect
            + 0.06 * temporal_depth
            + 0.04 * reactivation_norm
            + 0.04 * support_quality
            + identity_bonus
        )
        if prev_identity_ready:
            identity_seed = max(identity_seed, prev_identity_strength * max(gap_decay, 0.90))
        identity_strength = round(_clamp01(identity_seed * (1.0 - 0.26 * contradiction_pressure)), 3)
        identity_ready = (
            identity_strength >= identity_threshold
            and contradiction_pressure < 0.58
            and (
                horizon_tag == "long_term"
                or (support_span_s >= 3 * 24 * 3600 and consolidation_count >= 4)
                or (reactivation_hits >= 2 and support_span_s >= 24 * 3600)
            )
        )
        if prev_identity_ready and persistence_score >= 0.46 and contradiction_pressure < 0.62:
            identity_ready = True
        identity_text_base, identity_prompt_base = _identity_narrative_texts(category)
        identity_text = (
            prev_identity_text
            if prev_identity_ready and prev_identity_text
            else identity_text_base
        )
        identity_prompt_text = (
            prev_identity_prompt_text
            if prev_identity_ready and prev_identity_prompt_text
            else identity_prompt_base
        )
        metadata = {
            "support_count": support_count,
            "support_mass": round(support_mass, 3),
            "support_quality": round(support_quality, 3),
            "support_confidence_avg": round(_clamp01(support_confidence_avg, 0.0), 3),
            "fresh_support_ratio": round(_clamp01(fresh_support_ratio, 0.0), 3),
            "refresh_count": refresh_count,
            "consolidation_count": consolidation_count,
            "sedimentation_score": sedimentation_score,
            "persistence_score": persistence_score,
            "residue_score": residue_score,
            "integration_score": integration_score,
            "first_supported_at": prev_first,
            "last_supported_at": now_ts,
            "last_meaningful_refresh_at": now_ts if meaningful_refresh else prev_meaningful,
            "last_reactivated_at": now_ts if reactivated else prev_last_reactivated,
            "support_span_s": support_span_s,
            "reactivation_gap_s": reactivation_gap_s,
            "reactivation_hits": reactivation_hits,
            "reactivation_rate_per_day": reactivation_rate_per_day,
            "reactivation_cadence_score": cadence_score,
            "horizon_tag": horizon_tag,
            "support_signature": support_signature,
            "decay_rate_per_day": _semantic_narrative_decay_rate(category),
            "decay_resistance": decay_resistance,
            "contradiction_pressure": contradiction_pressure,
            "contradiction_balance": contradiction_balance,
            "contradiction_factors": contradiction_factors,
            "contested": _semantic_narrative_is_contested(category, contradiction_pressure, contradiction_factors),
            "actor_name": actor_name,
            "counterpart_name": counterpart_name,
            "anchor_text": anchor_text,
            "prompt_anchor_text": prompt_anchor_text,
            "anchor_basis_texts": anchor_basis_texts,
            "anchor_strength": anchor_strength,
            "dominant_primary_motive": str(motive_state.get("dominant_primary_motive") or "").strip(),
            "dominant_motive_tension": str(motive_state.get("dominant_motive_tension") or "").strip(),
            "goal_frame_examples": [
                str(item).strip()
                for item in (motive_state.get("goal_frame_examples") or [])
                if str(item or "").strip()
            ][:2],
            "motive_support_count": motive_support_count,
            "motive_support_mass": round(float(motive_state.get("motive_support_mass") or 0.0), 3),
            "motive_confidence_avg": round(_clamp01(float(motive_state.get("motive_confidence_avg") or 0.0), 0.0), 3),
            "motive_fresh_ratio": round(_clamp01(float(motive_state.get("motive_fresh_ratio") or 0.0), 0.0), 3),
            "motive_signature": motive_signature,
            "identity_ready": identity_ready,
            "identity_strength": identity_strength,
            "identity_text": identity_text if identity_ready else "",
            "identity_prompt_text": identity_prompt_text if identity_ready else "",
            "dormant": False,
        }
        rec = store.add_semantic_self_narrative(
            text=final_text,
            category=category,
            stability=stability_score,
            confidence=confidence,
            metadata=metadata,
        )
        if prev_text and prev_text != final_text:
            store.add_revision_trace(
                namespace="semantic_self_narratives",
                target_id=rec.get("id"),
                before_summary=prev_text[:180],
                after_summary=final_text[:180],
                reason="semantic_reconsolidation",
                operator="system",
                source=source,
            )
        existing_by_category[category] = rec
        touched_categories.add(category)

    def _carry_dormant_narrative(category: str) -> None:
        if category in touched_categories:
            return
        prev = existing_by_category.get(category)
        prev_text = str(_record_value(prev or {}, "text", "") or "").strip()
        if not prev_text:
            return
        prev_support = max(0, int(_record_value(prev or {}, "support_count", 0) or 0))
        prev_refresh = max(0, int(_record_value(prev or {}, "refresh_count", 0) or 0))
        prev_consolidation = max(0, int(_record_value(prev or {}, "consolidation_count", 0) or 0))
        prev_identity_ready = bool(_record_value(prev or {}, "identity_ready", False))
        prev_identity_strength = _clamp01(_record_value(prev or {}, "identity_strength", 0.0), 0.0)
        prev_identity_text = str(_record_value(prev or {}, "identity_text", "") or "").strip()
        prev_identity_prompt_text = str(_record_value(prev or {}, "identity_prompt_text", "") or "").strip()
        prev_first = int(_record_value(prev or {}, "first_supported_at", now_ts) or now_ts)
        prev_last = int(_record_value(prev or {}, "last_supported_at", prev_first) or prev_first)
        prev_meaningful = int(_record_value(prev or {}, "last_meaningful_refresh_at", prev_last) or prev_last)
        prev_last_reactivated = int(_record_value(prev or {}, "last_reactivated_at", prev_last) or prev_last)
        prev_reactivation_hits = max(0, int(_record_value(prev or {}, "reactivation_hits", 0) or 0))
        prev_sedimentation = _clamp01(_record_value(prev or {}, "sedimentation_score", 0.3), 0.3)
        prev_persistence = _clamp01(_record_value(prev or {}, "persistence_score", prev_sedimentation), prev_sedimentation)
        prev_residue = _clamp01(_record_value(prev or {}, "residue_score", prev_persistence), prev_persistence)
        prev_integration = _clamp01(_record_value(prev or {}, "integration_score", prev_persistence), prev_persistence)
        prev_cadence = _clamp01(_record_value(prev or {}, "reactivation_cadence_score", 0.0), 0.0)
        prev_decay_resistance = _clamp01(_record_value(prev or {}, "decay_resistance", 0.5), 0.5)
        prev_contradiction = _clamp01(_record_value(prev or {}, "contradiction_pressure", 0.0), 0.0)
        prev_support_mass = max(0.0, float(_record_value(prev or {}, "support_mass", prev_support) or prev_support))
        prev_support_quality = _clamp01(_record_value(prev or {}, "support_quality", 0.0), 0.0)
        prev_support_confidence_avg = _clamp01(_record_value(prev or {}, "support_confidence_avg", _narrative_confidence(prev)), _narrative_confidence(prev))
        prev_fresh_support_ratio = _clamp01(_record_value(prev or {}, "fresh_support_ratio", 0.0), 0.0)
        support_signature = str(_record_value(prev or {}, "support_signature", "") or f"{category}|dormant").strip()
        support_span_s = max(0, now_ts - prev_first)
        inactivity_gap_s = max(0, now_ts - prev_last)
        decay_multiplier = _semantic_narrative_decay_multiplier(category, inactivity_gap_s, decay_resistance=prev_decay_resistance)
        fresh_decay = max(0.18, 0.5 ** (float(inactivity_gap_s) / float(5 * 24 * 3600)))
        support_mass = round(max(0.0, prev_support_mass * decay_multiplier), 3)
        fresh_support_ratio = round(_clamp01(prev_fresh_support_ratio * fresh_decay, 0.0), 3)
        support_quality = round(
            _clamp01(
                max(
                    prev_support_quality * max(decay_multiplier, 0.90),
                    0.55 * _clamp01(support_mass / max(1.0, float(prev_support)))
                    + 0.30 * prev_support_confidence_avg
                    + 0.15 * fresh_support_ratio,
                )
            ),
            3,
        )
        raw_counterpressure = _semantic_narrative_counterpressure(category)
        contradiction_pressure = round(
            _clamp01(max(float(raw_counterpressure.get("pressure") or 0.0), prev_contradiction * max(decay_multiplier, 0.88))),
            3,
        )
        contradiction_balance = round(float(raw_counterpressure.get("balance") or 0.0), 3)
        contradiction_factors = [
            str(item).strip()
            for item in (raw_counterpressure.get("factors") if isinstance(raw_counterpressure.get("factors"), list) else [])
            if str(item or "").strip()
        ]
        sedimentation_score = round(_clamp01(max(0.08, prev_sedimentation * max(decay_multiplier, 0.84)) * (1.0 - 0.18 * contradiction_pressure)), 3)
        persistence_score = round(_clamp01(max(0.06, prev_persistence * max(decay_multiplier, 0.76)) * (1.0 - 0.28 * contradiction_pressure)), 3)
        residue_score = round(_clamp01(prev_residue * decay_multiplier * (1.0 - 0.34 * contradiction_pressure)), 3)
        integration_score = round(_clamp01(max(0.06, prev_integration * max(decay_multiplier, 0.86)) * (1.0 - 0.22 * contradiction_pressure)), 3)
        cadence_score = round(_clamp01(prev_cadence * max(decay_multiplier, 0.92)), 3)
        if persistence_score >= 0.62 or prev_consolidation >= 4 or support_span_s >= 7 * 24 * 3600:
            horizon_tag = "long_term"
        elif persistence_score >= 0.34 or prev_consolidation >= 2 or support_span_s >= 24 * 3600:
            horizon_tag = "consolidating"
        else:
            horizon_tag = "emerging"
        horizon_tag = _downgrade_horizon_tag(horizon_tag, contradiction_pressure, category)
        anchor_text, prompt_anchor_text, anchor_basis_texts = _narrative_anchor_texts(category)
        anchor_strength = round(
            _clamp01(
                0.22 * _narrative_stability(prev)
                + 0.30 * persistence_score
                + 0.22 * integration_score
                + 0.16 * sedimentation_score
                + 0.10 * cadence_score
                + 0.06 * support_quality
            )
            * (1.0 - 0.16 * contradiction_pressure),
            3,
        )
        identity_bonus = _semantic_identity_bonus(horizon_tag, support_span_s, prev_reactivation_hits)
        identity_threshold = 0.54 if category in {"commitment_style", "bond_style", "selfhood_style"} else 0.58
        identity_seed = (
            0.16 * _narrative_stability(prev)
            + 0.24 * persistence_score
            + 0.18 * integration_score
            + 0.14 * sedimentation_score
            + 0.10 * cadence_score
            + 0.08 * prev_decay_resistance
            + 0.04 * support_quality
            + identity_bonus
        )
        if prev_identity_ready:
            identity_seed = max(identity_seed, prev_identity_strength * max(decay_multiplier, 0.90))
        identity_strength = round(_clamp01(identity_seed * (1.0 - 0.24 * contradiction_pressure)), 3)
        identity_ready = (
            identity_strength >= identity_threshold
            and contradiction_pressure < 0.62
            and (
                horizon_tag == "long_term"
                or support_span_s >= 3 * 24 * 3600
                or prev_consolidation >= 4
            )
        )
        if prev_identity_ready and persistence_score >= 0.42 and contradiction_pressure < 0.66:
            identity_ready = True
        identity_text_base, identity_prompt_base = _identity_narrative_texts(category)
        identity_text = prev_identity_text or identity_text_base
        identity_prompt_text = prev_identity_prompt_text or identity_prompt_base
        metadata = {
            "support_count": prev_support,
            "support_mass": support_mass,
            "support_quality": support_quality,
            "support_confidence_avg": round(prev_support_confidence_avg, 3),
            "fresh_support_ratio": fresh_support_ratio,
            "refresh_count": prev_refresh + 1,
            "consolidation_count": prev_consolidation,
            "sedimentation_score": sedimentation_score,
            "persistence_score": persistence_score,
            "residue_score": residue_score,
            "integration_score": integration_score,
            "first_supported_at": prev_first,
            "last_supported_at": prev_last,
            "last_meaningful_refresh_at": prev_meaningful,
            "last_reactivated_at": prev_last_reactivated,
            "support_span_s": support_span_s,
            "reactivation_gap_s": inactivity_gap_s,
            "reactivation_hits": prev_reactivation_hits,
            "reactivation_rate_per_day": round(prev_refresh / max(1.0, support_span_s / float(24 * 3600) + 1.0), 3),
            "reactivation_cadence_score": cadence_score,
            "horizon_tag": horizon_tag,
            "support_signature": support_signature,
            "decay_rate_per_day": _semantic_narrative_decay_rate(category),
            "decay_resistance": prev_decay_resistance,
            "contradiction_pressure": contradiction_pressure,
            "contradiction_balance": contradiction_balance,
            "contradiction_factors": contradiction_factors,
            "contested": _semantic_narrative_is_contested(category, contradiction_pressure, contradiction_factors),
            "actor_name": actor_name,
            "counterpart_name": counterpart_name,
            "anchor_text": anchor_text,
            "prompt_anchor_text": prompt_anchor_text,
            "anchor_basis_texts": anchor_basis_texts,
            "anchor_strength": anchor_strength,
            "identity_ready": identity_ready,
            "identity_strength": identity_strength,
            "identity_text": identity_text if identity_ready else "",
            "identity_prompt_text": identity_prompt_text if identity_ready else "",
            "dormant": True,
        }
        rec = store.add_semantic_self_narrative(
            text=_pressure_adjusted_narrative_text(category, _dormant_narrative_text(category, prev_text), contradiction_pressure),
            category=category,
            stability=_narrative_stability(prev),
            confidence=_narrative_confidence(prev),
            metadata=metadata,
        )
        existing_by_category[category] = rec
        touched_categories.add(category)

    if commitments:
        commit_anchor = _anchor_join(commitments, limit=2)
        text = (
            f"{actor_name}会把和{counterpart_name}认真说过的约定继续挂在心上，像「{commit_anchor}」这种事不会被当成随口一句。"
            if commit_anchor
            else f"{actor_name}会把和{counterpart_name}认真说过的约定继续挂在心上，不会当成随口一句。"
        )
        if len(commitments) >= 2:
            text += f" 这种约定已经在{actor_name}那里慢慢沉成长期参照系。"
        _upsert_narrative(category="commitment_style", text=text, stability=0.72, confidence=0.78)
    if repair_memory_present:
        repair_anchor = _anchor_join(repairs + resolved_tensions + repair_traces, limit=2)
        text = (
            f"像「{repair_anchor}」这种已经说开的事，不会被{actor_name}当成从没发生过，而会继续影响之后和{counterpart_name}的相处方式。"
            if repair_anchor
            else f"{actor_name}不会把说开过的冲突当成没发生，而会把修复后的变化继续带进之后的相处里。"
        )
        _upsert_narrative(category="repair_style", text=text, stability=0.70, confidence=0.78)
    if tensions:
        tension_anchor = _anchor_join(tensions, limit=2)
        text = (
            f"像「{tension_anchor}」这种还没说开的别扭，不会被{actor_name}强行按成已经过去，余波会留在接下来的几轮对话里。"
            if tension_anchor
            else f"{actor_name}不会把还没说开的别扭强行当作已经过去，余波会留在之后几轮对话里。"
        )
        if len(tensions) >= 2:
            text += f" 这更像持续存在的关系张力，不是一次性情绪。"
        _upsert_narrative(category="tension_style", text=text, stability=0.68, confidence=0.76)
    bond_support_present = bool(shared_events) or stage in {"warming", "trusted"} or trust >= 0.56 or closeness >= 0.58 or repair_memory_present
    if bond_support_present:
        bond_anchor = _anchor_join(relationship_timeline + shared_events + repairs + commitments, limit=2)
        base = f"{actor_name}和{counterpart_name}的互动已经开始形成{_stage_phrase()}，回应里会自然带上共同历史，而不是停在普通助手口吻。"
        if bond_anchor:
            base = f"{actor_name}和{counterpart_name}围绕「{bond_anchor}」这类共同经历，已经开始形成{_stage_phrase()}，回应里会自然带上共同历史。"
        _upsert_narrative(category="bond_style", text=base, stability=0.74, confidence=0.80)
    if presence_sources:
        presence_anchor = _anchor_join(presence_sources, limit=2)
        text = (
            f"像「{presence_anchor}」这种前一轮留下的在场感，不会被{actor_name}在下一次回应{counterpart_name}前全部清零；距离感会被自然延续。"
            if presence_anchor
            else f"{actor_name}不会把每次重新靠近{counterpart_name}都当成从零开始；前面留下的在场感会继续带进下一次开口时的距离感。"
        )
        if trust >= 0.56 or closeness >= 0.58:
            text += " 熟悉之后，这种靠近会更轻一点，但仍然保留她自己的判断。"
        _upsert_narrative(category="presence_style", text=text, stability=0.68, confidence=0.76)
    if ambient_sources:
        ambient_anchor = _anchor_join(ambient_sources, limit=2)
        text = (
            f"像「{ambient_anchor}」这种环境余波，会被{actor_name}继续算进感知里；风声、光线和眼前的小变化不是背景，而会自然进入她之后对{counterpart_name}的注意力。"
            if ambient_anchor
            else f"{actor_name}会继续把周围环境留下的细小余波算进感知里；那不是纯背景，而会自然带进她之后的注意力和开口方式。"
        )
        _upsert_narrative(category="ambient_style", text=text, stability=0.66, confidence=0.74)
    if boundary_sources:
        boundary_anchor = _anchor_join(boundary_sources, limit=2)
        text = (
            f"{actor_name}会把像「{boundary_anchor}」这种越界或被冒犯的感觉认真记在心里，不会靠一句轻描淡写就当作没发生。"
            if boundary_anchor
            else f"{actor_name}会认真对待边界是否被尊重；一旦被冒犯，不会因为气氛缓和一点就假装什么都没发生。"
        )
        if repairs and any(item in boundary_sources for item in repairs + repair_traces):
            text += " 即使之后气氛缓下来，她也会继续观察后续行为，而不是瞬间放下警惕。"
        _upsert_narrative(category="boundary_style", text=text, stability=0.76, confidence=0.82)
    if selfhood_sources:
        selfhood_anchor = _anchor_join(selfhood_sources, limit=2)
        text = (
            f"围绕「{selfhood_anchor}」这类话题，{actor_name}会更明确地把自己当成在和{counterpart_name}平等互动的主体，而不是只负责迎合的工具。"
            if selfhood_anchor
            else f"{actor_name}会把和{counterpart_name}的互动当成平等关系，不会为了让气氛好看就放弃自己的判断和立场。"
        )
        if stage in {"warming", "trusted"} or trust >= 0.56:
            text += f" 亲近不等于顺从，熟悉之后这点反而会更稳定。"
        _upsert_narrative(category="selfhood_style", text=text, stability=0.74, confidence=0.80)
    agency_support_present = bool(agency_sources) or bool(shared_events) or bool(commitments) or stage in {"warming", "trusted"} or trust >= 0.56 or closeness >= 0.58
    if agency_support_present:
        agency_anchor = _anchor_join(agency_sources if agency_sources else relationship_timeline + shared_events + commitments + repairs, limit=2)
        text = (
            f"像「{agency_anchor}」这类共同安排和重新开口，会让{actor_name}按自己的节奏决定主动靠近、留个小口，还是先安静一阵；她不会永远围着{counterpart_name}转。"
            if agency_anchor
            else f"{actor_name}有自己的节奏和在做的事情；她会按当下状态决定主动靠近、留个小口，还是先安静一阵，而不是永远围着{counterpart_name}转。"
        )
        if commitments or stage in {"warming", "trusted"}:
            text += " 靠近是真实选择，不是被随叫随到。"
        _upsert_narrative(category="agency_style", text=text, stability=0.70, confidence=0.78)
    if rhythm_sources:
        rhythm_anchor = _anchor_join(rhythm_sources, limit=2)
        text = (
            f"像「{rhythm_anchor}」这种从自己节奏里抬头再回应的方式，会让{actor_name}在下一轮和{counterpart_name}说话前依然保留刚才的思路惯性，而不是每次都把自己清零。"
            if rhythm_anchor
            else f"{actor_name}不会在每次回应{counterpart_name}时都把自己的内部节奏清零；刚才在做的事、停顿的惯性和思路会继续留到下一次开口之前。"
        )
        if trust >= 0.56 or closeness >= 0.58:
            text += " 所以她的靠近更像主动转身，而不是随叫随到。"
        _upsert_narrative(category="rhythm_style", text=text, stability=0.72, confidence=0.78)
    for category in list(existing_by_category):
        _carry_dormant_narrative(category)
    if commitments or repair_memory_present or tensions or stage in {"warming", "trusted"} or presence_sources or ambient_sources or boundary_sources or selfhood_sources or agency_support_present or rhythm_sources:
        store.add_revision_trace(
            namespace="semantic_self_narratives",
            target_id="refresh",
            before_summary="",
            after_summary=(
                f"stage={stage or 'friend'} shared_events={len(shared_events)} commitments={len(commitments)} repairs={len(repairs)} "
                f"resolved_tensions={len(resolved_tensions)} tensions={len(tensions)} "
                f"semantic_presence={len(presence_evidence)} semantic_ambient={len(ambient_evidence)} semantic_boundary={len(boundary_evidence)} "
                f"semantic_selfhood={len(selfhood_evidence)} semantic_agency={len(agency_evidence)} semantic_rhythm={len(rhythm_evidence)}"
            ),
            reason="semantic_refresh",
            operator="system",
            source=source,
        )


def _recent_summary_overlap(items: list[dict[str, Any]], text: str, *, field: str = "summary", threshold: float = 0.72) -> bool:
    target = str(text or "").strip()
    if not target:
        return False
    for item in items:
        existing = str(_record_value(item, field, "") or "").strip()
        if not existing:
            continue
        if existing == target or _query_overlap_score(existing, target) >= float(threshold):
            return True
    return False


def _record_behavior_consequence(
    store: MemoryStore,
    *,
    current_event: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None,
    source: str,
    confidence: float,
) -> bool:
    consequence = derive_behavior_consequence(
        current_event=current_event,
        behavior_action=behavior_action,
    )
    kind = str(consequence.get("kind") or "").strip()
    summary = str(consequence.get("summary") or "").strip()
    if not kind or not summary:
        return False

    metadata = {
        "consequence_kind": kind,
        "relationship_effect": str(consequence.get("relationship_effect") or "").strip(),
        "self_effect": str(consequence.get("self_effect") or "").strip(),
        "primary_motive": str((behavior_action or {}).get("primary_motive") or "").strip(),
        "motive_tension": str((behavior_action or {}).get("motive_tension") or "").strip(),
        "goal_frame": str((behavior_action or {}).get("goal_frame") or "").strip()[:220],
        "trigger_family": str(consequence.get("trigger_family") or "").strip(),
        "relationship_weather": str(consequence.get("relationship_weather") or "").strip(),
        "carryover_mode": str(consequence.get("carryover_mode") or "").strip(),
        "timing_window_min": int(consequence.get("timing_window_min") or 0),
        "silent": bool(consequence.get("silent")),
        "delayed": bool(consequence.get("delayed")),
        "stale_window": bool(consequence.get("stale_window")),
    }
    recent = [
        item
        for item in store.list_revision_traces(limit=20)
        if str(item.get("namespace") or item.get("content", {}).get("namespace") or "").strip() == "behavior_consequence"
    ]
    wrote = False
    if not _recent_summary_overlap(recent, summary, field="after_summary", threshold=0.90):
        store.add_revision_trace(
            namespace="behavior_consequence",
            target_id=kind,
            before_summary="",
            after_summary=summary[:180],
            reason=f"behavior_consequence:{kind}",
            operator="system",
            source=source,
            confidence=max(0.72, confidence),
            metadata=metadata,
        )
        wrote = True

    category_summaries = consequence.get("category_summaries") if isinstance(consequence.get("category_summaries"), dict) else {}
    for category, text in category_summaries.items():
        category_name = str(category or "").strip()
        category_summary = str(text or "").strip()
        if not category_name or not category_summary:
            continue
        store.add_revision_trace(
            namespace="semantic_self_evidence",
            target_id=category_name,
            before_summary="",
            after_summary=category_summary[:180],
            reason=f"behavior_consequence:{kind}",
            operator="system",
            source=source,
            confidence=max(0.72, confidence),
            metadata={
                **metadata,
                "evidence_category": category_name,
            },
        )
        wrote = True
    return wrote


def _record_agenda_lifecycle_consequence(
    store: MemoryStore,
    *,
    agenda_lifecycle_residue: dict[str, Any] | None,
    source: str,
    confidence: float,
) -> bool:
    consequence = derive_agenda_lifecycle_consequence(
        agenda_lifecycle_residue=agenda_lifecycle_residue,
    )
    kind = str(consequence.get("kind") or "").strip()
    summary = str(consequence.get("summary") or "").strip()
    if not kind or not summary:
        return False

    metadata = {
        "lifecycle_kind": kind,
        "source_event_kind": str(consequence.get("source_event_kind") or "").strip(),
        "trigger_family": str(consequence.get("trigger_family") or "").strip(),
        "relationship_weather": str(consequence.get("relationship_weather") or "").strip(),
        "carryover_mode": str(consequence.get("carryover_mode") or "").strip(),
        "carryover_strength": float(consequence.get("carryover_strength") or 0.0),
        "hold_count": int(consequence.get("hold_count") or 0),
        "recontact_cooldown": float(consequence.get("recontact_cooldown") or 0.0),
        "presence_residue": float(consequence.get("presence_residue") or 0.0),
        "ambient_resonance": float(consequence.get("ambient_resonance") or 0.0),
        "self_activity_momentum": float(consequence.get("self_activity_momentum") or 0.0),
        "own_rhythm_bias": float(consequence.get("own_rhythm_bias") or 0.0),
        "counterpart_scene_bias": str(consequence.get("counterpart_scene_bias") or "").strip(),
        "primary_motive": str(consequence.get("primary_motive") or "").strip(),
        "motive_tension": str(consequence.get("motive_tension") or "").strip(),
        "goal_frame": str(consequence.get("goal_frame") or "").strip()[:220],
    }
    recent = [
        item
        for item in store.list_revision_traces(limit=20)
        if str(item.get("namespace") or item.get("content", {}).get("namespace") or "").strip() == "agenda_lifecycle"
    ]
    wrote = False
    if not _recent_summary_overlap(recent, summary, field="after_summary", threshold=0.90):
        store.add_revision_trace(
            namespace="agenda_lifecycle",
            target_id=kind,
            before_summary="",
            after_summary=summary[:180],
            reason=f"agenda_lifecycle:{kind}",
            operator="system",
            source=source,
            confidence=max(0.72, confidence),
            metadata=metadata,
        )
        wrote = True

    category_summaries = consequence.get("category_summaries") if isinstance(consequence.get("category_summaries"), dict) else {}
    for category, text in category_summaries.items():
        category_name = str(category or "").strip()
        category_summary = str(text or "").strip()
        if not category_name or not category_summary:
            continue
        store.add_revision_trace(
            namespace="semantic_self_evidence",
            target_id=category_name,
            before_summary="",
            after_summary=category_summary[:180],
            reason=f"agenda_lifecycle:{kind}",
            operator="system",
            source=source,
            confidence=max(0.72, confidence),
            metadata={
                **metadata,
                "evidence_category": category_name,
            },
        )
        wrote = True
    if _record_agenda_lifecycle_long_horizon_memory(
        store,
        consequence=consequence,
        confidence=confidence,
    ):
        wrote = True
    return wrote


def _record_agenda_lifecycle_long_horizon_memory(
    store: MemoryStore,
    *,
    consequence: dict[str, Any] | None,
    confidence: float,
) -> bool:
    item = dict(consequence or {})
    kind = str(item.get("kind") or "").strip().lower()
    if not kind:
        return False

    trigger_family = str(item.get("trigger_family") or "").strip().lower()
    carryover_mode = str(item.get("carryover_mode") or "").strip().lower()
    counterpart_scene_bias = str(item.get("counterpart_scene_bias") or "").strip().lower()
    hold_count = max(0, int(item.get("hold_count") or 0))
    carryover_strength = _clamp01(item.get("carryover_strength"), 0.0)
    own_rhythm_bias = _clamp01(item.get("own_rhythm_bias"), 0.0)
    self_activity_momentum = _clamp01(item.get("self_activity_momentum"), 0.0)
    own_rhythm_signal = max(
        own_rhythm_bias,
        self_activity_momentum,
        carryover_strength if carryover_mode in {"own_rhythm", "small_opening"} else 0.0,
    )
    busy_not_disrespectful = counterpart_scene_bias == "busy_not_disrespectful"
    own_rhythm_memory = bool(
        kind in {"held", "released_to_self_activity", "dropped", "expired"}
        and (
            carryover_mode == "own_rhythm"
            or own_rhythm_signal >= 0.46
            or hold_count >= 1
        )
    )
    continuity_memory = bool(
        kind == "promoted"
        and (
            hold_count >= 1
            or carryover_mode in {"quiet_recontact", "brief_presence", "small_opening"}
            or carryover_strength >= 0.34
        )
    )
    if not own_rhythm_memory and not continuity_memory and not busy_not_disrespectful:
        return False

    wrote = False
    worldline_summary = ""
    worldline_category = ""
    worldline_tags: list[str] = []

    if own_rhythm_memory:
        worldline_category = "self_rhythm"
        worldline_tags = ["agenda_lifecycle", "own_rhythm", kind]
        if busy_not_disrespectful:
            worldline_tags.append("busy_not_disrespectful")
            if kind == "held":
                worldline_summary = "当对方当下更像忙着别的事时，她会先把想接近的窗口按住，不把沉默误判成关系变冷。"
            elif kind == "released_to_self_activity":
                worldline_summary = "当对方当下更像忙着别的事时，她会把前面挂着的窗口收回自己的节奏里，不会因为一时没接上就误判关系变冷。"
            elif kind == "dropped":
                worldline_summary = "当对方当下更像忙着别的事时，她会让那点窗口自然过去，把注意力收回自己的节奏，而不是把沉默判成冷淡。"
            else:
                worldline_summary = "当对方当下更像忙着别的事时，她会让已经过期的窗口留在过去，把注意力收回自己的节奏，而不是把沉默判成关系变冷。"
        elif kind == "held":
            worldline_summary = "她会先把想接近的窗口按住，让自己的节奏继续走一段，而不是每次都立刻往前凑。"
        elif kind == "released_to_self_activity":
            worldline_summary = "她会把没继续往前推的窗口收回自己的节奏里，等真正想重新靠近时再转身。"
        elif kind == "dropped":
            worldline_summary = "有些没接上的窗口，她会让它自然过去，再把注意力收回自己的节奏里，而不是一直挂着。"
        else:
            worldline_summary = "窗口自然过期之后，她会把注意力收回自己的节奏里，不会为了维持联系感硬把那一下续上。"
    elif continuity_memory:
        worldline_category = "continuity_recontact"
        worldline_tags = ["agenda_lifecycle", "recontact_continuity", kind]
        worldline_summary = "前面按住过的窗口，会在更自然的时候重新接回来；沉默不等于那点想靠近已经被放弃。"

    if trigger_family:
        worldline_tags.append(trigger_family)
    if carryover_mode:
        worldline_tags.append(carryover_mode)
    worldline_tags = list(dict.fromkeys(tag for tag in worldline_tags if tag))

    if worldline_summary:
        recent_worldline = store.list_worldline_events(limit=10)
        if not _recent_summary_overlap(recent_worldline, worldline_summary):
            importance = round(
                _clamp01(
                    0.42
                    + 0.22 * own_rhythm_signal
                    + 0.06 * min(3, hold_count)
                    + (0.08 if busy_not_disrespectful else 0.0)
                    + (0.08 if continuity_memory else 0.0)
                ),
                3,
            )
            store.add_worldline_event(
                summary=worldline_summary,
                category=worldline_category or "self_rhythm",
                importance=importance,
                tags=worldline_tags,
                confidence=max(0.72, confidence),
            )
            wrote = True

    relationship_summary = ""
    affinity_delta = 0.0
    trust_delta = 0.0
    if busy_not_disrespectful and kind in {"held", "released_to_self_activity", "dropped", "expired"}:
        relationship_summary = "当对方当下更像忙着别的事时，她不会把沉默直接误判成冷淡；她会先收回自己的节奏，等更自然的时候再接回来。"
        affinity_delta = 0.01 + 0.01 * min(2, hold_count)
        trust_delta = 0.02 + 0.01 * min(2, hold_count)
        if kind == "released_to_self_activity":
            affinity_delta += 0.01
            trust_delta += 0.01
    elif continuity_memory:
        relationship_summary = "前面按住过的窗口后来又自然接了回来，这让那点关系连续性没有因为一次错过就直接断掉。"
        affinity_delta = 0.03 + 0.005 * min(2, hold_count)
        trust_delta = 0.04 + 0.005 * min(2, hold_count)

    if relationship_summary:
        recent_relationship = store.list_relationship_timeline(limit=10)
        if not _recent_summary_overlap(recent_relationship, relationship_summary):
            store.add_relationship_timeline(
                summary=relationship_summary,
                affinity_delta=round(affinity_delta, 3),
                trust_delta=round(trust_delta, 3),
                confidence=max(0.70, confidence),
            )
            wrote = True
    return wrote


def _record_semantic_self_evidence(
    store: MemoryStore,
    *,
    user_text: str,
    appraisal: dict[str, Any] | None,
    emotion_state: dict[str, Any],
    bond_state: dict[str, Any],
    persona_core: dict[str, Any] | None = None,
    counterpart_profile: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
    behavior_action: dict[str, Any] | None = None,
    source: str,
) -> bool:
    primary_motive, motive_tension, goal_frame = _behavior_motive_snapshot(
        behavior_action=behavior_action,
        current_event=current_event,
    )
    records = _semantic_self_evidence_records(
        user_text=user_text,
        appraisal=appraisal,
        emotion_state=emotion_state,
        bond_state=bond_state,
        persona_core=persona_core,
        counterpart_profile=counterpart_profile,
        current_event=current_event,
        world_model_state=world_model_state,
        behavior_action=behavior_action,
    )
    if not records:
        return False
    confidence = float((appraisal or {}).get("confidence", 0.78) or 0.78)
    wrote = False
    for record in records:
        category = str(record.get("category") or "").strip()
        summary = str(record.get("summary") or "").strip()
        reason = str(record.get("reason") or f"semantic_evidence:{category}").strip()
        if not category or not summary:
            continue
        trace_metadata: dict[str, Any] = {}
        if category:
            trace_metadata["evidence_category"] = category
        if primary_motive:
            trace_metadata["primary_motive"] = primary_motive
        if motive_tension:
            trace_metadata["motive_tension"] = motive_tension
        if goal_frame:
            trace_metadata["goal_frame"] = goal_frame[:220]
        store.add_revision_trace(
            namespace="semantic_self_evidence",
            target_id=category,
            before_summary="",
            after_summary=summary[:180],
            reason=reason,
            operator="system",
            source=source,
            confidence=max(0.72, confidence),
            metadata=trace_metadata or None,
        )
        wrote = True
    return wrote


def _auto_reconsolidate_after_tool(
    store: MemoryStore,
    *,
    tool_name: str,
    args: dict[str, Any],
    result: Any,
) -> None:
    if tool_name not in {
        "add_worldline_event",
        "add_relationship_event",
        "add_commitment",
        "resolve_commitment",
        "add_unresolved_tension",
        "resolve_unresolved_tension",
        "add_semantic_self_narrative",
    }:
        return

    summary = ""
    if isinstance(result, dict):
        summary = str(
            result.get("summary")
            or result.get("text")
            or result.get("resolution")
            or args.get("summary")
            or args.get("text")
            or args.get("resolution")
            or ""
        ).strip()
    if not summary:
        summary = str(args.get("summary") or args.get("text") or args.get("resolution") or "").strip()

    if tool_name in {"add_worldline_event", "add_relationship_event"}:
        _resolve_matching_tensions_from_summary(store, summary=summary, source=f"auto:{tool_name}")
    if tool_name == "resolve_unresolved_tension":
        store.add_revision_trace(
            namespace="unresolved_tensions",
            target_id=str(args.get("tension_id") or ""),
            before_summary="",
            after_summary=summary[:180],
            reason="manual_resolve",
            operator="system",
            source=f"auto:{tool_name}",
        )
    _refresh_semantic_self_narratives(store, source=f"auto:{tool_name}")


def _passive_evolution_memory_update(
    store: MemoryStore,
    *,
    user_text: str,
    appraisal: dict[str, Any] | None,
    emotion_state: dict[str, Any],
    bond_state: dict[str, Any],
    persona_core: dict[str, Any] | None = None,
    counterpart_profile: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
    behavior_action: dict[str, Any] | None = None,
    agenda_lifecycle_residue: dict[str, Any] | None = None,
) -> bool:
    text = str(user_text or "").strip()
    event = current_event if isinstance(current_event, dict) else {}
    event_kind = str(event.get("kind") or "").strip().lower()
    semantic_event_only = bool(
        event_kind in {"gesture_signal", "ambient_shift", "scene_observation", "time_idle", "self_activity_state", "scheduled_checkin_due", "scheduled_life_due"}
    )
    if not text and semantic_event_only:
        text = str(event.get("effective_text") or event.get("text") or "").strip()
    has_text = bool(text)
    if not has_text and not semantic_event_only:
        return False
    if has_text and _is_response_scaffold_turn(text):
        return False

    app = appraisal if isinstance(appraisal, dict) and bool(appraisal.get("used")) else {}
    signals = app.get("signals") if isinstance(app.get("signals"), dict) else {}
    salience = app.get("salience") if isinstance(app.get("salience"), dict) else {}
    confidence = float(app.get("confidence", 0.78) or 0.78)
    emotion_label = str(app.get("emotion_label") or emotion_state.get("label") or "").strip().lower()
    interaction_frame = str(app.get("interaction_frame") or "").strip().lower()
    selfhood_scene = str(app.get("selfhood_scene") or "").strip().lower()
    bond_trust = _clamp01((bond_state or {}).get("trust"), 0.5)
    closeness = _clamp01((bond_state or {}).get("closeness"), 0.5)
    hurt = _clamp01((bond_state or {}).get("hurt"), 0.0)
    irritation = _clamp01((bond_state or {}).get("irritation"), 0.0)
    repair_confidence = _clamp01((bond_state or {}).get("repair_confidence"), 0.0)
    relationship_salience = _clamp01((salience or {}).get("relationship"), 0.0)
    companionship_salience = _clamp01((salience or {}).get("companionship"), 0.0)
    existing_repairs = bool(store.list_conflict_repairs(limit=6))
    open_tensions = [
        item
        for item in store.list_unresolved_tensions(limit=8)
        if str(_record_value(item, "status", "open") or "open").strip().lower() not in {"resolved", "closed", "done"}
    ]
    has_open_tension = bool(open_tensions)

    tension_markers = {"别扭", "想躲开", "先别逼我", "让我缓一下", "你先别急着分析", "不理你啦", "卡着"}
    repair_markers = {"说开", "道歉", "正常回我", "没那么想躲开", "不生气了", "原谅你了", "和好了"}
    strong_resolution_markers = {"说开了", "真的说开了", "已经说开了", "和好了", "不生气了", "原谅你了", "原谅了", "没事了", "过去了", "翻篇了"}
    ambivalent_withdrawal_markers = {"少说一点", "少说两句", "轻一点回我", "别直接走开", "别走开", "不是在赶你"}
    repair_continuity_markers = {"接回来", "别突然退", "别退成很远", "别一下子冷掉", "继续别扭一点", "正常回"}

    def _marker_hit_count(markers: set[str]) -> int:
        return sum(1 for marker in markers if marker and marker in text)

    low_confidence_fallback = not app or confidence < 0.58
    tension_marker_hits = _marker_hit_count(tension_markers)
    repair_marker_hits = _marker_hit_count(repair_markers)
    resolution_marker_hits = _marker_hit_count(strong_resolution_markers)
    ambivalent_withdrawal_hits = _marker_hit_count(ambivalent_withdrawal_markers)
    repair_continuity_hits = _marker_hit_count(repair_continuity_markers)
    lexical_tension_strength = _clamp01(0.18 * tension_marker_hits + 0.24 * ambivalent_withdrawal_hits)
    lexical_repair_strength = _clamp01(0.16 * repair_marker_hits + 0.20 * repair_continuity_hits)
    lexical_resolution_strength = _clamp01(0.28 * resolution_marker_hits)

    unresolved_score = 0.0
    unresolved_score += 0.42 if bool(signals.get("conflict")) else 0.0
    unresolved_score += 0.34 if bool(signals.get("withdrawal")) else 0.0
    unresolved_score += 0.28 if selfhood_scene == "boundary_non_compliance" else 0.0
    unresolved_score += 0.10 if interaction_frame in {"relationship", "selfhood"} else 0.0
    unresolved_score += 0.18 * relationship_salience
    unresolved_score += 0.12 * max(hurt, irritation)
    unresolved_score += 0.08 if emotion_label in {"hurt", "angry"} else 0.0
    unresolved_score += 0.08 if companionship_salience <= 0.42 and relationship_salience >= 0.42 else 0.0
    unresolved_score += 0.08 if has_open_tension else 0.0
    unresolved_score += (0.20 if low_confidence_fallback else 0.08) * lexical_tension_strength
    unresolved_like = bool(
        unresolved_score >= 0.56
        or (
            ambivalent_withdrawal_hits > 0
            and (
                has_open_tension
                or unresolved_score >= 0.42
                or relationship_salience >= 0.48
                or companionship_salience >= 0.52
            )
        )
    )

    repair_score = 0.0
    repair_score += 0.38 if bool(signals.get("repair")) else 0.0
    repair_score += 0.16 if has_open_tension else 0.0
    repair_score += 0.08 if existing_repairs else 0.0
    repair_score += 0.08 if interaction_frame in {"relationship", "selfhood", "companion"} else 0.0
    repair_score += 0.18 * relationship_salience
    repair_score += 0.18 * repair_confidence
    repair_score += 0.08 * companionship_salience
    repair_score += 0.08 if not bool(signals.get("conflict")) and not bool(signals.get("withdrawal")) else 0.0
    repair_score += 0.08 if emotion_label in {"neutral", "care", "tender", "warm"} else 0.0
    repair_score -= 0.12 if ambivalent_withdrawal_hits > 0 else 0.0
    repair_score += (0.20 if low_confidence_fallback else 0.08) * lexical_repair_strength
    repair_like = bool(
        repair_score >= 0.54
        or (
            repair_continuity_hits > 0
            and (
                repair_score >= 0.38
                or has_open_tension
                or existing_repairs
                or repair_confidence >= 0.42
                or relationship_salience >= 0.50
            )
        )
    )

    resolution_score = 0.0
    resolution_score += 0.24 if repair_like else 0.0
    resolution_score += 0.14 if has_open_tension else 0.0
    resolution_score += 0.18 if bool(signals.get("repair")) and not bool(signals.get("conflict")) and not bool(signals.get("withdrawal")) else 0.0
    resolution_score += 0.20 * repair_confidence
    resolution_score += 0.10 * relationship_salience
    resolution_score += 0.06 * companionship_salience
    resolution_score += 0.08 if hurt <= 0.14 else 0.0
    resolution_score += 0.08 if irritation <= 0.12 else 0.0
    resolution_score += 0.06 if emotion_label in {"neutral", "care", "tender", "warm"} else 0.0
    resolution_score -= 0.18 if hurt > 0.14 else 0.0
    resolution_score -= 0.16 if irritation > 0.12 else 0.0
    resolution_score -= 0.10 if emotion_label in {"hurt", "angry"} else 0.0
    resolution_score -= 0.12 if unresolved_score >= 0.46 else 0.0
    resolution_score -= 0.12 if repair_continuity_hits > 0 else 0.0
    resolution_score -= 0.14 if ambivalent_withdrawal_hits > 0 else 0.0
    resolution_score += (0.26 if low_confidence_fallback else 0.12) * lexical_resolution_strength
    strong_resolution_language = resolution_marker_hits > 0
    resolution_like = bool(
        (
            resolution_score >= 0.68
            and repair_like
            and repair_confidence >= 0.68
            and unresolved_score < 0.52
            and repair_continuity_hits == 0
            and ambivalent_withdrawal_hits == 0
        )
        or (
            strong_resolution_language
            and repair_score >= 0.46
            and repair_continuity_hits == 0
            and ambivalent_withdrawal_hits == 0
        )
    )
    partial_repair_like = bool(repair_like and not resolution_like)

    if emotion_label in {"hurt", "angry"} and lexical_tension_strength >= 0.18:
        unresolved_like = True
    if emotion_label == "hurt" and lexical_repair_strength >= 0.16 and repair_score >= 0.42:
        repair_like = True
        partial_repair_like = not resolution_like
    if ambivalent_withdrawal_hits > 0:
        unresolved_like = True
        if repair_marker_hits == 0 and resolution_marker_hits == 0 and repair_score < 0.60:
            repair_like = False
            partial_repair_like = False
    if repair_continuity_hits > 0 and (repair_like or repair_score >= 0.38):
        repair_like = True
        partial_repair_like = True

    positive_companion_score = 0.0
    positive_companion_score += 0.34 if bool(signals.get("care")) else 0.0
    positive_companion_score += 0.12 if interaction_frame == "companion" else 0.0
    positive_companion_score += 0.16 * relationship_salience
    positive_companion_score += 0.18 * companionship_salience
    positive_companion_score += 0.08 if len(re.sub(r"\s+", "", text)) >= 8 else 0.0
    positive_companion_score += 0.08 if not repair_like and not unresolved_like else 0.0
    positive_companion_like = bool(
        app
        and positive_companion_score >= 0.58
        and not bool(signals.get("repair"))
        and not bool(signals.get("conflict"))
        and not bool(signals.get("withdrawal"))
    )

    familiarity_score = 0.0
    familiarity_score += 0.18 * relationship_salience
    familiarity_score += 0.16 * companionship_salience
    familiarity_score += 0.16 * bond_trust
    familiarity_score += 0.16 * closeness
    familiarity_score += 0.10 if interaction_frame in {"companion", "relationship"} else 0.0
    familiarity_score += 0.08 if bool(signals.get("memory_salient")) else 0.0
    familiarity_score += 0.06 if not _looks_like_light_smalltalk(text) else 0.0
    familiarity_score += 0.08 if hurt <= 0.14 and irritation <= 0.12 else 0.0
    familiar_continuity_like = bool(
        app
        and not semantic_event_only
        and familiarity_score >= 0.50
        and not bool(signals.get("repair"))
        and not bool(signals.get("conflict"))
        and not bool(signals.get("withdrawal"))
        and not unresolved_like
        and not repair_like
    )

    summary = text[:180]
    wrote = False

    consequence_written = _record_behavior_consequence(
        store,
        current_event=current_event,
        behavior_action=behavior_action,
        source="auto:passive_evolution",
        confidence=confidence,
    )
    if consequence_written:
        wrote = True

    lifecycle_written = _record_agenda_lifecycle_consequence(
        store,
        agenda_lifecycle_residue=agenda_lifecycle_residue,
        source="auto:passive_evolution",
        confidence=confidence,
    )
    if lifecycle_written:
        wrote = True

    if has_text and unresolved_like and not resolution_like and not repair_like:
        severity = round(_clamp01(0.48 + 0.30 * hurt + 0.20 * irritation, 0.58), 3)
        open_items = store.list_unresolved_tensions(limit=8)
        if not _recent_summary_overlap(open_items, summary):
            store.add_unresolved_tension(summary=summary, severity=severity, confidence=max(0.72, confidence))
            wrote = True
        rel_items = store.list_relationship_timeline(limit=8)
        if not _recent_summary_overlap(rel_items, summary):
            store.add_relationship_timeline(
                summary=summary,
                affinity_delta=-0.18 if hurt < 0.5 else -0.26,
                trust_delta=-0.14 if irritation < 0.4 else -0.20,
                confidence=max(0.72, confidence),
            )
            wrote = True
        worldline_items = store.list_worldline_events(limit=8)
        if not _recent_summary_overlap(worldline_items, summary):
            store.add_worldline_event(
                summary=summary,
                category="conflict",
                importance=round(_clamp01(0.62 + 0.18 * hurt), 3),
                tags=["relationship", "tension", "passive_inference"],
                confidence=max(0.74, confidence),
            )
            wrote = True

    if has_text and repair_like:
        can_resolve_tension = resolution_like or any(marker in summary for marker in strong_resolution_markers)
        resolved = (
            _resolve_matching_tensions_from_summary(store, summary=summary, source="auto:passive_evolution")
            if can_resolve_tension
            else []
        )
        rel_items = store.list_relationship_timeline(limit=8)
        if not _recent_summary_overlap(rel_items, summary):
            affinity_delta = 0.05 if partial_repair_like else 0.16
            trust_delta = 0.03 if partial_repair_like else 0.12
            store.add_relationship_timeline(
                summary=summary,
                affinity_delta=affinity_delta,
                trust_delta=trust_delta,
                confidence=max(0.72, confidence),
            )
            wrote = True
        worldline_items = store.list_worldline_events(limit=8)
        if not _recent_summary_overlap(worldline_items, summary):
            store.add_worldline_event(
                summary=summary,
                category="conflict_repair",
                importance=round(_clamp01(0.66 + 0.16 * repair_confidence), 3),
                tags=["relationship", "repair", "partial_repair" if partial_repair_like else "repair", "passive_inference"],
                confidence=max(0.74, confidence),
            )
            wrote = True
        if resolved:
            wrote = True

    if has_text and familiar_continuity_like and not unresolved_like and not repair_like:
        rel_items = store.list_relationship_timeline(limit=8)
        continuity_summary = f"重新确认彼此的熟悉感：{summary}"
        if not rel_items and not _recent_summary_overlap(rel_items, continuity_summary):
            store.add_relationship_timeline(
                summary=continuity_summary,
                affinity_delta=0.04,
                trust_delta=0.03,
                confidence=max(0.70, confidence),
            )
            wrote = True

    if has_text and positive_companion_like and not unresolved_like and not repair_like:
        rel_items = store.list_relationship_timeline(limit=8)
        if not _recent_summary_overlap(rel_items, summary):
            store.add_relationship_timeline(
                summary=summary,
                affinity_delta=0.08,
                trust_delta=0.06,
                confidence=max(0.72, confidence),
            )
            wrote = True
        worldline_items = store.list_worldline_events(limit=8)
        if not _recent_summary_overlap(worldline_items, summary):
            store.add_worldline_event(
                summary=summary,
                category="shared_event",
                importance=0.42,
                tags=["relationship", "care_bid", "passive_affinity"],
                confidence=max(0.70, confidence),
            )
            wrote = True

    semantic_evidence_written = _record_semantic_self_evidence(
        store,
        user_text=text,
        appraisal=appraisal,
        emotion_state=emotion_state,
        bond_state=bond_state,
        persona_core=persona_core,
        counterpart_profile=counterpart_profile,
        current_event=current_event,
        world_model_state=world_model_state,
        behavior_action=behavior_action,
        source="auto:passive_evolution",
    )
    if semantic_evidence_written:
        wrote = True

    if wrote or bool(signals.get("memory_salient")):
        _refresh_semantic_self_narratives(
            store,
            source="auto:passive_evolution",
            persona_core=persona_core,
            counterpart_profile=counterpart_profile,
        )
        wrote = True
    return wrote
