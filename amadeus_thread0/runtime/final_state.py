from __future__ import annotations

from typing import Any

from ..graph_parts.behavior_runtime import _behavior_plan_from_action


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
        "primary_motive",
        "motive_tension",
        "goal_frame",
        "deferred_action_family",
        "relationship_weather",
        "attention_target",
        "nonverbal_signal",
    ):
        value = action.get(key)
        if isinstance(value, str) and value.strip():
            return True
    value = action.get("timing_window_min")
    return isinstance(value, (int, float)) and float(value) != 0.0


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
    ):
        value = plan.get(key)
        if isinstance(value, str) and value.strip():
            return True
    for key in ("scheduled_after_min", "timing_window_min"):
        value = plan.get(key)
        if isinstance(value, (int, float)) and float(value) != 0.0:
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
    "resolve_behavior_payloads",
    "resolve_interaction_carryover",
    "resolve_behavior_queue",
]
