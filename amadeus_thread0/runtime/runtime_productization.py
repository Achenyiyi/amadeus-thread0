from __future__ import annotations

from typing import Any


RUNTIME_PRODUCTIZATION_READINESS = "runtime_productization_phase1_ready"

EXPECTED_INPUT_READINESS = {
    "post_baseline": "post_baseline_closure_ready",
    "preserved_baselines": "preserved_baselines_ready",
    "post_unlock_roadmap": "post_unlock_roadmap_ready",
}

AUTHORITY_BOUNDARY = {
    "external_mutation_requires_approval": True,
    "memory_write_follows_existing_policy": True,
    "persona_core_mutation_allowed": False,
    "frontend_semantics_owner": False,
    "dynamic_registry_write_auto_allowed": False,
    "external_harness_runtime_auto_enabled": False,
    "live_capture_auto_enabled": False,
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _status_line(value: dict[str, Any] | None) -> dict[str, str]:
    data = _dict_or_empty(value)
    return {
        "overall_status": str(data.get("overall_status") or "").strip(),
        "readiness_status": str(data.get("readiness_status") or data.get("readiness") or "").strip(),
    }


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _lane_rows(post_baseline_status: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    data = _dict_or_empty(post_baseline_status)
    items = data.get("items") if isinstance(data.get("items"), dict) else {}
    rows: dict[str, dict[str, Any]] = {}
    for item_id, raw in items.items():
        row = _dict_or_empty(raw)
        rows[str(item_id)] = {
            "status": str(row.get("status") or "").strip(),
            "runtime_available": bool(row.get("runtime_available", False)),
            "readiness_status": str(row.get("readiness_status") or row.get("readiness") or "").strip(),
            "post_unlock_lane": str(row.get("post_unlock_lane") or "").strip(),
            "blocked_surfaces": list(row.get("blocked_surfaces") or []) if isinstance(row.get("blocked_surfaces"), list) else [],
            "summary": str(row.get("summary") or "").strip(),
        }
    return rows


def _operator_snapshot(current_turn: dict[str, Any] | None) -> dict[str, Any]:
    turn = _dict_or_empty(current_turn)
    recovery = turn.get("procedural_recovery") if isinstance(turn.get("procedural_recovery"), dict) else {}
    outcome = turn.get("procedural_outcome") if isinstance(turn.get("procedural_outcome"), dict) else {}
    planning = turn.get("procedural_planning") if isinstance(turn.get("procedural_planning"), dict) else {}
    hint = turn.get("procedural_hint") if isinstance(turn.get("procedural_hint"), dict) else {}
    return {
        "autonomy_mode": str(turn.get("autonomy_mode") or "").strip(),
        "autonomy_origin": str(turn.get("autonomy_origin") or "").strip(),
        "action_packet_count": _int_value(turn.get("action_packet_count"), 0),
        "pending_approval_count": _int_value(turn.get("digital_body_pending_approval_count"), 0),
        "digital_body_surface": str(turn.get("digital_body_surface") or "").strip(),
        "digital_body_access_mode": str(turn.get("digital_body_access_mode") or "").strip(),
        "digital_body_consequence_kind": str(turn.get("digital_body_consequence_kind") or "").strip(),
        "workspace_root": str(turn.get("digital_body_workspace_root") or "").strip(),
        "procedural_hint_kind": str(hint.get("trace_kind") or "").strip(),
        "procedural_planning_bias": str(planning.get("bias_kind") or "").strip(),
        "procedural_outcome_kind": str(outcome.get("outcome_kind") or "").strip(),
        "procedural_recovery_kind": str(recovery.get("recovery_kind") or "").strip(),
    }


def evaluate_runtime_productization_contract(readback: dict[str, Any] | None) -> dict[str, Any]:
    data = _dict_or_empty(readback)
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    boundary = data.get("authority_boundary") if isinstance(data.get("authority_boundary"), dict) else {}
    failure_reasons: list[str] = []

    for key, expected in EXPECTED_INPUT_READINESS.items():
        row = inputs.get(key) if isinstance(inputs.get(key), dict) else {}
        if str(row.get("overall_status") or "").strip() != "passed" or str(row.get("readiness_status") or "").strip() != expected:
            failure_reasons.append(
                f"{key}_readiness={str(row.get('readiness_status') or 'missing')} expected={expected}"
            )

    required_boundary = {
        "external_mutation_requires_approval": True,
        "memory_write_follows_existing_policy": True,
        "persona_core_mutation_allowed": False,
        "frontend_semantics_owner": False,
        "dynamic_registry_write_auto_allowed": False,
        "external_harness_runtime_auto_enabled": False,
    }
    for key, expected in required_boundary.items():
        if bool(boundary.get(key, not expected)) != expected:
            failure_reasons.append(f"authority_boundary.{key}={boundary.get(key)!r} expected={expected!r}")

    return {
        "overall_status": "failed" if failure_reasons else "passed",
        "readiness_status": RUNTIME_PRODUCTIZATION_READINESS if not failure_reasons else "runtime_productization_phase1_in_progress",
        "failure_reasons": failure_reasons,
    }


def build_runtime_productization_readback(
    *,
    post_baseline_status: dict[str, Any] | None,
    preserved_baselines: dict[str, Any] | None,
    post_unlock_roadmap: dict[str, Any] | None,
    current_turn: dict[str, Any] | None = None,
) -> dict[str, Any]:
    inputs = {
        "post_baseline": _status_line(post_baseline_status),
        "preserved_baselines": _status_line(preserved_baselines),
        "post_unlock_roadmap": _status_line(post_unlock_roadmap),
    }
    readback = {
        "phase": "Runtime Productization Phase 1",
        "schema": "operator_readback.v1",
        "inputs": inputs,
        "lanes": _lane_rows(post_baseline_status),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "operator_snapshot": _operator_snapshot(current_turn),
    }
    contract = evaluate_runtime_productization_contract(readback)
    readback["overall_status"] = contract["overall_status"]
    readback["readiness_status"] = contract["readiness_status"]
    readback["failure_reasons"] = list(contract.get("failure_reasons") or [])
    return readback


def compact_operator_readback_line(readback: dict[str, Any] | None) -> str:
    data = _dict_or_empty(readback)
    if not data:
        return ""
    snapshot = data.get("operator_snapshot") if isinstance(data.get("operator_snapshot"), dict) else {}
    parts = [
        f"productization={str(data.get('readiness_status') or '').strip() or 'unknown'}",
        "runtime=operator_readback",
    ]
    autonomy = str(snapshot.get("autonomy_mode") or "").strip()
    if autonomy:
        parts.append(f"autonomy={autonomy}")
    packet_count = _int_value(snapshot.get("action_packet_count"), 0)
    if packet_count:
        parts.append(f"packets={packet_count}")
    body_fx = str(snapshot.get("digital_body_consequence_kind") or "").strip()
    if body_fx:
        parts.append(f"bodyfx={body_fx}")
    recovery = str(snapshot.get("procedural_recovery_kind") or "").strip()
    if recovery:
        parts.append(f"recovery={recovery}")
    return " | ".join(parts)


__all__ = [
    "AUTHORITY_BOUNDARY",
    "EXPECTED_INPUT_READINESS",
    "RUNTIME_PRODUCTIZATION_READINESS",
    "build_runtime_productization_readback",
    "compact_operator_readback_line",
    "evaluate_runtime_productization_contract",
]
