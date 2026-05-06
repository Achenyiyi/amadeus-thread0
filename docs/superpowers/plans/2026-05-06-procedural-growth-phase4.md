# Procedural Growth Phase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add recovery-oriented procedural adaptation that converts failed, blocked, manual-takeover, and stale outcomes into safe advisory recovery readback.

**Architecture:** Add a pure `procedural_recovery.py` helper under `graph_parts`, then thread its normalized recovery summary through digital-body consequence normalization, backend envelopes, session summaries, CLI compact output, deterministic smokes, and an audit runner. Planning remains conservative: unresolved failed or boundary recovery cannot produce a new execution-producing packet.

**Tech Stack:** Python, pytest, existing backend readback helpers, existing eval report pattern.

---

### Task 1: Recovery Helper TDD

**Files:**
- Create: `amadeus_thread0/graph_parts/procedural_recovery.py`
- Create: `tests/test_procedural_recovery.py`

- [ ] **Step 1: Write failing tests**

Create tests for:

```python
def test_failed_execution_outcome_builds_failure_artifact_recovery():
    recoveries = derive_procedural_recoveries_from_outcomes([failed_execution_outcome])
    assert recoveries[0]["recovery_kind"] == "inspect_failure_artifact"
    assert recoveries[0]["allowed_bias_kind"] == "workspace_guidance"
    assert recoveries[0]["safe_to_reuse"] is False
    assert recoveries[0]["requires_approval"] is False
```

Also cover blocked boundary, manual takeover, stale context, no executed attempt, normalization, summary, and trace recovery marker application.

- [ ] **Step 2: Run red**

Run: `python -m pytest tests/test_procedural_recovery.py -q`

Expected: fail with missing `amadeus_thread0.graph_parts.procedural_recovery`.

- [ ] **Step 3: Implement helper**

Implement:

- `normalize_procedural_recovery()`
- `normalize_procedural_recoveries()`
- `derive_procedural_recoveries_from_outcomes()`
- `summarize_procedural_recoveries()`
- `apply_recovery_markers_to_traces()`

- [ ] **Step 4: Run green**

Run: `python -m pytest tests/test_procedural_recovery.py -q`

Expected: all recovery helper tests pass.

### Task 2: Consequence And Planning Integration

**Files:**
- Modify: `amadeus_thread0/graph_parts/procedural_growth.py`
- Modify: `amadeus_thread0/graph_parts/procedural_planning.py`
- Modify: `amadeus_thread0/graph_parts/digital_body_runtime.py`
- Modify: `tests/test_procedural_growth_writeback.py`
- Modify: `tests/test_procedural_planning.py`

- [ ] **Step 1: Write failing integration tests**

Add tests asserting:

- failed sandbox outcomes attach `procedural_recoveries` and `procedural_recovery_summary`
- failed recovery markers prevent direct `sandbox_execute` planning reuse
- blocked recovery stays `boundary_only`

- [ ] **Step 2: Run red**

Run: `python -m pytest tests/test_procedural_growth_writeback.py -k recovery -q`

Expected: fail because consequence lacks recovery readback.

Run: `python -m pytest tests/test_procedural_planning.py -k recovery -q`

Expected: fail because planning ignores recovery markers.

- [ ] **Step 3: Implement integration**

Attach recoveries in `enrich_digital_body_consequence_with_procedural_growth()`, normalize them in `normalize_embodied_context()`, and mark traces with `recovery_kind`, `recovery_required`, `recovery_allowed_bias_kind`, and `recovery_refs`.

- [ ] **Step 4: Run green**

Run: `python -m pytest tests/test_procedural_recovery.py tests/test_procedural_growth_writeback.py tests/test_procedural_planning.py -q`

Expected: all selected tests pass.

### Task 3: Backend, Session, And CLI Readback

**Files:**
- Modify: `amadeus_thread0/utils/turn_summary_export.py`
- Modify: `amadeus_thread0/utils/cli_views.py`
- Modify: `amadeus_thread0/runtime/backend_api.py`
- Modify: `tests/test_backend_api.py`
- Modify: `tests/test_backend_session.py`
- Modify: `tests/test_cli_views.py`

- [ ] **Step 1: Write failing readback tests**

Add tests asserting:

- backend event and turn payloads include top-level `procedural_recovery`
- `turn_summary.current_turn.procedural_recovery` includes latest recovery kind and run id
- CLI line includes `recovery=inspect_failure_artifact:<run_id>:hint`

- [ ] **Step 2: Run red**

Run: `python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py -k procedural_recovery -q`

Expected: fail because readback does not yet expose recovery.

- [ ] **Step 3: Implement readback**

Add `summarize_procedural_recovery()` and thread it through backend API summary enrichment and CLI current-turn/compact output.

- [ ] **Step 4: Run green**

Run: `python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py -k procedural -q`

Expected: procedural readback tests pass.

### Task 4: Smokes, Audit, And Documentation

**Files:**
- Create: `evals/run_procedural_growth_phase4_smokes.py`
- Create: `evals/run_procedural_growth_phase4_audit.py`
- Create: `tests/test_procedural_growth_phase4_audit.py`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `program.md`

- [ ] **Step 1: Write failing audit tests**

Add tests checking smoke scenario coverage, audit check ids, readiness aggregation, markdown rendering, and smoke stdout parsing.

- [ ] **Step 2: Run red**

Run: `python -m pytest tests/test_procedural_growth_phase4_audit.py -q`

Expected: fail with missing Phase 4 eval modules.

- [ ] **Step 3: Implement smokes and audit**

Follow the Phase 3 eval style and report `procedural_growth_phase4_ready` only when all blocking checks pass.

- [ ] **Step 4: Run final verification**

Run:

```powershell
python -m pytest tests/test_procedural_recovery.py tests/test_procedural_planning.py tests/test_procedural_growth_writeback.py tests/test_procedural_growth_phase4_audit.py -q
python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py -k procedural -q
python -m pytest tests/test_companion_autonomy_runtime.py -k procedural -q
python -m pytest tests/test_sandbox_execution_runtime.py tests/test_skill_runtime.py tests/test_tool_approval_policy.py tests/test_world_model_residue.py -q
python evals/run_procedural_growth_phase4_smokes.py --run-tag phase4-final
python evals/run_procedural_growth_phase4_audit.py --run-tag phase4-final
python -m py_compile amadeus_thread0/graph_parts/procedural_recovery.py evals/run_procedural_growth_phase4_smokes.py evals/run_procedural_growth_phase4_audit.py
```

Expected: tests pass, smokes pass, audit reports `procedural_growth_phase4_ready`, py_compile exits 0.
