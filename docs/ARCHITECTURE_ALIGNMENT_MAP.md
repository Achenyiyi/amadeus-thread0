# Architecture Alignment Map

Updated: 2026-03-27

Status note, 2026-05-04: this document preserves earlier architecture framing. For readiness truth, prefer `program.md` and the latest audit reports; sandbox embodied execution phase 2 is now ready/preserved.

This document originally mapped the current codebase to an intended three-layer architecture:

- `Perception Layer`
- `Persona Core + Self-Evolution System`
- `Behavior Layer`

That framing is still conceptually useful, but the current runtime target is broader.
The codebase is now converging toward a `digital embodiment` architecture with five aligned layers:

- `Perception Layer`
- `Persona Core`
- `Unified Experience + Self-Evolution System`
- `Digital Body / Access Layer`
- `Behavior Layer`

It also records what is already implemented, what is only partially implemented, and what remains future work.

## 1. Perception Layer

### Definition
Perception is the structured intake of events from the outside world.
The correct abstraction is `event`, not only `user message`.

### Current status
Status: `implemented as a text-first, event-centric bridge that is starting to situate a digital body`

Currently implemented inputs:
- user text
- time/idle events
- scheduler-derived life events
- self-originated activity state events
- recent dialogue history
- retrieved worldline/context
- source evidence pack
- pending continuation fragment / user goal
- tool outputs and retrieval traces

Current evidence:
- `messages`
- `current_event`
- `recent_events`
- `worldline_focus`
- `evidence_pack`
- `pending_utterance_fragment`
- `pending_user_goal`
- `turn_appraisal`
- emerging autonomy packet aftermath in runtime/backend traces

### Missing
Not yet first-class:
- visual events
- audio/perceptual cues
- proactive world events
- bodily / ambient state simulation
- browser/session/access/resource observations as explicit body-state events

### Near-term action
Refactor runtime language so internal logic increasingly speaks in terms of `events` and `body/resource observations` rather than only `user_text`.

## 2. Persona Core

### Definition
Persona Core defines who she is.
It is fixed and should not be rewritten by normal interaction.

### Current status
Status: `implemented and now centralized through a repo-level authority`

Current evidence:
- canonical Amadeus-Kurisu role brief
- identity axioms
- counterpart anchor: `冈部伦太郎`
- canon shell used across draft and align stages
- repo-level authority file: `amadeus_thread0/persona_specs/amadeus_kurisu.json`
- runtime override policy: `authority_preserving` by default, explicit `shell_swap` only for transfer / external probes

### Missing
- stronger selfhood continuity evaluation at philosophical depth

### Near-term action
Keep the authority file as the only entry point for future role-shell swaps and persona-core edits, and refuse ordinary runtime payloads that try to rewrite immutable identity fields.

## 3. Unified Experience + Self-Evolution System

This is the mutable layer that lets the same person change.
It now has one explicit architectural constraint:
relationship change, world interaction, task attempts, access failures, and procedural learning should reconverge into one lived continuity model rather than split into separate persona and work brains.

### 3.1 Appraisal Layer
Status: `implemented as mixed path`

Current evidence:
- `LLM Appraisal + Rule Fallback`
- structured appraisal JSON used to update state

What it already does:
- resolves ambiguous emotional/relational turns better than plain keyword rules
- can now be triggered by non-user events such as `vision / ambient / gesture / idle-time` seeds
- can now appraise scheduler-derived life windows such as `deadline_window` and `shared_activity_window`
- can now preserve “she is busy with her own thing” as a valid runtime state instead of always pivoting toward the user
- now reads `semantic_self_narratives` as long-horizon bias, so appraisal no longer treats each turn as an isolated reset

What still needs work:
- broader event understanding beyond text-first turns
- better calibration against public affect datasets
- explicit body-state and access-state appraisal

### 3.2 Affect Engine
Status: `implemented`

Current evidence:
- `emotion_state`
- valence/arousal/linger/recovery-related fields

What it does:
- supports emotional inertia instead of one-turn resets

### 3.3 Bond Engine
Status: `implemented as v1`

Current evidence:
- `bond_state`
- trust / closeness / hurt / irritation / engagement / repair confidence

What it does:
- supports rise and decline of relationship quality
- supports partial repair rather than instant reset

### 3.4 Counterpart Assessment Engine
Status: `implemented as v1`

Current evidence:
- `counterpart_assessment`
- respect / reciprocity / boundary pressure / reliability read / stance

What it does:
- keeps “how she judges the counterpart right now” separate from raw emotion
- distinguishes disrespect from overload, apology, repair attempts, and boundary testing
- gives the behavior layer a bidirectional relationship read instead of only inward state
- now also survives passive scheduler/time turns instead of being silently washed back to `open`
- now absorbs long-term semantic narratives, so unresolved tension / repair residue / bond depth can keep affecting how she reads the same person over time

### 3.5 Allostasis Engine
Status: `implemented as v1`

Current evidence:
- `allostasis_state`
- safety / closeness / competence / autonomy / cognitive budget

What it does:
- turns the system from reactive shell into regulation-aware actor

### 3.6 Unified Experience Memory + Reconsolidation
Status: `implemented as strongest subsystem, with embodied expansion still open`

Current evidence:
- commitments
- unresolved tensions
- repair traces
- semantic self narratives
- revision traces
- autonomy/action traces entering final semantics

What it does:
- preserves long-term relationship and identity meaning, not just recall
- semantic narratives now feed back into appraisal and counterpart judgment, so reconsolidation is part of runtime causality rather than a passive archive
- current runtime narratives now cover not only `bond / commitment / repair / tension`, but also `boundary / selfhood / agency`, so “平权、自我、自己的节奏” 已经进入长期状态层而不是只停在提示词
- runtime now also records `semantic self evidence` from high-value turns, so long-term self narratives can keep consolidating even when the user is discussing selfhood/boundaries/autonomy rather than generating explicit relationship events

What still needs work:
- browser/filesystem/search/sandbox interaction results should write back through the same reconsolidation path
- access/resource traces should become first-class lived memory, not only transient runtime metadata

### 3.7 Behavior Policy Engine
Status: `implemented as explicit bridge`

Current evidence:
- `behavior_policy`
- `behavior_action`
- `behavior_plan`
- `behavior_agenda`
- `behavior_queue`
- now also conditioned by `counterpart_assessment`
- warmth / sharpness / initiative / disclosure / reply length / approach-withdraw / tease bias
- action target / deferred action family / timing window

What it does:
- translates latent state into conversational tendency without rigid templates
- starts exposing the selected outward interaction mode without collapsing into fixed response scripts
- preserves low-pressure deferred intentions across turns so behavior is not reduced to only the latest reply
- now supports `hold / reprioritize / mature / expire` semantics for pending low-pressure behavior under changing event context
- queue maturity can now also be influenced by `counterpart_assessment`, not only by elapsed time or event tags
- scheduled shared/work/life windows can now branch differently under `open / watchful / guarded` counterpart reads without introducing hard reply templates
- self-originated break windows can now also branch under `open / guarded` counterpart reads instead of always becoming reopening speech
- gesture / ambient / observed-scene events can now also branch under the current counterpart read instead of always forcing immediate speech

## 4. Digital Body / Access Layer

### Definition
Digital body is the bounded runtime body through which the persona senses, acts, verifies, asks for help, and gradually learns how to use its environment.
It should not be reduced to a fixed tool checklist.

### Current status
Status: `partially implemented through bounded autonomy substrate; not yet fully embodied`

Current evidence:
- `autonomy_intent`
- `action_packets`
- `pending_approval`
- `execution_trace`
- approval-gated risk tiers: `read / memory_write / external_mutation`
- `toolset_unlocks` and upgrade proposals outside persona-core judgment

What it does:
- models structured action proposals instead of only reply text
- keeps approval semantics explicit and inspectable
- separates persona-owned continuity (`behavior_queue`) from structured action execution (`action_packets`)
- already supports bounded low-risk reads, approval-gated writes, and live pending state

What still needs work:
- browser, filesystem, search, sandbox, account/session state should become first-class body surfaces
- resource/access state should be readable as world condition, not only as tool failure
- bounded helper/workflow formation should eventually happen inside approved or sandboxed environments, not by treating persona-core as a generic ops shell

### Near-term action
Formalize `affordance / resource / access` runtime state and make body interaction results write back into unified experience memory instead of a detached operational side log.

## 5. Behavior Layer

### Definition
Behavior is the outward action selected from identity + state + context.
Text is only one channel.

### Current status
Status: `text behavior plus initial structured autonomy behavior implemented`

Current behavior forms:
- final text response
- silence / brevity bias
- continuation behavior
- explicit interaction mode summary via `behavior_action`
- lightweight cross-turn behavior agenda / queue via `behavior_agenda / behavior_queue`
- structured `action_packets` with execution / approval / block semantics
- context-sensitive queue conflict handling so “到点了也不一定立刻冒头”
- idle-time low-pressure check-in / quiet non-expansion
- scheduled life nudges and shared-activity offers, now with counterpart-aware maturity/hold
- self-rhythm holding and self-originated small reopenings, now also allowed to stay silent when the counterpart read is still guarded
- perception-driven presence/support/object cues, now also allowed to stay silent when the current relationship read argues for distance
- abstract next-step skeleton via `action_target / deferred_action_family / timing_window_min`
- nonverbal/initiative skeleton via `attention_target / nonverbal_signal / initiative_shape`
- TTS rendering as secondary output channel

### Missing
- richer proactive initiation families beyond light check-ins and life nudges
- browser/file/world actions as ordinary behavior channels
- multimodal body/attention outputs

### Near-term action
Treat behavior as a richer action object whose language output, structured packets, and later embodied actions all share one final-turn semantics.
Examples:
- brief reply
- delayed reply
- proactive check-in
- low-engagement acknowledgement
- topic follow-up intention

## 6. Evaluation Mapping

### Regression Gate
Purpose:
- prevent obvious failure
- prevent system/meta leakage
- keep engineering stable

### Open Evolution Evaluation
Purpose:
- judge whether she remains herself while changing
- check daily realism, relationship residue, and open-ended continuity

### External Calibration
Purpose:
- verify transfer and non-Kurisu-specific engine behavior
- calibrate appraisal quality and support/empathy continuity against public benchmarks

### Human Validation
Purpose:
- measure whether the system feels like a real interacting being rather than a prompt shell

## 7. Immediate Priority

The current bottleneck is no longer only conversational behavior polish.
The bottleneck is convergence from an autonomy-closed backend to an embodied runtime:
- formal `digital body / access / resource` state
- unified writeback of world interaction results
- gradual procedural growth without identity drift

That means the next optimization phase should focus on:
- formalizing browser/filesystem/search/sandbox surfaces as body components
- treating missing access/cookies/accounts/permissions as world conditions rather than immediate terminal failure
- writing procedural/access/world traces into the same reconsolidation path as relationship and selfhood traces
- keeping language as one behavior channel inside a broader action system

## 8. Long-Term Direction

To match the constitution, the project should move toward:
- event-centric perception
- a real digital body / access model
- one unified experience memory
- selfhood-preserving evolution
- behavior outputs beyond dialogue
- fewer handcrafted response rules
- more fitting from realistic interaction data and pairwise preferences
- bounded capability formation inside approved or sandboxed environments rather than a dead fixed tool menu
