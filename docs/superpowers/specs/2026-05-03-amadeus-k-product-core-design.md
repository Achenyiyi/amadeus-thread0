# Amadeus-K Product Core Design

## Goal

Build a clean, production-oriented backend product layer inside the current repository that extracts the stable Amadeus-K capabilities from the research codebase and exposes a complete frontend contract for a real virtual digital persona experience.

This layer must support later Live2D / web frontend integration, but this spec does not implement frontend UI. It delivers backend APIs, frontend-facing schemas, example payloads, and documentation that can guide both frontend implementation and undergraduate thesis writing.

## Background

The original graduation-design documents define the target as a multimodal personalized dialogue interaction system for a 2D IP character. The expected final state includes:

- character voice / persona restoration
- character-origin memory
- long-term user companionship memory
- Live2D visual embodiment
- text and voice interaction
- integrated runnable software

The current repository has evolved beyond the original implementation plan. Instead of a simple fine-tuned role-play chatbot, it now contains a research-grade LangGraph backend with:

- fixed persona core
- unified memory and relationship continuity
- appraisal -> state -> motive -> behavior -> consequence -> reconsolidation loop
- action packets and approval semantics
- digital body / access / resource state
- skills capability ecology
- live browser runtime
- sandbox execution baselines
- CLI / TTS / eval artifacts

The problem is that these capabilities are distributed across a large research codebase with many historical baselines, smoke reports, experimental branches, and frozen or incomplete surfaces. The product layer should not rewrite that research backend. It should extract and adapt the stable capabilities into a coherent deliverable.

## Non-Goals

This project core does not:

- implement the frontend UI
- download or bundle Live2D models
- implement commercial Live2D model parameter mapping
- finish Docker Sandbox Phase 2 closeout
- rebuild a full GraphRAG character-origin knowledge base
- perform LoRA / SFT training
- package a desktop pet application
- target embedded hardware
- delete or restructure the existing research backend

Docker Sandbox Phase 2 remains an experimental capability until its smoke/audit suite reaches readiness. It must not be presented as a preserved production baseline.

## Architecture Decision

Use LangGraph + LangChain as the backend foundation.

LangGraph remains the right layer because the persona system depends on stateful control flow, long-horizon persistence, action approval, and explicit state transitions. LangChain remains the model/tool/RAG foundation used by graph nodes and runtime integrations.

Do not introduce Deep Agents for this graduation-deliverable layer. The current system already owns the graph control flow and memory semantics; adding another orchestration layer would increase implementation and thesis complexity.

## Package Location

Create a new product package in the current repository:

```text
apps/
  amadeus_k/
    README.md
    backend/
      __init__.py
      app.py
      adapter.py
      avatar_state.py
      capabilities.py
      schemas.py
    contracts/
      amadeus_k_api.types.ts
      examples/
        bootstrap.response.json
        turn.response.json
        approval_pending.response.json
        capabilities.response.json
    docs/
      FRONTEND_CONTRACT.md
      PRODUCT_BOUNDARY.md
      DEMO_SCRIPT.md
```

The existing `amadeus_thread0/` package remains the research backend and capability source. The new product package imports stable runtime entry points from it and translates them into a narrower product contract.

## Product Boundary

The product core exposes a backend that is complete enough to be used by a real frontend:

- A frontend can bootstrap session state.
- A frontend can submit a user turn and receive a stable product envelope.
- A frontend can display final text and feed TTS text to a speech layer.
- A frontend can render memory, relationship, autonomy, approval, and digital-body state without knowing old internal field names.
- A frontend can drive Live2D expression/motion via `avatar_state`.
- A frontend can inspect capability readiness and avoid presenting experimental surfaces as ready.

The product core is not a toy mock. It must prefer real `amadeus_thread0` runtime output. Demo/example JSON files are contract fixtures, not the primary runtime.

## Backend Interfaces

### Runtime Assembly

`apps/amadeus_k/backend/adapter.py` owns product-runtime construction and turn adaptation.

It should use:

- `amadeus_thread0.runtime.runtime_bundle.RuntimeBundle.create()`
- `RuntimeBundle.backend_api(...)`
- `BackendSession.invoke_stream(...)`
- `BackendAPI.build_turn_response(...)`

The adapter must hide the old backend envelope shape from frontend consumers. It can keep original backend payload fragments in a clipped `diagnostics.raw_backend_kind` / `diagnostics.backend_schema_version` field, but the frontend contract must not require old internal fields.

### HTTP API

`apps/amadeus_k/backend/app.py` exposes a small HTTP surface:

```text
GET  /health
GET  /session/bootstrap
POST /turn
GET  /capabilities
POST /approval/{proposal_id}/approve
POST /approval/{proposal_id}/reject
```

Implementation priority:

1. `/health`
2. `/session/bootstrap`
3. `/turn`
4. `/capabilities`
5. approval endpoints

If approval endpoints cannot safely execute in the first implementation pass, their contract should be defined and they should return a typed `not_implemented` capability response rather than silently pretending approval succeeded.

## Product Schemas

All frontend-facing envelopes use:

```text
schema_version = "amadeus-k.product.v1"
```

### ProductBootstrapEnvelope

Fields:

- `schema_version`
- `thread_id`
- `generated_at`
- `persona`
- `session`
- `capabilities`
- `frontend_hints`

Purpose:

- Initial frontend setup.
- Tells the frontend which backend capabilities are ready, experimental, blocked, or unavailable.
- Provides default avatar mappings without requiring a frontend to inspect graph internals.

### ProductTurnEnvelope

Fields:

- `schema_version`
- `thread_id`
- `turn_id`
- `generated_at`
- `user_text`
- `final_text`
- `tts_text`
- `avatar_state`
- `memory_view`
- `relationship_view`
- `autonomy`
- `approvals`
- `digital_body`
- `capabilities`
- `diagnostics`

This is the primary frontend contract.

`final_text` is the only assistant utterance for display.

`tts_text` defaults to `final_text` unless a future TTS layer requires a sanitized spoken variant. Text and TTS must not diverge semantically.

### AvatarState

Fields:

- `emotion`
- `motion`
- `speaking`
- `intensity`
- `reason`
- `suggested_expression`
- `suggested_motion_group`

Allowed emotions:

- `neutral`
- `smile`
- `sad`
- `surprised`
- `angry`
- `blush`
- `thinking`
- `approval_wait`

Allowed motions:

- `idle`
- `tap_body`
- `thinking`
- `approval_wait`
- `speaking`

The backend emits semantic avatar hints. The frontend owns model-specific mapping. For example, a Live2D Natori mapping can map `smile` to `Smile`, `sad` to `Sad`, and `blush` to `Blushing`.

### MemoryView

Fields:

- `summary`
- `recent_continuity`
- `writeback_happened`
- `writeback_preview`

Purpose:

- Give the frontend a compact, human-readable memory state without exposing database tables.
- Support thesis demos showing that user interactions become durable continuity traces.

### RelationshipView

Fields:

- `summary`
- `stance`
- `bond_label`
- `continuity_preview`
- `unresolved_tension_count`
- `commitment_count`

Purpose:

- Show companionship continuity as a product feature.
- Avoid exposing raw graph-state structures.

### AutonomyView

Fields:

- `mode`
- `reason`
- `primary_proposal_id`
- `pending`
- `action_packets`
- `execution_trace`
- `block_reason`

Purpose:

- Make autonomous intentions and action packets visible.
- Preserve honest semantics: pending/rejected/blocked actions are not completed facts.

### ApprovalView

Fields:

- `has_pending`
- `proposal_id`
- `kind`
- `message`
- `risk`
- `required_action`
- `preview`

Purpose:

- Let the frontend render approval controls.
- Keep human-in-the-loop boundaries visible.

### DigitalBodyView

Fields:

- `active_surface`
- `access_mode`
- `world_surfaces`
- `filesystem_state`
- `browser_state`
- `sandbox_state`
- `skill_state`
- `workspace_root`
- `last_run`
- `experimental_notes`

Purpose:

- Convert the research backend's digital-body truth into a product read model.
- Support frontend status panels and thesis diagrams.

### CapabilityView

Fields:

- `id`
- `label`
- `status`
- `description`
- `evidence`
- `frontend_visible`

Allowed statuses:

- `ready`
- `experimental`
- `blocked`
- `unavailable`

Initial capabilities:

- `dialogue_core`: `ready`
- `long_term_memory`: `ready`
- `relationship_continuity`: `ready`
- `autonomy_action_packets`: `ready`
- `approval_gate`: `ready`
- `digital_body_state`: `ready`
- `skills_ecosystem`: `ready`
- `live_browser_runtime`: `ready`
- `sandbox_phase1`: `ready`
- `sandbox_phase2_docker`: `experimental`
- `tts`: `ready` or `unavailable`, depending on local settings/env
- `live2d_frontend`: `unavailable` in backend-only delivery

## Avatar State Derivation

`apps/amadeus_k/backend/avatar_state.py` maps backend payloads to frontend avatar hints.

Inputs:

- `final_text`
- `emotion_label`
- `turn_summary`
- `autonomy`
- `approvals`
- `digital_body`
- `digital_body_consequence`
- `reconsolidation_snapshot`
- `relationship_view`

Rules:

- Pending approval -> `emotion=approval_wait`, `motion=approval_wait`
- Blocked or environmental friction -> `emotion=thinking`
- Boundary stance or hard block -> `emotion=angry` only when the stance is clearly boundary/protective; otherwise `thinking`
- Repair, regret, sadness, or unresolved tension -> `emotion=sad`
- Warm continuity, presence, ordinary companionship -> `emotion=smile`
- Surprise/discovery -> `emotion=surprised`
- Intimacy/blushing cues -> `emotion=blush`
- Default -> `emotion=neutral`

The derivation must be deterministic and testable. It should not add persona behavior; it only maps already-derived backend state to a presentation hint.

## Frontend Contract Deliverables

`apps/amadeus_k/contracts/amadeus_k_api.types.ts` is the frontend's stable type entry.

It should include:

- request types
- response envelope types
- all view types
- `AmadeusKClient` interface
- literal unions for avatar emotions, motions, capability statuses, and approval risk

Example JSON files must validate against the TypeScript contract by inspection and should be generated or manually kept in sync with Python schema defaults.

`apps/amadeus_k/docs/FRONTEND_CONTRACT.md` explains:

- startup flow
- turn flow
- approval flow
- capability display
- Live2D mapping guidance
- TTS guidance
- stable vs diagnostic fields

## Thesis Support Deliverables

`apps/amadeus_k/docs/PRODUCT_BOUNDARY.md` explains:

- what is implemented in the deliverable backend
- what remains experimental
- how the implementation maps to the original graduation-design goals
- why the final route differs from the initial fine-tune + GraphRAG + Memos plan

`apps/amadeus_k/docs/DEMO_SCRIPT.md` provides a reproducible demonstration script:

- bootstrap backend
- send ordinary companionship turn
- show memory/relationship continuity view
- trigger or inspect autonomy/approval state
- show digital-body status
- explain Live2D avatar-state output
- point out experimental Docker Phase 2 honestly

## Testing Strategy

Add focused tests for the product layer:

```text
tests/test_amadeus_k_avatar_state.py
tests/test_amadeus_k_contracts.py
tests/test_amadeus_k_adapter.py
```

Minimum verification:

- Avatar mapping is deterministic for approval, blocked, warm, sad, and neutral cases.
- Product envelopes always include required fields.
- Product capability statuses mark Phase 2 Docker as `experimental`.
- `tts_text` defaults to `final_text`.
- Adapter can transform a representative `BackendAPI.build_turn_response()` payload into `ProductTurnEnvelope`.
- Example JSON contains `schema_version=amadeus-k.product.v1`.

If live model invocation is unavailable or too slow for routine tests, adapter tests may use representative backend envelopes copied from existing backend contract fixtures. The runtime path must still exist and be documented.

## Acceptance Criteria

The product-core refactor is complete when:

- The product package exists under `apps/amadeus_k/`.
- Backend schemas and TypeScript contract exist.
- A product adapter transforms old backend turn envelopes into product turn envelopes.
- `avatar_state` is present on every product turn.
- Capability reporting distinguishes ready, experimental, blocked, and unavailable capabilities.
- Example JSON responses are present for bootstrap, normal turn, approval-pending turn, and capabilities.
- Frontend contract docs explain how to connect a later Live2D frontend.
- Product boundary docs support thesis writing.
- Demo script shows how to present the system as a real backend product.
- Existing research backend files are not destructively reorganized.
- `program.md` is updated with the new product-core direction and validation results.

## Risk Controls

- Keep old imports stable.
- Do not delete old eval reports or experimental code during this refactor.
- Do not mark Docker Phase 2 as ready.
- Do not add frontend implementation.
- Do not allow frontend consumers to depend on old backend internals.
- Prefer adapter tests over live model tests for routine verification.
- Use actual backend entry points where feasible so the product layer remains real, not mock-only.

## Open Implementation Choice

The first implementation pass may choose one of two runtime modes:

1. Adapter-first: build and test the product adapter against representative backend envelopes, then wire HTTP endpoints.
2. Runtime-first: wire `RuntimeBundle.create()` immediately and return live product envelopes from `/turn`.

Adapter-first is safer for today because it delivers stable frontend contracts and deterministic tests quickly. Runtime-first is more impressive but can be slowed by model/runtime availability. The design should support both, with adapter-first as the recommended implementation order.
