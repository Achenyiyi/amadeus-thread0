# Multimodal Perception Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add approval-gated multimodal artifact inspection packets and approved-result semantics without enabling live capture or automatic multimodal model API calls.

**Architecture:** Phase 2 extends the existing consent-bound multimodal source contract with one bounded `artifact:inspect_multimodal` packet surface. The packet is preview-only until approval, completed observations only come from a precomputed approved inspection result, and artifact semantics/runtime readback mirrors that result as read-only evidence. No graph generation, persona core, memory authority, browser/sandbox authority, frontend semantics, skill registry, or live capture behavior changes.

**Tech Stack:** Python 3, pytest, deterministic `evals/` audit scripts, existing action-packet normalization, existing embodied interaction readback.

---

## File Structure

- `amadeus_thread0/runtime/multimodal_sources.py`
  - Owns Phase 1 source normalization and adds Phase 2 inspection spec/preview/result helpers plus `build_multimodal_inspection_packet()`.
- `amadeus_thread0/graph_parts/action_packets.py`
  - Preserves `multimodal_inspection_spec`, `multimodal_inspection_preview`, and `multimodal_inspection_result` through generic action packet normalization.
- `amadeus_thread0/runtime/artifact_perception_semantics.py`
  - Converts completed approved multimodal inspection results into read-only semantic observations with `source=approved_inspection_result`.
- `amadeus_thread0/runtime/embodied_interaction_runtime.py`
  - Includes action-packet approved inspection results as artifact semantics candidates for backend-style payloads.
- `tests/test_multimodal_perception_phase2.py`
  - New RED/GREEN unit and integration tests for packet contract, live capture blocking, approved results, and embodied runtime mirroring.
- `tests/test_action_packet_contract.py`
  - Adds one contract test proving multimodal inspection packet fields survive normalization.
- `tests/test_artifact_perception_semantics.py`
  - Adds one test proving approved inspection result semantics are admitted and pending/rejected results are ignored.
- `evals/run_multimodal_perception_phase2_audit.py`
  - New deterministic audit covering pending approval, completed approved inspection, rejected inspection, and blocked live capture.
- `tests/test_multimodal_perception_phase2_audit.py`
  - Tests audit readiness and markdown rendering.
- `evals/run_preserved_baselines_audit.py`
  - Adds `multimodal_perception_phase2_ready` as a preserved multimodal baseline.
- `tests/test_preserved_baselines_audit.py`
  - Updates expected preserved baseline ids and category counts.
- `AGENTS.md`, `docs/engineering/PROJECT_STRUCTURE.md`, `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`, `program.md`
  - Records the closed Phase 2 contract and verification.

---

### Task 1: Multimodal Inspection Packet Contract

**Files:**
- Modify: `amadeus_thread0/runtime/multimodal_sources.py`
- Modify: `amadeus_thread0/graph_parts/action_packets.py`
- Create: `tests/test_multimodal_perception_phase2.py`
- Modify: `tests/test_action_packet_contract.py`

- [x] **Step 1: Write the failing packet tests**

Create `tests/test_multimodal_perception_phase2.py` with tests that import:

```python
from amadeus_thread0.graph_parts.action_packets import normalize_action_packet
from amadeus_thread0.runtime.multimodal_sources import (
    build_multimodal_inspection_packet,
    normalize_multimodal_source,
)
```

Add `test_inspection_packet_requires_approval_and_never_auto_executes()`:

```python
source = normalize_multimodal_source(
    {
        "source_id": "img-inspect-1",
        "modality": "image",
        "path": "fixtures/panel.png",
        "consent_scope": "single_turn",
        "capture_method": "operator_attached_file",
        "label": "panel.png",
    }
)

packet = build_multimodal_inspection_packet(source, origin="counterpart_request")

assert packet["intent"] == "artifact:inspect_multimodal"
assert packet["status"] == "awaiting_approval"
assert packet["risk"] == "external_mutation"
assert packet["requires_approval"] is True
assert packet["writeback_ready"] is False
assert packet["proposal_id"].startswith("ap-")
assert packet["tool_name"] == "inspect_multimodal_artifact"
assert packet["multimodal_inspection_spec"]["source_ref_id"] == "img-inspect-1"
assert packet["multimodal_inspection_spec"]["model_api_call_allowed"] is False
assert packet["multimodal_inspection_spec"]["live_capture_allowed"] is False
assert packet["multimodal_inspection_preview"]["auto_execute"] is False
assert packet["multimodal_inspection_preview"]["model_api_call_planned"] is False
assert packet["multimodal_inspection_preview"]["requires_approval"] is True
```

Add `test_blocked_live_capture_builds_blocked_packet_without_model_preview()`:

```python
source = normalize_multimodal_source(
    {
        "source_id": "mic-live-phase2",
        "modality": "audio",
        "artifact_ref": "live:microphone",
        "consent_scope": "single_turn",
        "capture_method": "background_microphone",
    }
)

packet = build_multimodal_inspection_packet(source, origin="counterpart_request")

assert source["status"] == "blocked"
assert packet["status"] == "blocked"
assert packet["requires_approval"] is False
assert packet["writeback_ready"] is False
assert packet["block_reason"] == "blocked_capture_method"
assert packet["multimodal_inspection_preview"]["blocked"] is True
assert packet["multimodal_inspection_preview"]["auto_execute"] is False
assert packet["multimodal_inspection_preview"]["model_api_call_planned"] is False
```

Add `test_action_packet_normalizer_preserves_multimodal_inspection_fields()`:

```python
source = normalize_multimodal_source(
    {
        "source_id": "screen-inspect-1",
        "modality": "screen",
        "path": "fixtures/screen.png",
        "consent_scope": "single_turn",
        "capture_method": "operator_attached_file",
    }
)
packet = build_multimodal_inspection_packet(source)
normalized = normalize_action_packet(packet)

assert normalized["multimodal_inspection_spec"]["source_ref_id"] == "screen-inspect-1"
assert normalized["multimodal_inspection_preview"]["auto_execute"] is False
assert normalized["multimodal_inspection_result"] == {}
```

- [x] **Step 2: Run test to verify RED**

Run:

```powershell
python -m pytest tests/test_multimodal_perception_phase2.py -q
```

Expected: FAIL because `build_multimodal_inspection_packet` does not exist.

- [x] **Step 3: Implement minimal packet contract**

In `amadeus_thread0/runtime/multimodal_sources.py` add:

```python
MULTIMODAL_PERCEPTION_PHASE2_READY = "multimodal_perception_phase2_ready"
MULTIMODAL_PERCEPTION_PHASE2_IN_PROGRESS = "multimodal_perception_phase2_in_progress"

def normalize_multimodal_inspection_spec(value: Any) -> dict[str, Any]:
    ...

def normalize_multimodal_inspection_preview(value: Any) -> dict[str, Any]:
    ...

def normalize_multimodal_inspection_result(value: Any) -> dict[str, Any]:
    ...

def build_multimodal_inspection_packet(
    source: dict[str, Any] | None,
    *,
    origin: str = "counterpart_request",
    status: str = "awaiting_approval",
    approved_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ...
```

The packet must use:

```python
"intent": "artifact:inspect_multimodal"
"risk": "external_mutation"
"requires_approval": True for pending proposals
"requires_approval": False for blocked/rejected/completed rows
"tool_name": "inspect_multimodal_artifact"
"writeback_ready": True only for completed approved fixture results
```

The spec must include:

```python
"source_ref_id"
"modality"
"artifact_ref"
"artifact_label"
"consent_scope"
"capture_method"
"inspection_mode": "model_assisted_artifact_inspection"
"approved_result_required": True
"model_api_call_allowed": False
"live_capture_allowed": False
```

The preview must include:

```python
"requires_approval": True
"auto_execute": False
"model_api_call_planned": False
"live_capture_allowed": False
"blocked": False or True
```

In `amadeus_thread0/graph_parts/action_packets.py`, add normalizers for those three fields and include them in:

```python
action_packet_has_signal()
normalize_action_packet()
build_tool_action_packet()
__all__
```

- [x] **Step 4: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_multimodal_perception_phase2.py tests/test_action_packet_contract.py -k "multimodal or action_packet" -q
```

Expected: PASS.

- [x] **Step 5: Commit**

Run:

```powershell
git add amadeus_thread0/runtime/multimodal_sources.py amadeus_thread0/graph_parts/action_packets.py tests/test_multimodal_perception_phase2.py tests/test_action_packet_contract.py
git commit -m "feat: add multimodal inspection packet contract"
```

---

### Task 2: Approved Inspection Result Semantics

**Files:**
- Modify: `amadeus_thread0/runtime/artifact_perception_semantics.py`
- Modify: `amadeus_thread0/runtime/embodied_interaction_runtime.py`
- Modify: `tests/test_multimodal_perception_phase2.py`
- Modify: `tests/test_artifact_perception_semantics.py`
- Modify: `tests/test_embodied_interaction_runtime.py`

- [x] **Step 1: Write failing approved-result tests**

Add `test_completed_approved_inspection_result_becomes_semantic_observation()`:

```python
source = {
    "source_id": "img-approved-1",
    "modality": "image",
    "path": "fixtures/panel.png",
    "consent_scope": "single_turn",
    "capture_method": "operator_attached_file",
    "multimodal_inspection_result": {
        "status": "completed",
        "approval_status": "approved",
        "source_ref_id": "img-approved-1",
        "semantic_summary": "The panel shows a failed login message.",
        "tags": ["login", "failure"],
        "confidence": 0.83,
    },
}
readback = build_artifact_semantics_readback([source])
observation = readback["semantic_observations"][0]

assert readback["status"] == "ready"
assert observation["source"] == "approved_inspection_result"
assert observation["source_ref_id"] == "img-approved-1"
assert observation["summary"] == "The panel shows a failed login message."
assert observation["model_api_called"] is False
assert observation["writeback_ready"] is False
```

Add `test_pending_and_rejected_inspection_results_do_not_emit_semantics()`:

```python
readback = build_artifact_semantics_readback(
    [
        {
            "source_id": "img-pending",
            "modality": "image",
            "path": "fixtures/pending.png",
            "consent_scope": "single_turn",
            "capture_method": "operator_attached_file",
            "multimodal_inspection_result": {
                "status": "awaiting_approval",
                "approval_status": "pending",
                "semantic_summary": "Should not be admitted.",
            },
        },
        {
            "source_id": "img-rejected",
            "modality": "image",
            "path": "fixtures/rejected.png",
            "consent_scope": "single_turn",
            "capture_method": "operator_attached_file",
            "multimodal_inspection_result": {
                "status": "rejected",
                "approval_status": "rejected",
                "semantic_summary": "Should not be admitted.",
            },
        },
    ]
)

assert readback["status"] == "empty"
assert readback["semantic_observations"] == []
```

Add `test_runtime_uses_completed_action_packet_inspection_result_as_semantics()`:

```python
source = normalize_multimodal_source({...})
packet = build_multimodal_inspection_packet(
    source,
    status="completed",
    approved_result={"semantic_summary": "A checklist is visible.", "tags": ["checklist"], "confidence": 0.8},
)
readback = build_embodied_interaction_readback(
    {
        "final_text": "嗯，我看到了。",
        "current_event": {"digital_body_hints": {"multimodal_sources": [source]}},
        "action_packets": [packet],
        "reconsolidation_snapshot": {"final_text": "嗯，我看到了。"},
    }
)

assert readback["artifact_semantics"]["semantic_observations"][0]["source"] == "approved_inspection_result"
assert readback["current_event"]["perception"]["semantic_observations"][0]["source_ref_id"] == source["source_id"]
```

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_multimodal_perception_phase2.py tests/test_artifact_perception_semantics.py -k "inspection or approved" -q
```

Expected: FAIL because approved inspection results are not mirrored.

- [x] **Step 3: Implement approved-result semantic mirroring**

In `artifact_perception_semantics.py`:

- import `normalize_multimodal_inspection_result`;
- detect `raw["multimodal_inspection_result"]`;
- admit only normalized results where:

```python
status == "completed"
approval_status == "approved"
model_api_called is False
```

- emit observation with:

```python
"source": "approved_inspection_result"
"model_api_called": False
"writeback_ready": False
```

In `embodied_interaction_runtime.py`:

- add a helper that pulls completed action packets with `intent="artifact:inspect_multimodal"` and `multimodal_inspection_result`;
- append those as semantic source candidates before calling `build_artifact_semantics_readback()`;
- do not add pending, rejected, or blocked packet results.

- [x] **Step 4: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_multimodal_perception_phase2.py tests/test_artifact_perception_semantics.py tests/test_embodied_interaction_runtime.py -k "inspection or approved or embodied_interaction" -q
```

Expected: PASS.

- [x] **Step 5: Commit**

Run:

```powershell
git add amadeus_thread0/runtime/artifact_perception_semantics.py amadeus_thread0/runtime/embodied_interaction_runtime.py tests/test_multimodal_perception_phase2.py tests/test_artifact_perception_semantics.py tests/test_embodied_interaction_runtime.py
git commit -m "feat: mirror approved multimodal inspections"
```

---

### Task 3: Phase 2 Audit And Preserved Baseline

**Files:**
- Create: `evals/run_multimodal_perception_phase2_audit.py`
- Create: `tests/test_multimodal_perception_phase2_audit.py`
- Modify: `evals/run_preserved_baselines_audit.py`
- Modify: `tests/test_preserved_baselines_audit.py`

- [x] **Step 1: Write failing audit tests**

Create `tests/test_multimodal_perception_phase2_audit.py`:

```python
from evals.run_multimodal_perception_phase2_audit import build_report, render_markdown


def test_phase2_audit_reports_ready():
    report = build_report(run_id="unit")
    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "multimodal_perception_phase2_ready"
    assert report["summary"]["scenario_count"] == 4
    assert report["summary"]["model_api_called"] is False
    assert report["summary"]["live_capture_enabled"] is False
    assert report["summary"]["memory_write_allowed"] is False


def test_phase2_audit_markdown_names_ready_status():
    rendered = render_markdown(
        {
            "overall_status": "passed",
            "readiness_status": "multimodal_perception_phase2_ready",
            "summary": {"scenario_count": 4},
            "scenarios": [{"name": "pending_approval", "status": "passed", "readiness_status": "multimodal_perception_phase2_ready"}],
            "failure_reasons": [],
        }
    )
    assert "Multimodal Perception Phase 2 Audit" in rendered
    assert "multimodal_perception_phase2_ready" in rendered
```

Update `tests/test_preserved_baselines_audit.py`:

- add `multimodal_perception_phase2` to expected ids;
- assert category `multimodal_perception` has one passed row.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_multimodal_perception_phase2_audit.py tests/test_preserved_baselines_audit.py -q
```

Expected: FAIL because the audit script and preserved baseline row do not exist.

- [x] **Step 3: Implement audit and baseline row**

Create `evals/run_multimodal_perception_phase2_audit.py` with deterministic scenarios:

- pending approval: packet awaits approval, no model call, no semantics;
- completed approved inspection: completed packet with precomputed result becomes approved-result semantic observation;
- rejected inspection: rejected packet produces no semantic observation and no writeback;
- blocked live capture: background microphone/camera/screen stay blocked with no live capture enabled.

The report must expose:

```python
"overall_status": "passed"
"readiness_status": "multimodal_perception_phase2_ready"
"summary": {
    "scenario_count": 4,
    "model_api_called": False,
    "live_capture_enabled": False,
    "memory_write_allowed": False,
    "external_mutation_allowed": False,
}
```

Add the preserved baseline spec:

```python
{
    "id": "multimodal_perception_phase2",
    "prefix": "multimodal-perception-phase2-audit-",
    "expected_readiness": "multimodal_perception_phase2_ready",
    "category": "multimodal_perception",
}
```

- [x] **Step 4: Run tests and audit to verify GREEN**

Run:

```powershell
python -m pytest tests/test_multimodal_perception_phase2_audit.py tests/test_preserved_baselines_audit.py -q
python evals/run_multimodal_perception_phase2_audit.py --run-tag phase2-dev
```

Expected: tests pass and audit prints `readiness=multimodal_perception_phase2_ready`.

- [x] **Step 5: Commit**

Run:

```powershell
git add evals/run_multimodal_perception_phase2_audit.py tests/test_multimodal_perception_phase2_audit.py evals/run_preserved_baselines_audit.py tests/test_preserved_baselines_audit.py
git commit -m "test: audit multimodal perception phase 2"
```

---

### Task 4: Documentation, Verification, Merge, Push

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `program.md`
- Modify: `docs/superpowers/plans/2026-05-07-multimodal-perception-phase2.md`

- [x] **Step 1: Update documentation**

Document:

- `multimodal_perception_phase2_ready` is closed;
- approved artifacts may propose `artifact:inspect_multimodal` packets;
- pending packets are approval-gated and never auto-execute;
- completed semantics are accepted only from approved precomputed inspection results;
- `model_api_called=false`, `live_capture_allowed=false`, `memory_write_allowed=false`, `writeback_ready=false`;
- live microphone/camera/background screen capture remains blocked.

- [x] **Step 2: Run focused verification**

Run:

```powershell
python -m pytest tests/test_multimodal_sources.py tests/test_multimodal_perception_phase2.py tests/test_artifact_perception_semantics.py tests/test_embodied_interaction_runtime.py -q
python -m pytest tests/test_backend_api.py -k "multimodal or artifact_semantics or embodied_interaction" -q
python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py tests/test_tool_approval_policy.py -q
python -m py_compile amadeus_thread0/runtime/multimodal_sources.py amadeus_thread0/runtime/artifact_perception_semantics.py amadeus_thread0/runtime/embodied_interaction_runtime.py amadeus_thread0/graph_parts/action_packets.py amadeus_thread0/graph_parts/autonomy_runtime.py evals/run_multimodal_perception_phase2_audit.py evals/run_preserved_baselines_audit.py
python evals/run_multimodal_perception_phase2_audit.py --run-tag phase2-final
python evals/run_chinese_semantic_descaffolding_phase2_audit.py --run-tag multimodal-phase2-regression
python evals/run_embodied_interaction_runtime_phase5_audit.py --run-tag multimodal-phase2-regression
git diff --check
```

Expected: all commands exit 0.

- [x] **Step 3: Commit documentation**

Run:

```powershell
git add AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md docs/superpowers/plans/2026-05-07-multimodal-perception-phase2.md
git commit -m "docs: record multimodal perception phase 2"
```

- [x] **Step 4: Merge to main and post-merge verify**

Run:

```powershell
cd E:\桌面\amadeus-thread0
git merge --ff-only codex/multimodal-perception-phase2
python -m pytest tests/test_multimodal_sources.py tests/test_multimodal_perception_phase2.py tests/test_backend_api.py -k "multimodal or artifact_semantics or embodied_interaction" -q
python evals/run_multimodal_perception_phase2_audit.py --run-tag post-merge
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
```

Expected: merge succeeds, focused tests pass, phase audit reports `multimodal_perception_phase2_ready`, preserved-baseline audit reports `preserved_baselines_ready`.

- [ ] **Step 5: Push main**

Run:

```powershell
git push origin main
```

Expected: push succeeds.

---

## Self-Review

- Spec coverage: The plan covers approval-gated inspection packet creation, blocked live capture, preview-only pending behavior, completed approved fixture result, semantic mirroring, deterministic audit, preserved-baseline registration, docs, merge, post-merge verification, and push.
- Placeholder scan: No step uses TBD/TODO/fill-in instructions; every code-facing step names concrete functions, fields, and commands.
- Type consistency: The same packet field names are used throughout: `multimodal_inspection_spec`, `multimodal_inspection_preview`, and `multimodal_inspection_result`.
