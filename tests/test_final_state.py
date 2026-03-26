from __future__ import annotations

import unittest
from unittest.mock import patch

from amadeus_thread0.runtime.final_state import (
    resolve_behavior_payloads,
    resolve_counterpart_assessment,
    resolve_interaction_carryover,
)


class FinalStateTests(unittest.TestCase):
    def test_resolve_behavior_payloads_prefers_persisted_plan_when_present(self):
        behavior_action = {
            "action_target": "offer_small_opening",
            "primary_motive": "gentle_recontact",
            "motive_tension": "self_rhythm_vs_contact",
            "goal_frame": "顺着余温轻轻回头。",
            "deferred_action_family": "small_opening",
            "relationship_weather": "warm_residue",
        }
        behavior_plan = {
            "kind": "deferred_checkin",
            "target": "counterpart",
            "trigger_family": "observe",
            "scheduled_after_min": 45,
            "legacy_hint": "keep-me",
        }

        with patch("amadeus_thread0.runtime.final_state._behavior_plan_from_action") as mock_derive:
            action, plan = resolve_behavior_payloads(
                behavior_action=behavior_action,
                behavior_plan=behavior_plan,
                current_event={"kind": "self_activity_state"},
                world_model_state={"presence_residue": 0.42},
            )

        self.assertEqual(action, behavior_action)
        self.assertEqual(plan, behavior_plan)
        mock_derive.assert_not_called()

    def test_resolve_behavior_payloads_derives_plan_only_when_final_plan_is_missing(self):
        behavior_action = {
            "action_target": "offer_small_opening",
            "primary_motive": "gentle_recontact",
            "motive_tension": "self_rhythm_vs_contact",
            "goal_frame": "顺着余温轻轻回头。",
            "deferred_action_family": "small_opening",
            "relationship_weather": "warm_residue",
        }
        partial_plan = {"legacy_hint": "keep-me"}

        with patch(
            "amadeus_thread0.runtime.final_state._behavior_plan_from_action",
            return_value={
                "kind": "small_opening",
                "target": "counterpart",
                "trigger_family": "small_opening",
                "scheduled_after_min": 0,
                "primary_motive": "gentle_recontact",
            },
        ) as mock_derive:
            _, plan = resolve_behavior_payloads(
                behavior_action=behavior_action,
                behavior_plan=partial_plan,
                current_event={"kind": "self_activity_state"},
                world_model_state={"presence_residue": 0.42},
            )

        self.assertEqual(plan["kind"], "small_opening")
        self.assertEqual(plan["trigger_family"], "small_opening")
        self.assertEqual(plan["legacy_hint"], "keep-me")
        mock_derive.assert_called_once()

    def test_resolve_behavior_payloads_prefers_frozen_reconsolidation_action_and_plan(self):
        live_action = {
            "action_target": "hold_own_rhythm",
            "interaction_mode": "self_activity_hold",
            "primary_motive": "preserve_self_rhythm",
            "goal_frame": "stale live action should not win",
        }
        live_plan = {
            "kind": "self_activity_continue",
            "trigger_family": "self_activity",
            "scheduled_after_min": 0,
        }
        reconsolidation_snapshot = {
            "behavior_action": {
                "action_target": "wait_and_recheck",
                "interaction_mode": "deferred_watch",
                "primary_motive": "honor_continuity",
                "motive_tension": "contact_without_pressure",
                "goal_frame": "顺着前面的惦记等更自然的时候再接回来。",
                "deferred_action_family": "life_window",
                "timing_window_min": 30,
                "relationship_weather": "warm_residue",
            },
            "behavior_plan": {
                "kind": "deferred_checkin",
                "target": "counterpart",
                "trigger_family": "observe",
                "scheduled_after_min": 30,
            },
        }

        with patch("amadeus_thread0.runtime.final_state._behavior_plan_from_action") as mock_derive:
            action, plan = resolve_behavior_payloads(
                behavior_action=live_action,
                behavior_plan=live_plan,
                reconsolidation_snapshot=reconsolidation_snapshot,
                current_event={"kind": "self_activity_state"},
                world_model_state={"presence_residue": 0.42},
            )

        self.assertEqual(action["action_target"], "wait_and_recheck")
        self.assertEqual(action["interaction_mode"], "deferred_watch")
        self.assertEqual(action["timing_window_min"], 30)
        self.assertEqual(plan["kind"], "deferred_checkin")
        self.assertEqual(plan["scheduled_after_min"], 30)
        mock_derive.assert_not_called()

    def test_resolve_behavior_payloads_derives_plan_from_frozen_action_before_live_plan(self):
        live_action = {
            "action_target": "hold_own_rhythm",
            "interaction_mode": "self_activity_hold",
            "primary_motive": "preserve_self_rhythm",
            "goal_frame": "stale live action should not win",
        }
        live_plan = {
            "kind": "self_activity_continue",
            "target": "self",
            "trigger_family": "self_activity",
            "scheduled_after_min": 45,
            "legacy_hint": "stale-live-plan",
        }
        reconsolidation_snapshot = {
            "behavior_action": {
                "action_target": "wait_and_recheck",
                "interaction_mode": "deferred_watch",
                "primary_motive": "honor_continuity",
                "motive_tension": "contact_without_pressure",
                "goal_frame": "顺着前面的惦记等更自然的时候再接回来。",
                "deferred_action_family": "life_window",
                "timing_window_min": 30,
                "relationship_weather": "warm_residue",
            }
        }

        with patch(
            "amadeus_thread0.runtime.final_state._behavior_plan_from_action",
            return_value={
                "kind": "deferred_checkin",
                "target": "counterpart",
                "trigger_family": "life_window",
                "scheduled_after_min": 30,
                "primary_motive": "honor_continuity",
            },
        ) as mock_derive:
            action, plan = resolve_behavior_payloads(
                behavior_action=live_action,
                behavior_plan=live_plan,
                reconsolidation_snapshot=reconsolidation_snapshot,
                current_event={"kind": "self_activity_state"},
                world_model_state={"presence_residue": 0.42},
            )

        self.assertEqual(action["action_target"], "wait_and_recheck")
        self.assertEqual(plan["kind"], "deferred_checkin")
        self.assertEqual(plan["trigger_family"], "life_window")
        self.assertEqual(plan["scheduled_after_min"], 30)
        self.assertNotIn("legacy_hint", plan)
        mock_derive.assert_called_once()

    def test_resolve_interaction_carryover_prefers_frozen_reconsolidation_snapshot(self):
        live_carryover = {
            "source": "live",
            "strength": 0.18,
            "carryover_mode": "fading_residue",
            "relationship_weather": "thin_residue",
        }
        reconsolidation_snapshot = {
            "interaction_carryover": {
                "source": "reconsolidation",
                "strength": 0.53,
                "carryover_mode": "own_rhythm",
                "relationship_weather": "warm_residue",
                "note": "final carryover should win",
            }
        }

        carryover = resolve_interaction_carryover(
            interaction_carryover=live_carryover,
            reconsolidation_snapshot=reconsolidation_snapshot,
        )

        self.assertEqual(carryover["source"], "reconsolidation")
        self.assertEqual(carryover["carryover_mode"], "own_rhythm")
        self.assertEqual(carryover["strength"], 0.53)
        self.assertEqual(carryover["relationship_weather"], "warm_residue")

    def test_resolve_counterpart_assessment_normalizes_extended_profile_axes(self):
        assessment = resolve_counterpart_assessment(
            counterpart_assessment={
                "stance": "watchful",
                "scene": "repair_attempt",
                "respect_level": 0.63,
                "reciprocity": 0.58,
                "boundary_pressure": 0.24,
                "reliability_read": 0.71,
            }
        )

        profile = assessment.get("assessment_profile") if isinstance(assessment.get("assessment_profile"), dict) else {}
        self.assertEqual(assessment["scene"], "repair_attempt")
        self.assertEqual(profile["dominant_scene_signal"], "repair")
        self.assertGreaterEqual(profile["repairability"], 0.6)
        self.assertGreaterEqual(profile["predictability"], 0.5)
        self.assertGreaterEqual(profile["safety_read"], 0.5)
        self.assertGreaterEqual(profile["closeness_read"], 0.45)

    def test_resolve_counterpart_assessment_prefers_frozen_snapshot_and_preserves_normalized_profile(self):
        assessment = resolve_counterpart_assessment(
            counterpart_assessment={"stance": "open", "scene": "care_bid"},
            reconsolidation_snapshot={
                "counterpart": {
                    "summary": "她会先把这次靠近当成一次谨慎但可修复的重新接近。",
                    "stance": "watchful",
                    "scene": "repair_attempt",
                    "respect_level": 0.63,
                    "reciprocity": 0.58,
                    "boundary_pressure": 0.24,
                    "reliability_read": 0.71,
                }
            },
        )

        profile = assessment.get("assessment_profile") if isinstance(assessment.get("assessment_profile"), dict) else {}
        self.assertEqual(assessment["scene"], "repair_attempt")
        self.assertEqual(profile["dominant_scene_signal"], "repair")
        self.assertIn("repairability", profile)
        self.assertIn("dependency_risk", profile)


if __name__ == "__main__":
    unittest.main()
