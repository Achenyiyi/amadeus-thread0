from pathlib import Path
from tempfile import TemporaryDirectory

from amadeus_thread0.graph_parts.retrieval import _retrieve_context
from amadeus_thread0.memory_store import MemoryStore


def test_retrieve_context_surfaces_behavior_plan_traces_in_working_context() -> None:
    with TemporaryDirectory() as td:
        store = MemoryStore(Path(td) / "memories.sqlite")
        try:
            store.add_revision_trace(
                namespace="behavior_plan",
                target_id="deferred_checkin",
                before_summary="",
                after_summary="等忙完这阵，再轻轻回头看看冈部那边是不是还卡着。",
                reason="behavior_plan:deferred_checkin",
                operator="system",
                source="test",
                metadata={
                    "plan_kind": "deferred_checkin",
                    "trigger_family": "life_window",
                    "carryover_mode": "small_opening",
                    "carryover_strength": 0.58,
                    "presence_residue": 0.34,
                    "ambient_resonance": 0.22,
                    "self_activity_momentum": 0.48,
                    "scheduled_after_min": 18,
                },
            )
            retrieved = _retrieve_context("", store)
        finally:
            store.close()

    traces = retrieved.get("behavior_plan_traces")
    assert isinstance(traces, list)
    assert traces
    first_summary = str(traces[0].get("after_summary") or traces[0].get("content", {}).get("after_summary") or "")
    assert "等忙完这阵" in first_summary
    working_items = retrieved.get("working_items")
    assert isinstance(working_items, list)
    assert any("等忙完这阵" in str(item) for item in working_items)


def test_retrieve_context_surfaces_behavior_reactivation_traces_in_working_context() -> None:
    with TemporaryDirectory() as td:
        store = MemoryStore(Path(td) / "memories.sqlite")
        try:
            store.add_revision_trace(
                namespace="behavior_reactivation",
                target_id="deferred_checkin",
                before_summary="",
                after_summary="先前那点惦记又浮了上来，所以她顺着旧的连续线重新回头看向冈部。",
                reason="retrieved_continuity_reactivation",
                operator="system",
                source="test",
                metadata={
                    "carryover_mode": "small_opening",
                    "carryover_strength": 0.61,
                    "relationship_weather": "warm_residue",
                    "source_plan_kind": "deferred_checkin",
                    "source_trigger_family": "life_window",
                    "current_plan_kind": "small_opening",
                    "presence_residue": 0.36,
                    "ambient_resonance": 0.24,
                    "self_activity_momentum": 0.41,
                    "primary_motive": "stay_connected",
                },
            )
            retrieved = _retrieve_context("", store)
        finally:
            store.close()

    traces = retrieved.get("behavior_reactivation_traces")
    assert isinstance(traces, list)
    assert traces
    first_summary = str(traces[0].get("after_summary") or traces[0].get("content", {}).get("after_summary") or "")
    assert "顺着旧的连续线" in first_summary
    working_items = retrieved.get("working_items")
    assert isinstance(working_items, list)
    assert any("顺着旧的连续线" in str(item) for item in working_items)


def test_retrieve_context_surfaces_agenda_lifecycle_traces_in_working_context() -> None:
    with TemporaryDirectory() as td:
        store = MemoryStore(Path(td) / "memories.sqlite")
        try:
            store.add_revision_trace(
                namespace="agenda_lifecycle",
                target_id="held",
                before_summary="",
                after_summary="这次先把窗口按住，没有顺势往前推进。",
                reason="agenda_lifecycle:held",
                operator="system",
                source="test",
                metadata={
                    "lifecycle_kind": "held",
                    "source_event_kind": "time_idle",
                    "trigger_family": "life_window",
                    "relationship_weather": "warm_residue",
                    "carryover_mode": "quiet_recontact",
                    "carryover_strength": 0.37,
                    "hold_count": 2,
                    "recontact_cooldown": 0.41,
                    "presence_residue": 0.29,
                    "ambient_resonance": 0.21,
                    "self_activity_momentum": 0.46,
                    "own_rhythm_bias": 0.53,
                    "continuity_anchor": 0.58,
                    "own_rhythm_anchor": 0.61,
                    "recontact_anchor": 0.44,
                    "memory_anchor": 0.42,
                },
            )
            retrieved = _retrieve_context("", store)
        finally:
            store.close()

    traces = retrieved.get("agenda_lifecycle_traces")
    assert isinstance(traces, list)
    assert traces
    first_summary = str(traces[0].get("after_summary") or traces[0].get("content", {}).get("after_summary") or "")
    assert "先把窗口按住" in first_summary
    working_items = retrieved.get("working_items")
    assert isinstance(working_items, list)
    assert any("先把窗口按住" in str(item) for item in working_items)


def test_retrieve_context_surfaces_behavior_consequence_traces_in_working_context() -> None:
    with TemporaryDirectory() as td:
        store = MemoryStore(Path(td) / "memories.sqlite")
        try:
            store.add_revision_trace(
                namespace="behavior_consequence",
                target_id="let_window_expire",
                before_summary="",
                after_summary="她先前那次把靠近压轻了一点，关系里留下的是还在场但不过分逼近的余温。",
                reason="behavior_consequence:let_window_expire",
                operator="system",
                source="test",
                metadata={
                    "consequence_kind": "let_window_expire",
                    "relationship_effect": "warm_residue",
                    "self_effect": "self_rhythm_preserved",
                    "carryover_mode": "quiet_recontact",
                    "timing_window_min": 18,
                    "delayed": True,
                },
            )
            retrieved = _retrieve_context("", store)
        finally:
            store.close()

    traces = retrieved.get("behavior_consequence_traces")
    assert isinstance(traces, list)
    assert traces
    first_summary = str(traces[0].get("after_summary") or traces[0].get("content", {}).get("after_summary") or "")
    assert "余温" in first_summary
    working_items = retrieved.get("working_items")
    assert isinstance(working_items, list)
    assert any("余温" in str(item) for item in working_items)
