from __future__ import annotations

import re
from typing import Any

from .behavior_agenda import _agenda_long_horizon_snapshot
from .common import _clamp01, _now_ts
from .digital_body_runtime import normalize_embodied_context, normalize_embodied_trace_context
from .prompt_helpers import _compact_embodied_carryover_hint
from .state import AgendaLifecycleResiduePayload, InteractionCarryoverPayload, ThreadState


def _recent_non_user_event_with_gap(
    recent_events: Any,
    *,
    max_user_turn_gap: int = 3,
) -> tuple[dict[str, Any], str, int]:
    if not isinstance(recent_events, list):
        return {}, "", 0
    user_turn_gap = 0
    for item in reversed(recent_events):
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip().lower()
        if not kind:
            continue
        if kind == "user_utterance":
            user_turn_gap += 1
            if user_turn_gap > max(0, int(max_user_turn_gap)):
                break
            continue
        return dict(item), kind, user_turn_gap
    return {}, "", 0

def _history_source_behavior_hint(source_event: dict[str, Any]) -> dict[str, str]:
    event = dict(source_event or {})
    kind = str(event.get("kind") or "").strip().lower()
    tags = {
        str(tag).strip().lower()
        for tag in (event.get("tags") if isinstance(event.get("tags"), list) else [])
        if str(tag).strip()
    }
    carryover_mode = str(event.get("carryover_mode") or "").strip().lower()
    attention_target = str(event.get("attention_target_hint") or "").strip()
    nonverbal_signal = str(event.get("nonverbal_signal_hint") or "").strip()

    if kind == "self_activity_state":
        if {"deep_focus", "own_task"} & tags or carryover_mode == "own_rhythm":
            return {
                "behavior_mode": "self_activity_hold",
                "action_target": "hold_own_rhythm",
                "attention_target": attention_target or "self_then_counterpart",
                "nonverbal_signal": nonverbal_signal or "thought_glance",
            }
        return {
            "behavior_mode": "self_activity_reopen",
            "action_target": "offer_small_opening",
            "attention_target": attention_target or "self_then_counterpart",
            "nonverbal_signal": nonverbal_signal or "thought_glance",
        }
    if kind in {"scheduled_checkin_due", "scheduled_life_due"}:
        if {"shared_activity_window", "offer_window"} & tags or "shared_activity" in str(event.get("trigger_family") or "").strip().lower():
            return {
                "behavior_mode": "shared_activity_offer",
                "action_target": "offer_shared_activity",
                "attention_target": attention_target or "shared_window",
                "nonverbal_signal": nonverbal_signal or "nudge_presence",
            }
        if {"deadline_window", "work_nudge", "task_window"} & tags or str(event.get("trigger_family") or "").strip().lower() == "deadline_window":
            return {
                "behavior_mode": "scheduled_life_nudge",
                "action_target": "light_work_nudge",
                "attention_target": attention_target or "shared_task",
                "nonverbal_signal": nonverbal_signal or "focus_glance",
            }
        if {"life_window"} & tags or str(event.get("trigger_family") or "").strip().lower() == "life_window":
            return {
                "behavior_mode": "scheduled_life_nudge",
                "action_target": "light_life_nudge",
                "attention_target": attention_target or "counterpart_state",
                "nonverbal_signal": nonverbal_signal or "quiet_glance",
            }
        return {
            "behavior_mode": "proactive_checkin" if kind == "scheduled_checkin_due" else "scheduled_life_nudge",
            "action_target": "wait_and_recheck",
            "attention_target": attention_target or "counterpart_state",
            "nonverbal_signal": nonverbal_signal or "quiet_glance",
        }
    if kind == "time_idle":
        if {"respect_space", "user_busy", "cognitive_load"} & tags:
            return {
                "behavior_mode": "idle_presence",
                "action_target": "wait_and_recheck",
                "attention_target": attention_target or "counterpart_state",
                "nonverbal_signal": nonverbal_signal or "quiet_glance",
            }
        return {
            "behavior_mode": "idle_presence",
            "action_target": "hold_own_rhythm" if {"self_activity", "own_task", "quiet_presence"} & tags else "reach_out_now",
            "attention_target": attention_target or "self_then_counterpart",
            "nonverbal_signal": nonverbal_signal or "thought_glance",
        }
    if kind == "gesture_signal":
        return {
            "behavior_mode": "brief_presence",
            "action_target": "confirm_presence",
            "attention_target": attention_target or "counterpart_state",
            "nonverbal_signal": nonverbal_signal or "brief_notice",
        }
    if kind == "ambient_shift":
        return {
            "behavior_mode": "companion_reply",
            "action_target": "ambient_checkin",
            "attention_target": attention_target or "ambient_cue",
            "nonverbal_signal": nonverbal_signal or "still_presence",
        }
    if kind == "scene_observation":
        return {
            "behavior_mode": "companion_reply",
            "action_target": "respond_now",
            "attention_target": attention_target or "object_then_user",
            "nonverbal_signal": nonverbal_signal or "small_notice",
        }
    return {
        "behavior_mode": "",
        "action_target": "",
        "attention_target": attention_target,
        "nonverbal_signal": nonverbal_signal,
    }


def _has_trace_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _trace_value(item: dict[str, Any], key: str, default: Any = None) -> Any:
    if not isinstance(item, dict):
        return default
    direct = item.get(key)
    if _has_trace_value(direct):
        return direct
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    meta_value = metadata.get(key)
    if _has_trace_value(meta_value):
        return meta_value
    content = item.get("content") if isinstance(item.get("content"), dict) else {}
    content_value = content.get(key)
    if _has_trace_value(content_value):
        return content_value
    content_metadata = content.get("metadata") if isinstance(content.get("metadata"), dict) else {}
    content_meta_value = content_metadata.get(key)
    if _has_trace_value(content_meta_value):
        return content_meta_value
    return default


def _embodied_summary_mentions_constraint(summary: str, embodied_context: dict[str, Any] | None) -> bool:
    text = str(summary or "").strip().lower()
    embodied = normalize_embodied_context(embodied_context)
    if not text or not embodied:
        return False
    tokens: list[str] = []
    for key in ("requested_access", "missing_access", "granted_toolsets", "active_tools", "world_surfaces"):
        value = embodied.get(key)
        if isinstance(value, list):
            tokens.extend(str(item or "").strip().lower() for item in value if str(item or "").strip())
    block_reason = str(embodied.get("block_reason") or "").strip().lower()
    if block_reason:
        tokens.append(block_reason)
    if any(token and token in text for token in tokens):
        return True
    kind = str(embodied.get("kind") or "").strip().lower()
    if kind == "access_request_pending":
        return any(marker in text for marker in ("入口", "审批", "批准", "没放开", "未完成", "没做完"))
    if kind == "environmental_friction":
        return any(marker in text for marker in ("环境条件", "卡着", "受阻", "缺着", "限制"))
    if kind == "embodied_growth":
        return any(marker in text for marker in ("摸顺", "会用了", "继续用", "新路径", "从零开始"))
    return False


def _embodied_aware_summary(summary: str, embodied_context: dict[str, Any] | None) -> str:
    base = str(summary or "").strip()
    embodied = normalize_embodied_context(embodied_context)
    if not embodied:
        return base
    suffix = _compact_embodied_carryover_hint({"embodied_context": embodied}).strip()
    if not suffix:
        return base
    if _embodied_summary_mentions_constraint(base, embodied):
        return base
    if not base:
        return suffix
    return f"{base.rstrip('。')}；{suffix}"


def _bridge_mode_from_behavior_trace(item: dict[str, Any]) -> str:
    trigger_family = str(
        _trace_value(item, "trigger_family", _trace_value(item, "source_trigger_family", "")) or ""
    ).strip().lower()
    carryover_mode = str(_trace_value(item, "carryover_mode", "") or "").strip().lower()
    plan_kind = str(
        _trace_value(item, "plan_kind", _trace_value(item, "current_plan_kind", _trace_value(item, "source_plan_kind", "")))
        or ""
    ).strip().lower()

    if trigger_family in {"shared_activity", "shared_activity_window"}:
        return "shared_window"
    if trigger_family == "deadline_window":
        return "task_window"
    if trigger_family == "life_window":
        return "life_window"
    if carryover_mode in {
        "own_rhythm",
        "quiet_recontact",
        "small_opening",
        "brief_presence",
        "ambient_echo",
        "shared_window",
        "task_window",
        "life_window",
    }:
        return carryover_mode
    if plan_kind == "shared_activity_offer":
        return "shared_window"
    if plan_kind == "work_nudge":
        return "task_window"
    if plan_kind == "life_nudge":
        return "life_window"
    if plan_kind == "small_opening":
        return "small_opening"
    if plan_kind == "self_activity_continue":
        return "own_rhythm"
    if plan_kind == "presence_confirmation":
        return "brief_presence"
    if plan_kind == "ambient_checkin":
        return "ambient_echo"
    if plan_kind == "deferred_checkin":
        return "quiet_recontact"
    return ""


def _bridge_defaults_for_mode(mode: str) -> tuple[str, str]:
    key = str(mode or "").strip().lower()
    if key == "shared_window":
        return "shared_window", "nudge_presence"
    if key == "task_window":
        return "shared_task", "focus_glance"
    if key == "life_window":
        return "counterpart_state", "quiet_glance"
    if key == "small_opening":
        return "self_then_counterpart", "thought_glance"
    if key == "own_rhythm":
        return "self_then_counterpart", "thought_glance"
    if key == "ambient_echo":
        return "ambient_cue", "small_notice"
    if key == "brief_presence":
        return "counterpart_state", "brief_notice"
    return "counterpart_state", "quiet_glance"


def _implicit_strength_from_behavior_consequence_trace(item: dict[str, Any]) -> float:
    relationship_weather = str(_trace_value(item, "relationship_weather", "") or "").strip().lower()
    relationship_effect = str(_trace_value(item, "relationship_effect", "") or "").strip().lower()
    self_effect = str(_trace_value(item, "self_effect", "") or "").strip().lower()
    carryover_mode = str(_trace_value(item, "carryover_mode", "") or "").strip().lower()
    consequence_kind = str(_trace_value(item, "consequence_kind", "") or "").strip().lower()

    score = 0.0
    if relationship_weather in {"warm_residue", "repair_residue"}:
        score = max(score, 0.24)
    elif relationship_weather == "guarded_residue":
        score = max(score, 0.18)

    relationship_effect_floor = {
        "soft_reapproach": 0.34,
        "contact_deferred": 0.28,
        "window_released": 0.24,
        "space_preserved": 0.22,
    }
    self_effect_floor = {
        "partial_reengagement": 0.34,
        "recheck_pending": 0.26,
        "attention_returns_to_self": 0.24,
        "own_rhythm_continues": 0.28,
    }
    kind_floor = {
        "leave_small_opening": 0.34,
        "defer_recontact": 0.28,
        "let_window_expire": 0.24,
        "hold_own_rhythm": 0.26,
    }
    mode_floor = {
        "small_opening": 0.30,
        "quiet_recontact": 0.26,
        "own_rhythm": 0.28,
        "brief_presence": 0.22,
        "ambient_echo": 0.20,
        "life_window": 0.26,
        "shared_window": 0.28,
        "task_window": 0.24,
    }

    score = max(
        score,
        relationship_effect_floor.get(relationship_effect, 0.0),
        self_effect_floor.get(self_effect, 0.0),
        kind_floor.get(consequence_kind, 0.0),
        mode_floor.get(carryover_mode, 0.0),
    )
    return _clamp01(score, 0.0)


def _consequence_trace_runtime_residue(
    item: dict[str, Any],
    *,
    derived_strength: float,
) -> tuple[float, float, float]:
    relationship_weather = str(_trace_value(item, "relationship_weather", "") or "").strip().lower()
    relationship_effect = str(_trace_value(item, "relationship_effect", "") or "").strip().lower()
    self_effect = str(_trace_value(item, "self_effect", "") or "").strip().lower()
    carryover_mode = str(_trace_value(item, "carryover_mode", "") or "").strip().lower()

    presence_residue = _clamp01(_trace_value(item, "presence_residue", 0.0), 0.0)
    ambient_resonance = _clamp01(_trace_value(item, "ambient_resonance", 0.0), 0.0)
    self_activity_momentum = _clamp01(_trace_value(item, "self_activity_momentum", 0.0), 0.0)

    if presence_residue <= 0.0 and (
        relationship_weather in {"warm_residue", "repair_residue"}
        or relationship_effect in {"soft_reapproach", "contact_deferred", "window_released"}
    ):
        presence_multiplier = (
            0.86
            if relationship_effect == "soft_reapproach"
            else 0.82
            if relationship_effect == "contact_deferred"
            else 0.86
            if relationship_effect == "window_released"
            else 0.78
        )
        presence_floor = max(
            0.0,
            0.22 if carryover_mode == "quiet_recontact" else 0.0,
            0.24 if carryover_mode == "brief_presence" else 0.0,
            0.24 if relationship_weather == "warm_residue" and relationship_effect == "soft_reapproach" else 0.0,
            0.22 if relationship_weather == "warm_residue" and relationship_effect in {"contact_deferred", "window_released"} else 0.0,
            0.20 if relationship_weather == "repair_residue" else 0.0,
        )
        presence_residue = max(
            presence_residue,
            derived_strength * presence_multiplier,
            presence_floor,
        )

    if ambient_resonance <= 0.0 and carryover_mode in {"quiet_recontact", "brief_presence", "ambient_echo", "life_window"}:
        ambient_resonance = max(ambient_resonance, derived_strength * (0.42 if carryover_mode == "ambient_echo" else 0.24))

    if self_activity_momentum <= 0.0 and (
        carryover_mode in {"own_rhythm", "small_opening"}
        or self_effect in {"own_rhythm_continues", "attention_returns_to_self"}
    ):
        self_activity_momentum = max(
            self_activity_momentum,
            derived_strength * (
                0.88
                if self_effect == "own_rhythm_continues"
                else 0.76
                if self_effect == "attention_returns_to_self"
                else 0.70
            ),
        )

    return (
        round(_clamp01(presence_residue, 0.0), 3),
        round(_clamp01(ambient_resonance, 0.0), 3),
        round(_clamp01(self_activity_momentum, 0.0), 3),
    )


def _build_retrieved_behavior_trace_bridge(
    *,
    retrieved: dict[str, Any],
    current_event: dict[str, Any],
    interaction_carryover: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(retrieved, dict):
        return {}
    traces: list[tuple[str, dict[str, Any]]] = []
    reactivation_traces = retrieved.get("behavior_reactivation_traces")
    if isinstance(reactivation_traces, list):
        traces.extend(
            ("retrieved_behavior_reactivation", item if isinstance(item, dict) else {})
            for item in reactivation_traces
        )
    consequence_traces = retrieved.get("behavior_consequence_traces")
    if isinstance(consequence_traces, list):
        traces.extend(
            ("retrieved_behavior_consequence", item if isinstance(item, dict) else {})
            for item in consequence_traces
        )
    digital_body_traces = retrieved.get("digital_body_consequence_traces")
    if isinstance(digital_body_traces, list):
        traces.extend(
            ("retrieved_digital_body_consequence", item if isinstance(item, dict) else {})
            for item in digital_body_traces
        )
    plan_traces = retrieved.get("behavior_plan_traces")
    if isinstance(plan_traces, list):
        traces.extend(
            ("retrieved_behavior_plan", item if isinstance(item, dict) else {})
            for item in plan_traces
        )
    if not traces:
        return {}

    current = dict(current_event or {})
    carryover = dict(interaction_carryover or {})
    event_kind = str(current.get("kind") or "").strip().lower()
    event_tags = {
        str(item).strip().lower()
        for item in (current.get("tags") if isinstance(current.get("tags"), list) else [])
        if str(item).strip()
    }
    existing_mode = str(carryover.get("carryover_mode") or current.get("carryover_mode") or "").strip().lower()
    existing_strength = max(
        _clamp01(carryover.get("strength"), 0.0),
        _clamp01(current.get("carryover_strength"), 0.0),
    )
    if existing_mode or existing_strength >= 0.18:
        return {}
    if event_kind not in {"user_utterance", "time_idle"}:
        return {}
    if {"user_busy", "cognitive_load", "respect_space"} & event_tags:
        return {}

    for trace_source, trace in traces:
        current_plan_kind = str(_trace_value(trace, "current_plan_kind", _trace_value(trace, "plan_kind", "")) or "").strip().lower()
        source_plan_kind = str(_trace_value(trace, "source_plan_kind", "") or "").strip().lower()
        plan_kind = current_plan_kind or source_plan_kind
        consequence_kind = str(_trace_value(trace, "consequence_kind", "") or "").strip().lower()
        body_consequence_kind = str(_trace_value(trace, "body_consequence_kind", _trace_value(trace, "kind", "")) or "").strip().lower()
        embodied_context = normalize_embodied_trace_context(trace)
        if trace_source == "retrieved_behavior_consequence":
            if consequence_kind in {"", "none"}:
                continue
        elif trace_source == "retrieved_digital_body_consequence":
            artifact_carrier = str(
                _trace_value(trace, "artifact_carrier", embodied_context.get("artifact_carrier", "")) or ""
            ).strip().lower()
            active_artifact_kind = str(
                _trace_value(trace, "active_artifact_kind", embodied_context.get("active_artifact_kind", "")) or ""
            ).strip().lower()
            workspace_root = str(embodied_context.get("workspace_root") or "").strip()
            sandbox_run_id = str(embodied_context.get("sandbox_run_id") or "").strip()
            skill_effects = [
                dict(effect)
                for effect in (embodied_context.get("skill_effects") if isinstance(embodied_context.get("skill_effects"), list) else [])
                if isinstance(effect, dict)
            ][:6]
            primary_skill = dict(skill_effects[0]) if skill_effects else {}
            skill_use_kind = str(primary_skill.get("use_kind") or "").strip().lower()
            work_surface_kinds = {"workspace_file_updated", "workspace_path_inspected"}
            source_surface_kinds = {"source_material_compared", "source_material_inspected"}
            access_state_kinds = {"workspace_access_resolved", "access_state_refreshed"}
            sandbox_surface_kinds = {"sandbox_execution_completed", "sandbox_execution_blocked"}
            browser_surface_kinds = {
                "browser_navigation_completed",
                "browser_interaction_completed",
                "browser_download_completed",
                "browser_upload_completed",
                "browser_takeover_requested",
                "browser_action_blocked",
            }
            if body_consequence_kind in source_surface_kinds:
                if artifact_carrier != "source_ref":
                    continue
            elif body_consequence_kind == "artifact_reacquired":
                if artifact_carrier == "source_ref":
                    pass
                elif artifact_carrier == "filesystem" or active_artifact_kind in {"file", "workspace"} or workspace_root:
                    pass
                else:
                    continue
            elif body_consequence_kind in work_surface_kinds:
                if not (artifact_carrier == "filesystem" or active_artifact_kind in {"file", "workspace"} or workspace_root):
                    continue
            elif body_consequence_kind == "workspace_access_resolved":
                if not any(
                    (
                        str(embodied_context.get("access_mode") or "").strip().lower(),
                        workspace_root,
                        active_artifact_kind in {"file", "workspace"},
                        bool(embodied_context.get("granted_toolsets")),
                        bool(embodied_context.get("active_tools")),
                    )
                ):
                    continue
            elif body_consequence_kind == "access_state_refreshed":
                if not any(
                    (
                        str(embodied_context.get("session_continuity") or "").strip().lower(),
                        str(embodied_context.get("session_recovery_mode") or "").strip().lower(),
                        str(embodied_context.get("browser_session") or "").strip().lower(),
                        str(embodied_context.get("account_state") or "").strip().lower(),
                        str(embodied_context.get("cookie_state") or "").strip().lower(),
                        str(embodied_context.get("filesystem_state") or "").strip().lower(),
                        str(embodied_context.get("network_access") or "").strip().lower(),
                        str(embodied_context.get("sandbox_mode") or "").strip().lower(),
                        workspace_root,
                    )
                ):
                    continue
            elif body_consequence_kind == "workspace_root_attached":
                if not any(
                    (
                        workspace_root,
                        active_artifact_kind in {"file", "workspace"},
                        artifact_carrier == "filesystem",
                    )
                ):
                    continue
            elif body_consequence_kind in sandbox_surface_kinds:
                if not any(
                    (
                        sandbox_run_id,
                        workspace_root,
                        artifact_carrier == "filesystem",
                        active_artifact_kind in {"file", "workspace"},
                        bool(embodied_context.get("sandbox_stdout_log_ref")),
                        bool(embodied_context.get("sandbox_stderr_log_ref")),
                        bool(embodied_context.get("sandbox_produced_artifacts")),
                    )
                ):
                    continue
            elif body_consequence_kind in browser_surface_kinds:
                if not any(
                    (
                        artifact_carrier == "browser_page",
                        active_artifact_kind in {"page", "tab", "browser_page"},
                        str(embodied_context.get("browser_run_id") or "").strip(),
                        str(embodied_context.get("browser_profile_id") or "").strip(),
                        str(embodied_context.get("browser_page_id") or "").strip(),
                        str(embodied_context.get("browser_tab_id") or "").strip(),
                        str(embodied_context.get("browser_url") or "").strip(),
                        str(embodied_context.get("browser_title") or "").strip(),
                        bool(embodied_context.get("browser_runtime_state")),
                    )
                ):
                    continue
            elif body_consequence_kind in {
                "skill_install_completed",
                "skill_activation_changed",
                "skill_usage_completed",
                "skill_mutation_blocked",
            }:
                if not skill_effects:
                    continue
            else:
                continue
        elif plan_kind in {"", "none", "observe_only", "respond_now", "speak_now"}:
            continue
        summary = str(_trace_value(trace, "after_summary", "") or "").strip()
        trigger_family = str(
            _trace_value(trace, "trigger_family", _trace_value(trace, "source_trigger_family", ""))
            or ""
        ).strip().lower()
        event_mode = str(_trace_value(trace, "carryover_mode", "") or "").strip().lower()
        attention_target = str(_trace_value(trace, "attention_target", "") or "").strip().lower()
        nonverbal_signal = str(_trace_value(trace, "nonverbal_signal", "") or "").strip().lower()
        relationship_weather = str(_trace_value(trace, "relationship_weather", "") or "").strip().lower()
        carryover_strength = _clamp01(_trace_value(trace, "carryover_strength", 0.0), 0.0)
        presence_residue = _clamp01(_trace_value(trace, "presence_residue", 0.0), 0.0)
        ambient_resonance = _clamp01(_trace_value(trace, "ambient_resonance", 0.0), 0.0)
        self_activity_momentum = _clamp01(_trace_value(trace, "self_activity_momentum", 0.0), 0.0)
        summary = _embodied_aware_summary(summary, embodied_context)
        if trace_source == "retrieved_digital_body_consequence":
            bridge_mode = "task_window"
            trigger_family = trigger_family or (
                "source_anchor"
                if body_consequence_kind in {"source_material_compared", "source_material_inspected"}
                else "access_state"
                if body_consequence_kind in {"workspace_access_resolved", "access_state_refreshed", "workspace_root_attached"}
                else "browser_page"
                if body_consequence_kind in browser_surface_kinds
                else "source_anchor"
                if skill_use_kind == "source_ref_continuity"
                else "workspace_surface"
                if skill_use_kind == "workspace_workflow"
                else "workspace_surface"
            )
            if carryover_strength <= 0.0:
                carryover_strength = {
                    "source_material_compared": 0.36,
                    "source_material_inspected": 0.24,
                    "workspace_access_resolved": 0.28,
                    "access_state_refreshed": 0.22,
                    "workspace_root_attached": 0.28,
                    "workspace_file_updated": 0.34,
                    "workspace_path_inspected": 0.24,
                    "artifact_reacquired": 0.28,
                    "sandbox_execution_completed": 0.34,
                    "sandbox_execution_blocked": 0.24,
                    "browser_navigation_completed": 0.32,
                    "browser_interaction_completed": 0.34,
                    "browser_download_completed": 0.34,
                    "browser_upload_completed": 0.34,
                    "browser_takeover_requested": 0.26,
                    "browser_action_blocked": 0.24,
                    "skill_install_completed": 0.28,
                    "skill_activation_changed": 0.22,
                    "skill_usage_completed": 0.30,
                    "skill_mutation_blocked": 0.20,
                }.get(body_consequence_kind, 0.24)
            if presence_residue <= 0.0:
                presence_residue = {
                    "source_material_compared": 0.12,
                    "source_material_inspected": 0.08,
                    "workspace_access_resolved": 0.08,
                    "access_state_refreshed": 0.06,
                    "workspace_root_attached": 0.08,
                    "workspace_file_updated": 0.10,
                    "workspace_path_inspected": 0.08,
                    "artifact_reacquired": 0.10,
                    "sandbox_execution_completed": 0.10,
                    "sandbox_execution_blocked": 0.08,
                    "browser_navigation_completed": 0.10,
                    "browser_interaction_completed": 0.10,
                    "browser_download_completed": 0.10,
                    "browser_upload_completed": 0.10,
                    "browser_takeover_requested": 0.08,
                    "browser_action_blocked": 0.08,
                    "skill_install_completed": 0.10,
                    "skill_activation_changed": 0.08,
                    "skill_usage_completed": 0.10,
                    "skill_mutation_blocked": 0.08,
                }.get(body_consequence_kind, 0.08)
            if ambient_resonance <= 0.0:
                ambient_resonance = {
                    "source_material_compared": 0.18,
                    "source_material_inspected": 0.12,
                    "workspace_access_resolved": 0.08,
                    "access_state_refreshed": 0.06,
                    "workspace_root_attached": 0.08,
                    "workspace_file_updated": 0.10,
                    "workspace_path_inspected": 0.08,
                    "artifact_reacquired": 0.10,
                    "sandbox_execution_completed": 0.10,
                    "sandbox_execution_blocked": 0.08,
                    "browser_navigation_completed": 0.12,
                    "browser_interaction_completed": 0.12,
                    "browser_download_completed": 0.12,
                    "browser_upload_completed": 0.12,
                    "browser_takeover_requested": 0.08,
                    "browser_action_blocked": 0.08,
                    "skill_install_completed": 0.08,
                    "skill_activation_changed": 0.06,
                    "skill_usage_completed": 0.10,
                    "skill_mutation_blocked": 0.06,
                }.get(body_consequence_kind, 0.10)
            if not summary:
                summary = {
                    "source_material_compared": "前面那组材料已经对照过一遍了，当前判断会顺着重新锚定后的资料线继续。",
                    "source_material_inspected": "前面那条材料已经重新看过一遍了，当前判断会顺着这条资料面继续。",
                    "workspace_access_resolved": "前面那条工作区入口已经接上了，后面的文件动作可以在同一个边界里继续。",
                    "access_state_refreshed": "前面那条入口状态已经重新确认过了，后面的推进可以顺着这条路继续。",
                    "workspace_root_attached": "前面那条 repo root 已经正式挂接成当前 workspace，后面的代码和研究动作可以顺着这块真实工作面继续。",
                    "workspace_file_updated": "前面那条文件工作面已经真的接上了，后面的推进可以顺着这块表面继续。",
                    "workspace_path_inspected": "前面那条文件工作面已经重新看过一遍，后面的推进可以顺着这块表面继续。",
                    "artifact_reacquired": "前面那块工作面已经重新接回当前上下文，后面的动作可以顺着它继续。",
                    "sandbox_execution_completed": "前面那次受限执行已经真实跑完，后面的排查和推进可以顺着它留下的日志或产物继续。",
                    "sandbox_execution_blocked": "前面那次受限执行没有真正跑通，后面的排查可以顺着它留下的错误日志和边界继续。",
                    "browser_navigation_completed": "前面那个 live browser 页面已经真实打开或更新，后面的动作可以顺着同一个 profile 和 tab 继续。",
                    "browser_interaction_completed": "前面那个 live browser 交互已经真实完成，后面的动作可以顺着同一个页面状态继续。",
                    "browser_download_completed": "前面那个 live browser 下载已经真实落到受控目录，后面的动作可以顺着这个产物继续。",
                    "browser_upload_completed": "前面那个 live browser 上传已经真实完成，后面的动作可以顺着当前页面和已提交文件继续。",
                    "browser_takeover_requested": "前面那个 live browser 步骤已经转成人工接管，后面要沿同一个 profile 继续，而不是写成她已完成凭据动作。",
                    "browser_action_blocked": "前面那个 live browser 动作没有真正跑通，后面的排查要顺着当前页面、run 记录和阻断原因继续。",
                    "skill_install_completed": "前面那条 skill 安装已经真的落地了，后面的匹配和执行会顺着这条能力生态继续。",
                    "skill_activation_changed": "前面那条 skill 的激活态已经切换完成，后面的决策会沿这次能力生态变化继续。",
                    "skill_usage_completed": "前面那条 skill 已经真正参与过一次动作了，后面的推进可以顺着它留下的工作面继续。",
                    "skill_mutation_blocked": "前面那条 skill 变更没有真正落地，后面如果还要继续，得沿着被挡住的边界重新处理。",
                }.get(
                    body_consequence_kind,
                    "前面那条工作面已经重新接回当前上下文，后面的推进可以顺着它继续。",
                )
        else:
            bridge_mode = _bridge_mode_from_behavior_trace(trace)
        derived_strength = _clamp01(
            max(
                carryover_strength,
                presence_residue,
                0.82 * ambient_resonance,
                self_activity_momentum if (event_mode or bridge_mode) in {"own_rhythm", "small_opening"} else 0.0,
            ),
            0.0,
        )
        if trace_source == "retrieved_behavior_consequence":
            derived_strength = max(derived_strength, _implicit_strength_from_behavior_consequence_trace(trace))
            presence_residue, ambient_resonance, self_activity_momentum = _consequence_trace_runtime_residue(
                trace,
                derived_strength=derived_strength,
            )
        if not bridge_mode or derived_strength < 0.12:
            continue
        default_attention_target, default_nonverbal_signal = _bridge_defaults_for_mode(bridge_mode)
        source_tags = [
            trace_source,
            "continuity_anchor",
            f"plan_kind:{plan_kind}" if plan_kind else "",
            f"consequence_kind:{consequence_kind}" if consequence_kind else "",
            f"body_consequence_kind:{body_consequence_kind}" if body_consequence_kind else "",
            f"trigger_family:{trigger_family}" if trigger_family else "",
        ]
        for skill_effect in [
            dict(effect)
            for effect in (embodied_context.get("skill_effects") if isinstance(embodied_context.get("skill_effects"), list) else [])
            if isinstance(effect, dict)
        ][:3]:
            skill_id = str(skill_effect.get("skill_id") or "").strip().lower()
            operation = str(skill_effect.get("operation") or "").strip().lower()
            use_kind = str(skill_effect.get("use_kind") or "").strip().lower()
            if skill_id:
                source_tags.append(f"skill:{skill_id}")
            if operation:
                source_tags.append(f"skillop:{operation}")
            if use_kind:
                source_tags.append(f"skilluse:{use_kind}")
        if source_plan_kind and source_plan_kind != plan_kind:
            source_tags.append(f"source_plan_kind:{source_plan_kind}")
        relationship_effect = str(_trace_value(trace, "relationship_effect", "") or "").strip().lower()
        self_effect = str(_trace_value(trace, "self_effect", "") or "").strip().lower()
        if relationship_effect:
            source_tags.append(f"relationship_effect:{relationship_effect}")
        if self_effect:
            source_tags.append(f"self_effect:{self_effect}")
        source_tags = list(
            dict.fromkeys(
                [
                    *source_tags,
                    f"bodyfx:{str(embodied_context.get('kind') or '').strip().lower()}" if embodied_context else "",
                    "bodyfx:requested_help" if bool(embodied_context.get("requested_help", False)) else "",
                    "bodyfx:friction" if bool(embodied_context.get("environmental_friction", False)) else "",
                    "bodyfx:growth" if bool(embodied_context.get("procedural_growth", False)) else "",
                ]
            )
        )
        result = {
            "interaction_carryover": {
                "carryover_mode": bridge_mode,
                "strength": round(derived_strength, 3),
                "relationship_weather": relationship_weather,
                "attention_target": attention_target or default_attention_target,
                "nonverbal_signal": nonverbal_signal or default_nonverbal_signal,
                "note": summary,
                "source": trace_source,
                "source_tags": [tag for tag in source_tags if tag],
            },
            "event_patch": {
                "carryover_mode": event_mode or bridge_mode,
                "carryover_strength": round(derived_strength, 3),
                "relationship_weather": relationship_weather,
                "presence_residue": round(presence_residue, 3),
                "ambient_resonance": round(ambient_resonance, 3),
                "self_activity_momentum": round(self_activity_momentum, 3),
            },
        }
        if embodied_context:
            result["interaction_carryover"]["embodied_context"] = embodied_context
        return result
    return {}


def _apply_retrieved_behavior_trace_bridge(
    *,
    retrieved: dict[str, Any],
    current_event: dict[str, Any],
    interaction_carryover: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    bridge = _build_retrieved_behavior_trace_bridge(
        retrieved=retrieved,
        current_event=current_event,
        interaction_carryover=interaction_carryover,
    )
    if not bridge:
        return dict(current_event or {}), dict(interaction_carryover or {})
    merged_event = dict(current_event or {})
    merged_event.update(dict(bridge.get("event_patch") or {}))
    merged_carryover = dict(interaction_carryover or {})
    merged_carryover.update(dict(bridge.get("interaction_carryover") or {}))
    return merged_event, merged_carryover


def _hydrate_retrieved_agenda_lifecycle_residue(
    *,
    retrieved: dict[str, Any],
) -> AgendaLifecycleResiduePayload:
    if not isinstance(retrieved, dict):
        return {}
    traces = retrieved.get("agenda_lifecycle_traces")
    if not isinstance(traces, list):
        return {}

    for item in traces:
        trace = item if isinstance(item, dict) else {}
        summary = str(_trace_value(trace, "after_summary", "") or "").strip()
        kind = str(_trace_value(trace, "lifecycle_kind", _trace_value(trace, "kind", "")) or "").strip().lower()
        carryover_mode = str(_trace_value(trace, "carryover_mode", "") or "").strip().lower()
        carryover_strength = _clamp01(_trace_value(trace, "carryover_strength", 0.0), 0.0)
        embodied_context = normalize_embodied_trace_context(trace)
        summary = _embodied_aware_summary(summary, embodied_context)
        try:
            counterpart_boundary_delta = float(_trace_value(trace, "counterpart_boundary_delta", 0.0) or 0.0)
        except Exception:
            counterpart_boundary_delta = 0.0
        if kind not in {"held", "released_to_self_activity", "dropped", "expired"}:
            continue
        if not summary or not carryover_mode or carryover_strength < 0.12:
            continue

        source_tags = [
            str(tag).strip().lower()
            for tag in (_trace_value(trace, "source_tags", []) or [])
            if str(tag).strip()
        ]
        source_tags = list(
            dict.fromkeys(
                [
                    *source_tags,
                    "agenda_lifecycle",
                    kind,
                    "retrieved_agenda_lifecycle",
                    f"bodyfx:{str(embodied_context.get('kind') or '').strip().lower()}" if embodied_context else "",
                    "bodyfx:requested_help" if bool(embodied_context.get("requested_help", False)) else "",
                    "bodyfx:friction" if bool(embodied_context.get("environmental_friction", False)) else "",
                    "bodyfx:growth" if bool(embodied_context.get("procedural_growth", False)) else "",
                ]
            )
        )
        residue: AgendaLifecycleResiduePayload = {
            "kind": kind,
            "source_event_kind": str(_trace_value(trace, "source_event_kind", "time_idle") or "").strip().lower()
            or "time_idle",
            "trigger_family": str(_trace_value(trace, "trigger_family", "") or "").strip().lower(),
            "carryover_mode": carryover_mode,
            "carryover_strength": round(carryover_strength, 3),
            "relationship_weather": str(_trace_value(trace, "relationship_weather", "") or "").strip().lower(),
            "hold_count": max(0, int(_trace_value(trace, "hold_count", 0) or 0)),
            "idle_minutes": max(0, int(_trace_value(trace, "idle_minutes", 0) or 0)),
            "attention_target": str(_trace_value(trace, "attention_target", "") or "").strip(),
            "nonverbal_signal": str(_trace_value(trace, "nonverbal_signal", "") or "").strip(),
            "note": summary,
            "source_tags": source_tags,
            "presence_residue": round(_clamp01(_trace_value(trace, "presence_residue", 0.0), 0.0), 3),
            "ambient_resonance": round(_clamp01(_trace_value(trace, "ambient_resonance", 0.0), 0.0), 3),
            "self_activity_momentum": round(_clamp01(_trace_value(trace, "self_activity_momentum", 0.0), 0.0), 3),
            "continuity_anchor": round(_clamp01(_trace_value(trace, "continuity_anchor", 0.0), 0.0), 3),
            "own_rhythm_anchor": round(_clamp01(_trace_value(trace, "own_rhythm_anchor", 0.0), 0.0), 3),
            "recontact_anchor": round(_clamp01(_trace_value(trace, "recontact_anchor", 0.0), 0.0), 3),
            "boundary_anchor": round(_clamp01(_trace_value(trace, "boundary_anchor", 0.0), 0.0), 3),
            "memory_anchor": round(_clamp01(_trace_value(trace, "memory_anchor", 0.0), 0.0), 3),
            "semantic_continuity_depth": round(
                _clamp01(_trace_value(trace, "semantic_continuity_depth", 0.0), 0.0),
                3,
            ),
            "semantic_identity_gravity": round(
                _clamp01(_trace_value(trace, "semantic_identity_gravity", 0.0), 0.0),
                3,
            ),
            "long_term_axis_count": max(0, int(_trace_value(trace, "long_term_axis_count", 0) or 0)),
            "lineage_gravity": round(_clamp01(_trace_value(trace, "lineage_gravity", 0.0), 0.0), 3),
            "contact_lineage": round(_clamp01(_trace_value(trace, "contact_lineage", 0.0), 0.0), 3),
            "repair_lineage": round(_clamp01(_trace_value(trace, "repair_lineage", 0.0), 0.0), 3),
            "boundary_lineage": round(_clamp01(_trace_value(trace, "boundary_lineage", 0.0), 0.0), 3),
            "selfhood_lineage": round(_clamp01(_trace_value(trace, "selfhood_lineage", 0.0), 0.0), 3),
            "agency_lineage": round(_clamp01(_trace_value(trace, "agency_lineage", 0.0), 0.0), 3),
            "own_rhythm_bias": round(_clamp01(_trace_value(trace, "own_rhythm_bias", 0.0), 0.0), 3),
            "recontact_cooldown": round(_clamp01(_trace_value(trace, "recontact_cooldown", 0.0), 0.0), 3),
            "counterpart_scene_bias": str(_trace_value(trace, "counterpart_scene_bias", "") or "").strip().lower(),
            "counterpart_boundary_delta": round(max(-1.0, min(1.0, counterpart_boundary_delta)), 3),
            "created_at": int(_trace_value(trace, "created_at", _now_ts()) or _now_ts()),
        }
        if embodied_context:
            residue["embodied_context"] = embodied_context
        return residue
    return {}


def _long_horizon_interaction_carryover(
    *,
    world_model_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
    counterpart_assessment: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
    response_style_hint: str = "",
) -> InteractionCarryoverPayload:
    current = dict(current_event or {})
    current_kind = str(current.get("kind") or "").strip().lower()
    if current_kind and current_kind != "user_utterance":
        return {}

    hint = str(response_style_hint or current.get("response_style_hint") or "").strip().lower() or "natural"
    snapshot = _agenda_long_horizon_snapshot(
        world_model_state=world_model_state,
        semantic_narrative_profile=semantic_narrative_profile,
    )
    world = dict(world_model_state or {})
    semantic = dict(semantic_narrative_profile or {})
    assessment = dict(counterpart_assessment or {})

    continuity_anchor = _clamp01(snapshot.get("continuity_anchor"), 0.0)
    own_rhythm_anchor = _clamp01(snapshot.get("own_rhythm_anchor"), 0.0)
    recontact_anchor = _clamp01(snapshot.get("recontact_anchor"), 0.0)
    boundary_anchor = _clamp01(snapshot.get("boundary_anchor"), 0.0)
    memory_anchor = _clamp01(snapshot.get("memory_anchor"), 0.0)
    continuity_depth = _clamp01(snapshot.get("semantic_continuity_depth"), 0.0)
    identity_gravity = _clamp01(snapshot.get("semantic_identity_gravity"), 0.0)
    axis_count = max(0, int(snapshot.get("long_term_axis_count") or 0))
    axis_norm = _clamp01(float(axis_count) / 4.0)
    lineage_snapshot = semantic.get("lineage_snapshot") if isinstance(semantic.get("lineage_snapshot"), dict) else {}
    lineage_gravity = max(
        _clamp01(semantic.get("lineage_gravity"), 0.0),
        _clamp01(world.get("lineage_gravity"), 0.0),
    )
    contact_lineage = max(
        _clamp01(world.get("contact_lineage"), 0.0),
        _clamp01(lineage_snapshot.get("bond_style"), 0.0),
        _clamp01(lineage_snapshot.get("presence_style"), 0.0),
        _clamp01(lineage_snapshot.get("commitment_style"), 0.0),
        _clamp01(lineage_snapshot.get("repair_style"), 0.0),
    )
    repair_lineage = max(
        _clamp01(world.get("repair_lineage"), 0.0),
        _clamp01(lineage_snapshot.get("repair_style"), 0.0),
        _clamp01(lineage_snapshot.get("commitment_style"), 0.0),
        _clamp01(lineage_snapshot.get("bond_style"), 0.0),
    )
    boundary_lineage = max(
        _clamp01(world.get("boundary_lineage"), 0.0),
        _clamp01(lineage_snapshot.get("boundary_style"), 0.0),
        _clamp01(lineage_snapshot.get("selfhood_style"), 0.0),
    )
    selfhood_lineage = max(
        _clamp01(world.get("selfhood_lineage"), 0.0),
        _clamp01(lineage_snapshot.get("selfhood_style"), 0.0),
        _clamp01(lineage_snapshot.get("agency_style"), 0.0),
        _clamp01(lineage_snapshot.get("rhythm_style"), 0.0),
    )
    agency_lineage = max(
        _clamp01(world.get("agency_lineage"), 0.0),
        _clamp01(lineage_snapshot.get("agency_style"), 0.0),
        _clamp01(lineage_snapshot.get("rhythm_style"), 0.0),
        _clamp01(lineage_snapshot.get("selfhood_style"), 0.0),
    )

    self_activity_momentum = _clamp01(world.get("self_activity_momentum"), 0.0)
    bond_depth = _clamp01(world.get("bond_depth"), 0.0)
    repair_load = _clamp01(world.get("repair_load"), 0.0)
    tension_load = _clamp01(world.get("tension_load"), 0.0)
    relationship_maturity = _clamp01(world.get("relationship_maturity"), 0.0)
    presence_residue = max(
        _clamp01(world.get("presence_residue"), 0.0),
        _clamp01(semantic.get("presence_carry"), 0.0),
    )
    ambient_resonance = max(
        _clamp01(world.get("ambient_resonance"), 0.0),
        _clamp01(semantic.get("ambient_attunement"), 0.0),
    )
    narrative_bond = _clamp01(semantic.get("bond_depth"), 0.0)
    narrative_repair = _clamp01(semantic.get("repair_residue"), 0.0)
    narrative_tension = _clamp01(semantic.get("tension_residue"), 0.0)
    commitment_carry = _clamp01(semantic.get("commitment_carry"), 0.0)
    stance = str(assessment.get("stance") or "").strip().lower()
    scene = str(assessment.get("scene") or "").strip().lower()
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.0)
    reliability_read = _clamp01(assessment.get("reliability_read"), 0.0)
    respect_level = _clamp01(assessment.get("respect_level"), 0.0)

    guarded_pull = _clamp01(
        0.26 * boundary_anchor
        + 0.16 * boundary_pressure
        + 0.14 * max(narrative_tension, tension_load)
        + 0.10 * continuity_anchor
        + 0.10 * boundary_lineage
        + 0.06 * selfhood_lineage
        + 0.08 * presence_residue
        + 0.04 * lineage_gravity
        + 0.06 * axis_norm
        + (0.08 if stance in {"guarded", "watchful"} else 0.0)
        + (0.08 if scene in {"friction", "relationship_degradation", "boundary_non_compliance"} else 0.0)
    )
    repair_pull = _clamp01(
        0.24 * narrative_repair
        + 0.18 * repair_load
        + 0.14 * recontact_anchor
        + 0.14 * memory_anchor
        + 0.10 * continuity_anchor
        + 0.10 * commitment_carry
        + 0.08 * repair_lineage
        + 0.04 * contact_lineage
        + 0.06 * relationship_maturity
        + 0.06 * reliability_read
        - 0.12 * max(boundary_anchor, boundary_pressure)
        - 0.12 * max(narrative_tension, tension_load)
        + (0.10 if scene == "repair_attempt" else 0.0)
    )
    warm_pull = _clamp01(
        0.24 * narrative_bond
        + 0.18 * bond_depth
        + 0.16 * recontact_anchor
        + 0.12 * presence_residue
        + 0.10 * memory_anchor
        + 0.08 * continuity_anchor
        + 0.08 * relationship_maturity
        + 0.06 * commitment_carry
        + 0.10 * contact_lineage
        + 0.04 * repair_lineage
        + 0.04 * reliability_read
        + 0.04 * respect_level
        - 0.14 * max(boundary_anchor, boundary_pressure)
        - 0.14 * max(narrative_tension, tension_load)
        + (0.06 if stance == "open" else 0.0)
    )

    if max(
        continuity_anchor,
        own_rhythm_anchor,
        recontact_anchor,
        boundary_anchor,
        memory_anchor,
        self_activity_momentum,
        presence_residue,
        bond_depth,
        repair_load,
        narrative_bond,
        narrative_repair,
        contact_lineage,
        agency_lineage,
        boundary_lineage,
        lineage_gravity,
    ) < 0.28:
        return {}

    carryover_mode = ""
    relationship_weather = ""
    source_action_target = ""
    source_primary_motive = ""
    source_motive_tension = ""
    source_goal_frame = ""
    attention_target = ""
    nonverbal_signal = ""
    note = ""
    strength = 0.0

    if (
        guarded_pull >= max(0.58, repair_pull + 0.10, warm_pull + 0.08)
        and own_rhythm_anchor < 0.52
        and (
            stance in {"guarded", "watchful"}
            or boundary_pressure >= 0.22
            or scene in {"friction", "relationship_degradation", "boundary_non_compliance", "repair_attempt"}
        )
    ):
        carryover_mode = "quiet_recontact"
        relationship_weather = "guarded_residue"
        source_action_target = "wait_and_recheck"
        source_primary_motive = "protect_boundary"
        source_motive_tension = "boundary_vs_contact"
        source_goal_frame = "先带着还没完全退掉的边界感接住对方。"
        attention_target = "counterpart_state"
        nonverbal_signal = "quiet_glance"
        note = "长期积累下来的边界感还在，这轮会先收一点。"
        strength = (
            0.18
            + 0.20 * max(boundary_anchor, guarded_pull)
            + 0.14 * continuity_anchor
            + 0.10 * presence_residue
            + 0.08 * axis_norm
        )
    elif (
        repair_pull >= max(0.44, warm_pull + 0.04)
        and own_rhythm_anchor < repair_pull + 0.12
        and (
            scene in {"repair_attempt", "friction", "relationship_degradation"}
            or narrative_repair >= 0.52
            or repair_load >= 0.34
        )
    ):
        carryover_mode = "brief_presence" if stance not in {"guarded"} and boundary_pressure < 0.22 else "quiet_recontact"
        relationship_weather = "repair_residue"
        source_action_target = "confirm_presence" if carryover_mode == "brief_presence" else "wait_and_recheck"
        source_primary_motive = "repair_without_erasing_history"
        source_motive_tension = "repair_vs_distance"
        source_goal_frame = "先带着仍在延续的修复意愿把这轮关系接住。"
        attention_target = "counterpart_state"
        nonverbal_signal = "quiet_notice" if carryover_mode == "brief_presence" else "quiet_glance"
        note = "最近几轮积下来的修复余波还在，这轮不会一下子退回陌生。"
        strength = (
            0.16
            + 0.28 * repair_pull
            + 0.12 * recontact_anchor
            + 0.10 * memory_anchor
            + 0.08 * continuity_anchor
            + 0.06 * axis_norm
        )
    elif (
        warm_pull >= max(0.44, guarded_pull + 0.04)
        and own_rhythm_anchor < warm_pull + 0.10
        and stance not in {"guarded"}
        and max(narrative_tension, tension_load, boundary_pressure) < 0.34
    ):
        carryover_mode = "small_opening" if recontact_anchor >= 0.34 or presence_residue >= 0.24 else "brief_presence"
        relationship_weather = "warm_residue"
        source_action_target = "offer_small_opening" if carryover_mode == "small_opening" else "confirm_presence"
        source_primary_motive = "keep_closeness_alive"
        source_motive_tension = "continuity_vs_distance"
        source_goal_frame = "先顺着长期积累下来的熟悉感把这轮轻轻接回来。"
        attention_target = "counterpart_state" if carryover_mode == "brief_presence" else "self_then_counterpart"
        nonverbal_signal = "brief_notice" if carryover_mode == "brief_presence" else "thought_glance"
        note = "没有明确触发点，但长期积下来的熟悉感会自然留在这轮语气里。"
        strength = (
            0.15
            + 0.26 * warm_pull
            + 0.12 * recontact_anchor
            + 0.10 * memory_anchor
            + 0.08 * continuity_anchor
            + 0.06 * axis_norm
        )
    elif (
        own_rhythm_anchor >= max(0.52, recontact_anchor + 0.08, boundary_anchor + 0.04)
        or (continuity_anchor >= 0.54 and own_rhythm_anchor >= 0.44 and self_activity_momentum >= 0.52)
        or (agency_lineage >= 0.56 and continuity_anchor >= 0.46 and boundary_anchor < 0.54)
    ):
        carryover_mode = "own_rhythm"
        source_action_target = "hold_own_rhythm"
        source_primary_motive = "preserve_self_rhythm"
        source_motive_tension = "self_rhythm_vs_contact"
        source_goal_frame = "先带着自己一路延续下来的节奏接住对方。"
        attention_target = "self_then_counterpart"
        nonverbal_signal = "thought_glance"
        note = "就算没有明确窗口，她也还是带着自己的节奏在回应。"
        strength = (
            0.16
            + 0.34 * own_rhythm_anchor
            + 0.12 * continuity_anchor
            + 0.10 * self_activity_momentum
            + 0.08 * agency_lineage
            + 0.04 * lineage_gravity
            + 0.08 * identity_gravity
            + 0.06 * axis_norm
        )
    elif (
        own_rhythm_anchor >= 0.40
        or (continuity_anchor >= 0.48 and recontact_anchor >= 0.30)
        or (self_activity_momentum >= 0.56 and presence_residue >= 0.24)
        or (agency_lineage >= 0.48 and contact_lineage >= 0.36 and boundary_lineage < 0.52)
    ):
        carryover_mode = "small_opening"
        source_action_target = "offer_small_opening"
        source_primary_motive = "keep_contact_without_dropping_self"
        source_motive_tension = "self_rhythm_vs_contact"
        source_goal_frame = "先顺着自己的节奏留一个小开口。"
        attention_target = "self_then_counterpart"
        nonverbal_signal = "thought_glance"
        note = "没有具体事件催着走，但那种长期形成的节奏会让她先留个小开口。"
        strength = (
            0.14
            + 0.24 * own_rhythm_anchor
            + 0.12 * recontact_anchor
            + 0.10 * continuity_anchor
            + 0.08 * self_activity_momentum
            + 0.06 * presence_residue
            + 0.06 * max(agency_lineage, contact_lineage)
            + 0.05 * axis_norm
        )
    elif (
        recontact_anchor >= 0.38
        or memory_anchor >= 0.42
        or (continuity_anchor >= 0.46 and presence_residue >= 0.22)
        or (contact_lineage >= 0.46 and boundary_lineage < 0.42)
    ):
        carryover_mode = "quiet_recontact"
        source_action_target = "wait_and_recheck"
        source_primary_motive = "gentle_recontact"
        source_motive_tension = "space_vs_contact"
        source_goal_frame = "先顺着长期积累下来的在场感轻一点地重新接近。"
        attention_target = "counterpart_state"
        nonverbal_signal = "quiet_glance" if stance in {"guarded", "watchful"} else "brief_notice"
        note = "虽然没有新鲜余波，但长期积累下来的在场感还在。"
        strength = (
            0.14
            + 0.24 * recontact_anchor
            + 0.16 * memory_anchor
            + 0.10 * continuity_anchor
            + 0.08 * presence_residue
            + 0.06 * contact_lineage
            + 0.04 * axis_norm
        )

    if not carryover_mode:
        return {}

    if not relationship_weather:
        if (
            guarded_pull >= max(0.58, repair_pull + 0.10, warm_pull + 0.08)
            and (
                stance in {"guarded", "watchful"}
                or boundary_pressure >= 0.22
                or scene in {"friction", "relationship_degradation", "boundary_non_compliance"}
            )
        ):
            relationship_weather = "guarded_residue"
        elif repair_pull >= max(0.46, warm_pull + 0.04) and (
            scene in {"repair_attempt", "friction", "relationship_degradation"}
            or narrative_repair >= 0.54
            or repair_load >= 0.36
        ):
            relationship_weather = "repair_residue"
        elif (
            warm_pull >= 0.46
            and stance not in {"guarded"}
            and max(narrative_tension, tension_load, boundary_pressure) < 0.34
        ):
            relationship_weather = "warm_residue"

    if relationship_weather == "guarded_residue" and not note:
        note = "长期积累下来的边界感还在，这轮会先收一点。"
    elif relationship_weather == "repair_residue" and not note:
        note = "前面几轮一点点修回来的感觉还在，这轮不会突然断掉。"
    elif relationship_weather == "warm_residue" and not note:
        note = "长期积累下来的熟悉感还在，这轮语气会自然更近一点。"

    if hint == "structured":
        strength *= 0.35
    elif hint in {"memory_recall", "relationship"}:
        strength *= 0.68

    strength = _clamp01(strength, 0.0)
    if strength < 0.12:
        return {}

    source_tags = ["long_horizon", "semantic_continuity"]
    if own_rhythm_anchor >= 0.40:
        source_tags.append("own_rhythm_anchor")
    if recontact_anchor >= 0.34:
        source_tags.append("recontact_anchor")
    if boundary_anchor >= 0.40:
        source_tags.append("boundary_anchor")
    if memory_anchor >= 0.40:
        source_tags.append("memory_anchor")
    if agency_lineage >= 0.46:
        source_tags.append("agency_lineage")
    if contact_lineage >= 0.46:
        source_tags.append("contact_lineage")
    if boundary_lineage >= 0.46:
        source_tags.append("boundary_lineage")
    if ambient_resonance >= 0.32:
        source_tags.append("ambient_echo")
    if axis_count > 0:
        source_tags.append("long_term_axis")

    return {
        "source_event_kind": "long_horizon:semantic_continuity",
        "source_behavior_mode": "long_horizon_carryover",
        "source_action_target": source_action_target,
        "source_primary_motive": source_primary_motive,
        "source_motive_tension": source_motive_tension,
        "source_goal_frame": source_goal_frame,
        "source_text": "",
        "source_tags": source_tags,
        "carryover_mode": carryover_mode,
        "strength": round(strength, 3),
        "relationship_weather": relationship_weather,
        "idle_minutes": 0,
        "source_turn_gap": 0,
        "attention_target": attention_target,
        "nonverbal_signal": nonverbal_signal,
        "note": note,
        "created_at": _now_ts(),
    }


def _normalized_proactive_continuity_history_item(item: dict[str, Any] | None) -> dict[str, Any]:
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
        "source_event_kind": str(_pick("source_event_kind") or "").strip().lower(),
        "trigger_family": str(_pick("trigger_family") or "").strip().lower(),
        "carryover_mode": str(_pick("carryover_mode") or "").strip().lower(),
        "relationship_weather": str(_pick("relationship_weather") or "").strip().lower(),
        "counterpart_scene_bias": str(_pick("counterpart_scene_bias") or "").strip().lower(),
        "hold_count": max(0, int(_pick("hold_count") or 0)),
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
        "long_term_axis_count": max(0, int(_pick("long_term_axis_count") or 0)),
        "lineage_gravity": _clamp01(_pick("lineage_gravity"), 0.0),
        "contact_lineage": _clamp01(_pick("contact_lineage"), 0.0),
        "repair_lineage": _clamp01(_pick("repair_lineage"), 0.0),
        "boundary_lineage": _clamp01(_pick("boundary_lineage"), 0.0),
        "selfhood_lineage": _clamp01(_pick("selfhood_lineage"), 0.0),
        "agency_lineage": _clamp01(_pick("agency_lineage"), 0.0),
        "primary_motive": str(_pick("primary_motive") or "").strip().lower(),
        "motive_tension": str(_pick("motive_tension") or "").strip().lower(),
        "goal_frame": str(_pick("goal_frame") or "").strip(),
    }
    embodied_context = normalize_embodied_trace_context(row)
    if embodied_context:
        normalized["embodied_context"] = embodied_context
    return normalized


def _proactive_continuity_history_carryover(
    proactive_continuity_history: Any,
    *,
    current_event: dict[str, Any] | None,
    response_style_hint: str,
) -> InteractionCarryoverPayload:
    current = dict(current_event or {})
    current_kind = str(current.get("kind") or "user_utterance").strip().lower()
    if current_kind != "user_utterance" or not isinstance(proactive_continuity_history, list):
        return {}

    hint = str(response_style_hint or "").strip().lower() or "natural"
    mode_defaults: dict[str, tuple[str, str, str, str, str, str]] = {
        "own_rhythm": (
            "agenda_lifecycle",
            "hold_own_rhythm",
            "preserve_self_rhythm",
            "self_rhythm_vs_contact",
            "self_then_counterpart",
            "thought_glance",
        ),
        "quiet_recontact": (
            "agenda_lifecycle",
            "wait_and_recheck",
            "gentle_recontact",
            "space_vs_contact",
            "counterpart_state",
            "quiet_glance",
        ),
        "small_opening": (
            "continuity_recontact",
            "offer_small_opening",
            "gentle_recontact",
            "space_vs_contact",
            "self_then_counterpart",
            "thought_glance",
        ),
        "brief_presence": (
            "continuity_recontact",
            "confirm_presence",
            "confirm_connection",
            "space_vs_contact",
            "counterpart_state",
            "brief_notice",
        ),
        "shared_window": (
            "shared_activity_offer",
            "offer_shared_activity",
            "shared_presence",
            "timing_vs_contact",
            "shared_window",
            "nudge_presence",
        ),
        "task_window": (
            "scheduled_life_nudge",
            "light_work_nudge",
            "shared_task_progress",
            "task_vs_timing",
            "shared_task",
            "focus_glance",
        ),
        "life_window": (
            "scheduled_life_nudge",
            "light_life_nudge",
            "gentle_recontact",
            "space_vs_contact",
            "counterpart_state",
            "quiet_glance",
        ),
    }
    min_strength = {
        "own_rhythm": 0.24,
        "quiet_recontact": 0.20,
        "small_opening": 0.20,
        "brief_presence": 0.18,
        "shared_window": 0.22,
        "task_window": 0.22,
        "life_window": 0.20,
    }

    for raw_item in proactive_continuity_history:
        item = _normalized_proactive_continuity_history_item(raw_item)
        if not item:
            continue
        carryover_mode = str(item.get("carryover_mode") or "").strip().lower()
        defaults = mode_defaults.get(carryover_mode)
        if defaults is None:
            continue

        (
            source_behavior_mode,
            source_action_target,
            default_primary_motive,
            default_motive_tension,
            attention_target,
            nonverbal_signal,
        ) = defaults
        carryover_strength = _clamp01(item.get("carryover_strength"), 0.0)
        own_rhythm_bias = _clamp01(item.get("own_rhythm_bias"), 0.0)
        self_activity_momentum = _clamp01(item.get("self_activity_momentum"), 0.0)
        presence_residue = _clamp01(item.get("presence_residue"), 0.0)
        ambient_resonance = _clamp01(item.get("ambient_resonance"), 0.0)
        recontact_cooldown = _clamp01(item.get("recontact_cooldown"), 0.0)
        hold_count = max(0, int(item.get("hold_count") or 0))
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
        trace_family = str(item.get("trace_family") or "").strip().lower()
        counterpart_scene_bias = str(item.get("counterpart_scene_bias") or "").strip().lower()
        embodied_context = item.get("embodied_context") if isinstance(item.get("embodied_context"), dict) else {}
        embodied_kind = str(embodied_context.get("kind") or "").strip().lower()

        strength = carryover_strength
        if carryover_mode == "own_rhythm":
            strength = max(
                strength,
                0.74 * own_rhythm_bias,
                0.72 * self_activity_momentum,
                0.82 * own_rhythm_anchor,
                0.60 * continuity_anchor,
                0.64 * agency_lineage,
                0.56 * lineage_gravity,
                0.16 + 0.08 * min(3, hold_count),
            )
        elif carryover_mode == "quiet_recontact":
            strength = max(
                strength,
                0.18 + 0.16 * (1.0 - recontact_cooldown),
                0.62 * presence_residue,
                0.74 * recontact_anchor,
                0.58 * continuity_anchor,
                0.52 * memory_anchor,
                0.48 * contact_lineage,
            )
        elif carryover_mode == "small_opening":
            strength = max(
                strength,
                0.64 * presence_residue,
                0.58 * self_activity_momentum,
                0.62 * own_rhythm_anchor,
                0.54 * recontact_anchor,
                0.48 * continuity_anchor,
                0.48 * max(agency_lineage, contact_lineage),
                0.20 + 0.06 * min(3, hold_count),
            )
        elif carryover_mode == "brief_presence":
            strength = max(
                strength,
                0.66 * presence_residue,
                0.44 * ambient_resonance,
                0.60 * recontact_anchor,
                0.42 * memory_anchor,
            )
        else:
            strength = max(
                strength,
                0.52 * presence_residue,
                0.44 * ambient_resonance,
                0.50 * continuity_anchor,
                0.40 * memory_anchor,
            )

        if trace_family == "continuity_recontact":
            strength = max(strength, 0.22 + 0.18 * max(carryover_strength, presence_residue))
        if counterpart_scene_bias == "busy_not_disrespectful":
            strength = max(strength, 0.24 + 0.16 * max(carryover_strength, presence_residue))
        if boundary_lineage >= 0.46 or selfhood_lineage >= 0.46 or boundary_anchor >= 0.44:
            strength = max(strength, 0.18 + 0.18 * max(boundary_lineage, selfhood_lineage, boundary_anchor))
        if long_term_axis_count > 0:
            strength = max(strength, 0.14 + 0.04 * min(4, long_term_axis_count))
        if semantic_continuity_depth >= 0.50 or semantic_identity_gravity >= 0.50:
            strength = max(strength, 0.18 + 0.16 * max(semantic_continuity_depth, semantic_identity_gravity))
        if embodied_kind == "access_request_pending":
            strength = max(strength, 0.16 + 0.16 * max(carryover_strength, continuity_anchor, recontact_anchor))
        elif embodied_kind == "environmental_friction":
            strength = max(strength, 0.14 + 0.14 * max(carryover_strength, boundary_anchor, memory_anchor))
        elif embodied_kind == "embodied_growth":
            strength = max(strength, 0.14 + 0.12 * max(carryover_strength, agency_lineage, contact_lineage))

        if hint == "structured":
            strength *= 0.35
        elif hint in {"memory_recall", "relationship"}:
            strength *= 0.65
        strength = _clamp01(strength, 0.0)
        if strength < float(min_strength.get(carryover_mode, 0.18)):
            continue

        relationship_weather = str(item.get("relationship_weather") or "").strip().lower()
        if not relationship_weather and counterpart_scene_bias == "busy_not_disrespectful" and carryover_mode != "own_rhythm":
            relationship_weather = "warm_residue"

        source_tags = [
            tag
            for tag in dict.fromkeys(
                [
                    "persisted_proactive_history",
                    trace_family,
                    str(item.get("trigger_family") or "").strip().lower(),
                    str(item.get("kind") or "").strip().lower(),
                    carryover_mode,
                    counterpart_scene_bias,
                    "own_rhythm_anchor" if own_rhythm_anchor >= 0.40 else "",
                    "recontact_anchor" if recontact_anchor >= 0.34 else "",
                    "boundary_anchor" if boundary_anchor >= 0.40 else "",
                    "continuity_anchor" if continuity_anchor >= 0.40 else "",
                    "memory_anchor" if memory_anchor >= 0.40 else "",
                    "agency_lineage" if agency_lineage >= 0.46 else "",
                    "contact_lineage" if contact_lineage >= 0.46 else "",
                    "repair_lineage" if repair_lineage >= 0.46 else "",
                    "boundary_lineage" if boundary_lineage >= 0.46 else "",
                    "selfhood_lineage" if selfhood_lineage >= 0.46 else "",
                    "lineage_gravity" if lineage_gravity >= 0.50 else "",
                    "long_term_axis" if long_term_axis_count > 0 else "",
                    f"bodyfx:{embodied_kind}" if embodied_kind else "",
                    "bodyfx:requested_help" if bool(embodied_context.get("requested_help", False)) else "",
                    "bodyfx:friction" if bool(embodied_context.get("environmental_friction", False)) else "",
                    "bodyfx:growth" if bool(embodied_context.get("procedural_growth", False)) else "",
                ]
            )
            if tag
        ]
        payload = {
            "source_event_kind": str(item.get("source_event_kind") or "").strip().lower()
            or f"proactive_continuity:{str(item.get('kind') or '').strip().lower() or carryover_mode}",
            "source_behavior_mode": source_behavior_mode,
            "source_action_target": source_action_target,
            "source_primary_motive": str(item.get("primary_motive") or "").strip().lower() or default_primary_motive,
            "source_motive_tension": str(item.get("motive_tension") or "").strip().lower() or default_motive_tension,
            "source_goal_frame": str(item.get("goal_frame") or "").strip()[:220],
            "source_text": str(item.get("summary") or "").strip()[:180],
            "source_tags": source_tags[:10],
            "carryover_mode": carryover_mode,
            "strength": round(strength, 3),
            "relationship_weather": relationship_weather,
            "idle_minutes": 0,
            "source_turn_gap": 0,
            "attention_target": attention_target,
            "nonverbal_signal": nonverbal_signal,
            "note": str(item.get("summary") or "").strip(),
            "created_at": _now_ts(),
        }
        if embodied_context:
            payload["embodied_context"] = embodied_context
        return payload
    return {}

def _recent_interaction_carryover(
    *,
    prior_current_event: dict[str, Any] | None,
    prior_behavior_action: dict[str, Any] | None,
    prior_agenda_lifecycle_residue: dict[str, Any] | None = None,
    prior_counterpart_assessment: dict[str, Any] | None = None,
    proactive_continuity_history: Any = None,
    recent_events: Any,
    current_event: dict[str, Any] | None,
    response_style_hint: str,
    world_model_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
) -> InteractionCarryoverPayload:
    current = dict(current_event or {})
    current_kind = str(current.get("kind") or "user_utterance").strip().lower()
    if current_kind != "user_utterance":
        return {}

    source_event = dict(prior_current_event or {})
    source_kind = str(source_event.get("kind") or "").strip().lower()
    prior_action = dict(prior_behavior_action or {})
    relational_fallback = _prior_user_exchange_carryover(
        source_event,
        prior_action,
        prior_counterpart_assessment=prior_counterpart_assessment,
        response_style_hint=response_style_hint,
    )
    agenda_fallback = _agenda_lifecycle_carryover(
        prior_agenda_lifecycle_residue,
        current_event=current_event,
    )
    long_horizon_fallback = _long_horizon_interaction_carryover(
        world_model_state=world_model_state,
        semantic_narrative_profile=semantic_narrative_profile,
        counterpart_assessment=prior_counterpart_assessment,
        current_event=current_event,
        response_style_hint=response_style_hint,
    )
    proactive_history_fallback = _proactive_continuity_history_carryover(
        proactive_continuity_history,
        current_event=current_event,
        response_style_hint=response_style_hint,
    )
    source_from_history = False
    user_turn_gap = 0
    if source_kind == "user_utterance" or not source_kind:
        source_event, source_kind, user_turn_gap = _recent_non_user_event_with_gap(recent_events, max_user_turn_gap=3)
        source_from_history = bool(source_event and source_kind)
    if not source_event or not source_kind or source_kind == "user_utterance":
        combined = _prefer_relational_carryover(long_horizon_fallback, relational_fallback)
        combined = _prefer_relational_carryover(proactive_history_fallback, combined)
        return _prefer_relational_carryover(agenda_fallback, combined)

    prior_action = {} if source_from_history else prior_action
    source_behavior_mode = str(prior_action.get("interaction_mode") or "").strip().lower()
    source_action_target = str(prior_action.get("action_target") or "").strip().lower()
    source_primary_motive = str(prior_action.get("primary_motive") or "").strip().lower()
    source_motive_tension = str(prior_action.get("motive_tension") or "").strip().lower()
    source_goal_frame = str(prior_action.get("goal_frame") or "").strip()
    idle_minutes = 0
    try:
        idle_minutes = int(source_event.get("idle_minutes") or 0)
    except Exception:
        idle_minutes = 0
    source_tags = [
        str(item).strip()
        for item in (source_event.get("tags") if isinstance(source_event.get("tags"), list) else [])
        if str(item).strip()
    ]
    hint = str(response_style_hint or "").strip().lower() or "natural"
    if source_from_history:
        implied = _history_source_behavior_hint(source_event)
        source_behavior_mode = str(implied.get("behavior_mode") or source_behavior_mode).strip().lower()
        source_action_target = str(implied.get("action_target") or source_action_target).strip().lower()
    carryover_mode = ""
    strength = 0.0
    attention_target = str(source_event.get("attention_target_hint") or "").strip()
    nonverbal_signal = str(source_event.get("nonverbal_signal_hint") or "").strip()
    relationship_weather = str(source_event.get("relationship_weather") or "").strip().lower()
    note = ""

    if source_kind == "time_idle":
        if source_action_target == "hold_own_rhythm" or source_behavior_mode in {"self_activity_hold", "idle_presence"}:
            carryover_mode = "own_rhythm"
            strength = 0.40 + min(0.18, idle_minutes / 150.0)
            attention_target = "self_then_counterpart"
            nonverbal_signal = "thought_glance"
            note = "前面那段安静还留着一点她自己的节奏。"
        elif source_action_target == "wait_and_recheck":
            carryover_mode = "quiet_recontact"
            strength = 0.30 + min(0.16, idle_minutes / 180.0)
            attention_target = "counterpart_state"
            nonverbal_signal = "quiet_glance"
            note = "刚从安静里抬头时，这轮开口会更轻一点。"
        else:
            carryover_mode = "small_opening"
            strength = 0.28 + min(0.12, idle_minutes / 240.0)
            attention_target = "counterpart_state"
            nonverbal_signal = "brief_notice"
            note = "安静过后，她会先留一个不太张扬的小开口。"
    elif source_kind == "self_activity_state":
        if source_action_target == "hold_own_rhythm":
            carryover_mode = "own_rhythm"
            strength = 0.42
            attention_target = "self_then_counterpart"
            nonverbal_signal = "thought_glance"
            note = "她会先带着自己的节奏接住对方。"
        else:
            carryover_mode = "small_opening"
            strength = 0.36
            attention_target = "self_then_counterpart"
            nonverbal_signal = "thought_glance"
            note = "刚从自己的事情里抬头时，她更像是顺手把话接住。"
    elif source_kind in {"scheduled_checkin_due", "scheduled_life_due"}:
        if source_action_target == "offer_shared_activity":
            carryover_mode = "shared_window"
            strength = 0.32
            attention_target = "shared_window"
            nonverbal_signal = "nudge_presence"
            note = "前面那点还能接着说下去的空当还没完全过去。"
        elif source_action_target == "light_work_nudge" and (
            {"deadline_window", "work_nudge", "task_window", "shared_task"} & {str(item).strip().lower() for item in source_tags}
            or str(source_event.get("trigger_family") or "").strip().lower() == "deadline_window"
        ):
            carryover_mode = "task_window"
            strength = 0.30
            attention_target = "shared_task"
            nonverbal_signal = "focus_glance"
            note = "之前那件事的节点还留在她的注意力里。"
        elif source_action_target in {"light_work_nudge", "light_life_nudge"}:
            carryover_mode = "life_window"
            strength = 0.26
            attention_target = "counterpart_state"
            nonverbal_signal = "quiet_glance"
            note = "前面那点生活上的惦记还留在她心里。"
        elif source_action_target == "wait_and_recheck":
            carryover_mode = "quiet_recontact"
            strength = 0.24
            attention_target = "counterpart_state"
            nonverbal_signal = "quiet_glance"
            note = "刚才没开口的那一下，会让这轮先更轻一点。"
    elif source_kind == "gesture_signal":
        carryover_mode = "brief_presence"
        strength = 0.20
        attention_target = "counterpart_state"
        nonverbal_signal = "brief_notice"
        note = "上一下轻信号留下的在场感还没完全退掉。"
    elif source_kind == "ambient_shift":
        carryover_mode = "ambient_echo"
        strength = 0.22
        attention_target = "ambient_cue"
        nonverbal_signal = "still_presence"
        note = "刚才那点环境变化还在她的感知里。"
    elif source_kind == "scene_observation":
        carryover_mode = "ambient_echo"
        strength = 0.24
        attention_target = "object_then_user"
        nonverbal_signal = "small_notice"
        note = "刚才注意到的小事，还会顺手带进这轮开口里。"

    if not carryover_mode:
        combined = _prefer_relational_carryover(long_horizon_fallback, relational_fallback)
        combined = _prefer_relational_carryover(proactive_history_fallback, combined)
        return _prefer_relational_carryover(agenda_fallback, combined)

    if source_from_history and user_turn_gap > 0:
        if carryover_mode in {"shared_window", "task_window"}:
            strength *= max(0.46, 1.0 - 0.14 * user_turn_gap)
        elif carryover_mode in {"own_rhythm", "small_opening"}:
            strength *= max(0.34, 1.0 - 0.18 * user_turn_gap)
        else:
            strength *= max(0.30, 1.0 - 0.22 * user_turn_gap)

    if hint == "structured":
        strength *= 0.35
    elif hint in {"memory_recall", "relationship"}:
        strength *= 0.65
    strength = _clamp01(strength, 0.0)
    if strength < 0.12:
        return relational_fallback

    derived = {
        "source_event_kind": source_kind,
        "source_behavior_mode": source_behavior_mode,
        "source_action_target": source_action_target,
        "source_primary_motive": source_primary_motive,
        "source_motive_tension": source_motive_tension,
        "source_goal_frame": source_goal_frame,
        "source_text": str(source_event.get("effective_text") or source_event.get("text") or "").strip()[:180],
        "source_tags": source_tags[:6],
        "carryover_mode": carryover_mode,
        "strength": round(strength, 3),
        "relationship_weather": relationship_weather,
        "idle_minutes": max(0, idle_minutes),
        "attention_target": attention_target,
        "nonverbal_signal": nonverbal_signal,
        "note": note,
        "source_turn_gap": max(0, int(user_turn_gap)),
        "created_at": _now_ts(),
    }
    combined = _prefer_relational_carryover(derived, relational_fallback)
    return _prefer_relational_carryover(agenda_fallback, combined)


def _agenda_lifecycle_carryover(
    residue: dict[str, Any] | None,
    *,
    current_event: dict[str, Any] | None,
) -> AgendaLifecycleResiduePayload | InteractionCarryoverPayload:
    current = dict(current_event or {})
    if str(current.get("kind") or "").strip().lower() != "user_utterance":
        return {}
    payload = dict(residue or {})
    kind = str(payload.get("kind") or "").strip().lower()
    carryover_mode = str(payload.get("carryover_mode") or "").strip().lower()
    strength = _clamp01(payload.get("carryover_strength"), 0.0)
    if not kind or not carryover_mode or strength < 0.12:
        return {}
    embodied_context = normalize_embodied_context(payload.get("embodied_context"))
    note = _embodied_aware_summary(str(payload.get("note") or "").strip(), embodied_context)
    source_tags = [
        str(item).strip().lower()
        for item in (payload.get("source_tags") if isinstance(payload.get("source_tags"), list) else [])
        if str(item).strip()
    ]
    source_tags = list(
        dict.fromkeys(
            [
                *source_tags,
                f"bodyfx:{str(embodied_context.get('kind') or '').strip().lower()}" if embodied_context else "",
                "bodyfx:requested_help" if bool(embodied_context.get("requested_help", False)) else "",
                "bodyfx:friction" if bool(embodied_context.get("environmental_friction", False)) else "",
                "bodyfx:growth" if bool(embodied_context.get("procedural_growth", False)) else "",
            ]
        )
    )
    result: InteractionCarryoverPayload = {
        "source_event_kind": f"agenda_lifecycle:{kind}",
        "source_behavior_mode": "agenda_lifecycle",
        "source_action_target": "hold_own_rhythm" if carryover_mode == "own_rhythm" else "wait_and_recheck",
        "source_primary_motive": "preserve_self_rhythm" if carryover_mode == "own_rhythm" else "gentle_recontact",
        "source_motive_tension": "self_rhythm_vs_contact" if carryover_mode == "own_rhythm" else "space_vs_contact",
        "source_goal_frame": note,
        "source_text": note[:180],
        "source_tags": source_tags,
        "carryover_mode": carryover_mode,
        "strength": round(strength, 3),
        "relationship_weather": str(payload.get("relationship_weather") or "").strip().lower(),
        "idle_minutes": max(0, int(payload.get("idle_minutes") or 0)),
        "source_turn_gap": 0,
        "attention_target": str(payload.get("attention_target") or "").strip() or "self_then_counterpart",
        "nonverbal_signal": str(payload.get("nonverbal_signal") or "").strip() or "thought_glance",
        "note": note,
        "created_at": int(payload.get("created_at") or _now_ts()),
    }
    if embodied_context:
        result["embodied_context"] = embodied_context
    return result
def _apply_agenda_lifecycle_residue_to_runtime_state(
    *,
    agenda_lifecycle_residue: dict[str, Any] | None,
    world_model_state: dict[str, Any] | None,
    counterpart_assessment: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    residue = dict(agenda_lifecycle_residue or {})
    if not residue:
        return dict(world_model_state or {}), dict(counterpart_assessment or {})
    kind = str(residue.get("kind") or "").strip().lower()
    if kind not in {"held", "released_to_self_activity", "dropped", "expired"}:
        return dict(world_model_state or {}), dict(counterpart_assessment or {})

    world = dict(world_model_state or {})
    assessment = dict(counterpart_assessment or {})
    own_rhythm_bias = max(
        _clamp01(residue.get("own_rhythm_bias"), 0.0),
        _clamp01(residue.get("self_activity_momentum"), 0.0),
    )
    presence_residue = _clamp01(residue.get("presence_residue"), 0.0)
    ambient_resonance = _clamp01(residue.get("ambient_resonance"), 0.0)
    cooldown = _clamp01(residue.get("recontact_cooldown"), 0.0)
    continuity_anchor = _clamp01(residue.get("continuity_anchor"), 0.0)
    own_rhythm_anchor = _clamp01(residue.get("own_rhythm_anchor"), 0.0)
    recontact_anchor = _clamp01(residue.get("recontact_anchor"), 0.0)
    boundary_anchor = _clamp01(residue.get("boundary_anchor"), 0.0)
    memory_anchor = _clamp01(residue.get("memory_anchor"), 0.0)
    lineage_gravity = _clamp01(residue.get("lineage_gravity"), 0.0)
    contact_lineage = _clamp01(residue.get("contact_lineage"), 0.0)
    repair_lineage = _clamp01(residue.get("repair_lineage"), 0.0)
    boundary_lineage = _clamp01(residue.get("boundary_lineage"), 0.0)
    selfhood_lineage = _clamp01(residue.get("selfhood_lineage"), 0.0)
    agency_lineage = _clamp01(residue.get("agency_lineage"), 0.0)

    if kind == "released_to_self_activity":
        lineage_scale = 0.92
        contact_scale = 0.74
        repair_scale = 0.78
        boundary_scale = 0.86
        selfhood_scale = 0.90
        agency_scale = 0.94
    elif kind == "held":
        lineage_scale = 0.88
        contact_scale = 0.84 if str(residue.get("carryover_mode") or "").strip().lower() != "own_rhythm" else 0.72
        repair_scale = 0.82
        boundary_scale = 0.88
        selfhood_scale = 0.84
        agency_scale = 0.86
    else:
        lineage_scale = 0.76
        contact_scale = 0.68
        repair_scale = 0.72
        boundary_scale = 0.80
        selfhood_scale = 0.78
        agency_scale = 0.84

    world["self_activity_momentum"] = round(max(_clamp01(world.get("self_activity_momentum"), 0.0), own_rhythm_bias), 3)
    world["presence_residue"] = round(
        max(
            _clamp01(world.get("presence_residue"), 0.0),
            presence_residue * (0.92 if kind == "released_to_self_activity" else 0.82 if kind == "held" else 0.72),
        ),
        3,
    )
    world["ambient_resonance"] = round(max(_clamp01(world.get("ambient_resonance"), 0.0), 0.88 * ambient_resonance), 3)
    world["memory_gravity"] = round(
        max(
            _clamp01(world.get("memory_gravity"), 0.0),
            0.74 * memory_anchor,
            0.58 * continuity_anchor,
        ),
        3,
    )
    world["relationship_maturity"] = round(
        max(
            _clamp01(world.get("relationship_maturity"), 0.0),
            0.64 * continuity_anchor,
        ),
        3,
    )
    world["lineage_gravity"] = round(
        max(
            _clamp01(world.get("lineage_gravity"), 0.0),
            lineage_scale * max(lineage_gravity, 0.82 * max(contact_lineage, boundary_lineage, agency_lineage, selfhood_lineage, repair_lineage)),
        ),
        3,
    )
    world["contact_lineage"] = round(
        max(
            _clamp01(world.get("contact_lineage"), 0.0),
            contact_scale * max(contact_lineage, 0.72 * recontact_anchor),
        ),
        3,
    )
    world["repair_lineage"] = round(
        max(
            _clamp01(world.get("repair_lineage"), 0.0),
            repair_scale * max(repair_lineage, 0.66 * recontact_anchor),
        ),
        3,
    )
    world["boundary_lineage"] = round(
        max(
            _clamp01(world.get("boundary_lineage"), 0.0),
            boundary_scale * max(boundary_lineage, 0.74 * boundary_anchor),
        ),
        3,
    )
    world["selfhood_lineage"] = round(
        max(
            _clamp01(world.get("selfhood_lineage"), 0.0),
            selfhood_scale * max(selfhood_lineage, 0.66 * boundary_anchor),
        ),
        3,
    )
    world["agency_lineage"] = round(
        max(
            _clamp01(world.get("agency_lineage"), 0.0),
            agency_scale * max(agency_lineage, 0.78 * own_rhythm_anchor),
        ),
        3,
    )
    boundary_load = _clamp01(world.get("boundary_load"), 0.0)
    if kind == "released_to_self_activity":
        boundary_load = max(boundary_load, 0.08 + 0.10 * cooldown + 0.06 * boundary_anchor)
    else:
        boundary_load = max(boundary_load, 0.12 + 0.18 * cooldown + 0.08 * boundary_anchor)
    world["boundary_load"] = round(_clamp01(boundary_load), 3)

    if assessment:
        scene_bias = str(residue.get("counterpart_scene_bias") or "").strip().lower()
        stance = str(assessment.get("stance") or "").strip().lower()
        if scene_bias and stance != "guarded":
            assessment["scene"] = scene_bias
        boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1) + float(residue.get("counterpart_boundary_delta") or 0.0)
        if boundary_lineage >= 0.44 or selfhood_lineage >= 0.44:
            boundary_pressure = max(boundary_pressure, 0.14 + 0.12 * max(boundary_lineage, selfhood_lineage))
        assessment["boundary_pressure"] = round(_clamp01(boundary_pressure), 3)
        if scene_bias == "busy_not_disrespectful":
            assessment["reliability_read"] = round(
                max(_clamp01(assessment.get("reliability_read"), 0.5), 0.52 + 0.06 * max(contact_lineage, 0.72 * recontact_anchor)),
                3,
            )
            assessment["respect_level"] = round(
                max(_clamp01(assessment.get("respect_level"), 0.5), 0.52 + 0.04 * max(contact_lineage, 0.64 * continuity_anchor)),
                3,
            )
        elif boundary_lineage >= 0.48 and stance == "open":
            assessment["stance"] = "watchful"
            assessment["reliability_read"] = round(min(_clamp01(assessment.get("reliability_read"), 0.5), 0.66), 3)

    return world, assessment

def _prefer_relational_carryover(
    derived: InteractionCarryoverPayload | dict[str, Any] | None,
    relational_fallback: InteractionCarryoverPayload | dict[str, Any] | None,
) -> InteractionCarryoverPayload:
    fallback = dict(relational_fallback or {})
    base = dict(derived or {})
    if not fallback:
        return base
    if not base:
        return fallback

    fallback_weather = str(fallback.get("relationship_weather") or "").strip().lower()
    fallback_strength = _clamp01(fallback.get("strength"), 0.0)
    base_strength = _clamp01(base.get("strength"), 0.0)
    base_mode = str(base.get("carryover_mode") or "").strip().lower()

    if fallback_weather == "guarded_residue":
        # Fresh guardedness from the last user exchange should usually dominate
        # older background nudges; otherwise the system feels like it "forgets"
        # being upset as soon as another soft residue exists.
        if base_mode == "own_rhythm" and base_strength >= fallback_strength + 0.10:
            merged = dict(base)
            merged["relationship_weather"] = fallback_weather
            merged["strength"] = round(max(base_strength, fallback_strength), 3)
            merged["note"] = str(fallback.get("note") or merged.get("note") or "").strip()
            return merged
        return fallback

    if fallback_weather in {"warm_residue", "repair_residue"}:
        if fallback_strength >= base_strength + 0.08:
            return fallback
        merged = dict(base)
        merged["relationship_weather"] = fallback_weather
        if not str(merged.get("note") or "").strip():
            merged["note"] = str(fallback.get("note") or "").strip()
        return merged

    if fallback_strength > base_strength + 0.08:
        return fallback
    return base

def _prior_user_exchange_carryover(
    source_event: dict[str, Any] | None,
    prior_action: dict[str, Any] | None,
    *,
    prior_counterpart_assessment: dict[str, Any] | None = None,
    response_style_hint: str,
) -> InteractionCarryoverPayload:
    event = dict(source_event or {})
    if str(event.get("kind") or "").strip().lower() != "user_utterance":
        return {}
    action = dict(prior_action or {})
    if not action:
        return {}
    hint = str(response_style_hint or "").strip().lower() or "natural"
    if hint in {"structured", "memory_recall"}:
        return {}

    source_text = str(event.get("effective_text") or event.get("text") or "").strip()
    source_tags = {
        str(item).strip().lower()
        for item in (event.get("tags") if isinstance(event.get("tags"), list) else [])
        if str(item).strip()
    }
    interaction_mode = str(action.get("interaction_mode") or "").strip().lower()
    approach_style = str(action.get("approach_style") or "").strip().lower()
    affect_surface = str(action.get("affect_surface") or "").strip().lower()
    followup_intent = str(action.get("followup_intent") or "").strip().lower()
    disclosure_posture = str(action.get("disclosure_posture") or "").strip().lower()
    attention_target = str(action.get("attention_target") or "").strip() or "counterpart_state"
    nonverbal_signal = str(action.get("nonverbal_signal") or "").strip()
    primary_motive = str(action.get("primary_motive") or "").strip().lower()
    motive_tension = str(action.get("motive_tension") or "").strip().lower()
    goal_frame = str(action.get("goal_frame") or "").strip()
    initiative_level = _clamp01(action.get("initiative_level"), 0.0)
    engagement_level = _clamp01(action.get("engagement_level"), 0.0)
    assessment = dict(prior_counterpart_assessment or {})
    prior_stance = str(assessment.get("stance") or "").strip().lower()
    prior_scene = str(assessment.get("scene") or "").strip().lower()
    prior_boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.0)
    base_strength = max(initiative_level, 0.72 * engagement_level)
    explicit_repair_context = bool(
        prior_scene == "repair_attempt"
        or "repair" in source_tags
        or re.search(r"(道歉|说开|原谅|和好|别冷掉|正常回我|别装成陌生人|不在走流程|不是在走流程)", source_text)
    )
    open_repair_relational_residue = bool(
        explicit_repair_context
        and interaction_mode == "relationship_sensitive"
        and prior_stance not in {"guarded", "watchful"}
        and prior_boundary_pressure < 0.16
        and affect_surface in {"warm", "tender", "mixed"}
        and followup_intent in {"soft", "active"}
    )
    guarded_brief_presence = bool(
        interaction_mode == "brief_presence"
        and (
            prior_stance in {"guarded", "watchful"}
            or prior_scene in {"friction", "relationship_degradation", "boundary_non_compliance", "repair_attempt"}
            or prior_boundary_pressure >= 0.18
            or motive_tension in {"space_vs_contact", "boundary_vs_closeness", "care_vs_guard"}
        )
    )
    guarded_relational_residue = bool(
        interaction_mode == "relationship_sensitive"
        and (
            prior_stance in {"guarded", "watchful"}
            or (
                str(action.get("action_target") or "").strip().lower() == "protect_relationship_boundary"
                and (prior_boundary_pressure >= 0.16 or prior_scene in {"relationship_degradation", "boundary_non_compliance", "friction"})
            )
        )
    )

    if (
        approach_style == "guarded"
        or (disclosure_posture == "guarded" and interaction_mode != "brief_presence" and not open_repair_relational_residue)
        or affect_surface == "cool"
        or guarded_relational_residue
        or guarded_brief_presence
    ):
        strength = _clamp01(
            0.18
            + 0.14 * base_strength
            + (0.08 if disclosure_posture == "guarded" and interaction_mode != "brief_presence" else 0.0)
            + (0.06 if followup_intent == "none" else 0.0)
            + (0.04 if prior_stance == "guarded" else 0.0)
        )
        if strength < 0.16:
            return {}
        return {
            "source_event_kind": "user_utterance",
            "source_behavior_mode": interaction_mode,
            "source_action_target": str(action.get("action_target") or "").strip().lower(),
            "source_primary_motive": primary_motive,
            "source_motive_tension": motive_tension,
            "source_goal_frame": goal_frame,
            "source_text": str(event.get("effective_text") or event.get("text") or "").strip()[:180],
            "source_tags": [],
            "carryover_mode": "quiet_recontact",
            "strength": round(strength, 3),
            "relationship_weather": "guarded_residue",
            "idle_minutes": 0,
            "source_turn_gap": 0,
            "attention_target": "counterpart_state",
            "nonverbal_signal": nonverbal_signal or "quiet_glance",
            "note": "上一轮那点情绪还没完全退掉，这轮会先收一点。",
            "created_at": _now_ts(),
        }

    if (
        interaction_mode in {"low_pressure_support", "relationship_sensitive", "companion_reply", "shared_memory", "brief_presence"}
        and affect_surface in {"warm", "tender", "mixed"}
        and followup_intent in {"soft", "active"}
    ):
        if interaction_mode == "relationship_sensitive" and not explicit_repair_context:
            return {}
        weather = "repair_residue" if interaction_mode == "relationship_sensitive" else "warm_residue"
        strength = _clamp01(
            0.16
            + 0.16 * base_strength
            + (0.06 if affect_surface in {"warm", "tender"} else 0.0)
            + (0.04 if followup_intent == "active" else 0.0)
        )
        if strength < 0.16:
            return {}
        return {
            "source_event_kind": "user_utterance",
            "source_behavior_mode": interaction_mode,
            "source_action_target": str(action.get("action_target") or "").strip().lower(),
            "source_primary_motive": primary_motive,
            "source_motive_tension": motive_tension,
            "source_goal_frame": goal_frame,
            "source_text": str(event.get("effective_text") or event.get("text") or "").strip()[:180],
            "source_tags": [],
            "carryover_mode": "brief_presence" if weather == "repair_residue" else "small_opening",
            "strength": round(strength, 3),
            "relationship_weather": weather,
            "idle_minutes": 0,
            "source_turn_gap": 0,
            "attention_target": "counterpart_state",
            "nonverbal_signal": nonverbal_signal or ("quiet_notice" if weather == "repair_residue" else "brief_notice"),
            "note": "上一轮留下来的那点感觉还在，这轮不会一下子退回陌生。",
            "created_at": _now_ts(),
        }
    return {}

def _seeded_interaction_carryover_from_state(
    *,
    state: ThreadState,
    prior_current_event: dict[str, Any] | None,
    prior_behavior_action: dict[str, Any] | None,
    seed_world_model_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
    counterpart_assessment: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
    response_style_hint: str = "",
) -> dict[str, Any]:
    if isinstance(prior_current_event, dict) and prior_current_event:
        return {}
    if isinstance(prior_behavior_action, dict) and prior_behavior_action:
        return {}
    seeded = state.get("interaction_carryover") if isinstance(state.get("interaction_carryover"), dict) else {}
    long_horizon_fallback = _long_horizon_interaction_carryover(
        world_model_state=seed_world_model_state
        if isinstance(seed_world_model_state, dict)
        else state.get("world_model_state")
        if isinstance(state.get("world_model_state"), dict)
        else None,
        semantic_narrative_profile=semantic_narrative_profile
        if isinstance(semantic_narrative_profile, dict)
        else state.get("semantic_narrative_profile")
        if isinstance(state.get("semantic_narrative_profile"), dict)
        else None,
        counterpart_assessment=counterpart_assessment
        if isinstance(counterpart_assessment, dict)
        else state.get("counterpart_assessment")
        if isinstance(state.get("counterpart_assessment"), dict)
        else None,
        current_event=current_event,
        response_style_hint=response_style_hint,
    )
    if not seeded:
        return long_horizon_fallback
    carryover_mode = str(seeded.get("carryover_mode") or "").strip().lower()
    strength = _clamp01(seeded.get("strength"), 0.0)
    if not carryover_mode or strength < 0.12:
        return long_horizon_fallback
    out: dict[str, Any] = {
        "source_event_kind": str(seeded.get("source_event_kind") or "seed_state").strip().lower() or "seed_state",
        "source_behavior_mode": str(seeded.get("source_behavior_mode") or "").strip().lower(),
        "source_action_target": str(seeded.get("source_action_target") or "").strip().lower(),
        "source_primary_motive": str(seeded.get("source_primary_motive") or "").strip().lower(),
        "source_motive_tension": str(seeded.get("source_motive_tension") or "").strip().lower(),
        "source_goal_frame": str(seeded.get("source_goal_frame") or "").strip(),
        "source_text": str(seeded.get("source_text") or "").strip()[:180],
        "source_tags": [
            str(item).strip()
            for item in (seeded.get("source_tags") if isinstance(seeded.get("source_tags"), list) else [])
            if str(item).strip()
        ],
        "carryover_mode": carryover_mode,
        "strength": round(strength, 3),
        "relationship_weather": str(seeded.get("relationship_weather") or "").strip().lower(),
        "idle_minutes": max(0, int(seeded.get("idle_minutes") or 0)),
        "source_turn_gap": max(0, int(seeded.get("source_turn_gap") or 0)),
        "attention_target": str(seeded.get("attention_target") or "").strip().lower(),
        "nonverbal_signal": str(seeded.get("nonverbal_signal") or "").strip().lower(),
        "note": str(seeded.get("note") or "").strip(),
        "created_at": int(seeded.get("created_at") or _now_ts()),
    }
    cleaned: dict[str, Any] = {}
    for key, value in out.items():
        if value is None:
            continue
        if isinstance(value, str) and not value:
            continue
        if isinstance(value, list) and not value:
            continue
        cleaned[key] = value
    return cleaned

