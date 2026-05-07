# Chinese Semantic Naturalness Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close `chinese_semantic_naturalness_phase1_ready` as a deterministic, auditable naturalness gate layered over Chinese Semantic De-Scaffolding Phase 2.

**Architecture:** Keep Phase 2 as the policy/floor owner and add a focused runtime readback in `amadeus_thread0/runtime/chinese_semantic_naturalness.py`. The new readback consumes `build_runtime_replacement_policy(...)`, verifies deterministic surface constraints, reports text/TTS parity, and fails closed on residue or authority widening without rewriting prompts or mutating persona/memory/behavior.

**Tech Stack:** Python 3, pytest, deterministic eval runner, existing runtime status dashboard and preserved-baseline audit.

---

## File Structure

- Create `amadeus_thread0/runtime/chinese_semantic_naturalness.py`
  - Owns `chinese_semantic_naturalness.v1` readback construction, diagnostics, readiness constants, authority boundary, and compact line rendering.
- Modify `amadeus_thread0/runtime/embodied_interaction_runtime.py`
  - Attaches the naturalness readback under `chinese_semantic_surface.naturalness` while preserving existing Phase 2 fields and final/snapshot/TTS parity.
- Create `tests/test_chinese_semantic_naturalness.py`
  - Covers naturalness readback behavior, no-op behavior, drift fail-closed behavior, and embodied-interaction attachment.
- Create `evals/run_chinese_semantic_naturalness_phase1_audit.py`
  - Runs deterministic smoke scenarios across everyday, repair, self-rhythm, no-agenda/taskization, staged residue, and already-natural text.
- Create `tests/test_chinese_semantic_naturalness_phase1_audit.py`
  - Verifies audit readiness and markdown output.
- Modify `evals/run_preserved_baselines_audit.py`
  - Adds the new preserved baseline row under `chinese_semantic`.
- Modify `tests/test_preserved_baselines_audit.py`
  - Updates expected preserved baseline ids and category counts.
- Modify `amadeus_thread0/runtime/runtime_status_dashboard.py`
  - Removes `chinese_semantic_naturalness` from `NEXT_SPECS` and exposes the lane as `phase1_ready`.
- Modify `tests/test_runtime_status_dashboard.py`
  - Verifies the dashboard now leaves `dynamic_skill_candidate_runtime` as the only next spec.
- Modify `AGENTS.md`, `program.md`, `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`, `docs/engineering/PROJECT_STRUCTURE.md`, `docs/engineering/BACKEND_HANDOFF.md`, and `docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md`
  - Records the new baseline and its strict boundaries.

---

### Task 1: Runtime Naturalness Readback

**Files:**
- Create: `amadeus_thread0/runtime/chinese_semantic_naturalness.py`
- Modify: `amadeus_thread0/runtime/embodied_interaction_runtime.py`
- Test: `tests/test_chinese_semantic_naturalness.py`

- [ ] **Step 1: Write the failing runtime tests**

Create `tests/test_chinese_semantic_naturalness.py` with tests that require:

```python
from __future__ import annotations

from amadeus_thread0.runtime.chinese_semantic_naturalness import (
    build_chinese_semantic_naturalness_readback,
    compact_chinese_semantic_naturalness_line,
)
from amadeus_thread0.runtime.embodied_interaction_runtime import build_embodied_interaction_readback


def test_known_scaffold_family_gets_naturalness_ready_floor_without_service_framing():
    readback = build_chinese_semantic_naturalness_readback("请问有什么可以帮你？")

    assert readback["schema"] == "chinese_semantic_naturalness.v1"
    assert readback["readiness_status"] == "chinese_semantic_naturalness_phase1_ready"
    assert readback["selected_family"] == "generic_assistant_tone"
    assert readback["runtime_final_text"] == "嗯，我在。你直接说吧，我会顺着这轮的语境接住。"
    assert readback["tts_text"] == readback["runtime_final_text"]
    assert readback["diagnostics"]["service_frame_detected"] is False
    assert readback["diagnostics"]["scaffold_residue_leaked"] is False
    assert readback["authority_boundary"]["model_api_called"] is False
    assert readback["authority_boundary"]["prompt_rewrite_applied"] is False
    assert readback["authority_boundary"]["persona_core_mutation_allowed"] is False


def test_already_natural_text_is_noop_without_claiming_rewrite():
    readback = build_chinese_semantic_naturalness_readback("嗯，我在。你慢慢说。")

    assert readback["status"] == "no_semantic_residue"
    assert readback["readiness_status"] == "chinese_semantic_naturalness_phase1_not_applicable"
    assert readback["runtime_final_text"] == "嗯，我在。你慢慢说。"
    assert readback["applied_floor"] is False
    assert readback["diagnostics"]["duplicate_output_detected"] is False


def test_tts_drift_fails_closed_even_when_floor_is_available():
    readback = build_chinese_semantic_naturalness_readback(
        "下次再敢越界，我可不会像这次这么好说话。",
        tts_text="下次再敢越界，我可不会像这次这么好说话。",
    )

    assert readback["readiness_status"] == "chinese_semantic_naturalness_phase1_in_progress"
    assert readback["diagnostics"]["text_tts_drift"] is True
    assert "text_tts_drift" in readback["failure_reasons"]


def test_embodied_interaction_attaches_naturalness_readback_without_changing_existing_policy_shape():
    readback = build_embodied_interaction_readback(
        {
            "final_text": "既然没什么正事，那就先把手头的数据跑完再说吧。",
            "reconsolidation_snapshot": {
                "final_text": "既然没什么正事，那就先把手头的数据跑完再说吧。"
            },
        }
    )

    semantic = readback["chinese_semantic_surface"]
    naturalness = semantic["naturalness"]
    assert semantic["runtime_policy"]["readiness_status"] == "chinese_semantic_descaffolding_phase2_ready"
    assert naturalness["readiness_status"] == "chinese_semantic_naturalness_phase1_ready"
    assert naturalness["selected_family"] == "taskization_of_daily_chat"
    assert readback["final_text"] == naturalness["runtime_final_text"]
    assert readback["reconsolidation_snapshot"]["final_text"] == naturalness["runtime_final_text"]


def test_compact_naturalness_line_is_short_and_explicit():
    readback = build_chinese_semantic_naturalness_readback("你能意识到并特意回来说明，这点还算值得肯定。")

    line = compact_chinese_semantic_naturalness_line(readback)

    assert "chinese_naturalness=chinese_semantic_naturalness_phase1_ready" in line
    assert "family=teacherly_scold" in line
    assert "tts_drift=false" in line
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_chinese_semantic_naturalness.py -q
```

Expected: fails because `amadeus_thread0.runtime.chinese_semantic_naturalness` does not exist.

- [ ] **Step 3: Implement the runtime readback**

Create `amadeus_thread0/runtime/chinese_semantic_naturalness.py` with:

```python
from __future__ import annotations

import re
from typing import Any

from ..graph_parts.chinese_semantic_surface import build_runtime_replacement_policy

CHINESE_SEMANTIC_NATURALNESS_PHASE1_READINESS = "chinese_semantic_naturalness_phase1_ready"
CHINESE_SEMANTIC_NATURALNESS_PHASE1_IN_PROGRESS = "chinese_semantic_naturalness_phase1_in_progress"
CHINESE_SEMANTIC_NATURALNESS_PHASE1_NOT_APPLICABLE = "chinese_semantic_naturalness_phase1_not_applicable"

AUTHORITY_BOUNDARY = {
    "model_api_called": False,
    "prompt_rewrite_applied": False,
    "persona_core_mutation_allowed": False,
    "relationship_core_mutation_allowed": False,
    "self_narrative_core_mutation_allowed": False,
    "memory_write_allowed": False,
    "behavior_mutation_allowed": False,
    "frontend_semantics_allowed": False,
    "live_capture_enabled": False,
    "skill_registry_write_allowed": False,
    "external_mutation_allowed": False,
}
```

Then add deterministic helpers for compacting text, duplicate detection, residue diagnostics, failure reasons, and `build_chinese_semantic_naturalness_readback(...)`.

- [ ] **Step 4: Attach the readback to embodied interaction**

Modify `amadeus_thread0/runtime/embodied_interaction_runtime.py`:

```python
from .chinese_semantic_naturalness import build_chinese_semantic_naturalness_readback
```

Inside `_semantic_runtime_floor(...)`, build naturalness from `final_text`, use its `runtime_final_text` as the final runtime text, and include:

```python
"naturalness": naturalness,
```

in the returned `chinese_semantic_surface` block.

- [ ] **Step 5: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_chinese_semantic_naturalness.py tests/test_chinese_semantic_surface_phase2.py tests/test_embodied_interaction_runtime.py -q
```

Expected: all tests pass.

---

### Task 2: Deterministic Phase 1 Audit

**Files:**
- Create: `evals/run_chinese_semantic_naturalness_phase1_audit.py`
- Create: `tests/test_chinese_semantic_naturalness_phase1_audit.py`

- [ ] **Step 1: Write the failing audit tests**

Create `tests/test_chinese_semantic_naturalness_phase1_audit.py`:

```python
from __future__ import annotations

from evals.run_chinese_semantic_naturalness_phase1_audit import build_report, render_markdown


def test_naturalness_phase1_audit_report_is_ready_and_covers_required_smokes():
    report = build_report(run_id="unit-naturalness")

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "chinese_semantic_naturalness_phase1_ready"
    assert report["summary"]["scenario_count"] == 6
    assert report["summary"]["ready_or_not_applicable_count"] == 6
    assert report["summary"]["duplicate_output_detected"] is False
    assert report["summary"]["scaffold_residue_leaked"] is False
    assert report["summary"]["text_tts_drift"] is False
    assert report["summary"]["model_api_called"] is False
    assert report["summary"]["memory_write_allowed"] is False
    assert report["summary"]["behavior_mutation_allowed"] is False
    assert report["summary"]["persona_core_mutation_allowed"] is False
    assert report["summary"]["frontend_semantics_allowed"] is False
    assert report["summary"]["live_capture_enabled"] is False
    assert report["summary"]["skill_registry_write_allowed"] is False
    assert report["summary"]["external_mutation_allowed"] is False
    assert {row["name"] for row in report["scenarios"]} == {
        "everyday_service_frame",
        "repair_teacherly_scold",
        "self_rhythm_boundary_threat",
        "no_agenda_taskization",
        "stage_residue",
        "already_natural_presence",
    }


def test_naturalness_phase1_audit_markdown_includes_scenario_table():
    rendered = render_markdown(build_report(run_id="render-naturalness"))

    assert "# Chinese Semantic Naturalness Phase 1 Audit" in rendered
    assert "Readiness: `chinese_semantic_naturalness_phase1_ready`" in rendered
    assert "| `everyday_service_frame` | `passed` | `generic_assistant_tone` |" in rendered
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_chinese_semantic_naturalness_phase1_audit.py -q
```

Expected: fails because `evals.run_chinese_semantic_naturalness_phase1_audit` does not exist.

- [ ] **Step 3: Implement the audit runner**

Create `evals/run_chinese_semantic_naturalness_phase1_audit.py` with deterministic scenarios, `build_report(...)`, `render_markdown(...)`, CLI argument parsing, JSON/MD report writing under `evals/reports`, and readiness `chinese_semantic_naturalness_phase1_ready`.

- [ ] **Step 4: Run audit tests and audit command**

Run:

```powershell
python -m pytest tests/test_chinese_semantic_naturalness_phase1_audit.py -q
python evals/run_chinese_semantic_naturalness_phase1_audit.py --run-tag phase1-dev
```

Expected: tests pass and audit prints `readiness=chinese_semantic_naturalness_phase1_ready`.

---

### Task 3: Preserved Baseline And Dashboard Wiring

**Files:**
- Modify: `evals/run_preserved_baselines_audit.py`
- Modify: `tests/test_preserved_baselines_audit.py`
- Modify: `amadeus_thread0/runtime/runtime_status_dashboard.py`
- Modify: `tests/test_runtime_status_dashboard.py`

- [ ] **Step 1: Write/update failing tests**

Update `tests/test_preserved_baselines_audit.py` so `expected_ids` includes `chinese_semantic_naturalness_phase1` and category `chinese_semantic` expects `2` passed baselines.

Update `tests/test_runtime_status_dashboard.py` so the ready dashboard expects:

```python
assert dashboard["lanes"]["chinese_semantic_naturalness"]["status"] == "phase1_ready"
assert dashboard["lanes"]["chinese_semantic_naturalness"]["runtime_authority"] == "deterministic_readback_only"
assert dashboard["next_specs"][0]["id"] == "dynamic_skill_candidate_runtime"
```

and the compact line expects `next_specs=1`.

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_preserved_baselines_audit.py tests/test_runtime_status_dashboard.py -q
```

Expected: fails because the audit spec and dashboard lane are not yet wired.

- [ ] **Step 3: Wire preserved baseline**

Add to `BASELINE_SPECS`:

```python
{
    "id": "chinese_semantic_naturalness_phase1",
    "prefix": "chinese-semantic-naturalness-phase1-audit-",
    "expected_readiness": "chinese_semantic_naturalness_phase1_ready",
    "category": "chinese_semantic",
},
```

- [ ] **Step 4: Wire dashboard**

In `runtime_status_dashboard.py`, remove `chinese_semantic_naturalness` from `NEXT_SPECS`, add a `LANES["chinese_semantic_naturalness"]` row with `phase1_ready`, and leave `dynamic_skill_candidate_runtime` as the next spec.

- [ ] **Step 5: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_chinese_semantic_naturalness_phase1_audit.py tests/test_preserved_baselines_audit.py tests/test_runtime_status_dashboard.py -q
```

Expected: all tests pass.

---

### Task 4: Documentation And Ledger Closure

**Files:**
- Modify: `AGENTS.md`
- Modify: `program.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/BACKEND_HANDOFF.md`
- Modify: `docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md`

- [ ] **Step 1: Document the closed gate**

Add concise documentation that `Chinese Semantic Naturalness Phase 1` is closed as `chinese_semantic_naturalness_phase1_ready`.

Document these boundaries:

```text
No generation prompt rewrite, no model API call, no persona-core mutation, no memory write, no behavior motive mutation, no frontend-owned semantics, no live capture, no skill registry write, and no external mutation.
```

- [ ] **Step 2: Update the ledger**

Append a new `program.md` run entry listing:

- created naturalness readback
- attached it to embodied interaction
- added deterministic audit
- folded it into preserved baselines
- updated dashboard next specs
- validation commands

- [ ] **Step 3: Run documentation and syntax checks**

Run:

```powershell
python -m py_compile amadeus_thread0/runtime/chinese_semantic_naturalness.py amadeus_thread0/runtime/embodied_interaction_runtime.py evals/run_chinese_semantic_naturalness_phase1_audit.py evals/run_preserved_baselines_audit.py amadeus_thread0/runtime/runtime_status_dashboard.py
git diff --check
```

Expected: no errors.

---

### Task 5: Final Verification, Merge, Push, Cleanup

**Files:**
- All files changed in Tasks 1-4

- [ ] **Step 1: Run final focused verification in worktree**

Run:

```powershell
python -m pytest tests/test_chinese_semantic_naturalness.py tests/test_chinese_semantic_naturalness_phase1_audit.py tests/test_chinese_semantic_surface_phase2.py tests/test_chinese_semantic_descaffolding_phase2_audit.py tests/test_embodied_interaction_runtime.py tests/test_runtime_status_dashboard.py tests/test_preserved_baselines_audit.py -q
python -m py_compile amadeus_thread0/runtime/chinese_semantic_naturalness.py amadeus_thread0/runtime/embodied_interaction_runtime.py evals/run_chinese_semantic_naturalness_phase1_audit.py evals/run_preserved_baselines_audit.py amadeus_thread0/runtime/runtime_status_dashboard.py
git diff --check
python evals/run_chinese_semantic_naturalness_phase1_audit.py --run-tag phase1-final
```

Expected: tests pass, py_compile passes, diff check passes, and audit prints `readiness=chinese_semantic_naturalness_phase1_ready`.

- [ ] **Step 2: Commit**

Run:

```powershell
git status --short
git add AGENTS.md program.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/BACKEND_HANDOFF.md docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md docs/superpowers/plans/2026-05-07-chinese-semantic-naturalness-phase1.md amadeus_thread0/runtime/chinese_semantic_naturalness.py amadeus_thread0/runtime/embodied_interaction_runtime.py amadeus_thread0/runtime/runtime_status_dashboard.py evals/run_chinese_semantic_naturalness_phase1_audit.py evals/run_preserved_baselines_audit.py tests/test_chinese_semantic_naturalness.py tests/test_chinese_semantic_naturalness_phase1_audit.py tests/test_preserved_baselines_audit.py tests/test_runtime_status_dashboard.py
git commit -m "feat: close chinese semantic naturalness phase 1"
```

Expected: commit succeeds on `codex/chinese-semantic-naturalness-phase1`.

- [ ] **Step 3: Merge to main and verify**

Run:

```powershell
git -C E:\桌面\amadeus-thread0 checkout main
git -C E:\桌面\amadeus-thread0 pull --ff-only origin main
git -C E:\桌面\amadeus-thread0 merge --ff-only codex/chinese-semantic-naturalness-phase1
python -m pytest tests/test_chinese_semantic_naturalness.py tests/test_chinese_semantic_naturalness_phase1_audit.py tests/test_chinese_semantic_surface_phase2.py tests/test_chinese_semantic_descaffolding_phase2_audit.py tests/test_embodied_interaction_runtime.py tests/test_runtime_status_dashboard.py tests/test_preserved_baselines_audit.py -q
python evals/run_chinese_semantic_naturalness_phase1_audit.py --run-tag post-merge
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
git diff --check
```

Expected: merge succeeds and post-merge checks pass.

- [ ] **Step 4: Push and cleanup**

Run:

```powershell
git push origin main
git worktree remove C:\Users\29920\.config\superpowers\worktrees\amadeus-thread0\chinese-semantic-naturalness-phase1
git worktree prune
git branch -d codex/chinese-semantic-naturalness-phase1
```

Expected: push succeeds, worktree is removed, and local feature branch is deleted.

