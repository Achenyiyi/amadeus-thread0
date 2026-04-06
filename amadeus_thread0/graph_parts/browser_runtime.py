from __future__ import annotations

from typing import Any

BROWSER_READ_TOOL_NAMES = {
    "browser_open_url",
    "browser_follow_link",
    "browser_list_tabs",
    "browser_select_tab",
    "browser_go_back",
    "browser_go_forward",
    "browser_reload",
    "browser_snapshot",
    "browser_capture_page_to_source_ref",
}

BROWSER_MUTATION_TOOL_NAMES = {
    "browser_click",
    "browser_fill",
    "browser_press_key",
    "browser_download_click",
    "browser_upload_file",
    "browser_begin_manual_takeover",
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _clean_text(value: Any, *, limit: int = 220) -> str:
    return str(value or "").strip()[:limit]


def _clean_state_label(value: Any, *, limit: int = 80) -> str:
    return _clean_text(value, limit=limit).lower()


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _clean_text_list(value: Any, *, limit: int = 8, item_limit: int = 320) -> list[str]:
    items = value if isinstance(value, list) else []
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _clean_text(item, limit=item_limit)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= max(1, int(limit)):
            break
    return out


def browser_tool_intent(tool_name: Any) -> str:
    name = _clean_state_label(tool_name)
    if not name.startswith("browser_"):
        return ""
    return f"browser:{name.removeprefix('browser_')}"


def normalize_browser_execution_spec(value: Any) -> dict[str, Any]:
    row = _dict_or_empty(value)
    if not row:
        return {}
    normalized = {
        "operation": _clean_state_label(row.get("operation")),
        "profile_id": _clean_text(row.get("profile_id"), limit=120),
        "page_ref": _clean_text(row.get("page_ref"), limit=64),
        "navigation_url": _clean_text(row.get("navigation_url"), limit=1200),
        "target_ref": _clean_text(row.get("target_ref"), limit=64),
        "input_text": _clean_text(row.get("input_text"), limit=4000),
        "key": _clean_text(row.get("key"), limit=64),
        "upload_source": _clean_text(row.get("upload_source"), limit=520),
        "download_target": _clean_text(row.get("download_target"), limit=520),
        "allowed_roots": _clean_text_list(row.get("allowed_roots"), limit=8, item_limit=320),
        "browser_downloads_root": _clean_text(row.get("browser_downloads_root"), limit=320),
        "timeout_s": max(0, _coerce_int(row.get("timeout_s"), 0)),
        "wait_until": _clean_state_label(row.get("wait_until"), limit=32),
    }
    if any(
        (
            normalized["operation"],
            normalized["profile_id"],
            normalized["page_ref"],
            normalized["navigation_url"],
            normalized["target_ref"],
            normalized["input_text"],
            normalized["key"],
            normalized["upload_source"],
            normalized["download_target"],
            normalized["allowed_roots"],
            normalized["browser_downloads_root"],
            normalized["timeout_s"] > 0,
            normalized["wait_until"],
        )
    ):
        return normalized
    return {}


def normalize_browser_execution_preview(value: Any) -> dict[str, Any]:
    row = _dict_or_empty(value)
    if not row:
        return {}
    normalized = {
        "runner_kind": _clean_state_label(row.get("runner_kind")),
        "isolation_level": _clean_state_label(row.get("isolation_level")),
        "operation": _clean_state_label(row.get("operation")),
        "profile_id": _clean_text(row.get("profile_id"), limit=120),
        "page_ref": _clean_text(row.get("page_ref"), limit=64),
        "page_url": _clean_text(row.get("page_url"), limit=1200),
        "page_title": _clean_text(row.get("page_title"), limit=220),
        "target_ref": _clean_text(row.get("target_ref"), limit=64),
        "target_tag": _clean_state_label(row.get("target_tag"), limit=32),
        "target_label": _clean_text(row.get("target_label"), limit=220),
        "target_role": _clean_state_label(row.get("target_role"), limit=64),
        "target_input_type": _clean_state_label(row.get("target_input_type"), limit=64),
        "input_payload_schema": _clean_state_label(row.get("input_payload_schema"), limit=64),
        "download_target": _clean_text(row.get("download_target"), limit=520),
        "upload_source": _clean_text(row.get("upload_source"), limit=520),
        "allowed_roots": _clean_text_list(row.get("allowed_roots"), limit=8, item_limit=320),
        "downloads_root": _clean_text(row.get("downloads_root"), limit=320),
        "timeout_s": max(0, _coerce_int(row.get("timeout_s"), 0)),
        "verification_summary": _clean_text(row.get("verification_summary"), limit=220),
        "requires_manual_takeover": _coerce_bool(row.get("requires_manual_takeover"), False),
    }
    if any(
        (
            normalized["runner_kind"],
            normalized["isolation_level"],
            normalized["operation"],
            normalized["profile_id"],
            normalized["page_ref"],
            normalized["page_url"],
            normalized["page_title"],
            normalized["target_ref"],
            normalized["target_tag"],
            normalized["target_label"],
            normalized["target_role"],
            normalized["target_input_type"],
            normalized["input_payload_schema"],
            normalized["download_target"],
            normalized["upload_source"],
            normalized["allowed_roots"],
            normalized["downloads_root"],
            normalized["timeout_s"] > 0,
            normalized["verification_summary"],
            normalized["requires_manual_takeover"],
        )
    ):
        return normalized
    return {}


def normalize_browser_execution_result(value: Any) -> dict[str, Any]:
    row = _dict_or_empty(value)
    if not row:
        return {}
    normalized = {
        "run_id": _clean_text(row.get("run_id"), limit=128),
        "status": _clean_state_label(row.get("status"), limit=32),
        "profile_id": _clean_text(row.get("profile_id"), limit=120),
        "page_id": _clean_text(row.get("page_id"), limit=64),
        "tab_id": _clean_text(row.get("tab_id"), limit=64),
        "url": _clean_text(row.get("url"), limit=1200),
        "title": _clean_text(row.get("title"), limit=220),
        "action_kind": _clean_state_label(row.get("action_kind"), limit=64),
        "target_ref": _clean_text(row.get("target_ref"), limit=64),
        "duration_ms": max(0, _coerce_int(row.get("duration_ms"), 0)),
        "active_tab_count": max(0, _coerce_int(row.get("active_tab_count"), 0)),
        "last_action_status": _clean_state_label(row.get("last_action_status"), limit=64),
        "download_path": _clean_text(row.get("download_path"), limit=520),
        "upload_source": _clean_text(row.get("upload_source"), limit=520),
        "error_summary": _clean_text(row.get("error_summary"), limit=220),
        "manual_takeover_required": _coerce_bool(row.get("manual_takeover_required"), False),
        "text_preview": _clean_text(row.get("text_preview"), limit=2400),
        "snapshot_targets": [
            dict(item)
            for item in _list_or_empty(row.get("snapshot_targets"))
            if isinstance(item, dict)
        ][:64],
    }
    if any(
        (
            normalized["run_id"],
            normalized["status"],
            normalized["profile_id"],
            normalized["page_id"],
            normalized["tab_id"],
            normalized["url"],
            normalized["title"],
            normalized["action_kind"],
            normalized["target_ref"],
            normalized["duration_ms"] > 0,
            normalized["active_tab_count"] > 0,
            normalized["last_action_status"],
            normalized["download_path"],
            normalized["upload_source"],
            normalized["error_summary"],
            normalized["manual_takeover_required"],
            normalized["text_preview"],
            normalized["snapshot_targets"],
        )
    ):
        return normalized
    return {}


def normalize_browser_runtime_state(value: Any) -> dict[str, Any]:
    row = _dict_or_empty(value)
    if not row:
        return {}
    normalized = {
        "availability": _clean_state_label(row.get("availability")),
        "profile_root": _clean_text(row.get("profile_root"), limit=320),
        "context_status": _clean_state_label(row.get("context_status")),
        "active_page_id": _clean_text(row.get("active_page_id"), limit=64),
        "active_tab_count": max(0, _coerce_int(row.get("active_tab_count"), 0)),
        "downloads_dir": _clean_text(row.get("downloads_dir"), limit=320),
        "last_action_status": _clean_state_label(row.get("last_action_status"), limit=64),
        "last_run_id": _clean_text(row.get("last_run_id"), limit=128),
        "manual_takeover_required": _coerce_bool(row.get("manual_takeover_required"), False),
        "runner_kind": _clean_state_label(row.get("runner_kind"), limit=80),
        "isolation_level": _clean_state_label(row.get("isolation_level"), limit=80),
    }
    if any(
        (
            normalized["availability"],
            normalized["profile_root"],
            normalized["context_status"],
            normalized["active_page_id"],
            normalized["active_tab_count"] > 0,
            normalized["downloads_dir"],
            normalized["last_action_status"],
            normalized["last_run_id"],
            normalized["manual_takeover_required"],
            normalized["runner_kind"],
            normalized["isolation_level"],
        )
    ):
        return normalized
    return {}


def browser_runtime_state_has_signal(value: Any) -> bool:
    return bool(normalize_browser_runtime_state(value))


def build_browser_runtime_state(
    *,
    profile_root: Any = "",
    downloads_dir: Any = "",
    page_id: Any = "",
    active_tab_count: Any = 0,
    last_action_status: Any = "",
    last_run_id: Any = "",
    manual_takeover_required: Any = False,
    context_status: Any = "",
    availability: Any = "available",
) -> dict[str, Any]:
    return normalize_browser_runtime_state(
        {
            "availability": availability,
            "profile_root": profile_root,
            "context_status": context_status,
            "active_page_id": page_id,
            "active_tab_count": active_tab_count,
            "downloads_dir": downloads_dir,
            "last_action_status": last_action_status,
            "last_run_id": last_run_id,
            "manual_takeover_required": manual_takeover_required,
            "runner_kind": "playwright_persistent_context",
            "isolation_level": "persistent_profile_runtime",
        }
    )


__all__ = [
    "BROWSER_MUTATION_TOOL_NAMES",
    "BROWSER_READ_TOOL_NAMES",
    "browser_runtime_state_has_signal",
    "browser_tool_intent",
    "build_browser_runtime_state",
    "normalize_browser_execution_preview",
    "normalize_browser_execution_result",
    "normalize_browser_execution_spec",
    "normalize_browser_runtime_state",
]
