from __future__ import annotations

from amadeus_thread0.graph_parts.procedural_growth import (
    build_procedural_hint,
    extract_procedural_traces_from_action_packets,
    normalize_procedural_trace,
    normalize_procedural_traces,
)


def test_normalize_procedural_trace_cleans_shape_and_generates_stable_id():
    raw = {
        "trace_kind": "sandbox_execution_pattern",
        "source_proposal_id": " ap-sandbox-1 ",
        "source_run_id": " run-1 ",
        "source_tool_name": " Execute_Workspace_Command ",
        "status": "COMPLETED",
        "preconditions": [" workspace_root available ", "", "approval granted"],
        "procedure_steps": [" inspect cwd ", "run bounded command", "read stdout"],
        "result_summary": " pytest passed " * 30,
        "reuse_conditions": ["similar workspace command"],
        "boundary_notes": ["requires approval before execution"],
        "confidence": 2.5,
    }

    first = normalize_procedural_trace(raw)
    second = normalize_procedural_trace({**raw, "trace_id": ""})

    assert first["trace_id"].startswith("proc_")
    assert first["trace_id"] == second["trace_id"]
    assert first["trace_kind"] == "sandbox_execution_pattern"
    assert first["source_proposal_id"] == "ap-sandbox-1"
    assert first["source_tool_name"] == "execute_workspace_command"
    assert first["status"] == "completed"
    assert first["preconditions"] == ["workspace_root available", "approval granted"]
    assert first["confidence"] == 1.0
    assert len(first["result_summary"]) <= 220


def test_completed_sandbox_packet_creates_sandbox_execution_pattern():
    traces = extract_procedural_traces_from_action_packets(
        [
            {
                "proposal_id": "ap-sandbox-pytest",
                "origin": "motive_goal",
                "intent": "sandbox:execute_workspace_command",
                "status": "completed",
                "risk": "external_mutation",
                "requires_approval": True,
                "tool_name": "execute_workspace_command",
                "result_summary": "pytest passed",
                "execution_spec": {
                    "profile": "pytest",
                    "argv": ["pytest", "-q", "tests/test_demo.py"],
                    "cwd": "E:/repo/amadeus-thread0",
                    "allowed_roots": ["E:/repo/amadeus-thread0"],
                },
                "execution_result": {
                    "run_id": "run-pytest-1",
                    "status": "completed",
                    "exit_code": 0,
                    "stdout_log_ref": "E:/repo/.amadeus/sandbox-runs/run-pytest-1/stdout.txt",
                },
            }
        ]
    )

    assert len(traces) == 1
    trace = traces[0]
    assert trace["trace_kind"] == "sandbox_execution_pattern"
    assert trace["status"] == "completed"
    assert trace["source_proposal_id"] == "ap-sandbox-pytest"
    assert trace["source_run_id"] == "run-pytest-1"
    assert trace["source_tool_name"] == "execute_workspace_command"
    assert "approval granted" in trace["preconditions"]
    assert "requires approval before execution" in trace["boundary_notes"]


def test_blocked_sandbox_packet_creates_boundary_trace_not_completed_capability():
    traces = extract_procedural_traces_from_action_packets(
        [
            {
                "proposal_id": "ap-sandbox-blocked",
                "intent": "sandbox:execute_workspace_command",
                "status": "blocked",
                "risk": "external_mutation",
                "requires_approval": True,
                "tool_name": "execute_workspace_command",
                "block_reason": "process exited with code 3",
                "execution_spec": {"profile": "pytest", "argv": ["pytest", "-q"]},
                "execution_result": {
                    "run_id": "run-blocked-1",
                    "status": "blocked",
                    "exit_code": 3,
                    "error_summary": "process exited with code 3",
                },
            }
        ]
    )

    assert len(traces) == 1
    trace = traces[0]
    assert trace["trace_kind"] == "blocked_boundary_pattern"
    assert trace["status"] == "blocked"
    assert trace["source_run_id"] == "run-blocked-1"
    assert "process exited with code 3" in trace["boundary_notes"]
    assert trace.get("capability_family", "") == ""


def test_pending_rejected_or_approved_only_packets_do_not_create_completed_traces():
    traces = extract_procedural_traces_from_action_packets(
        [
            {
                "proposal_id": "ap-pending",
                "intent": "sandbox:execute_workspace_command",
                "status": "awaiting_approval",
                "tool_name": "execute_workspace_command",
            },
            {
                "proposal_id": "ap-approved",
                "intent": "sandbox:execute_workspace_command",
                "status": "approved",
                "tool_name": "execute_workspace_command",
            },
            {
                "proposal_id": "ap-rejected",
                "intent": "browser:click",
                "status": "rejected",
                "tool_name": "browser_click",
            },
        ]
    )

    assert traces == []


def test_completed_skill_usage_packet_creates_skill_usage_pattern():
    traces = extract_procedural_traces_from_action_packets(
        [
            {
                "proposal_id": "ap-skill-use",
                "intent": "tool:search_web",
                "status": "completed",
                "risk": "read",
                "tool_name": "search_web",
                "result_summary": "searched source material",
                "skill_effects": [
                    {
                        "skill_id": "source-ref-anchor-review",
                        "name": "Source Ref Anchor Review",
                        "status": "completed",
                        "operation": "use",
                        "use_kind": "source_ref_continuity",
                        "tool_name": "search_web",
                    }
                ],
            }
        ]
    )

    assert len(traces) == 1
    trace = traces[0]
    assert trace["trace_kind"] == "skill_usage_pattern"
    assert trace["status"] == "completed"
    assert trace["source_tool_name"] == "search_web"
    assert trace["reuse_conditions"] == ["similar skill-supported task"]


def test_browser_manual_takeover_packet_creates_boundary_pattern():
    traces = extract_procedural_traces_from_action_packets(
        [
            {
                "proposal_id": "ap-browser-takeover",
                "intent": "browser:fill",
                "status": "blocked",
                "risk": "external_mutation",
                "requires_approval": True,
                "tool_name": "browser_fill",
                "block_reason": "sensitive credential entry requires manual browser takeover",
                "browser_execution_preview": {
                    "operation": "fill",
                    "profile_id": "thread-browser",
                    "requires_manual_takeover": True,
                },
                "browser_execution_result": {
                    "run_id": "browser-run-1",
                    "status": "blocked",
                    "profile_id": "thread-browser",
                    "page_id": "page-1",
                    "last_action_status": "manual_takeover_required",
                    "manual_takeover_required": True,
                },
            }
        ]
    )

    assert len(traces) == 1
    trace = traces[0]
    assert trace["trace_kind"] == "blocked_boundary_pattern"
    assert trace["status"] == "blocked"
    assert trace["source_run_id"] == "browser-run-1"
    assert "manual browser takeover required" in trace["boundary_notes"]


def test_normalize_procedural_traces_dedupes_and_hint_keeps_approval_boundary():
    traces = normalize_procedural_traces(
        [
            {
                "trace_id": "proc_same",
                "trace_kind": "sandbox_execution_pattern",
                "source_proposal_id": "ap-1",
                "source_run_id": "run-1",
                "source_tool_name": "execute_workspace_command",
                "status": "completed",
                "procedure_steps": ["run bounded command"],
                "boundary_notes": ["requires approval before execution"],
                "confidence": 0.7,
            },
            {
                "trace_id": "proc_same",
                "trace_kind": "sandbox_execution_pattern",
                "source_proposal_id": "ap-duplicate",
                "status": "completed",
                "confidence": 0.4,
            },
        ]
    )

    assert len(traces) == 1
    hint = build_procedural_hint(traces)
    assert hint["trace_id"] == "proc_same"
    assert hint["trace_kind"] == "sandbox_execution_pattern"
    assert hint["source_run_id"] == "run-1"
    assert hint["must_request_approval"] is True
    assert "approval" in hint["boundary_note"]
