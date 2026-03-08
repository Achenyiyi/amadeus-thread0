from __future__ import annotations

from typing import Any, TypedDict


class V2MetricSchema(TypedDict):
    ooc_rate: float
    canon_violation_rate: float
    worldline_recall_at_k: float
    commitment_fulfillment: float
    relationship_continuity: float
    citation_coverage: float
    memory_guard_block_rate: float
    bargein_recovery_rate: float


def metric_defaults() -> V2MetricSchema:
    return {
        "ooc_rate": 1.0,
        "canon_violation_rate": 0.0,
        "worldline_recall_at_k": 0.0,
        "commitment_fulfillment": 0.0,
        "relationship_continuity": 0.0,
        "citation_coverage": 0.0,
        "memory_guard_block_rate": 0.0,
        "bargein_recovery_rate": 0.0,
    }


def build_metric_snapshot(
    *,
    ooc_detector: dict[str, Any] | None = None,
    canon_guard: dict[str, Any] | None = None,
    worldline_hits: int = 0,
    worldline_total: int = 0,
    commitments_done: int = 0,
    commitments_total: int = 0,
    relationship_hits: int = 0,
    relationship_total: int = 0,
    claims_with_sources: int = 0,
    claims_total: int = 0,
    guard_blocked: int = 0,
    guard_checked: int = 0,
    bargein_recovered: int = 0,
    bargein_total: int = 0,
) -> V2MetricSchema:
    m = metric_defaults()

    risk = 0.0
    if isinstance(ooc_detector, dict):
        try:
            risk = float(ooc_detector.get("risk", 0.0) or 0.0)
        except Exception:
            risk = 0.0
    m["ooc_rate"] = max(0.0, min(1.0, risk))

    violations = 0
    if isinstance(canon_guard, dict):
        v = canon_guard.get("violations")
        if isinstance(v, list):
            violations = len(v)
    m["canon_violation_rate"] = 1.0 if violations > 0 else 0.0

    if worldline_total > 0:
        m["worldline_recall_at_k"] = max(0.0, min(1.0, float(worldline_hits) / float(worldline_total)))
    if commitments_total > 0:
        m["commitment_fulfillment"] = max(0.0, min(1.0, float(commitments_done) / float(commitments_total)))
    if relationship_total > 0:
        m["relationship_continuity"] = max(0.0, min(1.0, float(relationship_hits) / float(relationship_total)))
    if claims_total > 0:
        m["citation_coverage"] = max(0.0, min(1.0, float(claims_with_sources) / float(claims_total)))
    if guard_checked > 0:
        m["memory_guard_block_rate"] = max(0.0, min(1.0, float(guard_blocked) / float(guard_checked)))
    if bargein_total > 0:
        m["bargein_recovery_rate"] = max(0.0, min(1.0, float(bargein_recovered) / float(bargein_total)))

    return m

