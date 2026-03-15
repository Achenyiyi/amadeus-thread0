import tempfile
import unittest
from pathlib import Path

from amadeus_thread0.runtime_audit import audit_runtime_layout, render_runtime_audit_report


class RuntimeAuditTests(unittest.TestCase):
    def test_audit_runtime_layout_classifies_shared_isolated_and_legacy_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "checkpoints.sqlite").write_bytes(b"root-checkpoints")
            (root / "memories.sqlite").write_bytes(b"root-memories")
            (root / "copy_wav").mkdir()
            (root / "copy_wav" / "ref.wav").write_bytes(b"wav")

            smoke = root / "smoke_prompt"
            smoke.mkdir()
            (smoke / "checkpoints.sqlite").write_bytes(b"smoke-checkpoints")

            isolated = root / "worldlines" / "demo-thread"
            isolated.mkdir(parents=True)
            (isolated / "memories.sqlite").write_bytes(b"worldline-memories")

            other = root / "notes"
            other.mkdir()
            (other / "readme.txt").write_text("hello", encoding="utf-8")

            audit = audit_runtime_layout(root)

        self.assertEqual(int(audit["stats"]["shared_artifact_count"]), 2)
        self.assertEqual(int(audit["stats"]["isolated_worldline_count"]), 1)
        self.assertEqual(int(audit["stats"]["legacy_runtime_dir_count"]), 1)
        self.assertEqual(int(audit["stats"]["asset_dir_count"]), 1)
        self.assertEqual(int(audit["stats"]["other_dir_count"]), 1)
        self.assertEqual(str(audit["legacy_runtime_dirs"][0]["name"]), "smoke_prompt")
        self.assertTrue(bool(audit["legacy_runtime_dirs"][0]["smoke_like"]))
        self.assertEqual(str(audit["isolated_worldlines"][0]["name"]), "demo-thread")

    def test_render_runtime_audit_report_contains_recommendations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "checkpoints.sqlite").write_bytes(b"root-checkpoints")
            legacy = root / "smoke_debug"
            legacy.mkdir()
            (legacy / "memories.sqlite").write_bytes(b"legacy-memories")
            report = render_runtime_audit_report(audit_runtime_layout(root))

        self.assertIn("[runtime-audit]", report)
        self.assertIn("[shared-root]", report)
        self.assertIn("[legacy-runtime-dirs]", report)
        self.assertIn("[recommendations]", report)
        self.assertIn("--fresh-thread", report)
        self.assertIn("smoke/debug", report)


if __name__ == "__main__":
    unittest.main()
