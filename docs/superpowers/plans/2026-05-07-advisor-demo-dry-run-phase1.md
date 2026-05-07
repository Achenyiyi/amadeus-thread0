# Advisor Demo Dry Run Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic `advisor_demo_dry_run.v1` gate that verifies the advisor/demo rehearsal path can be followed and archived from current assets.

**Architecture:** Add one pure runtime helper that consumes ready Advisor Demo Readiness evidence plus demo/runbook/checklist/manifest text. Add one audit runner that loads the latest ready Advisor Demo Readiness report and scans required dry-run assets from disk. Update status docs to describe the dry-run gate without claiming a real live demo has occurred.

**Tech Stack:** Python runtime helper, pytest, deterministic `evals/` audit script, Markdown status docs.

---

## File Structure

- Create `amadeus_thread0/runtime/advisor_demo_dry_run.py`: pure rehearsal-readiness aggregation over advisor readiness evidence, scenario coverage, runbook coverage, archive coverage, and authority boundary.
- Create `tests/test_advisor_demo_dry_run.py`: unit tests for ready and blocked helper behavior.
- Create `evals/run_advisor_demo_dry_run_phase1_audit.py`: deterministic audit runner and Markdown report writer.
- Create `tests/test_advisor_demo_dry_run_audit.py`: audit runner tests.
- Modify docs/status ledgers:
  - `AGENTS.md`
  - `program.md`
  - `docs/engineering/PROJECT_STRUCTURE.md`
  - `docs/engineering/BACKEND_HANDOFF.md`
  - `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
  - `docs/FINAL_DELIVERY_MANIFEST.md`
  - `docs/ADVISOR_REPRO_RUNBOOK.md`
  - `docs/TECHNICAL_PREVIEW_CHECKLIST.md`

---

### Task 1: Runtime Dry-Run Helper

**Files:**
- Create: `amadeus_thread0/runtime/advisor_demo_dry_run.py`
- Test: `tests/test_advisor_demo_dry_run.py`

- [x] **Step 1: Write failing helper tests**

Add tests importing `build_advisor_demo_dry_run`, `compact_advisor_demo_dry_run_line`, and `ADVISOR_DEMO_DRY_RUN_PHASE1_READY`.

Cover:

- ready Advisor Demo Readiness evidence plus all scenario/runbook/archive coverage produces `advisor_demo_dry_run_phase1_ready`;
- missing demo scenario blocks readiness;
- widened authority inherited from advisor readiness blocks readiness;
- compact line exposes readiness, scenario count, runbook count, archive count, and scope.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_advisor_demo_dry_run.py -q
```

Expected: fail with `ModuleNotFoundError` for `amadeus_thread0.runtime.advisor_demo_dry_run`.

- [x] **Step 3: Implement minimal helper**

Implement:

- `ADVISOR_DEMO_DRY_RUN_PHASE1_READY = "advisor_demo_dry_run_phase1_ready"`
- `ADVISOR_DEMO_DRY_RUN_PHASE1_BLOCKED = "advisor_demo_dry_run_phase1_blocked"`
- `DRY_RUN_SCOPE = "scripted_rehearsal_ready_not_live_demo_observed"`
- `REQUIRED_DEMO_SCENARIOS`
- `REQUIRED_RUNBOOK_MARKERS`
- `REQUIRED_ARCHIVE_MARKERS`
- `build_advisor_demo_dry_run(...)`
- `compact_advisor_demo_dry_run_line(...)`

The helper should fail closed when:

- advisor demo readiness is not `overall_status=passed` and `advisor_demo_readiness_phase1_ready`;
- any required scenario coverage is missing;
- any runbook marker is missing;
- any archive marker is missing;
- any blocked authority boolean is true.

- [x] **Step 4: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_advisor_demo_dry_run.py -q
```

Expected: all tests pass.

---

### Task 2: Audit Runner

**Files:**
- Create: `evals/run_advisor_demo_dry_run_phase1_audit.py`
- Test: `tests/test_advisor_demo_dry_run_audit.py`

- [x] **Step 1: Write failing audit tests**

Add tests for:

- loading the latest ready `advisor-demo-readiness-phase1-audit-*.json`;
- evaluating a temporary repo tree with required dry-run docs;
- rendering Markdown with readiness, scenario inventory, runbook inventory, archive inventory, and authority boundary.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_advisor_demo_dry_run_audit.py -q
```

Expected: fail with `ModuleNotFoundError` for `evals.run_advisor_demo_dry_run_phase1_audit`.

- [x] **Step 3: Implement audit runner**

The runner should:

- accept `--reports-dir`, `--project-root`, and `--run-tag`;
- load latest ready Advisor Demo Readiness evidence;
- read required docs from `project_root`;
- call `build_advisor_demo_dry_run(...)`;
- write JSON and Markdown reports named `advisor-demo-dry-run-phase1-audit-*`;
- return exit code `0` only when `overall_status == "passed"`.

- [x] **Step 4: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_advisor_demo_dry_run_audit.py tests/test_advisor_demo_dry_run.py -q
```

Expected: all tests pass.

---

### Task 3: Documentation And Status Wiring

**Files:**
- Modify: `AGENTS.md`
- Modify: `program.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/BACKEND_HANDOFF.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `docs/FINAL_DELIVERY_MANIFEST.md`
- Modify: `docs/ADVISOR_REPRO_RUNBOOK.md`
- Modify: `docs/TECHNICAL_PREVIEW_CHECKLIST.md`
- Modify: `docs/superpowers/plans/2026-05-07-advisor-demo-dry-run-phase1.md`

- [x] **Step 1: Update docs**

Document `advisor_demo_dry_run_phase1_ready` as a scripted rehearsal / archive-readiness gate layered over Advisor Demo Readiness.

Make the boundary explicit:

- it is scripted dry-run readiness, not live demo certification;
- it does not add live capture, model calls, registry writes, external harness enablement, frontend-owned semantics, HTTP ownership, persona mutation, memory writes, or external mutation.

- [x] **Step 2: Run doc scan**

Run:

```powershell
rg -n "advisor_demo_dry_run|advisor-demo-dry-run|Advisor Demo Dry Run" AGENTS.md program.md docs
```

Expected: the new gate is documented in status, handoff, manifest, checklist, runbook, structure docs, architecture decisions, spec, and plan.

---

### Task 4: Final Verification And Commit

**Files:**
- All changed files.

- [x] **Step 1: Seed current Advisor Demo Readiness evidence for local audit**

If the worktree has no `evals/reports` directory, copy the latest ready `advisor-demo-readiness-phase1-audit-*.json` and `.md` from the main repo's `evals/reports` into this worktree's ignored `evals/reports`.

- [x] **Step 2: Run focused tests**

Run:

```powershell
python -m pytest tests/test_advisor_demo_dry_run.py tests/test_advisor_demo_dry_run_audit.py tests/test_advisor_demo_readiness.py tests/test_advisor_demo_readiness_audit.py -q
```

Expected: all selected tests pass.

- [x] **Step 3: Run audit**

Run:

```powershell
python evals/run_advisor_demo_dry_run_phase1_audit.py --run-tag advisor-demo-dry-run-phase1-dev
```

Expected: `overall_status=passed` and `readiness=advisor_demo_dry_run_phase1_ready`.

- [x] **Step 4: Compile changed Python modules**

Run:

```powershell
python -m py_compile amadeus_thread0/runtime/advisor_demo_dry_run.py evals/run_advisor_demo_dry_run_phase1_audit.py
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
git add AGENTS.md program.md docs amadeus_thread0/runtime/advisor_demo_dry_run.py evals/run_advisor_demo_dry_run_phase1_audit.py tests/test_advisor_demo_dry_run.py tests/test_advisor_demo_dry_run_audit.py
git commit -m "feat: add advisor demo dry run gate"
```

Expected: commit succeeds.
