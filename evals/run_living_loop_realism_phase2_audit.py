from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

from amadeus_thread0.runtime.living_loop_realism import build_backend_payload_realism_readback
from evals.run_living_loop_realism_audit import build_deterministic_turn_fixture


def build_backend_payload_fixture() -> dict[str, Any]:
    turn = build_deterministic_turn_fixture()
    return {
        **turn,
        "emotion_label": "hurt",
        "session_context": {"thread_id": "thread-a", "turn_started_at": 1_777_777_001},
        "turn_summary": {
            "current_turn": {
                "recon_event_kind": "user_utterance",
                "recon_interaction_frame": "relationship",
                "counterpart_stance": "watchful",
                "counterpart_scene": "repair_attempt",
                "behavior_consequence_kind": "relationship_repair_acknowledged",
                "digital_body_consequence_kind": "relationship_repair_acknowledged",
            },
            "relationship": {"stage": "repairing"},
            "interaction_carryover": {"carryover_mode": "low_pressure_repair"},
            "digital_body_consequence": {"kind": "relationship_repair_acknowledged"},
        },
        "autonomy": {"intent": {"mode": "assist", "origin": "motive_goal"}, "action_packets": []},
        "skills": {"active_skill_ids": [], "matched_skill_ids": []},
        "digital_body": {
            "active_surface": "dialogue",
            "access_state": {"mode": "dialogue_only"},
            "resource_state": {"artifact_continuity": "none"},
        },
        "procedural_growth": {"procedural_growth": False},
        "procedural_outcome": {"procedural_outcome": False},
        "procedural_recovery": {"procedural_recovery": False},
        "operator_readback": {
            "schema": "operator_readback.v2",
            "readiness_status": "runtime_productization_phase2_ready",
        },
    }


def build_report(*, run_id: str) -> dict[str, Any]:
    payload = build_backend_payload_fixture()
    readback = build_backend_payload_realism_readback(payload)
    failure_reasons = list(readback.get("failure_reasons") or [])
    overall_status = "passed" if not failure_reasons else "failed"
    return {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": overall_status,
        "readiness_status": (
            "living_loop_runtime_realism_phase2_ready"
            if overall_status == "passed"
            else "living_loop_runtime_realism_phase2_in_progress"
        ),
        "failure_reasons": failure_reasons,
        "readback": readback,
        "backend_payload_keys": sorted(payload.keys()),
    }


def render_markdown(report: dict[str, Any]) -> str:
    readback = report.get("readback") if isinstance(report.get("readback"), dict) else {}
    backend_payload = (
        readback.get("backend_payload")
        if isinstance(readback.get("backend_payload"), dict)
        else {}
    )
    causality = readback.get("causality") if isinstance(readback.get("causality"), dict) else {}
    links = causality.get("links") if isinstance(causality.get("links"), dict) else {}
    lines = [
        "# Living Loop Runtime Realism Phase 2 Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Backend Payload",
        "",
        "| Surface | Status |",
        "| --- | --- |",
        f"| `backend_payload` | `{backend_payload.get('status', 'unknown')}` |",
        "",
        "## Causality Links",
        "",
        "| Link | Status |",
        "| --- | --- |",
    ]
    for key, row in links.items():
        if not isinstance(row, dict):
            continue
        lines.append(f"| `{key}` | `{row.get('status', '')}` |")
    lines.extend(["", "## Failure Reasons", ""])
    reasons = list(report.get("failure_reasons") or [])
    if reasons:
        lines.extend(f"- `{reason}`" for reason in reasons)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run living loop runtime realism phase 2 audit.")
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    report = build_report(run_id=run_id)
    json_path = REPORT_DIR / f"living-loop-realism-phase2-audit-{run_id}.json"
    md_path = REPORT_DIR / f"living-loop-realism-phase2-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[living-loop-realism-phase2] json={json_path}")
    print(f"[living-loop-realism-phase2] md={md_path}")
    print(f"[living-loop-realism-phase2] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[living-loop-realism-phase2] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
