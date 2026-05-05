# TTS Presence Timing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `TTS_presence_timing` as a bounded multimodal body slice so spoken-output timing, silence, interruption, and delivery truth flow through perception, digital-body state, turn summaries, and writeback without creating a new capture surface or splitting the memory model.

**Architecture:** Keep TTS as a timing-only body telemetry slice around the existing frozen `final_text`. Normalize one new perception/event kind into the same backend envelope path used by other runtime observations, extend digital-body state with one dedicated TTS presence block, and surface that block through final-state readback and CLI summaries. Preserve the existing `CLI + TTS + evals` boundary; do not introduce microphone capture, generated-audio persistence, or a separate voice memory model.

**Tech Stack:** Python 3, pytest, existing LangGraph backend envelopes, existing `digital_body_runtime` / `final_state` / `backend_api` / `cli_views` modules, `evals/` smoke and audit runners.

---

## File Ownership Map

- Event/perception normalization:
  - `amadeus_thread0/graph_parts/perception.py`
  - `amadeus_thread0/runtime/event_identity.py`
  - `tests/test_perception_event_contract.py`

- Digital-body state and consequence normalization:
  - `amadeus_thread0/graph_parts/digital_body_runtime.py`
  - `amadeus_thread0/evolution_engine/reconsolidation.py`
  - `amadeus_thread0/runtime/final_state.py`
  - `tests/test_world_model_residue.py`

- Backend and CLI readback surfaces:
  - `amadeus_thread0/runtime/backend_api.py`
  - `amadeus_thread0/runtime/backend_session.py`
  - `amadeus_thread0/utils/turn_summary_export.py`
  - `amadeus_thread0/utils/cli_views.py`
  - `tests/test_backend_api.py`
  - `tests/test_backend_session.py`
  - `tests/test_cli_views.py`

- Validation and audit scaffolding:
  - `evals/run_tts_presence_timing_smokes.py`
  - `evals/run_tts_presence_timing_audit.py`
  - `tests/test_tts_presence_timing_smokes.py`
  - `tests/test_tts_presence_timing_audit.py`
  - `program.md`

---

## Task 1: Add perception normalization for TTS presence timing

**Files:**
- Modify: `amadeus_thread0/graph_parts/perception.py`
- Modify: `amadeus_thread0/runtime/event_identity.py`
- Test: `tests/test_perception_event_contract.py`

- [ ] **Step 1: Write the failing test**

Add a new test that builds a `tts_presence_timing_observation` event and asserts all of the following:

```python
def test_tts_presence_timing_observation_keeps_runtime_voice_timing_hints():
    event = attach_perception_context(
        {
            "kind": "tts_presence_timing_observation",
            "source": "tts",
            "text": "TTS delivered the frozen final text.",
            "final_text_ref": "turn.final_text",
            "digital_body_hints": {
                "tts_presence_state": {
                    "last_status": "delivered",
                    "voice_profile_id": "default",
                }
            },
        },
        thread_id="thread-body",
        turn_now_ts=1710000210,
    )

    perception = event["perception"]
    assert perception["modality"] == "TTS_presence_timing"
    assert perception["channel"] == "voice"
    assert perception["source_role"] == "runtime"
    assert perception["trust_tier"] == "high_runtime_telemetry"
    assert perception["delivery_mode"] == "spoken"
    assert event["digital_body_hints"]["tts_presence_state"]["last_status"] == "delivered"


def test_readback_current_event_mirrors_tts_presence_timing_hints_into_perception():
    readback = resolve_readback_current_event(
        {
            "current_event": {
                "kind": "tts_presence_timing_observation",
                "source": "tts",
                "created_at": 1710000211,
                "digital_body_hints": {
                    "tts_presence_state": {
                        "last_status": "delivered",
                        "voice_profile_id": "default",
                    }
                },
                "perception": {
                    "thread_id": "thread-body",
                    "turn_id": "thread-body:1710000211",
                    "modality": "TTS_presence_timing",
                    "source_role": "runtime",
                },
            }
        },
        thread_id="thread-body",
        session_context={"thread_id": "thread-body", "turn_id": "thread-body:1710000211"},
    )

    assert readback["perception"]["modality"] == "TTS_presence_timing"
    assert readback["perception"]["source_role"] == "runtime"
    assert readback["perception"]["digital_body_hints"]["tts_presence_state"]["last_status"] == "delivered"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m pytest tests/test_perception_event_contract.py -q
```

Expected:

- The new test fails because `tts_presence_timing_observation` is not yet normalized.

- [ ] **Step 3: Write minimal implementation**

Update the source normalization helpers so the new event is recognized as:

```python
if normalized_kind == "tts_presence_timing_observation":
    return "voice"
```

and:

```python
if normalized_kind == "tts_presence_timing_observation":
    return "TTS_presence_timing"
```

with source role:

```python
if normalized_kind == "tts_presence_timing_observation" or normalized_source in {"tts", "speech", "voice"}:
    return "runtime"
```

and delivery mode:

```python
if normalized_kind == "tts_presence_timing_observation":
    return "spoken"
```

Keep the implementation additive and leave other event kinds unchanged.

- [ ] **Step 4: Run the test to verify it passes**

Run:

```powershell
python -m pytest tests/test_perception_event_contract.py -q
```

Expected:

- The new TTS presence timing tests pass.
- Existing perception contract tests still pass.

- [ ] **Step 5: Commit**

```powershell
git add amadeus_thread0/graph_parts/perception.py amadeus_thread0/runtime/event_identity.py tests/test_perception_event_contract.py
git commit -m "feat: normalize tts presence timing perception"
```

---

## Task 2: Extend digital-body state and consequence normalization

**Files:**
- Modify: `amadeus_thread0/graph_parts/digital_body_runtime.py`
- Modify: `amadeus_thread0/evolution_engine/reconsolidation.py`
- Modify: `amadeus_thread0/runtime/final_state.py`
- Test: `tests/test_world_model_residue.py`

- [ ] **Step 1: Write the failing test**

Add a test that starts from a `digital_body_state` with a TTS presence block and a matching `digital_body_consequence`, then asserts the normalized body and consequence preserve one shared timing truth:

```python
def test_tts_presence_timing_stays_inside_digital_body_and_consequence():
    normalized_body = normalize_digital_body_state(
        {
            "access_state": {
                "tts_presence_state": {
                    "availability": "available",
                    "enabled": True,
                    "backend": "dashscope_realtime",
                    "voice_profile_id": "default",
                    "queue_state": "idle",
                    "last_status": "delivered",
                    "last_run_id": "evt_tts_20260505_0001",
                }
            },
            "resource_state": {
                "tts_presence_timing": {
                    "last_event_id": "evt_tts_20260505_0001",
                    "last_delivery_mode": "spoken",
                    "last_actual_start_delay_ms": 180,
                    "last_duration_ms": 3120,
                }
            },
        }
    )

    normalized_consequence = normalize_embodied_context(
        {
            "kind": "tts_presence_delivered",
            "summary": "TTS delivered the frozen final text.",
            "tts_presence_timing": {
                "delivery_mode": "spoken",
                "actual_start_delay_ms": 180,
                "duration_ms": 3120,
            },
        }
    )

    assert normalized_body["access_state"]["tts_presence_state"]["last_status"] == "delivered"
    assert normalized_body["resource_state"]["tts_presence_timing"]["last_delivery_mode"] == "spoken"
    assert normalized_consequence["kind"] == "tts_presence_delivered"
    assert normalized_consequence["tts_presence_timing"]["delivery_mode"] == "spoken"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m pytest tests/test_world_model_residue.py -q
```

Expected:

- The new TTS timing body/consequence test fails because the new fields are not normalized yet.

- [ ] **Step 3: Write minimal implementation**

Add a dedicated `tts_presence_state` block under `access_state` and a dedicated `tts_presence_timing` block under `resource_state` in `normalize_digital_body_state(...)`.

Add `tts_presence_timing` to `normalize_embodied_context(...)` / `normalize_digital_body_consequence(...)` so the consequence can preserve:

```python
{
    "kind": "tts_presence_delivered",
    "summary": "...",
    "tts_presence_timing": {
        "delivery_mode": "spoken",
        "actual_start_delay_ms": 180,
        "duration_ms": 3120,
        "silence_before_ms": 0,
        "silence_after_ms": 420,
        "pause_profile": "direct",
        "interrupted": False,
    },
}
```

Extend `digital_body_consequence_has_signal(...)` only as needed so the new TTS consequence kinds are treated as real embodied facts.

- [ ] **Step 4: Run the test to verify it passes**

Run:

```powershell
python -m pytest tests/test_world_model_residue.py -q
```

Expected:

- The TTS timing body/consequence test passes.
- Existing world-model residue tests still pass.

- [ ] **Step 5: Commit**

```powershell
git add amadeus_thread0/graph_parts/digital_body_runtime.py amadeus_thread0/evolution_engine/reconsolidation.py amadeus_thread0/runtime/final_state.py tests/test_world_model_residue.py
git commit -m "feat: add tts timing body writeback"
```

---

## Task 3: Surface TTS timing through backend API and CLI summaries

**Files:**
- Modify: `amadeus_thread0/runtime/backend_api.py`
- Modify: `amadeus_thread0/runtime/backend_session.py`
- Modify: `amadeus_thread0/utils/turn_summary_export.py`
- Modify: `amadeus_thread0/utils/cli_views.py`
- Test: `tests/test_backend_api.py`
- Test: `tests/test_backend_session.py`
- Test: `tests/test_cli_views.py`

- [ ] **Step 1: Write the failing test**

Add a backend API test that builds a turn/event response containing the TTS timing fields and asserts:

```python
def test_turn_and_event_responses_preserve_tts_presence_timing_fields():
    self.assertEqual(payload["current_event"]["modality"], "TTS_presence_timing")
    self.assertEqual(payload["digital_body"]["access_state"]["tts_presence_state"]["last_status"], "delivered")
    self.assertEqual(payload["digital_body"]["resource_state"]["tts_presence_timing"]["last_delivery_mode"], "spoken")
    self.assertEqual(payload["digital_body_consequence"]["kind"], "tts_presence_delivered")
    self.assertEqual(payload["turn_summary"]["current_turn"]["tts_presence_status"], "delivered")
    self.assertEqual(payload["turn_summary"]["current_turn"]["tts_presence_delivery_mode"], "spoken")
```

Add a CLI summary test that expects a compact TTS line such as:

```python
assert "TTS: delivered via dashscope_realtime" in line
assert "start_delay=180ms" in line
assert "duration=3120ms" in line
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py -q
```

Expected:

- The new TTS timing envelope and CLI assertions fail because the fields are not yet surfaced.

- [ ] **Step 3: Write minimal implementation**

Thread the new `tts_presence_state` and `tts_presence_timing` fields through:

- `BackendAPI.build_event_round_response(...)`
- `BackendAPI.build_turn_response(...)`
- `BackendSession` summary assembly if needed
- `summarize_digital_body(...)`
- `summarize_digital_body_consequence(...)`
- `build_evolution_summary_line(...)`

Make the summary compact and one-line only, with no duplicate utterance text:

```text
TTS: delivered via dashscope_realtime, start_delay=180ms, duration=3120ms
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```powershell
python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py -q
```

Expected:

- The new backend/CLI tests pass.
- Existing backend/session/CLI tests still pass.

- [ ] **Step 5: Commit**

```powershell
git add amadeus_thread0/runtime/backend_api.py amadeus_thread0/runtime/backend_session.py amadeus_thread0/utils/turn_summary_export.py amadeus_thread0/utils/cli_views.py tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py
git commit -m "feat: surface tts presence timing in readback"
```

---

## Task 4: Add TTS presence timing smoke and audit coverage

**Files:**
- Create: `evals/run_tts_presence_timing_smokes.py`
- Create: `evals/run_tts_presence_timing_audit.py`
- Create: `tests/test_tts_presence_timing_smokes.py`
- Create: `tests/test_tts_presence_timing_audit.py`
- Modify: `program.md`

- [ ] **Step 1: Write the failing test**

Create a smoke test that exercises the three minimal cases:

```python
def test_spoken_final_text_no_drift():
    ...


def test_text_only_when_tts_disabled():
    ...


def test_deliberate_silence_as_presence_timing():
    ...
```

Add an audit test that asserts the audit runner reports:

```text
tts_presence_timing_ready
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_tts_presence_timing_smokes.py tests/test_tts_presence_timing_audit.py -q
```

Expected:

- The new smoke and audit tests fail because the runners do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create small eval runners that:

- load a compact JSON/MD report
- check final-text/TTS drift
- verify silent/text-only/delivered delivery branches
- report `tts_presence_timing_ready`

Keep them offline and deterministic.

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```powershell
python -m pytest tests/test_tts_presence_timing_smokes.py tests/test_tts_presence_timing_audit.py -q
python evals/run_tts_presence_timing_smokes.py
python evals/run_tts_presence_timing_audit.py
```

Expected:

- The smoke/audit tests and scripts pass.
- The generated readiness label is `tts_presence_timing_ready`.

- [ ] **Step 5: Update the run ledger and commit**

Append a concise run entry to `program.md` describing the new TTS slice, validations run, and next step.

Then commit:

```powershell
git add evals/run_tts_presence_timing_smokes.py evals/run_tts_presence_timing_audit.py tests/test_tts_presence_timing_smokes.py tests/test_tts_presence_timing_audit.py program.md
git commit -m "test: add tts presence timing audit"
```

---

## Validation Checklist

After the implementation finishes, run at minimum:

```powershell
python -m pytest tests/test_perception_event_contract.py tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py tests/test_world_model_residue.py -q
python -m pytest tests/test_tts_presence_timing_smokes.py tests/test_tts_presence_timing_audit.py -q
python evals/run_tts_presence_timing_smokes.py
python evals/run_tts_presence_timing_audit.py
python evals/run_digital_embodiment_audit.py
```

If the new slice changes any final-state or summary contract outside the TTS block, also run the existing preserved baseline audits listed in `AGENTS.md`.

