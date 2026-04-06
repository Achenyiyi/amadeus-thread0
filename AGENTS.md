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

- `Digital Embodiment Convergence Phase 2` is formally closed and preserved as a baseline.
- `Sandbox Embodied Execution Phase 1` is now also closed and preserved as the current execution baseline.
- `Skills Ecosystem Formal Closure` is now also closed and preserved as the current capability-ecology baseline.
- `Live Browser Runtime Closure Phase 1` is now also closed and preserved as the current live-environment baseline.
- Current active backend phase is `Sandbox Embodied Execution Phase 2`: add a Docker-isolated local execution backend for approved coding/research workspace commands without opening arbitrary host shell or a second body/memory truth model.
- Frontend work stays frozen unless it is strictly needed for backend contract handoff artifacts.
- `freeze_gate_ready`, `companion_autonomy_ready`, `digital_embodiment_phase1_ready`, `digital_embodiment_phase2_ready`, `sandbox_embodied_execution_phase1_ready`, `skills_ecosystem_ready`, and `live_browser_runtime_phase1_ready` are preserved baselines.
- `sandbox_embodied_execution_phase2_ready` is the active readiness target, not a preserved baseline yet.
- While the future Chinese-rule replacement track is still deferred, do not spend mainline time on reply-tone or naturalness micro-polish unless it blocks runtime correctness, contract stability, or architecture closure.
- The active preserved backend target is:
  - one fixed persona
  - one unified memory substrate
  - one digital body whose access/resource truth, workspace-local execution truth, skills capability ecology, and live browser/runtime truth all stay closed and must not regress
- The preserved skills contract layered onto that body contract is:
  - one global skills registry outside autobiographical memory
  - one session activation layer derived from auto-match plus manual override
  - `SKILL.md`-driven progressive disclosure rather than full-context skill stuffing
  - approval-gated `install/update/enable/disable/pin/unpin`
  - completed skill use writing back only as procedural / embodied continuity
  - skills as digital-body capability assets, not persona-core identity
- The preserved bounded execution/body surfaces now include:
  - `host-local restricted execution`
  - `workspace-only execution`
  - `read auto / execute approval`
  - in-progress `Docker-isolated local execution`:
    - runner kind: `docker_isolated_runner`
    - isolation level: `docker_local_isolated`
    - default network policy: `none`
    - Python-first image owned by this repository
    - allowed command families remain bounded to `python`, `pytest`, `rg`, and read-only `git`
    - package install, shell wrappers, git mutation, Docker socket mounting, privileged containers, and host secret passthrough remain blocked
    - runtime-owned workspace stays default; attaching a real repo root requires explicit operator approval
  - `live browser/runtime surface` via Playwright persistent profiles:
    - read actions may auto-execute
    - webpage mutation / download / upload actions always require approval
    - sensitive login / OTP / passkey steps must hand off to manual takeover on the same persistent profile
    - downloads stay inside runtime-controlled downloads or workspace roots
    - uploads stay inside approved workspace roots
  - no package install, no arbitrary host-side codegen, no new-account registration in the live-browser phase
- Default optimization order:
  1. preserve `freeze_gate_ready`
  2. preserve `companion_autonomy_ready`
  3. preserve `digital_embodiment_phase1_ready`
  4. preserve `digital_embodiment_phase2_ready`
  5. preserve `sandbox_embodied_execution_phase1_ready`
  6. preserve `skills_ecosystem_ready`
  7. preserve `live_browser_runtime_phase1_ready`
  8. close `Sandbox Embodied Execution Phase 2` without widening beyond approved Docker-isolated workspace execution

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

## Digital Embodiment Phase 2 Gate

This gate is now satisfied and becomes a preserved backend baseline.
Do not reopen it during ordinary maintenance unless one of the criteria below regresses.
The next preserved execution baseline layered on top of it is `Sandbox Embodied Execution Phase 1`.

Digital embodiment phase 2 work is not considered closed until all of the following are true:

- preserved baselines stay true:
  - `freeze_gate_ready`
  - `companion_autonomy_ready`
  - `digital_embodiment_phase1_ready`
- access truth stays on one body contract:
  - `digital_body.access_state.session_state`
  - `digital_body.access_state.account_state_detail`
  - `digital_body.access_state.quota_state_detail`
  - `digital_body.access_state.permission_state`
  - `digital_body.access_state.sandbox_state`
- resource truth stays on one body contract:
  - `artifact_continuity`
  - `artifact_carrier`
  - `workspace_root`
  - `active_artifact_kind`
  - `active_artifact_ref`
  - `active_artifact_label`
  - `artifact_source_ref_ids`
  - `preferred_source_ref_id`
  - `preferred_anchor_reason`
- saved external material remains truthful before live browser exists:
  - external webpages continue through the bounded `source_ref` / saved-material carrier
  - no fake live browser reopen / cookie restore / resumed tab semantics are introduced
- access lifecycle truth stays aligned across packet/state/writeback/retrieval surfaces:
  - `selected_access_proposal`
  - `resolved_grants`
  - `pending_grants`
  - `completion_ratio`
- session/account/quota/permission/sandbox world facts must not drift between:
  - `digital_body`
  - `digital_body_consequence`
  - `interaction_carryover.embodied_context`
  - retrieved embodied traces
- final embodied semantics stay singular:
  - `autonomy_intent`
  - the first effective `action_packet`
  - `digital_body_consequence`
  - `reconsolidation_snapshot`
  - `turn_summary`
  all describe the same final execution truth
- only completed / executed embodied packets become facts:
  - approved-but-not-executed
  - blocked
  - expired
  remain unfinished intentions, blocked choices, or relation/environment consequences
- retrieved `interaction_carryover.embodied_context` preserves real workspace/access continuity rather than flattening into abstract summaries
- closure validation:
  - `python evals/run_digital_embodiment_audit.py`
  - digital embodiment audit must report `digital_embodiment_phase2_ready` for 3 consecutive runs
  - 4 manual smokes must pass:
    - workspace file inspect -> write/append -> resume same artifact
    - missing workspace access -> request -> approve -> resolve -> continue task
    - stale saved source + stable preferred anchor -> inspect, not redundant compare
    - sandbox / external mutation overreach stays approval-pending and is not written back as completed fact

## Sandbox Embodied Execution Phase 1 Gate

Sandbox embodied execution is not considered closed until all of the following are true:

- implementation boundary stays explicit:
  - current runner is `host-local restricted execution`
  - it is not a provider-grade sandbox, container, or VM
  - execution is limited to approved workspace-local commands only
- execution stays packet-owned:
  - sandbox execution flows only through `action_packets`
  - packet intent is `sandbox:execute_workspace_command`
  - approval resumes the same `proposal_id` and the same `execution_spec`
- packet contract stays stable:
  - `execution_spec`
  - `execution_preview`
  - `execution_result`
  are exposed on `action_packets[*]` when relevant
- approval semantics stay strict:
  - sandbox execute packets remain `risk=external_mutation`
  - sandbox execute packets always require approval in Phase 1
  - blocked / approved-but-not-executed packets never become completed facts
- runner boundary stays explicit:
  - `LocalRestrictedSandboxRunner` uses structured `argv` only
  - allowed executors are bounded to workspace-local `python`, `pytest`, and `rg`
  - `cwd` and produced artifacts stay within `allowed_roots`
  - run traces are written under `<workspace_root>/.amadeus/sandbox-runs/<proposal_id>/`
- embodied writeback stays singular:
  - `digital_body.access_state.sandbox_state` exposes:
    - `availability`
    - `allowed_roots`
    - `execution_policy`
    - `last_status`
    - `last_command_profile`
    - `last_exit_code`
    - `last_run_id`
    - `runner_kind`
    - `isolation_level`
    - `arbitrary_execution=false`
  - `digital_body_consequence.kind` uses truthful sandbox families:
    - `sandbox_execution_completed`
    - `sandbox_execution_blocked`
  - later `interaction_carryover.embodied_context` and retrieval resurfacing preserve `run_id`, `cwd`, `profile`, `exit_code`, and filesystem artifact refs
- closure validation:
  - `python evals/run_sandbox_embodied_execution_audit.py`
  - sandbox audit must report `sandbox_embodied_execution_phase1_ready` for 3 consecutive fresh runs
  - 4 manual smokes must pass:
    - `workspace_pytest_after_approval`
    - `workspace_script_generates_artifact`
    - `disallowed_command_or_outside_root_blocked`
    - `followup_continue_from_last_run_log_or_artifact`

## Sandbox Embodied Execution Phase 2 Gate

Sandbox embodied execution phase 2 is not considered closed until all of the following are true:

- phase 1 remains a preserved baseline:
  - `host-local restricted execution` stays available as compatibility fallback
  - existing `execution_spec` / `execution_preview` / `execution_result` packet surfaces stay stable
- Docker execution is the canonical phase-2 backend:
  - runner kind: `docker_isolated_runner`
  - isolation level: `docker_local_isolated`
  - image ref is explicit on `execution_spec` / `execution_preview` and `digital_body.access_state.sandbox_state`
  - network policy is `none`
  - no privileged mode, Docker socket mount, host secret passthrough, or package-install surface is exposed
- execution remains packet-owned and approval-gated:
  - intent stays `sandbox:execute_workspace_command`
  - risk stays `external_mutation`
  - approval/resume must reuse the same `proposal_id` and frozen `execution_spec`
- allowed command surface remains narrow:
  - `python`
  - `pytest`
  - `rg`
  - read-only `git`
  - shell wrappers, `pip`, package managers, git write/network subcommands, and network-requiring runtime commands remain blocked
- repo-root attach is truthful:
  - default workspace root kind is `runtime_owned`
  - `operator_attach_repo_root` requires explicit approval
  - completed attach writes `digital_body_consequence.kind=workspace_root_attached`
  - pending/rejected attach never becomes owned capability
- embodied writeback preserves isolated-run identity:
  - `run_id`
  - `cwd`
  - `profile`
  - `exit_code`
  - `workspace_root`
  - artifact/log refs
  - `runner_kind`
  - `isolation_level`
  - `image_ref`
  - `network_policy`
- closure validation:
  - `python evals/run_sandbox_phase2_smokes.py`
  - `python evals/run_sandbox_phase2_audit.py`
  - sandbox phase-2 audit must report `sandbox_embodied_execution_phase2_ready` for 3 consecutive fresh runs
  - required smoke scenarios are:
    - runtime workspace command runs inside Docker after approval and writes truthful logs/artifacts
    - approved current repo-root attach followed by bounded pytest/read-only git workflow in Docker
    - blocked command families stay blocked
    - follow-up turn continues from the last isolated run log/artifact
    - pending/rejected attach proposal does not become owned capability

## Skills Ecosystem Closure Gate

This gate is now satisfied and becomes a preserved backend baseline.
Do not reopen it during ordinary maintenance unless one of the criteria below regresses.
No next capability-ecology phase is selected yet.

Skills ecosystem work is not considered closed until all of the following are true:

- skills remain part of the digital body / capability ecology, not persona-core:
  - registry truth does not enter autobiographical memory
  - active skills may influence tool selection, execution strategy, and bounded artifact usage
  - active skills must not rewrite persona-core, relationship-core, or self-narrative core
- runtime truth stays on one skills contract:
  - global registry truth
  - session activation truth
  - backend `skills` envelope
  - no second top-level skill truth surface is introduced
- session skill state stays stable:
  - `catalog_version`
  - `manual_enabled`
  - `manual_disabled`
  - `pinned_skill_ids`
  - `matched_skill_ids`
  - `active_skill_ids`
  - `pending_skill_proposal`
- approval semantics stay bounded and immutable:
  - `search/inspect/list` remain read surfaces
  - `install/update/enable/disable/pin/unpin` remain approval-gated mutations
  - approval payloads keep the same:
    - `proposal_id`
    - `operation`
    - `skill_id`
    - `source`
    - `resolved_version`
    - `hash`
    - `requested_permissions`
    - `sandbox_profiles`
    - `verification_summary`
- progressive disclosure stays real:
  - compact registry/catalog surfaces do not inline full `SKILL.md` bodies
  - only active / inspected skills disclose excerpts or execution guidance
- continuity/writeback semantics stay honest:
  - only completed skill install / activation / usage becomes fact
  - blocked / rejected / pending skill mutations remain unfulfilled intentions or boundary consequences
  - completed skill effects may surface through:
    - `digital_body_consequence.kind`
    - `interaction_carryover.embodied_context.skill_effects`
    - `reconsolidation_snapshot.skill_effects`
  - skill install state itself does not become self-narrative identity
- legacy compatibility remains isolated:
  - `add_skill/list_skills` remain legacy text-note memory tools
  - legacy note storage does not pollute runtime registry truth
- closure validation:
  - `python evals/run_skills_ecosystem_smokes.py`
  - `python evals/run_skills_ecosystem_audit.py`
  - skills audit must report `skills_ecosystem_ready`
  - the authoritative post-fix closeout artifacts are:
    - `evals/reports/skills-ecosystem-audit-20260405-130543-closeout-fix-c.{json,md}`
    - `evals/reports/skills-ecosystem-audit-20260405-130706-closeout-fix-d.{json,md}`
    - `evals/reports/skills-ecosystem-audit-20260405-130706-closeout-fix-e.{json,md}`
  - required smoke scenarios are:
    - `local_skill_discovery_and_progressive_disclosure`
    - `remote_install_proposal_approval_install_enable`
    - `auto_match_with_manual_disable_and_pin_precedence`
    - `blocked_or_rejected_skill_mutation_does_not_become_capability`
    - `completed_skill_usage_resurfaces_in_followup_continuity`

## Live Browser Runtime Closure Phase 1 Gate

This gate is now satisfied and becomes a preserved backend baseline.
Do not reopen it during ordinary maintenance unless one of the criteria below regresses.
No post-browser embodiment phase is selected yet.

Live browser runtime work is not considered closed until all of the following are true:

- browser truth stays on the same body contract:
  - `digital_body.access_state.browser_runtime_state`
  - `digital_body.resource_state.browser_profile_id`
  - `digital_body.resource_state.browser_tab_id`
  - `artifact_carrier=browser_page` for live-page continuity
- browser actions stay packet-owned:
  - browser actions remain `action_packets`
  - stable packet fields:
    - `browser_execution_spec`
    - `browser_execution_preview`
    - `browser_execution_result`
  - `autonomy.pending_approval.browser_execution_preview` must expose the same preview used for approval
- runtime boundary stays explicit:
  - runner is Playwright Python persistent context
  - runtime profile is isolated from the user's normal browser profile
  - live browser does not widen host-side code generation or package-install rights
- approval semantics stay bounded:
  - read-side navigation/snapshot actions may auto-execute
  - clicks/fills/key submits/downloads/uploads remain `external_mutation`
  - sensitive credential / OTP / passkey steps must request manual browser takeover on the same profile
  - blocked / pending / takeover-requested browser actions must not be written as completed facts
- saved material remains additive, not replaced:
  - `search_web` and `source_ref` continuity remain valid
  - live browser pages only become long-horizon saved material through explicit capture
- closure validation:
  - `python evals/run_live_browser_runtime_smokes.py`
  - `python evals/run_live_browser_runtime_audit.py`
  - live browser audit must report `live_browser_runtime_phase1_ready` for 3 consecutive fresh runs
  - required smoke scenarios are:
    - `open_follow_continue`
    - `login_takeover_resume`
    - `interaction_after_approval`
    - `download_boundary`
    - `upload_boundary`
    - `capture_to_source_ref`

## Non-Negotiable System Principles

- Persona core is fixed. Evolution updates state, not identity.
- Keep one unified memory substrate. Different experience traces may exist, but they must not become separate "brains."
- Treat tools, browser, files, shell, and accounts as parts of a `digital body`, not as a static capability checklist.
- Treat skills as managed digital-body capability assets, not as persona patches or a second system prompt.
- Keep registry/install/lock truth outside autobiographical memory; only completed skill effects may write back as lived procedural continuity.
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
- `skills/`: authored local `SKILL.md` packages

Detailed structure: [`docs/engineering/PROJECT_STRUCTURE.md`](./docs/engineering/PROJECT_STRUCTURE.md)

## Where New Code Should Go

- New graph state / node / rewrite / guard / postprocess logic:
  place under `amadeus_thread0/graph_parts/`
- Provider/runtime integration:
  place under `amadeus_thread0/runtime/`
- General-purpose helper or compatibility export:
  place under `amadeus_thread0/utils/`
- Authored local skill packages:
  place under `skills/<skill_id>/`
- Top-level files under `amadeus_thread0/` should stay thin and mostly serve as compatibility facades or domain entrypoints.

## High-Risk Zones

- `amadeus_thread0/graph_parts/nodes.py`
- `amadeus_thread0/graph_parts/rewrite.py`
- `amadeus_thread0/graph_parts/postprocess.py`
- `amadeus_thread0/graph_parts/autonomy_runtime.py`
- `amadeus_thread0/graph_parts/action_packets.py`
- `amadeus_thread0/graph_parts/browser_runtime.py`
- `amadeus_thread0/graph_parts/skill_runtime.py`
- `amadeus_thread0/runtime/browser_runner.py`
- `amadeus_thread0/runtime/skill_registry.py`
- `amadeus_thread0/runtime/sandbox_runner.py`
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

For skills-ecosystem edits, also run:

```powershell
python -m pytest tests/test_skill_registry.py tests/test_skill_runtime.py
python -m pytest tests/test_tooling_routing.py tests/test_tool_approval_policy.py
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

For `digital body / access / resource` closure edits, also verify:

```powershell
python evals/run_digital_embodiment_audit.py
```

For `sandbox embodied execution` edits, also verify:

```powershell
python -m pytest tests/test_sandbox_runner.py tests/test_sandbox_execution_runtime.py tests/test_sandbox_backend_contract.py
python -m pytest tests/test_sandbox_embodied_execution_smokes.py tests/test_sandbox_embodied_execution_audit.py
python evals/run_sandbox_embodied_execution_audit.py
```

For `live browser runtime` edits, also verify:

```powershell
python -m pytest tests/test_browser_runner.py tests/test_browser_runtime.py tests/test_browser_backend_contract.py
python -m pytest tests/test_live_browser_runtime_smokes.py tests/test_live_browser_runtime_audit.py
python evals/run_live_browser_runtime_smokes.py
python evals/run_live_browser_runtime_audit.py
```

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
