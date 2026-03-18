from amadeus_thread0.graph_parts.affect_dynamics import _behavior_policy_from_state


def test_behavior_policy_from_state_handles_lineage_without_unbound_locals():
    policy = _behavior_policy_from_state(
        response_style_hint="relationship",
        emotion_state={"label": "care"},
        bond_state={
            "trust": 0.64,
            "closeness": 0.62,
            "hurt": 0.02,
            "irritation": 0.0,
            "engagement_drive": 0.68,
        },
        allostasis_state={
            "safety_need": 0.14,
            "autonomy_need": 0.22,
            "cognitive_budget": 0.76,
        },
        counterpart_assessment={
            "respect_level": 0.72,
            "reciprocity": 0.70,
            "boundary_pressure": 0.18,
            "reliability_read": 0.66,
            "stance": "watchful",
        },
        semantic_narrative_profile={
            "bond_depth": 0.40,
            "commitment_carry": 0.48,
            "repair_residue": 0.36,
            "tension_residue": 0.18,
            "boundary_residue": 0.28,
            "selfhood_integrity": 0.42,
            "agency_drive": 0.46,
            "history_weight": 0.44,
            "lineage_gravity": 0.52,
            "lineage_snapshot": {
                "bond_style": 0.34,
                "commitment_style": 0.38,
                "repair_style": 0.32,
                "boundary_style": 0.36,
                "selfhood_style": 0.40,
                "agency_style": 0.44,
                "rhythm_style": 0.30,
            },
        },
        tsundere_intensity=0.56,
        science_mode=False,
        user_text="你记得我们周末还要一起把实验记录顺一遍吧？",
    )
    assert float(policy.get("boundary_assertiveness") or 0.0) > 0.0
    assert float(policy.get("self_directedness") or 0.0) > 0.0
    assert float(policy.get("equality_guard") or 0.0) > 0.0
