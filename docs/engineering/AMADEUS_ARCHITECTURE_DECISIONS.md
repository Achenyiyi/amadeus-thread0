# Amadeus Architecture Decisions

This document records the current architecture decisions derived from the `digital persona lifeform seed` direction and the recent `OpenClaw` comparison study.

It is not a generic agent roadmap.
It is the decision contract for what `Amadeus-K` should become and what it should explicitly avoid becoming.

## Decision Frame

- `OpenClaw` is useful as a systems reference, not as a product template.
- `Amadeus-K` remains a `digital persona system`, not a personal ops shell.
- We borrow `runtime structure`, `continuity`, and `presence` ideas.
- We do not borrow `task-first identity` or tool-heavy persona drift.
- The next target is not "more tools". It is `digital embodiment`: one fixed persona interacting with the digital world through one unified memory substrate and one bounded runtime body.

## Backend Status

Status as of `2026-03-27`: `freeze-gate-ready, companion-autonomy-ready, digital-embodiment-open`

For backend purposes, the structural decisions in this document are now split into:

- baseline gate: `python evals/run_backend_freeze_gate_audit.py`
- autonomy gate: `python evals/run_companion_autonomy_audit.py`
- current handoff posture:
  - frontend remains frozen
  - backend contract is stable enough to consume
  - autonomy contract is baseline-complete
  - digital embodiment buildout is now the active structural work

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
  - for browser/search-like surfaces, the current bounded carrier is `saved source_refs`, not a fake live browser session:
    - previously retrieved pages/search results may be reattached from stored `url/title/query/snippet`
    - true live browser reopening remains deferred until a real browser/runtime surface exists

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
- This is the digital analogue of real-world constraints rather than a static tool-gating table.
- `resource_state` must now also track attached work surfaces as first-class runtime facts:
  - `artifact_continuity`
  - `active_artifact_kind`
  - `active_artifact_ref`
  - `active_artifact_label`
  - `artifact_age_s`
  - `artifact_reacquisition_mode`
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
7. `Digital Body / Unified Experience / Embodied Capability` - `current convergence target`
8. `Chinese lexical de-scaffolding with semantic replacements` - `future deferred track`
9. later frontend / multimodal integration - `intentionally deferred`
