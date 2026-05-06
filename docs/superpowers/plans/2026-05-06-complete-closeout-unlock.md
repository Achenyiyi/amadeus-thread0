# Complete Closeout Unlock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unlock all remaining post-baseline lanes into bounded implementation-ready phases and add a complete cross-gate preserved-baseline audit.

**Architecture:** Keep this slice as a control-plane change. Update post-baseline status contracts, expand the preserved-baselines meta-audit, and synchronize architecture docs and the run ledger. Do not implement large runtime systems inside this closeout slice.

**Tech Stack:** Python, pytest, existing eval/report helpers, repository docs.

---

### Task 1: Post-Baseline Unlock Matrix

**Files:**
- Modify: `tests/test_post_baseline_closure.py`
- Modify: `tests/test_post_baseline_closure_audit.py`
- Modify: `amadeus_thread0/runtime/post_baseline_closure.py`
- Modify: `evals/run_post_baseline_closure_audit.py`

- [x] **Step 1: Write failing tests**

Tests assert formerly deferred/tracked lanes are now `unlocked_planned`, and that `external_executor_harnesses` plus `frontend_runtime_shell` are part of the closeout matrix.

- [x] **Step 2: Run red**

Run: `python -m pytest tests/test_post_baseline_closure.py tests/test_post_baseline_closure_audit.py -q`

Observed: 5 failures against the old deferred/tracked implementation.

- [x] **Step 3: Implement unlock matrix**

Add `unlocked_planned`, preserve required runtime items, add explicit blocked surfaces, and render unlocked counts in the audit markdown.

- [x] **Step 4: Run green**

Run: `python -m pytest tests/test_post_baseline_closure.py tests/test_post_baseline_closure_audit.py -q`

Observed: `9 passed`.

### Task 2: Cross-Gate Preserved Baselines Audit

**Files:**
- Modify: `tests/test_preserved_baselines_audit.py`
- Modify: `evals/run_preserved_baselines_audit.py`

- [x] **Step 1: Write failing tests**

Tests assert the current preserved gate set includes freeze gate, autonomy, embodiment, sandbox phase 1 and 2, skills, browser, post-baseline, TTS, and procedural phases 1 through 4.

- [x] **Step 2: Run red**

Run: `python -m pytest tests/test_preserved_baselines_audit.py -q`

Observed: import failure for missing `load_statuses`, proving the old helper did not expose the needed contract.

- [x] **Step 3: Implement baseline specs**

Add `BASELINE_SPECS`, compatibility dictionaries, category summaries, explicit missing-report failures, and category-aware markdown.

- [x] **Step 4: Run green**

Run: `python -m pytest tests/test_preserved_baselines_audit.py -q`

Observed: `7 passed`.

### Task 3: Documentation And Ledger

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `program.md`

- [x] **Step 1: Update operating contract**

Record that the complete closeout unlock is now the active control-plane posture and that all formerly deferred lanes are unlocked for bounded implementation specs.

- [x] **Step 2: Update structure and architecture docs**

Document the expanded `post_baseline_closure` and `preserved_baselines_audit` ownership.

- [x] **Step 3: Update run ledger**

Append a concise entry with focus, changed files, validations, result, and concrete next step.

### Task 4: Verification And Merge

**Files:**
- No additional implementation files expected.

- [x] **Step 1: Run targeted tests**

```powershell
python -m pytest tests/test_post_baseline_closure.py tests/test_post_baseline_closure_audit.py tests/test_preserved_baselines_audit.py -q
```

Observed: `16 passed`.

- [x] **Step 2: Compile changed eval/runtime modules**

```powershell
python -m py_compile amadeus_thread0/runtime/post_baseline_closure.py evals/run_post_baseline_closure_audit.py evals/run_preserved_baselines_audit.py
```

Observed: passed.

- [x] **Step 3: Run meta-audits**

Run the post-baseline closure audit. Run preserved-baselines audit against the main worktree report directory if current reports are available; otherwise record the expected missing-report failure for the clean worktree.

Observed:
- `python evals/run_post_baseline_closure_audit.py --run-tag complete-closeout-unlock-postfix`: passed with `post_baseline_closure_ready`
- `python evals/run_preserved_baselines_audit.py --reports-dir 'E:\桌面\amadeus-thread0\evals\reports'`: initially exposed report-selection bug, then passed with `preserved_baselines_ready`

- [x] **Step 4: Diff check**

```powershell
git diff --check -- amadeus_thread0/runtime/post_baseline_closure.py evals/run_post_baseline_closure_audit.py evals/run_preserved_baselines_audit.py tests/test_post_baseline_closure.py tests/test_post_baseline_closure_audit.py tests/test_preserved_baselines_audit.py AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md docs/superpowers/specs/2026-05-06-complete-closeout-unlock-design.md docs/superpowers/plans/2026-05-06-complete-closeout-unlock.md
```

Observed: passed with only Windows LF-to-CRLF warnings.

- [ ] **Step 5: Commit and merge**

Commit the worktree branch, then merge `codex/complete-closeout-unlock` back into `main`.
