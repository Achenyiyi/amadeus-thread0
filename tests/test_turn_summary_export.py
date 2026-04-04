from amadeus_thread0.utils.turn_summary_export import (
    summarize_agenda_lifecycle,
    summarize_behavior_consequence,
    summarize_digital_body,
    summarize_digital_body_consequence,
    summarize_embodied_context,
    summarize_event_residue,
    summarize_interaction_carryover,
    summarize_opening_window_profile,
)


def test_summarize_embodied_context_normalizes_source_anchor_fields():
    summary = summarize_embodied_context(
        {
            "kind": "source_material_compared",
            "artifact_carrier": "source_ref",
            "artifact_source_ref_ids": ["21", "17"],
            "preferred_source_ref_id": "21",
            "preferred_anchor_reason": " Primary_More_Current ",
            "artifact_source_title": " Persistence v2 ",
            "artifact_source_tool_name": " search_web ",
            "requested_help": True,
            "primary_status": "completed",
        }
    )

    assert summary["kind"] == "source_material_compared"
    assert summary["artifact_carrier"] == "source_ref"
    assert summary["artifact_source_ref_ids"] == [21, 17]
    assert summary["preferred_source_ref_id"] == 21
    assert summary["preferred_anchor_reason"] == "primary_more_current"
    assert summary["artifact_source_title"] == "Persistence v2"
    assert summary["artifact_source_tool_name"] == "search_web"
    assert summary["requested_help"] is True
    assert summary["primary_status"] == "completed"


def test_summarize_event_residue_keeps_perception_and_preview_contract():
    summary = summarize_event_residue(
        {
            "kind": "scheduled_life_due",
            "source": "scheduler",
            "event_frame": "idle continuation",
            "response_style_hint": "relationship",
            "science_mode": False,
            "continuation_mode": True,
            "counterpart_name": "冈部伦太郎",
            "appraisal_label": "care",
            "appraisal_confidence": 0.61,
            "created_at": 1710000018,
            "tags": ["user_busy", "commitment_window", ""],
            "trigger_family": "life_window",
            "derived_from_plan_kind": "commitment_window",
            "commitment_id": 12,
            "due_at": "今晚",
            "carryover_mode": "small_opening",
            "carryover_strength": 0.44,
            "relationship_weather": "warm_residue",
            "presence_residue": 0.38,
            "ambient_resonance": 0.27,
            "self_activity_momentum": 0.49,
            "attention_target_hint": "counterpart_state",
            "nonverbal_signal_hint": "quiet_glance",
            "scheduled_after_min": 18,
            "idle_minutes": 18,
            "perception": {
                "thread_id": "thread-a",
                "turn_id": "thread-a:555",
                "event_id": "thread-a:555:idle:scheduler",
                "channel": "system",
                "modality": "system",
                "source_role": "system",
                "trust_tier": "high",
                "salience": 0.58,
                "interruptibility": "soft",
                "delivery_mode": "scheduled",
                "is_proactive": True,
            },
        },
        digital_body_consequence={
            "kind": "access_request_pending",
            "requested_access": ["workspace_write", "human_approval"],
            "artifact_carrier": "source_ref",
            "artifact_source_ref_ids": [17],
            "artifact_source_title": "Persistence",
            "artifact_source_tool_name": "search_web",
            "requested_help": True,
            "primary_status": "awaiting_approval",
        },
    )

    assert summary["event_kind"] == "scheduled_life_due"
    assert summary["thread_id"] == "thread-a"
    assert summary["turn_id"] == "thread-a:555"
    assert summary["event_id"] == "thread-a:555:idle:scheduler"
    assert summary["tags"] == ["user_busy", "commitment_window"]
    assert summary["digital_body_consequence"]["kind"] == "access_request_pending"
    assert summary["digital_body_consequence"]["artifact_source_ref_ids"] == [17]
    assert "scheduled_life_due@scheduler" in (summary.get("preview_line") or "")
    assert "bodyfx=access_request_pending" in (summary.get("preview_line") or "")


def test_summarize_agenda_lifecycle_preserves_long_horizon_axes_and_embodied_context():
    summary = summarize_agenda_lifecycle(
        {
            "kind": "released_to_self_activity",
            "source_event_kind": "scheduled_life_due",
            "trigger_family": "life_window",
            "carryover_mode": "own_rhythm",
            "carryover_strength": 0.53,
            "relationship_weather": "warm_residue",
            "hold_count": 2,
            "idle_minutes": 18,
            "attention_target": "counterpart_state",
            "presence_residue": 0.33,
            "ambient_resonance": 0.24,
            "self_activity_momentum": 0.58,
            "continuity_anchor": 0.66,
            "own_rhythm_anchor": 0.72,
            "recontact_anchor": 0.34,
            "boundary_anchor": 0.22,
            "memory_anchor": 0.30,
            "semantic_continuity_depth": 0.68,
            "semantic_identity_gravity": 0.64,
            "lineage_gravity": 0.70,
            "contact_lineage": 0.44,
            "repair_lineage": 0.41,
            "boundary_lineage": 0.36,
            "selfhood_lineage": 0.69,
            "agency_lineage": 0.78,
            "long_term_axis_count": 4,
            "own_rhythm_bias": 0.61,
            "recontact_cooldown": 0.47,
            "counterpart_scene_bias": "busy_not_disrespectful",
            "counterpart_boundary_delta": -0.04,
            "created_at": 1710000099,
            "source_tags": ["user_busy", "agenda_lifecycle", ""],
            "note": "前面挂着的窗口没有继续往前推，注意力被自然收回到了自己的节奏里。",
            "embodied_context": {
                "kind": "access_request_pending",
                "requested_access": ["workspace_write", "human_approval"],
                "artifact_carrier": "source_ref",
                "artifact_source_ref_ids": [17],
                "artifact_source_title": "Persistence",
                "artifact_source_tool_name": "search_web",
                "requested_help": True,
                "primary_status": "awaiting_approval",
            },
        }
    )

    assert summary["kind"] == "released_to_self_activity"
    assert summary["carryover_mode"] == "own_rhythm"
    assert summary["continuity_anchor"] == 0.66
    assert summary["semantic_continuity_depth"] == 0.68
    assert summary["long_term_axis_count"] == 4
    assert summary["source_tags"] == ["user_busy", "agenda_lifecycle"]
    assert summary["embodied_context"]["kind"] == "access_request_pending"
    assert summary["embodied_context"]["artifact_source_ref_ids"] == [17]


def test_summarize_interaction_carryover_preserves_embodied_context():
    summary = summarize_interaction_carryover(
        {
            "source": "reconsolidation",
            "source_event_kind": "scheduled_life_due",
            "source_primary_motive": "honor_continuity",
            "source_text": "前面的窗口还在慢慢往后带。",
            "source_tags": ["continuity", "warm_residue", ""],
            "carryover_mode": "own_rhythm",
            "strength": 0.53,
            "relationship_weather": "warm_residue",
            "note": "窗口先不往前推太满。",
            "embodied_context": {
                "kind": "access_request_pending",
                "requested_access": ["workspace_write"],
                "requested_help": True,
                "primary_status": "awaiting_approval",
                "primary_origin": "counterpart_request",
                "primary_intent": "write_file",
                "primary_tool_name": "write_file",
            },
        }
    )

    assert summary["source"] == "reconsolidation"
    assert summary["carryover_mode"] == "own_rhythm"
    assert summary["source_tags"] == ["continuity", "warm_residue"]
    assert summary["embodied_context"]["kind"] == "access_request_pending"
    assert summary["embodied_context"]["requested_access"] == ["workspace_write"]
    assert summary["embodied_context"]["primary_origin"] == "counterpart_request"
    assert summary["embodied_context"]["primary_intent"] == "write_file"
    assert summary["embodied_context"]["primary_tool_name"] == "write_file"


def test_summarize_behavior_consequence_preserves_embodied_context():
    summary = summarize_behavior_consequence(
        {
            "kind": "defer_recontact",
            "summary": "这次先没有立刻往前接。",
            "relationship_effect": "warm_residue",
            "self_effect": "hold_rhythm",
            "trigger_family": "life_window",
            "carryover_mode": "own_rhythm",
            "timing_window_min": 18,
            "embodied_context": {
                "kind": "environmental_friction",
                "missing_access": ["browser_session"],
                "environmental_friction": True,
            },
        }
    )

    assert summary["kind"] == "defer_recontact"
    assert summary["carryover_mode"] == "own_rhythm"
    assert summary["timing_window_min"] == 18
    assert summary["embodied_context"]["kind"] == "environmental_friction"
    assert summary["embodied_context"]["missing_access"] == ["browser_session"]
    assert summary["embodied_context"]["environmental_friction"] is True


def test_summarize_digital_body_normalizes_access_and_resource_sections():
    summary = summarize_digital_body(
        {
            "active_surface": "tooling",
            "perception_channels": ["dialogue", "scene"],
            "action_channels": ["language", "structured_action", "tooling"],
            "world_surfaces": ["browser", "filesystem", "network"],
            "available_toolsets": ["browser", "filesystem"],
            "active_tools": ["search_web", "read_file"],
            "access_state": {
                "mode": "tool_enabled",
                "conditions": ["network_available", ""],
                "pending_approval_count": 1,
                "granted_toolsets": ["browser", "filesystem"],
                "missing_access": ["browser_session"],
                "requestable_access": ["browser_session", "workspace_write"],
                "browser_session": "missing",
                "api_key_state": "missing",
                "quota_state": "low",
                "filesystem_state": "read_only",
                "sandbox_mode": "restricted",
                "network_access": "enabled",
                "selected_access_proposal": {
                    "target": "workspace_write",
                    "mode": "operator_grant",
                    "summary": "补一个工作区写权限。",
                    "operator_action": "确认授权。",
                    "grants": ["workspace_write"],
                    "requires_operator": True,
                },
            },
            "resource_state": {
                "action_packet_count": 2,
                "external_tool_count": 1,
                "artifact_continuity": "detached",
                "active_artifact_kind": "file",
                "workspace_root": "E:/runtime/workspaces/lab-notes",
                "active_artifact_label": "plan.md",
                "artifact_reacquisition_mode": "reopen_file",
                "artifact_carrier": "source_ref",
                "artifact_source_ref_ids": [17],
                "preferred_source_ref_id": 17,
                "preferred_anchor_reason": "only_saved_source",
                "artifact_source_title": "Persistence",
                "artifact_source_tool_name": "search_web",
            },
            "body_constraints": ["network_available"],
        }
    )

    assert summary["active_surface"] == "tooling"
    assert summary["access"]["mode"] == "tool_enabled"
    assert summary["access"]["missing_access"] == ["browser_session"]
    assert summary["access"]["selected_access_proposal"]["target"] == "workspace_write"
    assert summary["resources"]["action_packet_count"] == 2
    assert summary["resources"]["artifact_carrier"] == "source_ref"
    assert summary["resources"]["artifact_source_ref_ids"] == [17]
    assert summary["resources"]["preferred_anchor_reason"] == "only_saved_source"
    assert summary["constraints"] == ["network_available"]


def test_summarize_digital_body_consequence_keeps_primary_tool_and_source_anchor_fields():
    summary = summarize_digital_body_consequence(
        {
            "kind": "source_material_compared",
            "summary": "她已经把两份材料比过了。",
            "artifact_carrier": "source_ref",
            "artifact_source_ref_ids": [21, 17],
            "preferred_source_ref_id": 21,
            "preferred_anchor_reason": "primary_more_current",
            "artifact_source_title": "Persistence",
            "artifact_source_tool_name": "compare_source_refs",
            "primary_proposal_id": "ap-body-1",
            "primary_status": "completed",
            "primary_origin": "counterpart_request",
            "primary_intent": "artifact:compare_source_refs",
            "primary_tool_name": "compare_source_refs",
            "requested_help": False,
        }
    )

    assert summary["kind"] == "source_material_compared"
    assert summary["artifact_source_ref_ids"] == [21, 17]
    assert summary["preferred_source_ref_id"] == 21
    assert summary["primary_proposal_id"] == "ap-body-1"
    assert summary["primary_status"] == "completed"
    assert summary["primary_origin"] == "counterpart_request"
    assert summary["primary_intent"] == "artifact:compare_source_refs"
    assert summary["primary_tool_name"] == "compare_source_refs"


def test_summarize_opening_window_profile_normalizes_scheduled_window_shape():
    summary = summarize_opening_window_profile(
        {
            "profile_type": "scheduled_window",
            "event_kind": "scheduled_life_due",
            "family": "life",
            "trigger_family": "life_window",
            "decision": "wait_and_recheck",
            "maturity": 0.52,
            "required_maturity": 0.58,
            "invite_ready": False,
            "recheck_min": 18,
            "carryover_mode": "small_opening",
            "carryover_strength": 0.44,
            "presence_residue": 0.38,
            "ambient_resonance": 0.27,
            "self_activity_momentum": 0.49,
            "recontact_echo": 0.38,
            "own_rhythm_load": 0.49,
            "continuity_bonus": 0.08,
            "continuity_discount": 0.02,
        }
    )

    assert summary["profile_type"] == "scheduled_window"
    assert summary["maturity"] == 0.52
    assert summary["required_maturity"] == 0.58
    assert summary["gap"] == -0.06
    assert summary["invite_ready"] is False
    assert summary["carryover_mode"] == "small_opening"
    assert summary["recheck_min"] == 18
