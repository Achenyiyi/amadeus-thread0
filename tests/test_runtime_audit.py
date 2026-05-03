import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import json

from amadeus_thread0.runtime_audit import (
    REQUIRED_DEPENDENCY_PROBES,
    audit_runtime_layout,
    build_graph_startup_preflight_report,
    build_runtime_doctor_report,
    render_runtime_audit_report,
    render_runtime_doctor_report,
)


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

    def test_runtime_doctor_report_contains_required_top_level_keys(self):
        with patch("amadeus_thread0.utils.runtime_audit.importlib.util.find_spec", return_value=object()), patch(
            "amadeus_thread0.utils.runtime_audit.subprocess.run",
            return_value=Mock(returncode=0, stdout="ok", stderr=""),
        ), patch.dict("os.environ", {"AMADEUS_MODEL_API_KEY": "test-key"}, clear=True):
            report = build_runtime_doctor_report()

        self.assertEqual(
            set(report),
            {
                "overall_status",
                "python",
                "dependencies",
                "pip_check",
                "env",
                "model_key",
                "playwright",
                "docker",
                "phase_readiness",
                "remediation",
            },
        )
        json.dumps(report, ensure_ascii=False)

    def test_graph_startup_preflight_is_lightweight(self):
        with patch("amadeus_thread0.utils.runtime_audit.importlib.util.find_spec", return_value=object()), patch(
            "amadeus_thread0.utils.runtime_audit.subprocess.run",
            side_effect=AssertionError("startup preflight must not shell out"),
        ), patch.dict("os.environ", {"AMADEUS_MODEL_API_KEY": "test-key"}, clear=True):
            report = build_graph_startup_preflight_report()

        self.assertEqual(report["overall_status"], "passed")
        self.assertEqual(report["phase_readiness"]["graph"], "ready")
        self.assertNotIn("pip_check", report)
        self.assertNotIn("docker", report)

    def test_langgraph_checkpoint_sqlite_probe_uses_runtime_import_path(self):
        probes = dict(REQUIRED_DEPENDENCY_PROBES)

        self.assertEqual(probes["langgraph-checkpoint-sqlite"], "langgraph.checkpoint.sqlite")

    def test_missing_required_dependency_fails_graph_and_adds_remediation(self):
        def fake_find_spec(name: str):
            if name == "langgraph":
                return None
            return object()

        with patch("amadeus_thread0.utils.runtime_audit.importlib.util.find_spec", side_effect=fake_find_spec), patch(
            "amadeus_thread0.utils.runtime_audit.subprocess.run",
            return_value=Mock(returncode=0, stdout="ok", stderr=""),
        ), patch.dict("os.environ", {"AMADEUS_MODEL_API_KEY": "test-key"}, clear=True):
            report = build_runtime_doctor_report()

        self.assertEqual(report["overall_status"], "failed")
        self.assertEqual(report["phase_readiness"]["graph"], "blocked")
        self.assertTrue(
            any(
                item.get("kind") == "missing_package" and item.get("package") == "langgraph"
                for item in report["remediation"]
            )
        )

    def test_sandbox_phase_rendering_mentions_docker_image_and_network_policy(self):
        report = {
            "overall_status": "failed",
            "python": {"status": "ok", "version": "3.x"},
            "dependencies": [],
            "pip_check": {"status": "ok", "details": "ok"},
            "env": {"dotenv_loaded": False, "model_key": "set"},
            "model_key": {"status": "set", "env_var": "AMADEUS_MODEL_API_KEY"},
            "playwright": {"status": "ok"},
            "docker": {
                "status": "blocked",
                "image_ref": "amadeus-k-sandbox-python:phase2",
                "network_policy": "none",
            },
            "phase_readiness": {"graph": "ready", "live_browser": "ready", "sandbox_phase2": "blocked"},
            "remediation": [{"kind": "docker_unavailable", "install_hint": "Install Docker Desktop."}],
        }

        rendered = render_runtime_doctor_report(report, phase="sandbox_phase2")

        self.assertIn("[doctor:sandbox_phase2]", rendered)
        self.assertIn("docker", rendered.lower())
        self.assertIn("image_ref=amadeus-k-sandbox-python:phase2", rendered)
        self.assertIn("network_policy=none", rendered)
        self.assertIn("[global-blockers]", rendered)


if __name__ == "__main__":
    unittest.main()
