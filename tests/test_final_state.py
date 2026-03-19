from __future__ import annotations

import unittest
from unittest.mock import patch

from amadeus_thread0.runtime.final_state import resolve_behavior_payloads


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


if __name__ == "__main__":
    unittest.main()
