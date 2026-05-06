from __future__ import annotations

from amadeus_thread0.runtime.executor_harness_registry import (
    build_executor_harness_registry,
    describe_harness_boundary,
    normalize_external_harness_result,
)


def test_external_harnesses_are_fail_closed_by_default():
    registry = build_executor_harness_registry()
    for harness in ("deep_agents", "codex_harness", "claude_harness", "openclaw_harness"):
        row = registry[harness]
        assert row["runtime_enabled"] is False
        assert row["persona_memory_ownership"] is False
        assert row["requires_approval"] is True
        assert row["writeback_policy"] == "result_only"


def test_sandbox_runner_remains_only_enabled_executor():
    registry = build_executor_harness_registry()
    enabled = [key for key, row in registry.items() if row["runtime_enabled"]]
    assert enabled == ["sandbox_runner"]


def test_external_result_normalization_is_result_only():
    result = normalize_external_harness_result(
        {
            "harness_kind": "codex_harness",
            "status": "completed",
            "summary": "recorded dry-run result",
            "memory_writes": [{"fact": "should be stripped"}],
        }
    )

    assert result["harness_kind"] == "codex_harness"
    assert result["writeback_policy"] == "result_only"
    assert result["persona_memory_ownership"] is False
    assert "memory_writes" not in result


def test_unknown_harness_boundary_fails_closed():
    boundary = describe_harness_boundary("unknown_runner")
    assert boundary["status"] == "unknown"
    assert boundary["runtime_enabled"] is False
    assert boundary["requires_operator_install"] is True
