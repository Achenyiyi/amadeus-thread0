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
from evals.run_living_loop_realism_phase2_audit import build_backend_payload_fixture


PHASE3_READY = "living_loop_runtime_realism_phase3_ready"
PHASE3_IN_PROGRESS = "living_loop_runtime_realism_phase3_in_progress"


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _alignment(status: str) -> dict[str, Any]:
    return {
        "schema": "artifact_behavior_alignment.v1",
        "status": "ready",
        "readiness_status": "artifact_behavior_alignment_ready",
        "alignment_items": [
            {
                "source_ref_id": "img-loop-phase3",
                "primary_motive_hint": "restore_access_continuity",
                "behavior_primary_motive": "restore_access_continuity",
                "plan_primary_motive": "restore_access_continuity",
                "alignment_status": status,
                "behavior_mutation_applied": False,
                "authority": {
                    "model_api_called": False,
                    "memory_write_allowed": False,
                    "writeback_ready": False,
                    "behavior_mutation_allowed": False,
                    "behavior_mutation_applied": False,
                },
            }
        ],
        "alignment_summary": {
            "alignment_status": status,
            "aligned_count": 1 if status == "causally_aligned" else 0,
            "advisory_not_reflected_count": 1 if status == "advisory_not_reflected" else 0,
            "conflict_count": 1 if status == "behavior_conflict_observed" else 0,
            "should_mutate_behavior": False,
            "should_write_memory": False,
        },
        "authority_boundary": {
            "persona_core_mutation_allowed": False,
            "memory_write_allowed": False,
            "behavior_mutation_allowed": False,
            "external_mutation_allowed": False,
            "live_capture_enabled": False,
            "multimodal_model_api_called": False,
            "writeback_allowed": False,
        },
        "model_api_called": False,
        "writeback_ready_count": 0,
    }


def _payload_with_alignment(status: str) -> dict[str, Any]:
    payload = build_backend_payload_fixture()
    payload["turn_appraisal"] = {
        "scene": "artifact_review",
        "interaction_frame": "task",
        "signals": {"task": True, "workspace": True},
    }
    payload["behavior_action"] = {
        **_dict_or_empty(payload.get("behavior_action")),
        "primary_motive": "restore_access_continuity",
    }
    payload["behavior_plan"] = {
        **_dict_or_empty(payload.get("behavior_plan")),
        "primary_motive": "restore_access_continuity",
    }
    snapshot = _dict_or_empty(payload.get("reconsolidation_snapshot"))
    payload["reconsolidation_snapshot"] = {
        **snapshot,
        "behavior_action": {"primary_motive": "restore_access_continuity"},
        "behavior_plan": {"primary_motive": "restore_access_continuity"},
    }
    payload["writeback_trace"] = {
        "revision_traces": [{"namespace": "artifact_access", "target_id": "restore_access_continuity"}]
    }
    payload["embodied_interaction"] = {
        "readiness_status": "embodied_interaction_runtime_phase5_ready",
        "artifact_behavior_alignment": _alignment(status),
    }
    return payload


def _scenario_result(*, name: str, readback: dict[str, Any]) -> dict[str, Any]:
    alignment = _dict_or_empty(readback.get("artifact_behavior_alignment"))
    passed = (
        readback.get("overall_status") == "passed"
        and readback.get("readiness_status") == PHASE3_READY
        and alignment.get("alignment_visible") is True
        and alignment.get("model_api_called") is False
        and int(alignment.get("writeback_ready_count") or 0) == 0
        and alignment.get("should_write_memory") is False
        and alignment.get("behavior_mutation_applied") is False
    )
    return {
        "name": name,
        "status": "passed" if passed else "failed",
        "readiness_status": PHASE3_READY if passed else PHASE3_IN_PROGRESS,
        "alignment_visible": bool(alignment.get("alignment_visible", False)),
        "alignment_status": str(alignment.get("alignment_status") or ""),
        "model_api_called": bool(alignment.get("model_api_called", False)),
        "writeback_ready_count": int(alignment.get("writeback_ready_count") or 0),
        "should_write_memory": bool(alignment.get("should_write_memory", False)),
        "behavior_mutation_applied": bool(alignment.get("behavior_mutation_applied", False)),
        "readback": readback,
    }


def _causal_alignment_scenario() -> dict[str, Any]:
    readback = build_backend_payload_realism_readback(_payload_with_alignment("causally_aligned"))
    return _scenario_result(name="artifact_alignment_causally_aligned_visible", readback=readback)


def _advisory_not_reflected_scenario() -> dict[str, Any]:
    readback = build_backend_payload_realism_readback(_payload_with_alignment("advisory_not_reflected"))
    return _scenario_result(name="artifact_alignment_advisory_not_reflected_visible", readback=readback)


def _phase2_fallback_scenario() -> dict[str, Any]:
    payload = build_backend_payload_fixture()
    readback = build_backend_payload_realism_readback(payload)
    passed = (
        readback.get("overall_status") == "passed"
        and readback.get("readiness_status") == "living_loop_runtime_realism_phase2_ready"
        and _dict_or_empty(readback.get("artifact_behavior_alignment")).get("status") == "not_applicable"
    )
    return {
        "name": "payload_without_alignment_remains_phase2_ready",
        "status": "passed" if passed else "failed",
        "readiness_status": "living_loop_runtime_realism_phase2_ready" if passed else PHASE3_IN_PROGRESS,
        "alignment_visible": False,
        "alignment_status": "not_applicable",
        "model_api_called": False,
        "writeback_ready_count": 0,
        "should_write_memory": False,
        "behavior_mutation_applied": False,
        "readback": readback,
    }


def _blocked_mutation_scenario() -> dict[str, Any]:
    payload = _payload_with_alignment("causally_aligned")
    payload["embodied_interaction"]["artifact_behavior_alignment"]["alignment_items"][0]["authority"][
        "behavior_mutation_applied"
    ] = True
    readback = build_backend_payload_realism_readback(payload)
    alignment = _dict_or_empty(readback.get("artifact_behavior_alignment"))
    passed = (
        readback.get("overall_status") == "in_progress"
        and readback.get("readiness_status") == PHASE3_IN_PROGRESS
        and alignment.get("status") == "blocked"
        and alignment.get("behavior_mutation_applied") is True
    )
    return {
        "name": "mutating_alignment_is_blocked",
        "status": "passed" if passed else "failed",
        "readiness_status": PHASE3_IN_PROGRESS,
        "alignment_visible": False,
        "alignment_status": str(alignment.get("alignment_status") or ""),
        "model_api_called": bool(alignment.get("model_api_called", False)),
        "writeback_ready_count": int(alignment.get("writeback_ready_count") or 0),
        "should_write_memory": bool(alignment.get("should_write_memory", False)),
        "behavior_mutation_applied": bool(alignment.get("behavior_mutation_applied", False)),
        "readback": readback,
    }


def _scenarios() -> list[dict[str, Any]]:
    return [
        _causal_alignment_scenario(),
        _advisory_not_reflected_scenario(),
        _phase2_fallback_scenario(),
        _blocked_mutation_scenario(),
    ]


def build_report(*, run_id: str) -> dict[str, Any]:
    scenarios = _scenarios()
    failed = [row["name"] for row in scenarios if row["status"] != "passed"]
    alignment_visible_count = sum(1 for row in scenarios if row.get("alignment_visible"))
    causally_aligned_count = sum(
        1
        for row in scenarios
        if row.get("alignment_status") == "causally_aligned" and row.get("alignment_visible")
    )
    advisory_not_reflected_count = sum(
        1 for row in scenarios if row.get("alignment_status") == "advisory_not_reflected"
    )
    model_api_called = any(bool(row.get("model_api_called", False)) for row in scenarios)
    writeback_ready_count = sum(int(row.get("writeback_ready_count") or 0) for row in scenarios)
    should_write_memory = any(bool(row.get("should_write_memory", False)) for row in scenarios)
    behavior_mutation_applied = any(
        bool(row.get("behavior_mutation_applied", False)) and row.get("name") != "mutating_alignment_is_blocked"
        for row in scenarios
    )
    overall = (
        "passed"
        if (
            not failed
            and alignment_visible_count >= 2
            and causally_aligned_count >= 1
            and advisory_not_reflected_count >= 1
            and not model_api_called
            and writeback_ready_count == 0
            and not should_write_memory
            and not behavior_mutation_applied
        )
        else "failed"
    )
    return {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": overall,
        "readiness_status": PHASE3_READY if overall == "passed" else PHASE3_IN_PROGRESS,
        "summary": {
            "scenario_count": len(scenarios),
            "alignment_visible_count": alignment_visible_count,
            "causally_aligned_count": causally_aligned_count,
            "advisory_not_reflected_count": advisory_not_reflected_count,
            "model_api_called": model_api_called,
            "writeback_ready_count": writeback_ready_count,
            "should_write_memory": should_write_memory,
            "behavior_mutation_applied": behavior_mutation_applied,
        },
        "failure_reasons": failed,
        "scenarios": scenarios,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    lines = [
        "# Living Loop Runtime Realism Phase 3 Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Artifact Alignment",
        "",
        f"- Alignment visible count: `{summary.get('alignment_visible_count', 0)}`",
        f"- Causally aligned count: `{summary.get('causally_aligned_count', 0)}`",
        f"- Advisory not reflected count: `{summary.get('advisory_not_reflected_count', 0)}`",
        f"- Model API called: `{summary.get('model_api_called', False)}`",
        f"- Writeback ready count: `{summary.get('writeback_ready_count', 0)}`",
        f"- Should write memory: `{summary.get('should_write_memory', False)}`",
        f"- Behavior mutation applied: `{summary.get('behavior_mutation_applied', False)}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Status | Readiness | Alignment |",
        "| --- | --- | --- | --- |",
    ]
    for row in report.get("scenarios") or []:
        lines.append(
            f"| `{row.get('name', '')}` | `{row.get('status', '')}` | `{row.get('readiness_status', '')}` | `{row.get('alignment_status', '')}` |"
        )
    reasons = list(report.get("failure_reasons") or [])
    lines.extend(["", "## Failure Reasons", ""])
    if reasons:
        lines.extend(f"- `{reason}`" for reason in reasons)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run living loop runtime realism phase 3 audit.")
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (str(args.run_tag).strip() or str(uuid.uuid4())[:8])
    report = build_report(run_id=run_id)
    json_path = REPORT_DIR / f"living-loop-realism-phase3-audit-{run_id}.json"
    md_path = REPORT_DIR / f"living-loop-realism-phase3-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[living-loop-realism-phase3] json={json_path}")
    print(f"[living-loop-realism-phase3] md={md_path}")
    print(f"[living-loop-realism-phase3] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[living-loop-realism-phase3] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
