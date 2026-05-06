# Procedural Growth Phase 4 Design

## Purpose

Procedural Growth Phase 4 turns calibrated failed, blocked, manual-takeover, and stale procedural outcomes into bounded recovery guidance.

Phase 1 captured procedural traces. Phase 2 let safe traces bias autonomy planning. Phase 3 calibrated those traces with final attempt outcomes. Phase 4 closes the next loop: when an attempt failed or hit a boundary, the system should remember how to recover without treating the failed attempt as a new capability fact.

## Scope

This phase adds advisory recovery readback over existing procedural outcomes. It does not add a new executor, browser authority, skill mutation surface, package install path, network path, desktop UI, persona-core edit, or memory store.

Recovery guidance may influence planning only by narrowing behavior:

- `failed_execution` may suggest inspecting failure logs or adjusting an already bounded command profile before reuse.
- `blocked_boundary_reinforced` must become boundary-only guidance and must not repeat the blocked family.
- `manual_takeover_required` must preserve manual browser takeover and must not create a browser mutation packet.
- `stale_or_mismatched_context` must suggest refreshing workspace/artifact context before reuse.
- `no_executed_attempt` remains an unfulfilled intention, not recovery evidence.

## Data Contract

The new normalized recovery item is `procedural_recovery`:

```python
{
    "recovery_id": "proc_rec_<stable_hash>",
    "source_outcome_id": "proc_out_<...>",
    "source_trace_id": "proc_<...>",
    "source_run_id": "run-...",
    "source_proposal_id": "ap-...",
    "recovery_kind": "inspect_failure_artifact",
    "status": "suggested",
    "safe_to_reuse": False,
    "requires_approval": False,
    "allowed_bias_kind": "workspace_guidance",
    "suggested_next_step": "inspect stderr/stdout artifacts before rerunning a bounded command",
    "must_not_repeat": ["package install", "browser mutation"],
    "evidence_refs": ["run-...", "stderr.txt"],
}
```

Allowed recovery kinds:

- `inspect_failure_artifact`
- `adjust_bounded_command`
- `preserve_manual_takeover`
- `avoid_blocked_boundary`
- `refresh_workspace_context`
- `hold_for_approval`
- `no_recovery_needed`

Allowed bias kinds:

- `workspace_guidance`
- `boundary_only`
- `browser_manual_takeover`
- `hold`

## Architecture

Add `amadeus_thread0/graph_parts/procedural_recovery.py` as a pure graph-adjacent helper. It consumes normalized procedural outcomes and, optionally, calibrated procedural traces. It returns normalized recovery items and a compact recovery summary.

Integrate recovery into the existing consequence/readback path:

- `procedural_growth.enrich_digital_body_consequence_with_procedural_growth()` attaches `procedural_recoveries` and `procedural_recovery_summary`.
- `digital_body_runtime.normalize_embodied_context()` preserves those fields.
- `turn_summary_export` exposes `summarize_procedural_recovery()`.
- `backend_api` exposes top-level `procedural_recovery` and current-turn recovery readback.
- `cli_views` exposes `current_turn.procedural_recovery` and compact `recovery=<kind>:<source_run_id>:<status>`.

Planning integration stays conservative. A failure or recovery-bearing trace must not produce execution-producing `sandbox_execute` bias until recovery has been resolved into a later confirmed success. In Phase 4, failed recovery evidence is readback/guidance only.

## Safety Rules

Recovery suggestions must never introduce:

- package installation
- shell wrappers
- git mutation
- network enablement
- Docker socket or privileged container access
- browser mutation without existing approval semantics
- skill install/update/enable/disable/pin/unpin
- external executor harness runtime
- persona-core or relationship-core rewrites

Only completed later attempts may become capability facts. Suggested, blocked, rejected, pending, and manual-takeover recovery items remain boundary or guidance records.

## Validation

Phase 4 is ready only when:

- recovery unit tests cover normalization, failed execution, manual takeover, boundary avoidance, stale context, and no-executed hold behavior
- planning tests prove failed/boundary recovery does not produce unsafe sandbox/browser mutation bias
- backend/session/CLI tests expose `procedural_recovery` readback
- deterministic smokes pass the required scenarios
- audit reports `procedural_growth_phase4_ready`

Required smoke scenarios:

- `failed_execution_suggests_failure_artifact_inspection`
- `blocked_boundary_recovery_does_not_repeat_blocked_action`
- `manual_takeover_recovery_preserves_takeover_boundary`
- `stale_context_recovery_refreshes_workspace_context`
- `no_executed_attempt_stays_hold`
