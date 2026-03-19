import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from amadeus_thread0.runtime.thread_runtime import (
    activate_thread_runtime,
    list_threads,
)


class ThreadRuntimeTests(unittest.TestCase):
    def test_list_threads_collects_checkpoint_ids_and_worldline_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            conn = sqlite3.connect(str(checkpoint_db))
            try:
                conn.execute("CREATE TABLE checkpoints (id INTEGER PRIMARY KEY, thread_id TEXT)")
                conn.execute("INSERT INTO checkpoints(thread_id) VALUES (?)", ("thread-b",))
                conn.execute("INSERT INTO checkpoints(thread_id) VALUES (?)", ("thread-a",))
                conn.execute("CREATE TABLE misc (id INTEGER PRIMARY KEY, note TEXT)")
                conn.commit()
            finally:
                conn.close()

            (root / "worldlines" / "thread-a").mkdir(parents=True, exist_ok=True)
            (root / "worldlines" / "thread-c").mkdir(parents=True, exist_ok=True)

            inventory = list_threads(base_data_dir=root, checkpoint_db_path=checkpoint_db)

        self.assertEqual(inventory.checkpoint_thread_ids, ["thread-a", "thread-b"])
        self.assertEqual(inventory.worldline_dir_ids, ["thread-a", "thread-c"])

    def test_activate_thread_runtime_applies_env_and_returns_switch_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous = {
                "AMADEUS_DATA_DIR": os.environ.get("AMADEUS_DATA_DIR"),
                "AMADEUS_CHECKPOINT_DB": os.environ.get("AMADEUS_CHECKPOINT_DB"),
                "AMADEUS_MEMORY_DB": os.environ.get("AMADEUS_MEMORY_DB"),
                "AMADEUS_DIARY_PATH": os.environ.get("AMADEUS_DIARY_PATH"),
            }
            try:
                plan = activate_thread_runtime(
                    root,
                    "demo/session",
                    fallback_prefix="thread",
                    now_ts=1_710_000_000,
                    suffix="seed42",
                )
                self.assertEqual(plan.thread_id, "demo-session")
                self.assertTrue(plan.runtime_dir.exists())
                self.assertEqual(Path(os.environ["AMADEUS_DATA_DIR"]), plan.runtime_dir)
                self.assertEqual(Path(os.environ["AMADEUS_CHECKPOINT_DB"]), plan.runtime_dir / "checkpoints.sqlite")
                self.assertEqual(Path(os.environ["AMADEUS_MEMORY_DB"]), plan.runtime_dir / "memories.sqlite")
                self.assertEqual(Path(os.environ["AMADEUS_DIARY_PATH"]), plan.runtime_dir / "diary.txt")
            finally:
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
