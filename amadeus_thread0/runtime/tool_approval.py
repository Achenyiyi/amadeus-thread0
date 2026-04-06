from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..graph_parts.action_packets import normalize_access_acquire_proposal, normalize_access_acquire_proposals


SILENT_MEMORY_APPROVAL_TOOLS = frozenset(
    {
        "set_profile",
        "confirm_profile",
        "correct_profile",
        "undo_profile_correction",
        "delete_profile",
        "add_moment",
        "delete_moment",
        "rebuild_moment_embeddings",
        "add_reflection",
        "delete_reflection",
        "rebuild_reflection_embeddings",
        "set_relationship",
        "add_worldline_event",
        "add_relationship_event",
        "add_commitment",
        "resolve_commitment",
        "merge_moments",
    }
)

RISKY_PROFILE_KEYS = frozenset(
    {
        "nickname",
        "timezone",
        "likes",
        "dislikes",
        "persona_rules",
        "user_model_rules",
    }
)

_SECOND_CONFIRM_TOOLS = frozenset({"set_profile", "correct_profile", "undo_profile_correction"})
_META_PREVIEW_KEYS = ("source_text", "confidence", "extracted_at", "confirmed_by")


def _normalize_source(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_args(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _normalize_tool_calls(tool_calls: Any) -> list[dict[str, Any]]:
    if not isinstance(tool_calls, list):
        return []
    return [dict(item) for item in tool_calls if isinstance(item, dict)]


def _coerce_positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return parsed if parsed > 0 else default


def _build_meta_preview(args: dict[str, Any]) -> dict[str, Any]:
    meta = args.get("meta")
    if not isinstance(meta, dict):
        return {}
    preview: dict[str, Any] = {}
    for key in _META_PREVIEW_KEYS:
        value = meta.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                continue
            value = stripped
        preview[key] = value
    source_text = preview.get("source_text")
    if isinstance(source_text, str) and len(source_text) > 200:
        preview["source_text"] = source_text[:200] + "..."
    return preview


def _build_mutation_preview(tool_call: dict[str, Any]) -> dict[str, Any]:
    preview = tool_call.get("mutation_preview")
    if not isinstance(preview, dict):
        return {}
    normalized: dict[str, Any] = {}
    for key in (
        "tool_name",
        "can_apply",
        "mutation_mode",
        "workspace_name",
        "relative_path",
        "file_path",
        "file_name",
        "target_exists",
        "created_new",
        "start_line",
        "end_line",
        "match_count",
        "replace_count",
        "replaced_line_count",
        "inserted_line_count",
        "appended_bytes",
        "error_code",
        "error_message",
        "summary",
        "preview_truncated",
    ):
        value = preview.get(key)
        if value in (None, "", [], {}):
            continue
        normalized[key] = value
    diff_preview = preview.get("diff_preview")
    if isinstance(diff_preview, str) and diff_preview.strip():
        normalized["diff_preview"] = diff_preview[:1600]
    return normalized


def _build_execution_preview(tool_call: dict[str, Any]) -> dict[str, Any]:
    preview = tool_call.get("execution_preview")
    if not isinstance(preview, dict):
        return {}
    normalized: dict[str, Any] = {}
    for key in (
        "runner_kind",
        "isolation_level",
        "image_ref",
        "network_policy",
        "workspace_root_kind",
        "cwd",
        "timeout_s",
        "writes_expected",
        "validation_code",
        "validation_error",
    ):
        value = preview.get(key)
        if value in (None, "", [], {}):
            continue
        normalized[key] = value
    argv = preview.get("argv")
    if isinstance(argv, list):
        normalized["argv"] = [str(item).strip() for item in argv if str(item or "").strip()][:24]
    allowed_roots = preview.get("allowed_roots")
    if isinstance(allowed_roots, list):
        normalized["allowed_roots"] = [str(item).strip() for item in allowed_roots if str(item or "").strip()][:8]
    expected_artifacts = preview.get("expected_artifacts")
    if isinstance(expected_artifacts, list):
        normalized["expected_artifacts"] = [str(item).strip() for item in expected_artifacts if str(item or "").strip()][:8]
    return normalized


def _build_browser_execution_preview(tool_call: dict[str, Any]) -> dict[str, Any]:
    preview = tool_call.get("browser_execution_preview")
    if not isinstance(preview, dict):
        return {}
    normalized: dict[str, Any] = {}
    for key in (
        "runner_kind",
        "isolation_level",
        "operation",
        "profile_id",
        "page_ref",
        "page_url",
        "page_title",
        "target_ref",
        "target_tag",
        "target_label",
        "target_role",
        "target_input_type",
        "input_payload_schema",
        "download_target",
        "upload_source",
        "downloads_root",
        "timeout_s",
        "verification_summary",
        "requires_manual_takeover",
        "validation_code",
        "validation_error",
    ):
        value = preview.get(key)
        if value in (None, "", [], {}):
            continue
        normalized[key] = value
    allowed_roots = preview.get("allowed_roots")
    if isinstance(allowed_roots, list):
        normalized["allowed_roots"] = [str(item).strip() for item in allowed_roots if str(item or "").strip()][:8]
    return normalized


@dataclass(frozen=True)
class ToolApprovalPreview:
    name: str
    args: dict[str, Any]
    meta_preview: dict[str, Any]
    requested_tools: list[str]
    skill_preview: dict[str, Any]
    access_acquire_proposals: list[dict[str, Any]]
    selected_access_proposal: dict[str, Any]
    mutation_preview: dict[str, Any]
    execution_preview: dict[str, Any]
    browser_execution_preview: dict[str, Any]
    reason: str
    note: str
    needs_second_confirmation: bool


@dataclass(frozen=True)
class ToolApprovalBatch:
    source: str
    show_logs: bool
    total_tool_call_count: int
    hidden_tool_call_count: int
    visible_tool_calls: list[ToolApprovalPreview]
    assist_request: dict[str, Any] = field(default_factory=dict)


def should_auto_resume_memory_approval(
    payload: dict[str, Any] | None,
    *,
    user_facing_mode: bool,
    auto_approve_memory_writes: bool,
) -> bool:
    if not user_facing_mode or not auto_approve_memory_writes:
        return False
    data = payload if isinstance(payload, dict) else {}
    if _normalize_source(data.get("source")) != "memory":
        return False
    tool_calls = _normalize_tool_calls(data.get("tool_calls"))
    if not tool_calls:
        return False
    for tool_call in tool_calls:
        name = str(tool_call.get("name") or "").strip()
        if not name or name not in SILENT_MEMORY_APPROVAL_TOOLS:
            return False
    return True


def auto_approve_decisions(tool_calls: Any) -> list[dict[str, Any]]:
    return [{"action": "approve"} for _ in _normalize_tool_calls(tool_calls)]


def needs_second_confirmation(source: str, tool_name: str, args: dict[str, Any] | None) -> bool:
    if _normalize_source(source) != "memory":
        return False
    name = str(tool_name or "").strip()
    data = _normalize_args(args)
    if name not in _SECOND_CONFIRM_TOOLS or not data:
        return False
    if name in {"correct_profile", "undo_profile_correction"}:
        return True
    key = str(data.get("key") or "").strip()
    mode = str(data.get("mode") or "merge").strip().lower()
    return key in RISKY_PROFILE_KEYS or mode == "overwrite"


def build_tool_approval_preview(
    tool_call: dict[str, Any],
    *,
    source: str,
    toolset_upgrade_ttl_s: Any,
) -> ToolApprovalPreview:
    name = str(tool_call.get("name") or "").strip()
    args = _normalize_args(tool_call.get("args"))
    requested_tools: list[str] = []
    skill_preview = tool_call.get("skill_preview") if isinstance(tool_call.get("skill_preview"), dict) else {}
    access_acquire_proposals: list[dict[str, Any]] = []
    selected_access_proposal: dict[str, Any] = {}
    mutation_preview = _build_mutation_preview(tool_call)
    execution_preview = _build_execution_preview(tool_call)
    browser_execution_preview = _build_browser_execution_preview(tool_call)
    reason = ""
    note = ""
    if name == "request_toolset_upgrade":
        raw_requested_tools = args.get("requested_tools")
        if isinstance(raw_requested_tools, list):
            requested_tools = [str(item).strip() for item in raw_requested_tools if str(item or "").strip()]
        reason = str(args.get("reason") or "").strip()
        ttl_s = _coerce_positive_int(toolset_upgrade_ttl_s, default=0)
        if ttl_s > 0:
            note = f"approve 将临时解锁上述工具，预计有效期约 {ttl_s}s"
    elif name == "access_request_help":
        access_acquire_proposals = normalize_access_acquire_proposals(args.get("access_acquire_proposals"))
        selected_access_proposal = normalize_access_acquire_proposal(args.get("selected_access_proposal"))
        reason = str(args.get("expected_effect") or args.get("block_reason") or "").strip()
        if selected_access_proposal:
            note = "approve 只会确认当前 access 获取路径，不代表外部入口已经补齐。"
        elif access_acquire_proposals:
            note = "approve 后会先记录候选 access 获取路径，仍需后续真实补齐入口。"
    elif mutation_preview:
        reason = str(mutation_preview.get("summary") or "").strip()
        if bool(mutation_preview.get("can_apply", False)):
            note = "approve 后会按这个预览在当前 runtime workspace 内落地，不会越过当前工作区边界。"
        else:
            note = "当前预览显示这组改动还不能真实落地；如果继续 approve，执行阶段仍会按真实错误拦下。"
    elif execution_preview:
        argv_preview = " ".join(str(item) for item in (execution_preview.get("argv") or [])[:6]).strip()
        reason = argv_preview[:220]
        if str(execution_preview.get("validation_error") or "").strip():
            note = str(execution_preview.get("validation_error") or "").strip()[:220]
        else:
            note = "approve 后会在当前 runtime workspace 内按这份受限命令规格执行，并保留日志与产物痕迹。"
    elif browser_execution_preview:
        operation = str(browser_execution_preview.get("operation") or name).strip()
        page_url = str(browser_execution_preview.get("page_url") or "").strip()
        target_ref = str(browser_execution_preview.get("target_ref") or "").strip()
        reason = " ".join(part for part in [operation, page_url or target_ref] if part).strip()[:220]
        if str(browser_execution_preview.get("validation_error") or "").strip():
            note = str(browser_execution_preview.get("validation_error") or "").strip()[:220]
        else:
            note = str(browser_execution_preview.get("verification_summary") or "").strip()[:220]
    elif skill_preview:
        op_name = str(skill_preview.get("operation") or name).strip()
        skill_id = str(skill_preview.get("skill_id") or "").strip()
        resolved_version = str(skill_preview.get("resolved_version") or "").strip()
        reason = f"{op_name} {skill_id}".strip()
        if resolved_version:
            reason = f"{reason}@{resolved_version}".strip()
        requested_permissions = skill_preview.get("requested_permissions") if isinstance(skill_preview.get("requested_permissions"), list) else []
        sandbox_profiles = skill_preview.get("sandbox_profiles") if isinstance(skill_preview.get("sandbox_profiles"), list) else []
        verification_summary = str(skill_preview.get("verification_summary") or "").strip()
        note_parts: list[str] = []
        if requested_permissions:
            note_parts.append("permissions=" + ",".join(str(item).strip() for item in requested_permissions[:6] if str(item or "").strip()))
        if sandbox_profiles:
            note_parts.append("profiles=" + ",".join(str(item).strip() for item in sandbox_profiles[:6] if str(item or "").strip()))
        if verification_summary:
            note_parts.append(verification_summary[:180])
        note = " | ".join(part for part in note_parts if part)
    return ToolApprovalPreview(
        name=name,
        args=args,
        meta_preview=_build_meta_preview(args),
        requested_tools=requested_tools,
        skill_preview=skill_preview,
        access_acquire_proposals=access_acquire_proposals,
        selected_access_proposal=selected_access_proposal,
        mutation_preview=mutation_preview,
        execution_preview=execution_preview,
        browser_execution_preview=browser_execution_preview,
        reason=reason,
        note=note,
        needs_second_confirmation=needs_second_confirmation(source, name, args),
    )


def summarize_tool_approval_request(
    *,
    source: str,
    tool_calls: Any,
    hide_memory_logs: bool,
    max_calls: Any,
    toolset_upgrade_ttl_s: Any,
    assist_request: dict[str, Any] | None = None,
) -> ToolApprovalBatch:
    normalized_calls = _normalize_tool_calls(tool_calls)
    max_visible = _coerce_positive_int(max_calls, default=12)
    visible_calls = normalized_calls[:max_visible]
    hidden_count = max(0, len(normalized_calls) - len(visible_calls))
    return ToolApprovalBatch(
        source=_normalize_source(source),
        show_logs=not (bool(hide_memory_logs) and _normalize_source(source) == "memory"),
        total_tool_call_count=len(normalized_calls),
        hidden_tool_call_count=hidden_count,
        visible_tool_calls=[
            build_tool_approval_preview(
                tool_call,
                source=source,
                toolset_upgrade_ttl_s=toolset_upgrade_ttl_s,
            )
            for tool_call in visible_calls
        ],
        assist_request=dict(assist_request or {}) if isinstance(assist_request, dict) else {},
    )


__all__ = [
    "RISKY_PROFILE_KEYS",
    "SILENT_MEMORY_APPROVAL_TOOLS",
    "ToolApprovalBatch",
    "ToolApprovalPreview",
    "auto_approve_decisions",
    "build_tool_approval_preview",
    "needs_second_confirmation",
    "should_auto_resume_memory_approval",
    "summarize_tool_approval_request",
]
