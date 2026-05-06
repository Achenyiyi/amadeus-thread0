from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from amadeus_thread0.graph_parts.capability_growth import derive_workflow_candidate, workflow_candidate_to_planning_bias

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def run_smokes():
    workspace = derive_workflow_candidate([{"trace_id": "w1", "status": "completed", "capability_family": "workspace", "confidence": 0.82}, {"trace_id": "w2", "status": "completed", "capability_family": "workspace", "confidence": 0.84}])
    sandbox = derive_workflow_candidate([{"trace_id": "s1", "status": "completed", "capability_family": "sandbox", "confidence": 0.82}, {"trace_id": "s2", "status": "completed", "capability_family": "sandbox", "confidence": 0.84}])
    browser = derive_workflow_candidate([{"trace_id": "b1", "status": "completed", "capability_family": "browser", "confidence": 0.82}, {"trace_id": "b2", "status": "completed", "capability_family": "browser", "confidence": 0.84}])
    blocked = derive_workflow_candidate([{"trace_id": "x", "status": "blocked", "capability_family": "sandbox", "confidence": 0.9}])
    skill = derive_workflow_candidate([{"trace_id": "k1", "status": "completed", "capability_family": "skill", "confidence": 0.86}, {"trace_id": "k2", "status": "completed", "capability_family": "skill", "confidence": 0.88}])
    sandbox_bias = workflow_candidate_to_planning_bias(sandbox, {"access_state": {"sandbox_state": {"runner_kind": "docker_isolated_runner"}}})
    return [
        {"id": "workspace_reuse_candidate", "status": "passed" if workspace["status"] == "candidate" else "failed"},
        {"id": "sandbox_candidate_preserves_approval", "status": "passed" if sandbox_bias.get("requires_approval") else "failed"},
        {"id": "browser_candidate_preserves_manual_takeover", "status": "passed" if browser["recommended_next_action"] == "ask_operator" else "failed"},
        {"id": "blocked_trace_boundary_only", "status": "passed" if blocked["status"] == "blocked" else "failed"},
        {"id": "dynamic_skill_candidate_path_is_proposal_only", "status": "passed" if skill["recommended_next_action"] == "propose_skill" and skill["capability_claim"] is False else "failed"},
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    rows = run_smokes()
    overall = "failed" if any(row["status"] != "passed" for row in rows) else "passed"
    path = REPORT_DIR / f"capability-growth-phase5-smokes-{run_id}.json"
    path.write_text(json.dumps({"run_id": run_id, "overall_status": overall, "scenarios": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[capability-growth-phase5-smokes] json={path}")
    print(f"[capability-growth-phase5-smokes] overall_status={overall}")
    return 0 if overall == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
