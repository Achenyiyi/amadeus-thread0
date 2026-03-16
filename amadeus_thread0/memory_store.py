from __future__ import annotations

import json
import importlib
import math
import os
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import site

# Reduce TensorFlow noise emitted through sentence-transformers dependencies.
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TF", "0")


def _prefer_conda_gpu_torch() -> None:
    """Prefer the conda-managed GPU torch over a user-site CPU shadow build.

    This must happen before any torch import. Reordering sys.path is stable;
    importing torch manually via importlib spec is not.
    """

    try:
        user_site = str(site.getusersitepackages() or "").strip()
    except Exception:
        user_site = ""
    if not user_site:
        return

    try:
        conda_site = Path(sys.executable).resolve().parent / "Lib" / "site-packages"
    except Exception:
        return

    conda_torch_init = conda_site / "torch" / "__init__.py"
    user_torch_init = Path(user_site) / "torch" / "__init__.py"
    if not conda_torch_init.exists() or not user_torch_init.exists():
        return

    loaded = sys.modules.get("torch")
    loaded_path = str(getattr(loaded, "__file__", "") or "")
    if loaded_path:
        return

    conda_site_str = str(conda_site)
    user_site_str = str(user_site)
    original_path = list(sys.path)
    try:
        sys.path[:] = [item for item in sys.path if item != user_site_str]
        if conda_site_str in sys.path:
            sys.path.remove(conda_site_str)
        sys.path.insert(0, conda_site_str)
        importlib.import_module("torch")
    except Exception:
        sys.modules.pop("torch", None)
    finally:
        sys.path[:] = original_path


_prefer_conda_gpu_torch()

from langchain_huggingface import HuggingFaceEmbeddings

from .settings import get_settings

try:
    import sqlite_vec  # type: ignore
except Exception:
    sqlite_vec = None

DEFAULT_HARD_BOUNDARY_RULES = [
    "Do not encourage illegal, self-harm, violent, or dangerous behavior.",
    "Do not fabricate user facts that were never stated.",
    "Do not cross explicit refusal or safety boundaries in relationship progression.",
    "External factual claims must be traceable to sources.",
]


@dataclass
class MemoryCandidate:
    kind: str  # profile|relationship|moment
    key: str
    value: Any
    confidence: float | None = None


class MemoryStore:
    """Structured long-term memory store.

    - profile: stable user facts and preferences
    - relationship: the current relationship state and boundaries
    - moments: time-ordered episodic snippets with semantic retrieval support

    This class only handles storage and retrieval. Write decisions are made by
    the dialogue layer and approval flow.
    """

    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._embedder: HuggingFaceEmbeddings | None = None
        self._embedding_disabled_reason: str = ""
        self._vec_enabled: bool = False
        self._vec_dim: int | None = None
        try:
            self._init_schema()
        except Exception:
            # Release the sqlite handle on init failure; Windows otherwise
            # tends to hold the file open and break temp directory cleanup.
            try:
                self.conn.close()
            except Exception:
                pass
            raise

    @staticmethod
    def _read_bool_env(name: str) -> bool | None:
        raw = str(os.getenv(name, "") or "").strip().lower()
        if not raw:
            return None
        if raw in {"1", "true", "yes", "y", "on"}:
            return True
        if raw in {"0", "false", "no", "n", "off"}:
            return False
        return None

    @staticmethod
    def _huggingface_cache_dirs() -> list[Path]:
        out: list[Path] = []
        hub_cache = str(os.getenv("HUGGINGFACE_HUB_CACHE", "") or "").strip()
        if hub_cache:
            out.append(Path(hub_cache).expanduser())
        hf_home = str(os.getenv("HF_HOME", "") or "").strip()
        if hf_home:
            out.append(Path(hf_home).expanduser() / "hub")
        out.append(Path.home() / ".cache" / "huggingface" / "hub")

        deduped: list[Path] = []
        seen: set[str] = set()
        for path in out:
            key = str(path).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(path)
        return deduped

    @classmethod
    def _cached_embedding_model_path(cls, model_name: str) -> Path | None:
        name = str(model_name or "").strip()
        if not name:
            return None
        path = Path(name).expanduser()
        if path.exists():
            return path

        normalized = name.replace("\\", "/").strip("/")
        if not normalized or normalized.count("/") > 1:
            return None
        repo_dir = "models--" + normalized.replace("/", "--")
        for root in cls._huggingface_cache_dirs():
            repo_root = root / repo_dir
            if not repo_root.exists():
                continue
            ref_main = repo_root / "refs" / "main"
            if ref_main.exists():
                try:
                    revision = ref_main.read_text(encoding="utf-8").strip()
                except Exception:
                    revision = ""
                if revision:
                    snapshot = repo_root / "snapshots" / revision
                    if snapshot.exists():
                        return snapshot
            snapshots_dir = repo_root / "snapshots"
            if snapshots_dir.exists():
                candidates = [p for p in snapshots_dir.iterdir() if p.is_dir()]
                if candidates:
                    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                    return candidates[0]
            return repo_root
        return None

    @classmethod
    def _embedding_model_cached(cls, model_name: str) -> bool:
        return cls._cached_embedding_model_path(model_name) is not None

    def _resolve_embedding_model_name(self, model_name: str) -> str:
        cached = self._cached_embedding_model_path(model_name)
        if cached is not None:
            return str(cached)
        return str(model_name or "").strip()

    def _resolve_embedding_device(self, device_name: str) -> str:
        requested = str(device_name or "").strip() or "cpu"
        if not requested.lower().startswith("cuda"):
            return requested
        try:
            import torch

            if bool(torch.cuda.is_available()):
                return requested
        except Exception:
            pass

        self._audit_log(
            {
                "event": "embedding_device_downgraded",
                "requested_device": requested,
                "resolved_device": "cpu",
            }
        )
        return "cpu"

    def _embedding_local_files_only(self, model_name: str) -> bool:
        explicit = self._read_bool_env("AMADEUS_EMBEDDING_LOCAL_FILES_ONLY")
        if explicit is not None:
            return bool(explicit)
        if self._embedding_model_cached(model_name):
            return True
        runtime_mode = str(get_settings().runtime_mode or "").strip().lower()
        return runtime_mode == "regression"

    def _disable_embeddings(self, reason: str) -> None:
        msg = str(reason or "").strip() or "embedding disabled"
        if self._embedding_disabled_reason == msg:
            return
        self._embedding_disabled_reason = msg
        self._embedder = None
        self._audit_log({"event": "embedding_disabled", "reason": msg})

    def _get_embedder(self) -> HuggingFaceEmbeddings:
        if self._embedder is not None:
            return self._embedder
        if self._embedding_disabled_reason:
            raise RuntimeError(self._embedding_disabled_reason)
        s = get_settings()
        model_name = self._resolve_embedding_model_name(s.embedding_model_name)
        device = self._resolve_embedding_device(s.embedding_device)
        try:
            self._embedder = HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs={
                    "device": device,
                    "trust_remote_code": bool(s.embedding_trust_remote_code),
                    "local_files_only": self._embedding_local_files_only(model_name),
                },
                encode_kwargs={"normalize_embeddings": bool(s.embedding_normalize)},
            )
        except Exception as e:
            reason = f"{type(e).__name__}: {e}"
            self._disable_embeddings(reason)
            raise RuntimeError(reason) from e
        return self._embedder

    def _embed_query(self, text: str) -> list[float]:
        if self._embedding_disabled_reason:
            raise RuntimeError(self._embedding_disabled_reason)
        try:
            return self._get_embedder().embed_query(text)
        except Exception as e:
            reason = f"{type(e).__name__}: {e}"
            self._disable_embeddings(reason)
            raise RuntimeError(reason) from e

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if not a or not b:
            return -1.0
        n = min(len(a), len(b))
        dot = 0.0
        na = 0.0
        nb = 0.0
        for i in range(n):
            x = float(a[i])
            y = float(b[i])
            dot += x * y
            na += x * x
            nb += y * y
        if na <= 0.0 or nb <= 0.0:
            return -1.0
        return dot / (math.sqrt(na) * math.sqrt(nb))

    @staticmethod
    def _clamp_signed(value: Any, low: float = -1.5, high: float = 1.5, default: float = 0.0) -> float:
        try:
            v = float(value)
        except Exception:
            v = float(default)
        return max(float(low), min(float(high), v))

    @staticmethod
    def _recent_item_sort_key(item: dict[str, Any], *time_fields: str) -> tuple[int, int]:
        ts = 0
        for field in time_fields:
            try:
                ts = int(item.get(field) or 0)
            except Exception:
                ts = 0
            if ts > 0:
                break
        try:
            rid = int(item.get("id") or 0)
        except Exception:
            rid = 0
        return (ts, rid)

    @staticmethod
    def _relationship_stage_from_scores(
        affinity_score: float,
        trust_score: float,
        *,
        evidence_density: float = 0.0,
        positive_count: int = 0,
        negative_count: int = 0,
        recent_positive: float = 0.0,
        recent_negative: float = 0.0,
        repair_count: int = 0,
        prior_stage: str = "",
    ) -> str:
        affinity = float(affinity_score)
        trust = float(trust_score)
        stage = str(prior_stage or "").strip().lower()
        if affinity <= -0.75 or trust <= -0.75:
            return "strained"
        if negative_count >= 2 and recent_negative >= 0.55 and (affinity <= 0.22 or trust <= 0.22):
            return "strained"
        if stage in {"warming", "trusted"} and negative_count >= 2 and recent_negative >= 0.62 and (affinity <= 0.32 or trust <= 0.32):
            return "strained"
        if affinity >= 1.5 and trust >= 1.5 and evidence_density >= 0.52 and recent_negative <= 0.28:
            return "trusted"
        if stage == "trusted" and affinity >= 0.90 and trust >= 0.90 and recent_negative <= 0.34:
            return "trusted"
        if stage == "trusted" and (recent_negative >= 0.34 or negative_count >= 2):
            return "warming"
        if (
            (affinity >= 0.45 and trust >= 0.45 and evidence_density >= 0.34)
            or (positive_count >= 3 and (affinity >= 0.18 or trust >= 0.18))
            or (evidence_density >= 0.58 and recent_positive >= 0.28 and (affinity >= 0.16 or trust >= 0.16))
        ):
            if negative_count >= 2 and recent_negative >= 0.46 and affinity < 0.32 and trust < 0.32:
                return "friend"
            return "warming"
        if stage in {"warming", "trusted"} and (affinity >= 0.18 or trust >= 0.18):
            if negative_count >= 2 and recent_negative >= 0.48 and affinity < 0.28 and trust < 0.28:
                return "friend"
            return "warming"
        return "friend"

    @staticmethod
    def _relationship_evidence_stats(
        timeline: list[dict[str, Any]] | None,
        *,
        repair_count: int = 0,
    ) -> dict[str, float]:
        items = list(timeline or [])
        positive_count = 0
        negative_count = 0
        weighted_positive = 0.0
        weighted_negative = 0.0
        positive_strength = 0.0
        negative_strength = 0.0
        for idx, item in enumerate(items):
            try:
                affinity_delta = float(item.get("affinity_delta", 0.0) or 0.0)
            except Exception:
                affinity_delta = 0.0
            try:
                trust_delta = float(item.get("trust_delta", 0.0) or 0.0)
            except Exception:
                trust_delta = 0.0
            signed = 0.5 * affinity_delta + 0.5 * trust_delta
            magnitude = min(1.0, (abs(affinity_delta) + abs(trust_delta)) / 0.35)
            recency_weight = max(0.35, 1.0 - 0.12 * idx)
            if signed >= 0.025:
                positive_count += 1
                positive_strength += magnitude
                weighted_positive += recency_weight * magnitude
            elif signed <= -0.025:
                negative_count += 1
                negative_strength += magnitude
                weighted_negative += recency_weight * magnitude
        evidence_density = min(1.0, len(items) / 5.0)
        positive_density = min(1.0, positive_count / 4.0)
        negative_density = min(1.0, negative_count / 3.0)
        recent_positive = min(1.0, weighted_positive / 2.2)
        recent_negative = min(1.0, weighted_negative / 2.0)
        return {
            "evidence_density": evidence_density,
            "positive_count": float(positive_count),
            "negative_count": float(negative_count),
            "positive_density": positive_density,
            "negative_density": negative_density,
            "positive_strength": min(1.0, positive_strength / max(1.0, float(positive_count or 1))),
            "negative_strength": min(1.0, negative_strength / max(1.0, float(negative_count or 1))),
            "recent_positive": recent_positive,
            "recent_negative": recent_negative,
        }

    def _audit_log(self, record: dict[str, Any]) -> None:
        """Best-effort audit logging for internal memory-store failures."""
        try:
            s = get_settings()
            s.data_dir.mkdir(parents=True, exist_ok=True)
            path = s.data_dir / "memory_store_audit.jsonl"
            rec = {"ts": int(time.time()), **record}
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass

    def _init_sqlite_vec_indexes(self) -> None:
        """Initialize optional sqlite-vec virtual tables for KNN retrieval.

        Behavior:
        - default: best-effort with embedding+Python fallback
        - force mode: `AMADEUS_SQLITE_VEC=on` raises if init fails
        """

        mode = str(os.getenv("AMADEUS_SQLITE_VEC", "off") or "off").strip().lower()
        force = mode in {"1", "true", "yes", "y", "on"}
        if mode in {"0", "false", "no", "n", "off"}:
            self._vec_enabled = False
            return

        if sqlite_vec is None:
            self._vec_enabled = False
            if force:
                raise RuntimeError("sqlite-vec is required but not available (import sqlite_vec failed)")
            return

        try:
            self.conn.enable_load_extension(True)
            sqlite_vec.load(self.conn)
            self.conn.enable_load_extension(False)
        except Exception as e:
            self._vec_enabled = False
            self._audit_log(
                {
                    "event": "sqlite_vec_init_failed",
                    "error": f"{type(e).__name__}: {e}",
                    "sqlite_version": getattr(sqlite3, "sqlite_version", ""),
                    "platform": os.name,
                }
            )
            if force:
                raise RuntimeError(f"sqlite-vec init failed: {type(e).__name__}: {e}")
            return

        try:
            probe = self._embed_query("dimension probe")
            dim = int(len(probe))
            if dim <= 0:
                self._vec_enabled = False
                return
            self._vec_dim = dim
        except Exception:
            self._vec_enabled = False
            return

        try:
            # sqlite-vec support differs slightly across builds. Keep the vector
            # table minimal here and store extra metadata in regular tables.
            self.conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS moments_vss USING vec0(
                  moment_id INTEGER PRIMARY KEY,
                  embedding float[%d] distance_metric=cosine
                )
                """
                % self._vec_dim
            )
            self.conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS reflections_vss USING vec0(
                  reflection_id INTEGER PRIMARY KEY,
                  embedding float[%d] distance_metric=cosine
                )
                """
                % self._vec_dim
            )
            self.conn.commit()
            self._vec_enabled = True
        except Exception as e:
            self._vec_enabled = False
            self._audit_log(
                {
                    "event": "sqlite_vec_create_vtable_failed",
                    "error": f"{type(e).__name__}: {e}",
                    "vec_dim": self._vec_dim,
                }
            )
            if force:
                raise RuntimeError(f"sqlite-vec create vtable failed: {type(e).__name__}: {e}")

    def _vec_param(self, vec: list[float]) -> object:
        if sqlite_vec is None:
            return json.dumps(vec, ensure_ascii=False)
        try:
            return sqlite_vec.serialize_float32(vec)  # type: ignore[attr-defined]
        except Exception:
            return json.dumps(vec, ensure_ascii=False)

    def __enter__(self) -> "MemoryStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _init_schema(self) -> None:
        # Long-term key-value store. Namespaces keep memory types separated and
        # align well with LangGraph-style persistence patterns.
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS store_kv (
              namespace TEXT NOT NULL,
              k TEXT NOT NULL,
              v TEXT NOT NULL,
              updated_at INTEGER NOT NULL,
              PRIMARY KEY(namespace, k)
            )
            """
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_store_kv_namespace ON store_kv(namespace)"
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_ledger (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              record_type TEXT NOT NULL,
              namespace TEXT NOT NULL,
              key_name TEXT NOT NULL,
              before_v TEXT,
              after_v TEXT,
              reason TEXT NOT NULL DEFAULT '',
              operator TEXT NOT NULL DEFAULT 'system',
              source TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL DEFAULT 'active',
              created_at INTEGER NOT NULL
            )
            """
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memory_ledger_created_at ON memory_ledger(created_at)"
        )

        # Legacy tables stay opt-in. New databases should write to `store_kv`
        # only to avoid duplicated and stale storage.
        legacy_enabled = str(__import__("os").getenv("AMADEUS_LEGACY_TABLES", "0")).strip().lower() in {"1", "true", "yes", "y", "on"}
        if legacy_enabled:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS profile (
                  k TEXT PRIMARY KEY,
                  v TEXT NOT NULL,
                  updated_at INTEGER NOT NULL
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS relationship (
                  id INTEGER PRIMARY KEY CHECK (id = 1),
                  v TEXT NOT NULL,
                  updated_at INTEGER NOT NULL
                )
                """
            )
        else:
            self._audit_log({"event": "legacy_tables_disabled"})

        # `moments` is core storage and should exist regardless of legacy mode.
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS moments (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              summary TEXT NOT NULL,
              tags TEXT NOT NULL DEFAULT '[]',
              links TEXT NOT NULL DEFAULT '[]',
              created_at INTEGER NOT NULL,
              superseded_by INTEGER,
              merged_from TEXT NOT NULL DEFAULT '[]'
            )
            """
        )

        # Moment embeddings live in a plain table first so local inspection and
        # future backend swaps stay straightforward.
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS moments_vec (
              moment_id INTEGER PRIMARY KEY,
              embedding TEXT NOT NULL,
              updated_at INTEGER NOT NULL,
              FOREIGN KEY(moment_id) REFERENCES moments(id) ON DELETE CASCADE
            )
            """
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_moments_vec_updated_at ON moments_vec(updated_at)"
        )

        # Basic indexes still matter once the store grows beyond a toy size.
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_moments_created_at ON moments(created_at)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_moments_summary ON moments(summary)"
        )

        # Reflections are semantic summaries distilled from episodic moments.
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reflections (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              text TEXT NOT NULL,
              derived_from TEXT NOT NULL DEFAULT '[]',
              importance REAL NOT NULL DEFAULT 0.5,
              created_at INTEGER NOT NULL
            )
            """
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_reflections_created_at ON reflections(created_at)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_reflections_text ON reflections(text)"
        )

        # Separate embedding table for reflections.
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reflections_vec (
              reflection_id INTEGER PRIMARY KEY,
              embedding TEXT NOT NULL,
              updated_at INTEGER NOT NULL,
              FOREIGN KEY(reflection_id) REFERENCES reflections(id) ON DELETE CASCADE
            )
            """
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_reflections_vec_updated_at ON reflections_vec(updated_at)"
        )

        # Optional sqlite-vec indexes upgrade vector retrieval from Python-side
        # reranking to in-database nearest-neighbor search.

        # Lightweight compatibility migration for older `moments` schemas.
        cols = {
            row[1] for row in self.conn.execute("PRAGMA table_info(moments)").fetchall()
        }
        if "tags" not in cols:
            self.conn.execute("ALTER TABLE moments ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'")
        if "links" not in cols:
            self.conn.execute("ALTER TABLE moments ADD COLUMN links TEXT NOT NULL DEFAULT '[]'")
        if "superseded_by" not in cols:
            self.conn.execute("ALTER TABLE moments ADD COLUMN superseded_by INTEGER")
        if "merged_from" not in cols:
            self.conn.execute("ALTER TABLE moments ADD COLUMN merged_from TEXT NOT NULL DEFAULT '[]'")

        # One-time legacy -> store_kv migration. The meta flag prevents repeated
        # imports if the user partially clears the new store.
        migrated_at = self._store_get("meta", "migrated_from_legacy_at")

        cur2 = self.conn.execute("SELECT COUNT(1) FROM store_kv")
        store_cnt = int(cur2.fetchone()[0] or 0)
        should_migrate = bool(store_cnt == 0 and migrated_at is None)

        if should_migrate and legacy_enabled:
            # profile
            cur_p = self.conn.execute("SELECT k, v FROM profile")
            for k, v in cur_p.fetchall():
                try:
                    vv = json.loads(v)
                except Exception:
                    vv = v
                self.conn.execute(
                    "INSERT OR REPLACE INTO store_kv(namespace, k, v, updated_at) VALUES(?, ?, ?, ?)",
                    ("profile", k, json.dumps(vv, ensure_ascii=False), int(time.time())),
                )

            # relationship
            cur_r = self.conn.execute("SELECT v FROM relationship WHERE id=1")
            row_r = cur_r.fetchone()
            if row_r and row_r[0]:
                try:
                    rv = json.loads(row_r[0])
                except Exception:
                    rv = {"stage": "friend", "notes": str(row_r[0])}
            else:
                rv = {"stage": "friend", "notes": ""}
            self.conn.execute(
                "INSERT OR REPLACE INTO store_kv(namespace, k, v, updated_at) VALUES(?, ?, ?, ?)",
                ("relationship", "state", json.dumps(rv, ensure_ascii=False), int(time.time())),
            )

            # Mark legacy migration as completed.
            self._store_put("meta", "migrated_from_legacy_at", int(time.time()))
        elif should_migrate and (not legacy_enabled):
            # Fresh databases without legacy tables still record the migration
            # marker so later startup paths do not re-enter this branch.
            self._store_put("meta", "migrated_from_legacy_at", int(time.time()))

        # Ensure `relationship.state` always exists in the new key-value store.
        cur3 = self.conn.execute(
            "SELECT v FROM store_kv WHERE namespace=? AND k=?", ("relationship", "state")
        )
        if cur3.fetchone() is None:
            self.conn.execute(
                "INSERT OR REPLACE INTO store_kv(namespace, k, v, updated_at) VALUES(?, ?, ?, ?)",
                (
                    "relationship",
                    "state",
                    json.dumps({"stage": "friend", "notes": ""}, ensure_ascii=False),
                    int(time.time()),
                ),
            )

        # Ensure hard boundary rules always exist in canon_facts.
        canon = self._store_get("canon_facts", "hard_boundary_rules")
        if not isinstance(canon, list) or not canon:
            self._store_put("canon_facts", "hard_boundary_rules", list(DEFAULT_HARD_BOUNDARY_RULES))

        self.conn.commit()

    # -------- store (namespace+key) --------
    _MOJIBAKE_HINT_CHARS = set("鍦鍚鍒鍙浠浣犺繖閭鎴戠殑鐨涓婁笅璇鎯銆傦紵锛岋紒")
    _MOJIBAKE_HINT_PATTERNS = (
        "浣犲",
        "鍦ㄥ",
        "涓婃",
        "鎴戜",
        "璇存",
        "鐨勬",
        "鎯宠",
        "杩欎",
        "閭ｄ",
        "銆傞",
        "锛屼",
        "浠栦",
    )

    @classmethod
    def _mojibake_score(cls, text: str) -> int:
        raw = str(text or "")
        if not raw:
            return 0
        score = 0
        for ch in raw:
            if ch in cls._MOJIBAKE_HINT_CHARS:
                score += 1
        for pattern in cls._MOJIBAKE_HINT_PATTERNS:
            score += raw.count(pattern) * 2
        score += raw.count("锟")
        score += raw.count("鈥")
        return score

    @classmethod
    def _repair_common_mojibake(cls, text: str) -> str:
        raw = str(text or "")
        if not raw:
            return ""
        base_score = cls._mojibake_score(raw)
        if base_score < 2:
            return raw

        best = raw
        best_score = base_score
        min_len = max(2, int(len(raw) * 0.6))
        for enc in ("gb18030", "gbk"):
            try:
                candidate = raw.encode(enc, "ignore").decode("utf-8", "ignore")
            except Exception:
                continue
            candidate = candidate.encode("utf-8", "ignore").decode("utf-8")
            if not candidate or len(candidate) < min_len:
                continue
            score = cls._mojibake_score(candidate)
            if score < best_score and score <= max(0, base_score - 2):
                best = candidate
                best_score = score
        return best

    @staticmethod
    def _sanitize_text(text: str) -> str:
        raw = str(text or "").encode("utf-8", "ignore").decode("utf-8")
        parts = re.split(r"(\s+|\|)", raw)
        if len(parts) > 1:
            return "".join(
                part if idx % 2 == 1 else MemoryStore._repair_common_mojibake(part)
                for idx, part in enumerate(parts)
            )
        return MemoryStore._repair_common_mojibake(raw)

    @classmethod
    def _sanitize_obj(cls, value: Any) -> Any:
        if isinstance(value, str):
            return cls._sanitize_text(value)
        if isinstance(value, list):
            return [cls._sanitize_obj(x) for x in value]
        if isinstance(value, tuple):
            return tuple(cls._sanitize_obj(x) for x in value)
        if isinstance(value, dict):
            out: dict[Any, Any] = {}
            for k, v in value.items():
                out[cls._sanitize_obj(k)] = cls._sanitize_obj(v)
            return out
        return value

    @staticmethod
    def _safe_json_for_db(value: Any) -> str:
        """Serialize JSON safely for sqlite text storage."""
        value = MemoryStore._sanitize_obj(value)
        try:
            raw = json.dumps(value, ensure_ascii=False)
        except Exception:
            raw = json.dumps(str(value), ensure_ascii=True)
        # Guard against invalid surrogate chars that break sqlite utf-8 encoding.
        return raw.encode("utf-8", "backslashreplace").decode("utf-8")

    def _store_put(self, namespace: str, key: str, value: Any) -> None:
        self.conn.execute(
            "INSERT INTO store_kv(namespace, k, v, updated_at) VALUES(?, ?, ?, ?) "
            "ON CONFLICT(namespace, k) DO UPDATE SET v=excluded.v, updated_at=excluded.updated_at",
            (namespace, key, self._safe_json_for_db(value), int(time.time())),
        )
        self.conn.commit()

    def _store_get(self, namespace: str, key: str) -> Any | None:
        cur = self.conn.execute("SELECT v FROM store_kv WHERE namespace=? AND k=?", (namespace, key))
        row = cur.fetchone()
        if not row:
            return None
        try:
            return self._sanitize_obj(json.loads(row[0]))
        except Exception:
            return self._sanitize_obj(row[0])

    def _store_delete(self, namespace: str, key: str) -> bool:
        cur = self.conn.execute("DELETE FROM store_kv WHERE namespace=? AND k=?", (namespace, key))
        self.conn.commit()
        return cur.rowcount > 0

    def _store_list(self, namespace: str) -> dict[str, Any]:
        cur = self.conn.execute("SELECT k, v FROM store_kv WHERE namespace=? ORDER BY k", (namespace,))
        out: dict[str, Any] = {}
        for k, v in cur.fetchall():
            try:
                out[k] = self._sanitize_obj(json.loads(v))
            except Exception:
                out[k] = self._sanitize_obj(v)
        return out

    def _list_ns_items(self, namespace: str, key: str = "items") -> list[dict[str, Any]]:
        raw = self._store_get(namespace, key)
        if not isinstance(raw, list):
            return []
        out: list[dict[str, Any]] = []
        for it in raw:
            if isinstance(it, dict):
                out.append(it)
        return out

    def _put_ns_items(self, namespace: str, items: list[dict[str, Any]], key: str = "items") -> None:
        self._store_put(namespace, key, items)

    def _next_item_id(self, items: list[dict[str, Any]]) -> int:
        max_id = 0
        for it in items:
            try:
                max_id = max(max_id, int(it.get("id") or 0))
            except Exception:
                continue
        return max_id + 1

    def _append_ns_item(
        self,
        namespace: str,
        item: dict[str, Any],
        *,
        key: str = "items",
        max_items: int = 500,
    ) -> dict[str, Any]:
        items = self._list_ns_items(namespace, key=key)
        now = int(time.time())
        rec = {**item}
        if "id" not in rec:
            rec["id"] = self._next_item_id(items)
        if "created_at" not in rec:
            rec["created_at"] = now
        items.append(rec)
        if len(items) > int(max_items):
            items = items[-int(max_items):]
        self._put_ns_items(namespace, items, key=key)
        return rec

    @staticmethod
    def _text_units(text: Any) -> set[str]:
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

    @classmethod
    def _text_overlap_score(cls, a: Any, b: Any) -> float:
        au = cls._text_units(a)
        bu = cls._text_units(b)
        if not au or not bu:
            return 0.0
        denom = max(1, min(len(au), 6))
        return max(0.0, min(1.0, float(len(au & bu)) / float(denom)))

    @staticmethod
    def _json_dumps(value: Any) -> str:
        value = MemoryStore._sanitize_obj(value)
        try:
            raw = json.dumps(value, ensure_ascii=False)
        except Exception:
            raw = json.dumps(str(value), ensure_ascii=True)
        return raw.encode("utf-8", "backslashreplace").decode("utf-8")

    @staticmethod
    def _json_loads(raw: str | None) -> Any:
        if raw is None:
            return None
        try:
            return MemoryStore._sanitize_obj(json.loads(raw))
        except Exception:
            return MemoryStore._sanitize_obj(raw)

    def append_memory_ledger(
        self,
        *,
        record_type: str,
        namespace: str,
        key_name: str,
        before: Any,
        after: Any,
        reason: str = "",
        operator: str = "system",
        source: str = "",
        status: str = "active",
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO memory_ledger(
              record_type, namespace, key_name, before_v, after_v,
              reason, operator, source, status, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(record_type or "").strip() or "generic",
                str(namespace or "").strip() or "unknown",
                str(key_name or "").strip() or "",
                self._json_dumps(before),
                self._json_dumps(after),
                str(reason or "").strip(),
                str(operator or "system").strip() or "system",
                str(source or "").strip(),
                str(status or "active").strip() or "active",
                int(time.time()),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid or 0)

    def list_memory_ledger(self, limit: int = 50) -> list[dict[str, Any]]:
        lim = max(1, min(500, int(limit)))
        cur = self.conn.execute(
            """
            SELECT id, record_type, namespace, key_name, before_v, after_v,
                   reason, operator, source, status, created_at
            FROM memory_ledger
            ORDER BY id DESC
            LIMIT ?
            """,
            (lim,),
        )
        out: list[dict[str, Any]] = []
        for row in cur.fetchall():
            (
                rid,
                record_type,
                namespace,
                key_name,
                before_v,
                after_v,
                reason,
                operator,
                source,
                status,
                created_at,
            ) = row
            out.append(
                {
                    "id": int(rid),
                    "record_type": str(record_type),
                    "namespace": str(namespace),
                    "key_name": str(key_name),
                    "before": self._json_loads(before_v),
                    "after": self._json_loads(after_v),
                    "reason": str(reason or ""),
                    "operator": str(operator or ""),
                    "source": str(source or ""),
                    "status": str(status or "active"),
                    "created_at": int(created_at or 0),
                }
            )
        return out

    def mark_memory_ledger_status(self, change_id: int, status: str) -> bool:
        cur = self.conn.execute(
            "UPDATE memory_ledger SET status=? WHERE id=?",
            (str(status or "active"), int(change_id)),
        )
        self.conn.commit()
        return bool(cur.rowcount > 0)

    def rollback_memory_change(self, change_id: int, *, reason: str = "", operator: str = "system") -> bool:
        cur = self.conn.execute(
            """
            SELECT id, namespace, key_name, before_v, after_v, status
            FROM memory_ledger
            WHERE id=?
            """,
            (int(change_id),),
        )
        row = cur.fetchone()
        if not row:
            return False
        _, namespace, key_name, before_v, after_v, status = row
        if str(status or "").strip().lower() == "rolled_back":
            return False

        before = self._json_loads(before_v)
        after = self._json_loads(after_v)
        ns = str(namespace or "")
        key = str(key_name or "")

        if ns == "profile":
            if before is None:
                self.delete_profile(key)
            else:
                self.set_profile(key, before)
        elif ns == "relationship" and key == "state":
            if isinstance(before, dict):
                self.set_relationship(before)
            else:
                return False
        elif ns == "store_kv":
            if before is None:
                self._store_delete("profile", key)
            else:
                self._store_put("profile", key, before)
        else:
            return False

        self.mark_memory_ledger_status(int(change_id), "rolled_back")
        self.append_memory_ledger(
            record_type="rollback",
            namespace=ns,
            key_name=key,
            before=after,
            after=before,
            reason=str(reason or "").strip() or "manual rollback",
            operator=str(operator or "system"),
            source=f"ledger:{int(change_id)}",
            status="active",
        )
        return True

    def list_memory_quarantine(self, limit: int = 50) -> list[dict[str, Any]]:
        items = self._list_ns_items("memory_quarantine")
        items.sort(key=lambda x: self._recent_item_sort_key(x, "created_at"), reverse=True)
        return items[: max(1, min(500, int(limit)))]

    def add_memory_quarantine(
        self,
        *,
        tool_name: str,
        args: dict[str, Any],
        reason: str,
        confidence: float | None = None,
    ) -> dict[str, Any]:
        conf = None
        if confidence is not None:
            try:
                conf = float(confidence)
            except Exception:
                conf = None
        rec = self._append_ns_item(
            "memory_quarantine",
            {
                "tool_name": str(tool_name or "").strip(),
                "args": args if isinstance(args, dict) else {"raw": str(args)},
                "reason": str(reason or "").strip(),
                "confidence": conf,
                "status": "quarantine",
            },
            max_items=2000,
        )
        self.append_memory_ledger(
            record_type="quarantine",
            namespace="memory_quarantine",
            key_name=str(rec.get("id") or ""),
            before=None,
            after=rec,
            reason=str(reason or "").strip(),
            operator="memory_guard",
            source=str(tool_name or ""),
            status="active",
        )
        return rec

    def resolve_memory_quarantine(self, quarantine_id: int, status: str = "resolved") -> bool:
        items = self._list_ns_items("memory_quarantine")
        qid = int(quarantine_id)
        updated = False
        for it in items:
            try:
                if int(it.get("id") or 0) != qid:
                    continue
            except Exception:
                continue
            it["status"] = str(status or "resolved").strip() or "resolved"
            it["resolved_at"] = int(time.time())
            updated = True
            break
        if updated:
            self._put_ns_items("memory_quarantine", items)
        return updated

    # -------- profile --------
    def get_profile(self) -> dict[str, Any]:
        return self._store_list("profile")

    def get_profile_meta(self) -> dict[str, Any]:
        """Return profile metadata for provenance/correction history."""
        return self._store_list("profile_meta")

    def set_profile(self, key: str, value: Any) -> None:
        self._store_put("profile", key, value)

    def set_profile_meta(self, key: str, meta: dict[str, Any]) -> None:
        self._store_put("profile_meta", key, meta)

    def delete_profile(self, key: str) -> bool:
        # Best effort: deleting a profile key should also clear its metadata.
        try:
            self._store_delete("profile_meta", key)
        except Exception:
            pass
        return self._store_delete("profile", key)

    # -------- relationship --------
    def _derive_relationship_state(self) -> dict[str, Any]:
        timeline = self.list_relationship_timeline(limit=12)
        repairs = self.list_conflict_repairs(limit=6)
        affinity_score = 0.0
        trust_score = 0.0
        for item in timeline:
            try:
                affinity_score += float(item.get("affinity_delta", 0.0) or 0.0)
            except Exception:
                pass
            try:
                trust_score += float(item.get("trust_delta", 0.0) or 0.0)
            except Exception:
                pass

        latest_timeline = timeline[0] if timeline else {}
        latest_repair = repairs[0] if repairs else {}
        notes = str(latest_timeline.get("summary") or latest_repair.get("summary") or "").strip()
        stats = self._relationship_evidence_stats(timeline, repair_count=len(repairs))
        stage = self._relationship_stage_from_scores(
            affinity_score,
            trust_score,
            evidence_density=float(stats.get("evidence_density", 0.0) or 0.0),
            positive_count=int(stats.get("positive_count", 0.0) or 0.0),
            negative_count=int(stats.get("negative_count", 0.0) or 0.0),
            recent_positive=float(stats.get("recent_positive", 0.0) or 0.0),
            recent_negative=float(stats.get("recent_negative", 0.0) or 0.0),
            repair_count=len(repairs),
            prior_stage=str(latest_repair.get("stage") or ""),
        )

        return {
            "stage": stage,
            "notes": notes,
            "affinity_score": round(float(affinity_score), 3),
            "trust_score": round(float(trust_score), 3),
            "derived": True,
        }

    def get_relationship(self) -> dict[str, Any]:
        stored = self._store_get("relationship", "state")
        base = stored if isinstance(stored, dict) else {}
        derived = self._derive_relationship_state()
        explicit_stage = str(base.get("stage") or "").strip()
        explicit_notes = str(base.get("notes") or "").strip()
        try:
            base_affinity = float(base.get("affinity_score", 0.0) or 0.0)
        except Exception:
            base_affinity = 0.0
        try:
            base_trust = float(base.get("trust_score", 0.0) or 0.0)
        except Exception:
            base_trust = 0.0
        try:
            derived_affinity = float(derived.get("affinity_score", 0.0) or 0.0)
        except Exception:
            derived_affinity = 0.0
        try:
            derived_trust = float(derived.get("trust_score", 0.0) or 0.0)
        except Exception:
            derived_trust = 0.0
        timeline = self.list_relationship_timeline(limit=12)
        repairs = self.list_conflict_repairs(limit=6)
        timeline_count = len(timeline)
        repair_count = len(repairs)
        stats = self._relationship_evidence_stats(timeline, repair_count=repair_count)
        evidence_density = float(stats.get("evidence_density", 0.0) or 0.0)
        positive_count = int(stats.get("positive_count", 0.0) or 0.0)
        negative_count = int(stats.get("negative_count", 0.0) or 0.0)
        recent_positive = float(stats.get("recent_positive", 0.0) or 0.0)
        recent_negative = float(stats.get("recent_negative", 0.0) or 0.0)

        use_explicit = bool(explicit_stage and explicit_stage != "friend")
        if explicit_notes and not use_explicit:
            use_explicit = True

        if use_explicit:
            low_anchor = (
                explicit_stage.lower() in {"", "friend"}
                and abs(base_affinity) <= 0.24
                and abs(base_trust) <= 0.24
            )
            if timeline_count or repair_count:
                if low_anchor:
                    merged_affinity = self._clamp_signed(base_affinity + derived_affinity)
                    merged_trust = self._clamp_signed(base_trust + derived_trust)
                else:
                    absorb = min(
                        0.62,
                        0.24
                        + 0.18 * evidence_density
                        + 0.06 * min(3, negative_count),
                    )
                    merged_affinity = self._clamp_signed(base_affinity + absorb * derived_affinity)
                    merged_trust = self._clamp_signed(base_trust + absorb * derived_trust)
            else:
                merged_affinity = self._clamp_signed(base_affinity)
                merged_trust = self._clamp_signed(base_trust)
            out = dict(base)
            out["stage"] = self._relationship_stage_from_scores(
                merged_affinity,
                merged_trust,
                evidence_density=evidence_density,
                positive_count=positive_count,
                negative_count=negative_count,
                recent_positive=recent_positive,
                recent_negative=recent_negative,
                repair_count=repair_count,
                prior_stage=explicit_stage,
            )
            out["affinity_score"] = round(float(merged_affinity), 3)
            out["trust_score"] = round(float(merged_trust), 3)
            out.setdefault("derived", False)
            return out

        stage = explicit_stage
        if stage in {"", "friend"}:
            stage = self._relationship_stage_from_scores(
                derived_affinity,
                derived_trust,
                evidence_density=evidence_density,
                positive_count=positive_count,
                negative_count=negative_count,
                recent_positive=recent_positive,
                recent_negative=recent_negative,
                repair_count=repair_count,
                prior_stage=str(derived.get("stage") or "friend"),
            )

        return {
            "stage": stage,
            "notes": explicit_notes or str(derived.get("notes") or ""),
            "affinity_score": round(float(derived_affinity), 3),
            "trust_score": round(float(derived_trust), 3),
            "derived": True,
        }

    def set_relationship(self, value: dict[str, Any]) -> None:
        self._store_put("relationship", "state", value)

    # -------- skills (Voyager-style, text-only) --------
    def list_skills(self) -> list[dict[str, Any]]:
        v = self._store_get("skills", "library")
        if not isinstance(v, list):
            return []
        out: list[dict[str, Any]] = []
        for it in v[:100]:
            if isinstance(it, dict) and it.get("name"):
                out.append(it)
        return out

    def add_skill(self, name: str, description: str, steps: list[str] | None = None) -> None:
        nm = (name or "").strip()
        if not nm:
            raise ValueError("empty name")
        desc = (description or "").strip()
        if not desc:
            raise ValueError("empty description")
        st = [str(x).strip() for x in (steps or []) if str(x).strip()]
        skill = {"name": nm, "description": desc, "steps": st[:12], "created_at": int(time.time())}
        cur = self.list_skills()
        # Deduplicate by skill name.
        cur2 = [s for s in cur if str(s.get("name")).strip() != nm]
        cur2.insert(0, skill)
        self._store_put("skills", "library", cur2[:100])

    def _to_memory_record(
        self,
        *,
        record_type: str,
        content: dict[str, Any],
        confidence: float = 0.8,
        source_refs: list[int] | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "type": str(record_type or "").strip() or "memory",
            "content": content,
            "source_refs": [int(x) for x in (source_refs or []) if int(x) > 0],
            "confidence": max(0.0, min(1.0, float(confidence))),
            "status": str(status or "active").strip() or "active",
            "updated_at": int(time.time()),
        }
        if isinstance(content, dict):
            rec.update(content)
        return rec

    def list_identity_facts(self, limit: int = 30) -> list[dict[str, Any]]:
        items = self._list_ns_items("identity_facts")
        items.sort(key=lambda x: self._recent_item_sort_key(x, "created_at"), reverse=True)
        return items[: int(limit)]

    def add_identity_fact(
        self,
        *,
        summary: str,
        confidence: float = 0.8,
        source_refs: list[int] | None = None,
    ) -> dict[str, Any]:
        s = str(summary or "").strip()
        if not s:
            raise ValueError("empty identity fact")
        return self._append_ns_item(
            "identity_facts",
            self._to_memory_record(
                record_type="identity_fact",
                content={"summary": s},
                confidence=float(confidence),
                source_refs=source_refs,
            ),
            max_items=1200,
        )

    def list_shared_events(self, limit: int = 30) -> list[dict[str, Any]]:
        items = self._list_ns_items("shared_events")
        items.sort(key=lambda x: self._recent_item_sort_key(x, "created_at"), reverse=True)
        return items[: int(limit)]

    def add_shared_event(
        self,
        *,
        summary: str,
        category: str = "shared_event",
        confidence: float = 0.8,
        source_refs: list[int] | None = None,
    ) -> dict[str, Any]:
        s = str(summary or "").strip()
        if not s:
            raise ValueError("empty shared event")
        return self._append_ns_item(
            "shared_events",
            self._to_memory_record(
                record_type="shared_event",
                content={
                    "summary": s,
                    "category": str(category or "shared_event").strip() or "shared_event",
                },
                confidence=float(confidence),
                source_refs=source_refs,
            ),
            max_items=1500,
        )

    def list_conflict_repairs(self, limit: int = 30) -> list[dict[str, Any]]:
        items = self._list_ns_items("conflict_repair")
        items.sort(key=lambda x: self._recent_item_sort_key(x, "created_at"), reverse=True)
        return items[: int(limit)]

    def add_conflict_repair(
        self,
        *,
        summary: str,
        confidence: float = 0.85,
        source_refs: list[int] | None = None,
    ) -> dict[str, Any]:
        s = str(summary or "").strip()
        if not s:
            raise ValueError("empty conflict repair")
        return self._append_ns_item(
            "conflict_repair",
            self._to_memory_record(
                record_type="conflict_repair",
                content={"summary": s},
                confidence=float(confidence),
                source_refs=source_refs,
            ),
            max_items=1200,
        )

    # -------- worldline / relationship timeline / commitments / canon facts / sources --------
    def list_worldline_events(self, limit: int = 20) -> list[dict[str, Any]]:
        items = self._list_ns_items("worldline_events")
        items.sort(key=lambda x: self._recent_item_sort_key(x, "created_at"), reverse=True)
        return items[: int(limit)]

    def add_worldline_event(
        self,
        summary: str,
        *,
        category: str = "shared_event",
        importance: float = 0.5,
        tags: list[str] | None = None,
        source_refs: list[int] | None = None,
        confidence: float = 0.8,
    ) -> dict[str, Any]:
        s = str(summary or "").strip()
        if not s:
            raise ValueError("empty worldline summary")
        imp = max(0.0, min(1.0, float(importance)))
        t = [str(x).strip() for x in (tags or []) if str(x).strip()][:12]
        rec = self._append_ns_item(
            "worldline_events",
            self._to_memory_record(
                record_type="worldline_event",
                content={
                    "summary": s,
                    "category": str(category or "shared_event").strip() or "shared_event",
                    "importance": imp,
                    "tags": t,
                },
                confidence=float(confidence),
                source_refs=source_refs,
            ),
            max_items=1000,
        )
        c = str(category or "").strip().lower()
        if c in {"shared_event", "event"}:
            try:
                self.add_shared_event(
                    summary=s,
                    category=c or "shared_event",
                    confidence=confidence,
                    source_refs=source_refs,
                )
            except Exception:
                pass
        elif c in {"repair", "conflict_repair"}:
            try:
                self.add_conflict_repair(summary=s, confidence=confidence, source_refs=source_refs)
            except Exception:
                pass
        return rec

    def list_relationship_timeline(self, limit: int = 20) -> list[dict[str, Any]]:
        items = self._list_ns_items("relationship_timeline")
        items.sort(key=lambda x: self._recent_item_sort_key(x, "created_at"), reverse=True)
        return items[: int(limit)]

    def add_relationship_timeline(
        self,
        summary: str,
        *,
        affinity_delta: float = 0.0,
        trust_delta: float = 0.0,
        confidence: float = 0.8,
        source_refs: list[int] | None = None,
    ) -> dict[str, Any]:
        s = str(summary or "").strip()
        if not s:
            raise ValueError("empty relationship summary")
        return self._append_ns_item(
            "relationship_timeline",
            self._to_memory_record(
                record_type="relationship_timeline",
                content={
                    "summary": s,
                    "affinity_delta": float(affinity_delta),
                    "trust_delta": float(trust_delta),
                },
                confidence=float(confidence),
                source_refs=source_refs,
            ),
            max_items=800,
        )

    def list_commitments(self, limit: int = 50) -> list[dict[str, Any]]:
        items = self._list_ns_items("commitments")
        items.sort(key=lambda x: self._recent_item_sort_key(x, "created_at"), reverse=True)
        return items[: int(limit)]

    def add_commitment(
        self,
        text: str,
        *,
        due_at: str = "",
        status: str = "open",
        confidence: float = 0.85,
        source_refs: list[int] | None = None,
    ) -> dict[str, Any]:
        t = str(text or "").strip()
        if not t:
            raise ValueError("empty commitment text")
        return self._append_ns_item(
            "commitments",
            self._to_memory_record(
                record_type="commitment",
                content={
                    "text": t,
                    "due_at": str(due_at or "").strip(),
                    "status": str(status or "open").strip() or "open",
                    "resolved_at": 0,
                    "resolution": "",
                },
                confidence=float(confidence),
                source_refs=source_refs,
            ),
            max_items=600,
        )

    def resolve_commitment(self, commitment_id: int, resolution: str) -> bool:
        items = self._list_ns_items("commitments")
        updated = False
        rid = int(commitment_id)
        now = int(time.time())
        for it in items:
            try:
                if int(it.get("id") or 0) != rid:
                    continue
            except Exception:
                continue
            content = it.get("content") if isinstance(it.get("content"), dict) else {}
            content["status"] = "resolved"
            content["resolution"] = str(resolution or "").strip()
            content["resolved_at"] = now
            it["content"] = content
            it["status"] = "resolved"
            it["resolution"] = str(resolution or "").strip()
            it["resolved_at"] = now
            it["updated_at"] = now
            updated = True
            break
        if updated:
            self._put_ns_items("commitments", items)
        return updated

    def list_unresolved_tensions(self, limit: int = 30) -> list[dict[str, Any]]:
        items = self._list_ns_items("unresolved_tensions")
        items.sort(key=lambda x: self._recent_item_sort_key(x, "updated_at", "created_at"), reverse=True)
        return items[: int(limit)]

    def add_unresolved_tension(
        self,
        *,
        summary: str,
        severity: float = 0.5,
        status: str = "open",
        confidence: float = 0.8,
        source_refs: list[int] | None = None,
    ) -> dict[str, Any]:
        s = str(summary or "").strip()
        if not s:
            raise ValueError("empty tension summary")
        now = int(time.time())
        items = self._list_ns_items("unresolved_tensions")
        for it in reversed(items):
            status_cur = str(it.get("status") or it.get("content", {}).get("status") or "open").strip().lower()
            if status_cur in {"resolved", "closed", "done"}:
                continue
            cur_summary = str(it.get("summary") or it.get("content", {}).get("summary") or "").strip()
            if cur_summary == s or self._text_overlap_score(cur_summary, s) >= 0.72:
                content = it.get("content") if isinstance(it.get("content"), dict) else {}
                sev = max(
                    max(0.0, min(1.0, float(severity))),
                    max(0.0, min(1.0, float(it.get("severity", 0.0) or content.get("severity", 0.0) or 0.0))),
                )
                conf = max(
                    max(0.0, min(1.0, float(confidence))),
                    max(0.0, min(1.0, float(it.get("confidence", 0.0) or 0.0))),
                )
                content["summary"] = cur_summary or s
                content["severity"] = sev
                content["status"] = status_cur or "open"
                content["last_seen_at"] = now
                it["content"] = content
                it["summary"] = content["summary"]
                it["severity"] = sev
                it["status"] = content["status"]
                it["last_seen_at"] = now
                it["updated_at"] = now
                it["confidence"] = conf
                self._put_ns_items("unresolved_tensions", items)
                return it
        return self._append_ns_item(
            "unresolved_tensions",
            self._to_memory_record(
                record_type="unresolved_tension",
                content={
                    "summary": s,
                    "severity": max(0.0, min(1.0, float(severity))),
                    "status": str(status or "open").strip() or "open",
                    "first_seen_at": now,
                    "last_seen_at": now,
                    "resolved_at": 0,
                    "resolution": "",
                },
                confidence=float(confidence),
                source_refs=source_refs,
            ),
            max_items=600,
        )

    def resolve_unresolved_tension(self, tension_id: int, resolution: str) -> bool:
        items = self._list_ns_items("unresolved_tensions")
        updated = False
        rid = int(tension_id)
        now = int(time.time())
        for it in items:
            try:
                if int(it.get("id") or 0) != rid:
                    continue
            except Exception:
                continue
            content = it.get("content") if isinstance(it.get("content"), dict) else {}
            content["status"] = "resolved"
            content["resolution"] = str(resolution or "").strip()
            content["resolved_at"] = now
            content["last_seen_at"] = now
            it["content"] = content
            it["status"] = "resolved"
            it["resolution"] = str(resolution or "").strip()
            it["resolved_at"] = now
            it["last_seen_at"] = now
            it["updated_at"] = now
            updated = True
            break
        if updated:
            self._put_ns_items("unresolved_tensions", items)
        return updated

    def list_semantic_self_narratives(self, limit: int = 30) -> list[dict[str, Any]]:
        items = self._list_ns_items("semantic_self_narratives")
        items.sort(key=lambda x: self._recent_item_sort_key(x, "updated_at", "created_at"), reverse=True)
        return items[: int(limit)]

    def add_semantic_self_narrative(
        self,
        *,
        text: str,
        category: str = "self_narrative",
        stability: float = 0.6,
        confidence: float = 0.78,
        source_refs: list[int] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        t = str(text or "").strip()
        if not t:
            raise ValueError("empty semantic self narrative")
        items = self._list_ns_items("semantic_self_narratives")
        cat = str(category or "self_narrative").strip() or "self_narrative"
        meta = dict(metadata or {})
        for it in reversed(items):
            cur_text = str(it.get("text") or it.get("content", {}).get("text") or "").strip()
            cur_cat = str(it.get("category") or it.get("content", {}).get("category") or "").strip()
            if cur_cat == cat:
                content = it.get("content") if isinstance(it.get("content"), dict) else {}
                stab = max(
                    max(0.0, min(1.0, float(stability))),
                    max(0.0, min(1.0, float(it.get("stability", 0.0) or content.get("stability", 0.0) or 0.0))),
                )
                conf = max(
                    max(0.0, min(1.0, float(confidence))),
                    max(0.0, min(1.0, float(it.get("confidence", 0.0) or 0.0))),
                )
                content["text"] = t
                content["category"] = cat
                content["stability"] = stab
                for key, value in meta.items():
                    content[key] = value
                it["content"] = content
                it["text"] = t
                it["category"] = cat
                it["stability"] = stab
                it["updated_at"] = int(time.time())
                it["confidence"] = conf
                for key, value in meta.items():
                    it[key] = value
                self._put_ns_items("semantic_self_narratives", items)
                return it
        content = {
            "text": t,
            "category": cat,
            "stability": max(0.0, min(1.0, float(stability))),
        }
        for key, value in meta.items():
            content[key] = value
        return self._append_ns_item(
            "semantic_self_narratives",
            self._to_memory_record(
                record_type="semantic_self_narrative",
                content=content,
                confidence=float(confidence),
                source_refs=source_refs,
            ),
            max_items=500,
        )

    def list_revision_traces(self, limit: int = 50) -> list[dict[str, Any]]:
        items = self._list_ns_items("revision_traces")
        items.sort(key=lambda x: self._recent_item_sort_key(x, "updated_at", "created_at"), reverse=True)
        return items[: int(limit)]

    def add_revision_trace(
        self,
        *,
        namespace: str,
        target_id: int | str = "",
        before_summary: str = "",
        after_summary: str = "",
        reason: str = "",
        operator: str = "system",
        source: str = "",
        confidence: float = 0.75,
        source_refs: list[int] | None = None,
    ) -> dict[str, Any]:
        ns = str(namespace or "").strip()
        if not ns:
            raise ValueError("empty revision namespace")
        items = self._list_ns_items("revision_traces")
        target_key = str(target_id or "").strip()
        before_text = str(before_summary or "").strip()
        after_text = str(after_summary or "").strip()
        reason_text = str(reason or "").strip()
        operator_text = str(operator or "system").strip() or "system"
        source_text = str(source or "").strip()
        now = int(time.time())
        for it in reversed(items[-12:]):
            if (
                str(it.get("namespace") or it.get("content", {}).get("namespace") or "").strip() == ns
                and str(it.get("target_id") or it.get("content", {}).get("target_id") or "").strip() == target_key
                and str(it.get("reason") or it.get("content", {}).get("reason") or "").strip() == reason_text
                and str(it.get("after_summary") or it.get("content", {}).get("after_summary") or "").strip() == after_text
                and abs(now - int(it.get("updated_at") or it.get("created_at") or 0)) <= 120
            ):
                it["updated_at"] = now
                self._put_ns_items("revision_traces", items)
                return it
        return self._append_ns_item(
            "revision_traces",
            self._to_memory_record(
                record_type="revision_trace",
                content={
                    "namespace": ns,
                    "target_id": target_key,
                    "before_summary": before_text,
                    "after_summary": after_text,
                    "reason": reason_text,
                    "operator": operator_text,
                    "source": source_text,
                },
                confidence=float(confidence),
                source_refs=source_refs,
            ),
            max_items=1200,
        )

    def list_canon_facts(self) -> dict[str, Any]:
        return self._store_list("canon_facts")

    def set_canon_fact(self, key: str, value: Any) -> None:
        self._store_put("canon_facts", str(key), value)

    def list_source_refs(self, limit: int = 30) -> list[dict[str, Any]]:
        items = self._list_ns_items("source_refs")
        items.sort(key=lambda x: self._recent_item_sort_key(x, "retrieved_at", "timestamp", "created_at"), reverse=True)
        return items[: int(limit)]

    def add_source_ref(
        self,
        *,
        url: str,
        title: str = "",
        query: str = "",
        tool_name: str = "",
        snippet: str = "",
        published_at: str = "",
        retrieved_at: int | None = None,
        reliability_score: float | None = None,
        span_hint: str = "",
    ) -> dict[str, Any]:
        u = str(url or "").strip()
        if not u:
            raise ValueError("empty source url")

        q = str(query or "").strip()
        tname = str(tool_name or "").strip()
        existing = self.list_source_refs(limit=100)
        for it in existing:
            if (
                str(it.get("url") or "").strip() == u
                and str(it.get("query") or "").strip() == q
                and str(it.get("tool_name") or "").strip() == tname
            ):
                return it

        score = None
        if reliability_score is not None:
            try:
                score = max(0.0, min(1.0, float(reliability_score)))
            except Exception:
                score = None

        ts = int(retrieved_at) if retrieved_at is not None else int(time.time())
        return self._append_ns_item(
            "source_refs",
            {
                "url": u,
                "title": str(title or "").strip(),
                "published_at": str(published_at or "").strip(),
                "retrieved_at": ts,
                "query": q,
                "tool_name": tname,
                "snippet": str(snippet or "").strip(),
                "reliability_score": score,
                "span_hint": str(span_hint or "").strip(),
                "timestamp": ts,
            },
            max_items=3000,
        )

    # -------- moments --------
    def list_moments(self, limit: int = 20) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            "SELECT id, summary, tags, links, created_at, superseded_by, merged_from FROM moments ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        out: list[dict[str, Any]] = []
        for (rid, summary, tags, links, created_at, superseded_by, merged_from) in cur.fetchall():
            try:
                tags_v = json.loads(tags)
            except Exception:
                tags_v = []
            try:
                links_v = json.loads(links)
            except Exception:
                links_v = []
            try:
                merged_from_v = json.loads(merged_from) if merged_from else []
            except Exception:
                merged_from_v = []
            out.append(
                {
                    "id": rid,
                    "summary": summary,
                    "tags": tags_v,
                    "links": links_v,
                    "created_at": created_at,
                    "superseded_by": superseded_by,
                    "merged_from": merged_from_v,
                }
            )
        return out

    def search_moments(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Semantic search over local embeddings only.

        If sqlite-vec is enabled, query KNN from `moments_vss` first.
        """

        q = (query or "").strip()
        if not q:
            return []

        # 1) sqlite-vec KNN
        if self._vec_enabled:
            try:
                q_emb = self._embed_query(q)
                cur = self.conn.execute(
                    """
                    SELECT moment_id, distance
                    FROM moments_vss
                    WHERE embedding MATCH ?
                    ORDER BY distance
                    LIMIT ?
                    """,
                    (self._vec_param(q_emb), int(limit) * 5),
                )
                rows = [(int(r[0]), float(r[1])) for r in cur.fetchall()]
                if rows:
                    ids = [r[0] for r in rows]
                    placeholders = ",".join(["?"] * len(ids))
                    cur2 = self.conn.execute(
                        f"SELECT id, summary, tags, links, created_at FROM moments WHERE id IN ({placeholders})",
                        tuple(ids),
                    )
                    by_id: dict[int, dict[str, Any]] = {}
                    for rid, summary, tags, links, created_at in cur2.fetchall():
                        try:
                            tags_v = json.loads(tags)
                        except Exception:
                            tags_v = []
                        try:
                            links_v = json.loads(links)
                        except Exception:
                            links_v = []
                        by_id[int(rid)] = {
                            "id": int(rid),
                            "summary": summary,
                            "tags": tags_v,
                            "links": links_v,
                            "created_at": int(created_at),
                        }

                    scored: list[tuple[float, dict[str, Any]]] = []
                    for mid, dist in rows:
                        base = by_id.get(int(mid))
                        if not base:
                            continue
                        scored.append(((-dist), {**base, "score": round((-dist), 6)}))
                    scored.sort(key=lambda x: x[0], reverse=True)
                    return [x[1] for x in scored[: int(limit)]]
            except Exception:
                pass

        # 2) Fallback to embedding + Python reranking when sqlite-vec is unavailable.
        try:
            q_emb = self._embed_query(q)

            window = max(200, limit * 50)
            cur = self.conn.execute(
                """
                SELECT m.id, m.summary, m.tags, m.links, m.created_at, mv.embedding
                FROM moments m
                LEFT JOIN moments_vec mv ON mv.moment_id = m.id
                ORDER BY m.id DESC
                LIMIT ?
                """,
                (window,),
            )

            scored: list[tuple[float, dict[str, Any]]] = []
            now = int(time.time())

            for (rid, summary, tags, links, created_at, emb_json) in cur.fetchall():
                try:
                    tags_v = json.loads(tags)
                except Exception:
                    tags_v = []
                try:
                    links_v = json.loads(links)
                except Exception:
                    links_v = []

                emb: list[float] | None = None
                if emb_json:
                    try:
                        emb = json.loads(emb_json)
                    except Exception:
                        emb = None

                if emb is None:
                    try:
                        emb = self._embed_query(str(summary))
                        self.conn.execute(
                            "INSERT OR REPLACE INTO moments_vec(moment_id, embedding, updated_at) VALUES(?, ?, ?)",
                            (rid, json.dumps(emb, ensure_ascii=False), int(time.time())),
                        )
                    except Exception:
                        emb = None

                sim = self._cosine(q_emb, emb or [])
                age_days = max(0.0, (now - int(created_at)) / 86400.0)
                recency_bonus = 0.08 * math.exp(-age_days / 14.0)
                score = float(sim) + float(recency_bonus)

                scored.append(
                    (
                        score,
                        {
                            "id": rid,
                            "summary": summary,
                            "tags": tags_v,
                            "links": links_v,
                            "created_at": created_at,
                            "score": round(score, 6),
                        },
                    )
                )

            self.conn.commit()
            scored.sort(key=lambda x: x[0], reverse=True)
            return [x[1] for x in scored[:limit] if x[0] > -0.5]
        except Exception as e:
            self._audit_log(
                {
                    "event": "search_moments_failed",
                    "query": q,
                    "limit": int(limit),
                    "error": f"{type(e).__name__}: {e}",
                }
            )
            return []

    def merge_moments(
        self,
        moment_ids: list[int],
        new_summary: str,
        tags: list[str] | None = None,
        links: list[int] | None = None,
    ) -> int:
        """Merge moments into a new summary node and mark originals superseded."""

        ids = [int(x) for x in (moment_ids or [])]
        ids = [x for x in list(dict.fromkeys(ids)) if x > 0]
        if len(ids) < 2:
            raise ValueError("need at least 2 moment_ids")

        ns = (new_summary or "").strip()
        if not ns:
            raise ValueError("empty new_summary")

        # The merged node records the original source moment ids in `merged_from`.
        mid = self.add_moment(ns, tags=tags, links=links)
        try:
            self.conn.execute(
                "UPDATE moments SET merged_from=? WHERE id=?",
                (json.dumps(ids, ensure_ascii=False), int(mid)),
            )
            placeholders = ",".join(["?"] * len(ids))
            self.conn.execute(
                f"UPDATE moments SET superseded_by=? WHERE id IN ({placeholders})",
                (int(mid), *ids),
            )
            self.conn.commit()
        except Exception as e:
            self._audit_log(
                {"event": "merge_moments_failed", "error": f"{type(e).__name__}: {e}", "ids": ids, "new_id": int(mid)}
            )
        return int(mid)

    def add_moment(self, summary: str, tags: list[str] | None = None, links: list[int] | None = None) -> int:
        # Keep the moments table clean by rejecting near-duplicate episodic snippets.
        s = (summary or "").strip()
        if not s:
            raise ValueError("empty summary")

        tags = [str(x).strip() for x in (tags or []) if str(x).strip()]
        # Deduplicate and cap tag count to avoid prompt/database noise.
        tags = list(dict.fromkeys(tags))[:12]

        links = [int(x) for x in (links or []) if str(x).strip().isdigit()]
        links = list(dict.fromkeys(links))[:12]

        recent = [m["summary"] for m in self.list_moments(limit=20)]
        s_norm = "".join(s.split()).lower()
        for prev in recent:
            p_norm = "".join(str(prev).split()).lower()
            if not p_norm:
                continue
            # Exact match or trivial containment means this is not a new memory.
            if s_norm == p_norm or s_norm in p_norm or p_norm in s_norm:
                raise ValueError("duplicate moment")

        cur = self.conn.execute(
            "INSERT INTO moments(summary, tags, links, created_at) VALUES(?, ?, ?, ?)",
            (s, json.dumps(tags, ensure_ascii=False), json.dumps(links, ensure_ascii=False), int(time.time())),
        )
        mid = int(cur.lastrowid)

        # Best-effort embedding write; failures should not block the main write path.
        try:
            emb = self._embed_query(s)
            self.conn.execute(
                "INSERT OR REPLACE INTO moments_vec(moment_id, embedding, updated_at) VALUES(?, ?, ?)",
                (mid, json.dumps(emb, ensure_ascii=False), int(time.time())),
            )

            # Mirror the vector into sqlite-vec when that index is available.
            if self._vec_enabled:
                self.conn.execute(
                    "INSERT OR REPLACE INTO moments_vss(moment_id, embedding) VALUES(?, ?)",
                    (int(mid), self._vec_param(emb)),
                )
        except Exception:
            pass

        self.conn.commit()
        return mid

    def backfill_moment_embeddings(self, limit: int = 500) -> int:
        """Backfill vectors for moments that currently have no embedding row."""

        lim = int(limit or 0)
        if lim <= 0:
            lim = 500

        cur = self.conn.execute(
            """
            SELECT m.id, m.summary
            FROM moments m
            LEFT JOIN moments_vec mv ON mv.moment_id = m.id
            WHERE mv.moment_id IS NULL
            ORDER BY m.id DESC
            LIMIT ?
            """,
            (lim,),
        )
        rows = cur.fetchall()
        if not rows:
            return 0

        wrote = 0
        for rid, summary in rows:
            try:
                emb = self._embed_query(str(summary))
                self.conn.execute(
                    "INSERT OR REPLACE INTO moments_vec(moment_id, embedding, updated_at) VALUES(?, ?, ?)",
                    (int(rid), json.dumps(emb, ensure_ascii=False), int(time.time())),
                )
                wrote += 1
            except Exception:
                continue

        self.conn.commit()
        return wrote

    def delete_moment(self, moment_id: int) -> bool:
        # Best effort: clean the auxiliary vector table even if cascading deletes fail.
        try:
            self.conn.execute("DELETE FROM moments_vec WHERE moment_id=?", (int(moment_id),))
        except Exception:
            pass
        cur = self.conn.execute("DELETE FROM moments WHERE id=?", (int(moment_id),))
        self.conn.commit()
        return cur.rowcount > 0

    # -------- reflections --------
    def list_reflections(self, limit: int = 20) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            "SELECT id, text, derived_from, importance, created_at FROM reflections ORDER BY id DESC LIMIT ?",
            (int(limit),),
        )
        out: list[dict[str, Any]] = []
        for rid, text, derived_from, importance, created_at in cur.fetchall():
            try:
                df = json.loads(derived_from)
            except Exception:
                df = []
            out.append(
                {
                    "id": int(rid),
                    "text": str(text),
                    "derived_from": df,
                    "importance": float(importance),
                    "created_at": int(created_at),
                }
            )
        return out

    def add_reflection(
        self,
        text: str,
        derived_from: list[int] | None = None,
        importance: float | None = None,
    ) -> int:
        t = (text or "").strip()
        if not t:
            raise ValueError("empty reflection")

        derived_from = [int(x) for x in (derived_from or [])]
        derived_from = list(dict.fromkeys(derived_from))[:20]

        imp = 0.5
        if importance is not None:
            try:
                imp = float(importance)
            except Exception:
                imp = 0.5
        imp = max(0.0, min(1.0, imp))

        cur = self.conn.execute(
            "INSERT INTO reflections(text, derived_from, importance, created_at) VALUES(?, ?, ?, ?)",
            (t, json.dumps(derived_from, ensure_ascii=False), imp, int(time.time())),
        )
        rid = int(cur.lastrowid)

        # Best effort: write the embedding without blocking the main row insert.
        try:
            emb = self._embed_query(t)
            self.conn.execute(
                "INSERT OR REPLACE INTO reflections_vec(reflection_id, embedding, updated_at) VALUES(?, ?, ?)",
                (rid, json.dumps(emb, ensure_ascii=False), int(time.time())),
            )

            # Mirror into sqlite-vec when that index is available.
            if self._vec_enabled:
                self.conn.execute(
                    "INSERT OR REPLACE INTO reflections_vss(reflection_id, embedding) VALUES(?, ?)",
                    (int(rid), self._vec_param(emb)),
                )
        except Exception:
            pass

        self.conn.commit()
        return rid

    def delete_reflection(self, reflection_id: int) -> bool:
        # Best effort: clean the auxiliary vector table before deleting the main row.
        try:
            self.conn.execute(
                "DELETE FROM reflections_vec WHERE reflection_id=?", (int(reflection_id),)
            )
        except Exception:
            pass
        cur = self.conn.execute("DELETE FROM reflections WHERE id=?", (int(reflection_id),))
        self.conn.commit()
        return cur.rowcount > 0

    def search_reflections(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return []

        # 1) sqlite-vec KNN when the vector index is available.
        if self._vec_enabled:
            try:
                q_emb = self._embed_query(q)
                cur = self.conn.execute(
                    """
                    SELECT reflection_id, distance
                    FROM reflections_vss
                    WHERE embedding MATCH ?
                    ORDER BY distance
                    LIMIT ?
                    """,
                    (self._vec_param(q_emb), int(limit) * 5),
                )
                rows = [(int(r[0]), float(r[1])) for r in cur.fetchall()]
                if rows:
                    ids = [r[0] for r in rows]
                    placeholders = ",".join(["?"] * len(ids))
                    cur2 = self.conn.execute(
                        f"SELECT id, text, derived_from, importance, created_at FROM reflections WHERE id IN ({placeholders})",
                        tuple(ids),
                    )
                    by_id: dict[int, dict[str, Any]] = {}
                    for rid, text, derived_from, importance, created_at in cur2.fetchall():
                        try:
                            df = json.loads(derived_from)
                        except Exception:
                            df = []
                        by_id[int(rid)] = {
                            "id": int(rid),
                            "text": str(text),
                            "derived_from": df,
                            "importance": float(importance),
                            "created_at": int(created_at),
                        }

                    scored: list[tuple[float, dict[str, Any]]] = []
                    for rid, dist in rows:
                        base = by_id.get(int(rid))
                        if not base:
                            continue
                        scored.append(((-dist), {**base, "score": round((-dist), 6)}))
                    scored.sort(key=lambda x: x[0], reverse=True)
                    return [x[1] for x in scored[: int(limit)]]
            except Exception:
                pass

        # 2) Fallback to embedding search + Python reranking when sqlite-vec is unavailable.
        try:
            q_emb = self._embed_query(q)
            window = max(200, int(limit) * 50)
            cur = self.conn.execute(
                """
                SELECT r.id, r.text, r.derived_from, r.importance, r.created_at, rv.embedding
                FROM reflections r
                LEFT JOIN reflections_vec rv ON rv.reflection_id = r.id
                ORDER BY r.id DESC
                LIMIT ?
                """,
                (window,),
            )

            scored: list[tuple[float, dict[str, Any]]] = []
            now = int(time.time())
            for rid, text, derived_from, importance, created_at, emb_json in cur.fetchall():
                try:
                    df = json.loads(derived_from)
                except Exception:
                    df = []

                emb: list[float] | None = None
                if emb_json:
                    try:
                        emb = json.loads(emb_json)
                    except Exception:
                        emb = None

                # 鎳掕ˉ
                if emb is None:
                    try:
                        emb = self._embed_query(str(text))
                        self.conn.execute(
                            "INSERT OR REPLACE INTO reflections_vec(reflection_id, embedding, updated_at) VALUES(?, ?, ?)",
                            (int(rid), json.dumps(emb, ensure_ascii=False), int(time.time())),
                        )
                    except Exception:
                        emb = None

                sim = self._cosine(q_emb, emb or [])

                age_days = max(0.0, (now - int(created_at)) / 86400.0)
                recency_bonus = 0.06 * math.exp(-age_days / 21.0)
                imp_bonus = 0.08 * float(importance)

                score = float(sim) + float(recency_bonus) + float(imp_bonus)
                scored.append(
                    (
                        score,
                        {
                            "id": int(rid),
                            "text": str(text),
                            "derived_from": df,
                            "importance": float(importance),
                            "created_at": int(created_at),
                            "score": round(score, 6),
                        },
                    )
                )

            self.conn.commit()
            scored.sort(key=lambda x: x[0], reverse=True)
            return [x[1] for x in scored[: int(limit)] if x[0] > -0.5]
        except Exception as e:
            self._audit_log(
                {
                    "event": "search_reflections_failed",
                    "query": q,
                    "limit": int(limit),
                    "error": f"{type(e).__name__}: {e}",
                }
            )
            return []

    def backfill_reflection_embeddings(self, limit: int = 500) -> int:
        lim = int(limit or 0)
        if lim <= 0:
            lim = 500

        cur = self.conn.execute(
            """
            SELECT r.id, r.text
            FROM reflections r
            LEFT JOIN reflections_vec rv ON rv.reflection_id = r.id
            WHERE rv.reflection_id IS NULL
            ORDER BY r.id DESC
            LIMIT ?
            """,
            (lim,),
        )
        rows = cur.fetchall()
        if not rows:
            return 0

        wrote = 0
        for rid, text in rows:
            try:
                emb = self._embed_query(str(text))
                self.conn.execute(
                    "INSERT OR REPLACE INTO reflections_vec(reflection_id, embedding, updated_at) VALUES(?, ?, ?)",
                    (int(rid), json.dumps(emb, ensure_ascii=False), int(time.time())),
                )
                wrote += 1
            except Exception:
                continue

        self.conn.commit()
        return wrote

    # -------- helpers --------
    def snapshot(self) -> dict[str, Any]:
        """Return a compact multi-namespace memory snapshot."""
        profile = self.get_profile()
        relationship = self.get_relationship()
        moments = list(reversed(self.list_moments(limit=5)))
        reflections = list(reversed(self.list_reflections(limit=5)))
        worldline_events = list(reversed(self.list_worldline_events(limit=5)))
        identity_facts = list(reversed(self.list_identity_facts(limit=5)))
        shared_events = list(reversed(self.list_shared_events(limit=5)))
        conflict_repair = list(reversed(self.list_conflict_repairs(limit=5)))
        relationship_timeline = list(reversed(self.list_relationship_timeline(limit=5)))
        commitments = list(reversed(self.list_commitments(limit=5)))
        unresolved_tensions = list(reversed(self.list_unresolved_tensions(limit=5)))
        semantic_self_narratives = list(reversed(self.list_semantic_self_narratives(limit=5)))
        revision_traces = list(reversed(self.list_revision_traces(limit=5)))
        source_refs = list(reversed(self.list_source_refs(limit=5)))
        canon_facts = self.list_canon_facts()
        memory_quarantine = list(reversed(self.list_memory_quarantine(limit=5)))
        memory_ledger = list(reversed(self.list_memory_ledger(limit=5)))
        return {
            "profile": profile,
            "relationship": relationship,
            "moments": moments,
            "reflections": reflections,
            "worldline_events": worldline_events,
            "identity_facts": identity_facts,
            "shared_events": shared_events,
            "conflict_repair": conflict_repair,
            "relationship_timeline": relationship_timeline,
            "commitments": commitments,
            "unresolved_tensions": unresolved_tensions,
            "semantic_self_narratives": semantic_self_narratives,
            "revision_traces": revision_traces,
            "source_refs": source_refs,
            "canon_facts": canon_facts,
            "memory_quarantine": memory_quarantine,
            "memory_ledger": memory_ledger,
        }




