from __future__ import annotations

from typing import Any

from .action_packets import compact_artifact_identity, normalize_action_packets

_OWN_RHYTHM_EVENT_KINDS = {
    "self_activity_state",
    "time_idle",
    "scheduled_checkin_due",
    "scheduled_life_due",
}

_EVENT_SURFACE_BY_KIND = {
    "user_utterance": "dialogue",
    "gesture_signal": "gesture",
    "ambient_shift": "ambient",
    "scene_observation": "scene",
    "time_idle": "idle",
    "self_activity_state": "self_rhythm",
    "scheduled_checkin_due": "scheduler",
    "scheduled_life_due": "scheduler",
}

_SESSION_PRESENT_STATES = {"present", "active", "ready", "available"}
_ACCOUNT_PRESENT_STATES = {"present", "active", "logged_in", "ready", "available"}
_COOKIE_PRESENT_STATES = {"present", "active", "ready", "available"}
_SESSION_EXPIRING_SOON_S = 900
_ARTIFACT_BROWSER_KINDS = {"page", "tab", "site", "browser_page", "search_result"}
_ARTIFACT_FILESYSTEM_KINDS = {"file", "workspace", "document", "buffer", "notebook"}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _clean_text(value: Any, *, limit: int = 160) -> str:
    return str(value or "").strip()[:limit]


def _clean_state_label(value: Any, *, limit: int = 80) -> str:
    return _clean_text(value, limit=limit).lower()


def _clean_nonnegative_int(value: Any, *, limit: int = 604800) -> int:
    try:
        return max(0, min(int(value), max(0, int(limit))))
    except Exception:
        return 0


def derive_session_lifecycle(
    *,
    browser_session: Any,
    account_state: Any,
    cookie_state: Any,
    session_continuity: Any = None,
    session_expires_in_s: Any = None,
    session_recovery_mode: Any = None,
) -> dict[str, Any]:
    browser = _clean_state_label(browser_session)
    account = _clean_state_label(account_state)
    cookie = _clean_state_label(cookie_state)
    continuity = _clean_state_label(session_continuity)
    expires_in_s = _clean_nonnegative_int(session_expires_in_s)
    recovery_mode = _clean_state_label(session_recovery_mode)

    if not continuity:
        if browser == "expired" or cookie == "expired":
            continuity = "expired"
        elif account in {"logged_out", "missing", "required"}:
            continuity = "missing"
        elif browser in {"missing", "required"} or cookie in {"missing", "required"}:
            continuity = "missing"
        elif 0 < expires_in_s <= _SESSION_EXPIRING_SOON_S:
            continuity = "expiring"
        elif browser in _SESSION_PRESENT_STATES or account in _ACCOUNT_PRESENT_STATES or cookie in _COOKIE_PRESENT_STATES:
            continuity = "stable"

    if not recovery_mode:
        if continuity == "expiring":
            recovery_mode = "refresh_session"
        elif continuity == "expired":
            if account in {"logged_out", "missing", "required"}:
                recovery_mode = "relogin"
            elif browser == "expired":
                recovery_mode = "refresh_session"
            elif cookie == "expired":
                recovery_mode = "restore_cookies"
        elif continuity == "missing":
            if account in {"logged_out", "missing", "required"}:
                recovery_mode = "relogin"
            elif cookie in {"missing", "required", "expired"}:
                recovery_mode = "restore_cookies"
            elif browser in {"missing", "required", "expired"}:
                recovery_mode = "refresh_session"

    return {
        "session_continuity": continuity,
        "session_expires_in_s": expires_in_s,
        "session_recovery_mode": recovery_mode,
    }


def derive_artifact_continuity(
    *,
    artifact_continuity: Any = None,
    active_artifact_kind: Any = None,
    active_artifact_ref: Any = None,
    active_artifact_label: Any = None,
    artifact_age_s: Any = None,
    artifact_reacquisition_mode: Any = None,
) -> dict[str, Any]:
    continuity = _clean_state_label(artifact_continuity)
    kind = _clean_state_label(active_artifact_kind)
    ref = _clean_text(active_artifact_ref, limit=220)
    label = _clean_text(active_artifact_label, limit=160)
    age_s = _clean_nonnegative_int(artifact_age_s)
    reacquisition_mode = _clean_state_label(artifact_reacquisition_mode)

    if not continuity and (kind or ref or label):
        continuity = "attached"

    return {
        "artifact_continuity": continuity,
        "active_artifact_kind": kind,
        "active_artifact_ref": ref,
        "active_artifact_label": label,
        "artifact_age_s": age_s,
        "artifact_reacquisition_mode": reacquisition_mode,
    }


def derive_artifact_identity(
    *,
    artifact_carrier: Any = None,
    artifact_source_ref_ids: Any = None,
    artifact_source_url: Any = None,
    artifact_source_query: Any = None,
    artifact_source_title: Any = None,
    artifact_source_tool_name: Any = None,
) -> dict[str, Any]:
    normalized = compact_artifact_identity(
        {
            "carrier": artifact_carrier,
            "source_ref_ids": artifact_source_ref_ids,
            "source_url": artifact_source_url,
            "source_query": artifact_source_query,
            "source_title": artifact_source_title,
            "source_tool_name": artifact_source_tool_name,
        }
    )
    if not normalized:
        return {
            "artifact_carrier": "",
            "artifact_source_ref_ids": [],
            "artifact_source_url": "",
            "artifact_source_query": "",
            "artifact_source_title": "",
            "artifact_source_tool_name": "",
        }
    return {
        "artifact_carrier": str(normalized.get("artifact_carrier") or "").strip(),
        "artifact_source_ref_ids": list(normalized.get("artifact_source_ref_ids") or [])[:8],
        "artifact_source_url": str(normalized.get("artifact_source_url") or "").strip(),
        "artifact_source_query": str(normalized.get("artifact_source_query") or "").strip(),
        "artifact_source_title": str(normalized.get("artifact_source_title") or "").strip(),
        "artifact_source_tool_name": str(normalized.get("artifact_source_tool_name") or "").strip(),
    }


def _unique_clean_list(*values: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean_text(value).lower()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _merge_unique_lists(*values: Any, limit: int = 12) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in _list_or_empty(value):
            text = _clean_text(item).lower()
            if not text or text in seen:
                continue
            seen.add(text)
            merged.append(text)
            if len(merged) >= max(1, int(limit)):
                return merged
    return merged


def _tool_surface_tags(name: Any) -> list[str]:
    text = _clean_text(name).lower()
    if not text:
        return []
    tags: list[str] = []
    if any(marker in text for marker in ("memory", "profile", "moment", "reflection", "worldline", "relationship", "diary", "commitment", "tension", "semantic", "revision")):
        tags.append("memory")
    if any(marker in text for marker in ("web", "browser", "page", "site", "search", "arxiv", "docs", "http", "url")):
        tags.append("network")
    if any(marker in text for marker in ("browser", "web", "page", "site")):
        tags.append("browser")
    if any(marker in text for marker in ("file", "fs", "workspace", "path", "glob", "grep")):
        tags.append("filesystem")
    if any(marker in text for marker in ("shell", "python", "exec", "sandbox", "command", "code")):
        tags.append("sandbox")
    if text == "request_toolset_upgrade":
        tags.append("capability_upgrade")
    return list(dict.fromkeys(tags))


def _merged_hint_payload(
    *,
    session_context: dict[str, Any] | None,
    current_event: dict[str, Any] | None,
) -> dict[str, Any]:
    hints: dict[str, Any] = {}
    event = _dict_or_empty(current_event)
    perception = _dict_or_empty(event.get("perception"))
    for source in (
        _dict_or_empty(_dict_or_empty(session_context).get("digital_body_hints")),
        _dict_or_empty(event.get("digital_body_hints")),
        _dict_or_empty(perception.get("digital_body_hints")),
    ):
        if not source:
            continue
        for key, value in source.items():
            if key in {"world_surfaces", "missing_access", "requestable_access", "constraints"}:
                hints[key] = _merge_unique_lists(hints.get(key), value, limit=16)
            elif isinstance(value, dict):
                prior = _dict_or_empty(hints.get(key))
                merged = dict(prior)
                merged.update(value)
                hints[key] = merged
            elif value not in (None, "", []):
                hints[key] = value
    return hints


def digital_body_state_has_signal(state: Any) -> bool:
    if not isinstance(state, dict) or not state:
        return False
    if _clean_text(state.get("active_surface")):
        return True
    for key in ("perception_channels", "action_channels", "world_surfaces", "available_toolsets", "active_tools", "body_constraints"):
        if isinstance(state.get(key), list) and bool(state.get(key)):
            return True
    access_state = _dict_or_empty(state.get("access_state"))
    if any(
        (
            _clean_text(access_state.get("mode")),
            _clean_text(access_state.get("block_reason")),
            isinstance(access_state.get("conditions"), list) and bool(access_state.get("conditions")),
            bool(access_state.get("external_mutation_pending", False)),
            int(access_state.get("pending_approval_count") or 0) > 0,
            isinstance(access_state.get("missing_access"), list) and bool(access_state.get("missing_access")),
            isinstance(access_state.get("requestable_access"), list) and bool(access_state.get("requestable_access")),
            _clean_text(access_state.get("browser_session")),
            _clean_text(access_state.get("account_state")),
            _clean_text(access_state.get("cookie_state")),
            _clean_text(access_state.get("api_key_state")),
            _clean_text(access_state.get("quota_state")),
            int(access_state.get("retry_after_s") or 0) > 0,
            _clean_text(access_state.get("cooldown_scope")),
            _clean_text(access_state.get("session_continuity")),
            int(access_state.get("session_expires_in_s") or 0) > 0,
            _clean_text(access_state.get("session_recovery_mode")),
            _clean_text(access_state.get("filesystem_state")),
            _clean_text(access_state.get("sandbox_mode")),
            _clean_text(access_state.get("network_access")),
        )
    ):
        return True
    resource_state = _dict_or_empty(state.get("resource_state"))
    if any(
        (
            int(resource_state.get("behavior_queue_depth") or 0) > 0,
            int(resource_state.get("action_packet_count") or 0) > 0,
            int(resource_state.get("pending_approval_count") or 0) > 0,
            int(resource_state.get("queued_packet_count") or 0) > 0,
            int(resource_state.get("executing_packet_count") or 0) > 0,
            int(resource_state.get("completed_packet_count") or 0) > 0,
            int(resource_state.get("blocked_packet_count") or 0) > 0,
            int(resource_state.get("external_tool_count") or 0) > 0,
            _clean_text(resource_state.get("artifact_continuity")),
            _clean_text(resource_state.get("active_artifact_kind")),
            _clean_text(resource_state.get("active_artifact_ref")),
            _clean_text(resource_state.get("active_artifact_label")),
            int(resource_state.get("artifact_age_s") or 0) > 0,
            _clean_text(resource_state.get("artifact_reacquisition_mode")),
            _clean_text(resource_state.get("artifact_carrier")),
            isinstance(resource_state.get("artifact_source_ref_ids"), list) and bool(resource_state.get("artifact_source_ref_ids")),
            _clean_text(resource_state.get("artifact_source_url")),
            _clean_text(resource_state.get("artifact_source_query")),
            _clean_text(resource_state.get("artifact_source_title")),
            _clean_text(resource_state.get("artifact_source_tool_name")),
        )
    ):
        return True
    return False



def normalize_embodied_context(context: Any) -> dict[str, Any]:
    row = _dict_or_empty(context)
    requested_access = _merge_unique_lists(row.get("requested_access"), limit=12)
    missing_access = _merge_unique_lists(row.get("missing_access"), limit=12)
    granted_toolsets = _merge_unique_lists(row.get("granted_toolsets"), limit=12)
    active_tools = _merge_unique_lists(row.get("active_tools"), limit=8)
    world_surfaces = _merge_unique_lists(
        row.get("world_surfaces"),
        [row.get("active_surface")] if _clean_text(row.get("active_surface")) else [],
        limit=12,
    )
    block_reason = _clean_text(row.get("block_reason"), limit=220)
    primary_status = _clean_state_label(row.get("primary_status"))
    primary_origin = _clean_state_label(row.get("primary_origin"))
    primary_intent = _clean_text(row.get("primary_intent"), limit=120).lower()
    primary_tool_name = _clean_text(row.get("primary_tool_name"), limit=120).lower()
    requested_help = bool(row.get("requested_help", False))
    environmental_friction = bool(row.get("environmental_friction", False))
    procedural_growth = bool(row.get("procedural_growth", False))
    session_continuity = _clean_state_label(row.get("session_continuity"))
    session_expires_in_s = _clean_nonnegative_int(row.get("session_expires_in_s"))
    session_recovery_mode = _clean_state_label(row.get("session_recovery_mode"))
    artifact = derive_artifact_continuity(
        artifact_continuity=row.get("artifact_continuity"),
        active_artifact_kind=row.get("active_artifact_kind"),
        active_artifact_ref=row.get("active_artifact_ref"),
        active_artifact_label=row.get("active_artifact_label"),
        artifact_age_s=row.get("artifact_age_s"),
        artifact_reacquisition_mode=row.get("artifact_reacquisition_mode"),
    )
    artifact_identity = derive_artifact_identity(
        artifact_carrier=row.get("artifact_carrier"),
        artifact_source_ref_ids=row.get("artifact_source_ref_ids"),
        artifact_source_url=row.get("artifact_source_url"),
        artifact_source_query=row.get("artifact_source_query"),
        artifact_source_title=row.get("artifact_source_title"),
        artifact_source_tool_name=row.get("artifact_source_tool_name"),
    )

    kind = _clean_state_label(row.get("kind"))
    if not kind:
        if requested_help or primary_status in {"queued", "awaiting_approval", "approved"} or requested_access:
            kind = "access_request_pending"
        elif environmental_friction or block_reason or missing_access:
            kind = "environmental_friction"
        elif procedural_growth or granted_toolsets or active_tools:
            kind = "embodied_growth"

    normalized = {
        "kind": kind,
        "summary": _clean_text(row.get("summary"), limit=220),
        "access_mode": _clean_state_label(row.get("access_mode")),
        "active_surface": _clean_state_label(row.get("active_surface")),
        "world_surfaces": world_surfaces,
        "missing_access": missing_access,
        "requested_access": requested_access,
        "granted_toolsets": granted_toolsets,
        "active_tools": active_tools,
        "block_reason": block_reason,
        "session_continuity": session_continuity,
        "session_expires_in_s": session_expires_in_s,
        "session_recovery_mode": session_recovery_mode,
        "artifact_continuity": str(artifact.get("artifact_continuity") or "").strip(),
        "active_artifact_kind": str(artifact.get("active_artifact_kind") or "").strip(),
        "active_artifact_ref": str(artifact.get("active_artifact_ref") or "").strip(),
        "active_artifact_label": str(artifact.get("active_artifact_label") or "").strip(),
        "artifact_age_s": _clean_nonnegative_int(artifact.get("artifact_age_s")),
        "artifact_reacquisition_mode": str(artifact.get("artifact_reacquisition_mode") or "").strip(),
        "artifact_carrier": str(artifact_identity.get("artifact_carrier") or "").strip(),
        "artifact_source_ref_ids": list(artifact_identity.get("artifact_source_ref_ids") or [])[:8],
        "artifact_source_url": str(artifact_identity.get("artifact_source_url") or "").strip(),
        "artifact_source_query": str(artifact_identity.get("artifact_source_query") or "").strip(),
        "artifact_source_title": str(artifact_identity.get("artifact_source_title") or "").strip(),
        "artifact_source_tool_name": str(artifact_identity.get("artifact_source_tool_name") or "").strip(),
        "primary_proposal_id": _clean_text(row.get("primary_proposal_id"), limit=128),
        "primary_status": primary_status,
        "primary_origin": primary_origin,
        "primary_intent": primary_intent,
        "primary_tool_name": primary_tool_name,
        "procedural_growth": procedural_growth,
        "environmental_friction": environmental_friction,
        "requested_help": requested_help,
    }
    if not any(
        (
            normalized["kind"],
            normalized["summary"],
            normalized["access_mode"],
            normalized["active_surface"],
            normalized["block_reason"],
            normalized["session_continuity"],
            normalized["session_expires_in_s"] > 0,
            normalized["session_recovery_mode"],
            normalized["artifact_continuity"],
            normalized["active_artifact_kind"],
            normalized["active_artifact_ref"],
            normalized["active_artifact_label"],
            normalized["artifact_age_s"] > 0,
            normalized["artifact_reacquisition_mode"],
            normalized["artifact_carrier"],
            bool(normalized["artifact_source_ref_ids"]),
            normalized["artifact_source_url"],
            normalized["artifact_source_query"],
            normalized["artifact_source_title"],
            normalized["artifact_source_tool_name"],
            normalized["primary_proposal_id"],
            normalized["primary_status"],
            normalized["primary_origin"],
            normalized["primary_intent"],
            normalized["primary_tool_name"],
            normalized["world_surfaces"],
            normalized["missing_access"],
            normalized["requested_access"],
            normalized["granted_toolsets"],
            normalized["active_tools"],
            normalized["procedural_growth"],
            normalized["environmental_friction"],
            normalized["requested_help"],
        )
    ):
        return {}
    return normalized


def embodied_context_has_signal(context: Any) -> bool:
    return bool(normalize_embodied_context(context))


def normalize_digital_body_state(state: Any) -> dict[str, Any]:
    row = _dict_or_empty(state)
    if not digital_body_state_has_signal(row):
        return {}

    access_state = _dict_or_empty(row.get("access_state"))
    resource_state = _dict_or_empty(row.get("resource_state"))
    granted_toolsets = [
        _clean_text(item).lower()
        for item in _list_or_empty(access_state.get("granted_toolsets"))
        if _clean_text(item)
    ]
    granted_toolsets = list(dict.fromkeys(granted_toolsets))[:12]
    missing_access = _merge_unique_lists(access_state.get("missing_access"), limit=12)
    requestable_access = _merge_unique_lists(access_state.get("requestable_access"), limit=12)
    browser_session = _clean_state_label(access_state.get("browser_session"))
    account_state = _clean_state_label(access_state.get("account_state"))
    cookie_state = _clean_state_label(access_state.get("cookie_state"))
    session_lifecycle = derive_session_lifecycle(
        browser_session=browser_session,
        account_state=account_state,
        cookie_state=cookie_state,
        session_continuity=access_state.get("session_continuity"),
        session_expires_in_s=access_state.get("session_expires_in_s"),
        session_recovery_mode=access_state.get("session_recovery_mode"),
    )
    artifact = derive_artifact_continuity(
        artifact_continuity=resource_state.get("artifact_continuity"),
        active_artifact_kind=resource_state.get("active_artifact_kind"),
        active_artifact_ref=resource_state.get("active_artifact_ref"),
        active_artifact_label=resource_state.get("active_artifact_label"),
        artifact_age_s=resource_state.get("artifact_age_s"),
        artifact_reacquisition_mode=resource_state.get("artifact_reacquisition_mode"),
    )
    artifact_identity = derive_artifact_identity(
        artifact_carrier=resource_state.get("artifact_carrier"),
        artifact_source_ref_ids=resource_state.get("artifact_source_ref_ids"),
        artifact_source_url=resource_state.get("artifact_source_url"),
        artifact_source_query=resource_state.get("artifact_source_query"),
        artifact_source_title=resource_state.get("artifact_source_title"),
        artifact_source_tool_name=resource_state.get("artifact_source_tool_name"),
    )

    normalized = {
        "active_surface": _clean_text(row.get("active_surface")).lower() or "dialogue",
        "perception_channels": list(dict.fromkeys(_unique_clean_list(*_list_or_empty(row.get("perception_channels")))))[:8],
        "action_channels": list(dict.fromkeys(_unique_clean_list(*_list_or_empty(row.get("action_channels")))))[:8],
        "world_surfaces": list(dict.fromkeys(_unique_clean_list(*_list_or_empty(row.get("world_surfaces")))))[:12],
        "available_toolsets": list(dict.fromkeys(_unique_clean_list(*_list_or_empty(row.get("available_toolsets")))))[:12],
        "active_tools": list(dict.fromkeys(_unique_clean_list(*_list_or_empty(row.get("active_tools")))))[:8],
        "access_state": {
            "mode": _clean_text(access_state.get("mode")).lower() or "native_only",
            "conditions": list(dict.fromkeys(_unique_clean_list(*_list_or_empty(access_state.get("conditions")))))[:8],
            "block_reason": _clean_text(access_state.get("block_reason"), limit=220),
            "retry_after_s": _clean_nonnegative_int(access_state.get("retry_after_s")),
            "cooldown_scope": _clean_state_label(access_state.get("cooldown_scope")),
            "session_continuity": str(session_lifecycle.get("session_continuity") or "").strip(),
            "session_expires_in_s": _clean_nonnegative_int(session_lifecycle.get("session_expires_in_s")),
            "session_recovery_mode": str(session_lifecycle.get("session_recovery_mode") or "").strip(),
            "pending_approval_count": max(0, int(access_state.get("pending_approval_count") or 0)),
            "external_mutation_pending": bool(access_state.get("external_mutation_pending", False)),
            "granted_toolsets": granted_toolsets,
            "missing_access": missing_access,
            "requestable_access": requestable_access,
            "browser_session": browser_session,
            "account_state": account_state,
            "cookie_state": cookie_state,
            "api_key_state": _clean_state_label(access_state.get("api_key_state")),
            "quota_state": _clean_state_label(access_state.get("quota_state")),
            "filesystem_state": _clean_state_label(access_state.get("filesystem_state")),
            "sandbox_mode": _clean_state_label(access_state.get("sandbox_mode")),
            "network_access": _clean_state_label(access_state.get("network_access")),
        },
        "resource_state": {
            "behavior_queue_depth": max(0, int(resource_state.get("behavior_queue_depth") or 0)),
            "action_packet_count": max(0, int(resource_state.get("action_packet_count") or 0)),
            "pending_approval_count": max(0, int(resource_state.get("pending_approval_count") or 0)),
            "queued_packet_count": max(0, int(resource_state.get("queued_packet_count") or 0)),
            "executing_packet_count": max(0, int(resource_state.get("executing_packet_count") or 0)),
            "completed_packet_count": max(0, int(resource_state.get("completed_packet_count") or 0)),
            "blocked_packet_count": max(0, int(resource_state.get("blocked_packet_count") or 0)),
            "external_tool_count": max(0, int(resource_state.get("external_tool_count") or 0)),
            "artifact_continuity": str(artifact.get("artifact_continuity") or "").strip(),
            "active_artifact_kind": str(artifact.get("active_artifact_kind") or "").strip(),
            "active_artifact_ref": str(artifact.get("active_artifact_ref") or "").strip(),
            "active_artifact_label": str(artifact.get("active_artifact_label") or "").strip(),
            "artifact_age_s": _clean_nonnegative_int(artifact.get("artifact_age_s")),
            "artifact_reacquisition_mode": str(artifact.get("artifact_reacquisition_mode") or "").strip(),
            "artifact_carrier": str(artifact_identity.get("artifact_carrier") or "").strip(),
            "artifact_source_ref_ids": list(artifact_identity.get("artifact_source_ref_ids") or [])[:8],
            "artifact_source_url": str(artifact_identity.get("artifact_source_url") or "").strip(),
            "artifact_source_query": str(artifact_identity.get("artifact_source_query") or "").strip(),
            "artifact_source_title": str(artifact_identity.get("artifact_source_title") or "").strip(),
            "artifact_source_tool_name": str(artifact_identity.get("artifact_source_tool_name") or "").strip(),
        },
        "body_constraints": list(dict.fromkeys(_unique_clean_list(*_list_or_empty(row.get("body_constraints")))))[:12],
    }
    return normalized



def derive_digital_body_state(
    *,
    current_event: dict[str, Any] | None,
    behavior_queue: Any,
    action_packets: Any,
    interaction_carryover: dict[str, Any] | None = None,
    toolset_unlocks: dict[str, Any] | None = None,
    autonomy_block_reason: str = "",
    session_context: dict[str, Any] | None = None,
    last_external_tools: Any = None,
) -> dict[str, Any]:
    event = _dict_or_empty(current_event)
    perception = _dict_or_empty(event.get("perception"))
    context = _dict_or_empty(session_context)
    hints = _merged_hint_payload(session_context=context, current_event=event)
    packets = normalize_action_packets(action_packets)
    queue_depth = len([item for item in _list_or_empty(behavior_queue) if isinstance(item, dict)])
    carryover = _dict_or_empty(interaction_carryover)
    carried_embodied = _dict_or_empty(carryover.get("embodied_context"))
    carried_primary_status = _clean_state_label(carried_embodied.get("primary_status"))
    carried_requested_help = bool(carried_embodied.get("requested_help", False))
    carried_block_reason = _clean_text(carried_embodied.get("block_reason"), limit=220)
    carried_granted_toolsets = _merge_unique_lists(carried_embodied.get("granted_toolsets"), limit=12)
    carried_active_tools = _merge_unique_lists(carried_embodied.get("active_tools"), limit=8)
    carried_missing_access = _merge_unique_lists(carried_embodied.get("missing_access"), limit=12)
    carried_requested_access = _merge_unique_lists(carried_embodied.get("requested_access"), limit=12)
    carried_world_surfaces = _merge_unique_lists(
        carried_embodied.get("world_surfaces"),
        [carried_embodied.get("active_surface")] if _clean_text(carried_embodied.get("active_surface")) else [],
        ["approval_gate"] if carried_primary_status == "awaiting_approval" else [],
        limit=12,
    )
    carried_artifact = derive_artifact_continuity(
        artifact_continuity=carried_embodied.get("artifact_continuity"),
        active_artifact_kind=carried_embodied.get("active_artifact_kind"),
        active_artifact_ref=carried_embodied.get("active_artifact_ref"),
        active_artifact_label=carried_embodied.get("active_artifact_label"),
        artifact_age_s=carried_embodied.get("artifact_age_s"),
        artifact_reacquisition_mode=carried_embodied.get("artifact_reacquisition_mode"),
    )
    carried_artifact_identity = derive_artifact_identity(
        artifact_carrier=carried_embodied.get("artifact_carrier"),
        artifact_source_ref_ids=carried_embodied.get("artifact_source_ref_ids"),
        artifact_source_url=carried_embodied.get("artifact_source_url"),
        artifact_source_query=carried_embodied.get("artifact_source_query"),
        artifact_source_title=carried_embodied.get("artifact_source_title"),
        artifact_source_tool_name=carried_embodied.get("artifact_source_tool_name"),
    )

    perception_channels = _unique_clean_list(
        perception.get("channel"),
        perception.get("modality"),
        _EVENT_SURFACE_BY_KIND.get(_clean_text(event.get("kind")).lower(), ""),
    )
    if not perception_channels:
        perception_channels = ["dialogue"]

    granted_toolsets = sorted(
        {
            _clean_text(key).lower()
            for key, value in _dict_or_empty(toolset_unlocks).items()
            if _clean_text(key) and int(value or 0) > 0
        }
    )
    granted_toolsets = _merge_unique_lists(granted_toolsets, carried_granted_toolsets, limit=12)
    external_tools = sorted({_clean_text(item).lower() for item in _list_or_empty(last_external_tools) if _clean_text(item)})
    active_tools = _merge_unique_lists(
        sorted(
            {
                _clean_text(packet.get("tool_name")).lower()
                for packet in packets
                if _clean_text(packet.get("tool_name"))
            }
        ),
        carried_active_tools,
        limit=8,
    )
    surface_names = [*granted_toolsets, *active_tools, *external_tools]
    world_surfaces = _merge_unique_lists(
        ["dialogue"],
        ["scheduler"] if queue_depth > 0 else [],
        ["approval_gate"] if packets else [],
        hints.get("world_surfaces"),
        carried_world_surfaces,
        *[_tool_surface_tags(name) for name in surface_names],
        limit=12,
    )

    pending_approval_count = 0
    queued_packet_count = 0
    executing_packet_count = 0
    completed_packet_count = 0
    blocked_packet_count = 0
    external_mutation_pending = False
    for packet in packets:
        status = _clean_text(packet.get("status")).lower()
        risk = _clean_text(packet.get("risk")).lower()
        requires_approval = bool(packet.get("requires_approval", False))
        if status in {"awaiting_approval"} or (requires_approval and status in {"proposed", "approved"}):
            pending_approval_count += 1
        if status in {"proposed", "queued", "approved"}:
            queued_packet_count += 1
        if status == "executing":
            executing_packet_count += 1
        if status == "completed":
            completed_packet_count += 1
        if status in {"blocked", "rejected"}:
            blocked_packet_count += 1
        if risk == "external_mutation" and status not in {"completed", "rejected", "blocked"}:
            external_mutation_pending = True
    if carried_primary_status == "awaiting_approval":
        pending_approval_count = max(pending_approval_count, 1)

    browser_session = _clean_state_label(hints.get("browser_session"))
    account_state = _clean_state_label(hints.get("account_state"))
    cookie_state = _clean_state_label(hints.get("cookie_state"))
    api_key_state = _clean_state_label(hints.get("api_key_state"))
    quota_state = _clean_state_label(hints.get("quota_state"))
    retry_after_s = _clean_nonnegative_int(hints.get("retry_after_s"))
    cooldown_scope = _clean_state_label(hints.get("cooldown_scope"))
    session_lifecycle = derive_session_lifecycle(
        browser_session=browser_session,
        account_state=account_state,
        cookie_state=cookie_state,
        session_continuity=hints.get("session_continuity"),
        session_expires_in_s=hints.get("session_expires_in_s"),
        session_recovery_mode=hints.get("session_recovery_mode"),
    )
    session_continuity = _clean_state_label(session_lifecycle.get("session_continuity"))
    session_expires_in_s = _clean_nonnegative_int(session_lifecycle.get("session_expires_in_s"))
    session_recovery_mode = _clean_state_label(session_lifecycle.get("session_recovery_mode"))
    filesystem_state = _clean_state_label(hints.get("filesystem_state"))
    sandbox_mode = _clean_state_label(hints.get("sandbox_mode"))
    network_access = _clean_state_label(hints.get("network_access"))
    artifact = derive_artifact_continuity(
        artifact_continuity=hints.get("artifact_continuity") or carried_artifact.get("artifact_continuity"),
        active_artifact_kind=hints.get("active_artifact_kind") or carried_artifact.get("active_artifact_kind"),
        active_artifact_ref=hints.get("active_artifact_ref") or carried_artifact.get("active_artifact_ref"),
        active_artifact_label=hints.get("active_artifact_label") or carried_artifact.get("active_artifact_label"),
        artifact_age_s=hints.get("artifact_age_s") or carried_artifact.get("artifact_age_s"),
        artifact_reacquisition_mode=hints.get("artifact_reacquisition_mode")
        or carried_artifact.get("artifact_reacquisition_mode"),
    )
    artifact_identity = derive_artifact_identity(
        artifact_carrier=hints.get("artifact_carrier") or carried_artifact_identity.get("artifact_carrier"),
        artifact_source_ref_ids=hints.get("artifact_source_ref_ids")
        or carried_artifact_identity.get("artifact_source_ref_ids"),
        artifact_source_url=hints.get("artifact_source_url") or carried_artifact_identity.get("artifact_source_url"),
        artifact_source_query=hints.get("artifact_source_query") or carried_artifact_identity.get("artifact_source_query"),
        artifact_source_title=hints.get("artifact_source_title") or carried_artifact_identity.get("artifact_source_title"),
        artifact_source_tool_name=hints.get("artifact_source_tool_name")
        or carried_artifact_identity.get("artifact_source_tool_name"),
    )
    artifact_continuity = _clean_state_label(artifact.get("artifact_continuity"))
    active_artifact_kind = _clean_state_label(artifact.get("active_artifact_kind"))
    active_artifact_ref = _clean_text(artifact.get("active_artifact_ref"), limit=220)
    active_artifact_label = _clean_text(artifact.get("active_artifact_label"), limit=160)
    artifact_age_s = _clean_nonnegative_int(artifact.get("artifact_age_s"))
    artifact_reacquisition_mode = _clean_state_label(artifact.get("artifact_reacquisition_mode"))
    artifact_carrier = _clean_state_label(artifact_identity.get("artifact_carrier"))
    artifact_source_ref_ids = list(artifact_identity.get("artifact_source_ref_ids") or [])[:8]
    artifact_source_url = _clean_text(artifact_identity.get("artifact_source_url"), limit=320)
    artifact_source_query = _clean_text(artifact_identity.get("artifact_source_query"), limit=220)
    artifact_source_title = _clean_text(artifact_identity.get("artifact_source_title"), limit=160)
    artifact_source_tool_name = _clean_state_label(artifact_identity.get("artifact_source_tool_name"))
    cooldown_active = retry_after_s > 0
    conditions: list[str] = []
    if pending_approval_count > 0:
        conditions.append("human_approval_required")
    if external_mutation_pending:
        conditions.append("external_mutation_gated")
    block_reason = _clean_text(autonomy_block_reason, limit=220) or carried_block_reason
    if cooldown_active:
        conditions.append("cooldown_active")
        if cooldown_scope:
            conditions.append(f"{cooldown_scope}_cooldown_active")
    if session_continuity == "expiring":
        conditions.append("session_expiring_soon")
    elif session_continuity == "expired":
        conditions.append("session_expired")
    if session_recovery_mode == "refresh_session":
        conditions.append("session_refresh_available")
    elif session_recovery_mode == "restore_cookies":
        conditions.append("cookie_restore_available")
    if artifact_continuity == "stale":
        conditions.append("artifact_refresh_needed")
    elif artifact_continuity in {"missing", "detached"}:
        conditions.append("artifact_reacquisition_needed")
    if artifact_reacquisition_mode:
        conditions.append("artifact_reacquisition_available")
    if blocked_packet_count > 0 or block_reason:
        conditions.append("blocked_action_present")
    explicit_surfaces: list[str] = []
    if browser_session or account_state or cookie_state or api_key_state or quota_state:
        explicit_surfaces.append("browser")
    if filesystem_state:
        explicit_surfaces.append("filesystem")
    if sandbox_mode:
        explicit_surfaces.append("sandbox")
    if network_access or api_key_state or quota_state:
        explicit_surfaces.append("network")
    if active_artifact_kind in _ARTIFACT_BROWSER_KINDS:
        explicit_surfaces.append("browser")
    if active_artifact_kind in _ARTIFACT_FILESYSTEM_KINDS:
        explicit_surfaces.append("filesystem")
    world_surfaces = _merge_unique_lists(world_surfaces, explicit_surfaces, limit=12)

    missing_access = _merge_unique_lists(hints.get("missing_access"), carried_missing_access, limit=12)
    requestable_access = _merge_unique_lists(hints.get("requestable_access"), carried_requested_access, limit=12)

    if browser_session in {"missing", "expired", "required"}:
        conditions.append("browser_session_missing")
        missing_access = _merge_unique_lists(missing_access, ["browser_session"], limit=12)
        requestable_access = _merge_unique_lists(requestable_access, ["browser_session"], limit=12)
    if account_state in {"missing", "logged_out", "required"}:
        conditions.append("account_login_required")
        missing_access = _merge_unique_lists(missing_access, ["account_login"], limit=12)
        requestable_access = _merge_unique_lists(requestable_access, ["account_login"], limit=12)
    if cookie_state in {"missing", "expired", "required"}:
        conditions.append("cookie_access_missing")
        missing_access = _merge_unique_lists(missing_access, ["cookies"], limit=12)
        requestable_access = _merge_unique_lists(requestable_access, ["cookies"], limit=12)
    if session_recovery_mode == "refresh_session":
        requestable_access = _merge_unique_lists(requestable_access, ["session_refresh"], limit=12)
    if api_key_state in {"missing", "required", "unset", "invalid", "expired"}:
        conditions.append("api_key_missing")
        missing_access = _merge_unique_lists(missing_access, ["api_key"], limit=12)
        requestable_access = _merge_unique_lists(requestable_access, ["api_key"], limit=12)
    if quota_state in {"exhausted", "blocked"}:
        conditions.append("api_quota_exhausted")
        missing_access = _merge_unique_lists(missing_access, ["api_quota"], limit=12)
        requestable_access = _merge_unique_lists(requestable_access, ["api_quota"], limit=12)
    elif quota_state in {"missing", "required", "unavailable"}:
        conditions.append("api_quota_unavailable")
        missing_access = _merge_unique_lists(missing_access, ["api_quota"], limit=12)
        requestable_access = _merge_unique_lists(requestable_access, ["api_quota"], limit=12)
    elif quota_state in {"low"}:
        conditions.append("api_quota_low")
        requestable_access = _merge_unique_lists(requestable_access, ["api_quota"], limit=12)
    if filesystem_state == "read_only":
        conditions.append("workspace_read_only")
        missing_access = _merge_unique_lists(missing_access, ["workspace_write"], limit=12)
        requestable_access = _merge_unique_lists(requestable_access, ["workspace_write"], limit=12)
    elif filesystem_state in {"missing", "unavailable", "required"}:
        conditions.append("filesystem_unavailable")
        missing_access = _merge_unique_lists(missing_access, ["filesystem"], limit=12)
        requestable_access = _merge_unique_lists(requestable_access, ["filesystem"], limit=12)
    if sandbox_mode in {"restricted", "blocked"}:
        conditions.append("sandbox_restricted")
        missing_access = _merge_unique_lists(missing_access, ["sandbox"], limit=12)
        requestable_access = _merge_unique_lists(requestable_access, ["sandbox"], limit=12)
    if network_access in {"disabled", "blocked"}:
        conditions.append("network_unavailable")
        missing_access = _merge_unique_lists(missing_access, ["network"], limit=12)
        requestable_access = _merge_unique_lists(requestable_access, ["network"], limit=12)
    elif network_access == "restricted":
        conditions.append("network_restricted")
        requestable_access = _merge_unique_lists(requestable_access, ["network"], limit=12)
    if pending_approval_count > 0 or external_mutation_pending:
        requestable_access = _merge_unique_lists(requestable_access, ["human_approval"], limit=12)
    if carried_requested_help:
        requestable_access = _merge_unique_lists(requestable_access, ["human_approval"], limit=12)
    conditions = _merge_unique_lists(hints.get("constraints"), conditions, limit=12)

    if blocked_packet_count > 0 and not cooldown_active and block_reason:
        access_mode = "blocked"
    elif pending_approval_count > 0:
        access_mode = "approval_pending"
    elif cooldown_active:
        access_mode = "cooldown"
    elif active_tools or granted_toolsets:
        access_mode = "tool_enabled"
    elif missing_access:
        access_mode = "limited"
    else:
        access_mode = "native_only"

    action_channels = ["language"]
    if queue_depth > 0:
        action_channels.append("continuity_queue")
    if packets:
        action_channels.append("structured_action")
    if active_tools or granted_toolsets:
        action_channels.append("tooling")
    if pending_approval_count > 0:
        action_channels.append("approval_gate")
    if access_mode == "cooldown":
        action_channels.append("cooldown_gate")
    action_channels = list(dict.fromkeys(action_channels))

    event_kind = _clean_text(event.get("kind")).lower()
    if pending_approval_count > 0:
        active_surface = "approval_gate"
    elif access_mode == "cooldown":
        active_surface = "cooldown_gate"
    elif active_tools:
        active_surface = "tooling"
    elif event_kind in _OWN_RHYTHM_EVENT_KINDS:
        active_surface = "self_rhythm"
    else:
        active_surface = perception_channels[0]

    return normalize_digital_body_state(
        {
            "active_surface": active_surface,
            "perception_channels": perception_channels,
            "action_channels": action_channels,
            "world_surfaces": world_surfaces,
            "available_toolsets": granted_toolsets,
            "active_tools": active_tools,
            "access_state": {
                "mode": access_mode,
                "conditions": conditions,
                "block_reason": block_reason,
                "retry_after_s": retry_after_s,
                "cooldown_scope": cooldown_scope,
                "session_continuity": session_continuity,
                "session_expires_in_s": session_expires_in_s,
                "session_recovery_mode": session_recovery_mode,
                "pending_approval_count": pending_approval_count,
                "external_mutation_pending": external_mutation_pending,
                "granted_toolsets": granted_toolsets,
                "missing_access": missing_access,
                "requestable_access": requestable_access,
                "browser_session": browser_session,
                "account_state": account_state,
                "cookie_state": cookie_state,
                "api_key_state": api_key_state,
                "quota_state": quota_state,
                "filesystem_state": filesystem_state,
                "sandbox_mode": sandbox_mode,
                "network_access": network_access,
            },
            "resource_state": {
                "behavior_queue_depth": queue_depth,
                "action_packet_count": len(packets),
                "pending_approval_count": pending_approval_count,
                "queued_packet_count": queued_packet_count,
                "executing_packet_count": executing_packet_count,
                "completed_packet_count": completed_packet_count,
                "blocked_packet_count": blocked_packet_count,
                "external_tool_count": len(external_tools),
                "artifact_continuity": artifact_continuity,
                "active_artifact_kind": active_artifact_kind,
                "active_artifact_ref": active_artifact_ref,
                "active_artifact_label": active_artifact_label,
                "artifact_age_s": artifact_age_s,
                "artifact_reacquisition_mode": artifact_reacquisition_mode,
                "artifact_carrier": artifact_carrier,
                "artifact_source_ref_ids": artifact_source_ref_ids,
                "artifact_source_url": artifact_source_url,
                "artifact_source_query": artifact_source_query,
                "artifact_source_title": artifact_source_title,
                "artifact_source_tool_name": artifact_source_tool_name,
            },
            "body_constraints": conditions,
        }
    )


__all__ = [
    "derive_artifact_identity",
    "derive_artifact_continuity",
    "derive_session_lifecycle",
    "derive_digital_body_state",
    "embodied_context_has_signal",
    "digital_body_state_has_signal",
    "normalize_embodied_context",
    "normalize_digital_body_state",
]
