# Procedural Growth Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Phase 1 procedural traces guide autonomy planning as advisory bias while preserving approval gates, execution boundaries, browser/manual-takeover rules, skills registry separation, and Phase 1 writeback truth.

**Architecture:** Add `amadeus_thread0.graph_parts.procedural_planning` as a pure bias builder over current event text, carried embodied procedural traces, and current access hints. Integrate the bias into `autonomy_runtime` so only safe sandbox biases can produce existing approval-gated action packets, then surface the bias through backend/session/CLI summaries and deterministic phase-2 evals.

**Tech Stack:** Python 3, pytest, existing LangGraph graph-parts, existing action-packet normalization, existing backend API/session/CLI readback, existing eval report conventions.

---

## File Structure

- Create `amadeus_thread0/graph_parts/procedural_planning.py`
  - Owns candidate extraction, ranking, request matching, boundary checks, and compact `procedural_planning` bias output.
- Create `tests/test_procedural_planning.py`
  - Pure helper tests for completed sandbox, blocked boundary, browser takeover, skill guidance, low confidence, dedupe, and access mismatch.
- Modify `amadeus_thread0/graph_parts/autonomy_runtime.py`
  - Computes procedural planning bias and uses it only for approval-preserving sandbox packets or readback-only boundary/manual/skill planning.
- Modify `tests/test_companion_autonomy_runtime.py`
  - Adds Phase 2 autonomy integration tests without breaking Phase 1 procedural-continuity tests.
- Modify `amadeus_thread0/runtime/backend_api.py`
  - Adds `autonomy.procedural_planning` readback for turn/event payloads.
- Modify `amadeus_thread0/runtime/backend_session.py`
  - Adds `autonomy.procedural_planning` to session summary normalization.
- Modify `amadeus_thread0/utils/turn_summary_export.py`
  - Preserves procedural planning in turn summary export.
- Modify `amadeus_thread0/utils/cli_views.py`
  - Adds compact `planproc=<kind>:<run>:<status>` readback.
- Modify `tests/test_backend_api.py`, `tests/test_backend_session.py`, and `tests/test_cli_views.py`
  - Adds focused procedural-planning readback coverage.
- Create `evals/run_procedural_growth_phase2_smokes.py`
  - Offline deterministic smoke scenarios for Phase 2.
- Create `evals/run_procedural_growth_phase2_audit.py`
  - Audit runner requiring Phase 2 unit/integration/readback tests and smokes.
- Create `tests/test_procedural_growth_phase2_audit.py`
  - Audit helper tests.
- Modify `docs/engineering/PROJECT_STRUCTURE.md`
  - Documents `procedural_planning.py` ownership.
- Modify `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
  - Adds Phase 2 preserved contract once validation passes.
- Modify `program.md`
  - Records plan, implementation, validation, and next step.

## Tasks

### Task 1: Pure Procedural Planning Bias

**Files:**
- Create: `tests/test_procedural_planning.py`
- Create: `amadeus_thread0/graph_parts/procedural_planning.py`

- [ ] Write failing tests that import:
  - `build_procedural_planning_bias`
  - `normalize_procedural_planning`
- [ ] Cover these behaviors:
  - completed sandbox pytest trace plus matching current request returns `bias_kind="sandbox_execute"`, `suggested_executor="pytest"`, `suggested_argv=["pytest"]`, `must_request_approval=True`, and `capability_claim=True`
  - blocked boundary trace returns `bias_kind="boundary_only"`, `avoid_repeating_boundary=True`, and `capability_claim=False`
  - browser manual takeover trace returns `bias_kind="browser_manual_takeover"`, `must_request_approval=True`, and no browser mutation fields
  - skill usage trace returns `bias_kind="skill_guidance"` without registry mutation fields
  - confidence below `0.35` returns `{}`
  - duplicated trace ids are deduped and the higher-confidence trace wins
  - sandbox execution bias is ignored when carried `workspace_root` differs from current access `workspace_root`
- [ ] Run:
  - `python -m pytest tests/test_procedural_planning.py -q`
  - Expected before implementation: fail with missing module/function.
- [ ] Implement `procedural_planning.py` with pure helpers only.
- [ ] Run:
  - `python -m pytest tests/test_procedural_planning.py -q`
  - Expected after implementation: pass.

### Task 2: Autonomy Runtime Integration

**Files:**
- Modify: `tests/test_companion_autonomy_runtime.py`
- Modify: `amadeus_thread0/graph_parts/autonomy_runtime.py`

- [ ] Add failing tests proving:
  - carried Phase 1 `procedural_traces` can create a Phase 2 pytest packet only when the current request matches
  - the packet stays `awaiting_approval`, `risk="external_mutation"`, and `requires_approval=True`
  - the packet includes `tool_args.procedural_planning.trace_id`
  - a blocked trace creates readback-only planning and does not create `execute_workspace_command`
  - a browser manual-takeover trace creates readback-only planning and does not create browser mutation packet
- [ ] Run:
  - `python -m pytest tests/test_companion_autonomy_runtime.py -k procedural -q`
  - Expected before implementation: new tests fail because `procedural_planning` is missing or ignored.
- [ ] Compute `procedural_planning` in `derive_autonomy_runtime()`.
- [ ] Use the bias to build a sandbox packet only for `bias_kind="sandbox_execute"` and existing allowed executors.
- [ ] Add the bias to `action_trace[0].procedural_planning` and the returned runtime payload.
- [ ] Run:
  - `python -m pytest tests/test_companion_autonomy_runtime.py -k procedural -q`
  - Expected after implementation: pass.

### Task 3: Backend, Session, And CLI Readback

**Files:**
- Modify: `tests/test_backend_api.py`
- Modify: `tests/test_backend_session.py`
- Modify: `tests/test_cli_views.py`
- Modify: `amadeus_thread0/runtime/backend_api.py`
- Modify: `amadeus_thread0/runtime/backend_session.py`
- Modify: `amadeus_thread0/utils/turn_summary_export.py`
- Modify: `amadeus_thread0/utils/cli_views.py`

- [ ] Add failing readback tests:
  - backend turn response exposes `payload.autonomy.procedural_planning`
  - backend event response exposes the same shape
  - session evolution summary exposes `summary["autonomy"]["procedural_planning"]`
  - `summary["current_turn"]["procedural_planning"]` mirrors the compact bias
  - CLI summary line includes `planproc=sandbox_execute:<source_run_id>:approval`
- [ ] Run:
  - `python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py -k procedural -q`
  - Expected before implementation: new readback assertions fail.
- [ ] Thread `procedural_planning` through existing autonomy summary helpers.
- [ ] Render compact CLI readback after the existing `procedure=...` trace line.
- [ ] Run:
  - `python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py -k procedural -q`
  - Expected after implementation: pass.

### Task 4: Phase 2 Smokes And Audit

**Files:**
- Create: `tests/test_procedural_growth_phase2_audit.py`
- Create: `evals/run_procedural_growth_phase2_smokes.py`
- Create: `evals/run_procedural_growth_phase2_audit.py`

- [ ] Write failing audit helper tests for:
  - required smoke scenario ids
  - smoke output parser
  - readiness aggregation
  - markdown rendering
  - blocking failure ids
- [ ] Run:
  - `python -m pytest tests/test_procedural_growth_phase2_audit.py -q`
  - Expected before implementation: fail with missing eval module.
- [ ] Implement smoke runner with:
  - `completed_sandbox_trace_guides_pytest_packet_with_approval`
  - `blocked_trace_becomes_boundary_bias_not_execution`
  - `browser_takeover_trace_surfaces_manual_boundary`
  - `skill_usage_trace_guides_without_registry_mutation`
  - `low_confidence_or_mismatched_trace_is_ignored`
- [ ] Implement audit runner requiring:
  - `tests/test_procedural_planning.py`
  - `tests/test_companion_autonomy_runtime.py -k procedural`
  - backend/session/CLI procedural readback tests
  - phase-2 smokes
- [ ] Run:
  - `python -m pytest tests/test_procedural_growth_phase2_audit.py -q`
  - `python evals/run_procedural_growth_phase2_smokes.py --run-tag phase2-dev`
  - `python evals/run_procedural_growth_phase2_audit.py --run-tag phase2-dev`
  - Expected after implementation: pass with readiness `procedural_growth_phase2_ready`.

### Task 5: Docs, Ledger, And Final Validation

**Files:**
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `program.md`

- [ ] Update engineering docs with Phase 2 module ownership and preserved contract.
- [ ] Run final targeted validation:
  - `python -m pytest tests/test_procedural_planning.py tests/test_procedural_growth_phase2_audit.py -q`
  - `python -m pytest tests/test_companion_autonomy_runtime.py -k procedural -q`
  - `python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py -k procedural -q`
  - `python -m pytest tests/test_sandbox_execution_runtime.py tests/test_skill_runtime.py tests/test_tool_approval_policy.py tests/test_world_model_residue.py -q`
  - `python evals/run_procedural_growth_phase2_smokes.py --run-tag phase2-final`
  - `python evals/run_procedural_growth_phase2_audit.py --run-tag phase2-final`
- [ ] Run compile and hygiene:
  - `python -m py_compile amadeus_thread0/graph_parts/procedural_planning.py evals/run_procedural_growth_phase2_smokes.py evals/run_procedural_growth_phase2_audit.py`
  - `git diff --check -- amadeus_thread0/graph_parts/procedural_planning.py amadeus_thread0/graph_parts/autonomy_runtime.py amadeus_thread0/runtime/backend_api.py amadeus_thread0/runtime/backend_session.py amadeus_thread0/utils/turn_summary_export.py amadeus_thread0/utils/cli_views.py evals/run_procedural_growth_phase2_smokes.py evals/run_procedural_growth_phase2_audit.py tests/test_procedural_planning.py tests/test_procedural_growth_phase2_audit.py tests/test_companion_autonomy_runtime.py tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md docs/superpowers/specs/2026-05-06-procedural-growth-phase2-design.md docs/superpowers/plans/2026-05-06-procedural-growth-phase2.md`
- [ ] Update `program.md` with files changed, validations, result, and concrete next step.
