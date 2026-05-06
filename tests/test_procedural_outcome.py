from __future__ import annotations

from amadeus_thread0.graph_parts.procedural_outcome import (
    calibrate_procedural_traces_with_outcomes,
    derive_procedural_outcomes_from_action_packets,
    normalize_procedural_outcome,
    summarize_procedural_outcomes,
)


def _planning() -> dict[str, object]:
    return {
        "planning_bias": True,
        "bias_kind": "sandbox_execute",
        "trace_id": "proc_pytest_source",
        "trace_kind": "sandbox_execution_pattern",
        "source_run_id": "run-source",
        "source_tool_name": "execute_workspace_command",
        "suggested_capability_family": "sandbox",
        "suggested_pattern": "pytest",
        "must_request_approval": True,
        "requires_approval": True,
        "capability_claim": True,
        "confidence": 0.7,
    }


def _sandbox_packet(*, status: str = "completed", exit_code: int = 0) -> dict[str, object]:
    return {
        "proposal_id": "ap-outcome-pytest",
        "origin": "motive_goal",
        "intent": "sandbox:execute_workspace_command",
        "status": status,
        "risk": "external_mutation",
        "requires_approval": True,
        "tool_name": "execute_workspace_command",
        "result_summary": "pytest passed" if exit_code == 0 else "pytest failed",
        "tool_args": {
            "procedural_planning": _planning(),
        },
        "execution_spec": {
            "executor": "pytest",
            "profile": "pytest",
            "argv": ["pytest"],
            "cwd": "E:/repo/amadeus-thread0",
            "allowed_roots": ["E:/repo/amadeus-thread0"],
        },
        "execution_result": {
            "run_id": "run-outcome-pytest",
            "status": "completed" if exit_code == 0 else "failed",
            "exit_code": exit_code,
            "stdout_log_ref": "E:/repo/.amadeus/sandbox-runs/run-outcome-pytest/stdout.txt",
            "stderr_log_ref": "E:/repo/.amadeus/sandbox-runs/run-outcome-pytest/stderr.txt",
            "error_summary": "" if exit_code == 0 else "process exited with code 2",
        },
    }


def test_normalize_procedural_outcome_cleans_shape_and_generates_stable_id():
    raw = {
        "source_trace_id": " proc_pytest_source ",
        "source_proposal_id": " ap-outcome-pytest ",
        "source_run_id": " run-outcome-pytest ",
        "planning_bias_kind": " Sandbox_Execute ",
        "source_tool_name": " Execute_Workspace_Command ",
        "attempt_status": " COMPLETED ",
        "outcome_kind": " CONFIRMED_SUCCESS ",
        "confidence_delta": 2,
        "reuse_allowed": True,
        "boundary_reinforced": False,
        "recovery_hint": " reuse the bounded pytest profile ",
        "evidence_refs": [" run-outcome-pytest ", "", " run-outcome-pytest "],
    }

    first = normalize_procedural_outcome(raw)
    second = normalize_procedural_outcome({**raw, "outcome_id": ""})

    assert first["outcome_id"].startswith("proc_out_")
    assert first["outcome_id"] == second["outcome_id"]
    assert first["source_trace_id"] == "proc_pytest_source"
    assert first["planning_bias_kind"] == "sandbox_execute"
    assert first["source_tool_name"] == "execute_workspace_command"
    assert first["attempt_status"] == "completed"
    assert first["outcome_kind"] == "confirmed_success"
    assert first["confidence_delta"] == 1.0
    assert first["reuse_allowed"] is True
    assert first["boundary_reinforced"] is False
    assert first["evidence_refs"] == ["run-outcome-pytest"]


def test_completed_sandbox_packet_derives_confirmed_success_outcome():
    outcomes = derive_procedural_outcomes_from_action_packets([_sandbox_packet()])

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome["source_trace_id"] == "proc_pytest_source"
    assert outcome["source_proposal_id"] == "ap-outcome-pytest"
    assert outcome["source_run_id"] == "run-outcome-pytest"
    assert outcome["planning_bias_kind"] == "sandbox_execute"
    assert outcome["attempt_status"] == "completed"
    assert outcome["outcome_kind"] == "confirmed_success"
    assert outcome["confidence_delta"] == 0.08
    assert outcome["reuse_allowed"] is True
    assert outcome["boundary_reinforced"] is False
    assert "stdout.txt" in outcome["evidence_refs"][1]


def test_failed_sandbox_execution_derives_failed_execution_outcome():
    outcomes = derive_procedural_outcomes_from_action_packets(
        [_sandbox_packet(status="completed", exit_code=2)]
    )

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome["outcome_kind"] == "failed_execution"
    assert outcome["attempt_status"] == "completed"
    assert outcome["confidence_delta"] == -0.12
    assert outcome["reuse_allowed"] is False
    assert outcome["boundary_reinforced"] is False
    assert "process exited with code 2" in outcome["recovery_hint"]


def test_pending_packet_derives_no_executed_attempt_without_reuse():
    outcomes = derive_procedural_outcomes_from_action_packets(
        [
            {
                "proposal_id": "ap-awaiting",
                "origin": "motive_goal",
                "intent": "sandbox:execute_workspace_command",
                "status": "awaiting_approval",
                "risk": "external_mutation",
                "requires_approval": True,
                "tool_name": "execute_workspace_command",
                "tool_args": {"procedural_planning": _planning()},
            }
        ]
    )

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome["outcome_kind"] == "no_executed_attempt"
    assert outcome["attempt_status"] == "awaiting_approval"
    assert outcome["confidence_delta"] == 0.0
    assert outcome["reuse_allowed"] is False
    assert outcome["boundary_reinforced"] is False


def test_manual_takeover_derives_manual_boundary_outcome():
    outcomes = derive_procedural_outcomes_from_action_packets(
        [
            {
                "proposal_id": "ap-browser-manual",
                "origin": "motive_goal",
                "intent": "browser:fill",
                "status": "blocked",
                "risk": "external_mutation",
                "requires_approval": True,
                "tool_name": "browser_fill",
                "block_reason": "sensitive credential entry requires manual browser takeover",
                "browser_execution_preview": {"operation": "fill", "requires_manual_takeover": True},
                "browser_execution_result": {
                    "run_id": "browser-run-manual",
                    "status": "blocked",
                    "last_action_status": "manual_takeover_required",
                    "manual_takeover_required": True,
                },
            }
        ],
        planning_bias={
            "bias_kind": "browser_manual_takeover",
            "trace_id": "proc_browser_manual",
        },
    )

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome["source_trace_id"] == "proc_browser_manual"
    assert outcome["source_run_id"] == "browser-run-manual"
    assert outcome["planning_bias_kind"] == "browser_manual_takeover"
    assert outcome["outcome_kind"] == "manual_takeover_required"
    assert outcome["confidence_delta"] == 0.0
    assert outcome["reuse_allowed"] is False
    assert outcome["boundary_reinforced"] is True
    assert "manual browser takeover" in outcome["recovery_hint"]


def test_calibration_adjusts_trace_confidence_and_preserves_outcome_readback():
    traces = [
        {
            "trace_id": "proc_pytest_source",
            "trace_kind": "sandbox_execution_pattern",
            "source_proposal_id": "ap-outcome-pytest",
            "source_run_id": "run-source",
            "source_tool_name": "execute_workspace_command",
            "status": "completed",
            "procedure_steps": ["inspect cwd", "run bounded command"],
            "boundary_notes": ["requires approval before execution"],
            "confidence": 0.7,
        }
    ]
    outcomes = derive_procedural_outcomes_from_action_packets([_sandbox_packet()])

    calibrated = calibrate_procedural_traces_with_outcomes(traces, outcomes)

    assert len(calibrated) == 1
    assert calibrated[0]["confidence"] == 0.78
    assert calibrated[0]["last_outcome_kind"] == "confirmed_success"
    assert calibrated[0]["reuse_allowed"] is True
    assert calibrated[0]["boundary_reinforced"] is False
    assert calibrated[0]["outcome_refs"] == [outcomes[0]["outcome_id"]]


def test_summary_reports_last_outcome_and_total_delta():
    outcomes = derive_procedural_outcomes_from_action_packets([_sandbox_packet()])

    summary = summarize_procedural_outcomes(outcomes)

    assert summary["procedural_outcome"] is True
    assert summary["last_outcome_kind"] == "confirmed_success"
    assert summary["source_trace_id"] == "proc_pytest_source"
    assert summary["source_run_id"] == "run-outcome-pytest"
    assert summary["confidence_delta_total"] == 0.08
    assert summary["reuse_allowed"] is True
    assert summary["boundary_reinforced"] is False
