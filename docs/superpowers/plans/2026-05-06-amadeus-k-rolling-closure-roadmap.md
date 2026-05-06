# Amadeus-K Rolling Closure Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining unlocked Amadeus-K backend lanes as one rolling sequence of bounded, audited phases that preserve all established persona, memory, body, sandbox, browser, skills, and backend contract baselines.

**Architecture:** Each phase gets its own isolated git worktree, detailed implementation plan, RED/GREEN tests, deterministic audit, documentation update, fast-forward merge to `main`, post-merge verification, and push before the next phase starts. The sequence favors the north-star loop first: make existing perception/appraisal/motive evidence causally visible to behavior readback, then upgrade loop realism, Chinese semantic policy, multimodal inspection, dynamic skill installation, and finally frontend contract consumption.

**Tech Stack:** Python 3, pytest, deterministic `evals/` audit scripts, LangGraph backend payload surfaces, repo-local git worktrees, existing `backend.v1` envelopes.

---

## Rolling Rules

- Work only from isolated branches named with the `codex/` prefix.
- Use E-drive worktrees because C-drive free space is low.
- Keep the existing untracked `third_party/benchmarks/ESConv` directory untouched.
- Before each phase, write or refresh the phase-specific detailed plan under `docs/superpowers/plans/`.
- For production behavior changes, write tests first and watch them fail before implementation.
- Each phase must preserve these blocked surfaces unless the phase-specific plan explicitly closes a new audited gate:
  - no persona-core mutation
  - no second memory substrate
  - no unapproved memory writes
  - no live microphone/camera/background screen capture
  - no multimodal model API call unless the multimodal phase explicitly creates an approval-gated packet and audit gate
  - no unapproved browser/tool/sandbox/external mutation
  - no automatic skill registry mutation
  - no frontend-owned backend semantics
- Do not proceed to the next phase until:
  - focused pytest passes
  - phase audit reports the phase readiness value
  - preserved-baseline audit passes on `main`
  - branch is merged to `main`
  - `main` is pushed

---

## Phase 1: Embodied Interaction Runtime Phase 5

**Readiness:** `embodied_interaction_runtime_phase5_ready`

**Purpose:** Connect Phase 4 `artifact_motive.motive_hints` to behavior-plan/behavior-action readback through an audit-only alignment layer.

**Core Files:**

- Create `amadeus_thread0/runtime/artifact_behavior_alignment.py`
- Modify `amadeus_thread0/runtime/embodied_interaction_runtime.py`
- Create `tests/test_artifact_behavior_alignment.py`
- Modify `tests/test_embodied_interaction_runtime.py`
- Modify `tests/test_backend_api.py`
- Create `evals/run_embodied_interaction_runtime_phase5_audit.py`
- Create `tests/test_embodied_interaction_runtime_phase5_audit.py`
- Modify `evals/run_embodied_interaction_runtime_phase4_audit.py`
- Modify `evals/run_preserved_baselines_audit.py`
- Modify `tests/test_preserved_baselines_audit.py`
- Update `AGENTS.md`, `docs/engineering/PROJECT_STRUCTURE.md`, `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`, and `program.md`

**Executable Steps:**

- [x] Write `tests/test_artifact_behavior_alignment.py` proving aligned, not-reflected, empty/blocked, and inadmissible cases.
- [x] Run the new unit test and verify RED because `artifact_behavior_alignment` does not exist.
- [x] Implement `build_artifact_behavior_alignment_readback()`.
- [x] Run the unit test and verify GREEN.
- [x] Add integration/backend tests proving alignment is attached without changing `behavior_action.primary_motive` or `behavior_plan.primary_motive`.
- [x] Run selected integration/backend tests and verify RED.
- [x] Attach alignment readback to `embodied_interaction_runtime.py`.
- [x] Run selected integration/backend tests and verify GREEN.
- [x] Add Phase 5 audit and update preserved-baseline metadata.
- [x] Run audit tests and the Phase 5 audit.
- [x] Update docs and ledger.
- [ ] Run final Phase 5 verification, merge to `main`, run post-merge verification, push.

---

## Phase 2: Living Loop Runtime Realism Phase 3

**Readiness:** `living_loop_runtime_realism_phase3_ready`

**Purpose:** Teach `living_loop_realism` to evaluate whether `artifact_motive -> artifact_behavior_alignment -> final behavior` is causally visible in real backend payloads.

**Core Files:**

- Modify `amadeus_thread0/runtime/living_loop_realism.py`
- Modify `tests/test_living_loop_realism.py`
- Modify `tests/test_backend_api.py`
- Create `evals/run_living_loop_realism_phase3_audit.py`
- Create `tests/test_living_loop_realism_phase3_audit.py`
- Modify `evals/run_preserved_baselines_audit.py`
- Modify `tests/test_preserved_baselines_audit.py`
- Update docs and `program.md`

**Executable Steps:**

- [ ] Write failing realism tests with backend payloads that include Phase 5 alignment readback.
- [ ] Require realism output to distinguish `artifact_behavior_alignment_visible`, `advisory_not_reflected_visible`, and `causal_alignment_visible`.
- [ ] Implement minimal normalization in `living_loop_realism.py` that consumes existing Phase 5 readback without recalculating alignment.
- [ ] Verify existing Phase 1/2 living-loop realism audits still pass.
- [ ] Add Phase 3 audit scenarios:
  - aligned artifact motive reflected in behavior
  - advisory-not-reflected motive visible without fake success
  - blocked artifact motive does not become causality
  - backend payload carries same realism readback on `assistant_turn` and `event_round`
- [ ] Add preserved baseline row and update docs.
- [ ] Merge, post-merge audit, push.

---

## Phase 3: Chinese Semantic De-Scaffolding Phase 2

**Readiness:** `chinese_semantic_descaffolding_phase2_ready`

**Purpose:** Convert conservative Chinese semantic floors into an auditable runtime replacement policy, still avoiding broad prompt-sprawl or tone micro-polish outside typed semantic families.

**Core Files:**

- Modify `amadeus_thread0/graph_parts/chinese_semantic_surface.py`
- Modify `amadeus_thread0/runtime/embodied_interaction_runtime.py`
- Create or modify `evals/run_chinese_semantic_descaffolding_phase2_audit.py`
- Create or modify `tests/test_chinese_semantic_descaffolding_phase2_audit.py`
- Modify existing surface tests under `tests/`
- Modify `evals/run_preserved_baselines_audit.py`
- Update docs and `program.md`

**Executable Steps:**

- [ ] Write failing tests for typed replacement families that currently rely on brittle surface residue.
- [ ] Require one runtime policy envelope with `family`, `semantic_intent`, `replacement_strategy`, `applied_floor`, and `authority_boundary`.
- [ ] Implement policy output without changing generation prompts or persona core.
- [ ] Ensure `final_text` and `reconsolidation_snapshot.final_text` remain identical when replacement applies.
- [ ] Add audit scenarios for everyday, repair, self-rhythm, and technical task responses.
- [ ] Confirm no duplicate output, no scaffold residue leak, and no text/TTS drift.
- [ ] Merge, post-merge audit, push.

---

## Phase 4: Multimodal Perception Phase 2

**Readiness:** `multimodal_perception_phase2_ready`

**Purpose:** Add approval-gated artifact inspection packets for multimodal model inspection while preserving Phase 1 consent-bound source artifacts and keeping live capture blocked.

**Core Files:**

- Modify `amadeus_thread0/runtime/multimodal_sources.py`
- Modify `amadeus_thread0/runtime/embodied_interaction_runtime.py`
- Modify `amadeus_thread0/graph_parts/action_packets.py`
- Modify `amadeus_thread0/graph_parts/autonomy_runtime.py`
- Modify `tests/test_multimodal_sources.py`
- Create `tests/test_multimodal_perception_phase2.py`
- Create `evals/run_multimodal_perception_phase2_audit.py`
- Modify `evals/run_preserved_baselines_audit.py`
- Update docs and `program.md`

**Executable Steps:**

- [ ] Write failing tests for an `artifact:inspect_multimodal` action packet with stable proposal id, source refs, preview, approval status, and no auto-execution.
- [ ] Require live microphone/camera/background screen capture attempts to remain blocked.
- [ ] Implement packet preview only; do not call a multimodal model until approval semantics are explicit and tested.
- [ ] Add approved-result fixture path that accepts a precomputed inspection result as packet execution result.
- [ ] Mirror completed inspection into artifact semantics only as approved result, not as live capture.
- [ ] Add audit scenarios for pending approval, completed approved inspection, rejected inspection, and blocked live capture.
- [ ] Merge, post-merge audit, push.

---

## Phase 5: Dynamic Skills Phase 2

**Readiness:** `dynamic_skills_phase2_ready`

**Purpose:** Close the approved candidate installation loop: candidate skill proposal -> operator approval -> install/enable -> session activation/readback -> later continuity.

**Core Files:**

- Modify `amadeus_thread0/runtime/dynamic_skill_candidates.py`
- Modify `amadeus_thread0/runtime/skill_registry.py`
- Modify `amadeus_thread0/graph_parts/skill_runtime.py`
- Modify `tests/test_skill_registry.py`
- Modify `tests/test_skill_runtime.py`
- Create `tests/test_dynamic_skills_phase2.py`
- Create `evals/run_dynamic_skills_phase2_audit.py`
- Modify `evals/run_preserved_baselines_audit.py`
- Update docs and `program.md`

**Executable Steps:**

- [ ] Write failing tests for candidate proposal hash/version/permissions stability.
- [ ] Require approval resume to install exactly the frozen candidate payload.
- [ ] Implement install/enable path through the existing registry, not autobiographical memory.
- [ ] Verify rejected/pending/blocked candidates never become active skills.
- [ ] Add continuity readback only for completed skill use effects.
- [ ] Add audit scenarios for approved install, rejected install, manual disable precedence, pin precedence, and follow-up continuity.
- [ ] Merge, post-merge audit, push.

---

## Phase 6: Frontend Runtime Shell Phase 2

**Readiness:** `frontend_runtime_shell_phase2_ready`

**Purpose:** Make the frontend shell consume live `backend.v1` contract payloads through a thin adapter while keeping backend semantics owned by Python runtime modules.

**Core Files:**

- Modify `frontend/` only if it exists on the current `main`
- Modify or create frontend API client files under `frontend/src/`
- Modify or create frontend contract fixtures/tests
- Modify `docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md`
- Create `evals/run_frontend_runtime_shell_phase2_audit.py`
- Modify `evals/run_preserved_baselines_audit.py`
- Update docs and `program.md`

**Executable Steps:**

- [ ] Confirm frontend workspace existence and current package scripts.
- [ ] Write failing frontend tests for live transport adapter shape using `backend.v1` envelopes.
- [ ] Implement a thin client that can read from route-like backend responses without redefining schema.
- [ ] Render `assistant_turn`, `event_round`, `operator_readback`, `living_loop_realism`, and `embodied_interaction` from backend payloads.
- [ ] Verify build and browser smoke if frontend workspace is present.
- [ ] Add audit proving frontend is consumer-only and does not own memory/body/autonomy semantics.
- [ ] Merge, post-merge audit, push.

---

## Closure Definition

This rolling program is considered closed when:

- all six phases above have corresponding ready audits,
- `python evals/run_preserved_baselines_audit.py --reports-dir evals/reports` passes on `main`,
- all phase-specific readiness values are listed in `AGENTS.md`, `PROJECT_STRUCTURE.md`, architecture decisions, and `program.md`,
- no phase has opened live capture, automatic skill registry writes, arbitrary execution, persona-core mutation, second memory substrate, frontend-owned semantics, or unapproved external mutation outside its audited boundary.
