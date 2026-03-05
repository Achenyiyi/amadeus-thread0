from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    # 允许用环境变量覆盖数据目录，方便评测/回归时用“隔离库”避免污染真实记忆
    data_dir: Path
    checkpoint_db_path: Path
    memory_db_path: Path
    diary_path: Path

    # 单用户：固定 user_id / thread_id 即可（评测时建议用 env 覆盖）
    user_id: str
    thread_id: str

    # DeepSeek
    deepseek_model: str
    temperature: float

    # Embeddings（moments 语义检索）
    embedding_model_name: str
    embedding_device: str
    embedding_normalize: bool
    embedding_trust_remote_code: bool

    # TTS（DashScope Qwen3-TTS Realtime；只做 I/O，不进入工具系统）
    tts_enabled: bool

    # 参考音频（用于 enrollment）；输出语言目前由服务端模型决定
    tts_ref_audio: str
    tts_ref_text: str


def get_settings() -> Settings:
    """从当前环境变量构造 Settings。"""

    data_dir = Path(os.getenv("AMADEUS_DATA_DIR", str(BASE_DIR / "data")))

    checkpoint_db_path = Path(os.getenv("AMADEUS_CHECKPOINT_DB", str(data_dir / "checkpoints.sqlite")))
    memory_db_path = Path(os.getenv("AMADEUS_MEMORY_DB", str(data_dir / "memories.sqlite")))
    diary_path = Path(os.getenv("AMADEUS_DIARY_PATH", str(data_dir / "diary.txt")))

    user_id = os.getenv("AMADEUS_USER_ID", "me")
    thread_id = os.getenv("AMADEUS_THREAD_ID", "thread0")

    deepseek_model = os.getenv("AMADEUS_DEEPSEEK_MODEL", "deepseek-chat")
    temperature = float(os.getenv("AMADEUS_TEMPERATURE", "0.5"))

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
        deepseek_model=deepseek_model,
        temperature=temperature,
        embedding_model_name=embedding_model_name,
        embedding_device=embedding_device,
        embedding_normalize=embedding_normalize,
        embedding_trust_remote_code=embedding_trust_remote_code,
        tts_enabled=tts_enabled,
        tts_ref_audio=tts_ref_audio,
        tts_ref_text=tts_ref_text,
    )