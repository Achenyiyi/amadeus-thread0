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


def merge_digital_body_hints(
    *,
    session_context: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _merged_hint_payload(session_context=session_context, current_event=current_event)


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
            isinstance(access_state.get("access_acquire_proposals"), list) and bool(access_state.get("access_acquire_proposals")),
            isinstance(access_state.get("selected_access_proposal"), dict) and bool(access_state.get("selected_access_proposal")),
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
    access_acquire_proposals = _merge_access_acquire_proposals(row.get("access_acquire_proposals"), limit=8)
    selected_access_proposal = normalize_access_acquire_proposal(row.get("selected_access_proposal"))
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
        "access_acquire_proposals": access_acquire_proposals,
        "selected_access_proposal": selected_access_proposal,
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
            normalized["access_acquire_proposals"],
            normalized["selected_access_proposal"],
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
    access_acquire_proposals = _merge_access_acquire_proposals(access_state.get("access_acquire_proposals"), limit=8)
    selected_access_proposal = normalize_access_acquire_proposal(access_state.get("selected_access_proposal"))
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
            "access_acquire_proposals": access_acquire_proposals,
            "selected_access_proposal": selected_access_proposal,
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
    conditions = _merge_unique_lists(hints.get("constraints"), conditions, limit=12)
    has_completed_selected_access = any(
        _clean_text(packet.get("status")).lower() == "completed"
        and bool(normalize_access_acquire_proposal(packet.get("selected_access_proposal")))
        for packet in packets
    )
    if selected_access_proposal and not has_completed_selected_access:
        conditions = _merge_unique_lists(conditions, ["access_acquire_planned"], limit=12)

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
    "normalize_digital_body_state",
    "select_access_acquire_proposal",
    "selected_access_proposal_resolved",
]
