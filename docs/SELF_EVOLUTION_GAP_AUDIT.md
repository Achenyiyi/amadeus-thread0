# Self-Evolution Engine Gap Audit

## Verdict

Current Amadeus-K is no longer a prompt-only roleplay shell.

It already has an explicit self-evolution pipeline:

- `turn appraisal`
- `world model update`
- `emotion / bond / allostasis / counterpart assessment transition`
- `behavior policy + behavior action derivation`
- `worldline reconsolidation + semantic self narrative refresh`

So the main gap has changed.

The project is no longer blocked by missing state objects.
It is now blocked by calibration quality, runtime consumption quality, and whether these states actually produce believable long-horizon behavior.

## Current Mapping

### Persona Core

Status: `implemented, state-backed`

Current evidence:

- `amadeus_thread0/graph.py`
- `amadeus_thread0/evolution_engine/engine.py`

What exists:

- explicit canon shell for `Amadeus / 牧濑红莉栖`
- explicit counterpart anchoring, with `冈部伦太郎` as canonical counterpart baseline
- thread-level `persona_state`
- explicit `identity_axioms`, `value_floor`, `evolution_contract`
- authority trace and override path separation

What is still weak:

- persona quality still depends heavily on prompt rendering quality at generation time
- the remaining issue is not missing schema, but insufficient naturalness / role feel under open-ended dialogue

### Affect / Appraisal Engine

Status: `implemented`

Current evidence:

- `amadeus_thread0/graph.py`
- `amadeus_thread0/evolution_engine/appraisal.py`
- `amadeus_thread0/evolution_engine/state.py`

What exists:

- model-driven turn appraisal, not simple keyword matching
- emotion label + valence + arousal + linger
- explicit `recovery_rate`
- explicit `volatility`
- appraisal confidence weighting
- world-model-aware emotion carryover

What is still weak:

- appraisal calibration is still the bottleneck
- the hard part now is whether the upstream appraisal captures the right scene, not whether the downstream emotion state exists

### Bond Engine

Status: `implemented`

Current evidence:

- `amadeus_thread0/evolution_engine/state.py`
- `amadeus_thread0/memory_store.py`

What exists:

- `trust`
- `closeness`
- `hurt`
- `irritation`
- `engagement_drive`
- `repair_confidence`
- relationship memory coupling with repair / tension signals

What is still weak:

- bond dynamics exist structurally, but believable pacing across long natural conversations still needs calibration
- the remaining question is whether bond change feels human, not whether bond state is missing

### Allostasis Engine

Status: `implemented`

Current evidence:

- `amadeus_thread0/evolution_engine/state.py`

What exists:

- `safety_need`
- `closeness_need`
- `competence_need`
- `autonomy_need`
- `cognitive_budget`
- `relational_security`

What is still weak:

- allostasis is present, but its downstream effect still depends on behavior policy and response realization being strong enough to be felt by the user
- product feeling will come from calibration, not from adding more need axes right now

### Counterpart Assessment Engine

Status: `implemented`

Current evidence:

- `amadeus_thread0/evolution_engine/state.py`
- `amadeus_thread0/graph.py`

What exists:

- `respect_level`
- `reciprocity`
- `boundary_pressure`
- `reliability_read`
- `stance`
- `scene`
- summary compaction for generation context

Why this matters:

- this is the actual basis for the "she evaluates the user too" direction
- it already moves the system away from unconditional assistant behavior

What is still weak:

- assessment quality is only as good as turn appraisal and long-thread residue quality
- some subtle user-style judgments likely still underfire in casual dialogue

### Worldline + Reconsolidation Engine

Status: `implemented, stronger than the old audit claimed`

Current evidence:

- `amadeus_thread0/memory_store.py`
- `amadeus_thread0/graph.py`
- `amadeus_thread0/evolution_engine/reconsolidation.py`

What exists:

- `identity_facts`
- `shared_events`
- `relationship_timeline`
- `commitments`
- `conflict_repairs`
- `unresolved_tensions`
- `semantic_self_narratives`
- `revision_traces`
- reconsolidation snapshot exported into thread state and CLI views

Important nuance:

- `semantic_self_narratives` currently behave like a stable-per-category memory surface, not an append-forever log
- that is consistent with the current design in `_refresh_semantic_self_narratives(...)`
- this means "single evolving narrative per category plus trace evidence" appears intentional, not obviously a bug

What is still weak:

- reconsolidation quality depends on the quality of evidence promotion, not storage availability
- category-level narrative updating exists, but evidence aging / forgetting / contradiction resolution can still be improved

### Behavior Policy Engine

Status: `implemented and explicit`

Current evidence:

- `amadeus_thread0/evolution_engine/policy.py`
- `amadeus_thread0/graph.py`
- `amadeus_thread0/cli.py`

What exists:

- explicit `warmth / sharpness / initiative / disclosure`
- explicit `reply_length_bias / approach_vs_withdraw / humor_or_tease_bias`
- explicit `boundary_assertiveness / self_directedness / equality_guard`
- explicit `behavior_action`
- explicit `behavior_plan`
- explicit `behavior_agenda`
- due-promotion / hold / reschedule logic for own-rhythm and deferred interaction
- CLI surfacing for `/persona` and `/agenda`

What is still weak:

- agenda-backed self activity exists, but the perceived "she has her own life" effect still depends on long-horizon promotion quality and natural surface realization
- this is now a runtime realism problem, not an "implicit only" architecture problem

## Corrected Gap Statement

The old audit overstated several missing pieces.

These are already present today:

- unresolved tension tracking
- semantic self narrative storage
- revision trace storage
- explicit bond state
- explicit allostasis state
- explicit behavior policy
- agenda-backed own-rhythm handling

So the real remaining gaps are:

1. `appraisal calibration`
   - whether the scene classification and affect interpretation are consistently right

2. `runtime consumption realism`
   - whether bond / allostasis / policy / agenda actually change how she feels in live dialogue, instead of staying internal numbers

3. `reconsolidation quality`
   - whether semantic narratives update with the right evidence, at the right rate, with the right forgetting behavior

4. `long-horizon own-rhythm credibility`
   - whether behavior agenda promotion, self-activity carryover, and scheduled life events feel like a living rhythm rather than an engineering artifact

5. `evaluation realism`
   - whether the current subjective and probe suites actually stress natural interaction instead of only structural success conditions

## Engineering Priority

### Priority P0

- stop adding new top-level state buckets unless a real failure proves they are missing
- improve appraisal calibration and downstream state realism
- improve long-thread consumption of `behavior_agenda`, `self_activity_momentum`, and scheduled-life promotion
- keep pushing evaluation toward natural dialogue rather than template-safe prompts

### Priority P1

- strengthen reconsolidation policy:
  - evidence aging
  - contradiction handling
  - confidence-aware narrative refresh
- improve how self activity and ambient perception are surfaced in ordinary turns
- tighten subjective review packs around "is she alive" rather than "did the field update"

### Priority P2

- transfer evaluation on a second persona shell
- product-level multimodal input expansion after backend calibration is stable

## Short Summary

Current code already crosses the line into an explicit self-evolution architecture.

The next milestone is not "add more fields".

The next milestone is:

- make existing fields believable
- make existing state transitions visible in natural dialogue
- make her own rhythm, selfhood, and relationship judgments feel real over time
