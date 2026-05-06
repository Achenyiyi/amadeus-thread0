# Residual Living Loop Closure Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Close the current residual work into one auditable `Residual Living Loop Closure Phase 1` gate that proves post-unlock lanes support the north-star loop without widening frozen runtime authority.

**Architecture:** Add a small runtime read-model module that evaluates residual closure across living-loop traceability, Chinese semantic de-scaffolding, multimodal perception bridging, dynamic capability boundaries, and long-horizon calibration. Add an offline audit runner and focused tests, then optionally surface the readiness through the existing operator readback without changing execution authority.

**Tech Stack:** Python 3, pytest, existing `evals/` audit pattern, existing `runtime_productization` readback contract, existing post-unlock lane modules.

---

## File Structure

- Create `amadeus_thread0/runtime/residual_living_loop.py`
  - Owns the residual phase-1 read-model and pure evaluation helpers.
  - Does not execute tools, mutate memory, install skills, open live capture, or run external harnesses.
- Create `evals/run_residual_living_loop_audit.py`
  - Runs the deterministic residual closure audit and writes json/md reports.
- Create `tests/test_residual_living_loop.py`
  - Unit coverage for the pure runtime helpers.
- Create `tests/test_residual_living_loop_audit.py`
  - Unit coverage for audit report shape and markdown rendering.
- Modify `amadeus_thread0/runtime/runtime_productization.py`
  - Accepts an optional residual readback input and exposes it in operator readback v2.
  - Keeps the productization phase readback-only.
- Modify `tests/test_runtime_productization.py`
  - Locks the optional residual readback compact line and authority boundary.
- Modify `docs/engineering/PROJECT_STRUCTURE.md`
  - Documents ownership of the new runtime/audit files.
- Modify `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
  - Records the residual phase as a closure gate, not a capability expansion.
- Modify `AGENTS.md`
  - Records the new readiness label and non-widening boundaries.
- Modify `program.md`
  - Adds the run ledger entry with changed files, validation, and next step.

## Task 1: Pure Residual Closure Contract

**Files:**
- Create: `tests/test_residual_living_loop.py`
- Create: `amadeus_thread0/runtime/residual_living_loop.py`

- [x] **Step 1: Write failing tests for the residual contract**

Add tests that import the new module and assert:

```python
from amadeus_thread0.runtime.residual_living_loop import (
    RESIDUAL_LIVING_LOOP_PHASE1_READINESS,
    build_residual_living_loop_readback,
    compact_residual_living_loop_line,
    evaluate_living_loop_trace,
)


def _complete_turn():
    return {
        "current_event": {"kind": "user_message", "perception": {"modality": "text"}},
        "turn_appraisal": {"scene": "repair", "confidence": 0.84},
        "emotion_state": {"label": "guarded"},
        "bond_state": {"trust": 0.58},
        "allostasis_state": {"autonomy_need": 0.62},
        "behavior_action": {"primary_motive": "repair_without_erasing_boundary"},
        "behavior_plan": {"action_family": "low_pressure_support"},
        "digital_body_consequence": {"kind": "source_material_inspected"},
        "reconsolidation_snapshot": {
            "behavior_action": {"primary_motive": "repair_without_erasing_boundary"},
            "digital_body_consequence": {"kind": "source_material_inspected"},
        },
        "writeback_trace": {
            "revision_traces": [{"namespace": "semantic_self_evidence"}],
            "counterpart_assessment_history": [{"stance": "watchful"}],
        },
        "semantic_narrative_profile": {"continuity_axes": [{"category": "repair_style"}]},
    }


def test_living_loop_trace_passes_when_all_north_star_stages_are_visible():
    trace = evaluate_living_loop_trace(_complete_turn())
    assert trace["status"] == "ready"
    assert trace["ready_stage_count"] == 8
    assert trace["missing_stages"] == []


def test_living_loop_trace_fails_when_writeback_is_missing():
    turn = _complete_turn()
    turn.pop("writeback_trace")
    trace = evaluate_living_loop_trace(turn)
    assert trace["status"] == "incomplete"
    assert "memory_reconsolidation" in trace["missing_stages"]


def test_residual_readback_closes_without_widening_authority():
    readback = build_residual_living_loop_readback(current_turn=_complete_turn())
    assert readback["readiness_status"] == RESIDUAL_LIVING_LOOP_PHASE1_READINESS
    assert readback["authority_boundary"]["live_capture_enabled"] is False
    assert readback["authority_boundary"]["auto_skill_registry_write"] is False
    assert readback["residuals"]["chinese_semantic_descaffolding"]["status"] == "ready"
    assert readback["residuals"]["multimodal_perception_bridge"]["status"] == "ready"


def test_compact_line_is_short_and_actionable():
    line = compact_residual_living_loop_line(build_residual_living_loop_readback(current_turn=_complete_turn()))
    assert "residual=residual_living_loop_phase1_ready" in line
    assert "loop=ready" in line
    assert "blocked_live_capture=true" in line
```

Run:

```powershell
python -m pytest tests/test_residual_living_loop.py -q
```

Expected: FAIL because `amadeus_thread0.runtime.residual_living_loop` does not exist.

- [x] **Step 2: Implement `residual_living_loop.py`**

Create the runtime module with these public helpers:

```python
RESIDUAL_LIVING_LOOP_PHASE1_READINESS = "residual_living_loop_phase1_ready"

def evaluate_living_loop_trace(current_turn: dict | None) -> dict: ...
def build_residual_living_loop_readback(*, current_turn: dict | None = None) -> dict: ...
def compact_residual_living_loop_line(readback: dict | None) -> str: ...
```

Implementation rules:

- `evaluate_living_loop_trace()` checks the eight north-star stages:
  - `perception`
  - `appraisal`
  - `internal_state_change`
  - `motive_goal_shift`
  - `behavior`
  - `consequence`
  - `memory_reconsolidation`
  - `self_narrative_update`
- The readback has residual rows:
  - `living_loop_traceability`
  - `chinese_semantic_descaffolding`
  - `multimodal_perception_bridge`
  - `dynamic_capability_boundaries`
  - `natural_long_horizon_calibration`
- The authority boundary always reports:
  - `live_capture_enabled=False`
  - `auto_skill_registry_write=False`
  - `external_harness_auto_enabled=False`
  - `frontend_semantics_owner=False`
  - `persona_core_mutation_allowed=False`
- No runtime side effects.

Run:

```powershell
python -m pytest tests/test_residual_living_loop.py -q
```

Expected: PASS.

## Task 2: Residual Closure Audit Runner

**Files:**
- Create: `tests/test_residual_living_loop_audit.py`
- Create: `evals/run_residual_living_loop_audit.py`

- [x] **Step 1: Write failing audit tests**

Add tests that assert:

```python
from evals.run_residual_living_loop_audit import (
    build_deterministic_turn_fixture,
    build_report,
    render_markdown,
)


def test_build_report_returns_phase1_ready():
    report = build_report(run_id="test-run")
    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "residual_living_loop_phase1_ready"
    assert report["readback"]["residuals"]["living_loop_traceability"]["status"] == "ready"


def test_deterministic_fixture_contains_all_loop_surfaces():
    turn = build_deterministic_turn_fixture()
    for key in (
        "current_event",
        "turn_appraisal",
        "emotion_state",
        "bond_state",
        "allostasis_state",
        "behavior_action",
        "behavior_plan",
        "digital_body_consequence",
        "reconsolidation_snapshot",
        "writeback_trace",
    ):
        assert key in turn


def test_markdown_renders_residual_table():
    rendered = render_markdown(build_report(run_id="render-test"))
    assert "# Residual Living Loop Closure Audit" in rendered
    assert "`residual_living_loop_phase1_ready`" in rendered
    assert "| `living_loop_traceability` | `ready` |" in rendered
```

Run:

```powershell
python -m pytest tests/test_residual_living_loop_audit.py -q
```

Expected: FAIL because the audit runner does not exist.

- [x] **Step 2: Implement `evals/run_residual_living_loop_audit.py`**

The runner:

- imports `build_residual_living_loop_readback`
- builds one deterministic current-turn fixture with all north-star surfaces
- writes:
  - `evals/reports/residual-living-loop-audit-<run_id>.json`
  - `evals/reports/residual-living-loop-audit-<run_id>.md`
- prints:
  - json path
  - md path
  - overall status
  - readiness

Run:

```powershell
python -m pytest tests/test_residual_living_loop_audit.py -q
python evals/run_residual_living_loop_audit.py --run-tag phase1-dev
```

Expected: tests PASS and audit prints `readiness=residual_living_loop_phase1_ready`.

## Task 3: Operator Readback Integration

**Files:**
- Modify: `amadeus_thread0/runtime/runtime_productization.py`
- Modify: `tests/test_runtime_productization.py`

- [x] **Step 1: Write failing productization tests**

Add a test that builds `residual_living_loop` using the new readback helper, passes it into `build_runtime_productization_readback(...)`, and asserts:

```python
from amadeus_thread0.runtime.residual_living_loop import build_residual_living_loop_readback


def test_operator_readback_can_include_residual_living_loop_without_widening_authority():
    residual = build_residual_living_loop_readback(current_turn={...complete fixture...})
    readback = build_runtime_productization_readback(
        post_baseline_status={"overall_status": "passed", "readiness_status": "post_baseline_closure_ready", "items": {}},
        preserved_baselines={"overall_status": "passed", "readiness_status": "preserved_baselines_ready"},
        post_unlock_roadmap={"overall_status": "passed", "readiness_status": "post_unlock_roadmap_ready"},
        residual_living_loop=residual,
    )
    assert readback["residual_living_loop"]["readiness_status"] == "residual_living_loop_phase1_ready"
    assert readback["authority_boundary"]["live_capture_auto_enabled"] is False
    assert "residual=residual_living_loop_phase1_ready" in compact_operator_readback_line(readback)
```

Run:

```powershell
python -m pytest tests/test_runtime_productization.py -q
```

Expected: FAIL because `build_runtime_productization_readback` has no `residual_living_loop` parameter.

- [x] **Step 2: Implement optional residual readback**

Modify `build_runtime_productization_readback(...)` to accept:

```python
residual_living_loop: dict[str, Any] | None = None
```

If supplied:

- store it under `readback["residual_living_loop"]`
- include its readiness in `compact_operator_readback_line(...)`
- do not add it to `EXPECTED_INPUT_READINESS`
- do not make productization fail when the residual block is absent

Run:

```powershell
python -m pytest tests/test_runtime_productization.py tests/test_residual_living_loop.py -q
```

Expected: PASS.

## Task 4: Documentation And Ledger

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `program.md`

- [x] **Step 1: Update AGENTS.md**

Record:

- `Residual Living Loop Closure Phase 1` is closed when the new audit reports `residual_living_loop_phase1_ready`.
- The phase is not a live capture, auto skill install, external harness, frontend-owned semantics, or persona-core mutation phase.

- [x] **Step 2: Update structure doc**

Add:

- `residual_living_loop.py` under `amadeus_thread0/runtime/`
- `run_residual_living_loop_audit.py` under `evals/`

- [x] **Step 3: Update architecture decisions**

Add a decision-frame note:

- residual closure turns the post-unlock residuals into one auditable north-star loop contract
- it does not widen runtime authority

- [x] **Step 4: Update program.md**

Add a new run entry with:

- focus
- files changed
- validations run
- concrete next step

Run:

```powershell
rg -n "residual_living_loop_phase1_ready|Residual Living Loop" AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md
```

Expected: all four docs mention the phase or readiness label.

## Task 5: Final Verification And Merge Readiness

**Files:**
- No new files unless verification reveals a scoped fix.

- [x] **Step 1: Run focused tests**

Run:

```powershell
python -m pytest tests/test_residual_living_loop.py tests/test_residual_living_loop_audit.py tests/test_runtime_productization.py tests/test_multimodal_sources.py tests/test_chinese_surface_de_scaffold_audit.py -q
```

Expected: PASS.

- [x] **Step 2: Run focused audits**

Run:

```powershell
python evals/run_residual_living_loop_audit.py --run-tag phase1-final
python evals/run_chinese_surface_de_scaffold_audit.py --run-tag residual-phase1-final
python evals/run_multimodal_capture_audit.py --run-tag residual-phase1-final
```

Expected:

- residual audit reports `residual_living_loop_phase1_ready`
- Chinese audit reports `chinese_semantic_descaffolding_phase1_ready`
- multimodal audit reports `multimodal_capture_phase1_ready`

- [x] **Step 3: Compile touched Python**

Run:

```powershell
python -m py_compile amadeus_thread0/runtime/residual_living_loop.py amadeus_thread0/runtime/runtime_productization.py evals/run_residual_living_loop_audit.py
```

Expected: PASS.

- [x] **Step 4: Diff and placeholder checks**

Run:

```powershell
git diff --check
rg -n -e "T[B]D" -e "T[O]DO" -e "f[i]ll in" -e "implement la[t]er" -e "appropriate error handl[i]ng" docs/superpowers/plans/2026-05-06-residual-living-loop-closure-phase1.md amadeus_thread0/runtime/residual_living_loop.py evals/run_residual_living_loop_audit.py tests/test_residual_living_loop.py tests/test_residual_living_loop_audit.py
```

Expected:

- `git diff --check` has no errors
- placeholder scan has no matches

- [x] **Step 5: Commit and merge**

After verification passes:

```powershell
git status --short
git add AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md docs/superpowers/plans/2026-05-06-residual-living-loop-closure-phase1.md program.md amadeus_thread0/runtime/residual_living_loop.py amadeus_thread0/runtime/runtime_productization.py evals/run_residual_living_loop_audit.py tests/test_residual_living_loop.py tests/test_residual_living_loop_audit.py tests/test_runtime_productization.py
git commit -m "feat: add residual living loop closure audit"
```

Expected: commit succeeds on branch `codex/residual-closure-plan`.

Then merge to `main` from the primary workspace with a fast-forward merge.


