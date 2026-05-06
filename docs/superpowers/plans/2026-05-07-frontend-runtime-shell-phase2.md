# Frontend Runtime Shell Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the React frontend shell consume route-like `backend.v1` envelopes and render Phase 2 operator/living-loop/embodied readbacks while staying a backend-contract consumer only.

**Architecture:** The frontend keeps the existing Vite/React shell and adds a thin route transport seam that validates backend envelopes without deriving memory, body, autonomy, or persona semantics. Contract types remain byte-synced between `docs/engineering/frontend_contract/backend_api.types.ts` and `frontend/src/contracts/backend.ts`; UI additions display backend-owned payload blocks as read-only records/JSON. A deterministic audit proves build health, contract sync, route-client presence, readback rendering, and absence of frontend semantic ownership modules.

**Tech Stack:** React 19, Vite 8, TypeScript strict mode, Python `pytest`, deterministic `evals/` audit scripts, existing `backend.v1` envelope fixtures.

---

## File Structure

- Modify `docs/engineering/frontend_contract/backend_api.types.ts`
  - Add `runtime_productization` to `BackendKind`.
  - Add `RuntimeProductizationPayload`.
  - Add optional `operator_readback`, `living_loop_realism`, and `embodied_interaction` fields to turn/event payloads.
- Modify `frontend/src/contracts/backend.ts`
  - Keep byte-identical with the docs contract copy.
- Modify `frontend/src/data/mockBackend.ts`
  - Rename the session surface to a runtime-neutral `RuntimeSession`.
  - Include `runtimeProductization?: BackendEnvelopeFor<"runtime_productization">`.
  - Include `transportMode: "mock" | "route"`.
  - Export `createSessionSnapshotFromEnvelopes(...)` so mock and route transports share one grouping helper.
- Modify `frontend/src/runtime/backendClient.ts`
  - Add `BackendRoute`, `BackendRouteTransport`, `BackendClientOptions`, `RouteBackendClient`.
  - Validate only common envelope fields: `schema_version`, `kind`, `status`, and object payload.
  - Keep frontend logic limited to grouping backend envelopes into `RuntimeSession`.
- Modify `frontend/src/App.tsx`
  - Render transport/readiness chips from session metadata.
  - Render `operator_readback`, `living_loop_realism`, and `embodied_interaction` from selected backend turn/event payloads.
  - Render the optional `runtime_productization` route envelope in the inspector.
- Modify `frontend/src/styles.css`
  - Add small layout helpers only for readback grouping if needed.
- Create `tests/test_frontend_runtime_shell_phase2.py`
  - Static tests for contract fields, route client shape, readback rendering strings, and consumer-only boundaries.
- Create `evals/run_frontend_runtime_shell_phase2_audit.py`
  - Run focused pytest checks and `npm --prefix frontend run build`.
  - Emit `frontend_runtime_shell_phase2_ready` when all checks pass.
- Create `tests/test_frontend_runtime_shell_phase2_audit.py`
  - Unit-test audit readiness and markdown rendering.
- Modify `evals/run_preserved_baselines_audit.py`
  - Add `frontend_runtime_shell_phase2` baseline metadata.
- Modify `tests/test_preserved_baselines_audit.py`
  - Add expected id and frontend category count.
- Update docs:
  - `AGENTS.md`
  - `docs/engineering/PROJECT_STRUCTURE.md`
  - `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
  - `docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md`
  - `program.md`

---

### Task 1: RED Tests For Frontend Phase 2 Contract

**Files:**
- Create: `tests/test_frontend_runtime_shell_phase2.py`

- [x] **Step 1: Write the failing static tests**

Add this test file:

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_frontend_phase2_contract_types_include_live_readback_surfaces():
    types = _read("frontend/src/contracts/backend.ts")
    docs_types = _read("docs/engineering/frontend_contract/backend_api.types.ts")

    for content in (types, docs_types):
        assert '| "runtime_productization"' in content
        assert "RuntimeProductizationPayload" in content
        assert "operator_readback?: JsonRecord" in content
        assert "living_loop_realism?: JsonRecord" in content
        assert "embodied_interaction?: JsonRecord" in content


def test_frontend_phase2_client_exposes_route_transport_without_backend_semantic_ownership():
    client = _read("frontend/src/runtime/backendClient.ts")

    assert "BackendRouteTransport" in client
    assert "RouteBackendClient" in client
    assert 'schema_version !== "backend.v1"' in client
    assert "createSessionSnapshotFromEnvelopes" in client

    forbidden = ["memoryReducer", "personaReducer", "autonomyReducer", "digitalBodyReducer"]
    for term in forbidden:
        assert term not in client


def test_frontend_phase2_ui_renders_backend_owned_readback_blocks():
    app = _read("frontend/src/App.tsx")

    assert "Operator readback" in app
    assert "Living loop realism" in app
    assert "Embodied interaction" in app
    assert "Runtime productization" in app
    assert "session.transportMode" in app


def test_frontend_phase2_has_no_frontend_owned_semantic_modules():
    frontend_files = list((ROOT / "frontend" / "src").rglob("*"))
    forbidden_names = {
        "memoryReducer.ts",
        "personaReducer.ts",
        "autonomyReducer.ts",
        "digitalBodyReducer.ts",
        "memoryStore.ts",
        "personaStore.ts",
        "autonomyStore.ts",
        "digitalBodyStore.ts",
    }

    assert not {path.name for path in frontend_files} & forbidden_names
```

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_frontend_runtime_shell_phase2.py -q
```

Expected: fail because Phase 2 contract fields and route transport do not exist yet.

---

### Task 2: Contract Types And Shared Session Snapshot

**Files:**
- Modify: `docs/engineering/frontend_contract/backend_api.types.ts`
- Modify: `frontend/src/contracts/backend.ts`
- Modify: `frontend/src/data/mockBackend.ts`

- [x] **Step 1: Add contract fields**

Apply the same TypeScript changes to both contract files:

```ts
export type BackendKind =
  | "memory_snapshot"
  | "worldline_view"
  | "bond_view"
  | "sources_view"
  | "persona_view"
  | "appraisal_view"
  | "behavior_queue_view"
  | "checkpoint_history"
  | "current_checkpoint"
  | "thread_inventory"
  | "runtime_layout"
  | "environment_summary"
  | "runtime_productization"
  | "event_round"
  | "assistant_turn";
```

```ts
export interface AssistantTurnPayload {
  final_text: string;
  ...
  operator_readback?: JsonRecord;
  living_loop_realism?: JsonRecord;
  embodied_interaction?: JsonRecord;
}
```

```ts
export interface EventRoundPayload {
  final_text: string;
  ...
  operator_readback?: JsonRecord;
  living_loop_realism?: JsonRecord;
  embodied_interaction?: JsonRecord;
}
```

```ts
export interface RuntimeProductizationPayload extends JsonRecord {
  schema?: string;
  readiness_status?: string;
  operator_snapshot?: JsonRecord;
  console_health?: JsonRecord;
  evidence_summary?: JsonRecord;
  route_inventory?: JsonRecord;
  next_action_hints?: JsonRecord[];
  lanes?: JsonRecord;
}
```

Add this map entry:

```ts
runtime_productization: RuntimeProductizationPayload;
```

- [x] **Step 2: Add runtime-neutral session grouping**

In `frontend/src/data/mockBackend.ts`, add:

```ts
export type TransportMode = "mock" | "route";

export interface RuntimeSession {
  threadId: string;
  schemaVersion: string;
  transportMode: TransportMode;
  transcript: TranscriptEntry[];
  persona: BackendEnvelopeFor<"persona_view">;
  worldline: BackendEnvelopeFor<"worldline_view">;
  bond: BackendEnvelopeFor<"bond_view">;
  runtimeProductization?: BackendEnvelopeFor<"runtime_productization">;
  sources: SourceRef[];
  claimLinks: ClaimLink[];
}

export type MockSession = RuntimeSession;
```

Then export `createSessionSnapshotFromEnvelopes(...)` that sorts transcript envelopes and uses `sources_view` when present, otherwise falls back to `assistant_turn.payload.sources`.

- [x] **Step 3: Run focused tests**

Run:

```powershell
python -m pytest tests/test_frontend_runtime_shell_phase2.py tests/test_frontend_contract_sync.py -q
```

Expected: Phase 2 static contract assertions pass, contract sync passes, route client assertions still fail until Task 3.

---

### Task 3: Thin Route Transport Client

**Files:**
- Modify: `frontend/src/runtime/backendClient.ts`

- [x] **Step 1: Implement route transport seam**

Replace the mock-only client with:

```ts
export type BackendRoute =
  | "/api/runtime-productization"
  | "/api/persona-view"
  | "/api/worldline-view"
  | "/api/bond-view"
  | "/api/sources-view";

export interface BackendRouteTransport {
  request(route: BackendRoute): Promise<{ status: number; body: unknown }>;
}

export interface BackendClientOptions {
  transport?: BackendRouteTransport;
}
```

`RouteBackendClient` should:

- request route envelopes,
- reject non-200 responses,
- validate `schema_version === "backend.v1"`,
- validate expected `kind`,
- pass envelopes to `createSessionSnapshotFromEnvelopes(..., "route")`,
- not interpret backend payload semantics.

- [x] **Step 2: Run focused tests**

Run:

```powershell
python -m pytest tests/test_frontend_runtime_shell_phase2.py tests/test_frontend_contract_sync.py -q
```

Expected: all Python static/frontend contract tests pass.

- [x] **Step 3: Run TypeScript build**

Run:

```powershell
npm --prefix frontend run build
```

Expected: TypeScript and Vite build succeed.

---

### Task 4: Readback Rendering

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css` only if necessary

- [x] **Step 1: Render backend-owned readbacks**

Add UI blocks under the selected packet panel:

```tsx
const readbackCards = [
  ["Operator readback", selectedPayload.operator_readback],
  ["Living loop realism", selectedPayload.living_loop_realism],
  ["Embodied interaction", selectedPayload.embodied_interaction],
] as const;
```

Render each present record through existing `DetailCard`, `RecordGrid`, and `JsonDump`.

- [x] **Step 2: Render runtime productization route envelope**

Add a compact chip:

```tsx
{session.runtimeProductization?.payload.readiness_status ? (
  <span className="chip chip--quiet">Productization {session.runtimeProductization.payload.readiness_status}</span>
) : null}
```

Add an inspector card titled `Runtime productization` that renders the route envelope payload when available.

- [x] **Step 3: Run focused tests and build**

Run:

```powershell
python -m pytest tests/test_frontend_runtime_shell_phase2.py -q
npm --prefix frontend run build
```

Expected: tests and build pass.

---

### Task 5: Phase 2 Audit And Preserved Baseline

**Files:**
- Create: `evals/run_frontend_runtime_shell_phase2_audit.py`
- Create: `tests/test_frontend_runtime_shell_phase2_audit.py`
- Modify: `evals/run_preserved_baselines_audit.py`
- Modify: `tests/test_preserved_baselines_audit.py`

- [x] **Step 1: Add audit script**

Audit checks:

```python
[
    [sys.executable, "-m", "pytest", "tests/test_frontend_runtime_shell_phase2.py", "tests/test_frontend_contract_sync.py", "-q"],
    [*npm_command(), "--prefix", "frontend", "run", "build"],
]
```

Return:

```python
"readiness_status": "frontend_runtime_shell_phase2_ready"
```

when all checks pass.

- [x] **Step 2: Add audit tests**

Test `evaluate_checks()` passes ready when all checks are passed, fails in-progress when one check fails, and markdown includes `frontend_runtime_shell_phase2_ready`.

- [x] **Step 3: Add preserved baseline row**

Add:

```python
{
    "id": "frontend_runtime_shell_phase2",
    "prefix": "frontend-runtime-shell-phase2-audit-",
    "expected_readiness": "frontend_runtime_shell_phase2_ready",
    "category": "frontend",
}
```

Update preserved-baseline tests to expect this id and `frontend` category count of 1.

- [x] **Step 4: Verify audit test RED/GREEN**

Run first before the implementation to see RED if the audit script is missing, then after adding it:

```powershell
python -m pytest tests/test_frontend_runtime_shell_phase2_audit.py tests/test_preserved_baselines_audit.py -q
python evals/run_frontend_runtime_shell_phase2_audit.py --run-tag phase2-dev
```

Expected after implementation: tests pass and audit reports `frontend_runtime_shell_phase2_ready`.

---

### Task 6: Documentation And Ledger

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md`
- Modify: `program.md`

- [x] **Step 1: Document Phase 2 boundary**

Add the ready gate:

```text
frontend_runtime_shell_phase2_ready
```

Document that Phase 2:

- consumes route-like `backend.v1` envelopes,
- renders `operator_readback`, `living_loop_realism`, and `embodied_interaction`,
- keeps frontend consumer-only,
- adds no HTTP server, execution authority, memory writes, persona mutation, frontend-owned semantics, live capture, skill registry writes, or external mutation.

- [x] **Step 2: Run docs/static checks**

Run:

```powershell
python -m pytest tests/test_frontend_runtime_shell_phase2.py tests/test_preserved_baselines_audit.py -q
```

Expected: docs strings and preserved-baseline metadata remain aligned.

---

### Task 7: Final Verification, Commit, Merge, Push

**Files:**
- All touched files

- [x] **Step 1: Run final verification in the worktree**

Run:

```powershell
$env:TEMP='E:\桌面\codex-temp'
$env:TMP=$env:TEMP
python -m pytest tests/test_frontend_runtime_shell_phase2.py tests/test_frontend_runtime_shell_phase2_audit.py tests/test_frontend_contract_sync.py tests/test_preserved_baselines_audit.py -q
npm --prefix frontend run build
python evals/run_frontend_runtime_shell_phase2_audit.py --run-tag phase2-final
python evals/run_frontend_runtime_shell_audit.py --run-tag phase2-regression
python evals/run_dynamic_skills_phase2_audit.py --run-tag frontend-phase2-regression
git diff --check
```

Expected: all commands exit 0; phase audit reports `frontend_runtime_shell_phase2_ready`; Phase 1 audit and dynamic skills regression remain ready.

- [x] **Step 2: Commit logical slices**

Suggested commits:

```powershell
git add docs/superpowers/plans/2026-05-07-frontend-runtime-shell-phase2.md tests/test_frontend_runtime_shell_phase2.py frontend/src/contracts/backend.ts docs/engineering/frontend_contract/backend_api.types.ts frontend/src/data/mockBackend.ts frontend/src/runtime/backendClient.ts frontend/src/App.tsx frontend/src/styles.css
git commit -m "feat: consume backend route envelopes in frontend shell"

git add evals/run_frontend_runtime_shell_phase2_audit.py tests/test_frontend_runtime_shell_phase2_audit.py evals/run_preserved_baselines_audit.py tests/test_preserved_baselines_audit.py
git commit -m "test: audit frontend runtime shell phase 2"

git add AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md program.md
git commit -m "docs: record frontend runtime shell phase 2"
```

- [x] **Step 3: Merge to main and verify**

Run:

```powershell
cd E:\桌面\amadeus-thread0
git merge --ff-only codex/frontend-runtime-shell-phase2
$env:TEMP='E:\桌面\codex-temp'
$env:TMP=$env:TEMP
npm --prefix frontend run build
python evals/run_frontend_runtime_shell_phase2_audit.py --run-tag post-merge
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
git diff --check
git push origin main
```

Expected: merge is fast-forward, build and audits pass on `main`, and `origin/main` receives the new commits.

---

## Self-Review

- Spec coverage:
  - route-like backend envelope consumption: Task 3
  - `assistant_turn` / `event_round` rendering: existing UI plus Task 4
  - `operator_readback` / `living_loop_realism` / `embodied_interaction` rendering: Task 4
  - frontend consumer-only audit: Task 5
  - preserved-baseline integration: Task 5
  - docs and ledger: Task 6
  - merge/push closure: Task 7
- Placeholder scan:
  - No `TBD`, `TODO`, `implement later`, or open-ended "similar to" steps remain.
- Type consistency:
  - `runtime_productization`, `RuntimeProductizationPayload`, `RuntimeSession`, `BackendRouteTransport`, and `RouteBackendClient` are introduced before use.

