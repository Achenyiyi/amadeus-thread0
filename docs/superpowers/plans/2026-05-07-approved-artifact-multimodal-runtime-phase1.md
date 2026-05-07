# Approved Artifact Multimodal Runtime Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the `approved_artifact_multimodal_runtime` lane by adding an audited runtime seam that ingests already-approved, precomputed artifact inspection results into completed `artifact:inspect_multimodal` action packets without live capture, multimodal model calls, memory writes, or authority widening.

**Architecture:** Add a focused runtime module that validates a frozen pending/approved multimodal inspection packet, checks an operator approval/result payload for proposal/spec/source drift and authority violations, and returns either a completed packet or a fail-closed readback. Existing embodied interaction and artifact semantics modules continue to consume completed packets; this phase supplies the missing approval-result ingestion gate and audit evidence.

**Tech Stack:** Python standard library, existing `action_packets`, `multimodal_sources`, `artifact_perception_semantics`, `embodied_interaction_runtime`, pytest, deterministic eval runners.

---

## File Structure

- Create `amadeus_thread0/runtime/approved_artifact_multimodal_runtime.py`
  - Owns Phase 1 readiness constants, authority boundary, approval/result validation, packet completion, payload application, and compact readback helpers.
- Create `tests/test_approved_artifact_multimodal_runtime.py`
  - Tests exact proposal completion, embodied semantic consumption, drift rejection, model/live-capture rejection, and payload application.
- Create `evals/run_approved_artifact_multimodal_runtime_phase1_audit.py`
  - Runs deterministic scenarios and writes JSON/Markdown reports with readiness `approved_artifact_multimodal_runtime_phase1_ready`.
- Create `tests/test_approved_artifact_multimodal_runtime_phase1_audit.py`
  - Unit tests audit pass/fail rendering and authority boundary.
- Modify `evals/run_preserved_baselines_audit.py`
  - Registers the new preserved baseline id `approved_artifact_multimodal_runtime_phase1`.
- Modify `tests/test_preserved_baselines_audit.py`
  - Adds expected baseline id and category assertion coverage.
- Modify `amadeus_thread0/runtime/runtime_status_dashboard.py`
  - Marks multimodal artifact inspection as Phase 1 ready and removes this lane from `NEXT_SPECS`.
- Modify `tests/test_runtime_status_dashboard.py`
  - Updates dashboard expectations for the newly closed lane.
- Modify docs:
  - `AGENTS.md`
  - `program.md`
  - `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
  - `docs/engineering/PROJECT_STRUCTURE.md`
  - `docs/engineering/BACKEND_HANDOFF.md`
  - `docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md`

---

### Task 1: Runtime Seam Tests

**Files:**
- Create: `tests/test_approved_artifact_multimodal_runtime.py`

- [ ] **Step 1: Write failing tests for exact approved-result ingestion**

Create `tests/test_approved_artifact_multimodal_runtime.py` with tests that import:

```python
from amadeus_thread0.runtime.approved_artifact_multimodal_runtime import (
    APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_READY,
    apply_approved_artifact_multimodal_runtime_to_payload,
    build_approved_artifact_multimodal_runtime_readback,
    compact_approved_artifact_multimodal_runtime_line,
)
```

The first test should:

```python
source = normalize_multimodal_source({...})
pending = build_multimodal_inspection_packet(source)
readback = build_approved_artifact_multimodal_runtime_readback(
    pending,
    approval={"proposal_id": pending["proposal_id"], "approval_status": "approved"},
    approved_result={
        "source_ref_id": "img-approved-runtime-1",
        "semantic_summary": "The approved result says a checklist is visible.",
        "tags": ["checklist"],
        "confidence": 0.84,
    },
)
```

Assert:

- `readback["readiness_status"] == APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_READY`
- `readback["completed_packet"]["proposal_id"] == pending["proposal_id"]`
- completed packet status is `completed`
- completed packet `writeback_ready` is `True`
- completed result source is `approved_inspection_result`
- `model_api_called`, live capture, memory write, and external mutation remain false
- feeding the completed packet into `build_embodied_interaction_readback(...)` produces one `approved_inspection_result` semantic observation

- [ ] **Step 2: Write failing tests for drift and unsafe result rejection**

Add tests for:

- source/proposal drift: approved result uses a different `source_ref_id`
- approval drift: approval `proposal_id` does not match the packet
- unsafe result: raw `approved_result` includes `model_api_called=True`
- unsafe result: raw `approved_result` includes `live_capture_used=True`

Assert each readback is `in_progress`, has no completed packet, and never emits semantic observations when inserted into a payload.

- [ ] **Step 3: Write failing tests for payload application and compact readback**

Add a payload test:

```python
payload = {
    "kind": "assistant_turn",
    "final_text": "嗯，我看到了。",
    "current_event": {"digital_body_hints": {"multimodal_sources": [source]}},
    "action_packets": [pending],
    "reconsolidation_snapshot": {"final_text": "嗯，我看到了。"},
}
updated = apply_approved_artifact_multimodal_runtime_to_payload(
    payload,
    approvals=[{"proposal_id": pending["proposal_id"], "approval_status": "approved"}],
    approved_results=[{"proposal_id": pending["proposal_id"], "semantic_summary": "..."}],
)
```

Assert:

- `updated["action_packets"][0]["status"] == "completed"`
- `updated["approved_artifact_multimodal_runtime"]["readiness_status"] == APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_READY`
- compact line contains `approved_artifact_multimodal=approved_artifact_multimodal_runtime_phase1_ready`
- original input payload is not mutated

- [ ] **Step 4: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_approved_artifact_multimodal_runtime.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'amadeus_thread0.runtime.approved_artifact_multimodal_runtime'`.

---

### Task 2: Runtime Seam Implementation

**Files:**
- Create: `amadeus_thread0/runtime/approved_artifact_multimodal_runtime.py`
- Test: `tests/test_approved_artifact_multimodal_runtime.py`

- [ ] **Step 1: Implement constants and helpers**

Create constants:

```python
APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_READY = "approved_artifact_multimodal_runtime_phase1_ready"
APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_IN_PROGRESS = "approved_artifact_multimodal_runtime_phase1_in_progress"
```

Authority boundary must keep all mutation/model/live-capture surfaces false:

```python
AUTHORITY_BOUNDARY = {
    "persona_core_mutation_allowed": False,
    "memory_write_allowed": False,
    "external_mutation_allowed": False,
    "live_microphone_enabled": False,
    "live_camera_enabled": False,
    "background_screen_capture_enabled": False,
    "live_capture_allowed": False,
    "multimodal_model_api_called": False,
    "multimodal_model_api_call_allowed": False,
    "skill_registry_write_allowed": False,
    "frontend_semantics_owner": False,
}
```

- [ ] **Step 2: Implement fail-closed validation**

Implement `build_approved_artifact_multimodal_runtime_readback(packet, *, approval=None, approved_result=None)` so it:

- normalizes the incoming packet with `normalize_action_packet`
- requires `intent == "artifact:inspect_multimodal"`
- requires a non-empty `proposal_id`
- if approval is present, requires approval `proposal_id` to match
- requires approval status to be `approved`
- requires packet status to be `awaiting_approval` or `approved`
- requires spec and preview to stay non-executing:
  - `model_api_call_allowed is False`
  - `live_capture_allowed is False`
  - `auto_execute is False`
  - `model_api_call_planned is False`
- rejects raw approved result booleans that imply model/live execution:
  - `model_api_called`
  - `model_api_call_allowed`
  - `model_api_call_planned`
  - `live_capture_used`
  - `live_capture_allowed`
  - `background_capture_used`
- requires result `source_ref_id`, `modality`, `artifact_ref`, and `artifact_label` to match the frozen spec when provided
- builds a completed packet preserving the same `proposal_id`, spec, preview, origin, tool binding, and capability steps
- sets completed packet:
  - `status="completed"`
  - `requires_approval=False`
  - `writeback_ready=True`
  - `result_summary` from semantic summary/caption/observed text

- [ ] **Step 3: Implement payload application**

Implement `apply_approved_artifact_multimodal_runtime_to_payload(payload, *, approvals=None, approved_results=None)` so it:

- copies the payload
- indexes approvals/results by `proposal_id`
- attempts completion for matching `artifact:inspect_multimodal` packets
- leaves failed or unmatched packets unchanged
- writes `approved_artifact_multimodal_runtime` readback with summary counts
- returns the copied payload

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_approved_artifact_multimodal_runtime.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit runtime seam**

```powershell
git add amadeus_thread0/runtime/approved_artifact_multimodal_runtime.py tests/test_approved_artifact_multimodal_runtime.py docs/superpowers/plans/2026-05-07-approved-artifact-multimodal-runtime-phase1.md
git commit -m "feat: add approved artifact multimodal runtime seam"
```

---

### Task 3: Audit And Preserved Baseline

**Files:**
- Create: `evals/run_approved_artifact_multimodal_runtime_phase1_audit.py`
- Create: `tests/test_approved_artifact_multimodal_runtime_phase1_audit.py`
- Modify: `evals/run_preserved_baselines_audit.py`
- Modify: `tests/test_preserved_baselines_audit.py`

- [ ] **Step 1: Write failing audit tests**

Create audit tests that assert:

- `build_report(run_id="unit")` passes with `approved_artifact_multimodal_runtime_phase1_ready`
- the report has scenarios:
  - `approved_result_ingestion`
  - `proposal_or_source_drift_rejected`
  - `model_api_or_live_capture_rejected`
  - `backend_payload_packet_completion`
- authority boundary keeps live capture/model/memory/external mutation false
- markdown contains the readiness string

Modify preserved baseline tests to expect new id:

```python
"approved_artifact_multimodal_runtime_phase1"
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_approved_artifact_multimodal_runtime_phase1_audit.py tests/test_preserved_baselines_audit.py -q
```

Expected: FAIL because audit runner and preserved-baseline row are not implemented.

- [ ] **Step 3: Implement deterministic audit**

The audit runner must:

- import the runtime seam and existing embodied readback functions
- build deterministic source/pending packet fixtures
- run four scenarios
- compute overall pass only when:
  - exactly four scenarios pass
  - at least one semantic observation is produced from an approved result
  - no rejected/drifted/unsafe result becomes a completed packet
  - no model API/live capture/memory/external mutation authority appears
- write JSON and Markdown under prefix:
  - `approved-artifact-multimodal-runtime-phase1-audit-`

- [ ] **Step 4: Register preserved baseline**

Add to `BASELINE_SPECS`:

```python
{
    "id": "approved_artifact_multimodal_runtime_phase1",
    "prefix": "approved-artifact-multimodal-runtime-phase1-audit-",
    "expected_readiness": "approved_artifact_multimodal_runtime_phase1_ready",
    "category": "multimodal_runtime",
}
```

- [ ] **Step 5: Run tests and audit**

Run:

```powershell
python -m pytest tests/test_approved_artifact_multimodal_runtime_phase1_audit.py tests/test_preserved_baselines_audit.py -q
python evals/run_approved_artifact_multimodal_runtime_phase1_audit.py --run-tag phase1-dev
```

Expected: tests pass and audit prints `readiness=approved_artifact_multimodal_runtime_phase1_ready`.

- [ ] **Step 6: Commit audit gate**

```powershell
git add evals/run_approved_artifact_multimodal_runtime_phase1_audit.py tests/test_approved_artifact_multimodal_runtime_phase1_audit.py evals/run_preserved_baselines_audit.py tests/test_preserved_baselines_audit.py
git commit -m "test: add approved artifact multimodal runtime audit"
```

---

### Task 4: Dashboard And Documentation

**Files:**
- Modify: `amadeus_thread0/runtime/runtime_status_dashboard.py`
- Modify: `tests/test_runtime_status_dashboard.py`
- Modify: docs listed in File Structure

- [ ] **Step 1: Write failing dashboard expectation**

Update dashboard tests so:

- `multimodal_artifact_inspection.status == "phase1_ready"`
- `multimodal_artifact_inspection.runtime_authority == "approved_result_ingestion_only"`
- first next spec is `chinese_semantic_naturalness`
- compact line reports `next_specs=2`

Run:

```powershell
python -m pytest tests/test_runtime_status_dashboard.py -q
```

Expected: FAIL because dashboard still lists approved multimodal as next spec.

- [ ] **Step 2: Update dashboard**

Remove `approved_artifact_multimodal_runtime` from `NEXT_SPECS`.

Update lane:

```python
"multimodal_artifact_inspection": {
    "status": "phase1_ready",
    "runtime_authority": "approved_result_ingestion_only",
    "summary": "Already-approved precomputed artifact inspection results can complete frozen packets without live capture or model calls.",
}
```

- [ ] **Step 3: Update docs**

Document the new closed baseline:

- `AGENTS.md`: add `approved_artifact_multimodal_runtime_phase1_ready` and a bullet describing the boundary.
- `program.md`: append a concise ledger entry with plan, commits, tests, audit, and next priority.
- `AMADEUS_ARCHITECTURE_DECISIONS.md`: add the architecture decision and audit command.
- `PROJECT_STRUCTURE.md`: list new module/test/audit.
- `BACKEND_HANDOFF.md`: add a short approved artifact multimodal status section.
- `FRONTEND_INTERFACE_DELIVERABLE.md`: note optional backend-owned `approved_artifact_multimodal_runtime` readback and packet completion semantics.

- [ ] **Step 4: Run docs/dashboard tests**

Run:

```powershell
python -m pytest tests/test_runtime_status_dashboard.py tests/test_preserved_baselines_audit.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit dashboard/docs**

```powershell
git add AGENTS.md program.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/BACKEND_HANDOFF.md docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md amadeus_thread0/runtime/runtime_status_dashboard.py tests/test_runtime_status_dashboard.py
git commit -m "docs: close approved artifact multimodal runtime phase 1"
```

---

### Task 5: Final Verification, Merge, And Push

**Files:**
- All touched files

- [ ] **Step 1: Run focused verification**

Run:

```powershell
python -m pytest tests/test_approved_artifact_multimodal_runtime.py tests/test_approved_artifact_multimodal_runtime_phase1_audit.py tests/test_multimodal_perception_phase2.py tests/test_artifact_perception_semantics.py tests/test_embodied_interaction_runtime.py tests/test_runtime_status_dashboard.py tests/test_preserved_baselines_audit.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run compile and diff checks**

Run:

```powershell
python -m py_compile amadeus_thread0/runtime/approved_artifact_multimodal_runtime.py evals/run_approved_artifact_multimodal_runtime_phase1_audit.py evals/run_preserved_baselines_audit.py amadeus_thread0/runtime/runtime_status_dashboard.py
git diff --check
```

Expected: exit 0. Windows line-ending warnings are acceptable only if exit code remains 0.

- [ ] **Step 3: Run audits**

Run:

```powershell
python evals/run_approved_artifact_multimodal_runtime_phase1_audit.py --run-tag phase1-final
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
```

Expected:

- `approved_artifact_multimodal_runtime_phase1_ready`
- `preserved_baselines_ready`

- [ ] **Step 4: Merge to main and verify again**

Run:

```powershell
git checkout main
git pull --ff-only
git merge codex/approved-artifact-multimodal-runtime-phase1
python -m pytest tests/test_approved_artifact_multimodal_runtime.py tests/test_approved_artifact_multimodal_runtime_phase1_audit.py tests/test_multimodal_perception_phase2.py tests/test_artifact_perception_semantics.py tests/test_embodied_interaction_runtime.py tests/test_runtime_status_dashboard.py tests/test_preserved_baselines_audit.py -q
python evals/run_approved_artifact_multimodal_runtime_phase1_audit.py --run-tag post-merge
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
```

Expected: merge succeeds, tests pass, and audits report ready.

- [ ] **Step 5: Push and cleanup**

Run:

```powershell
git push origin main
git worktree remove C:\Users\29920\.config\superpowers\worktrees\amadeus-thread0\approved-artifact-multimodal-runtime-phase1
git worktree prune
git branch -d codex/approved-artifact-multimodal-runtime-phase1
```

Expected: `main` is pushed, worktree is removed, and branch is deleted.

---

## Self-Review

- Spec coverage: covers approved-result ingestion, frozen proposal/spec matching, backend payload application, embodied semantic consumption, drift/unsafe rejection, audit, preserved baseline, dashboard, and docs.
- Placeholder scan: no TBD/TODO/fill-in placeholders remain.
- Type consistency: the plan consistently uses `approved_artifact_multimodal_runtime_phase1_ready`, `approved_artifact_multimodal_runtime.v1`, `artifact:inspect_multimodal`, `multimodal_inspection_spec`, `multimodal_inspection_preview`, and `multimodal_inspection_result`.
