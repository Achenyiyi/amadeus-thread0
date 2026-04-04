from __future__ import annotations

from typing import Any

from .embodied_preview import build_embodied_preview_line
from ..graph_parts.digital_body_runtime import normalize_embodied_context


def _normalized_nested_payload(value: Any) -> dict[str, Any]:
    row = dict(value) if isinstance(value, dict) else {}
    if not row:
        return {}
    normalized = {}
    for key, item in row.items():
        normalized[key] = item.strip() if isinstance(item, str) else item
    for key in ("embodied_context", "digital_body_consequence"):
        embodied = normalize_embodied_context(row.get(key))
        if embodied:
            normalized[key] = embodied
    return normalized


def normalize_memory_history_export(item: Any) -> dict[str, Any]:
    row = dict(item) if isinstance(item, dict) else {}
    if not row:
        return {}
    content = row.get("content") if isinstance(row.get("content"), dict) else {}
    normalized = {**content, **row}
    normalized_content = _normalized_nested_payload(content)
    if normalized_content:
        normalized["content"] = normalized_content
    for key, value in list(normalized.items()):
        if isinstance(value, str):
            normalized[key] = value.strip()
    found_embodied = False
    for source in (row, content, row.get("metadata")):
        if not isinstance(source, dict):
            continue
        for key in ("embodied_context", "digital_body_consequence"):
            embodied = normalize_embodied_context(source.get(key))
            if embodied:
                normalized["embodied_context"] = embodied
                found_embodied = True
                break
        if found_embodied:
            break
    preview_line = str(normalized.get("preview_line") or "").strip()
    if preview_line:
        normalized["preview_line"] = preview_line
        return normalized
    preview_line = build_embodied_preview_line(normalized)
    if preview_line:
        normalized["preview_line"] = preview_line
    return normalized


def normalize_memory_history_exports(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        normalized = normalize_memory_history_export(item)
        if normalized:
            out.append(normalized)
    return out


def normalize_memory_record_export(item: Any) -> dict[str, Any]:
    return normalize_memory_history_export(item)


def normalize_memory_record_exports(items: Any) -> list[dict[str, Any]]:
    return normalize_memory_history_exports(items)


__all__ = [
    "normalize_memory_history_export",
    "normalize_memory_history_exports",
    "normalize_memory_record_export",
    "normalize_memory_record_exports",
]
