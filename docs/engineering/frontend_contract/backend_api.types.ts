export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonRecord | JsonValue[] | undefined;

export interface JsonRecord {
  [key: string]: JsonValue;
}

export type BackendKind =
  | "memory_snapshot"
  | "worldline_view"
  | "bond_view"
  | "sources_view"
  | "persona_view"
  | "appraisal_view"
  | "behavior_queue_view"
  | "checkpoint_history"
  | "current_checkpoint"
  | "thread_inventory"
  | "runtime_layout"
  | "environment_summary"
  | "runtime_productization"
  | "operator_console_rc"
  | "event_round"
  | "assistant_turn";

export interface BackendEnvelope<K extends BackendKind, P> {
  schema_version: "backend.v1";
  generated_at: number;
  kind: K;
  thread_id: string;
  payload: P;
  meta: JsonRecord;
}

export interface ClaimLink extends JsonRecord {
  claim_excerpt?: string;
  source_ids?: number[];
}

export interface SourceRef extends JsonRecord {
  id?: number | string;
  tool_name?: string;
  title?: string;
  url?: string;
  query?: string;
}

export interface RelationshipState extends JsonRecord {
  stage: string;
  affinity_score: number;
  trust_score: number;
  notes: string;
}

export interface ContinuityAxis {
  semantic: number;
  world: number;
}

export interface TopNarrativeItem {
  category: string;
  score: number;
  reactivated: boolean;
  text: string;
  primary_motive?: string;
  motive_tension?: string;
  counterpart_snapshot?: JsonRecord;
  proactive_continuity?: JsonRecord;
}

export interface LongTermSelfNarrativeItem {
  category: string;
  score: number;
  horizon_tag: string;
  text: string;
  prompt_text: string;
  primary_motive?: string;
  motive_tension?: string;
  sedimentation_score?: number;
  persistence_score?: number;
  integration_score?: number;
  support_span_s?: number;
  reactivation_hits?: number;
  identity_strength?: number;
  lineage_depth?: number;
  counterpart_snapshot?: JsonRecord;
  proactive_continuity?: JsonRecord;
}

export interface SemanticContinuitySummary {
  history_weight: number;
  dominant_category: string;
  active_categories: string[];
  reactivated_categories: string[];
  summary_lines: string[];
  anchor_lines: string[];
  top_narratives: TopNarrativeItem[];
  frozen_anchor_bundle?: JsonRecord;
}

export interface IdentityContinuitySummary {
  identity_lines: string[];
  identity_prompt_lines: string[];
  dominant_identity_category: string;
  long_term_self_narratives: LongTermSelfNarrativeItem[];
}

export interface WorldDynamicsSummary {
  bond_depth: number;
  tension_load: number;
  selfhood_load: number;
  agency_load: number;
  memory_gravity: number;
  companionship_pull: number;
  task_pull: number;
}

export interface CurrentTurnSummary {
  event_kind: string;
  emotion_label: string;
  trust: number;
  closeness: number;
  hurt: number;
  counterpart_summary?: string;
  counterpart_stance: string;
  counterpart_scene: string;
  counterpart_respect_level?: number;
  counterpart_reciprocity?: number;
  counterpart_boundary_pressure?: number;
  counterpart_reliability_read?: number;
  counterpart_profile?: JsonRecord;
  behavior_mode: string;
  action_target: string;
  channel?: string;
  approach_style?: string;
  engagement_level?: number;
  initiative_level?: number;
  followup_intent?: string;
  task_focus?: string;
  affect_surface?: string;
  silence_ok?: boolean;
  proactive_checkin_readiness?: number;
  deferred_action_family?: string;
  attention_target?: string;
  nonverbal_signal?: string;
  initiative_shape?: string;
  disclosure_posture?: string;
  primary_motive: string;
  motive_tension: string;
  goal_frame: string;
  behavior_note?: string;
  behavior_action_embodied_context?: DigitalBodyConsequenceSummary | JsonRecord;
  timing_window_min?: number;
  behavior_weather: string;
  carryover_mode: string;
  carryover_strength: number;
  carryover_weather: string;
  recon_event_kind: string;
  recon_interaction_frame: string;
  behavior_consequence_kind: string;
  behavior_consequence_summary: string;
  behavior_consequence_embodied_context?: DigitalBodyConsequenceSummary | JsonRecord;
  semantic_anchor_bundle?: JsonRecord;
  autonomy_mode?: string;
  autonomy_origin?: string;
  autonomy_reason?: string;
  autonomy_confidence?: number;
  autonomy_requires_approval?: boolean;
  action_packet_count?: number;
  autonomy_block_reason?: string;
  digital_body_surface?: string;
  digital_body_access_mode?: string;
  digital_body_pending_approval_count?: number;
  digital_body_retry_after_s?: number;
  digital_body_cooldown_scope?: string;
  digital_body_session_continuity?: string;
  digital_body_session_expires_in_s?: number;
  digital_body_session_recovery_mode?: string;
  digital_body_artifact_continuity?: string;
  digital_body_active_artifact_kind?: string;
  digital_body_active_artifact_label?: string;
  digital_body_artifact_reacquisition_mode?: string;
  digital_body_consequence_kind?: string;
  digital_body_consequence_summary?: string;
  digital_body_procedural_growth?: boolean;
  digital_body_requested_help?: boolean;
  digital_body_environmental_friction?: boolean;
}

export interface CapabilityStep extends JsonRecord {
  kind?: string;
  name?: string;
  target?: string;
  status?: string;
  requires_approval?: boolean;
  note?: string;
}

export interface AccessAcquireProposal extends JsonRecord {
  target?: string;
  mode?: string;
  path_kind?: string;
  summary?: string;
  operator_action?: string;
  grants?: string[];
  requires_operator?: boolean;
  resolved_grants?: string[];
  pending_grants?: string[];
  completion_ratio?: number;
}

export interface AssistRequest extends JsonRecord {
  kind?: string;
  message?: string;
  requested_access?: string[];
  missing_access?: string[];
  selected_access_proposal?: AccessAcquireProposal | JsonRecord;
  requires_manual_takeover?: boolean;
  resume_mode?: string;
  proposal_id?: string;
  profile_id?: string;
  page_ref?: string;
  tab_id?: string;
}

export interface ActionPacket extends JsonRecord {
  proposal_id?: string;
  origin?: string;
  intent?: string;
  status?: string;
  risk?: string;
  requires_approval?: boolean;
  capability_steps?: CapabilityStep[];
  expected_effect?: string;
  result_summary?: string;
  writeback_ready?: boolean;
  linked_queue_id?: string;
  tool_name?: string;
  block_reason?: string;
  assist_request?: AssistRequest | JsonRecord;
  access_acquire_proposals?: AccessAcquireProposal[];
  selected_access_proposal?: AccessAcquireProposal | JsonRecord;
  execution_spec?: SandboxExecutionPayload | JsonRecord;
  execution_preview?: JsonRecord;
  execution_result?: JsonRecord;
  browser_execution_spec?: JsonRecord;
  browser_execution_preview?: JsonRecord;
  browser_execution_result?: JsonRecord;
}

export interface AutonomyIntent extends JsonRecord {
  mode?: string;
  origin?: string;
  reason?: string;
  confidence?: number;
  own_rhythm_weight?: number;
  continuity_weight?: number;
  requires_approval?: boolean;
  primary_proposal_id?: string;
}

export interface ActionTraceItem extends JsonRecord {
  proposal_id?: string;
  origin?: string;
  intent?: string;
  status?: string;
  event?: string;
  risk?: string;
  source?: string;
  result_summary?: string;
  block_reason?: string;
  requires_approval?: boolean;
}

export interface AutonomyEnvelope {
  intent: AutonomyIntent;
  action_packets: ActionPacket[];
  pending_approval: ActionPacket | JsonRecord;
  execution_trace: ActionTraceItem[];
  block_reason: string;
}

export interface SandboxExecutionPayload extends JsonRecord {
  runner_kind?: string;
  isolation_level?: string;
  image_ref?: string;
  network_policy?: string;
  workspace_root_kind?: string;
  executor?: string;
  profile?: string;
  argv?: string[];
  cwd?: string;
  allowed_roots?: string[];
  timeout_s?: number;
  writes_expected?: boolean;
  expected_artifacts?: string[];
}

export interface SkillCatalogEntry extends JsonRecord {
  skill_id: string;
  name?: string;
  description?: string;
  version?: string;
  kind?: string;
  source?: string;
  status?: string;
  trust_tier?: string;
  required_surfaces?: string[];
  allowed_tools?: string[];
  sandbox_profiles?: string[];
}

export interface ActiveSkillEntry extends SkillCatalogEntry {
  skill_excerpt?: string;
}

export interface SkillPendingApproval extends JsonRecord {
  proposal_id?: string;
  operation?: string;
  skill_id?: string;
  resolved_version?: string;
  source?: string;
  hash?: string;
  requested_permissions?: string[];
  sandbox_profiles?: string[];
  verification_summary?: string;
}

export interface SkillsEnvelope {
  installed: SkillCatalogEntry[];
  matched: SkillCatalogEntry[];
  active: ActiveSkillEntry[];
  manual_overrides: JsonRecord;
  pending_approval: SkillPendingApproval | JsonRecord;
}

export interface DigitalBodySessionStatePayload extends JsonRecord {
  continuity?: string;
  expires_in_s?: number;
  recovery_mode?: string;
  retry_after_s?: number;
  cooldown_scope?: string;
  browser_session?: string;
  needs_recovery?: boolean;
}

export interface DigitalBodyAccountStateDetailPayload extends JsonRecord {
  browser_session?: string;
  login_state?: string;
  cookie_state?: string;
  api_key_state?: string;
  account_available?: boolean;
  cookie_available?: boolean;
  api_key_available?: boolean;
}

export interface DigitalBodyQuotaStateDetailPayload extends JsonRecord {
  provider_state?: string;
  retry_after_s?: number;
  cooldown_scope?: string;
  available?: boolean;
  cooldown_active?: boolean;
}

export interface DigitalBodyPermissionStatePayload extends JsonRecord {
  pending_approval_count?: number;
  external_mutation_pending?: boolean;
  missing_access?: string[];
  requestable_access?: string[];
  access_acquire_proposals?: AccessAcquireProposal[];
  selected_access_proposal?: AccessAcquireProposal | JsonRecord;
  resolved_grants?: string[];
  pending_grants?: string[];
  completion_ratio?: number;
  approval_state?: string;
}

export interface DigitalBodySandboxStatePayload extends JsonRecord {
  availability?: string;
  allowed_roots?: string[];
  execution_policy?: string;
  last_status?: string;
  runner_kind?: string;
  isolation_level?: string;
  image_ref?: string;
  network_policy?: string;
  workspace_root_kind?: string;
  last_command_profile?: string;
  last_exit_code?: number;
  last_run_id?: string;
  arbitrary_execution?: boolean;
}

export interface DigitalBodyBrowserRuntimeStatePayload extends JsonRecord {
  availability?: string;
  profile_root?: string;
  context_status?: string;
  active_page_id?: string;
  active_tab_count?: number;
  downloads_dir?: string;
  last_action_status?: string;
  last_run_id?: string;
  manual_takeover_required?: boolean;
  runner_kind?: string;
  isolation_level?: string;
}

export interface DigitalBodyAccessPayload extends JsonRecord {
  mode?: string;
  conditions?: string[];
  block_reason?: string;
  retry_after_s?: number;
  cooldown_scope?: string;
  session_continuity?: string;
  session_expires_in_s?: number;
  session_recovery_mode?: string;
  pending_approval_count?: number;
  external_mutation_pending?: boolean;
  granted_toolsets?: string[];
  missing_access?: string[];
  requestable_access?: string[];
  browser_session?: string;
  account_state?: string;
  cookie_state?: string;
  api_key_state?: string;
  quota_state?: string;
  filesystem_state?: string;
  sandbox_mode?: string;
  network_access?: string;
  access_acquire_proposals?: AccessAcquireProposal[];
  selected_access_proposal?: AccessAcquireProposal | JsonRecord;
  session_state?: DigitalBodySessionStatePayload | JsonRecord;
  account_state_detail?: DigitalBodyAccountStateDetailPayload | JsonRecord;
  quota_state_detail?: DigitalBodyQuotaStateDetailPayload | JsonRecord;
  permission_state?: DigitalBodyPermissionStatePayload | JsonRecord;
  sandbox_state?: DigitalBodySandboxStatePayload | JsonRecord;
  browser_runtime_state?: DigitalBodyBrowserRuntimeStatePayload | JsonRecord;
}

export interface DigitalBodyResourcePayload extends JsonRecord {
  behavior_queue_depth?: number;
  action_packet_count?: number;
  pending_approval_count?: number;
  queued_packet_count?: number;
  executing_packet_count?: number;
  completed_packet_count?: number;
  blocked_packet_count?: number;
  external_tool_count?: number;
  artifact_continuity?: string;
  active_artifact_kind?: string;
  active_artifact_ref?: string;
  active_artifact_label?: string;
  artifact_age_s?: number;
  artifact_reacquisition_mode?: string;
  artifact_carrier?: string;
  artifact_source_ref_ids?: number[];
  preferred_source_ref_id?: number;
  preferred_anchor_reason?: string;
  artifact_source_url?: string;
  artifact_source_query?: string;
  artifact_source_title?: string;
  artifact_source_tool_name?: string;
  workspace_root?: string;
  browser_profile_id?: string;
  browser_tab_id?: string;
}

export interface DigitalBodyPayload extends JsonRecord {
  active_surface?: string;
  perception_channels?: string[];
  action_channels?: string[];
  world_surfaces?: string[];
  available_toolsets?: string[];
  active_tools?: string[];
  access_state?: DigitalBodyAccessPayload;
  resource_state?: DigitalBodyResourcePayload;
  body_constraints?: string[];
}

export interface DigitalBodyAccessSummary extends JsonRecord {
  mode: string;
  conditions: string[];
  block_reason: string;
  retry_after_s: number;
  cooldown_scope: string;
  session_continuity: string;
  session_expires_in_s: number;
  session_recovery_mode: string;
  pending_approval_count: number;
  external_mutation_pending: boolean;
  granted_toolsets: string[];
  missing_access: string[];
  requestable_access: string[];
  browser_session: string;
  account_state: string;
  cookie_state: string;
  api_key_state: string;
  quota_state: string;
  filesystem_state: string;
  sandbox_mode: string;
  network_access: string;
  access_acquire_proposals: AccessAcquireProposal[];
  selected_access_proposal: AccessAcquireProposal | JsonRecord;
  session_state: DigitalBodySessionStatePayload | JsonRecord;
  account_state_detail: DigitalBodyAccountStateDetailPayload | JsonRecord;
  quota_state_detail: DigitalBodyQuotaStateDetailPayload | JsonRecord;
  permission_state: DigitalBodyPermissionStatePayload | JsonRecord;
  sandbox_state: DigitalBodySandboxStatePayload | JsonRecord;
  browser_runtime_state: DigitalBodyBrowserRuntimeStatePayload | JsonRecord;
}

export interface DigitalBodyResourceSummary extends JsonRecord {
  behavior_queue_depth: number;
  action_packet_count: number;
  pending_approval_count: number;
  queued_packet_count: number;
  executing_packet_count: number;
  completed_packet_count: number;
  blocked_packet_count: number;
  external_tool_count: number;
  artifact_continuity: string;
  active_artifact_kind: string;
  active_artifact_ref: string;
  active_artifact_label: string;
  artifact_age_s: number;
  artifact_reacquisition_mode: string;
  artifact_carrier: string;
  artifact_source_ref_ids: number[];
  preferred_source_ref_id: number;
  preferred_anchor_reason: string;
  artifact_source_url: string;
  artifact_source_query: string;
  artifact_source_title: string;
  artifact_source_tool_name: string;
  workspace_root: string;
  browser_profile_id: string;
  browser_tab_id: string;
}

export interface DigitalBodySummary extends JsonRecord {
  active_surface: string;
  perception_channels: string[];
  action_channels: string[];
  world_surfaces: string[];
  available_toolsets: string[];
  active_tools: string[];
  access: DigitalBodyAccessSummary;
  resources: DigitalBodyResourceSummary;
  constraints: string[];
}

export interface DigitalBodyConsequenceSummary extends JsonRecord {
  kind: string;
  summary: string;
  access_mode: string;
  active_surface: string;
  world_surfaces: string[];
  missing_access: string[];
  requested_access: string[];
  granted_toolsets: string[];
  active_tools: string[];
  block_reason: string;
  retry_after_s: number;
  cooldown_scope: string;
  session_continuity: string;
  session_expires_in_s: number;
  session_recovery_mode: string;
  artifact_continuity: string;
  active_artifact_kind: string;
  active_artifact_ref: string;
  active_artifact_label: string;
  artifact_age_s: number;
  artifact_reacquisition_mode: string;
  artifact_carrier: string;
  artifact_source_ref_ids: number[];
  artifact_source_url: string;
  artifact_source_query: string;
  artifact_source_title: string;
  artifact_source_tool_name: string;
  primary_proposal_id: string;
  primary_status: string;
  primary_origin: string;
  primary_intent: string;
  primary_tool_name: string;
  procedural_growth: boolean;
  environmental_friction: boolean;
  requested_help: boolean;
  access_acquire_proposals: AccessAcquireProposal[];
  selected_access_proposal: AccessAcquireProposal | JsonRecord;
  session_state?: DigitalBodySessionStatePayload | JsonRecord;
  account_state_detail?: DigitalBodyAccountStateDetailPayload | JsonRecord;
  quota_state_detail?: DigitalBodyQuotaStateDetailPayload | JsonRecord;
  permission_state?: DigitalBodyPermissionStatePayload | JsonRecord;
  sandbox_state?: DigitalBodySandboxStatePayload | JsonRecord;
  browser_runtime_state?: DigitalBodyBrowserRuntimeStatePayload | JsonRecord;
  workspace_root?: string;
  workspace_root_kind?: string;
  sandbox_runner_kind?: string;
  sandbox_isolation_level?: string;
  sandbox_image_ref?: string;
  sandbox_network_policy?: string;
  skill_effects?: JsonRecord[];
  procedural_continuity?: JsonRecord;
}

export interface EventResidueSummary {
  event_kind: string;
  source?: string;
  event_frame?: string;
  response_style_hint?: string;
  science_mode?: boolean;
  continuation_mode?: boolean;
  counterpart_name?: string;
  appraisal_label?: string;
  appraisal_confidence?: number;
  created_at?: number;
  tags?: string[];
  thread_id?: string;
  turn_id?: string;
  event_id?: string;
  trigger_family: string;
  derived_from_plan_kind?: string;
  commitment_id?: number;
  due_at?: string;
  carryover_mode: string;
  carryover_strength: number;
  relationship_weather: string;
  channel?: string;
  modality?: string;
  source_role?: string;
  trust_tier?: string;
  salience?: number;
  interruptibility?: string;
  delivery_mode?: string;
  is_proactive?: boolean;
  presence_residue: number;
  ambient_resonance: number;
  self_activity_momentum: number;
  attention_target_hint?: string;
  nonverbal_signal_hint?: string;
  scheduled_after_min: number;
  idle_minutes: number;
  digital_body_consequence?: DigitalBodyConsequenceSummary | JsonRecord;
}

export interface AgendaLifecycleSummary {
  kind: string;
  source_event_kind: string;
  trigger_family: string;
  carryover_mode: string;
  carryover_strength: number;
  relationship_weather: string;
  hold_count: number;
  idle_minutes: number;
  attention_target: string;
  nonverbal_signal: string;
  presence_residue: number;
  ambient_resonance: number;
  self_activity_momentum: number;
  continuity_anchor: number;
  own_rhythm_anchor: number;
  recontact_anchor: number;
  boundary_anchor: number;
  memory_anchor: number;
  semantic_continuity_depth: number;
  semantic_identity_gravity: number;
  lineage_gravity: number;
  contact_lineage: number;
  repair_lineage?: number;
  boundary_lineage: number;
  selfhood_lineage?: number;
  agency_lineage: number;
  long_term_axis_count?: number;
  own_rhythm_bias: number;
  recontact_cooldown: number;
  counterpart_scene_bias: string;
  counterpart_boundary_delta: number;
  created_at: number;
  source_tags: string[];
  note: string;
}

export interface OpeningWindowSummary extends JsonRecord {
  profile_type: string;
  event_kind: string;
  family: string;
  trigger_family: string;
  stance: string;
  scene: string;
  decision: string;
  maturity?: number;
  required_maturity?: number;
  invite_ready?: boolean;
  readiness?: number;
  required_readiness?: number;
  reopen_ready?: boolean;
  score?: number;
  required?: number;
  ready?: boolean;
  gap: number;
  recheck_min: number;
  continuity_bonus: number;
  continuity_discount: number;
  carryover_mode: string;
  carryover_strength: number;
  event_carryover_mode: string;
  event_carryover_strength: number;
  presence_residue: number;
  ambient_resonance: number;
  self_activity_momentum: number;
  recontact_echo: number;
  own_rhythm_load: number;
}

export interface BehaviorPlanSummary {
  kind: string;
  target: string;
  trigger_family: string;
  scheduled_after_min: number;
  allow_interrupt?: boolean;
  primary_motive: string;
  motive_tension: string;
  goal_frame: string;
  carryover_mode: string;
  carryover_strength: number;
  relationship_weather: string;
  attention_target?: string;
  nonverbal_signal?: string;
  note?: string;
  presence_residue?: number;
  ambient_resonance?: number;
  self_activity_momentum?: number;
}

export interface BehaviorQueueItem extends JsonRecord {
  agenda_id?: string;
  kind?: string;
  target?: string;
  status?: string;
  trigger_family?: string;
  scheduled_after_min?: number;
  expires_after_min?: number;
  priority?: number;
  base_priority?: number;
  hold_count?: number;
  last_recheck_at_min?: number;
  allow_interrupt?: boolean;
  primary_motive?: string;
  motive_tension?: string;
  goal_frame?: string;
  source_event_kind?: string;
  created_at?: number;
  carryover_mode?: string;
  carryover_strength?: number;
  relationship_weather?: string;
  presence_residue?: number;
  ambient_resonance?: number;
  self_activity_momentum?: number;
  attention_target?: string;
  nonverbal_signal?: string;
  continuity_anchor?: number;
  own_rhythm_anchor?: number;
  recontact_anchor?: number;
  boundary_anchor?: number;
  memory_anchor?: number;
  semantic_continuity_depth?: number;
  semantic_identity_gravity?: number;
  lineage_gravity?: number;
  contact_lineage?: number;
  repair_lineage?: number;
  boundary_lineage?: number;
  selfhood_lineage?: number;
  agency_lineage?: number;
  long_term_axis_count?: number;
  note?: string;
}

export interface ProactiveContinuityPreviewItem extends JsonRecord {
  id?: number;
  summary?: string;
  kind?: string;
  trace_family?: string;
  source_event_kind?: string;
  trigger_family?: string;
  carryover_mode?: string;
  relationship_weather?: string;
  counterpart_scene_bias?: string;
  hold_count?: number;
  carryover_strength?: number;
  recontact_cooldown?: number;
  presence_residue?: number;
  ambient_resonance?: number;
  self_activity_momentum?: number;
  continuity_anchor?: number;
  own_rhythm_anchor?: number;
  recontact_anchor?: number;
  boundary_anchor?: number;
  memory_anchor?: number;
  semantic_continuity_depth?: number;
  semantic_identity_gravity?: number;
  lineage_gravity?: number;
  contact_lineage?: number;
  repair_lineage?: number;
  boundary_lineage?: number;
  selfhood_lineage?: number;
  agency_lineage?: number;
  long_term_axis_count?: number;
  own_rhythm_bias?: number;
  counterpart_boundary_delta?: number;
  created_at?: number;
  primary_motive?: string;
  motive_tension?: string;
  goal_frame?: string;
  embodied_context?: DigitalBodyConsequenceSummary | JsonRecord;
}

export interface CounterpartAssessmentPreviewItem extends JsonRecord {
  id?: number;
  summary?: string;
  stance?: string;
  scene?: string;
  created_at?: number;
  respect_level?: number;
  reciprocity?: number;
  boundary_pressure?: number;
  reliability_read?: number;
  event_kind?: string;
  interaction_frame?: string;
  primary_motive?: string;
  motive_tension?: string;
  goal_frame?: string;
  assessment_profile?: JsonRecord;
  embodied_context?: DigitalBodyConsequenceSummary | JsonRecord;
}

export interface WorldlineFocusItem extends JsonRecord {
  id: number;
  kind: string;
  text: string;
  status?: string;
  due_at?: string;
  severity?: number;
  affinity_delta?: number;
  trust_delta?: number;
  created_at?: number;
  updated_at?: number;
}

export interface BehaviorActionPayload extends JsonRecord {
  interaction_mode?: string;
  action_target?: string;
  channel?: string;
  approach_style?: string;
  engagement_level?: number;
  initiative_level?: number;
  followup_intent?: string;
  task_focus?: string;
  affect_surface?: string;
  silence_ok?: boolean;
  proactive_checkin_readiness?: number;
  primary_motive?: string;
  motive_tension?: string;
  goal_frame?: string;
  deferred_action_family?: string;
  relationship_weather?: string;
  attention_target?: string;
  nonverbal_signal?: string;
  initiative_shape?: string;
  disclosure_posture?: string;
  note?: string;
  timing_window_min?: number;
  window_profile?: OpeningWindowSummary;
  embodied_context?: DigitalBodyConsequenceSummary | JsonRecord;
}

export interface BehaviorPlanPayload extends JsonRecord {
  kind?: string;
  target?: string;
  trigger_family?: string;
  scheduled_after_min?: number;
  allow_interrupt?: boolean;
  primary_motive?: string;
  motive_tension?: string;
  goal_frame?: string;
  carryover_mode?: string;
  carryover_strength?: number;
  relationship_weather?: string;
  attention_target?: string;
  nonverbal_signal?: string;
  note?: string;
  presence_residue?: number;
  ambient_resonance?: number;
  self_activity_momentum?: number;
  embodied_context?: DigitalBodyConsequenceSummary | JsonRecord;
}

export interface InteractionCarryoverPayload extends JsonRecord {
  source?: string;
  source_event_kind?: string;
  source_behavior_mode?: string;
  source_action_target?: string;
  source_primary_motive?: string;
  source_motive_tension?: string;
  source_goal_frame?: string;
  source_text?: string;
  source_tags?: string[];
  carryover_mode?: string;
  strength?: number;
  relationship_weather?: string;
  idle_minutes?: number;
  source_turn_gap?: number;
  attention_target?: string;
  nonverbal_signal?: string;
  note?: string;
  created_at?: number;
  embodied_context?: DigitalBodyConsequenceSummary | JsonRecord;
}

export interface EvolutionSummary {
  relationship: RelationshipState;
  continuity_vector: {
    presence: ContinuityAxis;
    ambient: ContinuityAxis;
    rhythm: ContinuityAxis;
  };
  semantic_continuity: SemanticContinuitySummary;
  identity_continuity: IdentityContinuitySummary;
  world_dynamics: WorldDynamicsSummary;
  current_turn: CurrentTurnSummary;
  event_residue: EventResidueSummary;
  interaction_carryover: InteractionCarryoverPayload | {};
  agenda_lifecycle: AgendaLifecycleSummary;
  opening_window: OpeningWindowSummary | {};
  behavior_plan: BehaviorPlanSummary;
  behavior_queue_preview: BehaviorQueueItem[];
  autonomy: AutonomyEnvelope;
  digital_body: DigitalBodySummary | {};
  digital_body_consequence: DigitalBodyConsequenceSummary | {};
  worldline_focus_preview: string[];
  worldline_focus_items: WorldlineFocusItem[];
}

export interface AssistantTurnPayload {
  final_text: string;
  emotion_label: string;
  session_context: JsonRecord;
  current_event: JsonRecord;
  turn_summary: EvolutionSummary;
  behavior_action: BehaviorActionPayload;
  behavior_plan: BehaviorPlanPayload;
  interaction_carryover: InteractionCarryoverPayload | JsonRecord;
  counterpart_assessment: JsonRecord;
  agenda_lifecycle_residue: JsonRecord;
  reconsolidation_snapshot: JsonRecord;
  turn_appraisal: JsonRecord;
  autonomy: AutonomyEnvelope;
  skills: SkillsEnvelope;
  digital_body: DigitalBodyPayload | JsonRecord;
  digital_body_consequence: DigitalBodyConsequenceSummary | JsonRecord;
  emotion_state?: JsonRecord;
  bond_state?: JsonRecord;
  allostasis_state?: JsonRecord;
  semantic_narrative_profile?: JsonRecord;
  world_model_state?: JsonRecord;
  evolution_state?: JsonRecord;
  claim_links: ClaimLink[];
  sources: SourceRef[];
  pending_utterance_fragment: string;
  writeback_trace: WritebackTracePayload;
  operator_readback?: JsonRecord;
  living_loop_realism?: JsonRecord;
  embodied_interaction?: JsonRecord;
}

export interface EventRoundPayload {
  final_text: string;
  emotion_label: string;
  session_context: JsonRecord;
  behavior_action: BehaviorActionPayload;
  behavior_plan: BehaviorPlanPayload;
  interaction_carryover: InteractionCarryoverPayload | JsonRecord;
  counterpart_assessment: JsonRecord;
  agenda_lifecycle_residue: JsonRecord;
  reconsolidation_snapshot: JsonRecord;
  current_event: JsonRecord;
  turn_appraisal: JsonRecord;
  autonomy: AutonomyEnvelope;
  skills: SkillsEnvelope;
  digital_body: DigitalBodyPayload | JsonRecord;
  digital_body_consequence: DigitalBodyConsequenceSummary | JsonRecord;
  emotion_state?: JsonRecord;
  bond_state?: JsonRecord;
  allostasis_state?: JsonRecord;
  semantic_narrative_profile?: JsonRecord;
  world_model_state?: JsonRecord;
  evolution_state?: JsonRecord;
  turn_summary: EvolutionSummary;
  writeback_trace: WritebackTracePayload;
  operator_readback?: JsonRecord;
  living_loop_realism?: JsonRecord;
  embodied_interaction?: JsonRecord;
}

export interface WritebackTracePayload {
  turn_started_at: number;
  semantic_self_narratives: JsonRecord[];
  revision_traces: RevisionTraceItem[];
  counterpart_assessment_history: JsonRecord[];
  proactive_continuity_history: JsonRecord[];
}

export interface RevisionTraceItem extends JsonRecord {
  namespace?: string;
  target_id?: string;
  reason?: string;
  source?: string;
  after_summary?: string;
  summary?: string;
  created_at?: number;
  updated_at?: number;
  embodied_context?: DigitalBodyConsequenceSummary | JsonRecord;
}

export interface PersonaViewPayload {
  evolution_summary: EvolutionSummary;
  persona_state: JsonRecord;
  emotion_state: JsonRecord;
  bond_state: JsonRecord;
  allostasis_state: JsonRecord;
  counterpart_assessment: JsonRecord;
  semantic_narrative_profile: JsonRecord;
  world_model_state: JsonRecord;
  evolution_state: JsonRecord;
  reconsolidation_snapshot: JsonRecord;
  turn_appraisal: JsonRecord;
  behavior_policy: JsonRecord;
  behavior_action: BehaviorActionPayload;
  interaction_carryover: InteractionCarryoverPayload | JsonRecord;
  agenda_lifecycle_residue: JsonRecord;
  behavior_plan: BehaviorPlanPayload;
  behavior_queue: BehaviorQueueItem[];
  behavior_queue_summary: BehaviorQueueItem[];
  autonomy: AutonomyEnvelope;
  digital_body: DigitalBodyPayload | JsonRecord;
  digital_body_consequence: DigitalBodyConsequenceSummary | JsonRecord;
  science_mode: boolean;
  tsundere_intensity: number;
  ooc_detector: JsonRecord;
  canon_guard: JsonRecord;
}

export interface WorldlineViewPayload {
  worldline_summary: EvolutionSummary;
  worldline_events: JsonRecord[];
  commitments: JsonRecord[];
  conflict_repair: JsonRecord[];
  unresolved_tensions: JsonRecord[];
  autonomy: AutonomyEnvelope;
  counterpart_assessment_history: JsonRecord[];
  counterpart_assessment_preview: CounterpartAssessmentPreviewItem[];
  proactive_continuity_history: JsonRecord[];
  proactive_continuity_preview: ProactiveContinuityPreviewItem[];
  semantic_self_narratives: JsonRecord[];
  revision_traces: RevisionTraceItem[];
}

export interface BondViewPayload {
  relationship_state: JsonRecord;
  bond_state: JsonRecord;
  autonomy: AutonomyEnvelope;
  relationship_timeline: JsonRecord[];
  counterpart_assessment_history: JsonRecord[];
  counterpart_assessment_preview: CounterpartAssessmentPreviewItem[];
  proactive_continuity_history: JsonRecord[];
  proactive_continuity_preview: ProactiveContinuityPreviewItem[];
  conflict_repair: JsonRecord[];
}

export interface SourcesViewPayload {
  sources: SourceRef[];
  claim_links: ClaimLink[];
}

export interface AppraisalViewPayload {
  turn_appraisal: JsonRecord;
}

export interface BehaviorQueueViewPayload {
  behavior_queue: BehaviorQueueItem[];
  behavior_queue_summary: BehaviorQueueItem[];
  autonomy: AutonomyEnvelope;
}

export interface CheckpointHistoryRow {
  checkpoint_id: string | null;
  next: string[];
}

export interface CheckpointHistoryPayload {
  thread_id: string;
  limit: number;
  total: number;
  rows: CheckpointHistoryRow[];
}

export interface CurrentCheckpointPayload {
  thread_id: string;
  checkpoint_id: string | null;
}

export interface ThreadInventoryPayload {
  checkpoint_thread_ids: string[];
  worldline_dir_ids: string[];
  current_thread_id: string;
}

export interface RuntimeLayoutPayload {
  repo_runtime: JsonRecord;
  current_runtime: JsonRecord | null;
}

export interface EnvironmentSummaryPayload {
  cwd: string;
  model_provider: string;
  model_name: string;
  model_base_url: string;
  runtime_mode: string;
  eval_mode: string;
  user_facing_mode: string;
  cli_show_turn_summary: string;
  tts_enabled: string;
  tts_backend: string;
  tts_ref_audio: string;
  tts_model: string;
  dashscope_api_key_set: boolean;
}

export interface RuntimeProductizationPayload extends JsonRecord {
  schema?: string;
  readiness_status?: string;
  operator_snapshot?: JsonRecord;
  console_health?: JsonRecord;
  evidence_summary?: JsonRecord;
  route_inventory?: JsonRecord;
  next_action_hints?: JsonRecord[];
  lanes?: JsonRecord;
}

export interface OperatorConsoleRcPayload extends JsonRecord {
  schema?: string;
  overall_status?: string;
  readiness_status?: string;
  console_mode?: string;
  release_posture?: string;
  summary?: JsonRecord;
  readback_refs?: JsonRecord;
  operator_panels?: JsonRecord;
  route_inventory?: JsonRecord;
  authority_boundary?: JsonRecord;
  next_actions?: JsonValue[];
  failure_reasons?: JsonValue[];
}

export type MemorySnapshotPayload = JsonRecord;

export interface BackendEnvelopeMap {
  memory_snapshot: MemorySnapshotPayload;
  worldline_view: WorldlineViewPayload;
  bond_view: BondViewPayload;
  sources_view: SourcesViewPayload;
  persona_view: PersonaViewPayload;
  appraisal_view: AppraisalViewPayload;
  behavior_queue_view: BehaviorQueueViewPayload;
  checkpoint_history: CheckpointHistoryPayload;
  current_checkpoint: CurrentCheckpointPayload;
  thread_inventory: ThreadInventoryPayload;
  runtime_layout: RuntimeLayoutPayload;
  environment_summary: EnvironmentSummaryPayload;
  runtime_productization: RuntimeProductizationPayload;
  operator_console_rc: OperatorConsoleRcPayload;
  event_round: EventRoundPayload;
  assistant_turn: AssistantTurnPayload;
}

export type BackendEnvelopeFor<K extends BackendKind> = BackendEnvelope<K, BackendEnvelopeMap[K]>;

export type AnyBackendEnvelope = {
  [K in BackendKind]: BackendEnvelopeFor<K>;
}[BackendKind];
