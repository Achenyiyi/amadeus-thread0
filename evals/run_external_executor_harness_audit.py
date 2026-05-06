from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from amadeus_thread0.runtime.executor_harness_registry import build_executor_harness_registry, normalize_external_harness_result

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def evaluate_harness_registry(registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    failures: list[str] = []
    enabled = [key for key, row in registry.items() if row.get("runtime_enabled")]
    if enabled != ["sandbox_runner"]:
        failures.append("sandbox_runner_not_only_enabled")
    for kind in ("deep_agents", "codex_harness", "claude_harness", "openclaw_harness"):
        row = registry.get(kind) or {}
        if row.get("runtime_enabled") is not False:
            failures.append(f"{kind}_runtime_enabled")
        if row.get("writeback_policy") != "result_only":
            failures.append(f"{kind}_not_result_only")
    sample = normalize_external_harness_result({"harness_kind": "codex_harness", "status": "completed", "memory_writes": [{"x": 1}]})
    if sample.get("persona_memory_ownership") is not False or sample.get("writeback_policy") != "result_only":
        failures.append("external_harness_result_not_result_only")
    overall = "failed" if failures else "passed"
    return {
        "overall_status": overall,
        "readiness_status": "external_executor_harness_phase1_ready" if overall == "passed" else "external_executor_harness_phase1_in_progress",
        "failure_reasons": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    report = {"run_id": run_id, "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), **evaluate_harness_registry(build_executor_harness_registry())}
    path = REPORT_DIR / f"external-executor-harness-audit-{run_id}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[external-executor-harness] json={path}")
    print(f"[external-executor-harness] overall_status={report['overall_status']}")
    print(f"[external-executor-harness] readiness={report['readiness_status']}")
    return 0 if report["overall_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
