# Embodied Interaction Runtime Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert Phase 2 approved artifact semantic observations into bounded appraisal-facing evidence so perception can influence appraisal readback without memory write, persona-core mutation, live capture, multimodal model API calls, or execution-authority widening.

**Architecture:** Add one pure bridge module under `amadeus_thread0/runtime/artifact_appraisal_bridge.py`. `embodied_interaction_runtime.py` will keep Phase 1 source attachment and Phase 2 artifact semantics intact, then attach a Phase 3 `artifact_appraisal` block and mirror evidence into current-event perception, turn appraisal, perception semantics, and embodied carryover. `BackendAPI` already applies the embodied interaction adapter to `assistant_turn` and `event_round`, so backend payloads inherit Phase 3 through the existing attachment point.

**Tech Stack:** Python 3, existing backend payload dictionaries, `artifact_perception_semantics.py`, pytest, deterministic local eval runners.

---

## File Structure

- Create `amadeus_thread0/runtime/artifact_appraisal_bridge.py`
  - Owns read-only conversion from Phase 2 `semantic_observations` into appraisal evidence.
  - Accepts only approved metadata observations from `artifact_perception_semantics.v1` readbacks.
  - Emits evidence with `source=approved_metadata`, `model_api_called=False`, `memory_write_allowed=False`, and `writeback_ready=False`.
  - Produces deterministic appraisal axes and influence hints such as `task_relevance` and `access_friction`.
- Create `tests/test_artifact_appraisal_bridge.py`
  - Unit coverage for login/session friction, transcript/ocr evidence, blocked/empty readbacks, and no-writeback authority.
- Modify `amadeus_thread0/runtime/embodied_interaction_runtime.py`
  - Imports the bridge helper.
  - Adds Phase 3 readiness constants.
  - Adds `artifact_appraisal` to the `embodied_interaction` readback.
  - Mirrors evidence to `current_event.perception.appraisal_evidence`, `turn_appraisal.artifact_evidence`, `turn_appraisal.perception_semantics.appraisal_evidence`, and `interaction_carryover.embodied_context.artifact_appraisal_evidence`.
  - Preserves Phase 1 and Phase 2 readiness when no appraisal evidence exists.
- Extend `tests/test_embodied_interaction_runtime.py`
  - Verifies Phase 3 runtime surfaces and compact readback line behavior.
- Extend `tests/test_backend_api.py`
  - Verifies `assistant_turn` and `event_round` payloads carry Phase 3 appraisal evidence through the existing backend adapter.
- Create `evals/run_embodied_interaction_runtime_phase3_audit.py`
  - Deterministic Phase 3 audit with readiness `embodied_interaction_runtime_phase3_ready`.
- Create `tests/test_embodied_interaction_runtime_phase3_audit.py`
  - Verifies report readiness and markdown rendering.
- Modify `evals/run_preserved_baselines_audit.py`
  - Adds `embodied_interaction_runtime_phase3` as a preserved baseline with prefix `embodied-interaction-runtime-phase3-audit-`.
- Extend `tests/test_preserved_baselines_audit.py`
  - Adds the Phase 3 expected id and updates `embodied_interaction` category count from `2` to `3`.
- Modify `AGENTS.md`
  - Records Phase 3 as closed when implementation and audits pass.
- Modify `docs/engineering/PROJECT_STRUCTURE.md`
  - Documents `artifact_appraisal_bridge.py` and the Phase 3 audit entrypoint.
- Modify `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
  - Records Phase 3 as appraisal evidence coupling, not model vision or memory writeback.
- Modify `program.md`
  - Updates current state and adds the run ledger entry.

---

### Task 1: Artifact Appraisal Bridge

**Files:**
- Create: `tests/test_artifact_appraisal_bridge.py`
- Create: `amadeus_thread0/runtime/artifact_appraisal_bridge.py`

- [x] **Step 1: Write failing bridge tests**

Create `tests/test_artifact_appraisal_bridge.py`:

```python
from __future__ import annotations

from amadeus_thread0.runtime.artifact_appraisal_bridge import (
    build_artifact_appraisal_readback,
)


def _semantics(observations: list[dict]) -> dict:
    return {
        "schema": "artifact_perception_semantics.v1",
        "status": "ready" if observations else "empty",
        "readiness_status": "artifact_perception_semantics_ready" if observations else "artifact_perception_semantics_empty",
        "semantic_observations": observations,
        "observation_count": len(observations),
        "model_api_called": False,
        "writeback_ready_count": 0,
    }


def test_login_semantic_observation_becomes_access_friction_evidence():
    readback = build_artifact_appraisal_readback(
        _semantics(
            [
                {
                    "source_ref_id": "img-runtime-sem-1",
                    "source_kind": "image_file",
                    "modality": "image",
                    "semantic_label": "login_prompt",
                    "summary": "A login dialog with an expired session warning.",
                    "source": "approved_metadata",
                    "model_api_called": False,
                    "writeback_ready": False,
                }
            ]
        )
    )

    evidence = readback["evidence_items"][0]
    assert readback["schema"] == "artifact_appraisal_bridge.v1"
    assert readback["status"] == "ready"
    assert readback["readiness_status"] == "artifact_appraisal_bridge_ready"
    assert evidence["evidence_id"] == "artifact-evidence-img-runtime-sem-1"
    assert evidence["source_ref_id"] == "img-runtime-sem-1"
    assert evidence["semantic_label"] == "login_prompt"
    assert evidence["summary"] == "A login dialog with an expired session warning."
    assert evidence["appraisal_axes"] == ["task_relevance", "access_friction"]
    assert evidence["suggested_appraisal_delta"]["scene"] == "artifact_review"
    assert evidence["suggested_appraisal_delta"]["task_relevance"] == "high"
    assert evidence["suggested_appraisal_delta"]["access_friction"] is True
    assert evidence["authority"]["source"] == "approved_metadata"
    assert evidence["authority"]["model_api_called"] is False
    assert evidence["authority"]["memory_write_allowed"] is False
    assert evidence["authority"]["writeback_ready"] is False
    assert readback["influence_summary"]["artifact_relevance"] == "high"
    assert readback["influence_summary"]["access_friction_observed"] is True
    assert readback["influence_summary"]["should_request_live_capture"] is False
    assert readback["influence_summary"]["should_write_memory"] is False


def test_transcript_and_ocr_semantics_create_readonly_evidence_without_live_capture():
    readback = build_artifact_appraisal_readback(
        _semantics(
            [
                {
                    "source_ref_id": "audio-sem-1",
                    "source_kind": "audio_file",
                    "modality": "audio",
                    "observation_kind": "provided_transcript",
                    "summary": "刚才那段音频里提到需要继续看登录错误。",
                    "observed_text": "刚才那段音频里提到需要继续看登录错误。",
                    "source": "approved_metadata",
                    "model_api_called": False,
                    "writeback_ready": False,
                },
                {
                    "source_ref_id": "screen-sem-1",
                    "source_kind": "screen_snapshot_file",
                    "modality": "screen",
                    "observation_kind": "provided_ocr_text",
                    "summary": "Session expired. Sign in again.",
                    "observed_text": "Session expired. Sign in again.",
                    "source": "approved_metadata",
                    "model_api_called": False,
                    "writeback_ready": False,
                },
            ]
        )
    )

    assert readback["evidence_count"] == 2
    assert readback["influence_summary"]["should_request_live_capture"] is False
    assert all(item["authority"]["writeback_ready"] is False for item in readback["evidence_items"])


def test_empty_or_blocked_semantics_return_inert_readback():
    empty = build_artifact_appraisal_readback(
        {
            "schema": "artifact_perception_semantics.v1",
            "status": "empty",
            "readiness_status": "artifact_perception_semantics_empty",
            "semantic_observations": [],
        }
    )
    blocked = build_artifact_appraisal_readback(
        {
            "schema": "artifact_perception_semantics.v1",
            "status": "blocked",
            "readiness_status": "artifact_perception_semantics_blocked",
            "semantic_observations": [],
        }
    )

    assert empty["status"] == "empty"
    assert empty["evidence_items"] == []
    assert empty["influence_summary"]["artifact_relevance"] == "none"
    assert blocked["status"] == "blocked"
    assert blocked["evidence_items"] == []
    assert blocked["influence_summary"]["should_write_memory"] is False
```

- [x] **Step 2: Run bridge tests to verify RED**

Run:

```powershell
python -m pytest tests/test_artifact_appraisal_bridge.py -q
```

Expected: FAIL because `amadeus_thread0.runtime.artifact_appraisal_bridge` does not exist.

- [x] **Step 3: Implement bridge module**

Create `amadeus_thread0/runtime/artifact_appraisal_bridge.py` with:

```python
from __future__ import annotations

from typing import Any


ARTIFACT_APPRAISAL_BRIDGE_READY = "artifact_appraisal_bridge_ready"
ARTIFACT_APPRAISAL_BRIDGE_EMPTY = "artifact_appraisal_bridge_empty"
ARTIFACT_APPRAISAL_BRIDGE_BLOCKED = "artifact_appraisal_bridge_blocked"

AUTHORITY_BOUNDARY = {
    "persona_core_mutation_allowed": False,
    "memory_write_allowed": False,
    "external_mutation_allowed": False,
    "live_microphone_enabled": False,
    "live_camera_enabled": False,
    "background_screen_capture_enabled": False,
    "multimodal_model_api_called": False,
    "writeback_allowed": False,
}
```

Implement:

```python
def build_artifact_appraisal_readback(artifact_semantics: dict[str, Any] | None) -> dict[str, Any]:
    ...
```

The function must:

- read only `artifact_semantics["semantic_observations"]`
- accept observations only when:
  - `source == "approved_metadata"`
  - `model_api_called is False`
  - `writeback_ready is False`
- emit `evidence_items` with:
  - `evidence_id`
  - `source_ref_id`
  - `source_kind`
  - `semantic_label`
  - `summary`
  - `appraisal_axes`
  - `suggested_appraisal_delta`
  - `authority`
- classify `access_friction=True` when label, summary, observed text, or tags mention login/session/sign-in/access/credential/expired concepts in English or Chinese.
- return:
  - `schema=artifact_appraisal_bridge.v1`
  - `status=ready`, `empty`, or `blocked`
  - `readiness_status`
  - `evidence_items`
  - `evidence_count`
  - `blocked_observation_count`
  - `blocked_reasons`
  - `influence_summary`
  - `authority_boundary`
  - `model_api_called=False`
  - `writeback_ready_count=0`

- [x] **Step 4: Run bridge tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_artifact_appraisal_bridge.py -q
```

Expected: PASS.

- [x] **Step 5: Commit Task 1**

Run:

```powershell
git add amadeus_thread0/runtime/artifact_appraisal_bridge.py tests/test_artifact_appraisal_bridge.py
git commit -m "feat: add artifact appraisal bridge"
```

Expected: commit succeeds.

---

### Task 2: Runtime And Backend Attachment

**Files:**
- Modify: `amadeus_thread0/runtime/embodied_interaction_runtime.py`
- Modify: `tests/test_embodied_interaction_runtime.py`
- Modify: `tests/test_backend_api.py`

- [x] **Step 1: Write failing runtime/backend tests**

Extend `tests/test_embodied_interaction_runtime.py` with:

```python
def test_artifact_appraisal_evidence_reaches_appraisal_and_carryover_surfaces():
    turn = {
        "final_text": "嗯，我听见了。",
        "current_event": {
            "kind": "multimodal_observation",
            "perception": {"channel": "image"},
            "digital_body_hints": {
                "multimodal_sources": [
                    {
                        "source_id": "img-runtime-appraisal-1",
                        "modality": "image",
                        "path": "fixtures/login.png",
                        "consent_scope": "single_turn",
                        "capture_method": "operator_attached_file",
                        "semantic_summary": "A login dialog with an expired session warning.",
                        "semantic_label": "login_prompt",
                    }
                ]
            },
        },
        "turn_appraisal": {"scene": "artifact_review"},
        "interaction_carryover": {"embodied_context": {"kind": "multimodal_observation"}},
        "reconsolidation_snapshot": {"final_text": "嗯，我听见了。"},
    }

    readback = build_embodied_interaction_readback(turn)

    evidence = readback["artifact_appraisal"]["evidence_items"][0]
    assert readback["readiness_status"] == "embodied_interaction_runtime_phase3_ready"
    assert evidence["source_ref_id"] == "img-runtime-appraisal-1"
    assert evidence["suggested_appraisal_delta"]["access_friction"] is True
    assert readback["current_event"]["perception"]["appraisal_evidence"][0]["source_ref_id"] == "img-runtime-appraisal-1"
    assert readback["turn_appraisal"]["artifact_evidence"][0]["source_ref_id"] == "img-runtime-appraisal-1"
    assert readback["turn_appraisal"]["perception_semantics"]["appraisal_evidence"][0]["source_ref_id"] == "img-runtime-appraisal-1"
    assert readback["interaction_carryover"]["embodied_context"]["artifact_appraisal_evidence"][0]["source_ref_id"] == "img-runtime-appraisal-1"
```

Extend `tests/test_backend_api.py` with a backend payload test that builds both a turn response and an event response from the same semantic source and asserts:

```python
payload["embodied_interaction"]["readiness_status"] == "embodied_interaction_runtime_phase3_ready"
payload["embodied_interaction"]["artifact_appraisal"]["evidence_items"][0]["source_ref_id"] == "img-backend-appraisal-1"
payload["current_event"]["perception"]["appraisal_evidence"][0]["source_ref_id"] == "img-backend-appraisal-1"
payload["turn_appraisal"]["artifact_evidence"][0]["source_ref_id"] == "img-backend-appraisal-1"
payload["turn_appraisal"]["perception_semantics"]["appraisal_evidence"][0]["source_ref_id"] == "img-backend-appraisal-1"
payload["interaction_carryover"]["embodied_context"]["artifact_appraisal_evidence"][0]["source_ref_id"] == "img-backend-appraisal-1"
payload["embodied_interaction"]["artifact_appraisal"]["influence_summary"]["should_write_memory"] is False
```

- [x] **Step 2: Run runtime/backend tests to verify RED**

Run:

```powershell
python -m pytest tests/test_embodied_interaction_runtime.py -q
python -m pytest tests/test_backend_api.py -k "artifact_appraisal or artifact_semantics or embodied_interaction" -q
```

Expected: FAIL because Phase 3 runtime surfaces are not implemented yet.

- [x] **Step 3: Implement runtime attachment**

Modify `amadeus_thread0/runtime/embodied_interaction_runtime.py`:

- add constants:

```python
EMBODIED_INTERACTION_PHASE3_READINESS = "embodied_interaction_runtime_phase3_ready"
EMBODIED_INTERACTION_PHASE3_IN_PROGRESS = "embodied_interaction_runtime_phase3_in_progress"
```

- import:

```python
from .artifact_appraisal_bridge import build_artifact_appraisal_readback
```

- build:

```python
artifact_appraisal = build_artifact_appraisal_readback(artifact_semantics)
```

- set top-level readiness to Phase 3 ready when `artifact_appraisal["status"] == "ready"`.
- include `artifact_appraisal` in the returned readback.
- add evidence to:
  - `current_event.perception.appraisal_evidence`
  - `turn_appraisal.artifact_evidence`
  - `turn_appraisal.perception_semantics.appraisal_evidence`
  - `interaction_carryover.embodied_context.artifact_appraisal_evidence`
- keep Phase 2 behavior unchanged when `artifact_appraisal["status"]` is not `ready`.

- [x] **Step 4: Run runtime/backend tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_artifact_appraisal_bridge.py tests/test_artifact_perception_semantics.py tests/test_embodied_interaction_runtime.py -q
python -m pytest tests/test_backend_api.py -k "artifact_appraisal or artifact_semantics or embodied_interaction or living_loop_realism" -q
```

Expected: PASS.

- [x] **Step 5: Commit Task 2**

Run:

```powershell
git add amadeus_thread0/runtime/embodied_interaction_runtime.py tests/test_embodied_interaction_runtime.py tests/test_backend_api.py
git commit -m "feat: attach artifact appraisal evidence to embodied interaction"
```

Expected: commit succeeds.

---

### Task 3: Phase 3 Audit And Preserved Baseline

**Files:**
- Create: `evals/run_embodied_interaction_runtime_phase3_audit.py`
- Create: `tests/test_embodied_interaction_runtime_phase3_audit.py`
- Modify: `evals/run_preserved_baselines_audit.py`
- Modify: `tests/test_preserved_baselines_audit.py`

- [x] **Step 1: Write failing audit tests**

Create `tests/test_embodied_interaction_runtime_phase3_audit.py`:

```python
from __future__ import annotations

from evals.run_embodied_interaction_runtime_phase3_audit import build_report, render_markdown


def test_build_report_returns_phase3_ready():
    report = build_report(run_id="unit")

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "embodied_interaction_runtime_phase3_ready"
    assert report["summary"]["evidence_count"] >= 4
    assert report["summary"]["access_friction_observed"] is True
    assert report["summary"]["model_api_called"] is False
    assert report["summary"]["writeback_ready_count"] == 0
    assert report["summary"]["should_write_memory"] is False


def test_render_markdown_includes_phase3_scenarios():
    rendered = render_markdown(build_report(run_id="unit-md"))

    assert "# Embodied Interaction Runtime Phase 3 Audit" in rendered
    assert "`embodied_interaction_runtime_phase3_ready`" in rendered
    assert "| `artifact_semantics_becomes_appraisal_evidence` | `passed` |" in rendered
    assert "| `access_friction_observation_influences_appraisal_readback` | `passed` |" in rendered
    assert "| `backend_payload_carries_artifact_appraisal` | `passed` |" in rendered
    assert "| `blocked_live_capture_does_not_create_appraisal_evidence` | `passed` |" in rendered
```

Modify `tests/test_preserved_baselines_audit.py`:

- add expected id `embodied_interaction_runtime_phase3`
- change `summary["summary"]["categories"]["embodied_interaction"]["passed"]` from `2` to `3`

- [x] **Step 2: Run audit tests to verify RED**

Run:

```powershell
python -m pytest tests/test_embodied_interaction_runtime_phase3_audit.py tests/test_preserved_baselines_audit.py -q
```

Expected: FAIL because the Phase 3 audit entrypoint and preserved baseline row do not exist yet.

- [x] **Step 3: Implement Phase 3 audit**

Create `evals/run_embodied_interaction_runtime_phase3_audit.py` with deterministic scenarios:

- `artifact_semantics_becomes_appraisal_evidence`
- `access_friction_observation_influences_appraisal_readback`
- `transcript_and_ocr_observations_create_appraisal_evidence`
- `backend_payload_carries_artifact_appraisal`
- `blocked_live_capture_does_not_create_appraisal_evidence`
- `artifact_appraisal_does_not_write_memory_or_call_model_api`

The report must emit:

```python
"readiness_status": "embodied_interaction_runtime_phase3_ready"
```

when all scenarios pass.

- [x] **Step 4: Register preserved baseline**

Add to `BASELINE_SPECS` in `evals/run_preserved_baselines_audit.py`:

```python
{
    "id": "embodied_interaction_runtime_phase3",
    "prefix": "embodied-interaction-runtime-phase3-audit-",
    "expected_readiness": "embodied_interaction_runtime_phase3_ready",
    "category": "embodied_interaction",
}
```

- [x] **Step 5: Run audit tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_embodied_interaction_runtime_phase3_audit.py tests/test_preserved_baselines_audit.py -q
python evals/run_embodied_interaction_runtime_phase3_audit.py --run-tag phase3-dev
```

Expected: tests PASS and audit prints `readiness=embodied_interaction_runtime_phase3_ready`.

- [x] **Step 6: Commit Task 3**

Run:

```powershell
git add evals/run_embodied_interaction_runtime_phase3_audit.py tests/test_embodied_interaction_runtime_phase3_audit.py evals/run_preserved_baselines_audit.py tests/test_preserved_baselines_audit.py
git commit -m "test: add embodied interaction runtime phase 3 audit"
```

Expected: commit succeeds.

---

### Task 4: Documentation And Ledger Closure

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `program.md`
- Modify: `docs/superpowers/plans/2026-05-06-embodied-interaction-runtime-phase3.md`

- [x] **Step 1: Update project contracts**

Update `AGENTS.md`:

- add `Embodied Interaction Runtime Phase 3`
- add `embodied_interaction_runtime_phase3_ready` to preserved baselines
- state explicitly that Phase 3:
  - consumes Phase 2 approved semantic observations only
  - turns them into appraisal-facing evidence and influence hints
  - mirrors evidence into current-event perception, turn appraisal, perception semantics, and embodied carryover
  - does not call multimodal model APIs
  - does not open live microphone/camera/background screen capture
  - does not mutate memory, persona core, browser/tool/sandbox authority, skill registry, or frontend-owned semantics

Update `docs/engineering/PROJECT_STRUCTURE.md`:

- add `artifact_appraisal_bridge.py`
- update `embodied_interaction_runtime.py` ownership to include Phase 3 appraisal evidence attachment
- add `run_embodied_interaction_runtime_phase3_audit.py`

Update `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`:

- record `embodied_interaction_runtime_phase3_ready`
- update backend status, audit list, current posture, and implementation order

Update `program.md`:

- update Current State to Phase 3
- add a dated run entry with files changed, validations, result, and next step

- [x] **Step 2: Run doc/placeholder scan**

Run:

```powershell
rg -n "T[B]D|T[O]DO|implement[ ]later|fill[ ]in[ ]details|Similar[ ]to[ ]Task" AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md docs/superpowers/plans/2026-05-06-embodied-interaction-runtime-phase3.md amadeus_thread0/runtime/artifact_appraisal_bridge.py amadeus_thread0/runtime/embodied_interaction_runtime.py tests/test_artifact_appraisal_bridge.py tests/test_embodied_interaction_runtime.py evals/run_embodied_interaction_runtime_phase3_audit.py tests/test_embodied_interaction_runtime_phase3_audit.py
```

Expected: no matches.

- [x] **Step 3: Commit Task 4**

Run:

```powershell
git add AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md docs/superpowers/plans/2026-05-06-embodied-interaction-runtime-phase3.md
git commit -m "docs: record embodied interaction runtime phase 3"
```

Expected: commit succeeds.

---

### Task 5: Final Verification, Merge, And Push

**Files:**
- All files touched by Tasks 1-4.

- [x] **Step 1: Run focused runtime/backend verification**

Run:

```powershell
python -m pytest tests/test_artifact_appraisal_bridge.py tests/test_artifact_perception_semantics.py tests/test_embodied_interaction_runtime.py tests/test_embodied_interaction_runtime_phase2_audit.py tests/test_embodied_interaction_runtime_phase3_audit.py tests/test_multimodal_sources.py -q
python -m pytest tests/test_backend_api.py -k "artifact_appraisal or artifact_semantics or embodied_interaction or living_loop_realism or turn_and_event_responses_attach_operator_readback" -q
```

Expected: PASS.

- [x] **Step 2: Run required backend/memory regressions**

Run:

```powershell
python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py tests/test_tool_approval_policy.py -q
python -m pytest tests/test_memory_guard.py tests/test_session_orchestrator.py -q
```

Expected: PASS.

- [x] **Step 3: Run graph entrypoint checks**

Run:

```powershell
python -m py_compile amadeus_thread0/agent.py amadeus_thread0/graph.py amadeus_thread0/runtime/artifact_perception_semantics.py amadeus_thread0/runtime/artifact_appraisal_bridge.py amadeus_thread0/runtime/embodied_interaction_runtime.py amadeus_thread0/runtime/backend_api.py evals/run_embodied_interaction_runtime_phase2_audit.py evals/run_embodied_interaction_runtime_phase3_audit.py evals/run_preserved_baselines_audit.py
python -c "from amadeus_thread0.agent import agent; print(type(agent).__name__)"
```

Expected: compile passes and prints `CompiledStateGraph`.

- [x] **Step 4: Run phase audits**

Run:

```powershell
python evals/run_embodied_interaction_runtime_phase2_audit.py --run-tag phase3-regression
python evals/run_embodied_interaction_runtime_phase3_audit.py --run-tag phase3-final
python evals/run_living_loop_realism_phase2_audit.py --run-tag embodied-phase3-regression
```

Expected:

- Phase 2 audit reports `embodied_interaction_runtime_phase2_ready`
- Phase 3 audit reports `embodied_interaction_runtime_phase3_ready`
- living-loop realism phase 2 audit reports `living_loop_runtime_realism_phase2_ready`

- [x] **Step 5: Run diff checks**

Run:

```powershell
git diff --check
git status --short --branch
```

Expected:

- no diff-check errors other than benign Windows LF-to-CRLF warnings
- only intended files are modified

- [x] **Step 6: Commit any remaining tracked changes**

If any intended changes remain unstaged:

```powershell
git add AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md docs/superpowers/plans/2026-05-06-embodied-interaction-runtime-phase3.md amadeus_thread0/runtime/artifact_appraisal_bridge.py amadeus_thread0/runtime/embodied_interaction_runtime.py evals/run_embodied_interaction_runtime_phase3_audit.py evals/run_preserved_baselines_audit.py tests/test_artifact_appraisal_bridge.py tests/test_embodied_interaction_runtime.py tests/test_backend_api.py tests/test_embodied_interaction_runtime_phase3_audit.py tests/test_preserved_baselines_audit.py
git commit -m "feat: close embodied interaction runtime phase 3"
```

Expected: commit succeeds or there is nothing to commit.

- [x] **Step 7: Merge to main**

Run from primary workspace:

```powershell
git -C E:\桌面\amadeus-thread0 status --short --branch
git -C E:\桌面\amadeus-thread0 merge --ff-only codex/embodied-interaction-runtime-phase3
```

Expected:

- primary workspace remains on `main`
- merge fast-forwards
- existing untracked `third_party/benchmarks/ESConv` remains untouched

- [x] **Step 8: Post-merge verification on main**

Run from `E:\桌面\amadeus-thread0`:

```powershell
python -m pytest tests/test_artifact_appraisal_bridge.py tests/test_embodied_interaction_runtime.py tests/test_embodied_interaction_runtime_phase3_audit.py tests/test_backend_api.py -k "artifact_appraisal or artifact_semantics or embodied_interaction or living_loop_realism" -q
python evals/run_embodied_interaction_runtime_phase3_audit.py --run-tag post-merge
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
```

Expected:

- tests PASS
- Phase 3 audit reports `embodied_interaction_runtime_phase3_ready`
- preserved baselines audit reports `preserved_baselines_ready`

- [x] **Step 9: Push main**

Run:

```powershell
git -C E:\桌面\amadeus-thread0 push origin main
```

Expected: push succeeds.

---

## Self-Review

- Spec coverage:
  - Approved artifact semantics become appraisal-facing evidence: Tasks 1-2.
  - Access-friction influence from login/session observations: Tasks 1 and 3.
  - Transcript/OCR evidence without live capture: Tasks 1 and 3.
  - Backend `assistant_turn` and `event_round` payload attachment: Task 2.
  - Blocked live capture remains inert: Tasks 1 and 3.
  - No model API call / no memory write / no new authority: Tasks 1, 3, and 4.
  - Audit and preserved baseline closure: Task 3 and Task 5.
  - Docs and run ledger: Task 4.
- Placeholder scan:
  - No task uses vague placeholders; concrete paths, commands, expected outputs, and field names are specified.
- Type consistency:
  - The plan consistently uses `artifact_appraisal`, `evidence_items`, `appraisal_evidence`, `artifact_evidence`, `artifact_appraisal_evidence`, `influence_summary`, and `embodied_interaction_runtime_phase3_ready`.
