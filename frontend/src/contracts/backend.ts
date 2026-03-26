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
  timing_window_min?: number;
  behavior_weather: string;
  carryover_mode: string;
  carryover_strength: number;
  carryover_weather: string;
  recon_event_kind: string;
  recon_interaction_frame: string;
  behavior_consequence_kind: string;
  behavior_consequence_summary: string;
  semantic_anchor_bundle?: JsonRecord;
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
  agenda_lifecycle: AgendaLifecycleSummary;
  opening_window: OpeningWindowSummary | {};
  behavior_plan: BehaviorPlanSummary;
  behavior_queue_preview: BehaviorQueueItem[];
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
  interaction_carryover: JsonRecord;
  counterpart_assessment: JsonRecord;
  agenda_lifecycle_residue: JsonRecord;
  reconsolidation_snapshot: JsonRecord;
  turn_appraisal: JsonRecord;
  claim_links: ClaimLink[];
  sources: SourceRef[];
  pending_utterance_fragment: string;
}

export interface EventRoundPayload {
  final_text: string;
  emotion_label: string;
  session_context: JsonRecord;
  behavior_action: BehaviorActionPayload;
  behavior_plan: BehaviorPlanPayload;
  interaction_carryover: JsonRecord;
  counterpart_assessment: JsonRecord;
  agenda_lifecycle_residue: JsonRecord;
  reconsolidation_snapshot: JsonRecord;
  current_event: JsonRecord;
  turn_appraisal: JsonRecord;
  turn_summary: EvolutionSummary;
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
  interaction_carryover: JsonRecord;
  agenda_lifecycle_residue: JsonRecord;
  behavior_plan: BehaviorPlanPayload;
  behavior_queue: BehaviorQueueItem[];
  behavior_queue_summary: BehaviorQueueItem[];
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
  counterpart_assessment_history: JsonRecord[];
  counterpart_assessment_preview: CounterpartAssessmentPreviewItem[];
  proactive_continuity_history: JsonRecord[];
  proactive_continuity_preview: ProactiveContinuityPreviewItem[];
  semantic_self_narratives: JsonRecord[];
  revision_traces: JsonRecord[];
}

export interface BondViewPayload {
  relationship_state: JsonRecord;
  bond_state: JsonRecord;
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
  event_round: EventRoundPayload;
  assistant_turn: AssistantTurnPayload;
}

export type BackendEnvelopeFor<K extends BackendKind> = BackendEnvelope<K, BackendEnvelopeMap[K]>;

export type AnyBackendEnvelope = {
  [K in BackendKind]: BackendEnvelopeFor<K>;
}[BackendKind];
