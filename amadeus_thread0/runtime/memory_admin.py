from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from langchain_core.messages import SystemMessage

from ..memory_store import MemoryStore
from .modeling import build_chat_model


class MemoryAdminError(RuntimeError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(str(message or "").strip() or "memory admin error")
        self.details = dict(details or {})


@dataclass(frozen=True)
class ProfileCorrectionPreview:
    key: str
    old_value: Any
    new_value: Any
    reason: str


@dataclass(frozen=True)
class UndoCorrectionPreview:
    key: str
    current_value: Any
    revert_to: Any
    reason: str
    previous_meta: dict[str, Any]


@dataclass(frozen=True)
class ReflectionProposal:
    text: str
    derived_from: list[int] = field(default_factory=list)
    importance: float = 0.5


@dataclass(frozen=True)
class ReflectionWriteResult:
    reflection_id: int
    wrote_user_model_rule: bool


def _normalize_positive_int(value: Any, *, default: int, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(low, min(high, parsed))


def _normalize_importance(value: Any, *, default: float = 0.5) -> float:
    try:
        importance = float(value)
    except Exception:
        importance = float(default)
    return max(0.0, min(1.0, importance))


def _normalize_int_list(values: Any, *, limit: int) -> list[int]:
    if not isinstance(values, list):
        return []
    out: list[int] = []
    seen: set[int] = set()
    for item in values:
        try:
            parsed = int(item)
        except Exception:
            continue
        if parsed <= 0 or parsed in seen:
            continue
        seen.add(parsed)
        out.append(parsed)
        if len(out) >= limit:
            break
    return out


def _reflection_prompt(recent_moments: list[dict[str, Any]]) -> str:
    compact_moments = [{"id": item.get("id"), "summary": item.get("summary")} for item in recent_moments]
    return (
        "你是记忆反思器(reflection generator)。给定一组按时间排序的 moments，请总结出 1~6 条‘长期规律/稳定结论’。\n"
        "要求：\n"
        "- 反思应尽量稳定：偏好、禁忌、沟通方式、关系边界、长期目标等；不要总结一次性事件细节。\n"
        "- 每条反思尽量短（10~40字），可作为长期记忆注入。\n"
        "- 给出 derived_from：支撑该反思的 moment id 列表（1~10个）。\n"
        "- 给出 importance：0~1。越重要越高。\n"
        "- 只输出严格 JSON 数组，不要任何多余文字。\n"
        "输出格式：[{\"text\": str, \"derived_from\": [int,...], \"importance\": 0~1}, ...]\n"
        f"moments：{json.dumps(compact_moments, ensure_ascii=False)}\n"
    )


@dataclass
class MemoryAdminService:
    memory_store: MemoryStore
    llm_factory: Callable[..., Any] = build_chat_model

    def snapshot_view(self) -> dict[str, Any]:
        return self.memory_store.snapshot()

    def prepare_profile_correction(self, key: str, new_value: Any, *, reason: str = "") -> ProfileCorrectionPreview:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            raise MemoryAdminError("profile key 不能为空。")
        old_value = self.memory_store.get_profile().get(normalized_key)
        return ProfileCorrectionPreview(
            key=normalized_key,
            old_value=old_value,
            new_value=new_value,
            reason=str(reason or "").strip(),
        )

    def apply_profile_correction(
        self,
        preview: ProfileCorrectionPreview,
        *,
        confirmed_by: str = "user",
    ) -> None:
        self.memory_store.set_profile(preview.key, preview.new_value)
        self.memory_store.set_profile_meta(
            preview.key,
            {
                "source": "user_correction",
                "old_value": preview.old_value,
                "new_value": preview.new_value,
                "reason": preview.reason,
                "corrected_at": int(time.time()),
                "confirmed_by": str(confirmed_by or "user").strip() or "user",
            },
        )

    def prepare_undo_profile_correction(
        self,
        key: str,
        *,
        reason: str = "",
    ) -> UndoCorrectionPreview:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            raise MemoryAdminError("profile key 不能为空。")
        meta = (self.memory_store.get_profile_meta() or {}).get(normalized_key)
        if not isinstance(meta, dict):
            raise MemoryAdminError("未找到该 key 的 meta，无法自动撤销。")
        if ("old_value" not in meta) or ("new_value" not in meta):
            raise MemoryAdminError("meta 缺少 old_value/new_value，无法自动撤销。")
        current_value = self.memory_store.get_profile().get(normalized_key)
        if current_value != meta.get("new_value"):
            raise MemoryAdminError(
                "当前值与 meta.new_value 不一致，拒绝自动撤销（避免误操作）。",
                details={
                    "current": current_value,
                    "meta_new_value": meta.get("new_value"),
                },
            )
        return UndoCorrectionPreview(
            key=normalized_key,
            current_value=current_value,
            revert_to=meta.get("old_value"),
            reason=str(reason or "").strip() or "user requested undo",
            previous_meta=dict(meta),
        )

    def apply_undo_profile_correction(
        self,
        preview: UndoCorrectionPreview,
        *,
        confirmed_by: str = "user",
    ) -> None:
        self.memory_store.set_profile(preview.key, preview.revert_to)
        self.memory_store.set_profile_meta(
            preview.key,
            {
                "source": "undo_correction",
                "undone_at": int(time.time()),
                "reason": preview.reason,
                "reverted_from": preview.current_value,
                "reverted_to": preview.revert_to,
                "prev_meta": preview.previous_meta,
                "confirmed_by": str(confirmed_by or "user").strip() or "user",
            },
        )

    def set_profile_value(self, key: str, value: Any) -> str:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            raise MemoryAdminError("profile key 不能为空。")
        self.memory_store.set_profile(normalized_key, value)
        return normalized_key

    def delete_profile_key(self, key: str) -> bool:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            raise MemoryAdminError("profile key 不能为空。")
        return bool(self.memory_store.delete_profile(normalized_key))

    def list_moments(self, *, limit: int = 20) -> list[dict[str, Any]]:
        return list(reversed(self.memory_store.list_moments(limit=_normalize_positive_int(limit, default=20, low=1, high=200))))

    def delete_moment(self, moment_id: int) -> bool:
        return bool(self.memory_store.delete_moment(int(moment_id)))

    def list_reflections(self, *, limit: int = 20) -> list[dict[str, Any]]:
        return list(
            reversed(
                self.memory_store.list_reflections(
                    limit=_normalize_positive_int(limit, default=20, low=1, high=200)
                )
            )
        )

    def delete_reflection(self, reflection_id: int) -> bool:
        return bool(self.memory_store.delete_reflection(int(reflection_id)))

    def generate_reflection_proposals(self, *, moment_limit: int = 20) -> list[ReflectionProposal]:
        limit = _normalize_positive_int(moment_limit, default=20, low=5, high=200)
        recent = list(reversed(self.memory_store.list_moments(limit=limit)))
        if not recent:
            raise MemoryAdminError("没有 moments，无法生成反思。")

        prompt = _reflection_prompt(recent)
        llm = self.llm_factory(temperature=0.2)
        raw = llm.invoke([SystemMessage(content=prompt)])
        data = None
        for attempt in (1, 2):
            try:
                data = json.loads(getattr(raw, "content", "") or "")
                break
            except Exception:
                if attempt == 1:
                    raw = llm.invoke(
                        [
                            SystemMessage(
                                content=prompt
                                + "\n【重试】只输出 JSON 数组，不得包含 Markdown 代码块/解释文字。"
                            )
                        ]
                    )
                    continue
                data = None

        if not isinstance(data, list) or not data:
            raise MemoryAdminError("反思生成失败（未得到合法 JSON 数组）。")

        proposals: list[ReflectionProposal] = []
        for item in data[:6]:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            proposals.append(
                ReflectionProposal(
                    text=text,
                    derived_from=_normalize_int_list(item.get("derived_from"), limit=10),
                    importance=_normalize_importance(item.get("importance"), default=0.5),
                )
            )
        if not proposals:
            raise MemoryAdminError("反思生成失败（缺少可用提案）。")
        return proposals

    def write_reflection(
        self,
        proposal: ReflectionProposal,
        *,
        write_user_model_rule: bool = False,
    ) -> ReflectionWriteResult:
        reflection_id = int(
            self.memory_store.add_reflection(
                text=proposal.text,
                derived_from=proposal.derived_from,
                importance=proposal.importance,
            )
        )
        wrote_rule = False
        if write_user_model_rule:
            self._append_user_model_rule(proposal, reflection_id=reflection_id)
            wrote_rule = True
        return ReflectionWriteResult(reflection_id=reflection_id, wrote_user_model_rule=wrote_rule)

    def _append_user_model_rule(self, proposal: ReflectionProposal, *, reflection_id: int) -> None:
        rule = {
            "text": proposal.text,
            "importance": proposal.importance,
            "derived_from": proposal.derived_from,
            "reflection_id": int(reflection_id),
            "created_at": int(time.time()),
        }
        old = self.memory_store.get_profile().get("user_model_rules")
        merged = [*old] if isinstance(old, list) else []
        merged.append(rule)
        deduped: list[Any] = []
        seen: set[str] = set()
        for item in merged:
            text = str((item or {}).get("text") if isinstance(item, dict) else item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            deduped.append(item)
        self.memory_store.set_profile("user_model_rules", deduped[:50])
        self.memory_store.set_profile_meta(
            "user_model_rules",
            {
                "source": "reflect_batch",
                "last_confirmed_at": int(time.time()),
                "note": "derived from reflections",
            },
        )


__all__ = [
    "MemoryAdminError",
    "MemoryAdminService",
    "ProfileCorrectionPreview",
    "ReflectionProposal",
    "ReflectionWriteResult",
    "UndoCorrectionPreview",
]
