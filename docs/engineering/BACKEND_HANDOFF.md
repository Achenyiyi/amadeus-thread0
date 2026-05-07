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
- callable through `BackendTransportAdapter` when a route-shaped Python adapter is useful
- HTTP-shaped through the Phase 1 WSGI wrapper when an in-process or server-hosted transport shell is useful
- stable enough for a thin frontend adapter
- product-runtime status is available through the Runtime Productization Phase 3 dashboard/audit layer
- technical-preview RC status is available through the Technical Preview RC Phase 1 evidence/audit layer
- advisor/demo package readiness is available through the Advisor Demo Readiness Phase 1 audit layer
- scripted advisor/demo dry-run readiness is available through the Advisor Demo Dry Run Phase 1 audit layer
- dynamic skill candidate lifecycle readback is available on turn/event payloads without automatic registry writes
- autonomy-contract-first
- frontend-frozen while backend baselines are preserved after `Sandbox Embodied Execution Phase 2`
- explicit about current execution scope being:
  - preserved baseline: `host-local restricted execution`
  - preserved baseline: `docker-isolated local execution`
- explicit about current live-environment scope being Playwright persistent-profile browser runtime, not the user's default browser profile

## Stable Backend Surfaces

- runtime assembly: `amadeus_thread0.runtime.runtime_bundle`
- transport-neutral API: `amadeus_thread0.runtime.backend_api`
- Python-callable route adapter: `amadeus_thread0.runtime.transport_adapter`
- HTTP thin wrapper: `amadeus_thread0.runtime.http_transport`
- turn/event/readback execution: `amadeus_thread0.runtime.backend_session`
- final-state normalization: `amadeus_thread0.runtime.final_state`
- executor adapter boundary: `amadeus_thread0.runtime.executor_adapter`
- restricted execution runner: `amadeus_thread0.runtime.sandbox_runner`
- live browser runner: `amadeus_thread0.runtime.browser_runner`
- access negotiation persona layer: `amadeus_thread0.runtime.access_negotiation`
- managed skills registry: `amadeus_thread0.runtime.skill_registry`
- runtime status dashboard: `amadeus_thread0.runtime.runtime_status_dashboard`
- technical preview RC gate: `amadeus_thread0.runtime.technical_preview_rc`
- operator console RC gate: `amadeus_thread0.runtime.operator_console_rc`
- advisor demo readiness gate: `amadeus_thread0.runtime.advisor_demo_readiness`
- advisor demo dry-run gate: `amadeus_thread0.runtime.advisor_demo_dry_run`
- dynamic skill candidate runtime readback: `amadeus_thread0.runtime.dynamic_skill_candidate_runtime`
- approved artifact multimodal runtime: `amadeus_thread0.runtime.approved_artifact_multimodal_runtime`
- Chinese semantic naturalness: `amadeus_thread0.runtime.chinese_semantic_naturalness`

## Product Runtime Status

Runtime Productization Phase 3 adds `runtime_status_dashboard.v1` and deterministic product runtime smokes.
Frontend and operator-console consumers should treat it as readback only:

- it clarifies whether preserved gate evidence, post-unlock roadmap evidence, and productization evidence are present and ready
- it distinguishes missing gitignored report artifacts from real runtime authority changes
- it lists blocked lanes such as live capture and external executor auto-enablement
- it marks HTTP transport, approved artifact multimodal ingestion, Chinese semantic naturalness, and dynamic skill candidate runtime as ready readback lanes; current `NEXT_SPECS` is empty when all preserved source reports are present

It does not add HTTP server ownership, live capture, automatic skill registry writes, multimodal model auto-calls, external harness execution, persona-core mutation, memory writes, or frontend-owned backend semantics.

## Technical Preview RC Status

Technical Preview RC Phase 1 adds `technical_preview_rc.v1` as the current release-candidate evidence gate.

Use it as evidence/readback only:

- it requires ready evidence from preserved baselines, runtime status dashboard, Runtime Productization Phase 3, HTTP Transport Thin Wrapper Phase 1, Approved Artifact Multimodal Runtime Phase 1, Chinese Semantic Naturalness Phase 1, and Dynamic Skill Candidate Runtime Phase 1
- it requires the current dashboard `NEXT_SPECS` list to be empty
- it preserves blocked authority for live capture, external executor auto-enablement, automatic dynamic skill registry writes, and multimodal model auto-calls
- `evals/run_technical_preview_rc_phase1_audit.py` emits JSON/Markdown reports under `technical-preview-rc-phase1-audit-*`

It does not add runtime authority, live capture, model calls, skill registry writes, memory writes, persona-core mutation, frontend-owned semantics, external harness execution, or HTTP server ownership.

## Operator Console RC Status

Operator Console RC Phase 1 adds `operator_console_rc.v1` as the current read-only release-candidate console over Technical Preview RC evidence.

Use it as operator/readback only:

- it composes `technical_preview_rc.v1`, `runtime_status_dashboard.v1`, and `operator_readback.v2`
- it exposes `BackendAPI.operator_console_rc()` and `GET /api/operator-console-rc`
- it gives operator panels for RC evidence, runtime status, operator readback, route inventory, and authority boundary
- it fails closed when RC evidence regresses, `NEXT_SPECS` is non-empty, mutation routes appear, or blocked authority widens
- `evals/run_operator_console_rc_phase1_audit.py` emits JSON/Markdown reports under `operator-console-rc-phase1-audit-*`

It does not add runtime authority, live capture, model calls, skill registry writes, memory writes, persona-core mutation, frontend-owned semantics, external harness execution, HTTP server ownership, SSE/WebSocket streaming, or external mutation.

## Advisor Demo Readiness Status

Advisor Demo Readiness Phase 1 adds `advisor_demo_readiness.v1` as the reviewer-facing package-readiness gate over Operator Console RC evidence and the documented advisor/demo reproduction package.

Use it as package/readback evidence only:

- it consumes ready `operator_console_rc.v1` evidence
- it checks required advisor, demo, evaluation, failure-taxonomy, and user-study docs exist
- it checks the current reproduction commands are documented
- it checks the demo script still covers role consistency, worldline commitment, conflict repair, source traceability, interruption recovery, and memory guard interception
- it preserves the Operator Console RC authority boundary and fails closed if blocked authority widens
- `evals/run_advisor_demo_readiness_phase1_audit.py` emits JSON/Markdown reports under `advisor-demo-readiness-phase1-audit-*`

It is not live demo certification. It does not run an advisor session, open live capture, call models, write skills, execute external harnesses, mutate memory, mutate persona core, create frontend-owned semantics, own an HTTP server, or perform external mutation.

## Advisor Demo Dry Run Status

Advisor Demo Dry Run Phase 1 adds `advisor_demo_dry_run.v1` as the scripted rehearsal and archive-readiness gate over Advisor Demo Readiness evidence and the demo/runbook/checklist/manifest package.

Use it as dry-run/readback evidence only:

- it consumes ready `advisor_demo_readiness.v1` evidence
- it checks all six scripted demo scenarios still include stable headings, user input, expected signals, and representative text
- it checks the runbook still covers CLI smoke, RC evidence, Advisor Demo Readiness, Advisor Demo Dry Run, baseline reproduction, probe variance, live demo path, artifact capture, failure handling, and exit condition
- it checks the package requires archiving RC reports, dry-run reports, eval JSON/Markdown reports, demo script, technical-preview checklist, and user-study assets
- it preserves the inherited Advisor Demo Readiness authority boundary and fails closed if blocked authority widens
- `evals/run_advisor_demo_dry_run_phase1_audit.py` emits JSON/Markdown reports under `advisor-demo-dry-run-phase1-audit-*`

It is not live demo certification. It does not run an advisor session, open live capture, call models, write skills, execute external harnesses, mutate memory, mutate persona core, create frontend-owned semantics, own an HTTP server, or perform external mutation.

## Dynamic Skill Candidate Runtime Status

Dynamic Skill Candidate Runtime Phase 1 adds `amadeus_thread0.runtime.dynamic_skill_candidate_runtime` as the backend-owned readback gate for frozen dynamic skill candidate lifecycle evidence.

Use it as readback only:

- `assistant_turn.payload.dynamic_skill_candidate_runtime` and `event_round.payload.dynamic_skill_candidate_runtime` expose `dynamic_skill_candidate_runtime.v1`
- `skills.dynamic_candidate_runtime` and `operator_readback.dynamic_skill_candidate_runtime` mirror compact summaries for frontend/operator views
- pending, blocked, rejected, drifted, or proposal-only candidates remain non-facts
- approved install evidence is visible only when the existing skills registry/session surfaces show the dynamic candidate as installed or active
- completed dynamic skill use remains the only path that may resurface as identity-safe procedural continuity

It does not install skills, auto-write the registry, mutate persona core, write autobiographical memory, mutate behavior motives, widen browser/tool/sandbox authority, call model APIs, open live capture, create frontend-owned semantics, or allow unapproved external mutation.

## HTTP Transport Status

HTTP Transport Thin Wrapper Phase 1 adds `amadeus_thread0.runtime.http_transport` as a standard-library WSGI wrapper over the existing route adapter.

Use it as transport glue only:

- `build_wsgi_app(transport_adapter)` wraps an existing `BackendTransportAdapter`
- `create_http_transport_app(backend_api)` builds that adapter from a `BackendAPI`-compatible object
- `call_wsgi_app(...)` exists for deterministic in-process smokes and tests
- responses are the same backend-owned `backend.v1` envelopes or structured JSON errors already defined by the adapter boundary

It does not add FastAPI, Flask, Uvicorn, SSE, WebSocket streaming, full turn execution routes, live capture, automatic skill registry writes, external harness runtime enablement, persona-core mutation, memory writes, or frontend-owned backend semantics.

## Approved Artifact Multimodal Runtime Status

Approved Artifact Multimodal Runtime Phase 1 adds `amadeus_thread0.runtime.approved_artifact_multimodal_runtime` as the approved-result ingestion gate for `artifact:inspect_multimodal` packets.

Use it as packet completion/readback glue only:

- `build_approved_artifact_multimodal_runtime_readback(...)` validates a frozen inspection packet, operator approval, and precomputed result before producing a completed packet
- `apply_approved_artifact_multimodal_runtime_to_payload(...)` can complete matching packets and attach backend-owned `approved_artifact_multimodal_runtime.v1` readback without mutating the input payload
- completion preserves the same `proposal_id`, spec, preview, tool binding, and capability steps
- drifted approvals, source-mismatched results, model-called results, live-capture-derived results, pending results, rejected results, or blocked results fail closed

It does not call multimodal model APIs, open live microphone/camera/background screen capture, create memory facts, mutate persona core, widen browser/tool/sandbox authority, create frontend-owned semantics, write the skill registry, or allow unapproved external mutation.

## Chinese Semantic Naturalness Status

Chinese Semantic Naturalness Phase 1 adds `amadeus_thread0.runtime.chinese_semantic_naturalness` as a deterministic readback gate over the existing Phase 2 semantic replacement policy.

Use it as naturalness diagnostics only:

- `build_chinese_semantic_naturalness_readback(...)` consumes the Phase 2 runtime policy and reports `chinese_semantic_naturalness.v1`
- `embodied_interaction.chinese_semantic_surface.naturalness` mirrors that readback next to `runtime_policy`
- diagnostics cover duplicate output, service framing, scaffold residue, text/TTS drift, and authority widening
- no-op already-natural text stays no-op and does not claim a rewrite

It does not rewrite generation prompts, call models, mutate persona core, write memory, mutate behavior motives, create frontend-owned semantics, open live capture, write the skill registry, or allow external mutation.

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
For sandbox execution packets, the stable contract additions are:

- `autonomy.action_packets[*].execution_spec`
- `autonomy.action_packets[*].execution_preview`
- `autonomy.action_packets[*].execution_result`
- `autonomy.pending_approval.execution_preview`

For sandbox phase 2, frontend/CLI should also expect these stable execution fields when present:

- `runner_kind`
- `isolation_level`
- `image_ref`
- `network_policy`
- `workspace_root_kind`

Frontend/CLI may render these as preview/result surfaces, but they must not reinterpret them as permission to widen execution scope.
The current callable executor adapter keeps the sandbox runner as the only enabled harness. Deep Agents, Codex, Claude, and OpenClaw harness candidates are disabled until a future architecture decision opens and validates one of them.
For live browser packets, the stable contract additions are:

- `autonomy.action_packets[*].browser_execution_spec`
- `autonomy.action_packets[*].browser_execution_preview`
- `autonomy.action_packets[*].browser_execution_result`
- `autonomy.pending_approval.browser_execution_preview`

Frontend/CLI may render these as preview/result surfaces, but they must not reinterpret them as permission to widen browser authority beyond the approved packet.
For access negotiation and manual browser takeover, the stable contract additions are:

- `autonomy.pending_approval.assist_request`
- `approval_request.payload.assist_request`

`assist_request` is a user-facing translation of the same authoritative truth already present in:

- `approval_request`
- `autonomy.pending_approval`
- `digital_body.access_state`
- the blocked/pending action packet family

It is not a second truth model. Minimum stable fields are:

- `kind`
- `message`
- `requested_access`
- `missing_access`
- `selected_access_proposal`
- `requires_manual_takeover`
- `resume_mode`
- browser continuity refs when applicable:
  - `proposal_id`
  - `profile_id`
  - `page_ref`
  - `tab_id`

Rendering rules:

- CLI/frontend should show the persona-facing request first, then the structured approval or takeover summary
- pending / blocked / rejected access still must not be rendered as owned capability
- when `resume_mode=auto_continue`, frontend should not force a second "continue?" prompt after the operator resolves the access or manual takeover

## Skills Envelope

Frontend and CLI should consume the `skills` block directly instead of reconstructing session skill state from prompt text or legacy memory notes.

Current turn/event payloads now expose:

- `skills.installed`
- `skills.matched`
- `skills.active`
- `skills.manual_overrides`
- `skills.pending_approval`

Interpretation rules:

- `installed` is the compact registry/session catalog surface:
  - no full `SKILL.md` body
  - metadata only (`skill_id/name/description/version/status/triggers/surfaces/...`)
- `matched` is the compact subset selected by runtime auto-match
- `active` is the only skill surface allowed to carry progressive-disclosure guidance such as `skill_excerpt`
- `manual_overrides` is the session-local override truth:
  - `enabled`
  - `disabled`
  - `pinned`
- `pending_approval` is the only stable approval surface for skill mutations:
  - `proposal_id`
  - `operation`
  - `skill_id`
  - `resolved_version`
  - `source`
  - `hash`
  - `requested_permissions`
  - `sandbox_profiles`
  - `verification_summary`
- skill registry/install state does not belong to autobiographical memory:
  - backend may write procedural/result consequences from final action packets later
  - backend must not present "pending install" as if the capability were already active
- skill continuity stays inside existing embodied / summary surfaces:
  - `digital_body_consequence.kind` may now truthfully use:
    - `skill_install_completed`
    - `skill_activation_changed`
    - `skill_usage_completed`
    - `skill_mutation_blocked`
  - `interaction_carryover.embodied_context.skill_effects` and `reconsolidation_snapshot.skill_effects` are the minimal cross-turn skill consequence surfaces
  - these are final-effect surfaces only; they do not replace registry truth
- interpretation rule:
  - completed install / enable / disable / use may appear as fact
  - proposal / pending / blocked / rejected mutations must not be rendered as already-owned capability

## Embodiment Envelope

Frontend consumers should also treat the embodied runtime as a stable sub-contract.

Frontend consumes this contract only.
It should not infer or rebuild backend internals from prompt text, legacy fields, or execution hints.

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
- `writeback_trace.revision_traces[*].preview_line` when a normalized revision trace carries embodied context and a compact read-model line is available
- `writeback_trace.counterpart_assessment_history[*].preview_line` and `writeback_trace.proactive_continuity_history[*].preview_line` when the normalized history row carries embodied context and a compact read-model line is available
- `writeback_trace.counterpart_assessment_history[*]` and `writeback_trace.proactive_continuity_history[*]` should be treated as typed normalized history rows, not raw `content` blobs:
  - scalar fields such as `respect_level`, `carryover_strength`, `created_at`, and anchor metrics may already be coerced at the row surface
  - nested compatibility `content` may also be normalized to match the same top-level typed contract
- `sources[*].preview_line`, `claim_links[*].preview_line`, and `claim_links[*].sources[*].preview_line` when the normalized source / claim-link row carries embodied context and a compact source-bearing read-model line is available
- `counterpart_assessment_preview[*].embodied_context` and `proactive_continuity_preview[*].embodied_context` only when persisted history explicitly carried embodied context

Interpretation rules:

- `behavior_queue` remains persona-owned continuity / life rhythm.
- `action_packets` remain structured execution units.
- current execution surface is `host-local restricted execution`:
  - workspace-local only
  - approval-gated for all sandbox execute packets
  - phase 1 baseline remains available as compatibility fallback
- preserved phase-2 execution baseline is `docker-isolated local execution`:
  - canonical runner: `docker_isolated_runner`
  - isolation level: `docker_local_isolated`
  - default network policy: `none`
  - allowed command families: `python`, `pytest`, `rg`, read-only `git`
  - blocked surfaces: package install, shell wrappers, git mutation, Docker socket mounting, privileged containers, host secret passthrough
  - runtime-owned workspace remains the default
  - `operator_attach_repo_root` requires explicit approval
  - same packet family, approval path, and body surfaces
  - still not a claim of provider-side remote infra
- current sandbox execute family is:
  - `intent=sandbox:execute_workspace_command`
  - `risk=external_mutation`
  - `requires_approval=true`
- sandbox execution previews/results are stable packet payloads, not ad hoc tool-only blobs:
  - `execution_spec`
  - `execution_preview`
  - `execution_result`
- approval/resume must preserve the same:
  - `proposal_id`
  - `execution_spec`
- approved repo-root attach remains the only phase-2 non-runtime-owned workspace expansion:
  - proposal mode: `operator_attach_repo_root`
  - completed attach writes `digital_body_consequence.kind=workspace_root_attached`
  - pending/rejected attach must not be rendered as already-owned workspace capability
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
- completed skill effects may also surface through the same embodied continuity path:
  - `digital_body_consequence.skill_effects`
  - `interaction_carryover.embodied_context.skill_effects`
  - retrieval/export surfaces that already carry embodied context
- `digital_body.access_state` is the only stable access-truth container:
  - flat compatibility fields such as `mode`, `session_continuity`, `browser_session`, `quota_state`
  - phase 2 nested detail mirrors such as:
    - `session_state`
    - `account_state_detail`
    - `quota_state_detail`
    - `permission_state`
    - `sandbox_state`
- `digital_body.access_state.sandbox_state` is the stable sandbox truth surface:
  - `availability`
  - `allowed_roots`
  - `execution_policy`
  - `last_status`
  - `runner_kind`
  - `isolation_level`
  - `image_ref`
  - `network_policy`
  - `workspace_root_kind`
  - `last_command_profile`
  - `last_exit_code`
  - `last_run_id`
  - `arbitrary_execution`
- `digital_body.access_state.browser_runtime_state` is the stable live-browser truth surface:
  - `availability`
  - `profile_root`
  - `context_status`
  - `active_page_id`
  - `active_tab_count`
  - `downloads_dir`
  - `last_action_status`
  - `last_run_id`
  - `manual_takeover_required`
  - `runner_kind`
  - `isolation_level`
- `digital_body.resource_state` is the only stable active-resource container:
  - `artifact_continuity`
  - `artifact_carrier`
  - `active_artifact_kind`
  - `active_artifact_ref`
  - `active_artifact_label`
  - `workspace_root`
  - `artifact_source_ref_ids`
  - `preferred_source_ref_id`
  - `preferred_anchor_reason`
- when the active carrier is a live page, frontend/CLI should also expect:
  - `artifact_carrier=browser_page`
  - `active_artifact_kind=page`
  - `browser_profile_id`
  - `browser_tab_id`
  - `artifact_source_url`
- `digital_body_consequence.kind` may now also truthfully use live-browser families:
  - `browser_navigation_completed`
  - `browser_interaction_completed`
  - `browser_download_completed`
  - `browser_upload_completed`
  - `browser_takeover_requested`
  - `browser_action_blocked`
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
  - they may also carry `assist_request.kind=grant_access` so the user sees where she is blocked, what needs to be opened, and that she will continue automatically afterward
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

## Skills Handoff Status

Skills closure is now treated as preserved backend contract, not an open buildout slice.

- current authored local skills are:
  - `skills/source-ref-anchor-review`
  - `skills/workspace-regression-triage`
- current closeout evidence is:
  - `evals/run_skills_ecosystem_smokes.py`
  - `evals/run_skills_ecosystem_audit.py`
  - ready reports:
    - `evals/reports/skills-ecosystem-audit-20260405-130543-closeout-fix-c.{json,md}`
    - `evals/reports/skills-ecosystem-audit-20260405-130706-closeout-fix-d.{json,md}`
    - `evals/reports/skills-ecosystem-audit-20260405-130706-closeout-fix-e.{json,md}`
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
    - backend now also has one bounded read-only inspection surface on the existing saved external-material carrier:
      - `inspect_source_ref`
      - it may inspect a previously saved `source_ref` by id / ref / label
      - it does not claim a live browser session; it only re-enters already stored external material inside the current runtime
      - it updates active artifact continuity truthfully onto the `source_ref` carrier
      - when the active `source_ref` surface is still attached but marked `stale`, backend may derive an automatic read-only `artifact:inspect_source_ref` packet so continuity repair stays an inspection fact rather than being mislabeled as generic reacquisition
      - when inspection completes on an attached external-material surface, frozen readback may surface:
        - `digital_body_consequence.kind=source_material_inspected`
        - this is truthful material inspection, not `procedural_growth`
    - backend now also has one bounded read-only comparison surface on the same saved-material carrier:
      - `compare_source_refs`
      - it compares two already saved `source_ref` materials; it does not fetch new material and does not claim a live browser
      - when runtime continuity still carries two related saved refs and the active surface is stale, backend may derive `artifact:compare_source_refs` before falling back to plain re-inspection
      - when runtime continuity carries a bounded candidate set instead of just a pair, `compare_source_refs` may select the comparison partner from that candidate set at execution time
      - comparison should preserve the same compact carrier identity, with `artifact_source_ref_ids` carrying an ordered continuity set:
        - preferred anchor first
        - directly compared partner next
        - remaining saved candidates only as bounded follow-up continuity
      - preferred-anchor state should also stay explicit in the same compact identity payload:
        - `preferred_source_ref_id`
        - `preferred_anchor_reason`
      - if one side becomes the preferred anchor after comparison, live artifact continuity should now point at that preferred saved material rather than staying pinned to the original stale side by accident
      - if a later stale turn already carries that stable preferred anchor, backend should derive `artifact:inspect_source_ref` for the preferred saved material rather than re-running the same pairwise compare by default
      - when comparison completes on an attached external-material surface, frozen readback may surface:
        - `digital_body_consequence.kind=source_material_compared`
        - this is truthful material re-anchoring, not `procedural_growth`
      - retrieved `source_material_compared` traces may later feed runtime continuity bias so downstream behavior / motive selection can continue along the re-anchored material line
      - the same retrieved compare trace may also refresh `session_context.digital_body_hints` when the current turn already exposes a visible `source_ref` context:
        - refreshable fields include `artifact_source_ref_ids`, `preferred_source_ref_id`, `preferred_anchor_reason`, and missing saved-material metadata
        - this is a continuity refresh, not permission to invent a new active `source_ref` surface from retrieval alone
        - if the live turn exposes no visible `source_ref` context, the retrieved compare trace must remain non-seeding and stay only as carryover bias
      - once preferred-anchor fields exist on a saved-material line, frontend-facing backend outputs should preserve them consistently across both direct and summarized surfaces:
        - `digital_body.resource_state.preferred_source_ref_id`
        - `digital_body.resource_state.preferred_anchor_reason`
        - `digital_body_consequence.preferred_source_ref_id`
        - `digital_body_consequence.preferred_anchor_reason`
        - corresponding turn-summary / CLI summary views for the same active line
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
    - any completed tool result that returns `artifact_context` must now be allowed to refresh `session_context.digital_body_hints` through the same compact artifact identity path:
      - packet-only artifact facts are not enough
      - live `digital_body_state`, frozen `digital_body_consequence`, backend payloads, and CLI summaries must all be able to converge on the same active artifact truth
    - completed read-side access verification may now freeze as a concrete stable-path fact when no friction remains:
      - `tool_name=refresh_access_state`
    - `digital_body_consequence.kind=access_state_refreshed`
- external web material now has two truthful paths:
  - saved-material path:
    - use `source_ref` continuity for long-horizon resurfacing and explicit saved references
    - `source_ref` does not imply a live browser session, restored cookies, or resumed tab
  - live-page path:
    - use `artifact_carrier=browser_page` plus `browser_runtime_state` for the current live browser session
    - this does not imply arbitrary host execution or automatic account creation
  - when the current access/session boundary is only being re-checked, do not render it as if login/cookies/browser mutation already happened
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
  - `workspace_root` when the current artifact is attached inside a runtime workspace
  - `active_artifact_label`
  - `artifact_age_s`
  - `artifact_reacquisition_mode`
  - compact artifact identity when available:
    - `artifact_carrier`
    - `artifact_source_ref_ids`
- `workspace_root` is the stable workspace trust boundary for summarized consumers:
  - frontend/CLI may display it
  - they should not infer a narrower write boundary from a subdirectory/file `active_artifact_ref`
  - later relative workspace writes still resolve against `workspace_root`
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
- sandbox execution consequences stay explicit:
  - `sandbox_execution_completed`
  - `sandbox_execution_blocked`
- approved-but-not-executed sandbox packets must not be flattened into completed embodied facts.
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

The frozen frontend shell also carries matching copies under `frontend/src/contracts/` and `frontend/src/mocks/`.
Keep both copies synchronized and let `tests/test_frontend_contract_sync.py` enforce the contract.

## Validation Baseline

Minimum contract checks:

```powershell
python -m pytest tests/test_backend_api.py tests/test_backend_session.py
python -m pytest tests/test_final_state.py
python -m pytest tests/test_autonomy_backend_contract.py tests/test_autonomy_writeback.py
python -m pytest tests/test_sandbox_backend_contract.py tests/test_sandbox_embodied_execution_smokes.py tests/test_sandbox_embodied_execution_audit.py
python evals/run_sandbox_embodied_execution_audit.py
```
