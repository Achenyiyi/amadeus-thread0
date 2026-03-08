from __future__ import annotations

import ast
import asyncio
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

from .config import SOURCE_RELIABILITY_DEFAULT, TOOL_POLICIES, TOOL_RELIABILITY_WEIGHTS
from .memory_store import MemoryStore
from .settings import get_settings


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
                "revision_traces": store.list_revision_traces(limit=min(lim, 50)),
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
        return _ok(tool_name, store.list_revision_traces(limit=lim))
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
        from .config import TOOL_POLICIES

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
