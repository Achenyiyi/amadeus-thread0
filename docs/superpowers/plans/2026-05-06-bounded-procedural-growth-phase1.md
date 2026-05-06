# Bounded Procedural Growth Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first bounded procedural-growth loop so completed embodied actions create reusable procedural traces, blocked actions remain boundary notes, and later backend/CLI readback can expose procedural hints without widening runtime authority.

**Architecture:** Add `amadeus_thread0.graph_parts.procedural_growth` as a pure graph-adjacent normalization/extraction layer over frozen final semantics. Then thread its outputs through existing final-state, backend summary, CLI, smoke, and audit surfaces while keeping persona core, skills registry truth, sandbox/browser authority, and unified memory boundaries intact.

**Tech Stack:** Python 3, pytest, existing LangGraph graph-parts, existing backend/session/final-state readback, existing eval report conventions.

---

## File Structure

- Create `amadeus_thread0/graph_parts/procedural_growth.py`
  - Owns procedural trace normalization, extraction from final action packets, consequence enrichment, carryover enrichment, and resurfacing hints.
- Modify `amadeus_thread0/runtime/final_state.py`
  - Resolves procedural growth from final/frozen surfaces and includes it in normalized digital-body consequence/carryover readback.
- Modify `amadeus_thread0/runtime/backend_api.py`
  - Adds compact `procedural_growth` payload readback for `assistant_turn` and `event_round`.
- Modify `amadeus_thread0/runtime/backend_session.py`
  - Adds compact `procedural_growth` view to session summaries where backend API gets summary values.
- Modify `amadeus_thread0/utils/turn_summary_export.py`
  - Summarizes procedural traces and hints.
- Modify `amadeus_thread0/utils/cli_views.py`
  - Renders a compact procedural hint line without treating it as execution authority.
- Create `tests/test_procedural_growth.py`
  - Pure trace normalization/extraction tests.
- Create `tests/test_procedural_growth_writeback.py`
  - Final-state/consequence/carryover writeback semantics tests.
- Create `tests/test_procedural_growth_retrieval.py`
  - Resurfacing hint tests.
- Create `tests/test_procedural_growth_audit.py`
  - Audit helper tests.
- Create `evals/run_procedural_growth_smokes.py`
  - Offline deterministic smoke scenarios.
- Create `evals/run_procedural_growth_audit.py`
  - Closure audit runner.
- Modify `docs/engineering/PROJECT_STRUCTURE.md`
  - Documents `procedural_growth.py` ownership.
- Modify `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
  - Adds the phase-1 preserved contract after closure.
- Modify `program.md`
  - Records plan, implementation, validation, and next step.

## Tasks

### Task 1: Procedural Trace Pure Functions

**Files:**
- Create: `tests/test_procedural_growth.py`
- Create: `amadeus_thread0/graph_parts/procedural_growth.py`

- [ ] Write failing tests for:
  - `normalize_procedural_trace`
  - `extract_procedural_traces_from_action_packets`
  - completed sandbox packet -> `sandbox_execution_pattern`
  - blocked sandbox packet -> `blocked_boundary_pattern`
  - pending/rejected packets produce no completed traces
  - skill usage packet -> `skill_usage_pattern`
  - browser manual takeover packet -> `browser_runtime_pattern` or `blocked_boundary_pattern`
- [ ] Run:
  - `python -m pytest tests/test_procedural_growth.py -q`
  - Expected before implementation: import failure or missing function failure.
- [ ] Implement minimal pure functions in `procedural_growth.py`.
- [ ] Run:
  - `python -m pytest tests/test_procedural_growth.py -q`
  - Expected after implementation: pass.

### Task 2: Final-State Writeback Semantics

**Files:**
- Create: `tests/test_procedural_growth_writeback.py`
- Modify: `amadeus_thread0/runtime/final_state.py`
- Modify: `amadeus_thread0/graph_parts/procedural_growth.py`

- [ ] Write failing tests proving:
  - completed traces enrich `digital_body_consequence.procedural_growth`
  - traces are mirrored into `procedural_continuity.traces`
  - interaction carryover can preserve `embodied_context.procedural_traces`
  - blocked packets do not become completed capability facts
  - frozen reconsolidation procedural growth wins over stale live intermediates
- [ ] Run:
  - `python -m pytest tests/test_procedural_growth_writeback.py -q`
  - Expected before implementation: missing resolver/enrichment behavior.
- [ ] Implement final-state enrichment helpers.
- [ ] Run:
  - `python -m pytest tests/test_procedural_growth.py tests/test_procedural_growth_writeback.py -q`
  - Expected after implementation: pass.

### Task 3: Procedural Retrieval Hints

**Files:**
- Create: `tests/test_procedural_growth_retrieval.py`
- Modify: `amadeus_thread0/graph_parts/procedural_growth.py`

- [ ] Write failing tests for:
  - `build_procedural_hint`
  - completed sandbox trace resurfaces as a hint with `must_request_approval=True`
  - blocked trace resurfaces as boundary note, not capability claim
  - low-confidence or empty traces do not surface
  - duplicate trace ids are deduped deterministically
- [ ] Run:
  - `python -m pytest tests/test_procedural_growth_retrieval.py -q`
  - Expected before implementation: missing function failure.
- [ ] Implement hint builder and trace list normalization.
- [ ] Run:
  - `python -m pytest tests/test_procedural_growth.py tests/test_procedural_growth_writeback.py tests/test_procedural_growth_retrieval.py -q`
  - Expected after implementation: pass.

### Task 4: Backend And CLI Readback

**Files:**
- Modify: `tests/test_backend_api.py`
- Modify: `tests/test_backend_session.py`
- Modify: `tests/test_cli_views.py`
- Modify: `amadeus_thread0/runtime/backend_api.py`
- Modify: `amadeus_thread0/runtime/backend_session.py`
- Modify: `amadeus_thread0/utils/turn_summary_export.py`
- Modify: `amadeus_thread0/utils/cli_views.py`

- [ ] Add focused failing tests using existing test style:
  - backend turn response includes `payload.procedural_growth`
  - backend event response includes same shape
  - session evolution summary includes `procedural_growth`
  - CLI compact summary includes `procedure:` only when a procedural hint exists
- [ ] Run:
  - `python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py -k procedural_growth -q`
  - Expected before implementation: missing fields.
- [ ] Implement readback in backend/session/summary/CLI surfaces.
- [ ] Run:
  - `python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py -k procedural_growth -q`
  - Expected after implementation: pass.

### Task 5: Smokes And Audit

**Files:**
- Create: `tests/test_procedural_growth_audit.py`
- Create: `evals/run_procedural_growth_smokes.py`
- Create: `evals/run_procedural_growth_audit.py`

- [ ] Write failing audit helper tests for:
  - smoke parser paths
  - readiness aggregation
  - markdown rendering
  - blocking failure ids
- [ ] Run:
  - `python -m pytest tests/test_procedural_growth_audit.py -q`
  - Expected before implementation: missing module failure.
- [ ] Implement deterministic smoke runner with five scenarios from the spec.
- [ ] Implement audit runner that requires:
  - smoke pass
  - procedural unit/writeback/retrieval tests pass
  - backend readback procedural tests pass
- [ ] Run:
  - `python -m pytest tests/test_procedural_growth_audit.py -q`
  - `python evals/run_procedural_growth_smokes.py --run-tag phase1-dev`
  - `python evals/run_procedural_growth_audit.py --run-tag phase1-dev`
  - Expected after implementation: pass, readiness may be `procedural_growth_phase1_ready` if all checks pass.

### Task 6: Docs, Ledger, And Final Validation

**Files:**
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `program.md`

- [ ] Update docs with `Bounded Procedural Growth Phase 1` implementation status and module ownership.
- [ ] Run targeted validation:
  - `python -m pytest tests/test_procedural_growth.py tests/test_procedural_growth_writeback.py tests/test_procedural_growth_retrieval.py tests/test_procedural_growth_audit.py -q`
  - `python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py -k procedural_growth -q`
  - `python -m pytest tests/test_sandbox_execution_runtime.py tests/test_skill_runtime.py tests/test_tool_approval_policy.py tests/test_world_model_residue.py -q`
  - `python evals/run_procedural_growth_smokes.py --run-tag phase1-final`
  - `python evals/run_procedural_growth_audit.py --run-tag phase1-final`
- [ ] Run doc/code hygiene:
  - `python -m py_compile amadeus_thread0/graph_parts/procedural_growth.py evals/run_procedural_growth_smokes.py evals/run_procedural_growth_audit.py`
  - `git diff --check -- amadeus_thread0/graph_parts/procedural_growth.py evals/run_procedural_growth_smokes.py evals/run_procedural_growth_audit.py tests/test_procedural_growth.py tests/test_procedural_growth_writeback.py tests/test_procedural_growth_retrieval.py tests/test_procedural_growth_audit.py docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md`
- [ ] Update `program.md` with files changed, validations, result, and concrete next step.
