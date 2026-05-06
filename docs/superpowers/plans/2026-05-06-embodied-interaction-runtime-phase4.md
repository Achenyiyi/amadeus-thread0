# Embodied Interaction Runtime Phase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert Phase 3 artifact appraisal evidence into bounded, read-only motive/goal advisory readback while preserving all prior embodied interaction and backend baselines.

**Architecture:** Add a focused `artifact_motive_bridge` runtime module that consumes Phase 3 `artifact_appraisal.evidence_items`, not raw artifact metadata. Attach its output through the existing `embodied_interaction` payload adapter as advisory readback only; do not mutate graph generation, `behavior_action.primary_motive`, memory facts, persona core, browser/tool/sandbox authority, or frontend-owned semantics.

**Tech Stack:** Python 3, pytest, existing LangGraph backend payload surfaces, deterministic local audit scripts.

---

## File Structure

- `amadeus_thread0/runtime/artifact_motive_bridge.py`
  - New bounded normalizer from Phase 3 appraisal evidence to motive/goal hints.
  - Public API: `build_artifact_motive_readback(artifact_appraisal)`.
- `amadeus_thread0/runtime/embodied_interaction_runtime.py`
  - Import and attach the motive bridge.
  - Add Phase 4 readiness constants.
  - Mirror advisory hints into existing backend readback surfaces without replacing behavior motives.
- `tests/test_artifact_motive_bridge.py`
  - Unit coverage for access-friction hints, ordinary task-relevance hints, empty/blocked readbacks, and inadmissible evidence.
- `tests/test_embodied_interaction_runtime.py`
  - Integration coverage for Phase 4 readiness and readback mirrors.
- `tests/test_backend_api.py`
  - Backend payload coverage proving `assistant_turn` and `event_round` carry artifact motive hints.
- `evals/run_embodied_interaction_runtime_phase4_audit.py`
  - New audit script reporting `embodied_interaction_runtime_phase4_ready`.
- `tests/test_embodied_interaction_runtime_phase4_audit.py`
  - Unit coverage for Phase 4 audit helpers.
- `evals/run_preserved_baselines_audit.py`
  - Add Phase 4 as a preserved baseline.
- `tests/test_preserved_baselines_audit.py`
  - Update expected baseline set and embodied-interaction category count.
- `AGENTS.md`
  - Document Phase 4 as a closed/preserved baseline after implementation.
- `docs/engineering/PROJECT_STRUCTURE.md`
  - Register the new runtime bridge ownership.
- `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
  - Record the decision that Phase 4 is advisory/readback-only.
- `program.md`
  - Update the live run ledger with files changed, validation, and next step.

---

### Task 1: Artifact Motive Bridge Normalization

**Files:**
- Create: `tests/test_artifact_motive_bridge.py`
- Create: `amadeus_thread0/runtime/artifact_motive_bridge.py`

- [x] **Step 1: Write the failing tests**

Add tests covering the desired public API:

```python
from amadeus_thread0.runtime.artifact_motive_bridge import build_artifact_motive_readback


def test_access_friction_appraisal_evidence_creates_restore_access_hint():
    readback = build_artifact_motive_readback({
        "status": "ready",
        "evidence_items": [{
            "evidence_id": "artifact-evidence-img-runtime-appraisal-1",
            "source_ref_id": "img-runtime-appraisal-1",
            "source_kind": "image_file",
            "semantic_label": "login_prompt",
            "summary": "A login dialog with an expired session warning.",
            "appraisal_axes": ["task_relevance", "access_friction"],
            "suggested_appraisal_delta": {
                "scene": "artifact_review",
                "task_relevance": "high",
                "access_friction": True,
                "boundary_condition": "access_or_session_friction",
            },
            "authority": {
                "source": "approved_metadata",
                "model_api_called": False,
                "memory_write_allowed": False,
                "writeback_ready": False,
            },
        }],
    })

    hint = readback["motive_hints"][0]
    assert readback["status"] == "ready"
    assert readback["readiness_status"] == "artifact_motive_bridge_ready"
    assert hint["primary_motive_hint"] == "restore_access_continuity"
    assert hint["motive_tension_hint"] == "task_continuity_vs_access_friction"
    assert hint["goal_frame_hint"] == "Treat the artifact as an access/session condition to resolve before continuing the task."
    assert hint["authority"]["behavior_mutation_allowed"] is False
    assert readback["motive_summary"]["goal_bias"] == "resolve_access_before_task_continuation"
    assert readback["motive_summary"]["should_mutate_behavior"] is False
    assert readback["motive_summary"]["should_write_memory"] is False
```

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_artifact_motive_bridge.py -q
```

Expected: fails because `amadeus_thread0.runtime.artifact_motive_bridge` does not exist.

- [x] **Step 3: Implement the bridge**

Create `amadeus_thread0/runtime/artifact_motive_bridge.py` with:

```python
from __future__ import annotations

from typing import Any

ARTIFACT_MOTIVE_BRIDGE_READY = "artifact_motive_bridge_ready"
ARTIFACT_MOTIVE_BRIDGE_EMPTY = "artifact_motive_bridge_empty"
ARTIFACT_MOTIVE_BRIDGE_BLOCKED = "artifact_motive_bridge_blocked"

AUTHORITY_BOUNDARY = {
    "persona_core_mutation_allowed": False,
    "memory_write_allowed": False,
    "behavior_mutation_allowed": False,
    "external_mutation_allowed": False,
    "live_capture_enabled": False,
    "multimodal_model_api_called": False,
    "writeback_allowed": False,
}


def build_artifact_motive_readback(artifact_appraisal: dict[str, Any] | None) -> dict[str, Any]:
    ...
```

The implementation must:

- accept only Phase 3 evidence with `authority.source == "approved_metadata"`;
- block evidence if `model_api_called`, `memory_write_allowed`, or `writeback_ready` is true;
- produce `restore_access_continuity` for access-friction evidence;
- produce `continue_artifact_review` for high task-relevance evidence without access friction;
- return `blocked` when upstream appraisal is blocked and no hint can be emitted;
- return `empty` when no admissible evidence exists;
- keep all authority flags false.

- [x] **Step 4: Run bridge tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_artifact_motive_bridge.py -q
```

Expected: all tests pass.

- [x] **Step 5: Commit task slice**

Run:

```powershell
git add tests/test_artifact_motive_bridge.py amadeus_thread0/runtime/artifact_motive_bridge.py
git commit -m "feat: add artifact motive bridge"
```

---

### Task 2: Attach Motive Bridge To Embodied Interaction Runtime

**Files:**
- Modify: `amadeus_thread0/runtime/embodied_interaction_runtime.py`
- Modify: `tests/test_embodied_interaction_runtime.py`
- Modify: `tests/test_backend_api.py`

- [x] **Step 1: Write failing integration tests**

Extend `tests/test_embodied_interaction_runtime.py` so login/access artifact evidence now reports Phase 4 readiness and mirrors motive hints:

```python
def test_artifact_motive_hints_reach_readback_surfaces_without_replacing_behavior_motive():
    turn = {
        "final_text": "嗯，我听见了。",
        "current_event": {
            "kind": "multimodal_observation",
            "perception": {"channel": "image"},
            "digital_body_hints": {"multimodal_sources": [{
                "source_id": "img-runtime-motive-1",
                "modality": "image",
                "path": "fixtures/login.png",
                "consent_scope": "single_turn",
                "capture_method": "operator_attached_file",
                "semantic_summary": "A login dialog with an expired session warning.",
                "semantic_label": "login_prompt",
            }]},
        },
        "turn_appraisal": {"scene": "artifact_review"},
        "behavior_plan": {"primary_motive": "continue_workspace_task"},
        "interaction_carryover": {"embodied_context": {"kind": "multimodal_observation"}},
        "reconsolidation_snapshot": {"final_text": "嗯，我听见了。"},
    }

    readback = build_embodied_interaction_readback(turn)

    assert readback["readiness_status"] == "embodied_interaction_runtime_phase4_ready"
    assert readback["artifact_motive"]["motive_hints"][0]["primary_motive_hint"] == "restore_access_continuity"
    assert readback["current_event"]["perception"]["motive_hints"][0]["source_ref_id"] == "img-runtime-motive-1"
    assert readback["turn_appraisal"]["motive_evidence"][0]["source_ref_id"] == "img-runtime-motive-1"
    assert readback["turn_appraisal"]["perception_semantics"]["motive_hints"][0]["source_ref_id"] == "img-runtime-motive-1"
    assert readback["interaction_carryover"]["embodied_context"]["artifact_motive_hints"][0]["source_ref_id"] == "img-runtime-motive-1"
    assert readback["behavior_plan"]["primary_motive"] == "continue_workspace_task"
    assert readback["behavior_plan"]["artifact_motive_hints"][0]["primary_motive_hint"] == "restore_access_continuity"
```

Extend `tests/test_backend_api.py` with equivalent `assistant_turn` and `event_round` payload checks.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_embodied_interaction_runtime.py tests/test_backend_api.py -k "artifact_motive or artifact_appraisal or artifact_semantics or embodied_interaction" -q
```

Expected: fails because Phase 4 readback and mirrors do not exist.

- [x] **Step 3: Attach runtime bridge**

Modify `amadeus_thread0/runtime/embodied_interaction_runtime.py` to:

- import `build_artifact_motive_readback`;
- add constants:

```python
EMBODIED_INTERACTION_PHASE4_READINESS = "embodied_interaction_runtime_phase4_ready"
EMBODIED_INTERACTION_PHASE4_IN_PROGRESS = "embodied_interaction_runtime_phase4_in_progress"
```

- build `artifact_motive = build_artifact_motive_readback(artifact_appraisal)`;
- promote top-level readiness to Phase 4 when `artifact_motive.status == "ready"`;
- include `artifact_motive` in the readback;
- mirror motive hints to:
  - `current_event.perception.motive_hints`
  - `turn_appraisal.motive_evidence`
  - `turn_appraisal.perception_semantics.motive_hints`
  - `interaction_carryover.embodied_context.artifact_motive_hints`
  - `behavior_plan.artifact_motive_hints`
- preserve existing `behavior_plan.primary_motive` and all `behavior_action` motive fields.

- [x] **Step 4: Run integration tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_artifact_motive_bridge.py tests/test_embodied_interaction_runtime.py tests/test_backend_api.py -k "artifact_motive or artifact_appraisal or artifact_semantics or embodied_interaction or living_loop_realism" -q
```

Expected: all selected tests pass.

- [x] **Step 5: Commit task slice**

Run:

```powershell
git add amadeus_thread0/runtime/embodied_interaction_runtime.py tests/test_embodied_interaction_runtime.py tests/test_backend_api.py
git commit -m "feat: attach artifact motive readback"
```

---

### Task 3: Phase 4 Audit And Preserved Baseline

**Files:**
- Create: `evals/run_embodied_interaction_runtime_phase4_audit.py`
- Create: `tests/test_embodied_interaction_runtime_phase4_audit.py`
- Modify: `evals/run_preserved_baselines_audit.py`
- Modify: `tests/test_preserved_baselines_audit.py`

- [x] **Step 1: Write failing audit tests**

Add tests that assert:

```python
from evals.run_embodied_interaction_runtime_phase4_audit import build_report, render_markdown


def test_phase4_audit_reports_ready_when_motive_hints_are_readonly():
    report = build_report(run_id="phase4-test")
    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "embodied_interaction_runtime_phase4_ready"
    assert report["summary"]["hint_count"] >= 1
    assert report["summary"]["behavior_mutation_allowed"] is False
    assert report["summary"]["model_api_called"] is False
    assert report["summary"]["writeback_ready_count"] == 0
```

Update preserved baseline tests to include `embodied_interaction_runtime_phase4` and expect embodied-interaction category pass count `4`.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_embodied_interaction_runtime_phase4_audit.py tests/test_preserved_baselines_audit.py -q
```

Expected: fails because the audit module and preserved baseline row do not exist.

- [x] **Step 3: Implement audit and baseline row**

Create an audit script with scenarios:

- `artifact_appraisal_becomes_motive_hint`
- `access_friction_biases_motive_without_behavior_mutation`
- `backend_payload_carries_artifact_motive`
- `blocked_live_capture_does_not_create_motive_hint`
- `artifact_motive_does_not_write_memory_or_call_model_api`
- `phase3_appraisal_contract_remains_preserved`

Add this baseline spec:

```python
{
    "id": "embodied_interaction_runtime_phase4",
    "prefix": "embodied-interaction-runtime-phase4-audit-",
    "expected_readiness": "embodied_interaction_runtime_phase4_ready",
    "category": "embodied_interaction",
}
```

- [x] **Step 4: Run audit tests and audit**

Run:

```powershell
python -m pytest tests/test_embodied_interaction_runtime_phase4_audit.py tests/test_preserved_baselines_audit.py -q
python evals/run_embodied_interaction_runtime_phase4_audit.py --run-tag phase4-dev
```

Expected: tests pass and audit prints `readiness=embodied_interaction_runtime_phase4_ready`.

- [x] **Step 5: Commit task slice**

Run:

```powershell
git add evals/run_embodied_interaction_runtime_phase4_audit.py tests/test_embodied_interaction_runtime_phase4_audit.py evals/run_preserved_baselines_audit.py tests/test_preserved_baselines_audit.py
git commit -m "test: audit embodied interaction phase 4"
```

---

### Task 4: Documentation And Ledger

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `program.md`
- Modify: `docs/superpowers/plans/2026-05-06-embodied-interaction-runtime-phase4.md`

- [x] **Step 1: Update docs**

Document that `Embodied Interaction Runtime Phase 4`:

- reports `embodied_interaction_runtime_phase4_ready`;
- consumes Phase 3 appraisal evidence only;
- emits read-only motive/goal advisory hints;
- does not mutate actual behavior motives/plans except adding advisory `artifact_motive_hints`;
- does not call multimodal model APIs;
- does not write memory;
- does not open live capture;
- does not mutate persona core or widen execution authority.

- [x] **Step 2: Mark plan checkboxes complete**

Update this plan file as each task is finished.

- [x] **Step 3: Commit docs**

Run:

```powershell
git add AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md docs/superpowers/plans/2026-05-06-embodied-interaction-runtime-phase4.md
git commit -m "docs: close embodied interaction phase 4"
```

---

### Task 5: Final Verification, Merge, And Push

**Files:**
- No new implementation files. This task verifies and integrates all prior task slices.

- [ ] **Step 1: Run focused regression**

Run:

```powershell
python -m pytest tests/test_artifact_motive_bridge.py tests/test_artifact_appraisal_bridge.py tests/test_artifact_perception_semantics.py tests/test_embodied_interaction_runtime.py tests/test_embodied_interaction_runtime_phase3_audit.py tests/test_embodied_interaction_runtime_phase4_audit.py tests/test_multimodal_sources.py -q
```

Expected: all pass.

- [ ] **Step 2: Run backend payload regression**

Run:

```powershell
python -m pytest tests/test_backend_api.py -k "artifact_motive or artifact_appraisal or artifact_semantics or embodied_interaction or living_loop_realism" -q
python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py tests/test_tool_approval_policy.py -q
python -m pytest tests/test_memory_guard.py tests/test_session_orchestrator.py -q
```

Expected: all pass.

- [ ] **Step 3: Run compile and graph checks**

Run:

```powershell
python -m py_compile amadeus_thread0/agent.py amadeus_thread0/graph.py amadeus_thread0/runtime/artifact_perception_semantics.py amadeus_thread0/runtime/artifact_appraisal_bridge.py amadeus_thread0/runtime/artifact_motive_bridge.py amadeus_thread0/runtime/embodied_interaction_runtime.py amadeus_thread0/runtime/backend_api.py evals/run_embodied_interaction_runtime_phase3_audit.py evals/run_embodied_interaction_runtime_phase4_audit.py evals/run_preserved_baselines_audit.py
python -c "from amadeus_thread0.agent import agent; print(type(agent).__name__)"
```

Expected: compile succeeds and graph check prints `CompiledStateGraph`.

- [ ] **Step 4: Run audits**

Run:

```powershell
python evals/run_embodied_interaction_runtime_phase3_audit.py --run-tag phase4-regression
python evals/run_embodied_interaction_runtime_phase4_audit.py --run-tag phase4-final
python evals/run_living_loop_realism_phase2_audit.py --run-tag embodied-phase4-regression
git diff --check
```

Expected: Phase 3 and Phase 4 audits pass; living-loop phase 2 remains ready; diff check passes.

- [ ] **Step 5: Merge and push**

Run from the original main worktree:

```powershell
git switch main
git merge --ff-only codex/embodied-interaction-runtime-phase4
python -m pytest tests/test_artifact_motive_bridge.py tests/test_embodied_interaction_runtime.py tests/test_embodied_interaction_runtime_phase4_audit.py tests/test_backend_api.py -k "artifact_motive or artifact_appraisal or artifact_semantics or embodied_interaction or living_loop_realism" -q
python evals/run_embodied_interaction_runtime_phase4_audit.py --run-tag post-merge
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
git push origin main
```

Expected: post-merge verification passes and `main` pushes successfully.

