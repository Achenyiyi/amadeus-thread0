from __future__ import annotations

from typing import Any

from .counterpart_profile import normalize_counterpart_assessment_profile
from .embodied_preview import (
    compact_counterpart_assessment_preview_line,
    compact_proactive_continuity_preview_line,
)
from .memory_history_export import normalize_memory_record_export


def _trim_text(value: Any) -> str:
    return str(value or "").strip()


def _lower_text(value: Any) -> str:
    return _trim_text(value).lower()


def _metric(value: Any, default: float = 0.0) -> float:
    try:
        return round(float(value), 3)
    except Exception:
        return round(float(default), 3)


def _int_metric(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _write_content_value(content: dict[str, Any], key: str, value: Any) -> None:
    if key in content:
        content[key] = value


def _has_profile_signal(profile: dict[str, Any]) -> bool:
    if not profile:
        return False
    if profile.get("dominant_scene_signal"):
        return True
    if any(float(profile.get(key) or 0.0) > 0.0 for key in ("openness_drive", "guarded_drive", "safety_read", "repairability", "predictability", "dependency_risk", "closeness_read")):
        return True
    if abs(float(profile.get("guard_margin") or 0.0)) > 0.0:
        return True
    scene_strengths = profile.get("scene_strengths") if isinstance(profile.get("scene_strengths"), dict) else {}
    return any(float(score or 0.0) > 0.0 for score in scene_strengths.values())


def normalize_counterpart_assessment_export(item: Any) -> dict[str, Any]:
    row = normalize_memory_record_export(item)
    if not row:
        return {}

    content = _dict_or_empty(row.get("content"))
    row["id"] = _int_metric(row.get("id"), 0)
    row["summary"] = _trim_text(row.get("summary"))
    row["stance"] = _lower_text(row.get("stance"))
    row["scene"] = _lower_text(row.get("scene"))
    row["created_at"] = _int_metric(row.get("created_at"), 0)
    row["respect_level"] = _metric(row.get("respect_level"), 0.5)
    row["reciprocity"] = _metric(row.get("reciprocity"), 0.5)
    row["boundary_pressure"] = _metric(row.get("boundary_pressure"), 0.1)
    row["reliability_read"] = _metric(row.get("reliability_read"), 0.5)
    row["event_kind"] = _lower_text(row.get("event_kind"))
    row["interaction_frame"] = _lower_text(row.get("interaction_frame"))
    row["primary_motive"] = _trim_text(row.get("primary_motive"))
    row["motive_tension"] = _trim_text(row.get("motive_tension"))
    row["goal_frame"] = _trim_text(row.get("goal_frame"))

    for key in (
        "summary",
        "stance",
        "scene",
        "created_at",
        "respect_level",
        "reciprocity",
        "boundary_pressure",
        "reliability_read",
        "event_kind",
        "interaction_frame",
        "primary_motive",
        "motive_tension",
        "goal_frame",
    ):
        _write_content_value(content, key, row.get(key))

    profile = normalize_counterpart_assessment_profile(row)
    if _has_profile_signal(profile):
        row["assessment_profile"] = profile
        if content and "assessment_profile" in content:
            content["assessment_profile"] = profile
    elif isinstance(row.get("assessment_profile"), dict):
        row.pop("assessment_profile", None)
        if content:
            content.pop("assessment_profile", None)

    if content:
        row["content"] = content

    preview_line = compact_counterpart_assessment_preview_line(row)
    if preview_line:
        row["preview_line"] = preview_line
    else:
        preview_line = _trim_text(row.get("preview_line"))
        if preview_line:
            row["preview_line"] = preview_line
    return row


def normalize_counterpart_assessment_exports(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        normalized = normalize_counterpart_assessment_export(item)
        if normalized:
            out.append(normalized)
    return out


def normalize_proactive_continuity_export(item: Any) -> dict[str, Any]:
    row = normalize_memory_record_export(item)
    if not row:
        return {}

    content = _dict_or_empty(row.get("content"))
    row["id"] = _int_metric(row.get("id"), 0)
    row["summary"] = _trim_text(row.get("summary"))
    row["kind"] = _lower_text(row.get("kind"))
    row["trace_family"] = _lower_text(row.get("trace_family"))
    row["source_event_kind"] = _lower_text(row.get("source_event_kind"))
    row["trigger_family"] = _lower_text(row.get("trigger_family"))
    row["carryover_mode"] = _lower_text(row.get("carryover_mode"))
    row["relationship_weather"] = _lower_text(row.get("relationship_weather"))
    row["counterpart_scene_bias"] = _lower_text(row.get("counterpart_scene_bias"))
    row["created_at"] = _int_metric(row.get("created_at"), 0)
    row["hold_count"] = _int_metric(row.get("hold_count"), 0)
    row["long_term_axis_count"] = _int_metric(row.get("long_term_axis_count"), 0)
    row["carryover_strength"] = _metric(row.get("carryover_strength"), 0.0)
    row["recontact_cooldown"] = _metric(row.get("recontact_cooldown"), 0.0)
    row["presence_residue"] = _metric(row.get("presence_residue"), 0.0)
    row["ambient_resonance"] = _metric(row.get("ambient_resonance"), 0.0)
    row["self_activity_momentum"] = _metric(row.get("self_activity_momentum"), 0.0)
    row["continuity_anchor"] = _metric(row.get("continuity_anchor"), 0.0)
    row["own_rhythm_anchor"] = _metric(row.get("own_rhythm_anchor"), 0.0)
    row["recontact_anchor"] = _metric(row.get("recontact_anchor"), 0.0)
    row["boundary_anchor"] = _metric(row.get("boundary_anchor"), 0.0)
    row["memory_anchor"] = _metric(row.get("memory_anchor"), 0.0)
    row["semantic_continuity_depth"] = _metric(row.get("semantic_continuity_depth"), 0.0)
    row["semantic_identity_gravity"] = _metric(row.get("semantic_identity_gravity"), 0.0)
    row["lineage_gravity"] = _metric(row.get("lineage_gravity"), 0.0)
    row["contact_lineage"] = _metric(row.get("contact_lineage"), 0.0)
    row["repair_lineage"] = _metric(row.get("repair_lineage"), 0.0)
    row["boundary_lineage"] = _metric(row.get("boundary_lineage"), 0.0)
    row["selfhood_lineage"] = _metric(row.get("selfhood_lineage"), 0.0)
    row["agency_lineage"] = _metric(row.get("agency_lineage"), 0.0)
    row["own_rhythm_bias"] = _metric(row.get("own_rhythm_bias"), 0.0)
    row["counterpart_boundary_delta"] = _metric(row.get("counterpart_boundary_delta"), 0.0)
    row["primary_motive"] = _trim_text(row.get("primary_motive"))
    row["motive_tension"] = _trim_text(row.get("motive_tension"))
    row["goal_frame"] = _trim_text(row.get("goal_frame"))

    for key in (
        "summary",
        "kind",
        "trace_family",
        "source_event_kind",
        "trigger_family",
        "carryover_mode",
        "relationship_weather",
        "counterpart_scene_bias",
        "created_at",
        "hold_count",
        "long_term_axis_count",
        "carryover_strength",
        "recontact_cooldown",
        "presence_residue",
        "ambient_resonance",
        "self_activity_momentum",
        "continuity_anchor",
        "own_rhythm_anchor",
        "recontact_anchor",
        "boundary_anchor",
        "memory_anchor",
        "semantic_continuity_depth",
        "semantic_identity_gravity",
        "lineage_gravity",
        "contact_lineage",
        "repair_lineage",
        "boundary_lineage",
        "selfhood_lineage",
        "agency_lineage",
        "own_rhythm_bias",
        "counterpart_boundary_delta",
        "primary_motive",
        "motive_tension",
        "goal_frame",
    ):
        _write_content_value(content, key, row.get(key))

    if content:
        row["content"] = content

    preview_line = compact_proactive_continuity_preview_line(row)
    if preview_line:
        row["preview_line"] = preview_line
    else:
        preview_line = _trim_text(row.get("preview_line"))
        if preview_line:
            row["preview_line"] = preview_line
    return row


def normalize_proactive_continuity_exports(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        normalized = normalize_proactive_continuity_export(item)
        if normalized:
            out.append(normalized)
    return out


__all__ = [
    "normalize_counterpart_assessment_export",
    "normalize_counterpart_assessment_exports",
    "normalize_proactive_continuity_export",
    "normalize_proactive_continuity_exports",
]
