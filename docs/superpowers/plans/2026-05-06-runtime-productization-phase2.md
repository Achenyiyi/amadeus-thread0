# Runtime Productization Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the existing runtime productization readback into an operator console contract that summarizes runtime health, evidence, safe routes, and next actions without widening authority.

**Architecture:** Keep `amadeus_thread0/runtime/runtime_productization.py` as the pure read-model owner and extend `operator_readback` from v1 to v2. Backend API/session/transport/CLI continue to consume the same helper, while audits produce a new phase-2 report prefix and preserved-baseline coverage keeps phase 1 and phase 2 distinct.

**Tech Stack:** Python 3, existing `BackendAPI` / `BackendSession`, pytest, local eval audit scripts, no frontend schema ownership and no runtime execution changes.

---

## File Structure

- Modify `amadeus_thread0/runtime/runtime_productization.py`
  - Add `RUNTIME_PRODUCTIZATION_PHASE1_READINESS`, `RUNTIME_PRODUCTIZATION_PHASE2_READINESS`, operator console sections, route readback, evidence summary, and phase-2 contract checks.
- Modify `amadeus_thread0/runtime/backend_api.py`
  - Keep the public `runtime_productization()` method and turn/event payload attachment, now returning v2 readback.
- Modify `amadeus_thread0/runtime/backend_session.py`
  - Keep `operator_readback_view()` aligned with the same v2 shape.
- Modify `amadeus_thread0/utils/cli_views.py`
  - Keep the compact line short while surfacing console health and next action.
- Modify `evals/run_runtime_productization_audit.py`
  - Emit `runtime-productization-phase2-audit-*` reports with `runtime_productization_phase2_ready`.
- Modify `evals/run_preserved_baselines_audit.py`
  - Preserve both `runtime_productization_phase1` and `runtime_productization_phase2`.
- Modify tests:
  - `tests/test_runtime_productization.py`
  - `tests/test_runtime_productization_audit.py`
  - `tests/test_backend_api.py`
  - `tests/test_backend_session.py`
  - `tests/test_cli_views.py`
  - `tests/test_preserved_baselines_audit.py`
- Modify docs:
  - `AGENTS.md`
  - `docs/engineering/PROJECT_STRUCTURE.md`
  - `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
  - `program.md`

### Task 1: Operator Console Read Model

**Files:**
- Modify: `amadeus_thread0/runtime/runtime_productization.py`
- Modify: `tests/test_runtime_productization.py`

- [x] **Step 1: Write failing tests**

Add tests asserting that `build_runtime_productization_readback(...)` now returns:

```python
assert readback["schema"] == "operator_readback.v2"
assert readback["readiness_status"] == "runtime_productization_phase2_ready"
assert readback["console_summary"]["health"] == "ready"
assert readback["console_summary"]["mode"] == "readback_only"
assert readback["console_summary"]["next_action"] == "monitor_runtime_readback"
assert readback["evidence_summary"]["ready_inputs"] == 3
assert readback["safe_routes"]["read_only_routes"] == [
    "/api/runtime-productization",
    "/api/environment-summary",
    "/api/runtime-layout",
]
```

Also add a regression where a pending approval count produces:

```python
assert readback["console_summary"]["next_action"] == "resolve_pending_operator_approval"
assert "pending_approvals=2" in compact_operator_readback_line(readback)
```

- [x] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_runtime_productization.py -q
```

Expected: FAIL because the schema is still `operator_readback.v1` and phase-2 fields do not exist.

- [x] **Step 3: Implement minimal read-model upgrade**

Update `runtime_productization.py`:

```python
RUNTIME_PRODUCTIZATION_PHASE1_READINESS = "runtime_productization_phase1_ready"
RUNTIME_PRODUCTIZATION_PHASE2_READINESS = "runtime_productization_phase2_ready"
RUNTIME_PRODUCTIZATION_READINESS = RUNTIME_PRODUCTIZATION_PHASE2_READINESS
```

Add:

```python
READ_ONLY_ROUTES = [
    "/api/runtime-productization",
    "/api/environment-summary",
    "/api/runtime-layout",
]

def _evidence_summary(inputs): ...
def _safe_routes(): ...
def _console_summary(contract, snapshot): ...
```

Contract remains ready only when all three inputs are ready and authority boundaries remain strict.

- [x] **Step 4: Run test to verify it passes**

Run:

```powershell
python -m pytest tests/test_runtime_productization.py -q
```

Expected: PASS.

### Task 2: Backend And CLI V2 Surfacing

**Files:**
- Modify: `tests/test_backend_api.py`
- Modify: `tests/test_backend_session.py`
- Modify: `tests/test_cli_views.py`
- Modify: `amadeus_thread0/runtime/backend_api.py`
- Modify: `amadeus_thread0/runtime/backend_session.py`
- Modify: `amadeus_thread0/utils/cli_views.py`

- [x] **Step 1: Write failing tests**

Update existing runtime-productization tests to expect:

```python
payload["schema"] == "operator_readback.v2"
payload["readiness_status"] == "runtime_productization_phase2_ready"
payload["console_summary"]["mode"] == "readback_only"
```

Update CLI test to assert:

```python
assert "console=ready" in line
assert "next=monitor_runtime_readback" in line
```

- [x] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_backend_api.py -k runtime_productization -q
python -m pytest tests/test_backend_session.py -k operator_readback -q
python -m pytest tests/test_cli_views.py -k operator_readback -q
```

Expected: FAIL until the readback helper and compact CLI line emit v2 fields.

- [x] **Step 3: Implement minimal surfacing**

Backend API/session should need no schema-local rebuild; they must keep delegating to `build_runtime_productization_readback(...)`. Update only compact CLI formatting to add:

```text
console=<health>
next=<next_action>
pending_approvals=<count>
```

- [x] **Step 4: Run tests to verify they pass**

Run the three focused commands again.

Expected: PASS.

### Task 3: Phase-2 Audit And Preserved Baselines

**Files:**
- Modify: `evals/run_runtime_productization_audit.py`
- Modify: `evals/run_preserved_baselines_audit.py`
- Modify: `tests/test_runtime_productization_audit.py`
- Modify: `tests/test_preserved_baselines_audit.py`

- [x] **Step 1: Write failing tests**

Update tests to expect:

```python
assert report["readiness_status"] == "runtime_productization_phase2_ready"
assert report["operator_readback"]["schema"] == "operator_readback.v2"
assert "Runtime Productization Phase 2 Audit" in rendered
assert "runtime_productization_phase2_ready" in rendered
```

Preserved baselines should include:

```python
"runtime_productization_phase1"
"runtime_productization_phase2"
```

with phase-2 prefix:

```python
"runtime-productization-phase2-audit-"
```

- [x] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_runtime_productization_audit.py tests/test_preserved_baselines_audit.py -q
```

Expected: FAIL because phase-2 readiness and preserved-baseline spec are missing.

- [x] **Step 3: Implement audit updates**

Update the runtime audit title, expected readiness, contract check row, and output filenames to phase 2 while retaining `runtime-productization-audit-*` as phase-1 historical evidence.

Update preserved-baselines specs to include both phase 1 and phase 2 productization gates.

- [x] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/test_runtime_productization_audit.py tests/test_preserved_baselines_audit.py -q
```

Expected: PASS.

### Task 4: Docs, Ledger, And Final Verification

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `program.md`

- [x] **Step 1: Update docs**

Record `runtime_productization_phase2_ready` as a preserved readback/productization gate with no new runtime authority.

- [x] **Step 2: Run final focused verification**

Run:

```powershell
python -m pytest tests/test_runtime_productization.py tests/test_runtime_productization_audit.py tests/test_preserved_baselines_audit.py tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py tests/test_transport_adapter.py -q
python -m pytest tests/test_post_baseline_closure.py tests/test_post_baseline_closure_audit.py tests/test_preserved_baselines_audit.py -q
python -m py_compile amadeus_thread0/agent.py amadeus_thread0/graph.py amadeus_thread0/runtime/runtime_productization.py evals/run_runtime_productization_audit.py
python -c "from amadeus_thread0.agent import agent; print(type(agent).__name__)"
```

Expected: PASS and graph build prints `CompiledStateGraph`.

- [x] **Step 3: Run audits**

Run:

```powershell
python evals/run_runtime_productization_audit.py --reports-dir "E:\桌面\amadeus-thread0\evals\reports"
python evals/run_preserved_baselines_audit.py --reports-dir "E:\桌面\amadeus-thread0\evals\reports"
```

Expected:

- `runtime_productization_phase2_ready`
- `preserved_baselines_ready`

- [x] **Step 4: Diff and placeholder checks**

Run:

```powershell
git diff --check
rg -n -e "T[B]D" -e "T[O]DO" -e "f[i]ll in" -e "implement la[t]er" docs\superpowers\plans\2026-05-06-runtime-productization-phase2.md amadeus_thread0\runtime\runtime_productization.py evals\run_runtime_productization_audit.py tests\test_runtime_productization.py tests\test_runtime_productization_audit.py
```

Expected: no diff errors and no placeholder matches.

- [x] **Step 5: Commit and merge**

Run:

```powershell
git add AGENTS.md amadeus_thread0/runtime/runtime_productization.py amadeus_thread0/runtime/backend_api.py amadeus_thread0/runtime/backend_session.py amadeus_thread0/utils/cli_views.py evals/run_runtime_productization_audit.py evals/run_preserved_baselines_audit.py tests/test_runtime_productization.py tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py tests/test_runtime_productization_audit.py tests/test_preserved_baselines_audit.py docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md docs/superpowers/plans/2026-05-06-runtime-productization-phase2.md program.md
git commit -m "feat: add runtime productization console readback"
git -C E:\桌面\amadeus-thread0 merge --ff-only codex/runtime-productization-phase2
```

Expected: commit succeeds and local `main` fast-forwards.

## Self-Review

- Spec coverage: The plan covers the read model, backend/session/CLI surfacing, phase-2 audit, preserved-baseline inclusion, docs, validation, and merge.
- Placeholder scan: No placeholder-only implementation instructions are present.
- Type consistency: The plan consistently uses `operator_readback.v2`, `runtime_productization_phase2_ready`, `console_summary`, `evidence_summary`, and `safe_routes`.
