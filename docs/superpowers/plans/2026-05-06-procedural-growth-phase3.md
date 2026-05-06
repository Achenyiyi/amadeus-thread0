# Procedural Growth Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add outcome-calibrated procedural learning so completed, failed, blocked, manual, and pending attempts can adjust procedural trace confidence without widening runtime authority.

**Architecture:** A new pure module `amadeus_thread0/graph_parts/procedural_outcome.py` normalizes outcomes, derives them from final action packets, and calibrates existing procedural traces. Existing final-state, backend, session, turn-summary, and CLI surfaces only expose readback and preserve the Phase 1/2 execution contract.

**Tech Stack:** Python 3, LangGraph-adjacent pure helpers, pytest, existing eval report runners.

---

## Files

- Create: `amadeus_thread0/graph_parts/procedural_outcome.py`
- Create: `tests/test_procedural_outcome.py`
- Create: `tests/test_procedural_growth_phase3_audit.py`
- Create: `evals/run_procedural_growth_phase3_smokes.py`
- Create: `evals/run_procedural_growth_phase3_audit.py`
- Modify: `amadeus_thread0/graph_parts/procedural_growth.py`
- Modify: `amadeus_thread0/graph_parts/procedural_planning.py`
- Modify: `amadeus_thread0/runtime/final_state.py`
- Modify: `amadeus_thread0/runtime/backend_api.py`
- Modify: `amadeus_thread0/runtime/backend_session.py`
- Modify: `amadeus_thread0/utils/turn_summary_export.py`
- Modify: `amadeus_thread0/utils/cli_views.py`
- Modify: `tests/test_procedural_planning.py`
- Modify: `tests/test_backend_api.py`
- Modify: `tests/test_backend_session.py`
- Modify: `tests/test_cli_views.py`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `program.md`

---

### Task 1: Outcome Helper TDD

**Files:**
- Create: `tests/test_procedural_outcome.py`
- Create: `amadeus_thread0/graph_parts/procedural_outcome.py`

- [ ] **Step 1: Write failing tests**

Write tests covering:

```python
from amadeus_thread0.graph_parts.procedural_outcome import (
    calibrate_procedural_traces_with_outcomes,
    derive_procedural_outcomes_from_action_packets,
    normalize_procedural_outcome,
)

def test_completed_sandbox_packet_derives_confirmed_success_outcome():
    outcomes = derive_procedural_outcomes_from_action_packets([...])
    assert outcomes[0]["outcome_kind"] == "confirmed_success"

def test_failed_sandbox_packet_derives_failed_execution_outcome():
    outcomes = derive_procedural_outcomes_from_action_packets([...])
    assert outcomes[0]["outcome_kind"] == "failed_execution"

def test_pending_packet_derives_no_executed_attempt_without_reuse():
    outcomes = derive_procedural_outcomes_from_action_packets([...])
    assert outcomes[0]["outcome_kind"] == "no_executed_attempt"

def test_manual_takeover_derives_manual_boundary_outcome():
    outcomes = derive_procedural_outcomes_from_action_packets([...])
    assert outcomes[0]["outcome_kind"] == "manual_takeover_required"

def test_calibration_adjusts_trace_confidence_and_preserves_boundary_notes():
    calibrated = calibrate_procedural_traces_with_outcomes([...], [...])
    assert calibrated[0]["confidence"] > 0.7
```

- [ ] **Step 2: Run red**

Run:

```powershell
python -m pytest tests/test_procedural_outcome.py -q
```

Expected: fail because `amadeus_thread0.graph_parts.procedural_outcome` does not exist.

- [ ] **Step 3: Implement helper**

Implement:

```python
ALLOWED_PROCEDURAL_OUTCOME_KINDS = {...}
ALLOWED_ATTEMPT_STATUSES = {...}
normalize_procedural_outcome(value)
derive_procedural_outcomes_from_action_packets(action_packets, planning_bias=None, traces=None)
calibrate_procedural_traces_with_outcomes(traces, outcomes)
summarize_procedural_outcomes(outcomes)
```

Use only pure dict/list normalization, stable SHA-1 ids, and existing action packet normalization.

- [ ] **Step 4: Run green**

Run:

```powershell
python -m pytest tests/test_procedural_outcome.py -q
```

Expected: all tests pass.

---

### Task 2: Final-State Trace Calibration

**Files:**
- Modify: `amadeus_thread0/graph_parts/procedural_growth.py`
- Modify: `amadeus_thread0/runtime/final_state.py`
- Modify: `tests/test_procedural_growth_writeback.py`

- [ ] **Step 1: Write failing writeback test**

Add a test asserting that a completed procedural-planning sandbox packet enriches `digital_body_consequence` with calibrated traces, `procedural_outcomes`, and `procedural_outcome_summary`.

- [ ] **Step 2: Run red**

Run:

```powershell
python -m pytest tests/test_procedural_growth_writeback.py -k outcome -q
```

Expected: fail because no outcome fields are exposed.

- [ ] **Step 3: Integrate enrichment**

Update `enrich_digital_body_consequence_with_procedural_growth(...)` to accept optional `procedural_planning`, derive outcomes from final packets, calibrate traces, and attach outcome summary fields. Update `final_state.resolve_digital_body_consequence(...)` to pass `reconsolidation_snapshot.procedural_planning` or live state when available.

- [ ] **Step 4: Run green**

Run:

```powershell
python -m pytest tests/test_procedural_growth_writeback.py -k outcome -q
```

Expected: outcome writeback tests pass.

---

### Task 3: Planning Ranking Uses Calibrated Outcomes

**Files:**
- Modify: `amadeus_thread0/graph_parts/procedural_planning.py`
- Modify: `tests/test_procedural_planning.py`

- [ ] **Step 1: Write failing planning test**

Add a test where two matching sandbox traces exist, the lower base-confidence trace has a confirmed success outcome and becomes the selected `sandbox_execute` bias.

- [ ] **Step 2: Run red**

Run:

```powershell
python -m pytest tests/test_procedural_planning.py -k outcome -q
```

Expected: fail because planning does not yet consult outcome calibration.

- [ ] **Step 3: Integrate ranking**

Update candidate trace collection to accept `procedural_outcomes` from embodied context, calibrate candidate traces before priority sorting, and keep boundary-reinforced outcomes from producing execution packets.

- [ ] **Step 4: Run green**

Run:

```powershell
python -m pytest tests/test_procedural_planning.py -k outcome -q
```

Expected: planning outcome tests pass.

---

### Task 4: Backend, Session, Turn Summary, CLI Readback

**Files:**
- Modify: `amadeus_thread0/runtime/backend_api.py`
- Modify: `amadeus_thread0/runtime/backend_session.py`
- Modify: `amadeus_thread0/utils/turn_summary_export.py`
- Modify: `amadeus_thread0/utils/cli_views.py`
- Modify: `tests/test_backend_api.py`
- Modify: `tests/test_backend_session.py`
- Modify: `tests/test_cli_views.py`

- [ ] **Step 1: Write failing readback tests**

Add tests asserting:

```python
payload["procedural_outcome"]["last_outcome_kind"] == "confirmed_success"
payload["turn_summary"]["current_turn"]["procedural_outcome"]["source_run_id"] == "run-..."
summary["current_turn"]["procedural_outcome"]["outcome_kind"] == "confirmed_success"
"outcome=confirmed_success:run-...:reuse" in line
```

- [ ] **Step 2: Run red**

Run:

```powershell
python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py -k procedural_outcome -q
```

Expected: fail because readback surfaces are missing.

- [ ] **Step 3: Add readback only**

Expose `procedural_outcome`/`procedural_outcomes` summaries from normalized digital body consequence. Do not add new execution behavior.

- [ ] **Step 4: Run green**

Run:

```powershell
python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py -k procedural_outcome -q
```

Expected: backend/session/CLI readback tests pass.

---

### Task 5: Smokes and Audit

**Files:**
- Create: `evals/run_procedural_growth_phase3_smokes.py`
- Create: `evals/run_procedural_growth_phase3_audit.py`
- Create: `tests/test_procedural_growth_phase3_audit.py`

- [ ] **Step 1: Write failing audit tests**

Add tests for phase-3 smoke scenarios, audit check ids, readiness aggregation, and markdown rendering.

- [ ] **Step 2: Run red**

Run:

```powershell
python -m pytest tests/test_procedural_growth_phase3_audit.py -q
```

Expected: fail because eval runners do not exist.

- [ ] **Step 3: Implement smokes and audit**

Use the Phase 2 audit runner structure with phase-3 names and readiness `procedural_growth_phase3_ready`. Smoke scenarios must cover success boost, failed execution, manual takeover, and pending/no fact.

- [ ] **Step 4: Run green**

Run:

```powershell
python -m pytest tests/test_procedural_growth_phase3_audit.py -q
```

Expected: audit tests pass.

---

### Task 6: Docs and Final Verification

**Files:**
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `program.md`

- [ ] **Step 1: Update docs**

Document `procedural_outcome.py`, the phase-3 contract, and the audit gate.

- [ ] **Step 2: Run final validation**

Run:

```powershell
python -m pytest tests/test_procedural_outcome.py tests/test_procedural_planning.py tests/test_procedural_growth_phase3_audit.py -q
python -m pytest tests/test_companion_autonomy_runtime.py -k procedural -q
python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py -k procedural -q
python -m pytest tests/test_sandbox_execution_runtime.py tests/test_skill_runtime.py tests/test_tool_approval_policy.py tests/test_world_model_residue.py -q
python evals/run_procedural_growth_phase3_smokes.py --run-tag phase3-final
python evals/run_procedural_growth_phase3_audit.py --run-tag phase3-final
python -m py_compile amadeus_thread0/graph_parts/procedural_outcome.py evals/run_procedural_growth_phase3_smokes.py evals/run_procedural_growth_phase3_audit.py
git diff --check -- amadeus_thread0/graph_parts/procedural_outcome.py amadeus_thread0/graph_parts/procedural_growth.py amadeus_thread0/graph_parts/procedural_planning.py amadeus_thread0/runtime/final_state.py amadeus_thread0/runtime/backend_api.py amadeus_thread0/runtime/backend_session.py amadeus_thread0/utils/turn_summary_export.py amadeus_thread0/utils/cli_views.py evals/run_procedural_growth_phase3_smokes.py evals/run_procedural_growth_phase3_audit.py tests/test_procedural_outcome.py tests/test_procedural_growth_phase3_audit.py tests/test_procedural_planning.py tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md
```

- [ ] **Step 3: Update program.md**

Record focus, files changed, validation commands, results, and next step.
