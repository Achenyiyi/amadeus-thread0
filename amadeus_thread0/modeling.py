import os
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_qwq import ChatQwen

from .config import (
    EVAL_GENERATION_TEMPERATURE,
    EVAL_MODE,
    MODEL_DISABLE_STREAMING,
    MODEL_MAX_RETRIES,
    MODEL_TIMEOUT_S,
)
from .settings import get_settings


def _normalize_provider(provider: str) -> str:
    value = str(provider or "").strip().lower()
    if value in {"qwen", "qwen_native", "chatqwen"}:
        return "qwen_native"
    if value in {"dashscope", "dashscope_compatible", "openai-compatible", "openai_compatible", "openai"}:
        return "openai_compatible"
    return "deepseek"


def _resolve_api_key(provider: str) -> str:
    explicit = str(os.getenv("AMADEUS_MODEL_API_KEY", "")).strip()
    if explicit:
        return explicit
    if provider == "deepseek":
        return str(os.getenv("DEEPSEEK_API_KEY", "")).strip()
    return (
        str(os.getenv("DASHSCOPE_API_KEY", "")).strip()
        or str(os.getenv("OPENAI_API_KEY", "")).strip()
    )


def build_chat_model(*, temperature: float | None = None) -> BaseChatModel:
    s = get_settings()
    provider = _normalize_provider(s.model_provider)
    effective_temperature = s.temperature if temperature is None else float(temperature)
    if EVAL_MODE:
        effective_temperature = float(EVAL_GENERATION_TEMPERATURE)

    common: dict[str, Any] = {
        "model": s.model_name,
        "temperature": effective_temperature,
        "timeout": float(MODEL_TIMEOUT_S),
        "max_retries": max(0, int(MODEL_MAX_RETRIES)),
        "streaming": False,
        "disable_streaming": bool(MODEL_DISABLE_STREAMING),
    }
    api_key = _resolve_api_key(provider)
    if api_key:
        common["api_key"] = api_key
    if s.model_base_url:
        common["base_url"] = s.model_base_url

    if provider == "qwen_native":
        qwen_enable_thinking = str(os.getenv("AMADEUS_QWEN_ENABLE_THINKING", "0")).strip().lower()
        common["enable_thinking"] = qwen_enable_thinking in {"1", "true", "yes", "on"}
        qwen_thinking_budget = str(os.getenv("AMADEUS_QWEN_THINKING_BUDGET", "")).strip()
        if qwen_thinking_budget:
            try:
                common["thinking_budget"] = int(qwen_thinking_budget)
            except Exception:
                pass
        return ChatQwen(**common)
    if provider == "openai_compatible":
        return ChatOpenAI(**common)
    return ChatDeepSeek(**common)


def runtime_model_summary() -> str:
    s = get_settings()
    provider = _normalize_provider(s.model_provider)
    return f"{provider}:{s.model_name}"
