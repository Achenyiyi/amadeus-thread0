from __future__ import annotations

"""Compatibility export layer for graph helpers and builders."""

from .graph_parts import (
    ThreadState,
    build_graph,
    build_implicit_idle_state_update,
    reset_runtime_caches,
)

from .graph_parts.appraisal import (
    _build_turn_appraisal_prompt,
    _coerce_appraisal_payload,
    _explicit_boundary_test,
    _explicit_hierarchy_pressure,
    _extract_json_block,
    _finalize_turn_appraisal_payload,
    _invoke_turn_appraisal,
    _postprocess_appraisal_payload,
    _recent_dialogue_lines,
    _should_use_llm_appraisal,
    _soft_accept_appraisal_payload,
)

from .graph_parts.affect_dynamics import (
    _allostasis_next,
    _behavior_policy_from_state,
    _bond_next,
    _emotion_decay_target,
    _emotion_next,
)

from .graph_parts.behavior_agenda import (
    _behavior_agenda_entry_from_plan,
    _behavior_agenda_next_recheck_min,
    _behavior_agenda_should_release,
    _merge_behavior_agenda,
    _normalize_behavior_agenda,
    _promote_due_behavior_action_event,
    _promote_due_behavior_agenda_event,
    _promote_due_behavior_plan_event,
)

from .graph_parts.behavior_runtime import (
    _behavior_action_from_state,
    _behavior_plan_carryover_snapshot,
    _behavior_plan_from_action,
    _compact_behavior_action_hint,
)

from .graph_parts.common import (
    _clamp01,
    _clamp_signed,
    _norm_text,
    _now_ts,
    _safe_json,
    _sanitize_message,
    _sanitize_obj,
)

from .graph_parts.counterpart_dynamics import (
    _active_appraisal_payload,
    _appraisal_target_weight,
    _blend_state_value,
    _counterpart_assessment_next,
    _counterpart_dialogue_mode_profile,
    _counterpart_perception_profile,
    _counterpart_self_opening_profile,
    _counterpart_window_profile,
)

from .graph_parts.dialogue_guidance import (
    _event_behavior_preference_lines,
    _event_behavior_preference_scene,
    _light_free_dialog_counterpart_line,
    _light_free_dialog_state_hint,
    _load_event_to_behavior_preference_bank,
    _load_selfhood_preference_bank,
    _load_user_style_expression_bank,
    _narrative_actor_profile,
    _plain_contact_ping_needs_relational_guard,
    _scene_persona_axioms,
    _selfhood_preference_lines,
    _subjective_runtime_state_hint,
    _user_style_preference_lines,
)

from .graph_parts.generation_profile import (
    _daily_surface_alignment_metrics,
    _daily_surface_preference_lines,
    _daily_surface_profile,
    _daily_surface_prompt_similarity,
    _effective_relationship_weather,
    _ensure_response_structure,
    _flatten_surface_example,
    _generation_profile,
    _is_free_dialog_style,
    _is_light_free_dialog_turn,
    _load_daily_surface_preference_corpus,
    _looks_like_daily_surface_scene,
    _normalize_surface_prompt_text,
    _reply_opener_signature,
    _reply_repetition_signature,
    _stable_unit_interval,
    _surface_drift_marker_hits,
    _text_similarity,
)

from .graph_parts.guards import (
    _canon_guard,
    _ooc_risk,
    _persona_gap,
)

from .graph_parts.memory_evolution import (
    _auto_reconsolidate_after_tool,
    _passive_evolution_memory_update,
    _recent_summary_overlap,
    _record_semantic_self_evidence,
    _refresh_semantic_self_narratives,
    _resolve_matching_tensions_from_summary,
    _semantic_self_evidence_records,
    _selfhood_preference_scene,
)

from .graph_parts.nodes import (
    _available_tools_for_state,
    _node_call_model,
    _node_prepare_turn,
)

from .graph_parts.persona_runtime import (
    _active_counterpart_profile,
    _active_persona_core,
    _canon_counterpart_profile,
    _canon_okabe_recontact_baseline,
    _canon_persona_labels,
    _ensure_canon_counterpart_defaults,
    _has_relational_history_for_seed,
    _is_canon_amadeus_okabe_context,
    _is_external_probe_context,
    _prefer_explicit_state_dict,
    _science_mode_from_context,
    _science_mode_from_user,
    _tsundere_next,
)

from .graph_parts.postprocess import (
    _dialogue_surface_issues,
    _effective_natural_dialog_target_flags,
    _is_plain_contact_ping,
    _producer_surface_issues,
    _response_style_hint,
    _sanitize_final_answer,
)

from .graph_parts.prompt_helpers import (
    _compact_interaction_carryover_hint,
)

from .graph_parts.prompting import (
    _build_task_prompt,
)

from .graph_parts.relational import (
    _prefer_refreshed_relationship_state,
    _recent_interaction_carryover,
    _relationship_runtime_snapshot,
    _seeded_interaction_carryover_from_state,
    _worldline_focus,
)

from .graph_parts.rewrite import (
    _light_dialog_rewrite_notes,
    _relationship_weather_rewrite_guidance,
    _rewrite_light_dialog_answer,
    _rewrite_natural_dialog_answer,
    _should_run_light_dialog_rewrite,
    _should_run_natural_dialog_rewrite,
)

from .graph_parts.runtime_prompting import (
    _compact_appraisal_hint,
    _compact_behavior_hint,
    _emotion_prompt_hint,
    _prompt_state_runtime_brief,
    _prompt_state_snapshot,
    _renderer_guidance,
    _runtime_state_level,
)

from .graph_parts.runtime_services import (
    _audit_jsonl,
    _get_store,
    _get_tool_bundle,
    _invoke_model_with_retries,
    _is_transient_model_error,
    _model,
)

from .graph_parts.semantic_narrative import (
    _compact_semantic_narrative_hint,
    _self_narrative_anchor_lines,
    _semantic_narrative_appraisal_hint,
    _semantic_narrative_decay_multiplier,
    _semantic_narrative_decay_rate,
    _semantic_narrative_event_bonus,
    _semantic_narrative_profile,
)

from .graph_parts.tool_policies import (
    MEMORY_WRITE_TOOLS,
    WORLDLINE_ABLATION_READ_TOOLS,
)

from .graph_parts.tool_runtime import (
    _build_evidence_from_tool_result,
    _invoke_tool,
    _memory_guard_check,
)

from .graph_parts.tooling import (
    _build_followup_for_upgrade,
    _explicit_commitment_summary,
    _explicit_memory_request,
    _extract_skill_name,
    _extract_skill_steps,
    _infer_memory_tool_calls,
    _parse_explicit_tool_call,
    _parse_set_profile_args,
)

from .graph_parts.turn_events import (
    _append_recent_events,
    _appraisal_event_context,
    _build_current_event,
    _commitment_life_window_family,
    _event_frame,
    _event_tags,
    _is_silent_behavior_event,
    _normalize_event_override,
    _parse_due_at_timestamp,
    _promote_due_commitment_event,
)

from .persona_authority import get_persona_core_authority

_default_persona_core = get_persona_core_authority

__all__ = [
    "ThreadState",
    "build_graph",
    "build_implicit_idle_state_update",
    "reset_runtime_caches",
    "_build_turn_appraisal_prompt",
    "_coerce_appraisal_payload",
    "_explicit_boundary_test",
    "_explicit_hierarchy_pressure",
    "_extract_json_block",
    "_finalize_turn_appraisal_payload",
    "_invoke_turn_appraisal",
    "_postprocess_appraisal_payload",
    "_recent_dialogue_lines",
    "_should_use_llm_appraisal",
    "_soft_accept_appraisal_payload",
    "_allostasis_next",
    "_behavior_policy_from_state",
    "_bond_next",
    "_emotion_decay_target",
    "_emotion_next",
    "_behavior_agenda_entry_from_plan",
    "_behavior_agenda_next_recheck_min",
    "_behavior_agenda_should_release",
    "_merge_behavior_agenda",
    "_normalize_behavior_agenda",
    "_promote_due_behavior_action_event",
    "_promote_due_behavior_agenda_event",
    "_promote_due_behavior_plan_event",
    "_behavior_action_from_state",
    "_behavior_plan_carryover_snapshot",
    "_behavior_plan_from_action",
    "_compact_behavior_action_hint",
    "_clamp01",
    "_clamp_signed",
    "_norm_text",
    "_now_ts",
    "_safe_json",
    "_sanitize_message",
    "_sanitize_obj",
    "_active_appraisal_payload",
    "_appraisal_target_weight",
    "_blend_state_value",
    "_counterpart_assessment_next",
    "_counterpart_dialogue_mode_profile",
    "_counterpart_perception_profile",
    "_counterpart_self_opening_profile",
    "_counterpart_window_profile",
    "_event_behavior_preference_lines",
    "_event_behavior_preference_scene",
    "_light_free_dialog_counterpart_line",
    "_light_free_dialog_state_hint",
    "_load_event_to_behavior_preference_bank",
    "_load_selfhood_preference_bank",
    "_load_user_style_expression_bank",
    "_narrative_actor_profile",
    "_plain_contact_ping_needs_relational_guard",
    "_scene_persona_axioms",
    "_selfhood_preference_lines",
    "_subjective_runtime_state_hint",
    "_user_style_preference_lines",
    "_daily_surface_alignment_metrics",
    "_daily_surface_preference_lines",
    "_daily_surface_profile",
    "_daily_surface_prompt_similarity",
    "_effective_relationship_weather",
    "_ensure_response_structure",
    "_flatten_surface_example",
    "_generation_profile",
    "_is_free_dialog_style",
    "_is_light_free_dialog_turn",
    "_load_daily_surface_preference_corpus",
    "_looks_like_daily_surface_scene",
    "_normalize_surface_prompt_text",
    "_reply_opener_signature",
    "_reply_repetition_signature",
    "_stable_unit_interval",
    "_surface_drift_marker_hits",
    "_text_similarity",
    "_canon_guard",
    "_ooc_risk",
    "_persona_gap",
    "_auto_reconsolidate_after_tool",
    "_passive_evolution_memory_update",
    "_recent_summary_overlap",
    "_record_semantic_self_evidence",
    "_refresh_semantic_self_narratives",
    "_resolve_matching_tensions_from_summary",
    "_semantic_self_evidence_records",
    "_selfhood_preference_scene",
    "_available_tools_for_state",
    "_node_call_model",
    "_node_prepare_turn",
    "_active_counterpart_profile",
    "_active_persona_core",
    "_canon_counterpart_profile",
    "_canon_okabe_recontact_baseline",
    "_canon_persona_labels",
    "_ensure_canon_counterpart_defaults",
    "_has_relational_history_for_seed",
    "_is_canon_amadeus_okabe_context",
    "_is_external_probe_context",
    "_prefer_explicit_state_dict",
    "_science_mode_from_context",
    "_science_mode_from_user",
    "_tsundere_next",
    "_dialogue_surface_issues",
    "_effective_natural_dialog_target_flags",
    "_is_plain_contact_ping",
    "_producer_surface_issues",
    "_response_style_hint",
    "_sanitize_final_answer",
    "_compact_interaction_carryover_hint",
    "_build_task_prompt",
    "_prefer_refreshed_relationship_state",
    "_recent_interaction_carryover",
    "_relationship_runtime_snapshot",
    "_seeded_interaction_carryover_from_state",
    "_worldline_focus",
    "_light_dialog_rewrite_notes",
    "_relationship_weather_rewrite_guidance",
    "_rewrite_light_dialog_answer",
    "_rewrite_natural_dialog_answer",
    "_should_run_light_dialog_rewrite",
    "_should_run_natural_dialog_rewrite",
    "_compact_appraisal_hint",
    "_compact_behavior_hint",
    "_emotion_prompt_hint",
    "_prompt_state_runtime_brief",
    "_prompt_state_snapshot",
    "_renderer_guidance",
    "_runtime_state_level",
    "_audit_jsonl",
    "_get_store",
    "_get_tool_bundle",
    "_invoke_model_with_retries",
    "_is_transient_model_error",
    "_model",
    "_compact_semantic_narrative_hint",
    "_self_narrative_anchor_lines",
    "_semantic_narrative_appraisal_hint",
    "_semantic_narrative_decay_multiplier",
    "_semantic_narrative_decay_rate",
    "_semantic_narrative_event_bonus",
    "_semantic_narrative_profile",
    "MEMORY_WRITE_TOOLS",
    "WORLDLINE_ABLATION_READ_TOOLS",
    "_build_evidence_from_tool_result",
    "_invoke_tool",
    "_memory_guard_check",
    "_build_followup_for_upgrade",
    "_explicit_commitment_summary",
    "_explicit_memory_request",
    "_extract_skill_name",
    "_extract_skill_steps",
    "_infer_memory_tool_calls",
    "_parse_explicit_tool_call",
    "_parse_set_profile_args",
    "_append_recent_events",
    "_appraisal_event_context",
    "_build_current_event",
    "_commitment_life_window_family",
    "_event_frame",
    "_event_tags",
    "_is_silent_behavior_event",
    "_normalize_event_override",
    "_parse_due_at_timestamp",
    "_promote_due_commitment_event",
    "_default_persona_core",
]
