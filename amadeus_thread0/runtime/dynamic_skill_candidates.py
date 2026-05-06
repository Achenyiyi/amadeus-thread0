from __future__ import annotations

import hashlib
import json
import re
from typing import Any


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _clean_text(value: Any, *, limit: int = 320, lower: bool = False) -> str:
    text = str(value or "").strip()[: max(1, int(limit))]
    return text.lower() if lower else text


def _slug(value: Any, *, fallback: str) -> str:
    text = _clean_text(value, limit=120, lower=True)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or fallback


def _hash_candidate_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(
        {
            "candidate_id": payload.get("candidate_id", ""),
            "skill_id": payload.get("skill_id", ""),
            "draft_skill_md": payload.get("draft_skill_md", ""),
            "source_evidence_refs": payload.get("source_evidence_refs", []),
            "requested_permissions": payload.get("requested_permissions", []),
            "sandbox_profiles": payload.get("sandbox_profiles", []),
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
        "requested_permissions": [],
        "sandbox_profiles": ["docker_local_isolated"],
        "hash": "",
        "status": "proposed",
        "requires_approval": True,
        "registry_written": False,
        "block_reasons": [],
    }
    candidate["hash"] = _hash_candidate_payload(candidate)
    return candidate


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


__all__ = [
    "build_skill_candidate_approval",
    "propose_skill_candidate_from_trace",
    "verify_candidate_hash",
]
