from amadeus_thread0.utils.relational_history_export import (
    normalize_counterpart_assessment_export,
    normalize_proactive_continuity_export,
)


def test_normalize_counterpart_assessment_export_compacts_profile_and_nested_content():
    row = {
        "id": "41",
        "content": {
            "summary": " 她确认这次工作面已经真的接回来了。 ",
            "stance": " Open ",
            "scene": " Co_Work ",
            "created_at": "1710000109",
            "respect_level": "0.76",
            "reciprocity": "0.63",
            "boundary_pressure": "0.12",
            "reliability_read": "0.88",
            "assessment_profile": {
                "openness_drive": "0.74",
                "guarded_drive": "0.18",
                "guard_margin": "-0.56",
                "dominant_scene_signal": " Care ",
                "scene_strengths": {"care": "0.81", "repair": "0.22"},
                "safety_read": "0.84",
                "repairability": "0.77",
                "predictability": "0.73",
                "dependency_risk": "0.29",
                "closeness_read": "0.75",
            },
            "embodied_context": {
                "kind": "workspace_access_resolved",
                "workspace_root": "E:/runtime/workspaces/lab-notes",
                "filesystem_state": "writable",
            },
        },
    }

    normalized = normalize_counterpart_assessment_export(row)

    assert normalized["id"] == 41
    assert normalized["stance"] == "open"
    assert normalized["scene"] == "co_work"
    assert normalized["created_at"] == 1710000109
    assert normalized["respect_level"] == 0.76
    assert normalized["reliability_read"] == 0.88
    assert normalized["assessment_profile"]["dominant_scene_signal"] == "care"
    assert normalized["assessment_profile"]["scene_strengths"]["care"] == 0.81
    assert normalized["content"]["stance"] == "open"
    assert normalized["content"]["created_at"] == 1710000109
    assert normalized["content"]["assessment_profile"]["dominant_scene_signal"] == "care"
    assert "bodyfx=workspace_access_resolved" in (normalized.get("preview_line") or "")


def test_normalize_proactive_continuity_export_coerces_numeric_fields_and_nested_content():
    row = {
        "id": "42",
        "content": {
            "summary": " 她把这条稳定入口继续带进后续连续性里。 ",
            "kind": " Promoted ",
            "trace_family": " Access_State_Refresh_Followthrough ",
            "carryover_mode": " Continue_Work_Surface ",
            "relationship_weather": " Steady_Warmth ",
            "counterpart_scene_bias": " Busy_Not_Disrespectful ",
            "created_at": "1710000110",
            "hold_count": "2",
            "carryover_strength": "0.53",
            "semantic_continuity_depth": "0.68",
            "semantic_identity_gravity": "0.64",
            "own_rhythm_bias": "0.27",
            "long_term_axis_count": "4",
            "embodied_context": {
                "kind": "access_state_refreshed",
                "api_key_state": "present",
                "filesystem_state": "writable",
                "network_access": "enabled",
            },
        },
    }

    normalized = normalize_proactive_continuity_export(row)

    assert normalized["id"] == 42
    assert normalized["kind"] == "promoted"
    assert normalized["trace_family"] == "access_state_refresh_followthrough"
    assert normalized["carryover_mode"] == "continue_work_surface"
    assert normalized["relationship_weather"] == "steady_warmth"
    assert normalized["counterpart_scene_bias"] == "busy_not_disrespectful"
    assert normalized["created_at"] == 1710000110
    assert normalized["hold_count"] == 2
    assert normalized["carryover_strength"] == 0.53
    assert normalized["semantic_continuity_depth"] == 0.68
    assert normalized["long_term_axis_count"] == 4
    assert normalized["content"]["trace_family"] == "access_state_refresh_followthrough"
    assert normalized["content"]["carryover_strength"] == 0.53
    assert "carry=continue_work_surface:0.53" in (normalized.get("preview_line") or "")
    assert "bodyfx=access_state_refreshed" in (normalized.get("preview_line") or "")
