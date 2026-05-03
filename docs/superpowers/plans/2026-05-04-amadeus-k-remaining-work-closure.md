# Amadeus-K Remaining Work Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the remaining post-baseline gaps into an executable backend-first roadmap that preserves the closed persona/autonomy/body baselines while adding the next concrete capability layers.

**Architecture:** Treat the latest `program.md` and audit artifacts as the operational truth. Work in small baseline-preserving slices: first synchronize docs and validation, then improve operator readiness, then expand event/body perception, writeback coverage, presence behavior, procedural capability growth, contract handoff, and finally the deferred Chinese surface replacement track.

**Tech Stack:** Python 3, LangGraph/LangChain runtime already in `amadeus_thread0/`, pytest, existing `evals/` audit runners, existing CLI/BackendAPI envelopes, Docker sandbox phase 2, Playwright live browser runtime, markdown engineering docs.

---

## Execution Principles

- Do not reopen persona core or identity semantics. Evolution changes state, not identity.
- Do not split work memory from persona memory. New task, browser, sandbox, skill, and access traces must reconverge into the existing memory/writeback path.
- Do not widen execution authority. Docker sandbox phase 2 remains `python` / `pytest` / `rg` / read-only `git`, `network_policy=none`, no package managers, no shell wrappers, no Docker socket, no privileged containers.
- Do not resume frontend implementation while backend phases are active. Frontend work in this plan is contract-only unless a later explicit phase lifts the freeze.
- Do not start Chinese wording micro-polish as a mainline task until runtime/body/writeback contracts are stable and covered. The lexical replacement track is a separate research/eval phase.
- Before any code task, check `git status --short --branch` and avoid touching unrelated dirty files.
- After any code task touching graph/runtime/memory/tooling, run the validation set listed in the task and update `program.md`.

---

## Current Truth To Preserve

Treat these as preserved baselines unless a fresh audit proves otherwise:

- `freeze_gate_ready`
- `companion_autonomy_ready`
- `digital_embodiment_phase2_ready`
- `sandbox_embodied_execution_phase1_ready`
- `skills_ecosystem_ready`
- `live_browser_runtime_phase1_ready`
- `sandbox_embodied_execution_phase2_ready`

Latest high-signal artifacts:

- `evals/reports/digital-embodiment-audit-20260404-195802-phase2-closeout-c.md`
- `evals/reports/skills-ecosystem-audit-20260405-130706-closeout-fix-e.md`
- `evals/reports/live-browser-runtime-audit-20260503-203504-after-playwright-install-c.md`
- `evals/reports/sandbox-phase2-audit-20260503-203850-phase2-ready-c.md`

---

## File Ownership Map

Likely files to modify by phase:

- Status/docs synchronization:
  - `AGENTS.md`
  - `program.md`
  - `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
  - `docs/engineering/BACKEND_HANDOFF.md`
  - `docs/engineering/PROJECT_STRUCTURE.md`
  - `docs/DIGITAL_PERSONA_LIFEFORM_BLUEPRINT.md`
  - `docs/ARCHITECTURE_ALIGNMENT_MAP.md`

- Operator readiness and first-run UX:
  - `amadeus_thread0/cli.py`
  - `amadeus_thread0/runtime/modeling.py`
  - `amadeus_thread0/runtime/runtime_bundle.py`
  - `amadeus_thread0/utils/runtime_audit.py`
  - `README.md`
  - `requirements.txt`
  - `tests/test_cli_threading.py`
  - `tests/test_import_boundaries.py`
  - `tests/test_runtime_audit.py`

- Event and body observation:
  - `amadeus_thread0/graph_parts/perception.py`
  - `amadeus_thread0/graph_parts/session_context.py`
  - `amadeus_thread0/graph_parts/prepare_turn_context.py`
  - `amadeus_thread0/graph_parts/digital_body_runtime.py`
  - `amadeus_thread0/runtime/event_identity.py`
  - `tests/test_perception_event_contract.py`
  - `tests/test_session_context.py`
  - `tests/test_digital_body_runtime.py`

- Unified embodied writeback:
  - `amadeus_thread0/graph_parts/action_packets.py`
  - `amadeus_thread0/graph_parts/autonomy_runtime.py`
  - `amadeus_thread0/graph_parts/browser_runtime.py`
  - `amadeus_thread0/graph_parts/digital_body_runtime.py`
  - `amadeus_thread0/graph_parts/memory_evolution.py`
  - `amadeus_thread0/graph_parts/prepare_turn_runtime.py`
  - `amadeus_thread0/runtime/final_state.py`
  - `amadeus_thread0/utils/revision_trace_export.py`
  - `tests/test_autonomy_writeback.py`
  - `tests/test_world_model_residue.py`
  - `tests/test_backend_api.py`
  - `tests/test_backend_session.py`

- Presence and proactive behavior:
  - `amadeus_thread0/graph_parts/behavior_agenda.py`
  - `amadeus_thread0/graph_parts/behavior_runtime.py`
  - `amadeus_thread0/graph_parts/prepare_turn_runtime.py`
  - `amadeus_thread0/runtime/backend_session.py`
  - `tests/test_subjective_review_pack.py`
  - `tests/test_world_model_residue.py`
  - `tests/test_behavior_runtime_alignment.py`

- Procedural capability growth:
  - `amadeus_thread0/graph_parts/skill_runtime.py`
  - `amadeus_thread0/graph_parts/autonomy_runtime.py`
  - `amadeus_thread0/graph_parts/memory_evolution.py`
  - `amadeus_thread0/runtime/skill_registry.py`
  - `tests/test_skill_runtime.py`
  - `tests/test_skills_ecosystem_smokes.py`
  - `tests/test_autonomy_writeback.py`

- Contract handoff:
  - `docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md`
  - `docs/engineering/frontend_contract/backend_api.types.ts`
  - `docs/engineering/frontend_contract/mocks/*.json`
  - `tests/test_frontend_contract_sync.py`
  - `tests/test_backend_api.py`

- Chinese surface replacement track:
  - `amadeus_thread0/graph_parts/postprocess.py`
  - `amadeus_thread0/graph_parts/rewrite.py`
  - `evals/run_freeze_gate_smokes.py`
  - new: `evals/run_chinese_surface_de_scaffold_audit.py`
  - new: `evals/chinese_surface_residue_bank.json`
  - `tests/test_dialogue_mode_counterpart.py`
  - `tests/test_subjective_review_pack.py`

---

## Phase Order

Recommended order:

1. Baseline truth synchronization.
2. Operator readiness and first-run guardrails.
3. Body-state event perception.
4. Unified embodied writeback matrix.
5. Richer presence/proactive behavior.
6. Procedural capability growth.
7. Contract-only frontend handoff refresh.
8. Chinese lexical de-scaffolding research track.
9. Future multimodal/live-surface expansion.

Do not start Phase 8 before Phases 1-5 are green. Do not start Phase 9 before a separate product decision selects concrete modalities.

---

## Task 1: Baseline Truth Synchronization

**Goal:** Make all current docs agree that sandbox phase 2 is preserved/ready, while retaining the restrictions that made it safe.

**Files:**

- Modify: `AGENTS.md`
- Modify: `program.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `docs/engineering/BACKEND_HANDOFF.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/ARCHITECTURE_ALIGNMENT_MAP.md`

- [ ] **Step 1: Confirm latest readiness artifacts exist**

Run:

```powershell
Get-Item evals/reports/sandbox-phase2-audit-20260503-203850-phase2-ready-c.md
Get-Item evals/reports/live-browser-runtime-audit-20260503-203504-after-playwright-install-c.md
Get-Item evals/reports/skills-ecosystem-audit-20260405-130706-closeout-fix-e.md
Get-Item evals/reports/digital-embodiment-audit-20260404-195802-phase2-closeout-c.md
```

Expected:

- Each command returns a file object.
- No `Cannot find path` error.

- [ ] **Step 2: Locate stale phase wording**

Run:

```powershell
rg -n "sandbox_embodied_execution_phase2_in_progress|Sandbox Embodied Execution Phase 2.*in progress|current active backend expansion phase is `Sandbox Embodied Execution Phase 2`|active closeout target" AGENTS.md docs program.md
```

Expected:

- Every hit is reviewed.
- Hits that describe old status are updated.
- Hits that intentionally describe historical runs remain under dated run entries only.

- [ ] **Step 3: Update repository phase status**

Edit `AGENTS.md` and the listed docs so the current state reads:

```text
Sandbox Embodied Execution Phase 2 is closed and preserved as the current execution baseline.
```

Keep these restrictions in the same section:

```text
runner_kind=docker_isolated_runner
isolation_level=docker_local_isolated
network_policy=none
allowed commands: python, pytest, rg, read-only git
blocked: package install, shell wrappers, git mutation, Docker socket mounting, privileged containers, host secret passthrough
runtime-owned workspace by default
operator_attach_repo_root requires explicit approval
```

- [ ] **Step 4: Add a short status note for stale docs**

In `docs/ARCHITECTURE_ALIGNMENT_MAP.md`, add a short dated note near the top:

```markdown
Status note, 2026-05-04: this document preserves earlier architecture framing. For readiness truth, prefer `program.md` and the latest audit reports; sandbox embodied execution phase 2 is now ready/preserved.
```

- [ ] **Step 5: Run docs/status verification**

Run:

```powershell
rg -n "sandbox_embodied_execution_phase2_in_progress|Sandbox Embodied Execution Phase 2.*in progress|active closeout target" AGENTS.md docs/engineering docs/ARCHITECTURE_ALIGNMENT_MAP.md
```

Expected:

- No current-state hit remains.
- Historical report names or dated run entries may remain only outside the edited current-state sections.

- [ ] **Step 6: Commit**

Run:

```powershell
git status --short
git add AGENTS.md program.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md docs/engineering/BACKEND_HANDOFF.md docs/engineering/PROJECT_STRUCTURE.md docs/ARCHITECTURE_ALIGNMENT_MAP.md
git commit -m "docs: preserve sandbox phase 2 baseline"
```

Expected:

- Commit includes only docs and `program.md`.
- No generated sandbox run logs or unrelated deletions are staged.

---

## Task 2: Baseline Preservation Meta-Audit

**Goal:** Add one quick entrypoint that tells maintainers whether all preserved baselines are currently green without reading several audit reports by hand.

**Files:**

- Create: `evals/run_preserved_baselines_audit.py`
- Create: `tests/test_preserved_baselines_audit.py`
- Modify: `program.md`

- [ ] **Step 1: Write failing tests for report discovery**

Create `tests/test_preserved_baselines_audit.py` with tests for:

- finding the latest report by prefix
- extracting `overall_status`
- extracting readiness labels
- failing when any preserved baseline is not ready
- rendering a compact markdown table

Use fixture dictionaries, not real report files, for helper tests.

- [ ] **Step 2: Run the tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_preserved_baselines_audit.py -q
```

Expected:

- Fails because `evals/run_preserved_baselines_audit.py` does not exist.

- [ ] **Step 3: Implement pure helpers**

Create `evals/run_preserved_baselines_audit.py` with pure helper functions:

- `load_latest_report(report_dir: Path, prefix: str) -> dict`
- `status_from_report(report: dict) -> dict`
- `evaluate_preserved_baselines(statuses: dict[str, dict]) -> dict`
- `render_markdown(summary: dict) -> str`

Required baseline prefixes:

```python
BASELINES = {
    "digital_embodiment": "digital-embodiment-audit-",
    "skills_ecosystem": "skills-ecosystem-audit-",
    "live_browser_runtime": "live-browser-runtime-audit-",
    "sandbox_phase2": "sandbox-phase2-audit-",
}
```

Expected readiness values:

```python
EXPECTED_READY = {
    "digital_embodiment": "digital_embodiment_phase2_ready",
    "skills_ecosystem": "skills_ecosystem_ready",
    "live_browser_runtime": "live_browser_runtime_phase1_ready",
    "sandbox_phase2": "sandbox_embodied_execution_phase2_ready",
}
```

- [ ] **Step 4: Add CLI behavior**

The script should support:

```powershell
python evals/run_preserved_baselines_audit.py
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
```

It should write:

- `evals/reports/preserved-baselines-audit-<timestamp>.json`
- `evals/reports/preserved-baselines-audit-<timestamp>.md`

Exit code:

- `0` when all expected readiness values are present and each latest report has `overall_status=passed`
- `1` otherwise

- [ ] **Step 5: Run focused tests**

Run:

```powershell
python -m pytest tests/test_preserved_baselines_audit.py -q
```

Expected:

- All tests pass.

- [ ] **Step 6: Run the new audit**

Run:

```powershell
python evals/run_preserved_baselines_audit.py
```

Expected:

- Overall status is `passed`.
- Markdown includes the four preserved report families and the expected readiness labels.

- [ ] **Step 7: Commit**

Run:

```powershell
git add evals/run_preserved_baselines_audit.py tests/test_preserved_baselines_audit.py program.md
git commit -m "test: add preserved baseline audit"
```

Expected:

- Generated reports are not committed unless the repository convention for eval reports explicitly requires that run artifact.

---

## Task 3: Operator Readiness And First-Run UX

**Goal:** Make first-run failures impossible to miss and easy to recover from before the graph imports heavy runtime modules.

**Files:**

- Modify: `amadeus_thread0/cli.py`
- Modify: `amadeus_thread0/runtime/modeling.py`
- Modify: `amadeus_thread0/utils/runtime_audit.py`
- Modify: `README.md`
- Modify: `tests/test_cli_threading.py`
- Modify: `tests/test_import_boundaries.py`
- Modify: `tests/test_runtime_audit.py`
- Modify: `program.md`

- [ ] **Step 1: Add tests for machine-readable doctor**

Extend `tests/test_runtime_audit.py` to assert the doctor report includes:

- `overall_status`
- `python`
- `dependencies`
- `pip_check`
- `env`
- `model_key`
- `playwright`
- `docker`
- `phase_readiness`
- `remediation`

Expected remediation examples:

```json
{
  "missing_package": "langgraph-checkpoint-sqlite",
  "install_hint": "python -m pip install -r requirements.txt"
}
```

- [ ] **Step 2: Add tests for CLI flags**

Extend `tests/test_cli_threading.py` to cover:

```powershell
python -m amadeus_thread0.cli --doctor --json
python -m amadeus_thread0.cli --doctor --phase sandbox_phase2
```

Expected:

- `--doctor --json` prints valid JSON.
- `--doctor --phase sandbox_phase2` reports Docker/image/network policy readiness.

- [ ] **Step 3: Run the focused tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_runtime_audit.py tests/test_cli_threading.py -q
```

Expected:

- Fails for missing fields or missing CLI flags.

- [ ] **Step 4: Implement phase-aware runtime audit fields**

Update `amadeus_thread0/utils/runtime_audit.py` so the returned dictionary contains:

```python
{
    "overall_status": "passed" | "failed",
    "dependencies": [...],
    "pip_check": {"status": "ok" | "failed", "details": "..."},
    "env": {"dotenv_loaded": bool, "model_key": "set" | "missing"},
    "phase_readiness": {
        "graph": "ready" | "blocked",
        "live_browser": "ready" | "blocked",
        "sandbox_phase2": "ready" | "blocked"
    },
    "remediation": [...]
}
```

- [ ] **Step 5: Implement CLI rendering**

Update `amadeus_thread0/cli.py`:

- `--doctor` keeps human-readable output.
- `--doctor --json` prints only JSON.
- `--doctor --phase sandbox_phase2` narrows output to that phase plus global blockers.
- normal CLI start should warn when doctor has blocking graph dependencies before starting the graph.

- [ ] **Step 6: Update README**

Add a "First Run Check" section:

```powershell
python -m amadeus_thread0.cli --doctor
python -m amadeus_thread0.cli --doctor --json
python -m amadeus_thread0.cli --fresh-thread --fresh-thread-prefix smoke
```

Explain that `--doctor` must pass before judging product behavior.

- [ ] **Step 7: Run validation**

Run:

```powershell
python -m amadeus_thread0.cli --doctor
python -m amadeus_thread0.cli --doctor --json
python -m pytest tests/test_import_boundaries.py tests/test_cli_threading.py tests/test_runtime_audit.py -q
```

Expected:

- Doctor commands pass.
- Tests pass.
- JSON output parses without extra prose.

- [ ] **Step 8: Commit**

Run:

```powershell
git add amadeus_thread0/cli.py amadeus_thread0/utils/runtime_audit.py amadeus_thread0/runtime/modeling.py README.md tests/test_cli_threading.py tests/test_import_boundaries.py tests/test_runtime_audit.py program.md
git commit -m "feat: make runtime doctor phase aware"
```

---

## Task 4: Body-State Event Perception

**Goal:** Promote browser/session/sandbox/skill/workspace observations into first-class perception context, not just passive runtime metadata.

**Files:**

- Modify: `amadeus_thread0/graph_parts/perception.py`
- Modify: `amadeus_thread0/graph_parts/session_context.py`
- Modify: `amadeus_thread0/graph_parts/prepare_turn_context.py`
- Modify: `amadeus_thread0/graph_parts/digital_body_runtime.py`
- Modify: `amadeus_thread0/runtime/event_identity.py`
- Modify: `tests/test_perception_event_contract.py`
- Modify: `tests/test_session_context.py`
- Modify: `tests/test_digital_body_runtime.py`
- Modify: `program.md`

- [ ] **Step 1: Add failing perception tests**

Add cases to `tests/test_perception_event_contract.py`:

- `browser_runtime_observation` keeps `modality=browser`, `source_role=environment`, `digital_body_hints.browser_runtime_state`
- `sandbox_run_observation` keeps `modality=sandbox`, `source_role=environment`, `digital_body_hints.sandbox_state`
- `skill_usage_observation` keeps `modality=skill`, `source_role=capability`, `digital_body_hints.skill_effects`
- `audio_observation` keeps `modality=audio`, `channel=voice`, `trust_tier=medium`
- `vision_observation` keeps `modality=vision`, `channel=vision`, `trust_tier=medium`

- [ ] **Step 2: Run perception tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_perception_event_contract.py -q
```

Expected:

- New event kinds are not normalized correctly yet.

- [ ] **Step 3: Extend channel/modality/source-role normalization**

Update `amadeus_thread0/graph_parts/perception.py`:

- `_channel_from_source()` recognizes `browser`, `sandbox`, `skill`, `audio`, `voice`, `vision`
- `_modality_from_event()` recognizes event kinds:
  - `browser_runtime_observation`
  - `sandbox_run_observation`
  - `skill_usage_observation`
  - `audio_observation`
  - `vision_observation`
  - `body_resource_observation`
- `_source_role()` maps environment/runtime observations to `environment`
- `_delivery_mode()` maps runtime observations to `ambient` or `external`
- `_trust_tier()` keeps runtime observations `medium` unless explicitly high-trust system events

- [ ] **Step 4: Preserve digital body hints through session context**

Update `amadeus_thread0/graph_parts/session_context.py` and `prepare_turn_context.py` so `current_event.perception.digital_body_hints` can seed `session_context.digital_body_hints` without replacing existing completed body truth.

Rules:

- event hints may refresh missing fields
- event hints may not overwrite completed packet result truth
- event hints may not turn pending/rejected access into owned capability

- [ ] **Step 5: Preserve readback identity**

Update `amadeus_thread0/runtime/event_identity.py` so backend readback surfaces still expose the event's body-observation metadata.

- [ ] **Step 6: Run validation**

Run:

```powershell
python -m pytest tests/test_perception_event_contract.py tests/test_session_context.py tests/test_digital_body_runtime.py -q
python -m pytest tests/test_backend_session.py tests/test_backend_api.py -q
```

Expected:

- Perception tests pass.
- Backend envelopes expose the same event identity and body hints.

- [ ] **Step 7: Commit**

Run:

```powershell
git add amadeus_thread0/graph_parts/perception.py amadeus_thread0/graph_parts/session_context.py amadeus_thread0/graph_parts/prepare_turn_context.py amadeus_thread0/graph_parts/digital_body_runtime.py amadeus_thread0/runtime/event_identity.py tests/test_perception_event_contract.py tests/test_session_context.py tests/test_digital_body_runtime.py program.md
git commit -m "feat: treat body observations as perception events"
```

---

## Task 5: Unified Embodied Writeback Matrix

**Goal:** Ensure every completed world interaction family writes one truthful embodied consequence and resurfaces through later continuity.

**Files:**

- Create: `evals/run_embodied_writeback_matrix_audit.py`
- Create: `tests/test_embodied_writeback_matrix_audit.py`
- Modify: `amadeus_thread0/graph_parts/action_packets.py`
- Modify: `amadeus_thread0/graph_parts/autonomy_runtime.py`
- Modify: `amadeus_thread0/graph_parts/digital_body_runtime.py`
- Modify: `amadeus_thread0/graph_parts/memory_evolution.py`
- Modify: `amadeus_thread0/graph_parts/prepare_turn_runtime.py`
- Modify: `amadeus_thread0/runtime/final_state.py`
- Modify: `amadeus_thread0/utils/revision_trace_export.py`
- Modify: `tests/test_autonomy_writeback.py`
- Modify: `tests/test_world_model_residue.py`
- Modify: `tests/test_backend_session.py`
- Modify: `tests/test_backend_api.py`
- Modify: `program.md`

- [ ] **Step 1: Define the matrix**

The matrix must cover these completed consequence families:

- `workspace_path_inspected`
- `workspace_file_updated`
- `source_material_inspected`
- `source_material_compared`
- `artifact_reacquired`
- `access_state_refreshed`
- `workspace_root_attached`
- `sandbox_execution_completed`
- `sandbox_execution_blocked`
- `browser_navigation_completed`
- `browser_interaction_completed`
- `browser_download_completed`
- `browser_upload_completed`
- `browser_takeover_requested`
- `browser_action_blocked`
- `skill_usage_completed`
- `skill_mutation_blocked`

- [ ] **Step 2: Add failing tests**

Extend `tests/test_autonomy_writeback.py` and `tests/test_world_model_residue.py` so each matrix row asserts:

- completed packet appears in final `autonomy.action_packets`
- `digital_body_consequence.kind` matches the completed family
- `interaction_carryover.embodied_context` preserves carrier/run/profile/workspace/source identity
- `reconsolidation_snapshot` carries the same embodied truth
- later retrieval can resurface the trace without inventing capability

- [ ] **Step 3: Run focused tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_autonomy_writeback.py tests/test_world_model_residue.py -k "embodied or sandbox or browser or skill or source or workspace" -q
```

Expected:

- At least one matrix family fails, proving coverage was missing or inconsistent.

- [ ] **Step 4: Normalize consequence shaping**

Update graph/runtime helpers so every completed result family flows through one normalization path before writeback:

- packet result truth wins
- live state synthesis is fallback only
- blocked/pending/rejected packets never become completed facts
- `run_id`, `cwd`, `profile`, `exit_code`, `workspace_root`, `artifact_carrier`, `source_ref_ids`, `browser_profile_id`, `browser_tab_id`, `skill_effects`, and `network_policy` are preserved when present

- [ ] **Step 5: Add matrix audit runner**

Create `evals/run_embodied_writeback_matrix_audit.py`.

It should run:

```powershell
python -m pytest tests/test_autonomy_writeback.py tests/test_world_model_residue.py -k "embodied or sandbox or browser or skill or source or workspace" -q
python -m pytest tests/test_backend_session.py tests/test_backend_api.py -k "embodied or sandbox or browser or skill or source or workspace" -q
```

It should write:

- `evals/reports/embodied-writeback-matrix-audit-<timestamp>.json`
- `evals/reports/embodied-writeback-matrix-audit-<timestamp>.md`

- [ ] **Step 6: Run validation**

Run:

```powershell
python -m pytest tests/test_embodied_writeback_matrix_audit.py -q
python evals/run_embodied_writeback_matrix_audit.py
python evals/run_digital_embodiment_audit.py
python evals/run_sandbox_phase2_audit.py
```

Expected:

- New audit passes.
- Existing digital embodiment and sandbox phase 2 readiness remain ready.

- [ ] **Step 7: Commit**

Run:

```powershell
git add evals/run_embodied_writeback_matrix_audit.py tests/test_embodied_writeback_matrix_audit.py amadeus_thread0/graph_parts/action_packets.py amadeus_thread0/graph_parts/autonomy_runtime.py amadeus_thread0/graph_parts/digital_body_runtime.py amadeus_thread0/graph_parts/memory_evolution.py amadeus_thread0/graph_parts/prepare_turn_runtime.py amadeus_thread0/runtime/final_state.py amadeus_thread0/utils/revision_trace_export.py tests/test_autonomy_writeback.py tests/test_world_model_residue.py tests/test_backend_session.py tests/test_backend_api.py program.md
git commit -m "test: close embodied writeback matrix"
```

---

## Task 6: Richer Presence And Proactive Behavior Families

**Goal:** Expand behavior beyond reply text and generic check-ins while keeping final-turn semantics singular.

**Files:**

- Modify: `amadeus_thread0/graph_parts/behavior_agenda.py`
- Modify: `amadeus_thread0/graph_parts/behavior_runtime.py`
- Modify: `amadeus_thread0/graph_parts/prepare_turn_runtime.py`
- Modify: `amadeus_thread0/runtime/final_state.py`
- Modify: `amadeus_thread0/runtime/backend_session.py`
- Modify: `tests/test_behavior_runtime_alignment.py`
- Modify: `tests/test_subjective_review_pack.py`
- Modify: `tests/test_world_model_residue.py`
- Modify: `program.md`

- [ ] **Step 1: Define presence behavior families**

Add tests for these behavior plan families:

- `quiet_presence`
- `ambient_echo`
- `deferred_return`
- `boundary_hold`
- `repair_probe`
- `shared_work_nudge`
- `self_activity_continue`

Each family must resolve into:

- `behavior_action`
- `behavior_plan`
- `turn_summary`
- `reconsolidation_snapshot`

with the same `interaction_mode`, `attention_target`, `timing_window_min`, and `final_text` semantics.

- [ ] **Step 2: Run behavior tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_behavior_runtime_alignment.py tests/test_subjective_review_pack.py tests/test_world_model_residue.py -k "presence or proactive or rhythm or boundary or repair" -q
```

Expected:

- Missing or inconsistent families fail.

- [ ] **Step 3: Extend agenda selection**

Update `behavior_agenda.py` so agenda maturity can select the new families from:

- `counterpart_assessment`
- `world_model_state`
- `semantic_narrative_profile`
- `digital_body_state`
- existing `behavior_queue`

Rules:

- guarded counterpart state may hold or soften contact
- open counterpart state may allow low-pressure re-entry
- completed embodied context can influence topic continuity
- no family should force speech if silence/hold is the better behavior

- [ ] **Step 4: Extend behavior runtime/final-state readback**

Update `behavior_runtime.py`, `prepare_turn_runtime.py`, and `runtime/final_state.py` so the new fields survive:

- `presence_family`
- `attention_target`
- `nonverbal_signal`
- `timing_window_min`
- `allow_interrupt`
- `silence_allowed`
- `embodied_context`

- [ ] **Step 5: Run validation**

Run:

```powershell
python -m pytest tests/test_behavior_runtime_alignment.py tests/test_subjective_review_pack.py tests/test_world_model_residue.py -k "presence or proactive or rhythm or boundary or repair" -q
python -m pytest tests/test_daily_surface_gating.py tests/test_dialogue_mode_counterpart.py tests/test_generation_profile.py -q
```

Expected:

- New presence families pass.
- Existing daily/dialogue/generation gates remain green.

- [ ] **Step 6: Commit**

Run:

```powershell
git add amadeus_thread0/graph_parts/behavior_agenda.py amadeus_thread0/graph_parts/behavior_runtime.py amadeus_thread0/graph_parts/prepare_turn_runtime.py amadeus_thread0/runtime/final_state.py amadeus_thread0/runtime/backend_session.py tests/test_behavior_runtime_alignment.py tests/test_subjective_review_pack.py tests/test_world_model_residue.py program.md
git commit -m "feat: expand presence behavior families"
```

---

## Task 7: Procedural Capability Growth Without Persona Drift

**Goal:** Let completed skill/browser/sandbox/workspace usage consolidate into procedural continuity without turning skills or tools into persona identity.

**Files:**

- Modify: `amadeus_thread0/graph_parts/skill_runtime.py`
- Modify: `amadeus_thread0/graph_parts/autonomy_runtime.py`
- Modify: `amadeus_thread0/graph_parts/memory_evolution.py`
- Modify: `amadeus_thread0/graph_parts/digital_body_runtime.py`
- Modify: `amadeus_thread0/runtime/skill_registry.py`
- Modify: `tests/test_skill_runtime.py`
- Modify: `tests/test_skills_ecosystem_smokes.py`
- Modify: `tests/test_autonomy_writeback.py`
- Modify: `tests/test_world_model_residue.py`
- Modify: `program.md`

- [ ] **Step 1: Add tests for procedural continuity traces**

Add tests asserting:

- completed skill use may write `procedural_continuity`
- completed sandbox/browser/workspace patterns may write `procedural_continuity`
- installed skill registry truth does not enter autobiographical memory
- rejected/pending skill mutation does not become a capability fact
- repeated successful usage can bias future action selection without changing persona core

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_skill_runtime.py tests/test_autonomy_writeback.py tests/test_world_model_residue.py -k "procedural or skill_effects or capability" -q
```

Expected:

- Missing procedural continuity tests fail.

- [ ] **Step 3: Add procedural continuity shaping**

Update final writeback logic so completed effects can carry:

```python
{
    "procedural_continuity": {
        "capability_family": "skill" | "sandbox" | "browser" | "workspace",
        "pattern": "...",
        "confidence": 0.0,
        "evidence_count": 1,
        "last_success_ref": "...",
        "identity_safe": True
    }
}
```

Rules:

- `identity_safe` must always be `True` for writeback to proceed.
- This object is a procedural/body trace, not a persona-core override.
- Confidence only rises from completed action results.

- [ ] **Step 4: Add future action bias**

Update `autonomy_runtime.py` to let retrieved procedural continuity bias action choice when:

- the current request matches the same bounded capability family
- the required approval policy still applies
- the retrieved trace does not claim broader access than current `digital_body.access_state`

- [ ] **Step 5: Run validation**

Run:

```powershell
python -m pytest tests/test_skill_registry.py tests/test_skill_runtime.py -q
python -m pytest tests/test_skills_ecosystem_smokes.py tests/test_skills_ecosystem_audit.py -q
python -m pytest tests/test_autonomy_writeback.py tests/test_world_model_residue.py -k "procedural or skill_effects or capability" -q
python evals/run_skills_ecosystem_audit.py
```

Expected:

- Skills ecosystem remains ready.
- Procedural continuity appears only for completed effects.

- [ ] **Step 6: Commit**

Run:

```powershell
git add amadeus_thread0/graph_parts/skill_runtime.py amadeus_thread0/graph_parts/autonomy_runtime.py amadeus_thread0/graph_parts/memory_evolution.py amadeus_thread0/graph_parts/digital_body_runtime.py amadeus_thread0/runtime/skill_registry.py tests/test_skill_runtime.py tests/test_skills_ecosystem_smokes.py tests/test_autonomy_writeback.py tests/test_world_model_residue.py program.md
git commit -m "feat: consolidate procedural capability traces"
```

---

## Task 8: Contract-Only Frontend Handoff Refresh

**Goal:** Keep frontend consumers aligned with backend envelopes without resuming frontend UI work.

**Files:**

- Modify: `docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md`
- Modify: `docs/engineering/BACKEND_HANDOFF.md`
- Modify: `docs/engineering/frontend_contract/backend_api.types.ts`
- Modify: `docs/engineering/frontend_contract/mocks/assistant_turn.json`
- Modify: `docs/engineering/frontend_contract/mocks/event_round.json`
- Modify: `docs/engineering/frontend_contract/mocks/persona_view.json`
- Modify: `docs/engineering/frontend_contract/mocks/worldline_view.json`
- Modify: `docs/engineering/frontend_contract/mocks/bond_view.json`
- Modify: `tests/test_frontend_contract_sync.py`
- Modify: `program.md`

- [ ] **Step 1: Decide frozen frontend directory state**

Run:

```powershell
git status --short -- frontend
```

Expected:

- If `frontend/` is intentionally frozen-but-removed, document that in `PROJECT_STRUCTURE.md`.
- If `frontend/` must remain as a frozen shell, restore it in a separate cleanup commit before this task.

Do not mix frontend restoration/deletion with contract schema edits.

- [ ] **Step 2: Add contract sync tests**

Update `tests/test_frontend_contract_sync.py` so mocks assert presence of:

- `autonomy.intent`
- `autonomy.action_packets`
- `autonomy.pending_approval`
- `skills.active`
- `skills.pending_approval`
- `digital_body.access_state.sandbox_state`
- `digital_body.access_state.browser_runtime_state`
- `digital_body.resource_state`
- `digital_body_consequence`
- `interaction_carryover.embodied_context`
- phase-2 fields: `runner_kind`, `isolation_level`, `image_ref`, `network_policy`, `workspace_root_kind`

- [ ] **Step 3: Run contract test and confirm failure**

Run:

```powershell
python -m pytest tests/test_frontend_contract_sync.py -q
```

Expected:

- Fails if mocks/types do not carry all current backend fields.

- [ ] **Step 4: Refresh TypeScript types and mocks**

Update `backend_api.types.ts` and the mock JSON files from stable backend envelope examples.

Rules:

- Do not invent frontend-only semantics.
- Do not import backend internals into frontend contract docs.
- Treat action packet execution hints as backend-owned details.

- [ ] **Step 5: Run validation**

Run:

```powershell
python -m pytest tests/test_frontend_contract_sync.py tests/test_backend_api.py tests/test_backend_session.py -q
```

Expected:

- Contract sync passes.
- Backend session/API tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md docs/engineering/BACKEND_HANDOFF.md docs/engineering/frontend_contract/backend_api.types.ts docs/engineering/frontend_contract/mocks tests/test_frontend_contract_sync.py program.md
git commit -m "docs: refresh frontend backend contract"
```

---

## Task 9: Chinese Lexical De-Scaffolding Research Track

**Goal:** Start replacing brittle Chinese surface heuristics with auditable semantic diagnostics without destabilizing runtime behavior.

**Files:**

- Create: `evals/chinese_surface_residue_bank.json`
- Create: `evals/run_chinese_surface_de_scaffold_audit.py`
- Create: `tests/test_chinese_surface_de_scaffold_audit.py`
- Modify: `amadeus_thread0/graph_parts/postprocess.py`
- Modify: `amadeus_thread0/graph_parts/rewrite.py`
- Modify: `tests/test_subjective_review_pack.py`
- Modify: `tests/test_dialogue_mode_counterpart.py`
- Modify: `program.md`

- [ ] **Step 1: Freeze a residue bank**

Create `evals/chinese_surface_residue_bank.json` with categories:

- `teacherly_scold`
- `meta_persona_proof`
- `generic_assistant_tone`
- `hardline_autonomy_overreach`
- `scene_script residue`
- `taskization_of_daily_chat`
- `repair_scorekeeping`
- `boundary_threat_excess`

Each entry must include:

```json
{
  "id": "teacherly_scold_001",
  "input_context": "guarded repair followup",
  "bad_surface": "你能意识到并特意回来说明，这点还算值得肯定",
  "reason": "sounds like teacherly scoring instead of lived relational response",
  "target_semantic": "ordinary guarded acknowledgement without scoring"
}
```

- [ ] **Step 2: Add audit tests**

Create `tests/test_chinese_surface_de_scaffold_audit.py`.

Test that the audit:

- loads every residue item
- detects legacy surface families
- reports category counts
- fails if a required category has no examples
- does not require a live model call

- [ ] **Step 3: Run audit tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_chinese_surface_de_scaffold_audit.py -q
```

Expected:

- Fails until the audit runner exists.

- [ ] **Step 4: Implement offline audit runner**

Create `evals/run_chinese_surface_de_scaffold_audit.py`.

It should:

- load `evals/chinese_surface_residue_bank.json`
- run current postprocess/rewrite diagnostics on `bad_surface`
- write category pass/fail stats
- not mutate runtime behavior
- emit:
  - `evals/reports/chinese-surface-de-scaffold-audit-<timestamp>.json`
  - `evals/reports/chinese-surface-de-scaffold-audit-<timestamp>.md`

- [ ] **Step 5: Introduce semantic diagnostics behind existing behavior**

Only after the audit exists, add small semantic helper functions to `postprocess.py` or `rewrite.py` that classify residue families by meaning rather than exact lexical string.

Rules:

- Do not remove existing lexical guards in the first pass.
- Use semantic diagnostics for reporting and candidate scoring first.
- Remove lexical heuristics only in a later commit when audit evidence shows equivalent coverage.

- [ ] **Step 6: Run validation**

Run:

```powershell
python -m pytest tests/test_chinese_surface_de_scaffold_audit.py -q
python evals/run_chinese_surface_de_scaffold_audit.py
python -m pytest tests/test_subjective_review_pack.py tests/test_dialogue_mode_counterpart.py -q
python evals/run_backend_freeze_gate_audit.py
```

Expected:

- New audit passes.
- Existing dialogue/freeze gates remain ready.

- [ ] **Step 7: Commit**

Run:

```powershell
git add evals/chinese_surface_residue_bank.json evals/run_chinese_surface_de_scaffold_audit.py tests/test_chinese_surface_de_scaffold_audit.py amadeus_thread0/graph_parts/postprocess.py amadeus_thread0/graph_parts/rewrite.py tests/test_subjective_review_pack.py tests/test_dialogue_mode_counterpart.py program.md
git commit -m "test: add chinese surface de-scaffolding audit"
```

---

## Task 10: Future Multimodal And Live-Surface Expansion Spec

**Goal:** Decide the next actual modality before implementing it. This is intentionally a spec task, not a coding task.

**Files:**

- Create: `docs/engineering/MULTIMODAL_BODY_EXPANSION_SPEC.md`
- Modify: `program.md`

- [ ] **Step 1: Choose one next modality**

Pick exactly one:

- `audio_input`
- `image_observation`
- `screen_observation`
- `live_browser_plus_capture`
- `TTS_presence_timing`

Do not implement all at once.

- [ ] **Step 2: Write the spec**

Create `docs/engineering/MULTIMODAL_BODY_EXPANSION_SPEC.md` with:

- chosen modality
- input event contract
- trust tier
- access/privacy boundary
- digital body state fields
- writeback policy
- approval policy
- CLI/backend envelope fields
- evaluation pack

- [ ] **Step 3: Add validation checklist**

The spec must define commands for the future implementation, for example:

```powershell
python -m pytest tests/test_perception_event_contract.py tests/test_backend_api.py tests/test_world_model_residue.py -q
python evals/run_digital_embodiment_audit.py
```

- [ ] **Step 4: Commit**

Run:

```powershell
git add docs/engineering/MULTIMODAL_BODY_EXPANSION_SPEC.md program.md
git commit -m "docs: specify next multimodal body slice"
```

---

## Full Regression Checkpoints

Run after Task 1 or docs-only changes:

```powershell
python evals/run_preserved_baselines_audit.py
```

Run after graph-layer changes:

```powershell
python -m pytest tests/test_daily_surface_gating.py
python -m pytest tests/test_generation_profile.py
python -m pytest tests/test_dialogue_mode_counterpart.py
python -m pytest tests/test_world_model_residue.py
python -m pytest tests/test_subjective_review_pack.py
python -m pytest tests/test_companion_autonomy_runtime.py
python -m pytest tests/test_autonomy_writeback.py
```

Run after memory/tool-path changes:

```powershell
python -m pytest tests/test_memory_guard.py
python -m pytest tests/test_session_orchestrator.py
python -m pytest tests/test_cli_views.py
python -m pytest tests/test_backend_session.py tests/test_backend_api.py tests/test_tool_approval_policy.py
```

Run after skills changes:

```powershell
python -m pytest tests/test_skill_registry.py tests/test_skill_runtime.py
python -m pytest tests/test_tooling_routing.py tests/test_tool_approval_policy.py
python evals/run_skills_ecosystem_audit.py
```

Run after browser changes:

```powershell
python -m pytest tests/test_browser_runner.py tests/test_browser_runtime.py tests/test_browser_backend_contract.py
python -m pytest tests/test_live_browser_runtime_smokes.py tests/test_live_browser_runtime_audit.py
python evals/run_live_browser_runtime_smokes.py
python evals/run_live_browser_runtime_audit.py
```

Run after sandbox changes:

```powershell
python -m pytest tests/test_sandbox_runner.py tests/test_docker_sandbox_runner.py tests/test_sandbox_execution_runtime.py tests/test_sandbox_backend_contract.py tests/test_sandbox_phase2_backend_contract.py tests/test_sandbox_phase2_repo_fixture.py -q
python -m pytest tests/test_sandbox_phase2_smokes.py -q
python evals/run_sandbox_phase2_smokes.py --run-tag fresh-check
python evals/run_sandbox_phase2_audit.py --run-tag fresh-check
```

Run before claiming completion of a phase:

```powershell
python -m amadeus_thread0.cli --doctor
python -m py_compile amadeus_thread0/agent.py amadeus_thread0/graph.py
@'
from amadeus_thread0.agent import agent
print(type(agent).__name__)
'@ | python -
python evals/run_backend_freeze_gate_audit.py
python evals/run_companion_autonomy_audit.py
python evals/run_digital_embodiment_audit.py
python evals/run_skills_ecosystem_audit.py
python evals/run_live_browser_runtime_audit.py
python evals/run_sandbox_phase2_audit.py
```

Expected:

- Doctor passes.
- Graph build prints `CompiledStateGraph`.
- Preserved audits remain ready.

---

## Backlog Items That Are Explicitly Deferred

Do not implement these until the above phases are stable and a separate plan exists:

- New desktop UI or full frontend rebuild.
- Arbitrary host shell execution.
- Network-enabled Docker sandbox commands.
- Package install inside sandbox packets.
- Dynamic skill generation that writes new executable host code.
- Autonomous account registration without explicit operator approval and a bounded runtime contract.
- Credential guessing, OTP simulation, CAPTCHA bypass, cookie forgery, or browser profile reuse outside the isolated runtime profile.
- Broad Chinese wording rewrite without an audit-backed semantic replacement path.
- Multi-modal ingestion of arbitrary camera/microphone/screen data without an explicit privacy/access contract.

---

## Suggested Milestone Commits

1. `docs: preserve sandbox phase 2 baseline`
2. `test: add preserved baseline audit`
3. `feat: make runtime doctor phase aware`
4. `feat: treat body observations as perception events`
5. `test: close embodied writeback matrix`
6. `feat: expand presence behavior families`
7. `feat: consolidate procedural capability traces`
8. `docs: refresh frontend backend contract`
9. `test: add chinese surface de-scaffolding audit`
10. `docs: specify next multimodal body slice`

---

## Success Definition

This remaining-work plan is complete when:

- all docs and ledgers agree on the preserved baseline state
- a single preserved-baselines audit reports green
- first-run readiness is phase-aware and machine-readable
- body/resource observations enter perception as first-class events
- every completed embodied action family writes back and resurfaces through one continuity path
- proactive behavior exposes richer presence families without forcing speech
- procedural capability growth exists as embodied continuity, not persona identity
- frontend handoff artifacts match current backend envelopes
- Chinese surface replacement has an offline audit track before any broad rewrite
- the next multimodal/body expansion is specified as one bounded slice
