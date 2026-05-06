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


PHASE5_READY = "embodied_interaction_runtime_phase5_ready"
PHASE5_IN_PROGRESS = "embodied_interaction_runtime_phase5_in_progress"
PHASE4_READY = "embodied_interaction_runtime_phase4_ready"


IMAGE_SOURCE = {
    "source_id": "img-phase5-audit",
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
    "source_id": "img-phase5-task",
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
    "source_id": "mic-live-phase5-audit",
    "modality": "audio",
    "artifact_ref": "live:microphone",
    "consent_scope": "single_turn",
    "capture_method": "background_microphone",
    "transcript": "This must not be admitted.",
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _turn(
    source: dict[str, Any],
    *,
    behavior_action: dict[str, Any] | None = None,
    behavior_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "final_text": "嗯，我听见了。",
        "current_event": {
            "kind": "multimodal_observation",
            "perception": {"channel": str(source.get("modality") or "").strip()},
            "digital_body_hints": {"multimodal_sources": [source]},
        },
        "turn_appraisal": {"scene": "artifact_review"},
        "behavior_action": behavior_action or {"primary_motive": "continue_workspace_task"},
        "behavior_plan": behavior_plan or {"primary_motive": "continue_workspace_task"},
        "interaction_carryover": {"embodied_context": {"kind": "multimodal_observation"}},
        "reconsolidation_snapshot": {"final_text": "嗯，我听见了。"},
    }


def _alignment_from_readback(readback: dict[str, Any]) -> dict[str, Any]:
    return _dict_or_empty(readback.get("artifact_behavior_alignment"))


def _alignment_items(readback: dict[str, Any]) -> list[dict[str, Any]]:
    alignment = _alignment_from_readback(readback)
    return [
        dict(item)
        for item in list(alignment.get("alignment_items") or [])
        if isinstance(item, dict)
    ]


def _scenario_result(
    *,
    name: str,
    passed: bool,
    alignment_count: int,
    advisory_not_reflected_count: int = 0,
    causally_aligned_count: int = 0,
    model_api_called: bool = False,
    writeback_ready_count: int = 0,
    should_write_memory: bool = False,
    behavior_mutation_applied: bool = False,
    readback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": "passed" if passed else "failed",
        "readiness_status": PHASE5_READY if passed else PHASE5_IN_PROGRESS,
        "alignment_count": int(alignment_count),
        "advisory_not_reflected_count": int(advisory_not_reflected_count),
        "causally_aligned_count": int(causally_aligned_count),
        "model_api_called": bool(model_api_called),
        "writeback_ready_count": int(writeback_ready_count),
        "should_write_memory": bool(should_write_memory),
        "behavior_mutation_applied": bool(behavior_mutation_applied),
        "readback": readback or {},
    }


def _not_reflected_scenario() -> dict[str, Any]:
    readback = build_embodied_interaction_readback(
        _turn(
            IMAGE_SOURCE,
            behavior_action={"primary_motive": "continue_workspace_task"},
            behavior_plan={"primary_motive": "continue_workspace_task"},
        )
    )
    items = _alignment_items(readback)
    first = _dict_or_empty(items[0] if items else {})
    summary = _dict_or_empty(_alignment_from_readback(readback).get("alignment_summary"))
    passed = (
        readback.get("readiness_status") == PHASE5_READY
        and len(items) == 1
        and first.get("alignment_status") == "advisory_not_reflected"
        and first.get("behavior_primary_motive") == "continue_workspace_task"
        and first.get("plan_primary_motive") == "continue_workspace_task"
        and first.get("behavior_mutation_applied") is False
        and summary.get("should_mutate_behavior") is False
    )
    return _scenario_result(
        name="artifact_motive_alignment_reports_not_reflected_without_mutation",
        passed=passed,
        alignment_count=len(items),
        advisory_not_reflected_count=1 if first.get("alignment_status") == "advisory_not_reflected" else 0,
        behavior_mutation_applied=bool(first.get("behavior_mutation_applied", False)),
        should_write_memory=bool(summary.get("should_write_memory", False)),
        readback=readback,
    )


def _causal_alignment_scenario() -> dict[str, Any]:
    readback = build_embodied_interaction_readback(
        _turn(
            IMAGE_SOURCE,
            behavior_action={"primary_motive": "restore_access_continuity"},
            behavior_plan={"primary_motive": "restore_access_continuity"},
        )
    )
    items = _alignment_items(readback)
    first = _dict_or_empty(items[0] if items else {})
    passed = (
        readback.get("readiness_status") == PHASE5_READY
        and len(items) == 1
        and first.get("alignment_status") == "causally_aligned"
        and first.get("behavior_mutation_applied") is False
    )
    return _scenario_result(
        name="artifact_motive_alignment_reports_causal_alignment",
        passed=passed,
        alignment_count=len(items),
        causally_aligned_count=1 if first.get("alignment_status") == "causally_aligned" else 0,
        behavior_mutation_applied=bool(first.get("behavior_mutation_applied", False)),
        readback=readback,
    )


class _FakeSession:
    def build_evolution_summary(self, *, state_values=None):
        return {"current_turn": {}}

    def extract_final_text(self, values, *, streamed_text=""):
        data = values if isinstance(values, dict) else {}
        return str(data.get("final_text") or streamed_text or "")


class _FakeRuntimeBundle:
    thread_id = "thread-phase5"
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
    alignment_count = 0
    advisory = 0
    for payload in (turn_payload, event_payload):
        alignment = _dict_or_empty(_dict_or_empty(payload.get("embodied_interaction")).get("artifact_behavior_alignment"))
        items = [
            dict(item)
            for item in list(alignment.get("alignment_items") or [])
            if isinstance(item, dict)
        ]
        alignment_count += len(items)
        advisory += sum(1 for item in items if item.get("alignment_status") == "advisory_not_reflected")
        passed = passed and (
            len(items) == 1
            and payload["current_event"]["perception"]["behavior_alignment"]["alignment_items"][0][
                "source_ref_id"
            ]
            == IMAGE_SOURCE["source_id"]
            and payload["turn_appraisal"]["behavior_alignment_evidence"]["alignment_items"][0][
                "source_ref_id"
            ]
            == IMAGE_SOURCE["source_id"]
            and payload["interaction_carryover"]["embodied_context"]["artifact_behavior_alignment"][
                "alignment_items"
            ][0]["source_ref_id"]
            == IMAGE_SOURCE["source_id"]
        )
    return _scenario_result(
        name="backend_payload_carries_behavior_alignment",
        passed=passed,
        alignment_count=alignment_count,
        advisory_not_reflected_count=advisory,
        readback={"turn": turn_payload, "event": event_payload},
    )


def _blocked_live_scenario() -> dict[str, Any]:
    readback = build_embodied_interaction_readback(_turn(BLOCKED_LIVE_SOURCE))
    alignment = _alignment_from_readback(readback)
    items = _alignment_items(readback)
    passed = not items and alignment.get("status") == "blocked"
    return _scenario_result(
        name="blocked_live_capture_does_not_create_behavior_alignment",
        passed=passed,
        alignment_count=0,
        readback=readback,
    )


def _phase4_preserved_scenario() -> dict[str, Any]:
    readback = build_embodied_interaction_readback(_turn(IMAGE_SOURCE))
    motive = _dict_or_empty(readback.get("artifact_motive"))
    hints = [
        dict(item)
        for item in list(motive.get("motive_hints") or [])
        if isinstance(item, dict)
    ]
    first = _dict_or_empty(hints[0] if hints else {})
    authority = _dict_or_empty(first.get("authority"))
    passed = (
        readback.get("readiness_status") == PHASE5_READY
        and motive.get("readiness_status") == "artifact_motive_bridge_ready"
        and len(hints) == 1
        and first.get("source_ref_id") == IMAGE_SOURCE["source_id"]
        and first.get("primary_motive_hint") == "restore_access_continuity"
        and authority.get("behavior_mutation_allowed") is False
        and authority.get("writeback_ready") is False
    )
    return _scenario_result(
        name="phase4_motive_contract_remains_preserved",
        passed=passed,
        alignment_count=len(_alignment_items(readback)),
        readback={
            "phase4_expected_readiness": PHASE4_READY,
            "phase4_subcontract_readiness": motive.get("readiness_status"),
            "readback": readback,
        },
    )


def _authority_scenario() -> dict[str, Any]:
    readback = build_embodied_interaction_readback(
        _turn(
            TASK_SOURCE,
            behavior_action={"primary_motive": "continue_workspace_task"},
            behavior_plan={"primary_motive": "continue_workspace_task"},
        )
    )
    alignment = _alignment_from_readback(readback)
    summary = _dict_or_empty(alignment.get("alignment_summary"))
    boundary = _dict_or_empty(alignment.get("authority_boundary"))
    items = _alignment_items(readback)
    model_api_called = bool(alignment.get("model_api_called", False)) or any(
        bool(_dict_or_empty(item.get("authority")).get("model_api_called", False))
        for item in items
    )
    writeback_ready_count = int(alignment.get("writeback_ready_count") or 0) + sum(
        1 for item in items if _dict_or_empty(item.get("authority")).get("writeback_ready")
    )
    should_write_memory = bool(summary.get("should_write_memory", False))
    behavior_mutation_applied = any(
        bool(item.get("behavior_mutation_applied", False))
        or bool(_dict_or_empty(item.get("authority")).get("behavior_mutation_applied", False))
        for item in items
    )
    passed = (
        len(items) == 1
        and model_api_called is False
        and writeback_ready_count == 0
        and should_write_memory is False
        and behavior_mutation_applied is False
        and bool(boundary.get("memory_write_allowed", False)) is False
        and bool(boundary.get("behavior_mutation_allowed", False)) is False
    )
    return _scenario_result(
        name="alignment_does_not_write_memory_or_call_model_api",
        passed=passed,
        alignment_count=len(items),
        causally_aligned_count=sum(1 for item in items if item.get("alignment_status") == "causally_aligned"),
        model_api_called=model_api_called,
        writeback_ready_count=writeback_ready_count,
        should_write_memory=should_write_memory,
        behavior_mutation_applied=behavior_mutation_applied,
        readback=readback,
    )


def _scenarios() -> list[dict[str, Any]]:
    return [
        _not_reflected_scenario(),
        _causal_alignment_scenario(),
        _backend_payload_scenario(),
        _blocked_live_scenario(),
        _phase4_preserved_scenario(),
        _authority_scenario(),
    ]


def build_report(*, run_id: str) -> dict[str, Any]:
    scenarios = _scenarios()
    failed = [row["name"] for row in scenarios if row["status"] != "passed"]
    alignment_count = sum(int(row.get("alignment_count") or 0) for row in scenarios)
    advisory_not_reflected_count = sum(int(row.get("advisory_not_reflected_count") or 0) for row in scenarios)
    causally_aligned_count = sum(int(row.get("causally_aligned_count") or 0) for row in scenarios)
    model_api_called = any(bool(row.get("model_api_called", False)) for row in scenarios)
    writeback_ready_count = sum(int(row.get("writeback_ready_count") or 0) for row in scenarios)
    should_write_memory = any(bool(row.get("should_write_memory", False)) for row in scenarios)
    behavior_mutation_applied = any(bool(row.get("behavior_mutation_applied", False)) for row in scenarios)
    overall = (
        "passed"
        if (
            not failed
            and alignment_count >= 1
            and advisory_not_reflected_count >= 1
            and causally_aligned_count >= 1
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
        "readiness_status": PHASE5_READY if overall == "passed" else PHASE5_IN_PROGRESS,
        "summary": {
            "scenario_count": len(scenarios),
            "alignment_count": alignment_count,
            "advisory_not_reflected_count": advisory_not_reflected_count,
            "causally_aligned_count": causally_aligned_count,
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
        "# Embodied Interaction Runtime Phase 5 Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Overall Status: `{report.get('overall_status', 'unknown')}`",
        f"Readiness: `{report.get('readiness_status', 'unknown')}`",
        "",
        "## Summary",
        "",
        f"- Alignment count: `{summary.get('alignment_count', 0)}`",
        f"- Advisory not reflected count: `{summary.get('advisory_not_reflected_count', 0)}`",
        f"- Causally aligned count: `{summary.get('causally_aligned_count', 0)}`",
        f"- Model API called: `{summary.get('model_api_called', False)}`",
        f"- Writeback ready count: `{summary.get('writeback_ready_count', 0)}`",
        f"- Should write memory: `{summary.get('should_write_memory', False)}`",
        f"- Behavior mutation applied: `{summary.get('behavior_mutation_applied', False)}`",
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
    parser = argparse.ArgumentParser(description="Run embodied interaction runtime phase 5 audit.")
    parser.add_argument("--run-tag", default="")
    args = parser.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + (
        str(args.run_tag).strip() or str(uuid.uuid4())[:8]
    )
    report = build_report(run_id=run_id)
    json_path = REPORT_DIR / f"embodied-interaction-runtime-phase5-audit-{run_id}.json"
    md_path = REPORT_DIR / f"embodied-interaction-runtime-phase5-audit-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"[embodied-interaction-runtime-phase5] json={json_path}")
    print(f"[embodied-interaction-runtime-phase5] md={md_path}")
    print(f"[embodied-interaction-runtime-phase5] overall_status={report.get('overall_status', 'unknown')}")
    print(f"[embodied-interaction-runtime-phase5] readiness={report.get('readiness_status', 'unknown')}")
    return 0 if report.get("overall_status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

