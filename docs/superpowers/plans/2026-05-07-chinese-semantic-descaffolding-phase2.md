# Chinese Semantic De-Scaffolding Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert Phase 1 Chinese semantic floors into a typed, auditable runtime replacement policy envelope without broad prompt rewrites or ad hoc tone micro-polish.

**Architecture:** Keep `amadeus_thread0/graph_parts/chinese_semantic_surface.py` as the pure semantic policy owner. `embodied_interaction_runtime.py` will consume that policy and expose it under `chinese_semantic_surface.runtime_policy`, while still updating `final_text` and `reconsolidation_snapshot.final_text` together only when a deterministic safe floor applies. A new deterministic audit proves everyday, repair, self-rhythm, and technical-task cases are typed, floor-applied, duplicate-safe, and text/TTS aligned.

**Tech Stack:** Python 3, pytest, deterministic local `evals/` audit scripts, existing backend payload dictionaries.

---

## File Structure

- `amadeus_thread0/graph_parts/chinese_semantic_surface.py`
  - Add Phase 2 readiness constants.
  - Add `build_runtime_replacement_policy()`.
  - Keep Phase 1 `build_semantic_replacement_plan()` and `rewrite_semantic_surface_floor()` backward compatible.
- `amadeus_thread0/runtime/embodied_interaction_runtime.py`
  - Attach the policy envelope to `chinese_semantic_surface`.
  - Preserve final/snapshot parity when a deterministic floor applies.
- `tests/test_chinese_semantic_surface_phase2.py`
  - Add policy-envelope unit coverage.
- `tests/test_embodied_interaction_runtime.py`
  - Add runtime policy attachment and final/snapshot parity coverage.
- `tests/test_backend_api.py`
  - Add backend payload coverage proving `assistant_turn` / `event_round` expose the policy envelope and keep text parity.
- `evals/run_chinese_semantic_descaffolding_phase2_audit.py`
  - New deterministic audit reporting `chinese_semantic_descaffolding_phase2_ready`.
- `tests/test_chinese_semantic_descaffolding_phase2_audit.py`
  - Audit helper coverage.
- `evals/run_preserved_baselines_audit.py`
  - Add Phase 2 as a preserved baseline.
- `tests/test_preserved_baselines_audit.py`
  - Add expected baseline and update category checks.
- `AGENTS.md`
  - Document Phase 2 as a preserved bounded runtime policy gate.
- `docs/engineering/PROJECT_STRUCTURE.md`
  - Document the policy owner and audit entrypoint.
- `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
  - Record the readback/runtime-policy decision.
- `program.md`
  - Update current state and run ledger.

---

### Task 1: Runtime Replacement Policy Contract

**Files:**
- Modify: `tests/test_chinese_semantic_surface_phase2.py`
- Modify: `amadeus_thread0/graph_parts/chinese_semantic_surface.py`

- [x] **Step 1: Write failing policy tests**

Add tests requiring a policy envelope:

```python
from amadeus_thread0.graph_parts.chinese_semantic_surface import build_runtime_replacement_policy


def test_runtime_policy_envelope_contains_typed_strategy_and_boundaries():
    policy = build_runtime_replacement_policy("请问有什么可以帮你？")

    assert policy["schema"] == "chinese_semantic_replacement_policy.v1"
    assert policy["readiness_status"] == "chinese_semantic_descaffolding_phase2_ready"
    assert policy["status"] == "policy_ready"
    assert policy["selected_policy"]["family"] == "generic_assistant_tone"
    assert policy["selected_policy"]["semantic_intent"] == "answer from familiar shared presence instead of service framing"
    assert policy["selected_policy"]["replacement_strategy"] == "deterministic_safe_surface_floor"
    assert policy["selected_policy"]["applied_floor"] == "嗯，我在。你直接说吧，我会顺着这轮的语境接住。"
    assert policy["selected_policy"]["authority_boundary"]["model_api_called"] is False
    assert policy["selected_policy"]["authority_boundary"]["prompt_rewrite_applied"] is False
    assert policy["selected_policy"]["authority_boundary"]["persona_core_mutation_allowed"] is False
    assert policy["applied_floor"] is True
```

Also add a no-residue test:

```python
def test_runtime_policy_noop_preserves_text_without_claiming_rewrite():
    policy = build_runtime_replacement_policy("嗯，我听见了。")

    assert policy["status"] == "no_semantic_residue"
    assert policy["readiness_status"] == "chinese_semantic_descaffolding_phase2_not_applicable"
    assert policy["policies"] == []
    assert policy["applied_floor"] is False
    assert policy["runtime_final_text"] == "嗯，我听见了。"
```

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_chinese_semantic_surface_phase2.py -q
```

Expected: fails because `build_runtime_replacement_policy` does not exist.

- [x] **Step 3: Implement minimal policy builder**

Add:

```python
CHINESE_SEMANTIC_PHASE2_READINESS = "chinese_semantic_descaffolding_phase2_ready"
CHINESE_SEMANTIC_PHASE2_NOT_APPLICABLE = "chinese_semantic_descaffolding_phase2_not_applicable"
CHINESE_SEMANTIC_PHASE2_IN_PROGRESS = "chinese_semantic_descaffolding_phase2_in_progress"

RUNTIME_POLICY_AUTHORITY_BOUNDARY = {
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

Implement `build_runtime_replacement_policy(text, family_context=None)` so each policy row contains:

- `family`
- `semantic_intent`
- `target_behavior`
- `replacement_strategy="deterministic_safe_surface_floor"`
- `applied_floor`
- `source="typed_semantic_family"`
- `authority_boundary`

The function returns one envelope with:

- `schema`
- `status`
- `readiness_status`
- `original_text`
- `runtime_final_text`
- `families`
- `policies`
- `selected_policy`
- `applied_floor`
- `authority_boundary`
- `failure_reasons`

- [x] **Step 4: Run policy tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_chinese_semantic_surface_phase2.py -q
```

Expected: all Chinese semantic surface Phase 2 tests pass.

- [x] **Step 5: Commit task slice**

Run:

```powershell
git add amadeus_thread0/graph_parts/chinese_semantic_surface.py tests/test_chinese_semantic_surface_phase2.py
git commit -m "feat: add chinese semantic runtime policy"
```

---

### Task 2: Runtime And Backend Payload Attachment

**Files:**
- Modify: `tests/test_embodied_interaction_runtime.py`
- Modify: `tests/test_backend_api.py`
- Modify: `amadeus_thread0/runtime/embodied_interaction_runtime.py`

- [x] **Step 1: Write failing runtime tests**

Add a test requiring `build_embodied_interaction_readback()` to expose the policy:

```python
def test_chinese_semantic_surface_exposes_runtime_policy_envelope():
    readback = build_embodied_interaction_readback(
        {
            "final_text": "请问有什么可以帮你？",
            "reconsolidation_snapshot": {"final_text": "请问有什么可以帮你？"},
        }
    )

    policy = readback["chinese_semantic_surface"]["runtime_policy"]
    assert policy["readiness_status"] == "chinese_semantic_descaffolding_phase2_ready"
    assert policy["selected_policy"]["family"] == "generic_assistant_tone"
    assert policy["selected_policy"]["replacement_strategy"] == "deterministic_safe_surface_floor"
    assert readback["final_text"] == policy["runtime_final_text"]
    assert readback["reconsolidation_snapshot"]["final_text"] == policy["runtime_final_text"]
    assert readback["chinese_semantic_surface"]["tts_text"] == readback["final_text"]
    assert readback["chinese_semantic_surface"]["text_tts_drift"] is False
```

Add backend coverage for turn/event payloads:

```python
def test_turn_response_exposes_chinese_runtime_policy_and_text_parity(self):
    state_values = {
        "final_text": "请问有什么可以帮你？",
        "reconsolidation_snapshot": {"final_text": "请问有什么可以帮你？"},
    }
    payload = api.build_turn_response(state_values=state_values, streamed_text="ignored").payload
    policy = payload["embodied_interaction"]["chinese_semantic_surface"]["runtime_policy"]
    assert policy["readiness_status"] == "chinese_semantic_descaffolding_phase2_ready"
    assert payload["reconsolidation_snapshot"]["final_text"] == payload["final_text"]
```

- [x] **Step 2: Run runtime/backend tests to verify RED**

Run:

```powershell
python -m pytest tests/test_embodied_interaction_runtime.py tests/test_backend_api.py -k "chinese_semantic or semantic_floor" -q
```

Expected: fails because runtime policy, `tts_text`, and `text_tts_drift` are not attached.

- [x] **Step 3: Attach policy to embodied interaction runtime**

Modify `_semantic_runtime_floor()` so it calls `build_runtime_replacement_policy(final_text)` and returns:

- `runtime_policy`
- `tts_text` equal to `runtime_final_text`
- `text_tts_drift=False`

Keep existing fields:

- `status`
- `families`
- `applied_floor`
- `original_text`
- `runtime_final_text`
- `replacement_plan`

- [x] **Step 4: Run runtime/backend tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_embodied_interaction_runtime.py tests/test_backend_api.py -k "chinese_semantic or semantic_floor" -q
```

Expected: selected runtime/backend tests pass.

- [x] **Step 5: Commit task slice**

Run:

```powershell
git add amadeus_thread0/runtime/embodied_interaction_runtime.py tests/test_embodied_interaction_runtime.py tests/test_backend_api.py
git commit -m "feat: attach chinese semantic policy to runtime"
```

---

### Task 3: Phase 2 Audit And Preserved Baseline

**Files:**
- Create: `evals/run_chinese_semantic_descaffolding_phase2_audit.py`
- Create: `tests/test_chinese_semantic_descaffolding_phase2_audit.py`
- Modify: `evals/run_preserved_baselines_audit.py`
- Modify: `tests/test_preserved_baselines_audit.py`

- [x] **Step 1: Write failing audit tests**

Create tests requiring:

- overall status `passed`;
- readiness `chinese_semantic_descaffolding_phase2_ready`;
- four scenarios: `everyday_generic_assistant`, `repair_teacherly_scold`, `self_rhythm_boundary_threat`, `technical_task_taskization`;
- no duplicate output;
- no scaffold residue leaks;
- no text/TTS drift;
- no model API calls, memory writes, behavior mutation, persona-core mutation, live capture, skill registry writes, frontend-owned semantics, or external mutation.

- [x] **Step 2: Run audit tests to verify RED**

Run:

```powershell
python -m pytest tests/test_chinese_semantic_descaffolding_phase2_audit.py tests/test_preserved_baselines_audit.py -q
```

Expected: fails because the Phase 2 audit module and preserved-baseline row do not exist.

- [x] **Step 3: Implement audit and baseline row**

The audit should call `build_runtime_replacement_policy()` and `build_embodied_interaction_readback()` for deterministic fixtures. It should write reports under:

```text
evals/reports/chinese-semantic-descaffolding-phase2-audit-*.json
evals/reports/chinese-semantic-descaffolding-phase2-audit-*.md
```

Add preserved baseline:

```python
{
    "id": "chinese_semantic_descaffolding_phase2",
    "prefix": "chinese-semantic-descaffolding-phase2-audit-",
    "expected_readiness": "chinese_semantic_descaffolding_phase2_ready",
    "category": "chinese_semantic",
}
```

- [x] **Step 4: Run audit tests and audit**

Run:

```powershell
python -m pytest tests/test_chinese_semantic_descaffolding_phase2_audit.py tests/test_preserved_baselines_audit.py -q
python evals/run_chinese_semantic_descaffolding_phase2_audit.py --run-tag phase2-dev
```

Expected: tests pass and audit prints `readiness=chinese_semantic_descaffolding_phase2_ready`.

- [x] **Step 5: Commit task slice**

Run:

```powershell
git add evals/run_chinese_semantic_descaffolding_phase2_audit.py tests/test_chinese_semantic_descaffolding_phase2_audit.py evals/run_preserved_baselines_audit.py tests/test_preserved_baselines_audit.py
git commit -m "test: audit chinese semantic phase 2"
```

---

### Task 4: Documentation, Final Verification, Merge, And Push

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `program.md`
- Modify: `docs/superpowers/plans/2026-05-07-chinese-semantic-descaffolding-phase2.md`

- [x] **Step 1: Update docs**

Document that Phase 2:

- reports `chinese_semantic_descaffolding_phase2_ready`;
- exposes a typed runtime replacement policy envelope;
- applies deterministic safe floors only for known semantic families;
- keeps `final_text`, `reconsolidation_snapshot.final_text`, and `tts_text` aligned;
- does not mutate persona core, memory, behavior motives, prompts, browser/tool/sandbox authority, frontend semantics, skill registry state, live capture, model APIs, or external state.

- [x] **Step 2: Commit docs**

Run:

```powershell
git add AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md docs/superpowers/plans/2026-05-07-chinese-semantic-descaffolding-phase2.md
git commit -m "docs: close chinese semantic phase 2"
```

- [x] **Step 3: Run final verification**

Run:

```powershell
python -m pytest tests/test_chinese_semantic_surface_phase2.py tests/test_chinese_semantic_descaffolding_phase2_audit.py tests/test_chinese_surface_de_scaffold_audit.py tests/test_embodied_interaction_runtime.py -q
python -m pytest tests/test_backend_api.py -k "chinese_semantic or semantic_floor or embodied_interaction" -q
python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py tests/test_tool_approval_policy.py -q
python -m py_compile amadeus_thread0/graph_parts/chinese_semantic_surface.py amadeus_thread0/runtime/embodied_interaction_runtime.py evals/run_chinese_surface_de_scaffold_audit.py evals/run_chinese_semantic_descaffolding_phase2_audit.py evals/run_preserved_baselines_audit.py
python evals/run_chinese_surface_de_scaffold_audit.py --run-tag phase2-regression
python evals/run_chinese_semantic_descaffolding_phase2_audit.py --run-tag phase2-final
python evals/run_embodied_interaction_runtime_phase5_audit.py --run-tag chinese-phase2-regression
git diff --check
```

- [ ] **Step 4: Merge and push**

Run from the original main worktree:

```powershell
git merge --ff-only codex/chinese-semantic-descaffolding-phase2
python -m pytest tests/test_chinese_semantic_surface_phase2.py tests/test_chinese_semantic_descaffolding_phase2_audit.py tests/test_backend_api.py -k "chinese_semantic or semantic_floor or embodied_interaction" -q
python evals/run_chinese_semantic_descaffolding_phase2_audit.py --run-tag post-merge
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
git push origin main
```

---

## Self-Review

- Spec coverage: covers the policy builder, runtime/backend attachment, deterministic audit, preserved baseline, docs, verification, merge, and push.
- Placeholder scan: no placeholder strings or open-ended implementation steps remain.
- Type consistency: `runtime_policy`, `selected_policy`, `semantic_intent`, `replacement_strategy`, `applied_floor`, `tts_text`, and `text_tts_drift` are used consistently across tests, runtime, audit, and docs.
