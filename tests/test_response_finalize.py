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

    def test_finalize_text_response_re_sanitizes_after_natural_rewrite(self):
        state = {
            "science_mode": False,
            "semantic_narrative_profile": {},
            "interaction_carryover": {},
            "counterpart_assessment": {"scene": "repair_attempt"},
            "world_model_state": {},
            "evidence_pack": [],
            "last_external_tools": [],
        }
        sanitize_inputs: list[str] = []

        def _sanitize(text, *_args, **_kwargs):
            sanitize_inputs.append(str(text))
            if text == "rewritten-with-meta":
                return "sanitized-final"
            return str(text)

        with patch("amadeus_thread0.graph_parts.response_finalize._producer_surface_issues", return_value=[]):
            with patch("amadeus_thread0.graph_parts.response_finalize._sanitize_final_answer", side_effect=_sanitize):
                with patch("amadeus_thread0.graph_parts.response_finalize._ooc_risk", return_value=(0.0, [])):
                    with patch("amadeus_thread0.graph_parts.response_finalize._persona_gap", return_value=(0.0, [])):
                        with patch(
                            "amadeus_thread0.graph_parts.response_finalize._dialogue_issues_with_recent_repeat",
                            side_effect=[["wording_meta_detour"], ["wording_meta_detour"], []],
                        ):
                            with patch(
                                "amadeus_thread0.graph_parts.response_finalize._effective_natural_dialog_target_flags",
                                return_value=["wording_meta_detour"],
                            ):
                                with patch(
                                    "amadeus_thread0.graph_parts.response_finalize._natural_dialog_rewrite_notes_for",
                                    return_value=["rewrite-needed"],
                                ):
                                    with patch(
                                        "amadeus_thread0.graph_parts.response_finalize._should_run_natural_dialog_rewrite",
                                        return_value=True,
                                    ):
                                        with patch(
                                            "amadeus_thread0.graph_parts.response_finalize._rewrite_natural_dialog_answer",
                                            return_value="rewritten-with-meta",
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.response_finalize._dialogue_surface_issues",
                                                return_value=[],
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
                                                                user_text="你要是还别扭就别硬装大度，照你现在的状态回我就好。",
                                                                raw_draft_text="draft",
                                                                current_event={"kind": "user_utterance"},
                                                                behavior_action={"interaction_mode": "relationship_sensitive"},
                                                                response_style_hint="relationship",
                                                                continuation_mode=False,
                                                                light_free_dialog=False,
                                                                previous_assistant_text="",
                                                                chosen_generation_profile={},
                                                                generation_runtime_mode="default",
                                                                generation_repetition_pressure=0.0,
                                                                generation_recent_reply_max_similarity=0.0,
                                                                generation_recent_reply_avg_similarity=0.0,
                                                                generation_recent_reply_opener_repeat_ratio=0.0,
                                                                generation_recent_reply_sample_size=0,
                                                            )

        self.assertIn("rewritten-with-meta", sanitize_inputs)
        self.assertEqual(str((result.get("messages") or [None])[0].content or ""), "sanitized-final")

    def test_finalize_text_response_rejects_light_rewrite_that_drops_embodied_continuity(self):
        state = {
            "science_mode": False,
            "semantic_narrative_profile": {},
            "interaction_carryover": {},
            "counterpart_assessment": {"scene": "open"},
            "world_model_state": {},
            "evidence_pack": [],
            "last_external_tools": [],
        }
        draft_text = "还卡在 workspace_write 这一步，我没法装作已经做完。"

        with patch("amadeus_thread0.graph_parts.response_finalize._producer_surface_issues", return_value=[]):
            with patch(
                "amadeus_thread0.graph_parts.response_finalize._sanitize_final_answer",
                side_effect=lambda text, *_args, **_kwargs: str(text),
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
                                    side_effect=[{"score": 0.12}, {"score": 0.26}],
                                ):
                                    with patch(
                                        "amadeus_thread0.graph_parts.response_finalize._light_dialog_rewrite_notes",
                                        return_value=["rewrite-needed"],
                                    ):
                                        with patch(
                                            "amadeus_thread0.graph_parts.response_finalize._light_dialog_surface_penalty",
                                            side_effect=[0.42, 0.18],
                                        ):
                                            with patch(
                                                "amadeus_thread0.graph_parts.response_finalize._should_run_light_dialog_rewrite",
                                                return_value=True,
                                            ):
                                                with patch(
                                                    "amadeus_thread0.graph_parts.response_finalize._rewrite_light_dialog_answer",
                                                    return_value="行，我先接着做。",
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
                                                                    user_text="你这边现在到底卡在哪里？",
                                                                    raw_draft_text=draft_text,
                                                                    current_event={"kind": "user_utterance"},
                                                                    behavior_action={
                                                                        "interaction_mode": "companion_reply",
                                                                        "embodied_context": {
                                                                            "kind": "access_request_pending",
                                                                            "requested_access": ["workspace_write", "human_approval"],
                                                                        },
                                                                    },
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

        self.assertEqual(str((result.get("messages") or [None])[0].content or ""), draft_text)


if __name__ == "__main__":
    unittest.main()
