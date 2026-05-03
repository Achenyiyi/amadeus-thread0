from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]

_BANNED_IMPORT_SNIPPETS = (
    "from amadeus_thread0.graph import",
    "from amadeus_thread0.session_orchestrator import",
    "from amadeus_thread0.settings import",
    "from amadeus_thread0.tools import",
    "from amadeus_thread0.tool_registry import",
    "from amadeus_thread0.cli_views import",
)

_INTERNAL_ENTRYPOINTS = (
    PROJECT_ROOT / "amadeus_thread0" / "cli.py",
    PROJECT_ROOT / "evals" / "run_langsmith_evals.py",
    PROJECT_ROOT / "evals" / "run_backend_reliability_checks.py",
    PROJECT_ROOT / "evals" / "run_provider_greeting_probe.py",
    PROJECT_ROOT / "evals" / "run_appraisal_calibration.py",
)

_GRAPH_FACADE_IMPORT_ALLOWLIST = {
    PROJECT_ROOT / "tests" / "test_graph_facade.py",
}


class ImportBoundaryTests(unittest.TestCase):
    def test_internal_entrypoints_do_not_use_top_level_compat_facades(self) -> None:
        failures: list[str] = []
        for path in _INTERNAL_ENTRYPOINTS:
            text = path.read_text(encoding="utf-8")
            for snippet in _BANNED_IMPORT_SNIPPETS:
                if snippet in text:
                    failures.append(f"{path.name}: {snippet}")
        self.assertEqual(failures, [])

    def test_repo_only_uses_graph_facade_in_dedicated_compat_test(self) -> None:
        failures: list[str] = []
        for path in PROJECT_ROOT.rglob("*.py"):
            if path == PROJECT_ROOT / "amadeus_thread0" / "graph.py":
                continue
            if path == Path(__file__).resolve():
                continue
            text = path.read_text(encoding="utf-8")
            if "from amadeus_thread0.graph import" not in text:
                continue
            if path not in _GRAPH_FACADE_IMPORT_ALLOWLIST:
                failures.append(str(path.relative_to(PROJECT_ROOT)))
        self.assertEqual(failures, [])

    def test_cli_does_not_import_runtime_bundle_before_argument_parsing(self) -> None:
        cli_text = (PROJECT_ROOT / "amadeus_thread0" / "cli.py").read_text(encoding="utf-8")
        pre_main = cli_text[: cli_text.index("def main(")]
        main_and_after = cli_text[cli_text.index("def main(") :]

        self.assertNotIn("from .runtime.runtime_bundle import RuntimeBundle", pre_main)
        self.assertIn("from .runtime.runtime_bundle import RuntimeBundle", main_and_after)

    def test_cli_loads_dotenv_before_config_import(self) -> None:
        cli_text = (PROJECT_ROOT / "amadeus_thread0" / "cli.py").read_text(encoding="utf-8")

        self.assertLess(cli_text.index("_CLI_DOTENV_LOADED_PATH = _load_cli_dotenv()"), cli_text.index("from .config import"))


if __name__ == "__main__":
    unittest.main()
