from __future__ import annotations

from datetime import datetime

from amadeus_thread0.graph_parts import build_implicit_idle_event_override


def test_idle_event_carries_respect_space_and_self_rhythm_context() -> None:
    event = build_implicit_idle_event_override(
        {
            "current_event": {
                "kind": "user_utterance",
                "tags": ["user_busy", "respect_space", "quiet_presence"],
            },
            "behavior_action": {
                "action_target": "hold_own_rhythm",
                "timing_window_min": 18,
                "relationship_weather": "settled",
            },
            "interaction_carryover": {
                "carryover_mode": "own_rhythm",
                "strength": 0.66,
                "relationship_weather": "settled",
            },
            "world_model_state": {
                "presence_residue": 0.34,
                "ambient_resonance": 0.12,
                "self_activity_momentum": 0.72,
            },
        },
        idle_minutes=36,
        created_at=int(datetime(2026, 10, 9, 14, 0, 0).timestamp()),
        extra_tags=["pulse"],
    )

    tags = set(event["tags"])
    assert {"time_idle", "ambient", "behavior_layer", "pulse"} <= tags
    assert {"user_busy", "respect_space", "quiet_presence", "from_own_rhythm", "own_task", "deep_focus"} <= tags
    assert event["relationship_weather"] == "settled"
    assert "给对方留空间" in event["event_frame"]
    assert "自己的节奏" in event["event_frame"]


def test_idle_event_marks_stale_recheck_and_late_night_when_window_is_old() -> None:
    event = build_implicit_idle_event_override(
        {
            "current_event": {
                "kind": "time_idle",
                "tags": ["ambient_echo"],
            },
            "behavior_action": {
                "action_target": "wait_and_recheck",
                "timing_window_min": 12,
            },
            "interaction_carryover": {
                "carryover_mode": "ambient_echo",
                "strength": 0.52,
            },
            "world_model_state": {
                "ambient_resonance": 0.44,
            },
        },
        idle_minutes=80,
        created_at=int(datetime(2026, 10, 10, 1, 30, 0).timestamp()),
    )

    tags = set(event["tags"])
    assert "ambient_echo" in tags
    assert "stale_window" in tags
    assert "late_night" in tags
    assert "自然过期" in event["event_frame"]


def test_idle_event_does_not_invent_busy_or_rhythm_tags_without_support() -> None:
    event = build_implicit_idle_event_override(
        {
            "world_model_state": {
                "presence_residue": 0.08,
                "ambient_resonance": 0.06,
                "self_activity_momentum": 0.10,
            }
        },
        idle_minutes=12,
        created_at=int(datetime(2026, 10, 9, 15, 0, 0).timestamp()),
    )

    tags = set(event["tags"])
    assert "user_busy" not in tags
    assert "respect_space" not in tags
    assert "from_own_rhythm" not in tags
    assert "stale_window" not in tags
