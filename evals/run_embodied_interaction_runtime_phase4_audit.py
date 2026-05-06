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

from amadeus_thread0.runtime.backend_api import BackendAPI
from amadeus_thread0.runtime.embodied_interaction_runtime import build_embodied_interaction_readback


PHASE4_READY = "embodied_interaction_runtime_phase4_ready"
PHASE4_IN_PROGRESS = "embodied_interaction_runtime_phase4_in_progress"
PHASE3_READY = "embodied_interaction_runtime_phase3_ready"


IMAGE_SOURCE = {
    "source_id": "img-phase4-audit",
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

TASK_SOURCE = {
    "source_id": "img-phase4-task",
    "modality": "image",
    "path": "fixtures/task.png",
    "consent_scope": "single_turn",
    "capture_method": "operator_attached_file",
    "label": "task.png",
    "semantic_label": "task_panel",
    "semantic_summary": "A dashboard panel with the current task checklist.",
    "semantic_tags": ["task", "checklist"],
    "confidence": 0.78,
}

BLOCKED_LIVE_SOURCE = {
    "source_id": "mic-live-phase4-audit",
    "modality": "audio",
    "artifact_ref": "live:microphone",
    "consent_scope": "single_turn",
    "capture_method": "background_microphone",
    "transcript": "This must not be admitted.",
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _turn(source: dict[str, Any], *, behavior_plan: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "final_text": "嗯，我听见了。",
        "current_event": {
            "kind": "multimodal_observation",
            "perception": {"channel": str(source.get("modality") or "").strip()},
            "digital_body_hints": {"multimodal_sources": [source]},
        },
        "turn_appraisal": {"scene": "artifact_review"},
        "behavior_plan": behavior_plan or {"primary_motive": "continue_workspace_task"},
        "interaction_carryover": {"embodied_context": {"kind": "multimodal_observation"}},
        "reconsolidation_snapshot": {"final_text": "嗯，我听见了。"},
    }


def _hints_from_readback(readback: dict[str, Any]) -> list[dict[str, Any]]:
    motive = _dict_or_empty(readback.get("artifact_motive"))
    return [
        dict(item)
        for item in list(motive.get("motive_hints") or [])
        if isinstance(item, dict)
    ]


def _scenario_result(
    *,
    name: str,
    passed: bool,
    hint_count: int,
    model_api_called: bool = False,
    writeback_ready_count: int = 0,
    should_write_memory: bool = False,
    behavior_mutation_allowed: bool = False,
    readback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": "passed" if passed else "failed",
        "readiness_status": PHASE4_READY if passed else PHASE4_IN_PROGRESS,
        "hint_count": int(hint_count),
        "model_api_called": bool(model_api_called),
        "writeback_ready_count": int(writeback_ready_count),
        "should_write_memory": bool(should_write_memory),
        "behavior_mutation_allowed": bool(behavior_mutation_allowed),
        "readback": readback or {},
    }


def _artifact_appraisal_to_motive_scenario() -> dict[str, Any]:
    readback = build_embodied_interaction_readback(_turn(IMAGE_SOURCE))
    hints = _hints_from_readback(readback)
    first = _dict_or_empty(hints[0] if hints else {})
    passed = (
        readback.get("readiness_status") == PHASE4_READY
        and len(hints) == 1
        and first.get("source_ref_id") == IMAGE_SOURCE["source_id"]
        and first.get("primary_motive_hint") == "restore_access_continuity"
        and _dict_or_empty(first.get("authority")).get("behavior_mutation_allowed") is False
    )
    return _scenario_result(
        name="artifact_appraisal_becomes_motive_hint",
        passed=passed,
        hint_count=len(hints),
        readback=readback,
    )


def _access_friction_scenario() -> dict[str, Any]:
    behavior_plan = {"primary_motive": "continue_workspace_task"}
    readback = build_embodied_interaction_readback(_turn(IMAGE_SOURCE, behavior_plan=behavior_plan))
    hints = _hints_from_readback(readback)
    first = _dict_or_empty(hints[0] if hints else {})
    plan = _dict_or_empty(readback.get("behavior_plan"))
    motive = _dict_or_empty(readback.get("artifact_motive"))
    summary = _dict_or_empty(motive.get("motive_summary"))
    passed = (
        first.get("primary_motive_hint") == "restore_access_continuity"
        and summary.get("goal_bias") == "resolve_access_before_task_continuation"
        and summary.get("should_mutate_behavior") is False
        and plan.get("primary_motive") == "continue_workspace_task"
        and len(plan.get("artifact_motive_hints") or []) == 1
    )
    return _scenario_result(
        name="access_friction_biases_motive_without_behavior_mutation",
        passed=passed,
        hint_count=len(hints),
        should_write_memory=bool(summary.get("should_write_memory", False)),
        behavior_mutation_allowed=bool(summary.get("should_mutate_behavior", False)),
        readback=readback,
    )


class _FakeSession:
    def build_evolution_summary(self, *, state_values=None):
        return {"current_turn": {}}

    def extract_final_text(self, values, *, streamed_text=""):
        data = values if isinstance(values, dict) else {}
        return str(data.get("final_text") or streamed_text or "")


class _FakeRuntimeBundle:
    thread_id = "thread-phase4"
    backend_session = _FakeSession()
    memory_admin = None

    class settings:
        checkpoint_db_path = ""
        data_dir = ""
        model_provider = "test"
        model_name = "test"
        model_base_url = ""
        runtime_mode = "test"


def _backend_payload_scenario() -> dict[str, Any]:
    api = BackendAPI(runtime_bundle=_FakeRuntimeBundle(), base_data_dir=PROJECT_ROOT, cwd=PROJECT_ROOT)
    state_values = _turn(IMAGE_SOURCE)
    turn_payload = api.build_turn_response(state_values=state_values, streamed_text="ignored").payload
    event_payload = api.build_event_round_response(state_values=state_values, final_text="嗯，我听见了。").payload
    passed = True
    hint_count = 0
    for payload in (turn_payload, event_payload):
        hints = _hints_from_readback(_dict_or_empty(payload.get("embodied_interaction")))
        hint_count += len(hints)
        passed = passed and (
            len(hints) == 1
            and payload["current_event"]["perception"]["motive_hints"][0]["source_ref_id"]
            == IMAGE_SOURCE["source_id"]
            and payload["turn_appraisal"]["motive_evidence"][0]["source_ref_id"]
            == IMAGE_SOURCE["source_id"]
            and payload["interaction_carryover"]["embodied_context"]["artifact_motive_hints"][0][
                "source_ref_id"
            ]
            == IMAGE_SOURCE["source_id"]
        )
    return _scenario_result(
        name="backend_payload_carries_artifact_motive",
        passed=passed,
        hint_count=hint_count,
        readback={"turn": turn_payload, "event": event_payload},
    )


def _blocked_live_scenario() -> dict[str, Any]:
    readback = build_embodied_interaction_readback(_turn(BLOCKED_LIVE_SOURCE))
    motive = _dict_or_empty(readback.get("artifact_motive"))
    hints = _hints_from_readback(readback)
    passed = not hints and motive.get("status") == "blocked"
    return _scenario_result(
        name="blocked_live_capture_does_not_create_motive_hint",
        passed=passed,
        hint_count=0,
        readback=readback,
    )


def _authority_scenario() -> dict[str, Any]:
    readback = build_embodied_interaction_readback(_turn(TASK_SOURCE))
    motive = _dict_or_empty(readback.get("artifact_motive"))
    summary = _dict_or_empty(motive.get("motive_summary"))
    boundary = _dict_or_empty(motive.get("authority_boundary"))
    hints = _hints_from_readback(readback)
    model_api_called = bool(motive.get("model_api_called", False)) or any(
        bool(_dict_or_empty(item.get("authority")).get("model_api_called", False))
        for item in hints
    )
    writeback_ready_count = int(motive.get("writeback_ready_count") or 0) + sum(
        1 for item in hints if _dict_or_empty(item.get("authority")).get("writeback_ready")
    )
    should_write_memory = bool(summary.get("should_write_memory", False))
    behavior_mutation_allowed = bool(boundary.get("behavior_mutation_allowed", False)) or any(
        bool(_dict_or_empty(item.get("authority")).get("behavior_mutation_allowed", False))
        for item in hints
    )
    passed = (
        len(hints) == 1
        and model_api_called is False
        and writeback_ready_count == 0
        and should_write_memory is False
        and behavior_mutation_allowed is False
        and bool(boundary.get("memory_write_allowed", False)) is False
    )
    return _scenario_result(
        name="artifact_motive_does_not_write_memory_or_call_model_api",
        passed=passed,
        hint_count=len(hints),
        model_api_called=model_api_called,
        writeback_ready_count=writeback_ready_count,
        should_write_memory=should_write_memory,
        behavior_mutation_allowed=behavior_mutation_allowed,
        readback=readback,
    )


def _phase3_preserved_scenario() -> dict[str, Any]:
    readback = build_embodied_interaction_readback(_turn(IMAGE_SOURCE))
    appraisal = _dict_or_empty(readback.get("artifact_appraisal"))
    evidence = [
        dict(item)
        for item in list(appraisal.get("evidence_items") or [])
        if isinstance(item, dict)
    ]
    first = _dict_or_empty(evidence[0] if evidence else {})
    authority = _dict_or_empty(first.get("authority"))
    passed = (
        readback.get("readiness_status") == PHASE4_READY
        and appraisal.get("readiness_status") == "artifact_appraisal_bridge_ready"
        and len(evidence) == 1
        and first.get("source_ref_id") == IMAGE_SOURCE["source_id"]
        and authority.get("model_api_called") is False
        and authority.get("memory_write_allowed") is False
        and authority.get("writeback_ready") is False
    )
    return _scenario_result(
        name="phase3_appraisal_contract_remains_preserved",
        passed=passed,
        hint_count=len(_hints_from_readback(readback)),
        readback={
            "phase3_expected_readiness": PHASE3_READY,
            "phase3_subcontract_readiness": appraisal.get("readiness_status"),
            "readback": readback,
        },
    )


def _scenarios() -> list[dict[str, Any]]:
    return [
        _artifact_appraisal_to_motive_scenario(),
        _access_friction_scenario(),
        _backend_payload_scenario(),
        _blocked_live_scenario(),
        _authority_scenario(),
        _phase3_preserved_scenario(),
    ]


def build_report(*, run_id: str) -> dict[str, Any]:
    scenarios = _scenarios()
    failed = [row["name"] for row in scenarios if row["status"] != "passed"]
    hint_count = sum(int(row.get("hint_count") or 0) for row in scenarios)
    model_api_called = any(bool(row.get("model_api_called", False)) for row in scenarios)
    writeback_ready_count = sum(int(row.get("writeback_ready_count") or 0) for row in scenarios)
    should_write_memory = any(bool(row.get("should_write_memory", False)) for row in scenarios)
    behavior_mutation_allowed = any(bool(row.get("behavior_mutation_allowed", False)) for row in scenarios)
    overall = (
        "passed"
        if (
            not failed
            and hint_count >= 1
            and not model_api_called
            and writeback_ready_count == 0
            and not should_write_memory
            and not behavior_mutation_allowed
        )
        else "failed"
    )
    return {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": overall,
        "readiness_status": PHASE4_READY if overall == "passed" else PHASE4_IN_PROGRESS,
        "summary": {
            "scenario_count": len(scenarios),
            "hint_count": hint_count,
            "model_api_called": model_api_called,
            "writeback_ready_count": writeback_ready_count,
            "should_write_memory": should_write_memory,
            "behavior_mutation_allowed": behavior_mutation_allowed,
        },
        "failure_reasons": failed,
        "scenarios": scenarios,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    lines = [
        "# Embodied Interaction Runtime Phase 4 Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Summary",
        "",
        f"- Hint count: `{summary.get('hint_count', 0)}`",
        f"- Model API called: `{summary.get('model_api_called', False)}`",
        f"- Writeback ready count: `{summary.get('writeback_ready_count', 0)}`",
        f"- Should write memory: `{summary.get('should_write_memory', False)}`",
        f"- Behavior mutation allowed: `{summary.get('behavior_mutation_allowed', False)}`",
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
    parser = argparse.ArgumentParser(description="Run embodied interaction runtime phase 4 audit.")
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (
        str(args.run_tag).strip() or str(uuid.uuid4())[:8]
    )
    report = build_report(run_id=run_id)
    json_path = REPORT_DIR / f"embodied-interaction-runtime-phase4-audit-{run_id}.json"
    md_path = REPORT_DIR / f"embodied-interaction-runtime-phase4-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[embodied-interaction-runtime-phase4] json={json_path}")
    print(f"[embodied-interaction-runtime-phase4] md={md_path}")
    print(f"[embodied-interaction-runtime-phase4] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[embodied-interaction-runtime-phase4] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
