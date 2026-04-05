from __future__ import annotations

from typing import Any

from ..graph_parts.digital_body_runtime import normalize_digital_body_state, normalize_embodied_context
from .embodied_preview import compact_event_residue_preview_line


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _metric(value: Any, default: float = 0.0) -> float:
    try:
        return round(float(value), 3)
    except Exception:
        return round(float(default), 3)


def _int_metric(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _clean_list(values: Any, *, limit: int = 4) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if not text:
            continue
        out.append(text)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _clean_int_list(values: Any, *, limit: int = 8) -> list[int]:
    if not isinstance(values, list):
        return []
    out: list[int] = []
    for item in values:
        try:
            number = int(item)
        except Exception:
            continue
        if number <= 0:
            continue
        out.append(number)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _clean_access_grants(values: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in out:
            continue
        out.append(lowered)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _clean_access_acquire_proposal(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    target = str(value.get("target") or "").strip().lower()
    mode = str(value.get("mode") or "").strip().lower()
    summary = str(value.get("summary") or "").strip()
    operator_action = str(value.get("operator_action") or "").strip()
    grants = _clean_access_grants(value.get("grants"), limit=8)
    requires_operator = bool(value.get("requires_operator", False))
    if not any((target, mode, summary, operator_action, grants, requires_operator)):
        return {}
    return {
        "target": target,
        "mode": mode,
        "summary": summary[:220],
        "operator_action": operator_action[:220],
        "grants": grants,
        "requires_operator": requires_operator,
    }


def _clean_access_acquire_proposals(values: Any, *, limit: int = 8) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in values:
        proposal = _clean_access_acquire_proposal(item)
        if not proposal:
            continue
        key = (
            str(proposal.get("target") or "").strip(),
            str(proposal.get("mode") or "").strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(proposal)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _clean_skill_effects(values: Any, *, limit: int = 6) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    out: list[dict[str, Any]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        skill_id = str(item.get("skill_id") or "").strip().lower()
        name = str(item.get("name") or "").strip()
        status = str(item.get("status") or "").strip().lower()
        operation = str(item.get("operation") or "").strip().lower()
        use_kind = str(item.get("use_kind") or "").strip().lower()
        tool_name = str(item.get("tool_name") or "").strip().lower()
        artifact_carrier = str(item.get("artifact_carrier") or "").strip().lower()
        artifact_ref = str(item.get("artifact_ref") or "").strip()
        artifact_label = str(item.get("artifact_label") or "").strip()
        version = str(item.get("version") or "").strip()
        source = str(item.get("source") or "").strip()
        trust_tier = str(item.get("trust_tier") or "").strip().lower()
        if not any((skill_id, name, status, operation, use_kind, tool_name, artifact_ref, artifact_label)):
            continue
        out.append(
            {
                "skill_id": skill_id,
                "name": name,
                "version": version,
                "source": source,
                "trust_tier": trust_tier,
                "status": status,
                "operation": operation,
                "use_kind": use_kind,
                "tool_name": tool_name,
                "artifact_carrier": artifact_carrier,
                "artifact_ref": artifact_ref,
                "artifact_label": artifact_label,
            }
        )
        if len(out) >= max(1, int(limit)):
            break
    return out


def summarize_embodied_context(state: Any) -> dict[str, Any]:
    normalized = normalize_embodied_context(state)
    if not normalized:
        return {}
    summary = {
        "kind": str(normalized.get("kind") or "").strip(),
        "summary": str(normalized.get("summary") or "").strip(),
        "access_mode": str(normalized.get("access_mode") or "").strip(),
        "active_surface": str(normalized.get("active_surface") or "").strip(),
        "world_surfaces": _clean_list(normalized.get("world_surfaces"), limit=12),
        "requested_access": _clean_list(normalized.get("requested_access"), limit=8),
        "missing_access": _clean_list(normalized.get("missing_access"), limit=8),
        "granted_toolsets": _clean_list(normalized.get("granted_toolsets"), limit=8),
        "active_tools": _clean_list(normalized.get("active_tools"), limit=8),
        "block_reason": str(normalized.get("block_reason") or "").strip(),
        "retry_after_s": _int_metric(normalized.get("retry_after_s"), 0),
        "cooldown_scope": str(normalized.get("cooldown_scope") or "").strip(),
        "session_continuity": str(normalized.get("session_continuity") or "").strip(),
        "session_expires_in_s": _int_metric(normalized.get("session_expires_in_s"), 0),
        "session_recovery_mode": str(normalized.get("session_recovery_mode") or "").strip(),
        "browser_session": str(normalized.get("browser_session") or "").strip(),
        "account_state": str(normalized.get("account_state") or "").strip(),
        "cookie_state": str(normalized.get("cookie_state") or "").strip(),
        "api_key_state": str(normalized.get("api_key_state") or "").strip(),
        "quota_state": str(normalized.get("quota_state") or "").strip(),
        "filesystem_state": str(normalized.get("filesystem_state") or "").strip(),
        "sandbox_mode": str(normalized.get("sandbox_mode") or "").strip(),
        "network_access": str(normalized.get("network_access") or "").strip(),
        "access_acquire_proposals": _clean_access_acquire_proposals(
            normalized.get("access_acquire_proposals"),
            limit=8,
        ),
        "selected_access_proposal": _clean_access_acquire_proposal(
            normalized.get("selected_access_proposal")
        ),
        "artifact_continuity": str(normalized.get("artifact_continuity") or "").strip(),
        "active_artifact_kind": str(normalized.get("active_artifact_kind") or "").strip(),
        "active_artifact_ref": str(normalized.get("active_artifact_ref") or "").strip(),
        "workspace_root": str(normalized.get("workspace_root") or "").strip(),
        "active_artifact_label": str(normalized.get("active_artifact_label") or "").strip(),
        "artifact_age_s": _int_metric(normalized.get("artifact_age_s"), 0),
        "artifact_reacquisition_mode": str(normalized.get("artifact_reacquisition_mode") or "").strip(),
        "artifact_mutation_mode": str(normalized.get("artifact_mutation_mode") or "").strip(),
        "artifact_carrier": str(normalized.get("artifact_carrier") or "").strip(),
        "artifact_source_ref_ids": _clean_int_list(normalized.get("artifact_source_ref_ids"), limit=8),
        "preferred_source_ref_id": _int_metric(normalized.get("preferred_source_ref_id"), 0),
        "preferred_anchor_reason": str(normalized.get("preferred_anchor_reason") or "").strip(),
        "artifact_source_url": str(normalized.get("artifact_source_url") or "").strip(),
        "artifact_source_query": str(normalized.get("artifact_source_query") or "").strip(),
        "artifact_source_title": str(normalized.get("artifact_source_title") or "").strip(),
        "artifact_source_tool_name": str(normalized.get("artifact_source_tool_name") or "").strip(),
        "pending_approval_count": _int_metric(normalized.get("pending_approval_count"), 0),
        "blocked_packet_count": _int_metric(normalized.get("blocked_packet_count"), 0),
        "completed_packet_count": _int_metric(normalized.get("completed_packet_count"), 0),
        "external_tool_count": _int_metric(normalized.get("external_tool_count"), 0),
        "primary_proposal_id": str(normalized.get("primary_proposal_id") or "").strip(),
        "primary_status": str(normalized.get("primary_status") or "").strip(),
        "primary_origin": str(normalized.get("primary_origin") or "").strip(),
        "primary_intent": str(normalized.get("primary_intent") or "").strip(),
        "primary_tool_name": str(normalized.get("primary_tool_name") or "").strip(),
        "procedural_growth": bool(normalized.get("procedural_growth", False)),
        "environmental_friction": bool(normalized.get("environmental_friction", False)),
        "requested_help": bool(normalized.get("requested_help", False)),
    }
    skill_effects = _clean_skill_effects(normalized.get("skill_effects"), limit=6)
    if skill_effects:
        summary["skill_effects"] = skill_effects
    return summary


def summarize_interaction_carryover(carryover: Any) -> dict[str, Any]:
    if not isinstance(carryover, dict) or not carryover:
        return {}
    summary = {
        "source": str(carryover.get("source") or "").strip(),
        "source_event_kind": str(carryover.get("source_event_kind") or "").strip(),
        "source_behavior_mode": str(carryover.get("source_behavior_mode") or "").strip(),
        "source_action_target": str(carryover.get("source_action_target") or "").strip(),
        "source_primary_motive": str(carryover.get("source_primary_motive") or "").strip(),
        "source_motive_tension": str(carryover.get("source_motive_tension") or "").strip(),
        "source_goal_frame": str(carryover.get("source_goal_frame") or "").strip(),
        "source_text": str(carryover.get("source_text") or "").strip()[:180],
        "source_tags": _clean_list(carryover.get("source_tags"), limit=10),
        "carryover_mode": str(carryover.get("carryover_mode") or "").strip(),
        "strength": _metric(carryover.get("strength"), 0.0),
        "relationship_weather": str(carryover.get("relationship_weather") or "").strip(),
        "idle_minutes": _int_metric(carryover.get("idle_minutes"), 0),
        "source_turn_gap": _int_metric(carryover.get("source_turn_gap"), 0),
        "attention_target": str(carryover.get("attention_target") or "").strip(),
        "nonverbal_signal": str(carryover.get("nonverbal_signal") or "").strip(),
        "note": str(carryover.get("note") or "").strip(),
        "created_at": _int_metric(carryover.get("created_at"), 0),
    }
    embodied_context = summarize_embodied_context(carryover.get("embodied_context"))
    if embodied_context:
        summary["embodied_context"] = embodied_context
    return summary


def summarize_event_residue(current_event: Any, *, digital_body_consequence: Any = None) -> dict[str, Any]:
    if not isinstance(current_event, dict) or not current_event:
        return {}
    perception = _dict_or_empty(current_event.get("perception"))
    summary = {
        "event_kind": str(current_event.get("kind") or "").strip(),
        "source": str(current_event.get("source") or "").strip(),
        "event_frame": str(current_event.get("event_frame") or "").strip(),
        "response_style_hint": str(current_event.get("response_style_hint") or "").strip(),
        "science_mode": bool(current_event.get("science_mode", False)),
        "continuation_mode": bool(current_event.get("continuation_mode", False)),
        "counterpart_name": str(current_event.get("counterpart_name") or "").strip(),
        "appraisal_label": str(current_event.get("appraisal_label") or "").strip(),
        "appraisal_confidence": _metric(current_event.get("appraisal_confidence"), 0.0),
        "created_at": _int_metric(current_event.get("created_at"), 0),
        "tags": _clean_list(current_event.get("tags"), limit=8),
        "thread_id": str(perception.get("thread_id") or "").strip(),
        "turn_id": str(perception.get("turn_id") or "").strip(),
        "event_id": str(perception.get("event_id") or "").strip(),
        "trigger_family": str(current_event.get("trigger_family") or "").strip(),
        "derived_from_plan_kind": str(current_event.get("derived_from_plan_kind") or "").strip(),
        "commitment_id": _int_metric(current_event.get("commitment_id"), 0),
        "due_at": str(current_event.get("due_at") or "").strip(),
        "carryover_mode": str(current_event.get("carryover_mode") or "").strip(),
        "carryover_strength": _metric(current_event.get("carryover_strength"), 0.0),
        "relationship_weather": str(current_event.get("relationship_weather") or "").strip(),
        "channel": str(perception.get("channel") or "").strip(),
        "modality": str(perception.get("modality") or "").strip(),
        "source_role": str(perception.get("source_role") or "").strip(),
        "trust_tier": str(perception.get("trust_tier") or "").strip(),
        "salience": _metric(perception.get("salience"), 0.0),
        "interruptibility": str(perception.get("interruptibility") or "").strip(),
        "delivery_mode": str(perception.get("delivery_mode") or "").strip(),
        "is_proactive": bool(perception.get("is_proactive", False)),
        "presence_residue": _metric(current_event.get("presence_residue"), 0.0),
        "ambient_resonance": _metric(current_event.get("ambient_resonance"), 0.0),
        "self_activity_momentum": _metric(current_event.get("self_activity_momentum"), 0.0),
        "attention_target_hint": str(current_event.get("attention_target_hint") or "").strip(),
        "nonverbal_signal_hint": str(current_event.get("nonverbal_signal_hint") or "").strip(),
        "scheduled_after_min": _int_metric(current_event.get("scheduled_after_min"), 0),
        "idle_minutes": _int_metric(current_event.get("idle_minutes"), 0),
    }
    embodied = summarize_embodied_context(digital_body_consequence)
    if embodied:
        summary["digital_body_consequence"] = embodied
    preview_line = compact_event_residue_preview_line(summary)
    if preview_line:
        summary["preview_line"] = preview_line
    return summary


def summarize_behavior_consequence(consequence: Any) -> dict[str, Any]:
    if not isinstance(consequence, dict) or not consequence:
        return {}
    summary = {
        "kind": str(consequence.get("kind") or "").strip(),
        "summary": str(consequence.get("summary") or "").strip(),
        "relationship_effect": str(consequence.get("relationship_effect") or "").strip(),
        "self_effect": str(consequence.get("self_effect") or "").strip(),
        "trigger_family": str(consequence.get("trigger_family") or "").strip(),
        "relationship_weather": str(consequence.get("relationship_weather") or "").strip(),
        "carryover_mode": str(consequence.get("carryover_mode") or "").strip(),
        "timing_window_min": _int_metric(consequence.get("timing_window_min"), 0),
        "silent": bool(consequence.get("silent", False)),
        "delayed": bool(consequence.get("delayed", False)),
        "stale_window": bool(consequence.get("stale_window", False)),
    }
    embodied = summarize_embodied_context(consequence.get("embodied_context"))
    if embodied:
        summary["embodied_context"] = embodied
    return summary


def summarize_opening_window_profile(profile: Any) -> dict[str, Any]:
    if not isinstance(profile, dict) or not profile:
        return {}
    profile_type = str(profile.get("profile_type") or "").strip()
    if profile_type == "scheduled_window":
        score = _metric(profile.get("maturity"), 0.0)
        required = _metric(profile.get("required_maturity"), 0.0)
        ready = bool(profile.get("invite_ready", False))
        score_label = "maturity"
        required_label = "required_maturity"
        ready_label = "invite_ready"
    elif profile_type == "self_opening":
        score = _metric(profile.get("readiness"), 0.0)
        required = _metric(profile.get("required_readiness"), 0.0)
        ready = bool(profile.get("reopen_ready", False))
        score_label = "readiness"
        required_label = "required_readiness"
        ready_label = "reopen_ready"
    else:
        score = _metric(profile.get("maturity"), 0.0)
        required = _metric(profile.get("required_maturity"), 0.0)
        ready = bool(profile.get("invite_ready", False) or profile.get("reopen_ready", False))
        score_label = "score"
        required_label = "required"
        ready_label = "ready"
    return {
        "profile_type": profile_type,
        "event_kind": str(profile.get("event_kind") or "").strip(),
        "family": str(profile.get("family") or "").strip(),
        "trigger_family": str(profile.get("trigger_family") or "").strip(),
        "stance": str(profile.get("stance") or "").strip(),
        "scene": str(profile.get("scene") or "").strip(),
        "decision": str(profile.get("decision") or "").strip(),
        score_label: score,
        required_label: required,
        "gap": round(score - required, 3),
        ready_label: ready,
        "recheck_min": _int_metric(profile.get("recheck_min"), 0),
        "continuity_bonus": _metric(profile.get("continuity_bonus"), 0.0),
        "continuity_discount": _metric(profile.get("continuity_discount"), 0.0),
        "carryover_mode": str(profile.get("carryover_mode") or "").strip(),
        "carryover_strength": _metric(profile.get("carryover_strength"), 0.0),
        "event_carryover_mode": str(profile.get("event_carryover_mode") or "").strip(),
        "event_carryover_strength": _metric(profile.get("event_carryover_strength"), 0.0),
        "presence_residue": _metric(profile.get("presence_residue"), 0.0),
        "ambient_resonance": _metric(profile.get("ambient_resonance"), 0.0),
        "self_activity_momentum": _metric(profile.get("self_activity_momentum"), 0.0),
        "recontact_echo": _metric(profile.get("recontact_echo"), 0.0),
        "own_rhythm_load": _metric(profile.get("own_rhythm_load"), 0.0),
    }


def summarize_agenda_lifecycle(residue: Any) -> dict[str, Any]:
    if not isinstance(residue, dict) or not residue:
        return {}
    summary = {
        "kind": str(residue.get("kind") or "").strip(),
        "source_event_kind": str(residue.get("source_event_kind") or "").strip(),
        "trigger_family": str(residue.get("trigger_family") or "").strip(),
        "carryover_mode": str(residue.get("carryover_mode") or "").strip(),
        "carryover_strength": _metric(residue.get("carryover_strength"), 0.0),
        "relationship_weather": str(residue.get("relationship_weather") or "").strip(),
        "hold_count": _int_metric(residue.get("hold_count"), 0),
        "idle_minutes": _int_metric(residue.get("idle_minutes"), 0),
        "attention_target": str(residue.get("attention_target") or "").strip(),
        "nonverbal_signal": str(residue.get("nonverbal_signal") or "").strip(),
        "presence_residue": _metric(residue.get("presence_residue"), 0.0),
        "ambient_resonance": _metric(residue.get("ambient_resonance"), 0.0),
        "self_activity_momentum": _metric(residue.get("self_activity_momentum"), 0.0),
        "continuity_anchor": _metric(residue.get("continuity_anchor"), 0.0),
        "own_rhythm_anchor": _metric(residue.get("own_rhythm_anchor"), 0.0),
        "recontact_anchor": _metric(residue.get("recontact_anchor"), 0.0),
        "boundary_anchor": _metric(residue.get("boundary_anchor"), 0.0),
        "memory_anchor": _metric(residue.get("memory_anchor"), 0.0),
        "semantic_continuity_depth": _metric(residue.get("semantic_continuity_depth"), 0.0),
        "semantic_identity_gravity": _metric(residue.get("semantic_identity_gravity"), 0.0),
        "lineage_gravity": _metric(residue.get("lineage_gravity"), 0.0),
        "contact_lineage": _metric(residue.get("contact_lineage"), 0.0),
        "repair_lineage": _metric(residue.get("repair_lineage"), 0.0),
        "boundary_lineage": _metric(residue.get("boundary_lineage"), 0.0),
        "selfhood_lineage": _metric(residue.get("selfhood_lineage"), 0.0),
        "agency_lineage": _metric(residue.get("agency_lineage"), 0.0),
        "long_term_axis_count": _int_metric(residue.get("long_term_axis_count"), 0),
        "own_rhythm_bias": _metric(residue.get("own_rhythm_bias"), 0.0),
        "recontact_cooldown": _metric(residue.get("recontact_cooldown"), 0.0),
        "counterpart_scene_bias": str(residue.get("counterpart_scene_bias") or "").strip(),
        "counterpart_boundary_delta": _metric(residue.get("counterpart_boundary_delta"), 0.0),
        "created_at": _int_metric(residue.get("created_at"), 0),
        "source_tags": _clean_list(residue.get("source_tags"), limit=6),
        "note": str(residue.get("note") or "").strip()[:160],
    }
    embodied = summarize_embodied_context(residue.get("embodied_context"))
    if embodied:
        summary["embodied_context"] = embodied
    return summary


def summarize_digital_body(state: Any) -> dict[str, Any]:
    normalized = normalize_digital_body_state(state)
    if not normalized:
        return {}
    access_state = _dict_or_empty(normalized.get("access_state"))
    resource_state = _dict_or_empty(normalized.get("resource_state"))
    return {
        "active_surface": str(normalized.get("active_surface") or "").strip(),
        "perception_channels": _clean_list(normalized.get("perception_channels"), limit=8),
        "action_channels": _clean_list(normalized.get("action_channels"), limit=8),
        "world_surfaces": _clean_list(normalized.get("world_surfaces"), limit=12),
        "available_toolsets": _clean_list(normalized.get("available_toolsets"), limit=8),
        "active_tools": _clean_list(normalized.get("active_tools"), limit=8),
        "access": {
            "mode": str(access_state.get("mode") or "").strip(),
            "conditions": _clean_list(access_state.get("conditions"), limit=8),
            "block_reason": str(access_state.get("block_reason") or "").strip(),
            "retry_after_s": _int_metric(access_state.get("retry_after_s"), 0),
            "cooldown_scope": str(access_state.get("cooldown_scope") or "").strip(),
            "session_continuity": str(access_state.get("session_continuity") or "").strip(),
            "session_expires_in_s": _int_metric(access_state.get("session_expires_in_s"), 0),
            "session_recovery_mode": str(access_state.get("session_recovery_mode") or "").strip(),
            "pending_approval_count": _int_metric(access_state.get("pending_approval_count"), 0),
            "external_mutation_pending": bool(access_state.get("external_mutation_pending", False)),
            "granted_toolsets": _clean_list(access_state.get("granted_toolsets"), limit=8),
            "missing_access": _clean_list(access_state.get("missing_access"), limit=8),
            "requestable_access": _clean_list(access_state.get("requestable_access"), limit=8),
            "browser_session": str(access_state.get("browser_session") or "").strip(),
            "account_state": str(access_state.get("account_state") or "").strip(),
            "cookie_state": str(access_state.get("cookie_state") or "").strip(),
            "api_key_state": str(access_state.get("api_key_state") or "").strip(),
            "quota_state": str(access_state.get("quota_state") or "").strip(),
            "filesystem_state": str(access_state.get("filesystem_state") or "").strip(),
            "sandbox_mode": str(access_state.get("sandbox_mode") or "").strip(),
            "network_access": str(access_state.get("network_access") or "").strip(),
            "access_acquire_proposals": [
                dict(item)
                for item in (access_state.get("access_acquire_proposals") or [])[:8]
                if isinstance(item, dict)
            ],
            "selected_access_proposal": dict(access_state.get("selected_access_proposal"))
            if isinstance(access_state.get("selected_access_proposal"), dict)
            else {},
            "session_state": dict(access_state.get("session_state"))
            if isinstance(access_state.get("session_state"), dict)
            else {},
            "account_state_detail": dict(access_state.get("account_state_detail"))
            if isinstance(access_state.get("account_state_detail"), dict)
            else {},
            "quota_state_detail": dict(access_state.get("quota_state_detail"))
            if isinstance(access_state.get("quota_state_detail"), dict)
            else {},
            "permission_state": dict(access_state.get("permission_state"))
            if isinstance(access_state.get("permission_state"), dict)
            else {},
            "sandbox_state": dict(access_state.get("sandbox_state"))
            if isinstance(access_state.get("sandbox_state"), dict)
            else {},
        },
        "resources": {
            "behavior_queue_depth": _int_metric(resource_state.get("behavior_queue_depth"), 0),
            "action_packet_count": _int_metric(resource_state.get("action_packet_count"), 0),
            "pending_approval_count": _int_metric(resource_state.get("pending_approval_count"), 0),
            "queued_packet_count": _int_metric(resource_state.get("queued_packet_count"), 0),
            "executing_packet_count": _int_metric(resource_state.get("executing_packet_count"), 0),
            "completed_packet_count": _int_metric(resource_state.get("completed_packet_count"), 0),
            "blocked_packet_count": _int_metric(resource_state.get("blocked_packet_count"), 0),
            "external_tool_count": _int_metric(resource_state.get("external_tool_count"), 0),
            "artifact_continuity": str(resource_state.get("artifact_continuity") or "").strip(),
            "active_artifact_kind": str(resource_state.get("active_artifact_kind") or "").strip(),
            "active_artifact_ref": str(resource_state.get("active_artifact_ref") or "").strip(),
            "workspace_root": str(resource_state.get("workspace_root") or "").strip(),
            "active_artifact_label": str(resource_state.get("active_artifact_label") or "").strip(),
            "artifact_age_s": _int_metric(resource_state.get("artifact_age_s"), 0),
            "artifact_reacquisition_mode": str(resource_state.get("artifact_reacquisition_mode") or "").strip(),
            "artifact_carrier": str(resource_state.get("artifact_carrier") or "").strip(),
            "artifact_source_ref_ids": _clean_int_list(resource_state.get("artifact_source_ref_ids"), limit=8),
            "preferred_source_ref_id": _int_metric(resource_state.get("preferred_source_ref_id"), 0),
            "preferred_anchor_reason": str(resource_state.get("preferred_anchor_reason") or "").strip(),
            "artifact_source_url": str(resource_state.get("artifact_source_url") or "").strip(),
            "artifact_source_query": str(resource_state.get("artifact_source_query") or "").strip(),
            "artifact_source_title": str(resource_state.get("artifact_source_title") or "").strip(),
            "artifact_source_tool_name": str(resource_state.get("artifact_source_tool_name") or "").strip(),
        },
        "constraints": _clean_list(normalized.get("body_constraints"), limit=8),
    }


def summarize_digital_body_consequence(state: Any) -> dict[str, Any]:
    return summarize_embodied_context(state)


__all__ = [
    "summarize_agenda_lifecycle",
    "summarize_behavior_consequence",
    "summarize_digital_body",
    "summarize_digital_body_consequence",
    "summarize_embodied_context",
    "summarize_event_residue",
    "summarize_interaction_carryover",
    "summarize_opening_window_profile",
]
