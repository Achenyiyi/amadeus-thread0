from __future__ import annotations

from amadeus_thread0.runtime.technical_preview_rc import (
    TECHNICAL_PREVIEW_RC_PHASE1_READY,
    build_technical_preview_rc_readiness,
    compact_technical_preview_rc_line,
)


def _passed(readiness: str) -> dict:
    return {"overall_status": "passed", "readiness_status": readiness, "report_path": f"evals/reports/{readiness}.json"}


def test_rc_readiness_passes_when_current_closeout_evidence_is_ready():
    report = build_technical_preview_rc_readiness(
        preserved_baselines=_passed("preserved_baselines_ready"),
        runtime_productization_phase3=_passed("runtime_productization_phase3_ready"),
        http_transport=_passed("http_transport_thin_wrapper_phase1_ready"),
        approved_artifact_multimodal_runtime=_passed("approved_artifact_multimodal_runtime_phase1_ready"),
        chinese_semantic_naturalness=_passed("chinese_semantic_naturalness_phase1_ready"),
        dynamic_skill_candidate_runtime=_passed("dynamic_skill_candidate_runtime_phase1_ready"),
        runtime_status_dashboard={
            "overall_status": "passed",
            "readiness_status": "runtime_status_dashboard_ready",
            "summary": {"next_spec_count": 0, "ready_gates": 3, "total_gates": 3},
            "lanes": {
                "live_capture": {"runtime_authority": "blocked_by_contract"},
                "external_executor_harness": {"runtime_authority": "blocked_by_contract"},
                "dynamic_skill_generation": {"runtime_authority": "readback_audit_only"},
                "multimodal_artifact_inspection": {"runtime_authority": "approved_result_ingestion_only"},
            },
            "next_specs": [],
        },
    )

    assert report["overall_status"] == "passed"
    assert report["readiness_status"] == TECHNICAL_PREVIEW_RC_PHASE1_READY
    assert report["summary"]["ready_evidence_count"] == 7
    assert report["summary"]["next_spec_count"] == 0
    assert report["authority_boundary"]["live_capture_enabled"] is False
    assert report["authority_boundary"]["external_executor_auto_enabled"] is False
    assert report["authority_boundary"]["dynamic_skill_registry_auto_write_enabled"] is False
    assert report["authority_boundary"]["multimodal_model_auto_call_enabled"] is False
    assert report["checks"]["runtime_status_dashboard"]["status"] == "passed"


def test_rc_readiness_fails_when_dashboard_still_has_next_specs():
    report = build_technical_preview_rc_readiness(
        preserved_baselines=_passed("preserved_baselines_ready"),
        runtime_productization_phase3=_passed("runtime_productization_phase3_ready"),
        http_transport=_passed("http_transport_thin_wrapper_phase1_ready"),
        approved_artifact_multimodal_runtime=_passed("approved_artifact_multimodal_runtime_phase1_ready"),
        chinese_semantic_naturalness=_passed("chinese_semantic_naturalness_phase1_ready"),
        dynamic_skill_candidate_runtime=_passed("dynamic_skill_candidate_runtime_phase1_ready"),
        runtime_status_dashboard={
            "overall_status": "passed",
            "readiness_status": "runtime_status_dashboard_ready",
            "summary": {"next_spec_count": 1, "ready_gates": 3, "total_gates": 3},
            "lanes": {
                "live_capture": {"runtime_authority": "blocked_by_contract"},
                "external_executor_harness": {"runtime_authority": "blocked_by_contract"},
            },
            "next_specs": [{"id": "some_future_spec"}],
        },
    )

    assert report["overall_status"] == "failed"
    assert report["readiness_status"] == "technical_preview_rc_phase1_blocked"
    assert "next_specs_not_empty" in report["failure_reasons"]
    assert report["checks"]["runtime_status_dashboard_next_specs"]["status"] == "failed"


def test_rc_readiness_fails_closed_when_blocked_lane_authority_widens():
    report = build_technical_preview_rc_readiness(
        preserved_baselines=_passed("preserved_baselines_ready"),
        runtime_productization_phase3=_passed("runtime_productization_phase3_ready"),
        http_transport=_passed("http_transport_thin_wrapper_phase1_ready"),
        approved_artifact_multimodal_runtime=_passed("approved_artifact_multimodal_runtime_phase1_ready"),
        chinese_semantic_naturalness=_passed("chinese_semantic_naturalness_phase1_ready"),
        dynamic_skill_candidate_runtime=_passed("dynamic_skill_candidate_runtime_phase1_ready"),
        runtime_status_dashboard={
            "overall_status": "passed",
            "readiness_status": "runtime_status_dashboard_ready",
            "summary": {"next_spec_count": 0, "ready_gates": 3, "total_gates": 3},
            "lanes": {
                "live_capture": {"runtime_authority": "enabled"},
                "external_executor_harness": {"runtime_authority": "blocked_by_contract"},
            },
            "next_specs": [],
        },
    )

    assert report["overall_status"] == "failed"
    assert "authority_widened:live_capture" in report["failure_reasons"]
    assert report["authority_boundary"]["live_capture_enabled"] is True


def test_compact_rc_line_is_short_and_explicit():
    report = build_technical_preview_rc_readiness(
        preserved_baselines=_passed("preserved_baselines_ready"),
        runtime_productization_phase3=_passed("runtime_productization_phase3_ready"),
        http_transport=_passed("http_transport_thin_wrapper_phase1_ready"),
        approved_artifact_multimodal_runtime=_passed("approved_artifact_multimodal_runtime_phase1_ready"),
        chinese_semantic_naturalness=_passed("chinese_semantic_naturalness_phase1_ready"),
        dynamic_skill_candidate_runtime=_passed("dynamic_skill_candidate_runtime_phase1_ready"),
        runtime_status_dashboard={
            "overall_status": "passed",
            "readiness_status": "runtime_status_dashboard_ready",
            "summary": {"next_spec_count": 0, "ready_gates": 3, "total_gates": 3},
            "lanes": {
                "live_capture": {"runtime_authority": "blocked_by_contract"},
                "external_executor_harness": {"runtime_authority": "blocked_by_contract"},
                "dynamic_skill_generation": {"runtime_authority": "readback_audit_only"},
                "multimodal_artifact_inspection": {"runtime_authority": "approved_result_ingestion_only"},
            },
            "next_specs": [],
        },
    )

    line = compact_technical_preview_rc_line(report)

    assert "technical_preview_rc=technical_preview_rc_phase1_ready" in line
    assert "evidence=7/7" in line
    assert "next_specs=0" in line
    assert "blocked_lanes_preserved=True" in line
