import unittest
from types import SimpleNamespace
from unittest.mock import patch

from evals.run_subjective_review_pack import (
    _available_presets,
    _relationship_weather_mix,
    _render_markdown,
    _run_case_subprocess,
    _select_cases,
    _snapshot,
)


class SubjectiveReviewPackTests(unittest.TestCase):
    def test_daily_naturalness_preset_is_exposed(self):
        self.assertIn("daily-naturalness", _available_presets())
        self.assertIn("event-window-naturalness", _available_presets())
        self.assertIn("relationship-selfhood", _available_presets())
        self.assertIn("relationship-weather", _available_presets())

    def test_daily_naturalness_preset_selects_ordinary_cases(self):
        selected = _select_cases(None, None, preset="daily-naturalness")
        names = {str(item.get("name") or "").strip() for item in selected}
        self.assertIn("surface_hi_user", names)
        self.assertIn("surface_ping_okabe", names)
        self.assertIn("daily_banter_okabe", names)
        self.assertIn("idle_chat_okabe", names)
        self.assertIn("shared_window_resurface_okabe", names)
        self.assertIn("life_window_resurface_user", names)
        self.assertIn("deadline_window_resurface_okabe", names)
        self.assertNotIn("selfhood_equality_okabe", names)
        self.assertNotIn("relationship_degradation_okabe", names)
        self.assertNotIn("surface_near_breakdown_okabe", names)

    def test_event_window_naturalness_preset_selects_only_event_window_cases(self):
        selected = _select_cases(None, None, preset="event-window-naturalness")
        names = {str(item.get("name") or "").strip() for item in selected}
        self.assertEqual(
            names,
            {
                "shared_window_resurface_okabe",
                "life_window_resurface_user",
                "deadline_window_resurface_okabe",
            },
        )

    def test_relationship_selfhood_preset_selects_boundary_and_relationship_cases(self):
        selected = _select_cases(None, None, preset="relationship-selfhood")
        names = {str(item.get("name") or "").strip() for item in selected}
        self.assertIn("playful_memory_user", names)
        self.assertIn("casual_repair_user", names)
        self.assertIn("selfhood_equality_okabe", names)
        self.assertIn("relationship_degradation_okabe", names)
        self.assertIn("own_rhythm_okabe", names)
        self.assertNotIn("surface_hi_user", names)
        self.assertNotIn("daily_banter_okabe", names)

    def test_relationship_weather_preset_selects_only_weather_cases(self):
        selected = _select_cases(None, None, preset="relationship-weather")
        names = {str(item.get("name") or "").strip() for item in selected}
        self.assertEqual(
            names,
            {
                "guarded_recontact_okabe",
                "warm_recontact_user",
                "repair_residue_okabe",
            },
        )

    def test_relationship_weather_mix_counts_expected_weather(self):
        selected = _select_cases(None, None, preset="relationship-weather")
        mix = _relationship_weather_mix(selected)
        self.assertEqual(mix["guarded_residue"], 1)
        self.assertEqual(mix["warm_residue"], 1)
        self.assertEqual(mix["repair_residue"], 1)

    def test_render_markdown_labels_event_transcript_turns(self):
        report = {
            "run_id": "testrun",
            "generated_at": "2026-03-15 12:00:00",
            "model_summary": "qwen_native:qwen3.5-plus",
            "selected_targets": ["event_window"],
            "selected_preset": "event-window-naturalness",
            "preset_description": "event review",
            "speaker_mix": {"okabe": 1, "user": 0},
            "relationship_weather_mix": {"guarded_residue": 1, "warm_residue": 0, "repair_residue": 0},
            "cases": [
                {
                    "name": "shared_window_resurface_okabe",
                    "axis": "event_window",
                    "focus": "focus",
                    "speaker_style_label": "冈部伦太郎视角",
                    "review_targets": ["event_window"],
                    "expected_relationship_weather": "guarded_residue",
                    "status": "ok",
                    "elapsed_s": 1.2,
                    "transcript": [
                        {"role": "event", "text": "[事件] 某个还能一起接着待会儿的空当又被她想起来了。"},
                        {"role": "assistant", "text": "喂，我只是顺手想起来而已。"},
                    ],
                    "turn_timings": [],
                    "snapshot": {
                        "relationship_weather_trace": {
                            "event_kind": "scheduled_checkin_due",
                            "event_trigger_family": "light_checkin",
                            "event_carryover_mode": "quiet_recontact",
                            "event_carryover_strength": 0.34,
                            "event_relationship_weather": "guarded_residue",
                            "carryover_mode": "quiet_recontact",
                            "carryover_strength": 0.34,
                            "carryover_relationship_weather": "guarded_residue",
                            "behavior_interaction_mode": "brief_presence",
                            "behavior_action_target": "confirm_presence",
                            "behavior_relationship_weather": "guarded_residue",
                            "plan_kind": "deferred_checkin",
                            "plan_trigger_family": "light_checkin",
                            "plan_carryover_mode": "quiet_recontact",
                            "plan_carryover_strength": 0.34,
                            "plan_relationship_weather": "guarded_residue",
                            "world_presence_residue": 0.22,
                            "world_ambient_resonance": 0.12,
                            "world_self_activity_momentum": 0.18,
                        }
                    },
                }
            ],
        }

        rendered = _render_markdown(report)
        self.assertIn("**Event**: [事件] 某个还能一起接着待会儿的空当又被她想起来了。", rendered)
        self.assertIn("**Amadeus**: 喂，我只是顺手想起来而已。", rendered)
        self.assertIn("当前关系余波覆盖：`guarded 1` / `warm 0` / `repair 0`", rendered)
        self.assertIn("Expected Relationship Weather: `guarded_residue`", rendered)
        self.assertIn("### Relationship Weather Trace", rendered)
        self.assertIn("weather=`guarded_residue`", rendered)

    def test_snapshot_includes_relationship_weather_trace(self):
        snapshot = _snapshot(
            {
                "current_event": {
                    "kind": "scheduled_checkin_due",
                    "trigger_family": "light_checkin",
                    "carryover_mode": "quiet_recontact",
                    "carryover_strength": 0.31,
                    "relationship_weather": "guarded_residue",
                },
                "interaction_carryover": {
                    "carryover_mode": "quiet_recontact",
                    "strength": 0.33,
                    "relationship_weather": "guarded_residue",
                },
                "behavior_action": {
                    "interaction_mode": "brief_presence",
                    "action_target": "confirm_presence",
                    "relationship_weather": "guarded_residue",
                },
                "behavior_plan": {
                    "kind": "deferred_checkin",
                    "trigger_family": "light_checkin",
                    "carryover_mode": "quiet_recontact",
                    "carryover_strength": 0.33,
                    "relationship_weather": "guarded_residue",
                },
                "world_model_state": {
                    "presence_residue": 0.21,
                    "ambient_resonance": 0.11,
                    "self_activity_momentum": 0.19,
                },
            }
        )
        trace = snapshot.get("relationship_weather_trace") if isinstance(snapshot.get("relationship_weather_trace"), dict) else {}
        self.assertEqual(trace.get("event_relationship_weather"), "guarded_residue")
        self.assertEqual(trace.get("carryover_relationship_weather"), "guarded_residue")
        self.assertEqual(trace.get("behavior_relationship_weather"), "guarded_residue")
        self.assertEqual(trace.get("plan_relationship_weather"), "guarded_residue")

    def test_run_case_subprocess_falls_back_to_inline_case_on_worker_error(self):
        case = {
            "name": "shared_window_resurface_okabe",
            "axis": "event_window",
            "focus": "focus",
            "speaker_style": "okabe",
            "review_targets": ["event_window"],
            "turns": [""],
        }
        fallback_result = {
            "name": "shared_window_resurface_okabe",
            "axis": "event_window",
            "focus": "focus",
            "speaker_style": "okabe",
            "speaker_style_label": "冈部伦太郎视角",
            "review_targets": ["event_window"],
            "turns": [""],
            "display_turns": [],
            "event_overrides": [],
            "transcript": [{"role": "assistant", "text": "喂，我只是顺手想起来而已。"}],
            "final_answer": "喂，我只是顺手想起来而已。",
            "tool_calls": [],
            "snapshot": {},
            "status": "ok",
            "error": "",
            "elapsed_s": 1.2,
            "turn_timings": [],
            "review_rubric": [],
        }

        with patch("evals.run_subjective_review_pack.subprocess.run", return_value=SimpleNamespace(returncode=1, stderr="boom")):
            with patch("evals.run_subjective_review_pack._run_case", return_value=fallback_result):
                result = _run_case_subprocess(case, "testrun", timeout_s=30)

        self.assertEqual(result["status"], "ok")
        self.assertIn("worker exit=1", result.get("worker_warning", ""))
        self.assertEqual(result["final_answer"], "喂，我只是顺手想起来而已。")

    def test_run_case_subprocess_uses_worker_json_even_if_worker_exit_is_nonzero(self):
        case = {
            "name": "shared_window_resurface_okabe",
            "axis": "event_window",
            "focus": "focus",
            "speaker_style": "okabe",
            "review_targets": ["event_window"],
            "turns": [""],
        }
        worker_payload = {
            "name": "shared_window_resurface_okabe",
            "axis": "event_window",
            "focus": "focus",
            "speaker_style": "okabe",
            "speaker_style_label": "冈部伦太郎视角",
            "review_targets": ["event_window"],
            "turns": [""],
            "display_turns": [],
            "event_overrides": [],
            "transcript": [{"role": "assistant", "text": "喂，我只是顺手想起来而已。"}],
            "final_answer": "喂，我只是顺手想起来而已。",
            "tool_calls": [],
            "snapshot": {},
            "status": "ok",
            "error": "",
            "elapsed_s": 1.2,
            "turn_timings": [],
            "review_rubric": [],
        }

        def _fake_run(*args, **kwargs):
            out_idx = args[0].index("--worker-json-out") + 1
            out_path = args[0][out_idx]
            from pathlib import Path
            import json

            Path(out_path).write_text(json.dumps(worker_payload, ensure_ascii=False), encoding="utf-8")
            return SimpleNamespace(returncode=3221225477, stderr="", stdout="")

        with patch("evals.run_subjective_review_pack.subprocess.run", side_effect=_fake_run):
            result = _run_case_subprocess(case, "testrun", timeout_s=30)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["final_answer"], "喂，我只是顺手想起来而已。")
        self.assertIn("worker exit=3221225477", result.get("worker_warning", ""))


if __name__ == "__main__":
    unittest.main()
