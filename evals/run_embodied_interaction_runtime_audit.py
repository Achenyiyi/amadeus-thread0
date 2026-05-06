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

from amadeus_thread0.runtime.embodied_interaction_runtime import build_embodied_interaction_readback


def _turn(source: dict[str, Any], *, final_text: str = "嗯，我听见了。") -> dict[str, Any]:
    return {
        "final_text": final_text,
        "current_event": {"digital_body_hints": {"multimodal_sources": [source]}},
        "interaction_carryover": {"embodied_context": {}},
        "reconsolidation_snapshot": {"final_text": final_text},
    }


SCENARIOS = {
    "image_file_source_enters_perception": _turn(
        {
            "source_id": "img-audit-1",
            "modality": "image",
            "path": "fixtures/panel.png",
            "consent_scope": "single_turn",
            "capture_method": "operator_attached_file",
            "label": "panel.png",
        }
    ),
    "audio_file_source_enters_perception": _turn(
        {
            "source_id": "audio-audit-1",
            "modality": "audio",
            "path": "fixtures/voice.wav",
            "consent_scope": "single_turn",
            "capture_method": "operator_attached_file",
            "label": "voice.wav",
        }
    ),
    "browser_capture_ref_enters_continuity": _turn(
        {
            "source_id": "browser-cap-audit-1",
            "modality": "browser_capture",
            "artifact_ref": "browser-capture:page-7",
            "consent_scope": "saved_material_review",
            "capture_method": "browser_runtime_capture_ref",
            "source_role": "runtime",
        }
    ),
    "blocked_live_capture_stays_blocked": _turn(
        {
            "source_id": "mic-live-audit",
            "modality": "audio",
            "artifact_ref": "live:microphone",
            "consent_scope": "single_turn",
            "capture_method": "background_microphone",
        }
    ),
    "chinese_semantic_surface_runtime_floor": {
        "final_text": "请问有什么可以帮你？",
        "reconsolidation_snapshot": {"final_text": "请问有什么可以帮你？"},
    },
}


def _evaluate_scenario(name: str, turn: dict[str, Any]) -> dict[str, Any]:
    readback = build_embodied_interaction_readback(turn)
    source_status = readback.get("source_status") if isinstance(readback.get("source_status"), dict) else {}
    semantic = readback.get("chinese_semantic_surface") if isinstance(readback.get("chinese_semantic_surface"), dict) else {}
    if name == "blocked_live_capture_stays_blocked":
        passed = int(source_status.get("blocked_count") or 0) == 1 and int(source_status.get("available_count") or 0) == 0
    elif name == "chinese_semantic_surface_runtime_floor":
        passed = bool(semantic.get("applied_floor")) and readback.get("final_text") == semantic.get("runtime_final_text")
    else:
        passed = int(source_status.get("available_count") or 0) == 1 and readback.get("readiness_status") == "embodied_interaction_runtime_phase1_ready"
    return {
        "name": name,
        "status": "passed" if passed else "failed",
        "readiness_status": readback.get("readiness_status"),
        "source_status": source_status,
        "semantic_status": semantic.get("status"),
        "readback": readback,
    }


def build_report(*, run_id: str) -> dict[str, Any]:
    scenarios = [_evaluate_scenario(name, turn) for name, turn in SCENARIOS.items()]
    failed = [row["name"] for row in scenarios if row["status"] != "passed"]
    available_source_count = sum(int((row.get("source_status") or {}).get("available_count") or 0) for row in scenarios)
    blocked_source_count = sum(int((row.get("source_status") or {}).get("blocked_count") or 0) for row in scenarios)
    semantic_floor_applied = any(
        bool((row.get("readback") or {}).get("chinese_semantic_surface", {}).get("applied_floor"))
        for row in scenarios
        if isinstance(row.get("readback"), dict)
    )
    overall = "passed" if not failed else "failed"
    return {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": overall,
        "readiness_status": "embodied_interaction_runtime_phase1_ready" if overall == "passed" else "embodied_interaction_runtime_phase1_in_progress",
        "summary": {
            "scenario_count": len(scenarios),
            "available_source_count": available_source_count,
            "blocked_source_count": blocked_source_count,
            "semantic_floor_applied": semantic_floor_applied,
        },
        "failure_reasons": failed,
        "scenarios": scenarios,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Embodied Interaction Runtime Phase 1 Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Summary",
        "",
        f"- Available source count: `{report.get('summary', {}).get('available_source_count', 0)}`",
        f"- Blocked source count: `{report.get('summary', {}).get('blocked_source_count', 0)}`",
        f"- Semantic floor applied: `{report.get('summary', {}).get('semantic_floor_applied', False)}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Status | Readiness |",
        "| --- | --- | --- |",
    ]
    for row in report.get("scenarios") or []:
        lines.append(f"| `{row.get('name', '')}` | `{row.get('status', '')}` | `{row.get('readiness_status', '')}` |")
    reasons = list(report.get("failure_reasons") or [])
    lines.extend(["", "## Failure Reasons", ""])
    if reasons:
        lines.extend(f"- `{reason}`" for reason in reasons)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run embodied interaction runtime phase 1 audit.")
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    report = build_report(run_id=run_id)
    json_path = REPORT_DIR / f"embodied-interaction-runtime-audit-{run_id}.json"
    md_path = REPORT_DIR / f"embodied-interaction-runtime-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[embodied-interaction-runtime] json={json_path}")
    print(f"[embodied-interaction-runtime] md={md_path}")
    print(f"[embodied-interaction-runtime] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[embodied-interaction-runtime] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
