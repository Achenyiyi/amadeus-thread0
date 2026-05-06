import unittest

from amadeus_thread0.runtime.executor_adapter import (
    EXECUTOR_ADAPTER_CLAUDE,
    EXECUTOR_ADAPTER_CODEX,
    EXECUTOR_ADAPTER_DEEP_AGENTS,
    EXECUTOR_ADAPTER_OPENCLAW,
)
from evals.run_executor_adapter_audit import (
    _aggregate_overall_status,
    _build_check_specs,
    disabled_adapter_matrix,
    render_markdown,
)


class ExecutorAdapterAuditTests(unittest.TestCase):
    def test_build_check_specs_covers_contract_and_runtime_integration(self):
        ids = {item["id"] for item in _build_check_specs("demo")}

        self.assertEqual(
            ids,
            {
                "executor_adapter_contract",
                "workspace_command_adapter_integration",
            },
        )

    def test_disabled_adapter_matrix_keeps_external_harnesses_fail_closed(self):
        matrix = disabled_adapter_matrix()
        by_kind = {row["adapter_kind"]: row for row in matrix}

        self.assertEqual(
            set(by_kind),
            {
                EXECUTOR_ADAPTER_DEEP_AGENTS,
                EXECUTOR_ADAPTER_CODEX,
                EXECUTOR_ADAPTER_CLAUDE,
                EXECUTOR_ADAPTER_OPENCLAW,
            },
        )
        for row in matrix:
            self.assertEqual(row["status"], "disabled")
            self.assertEqual(row["memory_policy"], "no_persona_memory_ownership")
            self.assertEqual(row["writeback_policy"], "result_only")

    def test_aggregate_reports_ready_when_checks_pass(self):
        summary = _aggregate_overall_status(
            [
                {"id": "a", "status": "passed", "blocking": True},
                {"id": "b", "status": "passed", "blocking": True},
            ]
        )

        self.assertEqual(summary["overall_status"], "passed")
        self.assertEqual(summary["readiness_status"], "executor_adapter_ready")
        self.assertEqual(summary["summary"]["passed"], 2)

    def test_aggregate_reports_blocking_failures(self):
        summary = _aggregate_overall_status(
            [
                {"id": "a", "status": "passed", "blocking": True},
                {"id": "b", "status": "failed", "blocking": True},
            ]
        )

        self.assertEqual(summary["overall_status"], "failed")
        self.assertEqual(summary["readiness_status"], "executor_adapter_in_progress")
        self.assertEqual(summary["blocking_failure_ids"], ["b"])

    def test_render_markdown_includes_disabled_harness_table(self):
        rendered = render_markdown(
            {
                "run_id": "executor-audit",
                "generated_at": "2026-05-06 12:00:00",
                "overall_status": "passed",
                "readiness_status": "executor_adapter_ready",
                "summary": {"total": 1, "passed": 1, "failed": 0},
                "disabled_adapters": [
                    {
                        "adapter_kind": EXECUTOR_ADAPTER_CODEX,
                        "status": "disabled",
                        "memory_policy": "no_persona_memory_ownership",
                        "writeback_policy": "result_only",
                    }
                ],
                "checks": [{"id": "executor_adapter_contract", "title": "Contract", "status": "passed", "duration_s": 0.1, "command": "python -m pytest"}],
            }
        )

        self.assertIn("# Executor Adapter Audit", rendered)
        self.assertIn("| Adapter | Status | Memory Policy | Writeback Policy |", rendered)
        self.assertIn("| `codex_harness` | `disabled` | `no_persona_memory_ownership` | `result_only` |", rendered)


if __name__ == "__main__":
    unittest.main()
