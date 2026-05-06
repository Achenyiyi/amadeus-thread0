# Procedural Growth Phase 3 Design

## Summary

`Procedural Growth Phase 3` adds outcome-calibrated procedural learning on top of the preserved Phase 1/2 contracts.

The phase does not add a new executor, browser authority, skill mutation surface, frontend, persona-core edit, or second memory store. It reads already-final action packet results, derives a bounded `procedural_outcome`, and uses that outcome to adjust procedural trace confidence before later planning bias is selected.

The intended loop is:

```text
procedural trace
-> Phase 2 planning bias
-> approval-gated action packet or boundary/manual guidance
-> final execution/browser/skill/workspace result
-> procedural outcome appraisal
-> trace confidence / boundary / recovery calibration
-> reconsolidated procedural continuity
```

## Goals

- Convert final action-packet attempts into normalized `procedural_outcome` records.
- Keep completed success as capability evidence while keeping blocked, rejected, pending, manual-takeover, and failed attempts honest.
- Adjust only procedural trace confidence and continuity metadata; never rewrite persona core, relationship core, or skills registry truth.
- Let Phase 2 planning prefer higher-confidence calibrated traces and avoid traces that were recently reinforced as boundary failures.
- Expose concise outcome readback in backend/session/CLI surfaces for debugging and handoff parity.
- Add deterministic smoke and audit coverage with readiness status `procedural_growth_phase3_ready`.

## Non-Goals

- No sandbox command family expansion.
- No package installation, shell wrappers, network execution, Docker socket mounting, privileged containers, or host secret passthrough.
- No automatic browser mutation or credential/OTP/passkey simulation.
- No dynamic skill generation, install/update/enable/disable/pin/unpin automation, or registry writeback into autobiographical memory.
- No frontend work.
- No Chinese reply-tone polishing.
- No new memory silo separate from `digital_body_consequence` / `interaction_carryover.embodied_context`.

## Architecture

Add a pure graph-adjacent module:

```text
amadeus_thread0/graph_parts/procedural_outcome.py
```

This module owns:

- `normalize_procedural_outcome(value)`
- `derive_procedural_outcomes_from_action_packets(action_packets, planning_bias=None, traces=None)`
- `calibrate_procedural_traces_with_outcomes(traces, outcomes)`
- `summarize_procedural_outcomes(outcomes)`

Existing modules keep their ownership:

- `procedural_growth.py` still owns trace extraction and final-state enrichment.
- `procedural_planning.py` still owns advisory planning bias.
- `final_state.py` resolves frozen final packets and calls enrichment.
- `backend_api.py`, `backend_session.py`, `turn_summary_export.py`, and `cli_views.py` only expose readback.

## Data Contract

`procedural_outcome` shape:

```python
{
    "outcome_id": "proc_out_...",
    "source_trace_id": "proc_...",
    "source_proposal_id": "ap-...",
    "source_run_id": "run-...",
    "planning_bias_kind": "sandbox_execute",
    "source_tool_name": "execute_workspace_command",
    "attempt_status": "completed",
    "outcome_kind": "confirmed_success",
    "confidence_delta": 0.08,
    "reuse_allowed": True,
    "boundary_reinforced": False,
    "recovery_hint": "",
    "evidence_refs": ["run-...", "stdout-ref"],
}
```

Allowed `outcome_kind` values:

- `confirmed_success`
- `partial_success`
- `failed_execution`
- `blocked_boundary_reinforced`
- `manual_takeover_required`
- `stale_or_mismatched_context`
- `no_executed_attempt`

Allowed `attempt_status` values:

- `completed`
- `executed`
- `blocked`
- `rejected`
- `expired`
- `awaiting_approval`
- `approved`
- `proposed`
- `queued`
- `executing`
- `pending`

Confidence policy:

- `confirmed_success`: positive delta, default `+0.08`, reuse allowed.
- `partial_success`: small positive delta, default `+0.02`, reuse allowed only when the packet completed with result evidence.
- `failed_execution`: negative delta, default `-0.12`, reuse not allowed until a later success revalidates the trace.
- `blocked_boundary_reinforced`: negative delta, default `-0.08`, boundary reinforced, no capability fact.
- `manual_takeover_required`: no capability confidence gain, boundary reinforced, manual requirement preserved.
- `stale_or_mismatched_context`: no confidence gain, reuse not allowed for the current context.
- `no_executed_attempt`: no confidence change and no capability fact.

## Integration Flow

1. `final_state.resolve_digital_body_consequence(...)` chooses final/frozen action packets as it already does.
2. `procedural_growth.enrich_digital_body_consequence_with_procedural_growth(...)` extracts traces.
3. Phase 3 derives outcomes from the same final packets and the current `procedural_planning`/packet `tool_args.procedural_planning` evidence.
4. Extracted or existing traces are calibrated with matching outcomes.
5. The enriched consequence exposes:

```python
{
    "procedural_outcomes": [...],
    "procedural_outcome_summary": {
        "procedural_outcome": True,
        "outcomes": [...],
        "last_outcome_kind": "confirmed_success",
        "confidence_delta_total": 0.08,
        "boundary_reinforced": False,
        "reuse_allowed": True,
    }
}
```

6. `interaction_carryover.embodied_context` preserves calibrated traces and outcomes.
7. `procedural_planning` ranks calibrated traces by priority and confidence. A boundary-reinforced trace remains readback-only.
8. Backend/session/CLI expose the same compact readback:

```text
outcome=<outcome_kind>:<source_run_id>:reuse|boundary|hold
```

## Safety Rules

- Outcome derivation only reads final packet fields.
- Pending/rejected/expired/approved-only packets cannot create completed capability facts.
- Failed or blocked outcomes cannot produce execution packets.
- Browser manual takeover outcomes never become browser mutation automation.
- Skill usage outcomes can describe completed use but cannot mutate the skill registry.
- Registry/install/lock truth remains outside autobiographical memory.
- Outcome evidence must stay attached to action/result refs, not a persona identity claim.

## Testing

Unit tests:

- outcome normalization and stable id generation
- sandbox success outcome
- sandbox failed execution outcome
- pending/no-executed attempt outcome
- manual browser takeover outcome
- trace calibration from success and failure
- Phase 2 planning prefers calibrated higher-confidence traces
- backend/session/CLI readback surfaces outcomes

Smokes:

- `calibrated_sandbox_success_boosts_reuse`
- `failed_sandbox_attempt_reduces_reuse`
- `manual_takeover_preserves_boundary`
- `pending_attempt_does_not_become_fact`

Audit:

- phase-3 unit tests
- phase-3 planning/backend readback tests
- phase-3 smokes
- guard suite for sandbox/skill/tool/world boundaries

Readiness:

```text
procedural_growth_phase3_ready
```

## Acceptance Criteria

- Phase 1/2 existing tests remain green.
- `python evals/run_procedural_growth_phase3_smokes.py` reports `overall_status=passed`.
- `python evals/run_procedural_growth_phase3_audit.py` reports `readiness_status=procedural_growth_phase3_ready`.
- No new authority surface is introduced.
- `program.md` records changed files, validation commands, results, and next step.
