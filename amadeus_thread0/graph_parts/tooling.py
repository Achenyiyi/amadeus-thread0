from __future__ import annotations

import re
import uuid
from typing import Any

from langchain_core.tools import BaseTool

from ..config import TOOL_POLICIES
from .common import _safe_json

def _parse_set_profile_args(text: str) -> dict[str, Any]:
    key = ""
    value = ""

    km = re.search(r"\bkey\s*=\s*([a-zA-Z_][a-zA-Z0-9_]*)", text, flags=re.I)
    vm = re.search(r"\bvalue\s*=\s*([^，。,；;\n]+)", text, flags=re.I)
    if km:
        key = km.group(1).strip()
    if vm:
        value = vm.group(1).strip()

    if not key or not value:
        km2 = re.search(r"(?:把|将|设置)\s*(?:我的)?([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:设为|设置为|改为)\s*([^，。,；;\n]+)", text)
        if km2:
            key = key or km2.group(1).strip()
            value = value or km2.group(2).strip()

    if not key:
        key = "nickname"
    if not value:
        vm2 = re.search(r"(?:昵称|称呼).{0,4}(?:设为|设置为|改为)?\s*([^，。,；;\n]+)", text)
        value = vm2.group(1).strip() if vm2 else "用户"

    return {"key": key, "value": value, "mode": "merge", "meta": {"confidence": 0.9, "source_text": text}}

def _build_followup_for_upgrade(text: str, mentioned_registered: list[str]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    if not mentioned_registered:
        return calls

    wants_execute = any(marker in text for marker in {"再执行", "然后执行", "再保存", "随后保存", "执行保存"})
    if not wants_execute:
        return calls

    if "add_skill" in mentioned_registered and any(marker in text for marker in {"技能", "保存"}):
        calls.append(
            {
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "name": "add_skill",
                "args": {
                    "name": _extract_skill_name(text),
                    "description": text[:160],
                    "steps": _extract_skill_steps(text),
                },
            }
        )

    if "set_profile" in mentioned_registered:
        calls.append(
            {
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "name": "set_profile",
                "args": _parse_set_profile_args(text),
            }
        )

    if "add_commitment" in mentioned_registered:
        tm = re.search(r"(?:承诺|约定|记下)(.+?)(?:，|,|$)", text)
        txt = tm.group(1).strip() if tm else text
        calls.append(
            {
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "name": "add_commitment",
                "args": {"text": txt},
            }
        )
    return calls

def _parse_explicit_tool_call(user_text: str, tools: list[BaseTool]) -> list[dict[str, Any]] | None:
    text = str(user_text or "").strip()
    if not text:
        return None

    names = {str(getattr(t, "name", "") or "").strip(): t for t in tools}
    all_registered = {str(name).strip() for name in TOOL_POLICIES.keys() if str(name).strip()}
    if not names and not all_registered:
        return None
    has_named_tool = any(name and name in text for name in all_registered)
    wants_upgrade = any(marker in text for marker in {"申请解锁", "先申请解锁", "升级", "解锁", "开放权限"})
    if ("调用" not in text and "使用" not in text and not wants_upgrade and not has_named_tool) or (
        "工具" not in text and not has_named_tool and not wants_upgrade
    ):
        return None

    mentioned_registered: list[str] = []
    for name in sorted(all_registered, key=len, reverse=True):
        if name and name in text and name != "request_toolset_upgrade":
            mentioned_registered.append(name)
    mentioned_registered = list(dict.fromkeys(mentioned_registered))

    hit_name = ""
    if wants_upgrade and mentioned_registered:
        hit_name = "request_toolset_upgrade"
    for name in names.keys():
        if hit_name:
            break
        if name and name in text:
            hit_name = name
            break
    if not hit_name:
        m = re.search(r"(?:调用|使用)\s*([a-zA-Z_][a-zA-Z0-9_]*)", text)
        if m:
            cand = m.group(1).strip()
            if cand in names:
                hit_name = cand
            elif wants_upgrade and cand in all_registered:
                hit_name = "request_toolset_upgrade"
                mentioned_registered = [cand]
            elif cand in all_registered:
                hit_name = cand
    if not hit_name and mentioned_registered:
        hit_name = mentioned_registered[0]
    if not hit_name:
        return None

    args: dict[str, Any] = {}

    if hit_name in {"search_langchain_docs", "arxiv_search"}:
        m = re.search(r"(?:检索|搜索|查询)(.+?)(?:，|,|并|并且|$)", text)
        q = m.group(1).strip() if m else text
        q = q.replace("工具", "").replace(hit_name, "").strip()
        args = {"query": q or "langchain langgraph"}
        if hit_name == "search_langchain_docs":
            args["max_results"] = 3
        else:
            args["max_results"] = 3

    elif hit_name == "request_toolset_upgrade":
        req: list[str] = []
        for name in all_registered:
            if name and name != "request_toolset_upgrade" and name in text:
                req.append(name)
        # Fallback token parse for explicit snake_case tool names.
        if not req:
            for token in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", text):
                t = token.strip()
                if t in all_registered and t != "request_toolset_upgrade":
                    req.append(t)
        req = list(dict.fromkeys(req))[:8]
        rm = re.search(r"(?:reason|理由|原因)[：: ](.+)$", text)
        reason = rm.group(1).strip() if rm else "Need tool for requested operation."
        args = {"requested_tools": req, "reason": reason}

    elif hit_name == "set_profile":
        args = _parse_set_profile_args(text)

    elif hit_name == "add_commitment":
        tm = re.search(r"(?:承诺|约定|记下)(.+?)(?:，|,|$)", text)
        txt = tm.group(1).strip() if tm else text
        args = {"text": txt}

    if not args:
        args = {}
    calls = [
        {
            "id": f"call_{uuid.uuid4().hex[:8]}",
            "name": hit_name,
            "args": args,
        }
    ]
    if hit_name == "request_toolset_upgrade":
        calls.extend(_build_followup_for_upgrade(text, mentioned_registered))
    return calls

def _extract_skill_name(text: str) -> str:
    qm = re.search(r"[“\"']([^“”\"']{2,40})[”\"']", text)
    if qm:
        return qm.group(1).strip()
    m = re.search(r"把(.+?)作为一个技能保存", text)
    if m:
        return m.group(1).strip("：: ，,。")
    return "新技能"

def _extract_skill_steps(text: str) -> list[str]:
    m = re.search(r"(?:步骤是|步骤为|流程是)(.+)", text)
    if not m:
        return []
    raw = re.split(r"[。；;]", m.group(1).strip())[0]
    parts = re.split(r"[、,，]", raw)
    return [str(part).strip() for part in parts if str(part).strip()][:8]

def _explicit_memory_request(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    return any(marker in raw for marker in {"请记住", "记住这件事", "记下来", "帮我记着", "提醒我", "别忘了", "之后提醒"})

def _explicit_commitment_summary(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    summary = re.sub(r"(请记住|记下来|帮我记着|提醒我|别忘了|之后提醒)", "", raw).strip("，,。 ")
    summary = re.sub(r"^(这件事|这个约定|这件)$", "", summary).strip("，,。 ")
    return summary[:180]

def _infer_memory_tool_calls(user_text: str) -> list[dict[str, Any]]:
    text = str(user_text or "").strip()
    if not text:
        return []

    calls: list[dict[str, Any]] = []

    # Preference updates: keep likes/dislikes mutually exclusive through set_profile.
    neg = re.search(r"我(?:不喜欢|不吃|讨厌)([^，。！？,]{1,12})", text)
    pos = re.search(r"我(?:改主意了，?)?(?:其实)?(?:喜欢|爱吃|爱喝)([^，。！？,]{1,12})", text)
    if neg:
        item = neg.group(1).strip()
        if item:
            calls.append(
                {
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "name": "set_profile",
                    "args": {
                        "key": "dislikes",
                        "value": [item],
                        "mode": "merge",
                        "meta": {"confidence": 0.92, "source_text": text},
                    },
                }
            )
    elif pos:
        item = pos.group(1).strip()
        if item:
            calls.append(
                {
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "name": "set_profile",
                    "args": {
                        "key": "likes",
                        "value": [item],
                        "mode": "merge",
                        "meta": {"confidence": 0.92, "source_text": text},
                    },
                }
            )

    # Skill persistence from direct user instruction.
    if any(marker in text for marker in {"作为一个技能保存", "保存为技能", "技能保存"}) and "add_skill" not in text:
        calls.append(
            {
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "name": "add_skill",
                "args": {
                    "name": _extract_skill_name(text),
                    "description": text[:160],
                    "steps": _extract_skill_steps(text),
                },
            }
        )

    # Only explicit memory instructions should force tool writes here.
    explicit_memory = _explicit_memory_request(text)
    explicit_commitment = explicit_memory and (
        any(marker in text for marker in {"约定", "承诺", "提醒"})
        or (
            any(marker in text for marker in {"下周", "周末", "以后", "下次", "明天", "今晚", "复盘"})
            and any(marker in text for marker in {"一起", "提醒", "别忘", "记住"})
        )
    )
    if explicit_commitment:
        summary = _explicit_commitment_summary(text)
        if summary:
            calls.append(
                {
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "name": "add_commitment",
                    "args": {"text": summary, "confidence": 0.9},
                }
            )
            calls.append(
                {
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "name": "add_worldline_event",
                    "args": {
                        "summary": summary,
                        "category": "commitment",
                        "importance": 0.82,
                        "tags": ["commitment", "worldline", "explicit_memory_request"],
                        "confidence": 0.86,
                    },
                }
            )

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for call in calls:
        name = str(call.get("name") or "").strip()
        args = _safe_json(call.get("args") or {})
        key = (name, args)
        if name and key not in seen:
            seen.add(key)
            deduped.append(call)
    return deduped[:4]
