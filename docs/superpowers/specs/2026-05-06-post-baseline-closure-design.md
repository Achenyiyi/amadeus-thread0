# Post-Baseline Closure Design

## Goal

Close the remaining post-baseline items without widening Amadeus-K beyond the preserved backend contract.

The closure pack covers:

- callable transport adapter for future HTTP/Web handoff
- `TTS_presence_timing` readiness closure
- multimodal input fail-closed boundary
- executor adapter boundary
- dynamic skill-generation fail-closed boundary
- Chinese lexical de-scaffolding tracking
- bounded procedural growth tracking
- natural long-horizon calibration tracking

## Product Boundary

The product remains backend-first: `CLI + TTS + evals`.

This design does not add a desktop UI, browser UI, FastAPI dependency, microphone capture, camera capture, screen capture, host-side code generation, dynamic runtime skill authoring, or external executor harness runtime.

## Architecture

The closure pack adds three narrow read/dispatch layers:

1. `runtime.transport_adapter`
   - Python-callable route adapter over the existing `BackendAPI`.
   - No web-server dependency.
   - Returns `backend.v1` envelope dictionaries as-is.
   - Future HTTP/SSE/WebSocket servers may wrap this layer without rebuilding backend state semantics.

2. `runtime.executor_adapter`
   - Runtime-owned executor boundary around the existing sandbox runner.
   - The only enabled adapter is `sandbox_runner`.
   - Deep Agents, Codex, Claude, and OpenClaw harness candidates fail closed.
   - The adapter never owns persona memory, session truth, browser state, skills registry truth, or writeback semantics.

3. `runtime.post_baseline_closure`
   - Static policy/readiness helpers for deferred surfaces and tracked quality lanes.
   - Multimodal input surfaces stay `deferred_fail_closed`.
   - Dynamic skill generation stays `deferred_fail_closed`.
   - Chinese de-scaffolding, bounded procedural growth, and natural long-horizon calibration become tracked non-runtime-expansion lanes.

## Status Labels

- `implemented_ready`: implemented and testable in runtime.
- `preserved_ready`: already closed and preserved by prior audits.
- `deferred_fail_closed`: intentionally unavailable; attempts must not become capability facts.
- `tracked_not_mainline`: tracked by audit/backlog but not an active runtime expansion.
- `quality_backlog_tracked`: quality work is visible and bounded by existing evaluation gates.

## Closure Matrix

| Item | Closure State | Runtime Effect |
| --- | --- | --- |
| HTTP/Web adapter | `implemented_ready` via callable transport adapter | No server dependency; route-like calls return backend envelopes |
| `TTS_presence_timing` | `preserved_ready` after audit streak | Timing-only output telemetry remains inside `digital_body` |
| Multimodal inputs | `deferred_fail_closed` | Audio/image/screen/browser capture inputs are unavailable |
| Executor adapter | `implemented_ready` | Sandbox runner dispatch only; external harnesses fail closed |
| Dynamic skill generation | `deferred_fail_closed` | Managed skills stay; runtime skill authoring stays blocked |
| Chinese lexical de-scaffolding | `tracked_not_mainline` | Diagnostics remain; no broad surface rewrite in this closure |
| Capability self-growth | `quality_backlog_tracked` | Completed procedural traces may bias future actions; no second brain |
| Natural long-horizon calibration | `quality_backlog_tracked` | Appraisal/own-rhythm realism is tracked by evals, not prompt sprawl |

## Invariants

- The LangGraph persona loop remains authoritative.
- `final_text`, TTS, behavior packets, body consequence, and reconsolidation stay aligned.
- `action_packets` remain the only structured action unit.
- Existing sandbox phase-2 limits remain unchanged.
- Existing browser mutation/takeover limits remain unchanged.
- Existing skills registry truth remains outside autobiographical memory.
- Deferred surfaces must be visible as blocked/deferred status, not silently absent or falsely available.

## Validation

The final closure audit reports `post_baseline_closure_ready` only when:

- callable transport adapter tests pass
- executor adapter tests and audit pass
- deferred multimodal and dynamic skill-generation policies are fail-closed
- TTS timing has a sufficient passing audit streak or fresh closure reports
- Chinese/procedural-growth/natural-calibration lanes are tracked without runtime expansion

