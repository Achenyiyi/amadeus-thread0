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


def test_retrieve_context_uses_nested_source_identity_for_legacy_digital_body_traces() -> None:
    with TemporaryDirectory() as td:
        store = MemoryStore(Path(td) / "memories.sqlite")
        try:
            store.add_revision_trace(
                namespace="digital_body_consequence",
                target_id="source_material_compared",
                before_summary="",
                after_summary="当前判断会顺着这条相连线索继续。",
                reason="digital_body_consequence:source_material_compared",
                operator="system",
                source="test",
                metadata={
                    "body_consequence_kind": "source_material_compared",
                    "embodied_context": {
                        "kind": "source_material_compared",
                        "artifact_carrier": "source_ref",
                        "artifact_source_ref_ids": [21, 17],
                        "preferred_source_ref_id": 21,
                        "preferred_anchor_reason": "primary_more_current",
                        "artifact_source_title": "Persistence v2",
                        "artifact_source_query": "langgraph persistence checkpointer thread recovery",
                    },
                },
            )
            store.add_revision_trace(
                namespace="digital_body_consequence",
                target_id="artifact_reacquired",
                before_summary="",
                after_summary="Persistence 那条旧链接只是被重新拿回来了一下。",
                reason="digital_body_consequence:artifact_reacquired",
                operator="system",
                source="test",
                metadata={
                    "body_consequence_kind": "artifact_reacquired",
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [9],
                    "artifact_source_title": "Old persistence note",
                },
            )
            retrieved = _retrieve_context("langgraph persistence checkpointer", store)
        finally:
            store.close()

    traces = retrieved.get("digital_body_consequence_traces")
    assert isinstance(traces, list)
    assert traces
    first_summary = str(traces[0].get("after_summary") or traces[0].get("content", {}).get("after_summary") or "")
    assert "相连线索继续" in first_summary
    working_items = retrieved.get("working_items")
    assert isinstance(working_items, list)
    assert any("Persistence v2" in str(item) for item in working_items)
    assert any("source_material_compared" in str(item) and "Persistence v2" in str(item) for item in working_items)


def test_retrieve_context_surfaces_browser_digital_body_trace_identity() -> None:
    with TemporaryDirectory() as td:
        store = MemoryStore(Path(td) / "memories.sqlite")
        try:
            store.add_revision_trace(
                namespace="digital_body_consequence",
                target_id="browser_interaction_completed",
                before_summary="",
                after_summary="Docs 页面上的确认按钮已经点过，后续可以沿同一 tab 继续。",
                reason="digital_body_consequence:browser_interaction_completed",
                operator="system",
                source="test",
                metadata={
                    "body_consequence_kind": "browser_interaction_completed",
                    "embodied_context": {
                        "kind": "browser_interaction_completed",
                        "artifact_carrier": "browser_page",
                        "active_artifact_kind": "page",
                        "active_artifact_ref": "page:page-1",
                        "active_artifact_label": "Docs",
                        "workspace_root": "E:/runtime/workspaces/browser-smoke",
                        "browser_run_id": "ap-browser-click-1",
                        "browser_profile_id": "thread-browser",
                        "browser_page_id": "page-1",
                        "browser_tab_id": "tab-1",
                        "browser_url": "https://example.com/docs",
                        "browser_title": "Docs",
                        "browser_last_action_kind": "click",
                        "browser_last_exit_status": "completed",
                    },
                },
            )
            retrieved = _retrieve_context("继续刚才那个 Docs 页面", store)
        finally:
            store.close()

    traces = retrieved.get("digital_body_consequence_traces")
    assert isinstance(traces, list)
    assert traces
    embodied = traces[0].get("embodied_context") if isinstance(traces[0].get("embodied_context"), dict) else {}
    assert embodied.get("kind") == "browser_interaction_completed"
    assert embodied.get("browser_profile_id") == "thread-browser"
    assert embodied.get("browser_tab_id") == "tab-1"
    working_items = retrieved.get("working_items")
    assert isinstance(working_items, list)
    assert any("browser_interaction_completed" in str(item) and "Docs" in str(item) for item in working_items)


def test_retrieve_context_surfaces_workspace_root_attach_trace_identity() -> None:
    with TemporaryDirectory() as td:
        store = MemoryStore(Path(td) / "memories.sqlite")
        try:
            store.add_revision_trace(
                namespace="digital_body_consequence",
                target_id="workspace_root_attached",
                before_summary="",
                after_summary="amadeus-thread0 已经被正式挂接成当前 repo root。",
                reason="digital_body_consequence:workspace_root_attached",
                operator="system",
                source="test",
                metadata={
                    "body_consequence_kind": "workspace_root_attached",
                    "embodied_context": {
                        "kind": "workspace_root_attached",
                        "access_mode": "tool_enabled",
                        "artifact_carrier": "filesystem",
                        "active_artifact_kind": "workspace",
                        "active_artifact_ref": "E:/repo/amadeus-thread0",
                        "active_artifact_label": "amadeus-thread0",
                        "workspace_root": "E:/repo/amadeus-thread0",
                        "workspace_root_kind": "attached_repo_root",
                        "primary_status": "completed",
                        "primary_tool_name": "attach_repo_root_access",
                        "selected_access_proposal": {
                            "target": "filesystem",
                            "mode": "operator_attach_repo_root",
                            "grants": ["filesystem", "workspace_read"],
                            "resolved_grants": ["filesystem", "workspace_read"],
                            "pending_grants": [],
                            "completion_ratio": 1.0,
                        },
                    },
                },
            )
            retrieved = _retrieve_context("继续刚才 attach 的 repo root", store)
        finally:
            store.close()

    traces = retrieved.get("digital_body_consequence_traces")
    assert isinstance(traces, list)
    assert traces
    embodied = traces[0].get("embodied_context") if isinstance(traces[0].get("embodied_context"), dict) else {}
    assert embodied.get("kind") == "workspace_root_attached"
    assert embodied.get("workspace_root") == "E:/repo/amadeus-thread0"
    assert embodied.get("workspace_root_kind") == "attached_repo_root"
    working_items = retrieved.get("working_items")
    assert isinstance(working_items, list)
    assert any("workspace_root_attached" in str(item) and "amadeus-thread0" in str(item) for item in working_items)
