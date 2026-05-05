# Multimodal Body Expansion Spec

Status: proposed next slice, spec only

Date: 2026-05-05

Chosen modality: `TTS_presence_timing`

## Purpose

The next multimodal/body slice should make spoken presence timing a first-class
digital-body signal without adding microphone, camera, screen, browser-capture,
or frontend authority.

This slice treats TTS timing as embodied output telemetry around the already
frozen final utterance. It does not create a second response channel, does not
change the persona core, and does not infer counterpart emotion from silence or
delivery timing alone.

## Why This Modality

`TTS_presence_timing` is the lowest-risk next step because the current product
boundary is already backend-first with `CLI + TTS + evals`. It deepens the
existing body contract rather than opening a new capture surface.

The selected modality supports:

- one final utterance shared by text and TTS
- explicit timing, pause, silence, and delivery-result semantics
- better continuity for presence and own-rhythm behavior
- evaluation of text/TTS drift and skipped or failed voice delivery
- no camera, microphone, screen, or arbitrary live-environment capture

Deferred modalities remain deferred:

- `audio_input`
- `image_observation`
- `screen_observation`
- `live_browser_plus_capture`

## Non-Goals

- Do not implement TTS runtime changes in this spec task.
- Do not store generated audio by default.
- Do not record user audio or environmental audio.
- Do not add wake-word, passive listening, camera, screen, or desktop capture.
- Do not resume frontend UI implementation.
- Do not create a separate voice persona, voice memory, or TTS-specific brain.
- Do not treat delivery timing as proof of counterpart mood or relationship
  state.

## Input Event Contract

Although this modality describes an output channel, the graph should receive it
as a post-delivery perception/runtime event. The event is evidence about the
digital body's voice delivery, not new user content.

Event kind:

```text
tts_presence_timing_observation
```

Required normalized fields:

```json
{
  "kind": "tts_presence_timing_observation",
  "event_id": "evt_tts_20260505_0001",
  "turn_id": "turn_20260505_0001",
  "channel": "voice",
  "modality": "TTS_presence_timing",
  "source_role": "runtime",
  "trust_tier": "high_runtime_telemetry",
  "occurred_at": "2026-05-05T13:50:00+08:00",
  "final_text_ref": "turn.final_text",
  "final_text_sha256": "sha256-of-final-text",
  "delivery_mode": "spoken",
  "presence_family": "direct_answer",
  "interaction_mode": "conversation",
  "timing_window_min": 0,
  "silence_allowed": false,
  "allow_interrupt": true,
  "tts_backend": "dashscope_realtime",
  "voice_profile_id": "default",
  "timing": {
    "planned_delay_ms": 0,
    "actual_start_delay_ms": 180,
    "duration_ms": 3120,
    "silence_before_ms": 0,
    "silence_after_ms": 420,
    "pause_profile": "direct",
    "interrupted": false
  },
  "result": {
    "status": "delivered",
    "error_kind": null,
    "error_summary": ""
  },
  "privacy": {
    "captures_user_audio": false,
    "captures_environment_audio": false,
    "stores_generated_audio": false,
    "stores_timing_only": true
  },
  "digital_body_hints": {
    "tts_presence_state": {
      "last_status": "delivered",
      "last_run_id": "evt_tts_20260505_0001"
    }
  }
}
```

Allowed `delivery_mode` values:

- `spoken`
- `text_only`
- `silent_presence`
- `queued`
- `skipped`
- `failed`
- `interrupted`

Allowed `result.status` values:

- `delivered`
- `text_only`
- `silence_completed`
- `queued`
- `skipped`
- `failed`
- `interrupted`

The event must reuse the frozen `final_text`. If TTS receives text that differs
from `final_text`, validation must fail as text/TTS drift.

## Trust Tier

The telemetry trust tier is `high_runtime_telemetry` only for runtime-owned
facts:

- whether TTS was enabled
- which backend was selected
- whether the runtime attempted delivery
- timing and status reported by the local TTS wrapper
- failure, interruption, or skipped-delivery status

The trust tier is not high for psychological or relational interpretation.
Timing may support an embodied continuity trace such as "the previous turn was
spoken after a short pause", but it must not become a fact such as "the
counterpart felt reassured" unless the counterpart later expresses that
directly.

## Access And Privacy Boundary

This slice is timing-only by default.

Allowed without new approval when TTS is already enabled for the active session:

- generate or play the frozen final utterance through the configured TTS backend
- record timing telemetry, status, backend id, and voice profile id
- write delivery-result metadata into the normal turn envelope

Blocked unless a later explicit approval policy adds it:

- microphone capture
- ambient audio capture
- screen capture
- camera/image capture
- storing generated waveform files as durable artifacts
- uploading generated audio outside the configured TTS provider flow
- replaying old voice output outside the active session
- changing voice profile, TTS backend, or provider credentials

External TTS providers remain governed by the existing runtime/model access
state. This spec does not introduce a new credential path, package-install
surface, browser action, or sandbox command family.

## Digital Body State Fields

The single source of truth remains `digital_body`. No separate TTS body model is
introduced.

Recommended access state:

```json
{
  "digital_body": {
    "access_state": {
      "tts_presence_state": {
        "availability": "available",
        "enabled": true,
        "backend": "dashscope_realtime",
        "voice_profile_id": "default",
        "voice_profile_state": "configured",
        "queue_state": "idle",
        "last_status": "delivered",
        "last_error_kind": null,
        "last_run_id": "evt_tts_20260505_0001",
        "captures_user_audio": false,
        "stores_generated_audio": false,
        "arbitrary_audio_capture": false
      }
    }
  }
}
```

Recommended resource state:

```json
{
  "digital_body": {
    "resource_state": {
      "tts_presence_timing": {
        "last_event_id": "evt_tts_20260505_0001",
        "last_delivery_mode": "spoken",
        "last_presence_family": "direct_answer",
        "last_interaction_mode": "conversation",
        "last_timing_window_min": 0,
        "last_actual_start_delay_ms": 180,
        "last_duration_ms": 3120,
        "last_silence_before_ms": 0,
        "last_silence_after_ms": 420,
        "last_pause_profile": "direct",
        "last_allow_interrupt": true
      }
    }
  }
}
```

Recommended consequence kinds:

- `tts_presence_delivered`
- `tts_presence_text_only`
- `tts_presence_silence_completed`
- `tts_presence_queued`
- `tts_presence_skipped`
- `tts_presence_failed`
- `tts_presence_interrupted`

`digital_body_consequence` must describe the final delivery truth for the same
turn. It must not be recomputed from frontend state or later CLI rendering.

## Writeback Policy

Completed or attempted TTS timing may write back as embodied/procedural
continuity only when the status is truthful.

May write back:

- the final utterance was spoken, skipped, queued, interrupted, failed, or held
  as deliberate silence
- the delivery timing profile used for presence or own-rhythm behavior
- provider/runtime failure as an environment condition
- text-only fallback when voice delivery was unavailable

Must not write back:

- generated audio bytes by default
- counterpart emotional reaction inferred from voice timing
- identity-core changes
- a second "voice persona" memory
- failed/skipped delivery as completed spoken presence
- pending queue state as delivered fact

Relationship and self-narrative updates may reference TTS timing only as
supporting embodied context. The canonical final semantics still come from the
frozen `final_text`, `behavior_action`, `behavior_plan`,
`digital_body_consequence`, and reconsolidation snapshot.

## Approval Policy

Auto-allowed inside an already-enabled active session:

- speaking the current frozen `final_text`
- recording timing-only telemetry
- text-only fallback when TTS is disabled or unavailable
- deliberate silence when selected by the existing behavior plan

Requires explicit operator approval or a preconfigured session setting:

- enabling TTS for a session where it is off
- changing TTS backend, voice profile, or provider credentials
- storing generated audio as a durable artifact
- replaying old TTS output
- playing proactive voice output after the user has disengaged from the active
  session
- sending TTS output to a new external destination

Always blocked in this slice:

- microphone capture
- background listening
- ambient sound classification
- camera/screen capture
- browser capture expansion
- package installation or arbitrary host command execution

## CLI And Backend Envelope Fields

Backend turn/event payloads should expose the modality through the same body and
summary surfaces used by the preserved baselines.

Recommended payload fields:

- `payload.current_event.modality = "TTS_presence_timing"`
- `payload.current_event.channel = "voice"`
- `payload.current_event.source_role = "runtime"`
- `payload.current_event.trust_tier = "high_runtime_telemetry"`
- `payload.digital_body.access_state.tts_presence_state`
- `payload.digital_body.resource_state.tts_presence_timing`
- `payload.digital_body_consequence.kind`
- `payload.digital_body_consequence.tts_presence_timing`
- `payload.turn_summary.current_turn.tts_presence_status`
- `payload.turn_summary.current_turn.tts_presence_delivery_mode`
- `payload.turn_summary.current_turn.tts_presence_pause_profile`
- `payload.turn_summary.current_turn.tts_presence_duration_ms`
- `payload.turn_summary.event_residue.digital_body_consequence`
- `payload.interaction_carryover.embodied_context.tts_presence_timing`
- `payload.reconsolidation_snapshot.digital_body_consequence`

CLI summaries may display compact delivery truth, for example:

```text
TTS: delivered via dashscope_realtime, start_delay=180ms, duration=3120ms
```

CLI summaries must not display a second utterance. They should reference status
and timing only.

## Evaluation Pack

Future implementation should add or extend tests for these cases:

- `tts_event_normalization_preserves_final_text_ref`
- `tts_event_rejects_text_drift_from_final_text`
- `tts_delivery_status_surfaces_in_backend_payloads`
- `tts_presence_state_stays_inside_digital_body`
- `tts_failed_delivery_writes_environment_consequence_not_completed_speech`
- `tts_silence_completed_preserves_presence_family_and_silence_allowed`
- `tts_timing_does_not_infer_counterpart_emotion`
- `tts_text_only_fallback_keeps_text_tts_semantics_singular`

Suggested smoke scenarios:

- `spoken_final_text_no_drift`
- `text_only_when_tts_disabled`
- `deliberate_silence_as_presence_timing`
- `tts_backend_failure_as_environment_condition`
- `proactive_voice_requires_active_session_or_approval`

Suggested audit:

```text
evals/run_tts_presence_timing_smokes.py
evals/run_tts_presence_timing_audit.py
```

Readiness label:

```text
tts_presence_timing_ready
```

## Validation Checklist

For the future implementation, run at minimum:

```powershell
python -m pytest tests/test_perception_event_contract.py tests/test_backend_api.py tests/test_world_model_residue.py -q
python -m pytest tests/test_behavior_runtime_alignment.py tests/test_cli_views.py -k "tts or presence or timing or final_text" -q
python evals/run_digital_embodiment_audit.py
```

If backend envelope or CLI rendering changes, also run:

```powershell
python -m pytest tests/test_backend_session.py tests/test_backend_api.py tests/test_cli_views.py -q
```

If graph behavior, reconsolidation, or presence-family selection changes, also
run:

```powershell
python -m pytest tests/test_daily_surface_gating.py tests/test_generation_profile.py tests/test_dialogue_mode_counterpart.py tests/test_world_model_residue.py tests/test_subjective_review_pack.py tests/test_companion_autonomy_runtime.py tests/test_autonomy_writeback.py -q
python evals/run_backend_freeze_gate_audit.py
```

Implementation is not closed until:

- text and TTS share one frozen `final_text`
- TTS timing fields flow through `current_event`, `digital_body`,
  `digital_body_consequence`, turn summary, and reconsolidation without drift
- failed, skipped, queued, and interrupted states do not become completed facts
- no new capture surface is opened
- no persona-core or relationship-core state is rewritten from timing alone
- preserved embodiment, autonomy, sandbox, browser, and skills audits still pass
