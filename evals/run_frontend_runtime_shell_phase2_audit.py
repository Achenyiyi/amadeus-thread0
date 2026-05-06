from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

READY = "frontend_runtime_shell_phase2_ready"
IN_PROGRESS = "frontend_runtime_shell_phase2_in_progress"


def _npm_command() -> list[str]:
    for candidate in ("npm.cmd", "npm.exe", "npm"):
        path = shutil.which(candidate)
        if path:
            return [path]
    ps_script = shutil.which("npm.ps1")
    if ps_script:
        powershell = shutil.which("powershell") or shutil.which("pwsh") or "powershell"
        return [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_script]
    return ["npm"]


def _run(name: str, command: list[str]) -> dict[str, Any]:
    env = {**os.environ, "PYTHONUTF8": "1"}
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    return {
        "name": name,
        "command": subprocess.list2cmdline(command),
        "returncode": completed.returncode,
        "status": "passed" if completed.returncode == 0 else "failed",
        "stdout_tail": completed.stdout[-1600:],
        "stderr_tail": completed.stderr[-1600:],
    }


def evaluate_checks(checks: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [str(row.get("name") or row.get("command") or "") for row in checks if row.get("status") != "passed"]
    overall = "failed" if failed else "passed"
    return {
        "overall_status": overall,
        "readiness_status": READY if overall == "passed" else IN_PROGRESS,
        "failure_reasons": failed,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Frontend Runtime Shell Phase 2 Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Command |",
        "| --- | --- | --- |",
    ]
    for row in report.get("checks") or []:
        lines.append(
            f"| `{row.get('name', '')}` | `{row.get('status', '')}` | `{row.get('command', '')}` |"
        )
    reasons = [str(reason) for reason in report.get("failure_reasons") or [] if str(reason)]
    lines.extend(["", "## Failure Reasons", ""])
    if reasons:
        lines.extend(f"- `{reason}`" for reason in reasons)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def build_report(*, run_id: str) -> dict[str, Any]:
    checks = [
        _run(
            "phase2_contract_and_sync",
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_frontend_runtime_shell_phase2.py",
                "tests/test_frontend_contract_sync.py",
                "-q",
            ],
        ),
        _run("frontend_build", [*_npm_command(), "--prefix", "frontend", "run", "build"]),
    ]
    return {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "checks": checks,
        **evaluate_checks(checks),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run frontend runtime shell Phase 2 audit.")
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (
        str(args.run_tag).strip() or str(uuid.uuid4())[:8]
    )
    report = build_report(run_id=run_id)
    json_path = REPORT_DIR / f"frontend-runtime-shell-phase2-audit-{run_id}.json"
    md_path = REPORT_DIR / f"frontend-runtime-shell-phase2-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[frontend-runtime-shell-phase2] json={json_path}")
    print(f"[frontend-runtime-shell-phase2] md={md_path}")
    print(f"[frontend-runtime-shell-phase2] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[frontend-runtime-shell-phase2] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

