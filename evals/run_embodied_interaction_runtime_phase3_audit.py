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


PHASE3_READY = "embodied_interaction_runtime_phase3_ready"
PHASE3_IN_PROGRESS = "embodied_interaction_runtime_phase3_in_progress"


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
    "source_id": "img-phase3-audit",
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
    "source_id": "audio-phase3-audit",
    "modality": "audio",
    "path": "fixtures/voice.wav",
    "consent_scope": "single_turn",
    "capture_method": "operator_attached_file",
    "transcript": "刚才那段音频里提到需要继续看登录错误。",
}

SCREEN_SOURCE = {
    "source_id": "screen-phase3-audit",
    "modality": "screen",
    "path": "fixtures/screen.png",
    "consent_scope": "single_turn",
    "capture_method": "operator_attached_file",
    "ocr_text": "Session expired. Sign in again.",
}

BROWSER_SOURCE = {
    "source_id": "browser-phase3-audit",
    "modality": "browser_capture",
    "artifact_ref": "browser-capture:settings",
    "consent_scope": "saved_material_review",
    "capture_method": "browser_runtime_capture_ref",
    "operator_summary": "A saved browser capture of the account settings page.",
}

BLOCKED_LIVE_SOURCE = {
    "source_id": "mic-live-phase3-audit",
    "modality": "audio",
    "artifact_ref": "live:microphone",
    "consent_scope": "single_turn",
    "capture_method": "background_microphone",
    "transcript": "This must not be admitted.",
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _evidence_from_readback(readback: dict[str, Any]) -> list[dict[str, Any]]:
    appraisal = _dict_or_empty(readback.get("artifact_appraisal"))
    return [
        dict(item)
        for item in list(appraisal.get("evidence_items") or [])
        if isinstance(item, dict)
    ]


def _scenario_result(
    *,
    name: str,
    passed: bool,
    evidence_count: int,
    model_api_called: bool = False,
    writeback_ready_count: int = 0,
    access_friction_observed: bool = False,
    should_write_memory: bool = False,
    readback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": "passed" if passed else "failed",
        "readiness_status": PHASE3_READY if passed else PHASE3_IN_PROGRESS,
        "evidence_count": int(evidence_count),
        "model_api_called": bool(model_api_called),
        "writeback_ready_count": int(writeback_ready_count),
        "access_friction_observed": bool(access_friction_observed),
        "should_write_memory": bool(should_write_memory),
        "readback": readback or {},
    }


def _artifact_semantics_scenario() -> dict[str, Any]:
    readback = build_embodied_interaction_readback(_turn(IMAGE_SOURCE))
    evidence = _evidence_from_readback(readback)
    first = _dict_or_empty(evidence[0] if evidence else {})
    passed = (
        readback.get("readiness_status") == PHASE3_READY
        and len(evidence) == 1
        and first.get("source_ref_id") == IMAGE_SOURCE["source_id"]
        and first.get("authority", {}).get("model_api_called") is False
        and first.get("authority", {}).get("writeback_ready") is False
    )
    influence = _dict_or_empty(_dict_or_empty(readback.get("artifact_appraisal")).get("influence_summary"))
    return _scenario_result(
        name="artifact_semantics_becomes_appraisal_evidence",
        passed=passed,
        evidence_count=len(evidence),
        access_friction_observed=bool(influence.get("access_friction_observed", False)),
        should_write_memory=bool(influence.get("should_write_memory", False)),
        readback=readback,
    )


def _access_friction_scenario() -> dict[str, Any]:
    readback = build_embodied_interaction_readback(_turn(IMAGE_SOURCE))
    appraisal = _dict_or_empty(readback.get("artifact_appraisal"))
    evidence = _evidence_from_readback(readback)
    first = _dict_or_empty(evidence[0] if evidence else {})
    delta = _dict_or_empty(first.get("suggested_appraisal_delta"))
    influence = _dict_or_empty(appraisal.get("influence_summary"))
    passed = (
        delta.get("access_friction") is True
        and delta.get("task_relevance") == "high"
        and influence.get("access_friction_observed") is True
        and influence.get("should_request_live_capture") is False
    )
    return _scenario_result(
        name="access_friction_observation_influences_appraisal_readback",
        passed=passed,
        evidence_count=len(evidence),
        access_friction_observed=bool(influence.get("access_friction_observed", False)),
        should_write_memory=bool(influence.get("should_write_memory", False)),
        readback=readback,
    )


def _transcript_and_ocr_scenario() -> dict[str, Any]:
    semantics = build_artifact_semantics_readback([AUDIO_SOURCE, SCREEN_SOURCE, BROWSER_SOURCE])
    readback = build_embodied_interaction_readback(
        {
            "final_text": "嗯，我听见了。",
            "current_event": {
                "kind": "multimodal_observation",
                "digital_body_hints": {
                    "multimodal_sources": [AUDIO_SOURCE, SCREEN_SOURCE, BROWSER_SOURCE]
                },
            },
            "turn_appraisal": {"scene": "artifact_review"},
            "interaction_carryover": {"embodied_context": {"kind": "multimodal_observation"}},
            "reconsolidation_snapshot": {"final_text": "嗯，我听见了。"},
        }
    )
    evidence = _evidence_from_readback(readback)
    influence = _dict_or_empty(_dict_or_empty(readback.get("artifact_appraisal")).get("influence_summary"))
    passed = (
        semantics.get("status") == "ready"
        and len(evidence) == 3
        and influence.get("should_request_live_capture") is False
    )
    return _scenario_result(
        name="transcript_and_ocr_observations_create_appraisal_evidence",
        passed=passed,
        evidence_count=len(evidence),
        access_friction_observed=bool(influence.get("access_friction_observed", False)),
        should_write_memory=bool(influence.get("should_write_memory", False)),
        readback=readback,
    )


def _backend_payload_scenario() -> dict[str, Any]:
    readback = build_embodied_interaction_readback(_turn(IMAGE_SOURCE))
    evidence = _evidence_from_readback(readback)
    current_event = _dict_or_empty(readback.get("current_event"))
    perception = _dict_or_empty(current_event.get("perception"))
    turn_appraisal = _dict_or_empty(readback.get("turn_appraisal"))
    perception_semantics = _dict_or_empty(turn_appraisal.get("perception_semantics"))
    carryover = _dict_or_empty(readback.get("interaction_carryover"))
    embodied = _dict_or_empty(carryover.get("embodied_context"))
    passed = (
        len(evidence) == 1
        and len(perception.get("appraisal_evidence") or []) == 1
        and len(turn_appraisal.get("artifact_evidence") or []) == 1
        and len(perception_semantics.get("appraisal_evidence") or []) == 1
        and len(embodied.get("artifact_appraisal_evidence") or []) == 1
    )
    influence = _dict_or_empty(_dict_or_empty(readback.get("artifact_appraisal")).get("influence_summary"))
    return _scenario_result(
        name="backend_payload_carries_artifact_appraisal",
        passed=passed,
        evidence_count=len(evidence),
        access_friction_observed=bool(influence.get("access_friction_observed", False)),
        should_write_memory=bool(influence.get("should_write_memory", False)),
        readback=readback,
    )


def _blocked_live_scenario() -> dict[str, Any]:
    readback = build_embodied_interaction_readback(_turn(BLOCKED_LIVE_SOURCE))
    evidence = _evidence_from_readback(readback)
    appraisal = _dict_or_empty(readback.get("artifact_appraisal"))
    influence = _dict_or_empty(appraisal.get("influence_summary"))
    passed = (
        not evidence
        and appraisal.get("status") == "blocked"
        and influence.get("should_write_memory") is False
    )
    return _scenario_result(
        name="blocked_live_capture_does_not_create_appraisal_evidence",
        passed=passed,
        evidence_count=0,
        should_write_memory=bool(influence.get("should_write_memory", False)),
        readback=readback,
    )


def _authority_scenario() -> dict[str, Any]:
    readback = build_embodied_interaction_readback(_turn(AUDIO_SOURCE))
    appraisal = _dict_or_empty(readback.get("artifact_appraisal"))
    evidence = _evidence_from_readback(readback)
    model_api_called = bool(appraisal.get("model_api_called", False)) or any(
        bool(_dict_or_empty(item.get("authority")).get("model_api_called", False))
        for item in evidence
    )
    writeback_ready_count = int(appraisal.get("writeback_ready_count") or 0) + sum(
        1 for item in evidence if _dict_or_empty(item.get("authority")).get("writeback_ready")
    )
    influence = _dict_or_empty(appraisal.get("influence_summary"))
    boundary = _dict_or_empty(appraisal.get("authority_boundary"))
    should_write_memory = bool(influence.get("should_write_memory", False))
    passed = (
        model_api_called is False
        and writeback_ready_count == 0
        and should_write_memory is False
        and bool(boundary.get("memory_write_allowed", False)) is False
    )
    return _scenario_result(
        name="artifact_appraisal_does_not_write_memory_or_call_model_api",
        passed=passed,
        evidence_count=len(evidence),
        model_api_called=model_api_called,
        writeback_ready_count=writeback_ready_count,
        access_friction_observed=bool(influence.get("access_friction_observed", False)),
        should_write_memory=should_write_memory,
        readback=readback,
    )


def _scenarios() -> list[dict[str, Any]]:
    return [
        _artifact_semantics_scenario(),
        _access_friction_scenario(),
        _transcript_and_ocr_scenario(),
        _backend_payload_scenario(),
        _blocked_live_scenario(),
        _authority_scenario(),
    ]


def build_report(*, run_id: str) -> dict[str, Any]:
    scenarios = _scenarios()
    failed = [row["name"] for row in scenarios if row["status"] != "passed"]
    evidence_count = sum(int(row.get("evidence_count") or 0) for row in scenarios)
    model_api_called = any(bool(row.get("model_api_called", False)) for row in scenarios)
    writeback_ready_count = sum(int(row.get("writeback_ready_count") or 0) for row in scenarios)
    access_friction_observed = any(bool(row.get("access_friction_observed", False)) for row in scenarios)
    should_write_memory = any(bool(row.get("should_write_memory", False)) for row in scenarios)
    overall = (
        "passed"
        if not failed and not model_api_called and writeback_ready_count == 0 and not should_write_memory
        else "failed"
    )
    return {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": overall,
        "readiness_status": PHASE3_READY if overall == "passed" else PHASE3_IN_PROGRESS,
        "summary": {
            "scenario_count": len(scenarios),
            "evidence_count": evidence_count,
            "access_friction_observed": access_friction_observed,
            "model_api_called": model_api_called,
            "writeback_ready_count": writeback_ready_count,
            "should_write_memory": should_write_memory,
        },
        "failure_reasons": failed,
        "scenarios": scenarios,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    lines = [
        "# Embodied Interaction Runtime Phase 3 Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Summary",
        "",
        f"- Evidence count: `{summary.get('evidence_count', 0)}`",
        f"- Access friction observed: `{summary.get('access_friction_observed', False)}`",
        f"- Model API called: `{summary.get('model_api_called', False)}`",
        f"- Writeback ready count: `{summary.get('writeback_ready_count', 0)}`",
        f"- Should write memory: `{summary.get('should_write_memory', False)}`",
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
    parser = argparse.ArgumentParser(description="Run embodied interaction runtime phase 3 audit.")
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (
        str(args.run_tag).strip() or str(uuid.uuid4())[:8]
    )
    report = build_report(run_id=run_id)
    json_path = REPORT_DIR / f"embodied-interaction-runtime-phase3-audit-{run_id}.json"
    md_path = REPORT_DIR / f"embodied-interaction-runtime-phase3-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[embodied-interaction-runtime-phase3] json={json_path}")
    print(f"[embodied-interaction-runtime-phase3] md={md_path}")
    print(f"[embodied-interaction-runtime-phase3] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[embodied-interaction-runtime-phase3] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
