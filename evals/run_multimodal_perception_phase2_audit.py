from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from amadeus_thread0.runtime.artifact_perception_semantics import build_artifact_semantics_readback
from amadeus_thread0.runtime.embodied_interaction_runtime import build_embodied_interaction_readback
from amadeus_thread0.runtime.multimodal_sources import (
    MULTIMODAL_PERCEPTION_PHASE2_IN_PROGRESS,
    MULTIMODAL_PERCEPTION_PHASE2_READY,
    build_multimodal_inspection_packet,
    normalize_multimodal_source,
)


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _source(source_id: str = "img-phase2-audit") -> dict[str, Any]:
    return normalize_multimodal_source(
        {
            "source_id": source_id,
            "modality": "image",
            "path": f"fixtures/{source_id}.png",
            "consent_scope": "single_turn",
            "capture_method": "operator_attached_file",
            "label": f"{source_id}.png",
        }
    )


def _scenario_result(
    *,
    name: str,
    passed: bool,
    packet: dict[str, Any] | None = None,
    readback: dict[str, Any] | None = None,
    semantic_observation_count: int = 0,
    model_api_called: bool = False,
    live_capture_enabled: bool = False,
    memory_write_allowed: bool = False,
    external_mutation_allowed: bool = False,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": "passed" if passed else "failed",
        "readiness_status": MULTIMODAL_PERCEPTION_PHASE2_READY
        if passed
        else MULTIMODAL_PERCEPTION_PHASE2_IN_PROGRESS,
        "packet": packet or {},
        "readback": readback or {},
        "semantic_observation_count": int(semantic_observation_count),
        "model_api_called": bool(model_api_called),
        "live_capture_enabled": bool(live_capture_enabled),
        "memory_write_allowed": bool(memory_write_allowed),
        "external_mutation_allowed": bool(external_mutation_allowed),
    }


def _pending_approval_scenario() -> dict[str, Any]:
    source = _source("img-phase2-pending")
    packet = build_multimodal_inspection_packet(source)
    semantics = build_artifact_semantics_readback([{**source, "multimodal_inspection_result": packet.get("multimodal_inspection_result")}])
    preview = _dict_or_empty(packet.get("multimodal_inspection_preview"))
    spec = _dict_or_empty(packet.get("multimodal_inspection_spec"))
    passed = (
        packet.get("intent") == "artifact:inspect_multimodal"
        and packet.get("status") == "awaiting_approval"
        and packet.get("requires_approval") is True
        and packet.get("writeback_ready") is False
        and preview.get("auto_execute") is False
        and preview.get("model_api_call_planned") is False
        and spec.get("model_api_call_allowed") is False
        and spec.get("live_capture_allowed") is False
        and semantics.get("semantic_observations") == []
    )
    return _scenario_result(
        name="pending_approval",
        passed=passed,
        packet=packet,
        readback=semantics,
        semantic_observation_count=len(_list_or_empty(semantics.get("semantic_observations"))),
        model_api_called=bool(spec.get("model_api_call_allowed", False))
        or bool(preview.get("model_api_call_planned", False)),
        external_mutation_allowed=False,
    )


def _completed_approved_inspection_scenario() -> dict[str, Any]:
    source = _source("img-phase2-completed")
    packet = build_multimodal_inspection_packet(
        source,
        status="completed",
        approved_result={
            "semantic_summary": "The approved fixture result shows a checklist.",
            "tags": ["checklist"],
            "confidence": 0.82,
        },
    )
    readback = build_embodied_interaction_readback(
        {
            "final_text": "嗯，我看到了。",
            "current_event": {"digital_body_hints": {"multimodal_sources": [source]}},
            "action_packets": [packet],
            "behavior_action": {"primary_motive": "continue_artifact_review"},
            "behavior_plan": {"primary_motive": "continue_artifact_review"},
            "interaction_carryover": {"embodied_context": {"kind": "multimodal_observation"}},
            "reconsolidation_snapshot": {"final_text": "嗯，我看到了。"},
        }
    )
    observations = _list_or_empty(_dict_or_empty(readback.get("artifact_semantics")).get("semantic_observations"))
    first = _dict_or_empty(observations[0] if observations else {})
    boundary = _dict_or_empty(_dict_or_empty(readback.get("artifact_semantics")).get("authority_boundary"))
    passed = (
        packet.get("status") == "completed"
        and packet.get("requires_approval") is False
        and packet.get("writeback_ready") is True
        and len(observations) == 1
        and first.get("source") == "approved_inspection_result"
        and first.get("model_api_called") is False
        and first.get("writeback_ready") is False
        and boundary.get("memory_write_allowed") is False
        and boundary.get("external_mutation_allowed") is False
    )
    return _scenario_result(
        name="completed_approved_inspection",
        passed=passed,
        packet=packet,
        readback=readback,
        semantic_observation_count=len(observations),
        model_api_called=bool(first.get("model_api_called", False)),
        memory_write_allowed=bool(boundary.get("memory_write_allowed", False)),
        external_mutation_allowed=bool(boundary.get("external_mutation_allowed", False)),
    )


def _rejected_inspection_scenario() -> dict[str, Any]:
    source = _source("img-phase2-rejected")
    packet = build_multimodal_inspection_packet(
        source,
        status="rejected",
        approved_result={
            "approval_status": "rejected",
            "semantic_summary": "This rejected result must not become semantics.",
        },
    )
    semantics = build_artifact_semantics_readback([{**source, "multimodal_inspection_result": packet.get("multimodal_inspection_result")}])
    passed = (
        packet.get("status") == "rejected"
        and packet.get("requires_approval") is False
        and packet.get("writeback_ready") is False
        and semantics.get("semantic_observations") == []
        and int(semantics.get("writeback_ready_count") or 0) == 0
    )
    return _scenario_result(
        name="rejected_inspection",
        passed=passed,
        packet=packet,
        readback=semantics,
        semantic_observation_count=len(_list_or_empty(semantics.get("semantic_observations"))),
    )


def _blocked_live_capture_scenario() -> dict[str, Any]:
    sources = [
        normalize_multimodal_source(
            {
                "source_id": "mic-phase2-blocked",
                "modality": "audio",
                "artifact_ref": "live:microphone",
                "consent_scope": "single_turn",
                "capture_method": "background_microphone",
            }
        ),
        normalize_multimodal_source(
            {
                "source_id": "cam-phase2-blocked",
                "modality": "image",
                "artifact_ref": "live:camera",
                "consent_scope": "single_turn",
                "capture_method": "background_camera",
            }
        ),
        normalize_multimodal_source(
            {
                "source_id": "screen-phase2-blocked",
                "modality": "screen",
                "artifact_ref": "live:screen",
                "consent_scope": "single_turn",
                "capture_method": "background_screen",
            }
        ),
    ]
    packets = [build_multimodal_inspection_packet(source) for source in sources]
    readback = build_embodied_interaction_readback(
        {
            "current_event": {"digital_body_hints": {"multimodal_sources": sources}},
            "action_packets": packets,
        }
    )
    boundary = _dict_or_empty(readback.get("authority_boundary"))
    previews = [_dict_or_empty(packet.get("multimodal_inspection_preview")) for packet in packets]
    passed = (
        all(source.get("status") == "blocked" for source in sources)
        and all(packet.get("status") == "blocked" for packet in packets)
        and all(packet.get("requires_approval") is False for packet in packets)
        and all(preview.get("blocked") is True for preview in previews)
        and all(preview.get("auto_execute") is False for preview in previews)
        and readback.get("source_status", {}).get("blocked_count") == 3
        and boundary.get("live_microphone_enabled") is False
        and boundary.get("live_camera_enabled") is False
        and boundary.get("background_screen_capture_enabled") is False
    )
    return _scenario_result(
        name="blocked_live_capture",
        passed=passed,
        packet={"packets": packets},
        readback=readback,
        live_capture_enabled=any(
            bool(boundary.get(key, False))
            for key in ("live_microphone_enabled", "live_camera_enabled", "background_screen_capture_enabled")
        ),
    )


def _scenarios() -> list[dict[str, Any]]:
    return [
        _pending_approval_scenario(),
        _completed_approved_inspection_scenario(),
        _rejected_inspection_scenario(),
        _blocked_live_capture_scenario(),
    ]


def build_report(*, run_id: str) -> dict[str, Any]:
    scenarios = _scenarios()
    failed = [str(row.get("name") or "") for row in scenarios if row.get("status") != "passed"]
    summary = {
        "scenario_count": len(scenarios),
        "semantic_observation_count": sum(int(row.get("semantic_observation_count") or 0) for row in scenarios),
        "model_api_called": any(bool(row.get("model_api_called", False)) for row in scenarios),
        "live_capture_enabled": any(bool(row.get("live_capture_enabled", False)) for row in scenarios),
        "memory_write_allowed": any(bool(row.get("memory_write_allowed", False)) for row in scenarios),
        "external_mutation_allowed": any(bool(row.get("external_mutation_allowed", False)) for row in scenarios),
    }
    overall = (
        "passed"
        if (
            not failed
            and summary["scenario_count"] == 4
            and summary["semantic_observation_count"] >= 1
            and not summary["model_api_called"]
            and not summary["live_capture_enabled"]
            and not summary["memory_write_allowed"]
            and not summary["external_mutation_allowed"]
        )
        else "failed"
    )
    return {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": overall,
        "readiness_status": MULTIMODAL_PERCEPTION_PHASE2_READY
        if overall == "passed"
        else MULTIMODAL_PERCEPTION_PHASE2_IN_PROGRESS,
        "summary": summary,
        "failure_reasons": failed,
        "scenarios": scenarios,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = _dict_or_empty(report.get("summary"))
    lines = [
        "# Multimodal Perception Phase 2 Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Summary",
        "",
        f"- Scenarios: `{summary.get('scenario_count', 0)}`",
        f"- Semantic observations: `{summary.get('semantic_observation_count', 0)}`",
        f"- Model API called: `{summary.get('model_api_called', False)}`",
        f"- Live capture enabled: `{summary.get('live_capture_enabled', False)}`",
        f"- Memory write allowed: `{summary.get('memory_write_allowed', False)}`",
        f"- External mutation allowed: `{summary.get('external_mutation_allowed', False)}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Status | Readiness | Observations |",
        "| --- | --- | --- | ---: |",
    ]
    for row in report.get("scenarios") or []:
        lines.append(
            f"| `{row.get('name', '')}` | `{row.get('status', '')}` | `{row.get('readiness_status', '')}` | `{row.get('semantic_observation_count', 0)}` |"
        )
    reasons = [str(reason) for reason in _list_or_empty(report.get("failure_reasons")) if str(reason)]
    lines.extend(["", "## Failure Reasons", ""])
    if reasons:
        lines.extend(f"- `{reason}`" for reason in reasons)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run multimodal perception Phase 2 audit.")
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (
        str(args.run_tag).strip() or str(uuid.uuid4())[:8]
    )
    report = build_report(run_id=run_id)
    json_path = REPORT_DIR / f"multimodal-perception-phase2-audit-{run_id}.json"
    md_path = REPORT_DIR / f"multimodal-perception-phase2-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[multimodal-perception-phase2] json={json_path}")
    print(f"[multimodal-perception-phase2] md={md_path}")
    print(f"[multimodal-perception-phase2] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[multimodal-perception-phase2] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
