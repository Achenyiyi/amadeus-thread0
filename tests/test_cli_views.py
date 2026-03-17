import unittest

from amadeus_thread0.cli_views import (
    build_behavior_queue_cli_summary,
    build_evolution_cli_summary,
    build_evolution_summary_line,
    render_behavior_queue_cli_text,
)
from amadeus_thread0.evolution_engine.reconsolidation import build_reconsolidation_snapshot


class CliViewsTests(unittest.TestCase):
    def test_build_evolution_cli_summary_surfaces_continuity_vector(self):
        summary = build_evolution_cli_summary(
            relationship={
                "stage": "warming",
                "affinity_score": 0.72,
                "trust_score": 0.74,
                "notes": "逐渐熟悉起来。",
            },
            semantic_narrative_profile={
                "presence_carry": 0.58,
                "ambient_attunement": 0.46,
                "rhythm_continuity": 0.63,
                "history_weight": 0.67,
                "dominant_category": "rhythm_style",
                "active_categories": ["presence_style", "rhythm_style"],
                "reactivated_categories": ["ambient_style"],
                "summary_lines": ["上一轮留下的在场感会继续影响下一轮。"],
                "anchor_lines": ["红莉栖不会在每次回应前都把自己的内部节奏清零。"],
                "top_narratives": [
                    {
                        "category": "rhythm_style",
                        "score": 0.72,
                        "reactivated": True,
                        "text": "她会把自己的内部节奏延续到下一轮。",
                    }
                ],
                "identity_lines": ["红莉栖会把自己放在和冈部伦太郎平等互动的位置上。"],
                "identity_prompt_lines": ["你会把自己放在和冈部伦太郎平等互动的位置上。"],
                "long_term_self_narratives": [
                    {
                        "category": "selfhood_style",
                        "score": 0.77,
                        "horizon_tag": "long_term",
                        "text": "红莉栖会把自己放在和冈部伦太郎平等互动的位置上。",
                        "prompt_text": "你会把自己放在和冈部伦太郎平等互动的位置上。",
                    }
                ],
            },
            world_model_state={
                "presence_residue": 0.41,
                "ambient_resonance": 0.32,
                "self_activity_momentum": 0.57,
                "bond_depth": 0.64,
                "tension_load": 0.08,
                "selfhood_load": 0.42,
                "agency_load": 0.51,
                "memory_gravity": 0.48,
                "companionship_pull": 0.54,
                "task_pull": 0.20,
            },
            emotion_state={"label": "neutral"},
            bond_state={"trust": 0.68, "closeness": 0.66, "hurt": 0.04},
            counterpart_assessment={"stance": "open", "scene": "care_bid"},
            behavior_action={
                "interaction_mode": "self_activity_reopen",
                "action_target": "respond_now",
                "primary_motive": "gentle_recontact",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "先从自己的节奏里回头，留一个不压迫对方的小开口。",
                "relationship_weather": "warm_residue",
            },
            interaction_carryover={"carryover_mode": "own_rhythm", "strength": 0.57, "relationship_weather": "warm_residue"},
            worldline_focus=[
                {"summary": "刚才那阵风过去之后，她还是保留了在场感。"},
                {"summary": "她从自己的节奏里抬头回应。"},
            ],
            reconsolidation_snapshot={"event_kind": "user_utterance", "interaction_frame": "relationship"},
        )
        continuity = summary.get("continuity_vector") if isinstance(summary.get("continuity_vector"), dict) else {}
        self.assertEqual(continuity.get("presence"), {"semantic": 0.58, "world": 0.41})
        self.assertEqual(continuity.get("ambient"), {"semantic": 0.46, "world": 0.32})
        self.assertEqual(continuity.get("rhythm"), {"semantic": 0.63, "world": 0.57})
        semantic = summary.get("semantic_continuity") if isinstance(summary.get("semantic_continuity"), dict) else {}
        self.assertEqual(semantic.get("dominant_category"), "rhythm_style")
        self.assertIn("presence_style", semantic.get("active_categories") or [])
        self.assertIn("红莉栖不会在每次回应前都把自己的内部节奏清零。", semantic.get("anchor_lines") or [])
        identity = summary.get("identity_continuity") if isinstance(summary.get("identity_continuity"), dict) else {}
        self.assertEqual(identity.get("dominant_identity_category"), "selfhood_style")
        self.assertIn("你会把自己放在和冈部伦太郎平等互动的位置上。", identity.get("identity_prompt_lines") or [])
        self.assertEqual(len(summary.get("worldline_focus_preview") or []), 2)
        current_turn = summary.get("current_turn") if isinstance(summary.get("current_turn"), dict) else {}
        self.assertEqual(current_turn.get("carryover_weather"), "warm_residue")
        self.assertEqual(current_turn.get("behavior_weather"), "warm_residue")
        self.assertEqual(current_turn.get("primary_motive"), "gentle_recontact")
        self.assertEqual(current_turn.get("motive_tension"), "self_rhythm_vs_contact")

    def test_reconsolidation_snapshot_includes_residue_axes(self):
        snapshot = build_reconsolidation_snapshot(
            current_event={"kind": "user_utterance"},
            appraisal={
                "used": True,
                "interaction_frame": "relationship",
                "salience": {"relationship": 0.44},
            },
            world_model_state={
                "bond_depth": 0.61,
                "tension_load": 0.12,
                "repair_load": 0.14,
                "selfhood_load": 0.40,
                "agency_load": 0.48,
                "memory_gravity": 0.46,
                "presence_residue": 0.39,
                "ambient_resonance": 0.31,
                "self_activity_momentum": 0.55,
            },
            latent_state={"self_coherence": 0.74, "agency_pressure": 0.42, "reflection_drive": 0.46, "expression_freedom": 0.68},
            emotion_state={"label": "neutral"},
            bond_state={"trust": 0.66, "closeness": 0.64, "hurt": 0.02},
            behavior_action={
                "interaction_mode": "self_activity_reopen",
                "primary_motive": "gentle_recontact",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "先从自己的节奏里回头，留一个不压迫对方的小开口。",
            },
            agenda_lifecycle_residue={
                "kind": "released_to_self_activity",
                "source_event_kind": "scheduled_life_due",
                "trigger_family": "life_window",
                "carryover_mode": "own_rhythm",
                "carryover_strength": 0.53,
                "relationship_weather": "warm_residue",
                "hold_count": 2,
                "presence_residue": 0.33,
                "ambient_resonance": 0.24,
                "self_activity_momentum": 0.58,
                "own_rhythm_bias": 0.61,
                "recontact_cooldown": 0.47,
                "counterpart_scene_bias": "busy_not_disrespectful",
                "note": "前面挂着的窗口没有继续往前推，注意力被自然收回到了自己的节奏里。",
            },
        )
        world_model = snapshot.get("world_model") if isinstance(snapshot.get("world_model"), dict) else {}
        self.assertEqual(world_model.get("presence_residue"), 0.39)
        self.assertEqual(world_model.get("ambient_resonance"), 0.31)
        self.assertEqual(world_model.get("self_activity_momentum"), 0.55)
        self.assertEqual(snapshot.get("behavior_mode"), "self_activity_reopen")
        self.assertEqual(snapshot.get("primary_motive"), "gentle_recontact")
        self.assertEqual(snapshot.get("motive_tension"), "self_rhythm_vs_contact")
        self.assertIn("自己的节奏", str(snapshot.get("goal_frame") or ""))
        consequence = snapshot.get("behavior_consequence") if isinstance(snapshot.get("behavior_consequence"), dict) else {}
        self.assertEqual(str(consequence.get("kind") or ""), "leave_small_opening")
        self.assertIn("小开口", str(consequence.get("summary") or ""))
        lifecycle = snapshot.get("agenda_lifecycle_consequence") if isinstance(snapshot.get("agenda_lifecycle_consequence"), dict) else {}
        self.assertEqual(str(lifecycle.get("kind") or ""), "released_to_self_activity")
        self.assertEqual(str(lifecycle.get("carryover_mode") or ""), "own_rhythm")
        self.assertIn("自己的节奏", str(lifecycle.get("summary") or ""))
        self.assertIn("agency_style", lifecycle.get("narrative_categories") or [])
        self.assertEqual(str(lifecycle.get("primary_motive") or ""), "preserve_self_rhythm")
        self.assertEqual(str(lifecycle.get("motive_tension") or ""), "self_rhythm_vs_contact")
        self.assertIn("自己的节奏", str(lifecycle.get("goal_frame") or ""))

    def test_build_evolution_summary_line_is_compact_and_informative(self):
        summary = build_evolution_cli_summary(
            relationship={"stage": "warming", "affinity_score": 0.72, "trust_score": 0.74},
            semantic_narrative_profile={
                "presence_carry": 0.58,
                "ambient_attunement": 0.46,
                "rhythm_continuity": 0.63,
                "long_term_self_narratives": [
                    {
                        "category": "selfhood_style",
                        "score": 0.77,
                        "text": "红莉栖会把自己放在和冈部伦太郎平等互动的位置上。",
                    }
                ],
            },
            world_model_state={
                "presence_residue": 0.41,
                "ambient_resonance": 0.32,
                "self_activity_momentum": 0.57,
                "bond_depth": 0.64,
                "tension_load": 0.08,
            },
            counterpart_assessment={"stance": "open"},
            behavior_action={"interaction_mode": "self_activity_reopen", "primary_motive": "gentle_recontact"},
            interaction_carryover={"carryover_mode": "own_rhythm", "strength": 0.57, "relationship_weather": "guarded_residue"},
            reconsolidation_snapshot={
                "behavior_consequence": {
                    "kind": "leave_small_opening",
                    "summary": "她从自己的节奏里回头了，但只留了一个很轻的小开口。",
                }
            },
            agenda_lifecycle_residue={
                "kind": "held",
                "carryover_mode": "own_rhythm",
                "carryover_strength": 0.41,
                "hold_count": 2,
                "recontact_cooldown": 0.52,
            },
        )
        line = build_evolution_summary_line(summary)
        self.assertIn("presence=0.580/0.410", line)
        self.assertIn("ambient=0.460/0.320", line)
        self.assertIn("rhythm=0.630/0.570", line)
        self.assertIn("mode=self_activity_reopen", line)
        self.assertIn("motive=gentle_recontact", line)
        self.assertIn("cons=leave_small_opening", line)
        self.assertIn("carry=own_rhythm:0.570", line)
        self.assertIn("weather=guarded_residue", line)
        self.assertIn("identity=selfhood_style:0.770", line)
        self.assertIn("lifecycle=held:own_rhythm:0.410", line)
        self.assertIn("holds=2", line)
        self.assertIn("cool=0.520", line)
        self.assertIn("bond=0.640", line)

    def test_build_evolution_cli_summary_surfaces_window_profile_and_event_residue(self):
        summary = build_evolution_cli_summary(
            relationship={"stage": "warming", "affinity_score": 0.72, "trust_score": 0.74},
            world_model_state={
                "presence_residue": 0.41,
                "ambient_resonance": 0.32,
                "self_activity_momentum": 0.57,
                "bond_depth": 0.64,
                "tension_load": 0.08,
            },
            behavior_action={
                "interaction_mode": "scheduled_life_nudge",
                "action_target": "wait_and_recheck",
                "relationship_weather": "warm_residue",
                "window_profile": {
                    "profile_type": "scheduled_window",
                    "event_kind": "scheduled_life_due",
                    "family": "life",
                    "trigger_family": "life_window",
                    "decision": "wait_and_recheck",
                    "maturity": 0.52,
                    "required_maturity": 0.58,
                    "invite_ready": False,
                    "recheck_min": 18,
                    "carryover_mode": "small_opening",
                    "carryover_strength": 0.44,
                    "presence_residue": 0.38,
                    "ambient_resonance": 0.27,
                    "self_activity_momentum": 0.49,
                    "recontact_echo": 0.38,
                    "own_rhythm_load": 0.49,
                    "continuity_bonus": 0.08,
                    "continuity_discount": 0.02,
                },
            },
            behavior_plan={
                "kind": "deferred_checkin",
                "target": "counterpart",
                "trigger_family": "life_window",
                "scheduled_after_min": 18,
                "primary_motive": "honor_continuity",
                "motive_tension": "self_rhythm_vs_contact",
                "goal_frame": "先把前面那点生活上的惦记轻轻接回来。",
                "carryover_mode": "small_opening",
                "carryover_strength": 0.44,
                "relationship_weather": "warm_residue",
            },
            behavior_queue=[
                {
                    "agenda_id": "abc123",
                    "kind": "deferred_checkin",
                    "target": "counterpart",
                    "status": "pending",
                    "trigger_family": "life_window",
                    "scheduled_after_min": 18,
                    "expires_after_min": 180,
                    "priority": 0.58,
                    "base_priority": 0.52,
                    "hold_count": 1,
                    "carryover_mode": "small_opening",
                    "carryover_strength": 0.44,
                    "relationship_weather": "warm_residue",
                    "presence_residue": 0.38,
                    "ambient_resonance": 0.27,
                    "self_activity_momentum": 0.49,
                    "attention_target": "counterpart_state",
                    "note": "窗口先留着，等更自然的时候再推进",
                }
            ],
            current_event={
                "kind": "scheduled_life_due",
                "trigger_family": "life_window",
                "carryover_mode": "small_opening",
                "carryover_strength": 0.44,
                "relationship_weather": "warm_residue",
                "presence_residue": 0.38,
                "ambient_resonance": 0.27,
                "self_activity_momentum": 0.49,
                "scheduled_after_min": 18,
            },
            interaction_carryover={"carryover_mode": "small_opening", "strength": 0.44, "relationship_weather": "warm_residue"},
            agenda_lifecycle_residue={
                "kind": "released_to_self_activity",
                "source_event_kind": "scheduled_life_due",
                "trigger_family": "life_window",
                "carryover_mode": "own_rhythm",
                "carryover_strength": 0.53,
                "relationship_weather": "warm_residue",
                "hold_count": 2,
                "idle_minutes": 18,
                "attention_target": "counterpart_state",
                "presence_residue": 0.33,
                "ambient_resonance": 0.24,
                "self_activity_momentum": 0.58,
                "own_rhythm_bias": 0.61,
                "recontact_cooldown": 0.47,
                "counterpart_scene_bias": "busy_not_disrespectful",
                "counterpart_boundary_delta": -0.04,
                "source_tags": ["user_busy", "agenda_lifecycle"],
                "note": "前面挂着的窗口没有继续往前推，注意力被自然收回到了自己的节奏里。",
            },
        )
        opening = summary.get("opening_window") if isinstance(summary.get("opening_window"), dict) else {}
        self.assertEqual(opening.get("profile_type"), "scheduled_window")
        self.assertEqual(opening.get("maturity"), 0.52)
        self.assertEqual(opening.get("required_maturity"), 0.58)
        self.assertEqual(opening.get("gap"), -0.06)
        self.assertFalse(opening.get("invite_ready"))
        event_residue = summary.get("event_residue") if isinstance(summary.get("event_residue"), dict) else {}
        self.assertEqual(event_residue.get("event_kind"), "scheduled_life_due")
        self.assertEqual(event_residue.get("carryover_mode"), "small_opening")
        self.assertEqual(event_residue.get("relationship_weather"), "warm_residue")
        self.assertEqual(event_residue.get("scheduled_after_min"), 18)
        lifecycle = summary.get("agenda_lifecycle") if isinstance(summary.get("agenda_lifecycle"), dict) else {}
        self.assertEqual(lifecycle.get("kind"), "released_to_self_activity")
        self.assertEqual(lifecycle.get("carryover_mode"), "own_rhythm")
        self.assertEqual(lifecycle.get("carryover_strength"), 0.53)
        self.assertEqual(lifecycle.get("recontact_cooldown"), 0.47)
        self.assertEqual(lifecycle.get("counterpart_scene_bias"), "busy_not_disrespectful")
        self.assertIn("agenda_lifecycle", lifecycle.get("source_tags") or [])
        queue_preview = summary.get("behavior_queue_preview") if isinstance(summary.get("behavior_queue_preview"), list) else []
        self.assertEqual(len(queue_preview), 1)
        self.assertEqual(queue_preview[0].get("kind"), "deferred_checkin")
        self.assertEqual(queue_preview[0].get("relationship_weather"), "warm_residue")
        behavior_plan = summary.get("behavior_plan") if isinstance(summary.get("behavior_plan"), dict) else {}
        self.assertEqual(behavior_plan.get("relationship_weather"), "warm_residue")
        self.assertEqual(behavior_plan.get("primary_motive"), "honor_continuity")
        self.assertEqual(behavior_plan.get("motive_tension"), "self_rhythm_vs_contact")
        line = build_evolution_summary_line(summary)
        self.assertIn("window=scheduled_window:0.520/0.580", line)
        self.assertIn("decision=wait_and_recheck", line)
        self.assertIn("recheck=18m", line)
        self.assertIn("lifecycle=released_to_self_activity:own_rhythm:0.530", line)

    def test_render_behavior_queue_cli_text_is_readable(self):
        queue = [
            {
                "agenda_id": "abc123",
                "kind": "deferred_checkin",
                "target": "counterpart",
                "status": "pending",
                "trigger_family": "life_window",
                "scheduled_after_min": 18,
                "expires_after_min": 180,
                "priority": 0.58,
                "base_priority": 0.52,
                "hold_count": 2,
                "carryover_mode": "small_opening",
                "carryover_strength": 0.44,
                "relationship_weather": "warm_residue",
                "presence_residue": 0.38,
                "ambient_resonance": 0.27,
                "self_activity_momentum": 0.49,
                "attention_target": "counterpart_state",
                "note": "窗口先留着，等更自然的时候再推进",
            }
        ]
        rows = build_behavior_queue_cli_summary(queue)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("hold_count"), 2)
        rendered = render_behavior_queue_cli_text(queue)
        self.assertIn("#1 deferred_checkin/life_window", rendered)
        self.assertIn("holds=2", rendered)
        self.assertIn("carry=small_opening:0.440", rendered)
        self.assertIn("weather=warm_residue", rendered)
        self.assertIn("note=窗口先留着", rendered)


if __name__ == "__main__":
    unittest.main()
