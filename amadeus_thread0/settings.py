from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .config import RUNTIME_MODE

BASE_DIR = Path(__file__).resolve().parent.parent
_TRUTHY = {"1", "true", "yes", "y", "on"}
_FALSEY = {"0", "false", "no", "n", "off"}


@dataclass(frozen=True)
class Settings:
    # 允许通过环境变量覆盖数据目录，便于评测或回归时使用隔离数据。
    data_dir: Path
    checkpoint_db_path: Path
    memory_db_path: Path
    diary_path: Path

    # 单用户默认配置；评测时建议通过环境变量覆盖 thread_id。
    user_id: str
    thread_id: str

    # Runtime model settings.
    model_provider: str
    model_name: str
    model_base_url: str
    runtime_mode: str

    # Embeddings for semantic retrieval over moments/reflections.
    embedding_model_name: str
    embedding_device: str
    embedding_normalize: bool
    embedding_trust_remote_code: bool

    # TTS backend flags. TTS runs outside the tool system.
    tts_enabled: bool
    tts_ref_audio: str
    tts_ref_text: str


def _read_bool_env(name: str) -> bool | None:
    raw = str(os.getenv(name, "")).strip().lower()
    if not raw:
        return None
    if raw in _TRUTHY:
        return True
    if raw in _FALSEY:
        return False
    return None


def _clear_langsmith_env_cache() -> None:
    try:
        from langsmith import utils as langsmith_utils

        cache_clear = getattr(getattr(langsmith_utils, "get_env_var", None), "cache_clear", None)
        if callable(cache_clear):
            cache_clear()
    except Exception:
        pass


def configure_runtime_environment() -> None:
    """Apply shared runtime defaults before LangChain/LangSmith components boot."""

    explicit = _read_bool_env("AMADEUS_ENABLE_TRACING")
    if explicit is None:
        explicit = _read_bool_env("AMADEUS_CLI_ENABLE_TRACING")

    langsmith_flag = _read_bool_env("LANGSMITH_TRACING")
    langchain_flag = _read_bool_env("LANGCHAIN_TRACING_V2")

    if explicit is not None:
        tracing_enabled = explicit
    elif langsmith_flag is False or langchain_flag is False:
        tracing_enabled = False
    else:
        # Local/manual runs default to quiet. Raw LANGSMITH_* flags in .env do not
        # re-enable tracing unless the runtime explicitly opts in via AMADEUS_*.
        tracing_enabled = False

    desired = "true" if tracing_enabled else "false"
    os.environ["LANGSMITH_TRACING"] = desired
    os.environ["LANGCHAIN_TRACING_V2"] = desired
    _clear_langsmith_env_cache()


def get_settings() -> Settings:
    """Build Settings from environment variables."""
    configure_runtime_environment()

    data_dir = Path(os.getenv("AMADEUS_DATA_DIR", str(BASE_DIR / "data")))

    checkpoint_db_path = Path(os.getenv("AMADEUS_CHECKPOINT_DB", str(data_dir / "checkpoints.sqlite")))
    memory_db_path = Path(os.getenv("AMADEUS_MEMORY_DB", str(data_dir / "memories.sqlite")))
    diary_path = Path(os.getenv("AMADEUS_DIARY_PATH", str(data_dir / "diary.txt")))

    user_id = os.getenv("AMADEUS_USER_ID", "okabe_rintaro")
    thread_id = os.getenv("AMADEUS_THREAD_ID", "thread0")

    model_name = str(os.getenv("AMADEUS_MODEL_NAME", "") or os.getenv("AMADEUS_DEEPSEEK_MODEL", "deepseek-chat")).strip()
    model_base_url = str(os.getenv("AMADEUS_MODEL_BASE_URL", "")).strip()
    model_provider = str(os.getenv("AMADEUS_MODEL_PROVIDER", "")).strip().lower()
    if not model_provider:
        model_provider = "openai_compatible" if model_base_url else "deepseek"

    embedding_model_name = os.getenv("AMADEUS_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B")
    embedding_device = os.getenv("AMADEUS_EMBEDDING_DEVICE", "cpu")
    embedding_normalize = os.getenv("AMADEUS_EMBEDDING_NORMALIZE", "1") not in {"0", "false", "False"}
    embedding_trust_remote_code = os.getenv("AMADEUS_EMBEDDING_TRUST_REMOTE_CODE", "1") not in {"0", "false", "False"}

    tts_enabled = os.getenv("AMADEUS_TTS_ENABLED", "0") not in {"0", "false", "False"}
    tts_ref_audio = os.getenv("AMADEUS_TTS_REF_AUDIO", "")
    tts_ref_text = os.getenv("AMADEUS_TTS_REF_TEXT", "")

    return Settings(
        data_dir=data_dir,
        checkpoint_db_path=checkpoint_db_path,
        memory_db_path=memory_db_path,
        diary_path=diary_path,
        user_id=user_id,
        thread_id=thread_id,
        model_provider=model_provider,
        model_name=model_name,
        model_base_url=model_base_url,
        runtime_mode=RUNTIME_MODE,
        embedding_model_name=embedding_model_name,
        embedding_device=embedding_device,
        embedding_normalize=embedding_normalize,
        embedding_trust_remote_code=embedding_trust_remote_code,
        tts_enabled=tts_enabled,
        tts_ref_audio=tts_ref_audio,
        tts_ref_text=tts_ref_text,
    )
