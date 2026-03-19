from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from amadeus_thread0.runtime.runtime_bundle import RuntimeBundle


class FakeMemoryStore:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.closed = False

    def close(self):
        self.closed = True


class RuntimeBundleTests(unittest.TestCase):
    def test_create_builds_graph_store_session_and_admin(self):
        created_graphs = []

        def graph_factory():
            graph = object()
            created_graphs.append(graph)
            return graph

        settings = SimpleNamespace(memory_db_path=Path("E:/tmp/memories.sqlite"), user_id="okabe")
        bundle = RuntimeBundle.create(
            thread_id="thread-a",
            settings=settings,
            graph_factory=graph_factory,
            memory_store_factory=FakeMemoryStore,
        )

        self.assertIs(bundle.graph, created_graphs[0])
        self.assertEqual(bundle.thread_id, "thread-a")
        self.assertEqual(bundle.config()["configurable"]["user_id"], "okabe")
        self.assertEqual(bundle.memory_store.db_path, Path("E:/tmp/memories.sqlite"))

    def test_switch_thread_closes_old_store_and_rebuilds_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings_queue = [
                SimpleNamespace(memory_db_path=root / "thread-a.sqlite", user_id="okabe"),
                SimpleNamespace(memory_db_path=root / "thread-b.sqlite", user_id="okabe"),
            ]
            created_graphs = []
            reset_calls = []

            def graph_factory():
                graph = object()
                created_graphs.append(graph)
                return graph

            def settings_factory():
                return settings_queue.pop(0)

            bundle = RuntimeBundle.create(
                thread_id="thread-a",
                settings=settings_factory(),
                graph_factory=graph_factory,
                memory_store_factory=FakeMemoryStore,
            )
            old_store = bundle.memory_store

            switch_plan = bundle.switch_thread(
                base_data_dir=root,
                requested_thread_id="thread-b",
                settings_factory=settings_factory,
                graph_factory=graph_factory,
                memory_store_factory=FakeMemoryStore,
                reset_tool_runtime_caches_fn=lambda: reset_calls.append("tool"),
                reset_runtime_caches_fn=lambda: reset_calls.append("runtime"),
            )

            self.assertTrue(old_store.closed)
            self.assertEqual(reset_calls, ["tool", "runtime"])
            self.assertEqual(bundle.thread_id, "thread-b")
            self.assertEqual(bundle.config()["configurable"]["thread_id"], "thread-b")
            self.assertEqual(bundle.memory_store.db_path, root / "thread-b.sqlite")
            self.assertIs(bundle.graph, created_graphs[-1])
            self.assertEqual(switch_plan.thread_id, "thread-b")
            self.assertTrue(switch_plan.runtime_dir.exists())


if __name__ == "__main__":
    unittest.main()
