from __future__ import annotations

import argparse
import json
import os
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
    return {"command": subprocess.list2cmdline(command), "status": "passed" if completed.returncode == 0 else "failed", "returncode": completed.returncode}


def evaluate_checks(checks: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [row["command"] for row in checks if row["status"] != "passed"]
    overall = "failed" if failed else "passed"
    return {"overall_status": overall, "readiness_status": "capability_growth_phase5_ready" if overall == "passed" else "capability_growth_phase5_in_progress", "failure_reasons": failed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    checks = [_run([sys.executable, "-m", "pytest", "tests/test_capability_growth_phase5.py", "-q"]), _run([sys.executable, "evals/run_capability_growth_phase5_smokes.py", "--run-tag", run_id])]
    report = {"run_id": run_id, "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "checks": checks, **evaluate_checks(checks)}
    path = REPORT_DIR / f"capability-growth-phase5-audit-{run_id}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[capability-growth-phase5] json={path}")
    print(f"[capability-growth-phase5] overall_status={report['overall_status']}")
    print(f"[capability-growth-phase5] readiness={report['readiness_status']}")
    return 0 if report["overall_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
