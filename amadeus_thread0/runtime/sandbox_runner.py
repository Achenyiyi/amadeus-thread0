from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


LOCAL_RUNNER_KIND = "local_restricted_runner"
LOCAL_ISOLATION_LEVEL = "host_local_restricted"
DOCKER_RUNNER_KIND = "docker_isolated_runner"
DOCKER_ISOLATION_LEVEL = "docker_local_isolated"
DEFAULT_DOCKER_IMAGE_REF = "amadeus-thread0/sandbox-phase2:py312"
DEFAULT_DOCKER_NETWORK_POLICY = "none"
DEFAULT_LOCAL_NETWORK_POLICY = "host"
DEFAULT_WORKSPACE_ROOT_KIND = "runtime_owned"
ATTACHED_REPO_WORKSPACE_ROOT_KIND = "attached_repo_root"

_ALLOWED_EXECUTORS = {"python", "pytest", "rg", "git"}
_ALLOWED_GIT_READONLY_SUBCOMMANDS = {
    "branch",
    "cat-file",
    "describe",
    "diff",
    "grep",
    "log",
    "ls-files",
    "rev-list",
    "rev-parse",
    "show",
    "status",
    "symbolic-ref",
}
_BLOCKED_GIT_WRITE_OR_NETWORK_SUBCOMMANDS = {
    "add",
    "am",
    "apply",
    "bisect",
    "checkout",
    "cherry-pick",
    "clean",
    "clone",
    "commit",
    "fetch",
    "gc",
    "init",
    "merge",
    "mv",
    "pull",
    "push",
    "rebase",
    "reset",
    "restore",
    "revert",
    "rm",
    "stash",
    "submodule",
    "switch",
    "tag",
    "worktree",
}
_BLOCKED_PYTHON_MODULE_PREFIXES = ("pip", "ensurepip")
_BLOCKED_GLOBAL_FLAG_TOKENS = {
    "bash",
    "sh",
    "cmd",
    "powershell",
    "pwsh",
    "apt",
    "apt-get",
    "npm",
    "pnpm",
    "yarn",
}
_BLOCKED_GIT_FLAGS = {"--git-dir", "--work-tree"}
_WINDOWS_ENV_KEYS = {
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "TEMP",
    "TMP",
    "PYTHONIOENCODING",
    "PYTHONUTF8",
}


class SandboxValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = str(code or "INVALID_SPEC").strip().upper() or "INVALID_SPEC"


@dataclass(frozen=True)
class SandboxCommandSpec:
    executor: str
    profile: str
    argv: list[str]
    cwd: str
    allowed_roots: list[str]
    timeout_s: int
    writes_expected: bool
    expected_artifacts: list[str]
    runner_kind: str
    isolation_level: str
    image_ref: str
    network_policy: str
    workspace_root_kind: str


@dataclass(frozen=True)
class SandboxExecutionResult:
    run_id: str
    status: str
    exit_code: int
    duration_ms: int
    stdout_log_ref: str
    stderr_log_ref: str
    produced_artifacts: list[str]
    error_summary: str


def _clean_text(value: Any, *, limit: int = 320) -> str:
    return str(value or "").strip()[:limit]


def _clean_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _clean_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _path_within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except Exception:
        return False


def _normalize_allowed_roots(value: Any) -> list[Path]:
    if not isinstance(value, list):
        return []
    normalized: list[Path] = []
    seen: set[str] = set()
    for item in value:
        text = _clean_text(item, limit=520)
        if not text:
            continue
        path = Path(text).expanduser().resolve(strict=False)
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(path)
    return normalized


def _normalize_argv(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise SandboxValidationError("INVALID_ARGV", "argv must be a non-empty list")
    argv = [str(item).strip() for item in value if str(item or "").strip()]
    if not argv:
        raise SandboxValidationError("INVALID_ARGV", "argv must be a non-empty list")
    if any(str(item or "").strip().lower() in _BLOCKED_GLOBAL_FLAG_TOKENS for item in argv[:4]):
        raise SandboxValidationError(
            "SHELL_WRAPPER_BLOCKED",
            "shell wrappers and package managers are not allowed in sandbox execution",
        )
    return argv[:64]


def _relative_artifacts(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _clean_text(item, limit=320).replace("\\", "/")
        if not text:
            continue
        if Path(text).is_absolute():
            raise SandboxValidationError("INVALID_ARTIFACT", "expected_artifacts must stay workspace-relative")
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= 16:
            break
    return out


def _resolve_executor_binary(executor: str) -> str:
    name = str(executor or "").strip().lower()
    if name == "python":
        return sys.executable
    resolved = shutil.which(name)
    if resolved:
        return resolved
    raise SandboxValidationError("TOOL_UNAVAILABLE", f"{name} is not available in PATH")


def _looks_like_workspace_path(token: str) -> bool:
    text = str(token or "").strip()
    if not text or text.startswith("-"):
        return False
    if any(sep in text for sep in ("/", "\\")):
        return True
    return text.endswith((".py", ".txt", ".md", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"))


def sandbox_docker_asset_dir() -> Path:
    return (Path(__file__).resolve().parents[2] / "docker" / "sandbox_phase2").resolve(strict=False)


def sandbox_docker_image_ref(value: Any = "") -> str:
    explicit = _clean_text(value, limit=160)
    if explicit:
        return explicit
    env_value = _clean_text(os.environ.get("AMADEUS_SANDBOX_DOCKER_IMAGE"), limit=160)
    if env_value:
        return env_value
    return DEFAULT_DOCKER_IMAGE_REF


def sandbox_docker_engine_available() -> bool:
    docker = shutil.which("docker")
    if not docker:
        return False
    try:
        completed = subprocess.run(
            [docker, "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            shell=False,
        )
        return int(completed.returncode) == 0 and bool(str(completed.stdout or "").strip())
    except Exception:
        return False


def sandbox_docker_image_available(image_ref: Any = "") -> bool:
    image = sandbox_docker_image_ref(image_ref)
    docker = shutil.which("docker")
    if not docker or not image:
        return False
    try:
        completed = subprocess.run(
            [docker, "image", "inspect", image],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            shell=False,
        )
        return int(completed.returncode) == 0
    except Exception:
        return False


def ensure_docker_sandbox_image(*, image_ref: Any = "", rebuild: bool = False) -> str:
    image = sandbox_docker_image_ref(image_ref)
    if not sandbox_docker_engine_available():
        raise SandboxValidationError("DOCKER_UNAVAILABLE", "docker engine is not available for phase-2 sandbox execution")
    if not rebuild and sandbox_docker_image_available(image):
        return image
    asset_dir = sandbox_docker_asset_dir()
    dockerfile = asset_dir / "Dockerfile"
    if not dockerfile.exists():
        raise SandboxValidationError("DOCKER_IMAGE_ASSET_MISSING", f"missing docker asset: {dockerfile}")
    docker = shutil.which("docker")
    if not docker:
        raise SandboxValidationError("DOCKER_UNAVAILABLE", "docker CLI is not available for phase-2 sandbox execution")
    completed = subprocess.run(
        [docker, "build", "--tag", image, str(asset_dir)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1800,
        shell=False,
    )
    if int(completed.returncode) != 0:
        summary = _clean_text(completed.stderr or completed.stdout or "docker build failed", limit=220)
        raise SandboxValidationError("DOCKER_IMAGE_BUILD_FAILED", summary or "docker build failed")
    return image


def _normalize_workspace_root_kind(value: Any) -> str:
    text = _clean_text(value, limit=64).lower()
    if text in {DEFAULT_WORKSPACE_ROOT_KIND, ATTACHED_REPO_WORKSPACE_ROOT_KIND}:
        return text
    return DEFAULT_WORKSPACE_ROOT_KIND


def _normalize_runner_kind(value: Any) -> str:
    text = _clean_text(value, limit=80).lower()
    if text in {LOCAL_RUNNER_KIND, DOCKER_RUNNER_KIND, "auto"}:
        return text
    return ""


def _resolve_runner_metadata(
    *,
    runner_kind: Any = "",
    image_ref: Any = "",
    network_policy: Any = "",
    workspace_root_kind: Any = "",
) -> dict[str, str]:
    preferred_runner = _normalize_runner_kind(runner_kind)
    normalized_workspace_root_kind = _normalize_workspace_root_kind(workspace_root_kind)
    normalized_image_ref = sandbox_docker_image_ref(image_ref)
    normalized_network_policy = _clean_text(network_policy, limit=32).lower()

    docker_ready = sandbox_docker_engine_available() and sandbox_docker_image_available(normalized_image_ref)
    if preferred_runner == DOCKER_RUNNER_KIND:
        if not sandbox_docker_engine_available():
            raise SandboxValidationError("DOCKER_UNAVAILABLE", "docker engine is not available for phase-2 sandbox execution")
        if not sandbox_docker_image_available(normalized_image_ref):
            raise SandboxValidationError(
                "DOCKER_IMAGE_UNAVAILABLE",
                f"docker image is not available: {normalized_image_ref}",
            )
        if normalized_network_policy and normalized_network_policy != DEFAULT_DOCKER_NETWORK_POLICY:
            raise SandboxValidationError(
                "NETWORK_POLICY_BLOCKED",
                "phase-2 docker execution only allows network_policy=none",
            )
        return {
            "runner_kind": DOCKER_RUNNER_KIND,
            "isolation_level": DOCKER_ISOLATION_LEVEL,
            "image_ref": normalized_image_ref,
            "network_policy": DEFAULT_DOCKER_NETWORK_POLICY,
            "workspace_root_kind": normalized_workspace_root_kind,
        }
    if preferred_runner in {"", "auto"} and docker_ready:
        return {
            "runner_kind": DOCKER_RUNNER_KIND,
            "isolation_level": DOCKER_ISOLATION_LEVEL,
            "image_ref": normalized_image_ref,
            "network_policy": DEFAULT_DOCKER_NETWORK_POLICY,
            "workspace_root_kind": normalized_workspace_root_kind,
        }
    if preferred_runner not in {"", "auto", LOCAL_RUNNER_KIND}:
        raise SandboxValidationError("INVALID_RUNNER", f"unsupported sandbox runner kind: {preferred_runner}")
    return {
        "runner_kind": LOCAL_RUNNER_KIND,
        "isolation_level": LOCAL_ISOLATION_LEVEL,
        "image_ref": "",
        "network_policy": DEFAULT_LOCAL_NETWORK_POLICY,
        "workspace_root_kind": normalized_workspace_root_kind,
    }


def _validate_global_blocked_tokens(argv: list[str]) -> None:
    for token in argv:
        lower = str(token or "").strip().lower()
        if lower in _BLOCKED_GLOBAL_FLAG_TOKENS:
            raise SandboxValidationError("COMMAND_FAMILY_BLOCKED", f"{lower} is not allowed in sandbox execution")


def _normalize_profile(executor: str, argv: list[str], cwd: Path, allowed_roots: list[Path]) -> str:
    _validate_global_blocked_tokens(argv)

    if executor == "python":
        if len(argv) < 2:
            raise SandboxValidationError("INVALID_PYTHON", "python execution requires a script path or -m module")
        first_arg = str(argv[1] or "").strip()
        if first_arg == "-c":
            raise SandboxValidationError("PYTHON_INLINE_BLOCKED", "python -c is not allowed in sandbox execution")
        if first_arg == "-m":
            module_name = str(argv[2] or "").strip() if len(argv) >= 3 else ""
            if not module_name or any(ch.isspace() for ch in module_name):
                raise SandboxValidationError("INVALID_MODULE", "python -m requires a valid module name")
            lowered_module = module_name.lower()
            if any(
                lowered_module == prefix or lowered_module.startswith(prefix + ".")
                for prefix in _BLOCKED_PYTHON_MODULE_PREFIXES
            ):
                raise SandboxValidationError("PYTHON_MODULE_BLOCKED", f"python -m {module_name} is not allowed")
            return "python_module"
        script_path = Path(first_arg)
        if script_path.is_absolute():
            raise SandboxValidationError("ABSOLUTE_SCRIPT_BLOCKED", "python script path must stay workspace-relative")
        resolved = (cwd / script_path).resolve(strict=False)
        if not any(_path_within_root(resolved, root) for root in allowed_roots):
            raise SandboxValidationError("SCRIPT_OUTSIDE_ROOT", "python script path escapes allowed roots")
        return "python_script"

    if executor == "pytest":
        for token in argv[1:]:
            probe = str(token or "").strip()
            if not _looks_like_workspace_path(probe):
                continue
            target = probe.split("::", 1)[0]
            path = Path(target)
            resolved = (cwd / path).resolve(strict=False) if not path.is_absolute() else path.resolve(strict=False)
            if not any(_path_within_root(resolved, root) for root in allowed_roots):
                raise SandboxValidationError("PYTEST_TARGET_OUTSIDE_ROOT", "pytest target escapes allowed roots")
        return "pytest"

    if executor == "rg":
        for token in argv[1:]:
            probe = str(token or "").strip()
            if not _looks_like_workspace_path(probe):
                continue
            path = Path(probe)
            resolved = (cwd / path).resolve(strict=False) if not path.is_absolute() else path.resolve(strict=False)
            if not any(_path_within_root(resolved, root) for root in allowed_roots):
                raise SandboxValidationError("RG_TARGET_OUTSIDE_ROOT", "rg target escapes allowed roots")
        return "rg_search"

    if executor == "git":
        if len(argv) < 2:
            raise SandboxValidationError("INVALID_GIT", "git execution requires a read-only subcommand")
        subcommand = str(argv[1] or "").strip().lower()
        if subcommand in _BLOCKED_GIT_WRITE_OR_NETWORK_SUBCOMMANDS:
            raise SandboxValidationError("GIT_SUBCOMMAND_BLOCKED", f"git {subcommand} is not allowed in sandbox execution")
        if subcommand not in _ALLOWED_GIT_READONLY_SUBCOMMANDS:
            raise SandboxValidationError(
                "GIT_SUBCOMMAND_BLOCKED",
                f"git {subcommand} is not allowed in phase-2 sandbox execution",
            )
        if any(str(token or "").strip().lower() in _BLOCKED_GIT_FLAGS for token in argv[2:]):
            raise SandboxValidationError("GIT_FLAG_BLOCKED", "git --git-dir/--work-tree are not allowed in sandbox execution")
        for token in argv[2:]:
            probe = str(token or "").strip()
            if not _looks_like_workspace_path(probe):
                continue
            target = probe.split("::", 1)[0]
            path = Path(target)
            resolved = (cwd / path).resolve(strict=False) if not path.is_absolute() else path.resolve(strict=False)
            if not any(_path_within_root(resolved, root) for root in allowed_roots):
                raise SandboxValidationError("GIT_TARGET_OUTSIDE_ROOT", "git target escapes allowed roots")
        return "git_readonly"

    raise SandboxValidationError("INVALID_EXECUTOR", f"unsupported executor: {executor}")


def build_sandbox_command_spec(
    *,
    argv: Any,
    cwd: Any,
    allowed_roots: Any,
    timeout_s: Any,
    writes_expected: Any,
    expected_artifacts: Any = None,
    runner_kind: Any = "",
    image_ref: Any = "",
    network_policy: Any = "",
    workspace_root_kind: Any = "",
) -> SandboxCommandSpec:
    normalized_argv = _normalize_argv(argv)
    executor = str(normalized_argv[0] or "").strip().lower()
    if executor not in _ALLOWED_EXECUTORS:
        raise SandboxValidationError("INVALID_EXECUTOR", f"executor must be one of {_ALLOWED_EXECUTORS}")

    roots = _normalize_allowed_roots(allowed_roots)
    if not roots:
        raise SandboxValidationError("ALLOWED_ROOT_REQUIRED", "allowed_roots must contain at least one workspace root")

    raw_cwd = _clean_text(cwd, limit=520).replace("\\", "/") or "."
    cwd_path = Path(raw_cwd)
    if cwd_path.is_absolute():
        resolved_cwd = cwd_path.resolve(strict=False)
    else:
        resolved_cwd = (roots[0] / cwd_path).resolve(strict=False)
    if not any(_path_within_root(resolved_cwd, root) for root in roots):
        raise SandboxValidationError("CWD_OUTSIDE_ROOT", "cwd escapes allowed roots")

    profile = _normalize_profile(executor, normalized_argv, resolved_cwd, roots)
    timeout_value = max(1, min(_clean_int(timeout_s, 25), 300))
    artifacts = _relative_artifacts(expected_artifacts)
    runner_metadata = _resolve_runner_metadata(
        runner_kind=runner_kind,
        image_ref=image_ref,
        network_policy=network_policy,
        workspace_root_kind=workspace_root_kind,
    )

    return SandboxCommandSpec(
        executor=executor,
        profile=profile,
        argv=normalized_argv,
        cwd=str(resolved_cwd),
        allowed_roots=[str(root) for root in roots],
        timeout_s=timeout_value,
        writes_expected=_clean_bool(writes_expected, False),
        expected_artifacts=artifacts,
        runner_kind=str(runner_metadata.get("runner_kind") or ""),
        isolation_level=str(runner_metadata.get("isolation_level") or ""),
        image_ref=str(runner_metadata.get("image_ref") or ""),
        network_policy=str(runner_metadata.get("network_policy") or ""),
        workspace_root_kind=str(runner_metadata.get("workspace_root_kind") or DEFAULT_WORKSPACE_ROOT_KIND),
    )


def build_execution_preview(spec: SandboxCommandSpec) -> dict[str, Any]:
    return {
        "runner_kind": str(spec.runner_kind),
        "isolation_level": str(spec.isolation_level),
        "image_ref": str(spec.image_ref),
        "network_policy": str(spec.network_policy),
        "workspace_root_kind": str(spec.workspace_root_kind),
        "argv": list(spec.argv),
        "cwd": str(spec.cwd),
        "allowed_roots": list(spec.allowed_roots),
        "timeout_s": int(spec.timeout_s),
        "writes_expected": bool(spec.writes_expected),
        "expected_artifacts": list(spec.expected_artifacts),
    }


def _scrub_environment() -> dict[str, str]:
    env: dict[str, str] = {}
    current = os.environ
    for key in _WINDOWS_ENV_KEYS:
        value = current.get(key)
        if value:
            env[key] = str(value)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def _manifest_spec(spec: SandboxCommandSpec) -> dict[str, Any]:
    return {
        "executor": spec.executor,
        "profile": spec.profile,
        "argv": list(spec.argv),
        "cwd": spec.cwd,
        "allowed_roots": list(spec.allowed_roots),
        "timeout_s": spec.timeout_s,
        "writes_expected": spec.writes_expected,
        "expected_artifacts": list(spec.expected_artifacts),
        "runner_kind": spec.runner_kind,
        "isolation_level": spec.isolation_level,
        "image_ref": spec.image_ref,
        "network_policy": spec.network_policy,
        "workspace_root_kind": spec.workspace_root_kind,
    }


def _collect_produced_artifacts(*, spec: SandboxCommandSpec) -> list[str]:
    produced_artifacts: list[str] = []
    cwd_path = Path(spec.cwd)
    for relative in spec.expected_artifacts:
        candidate = (cwd_path / relative).resolve(strict=False)
        if not any(_path_within_root(candidate, Path(root)) for root in spec.allowed_roots):
            continue
        if candidate.exists():
            produced_artifacts.append(str(candidate))
    return produced_artifacts


def _write_run_manifest(
    *,
    manifest_path: Path,
    spec: SandboxCommandSpec,
    result: SandboxExecutionResult,
    runtime_details: dict[str, Any] | None = None,
) -> None:
    manifest_path.write_text(
        json.dumps(
            {
                "run_id": result.run_id,
                "runner_kind": spec.runner_kind,
                "isolation_level": spec.isolation_level,
                "image_ref": spec.image_ref,
                "network_policy": spec.network_policy,
                "workspace_root_kind": spec.workspace_root_kind,
                "spec": _manifest_spec(spec),
                "runtime": dict(runtime_details or {}),
                "result": {
                    "status": result.status,
                    "exit_code": result.exit_code,
                    "duration_ms": result.duration_ms,
                    "stdout_log_ref": result.stdout_log_ref,
                    "stderr_log_ref": result.stderr_log_ref,
                    "produced_artifacts": list(result.produced_artifacts),
                    "error_summary": result.error_summary,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


class LocalRestrictedSandboxRunner:
    runner_kind = LOCAL_RUNNER_KIND
    isolation_level = LOCAL_ISOLATION_LEVEL

    def execute(
        self,
        *,
        proposal_id: str,
        spec: SandboxCommandSpec,
        run_root: Path,
    ) -> SandboxExecutionResult:
        run_id = str(proposal_id or "").strip() or f"run-{int(time.time())}"
        run_dir = Path(run_root).resolve(strict=False)
        run_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = run_dir / "stdout.txt"
        stderr_path = run_dir / "stderr.txt"
        manifest_path = run_dir / "run.json"
        start = time.time()

        command = list(spec.argv)
        command[0] = _resolve_executor_binary(spec.executor)
        exit_code = -1
        status = "blocked"
        error_summary = ""
        stdout_text = ""
        stderr_text = ""
        try:
            completed = subprocess.run(
                command,
                cwd=str(spec.cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=_scrub_environment(),
                timeout=max(1, int(spec.timeout_s)),
                shell=False,
            )
            stdout_text = str(completed.stdout or "")
            stderr_text = str(completed.stderr or "")
            exit_code = int(completed.returncode)
            status = "completed" if exit_code == 0 else "blocked"
            if exit_code != 0:
                error_summary = f"process exited with code {exit_code}"
        except subprocess.TimeoutExpired as exc:
            stdout_text = str(exc.stdout or "")
            stderr_text = str(exc.stderr or "")
            status = "blocked"
            exit_code = -1
            error_summary = f"process timed out after {int(spec.timeout_s)}s"
        except Exception as exc:
            status = "blocked"
            exit_code = -1
            error_summary = f"{type(exc).__name__}: {exc}"

        stdout_path.write_text(stdout_text, encoding="utf-8")
        stderr_path.write_text(stderr_text, encoding="utf-8")
        produced_artifacts = _collect_produced_artifacts(spec=spec)
        duration_ms = max(0, int(round((time.time() - start) * 1000)))
        result = SandboxExecutionResult(
            run_id=run_id,
            status=status,
            exit_code=exit_code,
            duration_ms=duration_ms,
            stdout_log_ref=str(stdout_path),
            stderr_log_ref=str(stderr_path),
            produced_artifacts=produced_artifacts,
            error_summary=error_summary[:220],
        )
        _write_run_manifest(manifest_path=manifest_path, spec=spec, result=result, runtime_details={})
        return result


def _docker_mount_specs(spec: SandboxCommandSpec) -> list[tuple[Path, str]]:
    mounts: list[tuple[Path, str]] = []
    for index, raw_root in enumerate(spec.allowed_roots):
        host_root = Path(raw_root).resolve(strict=False)
        container_root = "/workspace" if index == 0 else f"/workspace-{index}"
        mounts.append((host_root, container_root))
    return mounts


def _container_path_for_host(host_path: Path, mounts: list[tuple[Path, str]]) -> str:
    resolved = host_path.resolve(strict=False)
    for root, container_root in mounts:
        if _path_within_root(resolved, root):
            relative = resolved.relative_to(root.resolve(strict=False))
            if str(relative) in {"", "."}:
                return container_root
            return f"{container_root}/{str(relative).replace('\\', '/')}"
    return str(resolved).replace("\\", "/")


def _translate_argv_for_container(argv: list[str], mounts: list[tuple[Path, str]]) -> list[str]:
    translated: list[str] = []
    for token in argv:
        text = str(token or "").strip()
        if not text:
            continue
        path = Path(text)
        if path.is_absolute():
            translated.append(_container_path_for_host(path, mounts))
        else:
            translated.append(text.replace("\\", "/"))
    return translated


def _best_effort_cleanup_stale_docker_state(*, docker: str, container_name: str, cidfile: Path) -> None:
    stale_container_id = ""
    if cidfile.exists():
        try:
            stale_container_id = _clean_text(cidfile.read_text(encoding="utf-8", errors="ignore"), limit=120)
        except Exception:
            stale_container_id = ""
        try:
            cidfile.unlink()
        except Exception:
            pass
    for target in (container_name, stale_container_id):
        target_text = str(target or "").strip()
        if not target_text:
            continue
        try:
            subprocess.run(
                [docker, "rm", "-f", target_text],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                shell=False,
            )
        except Exception:
            pass


class DockerIsolatedSandboxRunner:
    runner_kind = DOCKER_RUNNER_KIND
    isolation_level = DOCKER_ISOLATION_LEVEL

    def execute(
        self,
        *,
        proposal_id: str,
        spec: SandboxCommandSpec,
        run_root: Path,
    ) -> SandboxExecutionResult:
        if not sandbox_docker_engine_available():
            raise SandboxValidationError("DOCKER_UNAVAILABLE", "docker engine is not available for phase-2 sandbox execution")
        image_ref = sandbox_docker_image_ref(spec.image_ref)
        if not sandbox_docker_image_available(image_ref):
            raise SandboxValidationError("DOCKER_IMAGE_UNAVAILABLE", f"docker image is not available: {image_ref}")

        run_id = str(proposal_id or "").strip() or f"run-{int(time.time())}"
        run_dir = Path(run_root).resolve(strict=False)
        run_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = run_dir / "stdout.txt"
        stderr_path = run_dir / "stderr.txt"
        manifest_path = run_dir / "run.json"
        cidfile = run_dir / "container.cid"
        container_name = f"amadeus-sbox-{run_id}".lower().replace("_", "-")
        mounts = _docker_mount_specs(spec)
        container_cwd = _container_path_for_host(Path(spec.cwd), mounts)
        translated_argv = _translate_argv_for_container(list(spec.argv), mounts)
        docker = shutil.which("docker")
        if not docker:
            raise SandboxValidationError("DOCKER_UNAVAILABLE", "docker CLI is not available for phase-2 sandbox execution")
        _best_effort_cleanup_stale_docker_state(
            docker=docker,
            container_name=container_name,
            cidfile=cidfile,
        )

        command = [
            docker,
            "run",
            "--rm",
            "--name",
            container_name,
            "--cidfile",
            str(cidfile),
            "--network",
            DEFAULT_DOCKER_NETWORK_POLICY,
            "--workdir",
            container_cwd,
            "--mount",
            "type=tmpfs,destination=/tmp",
            "--env",
            "PYTHONIOENCODING=utf-8",
            "--env",
            "PYTHONUTF8=1",
        ]
        for host_root, container_root in mounts:
            command.extend(["--mount", f"type=bind,source={host_root},target={container_root}"])
        command.extend([image_ref, *translated_argv])

        exit_code = -1
        status = "blocked"
        error_summary = ""
        stdout_text = ""
        stderr_text = ""
        start = time.time()
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(1, int(spec.timeout_s)),
                shell=False,
            )
            stdout_text = str(completed.stdout or "")
            stderr_text = str(completed.stderr or "")
            exit_code = int(completed.returncode)
            status = "completed" if exit_code == 0 else "blocked"
            if exit_code != 0:
                error_summary = f"process exited with code {exit_code}"
        except subprocess.TimeoutExpired as exc:
            stdout_text = str(exc.stdout or "")
            stderr_text = str(exc.stderr or "")
            status = "blocked"
            exit_code = -1
            error_summary = f"process timed out after {int(spec.timeout_s)}s"
            try:
                subprocess.run(
                    [docker, "rm", "-f", container_name],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=20,
                    shell=False,
                )
            except Exception:
                pass
        except Exception as exc:
            status = "blocked"
            exit_code = -1
            error_summary = f"{type(exc).__name__}: {exc}"

        stdout_path.write_text(stdout_text, encoding="utf-8")
        stderr_path.write_text(stderr_text, encoding="utf-8")
        produced_artifacts = _collect_produced_artifacts(spec=spec)
        duration_ms = max(0, int(round((time.time() - start) * 1000)))
        container_id = _clean_text(
            cidfile.read_text(encoding="utf-8", errors="ignore") if cidfile.exists() else "",
            limit=120,
        )
        if cidfile.exists():
            try:
                cidfile.unlink()
            except Exception:
                pass
        result = SandboxExecutionResult(
            run_id=run_id,
            status=status,
            exit_code=exit_code,
            duration_ms=duration_ms,
            stdout_log_ref=str(stdout_path),
            stderr_log_ref=str(stderr_path),
            produced_artifacts=produced_artifacts,
            error_summary=error_summary[:220],
        )
        _write_run_manifest(
            manifest_path=manifest_path,
            spec=spec,
            result=result,
            runtime_details={
                "container_name": container_name,
                "container_id": container_id,
                "container_workdir": container_cwd,
                "translated_argv": translated_argv,
            },
        )
        return result


def execute_sandbox_command(
    *,
    proposal_id: str,
    spec: SandboxCommandSpec,
    run_root: Path,
) -> SandboxExecutionResult:
    if str(spec.runner_kind or "").strip().lower() == DOCKER_RUNNER_KIND:
        runner = DockerIsolatedSandboxRunner()
    else:
        runner = LocalRestrictedSandboxRunner()
    return runner.execute(proposal_id=proposal_id, spec=spec, run_root=run_root)


__all__ = [
    "ATTACHED_REPO_WORKSPACE_ROOT_KIND",
    "DEFAULT_DOCKER_IMAGE_REF",
    "DEFAULT_DOCKER_NETWORK_POLICY",
    "DEFAULT_LOCAL_NETWORK_POLICY",
    "DEFAULT_WORKSPACE_ROOT_KIND",
    "DOCKER_ISOLATION_LEVEL",
    "DOCKER_RUNNER_KIND",
    "DockerIsolatedSandboxRunner",
    "LOCAL_ISOLATION_LEVEL",
    "LOCAL_RUNNER_KIND",
    "LocalRestrictedSandboxRunner",
    "SandboxCommandSpec",
    "SandboxExecutionResult",
    "SandboxValidationError",
    "build_execution_preview",
    "build_sandbox_command_spec",
    "ensure_docker_sandbox_image",
    "execute_sandbox_command",
    "sandbox_docker_asset_dir",
    "sandbox_docker_engine_available",
    "sandbox_docker_image_available",
    "sandbox_docker_image_ref",
]
