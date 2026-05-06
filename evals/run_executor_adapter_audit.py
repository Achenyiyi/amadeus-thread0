from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from amadeus_thread0.runtime.executor_adapter import (
    EXECUTOR_ADAPTER_CLAUDE,
    EXECUTOR_ADAPTER_CODEX,
    EXECUTOR_ADAPTER_DEEP_AGENTS,
    EXECUTOR_ADAPTER_OPENCLAW,
    describe_disabled_adapter,
)


REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

DISABLED_ADAPTERS = [
    EXECUTOR_ADAPTER_DEEP_AGENTS,
    EXECUTOR_ADAPTER_CODEX,
    EXECUTOR_ADAPTER_CLAUDE,
    EXECUTOR_ADAPTER_OPENCLAW,
]


def _python(*args: str) -> list[str]:
    return [sys.executable, *args]


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    return env


def _tail(text: str, *, limit: int = 2400) -> str:
    value = str(text or "")
    return value if len(value) <= limit else value[-limit:]


def _format_command(command: Sequence[str]) -> str:
    return subprocess.list2cmdline([str(part) for part in command])


def _run(command: Sequence[str]) -> dict[str, Any]:
    started = time.time()
    completed = subprocess.run(
        [str(part) for part in command],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_env(),
    )
    return {
        "returncode": int(completed.returncode),
        "stdout": str(completed.stdout or ""),
        "stderr": str(completed.stderr or ""),
        "duration_s": round(time.time() - started, 3),
    }


def _check(id: str, title: str, command: Sequence[str], *, blocking: bool = True) -> dict[str, Any]:
    outcome = _run(command)
    status = "passed" if int(outcome.get("returncode") or 0) == 0 else "failed"
    return {
        "id": id,
        "title": title,
        "blocking": bool(blocking),
        "command": _format_command(command),
        "status": status,
        "returncode": int(outcome.get("returncode") or 0),
        "duration_s": float(outcome.get("duration_s") or 0.0),
        "failure_reasons": [] if status == "passed" else ["command_returncode=" + str(outcome.get("returncode"))],
        "stdout_tail": _tail(str(outcome.get("stdout") or "")),
        "stderr_tail": _tail(str(outcome.get("stderr") or "")),
    }


def _build_check_specs(run_id: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "executor_adapter_contract",
            "title": "Executor Adapter Contract Tests",
            "command": _python("-m", "pytest", "tests/test_executor_adapter.py", "-q"),
        },
        {
            "id": "workspace_command_adapter_integration",
            "title": "Workspace Command Adapter Integration",
            "command": _python("-m", "pytest", "tests/test_sandbox_execution_runtime.py", "-q"),
        },
    ]


def disabled_adapter_matrix() -> list[dict[str, Any]]:
    return [describe_disabled_adapter(adapter_kind) for adapter_kind in DISABLED_ADAPTERS]


def _aggregate_overall_status(checks: Sequence[dict[str, Any]]) -> dict[str, Any]:
    rows = [dict(item) for item in checks]
    blocking_failure_ids = [
        str(row.get("id") or "")
        for row in rows
        if bool(row.get("blocking", True)) and str(row.get("status") or "") != "passed"
    ]
    failed = len([row for row in rows if str(row.get("status") or "") != "passed"])
    total = len(rows)
    overall = "failed" if blocking_failure_ids else "passed"
    return {
        "overall_status": overall,
        "readiness_status": "executor_adapter_ready" if overall == "passed" else "executor_adapter_in_progress",
        "blocking_failure_ids": blocking_failure_ids,
        "summary": {"total": total, "passed": total - failed, "failed": failed},
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = dict(report.get("summary") or {})
    lines = [
        f"# Executor Adapter Audit ({report.get('run_id', 'unknown')})",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Summary",
        "",
        f"- Total checks: `{summary.get('total', 0)}`",
        f"- Passed: `{summary.get('passed', 0)}`",
        f"- Failed: `{summary.get('failed', 0)}`",
        "",
        "## Disabled External Harnesses",
        "",
        "| Adapter | Status | Memory Policy | Writeback Policy |",
        "| --- | --- | --- | --- |",
    ]
    for row in report.get("disabled_adapters") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| `{row.get('adapter_kind', '')}` | `{row.get('status', '')}` | "
            f"`{row.get('memory_policy', '')}` | `{row.get('writeback_policy', '')}` |"
        )
    lines.extend(["", "## Checks", "", "| Check | Status | Duration (s) |", "| --- | --- | ---: |"])
    for row in report.get("checks") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| `{row.get('id', '')}` | `{row.get('status', '')}` | {float(row.get('duration_s') or 0.0):.3f} |"
        )
    for row in report.get("checks") or []:
        if not isinstance(row, dict):
            continue
        lines.extend(
            [
                "",
                f"## {row.get('title', row.get('id', 'unknown'))}",
                "",
                f"- Check Id: `{row.get('id', '')}`",
                f"- Status: `{row.get('status', '')}`",
                f"- Command: `{row.get('command', '')}`",
            ]
        )
        for reason in row.get("failure_reasons") or []:
            lines.append(f"- Failure: `{reason}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the executor adapter closure audit.")
    parser.add_argument("--run-tag", default="", help="Optional suffix for report filenames.")
    args = parser.parse_args()

    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    checks = [
        _check(spec["id"], spec["title"], spec["command"], blocking=bool(spec.get("blocking", True)))
        for spec in _build_check_specs(run_id)
    ]
    report = {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "checks": checks,
        "disabled_adapters": disabled_adapter_matrix(),
        **_aggregate_overall_status(checks),
    }
    json_path = REPORT_DIR / f"executor-adapter-audit-{run_id}.json"
    md_path = REPORT_DIR / f"executor-adapter-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[executor-adapter] json={json_path}")
    print(f"[executor-adapter] md={md_path}")
    print(f"[executor-adapter] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[executor-adapter] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if str(report.get("overall_status") or "") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
