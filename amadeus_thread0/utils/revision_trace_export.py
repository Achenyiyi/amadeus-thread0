from __future__ import annotations

from typing import Any

from ..graph_parts.digital_body_runtime import normalize_embodied_context


def normalize_revision_trace_export(item: Any) -> dict[str, Any]:
    row = dict(item) if isinstance(item, dict) else {}
    if not row:
        return {}
    for source in (
        row,
        row.get("content"),
        row.get("metadata"),
        row.get("behavior_action"),
        row.get("behavior_plan"),
        row.get("behavior_consequence"),
        row.get("interaction_carryover"),
    ):
        if not isinstance(source, dict):
            continue
        for key in ("embodied_context", "digital_body_consequence"):
            embodied = normalize_embodied_context(source.get(key))
            if embodied:
                row["embodied_context"] = embodied
                return row
    return row


def normalize_revision_trace_exports(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        normalized = normalize_revision_trace_export(item)
        if normalized:
            out.append(normalized)
    return out


__all__ = ["normalize_revision_trace_export", "normalize_revision_trace_exports"]
