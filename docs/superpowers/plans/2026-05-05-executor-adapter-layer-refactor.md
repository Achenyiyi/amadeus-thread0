# Executor Adapter Layer Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor Amadeus-K's bounded execution surface into a stable executor adapter layer so the current Docker/local sandbox remains the canonical implementation while future Deep Agents, Codex, Claude Code, or OpenClaw-style harnesses can be evaluated behind the same action-packet and digital-body contract.

**Architecture:** Keep the existing LangGraph persona loop authoritative. Add a narrow runtime-owned `executor_adapter` module that normalizes `execution_spec`, dispatches only approved adapter kinds, and returns the same `execution_preview` / `execution_result` surfaces already used by `sandbox:execute_workspace_command`. The first implementation wraps the existing sandbox runner with no behavior widening; later tasks add disabled-by-default harness stubs and audit coverage so external agents cannot become a second memory, session, tool, or persona truth model.

**Tech Stack:** Python 3, pytest, existing LangGraph backend, existing `action_packets`, `sandbox_runner`, `execute_workspace_command`, backend envelopes, eval smoke/audit runners, no new runtime dependency in this plan.

---

## Refactor Boundary

This plan upgrades the execution architecture without importing OpenClaw, Deep Agents, Codex, or Claude Code into runtime behavior.

Preserved invariants:

- `Amadeus-K LangGraph core` remains the only owner of persona state, appraisal, motives, final behavior semantics, memory writeback, and self-narrative.
- `action_packets` remain the only structured action unit.
- `sandbox:execute_workspace_command` keeps `risk=external_mutation` and remains approval-gated.
- Current phase-2 execution constraints remain unchanged:
  - `runner_kind=docker_isolated_runner`
  - `isolation_level=docker_local_isolated`
  - `network_policy=none`
  - allowed command families: `python`, `pytest`, `rg`, read-only `git`
  - blocked: shell wrappers, package managers, package install, git mutation, Docker socket mounting, privileged containers, host secret passthrough
- External harnesses must not own Amadeus-K memory, identity, skills registry truth, browser state, or session continuity.

Target shape:

```text
Amadeus-K LangGraph core
  -> action_packet with frozen execution_spec
  -> runtime.executor_adapter
  -> sandbox runner or disabled harness adapter
  -> execution_result
  -> digital_body_consequence / reconsolidation
```

---

## File Ownership Map

- New executor adapter boundary:
  - Create: `amadeus_thread0/runtime/executor_adapter.py`
  - Test: `tests/test_executor_adapter.py`

- Existing sandbox execution integration:
  - Modify: `amadeus_thread0/utils/tools.py`
  - Test: `tests/test_sandbox_execution_runtime.py`
  - Test: `tests/test_sandbox_runner.py`

- Action-packet schema and normalization:
  - Modify: `amadeus_thread0/graph_parts/action_packets.py`
  - Modify: `amadeus_thread0/graph_parts/state.py`
  - Test: `tests/test_action_packet_contract.py`

- Backend / CLI contract readback:
  - Modify: `amadeus_thread0/runtime/final_state.py`
  - Modify: `amadeus_thread0/runtime/backend_api.py`
  - Modify: `amadeus_thread0/utils/cli_views.py`
  - Test: `tests/test_backend_api.py`
  - Test: `tests/test_backend_session.py`
  - Test: `tests/test_cli_views.py`

- Architecture docs:
  - Modify: `docs/engineering/PROJECT_STRUCTURE.md`
  - Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
  - Modify: `docs/engineering/BACKEND_HANDOFF.md`

- Evaluation closure:
  - Create: `evals/run_executor_adapter_audit.py`
  - Test: `tests/test_executor_adapter_audit.py`
  - Modify: `program.md`

---

## Task 1: Add the executor adapter boundary around the existing sandbox runner

**Files:**
- Create: `amadeus_thread0/runtime/executor_adapter.py`
- Test: `tests/test_executor_adapter.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_executor_adapter.py` with these tests:

```python
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from amadeus_thread0.runtime.executor_adapter import (
    EXECUTOR_ADAPTER_SANDBOX,
    ExecutorAdapterError,
    ExecutorRequest,
    build_executor_preview,
    execute_executor_request,
)
from amadeus_thread0.runtime.sandbox_runner import LOCAL_RUNNER_KIND


def test_executor_adapter_builds_sandbox_preview_without_running_command():
    with TemporaryDirectory() as td:
        workspace = Path(td) / "workspace"
        workspace.mkdir(parents=True)

        request = ExecutorRequest(
            adapter_kind=EXECUTOR_ADAPTER_SANDBOX,
            proposal_id="ap-exec-preview",
            argv=["python", "check.py"],
            cwd=".",
            allowed_roots=[str(workspace)],
            timeout_s=25,
            writes_expected=False,
            expected_artifacts=[],
            runner_kind=LOCAL_RUNNER_KIND,
            image_ref="",
            network_policy="",
            workspace_root_kind="runtime_owned",
        )

        preview = build_executor_preview(request)

        assert preview["adapter_kind"] == "sandbox_runner"
        assert preview["runner_kind"] == "local_restricted_runner"
        assert preview["isolation_level"] == "host_local_restricted"
        assert preview["argv"] == ["python", "check.py"]
        assert preview["cwd"] == str(workspace)
        assert preview["allowed_roots"] == [str(workspace)]
        assert preview["network_policy"] == "host"
        assert preview["memory_policy"] == "no_executor_memory"


def test_executor_adapter_executes_existing_sandbox_runner_and_preserves_result_shape():
    with TemporaryDirectory() as td:
        workspace = Path(td) / "workspace"
        workspace.mkdir(parents=True)
        (workspace / "emit.py").write_text("print('adapter-ok')\n", encoding="utf-8")

        request = ExecutorRequest(
            adapter_kind=EXECUTOR_ADAPTER_SANDBOX,
            proposal_id="ap-exec-run",
            argv=["python", "emit.py"],
            cwd=".",
            allowed_roots=[str(workspace)],
            timeout_s=25,
            writes_expected=False,
            expected_artifacts=[],
            runner_kind=LOCAL_RUNNER_KIND,
            image_ref="",
            network_policy="",
            workspace_root_kind="runtime_owned",
        )

        payload = execute_executor_request(request, run_root=workspace / ".amadeus" / "executor-runs" / "ap-exec-run")

        assert payload["adapter_kind"] == "sandbox_runner"
        assert payload["execution_spec"]["runner_kind"] == "local_restricted_runner"
        assert payload["execution_preview"]["adapter_kind"] == "sandbox_runner"
        assert payload["execution_result"]["run_id"] == "ap-exec-run"
        assert payload["execution_result"]["status"] == "completed"
        assert payload["execution_result"]["exit_code"] == 0
        assert Path(payload["execution_result"]["stdout_log_ref"]).read_text(encoding="utf-8") == "adapter-ok\n"
        assert payload["writeback_policy"] == "completed_results_only"
        assert payload["memory_policy"] == "no_executor_memory"


def test_executor_adapter_blocks_unknown_or_disabled_harnesses_before_execution():
    with TemporaryDirectory() as td:
        workspace = Path(td) / "workspace"
        workspace.mkdir(parents=True)
        request = ExecutorRequest(
            adapter_kind="codex_harness",
            proposal_id="ap-exec-disabled",
            argv=["python", "emit.py"],
            cwd=".",
            allowed_roots=[str(workspace)],
            timeout_s=25,
            writes_expected=False,
            expected_artifacts=[],
            runner_kind=LOCAL_RUNNER_KIND,
            image_ref="",
            network_policy="",
            workspace_root_kind="runtime_owned",
        )

        with pytest.raises(ExecutorAdapterError) as exc:
            execute_executor_request(request, run_root=workspace / ".amadeus" / "executor-runs" / "ap-exec-disabled")

        assert exc.value.code == "EXECUTOR_ADAPTER_DISABLED"
        assert "codex_harness" in str(exc.value)


def test_executor_adapter_does_not_call_sandbox_execute_for_disabled_harness():
    with TemporaryDirectory() as td:
        workspace = Path(td) / "workspace"
        workspace.mkdir(parents=True)
        request = ExecutorRequest(
            adapter_kind="deep_agents",
            proposal_id="ap-exec-disabled",
            argv=["python", "emit.py"],
            cwd=".",
            allowed_roots=[str(workspace)],
            timeout_s=25,
            writes_expected=False,
            expected_artifacts=[],
            runner_kind=LOCAL_RUNNER_KIND,
            image_ref="",
            network_policy="",
            workspace_root_kind="runtime_owned",
        )

        with patch("amadeus_thread0.runtime.executor_adapter.execute_sandbox_command") as execute_sandbox:
            with pytest.raises(ExecutorAdapterError):
                execute_executor_request(request, run_root=workspace / ".amadeus" / "executor-runs" / "ap-exec-disabled")

        execute_sandbox.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_executor_adapter.py -q
```

Expected:

- FAIL with `ModuleNotFoundError: No module named 'amadeus_thread0.runtime.executor_adapter'`.

- [ ] **Step 3: Add the minimal adapter implementation**

Create `amadeus_thread0/runtime/executor_adapter.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .sandbox_runner import (
    SandboxValidationError,
    build_execution_preview,
    build_sandbox_command_spec,
    execute_sandbox_command,
)

EXECUTOR_ADAPTER_SANDBOX = "sandbox_runner"
EXECUTOR_ADAPTER_DEEP_AGENTS = "deep_agents"
EXECUTOR_ADAPTER_CODEX = "codex_harness"
EXECUTOR_ADAPTER_CLAUDE = "claude_harness"
SUPPORTED_EXECUTOR_ADAPTERS = {EXECUTOR_ADAPTER_SANDBOX}
DISABLED_HARNESS_ADAPTERS = {
    EXECUTOR_ADAPTER_DEEP_AGENTS,
    EXECUTOR_ADAPTER_CODEX,
    EXECUTOR_ADAPTER_CLAUDE,
}


class ExecutorAdapterError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = str(code or "EXECUTOR_ADAPTER_ERROR").strip().upper() or "EXECUTOR_ADAPTER_ERROR"


@dataclass(frozen=True)
class ExecutorRequest:
    adapter_kind: str
    proposal_id: str
    argv: list[str]
    cwd: str
    allowed_roots: list[str]
    timeout_s: int
    writes_expected: bool
    expected_artifacts: list[str]
    runner_kind: str
    image_ref: str
    network_policy: str
    workspace_root_kind: str


def _clean_adapter_kind(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text or EXECUTOR_ADAPTER_SANDBOX


def _assert_adapter_enabled(adapter_kind: str) -> None:
    kind = _clean_adapter_kind(adapter_kind)
    if kind in SUPPORTED_EXECUTOR_ADAPTERS:
        return
    if kind in DISABLED_HARNESS_ADAPTERS:
        raise ExecutorAdapterError(
            "EXECUTOR_ADAPTER_DISABLED",
            f"{kind} is documented for future evaluation but is disabled in this runtime",
        )
    raise ExecutorAdapterError("EXECUTOR_ADAPTER_UNKNOWN", f"unknown executor adapter: {kind}")


def _sandbox_spec_from_request(request: ExecutorRequest):
    return build_sandbox_command_spec(
        argv=list(request.argv),
        cwd=request.cwd,
        allowed_roots=list(request.allowed_roots),
        timeout_s=request.timeout_s,
        writes_expected=request.writes_expected,
        expected_artifacts=list(request.expected_artifacts),
        runner_kind=request.runner_kind,
        image_ref=request.image_ref,
        network_policy=request.network_policy,
        workspace_root_kind=request.workspace_root_kind,
    )


def _execution_spec_payload(spec) -> dict[str, Any]:
    return {
        "executor": spec.executor,
        "profile": spec.profile,
        "runner_kind": spec.runner_kind,
        "isolation_level": spec.isolation_level,
        "image_ref": spec.image_ref,
        "network_policy": spec.network_policy,
        "workspace_root_kind": spec.workspace_root_kind,
        "argv": list(spec.argv),
        "cwd": spec.cwd,
        "allowed_roots": list(spec.allowed_roots),
        "timeout_s": spec.timeout_s,
        "writes_expected": spec.writes_expected,
        "expected_artifacts": list(spec.expected_artifacts),
    }


def _result_payload(result) -> dict[str, Any]:
    return {
        "run_id": result.run_id,
        "status": result.status,
        "exit_code": result.exit_code,
        "duration_ms": result.duration_ms,
        "stdout_log_ref": result.stdout_log_ref,
        "stderr_log_ref": result.stderr_log_ref,
        "produced_artifacts": list(result.produced_artifacts),
        "error_summary": result.error_summary,
    }


def build_executor_preview(request: ExecutorRequest) -> dict[str, Any]:
    adapter_kind = _clean_adapter_kind(request.adapter_kind)
    _assert_adapter_enabled(adapter_kind)
    spec = _sandbox_spec_from_request(request)
    preview = build_execution_preview(spec)
    preview["adapter_kind"] = adapter_kind
    preview["memory_policy"] = "no_executor_memory"
    preview["writeback_policy"] = "completed_results_only"
    return preview


def execute_executor_request(*, request: ExecutorRequest, run_root: Path) -> dict[str, Any]:
    adapter_kind = _clean_adapter_kind(request.adapter_kind)
    _assert_adapter_enabled(adapter_kind)
    try:
        spec = _sandbox_spec_from_request(request)
    except SandboxValidationError:
        raise
    preview = build_execution_preview(spec)
    preview["adapter_kind"] = adapter_kind
    preview["memory_policy"] = "no_executor_memory"
    preview["writeback_policy"] = "completed_results_only"
    result = execute_sandbox_command(
        proposal_id=str(request.proposal_id or "").strip(),
        spec=spec,
        run_root=Path(run_root),
    )
    return {
        "adapter_kind": adapter_kind,
        "execution_spec": _execution_spec_payload(spec),
        "execution_preview": preview,
        "execution_result": _result_payload(result),
        "memory_policy": "no_executor_memory",
        "writeback_policy": "completed_results_only",
    }


__all__ = [
    "DISABLED_HARNESS_ADAPTERS",
    "EXECUTOR_ADAPTER_CLAUDE",
    "EXECUTOR_ADAPTER_CODEX",
    "EXECUTOR_ADAPTER_DEEP_AGENTS",
    "EXECUTOR_ADAPTER_SANDBOX",
    "ExecutorAdapterError",
    "ExecutorRequest",
    "SUPPORTED_EXECUTOR_ADAPTERS",
    "build_executor_preview",
    "execute_executor_request",
]
```

- [ ] **Step 4: Run adapter tests**

Run:

```powershell
python -m pytest tests/test_executor_adapter.py -q
```

Expected:

- PASS: `4 passed`.

- [ ] **Step 5: Run existing sandbox runner tests**

Run:

```powershell
python -m pytest tests/test_sandbox_runner.py tests/test_docker_sandbox_runner.py -q
```

Expected:

- PASS.

- [ ] **Step 6: Commit**

```powershell
git add amadeus_thread0/runtime/executor_adapter.py tests/test_executor_adapter.py
git commit -m "feat: add executor adapter boundary"
```

---

## Task 2: Route `execute_workspace_command` through the adapter with no behavior widening

**Files:**
- Modify: `amadeus_thread0/utils/tools.py`
- Test: `tests/test_sandbox_execution_runtime.py`

- [ ] **Step 1: Write the failing regression**

Append this test to `tests/test_sandbox_execution_runtime.py`:

```python
def test_execute_workspace_command_uses_executor_adapter_and_preserves_packet_surfaces():
    with TemporaryDirectory() as td:
        runtime_dir = Path(td) / "runtime"
        workspace = runtime_dir / "workspaces" / "lab-notes"
        workspace.mkdir(parents=True)
        (workspace / "emit_adapter.py").write_text("print('adapter route')\n", encoding="utf-8")

        with patch.dict(os.environ, _sandbox_env(runtime_dir), clear=True):
            payload = execute_workspace_command.invoke(
                {
                    "argv": ["python", "emit_adapter.py"],
                    "cwd": ".",
                    "writes_expected": False,
                    "proposal_id": "ap-sandbox-adapter-route",
                    "access_hints": _workspace_hints(workspace),
                }
            )

    assert payload["execution_preview"]["adapter_kind"] == "sandbox_runner"
    assert payload["execution_preview"]["memory_policy"] == "no_executor_memory"
    assert payload["execution_preview"]["writeback_policy"] == "completed_results_only"
    assert payload["execution_result"]["run_id"] == "ap-sandbox-adapter-route"
    assert payload["execution_result"]["status"] == "completed"
    assert payload["sandbox_state"]["runner_kind"] == payload["execution_spec"]["runner_kind"]
    assert payload["sandbox_state"]["last_run_id"] == "ap-sandbox-adapter-route"
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
python -m pytest tests/test_sandbox_execution_runtime.py::test_execute_workspace_command_uses_executor_adapter_and_preserves_packet_surfaces -q
```

Expected:

- FAIL because `execution_preview.adapter_kind` is not present yet.

- [ ] **Step 3: Replace direct sandbox execution with adapter dispatch**

In `amadeus_thread0/utils/tools.py`, add imports near the existing sandbox imports:

```python
from amadeus_thread0.runtime.executor_adapter import (
    EXECUTOR_ADAPTER_SANDBOX,
    ExecutorRequest,
    execute_executor_request,
)
```

Inside `execute_workspace_command`, keep existing `build_sandbox_command_spec(...)` for validation and preview compatibility, but replace:

```python
execution_preview = build_execution_preview(spec)
run_id = str(proposal_id or "").strip() or f"run-{uuid.uuid4().hex[:12]}"
run_root = workspace_path / ".amadeus" / "sandbox-runs" / run_id
execution_result = execute_sandbox_command(
    proposal_id=run_id,
    spec=spec,
    run_root=run_root,
)
```

with:

```python
run_id = str(proposal_id or "").strip() or f"run-{uuid.uuid4().hex[:12]}"
request = ExecutorRequest(
    adapter_kind=EXECUTOR_ADAPTER_SANDBOX,
    proposal_id=run_id,
    argv=list(spec.argv),
    cwd=spec.cwd,
    allowed_roots=list(spec.allowed_roots),
    timeout_s=spec.timeout_s,
    writes_expected=spec.writes_expected,
    expected_artifacts=list(spec.expected_artifacts),
    runner_kind=spec.runner_kind,
    image_ref=spec.image_ref,
    network_policy=spec.network_policy,
    workspace_root_kind=spec.workspace_root_kind,
)
run_root = workspace_path / ".amadeus" / "sandbox-runs" / run_id
adapter_payload = execute_executor_request(request=request, run_root=run_root)
execution_preview = dict(adapter_payload.get("execution_preview") or {})
execution_result_payload = dict(adapter_payload.get("execution_result") or {})
```

Then replace all later `execution_result.<field>` reads in this tool with `execution_result_payload[...]`, for example:

```python
if execution_result_payload.get("produced_artifacts"):
    primary_path = Path(str(execution_result_payload["produced_artifacts"][0])).resolve(strict=False)
else:
    primary_path = Path(str(execution_result_payload.get("stdout_log_ref") or "")).resolve(strict=False)
```

and:

```python
"last_status": str(execution_result_payload.get("status") or "").strip(),
"last_exit_code": int(execution_result_payload.get("exit_code") or 0),
"last_run_id": str(execution_result_payload.get("run_id") or "").strip(),
```

Finally, return `execution_result_payload` directly:

```python
"execution_result": execution_result_payload,
```

Do not change command allowlists, workspace-root resolution, approval semantics, or Docker policy.

- [ ] **Step 4: Run the focused regression**

Run:

```powershell
python -m pytest tests/test_sandbox_execution_runtime.py::test_execute_workspace_command_uses_executor_adapter_and_preserves_packet_surfaces -q
```

Expected:

- PASS.

- [ ] **Step 5: Run the full sandbox execution runtime test file**

Run:

```powershell
python -m pytest tests/test_sandbox_execution_runtime.py -q
```

Expected:

- PASS.

- [ ] **Step 6: Commit**

```powershell
git add amadeus_thread0/utils/tools.py tests/test_sandbox_execution_runtime.py
git commit -m "refactor: route workspace execution through adapter"
```

---

## Task 3: Normalize adapter metadata on action packets

**Files:**
- Modify: `amadeus_thread0/graph_parts/action_packets.py`
- Modify: `amadeus_thread0/graph_parts/state.py`
- Test: `tests/test_action_packet_contract.py`

- [ ] **Step 1: Write failing action-packet tests**

Append these tests to `tests/test_action_packet_contract.py`:

```python
    def test_normalize_action_packet_preserves_executor_adapter_metadata(self):
        packet = normalize_action_packet(
            {
                "proposal_id": "ap-executor-1",
                "origin": "counterpart_request",
                "intent": "sandbox:execute_workspace_command",
                "status": "awaiting_approval",
                "risk": "external_mutation",
                "requires_approval": True,
                "tool_name": "execute_workspace_command",
                "execution_spec": {
                    "executor": "python",
                    "profile": "python_script",
                    "adapter_kind": "sandbox_runner",
                    "runner_kind": "docker_isolated_runner",
                    "isolation_level": "docker_local_isolated",
                    "image_ref": "amadeus-thread0/sandbox-phase2:py312",
                    "network_policy": "none",
                    "workspace_root_kind": "runtime_owned",
                    "memory_policy": "no_executor_memory",
                    "writeback_policy": "completed_results_only",
                    "argv": ["python", "emit.py"],
                    "cwd": "E:/runtime/workspaces/lab-notes",
                    "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
                    "timeout_s": 25,
                    "writes_expected": False,
                    "expected_artifacts": [],
                },
                "execution_preview": {
                    "adapter_kind": "sandbox_runner",
                    "runner_kind": "docker_isolated_runner",
                    "isolation_level": "docker_local_isolated",
                    "image_ref": "amadeus-thread0/sandbox-phase2:py312",
                    "network_policy": "none",
                    "workspace_root_kind": "runtime_owned",
                    "memory_policy": "no_executor_memory",
                    "writeback_policy": "completed_results_only",
                    "argv": ["python", "emit.py"],
                    "cwd": "E:/runtime/workspaces/lab-notes",
                    "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
                    "timeout_s": 25,
                    "writes_expected": False,
                    "expected_artifacts": [],
                },
            }
        )

        self.assertEqual(packet["execution_spec"]["adapter_kind"], "sandbox_runner")
        self.assertEqual(packet["execution_spec"]["memory_policy"], "no_executor_memory")
        self.assertEqual(packet["execution_spec"]["writeback_policy"], "completed_results_only")
        self.assertEqual(packet["execution_preview"]["adapter_kind"], "sandbox_runner")
        self.assertEqual(packet["execution_preview"]["memory_policy"], "no_executor_memory")
        self.assertEqual(packet["execution_preview"]["writeback_policy"], "completed_results_only")

    def test_normalize_action_packet_clips_unknown_executor_adapter_metadata(self):
        packet = normalize_action_packet(
            {
                "proposal_id": "ap-executor-2",
                "intent": "sandbox:execute_workspace_command",
                "tool_name": "execute_workspace_command",
                "execution_preview": {
                    "adapter_kind": "deep_agents",
                    "memory_policy": "persistent_agent_memory",
                    "writeback_policy": "agent_decides",
                    "argv": ["python", "emit.py"],
                    "cwd": "E:/runtime/workspaces/lab-notes",
                    "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
                    "timeout_s": 25,
                },
            }
        )

        self.assertEqual(packet["execution_preview"]["adapter_kind"], "deep_agents")
        self.assertEqual(packet["execution_preview"]["memory_policy"], "no_executor_memory")
        self.assertEqual(packet["execution_preview"]["writeback_policy"], "completed_results_only")
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
python -m pytest tests/test_action_packet_contract.py::ActionPacketContractTests::test_normalize_action_packet_preserves_executor_adapter_metadata tests/test_action_packet_contract.py::ActionPacketContractTests::test_normalize_action_packet_clips_unknown_executor_adapter_metadata -q
```

Expected:

- FAIL because `adapter_kind`, `memory_policy`, and `writeback_policy` are not normalized on execution payloads.

- [ ] **Step 3: Extend execution spec / preview normalization**

In `amadeus_thread0/graph_parts/action_packets.py`, update `normalize_execution_spec()` and `normalize_execution_preview()` normalized dictionaries with:

```python
"adapter_kind": _clean_text(row.get("adapter_kind"), limit=80).lower(),
"memory_policy": "no_executor_memory",
"writeback_policy": "completed_results_only",
```

Include these fields in each function's `any(...)` return check:

```python
normalized["adapter_kind"],
normalized["memory_policy"],
normalized["writeback_policy"],
```

This intentionally clamps memory and writeback policy to the Amadeus-K contract even if an external harness returns a wider policy.

- [ ] **Step 4: Extend typed payload schema**

In `amadeus_thread0/graph_parts/state.py`, keep `execution_spec` and `execution_preview` as dictionaries, but add comments above them in `ActionPacketPayload`:

```python
    # execution_* may include adapter_kind, memory_policy, and writeback_policy.
    # Those fields are runtime binding metadata, not permission to widen authority.
```

Do not add a separate top-level action-packet field for harness sessions.

- [ ] **Step 5: Run action packet tests**

Run:

```powershell
python -m pytest tests/test_action_packet_contract.py -q
```

Expected:

- PASS.

- [ ] **Step 6: Commit**

```powershell
git add amadeus_thread0/graph_parts/action_packets.py amadeus_thread0/graph_parts/state.py tests/test_action_packet_contract.py
git commit -m "feat: normalize executor adapter packet metadata"
```

---

## Task 4: Surface adapter metadata in backend and CLI readback

**Files:**
- Modify: `amadeus_thread0/runtime/backend_api.py`
- Modify: `amadeus_thread0/runtime/backend_session.py`
- Modify: `amadeus_thread0/runtime/final_state.py`
- Modify: `amadeus_thread0/utils/cli_views.py`
- Test: `tests/test_backend_api.py`
- Test: `tests/test_backend_session.py`
- Test: `tests/test_cli_views.py`

- [ ] **Step 1: Write backend response regression**

In `tests/test_backend_api.py`, add a focused test near the sandbox backend contract tests:

```python
def test_backend_api_surfaces_executor_adapter_metadata_on_sandbox_packets(self):
    api = self._build_api()
    state_values = {
        "final_text": "执行已经完成。",
        "current_event": {"kind": "user_utterance"},
        "action_packets": [
            {
                "proposal_id": "ap-adapter-api",
                "origin": "counterpart_request",
                "intent": "sandbox:execute_workspace_command",
                "status": "completed",
                "risk": "external_mutation",
                "requires_approval": True,
                "tool_name": "execute_workspace_command",
                "execution_preview": {
                    "adapter_kind": "sandbox_runner",
                    "runner_kind": "docker_isolated_runner",
                    "isolation_level": "docker_local_isolated",
                    "image_ref": "amadeus-thread0/sandbox-phase2:py312",
                    "network_policy": "none",
                    "workspace_root_kind": "runtime_owned",
                    "memory_policy": "no_executor_memory",
                    "writeback_policy": "completed_results_only",
                    "argv": ["python", "emit.py"],
                    "cwd": "E:/runtime/workspaces/lab-notes",
                    "allowed_roots": ["E:/runtime/workspaces/lab-notes"],
                    "timeout_s": 25,
                },
                "execution_result": {
                    "run_id": "ap-adapter-api",
                    "status": "completed",
                    "exit_code": 0,
                    "duration_ms": 12,
                    "stdout_log_ref": "E:/runtime/workspaces/lab-notes/.amadeus/sandbox-runs/ap-adapter-api/stdout.txt",
                    "stderr_log_ref": "E:/runtime/workspaces/lab-notes/.amadeus/sandbox-runs/ap-adapter-api/stderr.txt",
                    "produced_artifacts": [],
                    "error_summary": "",
                },
            }
        ],
    }

    payload = api.build_turn_response(state_values=state_values, streamed_text="ignored").payload
    packet = payload["autonomy"]["action_packets"][0]

    assert packet["execution_preview"]["adapter_kind"] == "sandbox_runner"
    assert packet["execution_preview"]["memory_policy"] == "no_executor_memory"
    assert packet["execution_preview"]["writeback_policy"] == "completed_results_only"
```

If `tests/test_backend_api.py` uses `unittest`, convert the assertions to `self.assertEqual(...)` inside the appropriate class.

- [ ] **Step 2: Write CLI rendering regression**

In `tests/test_cli_views.py`, add:

```python
def test_render_autonomy_summary_includes_executor_adapter_metadata():
    rendered = render_autonomy_summary(
        {
            "intent": {"mode": "completed"},
            "action_packets": [
                {
                    "proposal_id": "ap-cli-adapter",
                    "intent": "sandbox:execute_workspace_command",
                    "status": "completed",
                    "risk": "external_mutation",
                    "execution_preview": {
                        "adapter_kind": "sandbox_runner",
                        "runner_kind": "docker_isolated_runner",
                        "isolation_level": "docker_local_isolated",
                        "network_policy": "none",
                        "memory_policy": "no_executor_memory",
                        "argv": ["pytest", "-q", "tests/test_generation_profile.py"],
                    },
                    "execution_result": {
                        "run_id": "ap-cli-adapter",
                        "status": "completed",
                        "exit_code": 0,
                    },
                }
            ],
            "pending_approval": {},
            "execution_trace": [],
            "block_reason": "",
        }
    )

    assert "adapter=sandbox_runner" in rendered
    assert "memory=no_executor_memory" in rendered
```

If `render_autonomy_summary` has a different local helper signature, use the existing helper pattern in `tests/test_cli_views.py` and assert the same output fragments.

- [ ] **Step 3: Run failing tests**

Run:

```powershell
python -m pytest tests/test_backend_api.py tests/test_cli_views.py -q
```

Expected:

- Backend API may already pass because action packets are normalized centrally.
- CLI test fails until rendering includes adapter metadata.

- [ ] **Step 4: Update CLI execution line rendering**

In `amadeus_thread0/utils/cli_views.py`, find the block that renders `execution_preview` / `execution_result` for action packets. Add adapter metadata to the sandbox line:

```python
adapter_kind = str(execution_preview.get("adapter_kind") or "").strip()
memory_policy = str(execution_preview.get("memory_policy") or "").strip()
if adapter_kind:
    parts.append(f"adapter={adapter_kind}")
if memory_policy:
    parts.append(f"memory={memory_policy}")
```

Keep existing `runner_kind`, `isolation_level`, `network_policy`, `run_id`, and `exit_code` rendering unchanged.

- [ ] **Step 5: Run backend and CLI tests**

Run:

```powershell
python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py -q
```

Expected:

- PASS.

- [ ] **Step 6: Commit**

```powershell
git add amadeus_thread0/runtime/backend_api.py amadeus_thread0/runtime/backend_session.py amadeus_thread0/runtime/final_state.py amadeus_thread0/utils/cli_views.py tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py
git commit -m "feat: surface executor adapter metadata"
```

---

## Task 5: Add disabled-by-default external harness adapter stubs

**Files:**
- Modify: `amadeus_thread0/runtime/executor_adapter.py`
- Test: `tests/test_executor_adapter.py`

- [ ] **Step 1: Add failing tests for explicit disabled stubs**

Append to `tests/test_executor_adapter.py`:

```python
@pytest.mark.parametrize(
    "adapter_kind",
    ["deep_agents", "codex_harness", "claude_harness"],
)
def test_documented_external_harness_adapters_fail_closed(adapter_kind):
    with TemporaryDirectory() as td:
        workspace = Path(td) / "workspace"
        workspace.mkdir(parents=True)
        request = ExecutorRequest(
            adapter_kind=adapter_kind,
            proposal_id=f"ap-disabled-{adapter_kind}",
            argv=["python", "emit.py"],
            cwd=".",
            allowed_roots=[str(workspace)],
            timeout_s=25,
            writes_expected=False,
            expected_artifacts=[],
            runner_kind=LOCAL_RUNNER_KIND,
            image_ref="",
            network_policy="",
            workspace_root_kind="runtime_owned",
        )

        with pytest.raises(ExecutorAdapterError) as exc:
            build_executor_preview(request)

        assert exc.value.code == "EXECUTOR_ADAPTER_DISABLED"
        assert adapter_kind in str(exc.value)
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
python -m pytest tests/test_executor_adapter.py -q
```

Expected:

- FAIL because `build_executor_preview()` currently raises only after enabling sandbox or because the disabled preview path is not explicit.

- [ ] **Step 3: Make disabled external harness behavior explicit**

In `amadeus_thread0/runtime/executor_adapter.py`, add:

```python
def describe_disabled_adapter(adapter_kind: str) -> dict[str, Any]:
    kind = _clean_adapter_kind(adapter_kind)
    if kind not in DISABLED_HARNESS_ADAPTERS:
        return {}
    return {
        "adapter_kind": kind,
        "status": "disabled",
        "reason": "external harness adapters require a separate design, approval, sandbox, and memory-isolation closure",
        "memory_policy": "no_executor_memory",
        "writeback_policy": "completed_results_only",
    }
```

Then ensure `_assert_adapter_enabled()` raises `EXECUTOR_ADAPTER_DISABLED` for all three documented harness kinds. Add `describe_disabled_adapter` to `__all__`.

- [ ] **Step 4: Run adapter tests**

Run:

```powershell
python -m pytest tests/test_executor_adapter.py -q
```

Expected:

- PASS.

- [ ] **Step 5: Commit**

```powershell
git add amadeus_thread0/runtime/executor_adapter.py tests/test_executor_adapter.py
git commit -m "feat: fail closed external executor harnesses"
```

---

## Task 6: Add executor adapter audit

**Files:**
- Create: `evals/run_executor_adapter_audit.py`
- Test: `tests/test_executor_adapter_audit.py`

- [ ] **Step 1: Write failing audit tests**

Create `tests/test_executor_adapter_audit.py`:

```python
from __future__ import annotations

from evals.run_executor_adapter_audit import (
    EXECUTOR_ADAPTER_READY,
    _evaluate_checks,
    _render_markdown,
)


def test_executor_adapter_audit_reports_ready_when_all_checks_pass():
    result = _evaluate_checks(
        [
            {"name": "sandbox_adapter_executes", "passed": True, "details": "ok"},
            {"name": "external_harnesses_fail_closed", "passed": True, "details": "ok"},
            {"name": "memory_policy_clamped", "passed": True, "details": "ok"},
        ]
    )

    assert result["overall_status"] == "passed"
    assert result["readiness"] == EXECUTOR_ADAPTER_READY


def test_executor_adapter_audit_blocks_readiness_when_any_check_fails():
    result = _evaluate_checks(
        [
            {"name": "sandbox_adapter_executes", "passed": True, "details": "ok"},
            {"name": "external_harnesses_fail_closed", "passed": False, "details": "deep_agents executed"},
        ]
    )

    assert result["overall_status"] == "failed"
    assert result["readiness"] == "executor_adapter_not_ready"


def test_executor_adapter_audit_markdown_names_failed_checks():
    result = _evaluate_checks(
        [
            {"name": "sandbox_adapter_executes", "passed": False, "details": "missing stdout"},
        ]
    )

    markdown = _render_markdown(result)

    assert "executor_adapter_not_ready" in markdown
    assert "sandbox_adapter_executes" in markdown
    assert "missing stdout" in markdown
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
python -m pytest tests/test_executor_adapter_audit.py -q
```

Expected:

- FAIL with `ModuleNotFoundError: No module named 'evals.run_executor_adapter_audit'`.

- [ ] **Step 3: Implement the audit runner**

Create `evals/run_executor_adapter_audit.py`:

```python
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from amadeus_thread0.runtime.executor_adapter import (
    EXECUTOR_ADAPTER_CODEX,
    EXECUTOR_ADAPTER_DEEP_AGENTS,
    EXECUTOR_ADAPTER_CLAUDE,
    EXECUTOR_ADAPTER_SANDBOX,
    ExecutorAdapterError,
    ExecutorRequest,
    build_executor_preview,
    execute_executor_request,
)
from amadeus_thread0.runtime.sandbox_runner import LOCAL_RUNNER_KIND

EXECUTOR_ADAPTER_READY = "executor_adapter_ready"


def _check_sandbox_adapter_executes() -> dict[str, Any]:
    with TemporaryDirectory() as td:
        workspace = Path(td) / "workspace"
        workspace.mkdir(parents=True)
        (workspace / "emit.py").write_text("print('audit-ok')\n", encoding="utf-8")
        request = ExecutorRequest(
            adapter_kind=EXECUTOR_ADAPTER_SANDBOX,
            proposal_id="ap-executor-audit",
            argv=["python", "emit.py"],
            cwd=".",
            allowed_roots=[str(workspace)],
            timeout_s=25,
            writes_expected=False,
            expected_artifacts=[],
            runner_kind=LOCAL_RUNNER_KIND,
            image_ref="",
            network_policy="",
            workspace_root_kind="runtime_owned",
        )
        payload = execute_executor_request(
            request=request,
            run_root=workspace / ".amadeus" / "executor-runs" / "ap-executor-audit",
        )
        stdout = Path(payload["execution_result"]["stdout_log_ref"]).read_text(encoding="utf-8")
        passed = (
            payload["execution_preview"].get("adapter_kind") == EXECUTOR_ADAPTER_SANDBOX
            and payload["execution_result"].get("status") == "completed"
            and stdout == "audit-ok\n"
        )
        return {
            "name": "sandbox_adapter_executes",
            "passed": passed,
            "details": json.dumps(payload["execution_result"], ensure_ascii=False),
        }


def _check_external_harnesses_fail_closed() -> dict[str, Any]:
    blocked: list[str] = []
    leaked: list[str] = []
    with TemporaryDirectory() as td:
        workspace = Path(td) / "workspace"
        workspace.mkdir(parents=True)
        for adapter_kind in (EXECUTOR_ADAPTER_DEEP_AGENTS, EXECUTOR_ADAPTER_CODEX, EXECUTOR_ADAPTER_CLAUDE):
            request = ExecutorRequest(
                adapter_kind=adapter_kind,
                proposal_id=f"ap-disabled-{adapter_kind}",
                argv=["python", "emit.py"],
                cwd=".",
                allowed_roots=[str(workspace)],
                timeout_s=25,
                writes_expected=False,
                expected_artifacts=[],
                runner_kind=LOCAL_RUNNER_KIND,
                image_ref="",
                network_policy="",
                workspace_root_kind="runtime_owned",
            )
            try:
                build_executor_preview(request)
                leaked.append(adapter_kind)
            except ExecutorAdapterError as exc:
                if exc.code == "EXECUTOR_ADAPTER_DISABLED":
                    blocked.append(adapter_kind)
                else:
                    leaked.append(f"{adapter_kind}:{exc.code}")
    return {
        "name": "external_harnesses_fail_closed",
        "passed": not leaked and len(blocked) == 3,
        "details": f"blocked={blocked}; leaked={leaked}",
    }


def _check_memory_policy_clamped() -> dict[str, Any]:
    with TemporaryDirectory() as td:
        workspace = Path(td) / "workspace"
        workspace.mkdir(parents=True)
        request = ExecutorRequest(
            adapter_kind=EXECUTOR_ADAPTER_SANDBOX,
            proposal_id="ap-memory-policy",
            argv=["python", "missing.py"],
            cwd=".",
            allowed_roots=[str(workspace)],
            timeout_s=25,
            writes_expected=False,
            expected_artifacts=[],
            runner_kind=LOCAL_RUNNER_KIND,
            image_ref="",
            network_policy="",
            workspace_root_kind="runtime_owned",
        )
        preview = build_executor_preview(request)
    return {
        "name": "memory_policy_clamped",
        "passed": preview.get("memory_policy") == "no_executor_memory"
        and preview.get("writeback_policy") == "completed_results_only",
        "details": json.dumps(preview, ensure_ascii=False),
    }


def _evaluate_checks(checks: list[dict[str, Any]]) -> dict[str, Any]:
    passed = all(bool(item.get("passed", False)) for item in checks)
    return {
        "overall_status": "passed" if passed else "failed",
        "readiness": EXECUTOR_ADAPTER_READY if passed else "executor_adapter_not_ready",
        "checks": checks,
        "generated_at": int(time.time()),
    }


def _render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Executor Adapter Audit",
        "",
        f"- overall_status: `{result.get('overall_status')}`",
        f"- readiness: `{result.get('readiness')}`",
        "",
        "## Checks",
    ]
    for check in result.get("checks", []):
        status = "PASS" if check.get("passed") else "FAIL"
        lines.append(f"- `{status}` `{check.get('name')}`: {check.get('details')}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-tag", default="executor-adapter-audit")
    args = parser.parse_args()
    result = _evaluate_checks(
        [
            _check_sandbox_adapter_executes(),
            _check_external_harnesses_fail_closed(),
            _check_memory_policy_clamped(),
        ]
    )
    reports = Path("evals") / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    safe_tag = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in args.run_tag).strip("-")
    base = reports / f"executor-adapter-audit-{stamp}-{safe_tag}"
    base.with_suffix(".json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    base.with_suffix(".md").write_text(_render_markdown(result), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["overall_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run audit tests**

Run:

```powershell
python -m pytest tests/test_executor_adapter_audit.py -q
```

Expected:

- PASS.

- [ ] **Step 5: Run the audit**

Run:

```powershell
python evals/run_executor_adapter_audit.py --run-tag executor-adapter-refactor
```

Expected:

- `overall_status=passed`
- `readiness=executor_adapter_ready`
- report files are written under `evals/reports/`.

- [ ] **Step 6: Commit**

```powershell
git add evals/run_executor_adapter_audit.py tests/test_executor_adapter_audit.py
git commit -m "test: add executor adapter audit"
```

---

## Task 7: Update architecture and handoff docs

**Files:**
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `docs/engineering/BACKEND_HANDOFF.md`
- Modify: `program.md`

- [ ] **Step 1: Update project structure ownership**

In `docs/engineering/PROJECT_STRUCTURE.md`, under the runtime layer list, add:

```markdown
- `executor_adapter.py`
```

Then add a focused ownership paragraph:

```markdown
`executor_adapter.py` holds the runtime-owned execution adapter boundary:

- wraps the preserved sandbox runner as the only enabled adapter
- exposes adapter metadata on `execution_spec` / `execution_preview`
- keeps future Deep Agents, Codex, and Claude Code harness candidates fail-closed until separately designed and approved
- never owns persona memory, session truth, skills registry truth, or digital-body consequence writeback
```

- [ ] **Step 2: Update architecture decisions**

In `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`, add a new decision under the sandbox phase-2 section:

```markdown
### Decision: Executor Adapter Boundary

Status as of `2026-05-05`: accepted as an internal refactor boundary.

- The enabled execution adapter is `sandbox_runner`.
- `deep_agents`, `codex_harness`, and `claude_harness` are documented future candidates but fail closed by default.
- Adapter metadata may appear on `execution_spec` and `execution_preview`:
  - `adapter_kind`
  - `memory_policy=no_executor_memory`
  - `writeback_policy=completed_results_only`
- Adapter metadata is runtime binding information, not permission to widen execution authority.
- External harness sessions, if later added, must be treated as execution logs/artifacts, not Amadeus-K autobiographical memory or persona state.
```

- [ ] **Step 3: Update backend handoff contract**

In `docs/engineering/BACKEND_HANDOFF.md`, in the sandbox execution packet section, add:

```markdown
Executor adapter metadata may appear inside sandbox `execution_spec` / `execution_preview`:

- `adapter_kind`
- `memory_policy`
- `writeback_policy`

Current stable values are:

- `adapter_kind=sandbox_runner`
- `memory_policy=no_executor_memory`
- `writeback_policy=completed_results_only`

Frontend and CLI consumers may render these fields, but must not infer new execution authority, external-harness availability, or separate memory/session ownership from them.
```

- [ ] **Step 4: Update program ledger**

Append to `program.md`:

```markdown
## 2026-05-05 Run 244

- Focus:
  - write and begin the executor adapter layer refactor plan
  - preserve LangGraph persona core, unified memory, action packets, sandbox phase-2, skills, and browser baselines
- Files changed:
  - `docs/superpowers/plans/2026-05-05-executor-adapter-layer-refactor.md`
  - `program.md`
- Key changes:
  - planned a fail-closed executor adapter boundary around the existing sandbox runner
  - kept Deep Agents, Codex, and Claude Code as disabled future adapter candidates, not runtime dependencies
  - defined audit and docs updates required before any future harness import
- Validation:
  - plan-only run; no implementation tests run
- Next:
  - execute Task 1 of the executor adapter plan, starting with `tests/test_executor_adapter.py`
```

- [ ] **Step 5: Run markdown / whitespace check**

Run:

```powershell
git diff --check -- docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md docs/engineering/BACKEND_HANDOFF.md program.md
```

Expected:

- PASS, except the existing `program.md` LF-to-CRLF warning may still appear.

- [ ] **Step 6: Commit**

```powershell
git add docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md docs/engineering/BACKEND_HANDOFF.md program.md
git commit -m "docs: document executor adapter boundary"
```

---

## Task 8: Run closure validation

**Files:**
- No code changes.
- Generated ignored reports under `evals/reports/`.

- [ ] **Step 1: Run targeted executor and sandbox tests**

Run:

```powershell
python -m pytest tests/test_executor_adapter.py tests/test_executor_adapter_audit.py tests/test_sandbox_runner.py tests/test_docker_sandbox_runner.py tests/test_sandbox_execution_runtime.py tests/test_action_packet_contract.py -q
```

Expected:

- PASS.

- [ ] **Step 2: Run backend contract tests touched by execution packets**

Run:

```powershell
python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py tests/test_autonomy_writeback.py tests/test_world_model_residue.py -q
```

Expected:

- PASS.

- [ ] **Step 3: Run preserved sandbox phase-2 validation**

Run:

```powershell
python -m pytest tests/test_sandbox_phase2_smokes.py tests/test_sandbox_phase2_audit.py tests/test_sandbox_phase2_backend_contract.py -q
python evals/run_sandbox_phase2_smokes.py --run-tag executor-adapter-refactor
python evals/run_sandbox_phase2_audit.py --run-tag executor-adapter-refactor
```

Expected:

- pytest PASS.
- smoke runner reports `overall_status=passed`.
- audit runner reports `overall_status=passed` and `readiness=sandbox_embodied_execution_phase2_ready`.

- [ ] **Step 4: Run new executor adapter audit**

Run:

```powershell
python evals/run_executor_adapter_audit.py --run-tag final-check
```

Expected:

- `overall_status=passed`
- `readiness=executor_adapter_ready`

- [ ] **Step 5: Run import / compile checks**

Run:

```powershell
python -m py_compile amadeus_thread0/runtime/executor_adapter.py amadeus_thread0/utils/tools.py amadeus_thread0/graph_parts/action_packets.py evals/run_executor_adapter_audit.py tests/test_executor_adapter.py tests/test_executor_adapter_audit.py
```

Expected:

- PASS with no output.

- [ ] **Step 6: Final ledger update**

Update `program.md` with:

```markdown
- Result:
  - executor adapter boundary is implemented with the current sandbox runner as the only enabled adapter
  - external harness candidates remain fail-closed and do not own memory, session truth, or writeback
  - preserved sandbox phase-2 and backend action-packet contracts stayed green
- Next:
  - decide whether to write a separate design spec for exactly one disabled harness candidate, with Deep Agents as the recommended first candidate
```

- [ ] **Step 7: Commit validation ledger**

```powershell
git add program.md
git commit -m "chore: record executor adapter validation"
```

---

## Self-Review Checklist

- [x] Plan keeps Amadeus-K's LangGraph persona loop authoritative.
- [x] Plan does not import OpenClaw, Deep Agents, Codex, or Claude Code.
- [x] Plan makes the current sandbox runner the only enabled adapter.
- [x] Plan keeps external harness candidates fail-closed.
- [x] Plan keeps executor memory policy clamped to `no_executor_memory`.
- [x] Plan keeps writeback policy clamped to `completed_results_only`.
- [x] Plan preserves existing sandbox phase-2 allowed commands and network policy.
- [x] Plan includes tests before implementation for each behavior change.
- [x] Plan includes docs and audit closure.
- [x] Plan avoids frontend UI work.

---

## Execution Notes

- Do not start by adding Deep Agents, Codex, Claude Code, OpenClaw, ACP, MCP, or package dependencies.
- Do not add a second session store or executor-owned memory table.
- Do not allow external harness output to directly write Amadeus-K memory.
- Do not widen command allowlists while doing this refactor.
- If any preserved sandbox/browser/skills/backend contract test fails, stop and debug the regression before continuing.
