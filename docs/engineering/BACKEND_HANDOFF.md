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

Frontend should treat `intent/status/risk/approval/result` as the stable autonomy packet contract.
If backend-owned execution hints such as `tool_name` or `tool_args` appear on a packet, they are runtime binding details, not fields frontend code should depend on.

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
- `digital_body.access_state` may now also carry structured access-acquisition guidance:
  - `access_acquire_proposals`
  - `selected_access_proposal`
  - each proposal may distinguish:
    - `path_kind=acquire_existing`
    - `path_kind=create_new`
  - when multiple proposals exist, `selected_access_proposal` is the current active choice:
    - backend should expose one deterministic default selection
    - approval consumers may override that choice explicitly
    - later approved / partial / completed states should keep referencing the same chosen path until it is truthfully cleared
- completed `access:refresh_state` packets are read-only runtime rechecks:
  - they may refresh `session_context.digital_body_hints`
  - they may tighten the visible `digital_body.access_state`
  - they do not claim that external login / browser / cookie mutation has already happened when no such runtime exists
- pending `access:request_help` packets are truthful external-entry requests:
  - they may bind `requested_help`, `requested_access`, and `primary_proposal_id` into `session_context.digital_body_hints`
  - they should surface through `autonomy.pending_approval` and `digital_body.access_state.mode=approval_pending`
  - they must not be rendered as a completed external action
  - they represent missing operator-provided conditions such as:
    - browser/session entry
    - account login
    - cookies
    - API key / quota help when the runtime itself cannot resolve the condition
  - proposal lists may now include bounded `create_new` candidates such as:
    - fresh account registration
    - fresh writable workspace creation
    - fresh API key / service entry creation
  - these are still proposal/approval surfaces, not claims that creation already happened
  - current bounded exception:
    - if the selected approved path is `operator_create_workspace`
    - backend may truthfully execute local workspace creation through `create_workspace_access`
    - but only inside the runtime-owned `AMADEUS_DATA_DIR/workspaces/` boundary
    - after that execution:
      - the same access path may close as `status=completed`
      - `digital_body.access_state.filesystem_state` should become `writable`
      - `digital_body.resource_state.active_artifact_kind` should become `workspace`
      - stale `selected_access_proposal` should be cleared
  - next bounded local mutation surface:
    - backend may also truthfully write a concrete file through `write_workspace_file`
    - but only inside the already resolved runtime workspace boundary
    - it must reject absolute paths and parent-directory escapes
    - after that execution:
      - `digital_body.resource_state.active_artifact_kind` should become `file`
      - `digital_body.resource_state.active_artifact_label` should point at the written file name
      - `artifact_context` should carry the concrete file surface, not the parent workspace shell
      - frozen readback may become more specific than generic procedural growth:
        - `digital_body_consequence.kind=workspace_file_updated`
        - `digital_body_consequence.artifact_mutation_mode=write`
    - backend may continue mutating that same concrete file surface through `append_workspace_file`
    - but still only inside the same resolved runtime workspace boundary
    - append does not widen the trust boundary; it only extends the same concrete `file` artifact continuity
    - append uses the same concrete frozen consequence family:
      - `digital_body_consequence.kind=workspace_file_updated`
      - `digital_body_consequence.artifact_mutation_mode=append`
    - backend may also edit an existing file surface through `replace_workspace_text`
    - but only inside the same resolved runtime workspace boundary
    - it performs exact-text replacement on an existing file rather than widening into arbitrary host editing
    - backend may also edit an existing file surface through `replace_workspace_lines`
    - but only inside the same resolved runtime workspace boundary
    - it performs inclusive line-span replacement on an existing file rather than widening into arbitrary host editing
    - replace uses the same concrete frozen consequence family:
      - `digital_body_consequence.kind=workspace_file_updated`
      - `digital_body_consequence.artifact_mutation_mode=replace`
    - when a workspace mutation still needs human approval, backend may attach a bounded `mutation_preview` to the approval tool call:
      - preview is read-only
      - preview is computed against the current runtime workspace/file surface
      - approval still governs the later real mutation, not the preview itself
    - that same preview is now part of the stable backend autonomy contract for pending mutation packets:
      - `autonomy.action_packets[*].mutation_preview`
      - `autonomy.pending_approval.mutation_preview`
      - frontend/CLI may display it as an inspection surface, but it must not infer execution authority from preview presence alone
    - backend now also has one bounded read-only inspection surface on the same workspace boundary:
      - `inspect_workspace_path`
      - it may inspect either:
        - the workspace root / a subdirectory
        - a concrete file under that workspace
      - it must still reject absolute paths and `..` escapes
      - it updates the active artifact truthfully without mutating host state
      - when inspection completes on an attached workspace/file surface, frozen readback may surface a concrete read-side fact:
        - `digital_body_consequence.kind=workspace_path_inspected`
        - this is truthful perception, not `procedural_growth`
      - when the currently active artifact is only a subdirectory inside a workspace, later workspace-relative writes must still resolve against the containing runtime workspace root rather than shrinking the trust boundary to that subdirectory
    - completed read-side artifact reacquisition may now also freeze as its own consequence family instead of disappearing into generic continuity:
      - `tool_name=reacquire_artifact`
      - `digital_body_consequence.kind=artifact_reacquired`
      - this records that a page/search/file/workspace surface was reattached, not that it was mutated
      - compact carrier/source identity should stay preserved:
        - `artifact_carrier`
        - `artifact_source_ref_ids`
        - `artifact_source_url`
        - `artifact_source_query`
        - `artifact_source_title`
        - `artifact_source_tool_name`
    - completed read-side access verification may now freeze as a concrete stable-path fact when no friction remains:
      - `tool_name=refresh_access_state`
      - `digital_body_consequence.kind=access_state_refreshed`
      - this means the current access/session boundary was re-checked, not that login/cookies/browser mutation already happened
  - when a proposal path has already been accepted but the real access update has not yet happened:
    - packet `status=approved` means `acquisition path accepted`
    - packet `status=completed` means `concrete access updates actually arrived`
    - for multi-grant paths, `status=approved` may still surface truthful partial progress rather than binary all-or-nothing completion:
      - `selected_access_proposal.resolved_grants`
      - `selected_access_proposal.pending_grants`
      - `selected_access_proposal.completion_ratio`
    - the accepted-but-not-yet-fixed path should still surface through:
      - `action_packets[*].selected_access_proposal`
      - `digital_body.access_state.selected_access_proposal`
      - `autonomy.intent.mode=access_acquire_planned`
    - if operator approval explicitly chooses another candidate path, backend should persist that new `selected_access_proposal` rather than silently snapping back to an earlier default
  - when those accepted conditions later become true in runtime-visible state, backend may emit one later-turn resolution packet:
    - `intent=access:request_help`
    - `status=completed`
    - `autonomy.intent.mode=access_request_resolved`
    - after that turn, stale live `selected_access_proposal` state should be cleared rather than lingering as `planned`
    - if that completed path actually created and attached a writable workspace through `create_workspace_access`, `digital_body_consequence.kind` may be more specific than generic access recovery:
      - `workspace_access_resolved`
      - this means the workspace was truthfully created or reattached, not merely proposed
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
- when a completed packet truthfully wrote or appended a bounded workspace file, `digital_body_consequence` may preserve:
  - `artifact_mutation_mode`
  - concrete `active_artifact_kind=file`
  - concrete `active_artifact_label` / `active_artifact_ref`
  so downstream consumers see that a file surface was actually changed, not only that generic tool growth happened.
- when artifact continuity is driven by a completed `artifact:*` packet, `digital_body_consequence` / carried `embodied_context` may also preserve the same compact artifact identity fields above so later turns know what carrier/source is being reattached without copying full previews.
- when access help has already advanced into an accepted-but-not-yet-fixed acquisition path, `digital_body_consequence` / carried `embodied_context` may also preserve:
  - `access_acquire_proposals`
  - `selected_access_proposal`
  so later turns can remember which path was accepted without pretending the access is already fixed.
- `digital_body_consequence` is the frozen embodied consequence of this turn, not a generic capability inventory.
- `behavior_action.embodied_context` and `behavior_plan.embodied_context` expose body/access continuity only; they must not be reinterpreted into relationship stance shifts.
- `interaction_carryover.embodied_context` is a carried-forward continuity trace, not a mirror of the current turn's runtime body state.
- embodied context must not be inferred into relationship previews when it was never written there; the preview-level `embodied_context` fields are optional and provenance-bound.
- frontend should consume these payloads as-is and must not infer backend internals from file layout or node names.
- approval UX should bind by `proposal_id`, not by list position alone.
- session-layer approval consumers should also handle synthetic `BackendSession.invoke_stream()` / `resume_stream()` requests with:
  - `approval_request.kind="access_request"`
  - `approval_request.source="access"`
  - `tool_calls[0].name="access_request_help"`
  - `tool_calls[0].args.access_acquire_proposals`
  - `tool_calls[0].args.selected_access_proposal`
  - edits/resolution bound to the same `proposal_id`

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
