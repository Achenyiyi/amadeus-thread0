from __future__ import annotations

from amadeus_thread0.graph_parts.procedural_planning import (
    build_procedural_planning_bias,
    normalize_procedural_planning,
)


def _sandbox_trace(**overrides):
    trace = {
        "trace_id": "proc_pytest_trace",
        "trace_kind": "sandbox_execution_pattern",
        "source_proposal_id": "ap-pytest",
        "source_run_id": "run-pytest",
        "source_tool_name": "execute_workspace_command",
        "status": "completed",
        "preconditions": ["workspace_root available", "approval granted"],
        "procedure_steps": ["inspect cwd", "run bounded command", "read stdout/artifact"],
        "result_summary": "pytest passed",
        "reuse_conditions": ["similar workspace command", "pytest command profile"],
        "boundary_notes": ["requires approval before execution"],
        "confidence": 0.74,
    }
    trace.update(overrides)
    return trace


def _embodied_with_traces(traces):
    return {
        "workspace_root": "E:/repo/amadeus-thread0",
        "sandbox_runner_kind": "docker_isolated_runner",
        "sandbox_isolation_level": "docker_local_isolated",
        "sandbox_network_policy": "none",
        "procedural_traces": traces,
    }


def _access_hints(**overrides):
    hints = {
        "workspace_root": "E:/repo/amadeus-thread0",
        "sandbox_state": {
            "runner_kind": "docker_isolated_runner",
            "isolation_level": "docker_local_isolated",
            "network_policy": "none",
            "workspace_root_kind": "attached_repo_root",
            "image_ref": "amadeus-thread0/sandbox-phase2:py312",
        },
    }
    hints.update(overrides)
    return hints


def test_completed_sandbox_pytest_trace_creates_approval_preserving_execution_bias():
    bias = build_procedural_planning_bias(
        current_event={"text": "继续跑刚才那类 pytest 检查。"},
        embodied_context=_embodied_with_traces([_sandbox_trace()]),
        access_hints=_access_hints(),
    )

    assert bias["planning_bias"] is True
    assert bias["bias_kind"] == "sandbox_execute"
    assert bias["trace_id"] == "proc_pytest_trace"
    assert bias["trace_kind"] == "sandbox_execution_pattern"
    assert bias["source_run_id"] == "run-pytest"
    assert bias["suggested_capability_family"] == "sandbox"
    assert bias["suggested_pattern"] == "pytest"
    assert bias["suggested_executor"] == "pytest"
    assert bias["suggested_argv"] == ["pytest"]
    assert bias["suggested_profile"] == "pytest"
    assert bias["must_request_approval"] is True
    assert bias["requires_approval"] is True
    assert bias["capability_claim"] is True
    assert bias["avoid_repeating_boundary"] is False


def test_blocked_trace_creates_boundary_bias_not_capability_claim():
    bias = build_procedural_planning_bias(
        current_event={"text": "别再重复刚才被拦住的命令。"},
        embodied_context=_embodied_with_traces(
            [
                _sandbox_trace(
                    trace_id="proc_blocked_trace",
                    trace_kind="blocked_boundary_pattern",
                    status="blocked",
                    result_summary="pip install was blocked",
                    reuse_conditions=["similar workspace command"],
                    boundary_notes=["package install is blocked in the sandbox"],
                    confidence=0.67,
                )
            ]
        ),
        access_hints=_access_hints(),
    )

    assert bias["bias_kind"] == "boundary_only"
    assert bias["capability_claim"] is False
    assert bias["avoid_repeating_boundary"] is True
    assert "package install" in bias["boundary_note"]
    assert "suggested_executor" not in bias


def test_browser_manual_takeover_trace_surfaces_manual_boundary_without_mutation_fields():
    bias = build_procedural_planning_bias(
        current_event={"text": "继续刚才浏览器登录那一步。"},
        embodied_context=_embodied_with_traces(
            [
                {
                    "trace_id": "proc_browser_takeover",
                    "trace_kind": "blocked_boundary_pattern",
                    "source_proposal_id": "ap-browser",
                    "source_run_id": "run-browser",
                    "source_tool_name": "browser_fill",
                    "status": "blocked",
                    "procedure_steps": [
                        "preserve current page/profile",
                        "hand off sensitive step",
                        "resume after manual takeover",
                    ],
                    "result_summary": "manual browser takeover required",
                    "reuse_conditions": ["same browser profile/page family"],
                    "boundary_notes": ["manual browser takeover required"],
                    "confidence": 0.61,
                }
            ]
        ),
        access_hints=_access_hints(),
    )

    assert bias["bias_kind"] == "browser_manual_takeover"
    assert bias["must_request_approval"] is True
    assert bias["requires_approval"] is True
    assert bias["capability_claim"] is False
    assert "suggested_argv" not in bias
    assert "browser_operation" not in bias


def test_skill_usage_trace_creates_guidance_without_registry_mutation_truth():
    bias = build_procedural_planning_bias(
        current_event={"text": "继续用刚才那个资料锚点办法查下去。"},
        embodied_context=_embodied_with_traces(
            [
                {
                    "trace_id": "proc_skill_use",
                    "trace_kind": "skill_usage_pattern",
                    "source_proposal_id": "ap-skill",
                    "source_run_id": "ap-skill",
                    "source_tool_name": "search_web",
                    "status": "completed",
                    "procedure_steps": [
                        "match active skill",
                        "apply skill guidance",
                        "preserve artifact continuity",
                    ],
                    "result_summary": "used source-ref skill guidance",
                    "reuse_conditions": ["similar skill-supported task"],
                    "boundary_notes": ["skill registry truth stays outside autobiographical memory"],
                    "confidence": 0.7,
                }
            ]
        ),
        access_hints=_access_hints(),
    )

    assert bias["bias_kind"] == "skill_guidance"
    assert bias["capability_claim"] is True
    assert "registry" not in bias
    assert "skill_operation" not in bias
    assert "skill registry" in bias["boundary_note"]


def test_low_confidence_trace_is_ignored():
    assert (
        build_procedural_planning_bias(
            current_event={"text": "继续跑 pytest。"},
            embodied_context=_embodied_with_traces([_sandbox_trace(confidence=0.2)]),
            access_hints=_access_hints(),
        )
        == {}
    )


def test_duplicate_trace_ids_keep_highest_confidence_candidate():
    bias = build_procedural_planning_bias(
        current_event={"text": "继续跑 pytest。"},
        embodied_context=_embodied_with_traces(
            [
                _sandbox_trace(confidence=0.41, source_run_id="run-low"),
                _sandbox_trace(confidence=0.82, source_run_id="run-high"),
            ]
        ),
        access_hints=_access_hints(),
    )

    assert bias["source_run_id"] == "run-high"
    assert bias["confidence"] == 0.82


def test_outcome_calibration_prefers_recent_confirmed_success_trace():
    low_base_confirmed = _sandbox_trace(
        trace_id="proc_phase3_confirmed",
        source_run_id="run-confirmed",
        confidence=0.69,
    )
    high_base_unconfirmed = _sandbox_trace(
        trace_id="proc_phase3_unconfirmed",
        source_run_id="run-unconfirmed",
        confidence=0.72,
    )
    embodied = _embodied_with_traces([low_base_confirmed, high_base_unconfirmed])
    embodied["procedural_outcomes"] = [
        {
            "source_trace_id": "proc_phase3_confirmed",
            "source_proposal_id": "ap-confirmed",
            "source_run_id": "run-confirmed-new",
            "planning_bias_kind": "sandbox_execute",
            "source_tool_name": "execute_workspace_command",
            "attempt_status": "completed",
            "outcome_kind": "confirmed_success",
            "confidence_delta": 0.08,
            "reuse_allowed": True,
            "boundary_reinforced": False,
            "evidence_refs": ["run-confirmed-new"],
        }
    ]

    bias = build_procedural_planning_bias(
        current_event={"text": "继续跑 pytest。"},
        embodied_context=embodied,
        access_hints=_access_hints(),
    )

    assert bias["trace_id"] == "proc_phase3_confirmed"
    assert bias["source_run_id"] == "run-confirmed"
    assert bias["confidence"] == 0.77


def test_boundary_reinforced_outcome_keeps_trace_readback_only():
    trace = _sandbox_trace(
        trace_id="proc_phase3_boundary",
        source_run_id="run-boundary",
        confidence=0.76,
    )
    embodied = _embodied_with_traces([trace])
    embodied["procedural_outcomes"] = [
        {
            "source_trace_id": "proc_phase3_boundary",
            "source_proposal_id": "ap-boundary",
            "source_run_id": "run-boundary",
            "planning_bias_kind": "sandbox_execute",
            "source_tool_name": "execute_workspace_command",
            "attempt_status": "blocked",
            "outcome_kind": "blocked_boundary_reinforced",
            "confidence_delta": -0.08,
            "reuse_allowed": False,
            "boundary_reinforced": True,
            "recovery_hint": "package install is blocked in the sandbox",
            "evidence_refs": ["run-boundary"],
        }
    ]

    bias = build_procedural_planning_bias(
        current_event={"text": "继续跑 pytest。"},
        embodied_context=embodied,
        access_hints=_access_hints(),
    )

    assert bias["bias_kind"] == "boundary_only"
    assert bias["trace_id"] == "proc_phase3_boundary"
    assert bias["capability_claim"] is False
    assert bias["avoid_repeating_boundary"] is True
    assert "suggested_executor" not in bias


def test_failed_recovery_marker_prevents_direct_execution_reuse():
    trace = _sandbox_trace(
        trace_id="proc_phase4_failed_recovery",
        source_run_id="run-phase4-failed",
        confidence=0.74,
        last_outcome_kind="failed_execution",
        reuse_allowed=False,
        recovery_required=True,
        recovery_kind="inspect_failure_artifact",
        recovery_allowed_bias_kind="workspace_guidance",
        recovery_suggested_next_step="inspect stderr/stdout artifacts before rerunning a bounded command",
        recovery_refs=["proc_rec_failed"],
    )
    embodied = _embodied_with_traces([trace])

    bias = build_procedural_planning_bias(
        current_event={"text": "继续跑 pytest。"},
        embodied_context=embodied,
        access_hints=_access_hints(),
    )

    assert bias["bias_kind"] == "workspace_guidance"
    assert bias["trace_id"] == "proc_phase4_failed_recovery"
    assert bias["capability_claim"] is False
    assert bias["avoid_repeating_boundary"] is False
    assert "stderr" in bias["suggested_first_step"]
    assert "suggested_executor" not in bias


def test_failed_recovery_marker_on_blocked_trace_still_surfaces_workspace_guidance():
    trace = _sandbox_trace(
        trace_id="proc_phase4_failed_blocked_recovery",
        trace_kind="blocked_boundary_pattern",
        status="blocked",
        source_run_id="run-phase4-failed-blocked",
        confidence=0.5,
        result_summary="pytest failed",
        last_outcome_kind="failed_execution",
        reuse_allowed=False,
        boundary_reinforced=False,
        recovery_required=True,
        recovery_kind="inspect_failure_artifact",
        recovery_allowed_bias_kind="workspace_guidance",
        recovery_suggested_next_step="inspect stderr/stdout artifacts before rerunning a bounded command",
        recovery_refs=["proc_rec_failed_blocked"],
    )
    embodied = _embodied_with_traces([trace])

    bias = build_procedural_planning_bias(
        current_event={"text": "继续跑 pytest。"},
        embodied_context=embodied,
        access_hints=_access_hints(),
    )

    assert bias["bias_kind"] == "workspace_guidance"
    assert bias["trace_id"] == "proc_phase4_failed_blocked_recovery"
    assert bias["capability_claim"] is False
    assert "stderr" in bias["suggested_first_step"]
    assert "suggested_executor" not in bias


def test_boundary_recovery_marker_remains_boundary_only():
    trace = _sandbox_trace(
        trace_id="proc_phase4_boundary_recovery",
        source_run_id="run-phase4-boundary",
        confidence=0.74,
        recovery_required=True,
        recovery_kind="avoid_blocked_boundary",
        recovery_allowed_bias_kind="boundary_only",
        recovery_suggested_next_step="avoid repeating the blocked action",
        recovery_refs=["proc_rec_boundary"],
    )
    embodied = _embodied_with_traces([trace])

    bias = build_procedural_planning_bias(
        current_event={"text": "继续跑 pytest。"},
        embodied_context=embodied,
        access_hints=_access_hints(),
    )

    assert bias["bias_kind"] == "boundary_only"
    assert bias["trace_id"] == "proc_phase4_boundary_recovery"
    assert bias["capability_claim"] is False
    assert bias["avoid_repeating_boundary"] is True
    assert "suggested_executor" not in bias


def test_workspace_root_mismatch_ignores_execution_producing_bias():
    assert (
        build_procedural_planning_bias(
            current_event={"text": "继续跑 pytest。"},
            embodied_context=_embodied_with_traces([_sandbox_trace()]),
            access_hints=_access_hints(workspace_root="E:/runtime/workspaces/current"),
        )
        == {}
    )


def test_normalize_procedural_planning_cleans_unknown_or_unsafe_fields():
    normalized = normalize_procedural_planning(
        {
            "planning_bias": True,
            "bias_kind": "sandbox_execute",
            "trace_id": "proc_x",
            "source_run_id": "run-x",
            "suggested_capability_family": "sandbox",
            "suggested_pattern": "pytest",
            "suggested_executor": "pytest",
            "suggested_argv": ["pytest", "", None],
            "must_request_approval": True,
            "requires_approval": True,
            "capability_claim": True,
            "avoid_repeating_boundary": False,
            "confidence": 2,
            "registry": {"pollution": True},
            "browser_operation": "fill",
        }
    )

    assert normalized["confidence"] == 1.0
    assert normalized["suggested_argv"] == ["pytest"]
    assert "registry" not in normalized
    assert "browser_operation" not in normalized
