from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .sandbox_runner import (
    DEFAULT_WORKSPACE_ROOT_KIND,
    SandboxCommandSpec,
    SandboxExecutionResult,
    build_execution_preview,
    build_sandbox_command_spec,
    execute_sandbox_command,
)


EXECUTOR_ADAPTER_SANDBOX = "sandbox_runner"
EXECUTOR_ADAPTER_DEEP_AGENTS = "deep_agents"
EXECUTOR_ADAPTER_CODEX = "codex_harness"
EXECUTOR_ADAPTER_CLAUDE = "claude_harness"
EXECUTOR_ADAPTER_OPENCLAW = "openclaw_harness"

MEMORY_POLICY_NO_PERSONA_OWNERSHIP = "no_persona_memory_ownership"
WRITEBACK_POLICY_RESULT_ONLY = "result_only"

_DISABLED_ADAPTERS = {
    EXECUTOR_ADAPTER_DEEP_AGENTS,
    EXECUTOR_ADAPTER_CODEX,
    EXECUTOR_ADAPTER_CLAUDE,
    EXECUTOR_ADAPTER_OPENCLAW,
}


class ExecutorAdapterError(RuntimeError):
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
    timeout_s: int = 25
    writes_expected: bool = False
    expected_artifacts: list[str] | None = None
    runner_kind: str = ""
    image_ref: str = ""
    network_policy: str = ""
    workspace_root_kind: str = DEFAULT_WORKSPACE_ROOT_KIND


def _adapter_kind(value: Any) -> str:
    return str(value or "").strip().lower()


def _ensure_enabled(request: ExecutorRequest) -> None:
    adapter_kind = _adapter_kind(request.adapter_kind)
    if adapter_kind == EXECUTOR_ADAPTER_SANDBOX:
        return
    if adapter_kind in _DISABLED_ADAPTERS:
        raise ExecutorAdapterError(
            "EXECUTOR_ADAPTER_DISABLED",
            f"executor adapter is disabled in this baseline: {adapter_kind}",
        )
    raise ExecutorAdapterError("EXECUTOR_ADAPTER_UNKNOWN", f"unknown executor adapter: {adapter_kind or '(missing)'}")


def _sandbox_spec_from_request(request: ExecutorRequest) -> SandboxCommandSpec:
    _ensure_enabled(request)
    return build_sandbox_command_spec(
        argv=list(request.argv or []),
        cwd=request.cwd,
        allowed_roots=list(request.allowed_roots or []),
        timeout_s=request.timeout_s,
        writes_expected=request.writes_expected,
        expected_artifacts=list(request.expected_artifacts or []),
        runner_kind=request.runner_kind,
        image_ref=request.image_ref,
        network_policy=request.network_policy,
        workspace_root_kind=request.workspace_root_kind,
    )


def _with_adapter_policy(payload: dict[str, Any], *, adapter_kind: str) -> dict[str, Any]:
    enriched = dict(payload)
    enriched["adapter_kind"] = str(adapter_kind or EXECUTOR_ADAPTER_SANDBOX)
    enriched["memory_policy"] = MEMORY_POLICY_NO_PERSONA_OWNERSHIP
    enriched["writeback_policy"] = WRITEBACK_POLICY_RESULT_ONLY
    return enriched


def _result_to_dict(result: SandboxExecutionResult | dict[str, Any]) -> dict[str, Any]:
    if isinstance(result, SandboxExecutionResult):
        return asdict(result)
    return dict(result) if isinstance(result, dict) else {}


def build_executor_preview(request: ExecutorRequest) -> dict[str, Any]:
    spec = _sandbox_spec_from_request(request)
    preview = build_execution_preview(spec)
    preview["profile"] = str(spec.profile)
    return _with_adapter_policy(preview, adapter_kind=EXECUTOR_ADAPTER_SANDBOX)


def execute_executor_request(request: ExecutorRequest, *, run_root: Path | str) -> dict[str, Any]:
    spec = _sandbox_spec_from_request(request)
    preview = build_execution_preview(spec)
    preview["profile"] = str(spec.profile)
    preview = _with_adapter_policy(preview, adapter_kind=EXECUTOR_ADAPTER_SANDBOX)
    result = execute_sandbox_command(
        proposal_id=str(request.proposal_id or "").strip(),
        spec=spec,
        run_root=Path(run_root),
    )
    return {
        "adapter_kind": EXECUTOR_ADAPTER_SANDBOX,
        "execution_preview": preview,
        "execution_result": _result_to_dict(result),
        "memory_policy": MEMORY_POLICY_NO_PERSONA_OWNERSHIP,
        "writeback_policy": WRITEBACK_POLICY_RESULT_ONLY,
    }


def describe_disabled_adapter(adapter_kind: str) -> dict[str, Any]:
    normalized = _adapter_kind(adapter_kind)
    reason = (
        "External executor harnesses are documented but disabled in the preserved backend baseline. "
        "They may not own persona memory, widen command authority, or write facts directly."
    )
    return {
        "adapter_kind": normalized,
        "status": "disabled",
        "memory_policy": MEMORY_POLICY_NO_PERSONA_OWNERSHIP,
        "writeback_policy": WRITEBACK_POLICY_RESULT_ONLY,
        "reason": reason,
    }


__all__ = [
    "EXECUTOR_ADAPTER_CLAUDE",
    "EXECUTOR_ADAPTER_CODEX",
    "EXECUTOR_ADAPTER_DEEP_AGENTS",
    "EXECUTOR_ADAPTER_OPENCLAW",
    "EXECUTOR_ADAPTER_SANDBOX",
    "ExecutorAdapterError",
    "ExecutorRequest",
    "build_executor_preview",
    "describe_disabled_adapter",
    "execute_executor_request",
]
