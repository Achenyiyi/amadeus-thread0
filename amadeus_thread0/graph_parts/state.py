from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class EventPayload(TypedDict, total=False):
    kind: str
    source: str
    text: str
    effective_text: str
    semantic_goal: str
    primary_motive: str
    motive_tension: str
    goal_frame: str
    response_style_hint: str
    science_mode: bool
    continuation_mode: bool
    counterpart_name: str
    event_frame: str
    appraisal_label: str
    appraisal_confidence: float
    tags: list[str]
    created_at: int
    idle_minutes: int
    derived_from_plan_kind: str
    scheduled_after_min: int
    trigger_family: str
    commitment_id: int
    due_at: str
    carryover_mode: str
    carryover_strength: float
    relationship_weather: str
    presence_residue: float
    ambient_resonance: float
    self_activity_momentum: float
    attention_target_hint: str
    nonverbal_signal_hint: str
    perception: "PerceptionContextPayload"


class PerceptionContextPayload(TypedDict, total=False):
    event_id: str
    thread_id: str
    turn_id: str
    channel: str
    modality: str
    source_role: str
    trust_tier: str
    salience: float
    interruptibility: str
    delivery_mode: str
    is_proactive: bool


class SessionContextPayload(TypedDict, total=False):
    thread_id: str
    turn_id: str
    turn_started_at: int
    user_id: str
    checkpoint_id: str


class BehaviorActionPayload(TypedDict, total=False):
    channel: str
    interaction_mode: str
    approach_style: str
    engagement_level: float
    initiative_level: float
    followup_intent: str
    task_focus: str
    affect_surface: str
    silence_ok: bool
    proactive_checkin_readiness: float
    primary_motive: str
    motive_tension: str
    goal_frame: str
    action_target: str
    deferred_action_family: str
    timing_window_min: int
    attention_target: str
    nonverbal_signal: str
    initiative_shape: str
    disclosure_posture: str
    note: str
    relationship_weather: str
    window_profile: "BehaviorWindowProfilePayload"


class BehaviorWindowProfilePayload(TypedDict, total=False):
    profile_type: str
    event_kind: str
    family: str
    trigger_family: str
    stance: str
    scene: str
    decision: str
    maturity: float
    required_maturity: float
    readiness: float
    required_readiness: float
    continuity_bonus: float
    continuity_discount: float
    invite_ready: bool
    reopen_ready: bool
    recheck_min: int
    carryover_mode: str
    carryover_strength: float
    event_carryover_mode: str
    event_carryover_strength: float
    presence_residue: float
    ambient_resonance: float
    self_activity_momentum: float
    recontact_echo: float
    own_rhythm_load: float


class BehaviorPlanPayload(TypedDict, total=False):
    kind: str
    target: str
    scheduled_after_min: int
    trigger_family: str
    allow_interrupt: bool
    primary_motive: str
    motive_tension: str
    goal_frame: str
    note: str
    carryover_mode: str
    carryover_strength: float
    relationship_weather: str
    attention_target: str
    nonverbal_signal: str
    presence_residue: float
    ambient_resonance: float
    self_activity_momentum: float


class BehaviorAgendaEntryPayload(TypedDict, total=False):
    agenda_id: str
    kind: str
    target: str
    scheduled_after_min: int
    expires_after_min: int
    base_priority: float
    priority: float
    trigger_family: str
    allow_interrupt: bool
    primary_motive: str
    motive_tension: str
    goal_frame: str
    note: str
    source_event_kind: str
    created_at: int
    status: str
    hold_count: int
    last_recheck_at_min: int
    carryover_mode: str
    carryover_strength: float
    relationship_weather: str
    attention_target: str
    nonverbal_signal: str
    presence_residue: float
    ambient_resonance: float
    self_activity_momentum: float
    continuity_anchor: float
    own_rhythm_anchor: float
    recontact_anchor: float
    boundary_anchor: float
    memory_anchor: float
    semantic_continuity_depth: float
    semantic_identity_gravity: float
    long_term_axis_count: int
    lineage_gravity: float
    contact_lineage: float
    repair_lineage: float
    boundary_lineage: float
    selfhood_lineage: float
    agency_lineage: float


class InteractionCarryoverPayload(TypedDict, total=False):
    source_event_kind: str
    source_behavior_mode: str
    source_action_target: str
    source_primary_motive: str
    source_motive_tension: str
    source_goal_frame: str
    source_text: str
    source_tags: list[str]
    carryover_mode: str
    strength: float
    relationship_weather: str
    idle_minutes: int
    source_turn_gap: int
    attention_target: str
    nonverbal_signal: str
    note: str
    created_at: int


class AgendaLifecycleResiduePayload(TypedDict, total=False):
    kind: str
    source_event_kind: str
    trigger_family: str
    carryover_mode: str
    carryover_strength: float
    relationship_weather: str
    hold_count: int
    idle_minutes: int
    attention_target: str
    nonverbal_signal: str
    note: str
    source_tags: list[str]
    presence_residue: float
    ambient_resonance: float
    self_activity_momentum: float
    continuity_anchor: float
    own_rhythm_anchor: float
    recontact_anchor: float
    boundary_anchor: float
    memory_anchor: float
    semantic_continuity_depth: float
    semantic_identity_gravity: float
    long_term_axis_count: int
    lineage_gravity: float
    contact_lineage: float
    repair_lineage: float
    boundary_lineage: float
    selfhood_lineage: float
    agency_lineage: float
    own_rhythm_bias: float
    recontact_cooldown: float
    counterpart_scene_bias: str
    counterpart_boundary_delta: float
    created_at: int


class ThreadState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    final_text: str
    persona_core_override: dict[str, Any]
    counterpart_profile_override: dict[str, Any]
    persona_override_mode: str
    counterpart_override_mode: str
    authority_trace: dict[str, Any]
    relationship: dict[str, Any]
    semantic_narrative_profile: dict[str, Any]
    world_model_state: dict[str, Any]
    evolution_state: dict[str, Any]
    reconsolidation_snapshot: dict[str, Any]
    persona_state: dict[str, Any]
    emotion_state: dict[str, Any]
    bond_state: dict[str, Any]
    allostasis_state: dict[str, Any]
    counterpart_assessment: dict[str, Any]
    behavior_policy: dict[str, Any]
    behavior_action: BehaviorActionPayload
    behavior_plan: BehaviorPlanPayload
    behavior_agenda: list[BehaviorAgendaEntryPayload]
    behavior_queue: list[BehaviorAgendaEntryPayload]
    turn_appraisal: dict[str, Any]
    response_style_hint: str
    science_mode: bool
    tsundere_intensity: float
    canon_risk_score: float
    canon_guard: dict[str, Any]
    ooc_detector: dict[str, Any]
    worldline_focus: list[dict[str, Any]]
    evidence_pack: list[dict[str, Any]]
    event_override: EventPayload
    session_context: SessionContextPayload
    current_event: EventPayload
    recent_events: list[EventPayload]
    interaction_carryover: InteractionCarryoverPayload
    agenda_lifecycle_residue: AgendaLifecycleResiduePayload
    pending_utterance_fragment: str
    pending_user_goal: str
    retrieved_context: dict[str, Any]
    claim_links: list[dict[str, Any]]
    tool_round: int
    approval_actions: list[dict[str, Any]]
    toolset_unlocks: dict[str, int]
    last_external_tools: list[str]
    memory_guard_checked: int
    memory_guard_blocked: int

