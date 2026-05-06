from __future__ import annotations

from amadeus_thread0.graph_parts.procedural_growth import (
    build_procedural_hint,
    normalize_procedural_traces,
)


def test_completed_sandbox_trace_resurfaces_as_approval_preserving_hint():
    hint = build_procedural_hint(
        [
            {
                "trace_kind": "sandbox_execution_pattern",
                "source_proposal_id": "ap-pytest",
                "source_run_id": "run-pytest",
                "source_tool_name": "execute_workspace_command",
                "status": "completed",
                "procedure_steps": ["inspect previous run log", "rerun bounded pytest command"],
                "boundary_notes": ["requires approval before execution"],
                "confidence": 0.74,
            }
        ]
    )

    assert hint["trace_kind"] == "sandbox_execution_pattern"
    assert hint["suggested_first_step"] == "inspect previous run log"
    assert hint["source_run_id"] == "run-pytest"
    assert hint["must_request_approval"] is True
    assert hint["capability_claim"] is True
    assert hint["source_status"] == "completed"


def test_blocked_trace_resurfaces_as_boundary_note_not_capability_claim():
    hint = build_procedural_hint(
        [
            {
                "trace_kind": "blocked_boundary_pattern",
                "source_proposal_id": "ap-browser-login",
                "source_run_id": "run-browser-login",
                "source_tool_name": "browser_fill",
                "status": "blocked",
                "procedure_steps": ["preserve current page/profile"],
                "boundary_notes": ["manual browser takeover required"],
                "confidence": 0.66,
            }
        ]
    )

    assert hint["trace_kind"] == "blocked_boundary_pattern"
    assert hint["suggested_first_step"] == "manual browser takeover required"
    assert hint["must_request_approval"] is True
    assert hint["capability_claim"] is False
    assert hint["source_status"] == "blocked"


def test_blocked_takeover_hint_prefers_specific_boundary_over_generic_approval():
    hint = build_procedural_hint(
        [
            {
                "trace_kind": "blocked_boundary_pattern",
                "source_proposal_id": "ap-browser-login",
                "source_run_id": "run-browser-login",
                "source_tool_name": "browser_fill",
                "status": "blocked",
                "procedure_steps": ["preserve current page/profile"],
                "boundary_notes": [
                    "requires approval before execution",
                    "sensitive credential entry requires manual browser takeover",
                    "manual browser takeover required",
                ],
                "confidence": 0.66,
            }
        ]
    )

    assert "takeover" in hint["boundary_note"]
    assert "takeover" in hint["suggested_first_step"]
    assert hint["must_request_approval"] is True


def test_low_confidence_or_empty_traces_do_not_surface():
    assert build_procedural_hint([]) == {}
    assert (
        build_procedural_hint(
            [
                {
                    "trace_kind": "workspace_procedure",
                    "source_proposal_id": "ap-low-confidence",
                    "source_tool_name": "write_workspace_file",
                    "status": "completed",
                    "procedure_steps": ["write file"],
                    "confidence": 0.19,
                }
            ]
        )
        == {}
    )


def test_duplicate_trace_ids_dedupe_deterministically_and_keep_first_trace():
    traces = normalize_procedural_traces(
        [
            {
                "trace_id": "proc_dup",
                "trace_kind": "sandbox_execution_pattern",
                "source_proposal_id": "ap-first",
                "source_run_id": "run-first",
                "source_tool_name": "execute_workspace_command",
                "status": "completed",
                "procedure_steps": ["first step"],
                "boundary_notes": ["requires approval before execution"],
                "confidence": 0.81,
            },
            {
                "trace_id": "proc_dup",
                "trace_kind": "sandbox_execution_pattern",
                "source_proposal_id": "ap-second",
                "source_run_id": "run-second",
                "source_tool_name": "execute_workspace_command",
                "status": "completed",
                "procedure_steps": ["second step"],
                "confidence": 0.99,
            },
        ]
    )

    assert len(traces) == 1
    assert traces[0]["source_proposal_id"] == "ap-first"
    assert build_procedural_hint(traces)["source_run_id"] == "run-first"
