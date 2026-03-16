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
- `relational.py`
  relationship runtime snapshots, interaction carryover, and worldline focus aggregation.
- `retrieval.py`
  retrieval triggering, memory ranking helpers, and working-context assembly.
- `tooling.py`
  explicit tool-call parsing, memory-write inference, and graph-adjacent tool routing helpers.
- `nodes.py`
  graph nodes, graph assembly, runtime graph helpers.

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
- `modeling.py`
- `session_orchestrator.py`
- `tts_io.py`

Top-level wrappers like `amadeus_thread0/settings.py` exist only to preserve old imports.
They are thin facades implemented through `amadeus_thread0/_compat.py`.

## Utility Layer

`amadeus_thread0/utils/` contains lower-level supporting modules and re-export surfaces:

- `tool_registry.py`
- `runtime_audit.py`
- `cli_views.py`
- `perception_events.py`
- `state.py`
- `nodes.py`
- `tools.py`

Rule:

- if a module is generic support or compatibility-facing, it belongs here
- if a module directly shapes graph execution semantics, it belongs in `graph_parts/`

## Entry Points

- deployment graph:
  `amadeus_thread0/agent.py`
- CLI:
  `python -m amadeus_thread0.cli`
- deployment config:
  `langgraph.json`

## Migration Status

Already migrated out of the monolithic `graph.py`:

- state types
- graph assembly
- tool nodes
- `prepare_turn`
- `call_model`
- prompt construction
- prompt helper fragments
- message restoration and context window helpers
- relationship/worldline helper cluster
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
