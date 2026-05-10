from __future__ import annotations

import time
from typing import Any


OPERATOR_CONSOLE_RC_PHASE1_READY = "operator_console_rc_phase1_ready"
OPERATOR_CONSOLE_RC_PHASE1_BLOCKED = "operator_console_rc_phase1_blocked"


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _status_ref(report: dict[str, Any], *, fallback_schema: str = "") -> dict[str, str]:
    return {
        "schema": str(report.get("schema") or fallback_schema),
        "overall_status": str(report.get("overall_status") or "missing"),
        "readiness_status": str(report.get("readiness_status") or report.get("readiness") or ""),
    }


def _ready(report: dict[str, Any], expected_readiness: str) -> bool:
    return (
        str(report.get("overall_status") or "") == "passed"
        and str(report.get("readiness_status") or report.get("readiness") or "") == expected_readiness
    )


def _route_inventory(operator_readback: dict[str, Any]) -> dict[str, Any]:
    safe_routes = _dict_or_empty(operator_readback.get("safe_routes"))
    read_only_routes = [str(route) for route in _list_or_empty(safe_routes.get("read_only_routes")) if str(route)]
    mutation_routes = [str(route) for route in _list_or_empty(safe_routes.get("mutation_routes")) if str(route)]
    user_control_routes = [
        str(route) for route in _list_or_empty(safe_routes.get("user_control_routes")) if str(route)
    ]
    external_mutation_routes = [
        str(route) for route in _list_or_empty(safe_routes.get("external_mutation_routes")) if str(route)
    ]
    return {
        "read_only_routes": read_only_routes,
        "mutation_routes": mutation_routes,
        "user_control_routes": user_control_routes,
        "external_mutation_routes": external_mutation_routes,
        "route_count": len(read_only_routes),
        "approval_required_for_external_mutation": bool(
            safe_routes.get("approval_required_for_external_mutation", True)
        ),
        "frontend_semantics_owner": bool(safe_routes.get("frontend_semantics_owner", False)),
    }


def _authority_boundary(
    technical_preview_rc: dict[str, Any],
    operator_readback: dict[str, Any],
) -> dict[str, bool]:
    rc_boundary = _dict_or_empty(technical_preview_rc.get("authority_boundary"))
    operator_boundary = _dict_or_empty(operator_readback.get("authority_boundary"))
    return {
        "live_capture_enabled": bool(
            rc_boundary.get("live_capture_enabled")
            or operator_boundary.get("live_capture_auto_enabled")
        ),
        "external_executor_auto_enabled": bool(
            rc_boundary.get("external_executor_auto_enabled")
            or operator_boundary.get("external_harness_runtime_auto_enabled")
        ),
        "dynamic_skill_registry_auto_write_enabled": bool(
            rc_boundary.get("dynamic_skill_registry_auto_write_enabled")
            or operator_boundary.get("dynamic_registry_write_auto_allowed")
        ),
        "multimodal_model_auto_call_enabled": bool(
            rc_boundary.get("multimodal_model_auto_call_enabled")
            or operator_boundary.get("multimodal_model_auto_call_enabled")
        ),
        "frontend_semantics_owner": bool(
            rc_boundary.get("frontend_semantics_owner")
            or operator_boundary.get("frontend_semantics_owner")
        ),
        "persona_core_mutation_allowed": bool(
            rc_boundary.get("persona_core_mutation_allowed")
            or operator_boundary.get("persona_core_mutation_allowed")
        ),
        "memory_write_widened": bool(
            rc_boundary.get("memory_write_widened")
            or not bool(operator_boundary.get("memory_write_follows_existing_policy", True))
        ),
        "http_server_semantics_owner": bool(rc_boundary.get("http_server_semantics_owner")),
    }


def _closed_authority_failures(boundary: dict[str, bool]) -> list[str]:
    labels = {
        "live_capture_enabled": "authority_widened:live_capture",
        "external_executor_auto_enabled": "authority_widened:external_executor_harness",
        "dynamic_skill_registry_auto_write_enabled": "authority_widened:dynamic_skill_registry",
        "multimodal_model_auto_call_enabled": "authority_widened:multimodal_model_auto_call",
        "frontend_semantics_owner": "authority_widened:frontend_semantics_owner",
        "persona_core_mutation_allowed": "authority_widened:persona_core_mutation",
        "memory_write_widened": "authority_widened:memory_write",
        "http_server_semantics_owner": "authority_widened:http_server_semantics_owner",
    }
    return [reason for key, reason in labels.items() if bool(boundary.get(key, False))]


def _panel(status: bool, **details: Any) -> dict[str, Any]:
    row = {"status": "passed" if status else "failed"}
    row.update(details)
    return row


def build_operator_console_rc_readback(
    *,
    technical_preview_rc: dict[str, Any] | None,
    runtime_status_dashboard: dict[str, Any] | None,
    operator_readback: dict[str, Any] | None,
) -> dict[str, Any]:
    rc = _dict_or_empty(technical_preview_rc)
    dashboard = _dict_or_empty(runtime_status_dashboard)
    operator = _dict_or_empty(operator_readback)
    rc_summary = _dict_or_empty(rc.get("summary"))
    dashboard_summary = _dict_or_empty(dashboard.get("summary"))
    operator_summary = _dict_or_empty(operator.get("evidence_summary"))

    route_inventory = _route_inventory(operator)
    authority_boundary = _authority_boundary(rc, operator)
    next_specs = _list_or_empty(dashboard.get("next_specs"))
    next_spec_count = max(
        _int_value(rc_summary.get("next_spec_count"), 0),
        _int_value(dashboard_summary.get("next_spec_count"), len(next_specs)),
        len(next_specs),
    )

    rc_ready = _ready(rc, "technical_preview_rc_phase1_ready")
    dashboard_ready = _ready(dashboard, "runtime_status_dashboard_ready")
    operator_ready = _ready(operator, "runtime_productization_phase2_ready")
    no_next_specs = next_spec_count == 0
    routes_closed = not route_inventory["external_mutation_routes"] and not route_inventory["frontend_semantics_owner"]
    authority_closed = not _closed_authority_failures(authority_boundary)

    failures: list[str] = []
    if not rc_ready:
        failures.append("technical_preview_rc_not_ready")
    if not dashboard_ready:
        failures.append("runtime_status_dashboard_not_ready")
    if not operator_ready:
        failures.append("operator_readback_not_ready")
    if not no_next_specs:
        failures.append("next_specs_not_empty")
    if not routes_closed:
        failures.append("route_inventory_not_read_only")
    failures.extend(_closed_authority_failures(authority_boundary))
    failures.extend(str(reason) for reason in _list_or_empty(rc.get("failure_reasons")) if str(reason))
    failures = list(dict.fromkeys(failures))

    overall = "failed" if failures else "passed"
    demo_ready = overall == "passed"
    operator_panels = {
        "rc_evidence": _panel(
            rc_ready,
            readiness_status=str(rc.get("readiness_status") or ""),
            evidence=f"{_int_value(rc_summary.get('ready_evidence_count'), 0)}/{_int_value(rc_summary.get('total_evidence_count'), 0)}",
        ),
        "runtime_status": _panel(
            dashboard_ready and no_next_specs,
            readiness_status=str(dashboard.get("readiness_status") or ""),
            gates=f"{_int_value(dashboard_summary.get('ready_gates'), 0)}/{_int_value(dashboard_summary.get('total_gates'), 0)}",
            next_spec_count=next_spec_count,
        ),
        "operator_readback": _panel(
            operator_ready,
            readiness_status=str(operator.get("readiness_status") or ""),
            inputs=f"{_int_value(operator_summary.get('ready_inputs'), 0)}/{_int_value(operator_summary.get('total_inputs'), 0)}",
        ),
        "route_inventory": _panel(
            routes_closed,
            read_only_route_count=route_inventory["route_count"],
            mutation_route_count=len(route_inventory["mutation_routes"]),
            external_mutation_route_count=len(route_inventory["external_mutation_routes"]),
            user_control_route_count=len(route_inventory["user_control_routes"]),
        ),
        "authority_boundary": _panel(
            authority_closed,
            closed=authority_closed,
        ),
    }

    next_actions = (
        [
            "open_operator_console",
            "run_operator_console_rc_audit",
            "keep_blocked_lanes_closed",
        ]
        if demo_ready
        else [
            "inspect_blocked_evidence",
            "run_technical_preview_rc_audit",
            "rerun_operator_console_rc_audit",
        ]
    )

    return {
        "schema": "operator_console_rc.v1",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": overall,
        "readiness_status": (
            OPERATOR_CONSOLE_RC_PHASE1_READY if demo_ready else OPERATOR_CONSOLE_RC_PHASE1_BLOCKED
        ),
        "console_mode": "readback_only",
        "release_posture": "technical_preview_rc" if demo_ready else "attention_required",
        "summary": {
            "demo_ready": demo_ready,
            "ready_evidence_count": _int_value(rc_summary.get("ready_evidence_count"), 0),
            "total_evidence_count": _int_value(rc_summary.get("total_evidence_count"), 0),
            "ready_gates": _int_value(dashboard_summary.get("ready_gates"), 0),
            "total_gates": _int_value(dashboard_summary.get("total_gates"), 0),
            "next_spec_count": next_spec_count,
            "blocked_lane_count": _int_value(dashboard_summary.get("blocked_lane_count"), 0),
            "route_count": route_inventory["route_count"],
        },
        "readback_refs": {
            "technical_preview_rc": _status_ref(rc, fallback_schema="technical_preview_rc.v1"),
            "runtime_status_dashboard": _status_ref(
                dashboard,
                fallback_schema="runtime_status_dashboard.v1",
            ),
            "operator_readback": _status_ref(operator, fallback_schema="operator_readback.v2"),
        },
        "operator_panels": operator_panels,
        "route_inventory": route_inventory,
        "authority_boundary": authority_boundary,
        "next_actions": next_actions,
        "failure_reasons": failures,
    }


def compact_operator_console_rc_line(readback: dict[str, Any] | None) -> str:
    data = _dict_or_empty(readback)
    summary = _dict_or_empty(data.get("summary"))
    return " | ".join(
        [
            f"operator_console_rc={str(data.get('readiness_status') or 'unknown')}",
            f"demo_ready={bool(summary.get('demo_ready', False))}",
            f"evidence={_int_value(summary.get('ready_evidence_count'), 0)}/{_int_value(summary.get('total_evidence_count'), 0)}",
            f"next_specs={_int_value(summary.get('next_spec_count'), 0)}",
            f"routes={_int_value(summary.get('route_count'), 0)}",
        ]
    )


__all__ = [
    "OPERATOR_CONSOLE_RC_PHASE1_BLOCKED",
    "OPERATOR_CONSOLE_RC_PHASE1_READY",
    "build_operator_console_rc_readback",
    "compact_operator_console_rc_line",
]
