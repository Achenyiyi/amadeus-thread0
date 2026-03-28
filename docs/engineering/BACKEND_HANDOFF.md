# Backend Handoff

## Goal

This document is the short index for frontend handoff.

The authoritative frontend-facing backend contract now lives in:

- [`FRONTEND_INTERFACE_DELIVERABLE.md`](./FRONTEND_INTERFACE_DELIVERABLE.md)

That document is the one future frontend work should consume.

## Freeze-Lift Summary

Frontend integration should remain limited to contract consumption and adapter work unless the repository-level freeze gate in [`AGENTS.md`](../../AGENTS.md) stays satisfied.

For handoff purposes, the current backend should already be treated as:

- envelope-based
- final-state normalized
- transport-neutral
- stable enough for a thin frontend adapter
- autonomy-contract-first

## Stable Backend Surfaces

- runtime assembly: `amadeus_thread0.runtime.runtime_bundle`
- transport-neutral API: `amadeus_thread0.runtime.backend_api`
- turn/event/readback execution: `amadeus_thread0.runtime.backend_session`
- final-state normalization: `amadeus_thread0.runtime.final_state`

## Autonomy Envelope

Frontend consumers should treat autonomy as a stable sub-contract, not derive it indirectly from legacy fields.

Current turn/event/view payloads now expose:

- `autonomy.intent`
- `autonomy.action_packets`
- `autonomy.pending_approval`
- `autonomy.execution_trace`
- `autonomy.block_reason`

## Embodiment Envelope

Frontend consumers should also treat the embodied runtime as a stable sub-contract.

Current turn/persona/summary payloads now expose:

- `digital_body`
- `digital_body_consequence`
- `behavior_action.embodied_context` when the final behavior action itself carries embodied continuity
- `behavior_plan.embodied_context` when frozen final planning carries body/access continuity
- `interaction_carryover.embodied_context` when the active carryover itself is backed by persisted embodied context
- `turn_summary.digital_body`
- `turn_summary.digital_body_consequence`
- `turn_summary.behavior_plan.embodied_context` under the same provenance rule
- `turn_summary.interaction_carryover.embodied_context` under the same provenance rule
- `turn_summary.event_residue.digital_body_consequence` when a turn leaves an embodied consequence worth preserving at the event-residue layer
- `writeback_trace.revision_traces[*].embodied_context` when an exported revision trace was written from final `behavior_action` / `behavior_plan` / `behavior_consequence` / `interaction_carryover` semantics carrying embodied continuity
- `counterpart_assessment_preview[*].embodied_context` and `proactive_continuity_preview[*].embodied_context` only when persisted history explicitly carried embodied context

Interpretation rules:

- `behavior_queue` remains persona-owned continuity / life rhythm.
- `action_packets` remain structured execution units.
- completed `artifact:*` packets may now also carry `artifact_context`, which is the bounded structured reacquisition result:
  - `carrier`
  - `artifact_kind`
  - `artifact_ref`
  - `artifact_label`
  - `reacquisition_mode`
  - `preview`
  - `preview_truncated`
  - `exists`
  - `size_bytes`
  - `updated_at`
  - `source_ref_ids`
  - `source_url`
  - `source_query`
  - `source_title`
  - `source_tool_name`
- `digital_body` is the current runtime/body condition.
- `digital_body.access_state` may now also carry provider-side world conditions such as `api_key_state`, `quota_state`, reusable session lifecycle metadata like `session_continuity` / `session_expires_in_s` / `session_recovery_mode`, and time-bound retry metadata like `retry_after_s` / `cooldown_scope` when the runtime knows them.
- `digital_body.resource_state` may now also carry work-surface continuity facts such as:
  - `artifact_continuity`
  - `active_artifact_kind`
  - `active_artifact_ref`
  - `active_artifact_label`
  - `artifact_age_s`
  - `artifact_reacquisition_mode`
  - compact artifact identity when available:
    - `artifact_carrier`
    - `artifact_source_ref_ids`
    - `artifact_source_url`
    - `artifact_source_query`
    - `artifact_source_title`
    - `artifact_source_tool_name`
- `digital_body_consequence` may preserve the same session lifecycle fields when a turn ends in broken or blocked session continuity rather than a completed action.
- `digital_body_consequence` may also preserve frozen artifact continuity when a turn ended with a stale/detached/missing work surface and the reacquisition path matters for later continuation.
- when artifact continuity is driven by a completed `artifact:*` packet, `digital_body_consequence` / carried `embodied_context` may also preserve the same compact artifact identity fields above so later turns know what carrier/source is being reattached without copying full previews.
- `digital_body_consequence` is the frozen embodied consequence of this turn, not a generic capability inventory.
- `behavior_action.embodied_context` and `behavior_plan.embodied_context` expose body/access continuity only; they must not be reinterpreted into relationship stance shifts.
- `interaction_carryover.embodied_context` is a carried-forward continuity trace, not a mirror of the current turn's runtime body state.
- embodied context must not be inferred into relationship previews when it was never written there; the preview-level `embodied_context` fields are optional and provenance-bound.
- frontend should consume these payloads as-is and must not infer backend internals from file layout or node names.
- approval UX should bind by `proposal_id`, not by list position alone.

## Contract Assets

- detailed interface doc: [`FRONTEND_INTERFACE_DELIVERABLE.md`](./FRONTEND_INTERFACE_DELIVERABLE.md)
- TypeScript types: [`frontend_contract/backend_api.types.ts`](./frontend_contract/backend_api.types.ts)
- mock payloads:
  - [`assistant_turn.json`](./frontend_contract/mocks/assistant_turn.json)
  - [`event_round.json`](./frontend_contract/mocks/event_round.json)
  - [`persona_view.json`](./frontend_contract/mocks/persona_view.json)
  - [`worldline_view.json`](./frontend_contract/mocks/worldline_view.json)
  - [`bond_view.json`](./frontend_contract/mocks/bond_view.json)

## Validation Baseline

Minimum contract checks:

```powershell
python -m pytest tests/test_backend_api.py tests/test_backend_session.py
python -m pytest tests/test_final_state.py
python -m pytest tests/test_autonomy_backend_contract.py tests/test_autonomy_writeback.py
```
