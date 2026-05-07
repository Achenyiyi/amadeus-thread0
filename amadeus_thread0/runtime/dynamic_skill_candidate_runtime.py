from __future__ import annotations

from copy import deepcopy
from typing import Any


DYNAMIC_SKILL_CANDIDATE_RUNTIME_READY = "dynamic_skill_candidate_runtime_phase1_ready"
DYNAMIC_SKILL_CANDIDATE_RUNTIME_IN_PROGRESS = "dynamic_skill_candidate_runtime_phase1_in_progress"
DYNAMIC_SKILL_CANDIDATE_RUNTIME_NOT_APPLICABLE = "dynamic_skill_candidate_runtime_phase1_not_applicable"

AUTHORITY_BOUNDARY = {
    "registry_auto_write_allowed": False,
    "registry_write_requires_approval": True,
    "memory_write_allowed": False,
    "persona_core_mutation_allowed": False,
    "behavior_mutation_allowed": False,
    "proposal_becomes_fact_allowed": False,
    "model_api_call_allowed": False,
    "model_api_called": False,
    "live_capture_allowed": False,
    "frontend_semantics_owner": False,
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _clean(value: Any, *, lower: bool = False, limit: int = 240) -> str:
    text = str(value or "").strip()[: max(1, int(limit))]
    return text.lower() if lower else text


def _packet_tool_args(packet: dict[str, Any]) -> dict[str, Any]:
    return _dict_or_empty(packet.get("tool_args"))


def _candidate_payload_from_packet(packet: dict[str, Any]) -> dict[str, Any]:
    tool_args = _packet_tool_args(packet)
    payload = tool_args.get("candidate_payload")
    return _dict_or_empty(payload)


def _candidate_id_from_packet(packet: dict[str, Any]) -> str:
    tool_args = _packet_tool_args(packet)
    candidate = _candidate_payload_from_packet(packet)
    return _clean(
        tool_args.get("candidate_id")
        or candidate.get("candidate_id")
        or packet.get("proposal_id"),
        limit=160,
    )


def _candidate_hash_from_packet(packet: dict[str, Any]) -> str:
    tool_args = _packet_tool_args(packet)
    candidate = _candidate_payload_from_packet(packet)
    return _clean(
        tool_args.get("candidate_hash")
        or candidate.get("hash")
        or tool_args.get("hash"),
        lower=True,
        limit=160,
    )


def _skill_id_from_packet(packet: dict[str, Any]) -> str:
    tool_args = _packet_tool_args(packet)
    candidate = _candidate_payload_from_packet(packet)
    return _clean(tool_args.get("skill_id") or candidate.get("skill_id"), lower=True, limit=160)


def _version_from_packet(packet: dict[str, Any]) -> str:
    tool_args = _packet_tool_args(packet)
    candidate = _candidate_payload_from_packet(packet)
    return _clean(tool_args.get("resolved_version") or candidate.get("version"), limit=80)


def _source_refs_from_packet(packet: dict[str, Any]) -> list[str]:
    candidate = _candidate_payload_from_packet(packet)
    refs: list[str] = []
    for item in _list_or_empty(candidate.get("source_evidence_refs")):
        text = _clean(item, limit=180)
        if text and text not in refs:
            refs.append(text)
    return refs[:16]


def _dynamic_install_packet(packet: Any) -> bool:
    row = _dict_or_empty(packet)
    if not row:
        return False
    if _clean(row.get("tool_name"), lower=True) != "install_skill":
        return False
    tool_args = _packet_tool_args(row)
    if isinstance(tool_args.get("candidate_payload"), dict) and tool_args.get("candidate_payload"):
        return True
    if _clean(tool_args.get("source"), lower=True) == "dynamic_candidate":
        return True
    return bool(_clean(tool_args.get("candidate_id") or tool_args.get("candidate_hash")))


def _extract_action_packets(turn: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in _list_or_empty(turn.get("action_packets")):
        if isinstance(item, dict):
            rows.append(dict(item))
    autonomy = _dict_or_empty(turn.get("autonomy"))
    for item in _list_or_empty(autonomy.get("action_packets")):
        if isinstance(item, dict):
            rows.append(dict(item))
    pending = _dict_or_empty(autonomy.get("pending_approval"))
    if pending:
        rows.append(pending)
    pending_action = _dict_or_empty(turn.get("pending_action_proposal"))
    if pending_action:
        rows.append(pending_action)
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        key = (
            _clean(row.get("proposal_id"), limit=160),
            _clean(row.get("tool_name"), lower=True, limit=120),
            _candidate_id_from_packet(row),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _dynamic_skill_entries(skills: dict[str, Any], key: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in _list_or_empty(skills.get(key)):
        row = _dict_or_empty(item)
        if _clean(row.get("source"), lower=True) != "dynamic_candidate":
            continue
        out.append(row)
    return out


def _installed_lookup(skills: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _clean(item.get("skill_id"), lower=True, limit=160): item
        for item in _dynamic_skill_entries(skills, "installed")
        if _clean(item.get("skill_id"), lower=True, limit=160)
    }


def _active_lookup(skills: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _clean(item.get("skill_id"), lower=True, limit=160): item
        for item in _dynamic_skill_entries(skills, "active")
        if _clean(item.get("skill_id"), lower=True, limit=160)
    }


def _pending_skill_candidate(skills: dict[str, Any]) -> dict[str, Any]:
    pending = _dict_or_empty(skills.get("pending_approval"))
    if not pending:
        return {}
    if not bool(pending.get("dynamic_candidate", False)) and _clean(pending.get("source"), lower=True) != "dynamic_candidate":
        return {}
    return pending


def _state_from_status(status: str, *, installed: bool, active: bool) -> tuple[str, str, str]:
    if status == "completed":
        return (
            "installed_active" if active else "installed_inactive" if installed else "install_completed_without_registry_evidence",
            "approved",
            "installed" if installed else "missing_registry_evidence",
        )
    if status in {"blocked", "rejected", "failed", "expired"}:
        return "blocked", "blocked", "blocked"
    return "pending_approval", "awaiting_approval", "not_installed"


def _candidate_row_from_packet(
    packet: dict[str, Any],
    *,
    installed: dict[str, dict[str, Any]],
    active: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    status = _clean(packet.get("status"), lower=True, limit=80) or "awaiting_approval"
    candidate_id = _candidate_id_from_packet(packet)
    skill_id = _skill_id_from_packet(packet)
    version = _version_from_packet(packet)
    candidate_hash = _candidate_hash_from_packet(packet)
    installed_entry = installed.get(skill_id, {})
    active_entry = active.get(skill_id, {})
    installed_match = bool(installed_entry)
    active_match = bool(active_entry)
    candidate_state, approval_state, install_state = _state_from_status(
        status,
        installed=installed_match,
        active=active_match,
    )
    failure_reasons: list[str] = []
    if candidate_state == "blocked":
        failure_reasons.append("blocked_candidate")
    if candidate_state == "install_completed_without_registry_evidence":
        failure_reasons.append("completed_install_missing_registry_evidence")
    if installed_entry and candidate_hash and _clean(installed_entry.get("hash"), lower=True, limit=160) not in {"", candidate_hash}:
        failure_reasons.append("installed_hash_drift")
    if active_entry and candidate_hash and _clean(active_entry.get("hash"), lower=True, limit=160) not in {"", candidate_hash}:
        failure_reasons.append("active_hash_drift")
    safe_completed = status == "completed" and installed_match and not failure_reasons
    return {
        "candidate_id": candidate_id,
        "skill_id": skill_id,
        "version": version,
        "candidate_hash": candidate_hash,
        "candidate_state": candidate_state,
        "approval_state": approval_state,
        "install_state": install_state,
        "packet_status": status,
        "proposal_id": _clean(packet.get("proposal_id"), limit=160),
        "requires_approval": bool(packet.get("requires_approval", True)),
        "registry_written": installed_match,
        "active_after_install": active_match,
        "writeback_ready": bool(packet.get("writeback_ready", False)) and safe_completed,
        "source": "dynamic_candidate",
        "source_evidence_refs": _source_refs_from_packet(packet),
        "model_api_called": False,
        "memory_write_allowed": False,
        "behavior_mutation_allowed": False,
        "failure_reasons": failure_reasons,
    }


def _candidate_row_from_entry(entry: dict[str, Any], *, active: bool) -> dict[str, Any]:
    return {
        "candidate_id": _clean(entry.get("candidate_id"), limit=160),
        "skill_id": _clean(entry.get("skill_id"), lower=True, limit=160),
        "version": _clean(entry.get("version"), limit=80),
        "candidate_hash": _clean(entry.get("hash"), lower=True, limit=160),
        "candidate_state": "installed_active" if active else "installed_inactive",
        "approval_state": "approved",
        "install_state": "installed",
        "packet_status": "",
        "proposal_id": "",
        "requires_approval": True,
        "registry_written": True,
        "active_after_install": active,
        "writeback_ready": active,
        "source": "dynamic_candidate",
        "source_evidence_refs": list(entry.get("source_evidence_refs") or [])[:16],
        "model_api_called": False,
        "memory_write_allowed": False,
        "behavior_mutation_allowed": False,
        "failure_reasons": [],
    }


def _candidate_rows(turn: dict[str, Any]) -> list[dict[str, Any]]:
    skills = _dict_or_empty(turn.get("skills"))
    installed = _installed_lookup(skills)
    active = _active_lookup(skills)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    def mark_seen(row: dict[str, Any]) -> None:
        for key in (
            _clean(row.get("candidate_id"), limit=160),
            _clean(row.get("skill_id"), lower=True, limit=160),
        ):
            if key:
                seen.add(key)

    def has_seen(row: dict[str, Any]) -> bool:
        return any(
            key in seen
            for key in (
                _clean(row.get("candidate_id"), limit=160),
                _clean(row.get("skill_id"), lower=True, limit=160),
            )
            if key
        )

    for packet in _extract_action_packets(turn):
        if not _dynamic_install_packet(packet):
            continue
        row = _candidate_row_from_packet(packet, installed=installed, active=active)
        if not has_seen(row):
            mark_seen(row)
            rows.append(row)
    pending = _pending_skill_candidate(skills)
    if pending:
        row = {
            "candidate_id": _clean(pending.get("candidate_id"), limit=160),
            "skill_id": _clean(pending.get("skill_id"), lower=True, limit=160),
            "version": _clean(pending.get("resolved_version"), limit=80),
            "candidate_hash": _clean(pending.get("candidate_hash") or pending.get("hash"), lower=True, limit=160),
            "candidate_state": "pending_approval",
            "approval_state": "awaiting_approval",
            "install_state": "not_installed",
            "packet_status": "awaiting_approval",
            "proposal_id": _clean(pending.get("proposal_id"), limit=160),
            "requires_approval": True,
            "registry_written": False,
            "active_after_install": False,
            "writeback_ready": False,
            "source": "dynamic_candidate",
            "source_evidence_refs": [],
            "model_api_called": False,
            "memory_write_allowed": False,
            "behavior_mutation_allowed": False,
            "failure_reasons": [],
        }
        if not has_seen(row):
            mark_seen(row)
            rows.append(row)
    for skill_id, entry in installed.items():
        row = _candidate_row_from_entry(entry, active=skill_id in active)
        if has_seen(row):
            continue
        mark_seen(row)
        rows.append(row)
    for skill_id, entry in active.items():
        row = _candidate_row_from_entry(entry, active=True)
        if has_seen(row):
            continue
        mark_seen(row)
        rows.append(row)
    return rows[:16]


def _continuity(turn: dict[str, Any]) -> dict[str, Any]:
    consequence = _dict_or_empty(turn.get("digital_body_consequence"))
    effects = [
        item
        for item in _list_or_empty(consequence.get("skill_effects"))
        if isinstance(item, dict) and _clean(item.get("source"), lower=True) == "dynamic_candidate"
    ]
    procedural = _dict_or_empty(consequence.get("procedural_continuity"))
    kind = _clean(consequence.get("kind"), lower=True)
    primary_status = _clean(consequence.get("primary_status"), lower=True)
    if kind == "skill_usage_completed" and primary_status == "completed" and effects:
        return {
            "status": "completed_use_only",
            "capability_family": _clean(procedural.get("capability_family"), lower=True) or "skill",
            "pattern": _clean(procedural.get("pattern"), lower=True),
            "identity_safe": bool(procedural.get("identity_safe", True)),
            "effect_count": len(effects),
        }
    if effects:
        return {
            "status": "not_completed_use",
            "capability_family": "skill",
            "identity_safe": False,
            "effect_count": len(effects),
        }
    return {"status": "no_completed_dynamic_skill_use", "effect_count": 0}


def _summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "candidate_count": len(candidates),
        "pending_approval_count": sum(1 for item in candidates if item.get("candidate_state") == "pending_approval"),
        "blocked_count": sum(1 for item in candidates if item.get("candidate_state") == "blocked"),
        "installed_count": sum(1 for item in candidates if bool(item.get("registry_written", False))),
        "active_count": sum(1 for item in candidates if bool(item.get("active_after_install", False))),
        "writeback_ready_count": sum(1 for item in candidates if bool(item.get("writeback_ready", False))),
    }


def build_dynamic_skill_candidate_runtime_readback(turn: dict[str, Any] | None) -> dict[str, Any]:
    data = _dict_or_empty(turn)
    candidates = _candidate_rows(data)
    summary = _summary(candidates)
    continuity = _continuity(data)
    failure_reasons = [
        reason
        for item in candidates
        for reason in _list_or_empty(item.get("failure_reasons"))
        if _clean(reason)
    ]
    unsafe = any(reason.endswith("_drift") or reason == "completed_install_missing_registry_evidence" for reason in failure_reasons)
    if not candidates and continuity.get("status") == "no_completed_dynamic_skill_use":
        overall = "not_applicable"
        readiness = DYNAMIC_SKILL_CANDIDATE_RUNTIME_NOT_APPLICABLE
    elif unsafe:
        overall = "in_progress"
        readiness = DYNAMIC_SKILL_CANDIDATE_RUNTIME_IN_PROGRESS
    else:
        overall = "passed"
        readiness = DYNAMIC_SKILL_CANDIDATE_RUNTIME_READY
    return {
        "phase": "Dynamic Skill Candidate Runtime Phase 1",
        "schema": "dynamic_skill_candidate_runtime.v1",
        "overall_status": overall,
        "readiness_status": readiness,
        "summary": summary,
        "candidates": candidates,
        "continuity": continuity,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "failure_reasons": failure_reasons,
    }


def compact_dynamic_skill_candidate_runtime_line(readback: dict[str, Any] | None) -> str:
    data = _dict_or_empty(readback)
    summary = _dict_or_empty(data.get("summary"))
    boundary = _dict_or_empty(data.get("authority_boundary"))
    return " | ".join(
        [
            f"dynamic_skill_candidate_runtime={_clean(data.get('readiness_status')) or 'unknown'}",
            f"candidates={int(summary.get('candidate_count') or 0)}",
            f"pending={int(summary.get('pending_approval_count') or 0)}",
            f"installed={int(summary.get('installed_count') or 0)}",
            f"active={int(summary.get('active_count') or 0)}",
            f"auto_registry_write={str(bool(boundary.get('registry_auto_write_allowed', False))).lower()}",
        ]
    )


def apply_dynamic_skill_candidate_runtime_to_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = deepcopy(_dict_or_empty(payload))
    readback = build_dynamic_skill_candidate_runtime_readback(data)
    compact = {
        "schema": readback["schema"],
        "readiness_status": readback["readiness_status"],
        "summary": dict(readback.get("summary") or {}),
        "authority_boundary": dict(readback.get("authority_boundary") or {}),
        "line": compact_dynamic_skill_candidate_runtime_line(readback),
    }
    data["dynamic_skill_candidate_runtime"] = readback
    skills = _dict_or_empty(data.get("skills"))
    skills["dynamic_candidate_runtime"] = compact
    data["skills"] = skills
    operator = _dict_or_empty(data.get("operator_readback"))
    if operator:
        operator["dynamic_skill_candidate_runtime"] = compact
        data["operator_readback"] = operator
    return data


__all__ = [
    "AUTHORITY_BOUNDARY",
    "DYNAMIC_SKILL_CANDIDATE_RUNTIME_IN_PROGRESS",
    "DYNAMIC_SKILL_CANDIDATE_RUNTIME_NOT_APPLICABLE",
    "DYNAMIC_SKILL_CANDIDATE_RUNTIME_READY",
    "apply_dynamic_skill_candidate_runtime_to_payload",
    "build_dynamic_skill_candidate_runtime_readback",
    "compact_dynamic_skill_candidate_runtime_line",
]
