# Runtime Productization Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a product-runtime integration hardening gate that makes the current project state, route-envelope consumption, blocked lanes, and next-spec lanes auditable without reopening old closeout gates.

**Architecture:** Add a pure `runtime_status_dashboard.v1` readback module, a deterministic product-runtime smoke runner, and a Phase 3 audit runner. Keep Phase 3 readback/smoke/audit-only: no HTTP server ownership, no runtime authority widening, no frontend-owned semantics, and no automatic multimodal/skill/executor enablement.

**Tech Stack:** Python 3, pytest, existing `BackendTransportAdapter`, existing eval report conventions under ignored `evals/reports/`, Markdown engineering docs.

---

## File Structure

- Create: `amadeus_thread0/runtime/runtime_status_dashboard.py`
  - Pure dashboard builder for preserved gates, source-report availability, blocked lanes, and next-spec lanes.
- Create: `evals/run_runtime_productization_phase3_smokes.py`
  - Deterministic smoke runner over `BackendTransportAdapter` and backend-owned envelopes.
- Create: `evals/run_runtime_productization_phase3_audit.py`
  - Phase 3 audit aggregator over preserved baselines, post-unlock roadmap, Phase 2 productization, Phase 3 smokes, and dashboard status.
- Modify: `evals/run_preserved_baselines_audit.py`
  - Register `runtime_productization_phase3_ready` as a preserved productization gate.
- Create tests:
  - `tests/test_runtime_status_dashboard.py`
  - `tests/test_runtime_productization_phase3_smokes.py`
  - `tests/test_runtime_productization_phase3_audit.py`
- Modify tests:
  - `tests/test_preserved_baselines_audit.py`
- Modify docs:
  - `AGENTS.md`
  - `program.md`
  - `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
  - `docs/engineering/PROJECT_STRUCTURE.md`
  - `docs/engineering/BACKEND_HANDOFF.md`
  - `docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md`

---

### Task 1: Runtime Status Dashboard

**Files:**
- Create: `amadeus_thread0/runtime/runtime_status_dashboard.py`
- Test: `tests/test_runtime_status_dashboard.py`

- [x] **Step 1: Write failing tests**

Cover:

- ready preserved/productization gates produce `runtime_status_dashboard_ready`
- missing gitignored source reports produce `runtime_status_dashboard_attention_required`
- blocked lanes and next-spec lanes are visible
- compact status line is short and explicit

- [x] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_runtime_status_dashboard.py -q
```

Expected: fails with `ModuleNotFoundError` for `amadeus_thread0.runtime.runtime_status_dashboard`.

- [x] **Step 3: Implement dashboard**

Implement:

- `build_runtime_status_dashboard(...)`
- `compact_runtime_status_line(...)`
- constants for expected gates, blocked lanes, and next specs

- [x] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_runtime_status_dashboard.py -q
```

Expected: pass.

---

### Task 2: Product Runtime Phase 3 Smokes

**Files:**
- Create: `evals/run_runtime_productization_phase3_smokes.py`
- Test: `tests/test_runtime_productization_phase3_smokes.py`

- [x] **Step 1: Write failing smoke test**

Cover:

- `GET /api/runtime-productization`
- `POST /api/turns/finalize`
- `POST /api/event-rounds/finalize`
- frontend-consumer boundary stays read-only

- [x] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_runtime_productization_phase3_smokes.py -q
```

Expected: fails with `ModuleNotFoundError` for `evals.run_runtime_productization_phase3_smokes`.

- [x] **Step 3: Implement deterministic smoke runner**

Use a fake `BackendAPI` that returns `BackendApiEnvelope` objects and run through the real `BackendTransportAdapter`.

- [x] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_runtime_productization_phase3_smokes.py -q
```

Expected: pass.

---

### Task 3: Productization Phase 3 Audit

**Files:**
- Create: `evals/run_runtime_productization_phase3_audit.py`
- Test: `tests/test_runtime_productization_phase3_audit.py`

- [x] **Step 1: Write failing audit tests**

Cover:

- Phase 3 passes when preserved baselines, post-unlock roadmap, Phase 2 productization, and Phase 3 smokes are ready
- Phase 3 fails honestly when preserved source reports are missing
- authority boundaries stay closed

- [x] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_runtime_productization_phase3_audit.py -q
```

Expected: fails with `ModuleNotFoundError` for `evals.run_runtime_productization_phase3_audit`.

- [x] **Step 3: Implement audit runner**

Implement:

- report loading from `evals/reports`
- pure `evaluate_runtime_productization_phase3_audit(...)`
- JSON/Markdown report writing
- `runtime_productization_phase3_ready` readiness

- [x] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_runtime_productization_phase3_audit.py -q
```

Expected: pass.

---

### Task 4: Preserved Baseline Registration

**Files:**
- Modify: `evals/run_preserved_baselines_audit.py`
- Modify: `tests/test_preserved_baselines_audit.py`

- [x] **Step 1: Write failing tests**

Add `runtime_productization_phase3` to the expected preserved backend chain and productization category count.

- [x] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_preserved_baselines_audit.py -q
```

Expected: fails because the meta-gate does not know `runtime_productization_phase3`.

- [x] **Step 3: Register the baseline**

Add:

- id: `runtime_productization_phase3`
- prefix: `runtime-productization-phase3-audit-`
- expected readiness: `runtime_productization_phase3_ready`
- category: `productization`

- [x] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_preserved_baselines_audit.py -q
```

Expected: pass.

---

### Task 5: Documentation And Handoff

**Files:**
- Modify: `AGENTS.md`
- Modify: `program.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/BACKEND_HANDOFF.md`
- Modify: `docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md`

- [x] **Step 1: Update project state docs**

Document `Runtime Productization Phase 3` as readback/smoke/audit-only and explicitly preserve blocked surfaces.

- [x] **Step 2: Update handoff docs**

Document `runtime_status_dashboard.v1` and Phase 3 product runtime smokes as operator/product clarity layers, not frontend-owned state or HTTP server semantics.

- [x] **Step 3: Update plan**

Save this implementation plan at:

```text
docs/superpowers/plans/2026-05-07-runtime-productization-phase3.md
```

---

### Task 6: Verification And Merge

**Files:**
- Generated ignored reports under `evals/reports/`

- [x] **Step 1: Run focused tests**

```powershell
python -m pytest tests/test_runtime_status_dashboard.py tests/test_runtime_productization_phase3_smokes.py tests/test_runtime_productization_phase3_audit.py tests/test_preserved_baselines_audit.py tests/test_runtime_productization.py tests/test_transport_adapter.py tests/test_frontend_runtime_shell_phase2.py -q
```

- [x] **Step 2: Run phase reports**

```powershell
python evals/run_runtime_productization_phase3_smokes.py --reports-dir evals/reports
python evals/run_runtime_productization_phase3_audit.py --reports-dir "E:\桌面\amadeus-thread0\evals\reports"
python evals/run_preserved_baselines_audit.py --reports-dir "E:\桌面\amadeus-thread0\evals\reports"
```

- [x] **Step 3: Run compile check**

```powershell
python -m py_compile amadeus_thread0/runtime/runtime_status_dashboard.py evals/run_runtime_productization_phase3_smokes.py evals/run_runtime_productization_phase3_audit.py evals/run_preserved_baselines_audit.py
```

- [x] **Step 4: Commit, merge to main, and push**

```powershell
git status --short
git add AGENTS.md program.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/BACKEND_HANDOFF.md docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md docs/superpowers/plans/2026-05-07-runtime-productization-phase3.md amadeus_thread0/runtime/runtime_status_dashboard.py evals/run_runtime_productization_phase3_smokes.py evals/run_runtime_productization_phase3_audit.py evals/run_preserved_baselines_audit.py tests/test_runtime_status_dashboard.py tests/test_runtime_productization_phase3_smokes.py tests/test_runtime_productization_phase3_audit.py tests/test_preserved_baselines_audit.py
git commit -m "feat: close runtime productization phase 3"
git checkout main
git merge --ff-only codex/runtime-productization-phase3
git push origin main
```
