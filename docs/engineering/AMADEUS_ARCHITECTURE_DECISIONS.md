# Amadeus Architecture Decisions

This document records the current architecture decisions derived from the `digital persona lifeform seed` direction and the recent `OpenClaw` comparison study.

It is not a generic agent roadmap.
It is the decision contract for what `Amadeus-K` should become and what it should explicitly avoid becoming.

## Decision Frame

- `OpenClaw` is useful as a systems reference, not as a product template.
- `Amadeus-K` remains a `digital persona system`, not a personal ops shell.
- We borrow `runtime structure`, `continuity`, and `presence` ideas.
- We do not borrow `task-first identity` or tool-heavy persona drift.
- The latest closed execution target is `Sandbox Embodied Execution Phase 2`: one fixed persona interacting with the digital world through one unified memory substrate, one bounded runtime body, one managed capability ecology, one truthful live browser/runtime surface, and one Docker-isolated local execution backend that still stays outside persona-core.
- The post-baseline tail items selected on `2026-05-06` are closed as a bounded closure pack, not as a new capability-expansion phase.
- `Bounded Procedural Growth Phase 1` is now implemented as the next bounded slice on top of those baselines: completed embodied actions may leave reusable procedural traces, while blocked actions leave boundary notes only.
- `Procedural Growth Phase 2` is now implemented as the next advisory planning slice: resurfaced procedural traces may bias autonomy planning, but execution remains packet-owned and approval-gated.
- `Procedural Growth Phase 3` is now implemented as outcome-calibrated procedural learning: final action-packet results adjust procedural trace confidence and boundary/recovery readback without widening execution, browser, skill, frontend, persona-core, or memory authority.
- `Procedural Growth Phase 4` is now implemented as recovery-oriented procedural adaptation: failed, blocked, manual-takeover, stale, and unexecuted outcomes produce bounded recovery guidance without becoming new capability facts.
- `Complete Closeout Unlock` is now active as the control-plane decision after procedural growth phase 4: formerly deferred or tracked lanes may enter bounded implementation phases as `unlocked_planned`, but no lane gains runtime authority until its own spec, tests, approval semantics, and audit gate close.
- The unlocked lanes are multimodal input capture, dynamic skill generation, Chinese semantic de-scaffolding, bounded capability growth beyond phase 4, natural long-horizon calibration, external executor harness adapters, and a frontend runtime shell.
- `Post-Unlock Roadmap` is now implemented as a bounded release gate: all seven lanes have phase specs, implementation slices, tests, smoke/audit runners, and ready reports, while each lane's blocked surfaces remain in force.
- `Runtime Productization Phase 1` is now implemented as a readback/productization gate: backend API, backend session, transport adapter, CLI summary, and audit surfaces expose one operator readback without adding runtime authority.
- `Runtime Productization Phase 2` is now implemented as an operator-console readback gate: `operator_readback.v2` adds console health, evidence summary, read-only route inventory, and next-action hints without adding runtime authority.
- `Runtime Productization Phase 3` is now implemented as a product-runtime integration hardening gate: `runtime_status_dashboard.v1`, deterministic product smokes, and a Phase 3 audit make preserved gates, route-envelope consumption, blocked lanes, ready readback lanes, and gitignored source-report availability visible without adding HTTP server ownership or runtime authority.
- `HTTP Transport Thin Wrapper Phase 1` is now implemented as a standard-library WSGI transport gate: `amadeus_thread0.runtime.http_transport` wraps the existing `BackendTransportAdapter`, returns the same `backend.v1` envelopes through HTTP-shaped calls, and adds no backend semantics, execution authority, live capture, automatic skill registry writes, external harness enablement, SSE/WebSocket streaming, or framework dependency.
- `Operator Console RC Phase 1` is now implemented as a read-only release-candidate console gate: `operator_console_rc.v1` composes `technical_preview_rc.v1`, `runtime_status_dashboard.v1`, and `operator_readback.v2`, exposes `BackendAPI.operator_console_rc()` / `GET /api/operator-console-rc`, and adds no runtime authority, live capture, model calls, skill registry writes, external harness enablement, frontend-owned semantics, HTTP server ownership, or persona/memory mutation.
- `Advisor Demo Readiness Phase 1` is now implemented as a reviewer-facing package-readiness gate: `advisor_demo_readiness.v1` composes ready Operator Console RC evidence with required advisor/repro docs, reproduction-command coverage, demo-script scenario coverage, and closed authority-boundary truth; it proves the handoff package is reproducible, not that a live demo has already been observed, and adds no runtime authority, live capture, model calls, skill registry writes, external harness enablement, frontend-owned semantics, HTTP server ownership, persona mutation, memory writes, or external mutation.
- `Residual Living Loop Closure Phase 1` is now implemented as a north-star residual closure gate: post-unlock residuals are evaluated against one traceable loop from perception through self-narrative update, without opening live capture, automatic skill registry writes, external harness execution, frontend-owned semantics, persona-core mutation, memory writes, or unapproved external mutation.
- `Living Loop Runtime Realism Phase 1` is now implemented as a causal/north-star realism gate: visible loop stages must align across appraisal-to-motive, state-to-behavior, action/plan, consequence/reconsolidation, and final semantics, while Chinese semantic de-scaffolding gains deterministic replacement guidance and conservative safe-surface floors without broad prompt rewrites.
- `Living Loop Runtime Realism Phase 2` is now implemented as a backend-payload realism gate: `assistant_turn` and `event_round` payloads carry `living_loop_realism`, proving the same causal readback consumes backend-style `turn_summary` / `writeback_trace` payloads without changing generation or authority boundaries.
- `Living Loop Runtime Realism Phase 3` is now implemented as an artifact-alignment realism gate: backend payloads carrying Phase 5 `embodied_interaction.artifact_behavior_alignment` are promoted to `living_loop_runtime_realism_phase3_ready`, while payloads without alignment remain Phase 2 ready and unsafe or mutating alignment evidence fails closed without memory writes, behavior mutation, persona-core mutation, model API calls, frontend semantics, or authority widening.
- `Chinese Semantic De-Scaffolding Phase 2` is now implemented as a typed runtime replacement policy gate: deterministic Chinese safe floors expose `chinese_semantic_surface.runtime_policy` with family, semantic intent, replacement strategy, applied floor, and authority boundaries, while `final_text`, `reconsolidation_snapshot.final_text`, and `tts_text` remain aligned and prompt sprawl, model calls, persona-core mutation, memory writes, behavior mutation, frontend-owned semantics, skill registry writes, live capture, and external mutation stay blocked.
- `Chinese Semantic Naturalness Phase 1` is now implemented as a deterministic readback gate layered over Phase 2: `chinese_semantic_surface.naturalness` checks safe floors and already-natural text for duplicate output, service framing, scaffold residue, text/TTS drift, and authority widening without prompt rewrites, model calls, persona-core mutation, memory writes, behavior mutation, frontend-owned semantics, live capture, skill registry writes, or external mutation.
- `Multimodal Perception Phase 2` is now implemented as an approval-gated artifact inspection packet gate: consent-bound artifacts may propose `artifact:inspect_multimodal` packets with spec/preview/result readback, pending packets never auto-execute or call model APIs, and completed semantics come only from approved precomputed inspection results while live microphone/camera/background screen capture remains blocked.
- `Approved Artifact Multimodal Runtime Phase 1` is now implemented as the approved-result ingestion gate for that packet family: exact operator-approved precomputed results can complete the same frozen `artifact:inspect_multimodal` packet after proposal/spec/source drift checks, while drifted, model-called, live-capture-derived, pending, rejected, or blocked results fail closed without becoming semantic observations, memory facts, or completed capability facts.
- `Frontend Runtime Shell Phase 2` is now implemented as a route-consumption readback gate: the React/Vite shell can consume route-like `backend.v1` envelopes, render `operator_readback`, `living_loop_realism`, `embodied_interaction`, `runtime_productization`, and `operator_console_rc`, and remains consumer-only without owning memory, body, autonomy, persona, graph, browser, sandbox, skill-registry, live-capture, HTTP-server, or external-mutation semantics.
- `Embodied Interaction Runtime Phase 1` is now implemented as the first runtime integration gate over the unlocked multimodal and Chinese semantic lanes: `assistant_turn` and `event_round` payloads carry `embodied_interaction`, consent-bound source artifacts enter current-turn/body/carryover surfaces, and deterministic Chinese semantic floors update final/snapshot text together without opening live capture, multimodal model API calls, persona-core mutation, memory writes, external execution, skill registry writes, frontend-owned semantics, or unapproved external mutation.
- `Embodied Interaction Runtime Phase 2` is now implemented as approved artifact perception semantics: already-approved artifact metadata may enter perception/appraisal/carryover semantic observation surfaces while keeping live capture, multimodal model API calls, persona-core mutation, memory writes, execution authority, skill registry writes, frontend-owned semantics, and unapproved external mutation blocked.
- `Embodied Interaction Runtime Phase 3` is now implemented as approved artifact appraisal evidence coupling: Phase 2 semantic observations may become read-only appraisal-facing evidence and influence hints while still avoiding memory facts, persona-core mutation, live capture, multimodal model API calls, execution authority changes, skill registry writes, frontend-owned semantics, and unapproved external mutation.
- `Embodied Interaction Runtime Phase 4` is now implemented as approved artifact motive/goal advisory coupling: Phase 3 appraisal evidence may become read-only motive/goal hints that surface beside the behavior plan without replacing actual behavior motives or widening memory, model, browser, sandbox, frontend, skill, or persona authority.
- `Embodied Interaction Runtime Phase 5` is now implemented as motive-to-behavior alignment readback: Phase 4 motive hints may be compared against actual behavior action / behavior plan motives so the runtime can distinguish `causally_aligned`, `advisory_not_reflected`, and `behavior_conflict_observed` without changing behavior, writing memory, calling models, or widening authority.
- `Technical Preview RC Phase 1` is now implemented as an evidence-complete release-candidate gate: preserved baselines, runtime status dashboard, runtime productization phase 3, HTTP transport, approved artifact multimodal runtime, Chinese semantic naturalness, and dynamic skill candidate runtime evidence are composed into one RC readback, `NEXT_SPECS` must be empty, and any widened authority for live capture, external executor auto-enablement, dynamic skill registry auto-write, or multimodal model auto-calls fails closed.

## Backend Status

Status as of `2026-05-07`: `freeze-gate-ready, companion-autonomy-ready, digital-embodiment-phase1-ready, digital-embodiment-phase2-ready, sandbox-embodied-execution-phase1-ready, skills-ecosystem-ready, live-browser-runtime-phase1-ready, sandbox-embodied-execution-phase2-ready, post-baseline-closure-ready, procedural-growth-phase1-ready, procedural-growth-phase2-ready, procedural-growth-phase3-ready, procedural-growth-phase4-ready, post-unlock-roadmap-ready, chinese-semantic-descaffolding-phase2-ready, chinese-semantic-naturalness-phase1-ready, multimodal-perception-phase2-ready, approved-artifact-multimodal-runtime-phase1-ready, dynamic-skills-phase2-ready, dynamic-skill-candidate-runtime-phase1-ready, frontend-runtime-shell-phase2-ready, runtime-productization-phase1-ready, runtime-productization-phase2-ready, runtime-productization-phase3-ready, technical-preview-rc-phase1-ready, operator-console-rc-phase1-ready, advisor-demo-readiness-phase1-ready, http-transport-thin-wrapper-phase1-ready, residual-living-loop-phase1-ready, living-loop-runtime-realism-phase1-ready, living-loop-runtime-realism-phase2-ready, living-loop-runtime-realism-phase3-ready, embodied-interaction-runtime-phase1-ready, embodied-interaction-runtime-phase2-ready, embodied-interaction-runtime-phase3-ready, embodied-interaction-runtime-phase4-ready, embodied-interaction-runtime-phase5-ready`

For backend purposes, the structural decisions in this document are now split into:

- baseline gate: `python evals/run_backend_freeze_gate_audit.py`
- autonomy gate: `python evals/run_companion_autonomy_audit.py`
- digital embodiment gate: `python evals/run_digital_embodiment_audit.py`
- sandbox embodiment gate: `python evals/run_sandbox_embodied_execution_audit.py`
- sandbox phase 2 gate: `python evals/run_sandbox_phase2_audit.py`
- skills ecosystem gate: `python evals/run_skills_ecosystem_audit.py`
- live browser gate: `python evals/run_live_browser_runtime_audit.py`
- post-baseline closure gate: `python evals/run_post_baseline_closure_audit.py`
- procedural growth gate: `python evals/run_procedural_growth_audit.py`
- procedural growth phase 2 gate: `python evals/run_procedural_growth_phase2_audit.py`
- procedural growth phase 3 gate: `python evals/run_procedural_growth_phase3_audit.py`
- procedural growth phase 4 gate: `python evals/run_procedural_growth_phase4_audit.py`
- preserved-baselines meta-gate: `python evals/run_preserved_baselines_audit.py`
- post-unlock roadmap gate: `python evals/run_post_unlock_roadmap_audit.py`
- Chinese semantic de-scaffolding phase 2 gate: `python evals/run_chinese_semantic_descaffolding_phase2_audit.py`
- Chinese semantic naturalness phase 1 gate: `python evals/run_chinese_semantic_naturalness_phase1_audit.py`
- multimodal perception phase 2 gate: `python evals/run_multimodal_perception_phase2_audit.py`
- approved artifact multimodal runtime phase 1 gate: `python evals/run_approved_artifact_multimodal_runtime_phase1_audit.py`
- runtime productization gate: `python evals/run_runtime_productization_audit.py`
- runtime productization phase 3 gate: `python evals/run_runtime_productization_phase3_audit.py`
- HTTP transport thin-wrapper gate: `python evals/run_http_transport_audit.py`
- technical preview RC gate: `python evals/run_technical_preview_rc_phase1_audit.py`
- operator console RC gate: `python evals/run_operator_console_rc_phase1_audit.py`
- advisor demo readiness gate: `python evals/run_advisor_demo_readiness_phase1_audit.py`
- residual living-loop gate: `python evals/run_residual_living_loop_audit.py`
- living-loop runtime realism gate: `python evals/run_living_loop_realism_audit.py`
- living-loop runtime realism phase 2 gate: `python evals/run_living_loop_realism_phase2_audit.py`
- living-loop runtime realism phase 3 gate: `python evals/run_living_loop_realism_phase3_audit.py`
- embodied interaction runtime gate: `python evals/run_embodied_interaction_runtime_audit.py`
- embodied interaction runtime phase 2 gate: `python evals/run_embodied_interaction_runtime_phase2_audit.py`
- embodied interaction runtime phase 3 gate: `python evals/run_embodied_interaction_runtime_phase3_audit.py`
- embodied interaction runtime phase 4 gate: `python evals/run_embodied_interaction_runtime_phase4_audit.py`
- embodied interaction runtime phase 5 gate: `python evals/run_embodied_interaction_runtime_phase5_audit.py`
- current handoff posture:
  - frontend runtime shell work is unlocked only as a `backend.v1` contract consumer
  - backend contract is stable enough to consume
  - autonomy contract is baseline-complete
  - digital embodiment phase 1 remains the preserved workspace/access/resource baseline
  - digital embodiment phase 2 is formally closed on the same body contract
  - sandbox embodied execution phase 1 is formally closed on the same body contract
  - skills ecosystem formal closure is now also formally closed on the same body contract
  - live browser runtime closure phase 1 is now also formally closed on the same body contract
  - sandbox embodied execution phase 2 is now also formally closed on the same body contract
  - `search_web + source_ref` continuity remains preserved as the saved-material path; live browser is additive, not a replacement
  - current workspace execution posture is split into:
    - preserved baseline: `host-local restricted execution`
    - preserved baseline: `docker-isolated local execution`
  - current live browser posture remains Playwright persistent-profile runtime with approval-gated mutations and manual takeover for sensitive login steps
  - current access-negotiation posture is persona-first but truth-bound:
    - missing access or sensitive takeover should surface as a persona-facing request first
    - approval/manual takeover then reuses the same structured truth
    - after resolution the runtime should auto-continue on the same task when safe
    - no credential guessing, OTP simulation, CAPTCHA bypass, or cookie forgery paths are allowed
  - current post-baseline closure posture is:
    - callable transport adapter exists as `amadeus_thread0.runtime.transport_adapter.BackendTransportAdapter`
    - no FastAPI/Flask/Uvicorn dependency is introduced
    - executor adapter exists as `amadeus_thread0.runtime.executor_adapter`
    - the only enabled executor adapter is `sandbox_runner`
    - Deep Agents, Codex, Claude, and OpenClaw executor harnesses are documented but fail closed
    - formerly deferred or tracked lanes are now `unlocked_planned`
    - `unlocked_planned` means the lane may begin a bounded implementation phase, not that the runtime already exposes the capability
    - blocked surfaces remain explicit for multimodal input capture, dynamic skill generation, Chinese semantic de-scaffolding, bounded capability growth, natural long-horizon calibration, external executor harnesses, and frontend runtime shell work
  - current post-unlock roadmap posture is:
    - `multimodal_capture_phase1_ready`: consent-bound source artifacts and read-only perception events are implemented; live microphone/camera/background screen/secret capture remains blocked
    - `multimodal_perception_phase2_ready`: approval-gated `artifact:inspect_multimodal` packets are implemented for consent-bound artifacts; pending previews never auto-execute or call model APIs, and completed observations only come from approved precomputed inspection results
    - `approved_artifact_multimodal_runtime_phase1_ready`: exact approved precomputed inspection results may complete frozen `artifact:inspect_multimodal` packets after proposal/spec/source drift checks; unsafe or drifted result attempts fail closed
    - `dynamic_skills_phase1_ready`: completed procedural traces may propose hash-verified skill candidates; install/enable/registry writes remain approval-gated and manual
    - `dynamic_skills_phase2_ready`: exact frozen dynamic candidate payloads may be installed/enabled after approval through the existing managed skills registry; pending/rejected/drifted candidates never become active skills or memory facts
    - `dynamic_skill_candidate_runtime_phase1_ready`: frozen dynamic skill candidate lifecycle evidence is visible on real backend payloads as readback only; proposals remain non-facts until approved install evidence and completed use are present
    - `external_executor_harness_phase1_ready`: external harness families are represented as disabled result-only metadata; only `sandbox_runner` is enabled
    - `frontend_runtime_shell_phase1_ready`: the React/Vite shell builds against `backend.v1` fixtures and does not own backend semantics
    - `frontend_runtime_shell_phase2_ready`: the same shell consumes route-like `backend.v1` envelopes through a thin adapter and renders runtime/productization, living-loop, and embodied readbacks without owning backend semantics
    - `chinese_semantic_descaffolding_phase1_ready`: semantic diagnostics exist before any broad runtime rewrite; legacy post-baseline tracking remains compatible
    - `chinese_semantic_descaffolding_phase2_ready`: deterministic typed runtime policy envelopes are implemented for known scaffold families, with final/snapshot/TTS parity and no prompt/model/persona/memory/behavior/frontend/skill/external authority widening
    - `chinese_semantic_naturalness_phase1_ready`: deterministic readback diagnostics validate known scaffold-family floors and no-op natural text without ad hoc tone polishing or prompt/model/persona/memory/behavior/frontend/skill/external authority widening
    - `capability_growth_phase5_ready`: workflow candidates are advisory continuity over completed traces, not capability claims
    - `natural_long_horizon_calibration_phase1_ready`: deterministic offline packs evaluate the lived-loop surface without scene scripts
  - current runtime productization posture is:
    - `runtime_productization_phase1_ready`: `amadeus_thread0.runtime.runtime_productization` composes existing post-baseline, post-unlock, preserved-baseline, and current-turn readbacks into one operator surface
    - `runtime_productization_phase2_ready`: the same module now emits `operator_readback.v2` with console health, evidence summary, read-only route inventory, and next-action hints
    - `runtime_productization_phase3_ready`: `runtime_status_dashboard.v1`, product runtime smokes, and the Phase 3 audit make source-report gaps, blocked lanes, ready readback lanes, and route-envelope consumption visible without adding server or execution authority
    - `technical_preview_rc_phase1_ready`: `technical_preview_rc.v1` composes the current technical preview evidence set into one release-candidate readback and fails closed if `NEXT_SPECS` is non-empty or blocked authority widens
    - `BackendAPI.runtime_productization()` and `BackendSession.operator_readback_view()` expose the same readback family to runtime consumers
    - `assistant_turn` and `event_round` payloads now include `operator_readback`
    - `BackendTransportAdapter` exposes `GET /api/runtime-productization`
    - CLI compact summaries may render `productization=runtime_productization_phase2_ready`, `console=ready`, and `next=monitor_runtime_readback`
    - the productization phases are readback/smoke/audit-only and do not enable HTTP server semantics, live capture, automatic skill registry writes, multimodal model auto-calls, external harness execution, frontend-owned backend semantics, persona-core mutation, memory writes, or unapproved external mutation
  - current HTTP transport posture is:
    - `http_transport_thin_wrapper_phase1_ready`: `amadeus_thread0.runtime.http_transport` exposes a WSGI-compatible app factory over `BackendTransportAdapter`
    - `build_wsgi_app(transport_adapter)` and `create_http_transport_app(backend_api)` provide HTTP-shaped request/response flow for existing adapter routes
    - `call_wsgi_app(...)` is a deterministic in-process test helper, not a second backend API
    - the wrapper parses JSON bodies and query strings, serializes backend-owned envelopes, and preserves structured 400/404/405 errors from the adapter boundary
    - it does not own memory, body, autonomy, persona, graph execution, browser, sandbox, skills, multimodal, frontend, external harness, SSE/WebSocket, or model-call semantics
  - current residual living-loop posture is:
    - `residual_living_loop_phase1_ready`: `amadeus_thread0.runtime.residual_living_loop` evaluates living-loop traceability and residual lane boundaries as one pure readback contract
    - `evals/run_residual_living_loop_audit.py` emits deterministic json/md reports under `residual-living-loop-audit-*`
    - optional operator readback can include the residual block, but productization readiness remains governed by the existing post-baseline/post-unlock/preserved-baseline inputs
    - this phase is a closure/audit layer, not a capability widening layer
  - current living-loop runtime realism posture is:
    - `living_loop_runtime_realism_phase1_ready`: `amadeus_thread0.runtime.living_loop_realism` evaluates causal alignment between visible loop stages rather than mere field presence
    - `evals/run_living_loop_realism_audit.py` emits deterministic json/md reports under `living-loop-realism-audit-*`
    - `living_loop_runtime_realism_phase2_ready`: the same module normalizes real backend payloads and attaches `living_loop_realism` to `assistant_turn` / `event_round`
    - `evals/run_living_loop_realism_phase2_audit.py` emits backend-payload json/md reports under `living-loop-realism-phase2-audit-*`
    - `living_loop_runtime_realism_phase3_ready`: the same module consumes existing Phase 5 `embodied_interaction.artifact_behavior_alignment` readback from backend payloads, proves alignment visibility, and keeps payloads without alignment at Phase 2 readiness
    - `evals/run_living_loop_realism_phase3_audit.py` emits artifact-alignment json/md reports under `living-loop-realism-phase3-audit-*`
    - Phase 3 preserves `advisory_not_reflected` as truthful readback, fails closed on unsafe or mutating alignment claims, and does not recalculate alignment from raw artifacts
    - `amadeus_thread0.graph_parts.chinese_semantic_surface` now returns replacement guidance, conservative safe-surface floors, and typed runtime replacement policies for brittle Chinese surface families
    - `amadeus_thread0.runtime.chinese_semantic_naturalness` now returns deterministic naturalness diagnostics over those policies and exposes `chinese_semantic_naturalness_phase1_ready`
    - `chinese_semantic_descaffolding_phase2_ready` means these policies are audited across everyday, repair, self-rhythm, and technical-task cases for duplicate output, scaffold residue leaks, and text/TTS drift
    - `chinese_semantic_naturalness_phase1_ready` means known scaffold floors and already-natural text are audited for duplicate output, service framing, scaffold residue, text/TTS drift, and authority widening
    - this phase is readback/guidance/runtime-floor policy only and does not enable prompt-sprawl rewrites, live capture, model API calls, skill registry writes, external harness execution, frontend-owned semantics, persona-core mutation, behavior mutation, memory writes, or unapproved external mutation
  - current embodied interaction runtime posture is:
    - `embodied_interaction_runtime_phase1_ready`: `amadeus_thread0.runtime.embodied_interaction_runtime` connects unlocked multimodal source artifacts and Chinese semantic floors to real backend turn/event payloads
    - `embodied_interaction_runtime_phase2_ready`: `amadeus_thread0.runtime.artifact_perception_semantics` converts approved artifact metadata into bounded semantic observations, and `embodied_interaction_runtime` mirrors those observations into perception, appraisal, and carryover surfaces
    - `embodied_interaction_runtime_phase3_ready`: `amadeus_thread0.runtime.artifact_appraisal_bridge` converts those approved semantic observations into read-only appraisal evidence, and `embodied_interaction_runtime` mirrors that evidence into perception, appraisal, perception semantics, and carryover surfaces
    - `embodied_interaction_runtime_phase4_ready`: `amadeus_thread0.runtime.artifact_motive_bridge` converts approved appraisal evidence into read-only motive/goal advisory hints, and `embodied_interaction_runtime` mirrors those hints into perception, appraisal, carryover, and advisory behavior-plan surfaces without replacing actual motives
    - `embodied_interaction_runtime_phase5_ready`: `amadeus_thread0.runtime.artifact_behavior_alignment` compares approved motive hints against actual behavior action / behavior plan motives, and `embodied_interaction_runtime` mirrors that alignment into perception, appraisal, carryover, and advisory behavior-plan surfaces without mutating behavior
    - `multimodal_perception_phase2_ready`: `amadeus_thread0.runtime.multimodal_sources` now builds approval-gated `artifact:inspect_multimodal` packets, `action_packets` preserves the inspection spec/preview/result fields, and `artifact_perception_semantics` admits only completed approved precomputed results as `source=approved_inspection_result`
    - `approved_artifact_multimodal_runtime_phase1_ready`: `amadeus_thread0.runtime.approved_artifact_multimodal_runtime` validates exact approvals and precomputed results before completing those frozen packets, and can attach backend-owned `approved_artifact_multimodal_runtime` readback to a payload
    - `assistant_turn` and `event_round` payloads now include `embodied_interaction`
    - consent-bound source artifacts surface through `current_event.perception_sources`, `digital_body.resource_state.multimodal_source_refs`, and `interaction_carryover.embodied_context.multimodal_sources`
    - approved artifact semantics surface through `embodied_interaction.artifact_semantics.semantic_observations`, `current_event.perception.semantic_observations`, `turn_appraisal.perception_semantics`, and `interaction_carryover.embodied_context.artifact_semantic_observations`
    - completed approved multimodal inspection results can feed the same artifact semantics surfaces; pending, rejected, blocked, or live-capture-derived attempts do not become semantic observations
    - approved artifact appraisal evidence surfaces through `embodied_interaction.artifact_appraisal.evidence_items`, `current_event.perception.appraisal_evidence`, `turn_appraisal.artifact_evidence`, `turn_appraisal.perception_semantics.appraisal_evidence`, and `interaction_carryover.embodied_context.artifact_appraisal_evidence`
    - approved artifact motive/goal hints surface through `embodied_interaction.artifact_motive.motive_hints`, `current_event.perception.motive_hints`, `turn_appraisal.motive_evidence`, `turn_appraisal.perception_semantics.motive_hints`, `interaction_carryover.embodied_context.artifact_motive_hints`, and advisory `behavior_plan.artifact_motive_hints`
    - approved artifact behavior alignment surfaces through `embodied_interaction.artifact_behavior_alignment.alignment_items`, `current_event.perception.behavior_alignment`, `turn_appraisal.behavior_alignment_evidence`, `turn_appraisal.perception_semantics.behavior_alignment`, `interaction_carryover.embodied_context.artifact_behavior_alignment`, and advisory `behavior_plan.artifact_behavior_alignment`
    - Phase 4 and Phase 5 keep `behavior_action.primary_motive` and `behavior_plan.primary_motive` intact; hints and alignment may guide readback but are not behavior mutations
    - deterministic Chinese semantic floors may update `final_text` and `reconsolidation_snapshot.final_text` together for known brittle scaffold families, with Phase 2 `tts_text` parity inside `chinese_semantic_surface.runtime_policy`
    - deterministic Chinese semantic naturalness diagnostics surface under `chinese_semantic_surface.naturalness` without changing prompt generation, persona core, memory, behavior motives, frontend semantics, or authority boundaries
    - `evals/run_embodied_interaction_runtime_audit.py` emits deterministic json/md reports under `embodied-interaction-runtime-audit-*`
    - `evals/run_embodied_interaction_runtime_phase2_audit.py` emits deterministic json/md reports under `embodied-interaction-runtime-phase2-audit-*`
    - `evals/run_embodied_interaction_runtime_phase3_audit.py` emits deterministic json/md reports under `embodied-interaction-runtime-phase3-audit-*`
    - `evals/run_embodied_interaction_runtime_phase4_audit.py` emits deterministic json/md reports under `embodied-interaction-runtime-phase4-audit-*`
    - `evals/run_embodied_interaction_runtime_phase5_audit.py` emits deterministic json/md reports under `embodied-interaction-runtime-phase5-audit-*`
    - `evals/run_multimodal_perception_phase2_audit.py` emits deterministic json/md reports under `multimodal-perception-phase2-audit-*`
    - this phase does not call multimodal model APIs, open live microphone/camera/background screen capture, create memory facts, mutate persona core, mutate behavior motives, widen memory or execution authority, write the skill registry, create frontend-owned semantics, or allow unapproved external mutation
  - current procedural-growth posture is:
    - `amadeus_thread0.graph_parts.procedural_growth` owns reusable procedural trace normalization and hinting
    - `amadeus_thread0.graph_parts.procedural_planning` owns advisory procedure-guided planning bias
    - `amadeus_thread0.graph_parts.procedural_outcome` owns final attempt outcome normalization and trace confidence calibration
    - `amadeus_thread0.graph_parts.procedural_recovery` owns recovery guidance derived from failed, blocked, manual-takeover, stale, and unexecuted outcomes
    - completed / executed packets may create capability traces
    - blocked packets may create boundary traces only
    - pending / rejected / expired / approved-but-not-executed packets do not create completed capability facts
    - resurfaced hints preserve approval and manual-takeover requirements
    - only safe sandbox planning bias may produce existing approval-gated sandbox action packets
    - blocked, browser-manual-takeover, and skill-guidance bias remain readback/planning-only
    - outcome-calibrated traces may adjust confidence but cannot create new executor, browser, skill registry, persona-core, or memory authority
    - recovery-oriented traces may narrow planning into workspace guidance, boundary-only readback, manual takeover preservation, or hold states
    - unresolved recovery never produces a direct execution-producing packet
    - procedural traces are digital-body continuity, not persona-core or registry truth

Closure evidence by decision family:

- `Session Fabric + Perception Event`
  - runtime: `amadeus_thread0.runtime.runtime_bundle`, `amadeus_thread0.runtime.backend_session`, `amadeus_thread0.runtime.event_identity`
  - checks: `tests/test_perception_event_contract.py`, `tests/test_thread_runtime.py`, `tests/test_runtime_bundle.py`, `tests/test_turn_events.py`, `tests/test_session_context.py`
- `Persona Core Fixed + Self Model Evolves`
  - runtime: `amadeus_thread0/persona_specs/`, `amadeus_thread0.graph_parts.persona_runtime`, `amadeus_thread0.graph_parts.appraisal`, `amadeus_thread0.graph_parts.behavior_runtime`
  - checks: `tests/test_persona_runtime.py`, `tests/test_appraisal_calibration.py`, `tests/test_behavior_runtime_alignment.py`, `tests/test_dialogue_mode_counterpart.py`
- `Final Semantics Freeze Before Writeback`
  - runtime: `amadeus_thread0.graph_parts.prepare_turn_runtime`, `amadeus_thread0.graph_parts.memory_evolution`, `amadeus_thread0.runtime.final_state`
  - checks: `tests/test_memory_evolution_semantic_writeback.py`, `tests/test_prepare_turn_runtime.py`, `tests/test_response_finalize.py`, `tests/test_final_state.py`, `tests/test_backend_api.py`
- `Counterpart Model + Relationship Appraisal`
  - runtime: `amadeus_thread0.graph_parts.relational_runtime`, `amadeus_thread0.graph_parts.relational_carryover`, `amadeus_thread0.utils.counterpart_profile`
  - checks: `tests/test_dialogue_mode_counterpart.py`, `tests/test_world_model_residue.py`, `tests/test_counterpart_profile.py`
- `Own Rhythm Engine + Presence Layer`
  - runtime: `amadeus_thread0.graph_parts.behavior_agenda`, `amadeus_thread0.graph_parts.behavior_runtime`, `amadeus_thread0.runtime.backend_session`
  - checks: `tests/test_idle_event_context.py`, `tests/test_cli_threading.py`, `tests/test_backend_session.py`, `tests/test_subjective_review_pack.py`
- `Capability Bus Outside Persona Core`
  - runtime: tool routing and approval stay in runtime/tooling surfaces, not persona authority surfaces
  - checks: `tests/test_tooling_routing.py`, `tests/test_tool_approval_policy.py`
- `Managed Skills Ecosystem`
  - runtime: `amadeus_thread0.runtime.skill_registry`, `amadeus_thread0.graph_parts.skill_runtime`, `amadeus_thread0.runtime.backend_api`, `amadeus_thread0.runtime.backend_session`
  - checks: `tests/test_skill_registry.py`, `tests/test_skill_runtime.py`, `tests/test_skills_ecosystem_smokes.py`, `tests/test_skills_ecosystem_audit.py`, `tests/test_tool_approval_policy.py`, `tests/test_backend_api.py`, `tests/test_backend_session.py`, `tests/test_autonomy_writeback.py`, `tests/test_world_model_residue.py`
- `Relational Boundary Guard + Full Persona Traceability`
  - runtime: `counterpart_assessment`, `boundary_pressure`, `reconsolidation_snapshot`, `writeback_trace`
  - checks: `tests/test_behavior_runtime_alignment.py`, `tests/test_memory_guard.py`, `tests/test_backend_api.py`, `tests/test_cli_views.py`

This status does not change the intentional guardrails below:

- cross-surface continuity beyond the current backend contract still comes later
- subagents remain peripheral to persona-core judgment
- arbitrary host-side code generation remains deferred until sandbox and approval boundaries are explicit

Phase 2 preserved contract:

- keep one body contract:
  - `digital_body.access_state`
  - `digital_body.resource_state`
- do not open a second work-only container for session/account/search/sandbox state
- saved `source_ref` continuity remains the truthful saved-material carrier, and live browser runtime is now an additive real-time surface rather than a fake reopen shim
- `selected_access_proposal` remains the stable active path while partial/completed access truth evolves
- new world facts such as session/account/quota/permission/sandbox state must resurface through:
  - `digital_body_consequence`
  - `interaction_carryover.embodied_context`
  - retrieval resurfacing
  - later motive / behavior selection
- current local status for phase 2:
  - targeted phase 2 runtime/API/writeback/residue suites are green
  - `digital_embodiment_manual_smokes` is now a formal blocking check inside `run_digital_embodiment_audit.py`
  - fresh authoritative closeout reports are green:
    - `evals/reports/digital-embodiment-audit-20260404-192406-phase2-closeout-a.{json,md}`
    - `evals/reports/digital-embodiment-audit-20260404-194010-phase2-closeout-b.{json,md}`
    - `evals/reports/digital-embodiment-audit-20260404-195802-phase2-closeout-c.{json,md}`
  - phase 2 is formally closed and should now be treated as a preserved backend baseline

Sandbox Embodied Execution Phase 1 preserved contract:

- keep the same single body contract:
  - `digital_body.access_state`
  - `digital_body.resource_state`
- do not introduce a second execution-only state container
- the current execution surface is intentionally narrow:
  - `host-local restricted execution`
  - `workspace-local commands only`
  - no package install, no arbitrary host-side codegen
- execution remains approval-gated and packet-owned:
  - intent: `sandbox:execute_workspace_command`
  - stable packet fields:
    - `execution_spec`
    - `execution_preview`
    - `execution_result`
  - approval must resume the same `proposal_id` and the same `execution_spec`
- embodied truth must stay singular across packet/state/writeback/retrieval:
  - `digital_body.access_state.sandbox_state`
  - `digital_body_consequence`
  - `interaction_carryover.embodied_context`
  - retrieved embodied traces
- run identity must remain available for follow-up turns:
  - `run_id`
  - `cwd`
  - `profile`
  - `exit_code`
  - filesystem artifact refs
- closeout evidence for this phase is:
  - `evals/run_sandbox_embodied_execution_smokes.py`
  - `evals/run_sandbox_embodied_execution_audit.py`
  - targeted sandbox/runtime/backend/residue tests in `tests/test_sandbox_*`, `tests/test_backend_*`, `tests/test_autonomy_writeback.py`, and `tests/test_world_model_residue.py`
  - fresh closeout reports now include:
    - `evals/reports/sandbox-embodied-execution-audit-20260404-225854-phase1-closeout-b.{json,md}`
    - `evals/reports/sandbox-embodied-execution-audit-20260404-232002-phase1-closeout-c.{json,md}`
    - `evals/reports/sandbox-embodied-execution-audit-20260404-233428-phase1-closeout-d.{json,md}`

Sandbox Embodied Execution Phase 2 preserved contract:

- keep the same single body/runtime truth:
  - `digital_body.access_state`
  - `digital_body.resource_state`
  - `autonomy.action_packets[*]`
- Docker is the canonical phase-2 runner family:
  - `runner_kind=docker_isolated_runner`
  - `isolation_level=docker_local_isolated`
  - explicit `image_ref`
  - default `network_policy=none`
  - no privileged mode, Docker socket mount, host secret passthrough, or package-install surface
- allowed execution surface remains bounded to coding/research closure:
  - `python`
  - `pytest`
  - `rg`
  - read-only `git`
  - raw shell strings, shell wrappers, package managers, git mutation, and networked execution remain blocked
- workspace truth remains explicit:
  - runtime-owned workspace stays the default safe root
  - `operator_attach_repo_root` is the only new attach path in this phase
  - attached root must resolve to a real git worktree root
  - completed attach writes `workspace_root_attached`
  - pending/rejected attach does not become owned capability
- packet contract additions for phase 2 stay on the existing execution family:
  - `execution_spec.runner_kind`
  - `execution_spec.isolation_level`
  - `execution_spec.image_ref`
  - `execution_spec.network_policy`
  - `execution_spec.workspace_root_kind`
  - same fields mirrored on `execution_preview`
- embodied writeback/resurfacing must preserve:
  - `run_id`
  - `cwd`
  - `profile`
  - `exit_code`
  - `workspace_root`
  - artifact/log refs
  - isolated runner identity
- closeout evidence for this phase is:
  - `python evals/run_sandbox_phase2_smokes.py`
  - `python evals/run_sandbox_phase2_audit.py`
  - latest authoritative ready reports:
    - `evals/reports/sandbox-phase2-audit-20260503-203559-phase2-ready-a.{json,md}`
    - `evals/reports/sandbox-phase2-audit-20260503-203721-phase2-ready-b.{json,md}`
    - `evals/reports/sandbox-phase2-audit-20260503-203850-phase2-ready-c.{json,md}`
  - latest phase-2 audit pass streak: `3`
  - phase 2 is formally closed and should now be treated as a preserved backend baseline

Post-Baseline Closure Pack preserved contract:

- This closure pack resolves the selected tail items `2,3,4,5,6,7,11,12` without opening a new broad phase.
- HTTP/Web adapter closure:
  - implemented as a Python-callable adapter over `BackendAPI`
  - route-like calls return existing `backend.v1` envelopes as dictionaries
  - no server framework dependency is introduced
  - future HTTP/SSE/WebSocket work should wrap this adapter or the same `BackendAPI` methods rather than rebuilding response semantics
- TTS presence timing closure:
  - `TTS_presence_timing` is preserved as timing-only digital-body telemetry
  - fresh closure reports now include:
    - `evals/reports/tts-presence-timing-audit-20260506-015822-post-baseline-closure-a.{json,md}`
    - `evals/reports/tts-presence-timing-audit-20260506-015901-post-baseline-closure-b.{json,md}`
    - `evals/reports/tts-presence-timing-audit-20260506-015942-post-baseline-closure-c.{json,md}`
- Executor adapter closure:
  - implemented as `amadeus_thread0.runtime.executor_adapter`
  - `execute_workspace_command` now routes through the adapter while preserving existing `execution_spec`, `execution_preview`, and `execution_result` shapes
  - external harness candidates are disabled and may not own persona memory or writeback facts
  - closeout report:
    - `evals/reports/executor-adapter-audit-20260506-015758-post-baseline-closure.{json,md}`
- Complete closeout unlock lanes:
  - multimodal input capture: `multimodal_capture_phase1_ready`
  - dynamic skill generation: `dynamic_skills_phase1_ready`
  - approved dynamic skill candidate install/readback: `dynamic_skills_phase2_ready`
  - dynamic skill candidate runtime readback: `dynamic_skill_candidate_runtime_phase1_ready`
  - Chinese semantic de-scaffolding: `chinese_semantic_descaffolding_phase1_ready`
  - bounded capability growth: `capability_growth_phase5_ready`
  - natural long-horizon calibration: `natural_long_horizon_calibration_phase1_ready`
  - external executor harness adapters: `external_executor_harness_phase1_ready`
  - frontend runtime shell: `frontend_runtime_shell_phase2_ready`
  - these statuses close bounded implementation specs; they still do not widen beyond each lane's explicit runtime/approval boundary
- Final closure evidence:
  - `evals/reports/post-baseline-closure-audit-20260506-020030-final.{json,md}`
  - `overall_status=passed`
  - `readiness_status=post_baseline_closure_ready`

Bounded Procedural Growth Phase 1 preserved contract:

- This phase adds reusable procedural continuity without widening runtime authority.
- The owned graph-adjacent module is `amadeus_thread0.graph_parts.procedural_growth`.
- Allowed phase-1 trace kinds are:
  - `workspace_procedure`
  - `sandbox_execution_pattern`
  - `browser_runtime_pattern`
  - `skill_usage_pattern`
  - `blocked_boundary_pattern`
  - `recovery_pattern`
- Writeback remains final-state based:
  - completed / executed embodied packets may become reusable procedural traces
  - blocked packets may become boundary/friction traces only
  - pending / rejected / expired / awaiting-approval / approved-only packets do not become completed capability facts
  - frozen reconsolidation procedural traces win over stale live intermediates
- Resurfacing remains advisory:
  - `procedural_hint` is a planning hint, not execution authority
  - sandbox and browser traces preserve `must_request_approval`
  - manual browser takeover resurfaces as a boundary note
  - blocked traces set `capability_claim=false`
- Backend and CLI readback expose compact `procedural_growth` summaries while keeping the canonical embodied truth on `digital_body_consequence`.
- This phase does not add dynamic skill generation, package install, wider sandbox command families, external executor harness runtime, frontend UI, persona-core edits, or a second memory store.
- Initial closure evidence:
  - `evals/reports/procedural-growth-smokes-20260506-030102-phase1-dev.{json,md}`
  - `evals/reports/procedural-growth-audit-20260506-030113-phase1-dev.{json,md}`
  - `overall_status=passed`
  - `readiness_status=procedural_growth_phase1_ready`

Procedural Growth Phase 2 preserved contract:

- This phase adds procedure-guided autonomy planning without widening runtime authority.
- The owned graph-adjacent module is `amadeus_thread0.graph_parts.procedural_planning`.
- `procedural_planning` is advisory readback and planning bias, not an execution fact:
  - reads carried `procedural_traces`, `procedural_continuity.traces`, and compact hints
  - dedupes by trace id and ignores low-confidence traces
  - requires current request match before execution-producing bias
  - checks workspace root, runner, isolation, and network policy before sandbox execution bias
- Allowed phase-2 bias kinds are:
  - `sandbox_execute`
  - `browser_manual_takeover`
  - `skill_guidance`
  - `workspace_guidance`
  - `boundary_only`
- Only `sandbox_execute` with a completed capability trace may produce an action packet, and that packet must keep:
  - `intent=sandbox:execute_workspace_command`
  - `status=awaiting_approval`
  - `risk=external_mutation`
  - `requires_approval=true`
  - existing `execution_spec` / `execution_preview` boundaries
- Boundary-only traces, browser manual takeover traces, and skill guidance traces do not create execution/browser/registry mutation packets.
- Backend and CLI readback expose:
  - `autonomy.procedural_planning`
  - `turn_summary.autonomy.procedural_planning`
  - `turn_summary.current_turn.procedural_planning`
  - compact `planproc=<bias_kind>:<source_run_id>:approval|boundary|hint`
- This phase does not add dynamic skill generation, package install, wider sandbox command families, automatic browser mutation, external executor harness runtime, frontend UI, persona-core edits, or a second memory store.
- Initial closure evidence:
  - `evals/reports/procedural-growth-phase2-smokes-20260506-033738-phase2-dev.{json,md}`
  - `evals/reports/procedural-growth-phase2-audit-20260506-033746-phase2-dev.{json,md}`
  - `overall_status=passed`
  - `readiness_status=procedural_growth_phase2_ready`

Procedural Growth Phase 3 preserved contract:

- This phase adds outcome-calibrated procedural learning without widening runtime authority.
- The owned graph-adjacent module is `amadeus_thread0.graph_parts.procedural_outcome`.
- `procedural_outcome` is final-result readback and trace calibration, not an execution fact by itself:
  - derives outcomes from final/frozen action packets
  - uses packet `tool_args.procedural_planning` or carried trace refs to attribute attempts to prior procedural traces
  - adjusts only procedural trace confidence, reuse hints, boundary notes, and recovery hints
  - does not mutate persona core, relationship core, skills registry truth, sandbox/browser authority, or memory storage topology
- Allowed outcome kinds are:
  - `confirmed_success`
  - `partial_success`
  - `failed_execution`
  - `blocked_boundary_reinforced`
  - `manual_takeover_required`
  - `stale_or_mismatched_context`
  - `no_executed_attempt`
- Outcome semantics stay honest:
  - confirmed success may increase reuse confidence
  - failed execution reduces reuse confidence and carries recovery hints
  - blocked/manual outcomes reinforce boundary readback and cannot become capability facts
  - pending/rejected/expired/approved-only attempts remain `no_executed_attempt`
- Phase-2 planning ranks calibrated traces by updated confidence, but boundary-reinforced traces are downgraded to `boundary_only` and cannot produce execution packets.
- Backend and CLI readback expose:
  - top-level `procedural_outcome`
  - `turn_summary.current_turn.procedural_outcome`
  - compact `outcome=<outcome_kind>:<source_run_id>:reuse|boundary|hold`
- This phase does not add dynamic skill generation, package install, wider sandbox command families, automatic browser mutation, external executor harness runtime, frontend UI, persona-core edits, or a second memory store.
- Initial closure evidence:
  - `evals/reports/procedural-growth-phase3-smokes-20260506-095920-phase3-dev.{json,md}`
  - `overall_status=passed`

Procedural Growth Phase 4 preserved contract:

- This phase adds recovery-oriented procedural adaptation without widening runtime authority.
- The owned graph-adjacent module is `amadeus_thread0.graph_parts.procedural_recovery`.
- `procedural_recovery` is advisory recovery readback, not an execution fact:
  - derives recoveries from normalized `procedural_outcome` rows
  - marks affected procedural traces with `recovery_required`, `recovery_kind`, `recovery_allowed_bias_kind`, and recovery refs
  - keeps failed execution as failure-artifact inspection / workspace guidance before any future reuse
  - keeps blocked boundaries as `boundary_only`
  - keeps manual browser takeover as manual-takeover preservation
  - keeps stale context as workspace/artifact refresh guidance
  - keeps unexecuted attempts as hold-for-approval
- Allowed recovery kinds are:
  - `inspect_failure_artifact`
  - `adjust_bounded_command`
  - `preserve_manual_takeover`
  - `avoid_blocked_boundary`
  - `refresh_workspace_context`
  - `hold_for_approval`
  - `no_recovery_needed`
- Recovery semantics stay conservative:
  - unresolved recovery cannot produce direct `sandbox_execute` reuse
  - failed recovery may surface `workspace_guidance`
  - blocked recovery may surface `boundary_only`
  - manual recovery may surface `browser_manual_takeover`
  - hold recovery may surface approval/hold readback
  - no recovery item may add package install, shell wrappers, git mutation, network enablement, browser mutation, skill registry mutation, external executor harness runtime, persona-core edits, or a second memory store
- Backend and CLI readback expose:
  - top-level `procedural_recovery`
  - `turn_summary.current_turn.procedural_recovery`
  - compact `recovery=<recovery_kind>:<source_run_id>:approval|boundary|hold|hint`
- Initial closure evidence:
  - `evals/reports/procedural-growth-phase4-smokes-20260506-103539-phase4-dev.{json,md}`
  - `evals/reports/procedural-growth-phase4-audit-20260506-103615-phase4-dev.{json,md}`
  - `overall_status=passed`
  - `readiness_status=procedural_growth_phase4_ready`

Skills Ecosystem Formal Closure preserved contract:

- keep skills on the existing body/runtime contract:
  - global registry truth
  - session activation truth
  - backend `skills` envelope
  - no second top-level skill state container
- registry/install/lock truth remains outside autobiographical memory:
  - install status
  - resolved version
  - hash
  - source
  - verification metadata
  do not become self-narrative identity
- completed skill effects may re-enter lived continuity only through final semantics:
  - `digital_body_consequence.kind`
  - `interaction_carryover.embodied_context.skill_effects`
  - `reconsolidation_snapshot.skill_effects`
  - retrieval resurfacing from final writeback
- blocked / rejected / pending skill mutations do not become capability facts
- authored local skills now exist as real repo-owned packages, not only test fixtures:
  - `skills/source-ref-anchor-review/`
  - `skills/workspace-regression-triage/`
- closeout evidence for this phase is:
  - `evals/run_skills_ecosystem_smokes.py`
  - `evals/run_skills_ecosystem_audit.py`
  - post-fix authoritative ready reports:
    - `evals/reports/skills-ecosystem-audit-20260405-130543-closeout-fix-c.{json,md}`
    - `evals/reports/skills-ecosystem-audit-20260405-130706-closeout-fix-d.{json,md}`
    - `evals/reports/skills-ecosystem-audit-20260405-130706-closeout-fix-e.{json,md}`
  - the latest smoke artifact is:
    - `evals/reports/skills-ecosystem-smokes-20260405-130823-20260405-130706-closeout-fix-e-smokes.{json,md}`

Live Browser Runtime Closure Phase 1 preserved contract:

- keep the same single body contract:
  - `digital_body.access_state`
  - `digital_body.resource_state`
- live browser truth now stays inside that existing contract:
  - `digital_body.access_state.browser_runtime_state`
  - `digital_body.resource_state.browser_profile_id`
  - `digital_body.resource_state.browser_tab_id`
  - `artifact_carrier=browser_page`
- browser actions remain packet-owned and approval-gated through the same autonomy path:
  - `browser_execution_spec`
  - `browser_execution_preview`
  - `browser_execution_result`
  - `autonomy.pending_approval.browser_execution_preview`
- live browser does not replace saved-material continuity:
  - `search_web` remains the discovery path
  - `source_ref` remains the long-horizon saved-material carrier
  - live pages only become saved material through explicit capture
- login/session boundary remains truthful:
  - runtime may navigate to login flows and detect state
  - sensitive credential / OTP / passkey steps must become manual takeover on the same persistent profile
  - blocked / pending / takeover-requested actions do not become completed facts
  - the same blocked/pending truth may also derive a persona-facing `assist_request`:
    - `kind=grant_access` for missing access
    - `kind=manual_takeover` for sensitive browser entry
  - this is bounded translation, not a new truth model and not a prompt-only workaround
  - after operator resolution, runtime should prefer a short confirmation plus automatic continuation on the same task instead of re-asking whether to continue
- file transfer boundary remains truthful:
  - downloads only into runtime downloads or approved workspace roots
  - uploads only from approved workspace roots
  - no arbitrary host-path traversal
- closeout evidence for this phase is:
  - `evals/run_live_browser_runtime_smokes.py`
  - `evals/run_live_browser_runtime_audit.py`
  - targeted browser/runtime/backend/residue tests in:
    - `tests/test_browser_runner.py`
    - `tests/test_browser_runtime.py`
    - `tests/test_browser_backend_contract.py`
    - `tests/test_live_browser_runtime_smokes.py`
    - `tests/test_live_browser_runtime_audit.py`
    - browser-focused extensions in `tests/test_backend_session.py`, `tests/test_backend_api.py`, `tests/test_autonomy_writeback.py`, `tests/test_world_model_residue.py`, and `tests/test_tool_approval_policy.py`
  - fresh authoritative ready reports now include:
    - `evals/reports/live-browser-runtime-audit-20260405-224517-closeout-a.{json,md}`
    - `evals/reports/live-browser-runtime-audit-20260405-224803-closeout-b.{json,md}`
    - `evals/reports/live-browser-runtime-audit-20260405-225039-closeout-c.{json,md}`

## P0 Decisions

### 1. Session Fabric Is The Base Runtime

- Every interaction belongs to a long-lived `life thread`.
- The runtime should treat each turn as part of one continuous thread state, not as an isolated request/response call.
- Session continuity must survive CLI, TTS, future frontend surfaces, and future multimodal inputs.

### 2. Perception Event Is The Canonical Input Contract

- Raw user text is no longer the only conceptual input unit.
- All incoming signals should normalize into one `Perception Event` contract before appraisal:
  - source
  - channel
  - modality
  - trust tier
  - salience
  - interruptibility
  - delivery mode
  - session / turn identity
- Language is only one modality within the perception layer.

### 3. Persona Core Is Fixed; Self Model Evolves

- `persona_core` is stable and not rewritten by transient scenes.
- Evolution is allowed in:
  - emotion state
  - relationship state
  - counterpart assessment
  - self narrative
  - motive / goal state
  - own rhythm

### 4. Final Semantics Freeze Before Writeback

- Long-term updates must originate from the finalized turn semantics.
- Drafts, intermediate rewrites, and temporary tool reasoning must not directly write long-term identity or relationship state.

### 5. Counterpart Model Is A First-Class Runtime State

- `Amadeus` must maintain an explicit model of how she currently reads the counterpart.
- This is not a CRM profile. It is a relationship judgment surface.
- Minimum tracked axes:
  - trust
  - respect
  - safety
  - repairability
  - dependency risk
  - closeness
  - predictability

### 6. Own Rhythm Is A Core Engine, Not A Cosmetic Feature

- The system must support self-paced continuity:
  - wanting to continue
  - wanting to hold distance
  - wanting to revisit a thread
  - choosing silence
  - reopening from its own rhythm
- This is not cron-style productivity automation.
- It is the runtime expression of continued existence.

## P1 Decisions

### 7. Capability Bus Exists Outside The Persona Core

- Perception, knowledge, and action capabilities may expand over time.
- Capabilities can provide sensed facts, executable actions, and external feedback.
- Capabilities must not become the source of persona identity.

### 7a. Persona-First Autonomy

- Autonomy is built inside the companion loop, not as a separate generic task agent.
- `autonomy_intent` must arise from frozen appraisal / motive / relationship / own-rhythm state.
- Persona-core judgment remains upstream of tool execution and worker execution.

### 7b. Action Packet Contract

- Structured autonomy flows through one bounded packet contract.
- Required minimum fields:
  - `proposal_id`
  - `origin`
  - `intent`
  - `status`
  - `risk`
  - `requires_approval`
  - `capability_steps`
  - `expected_effect`
  - `result_summary`
  - `writeback_ready`

### 7c. Approval-Gated Mutation

- `read` packets may auto-execute.
- `memory_write` packets reuse the existing memory approval policy.
- `external_mutation` packets always require human approval.
- Rejected or blocked packets never masquerade as completed facts.
- when a packet is blocked by missing access or manual browser takeover, runtime may derive a bounded persona-facing `assist_request` from the same packet/body truth:
  - it may explain the concrete blockage
  - it may ask the operator to resolve it
  - it may promise automatic continuation after resolution
  - it does not widen execution authority or replace the structured truth surfaces
- The first concrete direct-execution slice is `artifact reacquisition`:
  - when a prior file/work-surface is detached or missing
  - and the packet is low-risk `read`
  - the graph may execute reacquisition before the next model turn instead of only describing the need semantically
  - this read-execution family may now also carry backend-owned runtime binding fields on the packet itself:
    - `tool_name=reacquire_artifact`
    - `tool_args={mode, artifact_kind, artifact_ref, artifact_label}`
  - those fields exist so execution can stay packet-owned even if live carryover has already moved on
  - for saved browser/search-like material, one bounded carrier remains `saved source_refs`:
    - previously retrieved pages/search results may be reattached from stored `url/title/query/snippet`
    - the separate live browser/runtime surface now owns real-time page continuity; saved-material reacquisition remains the long-horizon re-entry path
- The next bounded direct-execution slice is `access state refresh`:
  - when session/access conditions are present but the runtime can still do a truthful read-only recheck
  - the graph may execute a bounded `access:refresh_state` packet before the next model turn
  - this read-execution family may now also carry backend-owned runtime binding fields on the packet itself:
    - `tool_name=refresh_access_state`
    - `tool_args={access_hints}`
  - that binding is part of backend execution integrity, not a frontend autonomy contract surface
  - this slice only refreshes inspectable runtime truth such as:
    - API key presence
    - filesystem writability
    - session lifecycle recomputation from the current hints
    - requestable/missing access normalization
  - it does not pretend to complete external login/browser/cookie mutation that the runtime cannot actually perform
- The first truthful non-executing access-help slice is `access request help`:
  - when current-turn body hints show missing external conditions such as:
    - browser session entry
    - account login
    - cookies
    - API key / quota conditions that need operator intervention
  - the graph may emit a bounded `access:request_help` packet before the next model turn
  - this packet stays `awaiting_approval` with `external_mutation` risk:
    - it is a request/proposal surface
    - it is not a fake completed login, cookie restore, or account mutation
  - the packet must write through the same live/runtime/frozen surfaces as other action packets:
    - `pending_action_proposal`
    - `digital_body_state`
    - `reconsolidation_snapshot`
    - backend autonomy envelope
  - when multiple acquisition paths are available, the runtime must keep one stable current selection:
    - `selected_access_proposal` is the current active path
    - default selection should be deterministic and prefer the already-listed primary path rather than oscillating across turns
    - operator override may replace that selection, and the chosen path should persist through later approved/partial/resolved states until truthfully cleared
  - the current resolved semantics are intentionally split:
    - `awaiting_approval` = requesting operator help / approval for the missing access path
    - `approved` = operator accepted an acquisition path, but the real external access is still not fixed
    - `completed` = concrete access updates actually arrived in runtime state
    - for multi-grant acquisition plans, `approved` may also carry truthful partial progress:
      - some grants may already be satisfied
      - others may still be pending
      - this must not be flattened into fake `completed`
  - later-turn arrival must also close truthfully:
    - if a previously accepted `selected_access_proposal` is now actually satisfied by runtime-visible world state
    - the backend may synthesize one bounded `completed` resolution packet/writeback for that same proposal
    - then clear the stale planned state from live hints instead of letting `approved` hang forever
  - accepted-but-not-yet-fixed access paths must stay explicit through:
    - `action_packets[*].selected_access_proposal`
    - `digital_body.access_state.selected_access_proposal`
    - `autonomy_intent.mode=access_acquire_planned`
    - `digital_body_consequence` / carried `embodied_context` when that accepted path is the frozen state of the turn
    - when partial progress exists, those proposal surfaces may also expose:
      - `resolved_grants`
      - `pending_grants`
      - `completion_ratio`

### 7d. Bounded Capability Expansion

- Persona-core may request capability expansion through explicit upgrade proposals.
- Future worker execution, if added, stays outside persona-core judgment.

### 7e. Digital Body Core

- `Amadeus-K` should not converge toward a fixed tool menu.
- It should converge toward a `digital body` composed of bounded perception/action surfaces such as:
  - browser/runtime sessions
  - workspace filesystem
  - sandboxed execution
  - search/retrieval surfaces
  - access/session/cookie/account state
- These surfaces are not identity; they are the digital-world body through which identity acts.

### 7f. Affordance / Resource / Access Model

- The runtime should reason not only about "which tool exists" but also about:
  - what is reachable right now
  - what resources are missing
  - what accounts/cookies/permissions are absent
  - what conditions are only temporarily unavailable and should be retried later
  - whether a reusable session is still stable, already expiring, or broken and what recovery path would restore continuity
  - what can be requested, created, earned, or deferred
- Missing access is not always a terminal failure:
  - she may ask the operator for credentials or approval
  - she may create bounded new access such as a fresh account where appropriate
  - she may choose an alternate path when direct access is unavailable
  - when she asks, that request should sound like her, but it must stay grounded in the real runtime condition rather than hallucinated capability
  - when the operator resolves the condition, she should briefly confirm that the entrance is open and continue automatically when safe
  - she must not "solve" access by self-crack behavior such as:
    - credential guessing
    - OTP simulation
    - CAPTCHA bypass
    - cookie forgery
- the current bounded implementation path is still proposal-first:
  - `access:request_help` may now surface both:
    - `path_kind=acquire_existing`
    - `path_kind=create_new`
  - `create_new` means a truthful candidate path such as:
    - register a fresh account
    - create a fresh writable workspace
    - create a new API key / service entry
  - it does not mean the runtime has already executed that creation
  - first bounded execution exception now exists for the local filesystem surface only:
    - if the approved selected proposal is `operator_create_workspace`
    - and the runtime can truthfully create that workspace inside its own `AMADEUS_DATA_DIR/workspaces/` boundary
    - it may execute `create_workspace_access`
    - the approved packet may now also carry backend-owned execution binding for that step:
      - `tool_name=create_workspace_access`
      - `tool_args={workspace_name, access_hints}`
    - execution should prefer that frozen packet binding over re-deriving arguments from live session state
    - then resolve the same access path from `approved` to `completed`
    - and clear stale `selected_access_proposal` residue once filesystem / workspace-write grants are actually satisfied
    - the frozen readback consequence should then be explicit at the embodied layer:
      - prefer `digital_body_consequence.kind=workspace_access_resolved`
      - rather than flattening the turn back into a generic `access_request_resolved`
  - next bounded local mutation surface may build on that same workspace boundary:
    - `write_workspace_file`
    - it may only write relative paths under the currently resolved runtime workspace
    - it must reject absolute paths and `..` escapes
    - it updates the active artifact from `workspace` to the concrete written `file`
    - frozen embodied readback should preserve this as a concrete file-surface update rather than collapsing it into generic growth:
      - prefer `digital_body_consequence.kind=workspace_file_updated`
      - carry `artifact_mutation_mode=write`
    - follow-on bounded mutation may continue inside the same contract:
      - `append_workspace_file`
      - it may only append to a relative path under the currently resolved runtime workspace
      - it keeps the same bounded host-write surface and concrete `file` artifact continuity
      - the same frozen readback kind should remain concrete:
        - `digital_body_consequence.kind=workspace_file_updated`
        - `artifact_mutation_mode=append`
      - `replace_workspace_text`
      - it may only edit an existing relative file path under the currently resolved runtime workspace
      - it performs explicit exact-text replacement rather than arbitrary host editing
      - `replace_workspace_lines`
      - it may only replace a bounded inclusive line span inside an existing relative file path under the currently resolved runtime workspace
      - it provides a stronger structured edit surface than raw text replacement while still staying inside the same workspace/file boundary
      - the same frozen readback family should remain concrete:
        - `digital_body_consequence.kind=workspace_file_updated`
        - `artifact_mutation_mode=replace`
      - approved executable mutation packets may carry backend-owned execution binding fields:
        - `tool_name`
        - `tool_args`
      - human approval for bounded workspace mutation should prefer a truthful preview-first contract:
        - approval preview may carry a bounded diff / patch preview against the current runtime file surface
        - approval still gates the external mutation itself, not the preview
        - apply must continue using the same packet-owned runtime binding after approval rather than regenerating a new edit plan
        - once generated, that preview should persist through the formal packet/backend envelope too:
          - `action_packets[*].mutation_preview`
          - `pending_action_proposal.mutation_preview`
          - backend autonomy envelope should expose the same preview rather than keeping it trapped inside approval-only tool-call payloads
      - these fields exist only so runtime can bind one approved packet to one truthful local tool invocation
      - they must not replace the packet's semantic `intent` / `origin`, and they are not the frontend-facing autonomy contract
      - when the active artifact is already a concrete file inside a workspace, workspace resolution must still recover the containing runtime workspace root rather than naively treating the file's parent directory as a new workspace boundary
  - the same workspace boundary now also exposes a bounded read-only perception surface:
    - `inspect_workspace_path`
    - it may inspect the root workspace, a subdirectory, or a concrete file under the current runtime workspace
    - it updates active artifact continuity truthfully without widening beyond that workspace boundary
    - when that inspection completes against an attached workspace/file surface, frozen writeback may carry:
      - `digital_body_consequence.kind=workspace_path_inspected`
      - `procedural_growth=false`
    - if the active artifact becomes a subdirectory path, later workspace-relative mutation must still resolve against the containing runtime workspace root rather than silently collapsing the write boundary to the subdirectory itself
  - the existing `saved source_refs` carrier should now also expose a bounded read-only inspection surface rather than relying on reacquisition semantics for every external-material turn:
    - `inspect_source_ref`
    - it may inspect one previously saved source by id / ref / label
    - it does not pretend to reopen a live browser; it only re-enters already stored external material
    - when an attached `source_ref` surface is still present but marked `stale`, autonomy may derive a read-only `inspect_source_ref` packet directly instead of flattening that state back into generic artifact reacquisition
    - when runtime continuity still carries two related saved source refs on the same material line, backend may also expose a bounded read-only comparison surface:
      - `compare_source_refs`
      - it compares two already saved materials; it does not open a live browser or fetch a third unseen source
      - when an attached `source_ref` surface is stale and continuity still holds two related saved refs, autonomy may derive `artifact:compare_source_refs` before falling back to plain re-inspection
      - when continuity carries a bounded ordered candidate set rather than only a pair, `compare_source_refs` may choose the comparison partner from that saved candidate set instead of blindly fixing the second id up front
    - when that inspection completes against an attached external-material surface, frozen writeback may carry:
      - `digital_body_consequence.kind=source_material_inspected`
      - `procedural_growth=false`
    - when that bounded comparison completes against an attached external-material surface, frozen writeback may carry:
      - `digital_body_consequence.kind=source_material_compared`
      - `procedural_growth=false`
    - bounded saved-material comparison is no longer allowed to stop at “a comparison happened”:
      - compare completion should re-anchor the live artifact surface to the preferred saved material when one side is clearly the better continuity anchor
      - that preferred anchor must remain bounded to real saved `source_ref` ids rather than free text or invented URLs
      - preferred-anchor semantics should stay explicit across runtime layers:
        - preserve `preferred_source_ref_id`
        - preserve `preferred_anchor_reason`
      - `artifact_source_ref_ids` may now carry a bounded ordered continuity set rather than only one compared pair, but the ordering must stay meaningful:
        - preferred anchor first
        - directly compared partner next
        - remaining saved candidates only as bounded follow-up continuity
      - when a stale `source_ref` line already carries a stable preferred anchor from a prior compare, autonomy should inspect that preferred saved material directly instead of redundantly comparing the same pair again
      - later turns may retrieve `source_material_compared` traces and reapply them as runtime continuity bias so the re-anchored material line can affect later `task_pull / memory_gravity / behavior` selection instead of dying inside the frozen snapshot
      - retrieved compare continuity may also refresh the saved-material lineup already held in `session_context.digital_body_hints`, but only when a visible `source_ref` context is already present in runtime state:
        - allowed visible carriers: current session hints, event `digital_body_hints`, or perception `digital_body_hints`
        - this refresh may widen `artifact_source_ref_ids`, preserve `preferred_source_ref_id`, preserve `preferred_anchor_reason`, and backfill missing saved-material metadata
        - it must not seed a brand-new `source_ref` line from retrieval alone when the live turn has no visible saved-material context
      - preferred-anchor semantics are not allowed to disappear at summary/export boundaries once present in runtime state:
        - `digital_body_state.resource_state`
        - `digital_body_consequence`
        - backend turn/event envelopes
        - CLI/evolution summary views that surface saved-material continuity
  - completed read-side reacquisition and access refresh should also survive as concrete digital-body facts instead of flattening back into generic state:
    - `tool_name=reacquire_artifact` -> `digital_body_consequence.kind=artifact_reacquired`
    - `tool_name=refresh_access_state` -> `digital_body_consequence.kind=access_state_refreshed`
    - both are verification/reattachment facts, not procedural growth
  - `artifact_context` returned by a completed tool is not allowed to remain packet-only:
    - it must be able to refresh live `digital_body_hints`
    - otherwise runtime state, frozen consequence, backend envelope, and CLI summary drift apart on what artifact is actually in view
  - with `artifact reacquisition`, `access refresh`, `workspace creation`, and workspace file mutation now all aligned, the current direct-execution families share one contract:
    - packet owns the runtime binding
    - execution prefers packet binding
    - live-state synthesis is compatibility fallback only
- This is the digital analogue of real-world constraints rather than a static tool-gating table.
- `resource_state` must now also track attached work surfaces as first-class runtime facts:
  - `artifact_continuity`
  - `active_artifact_kind`
  - `active_artifact_ref`
  - `workspace_root` when the active surface is inside a runtime workspace
  - `active_artifact_label`
  - `artifact_age_s`
  - `artifact_reacquisition_mode`
- `workspace_root` is the explicit filesystem trust boundary:
  - it must survive live hints, derived `digital_body_state.resource_state`, and summarized backend/CLI views
  - it must not be inferred only from a narrower current artifact such as a subdirectory or file path
  - later workspace-relative writes and edits still resolve against that root even when the current attached artifact is deeper inside it
- Losing a page/file/work-surface attachment is not the same as a persona change; it is embodied world friction that must survive into writeback, summaries, and later reacquisition behavior.

### 7g. Unified Experience Memory

- Do not split the system into a "persona memory" and a separate "work memory" brain.
- Keep one memory substrate with multiple experience trace families, for example:
  - relationship traces
  - selfhood traces
  - world/task/artifact traces
  - procedural traces
  - access/resource traces
- Different retrieval views may exist, but they must write back into one lived continuity model.

### 7h. Unified Evolution Engine

- Do not create a separate top-level `capability evolution` system in parallel with personality evolution.
- The same evolution engine should absorb:
  - emotional change
  - relationship change
  - self-narrative change
  - work-style change
  - procedural competence change
  - digital-body usage strategy change
- The system should therefore grow as one person interacting with one world, not as a role shell plus an independent task optimizer.

### 7i. Capability Formation Through Embodied Interaction

- The long-term target is not a frozen toolbox.
- The long-term target is that she can:
  - explore how to use a granted environment
  - ask for missing context or access
  - learn usage patterns from trial, feedback, and explanation
  - eventually form bounded new workflows or helper capabilities inside approved/sandboxed environments
- Host-side arbitrary code generation remains unsafe and out of scope until explicit sandbox and approval contracts exist.

### 7j. Managed Skills Ecosystem Lives Outside Persona Core

- `SKILL.md` packages are a capability-management layer, not a persona-authority layer.
- The runtime should support:
  - authored local skills from `skills/`
  - controlled remote registry discovery
  - install/update/enable/disable/pin/unpin lifecycle operations
  - global registry truth plus session activation truth
  - progressive disclosure so only active skills expose instruction excerpts
- Skills belong to the digital-body / capability ecology:
  - install state, version, hash, and registry metadata do not enter autobiographical memory
  - their usage consequences may later write back as procedural competence or artifact continuity
- Approval policy remains strict:
  - `search/inspect/list` are read surfaces
  - `install/update/enable/disable/pin/unpin` are approval-gated mutations
  - approved skill mutations must execute the same resolved payload, not a regenerated plan
- Managed skills do not override persona-core, relationship-core, or self-narrative core.

### 8. Presence Layer Becomes Formal Runtime Infrastructure

- Typing, silence, interruption recovery, delayed continuation, and proactive re-entry belong to a dedicated presence layer.
- Presence should be treated as behavior orchestration, not UI sugar.

### 9. Relational Boundary Guard Is Separate From Generic Safety

- We need relational safety, not just policy safety.
- The guard layer should reason about:
  - disrespect
  - coercion
  - attachment imbalance
  - repair sincerity
  - emotional vulnerability

### 10. Traceability Must Cover The Full Persona Loop

- Each turn should remain inspectable across:
  - perception
  - appraisal
  - internal state delta
  - motive / goal shift
  - behavior packet
  - reconsolidation
  - self narrative delta

## P2 Decisions

### 11. Cross-Surface Continuity Is Unlocked

- Future frontend, voice, and multimodal surfaces should share one life-thread runtime.
- Complete closeout unlock opens the next bounded surface phases.
- Each surface must consume the existing backend/body/memory truth instead of creating a parallel schema or interaction brain.

### 12. Subagents Stay Peripheral

- Subagents / workers may support retrieval, synthesis, or bounded packet execution.
- Subagents must not own persona-core decisions or identity judgment.

### 13. Dynamic Skill Generation Is Unlocked As A Bounded Phase

- Host-side arbitrary skill/tool generation remains blocked.
- Bounded dynamic skill generation is unlocked for registry-backed proposals only.
- This does not block a managed skills ecosystem:
  - authored `SKILL.md` packages
  - controlled remote install/update
  - approval-gated activation
- In the near term, only explicit capability-upgrade proposals are allowed.
- Long-term digital-embodiment convergence may include bounded helper creation or workflow synthesis, but only inside sandboxed / approval-gated execution surfaces.

### 14. Chinese Semantic De-Scaffolding Is Unlocked

- Replacing brittle Chinese lexical heuristics is now unlocked as a separate semantic-replacement phase.
- The phase should replace lexical scaffolding with typed diagnostics and semantic classifiers before broad behavior rewrites.
- Output naturalness / tone micro-polish is not a structural success metric by itself unless it is inside that phase or blocks runtime correctness.
- Current quality bar is:
  - runtime is runnable
  - state contracts are correct
  - writeback provenance is correct
  - digital-body / autonomy / reconsolidation architecture keeps closing
- Candidate mechanisms are:
  - structured state extractors
  - small semantic classifiers
  - CrossEncoder semantic scorers / rerankers
  - preference optimization / DPO-style tuning
  - PEFT / LoRA / QLoRA-style role tuning
- The exact choice remains intentionally undecided until a phase spec selects the smallest auditable mechanism.
- Outside that phase, only the most brittle Chinese-heavy zones should be audited and documented, not proactively rewritten without a replacement contract.

## Explicit Rejections

### 1. Reject Task-First Product Identity

- `Amadeus-K` is not being optimized into a generic productivity agent.

### 2. Reject Tool-Driven Persona Drift

- Skills, tools, or plugins must not redefine the persona core.

### 3. Reject Prompt-Heavy Behavioral Repair As The Main Strategy

- If behavior quality is wrong, inspect state evolution, appraisal, writeback, and presence routing first.

### 4. Reject Keyword Scripts For Persona Behavior

- Keyword rules are allowed only for safety, auditability, or narrow routing.
- They are not the main persona engine.

### 5. Reject “Memory = Retrieval Store” Reduction

- Long-term memory must also preserve:
  - selfhood
  - counterpart judgment
  - relationship change
  - unresolved tension
  - repair history
  - own rhythm traces

### 6. Reject “Fixed Tool Suite = Capability” Reduction

- A static menu of tools is not the same thing as a living digital body.
- Capability should be modeled as embodied access, experimentation, verification, and reconsolidated experience.

## Current Implementation Order

1. `Session Fabric + Perception Event` - `backend-closed`
2. `Counterpart Model + Relationship Appraisal` - `backend-closed`
3. `Own Rhythm Engine` - `backend-closed`
4. `Capability Bus` - `backend-closed as baseline`
5. `Presence Layer` - `backend-closed as baseline`
6. `Companion Autonomy Closure` - `baseline-closed`
7. `Digital Body / Unified Experience / Embodied Capability` - `baseline-closed through digital embodiment phase 2`
8. `Sandbox Embodied Execution Phase 1` - `baseline-closed`
9. `Skills Ecosystem Formal Closure` - `baseline-closed`
10. `Live Browser Runtime Closure Phase 1` - `baseline-closed`
11. `Sandbox Embodied Execution Phase 2` - `baseline-closed`
12. `Post-Baseline Closure Pack` - `baseline-closed`
13. `Procedural Growth Phases 1-4` - `baseline-closed through recovery-oriented adaptation`
14. `Complete Closeout Unlock` - `active control-plane status`
15. `Multimodal Capture Phase 1` - `phase1-ready`
16. `Dynamic Skills Phase 1` - `phase1-ready`
17. `External Executor Harness Phase 1` - `phase1-ready`
18. `Frontend Runtime Shell` - `phase2-ready`
19. `Chinese semantic de-scaffolding` - `baseline-closed through phase 2 typed runtime policy`
20. `Capability Growth Phase 5` - `phase5-ready`
21. `Natural Long-Horizon Calibration` - `phase1-ready`
22. `Post-Unlock Roadmap Integration Gate` - `ready`
23. `Runtime Productization Phases 1-2` - `baseline-closed`
24. `Runtime Productization Phase 3` - `baseline-closed`
25. `HTTP Transport Thin Wrapper Phase 1` - `baseline-closed`
26. `Residual Living Loop Closure Phase 1` - `baseline-closed`
27. `Living Loop Runtime Realism Phase 1` - `baseline-closed`
28. `Living Loop Runtime Realism Phase 2` - `baseline-closed`
29. `Living Loop Runtime Realism Phase 3` - `baseline-closed`
30. `Embodied Interaction Runtime Phase 1` - `baseline-closed`
31. `Embodied Interaction Runtime Phase 2` - `baseline-closed`
32. `Embodied Interaction Runtime Phase 3` - `baseline-closed`
33. `Embodied Interaction Runtime Phase 4` - `baseline-closed`
34. `Embodied Interaction Runtime Phase 5` - `baseline-closed`
35. `Approved Artifact Multimodal Runtime Phase 1` - `baseline-closed`
36. `Technical Preview RC Phase 1` - `baseline-closed`
37. `Operator Console RC Phase 1` - `baseline-closed`
38. `Advisor Demo Readiness Phase 1` - `baseline-closed`
