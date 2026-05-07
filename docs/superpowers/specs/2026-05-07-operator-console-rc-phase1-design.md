# Operator Console RC Phase 1 Design

## Goal

Convert the current `technical_preview_rc_phase1_ready` backend evidence into one operator-facing, read-only release-candidate console packet that can be consumed through the existing backend route/front-end contract without opening any new runtime authority.

## Current Context

The project is currently on the `Technical Preview RC Phase 1` baseline. `runtime_status_dashboard.NEXT_SPECS` is empty, and the existing RC gate composes preserved baselines, runtime dashboard, runtime productization phase 3, HTTP transport, approved artifact multimodal runtime, Chinese semantic naturalness, and dynamic skill candidate runtime evidence into `technical_preview_rc.v1`.

The next step should not be another residual cleanup pass. The useful missing layer is operator clarity: a compact packet that answers whether the technical preview is demo-ready, what evidence backs it, which lanes are ready/read-only, and which blocked surfaces remain intentionally closed.

## Scope

Implement `Operator Console RC Phase 1` as a readback/product surface only.

In scope:

- new `operator_console_rc.v1` backend readback module;
- compact console summary line for CLI/operator surfaces;
- deterministic audit runner that emits JSON and Markdown evidence;
- `BackendAPI` envelope and `BackendTransportAdapter` GET route;
- frontend contract type and route client support;
- static frontend checks that the shell can render the new route as a read-only record;
- project status and delivery documentation updates.

Out of scope:

- live microphone, camera, or background screen capture;
- multimodal model API calls;
- automatic dynamic skill registry writes;
- external executor harness enablement beyond preserved sandbox contracts;
- frontend-owned memory, body, autonomy, persona, graph, skill, browser, sandbox, or causal-loop semantics;
- persona-core mutation;
- memory-write policy changes;
- HTTP server ownership, streaming, SSE, or WebSocket work.

## Architecture

Add `amadeus_thread0.runtime.operator_console_rc` as a thin aggregator over existing readbacks. It accepts `technical_preview_rc`, `runtime_status_dashboard`, `operator_readback`, and optional recent route evidence, then emits one `operator_console_rc.v1` packet.

The packet is intentionally derivative. It does not recompute living-loop, embodied interaction, Chinese semantic, multimodal, skill, or sandbox truth. It only summarizes already-owned backend evidence and fails closed when RC evidence regresses, `NEXT_SPECS` is non-empty, or authority boundaries widen.

Expose the packet through `BackendAPI.operator_console_rc()` and `GET /api/operator-console-rc`. The frontend route client may request and render the envelope as a read-only record. The frontend must not interpret the packet as permission to mutate backend state or derive backend semantics.

## Data Shape

`operator_console_rc.v1` includes:

- `schema`: fixed to `operator_console_rc.v1`;
- `overall_status`: `passed` or `failed`;
- `readiness_status`: `operator_console_rc_phase1_ready` or `operator_console_rc_phase1_blocked`;
- `console_mode`: fixed to `readback_only`;
- `release_posture`: `technical_preview_rc` when ready, otherwise `attention_required`;
- `summary`: evidence counts, ready gate counts, next spec count, blocked lane count, route count, and demo readiness;
- `readback_refs`: compact pointers to RC, runtime dashboard, and operator readback schemas/statuses;
- `operator_panels`: stable panel rows for `rc_evidence`, `runtime_status`, `operator_readback`, `route_inventory`, and `authority_boundary`;
- `route_inventory`: read-only route list and mutation-route absence inherited from backend evidence;
- `authority_boundary`: closed authority booleans inherited from RC/operator evidence;
- `next_actions`: deterministic operator hints such as `run_rc_audit`, `open_operator_console`, or `inspect_blocked_evidence`;
- `failure_reasons`: deterministic reasons when blocked.

## Testing

Use TDD.

Backend unit tests prove:

- ready evidence produces `operator_console_rc_phase1_ready`;
- next specs or widened blocked authority fail closed;
- compact line is short and explicit.

Audit tests prove:

- ready inputs produce a passed audit report;
- missing/regressed RC evidence blocks the console;
- Markdown includes readiness, panel, and authority information.

Transport/API tests prove:

- `BackendAPI.operator_console_rc()` returns a `backend.v1` envelope;
- `GET /api/operator-console-rc` delegates to BackendAPI without schema rebuild;
- HTTP wrapper can serve the route through the existing adapter.

Frontend static tests prove:

- `operator_console_rc` exists in frontend and docs contract types;
- route client requests `/api/operator-console-rc`;
- UI renders `Operator console RC`;
- no frontend semantic ownership modules are added.

## Documentation

Update `AGENTS.md`, `program.md`, `docs/engineering/PROJECT_STRUCTURE.md`, `docs/engineering/BACKEND_HANDOFF.md`, `docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md`, `docs/FINAL_DELIVERY_MANIFEST.md`, `docs/TECHNICAL_PREVIEW_CHECKLIST.md`, and `docs/ADVISOR_REPRO_RUNBOOK.md`.

The documentation must describe this phase as a read-only operator console gate layered on top of Technical Preview RC evidence, not a new authority lane.

## Self-Review

- No placeholders remain.
- Scope is one subsystem: read-only operator console RC aggregation and consumption.
- The design preserves `backend.v1` ownership and blocked authority boundaries.
- The design does not claim runtime availability for live capture, multimodal model calls, dynamic registry auto-writes, or external executor harnesses.
