from __future__ import annotations

from typing import Any


EXTERNAL_HARNESS_KINDS = ("deep_agents", "codex_harness", "claude_harness", "openclaw_harness")


def _clean_text(value: Any, *, limit: int = 220, lower: bool = False) -> str:
    text = str(value or "").strip()[: max(1, int(limit))]
    return text.lower() if lower else text


def _external_row(kind: str) -> dict[str, Any]:
    return {
        "harness_kind": kind,
        "adapter_kind": kind,
        "available_for_preview": False,
        "runtime_enabled": False,
        "result_only": True,
        "persona_memory_ownership": False,
        "requires_operator_install": True,
        "requires_approval": True,
        "memory_policy": "no_persona_memory_ownership",
        "writeback_policy": "result_only",
        "status": "disabled",
        "blocked_surfaces": [
            "code_execution",
            "package_install",
            "networked_execution",
            "git_mutation",
            "persona_memory_write",
        ],
    }


def build_executor_harness_registry() -> dict[str, dict[str, Any]]:
    registry = {
        "sandbox_runner": {
            "harness_kind": "sandbox_runner",
            "adapter_kind": "sandbox_runner",
            "available_for_preview": True,
            "runtime_enabled": True,
            "result_only": True,
            "persona_memory_ownership": False,
            "requires_operator_install": False,
            "requires_approval": True,
            "memory_policy": "no_persona_memory_ownership",
            "writeback_policy": "result_only",
            "status": "enabled",
            "blocked_surfaces": ["privileged_container", "docker_socket", "host_secret_passthrough"],
        }
    }
    for kind in EXTERNAL_HARNESS_KINDS:
        registry[kind] = _external_row(kind)
    return registry


def describe_harness_boundary(harness_kind: str) -> dict[str, Any]:
    key = _clean_text(harness_kind, limit=80, lower=True)
    registry = build_executor_harness_registry()
    if key in registry:
        return dict(registry[key])
    return {
        "harness_kind": key,
        "adapter_kind": key,
        "available_for_preview": False,
        "runtime_enabled": False,
        "result_only": True,
        "persona_memory_ownership": False,
        "requires_operator_install": True,
        "requires_approval": True,
        "memory_policy": "no_persona_memory_ownership",
        "writeback_policy": "result_only",
        "status": "unknown",
        "blocked_surfaces": ["unknown_harness"],
    }


def normalize_external_harness_result(raw: dict[str, Any] | None) -> dict[str, Any]:
    row = dict(raw) if isinstance(raw, dict) else {}
    kind = _clean_text(row.get("harness_kind") or row.get("adapter_kind"), limit=80, lower=True)
    boundary = describe_harness_boundary(kind)
    return {
        "harness_kind": boundary["harness_kind"],
        "status": _clean_text(row.get("status"), limit=80, lower=True) or "recorded",
        "summary": _clean_text(row.get("summary") or row.get("result_summary"), limit=320),
        "result_only": True,
        "persona_memory_ownership": False,
        "memory_policy": "no_persona_memory_ownership",
        "writeback_policy": "result_only",
        "runtime_enabled": bool(boundary.get("runtime_enabled", False)),
    }


__all__ = [
    "EXTERNAL_HARNESS_KINDS",
    "build_executor_harness_registry",
    "describe_harness_boundary",
    "normalize_external_harness_result",
]
