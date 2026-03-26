# Project Structure

## Purpose

This document is the engineering map for the repository layout after the LangGraph-oriented restructuring.

The target is not arbitrary cleanliness. The target is:

- a deployable LangGraph app entry
- clear ownership boundaries
- compatibility during migration away from the original monolithic `graph.py`
- low-risk ongoing iteration

## Top-Level Layout

```text
amadeus-thread0/
├── amadeus_thread0/        # primary Python package
├── frontend/               # React/Vite frontend shell consuming frozen backend envelopes
├── docs/                   # architecture, evaluation, defense, maintenance docs
├── evals/                  # evaluation entrypoints and reports
├── tests/                  # regression suite
├── scripts/                # utility scripts
├── user_study/             # user-study runtime and raw materials
├── langgraph.json          # LangGraph / LangSmith deployment config
├── requirements.txt        # canonical dependency file
└── AGENTS.md               # repository-level agent operating brief
```

This matches the LangChain / LangGraph recommended pattern at the level that matters:

- root deployment config
- root dependency file
- single package containing project code
- graph entry exposed via `agent.py`

## Python Package Layout

```text
amadeus_thread0/
├── agent.py                # deployable graph entry
├── graph.py                # compatibility facade during migration
├── graph_parts/            # structured graph modules
├── runtime/                # runtime integrations and provider adapters
├── utils/                  # utility surfaces and compatibility exports
├── persona_specs/          # canonical persona / counterpart specifications
├── evolution_engine/       # self-evolution engine logic
├── cli.py                  # interactive CLI
├── memory_store.py         # memory persistence and retrieval
├── tools.py                # tool definitions / assembly
└── ...
```

## Graph Module Ownership

`amadeus_thread0/graph_parts/` is the main home for graph-related logic.

- `state.py`
  Thread state and payload types.
- `guards.py`
  OOC risk, persona gap, canon guard.
- `prompting.py`
  task-draft prompt construction and prompt-state rendering.
- `prompt_helpers.py`
  compact prompt fragments reused by prompt construction, especially worldline / carryover / agenda prompt snippets.
- `rewrite.py`
  rewrite-time persona/daily-dialog alignment logic.
- `postprocess.py`
  final utterance cleanup, surface diagnosis, and lightweight text normalization.
- `messages.py`
  message restoration, rolling window selection, and thread compaction helpers.
- `graph_builder.py`
  LangGraph assembly and runtime cache lifecycle.
- `tool_nodes.py`
  tool gate, tool execution, tool-limit handling, and post-model routing.
- `implicit_idle.py`
  idle-time event override construction and idle-seeded state-update entry.
- `prepare_turn_context.py`
  the front half of `prepare_turn`: retrieval, event normalization, appraisal input assembly, and carryover seeding.
- `perception.py`
  canonical perception-event normalization and session/perception metadata attachment for runtime input events.
- `session_context.py`
  graph-native session fabric normalization for conversation mode, channel, presence, and related runtime carryover fields.
- `prepare_turn_runtime.py`
  the back half of `prepare_turn`: persona/runtime state evolution, memory-triggered refresh, and behavior synthesis.
- `model_call_prepare.py`
  model-call preparation, generation-profile selection, and tool-call setup.
- `response_finalize.py`
  final text shaping after generation, including rewrite/postprocess handoff.
- `relational_carryover.py`
  interaction carryover and agenda residue propagation.
- `relational_runtime.py`
  relationship snapshots, counterpart summaries, and worldline focus aggregation.
- `relational.py`
  temporary compatibility re-export over the split relational modules; do not add new logic here.
- `retrieval.py`
  retrieval triggering, memory ranking helpers, and working-context assembly.
- `tooling.py`
  explicit tool-call parsing, memory-write inference, and graph-adjacent tool routing helpers.
- `nodes.py`
  graph-node implementations and light orchestration glue only.

## Compatibility Layer

`amadeus_thread0/graph.py` is still intentionally present.

It currently serves three purposes:

- backward-compatible import surface for tests and legacy callers
- home for remaining helpers that have not yet been migrated
- bridge for lazy cross-module references during the incremental split

Rule:

- new graph logic should not be added directly to `graph.py` unless it is strictly temporary compatibility glue

## Runtime Layer

`amadeus_thread0/runtime/` contains provider-facing and environment-facing modules:

- `settings.py`
- `backend_api.py`
- `backend_session.py`
- `event_identity.py`
- `memory_admin.py`
- `runtime_bundle.py`
- `thread_runtime.py`
- `tool_approval.py`
- `modeling.py`
- `session_orchestrator.py`
- `tts_io.py`

`backend_session.py` is the reusable backend-facing session surface:

- graph turn execution wrappers
- state snapshot / checkpoint history / behavior queue / persona / worldline / sources view assembly
- the thin boundary future frontends should depend on instead of CLI print logic

`final_state.py` holds final-state normalization for readback parity:

- canonical `behavior_action` / `behavior_plan` resolution for backend views and turn envelopes
- behavior queue fallback normalization
- the shared rule that persisted final plan wins, and plan derivation from action is fallback-only

`backend_api.py` is the transport-neutral frontend schema surface:

- wraps backend session and memory-admin views in stable envelopes
- exposes thread inventory, runtime layout, environment summary, turn/event response payloads
- provides the interface future frontend shells should consume before any CLI formatting

`event_identity.py` holds shared readback identity normalization:

- canonical `current_event` perception id hydration for backend envelopes and inspector summaries
- thin `session_context` readback normalization so turn/event identity is resolved once and reused

`tool_approval.py` holds the reusable approval policy surface:

- memory auto-resume checks
- approval preview normalization and clipping
- second-confirmation detection for high-risk memory writes

`memory_admin.py` holds direct memory-management and reflection-admin surfaces:

- profile correction / undo workflows
- memory listing and deletion helpers
- reflection proposal generation and durable write-back

`runtime_bundle.py` holds active backend lifecycle assembly:

- graph + memory store + backend session + memory admin bundling
- backend API factory for frontend-facing access
- thread switch rebuild path
- a stable runtime object future shells can reuse

`thread_runtime.py` holds worldline/runtime management surfaces:

- thread id generation and startup resolution
- per-worldline runtime path activation
- checkpoint/worldline directory enumeration
- shared-runtime warning policy

Top-level wrappers like `amadeus_thread0/settings.py` exist only to preserve old imports.
They are thin facades implemented through `amadeus_thread0/_compat.py`.

## Utility Layer

`amadeus_thread0/utils/` contains lower-level supporting modules and re-export surfaces:

- `tool_registry.py`
- `runtime_audit.py`
- `cli_views.py`
- `counterpart_profile.py`
- `perception_events.py`
- `state.py`
- `nodes.py`
- `tools.py`

Rule:

- if a module is generic support or compatibility-facing, it belongs here
- if a module directly shapes graph execution semantics, it belongs in `graph_parts/`

## Frontend Workspace

`frontend/` is a separate React/Vite workspace for backend-contract consumption.

- It should render frozen `backend.v1` envelopes rather than inventing an alternative state schema.
- Contract copies and mock fixtures should stay close to the frontend shell so UI work can proceed without touching backend internals.
- Any future transport adapter should remain thin and delegate semantics to `amadeus_thread0/runtime/backend_api.py` and `backend_session.py`.

## Entry Points

- deployment graph:
  `amadeus_thread0/agent.py`
- CLI:
  `python -m amadeus_thread0.cli`
- frontend dev shell:
  `cd frontend && npm run dev`
- deployment config:
  `langgraph.json`

## Migration Status

Already migrated out of the monolithic `graph.py`:

- state types
- graph assembly
- tool nodes
- idle override entry helpers
- `prepare_turn` front-half context assembly
- `prepare_turn` back-half runtime synthesis
- `call_model` preparation and finalization
- prompt construction
- prompt helper fragments
- message restoration and context window helpers
- relationship/worldline helper cluster
  this is now split into `relational_carryover.py` and `relational_runtime.py`
  `relational.py` remains only as a transition shim
- retrieval and ranking helpers
- tool routing and memory-write inference helpers
- rewrite logic
- postprocess / surface cleanup
  this now includes the main text-surface normalization cluster: structured-answer gating, reply compression, surface trim passes, malformed-fragment cleanup, and dialogue-surface diagnostics
- guards

Still reasonable future extraction targets:

- idle/event entry helpers adjacent to graph orchestration
- remaining lexical-intent helper clusters that are still imported through `graph.py`
- non-graph domain logic that can move closer to `runtime/` or dedicated domain packages

## Rules For Future Refactors

- prefer additive migration with compatibility exports
- do not break `from amadeus_thread0.graph import ...` until downstream callers are cleaned up intentionally
- when moving code, migrate tests and docs in the same change
- if a new subpackage is introduced, document ownership here immediately

## Validation Expectations

After structural edits, always verify:

```powershell
python -m py_compile amadeus_thread0/agent.py amadeus_thread0/graph.py
python - <<'PY'
from amadeus_thread0.agent import agent
print(type(agent).__name__)
PY
```

Then run the regression subset appropriate to the touched area.
