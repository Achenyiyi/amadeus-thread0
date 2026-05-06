# Embodied Interaction Runtime Phase 5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only motive-to-behavior alignment readback layer that shows whether Phase 4 artifact motive hints are reflected in actual behavior action/plan semantics without mutating behavior.

**Architecture:** Create `artifact_behavior_alignment.py` as a focused runtime normalizer over Phase 4 `artifact_motive.motive_hints` plus existing `behavior_action` and `behavior_plan`. Attach the resulting readback through `embodied_interaction_runtime.py` to backend payload surfaces, audits, and preserved baselines while keeping model calls, memory writes, behavior mutation, live capture, frontend semantics, skills, browser, sandbox, and persona authority closed.

**Tech Stack:** Python 3, pytest, existing LangGraph backend payload dictionaries, deterministic `evals/` audit scripts.

---

## File Structure

- `amadeus_thread0/runtime/artifact_behavior_alignment.py`
  - New read-only normalizer from Phase 4 artifact motive hints to behavior alignment evidence.
  - Public API: `build_artifact_behavior_alignment_readback(artifact_motive, behavior_action, behavior_plan)`.
- `amadeus_thread0/runtime/embodied_interaction_runtime.py`
  - Import the alignment builder.
  - Add Phase 5 readiness constants.
  - Attach `artifact_behavior_alignment` through readback mirrors without changing actual motives.
- `tests/test_artifact_behavior_alignment.py`
  - Unit coverage for aligned, not-reflected, compatible workspace-review, empty, blocked, and inadmissible cases.
- `tests/test_embodied_interaction_runtime.py`
  - Integration coverage for Phase 5 readiness and readback mirrors.
- `tests/test_backend_api.py`
  - Backend envelope coverage proving `assistant_turn` and `event_round` carry Phase 5 alignment.
- `evals/run_embodied_interaction_runtime_phase5_audit.py`
  - New audit script reporting `embodied_interaction_runtime_phase5_ready`.
- `tests/test_embodied_interaction_runtime_phase5_audit.py`
  - Unit coverage for Phase 5 audit helpers.
- `evals/run_embodied_interaction_runtime_phase4_audit.py`
  - Preserve Phase 4 audit by checking the `artifact_motive_bridge_ready` sub-contract under later top-level readiness.
- `evals/run_preserved_baselines_audit.py`
  - Add Phase 5 as a preserved baseline.
- `tests/test_preserved_baselines_audit.py`
  - Add Phase 5 expected baseline and update embodied-interaction category count from `4` to `5`.
- `AGENTS.md`
  - Document Phase 5 as a preserved baseline after implementation.
- `docs/engineering/PROJECT_STRUCTURE.md`
  - Register the new runtime module and Phase 5 surfaces.
- `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
  - Record the Phase 5 readback-only decision.
- `program.md`
  - Update live ledger with files changed, validations run, and next step.

---

### Task 1: Artifact Behavior Alignment Unit Contract

**Files:**
- Create: `tests/test_artifact_behavior_alignment.py`
- Create: `amadeus_thread0/runtime/artifact_behavior_alignment.py`

- [x] **Step 1: Write failing tests**

Create `tests/test_artifact_behavior_alignment.py` with these cases:

```python
from amadeus_thread0.runtime.artifact_behavior_alignment import (
    build_artifact_behavior_alignment_readback,
)


def _artifact_motive(primary: str = "restore_access_continuity") -> dict:
    return {
        "status": "ready",
        "readiness_status": "artifact_motive_bridge_ready",
        "motive_hints": [
            {
                "hint_id": "artifact-motive-img-runtime-motive-1",
                "source_ref_id": "img-runtime-motive-1",
                "primary_motive_hint": primary,
                "authority": {
                    "source": "artifact_appraisal_evidence",
                    "model_api_called": False,
                    "memory_write_allowed": False,
                    "writeback_ready": False,
                    "behavior_mutation_allowed": False,
                },
            }
        ],
    }


def test_restore_access_hint_not_reflected_is_reported_without_mutation():
    readback = build_artifact_behavior_alignment_readback(
        _artifact_motive("restore_access_continuity"),
        {"primary_motive": "continue_workspace_task"},
        {"primary_motive": "continue_workspace_task"},
    )

    item = readback["alignment_items"][0]
    assert readback["schema"] == "artifact_behavior_alignment.v1"
    assert readback["status"] == "ready"
    assert readback["readiness_status"] == "artifact_behavior_alignment_ready"
    assert item["alignment_status"] == "advisory_not_reflected"
    assert item["alignment_reason"] == "artifact_motive_hint_not_reflected_in_behavior_plan"
    assert item["behavior_primary_motive"] == "continue_workspace_task"
    assert item["plan_primary_motive"] == "continue_workspace_task"
    assert item["behavior_mutation_applied"] is False
    assert item["authority"]["behavior_mutation_applied"] is False
    assert readback["alignment_summary"]["should_mutate_behavior"] is False
    assert readback["alignment_summary"]["should_write_memory"] is False
    assert readback["authority_boundary"]["memory_write_allowed"] is False
    assert readback["model_api_called"] is False
    assert readback["writeback_ready_count"] == 0
```

- [x] **Step 2: Run unit test to verify RED**

Run:

```powershell
python -m pytest tests/test_artifact_behavior_alignment.py -q
```

Expected: fails because `amadeus_thread0.runtime.artifact_behavior_alignment` does not exist.

- [x] **Step 3: Implement minimal alignment module**

Create `amadeus_thread0/runtime/artifact_behavior_alignment.py` with:

```python
from __future__ import annotations

from typing import Any

ARTIFACT_BEHAVIOR_ALIGNMENT_READY = "artifact_behavior_alignment_ready"
ARTIFACT_BEHAVIOR_ALIGNMENT_EMPTY = "artifact_behavior_alignment_empty"
ARTIFACT_BEHAVIOR_ALIGNMENT_BLOCKED = "artifact_behavior_alignment_blocked"

AUTHORITY_BOUNDARY = {
    "persona_core_mutation_allowed": False,
    "memory_write_allowed": False,
    "behavior_mutation_allowed": False,
    "external_mutation_allowed": False,
    "live_capture_enabled": False,
    "multimodal_model_api_called": False,
    "writeback_allowed": False,
}


def build_artifact_behavior_alignment_readback(
    artifact_motive: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None,
    behavior_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    motive = _dict_or_empty(artifact_motive)
    action = _dict_or_empty(behavior_action)
    plan = _dict_or_empty(behavior_plan)
    # normalize motive hints, reject inadmissible hints, build alignment_items,
    # then return the readback envelope with authority flags fixed to false.
```

Implementation requirements:

- accept hints only when `authority.source == "artifact_appraisal_evidence"`;
- reject hints if `model_api_called`, `memory_write_allowed`, `writeback_ready`, `behavior_mutation_allowed`, or `behavior_mutation_applied` is true;
- emit `causally_aligned` when hint and actual behavior/plan motives are directly or semantically compatible;
- emit `advisory_not_reflected` when a valid hint is visible but actual behavior/plan motives do not reflect it;
- emit `behavior_conflict_observed` only for explicit contradiction motives such as `ignore_access_friction` or `skip_artifact_review`;
- emit `empty` for no hints;
- emit `blocked` when upstream motive readback is blocked or all hints are inadmissible;
- keep all authority flags false and never alter input dictionaries.

- [x] **Step 4: Run unit test to verify GREEN**

Run:

```powershell
python -m pytest tests/test_artifact_behavior_alignment.py -q
```

Expected: all tests pass.

- [x] **Step 5: Commit task slice**

Run:

```powershell
git add tests/test_artifact_behavior_alignment.py amadeus_thread0/runtime/artifact_behavior_alignment.py
git commit -m "feat: add artifact behavior alignment readback"
```

---

### Task 2: Attach Alignment To Embodied Interaction Runtime

**Files:**
- Modify: `amadeus_thread0/runtime/embodied_interaction_runtime.py`
- Modify: `tests/test_embodied_interaction_runtime.py`
- Modify: `tests/test_backend_api.py`

- [x] **Step 1: Write failing integration tests**

Extend `tests/test_embodied_interaction_runtime.py` so a login/access artifact with behavior plan motive `continue_workspace_task` reports Phase 5 readiness, carries `artifact_behavior_alignment`, and leaves the original behavior plan motive intact:

```python
def test_artifact_behavior_alignment_reaches_readback_without_mutating_behavior_motive():
    turn = {
        "final_text": "嗯，我听见了。",
        "current_event": {
            "kind": "multimodal_observation",
            "perception": {"channel": "image"},
            "digital_body_hints": {"multimodal_sources": [{
                "source_id": "img-runtime-align-1",
                "modality": "image",
                "path": "fixtures/login.png",
                "consent_scope": "single_turn",
                "capture_method": "operator_attached_file",
                "semantic_summary": "A login dialog with an expired session warning.",
                "semantic_label": "login_prompt",
            }]},
        },
        "turn_appraisal": {"scene": "artifact_review"},
        "behavior_action": {"primary_motive": "continue_workspace_task"},
        "behavior_plan": {"primary_motive": "continue_workspace_task"},
        "interaction_carryover": {"embodied_context": {"kind": "multimodal_observation"}},
        "reconsolidation_snapshot": {"final_text": "嗯，我听见了。"},
    }

    readback = build_embodied_interaction_readback(turn)

    alignment = readback["artifact_behavior_alignment"]
    assert readback["readiness_status"] == "embodied_interaction_runtime_phase5_ready"
    assert alignment["readiness_status"] == "artifact_behavior_alignment_ready"
    assert alignment["alignment_items"][0]["alignment_status"] == "advisory_not_reflected"
    assert readback["turn_appraisal"]["behavior_alignment_evidence"]["alignment_items"][0]["source_ref_id"] == "img-runtime-align-1"
    assert readback["turn_appraisal"]["perception_semantics"]["behavior_alignment"]["alignment_items"][0]["source_ref_id"] == "img-runtime-align-1"
    assert readback["interaction_carryover"]["embodied_context"]["artifact_behavior_alignment"]["alignment_items"][0]["source_ref_id"] == "img-runtime-align-1"
    assert readback["behavior_plan"]["primary_motive"] == "continue_workspace_task"
    assert readback["behavior_plan"]["artifact_behavior_alignment"]["alignment_summary"]["should_mutate_behavior"] is False
```

Extend `tests/test_backend_api.py` with equivalent `assistant_turn` and `event_round` payload checks.

- [x] **Step 2: Run integration tests to verify RED**

Run:

```powershell
python -m pytest tests/test_embodied_interaction_runtime.py tests/test_backend_api.py -k "artifact_behavior_alignment or artifact_motive or artifact_appraisal or artifact_semantics or embodied_interaction" -q
```

Expected: fails because Phase 5 readback and mirrors do not exist.

- [x] **Step 3: Attach alignment readback**

Modify `amadeus_thread0/runtime/embodied_interaction_runtime.py` to:

- import `build_artifact_behavior_alignment_readback`;
- add:

```python
EMBODIED_INTERACTION_PHASE5_READINESS = "embodied_interaction_runtime_phase5_ready"
EMBODIED_INTERACTION_PHASE5_IN_PROGRESS = "embodied_interaction_runtime_phase5_in_progress"
```

- build:

```python
artifact_behavior_alignment = build_artifact_behavior_alignment_readback(
    artifact_motive,
    data.get("behavior_action"),
    data.get("behavior_plan"),
)
```

- promote top-level readiness to Phase 5 when `artifact_behavior_alignment.status == "ready"`;
- include `artifact_behavior_alignment` in top-level readback;
- mirror it to:
  - `current_event.perception.behavior_alignment`
  - `turn_appraisal.behavior_alignment_evidence`
  - `turn_appraisal.perception_semantics.behavior_alignment`
  - `interaction_carryover.embodied_context.artifact_behavior_alignment`
  - `behavior_plan.artifact_behavior_alignment`
- preserve `behavior_action.primary_motive`, `behavior_plan.primary_motive`, `final_text`, and `reconsolidation_snapshot.final_text`.

- [x] **Step 4: Run integration tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_artifact_behavior_alignment.py tests/test_embodied_interaction_runtime.py tests/test_backend_api.py -k "artifact_behavior_alignment or artifact_motive or artifact_appraisal or artifact_semantics or embodied_interaction or living_loop_realism" -q
```

Expected: selected tests pass.

- [x] **Step 5: Commit task slice**

Run:

```powershell
git add amadeus_thread0/runtime/embodied_interaction_runtime.py tests/test_embodied_interaction_runtime.py tests/test_backend_api.py
git commit -m "feat: attach artifact behavior alignment"
```

---

### Task 3: Audit And Preserved Baseline

**Files:**
- Create: `evals/run_embodied_interaction_runtime_phase5_audit.py`
- Create: `tests/test_embodied_interaction_runtime_phase5_audit.py`
- Modify: `evals/run_embodied_interaction_runtime_phase4_audit.py`
- Modify: `evals/run_preserved_baselines_audit.py`
- Modify: `tests/test_preserved_baselines_audit.py`

- [x] **Step 1: Write failing audit tests**

Create `tests/test_embodied_interaction_runtime_phase5_audit.py` with:

```python
from evals.run_embodied_interaction_runtime_phase5_audit import build_report, render_markdown


def test_phase5_audit_reports_ready_without_behavior_mutation():
    report = build_report(run_id="phase5-test")

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "embodied_interaction_runtime_phase5_ready"
    assert report["summary"]["alignment_count"] >= 1
    assert report["summary"]["behavior_mutation_applied"] is False
    assert report["summary"]["model_api_called"] is False
    assert report["summary"]["writeback_ready_count"] == 0
    assert report["summary"]["should_write_memory"] is False
```

Update `tests/test_preserved_baselines_audit.py` so expected ids include `embodied_interaction_runtime_phase5` and embodied-interaction category passed count is `5`.

- [x] **Step 2: Run audit tests to verify RED**

Run:

```powershell
python -m pytest tests/test_embodied_interaction_runtime_phase5_audit.py tests/test_preserved_baselines_audit.py -q
```

Expected: fails because Phase 5 audit and baseline row do not exist.

- [x] **Step 3: Implement audit and baseline row**

Create an audit script with scenarios:

- `artifact_motive_alignment_reports_not_reflected_without_mutation`
- `artifact_motive_alignment_reports_causal_alignment`
- `backend_payload_carries_behavior_alignment`
- `blocked_live_capture_does_not_create_behavior_alignment`
- `phase4_motive_contract_remains_preserved`
- `alignment_does_not_write_memory_or_call_model_api`

Add this baseline spec:

```python
{
    "id": "embodied_interaction_runtime_phase5",
    "prefix": "embodied-interaction-runtime-phase5-audit-",
    "expected_readiness": "embodied_interaction_runtime_phase5_ready",
    "category": "embodied_interaction",
}
```

Adjust Phase 4 audit to assert its sub-contract remains ready:

```python
motive = _dict_or_empty(readback.get("artifact_motive"))
passed = motive.get("readiness_status") == "artifact_motive_bridge_ready"
```

- [x] **Step 4: Run audit tests and audit**

Run:

```powershell
python -m pytest tests/test_embodied_interaction_runtime_phase4_audit.py tests/test_embodied_interaction_runtime_phase5_audit.py tests/test_preserved_baselines_audit.py -q
python evals/run_embodied_interaction_runtime_phase5_audit.py --run-tag phase5-dev
```

Expected: tests pass and audit prints `readiness=embodied_interaction_runtime_phase5_ready`.

- [x] **Step 5: Commit task slice**

Run:

```powershell
git add evals/run_embodied_interaction_runtime_phase5_audit.py tests/test_embodied_interaction_runtime_phase5_audit.py evals/run_embodied_interaction_runtime_phase4_audit.py evals/run_preserved_baselines_audit.py tests/test_preserved_baselines_audit.py
git commit -m "test: audit embodied interaction phase 5"
```

---

### Task 4: Documentation And Ledger

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `program.md`
- Modify: `docs/superpowers/plans/2026-05-06-amadeus-k-rolling-closure-roadmap.md`
- Modify: `docs/superpowers/plans/2026-05-06-embodied-interaction-runtime-phase5.md`

- [x] **Step 1: Update docs**

Document that `Embodied Interaction Runtime Phase 5`:

- reports `embodied_interaction_runtime_phase5_ready`;
- consumes Phase 4 artifact motive hints and actual behavior action/plan motives;
- emits read-only `artifact_behavior_alignment`;
- distinguishes `causally_aligned`, `advisory_not_reflected`, and `behavior_conflict_observed`;
- does not mutate behavior, memory, persona core, frontend semantics, skills, browser, sandbox, execution authority, or live capture.

- [x] **Step 2: Mark plan checkboxes complete**

Update this plan file as task work completes.

- [x] **Step 3: Commit docs**

Run:

```powershell
git add AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md docs/superpowers/plans/2026-05-06-amadeus-k-rolling-closure-roadmap.md docs/superpowers/plans/2026-05-06-embodied-interaction-runtime-phase5.md
git commit -m "docs: close embodied interaction phase 5"
```

---

### Task 5: Final Verification, Merge, And Push

**Files:**
- No new implementation files. This task verifies and integrates all prior task slices.

- [ ] **Step 1: Run focused regression**

Run:

```powershell
python -m pytest tests/test_artifact_behavior_alignment.py tests/test_artifact_motive_bridge.py tests/test_artifact_appraisal_bridge.py tests/test_artifact_perception_semantics.py tests/test_embodied_interaction_runtime.py tests/test_embodied_interaction_runtime_phase4_audit.py tests/test_embodied_interaction_runtime_phase5_audit.py tests/test_multimodal_sources.py -q
```

Expected: all pass.

- [ ] **Step 2: Run backend payload regression**

Run:

```powershell
python -m pytest tests/test_backend_api.py -k "artifact_behavior_alignment or artifact_motive or artifact_appraisal or artifact_semantics or embodied_interaction or living_loop_realism" -q
python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py tests/test_tool_approval_policy.py -q
python -m pytest tests/test_memory_guard.py tests/test_session_orchestrator.py -q
```

Expected: all pass.

- [ ] **Step 3: Run compile and graph checks**

Run:

```powershell
python -m py_compile amadeus_thread0/agent.py amadeus_thread0/graph.py amadeus_thread0/runtime/artifact_perception_semantics.py amadeus_thread0/runtime/artifact_appraisal_bridge.py amadeus_thread0/runtime/artifact_motive_bridge.py amadeus_thread0/runtime/artifact_behavior_alignment.py amadeus_thread0/runtime/embodied_interaction_runtime.py amadeus_thread0/runtime/backend_api.py evals/run_embodied_interaction_runtime_phase4_audit.py evals/run_embodied_interaction_runtime_phase5_audit.py evals/run_preserved_baselines_audit.py
python -c "from amadeus_thread0.agent import agent; print(type(agent).__name__)"
```

Expected: compile succeeds and graph check prints `CompiledStateGraph`.

- [ ] **Step 4: Run audits**

Run:

```powershell
python evals/run_embodied_interaction_runtime_phase4_audit.py --run-tag phase5-regression
python evals/run_embodied_interaction_runtime_phase5_audit.py --run-tag phase5-final
python evals/run_living_loop_realism_phase2_audit.py --run-tag embodied-phase5-regression
git diff --check
```

Expected: Phase 4 and Phase 5 audits pass; living-loop phase 2 remains ready; diff check passes.

- [ ] **Step 5: Merge and push**

Run from the original main worktree:

```powershell
git switch main
git merge --ff-only codex/embodied-interaction-runtime-phase5
python -m pytest tests/test_artifact_behavior_alignment.py tests/test_embodied_interaction_runtime.py tests/test_embodied_interaction_runtime_phase5_audit.py tests/test_backend_api.py -k "artifact_behavior_alignment or artifact_motive or artifact_appraisal or artifact_semantics or embodied_interaction or living_loop_realism" -q
python evals/run_embodied_interaction_runtime_phase5_audit.py --run-tag post-merge
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
git push origin main
```

Expected: post-merge verification passes and `main` pushes successfully.
