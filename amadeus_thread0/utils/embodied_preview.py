from __future__ import annotations

from typing import Any

from ..graph_parts.digital_body_runtime import normalize_access_acquire_proposal, normalize_access_acquire_proposals, normalize_embodied_context


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


def _embodied_context_summary(state: Any) -> dict[str, Any]:
    normalized = normalize_embodied_context(state)
    if not normalized:
        return {}
    return {
        "kind": str(normalized.get("kind") or "").strip(),
        "summary": str(normalized.get("summary") or "").strip(),
        "access_mode": str(normalized.get("access_mode") or "").strip(),
        "active_surface": str(normalized.get("active_surface") or "").strip(),
        "world_surfaces": _clean_list(normalized.get("world_surfaces"), limit=12),
        "requested_access": _clean_list(normalized.get("requested_access"), limit=8),
        "missing_access": _clean_list(normalized.get("missing_access"), limit=8),
        "granted_toolsets": _clean_list(normalized.get("granted_toolsets"), limit=8),
        "active_tools": _clean_list(normalized.get("active_tools"), limit=8),
        "block_reason": str(normalized.get("block_reason") or "").strip(),
        "retry_after_s": _int_metric(normalized.get("retry_after_s"), 0),
        "cooldown_scope": str(normalized.get("cooldown_scope") or "").strip(),
        "session_continuity": str(normalized.get("session_continuity") or "").strip(),
        "session_expires_in_s": _int_metric(normalized.get("session_expires_in_s"), 0),
        "session_recovery_mode": str(normalized.get("session_recovery_mode") or "").strip(),
        "browser_session": str(normalized.get("browser_session") or "").strip(),
        "account_state": str(normalized.get("account_state") or "").strip(),
        "cookie_state": str(normalized.get("cookie_state") or "").strip(),
        "api_key_state": str(normalized.get("api_key_state") or "").strip(),
        "quota_state": str(normalized.get("quota_state") or "").strip(),
        "filesystem_state": str(normalized.get("filesystem_state") or "").strip(),
        "sandbox_mode": str(normalized.get("sandbox_mode") or "").strip(),
        "network_access": str(normalized.get("network_access") or "").strip(),
        "access_acquire_proposals": normalize_access_acquire_proposals(
            normalized.get("access_acquire_proposals")
        ),
        "selected_access_proposal": normalize_access_acquire_proposal(
            normalized.get("selected_access_proposal")
        ),
        "artifact_continuity": str(normalized.get("artifact_continuity") or "").strip(),
        "active_artifact_kind": str(normalized.get("active_artifact_kind") or "").strip(),
        "active_artifact_ref": str(normalized.get("active_artifact_ref") or "").strip(),
        "workspace_root": str(normalized.get("workspace_root") or "").strip(),
        "active_artifact_label": str(normalized.get("active_artifact_label") or "").strip(),
        "artifact_age_s": _int_metric(normalized.get("artifact_age_s"), 0),
        "artifact_reacquisition_mode": str(normalized.get("artifact_reacquisition_mode") or "").strip(),
        "artifact_mutation_mode": str(normalized.get("artifact_mutation_mode") or "").strip(),
        "artifact_carrier": str(normalized.get("artifact_carrier") or "").strip(),
        "artifact_source_ref_ids": _clean_int_list(normalized.get("artifact_source_ref_ids"), limit=8),
        "preferred_source_ref_id": _int_metric(normalized.get("preferred_source_ref_id"), 0),
        "preferred_anchor_reason": str(normalized.get("preferred_anchor_reason") or "").strip(),
        "artifact_source_url": str(normalized.get("artifact_source_url") or "").strip(),
        "artifact_source_query": str(normalized.get("artifact_source_query") or "").strip(),
        "artifact_source_title": str(normalized.get("artifact_source_title") or "").strip(),
        "artifact_source_tool_name": str(normalized.get("artifact_source_tool_name") or "").strip(),
        "primary_proposal_id": str(normalized.get("primary_proposal_id") or "").strip(),
        "primary_status": str(normalized.get("primary_status") or "").strip(),
        "procedural_growth": bool(normalized.get("procedural_growth", False)),
        "environmental_friction": bool(normalized.get("environmental_friction", False)),
        "requested_help": bool(normalized.get("requested_help", False)),
    }


def compact_source_anchor_parts(
    state: Any,
    *,
    label_fallback: str = "",
    include_refs: bool = True,
) -> list[str]:
    if not isinstance(state, dict):
        return []
    artifact_carrier = str(state.get("artifact_carrier") or "").strip().lower()
    source_ref_ids = _clean_int_list(state.get("artifact_source_ref_ids"), limit=8)
    preferred_source_ref_id = _int_metric(state.get("preferred_source_ref_id"), 0)
    preferred_anchor_reason = str(state.get("preferred_anchor_reason") or "").strip()
    source_title = str(state.get("artifact_source_title") or "").strip() or str(label_fallback or "").strip()
    source_query = str(state.get("artifact_source_query") or "").strip()
    source_url = str(state.get("artifact_source_url") or "").strip()
    if not any(
        (
            artifact_carrier == "source_ref",
            source_ref_ids,
            preferred_source_ref_id > 0,
            preferred_anchor_reason,
            source_title,
            source_query,
            source_url,
        )
    ):
        return []
    parts: list[str] = []
    source_label = source_title or source_query or source_url
    if source_label:
        compact_label = source_label.replace("\n", " ").strip()
        if len(compact_label) > 48:
            compact_label = compact_label[:45] + "..."
        parts.append("source=" + compact_label)
    if preferred_source_ref_id > 0 or preferred_anchor_reason:
        preferred_label = "pref="
        preferred_label += str(preferred_source_ref_id) if preferred_source_ref_id > 0 else "-"
        if preferred_anchor_reason:
            preferred_label += "@" + preferred_anchor_reason[:40]
        parts.append(preferred_label)
    if include_refs:
        if source_ref_ids:
            compact_refs = ",".join(str(ref_id) for ref_id in source_ref_ids[:3])
            if len(source_ref_ids) > 3:
                compact_refs += ",..."
            parts.append("refs=" + compact_refs)
        elif preferred_source_ref_id > 0:
            parts.append(f"refs={preferred_source_ref_id}")
    return parts


def render_embodied_context_text(state: Any) -> str:
    context = _embodied_context_summary(state)
    if not context:
        return ""
    parts = ["bodyfx=" + (str(context.get("kind") or "").strip() or "-")]
    requested_access = _clean_list(context.get("requested_access"), limit=2)
    missing_access = _clean_list(context.get("missing_access"), limit=2)
    granted_toolsets = _clean_list(context.get("granted_toolsets"), limit=2)
    active_tools = _clean_list(context.get("active_tools"), limit=2)
    retry_after_s = _int_metric(context.get("retry_after_s"), 0)
    cooldown_scope = str(context.get("cooldown_scope") or "").strip()
    session_continuity = str(context.get("session_continuity") or "").strip()
    session_expires_in_s = _int_metric(context.get("session_expires_in_s"), 0)
    session_recovery_mode = str(context.get("session_recovery_mode") or "").strip()
    filesystem_state = str(context.get("filesystem_state") or "").strip()
    network_access = str(context.get("network_access") or "").strip()
    selected_access_proposal = (
        context.get("selected_access_proposal")
        if isinstance(context.get("selected_access_proposal"), dict)
        else {}
    )
    if not selected_access_proposal:
        proposals = context.get("access_acquire_proposals") if isinstance(context.get("access_acquire_proposals"), list) else []
        if proposals and isinstance(proposals[0], dict):
            selected_access_proposal = proposals[0]
    artifact_continuity = str(context.get("artifact_continuity") or "").strip()
    artifact_kind = str(context.get("active_artifact_kind") or "").strip()
    artifact_label = (
        str(context.get("active_artifact_label") or "").strip()
        or str(context.get("active_artifact_ref") or "").strip()
        or artifact_kind
    )
    artifact_reacquisition = str(context.get("artifact_reacquisition_mode") or "").strip()
    artifact_mutation = str(context.get("artifact_mutation_mode") or "").strip()
    workspace_root = str(context.get("workspace_root") or "").strip().replace("\\", "/")
    if requested_access:
        parts.append("ask=" + ",".join(requested_access))
    if missing_access:
        parts.append("missing=" + ",".join(missing_access))
    if granted_toolsets:
        parts.append("grant=" + ",".join(granted_toolsets))
    elif active_tools:
        parts.append("tools=" + ",".join(active_tools))
    if retry_after_s > 0:
        retry_label = f"retry={retry_after_s}s"
        if cooldown_scope:
            retry_label += f"@{cooldown_scope}"
        parts.append(retry_label)
    if session_continuity and (
        session_continuity != "stable" or session_expires_in_s > 0 or session_recovery_mode
    ):
        session_label = f"session={session_continuity}"
        if session_expires_in_s > 0:
            session_label += f":{session_expires_in_s}s"
        if session_recovery_mode:
            session_label += f":{session_recovery_mode}"
        parts.append(session_label)
    if filesystem_state:
        parts.append("fs=" + filesystem_state)
    if network_access:
        parts.append("net=" + network_access)
    selected_mode = str(selected_access_proposal.get("mode") or "").strip()
    selected_target = str(selected_access_proposal.get("target") or "").strip()
    if selected_mode:
        proposal_label = "proposal=" + selected_mode
        if selected_target:
            proposal_label += "@" + selected_target
        parts.append(proposal_label)
    if artifact_continuity:
        artifact_text = artifact_kind or "artifact"
        if artifact_label:
            artifact_text += ":" + artifact_label[:40]
        artifact_text += ":" + artifact_continuity
        if artifact_mutation:
            artifact_text += ":" + artifact_mutation
        if artifact_reacquisition:
            artifact_text += ":" + artifact_reacquisition
        parts.append(artifact_text)
    elif artifact_mutation:
        parts.append("mutate=" + artifact_mutation)
    parts.extend(compact_source_anchor_parts(context, label_fallback=artifact_label))
    if workspace_root:
        if len(workspace_root) > 60:
            workspace_root = "..." + workspace_root[-57:]
        parts.append("root=" + workspace_root)
    if bool(context.get("requested_help", False)):
        parts.append("help=yes")
    if bool(context.get("procedural_growth", False)):
        parts.append("growth=yes")
    if bool(context.get("environmental_friction", False)):
        parts.append("friction=yes")
    status = str(context.get("primary_status") or "").strip()
    if status:
        parts.append("status=" + status)
    return " ".join(parts)


def compact_counterpart_assessment_preview_line(row: dict[str, Any] | None) -> str:
    if not isinstance(row, dict):
        return ""
    parts: list[str] = []
    stance = str(row.get("stance") or "").strip() or "-"
    scene = str(row.get("scene") or "").strip()
    header = stance + (f"/{scene}" if scene else "")
    parts.append(header)
    parts.append(f"respect={_metric(row.get('respect_level'), 0.5):.2f}")
    parts.append(f"reciprocity={_metric(row.get('reciprocity'), 0.5):.2f}")
    embodied_line = render_embodied_context_text(row.get("embodied_context"))
    if embodied_line:
        parts.append(embodied_line)
    return " ".join(part for part in parts if part)


def compact_proactive_continuity_preview_line(row: dict[str, Any] | None) -> str:
    if not isinstance(row, dict):
        return ""
    parts: list[str] = []
    trace_family = str(row.get("trace_family") or "").strip() or "-"
    kind = str(row.get("kind") or "").strip()
    header = trace_family + (f"/{kind}" if kind else "")
    parts.append(header)
    carryover_mode = str(row.get("carryover_mode") or "").strip() or "-"
    parts.append(f"carry={carryover_mode}:{_metric(row.get('carryover_strength'), 0.0):.2f}")
    embodied_line = render_embodied_context_text(row.get("embodied_context"))
    if embodied_line:
        parts.append(embodied_line)
    return " ".join(part for part in parts if part)


def compact_event_residue_preview_line(summary: dict[str, Any] | None) -> str:
    if not isinstance(summary, dict):
        return ""
    parts: list[str] = []
    event_kind = str(summary.get("event_kind") or "").strip() or "-"
    source = str(summary.get("source") or "").strip()
    header = event_kind + (f"@{source}" if source else "")
    parts.append(header)
    response_style_hint = str(summary.get("response_style_hint") or "").strip()
    if response_style_hint:
        parts.append(f"style={response_style_hint}")
    appraisal_label = str(summary.get("appraisal_label") or "").strip()
    appraisal_confidence = _metric(summary.get("appraisal_confidence"), 0.0)
    if appraisal_label:
        parts.append(f"app={appraisal_label}:{appraisal_confidence:.2f}")
    embodied_line = render_embodied_context_text(summary.get("digital_body_consequence"))
    if embodied_line:
        parts.append(embodied_line)
    return " ".join(part for part in parts if part)


def compact_revision_trace_preview_line(row: dict[str, Any] | None) -> str:
    if not isinstance(row, dict):
        return ""
    parts: list[str] = []
    namespace = str(row.get("namespace") or "").strip()
    target_id = str(row.get("target_id") or "").strip()
    source = str(row.get("source") or "").strip()
    header = namespace or source or "-"
    if target_id:
        header += f"/{target_id}"
    if source and source != namespace:
        header += f"@{source}"
    if header:
        parts.append(header)
    embodied_line = render_embodied_context_text(row.get("embodied_context"))
    if embodied_line:
        parts.append(embodied_line)
    return " ".join(part for part in parts if part)


def build_embodied_preview_line(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    embodied = item.get("embodied_context") if isinstance(item.get("embodied_context"), dict) else {}
    digital_body_consequence = (
        item.get("digital_body_consequence")
        if isinstance(item.get("digital_body_consequence"), dict)
        else {}
    )
    if not embodied and not digital_body_consequence:
        return ""
    if any(
        (
            str(item.get("stance") or "").strip(),
            str(item.get("scene") or "").strip(),
            "respect_level" in item,
            "reciprocity" in item,
        )
    ):
        return compact_counterpart_assessment_preview_line(item)
    if any(
        (
            str(item.get("trace_family") or "").strip(),
            str(item.get("carryover_mode") or "").strip(),
            "carryover_strength" in item,
        )
    ):
        return compact_proactive_continuity_preview_line(item)
    if any(
        (
            str(item.get("event_kind") or "").strip(),
            str(item.get("response_style_hint") or "").strip(),
            str(item.get("appraisal_label") or "").strip(),
            bool(digital_body_consequence),
        )
    ):
        preview_line = compact_event_residue_preview_line(item)
        if preview_line:
            return preview_line
    if any(
        (
            str(item.get("namespace") or "").strip(),
            str(item.get("target_id") or "").strip(),
            str(item.get("after_summary") or "").strip(),
            str(item.get("before_summary") or "").strip(),
        )
    ):
        preview_line = compact_revision_trace_preview_line(item)
        if preview_line:
            return preview_line
    return render_embodied_context_text(embodied or digital_body_consequence)


__all__ = [
    "build_embodied_preview_line",
    "compact_counterpart_assessment_preview_line",
    "compact_event_residue_preview_line",
    "compact_proactive_continuity_preview_line",
    "compact_revision_trace_preview_line",
    "compact_source_anchor_parts",
    "render_embodied_context_text",
]
