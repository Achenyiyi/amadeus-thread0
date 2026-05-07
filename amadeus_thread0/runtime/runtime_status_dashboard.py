from __future__ import annotations

from typing import Any


RUNTIME_STATUS_DASHBOARD_READINESS = "runtime_status_dashboard_ready"

EXPECTED_GATES = {
    "preserved_baselines": "preserved_baselines_ready",
    "post_unlock_roadmap": "post_unlock_roadmap_ready",
    "runtime_productization": "runtime_productization_phase2_ready",
}

NEXT_SPECS = [
    {
        "id": "dynamic_skill_candidate_runtime",
        "status": "fresh_spec_required",
        "boundary": "candidate generation stays frozen/hash/approval gated; no automatic registry writes",
    },
]

LANES = {
    "backend_preserved_baselines": {
        "status": "preserved",
        "runtime_authority": "existing_contract",
        "summary": "Core loop, autonomy, memory/body, sandbox, browser, skills, productization, and embodied readbacks remain preserved.",
    },
    "frontend_runtime_shell": {
        "status": "phase2_ready",
        "runtime_authority": "consumer_only",
        "summary": "React/Vite shell consumes backend.v1 envelopes and does not own backend semantics.",
    },
    "http_transport": {
        "status": "phase1_ready",
        "runtime_authority": "thin_wrapper",
        "summary": "Standard-library WSGI wrapper delegates to BackendTransportAdapter without owning backend semantics.",
    },
    "multimodal_artifact_inspection": {
        "status": "phase1_ready",
        "runtime_authority": "approved_result_ingestion_only",
        "summary": "Already-approved precomputed artifact inspection results can complete frozen packets without live capture or model calls.",
    },
    "chinese_semantic_naturalness": {
        "status": "phase1_ready",
        "runtime_authority": "deterministic_readback_only",
        "summary": "Deterministic naturalness diagnostics sit on top of Phase 2 semantic floors without prompt rewrites or authority widening.",
    },
    "live_capture": {
        "status": "blocked",
        "runtime_authority": "blocked_by_contract",
        "summary": "Live microphone, camera, and background screen capture remain blocked.",
    },
    "dynamic_skill_generation": {
        "status": "planned_next_spec",
        "runtime_authority": "next_spec_required",
        "summary": "Candidate generation may be specified, but registry writes remain approval gated.",
    },
    "external_executor_harness": {
        "status": "blocked_except_preserved_sandbox",
        "runtime_authority": "blocked_by_contract",
        "summary": "External harnesses remain fail-closed except the preserved sandbox runner.",
    },
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _status_row(report: dict[str, Any] | None, expected: str, source_report: str = "") -> dict[str, Any]:
    data = _dict_or_empty(report)
    overall = str(data.get("overall_status") or "").strip() or "missing"
    readiness = str(data.get("readiness_status") or data.get("readiness") or "").strip()
    ready = overall == "passed" and readiness == expected
    failures = [str(reason) for reason in data.get("failure_reasons", []) if str(reason)]
    return {
        "status": "passed" if ready else "failed",
        "overall_status": overall,
        "readiness_status": readiness,
        "expected_readiness": expected,
        "source_report": str(source_report or data.get("report_path") or "").strip(),
        "failure_reasons": failures,
    }


def _collect_sample_failures(*reports: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    for report in reports:
        data = _dict_or_empty(report)
        direct = data.get("failure_reasons") if isinstance(data.get("failure_reasons"), list) else []
        failures.extend(str(reason) for reason in direct if str(reason))
        baselines = data.get("baselines") if isinstance(data.get("baselines"), dict) else {}
        for row in baselines.values():
            row_data = _dict_or_empty(row)
            row_failures = row_data.get("failure_reasons") if isinstance(row_data.get("failure_reasons"), list) else []
            failures.extend(str(reason) for reason in row_failures if str(reason))
            if len(failures) >= 5:
                return failures[:5]
    return failures[:5]


def _source_reports_missing(checks: dict[str, dict[str, Any]]) -> int:
    missing = 0
    for key, row in checks.items():
        if not str(row.get("source_report") or "").strip():
            missing += 1
            continue
        failure_text = " ".join(str(reason) for reason in row.get("failure_reasons", []))
        if "missing_report:" in failure_text:
            missing += 1
    return missing


def build_runtime_status_dashboard(
    *,
    preserved_baselines: dict[str, Any] | None,
    post_unlock_roadmap: dict[str, Any] | None,
    runtime_productization: dict[str, Any] | None,
    source_reports: dict[str, str] | None = None,
) -> dict[str, Any]:
    sources = dict(source_reports or {})
    checks = {
        "preserved_baselines": _status_row(
            preserved_baselines,
            EXPECTED_GATES["preserved_baselines"],
            sources.get("preserved_baselines", ""),
        ),
        "post_unlock_roadmap": _status_row(
            post_unlock_roadmap,
            EXPECTED_GATES["post_unlock_roadmap"],
            sources.get("post_unlock_roadmap", ""),
        ),
        "runtime_productization": _status_row(
            runtime_productization,
            EXPECTED_GATES["runtime_productization"],
            sources.get("runtime_productization", ""),
        ),
    }
    ready_gates = sum(1 for row in checks.values() if row["status"] == "passed")
    missing_source_reports = _source_reports_missing(checks)
    all_ready = ready_gates == len(checks)
    state_interpretation = (
        "ready"
        if all_ready
        else "source_reports_missing"
        if missing_source_reports
        else "readiness_regressed"
    )
    return {
        "schema": "runtime_status_dashboard.v1",
        "overall_status": "passed" if all_ready else "attention_required",
        "readiness_status": (
            RUNTIME_STATUS_DASHBOARD_READINESS if all_ready else "runtime_status_dashboard_attention_required"
        ),
        "checks": checks,
        "summary": {
            "ready_gates": ready_gates,
            "total_gates": len(checks),
            "missing_source_reports": missing_source_reports,
            "next_spec_count": len(NEXT_SPECS),
            "blocked_lane_count": sum(
                1 for row in LANES.values() if row["runtime_authority"] == "blocked_by_contract"
            ),
        },
        "lanes": {key: dict(value) for key, value in LANES.items()},
        "next_specs": [dict(row) for row in NEXT_SPECS],
        "stale_plan_hygiene": {
            "status": "attention_recommended",
            "summary": "Legacy plan checkboxes may remain unchecked even when later audits closed the phase.",
        },
        "diagnostics": {
            "state_interpretation": state_interpretation,
            "sample_failures": _collect_sample_failures(
                preserved_baselines,
                post_unlock_roadmap,
                runtime_productization,
            ),
        },
    }


def compact_runtime_status_line(dashboard: dict[str, Any] | None) -> str:
    data = _dict_or_empty(dashboard)
    summary = _dict_or_empty(data.get("summary"))
    return " | ".join(
        [
            f"runtime_status={str(data.get('readiness_status') or 'unknown')}",
            f"gates={int(summary.get('ready_gates') or 0)}/{int(summary.get('total_gates') or 0)}",
            f"next_specs={int(summary.get('next_spec_count') or 0)}",
            f"blocked={int(summary.get('blocked_lane_count') or 0)}",
        ]
    )


__all__ = [
    "EXPECTED_GATES",
    "LANES",
    "NEXT_SPECS",
    "RUNTIME_STATUS_DASHBOARD_READINESS",
    "build_runtime_status_dashboard",
    "compact_runtime_status_line",
]
