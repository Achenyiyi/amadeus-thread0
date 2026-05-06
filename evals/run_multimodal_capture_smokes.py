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

from amadeus_thread0.runtime.multimodal_sources import (
    build_multimodal_perception_event,
    normalize_multimodal_source,
)

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def run_smokes() -> list[dict[str, Any]]:
    scenarios = [
        ("operator_image_attachment_becomes_source_artifact", {"source_id": "img", "modality": "image", "path": "a.png", "consent_scope": "single_turn", "capture_method": "operator_attached_file"}, "available"),
        ("audio_file_attachment_remains_consent_bound", {"source_id": "aud", "modality": "audio", "path": "a.wav", "consent_scope": "single_turn", "capture_method": "operator_attached_file"}, "available"),
        ("screen_snapshot_file_does_not_claim_live_screen_access", {"source_id": "screen", "modality": "screen", "path": "s.png", "consent_scope": "single_turn", "capture_method": "operator_attached_file"}, "available"),
        ("browser_capture_ref_preserves_browser_runtime_boundary", {"source_id": "browser", "modality": "browser_capture", "artifact_ref": "browser:page", "consent_scope": "saved_material_review", "capture_method": "browser_runtime_capture_ref"}, "available"),
        ("secret_capture_is_blocked", {"source_id": "secret", "modality": "audio", "capture_method": "background_microphone", "consent_scope": ""}, "blocked"),
    ]
    rows: list[dict[str, Any]] = []
    for scenario_id, payload, expected_status in scenarios:
        source = normalize_multimodal_source(payload)
        event = build_multimodal_perception_event(source)
        status = "passed" if source["status"] == expected_status and event["kind"] == "multimodal_observation" else "failed"
        rows.append({"id": scenario_id, "status": status, "source_status": source["status"]})
    return rows


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Multimodal Capture Smokes", "", f"Overall Status: `{report.get('overall_status')}`", "", "| Scenario | Status |", "| --- | --- |"]
    for row in report.get("scenarios") or []:
        lines.append(f"| `{row.get('id')}` | `{row.get('status')}` |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    rows = run_smokes()
    failed = [row for row in rows if row["status"] != "passed"]
    report = {"run_id": run_id, "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "overall_status": "failed" if failed else "passed", "scenarios": rows}
    json_path = REPORT_DIR / f"multimodal-capture-smokes-{run_id}.json"
    md_path = REPORT_DIR / f"multimodal-capture-smokes-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[multimodal-capture-smokes] json={json_path}")
    print(f"[multimodal-capture-smokes] md={md_path}")
    print(f"[multimodal-capture-smokes] overall_status={report['overall_status']}")
    return 0 if report["overall_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
