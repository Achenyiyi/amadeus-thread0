from __future__ import annotations

from typing import Any

from .memory_history_export import normalize_memory_record_export


def _coerce_positive_int(value: Any) -> int:
    try:
        coerced = int(value)
    except Exception:
        return 0
    return coerced if coerced > 0 else 0


def _normalize_source_row(item: Any, *, flatten_memory_record: bool) -> dict[str, Any]:
    row = normalize_memory_record_export(item)
    if not row:
        return {}

    normalized = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in dict(row).items()
    }
    source_id = _coerce_positive_int(normalized.get("source_id") or normalized.get("id"))
    if source_id > 0:
        normalized["id"] = source_id
        normalized["source_id"] = source_id
    else:
        normalized.pop("id", None)
        normalized.pop("source_id", None)
    return normalized


def normalize_source_ref_export(item: Any) -> dict[str, Any]:
    return _normalize_source_row(item, flatten_memory_record=True)


def normalize_source_ref_exports(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        normalized = normalize_source_ref_export(item)
        if normalized:
            out.append(normalized)
    return out


def normalize_source_material_export(item: Any) -> dict[str, Any]:
    return _normalize_source_row(item, flatten_memory_record=False)


def normalize_source_material_exports(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        normalized = normalize_source_material_export(item)
        if normalized:
            out.append(normalized)
    return out


def _build_source_lookup(source_rows: Any) -> dict[int, dict[str, Any]]:
    lookup: dict[int, dict[str, Any]] = {}
    for row in normalize_source_material_exports(source_rows):
        source_id = _coerce_positive_int(row.get("source_id") or row.get("id"))
        if source_id > 0 and source_id not in lookup:
            lookup[source_id] = row
    return lookup


def normalize_claim_link_export(
    item: Any,
    *,
    source_lookup: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    row = normalize_memory_record_export(item)
    if not row:
        return {}

    normalized = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in dict(row).items()
    }

    source_ids: list[int] = []
    seen_ids: set[int] = set()
    raw_source_ids = normalized.get("source_ids")
    if isinstance(raw_source_ids, list):
        for raw in raw_source_ids:
            source_id = _coerce_positive_int(raw)
            if source_id > 0 and source_id not in seen_ids:
                source_ids.append(source_id)
                seen_ids.add(source_id)

    nested_sources = normalize_source_material_exports(normalized.get("sources"))
    nested_by_id: dict[int, dict[str, Any]] = {}
    unbound_sources: list[dict[str, Any]] = []
    for source in nested_sources:
        source_id = _coerce_positive_int(source.get("source_id") or source.get("id"))
        if source_id > 0 and source_id not in nested_by_id:
            nested_by_id[source_id] = source
            if source_id not in seen_ids:
                source_ids.append(source_id)
                seen_ids.add(source_id)
        elif source:
            unbound_sources.append(source)

    lookup = source_lookup or {}
    ordered_sources: list[dict[str, Any]] = []
    emitted_ids: set[int] = set()
    for source_id in source_ids:
        source = nested_by_id.get(source_id) or lookup.get(source_id)
        if not isinstance(source, dict) or source_id in emitted_ids:
            continue
        material = dict(source)
        material["id"] = source_id
        material["source_id"] = source_id
        ordered_sources.append(material)
        emitted_ids.add(source_id)

    for source_id, source in nested_by_id.items():
        if source_id in emitted_ids:
            continue
        ordered_sources.append(source)
        emitted_ids.add(source_id)

    ordered_sources.extend(unbound_sources)

    normalized["claim_excerpt"] = str(normalized.get("claim_excerpt") or "").strip()
    normalized["source_ids"] = source_ids
    if ordered_sources or "sources" in normalized:
        normalized["sources"] = ordered_sources
    if not normalized["claim_excerpt"] and not source_ids and not ordered_sources:
        return {}
    return normalized


def normalize_claim_link_exports(
    items: Any,
    *,
    source_rows: Any = None,
) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    lookup = _build_source_lookup(source_rows)
    out: list[dict[str, Any]] = []
    for item in items:
        normalized = normalize_claim_link_export(item, source_lookup=lookup)
        if normalized:
            out.append(normalized)
    return out


__all__ = [
    "normalize_claim_link_export",
    "normalize_claim_link_exports",
    "normalize_source_material_export",
    "normalize_source_material_exports",
    "normalize_source_ref_export",
    "normalize_source_ref_exports",
]
