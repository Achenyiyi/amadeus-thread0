from __future__ import annotations

from amadeus_thread0.runtime.final_state import (
    resolve_digital_body_consequence,
    resolve_interaction_carryover,
)


def _sandbox_packet(*, proposal_id: str = "ap-sandbox-writeback", status: str = "completed") -> dict[str, object]:
    exit_code = 0 if status == "completed" else 3
    return {
        "proposal_id": proposal_id,
        "origin": "motive_goal",
        "intent": "sandbox:execute_workspace_command",
        "status": status,
        "risk": "external_mutation",
        "requires_approval": True,
        "tool_name": "execute_workspace_command",
        "result_summary": "pytest passed" if status == "completed" else "pytest failed",
        "execution_spec": {
            "executor": "pytest",
            "profile": "pytest",
            "runner_kind": "docker_isolated_runner",
            "isolation_level": "docker_local_isolated",
            "image_ref": "amadeus-thread0/sandbox-phase2:py312",
            "network_policy": "none",
            "workspace_root_kind": "attached_repo_root",
            "argv": ["pytest", "-q", "tests/test_demo.py"],
            "cwd": "E:/repo/amadeus-thread0",
            "allowed_roots": ["E:/repo/amadeus-thread0"],
        },
        "execution_preview": {
            "runner_kind": "docker_isolated_runner",
            "isolation_level": "docker_local_isolated",
            "image_ref": "amadeus-thread0/sandbox-phase2:py312",
            "network_policy": "none",
            "workspace_root_kind": "attached_repo_root",
            "argv": ["pytest", "-q", "tests/test_demo.py"],
            "cwd": "E:/repo/amadeus-thread0",
            "allowed_roots": ["E:/repo/amadeus-thread0"],
        },
        "execution_result": {
            "run_id": f"{proposal_id}-run",
            "status": status,
            "exit_code": exit_code,
            "stdout_log_ref": f"E:/repo/.amadeus/sandbox-runs/{proposal_id}/stdout.txt",
            "stderr_log_ref": f"E:/repo/.amadeus/sandbox-runs/{proposal_id}/stderr.txt",
            "error_summary": "" if exit_code == 0 else "process exited with code 3",
        },
    }


def _body() -> dict[str, object]:
    return {
        "active_surface": "tooling",
        "perception_channels": ["dialogue", "filesystem"],
        "action_channels": ["language", "structured_action", "tooling"],
        "world_surfaces": ["filesystem", "sandbox"],
        "access_state": {
            "mode": "tool_enabled",
            "filesystem_state": "writable",
            "sandbox_mode": "restricted",
            "sandbox_state": {
                "availability": "restricted",
                "allowed_roots": ["E:/repo/amadeus-thread0"],
                "execution_policy": "approval_required",
                "runner_kind": "docker_isolated_runner",
                "isolation_level": "docker_local_isolated",
                "image_ref": "amadeus-thread0/sandbox-phase2:py312",
                "network_policy": "none",
                "workspace_root_kind": "attached_repo_root",
            },
        },
        "resource_state": {
            "completed_packet_count": 1,
            "artifact_continuity": "attached",
            "active_artifact_kind": "workspace",
            "active_artifact_ref": "E:/repo/amadeus-thread0",
            "active_artifact_label": "amadeus-thread0",
            "artifact_carrier": "filesystem",
            "workspace_root": "E:/repo/amadeus-thread0",
        },
    }


def test_completed_action_packet_enriches_consequence_with_procedural_traces():
    consequence = resolve_digital_body_consequence(
        digital_body_state=_body(),
        action_packets=[_sandbox_packet()],
    )

    assert consequence["kind"] == "sandbox_execution_completed"
    assert consequence["procedural_growth"] is True
    continuity = consequence["procedural_continuity"]
    assert continuity["capability_family"] == "sandbox"
    assert continuity["pattern"] == "pytest"
    assert continuity["identity_safe"] is True
    assert continuity["traces"][0]["trace_kind"] == "sandbox_execution_pattern"
    assert continuity["traces"][0]["source_run_id"] == "ap-sandbox-writeback-run"
    assert consequence["procedural_hint"]["trace_kind"] == "sandbox_execution_pattern"
    assert consequence["procedural_hint"]["must_request_approval"] is True


def test_completed_planning_packet_enriches_consequence_with_procedural_outcome():
    packet = _sandbox_packet(proposal_id="ap-phase3-writeback")
    packet["tool_args"] = {
        "procedural_planning": {
            "planning_bias": True,
            "bias_kind": "sandbox_execute",
            "trace_id": "proc_phase3_writeback",
            "trace_kind": "sandbox_execution_pattern",
            "source_run_id": "run-prior-phase3",
            "source_tool_name": "execute_workspace_command",
            "suggested_capability_family": "sandbox",
            "suggested_pattern": "pytest",
            "suggested_executor": "pytest",
            "suggested_argv": ["pytest"],
            "must_request_approval": True,
            "requires_approval": True,
            "capability_claim": True,
            "confidence": 0.7,
        }
    }
    consequence = resolve_digital_body_consequence(
        digital_body_state=_body(),
        action_packets=[packet],
    )

    assert consequence["procedural_growth"] is True
    assert consequence["procedural_outcome_summary"]["procedural_outcome"] is True
    assert consequence["procedural_outcome_summary"]["last_outcome_kind"] == "confirmed_success"
    assert consequence["procedural_outcomes"][0]["source_trace_id"] == "proc_phase3_writeback"
    assert consequence["procedural_outcomes"][0]["planning_bias_kind"] == "sandbox_execute"
    trace = consequence["procedural_continuity"]["traces"][0]
    assert trace["trace_id"] == "proc_phase3_writeback"
    assert trace["last_outcome_kind"] == "confirmed_success"
    assert trace["reuse_allowed"] is True
    assert trace["confidence"] > 0.74


def test_failed_planning_packet_enriches_consequence_with_procedural_recovery():
    packet = _sandbox_packet(proposal_id="ap-phase4-failed")
    packet["result_summary"] = "pytest failed"
    packet["execution_result"] = {
        **packet["execution_result"],
        "run_id": "run-phase4-failed",
        "status": "failed",
        "exit_code": 2,
        "stderr_log_ref": "E:/repo/.amadeus/sandbox-runs/run-phase4-failed/stderr.txt",
        "error_summary": "process exited with code 2",
    }
    packet["tool_args"] = {
        "procedural_planning": {
            "planning_bias": True,
            "bias_kind": "sandbox_execute",
            "trace_id": "proc_phase4_failed",
            "trace_kind": "sandbox_execution_pattern",
            "source_run_id": "run-prior-phase4",
            "source_tool_name": "execute_workspace_command",
            "suggested_capability_family": "sandbox",
            "suggested_pattern": "pytest",
            "suggested_executor": "pytest",
            "suggested_argv": ["pytest"],
            "must_request_approval": True,
            "requires_approval": True,
            "capability_claim": True,
            "confidence": 0.7,
        }
    }

    consequence = resolve_digital_body_consequence(
        digital_body_state=_body(),
        action_packets=[packet],
    )

    assert consequence["procedural_outcome_summary"]["last_outcome_kind"] == "failed_execution"
    assert consequence["procedural_recovery_summary"]["procedural_recovery"] is True
    assert consequence["procedural_recovery_summary"]["last_recovery_kind"] == "inspect_failure_artifact"
    assert consequence["procedural_recoveries"][0]["allowed_bias_kind"] == "workspace_guidance"
    assert consequence["procedural_recoveries"][0]["safe_to_reuse"] is False
    trace = consequence["procedural_continuity"]["traces"][0]
    assert trace["trace_id"] == "proc_phase4_failed"
    assert trace["recovery_required"] is True
    assert trace["recovery_kind"] == "inspect_failure_artifact"
    assert trace["recovery_allowed_bias_kind"] == "workspace_guidance"
    assert trace["reuse_allowed"] is False


def test_blocked_packet_creates_boundary_trace_without_completed_capability_fact():
    consequence = resolve_digital_body_consequence(
        digital_body_state={
            **_body(),
            "resource_state": {
                **_body()["resource_state"],
                "completed_packet_count": 0,
                "blocked_packet_count": 1,
            },
        },
        action_packets=[_sandbox_packet(proposal_id="ap-sandbox-blocked-writeback", status="blocked")],
    )

    assert consequence["kind"] == "sandbox_execution_blocked"
    assert consequence["procedural_growth"] is False
    continuity = consequence["procedural_continuity"]
    assert "capability_family" not in continuity
    assert continuity["traces"][0]["trace_kind"] == "blocked_boundary_pattern"
    assert continuity["traces"][0]["status"] == "blocked"
    assert "process exited with code 3" in continuity["traces"][0]["boundary_notes"]
    assert consequence["procedural_hint"]["trace_kind"] == "blocked_boundary_pattern"


def test_raw_skill_effects_on_final_packet_survive_final_state_enrichment():
    consequence = resolve_digital_body_consequence(
        digital_body_state={
            "active_surface": "tooling",
            "world_surfaces": ["source_ref"],
            "access_state": {"mode": "tool_enabled"},
            "resource_state": {
                "completed_packet_count": 1,
                "artifact_carrier": "source_ref",
                "active_artifact_kind": "search_result",
                "active_artifact_ref": "https://docs.example/proc",
                "active_artifact_label": "Procedural Docs",
            },
        },
        action_packets=[
            {
                "proposal_id": "ap-skill-writeback",
                "origin": "motive_goal",
                "intent": "tool:search_web",
                "status": "completed",
                "risk": "read",
                "requires_approval": False,
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
        ],
    )

    assert consequence["procedural_growth"] is True
    assert consequence["procedural_traces"][0]["trace_kind"] == "skill_usage_pattern"
    assert consequence["procedural_traces"][0]["source_tool_name"] == "search_web"
    assert consequence["procedural_hint"]["capability_claim"] is True


def test_interaction_carryover_preserves_embodied_procedural_traces():
    carryover = resolve_interaction_carryover(
        interaction_carryover={
            "source": "reconsolidation",
            "carryover_mode": "continue_work_surface",
            "strength": 0.42,
            "embodied_context": {
                "kind": "sandbox_execution_completed",
                "procedural_growth": True,
                "procedural_continuity": {
                    "capability_family": "sandbox",
                    "pattern": "pytest",
                    "identity_safe": True,
                    "confidence": 0.72,
                    "traces": [
                        {
                            "trace_kind": "sandbox_execution_pattern",
                            "source_proposal_id": "ap-sandbox-carryover",
                            "source_run_id": "run-carryover",
                            "source_tool_name": "execute_workspace_command",
                            "status": "completed",
                            "procedure_steps": ["inspect cwd", "run bounded command"],
                            "boundary_notes": ["requires approval before execution"],
                            "confidence": 0.72,
                        }
                    ],
                },
            },
        }
    )

    embodied = carryover["embodied_context"]
    assert embodied["procedural_growth"] is True
    assert embodied["procedural_continuity"]["traces"][0]["source_run_id"] == "run-carryover"
    assert embodied["procedural_traces"][0]["source_run_id"] == "run-carryover"
    assert embodied["procedural_hint"]["must_request_approval"] is True


def test_frozen_reconsolidation_procedural_trace_wins_over_stale_live_packet():
    consequence = resolve_digital_body_consequence(
        digital_body_state=_body(),
        action_packets=[_sandbox_packet(proposal_id="ap-live-stale")],
        reconsolidation_snapshot={
            "action_packets": [
                _sandbox_packet(proposal_id="ap-frozen-final"),
            ],
            "digital_body_consequence": {
                "kind": "sandbox_execution_completed",
                "summary": "frozen final sandbox run",
                "primary_status": "completed",
                "primary_tool_name": "execute_workspace_command",
                "sandbox_run_id": "ap-frozen-final-run",
                "sandbox_command_profile": "pytest",
                "procedural_growth": True,
                "procedural_continuity": {
                    "capability_family": "sandbox",
                    "pattern": "pytest",
                    "identity_safe": True,
                    "confidence": 0.8,
                    "last_success_ref": "ap-frozen-final-run",
                    "traces": [
                        {
                            "trace_kind": "sandbox_execution_pattern",
                            "source_proposal_id": "ap-frozen-final",
                            "source_run_id": "ap-frozen-final-run",
                            "source_tool_name": "execute_workspace_command",
                            "status": "completed",
                            "procedure_steps": ["read frozen run log"],
                            "boundary_notes": ["requires approval before execution"],
                            "confidence": 0.8,
                        }
                    ],
                },
            },
        },
    )

    traces = consequence["procedural_continuity"]["traces"]
    assert traces[0]["source_proposal_id"] == "ap-frozen-final"
    assert traces[0]["source_run_id"] == "ap-frozen-final-run"
    assert all(trace["source_proposal_id"] != "ap-live-stale" for trace in traces)
