from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from evals.run_langsmith_evals import (
    _build_local_suite_report,
    _child_suite_command,
    _example_case_ref,
    _parse_args,
    _run_graph,
    _single_suite_report_path,
    _select_suite_examples,
    _selected_suite_names,
    _write_local_eval_report,
    _write_suite_case_cache,
)


class EvalRunnerControlTests(unittest.TestCase):
    def test_run_graph_returns_runtime_state_fields_from_graph_state(self) -> None:
        run_dir = Path(self.id().replace(".", "_"))
        run_dir = Path.cwd() / "tests" / "_tmp" / run_dir
        run_dir.mkdir(parents=True, exist_ok=True)

        seed_state = {
            "emotion_state": {"label": "care"},
            "interaction_carryover": {"carryover_mode": "repair_residue", "strength": 0.33},
        }

        class _StubGraph:
            def __init__(self) -> None:
                self.seed: dict[str, object] = {}

            def update_state(self, cfg: dict[str, object], state: dict[str, object], as_node: str | None = None) -> None:
                self.seed = dict(state)

            def invoke(self, payload: dict[str, object], config: dict[str, object] | None = None) -> dict[str, object]:
                return {"messages": [SimpleNamespace(content="stub-answer")]}

            def get_state(self, cfg: dict[str, object]) -> SimpleNamespace:
                values = {
                    **self.seed,
                    "behavior_action": {"interaction_mode": "relationship_sensitive", "action_target": "protect_relationship_boundary"},
                    "current_event": {"kind": "user_utterance", "text": "hi"},
                    "interaction_carryover": {"carryover_mode": "repair_residue", "strength": 0.33},
                    "world_model_state": {"presence_residue": 0.24, "bond_depth": 0.58},
                    "semantic_narrative_profile": {"history_weight": 0.62, "repair_residue": 0.54},
                    "agenda_lifecycle_residue": {"kind": "held", "carryover_mode": "quiet_recontact"},
                }
                return SimpleNamespace(values=values)

        class _StubStore:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                pass

            def get_profile(self) -> dict[str, object]:
                return {}

            def get_relationship(self) -> dict[str, object]:
                return {}

            def list_moments(self, limit: int = 80) -> list[dict[str, object]]:
                return []

            def list_skills(self) -> list[dict[str, object]]:
                return []

            def list_worldline_events(self, limit: int = 80) -> list[dict[str, object]]:
                return []

            def list_relationship_timeline(self, limit: int = 80) -> list[dict[str, object]]:
                return []

            def list_conflict_repairs(self, limit: int = 80) -> list[dict[str, object]]:
                return []

            def list_commitments(self, limit: int = 80) -> list[dict[str, object]]:
                return []

            def list_unresolved_tensions(self, limit: int = 80) -> list[dict[str, object]]:
                return []

            def list_semantic_self_narratives(self, limit: int = 80) -> list[dict[str, object]]:
                return []

            def list_revision_traces(self, limit: int = 80) -> list[dict[str, object]]:
                return []

            def list_source_refs(self, limit: int = 80) -> list[dict[str, object]]:
                return []

            def list_memory_quarantine(self, limit: int = 80) -> list[dict[str, object]]:
                return []

            def close(self) -> None:
                return None

        with (
            patch("evals.run_langsmith_evals._prepare_case_runtime", return_value=run_dir),
            patch("evals.run_langsmith_evals.reset_runtime_caches", return_value=None),
            patch("evals.run_langsmith_evals.reset_tool_runtime_caches", return_value=None),
            patch("evals.run_langsmith_evals.build_graph", return_value=_StubGraph()),
            patch(
                "evals.run_langsmith_evals.get_settings",
                return_value=SimpleNamespace(memory_db_path=run_dir / "memories.sqlite", data_dir=run_dir),
            ),
            patch("evals.run_langsmith_evals.MemoryStore", _StubStore),
            patch("evals.run_langsmith_evals._tool_names_from_audit", return_value=[]),
        ):
            answer, tools, outputs = _run_graph(
                ["hi"],
                thread_id="stub-thread",
                case_key="stub-case",
                seed_thread_state=seed_state,
                reset_case_runtime=True,
            )

        self.assertEqual(answer, "stub-answer")
        self.assertEqual(tools, [])
        self.assertEqual(outputs["interaction_carryover"]["carryover_mode"], "repair_residue")
        self.assertAlmostEqual(float(outputs["interaction_carryover"]["strength"]), 0.33, places=3)
        self.assertEqual(outputs["world_model_state"]["bond_depth"], 0.58)
        self.assertEqual(outputs["semantic_narrative_profile"]["repair_residue"], 0.54)
        self.assertEqual(outputs["agenda_lifecycle_residue"]["kind"], "held")

    def test_example_case_ref_strips_run_specific_hex_segment(self) -> None:
        case_ref = _example_case_ref(
            {"thread_id": "natural-long-c14d065c-selfhood-carry-0"},
            "natural_long_thread",
            7,
        )
        self.assertEqual(case_ref, "natural-long-selfhood-carry-0")

    def test_select_suite_examples_filters_by_case_ref_and_respects_cap(self) -> None:
        examples = [
            {"thread_id": "natural-long-alpha", "input": "A", "tags": ["x"]},
            {"thread_id": "natural-long-beta", "input": "B", "tags": ["target"]},
            {"thread_id": "natural-long-gamma", "input": "C", "tags": ["target"]},
        ]
        selected = _select_suite_examples(
            examples,
            "natural_long_thread",
            case_filters=["target"],
            max_cases=1,
        )
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0][0], 2)
        self.assertEqual(selected[0][1]["thread_id"], "natural-long-beta")

    def test_build_local_suite_report_reuses_cached_cases_on_resume(self) -> None:
        run_dir = Path(self.id().replace(".", "_"))
        run_dir = Path.cwd() / "tests" / "_tmp" / run_dir
        run_dir.mkdir(parents=True, exist_ok=True)
        example = {"thread_id": "natural-long-selfhood-carry-0", "input": "hello", "tags": ["companion"]}
        cached_case = {
            "case_id": "natural_long_thread-001",
            "case_ref": "natural-long-selfhood-carry-0",
            "input": "hello",
            "turns": None,
            "tags": ["companion"],
            "answer_preview": "cached",
            "tool_calls": [],
            "ooc_detector": {},
            "canon_guard": {},
            "claim_links": [],
            "persona_state": {},
            "emotion_state": {},
            "bond_state": {},
            "allostasis_state": {},
            "counterpart_assessment": {},
            "behavior_policy": {},
            "behavior_action": {},
            "semantic_narrative_profile": {},
            "current_event": {},
            "recent_events": [],
            "turn_appraisal": {},
            "relationship_state": {},
            "relationship_timeline": [],
            "conflict_repair": [],
            "unresolved_tensions": [],
            "semantic_self_narratives": [],
            "revision_traces": [],
            "memory_guard_checked": 0,
            "memory_guard_blocked": 0,
            "memory_quarantine": [],
            "relationship_weather_trace": {},
            "metric_snapshot": {"ooc_rate": 0.0},
            "metric_applicability": {"ooc_rate": 1},
            "evaluator_results": [],
            "failed_evaluators": [],
        }
        cache_path = run_dir / "_suite_cache" / "natural_long_thread" / "natural-long-selfhood-carry-0.json"
        _write_suite_case_cache(cache_path, cached_case)

        with patch("evals.run_langsmith_evals._target", side_effect=AssertionError("cache should be reused")):
            report = _build_local_suite_report(
                [example],
                "natural_long_thread",
                [],
                run_dir=run_dir,
                resume=True,
                show_progress=False,
            )

        self.assertEqual(report["num_cases"], 1)
        self.assertEqual(report["cases"][0]["answer_preview"], "cached")

    def test_selected_suite_names_supports_core_pre_release_group(self) -> None:
        self.assertEqual(
            _selected_suite_names("core_pre_release"),
            [
                "natural_long_thread",
                "open_evolution_eval",
                "selfhood_probe",
                "experience_probe",
                "transfer_probe",
            ],
        )

    def test_parse_args_accepts_core_pre_release_group(self) -> None:
        args = _parse_args(["--suite", "core_pre_release", "--local-only"])
        self.assertEqual(args.suite, "core_pre_release")
        self.assertTrue(args.local_only)

    def test_child_suite_command_reuses_parent_run_dir(self) -> None:
        args = _parse_args(
            [
                "--suite",
                "core_pre_release",
                "--local-only",
                "--max-cases",
                "2",
                "--case",
                "science",
                "--keep-eval-data",
            ]
        )
        command = _child_suite_command(args, "experience_probe", Path("E:/tmp/eval-root"))
        self.assertIn("--suite", command)
        self.assertIn("experience_probe", command)
        self.assertIn("--resume-run-dir", command)
        self.assertIn("E:/tmp/eval-root", [item.replace("\\", "/") for item in command])
        self.assertIn("--local-only", command)
        self.assertIn("--keep-eval-data", command)
        self.assertIn("--max-cases", command)
        self.assertIn("2", command)
        self.assertIn("--case", command)
        self.assertIn("science", command)

    def test_single_suite_report_path_is_stable(self) -> None:
        path = _single_suite_report_path(Path("E:/tmp/eval-root"), "open_evolution_eval")
        self.assertEqual(str(path).replace("\\", "/"), "E:/tmp/eval-root/local-report-open_evolution_eval.json")

    def test_write_local_eval_report_emits_suite_specific_artifact_for_single_suite(self) -> None:
        run_dir = Path(self.id().replace(".", "_"))
        run_dir = Path.cwd() / "tests" / "_tmp" / run_dir
        report = {
            "run_id": "testrun",
            "generated_at": "2026-03-17 10:00:00",
            "mode": "local_only",
            "run_dir": str(run_dir),
            "suites": [
                {
                    "suite": "experience_probe",
                    "num_cases": 1,
                    "aggregated_metrics": {},
                    "metric_coverage": {},
                    "evaluator_summary": {},
                    "failing_cases": [],
                    "cases": [],
                }
            ],
            "summary": {"experience_probe": {}},
        }
        _write_local_eval_report(report, run_dir=run_dir)
        self.assertTrue((run_dir / "local-report-experience_probe.json").exists())
        self.assertTrue((run_dir / "local-report-experience_probe.md").exists())


if __name__ == "__main__":
    unittest.main()
