# Advisor Demo Readiness Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic `advisor_demo_readiness.v1` gate that verifies the current RC evidence and demo/advisor reproduction package are ready to hand to a reviewer.

**Architecture:** Add one focused runtime helper that consumes Operator Console RC evidence plus repository asset text and emits read-only readiness. Add one audit runner that loads the latest ready Operator Console RC report and scans required docs from disk. Update status docs to describe the new package-readiness gate without claiming a live demo has already happened.

**Tech Stack:** Python runtime helper, pytest, deterministic `evals/` audit script, Markdown status docs.

---

## File Structure

- Create `amadeus_thread0/runtime/advisor_demo_readiness.py`: pure readiness aggregation over operator RC evidence, asset inventory, command coverage, demo scenario coverage, and authority boundary.
- Create `tests/test_advisor_demo_readiness.py`: unit tests for ready and blocked helper behavior.
- Create `evals/run_advisor_demo_readiness_phase1_audit.py`: deterministic audit runner and Markdown report writer.
- Create `tests/test_advisor_demo_readiness_audit.py`: audit runner tests.
- Modify docs/status ledgers:
  - `AGENTS.md`
  - `program.md`
  - `docs/engineering/PROJECT_STRUCTURE.md`
  - `docs/engineering/BACKEND_HANDOFF.md`
  - `docs/FINAL_DELIVERY_MANIFEST.md`
  - `docs/ADVISOR_REPRO_RUNBOOK.md`
  - `docs/TECHNICAL_PREVIEW_CHECKLIST.md`

---

### Task 1: Runtime Readiness Helper

**Files:**
- Create: `amadeus_thread0/runtime/advisor_demo_readiness.py`
- Test: `tests/test_advisor_demo_readiness.py`

- [x] **Step 1: Write failing helper tests**

Add tests importing `build_advisor_demo_readiness`, `compact_advisor_demo_readiness_line`, and `ADVISOR_DEMO_READINESS_PHASE1_READY`.

Cover:

- ready Operator Console RC plus all assets/commands/demo scenarios produces `advisor_demo_readiness_phase1_ready`;
- missing required asset blocks readiness;
- widened live-capture authority blocks readiness;
- compact line exposes readiness, asset count, command count, scenario count, and scope.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_advisor_demo_readiness.py -q
```

Expected: fail with `ModuleNotFoundError` for `amadeus_thread0.runtime.advisor_demo_readiness`.

- [x] **Step 3: Implement minimal helper**

Implement:

- `ADVISOR_DEMO_READINESS_PHASE1_READY = "advisor_demo_readiness_phase1_ready"`
- `ADVISOR_DEMO_READINESS_PHASE1_BLOCKED = "advisor_demo_readiness_phase1_blocked"`
- `REQUIRED_ASSETS`
- `REQUIRED_COMMANDS`
- `REQUIRED_DEMO_SIGNALS`
- `build_advisor_demo_readiness(...)`
- `compact_advisor_demo_readiness_line(...)`

The helper should fail closed when:

- operator console RC is not `overall_status=passed` and `operator_console_rc_phase1_ready`;
- any required asset is missing;
- any required command coverage is missing;
- any required demo signal is missing;
- any blocked authority boolean is true.

- [x] **Step 4: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_advisor_demo_readiness.py -q
```

Expected: all tests pass.

---

### Task 2: Audit Runner

**Files:**
- Create: `evals/run_advisor_demo_readiness_phase1_audit.py`
- Test: `tests/test_advisor_demo_readiness_audit.py`

- [x] **Step 1: Write failing audit tests**

Add tests for:

- loading the latest ready `operator-console-rc-phase1-audit-*.json`;
- evaluating a temporary repo tree with all required docs and commands;
- rendering Markdown with readiness, asset inventory, and authority boundary.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_advisor_demo_readiness_audit.py -q
```

Expected: fail with `ModuleNotFoundError` for `evals.run_advisor_demo_readiness_phase1_audit`.

- [x] **Step 3: Implement audit runner**

The runner should:

- accept `--reports-dir`, `--project-root`, and `--run-tag`;
- load latest ready Operator Console RC evidence;
- read required doc assets from `project_root`;
- call `build_advisor_demo_readiness(...)`;
- write JSON and Markdown reports named `advisor-demo-readiness-phase1-audit-*`;
- return exit code `0` only when `overall_status == "passed"`.

- [x] **Step 4: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_advisor_demo_readiness_audit.py tests/test_advisor_demo_readiness.py -q
```

Expected: all tests pass.

---

### Task 3: Documentation And Status Wiring

**Files:**
- Modify: `AGENTS.md`
- Modify: `program.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/BACKEND_HANDOFF.md`
- Modify: `docs/FINAL_DELIVERY_MANIFEST.md`
- Modify: `docs/ADVISOR_REPRO_RUNBOOK.md`
- Modify: `docs/TECHNICAL_PREVIEW_CHECKLIST.md`
- Modify: `docs/superpowers/plans/2026-05-07-advisor-demo-readiness-phase1.md`

- [x] **Step 1: Update docs**

Document `advisor_demo_readiness_phase1_ready` as a package-readiness / advisor-repro gate layered over Operator Console RC.

Make the boundary explicit:

- it is package readiness, not live demo certification;
- it does not add live capture, model calls, registry writes, external harness enablement, frontend-owned semantics, HTTP ownership, persona mutation, memory writes, or external mutation.

- [x] **Step 2: Run doc scan**

Run:

```powershell
rg -n "advisor_demo_readiness|advisor-demo-readiness|Advisor Demo Readiness" AGENTS.md program.md docs
```

Expected: the new gate is documented in status, handoff, manifest, checklist, runbook, structure docs, spec, and plan.

---

### Task 4: Final Verification And Commit

**Files:**
- All changed files.

- [x] **Step 1: Seed current RC evidence for local audit**

If the worktree has no `evals/reports` directory, copy the latest ready `operator-console-rc-phase1-audit-*.json` and `.md` from the main repo's `evals/reports` into this worktree's ignored `evals/reports`.

- [x] **Step 2: Run focused tests**

Run:

```powershell
python -m pytest tests/test_advisor_demo_readiness.py tests/test_advisor_demo_readiness_audit.py tests/test_operator_console_rc.py tests/test_technical_preview_rc.py -q
```

Expected: all selected tests pass.

- [x] **Step 3: Run audit**

Run:

```powershell
python evals/run_advisor_demo_readiness_phase1_audit.py --run-tag advisor-demo-readiness-phase1-dev
```

Expected: `overall_status=passed` and `readiness=advisor_demo_readiness_phase1_ready`.

- [x] **Step 4: Compile changed Python modules**

Run:

```powershell
python -m py_compile amadeus_thread0/runtime/advisor_demo_readiness.py evals/run_advisor_demo_readiness_phase1_audit.py
```

Expected: command exits 0.

- [x] **Step 5: Check diff whitespace**

Run:

```powershell
git diff --check
```

Expected: command exits 0.

- [x] **Step 6: Commit**

Run:

```powershell
git add AGENTS.md program.md docs amadeus_thread0/runtime/advisor_demo_readiness.py evals/run_advisor_demo_readiness_phase1_audit.py tests/test_advisor_demo_readiness.py tests/test_advisor_demo_readiness_audit.py
git commit -m "feat: add advisor demo readiness gate"
```

Expected: commit succeeds.
