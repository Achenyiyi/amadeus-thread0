import unittest

from amadeus_thread0.evolution_engine.reconsolidation import _compact_counterpart_snapshot
from amadeus_thread0.utils.counterpart_profile import (
    compact_counterpart_profile,
    normalize_counterpart_assessment_profile,
)


class CounterpartProfileTests(unittest.TestCase):
    def test_normalize_counterpart_assessment_profile_derives_extended_axes(self):
        profile = normalize_counterpart_assessment_profile(
            {
                "stance": "open",
                "scene": "care_bid",
                "respect_level": 0.74,
                "reciprocity": 0.68,
                "boundary_pressure": 0.12,
                "reliability_read": 0.79,
            }
        )

        self.assertEqual(profile["dominant_scene_signal"], "care")
        self.assertGreater(profile["scene_strengths"]["care"], 0.6)
        self.assertGreater(profile["safety_read"], 0.6)
        self.assertGreater(profile["repairability"], 0.6)
        self.assertGreater(profile["predictability"], 0.55)
        self.assertGreater(profile["closeness_read"], 0.6)
        self.assertLess(profile["dependency_risk"], 0.6)

    def test_compact_counterpart_profile_clamps_extended_axes(self):
        compacted = compact_counterpart_profile(
            {
                "openness_drive": 2,
                "guarded_drive": -1,
                "guard_margin": 2,
                "dominant_scene_signal": "care",
                "scene_strengths": {"care": 2, "friction": -1},
                "safety_read": 1.5,
                "repairability": -0.5,
                "predictability": 0.6251,
                "dependency_risk": 9,
                "closeness_read": "0.512",
            }
        )

        self.assertEqual(compacted["openness_drive"], 1.0)
        self.assertEqual(compacted["guarded_drive"], 0.0)
        self.assertEqual(compacted["guard_margin"], 1.0)
        self.assertEqual(compacted["scene_strengths"]["care"], 1.0)
        self.assertEqual(compacted["scene_strengths"]["friction"], 0.0)
        self.assertEqual(compacted["safety_read"], 1.0)
        self.assertEqual(compacted["repairability"], 0.0)
        self.assertEqual(compacted["predictability"], 0.625)
        self.assertEqual(compacted["dependency_risk"], 1.0)
        self.assertEqual(compacted["closeness_read"], 0.512)

    def test_reconsolidation_snapshot_preserves_extended_counterpart_profile_axes(self):
        snapshot = _compact_counterpart_snapshot(
            {
                "stance": "watchful",
                "scene": "repair_attempt",
                "respect_level": 0.63,
                "reciprocity": 0.58,
                "boundary_pressure": 0.24,
                "reliability_read": 0.71,
                "assessment_profile": {
                    "openness_drive": 0.44,
                    "guarded_drive": 0.52,
                    "guard_margin": 0.08,
                    "dominant_scene_signal": "repair",
                    "scene_strengths": {"repair": 0.66},
                    "safety_read": 0.61,
                    "repairability": 0.72,
                    "predictability": 0.67,
                    "dependency_risk": 0.33,
                    "closeness_read": 0.55,
                },
            }
        )

        profile = snapshot["assessment_profile"]
        self.assertEqual(profile["dominant_scene_signal"], "repair")
        self.assertEqual(profile["safety_read"], 0.61)
        self.assertEqual(profile["repairability"], 0.72)
        self.assertEqual(profile["predictability"], 0.67)
        self.assertEqual(profile["dependency_risk"], 0.33)
        self.assertEqual(profile["closeness_read"], 0.55)
