# Thesis Backend Execution Plan

Updated: 2026-03-07

This plan locks the project into a thesis-first backend trajectory. Frontend, Live2D, camera interaction, and product-shell work are intentionally deferred until the backend and evaluation loops meet the graduation criteria below.

## Scope Freeze

Deferred until backend closure:

- New frontend UI
- Live2D integration
- Camera-driven interaction
- Steam packaging / distribution polish
- Large feature expansion outside persona, worldline, multimodal reliability, and evaluation

Active scope:

- Persona consistency and conversational realism
- Worldline continuity and relationship evolution
- Citation-backed retrieval reliability
- Memory safety and rollback
- TTS / interruption backend reliability
- Formal evaluation, ablation, and user-study assets

## Backend Graduation Gates

The backend is considered thesis-grade only when all of the following are true.

### Gate 1. Engineering Stability

- CLI can start and exit cleanly
- Core modules compile cleanly
- No duplicated final outputs
- No intermediate prompt/tool leakage
- Core docs and runbooks are readable and up to date

### Gate 2. Persona Realism

- Existing regression and long-thread suites remain green
- Natural conversation probe suite is green
- In manual spot checks, companionship and memory-recall turns do not read like reports
- OOC drift remains controlled without depending on visible scaffolding in the final answer

### Gate 3. Worldline Continuity

- Commitments are stored, recalled, and referenced naturally
- Relationship repair and trust changes survive long-thread replay
- Rewinds/corrections/undo paths remain auditable
- Worldline metrics stay stable under isolated reruns

### Gate 4. Multimodal Reliability

- Text and TTS use the same final answer
- Interruption recovery remains stable with no "amnesia restart"
- Emotional style hints influence speech output consistently
- Failure paths degrade gracefully when speech is off or unavailable

### Gate 5. Research Assets

- Regression baseline report exists
- Long-thread baseline report exists
- At least one realism-oriented suite exists
- Ablation plan is defined and runnable
- User-study protocol and materials are ready for execution

## Phase Order

### Phase A. Freeze and Define

- Lock scope
- Define graduation gates
- Add explicit backend roadmap docs

### Phase B. Realism Pass

- Reduce report-like answers in companionship/memory-recall turns
- Keep structure for scientific/tool-driven tasks
- Add realism evaluation suite and manual probe scripts

### Phase C. Worldline Depth Pass

- Improve natural commitment reminders
- Improve relationship-state phrasing
- Expand long-thread failure taxonomy

### Phase D. Multimodal Reliability Pass

- Tighten TTS consistency
- Tighten interruption recovery
- Add backend-only multimodal regression cases

### Phase E. Research Closure

- Add ablation suite definitions
- Finalize user-study packet
- Export experiment-ready tables and baselines

### Phase F. Delivery Closure

- Final advisor/demo runbook
- Final defense talk track
- Final defense QA bank
- Final defense slide evidence map
- Final thesis figure/table map
- Final experiment chapter outline
- Final writing skeleton
- Final delivery manifest
- Final reproducibility checklist
- Final technical-preview package

### Phase G. Frontend and Character Shell

- Minimal showcase frontend
- Live2D
- Camera interaction
- Final productization layer

## Current Status

- Regression suite: green
- Long-thread suite: green
- Experience probe suite: green
- Backend reliability checks: green
- Ablation matrix: runnable and recorded
- Probe variance runner: implemented and recorded
- User-study raw-sheet generator: implemented
- Advisor reproducibility runbook: added
- Defense talk track: added
- Defense QA bank: added
- Defense slide evidence map: added
- Defense slide draft: added
- Defense slide final: added
- Defense 5-minute talk track: added
- Thesis figure/table map: added
- Thesis asset exports: added
- User-study thesis export path: added
- Experiment chapter outline: added
- Writing skeleton: added
- Final delivery manifest: added
- Final submission checklist: added
- Current baselines: see `docs/EVAL_BASELINE.md`
- Immediate next focus: execute the formal user study and finish delivery closure around the current green backend
