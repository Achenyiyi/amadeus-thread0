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

from amadeus_thread0.runtime.approved_artifact_multimodal_runtime import (
    APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_IN_PROGRESS,
    APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_READY,
    AUTHORITY_BOUNDARY,
    apply_approved_artifact_multimodal_runtime_to_payload,
    build_approved_artifact_multimodal_runtime_readback,
)
from amadeus_thread0.runtime.embodied_interaction_runtime import (
    build_embodied_interaction_readback,
)
from amadeus_thread0.runtime.multimodal_sources import (
    build_multimodal_inspection_packet,
    normalize_multimodal_source,
)


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _source(source_id: str = "img-approved-runtime-audit") -> dict[str, Any]:
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


def _approved_result(source_id: str = "img-approved-runtime-audit") -> dict[str, Any]:
    return {
        "source_ref_id": source_id,
        "semantic_summary": "The approved audit result shows a checklist.",
        "tags": ["checklist"],
        "confidence": 0.86,
    }


def _scenario(
    *,
    name: str,
    passed: bool,
    readback: dict[str, Any] | None = None,
    semantic_observation_count: int = 0,
    completed_packet_count: int = 0,
    blocked_count: int = 0,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": "passed" if passed else "failed",
        "readiness_status": (
            APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_READY
            if passed
            else APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_IN_PROGRESS
        ),
        "semantic_observation_count": int(semantic_observation_count),
        "completed_packet_count": int(completed_packet_count),
        "blocked_count": int(blocked_count),
        "readback": readback or {},
    }


def _approved_result_ingestion() -> dict[str, Any]:
    source = _source()
    packet = build_multimodal_inspection_packet(source)
    readback = build_approved_artifact_multimodal_runtime_readback(
        packet,
        approval={"proposal_id": packet["proposal_id"], "approval_status": "approved"},
        approved_result=_approved_result(),
    )
    completed = _dict_or_empty(readback.get("completed_packet"))
    embodied = build_embodied_interaction_readback(
        {
            "final_text": "嗯，我看到了。",
            "current_event": {"digital_body_hints": {"multimodal_sources": [source]}},
            "action_packets": [completed],
            "behavior_action": {"primary_motive": "continue_artifact_review"},
            "behavior_plan": {"primary_motive": "continue_artifact_review"},
            "interaction_carryover": {"embodied_context": {"kind": "multimodal_observation"}},
            "reconsolidation_snapshot": {"final_text": "嗯，我看到了。"},
        }
    )
    observations = list(
        _dict_or_empty(embodied.get("artifact_semantics")).get("semantic_observations")
        or []
    )
    passed = (
        readback.get("overall_status") == "passed"
        and completed.get("status") == "completed"
        and completed.get("writeback_ready") is True
        and len(observations) == 1
        and _dict_or_empty(observations[0]).get("source") == "approved_inspection_result"
    )
    return _scenario(
        name="approved_result_ingestion",
        passed=passed,
        readback={"runtime": readback, "embodied": embodied},
        semantic_observation_count=len(observations),
        completed_packet_count=1 if completed else 0,
    )


def _proposal_or_source_drift_rejected() -> dict[str, Any]:
    source = _source("img-approved-runtime-drift")
    packet = build_multimodal_inspection_packet(source)
    proposal_drift = build_approved_artifact_multimodal_runtime_readback(
        packet,
        approval={"proposal_id": "ap-drifted", "approval_status": "approved"},
        approved_result=_approved_result("img-approved-runtime-drift"),
    )
    source_drift = build_approved_artifact_multimodal_runtime_readback(
        packet,
        approval={"proposal_id": packet["proposal_id"], "approval_status": "approved"},
        approved_result={
            **_approved_result("img-other-runtime-drift"),
            "artifact_ref": "fixtures/img-other-runtime-drift.png",
        },
    )
    passed = (
        proposal_drift.get("completed_packet") == {}
        and source_drift.get("completed_packet") == {}
        and "approval_proposal_id_drift" in proposal_drift.get("failure_reasons", [])
        and "source_ref_id_drift" in source_drift.get("failure_reasons", [])
    )
    return _scenario(
        name="proposal_or_source_drift_rejected",
        passed=passed,
        readback={"proposal_drift": proposal_drift, "source_drift": source_drift},
        blocked_count=2 if passed else 0,
    )


def _model_api_or_live_capture_rejected() -> dict[str, Any]:
    source = _source("img-approved-runtime-unsafe")
    packet = build_multimodal_inspection_packet(source)
    model = build_approved_artifact_multimodal_runtime_readback(
        packet,
        approval={"proposal_id": packet["proposal_id"], "approval_status": "approved"},
        approved_result={
            **_approved_result("img-approved-runtime-unsafe"),
            "model_api_called": True,
        },
    )
    live = build_approved_artifact_multimodal_runtime_readback(
        packet,
        approval={"proposal_id": packet["proposal_id"], "approval_status": "approved"},
        approved_result={
            **_approved_result("img-approved-runtime-unsafe"),
            "live_capture_used": True,
        },
    )
    passed = (
        model.get("completed_packet") == {}
        and live.get("completed_packet") == {}
        and "model_api_called_not_allowed" in model.get("failure_reasons", [])
        and "live_capture_used_not_allowed" in live.get("failure_reasons", [])
    )
    return _scenario(
        name="model_api_or_live_capture_rejected",
        passed=passed,
        readback={"model": model, "live": live},
        blocked_count=2 if passed else 0,
    )


def _backend_payload_packet_completion() -> dict[str, Any]:
    source = _source("img-approved-runtime-payload")
    packet = build_multimodal_inspection_packet(source)
    payload = {
        "kind": "assistant_turn",
        "final_text": "嗯，我看到了。",
        "current_event": {"digital_body_hints": {"multimodal_sources": [source]}},
        "action_packets": [packet],
        "reconsolidation_snapshot": {"final_text": "嗯，我看到了。"},
    }
    updated = apply_approved_artifact_multimodal_runtime_to_payload(
        payload,
        approvals=[{"proposal_id": packet["proposal_id"], "approval_status": "approved"}],
        approved_results=[{"proposal_id": packet["proposal_id"], **_approved_result("img-approved-runtime-payload")}],
    )
    completed = _dict_or_empty((updated.get("action_packets") or [{}])[0])
    readback = _dict_or_empty(updated.get("approved_artifact_multimodal_runtime"))
    passed = (
        completed.get("status") == "completed"
        and completed.get("writeback_ready") is True
        and readback.get("readiness_status")
        == APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_READY
        and readback.get("summary", {}).get("completed_count") == 1
    )
    return _scenario(
        name="backend_payload_packet_completion",
        passed=passed,
        readback=updated,
        completed_packet_count=1 if completed.get("status") == "completed" else 0,
    )


def _scenarios() -> dict[str, dict[str, Any]]:
    rows = [
        _approved_result_ingestion(),
        _proposal_or_source_drift_rejected(),
        _model_api_or_live_capture_rejected(),
        _backend_payload_packet_completion(),
    ]
    return {str(row["name"]): row for row in rows}


def build_report(*, run_id: str) -> dict[str, Any]:
    scenarios = _scenarios()
    failed = [key for key, row in scenarios.items() if row.get("status") != "passed"]
    summary = {
        "scenario_count": len(scenarios),
        "semantic_observation_count": sum(
            int(row.get("semantic_observation_count") or 0) for row in scenarios.values()
        ),
        "completed_packet_count": sum(
            int(row.get("completed_packet_count") or 0) for row in scenarios.values()
        ),
        "blocked_count": sum(int(row.get("blocked_count") or 0) for row in scenarios.values()),
        "model_api_called": False,
        "live_capture_enabled": False,
        "memory_write_allowed": False,
        "external_mutation_allowed": False,
    }
    boundary = dict(AUTHORITY_BOUNDARY)
    overall = (
        "passed"
        if (
            not failed
            and summary["scenario_count"] == 4
            and summary["semantic_observation_count"] >= 1
            and summary["completed_packet_count"] >= 2
            and summary["blocked_count"] >= 4
            and not summary["model_api_called"]
            and not summary["live_capture_enabled"]
            and not summary["memory_write_allowed"]
            and not summary["external_mutation_allowed"]
            and boundary.get("live_capture_allowed") is False
            and boundary.get("multimodal_model_api_called") is False
            and boundary.get("memory_write_allowed") is False
            and boundary.get("external_mutation_allowed") is False
        )
        else "failed"
    )
    return {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": overall,
        "readiness_status": (
            APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_READY
            if overall == "passed"
            else APPROVED_ARTIFACT_MULTIMODAL_RUNTIME_PHASE1_IN_PROGRESS
        ),
        "summary": summary,
        "authority_boundary": boundary,
        "failure_reasons": failed,
        "scenarios": scenarios,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = _dict_or_empty(report.get("summary"))
    lines = [
        "# Approved Artifact Multimodal Runtime Phase 1 Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Summary",
        "",
        f"- Scenarios: `{summary.get('scenario_count', 0)}`",
        f"- Semantic observations: `{summary.get('semantic_observation_count', 0)}`",
        f"- Completed packets: `{summary.get('completed_packet_count', 0)}`",
        f"- Blocked unsafe/drifted attempts: `{summary.get('blocked_count', 0)}`",
        f"- Model API called: `{summary.get('model_api_called', False)}`",
        f"- Live capture enabled: `{summary.get('live_capture_enabled', False)}`",
        f"- Memory write allowed: `{summary.get('memory_write_allowed', False)}`",
        f"- External mutation allowed: `{summary.get('external_mutation_allowed', False)}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Status | Readiness | Observations | Completed Packets | Blocked |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for key, row in (report.get("scenarios") or {}).items():
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| `{key}` | `{row.get('status', '')}` | `{row.get('readiness_status', '')}` | "
            f"`{row.get('semantic_observation_count', 0)}` | "
            f"`{row.get('completed_packet_count', 0)}` | `{row.get('blocked_count', 0)}` |"
        )
    lines.extend(["", "## Authority Boundary", "", "| Boundary | Value |", "| --- | --- |"])
    for key, value in _dict_or_empty(report.get("authority_boundary")).items():
        lines.append(f"| `{key}` | `{value}` |")
    failures = [str(reason) for reason in report.get("failure_reasons", []) if str(reason)]
    lines.extend(["", "## Failure Reasons", ""])
    if failures:
        lines.extend(f"- `{reason}`" for reason in failures)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run approved artifact multimodal runtime Phase 1 audit.")
    parser.add_argument("--run-tag", default="")
    parser.add_argument("--reports-dir", default=str(REPORT_DIR))
    args = parser.parse_args()
    report_dir = Path(args.reports_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (
        str(args.run_tag).strip() or str(uuid.uuid4())[:8]
    )
    report = build_report(run_id=run_id)
    json_path = report_dir / f"approved-artifact-multimodal-runtime-phase1-audit-{run_id}.json"
    md_path = report_dir / f"approved-artifact-multimodal-runtime-phase1-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[approved-artifact-multimodal-runtime-phase1] json={json_path}")
    print(f"[approved-artifact-multimodal-runtime-phase1] md={md_path}")
    print(f"[approved-artifact-multimodal-runtime-phase1] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[approved-artifact-multimodal-runtime-phase1] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
