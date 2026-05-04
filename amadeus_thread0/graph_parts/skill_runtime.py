from __future__ import annotations

from typing import Any

from ..runtime.skill_registry import get_skill_registry_manager
from .action_packets import compact_artifact_identity, normalize_action_packets
from .tool_policies import SKILL_MUTATION_TOOLS


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _clean_text(value: Any, *, limit: int = 240) -> str:
    text = str(value or "").strip()
    return text[:limit]


def _clean_id(value: Any, *, limit: int = 120) -> str:
    return _clean_text(value, limit=limit).lower()


def normalize_session_skill_state(value: Any) -> dict[str, Any]:
    row = _dict_or_empty(value)
    if not row:
        return {}
    manual_enabled = [str(item).strip().lower() for item in _list_or_empty(row.get("manual_enabled")) if str(item or "").strip()][:64]
    manual_disabled = [str(item).strip().lower() for item in _list_or_empty(row.get("manual_disabled")) if str(item or "").strip()][:64]
    pinned = [str(item).strip().lower() for item in _list_or_empty(row.get("pinned_skill_ids")) if str(item or "").strip()][:64]
    matched = [str(item).strip().lower() for item in _list_or_empty(row.get("matched_skill_ids")) if str(item or "").strip()][:64]
    active = [str(item).strip().lower() for item in _list_or_empty(row.get("active_skill_ids")) if str(item or "").strip()][:64]
    active_entries = [dict(item) for item in _list_or_empty(row.get("active_skill_entries")) if isinstance(item, dict)][:8]
    catalog_entries = [dict(item) for item in _list_or_empty(row.get("catalog_entries")) if isinstance(item, dict)][:64]
    matched_entries = [dict(item) for item in _list_or_empty(row.get("matched_skill_entries")) if isinstance(item, dict)][:16]
    pending_skill_proposal = row.get("pending_skill_proposal") if isinstance(row.get("pending_skill_proposal"), dict) else {}
    return {
        "catalog_version": _clean_text(row.get("catalog_version"), limit=120),
        "catalog_entries": catalog_entries,
        "manual_enabled": manual_enabled,
        "manual_disabled": manual_disabled,
        "pinned_skill_ids": pinned,
        "matched_skill_ids": matched,
        "matched_skill_entries": matched_entries,
        "active_skill_ids": active,
        "active_skill_entries": active_entries,
        "pending_skill_proposal": dict(pending_skill_proposal),
        "manual_overrides": {
            "enabled": manual_enabled,
            "disabled": manual_disabled,
            "pinned": pinned,
        },
    }


def _catalog_lookup(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for key in ("catalog_entries", "matched_skill_entries", "active_skill_entries"):
        for item in _list_or_empty(state.get(key)):
            if not isinstance(item, dict):
                continue
            skill_id = _clean_id(item.get("skill_id"))
            if not skill_id:
                continue
            lookup[skill_id] = dict(item)
    return lookup


def _artifact_identity_from_body(digital_body_state: Any) -> dict[str, str]:
    body = _dict_or_empty(digital_body_state)
    resource_state = body.get("resource_state") if isinstance(body.get("resource_state"), dict) else {}
    return {
        "artifact_carrier": _clean_text(resource_state.get("artifact_carrier"), limit=80).lower(),
        "artifact_ref": _clean_text(resource_state.get("active_artifact_ref"), limit=320),
        "artifact_label": _clean_text(resource_state.get("active_artifact_label"), limit=160),
    }


def _skill_entry_fields(entry: dict[str, Any] | None) -> dict[str, str]:
    row = dict(entry or {})
    return {
        "skill_id": _clean_id(row.get("skill_id")),
        "name": _clean_text(row.get("name") or row.get("skill_id"), limit=160),
        "version": _clean_text(row.get("version"), limit=80),
        "source": _clean_text(row.get("source"), limit=160),
        "trust_tier": _clean_text(row.get("trust_tier"), limit=80).lower(),
    }


def _normalize_skill_effect(effect: Any) -> dict[str, Any]:
    row = _dict_or_empty(effect)
    if not row:
        return {}
    normalized = {
        "skill_id": _clean_id(row.get("skill_id")),
        "name": _clean_text(row.get("name") or row.get("skill_id"), limit=160),
        "version": _clean_text(row.get("version"), limit=80),
        "source": _clean_text(row.get("source"), limit=160),
        "trust_tier": _clean_text(row.get("trust_tier"), limit=80).lower(),
        "status": _clean_text(row.get("status"), limit=80).lower(),
        "operation": _clean_text(row.get("operation"), limit=80).lower(),
        "use_kind": _clean_text(row.get("use_kind"), limit=80).lower(),
        "tool_name": _clean_text(row.get("tool_name"), limit=120).lower(),
        "artifact_carrier": _clean_text(row.get("artifact_carrier"), limit=80).lower(),
        "artifact_ref": _clean_text(row.get("artifact_ref"), limit=320),
        "artifact_label": _clean_text(row.get("artifact_label"), limit=160),
    }
    if not any(
        (
            normalized["skill_id"],
            normalized["status"],
            normalized["operation"],
            normalized["use_kind"],
            normalized["tool_name"],
            normalized["artifact_ref"],
            normalized["artifact_label"],
        )
    ):
        return {}
    return normalized


def normalize_skill_effects(value: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str, str]] = set()
    for item in _list_or_empty(value):
        normalized = _normalize_skill_effect(item)
        if not normalized:
            continue
        key = (
            str(normalized.get("skill_id") or ""),
            str(normalized.get("operation") or ""),
            str(normalized.get("use_kind") or ""),
            str(normalized.get("status") or ""),
            str(normalized.get("tool_name") or ""),
            str(normalized.get("artifact_ref") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(normalized)
        if len(out) >= 8:
            break
    return out


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        cast = float(value)
    except Exception:
        cast = float(default)
    return max(0.0, min(1.0, cast))


def _normalize_procedural_continuity(value: Any) -> dict[str, Any]:
    row = _dict_or_empty(value)
    if not row:
        return {}
    family = _clean_text(row.get("capability_family"), limit=80).lower()
    pattern = _clean_text(row.get("pattern"), limit=160).lower()
    if family not in {"skill", "sandbox", "browser", "workspace"}:
        return {}
    if not pattern:
        return {}
    identity_safe = bool(row.get("identity_safe", False))
    if not identity_safe:
        return {}
    evidence_count = max(1, min(999, int(row.get("evidence_count") or 1)))
    normalized = {
        "capability_family": family,
        "pattern": pattern,
        "confidence": round(_clamp01(row.get("confidence"), 0.0), 3),
        "evidence_count": evidence_count,
        "last_success_ref": _clean_text(row.get("last_success_ref"), limit=180),
        "identity_safe": True,
    }
    if normalized["confidence"] <= 0.0:
        normalized["confidence"] = 0.1
    return normalized


def normalize_procedural_continuity(value: Any) -> dict[str, Any]:
    return _normalize_procedural_continuity(value)


def _tool_use_kind(tool_name: str) -> str:
    name = _clean_text(tool_name, limit=120).lower()
    if name in {"inspect_source_ref", "compare_source_refs"}:
        return "source_ref_continuity"
    if name in {
        "inspect_workspace_path",
        "write_workspace_file",
        "append_workspace_file",
        "replace_workspace_text",
        "replace_workspace_lines",
        "execute_workspace_command",
    }:
        return "workspace_workflow"
    if name in {"search_web", "search_skills", "list_runtime_skills", "inspect_skill"}:
        return "research_workflow"
    return "tool_guidance" if name else ""


def _completed_status(value: Any) -> bool:
    return _clean_text(value, limit=80).lower() == "completed"


def _procedural_family_from_consequence(kind: str, tool_name: str) -> str:
    if kind == "skill_usage_completed":
        return "skill"
    if kind == "sandbox_execution_completed" or tool_name == "execute_workspace_command":
        return "sandbox"
    if kind in {
        "browser_navigation_completed",
        "browser_interaction_completed",
        "browser_download_completed",
        "browser_upload_completed",
    } or tool_name.startswith("browser_"):
        return "browser"
    if kind in {
        "workspace_file_updated",
        "workspace_path_inspected",
        "workspace_access_resolved",
        "workspace_root_attached",
        "artifact_reacquired",
    } or tool_name in {
        "inspect_workspace_path",
        "write_workspace_file",
        "append_workspace_file",
        "replace_workspace_text",
        "replace_workspace_lines",
        "reacquire_artifact",
    }:
        return "workspace"
    return ""


def _procedural_pattern_from_consequence(row: dict[str, Any], family: str) -> str:
    skill_effects = normalize_skill_effects(row.get("skill_effects"))
    primary_skill = dict(skill_effects[0]) if skill_effects else {}
    tool_name = _clean_text(row.get("primary_tool_name") or primary_skill.get("tool_name"), limit=120).lower()
    if family == "skill":
        artifact_carrier = _clean_text(row.get("artifact_carrier"), limit=80).lower()
        source_ref_ids = _list_or_empty(row.get("artifact_source_ref_ids"))
        if artifact_carrier == "source_ref" or source_ref_ids:
            return "source_ref_continuity"
        return (
            _clean_text(primary_skill.get("use_kind"), limit=120).lower()
            or _tool_use_kind(tool_name)
            or _clean_text(primary_skill.get("operation"), limit=80).lower()
            or "skill_usage"
        )
    if family == "sandbox":
        return (
            _clean_text(row.get("sandbox_command_profile"), limit=120).lower()
            or _clean_text(row.get("execution_profile"), limit=120).lower()
            or _clean_text(row.get("primary_intent"), limit=120).lower().replace("sandbox:", "")
            or tool_name
            or "workspace_command"
        )
    if family == "browser":
        return (
            _clean_text(row.get("browser_last_action_kind"), limit=120).lower()
            or tool_name.removeprefix("browser_")
            or "browser_action"
        )
    if family == "workspace":
        mutation_mode = _clean_text(row.get("artifact_mutation_mode"), limit=80).lower()
        if mutation_mode:
            return mutation_mode
        return {
            "inspect_workspace_path": "inspect",
            "write_workspace_file": "write",
            "append_workspace_file": "append",
            "replace_workspace_text": "replace",
            "replace_workspace_lines": "replace",
            "reacquire_artifact": "reacquire",
        }.get(tool_name, _clean_text(row.get("active_artifact_kind"), limit=80).lower() or "workspace")
    return ""


def derive_procedural_continuity(consequence: Any) -> dict[str, Any]:
    row = _dict_or_empty(consequence)
    if not row:
        return {}
    kind = _clean_text(row.get("kind"), limit=120).lower()
    primary_status = _clean_text(row.get("primary_status"), limit=80).lower()
    primary_tool_name = _clean_text(row.get("primary_tool_name"), limit=120).lower()
    skill_effects = normalize_skill_effects(row.get("skill_effects"))
    if not _completed_status(primary_status):
        return {}
    if kind in {"skill_install_completed", "skill_activation_changed", "skill_mutation_blocked"}:
        return {}
    if kind in {
        "sandbox_execution_blocked",
        "browser_action_blocked",
        "browser_takeover_requested",
        "access_request_pending",
        "environmental_friction",
    }:
        return {}
    if bool(row.get("environmental_friction", False)) or bool(row.get("requested_help", False)):
        return {}
    if skill_effects and any(_clean_text(item.get("status"), limit=80).lower() != "completed" for item in skill_effects):
        return {}

    family = _procedural_family_from_consequence(kind, primary_tool_name)
    if not family:
        return {}
    pattern = _procedural_pattern_from_consequence(row, family)
    if not pattern:
        return {}
    last_success_ref = (
        _clean_text(row.get("primary_proposal_id"), limit=180)
        or _clean_text(row.get("sandbox_run_id"), limit=180)
        or _clean_text(row.get("browser_run_id"), limit=180)
        or _clean_text(row.get("active_artifact_ref"), limit=180)
    )
    evidence_count = max(1, len(skill_effects) if family == "skill" and skill_effects else 1)
    confidence = 0.54
    if family == "skill":
        confidence += 0.08
    if family == "sandbox" and _clean_text(row.get("sandbox_run_id"), limit=120):
        confidence += 0.10
    if family == "browser" and _clean_text(row.get("browser_run_id"), limit=120):
        confidence += 0.10
    if family == "workspace" and _clean_text(row.get("workspace_root"), limit=320):
        confidence += 0.08
    if _clean_text(row.get("active_artifact_ref"), limit=220):
        confidence += 0.04
    return normalize_procedural_continuity(
        {
            "capability_family": family,
            "pattern": pattern,
            "confidence": confidence,
            "evidence_count": evidence_count,
            "last_success_ref": last_success_ref,
            "identity_safe": True,
        }
    )


def derive_skill_effects(
    session_skill_state: Any,
    action_packets: Any,
    *,
    digital_body_state: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    state = normalize_session_skill_state(session_skill_state)
    packets = normalize_action_packets(action_packets)
    if not state and not packets:
        return []

    catalog_lookup = _catalog_lookup(state)
    active_entries = [
        dict(item)
        for item in _list_or_empty(state.get("active_skill_entries"))
        if isinstance(item, dict)
    ]
    fallback_artifact = _artifact_identity_from_body(digital_body_state)
    derived: list[dict[str, Any]] = []

    for packet in packets[:8]:
        tool_name = _clean_text(packet.get("tool_name"), limit=120).lower()
        status = _clean_text(packet.get("status"), limit=80).lower()
        tool_args = packet.get("tool_args") if isinstance(packet.get("tool_args"), dict) else {}
        artifact_identity = compact_artifact_identity(packet.get("artifact_context")) or {}
        artifact_carrier = _clean_text(
            artifact_identity.get("artifact_carrier") or fallback_artifact.get("artifact_carrier"),
            limit=80,
        ).lower()
        artifact_ref = _clean_text(
            artifact_identity.get("active_artifact_ref") or fallback_artifact.get("artifact_ref"),
            limit=320,
        )
        artifact_label = _clean_text(
            artifact_identity.get("active_artifact_label") or fallback_artifact.get("artifact_label"),
            limit=160,
        )

        if tool_name in SKILL_MUTATION_TOOLS:
            skill_id = _clean_id(tool_args.get("skill_id"))
            entry = _skill_entry_fields(catalog_lookup.get(skill_id))
            derived.append(
                {
                    **entry,
                    "skill_id": skill_id or entry.get("skill_id", ""),
                    "name": entry.get("name") or skill_id,
                    "version": _clean_text(tool_args.get("resolved_version"), limit=80) or entry.get("version", ""),
                    "source": _clean_text(tool_args.get("source"), limit=160) or entry.get("source", ""),
                    "status": status,
                    "operation": tool_name.replace("_skill", ""),
                    "use_kind": "",
                    "tool_name": tool_name,
                    "artifact_carrier": artifact_carrier,
                    "artifact_ref": artifact_ref,
                    "artifact_label": artifact_label,
                }
            )
            continue

        if status != "completed" or not tool_name:
            continue
        for entry in active_entries[:8]:
            allowed_tools = [
                _clean_text(item, limit=120).lower()
                for item in _list_or_empty(entry.get("allowed_tools"))
                if _clean_text(item, limit=120)
            ]
            if tool_name not in allowed_tools:
                continue
            entry_fields = _skill_entry_fields(entry)
            derived.append(
                {
                    **entry_fields,
                    "status": "completed",
                    "operation": "use",
                    "use_kind": _tool_use_kind(tool_name),
                    "tool_name": tool_name,
                    "artifact_carrier": artifact_carrier,
                    "artifact_ref": artifact_ref,
                    "artifact_label": artifact_label,
                }
            )

    return normalize_skill_effects(derived)


def session_skill_state_has_signal(value: Any) -> bool:
    row = normalize_session_skill_state(value)
    if not row:
        return False
    return any(
        (
            str(row.get("catalog_version") or "").strip(),
            bool(row.get("catalog_entries")),
            bool(row.get("manual_enabled")),
            bool(row.get("manual_disabled")),
            bool(row.get("pinned_skill_ids")),
            bool(row.get("matched_skill_ids")),
            bool(row.get("active_skill_ids")),
            bool(row.get("pending_skill_proposal")),
        )
    )


def pending_skill_proposal_from_state(pending_action_proposal: Any) -> dict[str, Any]:
    proposal = _dict_or_empty(pending_action_proposal)
    tool_name = _clean_text(proposal.get("tool_name"), limit=80).lower()
    if not tool_name or tool_name not in SKILL_MUTATION_TOOLS:
        return {}
    tool_args = proposal.get("tool_args") if isinstance(proposal.get("tool_args"), dict) else {}
    return {
        "proposal_id": _clean_text(proposal.get("proposal_id"), limit=120),
        "operation": tool_name,
        "skill_id": _clean_text(tool_args.get("skill_id"), limit=120).lower(),
        "resolved_version": _clean_text(tool_args.get("resolved_version"), limit=80),
        "source": _clean_text(tool_args.get("source"), limit=160),
        "hash": _clean_text(tool_args.get("hash"), limit=128).lower(),
        "requested_permissions": [
            str(item).strip().lower()
            for item in _list_or_empty(tool_args.get("requested_permissions"))
            if str(item or "").strip()
        ][:16],
        "sandbox_profiles": [
            str(item).strip().lower()
            for item in _list_or_empty(tool_args.get("sandbox_profiles"))
            if str(item or "").strip()
        ][:16],
        "verification_summary": _clean_text(tool_args.get("verification_summary"), limit=320),
    }


def derive_session_skill_state(
    *,
    thread_id: str,
    query_text: str,
    current_event: dict[str, Any] | None,
    digital_body_state: dict[str, Any] | None,
    pending_action_proposal: dict[str, Any] | None,
) -> dict[str, Any]:
    manager = get_skill_registry_manager()
    state = manager.compute_session_skill_state(
        thread_id=thread_id,
        query_text=query_text,
        current_event=current_event,
        digital_body_state=digital_body_state,
        pending_skill_proposal=pending_skill_proposal_from_state(pending_action_proposal),
    )
    return normalize_session_skill_state(state)


def backend_skill_envelope(value: Any, *, pending_action_proposal: dict[str, Any] | None = None) -> dict[str, Any]:
    state = normalize_session_skill_state(value)
    pending = dict(state.get("pending_skill_proposal") or {})
    if not pending and isinstance(pending_action_proposal, dict):
        pending = pending_skill_proposal_from_state(pending_action_proposal)
    return {
        "installed": list(state.get("catalog_entries") or []),
        "matched": list(state.get("matched_skill_entries") or []),
        "active": [
            {
                "skill_id": str(item.get("skill_id") or ""),
                "name": str(item.get("name") or ""),
                "description": str(item.get("description") or ""),
                "version": str(item.get("version") or ""),
                "kind": str(item.get("kind") or ""),
                "source": str(item.get("source") or ""),
                "trust_tier": str(item.get("trust_tier") or ""),
                "required_surfaces": list(item.get("required_surfaces") or []),
                "allowed_tools": list(item.get("allowed_tools") or []),
                "sandbox_profiles": list(item.get("sandbox_profiles") or []),
                "skill_excerpt": str(item.get("skill_excerpt") or ""),
            }
            for item in _list_or_empty(state.get("active_skill_entries"))
            if isinstance(item, dict)
        ],
        "manual_overrides": dict(state.get("manual_overrides") or {}),
        "pending_approval": pending,
    }


def active_skill_prompt_block(value: Any) -> str:
    state = normalize_session_skill_state(value)
    active_entries = [item for item in _list_or_empty(state.get("active_skill_entries")) if isinstance(item, dict)]
    if not active_entries:
        return ""
    lines: list[str] = [
        "- skills 只影响工具选择、执行策略和资源绑定，不改写人格核心、关系立场或最终审批边界。"
    ]
    for item in active_entries[:4]:
        name = _clean_text(item.get("name") or item.get("skill_id"), limit=120)
        description = _clean_text(item.get("description"), limit=220)
        triggers = ", ".join(str(part) for part in _list_or_empty(item.get("triggers"))[:4])
        surfaces = ", ".join(str(part) for part in _list_or_empty(item.get("required_surfaces"))[:4])
        tools = ", ".join(str(part) for part in _list_or_empty(item.get("allowed_tools"))[:6])
        excerpt = _clean_text(item.get("skill_excerpt"), limit=800)
        line = f"- {name}: {description}" if description else f"- {name}"
        if triggers:
            line += f" | triggers={triggers}"
        if surfaces:
            line += f" | surfaces={surfaces}"
        if tools:
            line += f" | tools={tools}"
        if excerpt:
            line += f" | instructions={excerpt}"
        lines.append(line)
    return "可用技能提示:\n" + "\n".join(lines)


__all__ = [
    "active_skill_prompt_block",
    "backend_skill_envelope",
    "derive_procedural_continuity",
    "derive_skill_effects",
    "derive_session_skill_state",
    "normalize_procedural_continuity",
    "normalize_session_skill_state",
    "normalize_skill_effects",
    "pending_skill_proposal_from_state",
    "session_skill_state_has_signal",
]
