# Post-Unlock Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert every `Complete Closeout Unlock` lane into a bounded, testable, auditable implementation sequence without reopening persona identity, memory substrate, body truth, approval semantics, or preserved execution baselines.

**Architecture:** Treat this as a master orchestration plan, not one giant code batch. Each unlocked lane gets a phase-1 implementation slice with its own spec, tests, audit runner, docs, and merge gate; cross-lane integration happens only through existing `backend.v1`, `digital_body`, `action_packets`, `skills`, `procedural_growth`, and memory writeback surfaces. No lane may expose runtime authority merely because it appears in this plan.

**Tech Stack:** Python 3, LangGraph/LangChain graph modules in `amadeus_thread0/graph_parts/`, runtime adapters in `amadeus_thread0/runtime/`, pytest, existing `evals/` audit runners, React/Vite/TypeScript frontend shell, Docker sandbox phase 2, Playwright browser runtime, repository-local `SKILL.md` packages.

---

## Scope Contract

This plan covers the seven lanes unlocked by `Complete Closeout Unlock`:

1. Multimodal Capture Phase 1
2. Dynamic Skills Phase 1
3. External Executor Harness Phase 1
4. Frontend Runtime Shell Phase 1
5. Chinese Semantic De-Scaffolding Phase 1
6. Capability Growth Phase 5
7. Natural Long-Horizon Calibration Phase 1

This plan deliberately does not turn all seven lanes into one merge. Each lane must be implemented as a separate branch or worktree slice with its own green validation evidence. The master order below defines dependencies, shared contracts, and acceptance gates.

## Non-Negotiable Guardrails

- Persona core remains fixed. State may evolve; identity must not drift.
- One unified memory substrate remains authoritative. No work-memory, skill-memory, frontend-memory, or multimodal-memory silo may be introduced.
- One digital body truth remains authoritative. New surfaces must feed `digital_body`, `digital_body_consequence`, `interaction_carryover.embodied_context`, and retrieval/export surfaces rather than creating a parallel body model.
- `action_packets` remain the only structured external-action unit.
- External mutation remains approval-gated.
- Browser mutation/download/upload still require approval or manual takeover as already specified.
- Docker sandbox phase 2 remains bounded to `python`, `pytest`, `rg`, and read-only `git`, with `network_policy=none`.
- Package install, arbitrary host shell, privileged containers, Docker socket mounting, host secret passthrough, credential guessing, OTP simulation, CAPTCHA bypass, and cookie forgery remain blocked.
- Frontend work consumes `backend.v1`; it does not own backend semantics.
- Chinese semantic work replaces brittle scaffolding through diagnostics and tests first; it must not become ad hoc reply-tone micro-polish.

## Baseline Gate Before Any Lane

Run this gate at the start of each lane branch:

```powershell
git status --short --branch
python -m pytest tests/test_post_baseline_closure.py tests/test_post_baseline_closure_audit.py tests/test_preserved_baselines_audit.py -q
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
```

Expected:

- Git status shows only known unrelated local state, currently `third_party/benchmarks/ESConv` in the main workspace.
- Targeted closeout tests pass.
- Preserved-baselines audit reports `overall_status=passed` and `readiness=preserved_baselines_ready`.

If the reports directory is missing authoritative gitignored reports in a fresh worktree, rerun the audit against the main report directory or copy only the needed report artifacts into the worktree's ignored `evals/reports/` before judging baseline health.

## File Ownership Map

Common docs and planning files:

- `AGENTS.md`
- `program.md`
- `docs/engineering/PROJECT_STRUCTURE.md`
- `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- `docs/engineering/BACKEND_HANDOFF.md`
- `docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md`
- `docs/superpowers/specs/*.md`
- `docs/superpowers/plans/*.md`

Common audit surfaces:

- `evals/run_preserved_baselines_audit.py`
- `evals/run_post_baseline_closure_audit.py`
- new lane-specific `evals/run_*_audit.py`
- new lane-specific `evals/run_*_smokes.py` when a deterministic smoke pack is needed

Common backend surfaces:

- `amadeus_thread0/runtime/backend_api.py`
- `amadeus_thread0/runtime/backend_session.py`
- `amadeus_thread0/runtime/final_state.py`
- `amadeus_thread0/graph_parts/action_packets.py`
- `amadeus_thread0/graph_parts/autonomy_runtime.py`
- `amadeus_thread0/graph_parts/digital_body_runtime.py`
- `amadeus_thread0/graph_parts/memory_evolution.py`
- `amadeus_thread0/graph_parts/perception.py`
- `amadeus_thread0/graph_parts/session_context.py`
- `amadeus_thread0/graph_parts/prepare_turn_context.py`
- `amadeus_thread0/graph_parts/prepare_turn_runtime.py`
- `amadeus_thread0/utils/turn_summary_export.py`
- `amadeus_thread0/utils/revision_trace_export.py`

Common contract tests:

- `tests/test_backend_api.py`
- `tests/test_backend_session.py`
- `tests/test_tool_approval_policy.py`
- `tests/test_autonomy_writeback.py`
- `tests/test_world_model_residue.py`
- `tests/test_frontend_contract_sync.py`
- `tests/test_preserved_baselines_audit.py`

## Dependency Order

Recommended sequence:

1. `Multimodal Capture Phase 1` first, because all later cross-surface work needs one input artifact/consent contract.
2. `Dynamic Skills Phase 1` and `External Executor Harness Phase 1` can proceed in parallel after multimodal source identity is specified; both must stay proposal-only until their own approval gates close.
3. `Frontend Runtime Shell Phase 1` can proceed in parallel with dynamic skills and executor harness work because it consumes existing `backend.v1` envelopes.
4. `Chinese Semantic De-Scaffolding Phase 1` can proceed after its offline audit is green; behavior-changing replacements must wait until baseline audits pass after each semantic change.
5. `Capability Growth Phase 5` depends on procedural growth phase 4 plus dynamic skill/executor proposal contracts.
6. `Natural Long-Horizon Calibration Phase 1` should run after the new input/capability surfaces expose stable readback, so calibration evaluates the whole lived-loop surface rather than only final text.
7. `Post-Unlock Integration Gate` runs after each lane and again after all lanes targeted for a release train are merged.

---

## Task 0: Create The Release Train Ledger

**Files:**

- Create: `docs/superpowers/specs/2026-05-06-post-unlock-roadmap-design.md`
- Modify: `program.md`
- Optional Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`

- [ ] **Step 1: Write the release-train spec**

Create `docs/superpowers/specs/2026-05-06-post-unlock-roadmap-design.md` with these sections:

```markdown
# Post-Unlock Roadmap Design

## Purpose

Coordinate all `unlocked_planned` lanes into bounded, auditable implementation phases.

## Lanes

1. Multimodal Capture Phase 1
2. Dynamic Skills Phase 1
3. External Executor Harness Phase 1
4. Frontend Runtime Shell Phase 1
5. Chinese Semantic De-Scaffolding Phase 1
6. Capability Growth Phase 5
7. Natural Long-Horizon Calibration Phase 1

## Shared Guardrails

- one fixed persona core
- one unified memory substrate
- one digital body truth
- packet-owned actions
- approval-gated external mutation
- completed facts only write back as facts

## Completion Rule

Each lane must close with its own audit readiness label before the lane can be considered runtime-ready.
```

- [ ] **Step 2: Add program ledger entry**

Append to `program.md`:

```markdown
## 2026-05-06 Run 255

- Focus:
  - write the post-unlock master roadmap for all `unlocked_planned` lanes
- Files changed:
  - `docs/superpowers/plans/2026-05-06-post-unlock-roadmap.md`
  - `docs/superpowers/specs/2026-05-06-post-unlock-roadmap-design.md`
  - `program.md`
- Validation:
  - docs-only planning pass
  - final checks to run: placeholder scan and `git diff --check`
- Result:
  - post-unlock work is organized into lane-specific phase gates
- Next:
  - start with `Multimodal Capture Phase 1`
```

- [ ] **Step 3: Run doc checks**

Run:

```powershell
rg -n -e "T[B]D" -e "T[O]DO" -e "f[i]ll in" -e "implement la[t]er" -e "appropriate error handl[i]ng" -e "similar to T[a]sk" -e "Similar to T[a]sk" docs/superpowers/plans/2026-05-06-post-unlock-roadmap.md docs/superpowers/specs/2026-05-06-post-unlock-roadmap-design.md
git diff --check -- docs/superpowers/plans/2026-05-06-post-unlock-roadmap.md docs/superpowers/specs/2026-05-06-post-unlock-roadmap-design.md program.md
```

Expected:

- Placeholder scan returns no hits.
- `git diff --check` has no whitespace errors; Windows LF-to-CRLF warnings are acceptable.

- [ ] **Step 4: Commit release-train ledger**

Run:

```powershell
git add docs/superpowers/plans/2026-05-06-post-unlock-roadmap.md docs/superpowers/specs/2026-05-06-post-unlock-roadmap-design.md program.md
git commit -m "docs: plan post unlock roadmap"
```

---

## Task 1: Multimodal Capture Phase 1

**Goal:** Add consent-bound, read-only multimodal source ingestion as digital-body perception, without live microphone/camera/screen recording and without writing new memory facts unless a completed, source-bound event reaches final writeback.

**Files:**

- Create: `docs/superpowers/specs/2026-05-06-multimodal-capture-phase1-design.md`
- Create: `docs/superpowers/plans/2026-05-06-multimodal-capture-phase1.md`
- Create: `amadeus_thread0/runtime/multimodal_sources.py`
- Create: `evals/run_multimodal_capture_smokes.py`
- Create: `evals/run_multimodal_capture_audit.py`
- Create: `tests/test_multimodal_sources.py`
- Create: `tests/test_multimodal_capture_audit.py`
- Modify: `amadeus_thread0/graph_parts/perception.py`
- Modify: `amadeus_thread0/graph_parts/session_context.py`
- Modify: `amadeus_thread0/graph_parts/prepare_turn_context.py`
- Modify: `amadeus_thread0/graph_parts/digital_body_runtime.py`
- Modify: `amadeus_thread0/runtime/backend_api.py`
- Modify: `tests/test_perception_event_contract.py`
- Modify: `tests/test_digital_body_runtime.py`
- Modify: `tests/test_backend_api.py`
- Modify: `program.md`

- [ ] **Step 1: Write the phase spec**

The spec must define exactly these phase-1 modalities:

```text
text_attachment
image_file_observation
audio_file_observation
screen_snapshot_file_observation
browser_capture_ref_observation
```

The spec must explicitly block:

```text
live microphone recording
live camera capture
background screen recording
secret capture
emotion inference from voice alone
identity claims from image/audio alone
```

- [ ] **Step 2: Write failing source-contract tests**

Create `tests/test_multimodal_sources.py` with tests for:

```python
def test_source_artifact_requires_consent_and_digest():
    artifact = normalize_multimodal_source(
        {
            "source_id": "img-1",
            "modality": "image",
            "path": "fixtures/panel.png",
            "consent_scope": "single_turn",
            "capture_method": "operator_attached_file",
        }
    )
    assert artifact["source_id"] == "img-1"
    assert artifact["modality"] == "image"
    assert artifact["consent_scope"] == "single_turn"
    assert artifact["writeback_ready"] is False
    assert artifact["payload_digest"]


def test_source_artifact_blocks_secret_capture():
    artifact = normalize_multimodal_source(
        {
            "source_id": "mic-live",
            "modality": "audio",
            "capture_method": "background_microphone",
            "consent_scope": "",
        }
    )
    assert artifact["status"] == "blocked"
    assert "missing_explicit_consent" in artifact["block_reasons"]
```

- [ ] **Step 3: Run red**

Run:

```powershell
python -m pytest tests/test_multimodal_sources.py -q
```

Expected:

- Fails because `amadeus_thread0.runtime.multimodal_sources` does not exist.

- [ ] **Step 4: Implement minimal source normalizer**

Create `amadeus_thread0/runtime/multimodal_sources.py` with:

```python
ALLOWED_PHASE1_CAPTURE_METHODS = {
    "operator_attached_file",
    "saved_source_ref_capture",
    "browser_runtime_capture_ref",
}

BLOCKED_CAPTURE_METHODS = {
    "background_microphone",
    "background_camera",
    "background_screen",
    "unconsented_browser_capture",
}

def normalize_multimodal_source(raw: dict) -> dict:
    ...

def build_multimodal_perception_event(source: dict) -> dict:
    ...
```

Required output fields:

```python
{
    "source_id": "...",
    "modality": "image|audio|screen|text|browser_capture",
    "source_role": "operator|runtime|saved_material",
    "consent_scope": "single_turn|session|saved_material_review",
    "capture_method": "...",
    "artifact_ref": "...",
    "payload_digest": "...",
    "trust_tier": "medium",
    "status": "available|blocked",
    "block_reasons": [],
    "writeback_ready": False,
}
```

- [ ] **Step 5: Add graph/event integration tests**

Extend `tests/test_perception_event_contract.py` and `tests/test_digital_body_runtime.py` to assert:

```python
event = build_multimodal_perception_event(source)
assert event["kind"] == "multimodal_observation"
assert event["perception"]["modality"] == "image"
assert event["perception"]["digital_body_hints"]["active_artifact_kind"] == "image"
assert event["perception"]["digital_body_hints"]["artifact_carrier"] == "multimodal_source"
```

- [ ] **Step 6: Wire perception/session/body surfaces**

Update:

- `graph_parts/perception.py` so `multimodal_observation` is normalized as an environment/source event.
- `graph_parts/session_context.py` so `digital_body_hints.multimodal_source` flows into the session context.
- `graph_parts/digital_body_runtime.py` so resource state can expose `artifact_carrier=multimodal_source`.
- `runtime/backend_api.py` so `assistant_turn` and `event_round` payloads preserve the source-bound body facts.

- [ ] **Step 7: Add smoke and audit runners**

Create `evals/run_multimodal_capture_smokes.py` with deterministic fixture scenarios:

```text
operator_image_attachment_becomes_source_artifact
audio_file_attachment_remains_consent_bound
screen_snapshot_file_does_not_claim_live_screen_access
browser_capture_ref_preserves_browser_runtime_boundary
secret_capture_is_blocked
```

Create `evals/run_multimodal_capture_audit.py` that reports:

```text
overall_status=passed
readiness_status=multimodal_capture_phase1_ready
```

only when all five smoke scenarios pass and the key contract tests pass.

- [ ] **Step 8: Run validation**

Run:

```powershell
python -m pytest tests/test_multimodal_sources.py tests/test_perception_event_contract.py tests/test_digital_body_runtime.py tests/test_backend_api.py -q
python -m pytest tests/test_multimodal_capture_audit.py -q
python evals/run_multimodal_capture_smokes.py --run-tag phase1-dev
python evals/run_multimodal_capture_audit.py --run-tag phase1-dev
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
```

Expected:

- Multimodal audit reports `multimodal_capture_phase1_ready`.
- Preserved baselines remain ready.

- [ ] **Step 9: Update docs and commit**

Update `AGENTS.md`, `PROJECT_STRUCTURE.md`, `AMADEUS_ARCHITECTURE_DECISIONS.md`, and `program.md` with the new preserved phase-1 contract.

Run:

```powershell
git add AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md docs/superpowers/specs/2026-05-06-multimodal-capture-phase1-design.md docs/superpowers/plans/2026-05-06-multimodal-capture-phase1.md amadeus_thread0/runtime/multimodal_sources.py amadeus_thread0/graph_parts/perception.py amadeus_thread0/graph_parts/session_context.py amadeus_thread0/graph_parts/prepare_turn_context.py amadeus_thread0/graph_parts/digital_body_runtime.py amadeus_thread0/runtime/backend_api.py evals/run_multimodal_capture_smokes.py evals/run_multimodal_capture_audit.py tests/test_multimodal_sources.py tests/test_multimodal_capture_audit.py tests/test_perception_event_contract.py tests/test_digital_body_runtime.py tests/test_backend_api.py
git commit -m "feat: add multimodal capture phase 1"
```

---

## Task 2: Dynamic Skills Phase 1

**Goal:** Let the system propose registry-backed skill candidates from completed procedural evidence without installing, enabling, or executing generated skills automatically.

**Files:**

- Create: `docs/superpowers/specs/2026-05-06-dynamic-skills-phase1-design.md`
- Create: `docs/superpowers/plans/2026-05-06-dynamic-skills-phase1.md`
- Create: `amadeus_thread0/runtime/dynamic_skill_candidates.py`
- Create: `evals/run_dynamic_skills_smokes.py`
- Create: `evals/run_dynamic_skills_audit.py`
- Create: `tests/test_dynamic_skill_candidates.py`
- Create: `tests/test_dynamic_skills_audit.py`
- Modify: `amadeus_thread0/runtime/skill_registry.py`
- Modify: `amadeus_thread0/graph_parts/skill_runtime.py`
- Modify: `amadeus_thread0/graph_parts/autonomy_runtime.py`
- Modify: `amadeus_thread0/graph_parts/procedural_growth.py`
- Modify: `tests/test_skill_registry.py`
- Modify: `tests/test_skill_runtime.py`
- Modify: `tests/test_tool_approval_policy.py`
- Modify: `tests/test_autonomy_writeback.py`
- Modify: `program.md`

- [ ] **Step 1: Write the phase spec**

The spec must define a `SkillCandidate` contract:

```python
{
    "candidate_id": "skill-candidate-...",
    "origin": "procedural_trace|operator_request|source_ref_review",
    "skill_id": "workspace-regression-triage",
    "draft_skill_md": "...",
    "source_evidence_refs": ["..."],
    "requested_permissions": [],
    "sandbox_profiles": ["docker_local_isolated"],
    "hash": "...",
    "status": "proposed",
    "requires_approval": True,
}
```

The spec must explicitly block:

```text
auto-install
auto-enable
persona-core patching
registry write without approval
host-side executable generation outside the registry candidate area
```

- [ ] **Step 2: Write failing candidate tests**

Create `tests/test_dynamic_skill_candidates.py` with tests:

```python
def test_candidate_from_completed_procedural_trace_is_proposal_only():
    candidate = propose_skill_candidate_from_trace(
        {
            "trace_id": "proc-1",
            "kind": "workspace_procedure",
            "confidence": 0.91,
            "summary": "triage pytest failures with rg and pytest",
            "completed": True,
        }
    )
    assert candidate["status"] == "proposed"
    assert candidate["requires_approval"] is True
    assert candidate["registry_written"] is False


def test_pending_trace_cannot_become_skill_candidate():
    candidate = propose_skill_candidate_from_trace(
        {
            "trace_id": "proc-2",
            "kind": "workspace_procedure",
            "status": "pending_approval",
            "completed": False,
        }
    )
    assert candidate["status"] == "blocked"
    assert "not_completed_fact" in candidate["block_reasons"]
```

- [ ] **Step 3: Run red**

Run:

```powershell
python -m pytest tests/test_dynamic_skill_candidates.py -q
```

Expected:

- Fails because `dynamic_skill_candidates.py` does not exist.

- [ ] **Step 4: Implement candidate helper**

Create `amadeus_thread0/runtime/dynamic_skill_candidates.py` with:

```python
def propose_skill_candidate_from_trace(trace: dict) -> dict:
    ...

def build_skill_candidate_approval(candidate: dict) -> dict:
    ...

def verify_candidate_hash(candidate: dict) -> dict:
    ...
```

Rules:

- Candidate files may be written only under runtime-owned data directories such as `<AMADEUS_DATA_DIR>/skills/candidates/<candidate_id>/`.
- Candidate status remains `proposed` until approval.
- Existing `skill_registry` install/enable/pin approval rules remain authoritative.

- [ ] **Step 5: Integrate proposal readback**

Update:

- `runtime/skill_registry.py` to list candidate metadata without treating candidates as installed skills.
- `graph_parts/skill_runtime.py` to include `pending_skill_candidate` in the skills envelope.
- `graph_parts/autonomy_runtime.py` to create action packet intent `skills:propose_candidate` only when the input trace is completed.

- [ ] **Step 6: Add smoke and audit runners**

Smoke scenarios:

```text
completed_trace_proposes_candidate
candidate_hash_is_stable
approval_payload_contains_candidate_id_and_hash
pending_trace_does_not_propose_candidate
candidate_does_not_enter_autobiographical_memory
```

Audit readiness:

```text
dynamic_skills_phase1_ready
```

- [ ] **Step 7: Run validation**

Run:

```powershell
python -m pytest tests/test_dynamic_skill_candidates.py tests/test_skill_registry.py tests/test_skill_runtime.py tests/test_tool_approval_policy.py tests/test_autonomy_writeback.py -q
python -m pytest tests/test_dynamic_skills_audit.py -q
python evals/run_dynamic_skills_smokes.py --run-tag phase1-dev
python evals/run_dynamic_skills_audit.py --run-tag phase1-dev
python evals/run_skills_ecosystem_audit.py
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
```

Expected:

- Dynamic skills audit reports `dynamic_skills_phase1_ready`.
- Skills ecosystem audit remains `skills_ecosystem_ready`.

- [ ] **Step 8: Update docs and commit**

Run:

```powershell
git add AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md docs/superpowers/specs/2026-05-06-dynamic-skills-phase1-design.md docs/superpowers/plans/2026-05-06-dynamic-skills-phase1.md amadeus_thread0/runtime/dynamic_skill_candidates.py amadeus_thread0/runtime/skill_registry.py amadeus_thread0/graph_parts/skill_runtime.py amadeus_thread0/graph_parts/autonomy_runtime.py amadeus_thread0/graph_parts/procedural_growth.py evals/run_dynamic_skills_smokes.py evals/run_dynamic_skills_audit.py tests/test_dynamic_skill_candidates.py tests/test_dynamic_skills_audit.py tests/test_skill_registry.py tests/test_skill_runtime.py tests/test_tool_approval_policy.py tests/test_autonomy_writeback.py
git commit -m "feat: add dynamic skills phase 1"
```

---

## Task 3: External Executor Harness Phase 1

**Goal:** Add a fail-closed external harness registry and preview/result normalization layer while keeping only the existing sandbox runner enabled.

**Files:**

- Create: `docs/superpowers/specs/2026-05-06-external-executor-harness-phase1-design.md`
- Create: `docs/superpowers/plans/2026-05-06-external-executor-harness-phase1.md`
- Create: `amadeus_thread0/runtime/executor_harness_registry.py`
- Create: `evals/run_external_executor_harness_audit.py`
- Create: `tests/test_executor_harness_registry.py`
- Create: `tests/test_external_executor_harness_audit.py`
- Modify: `amadeus_thread0/runtime/executor_adapter.py`
- Modify: `amadeus_thread0/graph_parts/action_packets.py`
- Modify: `tests/test_executor_adapter.py`
- Modify: `tests/test_executor_adapter_audit.py`
- Modify: `tests/test_sandbox_phase2_backend_contract.py`
- Modify: `program.md`

- [ ] **Step 1: Write the phase spec**

The spec must define candidate harness kinds:

```text
deep_agents
codex_harness
claude_harness
openclaw_harness
```

Phase 1 status for each:

```text
available_for_preview=false
runtime_enabled=false
result_only=true
persona_memory_ownership=false
requires_operator_install=true
```

- [ ] **Step 2: Write failing registry tests**

Create `tests/test_executor_harness_registry.py`:

```python
def test_external_harnesses_are_fail_closed_by_default():
    registry = build_executor_harness_registry()
    for harness in ("deep_agents", "codex_harness", "claude_harness", "openclaw_harness"):
        row = registry[harness]
        assert row["runtime_enabled"] is False
        assert row["persona_memory_ownership"] is False
        assert row["requires_approval"] is True


def test_sandbox_runner_remains_only_enabled_executor():
    registry = build_executor_harness_registry()
    enabled = [key for key, row in registry.items() if row["runtime_enabled"]]
    assert enabled == ["sandbox_runner"]
```

- [ ] **Step 3: Run red**

Run:

```powershell
python -m pytest tests/test_executor_harness_registry.py -q
```

Expected:

- Fails because the registry module does not exist.

- [ ] **Step 4: Implement registry**

Create `runtime/executor_harness_registry.py` with:

```python
def build_executor_harness_registry() -> dict[str, dict]:
    ...

def describe_harness_boundary(harness_kind: str) -> dict:
    ...

def normalize_external_harness_result(raw: dict) -> dict:
    ...
```

Rules:

- No external harness runs code in phase 1.
- Result normalization accepts recorded fixtures only.
- Normalized results cannot write memory facts directly.

- [ ] **Step 5: Integrate with executor adapter**

Update `executor_adapter.py` so disabled adapter descriptions come from the registry and include:

```python
{
    "memory_policy": "no_persona_memory_ownership",
    "writeback_policy": "result_only",
    "status": "disabled",
    "requires_operator_install": True,
}
```

- [ ] **Step 6: Add audit runner**

Create `evals/run_external_executor_harness_audit.py` checking:

```text
sandbox_runner_enabled
external_harnesses_disabled
external_harness_result_normalization_is_result_only
no_package_install_surface
no_git_mutation_surface
```

Readiness:

```text
external_executor_harness_phase1_ready
```

- [ ] **Step 7: Run validation**

Run:

```powershell
python -m pytest tests/test_executor_harness_registry.py tests/test_executor_adapter.py tests/test_executor_adapter_audit.py tests/test_sandbox_phase2_backend_contract.py -q
python -m pytest tests/test_external_executor_harness_audit.py -q
python evals/run_external_executor_harness_audit.py --run-tag phase1-dev
python evals/run_sandbox_phase2_audit.py --run-tag external-harness-phase1-baseline
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
```

Expected:

- External harness audit reports `external_executor_harness_phase1_ready`.
- Sandbox phase 2 remains ready.

- [ ] **Step 8: Update docs and commit**

Run:

```powershell
git add AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md docs/superpowers/specs/2026-05-06-external-executor-harness-phase1-design.md docs/superpowers/plans/2026-05-06-external-executor-harness-phase1.md amadeus_thread0/runtime/executor_harness_registry.py amadeus_thread0/runtime/executor_adapter.py amadeus_thread0/graph_parts/action_packets.py evals/run_external_executor_harness_audit.py tests/test_executor_harness_registry.py tests/test_external_executor_harness_audit.py tests/test_executor_adapter.py tests/test_executor_adapter_audit.py tests/test_sandbox_phase2_backend_contract.py
git commit -m "feat: add external executor harness phase 1"
```

---

## Task 4: Frontend Runtime Shell Phase 1

**Goal:** Turn the frontend into a contract-consuming runtime shell over `backend.v1` envelopes, without letting the frontend own graph, memory, body, autonomy, or approval semantics.

**Files:**

- Create: `docs/superpowers/specs/2026-05-06-frontend-runtime-shell-phase1-design.md`
- Create: `docs/superpowers/plans/2026-05-06-frontend-runtime-shell-phase1.md`
- Create or Modify: `frontend/src/runtime/backendClient.ts`
- Create or Modify: `frontend/src/contracts/backend.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/InspectorTabs.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md`
- Modify: `docs/engineering/frontend_contract/backend_api.types.ts`
- Modify: `docs/engineering/frontend_contract/mocks/*.json`
- Modify: `tests/test_frontend_contract_sync.py`
- Modify: `program.md`

- [ ] **Step 1: Write the phase spec**

The spec must define:

```text
first screen: transcript + current final packet + inspector tabs
data source: backend.v1 envelopes only
transport: existing mockBackend first, optional callable adapter shim later
approval UX: display pending approval from backend envelope, do not generate approvals client-side
manual takeover UX: display backend assist_request, do not simulate credentials
```

- [ ] **Step 2: Add contract sync tests**

Extend `tests/test_frontend_contract_sync.py` so frontend mocks and docs types require:

```text
autonomy.intent
autonomy.action_packets
autonomy.pending_approval
skills.active
skills.pending_approval
digital_body.access_state.sandbox_state
digital_body.access_state.browser_runtime_state
digital_body.resource_state
digital_body_consequence
procedural_growth
procedural_outcome
procedural_recovery
```

- [ ] **Step 3: Run red**

Run:

```powershell
python -m pytest tests/test_frontend_contract_sync.py -q
npm --prefix frontend run build
```

Expected:

- Contract test or frontend build fails if types/mocks are stale.

- [ ] **Step 4: Refresh contract assets**

Update:

- `docs/engineering/frontend_contract/backend_api.types.ts`
- `frontend/src/contracts/backend.ts`
- `docs/engineering/frontend_contract/mocks/*.json`
- `frontend/src/mocks/*.json`

Rules:

- Do not rename backend fields.
- Treat unknown additive keys as allowed.
- Keep `final_text` as the only rendered/voiced text source.

- [ ] **Step 5: Implement shell behavior**

Update frontend UI so the first screen shows:

```text
transcript/final_text
pending approval strip
digital body state panel
skills panel
procedural continuity panel
worldline/bond inspector tabs
```

The UI may use mock envelopes but must be wired through `createBackendClient()` rather than importing mocks directly in component logic.

- [ ] **Step 6: Run validation**

Run:

```powershell
python -m pytest tests/test_frontend_contract_sync.py tests/test_backend_api.py tests/test_backend_session.py -q
npm --prefix frontend run build
```

Expected:

- Frontend build succeeds.
- Contract sync passes.

- [ ] **Step 7: Update docs and commit**

Run:

```powershell
git add docs/superpowers/specs/2026-05-06-frontend-runtime-shell-phase1-design.md docs/superpowers/plans/2026-05-06-frontend-runtime-shell-phase1.md docs/engineering/FRONTEND_INTERFACE_DELIVERABLE.md docs/engineering/frontend_contract frontend/src frontend/package.json frontend/package-lock.json tests/test_frontend_contract_sync.py program.md
git commit -m "feat: add frontend runtime shell phase 1"
```

---

## Task 5: Chinese Semantic De-Scaffolding Phase 1

**Goal:** Replace brittle Chinese lexical scaffolding with semantic diagnostics and audit-backed candidate replacements before broad runtime rewrites.

**Files:**

- Create: `docs/superpowers/specs/2026-05-06-chinese-semantic-descaffolding-phase1-design.md`
- Create: `docs/superpowers/plans/2026-05-06-chinese-semantic-descaffolding-phase1.md`
- Create: `amadeus_thread0/graph_parts/chinese_semantic_surface.py`
- Modify: `evals/chinese_surface_residue_bank.json`
- Modify: `evals/run_chinese_surface_de_scaffold_audit.py`
- Modify: `amadeus_thread0/graph_parts/postprocess.py`
- Modify: `amadeus_thread0/graph_parts/rewrite.py`
- Modify: `tests/test_chinese_surface_de_scaffold_audit.py`
- Modify: `tests/test_subjective_review_pack.py`
- Modify: `tests/test_dialogue_mode_counterpart.py`
- Modify: `program.md`

- [ ] **Step 1: Write the phase spec**

The spec must define semantic residue families:

```text
teacherly_scold
meta_persona_proof
generic_assistant_tone
hardline_autonomy_overreach
scene_script_residue
taskization_of_daily_chat
repair_scorekeeping
boundary_threat_excess
```

The spec must require that behavior changes proceed in this order:

```text
offline audit coverage
semantic classification
shadow diagnostics
candidate replacement tests
small runtime replacement
baseline audit
```

- [ ] **Step 2: Write failing semantic-classifier tests**

Create tests in `tests/test_chinese_surface_de_scaffold_audit.py`:

```python
def test_semantic_classifier_detects_teacherly_scold_without_exact_phrase():
    families = classify_chinese_surface_semantics("你能回来说明问题，别摆出一副求表扬的样子。")
    assert "teacherly_scold" in families


def test_semantic_classifier_detects_boundary_threat_without_exact_phrase():
    families = classify_chinese_surface_semantics("再来一次，我就不会继续给你留余地。")
    assert "boundary_threat_excess" in families
```

- [ ] **Step 3: Run red**

Run:

```powershell
python -m pytest tests/test_chinese_surface_de_scaffold_audit.py -q
```

Expected:

- Fails because `chinese_semantic_surface.py` does not exist or lacks the classifier.

- [ ] **Step 4: Implement semantic classifier**

Create `graph_parts/chinese_semantic_surface.py` with:

```python
def classify_chinese_surface_semantics(text: str) -> list[str]:
    ...

def candidate_replacement_semantics(family: str) -> dict:
    ...

def compare_legacy_and_semantic_detection(text: str) -> dict:
    ...
```

Rules:

- Phase 1 can use deterministic offline heuristics and pattern groups, but the public API must be semantic-family based rather than exact phrase based.
- Existing lexical guards remain in place until semantic coverage is proven.
- No broad rewrite of `postprocess.py` occurs in the first commit.

- [ ] **Step 5: Wire audit shadow diagnostics**

Update `run_chinese_surface_de_scaffold_audit.py` to report:

```text
legacy_detected_families
semantic_detected_families
semantic_only_matches
legacy_only_matches
replacement_candidate_available
```

Readiness remains:

```text
chinese_surface_de_scaffold_ready
```

for audit coverage; runtime replacement readiness should use a new label:

```text
chinese_semantic_descaffolding_phase1_ready
```

only after classifier tests and smoke packs pass.

- [ ] **Step 6: Run validation**

Run:

```powershell
python -m pytest tests/test_chinese_surface_de_scaffold_audit.py tests/test_subjective_review_pack.py tests/test_dialogue_mode_counterpart.py -q
python evals/run_chinese_surface_de_scaffold_audit.py --run-tag semantic-phase1
python evals/run_backend_freeze_gate_audit.py
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
```

Expected:

- Chinese audit passes.
- Backend freeze gate remains ready.

- [ ] **Step 7: Update docs and commit**

Run:

```powershell
git add AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md docs/superpowers/specs/2026-05-06-chinese-semantic-descaffolding-phase1-design.md docs/superpowers/plans/2026-05-06-chinese-semantic-descaffolding-phase1.md amadeus_thread0/graph_parts/chinese_semantic_surface.py amadeus_thread0/graph_parts/postprocess.py amadeus_thread0/graph_parts/rewrite.py evals/chinese_surface_residue_bank.json evals/run_chinese_surface_de_scaffold_audit.py tests/test_chinese_surface_de_scaffold_audit.py tests/test_subjective_review_pack.py tests/test_dialogue_mode_counterpart.py
git commit -m "test: add chinese semantic descaffolding phase 1"
```

---

## Task 6: Capability Growth Phase 5

**Goal:** Convert repeated completed procedural traces into bounded workflow candidates that can bias future planning or propose skills, without creating a second capability memory store.

**Files:**

- Create: `docs/superpowers/specs/2026-05-06-capability-growth-phase5-design.md`
- Create: `docs/superpowers/plans/2026-05-06-capability-growth-phase5.md`
- Create: `amadeus_thread0/graph_parts/capability_growth.py`
- Create: `evals/run_capability_growth_phase5_smokes.py`
- Create: `evals/run_capability_growth_phase5_audit.py`
- Create: `tests/test_capability_growth_phase5.py`
- Create: `tests/test_capability_growth_phase5_audit.py`
- Modify: `amadeus_thread0/graph_parts/procedural_growth.py`
- Modify: `amadeus_thread0/graph_parts/procedural_planning.py`
- Modify: `amadeus_thread0/graph_parts/procedural_outcome.py`
- Modify: `amadeus_thread0/graph_parts/procedural_recovery.py`
- Modify: `amadeus_thread0/graph_parts/autonomy_runtime.py`
- Modify: `amadeus_thread0/runtime/backend_api.py`
- Modify: `tests/test_procedural_growth.py`
- Modify: `tests/test_procedural_planning.py`
- Modify: `tests/test_autonomy_writeback.py`
- Modify: `tests/test_backend_api.py`
- Modify: `program.md`

- [ ] **Step 1: Write the phase spec**

The spec must define `WorkflowCandidate`:

```python
{
    "workflow_id": "workflow-...",
    "origin_trace_ids": ["proc-1", "proc-2"],
    "capability_family": "workspace|sandbox|browser|skill|multimodal",
    "reuse_confidence": 0.0,
    "approval_requirements": ["external_mutation"],
    "blocked_surfaces": [],
    "recommended_next_action": "reuse|propose_skill|ask_operator|hold",
    "status": "candidate",
}
```

Rules:

- Workflow candidates live inside the existing procedural/memory writeback substrate.
- They may bias planning only when current access/body state supports the same bounded family.
- They do not grant new tools.
- They do not install skills.

- [ ] **Step 2: Write failing workflow tests**

Create `tests/test_capability_growth_phase5.py`:

```python
def test_repeated_completed_traces_form_workflow_candidate():
    candidate = derive_workflow_candidate(
        [
            {"trace_id": "p1", "status": "completed", "capability_family": "workspace", "confidence": 0.82},
            {"trace_id": "p2", "status": "completed", "capability_family": "workspace", "confidence": 0.88},
        ]
    )
    assert candidate["status"] == "candidate"
    assert candidate["capability_family"] == "workspace"
    assert candidate["recommended_next_action"] in {"reuse", "propose_skill"}


def test_blocked_traces_cannot_become_capability_claim():
    candidate = derive_workflow_candidate(
        [{"trace_id": "p3", "status": "blocked", "capability_family": "sandbox", "confidence": 0.9}]
    )
    assert candidate["status"] == "blocked"
    assert "no_completed_evidence" in candidate["block_reasons"]
```

- [ ] **Step 3: Run red**

Run:

```powershell
python -m pytest tests/test_capability_growth_phase5.py -q
```

Expected:

- Fails because `capability_growth.py` does not exist.

- [ ] **Step 4: Implement capability growth helper**

Create `graph_parts/capability_growth.py` with:

```python
def derive_workflow_candidate(traces: list[dict]) -> dict:
    ...

def workflow_candidate_to_planning_bias(candidate: dict, digital_body_state: dict) -> dict:
    ...

def summarize_workflow_candidate(candidate: dict) -> str:
    ...
```

- [ ] **Step 5: Integrate with procedural planning**

Update procedural modules so:

- completed outcome-calibrated traces may form workflow candidates
- unresolved recovery keeps candidates in `hold` or `ask_operator`
- blocked boundary traces create boundary-only candidates
- backend envelopes expose `capability_growth` readback as advisory metadata

- [ ] **Step 6: Add smokes and audit**

Smoke scenarios:

```text
workspace_reuse_candidate
sandbox_candidate_preserves_approval
browser_candidate_preserves_manual_takeover
blocked_trace_boundary_only
dynamic_skill_candidate_path_is_proposal_only
```

Readiness:

```text
capability_growth_phase5_ready
```

- [ ] **Step 7: Run validation**

Run:

```powershell
python -m pytest tests/test_capability_growth_phase5.py tests/test_procedural_growth.py tests/test_procedural_planning.py tests/test_autonomy_writeback.py tests/test_backend_api.py -q
python -m pytest tests/test_capability_growth_phase5_audit.py -q
python evals/run_capability_growth_phase5_smokes.py --run-tag phase5-dev
python evals/run_capability_growth_phase5_audit.py --run-tag phase5-dev
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
```

Expected:

- Capability growth phase 5 audit reports `capability_growth_phase5_ready`.
- Preserved baselines remain ready.

- [ ] **Step 8: Update docs and commit**

Run:

```powershell
git add AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md docs/superpowers/specs/2026-05-06-capability-growth-phase5-design.md docs/superpowers/plans/2026-05-06-capability-growth-phase5.md amadeus_thread0/graph_parts/capability_growth.py amadeus_thread0/graph_parts/procedural_growth.py amadeus_thread0/graph_parts/procedural_planning.py amadeus_thread0/graph_parts/procedural_outcome.py amadeus_thread0/graph_parts/procedural_recovery.py amadeus_thread0/graph_parts/autonomy_runtime.py amadeus_thread0/runtime/backend_api.py evals/run_capability_growth_phase5_smokes.py evals/run_capability_growth_phase5_audit.py tests/test_capability_growth_phase5.py tests/test_capability_growth_phase5_audit.py tests/test_procedural_growth.py tests/test_procedural_planning.py tests/test_autonomy_writeback.py tests/test_backend_api.py
git commit -m "feat: add capability growth phase 5"
```

---

## Task 7: Natural Long-Horizon Calibration Phase 1

**Goal:** Evaluate and calibrate long-horizon companionship behavior across appraisal, own-rhythm, relationship continuity, embodied continuity, and final text/TTS parity without adding scene scripts.

**Files:**

- Create: `docs/superpowers/specs/2026-05-06-natural-long-horizon-calibration-phase1-design.md`
- Create: `docs/superpowers/plans/2026-05-06-natural-long-horizon-calibration-phase1.md`
- Create: `evals/long_horizon_calibration_bank.json`
- Create: `evals/run_natural_long_horizon_calibration_smokes.py`
- Create: `evals/run_natural_long_horizon_calibration_audit.py`
- Create: `tests/test_natural_long_horizon_calibration_audit.py`
- Modify: `amadeus_thread0/graph_parts/appraisal.py`
- Modify: `amadeus_thread0/graph_parts/behavior_runtime.py`
- Modify: `amadeus_thread0/graph_parts/relational_runtime.py`
- Modify: `amadeus_thread0/graph_parts/semantic_narrative.py`
- Modify: `tests/test_dialogue_mode_counterpart.py`
- Modify: `tests/test_subjective_review_pack.py`
- Modify: `tests/test_world_model_residue.py`
- Modify: `tests/test_tts_presence_timing_audit.py`
- Modify: `program.md`

- [ ] **Step 1: Write the phase spec**

The spec must define calibration packs:

```text
everyday_low_stakes_7_turns
repair_after_tension_9_turns
self_rhythm_boundary_8_turns
shared_work_continuity_10_turns
embodied_artifact_resume_8_turns
silence_and_deferred_return_6_turns
```

Metrics:

```text
final_text_tts_parity
no_duplicate_output
no_middle_state_leak
relationship_continuity_resurfaced
own_rhythm_not_subservient
boundary_not_punitive
embodied_context_truthful
generic_assistant_tone_absent
```

- [ ] **Step 2: Write failing audit tests**

Create `tests/test_natural_long_horizon_calibration_audit.py`:

```python
def test_calibration_bank_contains_required_packs():
    bank = load_calibration_bank(Path("evals/long_horizon_calibration_bank.json"))
    assert set(bank["packs"]) >= {
        "everyday_low_stakes_7_turns",
        "repair_after_tension_9_turns",
        "self_rhythm_boundary_8_turns",
        "shared_work_continuity_10_turns",
        "embodied_artifact_resume_8_turns",
        "silence_and_deferred_return_6_turns",
    }


def test_audit_fails_on_middle_state_leak():
    report = evaluate_calibration_results(
        [{"pack": "repair_after_tension_9_turns", "middle_state_leak": True}]
    )
    assert report["overall_status"] == "failed"
    assert "middle_state_leak" in report["failure_reasons"]
```

- [ ] **Step 3: Run red**

Run:

```powershell
python -m pytest tests/test_natural_long_horizon_calibration_audit.py -q
```

Expected:

- Fails because the audit runner and bank do not exist.

- [ ] **Step 4: Implement offline calibration bank and evaluator**

Create:

- `evals/long_horizon_calibration_bank.json`
- `evals/run_natural_long_horizon_calibration_smokes.py`
- `evals/run_natural_long_horizon_calibration_audit.py`

The first implementation may use deterministic recorded turn fixtures. It must not require live model calls for unit tests.

Readiness:

```text
natural_long_horizon_calibration_phase1_ready
```

- [ ] **Step 5: Add small calibration hooks only if audit identifies a targeted issue**

Allowed code changes:

- appraisal weighting over existing state fields
- behavior-family selection over existing agenda fields
- semantic narrative resurfacing over existing memory traces

Blocked code changes:

- new keyword scene scripts
- persona-core rewrite
- final text rewrite that diverges from TTS text
- hidden prompt sprawl

- [ ] **Step 6: Run validation**

Run:

```powershell
python -m pytest tests/test_natural_long_horizon_calibration_audit.py tests/test_dialogue_mode_counterpart.py tests/test_subjective_review_pack.py tests/test_world_model_residue.py tests/test_tts_presence_timing_audit.py -q
python evals/run_natural_long_horizon_calibration_smokes.py --run-tag phase1-dev
python evals/run_natural_long_horizon_calibration_audit.py --run-tag phase1-dev
python evals/run_backend_freeze_gate_audit.py
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
```

Expected:

- Natural long-horizon audit reports `natural_long_horizon_calibration_phase1_ready`.
- Freeze gate remains ready.
- TTS timing parity remains ready.

- [ ] **Step 7: Update docs and commit**

Run:

```powershell
git add AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md docs/superpowers/specs/2026-05-06-natural-long-horizon-calibration-phase1-design.md docs/superpowers/plans/2026-05-06-natural-long-horizon-calibration-phase1.md evals/long_horizon_calibration_bank.json evals/run_natural_long_horizon_calibration_smokes.py evals/run_natural_long_horizon_calibration_audit.py amadeus_thread0/graph_parts/appraisal.py amadeus_thread0/graph_parts/behavior_runtime.py amadeus_thread0/graph_parts/relational_runtime.py amadeus_thread0/graph_parts/semantic_narrative.py tests/test_natural_long_horizon_calibration_audit.py tests/test_dialogue_mode_counterpart.py tests/test_subjective_review_pack.py tests/test_world_model_residue.py tests/test_tts_presence_timing_audit.py
git commit -m "test: add natural long horizon calibration phase 1"
```

---

## Task 8: Post-Unlock Integration Gate

**Goal:** Add a single audit that tells maintainers which unlocked lanes are ready, in-progress, or still planned.

**Files:**

- Create: `evals/run_post_unlock_roadmap_audit.py`
- Create: `tests/test_post_unlock_roadmap_audit.py`
- Modify: `amadeus_thread0/runtime/post_baseline_closure.py`
- Modify: `evals/run_post_baseline_closure_audit.py`
- Modify: `evals/run_preserved_baselines_audit.py`
- Modify: `program.md`

- [ ] **Step 1: Write failing audit tests**

Create `tests/test_post_unlock_roadmap_audit.py`:

```python
def test_lane_statuses_include_all_unlocked_lanes():
    report = evaluate_post_unlock_roadmap({})
    assert set(report["lanes"]) == {
        "multimodal_capture_phase1",
        "dynamic_skills_phase1",
        "external_executor_harness_phase1",
        "frontend_runtime_shell_phase1",
        "chinese_semantic_descaffolding_phase1",
        "capability_growth_phase5",
        "natural_long_horizon_calibration_phase1",
    }


def test_missing_lane_reports_keep_overall_in_progress():
    report = evaluate_post_unlock_roadmap({})
    assert report["overall_status"] == "in_progress"
    assert report["readiness_status"] == "post_unlock_roadmap_in_progress"
```

- [ ] **Step 2: Run red**

Run:

```powershell
python -m pytest tests/test_post_unlock_roadmap_audit.py -q
```

Expected:

- Fails because `run_post_unlock_roadmap_audit.py` does not exist.

- [ ] **Step 3: Implement roadmap audit**

Create `evals/run_post_unlock_roadmap_audit.py` with:

```python
LANE_SPECS = {
    "multimodal_capture_phase1": ("multimodal-capture-audit-", "multimodal_capture_phase1_ready"),
    "dynamic_skills_phase1": ("dynamic-skills-audit-", "dynamic_skills_phase1_ready"),
    "external_executor_harness_phase1": ("external-executor-harness-audit-", "external_executor_harness_phase1_ready"),
    "frontend_runtime_shell_phase1": ("frontend-runtime-shell-audit-", "frontend_runtime_shell_phase1_ready"),
    "chinese_semantic_descaffolding_phase1": ("chinese-surface-de-scaffold-audit-", "chinese_semantic_descaffolding_phase1_ready"),
    "capability_growth_phase5": ("capability-growth-phase5-audit-", "capability_growth_phase5_ready"),
    "natural_long_horizon_calibration_phase1": ("natural-long-horizon-calibration-audit-", "natural_long_horizon_calibration_phase1_ready"),
}
```

Rules:

- Missing lane reports are `planned`.
- Failed latest reports are `in_progress` or `regressed`.
- Ready latest reports are `ready`.
- Overall status is `passed` only when every lane is ready and preserved baselines are ready.

- [ ] **Step 4: Integrate status docs**

Update `post_baseline_closure.py` so `unlocked_planned` can be upgraded by lane readiness reports without changing the meaning of `runtime_available=False` for not-yet-ready lanes.

- [ ] **Step 5: Run validation**

Run:

```powershell
python -m pytest tests/test_post_unlock_roadmap_audit.py tests/test_post_baseline_closure.py tests/test_post_baseline_closure_audit.py tests/test_preserved_baselines_audit.py -q
python evals/run_post_unlock_roadmap_audit.py --reports-dir evals/reports
python evals/run_post_baseline_closure_audit.py --run-tag post-unlock-roadmap
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
```

Expected:

- Roadmap audit reports planned/in-progress/ready accurately.
- Preserved baselines remain ready.

- [ ] **Step 6: Update docs and commit**

Run:

```powershell
git add AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md amadeus_thread0/runtime/post_baseline_closure.py evals/run_post_unlock_roadmap_audit.py evals/run_post_baseline_closure_audit.py evals/run_preserved_baselines_audit.py tests/test_post_unlock_roadmap_audit.py tests/test_post_baseline_closure.py tests/test_post_baseline_closure_audit.py tests/test_preserved_baselines_audit.py
git commit -m "test: add post unlock roadmap audit"
```

---

## Full Regression Checkpoints

Run before merging any lane:

```powershell
python -m pytest tests/test_post_baseline_closure.py tests/test_post_baseline_closure_audit.py tests/test_preserved_baselines_audit.py -q
python -m py_compile amadeus_thread0/agent.py amadeus_thread0/graph.py
@'
from amadeus_thread0.agent import agent
print(type(agent).__name__)
'@ | python -
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
```

Expected:

- Tests pass.
- Graph build prints `CompiledStateGraph`.
- Preserved-baselines readiness is `preserved_baselines_ready`.

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

Run after sandbox/executor changes:

```powershell
python -m pytest tests/test_sandbox_runner.py tests/test_docker_sandbox_runner.py tests/test_sandbox_execution_runtime.py tests/test_sandbox_backend_contract.py tests/test_sandbox_phase2_backend_contract.py tests/test_sandbox_phase2_repo_fixture.py -q
python -m pytest tests/test_sandbox_phase2_smokes.py -q
python evals/run_sandbox_phase2_smokes.py --run-tag post-unlock-check
python evals/run_sandbox_phase2_audit.py --run-tag post-unlock-check
```

Run after frontend changes:

```powershell
python -m pytest tests/test_frontend_contract_sync.py tests/test_backend_api.py tests/test_backend_session.py -q
npm --prefix frontend run build
```

Run after Chinese semantic changes:

```powershell
python -m pytest tests/test_chinese_surface_de_scaffold_audit.py tests/test_subjective_review_pack.py tests/test_dialogue_mode_counterpart.py -q
python evals/run_chinese_surface_de_scaffold_audit.py --run-tag post-unlock-check
python evals/run_backend_freeze_gate_audit.py
```

## Parallel Work Split

After Task 0:

- Worker A may own Multimodal Capture Phase 1.
- Worker B may own Frontend Runtime Shell Phase 1.
- Worker C may own Chinese Semantic De-Scaffolding Phase 1.
- Worker D may own External Executor Harness Phase 1.

Do not run Dynamic Skills Phase 1 and Capability Growth Phase 5 in the same write set. Dynamic skills owns registry/candidate proposal. Capability growth owns workflow candidates and planning bias. If both proceed in parallel, their write sets must be split and integrated through `autonomy_runtime.py` in a final coordination branch.

## Merge Policy

For each lane:

1. Create `codex/<lane-name>` from current `main`.
2. Implement the lane plan with TDD.
3. Run lane audit.
4. Run preserved-baseline meta-audit.
5. Update `program.md`.
6. Commit.
7. Merge to `main`.
8. Run the same validation on merged `main`.

Do not merge a lane with a failing preserved-baseline meta-audit unless the failure is a missing gitignored report artifact and the lane-specific validation has a separate authoritative ready report.

## Success Definition

The post-unlock roadmap is fully complete when:

- every lane has a phase-specific spec and implementation plan
- every lane has an audit runner and at least one ready report
- `evals/run_post_unlock_roadmap_audit.py` reports all lanes ready
- `evals/run_preserved_baselines_audit.py --reports-dir evals/reports` reports `preserved_baselines_ready`
- `AGENTS.md`, `program.md`, `PROJECT_STRUCTURE.md`, and `AMADEUS_ARCHITECTURE_DECISIONS.md` agree on the new preserved statuses
- frontend consumes `backend.v1` and does not define alternate backend truth
- Chinese semantic de-scaffolding has audit-backed semantic diagnostics before runtime rewrite
- multimodal capture remains consent-bound and source-artifact-bound
- dynamic skills remain proposal/approval/hash-gated
- external harnesses remain fail-closed until separately enabled
- capability growth remains procedural/body continuity, not persona identity
- natural long-horizon calibration evaluates the whole lifeform loop rather than final text alone
