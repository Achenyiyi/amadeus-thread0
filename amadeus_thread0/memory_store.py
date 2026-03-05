from __future__ import annotations

import json
import math
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Reduce TensorFlow noise emitted through sentence-transformers dependencies.
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TF", "0")

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
    """涓夊眰缁撴瀯鍖栬蹇嗭細

    - profile: key-value锛堢ǔ瀹氫簨瀹烇級
    - relationship: 鍗曟潯鐘舵€侊紙鏈嬪弸/鏆ф槯/鎭嬩汉鈥?+ 杈圭晫锛?
    - moments: 鏃堕棿绾跨墖娈碉紙1~2鍙ユ憳瑕侊紝鏀寔 embedding 璇箟妫€绱級

    娉ㄦ剰锛氭湰绫诲彧鍋氬瓨鍙栵紝涓嶅仛鈥滄槸鍚﹀簲鍐欏叆鈥濈殑鍐崇瓥锛堝喅绛栧湪CLI鐨勪汉绫荤‘璁ら噷锛夈€?
    """

    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._embedder: HuggingFaceEmbeddings | None = None
        self._vec_enabled: bool = False
        self._vec_dim: int | None = None
        try:
            self._init_schema()
        except Exception:
            # 鍒濆鍖栧け璐ユ椂纭繚閲婃斁 sqlite 鏂囦欢鍙ユ焺锛圵indows 涓嬪惁鍒欎細瀵艰嚧涓存椂鐩綍娓呯悊澶辫触锛夈€?
            try:
                self.conn.close()
            except Exception:
                pass
            raise

    def _get_embedder(self) -> HuggingFaceEmbeddings:
        if self._embedder is not None:
            return self._embedder
        s = get_settings()
        self._embedder = HuggingFaceEmbeddings(
            model_name=s.embedding_model_name,
            model_kwargs={
                "device": s.embedding_device,
                "trust_remote_code": bool(s.embedding_trust_remote_code),
            },
            encode_kwargs={"normalize_embeddings": bool(s.embedding_normalize)},
        )
        return self._embedder

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
            probe = self._get_embedder().embed_query("dimension probe")
            dim = int(len(probe))
            if dim <= 0:
                self._vec_enabled = False
                return
            self._vec_dim = dim
        except Exception:
            self._vec_enabled = False
            return

        try:
            # 娉ㄦ剰锛氫笉鍚?sqlite-vec 鐗堟湰瀵?vec0 鐨勫垪瀹氫箟鏀寔鑼冨洿涓嶅悓銆?
            # 涓轰繚璇佸吋瀹规€э紝杩欓噷鍙湪 vec0 琛ㄤ腑瀛樺偍 (id, embedding)锛?
            # 鍏朵粬鍏冩暟鎹紙created_at/importance锛変粛瀛樻斁鍦ㄥ父瑙勮〃閲屻€?
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
        # long-term store锛坣amespace + key -> JSON锛?
        # 鍙傝€?LangGraph Memory 鐨勭粍缁囨柟寮忥細鐢?namespace+key 绠＄悊闀挎湡璁板繂銆?
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

        # legacy tables锛堝吋瀹瑰巻鍙茬増鏈紱閫愭鏀跺彛鍒?store_kv锛?
        # 榛樿鍏抽棴锛氶伩鍏嶆柊搴撶户缁敓鎴?legacy 琛紝閫犳垚鈥滄棫琛ㄥ瓨鍦ㄤ絾瀹為檯涓嶅啀浣跨敤鈥濈殑闀挎湡鑴戣椋庨櫓銆?
        # 濡傞渶浠庢棫搴撹縼绉?鍏煎锛岃鏄惧紡璁剧疆鐜鍙橀噺锛欰MADEUS_LEGACY_TABLES=1銆?
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

        # moments 鏄牳蹇冨瓨鍌紙闈?legacy锛夛細涓嶅簲琚?AMADEUS_LEGACY_TABLES 褰卞搷銆?
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

        # moments embedding锛堣涔夋绱級
        # - embedding 浠?JSON 鏁扮粍褰㈠紡瀛樺偍锛屼究浜庤皟璇曚笌鍏煎锛堣妯′笂鏉ュ悗鍙崲 sqlite-vec / pgvector 绛夛級
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

        # 绱㈠紩锛氫釜浜轰娇鐢ㄤ篃寤鸿鍔犱笂锛岄伩鍏?moments 澶氫簡鍚?/moments銆佹绱㈠彉鎱?
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_moments_created_at ON moments(created_at)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_moments_summary ON moments(summary)"
        )

        # reflections锛堝弽鎬濆眰锛氫粠 moments 鎶借薄鍑烘潵鐨勯暱鏈熻寰?缁撹锛?
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

        # reflections embedding锛堣涔夋绱級
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

        # ---- sqlite-vec锛堝彲閫夛級锛氭妸鍚戦噺妫€绱粠 Python 鍏ㄦ壂鎻忓崌绾т负 SQLite 鍐?KNN ----
        self._init_sqlite_vec_indexes()

        # 鍏煎鏃у簱锛歮oments 琛ㄥ彲鑳界己灏?tags/links 瀛楁锛屽仛涓€娆¤交閲忚縼绉?
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

        # --- 杩佺Щ锛歭egacy -> store_kv锛堝彧鍋氫竴娆★細鐢?meta.migrated_from_legacy_at 鍋氭爣璁帮級
        # 璇存槑锛氶伩鍏嶁€渟tore_kv 琚汉涓烘竻绌?閮ㄥ垎鍒犻櫎鈥濇椂璇Е鍙戜簩娆¤縼绉伙紝瀵艰嚧鑴戣銆?
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

            # 鏍囪锛氬凡瀹屾垚杩佺Щ
            self._store_put("meta", "migrated_from_legacy_at", int(time.time()))
        elif should_migrate and (not legacy_enabled):
            # 鏂板簱/宸茬鐢?legacy锛氫笉鍋氳縼绉伙紝鍚庣画璧?store_kv 榛樿鍊煎厹搴曞嵆鍙€?
            self._store_put("meta", "migrated_from_legacy_at", int(time.time()))

        # store_kv 榛樿鍊煎厹搴曪細纭繚 relationship.state 涓€瀹氬瓨鍦?
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
    @staticmethod
    def _sanitize_text(text: str) -> str:
        return str(text or "").encode("utf-8", "ignore").decode("utf-8")

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
    def _json_dumps(value: Any) -> str:
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
        items.sort(key=lambda x: int(x.get("created_at") or 0), reverse=True)
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
        # 鍏煎锛氬垹闄?profile 鏃朵竴骞跺皾璇曟竻鐞?meta
        try:
            self._store_delete("profile_meta", key)
        except Exception:
            pass
        return self._store_delete("profile", key)

    # -------- relationship --------
    def get_relationship(self) -> dict[str, Any]:
        v = self._store_get("relationship", "state")
        if not isinstance(v, dict):
            return {"stage": "friend", "notes": ""}
        return v

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
        # 鍘婚噸锛氬悓鍚嶈鐩?
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
        items.sort(key=lambda x: int(x.get("created_at") or 0), reverse=True)
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
        items.sort(key=lambda x: int(x.get("created_at") or 0), reverse=True)
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
        items.sort(key=lambda x: int(x.get("created_at") or 0), reverse=True)
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
        items.sort(key=lambda x: int(x.get("created_at") or 0), reverse=True)
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
        elif c in {"conflict", "repair", "conflict_repair"}:
            try:
                self.add_conflict_repair(summary=s, confidence=confidence, source_refs=source_refs)
            except Exception:
                pass
        return rec

    def list_relationship_timeline(self, limit: int = 20) -> list[dict[str, Any]]:
        items = self._list_ns_items("relationship_timeline")
        items.sort(key=lambda x: int(x.get("created_at") or 0), reverse=True)
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
        items.sort(key=lambda x: int(x.get("created_at") or 0), reverse=True)
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

    def list_canon_facts(self) -> dict[str, Any]:
        return self._store_list("canon_facts")

    def set_canon_fact(self, key: str, value: Any) -> None:
        self._store_put("canon_facts", str(key), value)

    def list_source_refs(self, limit: int = 30) -> list[dict[str, Any]]:
        items = self._list_ns_items("source_refs")
        items.sort(
            key=lambda x: int(x.get("retrieved_at") or x.get("timestamp") or x.get("created_at") or 0),
            reverse=True,
        )
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
        """Semantic search first, with LIKE fallback.

        If sqlite-vec is enabled, query KNN from `moments_vss` first.
        """

        q = (query or "").strip()
        if not q:
            return []

        # 1) sqlite-vec KNN
        if self._vec_enabled:
            try:
                q_emb = self._get_embedder().embed_query(q)
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

        # 2) 鍥為€€鍒版棫鐨?embedding+Python rerank
        try:
            q_emb = self._get_embedder().embed_query(q)

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
                        emb = self._get_embedder().embed_query(str(summary))
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
        except Exception:
            cur = self.conn.execute(
                "SELECT id, summary, tags, links, created_at FROM moments WHERE summary LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{q}%", limit),
            )
            out: list[dict[str, Any]] = []
            for (rid, summary, tags, links, created_at) in cur.fetchall():
                try:
                    tags_v = json.loads(tags)
                except Exception:
                    tags_v = []
                try:
                    links_v = json.loads(links)
                except Exception:
                    links_v = []
                out.append(
                    {
                        "id": rid,
                        "summary": summary,
                        "tags": tags_v,
                        "links": links_v,
                        "created_at": created_at,
                    }
                )
            return out

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

        # 鏂拌妭鐐癸細merged_from 璁板綍鏉ユ簮
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
        # 淇濇寔 moments 骞插噣锛氶伩鍏嶉噸澶?楂樺害鐩镐技鐨勭墖娈靛埛灞?
        s = (summary or "").strip()
        if not s:
            raise ValueError("empty summary")

        tags = [str(x).strip() for x in (tags or []) if str(x).strip()]
        # 鍘婚噸 + 闄愬埗鏁伴噺锛岄伩鍏?prompt/DB 琚櫔澹版饭娌?
        tags = list(dict.fromkeys(tags))[:12]

        links = [int(x) for x in (links or []) if str(x).strip().isdigit()]
        links = list(dict.fromkeys(links))[:12]

        recent = [m["summary"] for m in self.list_moments(limit=20)]
        s_norm = "".join(s.split()).lower()
        for prev in recent:
            p_norm = "".join(str(prev).split()).lower()
            if not p_norm:
                continue
            # 瀹屽叏鐩稿悓 / 鍖呭惈
            if s_norm == p_norm or s_norm in p_norm or p_norm in s_norm:
                raise ValueError("duplicate moment")

        cur = self.conn.execute(
            "INSERT INTO moments(summary, tags, links, created_at) VALUES(?, ?, ?, ?)",
            (s, json.dumps(tags, ensure_ascii=False), json.dumps(links, ensure_ascii=False), int(time.time())),
        )
        mid = int(cur.lastrowid)

        # best-effort锛氬啓鍏?embedding锛堝け璐ヤ篃涓嶅奖鍝嶄富娴佺▼锛?
        try:
            emb = self._get_embedder().embed_query(s)
            self.conn.execute(
                "INSERT OR REPLACE INTO moments_vec(moment_id, embedding, updated_at) VALUES(?, ?, ?)",
                (mid, json.dumps(emb, ensure_ascii=False), int(time.time())),
            )

            # sqlite-vec 绱㈠紩锛堝鍙敤锛?
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
                emb = self._get_embedder().embed_query(str(summary))
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
        # 鍏煎锛氬嵆浣垮閿骇鑱旀湭鐢熸晥锛屼篃灏介噺娓呯悊 moments_vec
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

        # best-effort锛氬啓鍏?embedding
        try:
            emb = self._get_embedder().embed_query(t)
            self.conn.execute(
                "INSERT OR REPLACE INTO reflections_vec(reflection_id, embedding, updated_at) VALUES(?, ?, ?)",
                (rid, json.dumps(emb, ensure_ascii=False), int(time.time())),
            )

            # sqlite-vec 绱㈠紩锛堝鍙敤锛?
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
        # 鍏煎锛氬敖閲忔竻鐞?reflections_vec
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

        # 1) sqlite-vec KNN锛堝鍙敤锛?
        if self._vec_enabled:
            try:
                q_emb = self._get_embedder().embed_query(q)
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

        # 2) 鍥為€€锛歟mbedding 璇箟妫€绱紙embedding+Python rerank锛?
        try:
            q_emb = self._get_embedder().embed_query(q)
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
                        emb = self._get_embedder().embed_query(str(text))
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
        except Exception:
            # 3) 鍥為€€ LIKE
            cur = self.conn.execute(
                "SELECT id, text, derived_from, importance, created_at FROM reflections WHERE text LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{q}%", int(limit)),
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
                emb = self._get_embedder().embed_query(str(text))
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
            "source_refs": source_refs,
            "canon_facts": canon_facts,
            "memory_quarantine": memory_quarantine,
            "memory_ledger": memory_ledger,
        }


