# Living Loop Runtime Realism Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Attach living-loop realism readback to real backend turn/event payloads and audit backend-style payload causality rather than only deterministic fixtures.

**Architecture:** Keep `amadeus_thread0/runtime/living_loop_realism.py` as the pure readback owner and add a backend-payload adapter over the existing Phase 1 causality evaluator. `BackendAPI` attaches the readback after constructing `assistant_turn` and `event_round` payloads, while a new Phase 2 audit proves backend-shaped payloads are the evidence source.

**Tech Stack:** Python 3, existing `BackendAPI` envelopes, pytest, local eval audit scripts, no graph generation changes, no memory writes, no tool/browser/sandbox execution, and no persona-core mutation.

---

## File Structure

- Modify `amadeus_thread0/runtime/living_loop_realism.py`
  - Add Phase 2 readiness constants.
  - Add backend-payload normalization from `assistant_turn` / `event_round` payload shape into the Phase 1 current-turn shape.
  - Add backend-payload readback and compact line helpers.
- Modify `amadeus_thread0/runtime/backend_api.py`
  - Preserve explicit `values["writeback_trace"]` fixtures when no memory store is present.
  - Attach `payload["living_loop_realism"]` after constructing turn/event payloads.
- Create `evals/run_living_loop_realism_phase2_audit.py`
  - Build a backend-style payload from the deterministic Phase 1 fixture plus backend-only surfaces.
  - Emit `living-loop-realism-phase2-audit-*` reports.
- Create `tests/test_living_loop_realism_phase2_audit.py`
  - Lock Phase 2 audit report and markdown behavior.
- Modify tests:
  - `tests/test_living_loop_realism.py`
  - `tests/test_backend_api.py`
  - `tests/test_preserved_baselines_audit.py`
- Modify docs and ledger:
  - `AGENTS.md`
  - `docs/engineering/PROJECT_STRUCTURE.md`
  - `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
  - `program.md`

### Task 1: Backend Payload Realism Adapter

**Files:**
- Modify: `amadeus_thread0/runtime/living_loop_realism.py`
- Modify: `tests/test_living_loop_realism.py`

- [x] **Step 1: Write failing tests**

Add tests asserting that a backend-shaped payload with `turn_summary` and `writeback_trace` returns Phase 2 readiness:

```python
from amadeus_thread0.runtime.living_loop_realism import (
    LIVING_LOOP_REALISM_PHASE2_READINESS,
    build_backend_payload_realism_readback,
    compact_backend_payload_realism_line,
    normalize_backend_turn_payload_for_realism,
)

def test_backend_payload_readback_returns_phase2_ready():
    payload = _backend_payload()
    readback = build_backend_payload_realism_readback(payload)
    assert readback["schema"] == "living_loop_realism.backend_payload.v1"
    assert readback["readiness_status"] == LIVING_LOOP_REALISM_PHASE2_READINESS
    assert readback["backend_payload"]["source"] == "backend_payload"
    assert readback["backend_payload"]["status"] == "ready"
    assert readback["causality"]["status"] == "ready"

def test_backend_payload_requires_backend_only_surfaces():
    payload = _backend_payload()
    payload.pop("turn_summary")
    readback = build_backend_payload_realism_readback(payload)
    assert readback["overall_status"] == "in_progress"
    assert readback["backend_payload"]["status"] == "missing"
    assert "turn_summary" in readback["backend_payload"]["missing_fields"]

def test_backend_payload_compact_line_names_source_status():
    line = compact_backend_payload_realism_line(
        build_backend_payload_realism_readback(_backend_payload())
    )
    assert "backend_payload=ready" in line
    assert "realism=living_loop_runtime_realism_phase2_ready" in line
```

- [x] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_living_loop_realism.py -q
```

Expected: FAIL because Phase 2 constants and backend-payload helpers do not exist.

- [x] **Step 3: Implement minimal adapter**

Add constants:

```python
LIVING_LOOP_REALISM_PHASE2_READINESS = "living_loop_runtime_realism_phase2_ready"
LIVING_LOOP_REALISM_PHASE2_IN_PROGRESS = "living_loop_runtime_realism_phase2_in_progress"
```

Add:

```python
BACKEND_PAYLOAD_REQUIRED_FIELDS = (
    "final_text",
    "behavior_action",
    "behavior_plan",
    "turn_summary",
    "writeback_trace",
    "reconsolidation_snapshot",
)
```

Implement `normalize_backend_turn_payload_for_realism(payload)` by copying the actual backend fields:

```python
def normalize_backend_turn_payload_for_realism(payload):
    data = _dict_or_empty(payload)
    return {
        "final_text": data.get("final_text"),
        "current_event": _dict_or_empty(data.get("current_event")),
        "turn_appraisal": _dict_or_empty(data.get("turn_appraisal")),
        "emotion_state": _dict_or_empty(data.get("emotion_state")),
        "bond_state": _dict_or_empty(data.get("bond_state")),
        "allostasis_state": _dict_or_empty(data.get("allostasis_state")),
        "counterpart_assessment": _dict_or_empty(data.get("counterpart_assessment")),
        "semantic_narrative_profile": _dict_or_empty(data.get("semantic_narrative_profile")),
        "behavior_action": _dict_or_empty(data.get("behavior_action")),
        "behavior_plan": _dict_or_empty(data.get("behavior_plan")),
        "digital_body_consequence": _dict_or_empty(data.get("digital_body_consequence")),
        "reconsolidation_snapshot": _dict_or_empty(data.get("reconsolidation_snapshot")),
        "writeback_trace": _dict_or_empty(data.get("writeback_trace")),
    }
```

Implement `build_backend_payload_realism_readback(payload)` so Phase 2 is ready only when:

- backend-only payload fields are present
- Phase 1 causality is ready over the normalized current-turn view
- authority boundaries remain the same closed readback boundary

- [x] **Step 4: Run test to verify it passes**

Run:

```powershell
python -m pytest tests/test_living_loop_realism.py -q
```

Expected: PASS.

### Task 2: BackendAPI Attachment

**Files:**
- Modify: `amadeus_thread0/runtime/backend_api.py`
- Modify: `tests/test_backend_api.py`

- [x] **Step 1: Write failing tests**

Update `FakeBackendSession.extract_final_text()` to return `values["final_text"]` when present:

```python
def extract_final_text(self, values, *, streamed_text=""):
    self.last_extract_args = (values, streamed_text)
    data = values if isinstance(values, dict) else {}
    return str(data.get("final_text") or "final from session")
```

Add a backend API test using the same realistic state values:

```python
for payload in (turn_payload, event_payload):
    readback = payload["living_loop_realism"]
    assert readback["schema"] == "living_loop_realism.backend_payload.v1"
    assert readback["readiness_status"] == "living_loop_runtime_realism_phase2_ready"
    assert readback["backend_payload"]["status"] == "ready"
```

- [x] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_backend_api.py -k living_loop_realism -q
```

Expected: FAIL because `living_loop_realism` is not attached.

- [x] **Step 3: Implement backend attachment**

Import:

```python
from .living_loop_realism import build_backend_payload_realism_readback
```

After `payload = {...}` in both `build_event_round_response()` and `build_turn_response()`, attach:

```python
payload["living_loop_realism"] = build_backend_payload_realism_readback(payload)
```

Update `_writeback_trace_payload()` so explicit `values["writeback_trace"]` is preserved when it is a dict and no memory-store current-turn trace can be built:

```python
explicit_trace = _dict_or_empty(data.get("writeback_trace"))
if explicit_trace and store is None:
    trace = dict(explicit_trace)
    trace.setdefault("turn_started_at", anchor_ts)
    return trace
```

- [x] **Step 4: Run test to verify it passes**

Run:

```powershell
python -m pytest tests/test_backend_api.py -k living_loop_realism -q
```

Expected: PASS.

### Task 3: Phase 2 Audit And Preserved Baseline

**Files:**
- Create: `evals/run_living_loop_realism_phase2_audit.py`
- Create: `tests/test_living_loop_realism_phase2_audit.py`
- Modify: `evals/run_preserved_baselines_audit.py`
- Modify: `tests/test_preserved_baselines_audit.py`

- [x] **Step 1: Write failing tests**

Add audit tests:

```python
from evals.run_living_loop_realism_phase2_audit import build_backend_payload_fixture, build_report, render_markdown

def test_phase2_report_returns_ready():
    report = build_report(run_id="test-run")
    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "living_loop_runtime_realism_phase2_ready"
    assert report["readback"]["backend_payload"]["status"] == "ready"

def test_phase2_fixture_contains_backend_only_surfaces():
    payload = build_backend_payload_fixture()
    assert "turn_summary" in payload
    assert "writeback_trace" in payload
    assert "operator_readback" in payload

def test_phase2_markdown_renders_backend_payload_status():
    rendered = render_markdown(build_report(run_id="render-test"))
    assert "# Living Loop Runtime Realism Phase 2 Audit" in rendered
    assert "`living_loop_runtime_realism_phase2_ready`" in rendered
    assert "Backend Payload" in rendered
```

Update preserved-baseline expectations to add:

```python
"living_loop_runtime_realism_phase2"
```

with prefix:

```python
"living-loop-realism-phase2-audit-"
```

- [x] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_living_loop_realism_phase2_audit.py tests/test_preserved_baselines_audit.py -q
```

Expected: FAIL because the audit file and preserved baseline row do not exist.

- [x] **Step 3: Implement audit and baseline row**

Create `evals/run_living_loop_realism_phase2_audit.py` with:

- `build_backend_payload_fixture()`
- `build_report(run_id=...)`
- `render_markdown(report)`
- `main()`

The audit must call `build_backend_payload_realism_readback(payload)` and emit:

- `living-loop-realism-phase2-audit-<run_id>.json`
- `living-loop-realism-phase2-audit-<run_id>.md`

Add the new preserved-baseline spec:

```python
{
    "id": "living_loop_runtime_realism_phase2",
    "prefix": "living-loop-realism-phase2-audit-",
    "expected_readiness": "living_loop_runtime_realism_phase2_ready",
    "category": "living_loop_realism",
}
```

- [x] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/test_living_loop_realism_phase2_audit.py tests/test_preserved_baselines_audit.py -q
```

Expected: PASS.

### Task 4: Docs, Ledger, Verification, Merge

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `program.md`

- [x] **Step 1: Update docs**

Record `Living Loop Runtime Realism Phase 2` as a backend-payload integration gate:

- `living_loop_runtime_realism_phase2_ready`
- attaches `living_loop_realism` to `assistant_turn` and `event_round`
- validates backend-style payloads instead of only deterministic fixtures
- does not alter graph generation, persona core, memory-write authority, browser/tool/sandbox execution, frontend semantics, or Chinese prompt constraints

- [x] **Step 2: Run focused verification**

Run:

```powershell
python -m pytest tests/test_living_loop_realism.py tests/test_living_loop_realism_audit.py tests/test_living_loop_realism_phase2_audit.py tests/test_preserved_baselines_audit.py -q
python -m pytest tests/test_backend_api.py -k "living_loop_realism or turn_and_event_responses_attach_operator_readback" -q
python evals/run_living_loop_realism_phase2_audit.py --run-tag phase2-final
python evals/run_living_loop_realism_audit.py --run-tag phase2-regression
python -m py_compile amadeus_thread0/runtime/living_loop_realism.py amadeus_thread0/runtime/backend_api.py evals/run_living_loop_realism_phase2_audit.py evals/run_preserved_baselines_audit.py
git diff --check
```

Expected:

- pytest commands pass
- Phase 2 audit prints `readiness=living_loop_runtime_realism_phase2_ready`
- Phase 1 audit still prints `readiness=living_loop_runtime_realism_phase1_ready`
- compile passes
- diff check has no errors beyond possible Windows line-ending warnings

- [x] **Step 3: Placeholder scan**

Run:

```powershell
rg -n -e "T[B]D" -e "T[O]DO" -e "f[i]ll in" -e "implement la[t]er" docs\superpowers\plans\2026-05-06-living-loop-runtime-realism-phase2.md amadeus_thread0\runtime\living_loop_realism.py amadeus_thread0\runtime\backend_api.py evals\run_living_loop_realism_phase2_audit.py tests\test_living_loop_realism.py tests\test_backend_api.py tests\test_living_loop_realism_phase2_audit.py
```

Expected: no matches.

- [x] **Step 4: Commit, merge, and push**

Run:

```powershell
git add AGENTS.md amadeus_thread0/runtime/living_loop_realism.py amadeus_thread0/runtime/backend_api.py evals/run_living_loop_realism_phase2_audit.py evals/run_preserved_baselines_audit.py tests/test_living_loop_realism.py tests/test_backend_api.py tests/test_living_loop_realism_phase2_audit.py tests/test_preserved_baselines_audit.py docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md docs/superpowers/plans/2026-05-06-living-loop-runtime-realism-phase2.md program.md
git commit -m "feat: attach living loop realism to backend payloads"
git -C E:\桌面\amadeus-thread0 merge --ff-only codex/living-loop-runtime-realism-phase2
git -C E:\桌面\amadeus-thread0 push origin main
```

Expected: commit succeeds, local `main` fast-forwards, post-merge verification passes in the main workspace, and push succeeds.

## Self-Review

- Spec coverage: The plan covers backend-payload adaptation, BackendAPI attachment, Phase 2 audit, preserved-baseline integration, docs, verification, merge, and push.
- Placeholder scan: The plan contains concrete functions, commands, expected outputs, and exact files without deferred implementation instructions.
- Type consistency: The plan consistently uses `living_loop_realism.backend_payload.v1`, `living_loop_runtime_realism_phase2_ready`, and `living-loop-realism-phase2-audit-*`.
