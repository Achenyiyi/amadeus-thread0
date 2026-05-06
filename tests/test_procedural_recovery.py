from __future__ import annotations

from amadeus_thread0.graph_parts.procedural_recovery import (
    apply_recovery_markers_to_traces,
    derive_procedural_recoveries_from_outcomes,
    normalize_procedural_recovery,
    summarize_procedural_recoveries,
)


def _outcome(**overrides):
    row = {
        "outcome_id": "proc_out_failed",
        "source_trace_id": "proc_trace_failed",
        "source_proposal_id": "ap-failed",
        "source_run_id": "run-failed",
        "planning_bias_kind": "sandbox_execute",
        "source_tool_name": "execute_workspace_command",
        "attempt_status": "completed",
        "outcome_kind": "failed_execution",
        "confidence_delta": -0.12,
        "reuse_allowed": False,
        "boundary_reinforced": False,
        "recovery_hint": "process exited with code 2",
        "evidence_refs": [
            "run-failed",
            "E:/repo/.amadeus/sandbox-runs/run-failed/stdout.txt",
            "E:/repo/.amadeus/sandbox-runs/run-failed/stderr.txt",
        ],
    }
    row.update(overrides)
    return row


def test_normalize_procedural_recovery_cleans_shape_and_generates_stable_id():
    raw = {
        "source_outcome_id": " proc_out_failed ",
        "source_trace_id": " proc_trace_failed ",
        "source_proposal_id": " ap-failed ",
        "source_run_id": " run-failed ",
        "recovery_kind": " Inspect_Failure_Artifact ",
        "status": " Suggested ",
        "safe_to_reuse": True,
        "requires_approval": False,
        "allowed_bias_kind": " Workspace_Guidance ",
        "suggested_next_step": " inspect stderr before reusing pytest ",
        "must_not_repeat": ["pip install", "", "pip install"],
        "evidence_refs": [" run-failed ", " run-failed ", " stderr.txt "],
    }

    first = normalize_procedural_recovery(raw)
    second = normalize_procedural_recovery({**raw, "recovery_id": ""})

    assert first["recovery_id"].startswith("proc_rec_")
    assert first["recovery_id"] == second["recovery_id"]
    assert first["source_outcome_id"] == "proc_out_failed"
    assert first["source_trace_id"] == "proc_trace_failed"
    assert first["source_proposal_id"] == "ap-failed"
    assert first["source_run_id"] == "run-failed"
    assert first["recovery_kind"] == "inspect_failure_artifact"
    assert first["status"] == "suggested"
    assert first["safe_to_reuse"] is True
    assert first["requires_approval"] is False
    assert first["allowed_bias_kind"] == "workspace_guidance"
    assert first["must_not_repeat"] == ["pip install"]
    assert first["evidence_refs"] == ["run-failed", "stderr.txt"]


def test_failed_execution_outcome_builds_failure_artifact_recovery():
    recoveries = derive_procedural_recoveries_from_outcomes([_outcome()])

    assert len(recoveries) == 1
    recovery = recoveries[0]
    assert recovery["source_outcome_id"] == "proc_out_failed"
    assert recovery["source_trace_id"] == "proc_trace_failed"
    assert recovery["source_run_id"] == "run-failed"
    assert recovery["recovery_kind"] == "inspect_failure_artifact"
    assert recovery["status"] == "suggested"
    assert recovery["safe_to_reuse"] is False
    assert recovery["requires_approval"] is False
    assert recovery["allowed_bias_kind"] == "workspace_guidance"
    assert "stderr" in recovery["suggested_next_step"]
    assert "package install" in recovery["must_not_repeat"]
    assert "shell wrapper" in recovery["must_not_repeat"]
    assert "stderr.txt" in recovery["evidence_refs"][2]


def test_blocked_boundary_outcome_builds_boundary_only_recovery():
    recoveries = derive_procedural_recoveries_from_outcomes(
        [
            _outcome(
                outcome_id="proc_out_blocked",
                outcome_kind="blocked_boundary_reinforced",
                attempt_status="blocked",
                boundary_reinforced=True,
                recovery_hint="package install is blocked in the sandbox",
            )
        ]
    )

    recovery = recoveries[0]
    assert recovery["recovery_kind"] == "avoid_blocked_boundary"
    assert recovery["allowed_bias_kind"] == "boundary_only"
    assert recovery["safe_to_reuse"] is False
    assert recovery["requires_approval"] is True
    assert "blocked action" in recovery["suggested_next_step"]
    assert "package install is blocked" in recovery["must_not_repeat"]


def test_manual_takeover_outcome_preserves_manual_boundary_without_browser_mutation():
    recoveries = derive_procedural_recoveries_from_outcomes(
        [
            _outcome(
                outcome_id="proc_out_manual",
                source_trace_id="proc_trace_manual",
                source_tool_name="browser_fill",
                planning_bias_kind="browser_manual_takeover",
                outcome_kind="manual_takeover_required",
                attempt_status="blocked",
                boundary_reinforced=True,
                recovery_hint="manual browser takeover is still required before continuing",
            )
        ]
    )

    recovery = recoveries[0]
    assert recovery["recovery_kind"] == "preserve_manual_takeover"
    assert recovery["allowed_bias_kind"] == "browser_manual_takeover"
    assert recovery["safe_to_reuse"] is False
    assert recovery["requires_approval"] is True
    assert "manual browser takeover" in recovery["suggested_next_step"]
    assert "browser mutation" in recovery["must_not_repeat"]


def test_stale_context_outcome_builds_workspace_refresh_recovery():
    recoveries = derive_procedural_recoveries_from_outcomes(
        [
            _outcome(
                outcome_id="proc_out_stale",
                outcome_kind="stale_or_mismatched_context",
                attempt_status="completed",
                recovery_hint="current context no longer matches this procedural trace",
            )
        ]
    )

    recovery = recoveries[0]
    assert recovery["recovery_kind"] == "refresh_workspace_context"
    assert recovery["allowed_bias_kind"] == "workspace_guidance"
    assert recovery["safe_to_reuse"] is False
    assert recovery["requires_approval"] is False
    assert "refresh" in recovery["suggested_next_step"]


def test_no_executed_attempt_stays_hold_without_recovery_claim():
    recoveries = derive_procedural_recoveries_from_outcomes(
        [
            _outcome(
                outcome_id="proc_out_hold",
                outcome_kind="no_executed_attempt",
                attempt_status="awaiting_approval",
                recovery_hint="attempt did not execute; keep it as an unfulfilled intention",
            )
        ]
    )

    recovery = recoveries[0]
    assert recovery["recovery_kind"] == "hold_for_approval"
    assert recovery["allowed_bias_kind"] == "hold"
    assert recovery["safe_to_reuse"] is False
    assert recovery["requires_approval"] is True
    assert "unfulfilled intention" in recovery["suggested_next_step"]


def test_confirmed_success_gets_no_recovery_needed_marker():
    recoveries = derive_procedural_recoveries_from_outcomes(
        [
            _outcome(
                outcome_id="proc_out_success",
                outcome_kind="confirmed_success",
                confidence_delta=0.08,
                reuse_allowed=True,
                recovery_hint="",
            )
        ],
        include_noop=True,
    )

    recovery = recoveries[0]
    assert recovery["recovery_kind"] == "no_recovery_needed"
    assert recovery["allowed_bias_kind"] == "workspace_guidance"
    assert recovery["safe_to_reuse"] is True
    assert recovery["requires_approval"] is False


def test_summary_reports_latest_recovery_and_boundary_status():
    recoveries = derive_procedural_recoveries_from_outcomes(
        [
            _outcome(),
            _outcome(
                outcome_id="proc_out_manual",
                source_trace_id="proc_trace_manual",
                source_run_id="run-manual",
                outcome_kind="manual_takeover_required",
                attempt_status="blocked",
                boundary_reinforced=True,
                recovery_hint="manual browser takeover is still required before continuing",
            ),
        ]
    )

    summary = summarize_procedural_recoveries(recoveries)

    assert summary["procedural_recovery"] is True
    assert summary["last_recovery_kind"] == "preserve_manual_takeover"
    assert summary["source_trace_id"] == "proc_trace_manual"
    assert summary["source_run_id"] == "run-manual"
    assert summary["safe_to_reuse"] is False
    assert summary["requires_approval"] is True
    assert summary["allowed_bias_kind"] == "browser_manual_takeover"
    assert len(summary["recoveries"]) == 2


def test_apply_recovery_markers_to_traces_marks_matching_failed_trace_as_guidance_only():
    traces = [
        {
            "trace_id": "proc_trace_failed",
            "trace_kind": "sandbox_execution_pattern",
            "source_proposal_id": "ap-failed",
            "source_run_id": "run-prior",
            "source_tool_name": "execute_workspace_command",
            "status": "completed",
            "procedure_steps": ["inspect cwd", "run bounded command"],
            "boundary_notes": ["requires approval before execution"],
            "confidence": 0.74,
        }
    ]
    recoveries = derive_procedural_recoveries_from_outcomes([_outcome()])

    marked = apply_recovery_markers_to_traces(traces, recoveries)

    assert marked[0]["trace_id"] == "proc_trace_failed"
    assert marked[0]["recovery_required"] is True
    assert marked[0]["recovery_kind"] == "inspect_failure_artifact"
    assert marked[0]["recovery_allowed_bias_kind"] == "workspace_guidance"
    assert marked[0]["recovery_refs"] == [recoveries[0]["recovery_id"]]
