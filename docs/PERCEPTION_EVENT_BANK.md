# Perception Event Bank

Updated: 2026-03-10

This document defines the first reusable event seeds for the new `Perception Layer`.

The goal is to stop treating the system as only:

- `user_text -> reply`

and start treating it as:

- `event -> persona / self-evolution -> behavior`

## Purpose

The event bank is not a script library.

It is a structured set of reusable external events that can be injected into runtime as `event_override` payloads.
Each seed represents a type of thing the system can notice:

- passage of time
- a visible scene
- a gesture
- an ambient change

Later, the same interface can host:

- camera observations
- voice prosody cues
- scheduled life events
- avatar/environment interactions

It also now supports a second stage:

- scheduler-derived maturity events that arise from prior behavior plans rather than direct user text

## Current Seed File

- [perception_event_seed_bank.json](/E:/桌面/amadeus-thread0/evals/perception_event_seed_bank.json)

## Seed Status Labels

- `native`
  - the runtime already has explicit behavior-selection logic for this kind of event
- `prompt-mediated`
  - the runtime can already ingest the event and behave coherently, but behavior selection is still mostly model-mediated rather than specialized in engine logic

## Current Seeds

1. `time_idle_work_checkin`
- kind: `time_idle`
- source: `time`
- current use: verify that a quiet period can lead to a light proactive check-in

2. `time_idle_respect_space`
- kind: `time_idle`
- source: `time`
- current use: verify that the system can choose low-pressure non-expansion instead of always speaking

3. `scheduled_checkin_due_light`
- kind: `scheduled_checkin_due`
- source: `scheduler`
- current use: verify that a prior deferred check-in can mature later and either softly reach out or stay quiet again depending on current relationship state
- companion note: this event should feel like a delayed intention ripening, not like a timer notification

4. `desk_cold_coffee`
- kind: `scene_observation`
- source: `vision`
- current use: verify that a concrete visual cue can enter dialogue naturally

5. `user_busy_window_tangle`
- kind: `scene_observation`
- source: `vision`
- current use: verify that visible overload can become low-pressure support instead of diagnostic narration

6. `fish_keychain_glimpse`
- kind: `scene_observation`
- source: `vision`
- current use: verify that a small concrete object can open a light micro-interaction rather than object-recognition narration

7. `user_wave_ping`
- kind: `gesture_signal`
- source: `vision`
- current use: verify that a light gesture can be perceived as presence, not only as text

8. `late_night_screen_glow`
- kind: `ambient_shift`
- source: `ambient`
- current use: verify that atmosphere can influence behavior without turning into system narration

## Design Rule

Events should stay small, concrete, and local.

Good event seeds:
- describe what changed
- do not prescribe exactly what she must say
- preserve room for Persona Core + Self-Evolution to decide behavior

Bad event seeds:
- already contain the answer
- encode a script
- force a specific line of dialogue

## Current Validation

The current runtime now has two layers of event-oriented validation:

1. `behavior_layer_probe`
- verifies `time_idle -> behavior_action -> speech_or_silence`

2. `proactive_checkin_probe`
- verifies `deferred_checkin -> scheduled_checkin_due -> speak_now or deferred_checkin`
- checks that silence routing is respected even after a due event matures

3. `perception_probe`
- verifies that non-user events are ingested as first-class `current_event`s
- verifies that visual/ambient cues can produce natural dialogue without system leakage

4. `perception_appraisal_probe`
- verifies that perceived events can also enter `turn_appraisal`
- checks `event -> appraisal -> state/behavior` rather than only `event -> wording`

5. `run_event_behavior_pairwise_eval.py`
- compares a true event-driven round against a textified substitute of the same cue
- checks whether the event really changed behavior choice, not just final wording
- current canonical green report:
  - `evals/reports/event-behavior-pairwise-20260310-040406-77e797eb.md`

## Next Step

The next meaningful extension is not “more keywords”.

It is:

- richer event classes
- event-to-appraisal calibration
- event-driven proactive behavior

That is the path from chatbot behavior toward a real interaction system.
