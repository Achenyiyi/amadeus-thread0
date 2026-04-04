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


_ALLOWED_EXECUTORS = {"python", "pytest", "rg"}
_BLOCKED_PYTHON_MODULE_PREFIXES = ("pip", "ensurepip")
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
    return text.endswith((".py", ".txt", ".md", ".json", ".yaml", ".yml"))


def _normalize_profile(executor: str, argv: list[str], cwd: Path, allowed_roots: list[Path]) -> str:
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

    raise SandboxValidationError("INVALID_EXECUTOR", f"unsupported executor: {executor}")


def build_sandbox_command_spec(
    *,
    argv: Any,
    cwd: Any,
    allowed_roots: Any,
    timeout_s: Any,
    writes_expected: Any,
    expected_artifacts: Any = None,
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

    return SandboxCommandSpec(
        executor=executor,
        profile=profile,
        argv=normalized_argv,
        cwd=str(resolved_cwd),
        allowed_roots=[str(root) for root in roots],
        timeout_s=timeout_value,
        writes_expected=_clean_bool(writes_expected, False),
        expected_artifacts=artifacts,
    )


def build_execution_preview(spec: SandboxCommandSpec) -> dict[str, Any]:
    return {
        "runner_kind": "local_restricted_runner",
        "isolation_level": "host_local_restricted",
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


class LocalRestrictedSandboxRunner:
    runner_kind = "local_restricted_runner"
    isolation_level = "host_local_restricted"

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
        produced_artifacts: list[str] = []
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

        cwd_path = Path(spec.cwd)
        for relative in spec.expected_artifacts:
            candidate = (cwd_path / relative).resolve(strict=False)
            if not any(_path_within_root(candidate, Path(root)) for root in spec.allowed_roots):
                continue
            if candidate.exists():
                produced_artifacts.append(str(candidate))

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
        manifest_path.write_text(
            json.dumps(
                {
                    "run_id": result.run_id,
                    "runner_kind": self.runner_kind,
                    "isolation_level": self.isolation_level,
                    "spec": {
                        "executor": spec.executor,
                        "profile": spec.profile,
                        "argv": list(spec.argv),
                        "cwd": spec.cwd,
                        "allowed_roots": list(spec.allowed_roots),
                        "timeout_s": spec.timeout_s,
                        "writes_expected": spec.writes_expected,
                        "expected_artifacts": list(spec.expected_artifacts),
                    },
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
        return result


__all__ = [
    "LocalRestrictedSandboxRunner",
    "SandboxCommandSpec",
    "SandboxExecutionResult",
    "SandboxValidationError",
    "build_execution_preview",
    "build_sandbox_command_spec",
]
