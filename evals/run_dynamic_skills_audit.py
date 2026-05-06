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
    return {"command": subprocess.list2cmdline(command), "returncode": completed.returncode, "status": "passed" if completed.returncode == 0 else "failed", "stdout": completed.stdout[-1000:], "stderr": completed.stderr[-1000:]}


def evaluate_checks(checks: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [row["command"] for row in checks if row["status"] != "passed"]
    overall = "failed" if failed else "passed"
    return {"overall_status": overall, "readiness_status": "dynamic_skills_phase1_ready" if overall == "passed" else "dynamic_skills_phase1_in_progress", "failure_reasons": failed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    checks = [
        _run([sys.executable, "-m", "pytest", "tests/test_dynamic_skill_candidates.py", "-q"]),
        _run([sys.executable, "evals/run_dynamic_skills_smokes.py", "--run-tag", run_id]),
    ]
    report = {"run_id": run_id, "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "checks": checks, **evaluate_checks(checks)}
    path = REPORT_DIR / f"dynamic-skills-audit-{run_id}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[dynamic-skills] json={path}")
    print(f"[dynamic-skills] overall_status={report['overall_status']}")
    print(f"[dynamic-skills] readiness={report['readiness_status']}")
    return 0 if report["overall_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
