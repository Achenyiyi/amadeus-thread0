# Complete Closeout Unlock Design

## Purpose

This slice turns the repository from "several preserved backend baselines plus deferred future lanes" into one explicit complete-closeout control plane.

The user direction is that the remaining locked lanes can now all be unlocked. In this repository, "unlocked" means a lane may move into a bounded implementation phase with its own spec, tests, approval semantics, and audit gate. It does not mean the runtime may silently widen into arbitrary host execution, unapproved browser mutation, secret capture, persona-core rewriting, or a second memory/body truth model.

## Scope

This closeout unlock does three things:

- updates the post-baseline status model so formerly deferred or tracked lanes become `unlocked_planned`
- expands the preserved-baselines audit into a current cross-gate meta-audit after procedural growth phase 4
- records a complete implementation order for the newly unlocked lanes

This slice does not directly implement all large unlocked runtime systems. Instead, it removes the phase locks, gives them a common readiness vocabulary, and prevents unsafe interpretation of "unlock" by keeping blocked surfaces explicit.

## Unlocked Lanes

The unlocked lanes are:

- multimodal input capture
- dynamic skill generation
- Chinese semantic de-scaffolding
- bounded capability growth beyond procedural phase 4
- natural long-horizon calibration
- external executor harness adapters
- frontend runtime shell

Each lane remains subordinate to the core Amadeus-K constraints:

- fixed persona core
- one unified memory substrate
- one digital body truth model
- packet-owned actions
- approval-gated external mutation
- truthful writeback only from completed facts

## Status Contract

`amadeus_thread0.runtime.post_baseline_closure` owns the closeout-unlock matrix.

Accepted statuses now include:

- `implemented_ready`
- `preserved_ready`
- `unlocked_planned`
- `deferred_fail_closed`
- `tracked_not_mainline`
- `quality_backlog_tracked`

The active closeout state should use `unlocked_planned` for lanes that are allowed to start but do not yet have a runtime-ready implementation.

`runtime_available=False` remains meaningful. It means the lane is unlocked for implementation, not that the runtime already exposes the capability.

## Cross-Gate Audit Contract

`evals/run_preserved_baselines_audit.py` is the complete preserved-gate meta-audit. It selects the latest report matching each expected `*_ready` status and verifies readiness for:

- backend freeze gate
- companion autonomy
- digital embodiment phase 2
- sandbox embodied execution phase 1
- skills ecosystem
- live browser runtime phase 1
- sandbox embodied execution phase 2
- post-baseline closure
- TTS presence timing
- procedural growth phases 1 through 4

Missing ready reports must be explicit failures. This matters because `evals/reports/` is gitignored, so a fresh worktree can lack the evidence even when the code is valid. Historical failed probe reports may remain in the reports directory, but they do not override a later or earlier authoritative ready artifact for a preserved baseline.

## Implementation Order After This Slice

1. Multimodal capture phase 1:
   capture consent, source artifact identity, and read-only perception ingestion.
2. Dynamic skills phase 1:
   proposal-only skill synthesis into registry candidates with hash verification and approval-gated enablement.
3. External executor harness phase 1:
   adapter candidates for external harnesses as result-only surfaces, never persona-memory owners.
4. Frontend runtime shell:
   backend.v1 consuming UI shell over existing transport adapter without inventing a second schema.
5. Chinese semantic de-scaffolding:
   replace brittle lexical heuristics with semantic diagnostics and tests before broad behavior rewrites.
6. Capability growth phase 5:
   bounded workflow formation over completed procedural traces, with no second capability memory.
7. Natural long-horizon calibration:
   evaluation-backed calibration of appraisal, own-rhythm, and relationship continuity over existing state contracts.

## Validation

This slice is ready when:

- post-baseline closure tests show formerly deferred lanes are `unlocked_planned`
- preserved-baselines tests cover the current closed gate set
- audit renderers expose unlocked-planned and category summaries
- docs record the complete closeout unlock posture
- targeted tests and py_compile pass
