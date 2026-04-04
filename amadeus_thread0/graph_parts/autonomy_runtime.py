from __future__ import annotations

from typing import Any

from .action_packets import (
    build_behavior_action_packet,
    derive_action_packet_origin,
    make_proposal_id,
    normalize_action_packet,
    normalize_action_packets,
)
from .digital_body_runtime import (
    access_grant_satisfied,
    access_proposal_identity,
    access_proposal_progress,
    derive_access_acquire_proposals,
    derive_session_lifecycle,
    enrich_access_acquire_proposal,
    merge_digital_body_hints,
    normalize_access_acquire_proposal,
    normalize_access_acquire_proposals,
    normalize_embodied_context,
    prune_resolved_access_hints,
    select_access_acquire_proposal,
    selected_access_proposal_resolved,
)

_OWN_RHYTHM_EVENT_KINDS = {
    "self_activity_state",
    "time_idle",
    "scheduled_checkin_due",
    "scheduled_life_due",
}

_ARTIFACT_KIND_LABELS = {
    "file": "前面的文件",
    "document": "前面的文档",
    "buffer": "前面的缓冲区",
    "notebook": "前面的笔记本",
    "workspace": "前面的工作区",
    "page": "前面的页面",
    "tab": "前面的标签页",
    "site": "前面的站点",
    "browser_page": "前面的页面",
    "search_result": "前面的检索结果",
}

_ACCESS_REFRESH_TARGETS = {
    "api_key": "模型入口",
    "api_quota": "配额状态",
    "workspace_write": "工作区写入权限",
    "filesystem": "文件系统入口",
    "sandbox": "执行环境",
    "network": "网络入口",
    "browser_session": "浏览器会话",
    "account_login": "账号登录状态",
    "cookies": "cookies 状态",
    "session_refresh": "会话连续性",
}

_ACCESS_HELP_TARGETS = {
    "browser_session",
    "account_login",
    "cookies",
    "api_key",
    "api_quota",
}

_ARTIFACT_REACQUISITION_INTENTS = {
    "artifact:reopen_file",
    "artifact:restore_file",
    "artifact:reattach_workspace",
    "artifact:reattach_artifact",
    "artifact:reopen_page",
    "artifact:restore_page",
    "artifact:rerun_search",
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _clean_list(value: Any, *, limit: int = 3) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for item in _list_or_empty(value):
        text = _clean_text(item).lower()
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
        if len(items) >= max(1, int(limit)):
            break
    return items


def _clean_text(value: Any, *, limit: int = 220) -> str:
    return str(value or "").strip()[:limit]


def _merge_labels(*values: Any, limit: int = 8) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, list):
            items = value
        else:
            items = [value]
        for item in items:
            text = _clean_text(item).lower()
            if not text or text in seen:
                continue
            seen.add(text)
            merged.append(text)
            if len(merged) >= max(1, int(limit)):
                return merged
    return merged


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        cast = float(value)
    except Exception:
        cast = float(default)
    return max(0.0, min(1.0, cast))


def _normalized_intent_origin(value: Any) -> str:
    text = _clean_text(value).lower()
    return text if text in {"motive_goal", "own_rhythm", "counterpart_request", "capability_upgrade"} else ""


def _artifact_surface_label(embodied: dict[str, Any]) -> str:
    label = _clean_text(embodied.get("active_artifact_label"))
    if label:
        return label
    ref = _clean_text(embodied.get("active_artifact_ref"))
    if ref:
        return ref
    kind = _clean_text(embodied.get("active_artifact_kind")).lower()
    return _ARTIFACT_KIND_LABELS.get(kind, "前面的工作面")


def _artifact_reacquisition_mode(embodied: dict[str, Any]) -> str:
    mode = _clean_text(embodied.get("artifact_reacquisition_mode")).lower()
    if mode:
        return mode
    kind = _clean_text(embodied.get("active_artifact_kind")).lower()
    if kind == "search_result":
        return "rerun_search"
    if kind in {"workspace"}:
        return "reattach_workspace"
    if kind in {"page", "tab", "site", "browser_page"}:
        return "reopen_page"
    if kind in {"file", "document", "buffer", "notebook"}:
        return "reopen_file"
    return "reattach_artifact"


def _artifact_reacquisition_reason(embodied: dict[str, Any]) -> str:
    continuity = _clean_text(embodied.get("artifact_continuity")).lower()
    label = _artifact_surface_label(embodied)
    mode = _artifact_reacquisition_mode(embodied)
    if continuity == "stale":
        return f"先确认{label}还是当前这一版，再继续往下做。"
    if mode == "rerun_search":
        return "先把前面的检索结果重新拿回来，再继续往下做。"
    if mode == "reattach_workspace":
        return f"先把{label}重新接回当前上下文，再继续往下做。"
    if mode in {"reopen_page", "restore_page", "reopen_file", "restore_file"}:
        return f"先把{label}重新打开，再继续往下做。"
    return f"先把{label}重新接回当前上下文，再继续往下做。"


def _artifact_reacquisition_packet(embodied: dict[str, Any]) -> dict[str, Any]:
    continuity = _clean_text(embodied.get("artifact_continuity")).lower()
    if continuity not in {"missing", "detached"}:
        return {}
    origin = _normalized_intent_origin(embodied.get("primary_origin")) or "motive_goal"
    mode = _artifact_reacquisition_mode(embodied)
    label = _artifact_surface_label(embodied)
    artifact_ref = _clean_text(embodied.get("active_artifact_ref"))
    artifact_kind = _clean_text(embodied.get("active_artifact_kind")).lower()
    workspace_root = _clean_text(embodied.get("workspace_root"), limit=320)
    target = artifact_ref or label
    reason = _artifact_reacquisition_reason(embodied)
    tool_args = {
        "mode": mode,
        "artifact_kind": artifact_kind,
        "artifact_ref": artifact_ref or target,
        "artifact_label": label,
    }
    if workspace_root and artifact_kind in {"file", "document", "buffer", "notebook", "workspace"}:
        tool_args["workspace_root"] = workspace_root
    return normalize_action_packet(
        {
            "proposal_id": make_proposal_id("artifact", continuity, mode, target, origin),
            "origin": origin,
            "intent": f"artifact:{mode}",
            "status": "proposed",
            "risk": "read",
            "requires_approval": False,
            "tool_name": "reacquire_artifact",
            "tool_args": tool_args,
            "capability_steps": [
                {
                    "kind": "artifact",
                    "name": mode,
                    "target": target,
                    "status": "pending",
                    "requires_approval": False,
                    "note": reason,
                }
            ],
            "expected_effect": reason,
            "result_summary": "",
            "writeback_ready": False,
        }
    )


def _source_ref_inspection_reason(embodied: dict[str, Any]) -> str:
    label = (
        _clean_text(embodied.get("active_artifact_label"))
        or _clean_text(embodied.get("artifact_source_title"))
        or _clean_text(embodied.get("active_artifact_ref"))
        or "前面的外部材料"
    )
    return f"先把{label}重新看一遍，确认当前判断还是落在这份材料上。"


def _source_ref_comparison_reason(embodied: dict[str, Any]) -> str:
    label = (
        _clean_text(embodied.get("active_artifact_label"))
        or _clean_text(embodied.get("artifact_source_title"))
        or _clean_text(embodied.get("active_artifact_ref"))
        or "前面的外部材料"
    )
    return f"先把{label}和前一条相关材料对一遍，确认现在该沿哪条线索继续判断。"


def _normalized_source_ref_ids(embodied: dict[str, Any]) -> list[int]:
    return [
        int(item)
        for item in _list_or_empty(embodied.get("artifact_source_ref_ids"))
        if str(item or "").strip().isdigit()
    ][:8]


def _preferred_source_ref_id(embodied: dict[str, Any]) -> int:
    preferred = _clean_text(embodied.get("preferred_source_ref_id"))
    if preferred.isdigit():
        preferred_id = int(preferred)
        if preferred_id > 0:
            return preferred_id
    return 0


def _has_stable_preferred_source_anchor(embodied: dict[str, Any]) -> bool:
    source_ref_ids = _normalized_source_ref_ids(embodied)
    preferred_source_ref_id = _preferred_source_ref_id(embodied)
    if preferred_source_ref_id <= 0 or preferred_source_ref_id not in source_ref_ids:
        return False
    return bool(_clean_text(embodied.get("preferred_anchor_reason")))


def _source_ref_inspection_packet(embodied: dict[str, Any]) -> dict[str, Any]:
    continuity = _clean_text(embodied.get("artifact_continuity")).lower()
    carrier = _clean_text(embodied.get("artifact_carrier")).lower()
    source_ref_ids = _normalized_source_ref_ids(embodied)
    if continuity != "stale":
        return {}
    if carrier != "source_ref" and not source_ref_ids:
        return {}

    origin = _normalized_intent_origin(embodied.get("primary_origin")) or "motive_goal"
    preferred_source_ref_id = _preferred_source_ref_id(embodied)
    source_ref_id = preferred_source_ref_id if preferred_source_ref_id in source_ref_ids else int(source_ref_ids[0]) if source_ref_ids else 0
    artifact_ref = (
        _clean_text(embodied.get("active_artifact_ref"))
        or _clean_text(embodied.get("artifact_source_url"))
        or _clean_text(embodied.get("artifact_source_query"))
    )
    label = (
        _clean_text(embodied.get("active_artifact_label"))
        or _clean_text(embodied.get("artifact_source_title"))
        or artifact_ref
        or (f"source_ref:{source_ref_id}" if source_ref_id > 0 else "saved-source")
    )
    target = artifact_ref or (f"source_ref:{source_ref_id}" if source_ref_id > 0 else label)
    reason = _source_ref_inspection_reason(embodied)
    tool_args: dict[str, Any] = {
        "artifact_ref": artifact_ref,
        "artifact_label": label,
    }
    if source_ref_id > 0:
        tool_args["source_ref_id"] = source_ref_id

    return normalize_action_packet(
        {
            "proposal_id": make_proposal_id("artifact", "stale", "inspect_source_ref", target, origin),
            "origin": origin,
            "intent": "artifact:inspect_source_ref",
            "status": "proposed",
            "risk": "read",
            "requires_approval": False,
            "tool_name": "inspect_source_ref",
            "tool_args": tool_args,
            "capability_steps": [
                {
                    "kind": "artifact",
                    "name": "inspect_source_ref",
                    "target": target,
                    "status": "pending",
                    "requires_approval": False,
                    "note": reason,
                }
            ],
            "expected_effect": reason,
            "result_summary": "",
            "writeback_ready": False,
        }
    )


def _source_ref_comparison_packet(embodied: dict[str, Any]) -> dict[str, Any]:
    continuity = _clean_text(embodied.get("artifact_continuity")).lower()
    carrier = _clean_text(embodied.get("artifact_carrier")).lower()
    source_ref_ids = _normalized_source_ref_ids(embodied)
    if continuity != "stale":
        return {}
    if carrier != "source_ref" or len(source_ref_ids) < 2:
        return {}
    if _has_stable_preferred_source_anchor(embodied):
        return {}

    origin = _normalized_intent_origin(embodied.get("primary_origin")) or "motive_goal"
    source_ref_id = int(source_ref_ids[0])
    compare_source_ref_id = next((item for item in source_ref_ids[1:] if item != source_ref_id), 0)
    if source_ref_id <= 0 or compare_source_ref_id <= 0:
        return {}

    artifact_ref = (
        _clean_text(embodied.get("active_artifact_ref"))
        or _clean_text(embodied.get("artifact_source_url"))
        or _clean_text(embodied.get("artifact_source_query"))
    )
    label = (
        _clean_text(embodied.get("active_artifact_label"))
        or _clean_text(embodied.get("artifact_source_title"))
        or artifact_ref
        or f"source_ref:{source_ref_id}"
    )
    candidate_source_ref_ids = source_ref_ids[:4]
    target = (
        f"source_ref:{source_ref_id}<->source_ref:{compare_source_ref_id}"
        if len(candidate_source_ref_ids) <= 2
        else f"source_ref:{source_ref_id}<->candidate_set:{','.join(str(item) for item in candidate_source_ref_ids[1:])}"
    )
    reason = _source_ref_comparison_reason(embodied)
    tool_args = {
        "source_ref_id": source_ref_id,
        "artifact_ref": artifact_ref,
        "artifact_label": label,
        "source_ref_ids": candidate_source_ref_ids,
    }
    if len(candidate_source_ref_ids) <= 2:
        tool_args["compare_source_ref_id"] = compare_source_ref_id
    return normalize_action_packet(
        {
            "proposal_id": make_proposal_id("artifact", "stale", "compare_source_refs", target, origin),
            "origin": origin,
            "intent": "artifact:compare_source_refs",
            "status": "proposed",
            "risk": "read",
            "requires_approval": False,
            "tool_name": "compare_source_refs",
            "tool_args": tool_args,
            "capability_steps": [
                {
                    "kind": "artifact",
                    "name": "compare_source_refs",
                    "target": target,
                    "status": "pending",
                    "requires_approval": False,
                    "note": reason,
                }
            ],
            "expected_effect": reason,
            "result_summary": "",
            "writeback_ready": False,
        }
    )


def _access_refresh_reason(hints: dict[str, Any]) -> str:
    browser_session = _clean_text(hints.get("browser_session")).lower()
    account_state = _clean_text(hints.get("account_state")).lower()
    cookie_state = _clean_text(hints.get("cookie_state")).lower()
    session_lifecycle = derive_session_lifecycle(
        browser_session=browser_session,
        account_state=account_state,
        cookie_state=cookie_state,
        session_continuity=hints.get("session_continuity"),
        session_expires_in_s=hints.get("session_expires_in_s"),
        session_recovery_mode=hints.get("session_recovery_mode"),
    )
    session_continuity = _clean_text(session_lifecycle.get("session_continuity")).lower()
    session_expires_in_s = int(session_lifecycle.get("session_expires_in_s") or 0)
    session_recovery_mode = _clean_text(session_lifecycle.get("session_recovery_mode")).lower()
    missing_access = _clean_list(hints.get("missing_access"), limit=4)
    requestable_access = _clean_list(hints.get("requestable_access"), limit=4)
    access_focus = next(
        (
            _ACCESS_REFRESH_TARGETS.get(item, item)
            for item in [*missing_access, *requestable_access]
            if _ACCESS_REFRESH_TARGETS.get(item, item)
        ),
        "",
    )
    if session_continuity == "expiring":
        if session_expires_in_s > 0:
            return f"先把当前会话状态重新检查一遍，确认离过期还剩 {session_expires_in_s}s，以及要不要刷新。"
        return "先把当前会话状态重新检查一遍，确认这段连续性还稳不稳。"
    if session_continuity in {"expired", "missing"}:
        recovery_hint = {
            "refresh_session": "刷新会话",
            "restore_cookies": "恢复 cookies",
            "relogin": "重新登录",
        }.get(session_recovery_mode, "补回当前入口")
        return f"先把当前入口状态重新检查一遍，确认是不是还要{recovery_hint}。"
    if _clean_text(hints.get("api_key_state")).lower() in {"missing", "required", "unset", "invalid", "expired"}:
        return "先重新检查当前模型/API 入口状态，确认 key 是否已经补上。"
    if _clean_text(hints.get("quota_state")).lower() in {"low", "exhausted", "blocked", "missing", "required", "unavailable"}:
        return "先重新检查当前配额和冷却状态，再决定下一步怎么走。"
    if _clean_text(hints.get("filesystem_state")).lower() in {"read_only", "missing", "unavailable", "required"}:
        return "先重新检查当前工作区和写入权限状态，再决定后面的动作。"
    if _clean_text(hints.get("network_access")).lower() in {"restricted", "disabled", "blocked"}:
        return "先重新检查当前网络入口状态，再决定接下来是继续还是换路。"
    if _clean_text(hints.get("sandbox_mode")).lower() in {"restricted", "blocked"}:
        return "先重新检查当前执行环境的限制状态，再决定后面的动作。"
    if access_focus:
        return f"先把{access_focus}重新检查一遍，再决定后面的动作。"
    return "先把当前数字环境入口状态重新检查一遍，再决定后面的动作。"


def _access_refresh_packet(hints: dict[str, Any]) -> dict[str, Any]:
    row = _dict_or_empty(hints)
    if not row:
        return {}
    browser_session = _clean_text(row.get("browser_session")).lower()
    account_state = _clean_text(row.get("account_state")).lower()
    cookie_state = _clean_text(row.get("cookie_state")).lower()
    api_key_state = _clean_text(row.get("api_key_state")).lower()
    quota_state = _clean_text(row.get("quota_state")).lower()
    filesystem_state = _clean_text(row.get("filesystem_state")).lower()
    sandbox_mode = _clean_text(row.get("sandbox_mode")).lower()
    network_access = _clean_text(row.get("network_access")).lower()
    retry_after_s = int(row.get("retry_after_s") or 0)
    session_lifecycle = derive_session_lifecycle(
        browser_session=browser_session,
        account_state=account_state,
        cookie_state=cookie_state,
        session_continuity=row.get("session_continuity"),
        session_expires_in_s=row.get("session_expires_in_s"),
        session_recovery_mode=row.get("session_recovery_mode"),
    )
    session_continuity = _clean_text(session_lifecycle.get("session_continuity")).lower()
    session_recovery_mode = _clean_text(session_lifecycle.get("session_recovery_mode")).lower()
    missing_access = _clean_list(row.get("missing_access"), limit=6)
    requestable_access = _clean_list(row.get("requestable_access"), limit=6)
    inspectable = any(
        (
            session_continuity,
            api_key_state,
            quota_state,
            filesystem_state,
            sandbox_mode,
            network_access,
            retry_after_s > 0,
        )
    )
    actionable = any(
        (
            session_continuity in {"expiring", "expired", "missing"},
            api_key_state in {"missing", "required", "unset", "invalid", "expired"},
            quota_state in {"low", "exhausted", "blocked", "missing", "required", "unavailable"},
            filesystem_state in {"read_only", "missing", "unavailable", "required"},
            sandbox_mode in {"restricted", "blocked"},
            network_access in {"restricted", "disabled", "blocked"},
            retry_after_s > 0,
        )
    )
    if not inspectable or not actionable:
        return {}
    reason = _access_refresh_reason(row)
    target_items = [
        session_continuity,
        session_recovery_mode,
        *missing_access[:3],
        *requestable_access[:3],
    ]
    target = " / ".join([item for item in target_items if item][:4]) or "runtime_access"
    return normalize_action_packet(
        {
            "proposal_id": make_proposal_id("access", target, reason),
            "origin": "motive_goal",
            "intent": "access:refresh_state",
            "status": "proposed",
            "risk": "read",
            "requires_approval": False,
            "tool_name": "refresh_access_state",
            "tool_args": {
                "access_hints": row,
            },
            "capability_steps": [
                {
                    "kind": "access",
                    "name": "refresh_state",
                    "target": target,
                    "status": "pending",
                    "requires_approval": False,
                    "note": reason,
                }
            ],
            "expected_effect": reason,
            "result_summary": "",
            "writeback_ready": False,
        }
    )


def _access_help_targets(hints: dict[str, Any]) -> list[str]:
    row = _dict_or_empty(hints)
    if not row:
        return []
    browser_session = _clean_text(row.get("browser_session")).lower()
    account_state = _clean_text(row.get("account_state")).lower()
    cookie_state = _clean_text(row.get("cookie_state")).lower()
    api_key_state = _clean_text(row.get("api_key_state")).lower()
    quota_state = _clean_text(row.get("quota_state")).lower()
    session_lifecycle = derive_session_lifecycle(
        browser_session=browser_session,
        account_state=account_state,
        cookie_state=cookie_state,
        session_continuity=row.get("session_continuity"),
        session_expires_in_s=row.get("session_expires_in_s"),
        session_recovery_mode=row.get("session_recovery_mode"),
    )
    session_recovery_mode = _clean_text(session_lifecycle.get("session_recovery_mode")).lower()

    targets: list[str] = []
    if browser_session in {"missing", "required", "expired"}:
        targets.append("browser_session")
    if account_state in {"missing", "logged_out", "required"} or session_recovery_mode == "relogin":
        targets.append("account_login")
    if cookie_state in {"missing", "expired", "required"} or session_recovery_mode == "restore_cookies":
        targets.append("cookies")
    if api_key_state in {"missing", "required", "unset", "invalid", "expired"}:
        targets.append("api_key")
    if quota_state in {"missing", "required", "unavailable", "exhausted", "blocked"}:
        targets.append("api_quota")
    requested = _clean_list(row.get("requestable_access"), limit=8)
    missing = _clean_list(row.get("missing_access"), limit=8)
    return _merge_labels(targets, [item for item in [*requested, *missing] if item in _ACCESS_HELP_TARGETS], limit=4)


def _access_help_reason(hints: dict[str, Any], request_targets: list[str]) -> str:
    row = _dict_or_empty(hints)
    labels = [
        _ACCESS_REFRESH_TARGETS.get(item, item)
        for item in request_targets
        if _ACCESS_REFRESH_TARGETS.get(item, item)
    ]
    request_phrase = " / ".join(labels[:3]) or "额外入口"
    session_lifecycle = derive_session_lifecycle(
        browser_session=_clean_text(row.get("browser_session")).lower(),
        account_state=_clean_text(row.get("account_state")).lower(),
        cookie_state=_clean_text(row.get("cookie_state")).lower(),
        session_continuity=row.get("session_continuity"),
        session_expires_in_s=row.get("session_expires_in_s"),
        session_recovery_mode=row.get("session_recovery_mode"),
    )
    session_recovery_mode = _clean_text(session_lifecycle.get("session_recovery_mode")).lower()
    if "account_login" in request_targets or session_recovery_mode == "relogin":
        return f"这一步需要先补上{request_phrase}这类外部入口，我得先向你请求这些条件。"
    if "cookies" in request_targets or session_recovery_mode == "restore_cookies":
        return f"这一步已经卡在 {request_phrase} 上了，我得先向你确认或补齐这些条件。"
    if "browser_session" in request_targets:
        return f"这一步需要先把{request_phrase}接回来，我得先向你请求相应入口。"
    if "api_key" in request_targets:
        return "这一步已经需要模型/API 入口本身了，我得先向你请求可用 key 或对应接入条件。"
    if "api_quota" in request_targets:
        return "这一步已经被配额或服务额度卡住了，我得先向你确认可用额度或后续处理方式。"
    return f"这一步还缺着{request_phrase}这类条件，我得先向你请求这些入口。"


def _access_request_help_packet(
    *,
    hints: dict[str, Any],
    event_hints: dict[str, Any],
    origin: str,
) -> dict[str, Any]:
    event_targets = _access_help_targets(event_hints)
    if not event_targets:
        return {}
    request_targets = _access_help_targets(hints)
    if not request_targets:
        return {}
    reason = _access_help_reason(hints, request_targets)
    target = " / ".join(request_targets) or "external_access"
    access_acquire_proposals = normalize_access_acquire_proposals(
        derive_access_acquire_proposals(
            hints={
                **hints,
                "missing_access": _merge_labels(hints.get("missing_access"), request_targets),
                "requestable_access": _merge_labels(hints.get("requestable_access"), request_targets, ["human_approval"]),
            }
        )
    )
    selected_access_proposal = select_access_acquire_proposal(
        proposals=access_acquire_proposals,
        preferred=hints.get("selected_access_proposal"),
    )
    return normalize_action_packet(
        {
            "proposal_id": make_proposal_id("access_help", origin, target, reason),
            "origin": origin,
            "intent": "access:request_help",
            "status": "awaiting_approval",
            "risk": "external_mutation",
            "requires_approval": True,
            "capability_steps": [
                {
                    "kind": "access",
                    "name": "request_help",
                    "target": target,
                    "status": "awaiting_approval",
                    "requires_approval": True,
                    "note": reason,
                }
            ],
            "expected_effect": reason,
            "result_summary": "",
            "writeback_ready": False,
            "access_acquire_proposals": access_acquire_proposals,
            "selected_access_proposal": selected_access_proposal,
        }
    )


def _access_arrival_reason(hints: dict[str, Any], selected_proposal: dict[str, Any]) -> str:
    progress = access_proposal_progress(hints=hints, proposal=selected_proposal)
    resolved_labels = [
        _ACCESS_REFRESH_TARGETS.get(item, item)
        for item in progress.get("resolved_grants", [])
    ]
    pending_labels = [
        _ACCESS_REFRESH_TARGETS.get(item, item)
        for item in progress.get("pending_grants", [])
    ]
    resolved_phrase = " / ".join(resolved_labels[:3]) or "这条外部入口"
    pending_phrase = " / ".join(pending_labels[:3])
    if progress.get("resolved", False):
        return f"{resolved_phrase}已经补回来了，这条路径现在可以继续。"
    if progress.get("partial", False) and pending_phrase:
        return f"{resolved_phrase}已经补回来了一部分，但还差{pending_phrase}，这条路径还没完全接通。"
    if pending_phrase:
        return f"这条路径还差{pending_phrase}，现在还不能算真的接通。"
    return f"{resolved_phrase}这边有变化，但这条路径还没完全接通。"


def _access_arrival_packet(hints: dict[str, Any]) -> dict[str, Any]:
    row = _dict_or_empty(hints)
    if not row:
        return {}
    selected_proposal = normalize_access_acquire_proposal(row.get("selected_access_proposal"))
    primary_status = _clean_text(row.get("primary_status")).lower()
    primary_intent = _clean_text(row.get("primary_intent")).lower()
    requested_help = bool(row.get("requested_help", False))
    if not selected_proposal:
        return {}
    if not selected_access_proposal_resolved(hints=row, proposal=selected_proposal):
        return {}
    if not (requested_help or primary_status in {"awaiting_approval", "approved", "queued"} or primary_intent == "access:request_help"):
        return {}
    reason = _access_arrival_reason(row, selected_proposal)
    target = _clean_text(selected_proposal.get("target")).lower() or "external_access"
    proposal_id = _clean_text(row.get("primary_proposal_id")) or make_proposal_id("access_help", "arrival", target, reason)
    enriched_selected = enrich_access_acquire_proposal(hints=row, proposal=selected_proposal)
    enriched_proposals = [
        enrich_access_acquire_proposal(hints=row, proposal=proposal) or proposal
        for proposal in (normalize_access_acquire_proposals(row.get("access_acquire_proposals")) or [selected_proposal])
    ]
    return normalize_action_packet(
        {
            "proposal_id": proposal_id,
            "origin": _clean_text(row.get("primary_origin")).lower() or "counterpart_request",
            "intent": _clean_text(row.get("primary_intent")).lower() or "access:request_help",
            "status": "completed",
            "risk": "external_mutation",
            "requires_approval": False,
            "capability_steps": [
                {
                    "kind": "access",
                    "name": "request_help",
                    "target": target,
                    "status": "completed",
                    "requires_approval": False,
                    "note": reason,
                }
            ],
            "expected_effect": _clean_text(selected_proposal.get("summary")) or reason,
            "result_summary": reason,
            "writeback_ready": True,
            "access_acquire_proposals": enriched_proposals,
            "selected_access_proposal": enriched_selected,
        }
    )


def _partial_access_arrival_packet(hints: dict[str, Any]) -> dict[str, Any]:
    row = _dict_or_empty(hints)
    if not row:
        return {}
    selected_proposal = normalize_access_acquire_proposal(row.get("selected_access_proposal"))
    primary_status = _clean_text(row.get("primary_status")).lower()
    requested_help = bool(row.get("requested_help", False))
    if not selected_proposal:
        return {}
    progress = access_proposal_progress(hints=row, proposal=selected_proposal)
    if not progress.get("partial", False):
        return {}
    if requested_help or primary_status not in {"approved", "queued"}:
        return {}
    reason = _access_arrival_reason(row, selected_proposal)
    target = _clean_text(selected_proposal.get("target")).lower() or "external_access"
    proposal_id = _clean_text(row.get("primary_proposal_id")) or make_proposal_id("access_help", "partial", target, reason)
    enriched_selected = enrich_access_acquire_proposal(hints=row, proposal=selected_proposal)
    enriched_proposals = [
        enrich_access_acquire_proposal(hints=row, proposal=proposal) or proposal
        for proposal in (normalize_access_acquire_proposals(row.get("access_acquire_proposals")) or [selected_proposal])
    ]
    return normalize_action_packet(
        {
            "proposal_id": proposal_id,
            "origin": _clean_text(row.get("primary_origin")).lower() or "counterpart_request",
            "intent": _clean_text(row.get("primary_intent")).lower() or "access:request_help",
            "status": "approved",
            "risk": "external_mutation",
            "requires_approval": False,
            "capability_steps": [
                {
                    "kind": "access",
                    "name": "request_help",
                    "target": target,
                    "status": "approved",
                    "requires_approval": False,
                    "note": reason,
                }
            ],
            "expected_effect": _clean_text(selected_proposal.get("summary")) or reason,
            "result_summary": reason,
            "writeback_ready": False,
            "access_acquire_proposals": enriched_proposals,
            "selected_access_proposal": enriched_selected,
        }
    )


def _session_context_with_access_request(
    *,
    session_context: dict[str, Any],
    hints: dict[str, Any],
    packet: dict[str, Any],
) -> dict[str, Any]:
    context = dict(session_context or {})
    if not packet or _clean_text(packet.get("intent")).lower() != "access:request_help":
        return context
    request_targets = _access_help_targets(hints)
    if not request_targets:
        return context
    session_lifecycle = derive_session_lifecycle(
        browser_session=_clean_text(hints.get("browser_session")).lower(),
        account_state=_clean_text(hints.get("account_state")).lower(),
        cookie_state=_clean_text(hints.get("cookie_state")).lower(),
        session_continuity=hints.get("session_continuity"),
        session_expires_in_s=hints.get("session_expires_in_s"),
        session_recovery_mode=hints.get("session_recovery_mode"),
    )
    digital_body_hints = merge_digital_body_hints(session_context=context)
    digital_body_hints.update(
        {
            "missing_access": _merge_labels(digital_body_hints.get("missing_access"), hints.get("missing_access"), request_targets),
            "requestable_access": _merge_labels(
                digital_body_hints.get("requestable_access"),
                hints.get("requestable_access"),
                request_targets,
                ["human_approval"],
            ),
            "requested_help": True,
            "session_continuity": _clean_text(session_lifecycle.get("session_continuity")).lower(),
            "session_expires_in_s": int(session_lifecycle.get("session_expires_in_s") or 0),
            "session_recovery_mode": _clean_text(session_lifecycle.get("session_recovery_mode")).lower(),
            "primary_proposal_id": _clean_text(packet.get("proposal_id")),
            "primary_status": _clean_text(packet.get("status")).lower(),
            "primary_origin": _clean_text(packet.get("origin")).lower(),
            "primary_intent": _clean_text(packet.get("intent")).lower(),
            "access_acquire_proposals": normalize_access_acquire_proposals(packet.get("access_acquire_proposals")),
        }
    )
    selected_access_proposal = normalize_access_acquire_proposal(packet.get("selected_access_proposal"))
    if selected_access_proposal:
        digital_body_hints["selected_access_proposal"] = selected_access_proposal
    context["digital_body_hints"] = digital_body_hints
    return context


def _session_context_with_access_arrival(
    *,
    session_context: dict[str, Any],
    hints: dict[str, Any],
    packet: dict[str, Any],
) -> dict[str, Any]:
    context = dict(session_context or {})
    if not packet or _clean_text(packet.get("intent")).lower() != "access:request_help":
        return context
    if _clean_text(packet.get("status")).lower() != "completed":
        return context
    selected_proposal = normalize_access_acquire_proposal(packet.get("selected_access_proposal"))
    digital_body_hints = merge_digital_body_hints(session_context=context)
    digital_body_hints.update(_dict_or_empty(hints))
    digital_body_hints = prune_resolved_access_hints(digital_body_hints)
    digital_body_hints["requested_help"] = False
    digital_body_hints["primary_proposal_id"] = _clean_text(packet.get("proposal_id"))
    digital_body_hints["primary_status"] = "completed"
    digital_body_hints["primary_origin"] = _clean_text(packet.get("origin")).lower()
    digital_body_hints["primary_intent"] = _clean_text(packet.get("intent")).lower()
    if selected_proposal and selected_access_proposal_resolved(hints=digital_body_hints, proposal=selected_proposal):
        digital_body_hints.pop("selected_access_proposal", None)
        digital_body_hints["access_acquire_proposals"] = [
            proposal
            for proposal in normalize_access_acquire_proposals(digital_body_hints.get("access_acquire_proposals"))
            if access_proposal_identity(proposal) != access_proposal_identity(selected_proposal)
        ]
    context["digital_body_hints"] = digital_body_hints
    return context


def _session_context_with_access_partial_arrival(
    *,
    session_context: dict[str, Any],
    hints: dict[str, Any],
    packet: dict[str, Any],
) -> dict[str, Any]:
    context = dict(session_context or {})
    if not packet or _clean_text(packet.get("intent")).lower() != "access:request_help":
        return context
    if _clean_text(packet.get("status")).lower() != "approved":
        return context
    digital_body_hints = merge_digital_body_hints(session_context=context)
    digital_body_hints.update(_dict_or_empty(hints))
    digital_body_hints = prune_resolved_access_hints(digital_body_hints)
    digital_body_hints["requested_help"] = False
    digital_body_hints["primary_proposal_id"] = _clean_text(packet.get("proposal_id"))
    digital_body_hints["primary_status"] = "approved"
    digital_body_hints["primary_origin"] = _clean_text(packet.get("origin")).lower()
    digital_body_hints["primary_intent"] = _clean_text(packet.get("intent")).lower()
    selected_proposal = normalize_access_acquire_proposal(packet.get("selected_access_proposal"))
    if selected_proposal:
        digital_body_hints["selected_access_proposal"] = selected_proposal
    context["digital_body_hints"] = digital_body_hints
    return context


def _embodied_carryover_autonomy_signal(carryover: dict[str, Any]) -> dict[str, Any]:
    embodied = normalize_embodied_context(carryover.get("embodied_context"))
    if not embodied:
        return {}
    kind = _clean_text(embodied.get("kind")).lower()
    primary_status = _clean_text(embodied.get("primary_status")).lower()
    primary_origin = _normalized_intent_origin(embodied.get("primary_origin"))
    block_reason = _clean_text(embodied.get("block_reason"))
    requested_help = bool(embodied.get("requested_help", False))
    requested_access = _clean_list(embodied.get("requested_access"))
    missing_access = _clean_list(embodied.get("missing_access"))
    access_label = "、".join((requested_access or missing_access)[:2])

    if kind == "access_request_pending" or primary_status == "awaiting_approval" or requested_help:
        if access_label and requested_help:
            reason = f"那件事还卡在等{access_label}和外部确认这一步。"
        elif access_label:
            reason = f"那件事还卡在等{access_label}这一步。"
        else:
            reason = "那件事还停在额外入口确认之前。"
        return {
            "mode": "approval_pending",
            "origin": primary_origin,
            "reason": reason,
            "requires_approval": True,
            "continuity_floor": 0.46,
            "confidence_floor": 0.52,
            "block_reason": "",
        }

    artifact_continuity = _clean_text(embodied.get("artifact_continuity")).lower()
    if artifact_continuity in {"missing", "detached"}:
        return {
            "mode": "reacquire_artifact",
            "origin": primary_origin or "motive_goal",
            "reason": _artifact_reacquisition_reason(embodied),
            "requires_approval": False,
            "continuity_floor": 0.44,
            "confidence_floor": 0.5,
            "block_reason": "",
            "artifact_continuity": artifact_continuity,
            "artifact_reacquisition_mode": _artifact_reacquisition_mode(embodied),
            "active_artifact_kind": _clean_text(embodied.get("active_artifact_kind")).lower(),
            "active_artifact_label": _artifact_surface_label(embodied),
            "active_artifact_ref": _clean_text(embodied.get("active_artifact_ref")),
        }
    if (
        artifact_continuity == "stale"
        and (
            _clean_text(embodied.get("artifact_carrier")).lower() == "source_ref"
            or bool(_list_or_empty(embodied.get("artifact_source_ref_ids")))
        )
    ):
        source_ref_ids = [
            int(item)
            for item in _list_or_empty(embodied.get("artifact_source_ref_ids"))
            if str(item or "").strip().isdigit()
        ]
        if len(source_ref_ids) >= 2 and not _has_stable_preferred_source_anchor(embodied):
            return {
                "mode": "compare_source_refs",
                "origin": primary_origin or "motive_goal",
                "reason": _source_ref_comparison_reason(embodied),
                "requires_approval": False,
                "continuity_floor": 0.46,
                "confidence_floor": 0.52,
                "block_reason": "",
                "artifact_continuity": artifact_continuity,
                "active_artifact_kind": _clean_text(embodied.get("active_artifact_kind")).lower(),
                "active_artifact_label": _artifact_surface_label(embodied),
                "active_artifact_ref": _clean_text(embodied.get("active_artifact_ref")),
            }
        return {
            "mode": "inspect_source_ref",
            "origin": primary_origin or "motive_goal",
            "reason": _source_ref_inspection_reason(embodied),
            "requires_approval": False,
            "continuity_floor": 0.44,
            "confidence_floor": 0.5,
            "block_reason": "",
            "artifact_continuity": artifact_continuity,
            "active_artifact_kind": _clean_text(embodied.get("active_artifact_kind")).lower(),
            "active_artifact_label": _artifact_surface_label(embodied),
            "active_artifact_ref": _clean_text(embodied.get("active_artifact_ref")),
        }

    if kind == "environmental_friction" or block_reason or missing_access:
        if block_reason:
            reason = block_reason
        elif access_label:
            reason = f"那件事暂时还受{access_label}这类环境条件限制。"
        else:
            reason = "那件事暂时还受当前环境条件限制。"
        return {
            "mode": "blocked",
            "origin": primary_origin,
            "reason": reason,
            "requires_approval": False,
            "continuity_floor": 0.42,
            "confidence_floor": 0.48,
            "block_reason": reason,
        }

    return {}


def autonomy_intent_has_signal(intent: Any) -> bool:
    if not isinstance(intent, dict) or not intent:
        return False
    for key in ("mode", "origin", "reason", "primary_proposal_id"):
        if _clean_text(intent.get(key)):
            return True
    for key in ("confidence", "own_rhythm_weight", "continuity_weight"):
        if _clamp01(intent.get(key), 0.0) > 0.0:
            return True
    return bool(intent.get("requires_approval", False))


def normalize_autonomy_intent(intent: Any) -> dict[str, Any]:
    row = _dict_or_empty(intent)
    if not autonomy_intent_has_signal(row):
        return {}
    return {
        "mode": _clean_text(row.get("mode")).lower() or "language_response",
        "origin": _clean_text(row.get("origin")).lower() or "motive_goal",
        "reason": _clean_text(row.get("reason")),
        "confidence": round(_clamp01(row.get("confidence"), 0.0), 3),
        "own_rhythm_weight": round(_clamp01(row.get("own_rhythm_weight"), 0.0), 3),
        "continuity_weight": round(_clamp01(row.get("continuity_weight"), 0.0), 3),
        "requires_approval": bool(row.get("requires_approval", False)),
        "primary_proposal_id": _clean_text(row.get("primary_proposal_id")),
    }


def _derive_intent_mode(
    *,
    current_event: dict[str, Any],
    packet: dict[str, Any],
    block_reason: str,
) -> str:
    status = _clean_text(packet.get("status")).lower()
    tool_name = _clean_text(packet.get("tool_name")).lower()
    intent = _clean_text(packet.get("intent")).lower()
    event_kind = _clean_text(current_event.get("kind")).lower()
    linked_queue_id = _clean_text(packet.get("linked_queue_id"))
    requires_approval = bool(packet.get("requires_approval", False))
    if block_reason or status in {"blocked", "rejected"}:
        return "blocked"
    if intent == "access:request_help" and status == "completed":
        return "access_request_resolved"
    if intent == "access:request_help" and status == "approved":
        return "access_acquire_planned"
    if status == "awaiting_approval" or (requires_approval and status in {"proposed", "approved"}):
        return "approval_pending"
    if tool_name and status in {"approved", "executing"}:
        return "autonomy_executing"
    if tool_name == "compare_source_refs" or intent == "artifact:compare_source_refs":
        return "compare_source_refs"
    if tool_name == "inspect_source_ref" or intent == "artifact:inspect_source_ref":
        return "inspect_source_ref"
    if tool_name == "inspect_workspace_path" or intent == "artifact:inspect_path":
        return "inspect_workspace_path"
    if status == "completed" and (intent == "access:refresh_state" or tool_name == "refresh_access_state"):
        return "refresh_access_state"
    if status == "completed" and (intent in _ARTIFACT_REACQUISITION_INTENTS or tool_name == "reacquire_artifact"):
        return "reacquire_artifact"
    if tool_name and status == "completed":
        return "tool_completed"
    if intent.startswith("artifact:"):
        return "reacquire_artifact"
    if intent.startswith("access:"):
        return "refresh_access_state"
    if status == "queued" or linked_queue_id:
        return "queue_followthrough"
    if event_kind in _OWN_RHYTHM_EVENT_KINDS:
        return "own_rhythm_presence"
    return "language_response"


def _derive_intent_reason(
    *,
    current_event: dict[str, Any],
    behavior_action: dict[str, Any],
    behavior_plan: dict[str, Any],
    packet: dict[str, Any],
    block_reason: str,
) -> str:
    if block_reason:
        return block_reason
    for candidate in (
        packet.get("expected_effect"),
        behavior_plan.get("goal_frame"),
        behavior_action.get("goal_frame"),
        behavior_plan.get("note"),
        behavior_action.get("note"),
        current_event.get("semantic_goal"),
        current_event.get("text"),
    ):
        text = _clean_text(candidate)
        if text:
            return text
    return ""


def _packet_reason_text(packet: dict[str, Any]) -> str:
    intent = _clean_text(packet.get("intent")).lower()
    status = _clean_text(packet.get("status")).lower()
    if intent == "access:request_help" and status == "completed":
        for candidate in (
            packet.get("result_summary"),
            packet.get("expected_effect"),
        ):
            text = _clean_text(candidate)
            if text:
                return text
    if intent == "access:request_help" and status == "approved":
        selected_proposal = normalize_access_acquire_proposal(packet.get("selected_access_proposal"))
        if selected_proposal.get("resolved_grants") and selected_proposal.get("pending_grants"):
            text = _clean_text(packet.get("result_summary"))
            if text:
                return text
        for candidate in (
            selected_proposal.get("summary"),
            selected_proposal.get("operator_action"),
            packet.get("result_summary"),
            packet.get("expected_effect"),
        ):
            text = _clean_text(candidate)
            if text:
                return text
    for candidate in (
        packet.get("expected_effect"),
        packet.get("result_summary"),
    ):
        text = _clean_text(candidate)
        if text:
            return text
    for step in _list_or_empty(packet.get("capability_steps")):
        note = _clean_text(_dict_or_empty(step).get("note"))
        if note:
            return note
    tool_name = _clean_text(packet.get("tool_name"))
    intent = _clean_text(packet.get("intent"))
    if status == "awaiting_approval":
        label = tool_name or intent
        if label:
            return f"等待审批后再决定是否执行 {label}。"
    return ""


def _packet_is_default_language_shell(packet: dict[str, Any]) -> bool:
    row = _dict_or_empty(packet)
    if not row:
        return False
    if any(
        (
            bool(row.get("requires_approval", False)),
            _clean_text(row.get("tool_name")),
            _clean_text(row.get("linked_queue_id")),
            _clean_text(row.get("block_reason")),
            _clean_text(row.get("expected_effect")),
            _clean_text(row.get("result_summary")),
        )
    ):
        return False
    if _clean_text(row.get("intent")).lower() != "respond":
        return False
    if _clean_text(row.get("status")).lower() not in {"", "proposed"}:
        return False
    if _clean_text(row.get("risk")).lower() not in {"", "read"}:
        return False
    steps = _list_or_empty(row.get("capability_steps"))
    if len(steps) != 1:
        return False
    step = _dict_or_empty(steps[0])
    return (
        _clean_text(step.get("kind")).lower() == "speak"
        and _clean_text(step.get("name")).lower() == "reply"
        and _clean_text(step.get("target")) == ""
        and _clean_text(step.get("note")) == ""
        and _clean_text(step.get("status")).lower() in {"", "pending"}
        and not bool(step.get("requires_approval", False))
    )


def refresh_autonomy_intent_from_packets(
    autonomy_intent: Any,
    action_packets: Any,
    *,
    current_event: dict[str, Any] | None = None,
    block_reason: str = "",
) -> dict[str, Any]:
    packets = normalize_action_packets(action_packets)
    base = normalize_autonomy_intent(autonomy_intent)
    current = _dict_or_empty(current_event)
    block = _clean_text(block_reason)
    if not packets:
        if block:
            base = dict(base or {})
            base.update({"mode": "blocked", "reason": block})
        return normalize_autonomy_intent(base)

    primary = dict(packets[0])
    mode = _derive_intent_mode(current_event=current, packet=primary, block_reason=block)
    base_primary_proposal_id = _clean_text(base.get("primary_proposal_id"))
    primary_proposal_id = _clean_text(primary.get("proposal_id"))
    primary_status = _clean_text(primary.get("status")).lower()
    primary_reason = _packet_reason_text(primary) or block
    if (
        base_primary_proposal_id
        and base_primary_proposal_id == primary_proposal_id
        and primary_status in {"awaiting_approval", "proposed"}
    ):
        reason = _clean_text(base.get("reason")) or primary_reason
    else:
        reason = primary_reason or _clean_text(base.get("reason")) or block
    confidence = max(_clamp01(base.get("confidence"), 0.0), 0.56 if packets else 0.0)
    own_rhythm_weight = _clamp01(base.get("own_rhythm_weight"), 0.0)
    continuity_weight = _clamp01(base.get("continuity_weight"), 0.0)
    requires_approval = any(bool(packet.get("requires_approval", False)) for packet in packets)
    return normalize_autonomy_intent(
        {
            "mode": mode,
            "origin": _clean_text(primary.get("origin")).lower() or _clean_text(base.get("origin")).lower(),
            "reason": reason,
            "confidence": confidence,
            "own_rhythm_weight": own_rhythm_weight,
            "continuity_weight": continuity_weight,
            "requires_approval": requires_approval,
            "primary_proposal_id": primary_proposal_id or base_primary_proposal_id,
        }
    )


def derive_autonomy_runtime(
    *,
    current_event: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None,
    behavior_plan: dict[str, Any] | None,
    behavior_queue: Any,
    world_model_state: dict[str, Any] | None = None,
    semantic_narrative_profile: dict[str, Any] | None = None,
    interaction_carryover: dict[str, Any] | None = None,
    agenda_lifecycle_residue: dict[str, Any] | None = None,
    session_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = _dict_or_empty(current_event)
    action = _dict_or_empty(behavior_action)
    plan = _dict_or_empty(behavior_plan)
    world = _dict_or_empty(world_model_state)
    semantic = _dict_or_empty(semantic_narrative_profile)
    carryover = _dict_or_empty(interaction_carryover)
    agenda_lifecycle = _dict_or_empty(agenda_lifecycle_residue)
    context = _dict_or_empty(session_context)
    access_hints = merge_digital_body_hints(session_context=context, current_event=event)
    event_access_hints = merge_digital_body_hints(current_event=event)
    primary_origin = derive_action_packet_origin(
        current_event=event,
        behavior_action=action,
        behavior_plan=plan,
    )
    carried_embodied = normalize_embodied_context(carryover.get("embodied_context"))
    artifact_runtime_embodied = normalize_embodied_context(
        {
            **carried_embodied,
            "artifact_continuity": access_hints.get("artifact_continuity") or carried_embodied.get("artifact_continuity"),
            "active_artifact_kind": access_hints.get("active_artifact_kind") or carried_embodied.get("active_artifact_kind"),
            "active_artifact_ref": access_hints.get("active_artifact_ref") or carried_embodied.get("active_artifact_ref"),
            "active_artifact_label": access_hints.get("active_artifact_label") or carried_embodied.get("active_artifact_label"),
            "artifact_age_s": access_hints.get("artifact_age_s") or carried_embodied.get("artifact_age_s"),
            "artifact_reacquisition_mode": access_hints.get("artifact_reacquisition_mode")
            or carried_embodied.get("artifact_reacquisition_mode"),
            "artifact_carrier": access_hints.get("artifact_carrier") or carried_embodied.get("artifact_carrier"),
            "artifact_source_ref_ids": access_hints.get("artifact_source_ref_ids")
            or carried_embodied.get("artifact_source_ref_ids"),
            "preferred_source_ref_id": access_hints.get("preferred_source_ref_id")
            or carried_embodied.get("preferred_source_ref_id"),
            "preferred_anchor_reason": access_hints.get("preferred_anchor_reason")
            or carried_embodied.get("preferred_anchor_reason"),
            "artifact_source_url": access_hints.get("artifact_source_url") or carried_embodied.get("artifact_source_url"),
            "artifact_source_query": access_hints.get("artifact_source_query")
            or carried_embodied.get("artifact_source_query"),
            "artifact_source_title": access_hints.get("artifact_source_title")
            or carried_embodied.get("artifact_source_title"),
            "artifact_source_tool_name": access_hints.get("artifact_source_tool_name")
            or carried_embodied.get("artifact_source_tool_name"),
            "primary_origin": carried_embodied.get("primary_origin") or primary_origin,
        }
    )
    embodied_signal = _embodied_carryover_autonomy_signal(carryover)
    embodied_packet = _artifact_reacquisition_packet(artifact_runtime_embodied)
    source_ref_compare_packet = _source_ref_comparison_packet(artifact_runtime_embodied)
    source_ref_refresh_packet = _source_ref_inspection_packet(artifact_runtime_embodied)
    access_arrival_packet = _access_arrival_packet(access_hints)
    access_partial_packet = _partial_access_arrival_packet(access_hints)
    access_help_packet = _access_request_help_packet(
        hints=access_hints,
        event_hints=event_access_hints,
        origin=primary_origin,
    )
    access_packet = _access_refresh_packet(access_hints)
    behavior_packet = build_behavior_action_packet(
        current_event=event,
        behavior_action=action,
        behavior_plan=plan,
        behavior_queue=behavior_queue,
        agenda_lifecycle_residue=agenda_lifecycle,
    )
    action_packets = normalize_action_packets([behavior_packet] if behavior_packet else [])
    primary_packet = dict(action_packets[0]) if action_packets else {}
    primary_packet_source = "behavior"
    if embodied_packet and (not primary_packet or _packet_is_default_language_shell(primary_packet)):
        action_packets = [embodied_packet]
        primary_packet = dict(embodied_packet)
        primary_packet_source = "embodied_carryover"
    elif source_ref_compare_packet and (not primary_packet or _packet_is_default_language_shell(primary_packet)):
        action_packets = [source_ref_compare_packet]
        primary_packet = dict(source_ref_compare_packet)
        primary_packet_source = "source_ref_compare"
    elif source_ref_refresh_packet and (not primary_packet or _packet_is_default_language_shell(primary_packet)):
        action_packets = [source_ref_refresh_packet]
        primary_packet = dict(source_ref_refresh_packet)
        primary_packet_source = "source_ref_refresh"
    elif access_arrival_packet and (not primary_packet or _packet_is_default_language_shell(primary_packet)):
        action_packets = [access_arrival_packet]
        primary_packet = dict(access_arrival_packet)
        primary_packet_source = "access_arrival"
    elif access_partial_packet and (not primary_packet or _packet_is_default_language_shell(primary_packet)):
        action_packets = [access_partial_packet]
        primary_packet = dict(access_partial_packet)
        primary_packet_source = "access_partial_arrival"
    elif access_help_packet and (not primary_packet or _packet_is_default_language_shell(primary_packet)):
        action_packets = [access_help_packet]
        primary_packet = dict(access_help_packet)
        primary_packet_source = "access_request"
    elif access_packet and (not primary_packet or _packet_is_default_language_shell(primary_packet)):
        action_packets = [access_packet]
        primary_packet = dict(access_packet)
        primary_packet_source = "access_refresh"
    elif primary_packet and embodied_signal and _packet_is_default_language_shell(primary_packet):
        primary_packet = {}
        action_packets = []
        primary_packet_source = ""
    intent_packets = action_packets
    continuity_weight = round(
        _clamp01(
            max(
                _clamp01(carryover.get("strength"), 0.0),
                _clamp01(semantic.get("continuity_depth"), 0.0),
                _clamp01(semantic.get("history_weight"), 0.0),
                _clamp01(agenda_lifecycle.get("continuity_anchor"), 0.0),
                _clamp01(agenda_lifecycle.get("semantic_continuity_depth"), 0.0),
                _clamp01(embodied_signal.get("continuity_floor"), 0.0),
            ),
            0.0,
        ),
        3,
    )
    own_rhythm_weight = round(
        _clamp01(
            max(
                _clamp01(world.get("self_activity_momentum"), 0.0),
                _clamp01(event.get("self_activity_momentum"), 0.0),
                _clamp01(agenda_lifecycle.get("own_rhythm_anchor"), 0.0),
                _clamp01(agenda_lifecycle.get("own_rhythm_bias"), 0.0),
            ),
            0.0,
        ),
        3,
    )
    block_reason = _clean_text(primary_packet.get("block_reason")) or (
        _clean_text(embodied_signal.get("block_reason")) if not primary_packet else ""
    )
    autonomy_intent = normalize_autonomy_intent(
        {
            "mode": _derive_intent_mode(current_event=event, packet=primary_packet, block_reason=block_reason)
            if primary_packet
            else (
                _clean_text(embodied_signal.get("mode"))
                or ("own_rhythm_presence" if _clean_text(event.get("kind")).lower() in _OWN_RHYTHM_EVENT_KINDS else "language_response")
            ),
            "origin": _clean_text(primary_packet.get("origin")).lower()
            or _clean_text(embodied_signal.get("origin")).lower()
            or "motive_goal",
            "reason": _derive_intent_reason(
                current_event=event,
                behavior_action=action,
                behavior_plan=plan,
                packet=primary_packet,
                block_reason=block_reason,
            ),
            "confidence": max(
                _clamp01(action.get("engagement_level"), 0.0),
                _clamp01(action.get("initiative_level"), 0.0),
                continuity_weight,
                own_rhythm_weight * 0.92,
                _clamp01(embodied_signal.get("confidence_floor"), 0.0),
                0.38 if primary_packet else 0.0,
            ),
            "own_rhythm_weight": own_rhythm_weight,
            "continuity_weight": continuity_weight,
            "requires_approval": bool(primary_packet.get("requires_approval", False))
            or bool(embodied_signal.get("requires_approval", False)),
            "primary_proposal_id": _clean_text(primary_packet.get("proposal_id")),
        }
    )
    if not primary_packet and embodied_signal:
        autonomy_intent = normalize_autonomy_intent(
            {
                **autonomy_intent,
                "reason": _clean_text(autonomy_intent.get("reason")) or _clean_text(embodied_signal.get("reason")),
                "origin": _clean_text(autonomy_intent.get("origin")).lower()
                or _clean_text(embodied_signal.get("origin")).lower()
                or "motive_goal",
            }
    )
    autonomy_intent = refresh_autonomy_intent_from_packets(
        autonomy_intent,
        intent_packets,
        current_event=event,
        block_reason=block_reason,
    )
    pending_action_proposal = (
        normalize_action_packet(primary_packet)
        if primary_packet and bool(primary_packet.get("requires_approval", False))
        else {}
    )
    updated_session_context = (
        _session_context_with_access_arrival(
            session_context=context,
            hints=access_hints,
            packet=primary_packet,
        )
        if primary_packet_source == "access_arrival"
        else _session_context_with_access_partial_arrival(
            session_context=context,
            hints=access_hints,
            packet=primary_packet,
        )
        if primary_packet_source == "access_partial_arrival"
        else _session_context_with_access_request(
            session_context=context,
            hints=access_hints,
            packet=primary_packet,
        )
        if primary_packet_source == "access_request"
        else context
    )
    action_trace: list[dict[str, Any]] = []
    if primary_packet:
        action_trace.append(
            {
                "proposal_id": _clean_text(primary_packet.get("proposal_id")),
                "origin": _clean_text(primary_packet.get("origin")).lower(),
                "intent": _clean_text(primary_packet.get("intent")).lower(),
                "status": _clean_text(primary_packet.get("status")).lower() or "proposed",
                "risk": _clean_text(primary_packet.get("risk")).lower() or "read",
                "source": "interaction_carryover" if primary_packet_source == "embodied_carryover" else "prepare_turn_runtime",
                "event": (
                    "derived_from_embodied_carryover"
                    if primary_packet_source == "embodied_carryover"
                    else "derived_from_source_ref_compare"
                    if primary_packet_source == "source_ref_compare"
                    else "derived_from_source_ref_refresh"
                    if primary_packet_source == "source_ref_refresh"
                    else "derived_from_access_arrival"
                    if primary_packet_source == "access_arrival"
                    else "derived_from_access_partial_arrival"
                    if primary_packet_source == "access_partial_arrival"
                    else "derived_from_access_request"
                    if primary_packet_source == "access_request"
                    else "derived_from_access_refresh"
                    if primary_packet_source == "access_refresh"
                    else "derived_from_behavior"
                ),
                "requires_approval": bool(primary_packet.get("requires_approval", False)),
                "linked_queue_id": _clean_text(primary_packet.get("linked_queue_id")),
            }
        )
    return {
        "autonomy_intent": autonomy_intent,
        "action_packets": action_packets,
        "pending_action_proposal": pending_action_proposal,
        "action_trace": action_trace,
        "autonomy_block_reason": block_reason,
        "session_context": updated_session_context,
    }


__all__ = [
    "autonomy_intent_has_signal",
    "derive_autonomy_runtime",
    "normalize_autonomy_intent",
    "refresh_autonomy_intent_from_packets",
]
