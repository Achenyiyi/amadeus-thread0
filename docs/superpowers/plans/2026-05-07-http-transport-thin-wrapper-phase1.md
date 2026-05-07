# HTTP Transport Thin Wrapper Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a minimal HTTP transport wrapper over `BackendTransportAdapter` so product clients can exercise real HTTP-shaped request/response flow without creating a second backend semantics layer.

**Architecture:** Use Python standard-library WSGI primitives and pure request parsing helpers. The HTTP wrapper delegates every route to the existing `BackendTransportAdapter`, returns the same `backend.v1` envelopes, and keeps turn execution, approval resume, memory, persona, body, skills, browser, sandbox, and multimodal authority owned by the existing backend.

**Tech Stack:** Python 3, `wsgiref`/WSGI standard library, pytest, existing `BackendTransportAdapter`, existing eval report JSON/Markdown conventions, no FastAPI/Flask/Uvicorn dependency.

---

## File Structure

- Create: `amadeus_thread0/runtime/http_transport.py`
  - WSGI app factory, JSON request parsing, query parsing, response serialization, and optional runtime-bundle bootstrap helper.
- Create: `tests/test_http_transport.py`
  - Unit tests for WSGI GET, POST JSON, query parsing, invalid JSON, and semantics boundary.
- Create: `evals/run_http_transport_smokes.py`
  - Deterministic smoke runner over the WSGI app using a fake backend API.
- Create: `evals/run_http_transport_audit.py`
  - Audit runner that requires smoke readiness and closed authority boundaries.
- Create: `tests/test_http_transport_smokes.py`
- Create: `tests/test_http_transport_audit.py`
- Modify: `evals/run_preserved_baselines_audit.py`
  - Register `http_transport_thin_wrapper_phase1_ready`.
- Modify: `tests/test_preserved_baselines_audit.py`
  - Expect the HTTP transport preserved baseline after Phase 1 closes.
- Modify docs:
  - `AGENTS.md`
  - `program.md`
  - `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
  - `docs/engineering/PROJECT_STRUCTURE.md`
  - `docs/engineering/BACKEND_HANDOFF.md`
  - `docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md`
  - `docs/superpowers/plans/2026-05-07-runtime-productization-phase3.md`

---

### Task 1: WSGI Wrapper Core

**Files:**
- Create: `amadeus_thread0/runtime/http_transport.py`
- Test: `tests/test_http_transport.py`

- [x] **Step 1: Write failing tests**

Test code must cover:

- `GET /api/runtime-productization` returns HTTP 200 and a `backend.v1` envelope from `BackendTransportAdapter`
- `POST /api/turns/finalize` forwards JSON body to `BackendTransportAdapter`
- query strings are decoded into adapter query fields
- malformed JSON returns structured HTTP 400
- wrapper metadata says it is `thin_wrapper` and does not own backend semantics

- [x] **Step 2: Run RED**

```powershell
python -m pytest tests/test_http_transport.py -q
```

Expected: fail with `ModuleNotFoundError` for `amadeus_thread0.runtime.http_transport`.

- [x] **Step 3: Implement minimal WSGI wrapper**

Implement:

- `HTTP_TRANSPORT_PHASE1_READINESS = "http_transport_thin_wrapper_phase1_ready"`
- `HTTP_TRANSPORT_AUTHORITY_BOUNDARY`
- `build_wsgi_app(transport_adapter)`
- `call_wsgi_app(app, method, path, body=None, query_string="")`
- `create_http_transport_app(backend_api)`

Every request must delegate to `BackendTransportAdapter.handle(...)`.

- [x] **Step 4: Run GREEN**

```powershell
python -m pytest tests/test_http_transport.py tests/test_transport_adapter.py -q
```

Expected: pass.

---

### Task 2: HTTP Transport Smokes

**Files:**
- Create: `evals/run_http_transport_smokes.py`
- Test: `tests/test_http_transport_smokes.py`

- [x] **Step 1: Write failing smoke tests**

Assert `run_http_transport_smokes()` returns:

- `overall_status=passed`
- `readiness_status=http_transport_thin_wrapper_phase1_smokes_ready`
- scenarios for runtime read route, turn finalize route, invalid JSON, method-not-allowed, and boundary metadata

- [x] **Step 2: Run RED**

```powershell
python -m pytest tests/test_http_transport_smokes.py -q
```

Expected: fail with `ModuleNotFoundError` for `evals.run_http_transport_smokes`.

- [x] **Step 3: Implement smoke runner**

Use fake backend API envelopes and the real WSGI wrapper.
Write JSON/Markdown reports under `evals/reports/http-transport-smokes-*`.

- [x] **Step 4: Run GREEN**

```powershell
python -m pytest tests/test_http_transport_smokes.py -q
python evals/run_http_transport_smokes.py --reports-dir evals/reports
```

Expected: test passes and smoke report readiness is `http_transport_thin_wrapper_phase1_smokes_ready`.

---

### Task 3: HTTP Transport Audit

**Files:**
- Create: `evals/run_http_transport_audit.py`
- Test: `tests/test_http_transport_audit.py`

- [x] **Step 1: Write failing audit tests**

Assert `evaluate_http_transport_audit(...)`:

- passes when smoke report is ready and authority boundary remains closed
- fails when smoke report is missing or regressed
- reports `http_transport_thin_wrapper_phase1_ready`

- [x] **Step 2: Run RED**

```powershell
python -m pytest tests/test_http_transport_audit.py -q
```

Expected: fail with `ModuleNotFoundError` for `evals.run_http_transport_audit`.

- [x] **Step 3: Implement audit runner**

Load latest `http-transport-smokes-*.json`, evaluate boundary, write:

- `evals/reports/http-transport-audit-*.json`
- `evals/reports/http-transport-audit-*.md`

- [x] **Step 4: Run GREEN**

```powershell
python -m pytest tests/test_http_transport_audit.py -q
python evals/run_http_transport_audit.py --reports-dir evals/reports
```

Expected: audit report readiness is `http_transport_thin_wrapper_phase1_ready`.

---

### Task 4: Preserved Baseline And Dashboard Registration

**Files:**
- Modify: `evals/run_preserved_baselines_audit.py`
- Modify: `tests/test_preserved_baselines_audit.py`
- Modify: `amadeus_thread0/runtime/runtime_status_dashboard.py`
- Modify: `tests/test_runtime_status_dashboard.py`

- [x] **Step 1: Write failing tests**

Update preserved-baseline tests to expect `http_transport_thin_wrapper_phase1`.
Update dashboard tests to show `http_transport` as `phase1_ready` / `thin_wrapper` instead of `planned_next_spec`.

- [x] **Step 2: Run RED**

```powershell
python -m pytest tests/test_preserved_baselines_audit.py tests/test_runtime_status_dashboard.py -q
```

Expected: fail until the new baseline and dashboard lane are registered.

- [x] **Step 3: Implement registration**

Add:

- preserved baseline id `http_transport_thin_wrapper_phase1`
- prefix `http-transport-audit-`
- readiness `http_transport_thin_wrapper_phase1_ready`
- category `transport`

Update dashboard next-spec list so HTTP no longer appears as future-only after Phase 1.

- [x] **Step 4: Run GREEN**

```powershell
python -m pytest tests/test_preserved_baselines_audit.py tests/test_runtime_status_dashboard.py -q
```

Expected: pass.

---

### Task 5: Documentation

**Files:**
- Modify: `AGENTS.md`
- Modify: `program.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/BACKEND_HANDOFF.md`
- Modify: `docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md`
- Modify: `docs/superpowers/plans/2026-05-07-runtime-productization-phase3.md`

- [x] **Step 1: Document Phase 1 closure**

Record `HTTP Transport Thin Wrapper Phase 1` as:

- `http_transport_thin_wrapper_phase1_ready`
- WSGI/standard-library thin wrapper
- delegates to `BackendTransportAdapter`
- no HTTP-owned backend semantics

- [x] **Step 2: Preserve blocked surfaces**

Explicitly preserve:

- no HTTP-owned memory/body/autonomy/persona semantics
- no live capture
- no automatic skill registry writes
- no external harness enablement
- no frontend-owned backend semantics
- no SSE/WebSocket streaming implementation yet

---

### Task 6: Verification And Integration

**Files:**
- Generated ignored reports under `evals/reports/`

- [x] **Step 1: Run focused tests**

```powershell
python -m pytest tests/test_http_transport.py tests/test_http_transport_smokes.py tests/test_http_transport_audit.py tests/test_transport_adapter.py tests/test_runtime_status_dashboard.py tests/test_preserved_baselines_audit.py -q
```

- [x] **Step 2: Run audit reports**

```powershell
python evals/run_http_transport_smokes.py --reports-dir evals/reports
python evals/run_http_transport_audit.py --reports-dir "E:\桌面\amadeus-thread0\evals\reports"
python evals/run_preserved_baselines_audit.py --reports-dir "E:\桌面\amadeus-thread0\evals\reports"
```

- [x] **Step 3: Run compile check**

```powershell
python -m py_compile amadeus_thread0/runtime/http_transport.py evals/run_http_transport_smokes.py evals/run_http_transport_audit.py evals/run_preserved_baselines_audit.py
```

- [ ] **Step 4: Commit, merge, and push**

```powershell
git add AGENTS.md program.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/BACKEND_HANDOFF.md docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md docs/superpowers/plans/2026-05-07-runtime-productization-phase3.md docs/superpowers/plans/2026-05-07-http-transport-thin-wrapper-phase1.md amadeus_thread0/runtime/http_transport.py amadeus_thread0/runtime/runtime_status_dashboard.py evals/run_http_transport_smokes.py evals/run_http_transport_audit.py evals/run_preserved_baselines_audit.py tests/test_http_transport.py tests/test_http_transport_smokes.py tests/test_http_transport_audit.py tests/test_runtime_status_dashboard.py tests/test_preserved_baselines_audit.py
git commit -m "feat: add http transport thin wrapper"
git checkout main
git merge --ff-only codex/http-transport-thin-wrapper
git push origin main
```
