from __future__ import annotations

import json
import importlib.util
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any


RUNTIME_ARTIFACT_NAMES = (
    "checkpoints.sqlite",
    "memories.sqlite",
    "decision_audit.jsonl",
    "mcp_audit.jsonl",
    "memory_store_audit.jsonl",
    "tool_audit.jsonl",
)

ASSET_DIR_NAMES = {
    "copy_wav",
    "tts_out",
    "__pycache__",
}

WORLDLINES_DIRNAME = "worldlines"

REQUIRED_DEPENDENCY_PROBES: tuple[tuple[str, str], ...] = (
    ("langgraph", "langgraph"),
    ("langchain", "langchain"),
    ("langchain_core", "langchain_core"),
    ("langchain_openai", "langchain_openai"),
    ("langchain_huggingface", "langchain_huggingface"),
    ("sentence_transformers", "sentence_transformers"),
    ("transformers", "transformers"),
    ("torch", "torch"),
    ("sqlite_vec", "sqlite_vec"),
    ("playwright", "playwright"),
    ("langgraph-checkpoint-sqlite", "langgraph.checkpoint.sqlite"),
)

OPTIONAL_DEPENDENCY_PROBES: tuple[tuple[str, str], ...] = (
    ("pyaudio", "pyaudio"),
)

DOCTOR_REQUIRED_KEYS = (
    "overall_status",
    "python",
    "dependencies",
    "pip_check",
    "env",
    "model_key",
    "playwright",
    "docker",
    "phase_readiness",
    "remediation",
)

DEFAULT_SANDBOX_IMAGE_REF = "amadeus-k-sandbox-python:phase2"
DEFAULT_SANDBOX_NETWORK_POLICY = "none"


def _safe_stat(path: Path) -> tuple[int, int]:
    try:
        st = path.stat()
        return int(st.st_size), int(st.st_mtime)
    except Exception:
        return 0, 0


def _safe_total_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return _safe_stat(path)[0]
    total = 0
    try:
        for child in path.rglob("*"):
            if child.is_file():
                total += _safe_stat(child)[0]
    except Exception:
        return total
    return total


def _runtime_artifacts_in_dir(path: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for name in RUNTIME_ARTIFACT_NAMES:
        file_path = path / name
        if not file_path.exists() or not file_path.is_file():
            continue
        size, modified_at = _safe_stat(file_path)
        if size <= 0:
            continue
        artifacts.append(
            {
                "name": name,
                "path": str(file_path),
                "size_bytes": size,
                "modified_at": modified_at,
            }
        )
    return artifacts


def _entry_summary(path: Path, *, kind: str) -> dict[str, Any]:
    artifacts = _runtime_artifacts_in_dir(path)
    return {
        "name": path.name,
        "path": str(path),
        "kind": kind,
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "size_bytes": _safe_total_size(path),
        "modified_at": max((int(item.get("modified_at") or 0) for item in artifacts), default=0),
        "smoke_like": _is_smoke_like(path.name),
    }


def _is_smoke_like(name: str) -> bool:
    raw = str(name or "").strip().lower()
    if not raw:
        return False
    return raw.startswith("smoke") or "smoke" in raw or "debug" in raw


def audit_runtime_layout(data_dir: Path) -> dict[str, Any]:
    root = Path(data_dir)
    shared_runtime = _entry_summary(root, kind="shared_root_runtime")
    isolated_worldlines: list[dict[str, Any]] = []
    legacy_runtime_dirs: list[dict[str, Any]] = []
    asset_dirs: list[dict[str, Any]] = []
    other_dirs: list[dict[str, Any]] = []

    if root.exists():
        try:
            entries = sorted(root.iterdir(), key=lambda p: p.name.lower())
        except Exception:
            entries = []
        for entry in entries:
            if not entry.is_dir():
                continue
            if entry.name == WORLDLINES_DIRNAME:
                try:
                    worldline_entries = sorted(entry.iterdir(), key=lambda p: p.name.lower())
                except Exception:
                    worldline_entries = []
                for child in worldline_entries:
                    if not child.is_dir():
                        continue
                    summary = _entry_summary(child, kind="isolated_worldline")
                    if summary["artifact_count"] > 0:
                        isolated_worldlines.append(summary)
                    else:
                        other_dirs.append(summary)
                continue
            if entry.name in ASSET_DIR_NAMES:
                asset_dirs.append(
                    {
                        "name": entry.name,
                        "path": str(entry),
                        "kind": "asset_dir",
                        "size_bytes": _safe_total_size(entry),
                    }
                )
                continue
            summary = _entry_summary(entry, kind="legacy_runtime_dir")
            if summary["artifact_count"] > 0:
                legacy_runtime_dirs.append(summary)
            else:
                other_dirs.append(summary)

    isolated_worldlines.sort(key=lambda item: (int(item.get("modified_at") or 0), str(item.get("name") or "")), reverse=True)
    legacy_runtime_dirs.sort(key=lambda item: (int(item.get("modified_at") or 0), str(item.get("name") or "")), reverse=True)
    other_dirs.sort(key=lambda item: str(item.get("name") or ""))
    asset_dirs.sort(key=lambda item: str(item.get("name") or ""))

    recommendations: list[str] = []
    if shared_runtime["artifact_count"] > 0:
        recommendations.append(
            "默认 plain CLI 会继续使用 data/ 下的 shared thread0 运行数据；干净演示优先用 --fresh-thread。"
        )
    if legacy_runtime_dirs:
        smoke_dirs = [item for item in legacy_runtime_dirs if bool(item.get("smoke_like"))]
        if smoke_dirs:
            recommendations.append(
                f"发现 {len(smoke_dirs)} 个疑似 smoke/debug 运行目录；清理前先确认是否还需要保留回归证据。"
            )
        else:
            recommendations.append(
                f"发现 {len(legacy_runtime_dirs)} 个 data/ 根目录下的历史 runtime 目录；建议逐个审阅后迁移或删除。"
            )
    if isolated_worldlines:
        recommendations.append(
            f"发现 {len(isolated_worldlines)} 个隔离 worldline 目录；这类目录可安全作为独立演示/实验运行根。"
        )
    if not recommendations:
        recommendations.append("当前 data/ 目录结构干净，没有发现共享运行污染或历史 runtime 残留。")

    return {
        "data_dir": str(root),
        "exists": root.exists(),
        "shared_runtime": shared_runtime,
        "isolated_worldlines": isolated_worldlines,
        "legacy_runtime_dirs": legacy_runtime_dirs,
        "asset_dirs": asset_dirs,
        "other_dirs": other_dirs,
        "stats": {
            "shared_artifact_count": int(shared_runtime.get("artifact_count") or 0),
            "isolated_worldline_count": len(isolated_worldlines),
            "legacy_runtime_dir_count": len(legacy_runtime_dirs),
            "asset_dir_count": len(asset_dirs),
            "other_dir_count": len(other_dirs),
        },
        "recommendations": recommendations,
    }


def render_runtime_audit_report(audit: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("[runtime-audit]")
    lines.append("data_dir=" + str(audit.get("data_dir") or ""))
    lines.append("exists=" + ("yes" if bool(audit.get("exists")) else "no"))

    stats = audit.get("stats") if isinstance(audit.get("stats"), dict) else {}
    lines.append(
        "shared_artifacts={shared} | isolated_worldlines={isolated} | legacy_runtime_dirs={legacy}".format(
            shared=int(stats.get("shared_artifact_count") or 0),
            isolated=int(stats.get("isolated_worldline_count") or 0),
            legacy=int(stats.get("legacy_runtime_dir_count") or 0),
        )
    )

    shared = audit.get("shared_runtime") if isinstance(audit.get("shared_runtime"), dict) else {}
    shared_artifacts = shared.get("artifacts") if isinstance(shared.get("artifacts"), list) else []
    if shared_artifacts:
        lines.append("")
        lines.append("[shared-root]")
        lines.append("path=" + str(shared.get("path") or ""))
        lines.append(
            "artifacts=" + ", ".join(str(item.get("name") or "") for item in shared_artifacts if isinstance(item, dict))
        )

    isolated = audit.get("isolated_worldlines") if isinstance(audit.get("isolated_worldlines"), list) else []
    if isolated:
        lines.append("")
        lines.append("[isolated-worldlines]")
        for item in isolated:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- {name} | size={size} | artifacts={artifacts}".format(
                    name=str(item.get("name") or ""),
                    size=int(item.get("size_bytes") or 0),
                    artifacts=int(item.get("artifact_count") or 0),
                )
            )

    legacy = audit.get("legacy_runtime_dirs") if isinstance(audit.get("legacy_runtime_dirs"), list) else []
    if legacy:
        lines.append("")
        lines.append("[legacy-runtime-dirs]")
        for item in legacy:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- {name} | smoke_like={smoke_like} | size={size} | artifacts={artifacts}".format(
                    name=str(item.get("name") or ""),
                    smoke_like="yes" if bool(item.get("smoke_like")) else "no",
                    size=int(item.get("size_bytes") or 0),
                    artifacts=int(item.get("artifact_count") or 0),
                )
            )

    recs = audit.get("recommendations") if isinstance(audit.get("recommendations"), list) else []
    if recs:
        lines.append("")
        lines.append("[recommendations]")
        for item in recs:
            lines.append("- " + str(item))

    return "\n".join(lines)


def audit_runtime_layout_json(data_dir: Path) -> str:
    return json.dumps(audit_runtime_layout(data_dir), ensure_ascii=False, indent=2)


def _probe_module(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False


def _doctor_dependency_report() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for package, module_name in REQUIRED_DEPENDENCY_PROBES:
        present = _probe_module(module_name)
        rows.append(
            {
                "package": package,
                "module": module_name,
                "required": True,
                "status": "ok" if present else "missing",
            }
        )
    for package, module_name in OPTIONAL_DEPENDENCY_PROBES:
        present = _probe_module(module_name)
        rows.append(
            {
                "package": package,
                "module": module_name,
                "required": False,
                "status": "ok" if present else "missing_optional",
            }
        )
    return rows


def _graph_dependency_blockers(dependencies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in dependencies if item.get("required") and item.get("status") != "ok"]


def _missing_dependency_remediation(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "kind": "missing_package",
            "package": str(item.get("package") or ""),
            "module": str(item.get("module") or ""),
            "install_hint": "python -m pip install -r requirements.txt",
        }
        for item in items
    ]


def _run_pip_check(timeout_s: int = 12) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pip", "check"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return {"status": "failed", "details": f"pip check timed out after {timeout_s}s"}
    except Exception as exc:
        return {"status": "failed", "details": str(exc)}

    details = "\n".join(part.strip() for part in [completed.stdout, completed.stderr] if part and part.strip()).strip()
    return {
        "status": "ok" if int(completed.returncode or 0) == 0 else "failed",
        "details": details or "No broken requirements found.",
        "exit_code": int(completed.returncode or 0),
    }


def _load_dotenv_for_doctor(cwd: Path | None = None) -> dict[str, Any]:
    root = Path(cwd or Path.cwd())
    candidates = [root / ".env", Path(__file__).resolve().parents[2] / ".env"]
    dotenv_path = next((path for path in candidates if path.exists()), None)
    if dotenv_path is None:
        return {"dotenv_loaded": False, "dotenv_path": None}

    if _probe_module("dotenv"):
        try:
            from dotenv import load_dotenv

            loaded = bool(load_dotenv(dotenv_path=dotenv_path, override=False))
            return {"dotenv_loaded": loaded, "dotenv_path": str(dotenv_path)}
        except Exception as exc:
            return {"dotenv_loaded": False, "dotenv_path": str(dotenv_path), "error": str(exc)}

    loaded_any = False
    try:
        for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not key or key in os.environ:
                continue
            os.environ[key] = value.strip().strip('"').strip("'")
            loaded_any = True
    except Exception as exc:
        return {"dotenv_loaded": False, "dotenv_path": str(dotenv_path), "error": str(exc)}
    return {"dotenv_loaded": loaded_any, "dotenv_path": str(dotenv_path), "fallback_parser": True}


def _model_key_report() -> dict[str, Any]:
    key_vars = ("AMADEUS_MODEL_API_KEY", "DASHSCOPE_API_KEY", "OPENAI_API_KEY")
    found = next((name for name in key_vars if str(os.getenv(name) or "").strip()), None)
    return {
        "status": "set" if found else "missing",
        "env_var": found or "AMADEUS_MODEL_API_KEY",
        "checked": list(key_vars),
    }


def _docker_report(timeout_s: int = 6) -> dict[str, Any]:
    base = {
        "image_ref": str(os.getenv("AMADEUS_SANDBOX_DOCKER_IMAGE", DEFAULT_SANDBOX_IMAGE_REF) or DEFAULT_SANDBOX_IMAGE_REF),
        "network_policy": str(
            os.getenv("AMADEUS_SANDBOX_DOCKER_NETWORK_POLICY", DEFAULT_SANDBOX_NETWORK_POLICY)
            or DEFAULT_SANDBOX_NETWORK_POLICY
        ),
        "runner_kind": "docker_isolated_runner",
        "isolation_level": "docker_local_isolated",
    }
    try:
        completed = subprocess.run(
            ["docker", "version", "--format", "{{json .}}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except FileNotFoundError:
        return {**base, "status": "blocked", "details": "docker CLI not found"}
    except subprocess.TimeoutExpired:
        return {**base, "status": "blocked", "details": f"docker version timed out after {timeout_s}s"}
    except Exception as exc:
        return {**base, "status": "blocked", "details": str(exc)}

    details = "\n".join(part.strip() for part in [completed.stdout, completed.stderr] if part and part.strip()).strip()
    return {
        **base,
        "status": "ok" if int(completed.returncode or 0) == 0 else "blocked",
        "details": details,
        "exit_code": int(completed.returncode or 0),
    }


def build_graph_startup_preflight_report(*, cwd: Path | None = None) -> dict[str, Any]:
    """Build a lightweight graph-startup report for normal CLI startup."""

    dotenv_info = _load_dotenv_for_doctor(cwd)
    dependencies = _doctor_dependency_report()
    model_key = _model_key_report()
    required_missing = _graph_dependency_blockers(dependencies)
    model_blocked = model_key.get("status") != "set"
    phase_readiness = {
        "graph": "blocked" if required_missing or model_blocked else "ready",
    }

    remediation = _missing_dependency_remediation(required_missing)
    if model_blocked:
        remediation.append(
            {
                "kind": "missing_model_key",
                "env_var": str(model_key.get("env_var") or "AMADEUS_MODEL_API_KEY"),
                "install_hint": "Copy .env.example to .env and set AMADEUS_MODEL_API_KEY.",
            }
        )

    return {
        "overall_status": "failed" if phase_readiness["graph"] == "blocked" else "passed",
        "dependencies": dependencies,
        "env": {
            **dotenv_info,
            "model_key": "set" if model_key.get("status") == "set" else "missing",
        },
        "model_key": model_key,
        "phase_readiness": phase_readiness,
        "remediation": remediation,
    }


def build_runtime_doctor_report(*, phase: str | None = None, cwd: Path | None = None) -> dict[str, Any]:
    """Build a first-run readiness report without importing graph/runtime bundles."""

    dotenv_info = _load_dotenv_for_doctor(cwd)
    dependencies = _doctor_dependency_report()
    pip_check = _run_pip_check()
    model_key = _model_key_report()
    docker = _docker_report()

    required_missing = _graph_dependency_blockers(dependencies)
    missing_by_package = {str(item.get("package") or "") for item in required_missing}
    graph_dependency_blocked = bool(required_missing)
    model_blocked = model_key.get("status") != "set"
    pip_blocked = pip_check.get("status") != "ok"
    playwright_blocked = "playwright" in missing_by_package
    docker_blocked = docker.get("status") != "ok" or docker.get("network_policy") != DEFAULT_SANDBOX_NETWORK_POLICY

    phase_readiness = {
        "graph": "blocked" if graph_dependency_blocked or model_blocked or pip_blocked else "ready",
        "live_browser": "blocked" if graph_dependency_blocked or playwright_blocked else "ready",
        "sandbox_phase2": "blocked" if graph_dependency_blocked or docker_blocked else "ready",
    }

    remediation: list[dict[str, Any]] = []
    remediation.extend(_missing_dependency_remediation(required_missing))
    if pip_blocked:
        remediation.append(
            {
                "kind": "pip_check_failed",
                "install_hint": "python -m pip install -r requirements.txt",
                "details": str(pip_check.get("details") or ""),
            }
        )
    if model_blocked:
        remediation.append(
            {
                "kind": "missing_model_key",
                "env_var": str(model_key.get("env_var") or "AMADEUS_MODEL_API_KEY"),
                "install_hint": "Copy .env.example to .env and set AMADEUS_MODEL_API_KEY.",
            }
        )
    if docker.get("status") != "ok":
        remediation.append(
            {
                "kind": "docker_unavailable",
                "install_hint": "Install/start Docker Desktop, then rerun python -m amadeus_thread0.cli --doctor --phase sandbox_phase2.",
                "details": str(docker.get("details") or ""),
            }
        )
    if docker.get("network_policy") != DEFAULT_SANDBOX_NETWORK_POLICY:
        remediation.append(
            {
                "kind": "sandbox_network_policy",
                "expected": DEFAULT_SANDBOX_NETWORK_POLICY,
                "actual": str(docker.get("network_policy") or ""),
                "install_hint": "Set AMADEUS_SANDBOX_DOCKER_NETWORK_POLICY=none.",
            }
        )

    report = {
        "overall_status": "failed" if any(value == "blocked" for value in phase_readiness.values()) else "passed",
        "python": {
            "status": "ok",
            "version": platform.python_version(),
            "executable": sys.executable,
            "platform": platform.platform(),
        },
        "dependencies": dependencies,
        "pip_check": pip_check,
        "env": {
            **dotenv_info,
            "model_key": "set" if model_key.get("status") == "set" else "missing",
        },
        "model_key": model_key,
        "playwright": {
            "status": "blocked" if playwright_blocked else "ok",
            "package": "playwright",
        },
        "docker": docker,
        "phase_readiness": phase_readiness,
        "remediation": remediation,
    }
    return {key: report[key] for key in DOCTOR_REQUIRED_KEYS}


def render_runtime_doctor_report(report: dict[str, Any], *, phase: str | None = None) -> str:
    selected_phase = str(phase or "").strip()
    title = "[doctor" + (":" + selected_phase if selected_phase else "") + "]"
    lines: list[str] = [title]
    lines.append("overall_status=" + str(report.get("overall_status") or "unknown"))

    phase_readiness = report.get("phase_readiness") if isinstance(report.get("phase_readiness"), dict) else {}
    if selected_phase:
        lines.append("phase_readiness." + selected_phase + "=" + str(phase_readiness.get(selected_phase) or "unknown"))
    else:
        lines.append("[phase-readiness]")
        for name in ("graph", "live_browser", "sandbox_phase2"):
            lines.append("- " + name + "=" + str(phase_readiness.get(name) or "unknown"))

    if not selected_phase or selected_phase == "graph":
        missing = [
            str(item.get("package") or "")
            for item in report.get("dependencies", [])
            if isinstance(item, dict) and item.get("required") and item.get("status") != "ok"
        ]
        lines.append("")
        lines.append("[graph]")
        lines.append("python=" + str((report.get("python") or {}).get("version") or "unknown"))
        lines.append("model_key=" + str((report.get("model_key") or {}).get("status") or "unknown"))
        lines.append("pip_check=" + str((report.get("pip_check") or {}).get("status") or "unknown"))
        lines.append("missing_required=" + (", ".join(missing) if missing else "(none)"))

    if not selected_phase or selected_phase == "live_browser":
        playwright = report.get("playwright") if isinstance(report.get("playwright"), dict) else {}
        lines.append("")
        lines.append("[live_browser]")
        lines.append("playwright=" + str(playwright.get("status") or "unknown"))

    if not selected_phase or selected_phase == "sandbox_phase2":
        docker = report.get("docker") if isinstance(report.get("docker"), dict) else {}
        lines.append("")
        lines.append("[sandbox_phase2]")
        lines.append("docker=" + str(docker.get("status") or "unknown"))
        lines.append("runner_kind=" + str(docker.get("runner_kind") or "docker_isolated_runner"))
        lines.append("isolation_level=" + str(docker.get("isolation_level") or "docker_local_isolated"))
        lines.append("image_ref=" + str(docker.get("image_ref") or DEFAULT_SANDBOX_IMAGE_REF))
        lines.append("network_policy=" + str(docker.get("network_policy") or DEFAULT_SANDBOX_NETWORK_POLICY))

    blockers = [item for item in report.get("remediation", []) if isinstance(item, dict)]
    if blockers:
        lines.append("")
        lines.append("[global-blockers]")
        for item in blockers:
            label = str(item.get("kind") or "blocker")
            target = str(item.get("package") or item.get("env_var") or item.get("expected") or "").strip()
            hint = str(item.get("install_hint") or "").strip()
            line = "- " + label
            if target:
                line += ": " + target
            if hint:
                line += " | " + hint
            lines.append(line)
    else:
        lines.append("")
        lines.append("[global-blockers]")
        lines.append("- (none)")

    return "\n".join(lines)
