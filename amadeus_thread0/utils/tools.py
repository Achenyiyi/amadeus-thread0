from __future__ import annotations

import ast
import asyncio
import difflib
import operator as op
import os
import re
import time
import uuid
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

try:
    from langchain_community.tools.arxiv.tool import ArxivQueryRun
    from langchain_community.utilities import ArxivAPIWrapper
except Exception:
    ArxivQueryRun = None  # type: ignore[assignment]
    ArxivAPIWrapper = None  # type: ignore[assignment]

try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
except Exception:
    MultiServerMCPClient = None  # type: ignore[assignment]

from ..config import SOURCE_RELIABILITY_DEFAULT, TOOL_POLICIES, TOOL_RELIABILITY_WEIGHTS
from ..graph_parts.digital_body_runtime import (
    access_proposal_identity,
    derive_digital_body_state,
    derive_session_lifecycle,
    normalize_access_acquire_proposal,
    normalize_access_acquire_proposals,
    prune_resolved_access_hints,
    selected_access_proposal_resolved,
)
from ..memory_store import MemoryStore
from ..runtime.modeling import _normalize_provider, _resolve_api_key
from ..runtime.settings import BASE_DIR, get_settings
from .revision_trace_export import normalize_revision_trace_exports


def _meta(tool_name: str) -> dict[str, Any]:
    return {
        "tool": tool_name,
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "request_id": uuid.uuid4().hex,
    }


def _ok(tool_name: str, data: Any) -> Any:
    """兼容层：把历史的 {ok,data,error,meta} 返回协议改为 LangChain 更常见的“工具直接返回内容”。"""

    _ = tool_name
    return data


def _err(tool_name: str, code: str, message: str, details: Any | None = None) -> Any:
    """兼容层：错误改为抛异常，让宿主把异常作为工具错误返回给模型。"""

    _ = tool_name
    if details is None:
        raise RuntimeError(f"{code}: {message}")
    raise RuntimeError(f"{code}: {message} | details={details}")


@lru_cache(maxsize=1)
def _get_store() -> MemoryStore:
    s = get_settings()
    return MemoryStore(s.memory_db_path)


def reset_tool_runtime_caches() -> None:
    _get_store.cache_clear()


def _tool_reliability(tool_name: str, fallback: float | None = None) -> float:
    try:
        v = TOOL_RELIABILITY_WEIGHTS.get(str(tool_name or "").strip())
        if v is None:
            v = SOURCE_RELIABILITY_DEFAULT if fallback is None else float(fallback)
        return max(0.0, min(1.0, float(v)))
    except Exception:
        return max(0.0, min(1.0, float(SOURCE_RELIABILITY_DEFAULT)))


def _record_ledger(
    *,
    record_type: str,
    namespace: str,
    key_name: str,
    before: Any,
    after: Any,
    reason: str,
    source: str,
) -> None:
    try:
        store = _get_store()
        store.append_memory_ledger(
            record_type=record_type,
            namespace=namespace,
            key_name=key_name,
            before=before,
            after=after,
            reason=reason,
            operator="tool",
            source=source,
        )
    except Exception:
        pass


def _run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        # 兼容“已有事件循环”场景（例如某些嵌入运行环境）
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def _resolve_artifact_path(raw: Any) -> Path | None:
    text = str(raw or "").strip()
    if not text:
        return None
    candidate = Path(text).expanduser()
    attempts: list[Path] = []
    if candidate.is_absolute():
        attempts.append(candidate)
    else:
        attempts.append((Path.cwd() / candidate).resolve())
        attempts.append((BASE_DIR / candidate).resolve())
    for path in attempts:
        try:
            if path.exists():
                return path
        except Exception:
            continue
    return None


def _parse_source_ref_id(raw: Any) -> int:
    text = str(raw or "").strip().lower()
    if not text:
        return 0
    if text.startswith("source_ref:"):
        text = text.split(":", 1)[1].strip()
    try:
        value = int(text)
    except Exception:
        value = 0
    return value if value > 0 else 0


def _resolve_source_ref_surface(*, artifact_ref: Any, artifact_label: Any) -> dict[str, Any]:
    store = _get_store()
    refs = store.list_source_refs(limit=120)
    if not isinstance(refs, list) or not refs:
        return {}

    target_ref = str(artifact_ref or "").strip()
    target_label = str(artifact_label or "").strip()
    target_id = _parse_source_ref_id(target_ref) or _parse_source_ref_id(target_label)
    if target_id > 0:
        for item in refs:
            try:
                if int(item.get("id") or 0) == target_id:
                    return dict(item)
            except Exception:
                continue

    best: dict[str, Any] = {}
    best_score = 0.0
    for item in refs:
        url = str(item.get("url") or "").strip()
        title = str(item.get("title") or "").strip()
        query = str(item.get("query") or "").strip()
        snippet = str(item.get("snippet") or "").strip()
        score = 0.0
        if target_ref:
            if target_ref == url or target_ref == query or target_ref == title:
                score += 1.0
            elif target_ref and target_ref in url:
                score += 0.76
            score += 0.52 * _overlap_score(target_ref, title)
            score += 0.42 * _overlap_score(target_ref, query)
            score += 0.16 * _overlap_score(target_ref, snippet)
        if target_label:
            if target_label == title or target_label == query:
                score += 0.92
            score += 0.56 * _overlap_score(target_label, title)
            score += 0.46 * _overlap_score(target_label, query)
            score += 0.12 * _overlap_score(target_label, snippet)
        if score > best_score:
            best = dict(item)
            best_score = score

    return best if best_score >= 0.22 else {}


def _text_units(text: str) -> set[str]:
    raw = str(text or "").strip().lower()
    if not raw:
        return set()
    units = set(re.findall(r"[a-z0-9_]{2,}", raw))
    for chunk in re.findall(r"[\u4e00-\u9fff]+", raw):
        if len(chunk) == 1:
            units.add(chunk)
            continue
        for i in range(len(chunk) - 1):
            units.add(chunk[i : i + 2])
    return units


def _overlap_score(a: str, b: str) -> float:
    au = _text_units(a)
    bu = _text_units(b)
    if not au or not bu:
        return 0.0
    overlap = len(au & bu)
    denom = max(1, min(len(au), 8))
    return max(0.0, min(1.0, float(overlap) / float(denom)))


def _clean_lower_text(value: Any, *, limit: int = 80) -> str:
    return str(value or "").strip().lower()[:limit]


def _clean_lower_list(value: Any, *, limit: int = 12) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = _clean_lower_text(item, limit=64)
        if text and text not in items:
            items.append(text)
        if len(items) >= max(1, int(limit)):
            break
    return items


def _env_access_override(*names: str) -> str:
    for name in names:
        value = _clean_lower_text(os.getenv(name, ""))
        if value:
            return value
    return ""


def _probe_filesystem_state(path: Path) -> str:
    try:
        candidate = path if path.exists() else path.parent
        if not candidate.exists():
            return "missing"
        if os.access(str(candidate), os.W_OK):
            return "writable"
        if os.access(str(candidate), os.R_OK):
            return "read_only"
        return "unavailable"
    except Exception:
        return "unavailable"


def _summary_from_access_state(access_state: dict[str, Any], before: dict[str, Any]) -> str:
    changed: list[str] = []
    for key in (
        "session_continuity",
        "session_recovery_mode",
        "api_key_state",
        "quota_state",
        "filesystem_state",
        "network_access",
        "sandbox_mode",
    ):
        after_value = str(access_state.get(key) or "").strip().lower()
        before_value = str(before.get(key) or "").strip().lower()
        if after_value and after_value != before_value:
            changed.append(f"{key}={after_value}")
    missing_access = [
        str(item).strip().lower()
        for item in (access_state.get("missing_access") if isinstance(access_state.get("missing_access"), list) else [])
        if str(item or "").strip()
    ]
    session_continuity = str(access_state.get("session_continuity") or "").strip().lower()
    session_recovery_mode = str(access_state.get("session_recovery_mode") or "").strip().lower()
    session_expires_in_s = int(access_state.get("session_expires_in_s") or 0)
    if changed:
        return "已重新检查当前入口状态：" + "，".join(changed[:4]) + "。"
    if session_continuity == "expiring" and session_expires_in_s > 0:
        return (
            f"已重新检查当前会话状态，离过期大约还有 {session_expires_in_s}s，"
            f"当前恢复路径是 {session_recovery_mode or 'refresh_session'}。"
        )
    if missing_access:
        return "已重新检查当前入口状态，暂时还缺 " + "、".join(missing_access[:3]) + "。"
    if session_continuity in {"expired", "missing"}:
        return "已重新检查当前入口状态，这段会话连续性还没有补回来。"
    return "已重新检查当前入口状态，眼下这条路径是稳定的。"


def _slugify_workspace_name(raw: Any, *, fallback: str = "workspace") -> str:
    text = str(raw or "").strip().lower()
    if not text:
        return fallback
    text = re.sub(r"[^a-z0-9._-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-.")
    return text or fallback


def _workspace_preview(path: Path, *, limit: int = 24) -> tuple[str, bool]:
    if not path.exists() or not path.is_dir():
        return "", False
    names: list[str] = []
    try:
        for entry in sorted(path.iterdir(), key=lambda item: item.name.lower()):
            names.append(entry.name)
            if len(names) >= max(1, int(limit)):
                break
    except Exception:
        return "", False
    preview = "\n".join(names)
    truncated = False
    try:
        truncated = sum(1 for _ in path.iterdir()) > len(names)
    except Exception:
        truncated = False
    return preview[:1200], truncated


def _text_preview(text: str, *, limit: int = 1200) -> tuple[str, bool]:
    normalized = str(text or "")
    preview = normalized[: max(1, int(limit))]
    return preview, len(normalized) > len(preview)


def _workspace_artifact_context(path: Path, *, source_tool_name: str = "create_workspace_access") -> dict[str, Any]:
    preview, preview_truncated = _workspace_preview(path)
    try:
        updated_at = int(path.stat().st_mtime)
    except Exception:
        updated_at = 0
    return {
        "carrier": "filesystem",
        "artifact_kind": "workspace",
        "artifact_ref": str(path),
        "artifact_label": path.name,
        "reacquisition_mode": "reattach_workspace",
        "preview": preview,
        "preview_truncated": preview_truncated,
        "exists": path.exists(),
        "size_bytes": 0,
        "updated_at": updated_at,
        "source_ref_ids": [],
        "source_url": "",
        "source_query": "",
        "source_title": path.name,
        "source_tool_name": str(source_tool_name or "").strip() or "create_workspace_access",
    }


def _file_artifact_context(path: Path, *, content: str, source_tool_name: str) -> dict[str, Any]:
    preview, preview_truncated = _text_preview(content, limit=1200)
    try:
        stat = path.stat()
        updated_at = int(stat.st_mtime)
        size_bytes = int(stat.st_size)
    except Exception:
        updated_at = 0
        size_bytes = len(str(content or "").encode("utf-8"))
    return {
        "carrier": "filesystem",
        "artifact_kind": "file",
        "artifact_ref": str(path),
        "artifact_label": path.name,
        "reacquisition_mode": "reopen_file",
        "preview": preview,
        "preview_truncated": preview_truncated,
        "exists": path.exists(),
        "size_bytes": size_bytes,
        "updated_at": updated_at,
        "source_ref_ids": [],
        "source_url": "",
        "source_query": "",
        "source_title": path.name,
        "source_tool_name": source_tool_name,
    }


def _workspace_access_hints(
    *,
    hints: dict[str, Any],
    workspace_path: Path,
    source_tool_name: str = "create_workspace_access",
) -> dict[str, Any]:
    refreshed = dict(hints or {})
    refreshed.update(
        {
            "filesystem_state": "writable",
            "artifact_continuity": "attached",
            "active_artifact_kind": "workspace",
            "active_artifact_ref": str(workspace_path),
            "active_artifact_label": workspace_path.name,
            "artifact_age_s": 0,
            "artifact_reacquisition_mode": "reattach_workspace",
            "artifact_carrier": "filesystem",
            "artifact_source_ref_ids": [],
            "artifact_source_url": "",
            "artifact_source_query": "",
            "artifact_source_title": workspace_path.name,
            "artifact_source_tool_name": str(source_tool_name or "").strip() or "create_workspace_access",
        }
    )
    refreshed.setdefault("world_surfaces", [])
    if isinstance(refreshed.get("world_surfaces"), list):
        surfaces = [str(item).strip().lower() for item in refreshed.get("world_surfaces", []) if str(item or "").strip()]
        if "filesystem" not in surfaces:
            surfaces.append("filesystem")
        refreshed["world_surfaces"] = surfaces[:12]
    refreshed = prune_resolved_access_hints(refreshed)

    selected = normalize_access_acquire_proposal(refreshed.get("selected_access_proposal"))
    proposals = normalize_access_acquire_proposals(refreshed.get("access_acquire_proposals"))
    if selected and selected_access_proposal_resolved(hints=refreshed, proposal=selected):
        refreshed.pop("selected_access_proposal", None)
        refreshed["access_acquire_proposals"] = [
            proposal
            for proposal in proposals
            if access_proposal_identity(proposal) != access_proposal_identity(selected)
        ]
    elif proposals:
        refreshed["access_acquire_proposals"] = proposals
    return refreshed


def _workspace_file_hints(*, hints: dict[str, Any], file_path: Path, source_tool_name: str) -> dict[str, Any]:
    refreshed = dict(hints or {})
    refreshed.update(
        {
            "filesystem_state": "writable",
            "artifact_continuity": "attached",
            "active_artifact_kind": "file",
            "active_artifact_ref": str(file_path),
            "active_artifact_label": file_path.name,
            "artifact_age_s": 0,
            "artifact_reacquisition_mode": "reopen_file",
            "artifact_carrier": "filesystem",
            "artifact_source_ref_ids": [],
            "artifact_source_url": "",
            "artifact_source_query": "",
            "artifact_source_title": file_path.name,
            "artifact_source_tool_name": str(source_tool_name or "").strip() or "write_workspace_file",
            "workspace_path": str(file_path.parent),
        }
    )
    refreshed.setdefault("world_surfaces", [])
    if isinstance(refreshed.get("world_surfaces"), list):
        surfaces = [str(item).strip().lower() for item in refreshed.get("world_surfaces", []) if str(item or "").strip()]
        if "filesystem" not in surfaces:
            surfaces.append("filesystem")
        refreshed["world_surfaces"] = surfaces[:12]
    return prune_resolved_access_hints(refreshed)


def _source_ref_hints(
    *,
    hints: dict[str, Any],
    source_ref: dict[str, Any],
    artifact_kind: str,
) -> dict[str, Any]:
    refreshed = dict(hints or {})
    try:
        source_id = int(source_ref.get("id") or 0)
    except Exception:
        source_id = 0
    title = str(source_ref.get("title") or "").strip() or "saved-source"
    url = str(source_ref.get("url") or "").strip()
    query = str(source_ref.get("query") or "").strip()
    source_tool_name = str(source_ref.get("tool_name") or "").strip() or "source_ref"
    artifact_ref = url or query or (f"source_ref:{source_id}" if source_id > 0 else title)
    related_source_ref_ids: list[int] = [source_id] if source_id > 0 else []
    previous_source_ref_ids = [
        int(item)
        for item in (refreshed.get("artifact_source_ref_ids") if isinstance(refreshed.get("artifact_source_ref_ids"), list) else [])
        if str(item or "").strip().isdigit()
    ]
    previous_title = str(refreshed.get("artifact_source_title") or refreshed.get("active_artifact_label") or "").strip()
    previous_query = str(refreshed.get("artifact_source_query") or "").strip()
    previous_url = str(refreshed.get("artifact_source_url") or refreshed.get("active_artifact_ref") or "").strip()
    previous_preferred_source_ref_id = _parse_source_ref_id(refreshed.get("preferred_source_ref_id"))
    previous_preferred_anchor_reason = str(refreshed.get("preferred_anchor_reason") or "").strip().lower()
    exact_match = bool(
        (url and previous_url and url == previous_url)
        or (query and previous_query and query == previous_query)
        or (title and previous_title and title == previous_title)
    )
    continuity_overlap = max(
        _overlap_score(title, previous_title),
        _overlap_score(query, previous_query),
        _overlap_score(url, previous_url),
    )
    if previous_source_ref_ids and (exact_match or continuity_overlap >= 0.42):
        for previous_id in previous_source_ref_ids:
            if previous_id > 0 and previous_id not in related_source_ref_ids:
                related_source_ref_ids.append(previous_id)
            if len(related_source_ref_ids) >= 4:
                break
    refreshed.update(
        {
            "artifact_continuity": "attached",
            "active_artifact_kind": str(artifact_kind or "page").strip().lower() or "page",
            "active_artifact_ref": artifact_ref,
            "active_artifact_label": title,
            "artifact_age_s": 0,
            "artifact_reacquisition_mode": "inspect_source_ref",
            "artifact_carrier": "source_ref",
            "artifact_source_ref_ids": related_source_ref_ids[:4],
            "artifact_source_url": url,
            "artifact_source_query": query,
            "artifact_source_title": title,
            "artifact_source_tool_name": source_tool_name,
        }
    )
    if previous_preferred_source_ref_id > 0 and previous_preferred_source_ref_id == source_id:
        refreshed["preferred_source_ref_id"] = previous_preferred_source_ref_id
        if previous_preferred_anchor_reason:
            refreshed["preferred_anchor_reason"] = previous_preferred_anchor_reason
    else:
        refreshed.pop("preferred_source_ref_id", None)
        refreshed.pop("preferred_anchor_reason", None)
    refreshed.setdefault("world_surfaces", [])
    if isinstance(refreshed.get("world_surfaces"), list):
        surfaces = [str(item).strip().lower() for item in refreshed.get("world_surfaces", []) if str(item or "").strip()]
        for surface in ("source_ref", "browser"):
            if surface not in surfaces:
                surfaces.append(surface)
        refreshed["world_surfaces"] = surfaces[:12]
    return prune_resolved_access_hints(refreshed)


def _clean_nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0


def _source_ref_anchor_quality(source_ref: dict[str, Any]) -> float:
    row = dict(source_ref or {})
    title = str(row.get("title") or "").strip()
    query = str(row.get("query") or "").strip()
    url = str(row.get("url") or "").strip()
    snippet = str(row.get("snippet") or "").strip()
    tool_name = str(row.get("tool_name") or "").strip()
    try:
        reliability = max(0.0, min(1.0, float(row.get("reliability_score"))))
    except Exception:
        reliability = 0.0
    return max(
        0.0,
        min(
            1.0,
            0.20 * (1.0 if url else 0.0)
            + 0.24 * (1.0 if query else 0.0)
            + 0.14 * min(1.0, len(title) / 72.0)
            + 0.16 * min(1.0, len(snippet) / 320.0)
            + 0.10 * (1.0 if tool_name else 0.0)
            + 0.16 * reliability,
        ),
    )


def _ordered_unique_source_ref_ids(*values: Any, limit: int = 4) -> list[int]:
    ordered: list[int] = []
    for value in values:
        items = value if isinstance(value, list) else [value]
        for item in items:
            source_id = _parse_source_ref_id(item)
            if source_id <= 0 or source_id in ordered:
                continue
            ordered.append(source_id)
            if len(ordered) >= max(2, int(limit)):
                return ordered
    return ordered


def _source_ref_relation_metrics(primary: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    primary_title = str(primary.get("title") or "").strip()
    primary_url = str(primary.get("url") or "").strip()
    primary_query = str(primary.get("query") or "").strip()
    primary_snippet = str(primary.get("snippet") or "").strip()
    baseline_title = str(baseline.get("title") or "").strip()
    baseline_url = str(baseline.get("url") or "").strip()
    baseline_query = str(baseline.get("query") or "").strip()
    baseline_snippet = str(baseline.get("snippet") or "").strip()
    same_url = bool(primary_url and baseline_url and primary_url == baseline_url)
    same_query = bool(primary_query and baseline_query and primary_query == baseline_query)
    title_overlap = _overlap_score(primary_title, baseline_title)
    query_overlap = _overlap_score(primary_query, baseline_query)
    snippet_overlap = _overlap_score(primary_snippet, baseline_snippet)
    overlap_score = max(
        1.0 if same_url or same_query else 0.0,
        title_overlap,
        query_overlap,
        min(1.0, snippet_overlap * 0.72),
    )
    if same_url or same_query:
        relation = "same_thread"
    elif overlap_score >= 0.58:
        relation = "close_followup"
    elif overlap_score >= 0.34:
        relation = "adjacent"
    else:
        relation = "weak_relation"
    return {
        "same_url": same_url,
        "same_query": same_query,
        "title_overlap": title_overlap,
        "query_overlap": query_overlap,
        "snippet_overlap": snippet_overlap,
        "overlap_score": overlap_score,
        "relation": relation,
    }


def _candidate_compare_score(
    *,
    primary: dict[str, Any],
    candidate: dict[str, Any],
    ordinal: int,
) -> float:
    metrics = _source_ref_relation_metrics(primary, candidate)
    closeness = float(metrics.get("overlap_score") or 0.0)
    quality = _source_ref_anchor_quality(candidate)
    primary_ts = _clean_nonnegative_int(primary.get("retrieved_at") or primary.get("created_at"))
    candidate_ts = _clean_nonnegative_int(candidate.get("retrieved_at") or candidate.get("created_at"))
    recency_bonus = 0.0
    if candidate_ts > primary_ts > 0:
        recency_bonus = 1.0
    elif candidate_ts > 0 and primary_ts <= 0:
        recency_bonus = 0.5
    order_bonus = max(0.0, 0.08 - 0.02 * max(0, int(ordinal)))
    return round(0.62 * closeness + 0.24 * quality + 0.08 * recency_bonus + order_bonus, 6)


def _select_comparison_source_from_candidates(
    *,
    primary: dict[str, Any],
    candidate_source_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    best: dict[str, Any] = {}
    best_score = -1.0
    for ordinal, candidate in enumerate(candidate_source_refs):
        row = dict(candidate or {})
        try:
            candidate_id = int(row.get("id") or 0)
        except Exception:
            candidate_id = 0
        try:
            primary_id = int(primary.get("id") or 0)
        except Exception:
            primary_id = 0
        if candidate_id <= 0 or candidate_id == primary_id:
            continue
        score = _candidate_compare_score(primary=primary, candidate=row, ordinal=ordinal)
        if score > best_score:
            best = row
            best_score = score
    return best


def _select_preferred_source_anchor(
    *,
    primary: dict[str, Any],
    baseline: dict[str, Any],
    relation: str,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    primary_row = dict(primary or {})
    baseline_row = dict(baseline or {})
    if not baseline_row:
        return primary_row, baseline_row, "current_material_still_best"

    try:
        primary_id = int(primary_row.get("id") or 0)
    except Exception:
        primary_id = 0
    try:
        baseline_id = int(baseline_row.get("id") or 0)
    except Exception:
        baseline_id = 0

    primary_ts = _clean_nonnegative_int(primary_row.get("retrieved_at") or primary_row.get("created_at"))
    baseline_ts = _clean_nonnegative_int(baseline_row.get("retrieved_at") or baseline_row.get("created_at"))
    primary_quality = _source_ref_anchor_quality(primary_row)
    baseline_quality = _source_ref_anchor_quality(baseline_row)

    if primary_ts > baseline_ts:
        primary_recency = 1.0
        baseline_recency = 0.0
    elif baseline_ts > primary_ts:
        primary_recency = 0.0
        baseline_recency = 1.0
    elif primary_ts > 0 and baseline_ts > 0:
        primary_recency = 0.5
        baseline_recency = 0.5
    else:
        primary_recency = 0.0
        baseline_recency = 0.0

    primary_score = primary_quality + 0.18 * primary_recency
    baseline_score = baseline_quality + 0.18 * baseline_recency
    if relation == "same_thread":
        primary_score += 0.03
    elif relation == "weak_relation":
        primary_score += 0.10

    if relation == "weak_relation":
        return primary_row, baseline_row, "relation_too_weak_to_reanchor"

    if baseline_score > primary_score + 0.08 and baseline_id > 0:
        reason = "baseline_more_current" if baseline_recency > primary_recency else "baseline_more_complete"
        return baseline_row, primary_row, reason

    return primary_row, baseline_row, "current_material_still_best"


def _path_within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except Exception:
        return False


def _normalize_workspace_relative_path(raw: Any) -> Path:
    text = str(raw or "").strip()
    if not text:
        raise ValueError("relative_path is required")
    candidate = Path(text.replace("\\", "/"))
    if candidate.is_absolute():
        raise ValueError("relative_path must stay inside the current workspace")
    parts: list[str] = []
    for part in candidate.parts:
        stripped = str(part or "").strip()
        if not stripped or stripped == ".":
            continue
        if stripped == "..":
            raise ValueError("relative_path cannot escape the current workspace")
        parts.append(stripped)
    if not parts:
        raise ValueError("relative_path is required")
    return Path(*parts)


def _workspace_root_dir() -> Path:
    settings = get_settings()
    root = settings.data_dir / "workspaces"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve_runtime_workspace(
    *,
    hints: dict[str, Any],
    workspace_name: Any = "",
) -> Path | None:
    root = _workspace_root_dir()
    root_resolved = root.resolve(strict=False)
    explicit_name = _slugify_workspace_name(workspace_name, fallback="workspace") if str(workspace_name or "").strip() else ""
    if explicit_name:
        candidate = root / explicit_name
        if candidate.exists() and candidate.is_dir() and _path_within_root(candidate, root_resolved):
            return candidate

    artifact_kind = _clean_lower_text(hints.get("active_artifact_kind"))

    def _workspace_root_from_path(candidate: Path) -> Path | None:
        try:
            relative = candidate.resolve(strict=False).relative_to(root_resolved)
        except Exception:
            return None
        parts = tuple(str(part or "").strip() for part in relative.parts if str(part or "").strip())
        if not parts:
            return None
        workspace_root = (root_resolved / parts[0]).resolve(strict=False)
        if workspace_root.exists() and workspace_root.is_dir() and _path_within_root(workspace_root, root_resolved):
            return workspace_root
        return None

    for raw in (
        hints.get("workspace_path"),
        hints.get("active_artifact_ref"),
    ):
        text = str(raw or "").strip()
        if not text:
            continue
        candidate = Path(text).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved = candidate.resolve(strict=False)
        workspace_root = _workspace_root_from_path(resolved)
        if workspace_root is not None:
            return workspace_root

    settings = get_settings()
    thread_workspace = root / _slugify_workspace_name(settings.thread_id, fallback="workspace")
    if thread_workspace.exists() and thread_workspace.is_dir() and _path_within_root(thread_workspace, root_resolved):
        return thread_workspace

    try:
        children = [item for item in root.iterdir() if item.is_dir()]
    except Exception:
        children = []
    if len(children) == 1 and _path_within_root(children[0], root_resolved):
        return children[0]
    return None


def _langchain_requested_topics(query: str) -> set[str]:
    q = str(query or "").strip().lower()
    topics: set[str] = set()
    if any(tok in q for tok in {"persistence", "持久化", "checkpoint", "checkpointer", "thread"}):
        topics.add("persistence")
    if any(tok in q for tok in {"human-in-the-loop", "human in the loop", "hitl", "人工审批", "人工审核", "人工监督"}):
        topics.add("human_in_the_loop")
    return topics


def _normalize_langchain_docs_query(query: str) -> str:
    q = str(query or "").strip()
    if not q:
        return ""
    q = re.sub(r"请调用\s*search_langchain_docs(?:\s*工具)?", " ", q, flags=re.I)
    q = re.sub(r"请(?:帮我)?(?:查|检索|搜|看一下|看下|查一下)", " ", q)
    q = re.sub(r"(给我|分别|各自|各给我|各给一句|一句结论|一句判断|简洁结论|先给我一句|再补一句)", " ", q)
    q = re.sub(r"[，。！？、,:：；;（）()\"'“”‘’]", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    return q


def _langchain_search_queries(query: str) -> list[str]:
    base = _normalize_langchain_docs_query(query)
    topics = _langchain_requested_topics(base or query)
    queries: list[str] = []
    if "persistence" in topics:
        queries.append("LangGraph persistence checkpointer thread")
    if "human_in_the_loop" in topics:
        queries.append("LangChain human-in-the-loop middleware tool call approval interrupt")
    if not queries:
        queries.append(base or str(query or "").strip())
    return list(dict.fromkeys([q for q in queries if q]))


def _score_langchain_doc_item(item: dict[str, str], *, query: str, topics: set[str]) -> float:
    title = str(item.get("title") or "").strip()
    url = str(item.get("url") or "").strip().lower()
    snippet = str(item.get("snippet") or "").strip()
    score = 0.10
    score += 0.32 * _overlap_score(query, title)
    score += 0.28 * _overlap_score(query, snippet)
    if "/oss/python/" in url:
        score += 0.08
    elif "/oss/javascript/" in url:
        score += 0.02

    if "persistence" in topics:
        if "/langgraph/persistence" in url:
            score += 0.40
        elif "persistence" in title.lower():
            score += 0.26
        elif any(tok in url for tok in {"/langgraph/overview", "/releases/", "/contributing/", "/cli", "/test"}):
            score -= 0.18
    if "human_in_the_loop" in topics:
        if "/human-in-the-loop" in url:
            score += 0.40
        elif "human-in-the-loop" in title.lower():
            score += 0.26
        elif any(tok in url for tok in {"/middleware/built-in", "/guardrails"}):
            score += 0.08
        elif any(tok in url for tok in {"/langgraph/overview", "/releases/", "/contributing/", "/cli", "/test"}):
            score -= 0.12

    if any(tok in url for tok in {"/overview", "/releases/", "/contributing/code", "/langsmith/cli", "/test"}):
        score -= 0.10
    return score


def _rerank_langchain_doc_items(items: list[dict[str, str]], *, query: str, k: int) -> list[dict[str, str]]:
    topics = _langchain_requested_topics(query)
    dedup: dict[str, dict[str, str]] = {}
    for item in items:
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        prev = dedup.get(url)
        if prev is None or len(str(item.get("snippet") or "")) > len(str(prev.get("snippet") or "")):
            dedup[url] = dict(item)

    scored: list[tuple[float, dict[str, str]]] = []
    for item in dedup.values():
        scored.append((_score_langchain_doc_item(item, query=query, topics=topics), item))
    scored.sort(key=lambda row: row[0], reverse=True)

    if not topics:
        return [item for _, item in scored[:k]]

    selected: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    def _pick_topic(topic: str, matchers: set[str]) -> None:
        for _, item in scored:
            url = str(item.get("url") or "").strip()
            if not url or url in seen_urls:
                continue
            hay = f"{item.get('title') or ''} {url} {item.get('snippet') or ''}".lower()
            if any(m in hay for m in matchers):
                selected.append(item)
                seen_urls.add(url)
                return

    if "persistence" in topics:
        _pick_topic("persistence", {"persistence", "checkpointer", "thread"})
    if "human_in_the_loop" in topics:
        _pick_topic("human_in_the_loop", {"human-in-the-loop", "hitl", "interrupt", "approval"})

    for _, item in scored:
        url = str(item.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        selected.append(item)
        seen_urls.add(url)
        if len(selected) >= k:
            break
    return selected[:k]


@tool
def get_memory_snapshot(include_core: bool = False) -> dict[str, Any]:
    """读取记忆快照（只读）。

    - 默认 include_core=False：只返回 moments，避免与系统提示词中已注入的 profile/relationship 重复。
    - include_core=True：返回完整三层（profile/relationship/moments）。
    """

    tool_name = "get_memory_snapshot"
    try:
        store = _get_store()
        snap = store.snapshot()
        if include_core:
            return _ok(tool_name, snap)
        return _ok(tool_name, {"moments": snap.get("moments", [])})
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def search_moments(query: str, limit: int = 5) -> dict[str, Any]:
    """按关键词检索 moments（只读）。"""

    tool_name = "search_moments"
    q = (query or "").strip()
    if not q:
        return _ok(tool_name, [])
    try:
        store = _get_store()
        return _ok(tool_name, store.search_moments(query=q, limit=limit))
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def get_time() -> dict[str, Any]:
    """返回本机当前时间（只读）。"""

    tool_name = "get_time"
    try:
        return _ok(tool_name, {"local_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


_ALLOWED_BINOPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.Mod: op.mod,
}
_ALLOWED_UNARYOPS = {
    ast.UAdd: op.pos,
    ast.USub: op.neg,
}


def _safe_eval_expr(expr: str) -> float:
    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
            return _ALLOWED_BINOPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
            return _ALLOWED_UNARYOPS[type(node.op)](_eval(node.operand))
        raise ValueError("unsupported expression")

    tree = ast.parse(expr, mode="eval")
    return _eval(tree)


@tool
def calc(expression: str) -> dict[str, Any]:
    """安全计算器：支持 + - * / ** % 和括号（只读）。"""

    tool_name = "calc"
    try:
        val = _safe_eval_expr(expression)
        return _ok(tool_name, {"expression": expression, "value": val})
    except ValueError as e:
        return _err(tool_name, "BAD_INPUT", str(e), {"expression": expression})
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def write_diary(text: str) -> dict[str, Any]:
    """把一段文本追加写入本地日记文件（高风险：需要人工审批后才允许执行）。"""

    tool_name = "write_diary"
    try:
        s = get_settings()
        s.data_dir.mkdir(parents=True, exist_ok=True)
        path: Path = s.diary_path
        ts = time.strftime("%Y-%m-%d %H:%M:%S")

        with path.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] {text}\n")

        return _ok(tool_name, {"diary": path.name, "written_at": ts})
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def set_profile(key: str, value: Any, mode: str = "merge", meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """写入/更新 profile 记忆（写操作：需要审批）。

    mode:
    - merge（默认）：对 list/set 型字段做合并去重；其他类型则覆盖
    - overwrite：直接覆盖

    meta（可选）：证据链/来源信息（例如 source_text、confidence、extracted_at）。
    """

    # 轻量 schema：只约束最常见的 key，其他 key 先放行（避免过早把系统写死）
    PROFILE_SCHEMA: dict[str, str] = {
        "nickname": "str",
        "timezone": "str",
        "likes": "list[str]",
        "dislikes": "list[str]",
        "persona_rules": "list[dict]",
        # 从 reflections 回写的“用户模型/长期规律”（用于注入与检索提示）
        "user_model_rules": "list[dict]",
    }

    def _as_list_str(x: Any) -> list[str]:
        if x is None:
            return []
        if isinstance(x, str):
            s = x.strip()
            return [s] if s else []
        if isinstance(x, list):
            out: list[str] = []
            for it in x:
                s = str(it).strip()
                if s:
                    out.append(s)
            return out
        s = str(x).strip()
        return [s] if s else []

    tool_name = "set_profile"
    k = (key or "").strip()
    if not k:
        return _err(tool_name, "BAD_INPUT", "empty key")
    if mode not in {"merge", "overwrite"}:
        return _err(tool_name, "BAD_INPUT", "mode must be merge|overwrite", {"mode": mode})

    # skills 属于独立的“技能库”命名空间，不应写进 profile（避免评测与真实数据脑裂）。
    if k == "skills":
        return _err(tool_name, "BAD_INPUT", "skills must be managed via add_skill/list_skills tools")

    # schema 清洗：只对命中的 key 进行类型约束与轻量归一化
    expected = PROFILE_SCHEMA.get(k)
    if expected == "str":
        if value is None:
            value = ""
        # 归一化：有些抽取/纠错会把单值包成 list（例如 nickname=["B"]），
        # 这里取第一个元素，避免写入 "['B']" 这种脏值。
        if isinstance(value, list):
            if len(value) == 0:
                value = ""
            else:
                value = value[0]
        value = str(value)
    elif expected == "list[str]":
        value = _as_list_str(value)[:50]
    elif expected == "list[dict]":
        if value is None:
            value = []
        if not isinstance(value, list):
            return _err(tool_name, "BAD_INPUT", "persona_rules must be a list", {"key": k})
        # 不强行校验每个 dict 的结构（先留扩展空间），只保证 list 元素可 JSON 序列化
        cleaned: list[Any] = []
        for it in value[:50]:
            cleaned.append(it)
        value = cleaned

    try:
        store = _get_store()
        profile = store.get_profile()
        old_for_ledger = profile.get(k)

        if mode == "overwrite":
            # 治理：likes/dislikes 互斥（overwrite 也要生效；否则会出现“同时喜欢又讨厌同一项”的脏状态）
            if k in {"likes", "dislikes"}:
                other_k = "dislikes" if k == "likes" else "likes"
                other_old = profile.get(other_k)

                # 统一归一化为 list[str]
                new_items = value
                if not isinstance(new_items, list):
                    new_items = _as_list_str(new_items)
                new_items = [str(x).strip() for x in (new_items or []) if str(x).strip()]

                if isinstance(other_old, list) and new_items:
                    other_new = [x for x in other_old if x not in set(new_items)]
                    store.set_profile(other_k, other_new)

            store.set_profile(k, value)
            if isinstance(meta, dict) and meta:
                store.set_profile_meta(k, meta)
            _record_ledger(
                record_type="set_profile",
                namespace="profile",
                key_name=k,
                before=old_for_ledger,
                after=value,
                reason=f"set_profile:{mode}",
                source=tool_name,
            )
            return _ok(
                tool_name,
                {
                    "key": k,
                    "mode": mode,
                    "action": "overwrite",
                    "meta_saved": bool(isinstance(meta, dict) and meta),
                },
            )

        old = profile.get(k)
        # list-like 合并
        if isinstance(old, list) and isinstance(value, list):
            merged = list(dict.fromkeys([*old, *value]))

            # 治理：likes/dislikes 互斥（避免出现“同时喜欢又讨厌同一项”的脏状态）
            if k in {"likes", "dislikes"}:
                other_k = "dislikes" if k == "likes" else "likes"
                other_old = profile.get(other_k)
                if isinstance(other_old, list) and merged:
                    other_new = [x for x in other_old if x not in set(merged)]
                    store.set_profile(other_k, other_new)

            store.set_profile(k, merged)
            if isinstance(meta, dict) and meta:
                store.set_profile_meta(k, meta)
            _record_ledger(
                record_type="set_profile",
                namespace="profile",
                key_name=k,
                before=old_for_ledger,
                after=merged,
                reason=f"set_profile:{mode}",
                source=tool_name,
            )
            return _ok(
                tool_name,
                {
                    "key": k,
                    "mode": mode,
                    "action": "merge_list",
                    "meta_saved": bool(isinstance(meta, dict) and meta),
                },
            )

        # set-like（以 list 形式存储）
        if isinstance(old, list) and isinstance(value, str):
            merged = list(dict.fromkeys([*old, value]))
            store.set_profile(k, merged)
            if isinstance(meta, dict) and meta:
                store.set_profile_meta(k, meta)
            _record_ledger(
                record_type="set_profile",
                namespace="profile",
                key_name=k,
                before=old_for_ledger,
                after=merged,
                reason=f"set_profile:{mode}",
                source=tool_name,
            )
            return _ok(
                tool_name,
                {
                    "key": k,
                    "mode": mode,
                    "action": "merge_item",
                    "meta_saved": bool(isinstance(meta, dict) and meta),
                },
            )

        # 默认覆盖
        # 治理：likes/dislikes 互斥（即使 old 不是 list、或者 value 不是 list，也要清理对侧）。
        if k in {"likes", "dislikes"}:
            other_k = "dislikes" if k == "likes" else "likes"
            other_old = profile.get(other_k)
            new_items = value
            if not isinstance(new_items, list):
                new_items = _as_list_str(new_items)
            new_items = [str(x).strip() for x in (new_items or []) if str(x).strip()]
            if isinstance(other_old, list) and new_items:
                other_new = [x for x in other_old if x not in set(new_items)]
                store.set_profile(other_k, other_new)

        store.set_profile(k, value)
        if isinstance(meta, dict) and meta:
            store.set_profile_meta(k, meta)
        _record_ledger(
            record_type="set_profile",
            namespace="profile",
            key_name=k,
            before=old_for_ledger,
            after=value,
            reason=f"set_profile:{mode}",
            source=tool_name,
        )
        return _ok(
            tool_name,
            {
                "key": k,
                "mode": mode,
                "action": "update",
                "meta_saved": bool(isinstance(meta, dict) and meta),
            },
        )
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def delete_profile(key: str) -> dict[str, Any]:
    """删除 profile 某个键（写操作：需要审批；AgeMem 风格的“遗忘/清理”动作）。"""

    tool_name = "delete_profile"
    k = (key or "").strip()
    if not k:
        return _err(tool_name, "BAD_INPUT", "empty key")
    try:
        store = _get_store()
        old = store.get_profile().get(k)
        ok = store.delete_profile(k)
        if ok:
            _record_ledger(
                record_type="delete_profile",
                namespace="profile",
                key_name=k,
                before=old,
                after=None,
                reason="delete_profile",
                source=tool_name,
            )
        return _ok(tool_name, {"key": k, "deleted": bool(ok)})
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def confirm_profile(key: str, note: str = "") -> dict[str, Any]:
    """确认某个 profile 键当前仍然有效（写操作：需要审批）。

    只更新 profile_meta.last_confirmed_at，不修改值本身。
    """

    tool_name = "confirm_profile"
    k = (key or "").strip()
    if not k:
        return _err(tool_name, "BAD_INPUT", "empty key")
    try:
        store = _get_store()
        now = int(time.time())
        old_meta = store.get_profile_meta().get(k)
        meta: dict[str, Any] = {}
        if isinstance(old_meta, dict):
            meta.update(old_meta)
        meta.update({"last_confirmed_at": now, "confirmed_by": "user", "note": note})
        store.set_profile_meta(k, meta)
        return _ok(tool_name, {"key": k, "confirmed_at": now})
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def correct_profile(key: str, new_value: Any, reason: str = "", source_text: str = "") -> dict[str, Any]:
    """纠正某个 profile 键（写操作：需要审批）。

    用途：给“她记错了/你纠正一下”提供一个统一协议。

    行为：
    - 读取 old_value（若存在）
    - 覆盖写入 new_value
    - 写入 profile_meta：old/new/reason/source_text/时间戳，便于审计与复盘。
    """

    tool_name = "correct_profile"
    k = (key or "").strip()
    if not k:
        return _err(tool_name, "BAD_INPUT", "empty key")

    rsn = (reason or "").strip()
    if not rsn:
        return _err(tool_name, "BAD_INPUT", "reason is required")

    try:
        store = _get_store()
        old = store.get_profile().get(k)
        store.set_profile(k, new_value)
        store.set_profile_meta(
            k,
            {
                "source": "correction",
                "old_value": old,
                "new_value": new_value,
                "reason": rsn,
                "source_text": (source_text or "").strip(),
                "corrected_at": int(time.time()),
                "confirmed_by": "human_approval",
            },
        )
        _record_ledger(
            record_type="correct_profile",
            namespace="profile",
            key_name=k,
            before=old,
            after=new_value,
            reason=rsn,
            source=tool_name,
        )
        return _ok(tool_name, {"key": k, "old_value": old, "new_value": new_value})
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def undo_profile_correction(key: str, reason: str = "") -> dict[str, Any]:
    """撤销一次 profile 纠错（写操作：需要审批）。

    目的：让“错了 -> 纠正 -> 反悔/撤销”也能闭环，避免你只能手工 /set 或改 DB。

    行为：
    - 读取当前 profile_meta[key]，要求其中包含 old_value/new_value（来自 correct_profile 或 CLI 的 user_correction）
    - 将 profile[key] 回滚为 old_value
    - 写入新的 meta 记录（source=undo_correction），保留证据链与时间戳
    """

    tool_name = "undo_profile_correction"
    k = (key or "").strip()
    if not k:
        return _err(tool_name, "BAD_INPUT", "empty key")

    rsn = (reason or "").strip()
    if not rsn:
        return _err(tool_name, "BAD_INPUT", "reason is required")

    try:
        store = _get_store()
        meta_all = store.get_profile_meta() or {}
        meta = meta_all.get(k) if isinstance(meta_all, dict) else None
        if not isinstance(meta, dict):
            return _err(tool_name, "BAD_INPUT", "no meta found for this key")

        if "old_value" not in meta or "new_value" not in meta:
            return _err(tool_name, "BAD_INPUT", "meta missing old_value/new_value; nothing to undo")

        current = store.get_profile().get(k)
        old_value = meta.get("old_value")
        new_value = meta.get("new_value")

        # 尽量防误撤销：如果当前值与 meta.new_value 明显不一致，提示人工先确认。
        if current != new_value:
            return _err(
                tool_name,
                "BAD_INPUT",
                "current value does not match last corrected new_value; refuse to undo automatically",
                {"current": current, "meta_new_value": new_value},
            )

        store.set_profile(k, old_value)
        store.set_profile_meta(
            k,
            {
                "source": "undo_correction",
                "undone_at": int(time.time()),
                "reason": rsn,
                "reverted_from": new_value,
                "reverted_to": old_value,
                "prev_meta": meta,
                "confirmed_by": "human_approval",
            },
        )
        _record_ledger(
            record_type="undo_profile_correction",
            namespace="profile",
            key_name=k,
            before=new_value,
            after=old_value,
            reason=rsn,
            source=tool_name,
        )
        return _ok(tool_name, {"key": k, "reverted_to": old_value})
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def add_moment(summary: str, tags: list[str] | None = None, links: list[int] | None = None) -> dict[str, Any]:
    """新增一条 moment（写操作：需要审批）。

    - tags：用于主题聚合/检索提示（A-MEM 风格）
    - links：关联的 moment id 列表（A-MEM 风格，形成可浏览的记忆网络）

    去重：如果与最近片段重复/高度相似，将返回 ok=false + error.code=SKIPPED。
    """

    tool_name = "add_moment"
    try:
        store = _get_store()
        mid = store.add_moment(summary, tags=tags, links=links)
        _record_ledger(
            record_type="add_moment",
            namespace="moments",
            key_name=str(mid),
            before=None,
            after={"id": int(mid), "summary": summary, "tags": tags or [], "links": links or []},
            reason="add_moment",
            source=tool_name,
        )
        return _ok(tool_name, {"id": mid})
    except ValueError as e:
        # 语义性跳过（比如 duplicate moment）
        return _err(tool_name, "SKIPPED", str(e))
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def delete_moment(moment_id: int) -> dict[str, Any]:
    """删除一条 moment（写操作：需要审批；AgeMem 风格的“遗忘/清理”动作）。"""

    tool_name = "delete_moment"
    try:
        store = _get_store()
        old = None
        for m in store.list_moments(limit=200):
            try:
                if int(m.get("id") or 0) == int(moment_id):
                    old = m
                    break
            except Exception:
                continue
        ok = store.delete_moment(int(moment_id))
        if ok:
            _record_ledger(
                record_type="delete_moment",
                namespace="moments",
                key_name=str(int(moment_id)),
                before=old,
                after=None,
                reason="delete_moment",
                source=tool_name,
            )
        return _ok(tool_name, {"id": int(moment_id), "deleted": bool(ok)})
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def rebuild_moment_embeddings(limit: int = 500) -> dict[str, Any]:
    """为缺少 embedding 的旧 moments 回填向量（写操作：需要审批）。"""

    tool_name = "rebuild_moment_embeddings"
    try:
        store = _get_store()
        n = store.backfill_moment_embeddings(limit=int(limit))
        return _ok(tool_name, {"backfilled": int(n)})
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def list_reflections(limit: int = 20) -> dict[str, Any]:
    """列出最近的 reflections（只读）。"""

    tool_name = "list_reflections"
    try:
        store = _get_store()
        return _ok(tool_name, store.list_reflections(limit=int(limit)))
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def search_reflections(query: str, limit: int = 5) -> dict[str, Any]:
    """语义检索 reflections（只读）。"""

    tool_name = "search_reflections"
    q = (query or "").strip()
    if not q:
        return _ok(tool_name, [])
    try:
        store = _get_store()
        return _ok(tool_name, store.search_reflections(query=q, limit=int(limit)))
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def add_reflection(
    text: str,
    derived_from: list[int] | None = None,
    importance: float | None = None,
) -> dict[str, Any]:
    """新增一条 reflection（写操作：需要审批）。"""

    tool_name = "add_reflection"
    try:
        store = _get_store()
        rid = store.add_reflection(text=text, derived_from=derived_from, importance=importance)
        _record_ledger(
            record_type="add_reflection",
            namespace="reflections",
            key_name=str(rid),
            before=None,
            after={
                "id": int(rid),
                "text": text,
                "derived_from": derived_from or [],
                "importance": importance,
            },
            reason="add_reflection",
            source=tool_name,
        )
        return _ok(tool_name, {"id": int(rid)})
    except ValueError as e:
        return _err(tool_name, "BAD_INPUT", str(e))
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def delete_reflection(reflection_id: int) -> dict[str, Any]:
    """删除一条 reflection（写操作：需要审批）。"""

    tool_name = "delete_reflection"
    try:
        store = _get_store()
        old = None
        for r in store.list_reflections(limit=200):
            try:
                if int(r.get("id") or 0) == int(reflection_id):
                    old = r
                    break
            except Exception:
                continue
        ok = store.delete_reflection(int(reflection_id))
        if ok:
            _record_ledger(
                record_type="delete_reflection",
                namespace="reflections",
                key_name=str(int(reflection_id)),
                before=old,
                after=None,
                reason="delete_reflection",
                source=tool_name,
            )
        return _ok(tool_name, {"id": int(reflection_id), "deleted": bool(ok)})
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def rebuild_reflection_embeddings(limit: int = 500) -> dict[str, Any]:
    """为缺少 embedding 的旧 reflections 回填向量（写操作：需要审批）。"""

    tool_name = "rebuild_reflection_embeddings"
    try:
        store = _get_store()
        n = store.backfill_reflection_embeddings(limit=int(limit))
        return _ok(tool_name, {"backfilled": int(n)})
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def set_relationship(stage: str, notes: str = "") -> dict[str, Any]:
    """更新 relationship（写操作：需要审批；并建议你只在明确同意后批准）。"""

    tool_name = "set_relationship"
    st = (stage or "").strip()
    if not st:
        return _err(tool_name, "BAD_INPUT", "empty stage")
    try:
        store = _get_store()
        old = store.get_relationship()
        store.set_relationship({"stage": st, "notes": notes})
        _record_ledger(
            record_type="set_relationship",
            namespace="relationship",
            key_name="state",
            before=old,
            after={"stage": st, "notes": notes},
            reason="set_relationship",
            source=tool_name,
        )
        return _ok(tool_name, {"stage": st})
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def arxiv_search(query: str, max_results: int = 3) -> dict[str, Any]:
    """检索 arXiv 论文（只读）。

    返回内容包含标题/作者/发布日期/摘要等（由 langchain-community 的 ArxivAPIWrapper 提供）。

    注意：这是联网只读工具；失败时返回 ok=false。
    """

    tool_name = "arxiv_search"
    q = (query or "").strip()
    if not q:
        return _ok(tool_name, "")

    if ArxivAPIWrapper is None or ArxivQueryRun is None:
        return _err(tool_name, "MISSING_DEP", "langchain_community arxiv tool not available")

    try:
        k = int(max_results)
    except Exception:
        k = 3
    k = max(1, min(10, k))

    text = ""
    refs: list[dict[str, str]] = []

    # Preferred path: use arxiv package for structured records.
    try:
        import arxiv  # type: ignore

        search = arxiv.Search(query=q, max_results=k, sort_by=arxiv.SortCriterion.Relevance)
        for r in search.results():
            url = str(getattr(r, "entry_id", "") or getattr(r, "pdf_url", "") or "").strip()
            title = str(getattr(r, "title", "") or "").strip()
            summary = str(getattr(r, "summary", "") or "").strip()
            if not url:
                continue
            refs.append(
                {
                    "title": title,
                    "url": url,
                    "snippet": summary[:500],
                }
            )
        if refs:
            text = "\n\n".join(
                [
                    f"Title: {it['title']}\nLink: {it['url']}\nContent: {it['snippet']}"
                    for it in refs[:k]
                ]
            )
    except Exception:
        pass

    # Fallback path: parse langchain wrapper output.
    if not refs:
        try:
            wrapper = ArxivAPIWrapper(top_k_results=k, ARXIV_MAX_QUERY_LENGTH=300)
            runner = ArxivQueryRun(api_wrapper=wrapper)
            text = str(runner.run(q) or "")
            for block in _extract_title_link_blocks(text):
                if str(block.get("url") or "").strip():
                    refs.append(block)
        except Exception as e:
            return _err(tool_name, "INTERNAL", str(e), {"query": q, "max_results": k})

    try:
        store = _get_store()
        for rec in refs[:k]:
            store.add_source_ref(
                url=str(rec.get("url") or ""),
                title=str(rec.get("title") or ""),
                query=q,
                tool_name=tool_name,
                snippet=str(rec.get("snippet") or ""),
                reliability_score=_tool_reliability(tool_name),
            )
    except Exception:
        pass

    return _ok(tool_name, {"query": q, "max_results": k, "result": text, "items": refs[:k]})


@tool
def merge_moments(moment_ids: list[int], new_summary: str, tags: list[str] | None = None) -> dict[str, Any]:
    """把多条 moments 合并成一条新 moment（写操作：需要审批）。

    - 旧 moments 不删除，只会被标记 superseded_by
    - 新 moment 的 merged_from 记录来源 id
    """

    tool_name = "merge_moments"
    try:
        store = _get_store()
        mid = store.merge_moments(moment_ids=moment_ids, new_summary=new_summary, tags=tags, links=None)
        _record_ledger(
            record_type="merge_moments",
            namespace="moments",
            key_name=str(mid),
            before={"moment_ids": moment_ids},
            after={"new_id": int(mid), "new_summary": new_summary, "tags": tags or []},
            reason="merge_moments",
            source=tool_name,
        )
        return _ok(tool_name, {"new_id": int(mid), "merged_from": moment_ids})
    except ValueError as e:
        return _err(tool_name, "BAD_INPUT", str(e), {"moment_ids": moment_ids})
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def list_skills(limit: int = 20) -> dict[str, Any]:
    """列出技能库（只读）。"""

    tool_name = "list_skills"
    try:
        store = _get_store()
        skills = store.list_skills()
        try:
            lim = int(limit)
        except Exception:
            lim = 20
        lim = max(1, min(50, lim))
        return _ok(tool_name, skills[:lim])
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def add_skill(name: str, description: str, steps: list[str] | None = None) -> dict[str, Any]:
    """新增/更新一个技能（写操作：需要审批）。"""

    tool_name = "add_skill"
    try:
        store = _get_store()
        store.add_skill(name=name, description=description, steps=steps)
        _record_ledger(
            record_type="add_skill",
            namespace="skills",
            key_name=str(name or "").strip(),
            before=None,
            after={"name": name, "description": description, "steps": steps or []},
            reason="add_skill",
            source=tool_name,
        )
        return _ok(tool_name, {"name": name})
    except ValueError as e:
        return _err(tool_name, "BAD_INPUT", str(e))
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def get_worldline_snapshot(limit: int = 20) -> dict[str, Any]:
    """读取世界线相关快照（只读）：worldline / tensions / self narratives / revision traces。"""

    tool_name = "get_worldline_snapshot"
    try:
        lim = max(1, min(100, int(limit)))
        store = _get_store()
        return _ok(
            tool_name,
            {
                "worldline_events": store.list_worldline_events(limit=lim),
                "identity_facts": store.list_identity_facts(limit=lim),
                "shared_events": store.list_shared_events(limit=lim),
                "conflict_repair": store.list_conflict_repairs(limit=lim),
                "relationship_timeline": store.list_relationship_timeline(limit=lim),
                "commitments": store.list_commitments(limit=lim),
                "unresolved_tensions": store.list_unresolved_tensions(limit=lim),
                "semantic_self_narratives": store.list_semantic_self_narratives(limit=lim),
                "revision_traces": normalize_revision_trace_exports(
                    store.list_revision_traces(limit=min(lim, 50))
                ),
                "canon_facts": store.list_canon_facts(),
                "memory_quarantine": store.list_memory_quarantine(limit=min(lim, 50)),
            },
        )
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def add_worldline_event(
    summary: str,
    category: str = "shared_event",
    importance: float = 0.5,
    tags: list[str] | None = None,
    source_refs: list[int] | None = None,
    confidence: float = 0.8,
) -> dict[str, Any]:
    """新增世界线事件（写操作：需要审批）。"""

    tool_name = "add_worldline_event"
    try:
        store = _get_store()
        rec = store.add_worldline_event(
            summary=summary,
            category=category,
            importance=float(importance),
            tags=tags,
            source_refs=source_refs,
            confidence=float(confidence),
        )
        _record_ledger(
            record_type="add_worldline_event",
            namespace="worldline_events",
            key_name=str(rec.get("id") or ""),
            before=None,
            after=rec,
            reason="add_worldline_event",
            source=tool_name,
        )
        return _ok(tool_name, rec)
    except ValueError as e:
        return _err(tool_name, "BAD_INPUT", str(e))
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def add_relationship_event(
    summary: str,
    affinity_delta: float = 0.0,
    trust_delta: float = 0.0,
    confidence: float = 0.8,
    source_refs: list[int] | None = None,
) -> dict[str, Any]:
    """新增关系演化事件（写操作：需要审批）。"""

    tool_name = "add_relationship_event"
    try:
        store = _get_store()
        rec = store.add_relationship_timeline(
            summary=summary,
            affinity_delta=float(affinity_delta),
            trust_delta=float(trust_delta),
            confidence=float(confidence),
            source_refs=source_refs,
        )
        _record_ledger(
            record_type="add_relationship_event",
            namespace="relationship_timeline",
            key_name=str(rec.get("id") or ""),
            before=None,
            after=rec,
            reason="add_relationship_event",
            source=tool_name,
        )
        return _ok(tool_name, rec)
    except ValueError as e:
        return _err(tool_name, "BAD_INPUT", str(e))
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def add_commitment(
    text: str,
    due_at: str = "",
    status: str = "open",
    confidence: float = 0.85,
    source_refs: list[int] | None = None,
) -> dict[str, Any]:
    """新增长期承诺（写操作：需要审批）。"""

    tool_name = "add_commitment"
    try:
        store = _get_store()
        rec = store.add_commitment(
            text=text,
            due_at=due_at,
            status=status,
            confidence=float(confidence),
            source_refs=source_refs,
        )
        _record_ledger(
            record_type="add_commitment",
            namespace="commitments",
            key_name=str(rec.get("id") or ""),
            before=None,
            after=rec,
            reason="add_commitment",
            source=tool_name,
        )
        return _ok(tool_name, rec)
    except ValueError as e:
        return _err(tool_name, "BAD_INPUT", str(e))
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def resolve_commitment(commitment_id: int, resolution: str) -> dict[str, Any]:
    """标记承诺已完成/已解决（写操作：需要审批）。"""

    tool_name = "resolve_commitment"
    try:
        store = _get_store()
        before = None
        for it in store.list_commitments(limit=200):
            try:
                if int(it.get("id") or 0) == int(commitment_id):
                    before = it
                    break
            except Exception:
                continue
        ok = store.resolve_commitment(int(commitment_id), str(resolution or ""))
        if ok:
            after = None
            for it in store.list_commitments(limit=200):
                try:
                    if int(it.get("id") or 0) == int(commitment_id):
                        after = it
                        break
                except Exception:
                    continue
            _record_ledger(
                record_type="resolve_commitment",
                namespace="commitments",
                key_name=str(int(commitment_id)),
                before=before,
                after=after,
                reason="resolve_commitment",
                source=tool_name,
            )
            try:
                store.add_revision_trace(
                    namespace="commitments",
                    target_id=int(commitment_id),
                    before_summary=str((before or {}).get("text") or ""),
                    after_summary=str((after or {}).get("resolution") or ""),
                    reason="resolved",
                    operator="tool",
                    source=tool_name,
                )
            except Exception:
                pass
        return _ok(tool_name, {"id": int(commitment_id), "resolved": bool(ok)})
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def add_unresolved_tension(
    summary: str,
    severity: float = 0.5,
    status: str = "open",
    confidence: float = 0.8,
    source_refs: list[int] | None = None,
) -> dict[str, Any]:
    """记录尚未彻底说开的张力/遗留问题（写操作：需要审批）。"""

    tool_name = "add_unresolved_tension"
    try:
        store = _get_store()
        rec = store.add_unresolved_tension(
            summary=summary,
            severity=float(severity),
            status=status,
            confidence=float(confidence),
            source_refs=source_refs,
        )
        _record_ledger(
            record_type="add_unresolved_tension",
            namespace="unresolved_tensions",
            key_name=str(rec.get("id") or ""),
            before=None,
            after=rec,
            reason="add_unresolved_tension",
            source=tool_name,
        )
        return _ok(tool_name, rec)
    except ValueError as e:
        return _err(tool_name, "BAD_INPUT", str(e))
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def resolve_unresolved_tension(tension_id: int, resolution: str) -> dict[str, Any]:
    """标记某个未解决张力已经说开或处理完成（写操作：需要审批）。"""

    tool_name = "resolve_unresolved_tension"
    try:
        store = _get_store()
        before = None
        for it in store.list_unresolved_tensions(limit=200):
            try:
                if int(it.get("id") or 0) == int(tension_id):
                    before = it
                    break
            except Exception:
                continue
        ok = store.resolve_unresolved_tension(int(tension_id), str(resolution or ""))
        after = None
        if ok:
            for it in store.list_unresolved_tensions(limit=200):
                try:
                    if int(it.get("id") or 0) == int(tension_id):
                        after = it
                        break
                except Exception:
                    continue
            _record_ledger(
                record_type="resolve_unresolved_tension",
                namespace="unresolved_tensions",
                key_name=str(int(tension_id)),
                before=before,
                after=after,
                reason="resolve_unresolved_tension",
                source=tool_name,
            )
            try:
                store.add_revision_trace(
                    namespace="unresolved_tensions",
                    target_id=int(tension_id),
                    before_summary=str((before or {}).get("summary") or ""),
                    after_summary=str((after or {}).get("resolution") or ""),
                    reason="resolved",
                    operator="tool",
                    source=tool_name,
                )
            except Exception:
                pass
        return _ok(tool_name, {"id": int(tension_id), "resolved": bool(ok)})
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def add_semantic_self_narrative(
    text: str,
    category: str = "self_narrative",
    stability: float = 0.6,
    confidence: float = 0.78,
    source_refs: list[int] | None = None,
) -> dict[str, Any]:
    """写入角色长期沉淀出的语义自我叙事（写操作：需要审批）。"""

    tool_name = "add_semantic_self_narrative"
    try:
        store = _get_store()
        rec = store.add_semantic_self_narrative(
            text=text,
            category=category,
            stability=float(stability),
            confidence=float(confidence),
            source_refs=source_refs,
        )
        _record_ledger(
            record_type="add_semantic_self_narrative",
            namespace="semantic_self_narratives",
            key_name=str(rec.get("id") or ""),
            before=None,
            after=rec,
            reason="add_semantic_self_narrative",
            source=tool_name,
        )
        return _ok(tool_name, rec)
    except ValueError as e:
        return _err(tool_name, "BAD_INPUT", str(e))
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def list_revision_traces(limit: int = 20) -> dict[str, Any]:
    """查看最近记忆修订痕迹（只读）。"""

    tool_name = "list_revision_traces"
    try:
        store = _get_store()
        lim = max(1, min(100, int(limit)))
        return _ok(tool_name, normalize_revision_trace_exports(store.list_revision_traces(limit=lim)))
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def list_source_refs(limit: int = 20) -> dict[str, Any]:
    """查看最近外部来源引用（只读）。"""

    tool_name = "list_source_refs"
    try:
        store = _get_store()
        lim = max(1, min(100, int(limit)))
        return _ok(tool_name, store.list_source_refs(limit=lim))
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def inspect_source_ref(
    source_ref_id: int = 0,
    artifact_ref: str = "",
    artifact_label: str = "",
    preview_chars: int = 1200,
    access_hints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """检视已经存入 source_refs 的外部材料（只读）。"""

    tool_name = "inspect_source_ref"
    hints = dict(access_hints) if isinstance(access_hints, dict) else {}
    try:
        if int(source_ref_id or 0) > 0 and not str(artifact_ref or "").strip():
            artifact_ref = f"source_ref:{int(source_ref_id)}"
        rec = _resolve_source_ref_surface(
            artifact_ref=str(artifact_ref or "").strip(),
            artifact_label=str(artifact_label or "").strip(),
        )
        if not rec:
            return _err(
                tool_name,
                "NOT_FOUND",
                "saved source_ref could not be resolved in the current runtime",
                {
                    "source_ref_id": int(source_ref_id or 0),
                    "artifact_ref": str(artifact_ref or "").strip(),
                    "artifact_label": str(artifact_label or "").strip(),
                },
            )

        title = str(rec.get("title") or artifact_label or artifact_ref or "saved-source").strip()
        url = str(rec.get("url") or "").strip()
        query = str(rec.get("query") or "").strip()
        snippet = str(rec.get("snippet") or "").strip()
        artifact_kind = "search_result" if query else "page"
        limit = max(80, min(2400, int(preview_chars or 1200)))
        preview = snippet[:limit]
        preview_truncated = len(snippet) > len(preview)
        refreshed_hints = _source_ref_hints(
            hints=hints,
            source_ref=rec,
            artifact_kind=artifact_kind,
        )
        body = derive_digital_body_state(
            current_event={"kind": "user_utterance", "perception": {"channel": "runtime", "modality": "source_ref"}},
            behavior_queue=[],
            action_packets=[],
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context={"digital_body_hints": refreshed_hints},
            last_external_tools=[],
        )
        access_state = dict(body.get("access_state") or {}) if isinstance(body.get("access_state"), dict) else {}
        resource_state = dict(body.get("resource_state") or {}) if isinstance(body.get("resource_state"), dict) else {}
        try:
            retrieved_at = int(rec.get("retrieved_at") or rec.get("created_at") or 0)
        except Exception:
            retrieved_at = 0
        try:
            resolved_source_id = int(rec.get("id") or 0)
        except Exception:
            resolved_source_id = 0
        artifact_context = {
            "carrier": "source_ref",
            "artifact_kind": artifact_kind,
            "artifact_ref": url or query or str(artifact_ref or f"source_ref:{resolved_source_id}"),
            "artifact_label": title,
            "reacquisition_mode": "inspect_source_ref",
            "preview": preview,
            "preview_truncated": preview_truncated,
            "exists": True,
            "updated_at": retrieved_at,
            "source_ref_ids": [resolved_source_id] if resolved_source_id > 0 else [],
            "source_url": url,
            "source_query": query,
            "source_title": title,
            "source_tool_name": str(rec.get("tool_name") or "").strip() or tool_name,
        }
        summary = f"已查看外部材料 {title}，当前内容已经接回视野。"
        return _ok(
            tool_name,
            {
                "summary": summary,
                "source_ref_id": resolved_source_id,
                "artifact_kind": artifact_kind,
                "artifact_ref": artifact_context["artifact_ref"],
                "artifact_label": title,
                "artifact_preview": preview,
                "artifact_preview_truncated": preview_truncated,
                "artifact_exists": True,
                "artifact_updated_at": retrieved_at,
                "source_ref_ids": [resolved_source_id] if resolved_source_id > 0 else [],
                "source_url": url,
                "source_query": query,
                "access_hints": refreshed_hints,
                "access_state": access_state,
                "resource_state": resource_state,
                "artifact_context": artifact_context,
            },
        )
    except ValueError as e:
        return _err(tool_name, "BAD_INPUT", str(e))
    except Exception as e:
        return _err(
            tool_name,
            "INTERNAL",
            str(e),
            {
                "source_ref_id": int(source_ref_id or 0),
                "artifact_ref": str(artifact_ref or "").strip(),
                "artifact_label": str(artifact_label or "").strip(),
            },
        )


@tool
def compare_source_refs(
    source_ref_id: int = 0,
    compare_source_ref_id: int = 0,
    source_ref_ids: list[int] | None = None,
    artifact_ref: str = "",
    artifact_label: str = "",
    compare_artifact_ref: str = "",
    compare_artifact_label: str = "",
    preview_chars: int = 900,
    access_hints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """对照已经存入 source_refs 的两条外部材料（只读）。"""

    tool_name = "compare_source_refs"
    hints = dict(access_hints) if isinstance(access_hints, dict) else {}
    try:
        if int(source_ref_id or 0) > 0 and not str(artifact_ref or "").strip():
            artifact_ref = f"source_ref:{int(source_ref_id)}"
        primary = _resolve_source_ref_surface(
            artifact_ref=str(artifact_ref or "").strip(),
            artifact_label=str(artifact_label or "").strip(),
        )
        if not primary:
            return _err(
                tool_name,
                "NOT_FOUND",
                "primary saved source_ref could not be resolved in the current runtime",
                {
                    "source_ref_id": int(source_ref_id or 0),
                    "artifact_ref": str(artifact_ref or "").strip(),
                    "artifact_label": str(artifact_label or "").strip(),
                },
            )

        try:
            primary_source_id = int(primary.get("id") or 0)
        except Exception:
            primary_source_id = 0

        candidate_source_ref_ids = _ordered_unique_source_ref_ids(
            primary_source_id,
            source_ref_ids,
            hints.get("artifact_source_ref_ids"),
            limit=4,
        )

        if int(compare_source_ref_id or 0) <= 0 and not any(
            (str(compare_artifact_ref or "").strip(), str(compare_artifact_label or "").strip())
        ):
            candidate_refs = []
            for candidate_id in candidate_source_ref_ids[1:]:
                rec = _resolve_source_ref_surface(artifact_ref=f"source_ref:{candidate_id}", artifact_label="")
                if rec:
                    candidate_refs.append(rec)
            selected_candidate = _select_comparison_source_from_candidates(
                primary=primary,
                candidate_source_refs=candidate_refs,
            )
            try:
                compare_source_ref_id = int(selected_candidate.get("id") or 0)
            except Exception:
                compare_source_ref_id = 0
        if int(compare_source_ref_id or 0) > 0 and not str(compare_artifact_ref or "").strip():
            compare_artifact_ref = f"source_ref:{int(compare_source_ref_id)}"

        baseline = _resolve_source_ref_surface(
            artifact_ref=str(compare_artifact_ref or "").strip(),
            artifact_label=str(compare_artifact_label or "").strip(),
        )
        if not baseline:
            return _err(
                tool_name,
                "NOT_FOUND",
                "comparison saved source_ref could not be resolved in the current runtime",
                {
                    "compare_source_ref_id": int(compare_source_ref_id or 0),
                    "compare_artifact_ref": str(compare_artifact_ref or "").strip(),
                    "compare_artifact_label": str(compare_artifact_label or "").strip(),
                },
            )

        try:
            baseline_source_id = int(baseline.get("id") or 0)
        except Exception:
            baseline_source_id = 0

        primary_title = str(primary.get("title") or artifact_label or artifact_ref or "saved-source").strip()
        primary_url = str(primary.get("url") or "").strip()
        primary_query = str(primary.get("query") or "").strip()
        primary_snippet = str(primary.get("snippet") or "").strip()
        baseline_title = str(baseline.get("title") or compare_artifact_label or compare_artifact_ref or "saved-source").strip()
        baseline_url = str(baseline.get("url") or "").strip()
        baseline_query = str(baseline.get("query") or "").strip()
        baseline_snippet = str(baseline.get("snippet") or "").strip()
        primary_kind = "search_result" if primary_query else "page"
        metrics = _source_ref_relation_metrics(primary, baseline)
        same_url = bool(metrics.get("same_url"))
        same_query = bool(metrics.get("same_query"))
        title_overlap = float(metrics.get("title_overlap") or 0.0)
        query_overlap = float(metrics.get("query_overlap") or 0.0)
        snippet_overlap = float(metrics.get("snippet_overlap") or 0.0)
        overlap_score = float(metrics.get("overlap_score") or 0.0)
        relation = str(metrics.get("relation") or "").strip()
        if same_url or same_query:
            summary = (
                f"已把 {primary_title} 和 {baseline_title} 对照过一遍，它们属于同一条资料线，"
                "当前判断可以直接顺着这条连续性往下走。"
            )
        elif overlap_score >= 0.58:
            summary = (
                f"已把 {primary_title} 和 {baseline_title} 对照过一遍，两条材料是紧邻的延续，"
                "当前判断会优先沿着这条相连线索继续。"
            )
        elif overlap_score >= 0.34:
            summary = (
                f"已把 {primary_title} 和 {baseline_title} 并到一起看过，它们有部分相连的线索，"
                "当前判断会把这段连续性保留下来。"
            )
        else:
            summary = (
                f"已把 {primary_title} 和 {baseline_title} 对照过一遍，但它们关联不强，"
                "后面的判断仍以当前这条材料为主。"
            )

        preferred_source, secondary_source, preferred_anchor_reason = _select_preferred_source_anchor(
            primary=primary,
            baseline=baseline,
            relation=relation,
        )
        try:
            preferred_source_id = int(preferred_source.get("id") or 0)
        except Exception:
            preferred_source_id = 0
        try:
            secondary_source_id = int(secondary_source.get("id") or 0)
        except Exception:
            secondary_source_id = 0
        preferred_title = str(preferred_source.get("title") or primary_title).strip() or primary_title
        preferred_url = str(preferred_source.get("url") or "").strip()
        preferred_query = str(preferred_source.get("query") or "").strip()
        preferred_snippet = str(preferred_source.get("snippet") or "").strip()
        preferred_kind = "search_result" if preferred_query else "page"
        preferred_tool_name = str(preferred_source.get("tool_name") or "").strip() or tool_name
        try:
            preferred_retrieved_at = int(preferred_source.get("retrieved_at") or preferred_source.get("created_at") or 0)
        except Exception:
            preferred_retrieved_at = 0
        if preferred_source_id > 0 and preferred_source_id != primary_source_id and relation != "weak_relation":
            summary = (
                f"已把 {primary_title} 和 {baseline_title} 对照过一遍，当前判断会改为优先沿着 "
                f"{preferred_title} 这条更稳的资料线继续。"
            )

        refreshed_hints = _source_ref_hints(
            hints=hints,
            source_ref=preferred_source,
            artifact_kind=preferred_kind,
        )
        if preferred_source_id > 0:
            refreshed_hints["preferred_source_ref_id"] = preferred_source_id
        if preferred_anchor_reason:
            refreshed_hints["preferred_anchor_reason"] = preferred_anchor_reason
        compared_ids: list[int] = []
        for sid in [preferred_source_id, secondary_source_id, *candidate_source_ref_ids]:
            if sid > 0 and sid not in compared_ids:
                compared_ids.append(sid)
        if compared_ids:
            refreshed_hints["artifact_source_ref_ids"] = compared_ids[:4]

        body = derive_digital_body_state(
            current_event={"kind": "user_utterance", "perception": {"channel": "runtime", "modality": "source_ref"}},
            behavior_queue=[],
            action_packets=[],
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context={"digital_body_hints": refreshed_hints},
            last_external_tools=[],
        )
        access_state = dict(body.get("access_state") or {}) if isinstance(body.get("access_state"), dict) else {}
        resource_state = dict(body.get("resource_state") or {}) if isinstance(body.get("resource_state"), dict) else {}
        limit = max(120, min(2400, int(preview_chars or 900)))
        preview = preferred_snippet[:limit]
        preview_truncated = len(preferred_snippet) > len(preview)
        artifact_context = {
            "carrier": "source_ref",
            "artifact_kind": preferred_kind,
            "artifact_ref": preferred_url or preferred_query or str(artifact_ref or f"source_ref:{preferred_source_id}"),
            "artifact_label": preferred_title,
            "reacquisition_mode": "compare_source_refs",
            "preview": preview,
            "preview_truncated": preview_truncated,
            "exists": True,
            "updated_at": preferred_retrieved_at,
            "source_ref_ids": compared_ids[:4],
            "preferred_source_ref_id": preferred_source_id,
            "preferred_anchor_reason": preferred_anchor_reason,
            "source_url": preferred_url,
            "source_query": preferred_query,
            "source_title": preferred_title,
            "source_tool_name": preferred_tool_name,
        }
        return _ok(
            tool_name,
            {
                "summary": summary,
                "relation": relation,
                "overlap_score": round(max(0.0, min(1.0, overlap_score)), 3),
                "source_ref_id": primary_source_id,
                "compare_source_ref_id": baseline_source_id,
                "source_ref_ids": compared_ids[:4],
                "artifact_kind": preferred_kind,
                "artifact_ref": artifact_context["artifact_ref"],
                "artifact_label": preferred_title,
                "artifact_preview": preview,
                "artifact_preview_truncated": preview_truncated,
                "artifact_exists": True,
                "artifact_updated_at": preferred_retrieved_at,
                "preferred_source_ref_id": preferred_source_id,
                "preferred_source_title": preferred_title,
                "preferred_source_url": preferred_url,
                "preferred_source_query": preferred_query,
                "preferred_anchor_reason": preferred_anchor_reason,
                "source_url": primary_url,
                "source_query": primary_query,
                "access_hints": refreshed_hints,
                "access_state": access_state,
                "resource_state": resource_state,
                "artifact_context": artifact_context,
                "comparison": {
                    "primary_title": primary_title,
                    "primary_url": primary_url,
                    "primary_query": primary_query,
                    "baseline_title": baseline_title,
                    "baseline_url": baseline_url,
                    "baseline_query": baseline_query,
                    "relation": relation,
                    "same_url": same_url,
                    "same_query": same_query,
                    "title_overlap": round(title_overlap, 3),
                    "query_overlap": round(query_overlap, 3),
                    "snippet_overlap": round(snippet_overlap, 3),
                },
            },
        )
    except ValueError as e:
        return _err(tool_name, "BAD_INPUT", str(e))
    except Exception as e:
        return _err(
            tool_name,
            "INTERNAL",
            str(e),
            {
                "source_ref_id": int(source_ref_id or 0),
                "compare_source_ref_id": int(compare_source_ref_id or 0),
                "artifact_ref": str(artifact_ref or "").strip(),
                "compare_artifact_ref": str(compare_artifact_ref or "").strip(),
            },
        )


@tool
def list_memory_ledger(limit: int = 30) -> dict[str, Any]:
    """列出最近记忆变更台账（只读）。"""

    tool_name = "list_memory_ledger"
    try:
        lim = max(1, min(200, int(limit)))
        store = _get_store()
        return _ok(tool_name, store.list_memory_ledger(limit=lim))
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def list_memory_quarantine(limit: int = 30) -> dict[str, Any]:
    """列出隔离区记忆（只读）。"""

    tool_name = "list_memory_quarantine"
    try:
        lim = max(1, min(200, int(limit)))
        store = _get_store()
        return _ok(tool_name, store.list_memory_quarantine(limit=lim))
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@tool
def rollback_memory_change(change_id: int, reason: str = "") -> dict[str, Any]:
    """按记忆台账 ID 回滚变更（写操作：需要审批）。"""

    tool_name = "rollback_memory_change"
    try:
        store = _get_store()
        ok = store.rollback_memory_change(
            int(change_id),
            reason=str(reason or "").strip() or "manual rollback",
            operator="tool",
        )
        return _ok(tool_name, {"id": int(change_id), "rolled_back": bool(ok)})
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e))


@lru_cache(maxsize=1)
def _langchain_docs_mcp_client():
    if MultiServerMCPClient is None:
        raise RuntimeError("MISSING_DEP: langchain_mcp_adapters is not available")
    url = str(os.getenv("AMADEUS_LANGCHAIN_DOCS_MCP_URL", "https://docs.langchain.com/mcp")).strip()
    if not url:
        raise RuntimeError("BAD_INPUT: empty MCP url")
    return MultiServerMCPClient(
        {
            "langchainDocs": {
                "transport": "streamable_http",
                "url": url,
            }
        }
    )


def _extract_title_link_blocks(text: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    if not text:
        return blocks
    parts = re.split(r"\n\s*\n", text)
    for part in parts:
        title = ""
        link = ""
        content = part.strip()
        m_title = re.search(r"Title:\s*(.+)", part)
        m_link = re.search(r"Link:\s*(https?://\S+)", part)
        m_content = re.search(r"Content:\s*(.+)", part, re.DOTALL)
        if m_title:
            title = m_title.group(1).strip()
        if m_link:
            link = m_link.group(1).strip()
        if m_content:
            content = m_content.group(1).strip()
        if title or link or content:
            blocks.append(
                {
                    "title": title,
                    "url": link,
                    "snippet": content[:400],
                }
            )
    return blocks


@tool
def search_langchain_docs(query: str, max_results: int = 3) -> dict[str, Any]:
    """通过 LangChain Docs MCP 检索文档（只读，自动写入 source_refs 追溯）。"""

    tool_name = "search_langchain_docs"
    q = str(query or "").strip()
    if not q:
        return _ok(tool_name, {"query": "", "items": []})

    try:
        k = max(1, min(10, int(max_results)))
    except Exception:
        k = 3

    async def _do_search(search_query: str):
        client = _langchain_docs_mcp_client()
        tools = await client.get_tools(server_name="langchainDocs")
        if not tools:
            raise RuntimeError("MCP_NO_TOOLS: no tools from langchainDocs MCP")
        t = tools[0]
        return await t.ainvoke({"query": search_query})

    try:
        items: list[dict[str, str]] = []
        queries = _langchain_search_queries(q)
        for search_query in queries[:3]:
            raw = _run_async(_do_search(search_query))
            if isinstance(raw, list):
                for it in raw:
                    if isinstance(it, dict) and isinstance(it.get("text"), str):
                        items.extend(_extract_title_link_blocks(it.get("text") or ""))
                    elif isinstance(it, str):
                        items.extend(_extract_title_link_blocks(it))
            elif isinstance(raw, str):
                items.extend(_extract_title_link_blocks(raw))

        if not items:
            return _ok(tool_name, {"query": q, "items": []})

        items = _rerank_langchain_doc_items(items, query=q, k=k)
        source_ref_ids: list[int] = []

        try:
            store = _get_store()
            for rec in items:
                if not rec.get("url"):
                    continue
                saved = store.add_source_ref(
                    url=str(rec.get("url") or ""),
                    title=str(rec.get("title") or ""),
                    query=q,
                    tool_name=tool_name,
                    snippet=str(rec.get("snippet") or ""),
                    reliability_score=_tool_reliability(tool_name),
                    span_hint="langchain_docs_exact" if "/persistence" in str(rec.get("url") or "").lower() or "/human-in-the-loop" in str(rec.get("url") or "").lower() else "",
                )
                try:
                    sid = int(saved.get("id") or 0)
                    if sid > 0:
                        source_ref_ids.append(sid)
                except Exception:
                    pass
        except Exception:
            pass

        return _ok(tool_name, {"query": q, "items": items, "source_ref_ids": source_ref_ids})
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e), {"query": q, "max_results": k})


@tool
def reacquire_artifact(
    mode: str,
    artifact_kind: str = "",
    artifact_ref: str = "",
    artifact_label: str = "",
    preview_chars: int = 900,
) -> dict[str, Any]:
    """在受限只读范围内重新接回当前工作面。

    目前支持两类受限只读重接回：
    - 本地文件 / 文档 / 工作区类 artifact
    - 基于已保存 `source_ref` 的 page / search_result 类 surface

    真正的 live browser session 仍未落地。
    对 browser/search-like surface，目前只允许复用已经存入 `source_refs`
    的 `url/title/query/snippet`，不模拟虚假的在线浏览器状态。
    """

    tool_name = "reacquire_artifact"
    reacquire_mode = str(mode or "").strip().lower()
    kind = str(artifact_kind or "").strip().lower()
    label = str(artifact_label or artifact_ref or "").strip()
    ref = str(artifact_ref or artifact_label or "").strip()
    limit = max(120, min(int(preview_chars or 900), 2400))

    if not reacquire_mode:
        return _err(tool_name, "BAD_INPUT", "mode is required")

    path = _resolve_artifact_path(ref)
    if path is None and reacquire_mode == "reattach_workspace":
        path = _resolve_artifact_path(label)

    if path is not None:
        try:
            stat = path.stat()
            resolved_label = label
            try:
                normalized_label_path = Path(label).expanduser() if label else None
            except Exception:
                normalized_label_path = None
            if (
                not resolved_label
                or resolved_label == ref
                or (normalized_label_path is not None and str(normalized_label_path) == str(path))
            ):
                resolved_label = path.name or str(path)
            if path.is_dir():
                children = sorted(item.name for item in path.iterdir())[:20]
                summary = f"已重新接回工作区 {path.name or str(path)}。"
                return _ok(
                    tool_name,
                    {
                        "summary": summary,
                        "artifact_continuity": "attached",
                        "artifact_kind": kind or "workspace",
                        "artifact_ref": str(path),
                        "artifact_label": resolved_label or path.name or str(path),
                        "artifact_reacquisition_mode": reacquire_mode,
                        "artifact_exists": True,
                        "artifact_preview": "\n".join(children),
                        "artifact_preview_truncated": False,
                        "artifact_size_bytes": int(stat.st_size),
                        "artifact_updated_at": int(stat.st_mtime),
                    },
                )
            content = path.read_text(encoding="utf-8", errors="ignore")
            preview = content[:limit]
            summary = f"已重新接回文件 {path.name}。"
            return _ok(
                tool_name,
                    {
                        "summary": summary,
                        "artifact_continuity": "attached",
                        "artifact_kind": kind or "file",
                        "artifact_ref": str(path),
                        "artifact_label": resolved_label or path.name,
                        "artifact_reacquisition_mode": reacquire_mode,
                        "artifact_exists": True,
                        "artifact_preview": preview,
                    "artifact_preview_truncated": len(content) > len(preview),
                    "artifact_size_bytes": int(stat.st_size),
                    "artifact_updated_at": int(stat.st_mtime),
                },
            )
        except Exception as e:
            return _err(tool_name, "READ_FAILED", str(e), {"artifact_ref": str(path), "mode": reacquire_mode})

    browserish_kinds = {"page", "tab", "site", "browser_page", "search_result"}
    if kind in browserish_kinds or reacquire_mode in {"reopen_page", "rerun_search"}:
        try:
            rec = _resolve_source_ref_surface(artifact_ref=ref, artifact_label=label)
        except Exception as e:
            return _err(
                tool_name,
                "READ_FAILED",
                str(e),
                {"mode": reacquire_mode, "artifact_kind": kind, "artifact_ref": ref, "artifact_label": label},
            )
        if rec:
            url = str(rec.get("url") or "").strip()
            query = str(rec.get("query") or "").strip()
            title = str(rec.get("title") or label or ref).strip()
            snippet = str(rec.get("snippet") or "").strip()
            summary = (
                f"已重新接回检索结果 {title}。"
                if kind == "search_result" or reacquire_mode == "rerun_search"
                else f"已重新接回页面 {title}。"
            )
            return _ok(
                tool_name,
                {
                    "summary": summary,
                    "artifact_continuity": "attached",
                    "artifact_kind": kind or ("search_result" if reacquire_mode == "rerun_search" else "page"),
                    "artifact_ref": url or query or ref,
                    "artifact_label": title or label or ref,
                    "artifact_reacquisition_mode": reacquire_mode,
                    "artifact_exists": True,
                    "artifact_preview": snippet[:limit],
                    "artifact_preview_truncated": len(snippet) > limit,
                    "source_ref_ids": [int(rec.get("id") or 0)] if int(rec.get("id") or 0) > 0 else [],
                    "source_url": url,
                    "source_query": query,
                    "tool_name": str(rec.get("tool_name") or "").strip(),
                },
            )
        return _err(
            tool_name,
            "UNSUPPORTED",
            "browser/search artifact reacquisition needs a saved source_ref carrier in the current runtime",
            {"mode": reacquire_mode, "artifact_kind": kind, "artifact_ref": ref, "artifact_label": label},
        )

    return _err(
        tool_name,
        "NOT_FOUND",
        "artifact path could not be resolved in the current workspace",
        {"mode": reacquire_mode, "artifact_kind": kind, "artifact_ref": ref, "artifact_label": label},
    )


@tool
def refresh_access_state(access_hints: dict[str, Any] | None = None) -> dict[str, Any]:
    """只读刷新当前数字身体的 access/session 入口状态。

    这不是外部登录或真实浏览器操作。
    它只会：
    - 读取当前运行环境里真正可见的局部状态（例如 API key、文件系统可写性）
    - 结合现有 access hints 重新计算 session/access 连续性
    - 返回可写回的最新 hints 与规范化 access_state
    """

    tool_name = "refresh_access_state"
    hints = dict(access_hints) if isinstance(access_hints, dict) else {}
    try:
        settings = get_settings()
        provider = _normalize_provider(settings.model_provider)
        browser_session = _clean_lower_text(hints.get("browser_session"))
        account_state = _clean_lower_text(hints.get("account_state"))
        cookie_state = _clean_lower_text(hints.get("cookie_state"))
        quota_state = _clean_lower_text(hints.get("quota_state"))
        retry_after_s = max(0, int(hints.get("retry_after_s") or 0))
        cooldown_scope = _clean_lower_text(hints.get("cooldown_scope"))
        api_key_state = "present" if _resolve_api_key(provider) else (_clean_lower_text(hints.get("api_key_state")) or "missing")
        filesystem_state = _probe_filesystem_state(settings.data_dir)
        sandbox_mode = _env_access_override("AMADEUS_SANDBOX_MODE") or _clean_lower_text(hints.get("sandbox_mode")) or "open"
        network_access = (
            _env_access_override("AMADEUS_NETWORK_ACCESS", "AMADEUS_NETWORK_ACCESS_STATE")
            or _clean_lower_text(hints.get("network_access"))
            or "enabled"
        )
        session_lifecycle = derive_session_lifecycle(
            browser_session=browser_session,
            account_state=account_state,
            cookie_state=cookie_state,
            session_continuity=hints.get("session_continuity"),
            session_expires_in_s=hints.get("session_expires_in_s"),
            session_recovery_mode=hints.get("session_recovery_mode"),
        )
        refreshed_hints = {
            **hints,
            "browser_session": browser_session,
            "account_state": account_state,
            "cookie_state": cookie_state,
            "api_key_state": api_key_state,
            "quota_state": quota_state,
            "retry_after_s": retry_after_s,
            "cooldown_scope": cooldown_scope,
            "filesystem_state": filesystem_state,
            "sandbox_mode": sandbox_mode,
            "network_access": network_access,
            "session_continuity": str(session_lifecycle.get("session_continuity") or "").strip().lower(),
            "session_expires_in_s": int(session_lifecycle.get("session_expires_in_s") or 0),
            "session_recovery_mode": str(session_lifecycle.get("session_recovery_mode") or "").strip().lower(),
            "missing_access": _clean_lower_list(hints.get("missing_access"), limit=12),
            "requestable_access": _clean_lower_list(hints.get("requestable_access"), limit=12),
            "constraints": _clean_lower_list(hints.get("constraints"), limit=12),
            "world_surfaces": _clean_lower_list(hints.get("world_surfaces"), limit=12),
        }
        body = derive_digital_body_state(
            current_event={"kind": "user_utterance", "perception": {"channel": "runtime", "modality": "state"}},
            behavior_queue=[],
            action_packets=[],
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context={"digital_body_hints": refreshed_hints},
            last_external_tools=[],
        )
        access_state = dict(body.get("access_state") or {}) if isinstance(body.get("access_state"), dict) else {}
        resource_state = dict(body.get("resource_state") or {}) if isinstance(body.get("resource_state"), dict) else {}
        summary = _summary_from_access_state(access_state, hints)
        return _ok(
            tool_name,
            {
                "summary": summary,
                "access_hints": refreshed_hints,
                "access_state": access_state,
                "resource_state": resource_state,
                "browser_session": str(access_state.get("browser_session") or "").strip().lower(),
                "account_state": str(access_state.get("account_state") or "").strip().lower(),
                "cookie_state": str(access_state.get("cookie_state") or "").strip().lower(),
                "api_key_state": str(access_state.get("api_key_state") or "").strip().lower(),
                "quota_state": str(access_state.get("quota_state") or "").strip().lower(),
                "filesystem_state": str(access_state.get("filesystem_state") or "").strip().lower(),
                "sandbox_mode": str(access_state.get("sandbox_mode") or "").strip().lower(),
                "network_access": str(access_state.get("network_access") or "").strip().lower(),
                "session_continuity": str(access_state.get("session_continuity") or "").strip().lower(),
                "session_expires_in_s": int(access_state.get("session_expires_in_s") or 0),
                "session_recovery_mode": str(access_state.get("session_recovery_mode") or "").strip().lower(),
                "missing_access": [
                    str(item).strip().lower()
                    for item in (access_state.get("missing_access") if isinstance(access_state.get("missing_access"), list) else [])
                    if str(item or "").strip()
                ][:12],
                "requestable_access": [
                    str(item).strip().lower()
                    for item in (access_state.get("requestable_access") if isinstance(access_state.get("requestable_access"), list) else [])
                    if str(item or "").strip()
                ][:12],
            },
        )
    except Exception as e:
        return _err(tool_name, "INTERNAL", str(e), {"access_hints": hints})


@tool
def create_workspace_access(
    workspace_name: str = "",
    access_hints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """在当前 runtime 的受控目录里创建一个真实可写工作区。

    约束：
    - 只会在 `AMADEUS_DATA_DIR/workspaces/` 下创建目录
    - 不接受任意绝对路径写入
    - 结果会回写当前 digital-body 的 filesystem / artifact 连续性
    """

    tool_name = "create_workspace_access"
    hints = dict(access_hints) if isinstance(access_hints, dict) else {}
    try:
        settings = get_settings()
        workspace_root = settings.data_dir / "workspaces"
        workspace_root.mkdir(parents=True, exist_ok=True)

        preferred_name = _slugify_workspace_name(
            workspace_name
            or hints.get("workspace_name")
            or hints.get("active_artifact_label")
            or settings.thread_id,
            fallback="workspace",
        )
        workspace_path = workspace_root / preferred_name
        created_new = False
        if workspace_path.exists() and not workspace_path.is_dir():
            return _err(
                tool_name,
                "INVALID_TARGET",
                "workspace target exists but is not a directory",
                {"workspace_path": str(workspace_path)},
            )
        if not workspace_path.exists():
            workspace_path.mkdir(parents=True, exist_ok=True)
            created_new = True

        refreshed_hints = _workspace_access_hints(
            hints=hints,
            workspace_path=workspace_path,
            source_tool_name=tool_name,
        )
        body = derive_digital_body_state(
            current_event={"kind": "user_utterance", "perception": {"channel": "runtime", "modality": "filesystem"}},
            behavior_queue=[],
            action_packets=[],
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context={"digital_body_hints": refreshed_hints},
            last_external_tools=["create_workspace_access"],
        )
        access_state = dict(body.get("access_state") or {}) if isinstance(body.get("access_state"), dict) else {}
        resource_state = dict(body.get("resource_state") or {}) if isinstance(body.get("resource_state"), dict) else {}
        artifact_context = _workspace_artifact_context(workspace_path, source_tool_name=tool_name)
        summary = (
            f"已新建可写工作区 {workspace_path.name}，这条落盘路径现在接上了。"
            if created_new
            else f"已接回可写工作区 {workspace_path.name}，这条落盘路径现在接上了。"
        )
        return _ok(
            tool_name,
            {
                "summary": summary,
                "workspace_path": str(workspace_path),
                "workspace_name": workspace_path.name,
                "workspace_root": str(workspace_root),
                "created_new": created_new,
                "access_hints": refreshed_hints,
                "access_state": access_state,
                "resource_state": resource_state,
                "artifact_context": artifact_context,
                "filesystem_state": str(access_state.get("filesystem_state") or "writable").strip().lower(),
            },
        )
    except Exception as e:
        return _err(
            tool_name,
            "INTERNAL",
            str(e),
            {"workspace_name": workspace_name, "access_hints": hints},
        )


@tool
def inspect_workspace_path(
    relative_path: str = ".",
    workspace_name: str = "",
    access_hints: dict[str, Any] | None = None,
    preview_chars: int = 1200,
) -> dict[str, Any]:
    """在当前 runtime 已挂接的工作区里读取一个受限路径，作为数字身体的只读感知面。"""

    tool_name = "inspect_workspace_path"
    hints = dict(access_hints) if isinstance(access_hints, dict) else {}
    try:
        workspace_path = _resolve_runtime_workspace(hints=hints, workspace_name=workspace_name)
        if workspace_path is None:
            return _err(
                tool_name,
                "WORKSPACE_REQUIRED",
                "no attached runtime workspace is available for inspection",
                {
                    "workspace_name": workspace_name,
                    "active_artifact_kind": hints.get("active_artifact_kind"),
                    "active_artifact_ref": hints.get("active_artifact_ref"),
                },
            )

        raw_relative = str(relative_path or "").strip()
        target_relative = Path() if not raw_relative or raw_relative in {".", "./", ".\\"} else _normalize_workspace_relative_path(raw_relative)
        target_path = (workspace_path / target_relative).resolve(strict=False)
        if not _path_within_root(target_path, workspace_path):
            return _err(
                tool_name,
                "INVALID_TARGET",
                "relative_path escapes the current workspace",
                {"relative_path": str(relative_path), "workspace_path": str(workspace_path)},
            )
        if not target_path.exists():
            return _err(
                tool_name,
                "TARGET_NOT_FOUND",
                "target path does not exist inside the current workspace",
                {"relative_path": str(relative_path), "workspace_path": str(workspace_path)},
            )

        if target_path.is_dir():
            refreshed_hints = _workspace_access_hints(
                hints=hints,
                workspace_path=target_path,
                source_tool_name=tool_name,
            )
            artifact_context = _workspace_artifact_context(target_path, source_tool_name=tool_name)
            artifact_kind = "workspace"
            preview = str(artifact_context.get("preview") or "")
            preview_truncated = bool(artifact_context.get("preview_truncated", False))
            size_bytes = int(artifact_context.get("size_bytes") or 0)
            summary = f"已查看目录 {target_path.name or workspace_path.name}，当前结构已经重新接回工作面。"
        else:
            content = target_path.read_text(encoding="utf-8", errors="ignore")
            preview, preview_truncated = _text_preview(content, limit=max(80, int(preview_chars or 1200)))
            refreshed_hints = _workspace_file_hints(
                hints=hints,
                file_path=target_path,
                source_tool_name=tool_name,
            )
            artifact_context = _file_artifact_context(
                target_path,
                content=content,
                source_tool_name=tool_name,
            )
            artifact_context["preview"] = preview
            artifact_context["preview_truncated"] = preview_truncated
            artifact_kind = "file"
            size_bytes = int(artifact_context.get("size_bytes") or len(content.encode("utf-8")))
            summary = f"已查看文件 {target_path.name}，当前内容已经重新接回工作面。"

        refreshed_hints["filesystem_state"] = _probe_filesystem_state(workspace_path)
        body = derive_digital_body_state(
            current_event={"kind": "user_utterance", "perception": {"channel": "runtime", "modality": "filesystem"}},
            behavior_queue=[],
            action_packets=[],
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context={"digital_body_hints": refreshed_hints},
            last_external_tools=[],
        )
        access_state = dict(body.get("access_state") or {}) if isinstance(body.get("access_state"), dict) else {}
        resource_state = dict(body.get("resource_state") or {}) if isinstance(body.get("resource_state"), dict) else {}
        normalized_relative = "." if target_relative == Path() else str(target_relative).replace("\\", "/")
        return _ok(
            tool_name,
            {
                "summary": summary,
                "workspace_path": str(workspace_path),
                "workspace_name": workspace_path.name,
                "relative_path": normalized_relative,
                "artifact_kind": artifact_kind,
                "artifact_ref": str(target_path),
                "artifact_label": target_path.name or workspace_path.name,
                "artifact_preview": preview,
                "artifact_preview_truncated": preview_truncated,
                "artifact_exists": True,
                "artifact_size_bytes": size_bytes,
                "artifact_updated_at": int(artifact_context.get("updated_at") or 0),
                "access_hints": refreshed_hints,
                "access_state": access_state,
                "resource_state": resource_state,
                "artifact_context": artifact_context,
                "filesystem_state": str(refreshed_hints.get("filesystem_state") or "unavailable").strip().lower(),
            },
        )
    except ValueError as e:
        return _err(
            tool_name,
            "BAD_INPUT",
            str(e),
            {"relative_path": relative_path, "workspace_name": workspace_name},
        )
    except Exception as e:
        return _err(
            tool_name,
            "INTERNAL",
            str(e),
            {"relative_path": relative_path, "workspace_name": workspace_name},
        )


@tool
def write_workspace_file(
    relative_path: str,
    content: str,
    workspace_name: str = "",
    access_hints: dict[str, Any] | None = None,
    overwrite: bool = True,
) -> dict[str, Any]:
    """在当前 runtime 已挂接的工作区里真实写入一个文件。"""

    return _mutate_workspace_file(
        operation="write",
        relative_path=relative_path,
        content=content,
        workspace_name=workspace_name,
        access_hints=access_hints,
        overwrite=overwrite,
    )


def _mutate_workspace_file(
    *,
    operation: str,
    relative_path: str,
    content: str,
    workspace_name: str = "",
    access_hints: dict[str, Any] | None = None,
    overwrite: bool = True,
    ensure_newline: bool = False,
) -> dict[str, Any]:
    """在当前 runtime 已挂接的工作区里真实写入一个文件。

    约束：
    - 只会写到 `AMADEUS_DATA_DIR/workspaces/<workspace>/` 下面
    - `relative_path` 不能是绝对路径，也不能用 `..` 逃逸工作区
    - 若当前 runtime 里没有可解析的工作区，需要先显式创建/接回工作区
    """

    op = str(operation or "").strip().lower()
    if op not in {"write", "append"}:
        raise ValueError(f"unsupported workspace file operation: {operation}")
    tool_name = "append_workspace_file" if op == "append" else "write_workspace_file"
    hints = dict(access_hints) if isinstance(access_hints, dict) else {}
    try:
        workspace_path = _resolve_runtime_workspace(hints=hints, workspace_name=workspace_name)
        if workspace_path is None:
            return _err(
                tool_name,
                "WORKSPACE_REQUIRED",
                "no attached runtime workspace is available for file writes",
                {
                    "workspace_name": workspace_name,
                    "active_artifact_kind": hints.get("active_artifact_kind"),
                    "active_artifact_ref": hints.get("active_artifact_ref"),
                },
            )

        target_relative = _normalize_workspace_relative_path(relative_path)
        target_path = (workspace_path / target_relative).resolve(strict=False)
        if not _path_within_root(target_path, workspace_path):
            return _err(
                tool_name,
                "INVALID_TARGET",
                "relative_path escapes the current workspace",
                {"relative_path": str(relative_path), "workspace_path": str(workspace_path)},
            )

        existed = target_path.exists()
        if existed and target_path.is_dir():
            return _err(
                tool_name,
                "INVALID_TARGET",
                "file target exists but is a directory",
                {"file_path": str(target_path)},
            )
        if existed and not bool(overwrite):
            return _err(
                tool_name,
                "ALREADY_EXISTS",
                "file target already exists and overwrite is disabled",
                {"file_path": str(target_path)},
            )

        target_path.parent.mkdir(parents=True, exist_ok=True)
        normalized_content = str(content or "")
        if op == "append":
            existing_text = target_path.read_text(encoding="utf-8", errors="ignore") if existed else ""
            chunk = normalized_content
            if ensure_newline and existing_text and not existing_text.endswith(("\n", "\r")) and chunk:
                chunk = "\n" + chunk
            target_path.write_text(existing_text + chunk, encoding="utf-8")
            final_content = existing_text + chunk
            bytes_written = len(chunk.encode("utf-8"))
        else:
            target_path.write_text(normalized_content, encoding="utf-8")
            final_content = normalized_content
            bytes_written = len(normalized_content.encode("utf-8"))

        refreshed_hints = _workspace_file_hints(hints=hints, file_path=target_path, source_tool_name=tool_name)
        body = derive_digital_body_state(
            current_event={"kind": "user_utterance", "perception": {"channel": "runtime", "modality": "filesystem"}},
            behavior_queue=[],
            action_packets=[],
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context={"digital_body_hints": refreshed_hints},
            last_external_tools=["write_workspace_file"],
        )
        access_state = dict(body.get("access_state") or {}) if isinstance(body.get("access_state"), dict) else {}
        resource_state = dict(body.get("resource_state") or {}) if isinstance(body.get("resource_state"), dict) else {}
        artifact_context = _file_artifact_context(
            target_path,
            content=final_content,
            source_tool_name=tool_name,
        )
        if op == "append":
            summary = f"已把内容续写进 {target_path.name}，这条文件工作面现在接上了。"
        else:
            summary = f"已把内容写入 {target_path.name}，这条文件工作面现在接上了。"
        return _ok(
            tool_name,
            {
                "summary": summary,
                "workspace_path": str(workspace_path),
                "workspace_name": workspace_path.name,
                "relative_path": str(target_relative).replace("\\", "/"),
                "file_path": str(target_path),
                "file_name": target_path.name,
                "created_new": not existed,
                "bytes_written": bytes_written,
                "access_hints": refreshed_hints,
                "access_state": access_state,
                "resource_state": resource_state,
                "artifact_context": artifact_context,
                "filesystem_state": str(access_state.get("filesystem_state") or "writable").strip().lower(),
            },
        )
    except ValueError as e:
        return _err(
            tool_name,
            "BAD_INPUT",
            str(e),
            {"relative_path": relative_path, "workspace_name": workspace_name},
        )
    except Exception as e:
        return _err(
            tool_name,
            "INTERNAL",
            str(e),
            {"relative_path": relative_path, "workspace_name": workspace_name},
        )


@tool
def append_workspace_file(
    relative_path: str,
    content: str,
    workspace_name: str = "",
    access_hints: dict[str, Any] | None = None,
    ensure_newline: bool = False,
) -> dict[str, Any]:
    """在当前 runtime 已挂接的工作区里真实续写一个文件。"""

    return _mutate_workspace_file(
        operation="append",
        relative_path=relative_path,
        content=content,
        workspace_name=workspace_name,
        access_hints=access_hints,
        ensure_newline=ensure_newline,
    )


@tool
def replace_workspace_text(
    relative_path: str,
    old_text: str,
    new_text: str,
    workspace_name: str = "",
    access_hints: dict[str, Any] | None = None,
    replace_all: bool = False,
) -> dict[str, Any]:
    """在当前 runtime 已挂接的工作区里，对现有文件做一次精确文本替换。"""

    tool_name = "replace_workspace_text"
    hints = dict(access_hints) if isinstance(access_hints, dict) else {}
    try:
        needle = str(old_text or "")
        if not needle:
            raise ValueError("old_text is required")

        workspace_path = _resolve_runtime_workspace(hints=hints, workspace_name=workspace_name)
        if workspace_path is None:
            return _err(
                tool_name,
                "WORKSPACE_REQUIRED",
                "no attached runtime workspace is available for file edits",
                {
                    "workspace_name": workspace_name,
                    "active_artifact_kind": hints.get("active_artifact_kind"),
                    "active_artifact_ref": hints.get("active_artifact_ref"),
                },
            )

        target_relative = _normalize_workspace_relative_path(relative_path)
        target_path = (workspace_path / target_relative).resolve(strict=False)
        if not _path_within_root(target_path, workspace_path):
            return _err(
                tool_name,
                "INVALID_TARGET",
                "relative_path escapes the current workspace",
                {"relative_path": str(relative_path), "workspace_path": str(workspace_path)},
            )
        if not target_path.exists() or not target_path.is_file():
            return _err(
                tool_name,
                "MISSING_TARGET",
                "file target does not exist inside the current workspace",
                {"file_path": str(target_path)},
            )

        original_content = target_path.read_text(encoding="utf-8", errors="ignore")
        match_count = int(original_content.count(needle))
        if match_count <= 0:
            return _err(
                tool_name,
                "TEXT_NOT_FOUND",
                "old_text was not found in the target file",
                {"file_path": str(target_path), "relative_path": str(target_relative).replace("\\", "/")},
            )

        replacement = str(new_text or "")
        replace_count = match_count if bool(replace_all) else 1
        updated_content = original_content.replace(needle, replacement, replace_count)
        target_path.write_text(updated_content, encoding="utf-8")

        refreshed_hints = _workspace_file_hints(hints=hints, file_path=target_path, source_tool_name=tool_name)
        body = derive_digital_body_state(
            current_event={"kind": "user_utterance", "perception": {"channel": "runtime", "modality": "filesystem"}},
            behavior_queue=[],
            action_packets=[],
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context={"digital_body_hints": refreshed_hints},
            last_external_tools=[tool_name],
        )
        access_state = dict(body.get("access_state") or {}) if isinstance(body.get("access_state"), dict) else {}
        resource_state = dict(body.get("resource_state") or {}) if isinstance(body.get("resource_state"), dict) else {}
        artifact_context = _file_artifact_context(
            target_path,
            content=updated_content,
            source_tool_name=tool_name,
        )
        summary = f"已在 {target_path.name} 里精确替换 {replace_count} 处文本，这条文件工作面现在接上了。"
        return _ok(
            tool_name,
            {
                "summary": summary,
                "workspace_path": str(workspace_path),
                "workspace_name": workspace_path.name,
                "relative_path": str(target_relative).replace("\\", "/"),
                "file_path": str(target_path),
                "file_name": target_path.name,
                "replace_all": bool(replace_all),
                "match_count": match_count,
                "replace_count": replace_count,
                "access_hints": refreshed_hints,
                "access_state": access_state,
                "resource_state": resource_state,
                "artifact_context": artifact_context,
                "filesystem_state": str(access_state.get("filesystem_state") or "writable").strip().lower(),
            },
        )
    except ValueError as e:
        return _err(
            tool_name,
            "BAD_INPUT",
            str(e),
            {"relative_path": relative_path, "workspace_name": workspace_name},
        )
    except Exception as e:
        return _err(
            tool_name,
            "INTERNAL",
            str(e),
            {"relative_path": relative_path, "workspace_name": workspace_name},
        )


def _preferred_workspace_newline(text: str) -> str:
    match = re.search(r"\r\n|\n|\r", str(text or ""))
    if match:
        return match.group(0)
    return "\r\n" if os.linesep == "\r\n" else "\n"


def _normalize_workspace_newlines(text: str, newline: str) -> str:
    raw = str(text or "")
    if "\r" not in raw and "\n" not in raw:
        return raw
    return newline.join(raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"))


def _replace_workspace_line_span(
    *,
    content: str,
    start_line: int,
    end_line: int,
    replacement_text: str,
) -> tuple[str, int, int]:
    if start_line <= 0:
        raise ValueError("start_line must be >= 1")
    if end_line < start_line:
        raise ValueError("end_line must be >= start_line")

    lines = str(content or "").splitlines(keepends=True)
    total_lines = len(lines)
    if total_lines <= 0:
        raise ValueError("target file is empty; use write_workspace_file instead")
    if end_line > total_lines:
        raise ValueError(f"line range {start_line}-{end_line} exceeds file length {total_lines}")

    start_idx = sum(len(item) for item in lines[: start_line - 1])
    end_idx = sum(len(item) for item in lines[:end_line])
    newline = _preferred_workspace_newline(content)
    normalized_replacement = _normalize_workspace_newlines(str(replacement_text or ""), newline)
    selected_chunk = str(content or "")[start_idx:end_idx]
    has_following_content = end_idx < len(str(content or ""))
    preserve_trailing_newline = selected_chunk.endswith(("\n", "\r")) and (
        has_following_content or str(content or "").endswith(("\n", "\r"))
    )
    if normalized_replacement and preserve_trailing_newline and not normalized_replacement.endswith(("\n", "\r")):
        normalized_replacement += newline
    updated = f"{str(content or '')[:start_idx]}{normalized_replacement}{str(content or '')[end_idx:]}"
    inserted_line_count = len(str(replacement_text or "").splitlines()) if str(replacement_text or "") else 0
    return updated, end_line - start_line + 1, inserted_line_count


def preview_workspace_mutation(tool_name: str, args: dict[str, Any] | None) -> dict[str, Any]:
    name = str(tool_name or "").strip()
    data = dict(args or {}) if isinstance(args, dict) else {}
    if name not in {
        "write_workspace_file",
        "append_workspace_file",
        "replace_workspace_text",
        "replace_workspace_lines",
    }:
        return {}

    hints = dict(data.get("access_hints") or {}) if isinstance(data.get("access_hints"), dict) else {}
    workspace_name = str(data.get("workspace_name") or "").strip()
    mutation_mode = (
        "append"
        if name == "append_workspace_file"
        else "replace"
        if name in {"replace_workspace_text", "replace_workspace_lines"}
        else "write"
    )

    def _error(code: str, message: str, *, relative_path: str = "", file_path: str = "") -> dict[str, Any]:
        return {
            "tool_name": name,
            "can_apply": False,
            "mutation_mode": mutation_mode,
            "workspace_name": workspace_name,
            "relative_path": relative_path,
            "file_path": file_path,
            "error_code": code,
            "error_message": message[:220],
            "summary": message[:220],
        }

    try:
        workspace_path = _resolve_runtime_workspace(hints=hints, workspace_name=workspace_name)
        if workspace_path is None:
            return _error(
                "WORKSPACE_REQUIRED",
                "当前没有可用的 runtime workspace，预览无法对齐到真实落点。",
            )

        target_relative = _normalize_workspace_relative_path(data.get("relative_path"))
        target_path = (workspace_path / target_relative).resolve(strict=False)
        relative_path = str(target_relative).replace("\\", "/")
        if not _path_within_root(target_path, workspace_path):
            return _error(
                "INVALID_TARGET",
                "relative_path 超出了当前 workspace 边界。",
                relative_path=relative_path,
                file_path=str(target_path),
            )

        existed = target_path.exists()
        if existed and target_path.is_dir():
            return _error(
                "INVALID_TARGET",
                "目标路径当前是目录，不是可编辑文件。",
                relative_path=relative_path,
                file_path=str(target_path),
            )

        original_content = target_path.read_text(encoding="utf-8", errors="ignore") if existed else ""
        updated_content = original_content
        preview_fields: dict[str, Any] = {}

        if name == "write_workspace_file":
            if existed and not bool(data.get("overwrite", True)):
                return _error(
                    "ALREADY_EXISTS",
                    "目标文件已经存在且 overwrite 被关闭。",
                    relative_path=relative_path,
                    file_path=str(target_path),
                )
            updated_content = str(data.get("content") or "")
            preview_fields["created_new"] = not existed
        elif name == "append_workspace_file":
            chunk = str(data.get("content") or "")
            if bool(data.get("ensure_newline")) and original_content and not original_content.endswith(("\n", "\r")) and chunk:
                chunk = "\n" + chunk
            updated_content = original_content + chunk
            preview_fields["created_new"] = not existed
            preview_fields["appended_bytes"] = len(chunk.encode("utf-8"))
        elif name == "replace_workspace_text":
            if not existed or not target_path.is_file():
                return _error(
                    "MISSING_TARGET",
                    "目标文件不存在，无法做文本替换预览。",
                    relative_path=relative_path,
                    file_path=str(target_path),
                )
            needle = str(data.get("old_text") or "")
            if not needle:
                return _error(
                    "BAD_INPUT",
                    "old_text 不能为空。",
                    relative_path=relative_path,
                    file_path=str(target_path),
                )
            match_count = int(original_content.count(needle))
            if match_count <= 0:
                return _error(
                    "TEXT_NOT_FOUND",
                    "old_text 在目标文件里没有命中。",
                    relative_path=relative_path,
                    file_path=str(target_path),
                )
            replace_all = bool(data.get("replace_all"))
            replace_count = match_count if replace_all else 1
            updated_content = original_content.replace(needle, str(data.get("new_text") or ""), replace_count)
            preview_fields["match_count"] = match_count
            preview_fields["replace_count"] = replace_count
        else:
            if not existed or not target_path.is_file():
                return _error(
                    "MISSING_TARGET",
                    "目标文件不存在，无法做按行替换预览。",
                    relative_path=relative_path,
                    file_path=str(target_path),
                )
            updated_content, replaced_line_count, inserted_line_count = _replace_workspace_line_span(
                content=original_content,
                start_line=int(data.get("start_line") or 0),
                end_line=int(data.get("end_line") or 0),
                replacement_text=str(data.get("new_text") or ""),
            )
            preview_fields["start_line"] = int(data.get("start_line") or 0)
            preview_fields["end_line"] = int(data.get("end_line") or 0)
            preview_fields["replaced_line_count"] = replaced_line_count
            preview_fields["inserted_line_count"] = inserted_line_count

        diff_text = "".join(
            difflib.unified_diff(
                original_content.splitlines(keepends=True),
                updated_content.splitlines(keepends=True),
                fromfile=f"a/{relative_path}",
                tofile=f"b/{relative_path}",
                n=3,
            )
        )
        diff_preview, preview_truncated = _text_preview(diff_text or "(no textual diff)", limit=1600)
        summary = (
            f"{target_path.name} 的 patch 预览已生成，审批通过后会只在当前 workspace 内落地。"
            if diff_text
            else f"{target_path.name} 当前不会产生新的文本差异。"
        )
        return {
            "tool_name": name,
            "can_apply": True,
            "mutation_mode": mutation_mode,
            "workspace_name": workspace_path.name,
            "relative_path": relative_path,
            "file_path": str(target_path),
            "file_name": target_path.name,
            "target_exists": existed,
            "summary": summary,
            "diff_preview": diff_preview,
            "preview_truncated": preview_truncated,
            **preview_fields,
        }
    except ValueError as e:
        return _error("BAD_INPUT", str(e))
    except Exception as e:
        return _error("INTERNAL", str(e))


@tool
def replace_workspace_lines(
    relative_path: str,
    start_line: int,
    end_line: int,
    new_text: str,
    workspace_name: str = "",
    access_hints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """在当前 runtime 已挂接的工作区里，对现有文件做一次受限的按行替换。"""

    tool_name = "replace_workspace_lines"
    hints = dict(access_hints) if isinstance(access_hints, dict) else {}
    try:
        start = int(start_line)
        end = int(end_line)
        workspace_path = _resolve_runtime_workspace(hints=hints, workspace_name=workspace_name)
        if workspace_path is None:
            return _err(
                tool_name,
                "WORKSPACE_REQUIRED",
                "no attached runtime workspace is available for file edits",
                {
                    "workspace_name": workspace_name,
                    "active_artifact_kind": hints.get("active_artifact_kind"),
                    "active_artifact_ref": hints.get("active_artifact_ref"),
                },
            )

        target_relative = _normalize_workspace_relative_path(relative_path)
        target_path = (workspace_path / target_relative).resolve(strict=False)
        if not _path_within_root(target_path, workspace_path):
            return _err(
                tool_name,
                "INVALID_TARGET",
                "relative_path escapes the current workspace",
                {"relative_path": str(relative_path), "workspace_path": str(workspace_path)},
            )
        if not target_path.exists() or not target_path.is_file():
            return _err(
                tool_name,
                "MISSING_TARGET",
                "file target does not exist inside the current workspace",
                {"file_path": str(target_path)},
            )

        original_content = target_path.read_text(encoding="utf-8", errors="ignore")
        updated_content, replaced_line_count, inserted_line_count = _replace_workspace_line_span(
            content=original_content,
            start_line=start,
            end_line=end,
            replacement_text=str(new_text or ""),
        )
        target_path.write_text(updated_content, encoding="utf-8")

        refreshed_hints = _workspace_file_hints(hints=hints, file_path=target_path, source_tool_name=tool_name)
        body = derive_digital_body_state(
            current_event={"kind": "user_utterance", "perception": {"channel": "runtime", "modality": "filesystem"}},
            behavior_queue=[],
            action_packets=[],
            toolset_unlocks={},
            autonomy_block_reason="",
            session_context={"digital_body_hints": refreshed_hints},
            last_external_tools=[tool_name],
        )
        access_state = dict(body.get("access_state") or {}) if isinstance(body.get("access_state"), dict) else {}
        resource_state = dict(body.get("resource_state") or {}) if isinstance(body.get("resource_state"), dict) else {}
        artifact_context = _file_artifact_context(
            target_path,
            content=updated_content,
            source_tool_name=tool_name,
        )
        line_span = f"{start}" if start == end else f"{start}-{end}"
        summary = f"已在 {target_path.name} 里替换第 {line_span} 行，这条文件工作面现在接上了。"
        return _ok(
            tool_name,
            {
                "summary": summary,
                "workspace_path": str(workspace_path),
                "workspace_name": workspace_path.name,
                "relative_path": str(target_relative).replace("\\", "/"),
                "file_path": str(target_path),
                "file_name": target_path.name,
                "start_line": start,
                "end_line": end,
                "replaced_line_count": replaced_line_count,
                "inserted_line_count": inserted_line_count,
                "access_hints": refreshed_hints,
                "access_state": access_state,
                "resource_state": resource_state,
                "artifact_context": artifact_context,
                "filesystem_state": str(access_state.get("filesystem_state") or "writable").strip().lower(),
            },
        )
    except ValueError as e:
        return _err(
            tool_name,
            "BAD_INPUT",
            str(e),
            {"relative_path": relative_path, "workspace_name": workspace_name},
        )
    except Exception as e:
        return _err(
            tool_name,
            "INTERNAL",
            str(e),
            {"relative_path": relative_path, "workspace_name": workspace_name},
        )


@tool
def request_toolset_upgrade(requested_tools: list[str] | None = None, reason: str = "") -> dict[str, Any]:
    """向用户申请“升级工具集”（需要人工审批）。

    目的：让“工具=能力体系”，而不是随手乱用外挂。

    必填约束：
    - requested_tools：想要解锁的工具名列表（可空，但强烈建议写）
    - reason：必须写清楚：为什么需要工具、打算怎么用、潜在风险/边界是什么。
      （这样你审批时就能像看科研助理的申请单一样判断。）
    """

    tool_name = "request_toolset_upgrade"
    req = [str(x).strip() for x in (requested_tools or []) if str(x).strip()]
    rsn = (reason or "").strip()
    if not rsn:
        return _err(
            tool_name,
            "BAD_INPUT",
            "reason is required (explain why you need tools, how you'll use them, and risks/boundaries)",
        )

    # requested_tools 必须是已登记在 TOOL_POLICIES 的工具名（白名单），避免“申请不存在工具”导致升级无效/不可审计。
    try:
        from ..config import TOOL_POLICIES

        registered = set(TOOL_POLICIES.keys())
        unknown = [x for x in req if x not in registered]
        if unknown:
            return _err(
                tool_name,
                "BAD_INPUT",
                "requested_tools contains unknown tool names",
                {"unknown": unknown[:20]},
            )
    except Exception:
        # 校验失败不阻断申请（保持鲁棒），但正常情况下不会走到这里。
        pass

    return _ok(tool_name, {"requested_tools": req[:20], "reason": rsn})
