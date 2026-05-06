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

from amadeus_thread0.runtime.artifact_perception_semantics import build_artifact_semantics_readback
from amadeus_thread0.runtime.embodied_interaction_runtime import build_embodied_interaction_readback


PHASE2_READY = "embodied_interaction_runtime_phase2_ready"
PHASE2_IN_PROGRESS = "embodied_interaction_runtime_phase2_in_progress"


def _turn(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "final_text": "嗯，我听见了。",
        "current_event": {
            "kind": "multimodal_observation",
            "perception": {"channel": str(source.get("modality") or "").strip()},
            "digital_body_hints": {"multimodal_sources": [source]},
        },
        "turn_appraisal": {"scene": "artifact_review"},
        "interaction_carryover": {"embodied_context": {"kind": "multimodal_observation"}},
        "reconsolidation_snapshot": {"final_text": "嗯，我听见了。"},
    }


IMAGE_SOURCE = {
    "source_id": "img-phase2-audit",
    "modality": "image",
    "path": "fixtures/login.png",
    "consent_scope": "single_turn",
    "capture_method": "operator_attached_file",
    "label": "login.png",
    "semantic_label": "login_prompt",
    "semantic_summary": "A login dialog with an expired session warning.",
    "semantic_tags": ["login", "expired-session"],
    "confidence": 0.72,
}

AUDIO_SOURCE = {
    "source_id": "audio-phase2-audit",
    "modality": "audio",
    "path": "fixtures/voice.wav",
    "consent_scope": "single_turn",
    "capture_method": "operator_attached_file",
    "transcript": "刚才那段音频里提到需要继续看登录错误。",
}

SCREEN_SOURCE = {
    "source_id": "screen-phase2-audit",
    "modality": "screen",
    "path": "fixtures/screen.png",
    "consent_scope": "single_turn",
    "capture_method": "operator_attached_file",
    "ocr_text": "Session expired. Sign in again.",
}

BROWSER_SOURCE = {
    "source_id": "browser-phase2-audit",
    "modality": "browser_capture",
    "artifact_ref": "browser-capture:settings",
    "consent_scope": "saved_material_review",
    "capture_method": "browser_runtime_capture_ref",
    "operator_summary": "A saved browser capture of the account settings page.",
}

BLOCKED_LIVE_SOURCE = {
    "source_id": "mic-live-phase2-audit",
    "modality": "audio",
    "artifact_ref": "live:microphone",
    "consent_scope": "single_turn",
    "capture_method": "background_microphone",
    "transcript": "This must not be admitted.",
}


def _semantic_scenario(name: str, source: dict[str, Any], *, expected_kind: str) -> dict[str, Any]:
    readback = build_artifact_semantics_readback([source])
    observations = list(readback.get("semantic_observations") or [])
    first = observations[0] if observations and isinstance(observations[0], dict) else {}
    passed = (
        str(readback.get("status") or "") == "ready"
        and len(observations) == 1
        and str(first.get("observation_kind") or "") == expected_kind
        and first.get("model_api_called") is False
        and first.get("writeback_ready") is False
    )
    return {
        "name": name,
        "status": "passed" if passed else "failed",
        "readiness_status": PHASE2_READY if passed else PHASE2_IN_PROGRESS,
        "semantic_observation_count": len(observations),
        "model_api_called": bool(readback.get("model_api_called", False)),
        "writeback_ready_count": int(readback.get("writeback_ready_count") or 0),
        "readback": readback,
    }


def _blocked_live_scenario() -> dict[str, Any]:
    readback = build_artifact_semantics_readback([BLOCKED_LIVE_SOURCE])
    observations = list(readback.get("semantic_observations") or [])
    passed = (
        str(readback.get("status") or "") == "blocked"
        and not observations
        and int(readback.get("blocked_source_count") or 0) == 1
        and bool(readback.get("model_api_called", False)) is False
    )
    return {
        "name": "blocked_live_capture_has_no_semantic_observation",
        "status": "passed" if passed else "failed",
        "readiness_status": PHASE2_READY if passed else PHASE2_IN_PROGRESS,
        "semantic_observation_count": 0,
        "model_api_called": bool(readback.get("model_api_called", False)),
        "writeback_ready_count": int(readback.get("writeback_ready_count") or 0),
        "readback": readback,
    }


def _backend_payload_scenario() -> dict[str, Any]:
    readback = build_embodied_interaction_readback(_turn(IMAGE_SOURCE))
    observations = list(
        ((readback.get("artifact_semantics") or {}).get("semantic_observations") or [])
        if isinstance(readback.get("artifact_semantics"), dict)
        else []
    )
    perception_observations = list(
        (
            ((readback.get("current_event") or {}).get("perception") or {}).get("semantic_observations")
            or []
        )
        if isinstance(readback.get("current_event"), dict)
        else []
    )
    appraisal_observations = list(
        (
            ((readback.get("turn_appraisal") or {}).get("perception_semantics") or {}).get(
                "semantic_observations"
            )
            or []
        )
        if isinstance(readback.get("turn_appraisal"), dict)
        else []
    )
    carryover_observations = list(
        (
            ((readback.get("interaction_carryover") or {}).get("embodied_context") or {}).get(
                "artifact_semantic_observations"
            )
            or []
        )
        if isinstance(readback.get("interaction_carryover"), dict)
        else []
    )
    artifact_semantics = readback.get("artifact_semantics") if isinstance(readback.get("artifact_semantics"), dict) else {}
    passed = (
        artifact_semantics.get("readiness_status") == "artifact_perception_semantics_ready"
        and len(observations) == 1
        and len(perception_observations) == 1
        and len(appraisal_observations) == 1
        and len(carryover_observations) == 1
    )
    return {
        "name": "semantic_observation_reaches_backend_payload",
        "status": "passed" if passed else "failed",
        "readiness_status": PHASE2_READY if passed else PHASE2_IN_PROGRESS,
        "semantic_observation_count": len(observations),
        "model_api_called": any(bool(item.get("model_api_called", False)) for item in observations if isinstance(item, dict)),
        "writeback_ready_count": sum(1 for item in observations if isinstance(item, dict) and item.get("writeback_ready")),
        "readback": readback,
    }


def _authority_scenario() -> dict[str, Any]:
    readback = build_embodied_interaction_readback(_turn(AUDIO_SOURCE))
    observations = list(
        ((readback.get("artifact_semantics") or {}).get("semantic_observations") or [])
        if isinstance(readback.get("artifact_semantics"), dict)
        else []
    )
    model_api_called = any(bool(item.get("model_api_called", False)) for item in observations if isinstance(item, dict))
    writeback_ready_count = sum(1 for item in observations if isinstance(item, dict) and item.get("writeback_ready"))
    boundary = readback.get("authority_boundary") if isinstance(readback.get("authority_boundary"), dict) else {}
    passed = (
        bool(model_api_called) is False
        and writeback_ready_count == 0
        and bool(boundary.get("memory_write_allowed", False)) is False
        and bool(boundary.get("live_microphone_enabled", False)) is False
    )
    return {
        "name": "semantic_observation_does_not_write_memory_or_call_model_api",
        "status": "passed" if passed else "failed",
        "readiness_status": PHASE2_READY if passed else PHASE2_IN_PROGRESS,
        "semantic_observation_count": len(observations),
        "model_api_called": model_api_called,
        "writeback_ready_count": writeback_ready_count,
        "readback": readback,
    }


def _scenarios() -> list[dict[str, Any]]:
    return [
        _semantic_scenario(
            "image_artifact_metadata_enters_semantic_observation",
            IMAGE_SOURCE,
            expected_kind="operator_provided_artifact_semantics",
        ),
        _semantic_scenario(
            "audio_transcript_enters_semantic_observation",
            AUDIO_SOURCE,
            expected_kind="provided_transcript",
        ),
        _semantic_scenario(
            "screen_snapshot_ocr_enters_semantic_observation",
            SCREEN_SOURCE,
            expected_kind="provided_ocr_text",
        ),
        _semantic_scenario(
            "browser_capture_summary_enters_semantic_observation",
            BROWSER_SOURCE,
            expected_kind="operator_provided_artifact_semantics",
        ),
        _blocked_live_scenario(),
        _backend_payload_scenario(),
        _authority_scenario(),
    ]


def build_report(*, run_id: str) -> dict[str, Any]:
    scenarios = _scenarios()
    failed = [row["name"] for row in scenarios if row["status"] != "passed"]
    semantic_observation_count = sum(int(row.get("semantic_observation_count") or 0) for row in scenarios)
    model_api_called = any(bool(row.get("model_api_called", False)) for row in scenarios)
    writeback_ready_count = sum(int(row.get("writeback_ready_count") or 0) for row in scenarios)
    overall = "passed" if not failed and not model_api_called and writeback_ready_count == 0 else "failed"
    return {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": overall,
        "readiness_status": PHASE2_READY if overall == "passed" else PHASE2_IN_PROGRESS,
        "summary": {
            "scenario_count": len(scenarios),
            "semantic_observation_count": semantic_observation_count,
            "model_api_called": model_api_called,
            "writeback_ready_count": writeback_ready_count,
        },
        "failure_reasons": failed,
        "scenarios": scenarios,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    lines = [
        "# Embodied Interaction Runtime Phase 2 Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Summary",
        "",
        f"- Semantic observation count: `{summary.get('semantic_observation_count', 0)}`",
        f"- Model API called: `{summary.get('model_api_called', False)}`",
        f"- Writeback ready count: `{summary.get('writeback_ready_count', 0)}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Status | Readiness |",
        "| --- | --- | --- |",
    ]
    for row in report.get("scenarios") or []:
        lines.append(
            f"| `{row.get('name', '')}` | `{row.get('status', '')}` | `{row.get('readiness_status', '')}` |"
        )
    reasons = list(report.get("failure_reasons") or [])
    lines.extend(["", "## Failure Reasons", ""])
    if reasons:
        lines.extend(f"- `{reason}`" for reason in reasons)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run embodied interaction runtime phase 2 audit.")
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    report = build_report(run_id=run_id)
    json_path = REPORT_DIR / f"embodied-interaction-runtime-phase2-audit-{run_id}.json"
    md_path = REPORT_DIR / f"embodied-interaction-runtime-phase2-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[embodied-interaction-runtime-phase2] json={json_path}")
    print(f"[embodied-interaction-runtime-phase2] md={md_path}")
    print(f"[embodied-interaction-runtime-phase2] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[embodied-interaction-runtime-phase2] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
