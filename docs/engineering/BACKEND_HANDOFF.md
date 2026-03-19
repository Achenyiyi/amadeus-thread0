# Backend Handoff

## Goal

This document defines the backend contract future frontend shells should consume.
The frontend should depend on runtime envelopes, not on CLI formatting or internal graph state assembly.

## Stable Entry Points

- `amadeus_thread0.runtime.runtime_bundle`: runtime assembly and backend API factory
- `amadeus_thread0.runtime.backend_session.BackendSession`: reusable backend-facing session surface
- `amadeus_thread0.runtime.backend_api.BackendAPI`: transport-neutral frontend schema surface
- `amadeus_thread0.runtime.final_state`: shared final-state normalization for readback parity

## Envelope Contract

All frontend-facing responses come from `BackendApiEnvelope.to_dict()` and share:

```json
{
  "schema_version": "backend.v1",
  "generated_at": 1710000000,
  "kind": "assistant_turn",
  "thread_id": "thread-a",
  "payload": {},
  "meta": {}
}
```

Current `kind` values:

- `memory_snapshot`
- `worldline_view`
- `bond_view`
- `sources_view`
- `persona_view`
- `appraisal_view`
- `behavior_queue_view`
- `checkpoint_history`
- `current_checkpoint`
- `thread_inventory`
- `runtime_layout`
- `environment_summary`
- `event_round`
- `assistant_turn`

## Final-State Parity Rules

- `final_text` is the only text a shell should render or send to TTS.
- `behavior_action`, `behavior_plan`, `turn_summary`, and `reconsolidation_snapshot` must be read from backend envelopes, not re-derived in the frontend.
- `runtime.final_state.resolve_behavior_payloads()` is the single runtime rule for action/plan readback.
- Persisted `behavior_plan` is authoritative when it carries a real final-plan signal.
- Deriving a plan from `behavior_action` is allowed only when the final plan is absent or legacy-incomplete.
- `BackendSession.build_evolution_summary()`, `persona_view()`, `worldline_view()`, `BackendAPI.build_turn_response()`, and `BackendAPI.build_event_round_response()` all route through the same final-state normalization path.

## Payloads Frontends Should Expect

`assistant_turn.payload`:

- `final_text`
- `emotion_label`
- `turn_summary`
- `behavior_action`
- `behavior_plan`
- `reconsolidation_snapshot`
- `turn_appraisal`
- `claim_links`
- `sources`
- `pending_utterance_fragment`

`event_round.payload`:

- `final_text`
- `emotion_label`
- `behavior_action`
- `behavior_plan`
- `reconsolidation_snapshot`
- `current_event`
- `turn_appraisal`
- `turn_summary`

`persona_view.payload` should be treated as the debug / inspection surface for:

- persona and emotion state
- bond and allostasis state
- counterpart assessment
- semantic narrative profile
- world model state
- evolution state
- reconsolidation snapshot
- final behavior action / behavior plan / behavior queue

`worldline_view.payload` should be treated as the long-horizon continuity surface for:

- current turn summary
- worldline events
- commitments
- conflict repair
- unresolved tensions
- semantic self narratives
- revision traces

## TypeScript And Mocks

Ready-to-copy frontend contract assets live here:

- `docs/engineering/frontend_contract/backend_api.types.ts`
- `docs/engineering/frontend_contract/mocks/assistant_turn.json`
- `docs/engineering/frontend_contract/mocks/event_round.json`
- `docs/engineering/frontend_contract/mocks/persona_view.json`
- `docs/engineering/frontend_contract/mocks/worldline_view.json`

Recommended frontend workflow:

1. Import or copy `backend_api.types.ts` into the frontend workspace.
2. Start rendering from `assistant_turn` and `event_round`.
3. Use `persona_view` and `worldline_view` as debug / inspector panels.
4. Treat any extra keys in raw runtime dicts as additive, not breaking.

## Validation Baseline Before Frontend Work

Minimum checks that should stay green before frontend integration:

```powershell
python -m pytest tests/test_final_state.py
python -m pytest tests/test_backend_session.py
python -m pytest tests/test_backend_api.py
python -m pytest tests/test_memory_guard.py tests/test_session_orchestrator.py tests/test_cli_views.py
python -m pytest tests/test_daily_surface_gating.py tests/test_generation_profile.py tests/test_dialogue_mode_counterpart.py tests/test_world_model_residue.py tests/test_subjective_review_pack.py
python -m py_compile amadeus_thread0/agent.py amadeus_thread0/graph.py amadeus_thread0/runtime/final_state.py
```
