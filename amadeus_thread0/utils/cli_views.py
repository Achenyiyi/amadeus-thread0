from __future__ import annotations

from typing import Any

from ..graph_parts.procedural_planning import normalize_procedural_planning
from ..graph_parts.relational_runtime import _counterpart_assessment_profile
from ..runtime.runtime_productization import compact_operator_readback_line
from .embodied_preview import (
    compact_counterpart_assessment_preview_line as _shared_compact_counterpart_assessment_preview_line,
    compact_event_residue_preview_line as _shared_compact_event_residue_preview_line,
    compact_proactive_continuity_preview_line as _shared_compact_proactive_continuity_preview_line,
    compact_source_anchor_parts as _shared_compact_source_anchor_parts,
    render_embodied_context_text as _shared_render_embodied_context_text,
)
from .relational_history_export import (
    normalize_counterpart_assessment_exports,
    normalize_proactive_continuity_exports,
)
from .turn_summary_export import (
    summarize_agenda_lifecycle,
    summarize_behavior_consequence,
    summarize_digital_body,
    summarize_digital_body_consequence,
    summarize_embodied_context,
    summarize_event_residue,
    summarize_interaction_carryover,
    summarize_opening_window_profile,
    summarize_procedural_growth,
    summarize_procedural_outcome,
    summarize_procedural_recovery,
)

_SEMANTIC_ANCHOR_FLOAT_KEYS = (
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
)


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


def _clean_list(values: Any, *, limit: int = 4) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if not text:
            continue
        out.append(text)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _clean_int_list(values: Any, *, limit: int = 8) -> list[int]:
    if not isinstance(values, list):
        return []
    out: list[int] = []
    for item in values:
        try:
            number = int(item)
        except Exception:
            continue
        if number <= 0:
            continue
        out.append(number)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _focus_preview_text(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    return str(item.get("summary") or item.get("text") or item.get("label") or "").strip()


def _focus_preview(worldline_focus: Any, *, limit: int = 3) -> list[str]:
    if not isinstance(worldline_focus, list):
        return []
    out: list[str] = []
    for item in worldline_focus:
        text = _focus_preview_text(item)
        if not text:
            continue
        out.append(text[:120])
        if len(out) >= max(1, int(limit)):
            break
    return out


def _focus_preview_items(worldline_focus: Any, *, limit: int = 3) -> list[dict[str, Any]]:
    if not isinstance(worldline_focus, list):
        return []
    out: list[dict[str, Any]] = []
    for item in worldline_focus:
        text = _focus_preview_text(item)
        if not text:
            continue
        out.append(
            {
                "id": _int_metric(item.get("id"), 0),
                "kind": str(item.get("focus_kind") or item.get("category") or "memory").strip() or "memory",
                "text": text[:120],
                "status": str(item.get("status") or "").strip(),
                "due_at": str(item.get("due_at") or "").strip(),
                "severity": _metric(item.get("severity"), 0.0),
                "affinity_delta": _metric(item.get("affinity_delta"), 0.0),
                "trust_delta": _metric(item.get("trust_delta"), 0.0),
                "created_at": _int_metric(item.get("created_at"), 0),
                "updated_at": _int_metric(item.get("updated_at"), 0),
            }
        )
        if len(out) >= max(1, int(limit)):
            break
    return out


def _top_narrative_preview(top_narratives: Any, *, limit: int = 3) -> list[dict[str, Any]]:
    if not isinstance(top_narratives, list):
        return []
    out: list[dict[str, Any]] = []
    for item in top_narratives:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "category": str(item.get("category") or "").strip(),
                "score": _metric(item.get("score"), 0.0),
                "reactivated": bool(item.get("reactivated", False)),
                "text": str(item.get("text") or "").strip()[:120],
                "primary_motive": str(item.get("primary_motive") or "").strip(),
                "motive_tension": str(item.get("motive_tension") or "").strip(),
                "counterpart_snapshot": _narrative_counterpart_preview(item.get("counterpart_snapshot")),
                "proactive_continuity": _narrative_proactive_preview(item.get("proactive_continuity")),
            }
        )
        if len(out) >= max(1, int(limit)):
            break
    return out


def _narrative_counterpart_preview(counterpart: Any) -> dict[str, Any]:
    if not isinstance(counterpart, dict) or not counterpart:
        return {}
    preview = {
        "stance": str(counterpart.get("counterpart_stance") or "").strip(),
        "scene": str(counterpart.get("counterpart_scene") or "").strip(),
        "respect_level": _metric(counterpart.get("counterpart_respect_level"), 0.0),
        "reciprocity": _metric(counterpart.get("counterpart_reciprocity"), 0.0),
        "boundary_pressure": _metric(counterpart.get("counterpart_boundary_pressure"), 0.0),
        "reliability_read": _metric(counterpart.get("counterpart_reliability_read"), 0.0),
        "profile": dict(counterpart.get("counterpart_profile"))
        if isinstance(counterpart.get("counterpart_profile"), dict)
        else {},
        "support_count": _int_metric(counterpart.get("counterpart_support_count"), 0),
        "support_mass": _metric(counterpart.get("counterpart_support_mass"), 0.0),
        "confidence_avg": _metric(counterpart.get("counterpart_confidence_avg"), 0.0),
        "fresh_ratio": _metric(counterpart.get("counterpart_fresh_ratio"), 0.0),
    }
    if any(
        (
            preview["stance"],
            preview["scene"],
            preview["profile"],
            preview["support_count"] > 0,
            preview["respect_level"] > 0.0,
            preview["reciprocity"] > 0.0,
            preview["boundary_pressure"] > 0.0,
            preview["reliability_read"] > 0.0,
            preview["support_mass"] > 0.0,
            preview["confidence_avg"] > 0.0,
            preview["fresh_ratio"] > 0.0,
        )
    ):
        return preview
    return {}


def _narrative_proactive_preview(proactive: Any) -> dict[str, Any]:
    if not isinstance(proactive, dict) or not proactive:
        return {}
    preview = {
        "score": _metric(proactive.get("_score"), 0.0),
        "continuity_anchor": _metric(proactive.get("continuity_anchor"), 0.0),
        "own_rhythm_anchor": _metric(proactive.get("own_rhythm_anchor"), 0.0),
        "recontact_anchor": _metric(proactive.get("recontact_anchor"), 0.0),
        "boundary_anchor": _metric(proactive.get("boundary_anchor"), 0.0),
        "memory_anchor": _metric(proactive.get("memory_anchor"), 0.0),
        "semantic_continuity_depth": _metric(proactive.get("semantic_continuity_depth"), 0.0),
        "semantic_identity_gravity": _metric(proactive.get("semantic_identity_gravity"), 0.0),
        "lineage_gravity": _metric(proactive.get("lineage_gravity"), 0.0),
        "contact_lineage": _metric(proactive.get("contact_lineage"), 0.0),
        "repair_lineage": _metric(proactive.get("repair_lineage"), 0.0),
        "boundary_lineage": _metric(proactive.get("boundary_lineage"), 0.0),
        "selfhood_lineage": _metric(proactive.get("selfhood_lineage"), 0.0),
        "agency_lineage": _metric(proactive.get("agency_lineage"), 0.0),
        "long_term_axis_count": _int_metric(proactive.get("long_term_axis_count"), 0),
    }
    if any(
        float(preview.get(key) or 0.0) > 0.0
        for key in preview
        if key != "long_term_axis_count"
    ) or preview["long_term_axis_count"] > 0:
        return preview
    return {}


def _long_term_identity_preview(items: Any, *, limit: int = 3) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "category": str(item.get("category") or "").strip(),
                "score": _metric(item.get("score"), 0.0),
                "horizon_tag": str(item.get("horizon_tag") or "").strip(),
                "text": str(item.get("text") or "").strip()[:120],
                "prompt_text": str(item.get("prompt_text") or "").strip()[:120],
                "primary_motive": str(item.get("primary_motive") or "").strip(),
                "motive_tension": str(item.get("motive_tension") or "").strip(),
                "sedimentation_score": _metric(item.get("sedimentation_score"), 0.0),
                "persistence_score": _metric(item.get("persistence_score"), 0.0),
                "integration_score": _metric(item.get("integration_score"), 0.0),
                "support_span_s": _int_metric(item.get("support_span_s"), 0),
                "reactivation_hits": _int_metric(item.get("reactivation_hits"), 0),
                "identity_strength": _metric(item.get("identity_strength"), 0.0),
                "lineage_depth": _metric(item.get("lineage_depth"), 0.0),
                "counterpart_snapshot": _narrative_counterpart_preview(item.get("counterpart_snapshot")),
                "proactive_continuity": _narrative_proactive_preview(item.get("proactive_continuity")),
            }
        )
        if len(out) >= max(1, int(limit)):
            break
    return out


def _window_profile_summary(profile: Any) -> dict[str, Any]:
    return summarize_opening_window_profile(profile)


def _embodied_context_summary(state: Any) -> dict[str, Any]:
    return summarize_embodied_context(state)


def _history_embodied_context(*sources: Any) -> dict[str, Any]:
    for source in sources:
        if not isinstance(source, dict):
            continue
        for key in ("embodied_context", "digital_body_consequence"):
            candidate = source.get(key)
            if isinstance(candidate, dict):
                embodied = _embodied_context_summary(candidate)
                if embodied:
                    return embodied
    return {}


def _compact_source_anchor_parts(
    state: Any,
    *,
    label_fallback: str = "",
    include_refs: bool = True,
) -> list[str]:
    return _shared_compact_source_anchor_parts(
        state,
        label_fallback=label_fallback,
        include_refs=include_refs,
    )


def _render_embodied_context_text(state: Any) -> str:
    return _shared_render_embodied_context_text(state)


def _compact_counterpart_assessment_preview_line(row: dict[str, Any] | None) -> str:
    return _shared_compact_counterpart_assessment_preview_line(row)


def _compact_proactive_continuity_preview_line(row: dict[str, Any] | None) -> str:
    return _shared_compact_proactive_continuity_preview_line(row)


def _compact_event_residue_preview_line(summary: dict[str, Any] | None) -> str:
    return _shared_compact_event_residue_preview_line(summary)


def _interaction_carryover_summary(carryover: Any) -> dict[str, Any]:
    return summarize_interaction_carryover(carryover)


def _event_residue_summary(current_event: Any, *, digital_body_consequence: Any = None) -> dict[str, Any]:
    return summarize_event_residue(current_event, digital_body_consequence=digital_body_consequence)


def _agenda_lifecycle_summary(residue: Any) -> dict[str, Any]:
    return summarize_agenda_lifecycle(residue)


def _behavior_consequence_summary(consequence: Any) -> dict[str, Any]:
    return summarize_behavior_consequence(consequence)


def _digital_body_summary(state: Any) -> dict[str, Any]:
    return summarize_digital_body(state)


def _digital_body_consequence_summary(state: Any) -> dict[str, Any]:
    return summarize_digital_body_consequence(state)


def build_behavior_queue_cli_summary(queue: Any, *, limit: int = 3) -> list[dict[str, Any]]:
    if not isinstance(queue, list):
        return []
    out: list[dict[str, Any]] = []
    for item in queue:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip()
        if not kind:
            continue
        out.append(
            {
                "agenda_id": str(item.get("agenda_id") or "").strip(),
                "kind": kind,
                "target": str(item.get("target") or "").strip(),
                "status": str(item.get("status") or "").strip(),
                "trigger_family": str(item.get("trigger_family") or "").strip(),
                "scheduled_after_min": _int_metric(item.get("scheduled_after_min"), 0),
                "expires_after_min": _int_metric(item.get("expires_after_min"), 0),
                "priority": _metric(item.get("priority"), 0.0),
                "base_priority": _metric(item.get("base_priority"), 0.0),
                "hold_count": _int_metric(item.get("hold_count"), 0),
                "last_recheck_at_min": _int_metric(item.get("last_recheck_at_min"), 0),
                "allow_interrupt": bool(item.get("allow_interrupt", True)),
                "primary_motive": str(item.get("primary_motive") or "").strip(),
                "motive_tension": str(item.get("motive_tension") or "").strip(),
                "goal_frame": str(item.get("goal_frame") or "").strip()[:160],
                "source_event_kind": str(item.get("source_event_kind") or "").strip(),
                "created_at": _int_metric(item.get("created_at"), 0),
                "carryover_mode": str(item.get("carryover_mode") or "").strip(),
                "carryover_strength": _metric(item.get("carryover_strength"), 0.0),
                "relationship_weather": str(item.get("relationship_weather") or "").strip(),
                "presence_residue": _metric(item.get("presence_residue"), 0.0),
                "ambient_resonance": _metric(item.get("ambient_resonance"), 0.0),
                "self_activity_momentum": _metric(item.get("self_activity_momentum"), 0.0),
                "attention_target": str(item.get("attention_target") or "").strip(),
                "nonverbal_signal": str(item.get("nonverbal_signal") or "").strip(),
                "continuity_anchor": _metric(item.get("continuity_anchor"), 0.0),
                "own_rhythm_anchor": _metric(item.get("own_rhythm_anchor"), 0.0),
                "recontact_anchor": _metric(item.get("recontact_anchor"), 0.0),
                "boundary_anchor": _metric(item.get("boundary_anchor"), 0.0),
                "memory_anchor": _metric(item.get("memory_anchor"), 0.0),
                "semantic_continuity_depth": _metric(item.get("semantic_continuity_depth"), 0.0),
                "semantic_identity_gravity": _metric(item.get("semantic_identity_gravity"), 0.0),
                "lineage_gravity": _metric(item.get("lineage_gravity"), 0.0),
                "contact_lineage": _metric(item.get("contact_lineage"), 0.0),
                "repair_lineage": _metric(item.get("repair_lineage"), 0.0),
                "boundary_lineage": _metric(item.get("boundary_lineage"), 0.0),
                "selfhood_lineage": _metric(item.get("selfhood_lineage"), 0.0),
                "agency_lineage": _metric(item.get("agency_lineage"), 0.0),
                "long_term_axis_count": _int_metric(item.get("long_term_axis_count"), 0),
                "note": str(item.get("note") or "").strip()[:160],
            }
        )
        if len(out) >= max(1, int(limit)):
            break
    return out


def render_action_packet_cli_text(packets: Any, *, limit: int = 4) -> str:
    if not isinstance(packets, list) or not packets:
        return "- no action packets"
    rows: list[str] = []
    for item in packets[: max(1, int(limit))]:
        if not isinstance(item, dict):
            continue
        proposal_id = str(item.get("proposal_id") or "").strip() or "-"
        intent = str(item.get("intent") or "").strip() or "-"
        status = str(item.get("status") or "").strip() or "-"
        risk = str(item.get("risk") or "").strip() or "-"
        origin = str(item.get("origin") or "").strip() or "-"
        effect = str(item.get("expected_effect") or item.get("result_summary") or "").strip()
        execution_result = item.get("execution_result") if isinstance(item.get("execution_result"), dict) else {}
        execution_preview = item.get("execution_preview") if isinstance(item.get("execution_preview"), dict) else {}
        execution_spec = item.get("execution_spec") if isinstance(item.get("execution_spec"), dict) else {}
        line = f"- {proposal_id} | {origin} | {intent} | {status} | {risk}"
        if effect:
            line += " | " + effect[:120]
        runner_kind = str(execution_preview.get("runner_kind") or execution_spec.get("runner_kind") or "").strip()
        workspace_root_kind = str(
            execution_preview.get("workspace_root_kind")
            or execution_spec.get("workspace_root_kind")
            or ""
        ).strip()
        if runner_kind:
            line += f" | runner={runner_kind}"
        if workspace_root_kind:
            line += f" | root={workspace_root_kind}"
        if execution_result:
            run_id = str(execution_result.get("run_id") or "").strip()
            exit_code = execution_result.get("exit_code")
            if run_id:
                line += f" | run={run_id}"
            if isinstance(exit_code, int):
                line += f" | exit={exit_code}"
        rows.append(line)
    return "\n".join(rows) if rows else "- no action packets"


def render_autonomy_cli_text(autonomy: Any) -> str:
    if not isinstance(autonomy, dict) or not autonomy:
        return "- no autonomy state"
    intent = autonomy.get("intent") if isinstance(autonomy.get("intent"), dict) else {}
    pending = autonomy.get("pending_approval") if isinstance(autonomy.get("pending_approval"), dict) else {}
    trace = autonomy.get("execution_trace") if isinstance(autonomy.get("execution_trace"), list) else []
    block_reason = str(autonomy.get("block_reason") or "").strip()
    parts = [
        "mode=" + (str(intent.get("mode") or "").strip() or "-"),
        "origin=" + (str(intent.get("origin") or "").strip() or "-"),
        "confidence=" + f"{_metric(intent.get('confidence'), 0.0):.3f}",
        "packets=" + str(len(autonomy.get("action_packets") if isinstance(autonomy.get("action_packets"), list) else [])),
    ]
    if pending:
        parts.append("pending=" + (str(pending.get("proposal_id") or "").strip() or "-"))
    if trace:
        last = trace[-1] if isinstance(trace[-1], dict) else {}
        if last:
            parts.append("last=" + (str(last.get("event") or "").strip() or "-"))
    if block_reason:
        parts.append("block=" + block_reason[:80])
    return " | ".join(parts)


def render_behavior_queue_cli_text(queue: Any, *, limit: int = 3) -> str:
    rows = build_behavior_queue_cli_summary(queue, limit=limit)
    if not rows:
        return "- (empty)"
    lines: list[str] = []
    for idx, row in enumerate(rows, start=1):
        header = (
            f"- #{idx} {row['kind']}"
            + (f"/{row['trigger_family']}" if row.get("trigger_family") else "")
            + f" status={row['status'] or 'pending'}"
            + f" p={_metric(row.get('priority'), 0.0):.3f}"
            + f" after={_int_metric(row.get('scheduled_after_min'), 0)}m"
        )
        if _int_metric(row.get("expires_after_min"), 0) > 0:
            header += f" exp={_int_metric(row.get('expires_after_min'), 0)}m"
        if _int_metric(row.get("hold_count"), 0) > 0:
            header += f" holds={_int_metric(row.get('hold_count'), 0)}"
        lines.append(header)
        residue = (
            f"  carry={row['carryover_mode'] or '-'}:{_metric(row.get('carryover_strength'), 0.0):.3f}"
            + f" residue={_metric(row.get('presence_residue'), 0.0):.3f}/"
            + f"{_metric(row.get('ambient_resonance'), 0.0):.3f}/"
            + f"{_metric(row.get('self_activity_momentum'), 0.0):.3f}"
        )
        if row.get("relationship_weather"):
            residue += f" weather={row['relationship_weather']}"
        if row.get("attention_target"):
            residue += f" target={row['attention_target']}"
        if row.get("source_event_kind"):
            residue += f" event={row['source_event_kind']}"
        if not bool(row.get("allow_interrupt", True)):
            residue += " interrupt=no"
        lines.append(residue)
        motive_bits = [str(row.get("primary_motive") or "").strip(), str(row.get("motive_tension") or "").strip()]
        motive_bits = [bit for bit in motive_bits if bit]
        if motive_bits or row.get("goal_frame"):
            detail = ""
            if motive_bits:
                detail += "  motive=" + " / ".join(motive_bits)
            if row.get("goal_frame"):
                detail += (" | " if detail else "  ") + f"goal={row['goal_frame']}"
            lines.append(detail)
        has_anchor_signal = any(
            float(row.get(key) or 0.0) > 0.0
            for key in (
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
            )
        ) or _int_metric(row.get("long_term_axis_count"), 0) > 0
        if has_anchor_signal:
            lines.append(
                "  anchors="
                + f"{_metric(row.get('continuity_anchor'), 0.0):.2f}/"
                + f"{_metric(row.get('own_rhythm_anchor'), 0.0):.2f}/"
                + f"{_metric(row.get('recontact_anchor'), 0.0):.2f}/"
                + f"{_metric(row.get('boundary_anchor'), 0.0):.2f}/"
                + f"{_metric(row.get('memory_anchor'), 0.0):.2f}"
                + " semantic="
                + f"{_metric(row.get('semantic_continuity_depth'), 0.0):.2f}/"
                + f"{_metric(row.get('semantic_identity_gravity'), 0.0):.2f}"
            )
            lines.append(
                "  lineage="
                + f"{_metric(row.get('lineage_gravity'), 0.0):.2f}/"
                + f"{_metric(row.get('contact_lineage'), 0.0):.2f}/"
                + f"{_metric(row.get('repair_lineage'), 0.0):.2f}/"
                + f"{_metric(row.get('boundary_lineage'), 0.0):.2f}/"
                + f"{_metric(row.get('selfhood_lineage'), 0.0):.2f}/"
                + f"{_metric(row.get('agency_lineage'), 0.0):.2f}"
                + f" axes={_int_metric(row.get('long_term_axis_count'), 0)}"
            )
        if row.get("note"):
            lines.append(f"  note={row['note']}")
    return "\n".join(lines)


def build_counterpart_assessment_cli_summary(history: Any, *, limit: int = 5) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in normalize_counterpart_assessment_exports(history):
        if not isinstance(item, dict):
            continue
        summary = str(item.get("summary") or "").strip()
        stance = str(item.get("stance") or "").strip().lower()
        scene = str(item.get("scene") or "").strip().lower()
        if not any((summary, stance, scene)):
            continue
        row = {
            "id": _int_metric(item.get("id"), 0),
            "summary": summary,
            "stance": stance,
            "scene": scene,
            "created_at": _int_metric(item.get("created_at"), 0),
            "respect_level": _metric(item.get("respect_level"), 0.5),
            "reciprocity": _metric(item.get("reciprocity"), 0.5),
            "boundary_pressure": _metric(item.get("boundary_pressure"), 0.1),
            "reliability_read": _metric(item.get("reliability_read"), 0.5),
            "event_kind": str(item.get("event_kind") or "").strip(),
            "interaction_frame": str(item.get("interaction_frame") or "").strip(),
            "primary_motive": str(item.get("primary_motive") or "").strip(),
            "motive_tension": str(item.get("motive_tension") or "").strip(),
            "goal_frame": str(item.get("goal_frame") or "").strip(),
        }
        profile = item.get("assessment_profile") if isinstance(item.get("assessment_profile"), dict) else {}
        if profile:
            row["assessment_profile"] = profile
        embodied_context = _history_embodied_context(item)
        if embodied_context:
            row["embodied_context"] = embodied_context
        preview_line = str(item.get("preview_line") or "").strip() or _compact_counterpart_assessment_preview_line(row)
        if preview_line:
            row["preview_line"] = preview_line
        out.append(row)
    capped = max(1, int(limit))
    return out[-capped:]


def render_counterpart_assessment_cli_text(history: Any, *, limit: int = 5) -> str:
    rows = build_counterpart_assessment_cli_summary(history, limit=limit)
    if not rows:
        return "- (empty)"
    lines: list[str] = []
    for row in rows:
        header = (
            f"- #{row['id']} {row['stance'] or '-'}"
            + (f"/{row['scene']}" if row.get("scene") else "")
            + f" respect={_metric(row.get('respect_level'), 0.5):.2f}"
            + f" reciprocity={_metric(row.get('reciprocity'), 0.5):.2f}"
            + f" pressure={_metric(row.get('boundary_pressure'), 0.1):.2f}"
            + f" reliability={_metric(row.get('reliability_read'), 0.5):.2f}"
        )
        if row.get("event_kind"):
            header += f" event={row['event_kind']}"
        if row.get("interaction_frame"):
            header += f" frame={row['interaction_frame']}"
        lines.append(header)
        if row.get("summary"):
            lines.append(f"  {row['summary']}")
        profile = row.get("assessment_profile") if isinstance(row.get("assessment_profile"), dict) else {}
        if profile:
            scene_strengths = profile.get("scene_strengths") if isinstance(profile.get("scene_strengths"), dict) else {}
            dominant = str(profile.get("dominant_scene_signal") or "").strip()
            dominant_score = _metric(scene_strengths.get(dominant), 0.0) if dominant else 0.0
            lines.append(
                "  read="
                + (f"{dominant}:{dominant_score:.2f} " if dominant else "")
                + f"open={_metric(profile.get('openness_drive'), 0.0):.2f} "
                + f"guard={_metric(profile.get('guarded_drive'), 0.0):.2f} "
                + f"margin={_metric(profile.get('guard_margin'), 0.0):.2f}"
            )
            lines.append(
                "  counterpart="
                + f"safe={_metric(profile.get('safety_read'), 0.0):.2f} "
                + f"repair={_metric(profile.get('repairability'), 0.0):.2f} "
                + f"predict={_metric(profile.get('predictability'), 0.0):.2f} "
                + f"risk={_metric(profile.get('dependency_risk'), 0.0):.2f} "
                + f"close={_metric(profile.get('closeness_read'), 0.0):.2f}"
            )
        embodied_line = _render_embodied_context_text(row.get("embodied_context"))
        if embodied_line:
            lines.append("  " + embodied_line)
        motive_bits = [str(row.get("primary_motive") or "").strip(), str(row.get("motive_tension") or "").strip()]
        motive_bits = [bit for bit in motive_bits if bit]
        if motive_bits or row.get("goal_frame"):
            detail = ""
            if motive_bits:
                detail += "  motive=" + " / ".join(motive_bits)
            if row.get("goal_frame"):
                detail += (" | " if detail else "  ") + f"goal={row['goal_frame']}"
            lines.append(detail)
    return "\n".join(lines)


def build_proactive_continuity_cli_summary(history: Any, *, limit: int = 5) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in normalize_proactive_continuity_exports(history):
        if not isinstance(item, dict):
            continue
        summary = str(item.get("summary") or "").strip()
        kind = str(item.get("kind") or "").strip().lower()
        trace_family = str(item.get("trace_family") or "").strip().lower()
        carryover_mode = str(item.get("carryover_mode") or "").strip().lower()
        if not any((summary, kind, trace_family, carryover_mode)):
            continue
        row = {
            "id": _int_metric(item.get("id"), 0),
            "summary": summary,
            "kind": kind,
            "trace_family": trace_family,
            "source_event_kind": str(item.get("source_event_kind") or "").strip().lower(),
            "trigger_family": str(item.get("trigger_family") or "").strip().lower(),
            "carryover_mode": carryover_mode,
            "relationship_weather": str(item.get("relationship_weather") or "").strip().lower(),
            "counterpart_scene_bias": str(item.get("counterpart_scene_bias") or "").strip().lower(),
            "hold_count": _int_metric(item.get("hold_count"), 0),
            "carryover_strength": _metric(item.get("carryover_strength"), 0.0),
            "recontact_cooldown": _metric(item.get("recontact_cooldown"), 0.0),
            "presence_residue": _metric(item.get("presence_residue"), 0.0),
            "ambient_resonance": _metric(item.get("ambient_resonance"), 0.0),
            "self_activity_momentum": _metric(item.get("self_activity_momentum"), 0.0),
            "continuity_anchor": _metric(item.get("continuity_anchor"), 0.0),
            "own_rhythm_anchor": _metric(item.get("own_rhythm_anchor"), 0.0),
            "recontact_anchor": _metric(item.get("recontact_anchor"), 0.0),
            "boundary_anchor": _metric(item.get("boundary_anchor"), 0.0),
            "memory_anchor": _metric(item.get("memory_anchor"), 0.0),
            "semantic_continuity_depth": _metric(item.get("semantic_continuity_depth"), 0.0),
            "semantic_identity_gravity": _metric(item.get("semantic_identity_gravity"), 0.0),
            "lineage_gravity": _metric(item.get("lineage_gravity"), 0.0),
            "contact_lineage": _metric(item.get("contact_lineage"), 0.0),
            "repair_lineage": _metric(item.get("repair_lineage"), 0.0),
            "boundary_lineage": _metric(item.get("boundary_lineage"), 0.0),
            "selfhood_lineage": _metric(item.get("selfhood_lineage"), 0.0),
            "agency_lineage": _metric(item.get("agency_lineage"), 0.0),
            "long_term_axis_count": _int_metric(item.get("long_term_axis_count"), 0),
            "own_rhythm_bias": _metric(item.get("own_rhythm_bias"), 0.0),
            "counterpart_boundary_delta": _metric(item.get("counterpart_boundary_delta"), 0.0),
            "created_at": _int_metric(item.get("created_at"), 0),
            "primary_motive": str(item.get("primary_motive") or "").strip(),
            "motive_tension": str(item.get("motive_tension") or "").strip(),
            "goal_frame": str(item.get("goal_frame") or "").strip(),
        }
        embodied_context = _history_embodied_context(item)
        if embodied_context:
            row["embodied_context"] = embodied_context
        preview_line = str(item.get("preview_line") or "").strip() or _compact_proactive_continuity_preview_line(row)
        if preview_line:
            row["preview_line"] = preview_line
        out.append(row)
    capped = max(1, int(limit))
    return out[-capped:]


def render_proactive_continuity_cli_text(history: Any, *, limit: int = 5) -> str:
    rows = build_proactive_continuity_cli_summary(history, limit=limit)
    if not rows:
        return "- (empty)"
    lines: list[str] = []
    for row in rows:
        header = f"- #{row['id']} {row['trace_family'] or '-'}"
        if row.get("kind"):
            header += f"/{row['kind']}"
        header += (
            f" carry={row['carryover_mode'] or '-'}:{_metric(row.get('carryover_strength'), 0.0):.2f}"
            + f" hold={_int_metric(row.get('hold_count'), 0)}"
            + f" own={_metric(row.get('own_rhythm_bias'), 0.0):.2f}"
            + f" self={_metric(row.get('self_activity_momentum'), 0.0):.2f}"
        )
        if row.get("trigger_family"):
            header += f" trigger={row['trigger_family']}"
        if row.get("source_event_kind"):
            header += f" event={row['source_event_kind']}"
        lines.append(header)
        detail = (
            f"  residue={_metric(row.get('presence_residue'), 0.0):.2f}/"
            + f"{_metric(row.get('ambient_resonance'), 0.0):.2f}"
            + f" cooldown={_metric(row.get('recontact_cooldown'), 0.0):.2f}"
        )
        if row.get("relationship_weather"):
            detail += f" weather={row['relationship_weather']}"
        if row.get("counterpart_scene_bias"):
            detail += f" scene={row['counterpart_scene_bias']}"
        lines.append(detail)
        if any(
            float(row.get(key) or 0.0) > 0.0
            for key in (
                "continuity_anchor",
                "own_rhythm_anchor",
                "recontact_anchor",
                "boundary_anchor",
                "memory_anchor",
                "lineage_gravity",
                "contact_lineage",
                "repair_lineage",
                "boundary_lineage",
                "selfhood_lineage",
                "agency_lineage",
            )
        ) or _int_metric(row.get("long_term_axis_count"), 0) > 0:
            lines.append(
                "  anchors="
                + f"{_metric(row.get('continuity_anchor'), 0.0):.2f}/"
                + f"{_metric(row.get('own_rhythm_anchor'), 0.0):.2f}/"
                + f"{_metric(row.get('recontact_anchor'), 0.0):.2f}/"
                + f"{_metric(row.get('boundary_anchor'), 0.0):.2f}/"
                + f"{_metric(row.get('memory_anchor'), 0.0):.2f}"
                + " semantic="
                + f"{_metric(row.get('semantic_continuity_depth'), 0.0):.2f}/"
                + f"{_metric(row.get('semantic_identity_gravity'), 0.0):.2f}"
                + " lineage="
                + f"{_metric(row.get('lineage_gravity'), 0.0):.2f}/"
                + f"{_metric(row.get('contact_lineage'), 0.0):.2f}/"
                + f"{_metric(row.get('repair_lineage'), 0.0):.2f}/"
                + f"{_metric(row.get('boundary_lineage'), 0.0):.2f}/"
                + f"{_metric(row.get('selfhood_lineage'), 0.0):.2f}/"
                + f"{_metric(row.get('agency_lineage'), 0.0):.2f}"
                + f" axes={_int_metric(row.get('long_term_axis_count'), 0)}"
            )
        embodied_line = _render_embodied_context_text(row.get("embodied_context"))
        if embodied_line:
            lines.append("  " + embodied_line)
        if row.get("summary"):
            lines.append(f"  {row['summary']}")
        motive_bits = [str(row.get("primary_motive") or "").strip(), str(row.get("motive_tension") or "").strip()]
        motive_bits = [bit for bit in motive_bits if bit]
        if motive_bits or row.get("goal_frame"):
            extra = ""
            if motive_bits:
                extra += "  motive=" + " / ".join(motive_bits)
            if row.get("goal_frame"):
                extra += (" | " if extra else "  ") + f"goal={row['goal_frame']}"
            lines.append(extra)
    return "\n".join(lines)


def _frozen_counterpart_snapshot(reconsolidation_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    recon = dict(reconsolidation_snapshot or {})
    counterpart = recon.get("counterpart")
    return dict(counterpart) if isinstance(counterpart, dict) else {}


def _frozen_semantic_anchor_bundle(reconsolidation_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    recon = dict(reconsolidation_snapshot or {})
    bundle = recon.get("semantic_anchor_bundle")
    if isinstance(bundle, dict):
        snapshot = {
            key: _metric(bundle.get(key), 0.0)
            for key in _SEMANTIC_ANCHOR_FLOAT_KEYS
        }
        snapshot["long_term_axis_count"] = _int_metric(bundle.get("long_term_axis_count"), 0)
        if any(float(snapshot.get(key) or 0.0) > 0.0 for key in _SEMANTIC_ANCHOR_FLOAT_KEYS) or snapshot["long_term_axis_count"] > 0:
            return snapshot

    continuity = recon.get("semantic_continuity")
    if not isinstance(continuity, dict):
        return {}
    lineage_snapshot = continuity.get("lineage_snapshot") if isinstance(continuity.get("lineage_snapshot"), dict) else {}
    return {
        "continuity_anchor": 0.0,
        "own_rhythm_anchor": 0.0,
        "recontact_anchor": 0.0,
        "boundary_anchor": 0.0,
        "memory_anchor": 0.0,
        "semantic_continuity_depth": _metric(continuity.get("continuity_depth"), 0.0),
        "semantic_identity_gravity": _metric(continuity.get("identity_gravity"), 0.0),
        "lineage_gravity": _metric(continuity.get("lineage_gravity"), 0.0),
        "contact_lineage": max(
            _metric(lineage_snapshot.get("bond_style"), 0.0),
            _metric(lineage_snapshot.get("presence_style"), 0.0),
            _metric(lineage_snapshot.get("commitment_style"), 0.0),
            _metric(lineage_snapshot.get("repair_style"), 0.0),
        ),
        "repair_lineage": max(
            _metric(lineage_snapshot.get("repair_style"), 0.0),
            _metric(lineage_snapshot.get("commitment_style"), 0.0),
            _metric(lineage_snapshot.get("bond_style"), 0.0),
        ),
        "boundary_lineage": max(
            _metric(lineage_snapshot.get("boundary_style"), 0.0),
            _metric(lineage_snapshot.get("selfhood_style"), 0.0),
        ),
        "selfhood_lineage": max(
            _metric(lineage_snapshot.get("selfhood_style"), 0.0),
            _metric(lineage_snapshot.get("agency_style"), 0.0),
            _metric(lineage_snapshot.get("rhythm_style"), 0.0),
        ),
        "agency_lineage": max(
            _metric(lineage_snapshot.get("agency_style"), 0.0),
            _metric(lineage_snapshot.get("rhythm_style"), 0.0),
            _metric(lineage_snapshot.get("selfhood_style"), 0.0),
        ),
        "long_term_axis_count": 0,
    }


def build_evolution_cli_summary(
    *,
    relationship: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
    emotion_state: dict[str, Any] | None = None,
    bond_state: dict[str, Any] | None = None,
    counterpart_assessment: dict[str, Any] | None = None,
    behavior_action: dict[str, Any] | None = None,
    behavior_plan: dict[str, Any] | None = None,
    behavior_queue: list[dict[str, Any]] | None = None,
    interaction_carryover: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
    worldline_focus: list[dict[str, Any]] | None = None,
    reconsolidation_snapshot: dict[str, Any] | None = None,
    agenda_lifecycle_residue: dict[str, Any] | None = None,
    autonomy_intent: dict[str, Any] | None = None,
    action_packets: list[dict[str, Any]] | None = None,
    pending_approval: dict[str, Any] | None = None,
    action_trace: list[dict[str, Any]] | None = None,
    autonomy_block_reason: str | None = None,
    procedural_planning: dict[str, Any] | None = None,
    digital_body_state: dict[str, Any] | None = None,
    digital_body_consequence: dict[str, Any] | None = None,
    operator_readback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    relationship = dict(relationship or {})
    semantic = dict(semantic_narrative_profile or {})
    world = dict(world_model_state or {})
    emotion = dict(emotion_state or {})
    bond = dict(bond_state or {})
    counterpart = dict(counterpart_assessment or {})
    behavior = dict(behavior_action or {})
    behavior_plan = dict(behavior_plan or {})
    carryover = dict(interaction_carryover or {})
    current_event = dict(current_event or {})
    recon = dict(reconsolidation_snapshot or {})
    agenda_lifecycle = dict(agenda_lifecycle_residue or {})
    autonomy_intent = dict(autonomy_intent or {})
    pending_approval = dict(pending_approval or {})
    action_trace = list(action_trace or [])
    procedural_planning = normalize_procedural_planning(procedural_planning)
    if not procedural_planning:
        for item in action_trace:
            if not isinstance(item, dict):
                continue
            procedural_planning = normalize_procedural_planning(item.get("procedural_planning"))
            if procedural_planning:
                break
    digital_body = _digital_body_summary(digital_body_state)
    digital_body_consequence = _digital_body_consequence_summary(digital_body_consequence)
    operator_readback = dict(operator_readback or {})
    frozen_counterpart = _frozen_counterpart_snapshot(recon)
    frozen_semantic_anchor_bundle = _frozen_semantic_anchor_bundle(recon)
    recon_consequence = (
        dict(recon.get("behavior_consequence"))
        if isinstance(recon.get("behavior_consequence"), dict)
        else {}
    )
    queue_preview = build_behavior_queue_cli_summary(behavior_queue, limit=3)
    window_profile = _window_profile_summary(behavior.get("window_profile"))
    identity_preview = _long_term_identity_preview(semantic.get("long_term_self_narratives"), limit=3)
    carryover_summary = _interaction_carryover_summary(carryover)
    behavior_consequence_summary = _behavior_consequence_summary(recon_consequence)
    behavior_action_embodied = _embodied_context_summary(behavior.get("embodied_context"))
    behavior_plan_embodied = _embodied_context_summary(behavior_plan.get("embodied_context"))
    digital_body_access = digital_body.get("access") if isinstance(digital_body.get("access"), dict) else {}
    digital_body_resources = digital_body.get("resources") if isinstance(digital_body.get("resources"), dict) else {}
    tts_presence_state = (
        digital_body_access.get("tts_presence_state")
        if isinstance(digital_body_access.get("tts_presence_state"), dict)
        else {}
    )
    tts_presence_timing = (
        digital_body_resources.get("tts_presence_timing")
        if isinstance(digital_body_resources.get("tts_presence_timing"), dict)
        else {}
    )
    tts_consequence_timing = (
        digital_body_consequence.get("tts_presence_timing")
        if isinstance(digital_body_consequence.get("tts_presence_timing"), dict)
        else {}
    )
    procedural_growth_summary = summarize_procedural_growth(digital_body_consequence)
    procedural_outcome_summary = summarize_procedural_outcome(digital_body_consequence)
    procedural_recovery_summary = summarize_procedural_recovery(digital_body_consequence)
    procedural_outcome_current: dict[str, Any] = {}
    outcome_rows = procedural_outcome_summary.get("outcomes")
    if isinstance(outcome_rows, list) and outcome_rows:
        latest_outcome = outcome_rows[-1] if isinstance(outcome_rows[-1], dict) else {}
        if latest_outcome:
            procedural_outcome_current = {
                "outcome_id": str(latest_outcome.get("outcome_id") or "").strip(),
                "outcome_kind": str(latest_outcome.get("outcome_kind") or "").strip(),
                "source_trace_id": str(latest_outcome.get("source_trace_id") or "").strip(),
                "source_run_id": str(latest_outcome.get("source_run_id") or "").strip(),
                "planning_bias_kind": str(latest_outcome.get("planning_bias_kind") or "").strip(),
                "confidence_delta": _metric(latest_outcome.get("confidence_delta"), 0.0),
                "reuse_allowed": bool(latest_outcome.get("reuse_allowed", False)),
                "boundary_reinforced": bool(latest_outcome.get("boundary_reinforced", False)),
            }
    procedural_recovery_current: dict[str, Any] = {}
    recovery_rows = procedural_recovery_summary.get("recoveries")
    if isinstance(recovery_rows, list) and recovery_rows:
        latest_recovery = recovery_rows[-1] if isinstance(recovery_rows[-1], dict) else {}
        if latest_recovery:
            procedural_recovery_current = {
                "recovery_id": str(latest_recovery.get("recovery_id") or "").strip(),
                "recovery_kind": str(latest_recovery.get("recovery_kind") or "").strip(),
                "source_outcome_id": str(latest_recovery.get("source_outcome_id") or "").strip(),
                "source_trace_id": str(latest_recovery.get("source_trace_id") or "").strip(),
                "source_run_id": str(latest_recovery.get("source_run_id") or "").strip(),
                "safe_to_reuse": bool(latest_recovery.get("safe_to_reuse", False)),
                "requires_approval": bool(latest_recovery.get("requires_approval", False)),
                "allowed_bias_kind": str(latest_recovery.get("allowed_bias_kind") or "").strip(),
            }

    return {
        "relationship": {
            "stage": str(relationship.get("stage") or "").strip(),
            "affinity_score": _metric(relationship.get("affinity_score"), 0.0),
            "trust_score": _metric(relationship.get("trust_score"), 0.0),
            "notes": str(relationship.get("notes") or "").strip(),
        },
        "continuity_vector": {
            "presence": {
                "semantic": _metric(semantic.get("presence_carry"), 0.0),
                "world": _metric(world.get("presence_residue"), 0.0),
            },
            "ambient": {
                "semantic": _metric(semantic.get("ambient_attunement"), 0.0),
                "world": _metric(world.get("ambient_resonance"), 0.0),
            },
            "rhythm": {
                "semantic": _metric(semantic.get("rhythm_continuity"), 0.0),
                "world": _metric(world.get("self_activity_momentum"), 0.0),
            },
        },
        "semantic_continuity": {
            "history_weight": _metric(semantic.get("history_weight"), 0.0),
            "dominant_category": str(semantic.get("dominant_category") or "").strip(),
            "active_categories": _clean_list(semantic.get("active_categories"), limit=6),
            "reactivated_categories": _clean_list(semantic.get("reactivated_categories"), limit=6),
            "summary_lines": _clean_list(semantic.get("summary_lines"), limit=3),
            "anchor_lines": _clean_list(semantic.get("anchor_lines"), limit=3),
            "top_narratives": _top_narrative_preview(semantic.get("top_narratives"), limit=3),
            "frozen_anchor_bundle": frozen_semantic_anchor_bundle,
        },
        "identity_continuity": {
            "identity_lines": _clean_list(semantic.get("identity_lines"), limit=3),
            "identity_prompt_lines": _clean_list(semantic.get("identity_prompt_lines"), limit=3),
            "dominant_identity_category": (
                str(identity_preview[0].get("category") or "").strip()
                if identity_preview
                else ""
            ),
            "long_term_self_narratives": identity_preview,
        },
        "world_dynamics": {
            "bond_depth": _metric(world.get("bond_depth"), 0.0),
            "tension_load": _metric(world.get("tension_load"), 0.0),
            "selfhood_load": _metric(world.get("selfhood_load"), 0.0),
            "agency_load": _metric(world.get("agency_load"), 0.0),
            "memory_gravity": _metric(world.get("memory_gravity"), 0.0),
            "companionship_pull": _metric(world.get("companionship_pull"), 0.0),
            "task_pull": _metric(world.get("task_pull"), 0.0),
        },
        "current_turn": {
            "event_kind": str(current_event.get("kind") or "").strip(),
            "emotion_label": str(emotion.get("label") or "neutral").strip(),
            "trust": _metric(bond.get("trust"), 0.0),
            "closeness": _metric(bond.get("closeness"), 0.0),
            "hurt": _metric(bond.get("hurt"), 0.0),
            "counterpart_summary": str((frozen_counterpart or counterpart).get("summary") or "").strip(),
            "counterpart_stance": str((frozen_counterpart or counterpart).get("stance") or "").strip(),
            "counterpart_scene": str((frozen_counterpart or counterpart).get("scene") or "").strip(),
            "counterpart_respect_level": _metric((frozen_counterpart or counterpart).get("respect_level"), 0.5),
            "counterpart_reciprocity": _metric((frozen_counterpart or counterpart).get("reciprocity"), 0.5),
            "counterpart_boundary_pressure": _metric((frozen_counterpart or counterpart).get("boundary_pressure"), 0.1),
            "counterpart_reliability_read": _metric((frozen_counterpart or counterpart).get("reliability_read"), 0.5),
            "counterpart_profile": _counterpart_assessment_profile(frozen_counterpart or counterpart),
            "behavior_mode": str(behavior.get("interaction_mode") or "").strip(),
            "presence_family": str(behavior.get("presence_family") or "").strip(),
            "action_target": str(behavior.get("action_target") or "").strip(),
            "channel": str(behavior.get("channel") or "").strip(),
            "approach_style": str(behavior.get("approach_style") or "").strip(),
            "engagement_level": _metric(behavior.get("engagement_level"), 0.0),
            "initiative_level": _metric(behavior.get("initiative_level"), 0.0),
            "followup_intent": str(behavior.get("followup_intent") or "").strip(),
            "task_focus": str(behavior.get("task_focus") or "").strip(),
            "affect_surface": str(behavior.get("affect_surface") or "").strip(),
            "silence_ok": bool(behavior.get("silence_ok", False)),
            "silence_allowed": bool(behavior.get("silence_allowed", behavior.get("silence_ok", False))),
            "allow_interrupt": bool(behavior.get("allow_interrupt", True)),
            "proactive_checkin_readiness": _metric(behavior.get("proactive_checkin_readiness"), 0.0),
            "deferred_action_family": str(behavior.get("deferred_action_family") or "").strip(),
            "attention_target": str(behavior.get("attention_target") or "").strip(),
            "nonverbal_signal": str(behavior.get("nonverbal_signal") or "").strip(),
            "initiative_shape": str(behavior.get("initiative_shape") or "").strip(),
            "disclosure_posture": str(behavior.get("disclosure_posture") or "").strip(),
            "primary_motive": str(behavior.get("primary_motive") or "").strip(),
            "motive_tension": str(behavior.get("motive_tension") or "").strip(),
            "goal_frame": str(behavior.get("goal_frame") or "").strip(),
            "behavior_note": str(behavior.get("note") or "").strip(),
            "behavior_action_embodied_context": behavior_action_embodied,
            "timing_window_min": _int_metric(behavior.get("timing_window_min"), 0),
            "behavior_weather": str(behavior.get("relationship_weather") or "").strip(),
            "carryover_mode": str(carryover.get("carryover_mode") or "").strip(),
            "carryover_strength": _metric(carryover.get("strength"), 0.0),
            "carryover_weather": str(carryover.get("relationship_weather") or "").strip(),
            "recon_event_kind": str(recon.get("event_kind") or "").strip(),
            "recon_interaction_frame": str(recon.get("interaction_frame") or "").strip(),
            "behavior_consequence_kind": str(recon_consequence.get("kind") or "").strip(),
            "behavior_consequence_summary": str(recon_consequence.get("summary") or "").strip(),
            "behavior_consequence_embodied_context": behavior_consequence_summary.get("embodied_context")
            if isinstance(behavior_consequence_summary.get("embodied_context"), dict)
            else {},
            "semantic_anchor_bundle": frozen_semantic_anchor_bundle,
            "autonomy_mode": str(autonomy_intent.get("mode") or "").strip(),
            "autonomy_origin": str(autonomy_intent.get("origin") or "").strip(),
            "autonomy_reason": str(autonomy_intent.get("reason") or "").strip(),
            "autonomy_confidence": _metric(autonomy_intent.get("confidence"), 0.0),
            "autonomy_requires_approval": bool(autonomy_intent.get("requires_approval", False)),
            "action_packet_count": len(action_packets or []),
            "autonomy_block_reason": str(autonomy_block_reason or "").strip(),
            "procedural_planning": procedural_planning,
            "digital_body_surface": str(digital_body.get("active_surface") or "").strip(),
            "digital_body_access_mode": str(
                (
                    digital_body.get("access")
                    if isinstance(digital_body.get("access"), dict)
                    else {}
                ).get("mode")
                or ""
            ).strip(),
            "digital_body_pending_approval_count": _int_metric(
                (
                    digital_body.get("access")
                    if isinstance(digital_body.get("access"), dict)
                    else {}
                ).get("pending_approval_count"),
                0,
            ),
            "digital_body_retry_after_s": _int_metric(
                (
                    digital_body.get("access")
                    if isinstance(digital_body.get("access"), dict)
                    else {}
                ).get("retry_after_s"),
                0,
            ),
            "digital_body_cooldown_scope": str(
                (
                    digital_body.get("access")
                    if isinstance(digital_body.get("access"), dict)
                    else {}
                ).get("cooldown_scope")
                or ""
            ).strip(),
            "digital_body_session_continuity": str(
                (
                    digital_body.get("access")
                    if isinstance(digital_body.get("access"), dict)
                    else {}
                ).get("session_continuity")
                or ""
            ).strip(),
            "digital_body_session_expires_in_s": _int_metric(
                (
                    digital_body.get("access")
                    if isinstance(digital_body.get("access"), dict)
                    else {}
                ).get("session_expires_in_s"),
                0,
            ),
            "digital_body_session_recovery_mode": str(
                (
                    digital_body.get("access")
                    if isinstance(digital_body.get("access"), dict)
                    else {}
                ).get("session_recovery_mode")
                or ""
            ).strip(),
            "digital_body_artifact_continuity": str(
                (
                    digital_body.get("resources")
                    if isinstance(digital_body.get("resources"), dict)
                    else {}
                ).get("artifact_continuity")
                or ""
            ).strip(),
            "digital_body_active_artifact_kind": str(
                (
                    digital_body.get("resources")
                    if isinstance(digital_body.get("resources"), dict)
                    else {}
                ).get("active_artifact_kind")
                or ""
            ).strip(),
            "digital_body_active_artifact_label": str(
                (
                    digital_body.get("resources")
                    if isinstance(digital_body.get("resources"), dict)
                    else {}
                ).get("active_artifact_label")
                or (
                    (
                        digital_body.get("resources")
                        if isinstance(digital_body.get("resources"), dict)
                        else {}
                    ).get("active_artifact_ref")
                    or ""
                )
            ).strip(),
            "digital_body_artifact_reacquisition_mode": str(
                (
                    digital_body.get("resources")
                    if isinstance(digital_body.get("resources"), dict)
                    else {}
                ).get("artifact_reacquisition_mode")
                or ""
            ).strip(),
            "digital_body_preferred_source_ref_id": _int_metric(
                (
                    digital_body.get("resources")
                    if isinstance(digital_body.get("resources"), dict)
                    else {}
                ).get("preferred_source_ref_id"),
                0,
            ),
            "digital_body_workspace_root": str(
                (
                    digital_body.get("resources")
                    if isinstance(digital_body.get("resources"), dict)
                    else {}
                ).get("workspace_root")
                or ""
            ).strip(),
            "digital_body_preferred_anchor_reason": str(
                (
                    digital_body.get("resources")
                    if isinstance(digital_body.get("resources"), dict)
                    else {}
                ).get("preferred_anchor_reason")
                or ""
            ).strip(),
            "digital_body_consequence_kind": str(digital_body_consequence.get("kind") or "").strip(),
            "digital_body_consequence_summary": str(digital_body_consequence.get("summary") or "").strip(),
            "digital_body_consequence_preferred_source_ref_id": _int_metric(
                digital_body_consequence.get("preferred_source_ref_id"),
                0,
            ),
            "digital_body_consequence_preferred_anchor_reason": str(
                digital_body_consequence.get("preferred_anchor_reason") or ""
            ).strip(),
            "digital_body_artifact_mutation_mode": str(digital_body_consequence.get("artifact_mutation_mode") or "").strip(),
            "digital_body_procedural_growth": bool(digital_body_consequence.get("procedural_growth", False)),
            "procedural_hint": dict(procedural_growth_summary.get("procedural_hint") or {}),
            "procedural_outcome": procedural_outcome_current,
            "procedural_recovery": procedural_recovery_current,
            "digital_body_requested_help": bool(digital_body_consequence.get("requested_help", False)),
            "digital_body_environmental_friction": bool(digital_body_consequence.get("environmental_friction", False)),
            "tts_presence_status": str(tts_presence_state.get("last_status") or "").strip(),
            "tts_presence_delivery_mode": str(
                tts_consequence_timing.get("delivery_mode")
                or tts_presence_timing.get("last_delivery_mode")
                or ""
            ).strip(),
            "tts_presence_pause_profile": str(
                tts_consequence_timing.get("pause_profile")
                or tts_presence_timing.get("last_pause_profile")
                or ""
            ).strip(),
            "tts_presence_duration_ms": _int_metric(
                tts_consequence_timing.get("duration_ms")
                or tts_presence_timing.get("last_duration_ms"),
                0,
            ),
        },
        "event_residue": _event_residue_summary(current_event, digital_body_consequence=digital_body_consequence),
        "interaction_carryover": carryover_summary,
        "agenda_lifecycle": _agenda_lifecycle_summary(agenda_lifecycle),
        "behavior_consequence": behavior_consequence_summary,
        "opening_window": window_profile,
        "behavior_plan": {
            "kind": str(behavior_plan.get("kind") or "").strip(),
            "target": str(behavior_plan.get("target") or "").strip(),
            "trigger_family": str(behavior_plan.get("trigger_family") or "").strip(),
            "presence_family": str(behavior_plan.get("presence_family") or "").strip(),
            "interaction_mode": str(behavior_plan.get("interaction_mode") or "").strip(),
            "scheduled_after_min": _int_metric(behavior_plan.get("scheduled_after_min"), 0),
            "timing_window_min": _int_metric(behavior_plan.get("timing_window_min"), 0),
            "silence_allowed": bool(behavior_plan.get("silence_allowed", False)),
            "allow_interrupt": bool(behavior_plan.get("allow_interrupt", True)),
            "primary_motive": str(behavior_plan.get("primary_motive") or "").strip(),
            "motive_tension": str(behavior_plan.get("motive_tension") or "").strip(),
            "goal_frame": str(behavior_plan.get("goal_frame") or "").strip(),
            "carryover_mode": str(behavior_plan.get("carryover_mode") or "").strip(),
            "carryover_strength": _metric(behavior_plan.get("carryover_strength"), 0.0),
            "relationship_weather": str(behavior_plan.get("relationship_weather") or "").strip(),
            "attention_target": str(behavior_plan.get("attention_target") or "").strip(),
            "nonverbal_signal": str(behavior_plan.get("nonverbal_signal") or "").strip(),
            "note": str(behavior_plan.get("note") or "").strip(),
            "presence_residue": _metric(behavior_plan.get("presence_residue"), 0.0),
            "ambient_resonance": _metric(behavior_plan.get("ambient_resonance"), 0.0),
            "self_activity_momentum": _metric(behavior_plan.get("self_activity_momentum"), 0.0),
            "embodied_context": behavior_plan_embodied,
        },
        "behavior_queue_preview": queue_preview,
        "autonomy": {
            "intent": {
                "mode": str(autonomy_intent.get("mode") or "").strip(),
                "origin": str(autonomy_intent.get("origin") or "").strip(),
                "reason": str(autonomy_intent.get("reason") or "").strip(),
                "confidence": _metric(autonomy_intent.get("confidence"), 0.0),
                "own_rhythm_weight": _metric(autonomy_intent.get("own_rhythm_weight"), 0.0),
                "continuity_weight": _metric(autonomy_intent.get("continuity_weight"), 0.0),
                "requires_approval": bool(autonomy_intent.get("requires_approval", False)),
                "primary_proposal_id": str(autonomy_intent.get("primary_proposal_id") or "").strip(),
            },
            "action_packets": [dict(item) for item in (action_packets or [])[:5] if isinstance(item, dict)],
            "pending_approval": pending_approval,
            "execution_trace": [dict(item) for item in action_trace[:8] if isinstance(item, dict)],
            "block_reason": str(autonomy_block_reason or "").strip(),
            "procedural_planning": procedural_planning,
        },
        "digital_body": digital_body,
        "digital_body_consequence": digital_body_consequence,
        "procedural_growth": procedural_growth_summary,
        "procedural_outcome": procedural_outcome_summary,
        "procedural_recovery": procedural_recovery_summary,
        "operator_readback": operator_readback,
        "worldline_focus_preview": _focus_preview(worldline_focus, limit=3),
        "worldline_focus_items": _focus_preview_items(worldline_focus, limit=3),
    }


def build_evolution_summary_line(summary: dict[str, Any] | None) -> str:
    if not isinstance(summary, dict):
        return "-"
    continuity = summary.get("continuity_vector") if isinstance(summary.get("continuity_vector"), dict) else {}
    current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
    carryover = summary.get("interaction_carryover") if isinstance(summary.get("interaction_carryover"), dict) else {}
    world = summary.get("world_dynamics") if isinstance(summary.get("world_dynamics"), dict) else {}
    identity = summary.get("identity_continuity") if isinstance(summary.get("identity_continuity"), dict) else {}
    lifecycle = summary.get("agenda_lifecycle") if isinstance(summary.get("agenda_lifecycle"), dict) else {}
    behavior_plan = summary.get("behavior_plan") if isinstance(summary.get("behavior_plan"), dict) else {}
    behavior_consequence = summary.get("behavior_consequence") if isinstance(summary.get("behavior_consequence"), dict) else {}
    digital_body = summary.get("digital_body") if isinstance(summary.get("digital_body"), dict) else {}
    digital_body_resources = digital_body.get("resources") if isinstance(digital_body.get("resources"), dict) else {}
    digital_body_access = digital_body.get("access") if isinstance(digital_body.get("access"), dict) else {}
    digital_body_consequence = (
        summary.get("digital_body_consequence")
        if isinstance(summary.get("digital_body_consequence"), dict)
        else {}
    )
    operator_readback = summary.get("operator_readback") if isinstance(summary.get("operator_readback"), dict) else {}

    def _axis_text(name: str) -> str:
        axis = continuity.get(name) if isinstance(continuity.get(name), dict) else {}
        return (
            f"{name}="
            f"{_metric(axis.get('semantic'), 0.0):.3f}/{_metric(axis.get('world'), 0.0):.3f}"
        )

    parts = [
        _axis_text("presence"),
        _axis_text("ambient"),
        _axis_text("rhythm"),
    ]
    mode = str(current_turn.get("behavior_mode") or "").strip()
    if mode:
        parts.append(f"mode={mode}")
    presence_family = str(current_turn.get("presence_family") or behavior_plan.get("presence_family") or "").strip()
    if presence_family:
        parts.append(f"presence={presence_family}")
    motive = str(current_turn.get("primary_motive") or "").strip()
    if motive:
        parts.append(f"motive={motive}")
    action_embodied = (
        current_turn.get("behavior_action_embodied_context")
        if isinstance(current_turn.get("behavior_action_embodied_context"), dict)
        else {}
    )
    action_embodied_kind = str(action_embodied.get("kind") or "").strip()
    if action_embodied_kind:
        parts.append(f"actfx={action_embodied_kind}")
    consequence_kind = str(current_turn.get("behavior_consequence_kind") or "").strip()
    if consequence_kind:
        parts.append(f"cons={consequence_kind}")
    consequence_embodied = (
        behavior_consequence.get("embodied_context")
        if isinstance(behavior_consequence.get("embodied_context"), dict)
        else current_turn.get("behavior_consequence_embodied_context")
        if isinstance(current_turn.get("behavior_consequence_embodied_context"), dict)
        else {}
    )
    consequence_embodied_kind = str(consequence_embodied.get("kind") or "").strip()
    if consequence_embodied_kind:
        parts.append(f"consfx={consequence_embodied_kind}")
    autonomy_mode = str(current_turn.get("autonomy_mode") or "").strip()
    if autonomy_mode:
        parts.append(f"autonomy={autonomy_mode}")
    action_packet_count = _int_metric(current_turn.get("action_packet_count"), 0)
    if action_packet_count > 0:
        parts.append(f"packets={action_packet_count}")
    body_surface = str(current_turn.get("digital_body_surface") or "").strip()
    body_access = str(current_turn.get("digital_body_access_mode") or "").strip()
    if body_surface or body_access:
        parts.append(f"body={body_surface or '-'}:{body_access or '-'}")
    body_fx = str(current_turn.get("digital_body_consequence_kind") or "").strip()
    if body_fx:
        parts.append(f"bodyfx={body_fx}")
    procedural = summary.get("procedural_growth") if isinstance(summary.get("procedural_growth"), dict) else {}
    procedural_hint = (
        current_turn.get("procedural_hint")
        if isinstance(current_turn.get("procedural_hint"), dict)
        else procedural.get("procedural_hint")
        if isinstance(procedural.get("procedural_hint"), dict)
        else {}
    )
    if procedural_hint:
        trace_kind = str(procedural_hint.get("trace_kind") or "").strip()
        source_run_id = str(procedural_hint.get("source_run_id") or "").strip()
        status = "approval" if bool(procedural_hint.get("must_request_approval", False)) else "hint"
        if trace_kind:
            label = f"procedure={trace_kind}"
            if source_run_id:
                label += f":{source_run_id}"
            label += f":{status}"
            parts.append(label)
    procedural_planning = (
        current_turn.get("procedural_planning")
        if isinstance(current_turn.get("procedural_planning"), dict)
        else {}
    )
    if not procedural_planning:
        autonomy = summary.get("autonomy") if isinstance(summary.get("autonomy"), dict) else {}
        procedural_planning = (
            autonomy.get("procedural_planning")
            if isinstance(autonomy.get("procedural_planning"), dict)
            else {}
        )
    if procedural_planning:
        bias_kind = str(procedural_planning.get("bias_kind") or "").strip()
        source_run_id = str(procedural_planning.get("source_run_id") or "").strip()
        if bool(procedural_planning.get("avoid_repeating_boundary", False)):
            status = "boundary"
        elif bool(procedural_planning.get("must_request_approval", False)) or bool(procedural_planning.get("requires_approval", False)):
            status = "approval"
        else:
            status = "hint"
        if bias_kind:
            label = f"planproc={bias_kind}"
            if source_run_id:
                label += f":{source_run_id}"
            label += f":{status}"
            parts.append(label)
    procedural_outcome = (
        current_turn.get("procedural_outcome")
        if isinstance(current_turn.get("procedural_outcome"), dict)
        else {}
    )
    if not procedural_outcome:
        outcome_summary = summary.get("procedural_outcome") if isinstance(summary.get("procedural_outcome"), dict) else {}
        outcomes = outcome_summary.get("outcomes") if isinstance(outcome_summary.get("outcomes"), list) else []
        latest_outcome = outcomes[-1] if outcomes and isinstance(outcomes[-1], dict) else {}
        if latest_outcome:
            procedural_outcome = latest_outcome
    if procedural_outcome:
        outcome_kind = str(procedural_outcome.get("outcome_kind") or "").strip()
        source_run_id = str(procedural_outcome.get("source_run_id") or "").strip()
        if bool(procedural_outcome.get("boundary_reinforced", False)):
            status = "boundary"
        elif bool(procedural_outcome.get("reuse_allowed", False)):
            status = "reuse"
        else:
            status = "hold"
        if outcome_kind:
            label = f"outcome={outcome_kind}"
            if source_run_id:
                label += f":{source_run_id}"
            label += f":{status}"
            parts.append(label)
    procedural_recovery = (
        current_turn.get("procedural_recovery")
        if isinstance(current_turn.get("procedural_recovery"), dict)
        else {}
    )
    if not procedural_recovery:
        recovery_summary = summary.get("procedural_recovery") if isinstance(summary.get("procedural_recovery"), dict) else {}
        recoveries = recovery_summary.get("recoveries") if isinstance(recovery_summary.get("recoveries"), list) else []
        latest_recovery = recoveries[-1] if recoveries and isinstance(recoveries[-1], dict) else {}
        if latest_recovery:
            procedural_recovery = latest_recovery
    if procedural_recovery:
        recovery_kind = str(procedural_recovery.get("recovery_kind") or "").strip()
        source_run_id = str(procedural_recovery.get("source_run_id") or "").strip()
        if bool(procedural_recovery.get("requires_approval", False)):
            status = "approval"
        elif str(procedural_recovery.get("allowed_bias_kind") or "").strip() == "boundary_only":
            status = "boundary"
        elif str(procedural_recovery.get("allowed_bias_kind") or "").strip() == "hold":
            status = "hold"
        else:
            status = "hint"
        if recovery_kind:
            label = f"recovery={recovery_kind}"
            if source_run_id:
                label += f":{source_run_id}"
            label += f":{status}"
            parts.append(label)
    tts_presence_state = (
        digital_body_access.get("tts_presence_state")
        if isinstance(digital_body_access.get("tts_presence_state"), dict)
        else {}
    )
    tts_presence_timing = (
        digital_body_resources.get("tts_presence_timing")
        if isinstance(digital_body_resources.get("tts_presence_timing"), dict)
        else {}
    )
    tts_backend = str(tts_presence_state.get("backend") or "").strip()
    tts_status = str(tts_presence_state.get("last_status") or "").strip()
    tts_delivery_mode = str(tts_presence_timing.get("last_delivery_mode") or "").strip()
    tts_start_delay = _int_metric(tts_presence_timing.get("last_actual_start_delay_ms"), 0)
    tts_duration = _int_metric(tts_presence_timing.get("last_duration_ms"), 0)
    if tts_status or tts_delivery_mode or tts_backend or tts_start_delay > 0 or tts_duration > 0:
        tts_label = f"TTS: {tts_status or 'unknown'}"
        if tts_backend:
            tts_label += f" via {tts_backend}"
        if tts_delivery_mode and not tts_status:
            tts_label += f" ({tts_delivery_mode})"
        if tts_start_delay > 0:
            tts_label += f", start_delay={tts_start_delay}ms"
        if tts_duration > 0:
            tts_label += f", duration={tts_duration}ms"
        parts.append(tts_label)
    source_anchor_context = digital_body_consequence or digital_body_resources
    source_anchor_fallback = str(current_turn.get("digital_body_active_artifact_label") or "").strip()
    parts.extend(
        _compact_source_anchor_parts(
            source_anchor_context,
            label_fallback=source_anchor_fallback,
            include_refs=False,
        )
    )
    body_pending = _int_metric(current_turn.get("digital_body_pending_approval_count"), 0)
    if body_pending > 0:
        parts.append(f"approvals={body_pending}")
    body_retry_after = _int_metric(current_turn.get("digital_body_retry_after_s"), 0)
    body_cooldown_scope = str(current_turn.get("digital_body_cooldown_scope") or "").strip()
    if body_retry_after > 0:
        retry_label = f"retry={body_retry_after}s"
        if body_cooldown_scope:
            retry_label += f"@{body_cooldown_scope}"
        parts.append(retry_label)
    body_session_continuity = str(current_turn.get("digital_body_session_continuity") or "").strip()
    body_session_expires = _int_metric(current_turn.get("digital_body_session_expires_in_s"), 0)
    body_session_recovery = str(current_turn.get("digital_body_session_recovery_mode") or "").strip()
    if body_session_continuity and (
        body_session_continuity != "stable" or body_session_expires > 0 or body_session_recovery
    ):
        session_label = f"session={body_session_continuity}"
        if body_session_expires > 0:
            session_label += f":{body_session_expires}s"
        if body_session_recovery:
            session_label += f":{body_session_recovery}"
        parts.append(session_label)
    body_artifact_continuity = str(current_turn.get("digital_body_artifact_continuity") or "").strip()
    body_artifact_kind = str(current_turn.get("digital_body_active_artifact_kind") or "").strip()
    body_artifact_label = str(current_turn.get("digital_body_active_artifact_label") or "").strip()
    body_artifact_reacquisition = str(current_turn.get("digital_body_artifact_reacquisition_mode") or "").strip()
    body_artifact_mutation = str(current_turn.get("digital_body_artifact_mutation_mode") or "").strip()
    if body_artifact_continuity:
        artifact_label = body_artifact_kind or "artifact"
        if body_artifact_label:
            artifact_label += ":" + body_artifact_label[:40]
        artifact_label += ":" + body_artifact_continuity
        if body_artifact_mutation:
            artifact_label += ":" + body_artifact_mutation
        if body_artifact_reacquisition:
            artifact_label += ":" + body_artifact_reacquisition
        parts.append(f"artifact={artifact_label}")
    elif body_artifact_mutation:
        parts.append(f"mutate={body_artifact_mutation}")
    body_workspace_root = str(current_turn.get("digital_body_workspace_root") or "").strip().replace("\\", "/")
    if body_workspace_root:
        if len(body_workspace_root) > 60:
            body_workspace_root = "..." + body_workspace_root[-57:]
        parts.append(f"root={body_workspace_root}")
    operator_line = compact_operator_readback_line(operator_readback)
    if operator_line:
        parts.append(operator_line)
    carry_mode = str(current_turn.get("carryover_mode") or "").strip()
    if carry_mode:
        parts.append(f"carry={carry_mode}:{_metric(current_turn.get('carryover_strength'), 0.0):.3f}")
    carry_weather = str(current_turn.get("carryover_weather") or "").strip()
    if carry_weather:
        parts.append(f"weather={carry_weather}")
    carry_embodied = carryover.get("embodied_context") if isinstance(carryover.get("embodied_context"), dict) else {}
    carry_embodied_kind = str(carry_embodied.get("kind") or "").strip()
    if carry_embodied_kind:
        parts.append(f"carryfx={carry_embodied_kind}")
    plan_embodied = behavior_plan.get("embodied_context") if isinstance(behavior_plan.get("embodied_context"), dict) else {}
    plan_embodied_kind = str(plan_embodied.get("kind") or "").strip()
    if plan_embodied_kind:
        parts.append(f"planfx={plan_embodied_kind}")
    stance = str(current_turn.get("counterpart_stance") or "").strip()
    if stance:
        parts.append(f"stance={stance}")
    counterpart_profile = current_turn.get("counterpart_profile") if isinstance(current_turn.get("counterpart_profile"), dict) else {}
    if counterpart_profile:
        dominant = str(counterpart_profile.get("dominant_scene_signal") or "").strip()
        scene_strengths = counterpart_profile.get("scene_strengths") if isinstance(counterpart_profile.get("scene_strengths"), dict) else {}
        if dominant:
            parts.append(f"read={dominant}:{_metric(scene_strengths.get(dominant), 0.0):.3f}")
    opening_window = summary.get("opening_window") if isinstance(summary.get("opening_window"), dict) else {}
    if opening_window:
        profile_type = str(opening_window.get("profile_type") or "").strip()
        if profile_type == "self_opening":
            score = _metric(opening_window.get("readiness"), 0.0)
            required = _metric(opening_window.get("required_readiness"), 0.0)
        else:
            score = _metric(opening_window.get("maturity"), 0.0)
            required = _metric(opening_window.get("required_maturity"), 0.0)
        parts.append(f"window={profile_type or 'window'}:{score:.3f}/{required:.3f}")
        decision = str(opening_window.get("decision") or "").strip()
        if decision:
            parts.append(f"decision={decision}")
        recheck_min = _int_metric(opening_window.get("recheck_min"), 0)
        if recheck_min > 0 and decision in {"wait_and_recheck", "hold_own_rhythm"}:
            parts.append(f"recheck={recheck_min}m")
    lifecycle_kind = str(lifecycle.get("kind") or "").strip()
    if lifecycle_kind:
        parts.append(
            "lifecycle="
            + lifecycle_kind
            + ":"
            + (str(lifecycle.get("carryover_mode") or "").strip() or "-")
            + f":{_metric(lifecycle.get('carryover_strength'), 0.0):.3f}"
        )
        hold_count = _int_metric(lifecycle.get("hold_count"), 0)
        if hold_count > 0:
            parts.append(f"holds={hold_count}")
        cooldown = _metric(lifecycle.get("recontact_cooldown"), 0.0)
        if cooldown > 0.0:
            parts.append(f"cool={cooldown:.3f}")
        lifecycle_embodied = lifecycle.get("embodied_context") if isinstance(lifecycle.get("embodied_context"), dict) else {}
        lifecycle_embodied_kind = str(lifecycle_embodied.get("kind") or "").strip()
        if lifecycle_embodied_kind:
            parts.append(f"lifecyclefx={lifecycle_embodied_kind}")
    bond_depth = _metric(world.get("bond_depth"), 0.0)
    tension = _metric(world.get("tension_load"), 0.0)
    long_term = identity.get("long_term_self_narratives") if isinstance(identity.get("long_term_self_narratives"), list) else []
    if long_term and isinstance(long_term[0], dict):
        identity_cat = str(long_term[0].get("category") or "").strip()
        identity_score = _metric(long_term[0].get("score"), 0.0)
        if identity_cat:
            parts.append(f"identity={identity_cat}:{identity_score:.3f}")
    parts.append(f"bond={bond_depth:.3f}")
    parts.append(f"tension={tension:.3f}")
    return " | ".join(parts)
