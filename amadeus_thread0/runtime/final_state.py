from __future__ import annotations

from typing import Any

from ..graph_parts.action_packets import (
    normalize_action_packet,
    normalize_action_packets,
)
from ..graph_parts.autonomy_runtime import (
    autonomy_intent_has_signal,
    normalize_autonomy_intent,
    refresh_autonomy_intent_from_packets,
)
from ..graph_parts.behavior_runtime import _behavior_plan_from_action
from ..graph_parts.digital_body_runtime import (
    digital_body_state_has_signal,
    normalize_digital_body_state,
    normalize_embodied_context,
)
from ..evolution_engine.reconsolidation import derive_digital_body_consequence
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
    if isinstance(window_profile, dict) and bool(window_profile):
        return True
    embodied_context = _normalize_digital_body_consequence(_dict_or_empty(action.get("embodied_context")))
    return digital_body_consequence_has_signal(embodied_context)


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
    embodied_context = _normalize_digital_body_consequence(_dict_or_empty(plan.get("embodied_context")))
    return digital_body_consequence_has_signal(embodied_context)


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
    if isinstance(value, (int, float)) and float(value) != 0.0:
        return True
    embodied_context = _normalize_digital_body_consequence(_dict_or_empty(carryover.get("embodied_context")))
    return digital_body_consequence_has_signal(embodied_context)


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
    embodied_context = _normalize_digital_body_consequence(_dict_or_empty(residue.get("embodied_context")))
    return digital_body_consequence_has_signal(embodied_context)


def action_packets_have_signal(action_packets: Any) -> bool:
    return bool(normalize_action_packets(action_packets))


def action_trace_has_signal(action_trace: Any) -> bool:
    if not isinstance(action_trace, list) or not action_trace:
        return False
    for item in action_trace:
        if not isinstance(item, dict):
            continue
        if any(
            (
                str(item.get("proposal_id") or "").strip(),
                str(item.get("status") or "").strip(),
                str(item.get("event") or "").strip(),
            )
        ):
            return True
    return False


def autonomy_block_reason_has_signal(value: Any) -> bool:
    return bool(str(value or "").strip())


def _reconsolidation_behavior_action(reconsolidation_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    recon = _dict_or_empty(reconsolidation_snapshot)
    action = _normalized_behavior_action(_dict_or_empty(recon.get("behavior_action")))
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
    plan = _normalized_behavior_plan(_dict_or_empty(recon.get("behavior_plan")))
    return plan if behavior_plan_has_signal(plan) else {}


def _normalized_behavior_action(action: dict[str, Any] | None) -> dict[str, Any]:
    row = _dict_or_empty(action)
    if not row:
        return {}
    normalized = dict(row)
    embodied_context = _normalize_digital_body_consequence(_dict_or_empty(row.get("embodied_context")))
    if digital_body_consequence_has_signal(embodied_context):
        normalized["embodied_context"] = embodied_context
    else:
        normalized.pop("embodied_context", None)
    return normalized if behavior_action_has_signal(normalized) else {}


def _normalized_behavior_plan(plan: dict[str, Any] | None) -> dict[str, Any]:
    row = _dict_or_empty(plan)
    if not row:
        return {}
    normalized = dict(row)
    embodied_context = _normalize_digital_body_consequence(_dict_or_empty(row.get("embodied_context")))
    if digital_body_consequence_has_signal(embodied_context):
        normalized["embodied_context"] = embodied_context
    else:
        normalized.pop("embodied_context", None)
    return normalized if behavior_plan_has_signal(normalized) else {}


def _reconsolidation_interaction_carryover(reconsolidation_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    recon = _dict_or_empty(reconsolidation_snapshot)
    return _normalized_interaction_carryover(recon.get("interaction_carryover"))


def _reconsolidation_counterpart_assessment(reconsolidation_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    recon = _dict_or_empty(reconsolidation_snapshot)
    counterpart = _dict_or_empty(recon.get("counterpart"))
    return _normalized_counterpart_assessment(counterpart)


def _reconsolidation_agenda_lifecycle(reconsolidation_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    recon = _dict_or_empty(reconsolidation_snapshot)
    residue = _normalized_agenda_lifecycle(_dict_or_empty(recon.get("agenda_lifecycle_consequence")))
    return residue if agenda_lifecycle_has_signal(residue) else {}


def _normalized_agenda_lifecycle(residue: dict[str, Any] | None) -> dict[str, Any]:
    row = _dict_or_empty(residue)
    if not row:
        return {}
    normalized = dict(row)
    if isinstance(row.get("source_tags"), list):
        normalized["source_tags"] = [
            str(item).strip()
            for item in _list_or_empty(row.get("source_tags"))
            if str(item or "").strip()
        ][:12]
    embodied_context = _normalize_digital_body_consequence(_dict_or_empty(row.get("embodied_context")))
    if digital_body_consequence_has_signal(embodied_context):
        normalized["embodied_context"] = embodied_context
    else:
        normalized.pop("embodied_context", None)
    return normalized if agenda_lifecycle_has_signal(normalized) else {}


def _reconsolidation_autonomy_intent(reconsolidation_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    recon = _dict_or_empty(reconsolidation_snapshot)
    intent = normalize_autonomy_intent(recon.get("autonomy_intent"))
    return intent if autonomy_intent_has_signal(intent) else {}


def _reconsolidation_action_packets(reconsolidation_snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    recon = _dict_or_empty(reconsolidation_snapshot)
    return normalize_action_packets(recon.get("action_packets"))


def _reconsolidation_action_trace(reconsolidation_snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    recon = _dict_or_empty(reconsolidation_snapshot)
    trace = recon.get("action_trace")
    if not isinstance(trace, list):
        return []
    return [dict(item) for item in trace if isinstance(item, dict)]


def _reconsolidation_autonomy_block_reason(reconsolidation_snapshot: dict[str, Any] | None) -> str:
    recon = _dict_or_empty(reconsolidation_snapshot)
    return str(recon.get("autonomy_block_reason") or "").strip()


def _reconsolidation_digital_body_state(reconsolidation_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    recon = _dict_or_empty(reconsolidation_snapshot)
    body = normalize_digital_body_state(recon.get("digital_body_state"))
    return body if digital_body_state_has_signal(body) else {}


def digital_body_consequence_has_signal(consequence: dict[str, Any] | None) -> bool:
    if not isinstance(consequence, dict) or not consequence:
        return False
    return any(
        (
            str(consequence.get("kind") or "").strip(),
            str(consequence.get("summary") or "").strip(),
            bool(consequence.get("procedural_growth", False)),
            bool(consequence.get("environmental_friction", False)),
            bool(consequence.get("requested_help", False)),
            isinstance(consequence.get("missing_access"), list) and bool(consequence.get("missing_access")),
            isinstance(consequence.get("requested_access"), list) and bool(consequence.get("requested_access")),
            isinstance(consequence.get("granted_toolsets"), list) and bool(consequence.get("granted_toolsets")),
            isinstance(consequence.get("active_tools"), list) and bool(consequence.get("active_tools")),
            str(consequence.get("block_reason") or "").strip(),
            int(consequence.get("retry_after_s") or 0) > 0,
            str(consequence.get("cooldown_scope") or "").strip(),
            str(consequence.get("session_continuity") or "").strip(),
            int(consequence.get("session_expires_in_s") or 0) > 0,
            str(consequence.get("session_recovery_mode") or "").strip(),
            str(consequence.get("artifact_continuity") or "").strip(),
            str(consequence.get("active_artifact_kind") or "").strip(),
            str(consequence.get("active_artifact_ref") or "").strip(),
            str(consequence.get("active_artifact_label") or "").strip(),
            int(consequence.get("artifact_age_s") or 0) > 0,
            str(consequence.get("artifact_reacquisition_mode") or "").strip(),
            str(consequence.get("artifact_mutation_mode") or "").strip(),
            str(consequence.get("artifact_carrier") or "").strip(),
            isinstance(consequence.get("artifact_source_ref_ids"), list) and bool(consequence.get("artifact_source_ref_ids")),
            int(consequence.get("preferred_source_ref_id") or 0) > 0,
            str(consequence.get("preferred_anchor_reason") or "").strip(),
            str(consequence.get("artifact_source_url") or "").strip(),
            str(consequence.get("artifact_source_query") or "").strip(),
            str(consequence.get("artifact_source_title") or "").strip(),
            str(consequence.get("artifact_source_tool_name") or "").strip(),
            str(consequence.get("workspace_root") or "").strip(),
            isinstance(consequence.get("access_acquire_proposals"), list) and bool(consequence.get("access_acquire_proposals")),
            isinstance(consequence.get("selected_access_proposal"), dict) and bool(consequence.get("selected_access_proposal")),
            isinstance(consequence.get("session_state"), dict) and bool(consequence.get("session_state")),
            isinstance(consequence.get("account_state_detail"), dict) and bool(consequence.get("account_state_detail")),
            isinstance(consequence.get("quota_state_detail"), dict) and bool(consequence.get("quota_state_detail")),
            isinstance(consequence.get("permission_state"), dict) and bool(consequence.get("permission_state")),
            isinstance(consequence.get("sandbox_state"), dict) and bool(consequence.get("sandbox_state")),
            isinstance(consequence.get("skill_effects"), list) and bool(consequence.get("skill_effects")),
        )
    )


def _normalize_digital_body_consequence(consequence: dict[str, Any] | None) -> dict[str, Any]:
    normalized = normalize_embodied_context(consequence)
    return normalized if digital_body_consequence_has_signal(normalized) else {}


def _normalized_interaction_carryover(carryover: dict[str, Any] | None) -> dict[str, Any]:
    row = _dict_or_empty(carryover)
    if not row:
        return {}
    normalized = dict(row)
    if isinstance(row.get("source_tags"), list):
        normalized["source_tags"] = [
            str(item).strip()
            for item in _list_or_empty(row.get("source_tags"))
            if str(item or "").strip()
        ][:12]
    embodied_context = _normalize_digital_body_consequence(_dict_or_empty(row.get("embodied_context")))
    if digital_body_consequence_has_signal(embodied_context):
        normalized["embodied_context"] = embodied_context
    else:
        normalized.pop("embodied_context", None)
    return normalized if interaction_carryover_has_signal(normalized) else {}


def _reconsolidation_digital_body_consequence(reconsolidation_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    recon = _dict_or_empty(reconsolidation_snapshot)
    consequence = _normalize_digital_body_consequence(recon.get("digital_body_consequence"))
    return consequence if digital_body_consequence_has_signal(consequence) else {}


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
    raw_live_plan = _dict_or_empty(behavior_plan)
    mergeable_live_plan = dict(raw_live_plan)
    embodied_context = _normalize_digital_body_consequence(_dict_or_empty(mergeable_live_plan.get("embodied_context")))
    if digital_body_consequence_has_signal(embodied_context):
        mergeable_live_plan["embodied_context"] = embodied_context
    else:
        mergeable_live_plan.pop("embodied_context", None)
    live_action = _normalized_behavior_action(behavior_action)
    live_plan = _normalized_behavior_plan(raw_live_plan)
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
    merge_base = plan if plan else mergeable_live_plan
    if not merge_base:
        return action, dict(derived_plan)
    merged_plan = dict(derived_plan)
    merged_plan.update(merge_base)
    return action, merged_plan


def resolve_interaction_carryover(
    *,
    interaction_carryover: dict[str, Any] | None,
    reconsolidation_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    live_carryover = _normalized_interaction_carryover(interaction_carryover)
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
    live_residue = _normalized_agenda_lifecycle(agenda_lifecycle_residue)
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


def resolve_autonomy_intent(
    *,
    autonomy_intent: dict[str, Any] | None,
    reconsolidation_snapshot: dict[str, Any] | None = None,
    action_packets: Any = None,
    current_event: dict[str, Any] | None = None,
    autonomy_block_reason: str | None = None,
) -> dict[str, Any]:
    live_intent = normalize_autonomy_intent(autonomy_intent)
    frozen_intent = _reconsolidation_autonomy_intent(reconsolidation_snapshot)
    live_packets = normalize_action_packets(action_packets)
    if live_packets:
        has_live_pending = any(
            str(packet.get("status") or "").strip().lower() == "awaiting_approval"
            or (
                bool(packet.get("requires_approval", False))
                and str(packet.get("status") or "").strip().lower() in {"proposed", "approved"}
            )
            for packet in live_packets
        )
        if has_live_pending:
            refreshed_live = refresh_autonomy_intent_from_packets(
                live_intent or frozen_intent,
                live_packets,
                current_event=_dict_or_empty(current_event),
                block_reason=str(autonomy_block_reason or "").strip(),
            )
            if autonomy_intent_has_signal(refreshed_live):
                return refreshed_live
    if autonomy_intent_has_signal(frozen_intent):
        return frozen_intent
    return live_intent


def resolve_action_packets(
    *,
    action_packets: Any,
    reconsolidation_snapshot: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    live_packets = normalize_action_packets(action_packets)
    frozen_packets = _reconsolidation_action_packets(reconsolidation_snapshot)
    frozen_terminal = any(
        str(packet.get("status") or "").strip().lower() in {"completed", "blocked", "rejected", "awaiting_approval"}
        or bool(packet.get("writeback_ready", False))
        for packet in frozen_packets
    )
    if frozen_packets and (frozen_terminal or not live_packets):
        return frozen_packets
    if live_packets:
        return live_packets
    return frozen_packets


def resolve_pending_action_proposal(
    *,
    pending_action_proposal: dict[str, Any] | None,
    action_packets: Any,
    reconsolidation_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    live_pending = normalize_action_packet(pending_action_proposal)
    if live_pending and bool(live_pending.get("requires_approval", False)):
        return live_pending
    for packet in resolve_action_packets(action_packets=action_packets, reconsolidation_snapshot=reconsolidation_snapshot):
        status = str(packet.get("status") or "").strip().lower()
        if bool(packet.get("requires_approval", False)) and status in {"proposed", "awaiting_approval"}:
            return dict(packet)
    return {}


def resolve_action_trace(
    *,
    action_trace: Any,
    reconsolidation_snapshot: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    live_trace = [dict(item) for item in (action_trace if isinstance(action_trace, list) else []) if isinstance(item, dict)]
    frozen_trace = _reconsolidation_action_trace(reconsolidation_snapshot)
    if frozen_trace:
        return frozen_trace
    return live_trace


def resolve_autonomy_block_reason(
    *,
    autonomy_block_reason: str | None,
    action_packets: Any = None,
    reconsolidation_snapshot: dict[str, Any] | None = None,
) -> str:
    frozen_reason = _reconsolidation_autonomy_block_reason(reconsolidation_snapshot)
    if autonomy_block_reason_has_signal(frozen_reason):
        return frozen_reason
    live_reason = str(autonomy_block_reason or "").strip()
    if autonomy_block_reason_has_signal(live_reason):
        return live_reason
    for packet in resolve_action_packets(action_packets=action_packets, reconsolidation_snapshot=reconsolidation_snapshot):
        block_reason = str(packet.get("block_reason") or "").strip()
        if block_reason:
            return block_reason
    return ""


def resolve_digital_body_state(
    *,
    digital_body_state: dict[str, Any] | None,
    reconsolidation_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    live_body = normalize_digital_body_state(digital_body_state)
    if digital_body_state_has_signal(live_body):
        return live_body
    frozen_body = _reconsolidation_digital_body_state(reconsolidation_snapshot)
    if digital_body_state_has_signal(frozen_body):
        return frozen_body
    return {}


def resolve_digital_body_consequence(
    *,
    digital_body_consequence: dict[str, Any] | None = None,
    digital_body_state: dict[str, Any] | None = None,
    action_packets: Any = None,
    reconsolidation_snapshot: dict[str, Any] | None = None,
    session_skill_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    live_consequence = _normalize_digital_body_consequence(digital_body_consequence)
    if digital_body_consequence_has_signal(live_consequence):
        return live_consequence
    recon = _dict_or_empty(reconsolidation_snapshot)
    raw_frozen_consequence = _dict_or_empty(recon.get("digital_body_consequence"))
    resolved_body = normalize_digital_body_state(digital_body_state)
    access_state = _dict_or_empty(resolved_body.get("access_state"))
    resource_state = _dict_or_empty(resolved_body.get("resource_state"))
    body_fill_raw = {
        "access_mode": access_state.get("mode"),
        "active_surface": resolved_body.get("active_surface"),
        "world_surfaces": resolved_body.get("world_surfaces"),
        "missing_access": access_state.get("missing_access"),
        "requested_access": access_state.get("requestable_access"),
        "granted_toolsets": access_state.get("granted_toolsets"),
        "active_tools": resolved_body.get("active_tools"),
        "block_reason": access_state.get("block_reason"),
        "retry_after_s": access_state.get("retry_after_s"),
        "cooldown_scope": access_state.get("cooldown_scope"),
        "browser_session": access_state.get("browser_session"),
        "account_state": access_state.get("account_state"),
        "cookie_state": access_state.get("cookie_state"),
        "api_key_state": access_state.get("api_key_state"),
        "quota_state": access_state.get("quota_state"),
        "filesystem_state": access_state.get("filesystem_state"),
        "sandbox_mode": access_state.get("sandbox_mode"),
        "network_access": access_state.get("network_access"),
        "session_continuity": access_state.get("session_continuity"),
        "session_expires_in_s": access_state.get("session_expires_in_s"),
        "session_recovery_mode": access_state.get("session_recovery_mode"),
        "pending_approval_count": access_state.get("pending_approval_count"),
        "external_mutation_pending": access_state.get("external_mutation_pending"),
        "access_acquire_proposals": access_state.get("access_acquire_proposals"),
        "selected_access_proposal": access_state.get("selected_access_proposal"),
        "session_state": access_state.get("session_state"),
        "account_state_detail": access_state.get("account_state_detail"),
        "quota_state_detail": access_state.get("quota_state_detail"),
        "permission_state": access_state.get("permission_state"),
        "sandbox_state": access_state.get("sandbox_state"),
        "artifact_continuity": resource_state.get("artifact_continuity"),
        "active_artifact_kind": resource_state.get("active_artifact_kind"),
        "active_artifact_ref": resource_state.get("active_artifact_ref"),
        "active_artifact_label": resource_state.get("active_artifact_label"),
        "artifact_age_s": resource_state.get("artifact_age_s"),
        "artifact_reacquisition_mode": resource_state.get("artifact_reacquisition_mode"),
        "artifact_carrier": resource_state.get("artifact_carrier"),
        "artifact_source_ref_ids": resource_state.get("artifact_source_ref_ids"),
        "preferred_source_ref_id": resource_state.get("preferred_source_ref_id"),
        "preferred_anchor_reason": resource_state.get("preferred_anchor_reason"),
        "artifact_source_url": resource_state.get("artifact_source_url"),
        "artifact_source_query": resource_state.get("artifact_source_query"),
        "artifact_source_title": resource_state.get("artifact_source_title"),
        "artifact_source_tool_name": resource_state.get("artifact_source_tool_name"),
        "workspace_root": resource_state.get("workspace_root"),
        "blocked_packet_count": resource_state.get("blocked_packet_count"),
        "completed_packet_count": resource_state.get("completed_packet_count"),
        "external_tool_count": resource_state.get("external_tool_count"),
    }
    if any(
        key in raw_frozen_consequence
        for key in ("session_state", "session_continuity", "session_expires_in_s", "session_recovery_mode")
    ):
        body_fill_raw.pop("session_state", None)
    derived_raw = derive_digital_body_consequence(
        digital_body_state=digital_body_state,
        action_packets=action_packets,
        session_skill_state=session_skill_state,
    )
    frozen_consequence = _reconsolidation_digital_body_consequence(reconsolidation_snapshot)
    if digital_body_consequence_has_signal(frozen_consequence):
        merged_frozen = _normalize_digital_body_consequence(
            {
                **body_fill_raw,
                **_dict_or_empty(derived_raw),
                **raw_frozen_consequence,
            }
        )
        if digital_body_consequence_has_signal(merged_frozen):
            return merged_frozen
        return frozen_consequence
    derived = _normalize_digital_body_consequence(derived_raw)
    if digital_body_consequence_has_signal(derived):
        return derived
    return {}


__all__ = [
    "behavior_action_has_signal",
    "behavior_action_has_plan_signal",
    "behavior_plan_has_signal",
    "interaction_carryover_has_signal",
    "counterpart_assessment_has_signal",
    "agenda_lifecycle_has_signal",
    "action_packets_have_signal",
    "action_trace_has_signal",
    "autonomy_block_reason_has_signal",
    "resolve_behavior_payloads",
    "resolve_interaction_carryover",
    "resolve_counterpart_assessment",
    "resolve_agenda_lifecycle_residue",
    "resolve_behavior_queue",
    "resolve_autonomy_intent",
    "resolve_action_packets",
    "resolve_pending_action_proposal",
    "resolve_action_trace",
    "resolve_autonomy_block_reason",
    "resolve_digital_body_state",
    "resolve_digital_body_consequence",
]
