from __future__ import annotations

import time
from typing import Any


TECHNICAL_PREVIEW_RC_PHASE1_READY = "technical_preview_rc_phase1_ready"
TECHNICAL_PREVIEW_RC_PHASE1_BLOCKED = "technical_preview_rc_phase1_blocked"

EXPECTED_EVIDENCE = {
    "preserved_baselines": "preserved_baselines_ready",
    "runtime_status_dashboard": "runtime_status_dashboard_ready",
    "runtime_productization_phase3": "runtime_productization_phase3_ready",
    "http_transport": "http_transport_thin_wrapper_phase1_ready",
    "approved_artifact_multimodal_runtime": "approved_artifact_multimodal_runtime_phase1_ready",
    "chinese_semantic_naturalness": "chinese_semantic_naturalness_phase1_ready",
    "dynamic_skill_candidate_runtime": "dynamic_skill_candidate_runtime_phase1_ready",
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _readiness(report: dict[str, Any]) -> str:
    return str(report.get("readiness_status") or report.get("readiness") or "").strip()


def _evidence_check(report: dict[str, Any] | None, expected: str) -> dict[str, Any]:
    data = _dict_or_empty(report)
    overall = str(data.get("overall_status") or "").strip() or "missing"
    readiness = _readiness(data)
    status = "passed" if overall == "passed" and readiness == expected else "failed"
    reasons = [str(reason) for reason in data.get("failure_reasons", []) if str(reason)]
    if overall != "passed":
        reasons.append(f"overall_status={overall}")
    if readiness != expected:
        reasons.append(f"readiness={readiness or 'missing'} expected={expected}")
    return {
        "status": status,
        "overall_status": overall,
        "readiness_status": readiness,
        "expected_readiness": expected,
        "report_path": str(data.get("report_path") or ""),
        "failure_reasons": reasons,
    }


def _next_spec_check(dashboard: dict[str, Any]) -> dict[str, Any]:
    summary = _dict_or_empty(dashboard.get("summary"))
    next_specs = list(dashboard.get("next_specs") or [])
    count = int(summary.get("next_spec_count") or len(next_specs))
    passed = count == 0 and not next_specs
    return {
        "status": "passed" if passed else "failed",
        "next_spec_count": count,
        "failure_reasons": [] if passed else ["next_specs_not_empty"],
    }


def _authority_boundary_from_dashboard(dashboard: dict[str, Any]) -> dict[str, bool]:
    lanes = _dict_or_empty(dashboard.get("lanes"))
    live_capture = _dict_or_empty(lanes.get("live_capture"))
    external_executor = _dict_or_empty(lanes.get("external_executor_harness"))
    dynamic_skills = _dict_or_empty(lanes.get("dynamic_skill_generation"))
    multimodal = _dict_or_empty(lanes.get("multimodal_artifact_inspection"))
    return {
        "live_capture_enabled": live_capture.get("runtime_authority") != "blocked_by_contract",
        "external_executor_auto_enabled": external_executor.get("runtime_authority") not in {
            "blocked_by_contract",
            "blocked_except_preserved_sandbox",
        },
        "dynamic_skill_registry_auto_write_enabled": dynamic_skills.get("runtime_authority")
        != "readback_audit_only",
        "multimodal_model_auto_call_enabled": multimodal.get("runtime_authority")
        != "approved_result_ingestion_only",
        "frontend_semantics_owner": False,
        "persona_core_mutation_allowed": False,
        "memory_write_widened": False,
        "http_server_semantics_owner": False,
    }


def build_technical_preview_rc_readiness(
    *,
    preserved_baselines: dict[str, Any] | None,
    runtime_status_dashboard: dict[str, Any] | None,
    runtime_productization_phase3: dict[str, Any] | None,
    http_transport: dict[str, Any] | None,
    approved_artifact_multimodal_runtime: dict[str, Any] | None,
    chinese_semantic_naturalness: dict[str, Any] | None,
    dynamic_skill_candidate_runtime: dict[str, Any] | None,
) -> dict[str, Any]:
    dashboard = _dict_or_empty(runtime_status_dashboard)
    checks = {
        "preserved_baselines": _evidence_check(
            preserved_baselines, EXPECTED_EVIDENCE["preserved_baselines"]
        ),
        "runtime_status_dashboard": _evidence_check(
            dashboard, EXPECTED_EVIDENCE["runtime_status_dashboard"]
        ),
        "runtime_status_dashboard_next_specs": _next_spec_check(dashboard),
        "runtime_productization_phase3": _evidence_check(
            runtime_productization_phase3,
            EXPECTED_EVIDENCE["runtime_productization_phase3"],
        ),
        "http_transport": _evidence_check(http_transport, EXPECTED_EVIDENCE["http_transport"]),
        "approved_artifact_multimodal_runtime": _evidence_check(
            approved_artifact_multimodal_runtime,
            EXPECTED_EVIDENCE["approved_artifact_multimodal_runtime"],
        ),
        "chinese_semantic_naturalness": _evidence_check(
            chinese_semantic_naturalness,
            EXPECTED_EVIDENCE["chinese_semantic_naturalness"],
        ),
        "dynamic_skill_candidate_runtime": _evidence_check(
            dynamic_skill_candidate_runtime,
            EXPECTED_EVIDENCE["dynamic_skill_candidate_runtime"],
        ),
    }
    evidence_keys = set(EXPECTED_EVIDENCE)
    ready_evidence_count = sum(1 for key in evidence_keys if checks[key]["status"] == "passed")
    authority_boundary = _authority_boundary_from_dashboard(dashboard)
    failures = [
        key
        for key, row in checks.items()
        if str(row.get("status") or "") != "passed"
    ]
    if "runtime_status_dashboard_next_specs" in failures:
        failures.append("next_specs_not_empty")
    if authority_boundary["live_capture_enabled"]:
        failures.append("authority_widened:live_capture")
    if authority_boundary["external_executor_auto_enabled"]:
        failures.append("authority_widened:external_executor_harness")
    if authority_boundary["dynamic_skill_registry_auto_write_enabled"]:
        failures.append("authority_widened:dynamic_skill_registry")
    if authority_boundary["multimodal_model_auto_call_enabled"]:
        failures.append("authority_widened:multimodal_model_auto_call")
    blocked_lanes_preserved = not any(
        authority_boundary[key]
        for key in (
            "live_capture_enabled",
            "external_executor_auto_enabled",
            "dynamic_skill_registry_auto_write_enabled",
            "multimodal_model_auto_call_enabled",
        )
    )
    overall = "failed" if failures else "passed"
    next_spec_count = int(
        _dict_or_empty(dashboard.get("summary")).get("next_spec_count")
        or len(dashboard.get("next_specs") or [])
    )
    return {
        "schema": "technical_preview_rc.v1",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": overall,
        "readiness_status": (
            TECHNICAL_PREVIEW_RC_PHASE1_READY
            if overall == "passed"
            else TECHNICAL_PREVIEW_RC_PHASE1_BLOCKED
        ),
        "summary": {
            "ready_evidence_count": ready_evidence_count,
            "total_evidence_count": len(EXPECTED_EVIDENCE),
            "next_spec_count": next_spec_count,
            "blocked_lanes_preserved": blocked_lanes_preserved,
        },
        "checks": checks,
        "authority_boundary": authority_boundary,
        "failure_reasons": list(dict.fromkeys(failures)),
    }


def compact_technical_preview_rc_line(report: dict[str, Any] | None) -> str:
    data = _dict_or_empty(report)
    summary = _dict_or_empty(data.get("summary"))
    return " | ".join(
        [
            f"technical_preview_rc={str(data.get('readiness_status') or 'unknown')}",
            f"evidence={int(summary.get('ready_evidence_count') or 0)}/{int(summary.get('total_evidence_count') or 0)}",
            f"next_specs={int(summary.get('next_spec_count') or 0)}",
            f"blocked_lanes_preserved={bool(summary.get('blocked_lanes_preserved', False))}",
        ]
    )


__all__ = [
    "EXPECTED_EVIDENCE",
    "TECHNICAL_PREVIEW_RC_PHASE1_BLOCKED",
    "TECHNICAL_PREVIEW_RC_PHASE1_READY",
    "build_technical_preview_rc_readiness",
    "compact_technical_preview_rc_line",
]
