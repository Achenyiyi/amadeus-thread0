# Amadeus Architecture Decisions

This document records the current architecture decisions derived from the `digital persona lifeform seed` direction and the recent `OpenClaw` comparison study.

It is not a generic agent roadmap.
It is the decision contract for what `Amadeus-K` should become and what it should explicitly avoid becoming.

## Decision Frame

- `OpenClaw` is useful as a systems reference, not as a product template.
- `Amadeus-K` remains a `digital persona system`, not a personal ops shell.
- We borrow `runtime structure`, `continuity`, and `presence` ideas.
- We do not borrow `task-first identity` or tool-heavy persona drift.
- The latest closed execution target is `Sandbox Embodied Execution Phase 1`: one fixed persona interacting with the digital world through one unified memory substrate and one bounded runtime body, now extended to truthful workspace-local execution.

## Backend Status

Status as of `2026-04-04`: `freeze-gate-ready, companion-autonomy-ready, digital-embodiment-phase1-ready, digital-embodiment-phase2-ready, sandbox-embodied-execution-phase1-ready`

For backend purposes, the structural decisions in this document are now split into:

- baseline gate: `python evals/run_backend_freeze_gate_audit.py`
- autonomy gate: `python evals/run_companion_autonomy_audit.py`
- digital embodiment gate: `python evals/run_digital_embodiment_audit.py`
- sandbox embodiment gate: `python evals/run_sandbox_embodied_execution_audit.py`
- current handoff posture:
  - frontend remains frozen
  - backend contract is stable enough to consume
  - autonomy contract is baseline-complete
  - digital embodiment phase 1 remains the preserved workspace/access/resource baseline
  - digital embodiment phase 2 is formally closed on the same body contract
  - sandbox embodied execution phase 1 is formally closed on the same body contract
  - current execution posture remains `host-local restricted execution`, not a provider-grade sandbox
  - no wider execution surface is opened in this run

Closure evidence by decision family:

- `Session Fabric + Perception Event`
  - runtime: `amadeus_thread0.runtime.runtime_bundle`, `amadeus_thread0.runtime.backend_session`, `amadeus_thread0.runtime.event_identity`
  - checks: `tests/test_perception_event_contract.py`, `tests/test_thread_runtime.py`, `tests/test_runtime_bundle.py`, `tests/test_turn_events.py`, `tests/test_session_context.py`
- `Persona Core Fixed + Self Model Evolves`
  - runtime: `amadeus_thread0/persona_specs/`, `amadeus_thread0.graph_parts.persona_runtime`, `amadeus_thread0.graph_parts.appraisal`, `amadeus_thread0.graph_parts.behavior_runtime`
  - checks: `tests/test_persona_runtime.py`, `tests/test_appraisal_calibration.py`, `tests/test_behavior_runtime_alignment.py`, `tests/test_dialogue_mode_counterpart.py`
- `Final Semantics Freeze Before Writeback`
  - runtime: `amadeus_thread0.graph_parts.prepare_turn_runtime`, `amadeus_thread0.graph_parts.memory_evolution`, `amadeus_thread0.runtime.final_state`
  - checks: `tests/test_memory_evolution_semantic_writeback.py`, `tests/test_prepare_turn_runtime.py`, `tests/test_response_finalize.py`, `tests/test_final_state.py`, `tests/test_backend_api.py`
- `Counterpart Model + Relationship Appraisal`
  - runtime: `amadeus_thread0.graph_parts.relational_runtime`, `amadeus_thread0.graph_parts.relational_carryover`, `amadeus_thread0.utils.counterpart_profile`
  - checks: `tests/test_dialogue_mode_counterpart.py`, `tests/test_world_model_residue.py`, `tests/test_counterpart_profile.py`
- `Own Rhythm Engine + Presence Layer`
  - runtime: `amadeus_thread0.graph_parts.behavior_agenda`, `amadeus_thread0.graph_parts.behavior_runtime`, `amadeus_thread0.runtime.backend_session`
  - checks: `tests/test_idle_event_context.py`, `tests/test_cli_threading.py`, `tests/test_backend_session.py`, `tests/test_subjective_review_pack.py`
- `Capability Bus Outside Persona Core`
  - runtime: tool routing and approval stay in runtime/tooling surfaces, not persona authority surfaces
  - checks: `tests/test_tooling_routing.py`, `tests/test_tool_approval_policy.py`
- `Relational Boundary Guard + Full Persona Traceability`
  - runtime: `counterpart_assessment`, `boundary_pressure`, `reconsolidation_snapshot`, `writeback_trace`
  - checks: `tests/test_behavior_runtime_alignment.py`, `tests/test_memory_guard.py`, `tests/test_backend_api.py`, `tests/test_cli_views.py`

This status does not change the intentional guardrails below:

- cross-surface continuity beyond the current backend contract still comes later
- subagents remain peripheral to persona-core judgment
- arbitrary host-side code generation remains deferred until sandbox and approval boundaries are explicit

Phase 2 preserved contract:

- keep one body contract:
  - `digital_body.access_state`
  - `digital_body.resource_state`
- do not open a second work-only container for session/account/search/sandbox state
- external material remains truthful through saved `source_ref` continuity until a real browser runtime exists
- `selected_access_proposal` remains the stable active path while partial/completed access truth evolves
- new world facts such as session/account/quota/permission/sandbox state must resurface through:
  - `digital_body_consequence`
  - `interaction_carryover.embodied_context`
  - retrieval resurfacing
  - later motive / behavior selection
- current local status for phase 2:
  - targeted phase 2 runtime/API/writeback/residue suites are green
  - `digital_embodiment_manual_smokes` is now a formal blocking check inside `run_digital_embodiment_audit.py`
  - fresh authoritative closeout reports are green:
    - `evals/reports/digital-embodiment-audit-20260404-192406-phase2-closeout-a.{json,md}`
    - `evals/reports/digital-embodiment-audit-20260404-194010-phase2-closeout-b.{json,md}`
    - `evals/reports/digital-embodiment-audit-20260404-195802-phase2-closeout-c.{json,md}`
  - phase 2 is formally closed and should now be treated as a preserved backend baseline

Sandbox Embodied Execution Phase 1 preserved contract:

- keep the same single body contract:
  - `digital_body.access_state`
  - `digital_body.resource_state`
- do not introduce a second execution-only state container
- the current execution surface is intentionally narrow:
  - `host-local restricted execution`
  - `workspace-local commands only`
  - no browser runtime, no network download, no package install, no arbitrary host-side codegen
- execution remains approval-gated and packet-owned:
  - intent: `sandbox:execute_workspace_command`
  - stable packet fields:
    - `execution_spec`
    - `execution_preview`
    - `execution_result`
  - approval must resume the same `proposal_id` and the same `execution_spec`
- embodied truth must stay singular across packet/state/writeback/retrieval:
  - `digital_body.access_state.sandbox_state`
  - `digital_body_consequence`
  - `interaction_carryover.embodied_context`
  - retrieved embodied traces
- run identity must remain available for follow-up turns:
  - `run_id`
  - `cwd`
  - `profile`
  - `exit_code`
  - filesystem artifact refs
- closeout evidence for this phase is:
  - `evals/run_sandbox_embodied_execution_smokes.py`
  - `evals/run_sandbox_embodied_execution_audit.py`
  - targeted sandbox/runtime/backend/residue tests in `tests/test_sandbox_*`, `tests/test_backend_*`, `tests/test_autonomy_writeback.py`, and `tests/test_world_model_residue.py`
  - fresh closeout reports now include:
    - `evals/reports/sandbox-embodied-execution-audit-20260404-225854-phase1-closeout-b.{json,md}`
    - `evals/reports/sandbox-embodied-execution-audit-20260404-232002-phase1-closeout-c.{json,md}`
    - `evals/reports/sandbox-embodied-execution-audit-20260404-233428-phase1-closeout-d.{json,md}`

## P0 Decisions

### 1. Session Fabric Is The Base Runtime

- Every interaction belongs to a long-lived `life thread`.
- The runtime should treat each turn as part of one continuous thread state, not as an isolated request/response call.
- Session continuity must survive CLI, TTS, future frontend surfaces, and future multimodal inputs.

### 2. Perception Event Is The Canonical Input Contract

- Raw user text is no longer the only conceptual input unit.
- All incoming signals should normalize into one `Perception Event` contract before appraisal:
  - source
  - channel
  - modality
  - trust tier
  - salience
  - interruptibility
  - delivery mode
  - session / turn identity
- Language is only one modality within the perception layer.

### 3. Persona Core Is Fixed; Self Model Evolves

- `persona_core` is stable and not rewritten by transient scenes.
- Evolution is allowed in:
  - emotion state
  - relationship state
  - counterpart assessment
  - self narrative
  - motive / goal state
  - own rhythm

### 4. Final Semantics Freeze Before Writeback

- Long-term updates must originate from the finalized turn semantics.
- Drafts, intermediate rewrites, and temporary tool reasoning must not directly write long-term identity or relationship state.

### 5. Counterpart Model Is A First-Class Runtime State

- `Amadeus` must maintain an explicit model of how she currently reads the counterpart.
- This is not a CRM profile. It is a relationship judgment surface.
- Minimum tracked axes:
  - trust
  - respect
  - safety
  - repairability
  - dependency risk
  - closeness
  - predictability

### 6. Own Rhythm Is A Core Engine, Not A Cosmetic Feature

- The system must support self-paced continuity:
  - wanting to continue
  - wanting to hold distance
  - wanting to revisit a thread
  - choosing silence
  - reopening from its own rhythm
- This is not cron-style productivity automation.
- It is the runtime expression of continued existence.

## P1 Decisions

### 7. Capability Bus Exists Outside The Persona Core

- Perception, knowledge, and action capabilities may expand over time.
- Capabilities can provide sensed facts, executable actions, and external feedback.
- Capabilities must not become the source of persona identity.

### 7a. Persona-First Autonomy

- Autonomy is built inside the companion loop, not as a separate generic task agent.
- `autonomy_intent` must arise from frozen appraisal / motive / relationship / own-rhythm state.
- Persona-core judgment remains upstream of tool execution and worker execution.

### 7b. Action Packet Contract

- Structured autonomy flows through one bounded packet contract.
- Required minimum fields:
  - `proposal_id`
  - `origin`
  - `intent`
  - `status`
  - `risk`
  - `requires_approval`
  - `capability_steps`
  - `expected_effect`
  - `result_summary`
  - `writeback_ready`

### 7c. Approval-Gated Mutation

- `read` packets may auto-execute.
- `memory_write` packets reuse the existing memory approval policy.
- `external_mutation` packets always require human approval.
- Rejected or blocked packets never masquerade as completed facts.
- The first concrete direct-execution slice is `artifact reacquisition`:
  - when a prior file/work-surface is detached or missing
  - and the packet is low-risk `read`
  - the graph may execute reacquisition before the next model turn instead of only describing the need semantically
  - this read-execution family may now also carry backend-owned runtime binding fields on the packet itself:
    - `tool_name=reacquire_artifact`
    - `tool_args={mode, artifact_kind, artifact_ref, artifact_label}`
  - those fields exist so execution can stay packet-owned even if live carryover has already moved on
  - for browser/search-like surfaces, the current bounded carrier is `saved source_refs`, not a fake live browser session:
    - previously retrieved pages/search results may be reattached from stored `url/title/query/snippet`
    - true live browser reopening remains deferred until a real browser/runtime surface exists
- The next bounded direct-execution slice is `access state refresh`:
  - when session/access conditions are present but the runtime can still do a truthful read-only recheck
  - the graph may execute a bounded `access:refresh_state` packet before the next model turn
  - this read-execution family may now also carry backend-owned runtime binding fields on the packet itself:
    - `tool_name=refresh_access_state`
    - `tool_args={access_hints}`
  - that binding is part of backend execution integrity, not a frontend autonomy contract surface
  - this slice only refreshes inspectable runtime truth such as:
    - API key presence
    - filesystem writability
    - session lifecycle recomputation from the current hints
    - requestable/missing access normalization
  - it does not pretend to complete external login/browser/cookie mutation that the runtime cannot actually perform
- The first truthful non-executing access-help slice is `access request help`:
  - when current-turn body hints show missing external conditions such as:
    - browser session entry
    - account login
    - cookies
    - API key / quota conditions that need operator intervention
  - the graph may emit a bounded `access:request_help` packet before the next model turn
  - this packet stays `awaiting_approval` with `external_mutation` risk:
    - it is a request/proposal surface
    - it is not a fake completed login, cookie restore, or account mutation
  - the packet must write through the same live/runtime/frozen surfaces as other action packets:
    - `pending_action_proposal`
    - `digital_body_state`
    - `reconsolidation_snapshot`
    - backend autonomy envelope
  - when multiple acquisition paths are available, the runtime must keep one stable current selection:
    - `selected_access_proposal` is the current active path
    - default selection should be deterministic and prefer the already-listed primary path rather than oscillating across turns
    - operator override may replace that selection, and the chosen path should persist through later approved/partial/resolved states until truthfully cleared
  - the current resolved semantics are intentionally split:
    - `awaiting_approval` = requesting operator help / approval for the missing access path
    - `approved` = operator accepted an acquisition path, but the real external access is still not fixed
    - `completed` = concrete access updates actually arrived in runtime state
    - for multi-grant acquisition plans, `approved` may also carry truthful partial progress:
      - some grants may already be satisfied
      - others may still be pending
      - this must not be flattened into fake `completed`
  - later-turn arrival must also close truthfully:
    - if a previously accepted `selected_access_proposal` is now actually satisfied by runtime-visible world state
    - the backend may synthesize one bounded `completed` resolution packet/writeback for that same proposal
    - then clear the stale planned state from live hints instead of letting `approved` hang forever
  - accepted-but-not-yet-fixed access paths must stay explicit through:
    - `action_packets[*].selected_access_proposal`
    - `digital_body.access_state.selected_access_proposal`
    - `autonomy_intent.mode=access_acquire_planned`
    - `digital_body_consequence` / carried `embodied_context` when that accepted path is the frozen state of the turn
    - when partial progress exists, those proposal surfaces may also expose:
      - `resolved_grants`
      - `pending_grants`
      - `completion_ratio`

### 7d. Bounded Capability Expansion

- Persona-core may request capability expansion through explicit upgrade proposals.
- Future worker execution, if added, stays outside persona-core judgment.

### 7e. Digital Body Core

- `Amadeus-K` should not converge toward a fixed tool menu.
- It should converge toward a `digital body` composed of bounded perception/action surfaces such as:
  - browser/runtime sessions
  - workspace filesystem
  - sandboxed execution
  - search/retrieval surfaces
  - access/session/cookie/account state
- These surfaces are not identity; they are the digital-world body through which identity acts.

### 7f. Affordance / Resource / Access Model

- The runtime should reason not only about "which tool exists" but also about:
  - what is reachable right now
  - what resources are missing
  - what accounts/cookies/permissions are absent
  - what conditions are only temporarily unavailable and should be retried later
  - whether a reusable session is still stable, already expiring, or broken and what recovery path would restore continuity
  - what can be requested, created, earned, or deferred
- Missing access is not always a terminal failure:
  - she may ask the operator for credentials or approval
  - she may create bounded new access such as a fresh account where appropriate
  - she may choose an alternate path when direct access is unavailable
- the current bounded implementation path is still proposal-first:
  - `access:request_help` may now surface both:
    - `path_kind=acquire_existing`
    - `path_kind=create_new`
  - `create_new` means a truthful candidate path such as:
    - register a fresh account
    - create a fresh writable workspace
    - create a new API key / service entry
  - it does not mean the runtime has already executed that creation
  - first bounded execution exception now exists for the local filesystem surface only:
    - if the approved selected proposal is `operator_create_workspace`
    - and the runtime can truthfully create that workspace inside its own `AMADEUS_DATA_DIR/workspaces/` boundary
    - it may execute `create_workspace_access`
    - the approved packet may now also carry backend-owned execution binding for that step:
      - `tool_name=create_workspace_access`
      - `tool_args={workspace_name, access_hints}`
    - execution should prefer that frozen packet binding over re-deriving arguments from live session state
    - then resolve the same access path from `approved` to `completed`
    - and clear stale `selected_access_proposal` residue once filesystem / workspace-write grants are actually satisfied
    - the frozen readback consequence should then be explicit at the embodied layer:
      - prefer `digital_body_consequence.kind=workspace_access_resolved`
      - rather than flattening the turn back into a generic `access_request_resolved`
  - next bounded local mutation surface may build on that same workspace boundary:
    - `write_workspace_file`
    - it may only write relative paths under the currently resolved runtime workspace
    - it must reject absolute paths and `..` escapes
    - it updates the active artifact from `workspace` to the concrete written `file`
    - frozen embodied readback should preserve this as a concrete file-surface update rather than collapsing it into generic growth:
      - prefer `digital_body_consequence.kind=workspace_file_updated`
      - carry `artifact_mutation_mode=write`
    - follow-on bounded mutation may continue inside the same contract:
      - `append_workspace_file`
      - it may only append to a relative path under the currently resolved runtime workspace
      - it keeps the same bounded host-write surface and concrete `file` artifact continuity
      - the same frozen readback kind should remain concrete:
        - `digital_body_consequence.kind=workspace_file_updated`
        - `artifact_mutation_mode=append`
      - `replace_workspace_text`
      - it may only edit an existing relative file path under the currently resolved runtime workspace
      - it performs explicit exact-text replacement rather than arbitrary host editing
      - `replace_workspace_lines`
      - it may only replace a bounded inclusive line span inside an existing relative file path under the currently resolved runtime workspace
      - it provides a stronger structured edit surface than raw text replacement while still staying inside the same workspace/file boundary
      - the same frozen readback family should remain concrete:
        - `digital_body_consequence.kind=workspace_file_updated`
        - `artifact_mutation_mode=replace`
      - approved executable mutation packets may carry backend-owned execution binding fields:
        - `tool_name`
        - `tool_args`
      - human approval for bounded workspace mutation should prefer a truthful preview-first contract:
        - approval preview may carry a bounded diff / patch preview against the current runtime file surface
        - approval still gates the external mutation itself, not the preview
        - apply must continue using the same packet-owned runtime binding after approval rather than regenerating a new edit plan
        - once generated, that preview should persist through the formal packet/backend envelope too:
          - `action_packets[*].mutation_preview`
          - `pending_action_proposal.mutation_preview`
          - backend autonomy envelope should expose the same preview rather than keeping it trapped inside approval-only tool-call payloads
      - these fields exist only so runtime can bind one approved packet to one truthful local tool invocation
      - they must not replace the packet's semantic `intent` / `origin`, and they are not the frontend-facing autonomy contract
      - when the active artifact is already a concrete file inside a workspace, workspace resolution must still recover the containing runtime workspace root rather than naively treating the file's parent directory as a new workspace boundary
  - the same workspace boundary now also exposes a bounded read-only perception surface:
    - `inspect_workspace_path`
    - it may inspect the root workspace, a subdirectory, or a concrete file under the current runtime workspace
    - it updates active artifact continuity truthfully without widening beyond that workspace boundary
    - when that inspection completes against an attached workspace/file surface, frozen writeback may carry:
      - `digital_body_consequence.kind=workspace_path_inspected`
      - `procedural_growth=false`
    - if the active artifact becomes a subdirectory path, later workspace-relative mutation must still resolve against the containing runtime workspace root rather than silently collapsing the write boundary to the subdirectory itself
  - the existing `saved source_refs` carrier should now also expose a bounded read-only inspection surface rather than relying on reacquisition semantics for every external-material turn:
    - `inspect_source_ref`
    - it may inspect one previously saved source by id / ref / label
    - it does not pretend to reopen a live browser; it only re-enters already stored external material
    - when an attached `source_ref` surface is still present but marked `stale`, autonomy may derive a read-only `inspect_source_ref` packet directly instead of flattening that state back into generic artifact reacquisition
    - when runtime continuity still carries two related saved source refs on the same material line, backend may also expose a bounded read-only comparison surface:
      - `compare_source_refs`
      - it compares two already saved materials; it does not open a live browser or fetch a third unseen source
      - when an attached `source_ref` surface is stale and continuity still holds two related saved refs, autonomy may derive `artifact:compare_source_refs` before falling back to plain re-inspection
      - when continuity carries a bounded ordered candidate set rather than only a pair, `compare_source_refs` may choose the comparison partner from that saved candidate set instead of blindly fixing the second id up front
    - when that inspection completes against an attached external-material surface, frozen writeback may carry:
      - `digital_body_consequence.kind=source_material_inspected`
      - `procedural_growth=false`
    - when that bounded comparison completes against an attached external-material surface, frozen writeback may carry:
      - `digital_body_consequence.kind=source_material_compared`
      - `procedural_growth=false`
    - bounded saved-material comparison is no longer allowed to stop at “a comparison happened”:
      - compare completion should re-anchor the live artifact surface to the preferred saved material when one side is clearly the better continuity anchor
      - that preferred anchor must remain bounded to real saved `source_ref` ids rather than free text or invented URLs
      - preferred-anchor semantics should stay explicit across runtime layers:
        - preserve `preferred_source_ref_id`
        - preserve `preferred_anchor_reason`
      - `artifact_source_ref_ids` may now carry a bounded ordered continuity set rather than only one compared pair, but the ordering must stay meaningful:
        - preferred anchor first
        - directly compared partner next
        - remaining saved candidates only as bounded follow-up continuity
      - when a stale `source_ref` line already carries a stable preferred anchor from a prior compare, autonomy should inspect that preferred saved material directly instead of redundantly comparing the same pair again
      - later turns may retrieve `source_material_compared` traces and reapply them as runtime continuity bias so the re-anchored material line can affect later `task_pull / memory_gravity / behavior` selection instead of dying inside the frozen snapshot
      - retrieved compare continuity may also refresh the saved-material lineup already held in `session_context.digital_body_hints`, but only when a visible `source_ref` context is already present in runtime state:
        - allowed visible carriers: current session hints, event `digital_body_hints`, or perception `digital_body_hints`
        - this refresh may widen `artifact_source_ref_ids`, preserve `preferred_source_ref_id`, preserve `preferred_anchor_reason`, and backfill missing saved-material metadata
        - it must not seed a brand-new `source_ref` line from retrieval alone when the live turn has no visible saved-material context
      - preferred-anchor semantics are not allowed to disappear at summary/export boundaries once present in runtime state:
        - `digital_body_state.resource_state`
        - `digital_body_consequence`
        - backend turn/event envelopes
        - CLI/evolution summary views that surface saved-material continuity
  - completed read-side reacquisition and access refresh should also survive as concrete digital-body facts instead of flattening back into generic state:
    - `tool_name=reacquire_artifact` -> `digital_body_consequence.kind=artifact_reacquired`
    - `tool_name=refresh_access_state` -> `digital_body_consequence.kind=access_state_refreshed`
    - both are verification/reattachment facts, not procedural growth
  - `artifact_context` returned by a completed tool is not allowed to remain packet-only:
    - it must be able to refresh live `digital_body_hints`
    - otherwise runtime state, frozen consequence, backend envelope, and CLI summary drift apart on what artifact is actually in view
  - with `artifact reacquisition`, `access refresh`, `workspace creation`, and workspace file mutation now all aligned, the current direct-execution families share one contract:
    - packet owns the runtime binding
    - execution prefers packet binding
    - live-state synthesis is compatibility fallback only
- This is the digital analogue of real-world constraints rather than a static tool-gating table.
- `resource_state` must now also track attached work surfaces as first-class runtime facts:
  - `artifact_continuity`
  - `active_artifact_kind`
  - `active_artifact_ref`
  - `workspace_root` when the active surface is inside a runtime workspace
  - `active_artifact_label`
  - `artifact_age_s`
  - `artifact_reacquisition_mode`
- `workspace_root` is the explicit filesystem trust boundary:
  - it must survive live hints, derived `digital_body_state.resource_state`, and summarized backend/CLI views
  - it must not be inferred only from a narrower current artifact such as a subdirectory or file path
  - later workspace-relative writes and edits still resolve against that root even when the current attached artifact is deeper inside it
- Losing a page/file/work-surface attachment is not the same as a persona change; it is embodied world friction that must survive into writeback, summaries, and later reacquisition behavior.

### 7g. Unified Experience Memory

- Do not split the system into a "persona memory" and a separate "work memory" brain.
- Keep one memory substrate with multiple experience trace families, for example:
  - relationship traces
  - selfhood traces
  - world/task/artifact traces
  - procedural traces
  - access/resource traces
- Different retrieval views may exist, but they must write back into one lived continuity model.

### 7h. Unified Evolution Engine

- Do not create a separate top-level `capability evolution` system in parallel with personality evolution.
- The same evolution engine should absorb:
  - emotional change
  - relationship change
  - self-narrative change
  - work-style change
  - procedural competence change
  - digital-body usage strategy change
- The system should therefore grow as one person interacting with one world, not as a role shell plus an independent task optimizer.

### 7i. Capability Formation Through Embodied Interaction

- The long-term target is not a frozen toolbox.
- The long-term target is that she can:
  - explore how to use a granted environment
  - ask for missing context or access
  - learn usage patterns from trial, feedback, and explanation
  - eventually form bounded new workflows or helper capabilities inside approved/sandboxed environments
- Host-side arbitrary code generation remains unsafe and out of scope until explicit sandbox and approval contracts exist.

### 8. Presence Layer Becomes Formal Runtime Infrastructure

- Typing, silence, interruption recovery, delayed continuation, and proactive re-entry belong to a dedicated presence layer.
- Presence should be treated as behavior orchestration, not UI sugar.

### 9. Relational Boundary Guard Is Separate From Generic Safety

- We need relational safety, not just policy safety.
- The guard layer should reason about:
  - disrespect
  - coercion
  - attachment imbalance
  - repair sincerity
  - emotional vulnerability

### 10. Traceability Must Cover The Full Persona Loop

- Each turn should remain inspectable across:
  - perception
  - appraisal
  - internal state delta
  - motive / goal shift
  - behavior packet
  - reconsolidation
  - self narrative delta

## P2 Decisions

### 11. Cross-Surface Continuity Comes Later

- Future frontend, voice, and multimodal surfaces should share one life-thread runtime.
- This is not needed before the backend loop is structurally complete.

### 12. Subagents Stay Peripheral

- Subagents / workers may support retrieval, synthesis, or bounded packet execution.
- Subagents must not own persona-core decisions or identity judgment.

### 13. Dynamic Skill Generation Is Deferred

- Host-side arbitrary skill/tool generation remains deferred.
- In the near term, only explicit capability-upgrade proposals are allowed.
- Long-term digital-embodiment convergence may include bounded helper creation or workflow synthesis, but only inside sandboxed / approval-gated execution surfaces.

### 14. Chinese Lexical De-Scaffolding Is Deferred

- Replacing most Chinese lexical heuristics is a valid future architecture move, but it is not the active mainline slice.
- The current mainline remains `digital body / access / unified experience` convergence.
- Until that deferred replacement phase is explicitly opened, output naturalness / tone micro-polish is not a structural success metric by itself.
- Current quality bar is:
  - runtime is runnable
  - state contracts are correct
  - writeback provenance is correct
  - digital-body / autonomy / reconsolidation architecture keeps closing
- When this replacement phase is opened, the candidate mechanisms are:
  - structured state extractors
  - small semantic classifiers
  - CrossEncoder semantic scorers / rerankers
  - preference optimization / DPO-style tuning
  - PEFT / LoRA / QLoRA-style role tuning
- The exact choice remains intentionally undecided until the digital-body phase is stable enough to avoid solving the wrong layer first.
- Until then, only the most brittle Chinese-heavy zones should be audited and documented, not proactively rewritten without a replacement contract.

## Explicit Rejections

### 1. Reject Task-First Product Identity

- `Amadeus-K` is not being optimized into a generic productivity agent.

### 2. Reject Tool-Driven Persona Drift

- Skills, tools, or plugins must not redefine the persona core.

### 3. Reject Prompt-Heavy Behavioral Repair As The Main Strategy

- If behavior quality is wrong, inspect state evolution, appraisal, writeback, and presence routing first.

### 4. Reject Keyword Scripts For Persona Behavior

- Keyword rules are allowed only for safety, auditability, or narrow routing.
- They are not the main persona engine.

### 5. Reject “Memory = Retrieval Store” Reduction

- Long-term memory must also preserve:
  - selfhood
  - counterpart judgment
  - relationship change
  - unresolved tension
  - repair history
  - own rhythm traces

### 6. Reject “Fixed Tool Suite = Capability” Reduction

- A static menu of tools is not the same thing as a living digital body.
- Capability should be modeled as embodied access, experimentation, verification, and reconsolidated experience.

## Current Implementation Order

1. `Session Fabric + Perception Event` - `backend-closed`
2. `Counterpart Model + Relationship Appraisal` - `backend-closed`
3. `Own Rhythm Engine` - `backend-closed`
4. `Capability Bus` - `backend-closed as baseline`
5. `Presence Layer` - `backend-closed as baseline`
6. `Companion Autonomy Closure` - `baseline-closed`
7. `Digital Body / Unified Experience / Embodied Capability` - `baseline-closed through digital embodiment phase 2`
8. `Sandbox Embodied Execution Phase 1` - `baseline-closed`
9. `Chinese lexical de-scaffolding with semantic replacements` - `future deferred track`
10. later frontend / multimodal integration - `intentionally deferred`
