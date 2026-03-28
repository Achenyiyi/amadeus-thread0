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
- She should live through one unified memory substrate, not split into separate "persona brain" and "work brain" silos.
- She should interact through a `digital body`, not a static prompt shell or a fixed tool menu.
- Behavior should emerge from state, memory, appraisal, and relationship dynamics, not scene-by-scene keyword scripts.
- Capability should grow through embodied interaction, resource discovery, experimentation, and reconsolidation, not only through predeclared tool lists.
- Language is one behavior channel, not the whole system.
- The counterpart is a real relation target, not a command source; parity, boundaries, and self-rhythm matter.
- When short-term likability conflicts with selfhood continuity, preserve selfhood continuity.

## Mission

Build and maintain `Amadeus-K`: a LangChain/LangGraph-based long-term virtual companionship backend centered on:

- fixed persona core
- unified self-evolution without identity drift
- unified long-horizon memory and relationship continuity
- digital embodiment in bounded runtime environments
- natural multimodal interaction orchestration
- safety, traceability, and evaluation

## Current Product Boundary

- backend-first
- `CLI + TTS + evals`
- no new desktop UI in the current phase
- canonical shell remains `Amadeus 牧濑红莉栖`

## Current Phase Lock

- Current objective is `Digital Embodiment Convergence`, not frontend polish.
- Frontend work stays frozen unless it is strictly needed for backend contract handoff artifacts.
- `freeze_gate_ready` and `companion_autonomy_ready` are now baseline gates, not the final product target.
- While the future Chinese-rule replacement track is still deferred, do not spend mainline time on reply-tone or naturalness micro-polish unless it blocks runtime correctness, contract stability, or architecture closure.
- The active convergence target is:
  - one fixed persona
  - one unified memory substrate
  - one digital body that can perceive, act, verify, request access, and gradually learn how to use its environment
- Default optimization order:
  1. preserve `freeze_gate_ready`
  2. preserve `companion_autonomy_ready`
  3. formalize `digital body / access / resource` runtime surfaces
  4. let embodied interaction feed unified memory and unified evolution rather than opening a separate work-only subsystem

## Backend Freeze Gate Baseline

Backend work is allowed to move into autonomy buildout only while all of the following stay true:

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
  - after this gate is passed, remaining backend changes must preserve this baseline rather than reopen core-loop redesign.

If any item above is still failing, remain in backend maturation mode.

## Companion Autonomy Closure Gate

Autonomy work is not considered closed until all of the following are true:

- `autonomy_intent` is derived from frozen appraisal / motive / relationship / own-rhythm state, not from post-hoc text repair.
- `action_packets` are the only structured action unit for autonomy:
  - `proposal_id`
  - `origin`
  - `intent`
  - `status`
  - `risk`
  - `requires_approval`
  - `capability_steps`
  - `expected_effect`
  - `result_summary`
  - `writeback_ready`
- Approval semantics stay bounded:
  - `read` may auto-execute
  - `memory_write` follows the existing memory approval policy
  - `external_mutation` always requires human approval
- `backend_api`, `backend_session`, CLI summaries, and `reconsolidation_snapshot` all expose one consistent autonomy envelope:
  - `intent`
  - `action_packets`
  - `pending_approval`
  - `execution_trace`
  - `block_reason`
- packet writeback semantics stay honest:
  - only completed / executed packets count as facts
  - rejected / blocked / expired packets remain unfulfilled intentions or boundary consequences
- closure validation:
  - `python evals/run_companion_autonomy_audit.py`
  - autonomy audit must pass 3 consecutive runs
  - 4 manual smokes must pass:
    - natural everyday help
    - multi-step independent followthrough
    - overreach -> approval handoff
    - own-rhythm proactive continuation

## Non-Negotiable System Principles

- Persona core is fixed. Evolution updates state, not identity.
- Keep one unified memory substrate. Different experience traces may exist, but they must not become separate "brains."
- Treat tools, browser, files, shell, and accounts as parts of a `digital body`, not as a static capability checklist.
- Missing access, cookies, accounts, or permissions are not only hard stops; they are world conditions she may reason about, work around, ask about, or explicitly request help for.
- Do not reduce future capability growth to a fixed tool suite. The long-term target is embodied experimentation, procedural learning, and bounded capability formation inside approved environments.
- Do not hard-script persona behavior with keyword rules unless it is strictly for safety, auditability, or tool routing.
- Do not treat current Chinese reply-surface polish as a mainline goal while the lexical replacement track is still deferred; prioritize runnable architecture and correct state/writeback contracts first.
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
- `amadeus_thread0/graph_parts/autonomy_runtime.py`
- `amadeus_thread0/graph_parts/action_packets.py`
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
python -m pytest tests/test_companion_autonomy_runtime.py
python -m pytest tests/test_autonomy_writeback.py
```

For memory or tool-path edits, also run:

```powershell
python -m pytest tests/test_memory_guard.py
python -m pytest tests/test_session_orchestrator.py
python -m pytest tests/test_cli_views.py
python -m pytest tests/test_backend_session.py tests/test_backend_api.py tests/test_tool_approval_policy.py
```

For entrypoint or structure edits, also verify:

```powershell
python -m py_compile amadeus_thread0/agent.py amadeus_thread0/graph.py
python - <<'PY'
from amadeus_thread0.agent import agent
print(type(agent).__name__)
PY
python evals/run_companion_autonomy_audit.py
```

Expected graph build result: `CompiledStateGraph`

## Documentation Map

- Live progress ledger: [`program.md`](./program.md)
- Blueprint: [`docs/DIGITAL_PERSONA_LIFEFORM_BLUEPRINT.md`](./docs/DIGITAL_PERSONA_LIFEFORM_BLUEPRINT.md)
- Persona constitution: [`docs/PERSONA_SYSTEM_CONSTITUTION.md`](./docs/PERSONA_SYSTEM_CONSTITUTION.md)
- Architecture alignment: [`docs/ARCHITECTURE_ALIGNMENT_MAP.md`](./docs/ARCHITECTURE_ALIGNMENT_MAP.md)
- Self-evolution engine: [`docs/SELF_EVOLUTION_ENGINE.md`](./docs/SELF_EVOLUTION_ENGINE.md)
- Structure guide: [`docs/engineering/PROJECT_STRUCTURE.md`](./docs/engineering/PROJECT_STRUCTURE.md)
- Architecture decisions: [`docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`](./docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md)
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
