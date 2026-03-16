from __future__ import annotations

import tempfile
import time
from datetime import datetime
from pathlib import Path

from amadeus_thread0.graph_parts.turn_events import (
    _append_recent_events,
    _normalize_event_override,
    _promote_due_commitment_event,
)
from amadeus_thread0.memory_store import MemoryStore


def test_normalize_event_override_builds_time_idle_defaults():
    payload = _normalize_event_override(
        {
            "kind": "time_idle",
            "idle_minutes": "7",
            "tags": ["quiet_presence", ""],
            "carryover_strength": "1.8",
        },
        counterpart_name="冈部伦太郎",
    )

    assert payload["kind"] == "time_idle"
    assert payload["counterpart_name"] == "冈部伦太郎"
    assert payload["event_frame"] == "7 分钟的静默时间过去了。"
    assert payload["idle_minutes"] == 7
    assert payload["tags"] == ["quiet_presence"]
    assert payload["carryover_strength"] == 1.0
    assert isinstance(payload["created_at"], int)


def test_append_recent_events_dedupes_and_keeps_latest_order():
    history = [
        {"text": "最早那句", "effective_text": "最早那句", "created_at": 1},
        {"text": "重复句", "effective_text": "重复句", "created_at": 2},
        {"text": "重复句", "effective_text": "重复句", "created_at": 2},
        {"text": "中间句", "effective_text": "中间句", "created_at": 3},
    ]
    current_event = {"text": "最新句", "effective_text": "最新句", "created_at": 4}

    events = _append_recent_events(history, current_event, limit=3)

    assert [item["text"] for item in events] == ["重复句", "中间句", "最新句"]
    assert len(events) == 3


def test_promote_due_commitment_event_uses_due_commitment_window():
    with tempfile.TemporaryDirectory() as tmp:
        store = MemoryStore(Path(tmp) / "memories.sqlite")
        try:
            due_at = datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")
            shared = store.add_commitment("一起看一集动画", due_at=due_at)
            store.add_commitment("把实验日志补完", due_at=due_at)

            promoted = _promote_due_commitment_event(
                {"kind": "time_idle", "idle_minutes": 18, "tags": ["quiet_presence"]},
                store,
                counterpart_name="冈部伦太郎",
            )

            assert promoted["kind"] == "scheduled_life_due"
            assert promoted["source"] == "commitment_scheduler"
            assert promoted["trigger_family"] == "shared_activity_window"
            assert promoted["commitment_id"] == int(shared["id"])
            assert "scheduled_due" in (promoted.get("tags") or [])
            assert "offer_window" in (promoted.get("tags") or [])
            assert "一起看一集动画" in str(promoted.get("text") or "")
        finally:
            store.close()
