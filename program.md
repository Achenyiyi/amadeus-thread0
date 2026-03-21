# program.md

This file is the live development ledger for `amadeus-thread0`.

## Usage Contract

- Read this file at the start of every run, immediately after `AGENTS.md`.
- Update this file at the end of every run.
- Keep it operational, not narrative: current focus, concrete changes, validation, next step.
- Do not delete older entries unless they are condensed into the current-state summary.

## Current State

- Date: `2026-03-21`
- Product boundary: `backend-first`, `CLI + TTS + evals`, no frontend expansion yet
- Mainline phase: `backend maturation`
- Active backend focus:
  - `appraisal -> internal state -> motive/goal -> behavior`
  - `reconsolidation -> self-narrative -> counterpart assessment persistence`
  - `own-rhythm / proactive continuity traces`
- Latest completed technical milestone:
  - graph/runtime/eval now share an explicit `final_text` contract instead of inferring final replies from `messages[-1]`, closing the stale-message leak that could make smoke reports and CLI output diverge from finalized response semantics
  - repair-scene surface gating now also applies to `selfhood_reflection` turns, so postprocess can still catch `wording_meta_detour` / `boundary_abstraction_surface` / technicalized repair phrasing even when the behavior layer routes the turn through a more reflective interaction mode
  - focused real-model recheck on `guarded_everyday_user` now returns a single finalized repair reply without the previous `既然你都这么说了` / `完美宽容` / `输出-评测错位` style artifacts that were leaking through the old path
  - postprocess `idle_task_reframe` is now fully wired into final-answer sanitization instead of stopping at detection, and it now covers both direct task detours (`报告 / 数据 / 问卷调查`) and casual-chat science drift (`学术答辩 / 后台跑数据 / 时间跳跃`)
  - guarded repair cleanup now also normalizes `安全距离 / 缓一缓了一下 / 你所谓的“回来”` class residue into grounded relational wording
  - the latest combined real-model freeze-gate artifact is green again: `evals/reports/freeze-gate-smokes-20260321-200258-7d562271.{json,md}`
  - final-turn writeback now uses a frozen reconsolidation snapshot instead of relying on later-mutating runtime state
  - frozen motive / goal / counterpart snapshot is passed into behavior-trace writeback and semantic-self evidence writeback
  - post-writeback runtime refresh now re-reads persisted semantic narratives and relationship surfaces
  - counterpart assessment is now persisted as a first-class long-term history surface instead of only leaking through scattered trace metadata
  - `/bond` now exposes recent counterpart judgment history with compact readable summaries and the associated motive / scene context
  - agenda lifecycle long-term writeback now prefers frozen reconsolidation snapshots and persists first-class proactive continuity history for own-rhythm / continuity windows
  - `/worldline` and `/bond` now expose recent proactive continuity history so own-rhythm traces are inspectable from backend and CLI surfaces
  - persisted `proactive_continuity_history` now feeds `_recent_interaction_carryover()` through `prepare_turn_context`, so own-rhythm / continuity traces are no longer CLI-only logs and can re-enter runtime behavior seeding
  - repository now has a live per-run ledger wired into `AGENTS.md`
  - backend handoff contract assets now match the current runtime payload surface: `assistant_turn` / `event_round` carry `interaction_carryover`, `worldline_view` carries counterpart/proactive continuity history + preview, and a first-class `bond_view` mock now exists for frontend consumption
  - frozen reconsolidation snapshots now also carry final `behavior_action`, and runtime/API/session views prefer that frozen action over stale live residue
  - frozen reconsolidation `interaction_carryover` now drives runtime/API/session summaries too, so final action semantics and final carryover residue stay aligned
  - counterpart judgment now carries a structured `assessment_profile` through runtime, reconsolidation, long-horizon history, CLI/session summaries, and semantic self-narrative refresh instead of collapsing to stance-only or one-line summary surfaces
  - runtime `relationship_state` derivation now consumes structured counterpart judgment (`respect / reciprocity / reliability / openness / guardedness`), so bond-state summaries are no longer driven mostly by boundary pressure alone
  - persisted `relationship_state` derivation in `memory_store` now also absorbs structured `counterpart_assessment_history`, so refreshed `/bond` relationship surfaces no longer fall back to mostly timeline-only relation summaries
  - backend freeze-gate smoke runner is now in place and structurally catches duplicate output, final-text mismatch, prompt/middle-state leakage, generic assistant tone, and obvious daily-surface drift
  - the three required natural-dialogue smoke packs now pass on the real model path in a single combined report: `evals/reports/freeze-gate-smokes-20260321-150221-c2af8a53.{json,md}`
- Current risks / open questions:
  - continue auditing any remaining persistence paths that still derive long-term memory from non-frozen runtime inputs
  - keep expanding own-rhythm / proactive continuity behavior without falling back to prompt-heavy repair
  - latest freeze-gate smoke is green again, but transcript review still shows some passed cases are rhetorically dense and may still want manual polish before declaring the backend fully freeze-closed
- Immediate next step:
  - use the fresh `freeze-gate-smokes-20260321-200258-7d562271` artifact for manual transcript signoff, then decide whether the next turn should target final surface-density polish in a few passed cases or return to the next backend mainline lane beyond freeze-gate cleanup

## Validation Baseline

- Latest targeted regression status:
  - `tests/test_daily_surface_gating.py`: pass
  - AGENTS graph subset rerun after latest postprocess cleanup: pass
  - `evals/run_freeze_gate_smokes.py --case-timeout-s 180`: pass
  - `tests/test_backend_session.py tests/test_response_finalize.py tests/test_daily_surface_gating.py tests/test_eval_runner_controls.py`: pass
  - `tests/test_freeze_gate_smokes.py tests/test_subjective_review_pack.py`: pass
  - `tests/test_world_model_residue.py -k "get_relationship or counterpart_history"`: pass
  - `tests/test_world_model_residue.py -k "persisted_proactive_history or long_horizon_own_rhythm_without_recent_non_user_event or agenda_lifecycle_residue"`: pass
  - `tests/test_prepare_turn_context.py -k "proactive_continuity_history or semantic_narrative_profile"`: pass
  - `tests/test_backend_session.py`: pass
  - `tests/test_memory_guard.py tests/test_session_orchestrator.py tests/test_cli_views.py`: pass
  - `tests/test_daily_surface_gating.py tests/test_generation_profile.py tests/test_dialogue_mode_counterpart.py tests/test_world_model_residue.py tests/test_subjective_review_pack.py`: pass
  - `tests/test_memory_evolution_semantic_writeback.py tests/test_world_model_residue.py`: pass
  - `tests/test_cli_views.py tests/test_backend_session.py tests/test_memory_evolution_semantic_writeback.py`: pass
  - `tests/test_final_state.py tests/test_backend_api.py tests/test_backend_session.py tests/test_prepare_turn_runtime.py`: pass
  - `tests/test_final_state.py tests/test_backend_api.py tests/test_backend_session.py tests/test_prepare_turn_runtime.py`: pass
  - `tests/test_memory_evolution_semantic_writeback.py tests/test_backend_session.py tests/test_cli_views.py`: pass
  - `tests/test_memory_evolution_semantic_writeback.py tests/test_backend_session.py tests/test_cli_views.py`: pass
  - `tests/test_memory_evolution_semantic_writeback.py`: pass
  - `tests/test_prepare_turn_runtime.py`: pass
  - AGENTS targeted suite subset: pass
  - frontend contract mock JSON audit: pass
- Latest recorded result:
  - `freeze-gate-smokes overall_status=passed` (`7d562271`)
  - `443 passed, 24 subtests passed`
  - `238 passed, 24 subtests passed`
  - `20 passed`
  - `freeze-gate-smokes overall_status=passed`
  - `4 passed, 112 deselected`
  - `15 passed`
  - `24 passed, 9 subtests passed`
  - `407 passed, 24 subtests passed`
  - `132 passed, 4 subtests passed`
  - `43 passed, 4 subtests passed`
  - `427 passed, 33 subtests passed`
  - `45 passed, 1 warning`
  - `44 passed, 1 warning`
  - `423 passed`
  - `38 passed, 4 subtests passed`
  - `36 passed`
  - `474 passed`
  - `424 passed, 33 subtests passed`
  - `32 passed`
  - `5 passed, 57 deselected`
  - `405 passed, 24 subtests passed`
  - `25 passed`
  - `8 passed, 109 deselected`
  - `1 passed, 9 deselected`
  - `408 passed, 24 subtests passed`
  - `mock-json-ok`

## Run Log

### 2026-03-21 - Run 01

- Scope:
  - finish the interrupted `postprocess` cleanup from the previous turn
  - remove remaining demo-breaking drift in everyday smalltalk and guarded-repair transcript surfaces
- Files changed:
  - `amadeus_thread0/graph_parts/postprocess.py`
  - `tests/test_daily_surface_gating.py`
- Key changes:
  - fully wired `idle_task_reframe` into `_sanitize_final_answer()` instead of leaving it as detection-only
  - expanded `idle_task_reframe` coverage from simple `既然没事` residue to broader casual-chat detours such as `报告 / 数据 / 问卷调查 / 学术答辩 / 后台跑数据 / 时间跳跃`
  - added corresponding surface rewrites so light smalltalk no longer falls back into task nudges or research-topic drift
  - expanded `boundary_abstraction_surface` detection and cleanup so guarded residue no longer leaks phrases like `安全距离`, `缓一缓了一下`, or stagey quoted `回来`
  - added focused regressions for the new idle-task and guarded-boundary cases
- Validation:
  - `python -m py_compile amadeus_thread0/graph_parts/postprocess.py tests/test_daily_surface_gating.py`
  - `python -m pytest tests/test_daily_surface_gating.py -q`
  - `python -m pytest tests/test_daily_surface_gating.py tests/test_generation_profile.py tests/test_dialogue_mode_counterpart.py tests/test_world_model_residue.py tests/test_subjective_review_pack.py -q`
  - `python evals/run_freeze_gate_smokes.py --case-timeout-s 180`
- Result:
  - the previous smoke failure around `idle_chat_okabe` is closed
  - combined real-model freeze-gate report is green again: `evals/reports/freeze-gate-smokes-20260321-200258-7d562271.{json,md}`
  - key previously awkward cases now land on more grounded text, including `idle_chat_okabe` and `guarded_everyday_user`
- Next:
  - manually review the fresh green smoke transcript for any remaining over-dense but technically passing phrasing, then either do one more surface-polish pass or move back to the next backend mainline lane

### 2026-03-20 - Run 01

- Scope:
  - tighten `reconsolidation -> memory trace writeback`
  - eliminate live-state leakage in final-turn persistence
- Files changed:
  - `amadeus_thread0/graph_parts/prepare_turn_runtime.py`
  - `amadeus_thread0/graph_parts/memory_evolution.py`
  - `tests/test_prepare_turn_runtime.py`
  - `tests/test_memory_evolution_semantic_writeback.py`
- Key changes:
  - added provisional `writeback_reconsolidation_snapshot` before final writeback
  - passed frozen snapshot into behavior-trace and semantic-self writeback helpers
  - writeback now prefers frozen motive / goal / counterpart metadata
  - fixed integration regression to use real `MemoryStore` and deterministic behavior-action patching
  - closed Windows temp sqlite handle correctly in regression test
- Validation:
  - `python -m pytest tests/test_memory_evolution_semantic_writeback.py tests/test_prepare_turn_runtime.py -q`
  - `python -m pytest tests/test_cli_views.py tests/test_backend_session.py tests/test_backend_api.py tests/test_prepare_turn_runtime.py tests/test_memory_evolution_semantic_writeback.py tests/test_daily_surface_gating.py tests/test_generation_profile.py tests/test_dialogue_mode_counterpart.py tests/test_world_model_residue.py tests/test_subjective_review_pack.py tests/test_memory_guard.py tests/test_session_orchestrator.py -q`
  - `python -m py_compile amadeus_thread0/graph_parts/memory_evolution.py amadeus_thread0/graph_parts/prepare_turn_runtime.py tests/test_memory_evolution_semantic_writeback.py tests/test_prepare_turn_runtime.py`
- Result:
  - frozen final-turn writeback path is green
  - targeted AGENTS regression subset is green
- Next:
  - keep auditing persistence edges and continue toward stronger self-narrative and proactive continuity behavior

### 2026-03-20 - Run 02

- Scope:
  - install a persistent per-run progress ledger
  - wire the ledger into repository operating instructions
- Files changed:
  - `program.md`
  - `AGENTS.md`
- Key changes:
  - created root-level `program.md` as the live run ledger
  - defined read/update contract for every run
  - updated `AGENTS.md` documentation map and maintenance workflow so future runs must read `program.md` before work and update it before ending
- Validation:
  - reviewed rendered contents of `program.md`
  - reviewed `git diff -- AGENTS.md program.md`
- Result:
  - run-ledger mechanism is now part of repository execution contract
- Next:
  - continue backend mainline from `self-narrative / counterpart assessment persistence / own-rhythm proactive continuity`

### 2026-03-20 - Run 03

- Scope:
  - formalize `counterpart assessment` persistence
  - surface recent counterpart judgment history in backend views and CLI inspection
- Files changed:
  - `amadeus_thread0/memory_store.py`
  - `amadeus_thread0/graph_parts/memory_evolution.py`
  - `amadeus_thread0/utils/cli_views.py`
  - `amadeus_thread0/runtime/backend_session.py`
  - `amadeus_thread0/cli.py`
  - `tests/test_backend_session.py`
  - `tests/test_cli_views.py`
  - `tests/test_memory_evolution_semantic_writeback.py`
- Key changes:
  - added `counterpart_assessment_history` as a dedicated long-term memory namespace with `add/list` accessors and snapshot support
  - final behavior-trace writeback now records counterpart judgment history from the frozen reconsolidation snapshot, including stance / scene / respect / reciprocity / boundary / reliability plus motive context
  - deduped repeated counterpart reads so stable turns do not spam long-term memory
  - exposed counterpart judgment history through `worldline_view()` and `bond_view()`
  - added compact CLI summarizers and rendered the new history inside `/bond`
- Validation:
  - `python -m py_compile amadeus_thread0/memory_store.py amadeus_thread0/graph_parts/memory_evolution.py amadeus_thread0/utils/cli_views.py amadeus_thread0/runtime/backend_session.py amadeus_thread0/cli.py tests/test_backend_session.py tests/test_cli_views.py tests/test_memory_evolution_semantic_writeback.py`
  - `python -m pytest tests/test_memory_evolution_semantic_writeback.py tests/test_backend_session.py tests/test_cli_views.py -q`
  - `python -m pytest tests/test_daily_surface_gating.py tests/test_generation_profile.py tests/test_dialogue_mode_counterpart.py tests/test_world_model_residue.py tests/test_subjective_review_pack.py tests/test_memory_guard.py tests/test_session_orchestrator.py tests/test_cli_views.py -q`
- Result:
  - counterpart judgment is now a persistent inspectable relationship surface, not just runtime state
  - targeted direct regressions and AGENTS-required regression subset are green
- Next:
  - continue backend mainline on `own-rhythm / proactive continuity traces`, aiming to make self-initiated continuity windows equally persistent and inspectable

### 2026-03-20 - Run 04

- Scope:
  - formalize `own-rhythm / proactive continuity` persistence and freeze agenda-lifecycle writeback against final-turn reconsolidation snapshots
- Files changed:
  - `amadeus_thread0/memory_store.py`
  - `amadeus_thread0/graph_parts/memory_evolution.py`
  - `amadeus_thread0/utils/cli_views.py`
  - `amadeus_thread0/runtime/backend_session.py`
  - `amadeus_thread0/cli.py`
  - `tests/test_backend_session.py`
  - `tests/test_cli_views.py`
  - `tests/test_memory_evolution_semantic_writeback.py`
- Key changes:
  - added `proactive_continuity_history` as a dedicated long-term memory namespace with add/list accessors and snapshot support
  - agenda-lifecycle writeback now prefers `reconsolidation_snapshot["agenda_lifecycle_consequence"]` over later-mutating runtime residue
  - long-horizon agenda persistence now writes deduped proactive continuity history records for own-rhythm and continuity windows
  - exposed proactive continuity history through `worldline_view()` and `bond_view()`
  - rendered proactive continuity summaries inside `/worldline` and `/bond`
  - added regression coverage for proactive continuity dedupe and frozen agenda snapshot priority
- Validation:
  - `python -m py_compile amadeus_thread0/memory_store.py amadeus_thread0/graph_parts/memory_evolution.py amadeus_thread0/utils/cli_views.py amadeus_thread0/runtime/backend_session.py amadeus_thread0/cli.py tests/test_backend_session.py tests/test_cli_views.py tests/test_memory_evolution_semantic_writeback.py`
  - `python -m pytest tests/test_memory_evolution_semantic_writeback.py tests/test_backend_session.py tests/test_cli_views.py -q`
  - `python -m pytest tests/test_daily_surface_gating.py tests/test_generation_profile.py tests/test_dialogue_mode_counterpart.py tests/test_world_model_residue.py tests/test_subjective_review_pack.py tests/test_memory_guard.py tests/test_session_orchestrator.py tests/test_cli_views.py -q`
- Result:
  - proactive continuity is now a persisted inspectable backend surface instead of only a local residue
  - agenda-lifecycle writeback is covered against stale runtime-state leakage
  - direct regressions and AGENTS-required regression subset are green
- Next:
  - audit remaining long-term write paths for frozen-final parity, then continue deepening own-rhythm / proactive continuity behavior without prompt-heavy repair

### 2026-03-20 - Run 05

- Scope:
  - close the remaining `frozen-final parity` gap in retrieved continuity reactivation writeback
  - freeze `behavior_plan` and `interaction_carryover` inside reconsolidation snapshots and make writeback prefer them over runtime residue
- Files changed:
  - `amadeus_thread0/evolution_engine/reconsolidation.py`
  - `amadeus_thread0/graph_parts/prepare_turn_runtime.py`
  - `amadeus_thread0/graph_parts/memory_evolution.py`
  - `tests/test_memory_evolution_semantic_writeback.py`
  - `tests/test_cli_views.py`
  - `tests/test_prepare_turn_runtime.py`
- Key changes:
  - extended `build_reconsolidation_snapshot()` to compact and persist final-turn `behavior_plan` and `interaction_carryover`
  - wired `prepare_turn_runtime` so both writeback-time and final runtime snapshots receive the final `behavior_plan` and `interaction_carryover`
  - added frozen snapshot extractors for `behavior_plan` and `interaction_carryover` in `memory_evolution`
  - changed `_record_retrieved_continuity_reactivation()` to prefer frozen carryover, plan, and behavior semantics from `reconsolidation_snapshot` before live runtime inputs
  - added regression coverage for snapshot compaction, runtime-to-snapshot wiring, and stale-live-vs-frozen reactivation priority
- Validation:
  - `python -m py_compile amadeus_thread0/evolution_engine/reconsolidation.py amadeus_thread0/graph_parts/prepare_turn_runtime.py amadeus_thread0/graph_parts/memory_evolution.py tests/test_memory_evolution_semantic_writeback.py tests/test_cli_views.py tests/test_prepare_turn_runtime.py`
  - `python -m pytest tests/test_memory_evolution_semantic_writeback.py tests/test_prepare_turn_runtime.py tests/test_cli_views.py -q`
  - `python -m pytest tests/test_daily_surface_gating.py tests/test_generation_profile.py tests/test_dialogue_mode_counterpart.py tests/test_world_model_residue.py tests/test_subjective_review_pack.py tests/test_memory_guard.py tests/test_session_orchestrator.py tests/test_cli_views.py -q`
- Result:
  - retrieved continuity reactivation now writes from the same frozen final-turn semantics used elsewhere in the reconsolidation path
  - stale runtime carryover / plan residue no longer wins over the final snapshot during long-term writeback
  - targeted regressions and AGENTS-required regression subset are green
- Next:
  - continue the frozen-final parity audit on any remaining long-horizon write paths, then return to deeper `internal state -> motive/goal -> behavior -> reconsolidation` tightening

### 2026-03-20 - Run 06

- Scope:
  - close the remaining `frozen-final parity` gap in long-horizon `behavior_plan` writeback
  - ensure long-term plan traces, worldline tags, and relationship continuity all prefer the final reconsolidation snapshot over stale live residue
- Files changed:
  - `amadeus_thread0/graph_parts/memory_evolution.py`
  - `tests/test_memory_evolution_semantic_writeback.py`
- Key changes:
  - changed `_record_behavior_plan_long_horizon_memory()` to read `behavior_plan` from `_reconsolidation_behavior_plan_snapshot(reconsolidation_snapshot)` first and only fall back to live runtime `behavior_plan` when no frozen snapshot exists
  - added a regression where live `behavior_plan` and frozen snapshot disagree, asserting that `behavior_plan` trace target, worldline tags, and relationship timeline all follow the frozen final plan
- Validation:
  - `python -m py_compile amadeus_thread0/graph_parts/memory_evolution.py tests/test_memory_evolution_semantic_writeback.py`
  - `python -m pytest tests/test_memory_evolution_semantic_writeback.py -q`
  - `python -m pytest tests/test_daily_surface_gating.py tests/test_generation_profile.py tests/test_dialogue_mode_counterpart.py tests/test_world_model_residue.py tests/test_subjective_review_pack.py tests/test_memory_guard.py tests/test_session_orchestrator.py tests/test_cli_views.py -q`
- Result:
  - long-horizon `behavior_plan` persistence is now aligned with the same frozen final-turn semantics already used by reactivation and other writeback paths
  - stale live `behavior_plan` residue no longer contaminates long-term traces when reconsolidation has already decided the final plan
  - targeted regression and AGENTS-required memory-path subset are green
- Next:
  - move off parity cleanup and continue the backend mainline on `internal state -> motive/goal -> behavior -> reconsolidation`, with focus on tightening how final plan/action semantics drive downstream persistence without prompt-heavy repair

### 2026-03-20 - Run 07

- Scope:
  - close the remaining `frozen-final parity` gap for final `behavior_action` visibility
  - make runtime, API, and session surfaces resolve behavior views from frozen reconsolidation state instead of stale live residue
- Files changed:
  - `amadeus_thread0/evolution_engine/reconsolidation.py`
  - `amadeus_thread0/runtime/final_state.py`
  - `amadeus_thread0/runtime/backend_api.py`
  - `amadeus_thread0/runtime/backend_session.py`
  - `tests/test_final_state.py`
  - `tests/test_backend_api.py`
  - `tests/test_backend_session.py`
- Key changes:
  - extended `build_reconsolidation_snapshot()` so final `behavior_action` is compacted and persisted alongside frozen `behavior_plan`
  - changed top-level reconsolidation action fields to read from the frozen action snapshot instead of separate drifting runtime fields
  - taught `resolve_behavior_payloads()` to prefer frozen reconsolidation `behavior_action` and `behavior_plan`, while keeping a compatibility fallback for old snapshots
  - threaded `reconsolidation_snapshot` through backend API and backend session resolution paths so `/persona`, `/worldline`, and API event/turn surfaces all reflect the same final action semantics
  - fixed the backend-session regression to assert against the real `worldline_summary.current_turn` surface instead of a nonexistent `worldline_summary.behavior_action` path
- Validation:
  - `python -m py_compile amadeus_thread0/evolution_engine/reconsolidation.py amadeus_thread0/runtime/final_state.py amadeus_thread0/runtime/backend_api.py amadeus_thread0/runtime/backend_session.py tests/test_final_state.py tests/test_backend_api.py tests/test_backend_session.py`
  - `python -m pytest tests/test_final_state.py tests/test_backend_api.py tests/test_backend_session.py tests/test_prepare_turn_runtime.py -q`
  - `python -m pytest tests/test_daily_surface_gating.py tests/test_generation_profile.py tests/test_dialogue_mode_counterpart.py tests/test_world_model_residue.py tests/test_subjective_review_pack.py tests/test_memory_guard.py tests/test_session_orchestrator.py tests/test_cli_views.py -q`
  - `python -m py_compile amadeus_thread0/agent.py amadeus_thread0/graph.py`
  - `python - <<'PY' ... from amadeus_thread0.agent import agent; print(type(agent).__name__) ... PY`
- Result:
  - final `behavior_action` is now frozen and surfaced consistently across runtime, API, and session inspection paths
  - stale live `behavior_action` residue no longer overrides the final turn semantics after reconsolidation
  - targeted regressions and AGENTS-required regression subset are green; graph entry still resolves to `CompiledStateGraph`
- Next:
  - continue AGENTS mainline on `internal state -> motive/goal -> behavior -> reconsolidation`, focusing on richer state-to-action emergence now that frozen-final surface parity is closed

### 2026-03-20 - Run 08

- Scope:
  - close the remaining `frozen-final parity` gap for `interaction_carryover`
  - align runtime/API/session summaries so final behavior semantics and final carryover residue come from the same reconsolidation snapshot
- Files changed:
  - `amadeus_thread0/runtime/final_state.py`
  - `amadeus_thread0/runtime/backend_api.py`
  - `amadeus_thread0/runtime/backend_session.py`
  - `tests/test_final_state.py`
  - `tests/test_backend_api.py`
  - `tests/test_backend_session.py`
- Key changes:
  - added `interaction_carryover_has_signal()` plus frozen snapshot extraction and `resolve_interaction_carryover()` in `runtime/final_state.py`
  - changed backend session summary resolution so `build_evolution_summary()` and `persona_view()` prefer frozen reconsolidation carryover over stale live carryover
  - extended backend API event/turn envelopes to expose resolved `interaction_carryover` alongside resolved `behavior_action` and `behavior_plan`
  - added regression coverage for frozen carryover priority at final-state, session-view, and backend-API layers
- Validation:
  - `python -m py_compile amadeus_thread0/runtime/final_state.py amadeus_thread0/runtime/backend_api.py amadeus_thread0/runtime/backend_session.py tests/test_final_state.py tests/test_backend_api.py tests/test_backend_session.py`
  - `python -m pytest tests/test_final_state.py tests/test_backend_api.py tests/test_backend_session.py tests/test_prepare_turn_runtime.py -q`
  - `python -m pytest tests/test_daily_surface_gating.py tests/test_generation_profile.py tests/test_dialogue_mode_counterpart.py tests/test_world_model_residue.py tests/test_subjective_review_pack.py tests/test_memory_guard.py tests/test_session_orchestrator.py tests/test_cli_views.py -q`
- Result:
  - final `interaction_carryover` now surfaces consistently across session summaries and backend API envelopes
  - `/persona` and `/worldline` no longer risk mixing frozen final action with stale live carryover residue
  - targeted regressions and AGENTS-required regression subset are green
- Next:
  - return to AGENTS mainline and keep tightening `internal state -> motive/goal -> behavior -> reconsolidation`, now with the main frozen-final surface parity gaps closed for action, plan, and carryover

### 2026-03-20 - Run 09

- Scope:
  - tighten `internal state -> behavior` consistency at the final behavior-resolution layer
  - eliminate late boundary-promotion drift where final `action_target` had already become boundary-protective but `interaction_mode` still exposed a generic reply shell
- Files changed:
  - `amadeus_thread0/graph_parts/behavior_runtime.py`
  - `tests/test_behavior_runtime_alignment.py`
- Key changes:
  - added a final alignment step in `behavior_runtime` so when late state pressure promotes the turn to `protect_relationship_boundary`, the surfaced `interaction_mode`, `attention_target`, `initiative_shape`, and disclosure posture are synchronized to boundary semantics instead of leaking a stale `steady_reply` shell
  - added an explicit `relationship_sensitive` note branch so inspection surfaces reflect the resolved relational stance more clearly
  - added a focused regression proving that a late boundary escalation now resolves to `relationship_sensitive` with boundary-facing action metadata
- Validation:
  - `python -m py_compile amadeus_thread0/graph_parts/behavior_runtime.py tests/test_behavior_runtime_alignment.py`
  - `python -m pytest tests/test_behavior_runtime_alignment.py -q`
  - `python -m pytest tests/test_daily_surface_gating.py tests/test_generation_profile.py tests/test_dialogue_mode_counterpart.py tests/test_world_model_residue.py tests/test_subjective_review_pack.py tests/test_memory_guard.py tests/test_session_orchestrator.py tests/test_cli_views.py -q`
- Result:
  - late state-driven boundary escalation now changes the final surfaced behavior mode instead of only swapping the target label underneath
  - downstream inspection/eval layers see one coherent boundary-protective behavior packet rather than mixed `steady_reply + protect_relationship_boundary` semantics
  - targeted regression and AGENTS-required graph-layer regression subset are green
- Next:
  - continue AGENTS mainline on `internal state -> motive/goal -> behavior`, with the next pass focused on other late-state promotions where final action semantics may still be richer than the surfaced behavior shell

### 2026-03-20 - Run 10

- Scope:
  - continue the AGENTS mainline on `internal state -> motive/goal -> behavior`
  - eliminate repair-scene drift where strong repair residue still surfaced as a generic `companion_reply/respond_now` packet
- Files changed:
  - `amadeus_thread0/graph_parts/behavior_runtime.py`
  - `tests/test_behavior_runtime_alignment.py`
- Key changes:
  - added a final repair-continuity alignment step in `behavior_runtime` so a high-residue repair turn no longer falls through to generic contact semantics
  - when `repair_context_active` and late state still resolves to `steady_reply/companion_reply + respond_now`, the final behavior packet now upgrades to `low_pressure_support + low_pressure_hold` with aligned attention, initiative, disclosure, and follow-up pressure
  - added a focused regression proving that a watchful repair-attempt scene with strong repair residue and commitment carry now resolves to low-pressure repair behavior rather than a generic reply shell
- Validation:
  - `python -m py_compile amadeus_thread0/graph_parts/behavior_runtime.py tests/test_behavior_runtime_alignment.py`
  - `python -m pytest tests/test_behavior_runtime_alignment.py -q`
  - `python -m pytest tests/test_daily_surface_gating.py tests/test_generation_profile.py tests/test_dialogue_mode_counterpart.py tests/test_world_model_residue.py tests/test_subjective_review_pack.py tests/test_memory_guard.py tests/test_session_orchestrator.py tests/test_cli_views.py -q`
- Result:
  - repair-heavy user turns with lingering watchfulness no longer surface as plain `companion_reply/respond_now`
  - final behavior semantics now reflect a real low-pressure repair stance: `low_pressure_support/low_pressure_hold` with `support_without_pressure` as the primary motive
  - targeted regression and AGENTS-required regression subset are green
- Next:
  - continue the backend mainline by tightening how `commitment_carry`, `continuity_depth`, and own-rhythm traces shape proactive or deferred behavior beyond the repair path

### 2026-03-20 - Run 11

- Scope:
  - continue the AGENTS mainline on `internal state -> motive/goal -> behavior`
  - make continuity and commitment traces affect final motive semantics directly instead of only surviving as notes or carryover residue
- Files changed:
  - `amadeus_thread0/graph_parts/behavior_runtime.py`
  - `tests/test_behavior_runtime_alignment.py`
- Key changes:
  - completed the continuity-aware motive path in `behavior_runtime` by wiring `continuity_depth` from semantic narrative evidence into `_derive_behavior_motive(...)`
  - kept the existing final action shell resolution intact while upgrading motive semantics for continuity-heavy scenes:
    - `user_utterance + respond_now + life/task/shared window` can now resolve to `honor_continuity` or `open_shared_window`
    - `time_idle + reach_out_now + light_checkin` with strong continuity/commitment can now resolve to `honor_continuity`
  - added focused regressions proving that life-window user turns and high-commitment idle reach-outs no longer collapse back to generic `maintain_natural_contact`
- Validation:
  - `python -m py_compile E:\桌面\amadeus-thread0\amadeus_thread0\graph_parts\behavior_runtime.py E:\桌面\amadeus-thread0\tests\test_behavior_runtime_alignment.py`
  - `python -m pytest E:\桌面\amadeus-thread0\tests\test_behavior_runtime_alignment.py -q`
  - `python -m pytest tests/test_daily_surface_gating.py tests/test_generation_profile.py tests/test_dialogue_mode_counterpart.py tests/test_world_model_residue.py tests/test_subjective_review_pack.py tests/test_memory_guard.py tests/test_session_orchestrator.py tests/test_cli_views.py -q`
- Result:
  - continuity-heavy turns now keep a continuity-shaped motive instead of surfacing the right action shell with a generic contact motive underneath
  - proactive light check-ins can carry real “unfinished continuity” semantics without adding prompt-side scripting
  - targeted regression and AGENTS-required regression subset are green
- Next:
  - continue the backend mainline on `internal state -> motive/goal -> behavior -> reconsolidation`, with the next pass focused on making own-rhythm traces and resolved motive semantics write back cleanly into reconsolidated memory traces

### 2026-03-20 - Run 12

- Scope:
  - continue the AGENTS mainline on `behavior -> reconsolidation -> memory trace writeback`
  - remove a remaining source-of-truth drift where writeback paths could still derive consequences or reactivation alignment from stale live `behavior_action` instead of the final reconsolidated action packet
- Files changed:
  - `amadeus_thread0/graph_parts/memory_evolution.py`
  - `tests/test_memory_evolution_semantic_writeback.py`
- Key changes:
  - added `_reconsolidation_behavior_action_snapshot()` so memory writeback can read the frozen final `behavior_action` from `reconsolidation_snapshot`, not only top-level motive fields
  - changed `_record_behavior_consequence()` to derive consequence shape from frozen final action when available, including late-resolved `action_target` / `interaction_mode`
  - changed `_record_retrieved_continuity_reactivation()` to align against frozen final `action_target` before falling back to the live action shell
  - tightened `_record_counterpart_assessment_long_horizon_memory()` so if top-level frozen motive fields are absent, fallback still prefers frozen final action over stale live action
  - added focused regressions proving:
    - `behavior_consequence` no longer writes `hold_own_rhythm` when reconsolidation froze the turn as `wait_and_recheck`
    - reactivation traces now expose the frozen final `current_action_target`
- Validation:
  - `python -m py_compile E:\桌面\amadeus-thread0\amadeus_thread0\graph_parts\memory_evolution.py E:\桌面\amadeus-thread0\tests\test_memory_evolution_semantic_writeback.py`
  - `python -m pytest E:\桌面\amadeus-thread0\tests\test_memory_evolution_semantic_writeback.py -q`
  - `python -m pytest tests/test_memory_guard.py tests/test_session_orchestrator.py tests/test_cli_views.py -q`
- Result:
  - writeback now treats frozen reconsolidated `behavior_action` as the source of truth whenever consequence or reactivation logic still depends on action-shell fields
  - final resolved motive/action semantics now survive past runtime and into long-horizon memory traces more consistently
  - targeted writeback regression and AGENTS-required memory-path regression subset are green
- Next:
  - continue the backend mainline on `reconsolidation -> self-narrative`, focusing on whether semantic self-narrative updates compress the now-richer motive/consequence traces without flattening own-rhythm and continuity distinctions

### 2026-03-20 - Run 13

- Scope:
  - continue the AGENTS mainline on `reconsolidation -> self-narrative`
  - remove late semantic compression where `own-rhythm`, `continuity`, and `reactivation` traces were preserved in runtime/writeback but flattened again at narrative export surfaces
- Files changed:
  - `amadeus_thread0/graph_parts/semantic_narrative.py`
  - `tests/test_world_model_residue.py`
- Key changes:
  - added shared semantic category summary thresholds/lines so semantic export and compact hint generation use one category-to-surface mapping instead of several fixed-order fragments
  - added `continuity_axes` to the semantic narrative profile, preserving top continuity categories as a structured, score-ordered snapshot with `reactivated`, `lineage_depth`, and motive fields
  - changed `long_term_self_narratives` to build from deduped `identity_snapshot` winners rather than raw `identity_items`, preventing duplicate categories from occupying multiple long-term narrative slots
  - tightened `identity_snapshot` to retain richer winning evidence metadata (`sedimentation_score`, `persistence_score`, `integration_score`, `support_span_s`, `reactivation_hits`) so the long-term narrative export stays category-unique without losing detail
  - changed `summary_lines` generation from fixed category order to score-prioritized selection, so strong `rhythm/selfhood/commitment` traces are surfaced by actual semantic weight instead of whichever line was listed first
  - changed `_compact_semantic_narrative_hint()` to rank hint lines from `continuity_axes` plus numeric profile scores instead of blindly prepending `presence/ambient/rhythm`, preventing weaker early categories from crowding out the real dominant axes
  - added focused regressions proving:
    - semantic long-term narrative export no longer duplicates one category when multiple evidence items support the same axis
    - compact hint export prefers strongest axes over fixed-order truncation
- Validation:
  - `python -m py_compile E:\桌面\amadeus-thread0\amadeus_thread0\graph_parts\semantic_narrative.py E:\桌面\amadeus-thread0\tests\test_world_model_residue.py`
  - `python -m pytest E:\桌面\amadeus-thread0\tests\test_world_model_residue.py -q`
  - `python -m pytest E:\桌面\amadeus-thread0\tests\test_memory_evolution_semantic_writeback.py -q`
  - `python -m pytest tests/test_daily_surface_gating.py tests/test_generation_profile.py tests/test_dialogue_mode_counterpart.py tests/test_world_model_residue.py tests/test_subjective_review_pack.py tests/test_memory_guard.py tests/test_session_orchestrator.py tests/test_cli_views.py -q`
- Result:
  - semantic self-narrative export now preserves distinct long-horizon motive families more faithfully instead of collapsing them at the last presentation layer
  - `own-rhythm` can stay visible as a top semantic axis even when other continuity traces are also active
  - long-term self-narrative slots now represent distinct categories rather than repeated evidence from one category
  - targeted and AGENTS-required regression are green after the export-layer tightening
- Next:
  - continue the backend mainline on `reconsolidation -> self-narrative -> counterpart assessment persistence`, checking whether counterpart judgment and reconsolidated relationship traces still lose distinction when they are lifted into long-horizon semantic/state summaries

### 2026-03-21 - Run 14

- Scope:
  - formalize a high-bar backend finish line so the project does not keep drifting in open-ended optimization
  - make the repository itself define when backend work is mature enough to stop structural iteration and permit frontend handoff
- Files changed:
  - `AGENTS.md`
  - `docs/engineering/BACKEND_HANDOFF.md`
- Key changes:
  - added an explicit `Backend Freeze Gate` to `AGENTS.md`
  - defined backend completion as four simultaneous conditions:
    - core loop closure
    - long-horizon persistence closure
    - natural conversation acceptance
    - frontend handoff readiness
  - set a higher standard than “tests pass”: backend now also requires manual natural-dialogue smoke packs and repeated green regression before it can be treated as structurally complete
  - updated `BACKEND_HANDOFF.md` with a matching `Freeze-Lift Gate` so frontend work stays frozen until backend payloads reflect final semantics rather than still-changing internal architecture
- Validation:
  - docs-only policy update; no code-path validation required
- Result:
  - backend closure now has a repository-level high bar instead of an informal “keep optimizing until it feels done” rule
  - future runs can be judged against explicit exit criteria, reducing the risk of endless polishing without a real stopping point
  - frontend remains intentionally frozen until the backend satisfies the same explicit standard from both the architecture and handoff perspectives
- Next:
  - resume the mainline on `reconsolidation -> self-narrative -> counterpart assessment persistence`
  - use the new freeze gate as the standard for deciding whether a change is still core backend work or just later-stage polish

### 2026-03-21 - Run 15

- Scope:
  - finish the next `counterpart assessment persistence` pass by removing the remaining late flattening points
  - keep counterpart judgment structured not only in history/CLI surfaces but also inside semantic self-narrative aggregation
- Files changed:
  - `amadeus_thread0/graph_parts/relational_runtime.py`
  - `amadeus_thread0/graph_parts/counterpart_dynamics.py`
  - `amadeus_thread0/evolution_engine/reconsolidation.py`
  - `amadeus_thread0/memory_store.py`
  - `amadeus_thread0/graph_parts/memory_evolution.py`
  - `amadeus_thread0/graph_parts/semantic_narrative.py`
  - `amadeus_thread0/utils/cli_views.py`
  - `tests/test_cli_views.py`
  - `tests/test_backend_session.py`
  - `tests/test_memory_evolution_semantic_writeback.py`
  - `tests/test_world_model_residue.py`
- Key changes:
  - added a normalized `assessment_profile` for counterpart judgment with `openness_drive`, `guarded_drive`, `guard_margin`, and dominant scene signal
  - carried that profile through `counterpart_dynamics -> reconsolidation snapshot -> counterpart_assessment_history -> CLI/session summary`
  - upgraded `build_evolution_cli_summary()` and counterpart-history rendering so backend surfaces no longer compress the judgment vector to stance-only previews
  - extended semantic self-evidence trace metadata to include counterpart judgment drives/signals from the frozen reconsolidation snapshot
  - changed semantic self-narrative refresh to aggregate counterpart judgment per category, then export it through `semantic_narrative_profile.counterpart_snapshot`, `continuity_axes`, `top_narratives`, and `long_term_self_narratives`
  - verified that counterpart judgment now survives both presentation-layer summaries and semantic/selfhood aggregation instead of dropping out after writeback
- Validation:
  - `python -m py_compile amadeus_thread0/graph_parts/relational_runtime.py amadeus_thread0/graph_parts/counterpart_dynamics.py amadeus_thread0/evolution_engine/reconsolidation.py amadeus_thread0/memory_store.py amadeus_thread0/graph_parts/memory_evolution.py amadeus_thread0/utils/cli_views.py tests/test_cli_views.py tests/test_backend_session.py tests/test_memory_evolution_semantic_writeback.py`
  - `python -m pytest tests/test_cli_views.py tests/test_backend_session.py tests/test_memory_evolution_semantic_writeback.py -q`
  - `python -m py_compile amadeus_thread0/graph_parts/memory_evolution.py amadeus_thread0/graph_parts/semantic_narrative.py tests/test_memory_evolution_semantic_writeback.py tests/test_world_model_residue.py`
  - `python -m pytest tests/test_memory_evolution_semantic_writeback.py tests/test_world_model_residue.py -q`
  - `python -m pytest tests/test_daily_surface_gating.py tests/test_generation_profile.py tests/test_dialogue_mode_counterpart.py tests/test_world_model_residue.py tests/test_subjective_review_pack.py tests/test_memory_guard.py tests/test_session_orchestrator.py tests/test_cli_views.py -q`
- Result:
  - counterpart judgment is now a first-class structured long-horizon signal across runtime, CLI, history, and semantic self-narrative layers
  - the backend no longer loses counterpart read semantics at the last summary layer or inside semantic narrative consolidation
  - AGENTS-required regression subset stayed green after the deeper persistence/aggregation pass
- Next:
  - continue backend freeze-gate work on `counterpart assessment -> relationship_state` so respect / reciprocity / reliability shape bond-state derivation and later relation summaries more directly

### 2026-03-21 - Run 16

- Scope:
  - continue the freeze-gate pass on `counterpart assessment -> relationship_state`
  - fix the runtime relationship snapshot so bond-stage derivation actually consumes the fuller counterpart judgment vector instead of mostly `boundary_pressure`
- Files changed:
  - `amadeus_thread0/graph_parts/relational_runtime.py`
  - `tests/test_dialogue_mode_counterpart.py`
- Key changes:
  - added `_counterpart_relationship_pressures()` to derive relationship-facing positive/guarded/instability signals from structured counterpart judgment
  - changed `_relationship_runtime_snapshot()` so `respect_level`, `reciprocity`, `reliability_read`, `assessment_profile.openness_drive`, and guardedness now contribute directly to `affinity_score`, `trust_score`, stage selection, and notes
  - kept neutral counterpart reads close to previous behavior while allowing:
    - positive/open counterpart reads to warm the relationship more directly
    - low-reliability guarded reads to suppress trust without overusing boundary pressure as the only drag term
  - added focused regressions for:
    - positive counterpart warmth lifting `friend -> warming`
    - guarded low-reliability reads staying cautious and explicitly surfacing the trust gap
- Validation:
  - `python -m py_compile amadeus_thread0/graph_parts/relational_runtime.py tests/test_dialogue_mode_counterpart.py`
  - `python -m pytest tests/test_dialogue_mode_counterpart.py -k "relationship_runtime_snapshot or prefer_refreshed_relationship_state" -q`
  - `python -m pytest tests/test_daily_surface_gating.py tests/test_generation_profile.py tests/test_dialogue_mode_counterpart.py tests/test_world_model_residue.py tests/test_subjective_review_pack.py -q`
  - `python -m pytest tests/test_backend_session.py tests/test_cli_views.py -q`
- Result:
  - runtime relationship-state derivation no longer flattens richer counterpart judgment into almost pure boundary-pressure behavior
  - graph-layer AGENTS regression subset stayed green after the change
  - session and CLI consumers of relationship state also stayed green
- Next:
  - inspect persisted `memory_store` relationship derivation and the runtime-vs-persisted chooser so the richer counterpart judgment survives not only runtime but also the refreshed long-horizon bond surfaces

### 2026-03-21 - Run 17

- Scope:
  - finish the freeze-gate pass on `counterpart assessment -> relationship_state`
  - validate that persisted `memory_store` relationship derivation now keeps pace with the richer runtime counterpart judgment
- Files changed:
  - `amadeus_thread0/memory_store.py`
  - `tests/test_world_model_residue.py`
  - `program.md`
- Key changes:
  - added local counterpart-profile normalization helpers inside `MemoryStore` so persisted relationship derivation can consume structured counterpart judgment without introducing a circular import from `relational_runtime`
  - changed `_derive_relationship_state()` and `get_relationship()` to merge `counterpart_assessment_history` evidence into `affinity_score`, `trust_score`, stage evidence density, and fallback notes
  - verified that low-anchor explicit relationship states can now warm up from repeated positive/open counterpart history and that guarded low-reliability reads depress trust more than affinity on the persisted path too
  - audited `_prefer_refreshed_relationship_state(...)` after the persisted upgrade and kept it unchanged because the refreshed persisted state now carries meaningful signal rather than stale low-information summaries
- Validation:
  - `python -m py_compile amadeus_thread0/memory_store.py tests/test_world_model_residue.py`
  - `python -m pytest tests/test_world_model_residue.py -k "get_relationship or counterpart_history" -q`
  - `python -m pytest tests/test_daily_surface_gating.py tests/test_generation_profile.py tests/test_dialogue_mode_counterpart.py tests/test_world_model_residue.py tests/test_subjective_review_pack.py -q`
  - `python -m pytest tests/test_memory_guard.py tests/test_session_orchestrator.py tests/test_cli_views.py -q`
  - `python -m pytest tests/test_backend_session.py -q`
- Result:
  - persisted relationship-state derivation no longer collapses richer counterpart judgment back into timeline-only relation summaries
  - runtime and persisted bond-state surfaces are now aligned on the same structured counterpart-read semantics
  - focused validation plus AGENTS-required regression subsets all stayed green after the persistence-layer tightening
- Next:
  - continue backend freeze-gate work on `own-rhythm / proactive continuity` and manual natural-dialogue smoke validation, now that the `counterpart assessment -> relationship_state` path is aligned across runtime and persistence

### 2026-03-21 - Run 18

- Scope:
  - close the next `own-rhythm / proactive continuity` freeze-gate gap
  - make persisted proactive continuity history re-enter runtime carryover instead of staying as a read-only CLI/backend inspection surface
- Files changed:
  - `amadeus_thread0/graph_parts/relational_carryover.py`
  - `amadeus_thread0/graph_parts/prepare_turn_context.py`
  - `tests/test_world_model_residue.py`
  - `tests/test_prepare_turn_context.py`
  - `program.md`
- Key changes:
  - added local proactive-history normalization and a conservative `_proactive_continuity_history_carryover()` path in `relational_carryover`
  - extended `_recent_interaction_carryover(...)` with `proactive_continuity_history` and merged the persisted-history fallback into the existing `long_horizon -> relational -> agenda` chooser via `_prefer_relational_carryover(...)`
  - fetched `store.list_proactive_continuity_history(limit=12)` inside `_prepare_turn_context()` and threaded that history into both appraisal-time and main carryover derivation calls
  - added a focused residue regression proving that a recent persisted own-rhythm history item can backfill `interaction_carryover` without a fresh non-user event
  - added a `prepare_turn_context` regression proving the persisted proactive history actually reaches `_recent_interaction_carryover(...)`
- Validation:
  - `python -m py_compile amadeus_thread0/graph_parts/relational_carryover.py amadeus_thread0/graph_parts/prepare_turn_context.py tests/test_world_model_residue.py tests/test_prepare_turn_context.py`
  - `python -m pytest tests/test_world_model_residue.py -k "persisted_proactive_history or long_horizon_own_rhythm_without_recent_non_user_event or agenda_lifecycle_residue" -q`
  - `python -m pytest tests/test_prepare_turn_context.py -k "proactive_continuity_history or semantic_narrative_profile" -q`
  - `python -m pytest tests/test_daily_surface_gating.py tests/test_generation_profile.py tests/test_dialogue_mode_counterpart.py tests/test_world_model_residue.py tests/test_subjective_review_pack.py -q`
- Result:
  - persisted proactive continuity is now a causal runtime input, not just a persisted audit/log surface
  - own-rhythm / continuity traces can survive beyond CLI inspection and seed later-turn carryover even when no fresh non-user event is available
  - focused regressions and the AGENTS graph-layer regression subset stayed green after the change
- Next:
  - move from persistence closure into manual natural-dialogue smoke packs for `everyday companionship`, `relational tension / repair`, and `self-rhythm / proactive continuity` so the backend freeze gate can start closing on behavior, not only structure

### 2026-03-21 - Run 19

- Scope:
  - harden the new freeze-gate smoke runner so it catches real duplicate-output regressions without mislabeling ordinary lab-context nouns as persona drift
  - produce a real-model combined smoke artifact for the three AGENTS natural-dialogue packs
- Files changed:
  - `evals/run_freeze_gate_smokes.py`
  - `tests/test_freeze_gate_smokes.py`
  - `program.md`
- Key changes:
  - fixed `_has_duplicate_sequence(...)` so short exact repeated replies like `我在。我在。` are now treated as duplicate output rather than slipping past the old length threshold
  - added `_meaningful_text(...)` to separate true content from punctuation-only repeats when judging duplicate segments
  - tightened everyday surface-drift detection inside the smoke runner so `实验室` / `实验室成员` no longer trigger a false positive from the raw `实验` marker, while actual `实验` trope drift is still flagged
  - added regression coverage for both short duplicate replies and the `实验室成员` vs `重要实验` distinction
  - generated real smoke reports for:
    - `everyday_companionship`: `evals/reports/freeze-gate-smokes-20260321-144943-d1d15856.{json,md}`
    - `repair_apology + self_rhythm_boundary`: `evals/reports/freeze-gate-smokes-20260321-145502-27ed25c1.{json,md}`
    - all three packs combined: `evals/reports/freeze-gate-smokes-20260321-150221-c2af8a53.{json,md}`
- Validation:
  - `python -m py_compile evals/run_freeze_gate_smokes.py tests/test_freeze_gate_smokes.py tests/test_subjective_review_pack.py`
  - `python -m pytest tests/test_freeze_gate_smokes.py tests/test_subjective_review_pack.py -q`
  - `python evals/run_freeze_gate_smokes.py --pack everyday_companionship --case-timeout-s 180`
  - `python evals/run_freeze_gate_smokes.py --pack repair_apology --pack self_rhythm_boundary --case-timeout-s 180`
  - `python evals/run_freeze_gate_smokes.py --case-timeout-s 180`
- Result:
  - the smoke runner is now usable as a backend freeze-gate artifact rather than a near-pass tool with obvious false positives
  - all three AGENTS-required natural-dialogue smoke packs passed on the real model path in one combined report
- Next:
  - keep closing the backend freeze gate by pairing the new smoke artifact with the AGENTS regression-streak requirement and a final `BACKEND_HANDOFF.md` contract audit

### 2026-03-21 - Run 20

- Scope:
  - finish the remaining backend handoff contract closeout work for the freeze gate
  - align mock assets with the runtime payloads already exposed by `BackendAPI` / `BackendSession`
- Files changed:
  - `docs/engineering/BACKEND_HANDOFF.md`
  - `docs/engineering/frontend_contract/mocks/assistant_turn.json`
  - `docs/engineering/frontend_contract/mocks/event_round.json`
  - `docs/engineering/frontend_contract/mocks/worldline_view.json`
  - `docs/engineering/frontend_contract/mocks/bond_view.json`
  - `program.md`
- Key changes:
  - added `interaction_carryover` to the `assistant_turn` and `event_round` mock envelopes so the mock layer now matches the already-updated runtime contract and TypeScript definitions
  - extended `worldline_view.json` with `counterpart_assessment_history`, `counterpart_assessment_preview`, `proactive_continuity_history`, and `proactive_continuity_preview`
  - created a first-class `bond_view.json` mock that mirrors the current `BackendSession.bond_view()` shape for relationship continuity consumers
  - updated `BACKEND_HANDOFF.md` so the mock asset inventory explicitly includes `bond_view.json`
  - ran a JSON-level contract audit over the mock directory to ensure the required payload keys exist after the closeout patch
- Validation:
  - `python -m pytest tests/test_daily_surface_gating.py tests/test_generation_profile.py tests/test_dialogue_mode_counterpart.py tests/test_world_model_residue.py tests/test_subjective_review_pack.py -q`
  - `python - < mock JSON audit script` -> `mock-json-ok`
- Result:
  - frontend handoff docs, TypeScript surface, and mock assets are now aligned with the actual backend payloads instead of exposing stale partial examples
  - `bond_view` is no longer documented without a consumable mock artifact
  - the freeze-gate contract closeout is now blocked by backend acceptance judgment, not by missing handoff assets
- Next:
  - decide whether the backend freeze gate can be considered structurally closed using the existing smoke artifact, AGENTS regression streak, and human transcript review; if not, go straight back to the failing behavior/persistence layer

### 2026-03-21 - Run 21

- Scope:
  - close the eval/CLI stale-final-text leak that was still surfacing pre-finalized replies in smoke artifacts
  - tighten repair-scene postprocess gating so reflective repair turns cannot bypass wording/boundary cleanup
- Files changed:
  - `evals/run_langsmith_evals.py`
  - `amadeus_thread0/graph_parts/state.py`
  - `amadeus_thread0/graph_parts/response_finalize.py`
  - `amadeus_thread0/runtime/backend_session.py`
  - `amadeus_thread0/graph_parts/postprocess.py`
  - `tests/test_eval_runner_controls.py`
  - `tests/test_response_finalize.py`
  - `tests/test_backend_session.py`
  - `tests/test_daily_surface_gating.py`
  - `program.md`
- Key changes:
  - added an explicit `final_text` state field, wrote it from `_finalize_text_response(...)`, and updated runtime/eval extraction paths to prefer that field over `messages[-1]`
  - changed eval `_run_graph()` answer extraction so smoke/report consumers no longer read stale invoke output when finalized state is available
  - added response-finalize regression coverage proving rewritten text is re-sanitized after natural-dialog rewrite, not only before it
  - expanded repair-scene surface detection/cleanup for `wording_meta_detour`, `boundary_abstraction_surface`, and `technical_self_activity` so the same cleanup also applies when repair replies route through `selfhood_reflection`
  - broadened postprocess cleanup over the concrete bad variants seen in real-model repair outputs (`界限还在`, `完美复原`, `完美宽容`, `完美的宽容大度`, `数据层面的`, `自我缓住`, `做缓住自己`, `既然你都看出来了`)
  - rechecked the real-model `guarded_everyday_user` case directly after the fix and confirmed the output now resolves to one finalized repair reply instead of the earlier meta-rerouted transcript
- Validation:
  - `python -m py_compile evals/run_langsmith_evals.py amadeus_thread0/graph_parts/state.py amadeus_thread0/graph_parts/response_finalize.py amadeus_thread0/runtime/backend_session.py amadeus_thread0/graph_parts/postprocess.py tests/test_eval_runner_controls.py tests/test_response_finalize.py tests/test_backend_session.py tests/test_daily_surface_gating.py`
  - `python -m pytest tests/test_eval_runner_controls.py -q`
  - `python -m pytest tests/test_response_finalize.py tests/test_backend_session.py tests/test_daily_surface_gating.py tests/test_eval_runner_controls.py -q`
  - `python evals/run_freeze_gate_smokes.py --pack everyday_companionship --case-timeout-s 180`
  - `python evals/run_freeze_gate_smokes.py --pack self_rhythm_boundary --case-timeout-s 180`
  - `python - < single-case _run_graph(...) check for guarded_everyday_user`
- Result:
  - smoke/eval extraction is now aligned to finalized reply state instead of stale message tails
  - the guarded repair sample no longer depends on the old `messages[-1]` leak path and now surfaces a single finalized reply through `_run_graph()`
  - repair-scene cleanup coverage is materially stronger for reflective-but-still-relational turns, which were previously slipping past the wording/boundary filters
- Next:
  - rerun the remaining real-model freeze-gate packs from this updated path and use that refreshed artifact to decide whether backend freeze-closeout is justified or whether more repair-scene behavior tightening is still needed
