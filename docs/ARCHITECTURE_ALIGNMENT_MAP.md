# Architecture Alignment Map

Updated: 2026-03-11

This document maps the current codebase to the intended three-layer architecture:

- `Perception Layer`
- `Persona Core + Self-Evolution System`
- `Behavior Layer`

It also records what is already implemented, what is only partially implemented, and what remains future work.

## 1. Perception Layer

### Definition
Perception is the structured intake of events from the outside world.
The correct abstraction is `event`, not only `user message`.

### Current status
Status: `implemented as a text-first event bridge`

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

### Missing
Not yet first-class:
- visual events
- audio/perceptual cues
- proactive world events
- bodily / ambient state simulation

### Near-term action
Refactor runtime language so internal logic increasingly speaks in terms of `events` rather than only `user_text`.

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

## 3. Self-Evolution System

This is the mutable layer that lets the same person change.

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

### 3.6 Worldline + Reconsolidation
Status: `implemented as strongest subsystem`

Current evidence:
- commitments
- unresolved tensions
- repair traces
- semantic self narratives
- revision traces

What it does:
- preserves long-term relationship and identity meaning, not just recall
- semantic narratives now feed back into appraisal and counterpart judgment, so reconsolidation is part of runtime causality rather than a passive archive
- current runtime narratives now cover not only `bond / commitment / repair / tension`, but also `boundary / selfhood / agency`, so “平权、自我、自己的节奏” 已经进入长期状态层而不是只停在提示词
- runtime now also records `semantic self evidence` from high-value turns, so long-term self narratives can keep consolidating even when the user is discussing selfhood/boundaries/autonomy rather than generating explicit relationship events

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

## 4. Behavior Layer

### Definition
Behavior is the outward action selected from identity + state + context.
Text is only one channel.

### Current status
Status: `text behavior plus initial non-user event behavior implemented`

Current behavior forms:
- final text response
- silence / brevity bias
- continuation behavior
- explicit interaction mode summary via `behavior_action`
- lightweight cross-turn behavior agenda / queue via `behavior_agenda / behavior_queue`
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
- action planning outside reply text
- multimodal body/attention outputs

### Near-term action
Start treating behavior as a richer action object even before UI work resumes.
Examples:
- brief reply
- delayed reply
- proactive check-in
- low-engagement acknowledgement
- topic follow-up intention

## 5. Evaluation Mapping

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

## 6. Immediate Priority

The current bottleneck is no longer architecture.
The bottleneck is the last-mile `Behavior Layer`, especially:
- casual support
- quiet confirmation
- familiar low-effort companionship

That means the next optimization phase should focus on:
- user-style expression preference
- pairwise open evaluation
- reducing service-feel without reintroducing hard templates

## 7. Long-Term Direction

To match the constitution, the project should move toward:
- event-centric perception
- selfhood-preserving evolution
- behavior outputs beyond dialogue
- fewer handcrafted response rules
- more fitting from realistic interaction data and pairwise preferences
