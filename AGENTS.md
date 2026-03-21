# AGENTS.md

This file is the repository-level operating brief for AI coding agents working on `amadeus-thread0`.

Keep this file short. Treat it as the table of contents and execution contract. Detailed rationale belongs in `docs/`.

## Project North Star

This repository does not target a generic chatbot or a prompt-driven role-play shell.
It targets a `digital persona lifeform seed`: a system where `Amadeus 牧濑红莉栖` keeps a fixed identity core while changing through lived interaction.

The canonical loop is:

`perception -> appraisal -> internal state change -> motive / goal shift -> behavior -> consequence -> memory reconsolidation -> self-narrative update`

Non-negotiable direction:

- Persona core is fixed; evolution changes state, not identity.
- Behavior should emerge from state, memory, appraisal, and relationship dynamics, not scene-by-scene keyword scripts.
- Language is one behavior channel, not the whole system.
- The counterpart is a real relation target, not a command source; parity, boundaries, and self-rhythm matter.
- When short-term likability conflicts with selfhood continuity, preserve selfhood continuity.

## Mission

Build and maintain `Amadeus-K`: a LangChain/LangGraph-based long-term virtual companionship backend centered on:

- fixed persona core
- self-evolution without identity drift
- long-horizon memory and relationship continuity
- natural multimodal interaction orchestration
- safety, traceability, and evaluation

## Current Product Boundary

- backend-first
- `CLI + TTS + evals`
- no new desktop UI in the current phase
- canonical shell remains `Amadeus 牧濑红莉栖`

## Current Phase Lock

- Current objective is backend maturation, not frontend polish.
- Frontend work stays frozen unless it is strictly needed for backend contract handoff artifacts.
- The backend is not considered complete until the loop can sustain fixed persona core, counterpart judgment, reconsolidation parity, self-narrative continuity, and own-rhythm traces without relying on prompt-heavy repair.
- Default optimization order:
  1. `appraisal -> internal state -> motive / goal -> behavior`
  2. `reconsolidation -> self-narrative -> counterpart assessment` persistence
  3. own-rhythm / proactive continuity traces
  4. eval and regression hardening

## Backend Freeze Gate

Backend work may be considered structurally complete only when all of the following are true:

- Core loop closure:
  - `appraisal -> internal state -> motive / goal -> behavior` resolves to one coherent final `behavior_action` / `behavior_plan` packet rather than mixed shells.
  - `final_text`, `behavior_action`, `behavior_plan`, `turn_summary`, and `reconsolidation_snapshot` agree on the same final-turn semantics.
  - counterpart judgment, boundary stance, repair stance, and own-rhythm behavior arise from state and memory, not prompt-heavy repair or keyword steering.
- Long-horizon persistence closure:
  - consequence, reactivation, self-narrative, and counterpart-assessment writeback all prefer frozen final behavior semantics over stale live intermediates.
  - self-narrative export preserves distinct axes such as `selfhood`, `boundary`, `repair`, `commitment`, `presence`, and `own-rhythm` without late flattening.
  - relationship timeline, commitments, unresolved tension, conflict repair, and self-narrative can be re-surfaced on later turns as genuine continuity traces.
- Natural conversation acceptance:
  - the AGENTS-required regression subset stays green for 3 consecutive runs with no newly opened core-loop regressions.
  - at least 3 manual natural-dialogue smoke packs pass:
    - everyday / low-stakes companionship
    - relational tension / repair / apology
    - self-rhythm / proactive continuity / boundary stance
  - smoke packs must show no duplicate output, no text/TTS drift, no obvious middle-state leak, and no obvious collapse into generic assistant tone.
- Frontend handoff gate:
  - the backend envelope contract in [`docs/engineering/BACKEND_HANDOFF.md`](./docs/engineering/BACKEND_HANDOFF.md) is stable enough that frontend work would mostly consume existing payloads rather than forcing backend architecture churn.
  - after this gate is passed, remaining backend work should be bug-fix or additive polish, not open-ended structural redesign.

If any item above is still failing, remain in backend maturation mode.

## Non-Negotiable System Principles

- Persona core is fixed. Evolution updates state, not identity.
- Do not hard-script persona behavior with keyword rules unless it is strictly for safety, auditability, or tool routing.
- Prefer model judgment plus explicit state updates over brittle prompt micromanagement.
- Text and TTS must share one final utterance.
- Root-cause fixes are preferred over patchy fallbacks.

## Canonical Entry Points

- LangGraph deployment entry: [`langgraph.json`](./langgraph.json)
- Graph app entry: [`amadeus_thread0/agent.py`](./amadeus_thread0/agent.py)
- Compatibility facade: [`amadeus_thread0/graph.py`](./amadeus_thread0/graph.py)
- Structured graph modules: `amadeus_thread0/graph_parts/`

## Repository Map

- `amadeus_thread0/agent.py`: deployable graph entry
- `amadeus_thread0/graph_parts/`: graph-facing modules
- `amadeus_thread0/runtime/`: runtime integrations and provider adapters
- `amadeus_thread0/utils/`: utility surfaces and compatibility re-exports
- `amadeus_thread0/persona_specs/`: canonical persona/counterpart specs
- `evals/`: local and LangSmith evaluation entrypoints
- `tests/`: regression suite
- `docs/`: architecture, evaluation, defense, and maintenance docs

Detailed structure: [`docs/engineering/PROJECT_STRUCTURE.md`](./docs/engineering/PROJECT_STRUCTURE.md)

## Where New Code Should Go

- New graph state / node / rewrite / guard / postprocess logic:
  place under `amadeus_thread0/graph_parts/`
- Provider/runtime integration:
  place under `amadeus_thread0/runtime/`
- General-purpose helper or compatibility export:
  place under `amadeus_thread0/utils/`
- Top-level files under `amadeus_thread0/` should stay thin and mostly serve as compatibility facades or domain entrypoints.

## High-Risk Zones

- `amadeus_thread0/graph_parts/nodes.py`
- `amadeus_thread0/graph_parts/rewrite.py`
- `amadeus_thread0/graph_parts/postprocess.py`
- `amadeus_thread0/memory_store.py`
- `amadeus_thread0/cli.py`

Changes here require targeted regression, not just import checks.

## Required Validation

For graph-layer edits, run at minimum:

```powershell
python -m pytest tests/test_daily_surface_gating.py
python -m pytest tests/test_generation_profile.py
python -m pytest tests/test_dialogue_mode_counterpart.py
python -m pytest tests/test_world_model_residue.py
python -m pytest tests/test_subjective_review_pack.py
```

For memory or tool-path edits, also run:

```powershell
python -m pytest tests/test_memory_guard.py
python -m pytest tests/test_session_orchestrator.py
python -m pytest tests/test_cli_views.py
```

For entrypoint or structure edits, also verify:

```powershell
python -m py_compile amadeus_thread0/agent.py amadeus_thread0/graph.py
python - <<'PY'
from amadeus_thread0.agent import agent
print(type(agent).__name__)
PY
```

Expected graph build result: `CompiledStateGraph`

## Documentation Map

- Live progress ledger: [`program.md`](./program.md)
- Blueprint: [`docs/DIGITAL_PERSONA_LIFEFORM_BLUEPRINT.md`](./docs/DIGITAL_PERSONA_LIFEFORM_BLUEPRINT.md)
- Persona constitution: [`docs/PERSONA_SYSTEM_CONSTITUTION.md`](./docs/PERSONA_SYSTEM_CONSTITUTION.md)
- Architecture alignment: [`docs/ARCHITECTURE_ALIGNMENT_MAP.md`](./docs/ARCHITECTURE_ALIGNMENT_MAP.md)
- Self-evolution engine: [`docs/SELF_EVOLUTION_ENGINE.md`](./docs/SELF_EVOLUTION_ENGINE.md)
- Structure guide: [`docs/engineering/PROJECT_STRUCTURE.md`](./docs/engineering/PROJECT_STRUCTURE.md)
- Backend handoff: [`docs/engineering/BACKEND_HANDOFF.md`](./docs/engineering/BACKEND_HANDOFF.md)

## Run Ledger

- `program.md` is the live per-run progress ledger.
- At the start of every run: read `AGENTS.md`, then read `program.md`.
- At the end of every run: update `program.md` with:
  - current focus
  - files changed
  - validations run
  - concrete next step
- Keep `program.md` concise and cumulative. Prefer a current-state summary plus dated run entries.

## Editing Rules For Agents

- Preserve backward-compatible imports when moving code between modules.
- Keep `graph.py` as a compatibility facade until downstream imports are cleaned up deliberately.
- Do not expand prompt constraints casually. If behavior is wrong, first inspect state evolution, retrieval, and postprocess layers.
- When adding a new module, also update the structure doc if the module changes ownership boundaries.
- Avoid destructive cleanup of user data, study artifacts, or historical docs unless they are explicitly confirmed obsolete.

## Maintenance Workflow

1. Read this file.
2. Read [`program.md`](./program.md).
3. Read the structure doc.
4. Identify the owning layer before editing.
5. Make the smallest structural change that improves maintainability.
6. Run the required regression for the touched layer.
7. Update docs if file ownership or execution flow changed.
8. Update [`program.md`](./program.md) before ending the run.
