# Dynamic Skill Candidate Runtime Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close `dynamic_skill_candidate_runtime` as a backend-owned runtime readback gate over frozen dynamic skill candidates, approved installs, and session activation evidence.

**Architecture:** Add a pure readback module that consumes existing backend payload fields (`skills`, `autonomy`, `action_packets`, and `digital_body_consequence`) and emits `dynamic_skill_candidate_runtime.v1`. The readback is attached to real `assistant_turn` and `event_round` payloads and mirrored compactly into `skills` and `operator_readback`; it never installs skills or writes the registry. Dashboard and preserved-baseline audits then move the lane from `fresh_spec_required` to a closed `phase1_ready` gate.

**Tech Stack:** Python 3, existing backend.v1 payload builders, existing dynamic skill candidate helpers, pytest, deterministic eval scripts.

---

## File Structure

- `amadeus_thread0/runtime/dynamic_skill_candidate_runtime.py`: create a pure readback/audit helper for dynamic skill candidate lifecycle evidence.
- `amadeus_thread0/runtime/backend_api.py`: attach the readback to `assistant_turn` and `event_round` payloads after `skills` and `autonomy` are materialized.
- `amadeus_thread0/runtime/runtime_status_dashboard.py`: mark dynamic skill candidate runtime closed and remove the stale next spec.
- `evals/run_dynamic_skill_candidate_runtime_audit.py`: deterministic audit scenarios for pending, blocked, approved-install, active-session, and completed-use continuity evidence.
- `evals/run_preserved_baselines_audit.py`: add the new preserved baseline row.
- `tests/test_dynamic_skill_candidate_runtime.py`: RED/GREEN coverage for the pure runtime readback.
- `tests/test_dynamic_skill_candidate_runtime_audit.py`: audit readiness coverage.
- `tests/test_backend_api.py`: prove real backend payloads include the readback.
- `tests/test_runtime_status_dashboard.py`: prove dashboard next spec count closes.
- `tests/test_preserved_baselines_audit.py`: prove the new baseline is preserved.
- Docs/status: `AGENTS.md`, `program.md`, `docs/engineering/PROJECT_STRUCTURE.md`, `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`, `docs/engineering/BACKEND_HANDOFF.md`.

---

### Task 1: Runtime Readback RED Tests

**Files:**
- Create: `tests/test_dynamic_skill_candidate_runtime.py`

- [ ] **Step 1: Write failing tests**

Add tests that build frozen candidates with `propose_skill_candidate_from_trace()` and `freeze_skill_candidate_payload()`, then assert:

- a pending `install_skill` packet is visible as `candidate_state="pending_approval"`;
- pending candidates never report `registry_written=True` or `active_after_install=True`;
- blocked or rejected candidate packets stay non-active and non-writeback;
- approved completed install packets report approved install evidence only when the dynamic skill appears in installed/active session readback;
- completed skill use can be surfaced as procedural continuity evidence while install/proposal alone does not become memory writeback.

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_dynamic_skill_candidate_runtime.py -q
```

Expected: FAIL because `amadeus_thread0.runtime.dynamic_skill_candidate_runtime` does not exist.

---

### Task 2: Runtime Readback Implementation

**Files:**
- Create: `amadeus_thread0/runtime/dynamic_skill_candidate_runtime.py`

- [ ] **Step 1: Implement pure readback**

Implement:

```python
build_dynamic_skill_candidate_runtime_readback(turn: dict[str, Any] | None) -> dict[str, Any]
apply_dynamic_skill_candidate_runtime_to_payload(payload: dict[str, Any] | None) -> dict[str, Any]
compact_dynamic_skill_candidate_runtime_line(readback: dict[str, Any] | None) -> str
```

The readback must emit:

- `schema="dynamic_skill_candidate_runtime.v1"`;
- `readiness_status="dynamic_skill_candidate_runtime_phase1_ready"` when dynamic candidate evidence is safe;
- `readiness_status="dynamic_skill_candidate_runtime_phase1_not_applicable"` when no candidate evidence exists;
- `readiness_status="dynamic_skill_candidate_runtime_phase1_in_progress"` when candidate evidence is unsafe, drifted, or incomplete;
- `authority_boundary` showing no auto registry write, no memory write, no persona mutation, no model API call, and no live capture.

- [ ] **Step 2: Run GREEN**

Run:

```powershell
python -m pytest tests/test_dynamic_skill_candidate_runtime.py -q
```

Expected: PASS.

---

### Task 3: Backend Payload Integration

**Files:**
- Modify: `amadeus_thread0/runtime/backend_api.py`
- Modify: `tests/test_backend_api.py`

- [ ] **Step 1: Write failing backend test**

Add a test that calls both `BackendAPI.build_turn_response()` and `BackendAPI.build_event_round_response()` with a pending dynamic candidate install packet and asserts:

- top-level `dynamic_skill_candidate_runtime` exists;
- `skills.dynamic_candidate_runtime` mirrors a compact readback;
- `operator_readback.dynamic_skill_candidate_runtime` mirrors the same compact readback;
- both payload kinds preserve `requires_approval=True` and `registry_written=False`.

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_backend_api.py -k dynamic_skill_candidate_runtime -q
```

Expected: FAIL until backend integration is added.

- [ ] **Step 3: Integrate readback**

Import `apply_dynamic_skill_candidate_runtime_to_payload()` in `backend_api.py` and call it for both turn and event payloads after the payload dict is assembled and before `apply_embodied_interaction_readback_to_payload()`.

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_backend_api.py -k dynamic_skill_candidate_runtime -q
```

Expected: PASS.

---

### Task 4: Audit, Dashboard, And Preserved Baseline

**Files:**
- Create: `evals/run_dynamic_skill_candidate_runtime_audit.py`
- Create: `tests/test_dynamic_skill_candidate_runtime_audit.py`
- Modify: `amadeus_thread0/runtime/runtime_status_dashboard.py`
- Modify: `evals/run_preserved_baselines_audit.py`
- Modify: `tests/test_runtime_status_dashboard.py`
- Modify: `tests/test_preserved_baselines_audit.py`

- [ ] **Step 1: Write failing tests**

Add audit and dashboard tests that expect:

- audit readiness `dynamic_skill_candidate_runtime_phase1_ready`;
- dashboard `NEXT_SPECS == []`;
- dashboard lane `dynamic_skill_generation.status == "phase1_ready"`;
- preserved-baseline id `dynamic_skill_candidate_runtime_phase1`;
- skills category count increases to `3`.

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_dynamic_skill_candidate_runtime_audit.py tests/test_runtime_status_dashboard.py tests/test_preserved_baselines_audit.py -q
```

Expected: FAIL.

- [ ] **Step 3: Implement audit and status wiring**

Create deterministic scenarios:

- `pending_candidate_visible_without_activation`;
- `blocked_candidate_not_written`;
- `approved_install_visible_after_registry_evidence`;
- `manual_disable_keeps_dynamic_skill_inactive`;
- `completed_use_only_continuity`;
- `authority_boundary_not_widened`.

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_dynamic_skill_candidate_runtime_audit.py tests/test_runtime_status_dashboard.py tests/test_preserved_baselines_audit.py -q
python evals/run_dynamic_skill_candidate_runtime_audit.py --run-tag phase1-dev
```

Expected: PASS and readiness `dynamic_skill_candidate_runtime_phase1_ready`.

---

### Task 5: Docs, Verification, Merge

**Files:**
- Modify: `AGENTS.md`
- Modify: `program.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `docs/engineering/BACKEND_HANDOFF.md`

- [ ] **Step 1: Update docs**

Record `dynamic_skill_candidate_runtime_phase1_ready` as a preserved backend gate. State explicitly that the phase is readback/audit-only and does not auto-write the registry, mutate persona core, write autobiographical memory, widen sandbox/browser/tool authority, call model APIs, or create frontend-owned semantics.

- [ ] **Step 2: Run verification**

Run:

```powershell
python -m pytest tests/test_dynamic_skill_candidate_runtime.py tests/test_dynamic_skill_candidate_runtime_audit.py tests/test_dynamic_skill_candidates.py tests/test_dynamic_skills_phase2.py tests/test_skill_registry.py tests/test_skill_runtime.py tests/test_backend_api.py tests/test_runtime_status_dashboard.py tests/test_preserved_baselines_audit.py -q
python -m py_compile amadeus_thread0/runtime/dynamic_skill_candidate_runtime.py amadeus_thread0/runtime/backend_api.py amadeus_thread0/runtime/runtime_status_dashboard.py evals/run_dynamic_skill_candidate_runtime_audit.py evals/run_preserved_baselines_audit.py
python evals/run_dynamic_skill_candidate_runtime_audit.py --run-tag phase1-final
python evals/run_dynamic_skills_phase2_audit.py --run-tag candidate-runtime-regression
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
git diff --check
```

Expected: all commands exit `0`.

- [ ] **Step 3: Commit, merge, push**

Commit the feature branch, fast-forward merge into `main`, rerun post-merge audit, push `main`, then clean up the worktree.
