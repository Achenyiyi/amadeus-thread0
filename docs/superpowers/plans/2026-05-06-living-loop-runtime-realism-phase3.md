# Living Loop Runtime Realism Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make living-loop realism understand Phase 5 artifact motive-to-behavior alignment readback so backend payloads can prove whether artifact motive hints are causally visible in actual behavior semantics.

**Architecture:** Extend `living_loop_realism.py` with an optional Phase 3 readback path. Payloads without `embodied_interaction.artifact_behavior_alignment` continue to report Phase 2 readiness; payloads with a valid Phase 5 alignment readback are promoted to `living_loop_runtime_realism_phase3_ready` and expose alignment visibility without recalculating or mutating behavior.

**Tech Stack:** Python 3, pytest, deterministic local `evals/` audit scripts, existing backend payload dictionaries, existing Phase 5 `embodied_interaction` readback.

---

## File Structure

- `amadeus_thread0/runtime/living_loop_realism.py`
  - Add Phase 3 readiness constants.
  - Normalize `embodied_interaction.artifact_behavior_alignment`.
  - Preserve Phase 2 readiness when no artifact behavior alignment is present.
- `tests/test_living_loop_realism.py`
  - Unit coverage for Phase 3 promotion, missing alignment fallback, and authority boundaries.
- `tests/test_backend_api.py`
  - Backend envelope coverage proving `assistant_turn` / `event_round` include Phase 3 realism when Phase 5 embodied alignment is present.
- `evals/run_living_loop_realism_phase3_audit.py`
  - New deterministic audit reporting `living_loop_runtime_realism_phase3_ready`.
- `tests/test_living_loop_realism_phase3_audit.py`
  - Audit helper coverage.
- `evals/run_preserved_baselines_audit.py`
  - Add Phase 3 as a preserved baseline.
- `tests/test_preserved_baselines_audit.py`
  - Add expected baseline and update living-loop realism category count from `2` to `3`.
- `AGENTS.md`
  - Document Phase 3 as a preserved baseline after implementation.
- `docs/engineering/PROJECT_STRUCTURE.md`
  - Update living-loop realism ownership and audit list.
- `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
  - Record the Phase 3 readback-only decision.
- `program.md`
  - Update the live ledger.

---

### Task 1: Living-Loop Phase 3 Unit Contract

**Files:**
- Modify: `tests/test_living_loop_realism.py`
- Modify: `amadeus_thread0/runtime/living_loop_realism.py`

- [x] **Step 1: Write failing tests**

Add tests proving:

```python
def test_backend_payload_with_artifact_behavior_alignment_promotes_phase3_readiness():
    payload = _backend_payload()
    payload["embodied_interaction"] = {
        "readiness_status": "embodied_interaction_runtime_phase5_ready",
        "artifact_behavior_alignment": {
            "schema": "artifact_behavior_alignment.v1",
            "status": "ready",
            "readiness_status": "artifact_behavior_alignment_ready",
            "alignment_items": [{
                "source_ref_id": "img-align-1",
                "primary_motive_hint": "restore_access_continuity",
                "behavior_primary_motive": "restore_access_continuity",
                "plan_primary_motive": "restore_access_continuity",
                "alignment_status": "causally_aligned",
                "behavior_mutation_applied": False,
                "authority": {
                    "model_api_called": False,
                    "memory_write_allowed": False,
                    "writeback_ready": False,
                    "behavior_mutation_allowed": False,
                    "behavior_mutation_applied": False,
                },
            }],
            "alignment_summary": {
                "alignment_status": "causally_aligned",
                "aligned_count": 1,
                "advisory_not_reflected_count": 0,
                "conflict_count": 0,
                "should_mutate_behavior": False,
                "should_write_memory": False,
            },
            "model_api_called": False,
            "writeback_ready_count": 0,
        },
    }

    readback = build_backend_payload_realism_readback(payload)

    assert readback["readiness_status"] == "living_loop_runtime_realism_phase3_ready"
    assert readback["artifact_behavior_alignment"]["status"] == "ready"
    assert readback["artifact_behavior_alignment"]["alignment_visible"] is True
    assert readback["artifact_behavior_alignment"]["alignment_status"] == "causally_aligned"
    assert readback["authority_boundary"]["memory_write_allowed"] is False
```

- [x] **Step 2: Run test to verify RED**

Run:

```powershell
python -m pytest tests/test_living_loop_realism.py -k "artifact_behavior_alignment or backend_payload_readback_returns_phase2_ready" -q
```

Expected: fails because Phase 3 constants and `artifact_behavior_alignment` readback do not exist.

- [x] **Step 3: Implement Phase 3 readback**

Modify `living_loop_realism.py` to:

- add `LIVING_LOOP_REALISM_PHASE3_READINESS = "living_loop_runtime_realism_phase3_ready"`;
- add `LIVING_LOOP_REALISM_PHASE3_IN_PROGRESS = "living_loop_runtime_realism_phase3_in_progress"`;
- normalize `payload["embodied_interaction"]["artifact_behavior_alignment"]`;
- mark alignment visible only when status/readiness is ready and alignment items exist;
- fail closed if alignment claims model calls, memory writes, behavior mutation, writeback readiness, or external mutation;
- promote backend payload realism from Phase 2 to Phase 3 only when backend payload, regular causality, and artifact alignment readback are all ready;
- keep payloads without alignment at Phase 2 readiness.

- [x] **Step 4: Run unit tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_living_loop_realism.py -q
```

Expected: all living-loop realism unit tests pass.

- [x] **Step 5: Commit task slice**

Run:

```powershell
git add amadeus_thread0/runtime/living_loop_realism.py tests/test_living_loop_realism.py
git commit -m "feat: read artifact behavior alignment in realism"
```

---

### Task 2: Backend Payload Integration

**Files:**
- Modify: `tests/test_backend_api.py`

- [x] **Step 1: Write failing backend tests**

Add a backend payload test proving `assistant_turn` and `event_round` carry Phase 3 realism when Phase 5 embodied alignment is present.

- [x] **Step 2: Run backend selected tests to verify RED**

Run:

```powershell
python -m pytest tests/test_backend_api.py -k "living_loop_realism and artifact_behavior_alignment" -q
```

Expected: fails because backend realism readback still reports Phase 2.

- [x] **Step 3: Confirm backend integration uses existing readback builder**

No backend API production change should be needed unless the test reveals payload ordering issues. `BackendAPI` already attaches `embodied_interaction` and `living_loop_realism`; Phase 3 should be reached by extending the realism builder.

- [x] **Step 4: Run selected tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_backend_api.py -k "living_loop_realism or artifact_behavior_alignment or embodied_interaction" -q
```

Expected: selected backend tests pass.

- [x] **Step 5: Commit task slice**

Run:

```powershell
git add tests/test_backend_api.py
git commit -m "test: cover phase 3 realism backend payloads"
```

---

### Task 3: Phase 3 Audit And Preserved Baseline

**Files:**
- Create: `evals/run_living_loop_realism_phase3_audit.py`
- Create: `tests/test_living_loop_realism_phase3_audit.py`
- Modify: `evals/run_preserved_baselines_audit.py`
- Modify: `tests/test_preserved_baselines_audit.py`

- [x] **Step 1: Write failing audit tests**

Create tests requiring:

- overall status passed;
- readiness `living_loop_runtime_realism_phase3_ready`;
- at least one `causally_aligned` artifact alignment scenario;
- at least one `advisory_not_reflected` scenario that remains honest and does not fake causality;
- no model API calls, memory writes, writeback readiness, or behavior mutation.

- [x] **Step 2: Run audit tests to verify RED**

Run:

```powershell
python -m pytest tests/test_living_loop_realism_phase3_audit.py tests/test_preserved_baselines_audit.py -q
```

Expected: fails because Phase 3 audit and baseline row do not exist.

- [x] **Step 3: Implement audit and baseline row**

Add this preserved baseline spec:

```python
{
    "id": "living_loop_runtime_realism_phase3",
    "prefix": "living-loop-realism-phase3-audit-",
    "expected_readiness": "living_loop_runtime_realism_phase3_ready",
    "category": "living_loop_realism",
}
```

- [x] **Step 4: Run audit tests and audit**

Run:

```powershell
python -m pytest tests/test_living_loop_realism_phase3_audit.py tests/test_preserved_baselines_audit.py -q
python evals/run_living_loop_realism_phase3_audit.py --run-tag phase3-dev
```

Expected: tests pass and audit prints `readiness=living_loop_runtime_realism_phase3_ready`.

- [x] **Step 5: Commit task slice**

Run:

```powershell
git add evals/run_living_loop_realism_phase3_audit.py tests/test_living_loop_realism_phase3_audit.py evals/run_preserved_baselines_audit.py tests/test_preserved_baselines_audit.py
git commit -m "test: audit living loop realism phase 3"
```

---

### Task 4: Documentation And Ledger

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `program.md`
- Modify: `docs/superpowers/plans/2026-05-06-living-loop-runtime-realism-phase3.md`

- [x] **Step 1: Update docs**

Document that Phase 3:

- reports `living_loop_runtime_realism_phase3_ready`;
- consumes Phase 5 alignment readback from backend payloads;
- does not recalculate alignment from raw artifacts;
- preserves `advisory_not_reflected` as truthful visible evidence;
- does not mutate memory, behavior, persona core, frontend semantics, browser/tool/sandbox authority, or skill registry state.

- [x] **Step 2: Mark plan checkboxes complete**

Update this plan file as task work completes.

- [x] **Step 3: Commit docs**

Run:

```powershell
git add AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md docs/superpowers/plans/2026-05-06-living-loop-runtime-realism-phase3.md
git commit -m "docs: close living loop realism phase 3"
```

---

### Task 5: Final Verification, Merge, And Push

**Files:**
- No new implementation files. This task verifies and integrates all prior slices.

- [ ] **Step 1: Run focused regression**

Run:

```powershell
python -m pytest tests/test_living_loop_realism.py tests/test_living_loop_realism_phase2_audit.py tests/test_living_loop_realism_phase3_audit.py tests/test_embodied_interaction_runtime.py tests/test_artifact_behavior_alignment.py -q
```

- [ ] **Step 2: Run backend and preserved-baseline selected regression**

Run:

```powershell
python -m pytest tests/test_backend_api.py -k "living_loop_realism or artifact_behavior_alignment or embodied_interaction" -q
python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py tests/test_tool_approval_policy.py -q
python -m pytest tests/test_memory_guard.py tests/test_session_orchestrator.py -q
```

- [ ] **Step 3: Run compile and graph checks**

Run:

```powershell
python -m py_compile amadeus_thread0/agent.py amadeus_thread0/graph.py amadeus_thread0/runtime/living_loop_realism.py amadeus_thread0/runtime/embodied_interaction_runtime.py evals/run_living_loop_realism_phase2_audit.py evals/run_living_loop_realism_phase3_audit.py evals/run_preserved_baselines_audit.py
python -c "from amadeus_thread0.agent import agent; print(type(agent).__name__)"
```

- [ ] **Step 4: Run audits**

Run:

```powershell
python evals/run_living_loop_realism_phase2_audit.py --run-tag phase3-regression
python evals/run_living_loop_realism_phase3_audit.py --run-tag phase3-final
python evals/run_embodied_interaction_runtime_phase5_audit.py --run-tag living-loop-phase3-regression
git diff --check
```

- [ ] **Step 5: Merge and push**

Run from the original main worktree:

```powershell
git merge --ff-only codex/living-loop-runtime-realism-phase3
python -m pytest tests/test_living_loop_realism.py tests/test_living_loop_realism_phase3_audit.py tests/test_backend_api.py -k "living_loop_realism or artifact_behavior_alignment or embodied_interaction" -q
python evals/run_living_loop_realism_phase3_audit.py --run-tag post-merge
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
git push origin main
```
