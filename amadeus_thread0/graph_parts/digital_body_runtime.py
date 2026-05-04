from __future__ import annotations

from typing import Any

from .action_packets import compact_artifact_identity, normalize_action_packets
from .browser_runtime import (
    browser_runtime_state_has_signal,
    normalize_browser_runtime_state,
)
from .skill_runtime import normalize_procedural_continuity, normalize_skill_effects

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
_API_KEY_PRESENT_STATES = {"present", "active", "ready", "available", "ok"}
_QUOTA_PRESENT_STATES = {"present", "active", "ready", "available", "ok", "sufficient", "low"}
_FILESYSTEM_PRESENT_STATES = {"present", "active", "ready", "available", "ok", "writable"}
_NETWORK_PRESENT_STATES = {"present", "active", "ready", "available", "ok", "enabled"}
_SANDBOX_PRESENT_STATES = {"present", "active", "ready", "available", "ok", "enabled"}
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


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _clean_ratio(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return 0.0


def _clean_text_list(value: Any, *, limit: int = 8, item_limit: int = 320) -> list[str]:
    values = value if isinstance(value, list) else [value] if value not in (None, "") else []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = _clean_text(item, limit=item_limit)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
        if len(cleaned) >= max(1, int(limit)):
            break
    return cleaned


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
    preferred_source_ref_id: Any = None,
    preferred_anchor_reason: Any = None,
    artifact_source_url: Any = None,
    artifact_source_query: Any = None,
    artifact_source_title: Any = None,
    artifact_source_tool_name: Any = None,
) -> dict[str, Any]:
    normalized = compact_artifact_identity(
        {
            "carrier": artifact_carrier,
            "source_ref_ids": artifact_source_ref_ids,
            "preferred_source_ref_id": preferred_source_ref_id,
            "preferred_anchor_reason": preferred_anchor_reason,
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
            "preferred_source_ref_id": 0,
            "preferred_anchor_reason": "",
            "artifact_source_url": "",
            "artifact_source_query": "",
            "artifact_source_title": "",
            "artifact_source_tool_name": "",
        }
    return {
        "artifact_carrier": str(normalized.get("artifact_carrier") or "").strip(),
        "artifact_source_ref_ids": list(normalized.get("artifact_source_ref_ids") or [])[:8],
        "preferred_source_ref_id": _clean_nonnegative_int(normalized.get("preferred_source_ref_id")),
        "preferred_anchor_reason": _clean_text(normalized.get("preferred_anchor_reason"), limit=120).lower(),
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


def normalize_access_acquire_proposal(value: Any) -> dict[str, Any]:
    row = _dict_or_empty(value)
    if not row:
        return {}
    target = _clean_state_label(row.get("target"))
    mode = _clean_state_label(row.get("mode"))
    path_kind = _clean_state_label(row.get("path_kind"))
    if path_kind not in {"acquire_existing", "create_new"}:
        path_kind = "acquire_existing"
    summary = _clean_text(row.get("summary"), limit=220)
    operator_action = _clean_text(row.get("operator_action"), limit=220)
    grants = _merge_unique_lists(row.get("grants"), [target] if target else [], limit=8)
    requires_operator = bool(row.get("requires_operator", True))
    resolved_grants = [item for item in _merge_unique_lists(row.get("resolved_grants"), limit=8) if item in grants]
    pending_grants = [
        item
        for item in _merge_unique_lists(row.get("pending_grants"), limit=8)
        if item in grants and item not in resolved_grants
    ]
    try:
        completion_ratio = max(0.0, min(1.0, float(row.get("completion_ratio"))))
    except Exception:
        completion_ratio = float(len(resolved_grants)) / float(len(grants)) if grants else 0.0
    if not any((target, mode, summary, operator_action, grants, requires_operator)):
        return {}
    normalized = {
        "target": target,
        "mode": mode,
        "path_kind": path_kind,
        "summary": summary,
        "operator_action": operator_action,
        "grants": grants,
        "requires_operator": requires_operator,
    }
    if grants and (resolved_grants or pending_grants or "completion_ratio" in row):
        normalized.update(
            {
                "resolved_grants": resolved_grants,
                "pending_grants": pending_grants,
                "completion_ratio": round(completion_ratio, 3),
            }
        )
    return normalized


def access_proposal_identity(proposal: Any) -> tuple[str, str]:
    selected = normalize_access_acquire_proposal(proposal)
    return (
        str(selected.get("target") or "").strip(),
        str(selected.get("mode") or "").strip(),
    )


def select_access_acquire_proposal(
    *,
    proposals: Any = None,
    preferred: Any = None,
) -> dict[str, Any]:
    normalized_proposals = normalize_access_acquire_proposals(proposals)
    preferred_proposal = normalize_access_acquire_proposal(preferred)
    if preferred_proposal:
        preferred_key = access_proposal_identity(preferred_proposal)
        for item in normalized_proposals:
            if access_proposal_identity(item) == preferred_key:
                return item
        if not normalized_proposals:
            return preferred_proposal
    if not normalized_proposals:
        return {}

    def _priority(item: dict[str, Any]) -> tuple[int, int]:
        path_kind = str(item.get("path_kind") or "").strip().lower()
        return (
            1 if path_kind == "create_new" else 0,
            normalized_proposals.index(item),
        )

    return min(normalized_proposals, key=_priority)


def normalize_access_acquire_proposals(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in value:
        proposal = normalize_access_acquire_proposal(item)
        if not proposal:
            continue
        key = access_proposal_identity(proposal)
        if key in seen:
            continue
        seen.add(key)
        merged.append(proposal)
        if len(merged) >= 8:
            break
    return merged


def _merge_access_acquire_proposals(*values: Any, limit: int = 8) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for value in values:
        proposals = normalize_access_acquire_proposals(value if isinstance(value, list) else [value] if isinstance(value, dict) else [])
        for item in proposals:
            key = access_proposal_identity(item)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
            if len(merged) >= max(1, int(limit)):
                return merged
    return merged


def _proposal_grants(proposal: Any) -> list[str]:
    selected = normalize_access_acquire_proposal(proposal)
    if not selected:
        return []
    return _merge_unique_lists(selected.get("grants"), [selected.get("target")] if selected.get("target") else [], limit=8)


def access_grant_satisfied(*, grant: Any, hints: dict[str, Any] | None = None) -> bool:
    row = _dict_or_empty(hints)
    key = _clean_state_label(grant)
    if not key:
        return False

    browser_session = _clean_state_label(row.get("browser_session"))
    account_state = _clean_state_label(row.get("account_state"))
    cookie_state = _clean_state_label(row.get("cookie_state"))
    api_key_state = _clean_state_label(row.get("api_key_state"))
    quota_state = _clean_state_label(row.get("quota_state"))
    filesystem_state = _clean_state_label(row.get("filesystem_state"))
    sandbox_mode = _clean_state_label(row.get("sandbox_mode"))
    network_access = _clean_state_label(row.get("network_access"))
    session_lifecycle = derive_session_lifecycle(
        browser_session=browser_session,
        account_state=account_state,
        cookie_state=cookie_state,
        session_continuity=row.get("session_continuity"),
        session_expires_in_s=row.get("session_expires_in_s"),
        session_recovery_mode=row.get("session_recovery_mode"),
    )
    session_continuity = _clean_state_label(session_lifecycle.get("session_continuity"))

    if key == "browser_session":
        return browser_session in _SESSION_PRESENT_STATES
    if key == "account_login":
        return account_state in _ACCOUNT_PRESENT_STATES
    if key == "cookies":
        return cookie_state in _COOKIE_PRESENT_STATES
    if key == "api_key":
        return api_key_state in _API_KEY_PRESENT_STATES
    if key == "api_quota":
        return quota_state in _QUOTA_PRESENT_STATES
    if key == "workspace_write":
        return filesystem_state in _FILESYSTEM_PRESENT_STATES
    if key == "filesystem":
        return filesystem_state not in {"", "missing", "unavailable", "required"}
    if key == "sandbox":
        return sandbox_mode in _SANDBOX_PRESENT_STATES
    if key == "network":
        return network_access in _NETWORK_PRESENT_STATES
    if key == "session_refresh":
        return session_continuity in {"stable", "expiring"} or browser_session in _SESSION_PRESENT_STATES
    return False


def access_proposal_progress(
    *,
    hints: dict[str, Any] | None = None,
    proposal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = _dict_or_empty(hints)
    selected = normalize_access_acquire_proposal(proposal if isinstance(proposal, dict) else row.get("selected_access_proposal"))
    grants = _proposal_grants(selected)
    resolved_grants = [grant for grant in grants if access_grant_satisfied(grant=grant, hints=row)]
    pending_grants = [grant for grant in grants if grant not in resolved_grants]
    grant_count = len(grants)
    resolved_count = len(resolved_grants)
    return {
        "grants": grants,
        "resolved_grants": resolved_grants,
        "pending_grants": pending_grants,
        "grant_count": grant_count,
        "resolved_count": resolved_count,
        "completion_ratio": round(float(resolved_count) / float(grant_count), 3) if grant_count else 0.0,
        "resolved": grant_count > 0 and resolved_count == grant_count,
        "partial": resolved_count > 0 and resolved_count < grant_count,
    }


def enrich_access_acquire_proposal(
    *,
    hints: dict[str, Any] | None = None,
    proposal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected = normalize_access_acquire_proposal(proposal if isinstance(proposal, dict) else _dict_or_empty(hints).get("selected_access_proposal"))
    if not selected:
        return {}
    progress = access_proposal_progress(hints=hints, proposal=selected)
    if progress["grant_count"] <= 0:
        return selected
    return {
        **selected,
        "resolved_grants": progress["resolved_grants"],
        "pending_grants": progress["pending_grants"],
        "completion_ratio": progress["completion_ratio"],
    }


def selected_access_proposal_resolved(
    *,
    hints: dict[str, Any] | None = None,
    proposal: dict[str, Any] | None = None,
) -> bool:
    progress = access_proposal_progress(hints=hints, proposal=proposal)
    return bool(progress.get("resolved", False))


def derive_session_surface_state(
    *,
    session_state: Any = None,
    browser_session: Any = None,
    account_state: Any = None,
    cookie_state: Any = None,
    session_continuity: Any = None,
    session_expires_in_s: Any = None,
    session_recovery_mode: Any = None,
    retry_after_s: Any = None,
    cooldown_scope: Any = None,
) -> dict[str, Any]:
    existing = _dict_or_empty(session_state)
    browser = _clean_state_label(existing.get("browser_session") or browser_session)
    login_state = _clean_state_label(existing.get("account_login_state") or account_state)
    cookies = _clean_state_label(existing.get("cookie_state") or cookie_state)
    lifecycle = derive_session_lifecycle(
        browser_session=browser,
        account_state=login_state,
        cookie_state=cookies,
        session_continuity=existing.get("continuity") or session_continuity,
        session_expires_in_s=existing.get("expires_in_s") or session_expires_in_s,
        session_recovery_mode=existing.get("recovery_mode") or session_recovery_mode,
    )
    continuity = _clean_state_label(lifecycle.get("session_continuity"))
    expires_in_s = _clean_nonnegative_int(lifecycle.get("session_expires_in_s"))
    recovery_mode = _clean_state_label(lifecycle.get("session_recovery_mode"))
    retry = _clean_nonnegative_int(existing.get("retry_after_s") or retry_after_s)
    scope = _clean_state_label(existing.get("cooldown_scope") or cooldown_scope)
    return {
        "continuity": continuity,
        "expires_in_s": expires_in_s,
        "recovery_mode": recovery_mode,
        "retry_after_s": retry,
        "cooldown_scope": scope,
        "browser_session": browser,
        "needs_recovery": continuity in {"missing", "expired", "expiring"},
    }


def derive_account_surface_state(
    *,
    account_state_detail: Any = None,
    browser_session: Any = None,
    account_state: Any = None,
    cookie_state: Any = None,
    api_key_state: Any = None,
) -> dict[str, Any]:
    existing = _dict_or_empty(account_state_detail)
    browser = _clean_state_label(existing.get("browser_session") or browser_session)
    login_state = _clean_state_label(existing.get("login_state") or account_state)
    cookies = _clean_state_label(existing.get("cookie_state") or cookie_state)
    api_key = _clean_state_label(existing.get("api_key_state") or api_key_state)
    return {
        "browser_session": browser,
        "login_state": login_state,
        "cookie_state": cookies,
        "api_key_state": api_key,
        "account_available": login_state in _ACCOUNT_PRESENT_STATES,
        "cookie_available": cookies in _COOKIE_PRESENT_STATES,
        "api_key_available": api_key in _API_KEY_PRESENT_STATES,
    }


def derive_quota_surface_state(
    *,
    quota_state_detail: Any = None,
    quota_state: Any = None,
    retry_after_s: Any = None,
    cooldown_scope: Any = None,
) -> dict[str, Any]:
    existing = _dict_or_empty(quota_state_detail)
    provider_state = _clean_state_label(existing.get("provider_state") or quota_state)
    retry = _clean_nonnegative_int(existing.get("retry_after_s") or retry_after_s)
    scope = _clean_state_label(existing.get("cooldown_scope") or cooldown_scope)
    return {
        "provider_state": provider_state,
        "retry_after_s": retry,
        "cooldown_scope": scope,
        "available": provider_state in _QUOTA_PRESENT_STATES and retry <= 0,
        "cooldown_active": retry > 0,
    }


def derive_permission_surface_state(
    *,
    permission_state: Any = None,
    pending_approval_count: Any = None,
    external_mutation_pending: Any = None,
    missing_access: Any = None,
    requestable_access: Any = None,
    access_acquire_proposals: Any = None,
    selected_access_proposal: Any = None,
    progress_hints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    existing = _dict_or_empty(permission_state)
    missing = _merge_unique_lists(existing.get("missing_access"), missing_access, limit=12)
    requestable = _merge_unique_lists(existing.get("requestable_access"), requestable_access, limit=12)
    proposals = _merge_access_acquire_proposals(
        existing.get("access_acquire_proposals"),
        access_acquire_proposals,
        limit=8,
    )
    selected = normalize_access_acquire_proposal(existing.get("selected_access_proposal"))
    if not selected:
        selected = normalize_access_acquire_proposal(selected_access_proposal)
    if not selected and proposals:
        selected = select_access_acquire_proposal(proposals=proposals)
    enriched_selected = enrich_access_acquire_proposal(hints=progress_hints, proposal=selected) if selected else {}
    progress = access_proposal_progress(hints=progress_hints, proposal=enriched_selected or selected)
    approval_count = _clean_nonnegative_int(existing.get("pending_approval_count") or pending_approval_count, limit=999)
    mutation_pending = bool(existing.get("external_mutation_pending", external_mutation_pending))
    approval_state = (
        "approval_pending"
        if approval_count > 0
        else "partial_access"
        if bool(progress.get("partial"))
        else "access_resolved"
        if bool(progress.get("resolved"))
        else "open"
    )
    return {
        "pending_approval_count": approval_count,
        "external_mutation_pending": mutation_pending,
        "missing_access": missing,
        "requestable_access": requestable,
        "access_acquire_proposals": proposals,
        "selected_access_proposal": enriched_selected or selected,
        "resolved_grants": _merge_unique_lists(existing.get("resolved_grants"), progress.get("resolved_grants"), limit=8),
        "pending_grants": _merge_unique_lists(existing.get("pending_grants"), progress.get("pending_grants"), limit=8),
        "completion_ratio": round(
            _clean_ratio(existing.get("completion_ratio") if "completion_ratio" in existing else progress.get("completion_ratio")),
            3,
        ),
        "approval_state": approval_state,
    }


def derive_sandbox_surface_state(
    *,
    sandbox_state: Any = None,
    sandbox_mode: Any = None,
    workspace_root: Any = None,
) -> dict[str, Any]:
    existing = _dict_or_empty(sandbox_state)
    availability = _clean_state_label(existing.get("availability") or sandbox_mode)
    allowed_roots = _clean_text_list(existing.get("allowed_roots"), limit=6, item_limit=320)
    if not allowed_roots and _clean_text(workspace_root, limit=320):
        allowed_roots = [_clean_text(workspace_root, limit=320)]
    execution_policy = _clean_state_label(existing.get("execution_policy")) or "approval_required"
    last_status = _clean_state_label(existing.get("last_status") or existing.get("last_known_status"))
    if not last_status and availability in {"restricted", "blocked"}:
        last_status = "gated"
    runner_kind = _clean_state_label(existing.get("runner_kind"))
    isolation_level = _clean_state_label(existing.get("isolation_level"))
    image_ref = _clean_text(existing.get("image_ref"), limit=160)
    network_policy = _clean_state_label(existing.get("network_policy"))
    if not network_policy and runner_kind == "docker_isolated_runner":
        network_policy = "none"
    elif not network_policy and runner_kind == "local_restricted_runner":
        network_policy = "host"
    workspace_root_kind = _clean_state_label(existing.get("workspace_root_kind"))
    if workspace_root and workspace_root_kind not in {"runtime_owned", "attached_repo_root"}:
        workspace_root_kind = "runtime_owned"
    last_command_profile = _clean_state_label(existing.get("last_command_profile"))
    last_exit_code = _clean_nonnegative_int(existing.get("last_exit_code"), limit=999999)
    last_run_id = _clean_text(existing.get("last_run_id"), limit=128)
    return {
        "availability": availability,
        "allowed_roots": allowed_roots,
        "execution_policy": execution_policy,
        "last_status": last_status,
        "runner_kind": runner_kind,
        "isolation_level": isolation_level,
        "image_ref": image_ref,
        "network_policy": network_policy,
        "workspace_root_kind": workspace_root_kind,
        "last_command_profile": last_command_profile,
        "last_exit_code": last_exit_code,
        "last_run_id": last_run_id,
        "arbitrary_execution": False,
    }


def derive_browser_runtime_surface_state(
    *,
    browser_runtime_state: Any = None,
    browser_session: Any = None,
) -> dict[str, Any]:
    existing = _dict_or_empty(browser_runtime_state)
    normalized = normalize_browser_runtime_state(existing)
    availability = _clean_state_label(normalized.get("availability"))
    if not availability and _clean_state_label(browser_session) in _SESSION_PRESENT_STATES:
        availability = "available"
    context_status = _clean_state_label(normalized.get("context_status"))
    if not context_status and bool(normalized.get("manual_takeover_required", False)):
        context_status = "manual_takeover"
    return {
        "availability": availability,
        "profile_root": _clean_text(normalized.get("profile_root"), limit=320),
        "context_status": context_status,
        "active_page_id": _clean_text(normalized.get("active_page_id"), limit=64),
        "active_tab_count": _clean_nonnegative_int(normalized.get("active_tab_count"), limit=999),
        "downloads_dir": _clean_text(normalized.get("downloads_dir"), limit=320),
        "last_action_status": _clean_state_label(normalized.get("last_action_status"), limit=64),
        "last_run_id": _clean_text(normalized.get("last_run_id"), limit=128),
        "manual_takeover_required": bool(normalized.get("manual_takeover_required", False)),
        "runner_kind": _clean_state_label(normalized.get("runner_kind"), limit=80),
        "isolation_level": _clean_state_label(normalized.get("isolation_level"), limit=80),
    }


def _session_surface_state_has_signal(value: Any) -> bool:
    row = _dict_or_empty(value)
    if not row:
        return False
    return any(
        (
            _clean_state_label(row.get("continuity")),
            _clean_nonnegative_int(row.get("expires_in_s")) > 0,
            _clean_state_label(row.get("recovery_mode")),
            _clean_nonnegative_int(row.get("retry_after_s")) > 0,
            _clean_state_label(row.get("cooldown_scope")),
            _clean_state_label(row.get("browser_session")),
            bool(row.get("needs_recovery", False)),
        )
    )


def _account_surface_state_has_signal(value: Any) -> bool:
    row = _dict_or_empty(value)
    if not row:
        return False
    return any(
        (
            _clean_state_label(row.get("browser_session")),
            _clean_state_label(row.get("login_state")),
            _clean_state_label(row.get("cookie_state")),
            _clean_state_label(row.get("api_key_state")),
            bool(row.get("account_available", False)),
            bool(row.get("cookie_available", False)),
            bool(row.get("api_key_available", False)),
        )
    )


def _quota_surface_state_has_signal(value: Any) -> bool:
    row = _dict_or_empty(value)
    if not row:
        return False
    return any(
        (
            _clean_state_label(row.get("provider_state")),
            _clean_nonnegative_int(row.get("retry_after_s")) > 0,
            _clean_state_label(row.get("cooldown_scope")),
            bool(row.get("available", False)),
            bool(row.get("cooldown_active", False)),
        )
    )


def _permission_surface_state_has_signal(value: Any) -> bool:
    row = _dict_or_empty(value)
    if not row:
        return False
    return any(
        (
            _clean_nonnegative_int(row.get("pending_approval_count"), limit=999) > 0,
            bool(row.get("external_mutation_pending", False)),
            bool(_merge_unique_lists(row.get("missing_access"), limit=12)),
            bool(_merge_unique_lists(row.get("requestable_access"), limit=12)),
            bool(_merge_access_acquire_proposals(row.get("access_acquire_proposals"), limit=8)),
            bool(normalize_access_acquire_proposal(row.get("selected_access_proposal"))),
            bool(_merge_unique_lists(row.get("resolved_grants"), limit=8)),
            bool(_merge_unique_lists(row.get("pending_grants"), limit=8)),
            _clean_ratio(row.get("completion_ratio")) > 0.0,
            _clean_state_label(row.get("approval_state")) not in {"", "open"},
        )
    )


def _sandbox_surface_state_has_signal(value: Any) -> bool:
    row = _dict_or_empty(value)
    if not row:
        return False
    return any(
        (
            _clean_state_label(row.get("availability")),
            bool(_clean_text_list(row.get("allowed_roots"), limit=6, item_limit=320)),
            _clean_state_label(row.get("last_status") or row.get("last_known_status")),
            _clean_state_label(row.get("runner_kind")),
            _clean_state_label(row.get("isolation_level")),
            _clean_text(row.get("image_ref"), limit=160),
            _clean_state_label(row.get("network_policy")),
            _clean_state_label(row.get("workspace_root_kind")),
            _clean_state_label(row.get("last_command_profile")),
            _clean_text(row.get("last_run_id"), limit=128),
            _clean_nonnegative_int(row.get("last_exit_code"), limit=999999) > 0,
            _clean_state_label(row.get("execution_policy")) not in {"", "approval_required"},
            bool(row.get("arbitrary_execution", False)),
        )
    )


def _browser_runtime_surface_state_has_signal(value: Any) -> bool:
    return browser_runtime_state_has_signal(value)


def prune_resolved_access_hints(hints: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(hints or {})
    missing = [str(item).strip().lower() for item in _list_or_empty(data.get("missing_access")) if str(item or "").strip()]
    requestable = [str(item).strip().lower() for item in _list_or_empty(data.get("requestable_access")) if str(item or "").strip()]
    removal_keys = {
        item
        for item in [*missing, *requestable]
        if access_grant_satisfied(grant=item, hints=data)
    }
    if removal_keys:
        missing = [item for item in missing if item not in removal_keys]
        requestable = [item for item in requestable if item not in removal_keys]
    data["missing_access"] = missing
    data["requestable_access"] = requestable
    return data


def derive_access_acquire_proposals(*, hints: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    row = _dict_or_empty(hints)
    if not row:
        return []
    browser_session = _clean_state_label(row.get("browser_session"))
    account_state = _clean_state_label(row.get("account_state"))
    cookie_state = _clean_state_label(row.get("cookie_state"))
    api_key_state = _clean_state_label(row.get("api_key_state"))
    quota_state = _clean_state_label(row.get("quota_state"))
    filesystem_state = _clean_state_label(row.get("filesystem_state"))
    sandbox_mode = _clean_state_label(row.get("sandbox_mode"))
    network_access = _clean_state_label(row.get("network_access"))
    session_lifecycle = derive_session_lifecycle(
        browser_session=browser_session,
        account_state=account_state,
        cookie_state=cookie_state,
        session_continuity=row.get("session_continuity"),
        session_expires_in_s=row.get("session_expires_in_s"),
        session_recovery_mode=row.get("session_recovery_mode"),
    )
    session_continuity = _clean_state_label(session_lifecycle.get("session_continuity"))
    requestable_access = _merge_unique_lists(row.get("requestable_access"), limit=12)
    missing_access = _merge_unique_lists(row.get("missing_access"), limit=12)
    proposals: list[dict[str, Any]] = []

    def _add(
        target: str,
        mode: str,
        summary: str,
        operator_action: str,
        grants: list[str] | None = None,
        path_kind: str = "acquire_existing",
    ) -> None:
        proposal = normalize_access_acquire_proposal(
            {
                "target": target,
                "mode": mode,
                "path_kind": path_kind,
                "summary": summary,
                "operator_action": operator_action,
                "grants": list(grants or []),
                "requires_operator": True,
            }
        )
        if proposal:
            proposals.append(proposal)

    if account_state in {"missing", "logged_out", "required"}:
        _add(
            "account_login",
            "operator_login",
            "先把账号登录补回来，这条外部入口才接得上后面。",
            "登录目标账号，或把现成登录态交给我。",
            ["account_login", "browser_session"],
        )
        if network_access not in {"disabled", "blocked"}:
            _add(
                "account_login",
                "operator_register_account",
                "如果没有现成账号，也可以先注册一个新的可用入口，再把这条路径接起来。",
                "注册一个新的账号入口，或确认让我沿着新账号路径继续。",
                ["account_login", "browser_session"],
                path_kind="create_new",
            )
    if cookie_state in {"missing", "expired", "required"}:
        _add(
            "cookies",
            "operator_restore_cookies",
            "当前 cookies / session token 还没补回来，这条路径还续不上。",
            "补回可用 cookies 或 session token。",
            ["cookies", "browser_session"],
        )
    if browser_session in {"missing", "expired", "required"}:
        _add(
            "browser_session",
            "operator_restore_session",
            "浏览器会话本身还没接回去，我还进不到那条外部表面。",
            "补回可复用的浏览器会话或对应入口。",
            ["browser_session"],
        )
    if session_continuity in {"expiring", "expired"}:
        _add(
            "session_refresh",
            "operator_refresh_session",
            "这段会话连续性已经不稳了，最好先补一次可复用的刷新路径。",
            "提供新的会话刷新条件，或确认让我按刷新后的入口继续。",
            ["session_refresh", "browser_session"],
        )
    if api_key_state in {"missing", "required", "unset", "invalid", "expired"}:
        _add(
            "api_key",
            "operator_provide_api_key",
            "当前模型/API 入口还缺着，我没法直接继续这条链路。",
            "提供可用 API key，或切换到已有可用入口。",
            ["api_key"],
        )
        _add(
            "api_key",
            "operator_create_api_key",
            "如果没有现成 key，也可以新建一个可用入口再继续这条链路。",
            "新建一个可用 API key，或确认改接新的服务入口。",
            ["api_key"],
            path_kind="create_new",
        )
    if quota_state in {"exhausted", "blocked"}:
        _add(
            "api_quota",
            "operator_replenish_quota",
            "额度已经把这条路径卡住了，得先补额度或等额度恢复。",
            "补可用额度，或明确告诉我改走别的路径。",
            ["api_quota"],
        )
    elif quota_state in {"low", "missing", "required", "unavailable"}:
        _add(
            "api_quota",
            "operator_confirm_quota",
            "这条入口的额度状态还不稳，我需要先确认能不能继续用。",
            "确认当前额度可用，或提供新的服务入口。",
            ["api_quota"],
        )
    if filesystem_state == "read_only":
        _add(
            "workspace_write",
            "operator_grant_workspace_write",
            "当前工作区只能读不能写，后面的落盘动作接不上。",
            "给我可写工作区，或指定一个允许写入的位置。",
            ["workspace_write"],
        )
    elif filesystem_state in {"missing", "unavailable", "required"}:
        _add(
            "filesystem",
            "operator_attach_filesystem",
            "当前文件系统入口还不完整，我还拿不到稳定的工作表面。",
            "挂接可访问的文件系统入口，或把目标文件放到当前工作区里。",
            ["filesystem"],
        )
        _add(
            "filesystem",
            "operator_create_workspace",
            "如果当前没有现成工作区，也可以先新建一个可写工作区，再把这条路径接起来。",
            "新建一个可写工作区，或确认新的落点目录。",
            ["filesystem", "workspace_write"],
            path_kind="create_new",
        )
    if sandbox_mode in {"restricted", "blocked"}:
        _add(
            "sandbox",
            "operator_enable_sandbox",
            "执行环境限制还没放开，这条需要运行时动作的路径继续不了。",
            "授予合适的沙箱权限，或明确限制我不要走这条路径。",
            ["sandbox"],
        )
    if network_access in {"disabled", "blocked", "restricted"}:
        _add(
            "network",
            "operator_enable_network",
            "当前网络入口受限，外部检索/连接这条路径接不上。",
            "开放可用网络入口，或提供离线替代材料。",
            ["network"],
        )

    if requestable_access or missing_access:
        target_set = set(requestable_access) | set(missing_access)
        proposals = [
            item
            for item in proposals
            if str(item.get("target") or "").strip() in target_set
            or bool(set(item.get("grants") or []) & target_set)
        ] or proposals
    return _merge_access_acquire_proposals(proposals, limit=8)


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
    event = _dict_or_empty(current_event)
    perception = _dict_or_empty(event.get("perception"))
    return merge_digital_body_hints(
        _dict_or_empty(_dict_or_empty(session_context).get("digital_body_hints")),
        _dict_or_empty(perception.get("digital_body_hints")),
        _dict_or_empty(event.get("digital_body_hints")),
    )


def merge_digital_body_hints(
    *sources: dict[str, Any] | None,
    session_context: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if session_context is not None or current_event is not None:
        event = _dict_or_empty(current_event)
        perception = _dict_or_empty(event.get("perception"))
        sources = (
            _dict_or_empty(_dict_or_empty(session_context).get("digital_body_hints")),
            _dict_or_empty(perception.get("digital_body_hints")),
            _dict_or_empty(event.get("digital_body_hints")),
        )

    merged: dict[str, Any] = {}
    for source in sources:
        if not isinstance(source, dict) or not source:
            continue
        for key, value in source.items():
            if key in {"world_surfaces", "missing_access", "requestable_access", "constraints"}:
                merged[key] = _merge_unique_lists(merged.get(key), value, limit=16)
            elif isinstance(value, dict):
                prior = _dict_or_empty(merged.get(key))
                nested = dict(prior)
                for nested_key, nested_value in value.items():
                    if nested_value in (None, "", []):
                        continue
                    if nested_key not in nested or nested.get(nested_key) in (None, "", []):
                        nested[nested_key] = nested_value
                if nested:
                    merged[key] = nested
            elif value not in (None, "", []) and key not in merged:
                merged[key] = value
    return merged


def digital_body_state_has_signal(state: Any) -> bool:
    if not isinstance(state, dict) or not state:
        return False
    if _clean_text(state.get("active_surface")):
        return True
    for key in ("perception_channels", "action_channels", "world_surfaces", "available_toolsets", "active_tools", "body_constraints"):
        if isinstance(state.get(key), list) and bool(state.get(key)):
            return True
    access_state = _dict_or_empty(state.get("access_state"))
    session_state = _dict_or_empty(access_state.get("session_state"))
    account_state_detail = _dict_or_empty(access_state.get("account_state_detail"))
    quota_state_detail = _dict_or_empty(access_state.get("quota_state_detail"))
    permission_state = _dict_or_empty(access_state.get("permission_state"))
    sandbox_state = _dict_or_empty(access_state.get("sandbox_state"))
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
            isinstance(access_state.get("access_acquire_proposals"), list) and bool(access_state.get("access_acquire_proposals")),
            isinstance(access_state.get("selected_access_proposal"), dict) and bool(access_state.get("selected_access_proposal")),
            _session_surface_state_has_signal(session_state),
            _account_surface_state_has_signal(account_state_detail),
            _quota_surface_state_has_signal(quota_state_detail),
            _permission_surface_state_has_signal(permission_state),
            _sandbox_surface_state_has_signal(sandbox_state),
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
            _clean_text(resource_state.get("workspace_root")),
        )
    ):
        return True
    return False



def normalize_embodied_context(context: Any) -> dict[str, Any]:
    row = _dict_or_empty(context)
    requested_access = _merge_unique_lists(
        row.get("requested_access"),
        _dict_or_empty(row.get("permission_state")).get("requestable_access"),
        limit=12,
    )
    missing_access = _merge_unique_lists(
        row.get("missing_access"),
        _dict_or_empty(row.get("permission_state")).get("missing_access"),
        limit=12,
    )
    granted_toolsets = _merge_unique_lists(row.get("granted_toolsets"), limit=12)
    active_tools = _merge_unique_lists(row.get("active_tools"), limit=8)
    access_acquire_proposals = _merge_access_acquire_proposals(
        row.get("access_acquire_proposals"),
        _dict_or_empty(row.get("permission_state")).get("access_acquire_proposals"),
        limit=8,
    )
    selected_access_proposal = normalize_access_acquire_proposal(
        row.get("selected_access_proposal")
        or _dict_or_empty(row.get("permission_state")).get("selected_access_proposal")
    )
    account_state_detail = derive_account_surface_state(
        account_state_detail=row.get("account_state_detail"),
        browser_session=row.get("browser_session"),
        account_state=row.get("account_state"),
        cookie_state=row.get("cookie_state"),
        api_key_state=row.get("api_key_state"),
    )
    browser_session = _clean_state_label(
        row.get("browser_session") or account_state_detail.get("browser_session")
    )
    account_state = _clean_state_label(
        row.get("account_state") or account_state_detail.get("login_state")
    )
    cookie_state = _clean_state_label(
        row.get("cookie_state") or account_state_detail.get("cookie_state")
    )
    api_key_state = _clean_state_label(
        row.get("api_key_state") or account_state_detail.get("api_key_state")
    )
    quota_state_detail = derive_quota_surface_state(
        quota_state_detail=row.get("quota_state_detail"),
        quota_state=row.get("quota_state"),
        retry_after_s=row.get("retry_after_s"),
        cooldown_scope=row.get("cooldown_scope"),
    )
    quota_state = _clean_state_label(
        row.get("quota_state") or quota_state_detail.get("provider_state")
    )
    filesystem_state = _clean_state_label(row.get("filesystem_state"))
    workspace_root = _clean_text(row.get("workspace_root"), limit=320)
    sandbox_state = derive_sandbox_surface_state(
        sandbox_state=row.get("sandbox_state"),
        sandbox_mode=row.get("sandbox_mode"),
        workspace_root=workspace_root,
    )
    browser_runtime_state = derive_browser_runtime_surface_state(
        browser_runtime_state=row.get("browser_runtime_state"),
        browser_session=row.get("browser_session"),
    )
    sandbox_mode = _clean_state_label(
        row.get("sandbox_mode") or sandbox_state.get("availability")
    )
    if not browser_session and _browser_runtime_surface_state_has_signal(browser_runtime_state):
        browser_session = "present"
    network_access = _clean_state_label(row.get("network_access"))
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
    sandbox_run_id = _clean_text(row.get("sandbox_run_id"), limit=128)
    sandbox_command_profile = _clean_state_label(row.get("sandbox_command_profile"))
    sandbox_stdout_log_ref = _clean_text(row.get("sandbox_stdout_log_ref"), limit=320)
    sandbox_stderr_log_ref = _clean_text(row.get("sandbox_stderr_log_ref"), limit=320)
    sandbox_error_summary = _clean_text(row.get("sandbox_error_summary"), limit=220)
    sandbox_exit_code = _coerce_int(row.get("sandbox_exit_code"), 0)
    sandbox_duration_ms = max(0, _coerce_int(row.get("sandbox_duration_ms"), 0))
    sandbox_produced_artifacts = _clean_text_list(row.get("sandbox_produced_artifacts"), limit=8, item_limit=320)
    browser_run_id = _clean_text(row.get("browser_run_id"), limit=128)
    browser_profile_id = _clean_text(row.get("browser_profile_id"), limit=120)
    browser_page_id = _clean_text(row.get("browser_page_id"), limit=64)
    browser_tab_id = _clean_text(row.get("browser_tab_id"), limit=64)
    browser_url = _clean_text(row.get("browser_url"), limit=1200)
    browser_title = _clean_text(row.get("browser_title"), limit=220)
    browser_last_action_kind = _clean_state_label(row.get("browser_last_action_kind"), limit=64)
    browser_last_exit_status = _clean_state_label(row.get("browser_last_exit_status"), limit=64)
    requested_help = bool(row.get("requested_help", False))
    environmental_friction = bool(row.get("environmental_friction", False))
    procedural_growth = bool(row.get("procedural_growth", False))
    procedural_continuity = normalize_procedural_continuity(row.get("procedural_continuity"))
    retry_after_s = _clean_nonnegative_int(
        row.get("retry_after_s")
        or quota_state_detail.get("retry_after_s")
        or _dict_or_empty(row.get("session_state")).get("retry_after_s")
    )
    cooldown_scope = _clean_state_label(
        row.get("cooldown_scope")
        or quota_state_detail.get("cooldown_scope")
        or _dict_or_empty(row.get("session_state")).get("cooldown_scope")
    )
    session_state = derive_session_surface_state(
        session_state=row.get("session_state"),
        browser_session=browser_session,
        account_state=account_state,
        cookie_state=cookie_state,
        session_continuity=row.get("session_continuity"),
        session_expires_in_s=row.get("session_expires_in_s"),
        session_recovery_mode=row.get("session_recovery_mode"),
        retry_after_s=retry_after_s,
        cooldown_scope=cooldown_scope,
    )
    session_lifecycle = derive_session_lifecycle(
        browser_session=browser_session,
        account_state=account_state,
        cookie_state=cookie_state,
        session_continuity=session_state.get("continuity"),
        session_expires_in_s=session_state.get("expires_in_s"),
        session_recovery_mode=session_state.get("recovery_mode"),
    )
    session_continuity = str(session_lifecycle.get("session_continuity") or "").strip()
    session_expires_in_s = _clean_nonnegative_int(session_lifecycle.get("session_expires_in_s"))
    session_recovery_mode = str(session_lifecycle.get("session_recovery_mode") or "").strip()
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
        preferred_source_ref_id=row.get("preferred_source_ref_id"),
        preferred_anchor_reason=row.get("preferred_anchor_reason"),
        artifact_source_url=row.get("artifact_source_url"),
        artifact_source_query=row.get("artifact_source_query"),
        artifact_source_title=row.get("artifact_source_title"),
        artifact_source_tool_name=row.get("artifact_source_tool_name"),
    )
    permission_progress_hints = {
        "browser_session": browser_session,
        "account_state": account_state,
        "cookie_state": cookie_state,
        "api_key_state": api_key_state,
        "quota_state": quota_state,
        "filesystem_state": filesystem_state,
        "sandbox_mode": sandbox_mode,
        "network_access": network_access,
        "session_continuity": session_continuity,
        "session_expires_in_s": session_expires_in_s,
        "session_recovery_mode": session_recovery_mode,
        "selected_access_proposal": selected_access_proposal,
    }
    permission_state = derive_permission_surface_state(
        permission_state=row.get("permission_state"),
        pending_approval_count=row.get("pending_approval_count"),
        external_mutation_pending=row.get("external_mutation_pending"),
        missing_access=missing_access,
        requestable_access=requested_access,
        access_acquire_proposals=access_acquire_proposals,
        selected_access_proposal=selected_access_proposal,
        progress_hints=permission_progress_hints,
    )
    requested_access = _merge_unique_lists(permission_state.get("requestable_access"), limit=12)
    missing_access = _merge_unique_lists(permission_state.get("missing_access"), limit=12)
    access_acquire_proposals = _merge_access_acquire_proposals(permission_state.get("access_acquire_proposals"), limit=8)
    selected_access_proposal = normalize_access_acquire_proposal(permission_state.get("selected_access_proposal"))
    session_state = session_state if _session_surface_state_has_signal(session_state) else {}
    account_state_detail = account_state_detail if _account_surface_state_has_signal(account_state_detail) else {}
    quota_state_detail = quota_state_detail if _quota_surface_state_has_signal(quota_state_detail) else {}
    permission_state = (
        permission_state
        if _permission_surface_state_has_signal(permission_state) or isinstance(row.get("permission_state"), dict)
        else {}
    )
    sandbox_state = sandbox_state if _sandbox_surface_state_has_signal(sandbox_state) else {}
    browser_runtime_state = browser_runtime_state if _browser_runtime_surface_state_has_signal(browser_runtime_state) else {}
    skill_effects = normalize_skill_effects(row.get("skill_effects"))

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
        "retry_after_s": retry_after_s,
        "cooldown_scope": cooldown_scope,
        "browser_session": browser_session,
        "account_state": account_state,
        "cookie_state": cookie_state,
        "api_key_state": api_key_state,
        "quota_state": quota_state,
        "filesystem_state": filesystem_state,
        "sandbox_mode": sandbox_mode,
        "network_access": network_access,
        "session_continuity": session_continuity,
        "session_expires_in_s": session_expires_in_s,
        "session_recovery_mode": session_recovery_mode,
        "artifact_continuity": str(artifact.get("artifact_continuity") or "").strip(),
        "active_artifact_kind": str(artifact.get("active_artifact_kind") or "").strip(),
        "active_artifact_ref": str(artifact.get("active_artifact_ref") or "").strip(),
        "active_artifact_label": str(artifact.get("active_artifact_label") or "").strip(),
        "artifact_age_s": _clean_nonnegative_int(artifact.get("artifact_age_s")),
        "artifact_reacquisition_mode": str(artifact.get("artifact_reacquisition_mode") or "").strip(),
        "artifact_mutation_mode": _clean_state_label(row.get("artifact_mutation_mode")),
        "artifact_carrier": str(artifact_identity.get("artifact_carrier") or "").strip(),
        "artifact_source_ref_ids": list(artifact_identity.get("artifact_source_ref_ids") or [])[:8],
        "preferred_source_ref_id": _clean_nonnegative_int(artifact_identity.get("preferred_source_ref_id")),
        "preferred_anchor_reason": _clean_text(artifact_identity.get("preferred_anchor_reason"), limit=120).lower(),
        "artifact_source_url": str(artifact_identity.get("artifact_source_url") or "").strip(),
        "artifact_source_query": str(artifact_identity.get("artifact_source_query") or "").strip(),
        "artifact_source_title": str(artifact_identity.get("artifact_source_title") or "").strip(),
        "artifact_source_tool_name": str(artifact_identity.get("artifact_source_tool_name") or "").strip(),
        "workspace_root": workspace_root,
        "pending_approval_count": _clean_nonnegative_int(
            row.get("pending_approval_count") or permission_state.get("pending_approval_count"),
            limit=999,
        ),
        "blocked_packet_count": _clean_nonnegative_int(row.get("blocked_packet_count"), limit=999),
        "completed_packet_count": _clean_nonnegative_int(row.get("completed_packet_count"), limit=999),
        "external_tool_count": _clean_nonnegative_int(row.get("external_tool_count"), limit=999),
        "primary_proposal_id": _clean_text(row.get("primary_proposal_id"), limit=128),
        "primary_status": primary_status,
        "primary_origin": primary_origin,
        "primary_intent": primary_intent,
        "primary_tool_name": primary_tool_name,
        "sandbox_run_id": sandbox_run_id,
        "sandbox_command_profile": sandbox_command_profile,
        "sandbox_stdout_log_ref": sandbox_stdout_log_ref,
        "sandbox_stderr_log_ref": sandbox_stderr_log_ref,
        "sandbox_error_summary": sandbox_error_summary,
        "sandbox_exit_code": sandbox_exit_code,
        "sandbox_duration_ms": sandbox_duration_ms,
        "sandbox_produced_artifacts": sandbox_produced_artifacts,
        "sandbox_runner_kind": _clean_state_label(row.get("sandbox_runner_kind") or sandbox_state.get("runner_kind")),
        "sandbox_isolation_level": _clean_state_label(
            row.get("sandbox_isolation_level") or sandbox_state.get("isolation_level")
        ),
        "sandbox_image_ref": _clean_text(row.get("sandbox_image_ref") or sandbox_state.get("image_ref"), limit=160),
        "sandbox_network_policy": _clean_state_label(
            row.get("sandbox_network_policy") or sandbox_state.get("network_policy")
        ),
        "workspace_root_kind": _clean_state_label(
            row.get("workspace_root_kind") or sandbox_state.get("workspace_root_kind")
        ),
        "browser_run_id": browser_run_id,
        "browser_profile_id": browser_profile_id,
        "browser_page_id": browser_page_id,
        "browser_tab_id": browser_tab_id,
        "browser_url": browser_url,
        "browser_title": browser_title,
        "browser_last_action_kind": browser_last_action_kind,
        "browser_last_exit_status": browser_last_exit_status,
        "procedural_growth": procedural_growth,
        "procedural_continuity": procedural_continuity,
        "environmental_friction": environmental_friction,
        "requested_help": requested_help,
        "external_mutation_pending": bool(
            row.get("external_mutation_pending", permission_state.get("external_mutation_pending", False))
        ),
        "access_acquire_proposals": access_acquire_proposals,
        "selected_access_proposal": selected_access_proposal,
        "session_state": session_state,
        "account_state_detail": account_state_detail,
        "quota_state_detail": quota_state_detail,
        "permission_state": permission_state,
        "sandbox_state": sandbox_state,
        "browser_runtime_state": browser_runtime_state,
        "skill_effects": skill_effects,
    }
    if not any(
        (
            normalized["kind"],
            normalized["summary"],
            normalized["access_mode"],
            normalized["active_surface"],
            normalized["block_reason"],
            normalized["retry_after_s"] > 0,
            normalized["cooldown_scope"],
            normalized["browser_session"],
            normalized["account_state"],
            normalized["cookie_state"],
            normalized["api_key_state"],
            normalized["quota_state"],
            normalized["filesystem_state"],
            normalized["sandbox_mode"],
            normalized["network_access"],
            normalized["session_continuity"],
            normalized["session_expires_in_s"] > 0,
            normalized["session_recovery_mode"],
            normalized["artifact_continuity"],
            normalized["active_artifact_kind"],
            normalized["active_artifact_ref"],
            normalized["active_artifact_label"],
            normalized["artifact_age_s"] > 0,
            normalized["artifact_reacquisition_mode"],
            normalized["artifact_mutation_mode"],
            normalized["artifact_carrier"],
            bool(normalized["artifact_source_ref_ids"]),
            normalized["preferred_source_ref_id"] > 0,
            normalized["preferred_anchor_reason"],
            normalized["artifact_source_url"],
            normalized["artifact_source_query"],
            normalized["artifact_source_title"],
            normalized["artifact_source_tool_name"],
            normalized["workspace_root"],
            normalized["pending_approval_count"] > 0,
            normalized["blocked_packet_count"] > 0,
            normalized["completed_packet_count"] > 0,
            normalized["external_tool_count"] > 0,
            normalized["primary_proposal_id"],
            normalized["primary_status"],
            normalized["primary_origin"],
            normalized["primary_intent"],
            normalized["primary_tool_name"],
            normalized["sandbox_run_id"],
            normalized["sandbox_command_profile"],
            normalized["sandbox_stdout_log_ref"],
            normalized["sandbox_stderr_log_ref"],
            normalized["sandbox_error_summary"],
            normalized["sandbox_exit_code"] != 0,
            normalized["sandbox_duration_ms"] > 0,
            normalized["sandbox_produced_artifacts"],
            normalized["sandbox_runner_kind"],
            normalized["sandbox_isolation_level"],
            normalized["sandbox_image_ref"],
            normalized["sandbox_network_policy"],
            normalized["workspace_root_kind"],
            normalized["browser_run_id"],
            normalized["browser_profile_id"],
            normalized["browser_page_id"],
            normalized["browser_tab_id"],
            normalized["browser_url"],
            normalized["browser_title"],
            normalized["browser_last_action_kind"],
            normalized["browser_last_exit_status"],
            normalized["world_surfaces"],
            normalized["missing_access"],
            normalized["requested_access"],
            normalized["granted_toolsets"],
            normalized["active_tools"],
            normalized["procedural_growth"],
            normalized["procedural_continuity"],
            normalized["environmental_friction"],
            normalized["requested_help"],
            normalized["external_mutation_pending"],
            normalized["access_acquire_proposals"],
            normalized["selected_access_proposal"],
            normalized["session_state"],
            normalized["account_state_detail"],
            normalized["quota_state_detail"],
            normalized["permission_state"],
            normalized["sandbox_state"],
            normalized["browser_runtime_state"],
            normalized["skill_effects"],
        )
    ):
        return {}
    return normalized


def _embodied_field_has_signal(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, set, tuple)):
        return bool(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    return value is not None


def normalize_embodied_trace_context(item: Any) -> dict[str, Any]:
    row = _dict_or_empty(item)
    if not row:
        return {}

    merged: dict[str, Any] = {}
    sources = (
        row.get("content"),
        row.get("metadata"),
        row.get("behavior_action"),
        row.get("behavior_plan"),
        row.get("behavior_consequence"),
        row.get("interaction_carryover"),
        row.get("digital_body_consequence"),
        row,
    )
    for source in sources:
        source_row = _dict_or_empty(source)
        if not source_row:
            continue
        candidate = dict(source_row)
        digital_body_consequence = _dict_or_empty(source_row.get("digital_body_consequence"))
        embodied_context = _dict_or_empty(source_row.get("embodied_context"))
        if digital_body_consequence:
            candidate.update(digital_body_consequence)
        if embodied_context:
            candidate.update(embodied_context)
        normalized = normalize_embodied_context(candidate)
        if not normalized:
            continue
        for key, value in normalized.items():
            if _embodied_field_has_signal(merged.get(key)):
                continue
            if _embodied_field_has_signal(value):
                merged[key] = value
    return normalize_embodied_context(merged)


def embodied_context_has_signal(context: Any) -> bool:
    return bool(normalize_embodied_context(context))


def normalize_digital_body_state(state: Any) -> dict[str, Any]:
    row = _dict_or_empty(state)
    if not digital_body_state_has_signal(row):
        return {}

    access_state = _dict_or_empty(row.get("access_state"))
    resource_state = _dict_or_empty(row.get("resource_state"))
    workspace_root = _clean_text(resource_state.get("workspace_root"), limit=320)
    granted_toolsets = [
        _clean_text(item).lower()
        for item in _list_or_empty(access_state.get("granted_toolsets"))
        if _clean_text(item)
    ]
    granted_toolsets = list(dict.fromkeys(granted_toolsets))[:12]
    account_state_detail = derive_account_surface_state(
        account_state_detail=access_state.get("account_state_detail"),
        browser_session=access_state.get("browser_session"),
        account_state=access_state.get("account_state"),
        cookie_state=access_state.get("cookie_state"),
        api_key_state=access_state.get("api_key_state"),
    )
    browser_session = _clean_state_label(
        access_state.get("browser_session") or account_state_detail.get("browser_session")
    )
    account_state = _clean_state_label(
        access_state.get("account_state") or account_state_detail.get("login_state")
    )
    cookie_state = _clean_state_label(
        access_state.get("cookie_state") or account_state_detail.get("cookie_state")
    )
    api_key_state = _clean_state_label(
        access_state.get("api_key_state") or account_state_detail.get("api_key_state")
    )
    quota_state_detail = derive_quota_surface_state(
        quota_state_detail=access_state.get("quota_state_detail"),
        quota_state=access_state.get("quota_state"),
        retry_after_s=access_state.get("retry_after_s"),
        cooldown_scope=access_state.get("cooldown_scope"),
    )
    quota_state = _clean_state_label(
        access_state.get("quota_state") or quota_state_detail.get("provider_state")
    )
    retry_after_s = _clean_nonnegative_int(
        access_state.get("retry_after_s") or quota_state_detail.get("retry_after_s")
    )
    cooldown_scope = _clean_state_label(
        access_state.get("cooldown_scope") or quota_state_detail.get("cooldown_scope")
    )
    session_state = derive_session_surface_state(
        session_state=access_state.get("session_state"),
        browser_session=browser_session,
        account_state=account_state,
        cookie_state=cookie_state,
        session_continuity=access_state.get("session_continuity"),
        session_expires_in_s=access_state.get("session_expires_in_s"),
        session_recovery_mode=access_state.get("session_recovery_mode"),
        retry_after_s=retry_after_s,
        cooldown_scope=cooldown_scope,
    )
    missing_access = _merge_unique_lists(
        access_state.get("missing_access"),
        _dict_or_empty(access_state.get("permission_state")).get("missing_access"),
        limit=12,
    )
    requestable_access = _merge_unique_lists(
        access_state.get("requestable_access"),
        _dict_or_empty(access_state.get("permission_state")).get("requestable_access"),
        limit=12,
    )
    access_acquire_proposals = _merge_access_acquire_proposals(
        access_state.get("access_acquire_proposals"),
        _dict_or_empty(access_state.get("permission_state")).get("access_acquire_proposals"),
        limit=8,
    )
    selected_access_proposal = normalize_access_acquire_proposal(
        access_state.get("selected_access_proposal")
        or _dict_or_empty(access_state.get("permission_state")).get("selected_access_proposal")
    )
    session_lifecycle = derive_session_lifecycle(
        browser_session=browser_session,
        account_state=account_state,
        cookie_state=cookie_state,
        session_continuity=session_state.get("continuity"),
        session_expires_in_s=session_state.get("expires_in_s"),
        session_recovery_mode=session_state.get("recovery_mode"),
    )
    session_continuity = str(session_lifecycle.get("session_continuity") or "").strip()
    session_expires_in_s = _clean_nonnegative_int(session_lifecycle.get("session_expires_in_s"))
    session_recovery_mode = str(session_lifecycle.get("session_recovery_mode") or "").strip()
    sandbox_state = derive_sandbox_surface_state(
        sandbox_state=access_state.get("sandbox_state"),
        sandbox_mode=access_state.get("sandbox_mode"),
        workspace_root=workspace_root,
    )
    browser_runtime_state = derive_browser_runtime_surface_state(
        browser_runtime_state=access_state.get("browser_runtime_state"),
        browser_session=browser_session,
    )
    sandbox_mode = _clean_state_label(
        access_state.get("sandbox_mode") or sandbox_state.get("availability")
    )
    if not browser_session and _browser_runtime_surface_state_has_signal(browser_runtime_state):
        browser_session = "present"
    permission_progress_hints = {
        "browser_session": browser_session,
        "account_state": account_state,
        "cookie_state": cookie_state,
        "api_key_state": api_key_state,
        "quota_state": quota_state,
        "filesystem_state": access_state.get("filesystem_state"),
        "sandbox_mode": sandbox_mode,
        "network_access": access_state.get("network_access"),
        "session_continuity": session_continuity,
        "session_expires_in_s": session_expires_in_s,
        "session_recovery_mode": session_recovery_mode,
        "selected_access_proposal": selected_access_proposal,
    }
    permission_state = derive_permission_surface_state(
        permission_state=access_state.get("permission_state"),
        pending_approval_count=access_state.get("pending_approval_count"),
        external_mutation_pending=access_state.get("external_mutation_pending"),
        missing_access=missing_access,
        requestable_access=requestable_access,
        access_acquire_proposals=access_acquire_proposals,
        selected_access_proposal=selected_access_proposal,
        progress_hints=permission_progress_hints,
    )
    missing_access = _merge_unique_lists(permission_state.get("missing_access"), limit=12)
    requestable_access = _merge_unique_lists(permission_state.get("requestable_access"), limit=12)
    access_acquire_proposals = _merge_access_acquire_proposals(permission_state.get("access_acquire_proposals"), limit=8)
    selected_access_proposal = normalize_access_acquire_proposal(permission_state.get("selected_access_proposal"))
    session_state = session_state if _session_surface_state_has_signal(session_state) else {}
    account_state_detail = account_state_detail if _account_surface_state_has_signal(account_state_detail) else {}
    quota_state_detail = quota_state_detail if _quota_surface_state_has_signal(quota_state_detail) else {}
    permission_state = (
        permission_state
        if _permission_surface_state_has_signal(permission_state) or isinstance(access_state.get("permission_state"), dict)
        else {}
    )
    sandbox_state = sandbox_state if _sandbox_surface_state_has_signal(sandbox_state) else {}
    browser_runtime_state = browser_runtime_state if _browser_runtime_surface_state_has_signal(browser_runtime_state) else {}
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
        preferred_source_ref_id=resource_state.get("preferred_source_ref_id"),
        preferred_anchor_reason=resource_state.get("preferred_anchor_reason"),
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
            "retry_after_s": retry_after_s,
            "cooldown_scope": cooldown_scope,
            "session_continuity": session_continuity,
            "session_expires_in_s": session_expires_in_s,
            "session_recovery_mode": session_recovery_mode,
            "pending_approval_count": max(
                0,
                int(access_state.get("pending_approval_count") or permission_state.get("pending_approval_count") or 0),
            ),
            "external_mutation_pending": bool(
                access_state.get("external_mutation_pending", permission_state.get("external_mutation_pending", False))
            ),
            "granted_toolsets": granted_toolsets,
            "missing_access": missing_access,
            "requestable_access": requestable_access,
            "access_acquire_proposals": access_acquire_proposals,
            "selected_access_proposal": selected_access_proposal,
            "browser_session": browser_session,
            "account_state": account_state,
            "cookie_state": cookie_state,
            "api_key_state": api_key_state,
            "quota_state": quota_state,
            "filesystem_state": _clean_state_label(access_state.get("filesystem_state")),
            "sandbox_mode": sandbox_mode,
            "network_access": _clean_state_label(access_state.get("network_access")),
            "session_state": session_state,
            "account_state_detail": account_state_detail,
            "quota_state_detail": quota_state_detail,
            "permission_state": permission_state,
            "sandbox_state": sandbox_state,
            "browser_runtime_state": browser_runtime_state,
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
            "preferred_source_ref_id": _clean_nonnegative_int(artifact_identity.get("preferred_source_ref_id")),
            "preferred_anchor_reason": _clean_text(artifact_identity.get("preferred_anchor_reason"), limit=120).lower(),
            "artifact_source_url": str(artifact_identity.get("artifact_source_url") or "").strip(),
            "artifact_source_query": str(artifact_identity.get("artifact_source_query") or "").strip(),
            "artifact_source_title": str(artifact_identity.get("artifact_source_title") or "").strip(),
            "artifact_source_tool_name": str(artifact_identity.get("artifact_source_tool_name") or "").strip(),
            "workspace_root": workspace_root,
            "browser_profile_id": _clean_text(resource_state.get("browser_profile_id"), limit=120),
            "browser_tab_id": _clean_text(resource_state.get("browser_tab_id"), limit=64),
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
    carried_access_acquire_proposals = (
        _merge_access_acquire_proposals(carried_embodied.get("access_acquire_proposals"), limit=8)
        if carried_primary_status not in {"completed", "rejected", "blocked"}
        else []
    )
    carried_selected_access_proposal = (
        normalize_access_acquire_proposal(carried_embodied.get("selected_access_proposal"))
        if carried_primary_status not in {"completed", "rejected", "blocked"}
        else {}
    )
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
        preferred_source_ref_id=carried_embodied.get("preferred_source_ref_id"),
        preferred_anchor_reason=carried_embodied.get("preferred_anchor_reason"),
        artifact_source_url=carried_embodied.get("artifact_source_url"),
        artifact_source_query=carried_embodied.get("artifact_source_query"),
        artifact_source_title=carried_embodied.get("artifact_source_title"),
        artifact_source_tool_name=carried_embodied.get("artifact_source_tool_name"),
    )
    carried_browser_runtime_state = derive_browser_runtime_surface_state(
        browser_runtime_state=carried_embodied.get("browser_runtime_state"),
        browser_session=carried_embodied.get("browser_session"),
    )
    carried_browser_profile_id = _clean_text(carried_embodied.get("browser_profile_id"), limit=120)
    carried_browser_tab_id = _clean_text(carried_embodied.get("browser_tab_id"), limit=64)

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
    packet_access_acquire_proposals: list[dict[str, Any]] = []
    packet_selected_access_proposal: dict[str, Any] = {}
    for packet in packets:
        status = _clean_text(packet.get("status")).lower()
        risk = _clean_text(packet.get("risk")).lower()
        requires_approval = bool(packet.get("requires_approval", False))
        packet_access_acquire_proposals = _merge_access_acquire_proposals(
            packet_access_acquire_proposals,
            packet.get("access_acquire_proposals"),
            limit=8,
        )
        if not packet_selected_access_proposal:
            packet_selected_access_proposal = normalize_access_acquire_proposal(packet.get("selected_access_proposal"))
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

    hint_mode = _clean_state_label(hints.get("mode"))
    hint_pending_approval_count = _clean_nonnegative_int(hints.get("pending_approval_count"))
    hint_external_mutation_pending = bool(hints.get("external_mutation_pending", False))
    if hint_mode == "approval_pending":
        hint_pending_approval_count = max(hint_pending_approval_count, 1)
    pending_approval_count = max(pending_approval_count, hint_pending_approval_count)
    external_mutation_pending = external_mutation_pending or hint_external_mutation_pending

    hinted_account_state_detail = derive_account_surface_state(
        account_state_detail=hints.get("account_state_detail"),
        browser_session=hints.get("browser_session"),
        account_state=hints.get("account_state"),
        cookie_state=hints.get("cookie_state"),
        api_key_state=hints.get("api_key_state"),
    )
    browser_session = _clean_state_label(
        hints.get("browser_session") or hinted_account_state_detail.get("browser_session")
    )
    account_state = _clean_state_label(
        hints.get("account_state") or hinted_account_state_detail.get("login_state")
    )
    cookie_state = _clean_state_label(
        hints.get("cookie_state") or hinted_account_state_detail.get("cookie_state")
    )
    api_key_state = _clean_state_label(
        hints.get("api_key_state") or hinted_account_state_detail.get("api_key_state")
    )
    hinted_quota_state_detail = derive_quota_surface_state(
        quota_state_detail=hints.get("quota_state_detail"),
        quota_state=hints.get("quota_state"),
        retry_after_s=hints.get("retry_after_s"),
        cooldown_scope=hints.get("cooldown_scope"),
    )
    quota_state = _clean_state_label(
        hints.get("quota_state") or hinted_quota_state_detail.get("provider_state")
    )
    retry_after_s = _clean_nonnegative_int(
        hints.get("retry_after_s") or hinted_quota_state_detail.get("retry_after_s")
    )
    cooldown_scope = _clean_state_label(
        hints.get("cooldown_scope") or hinted_quota_state_detail.get("cooldown_scope")
    )
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
    hinted_sandbox_state = derive_sandbox_surface_state(
        sandbox_state=hints.get("sandbox_state"),
        sandbox_mode=hints.get("sandbox_mode"),
        workspace_root=hints.get("workspace_root") or carried_embodied.get("workspace_root"),
    )
    hinted_browser_runtime_state = derive_browser_runtime_surface_state(
        browser_runtime_state=hints.get("browser_runtime_state") or carried_browser_runtime_state,
        browser_session=browser_session,
    )
    sandbox_mode = _clean_state_label(
        hints.get("sandbox_mode") or hinted_sandbox_state.get("availability")
    )
    if not browser_session and _browser_runtime_surface_state_has_signal(hinted_browser_runtime_state):
        browser_session = "present"
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
        preferred_source_ref_id=hints.get("preferred_source_ref_id")
        or carried_artifact_identity.get("preferred_source_ref_id"),
        preferred_anchor_reason=hints.get("preferred_anchor_reason")
        or carried_artifact_identity.get("preferred_anchor_reason"),
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
    preferred_source_ref_id = _clean_nonnegative_int(artifact_identity.get("preferred_source_ref_id"))
    preferred_anchor_reason = _clean_text(artifact_identity.get("preferred_anchor_reason"), limit=120).lower()
    artifact_source_url = _clean_text(artifact_identity.get("artifact_source_url"), limit=320)
    artifact_source_query = _clean_text(artifact_identity.get("artifact_source_query"), limit=220)
    artifact_source_title = _clean_text(artifact_identity.get("artifact_source_title"), limit=160)
    artifact_source_tool_name = _clean_state_label(artifact_identity.get("artifact_source_tool_name"))
    browser_profile_id = _clean_text(
        hints.get("browser_profile_id") or carried_browser_profile_id,
        limit=120,
    )
    browser_tab_id = _clean_text(
        hints.get("browser_tab_id") or carried_browser_tab_id,
        limit=64,
    )
    workspace_root = _clean_text(
        hints.get("workspace_root") or carried_embodied.get("workspace_root"),
        limit=320,
    )
    cooldown_active = retry_after_s > 0
    conditions: list[str] = []
    if pending_approval_count > 0:
        conditions.append("human_approval_required")
    if external_mutation_pending:
        conditions.append("external_mutation_gated")
    block_reason = (
        _clean_text(autonomy_block_reason, limit=220)
        or _clean_text(hints.get("block_reason"), limit=220)
        or carried_block_reason
    )
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
    if bool(hinted_browser_runtime_state.get("manual_takeover_required", False)):
        conditions.append("manual_browser_takeover_required")
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
    if _browser_runtime_surface_state_has_signal(hinted_browser_runtime_state):
        explicit_surfaces.append("browser")
    if active_artifact_kind in _ARTIFACT_FILESYSTEM_KINDS:
        explicit_surfaces.append("filesystem")
    world_surfaces = _merge_unique_lists(world_surfaces, explicit_surfaces, limit=12)

    missing_access = _merge_unique_lists(hints.get("missing_access"), carried_missing_access, limit=12)
    requestable_access = _merge_unique_lists(hints.get("requestable_access"), carried_requested_access, limit=12)
    access_acquire_proposals = _merge_access_acquire_proposals(
        hints.get("access_acquire_proposals"),
        carried_access_acquire_proposals,
        packet_access_acquire_proposals,
        derive_access_acquire_proposals(
            hints={
                **hints,
                "missing_access": missing_access,
                "requestable_access": requestable_access,
            }
        ),
        limit=8,
    )
    selected_access_proposal = (
        normalize_access_acquire_proposal(hints.get("selected_access_proposal"))
        or packet_selected_access_proposal
        or carried_selected_access_proposal
    )
    proposal_progress_hints = {
        **hints,
        "browser_session": browser_session,
        "account_state": account_state,
        "cookie_state": cookie_state,
        "api_key_state": api_key_state,
        "quota_state": quota_state,
        "filesystem_state": filesystem_state,
        "sandbox_mode": sandbox_mode,
        "network_access": network_access,
        "session_continuity": session_continuity,
        "session_expires_in_s": session_expires_in_s,
        "session_recovery_mode": session_recovery_mode,
    }
    access_acquire_proposals = [
        enrich_access_acquire_proposal(hints=proposal_progress_hints, proposal=proposal) or proposal
        for proposal in access_acquire_proposals
    ]
    selected_access_proposal = (
        enrich_access_acquire_proposal(
            hints=proposal_progress_hints,
            proposal=select_access_acquire_proposal(
                proposals=access_acquire_proposals,
                preferred=selected_access_proposal,
            ),
        )
        or select_access_acquire_proposal(
            proposals=access_acquire_proposals,
            preferred=selected_access_proposal,
        )
    )

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
    if bool(hinted_browser_runtime_state.get("manual_takeover_required", False)):
        requestable_access = _merge_unique_lists(requestable_access, ["human_approval"], limit=12)
    conditions = _merge_unique_lists(hints.get("constraints"), conditions, limit=12)
    has_completed_selected_access = any(
        _clean_text(packet.get("status")).lower() == "completed"
        and bool(normalize_access_acquire_proposal(packet.get("selected_access_proposal")))
        for packet in packets
    )
    if selected_access_proposal and not has_completed_selected_access:
        conditions = _merge_unique_lists(conditions, ["access_acquire_planned"], limit=12)

    if (blocked_packet_count > 0 or hint_mode == "blocked") and not cooldown_active and block_reason:
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

    session_state = derive_session_surface_state(
        session_state=hints.get("session_state"),
        browser_session=browser_session,
        account_state=account_state,
        cookie_state=cookie_state,
        session_continuity=session_continuity,
        session_expires_in_s=session_expires_in_s,
        session_recovery_mode=session_recovery_mode,
        retry_after_s=retry_after_s,
        cooldown_scope=cooldown_scope,
    )
    account_state_detail = derive_account_surface_state(
        account_state_detail=hints.get("account_state_detail"),
        browser_session=browser_session,
        account_state=account_state,
        cookie_state=cookie_state,
        api_key_state=api_key_state,
    )
    quota_state_detail = derive_quota_surface_state(
        quota_state_detail=hints.get("quota_state_detail"),
        quota_state=quota_state,
        retry_after_s=retry_after_s,
        cooldown_scope=cooldown_scope,
    )
    permission_state = derive_permission_surface_state(
        permission_state=hints.get("permission_state"),
        pending_approval_count=pending_approval_count,
        external_mutation_pending=external_mutation_pending,
        missing_access=missing_access,
        requestable_access=requestable_access,
        access_acquire_proposals=access_acquire_proposals,
        selected_access_proposal=selected_access_proposal,
        progress_hints=proposal_progress_hints,
    )
    missing_access = _merge_unique_lists(permission_state.get("missing_access"), limit=12)
    requestable_access = _merge_unique_lists(permission_state.get("requestable_access"), limit=12)
    access_acquire_proposals = _merge_access_acquire_proposals(permission_state.get("access_acquire_proposals"), limit=8)
    selected_access_proposal = normalize_access_acquire_proposal(permission_state.get("selected_access_proposal"))
    sandbox_state = derive_sandbox_surface_state(
        sandbox_state=hints.get("sandbox_state"),
        sandbox_mode=sandbox_mode,
        workspace_root=workspace_root,
    )
    browser_runtime_state = derive_browser_runtime_surface_state(
        browser_runtime_state=hints.get("browser_runtime_state") or carried_browser_runtime_state,
        browser_session=browser_session,
    )

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
                "access_acquire_proposals": access_acquire_proposals,
                "selected_access_proposal": selected_access_proposal,
                "browser_session": browser_session,
                "account_state": account_state,
                "cookie_state": cookie_state,
                "api_key_state": api_key_state,
                "quota_state": quota_state,
                "filesystem_state": filesystem_state,
                "sandbox_mode": sandbox_mode,
                "network_access": network_access,
                "session_state": session_state,
                "account_state_detail": account_state_detail,
                "quota_state_detail": quota_state_detail,
                "permission_state": permission_state,
                "sandbox_state": sandbox_state,
                "browser_runtime_state": browser_runtime_state,
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
                "preferred_source_ref_id": preferred_source_ref_id,
                "preferred_anchor_reason": preferred_anchor_reason,
                "artifact_source_url": artifact_source_url,
                "artifact_source_query": artifact_source_query,
                "artifact_source_title": artifact_source_title,
                "artifact_source_tool_name": artifact_source_tool_name,
                "workspace_root": workspace_root,
                "browser_profile_id": browser_profile_id,
                "browser_tab_id": browser_tab_id,
            },
            "body_constraints": conditions,
        }
    )


__all__ = [
    "access_proposal_identity",
    "access_proposal_progress",
    "access_grant_satisfied",
    "derive_access_acquire_proposals",
    "derive_artifact_identity",
    "derive_artifact_continuity",
    "derive_session_lifecycle",
    "derive_digital_body_state",
    "embodied_context_has_signal",
    "digital_body_state_has_signal",
    "enrich_access_acquire_proposal",
    "merge_digital_body_hints",
    "prune_resolved_access_hints",
    "normalize_access_acquire_proposal",
    "normalize_access_acquire_proposals",
    "normalize_embodied_context",
    "normalize_embodied_trace_context",
    "normalize_digital_body_state",
    "select_access_acquire_proposal",
    "selected_access_proposal_resolved",
]
