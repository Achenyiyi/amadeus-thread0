from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from amadeus_thread0.runtime.executor_adapter import (
    EXECUTOR_ADAPTER_CLAUDE,
    EXECUTOR_ADAPTER_CODEX,
    EXECUTOR_ADAPTER_DEEP_AGENTS,
    EXECUTOR_ADAPTER_OPENCLAW,
    EXECUTOR_ADAPTER_SANDBOX,
    ExecutorAdapterError,
    ExecutorRequest,
    build_executor_preview,
    describe_disabled_adapter,
    execute_executor_request,
)
from amadeus_thread0.runtime.sandbox_runner import LOCAL_RUNNER_KIND


def test_executor_adapter_builds_sandbox_preview_without_running_command():
    with TemporaryDirectory() as td:
        workspace = Path(td) / "workspace"
        workspace.mkdir(parents=True)
        request = ExecutorRequest(
            adapter_kind=EXECUTOR_ADAPTER_SANDBOX,
            proposal_id="ap-preview",
            argv=["python", "check.py"],
            cwd=".",
            allowed_roots=[str(workspace)],
            timeout_s=25,
            writes_expected=False,
            expected_artifacts=[],
            runner_kind=LOCAL_RUNNER_KIND,
        )

        with patch("amadeus_thread0.runtime.executor_adapter.execute_sandbox_command") as execute_sandbox:
            preview = build_executor_preview(request)

        execute_sandbox.assert_not_called()
        assert preview["adapter_kind"] == "sandbox_runner"
        assert preview["runner_kind"] == "local_restricted_runner"
        assert preview["memory_policy"] == "no_persona_memory_ownership"
        assert preview["writeback_policy"] == "result_only"


def test_executor_adapter_executes_existing_sandbox_runner_and_preserves_result_shape():
    with TemporaryDirectory() as td:
        workspace = Path(td) / "workspace"
        workspace.mkdir(parents=True)
        script = workspace / "check.py"
        script.write_text("print('adapter ok')\n", encoding="utf-8")
        request = ExecutorRequest(
            adapter_kind=EXECUTOR_ADAPTER_SANDBOX,
            proposal_id="ap-run",
            argv=["python", "check.py"],
            cwd=".",
            allowed_roots=[str(workspace)],
            timeout_s=25,
            writes_expected=False,
            expected_artifacts=[],
            runner_kind=LOCAL_RUNNER_KIND,
        )

        payload = execute_executor_request(request, run_root=workspace / ".amadeus" / "sandbox-runs" / "ap-run")

        assert payload["adapter_kind"] == "sandbox_runner"
        assert payload["execution_preview"]["adapter_kind"] == "sandbox_runner"
        assert payload["execution_result"]["run_id"] == "ap-run"
        assert payload["execution_result"]["status"] == "completed"
        assert payload["execution_result"]["exit_code"] == 0
        assert Path(payload["execution_result"]["stdout_log_ref"]).exists()


@pytest.mark.parametrize(
    "adapter_kind",
    [EXECUTOR_ADAPTER_DEEP_AGENTS, EXECUTOR_ADAPTER_CODEX, EXECUTOR_ADAPTER_CLAUDE, EXECUTOR_ADAPTER_OPENCLAW],
)
def test_documented_external_harness_adapters_fail_closed(adapter_kind):
    request = ExecutorRequest(
        adapter_kind=adapter_kind,
        proposal_id=f"ap-disabled-{adapter_kind}",
        argv=["python", "check.py"],
        cwd=".",
        allowed_roots=["E:/runtime/workspaces/demo"],
    )

    with pytest.raises(ExecutorAdapterError) as exc:
        build_executor_preview(request)

    assert exc.value.code == "EXECUTOR_ADAPTER_DISABLED"
    assert adapter_kind in str(exc.value)
    disabled = describe_disabled_adapter(adapter_kind)
    assert disabled["status"] == "disabled"
    assert disabled["memory_policy"] == "no_persona_memory_ownership"

