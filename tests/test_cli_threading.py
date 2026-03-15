import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from amadeus_thread0.cli import (
    _generate_thread_id,
    _resolve_startup_thread_id,
    _sanitize_thread_id_seed,
    _shared_runtime_artifacts,
    _should_warn_shared_default_runtime,
)


class CliThreadingTests(unittest.TestCase):
    def test_sanitize_thread_id_seed_replaces_unsafe_chars(self):
        self.assertEqual(_sanitize_thread_id_seed(" world line / 01 "), "world-line-01")

    def test_generate_thread_id_uses_prefix_timestamp_and_suffix(self):
        actual = _generate_thread_id(
            prefix="worldline",
            now_ts=1_710_000_000,
            suffix="abc123",
        )
        self.assertEqual(actual, "worldline-20240310-000000-abc123")

    def test_resolve_startup_thread_id_prefers_cli_override(self):
        actual = _resolve_startup_thread_id(
            default_thread_id="thread0",
            cli_thread_id="demo/session",
            fresh_thread=False,
            fresh_thread_prefix="thread",
        )
        self.assertEqual(actual, "demo-session")

    def test_resolve_startup_thread_id_can_generate_fresh_thread(self):
        actual = _resolve_startup_thread_id(
            default_thread_id="thread0",
            cli_thread_id=None,
            fresh_thread=True,
            fresh_thread_prefix="worldline",
            now_ts=1_710_000_000,
            suffix="seed42",
        )
        self.assertEqual(actual, "worldline-20240310-000000-seed42")

    def test_resolve_startup_thread_id_falls_back_to_default(self):
        actual = _resolve_startup_thread_id(
            default_thread_id="thread0",
            cli_thread_id=None,
            fresh_thread=False,
            fresh_thread_prefix="thread",
        )
        self.assertEqual(actual, "thread0")

    def test_shared_runtime_artifacts_only_reports_existing_nonempty_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "checkpoints.sqlite").write_bytes(b"x")
            (root / "memories.sqlite").write_bytes(b"")
            (root / "decision_audit.jsonl").write_text("{}", encoding="utf-8")
            found = _shared_runtime_artifacts(root)
        self.assertEqual(found, ["checkpoints.sqlite", "decision_audit.jsonl"])

    def test_should_warn_shared_default_runtime_when_plain_thread0_hits_shared_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("amadeus_thread0.cli._repo_default_data_dir", return_value=root):
                actual = _should_warn_shared_default_runtime(
                    base_data_dir=root,
                    runtime_data_dir=root,
                    startup_thread_id="thread0",
                    startup_explicit=False,
                    shared_artifacts=["checkpoints.sqlite", "memories.sqlite"],
                )
        self.assertTrue(actual)

    def test_should_not_warn_when_startup_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            actual = _should_warn_shared_default_runtime(
                base_data_dir=root,
                runtime_data_dir=root,
                startup_thread_id="thread0",
                startup_explicit=True,
                shared_artifacts=["checkpoints.sqlite"],
            )
        self.assertFalse(actual)

    def test_should_not_warn_for_isolated_worldline_runtime_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            isolated = root / "worldlines" / "thread-a"
            isolated.mkdir(parents=True, exist_ok=True)
            with patch("amadeus_thread0.cli._repo_default_data_dir", return_value=root):
                actual = _should_warn_shared_default_runtime(
                    base_data_dir=root,
                    runtime_data_dir=isolated,
                    startup_thread_id="thread0",
                    startup_explicit=False,
                    shared_artifacts=["checkpoints.sqlite"],
                )
        self.assertFalse(actual)


if __name__ == "__main__":
    unittest.main()
