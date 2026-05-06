# Dynamic Skills Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the approved dynamic skill candidate loop: frozen candidate payload -> operator approval -> exact registry install/enable -> session readback -> completed-use continuity.

**Architecture:** Keep dynamic skills inside the existing digital-body skills ecology. Candidate creation remains proposal-only; registry writes happen only through an explicit frozen approval payload verified against a deterministic hash. Installed candidates reuse `SkillRegistryManager`, session activation, `backend_skill_envelope`, and procedural continuity rather than creating a second skill or memory substrate.

**Tech Stack:** Python 3, LangChain tool wrappers, existing `SkillRegistryManager`, pytest, deterministic eval scripts.

---

## File Structure

- `amadeus_thread0/runtime/dynamic_skill_candidates.py`: normalize dynamic candidate payloads, freeze candidates, build install action packets, and verify approval payloads.
- `amadeus_thread0/runtime/skill_registry.py`: install a verified dynamic candidate into the existing installed-skill layout and optionally enable it for a session.
- `amadeus_thread0/graph_parts/skill_runtime.py`: expose candidate metadata in pending skill proposals and completed skill effects.
- `amadeus_thread0/utils/tools.py`: allow `install_skill` and `preview_skill_operation` to carry a frozen `candidate_payload`.
- `tests/test_dynamic_skills_phase2.py`: phase-level RED/GREEN coverage for freeze, approval, install, rejected/pending/blocked non-activation, and continuity.
- `tests/test_skill_registry.py`: registry-level coverage for `install_candidate()`.
- `tests/test_skill_runtime.py`: pending proposal/readback coverage for dynamic candidate metadata.
- `evals/run_dynamic_skills_phase2_audit.py`: deterministic audit scenarios for approved install, rejected install, manual disable precedence, pin precedence, and follow-up continuity.
- `evals/run_preserved_baselines_audit.py` and `tests/test_preserved_baselines_audit.py`: add the preserved baseline row after a Phase 2 ready report exists.
- Docs/status: `AGENTS.md`, `docs/engineering/PROJECT_STRUCTURE.md`, `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`, `program.md`.

---

### Task 1: Candidate Freeze And Approval Packet

**Files:**
- Modify: `amadeus_thread0/runtime/dynamic_skill_candidates.py`
- Create: `tests/test_dynamic_skills_phase2.py`

- [ ] **Step 1: Write failing tests for frozen candidate stability**

Add these tests to `tests/test_dynamic_skills_phase2.py`:

```python
from amadeus_thread0.runtime.dynamic_skill_candidates import (
    build_candidate_install_packet,
    freeze_skill_candidate_payload,
    propose_skill_candidate_from_trace,
    verify_candidate_approval,
)


def _candidate():
    return propose_skill_candidate_from_trace(
        {
            "trace_id": "trace-skill-1",
            "status": "completed",
            "summary": "Use rg to inspect pytest failures before editing.",
            "skill_id": "pytest-failure-review",
            "requested_permissions": ["filesystem_read", "filesystem_read"],
            "sandbox_profiles": ["docker_local_isolated"],
        }
    )


def test_candidate_freeze_preserves_hash_version_and_permissions():
    frozen = freeze_skill_candidate_payload(_candidate())
    packet = build_candidate_install_packet(frozen)
    verification = verify_candidate_approval(frozen, packet["tool_args"]["candidate_payload"])

    assert frozen["schema"] == "dynamic_skill_candidate.v1"
    assert frozen["status"] == "frozen"
    assert frozen["version"] == "0.1.0"
    assert frozen["requested_permissions"] == ["filesystem_read"]
    assert frozen["sandbox_profiles"] == ["docker_local_isolated"]
    assert frozen["hash"].startswith("sha256:")
    assert packet["intent"] == "skills:install"
    assert packet["status"] == "awaiting_approval"
    assert packet["risk"] == "external_mutation"
    assert packet["requires_approval"] is True
    assert packet["tool_args"]["candidate_id"] == frozen["candidate_id"]
    assert packet["tool_args"]["hash"] == frozen["hash"]
    assert verification["verified"] is True


def test_candidate_approval_detects_payload_drift():
    frozen = freeze_skill_candidate_payload(_candidate())
    drifted = {**frozen, "version": "9.9.9"}

    verification = verify_candidate_approval(frozen, drifted)

    assert verification["verified"] is False
    assert "version_drift" in verification["failure_reasons"]
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_dynamic_skills_phase2.py -q
```

Expected: FAIL because `freeze_skill_candidate_payload`, `build_candidate_install_packet`, and `verify_candidate_approval` do not exist yet.

- [ ] **Step 3: Implement minimal candidate freeze helpers**

In `amadeus_thread0/runtime/dynamic_skill_candidates.py`, add:

```python
def freeze_skill_candidate_payload(candidate: dict[str, Any] | None) -> dict[str, Any]:
    ...


def build_candidate_install_packet(candidate: dict[str, Any] | None, *, origin: str = "capability_upgrade") -> dict[str, Any]:
    ...


def verify_candidate_approval(candidate: dict[str, Any] | None, approval_payload: dict[str, Any] | None) -> dict[str, Any]:
    ...
```

The frozen payload must include `schema`, `candidate_id`, `skill_id`, `version`, `draft_skill_md`, `source_evidence_refs`, `requested_permissions`, `sandbox_profiles`, `hash`, `status="frozen"`, `requires_approval=True`, and `registry_written=False`. The install packet must use `tool_name="install_skill"`, `intent="skills:install"`, `risk="external_mutation"`, and `status="awaiting_approval"`.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_dynamic_skills_phase2.py tests/test_dynamic_skill_candidates.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add amadeus_thread0/runtime/dynamic_skill_candidates.py tests/test_dynamic_skills_phase2.py
git commit -m "feat: freeze dynamic skill candidates"
```

---

### Task 2: Registry Install From Frozen Candidate

**Files:**
- Modify: `amadeus_thread0/runtime/skill_registry.py`
- Modify: `amadeus_thread0/utils/tools.py`
- Modify: `tests/test_dynamic_skills_phase2.py`
- Modify: `tests/test_skill_registry.py`

- [ ] **Step 1: Write failing tests for exact frozen install**

Add:

```python
import json
import tempfile
from pathlib import Path

import pytest

from amadeus_thread0.runtime.skill_registry import SkillRegistryError, SkillRegistryManager


def test_registry_installs_and_enables_exact_frozen_candidate():
    with tempfile.TemporaryDirectory() as tmp:
        manager = SkillRegistryManager(base_dir=Path(tmp) / "repo", data_dir=Path(tmp) / "data")
        frozen = freeze_skill_candidate_payload(_candidate())

        result = manager.install_candidate(frozen, frozen, thread_id="thread-dyn", enable=True)
        state = manager.compute_session_skill_state(thread_id="thread-dyn", query_text="pytest failures")
        lock_payload = json.loads(
            (Path(tmp) / "data" / "skills" / "installed" / "pytest-failure-review" / "0.1.0" / "skill.lock.json").read_text(
                encoding="utf-8"
            )
        )

        assert result["status"] == "installed"
        assert result["enabled"] is True
        assert result["hash"] == frozen["hash"]
        assert state["active_skill_ids"] == ["pytest-failure-review"]
        assert lock_payload["source"] == "dynamic_candidate"
        assert lock_payload["candidate_id"] == frozen["candidate_id"]


def test_registry_rejects_candidate_install_when_approval_payload_drifts():
    with tempfile.TemporaryDirectory() as tmp:
        manager = SkillRegistryManager(base_dir=Path(tmp) / "repo", data_dir=Path(tmp) / "data")
        frozen = freeze_skill_candidate_payload(_candidate())
        drifted = {**frozen, "hash": "sha256:" + "0" * 64}

        with pytest.raises(SkillRegistryError):
            manager.install_candidate(frozen, drifted, thread_id="thread-dyn", enable=True)

        assert manager.runtime_catalog() == []
        assert manager.compute_session_skill_state(thread_id="thread-dyn")["active_skill_ids"] == []
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_dynamic_skills_phase2.py -q
```

Expected: FAIL because `SkillRegistryManager.install_candidate()` is missing.

- [ ] **Step 3: Implement candidate install**

Add `SkillRegistryManager.install_candidate(candidate, approval_payload, thread_id="", enable=False)` that:

- verifies `verify_candidate_approval(candidate, approval_payload)["verified"]`;
- writes `SKILL.md` to `self.installed_root / skill_id / version`;
- loads the skill through `_load_skill_directory(...)`;
- sets `source="dynamic_candidate"`, `trust_tier="approved_candidate"`, `hash`, `requested_permissions`, `sandbox_profiles`, `verification_summary`, `candidate_id`, and `source_evidence_refs`;
- writes `skill.lock.json`;
- calls `_upsert_installed_registry_entry(installed)`;
- calls `enable(skill_id=..., thread_id=...)` only when `enable=True` and `thread_id` is non-empty.

Also extend `install_skill(...)` in `amadeus_thread0/utils/tools.py` to accept optional `candidate_payload: dict[str, Any] | None = None`; when present, route to `manager.install_candidate(candidate_payload, candidate_payload, thread_id=thread_id, enable=enable)`.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_dynamic_skills_phase2.py tests/test_skill_registry.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add amadeus_thread0/runtime/skill_registry.py amadeus_thread0/utils/tools.py tests/test_dynamic_skills_phase2.py tests/test_skill_registry.py
git commit -m "feat: install approved dynamic skill candidates"
```

---

### Task 3: Runtime Proposal And Continuity Readback

**Files:**
- Modify: `amadeus_thread0/graph_parts/skill_runtime.py`
- Modify: `amadeus_thread0/utils/tools.py`
- Modify: `tests/test_skill_runtime.py`
- Modify: `tests/test_dynamic_skills_phase2.py`

- [ ] **Step 1: Write failing tests for pending proposal and continuity**

Add tests that assert:

```python
from amadeus_thread0.graph_parts.skill_runtime import backend_skill_envelope, derive_procedural_continuity, derive_skill_effects


def test_pending_dynamic_candidate_proposal_surfaces_candidate_metadata_without_activation():
    frozen = freeze_skill_candidate_payload(_candidate())
    packet = build_candidate_install_packet(frozen)
    envelope = backend_skill_envelope(
        {"catalog_entries": [], "active_skill_entries": []},
        pending_action_proposal=packet,
    )

    assert envelope["active"] == []
    assert envelope["pending_approval"]["candidate_id"] == frozen["candidate_id"]
    assert envelope["pending_approval"]["candidate_hash"] == frozen["hash"]
    assert envelope["pending_approval"]["source"] == "dynamic_candidate"


def test_completed_dynamic_skill_use_resurfaces_only_after_actual_use():
    state = {
        "active_skill_entries": [
            {
                "skill_id": "pytest-failure-review",
                "name": "pytest-failure-review",
                "version": "0.1.0",
                "source": "dynamic_candidate",
                "trust_tier": "approved_candidate",
                "allowed_tools": ["execute_workspace_command"],
            }
        ]
    }
    effects = derive_skill_effects(
        state,
        [{"tool_name": "execute_workspace_command", "status": "completed", "proposal_id": "ap-use-1"}],
    )
    continuity = derive_procedural_continuity(
        {
            "kind": "skill_usage_completed",
            "primary_status": "completed",
            "primary_tool_name": "execute_workspace_command",
            "primary_proposal_id": "ap-use-1",
            "skill_effects": effects,
        }
    )

    assert effects[0]["operation"] == "use"
    assert effects[0]["source"] == "dynamic_candidate"
    assert continuity["capability_family"] == "skill"
    assert continuity["last_success_ref"] == "ap-use-1"
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_dynamic_skills_phase2.py tests/test_skill_runtime.py -q
```

Expected: FAIL until candidate metadata is copied into pending proposal readback.

- [ ] **Step 3: Implement runtime readback**

Extend `pending_skill_proposal_from_state()` to copy `candidate_id`, `candidate_hash`, `candidate_payload_schema`, and `dynamic_candidate=True` from `tool_args["candidate_payload"]`. Extend `preview_skill_operation()` so a frozen `candidate_payload` returns a `skill_preview` without querying remote catalog.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_dynamic_skills_phase2.py tests/test_skill_runtime.py tests/test_tool_approval_policy.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add amadeus_thread0/graph_parts/skill_runtime.py amadeus_thread0/utils/tools.py tests/test_dynamic_skills_phase2.py tests/test_skill_runtime.py tests/test_tool_approval_policy.py
git commit -m "feat: read back dynamic skill candidate approvals"
```

---

### Task 4: Audit And Preserved Baseline

**Files:**
- Create: `evals/run_dynamic_skills_phase2_audit.py`
- Modify: `evals/run_preserved_baselines_audit.py`
- Modify: `tests/test_preserved_baselines_audit.py`
- Create: `tests/test_dynamic_skills_phase2_audit.py`

- [ ] **Step 1: Write failing audit tests**

Add `tests/test_dynamic_skills_phase2_audit.py`:

```python
from evals.run_dynamic_skills_phase2_audit import evaluate_scenarios, run_scenarios


def test_dynamic_skills_phase2_audit_reaches_ready():
    report = evaluate_scenarios(run_scenarios())

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == "dynamic_skills_phase2_ready"
```

Update `tests/test_preserved_baselines_audit.py` expected ids to include `dynamic_skills_phase2` and expected `skills` category count to `2`.

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_dynamic_skills_phase2_audit.py tests/test_preserved_baselines_audit.py -q
```

Expected: FAIL because the new audit file and baseline row do not exist yet.

- [ ] **Step 3: Implement deterministic audit**

Create `evals/run_dynamic_skills_phase2_audit.py` with scenarios:

- `approved_install_enable_candidate`: frozen candidate installs and becomes active after approval;
- `rejected_install_not_active`: rejected packet or drifted approval never installs;
- `manual_disable_precedence`: manual disable removes the dynamic skill from active ids even if query matches;
- `pin_precedence`: pinned dynamic skill stays first in active ids;
- `followup_continuity_from_completed_use`: completed skill use derives identity-safe procedural continuity.

Write JSON and Markdown reports under `evals/reports/dynamic-skills-phase2-audit-<run_id>.{json,md}` and return `dynamic_skills_phase2_ready` only when all scenarios pass.

- [ ] **Step 4: Add preserved baseline row**

Add:

```python
{
    "id": "dynamic_skills_phase2",
    "prefix": "dynamic-skills-phase2-audit-",
    "expected_readiness": "dynamic_skills_phase2_ready",
    "category": "skills",
}
```

- [ ] **Step 5: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_dynamic_skills_phase2_audit.py tests/test_preserved_baselines_audit.py -q
python evals/run_dynamic_skills_phase2_audit.py --run-tag phase2-dev
```

Expected: PASS and readiness `dynamic_skills_phase2_ready`.

- [ ] **Step 6: Commit**

Run:

```powershell
git add evals/run_dynamic_skills_phase2_audit.py evals/run_preserved_baselines_audit.py tests/test_dynamic_skills_phase2_audit.py tests/test_preserved_baselines_audit.py
git commit -m "test: audit dynamic skills phase 2"
```

---

### Task 5: Docs, Regression Verification, Merge, Push

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `program.md`
- Modify: `docs/superpowers/plans/2026-05-07-dynamic-skills-phase2.md`

- [ ] **Step 1: Update project state docs**

Record `dynamic_skills_phase2_ready` as a closed bounded gate. State explicitly that it:

- installs only frozen approved dynamic candidates;
- writes only the existing skills registry, not autobiographical memory;
- respects manual disable and pin precedence;
- does not auto-write the registry from proposal, mutate persona core, widen sandbox/browser/tool authority, or create a second memory substrate.

- [ ] **Step 2: Run focused verification**

Run:

```powershell
python -m pytest tests/test_dynamic_skill_candidates.py tests/test_dynamic_skills_phase2.py tests/test_skill_registry.py tests/test_skill_runtime.py tests/test_tool_approval_policy.py -q
python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py tests/test_tool_approval_policy.py -q
python -m py_compile amadeus_thread0/runtime/dynamic_skill_candidates.py amadeus_thread0/runtime/skill_registry.py amadeus_thread0/graph_parts/skill_runtime.py amadeus_thread0/utils/tools.py evals/run_dynamic_skills_phase2_audit.py evals/run_preserved_baselines_audit.py
python evals/run_dynamic_skills_phase2_audit.py --run-tag phase2-final
python evals/run_skills_ecosystem_audit.py --run-tag dynamic-phase2-regression
python evals/run_multimodal_perception_phase2_audit.py --run-tag dynamic-skills-phase2-regression
git diff --check
```

Expected: all commands exit `0`.

- [ ] **Step 3: Commit docs**

Run:

```powershell
git add AGENTS.md docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md program.md docs/superpowers/plans/2026-05-07-dynamic-skills-phase2.md
git commit -m "docs: record dynamic skills phase 2"
```

- [ ] **Step 4: Merge and verify on main**

Run:

```powershell
cd E:\桌面\amadeus-thread0
git merge --ff-only codex/dynamic-skills-phase2
python -m pytest tests/test_dynamic_skills_phase2.py tests/test_skill_runtime.py tests/test_backend_api.py -k "skill or dynamic" -q
python evals/run_dynamic_skills_phase2_audit.py --run-tag post-merge
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
git diff --check
```

Expected: all commands exit `0`.

- [ ] **Step 5: Push main**

Run:

```powershell
git push origin main
```

Expected: push succeeds.

