from __future__ import annotations

import time
from functools import lru_cache
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage

from ..config import MODEL_MAX_RETRIES, MODEL_RETRY_BACKOFF_S
from ..memory_store import MemoryStore
from ..modeling import build_chat_model
from ..settings import get_settings
from ..tool_registry import ToolBundle, build_tool_bundle
from .common import _now_ts, _safe_json, _sanitize_message


def _audit_jsonl(file_name: str, payload: dict[str, Any]) -> None:
    try:
        settings = get_settings()
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        path = settings.data_dir / file_name
        record = {"ts": _now_ts(), **payload}
        with path.open("a", encoding="utf-8") as f:
            f.write(_safe_json(record) + "\n")
    except Exception:
        pass


@lru_cache(maxsize=1)
def _get_store() -> MemoryStore:
    settings = get_settings()
    return MemoryStore(settings.memory_db_path)


@lru_cache(maxsize=1)
def _get_tool_bundle() -> ToolBundle:
    return build_tool_bundle()


def _model(temperature: float | None = None, **kwargs: Any) -> BaseChatModel:
    return build_chat_model(temperature=temperature, **kwargs)


def _is_transient_model_error(exc: Exception) -> bool:
    transient_names = {
        "RemoteProtocolError",
        "ReadError",
        "WriteError",
        "PoolTimeout",
        "ReadTimeout",
        "ConnectTimeout",
        "TimeoutException",
        "ConnectError",
        "NetworkError",
        "APIConnectionError",
        "APITimeoutError",
        "InternalServerError",
    }
    cur: BaseException | None = exc
    seen: set[int] = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if type(cur).__name__ in transient_names:
            return True
        cur = cur.__cause__ or cur.__context__
    return False


def _invoke_model_with_retries(
    llm_runnable: Any,
    call_msgs: list[BaseMessage],
    *,
    max_retries: int | None = None,
    audit_file_name: str = "decision_audit.jsonl",
) -> Any:
    retry_budget = MODEL_MAX_RETRIES if max_retries is None else max(0, int(max_retries))
    attempts = max(1, int(retry_budget) + 1)
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            sanitized_call_msgs = [_sanitize_message(msg) for msg in call_msgs if isinstance(msg, BaseMessage)]
            return llm_runnable.invoke(sanitized_call_msgs)
        except Exception as exc:  # pragma: no cover - network/provider dependent
            if not isinstance(exc, Exception):
                raise
            last_exc = exc
            if (not _is_transient_model_error(exc)) or attempt >= attempts:
                raise
            _audit_jsonl(
                audit_file_name,
                {
                    "event": "model_invoke_retry",
                    "attempt": attempt,
                    "max_attempts": attempts,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:300],
                },
            )
            time.sleep(max(0.0, float(MODEL_RETRY_BACKOFF_S)) * float(attempt))
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("model invocation failed without an exception")
