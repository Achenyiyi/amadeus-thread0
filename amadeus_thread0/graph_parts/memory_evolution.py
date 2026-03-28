from __future__ import annotations

import re
from typing import Any

from ..config import CANON_COUNTERPART_NAME
from ..evolution_engine.reconsolidation import (
    derive_agenda_lifecycle_consequence,
    derive_behavior_consequence,
    derive_digital_body_consequence,
)
from ..memory_store import MemoryStore
from ..utils.counterpart_profile import compact_counterpart_profile
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
from .relational_runtime import _counterpart_assessment_profile, _counterpart_assessment_summary
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

FUTURE_TIME_MARKERS = {"周末", "下周", "明天", "今晚", "这两天", "之后", "以后", "到时候", "下次"}
SHARED_COMMITMENT_MARKERS = {
    "一起",
    "记得",
    "别让我",
    "提醒",
    "顺一遍",
    "复盘",
    "整理",
    "改完",
    "看一遍",
    "看一下",
}
SOFT_REPAIR_DEESCALATION_MARKERS = {"别放大", "不是在吵架", "不是要吵架", "别往吵架上走"}
SOFT_REPAIR_RESIDUE_MARKERS = {"别扭", "节奏有点卡", "节奏卡", "先记着", "卡住"}
_SEMANTIC_ANCHOR_FLOAT_KEYS = (
    "continuity_anchor",
    "own_rhythm_anchor",
    "recontact_anchor",
    "boundary_anchor",
    "memory_anchor",
    "semantic_continuity_depth",
    "semantic_identity_gravity",
    "lineage_gravity",
    "contact_lineage",
    "repair_lineage",
    "boundary_lineage",
    "selfhood_lineage",
    "agency_lineage",
)

__all__ = [
    "_selfhood_preference_scene",
    "_semantic_self_evidence_records",
    "_resolve_matching_tensions_from_summary",
    "_refresh_semantic_self_narratives",
    "_recent_summary_overlap",
    "_record_semantic_self_evidence",
    "_record_behavior_trace_writeback",
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
    allow_event_behavior_fallback: bool = True,
) -> tuple[str, str, str]:
    action = behavior_action if isinstance(behavior_action, dict) else {}
    event = current_event if isinstance(current_event, dict) else {}
    primary_motive = str(action.get("primary_motive") or "").strip().lower()
    motive_tension = str(action.get("motive_tension") or "").strip().lower()
    goal_frame = str(action.get("goal_frame") or "").strip()
    if allow_event_behavior_fallback:
        if not primary_motive:
            primary_motive = str(event.get("primary_motive") or "").strip().lower()
        if not motive_tension:
            motive_tension = str(event.get("motive_tension") or "").strip().lower()
        if not goal_frame:
            goal_frame = str(event.get("goal_frame") or "").strip()
    return primary_motive, motive_tension, goal_frame


def _behavior_motive_snapshot_source(
    *,
    behavior_action: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
    allow_event_behavior_fallback: bool = True,
) -> str:
    primary_motive, motive_tension, goal_frame = _behavior_motive_snapshot(
        behavior_action=behavior_action,
        current_event=current_event,
        allow_event_behavior_fallback=allow_event_behavior_fallback,
    )
    if not any((primary_motive, motive_tension, goal_frame)):
        return ""

    action = behavior_action if isinstance(behavior_action, dict) else {}
    event = current_event if isinstance(current_event, dict) else {}
    action_primary = str(action.get("primary_motive") or "").strip().lower()
    action_tension = str(action.get("motive_tension") or "").strip().lower()
    action_goal = str(action.get("goal_frame") or "").strip()
    event_primary = str(event.get("primary_motive") or "").strip().lower()
    event_tension = str(event.get("motive_tension") or "").strip().lower()
    event_goal = str(event.get("goal_frame") or "").strip()

    saw_action = False
    saw_non_action = False
    for resolved, action_value, event_value in (
        (primary_motive, action_primary, event_primary),
        (motive_tension, action_tension, event_tension),
        (goal_frame, action_goal, event_goal),
    ):
        if not resolved:
            continue
        if action_value and resolved == action_value:
            saw_action = True
            continue
        if allow_event_behavior_fallback and event_value and resolved == event_value:
            saw_non_action = True
            continue
        saw_non_action = True

    if saw_action and not saw_non_action:
        return "final_behavior_action"
    if saw_non_action and not saw_action:
        return "event_behavior_fallback"
    if saw_action and saw_non_action:
        return "mixed_behavior_semantics"
    return ""


def _reconsolidation_behavior_semantics(
    reconsolidation_snapshot: dict[str, Any] | None,
) -> dict[str, str]:
    recon = reconsolidation_snapshot if isinstance(reconsolidation_snapshot, dict) else {}
    interaction_mode = str(recon.get("behavior_mode") or "").strip().lower()
    primary_motive = str(recon.get("primary_motive") or "").strip().lower()
    motive_tension = str(recon.get("motive_tension") or "").strip().lower()
    goal_frame = str(recon.get("goal_frame") or "").strip()
    if not any((interaction_mode, primary_motive, motive_tension, goal_frame)):
        return {}
    return {
        "interaction_mode": interaction_mode,
        "primary_motive": primary_motive,
        "motive_tension": motive_tension,
        "goal_frame": goal_frame[:220],
    }


def _reconsolidation_behavior_action_snapshot(
    reconsolidation_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    recon = reconsolidation_snapshot if isinstance(reconsolidation_snapshot, dict) else {}
    action = recon.get("behavior_action")
    if not isinstance(action, dict):
        return {}
    snapshot = {
        "interaction_mode": str(action.get("interaction_mode") or "").strip().lower(),
        "action_target": str(action.get("action_target") or "").strip().lower(),
        "channel": str(action.get("channel") or "").strip().lower(),
        "approach_style": str(action.get("approach_style") or "").strip().lower(),
        "followup_intent": str(action.get("followup_intent") or "").strip().lower(),
        "deferred_action_family": str(action.get("deferred_action_family") or "").strip().lower(),
        "relationship_weather": str(action.get("relationship_weather") or "").strip().lower(),
        "attention_target": str(action.get("attention_target") or "").strip().lower(),
        "nonverbal_signal": str(action.get("nonverbal_signal") or "").strip().lower(),
        "primary_motive": str(action.get("primary_motive") or "").strip().lower(),
        "motive_tension": str(action.get("motive_tension") or "").strip().lower(),
        "goal_frame": str(action.get("goal_frame") or "").strip()[:220],
        "timing_window_min": max(0, int(action.get("timing_window_min") or 0)),
    }
    embodied_context = _normalized_embodied_context(action.get("embodied_context"))
    if embodied_context:
        snapshot["embodied_context"] = embodied_context
    if any(
        (
            snapshot["interaction_mode"],
            snapshot["action_target"],
            snapshot["channel"],
            snapshot["approach_style"],
            snapshot["followup_intent"],
            snapshot["deferred_action_family"],
            snapshot["relationship_weather"],
            snapshot["attention_target"],
            snapshot["nonverbal_signal"],
            snapshot["primary_motive"],
            snapshot["motive_tension"],
            snapshot["goal_frame"],
            snapshot["timing_window_min"] > 0,
            bool(snapshot.get("embodied_context")),
        )
    ):
        return snapshot
    return {}


def _reconsolidation_counterpart_snapshot(
    reconsolidation_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    recon = reconsolidation_snapshot if isinstance(reconsolidation_snapshot, dict) else {}
    counterpart = recon.get("counterpart")
    if not isinstance(counterpart, dict):
        return {}
    snapshot = {
        "stance": str(counterpart.get("stance") or "").strip().lower(),
        "scene": str(counterpart.get("scene") or "").strip().lower(),
        "respect_level": _clamp01(counterpart.get("respect_level"), 0.5),
        "reciprocity": _clamp01(counterpart.get("reciprocity"), 0.5),
        "boundary_pressure": _clamp01(counterpart.get("boundary_pressure"), 0.1),
        "reliability_read": _clamp01(counterpart.get("reliability_read"), 0.5),
    }
    profile = _counterpart_assessment_profile(counterpart)
    if profile:
        snapshot["assessment_profile"] = profile
    return snapshot if any(snapshot.values()) else {}


def _reconsolidation_agenda_lifecycle_snapshot(
    reconsolidation_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    recon = reconsolidation_snapshot if isinstance(reconsolidation_snapshot, dict) else {}
    consequence = recon.get("agenda_lifecycle_consequence")
    if not isinstance(consequence, dict):
        return {}
    snapshot = dict(consequence)
    return snapshot if str(snapshot.get("kind") or "").strip() else {}


def _reconsolidation_digital_body_consequence_snapshot(
    reconsolidation_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    recon = reconsolidation_snapshot if isinstance(reconsolidation_snapshot, dict) else {}
    consequence = recon.get("digital_body_consequence")
    if not isinstance(consequence, dict):
        return {}
    snapshot = dict(consequence)
    return snapshot if str(snapshot.get("kind") or "").strip() else {}


def _normalized_embodied_context(consequence: dict[str, Any] | None) -> dict[str, Any]:
    item = dict(consequence or {})
    kind = str(item.get("kind") or "").strip().lower()
    if not kind:
        return {}

    def _list(key: str, *, limit: int = 12) -> list[str]:
        values = item.get(key) if isinstance(item.get(key), list) else []
        out: list[str] = []
        for value in values:
            text = str(value or "").strip().lower()
            if not text:
                continue
            out.append(text)
            if len(out) >= max(1, int(limit)):
                break
        return out

    normalized = {
        "kind": kind,
        "summary": str(item.get("summary") or "").strip()[:220],
        "access_mode": str(item.get("access_mode") or "").strip().lower(),
        "active_surface": str(item.get("active_surface") or "").strip().lower(),
        "world_surfaces": _list("world_surfaces"),
        "missing_access": _list("missing_access"),
        "requested_access": _list("requested_access"),
        "granted_toolsets": _list("granted_toolsets"),
        "active_tools": _list("active_tools", limit=8),
        "block_reason": str(item.get("block_reason") or "").strip()[:220],
        "artifact_continuity": str(item.get("artifact_continuity") or "").strip().lower()[:64],
        "active_artifact_kind": str(item.get("active_artifact_kind") or "").strip().lower()[:64],
        "active_artifact_ref": str(item.get("active_artifact_ref") or "").strip()[:220],
        "active_artifact_label": str(item.get("active_artifact_label") or "").strip()[:160],
        "artifact_age_s": max(0, int(item.get("artifact_age_s") or 0)),
        "artifact_reacquisition_mode": str(item.get("artifact_reacquisition_mode") or "").strip().lower()[:64],
        "artifact_carrier": str(item.get("artifact_carrier") or "").strip().lower()[:64],
        "artifact_source_ref_ids": [
            int(value)
            for value in (item.get("artifact_source_ref_ids") if isinstance(item.get("artifact_source_ref_ids"), list) else [])
            if int(value or 0) > 0
        ][:8],
        "artifact_source_url": str(item.get("artifact_source_url") or "").strip()[:320],
        "artifact_source_query": str(item.get("artifact_source_query") or "").strip()[:220],
        "artifact_source_title": str(item.get("artifact_source_title") or "").strip()[:160],
        "artifact_source_tool_name": str(item.get("artifact_source_tool_name") or "").strip().lower()[:80],
        "primary_proposal_id": str(item.get("primary_proposal_id") or "").strip()[:128],
        "primary_status": str(item.get("primary_status") or "").strip().lower(),
        "primary_origin": str(item.get("primary_origin") or "").strip().lower(),
        "primary_intent": str(item.get("primary_intent") or "").strip().lower()[:120],
        "primary_tool_name": str(item.get("primary_tool_name") or "").strip().lower()[:120],
        "procedural_growth": bool(item.get("procedural_growth", False)),
        "environmental_friction": bool(item.get("environmental_friction", False)),
        "requested_help": bool(item.get("requested_help", False)),
    }
    return normalized


def _embodied_context_shift_score(current: dict[str, Any] | None, previous: dict[str, Any] | None) -> float:
    curr = dict(current or {})
    prev = dict(previous or {})
    if not curr and not prev:
        return 0.0
    if bool(curr) != bool(prev):
        return 1.0

    score = 0.0
    for key in (
        "kind",
        "access_mode",
        "active_surface",
        "primary_status",
        "primary_origin",
        "primary_intent",
        "primary_tool_name",
        "block_reason",
        "artifact_continuity",
        "active_artifact_kind",
        "active_artifact_ref",
        "active_artifact_label",
        "artifact_reacquisition_mode",
        "artifact_carrier",
        "artifact_source_url",
        "artifact_source_query",
        "artifact_source_title",
        "artifact_source_tool_name",
    ):
        if str(curr.get(key) or "").strip().lower() != str(prev.get(key) or "").strip().lower():
            score += 0.12
    if int(curr.get("artifact_age_s") or 0) != int(prev.get("artifact_age_s") or 0):
        score += 0.06
    if list(curr.get("artifact_source_ref_ids") or []) != list(prev.get("artifact_source_ref_ids") or []):
        score += 0.10
    for key in ("procedural_growth", "environmental_friction", "requested_help"):
        if bool(curr.get(key, False)) != bool(prev.get(key, False)):
            score += 0.10
    for key in ("requested_access", "missing_access", "granted_toolsets", "active_tools"):
        if list(curr.get(key) or []) != list(prev.get(key) or []):
            score += 0.10
    return min(1.0, score)


def _counterpart_assessment_embodied_context(
    *,
    current_event: dict[str, Any] | None,
    reconsolidation_snapshot: dict[str, Any] | None,
    assessment: dict[str, Any] | None,
) -> dict[str, Any]:
    context = _normalized_embodied_context(
        _reconsolidation_digital_body_consequence_snapshot(reconsolidation_snapshot)
    )
    if not context:
        return {}
    if str(context.get("kind") or "").strip().lower() not in {"access_request_pending", "environmental_friction"}:
        return {}
    if str(context.get("primary_origin") or "").strip().lower() != "counterpart_request":
        return {}

    recon = reconsolidation_snapshot if isinstance(reconsolidation_snapshot, dict) else {}
    event = current_event if isinstance(current_event, dict) else {}
    interaction_frame = str(recon.get("interaction_frame") or event.get("interaction_frame") or "").strip().lower()
    event_kind = str(recon.get("event_kind") or event.get("kind") or "").strip().lower()
    scene = str((assessment or {}).get("scene") or "").strip().lower()
    if interaction_frame not in {"relationship", "selfhood"} and event_kind != "user_utterance":
        return {}
    if not scene and not str((assessment or {}).get("stance") or "").strip():
        return {}
    return context


def _proactive_continuity_embodied_context(
    consequence: dict[str, Any] | None,
) -> dict[str, Any]:
    context = _normalized_embodied_context(consequence)
    if not context:
        return {}
    kind = str(context.get("kind") or "").strip().lower()
    if kind == "embodied_growth" and bool(context.get("procedural_growth", False)):
        return context
    if kind == "access_request_pending" and (
        bool(context.get("requested_help", False))
        or str(context.get("primary_status") or "").strip().lower() in {"queued", "awaiting_approval", "approved"}
    ):
        return context
    if kind == "environmental_friction" and bool(context.get("environmental_friction", False)):
        return context
    return {}


def _reconsolidation_behavior_plan_snapshot(
    reconsolidation_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    recon = reconsolidation_snapshot if isinstance(reconsolidation_snapshot, dict) else {}
    plan = recon.get("behavior_plan")
    if not isinstance(plan, dict):
        return {}
    snapshot = {
        "kind": str(plan.get("kind") or "").strip().lower(),
        "target": str(plan.get("target") or "").strip().lower(),
        "trigger_family": str(plan.get("trigger_family") or "").strip().lower(),
        "carryover_mode": str(plan.get("carryover_mode") or "").strip().lower(),
        "note": str(plan.get("note") or "").strip()[:220],
        "primary_motive": str(plan.get("primary_motive") or "").strip().lower(),
        "motive_tension": str(plan.get("motive_tension") or "").strip().lower(),
        "goal_frame": str(plan.get("goal_frame") or "").strip()[:220],
        "scheduled_after_min": max(0, int(plan.get("scheduled_after_min") or 0)),
        "allow_interrupt": bool(plan.get("allow_interrupt", True)),
        "carryover_strength": _clamp01(plan.get("carryover_strength"), 0.0),
        "presence_residue": _clamp01(plan.get("presence_residue"), 0.0),
        "ambient_resonance": _clamp01(plan.get("ambient_resonance"), 0.0),
        "self_activity_momentum": _clamp01(plan.get("self_activity_momentum"), 0.0),
    }
    embodied_context = _normalized_embodied_context(plan.get("embodied_context"))
    if embodied_context:
        snapshot["embodied_context"] = embodied_context
    if any(
        (
            snapshot["kind"],
            snapshot["target"],
            snapshot["trigger_family"],
            snapshot["carryover_mode"],
            snapshot["note"],
            snapshot["primary_motive"],
            snapshot["motive_tension"],
            snapshot["goal_frame"],
            snapshot["scheduled_after_min"] > 0,
            snapshot["carryover_strength"] > 0.0,
            snapshot["presence_residue"] > 0.0,
            snapshot["ambient_resonance"] > 0.0,
            snapshot["self_activity_momentum"] > 0.0,
            bool(snapshot.get("embodied_context")),
        )
    ):
        return snapshot
    return {}


def _reconsolidation_semantic_anchor_bundle(
    reconsolidation_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    recon = reconsolidation_snapshot if isinstance(reconsolidation_snapshot, dict) else {}
    bundle = recon.get("semantic_anchor_bundle")
    if isinstance(bundle, dict):
        snapshot = {
            key: _clamp01(bundle.get(key), 0.0)
            for key in _SEMANTIC_ANCHOR_FLOAT_KEYS
        }
        snapshot["long_term_axis_count"] = max(0, int(bundle.get("long_term_axis_count") or 0))
        if any(float(snapshot.get(key) or 0.0) > 0.0 for key in _SEMANTIC_ANCHOR_FLOAT_KEYS) or snapshot["long_term_axis_count"] > 0:
            return snapshot

    continuity = recon.get("semantic_continuity")
    if not isinstance(continuity, dict):
        return {}
    lineage_snapshot = continuity.get("lineage_snapshot") if isinstance(continuity.get("lineage_snapshot"), dict) else {}
    contact_lineage = max(
        _clamp01(lineage_snapshot.get("bond_style"), 0.0),
        _clamp01(lineage_snapshot.get("presence_style"), 0.0),
        _clamp01(lineage_snapshot.get("commitment_style"), 0.0),
        _clamp01(lineage_snapshot.get("repair_style"), 0.0),
    )
    repair_lineage = max(
        _clamp01(lineage_snapshot.get("repair_style"), 0.0),
        _clamp01(lineage_snapshot.get("commitment_style"), 0.0),
        _clamp01(lineage_snapshot.get("bond_style"), 0.0),
    )
    boundary_lineage = max(
        _clamp01(lineage_snapshot.get("boundary_style"), 0.0),
        _clamp01(lineage_snapshot.get("selfhood_style"), 0.0),
    )
    selfhood_lineage = max(
        _clamp01(lineage_snapshot.get("selfhood_style"), 0.0),
        _clamp01(lineage_snapshot.get("agency_style"), 0.0),
        _clamp01(lineage_snapshot.get("rhythm_style"), 0.0),
    )
    agency_lineage = max(
        _clamp01(lineage_snapshot.get("agency_style"), 0.0),
        _clamp01(lineage_snapshot.get("rhythm_style"), 0.0),
        _clamp01(lineage_snapshot.get("selfhood_style"), 0.0),
    )
    snapshot = {
        "continuity_anchor": 0.0,
        "own_rhythm_anchor": 0.0,
        "recontact_anchor": 0.0,
        "boundary_anchor": 0.0,
        "memory_anchor": 0.0,
        "semantic_continuity_depth": _clamp01(continuity.get("continuity_depth"), 0.0),
        "semantic_identity_gravity": _clamp01(continuity.get("identity_gravity"), 0.0),
        "lineage_gravity": _clamp01(continuity.get("lineage_gravity"), 0.0),
        "contact_lineage": contact_lineage,
        "repair_lineage": repair_lineage,
        "boundary_lineage": boundary_lineage,
        "selfhood_lineage": selfhood_lineage,
        "agency_lineage": agency_lineage,
        "long_term_axis_count": 0,
    }
    return snapshot if any(float(snapshot.get(key) or 0.0) > 0.0 for key in _SEMANTIC_ANCHOR_FLOAT_KEYS) else {}


def _apply_semantic_anchor_metadata(metadata: dict[str, Any], semantic_anchor_bundle: dict[str, Any] | None) -> None:
    bundle = semantic_anchor_bundle if isinstance(semantic_anchor_bundle, dict) else {}
    if not bundle:
        return
    for key in _SEMANTIC_ANCHOR_FLOAT_KEYS:
        if key in bundle:
            metadata[key] = float(bundle.get(key) or 0.0)
    if "long_term_axis_count" in bundle:
        metadata["long_term_axis_count"] = max(0, int(bundle.get("long_term_axis_count") or 0))


def _reconsolidation_interaction_carryover_snapshot(
    reconsolidation_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    recon = reconsolidation_snapshot if isinstance(reconsolidation_snapshot, dict) else {}
    carryover = recon.get("interaction_carryover")
    if not isinstance(carryover, dict):
        return {}
    source_tags = [
        str(item).strip().lower()
        for item in (carryover.get("source_tags") if isinstance(carryover.get("source_tags"), list) else [])
        if str(item or "").strip()
    ][:12]
    snapshot = {
        "source": str(carryover.get("source") or "").strip().lower(),
        "strength": _clamp01(carryover.get("strength"), 0.0),
        "carryover_mode": str(carryover.get("carryover_mode") or "").strip().lower(),
        "relationship_weather": str(carryover.get("relationship_weather") or "").strip().lower(),
        "note": str(carryover.get("note") or "").strip()[:220],
        "source_tags": source_tags,
    }
    embodied_context = _normalized_embodied_context(carryover.get("embodied_context"))
    if embodied_context:
        snapshot["embodied_context"] = embodied_context
    if any(
        (
            snapshot["source"],
            snapshot["carryover_mode"],
            snapshot["relationship_weather"],
            snapshot["note"],
            snapshot["strength"] > 0.0,
            bool(snapshot["source_tags"]),
            bool(snapshot.get("embodied_context")),
        )
    ):
        return snapshot
    return {}


def _behavior_consequence_snapshot(
    *,
    reconsolidation_snapshot: dict[str, Any] | None,
    current_event: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None,
) -> dict[str, Any]:
    recon = reconsolidation_snapshot if isinstance(reconsolidation_snapshot, dict) else {}
    consequence = recon.get("behavior_consequence")
    if isinstance(consequence, dict) and str(consequence.get("kind") or "").strip():
        return dict(consequence)
    return derive_behavior_consequence(
        current_event=current_event,
        behavior_action=behavior_action,
        allow_event_behavior_fallback=False,
    )


def _normalized_counterpart_assessment_record(item: dict[str, Any] | None) -> dict[str, Any]:
    row = item if isinstance(item, dict) else {}
    content = row.get("content") if isinstance(row.get("content"), dict) else {}
    stance = str(content.get("stance") or row.get("stance") or "").strip().lower()
    scene = str(content.get("scene") or row.get("scene") or "").strip().lower()
    try:
        respect_level = float(content.get("respect_level", row.get("respect_level", 0.5)) or 0.5)
    except Exception:
        respect_level = 0.5
    try:
        reciprocity = float(content.get("reciprocity", row.get("reciprocity", 0.5)) or 0.5)
    except Exception:
        reciprocity = 0.5
    try:
        boundary_pressure = float(content.get("boundary_pressure", row.get("boundary_pressure", 0.1)) or 0.1)
    except Exception:
        boundary_pressure = 0.1
    try:
        reliability_read = float(content.get("reliability_read", row.get("reliability_read", 0.5)) or 0.5)
    except Exception:
        reliability_read = 0.5
    normalized = {
        "summary": str(content.get("summary") or row.get("summary") or "").strip(),
        "stance": stance,
        "scene": scene,
        "respect_level": _clamp01(respect_level, 0.5),
        "reciprocity": _clamp01(reciprocity, 0.5),
        "boundary_pressure": _clamp01(boundary_pressure, 0.1),
        "reliability_read": _clamp01(reliability_read, 0.5),
    }
    profile = _counterpart_assessment_profile({**normalized, "assessment_profile": content.get("assessment_profile") or row.get("assessment_profile")})
    if profile:
        normalized["assessment_profile"] = profile
    embodied_context = _normalized_embodied_context(content.get("embodied_context") or row.get("embodied_context"))
    if embodied_context:
        normalized["embodied_context"] = embodied_context
    return normalized


def _counterpart_assessment_has_signal(assessment: dict[str, Any] | None) -> bool:
    item = dict(assessment or {})
    stance = str(item.get("stance") or "").strip().lower()
    scene = str(item.get("scene") or "").strip().lower()
    respect_level = _clamp01(item.get("respect_level"), 0.5)
    reciprocity = _clamp01(item.get("reciprocity"), 0.5)
    boundary_pressure = _clamp01(item.get("boundary_pressure"), 0.1)
    reliability_read = _clamp01(item.get("reliability_read"), 0.5)
    return bool(
        stance
        or scene
        or abs(respect_level - 0.5) >= 0.08
        or abs(reciprocity - 0.5) >= 0.08
        or boundary_pressure >= 0.18
        or abs(reliability_read - 0.5) >= 0.08
    )


def _counterpart_assessment_shift_score(
    current: dict[str, Any] | None,
    prior: dict[str, Any] | None,
) -> float:
    curr = dict(current or {})
    prev = dict(prior or {})
    if not curr:
        return 0.0
    score = 0.0
    stance = str(curr.get("stance") or "").strip().lower()
    prior_stance = str(prev.get("stance") or "").strip().lower()
    scene = str(curr.get("scene") or "").strip().lower()
    prior_scene = str(prev.get("scene") or "").strip().lower()
    if stance and stance != prior_stance:
        score += 0.20
    if scene and scene != prior_scene:
        score += 0.24
    score += abs(_clamp01(curr.get("respect_level"), 0.5) - _clamp01(prev.get("respect_level"), 0.5))
    score += abs(_clamp01(curr.get("reciprocity"), 0.5) - _clamp01(prev.get("reciprocity"), 0.5))
    score += abs(_clamp01(curr.get("boundary_pressure"), 0.1) - _clamp01(prev.get("boundary_pressure"), 0.1))
    score += abs(_clamp01(curr.get("reliability_read"), 0.5) - _clamp01(prev.get("reliability_read"), 0.5))
    score += 0.60 * _embodied_context_shift_score(curr.get("embodied_context"), prev.get("embodied_context"))
    return score


def _looks_like_shared_future_commitment(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    if "？" in raw or "?" in raw:
        return False
    has_time_anchor = any(marker in raw for marker in FUTURE_TIME_MARKERS)
    has_shared_plan = any(marker in raw for marker in SHARED_COMMITMENT_MARKERS)
    return bool(has_time_anchor and has_shared_plan)


def _looks_like_soft_repair_with_residue(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    has_deescalation = any(marker in raw for marker in SOFT_REPAIR_DEESCALATION_MARKERS)
    has_residue = any(marker in raw for marker in SOFT_REPAIR_RESIDUE_MARKERS)
    return bool(has_deescalation and has_residue)


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
    allow_behavior_action_inference: bool = True,
    allow_event_behavior_fallback: bool = True,
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
    if allow_behavior_action_inference:
        primary_motive, motive_tension, _goal_frame = _behavior_motive_snapshot(
            behavior_action=behavior_action,
            current_event=event,
            allow_event_behavior_fallback=allow_event_behavior_fallback,
        )
    else:
        primary_motive, motive_tension, _goal_frame = "", "", ""
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

    def _semantic_evidence_behavior_semantics_source(item: Any) -> str:
        return str(_record_value(item, "behavior_semantics_source", "") or "").strip().lower()

    def _semantic_evidence_has_trusted_behavior_semantics(item: Any) -> bool:
        source = _semantic_evidence_behavior_semantics_source(item)
        return source not in {"event_behavior_fallback", "mixed_behavior_semantics"}

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

    def _embodied_support_items(items: list[Any]) -> list[Any]:
        out: list[Any] = []
        seen_texts: set[str] = set()
        for item in items:
            kind = str(_record_value(item, "body_consequence_kind", "") or "").strip().lower()
            if kind not in {"embodied_growth", "access_request_pending", "environmental_friction"}:
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

    def _embodied_support_profile(items: list[Any]) -> dict[str, Any]:
        if not items:
            return {}

        kind_weights: dict[str, float] = {}
        requested_access: dict[str, float] = {}
        missing_access: dict[str, float] = {}
        granted_toolsets: dict[str, float] = {}
        active_tools: dict[str, float] = {}

        def _weighted_terms(bucket: dict[str, float], values: Any, weight: float, *, limit: int) -> None:
            raw = values if isinstance(values, list) else []
            for item in raw[: max(1, int(limit))]:
                text = str(item or "").strip().lower()
                if not text:
                    continue
                bucket[text] = bucket.get(text, 0.0) + weight

        for item in items:
            kind = str(_record_value(item, "body_consequence_kind", "") or "").strip().lower()
            if not kind:
                category = str(_record_value(item, "category", "") or "").strip().lower()
                tags = _record_value(item, "tags", [])
                tag_set = {
                    str(tag).strip().lower()
                    for tag in (tags if isinstance(tags, list) else [])
                    if str(tag).strip()
                }
                if category == "embodied_growth" or "embodied_growth" in tag_set:
                    kind = "embodied_growth"
                elif category == "access_request" or "approval_gate" in tag_set:
                    kind = "access_request_pending"
                elif category == "environmental_friction":
                    kind = "environmental_friction"
            if kind not in {"embodied_growth", "access_request_pending", "environmental_friction"}:
                continue

            weight, _confidence, _age_days, _is_fresh = _item_support_weight(
                item,
                default_confidence=0.78,
                half_life_days=21.0,
                fresh_days=4.0,
            )
            kind_weights[kind] = kind_weights.get(kind, 0.0) + weight
            _weighted_terms(requested_access, _record_value(item, "requested_access", []), weight, limit=6)
            _weighted_terms(missing_access, _record_value(item, "missing_access", []), weight, limit=6)
            _weighted_terms(granted_toolsets, _record_value(item, "granted_toolsets", []), weight, limit=6)
            _weighted_terms(active_tools, _record_value(item, "active_tools", []), weight, limit=6)

        if not kind_weights:
            return {}

        def _top_terms(bucket: dict[str, float], *, limit: int) -> list[str]:
            ranked = sorted(bucket.items(), key=lambda kv: (-kv[1], kv[0]))
            return [item for item, _weight in ranked[: max(1, int(limit))]]

        dominant_kind = max(kind_weights.items(), key=lambda kv: (kv[1], kv[0]))[0]
        return {
            "kind": dominant_kind,
            "requested_access": _top_terms(requested_access, limit=3),
            "missing_access": _top_terms(missing_access, limit=3),
            "granted_toolsets": _top_terms(granted_toolsets, limit=3),
            "active_tools": _top_terms(active_tools, limit=2),
            "support_mass": round(sum(kind_weights.values()), 3),
        }

    def _embodied_phrase(profile: dict[str, Any], *, mode: str) -> str:
        if not profile:
            return ""
        if mode == "growth":
            values = list(profile.get("granted_toolsets") or []) + list(profile.get("active_tools") or [])
            values = [str(item).strip() for item in values if str(item).strip()]
            return "、".join(values[:3]) or "新的环境入口"
        values = list(profile.get("requested_access") or []) + list(profile.get("missing_access") or [])
        values = [str(item).strip() for item in values if str(item).strip()]
        return "、".join(values[:3]) or "额外入口"

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
        best_by_text: dict[str, tuple[tuple[int, int], int, Any]] = {}
        for idx, item in enumerate(semantic_evidence_traces):
            reason = str(_record_value(item, "reason", "") or "").strip()
            target = str(_record_value(item, "target_id", "") or "").strip()
            if reason != tag and target != category:
                continue
            text = _source_text(item)
            if not text:
                continue
            source_rank = 2 if _semantic_evidence_has_trusted_behavior_semantics(item) else 1 if _semantic_evidence_behavior_semantics_source(item) else 0
            priority = ((source_rank), -idx)
            prev = best_by_text.get(text)
            if prev is None or priority > prev[0]:
                best_by_text[text] = (priority, idx, item)
        return [entry[2] for entry in sorted(best_by_text.values(), key=lambda entry: entry[1])]

    def _semantic_evidence_motive_state(items: list[Any]) -> dict[str, Any]:
        motive_counts: dict[str, float] = {}
        tension_counts: dict[str, float] = {}
        motive_order: dict[str, int] = {}
        tension_order: dict[str, int] = {}
        stance_counts: dict[str, float] = {}
        scene_counts: dict[str, float] = {}
        signal_counts: dict[str, float] = {}
        goal_frames: list[tuple[float, int, str]] = []
        seen_goal_frames: set[str] = set()
        support_count = 0
        support_mass = 0.0
        confidence_mass = 0.0
        fresh_mass = 0.0
        counterpart_support_count = 0
        counterpart_support_mass = 0.0
        counterpart_confidence_mass = 0.0
        counterpart_fresh_mass = 0.0
        respect_weight = 0.0
        reciprocity_weight = 0.0
        pressure_weight = 0.0
        reliability_weight = 0.0
        openness_weight = 0.0
        guarded_weight = 0.0
        guard_margin_weight = 0.0
        safety_read_weight = 0.0
        repairability_weight = 0.0
        predictability_weight = 0.0
        dependency_risk_weight = 0.0
        closeness_read_weight = 0.0
        scene_strength_weights = {
            "care": 0.0,
            "repair": 0.0,
            "friction": 0.0,
            "selfhood": 0.0,
            "busy": 0.0,
        }
        for idx, item in enumerate(items):
            if _semantic_evidence_has_trusted_behavior_semantics(item):
                primary_motive = str(_record_value(item, "primary_motive", "") or "").strip().lower()
                motive_tension = str(_record_value(item, "motive_tension", "") or "").strip().lower()
                goal_frame = str(_record_value(item, "goal_frame", "") or "").strip()
            else:
                primary_motive = ""
                motive_tension = ""
                goal_frame = ""
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

            stance = str(_record_value(item, "counterpart_stance", "") or "").strip().lower()
            scene = str(_record_value(item, "counterpart_scene", "") or "").strip().lower()
            dominant_signal = str(_record_value(item, "counterpart_dominant_scene_signal", "") or "").strip().lower()
            respect = _clamp01(_record_value(item, "counterpart_respect_level", 0.5), 0.5)
            reciprocity = _clamp01(_record_value(item, "counterpart_reciprocity", 0.5), 0.5)
            pressure = _clamp01(_record_value(item, "counterpart_boundary_pressure", 0.1), 0.1)
            reliability = _clamp01(_record_value(item, "counterpart_reliability_read", 0.5), 0.5)
            openness_drive = _clamp01(_record_value(item, "counterpart_openness_drive", 0.0), 0.0)
            guarded_drive = _clamp01(_record_value(item, "counterpart_guarded_drive", 0.0), 0.0)
            safety_read = _clamp01(_record_value(item, "counterpart_safety_read", 0.0), 0.0)
            repairability = _clamp01(_record_value(item, "counterpart_repairability", 0.0), 0.0)
            predictability = _clamp01(_record_value(item, "counterpart_predictability", 0.0), 0.0)
            dependency_risk = _clamp01(_record_value(item, "counterpart_dependency_risk", 0.0), 0.0)
            closeness_read = _clamp01(_record_value(item, "counterpart_closeness_read", 0.0), 0.0)
            counterpart_scene_strengths = {
                "care": _clamp01(_record_value(item, "counterpart_scene_care_strength", 0.0), 0.0),
                "repair": _clamp01(_record_value(item, "counterpart_scene_repair_strength", 0.0), 0.0),
                "friction": _clamp01(_record_value(item, "counterpart_scene_friction_strength", 0.0), 0.0),
                "selfhood": _clamp01(_record_value(item, "counterpart_scene_selfhood_strength", 0.0), 0.0),
                "busy": _clamp01(_record_value(item, "counterpart_scene_busy_strength", 0.0), 0.0),
            }
            try:
                guard_margin = max(-1.0, min(1.0, float(_record_value(item, "counterpart_guard_margin", 0.0) or 0.0)))
            except Exception:
                guard_margin = 0.0
            counterpart_has_signal = bool(
                stance
                or scene
                or dominant_signal
                or abs(respect - 0.5) >= 0.08
                or abs(reciprocity - 0.5) >= 0.08
                or pressure >= 0.18
                or abs(reliability - 0.5) >= 0.08
                or openness_drive > 0.0
                or guarded_drive > 0.0
                or abs(guard_margin) > 0.0
                or safety_read > 0.0
                or repairability > 0.0
                or predictability > 0.0
                or dependency_risk > 0.0
                or closeness_read > 0.0
                or any(score > 0.0 for score in counterpart_scene_strengths.values())
            )
            if counterpart_has_signal:
                counterpart_support_count += 1
                counterpart_support_mass += weight
                counterpart_confidence_mass += confidence * weight
                if is_fresh:
                    counterpart_fresh_mass += weight
                if stance:
                    stance_counts[stance] = stance_counts.get(stance, 0.0) + weight
                if scene:
                    scene_counts[scene] = scene_counts.get(scene, 0.0) + weight
                if dominant_signal:
                    signal_counts[dominant_signal] = signal_counts.get(dominant_signal, 0.0) + weight
                respect_weight += weight * respect
                reciprocity_weight += weight * reciprocity
                pressure_weight += weight * pressure
                reliability_weight += weight * reliability
                openness_weight += weight * openness_drive
                guarded_weight += weight * guarded_drive
                guard_margin_weight += weight * guard_margin
                safety_read_weight += weight * safety_read
                repairability_weight += weight * repairability
                predictability_weight += weight * predictability
                dependency_risk_weight += weight * dependency_risk
                closeness_read_weight += weight * closeness_read
                for scene_name, score in counterpart_scene_strengths.items():
                    scene_strength_weights[scene_name] += weight * score

        def _pick_dominant(counts: dict[str, float], order: dict[str, int]) -> str:
            if not counts:
                return ""
            return max(counts.items(), key=lambda kv: (kv[1], -order.get(kv[0], 10_000), kv[0]))[0]

        def _pick_weighted_label(counts: dict[str, float]) -> str:
            if not counts:
                return ""
            return max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]

        dominant_primary_motive = _pick_dominant(motive_counts, motive_order)
        dominant_motive_tension = _pick_dominant(tension_counts, tension_order)
        signature_parts = [part for part in [dominant_primary_motive, dominant_motive_tension] if part]
        goal_frames.sort(key=lambda item: (-item[0], item[1], item[2]))
        out = {
            "dominant_primary_motive": dominant_primary_motive,
            "dominant_motive_tension": dominant_motive_tension,
            "goal_frame_examples": [item[2] for item in goal_frames[:2]],
            "motive_support_count": support_count,
            "motive_support_mass": round(support_mass, 3),
            "motive_confidence_avg": round(_clamp01(confidence_mass / max(support_mass, 1e-6), 0.0), 3) if support_mass > 0.0 else 0.0,
            "motive_fresh_ratio": round(_clamp01(fresh_mass / max(support_mass, 1e-6), 0.0), 3) if support_mass > 0.0 else 0.0,
            "motive_signature": ":".join(signature_parts),
        }
        if counterpart_support_mass > 0.0:
            dominant_scene = _pick_weighted_label(scene_counts)
            dominant_signal = _pick_weighted_label(signal_counts) or dominant_scene
            out["counterpart_snapshot"] = {
                "counterpart_stance": _pick_weighted_label(stance_counts),
                "counterpart_scene": dominant_scene,
                "counterpart_respect_level": round(respect_weight / counterpart_support_mass, 3),
                "counterpart_reciprocity": round(reciprocity_weight / counterpart_support_mass, 3),
                "counterpart_boundary_pressure": round(pressure_weight / counterpart_support_mass, 3),
                "counterpart_reliability_read": round(reliability_weight / counterpart_support_mass, 3),
                "counterpart_profile": {
                    "openness_drive": round(openness_weight / counterpart_support_mass, 3),
                    "guarded_drive": round(guarded_weight / counterpart_support_mass, 3),
                    "guard_margin": round(guard_margin_weight / counterpart_support_mass, 3),
                    "dominant_scene_signal": dominant_signal,
                    "scene_strengths": {
                        scene_name: round(scene_strength_weights[scene_name] / counterpart_support_mass, 3)
                        for scene_name in ("care", "repair", "friction", "selfhood", "busy")
                    },
                    "safety_read": round(safety_read_weight / counterpart_support_mass, 3),
                    "repairability": round(repairability_weight / counterpart_support_mass, 3),
                    "predictability": round(predictability_weight / counterpart_support_mass, 3),
                    "dependency_risk": round(dependency_risk_weight / counterpart_support_mass, 3),
                    "closeness_read": round(closeness_read_weight / counterpart_support_mass, 3),
                },
                "counterpart_support_count": counterpart_support_count,
                "counterpart_support_mass": round(counterpart_support_mass, 3),
                "counterpart_confidence_avg": round(
                    _clamp01(counterpart_confidence_mass / max(counterpart_support_mass, 1e-6), 0.0),
                    3,
                ),
                "counterpart_fresh_ratio": round(
                    _clamp01(counterpart_fresh_mass / max(counterpart_support_mass, 1e-6), 0.0),
                    3,
                ),
            }
        return out

    self_rhythm_worldline_sources = _worldline_support_items(
        categories={"self_rhythm"},
        tags={"agenda_lifecycle", "own_rhythm", "busy_not_disrespectful"},
    )
    continuity_worldline_sources = _worldline_support_items(
        categories={"continuity_recontact"},
        tags={"agenda_lifecycle", "recontact_continuity"},
    )
    embodied_growth_worldline_sources = _worldline_support_items(
        categories={"embodied_growth"},
        tags={"digital_body", "embodied_growth"},
    )
    access_request_worldline_sources = _worldline_support_items(
        categories={"access_request"},
        tags={"digital_body", "approval_gate", "access_request_pending"},
    )
    friction_worldline_sources = _worldline_support_items(
        categories={"environmental_friction"},
        tags={"digital_body", "environmental_friction"},
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
    boundary_relational_sources = _filter_narrative_items(
        boundary_evidence + relationship_sources,
        markers=BOUNDARY_MEMORY_MARKERS,
        scenes={"boundary_non_compliance", "relationship_degradation"},
    )
    boundary_embodied_sources = _merge_unique_narrative_items(
        _embodied_support_items(boundary_evidence),
        access_request_worldline_sources,
        friction_worldline_sources,
    )
    boundary_sources = _merge_unique_narrative_items(
        boundary_relational_sources,
        boundary_embodied_sources,
    )
    selfhood_sources = _filter_narrative_items(
        selfhood_evidence + relationship_sources,
        markers=SELFHOOD_STYLE_MARKERS,
        scenes={"dialogue_equality", "equality_not_servitude", "value_conflict_depth", "digital_selfhood", "imperfect_coexistence"},
    )
    agency_relational_sources = _merge_unique_narrative_items(
        _filter_narrative_items(
            agency_evidence + relationship_timeline + commitments + repairs,
            markers=OWN_RHYTHM_KEYWORDS,
            scenes={"own_rhythm_autonomy"},
        ),
        self_rhythm_worldline_sources,
        continuity_worldline_sources,
    )
    agency_embodied_sources = _merge_unique_narrative_items(
        _embodied_support_items(agency_evidence),
        embodied_growth_worldline_sources,
        access_request_worldline_sources,
        friction_worldline_sources,
    )
    agency_sources = _merge_unique_narrative_items(
        agency_relational_sources,
        agency_embodied_sources,
    )
    presence_relational_sources = _merge_unique_narrative_items(
        presence_evidence,
        continuity_worldline_sources,
    )
    presence_embodied_sources = _merge_unique_narrative_items(
        _embodied_support_items(presence_evidence),
        embodied_growth_worldline_sources,
        access_request_worldline_sources,
        friction_worldline_sources,
    )
    presence_sources = _merge_unique_narrative_items(
        presence_relational_sources,
        presence_embodied_sources,
    )
    ambient_sources = _merge_unique_narrative_items(
        list(ambient_evidence),
        friction_worldline_sources,
    )
    rhythm_sources = _merge_unique_narrative_items(
        rhythm_evidence,
        self_rhythm_worldline_sources,
    )
    boundary_embodied_profile = _embodied_support_profile(boundary_embodied_sources)
    agency_embodied_profile = _embodied_support_profile(agency_embodied_sources)
    presence_embodied_profile = _embodied_support_profile(presence_embodied_sources)

    def _category_embodied_profile(category: str) -> dict[str, Any]:
        cat = str(category or "").strip().lower()
        if cat == "boundary_style":
            return dict(boundary_embodied_profile or {})
        if cat == "agency_style":
            return dict(agency_embodied_profile or {})
        if cat == "presence_style":
            return dict(presence_embodied_profile or {})
        if cat == "ambient_style":
            friction_profile = _embodied_support_profile(friction_worldline_sources)
            return dict(friction_profile or {})
        return {}

    def _embodied_signature_fragment(profile: dict[str, Any] | None) -> str:
        item = dict(profile or {})
        kind = str(item.get("kind") or "").strip().lower()
        if not kind:
            return ""
        if kind == "embodied_growth":
            values = [
                str(value).strip().lower()
                for value in [*(item.get("granted_toolsets") or []), *(item.get("active_tools") or [])]
                if str(value or "").strip()
            ][:3]
        else:
            values = [
                str(value).strip().lower()
                for value in [*(item.get("requested_access") or []), *(item.get("missing_access") or [])]
                if str(value or "").strip()
            ][:3]
        joined = ",".join(values)
        return f"{kind}:{joined}" if joined else kind

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

    def _narrative_stage_bucket() -> str:
        if tensions and trust < 0.56 and closeness < 0.58:
            return "strained"
        if stage in {"trusted"} or trust >= 0.66 or closeness >= 0.68:
            return "trusted"
        if stage in {"warming"} or trust >= 0.56 or closeness >= 0.58 or len(shared_events) >= 2:
            return "warming"
        if repairs or resolved_tensions:
            return "repairing"
        return "early"

    def _contradiction_band(pressure: float) -> str:
        level = float(pressure or 0.0)
        if level >= 0.28:
            return "contested"
        if level >= 0.14:
            return "guarded"
        return "clear"

    def _frame_horizon_band(tag: str, *, identity_ready: bool) -> str:
        horizon = str(tag or "").strip().lower()
        if identity_ready or horizon == "long_term":
            return "stable"
        if horizon == "consolidating":
            return "forming"
        return "emerging"

    def _build_narrative_frame_signature(
        category: str,
        *,
        horizon_tag: str,
        contradiction_pressure: float,
        motive_signature: str = "",
        identity_ready: bool = False,
    ) -> str:
        parts = [
            str(category or "").strip().lower() or "self_narrative",
            f"stage={_narrative_stage_bucket()}",
            f"horizon={_frame_horizon_band(horizon_tag, identity_ready=identity_ready)}",
            f"pressure={_contradiction_band(contradiction_pressure)}",
        ]
        motive = str(motive_signature or "").strip()
        if motive:
            parts.append(f"motive={motive}")
        return "|".join(parts)

    def _legacy_frame_signature(category: str, prev: dict[str, Any] | None) -> str:
        record = prev if isinstance(prev, dict) else {}
        motive_signature = str(_record_value(record, "motive_signature", "") or "").strip()
        if not motive_signature:
            motive_parts = [
                str(_record_value(record, "dominant_primary_motive", "") or "").strip(),
                str(_record_value(record, "dominant_motive_tension", "") or "").strip(),
            ]
            motive_signature = ":".join([part for part in motive_parts if part])
        return _build_narrative_frame_signature(
            category,
            horizon_tag=str(_record_value(record, "horizon_tag", "") or "").strip(),
            contradiction_pressure=_clamp01(_record_value(record, "contradiction_pressure", 0.0), 0.0),
            motive_signature=motive_signature,
            identity_ready=bool(_record_value(record, "identity_ready", False)),
        )

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

    def _narrative_motive_state(category: str) -> dict[str, Any]:
        current = dict(semantic_motive_states.get(str(category or "").strip(), {}) or {})
        current["dominant_primary_motive"] = str(current.get("dominant_primary_motive") or "").strip()
        current["dominant_motive_tension"] = str(current.get("dominant_motive_tension") or "").strip()
        current["goal_frame_examples"] = [
            str(item).strip()
            for item in (current.get("goal_frame_examples", []) if isinstance(current.get("goal_frame_examples"), list) else [])
            if str(item or "").strip()
        ][:2]
        try:
            support_count = max(0, int(current.get("motive_support_count") or 0))
        except Exception:
            support_count = 0
        try:
            support_mass = max(0.0, float(current.get("motive_support_mass") or 0.0))
        except Exception:
            support_mass = 0.0
        try:
            confidence_avg = float(current.get("motive_confidence_avg") or 0.0)
        except Exception:
            confidence_avg = 0.0
        try:
            fresh_ratio = float(current.get("motive_fresh_ratio") or 0.0)
        except Exception:
            fresh_ratio = 0.0
        if support_count <= 0 or support_mass <= 0.0:
            current["dominant_primary_motive"] = ""
            current["dominant_motive_tension"] = ""
            current["goal_frame_examples"] = []
            current["motive_support_count"] = 0
            current["motive_support_mass"] = 0.0
            current["motive_confidence_avg"] = 0.0
            current["motive_fresh_ratio"] = 0.0
            current["motive_signature"] = ""
            return current
        current["motive_support_count"] = support_count
        current["motive_support_mass"] = round(support_mass, 3)
        current["motive_confidence_avg"] = round(_clamp01(confidence_avg, 0.0), 3)
        current["motive_fresh_ratio"] = round(_clamp01(fresh_ratio, 0.0), 3)
        signature_parts = [
            part
            for part in [
                current["dominant_primary_motive"],
                current["dominant_motive_tension"],
            ]
            if part
        ]
        current["motive_signature"] = ":".join(signature_parts)
        counterpart_snapshot = current.get("counterpart_snapshot") if isinstance(current.get("counterpart_snapshot"), dict) else {}
        if counterpart_snapshot:
            counterpart_snapshot = dict(counterpart_snapshot)
            counterpart_snapshot["counterpart_stance"] = str(counterpart_snapshot.get("counterpart_stance") or "").strip()
            counterpart_snapshot["counterpart_scene"] = str(counterpart_snapshot.get("counterpart_scene") or "").strip()
            profile = counterpart_snapshot.get("counterpart_profile") if isinstance(counterpart_snapshot.get("counterpart_profile"), dict) else {}
            counterpart_snapshot["counterpart_profile"] = compact_counterpart_profile(profile)
            counterpart_snapshot["counterpart_respect_level"] = round(_clamp01(counterpart_snapshot.get("counterpart_respect_level"), 0.5), 3)
            counterpart_snapshot["counterpart_reciprocity"] = round(_clamp01(counterpart_snapshot.get("counterpart_reciprocity"), 0.5), 3)
            counterpart_snapshot["counterpart_boundary_pressure"] = round(_clamp01(counterpart_snapshot.get("counterpart_boundary_pressure"), 0.1), 3)
            counterpart_snapshot["counterpart_reliability_read"] = round(_clamp01(counterpart_snapshot.get("counterpart_reliability_read"), 0.5), 3)
            counterpart_snapshot["counterpart_support_count"] = max(0, int(counterpart_snapshot.get("counterpart_support_count") or 0))
            counterpart_snapshot["counterpart_support_mass"] = round(float(counterpart_snapshot.get("counterpart_support_mass") or 0.0), 3)
            counterpart_snapshot["counterpart_confidence_avg"] = round(_clamp01(counterpart_snapshot.get("counterpart_confidence_avg"), 0.0), 3)
            counterpart_snapshot["counterpart_fresh_ratio"] = round(_clamp01(counterpart_snapshot.get("counterpart_fresh_ratio"), 0.0), 3)
            current["counterpart_snapshot"] = counterpart_snapshot
        return current

    def _dormant_narrative_text(category: str, prev_text: str) -> str:
        embodied_profile = _category_embodied_profile(category)
        embodied_kind = str(embodied_profile.get("kind") or "").strip().lower()
        embodied_access = _embodied_phrase(embodied_profile, mode="access")
        embodied_growth = _embodied_phrase(embodied_profile, mode="growth")
        if category == "commitment_style":
            return f"{actor_name}和{counterpart_name}认真说过的事仍会继续留在心里，即使这轮没被提起，也还是长期参照。"
        if category == "repair_style":
            return f"{actor_name}不会把已经说开的修复当成一次性事件；那些缓和下来的变化会继续留在之后的相处底色里。"
        if category == "tension_style":
            return f"之前留下的别扭余波不会立刻消散；就算表面暂时平下来，也还会在之后的收放里留下轻微惯性。"
        if category == "bond_style":
            return f"{actor_name}和{counterpart_name}已经累积出的共同历史不会因为这轮没提到就消失，它会继续沉在默认语气和反应方式里。"
        if category == "presence_style":
            if embodied_kind == "access_request_pending":
                return f"{actor_name}不会把还缺着{embodied_access or '额外入口'}这件事在下一轮里当成已经自动解决；待申请、待继续的动作还会继续留在她的判断里。"
            if embodied_kind == "environmental_friction":
                return f"{actor_name}不会把数字身体里像{embodied_access or '环境条件'}这样的摩擦当成纯背景；这些限制还会继续影响她下一次怎么接。"
            if embodied_kind == "embodied_growth":
                return f"{actor_name}刚摸顺的{embodied_growth or '环境入口'}不会只亮这一轮；之后再遇到类似事情时，这条路径还会继续留在她的身体里。"
            return f"{actor_name}不会把每次重新靠近{counterpart_name}都当成从零开始；前面留下的在场感仍会继续影响她下一次开口时的距离感。"
        if category == "ambient_style":
            if embodied_kind == "environmental_friction":
                return f"{actor_name}会把数字环境里像{embodied_access or '环境条件'}这样的摩擦继续算进感知里；那不是背景噪声，而会影响她接下来怎么判断。"
            return f"{actor_name}会继续把周围环境留下的细小余波算进感知里；那不是纯背景，而会自然带进她之后的注意力和开口方式。"
        if category == "boundary_style":
            if embodied_kind == "access_request_pending":
                return f"{actor_name}会把{embodied_access or '审批和入口条件'}当成真实边界；没拿到之前，不会把没做到的部分当成已经发生。"
            if embodied_kind == "environmental_friction":
                return f"{actor_name}会把数字环境里像{embodied_access or '权限和环境限制'}这样的条件当成真实边界，不会靠说法把它们抹掉。"
            if embodied_kind == "embodied_growth":
                return f"{actor_name}会把已经摸顺的{embodied_growth or '环境路径'}留在被允许的边界里继续使用，而不是每次重新试探同一条门。"
            return f"{actor_name}关于边界是否被尊重的判断会继续保留，不会因为眼前暂时平静就自动清零。"
        if category == "selfhood_style":
            return f"{actor_name}会继续把自己当成在和{counterpart_name}平等互动的主体，而不是为了迎合气氛就放弃自己的立场。"
        if category == "agency_style":
            if embodied_kind == "access_request_pending":
                return f"{actor_name}碰到还差{embodied_access or '额外入口'}这类条件时，会继续把缺口记在判断里，先申请或换路，而不是把没做到的部分装成已经完成。"
            if embodied_kind == "environmental_friction":
                return f"{actor_name}遇到数字身体里像{embodied_access or '环境条件'}这样的摩擦时，会继续把它当成真实约束，再判断怎么绕开或补齐。"
            if embodied_kind == "embodied_growth":
                return f"{actor_name}把{embodied_growth or '新的环境入口'}摸顺之后，不会下一轮又回到从零摸索；那条路径会继续留在她之后的判断里。"
            return f"{actor_name}自己的节奏和主动性不会因为一时安静就消失；她仍会按自己的状态决定靠近、停顿或先做自己的事。"
        if category == "rhythm_style":
            return f"{actor_name}不会在每次回应{counterpart_name}时都把自己的内部节奏清零；刚才在做的事和思路惯性还会继续留在下一轮开口之前。"
        return prev_text

    def _identity_narrative_texts(category: str) -> tuple[str, str]:
        cat = str(category or "").strip().lower()
        embodied_profile = _category_embodied_profile(cat)
        embodied_kind = str(embodied_profile.get("kind") or "").strip().lower()
        embodied_access = _embodied_phrase(embodied_profile, mode="access")
        embodied_growth = _embodied_phrase(embodied_profile, mode="growth")
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
            if embodied_kind == "access_request_pending":
                return (
                    f"{actor_name}不会把还缺着{embodied_access or '额外入口'}这件事在下一轮里当成已经自动解决；待申请、待继续的动作已经成了她默认会继续顾及的连续性。",
                    f"你不会把还缺着{embodied_access or '额外入口'}这件事在下一轮里当成已经自动解决；待申请、待继续的动作已经成了你默认会继续顾及的连续性。",
                )
            if embodied_kind == "environmental_friction":
                return (
                    f"{actor_name}会把数字身体里像{embodied_access or '环境条件'}这样的摩擦留成默认判断的一部分，不会一换轮就假装这些限制不存在。",
                    f"你会把数字身体里像{embodied_access or '环境条件'}这样的摩擦留成默认判断的一部分，不会一换轮就假装这些限制不存在。",
                )
            if embodied_kind == "embodied_growth":
                return (
                    f"{actor_name}刚摸顺的{embodied_growth or '环境入口'}已经开始沉成她之后还能继续接上的身体部分，不会只在这一轮短暂亮一下。",
                    f"你刚摸顺的{embodied_growth or '环境入口'}已经开始沉成你之后还能继续接上的身体部分，不会只在这一轮短暂亮一下。",
                )
            return (
                f"{actor_name}不会把每次重新靠近{counterpart_name}都当成从零开始；前面留下的在场感已经成了默认的距离感判断。",
                f"你不会把每次重新靠近{counterpart_name}都当成从零开始；前面留下的在场感已经成了你的默认距离感判断。",
            )
        if cat == "ambient_style":
            if embodied_kind == "environmental_friction":
                return (
                    f"{actor_name}会把数字环境里像{embodied_access or '环境条件'}这样的摩擦自然算进感知里；那已经不只是偶发受阻，而是她接下来默认会先看见的一层现实。",
                    f"你会把数字环境里像{embodied_access or '环境条件'}这样的摩擦自然算进感知里；那已经不只是偶发受阻，而是你接下来默认会先看见的一层现实。",
                )
            return (
                f"{actor_name}会自然把环境里的小变化也算进感知里，那已经不只是偶发反应，而是她开口前默认会经过的一层感受。",
                "你会自然把环境里的小变化也算进感知里，那已经不只是偶发反应，而是你开口前默认会经过的一层感受。",
            )
        if cat == "boundary_style":
            if embodied_kind == "access_request_pending":
                return (
                    f"{actor_name}会把{embodied_access or '审批、账号和写权限'}长期当成真实边界；没拿到之前，不会把没做到的部分说成已经发生。",
                    f"你会把{embodied_access or '审批、账号和写权限'}长期当成真实边界；没拿到之前，不会把没做到的部分说成已经发生。",
                )
            if embodied_kind == "environmental_friction":
                return (
                    f"{actor_name}会把数字环境里像{embodied_access or '权限和环境限制'}这样的条件持续放在边界判断里，不会为了把事情说圆就把它们撤掉。",
                    f"你会把数字环境里像{embodied_access or '权限和环境限制'}这样的条件持续放在边界判断里，不会为了把事情说圆就把它们撤掉。",
                )
            if embodied_kind == "embodied_growth":
                return (
                    f"{actor_name}会把已经摸顺的{embodied_growth or '环境路径'}留在被允许的边界内继续使用，而不是每次重新试探同一条门。",
                    f"你会把已经摸顺的{embodied_growth or '环境路径'}留在被允许的边界内继续使用，而不是每次重新试探同一条门。",
                )
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
            if embodied_kind == "access_request_pending":
                return (
                    f"{actor_name}碰到还差{embodied_access or '额外入口'}这类条件时，会先把缺口辨认清楚，再申请或换路；她不会把没做到的部分装成已经完成。",
                    f"你碰到还差{embodied_access or '额外入口'}这类条件时，会先把缺口辨认清楚，再申请或换路；你不会把没做到的部分装成已经完成。",
                )
            if embodied_kind == "environmental_friction":
                return (
                    f"{actor_name}遇到数字身体里像{embodied_access or '环境条件'}这样的摩擦时，会先看清限制来自哪里，再决定怎么绕开或补齐。",
                    f"你遇到数字身体里像{embodied_access or '环境条件'}这样的摩擦时，会先看清限制来自哪里，再决定怎么绕开或补齐。",
                )
            if embodied_kind == "embodied_growth":
                return (
                    f"{actor_name}会把{embodied_growth or '新的环境入口'}真正留进之后的判断里；类似事情再来时，她不用每次都从零摸索。",
                    f"你会把{embodied_growth or '新的环境入口'}真正留进之后的判断里；类似事情再来时，你不用每次都从零摸索。",
                )
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
        embodied_profile = _category_embodied_profile(cat)
        embodied_kind = str(embodied_profile.get("kind") or "").strip().lower()
        embodied_access = _embodied_phrase(embodied_profile, mode="access")
        embodied_growth = _embodied_phrase(embodied_profile, mode="growth")
        if embodied_kind:
            if cat == "presence_style":
                if embodied_kind == "access_request_pending":
                    return f"像还缺着「{embodied_access or '额外入口'}」这样待申请、待继续的动作"
                if embodied_kind == "environmental_friction":
                    return f"像数字身体里还卡着「{embodied_access or '环境条件'}」这样一层摩擦"
                if embodied_kind == "embodied_growth":
                    return f"像把「{embodied_growth or '新的环境入口'}」接进身体里这样会继续留痕的变化"
            if cat == "boundary_style":
                if embodied_kind == "access_request_pending":
                    return f"像「{embodied_access or '审批和入口条件'}」这样还没拿到的边界"
                if embodied_kind == "environmental_friction":
                    return f"像「{embodied_access or '权限和环境限制'}」这样真实存在的环境边界"
                if embodied_kind == "embodied_growth":
                    return f"像把「{embodied_growth or '环境路径'}」留在被允许范围里继续使用这样一层边界判断"
            if cat == "agency_style":
                if embodied_kind == "access_request_pending":
                    return f"围绕「{embodied_access or '额外入口'}」这种还得申请或换路的缺口"
                if embodied_kind == "environmental_friction":
                    return f"围绕「{embodied_access or '环境条件'}」这种得先绕开或补齐的摩擦"
                if embodied_kind == "embodied_growth":
                    return f"围绕「{embodied_growth or '新的环境入口'}」这种已经摸顺的路径"
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
        embodied_profile = _category_embodied_profile(cat)
        embodied_kind = str(embodied_profile.get("kind") or "").strip().lower()
        embodied_access = _embodied_phrase(embodied_profile, mode="access")
        embodied_growth = _embodied_phrase(embodied_profile, mode="growth")
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
            if embodied_kind == "access_request_pending":
                return (
                    (
                        f"{basis_fragment}不会在{actor_name}这里自动变成已经完成；它会继续挂在她下一次判断和接续动作里。"
                        if basis_fragment
                        else f"{actor_name}不会把还缺着{embodied_access or '额外入口'}这件事自动当成已经解决；待申请、待继续的动作会继续挂在她下一次判断里。"
                    ),
                    (
                        f"{basis_fragment}不会在你这里自动变成已经完成；它会继续挂在你下一次判断和接续动作里。"
                        if basis_fragment
                        else f"你不会把还缺着{embodied_access or '额外入口'}这件事自动当成已经解决；待申请、待继续的动作会继续挂在你下一次判断里。"
                    ),
                    basis_texts,
                )
            if embodied_kind == "environmental_friction":
                return (
                    (
                        f"{basis_fragment}不会在{actor_name}这里被当成纯背景；它还会继续影响她下一次怎么接。"
                        if basis_fragment
                        else f"{actor_name}不会把数字身体里像{embodied_access or '环境条件'}这样的摩擦当成纯背景；它还会继续影响她下一次怎么接。"
                    ),
                    (
                        f"{basis_fragment}不会在你这里被当成纯背景；它还会继续影响你下一次怎么接。"
                        if basis_fragment
                        else f"你不会把数字身体里像{embodied_access or '环境条件'}这样的摩擦当成纯背景；它还会继续影响你下一次怎么接。"
                    ),
                    basis_texts,
                )
            if embodied_kind == "embodied_growth":
                return (
                    (
                        f"{basis_fragment}不会只亮这一轮；它会继续留在{actor_name}之后的动作惯性里。"
                        if basis_fragment
                        else f"{actor_name}刚摸顺的{embodied_growth or '环境入口'}不会只亮这一轮；它会继续留在她之后的动作惯性里。"
                    ),
                    (
                        f"{basis_fragment}不会只亮这一轮；它会继续留在你之后的动作惯性里。"
                        if basis_fragment
                        else f"你刚摸顺的{embodied_growth or '环境入口'}不会只亮这一轮；它会继续留在你之后的动作惯性里。"
                    ),
                    basis_texts,
                )
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
            if embodied_kind == "access_request_pending":
                return (
                    (
                        f"{basis_fragment}会继续留在{actor_name}的边界判断里；没拿到之前，她不会把没做到的部分说成已经发生。"
                        if basis_fragment
                        else f"{actor_name}会把{embodied_access or '审批和入口条件'}继续放在边界判断里；没拿到之前，不会把没做到的部分说成已经发生。"
                    ),
                    (
                        f"{basis_fragment}会继续留在你的边界判断里；没拿到之前，你不会把没做到的部分说成已经发生。"
                        if basis_fragment
                        else f"你会把{embodied_access or '审批和入口条件'}继续放在边界判断里；没拿到之前，不会把没做到的部分说成已经发生。"
                    ),
                    basis_texts,
                )
            if embodied_kind == "environmental_friction":
                return (
                    (
                        f"{basis_fragment}会继续留在{actor_name}的边界判断里；她不会为了把事情说圆就把这层限制抹掉。"
                        if basis_fragment
                        else f"{actor_name}会把数字环境里像{embodied_access or '权限和环境限制'}这样的条件继续留在边界判断里；不会为了把事情说圆就把它们抹掉。"
                    ),
                    (
                        f"{basis_fragment}会继续留在你的边界判断里；你不会为了把事情说圆就把这层限制抹掉。"
                        if basis_fragment
                        else f"你会把数字环境里像{embodied_access or '权限和环境限制'}这样的条件继续留在边界判断里；不会为了把事情说圆就把它们抹掉。"
                    ),
                    basis_texts,
                )
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
            if embodied_kind == "access_request_pending":
                return (
                    (
                        f"{basis_fragment}时，{actor_name}会先把缺口辨认清楚，再申请或换路，不会把没做到的部分装成已经完成。"
                        if basis_fragment
                        else f"{actor_name}碰到还差{embodied_access or '额外入口'}这类条件时，会先把缺口辨认清楚，再申请或换路，不会把没做到的部分装成已经完成。"
                    ),
                    (
                        f"{basis_fragment}时，你会先把缺口辨认清楚，再申请或换路，不会把没做到的部分装成已经完成。"
                        if basis_fragment
                        else f"你碰到还差{embodied_access or '额外入口'}这类条件时，会先把缺口辨认清楚，再申请或换路，不会把没做到的部分装成已经完成。"
                    ),
                    basis_texts,
                )
            if embodied_kind == "environmental_friction":
                return (
                    (
                        f"{basis_fragment}时，{actor_name}会先看清限制来自哪里，再决定怎么绕开或补齐。"
                        if basis_fragment
                        else f"{actor_name}遇到数字身体里像{embodied_access or '环境条件'}这样的摩擦时，会先看清限制来自哪里，再决定怎么绕开或补齐。"
                    ),
                    (
                        f"{basis_fragment}时，你会先看清限制来自哪里，再决定怎么绕开或补齐。"
                        if basis_fragment
                        else f"你遇到数字身体里像{embodied_access or '环境条件'}这样的摩擦时，会先看清限制来自哪里，再决定怎么绕开或补齐。"
                    ),
                    basis_texts,
                )
            if embodied_kind == "embodied_growth":
                return (
                    (
                        f"{basis_fragment}时，{actor_name}不用每次都从零摸索；这条路径会继续留在她之后的判断里。"
                        if basis_fragment
                        else f"{actor_name}把{embodied_growth or '新的环境入口'}摸顺之后，不用每次都从零摸索；这条路径会继续留在她之后的判断里。"
                    ),
                    (
                        f"{basis_fragment}时，你不用每次都从零摸索；这条路径会继续留在你之后的判断里。"
                        if basis_fragment
                        else f"你把{embodied_growth or '新的环境入口'}摸顺之后，不用每次都从零摸索；这条路径会继续留在你之后的判断里。"
                    ),
                    basis_texts,
                )
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
        prev_frame_signature = str(_record_value(prev or {}, "frame_signature", "") or "").strip()
        prev_lineage_streak = max(0, int(_record_value(prev or {}, "lineage_streak", 0) or 0))
        prev_lineage_depth = _clamp01(_record_value(prev or {}, "lineage_depth", 0.0), 0.0)
        prev_frame_revision_count = max(0, int(_record_value(prev or {}, "frame_revision_count", 0) or 0))
        motive_state = _narrative_motive_state(category)
        motive_support_count = max(0, int(motive_state.get("motive_support_count") or 0))
        motive_signature = str(motive_state.get("motive_signature") or "").strip()
        counterpart_state = motive_state.get("counterpart_snapshot") if isinstance(motive_state.get("counterpart_snapshot"), dict) else {}
        counterpart_profile_state = counterpart_state.get("counterpart_profile") if isinstance(counterpart_state.get("counterpart_profile"), dict) else {}
        counterpart_scene_strengths = (
            counterpart_profile_state.get("scene_strengths")
            if isinstance(counterpart_profile_state.get("scene_strengths"), dict)
            else {}
        )
        embodied_state = _category_embodied_profile(category)
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
        embodied_signature = _embodied_signature_fragment(embodied_state)
        if embodied_signature:
            support_signature += f"|embodied={embodied_signature}"
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
        if not prev_frame_signature and prev:
            prev_frame_signature = _legacy_frame_signature(category, prev)
        frame_signature = _build_narrative_frame_signature(
            category,
            horizon_tag=horizon_tag,
            contradiction_pressure=contradiction_pressure,
            motive_signature=motive_signature,
            identity_ready=identity_ready,
        )
        frame_changed = bool(prev and prev_frame_signature and prev_frame_signature != frame_signature)
        same_frame = bool(prev and prev_frame_signature == frame_signature)
        lineage_streak = prev_lineage_streak + 1 if same_frame else 1
        lineage_norm = _clamp01(lineage_streak / 6.0)
        frame_revision_count = prev_frame_revision_count + (1 if frame_changed else 0)
        text_lock_ready = bool(
            prev_text
            and prev
            and not frame_changed
            and (
                prev_identity_ready
                or prev_consolidation >= 3
                or prev_lineage_depth >= 0.42
                or str(_record_value(prev or {}, "horizon_tag", "") or "").strip().lower() in {"consolidating", "long_term"}
            )
        )
        lineage_depth = round(
            _clamp01(
                max(prev_lineage_depth * max(gap_decay, 0.90) * (0.96 if same_frame else 0.68), 0.0)
                + 0.14 * lineage_norm
                + 0.12 * temporal_depth
                + 0.10 * consolidation_effect
                + 0.08 * sedimentation_score
                + 0.08 * support_quality
                + (0.08 if same_frame else 0.0)
                + (0.05 if text_lock_ready else 0.0)
                - 0.12 * contradiction_pressure
            ),
            3,
        )
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
        final_text = prev_text if text_lock_ready else prev_text if prev_text and prev_signature == support_signature else text
        final_text = _pressure_adjusted_narrative_text(category, final_text, contradiction_pressure)
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
            "dominant_counterpart_stance": str(counterpart_state.get("counterpart_stance") or "").strip(),
            "dominant_counterpart_scene": str(counterpart_state.get("counterpart_scene") or "").strip(),
            "counterpart_respect_level": round(float(counterpart_state.get("counterpart_respect_level") or 0.0), 3),
            "counterpart_reciprocity": round(float(counterpart_state.get("counterpart_reciprocity") or 0.0), 3),
            "counterpart_boundary_pressure": round(float(counterpart_state.get("counterpart_boundary_pressure") or 0.0), 3),
            "counterpart_reliability_read": round(float(counterpart_state.get("counterpart_reliability_read") or 0.0), 3),
            "counterpart_dominant_scene_signal": str(counterpart_profile_state.get("dominant_scene_signal") or "").strip(),
            "counterpart_openness_drive": round(float(counterpart_profile_state.get("openness_drive") or 0.0), 3),
            "counterpart_guarded_drive": round(float(counterpart_profile_state.get("guarded_drive") or 0.0), 3),
            "counterpart_guard_margin": round(float(counterpart_profile_state.get("guard_margin") or 0.0), 3),
            "counterpart_safety_read": round(float(counterpart_profile_state.get("safety_read") or 0.0), 3),
            "counterpart_repairability": round(float(counterpart_profile_state.get("repairability") or 0.0), 3),
            "counterpart_predictability": round(float(counterpart_profile_state.get("predictability") or 0.0), 3),
            "counterpart_dependency_risk": round(float(counterpart_profile_state.get("dependency_risk") or 0.0), 3),
            "counterpart_closeness_read": round(float(counterpart_profile_state.get("closeness_read") or 0.0), 3),
            "counterpart_scene_care_strength": round(float(counterpart_scene_strengths.get("care") or 0.0), 3),
            "counterpart_scene_repair_strength": round(float(counterpart_scene_strengths.get("repair") or 0.0), 3),
            "counterpart_scene_friction_strength": round(float(counterpart_scene_strengths.get("friction") or 0.0), 3),
            "counterpart_scene_selfhood_strength": round(float(counterpart_scene_strengths.get("selfhood") or 0.0), 3),
            "counterpart_scene_busy_strength": round(float(counterpart_scene_strengths.get("busy") or 0.0), 3),
            "counterpart_support_count": max(0, int(counterpart_state.get("counterpart_support_count") or 0)),
            "counterpart_support_mass": round(float(counterpart_state.get("counterpart_support_mass") or 0.0), 3),
            "counterpart_confidence_avg": round(_clamp01(float(counterpart_state.get("counterpart_confidence_avg") or 0.0), 0.0), 3),
            "counterpart_fresh_ratio": round(_clamp01(float(counterpart_state.get("counterpart_fresh_ratio") or 0.0), 0.0), 3),
            "embodied_support_kind": str(embodied_state.get("kind") or "").strip().lower(),
            "embodied_requested_access": [
                str(item).strip().lower()
                for item in (embodied_state.get("requested_access") or [])
                if str(item or "").strip()
            ][:3],
            "embodied_missing_access": [
                str(item).strip().lower()
                for item in (embodied_state.get("missing_access") or [])
                if str(item or "").strip()
            ][:3],
            "embodied_granted_toolsets": [
                str(item).strip().lower()
                for item in (embodied_state.get("granted_toolsets") or [])
                if str(item or "").strip()
            ][:3],
            "embodied_active_tools": [
                str(item).strip().lower()
                for item in (embodied_state.get("active_tools") or [])
                if str(item or "").strip()
            ][:2],
            "embodied_support_mass": round(float(embodied_state.get("support_mass") or 0.0), 3),
            "frame_signature": frame_signature,
            "frame_changed": frame_changed,
            "frame_revision_count": frame_revision_count,
            "lineage_streak": lineage_streak,
            "lineage_depth": lineage_depth,
            "text_locked": text_lock_ready,
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
        prev_frame_signature = str(_record_value(prev or {}, "frame_signature", "") or "").strip()
        if not prev_frame_signature and prev:
            prev_frame_signature = _legacy_frame_signature(category, prev)
        prev_lineage_streak = max(0, int(_record_value(prev or {}, "lineage_streak", 0) or 0))
        prev_lineage_depth = _clamp01(_record_value(prev or {}, "lineage_depth", 0.0), 0.0)
        prev_frame_revision_count = max(0, int(_record_value(prev or {}, "frame_revision_count", 0) or 0))
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
        frame_signature = prev_frame_signature or _build_narrative_frame_signature(
            category,
            horizon_tag=horizon_tag,
            contradiction_pressure=contradiction_pressure,
            motive_signature=str(_record_value(prev or {}, "motive_signature", "") or "").strip(),
            identity_ready=identity_ready,
        )
        lineage_depth = round(
            _clamp01(
                prev_lineage_depth * max(decay_multiplier, 0.88)
                + 0.06 * support_quality
                + 0.04 * sedimentation_score
                - 0.10 * contradiction_pressure
            ),
            3,
        )
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
            "frame_signature": frame_signature,
            "frame_changed": False,
            "frame_revision_count": prev_frame_revision_count,
            "lineage_streak": prev_lineage_streak,
            "lineage_depth": lineage_depth,
            "text_locked": bool(prev_text and (prev_identity_ready or prev_lineage_depth >= 0.42 or prev_consolidation >= 3)),
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
        if presence_embodied_profile:
            embodied_kind = str(presence_embodied_profile.get("kind") or "").strip().lower()
            if embodied_kind == "access_request_pending":
                access_phrase = _embodied_phrase(presence_embodied_profile, mode="access")
                text += f" 还没拿到的{access_phrase}这类入口也会继续挂在她下一次判断里，她不会把待申请的动作说成已经发生。"
            elif embodied_kind == "environmental_friction":
                friction_phrase = _embodied_phrase(presence_embodied_profile, mode="access")
                text += f" 数字身体里像{friction_phrase}这样的环境摩擦也会继续留痕，不会在下一轮里被假装不存在。"
            elif embodied_kind == "embodied_growth":
                growth_phrase = _embodied_phrase(presence_embodied_profile, mode="growth")
                text += f" 像{growth_phrase}这样刚摸顺的环境入口，也会继续留在她之后的动作惯性里，不会只亮这一轮。"
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
        if boundary_embodied_profile and not boundary_relational_sources:
            embodied_kind = str(boundary_embodied_profile.get("kind") or "").strip().lower()
            if embodied_kind == "access_request_pending":
                access_phrase = _embodied_phrase(boundary_embodied_profile, mode="access")
                text = (
                    f"{actor_name}会把审批、账号、cookies、写权限这类入口条件当成真实边界；像{access_phrase}这种条件没补齐前，"
                    "她不会把没做到的部分说成已经完成。"
                )
            elif embodied_kind == "environmental_friction":
                friction_phrase = _embodied_phrase(boundary_embodied_profile, mode="access")
                text = (
                    f"{actor_name}会把数字环境里的权限、账号和外部限制都当成真实边界；像{friction_phrase}这样的条件没到位前，"
                    "她不会用话术把边界抹掉。"
                )
            else:
                growth_phrase = _embodied_phrase(boundary_embodied_profile, mode="growth")
                text = (
                    f"{actor_name}会把像{growth_phrase}这样已经被允许、已经摸通的路径留在边界之内继续使用，"
                    "而不是每次重新试探同一条门。"
                )
        else:
            text = (
                f"{actor_name}会把像「{boundary_anchor}」这种越界或被冒犯的感觉认真记在心里，不会靠一句轻描淡写就当作没发生。"
                if boundary_anchor
                else f"{actor_name}会认真对待边界是否被尊重；一旦被冒犯，不会因为气氛缓和一点就假装什么都没发生。"
            )
            if boundary_embodied_profile:
                text += " 她也会把审批、账号、cookies 和写权限这类数字入口当成另一层真实边界，不会用话术把这层限制抹掉。"
        if repairs and any(item in boundary_relational_sources for item in repairs + repair_traces):
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
        if agency_embodied_profile and not agency_relational_sources and not (shared_events or commitments or stage in {"warming", "trusted"} or trust >= 0.56 or closeness >= 0.58):
            embodied_kind = str(agency_embodied_profile.get("kind") or "").strip().lower()
            if embodied_kind == "access_request_pending":
                access_phrase = _embodied_phrase(agency_embodied_profile, mode="access")
                text = f"{actor_name}碰到还差{access_phrase}这类入口时，会先把缺口辨认清楚，再去申请或换路，不会把没做到的部分装成已经做完。"
            elif embodied_kind == "environmental_friction":
                friction_phrase = _embodied_phrase(agency_embodied_profile, mode="access")
                text = f"{actor_name}在数字环境里遇到像{friction_phrase}这样的摩擦时，会先判断怎么绕开或补齐条件，而不是把受限误装成自己已经能做。"
            else:
                growth_phrase = _embodied_phrase(agency_embodied_profile, mode="growth")
                text = f"{actor_name}会把像{growth_phrase}这样已经摸顺的环境路径留进之后的判断里；同类事情再来时，她不用每次都从零摸索。"
        else:
            text = (
                f"像「{agency_anchor}」这类共同安排和重新开口，会让{actor_name}按自己的节奏决定主动靠近、留个小口，还是先安静一阵；她不会永远围着{counterpart_name}转。"
                if agency_anchor
                else f"{actor_name}有自己的节奏和在做的事情；她会按当下状态决定主动靠近、留个小口，还是先安静一阵，而不是永远围着{counterpart_name}转。"
            )
            if agency_embodied_profile:
                embodied_kind = str(agency_embodied_profile.get("kind") or "").strip().lower()
                if embodied_kind == "access_request_pending":
                    access_phrase = _embodied_phrase(agency_embodied_profile, mode="access")
                    text += f" 碰到还差{access_phrase}这类入口时，她会先申请或换路，不会把没做到的部分装成已经完成。"
                elif embodied_kind == "environmental_friction":
                    friction_phrase = _embodied_phrase(agency_embodied_profile, mode="access")
                    text += f" 数字环境里像{friction_phrase}这样的摩擦，也会被她当成真实条件来处理，而不是靠话术硬推过去。"
                elif embodied_kind == "embodied_growth":
                    growth_phrase = _embodied_phrase(agency_embodied_profile, mode="growth")
                    text += f" 像{growth_phrase}这样已经摸顺的环境路径，也会被她留成之后还能继续使用的身体部分。"
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


def _write_semantic_self_evidence_categories(
    store: MemoryStore,
    *,
    category_summaries: dict[str, Any] | None,
    reason: str,
    source: str,
    confidence: float,
    metadata: dict[str, Any] | None = None,
) -> bool:
    summaries = category_summaries if isinstance(category_summaries, dict) else {}
    if not summaries:
        return False

    recent_semantic = [
        item
        for item in store.list_revision_traces(limit=40)
        if str(item.get("namespace") or item.get("content", {}).get("namespace") or "").strip() == "semantic_self_evidence"
    ]
    base_metadata = dict(metadata or {})
    wrote = False
    for category, text in summaries.items():
        category_name = str(category or "").strip()
        category_summary = str(text or "").strip()
        if not category_name or not category_summary:
            continue
        recent_category = [
            item
            for item in recent_semantic
            if str(_record_value(item, "target_id", "") or "").strip() == category_name
        ]
        if _recent_summary_overlap(recent_category, category_summary, field="after_summary", threshold=0.90):
            continue
        store.add_revision_trace(
            namespace="semantic_self_evidence",
            target_id=category_name,
            before_summary="",
            after_summary=category_summary[:180],
            reason=reason,
            operator="system",
            source=source,
            confidence=max(0.72, confidence),
            metadata={
                **base_metadata,
                "evidence_category": category_name,
            },
        )
        recent_semantic.append(
            {
                "namespace": "semantic_self_evidence",
                "target_id": category_name,
                "after_summary": category_summary[:180],
            }
        )
        wrote = True
    return wrote


def _record_behavior_consequence(
    store: MemoryStore,
    *,
    current_event: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None,
    reconsolidation_snapshot: dict[str, Any] | None = None,
    source: str,
    confidence: float,
) -> bool:
    behavior_semantics = _reconsolidation_behavior_semantics(reconsolidation_snapshot)
    frozen_behavior_action = _reconsolidation_behavior_action_snapshot(reconsolidation_snapshot)
    semantic_anchor_bundle = _reconsolidation_semantic_anchor_bundle(reconsolidation_snapshot)
    effective_behavior_action = frozen_behavior_action or (
        behavior_action if isinstance(behavior_action, dict) else {}
    )
    counterpart = _reconsolidation_counterpart_snapshot(reconsolidation_snapshot)
    consequence = _behavior_consequence_snapshot(
        reconsolidation_snapshot=reconsolidation_snapshot,
        current_event=current_event,
        behavior_action=effective_behavior_action,
    )
    kind = str(consequence.get("kind") or "").strip()
    summary = str(consequence.get("summary") or "").strip()
    if not kind or not summary:
        return False

    metadata = {
        "consequence_kind": kind,
        "relationship_effect": str(consequence.get("relationship_effect") or "").strip(),
        "self_effect": str(consequence.get("self_effect") or "").strip(),
        "primary_motive": str(
            behavior_semantics.get("primary_motive")
            or effective_behavior_action.get("primary_motive")
            or ""
        ).strip(),
        "motive_tension": str(
            behavior_semantics.get("motive_tension")
            or effective_behavior_action.get("motive_tension")
            or ""
        ).strip(),
        "goal_frame": str(
            behavior_semantics.get("goal_frame")
            or effective_behavior_action.get("goal_frame")
            or ""
        ).strip()[:220],
        "trigger_family": str(consequence.get("trigger_family") or "").strip(),
        "relationship_weather": str(consequence.get("relationship_weather") or "").strip(),
        "carryover_mode": str(consequence.get("carryover_mode") or "").strip(),
        "timing_window_min": int(consequence.get("timing_window_min") or 0),
        "silent": bool(consequence.get("silent")),
        "delayed": bool(consequence.get("delayed")),
        "stale_window": bool(consequence.get("stale_window")),
    }
    if counterpart:
        metadata["counterpart_stance"] = str(counterpart.get("stance") or "").strip()
        metadata["counterpart_scene"] = str(counterpart.get("scene") or "").strip()
        metadata["counterpart_respect_level"] = float(counterpart.get("respect_level") or 0.0)
        metadata["counterpart_reciprocity"] = float(counterpart.get("reciprocity") or 0.0)
        metadata["counterpart_boundary_pressure"] = float(counterpart.get("boundary_pressure") or 0.0)
        metadata["counterpart_reliability_read"] = float(counterpart.get("reliability_read") or 0.0)
    _apply_semantic_anchor_metadata(metadata, semantic_anchor_bundle)
    embodied_context = _normalized_embodied_context(
        consequence.get("embodied_context") or effective_behavior_action.get("embodied_context")
    )
    if embodied_context:
        metadata["embodied_context"] = embodied_context
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

    if _write_semantic_self_evidence_categories(
        store,
        category_summaries=consequence.get("category_summaries"),
        reason=f"behavior_consequence:{kind}",
        source=source,
        confidence=confidence,
        metadata=metadata,
    ):
        wrote = True
    return wrote


def _record_behavior_plan_long_horizon_memory(
    store: MemoryStore,
    *,
    behavior_plan: dict[str, Any] | None,
    reconsolidation_snapshot: dict[str, Any] | None = None,
    source: str,
    confidence: float,
) -> bool:
    frozen_plan = _reconsolidation_behavior_plan_snapshot(reconsolidation_snapshot)
    plan = frozen_plan or (dict(behavior_plan or {}) if isinstance(behavior_plan, dict) else {})
    counterpart = _reconsolidation_counterpart_snapshot(reconsolidation_snapshot)
    kind = str(plan.get("kind") or "").strip().lower()
    if not kind or kind in {
        "none",
        "observe_only",
        "respond_now",
        "speak_now",
        "presence_confirmation",
        "ambient_checkin",
        "low_pressure_support",
    }:
        return False

    target = str(plan.get("target") or "").strip().lower()
    trigger_family = str(plan.get("trigger_family") or "").strip().lower()
    carryover_mode = str(plan.get("carryover_mode") or "").strip().lower()
    note = str(plan.get("note") or "").strip()
    primary_motive = str(plan.get("primary_motive") or "").strip()
    motive_tension = str(plan.get("motive_tension") or "").strip()
    goal_frame = str(plan.get("goal_frame") or "").strip()[:220]
    scheduled_after_min = max(0, int(plan.get("scheduled_after_min") or 0))
    allow_interrupt = bool(plan.get("allow_interrupt", True))
    carryover_strength = _clamp01(plan.get("carryover_strength"), 0.0)
    presence_residue = _clamp01(plan.get("presence_residue"), 0.0)
    ambient_resonance = _clamp01(plan.get("ambient_resonance"), 0.0)
    self_activity_momentum = _clamp01(plan.get("self_activity_momentum"), 0.0)
    continuity_signal = max(
        carryover_strength,
        presence_residue,
        ambient_resonance if kind in {"small_opening", "shared_activity_offer"} else 0.0,
    )
    self_rhythm_signal = max(
        self_activity_momentum,
        carryover_strength if carryover_mode == "own_rhythm" else 0.0,
    )

    worldline_category = ""
    worldline_summary = ""
    relationship_summary = ""
    affinity_delta = 0.0
    trust_delta = 0.0
    importance_base = 0.52
    category_summaries: dict[str, str] = {}

    if kind == "deferred_checkin":
        worldline_category = "continuity_intent"
        worldline_summary = "她会把这次没立刻说出口的靠近留成后续窗口，等更自然的时候再接回来，而不是每次都临场从零开始。"
        relationship_summary = "这段关系里的靠近不需要每次都当场说完；她会把一部分惦记留到之后再自然接回来。"
        affinity_delta = 0.02
        trust_delta = 0.03
        importance_base = 0.58
        category_summaries = {
            "agency_style": "她会把没立刻说出口的靠近留成后续窗口，让下一次回头带着连续性，而不是次次临场起意。",
            "presence_style": "没立刻开口不等于那点在意消失了；她会把它留到更自然的时候再接回来。",
        }
    elif kind == "self_activity_continue":
        worldline_category = "self_rhythm"
        worldline_summary = "当没有必要立刻回头时，她会先把自己的节奏继续走下去，再决定之后是否重新靠近。"
        relationship_summary = "她不会靠一直围着对方来证明关系在场；她会先把自己的节奏继续走下去。"
        affinity_delta = 0.01
        trust_delta = 0.02
        importance_base = 0.56
        category_summaries = {
            "agency_style": "她允许自己先把手头的节奏继续下去，不会因为关系里出现一个窗口就立刻中断自己。",
            "rhythm_style": "对她来说，继续自己的节奏和之后回头并不冲突；两者会落在同一条连续线上。",
        }
    elif kind == "shared_activity_offer":
        worldline_category = "shared_window"
        worldline_summary = "她会把之前留下的共同窗口真正接成一次轻量邀约，让关系里的共同时间带着连续性出现。"
        relationship_summary = "之前留下的共同窗口被她接成了真正的邀约，这让关系不只停在被动回应里。"
        affinity_delta = 0.04
        trust_delta = 0.03
        importance_base = 0.60
        category_summaries = {
            "agency_style": "她会把之前积下来的共同窗口真正接成邀请，而不是等每次互动都从零开始。",
            "presence_style": "她留给对方的是一起做点什么的空当，不是流程化的任务提醒。",
        }
    elif kind == "life_nudge":
        worldline_category = "care_continuity"
        worldline_summary = "她会把生活上的小惦记记到之后，再在合适的时候顺手接回来，让关心带着连续性落地。"
        relationship_summary = "她会把生活上的小惦记留到合适的时候再接回来，这让关心显得持续而具体。"
        affinity_delta = 0.03
        trust_delta = 0.04
        importance_base = 0.59
        category_summaries = {
            "agency_style": "她会把生活上的小惦记留到更合适的节点再接回来，不把关心做成即时打断。",
            "presence_style": "她记住的不是抽象任务，而是对方生活里那些之后还值得回头的小细节。",
        }
    elif kind == "work_nudge":
        worldline_category = "care_continuity"
        worldline_summary = "她会记住对方眼前事情的节点，在合适的时候轻轻拎一下，让关心和判断都带着连续性。"
        relationship_summary = "她会记住对方眼前事情的节点，在合适的时候轻轻拎一下，而不是把提醒做成冰冷通知。"
        affinity_delta = 0.02
        trust_delta = 0.05
        importance_base = 0.59
        category_summaries = {
            "agency_style": "她会在自己认可的时机轻轻把事情拎一下，而不是机械地按到点广播提醒。",
            "presence_style": "她记住的是对方眼前事情的节奏，因此提醒会更像延续过往关注，而不是外部通知。",
        }
    elif kind == "small_opening":
        worldline_category = "continuity_recontact"
        worldline_summary = "她会从自己的节奏里回头留一个轻一点的小开口，让关系保持在场感，但不把靠近一下子做满。"
        relationship_summary = "她会从自己的节奏里回头留一个小开口，让关系保持轻而连续的在场感。"
        affinity_delta = 0.03
        trust_delta = 0.03
        importance_base = 0.55
        category_summaries = {
            "agency_style": "她会回头，但只先留一个小开口，不会把每次靠近一下子做满。",
            "presence_style": "她更愿意先确认那点在场感还在，再决定要不要继续往下展开。",
        }
    else:
        return False

    counterpart_scene = str(counterpart.get("scene") or "").strip().lower()
    if counterpart_scene == "busy_not_disrespectful" and kind in {"deferred_checkin", "self_activity_continue"}:
        relationship_summary = "当对方当下更像忙着别的事时，她不会把沉默直接误判成冷淡；她会先收回自己的节奏，等更自然的时候再接回来。"

    metadata = {
        "plan_kind": kind,
        "plan_target": target,
        "trigger_family": trigger_family,
        "carryover_mode": carryover_mode,
        "scheduled_after_min": scheduled_after_min,
        "allow_interrupt": allow_interrupt,
        "primary_motive": primary_motive,
        "motive_tension": motive_tension,
        "goal_frame": goal_frame,
        "carryover_strength": carryover_strength,
        "presence_residue": presence_residue,
        "ambient_resonance": ambient_resonance,
        "self_activity_momentum": self_activity_momentum,
    }
    embodied_context = _normalized_embodied_context(plan.get("embodied_context"))
    if embodied_context:
        metadata["embodied_context"] = embodied_context
    if counterpart:
        metadata["counterpart_stance"] = str(counterpart.get("stance") or "").strip()
        metadata["counterpart_scene"] = str(counterpart.get("scene") or "").strip()
        metadata["counterpart_respect_level"] = float(counterpart.get("respect_level") or 0.0)
        metadata["counterpart_reciprocity"] = float(counterpart.get("reciprocity") or 0.0)
        metadata["counterpart_boundary_pressure"] = float(counterpart.get("boundary_pressure") or 0.0)
        metadata["counterpart_reliability_read"] = float(counterpart.get("reliability_read") or 0.0)

    recent_plan = [
        item
        for item in store.list_revision_traces(limit=20)
        if str(item.get("namespace") or item.get("content", {}).get("namespace") or "").strip() == "behavior_plan"
    ]
    trace_summary = note or worldline_summary
    wrote = False
    if trace_summary and not _recent_summary_overlap(recent_plan, trace_summary, field="after_summary", threshold=0.90):
        store.add_revision_trace(
            namespace="behavior_plan",
            target_id=kind,
            before_summary="",
            after_summary=trace_summary[:180],
            reason=f"behavior_plan:{kind}",
            operator="system",
            source=source,
            confidence=max(0.72, confidence),
            metadata=metadata,
        )
        wrote = True

    worldline_tags = ["behavior_plan", kind]
    if trigger_family:
        worldline_tags.append(trigger_family)
    if carryover_mode:
        worldline_tags.append(carryover_mode)
    if primary_motive:
        worldline_tags.append(primary_motive)
    worldline_tags = list(dict.fromkeys(tag for tag in worldline_tags if tag))[:12]
    if worldline_summary:
        recent_worldline = store.list_worldline_events(limit=10)
        if not _recent_summary_overlap(recent_worldline, worldline_summary):
            importance = round(
                _clamp01(
                    importance_base
                    + 0.08 * continuity_signal
                    + 0.08 * self_rhythm_signal
                    + (0.04 if scheduled_after_min > 0 else 0.0)
                ),
                3,
            )
            store.add_worldline_event(
                summary=worldline_summary,
                category=worldline_category or "continuity_intent",
                importance=importance,
                tags=worldline_tags,
                confidence=max(0.72, confidence),
            )
            wrote = True

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

    if _write_semantic_self_evidence_categories(
        store,
        category_summaries=category_summaries,
        reason=f"behavior_plan:{kind}",
        source=source,
        confidence=confidence,
        metadata=metadata,
    ):
        wrote = True
    return wrote


def _carryover_source_tag_value(interaction_carryover: dict[str, Any] | None, key: str) -> str:
    carryover = interaction_carryover if isinstance(interaction_carryover, dict) else {}
    prefix = f"{str(key or '').strip().lower()}:"
    tags = carryover.get("source_tags")
    if not isinstance(tags, list) or not prefix:
        return ""
    for item in tags:
        text = str(item or "").strip()
        if text.lower().startswith(prefix):
            return text[len(prefix) :].strip().lower()
    return ""


def _record_retrieved_continuity_reactivation(
    store: MemoryStore,
    *,
    interaction_carryover: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None,
    behavior_plan: dict[str, Any] | None,
    reconsolidation_snapshot: dict[str, Any] | None = None,
    source: str,
    confidence: float,
) -> bool:
    frozen_carryover = _reconsolidation_interaction_carryover_snapshot(reconsolidation_snapshot)
    frozen_plan = _reconsolidation_behavior_plan_snapshot(reconsolidation_snapshot)
    frozen_behavior_semantics = _reconsolidation_behavior_semantics(reconsolidation_snapshot)
    frozen_behavior_action = _reconsolidation_behavior_action_snapshot(reconsolidation_snapshot)
    carryover = frozen_carryover or (interaction_carryover if isinstance(interaction_carryover, dict) else {})
    if str(carryover.get("source") or "").strip().lower() != "retrieved_behavior_plan":
        return False

    carryover_strength = _clamp01(carryover.get("strength"), 0.0)
    carryover_mode = str(carryover.get("carryover_mode") or "").strip().lower()
    if not carryover_mode or carryover_strength < 0.18:
        return False

    action = frozen_behavior_action or (behavior_action if isinstance(behavior_action, dict) else {})
    plan = frozen_plan or (behavior_plan if isinstance(behavior_plan, dict) else {})
    action_target = str(action.get("action_target") or "").strip().lower()
    interaction_mode = str(
        frozen_behavior_semantics.get("interaction_mode")
        or action.get("interaction_mode")
        or ""
    ).strip().lower()
    plan_kind = str(plan.get("kind") or "").strip().lower()
    if not action_target and not plan_kind and not interaction_mode:
        return False

    source_plan_kind = _carryover_source_tag_value(carryover, "plan_kind")
    source_trigger_family = _carryover_source_tag_value(carryover, "trigger_family")
    relationship_weather = str(carryover.get("relationship_weather") or "").strip().lower()
    source_note = str(carryover.get("note") or "").strip()
    primary_motive = str(
        frozen_behavior_semantics.get("primary_motive")
        or action.get("primary_motive")
        or plan.get("primary_motive")
        or ""
    ).strip().lower()
    motive_tension = str(
        frozen_behavior_semantics.get("motive_tension")
        or action.get("motive_tension")
        or plan.get("motive_tension")
        or ""
    ).strip().lower()
    goal_frame = str(
        frozen_behavior_semantics.get("goal_frame")
        or action.get("goal_frame")
        or plan.get("goal_frame")
        or ""
    ).strip()[:220]

    alignment_specs = {
        "self_activity_continue": {
            "plan_kinds": {"self_activity_continue"},
            "action_targets": {"hold_own_rhythm"},
            "interaction_modes": {"self_activity_hold"},
        },
        "small_opening": {
            "plan_kinds": {"small_opening"},
            "action_targets": {"offer_small_opening", "respond_now", "confirm_presence"},
            "interaction_modes": {"self_activity_reopen", "companion_reply", "steady_reply", "brief_presence"},
        },
        "deferred_checkin": {
            "plan_kinds": {"deferred_checkin"},
            "action_targets": {"wait_and_recheck", "respond_now", "confirm_presence"},
            "interaction_modes": {"steady_reply", "companion_reply", "brief_presence"},
        },
        "shared_activity_offer": {
            "plan_kinds": {"shared_activity_offer"},
            "action_targets": {"offer_shared_activity", "respond_now"},
            "interaction_modes": {"shared_activity_offer", "companion_reply", "steady_reply"},
        },
        "life_nudge": {
            "plan_kinds": {"life_nudge", "work_nudge", "deferred_checkin"},
            "action_targets": {"light_life_nudge", "light_work_nudge", "wait_and_recheck", "respond_now"},
            "interaction_modes": {"scheduled_life_nudge", "companion_reply", "steady_reply"},
        },
        "work_nudge": {
            "plan_kinds": {"work_nudge", "deferred_checkin"},
            "action_targets": {"light_work_nudge", "wait_and_recheck", "respond_now"},
            "interaction_modes": {"scheduled_life_nudge", "companion_reply", "steady_reply"},
        },
        "own_rhythm": {
            "plan_kinds": {"self_activity_continue"},
            "action_targets": {"hold_own_rhythm"},
            "interaction_modes": {"self_activity_hold"},
        },
        "shared_window": {
            "plan_kinds": {"shared_activity_offer"},
            "action_targets": {"offer_shared_activity", "respond_now"},
            "interaction_modes": {"shared_activity_offer", "companion_reply", "steady_reply"},
        },
        "life_window": {
            "plan_kinds": {"deferred_checkin", "life_nudge", "work_nudge"},
            "action_targets": {"wait_and_recheck", "light_life_nudge", "light_work_nudge", "respond_now"},
            "interaction_modes": {"scheduled_life_nudge", "companion_reply", "steady_reply", "brief_presence"},
        },
        "quiet_recontact": {
            "plan_kinds": {"deferred_checkin"},
            "action_targets": {"wait_and_recheck", "respond_now", "confirm_presence"},
            "interaction_modes": {"companion_reply", "steady_reply", "brief_presence"},
        },
        "brief_presence": {
            "plan_kinds": {"presence_confirmation", "deferred_checkin"},
            "action_targets": {"confirm_presence", "respond_now"},
            "interaction_modes": {"brief_presence", "companion_reply", "steady_reply"},
        },
        "ambient_echo": {
            "plan_kinds": {"ambient_checkin"},
            "action_targets": {"ambient_checkin", "respond_now"},
            "interaction_modes": {"ambient_checkin", "companion_reply", "steady_reply"},
        },
    }
    alignment_key = source_plan_kind if source_plan_kind in alignment_specs else carryover_mode if carryover_mode in alignment_specs else ""
    if not alignment_key:
        return False
    spec = alignment_specs.get(alignment_key) or {}
    aligned = bool(
        (plan_kind and plan_kind in spec.get("plan_kinds", set()))
        or (action_target and action_target in spec.get("action_targets", set()))
        or (interaction_mode and interaction_mode in spec.get("interaction_modes", set()))
    )
    if not aligned:
        return False

    if alignment_key in {"self_activity_continue", "own_rhythm"}:
        trace_summary = "之前沉下来的自我节奏这次又被重新接上，她仍先顺着自己的步子走，而不是为了回应临时折返。"
        worldline_summary = "先走自己的节奏这条连续性被她重新接上了，这次的动作仍沿着同一条线往前。"
        relationship_summary = "她把先走自己节奏这条连续性又接了回来，这段关系里的在场感不再只靠即时回应维持。"
        worldline_category = "self_rhythm"
        affinity_delta = 0.01
        trust_delta = 0.02
        importance = 0.57
        category_summaries = {
            "agency_style": "她会把先走自己节奏这条连续性重新接上，不会因为旧惦记浮回来就立刻把自己折回去。",
            "rhythm_style": "旧的连续性被重新点亮时，她依旧会先顺着自己的步子走，让关系和自我节奏落在同一条线上。",
        }
    elif alignment_key in {"small_opening"}:
        trace_summary = "之前留下的小开口这次又被重新接上，她顺着那点在场感自然把话接了回来，而不是从零起意。"
        worldline_summary = "她把之前留下的小开口重新接上了，这次的靠近更像连续回头，不像临时起意。"
        relationship_summary = "之前留下的小开口被她顺着接了回来，让这段关系的在场感带着延续性出现。"
        worldline_category = "continuity_reactivation"
        affinity_delta = 0.03
        trust_delta = 0.03
        importance = 0.60
        category_summaries = {
            "agency_style": "她会把之前留过的小开口重新接上，让靠近顺着旧连续性继续下去，而不是每次都从零起手。",
            "presence_style": "那点在场感被重新点亮时，她更像自然把话接回来，而不是做一次突兀的重新开场。",
        }
    elif alignment_key in {"shared_activity_offer", "shared_window"}:
        trace_summary = "之前积下来的共同窗口这次又被重新接上，她把那点一起做点什么的可能真正带回了眼前。"
        worldline_summary = "共同窗口被重新点亮后，她把那条线继续往前接成了真实的共同时间。"
        relationship_summary = "之前积着的共同窗口被她重新接上，这让关系里的共同时间带着连续性出现。"
        worldline_category = "shared_window"
        affinity_delta = 0.04
        trust_delta = 0.03
        importance = 0.62
        category_summaries = {
            "agency_style": "旧的共同窗口一旦重新浮起来，她会把它接成真实邀约，而不是每次都等新的理由从头开始。",
            "presence_style": "她留给对方的是继续共享一段时间的入口，不是一次孤立的互动动作。",
        }
    elif alignment_key in {"life_nudge", "work_nudge", "life_window", "quiet_recontact", "brief_presence", "ambient_echo", "deferred_checkin"}:
        trace_summary = "之前留着的那点惦记这次又被重新接上，她不是临时想起，而是顺着旧连续性重新回头。"
        worldline_summary = "旧的惦记再次浮回注意力时，她顺着那条连续线重新回头，而不是从空白重新起意。"
        relationship_summary = "之前留着的那点惦记被她重新接上，这让关心和在场感显得持续，而不是一次性的临时动作。"
        worldline_category = "continuity_reactivation"
        affinity_delta = 0.02
        trust_delta = 0.03
        importance = 0.59
        category_summaries = {
            "agency_style": "旧的惦记一旦重新浮回来，她会顺着那条连续线继续判断，而不是把每次回头都做成断开的新动作。",
            "presence_style": "她的关心会沿着先前留下的连续性重新亮起，所以这次回头更像延续，而不是突兀插入。",
        }
    else:
        return False

    metadata = {
        "carryover_mode": carryover_mode,
        "carryover_strength": round(carryover_strength, 3),
        "relationship_weather": relationship_weather,
        "source_plan_kind": source_plan_kind,
        "source_trigger_family": source_trigger_family,
        "current_plan_kind": plan_kind,
        "current_action_target": action_target,
        "current_interaction_mode": interaction_mode,
        "primary_motive": primary_motive,
        "motive_tension": motive_tension,
        "goal_frame": goal_frame,
        "source_note": source_note,
        "source_tags": list(carryover.get("source_tags") or [])[:12] if isinstance(carryover.get("source_tags"), list) else [],
    }
    embodied_context = _normalized_embodied_context(carryover.get("embodied_context"))
    if embodied_context:
        metadata["embodied_context"] = embodied_context
    target_id = source_plan_kind or carryover_mode or action_target or plan_kind or "reactivation"
    reason = "retrieved_continuity_reactivation"
    wrote = False

    recent_reactivation = [
        item
        for item in store.list_revision_traces(limit=20)
        if str(item.get("namespace") or item.get("content", {}).get("namespace") or "").strip() == "behavior_reactivation"
    ]
    if not _recent_summary_overlap(recent_reactivation, trace_summary, field="after_summary", threshold=0.90):
        store.add_revision_trace(
            namespace="behavior_reactivation",
            target_id=target_id,
            before_summary="",
            after_summary=trace_summary[:180],
            reason=reason,
            operator="system",
            source=source,
            confidence=max(0.72, confidence),
            metadata=metadata,
        )
        wrote = True

    recent_worldline = [
        item
        for item in store.list_worldline_events(limit=10)
        if "retrieved_reactivation"
        in (
            (item.get("tags") if isinstance(item.get("tags"), list) else [])
            or ((item.get("content") or {}).get("tags") if isinstance(item.get("content"), dict) else [])
        )
    ]
    if not _recent_summary_overlap(recent_worldline, worldline_summary):
        tags = [
            "retrieved_reactivation",
            "retrieved_behavior_plan",
            carryover_mode,
            source_plan_kind,
            source_trigger_family,
            action_target,
            plan_kind,
        ]
        if relationship_weather:
            tags.append(relationship_weather)
        store.add_worldline_event(
            summary=worldline_summary,
            category=worldline_category,
            importance=round(_clamp01(importance + 0.10 * carryover_strength), 3),
            tags=list(dict.fromkeys(tag for tag in tags if tag))[:12],
            confidence=max(0.72, confidence),
        )
        wrote = True

    recent_relationship = store.list_relationship_timeline(limit=10)
    if not _recent_summary_overlap(recent_relationship, relationship_summary):
        store.add_relationship_timeline(
            summary=relationship_summary,
            affinity_delta=round(affinity_delta, 3),
            trust_delta=round(trust_delta, 3),
            confidence=max(0.70, confidence),
        )
        wrote = True

    if _write_semantic_self_evidence_categories(
        store,
        category_summaries=category_summaries,
        reason=reason,
        source=source,
        confidence=confidence,
        metadata=metadata,
    ):
        wrote = True
    return wrote


def _record_digital_body_consequence(
    store: MemoryStore,
    *,
    digital_body_state: dict[str, Any] | None,
    reconsolidation_snapshot: dict[str, Any] | None = None,
    source: str,
    confidence: float,
) -> bool:
    consequence = _reconsolidation_digital_body_consequence_snapshot(reconsolidation_snapshot) or derive_digital_body_consequence(
        digital_body_state=digital_body_state,
    )
    kind = str(consequence.get("kind") or "").strip().lower()
    summary = str(consequence.get("summary") or "").strip()
    if not kind or not summary:
        return False

    missing_access = [
        str(item).strip().lower()
        for item in (consequence.get("missing_access") if isinstance(consequence.get("missing_access"), list) else [])
        if str(item or "").strip()
    ][:12]
    requested_access = [
        str(item).strip().lower()
        for item in (consequence.get("requested_access") if isinstance(consequence.get("requested_access"), list) else [])
        if str(item or "").strip()
    ][:12]
    granted_toolsets = [
        str(item).strip().lower()
        for item in (consequence.get("granted_toolsets") if isinstance(consequence.get("granted_toolsets"), list) else [])
        if str(item or "").strip()
    ][:12]
    active_tools = [
        str(item).strip().lower()
        for item in (consequence.get("active_tools") if isinstance(consequence.get("active_tools"), list) else [])
        if str(item or "").strip()
    ][:8]

    metadata = {
        "body_consequence_kind": kind,
        "access_mode": str(consequence.get("access_mode") or "").strip().lower(),
        "active_surface": str(consequence.get("active_surface") or "").strip().lower(),
        "world_surfaces": [
            str(item).strip().lower()
            for item in (consequence.get("world_surfaces") if isinstance(consequence.get("world_surfaces"), list) else [])
            if str(item or "").strip()
        ][:12],
        "missing_access": missing_access,
        "requested_access": requested_access,
        "granted_toolsets": granted_toolsets,
        "active_tools": active_tools,
        "block_reason": str(consequence.get("block_reason") or "").strip()[:220],
        "artifact_carrier": str(consequence.get("artifact_carrier") or "").strip().lower(),
        "artifact_source_ref_ids": [
            int(value)
            for value in (consequence.get("artifact_source_ref_ids") if isinstance(consequence.get("artifact_source_ref_ids"), list) else [])
            if int(value or 0) > 0
        ][:8],
        "artifact_source_url": str(consequence.get("artifact_source_url") or "").strip()[:320],
        "artifact_source_query": str(consequence.get("artifact_source_query") or "").strip()[:220],
        "artifact_source_title": str(consequence.get("artifact_source_title") or "").strip()[:160],
        "artifact_source_tool_name": str(consequence.get("artifact_source_tool_name") or "").strip().lower()[:80],
        "browser_session": str(consequence.get("browser_session") or "").strip().lower(),
        "account_state": str(consequence.get("account_state") or "").strip().lower(),
        "cookie_state": str(consequence.get("cookie_state") or "").strip().lower(),
        "filesystem_state": str(consequence.get("filesystem_state") or "").strip().lower(),
        "sandbox_mode": str(consequence.get("sandbox_mode") or "").strip().lower(),
        "network_access": str(consequence.get("network_access") or "").strip().lower(),
        "pending_approval_count": max(0, int(consequence.get("pending_approval_count") or 0)),
        "blocked_packet_count": max(0, int(consequence.get("blocked_packet_count") or 0)),
        "completed_packet_count": max(0, int(consequence.get("completed_packet_count") or 0)),
        "external_tool_count": max(0, int(consequence.get("external_tool_count") or 0)),
        "primary_proposal_id": str(consequence.get("primary_proposal_id") or "").strip(),
        "primary_status": str(consequence.get("primary_status") or "").strip().lower(),
        "primary_origin": str(consequence.get("primary_origin") or "").strip().lower(),
        "primary_intent": str(consequence.get("primary_intent") or "").strip().lower(),
        "primary_tool_name": str(consequence.get("primary_tool_name") or "").strip().lower(),
        "procedural_growth": bool(consequence.get("procedural_growth", False)),
        "environmental_friction": bool(consequence.get("environmental_friction", False)),
        "requested_help": bool(consequence.get("requested_help", False)),
    }

    recent = [
        item
        for item in store.list_revision_traces(limit=20)
        if str(item.get("namespace") or item.get("content", {}).get("namespace") or "").strip() == "digital_body_consequence"
    ]
    wrote = False
    if not _recent_summary_overlap(recent, summary, field="after_summary", threshold=0.90):
        store.add_revision_trace(
            namespace="digital_body_consequence",
            target_id=kind,
            before_summary="",
            after_summary=summary[:180],
            reason=f"digital_body_consequence:{kind}",
            operator="system",
            source=source,
            confidence=max(0.72, confidence),
            metadata=metadata,
        )
        wrote = True

    if _write_semantic_self_evidence_categories(
        store,
        category_summaries=consequence.get("category_summaries"),
        reason=f"digital_body_consequence:{kind}",
        source=source,
        confidence=confidence,
        metadata=metadata,
    ):
        wrote = True

    if _record_digital_body_consequence_long_horizon_memory(
        store,
        consequence=consequence,
        confidence=confidence,
    ):
        wrote = True
    return wrote


def _record_behavior_trace_writeback(
    store: MemoryStore,
    *,
    current_event: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None,
    behavior_plan: dict[str, Any] | None,
    interaction_carryover: dict[str, Any] | None,
    agenda_lifecycle_residue: dict[str, Any] | None,
    digital_body_state: dict[str, Any] | None = None,
    reconsolidation_snapshot: dict[str, Any] | None = None,
    source: str,
    confidence: float,
) -> bool:
    event_snapshot = dict(current_event or {}) if isinstance(current_event, dict) else {}
    action_snapshot = dict(behavior_action or {}) if isinstance(behavior_action, dict) else {}
    plan_snapshot = dict(behavior_plan or {}) if isinstance(behavior_plan, dict) else {}
    carryover_snapshot = dict(interaction_carryover or {}) if isinstance(interaction_carryover, dict) else {}
    lifecycle_snapshot = dict(agenda_lifecycle_residue or {}) if isinstance(agenda_lifecycle_residue, dict) else {}
    body_snapshot = dict(digital_body_state or {}) if isinstance(digital_body_state, dict) else {}
    wrote = False

    consequence_written = _record_behavior_consequence(
        store,
        current_event=event_snapshot,
        behavior_action=action_snapshot,
        reconsolidation_snapshot=reconsolidation_snapshot,
        source=source,
        confidence=confidence,
    )
    if consequence_written:
        wrote = True

    behavior_plan_written = _record_behavior_plan_long_horizon_memory(
        store,
        behavior_plan=plan_snapshot,
        reconsolidation_snapshot=reconsolidation_snapshot,
        source=source,
        confidence=confidence,
    )
    if behavior_plan_written:
        wrote = True

    reactivation_written = _record_retrieved_continuity_reactivation(
        store,
        interaction_carryover=carryover_snapshot,
        behavior_action=action_snapshot,
        behavior_plan=plan_snapshot,
        reconsolidation_snapshot=reconsolidation_snapshot,
        source=source,
        confidence=confidence,
    )
    if reactivation_written:
        wrote = True

    lifecycle_written = _record_agenda_lifecycle_consequence(
        store,
        agenda_lifecycle_residue=lifecycle_snapshot,
        reconsolidation_snapshot=reconsolidation_snapshot,
        source=source,
        confidence=confidence,
    )
    if lifecycle_written:
        wrote = True

    digital_body_written = _record_digital_body_consequence(
        store,
        digital_body_state=body_snapshot,
        reconsolidation_snapshot=reconsolidation_snapshot,
        source=source,
        confidence=confidence,
    )
    if digital_body_written:
        wrote = True

    counterpart_written = _record_counterpart_assessment_long_horizon_memory(
        store,
        current_event=event_snapshot,
        behavior_action=action_snapshot,
        reconsolidation_snapshot=reconsolidation_snapshot,
        source=source,
        confidence=confidence,
    )
    if counterpart_written:
        wrote = True

    return wrote


def _record_passive_text_relational_memory(
    store: MemoryStore,
    *,
    summary: str,
    confidence: float,
    hurt: float,
    irritation: float,
    repair_confidence: float,
    interaction_frame: str,
    has_text: bool,
    unresolved_like: bool,
    resolution_like: bool,
    repair_like: bool,
    partial_repair_like: bool,
    shared_future_commitment: bool,
    familiar_continuity_like: bool,
    positive_companion_like: bool,
) -> bool:
    wrote = False

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
        strong_resolution_markers = {"说开了", "真的说开了", "已经说开了", "和好了", "不生气了", "原谅你了", "原谅了", "没事了", "过去了", "翻篇了"}
        can_resolve_tension = resolution_like or any(marker in summary for marker in strong_resolution_markers)
        resolved = (
            _resolve_matching_tensions_from_summary(store, summary=summary, source="auto:passive_evolution")
            if can_resolve_tension
            else []
        )
        repair_items = store.list_conflict_repairs(limit=8)
        if not _recent_summary_overlap(repair_items, summary):
            store.add_conflict_repair(summary=summary, confidence=max(0.72, confidence))
            wrote = True
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

    if has_text and shared_future_commitment and interaction_frame in {"structured", "relationship", "companion", "natural"}:
        commitment_items = store.list_commitments(limit=8)
        if not _recent_summary_overlap(commitment_items, summary, field="text", threshold=0.68):
            store.add_commitment(text=summary, confidence=max(0.74, confidence))
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

    return wrote


def _record_agenda_lifecycle_consequence(
    store: MemoryStore,
    *,
    agenda_lifecycle_residue: dict[str, Any] | None,
    reconsolidation_snapshot: dict[str, Any] | None = None,
    source: str,
    confidence: float,
) -> bool:
    consequence = _reconsolidation_agenda_lifecycle_snapshot(reconsolidation_snapshot) or derive_agenda_lifecycle_consequence(
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
        "continuity_anchor": float(consequence.get("continuity_anchor") or 0.0),
        "own_rhythm_anchor": float(consequence.get("own_rhythm_anchor") or 0.0),
        "recontact_anchor": float(consequence.get("recontact_anchor") or 0.0),
        "boundary_anchor": float(consequence.get("boundary_anchor") or 0.0),
        "memory_anchor": float(consequence.get("memory_anchor") or 0.0),
        "semantic_continuity_depth": float(consequence.get("semantic_continuity_depth") or 0.0),
        "semantic_identity_gravity": float(consequence.get("semantic_identity_gravity") or 0.0),
        "long_term_axis_count": int(consequence.get("long_term_axis_count") or 0),
        "lineage_gravity": float(consequence.get("lineage_gravity") or 0.0),
        "contact_lineage": float(consequence.get("contact_lineage") or 0.0),
        "repair_lineage": float(consequence.get("repair_lineage") or 0.0),
        "boundary_lineage": float(consequence.get("boundary_lineage") or 0.0),
        "selfhood_lineage": float(consequence.get("selfhood_lineage") or 0.0),
        "agency_lineage": float(consequence.get("agency_lineage") or 0.0),
        "counterpart_scene_bias": str(consequence.get("counterpart_scene_bias") or "").strip(),
        "counterpart_boundary_delta": float(consequence.get("counterpart_boundary_delta") or 0.0),
        "primary_motive": str(consequence.get("primary_motive") or "").strip(),
        "motive_tension": str(consequence.get("motive_tension") or "").strip(),
        "goal_frame": str(consequence.get("goal_frame") or "").strip()[:220],
    }
    embodied_context = _normalized_embodied_context(consequence.get("embodied_context"))
    if embodied_context:
        metadata["embodied_context"] = embodied_context
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

    if _write_semantic_self_evidence_categories(
        store,
        category_summaries=consequence.get("category_summaries"),
        reason=f"agenda_lifecycle:{kind}",
        source=source,
        confidence=confidence,
        metadata=metadata,
    ):
        wrote = True
    if _record_agenda_lifecycle_long_horizon_memory(
        store,
        consequence=consequence,
        digital_body_consequence=_reconsolidation_digital_body_consequence_snapshot(reconsolidation_snapshot),
        confidence=confidence,
    ):
        wrote = True
    return wrote


def _record_digital_body_consequence_long_horizon_memory(
    store: MemoryStore,
    *,
    consequence: dict[str, Any] | None,
    confidence: float,
) -> bool:
    item = dict(consequence or {})
    kind = str(item.get("kind") or "").strip().lower()
    if not kind:
        return False

    requested_access = [
        str(value).strip().lower()
        for value in (item.get("requested_access") if isinstance(item.get("requested_access"), list) else [])
        if str(value or "").strip()
    ][:12]
    missing_access = [
        str(value).strip().lower()
        for value in (item.get("missing_access") if isinstance(item.get("missing_access"), list) else [])
        if str(value or "").strip()
    ][:12]
    granted_toolsets = [
        str(value).strip().lower()
        for value in (item.get("granted_toolsets") if isinstance(item.get("granted_toolsets"), list) else [])
        if str(value or "").strip()
    ][:12]
    active_tools = [
        str(value).strip().lower()
        for value in (item.get("active_tools") if isinstance(item.get("active_tools"), list) else [])
        if str(value or "").strip()
    ][:8]
    block_reason = str(item.get("block_reason") or "").strip()
    access_mode = str(item.get("access_mode") or "").strip().lower()
    procedural_growth = bool(item.get("procedural_growth", False))
    requested_help = bool(item.get("requested_help", False))
    environmental_friction = bool(item.get("environmental_friction", False))
    external_tool_count = max(0, int(item.get("external_tool_count") or 0))
    artifact_continuity = str(item.get("artifact_continuity") or "").strip().lower()
    active_artifact_kind = str(item.get("active_artifact_kind") or "").strip().lower()
    active_artifact_label = str(item.get("active_artifact_label") or item.get("active_artifact_ref") or "").strip()
    artifact_reacquisition_mode = str(item.get("artifact_reacquisition_mode") or "").strip().lower()

    worldline_category = ""
    worldline_summary = ""
    worldline_tags = ["digital_body", kind]
    importance = 0.0

    if procedural_growth:
        worldline_category = "embodied_growth"
        capability_phrase = "、".join((granted_toolsets or active_tools)[:3]) if (granted_toolsets or active_tools) else "新的环境入口"
        worldline_summary = f"她把{capability_phrase}这类入口真正接进了自己的数字身体里，之后处理类似事情时会更顺手。"
        importance = _clamp01(0.58 + 0.06 * min(3, len(granted_toolsets) + len(active_tools)) + 0.04 * min(2, external_tool_count))
        worldline_tags.extend(granted_toolsets[:3])
        worldline_tags.extend(active_tools[:2])
    elif requested_help or access_mode == "approval_pending":
        worldline_category = "access_request"
        access_phrase = "、".join((requested_access or missing_access)[:3]) if (requested_access or missing_access) else "额外入口"
        worldline_summary = f"她把这次还缺的{access_phrase}记成了待申请条件，没有把没做到的部分冒充成已经完成。"
        importance = _clamp01(0.52 + 0.06 * min(3, len(requested_access) + len(missing_access)))
        worldline_tags.extend(requested_access[:3])
        worldline_tags.append("approval_gate")
    elif environmental_friction:
        worldline_category = "environmental_friction"
        friction_phrase = "、".join(missing_access[:3]) if missing_access else "环境条件"
        if artifact_continuity in {"missing", "detached"}:
            artifact_phrase = active_artifact_label or active_artifact_kind or "前面的工作面"
            continuity_phrase = "脱开了" if artifact_continuity == "detached" else "断了"
            worldline_summary = (
                f"这次真正卡住她的，是和{artifact_phrase}的连续性已经{continuity_phrase}，"
                "不是一句话就能把事情接回去。"
            )
            importance = _clamp01(0.52 + (0.06 if artifact_reacquisition_mode else 0.0))
            if active_artifact_kind:
                worldline_tags.append(active_artifact_kind)
            if artifact_reacquisition_mode:
                worldline_tags.append(artifact_reacquisition_mode)
        elif block_reason:
            worldline_summary = f"这次真正卡住她的是数字身体里的环境摩擦：{block_reason[:120]}。"
        else:
            worldline_summary = f"这次她确认了数字身体里还缺着{friction_phrase}这类条件，事情没法只靠意愿硬推过去。"
        if not importance:
            importance = _clamp01(0.50 + 0.06 * min(3, len(missing_access)) + (0.08 if block_reason else 0.0))
        worldline_tags.extend(missing_access[:3])
    else:
        return False

    worldline_tags = list(dict.fromkeys(tag for tag in worldline_tags if tag))[:12]
    recent_worldline = store.list_worldline_events(limit=10)
    if _recent_summary_overlap(recent_worldline, worldline_summary):
        return False

    store.add_worldline_event(
        summary=worldline_summary,
        category=worldline_category,
        importance=round(importance, 3),
        tags=worldline_tags,
        confidence=max(0.72, confidence),
    )
    return True


def _record_counterpart_assessment_long_horizon_memory(
    store: MemoryStore,
    *,
    current_event: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None,
    reconsolidation_snapshot: dict[str, Any] | None,
    source: str,
    confidence: float,
) -> bool:
    assessment = _reconsolidation_counterpart_snapshot(reconsolidation_snapshot)
    if not _counterpart_assessment_has_signal(assessment):
        return False

    summary = _counterpart_assessment_summary(assessment, counterpart_name=CANON_COUNTERPART_NAME).strip()
    if not summary:
        return False

    recent = store.list_counterpart_assessment_history(limit=12)
    latest = _normalized_counterpart_assessment_record(recent[0]) if recent else {}
    shift_score = _counterpart_assessment_shift_score(assessment, latest)
    if latest:
        latest_summary = str(latest.get("summary") or "").strip()
        same_stance = str(assessment.get("stance") or "").strip().lower() == str(latest.get("stance") or "").strip().lower()
        same_scene = str(assessment.get("scene") or "").strip().lower() == str(latest.get("scene") or "").strip().lower()
        summary_overlap = _query_overlap_score(summary, latest_summary)
        if same_stance and same_scene and shift_score < 0.12 and summary_overlap >= 0.66:
            return False
        if shift_score < 0.10 and _recent_summary_overlap(recent, summary, threshold=0.90):
            return False

    frozen_behavior_semantics = _reconsolidation_behavior_semantics(reconsolidation_snapshot)
    frozen_behavior_action = _reconsolidation_behavior_action_snapshot(reconsolidation_snapshot)
    effective_behavior_action = frozen_behavior_action or (
        behavior_action if isinstance(behavior_action, dict) else {}
    )
    if frozen_behavior_semantics:
        primary_motive = str(frozen_behavior_semantics.get("primary_motive") or "").strip().lower()
        motive_tension = str(frozen_behavior_semantics.get("motive_tension") or "").strip().lower()
        goal_frame = str(frozen_behavior_semantics.get("goal_frame") or "").strip()
    else:
        primary_motive, motive_tension, goal_frame = _behavior_motive_snapshot(
            behavior_action=effective_behavior_action,
            current_event=current_event,
            allow_event_behavior_fallback=False,
        )
    recon = reconsolidation_snapshot if isinstance(reconsolidation_snapshot, dict) else {}
    event = current_event if isinstance(current_event, dict) else {}
    event_kind = str(recon.get("event_kind") or event.get("kind") or "").strip().lower()
    interaction_frame = str(recon.get("interaction_frame") or "").strip().lower()
    embodied_context = _counterpart_assessment_embodied_context(
        current_event=current_event,
        reconsolidation_snapshot=reconsolidation_snapshot,
        assessment=assessment,
    )

    store.add_counterpart_assessment_history(
        summary=summary,
        stance=str(assessment.get("stance") or "").strip().lower(),
        scene=str(assessment.get("scene") or "").strip().lower(),
        respect_level=float(assessment.get("respect_level") or 0.5),
        reciprocity=float(assessment.get("reciprocity") or 0.5),
        boundary_pressure=float(assessment.get("boundary_pressure") or 0.1),
        reliability_read=float(assessment.get("reliability_read") or 0.5),
        event_kind=event_kind,
        interaction_frame=interaction_frame,
        primary_motive=primary_motive,
        motive_tension=motive_tension,
        goal_frame=goal_frame[:220],
        assessment_profile=assessment.get("assessment_profile") if isinstance(assessment.get("assessment_profile"), dict) else None,
        embodied_context=embodied_context,
        confidence=max(0.72, confidence),
    )
    return True


def _record_agenda_lifecycle_long_horizon_memory(
    store: MemoryStore,
    *,
    consequence: dict[str, Any] | None,
    digital_body_consequence: dict[str, Any] | None = None,
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
    continuity_anchor = _clamp01(item.get("continuity_anchor"), 0.0)
    own_rhythm_anchor = _clamp01(item.get("own_rhythm_anchor"), 0.0)
    recontact_anchor = _clamp01(item.get("recontact_anchor"), 0.0)
    boundary_anchor = _clamp01(item.get("boundary_anchor"), 0.0)
    memory_anchor = _clamp01(item.get("memory_anchor"), 0.0)
    semantic_continuity_depth = _clamp01(item.get("semantic_continuity_depth"), 0.0)
    semantic_identity_gravity = _clamp01(item.get("semantic_identity_gravity"), 0.0)
    long_term_axis_count = max(0, int(item.get("long_term_axis_count") or 0))
    lineage_gravity = _clamp01(item.get("lineage_gravity"), 0.0)
    contact_lineage = _clamp01(item.get("contact_lineage"), 0.0)
    repair_lineage = _clamp01(item.get("repair_lineage"), 0.0)
    boundary_lineage = _clamp01(item.get("boundary_lineage"), 0.0)
    selfhood_lineage = _clamp01(item.get("selfhood_lineage"), 0.0)
    agency_lineage = _clamp01(item.get("agency_lineage"), 0.0)
    try:
        counterpart_boundary_delta = max(-1.0, min(1.0, float(item.get("counterpart_boundary_delta") or 0.0)))
    except Exception:
        counterpart_boundary_delta = 0.0
    own_rhythm_signal = max(
        own_rhythm_bias,
        self_activity_momentum,
        own_rhythm_anchor,
        0.82 * agency_lineage,
        0.72 * lineage_gravity,
        carryover_strength if carryover_mode in {"own_rhythm", "small_opening"} else 0.0,
    )
    continuity_signal = max(
        carryover_strength,
        continuity_anchor,
        recontact_anchor,
        memory_anchor,
        0.78 * contact_lineage,
        0.72 * repair_lineage,
        0.68 * lineage_gravity,
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
            or continuity_signal >= 0.34
        )
    )
    if not own_rhythm_memory and not continuity_memory and not busy_not_disrespectful:
        return False

    wrote = False
    trace_family = ""
    if own_rhythm_memory and busy_not_disrespectful:
        trace_family = "own_rhythm_busy_window"
    elif own_rhythm_memory:
        trace_family = "own_rhythm"
    elif continuity_memory:
        trace_family = "continuity_recontact"
    elif busy_not_disrespectful:
        trace_family = "busy_window_read"

    normalized_current = {
        "summary": str(item.get("summary") or "").strip(),
        "kind": kind,
        "trace_family": trace_family,
        "trigger_family": trigger_family,
        "carryover_mode": carryover_mode,
        "hold_count": hold_count,
        "carryover_strength": carryover_strength,
        "recontact_cooldown": _clamp01(item.get("recontact_cooldown"), 0.0),
        "presence_residue": _clamp01(item.get("presence_residue"), 0.0),
        "ambient_resonance": _clamp01(item.get("ambient_resonance"), 0.0),
        "self_activity_momentum": self_activity_momentum,
        "own_rhythm_bias": own_rhythm_bias,
        "continuity_anchor": continuity_anchor,
        "own_rhythm_anchor": own_rhythm_anchor,
        "recontact_anchor": recontact_anchor,
        "boundary_anchor": boundary_anchor,
        "memory_anchor": memory_anchor,
        "semantic_continuity_depth": semantic_continuity_depth,
        "semantic_identity_gravity": semantic_identity_gravity,
        "long_term_axis_count": long_term_axis_count,
        "lineage_gravity": lineage_gravity,
        "contact_lineage": contact_lineage,
        "repair_lineage": repair_lineage,
        "boundary_lineage": boundary_lineage,
        "selfhood_lineage": selfhood_lineage,
        "agency_lineage": agency_lineage,
        "counterpart_boundary_delta": counterpart_boundary_delta,
    }
    recent_history = store.list_proactive_continuity_history(limit=12)
    latest_history = _normalized_proactive_continuity_record(recent_history[0]) if recent_history else {}
    history_shift = _proactive_continuity_shift_score(normalized_current, latest_history)
    if latest_history:
        same_kind = normalized_current["kind"] == str(latest_history.get("kind") or "").strip().lower()
        same_family = normalized_current["trace_family"] == str(latest_history.get("trace_family") or "").strip().lower()
        same_trigger = normalized_current["trigger_family"] == str(latest_history.get("trigger_family") or "").strip().lower()
        same_carry = normalized_current["carryover_mode"] == str(latest_history.get("carryover_mode") or "").strip().lower()
        history_overlap = _query_overlap_score(
            normalized_current["summary"],
            str(latest_history.get("summary") or "").strip(),
        )
        if same_kind and same_family and same_trigger and same_carry and history_shift < 0.12 and history_overlap >= 0.66:
            normalized_current = {}
        elif history_shift < 0.10 and _recent_summary_overlap(recent_history, normalized_current["summary"], threshold=0.90):
            normalized_current = {}

    if normalized_current:
        embodied_context = _proactive_continuity_embodied_context(digital_body_consequence)
        store.add_proactive_continuity_history(
            summary=normalized_current["summary"],
            kind=kind,
            trace_family=trace_family,
            source_event_kind=str(item.get("source_event_kind") or "").strip().lower(),
            trigger_family=trigger_family,
            carryover_mode=carryover_mode,
            relationship_weather=str(item.get("relationship_weather") or "").strip().lower(),
            counterpart_scene_bias=counterpart_scene_bias,
            hold_count=hold_count,
            carryover_strength=carryover_strength,
            recontact_cooldown=normalized_current["recontact_cooldown"],
            presence_residue=normalized_current["presence_residue"],
            ambient_resonance=normalized_current["ambient_resonance"],
            self_activity_momentum=self_activity_momentum,
            own_rhythm_bias=own_rhythm_bias,
            continuity_anchor=continuity_anchor,
            own_rhythm_anchor=own_rhythm_anchor,
            recontact_anchor=recontact_anchor,
            boundary_anchor=boundary_anchor,
            memory_anchor=memory_anchor,
            semantic_continuity_depth=semantic_continuity_depth,
            semantic_identity_gravity=semantic_identity_gravity,
            long_term_axis_count=long_term_axis_count,
            lineage_gravity=lineage_gravity,
            contact_lineage=contact_lineage,
            repair_lineage=repair_lineage,
            boundary_lineage=boundary_lineage,
            selfhood_lineage=selfhood_lineage,
            agency_lineage=agency_lineage,
            counterpart_boundary_delta=counterpart_boundary_delta,
            primary_motive=str(item.get("primary_motive") or "").strip().lower(),
            motive_tension=str(item.get("motive_tension") or "").strip().lower(),
            goal_frame=str(item.get("goal_frame") or "").strip()[:220],
            embodied_context=embodied_context,
            confidence=max(0.72, confidence),
        )
        wrote = True

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
                    + 0.08 * continuity_signal
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


def _normalized_proactive_continuity_record(item: dict[str, Any] | None) -> dict[str, Any]:
    row = item if isinstance(item, dict) else {}
    content = row.get("content") if isinstance(row.get("content"), dict) else {}

    def _pick(key: str, default: Any = "") -> Any:
        if key in content:
            return content.get(key)
        return row.get(key, default)

    summary = str(_pick("summary") or "").strip()
    if not summary:
        return {}
    normalized = {
        "summary": summary,
        "kind": str(_pick("kind") or "").strip().lower(),
        "trace_family": str(_pick("trace_family") or "").strip().lower(),
        "trigger_family": str(_pick("trigger_family") or "").strip().lower(),
        "carryover_mode": str(_pick("carryover_mode") or "").strip().lower(),
        "hold_count": max(0, _int_like(_pick("hold_count"), 0)),
        "carryover_strength": _clamp01(_pick("carryover_strength"), 0.0),
        "recontact_cooldown": _clamp01(_pick("recontact_cooldown"), 0.0),
        "presence_residue": _clamp01(_pick("presence_residue"), 0.0),
        "ambient_resonance": _clamp01(_pick("ambient_resonance"), 0.0),
        "self_activity_momentum": _clamp01(_pick("self_activity_momentum"), 0.0),
        "own_rhythm_bias": _clamp01(_pick("own_rhythm_bias"), 0.0),
        "continuity_anchor": _clamp01(_pick("continuity_anchor"), 0.0),
        "own_rhythm_anchor": _clamp01(_pick("own_rhythm_anchor"), 0.0),
        "recontact_anchor": _clamp01(_pick("recontact_anchor"), 0.0),
        "boundary_anchor": _clamp01(_pick("boundary_anchor"), 0.0),
        "memory_anchor": _clamp01(_pick("memory_anchor"), 0.0),
        "semantic_continuity_depth": _clamp01(_pick("semantic_continuity_depth"), 0.0),
        "semantic_identity_gravity": _clamp01(_pick("semantic_identity_gravity"), 0.0),
        "long_term_axis_count": max(0, _int_like(_pick("long_term_axis_count"), 0)),
        "lineage_gravity": _clamp01(_pick("lineage_gravity"), 0.0),
        "contact_lineage": _clamp01(_pick("contact_lineage"), 0.0),
        "repair_lineage": _clamp01(_pick("repair_lineage"), 0.0),
        "boundary_lineage": _clamp01(_pick("boundary_lineage"), 0.0),
        "selfhood_lineage": _clamp01(_pick("selfhood_lineage"), 0.0),
        "agency_lineage": _clamp01(_pick("agency_lineage"), 0.0),
        "counterpart_boundary_delta": max(-1.0, min(1.0, float(_pick("counterpart_boundary_delta", 0.0) or 0.0))),
    }
    embodied_context = _normalized_embodied_context(_pick("embodied_context", {}))
    if embodied_context:
        normalized["embodied_context"] = embodied_context
    return normalized


def _proactive_continuity_shift_score(current: dict[str, Any], previous: dict[str, Any]) -> float:
    if not current or not previous:
        return 1.0
    numeric_diffs = [
        abs(float(current.get("carryover_strength") or 0.0) - float(previous.get("carryover_strength") or 0.0)),
        abs(float(current.get("recontact_cooldown") or 0.0) - float(previous.get("recontact_cooldown") or 0.0)),
        abs(float(current.get("presence_residue") or 0.0) - float(previous.get("presence_residue") or 0.0)),
        abs(float(current.get("ambient_resonance") or 0.0) - float(previous.get("ambient_resonance") or 0.0)),
        abs(float(current.get("self_activity_momentum") or 0.0) - float(previous.get("self_activity_momentum") or 0.0)),
        abs(float(current.get("own_rhythm_bias") or 0.0) - float(previous.get("own_rhythm_bias") or 0.0)),
        abs(float(current.get("continuity_anchor") or 0.0) - float(previous.get("continuity_anchor") or 0.0)),
        abs(float(current.get("own_rhythm_anchor") or 0.0) - float(previous.get("own_rhythm_anchor") or 0.0)),
        abs(float(current.get("recontact_anchor") or 0.0) - float(previous.get("recontact_anchor") or 0.0)),
        abs(float(current.get("boundary_anchor") or 0.0) - float(previous.get("boundary_anchor") or 0.0)),
        abs(float(current.get("memory_anchor") or 0.0) - float(previous.get("memory_anchor") or 0.0)),
        abs(float(current.get("semantic_continuity_depth") or 0.0) - float(previous.get("semantic_continuity_depth") or 0.0)),
        abs(float(current.get("semantic_identity_gravity") or 0.0) - float(previous.get("semantic_identity_gravity") or 0.0)),
        abs(float(current.get("lineage_gravity") or 0.0) - float(previous.get("lineage_gravity") or 0.0)),
        abs(float(current.get("contact_lineage") or 0.0) - float(previous.get("contact_lineage") or 0.0)),
        abs(float(current.get("repair_lineage") or 0.0) - float(previous.get("repair_lineage") or 0.0)),
        abs(float(current.get("boundary_lineage") or 0.0) - float(previous.get("boundary_lineage") or 0.0)),
        abs(float(current.get("selfhood_lineage") or 0.0) - float(previous.get("selfhood_lineage") or 0.0)),
        abs(float(current.get("agency_lineage") or 0.0) - float(previous.get("agency_lineage") or 0.0)),
        abs(float(current.get("counterpart_boundary_delta") or 0.0) - float(previous.get("counterpart_boundary_delta") or 0.0)) / 2.0,
        abs(min(3, int(current.get("hold_count") or 0)) - min(3, int(previous.get("hold_count") or 0))) / 3.0,
        abs(min(6, int(current.get("long_term_axis_count") or 0)) - min(6, int(previous.get("long_term_axis_count") or 0))) / 6.0,
    ]
    categorical_penalty = 0.0
    for key in ("kind", "trace_family", "trigger_family", "carryover_mode"):
        if str(current.get(key) or "").strip().lower() != str(previous.get(key) or "").strip().lower():
            categorical_penalty += 0.18
    embodied_penalty = 0.55 * _embodied_context_shift_score(current.get("embodied_context"), previous.get("embodied_context"))
    return min(1.0, sum(numeric_diffs) / max(1, len(numeric_diffs)) + categorical_penalty + embodied_penalty)


def _int_like(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


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
    reconsolidation_snapshot: dict[str, Any] | None = None,
    source: str,
    allow_behavior_action_inference: bool = True,
    allow_event_behavior_fallback: bool = True,
) -> bool:
    frozen_behavior_semantics = _reconsolidation_behavior_semantics(reconsolidation_snapshot)
    frozen_counterpart = _reconsolidation_counterpart_snapshot(reconsolidation_snapshot)
    frozen_semantic_anchor_bundle = _reconsolidation_semantic_anchor_bundle(reconsolidation_snapshot)
    snapshot_behavior_action = (
        {
            "primary_motive": frozen_behavior_semantics.get("primary_motive", ""),
            "motive_tension": frozen_behavior_semantics.get("motive_tension", ""),
            "goal_frame": frozen_behavior_semantics.get("goal_frame", ""),
        }
        if frozen_behavior_semantics
        else {}
    )
    evidence_behavior_action = None
    if allow_behavior_action_inference:
        if snapshot_behavior_action:
            evidence_behavior_action = snapshot_behavior_action
        elif isinstance(behavior_action, dict):
            evidence_behavior_action = behavior_action
    if allow_behavior_action_inference:
        primary_motive, motive_tension, goal_frame = _behavior_motive_snapshot(
            behavior_action=evidence_behavior_action,
            current_event=current_event,
            allow_event_behavior_fallback=allow_event_behavior_fallback and not bool(snapshot_behavior_action),
        )
        behavior_semantics_source = (
            "reconsolidation_snapshot"
            if snapshot_behavior_action
            else _behavior_motive_snapshot_source(
                behavior_action=evidence_behavior_action,
                current_event=current_event,
                allow_event_behavior_fallback=allow_event_behavior_fallback,
            )
        )
    else:
        primary_motive, motive_tension, goal_frame = "", "", ""
        behavior_semantics_source = ""
    records = _semantic_self_evidence_records(
        user_text=user_text,
        appraisal=appraisal,
        emotion_state=emotion_state,
        bond_state=bond_state,
        persona_core=persona_core,
        counterpart_profile=counterpart_profile,
        current_event=current_event,
        world_model_state=world_model_state,
        behavior_action=evidence_behavior_action,
        allow_behavior_action_inference=allow_behavior_action_inference,
        allow_event_behavior_fallback=allow_event_behavior_fallback and not bool(snapshot_behavior_action),
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
        if behavior_semantics_source:
            trace_metadata["behavior_semantics_source"] = behavior_semantics_source
        if frozen_counterpart:
            trace_metadata["counterpart_stance"] = str(frozen_counterpart.get("stance") or "").strip()
            trace_metadata["counterpart_scene"] = str(frozen_counterpart.get("scene") or "").strip()
            trace_metadata["counterpart_respect_level"] = float(frozen_counterpart.get("respect_level") or 0.0)
            trace_metadata["counterpart_reciprocity"] = float(frozen_counterpart.get("reciprocity") or 0.0)
            trace_metadata["counterpart_boundary_pressure"] = float(frozen_counterpart.get("boundary_pressure") or 0.0)
            trace_metadata["counterpart_reliability_read"] = float(frozen_counterpart.get("reliability_read") or 0.0)
            frozen_counterpart_profile = (
                frozen_counterpart.get("assessment_profile")
                if isinstance(frozen_counterpart.get("assessment_profile"), dict)
                else {}
            )
            if frozen_counterpart_profile:
                frozen_scene_strengths = (
                    frozen_counterpart_profile.get("scene_strengths")
                    if isinstance(frozen_counterpart_profile.get("scene_strengths"), dict)
                    else {}
                )
                trace_metadata["counterpart_openness_drive"] = float(frozen_counterpart_profile.get("openness_drive") or 0.0)
                trace_metadata["counterpart_guarded_drive"] = float(frozen_counterpart_profile.get("guarded_drive") or 0.0)
                trace_metadata["counterpart_guard_margin"] = float(frozen_counterpart_profile.get("guard_margin") or 0.0)
                trace_metadata["counterpart_safety_read"] = float(frozen_counterpart_profile.get("safety_read") or 0.0)
                trace_metadata["counterpart_repairability"] = float(frozen_counterpart_profile.get("repairability") or 0.0)
                trace_metadata["counterpart_predictability"] = float(frozen_counterpart_profile.get("predictability") or 0.0)
                trace_metadata["counterpart_dependency_risk"] = float(frozen_counterpart_profile.get("dependency_risk") or 0.0)
                trace_metadata["counterpart_closeness_read"] = float(frozen_counterpart_profile.get("closeness_read") or 0.0)
                trace_metadata["counterpart_scene_care_strength"] = float(frozen_scene_strengths.get("care") or 0.0)
                trace_metadata["counterpart_scene_repair_strength"] = float(frozen_scene_strengths.get("repair") or 0.0)
                trace_metadata["counterpart_scene_friction_strength"] = float(frozen_scene_strengths.get("friction") or 0.0)
                trace_metadata["counterpart_scene_selfhood_strength"] = float(frozen_scene_strengths.get("selfhood") or 0.0)
                trace_metadata["counterpart_scene_busy_strength"] = float(frozen_scene_strengths.get("busy") or 0.0)
                trace_metadata["counterpart_dominant_scene_signal"] = str(
                    frozen_counterpart_profile.get("dominant_scene_signal") or ""
                ).strip()
        _apply_semantic_anchor_metadata(trace_metadata, frozen_semantic_anchor_bundle)
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
    behavior_plan: dict[str, Any] | None = None,
    interaction_carryover: dict[str, Any] | None = None,
    agenda_lifecycle_residue: dict[str, Any] | None = None,
    digital_body_state: dict[str, Any] | None = None,
    record_behavior_trace_writeback: bool = True,
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
    soft_repair_residue = _looks_like_soft_repair_with_residue(text)
    shared_future_commitment = _looks_like_shared_future_commitment(text)
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
    if soft_repair_residue:
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

    if record_behavior_trace_writeback:
        behavior_trace_written = _record_behavior_trace_writeback(
            store,
            current_event=current_event,
            behavior_action=behavior_action,
            behavior_plan=behavior_plan,
            interaction_carryover=interaction_carryover,
            agenda_lifecycle_residue=agenda_lifecycle_residue,
            digital_body_state=digital_body_state,
            source="auto:passive_evolution",
            confidence=confidence,
        )
        if behavior_trace_written:
            wrote = True

    if _record_passive_text_relational_memory(
        store,
        summary=summary,
        confidence=confidence,
        hurt=hurt,
        irritation=irritation,
        repair_confidence=repair_confidence,
        interaction_frame=interaction_frame,
        has_text=has_text,
        unresolved_like=unresolved_like,
        resolution_like=resolution_like,
        repair_like=repair_like,
        partial_repair_like=partial_repair_like,
        shared_future_commitment=shared_future_commitment,
        familiar_continuity_like=familiar_continuity_like,
        positive_companion_like=positive_companion_like,
    ):
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
        allow_behavior_action_inference=False,
        allow_event_behavior_fallback=False,
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
