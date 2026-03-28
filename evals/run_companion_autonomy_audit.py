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
REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _python_cmd(*args: str) -> list[str]:
    return [sys.executable, *args]


def _base_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    return env


def _tail_text(text: str, *, limit: int = 2400) -> str:
    content = str(text or "").strip()
    return content if len(content) <= limit else content[-limit:]


def _format_command(command: Sequence[str]) -> str:
    return subprocess.list2cmdline([str(part) for part in command])


def _run_command(command: Sequence[str]) -> dict[str, Any]:
    start = time.time()
    completed = subprocess.run(
        [str(part) for part in command],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_base_env(),
    )
    return {
        "returncode": int(completed.returncode),
        "stdout": str(completed.stdout or ""),
        "stderr": str(completed.stderr or ""),
        "duration_s": round(time.time() - start, 3),
    }


def _load_json(path: str) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _previous_reports() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(REPORT_DIR.glob("companion-autonomy-audit-*.json")):
        payload = _load_json(str(path))
        if not payload:
            continue
        rows.append(payload)
    return rows


def _pass_streak(statuses: Sequence[str]) -> int:
    streak = 0
    for status in reversed([str(item or "").strip() for item in statuses]):
        if status != "passed":
            break
        streak += 1
    return streak


def _check(id: str, title: str, command: Sequence[str], *, blocking: bool = True) -> dict[str, Any]:
    outcome = _run_command(command)
    return {
        "id": id,
        "title": title,
        "blocking": blocking,
        "command": _format_command(command),
        "status": "passed" if int(outcome["returncode"]) == 0 else "failed",
        "returncode": int(outcome["returncode"]),
        "duration_s": float(outcome["duration_s"]),
        "stdout_tail": _tail_text(outcome["stdout"]),
        "stderr_tail": _tail_text(outcome["stderr"]),
    }


def _freeze_gate_readiness(check: dict[str, Any]) -> str:
    if str(check.get("status") or "") != "passed":
        return "backend_maturation_required"
    stdout = str(check.get("stdout_tail") or "")
    if "readiness=freeze_gate_ready" in stdout:
        return "freeze_gate_ready"
    return "freeze_gate_candidate"


def _render_markdown(report: dict[str, Any]) -> str:
    summary = dict(report.get("summary") or {})
    lines = [
        f"# Companion Autonomy Audit ({report.get('run_id', 'unknown')})",
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
        f"- Historical pass streak: `{summary.get('historical_pass_streak', 0)}`",
        f"- Freeze gate readiness: `{report.get('freeze_gate_readiness', 'unknown')}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Duration (s) |",
        "| --- | --- | ---: |",
    ]
    for row in report.get("checks") or []:
        if not isinstance(row, dict):
            continue
        lines.append(f"| `{row.get('id', '')}` | `{row.get('status', '')}` | {float(row.get('duration_s') or 0.0):.3f} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Companion Autonomy closure audit.")
    parser.add_argument("--run-tag", default="", help="Optional suffix for report filenames.")
    args = parser.parse_args()

    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    checks = [
        _check(
            "freeze_gate",
            "Backend Freeze Gate Audit",
            _python_cmd("evals/run_backend_freeze_gate_audit.py", "--run-tag", f"{run_id}-freeze"),
        ),
        _check(
            "autonomy_contract",
            "Autonomy Contract Pytests",
            _python_cmd(
                "-m",
                "pytest",
                "tests/test_action_packet_contract.py",
                "tests/test_companion_autonomy_runtime.py",
                "tests/test_autonomy_writeback.py",
                "tests/test_autonomy_backend_contract.py",
                "tests/test_backend_api.py",
                "tests/test_backend_session.py",
                "tests/test_tool_approval_policy.py",
                "-q",
            ),
        ),
    ]

    passed = len([row for row in checks if str(row.get("status") or "") == "passed"])
    failed = len(checks) - passed
    blocking_failures = [str(row.get("id") or "") for row in checks if str(row.get("status") or "") != "passed" and bool(row.get("blocking", True))]
    overall_status = "passed" if not blocking_failures else "failed"
    freeze_gate_readiness = _freeze_gate_readiness(checks[0])

    previous = _previous_reports()
    prior_statuses = [str(row.get("overall_status") or "").strip() for row in previous]
    historical_pass_streak = _pass_streak([*prior_statuses, overall_status])
    readiness_status = (
        "companion_autonomy_ready"
        if overall_status == "passed" and freeze_gate_readiness == "freeze_gate_ready" and historical_pass_streak >= 3
        else "companion_autonomy_in_progress"
    )

    report = {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": overall_status,
        "readiness_status": readiness_status,
        "freeze_gate_readiness": freeze_gate_readiness,
        "summary": {
            "total": len(checks),
            "passed": passed,
            "failed": failed,
            "historical_pass_streak": historical_pass_streak,
        },
        "checks": checks,
    }
    json_path = REPORT_DIR / f"companion-autonomy-audit-{run_id}.json"
    md_path = REPORT_DIR / f"companion-autonomy-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[companion-autonomy] json={json_path}")
    print(f"[companion-autonomy] md={md_path}")
    print(f"[companion-autonomy] overall_status={overall_status}")
    print(f"[companion-autonomy] readiness={readiness_status}")


if __name__ == "__main__":
    main()
