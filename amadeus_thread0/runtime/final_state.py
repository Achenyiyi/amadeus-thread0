from __future__ import annotations

from typing import Any

from ..graph_parts.behavior_runtime import _behavior_plan_from_action
from ..utils.counterpart_profile import normalize_counterpart_assessment_profile


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def behavior_action_has_signal(action: dict[str, Any] | None) -> bool:
    if not isinstance(action, dict) or not action:
        return False
    for key in (
        "interaction_mode",
        "action_target",
        "channel",
        "approach_style",
        "followup_intent",
        "task_focus",
        "affect_surface",
        "primary_motive",
        "motive_tension",
        "goal_frame",
        "deferred_action_family",
        "relationship_weather",
        "attention_target",
        "nonverbal_signal",
        "initiative_shape",
        "disclosure_posture",
        "note",
    ):
        value = action.get(key)
        if isinstance(value, str) and value.strip():
            return True
    for key in ("timing_window_min", "engagement_level", "initiative_level", "proactive_checkin_readiness"):
        value = action.get(key)
        if isinstance(value, (int, float)) and float(value) != 0.0:
            return True
    if bool(action.get("silence_ok", False)):
        return True
    window_profile = action.get("window_profile")
    return isinstance(window_profile, dict) and bool(window_profile)


def behavior_action_has_plan_signal(action: dict[str, Any] | None) -> bool:
    if not isinstance(action, dict) or not action:
        return False
    for key in (
        "action_target",
        "primary_motive",
        "motive_tension",
        "goal_frame",
        "deferred_action_family",
        "timing_window_min",
        "relationship_weather",
    ):
        value = action.get(key)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, (int, float)) and float(value) != 0.0:
            return True
    return False


def behavior_plan_has_signal(plan: dict[str, Any] | None) -> bool:
    if not isinstance(plan, dict) or not plan:
        return False
    for key in (
        "kind",
        "target",
        "trigger_family",
        "primary_motive",
        "motive_tension",
        "goal_frame",
        "carryover_mode",
        "relationship_weather",
        "attention_target",
        "nonverbal_signal",
        "note",
    ):
        value = plan.get(key)
        if isinstance(value, str) and value.strip():
            return True
    for key in (
        "scheduled_after_min",
        "timing_window_min",
        "carryover_strength",
        "presence_residue",
        "ambient_resonance",
        "self_activity_momentum",
    ):
        value = plan.get(key)
        if isinstance(value, (int, float)) and float(value) != 0.0:
            return True
    if "allow_interrupt" in plan and isinstance(plan.get("allow_interrupt"), bool):
        return True
    return False


def interaction_carryover_has_signal(carryover: dict[str, Any] | None) -> bool:
    if not isinstance(carryover, dict) or not carryover:
        return False
    for key in (
        "source",
        "carryover_mode",
        "relationship_weather",
        "note",
    ):
        value = carryover.get(key)
        if isinstance(value, str) and value.strip():
            return True
    value = carryover.get("strength")
    return isinstance(value, (int, float)) and float(value) != 0.0


def counterpart_assessment_has_signal(assessment: dict[str, Any] | None) -> bool:
    if not isinstance(assessment, dict) or not assessment:
        return False
    for key in ("summary", "stance", "scene"):
        value = assessment.get(key)
        if isinstance(value, str) and value.strip():
            return True
    for key in ("respect_level", "reciprocity", "boundary_pressure", "reliability_read"):
        value = assessment.get(key)
        if isinstance(value, (int, float)) and float(value) != 0.0:
            return True
    profile = assessment.get("assessment_profile")
    return isinstance(profile, dict) and bool(profile)


def agenda_lifecycle_has_signal(residue: dict[str, Any] | None) -> bool:
    if not isinstance(residue, dict) or not residue:
        return False
    for key in (
        "kind",
        "summary",
        "trigger_family",
        "carryover_mode",
        "relationship_weather",
        "counterpart_scene_bias",
        "primary_motive",
        "motive_tension",
        "goal_frame",
        "note",
    ):
        value = residue.get(key)
        if isinstance(value, str) and value.strip():
            return True
    for key in (
        "hold_count",
        "carryover_strength",
        "recontact_cooldown",
        "presence_residue",
        "ambient_resonance",
        "self_activity_momentum",
        "own_rhythm_bias",
        "continuity_anchor",
        "own_rhythm_anchor",
        "recontact_anchor",
        "boundary_anchor",
        "memory_anchor",
        "semantic_continuity_depth",
        "semantic_identity_gravity",
        "long_term_axis_count",
        "lineage_gravity",
        "contact_lineage",
        "repair_lineage",
        "boundary_lineage",
        "selfhood_lineage",
        "agency_lineage",
        "counterpart_boundary_delta",
    ):
        value = residue.get(key)
        if isinstance(value, (int, float)) and float(value) != 0.0:
            return True
    return False


def _reconsolidation_behavior_action(reconsolidation_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    recon = _dict_or_empty(reconsolidation_snapshot)
    action = _dict_or_empty(recon.get("behavior_action"))
    if behavior_action_has_signal(action):
        return action
    legacy_action = {
        "interaction_mode": str(recon.get("behavior_mode") or "").strip(),
        "primary_motive": str(recon.get("primary_motive") or "").strip(),
        "motive_tension": str(recon.get("motive_tension") or "").strip(),
        "goal_frame": str(recon.get("goal_frame") or "").strip(),
    }
    return legacy_action if behavior_action_has_signal(legacy_action) else {}


def _reconsolidation_behavior_plan(reconsolidation_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    recon = _dict_or_empty(reconsolidation_snapshot)
    plan = _dict_or_empty(recon.get("behavior_plan"))
    return plan if behavior_plan_has_signal(plan) else {}


def _reconsolidation_interaction_carryover(reconsolidation_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    recon = _dict_or_empty(reconsolidation_snapshot)
    carryover = _dict_or_empty(recon.get("interaction_carryover"))
    return carryover if interaction_carryover_has_signal(carryover) else {}


def _reconsolidation_counterpart_assessment(reconsolidation_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    recon = _dict_or_empty(reconsolidation_snapshot)
    counterpart = _dict_or_empty(recon.get("counterpart"))
    return _normalized_counterpart_assessment(counterpart)


def _reconsolidation_agenda_lifecycle(reconsolidation_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    recon = _dict_or_empty(reconsolidation_snapshot)
    residue = _dict_or_empty(recon.get("agenda_lifecycle_consequence"))
    return residue if agenda_lifecycle_has_signal(residue) else {}


def _normalized_counterpart_assessment(assessment: dict[str, Any] | None) -> dict[str, Any]:
    item = _dict_or_empty(assessment)
    if not counterpart_assessment_has_signal(item):
        return {}
    profile = normalize_counterpart_assessment_profile(item)
    if profile:
        item["assessment_profile"] = profile
    elif isinstance(item.get("assessment_profile"), dict) and not item.get("assessment_profile"):
        item.pop("assessment_profile", None)
    return item


def resolve_behavior_payloads(
    *,
    behavior_action: dict[str, Any] | None,
    behavior_plan: dict[str, Any] | None,
    reconsolidation_snapshot: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    live_action = _dict_or_empty(behavior_action)
    live_plan = _dict_or_empty(behavior_plan)
    frozen_action = _reconsolidation_behavior_action(reconsolidation_snapshot)
    frozen_plan = _reconsolidation_behavior_plan(reconsolidation_snapshot)
    action = frozen_action if behavior_action_has_signal(frozen_action) else live_action
    plan = frozen_plan if behavior_plan_has_signal(frozen_plan) else live_plan
    if behavior_plan_has_signal(frozen_plan):
        return action, frozen_plan
    # Once final action is frozen, derive the plan from that same action before
    # considering any live intermediate plan. Otherwise we can leak a stale plan
    # alongside the frozen final action.
    if behavior_action_has_plan_signal(frozen_action):
        derived_plan = _behavior_plan_from_action(
            _dict_or_empty(current_event),
            frozen_action,
            world_model_state=_dict_or_empty(world_model_state),
        )
        if isinstance(derived_plan, dict) and derived_plan:
            return action, dict(derived_plan)
    if behavior_plan_has_signal(plan):
        return action, plan
    derivation_action = action if behavior_action_has_plan_signal(action) else live_action
    if not behavior_action_has_plan_signal(derivation_action):
        return action, plan
    derived_plan = _behavior_plan_from_action(
        _dict_or_empty(current_event),
        derivation_action,
        world_model_state=_dict_or_empty(world_model_state),
    )
    if not isinstance(derived_plan, dict) or not derived_plan:
        return action, plan
    if not plan:
        return action, dict(derived_plan)
    merged_plan = dict(derived_plan)
    merged_plan.update(plan)
    return action, merged_plan


def resolve_interaction_carryover(
    *,
    interaction_carryover: dict[str, Any] | None,
    reconsolidation_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    live_carryover = _dict_or_empty(interaction_carryover)
    frozen_carryover = _reconsolidation_interaction_carryover(reconsolidation_snapshot)
    if interaction_carryover_has_signal(frozen_carryover):
        return frozen_carryover
    return live_carryover


def resolve_counterpart_assessment(
    *,
    counterpart_assessment: dict[str, Any] | None,
    reconsolidation_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    live_counterpart = _normalized_counterpart_assessment(counterpart_assessment)
    frozen_counterpart = _reconsolidation_counterpart_assessment(reconsolidation_snapshot)
    if counterpart_assessment_has_signal(frozen_counterpart):
        return frozen_counterpart
    return live_counterpart


def resolve_agenda_lifecycle_residue(
    *,
    agenda_lifecycle_residue: dict[str, Any] | None,
    reconsolidation_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    live_residue = _dict_or_empty(agenda_lifecycle_residue)
    frozen_residue = _reconsolidation_agenda_lifecycle(reconsolidation_snapshot)
    if agenda_lifecycle_has_signal(frozen_residue):
        return frozen_residue
    return live_residue


def resolve_behavior_queue(
    *,
    behavior_queue: Any,
    behavior_agenda: Any = None,
) -> list[dict[str, Any]]:
    queue = _list_or_empty(behavior_queue)
    agenda = _list_or_empty(behavior_agenda)
    if queue:
        return [dict(item) for item in queue if isinstance(item, dict)]
    if agenda:
        return [dict(item) for item in agenda if isinstance(item, dict)]
    return []


__all__ = [
    "behavior_action_has_signal",
    "behavior_action_has_plan_signal",
    "behavior_plan_has_signal",
    "interaction_carryover_has_signal",
    "counterpart_assessment_has_signal",
    "agenda_lifecycle_has_signal",
    "resolve_behavior_payloads",
    "resolve_interaction_carryover",
    "resolve_counterpart_assessment",
    "resolve_agenda_lifecycle_residue",
    "resolve_behavior_queue",
]
