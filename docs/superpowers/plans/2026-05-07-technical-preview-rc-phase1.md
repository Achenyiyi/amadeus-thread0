# Technical Preview RC Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only release-candidate readiness gate that proves the current backend-first technical preview is evidence-complete with no open `NEXT_SPECS`.

**Architecture:** Add a pure runtime readback module plus an eval audit runner. The module consumes existing reports/dashboard dictionaries and never owns backend semantics; the runner loads latest ready reports from `evals/reports`, writes JSON/Markdown evidence, and fails closed on missing reports or widened authority.

**Tech Stack:** Python runtime modules, pytest, existing eval report conventions, Markdown docs.

---

### Task 1: RC Readiness Module

**Files:**
- Create: `amadeus_thread0/runtime/technical_preview_rc.py`
- Test: `tests/test_technical_preview_rc.py`

- [x] **Step 1: Write failing behavior tests**

Cover:

- ready evidence across preserved baselines, runtime dashboard, productization phase 3, HTTP transport, approved artifact multimodal runtime, Chinese semantic naturalness, and dynamic skill candidate runtime;
- `NEXT_SPECS == []`;
- blocked live capture and external executor authority;
- failure when dashboard next specs are non-empty;
- failure when blocked authority widens;
- compact RC status line.

Run:

```powershell
python -m pytest tests/test_technical_preview_rc.py -q
```

Expected RED:

```text
ModuleNotFoundError: No module named 'amadeus_thread0.runtime.technical_preview_rc'
```

- [x] **Step 2: Implement pure readback module**

Add:

- `TECHNICAL_PREVIEW_RC_PHASE1_READY`
- `TECHNICAL_PREVIEW_RC_PHASE1_BLOCKED`
- `EXPECTED_EVIDENCE`
- `build_technical_preview_rc_readiness(...)`
- `compact_technical_preview_rc_line(...)`

The implementation must only consume dictionaries and return a readback packet.

- [x] **Step 3: Verify module tests pass**

Run:

```powershell
python -m pytest tests/test_technical_preview_rc.py -q
```

Expected GREEN:

```text
4 passed
```

### Task 2: RC Audit Runner

**Files:**
- Create: `evals/run_technical_preview_rc_phase1_audit.py`
- Test: `tests/test_technical_preview_rc_audit.py`

- [x] **Step 1: Write failing audit tests**

Cover:

- `load_input_reports(...)` loads latest ready evidence by prefix and readiness;
- `evaluate_technical_preview_rc_phase1_audit(...)` returns `technical_preview_rc_phase1_ready`;
- missing evidence fails with `technical_preview_rc_phase1_blocked`;
- Markdown names authority boundaries.

Run:

```powershell
python -m pytest tests/test_technical_preview_rc_audit.py -q
```

Expected RED:

```text
ModuleNotFoundError: No module named 'evals.run_technical_preview_rc_phase1_audit'
```

- [x] **Step 2: Implement audit runner**

Add:

- report loading helpers;
- `evaluate_technical_preview_rc_phase1_audit(...)`;
- `render_markdown(...)`;
- CLI `main()` with `--reports-dir` and `--run-tag`.

The runner must write `technical-preview-rc-phase1-audit-*.json` and `.md`.

- [x] **Step 3: Verify audit tests pass**

Run:

```powershell
python -m pytest tests/test_technical_preview_rc_audit.py tests/test_technical_preview_rc.py -q
```

Expected GREEN:

```text
7 passed
```

### Task 3: Documentation And Ledger

**Files:**
- Create: `docs/superpowers/specs/2026-05-07-technical-preview-rc-phase1-design.md`
- Create: `docs/superpowers/plans/2026-05-07-technical-preview-rc-phase1.md`
- Modify: `AGENTS.md`
- Modify: `program.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/BACKEND_HANDOFF.md`
- Modify: `docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md`
- Modify: `docs/FINAL_DELIVERY_MANIFEST.md`
- Modify: `docs/TECHNICAL_PREVIEW_CHECKLIST.md`
- Modify: `docs/ADVISOR_REPRO_RUNBOOK.md`

- [ ] **Step 1: Document RC boundary**

State that Technical Preview RC Phase 1 is evidence/readback-only and does not unlock live capture, model calls, registry writes, external harnesses, memory writes, persona mutation, or frontend semantics.

- [ ] **Step 2: Update delivery and reproduction docs**

Add the RC audit runner and the current report expectations to the manifest/checklist/runbook.

- [ ] **Step 3: Update current ledger**

Record the files changed, validation run, and next step in `program.md`.

### Task 4: Final Verification

**Files:**
- No new source files beyond Tasks 1-3.

- [ ] **Step 1: Run focused tests**

```powershell
python -m pytest tests/test_technical_preview_rc.py tests/test_technical_preview_rc_audit.py tests/test_runtime_status_dashboard.py tests/test_preserved_baselines_audit.py tests/test_runtime_productization_phase3_audit.py tests/test_frontend_contract_sync.py -q
```

- [ ] **Step 2: Run RC and preserved audits**

```powershell
python evals/run_runtime_productization_phase3_audit.py
python evals/run_technical_preview_rc_phase1_audit.py --run-tag rc-phase1-dev
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
```

- [ ] **Step 3: Compile changed Python files**

```powershell
python -m py_compile amadeus_thread0/runtime/technical_preview_rc.py evals/run_technical_preview_rc_phase1_audit.py
```

- [ ] **Step 4: Diff hygiene**

```powershell
git diff --check
```

- [ ] **Step 5: Commit**

```powershell
git add AGENTS.md program.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/BACKEND_HANDOFF.md docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md docs/FINAL_DELIVERY_MANIFEST.md docs/TECHNICAL_PREVIEW_CHECKLIST.md docs/ADVISOR_REPRO_RUNBOOK.md docs/superpowers/specs/2026-05-07-technical-preview-rc-phase1-design.md docs/superpowers/plans/2026-05-07-technical-preview-rc-phase1.md amadeus_thread0/runtime/technical_preview_rc.py evals/run_technical_preview_rc_phase1_audit.py tests/test_technical_preview_rc.py tests/test_technical_preview_rc_audit.py
git commit -m "feat: add technical preview rc gate"
```
