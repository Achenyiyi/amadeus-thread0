from __future__ import annotations

import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from amadeus_thread0.runtime.sandbox_runner import (
    ATTACHED_REPO_WORKSPACE_ROOT_KIND,
    DEFAULT_DOCKER_IMAGE_REF,
    DEFAULT_DOCKER_NETWORK_POLICY,
    DEFAULT_WORKSPACE_ROOT_KIND,
    DOCKER_ISOLATION_LEVEL,
    DOCKER_RUNNER_KIND,
    DockerIsolatedSandboxRunner,
    SandboxValidationError,
    build_sandbox_command_spec,
)


def test_build_sandbox_command_spec_prefers_docker_when_image_is_ready():
    with TemporaryDirectory() as td:
        workspace = Path(td) / "workspace"
        workspace.mkdir(parents=True)
        with (
            patch("amadeus_thread0.runtime.sandbox_runner.sandbox_docker_engine_available", return_value=True),
            patch("amadeus_thread0.runtime.sandbox_runner.sandbox_docker_image_available", return_value=True),
        ):
            spec = build_sandbox_command_spec(
                argv=["python", "emit.py"],
                cwd=".",
                allowed_roots=[str(workspace)],
                timeout_s=25,
                writes_expected=False,
            )

    assert spec.runner_kind == DOCKER_RUNNER_KIND
    assert spec.isolation_level == DOCKER_ISOLATION_LEVEL
    assert spec.image_ref == DEFAULT_DOCKER_IMAGE_REF
    assert spec.network_policy == DEFAULT_DOCKER_NETWORK_POLICY
    assert spec.workspace_root_kind == DEFAULT_WORKSPACE_ROOT_KIND


def test_build_sandbox_command_spec_rejects_non_none_network_for_docker():
    with TemporaryDirectory() as td:
        workspace = Path(td) / "workspace"
        workspace.mkdir(parents=True)
        with (
            patch("amadeus_thread0.runtime.sandbox_runner.sandbox_docker_engine_available", return_value=True),
            patch("amadeus_thread0.runtime.sandbox_runner.sandbox_docker_image_available", return_value=True),
        ):
            with pytest.raises(SandboxValidationError, match="network_policy=none"):
                build_sandbox_command_spec(
                    argv=["python", "emit.py"],
                    cwd=".",
                    allowed_roots=[str(workspace)],
                    timeout_s=25,
                    writes_expected=False,
                    runner_kind=DOCKER_RUNNER_KIND,
                    network_policy="host",
                )


def test_build_sandbox_command_spec_blocks_git_write_subcommands_for_phase2():
    with TemporaryDirectory() as td:
        workspace = Path(td) / "workspace"
        workspace.mkdir(parents=True)
        with (
            patch("amadeus_thread0.runtime.sandbox_runner.sandbox_docker_engine_available", return_value=True),
            patch("amadeus_thread0.runtime.sandbox_runner.sandbox_docker_image_available", return_value=True),
        ):
            with pytest.raises(SandboxValidationError, match="git commit"):
                build_sandbox_command_spec(
                    argv=["git", "commit", "-m", "x"],
                    cwd=".",
                    allowed_roots=[str(workspace)],
                    timeout_s=25,
                    writes_expected=False,
                    runner_kind=DOCKER_RUNNER_KIND,
                )
            with pytest.raises(SandboxValidationError, match="git push"):
                build_sandbox_command_spec(
                    argv=["git", "push"],
                    cwd=".",
                    allowed_roots=[str(workspace)],
                    timeout_s=25,
                    writes_expected=False,
                    runner_kind=DOCKER_RUNNER_KIND,
                )


def test_docker_isolated_runner_records_container_manifest_and_artifacts():
    with TemporaryDirectory() as td:
        workspace = Path(td) / "workspace"
        workspace.mkdir(parents=True)
        (workspace / "emit_artifact.py").write_text("print('artifact-ready')\n", encoding="utf-8")
        run_root = workspace / ".amadeus" / "sandbox-runs" / "ap-docker-1"
        produced_artifact = workspace / "notes" / "generated.txt"
        commands: list[list[str]] = []

        def _fake_run(command, **kwargs):
            command = [str(part) for part in command]
            commands.append(command)
            if command[:3] == ["docker", "rm", "-f"]:
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            if command[:2] == ["docker", "run"]:
                cid_index = command.index("--cidfile") + 1
                Path(command[cid_index]).write_text("cid-123\n", encoding="utf-8")
                produced_artifact.parent.mkdir(parents=True, exist_ok=True)
                produced_artifact.write_text("hello from docker\n", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, stdout="artifact-ready\n", stderr="")
            raise AssertionError(f"unexpected command: {command}")

        with (
            patch("amadeus_thread0.runtime.sandbox_runner.sandbox_docker_engine_available", return_value=True),
            patch("amadeus_thread0.runtime.sandbox_runner.sandbox_docker_image_available", return_value=True),
            patch("amadeus_thread0.runtime.sandbox_runner.shutil.which", return_value="docker"),
            patch("amadeus_thread0.runtime.sandbox_runner.subprocess.run", side_effect=_fake_run),
        ):
            spec = build_sandbox_command_spec(
                argv=["python", "emit_artifact.py"],
                cwd=".",
                allowed_roots=[str(workspace)],
                timeout_s=25,
                writes_expected=True,
                expected_artifacts=["notes/generated.txt"],
                runner_kind=DOCKER_RUNNER_KIND,
                workspace_root_kind=ATTACHED_REPO_WORKSPACE_ROOT_KIND,
            )
            result = DockerIsolatedSandboxRunner().execute(
                proposal_id="ap-docker-1",
                spec=spec,
                run_root=run_root,
            )

        manifest = json.loads((run_root / "run.json").read_text(encoding="utf-8"))
        docker_run = next(command for command in commands if command[:2] == ["docker", "run"])

        assert result.status == "completed"
        assert result.exit_code == 0
        assert produced_artifact.exists()
        assert result.produced_artifacts == [str(produced_artifact.resolve(strict=False))]
        assert "--network" in docker_run
        assert docker_run[docker_run.index("--network") + 1] == "none"
        assert "--privileged" not in docker_run
        assert "docker.sock" not in " ".join(docker_run)
        assert manifest["runner_kind"] == DOCKER_RUNNER_KIND
        assert manifest["isolation_level"] == DOCKER_ISOLATION_LEVEL
        assert manifest["network_policy"] == "none"
        assert manifest["workspace_root_kind"] == ATTACHED_REPO_WORKSPACE_ROOT_KIND
        assert manifest["runtime"]["container_id"] == "cid-123"
        assert manifest["runtime"]["container_workdir"] == "/workspace"
        assert manifest["runtime"]["translated_argv"] == ["python", "emit_artifact.py"]


def test_docker_isolated_runner_cleans_stale_cidfile_and_container_before_rerun():
    with TemporaryDirectory() as td:
        workspace = Path(td) / "workspace"
        workspace.mkdir(parents=True)
        (workspace / "emit_artifact.py").write_text("print('artifact-ready')\n", encoding="utf-8")
        run_root = workspace / ".amadeus" / "sandbox-runs" / "ap-docker-rerun"
        run_root.mkdir(parents=True, exist_ok=True)
        stale_cidfile = run_root / "container.cid"
        stale_cidfile.write_text("stale-cid-123\n", encoding="utf-8")
        commands: list[list[str]] = []

        def _fake_run(command, **kwargs):
            command = [str(part) for part in command]
            commands.append(command)
            if command[:3] == ["docker", "rm", "-f"]:
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            if command[:2] == ["docker", "run"]:
                cid_index = command.index("--cidfile") + 1
                Path(command[cid_index]).write_text("fresh-cid-456\n", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")
            raise AssertionError(f"unexpected command: {command}")

        with (
            patch("amadeus_thread0.runtime.sandbox_runner.sandbox_docker_engine_available", return_value=True),
            patch("amadeus_thread0.runtime.sandbox_runner.sandbox_docker_image_available", return_value=True),
            patch("amadeus_thread0.runtime.sandbox_runner.shutil.which", return_value="docker"),
            patch("amadeus_thread0.runtime.sandbox_runner.subprocess.run", side_effect=_fake_run),
        ):
            spec = build_sandbox_command_spec(
                argv=["python", "emit_artifact.py"],
                cwd=".",
                allowed_roots=[str(workspace)],
                timeout_s=25,
                writes_expected=False,
                runner_kind=DOCKER_RUNNER_KIND,
            )
            result = DockerIsolatedSandboxRunner().execute(
                proposal_id="ap-docker-rerun",
                spec=spec,
                run_root=run_root,
            )

        cleanup_targets = [command[-1] for command in commands if command[:3] == ["docker", "rm", "-f"]]
        assert result.status == "completed"
        assert "amadeus-sbox-ap-docker-rerun" in cleanup_targets
        assert "stale-cid-123" in cleanup_targets
        assert not stale_cidfile.exists()
