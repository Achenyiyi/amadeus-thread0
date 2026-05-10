# Amadeus-K Frontend Backend API Spec For Gemini

Updated: 2026-05-07

This document is a frontend-facing backend interface brief for designing an Amadeus-K operator beta frontend.

It is written for a frontend implementer or design agent such as Gemini. The frontend must treat the backend as the single source of truth for persona, memory, digital body, autonomy, skills, multimodal readbacks, and runtime status.

## 1. Product Context

Project: `amadeus-thread0 / Amadeus-K`

Current product shape:

- Backend-first technical preview.
- Primary runtime: Python backend plus CLI plus eval/audit reports.
- Frontend role: thin consumer of `backend.v1` envelopes.
- Canonical persona: `Amadeus 牧濑红莉栖`.
- Recommended frontend framing: `Amadeus-K Operator Beta Console`.

Main frontend-facing backend surfaces:

- `assistant_turn`
- `event_round`
- `persona_view`
- `worldline_view`
- `bond_view`
- `sources_view`
- `runtime_productization`
- `operator_console_rc`

The frontend may render backend-owned readbacks, but must not recompute or own backend semantics.

The frontend must not own or mutate:

- persona identity
- memory writes
- relationship state
- digital body state
- autonomy/action authority
- skill registry state
- multimodal perception semantics
- living-loop causality
- Chinese semantic rewrite policy

Authoritative implementation references:

- [`FRONTEND_INTERFACE_DELIVERABLE.md`](./FRONTEND_INTERFACE_DELIVERABLE.md)
- [`BACKEND_HANDOFF.md`](./BACKEND_HANDOFF.md)
- [`backend_api.py`](/E:/桌面/amadeus-thread0/amadeus_thread0/runtime/backend_api.py)
- [`transport_adapter.py`](/E:/桌面/amadeus-thread0/amadeus_thread0/runtime/transport_adapter.py)
- [`http_transport.py`](/E:/桌面/amadeus-thread0/amadeus_thread0/runtime/http_transport.py)

## 2. Transport Model

The stable frontend contract is the `BackendAPI` envelope.

```ts
type BackendEnvelope<TPayload = Record<string, unknown>> = {
  schema_version: "backend.v1";
  generated_at: number;
  kind: BackendKind;
  thread_id: string;
  payload: TPayload;
  meta: Record<string, unknown>;
};

type BackendKind =
  | "thread_inventory"
  | "runtime_layout"
  | "environment_summary"
  | "runtime_productization"
  | "operator_console_rc"
  | "persona_view"
  | "worldline_view"
  | "bond_view"
  | "sources_view"
  | "appraisal_view"
  | "behavior_queue_view"
  | "current_checkpoint"
  | "checkpoint_history"
  | "assistant_turn"
  | "event_round"
  | "memory_snapshot";
```

Every successful HTTP response should be rendered as a `BackendEnvelope`.

Example:

```json
{
  "schema_version": "backend.v1",
  "generated_at": 1710000000,
  "kind": "operator_console_rc",
  "thread_id": "thread-a",
  "payload": {},
  "meta": {}
}
```

HTTP status errors use this shape:

```ts
type BackendErrorResponse = {
  error: {
    code: "ROUTE_NOT_FOUND" | "METHOD_NOT_ALLOWED" | "INVALID_JSON" | string;
    message?: string;
    path?: string;
    method?: string;
    expected_method?: string;
  };
};
```

Transport note:

The repository currently provides a standard-library WSGI thin wrapper, not a full FastAPI, Flask, Express, SSE, or WebSocket service. Browser-accessible local development is available through `python -m amadeus_thread0.runtime.http_dev_server`, which serves the existing WSGI transport on `127.0.0.1:4180` by default.

No SSE/WebSocket streaming is currently exposed by the HTTP thin wrapper.

## 3. Existing HTTP Routes

These routes are implemented by `BackendTransportAdapter`.

| Method | Path | Envelope kind | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/thread-inventory` | `thread_inventory` | Available thread/checkpoint inventory |
| `GET` | `/api/runtime-layout` | `runtime_layout` | Repo/runtime path layout |
| `GET` | `/api/environment-summary` | `environment_summary` | Provider/TTS/runtime environment summary |
| `GET` | `/api/runtime-productization` | `runtime_productization` | Operator/productization readback |
| `GET` | `/api/operator-console-rc` | `operator_console_rc` | Release-candidate operator console |
| `GET` | `/api/persona-view` | `persona_view` | Current persona/internal state view |
| `GET` | `/api/worldline-view` | `worldline_view` | Long-horizon continuity view |
| `GET` | `/api/bond-view` | `bond_view` | Relationship continuity view |
| `GET` | `/api/sources-view` | `sources_view` | Source/citation/evidence view |
| `GET` | `/api/appraisal-view` | `appraisal_view` | Current appraisal inspector |
| `GET` | `/api/behavior-queue` | `behavior_queue_view` | Proactive/own-rhythm queue view |
| `GET` | `/api/checkpoints/current` | `current_checkpoint` | Current checkpoint id |
| `GET` | `/api/checkpoints/history?limit=10` | `checkpoint_history` | Checkpoint history, limit clamped from 1 to 100 |
| `GET` | `/api/turns/current` | `assistant_turn` | Current backend graph state rendered as an `assistant_turn` envelope |
| `POST` | `/api/chat/send` | `assistant_turn` | Send a user message through `BackendSession.invoke_stream(...)` and return the completed assistant turn |
| `POST` | `/api/turns/finalize` | `assistant_turn` | Finalize a completed backend state into frontend payload |
| `POST` | `/api/event-rounds/finalize` | `event_round` | Finalize a completed event round state |

Important:

`GET /api/turns/current` is the canonical read-only route for the visible conversation surface. It calls `BackendSession.get_state_values(...)`, then returns the same `assistant_turn` payload shape as `build_turn_response(...)`. It does not send a new user message, call a model, write memory, execute tools, or mutate persona/body/autonomy state.

`POST /api/turns/finalize` is not a plain chat endpoint. It expects backend graph/session `state_values`, not just `{ "message": "..." }`.

`POST /api/chat/send` is the normal chat endpoint. It trims a non-empty `message`, delegates to `BackendSession.invoke_stream(...)`, then wraps the returned state through `BackendAPI.build_turn_response(...)`. The frontend must render the returned backend-owned `assistant_turn` envelope and must not fabricate replies locally.

Current request body:

```ts
type TurnFinalizeRequest = {
  state_values: Record<string, unknown>;
  streamed_text?: string;
  meta?: Record<string, unknown>;
};
```

Current event finalize request body:

```ts
type EventRoundFinalizeRequest = {
  state_values: Record<string, unknown>;
  final_text?: string;
  meta?: Record<string, unknown>;
};
```

Current chat request body:

```ts
type ChatSendRequest = {
  message: string;
  config?: Record<string, unknown>;
  meta?: Record<string, unknown>;
};

type ChatSendResponse = BackendEnvelope<AssistantTurnPayload>;
```

## 4. Common Fetch Client

Gemini should design the frontend around a small typed adapter like this:

```ts
async function apiGet<T>(path: string): Promise<BackendEnvelope<T>> {
  const res = await fetch(path, { method: "GET" });
  const body = await res.json();
  if (!res.ok) throw body;
  return body as BackendEnvelope<T>;
}

async function apiPost<T>(path: string, data: unknown): Promise<BackendEnvelope<T>> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const body = await res.json();
  if (!res.ok) throw body;
  return body as BackendEnvelope<T>;
}
```

## 5. Primary Payloads

### 5.1 `assistant_turn.payload`

This is the main completed user-turn payload.

```ts
type AssistantTurnPayload = {
  final_text: string;

  emotion_label?: string;
  emotion_state?: Record<string, unknown>;
  bond_state?: Record<string, unknown>;
  allostasis_state?: Record<string, unknown>;
  semantic_narrative_profile?: Record<string, unknown>;
  world_model_state?: Record<string, unknown>;
  evolution_state?: Record<string, unknown>;

  session_context?: Record<string, unknown>;
  current_event?: Record<string, unknown>;
  turn_appraisal?: Record<string, unknown>;
  turn_summary?: Record<string, unknown>;

  behavior_action?: Record<string, unknown>;
  behavior_plan?: Record<string, unknown>;
  interaction_carryover?: Record<string, unknown>;
  counterpart_assessment?: Record<string, unknown>;
  agenda_lifecycle_residue?: Record<string, unknown>;

  autonomy?: AutonomyEnvelope;
  skills?: SkillsEnvelope;
  digital_body?: Record<string, unknown>;
  digital_body_consequence?: Record<string, unknown>;

  reconsolidation_snapshot?: Record<string, unknown>;
  writeback_trace?: Record<string, unknown>;

  claim_links?: Array<Record<string, unknown>>;
  sources?: Array<Record<string, unknown>>;

  pending_utterance_fragment?: string;

  operator_readback?: OperatorReadbackPayload;
  dynamic_skill_candidate_runtime?: Record<string, unknown>;
  living_loop_realism?: Record<string, unknown>;
  embodied_interaction?: EmbodiedInteractionPayload;
  approved_artifact_multimodal_runtime?: Record<string, unknown>;
};
```

Rendering priority:

1. Show `final_text` as the assistant message.
2. If `autonomy.pending_approval.assist_request.message` exists, show it prominently as an access/approval request.
3. Show source chips from `sources` and `claim_links`.
4. Show collapsible inspector panels for `turn_appraisal`, `behavior_action`, `behavior_plan`, `reconsolidation_snapshot`, `living_loop_realism`, `embodied_interaction`, and `operator_readback`.

Do not recompute any of these blocks in the frontend.

### 5.2 `event_round.payload`

Used for idle/proactive/runtime event rounds.

```ts
type EventRoundPayload = Omit<
  AssistantTurnPayload,
  "skills" | "claim_links" | "sources" | "pending_utterance_fragment"
> & {
  final_text: string;
};
```

Render similarly to an assistant turn, but label the item as a proactive, idle, or runtime event when that information is available from `current_event` or `behavior_action`.

## 6. Autonomy Envelope

```ts
type AutonomyEnvelope = {
  intent?: Record<string, unknown>;
  action_packets?: ActionPacket[];
  pending_approval?: PendingApproval | null;
  execution_trace?: Array<Record<string, unknown>>;
  block_reason?: string;
  procedural_planning?: Record<string, unknown>;
};

type ActionPacket = {
  proposal_id?: string;
  origin?: string;
  intent?: string;
  status?: "pending" | "requires_approval" | "approved" | "completed" | "blocked" | "rejected" | string;
  risk?: string;
  requires_approval?: boolean;
  auto_execute?: boolean;
  result_summary?: string;
  block_reason?: string;

  execution_spec?: Record<string, unknown>;
  execution_preview?: Record<string, unknown>;
  execution_result?: Record<string, unknown>;

  browser_execution_spec?: Record<string, unknown>;
  browser_execution_preview?: Record<string, unknown>;
  browser_execution_result?: Record<string, unknown>;

  multimodal_inspection_spec?: Record<string, unknown>;
  multimodal_inspection_preview?: Record<string, unknown>;
  multimodal_inspection_result?: Record<string, unknown>;
};

type PendingApproval = ActionPacket & {
  assist_request?: AssistRequest;
};

type AssistRequest = {
  kind?: string;
  message?: string;
  requested_access?: string[];
  missing_access?: string[];
  selected_access_proposal?: string;
  requires_manual_takeover?: boolean;
  resume_mode?: "auto_continue" | "manual_continue" | string;

  proposal_id?: string;
  profile_id?: string;
  page_ref?: string;
  tab_id?: string;
};
```

Frontend behavior:

- If `pending_approval` exists, show an `Approval Required` panel.
- If `assist_request.message` exists, render it as the human-readable request.
- Do not mark pending, blocked, or rejected packets as completed capability.
- Do not create approval/resume commands unless the backend exposes explicit endpoints later.

## 7. Skills Envelope

```ts
type SkillsEnvelope = {
  installed?: SkillSummary[];
  matched?: SkillSummary[];
  active?: SkillSummary[];
  manual_overrides?: {
    enabled?: string[];
    disabled?: string[];
    pinned?: string[];
  };
  pending_approval?: {
    proposal_id?: string;
    operation?: "install" | "update" | "enable" | "disable" | "pin" | "unpin" | string;
    skill_id?: string;
    resolved_version?: string;
    source?: string;
    hash?: string;
    requested_permissions?: string[];
    sandbox_profiles?: string[];
    verification_summary?: string;
  } | null;

  dynamic_candidate_runtime?: Record<string, unknown>;
};

type SkillSummary = {
  skill_id?: string;
  name?: string;
  description?: string;
  version?: string;
  status?: string;
  triggers?: string[];
  surfaces?: string[];
  skill_excerpt?: string;
};
```

Rendering rules:

- `installed` is the registry catalog, metadata only.
- `matched` is the auto-selected subset.
- `active` is the actually active subset. Only this surface may show `skill_excerpt`.
- `pending_approval` must never be rendered as installed or active until the backend reports it that way.

## 8. Operator/Productization Payloads

### 8.1 `runtime_productization.payload`

Purpose: runtime/operator status dashboard.

```ts
type RuntimeProductizationPayload = {
  schema?: string;
  readiness_status?: string;
  operator_snapshot?: Record<string, unknown>;
  console_health?: Record<string, unknown>;
  evidence_summary?: Record<string, unknown>;
  route_inventory?: RouteInventory;
  next_action_hints?: string[];
  lanes?: Record<string, unknown>;
  authority_boundary?: AuthorityBoundary;
};
```

Use this for a `System Status` page.

Recommended panels:

- readiness badge
- console health
- evidence summary
- route inventory
- blocked lanes
- next actions

### 8.2 `operator_console_rc.payload`

Purpose: release-candidate operator console.

```ts
type OperatorConsoleRCPayload = {
  schema: "operator_console_rc.v1" | string;
  overall_status?: "passed" | "failed" | string;
  readiness_status?: string;
  console_mode?: "read_only" | string;
  release_posture?: string;
  summary?: Record<string, unknown>;
  readback_refs?: Record<string, unknown>;
  operator_panels?: Record<string, unknown>;
  route_inventory?: RouteInventory;
  authority_boundary?: AuthorityBoundary;
  next_actions?: string[];
  failure_reasons?: string[];
};
```

Use this as the main operator dashboard route.

```ts
const rc = await apiGet<OperatorConsoleRCPayload>("/api/operator-console-rc");
```

Design recommendation:

- Top status strip: `overall_status`, `readiness_status`, `release_posture`.
- Left nav: Runtime, Persona, Worldline, Bond, Sources, Approvals, RC Evidence.
- Main panel: `operator_panels`.
- Right sidebar: `authority_boundary`, `next_actions`, `failure_reasons`.

## 9. Inspector Views

### 9.1 `persona_view.payload`

Purpose: current internal state and persona-facing diagnostics.

```ts
type PersonaViewPayload = {
  persona_state?: Record<string, unknown>;
  emotion_state?: Record<string, unknown>;
  bond_state?: Record<string, unknown>;
  allostasis_state?: Record<string, unknown>;
  semantic_narrative_profile?: Record<string, unknown>;
  world_model_state?: Record<string, unknown>;
  evolution_state?: Record<string, unknown>;
  [key: string]: unknown;
};
```

Render as read-only state cards.

### 9.2 `worldline_view.payload`

Purpose: long-horizon continuity.

```ts
type WorldlineViewPayload = {
  worldline_events?: Array<Record<string, unknown>>;
  semantic_self_narratives?: Array<Record<string, unknown>>;
  revision_traces?: Array<Record<string, unknown>>;
  proactive_continuity_history?: Array<Record<string, unknown>>;
  [key: string]: unknown;
};
```

Render as a timeline.

### 9.3 `bond_view.payload`

Purpose: relationship continuity.

```ts
type BondViewPayload = {
  bond_state?: Record<string, unknown>;
  counterpart_assessment?: Record<string, unknown>;
  counterpart_assessment_history?: Array<Record<string, unknown>>;
  commitments?: Array<Record<string, unknown>>;
  unresolved_tension?: Array<Record<string, unknown>>;
  [key: string]: unknown;
};
```

Render as a relationship dashboard.

### 9.4 `sources_view.payload`

Purpose: source/citation/claim evidence.

```ts
type SourcesViewPayload = {
  sources?: Array<SourceItem>;
  claim_links?: Array<Record<string, unknown>>;
  [key: string]: unknown;
};

type SourceItem = {
  id?: string;
  kind?: string;
  title?: string;
  preview_line?: string;
  source_ref?: string;
  created_at?: number;
  [key: string]: unknown;
};
```

Render as source cards or an evidence drawer.

### 9.5 `appraisal_view.payload`

Purpose: current appraisal inspector.

```ts
type AppraisalViewPayload = {
  turn_appraisal?: Record<string, unknown>;
  appraisal?: Record<string, unknown>;
  [key: string]: unknown;
};
```

Render as collapsible diagnostics, not as primary user-facing content.

### 9.6 `behavior_queue_view.payload`

Purpose: proactive/own-rhythm queue.

```ts
type BehaviorQueueViewPayload = {
  behavior_queue?: Array<Record<string, unknown>>;
  queued_behaviors?: Array<Record<string, unknown>>;
  config?: Record<string, unknown>;
  [key: string]: unknown;
};
```

Render as an upcoming, latent motives, or own-rhythm panel.

## 10. Checkpoint Routes

### 10.1 `GET /api/checkpoints/current`

```ts
type CurrentCheckpointPayload = {
  checkpoint_id?: string;
  thread_id?: string;
  config?: Record<string, unknown>;
  [key: string]: unknown;
};
```

### 10.2 `GET /api/checkpoints/history?limit=10`

```ts
type CheckpointHistoryPayload = {
  checkpoints?: Array<Record<string, unknown>>;
  limit?: number;
  config?: Record<string, unknown>;
  [key: string]: unknown;
};
```

Use checkpoint routes for history/debug views, not as the primary chat history, unless the backend later exposes a dedicated conversation-history route.

## 11. Embodied Interaction Payload

`assistant_turn` and `event_round` may include `embodied_interaction`.

```ts
type EmbodiedInteractionPayload = {
  schema?: string;
  readiness_status?: string;

  artifact_semantics?: {
    semantic_observations?: Array<Record<string, unknown>>;
    [key: string]: unknown;
  };

  artifact_appraisal?: {
    evidence_items?: Array<Record<string, unknown>>;
    [key: string]: unknown;
  };

  artifact_motive?: {
    motive_hints?: Array<Record<string, unknown>>;
    [key: string]: unknown;
  };

  artifact_behavior_alignment?: {
    alignment_items?: Array<Record<string, unknown>>;
    [key: string]: unknown;
  };

  chinese_semantic_surface?: {
    runtime_policy?: Record<string, unknown>;
    naturalness?: ChineseSemanticNaturalness;
    [key: string]: unknown;
  };

  [key: string]: unknown;
};

type ChineseSemanticNaturalness = {
  schema?: string;
  status?: string;
  readiness_status?: string;
  selected_family?: string;
  runtime_final_text?: string;
  tts_text?: string;
  diagnostics?: Record<string, unknown>;
  authority_boundary?: AuthorityBoundary;
  failure_reasons?: string[];
};
```

Rendering guidance:

- `artifact_semantics`: show what approved artifact metadata contributed.
- `artifact_appraisal`: show read-only influence evidence.
- `artifact_motive`: show advisory motive hints.
- `artifact_behavior_alignment`: show whether behavior reflected motive hints.
- `chinese_semantic_surface.naturalness`: show diagnostics only in debug/operator mode.

Do not expose these blocks as editable state.

## 12. Authority Boundary

Many payloads include an authority boundary.

```ts
type AuthorityBoundary = {
  transport_role?: string;
  backend_semantics_owner?: boolean;
  frontend_semantics_owner?: boolean;

  memory_write_authority?: boolean;
  persona_core_mutation_allowed?: boolean;

  live_capture_enabled?: boolean;
  multimodal_model_auto_call_enabled?: boolean;
  dynamic_skill_registry_auto_write_enabled?: boolean;
  external_executor_auto_enabled?: boolean;
  sse_or_websocket_streaming_enabled?: boolean;

  [key: string]: unknown;
};
```

Frontend should display blocked capabilities honestly.

Common blocked surfaces:

- live microphone capture
- live camera capture
- background screen capture
- automatic multimodal model calls
- automatic skill registry writes
- external executor auto-enablement
- frontend-owned memory/persona/body semantics
- SSE/WebSocket streaming in the current thin wrapper

## 13. Route Inventory

```ts
type RouteInventory = {
  routes?: Array<{
    method?: string;
    path?: string;
    kind?: string;
    mode?: "read_only" | "finalize" | string;
    mutating?: boolean;
    description?: string;
  }>;
  [key: string]: unknown;
};
```

If `route_inventory` appears, use it to render available backend surfaces dynamically.

Do not create hidden mutation routes from it.

## 14. Recommended Frontend Pages

Gemini should design the frontend as an operator beta console, not a mass-market consumer app yet.

### 14.1 Conversation

Purpose: daily interaction surface.

Recommended regions:

- message stream
- current assistant `final_text`
- pending approval/access request panel
- source chips
- debug drawer for latest `assistant_turn`

Current backend caveat:

A real chat-send route is not exposed yet through HTTP. The production/default UI must not render a working-looking message input, voice button, TTS button, approval button, artifact button, or any other mutation control until the backend owns the matching route. If the backend route host is unavailable, show an explicit connection/error state instead of substituting mock data.

### 14.2 Operator Console

Primary route:

```txt
GET /api/operator-console-rc
```

Show:

- overall status
- readiness status
- release posture
- operator panels
- route inventory
- authority boundary
- next actions
- failure reasons

### 14.3 Runtime Status

Primary route:

```txt
GET /api/runtime-productization
```

Show:

- console health
- evidence summary
- lanes
- blocked-by-contract capabilities
- next-action hints

### 14.4 Persona / Internal State

Primary route:

```txt
GET /api/persona-view
```

Show:

- emotion
- bond
- allostasis
- world model
- evolution state
- semantic narrative profile

Use read-only cards.

### 14.5 Worldline

Primary route:

```txt
GET /api/worldline-view
```

Show:

- continuity timeline
- self-narrative changes
- revision traces
- proactive continuity

### 14.6 Bond

Primary route:

```txt
GET /api/bond-view
```

Show:

- relationship state
- counterpart assessment
- commitments
- unresolved tension
- repair stance

### 14.7 Sources

Primary route:

```txt
GET /api/sources-view
```

Show:

- current evidence
- source references
- preview lines
- claim links

### 14.8 Checkpoints

Routes:

```txt
GET /api/checkpoints/current
GET /api/checkpoints/history?limit=20
```

Show:

- current checkpoint
- checkpoint list
- restore UI only as disabled/future unless the backend exposes a restore endpoint

## 15. Suggested Frontend Data Model

```ts
type AppState = {
  threadId?: string;

  runtime?: BackendEnvelope<RuntimeProductizationPayload>;
  operatorConsole?: BackendEnvelope<OperatorConsoleRCPayload>;

  persona?: BackendEnvelope<PersonaViewPayload>;
  worldline?: BackendEnvelope<WorldlineViewPayload>;
  bond?: BackendEnvelope<BondViewPayload>;
  sources?: BackendEnvelope<SourcesViewPayload>;

  latestTurn?: BackendEnvelope<AssistantTurnPayload>;
  latestEvent?: BackendEnvelope<EventRoundPayload>;

  currentCheckpoint?: BackendEnvelope<CurrentCheckpointPayload>;
  checkpointHistory?: BackendEnvelope<CheckpointHistoryPayload>;

  errors: Array<{
    route: string;
    code: string;
    message?: string;
  }>;
};
```

## 16. UX Rules

Frontend must follow these rules:

1. Render backend payloads as source of truth.
2. Treat missing optional blocks as not available, not as failure.
3. Do not infer readiness from colors or copy; use `readiness_status`.
4. Do not infer capability from pending proposals.
5. Do not turn blocked lanes into live buttons.
6. Do not call multimodal APIs from the frontend.
7. Do not open microphone, camera, or background screen capture.
8. Do not write skill registry state.
9. Do not mutate persona, memory, or body state locally.
10. Use a collapsible JSON inspector for unknown additive fields.

## 17. Visual Design Direction

Recommended product framing:

`Amadeus-K Operator Beta Console`

Tone:

- serious technical companion runtime
- quiet cockpit, not marketing landing page
- dense but readable
- evidence-oriented
- Chinese-first UI acceptable
- no decorative hero page

Recommended layout:

- Left sidebar:
  - Conversation
  - Operator Console
  - Runtime
  - Persona
  - Worldline
  - Bond
  - Sources
  - Checkpoints
- Top status bar:
  - thread id
  - RC readiness
  - model/environment status
- Main panel:
  - current selected page
- Right inspector:
  - authority boundary
  - pending approval
  - latest evidence/readback

## 18. Integration Warning For Gemini

Do not assume these endpoints exist yet:

```txt
POST /api/approvals/:proposal_id/approve
POST /api/approvals/:proposal_id/reject
POST /api/approvals/:proposal_id/resume
POST /api/artifacts
POST /api/tts/toggle
POST /api/checkpoints/restore
```

They are reasonable future product endpoints, but the current backend HTTP thin wrapper does not expose them. `POST /api/chat/send` is implemented and is the only normal user-message send route at this stage.

If designing the UI, Gemini may mention these as future backend work in documentation, but should not render them as clickable product controls until the backend contract exists. Mock fixtures may be used only when explicitly enabled for development, such as `VITE_AMADEUS_USE_MOCK=true`, and the UI must label that state as a development fixture.

## 19. Minimal Current Integration Example

```ts
async function loadOperatorConsole() {
  return apiGet<OperatorConsoleRCPayload>("/api/operator-console-rc");
}

async function loadCurrentTurn() {
  return apiGet<AssistantTurnPayload>("/api/turns/current");
}

async function loadRuntimeStatus() {
  return apiGet<RuntimeProductizationPayload>("/api/runtime-productization");
}

async function loadPersona() {
  return apiGet<PersonaViewPayload>("/api/persona-view");
}

async function loadWorldline() {
  return apiGet<WorldlineViewPayload>("/api/worldline-view");
}

async function loadBond() {
  return apiGet<BondViewPayload>("/api/bond-view");
}

async function loadSources() {
  return apiGet<SourcesViewPayload>("/api/sources-view");
}

async function sendChat(message: string) {
  return apiPost<AssistantTurnPayload>("/api/chat/send", {
    message,
    meta: { client: "frontend_runtime_shell" },
  });
}
```

## 20. Recommended First Frontend Milestone

Build a live backend-consuming frontend first.

Milestone 1:

- Connect to:
  - `/api/turns/current`
  - `/api/operator-console-rc`
  - `/api/runtime-productization`
  - `/api/persona-view`
  - `/api/worldline-view`
  - `/api/bond-view`
  - `/api/sources-view`
  - `/api/checkpoints/current`
  - `/api/checkpoints/history`
  - `/api/chat/send`
- Render backend envelopes.
- Show readiness and authority boundaries.
- Use `GET /api/turns/current` for the visible conversation readback.
- Use `POST /api/chat/send` for normal chat input.
- Do not implement or render any other mutation buttons until the backend exposes the matching route.
- If the backend route host is unavailable, show an explicit connection/error state instead of substituting mock data.

Milestone 2:

Add approval/resume routes only after the backend defines explicit approval semantics for HTTP.

Milestone 3:

Add SSE/WebSocket streaming only after the final envelope contract remains stable.

## 21. One-Sentence Contract

The frontend is a backend-consuming operator/product shell over backend-owned `backend.v1` envelopes. It may send normal chat messages through `POST /api/chat/send` and visualize Amadeus-K's persona, continuity, evidence, runtime status, approvals, and embodied readbacks, but it must not become a second backend or invent its own memory/body/autonomy semantics.
