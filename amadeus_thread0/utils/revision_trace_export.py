from __future__ import annotations

from typing import Any

from ..graph_parts.digital_body_runtime import normalize_embodied_context, normalize_embodied_trace_context
from .embodied_preview import build_embodied_preview_line


def _has_signal(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return value is not None


def _sparse_embodied_payload(value: Any) -> dict[str, Any]:
    normalized = normalize_embodied_context(value)
    if not normalized:
        return {}
    return {
        key: item
        for key, item in normalized.items()
        if _has_signal(item)
    }


def _normalized_nested_payload(value: Any) -> dict[str, Any]:
    row = dict(value) if isinstance(value, dict) else {}
    if not row:
        return {}
    normalized = {}
    for key, item in row.items():
        normalized[key] = item.strip() if isinstance(item, str) else item
    for key in ("embodied_context", "digital_body_consequence"):
        embodied = _sparse_embodied_payload(row.get(key))
        if embodied:
            normalized[key] = embodied
    return normalized


def normalize_revision_trace_export(item: Any) -> dict[str, Any]:
    row = dict(item) if isinstance(item, dict) else {}
    if not row:
        return {}
    for key in (
        "content",
        "metadata",
        "behavior_action",
        "behavior_plan",
        "behavior_consequence",
        "interaction_carryover",
        "digital_body_consequence",
    ):
        normalized_nested = _normalized_nested_payload(row.get(key))
        if normalized_nested:
            row[key] = normalized_nested
    embodied = normalize_embodied_trace_context(row)
    if embodied:
        row["embodied_context"] = embodied
    preview_line = str(row.get("preview_line") or "").strip()
    if preview_line:
        row["preview_line"] = preview_line
        return row
    preview_line = build_embodied_preview_line(row)
    if preview_line:
        row["preview_line"] = preview_line
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
