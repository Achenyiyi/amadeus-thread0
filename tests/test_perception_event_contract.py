from __future__ import annotations

from amadeus_thread0.graph_parts.perception import attach_perception_context
from amadeus_thread0.graph_parts.turn_events import _normalize_event_override


def test_attach_perception_context_adds_runtime_surface_fields():
    event = attach_perception_context(
        {
            "kind": "user_utterance",
            "source": "text",
            "text": "我回来了。",
            "effective_text": "我回来了。",
            "tags": ["relationship"],
            "created_at": 1710000000,
        },
        thread_id="thread-k",
        turn_now_ts=1710000005,
    )

    perception = event["perception"]
    assert perception["thread_id"] == "thread-k"
    assert perception["turn_id"] == "thread-k:1710000005"
    assert perception["channel"] == "text"
    assert perception["modality"] == "text"
    assert perception["source_role"] == "counterpart"
    assert perception["trust_tier"] == "high"
    assert perception["interruptibility"] == "hard"
    assert perception["delivery_mode"] == "direct"
    assert perception["salience"] > 0.8


def test_normalize_event_override_preserves_idle_defaults_and_attaches_perception():
    payload = _normalize_event_override(
        {
            "kind": "time_idle",
            "source": "ambient",
            "idle_minutes": "7",
            "tags": ["quiet_presence", ""],
            "carryover_strength": "1.8",
        },
        counterpart_name="冈部伦太郎",
        thread_id="thread-life",
        turn_now_ts=1710000100,
    )

    assert payload["kind"] == "time_idle"
    assert payload["event_frame"] == "7 分钟的静默时间过去了。"
    assert payload["idle_minutes"] == 7
    assert payload["tags"] == ["quiet_presence"]
    assert payload["carryover_strength"] == 1.0
    assert payload["perception"]["thread_id"] == "thread-life"
    assert payload["perception"]["channel"] == "ambient"
    assert payload["perception"]["interruptibility"] == "soft"
    assert payload["perception"]["delivery_mode"] == "ambient"
