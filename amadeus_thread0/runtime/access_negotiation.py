from __future__ import annotations

from typing import Any

from ..graph_parts.action_packets import normalize_access_acquire_proposal, normalize_action_packet
from ..graph_parts.browser_runtime import (
    normalize_browser_execution_preview,
    normalize_browser_execution_result,
    normalize_browser_runtime_state,
)
from ..graph_parts.digital_body_runtime import (
    derive_access_acquire_proposals,
    select_access_acquire_proposal,
)
from .final_state import resolve_action_packets, resolve_digital_body_state, resolve_pending_action_proposal


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _clean_text(value: Any, *, limit: int = 240) -> str:
    return str(value or "").strip()[:limit]


def _clean_label_list(value: Any, *, limit: int = 8) -> list[str]:
    out: list[str] = []
    for item in _list_or_empty(value):
        text = str(item or "").strip().lower()
        if not text or text in out:
            continue
        out.append(text)
        if len(out) >= max(1, int(limit)):
            break
    return out

def _target_phrase(labels: list[str]) -> str:
    mapping = {
        "account_login": "账号登录态",
        "api_key": "API key",
        "browser_session": "浏览器会话",
        "cookie": "cookies",
        "cookies": "cookies",
        "filesystem": "工作区写入入口",
        "workspace_write": "工作区写入入口",
        "human_approval": "你的确认",
        "network": "联网入口",
        "network_access": "联网入口",
        "quota": "额度",
        "sandbox": "sandbox 执行入口",
    }
    readable = [mapping.get(item, item.replace("_", " ")) for item in labels if item != "human_approval"]
    if not readable:
        return "当前这条入口"
    return " / ".join(readable[:3])


def _proposal_action_phrase(proposal: dict[str, Any]) -> str:
    operator_action = _clean_text(proposal.get("operator_action"))
    if operator_action:
        return operator_action.rstrip("。")
    summary = _clean_text(proposal.get("summary"))
    if summary:
        return summary.rstrip("。")
    mode = _clean_text(proposal.get("mode")).lower()
    target = _clean_text(proposal.get("target")).lower()
    if mode == "operator_login":
        return "先把目标账号登录好"
    if mode == "operator_provide_api_key":
        return "先给我一个可用的 API key"
    if mode == "operator_create_workspace":
        return "先把可写工作区开出来"
    if mode == "operator_enable_network":
        return "先把网络访问打开"
    if target:
        return f"先把 {target.replace('_', ' ')} 这条入口补齐"
    return "先把这条入口补齐"


def _page_ref_from_browser(result: dict[str, Any], preview: dict[str, Any]) -> str:
    page_ref = _clean_text(preview.get("page_ref"), limit=64)
    if page_ref:
        return page_ref
    page_id = _clean_text(result.get("page_id"), limit=64)
    return f"page:{page_id}" if page_id else ""


def _page_label(result: dict[str, Any], preview: dict[str, Any]) -> str:
    title = _clean_text(result.get("title")) or _clean_text(preview.get("page_title"))
    if title:
        return title
    url = _clean_text(result.get("url"), limit=160) or _clean_text(preview.get("page_url"), limit=160)
    return url


def _pending_access_context(
    values: dict[str, Any] | None,
    *,
    pending_action_proposal: dict[str, Any] | None = None,
    action_packets: Any = None,
    reconsolidation_snapshot: dict[str, Any] | None = None,
    digital_body_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = values if isinstance(values, dict) else {}
    pending = normalize_action_packet(pending_action_proposal)
    if not pending:
        pending = resolve_pending_action_proposal(
            pending_action_proposal=_dict_or_empty(data.get("pending_action_proposal")),
            action_packets=action_packets if action_packets is not None else data.get("action_packets"),
            reconsolidation_snapshot=reconsolidation_snapshot
            if isinstance(reconsolidation_snapshot, dict)
            else _dict_or_empty(data.get("reconsolidation_snapshot")),
        )
    if _clean_text(pending.get("intent")).lower() != "access:request_help":
        return {}
    status = _clean_text(pending.get("status")).lower()
    if status not in {"proposed", "awaiting_approval", "approved"}:
        return {}

    body = resolve_digital_body_state(
        digital_body_state=digital_body_state
        if isinstance(digital_body_state, dict)
        else _dict_or_empty(data.get("digital_body_state")),
        reconsolidation_snapshot=_dict_or_empty(data.get("reconsolidation_snapshot")),
    )
    access_state = _dict_or_empty(body.get("access_state"))
    requested_access = _clean_label_list(access_state.get("requestable_access"))
    missing_access = _clean_label_list(access_state.get("missing_access"))
    proposals = [
        dict(item)
        for item in (
            access_state.get("access_acquire_proposals")
            if isinstance(access_state.get("access_acquire_proposals"), list)
            else pending.get("access_acquire_proposals")
        )
        if isinstance(item, dict)
    ]
    if not proposals:
        proposals = derive_access_acquire_proposals(hints=access_state)
    selected = select_access_acquire_proposal(
        proposals=proposals,
        preferred=(
            access_state.get("selected_access_proposal")
            if isinstance(access_state.get("selected_access_proposal"), dict)
            else pending.get("selected_access_proposal")
        ),
    )
    missing_phrase = _target_phrase(missing_access or requested_access)
    action_phrase = _proposal_action_phrase(selected)
    message = (
        f"喂，先别催。我现在卡在 {missing_phrase} 这一步，入口还没真的接上。"
        f"你先{action_phrase}；你一处理完，我就沿着这件事继续做，不用你再提醒。"
    )
    return {
        "kind": "grant_access",
        "packet": pending,
        "assist_request": {
            "kind": "grant_access",
            "message": message,
            "requested_access": requested_access,
            "missing_access": missing_access,
            "selected_access_proposal": selected,
            "requires_manual_takeover": False,
            "resume_mode": "auto_continue",
            "proposal_id": _clean_text(pending.get("proposal_id"), limit=128),
        },
    }


def _manual_takeover_context(
    values: dict[str, Any] | None,
    *,
    action_packets: Any = None,
    reconsolidation_snapshot: dict[str, Any] | None = None,
    digital_body_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = values if isinstance(values, dict) else {}
    body = resolve_digital_body_state(
        digital_body_state=digital_body_state
        if isinstance(digital_body_state, dict)
        else _dict_or_empty(data.get("digital_body_state")),
        reconsolidation_snapshot=_dict_or_empty(data.get("reconsolidation_snapshot")),
    )
    access_state = _dict_or_empty(body.get("access_state"))
    resource_state = _dict_or_empty(body.get("resource_state"))
    browser_runtime_state = normalize_browser_runtime_state(access_state.get("browser_runtime_state"))
    if not browser_runtime_state.get("manual_takeover_required", False):
        return {}

    packets = resolve_action_packets(
        action_packets=action_packets if action_packets is not None else data.get("action_packets"),
        reconsolidation_snapshot=reconsolidation_snapshot
        if isinstance(reconsolidation_snapshot, dict)
        else _dict_or_empty(data.get("reconsolidation_snapshot")),
    )
    source_packet: dict[str, Any] = {}
    preview: dict[str, Any] = {}
    result: dict[str, Any] = {}
    for packet in reversed(packets):
        tool_name = _clean_text(packet.get("tool_name")).lower()
        intent = _clean_text(packet.get("intent")).lower()
        if not tool_name.startswith("browser_") and not intent.startswith("browser:"):
            continue
        packet_preview = normalize_browser_execution_preview(packet.get("browser_execution_preview"))
        packet_result = normalize_browser_execution_result(packet.get("browser_execution_result"))
        if not (
            packet_preview.get("requires_manual_takeover", False)
            or packet_result.get("manual_takeover_required", False)
            or tool_name == "browser_begin_manual_takeover"
        ):
            continue
        source_packet = packet
        preview = packet_preview
        result = packet_result
        break
    if not source_packet:
        return {}

    selected = normalize_access_acquire_proposal(access_state.get("selected_access_proposal"))
    requested_access = _clean_label_list(access_state.get("requestable_access"))
    missing_access = _clean_label_list(access_state.get("missing_access"))
    page_label = _page_label(result, preview) or _clean_text(resource_state.get("active_artifact_label"))
    target_label = (
        _clean_text(preview.get("target_label"))
        or _clean_text(preview.get("target_ref"), limit=120)
        or _clean_text(result.get("target_ref"), limit=120)
        or "当前页面这一步"
    )
    message = (
        f"这一步碰到 {target_label} 的敏感输入了。密码、OTP、passkey、验证码这种东西我不会替你乱碰。"
        f"你接管一下{page_label or '当前页面'}把这步处理完；你一搞定，我就从原位继续。"
    )
    proposal_id = _clean_text(source_packet.get("proposal_id"), limit=128) or _clean_text(
        browser_runtime_state.get("last_run_id"),
        limit=128,
    )
    profile_id = _clean_text(result.get("profile_id"), limit=120) or _clean_text(
        preview.get("profile_id"),
        limit=120,
    )
    page_ref = _page_ref_from_browser(result, preview)
    tab_id = _clean_text(result.get("tab_id"), limit=64) or _clean_text(
        resource_state.get("browser_tab_id"),
        limit=64,
    )
    return {
        "kind": "manual_takeover",
        "packet": source_packet,
        "assist_request": {
            "kind": "manual_takeover",
            "message": message,
            "requested_access": requested_access or ["human_approval"],
            "missing_access": missing_access,
            "selected_access_proposal": selected,
            "requires_manual_takeover": True,
            "resume_mode": "auto_continue",
            "proposal_id": proposal_id,
            "profile_id": profile_id,
            "page_ref": page_ref,
            "tab_id": tab_id,
        },
    }


def resolve_access_negotiation_context(
    values: dict[str, Any] | None,
    *,
    pending_action_proposal: dict[str, Any] | None = None,
    action_packets: Any = None,
    reconsolidation_snapshot: dict[str, Any] | None = None,
    digital_body_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pending = _pending_access_context(
        values,
        pending_action_proposal=pending_action_proposal,
        action_packets=action_packets,
        reconsolidation_snapshot=reconsolidation_snapshot,
        digital_body_state=digital_body_state,
    )
    if pending:
        return pending
    return _manual_takeover_context(
        values,
        action_packets=action_packets,
        reconsolidation_snapshot=reconsolidation_snapshot,
        digital_body_state=digital_body_state,
    )


def derive_assist_request(
    values: dict[str, Any] | None,
    *,
    pending_action_proposal: dict[str, Any] | None = None,
    action_packets: Any = None,
    reconsolidation_snapshot: dict[str, Any] | None = None,
    digital_body_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = resolve_access_negotiation_context(
        values,
        pending_action_proposal=pending_action_proposal,
        action_packets=action_packets,
        reconsolidation_snapshot=reconsolidation_snapshot,
        digital_body_state=digital_body_state,
    )
    return dict(context.get("assist_request") or {}) if isinstance(context.get("assist_request"), dict) else {}


def attach_assist_request_to_pending_approval(
    pending_approval: dict[str, Any] | None,
    *,
    assist_request: dict[str, Any] | None,
    source_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assist = dict(assist_request or {}) if isinstance(assist_request, dict) else {}
    pending = dict(pending_approval or {}) if isinstance(pending_approval, dict) else {}
    if not assist:
        return pending
    if not pending and isinstance(source_packet, dict):
        source = dict(source_packet)
        pending = {
            "proposal_id": _clean_text(source.get("proposal_id"), limit=128),
            "intent": _clean_text(source.get("intent"), limit=120).lower(),
            "status": _clean_text(source.get("status"), limit=64).lower(),
            "risk": _clean_text(source.get("risk"), limit=64).lower() or "external_mutation",
            "requires_approval": True,
        }
        preview = normalize_browser_execution_preview(source.get("browser_execution_preview"))
        if preview:
            pending["browser_execution_preview"] = preview
        result = normalize_browser_execution_result(source.get("browser_execution_result"))
        if result:
            pending["browser_execution_result"] = result
        selected = normalize_access_acquire_proposal(source.get("selected_access_proposal"))
        if selected:
            pending["selected_access_proposal"] = selected
    pending["assist_request"] = assist
    return pending


def build_access_resume_event_override(
    values: dict[str, Any] | None,
    *,
    assist_request: dict[str, Any],
) -> dict[str, Any]:
    data = values if isinstance(values, dict) else {}
    current_event = _dict_or_empty(data.get("current_event"))
    goal = (
        _clean_text(current_event.get("semantic_goal"), limit=280)
        or _clean_text(current_event.get("effective_text"), limit=280)
        or _clean_text(current_event.get("text"), limit=280)
        or _clean_text(data.get("pending_user_goal"), limit=280)
        or "继续当前任务"
    )
    request = dict(assist_request or {})
    hint_key = "just_completed_takeover" if _clean_text(request.get("kind")).lower() == "manual_takeover" else "just_resolved_access"
    hint_payload = {
        "proposal_id": _clean_text(request.get("proposal_id"), limit=128),
        "selected_access_proposal": normalize_access_acquire_proposal(request.get("selected_access_proposal")),
    }
    for key in ("profile_id", "page_ref", "tab_id"):
        text = _clean_text(request.get(key), limit=120)
        if text:
            hint_payload[key] = text
    return {
        "kind": "access_resume",
        "source": "access_negotiation",
        "text": goal,
        "effective_text": goal,
        "semantic_goal": goal,
        "response_style_hint": _clean_text(current_event.get("response_style_hint"), limit=80) or "natural",
        "science_mode": bool(current_event.get("science_mode", False)),
        "continuation_mode": True,
        "counterpart_name": _clean_text(current_event.get("counterpart_name"), limit=120),
        "event_frame": "外部入口刚刚接通，继续当前这件事。",
        "digital_body_hints": {hint_key: hint_payload},
    }


def derive_access_resume_ack(values: dict[str, Any] | None) -> str:
    data = values if isinstance(values, dict) else {}
    current_event = _dict_or_empty(data.get("current_event"))
    hints = _dict_or_empty(current_event.get("digital_body_hints"))
    if not hints:
        hints = _dict_or_empty(_dict_or_empty(current_event.get("perception")).get("digital_body_hints"))
    resolved = _dict_or_empty(hints.get("just_resolved_access"))
    if resolved:
        selected = normalize_access_acquire_proposal(resolved.get("selected_access_proposal"))
        phrase = _proposal_action_phrase(selected).removeprefix("先")
        if phrase:
            return f"好，{phrase}已经接上了。我继续。"
        return "好，入口已经接上了。我继续。"
    takeover = _dict_or_empty(hints.get("just_completed_takeover"))
    if takeover:
        return "好，浏览器这边已经接回来了。我继续。"
    return ""


def payload_user_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        return ""
    for item in reversed(messages):
        role = ""
        content = ""
        if isinstance(item, dict):
            role = _clean_text(item.get("role"), limit=32).lower()
            content = _clean_text(item.get("content"), limit=240)
        else:
            role = _clean_text(getattr(item, "type", "") or getattr(item, "role", ""), limit=32).lower()
            content = _clean_text(getattr(item, "content", ""), limit=240)
        if role in {"user", "human"} and content:
            return content
    return ""


def looks_like_takeover_completion_signal(text: str) -> bool:
    compact = _clean_text(text, limit=240).replace(" ", "").lower()
    if not compact:
        return False
    if any(marker in compact for marker in ("不用继续", "先别继续", "别继续", "不要继续")):
        return False
    positive_markers = (
        "好了",
        "可以了",
        "我接管好了",
        "接管完了",
        "登录好了",
        "已经登录",
        "输好了",
        "验证码好了",
        "密码填好了",
        "done",
        "finished",
        "continue",
    )
    return any(marker in compact for marker in positive_markers)


__all__ = [
    "attach_assist_request_to_pending_approval",
    "build_access_resume_event_override",
    "derive_access_resume_ack",
    "derive_assist_request",
    "looks_like_takeover_completion_signal",
    "payload_user_text",
    "resolve_access_negotiation_context",
]
