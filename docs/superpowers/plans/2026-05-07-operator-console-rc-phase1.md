# Operator Console RC Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only `operator_console_rc.v1` release-candidate console packet over existing Technical Preview RC evidence and expose it through backend routes and frontend readback rendering.

**Architecture:** Add a focused backend aggregator that consumes existing RC/dashboard/operator-readback payloads and fails closed on evidence regression, open next specs, or widened authority. Expose it through existing `BackendAPI` and `BackendTransportAdapter` envelopes, then let the frontend render the route result as a read-only backend-owned record.

**Tech Stack:** Python 3.12 style modules, pytest, existing `backend.v1` envelope/transport adapter, React/Vite TypeScript static frontend contract tests, deterministic `evals/` audit scripts.

---

## File Structure

- Create `amadeus_thread0/runtime/operator_console_rc.py`: backend read-only console aggregation and compact line helper.
- Create `tests/test_operator_console_rc.py`: unit tests for ready/blocked aggregation behavior.
- Create `evals/run_operator_console_rc_phase1_audit.py`: deterministic audit runner and Markdown report renderer.
- Create `tests/test_operator_console_rc_audit.py`: audit tests.
- Modify `amadeus_thread0/runtime/backend_api.py`: add `operator_console_rc()` envelope method.
- Modify `amadeus_thread0/runtime/transport_adapter.py`: add `GET /api/operator-console-rc`.
- Modify `tests/test_transport_adapter.py`, `tests/test_http_transport.py`: route coverage.
- Modify `frontend/src/contracts/backend.ts` and `docs/engineering/frontend_contract/backend_api.types.ts`: add `operator_console_rc` kind/payload type.
- Modify `frontend/src/data/mockBackend.ts`, `frontend/src/runtime/backendClient.ts`, `frontend/src/App.tsx`: route consumption and read-only rendering.
- Modify `tests/test_frontend_runtime_shell_phase2.py`: static frontend assertions.
- Modify docs/status ledgers listed in the design spec.

---

### Task 1: Backend Aggregator

**Files:**
- Create: `amadeus_thread0/runtime/operator_console_rc.py`
- Test: `tests/test_operator_console_rc.py`

- [x] **Step 1: Write failing tests**

Add tests that import `build_operator_console_rc_readback`, `compact_operator_console_rc_line`, and `OPERATOR_CONSOLE_RC_PHASE1_READY`. Cover ready evidence, next-spec blocking, authority widening, and compact line output.

- [x] **Step 2: Run tests to verify RED**

Run: `python -m pytest tests/test_operator_console_rc.py -q`

Expected: fail with `ModuleNotFoundError` for `amadeus_thread0.runtime.operator_console_rc`.

- [x] **Step 3: Implement minimal aggregator**

Implement:

- `OPERATOR_CONSOLE_RC_PHASE1_READY = "operator_console_rc_phase1_ready"`
- `OPERATOR_CONSOLE_RC_PHASE1_BLOCKED = "operator_console_rc_phase1_blocked"`
- `build_operator_console_rc_readback(...)`
- `compact_operator_console_rc_line(...)`

The ready path requires:

- technical preview RC overall passed and `technical_preview_rc_phase1_ready`;
- runtime dashboard overall passed and `runtime_status_dashboard_ready`;
- operator readback overall passed and `runtime_productization_phase2_ready`;
- `next_spec_count == 0`;
- blocked authority booleans remain false.

- [x] **Step 4: Run tests to verify GREEN**

Run: `python -m pytest tests/test_operator_console_rc.py -q`

Expected: all tests pass.

---

### Task 2: Audit Runner

**Files:**
- Create: `evals/run_operator_console_rc_phase1_audit.py`
- Test: `tests/test_operator_console_rc_audit.py`

- [x] **Step 1: Write failing audit tests**

Add tests for `evaluate_operator_console_rc_phase1_audit(...)` and `render_markdown(...)`.

- [x] **Step 2: Run tests to verify RED**

Run: `python -m pytest tests/test_operator_console_rc_audit.py -q`

Expected: fail with `ModuleNotFoundError` for `evals.run_operator_console_rc_phase1_audit`.

- [x] **Step 3: Implement audit runner**

The runner loads or accepts Technical Preview RC evidence, builds the operator console packet, emits JSON/Markdown, and returns exit code `0` only when `overall_status == "passed"`.

- [x] **Step 4: Run tests to verify GREEN**

Run: `python -m pytest tests/test_operator_console_rc_audit.py tests/test_operator_console_rc.py -q`

Expected: all tests pass.

---

### Task 3: Backend API And Route

**Files:**
- Modify: `amadeus_thread0/runtime/backend_api.py`
- Modify: `amadeus_thread0/runtime/transport_adapter.py`
- Modify: `tests/test_transport_adapter.py`
- Modify: `tests/test_http_transport.py`

- [x] **Step 1: Write failing route tests**

Add tests proving `GET /api/operator-console-rc` returns a `backend.v1` envelope with kind `operator_console_rc`.

- [x] **Step 2: Run tests to verify RED**

Run: `python -m pytest tests/test_transport_adapter.py tests/test_http_transport.py -q`

Expected: fail because `/api/operator-console-rc` is not routed or fake APIs do not expose the method.

- [x] **Step 3: Implement BackendAPI and route**

Add:

- `BackendAPI.operator_console_rc()`;
- `_ROUTES["/api/operator-console-rc"] = ("GET", _read_route("operator_console_rc"))`.

The API method should compose existing `_runtime_productization_payload`, an embedded ready runtime dashboard, and technical-preview RC evidence into `operator_console_rc.v1`.

- [x] **Step 4: Run tests to verify GREEN**

Run: `python -m pytest tests/test_transport_adapter.py tests/test_http_transport.py tests/test_operator_console_rc.py -q`

Expected: all tests pass.

---

### Task 4: Frontend Contract And Read-Only Rendering

**Files:**
- Modify: `frontend/src/contracts/backend.ts`
- Modify: `docs/engineering/frontend_contract/backend_api.types.ts`
- Modify: `frontend/src/data/mockBackend.ts`
- Modify: `frontend/src/runtime/backendClient.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `tests/test_frontend_runtime_shell_phase2.py`

- [x] **Step 1: Write failing frontend static assertions**

Assert the contract includes `operator_console_rc`, the route client requests `/api/operator-console-rc`, and the UI renders `Operator console RC`.

- [x] **Step 2: Run tests to verify RED**

Run: `python -m pytest tests/test_frontend_runtime_shell_phase2.py tests/test_frontend_contract_sync.py -q`

Expected: fail because the frontend contract and UI do not yet include the new console route.

- [x] **Step 3: Implement frontend route consumption**

Add the new backend kind and payload type, request the route through `RouteBackendClient`, carry the envelope in `RuntimeSession`, and render it as a read-only record in the existing inspector area.

- [x] **Step 4: Run tests and build**

Run:

- `python -m pytest tests/test_frontend_runtime_shell_phase2.py tests/test_frontend_contract_sync.py -q`
- `npm run build` from `frontend/`

Expected: pytest and TypeScript/Vite build pass.

---

### Task 5: Documentation And Ledger Updates

**Files:**
- Modify: `AGENTS.md`
- Modify: `program.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/BACKEND_HANDOFF.md`
- Modify: `docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md`
- Modify: `docs/FINAL_DELIVERY_MANIFEST.md`
- Modify: `docs/TECHNICAL_PREVIEW_CHECKLIST.md`
- Modify: `docs/ADVISOR_REPRO_RUNBOOK.md`
- Modify: `docs/superpowers/plans/2026-05-07-operator-console-rc-phase1.md`

- [x] **Step 1: Update docs**

Document `operator_console_rc_phase1_ready` as a read-only operator-console RC gate over existing Technical Preview RC evidence.

- [x] **Step 2: Run doc/static checks**

Run: `rg -n "operator_console_rc|operator-console-rc|Operator Console RC" AGENTS.md program.md docs`

Expected: new status and route are documented across handoff, manifest, checklist, runbook, and structure docs.

---

### Task 6: Final Verification And Commit

**Files:**
- All changed files.

- [x] **Step 1: Run focused Python verification**

Run:

`python -m pytest tests/test_operator_console_rc.py tests/test_operator_console_rc_audit.py tests/test_transport_adapter.py tests/test_http_transport.py tests/test_frontend_runtime_shell_phase2.py tests/test_frontend_contract_sync.py tests/test_technical_preview_rc.py tests/test_technical_preview_rc_audit.py -q`

Expected: all selected tests pass.

- [x] **Step 2: Run audit**

Run:

`python evals/run_operator_console_rc_phase1_audit.py --run-tag operator-console-rc-phase1-dev`

Expected: `overall_status=passed` and `readiness=operator_console_rc_phase1_ready`.

- [x] **Step 3: Run frontend build**

Run: `npm run build` from `frontend/`

Expected: TypeScript and Vite build pass.

- [x] **Step 4: Compile changed Python modules**

Run:

`python -m py_compile amadeus_thread0/runtime/operator_console_rc.py evals/run_operator_console_rc_phase1_audit.py amadeus_thread0/runtime/backend_api.py amadeus_thread0/runtime/transport_adapter.py`

Expected: command exits 0.

- [x] **Step 5: Commit**

Run:

`git add AGENTS.md program.md docs amadeus_thread0/runtime/operator_console_rc.py amadeus_thread0/runtime/backend_api.py amadeus_thread0/runtime/transport_adapter.py evals/run_operator_console_rc_phase1_audit.py tests/test_operator_console_rc.py tests/test_operator_console_rc_audit.py tests/test_transport_adapter.py tests/test_http_transport.py tests/test_frontend_runtime_shell_phase2.py frontend/src/contracts/backend.ts docs/engineering/frontend_contract/backend_api.types.ts frontend/src/data/mockBackend.ts frontend/src/runtime/backendClient.ts frontend/src/App.tsx`

Then:

`git commit -m "feat: add operator console rc gate"`

Expected: commit succeeds.
