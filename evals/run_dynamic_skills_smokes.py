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

from amadeus_thread0.runtime.dynamic_skill_candidates import build_skill_candidate_approval, propose_skill_candidate_from_trace, verify_candidate_hash

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def run_smokes():
    candidate = propose_skill_candidate_from_trace({"trace_id": "proc-1", "status": "completed", "summary": "pytest rg workflow"})
    pending = propose_skill_candidate_from_trace({"trace_id": "proc-2", "status": "pending_approval"})
    approval = build_skill_candidate_approval(candidate)
    return [
        {"id": "completed_trace_proposes_candidate", "status": "passed" if candidate["status"] == "proposed" else "failed"},
        {"id": "candidate_hash_is_stable", "status": "passed" if verify_candidate_hash(candidate)["verified"] else "failed"},
        {"id": "approval_payload_contains_candidate_id_and_hash", "status": "passed" if approval.get("candidate_id") and approval.get("hash") else "failed"},
        {"id": "pending_trace_does_not_propose_candidate", "status": "passed" if pending["status"] == "blocked" else "failed"},
        {"id": "candidate_does_not_enter_autobiographical_memory", "status": "passed" if candidate["registry_written"] is False else "failed"},
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    rows = run_smokes()
    overall = "failed" if any(row["status"] != "passed" for row in rows) else "passed"
    report = {"run_id": run_id, "overall_status": overall, "scenarios": rows}
    path = REPORT_DIR / f"dynamic-skills-smokes-{run_id}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[dynamic-skills-smokes] json={path}")
    print(f"[dynamic-skills-smokes] overall_status={overall}")
    return 0 if overall == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
