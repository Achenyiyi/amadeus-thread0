# Post-Unlock Roadmap Design

## Purpose

Coordinate every `Complete Closeout Unlock` lane into bounded, auditable implementation phases.

This is a control-plane design, not a runtime feature. It defines how the project should move from `unlocked_planned` to lane-specific readiness without reopening preserved baselines or silently widening the digital body. A lane appearing here means implementation may start in an isolated branch or worktree; it does not mean the capability is already available at runtime.

## Current Baseline

The roadmap starts after these preserved baselines:

- `freeze_gate_ready`
- `companion_autonomy_ready`
- `digital_embodiment_phase1_ready`
- `digital_embodiment_phase2_ready`
- `sandbox_embodied_execution_phase1_ready`
- `skills_ecosystem_ready`
- `live_browser_runtime_phase1_ready`
- `sandbox_embodied_execution_phase2_ready`
- `post_baseline_closure_ready`
- `tts_presence_timing_ready`
- `procedural_growth_phase1_ready`
- `procedural_growth_phase2_ready`
- `procedural_growth_phase3_ready`
- `procedural_growth_phase4_ready`

All follow-on work must preserve:

- one fixed persona core
- one unified memory substrate
- one digital body truth
- packet-owned structured actions
- approval-gated external mutation
- completed or executed facts only writing back as facts
- frontend as a `backend.v1` consumer rather than a backend semantics owner

## Roadmap Lanes

### Multimodal Capture Phase 1

Add consent-bound, read-only multimodal source ingestion as perception and digital-body resource truth.

Phase 1 accepts source-backed references such as text attachments, image files, audio files, screen snapshot files, and captured browser-page references. It excludes live microphone recording, live camera capture, background screen recording, secret capture, emotion inference from voice alone, and identity claims from image/audio alone.

### Dynamic Skills Phase 1

Add proposal-only dynamic skill candidates without auto-installing, auto-enabling, or writing skill registry truth into autobiographical memory.

The first slice creates a candidate contract, hashing/verification surface, approval packet preview, and fail-closed audit. Installed/enabled skills remain controlled by the existing skills ecosystem lifecycle.

### External Executor Harness Phase 1

Add a fail-closed harness registry for future executor adapters such as Deep Agents, Codex, Claude, and OpenClaw while keeping the preserved Docker sandbox as the only enabled execution backend.

Harness definitions are inspectable capability candidates. They must not execute, mutate files, install packages, pass secrets, use networked tooling, or own writeback semantics in this phase.

### Frontend Runtime Shell Phase 1

Create or stabilize a frontend runtime shell that consumes the existing `backend.v1` contract.

The shell may render conversation, autonomy packets, digital-body state, approval previews, browser/sandbox status, skill state, and procedural readback. It must not invent a second backend schema, store long-horizon truth, or route actions outside existing backend approval semantics.

### Chinese Semantic De-Scaffolding Phase 1

Replace Chinese reply-surface scaffolding through diagnostics-first semantic work rather than ad hoc tone polishing.

The first slice expands offline residue coverage, classifies scaffold families, exposes shadow diagnostics, and only then applies narrow runtime replacements that preserve final-turn semantics and TTS/text parity.

### Capability Growth Phase 5

Extend procedural growth beyond Phase 4 into proposal-grade workflow candidate formation.

The first slice should derive bounded workflow candidates from completed or blocked embodied traces. Candidates can influence planning only as advisory state until they pass explicit review, audit, and approval gates.

### Natural Long-Horizon Calibration Phase 1

Add deterministic multi-turn calibration packs that evaluate lived continuity across everyday companionship, repair, self-rhythm, shared work, embodied artifact resume, and deferred return.

This lane is an evaluation and calibration surface. It should measure memory continuity, relationship stance, body readback, and final utterance coherence without turning naturalness into prompt-heavy micro-polish.

## Dependency Order

The release train should start with Multimodal Capture Phase 1 because later lanes need stable source identity and resource continuity.

Dynamic Skills Phase 1, External Executor Harness Phase 1, and Frontend Runtime Shell Phase 1 can proceed in parallel after the source identity contract is explicit. The first two stay proposal-only and fail-closed; the frontend consumes backend envelopes.

Chinese Semantic De-Scaffolding Phase 1 can proceed once its offline audit bank is ready. Runtime replacement must be narrow and verified against preserved baseline audits after each behavior-affecting change.

Capability Growth Phase 5 follows procedural growth phase 4 and should use dynamic-skill and executor-harness contracts only as proposal surfaces, not as enabled authority.

Natural Long-Horizon Calibration Phase 1 should run after new source/capability readbacks are stable enough to evaluate as lived continuity.

The Post-Unlock Integration Gate runs after each lane and again after any multi-lane release train.

## Shared Readiness Rule

A lane moves from `unlocked_planned` to runtime-ready only when all of the following are true:

1. The lane has a committed design spec in `docs/superpowers/specs/`.
2. The lane has a committed implementation plan in `docs/superpowers/plans/`.
3. The lane has targeted tests for its contract.
4. The lane has deterministic smoke or audit coverage.
5. The lane audit reports the lane-specific readiness label.
6. Preserved baseline audits still pass after merge.
7. `program.md` records files changed, validation evidence, result, and next step.

## Merge Discipline

Each lane should be implemented in its own branch or worktree. Merge order follows dependency order unless a parallel lane only touches frontend contract consumption or fail-closed documentation/runtime registry code.

No lane may merge by relying on another lane's unmerged files. If two lanes need a shared helper, merge that helper as a small preparatory branch with its own tests first.

## Success Criteria

This roadmap succeeds when an engineer can open the plan, start any lane in the recommended order, know exactly which files own the change, know which behavior is allowed or blocked, run the correct tests, and decide whether the lane is still `unlocked_planned` or has earned its readiness label.

The roadmap fails if it encourages one giant implementation batch, implies runtime authority before audit closure, creates a second memory/body/skill truth surface, or treats Chinese naturalness, multimodal input, frontend shell, external harnesses, or capability growth as prompt-only patches.
