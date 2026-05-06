# Living Loop Runtime Realism Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Prove that visible living-loop stages constrain each other causally and add deterministic Chinese semantic replacement guidance beyond diagnostic-only residue classification.

**Architecture:** Keep `Residual Living Loop Closure Phase 1` as the stage-visibility baseline and add a focused read model in `amadeus_thread0/runtime/living_loop_realism.py` for cross-stage causality checks. Keep Chinese semantic de-scaffolding bounded inside `amadeus_thread0/graph_parts/chinese_semantic_surface.py` by returning replacement guidance and a conservative safe surface floor rather than broad prompt rewrites.

**Tech Stack:** Python 3, pytest, pure deterministic eval scripts, existing audit report conventions under `evals/reports/`.

---

## File Structure

- Create `amadeus_thread0/runtime/living_loop_realism.py`
  - Owns runtime realism readback only.
  - Checks whether appraisal, state, motive, behavior, consequence, reconsolidation, and self-narrative agree.
  - Does not mutate graph state, memory, tools, browser, skills, persona core, or final text.
- Create `tests/test_living_loop_realism.py`
  - Unit tests for happy-path causality, missing causality markers, final behavior mismatch, and compact readback output.
- Modify `amadeus_thread0/graph_parts/chinese_semantic_surface.py`
  - Adds semantic replacement plans and conservative safe surface-floor text for detected brittle Chinese families.
  - Keeps the existing classifier and replacement candidate APIs backward-compatible.
- Create `tests/test_chinese_semantic_surface_phase2.py`
  - Tests replacement guidance, safe-surface floors, family ordering, and no-runtime-authority widening.
- Create `evals/run_living_loop_realism_audit.py`
  - Deterministic audit runner producing `living-loop-realism-audit-*.json` and `*.md`.
- Create `tests/test_living_loop_realism_audit.py`
  - Tests report status, markdown rendering, fixture coverage, and semantic guidance inclusion.
- Modify `evals/run_preserved_baselines_audit.py`
  - Adds `living_loop_runtime_realism_phase1` to the preserved baseline chain.
- Modify `tests/test_preserved_baselines_audit.py`
  - Updates expected baseline ids and category pass counts.
- Modify `AGENTS.md`
  - Records the new phase as a preserved baseline and states its authority boundaries.
- Modify `docs/engineering/PROJECT_STRUCTURE.md`
  - Documents `living_loop_realism.py` ownership and audit runner.
- Modify `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
  - Adds the phase to current implementation order and readback/audit decisions.
- Modify `program.md`
  - Updates current state, latest milestone, files changed, validations, and next step.

## Guardrails

- Do not open live microphone, camera, or background screen capture.
- Do not auto-install, auto-enable, or auto-write skills registry state.
- Do not enable external executor harness runtime.
- Do not mutate persona core, relationship core, or self-narrative core.
- Do not add frontend-owned semantics.
- Do not perform broad prompt rewrite or final-answer postprocess rewrite in this phase.
- Do not touch `third_party/benchmarks/ESConv`.

---

### Task 1: Living Loop Causality Read Model

**Files:**
- Create: `tests/test_living_loop_realism.py`
- Create: `amadeus_thread0/runtime/living_loop_realism.py`

- [x] **Step 1: Write failing tests for cross-stage causality**

Create `tests/test_living_loop_realism.py` with these expectations:

```python
from __future__ import annotations

from amadeus_thread0.runtime.living_loop_realism import (
    LIVING_LOOP_REALISM_PHASE1_READINESS,
    build_living_loop_realism_readback,
    compact_living_loop_realism_line,
    evaluate_behavior_causality,
)


def _realistic_turn() -> dict:
    return {
        "final_text": "嗯。我听见了。边界还在，但这次我会先把话放轻一点。",
        "current_event": {
            "kind": "user_utterance",
            "text": "之前那件事我一直记着，我们能慢慢聊吗？",
            "tags": ["repair", "relationship"],
        },
        "turn_appraisal": {
            "scene": "repair_attempt",
            "interaction_frame": "relationship",
            "signals": {"repair": True, "care": True},
        },
        "emotion_state": {"label": "hurt", "valence": -0.08, "arousal": 0.22},
        "bond_state": {"trust": 0.60, "closeness": 0.58, "hurt": 0.14, "repair_confidence": 0.66},
        "allostasis_state": {"autonomy_need": 0.38, "safety_need": 0.42, "cognitive_budget": 0.70},
        "counterpart_assessment": {
            "stance": "watchful",
            "scene": "repair_attempt",
            "boundary_pressure": 0.18,
            "reliability_read": 0.62,
        },
        "semantic_narrative_profile": {
            "repair_residue": 0.76,
            "continuity_depth": 0.68,
            "commitment_carry": 0.62,
            "continuity_axes": [{"category": "repair_style", "score": 0.74}],
        },
        "behavior_action": {
            "interaction_mode": "low_pressure_support",
            "action_target": "low_pressure_hold",
            "primary_motive": "support_without_pressure",
            "motive_tension": "boundary_vs_closeness",
            "goal_frame": "先低负担接住，不接管对方节奏。",
        },
        "behavior_plan": {
            "kind": "low_pressure_support",
            "interaction_mode": "low_pressure_support",
            "primary_motive": "support_without_pressure",
            "goal_frame": "先低负担接住，不接管对方节奏。",
        },
        "digital_body_consequence": {"kind": "relationship_repair_acknowledged"},
        "reconsolidation_snapshot": {
            "behavior_action": {"primary_motive": "support_without_pressure"},
            "behavior_plan": {"kind": "low_pressure_support", "primary_motive": "support_without_pressure"},
            "digital_body_consequence": {"kind": "relationship_repair_acknowledged"},
            "final_text": "嗯。我听见了。边界还在，但这次我会先把话放轻一点。",
        },
        "writeback_trace": {
            "revision_traces": [{"namespace": "semantic_self_evidence", "target_id": "repair_style"}],
            "counterpart_assessment_history": [{"stance": "watchful", "scene": "repair_attempt"}],
        },
    }


def test_behavior_causality_passes_when_state_drives_behavior():
    report = evaluate_behavior_causality(_realistic_turn())

    assert report["status"] == "ready"
    assert report["missing_links"] == []
    assert report["links"]["appraisal_to_motive"]["status"] == "ready"
    assert report["links"]["state_to_behavior"]["status"] == "ready"
    assert report["links"]["final_semantics_alignment"]["status"] == "ready"


def test_behavior_causality_fails_when_appraisal_conflicts_with_motive():
    turn = _realistic_turn()
    turn["turn_appraisal"] = {"scene": "repair_attempt", "signals": {"repair": True}}
    turn["behavior_action"] = {"primary_motive": "solve_task", "interaction_mode": "tooling"}
    turn["behavior_plan"] = {"primary_motive": "solve_task", "kind": "tooling"}

    report = evaluate_behavior_causality(turn)

    assert report["status"] == "incomplete"
    assert "appraisal_to_motive" in report["missing_links"]


def test_readback_keeps_authority_boundary_closed():
    readback = build_living_loop_realism_readback(current_turn=_realistic_turn())

    assert readback["readiness_status"] == LIVING_LOOP_REALISM_PHASE1_READINESS
    assert readback["schema"] == "living_loop_realism.v1"
    assert readback["authority_boundary"]["persona_core_mutation_allowed"] is False
    assert readback["authority_boundary"]["memory_write_allowed"] is False
    assert readback["authority_boundary"]["prompt_sprawl_rewrite_allowed"] is False


def test_compact_line_names_causality_status():
    line = compact_living_loop_realism_line(build_living_loop_realism_readback(current_turn=_realistic_turn()))

    assert "realism=living_loop_runtime_realism_phase1_ready" in line
    assert "causality=ready" in line
```

- [x] **Step 2: Run the focused tests and verify failure**

Run:

```powershell
python -m pytest tests/test_living_loop_realism.py -q
```

Expected: FAIL because `amadeus_thread0.runtime.living_loop_realism` does not exist.

- [x] **Step 3: Implement the read model**

Create `amadeus_thread0/runtime/living_loop_realism.py` with:

```python
LIVING_LOOP_REALISM_PHASE1_READINESS = "living_loop_runtime_realism_phase1_ready"
LIVING_LOOP_REALISM_IN_PROGRESS = "living_loop_runtime_realism_phase1_in_progress"

def evaluate_behavior_causality(current_turn: dict[str, Any] | None) -> dict[str, Any]: ...
def build_living_loop_realism_readback(*, current_turn: dict[str, Any] | None = None) -> dict[str, Any]: ...
def compact_living_loop_realism_line(readback: dict[str, Any] | None) -> str: ...
```

The implementation should check these links:

- `appraisal_to_motive`
  - repair scenes/signals require motives such as `support_without_pressure`, `repair_without_erasing_boundary`, `protect_boundary`, or `honor_continuity`.
  - boundary/selfhood scenes require motives such as `protect_boundary` or `preserve_self_rhythm`.
  - daily/care/continuity scenes require motives such as `honor_continuity`, `confirm_presence`, `gentle_recontact`, or `maintain_natural_contact`.
- `state_to_behavior`
  - at least two state families among emotion, bond, allostasis, counterpart, and semantic narrative must leave compatible influence markers in motive, interaction mode, action target, tension, goal frame, or plan kind.
- `action_plan_alignment`
  - `behavior_action.primary_motive` must match `behavior_plan.primary_motive` when both are present.
- `consequence_reconsolidation_alignment`
  - `digital_body_consequence.kind` must match the reconsolidation snapshot consequence kind when both are present.
- `final_semantics_alignment`
  - final text, snapshot final text, action, plan, and writeback must describe one final behavior rather than conflicting motives.

- [x] **Step 4: Run focused tests and verify pass**

Run:

```powershell
python -m pytest tests/test_living_loop_realism.py -q
```

Expected: PASS.

---

### Task 2: Chinese Semantic Replacement Guidance Phase 2

**Files:**
- Modify: `amadeus_thread0/graph_parts/chinese_semantic_surface.py`
- Create: `tests/test_chinese_semantic_surface_phase2.py`

- [x] **Step 1: Write failing tests for replacement guidance**

Create `tests/test_chinese_semantic_surface_phase2.py` with tests that assert:

```python
from __future__ import annotations

from amadeus_thread0.graph_parts.chinese_semantic_surface import (
    build_semantic_replacement_plan,
    rewrite_semantic_surface_floor,
)


def test_replacement_plan_maps_detected_families_to_behavior_targets():
    plan = build_semantic_replacement_plan("请问有什么可以帮你？")

    assert plan["status"] == "replacement_guidance_ready"
    assert plan["families"] == ["generic_assistant_tone"]
    assert plan["replacement_semantics"][0]["target_behavior"] == "familiar_shared_presence"
    assert plan["authority_boundary"]["persona_core_mutation_allowed"] is False
    assert plan["authority_boundary"]["prompt_sprawl_rewrite_allowed"] is False


def test_safe_surface_floor_replaces_scaffold_without_claiming_full_rewrite():
    result = rewrite_semantic_surface_floor("你能意识到并特意回来说明，这点还算值得肯定。")

    assert result["status"] == "floor_rewritten"
    assert "值得肯定" not in result["safe_surface_floor"]
    assert result["families"] == ["teacherly_scold"]
    assert result["applied_floor"] is True


def test_no_detected_family_returns_noop_floor():
    result = rewrite_semantic_surface_floor("嗯，我听见了。")

    assert result["status"] == "no_semantic_residue"
    assert result["safe_surface_floor"] == "嗯，我听见了。"
    assert result["applied_floor"] is False
```

- [x] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests/test_chinese_semantic_surface_phase2.py -q
```

Expected: FAIL because `build_semantic_replacement_plan` and `rewrite_semantic_surface_floor` do not exist.

- [x] **Step 3: Implement deterministic guidance**

Modify `amadeus_thread0/graph_parts/chinese_semantic_surface.py`:

- Add `REPLACEMENT_GUIDANCE` keyed by existing `FAMILIES`.
- Each family must expose:
  - `replacement_semantic`
  - `target_behavior`
  - `avoid`
  - `safe_surface_floor`
- Add:

```python
def build_semantic_replacement_plan(text: str, *, family_context: list[str] | None = None) -> dict[str, object]: ...
def rewrite_semantic_surface_floor(text: str, *, family_context: list[str] | None = None) -> dict[str, object]: ...
```

The conservative floor should return a short safe sentence for the first detected family, not attempt full final-answer rewriting.

- [x] **Step 4: Run focused and legacy Chinese tests**

Run:

```powershell
python -m pytest tests/test_chinese_semantic_surface_phase2.py tests/test_chinese_surface_de_scaffold_audit.py -q
```

Expected: PASS.

---

### Task 3: Living Loop Realism Audit Runner

**Files:**
- Create: `tests/test_living_loop_realism_audit.py`
- Create: `evals/run_living_loop_realism_audit.py`

- [x] **Step 1: Write failing audit tests**

Create `tests/test_living_loop_realism_audit.py` with tests that assert:

```python
from __future__ import annotations

from evals.run_living_loop_realism_audit import (
    build_deterministic_turn_fixture,
    build_report,
    render_markdown,
)


def test_build_report_returns_phase1_ready():
    report = build_report(run_id="test-run")

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "living_loop_runtime_realism_phase1_ready"
    assert report["readback"]["causality"]["status"] == "ready"
    assert report["chinese_semantic_replacement"]["status"] == "floor_rewritten"


def test_fixture_contains_causal_loop_surfaces():
    turn = build_deterministic_turn_fixture()

    for key in (
        "turn_appraisal",
        "emotion_state",
        "bond_state",
        "allostasis_state",
        "counterpart_assessment",
        "semantic_narrative_profile",
        "behavior_action",
        "behavior_plan",
        "digital_body_consequence",
        "reconsolidation_snapshot",
        "writeback_trace",
    ):
        assert key in turn


def test_markdown_renders_causality_and_chinese_guidance():
    rendered = render_markdown(build_report(run_id="render-test"))

    assert "# Living Loop Runtime Realism Audit" in rendered
    assert "`living_loop_runtime_realism_phase1_ready`" in rendered
    assert "| `appraisal_to_motive` | `ready` |" in rendered
    assert "Chinese Semantic Replacement" in rendered
```

- [x] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests/test_living_loop_realism_audit.py -q
```

Expected: FAIL because `evals.run_living_loop_realism_audit` does not exist.

- [x] **Step 3: Implement audit runner**

Create `evals/run_living_loop_realism_audit.py`:

- Use the same project-root import setup as existing audit scripts.
- Build a deterministic repair fixture.
- Call `build_living_loop_realism_readback(...)`.
- Call `rewrite_semantic_surface_floor(...)` on a known brittle Chinese surface.
- Emit:
  - `overall_status`
  - `readiness_status`
  - `failure_reasons`
  - `readback`
  - `chinese_semantic_replacement`
- Write reports to:
  - `evals/reports/living-loop-realism-audit-<run_id>.json`
  - `evals/reports/living-loop-realism-audit-<run_id>.md`

- [x] **Step 4: Run audit tests and dev audit**

Run:

```powershell
python -m pytest tests/test_living_loop_realism_audit.py -q
python evals/run_living_loop_realism_audit.py --run-tag phase1-dev
```

Expected: tests PASS and audit prints `readiness=living_loop_runtime_realism_phase1_ready`.

---

### Task 4: Preserved Baseline Integration

**Files:**
- Modify: `evals/run_preserved_baselines_audit.py`
- Modify: `tests/test_preserved_baselines_audit.py`

- [x] **Step 1: Update failing preserved-baseline expectations**

Modify `tests/test_preserved_baselines_audit.py`:

- Add `living_loop_runtime_realism_phase1` to `expected_ids`.
- Assert `summary["summary"]["categories"]["living_loop_realism"]["passed"] == 1`.
- The total expected baseline count should increase by one through `len(EXPECTED_READY)`.

- [x] **Step 2: Run focused preserved-baseline test and verify failure**

Run:

```powershell
python -m pytest tests/test_preserved_baselines_audit.py -q
```

Expected: FAIL because the audit spec has not been added yet.

- [x] **Step 3: Add the new baseline spec**

Modify `BASELINE_SPECS` in `evals/run_preserved_baselines_audit.py`:

```python
{
    "id": "living_loop_runtime_realism_phase1",
    "prefix": "living-loop-realism-audit-",
    "expected_readiness": "living_loop_runtime_realism_phase1_ready",
    "category": "living_loop_realism",
}
```

- [x] **Step 4: Run preserved-baseline tests**

Run:

```powershell
python -m pytest tests/test_preserved_baselines_audit.py -q
```

Expected: PASS.

---

### Task 5: Documentation and Ledger

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `program.md`

- [x] **Step 1: Update repository contract docs**

Add concise notes:

- `Living Loop Runtime Realism Phase 1` is closed by `living_loop_runtime_realism_phase1_ready`.
- It upgrades residual traceability into causality readback.
- It keeps Chinese semantic replacement bounded to deterministic guidance and safe surface floors.
- It does not open new capture, execution, memory, skill-registry, frontend, or persona-core authority.

- [x] **Step 2: Update project structure ownership**

Document:

- `amadeus_thread0/runtime/living_loop_realism.py`
- `evals/run_living_loop_realism_audit.py`
- new preserved-baseline coverage.

- [x] **Step 3: Update `program.md`**

Add a dated entry with:

- current focus
- files changed
- validations run
- concrete next step

---

### Task 6: Final Verification, Commit, Merge, Push

**Files:**
- All files touched in Tasks 1-5.

- [x] **Step 1: Run focused regression**

Run:

```powershell
python -m pytest tests/test_living_loop_realism.py tests/test_living_loop_realism_audit.py tests/test_chinese_semantic_surface_phase2.py tests/test_chinese_surface_de_scaffold_audit.py tests/test_preserved_baselines_audit.py tests/test_residual_living_loop.py -q
```

Expected: PASS.

- [x] **Step 2: Run audits**

Run:

```powershell
python evals/run_living_loop_realism_audit.py --run-tag phase1-final
python evals/run_chinese_surface_de_scaffold_audit.py --run-tag realism-phase1-final
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
```

Expected:

- `living_loop_runtime_realism_phase1_ready`
- `chinese_semantic_descaffolding_phase1_ready`
- `preserved_baselines_ready`

- [x] **Step 3: Compile changed Python files**

Run:

```powershell
python -m py_compile amadeus_thread0/runtime/living_loop_realism.py amadeus_thread0/graph_parts/chinese_semantic_surface.py evals/run_living_loop_realism_audit.py evals/run_preserved_baselines_audit.py
```

Expected: no output and exit code 0.

- [x] **Step 4: Run diff and placeholder checks**

Run:

```powershell
git diff --check
rg -n -e "T[B]D" -e "T[O]DO" -e "f[i]ll in" -e "implement la[t]er" -e "appropriate error handl[i]ng" docs/superpowers/plans/2026-05-06-living-loop-runtime-realism-phase1.md amadeus_thread0/runtime/living_loop_realism.py amadeus_thread0/graph_parts/chinese_semantic_surface.py evals/run_living_loop_realism_audit.py tests/test_living_loop_realism.py tests/test_living_loop_realism_audit.py tests/test_chinese_semantic_surface_phase2.py
```

Expected:

- `git diff --check` exits 0.
- `rg` exits 1 because no placeholder patterns are found.

- [x] **Step 5: Commit the branch**

Run:

```powershell
git status --short
git add AGENTS.md program.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md docs/superpowers/plans/2026-05-06-living-loop-runtime-realism-phase1.md amadeus_thread0/runtime/living_loop_realism.py amadeus_thread0/graph_parts/chinese_semantic_surface.py evals/run_living_loop_realism_audit.py evals/run_preserved_baselines_audit.py tests/test_living_loop_realism.py tests/test_living_loop_realism_audit.py tests/test_chinese_semantic_surface_phase2.py tests/test_preserved_baselines_audit.py
git commit -m "feat: add living loop runtime realism audit"
```

Expected: commit succeeds on `codex/living-loop-runtime-realism-phase1`.

- [x] **Step 6: Merge to main and push**

Run from the main repository at `E:\桌面\amadeus-thread0`:

```powershell
git status --short --branch
git pull --ff-only
git merge --ff-only codex/living-loop-runtime-realism-phase1
python -m pytest tests/test_living_loop_realism.py tests/test_living_loop_realism_audit.py tests/test_chinese_semantic_surface_phase2.py tests/test_preserved_baselines_audit.py -q
python evals/run_living_loop_realism_audit.py --run-tag post-merge
git push origin main
```

Expected:

- Main fast-forwards.
- Post-merge verification passes.
- Push succeeds.

## Self-Review

- Spec coverage: The plan directly covers runtime causality, Chinese semantic replacement guidance, audit closure, preserved-baseline integration, docs, ledger, commit, merge, and push.
- Placeholder scan: The only forbidden-looking text is intentionally obfuscated in the final placeholder-scan command. There are no unresolved implementation placeholders in the plan steps.
- Type consistency: The plan consistently uses `living_loop_runtime_realism_phase1_ready`, `living_loop_realism.v1`, `build_living_loop_realism_readback`, `evaluate_behavior_causality`, `build_semantic_replacement_plan`, and `rewrite_semantic_surface_floor`.

