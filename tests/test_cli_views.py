import unittest

from amadeus_thread0.cli_views import build_evolution_cli_summary, build_evolution_summary_line
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
                "top_narratives": [
                    {
                        "category": "rhythm_style",
                        "score": 0.72,
                        "reactivated": True,
                        "text": "她会把自己的内部节奏延续到下一轮。",
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
            behavior_action={"interaction_mode": "self_activity_reopen", "action_target": "respond_now"},
            interaction_carryover={"carryover_mode": "own_rhythm", "strength": 0.57},
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
        self.assertEqual(len(summary.get("worldline_focus_preview") or []), 2)

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
        )
        world_model = snapshot.get("world_model") if isinstance(snapshot.get("world_model"), dict) else {}
        self.assertEqual(world_model.get("presence_residue"), 0.39)
        self.assertEqual(world_model.get("ambient_resonance"), 0.31)
        self.assertEqual(world_model.get("self_activity_momentum"), 0.55)

    def test_build_evolution_summary_line_is_compact_and_informative(self):
        summary = build_evolution_cli_summary(
            relationship={"stage": "warming", "affinity_score": 0.72, "trust_score": 0.74},
            semantic_narrative_profile={
                "presence_carry": 0.58,
                "ambient_attunement": 0.46,
                "rhythm_continuity": 0.63,
            },
            world_model_state={
                "presence_residue": 0.41,
                "ambient_resonance": 0.32,
                "self_activity_momentum": 0.57,
                "bond_depth": 0.64,
                "tension_load": 0.08,
            },
            counterpart_assessment={"stance": "open"},
            behavior_action={"interaction_mode": "self_activity_reopen"},
            interaction_carryover={"carryover_mode": "own_rhythm", "strength": 0.57},
        )
        line = build_evolution_summary_line(summary)
        self.assertIn("presence=0.580/0.410", line)
        self.assertIn("ambient=0.460/0.320", line)
        self.assertIn("rhythm=0.630/0.570", line)
        self.assertIn("mode=self_activity_reopen", line)
        self.assertIn("carry=own_rhythm:0.570", line)
        self.assertIn("bond=0.640", line)


if __name__ == "__main__":
    unittest.main()
