from __future__ import annotations

import hashlib
import json
import re
from typing import Any


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _clean_text(value: Any, *, limit: int = 320, lower: bool = False) -> str:
    text = str(value or "").strip()[: max(1, int(limit))]
    return text.lower() if lower else text


def _dedupe_lower_list(values: Any, *, limit: int = 16) -> list[str]:
    out: list[str] = []
    for item in _list_or_empty(values):
        text = _clean_text(item, limit=120, lower=True)
        if text and text not in out:
            out.append(text)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _slug(value: Any, *, fallback: str) -> str:
    text = _clean_text(value, limit=120, lower=True)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or fallback


def _candidate_version(payload: dict[str, Any]) -> str:
    direct = _clean_text(payload.get("version"), limit=80)
    if direct:
        return direct
    draft = str(payload.get("draft_skill_md") or "")
    match = re.search(r"(?m)^version:\s*([^\n\r#]+)\s*$", draft)
    if match:
        return _clean_text(match.group(1), limit=80)
    return "0.1.0"


def _source_evidence_refs(value: Any) -> list[str]:
    out: list[str] = []
    for item in _list_or_empty(value):
        text = _clean_text(item, limit=180)
        if text and text not in out:
            out.append(text)
        if len(out) >= 16:
            break
    return out


def _hash_candidate_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(
        {
            "candidate_id": payload.get("candidate_id", ""),
            "skill_id": payload.get("skill_id", ""),
            "version": _candidate_version(payload),
            "draft_skill_md": payload.get("draft_skill_md", ""),
            "source_evidence_refs": _source_evidence_refs(payload.get("source_evidence_refs")),
            "requested_permissions": _dedupe_lower_list(payload.get("requested_permissions")),
            "sandbox_profiles": _dedupe_lower_list(payload.get("sandbox_profiles")),
        },
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _trace_completed(trace: dict[str, Any]) -> bool:
    return bool(trace.get("completed", False)) or _clean_text(trace.get("status"), lower=True) == "completed"


def propose_skill_candidate_from_trace(trace: dict[str, Any] | None) -> dict[str, Any]:
    row = _dict_or_empty(trace)
    trace_id = _clean_text(row.get("trace_id") or row.get("source_trace_id"), limit=120)
    if not _trace_completed(row):
        return {
            "candidate_id": f"skill-candidate-{_slug(trace_id, fallback='blocked')}",
            "origin": "procedural_trace",
            "skill_id": "",
            "draft_skill_md": "",
            "source_evidence_refs": [trace_id] if trace_id else [],
            "requested_permissions": [],
            "sandbox_profiles": [],
            "hash": "",
            "status": "blocked",
            "requires_approval": True,
            "registry_written": False,
            "block_reasons": ["not_completed_fact"],
        }
    summary = _clean_text(row.get("summary") or row.get("result_summary") or row.get("pattern"), limit=220)
    skill_id = _slug(row.get("skill_id") or summary, fallback="procedural-skill-candidate")
    candidate_id = f"skill-candidate-{_slug(trace_id or skill_id, fallback=skill_id)}"
    requested_permissions = _dedupe_lower_list(row.get("requested_permissions"), limit=16)
    sandbox_profiles = _dedupe_lower_list(row.get("sandbox_profiles"), limit=16) or ["docker_local_isolated"]
    draft = "\n".join(
        [
            "---",
            f"name: {skill_id}",
            f"description: Candidate skill derived from completed trace {trace_id or 'unknown'}",
            "version: 0.1.0",
            f"skill_id: {skill_id}",
            "kind: executable",
            "source: dynamic_candidate",
            "trust_tier: proposed",
            "---",
            "",
            "## Instructions",
            summary or "Reuse the completed bounded procedure only after approval.",
            "",
        ]
    )
    candidate = {
        "candidate_id": candidate_id,
        "origin": "procedural_trace",
        "skill_id": skill_id,
        "draft_skill_md": draft,
        "source_evidence_refs": [trace_id] if trace_id else [],
        "requested_permissions": requested_permissions,
        "sandbox_profiles": sandbox_profiles,
        "hash": "",
        "status": "proposed",
        "requires_approval": True,
        "registry_written": False,
        "block_reasons": [],
    }
    candidate["hash"] = _hash_candidate_payload(candidate)
    return candidate


def freeze_skill_candidate_payload(candidate: dict[str, Any] | None) -> dict[str, Any]:
    row = _dict_or_empty(candidate)
    if not row:
        return {}
    status = _clean_text(row.get("status"), lower=True)
    if status not in {"proposed", "frozen"}:
        return {
            "schema": "dynamic_skill_candidate.v1",
            "candidate_id": _clean_text(row.get("candidate_id"), limit=140),
            "skill_id": "",
            "version": "",
            "draft_skill_md": "",
            "source_evidence_refs": _source_evidence_refs(row.get("source_evidence_refs")),
            "requested_permissions": [],
            "sandbox_profiles": [],
            "hash": "",
            "status": "blocked",
            "requires_approval": True,
            "registry_written": False,
            "block_reasons": list(row.get("block_reasons") or ["not_proposed_candidate"]),
        }
    skill_id = _slug(row.get("skill_id"), fallback="procedural-skill-candidate")
    payload = {
        "schema": "dynamic_skill_candidate.v1",
        "candidate_id": _clean_text(row.get("candidate_id"), limit=140)
        or f"skill-candidate-{skill_id}",
        "origin": _clean_text(row.get("origin") or "procedural_trace", limit=80),
        "skill_id": skill_id,
        "version": _candidate_version(row),
        "draft_skill_md": str(row.get("draft_skill_md") or ""),
        "source": "dynamic_candidate",
        "source_evidence_refs": _source_evidence_refs(row.get("source_evidence_refs")),
        "requested_permissions": _dedupe_lower_list(row.get("requested_permissions"), limit=16),
        "sandbox_profiles": _dedupe_lower_list(row.get("sandbox_profiles"), limit=16),
        "hash": "",
        "status": "frozen",
        "requires_approval": True,
        "registry_written": False,
        "verification_summary": "dynamic candidate payload frozen for approval-gated install",
    }
    payload["hash"] = _hash_candidate_payload(payload)
    return payload


def build_candidate_install_packet(
    candidate: dict[str, Any] | None,
    *,
    origin: str = "capability_upgrade",
) -> dict[str, Any]:
    frozen = freeze_skill_candidate_payload(candidate)
    if not frozen or frozen.get("status") != "frozen":
        return {}
    proposal_id = _clean_text(frozen.get("candidate_id"), limit=140)
    tool_args = {
        "skill_id": _clean_text(frozen.get("skill_id"), limit=140),
        "resolved_version": _clean_text(frozen.get("version"), limit=80),
        "source": "dynamic_candidate",
        "hash": _clean_text(frozen.get("hash"), limit=128, lower=True),
        "requested_permissions": list(frozen.get("requested_permissions") or []),
        "sandbox_profiles": list(frozen.get("sandbox_profiles") or []),
        "verification_summary": _clean_text(frozen.get("verification_summary"), limit=320),
        "candidate_id": _clean_text(frozen.get("candidate_id"), limit=140),
        "candidate_hash": _clean_text(frozen.get("hash"), limit=128, lower=True),
        "candidate_payload": dict(frozen),
    }
    return {
        "proposal_id": proposal_id,
        "origin": origin if origin in {"motive_goal", "own_rhythm", "counterpart_request", "capability_upgrade"} else "capability_upgrade",
        "intent": "skills:install",
        "status": "awaiting_approval",
        "risk": "external_mutation",
        "requires_approval": True,
        "capability_steps": [
            {
                "kind": "skill_mutation",
                "name": "install_skill",
                "target": tool_args["skill_id"],
                "status": "awaiting_approval",
                "requires_approval": True,
                "note": "install frozen dynamic skill candidate after operator approval",
            }
        ],
        "expected_effect": f"install dynamic skill candidate {tool_args['skill_id']}@{tool_args['resolved_version']}",
        "result_summary": "",
        "writeback_ready": False,
        "tool_name": "install_skill",
        "tool_args": tool_args,
        "block_reason": "",
    }


def build_skill_candidate_approval(candidate: dict[str, Any] | None) -> dict[str, Any]:
    row = _dict_or_empty(candidate)
    if row.get("status") != "proposed":
        return {}
    return {
        "proposal_id": _clean_text(row.get("candidate_id"), limit=140),
        "operation": "propose_candidate",
        "candidate_id": _clean_text(row.get("candidate_id"), limit=140),
        "skill_id": _clean_text(row.get("skill_id"), limit=140),
        "source": _clean_text(row.get("origin"), limit=80),
        "hash": _clean_text(row.get("hash"), limit=128),
        "requested_permissions": list(row.get("requested_permissions") or []),
        "sandbox_profiles": list(row.get("sandbox_profiles") or []),
        "verification_summary": "candidate hash verified before any registry mutation",
        "requires_approval": True,
    }


def verify_candidate_hash(candidate: dict[str, Any] | None) -> dict[str, Any]:
    row = _dict_or_empty(candidate)
    expected = _hash_candidate_payload(row)
    actual = _clean_text(row.get("hash"), limit=128)
    return {
        "candidate_id": _clean_text(row.get("candidate_id"), limit=140),
        "expected_hash": expected,
        "actual_hash": actual,
        "verified": bool(actual and actual == expected),
    }


def verify_candidate_approval(
    candidate: dict[str, Any] | None,
    approval_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    expected = freeze_skill_candidate_payload(candidate)
    raw_actual = _dict_or_empty(approval_payload)
    actual = raw_actual.get("candidate_payload") if isinstance(raw_actual.get("candidate_payload"), dict) else raw_actual
    actual = freeze_skill_candidate_payload(actual)
    failure_reasons: list[str] = []
    if not expected or expected.get("status") != "frozen":
        failure_reasons.append("candidate_not_frozen")
    if not actual or actual.get("status") != "frozen":
        failure_reasons.append("approval_payload_not_frozen")

    comparisons = [
        ("candidate_id", "candidate_id_drift"),
        ("skill_id", "skill_id_drift"),
        ("version", "version_drift"),
        ("draft_skill_md", "draft_skill_md_drift"),
        ("hash", "hash_drift"),
    ]
    for key, reason in comparisons:
        if str(expected.get(key) or "") != str(actual.get(key) or ""):
            failure_reasons.append(reason)

    if _source_evidence_refs(expected.get("source_evidence_refs")) != _source_evidence_refs(actual.get("source_evidence_refs")):
        failure_reasons.append("source_evidence_refs_drift")
    if _dedupe_lower_list(expected.get("requested_permissions")) != _dedupe_lower_list(actual.get("requested_permissions")):
        failure_reasons.append("requested_permissions_drift")
    if _dedupe_lower_list(expected.get("sandbox_profiles")) != _dedupe_lower_list(actual.get("sandbox_profiles")):
        failure_reasons.append("sandbox_profiles_drift")
    recomputed = _hash_candidate_payload(actual)
    if str(actual.get("hash") or "") != recomputed:
        failure_reasons.append("approval_hash_invalid")

    return {
        "candidate_id": _clean_text(expected.get("candidate_id"), limit=140),
        "skill_id": _clean_text(expected.get("skill_id"), limit=140),
        "expected_hash": _clean_text(expected.get("hash"), limit=128),
        "actual_hash": _clean_text(actual.get("hash"), limit=128),
        "verified": not failure_reasons,
        "failure_reasons": failure_reasons,
    }


__all__ = [
    "build_candidate_install_packet",
    "build_skill_candidate_approval",
    "freeze_skill_candidate_payload",
    "propose_skill_candidate_from_trace",
    "verify_candidate_approval",
    "verify_candidate_hash",
]
