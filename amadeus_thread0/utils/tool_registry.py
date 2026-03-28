from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from langchain_core.tools import BaseTool

from ..config import (
    MCP_CALLS_MAX,
    MCP_ENABLED,
    MCP_SERVER_ALLOWLIST,
    MCP_TIMEOUT_S,
    MCP_TOOL_ALLOWLIST,
    TOOL_POLICIES,
)
from ..runtime.settings import get_settings
from . import tools as builtin_tools

try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
except Exception:
    MultiServerMCPClient = None  # type: ignore[assignment]



def _stable_hash(obj: object) -> str:
    """给审计用：将 server/tool 配置做稳定 hash，避免直接落完整敏感配置。"""

    try:
        raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except Exception:
        raw = str(obj)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _audit_log(event: str, record: dict[str, Any]) -> None:
    try:
        s = get_settings()
        s.data_dir.mkdir(parents=True, exist_ok=True)
        path = s.data_dir / "mcp_audit.jsonl"
        payload = {"ts": int(__import__("time").time()), "event": event, **record}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


@dataclass(frozen=True)
class ToolBundle:
    base_tools: list[BaseTool]
    extended_tools: list[BaseTool]


def _load_registry_config() -> dict[str, Any]:
    """加载工具注册配置（JSON）。

    目的：以后你只需要改配置就能扩展 LangChain integrations/toolkits 或 MCP tools。
    """

    s = get_settings()
    default_path = s.data_dir / "tool_registry.json"
    p = Path(os.getenv("AMADEUS_TOOL_REGISTRY_JSON", str(default_path))).expanduser()

    if not p.exists():
        return {"toolkits": [], "mcp_servers": [], "custom_tools": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"toolkits": [], "mcp_servers": [], "custom_tools": []}


def _iter_builtin_tools() -> Iterable[BaseTool]:
    # 你当前项目里的内建工具：由 @tool 装饰器生成的 StructuredTool
    # 注意：这里只做“发现”，不做风险分级；风险分级由 TOOL_POLICIES 控制。
    return [
        builtin_tools.get_memory_snapshot,
        builtin_tools.search_moments,
        builtin_tools.list_reflections,
        builtin_tools.search_reflections,
        builtin_tools.get_time,
        builtin_tools.calc,
        builtin_tools.arxiv_search,
        builtin_tools.get_worldline_snapshot,
        builtin_tools.list_source_refs,
        builtin_tools.list_memory_ledger,
        builtin_tools.list_memory_quarantine,
        builtin_tools.reacquire_artifact,
        builtin_tools.refresh_access_state,
        builtin_tools.create_workspace_access,
        builtin_tools.inspect_workspace_path,
        builtin_tools.write_workspace_file,
        builtin_tools.append_workspace_file,
        builtin_tools.replace_workspace_text,
        builtin_tools.replace_workspace_lines,
        builtin_tools.search_langchain_docs,
        builtin_tools.list_skills,
        builtin_tools.add_skill,
        builtin_tools.merge_moments,
        builtin_tools.write_diary,
        # memory write
        builtin_tools.set_profile,
        builtin_tools.confirm_profile,
        builtin_tools.correct_profile,
        builtin_tools.undo_profile_correction,
        builtin_tools.delete_profile,
        builtin_tools.add_moment,
        builtin_tools.delete_moment,
        builtin_tools.rebuild_moment_embeddings,
        builtin_tools.add_reflection,
        builtin_tools.delete_reflection,
        builtin_tools.rebuild_reflection_embeddings,
        builtin_tools.set_relationship,
        builtin_tools.add_worldline_event,
        builtin_tools.add_relationship_event,
        builtin_tools.add_commitment,
        builtin_tools.resolve_commitment,
        builtin_tools.add_unresolved_tension,
        builtin_tools.resolve_unresolved_tension,
        builtin_tools.add_semantic_self_narrative,
        builtin_tools.list_revision_traces,
        builtin_tools.rollback_memory_change,
        # escalation request
        getattr(builtin_tools, "request_toolset_upgrade"),
    ]


def _run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def build_tool_bundle() -> ToolBundle:
    """构建本项目可用的工具集合。

    约定：
    - base_tools：默认暴露给模型的工具（读/低风险为主）
    - extended_tools：需要“申请升级”后才暴露的工具（网络/写/高风险）

    目前先只接入 builtin tools；toolkits/MCP 的加载留好扩展口。
    """

    _ = _load_registry_config()  # toolkits/custom_tools 仍预留扩展

    all_tools: list[BaseTool] = []
    for t in _iter_builtin_tools():
        if t is None:
            continue
        all_tools.append(t)

    # 真实加载 MCP tools（若开启且 allowlist 命中）。
    try:
        mcp_tools = _run_async(load_mcp_tools_from_config())
        for t in mcp_tools or []:
            if t is not None:
                all_tools.append(t)
    except Exception as e:
        _audit_log("mcp_load_failed", {"error": f"{type(e).__name__}: {e}"})

    # 按 TOOL_POLICIES 做分组：read -> base, 其他 -> extended
    base: list[BaseTool] = []
    ext: list[BaseTool] = []

    for t in all_tools:
        name = getattr(t, "name", None)
        pol = TOOL_POLICIES.get(str(name), {})
        risk = str(pol.get("risk") or "write")
        if risk == "read" and bool(pol.get("auto_approve")):
            base.append(t)
        else:
            ext.append(t)

    # base 也允许包含“申请升级”工具（本质上是交互入口）
    # 如果没在 policies 里标 read/auto_approve，也强制放到 base。
    for t in all_tools:
        if getattr(t, "name", "") == "request_toolset_upgrade" and t not in base:
            base.append(t)
            if t in ext:
                ext.remove(t)

    return ToolBundle(base_tools=base, extended_tools=ext)


async def load_mcp_tools_from_config() -> list[BaseTool]:
    """（可选扩展）从配置加载 MCP tools。

    安全策略（先把防线立住）：
    - 默认 MCP_ENABLED=False：不开口子
    - 即使 enabled，也只允许加载 allowlist 内的 server（按 id/name 匹配）

    接入方式：langchain-mcp-adapters / MultiServerMCPClient。
    """

    cfg = _load_registry_config() or {}
    servers = cfg.get("mcp_servers") or []
    if not isinstance(servers, list):
        servers = []

    enabled = bool(MCP_ENABLED)
    if not enabled:
        _audit_log("mcp_disabled", {"reason": "MCP disabled", "server_count": len(servers)})
        return []

    cfg_allow = cfg.get("mcp_server_allowlist") or cfg.get("mcp_allowlist") or []
    allow = [*list(MCP_SERVER_ALLOWLIST or []), *list(cfg_allow if isinstance(cfg_allow, list) else [])]
    allow = {str(x).strip() for x in allow if str(x).strip()}
    if not allow:
        _audit_log("mcp_disabled", {"reason": "empty allowlist", "server_count": len(servers)})
        return []

    allowed_servers: list[dict[str, Any]] = []
    for s in servers:
        if not isinstance(s, dict):
            continue
        sid = str(s.get("id") or s.get("name") or "").strip()
        if sid and sid in allow:
            allowed_servers.append(s)

    # server allowlist 通过后，再记录 tool allowlist（真正接入 adapter 时必须双层都过）。
    tool_allow = {str(x).strip() for x in (MCP_TOOL_ALLOWLIST or []) if str(x).strip()}

    _audit_log(
        "mcp_filtered",
        {
            "server_count": len(servers),
            "allowed_count": len(allowed_servers),
            "allowlist": sorted(list(allow))[:50],
            "tool_allowlist": sorted(list(tool_allow))[:50],
            "server_hashes": [
                {
                    "id": str(s.get("id") or s.get("name") or "").strip(),
                    "hash": _stable_hash(s),
                }
                for s in allowed_servers
                if isinstance(s, dict)
            ][:50],
            "guards": {
                "calls_max": int(MCP_CALLS_MAX),
                "timeout_s": int(MCP_TIMEOUT_S),
            },
        },
    )
    if MultiServerMCPClient is None:
        _audit_log("mcp_disabled", {"reason": "langchain_mcp_adapters missing"})
        return []

    # 组装 MCP 连接配置。
    connections: dict[str, Any] = {}
    for s in allowed_servers:
        sid = str(s.get("id") or s.get("name") or "").strip()
        if not sid:
            continue
        transport = str(s.get("transport") or "streamable_http").strip().lower()
        if transport in {"streamable_http", "http"}:
            url = str(s.get("url") or "").strip()
            if not url:
                continue
            conn: dict[str, Any] = {"transport": "streamable_http", "url": url}
            headers = s.get("headers")
            if isinstance(headers, dict) and headers:
                conn["headers"] = headers
            connections[sid] = conn
        elif transport == "sse":
            url = str(s.get("url") or "").strip()
            if not url:
                continue
            conn = {"transport": "sse", "url": url}
            headers = s.get("headers")
            if isinstance(headers, dict) and headers:
                conn["headers"] = headers
            connections[sid] = conn
        elif transport == "stdio":
            cmd = str(s.get("command") or "").strip()
            if not cmd:
                continue
            args = s.get("args") if isinstance(s.get("args"), list) else []
            env = s.get("env") if isinstance(s.get("env"), dict) else None
            cwd = s.get("cwd")
            conn = {"transport": "stdio", "command": cmd, "args": [str(x) for x in args]}
            if isinstance(env, dict):
                conn["env"] = {str(k): str(v) for k, v in env.items()}
            if isinstance(cwd, str) and cwd.strip():
                conn["cwd"] = cwd.strip()
            connections[sid] = conn

    if not connections:
        _audit_log("mcp_disabled", {"reason": "no valid allowed servers"})
        return []

    client = MultiServerMCPClient(connections, tool_name_prefix=True)
    out: list[BaseTool] = []
    for sid in connections.keys():
        try:
            tools = await client.get_tools(server_name=sid)
        except Exception as e:
            _audit_log(
                "mcp_server_load_failed",
                {"server": sid, "error": f"{type(e).__name__}: {e}"},
            )
            continue

        for t in tools or []:
            name = str(getattr(t, "name", "") or "")
            if not name:
                continue
            if tool_allow and (name not in tool_allow):
                # 若开启 tool allowlist，则只暴露 allowlist 中的 MCP 工具。
                continue
            out.append(t)

    _audit_log(
        "mcp_tools_loaded",
        {
            "server_count": len(connections),
            "tool_count": len(out),
            "tools": [str(getattr(t, "name", "")) for t in out][:200],
        },
    )
    return out
