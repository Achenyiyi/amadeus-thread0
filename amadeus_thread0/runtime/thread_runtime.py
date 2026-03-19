from __future__ import annotations

import os
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


def sanitize_thread_id_seed(raw: str, *, fallback: str = "thread") -> str:
    seed = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(raw or "").strip()).strip("-._")
    return seed or fallback


def generate_thread_id(
    *,
    prefix: str = "thread",
    now_ts: int | None = None,
    suffix: str | None = None,
) -> str:
    safe_prefix = sanitize_thread_id_seed(prefix)
    clock = int(now_ts if now_ts is not None else time.time())
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(clock))
    token = sanitize_thread_id_seed(suffix or uuid.uuid4().hex[:8], fallback="session")
    return f"{safe_prefix}-{stamp}-{token}"


def resolve_startup_thread_id(
    *,
    default_thread_id: str,
    cli_thread_id: str | None,
    fresh_thread: bool,
    fresh_thread_prefix: str,
    now_ts: int | None = None,
    suffix: str | None = None,
) -> str:
    if cli_thread_id:
        return sanitize_thread_id_seed(cli_thread_id, fallback=default_thread_id)
    if fresh_thread:
        return generate_thread_id(prefix=fresh_thread_prefix, now_ts=now_ts, suffix=suffix)
    return default_thread_id


def worldline_runtime_dir(base_data_dir: Path, thread_id: str) -> Path:
    return Path(base_data_dir) / "worldlines" / sanitize_thread_id_seed(thread_id, fallback="thread")


def apply_worldline_runtime_paths(base_data_dir: Path, thread_id: str) -> Path:
    runtime_dir = worldline_runtime_dir(base_data_dir, thread_id)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    os.environ["AMADEUS_DATA_DIR"] = str(runtime_dir)
    os.environ["AMADEUS_CHECKPOINT_DB"] = str(runtime_dir / "checkpoints.sqlite")
    os.environ["AMADEUS_MEMORY_DB"] = str(runtime_dir / "memories.sqlite")
    os.environ["AMADEUS_DIARY_PATH"] = str(runtime_dir / "diary.txt")
    return runtime_dir


def has_explicit_runtime_path_overrides() -> bool:
    return any(
        str(os.getenv(name) or "").strip()
        for name in {
            "AMADEUS_DATA_DIR",
            "AMADEUS_CHECKPOINT_DB",
            "AMADEUS_MEMORY_DB",
            "AMADEUS_DIARY_PATH",
        }
    )


def should_isolate_startup_runtime(
    *,
    startup_thread_id: str,
    fresh_thread: bool,
    explicit_runtime_paths: bool,
) -> bool:
    thread_id = str(startup_thread_id or "").strip()
    if fresh_thread:
        return True
    if explicit_runtime_paths:
        return False
    return bool(thread_id) and thread_id != "thread0"


def repo_default_data_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data"


def shared_runtime_artifacts(base_data_dir: Path) -> list[str]:
    names = [
        "checkpoints.sqlite",
        "memories.sqlite",
        "decision_audit.jsonl",
        "mcp_audit.jsonl",
        "memory_store_audit.jsonl",
        "tool_audit.jsonl",
    ]
    found: list[str] = []
    root = Path(base_data_dir)
    for name in names:
        path = root / name
        try:
            if path.exists() and path.is_file() and path.stat().st_size > 0:
                found.append(name)
        except Exception:
            continue
    return found


def should_warn_shared_default_runtime(
    *,
    base_data_dir: Path,
    runtime_data_dir: Path,
    startup_thread_id: str,
    startup_explicit: bool,
    shared_artifacts: list[str],
) -> bool:
    if startup_explicit:
        return False
    if str(startup_thread_id or "").strip() != "thread0":
        return False
    if not shared_artifacts:
        return False
    try:
        if Path(base_data_dir).resolve() != repo_default_data_dir().resolve():
            return False
        if Path(runtime_data_dir).resolve() != Path(base_data_dir).resolve():
            return False
    except Exception:
        return False
    raw = str(os.getenv("AMADEUS_CLI_SUPPRESS_SHARED_RUNTIME_WARNING", "0") or "").strip().lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return False
    return True


@dataclass(frozen=True)
class ThreadInventory:
    checkpoint_thread_ids: list[str]
    worldline_dir_ids: list[str]


def list_threads(base_data_dir: Path, checkpoint_db_path: Path) -> ThreadInventory:
    checkpoint_ids: set[str] = set()
    try:
        conn = sqlite3.connect(str(checkpoint_db_path), check_same_thread=False)
        try:
            tables = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
            ]
            for table_name in tables:
                cols = [col[1] for col in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
                if "thread_id" not in cols:
                    continue
                try:
                    rows = conn.execute(f"SELECT DISTINCT thread_id FROM {table_name}").fetchall()
                except Exception:
                    continue
                for (thread_id,) in rows:
                    if thread_id:
                        checkpoint_ids.add(str(thread_id))
        finally:
            conn.close()
    except Exception:
        checkpoint_ids = set()

    worldline_root = Path(base_data_dir) / "worldlines"
    worldline_ids: list[str] = []
    try:
        if worldline_root.exists():
            worldline_ids = sorted(path.name for path in worldline_root.iterdir() if path.is_dir())
    except Exception:
        worldline_ids = []

    return ThreadInventory(
        checkpoint_thread_ids=sorted(checkpoint_ids),
        worldline_dir_ids=worldline_ids,
    )


@dataclass(frozen=True)
class ThreadSwitchPlan:
    thread_id: str
    runtime_dir: Path


def activate_thread_runtime(
    base_data_dir: Path,
    requested_thread_id: str,
    *,
    fallback_prefix: str = "thread",
    now_ts: int | None = None,
    suffix: str | None = None,
) -> ThreadSwitchPlan:
    fallback_thread_id = generate_thread_id(prefix=fallback_prefix, now_ts=now_ts, suffix=suffix)
    thread_id = sanitize_thread_id_seed(requested_thread_id, fallback=fallback_thread_id)
    runtime_dir = apply_worldline_runtime_paths(base_data_dir, thread_id)
    return ThreadSwitchPlan(thread_id=thread_id, runtime_dir=runtime_dir)


__all__ = [
    "ThreadInventory",
    "ThreadSwitchPlan",
    "activate_thread_runtime",
    "apply_worldline_runtime_paths",
    "generate_thread_id",
    "has_explicit_runtime_path_overrides",
    "list_threads",
    "repo_default_data_dir",
    "resolve_startup_thread_id",
    "sanitize_thread_id_seed",
    "shared_runtime_artifacts",
    "should_isolate_startup_runtime",
    "should_warn_shared_default_runtime",
    "worldline_runtime_dir",
]
