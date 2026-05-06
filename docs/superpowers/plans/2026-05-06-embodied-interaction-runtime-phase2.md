# Embodied Interaction Runtime Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote approved artifact metadata such as summaries, captions, transcripts, OCR text, and semantic tags into bounded perception-facing semantic observations without opening live capture, multimodal model API calls, persona-core mutation, memory writes, or new execution authority.

**Architecture:** Add one pure semantic-normalization module under `amadeus_thread0/runtime/artifact_perception_semantics.py`. `embodied_interaction_runtime.py` will keep the existing Phase 1 source and Chinese-surface behavior, then add a Phase 2 `artifact_semantics` block and mirror observations into `current_event.perception.semantic_observations`, `turn_appraisal.perception_semantics`, and `interaction_carryover.embodied_context.artifact_semantic_observations`. `BackendAPI` already applies the embodied interaction adapter to `assistant_turn` and `event_round`, so Phase 2 stays inside that existing runtime attachment point.

**Tech Stack:** Python 3, existing backend payload dictionaries, `multimodal_sources.py`, pytest, deterministic local eval runners.

---

## File Structure

- Create `amadeus_thread0/runtime/artifact_perception_semantics.py`
  - Owns approved-artifact semantic observation normalization.
  - Accepts existing multimodal source rows and only uses already-provided metadata fields.
  - Emits `model_api_called=False` and `writeback_ready=False` for every observation.
  - Blocks live microphone/camera/background screen/secret capture by reusing `normalize_multimodal_source()`.
- Modify `amadeus_thread0/runtime/embodied_interaction_runtime.py`
  - Imports the artifact semantic helper.
  - Adds Phase 2 readiness constants.
  - Adds `artifact_semantics` to `embodied_interaction`.
  - Mirrors semantic observations into current-event perception, appraisal readback, and carryover.
  - Deep-merges `current_event.perception` so existing perception fields are not overwritten.
- Add `tests/test_artifact_perception_semantics.py`
  - Unit coverage for image summaries, audio transcripts, screen OCR, browser summaries, blocked live capture, and no-model/no-writeback authority.
- Extend `tests/test_embodied_interaction_runtime.py`
  - Verifies Phase 2 runtime surfaces and compact line behavior.
- Extend `tests/test_backend_api.py`
  - Verifies `assistant_turn` and `event_round` payloads carry Phase 2 observations through the existing backend attachment path.
- Add `evals/run_embodied_interaction_runtime_phase2_audit.py`
  - Deterministic Phase 2 audit with artifact semantic scenarios and readiness `embodied_interaction_runtime_phase2_ready`.
- Add `tests/test_embodied_interaction_runtime_phase2_audit.py`
  - Verifies report readiness and markdown rendering.
- Modify `evals/run_preserved_baselines_audit.py`
  - Adds `embodied_interaction_runtime_phase2` as a preserved baseline with prefix `embodied-interaction-runtime-phase2-audit-`.
- Extend `tests/test_preserved_baselines_audit.py`
  - Updates expected id set and `embodied_interaction` category count from 1 to 2.
- Modify `AGENTS.md`
  - Records the Phase 2 closed contract and adds the readiness to preserved baselines.
- Modify `docs/engineering/PROJECT_STRUCTURE.md`
  - Documents `artifact_perception_semantics.py` and the Phase 2 audit entrypoint.
- Modify `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
  - Records Phase 2 as approved artifact perception semantics, not live capture or model vision.
- Modify `program.md`
  - Updates current state and adds the run ledger entry.

---

### Task 1: Artifact Semantic Normalization

**Files:**
- Create: `tests/test_artifact_perception_semantics.py`
- Create: `amadeus_thread0/runtime/artifact_perception_semantics.py`

- [x] **Step 1: Write failing semantic normalization tests**

Create `tests/test_artifact_perception_semantics.py` with tests for these exact behaviors:

```python
from __future__ import annotations

from amadeus_thread0.runtime.artifact_perception_semantics import (
    build_artifact_semantics_readback,
)


def test_image_summary_metadata_becomes_semantic_observation():
    readback = build_artifact_semantics_readback(
        [
            {
                "source_id": "img-sem-1",
                "modality": "image",
                "path": "fixtures/login.png",
                "consent_scope": "single_turn",
                "capture_method": "operator_attached_file",
                "label": "login.png",
                "semantic_label": "login_prompt",
                "semantic_summary": "A login dialog with an expired session warning.",
                "semantic_tags": ["login", "expired-session"],
                "confidence": 0.72,
            }
        ]
    )

    observation = readback["semantic_observations"][0]
    assert readback["status"] == "ready"
    assert readback["readiness_status"] == "artifact_perception_semantics_ready"
    assert observation["source_ref_id"] == "img-sem-1"
    assert observation["source_kind"] == "image_file"
    assert observation["observation_kind"] == "operator_provided_artifact_semantics"
    assert observation["semantic_label"] == "login_prompt"
    assert observation["summary"] == "A login dialog with an expired session warning."
    assert observation["tags"] == ["login", "expired-session"]
    assert observation["confidence"] == 0.72
    assert observation["source"] == "approved_metadata"
    assert observation["model_api_called"] is False
    assert observation["writeback_ready"] is False


def test_audio_transcript_becomes_transcript_observation():
    readback = build_artifact_semantics_readback(
        [
            {
                "source_id": "audio-sem-1",
                "modality": "audio",
                "path": "fixtures/voice.wav",
                "consent_scope": "single_turn",
                "capture_method": "operator_attached_file",
                "transcript": "刚才那段音频里提到需要继续看登录错误。",
            }
        ]
    )

    observation = readback["semantic_observations"][0]
    assert observation["source_kind"] == "audio_file"
    assert observation["observation_kind"] == "provided_transcript"
    assert observation["summary"] == "刚才那段音频里提到需要继续看登录错误。"
    assert observation["observed_text"] == "刚才那段音频里提到需要继续看登录错误。"


def test_blocked_live_capture_does_not_emit_semantic_observation():
    readback = build_artifact_semantics_readback(
        [
            {
                "source_id": "mic-live-sem",
                "modality": "audio",
                "artifact_ref": "live:microphone",
                "consent_scope": "single_turn",
                "capture_method": "background_microphone",
                "transcript": "This must not be admitted.",
            }
        ]
    )

    assert readback["status"] == "blocked"
    assert readback["semantic_observations"] == []
    assert readback["blocked_source_count"] == 1
    assert readback["authority_boundary"]["multimodal_model_api_called"] is False
    assert readback["authority_boundary"]["memory_write_allowed"] is False
```

- [x] **Step 2: Run semantic tests to verify RED**

Run:

```powershell
python -m pytest tests/test_artifact_perception_semantics.py -q
```

Expected: FAIL because `amadeus_thread0.runtime.artifact_perception_semantics` does not exist.

- [x] **Step 3: Implement semantic normalization**

Create `amadeus_thread0/runtime/artifact_perception_semantics.py` with:

```python
from __future__ import annotations

from typing import Any

from .multimodal_sources import normalize_multimodal_source


ARTIFACT_PERCEPTION_SEMANTICS_READY = "artifact_perception_semantics_ready"
ARTIFACT_PERCEPTION_SEMANTICS_EMPTY = "artifact_perception_semantics_empty"
ARTIFACT_PERCEPTION_SEMANTICS_BLOCKED = "artifact_perception_semantics_blocked"

SOURCE_KIND_BY_MODALITY = {
    "text": "text",
    "image": "image_file",
    "audio": "audio_file",
    "screen": "screen_snapshot_file",
    "browser_capture": "browser_capture_ref",
}

AUTHORITY_BOUNDARY = {
    "persona_core_mutation_allowed": False,
    "memory_write_allowed": False,
    "external_mutation_allowed": False,
    "live_microphone_enabled": False,
    "live_camera_enabled": False,
    "background_screen_capture_enabled": False,
    "secret_capture_enabled": False,
    "multimodal_model_api_called": False,
}
```

Implement helper functions:

```python
def build_artifact_semantics_readback(raw_sources: list[dict[str, Any]] | None) -> dict[str, Any]:
    ...
```

The function must:

- call `normalize_multimodal_source()` for every source
- skip sources whose normalized status is not `available`
- read semantic content only from these raw metadata fields:
  - `semantic_summary`
  - `operator_summary`
  - `caption`
  - `observed_text`
  - `ocr_text`
  - `transcript`
  - `semantic_tags`
- emit observation fields:
  - `source_ref_id`
  - `source_kind`
  - `modality`
  - `observation_kind`
  - `semantic_label`
  - `summary`
  - `observed_text`
  - `tags`
  - `confidence`
  - `source=approved_metadata`
  - `model_api_called=False`
  - `writeback_ready=False`
- return:
  - `schema=artifact_perception_semantics.v1`
  - `status=ready` when at least one observation exists
  - `status=blocked` when no observation exists and at least one source was blocked
  - `status=empty` when no observation exists and no source was blocked
  - `readiness_status` using the constants above
  - `semantic_observations`
  - `observation_count`
  - `blocked_source_count`
  - `blocked_reasons`
  - `authority_boundary`

- [x] **Step 4: Run semantic tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_artifact_perception_semantics.py -q
```

Expected: PASS.

- [x] **Step 5: Commit Task 1**

Run:

```powershell
git add amadeus_thread0/runtime/artifact_perception_semantics.py tests/test_artifact_perception_semantics.py
git commit -m "feat: add artifact perception semantics normalization"
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
def test_artifact_semantics_reaches_perception_appraisal_and_carryover():
    turn = {
        "final_text": "嗯，我听见了。",
        "current_event": {
            "kind": "multimodal_observation",
            "perception": {"channel": "image"},
            "digital_body_hints": {
                "multimodal_sources": [
                    {
                        "source_id": "img-runtime-sem-1",
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

    observation = readback["artifact_semantics"]["semantic_observations"][0]
    assert readback["readiness_status"] == "embodied_interaction_runtime_phase2_ready"
    assert observation["source_ref_id"] == "img-runtime-sem-1"
    assert readback["current_event"]["perception"]["semantic_observations"][0]["source_ref_id"] == "img-runtime-sem-1"
    assert readback["turn_appraisal"]["perception_semantics"]["semantic_observations"][0]["source_ref_id"] == "img-runtime-sem-1"
    assert readback["interaction_carryover"]["embodied_context"]["artifact_semantic_observations"][0]["source_ref_id"] == "img-runtime-sem-1"
```

Extend `tests/test_backend_api.py` with a backend payload test that builds a turn/event response from the same semantic source and asserts:

```python
payload["embodied_interaction"]["readiness_status"] == "embodied_interaction_runtime_phase2_ready"
payload["current_event"]["perception"]["channel"] == "image"
payload["current_event"]["perception"]["semantic_observations"][0]["source_ref_id"] == "img-backend-sem-1"
payload["turn_appraisal"]["scene"] == "artifact_review"
payload["turn_appraisal"]["perception_semantics"]["semantic_observations"][0]["source_ref_id"] == "img-backend-sem-1"
payload["interaction_carryover"]["embodied_context"]["artifact_semantic_observations"][0]["source_ref_id"] == "img-backend-sem-1"
payload["embodied_interaction"]["artifact_semantics"]["semantic_observations"][0]["model_api_called"] is False
```

- [x] **Step 2: Run runtime/backend tests to verify RED**

Run:

```powershell
python -m pytest tests/test_embodied_interaction_runtime.py -q
python -m pytest tests/test_backend_api.py -k "artifact_semantics or embodied_interaction" -q
```

Expected: FAIL because Phase 2 surfaces are not implemented yet.

- [x] **Step 3: Implement runtime attachment**

Modify `amadeus_thread0/runtime/embodied_interaction_runtime.py`:

- add constants:

```python
EMBODIED_INTERACTION_PHASE2_READINESS = "embodied_interaction_runtime_phase2_ready"
EMBODIED_INTERACTION_PHASE2_IN_PROGRESS = "embodied_interaction_runtime_phase2_in_progress"
```

- import:

```python
from .artifact_perception_semantics import build_artifact_semantics_readback
```

- call:

```python
artifact_semantics = build_artifact_semantics_readback(_candidate_sources(data))
```

- set top-level readiness to Phase 2 ready when `artifact_semantics["status"] == "ready"`.
- include `artifact_semantics`, `turn_appraisal`, and perception semantic patches in the readback.
- preserve existing Phase 1 behavior when no semantic observation exists.
- update `apply_embodied_interaction_readback_to_payload()` so `current_event.perception` is deep-merged instead of overwritten.

- [x] **Step 4: Run runtime/backend tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_artifact_perception_semantics.py tests/test_embodied_interaction_runtime.py -q
python -m pytest tests/test_backend_api.py -k "artifact_semantics or embodied_interaction or living_loop_realism" -q
```

Expected: PASS.

- [x] **Step 5: Commit Task 2**

Run:

```powershell
git add amadeus_thread0/runtime/embodied_interaction_runtime.py tests/test_embodied_interaction_runtime.py tests/test_backend_api.py
git commit -m "feat: attach artifact semantics to embodied interaction payloads"
```

Expected: commit succeeds.

---

### Task 3: Phase 2 Audit And Preserved Baseline

**Files:**
- Create: `evals/run_embodied_interaction_runtime_phase2_audit.py`
- Create: `tests/test_embodied_interaction_runtime_phase2_audit.py`
- Modify: `evals/run_preserved_baselines_audit.py`
- Modify: `tests/test_preserved_baselines_audit.py`

- [x] **Step 1: Write failing audit tests**

Create `tests/test_embodied_interaction_runtime_phase2_audit.py`:

```python
from __future__ import annotations

from evals.run_embodied_interaction_runtime_phase2_audit import build_report, render_markdown


def test_build_report_returns_phase2_ready():
    report = build_report(run_id="unit")

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "embodied_interaction_runtime_phase2_ready"
    assert report["summary"]["semantic_observation_count"] >= 5
    assert report["summary"]["model_api_called"] is False
    assert report["summary"]["writeback_ready_count"] == 0


def test_render_markdown_includes_phase2_scenarios():
    rendered = render_markdown(build_report(run_id="unit-md"))

    assert "# Embodied Interaction Runtime Phase 2 Audit" in rendered
    assert "`embodied_interaction_runtime_phase2_ready`" in rendered
    assert "| `image_artifact_metadata_enters_semantic_observation` | `passed` |" in rendered
    assert "| `blocked_live_capture_has_no_semantic_observation` | `passed` |" in rendered
    assert "| `semantic_observation_reaches_backend_payload` | `passed` |" in rendered
```

Modify `tests/test_preserved_baselines_audit.py`:

- add expected id `embodied_interaction_runtime_phase2`
- change `summary["summary"]["categories"]["embodied_interaction"]["passed"]` from `1` to `2`

- [x] **Step 2: Run audit tests to verify RED**

Run:

```powershell
python -m pytest tests/test_embodied_interaction_runtime_phase2_audit.py tests/test_preserved_baselines_audit.py -q
```

Expected: FAIL because the audit entrypoint and preserved row do not exist yet.

- [x] **Step 3: Implement Phase 2 audit**

Create `evals/run_embodied_interaction_runtime_phase2_audit.py` with deterministic scenarios:

- `image_artifact_metadata_enters_semantic_observation`
- `audio_transcript_enters_semantic_observation`
- `screen_snapshot_ocr_enters_semantic_observation`
- `browser_capture_summary_enters_semantic_observation`
- `blocked_live_capture_has_no_semantic_observation`
- `semantic_observation_reaches_backend_payload`
- `semantic_observation_does_not_write_memory_or_call_model_api`

The report must emit:

```python
"readiness_status": "embodied_interaction_runtime_phase2_ready"
```

when all scenarios pass.

- [x] **Step 4: Register preserved baseline**

Add to `BASELINE_SPECS` in `evals/run_preserved_baselines_audit.py`:

```python
{
    "id": "embodied_interaction_runtime_phase2",
    "prefix": "embodied-interaction-runtime-phase2-audit-",
    "expected_readiness": "embodied_interaction_runtime_phase2_ready",
    "category": "embodied_interaction",
}
```

- [x] **Step 5: Run audit tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_embodied_interaction_runtime_phase2_audit.py tests/test_preserved_baselines_audit.py -q
python evals/run_embodied_interaction_runtime_phase2_audit.py --run-tag phase2-dev
```

Expected: tests PASS and audit prints `readiness=embodied_interaction_runtime_phase2_ready`.

- [x] **Step 6: Commit Task 3**

Run:

```powershell
git add evals/run_embodied_interaction_runtime_phase2_audit.py tests/test_embodied_interaction_runtime_phase2_audit.py evals/run_preserved_baselines_audit.py tests/test_preserved_baselines_audit.py
git commit -m "test: add embodied interaction runtime phase 2 audit"
```

Expected: commit succeeds.

---

### Task 4: Documentation And Ledger Closure

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `program.md`

- [x] **Step 1: Update project contracts**

Update `AGENTS.md`:

- add `Embodied Interaction Runtime Phase 2`
- add `embodied_interaction_runtime_phase2_ready` to preserved baselines
- state explicitly that it:
  - consumes approved artifact metadata only
  - places semantic observations into perception/appraisal/carryover surfaces
  - does not call multimodal model APIs
  - does not open live microphone/camera/background screen capture
  - does not mutate memory, persona core, browser/tool/sandbox authority, skill registry, or frontend-owned semantics

Update `docs/engineering/PROJECT_STRUCTURE.md`:

- add `artifact_perception_semantics.py`
- update `embodied_interaction_runtime.py` ownership to include Phase 2 observation attachment
- add `run_embodied_interaction_runtime_phase2_audit.py`

Update `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`:

- record `embodied_interaction_runtime_phase2_ready`
- update backend status, current posture, and implementation order

Update `program.md`:

- update Current State to Phase 2
- add a dated run entry with files changed, validations, result, and next step

- [x] **Step 2: Run doc/placeholder scan**

Run:

```powershell
rg -n "T[B]D|T[O]DO|implement[ ]later|fill[ ]in[ ]details|Similar[ ]to[ ]Task" AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md docs/superpowers/plans/2026-05-06-embodied-interaction-runtime-phase2.md amadeus_thread0/runtime/artifact_perception_semantics.py amadeus_thread0/runtime/embodied_interaction_runtime.py tests/test_artifact_perception_semantics.py tests/test_embodied_interaction_runtime.py evals/run_embodied_interaction_runtime_phase2_audit.py tests/test_embodied_interaction_runtime_phase2_audit.py
```

Expected: no matches.

- [x] **Step 3: Commit Task 4**

Run:

```powershell
git add AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md docs/superpowers/plans/2026-05-06-embodied-interaction-runtime-phase2.md
git commit -m "docs: record embodied interaction runtime phase 2"
```

Expected: commit succeeds.

---

### Task 5: Final Verification, Merge, And Push

**Files:**
- All files touched by Tasks 1-4.

- [x] **Step 1: Run focused runtime/backend verification**

Run:

```powershell
python -m pytest tests/test_artifact_perception_semantics.py tests/test_embodied_interaction_runtime.py tests/test_embodied_interaction_runtime_audit.py tests/test_embodied_interaction_runtime_phase2_audit.py tests/test_multimodal_sources.py -q
python -m pytest tests/test_backend_api.py -k "artifact_semantics or embodied_interaction or living_loop_realism or turn_and_event_responses_attach_operator_readback" -q
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
python -m py_compile amadeus_thread0/agent.py amadeus_thread0/graph.py amadeus_thread0/runtime/artifact_perception_semantics.py amadeus_thread0/runtime/embodied_interaction_runtime.py amadeus_thread0/runtime/backend_api.py evals/run_embodied_interaction_runtime_audit.py evals/run_embodied_interaction_runtime_phase2_audit.py evals/run_preserved_baselines_audit.py
python -c "from amadeus_thread0.agent import agent; print(type(agent).__name__)"
```

Expected: compile passes and prints `CompiledStateGraph`.

- [x] **Step 4: Run phase audits**

Run:

```powershell
python evals/run_embodied_interaction_runtime_audit.py --run-tag phase2-regression
python evals/run_embodied_interaction_runtime_phase2_audit.py --run-tag phase2-final
python evals/run_multimodal_capture_audit.py --run-tag embodied-phase2-regression
python evals/run_living_loop_realism_phase2_audit.py --run-tag embodied-phase2-regression
```

Expected:

- Phase 1 audit reports `embodied_interaction_runtime_phase1_ready`
- Phase 2 audit reports `embodied_interaction_runtime_phase2_ready`
- multimodal audit reports `multimodal_capture_phase1_ready`
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
git add AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md docs/superpowers/plans/2026-05-06-embodied-interaction-runtime-phase2.md amadeus_thread0/runtime/artifact_perception_semantics.py amadeus_thread0/runtime/embodied_interaction_runtime.py amadeus_thread0/runtime/backend_api.py evals/run_embodied_interaction_runtime_phase2_audit.py evals/run_preserved_baselines_audit.py tests/test_artifact_perception_semantics.py tests/test_embodied_interaction_runtime.py tests/test_backend_api.py tests/test_embodied_interaction_runtime_phase2_audit.py tests/test_preserved_baselines_audit.py
git commit -m "feat: close embodied interaction runtime phase 2"
```

Expected: commit succeeds or there is nothing to commit.

- [ ] **Step 7: Merge to main**

Run from primary workspace:

```powershell
git -C E:\桌面\amadeus-thread0 status --short --branch
git -C E:\桌面\amadeus-thread0 merge --ff-only codex/embodied-interaction-runtime-phase2
```

Expected:

- primary workspace remains on `main`
- merge fast-forwards
- existing untracked `third_party/benchmarks/ESConv` remains untouched

- [ ] **Step 8: Post-merge verification on main**

Run from `E:\桌面\amadeus-thread0`:

```powershell
python -m pytest tests/test_artifact_perception_semantics.py tests/test_embodied_interaction_runtime.py tests/test_embodied_interaction_runtime_phase2_audit.py tests/test_backend_api.py -k "artifact_semantics or embodied_interaction or living_loop_realism" -q
python evals/run_embodied_interaction_runtime_phase2_audit.py --run-tag post-merge
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
```

Expected:

- tests PASS
- Phase 2 audit reports `embodied_interaction_runtime_phase2_ready`
- preserved baselines audit reports `preserved_baselines_ready`

- [ ] **Step 9: Push main**

Run:

```powershell
git -C E:\桌面\amadeus-thread0 push origin main
```

Expected: push succeeds.

---

## Self-Review

- Spec coverage:
  - Approved artifact semantic observations: Tasks 1-2.
  - Image/audio/screen/browser metadata paths: Tasks 1 and 3.
  - Blocked live capture remains blocked: Tasks 1 and 3.
  - Backend `assistant_turn` and `event_round` payload attachment: Task 2.
  - No model API call / no memory write / no new authority: Tasks 1, 3, and 4.
  - Audit and preserved baseline closure: Task 3 and Task 5.
  - Docs and run ledger: Task 4.
- Placeholder scan:
  - No task uses vague placeholders; concrete paths, commands, expected outputs, and field names are specified.
- Type consistency:
  - The plan consistently uses `artifact_semantics`, `semantic_observations`, `current_event.perception.semantic_observations`, `turn_appraisal.perception_semantics`, `artifact_semantic_observations`, and `embodied_interaction_runtime_phase2_ready`.
