import unittest
from unittest.mock import patch

from amadeus_thread0.graph_parts.response_finalize import _NATURAL_REWRITE_ISSUE_KEYS, _finalize_text_response


class ResponseFinalizeTests(unittest.TestCase):
    def test_natural_rewrite_triggers_on_brevity_and_template_drift(self):
        self.assertTrue(
            {"visible_template", "lecture_list", "overexplained"}.issubset(_NATURAL_REWRITE_ISSUE_KEYS)
        )

    def test_finalize_text_response_uses_entry_snapshot_for_light_rewrite_semantic_profile(self):
        fresh_profile = {
            "history_weight": 0.81,
            "prompt_anchor_lines": ["fresh-anchor"],
            "summary_lines": ["fresh-summary"],
        }
        mutated_profile = {
            "history_weight": 0.07,
            "prompt_anchor_lines": ["mutated-anchor"],
            "summary_lines": ["mutated-summary"],
        }
        state = {
            "science_mode": False,
            "semantic_narrative_profile": dict(fresh_profile),
            "interaction_carryover": {"carryover_mode": "small_opening"},
            "counterpart_assessment": {"scene": "care_bid"},
            "world_model_state": {"active_thread": "fresh"},
            "evidence_pack": [],
            "last_external_tools": [],
        }
        captured: dict[str, object] = {}

        def _mutating_rewrite_notes(*args, **kwargs):
            state["semantic_narrative_profile"] = dict(mutated_profile)
            return ["rewrite-needed"]

        def _capture_light_rewrite(**kwargs):
            captured["semantic_narrative_profile"] = kwargs.get("semantic_narrative_profile")
            return None

        with patch("amadeus_thread0.graph_parts.response_finalize._producer_surface_issues", return_value=[]):
            with patch(
                "amadeus_thread0.graph_parts.response_finalize._sanitize_final_answer",
                side_effect=lambda text, *_args, **_kwargs: text,
            ):
                with patch("amadeus_thread0.graph_parts.response_finalize._ooc_risk", return_value=(0.0, [])):
                    with patch("amadeus_thread0.graph_parts.response_finalize._persona_gap", return_value=(0.0, [])):
                        with patch(
                            "amadeus_thread0.graph_parts.response_finalize._dialogue_surface_issues",
                            return_value=[],
                        ):
                            with patch(
                                "amadeus_thread0.graph_parts.response_finalize._daily_surface_profile",
                                return_value={"score": 1.0},
                            ):
                                with patch(
                                    "amadeus_thread0.graph_parts.response_finalize._daily_surface_alignment_metrics",
                                    return_value={"score": 0.12},
                                ):
                                    with patch(
                                        "amadeus_thread0.graph_parts.response_finalize._light_dialog_rewrite_notes",
                                        side_effect=_mutating_rewrite_notes,
                                    ):
                                        with patch(
                                            "amadeus_thread0.graph_parts.response_finalize._light_dialog_surface_penalty",
                                            return_value=0.42,
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.response_finalize._should_run_light_dialog_rewrite",
                                                return_value=True,
                                            ):
                                                with patch(
                                                    "amadeus_thread0.graph_parts.response_finalize._rewrite_light_dialog_answer",
                                                    side_effect=_capture_light_rewrite,
                                                ):
                                                    with patch(
                                                        "amadeus_thread0.graph_parts.response_finalize._ensure_response_structure",
                                                        side_effect=lambda text, *_args, **_kwargs: text,
                                                    ):
                                                        with patch(
                                                            "amadeus_thread0.graph_parts.response_finalize.build_claim_attribution",
                                                            return_value=[],
                                                        ):
                                                            with patch(
                                                                "amadeus_thread0.graph_parts.response_finalize._canon_guard",
                                                                return_value={"ok": True},
                                                            ):
                                                                result = _finalize_text_response(
                                                                    state=state,
                                                                    store=object(),
                                                                    user_text="你在忙什么？",
                                                                    raw_draft_text="我刚刚在想一点别的事。",
                                                                    current_event={"kind": "user_utterance"},
                                                                    behavior_action={"interaction_mode": "self_activity_reopen"},
                                                                    response_style_hint="natural",
                                                                    continuation_mode=False,
                                                                    light_free_dialog=True,
                                                                    previous_assistant_text="",
                                                                    chosen_generation_profile={},
                                                                    generation_runtime_mode="default",
                                                                    generation_repetition_pressure=0.0,
                                                                    generation_recent_reply_max_similarity=0.0,
                                                                    generation_recent_reply_avg_similarity=0.0,
                                                                    generation_recent_reply_opener_repeat_ratio=0.0,
                                                                    generation_recent_reply_sample_size=0,
                                                                )

        self.assertEqual(captured.get("semantic_narrative_profile"), fresh_profile)
        self.assertEqual(state.get("semantic_narrative_profile"), mutated_profile)
        self.assertEqual(str((result.get("messages") or [None])[0].content or ""), "我刚刚在想一点别的事。")


if __name__ == "__main__":
    unittest.main()
