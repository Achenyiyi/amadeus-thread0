# Amadeus Architecture Decisions

This document records the current architecture decisions derived from the `digital persona lifeform seed` direction and the recent `OpenClaw` comparison study.

It is not a generic agent roadmap.
It is the decision contract for what `Amadeus-K` should become and what it should explicitly avoid becoming.

## Decision Frame

- `OpenClaw` is useful as a systems reference, not as a product template.
- `Amadeus-K` remains a `digital persona system`, not a personal ops shell.
- We borrow `runtime structure`, `continuity`, and `presence` ideas.
- We do not borrow `task-first identity` or tool-heavy persona drift.

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

- Subagents may support retrieval, synthesis, or external work.
- Subagents must not own persona-core decisions.

### 13. Dynamic Skill Generation Is Deferred

- It may become useful later for external capability expansion.
- It is not a current bottleneck for persona realism.

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

## Current Implementation Order

1. `Session Fabric + Perception Event`
2. `Counterpart Model + Relationship Appraisal`
3. `Own Rhythm Engine`
4. `Capability Bus`
5. `Presence Layer`
6. later frontend / multimodal integration
