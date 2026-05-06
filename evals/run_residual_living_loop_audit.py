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

from amadeus_thread0.runtime.residual_living_loop import build_residual_living_loop_readback


def build_deterministic_turn_fixture() -> dict[str, Any]:
    return {
        "final_text": "嗯。我听见了，但这不等于我会把边界也一并抹掉。",
        "current_event": {
            "kind": "multimodal_observation",
            "perception": {
                "channel": "image",
                "modality": "image",
                "source_role": "operator",
                "trust_tier": "medium",
                "digital_body_hints": {
                    "artifact_carrier": "multimodal_source",
                    "active_artifact_kind": "image",
                    "active_artifact_ref": "fixtures/panel.png",
                    "multimodal_source": {
                        "source_id": "image-1",
                        "status": "available",
                        "modality": "image",
                    },
                },
            },
            "digital_body_hints": {
                "artifact_carrier": "multimodal_source",
                "active_artifact_kind": "image",
                "active_artifact_ref": "fixtures/panel.png",
            },
        },
        "turn_appraisal": {
            "scene": "repair",
            "confidence": 0.84,
            "counterpart_signal": "returns_with_repair_attempt",
        },
        "emotion_state": {"label": "guarded", "valence": -0.08, "arousal": 0.22},
        "bond_state": {"trust": 0.58, "closeness": 0.52, "repair_confidence": 0.63},
        "allostasis_state": {"autonomy_need": 0.62, "safety_need": 0.36, "cognitive_budget": 0.71},
        "behavior_action": {
            "primary_motive": "repair_without_erasing_boundary",
            "interaction_mode": "low_pressure_support",
        },
        "behavior_plan": {
            "action_family": "low_pressure_support",
            "primary_motive": "repair_without_erasing_boundary",
        },
        "digital_body_consequence": {
            "kind": "source_material_inspected",
            "artifact_carrier": "multimodal_source",
        },
        "reconsolidation_snapshot": {
            "behavior_action": {"primary_motive": "repair_without_erasing_boundary"},
            "behavior_plan": {"action_family": "low_pressure_support"},
            "digital_body_consequence": {"kind": "source_material_inspected"},
        },
        "writeback_trace": {
            "revision_traces": [
                {
                    "namespace": "semantic_self_evidence",
                    "target_id": "repair_style",
                    "content": {"primary_motive": "repair_without_erasing_boundary"},
                }
            ],
            "counterpart_assessment_history": [{"stance": "watchful", "repairability": 0.64}],
            "proactive_continuity_history": [{"continuity_kind": "low_pressure_repair"}],
        },
        "semantic_narrative_profile": {
            "continuity_axes": [{"category": "repair_style", "score": 0.74}],
            "semantic_continuity_depth": 0.66,
        },
        "skills": {"active": [], "pending_approval": None},
        "autonomy": {"action_packets": []},
    }


def build_report(*, run_id: str) -> dict[str, Any]:
    readback = build_residual_living_loop_readback(current_turn=build_deterministic_turn_fixture())
    return {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": readback["overall_status"],
        "readiness_status": readback["readiness_status"],
        "failure_reasons": list(readback.get("failure_reasons") or []),
        "readback": readback,
    }


def render_markdown(report: dict[str, Any]) -> str:
    readback = report.get("readback") if isinstance(report.get("readback"), dict) else {}
    residuals = readback.get("residuals") if isinstance(readback.get("residuals"), dict) else {}
    lines = [
        "# Residual Living Loop Closure Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "| Residual | Status | Runtime Available |",
        "| --- | --- | ---: |",
    ]
    for key, row in residuals.items():
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| `{key}` | `{row.get('status', '')}` | `{str(bool(row.get('runtime_available', False))).lower()}` |"
        )
    reasons = list(report.get("failure_reasons") or [])
    lines.extend(["", "## Failure Reasons", ""])
    if reasons:
        lines.extend(f"- `{reason}`" for reason in reasons)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run residual living loop closure audit.")
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    report = build_report(run_id=run_id)
    json_path = REPORT_DIR / f"residual-living-loop-audit-{run_id}.json"
    md_path = REPORT_DIR / f"residual-living-loop-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[residual-living-loop] json={json_path}")
    print(f"[residual-living-loop] md={md_path}")
    print(f"[residual-living-loop] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[residual-living-loop] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
