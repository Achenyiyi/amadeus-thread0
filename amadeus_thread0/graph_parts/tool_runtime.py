from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Any

from langchain_core.tools import BaseTool

from ..config import (
    CLAIM_REQUIRED_TOOLS,
    MEMORY_GUARD_ENABLED,
    MEMORY_GUARD_INJECTION_PATTERNS,
    MEMORY_GUARD_MIN_CONFIDENCE,
    MEMORY_GUARD_PROTECTED_PROFILE_KEYS,
    TOOL_RETRY_MAX,
    TOOL_TIMEOUT_S,
)
from ..memory_store import MemoryStore
from ..utils.source_material_export import normalize_source_ref_exports
from .tool_policies import MEMORY_WRITE_TOOLS


def _build_evidence_from_tool_result(
    *,
    tool_name: str,
    result: Any,
    store: MemoryStore,
) -> list[dict[str, Any]]:
    if tool_name not in CLAIM_REQUIRED_TOOLS:
        return []

    source_ids: list[int] = []
    refs = normalize_source_ref_exports(store.list_source_refs(limit=80))
    if isinstance(result, dict):
        sids = result.get("source_ref_ids")
        if isinstance(sids, list):
            for sid in sids:
                try:
                    value = int(sid)
                except Exception:
                    continue
                if value > 0:
                    source_ids.append(value)

    if not source_ids:
        for item in refs[:8]:
            try:
                sid = int(item.get("id") or 0)
            except Exception:
                sid = 0
            if sid > 0:
                source_ids.append(sid)
        source_ids = source_ids[:3]

    ref_map = {int(item.get("id")): item for item in refs if int(item.get("id") or 0) > 0}
    out: list[dict[str, Any]] = []
    for sid in source_ids:
        ref = ref_map.get(int(sid))
        if not ref:
            continue
        out.append(
            {
                "source_id": int(sid),
                "url": str(ref.get("url") or ""),
                "title": str(ref.get("title") or ""),
                "tool_name": str(tool_name),
                "reliability_score": ref.get("reliability_score"),
                "snippet": str(ref.get("snippet") or ""),
                "query": str(ref.get("query") or ""),
                "span_hint": str(ref.get("span_hint") or ""),
            }
        )
    return out


def _memory_guard_check(tool_name: str, args: dict[str, Any], store: MemoryStore) -> tuple[bool, str]:
    if not MEMORY_GUARD_ENABLED:
        return True, ""
    if tool_name not in MEMORY_WRITE_TOOLS:
        return True, ""

    flat_parts: list[str] = []

    def _walk(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, dict):
            for child in value.values():
                _walk(child)
            return
        if isinstance(value, list):
            for child in value:
                _walk(child)
            return
        flat_parts.append(str(value))

    _walk(args)
    joined = " ".join(flat_parts).lower()
    for pattern in MEMORY_GUARD_INJECTION_PATTERNS:
        if pattern and pattern.lower() in joined:
            store.add_memory_quarantine(
                tool_name=tool_name,
                args=args,
                reason=f"injection_pattern:{pattern}",
                confidence=None,
            )
            return False, f"blocked by memory_guard: injection pattern `{pattern}`"

    if tool_name in {"set_profile", "correct_profile"}:
        key_name = str(args.get("key") or "").strip()
        if key_name in MEMORY_GUARD_PROTECTED_PROFILE_KEYS:
            store.add_memory_quarantine(
                tool_name=tool_name,
                args=args,
                reason=f"protected_profile_key:{key_name}",
                confidence=None,
            )
            return False, f"blocked by memory_guard: protected profile key `{key_name}`"

    conf: float | None = None
    meta = args.get("meta")
    if isinstance(meta, dict):
        raw = meta.get("confidence")
        if raw is not None:
            try:
                conf = float(raw)
            except Exception:
                conf = None
    if conf is not None and conf < float(MEMORY_GUARD_MIN_CONFIDENCE):
        store.add_memory_quarantine(
            tool_name=tool_name,
            args=args,
            reason="low_confidence",
            confidence=conf,
        )
        return False, f"blocked by memory_guard: low confidence ({conf:.2f})"

    return True, ""


def _invoke_tool(tool: BaseTool, args: dict[str, Any]) -> Any:
    retries = max(0, int(TOOL_RETRY_MAX))
    timeout_s = max(1, int(TOOL_TIMEOUT_S))
    last_err: Exception | None = None
    for _ in range(retries + 1):
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(tool.invoke, args)
                return future.result(timeout=timeout_s)
        except FutureTimeout:
            last_err = RuntimeError(f"TIMEOUT: exceeded {timeout_s}s")
        except Exception as exc:
            last_err = exc
    raise RuntimeError(str(last_err) if last_err else "tool invoke failed")
