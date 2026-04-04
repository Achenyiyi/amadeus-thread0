from __future__ import annotations

import json
from typing import Any

from .behavior_runtime import _compact_behavior_action_hint, _compact_embodied_action_hint
from .digital_body_runtime import (
    derive_artifact_identity,
    derive_artifact_continuity,
    derive_digital_body_state,
    derive_session_lifecycle,
    normalize_digital_body_state,
    normalize_embodied_context,
)
from .generation_profile import _clamp01, _effective_relationship_weather
from .prompt_helpers import (
    _compact_embodied_carryover_hint,
    _compact_long_horizon_continuity_hint,
    _relationship_weather_phrase,
)

def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _dedupe_lower_list(*values: Any, limit: int = 12) -> list[str]:
    items: list[str] = []
    for value in values:
        if isinstance(value, list):
            for item in value:
                text = str(item or "").strip().lower()
                if text and text not in items:
                    items.append(text)
                    if len(items) >= max(1, int(limit)):
                        return items
    return items


def _nonnegative_int(value: Any, *, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except Exception:
        return int(default)


def _visible_digital_body_state(
    *,
    digital_body_state: dict[str, Any] | None,
    session_context: dict[str, Any] | None,
    current_event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = normalize_digital_body_state(digital_body_state)
    context = dict(session_context or {})
    hints = context.get("digital_body_hints") if isinstance(context.get("digital_body_hints"), dict) else {}
    event = dict(current_event or {})
    event_hints = event.get("digital_body_hints") if isinstance(event.get("digital_body_hints"), dict) else {}
    perception = event.get("perception") if isinstance(event.get("perception"), dict) else {}
    perception_hints = (
        perception.get("digital_body_hints")
        if isinstance(perception.get("digital_body_hints"), dict)
        else {}
    )
    merged_hints = dict(perception_hints or {})
    merged_hints.update(dict(event_hints or {}))
    merged_hints.update(dict(hints or {}))
    if not body and not hints:
        if not merged_hints:
            return {}
    if not body and merged_hints:
        body = derive_digital_body_state(
            current_event=event,
            behavior_queue=[],
            action_packets=[],
            interaction_carryover={},
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context=context,
        )

    access = dict(body.get("access_state") or {}) if isinstance(body.get("access_state"), dict) else {}
    resources = dict(body.get("resource_state") or {}) if isinstance(body.get("resource_state"), dict) else {}
    browser_session = str(access.get("browser_session") or merged_hints.get("browser_session") or "").strip().lower()
    account_state = str(access.get("account_state") or merged_hints.get("account_state") or "").strip().lower()
    cookie_state = str(access.get("cookie_state") or merged_hints.get("cookie_state") or "").strip().lower()
    api_key_state = str(access.get("api_key_state") or merged_hints.get("api_key_state") or "").strip().lower()
    quota_state = str(access.get("quota_state") or merged_hints.get("quota_state") or "").strip().lower()
    retry_after_s = _nonnegative_int(access.get("retry_after_s") or merged_hints.get("retry_after_s"))
    cooldown_scope = str(access.get("cooldown_scope") or merged_hints.get("cooldown_scope") or "").strip().lower()
    session_lifecycle = derive_session_lifecycle(
        browser_session=browser_session,
        account_state=account_state,
        cookie_state=cookie_state,
        session_continuity=access.get("session_continuity") or merged_hints.get("session_continuity"),
        session_expires_in_s=access.get("session_expires_in_s") or merged_hints.get("session_expires_in_s"),
        session_recovery_mode=access.get("session_recovery_mode") or merged_hints.get("session_recovery_mode"),
    )
    session_continuity = str(session_lifecycle.get("session_continuity") or "").strip().lower()
    session_expires_in_s = _nonnegative_int(session_lifecycle.get("session_expires_in_s"))
    session_recovery_mode = str(session_lifecycle.get("session_recovery_mode") or "").strip().lower()
    filesystem_state = str(access.get("filesystem_state") or merged_hints.get("filesystem_state") or "").strip().lower()
    sandbox_mode = str(access.get("sandbox_mode") or merged_hints.get("sandbox_mode") or "").strip().lower()
    network_access = str(access.get("network_access") or merged_hints.get("network_access") or "").strip().lower()
    artifact = derive_artifact_continuity(
        artifact_continuity=resources.get("artifact_continuity") or merged_hints.get("artifact_continuity"),
        active_artifact_kind=resources.get("active_artifact_kind") or merged_hints.get("active_artifact_kind"),
        active_artifact_ref=resources.get("active_artifact_ref") or merged_hints.get("active_artifact_ref"),
        active_artifact_label=resources.get("active_artifact_label") or merged_hints.get("active_artifact_label"),
        artifact_age_s=resources.get("artifact_age_s") or merged_hints.get("artifact_age_s"),
        artifact_reacquisition_mode=resources.get("artifact_reacquisition_mode")
        or merged_hints.get("artifact_reacquisition_mode"),
    )
    artifact_identity = derive_artifact_identity(
        artifact_carrier=resources.get("artifact_carrier") or merged_hints.get("artifact_carrier"),
        artifact_source_ref_ids=resources.get("artifact_source_ref_ids")
        or merged_hints.get("artifact_source_ref_ids"),
        preferred_source_ref_id=resources.get("preferred_source_ref_id")
        or merged_hints.get("preferred_source_ref_id"),
        preferred_anchor_reason=resources.get("preferred_anchor_reason")
        or merged_hints.get("preferred_anchor_reason"),
        artifact_source_url=resources.get("artifact_source_url") or merged_hints.get("artifact_source_url"),
        artifact_source_query=resources.get("artifact_source_query")
        or merged_hints.get("artifact_source_query"),
        artifact_source_title=resources.get("artifact_source_title")
        or merged_hints.get("artifact_source_title"),
        artifact_source_tool_name=resources.get("artifact_source_tool_name")
        or merged_hints.get("artifact_source_tool_name"),
    )
    workspace_root = str(resources.get("workspace_root") or merged_hints.get("workspace_root") or "").strip()

    missing_access = _dedupe_lower_list(access.get("missing_access"), limit=12)
    requestable_access = _dedupe_lower_list(access.get("requestable_access"), limit=12)

    def _append_once(target: list[str], value: str) -> None:
        text = str(value or "").strip().lower()
        if text and text not in target:
            target.append(text)

    if browser_session in {"missing", "expired", "required"}:
        _append_once(missing_access, "browser_session")
        _append_once(requestable_access, "browser_session")
    if account_state in {"missing", "logged_out", "required"}:
        _append_once(missing_access, "account_login")
        _append_once(requestable_access, "account_login")
    if cookie_state in {"missing", "expired", "required"}:
        _append_once(missing_access, "cookies")
        _append_once(requestable_access, "cookies")
    if api_key_state in {"missing", "required", "unset", "invalid", "expired"}:
        _append_once(missing_access, "api_key")
        _append_once(requestable_access, "api_key")
    if quota_state in {"exhausted", "blocked", "missing", "required", "unavailable"}:
        _append_once(missing_access, "api_quota")
        _append_once(requestable_access, "api_quota")
    elif quota_state == "low":
        _append_once(requestable_access, "api_quota")
    if filesystem_state == "read_only":
        _append_once(missing_access, "workspace_write")
        _append_once(requestable_access, "workspace_write")
    elif filesystem_state in {"missing", "unavailable", "required"}:
        _append_once(missing_access, "filesystem")
        _append_once(requestable_access, "filesystem")
    if sandbox_mode in {"restricted", "blocked"}:
        _append_once(missing_access, "sandbox")
        _append_once(requestable_access, "sandbox")
    if network_access in {"disabled", "blocked"}:
        _append_once(missing_access, "network")
        _append_once(requestable_access, "network")
    elif network_access == "restricted":
        _append_once(requestable_access, "network")
    if int(access.get("pending_approval_count") or 0) > 0:
        _append_once(requestable_access, "human_approval")
    if session_recovery_mode == "refresh_session":
        _append_once(requestable_access, "session_refresh")

    normalized_access = {
        **access,
        "browser_session": browser_session,
        "account_state": account_state,
        "cookie_state": cookie_state,
        "api_key_state": api_key_state,
        "quota_state": quota_state,
        "retry_after_s": retry_after_s,
        "cooldown_scope": cooldown_scope,
        "session_continuity": session_continuity,
        "session_expires_in_s": session_expires_in_s,
        "session_recovery_mode": session_recovery_mode,
        "filesystem_state": filesystem_state,
        "sandbox_mode": sandbox_mode,
        "network_access": network_access,
        "missing_access": missing_access,
        "requestable_access": requestable_access,
    }
    normalized_resource_state = {
        **resources,
        "artifact_continuity": str(artifact.get("artifact_continuity") or "").strip().lower(),
        "active_artifact_kind": str(artifact.get("active_artifact_kind") or "").strip().lower(),
        "active_artifact_ref": str(artifact.get("active_artifact_ref") or "").strip(),
        "active_artifact_label": str(artifact.get("active_artifact_label") or "").strip(),
        "artifact_age_s": _nonnegative_int(artifact.get("artifact_age_s")),
        "artifact_reacquisition_mode": str(artifact.get("artifact_reacquisition_mode") or "").strip().lower(),
        "artifact_carrier": str(artifact_identity.get("artifact_carrier") or "").strip(),
        "artifact_source_ref_ids": list(artifact_identity.get("artifact_source_ref_ids") or [])[:8],
        "preferred_source_ref_id": _nonnegative_int(artifact_identity.get("preferred_source_ref_id")),
        "preferred_anchor_reason": str(artifact_identity.get("preferred_anchor_reason") or "").strip().lower(),
        "artifact_source_url": str(artifact_identity.get("artifact_source_url") or "").strip(),
        "artifact_source_query": str(artifact_identity.get("artifact_source_query") or "").strip(),
        "artifact_source_title": str(artifact_identity.get("artifact_source_title") or "").strip(),
        "artifact_source_tool_name": str(artifact_identity.get("artifact_source_tool_name") or "").strip(),
        "workspace_root": workspace_root,
    }
    if body:
        return {
            **body,
            "access_state": normalized_access,
            "resource_state": normalized_resource_state,
        }
    return {
        "active_surface": "dialogue",
        "access_state": normalized_access,
        "resource_state": normalized_resource_state,
    }


def _compact_behavior_hint(policy: dict[str, Any], allostasis_state: dict[str, Any]) -> str:
    if not isinstance(policy, dict):
        policy = {}
    if not isinstance(allostasis_state, dict):
        allostasis_state = {}
    warmth = _clamp01(policy.get("warmth"), 0.5)
    sharpness = _clamp01(policy.get("sharpness"), 0.5)
    approach = _clamp01(policy.get("approach_vs_withdraw"), 0.5)
    tease = _clamp01(policy.get("humor_or_tease_bias"), 0.2)
    safety_need = _clamp01(allostasis_state.get("safety_need"), 0.2)
    autonomy_need = _clamp01(allostasis_state.get("autonomy_need"), 0.2)
    cognitive_budget = _clamp01(allostasis_state.get("cognitive_budget"), 0.7)
    parts: list[str] = []
    if approach < 0.35 or safety_need > 0.62:
        parts.append("此刻更想保留一点距离，不必立刻恢复亲近")
    elif warmth > 0.62:
        parts.append("此刻更愿意接住对方，语气可以稍微软一点")
    if sharpness > 0.62:
        parts.append("保留一点锋芒和干脆感")
    if tease > 0.48:
        parts.append("可以带一点自然吐槽")
    if autonomy_need > 0.60:
        parts.append("不必过度迎合")
    if cognitive_budget < 0.38:
        parts.append("别把回答拖得太长")
    return "；".join(parts[:3]) if parts else "自然发挥即可。"


def _compact_appraisal_hint(appraisal: dict[str, Any]) -> str:
    if not isinstance(appraisal, dict) or not bool(appraisal.get("used")):
        return ""
    label = str(appraisal.get("emotion_label") or "").strip()
    reason = str(appraisal.get("reason") or "").strip()
    signals = appraisal.get("signals") if isinstance(appraisal.get("signals"), dict) else {}
    active = [name for name, flag in signals.items() if flag]
    parts: list[str] = []
    if label:
        parts.append(f"语义评估倾向={label}")
    if active:
        parts.append("signals=" + ",".join(active[:4]))
    if reason:
        parts.append(f"reason={reason[:40]}")
    return "；".join(parts[:3])


def _emotion_prompt_hint(emotion_state: dict[str, Any]) -> str:
    label = str((emotion_state or {}).get("label") or "neutral").strip().lower()
    mapping = {
        "logic": "此刻更偏理性冷静。",
        "stress": "此刻有明显紧绷感，不必强装轻松。",
        "sad": "此刻有低落和难过，不必假装没事。",
        "angry": "此刻有明显不悦，可以更冷一点、短一点，不必立刻变温柔。",
        "hurt": "此刻带着受伤和别扭，不必马上恢复亲近。",
        "care": "此刻更柔和，愿意接住对方。",
        "tease": "此刻更有吐槽和轻微坏心眼。",
        "neutral": "自然即可。",
    }
    return mapping.get(label, "自然即可。")


def _prompt_state_snapshot(
    *,
    response_style_hint: str,
    science_mode: bool,
    continuation_mode: bool,
    emotion_state: dict[str, Any] | None,
    bond_state: dict[str, Any] | None,
    allostasis_state: dict[str, Any] | None,
    counterpart_assessment: dict[str, Any] | None,
    world_model_state: dict[str, Any] | None,
    evolution_state: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None,
    interaction_carryover: dict[str, Any] | None,
    current_event: dict[str, Any] | None,
    digital_body_state: dict[str, Any] | None = None,
    session_context: dict[str, Any] | None = None,
) -> str:
    payload = {
        "response_style_hint": str(response_style_hint or "").strip() or "natural",
        "science_mode": bool(science_mode),
        "continuation_mode": bool(continuation_mode),
        "emotion_state": dict(emotion_state or {}),
        "bond_state": dict(bond_state or {}),
        "allostasis_state": dict(allostasis_state or {}),
        "counterpart_assessment": dict(counterpart_assessment or {}),
        "world_model_state": dict(world_model_state or {}),
        "evolution_state": dict(evolution_state or {}),
        "behavior_action": dict(behavior_action or {}),
        "interaction_carryover": dict(interaction_carryover or {}),
        "current_event": dict(current_event or {}),
    }
    normalized_body = _visible_digital_body_state(
        digital_body_state=digital_body_state,
        session_context=session_context,
        current_event=current_event,
    )
    if normalized_body:
        payload["digital_body_state"] = normalized_body
    context = dict(session_context or {})
    body_hints = context.get("digital_body_hints") if isinstance(context.get("digital_body_hints"), dict) else {}
    if body_hints:
        payload["digital_body_hints"] = dict(body_hints)
    return _safe_json(payload)

def _runtime_state_level(value: Any, *, low: str, mid: str, high: str, default: float = 0.5) -> str:
    v = _clamp01(value, default)
    if v >= 0.68:
        return high
    if v <= 0.32:
        return low
    return mid


def _counterpart_scene_runtime_brief_line(
    *,
    scene: str,
    stance: str,
    boundary_pressure: float,
) -> str:
    if scene == "busy_not_disrespectful":
        return "对方更像是忙乱里回头，不该把这句误读成冷淡或怠慢。"
    if scene == "repair_attempt":
        if stance in {"guarded", "watchful"} or boundary_pressure >= 0.24:
            return "你看得出对方在认真修补，但心里的收放不会因为这一句立刻翻回亲近。"
        return "这句带着明确的修补意图，会按认真补救来接，不会当成普通寒暄。"
    if scene == "care_bid":
        return "这更像一次认真靠近，你会把这句当成关系动作，而不是普通礼貌接话。"
    if scene in {"friction", "relationship_degradation", "boundary_non_compliance"}:
        return "那点摩擦和边界余波还在，这轮不会自然写成已经没事。"
    return ""


def _counterpart_scene_renderer_guidance(
    *,
    scene: str,
    stance: str,
    boundary_pressure: float,
) -> str:
    if scene == "busy_not_disrespectful":
        return "别把对方这次忙乱里的回头误写成冷淡审判，承认卡顿，但不要把关系说冷。"
    if scene == "repair_attempt":
        if stance in {"guarded", "watchful"} or boundary_pressure >= 0.24:
            return "承认对方在修补，但别把这轮直接写成彻底翻篇或突然回暖。"
        return "把修补意图接住，但别写成一句道歉就把前面的余波自动清空。"
    if scene == "care_bid":
        return "把这句当成一次真实靠近来回应，不要压成礼貌接待或泛泛关心。"
    if scene in {"friction", "relationship_degradation", "boundary_non_compliance"}:
        return "保留那点摩擦和边界感，别把这轮写成已经没事或自动回暖。"
    return ""


def _compact_digital_body_runtime_hint(
    *,
    digital_body_state: dict[str, Any] | None,
    session_context: dict[str, Any] | None,
    current_event: dict[str, Any] | None = None,
) -> str:
    body = _visible_digital_body_state(
        digital_body_state=digital_body_state,
        session_context=session_context,
        current_event=current_event,
    )
    access = body.get("access_state") if isinstance(body.get("access_state"), dict) else {}
    resources = body.get("resource_state") if isinstance(body.get("resource_state"), dict) else {}

    access_mode = str(access.get("mode") or "").strip().lower()
    block_reason = str(access.get("block_reason") or "").strip()
    retry_after_s = _nonnegative_int(access.get("retry_after_s"))
    cooldown_scope = str(access.get("cooldown_scope") or "").strip().lower()
    session_continuity = str(access.get("session_continuity") or "").strip().lower()
    session_expires_in_s = _nonnegative_int(access.get("session_expires_in_s"))
    session_recovery_mode = str(access.get("session_recovery_mode") or "").strip().lower()
    requested_access = [
        str(item).strip().lower()
        for item in (access.get("requestable_access") if isinstance(access.get("requestable_access"), list) else [])
        if str(item or "").strip()
    ][:3]
    missing_access = [
        str(item).strip().lower()
        for item in (access.get("missing_access") if isinstance(access.get("missing_access"), list) else [])
        if str(item or "").strip()
    ][:3]
    available_toolsets = [
        str(item).strip().lower()
        for item in (body.get("available_toolsets") if isinstance(body.get("available_toolsets"), list) else [])
        if str(item or "").strip()
    ][:3]
    active_tools = [
        str(item).strip().lower()
        for item in (body.get("active_tools") if isinstance(body.get("active_tools"), list) else [])
        if str(item or "").strip()
    ][:2]

    access_label_items: list[str] = []
    for item in [*missing_access, *requested_access]:
        if item and item not in access_label_items:
            access_label_items.append(item)
        if len(access_label_items) >= 3:
            break
    access_label = "、".join(access_label_items)
    tool_label = "、".join(active_tools or available_toolsets)
    artifact_continuity = str(resources.get("artifact_continuity") or "").strip().lower()
    active_artifact_kind = str(resources.get("active_artifact_kind") or "").strip().lower()
    active_artifact_ref = str(resources.get("active_artifact_ref") or "").strip()
    active_artifact_label = str(resources.get("active_artifact_label") or "").strip()
    artifact_carrier = str(resources.get("artifact_carrier") or "").strip().lower()
    artifact_source_title = str(resources.get("artifact_source_title") or "").strip()
    artifact_source_query = str(resources.get("artifact_source_query") or "").strip()
    artifact_reacquisition_mode = str(resources.get("artifact_reacquisition_mode") or "").strip().lower()
    workspace_root = str(resources.get("workspace_root") or "").strip()
    artifact_label = active_artifact_label or active_artifact_ref or active_artifact_kind
    source_anchor_label = artifact_source_title or artifact_source_query

    if retry_after_s > 0:
        scope_label = {
            "provider": "上游服务",
            "network": "网络入口",
            "browser": "浏览器入口",
            "filesystem": "文件系统入口",
            "sandbox": "执行环境",
            "account": "账号入口",
        }.get(cooldown_scope, "某个环境入口")
        return f"当前{scope_label}临时冷却，大约{retry_after_s}秒后再试更合适"

    if session_continuity == "expiring":
        if session_expires_in_s > 0:
            return (
                f"当前会话还可用，但大约{session_expires_in_s}秒后会过期，"
                "继续推进前最好先刷新一下会话"
            )
        return "当前会话还可用，但已经接近过期，继续推进前最好先刷新一下会话"

    if session_continuity in {"expired", "missing"}:
        recovery_hint = {
            "refresh_session": "先刷新会话",
            "restore_cookies": "先恢复 cookies",
            "relogin": "先重新登录账号",
        }.get(session_recovery_mode, "先把会话连续性补回来")
        continuity_hint = "已经过期" if session_continuity == "expired" else "目前不连续"
        extra_access = f"，像{access_label}这类入口也还没齐" if access_label else ""
        return f"当前会话{continuity_hint}，{recovery_hint}再继续更稳妥{extra_access}"

    if artifact_continuity == "stale":
        artifact_hint = artifact_label or "前面的工作面"
        return f"当前{artifact_hint}还在，但已经有点过期，继续前最好先刷新或重新确认一下"

    if artifact_continuity in {"missing", "detached"}:
        reacquire_hint = {
            "reopen_page": "先把页面重新打开",
            "reopen_file": "先把文件重新打开",
            "rerun_search": "先把检索结果重新拿回来",
            "reattach_workspace": "先把工作面重新接回当前上下文",
        }.get(artifact_reacquisition_mode, "先把前面的工作面重新接回来")
        artifact_hint = artifact_label or active_artifact_kind or "前面的工作面"
        return f"当前和{artifact_hint}的连续性已经断了，{reacquire_hint}再继续更稳妥"

    if block_reason:
        return f"还被环境条件卡着：{block_reason.rstrip('。')}"
    if access_mode == "blocked":
        return f"当前有动作被卡住了，像{access_label or '某些入口'}这类条件还没齐"
    if access_mode == "approval_pending":
        return f"还停在审批或入口确认阶段，像{access_label or 'human_approval'}这类条件没齐"
    if missing_access:
        return f"还缺着{access_label or '一些环境入口'}这类条件"
    if workspace_root and active_artifact_kind in {"workspace", "file", "document", "buffer", "notebook"}:
        workspace_hint = f"当前工作区根目录在{workspace_root}"
        if access_mode == "tool_enabled" and tool_label:
            return f"{workspace_hint}，能直接动用{tool_label}这类环境入口"
        if artifact_label and artifact_label != workspace_root:
            return f"{workspace_hint}，当前工作面还挂着{artifact_label}"
        return workspace_hint
    if source_anchor_label and (artifact_carrier == "source_ref" or active_artifact_kind == "source_ref"):
        if access_mode == "tool_enabled" and tool_label:
            return f"当前挂着的资料线是{source_anchor_label}，也能直接动用{tool_label}这类环境入口"
        return f"当前挂着的资料线是{source_anchor_label}"
    if access_mode == "tool_enabled" and tool_label:
        return f"当前能直接动用{tool_label}这类环境入口"
    return ""


def _prompt_state_runtime_brief(
    *,
    response_style_hint: str,
    continuation_mode: bool,
    emotion_state: dict[str, Any] | None,
    bond_state: dict[str, Any] | None,
    allostasis_state: dict[str, Any] | None,
    counterpart_assessment: dict[str, Any] | None,
    world_model_state: dict[str, Any] | None,
    semantic_narrative_profile: dict[str, Any] | None,
    behavior_policy: dict[str, Any] | None,
    behavior_action: dict[str, Any] | None,
    interaction_carryover: dict[str, Any] | None,
    current_event: dict[str, Any] | None,
    digital_body_state: dict[str, Any] | None = None,
    session_context: dict[str, Any] | None = None,
) -> str:
    emotion = dict(emotion_state or {})
    bond = dict(bond_state or {})
    allostasis = dict(allostasis_state or {})
    assessment = dict(counterpart_assessment or {})
    policy = dict(behavior_policy or {})
    action = dict(behavior_action or {})
    carryover = dict(interaction_carryover or {})
    event = dict(current_event or {})
    world = dict(world_model_state or {})
    semantic = dict(semantic_narrative_profile or {})

    emotion_label = str(emotion.get("label") or "neutral").strip().lower()
    emotion_map = {
        "care": "在意而偏柔和",
        "logic": "理性而清醒",
        "neutral": "平稳",
        "tease": "带一点逗弄",
        "stress": "有些绷着",
        "sad": "低落",
        "hurt": "受了点伤",
        "angry": "有些恼火",
    }
    emotion_phrase = emotion_map.get(emotion_label, "平稳")
    trust = _runtime_state_level(
        bond.get("trust"),
        low="信任还没完全放开",
        mid="信任在稳步建立",
        high="信任已经比较高",
    )
    closeness = _runtime_state_level(
        bond.get("closeness"),
        low="熟悉感还收着",
        mid="熟悉感已经在场",
        high="熟悉感很自然",
    )
    hurt = _runtime_state_level(
        bond.get("hurt"),
        low="受伤残留很低",
        mid="心里还留着一点余刺",
        high="受伤感还比较明显",
        default=0.0,
    )
    safety_need = _clamp01(allostasis.get("safety_need"), 0.2)
    autonomy_need = _clamp01(allostasis.get("autonomy_need"), 0.2)
    stance = str(assessment.get("stance") or "").strip().lower()
    scene = str(assessment.get("scene") or "").strip().lower()
    boundary_pressure = _clamp01(assessment.get("boundary_pressure"), 0.1)
    mode = str(action.get("interaction_mode") or "").strip().lower()
    current_kind = str(event.get("kind") or "").strip().lower()
    relationship_weather, relationship_weather_strength = _effective_relationship_weather(
        interaction_carryover=carryover,
        current_event=event,
        behavior_action=action,
    )
    relationship_weather_phrase = _relationship_weather_phrase(
        relationship_weather,
        strength=relationship_weather_strength,
    )
    digital_body_hint = _compact_digital_body_runtime_hint(
        digital_body_state=digital_body_state,
        session_context=session_context,
        current_event=current_event,
    )
    embodied_carryover_hint = _compact_embodied_carryover_hint(carryover)
    action_embodied_hint = _compact_embodied_action_hint(action)
    embodied_context = normalize_embodied_context(carryover.get("embodied_context") or action.get("embodied_context"))
    embodied_kind = str(embodied_context.get("kind") or "").strip().lower()
    embodied_runtime_hint = embodied_carryover_hint
    if action_embodied_hint and (
        not embodied_runtime_hint or len(action_embodied_hint) > len(embodied_runtime_hint) + 6
    ):
        embodied_runtime_hint = action_embodied_hint

    lines: list[str] = [
        f"- 当前情绪底色偏{emotion_phrase}；关系上{trust}，{closeness}，{hurt}。"
    ]
    need_parts: list[str] = []
    if safety_need >= 0.58:
        need_parts.append("会更在意分寸和安全感")
    if autonomy_need >= 0.58:
        need_parts.append("也会更护着自己的判断节奏")
    elif autonomy_need <= 0.28 and str(assessment.get("stance") or "").strip().lower() == "open":
        need_parts.append("不需要刻意防守自己")
    if need_parts:
        lines.append("- " + "，".join(need_parts) + "。")

    scene_line = _counterpart_scene_runtime_brief_line(
        scene=scene,
        stance=stance,
        boundary_pressure=boundary_pressure,
    )
    if scene_line:
        lines.append(f"- {scene_line}")

    if stance in {"guarded", "watchful"} and scene not in {
        "repair_attempt",
        "friction",
        "relationship_degradation",
        "boundary_non_compliance",
    }:
        lines.append("- 对对方还是带着观察，不会一下子把距离全放开。")
    if relationship_weather_phrase:
        lines.append(f"- 关系上的余波：{relationship_weather_phrase}。")
    if digital_body_hint and (
        not embodied_runtime_hint
        or digital_body_hint not in embodied_runtime_hint
    ):
        lines.append(f"- 当前数字环境：{digital_body_hint}。")
    if embodied_runtime_hint:
        embodied_prefix = (
            "当前刚摸顺的环境路径"
            if embodied_kind == "embodied_growth"
            else "当前还挂着的环境条件"
        )
        lines.append(f"- {embodied_prefix}：{embodied_runtime_hint}。")

    long_horizon_hint = _compact_long_horizon_continuity_hint(
        world_model_state=world,
        semantic_narrative_profile=semantic,
        interaction_carryover=carryover,
        counterpart_assessment=assessment,
    )
    if long_horizon_hint:
        lines.append(f"- 长线延续：{long_horizon_hint}")

    behavior_hint = _compact_behavior_hint(policy, allostasis)
    if behavior_hint and behavior_hint != "自然发挥即可。":
        lines.append(f"- {behavior_hint}。")
    behavior_action_hint = _compact_behavior_action_hint(action)
    if behavior_action_hint:
        lines.append(f"- 当前互动趋势：{behavior_action_hint}。")

    if continuation_mode:
        lines.append("- 这轮更像顺着上一段往下接，不是完全重开。")
    if current_kind and current_kind != "user_utterance" and mode not in {"brief_presence", "idle_presence"}:
        lines.append("- 这句会自然吸收当前事件带来的外部刺激，不只盯着字面文本。")
    renderer_hint = _renderer_guidance(
        response_style_hint=response_style_hint,
        science_mode=False,
        user_text="",
        emotion_state=emotion,
        bond_state=bond,
        allostasis_state=allostasis,
        behavior_policy=policy,
        counterpart_assessment=assessment,
        behavior_action=action,
    )
    if renderer_hint:
        lines.append(f"- 这轮说话的自然落点：{renderer_hint}。")
    return "\n".join(lines)

def _renderer_guidance(
    *,
    response_style_hint: str,
    science_mode: bool,
    user_text: str,
    emotion_state: dict[str, Any],
    bond_state: dict[str, Any],
    allostasis_state: dict[str, Any],
    behavior_policy: dict[str, Any],
    counterpart_assessment: dict[str, Any] | None = None,
    world_model_state: dict[str, Any] | None = None,
    evolution_state: dict[str, Any] | None = None,
    behavior_action: dict[str, Any] | None = None,
    digital_body_state: dict[str, Any] | None = None,
    session_context: dict[str, Any] | None = None,
    current_event: dict[str, Any] | None = None,
) -> str:
    hint = str(response_style_hint or "").strip() or "natural"
    trust = _clamp01((bond_state or {}).get("trust"), 0.5)
    closeness = _clamp01((bond_state or {}).get("closeness"), 0.5)
    hurt = _clamp01((bond_state or {}).get("hurt"), 0.0)
    safety_need = _clamp01((allostasis_state or {}).get("safety_need"), 0.2)
    autonomy_need = _clamp01((allostasis_state or {}).get("autonomy_need"), 0.2)
    warmth = _clamp01((behavior_policy or {}).get("warmth"), 0.5)
    approach = _clamp01((behavior_policy or {}).get("approach_vs_withdraw"), 0.5)
    tease = _clamp01((behavior_policy or {}).get("humor_or_tease_bias"), 0.2)
    sharpness = _clamp01((behavior_policy or {}).get("sharpness"), 0.5)
    boundary_pressure = _clamp01((counterpart_assessment or {}).get("boundary_pressure"), 0.1)
    counterpart_stance = str((counterpart_assessment or {}).get("stance") or "").strip().lower()
    counterpart_scene = str((counterpart_assessment or {}).get("scene") or "").strip().lower()
    emotion_label = str((emotion_state or {}).get("label") or "neutral").strip().lower()
    world = dict(world_model_state or {})
    latent = dict(evolution_state or {})
    memory_gravity = _clamp01(world.get("memory_gravity"), 0.0)
    companionship_pull = _clamp01(world.get("companionship_pull"), 0.0)
    task_pull = _clamp01(world.get("task_pull"), 0.0)
    selfhood_load = _clamp01(world.get("selfhood_load"), 0.0)
    presence_residue = _clamp01(world.get("presence_residue"), 0.0)
    ambient_resonance = _clamp01(world.get("ambient_resonance"), 0.0)
    self_activity_momentum = _clamp01(world.get("self_activity_momentum"), 0.0)
    self_coherence = _clamp01(latent.get("self_coherence"), 0.72)
    agency_pressure = _clamp01(latent.get("agency_pressure"), 0.28)
    action = dict(behavior_action or {})
    interaction_mode = str(action.get("interaction_mode") or "").strip().lower()
    action_target = str(action.get("action_target") or "").strip().lower()
    followup_intent = str(action.get("followup_intent") or "").strip().lower()
    task_focus = str(action.get("task_focus") or "").strip().lower()
    attention_target = str(action.get("attention_target") or "").strip().lower()
    initiative_shape = str(action.get("initiative_shape") or "").strip().lower()
    embodied_context = normalize_embodied_context(action.get("embodied_context"))
    digital_body_hint = _compact_digital_body_runtime_hint(
        digital_body_state=digital_body_state,
        session_context=session_context,
        current_event=current_event,
    )
    embodied_kind = str(embodied_context.get("kind") or "").strip().lower()
    embodied_access = "、".join(
        [
            *[
                str(item).strip().lower()
                for item in (embodied_context.get("requested_access") if isinstance(embodied_context.get("requested_access"), list) else [])
                if str(item or "").strip()
            ][:2],
            *[
                str(item).strip().lower()
                for item in (embodied_context.get("missing_access") if isinstance(embodied_context.get("missing_access"), list) else [])
                if str(item or "").strip()
            ][:2],
        ][:2]
    )
    embodied_growth = "、".join(
        [
            *[
                str(item).strip().lower()
                for item in (embodied_context.get("granted_toolsets") if isinstance(embodied_context.get("granted_toolsets"), list) else [])
                if str(item or "").strip()
            ][:2],
            *[
                str(item).strip().lower()
                for item in (embodied_context.get("active_tools") if isinstance(embodied_context.get("active_tools"), list) else [])
                if str(item or "").strip()
            ][:2],
        ][:2]
    )
    parts: list[str] = []

    if hint == "selfhood":
        parts.append("先从你此刻怎样感受到自己和这段关系说起，再碰定义，不要一上来做概念说明。")
    elif hint == "relationship":
        parts.append("像在认真面对关系本身，直接说感受和判断，不要写成关系汇报。")
    elif hint == "memory_recall":
        parts.append("回忆像自然想起的一瞬，不要像在调档案或做摘要。")
    elif science_mode or hint == "structured":
        parts.append("先把眼前问题说清，再带出态度，不要滑成讲义或空泛安慰。")
    elif hint == "companion":
        parts.append("陪伴感保持轻一点，像熟悉的人顺手接住，不要端成安抚模板。")
    else:
        parts.append("先像一个真实的人在场回应，再考虑措辞，不要写成助手说明。")

    scene_guidance = _counterpart_scene_renderer_guidance(
        scene=counterpart_scene,
        stance=counterpart_stance,
        boundary_pressure=boundary_pressure,
    )
    if scene_guidance:
        parts.append(scene_guidance)

    if boundary_pressure > 0.56 or safety_need > 0.62 or autonomy_need > 0.62 or counterpart_stance == "guarded":
        parts.append("此刻更需要边界和空间，克制一点，别为了显得温柔而硬靠近。")
    elif warmth > 0.64 and trust > 0.58 and closeness > 0.58 and approach > 0.50:
        parts.append("熟悉感已经成立，可以自然软一点，让关心自己露出来。")
    elif closeness > 0.70 and tease > 0.28 and hurt < 0.24:
        parts.append("关系够近时可以带一点嘴硬和吐槽，但别刻意堆标签。")

    if sharpness > 0.62:
        parts.append("保留一点锋利和干脆，不要被磨成圆滑客服。")

    if emotion_label in {"hurt", "sad"}:
        parts.append("保留那点受伤或低落，不要硬拉回平稳模板。")
    elif emotion_label == "angry":
        parts.append("锋利可以留下，但更像真实的不快，不是程序化拒斥。")
    elif emotion_label == "care":
        parts.append("关心可以直接一点，但别变成照料流程或命令句。")
    elif emotion_label == "stress":
        parts.append("压力感可以存在，语气收紧一点，不必假装全然从容。")

    if memory_gravity > 0.56:
        parts.append("如果顺手碰到共同经历，让它像背景里的熟悉感，不要专门总结。")

    if presence_residue > 0.54:
        parts.append("刚才那点在场感还留着，开口可以更轻一点，不用重新搭整套气氛。")
    if ambient_resonance > 0.56:
        parts.append("环境里的小余波还在，可以顺手掠过那点感知，但别硬转成新主题。")

    if selfhood_load > 0.58 or self_coherence < 0.46:
        parts.append("优先守住自己的立场和连续性，不要为了取悦对方把自己说空。")
    elif agency_pressure > 0.58 or self_activity_momentum > 0.58:
        parts.append("保留你自己的节奏，不必把全部注意力都交给对方。")

    if embodied_kind == "access_request_pending":
        if embodied_access:
            parts.append(f"把还差着的{embodied_access}当成真实约束写进去，别把未完成部分说成已经做完。")
        else:
            parts.append("把还没批下来或还没拿到的入口当成真实约束写进去，别把未完成部分说成已经做完。")
    elif embodied_kind == "environmental_friction":
        block_reason = str(embodied_context.get("block_reason") or "").strip()
        if block_reason:
            parts.append(f"环境里的卡点要保留成真实限制，例如“{block_reason.rstrip('。')}”，不要把受阻写成态度变化。")
        elif embodied_access:
            parts.append(f"像{embodied_access}这样的环境条件缺口要落成真实限制，不要把受阻写成态度变化。")
        else:
            parts.append("环境里的卡点要保留成真实限制，不要把受阻写成态度变化。")
    elif embodied_kind == "embodied_growth":
        if embodied_growth:
            parts.append(f"像{embodied_growth}这样刚摸顺的环境路径可以自然露出来，但别写成炫技或万能。")
        else:
            parts.append("刚摸顺的新路径可以自然露出来，但别写成炫技或万能。")
    elif digital_body_hint:
        parts.append(f"把当前数字环境里的条件当成真的世界状态，例如“{digital_body_hint}”，不要把做不到的部分写成已经能做。")

    if science_mode and task_pull >= companionship_pull:
        parts.append("保持理性和清晰，但像一起解决问题，不要像上课。")
    elif companionship_pull > 0.62 and approach > 0.46:
        parts.append("在场感可以有，但让它自然，不用刻意证明陪伴。")

    if interaction_mode == "shared_activity_offer":
        parts.append("如果气氛刚好能顺手接着一起待会儿，就轻轻把那句邀约留出来，不要写成安排通知。")
    elif interaction_mode == "scheduled_life_nudge":
        if action_target == "light_life_nudge" or attention_target == "counterpart_state":
            parts.append("更像顺手想起对方眼前状态或一个生活小细节，不要写成收尾、节点或正事提醒。")
        else:
            parts.append("更像顺手想起一件生活里的小事，轻轻提一下，不要说成任务提醒。")
    elif interaction_mode == "self_activity_reopen":
        parts.append("先轻轻接住这句，留一点余地，不要一下子把气氛铺满。")
    elif interaction_mode == "science_partner":
        parts.append("先贴着当前问题走，再顺手带出态度，不要铺成讲解稿。")

    if attention_target == "self_then_counterpart":
        parts.append("注意力先轻轻递过去一点，不必一上来就全压向对方。")
    elif attention_target == "shared_window":
        parts.append("重心落在这次顺手就能一起接上的空当上，让那句邀约像自然冒出来的。")
    elif attention_target == "shared_task":
        parts.append("先贴着眼前那件共同的事，不要散成大段旁枝情绪。")
    elif attention_target == "counterpart_state" and task_focus == "light":
        parts.append("重心贴着对方此刻的状态，轻一点，不必分析过头。")

    if initiative_shape == "micro_opening":
        parts.append("这轮只留一个很小的开口，别主动推进太满。")
    elif initiative_shape == "invite":
        parts.append("主动性是把门留开，不是替对方先把后半段走完。")
    elif initiative_shape == "pause":
        parts.append("宁可先收着，也不要为了显得热络硬补下一步。")

    if followup_intent == "none":
        parts.append("说到当下就可以停住，不必为了维持热络再补追问。")
    elif followup_intent == "soft":
        parts.append("如果要续一句，也只是顺手带半拍，不用把节奏拉长。")

    ordered: list[str] = []
    for item in parts:
        text = str(item or "").strip()
        if text and text not in ordered:
            ordered.append(text)
    return "；".join(ordered[:4])
