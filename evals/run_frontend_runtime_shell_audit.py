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


def _run(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", env={**os.environ, "PYTHONUTF8": "1"})
    return {
        "command": subprocess.list2cmdline(command),
        "returncode": completed.returncode,
        "status": "passed" if completed.returncode == 0 else "failed",
        "stdout_tail": completed.stdout[-1600:],
        "stderr_tail": completed.stderr[-1600:],
    }


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


def evaluate_checks(checks: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [row["command"] for row in checks if row.get("status") != "passed"]
    overall = "failed" if failed else "passed"
    return {
        "overall_status": overall,
        "readiness_status": "frontend_runtime_shell_phase1_ready" if overall == "passed" else "frontend_runtime_shell_phase1_in_progress",
        "failure_reasons": failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    checks = [
        _run([sys.executable, "-m", "pytest", "tests/test_frontend_contract_sync.py", "tests/test_backend_api.py", "tests/test_backend_session.py", "-q"]),
        _run([*_npm_command(), "--prefix", "frontend", "run", "build"]),
    ]
    report = {"run_id": run_id, "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "checks": checks, **evaluate_checks(checks)}
    path = REPORT_DIR / f"frontend-runtime-shell-audit-{run_id}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[frontend-runtime-shell] json={path}")
    print(f"[frontend-runtime-shell] overall_status={report['overall_status']}")
    print(f"[frontend-runtime-shell] readiness={report['readiness_status']}")
    return 0 if report["overall_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
