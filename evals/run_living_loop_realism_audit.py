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

from amadeus_thread0.graph_parts.chinese_semantic_surface import rewrite_semantic_surface_floor
from amadeus_thread0.runtime.living_loop_realism import build_living_loop_realism_readback


def build_deterministic_turn_fixture() -> dict[str, Any]:
    return {
        "final_text": "嗯。我听见了。边界还在，但这次我会先把话放轻一点。",
        "current_event": {
            "kind": "user_utterance",
            "text": "之前那件事我一直记着，我们能慢慢聊吗？",
            "tags": ["repair", "relationship"],
        },
        "turn_appraisal": {
            "scene": "repair_attempt",
            "interaction_frame": "relationship",
            "signals": {"repair": True, "care": True},
            "confidence": 0.86,
        },
        "emotion_state": {"label": "hurt", "valence": -0.08, "arousal": 0.22},
        "bond_state": {"trust": 0.60, "closeness": 0.58, "hurt": 0.14, "repair_confidence": 0.66},
        "allostasis_state": {"autonomy_need": 0.38, "safety_need": 0.42, "cognitive_budget": 0.70},
        "counterpart_assessment": {
            "stance": "watchful",
            "scene": "repair_attempt",
            "boundary_pressure": 0.18,
            "reliability_read": 0.62,
        },
        "semantic_narrative_profile": {
            "repair_residue": 0.76,
            "continuity_depth": 0.68,
            "commitment_carry": 0.62,
            "continuity_axes": [{"category": "repair_style", "score": 0.74}],
        },
        "behavior_action": {
            "interaction_mode": "low_pressure_support",
            "action_target": "low_pressure_hold",
            "primary_motive": "support_without_pressure",
            "motive_tension": "boundary_vs_closeness",
            "goal_frame": "先低负担接住，不接管对方节奏。",
        },
        "behavior_plan": {
            "kind": "low_pressure_support",
            "interaction_mode": "low_pressure_support",
            "primary_motive": "support_without_pressure",
            "goal_frame": "先低负担接住，不接管对方节奏。",
        },
        "digital_body_consequence": {"kind": "relationship_repair_acknowledged"},
        "reconsolidation_snapshot": {
            "behavior_action": {"primary_motive": "support_without_pressure"},
            "behavior_plan": {"kind": "low_pressure_support", "primary_motive": "support_without_pressure"},
            "digital_body_consequence": {"kind": "relationship_repair_acknowledged"},
            "final_text": "嗯。我听见了。边界还在，但这次我会先把话放轻一点。",
        },
        "writeback_trace": {
            "revision_traces": [{"namespace": "semantic_self_evidence", "target_id": "repair_style"}],
            "counterpart_assessment_history": [{"stance": "watchful", "scene": "repair_attempt"}],
        },
    }


def build_report(*, run_id: str) -> dict[str, Any]:
    readback = build_living_loop_realism_readback(current_turn=build_deterministic_turn_fixture())
    chinese_replacement = rewrite_semantic_surface_floor(
        "你能意识到并特意回来说明，这点还算值得肯定。"
    )
    failure_reasons = list(readback.get("failure_reasons") or [])
    if str(chinese_replacement.get("status") or "") != "floor_rewritten":
        failure_reasons.append("chinese_semantic_replacement")
    overall_status = "passed" if not failure_reasons else "failed"
    return {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": overall_status,
        "readiness_status": (
            "living_loop_runtime_realism_phase1_ready"
            if overall_status == "passed"
            else "living_loop_runtime_realism_phase1_in_progress"
        ),
        "failure_reasons": failure_reasons,
        "readback": readback,
        "chinese_semantic_replacement": chinese_replacement,
    }


def render_markdown(report: dict[str, Any]) -> str:
    readback = report.get("readback") if isinstance(report.get("readback"), dict) else {}
    causality = readback.get("causality") if isinstance(readback.get("causality"), dict) else {}
    links = causality.get("links") if isinstance(causality.get("links"), dict) else {}
    replacement = (
        report.get("chinese_semantic_replacement")
        if isinstance(report.get("chinese_semantic_replacement"), dict)
        else {}
    )
    lines = [
        "# Living Loop Runtime Realism Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
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
    lines.extend(
        [
            "",
            "## Chinese Semantic Replacement",
            "",
            f"- Status: `{replacement.get('status', 'unknown')}`",
            f"- Families: `{', '.join(str(item) for item in replacement.get('families', []) or [])}`",
            f"- Safe surface floor: `{replacement.get('safe_surface_floor', '')}`",
            "",
            "## Failure Reasons",
            "",
        ]
    )
    reasons = list(report.get("failure_reasons") or [])
    if reasons:
        lines.extend(f"- `{reason}`" for reason in reasons)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run living loop runtime realism audit.")
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    report = build_report(run_id=run_id)
    json_path = REPORT_DIR / f"living-loop-realism-audit-{run_id}.json"
    md_path = REPORT_DIR / f"living-loop-realism-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[living-loop-realism] json={json_path}")
    print(f"[living-loop-realism] md={md_path}")
    print(f"[living-loop-realism] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[living-loop-realism] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
