# Backend Handoff

## Goal

This document is the short index for frontend handoff.

The authoritative frontend-facing backend contract now lives in:

- [`FRONTEND_INTERFACE_DELIVERABLE.md`](./FRONTEND_INTERFACE_DELIVERABLE.md)

That document is the one future frontend work should consume.

## Freeze-Lift Summary

Frontend integration should remain limited to contract consumption and adapter work unless the repository-level freeze gate in [`AGENTS.md`](../../AGENTS.md) stays satisfied.

For handoff purposes, the current backend should already be treated as:

- envelope-based
- final-state normalized
- transport-neutral
- stable enough for a thin frontend adapter

## Stable Backend Surfaces

- runtime assembly: `amadeus_thread0.runtime.runtime_bundle`
- transport-neutral API: `amadeus_thread0.runtime.backend_api`
- turn/event/readback execution: `amadeus_thread0.runtime.backend_session`
- final-state normalization: `amadeus_thread0.runtime.final_state`

## Contract Assets

- detailed interface doc: [`FRONTEND_INTERFACE_DELIVERABLE.md`](./FRONTEND_INTERFACE_DELIVERABLE.md)
- TypeScript types: [`frontend_contract/backend_api.types.ts`](./frontend_contract/backend_api.types.ts)
- mock payloads:
  - [`assistant_turn.json`](./frontend_contract/mocks/assistant_turn.json)
  - [`event_round.json`](./frontend_contract/mocks/event_round.json)
  - [`persona_view.json`](./frontend_contract/mocks/persona_view.json)
  - [`worldline_view.json`](./frontend_contract/mocks/worldline_view.json)
  - [`bond_view.json`](./frontend_contract/mocks/bond_view.json)

## Validation Baseline

Minimum contract checks:

```powershell
python -m pytest tests/test_backend_api.py tests/test_backend_session.py
python -m pytest tests/test_final_state.py
```
