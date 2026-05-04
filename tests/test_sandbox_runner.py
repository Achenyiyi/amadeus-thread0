from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from amadeus_thread0.runtime.sandbox_runner import (
    LOCAL_RUNNER_KIND,
    LocalRestrictedSandboxRunner,
    SandboxValidationError,
    build_sandbox_command_spec,
)


def test_build_sandbox_command_spec_rejects_python_inline_execution():
    with TemporaryDirectory() as td:
        workspace = Path(td) / "workspace"
        workspace.mkdir(parents=True)
        with pytest.raises(SandboxValidationError, match="python -c"):
            build_sandbox_command_spec(
                argv=["python", "-c", "print('hi')"],
                cwd=".",
                allowed_roots=[str(workspace)],
                timeout_s=10,
                writes_expected=False,
            )


def test_build_sandbox_command_spec_rejects_pip_module_execution():
    with TemporaryDirectory() as td:
        workspace = Path(td) / "workspace"
        workspace.mkdir(parents=True)
        with pytest.raises(SandboxValidationError, match="not allowed"):
            build_sandbox_command_spec(
                argv=["python", "-m", "pip", "install", "requests"],
                cwd=".",
                allowed_roots=[str(workspace)],
                timeout_s=10,
                writes_expected=True,
            )


def test_build_sandbox_command_spec_rejects_script_outside_allowed_root():
    with TemporaryDirectory() as td:
        workspace = Path(td) / "workspace"
        workspace.mkdir(parents=True)
        outside = Path(td) / "outside.py"
        outside.write_text("print('nope')\n", encoding="utf-8")
        with pytest.raises(SandboxValidationError, match="escapes allowed roots|outside allowed roots"):
            build_sandbox_command_spec(
                argv=["python", "../outside.py"],
                cwd=".",
                allowed_roots=[str(workspace)],
                timeout_s=10,
                writes_expected=False,
            )


def test_local_restricted_sandbox_runner_executes_workspace_script_and_records_artifacts():
    with TemporaryDirectory() as td:
        workspace = Path(td) / "workspace"
        workspace.mkdir(parents=True)
        script = workspace / "emit_artifact.py"
        script.write_text(
            "\n".join(
                [
                    "from pathlib import Path",
                    "out = Path('notes/generated.txt')",
                    "out.parent.mkdir(parents=True, exist_ok=True)",
                    "out.write_text('hello from sandbox\\n', encoding='utf-8')",
                    "print('artifact-ready')",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        spec = build_sandbox_command_spec(
            argv=["python", "emit_artifact.py"],
            cwd=".",
            allowed_roots=[str(workspace)],
            timeout_s=10,
            writes_expected=True,
            expected_artifacts=["notes/generated.txt"],
            runner_kind=LOCAL_RUNNER_KIND,
        )
        run_root = workspace / ".amadeus" / "sandbox-runs" / "ap-sandbox-1"
        runner = LocalRestrictedSandboxRunner()

        result = runner.execute(
            proposal_id="ap-sandbox-1",
            spec=spec,
            run_root=run_root,
        )

        generated = workspace / "notes" / "generated.txt"
        manifest = json.loads((run_root / "run.json").read_text(encoding="utf-8"))

        assert result.status == "completed"
        assert result.exit_code == 0
        assert generated.exists()
        assert generated.read_text(encoding="utf-8") == "hello from sandbox\n"
        assert result.produced_artifacts == [str(generated.resolve(strict=False))]
        assert Path(result.stdout_log_ref).exists()
        assert Path(result.stderr_log_ref).exists()
        assert "artifact-ready" in Path(result.stdout_log_ref).read_text(encoding="utf-8")
        assert manifest["run_id"] == "ap-sandbox-1"
        assert manifest["runner_kind"] == "local_restricted_runner"
        assert manifest["spec"]["profile"] == "python_script"
        assert manifest["result"]["status"] == "completed"
