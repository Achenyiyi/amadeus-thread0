from __future__ import annotations

from typing import Any

from ..graph_parts.behavior_runtime import _behavior_plan_from_action


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


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


def resolve_behavior_payloads(
    *,
    behavior_action: dict[str, Any] | None,
    behavior_plan: dict[str, Any] | None,
    current_event: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    action = _dict_or_empty(behavior_action)
    plan = _dict_or_empty(behavior_plan)
    if behavior_plan_has_signal(plan):
        return action, plan
    if not behavior_action_has_plan_signal(action):
        return action, plan
    derived_plan = _behavior_plan_from_action(
        _dict_or_empty(current_event),
        action,
        world_model_state=_dict_or_empty(world_model_state),
    )
    if not isinstance(derived_plan, dict) or not derived_plan:
        return action, plan
    if not plan:
        return action, dict(derived_plan)
    merged_plan = dict(derived_plan)
    merged_plan.update(plan)
    return action, merged_plan


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
    "behavior_action_has_plan_signal",
    "behavior_plan_has_signal",
    "resolve_behavior_payloads",
    "resolve_behavior_queue",
]
