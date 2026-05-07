# Project Structure

## Purpose

This document is the engineering map for the repository layout after the LangGraph-oriented restructuring.

The target is not arbitrary cleanliness. The target is:

- a deployable LangGraph app entry
- clear ownership boundaries
- compatibility during migration away from the original monolithic `graph.py`
- low-risk ongoing iteration

## Top-Level Layout

```text
amadeus-thread0/
├── amadeus_thread0/        # primary Python package
├── frontend/               # unlocked contract-consuming runtime shell workspace
├── skills/                 # authored local SKILL.md packages
├── docs/                   # architecture, evaluation, defense, maintenance docs
├── evals/                  # evaluation entrypoints and reports
├── tests/                  # regression suite
├── scripts/                # utility scripts
├── user_study/             # user-study runtime and raw materials
├── langgraph.json          # LangGraph / LangSmith deployment config
├── requirements.txt        # canonical dependency file
└── AGENTS.md               # repository-level agent operating brief
```

This matches the LangChain / LangGraph recommended pattern at the level that matters:

- root deployment config
- root dependency file
- single package containing project code
- graph entry exposed via `agent.py`

## Python Package Layout

```text
amadeus_thread0/
├── agent.py                # deployable graph entry
├── graph.py                # compatibility facade during migration
├── graph_parts/            # structured graph modules
├── runtime/                # runtime integrations and provider adapters
├── utils/                  # utility surfaces and compatibility exports
├── persona_specs/          # canonical persona / counterpart specifications
├── evolution_engine/       # self-evolution engine logic
├── cli.py                  # interactive CLI
├── memory_store.py         # memory persistence and retrieval
├── tools.py                # tool definitions / assembly
└── ...
```

## Graph Module Ownership

`amadeus_thread0/graph_parts/` is the main home for graph-related logic.

- `state.py`
  Thread state and payload types.
- `guards.py`
  OOC risk, persona gap, canon guard.
- `prompting.py`
  task-draft prompt construction and prompt-state rendering.
- `prompt_helpers.py`
  compact prompt fragments reused by prompt construction, especially worldline / carryover / agenda prompt snippets.
- `rewrite.py`
  rewrite-time persona/daily-dialog alignment logic.
- `postprocess.py`
  final utterance cleanup, surface diagnosis, and lightweight text normalization.
- `messages.py`
  message restoration, rolling window selection, and thread compaction helpers.
- `graph_builder.py`
  LangGraph assembly and runtime cache lifecycle.
- `tool_nodes.py`
  tool gate, tool execution, tool-limit handling, and post-model routing.
- `skill_runtime.py`
  session-level skill activation, backend skill envelope shaping, and active-skill prompt disclosure.
- `procedural_growth.py`
  bounded procedural trace extraction, final-state enrichment, and approval-preserving procedural hints derived from completed or blocked embodied action packets.
- `procedural_planning.py`
  advisory procedure-guided autonomy planning over resurfaced procedural traces; may bias existing action packet selection but never owns execution, registry mutation, or persona-core truth.
- `procedural_outcome.py`
  outcome-calibrated procedural learning helpers; derives final action-packet outcomes, adjusts procedural trace confidence, and keeps failed/blocked/manual/pending attempts from becoming capability facts.
- `procedural_recovery.py`
  recovery-oriented procedural adaptation helpers; converts failed, blocked, manual-takeover, stale, and unexecuted outcomes into bounded advisory recovery guidance without opening new execution or mutation authority.
- `capability_growth.py`
  phase-5 workflow-candidate helpers over completed procedural evidence; advisory planning metadata only, with no new tool grant, skill install, or persona-core authority.
- `chinese_semantic_surface.py`
  semantic diagnostic, replacement-guidance, and typed runtime replacement-policy helpers for Chinese surface de-scaffolding; classifies brittle surface families, returns candidate replacement semantics, provides conservative safe-surface floors, and exposes authority-bound policy envelopes before any broad runtime rewrite.
- `browser_runtime.py`
  live-browser state shaping, browser packet preview/result normalization, and body-surface continuity helpers.
- `autonomy_runtime.py`
  derives bounded companion autonomy from frozen runtime state into `autonomy_intent`.
- `action_packets.py`
  packet normalization, proposal ids, risk classification, and structured action contract helpers.
- `implicit_idle.py`
  idle-time event override construction and idle-seeded state-update entry.
- `prepare_turn_context.py`
  the front half of `prepare_turn`: retrieval, event normalization, appraisal input assembly, and carryover seeding.
- `perception.py`
  canonical perception-event normalization and session/perception metadata attachment for runtime input events.
- `session_context.py`
  graph-native session fabric normalization for conversation mode, channel, presence, and related runtime carryover fields.
- `prepare_turn_runtime.py`
  the back half of `prepare_turn`: persona/runtime state evolution, memory-triggered refresh, and behavior synthesis.
- `model_call_prepare.py`
  model-call preparation, generation-profile selection, and tool-call setup.
- `response_finalize.py`
  final text shaping after generation, including rewrite/postprocess handoff.
- `relational_carryover.py`
  interaction carryover and agenda residue propagation.
- `relational_runtime.py`
  relationship snapshots, counterpart summaries, and worldline focus aggregation.
- `relational.py`
  temporary compatibility re-export over the split relational modules; do not add new logic here.
- `retrieval.py`
  retrieval triggering, memory ranking helpers, and working-context assembly.
- `tooling.py`
  explicit tool-call parsing, memory-write inference, and graph-adjacent tool routing helpers.
- `nodes.py`
  graph-node implementations and light orchestration glue only.

## Compatibility Layer

`amadeus_thread0/graph.py` is still intentionally present.

It currently serves three purposes:

- backward-compatible import surface for tests and legacy callers
- home for remaining helpers that have not yet been migrated
- bridge for lazy cross-module references during the incremental split

Rule:

- new graph logic should not be added directly to `graph.py` unless it is strictly temporary compatibility glue

## Runtime Layer

`amadeus_thread0/runtime/` contains provider-facing and environment-facing modules:

- `settings.py`
- `backend_api.py`
- `backend_session.py`
- `event_identity.py`
- `memory_admin.py`
- `final_state.py`
- `runtime_bundle.py`
- `transport_adapter.py`
- `executor_adapter.py`
- `executor_harness_registry.py`
- `dynamic_skill_candidates.py`
- `multimodal_sources.py`
- `artifact_perception_semantics.py`
- `artifact_appraisal_bridge.py`
- `artifact_motive_bridge.py`
- `artifact_behavior_alignment.py`
- `embodied_interaction_runtime.py`
- `post_baseline_closure.py`
- `runtime_productization.py`
- `residual_living_loop.py`
- `living_loop_realism.py`
- `sandbox_runner.py`
- `browser_runner.py`
- `access_negotiation.py`
- `skill_registry.py`
- `thread_runtime.py`
- `tool_approval.py`
- `modeling.py`
- `session_orchestrator.py`
- `tts_io.py`

`backend_session.py` is the reusable backend-facing session surface:

- graph turn execution wrappers
- state snapshot / checkpoint history / behavior queue / persona / worldline / sources view assembly
- the thin boundary future frontends should depend on instead of CLI print logic
- access-negotiation auto-continue over the same `proposal_id` after resolved access or manual browser takeover

`final_state.py` holds final-state normalization for readback parity:

- canonical `behavior_action` / `behavior_plan` resolution for backend views and turn envelopes
- behavior queue fallback normalization
- autonomy envelope resolution (`intent`, `action_packets`, `pending_approval`, `execution_trace`, `block_reason`)
- the shared rule that persisted final plan wins, and plan derivation from action is fallback-only
- procedural-growth finalization from frozen or terminal action packets, including raw read-only packet evidence such as completed skill-use effects
- procedural-outcome finalization from the same terminal packet evidence, including confidence calibration and boundary/recovery readback

`backend_api.py` is the transport-neutral frontend schema surface:

- wraps backend session and memory-admin views in stable envelopes
- exposes thread inventory, runtime layout, environment summary, turn/event response payloads
- exposes the unified autonomy envelope for turn/event/view payloads
- exposes compact `procedural_growth` readback alongside `digital_body_consequence`
- exposes advisory `autonomy.procedural_planning` readback when resurfaced procedural traces influenced planning
- exposes compact `procedural_outcome` readback when a final procedural attempt calibrated trace confidence or reinforced a boundary
- exposes compact `procedural_recovery` readback when a final procedural outcome requires failure-artifact inspection, boundary avoidance, manual takeover preservation, context refresh, or hold-for-approval
- provides the interface future frontend shells should consume before any CLI formatting

`transport_adapter.py` is the Python-callable route adapter over `BackendAPI`:

- maps stable route-like method/path calls to existing backend envelopes
- returns `backend.v1` envelope dictionaries without introducing FastAPI/Flask/Uvicorn
- exists so a future HTTP/SSE/WebSocket server can wrap the same transport-neutral contract without rebuilding backend semantics

`http_transport.py` is the HTTP Transport Thin Wrapper Phase 1 WSGI boundary:

- exposes `build_wsgi_app(transport_adapter)`, `create_http_transport_app(backend_api)`, and test helper `call_wsgi_app(...)`
- parses HTTP JSON bodies and query strings, then delegates every route to `BackendTransportAdapter.handle(...)`
- serializes the same backend-owned `backend.v1` envelopes and structured adapter errors as JSON responses
- remains standard-library transport glue only; it does not own backend semantics, execution, browser, sandbox, memory-write, skill-registry, frontend, multimodal model-call, live-capture, SSE/WebSocket, external harness, or persona-core authority

`event_identity.py` holds shared readback identity normalization:

- canonical `current_event` perception id hydration for backend envelopes and inspector summaries
- thin `session_context` readback normalization so turn/event identity is resolved once and reused

`tool_approval.py` holds the reusable approval policy surface:

- memory auto-resume checks
- approval preview normalization and clipping
- second-confirmation detection for high-risk memory writes
- shared approval-batch rendering inputs such as persona-facing `assist_request`

`access_negotiation.py` holds the bounded access-negotiation persona surface:

- derives persona-facing `assist_request` from existing access/browser truth rather than storing a second truth model
- covers both `grant_access` and `manual_takeover`
- builds the auto-continue resume event and short resume acknowledgements after access or browser takeover is resolved
- keeps sensitive-login friction truthful: request help or manual takeover, never credential guessing / OTP simulation / cookie forgery

`executor_adapter.py` holds the fail-closed executor adapter boundary:

- exposes the existing sandbox runner as the only enabled executor adapter
- documents Deep Agents, Codex, Claude, and OpenClaw harnesses as disabled future candidates
- keeps executor results as result-only runtime facts; adapters do not own persona memory or writeback semantics

`executor_harness_registry.py` holds the post-unlock external harness registry:

- keeps Deep Agents, Codex, Claude, and OpenClaw harnesses disabled and result-only
- preserves `sandbox_runner` as the only enabled executor harness
- keeps external harness metadata outside persona memory/writeback ownership

`dynamic_skill_candidates.py` holds dynamic skill candidate helpers:

- derives draft `SKILL.md` candidates only from completed procedural evidence
- produces frozen `dynamic_skill_candidate.v1` payloads with stable candidate/version/permission/profile/hash fields
- builds approval-gated `install_skill` action packets for those frozen payloads
- verifies approval payloads before any registry mutation can happen
- does not install, enable, or mutate the managed skills registry automatically from a proposal

`multimodal_sources.py` holds phase-1 multimodal source artifact normalization and phase-2 inspection packet helpers:

- supports consent-bound text, image, audio-file, screen-snapshot-file, and browser-capture-ref observations
- blocks live microphone/camera/background screen/secret capture methods
- emits read-only source artifacts and perception events with digital-body hints
- builds approval-gated `artifact:inspect_multimodal` packets with stable `multimodal_inspection_spec`, `multimodal_inspection_preview`, and optional `multimodal_inspection_result`
- keeps pending inspection preview-only with `auto_execute=false`, `model_api_call_planned=false`, `model_api_call_allowed=false`, and `live_capture_allowed=false`
- accepts completed inspection semantics only from approved precomputed results; the helper itself does not call multimodal model APIs

`approved_artifact_multimodal_runtime.py` holds the Approved Artifact Multimodal Runtime Phase 1 ingestion gate:

- validates exact operator-approved precomputed results against a frozen `artifact:inspect_multimodal` packet
- rejects proposal id drift, source/spec/result drift, model-called results, live-capture-derived results, pending results, rejected results, and blocked results
- completes only the same frozen packet by preserving `proposal_id`, spec, preview, tool binding, and capability steps while setting `status=completed`, `requires_approval=false`, and `writeback_ready=true`
- can attach backend-owned `approved_artifact_multimodal_runtime.v1` readback to a payload without mutating the original payload
- remains an ingestion/readback gate; it does not call multimodal model APIs, open live capture, mutate memory, execute tools, install skills, change persona core, or own frontend semantics

`artifact_perception_semantics.py` holds approved artifact semantic observation normalization:

- converts already-approved artifact metadata such as summaries, captions, transcripts, OCR text, observed text, and tags into bounded `semantic_observations`
- converts completed approved multimodal inspection results into bounded `semantic_observations` with `source=approved_inspection_result`
- keeps every observation read-only with `source=approved_metadata`, `model_api_called=false`, and `writeback_ready=false`
- keeps every approved inspection observation read-only with `model_api_called=false` and `writeback_ready=false`
- reuses multimodal source blocking so live microphone/camera/background screen and secret capture methods cannot become semantic observations
- does not call model APIs, capture live media, mutate memory, execute tools, install skills, or own frontend semantics

`artifact_appraisal_bridge.py` holds approved artifact appraisal evidence normalization:

- converts Phase 2 `semantic_observations` into read-only appraisal-facing `evidence_items`
- keeps every evidence item sourced from approved metadata with `model_api_called=false`, `memory_write_allowed=false`, and `writeback_ready=false`
- derives bounded influence hints such as `task_relevance` and `access_friction` without making memory facts or widening authority
- does not call model APIs, capture live media, mutate memory, execute tools, install skills, change persona core, or own frontend semantics

`artifact_motive_bridge.py` holds approved artifact motive/goal advisory normalization:

- converts Phase 3 `artifact_appraisal.evidence_items` into read-only `motive_hints`
- derives advisory frames such as `restore_access_continuity` and `continue_artifact_review` without replacing actual behavior motives
- keeps every hint sourced from `artifact_appraisal_evidence` with `model_api_called=false`, `memory_write_allowed=false`, `behavior_mutation_allowed=false`, and `writeback_ready=false`
- does not call model APIs, capture live media, mutate memory, execute tools, install skills, change persona core, own frontend semantics, or widen execution/browser/sandbox authority

`artifact_behavior_alignment.py` holds approved artifact motive-to-behavior alignment readback:

- compares Phase 4 `artifact_motive.motive_hints` with actual `behavior_action` / `behavior_plan` motive semantics
- emits read-only alignment states such as `causally_aligned`, `advisory_not_reflected`, and `behavior_conflict_observed`
- keeps every alignment item sourced from `artifact_motive_hint` with `model_api_called=false`, `memory_write_allowed=false`, `behavior_mutation_allowed=false`, `behavior_mutation_applied=false`, and `writeback_ready=false`
- does not call model APIs, capture live media, mutate memory, execute tools, install skills, change persona core, own frontend semantics, or widen execution/browser/sandbox authority

`embodied_interaction_runtime.py` holds the Embodied Interaction Runtime Phase 1, Phase 2, Phase 3, Phase 4, and Phase 5 integration contract:

- attaches consent-bound multimodal source artifacts to current-turn backend surfaces
- mirrors completed approved multimodal inspection results from `artifact:inspect_multimodal` action packets into artifact semantics candidates without admitting pending/rejected/blocked results
- mirrors source refs through `current_event.perception_sources`, `digital_body.resource_state.multimodal_source_refs`, and `interaction_carryover.embodied_context.multimodal_sources`
- attaches approved artifact semantic observations through `embodied_interaction.artifact_semantics`, `current_event.perception.semantic_observations`, `turn_appraisal.perception_semantics`, and `interaction_carryover.embodied_context.artifact_semantic_observations`
- attaches approved artifact appraisal evidence through `embodied_interaction.artifact_appraisal`, `current_event.perception.appraisal_evidence`, `turn_appraisal.artifact_evidence`, `turn_appraisal.perception_semantics.appraisal_evidence`, and `interaction_carryover.embodied_context.artifact_appraisal_evidence`
- attaches approved artifact motive/goal advisory hints through `embodied_interaction.artifact_motive`, `current_event.perception.motive_hints`, `turn_appraisal.motive_evidence`, `turn_appraisal.perception_semantics.motive_hints`, `interaction_carryover.embodied_context.artifact_motive_hints`, and advisory `behavior_plan.artifact_motive_hints`
- attaches approved artifact motive-to-behavior alignment readback through `embodied_interaction.artifact_behavior_alignment`, `current_event.perception.behavior_alignment`, `turn_appraisal.behavior_alignment_evidence`, `turn_appraisal.perception_semantics.behavior_alignment`, `interaction_carryover.embodied_context.artifact_behavior_alignment`, and advisory `behavior_plan.artifact_behavior_alignment`
- preserves existing `behavior_action.primary_motive` and `behavior_plan.primary_motive`; Phase 4 hints are readback/advisory only
- applies deterministic Chinese semantic runtime floors to `final_text` and `reconsolidation_snapshot.final_text` together for known brittle scaffold families
- exposes `chinese_semantic_surface.runtime_policy` with typed family / semantic intent / deterministic safe-floor strategy / authority-boundary readback, and keeps `tts_text` aligned with the final runtime text
- exposes `embodied_interaction_runtime_phase1_ready` through a deterministic audit/readback gate
- exposes `embodied_interaction_runtime_phase2_ready` when approved artifact metadata reaches perception/appraisal/carryover semantic surfaces without widening authority
- exposes `embodied_interaction_runtime_phase3_ready` when approved artifact semantic observations become read-only appraisal-facing evidence without becoming memory facts
- exposes `embodied_interaction_runtime_phase4_ready` when approved artifact appraisal evidence becomes read-only motive/goal advisory hints without mutating behavior or memory
- exposes `embodied_interaction_runtime_phase5_ready` when approved artifact motive hints are compared against actual behavior action / behavior plan motives through read-only alignment readback without mutating behavior or memory
- remains bounded runtime normalization; it does not call multimodal model APIs, open live capture, execute tools, mutate memory, change persona core, write the skill registry, or own frontend semantics

`sandbox_runner.py` holds the bounded execution surface for the preserved sandbox baselines:

- `LocalRestrictedSandboxRunner`
- structured `argv` validation and executor allowlist enforcement
- `allowed_roots` / `cwd` boundary checks
- scrubbed environment assembly
- per-run trace artifact emission (`run.json`, `stdout.txt`, `stderr.txt`)
- phase-2 Docker-isolated execution through `docker_isolated_runner` / `docker_local_isolated`
- default `network_policy=none`
- bounded command families only: `python`, `pytest`, `rg`, read-only `git`
- blocked surfaces remain package install, shell wrappers, git mutation, Docker socket mounting, privileged containers, and host secret passthrough
- runtime-owned workspace is the default; `operator_attach_repo_root` requires explicit approval

`browser_runner.py` holds the live browser surface for `Live Browser Runtime Closure Phase 1`:

- Playwright persistent-context runtime assembly
- isolated profile-root management under runtime data dirs
- run-ledger emission for browser actions
- packet-owned browser action replay safety via `proposal_id`
- controlled download/upload boundary enforcement

`skill_registry.py` holds the managed skills ecosystem surface:

- local authored skill discovery from `skills/`
- remote catalog / install cache / registry truth
- approved dynamic candidate install into the existing installed-skill layout after exact frozen-payload verification
- session activation state from auto-match plus manual override
- `SKILL.md` metadata parsing plus on-demand disclosure for active skills
- install/update/enable/disable/pin/unpin lifecycle helpers

`post_baseline_closure.py` holds the post-baseline closure status policy:

- marks callable transport, TTS presence timing, and executor adapter readiness
- marks post-unlock roadmap lanes as `unlocked_planned` until their phase audits are ready
- upgrades lane status from the post-unlock roadmap audit while keeping blocked surfaces explicit
- keeps "ready" lane status separate from blanket runtime authority when a lane remains proposal-only, diagnostic-only, advisory-only, or fail-closed

`runtime_productization.py` holds the Runtime Productization operator readback contract:

- composes post-baseline closure, post-unlock roadmap, preserved-baseline, and current-turn readback into one `operator_readback` surface
- emits `operator_readback.v2` with console health, evidence summary, read-only route inventory, and next-action hints for operator-console consumption
- exposes authority-boundary booleans that keep external mutation approval, persona-core immutability, frontend consumer-only semantics, dynamic skill registry approval, and fail-closed harness behavior explicit
- formats compact operator readback lines for CLI summaries
- may optionally include residual living-loop readback when supplied, but absence of that optional block must not change the runtime productization gate
- must remain readback-only; it does not execute tools, mutate memory, change persona state, install skills, run browser actions, or enable external executor harnesses

`runtime_status_dashboard.py` holds the Runtime Productization Phase 3 status dashboard:

- composes preserved-baseline, post-unlock-roadmap, and runtime-productization report status into `runtime_status_dashboard.v1`
- distinguishes ready gates, missing gitignored source reports, blocked-by-contract lanes, and fresh next-spec lanes
- marks HTTP transport as `phase1_ready` / `thin_wrapper` and multimodal artifact inspection as `phase1_ready` / `approved_result_ingestion_only` while keeping Chinese semantic naturalness and dynamic skill candidate generation visible as future bounded specs
- remains pure readback logic with no HTTP server, execution, browser, sandbox, memory-write, skill-registry, frontend, model-call, or persona-core authority

`residual_living_loop.py` holds the Residual Living Loop Closure readback contract:

- evaluates whether one final-turn packet exposes the north-star stages from perception through self-narrative update
- summarizes residual post-unlock lanes such as Chinese semantic de-scaffolding, multimodal perception bridge, dynamic capability boundaries, and offline long-horizon calibration
- keeps live capture, auto skill registry writes, external harness enablement, frontend-owned semantics, and persona-core mutation explicitly blocked
- remains pure readback/audit logic with no execution, memory-write, browser, sandbox, skill-install, or frontend authority

`living_loop_realism.py` holds the Living Loop Runtime Realism readback contract:

- evaluates whether visible north-star stages causally constrain each other instead of merely appearing in one packet
- checks appraisal-to-motive, state-to-behavior, action/plan, consequence/reconsolidation, and final-semantics alignment
- exposes `living_loop_runtime_realism_phase1_ready` as a deterministic audit/readback gate
- exposes `living_loop_runtime_realism_phase2_ready` when real `assistant_turn` / `event_round` backend payloads carry the same causal readback through `living_loop_realism`
- exposes `living_loop_runtime_realism_phase3_ready` when those backend payloads also carry Phase 5 `embodied_interaction.artifact_behavior_alignment` readback
- preserves `advisory_not_reflected` as truthful visible evidence while failing closed on unsafe or mutating artifact-alignment claims
- normalizes backend payload fields such as `turn_summary`, `writeback_trace`, final behavior payloads, internal state, and reconsolidation snapshots into one current-turn realism view
- consumes existing artifact-alignment readback only; it does not recalculate alignment from raw artifacts
- remains pure readback/audit logic with no execution, memory-write, browser, sandbox, skill-install, frontend, prompt-sprawl, or persona-core authority

`memory_admin.py` holds direct memory-management and reflection-admin surfaces:

- profile correction / undo workflows
- memory listing and deletion helpers
- reflection proposal generation and durable write-back

`runtime_bundle.py` holds active backend lifecycle assembly:

- graph + memory store + backend session + memory admin bundling
- backend API factory for frontend-facing access
- thread switch rebuild path
- a stable runtime object future shells can reuse

`thread_runtime.py` holds worldline/runtime management surfaces:

- thread id generation and startup resolution
- per-worldline runtime path activation
- checkpoint/worldline directory enumeration
- shared-runtime warning policy

Top-level wrappers like `amadeus_thread0/settings.py` exist only to preserve old imports.
They are thin facades implemented through `amadeus_thread0/_compat.py`.

## Utility Layer

`amadeus_thread0/utils/` contains lower-level supporting modules and re-export surfaces:

- `tool_registry.py`
- `runtime_audit.py`
- `embodied_preview.py`
- `relational_history_export.py`
- `turn_summary_export.py`
- `revision_trace_export.py`
- `cli_views.py`
- `counterpart_profile.py`
- `perception_events.py`
- `state.py`
- `nodes.py`
- `tools.py`

Rule:

- if a module is generic support or compatibility-facing, it belongs here
- if a module directly shapes graph execution semantics, it belongs in `graph_parts/`

`embodied_preview.py` is the shared compact read-model surface for embodied continuity exports:

- provides one public home for compact `preview_line` formatting over source-bearing `embodied_context`
- keeps backend/session/export read models off direct imports of CLI-private helpers
- CLI preview renderers should also consume this module rather than owning a separate embodied compact-format implementation
- must stay additive and contract-oriented; it formats already-normalized embodied facts, it does not reinterpret persona state

`relational_history_export.py` is the shared typed export-normalization surface for persisted relationship-history rows:

- owns type-specific export/readback normalization for `counterpart_assessment_history` and `proactive_continuity_history`
- keeps runtime/admin/tool/backend consumers off ad hoc local flattening of `content` when these rows carry typed scalar fields or nested `assessment_profile`
- normalizes nested compatibility `content` back toward the same typed top-level contract instead of leaving summary consumers to repair types later
- may add compact `preview_line` companions, but must not reinterpret embodied continuity into new persona judgments

`turn_summary_export.py` is the shared typed summary-normalization surface for current-turn residue summaries:

- owns normalized read-model construction for `event_residue`, `agenda_lifecycle`, `interaction_carryover`, `behavior_consequence`, `opening_window`, and `digital_body` current-turn summary surfaces
- keeps these turn-summary surfaces out of CLI-local field flattening so backend summary consumers can share one contract
- also provides the shared compact `embodied_context` / `digital_body_consequence` summary used by turn-residue summaries
- should stay presentation-adjacent but contract-stable: normalize typed summary fields without reinterpreting persona logic

`revision_trace_export.py` is the shared export-normalization surface for persisted revision traces:

- promotes provenance-bound `embodied_context` from nested final semantics (`behavior_action`, `behavior_plan`, `behavior_consequence`, `interaction_carryover`)
- adds compact `preview_line` companions for embodied revision traces through the shared embodied preview surface
- keeps read-only export surfaces aligned across backend API envelopes and tool-facing memory inspectors
- must not reinterpret body/access continuity into relationship stance or other persona judgments

## Evaluation And Audit Layer

`evals/` holds the repository's closeout and regression entrypoints, not only ad hoc experiments.

- gate audits:
  - `run_backend_freeze_gate_audit.py`
  - `run_companion_autonomy_audit.py`
  - `run_digital_embodiment_audit.py`
  - `run_sandbox_embodied_execution_audit.py`
  - `run_sandbox_phase2_audit.py`
  - `run_skills_ecosystem_audit.py`
  - `run_post_baseline_closure_audit.py`
  - `run_preserved_baselines_audit.py`
  - `run_post_unlock_roadmap_audit.py`
  - `run_runtime_productization_audit.py`
  - `run_runtime_productization_phase3_audit.py`
  - `run_residual_living_loop_audit.py`
  - `run_living_loop_realism_audit.py`
  - `run_embodied_interaction_runtime_audit.py`
  - `run_embodied_interaction_runtime_phase2_audit.py`
  - `run_embodied_interaction_runtime_phase3_audit.py`
  - `run_embodied_interaction_runtime_phase4_audit.py`
  - `run_embodied_interaction_runtime_phase5_audit.py`
  - `run_approved_artifact_multimodal_runtime_phase1_audit.py`
  - `run_multimodal_perception_phase2_audit.py`
  - `run_multimodal_capture_audit.py`
  - `run_dynamic_skills_audit.py`
  - `run_dynamic_skills_phase2_audit.py`
  - `run_external_executor_harness_audit.py`
  - `run_frontend_runtime_shell_audit.py`
  - `run_frontend_runtime_shell_phase2_audit.py`
  - `run_capability_growth_phase5_audit.py`
  - `run_natural_long_horizon_calibration_audit.py`
- manual smoke packs:
  - `run_freeze_gate_smokes.py`
  - `run_companion_autonomy_smokes.py`
  - `run_digital_embodiment_smokes.py`
  - `run_sandbox_embodied_execution_smokes.py`
  - `run_sandbox_phase2_smokes.py`
  - `run_skills_ecosystem_smokes.py`
  - `run_multimodal_capture_smokes.py`
  - `run_dynamic_skills_smokes.py`
  - `run_capability_growth_phase5_smokes.py`
  - `run_natural_long_horizon_calibration_smokes.py`
  - `run_runtime_productization_phase3_smokes.py`
- baseline helpers:
  - `print_latest_sandbox_baseline.py`
- artifacts:
  - `evals/reports/` stores authoritative json/md reports
  - `evals/_tmp/` stores temporary runtime fixtures for bounded smoke scenarios such as sandbox execution and skills lifecycle continuity

`tests/` mirrors those gates with owning-layer coverage.
Current sandbox closure coverage lives in:

- `tests/test_sandbox_runner.py`
- `tests/test_sandbox_execution_runtime.py`
- `tests/test_sandbox_backend_contract.py`
- `tests/test_sandbox_embodied_execution_smokes.py`
- `tests/test_sandbox_embodied_execution_audit.py`
- `tests/test_sandbox_phase2_backend_contract.py`
- `tests/test_sandbox_phase2_smokes.py`

Current skills closure coverage lives in:

- `tests/test_skill_registry.py`
- `tests/test_skill_runtime.py`
- `tests/test_dynamic_skills_phase2.py`
- `tests/test_dynamic_skills_phase2_audit.py`
- `tests/test_skills_ecosystem_smokes.py`
- `tests/test_skills_ecosystem_audit.py`

## Frontend Workspace

`frontend/` is a separate React/Vite workspace for backend-contract consumption.

- It should render frozen `backend.v1` envelopes rather than inventing an alternative state schema.
- Contract copies and mock fixtures should stay close to the frontend shell so UI work can proceed without touching backend internals.
- The Phase 2 route client in `frontend/src/runtime/backendClient.ts` validates common envelope shape, consumes route-like backend responses, and groups them into the UI session without deriving backend semantics.
- The shell can render backend-owned `operator_readback`, `living_loop_realism`, `embodied_interaction`, and `runtime_productization` payloads as read-only records.
- Any future transport adapter should remain thin and delegate semantics to `amadeus_thread0/runtime/backend_api.py` and `backend_session.py`.
- It is now unlocked as a runtime shell lane, but only as a consumer of the existing backend contract; it must not own memory, body, autonomy, persona, graph, browser, sandbox, skill-registry, or external-mutation semantics.

## Entry Points

- deployment graph:
  `amadeus_thread0/agent.py`
- CLI:
  `python -m amadeus_thread0.cli`
- sandbox phase audit:
  `python evals/run_sandbox_embodied_execution_audit.py`
- sandbox manual smokes:
  `python evals/run_sandbox_embodied_execution_smokes.py`
- sandbox phase-2 audit:
  `python evals/run_sandbox_phase2_audit.py`
- sandbox phase-2 manual smokes:
  `python evals/run_sandbox_phase2_smokes.py`
- skills ecosystem audit:
  `python evals/run_skills_ecosystem_audit.py`
- skills ecosystem manual smokes:
  `python evals/run_skills_ecosystem_smokes.py`
- post-baseline closure audit:
  `python evals/run_post_baseline_closure_audit.py`
- preserved-baselines meta-audit:
  `python evals/run_preserved_baselines_audit.py`
- Chinese semantic de-scaffolding phase-2 audit:
  `python evals/run_chinese_semantic_descaffolding_phase2_audit.py`
- multimodal perception phase-2 audit:
  `python evals/run_multimodal_perception_phase2_audit.py`
- approved artifact multimodal runtime phase-1 audit:
  `python evals/run_approved_artifact_multimodal_runtime_phase1_audit.py`
- living-loop realism phase-3 audit:
  `python evals/run_living_loop_realism_phase3_audit.py`
- frontend runtime shell phase-2 audit:
  `python evals/run_frontend_runtime_shell_phase2_audit.py`
- frontend dev shell:
  `cd frontend && npm run dev`
- deployment config:
  `langgraph.json`

## Migration Status

Already migrated out of the monolithic `graph.py`:

- state types
- graph assembly
- tool nodes
- idle override entry helpers
- `prepare_turn` front-half context assembly
- `prepare_turn` back-half runtime synthesis
- `call_model` preparation and finalization
- prompt construction
- prompt helper fragments
- message restoration and context window helpers
- relationship/worldline helper cluster
  this is now split into `relational_carryover.py` and `relational_runtime.py`
  `relational.py` remains only as a transition shim
- retrieval and ranking helpers
- tool routing and memory-write inference helpers
- rewrite logic
- postprocess / surface cleanup
  this now includes the main text-surface normalization cluster: structured-answer gating, reply compression, surface trim passes, malformed-fragment cleanup, and dialogue-surface diagnostics
- guards

Still reasonable future extraction targets:

- idle/event entry helpers adjacent to graph orchestration
- remaining lexical-intent helper clusters that are still imported through `graph.py`
- non-graph domain logic that can move closer to `runtime/` or dedicated domain packages

## Rules For Future Refactors

- prefer additive migration with compatibility exports
- do not break `from amadeus_thread0.graph import ...` until downstream callers are cleaned up intentionally
- when moving code, migrate tests and docs in the same change
- if a new subpackage is introduced, document ownership here immediately

## Validation Expectations

After structural edits, always verify:

```powershell
python -m py_compile amadeus_thread0/agent.py amadeus_thread0/graph.py
python - <<'PY'
from amadeus_thread0.agent import agent
print(type(agent).__name__)
PY
```

Then run the regression subset appropriate to the touched area.
