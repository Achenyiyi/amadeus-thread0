from __future__ import annotations

from unittest.mock import patch

from amadeus_thread0.utils.revision_trace_export import normalize_revision_trace_export
from amadeus_thread0.utils.tools import get_memory_snapshot, get_worldline_snapshot, list_revision_traces


class FakeTraceStore:
    def __init__(
        self,
        traces,
        *,
        worldline_events=None,
        identity_facts=None,
        shared_events=None,
        conflict_repairs=None,
        relationship_timeline=None,
        commitments=None,
        unresolved_tensions=None,
        semantic_self_narratives=None,
        counterpart_history=None,
        proactive_history=None,
        source_refs=None,
    ):
        self._traces = list(traces)
        self._worldline_events = list(worldline_events or [])
        self._identity_facts = list(identity_facts or [])
        self._shared_events = list(shared_events or [])
        self._conflict_repairs = list(conflict_repairs or [])
        self._relationship_timeline = list(relationship_timeline or [])
        self._commitments = list(commitments or [])
        self._unresolved_tensions = list(unresolved_tensions or [])
        self._semantic_self_narratives = list(semantic_self_narratives or [])
        self._counterpart_history = list(counterpart_history or [])
        self._proactive_history = list(proactive_history or [])
        self._source_refs = list(source_refs or [])

    def list_revision_traces(self, limit=20):
        return list(self._traces[:limit])

    def list_worldline_events(self, limit=20):
        return list(self._worldline_events[:limit])

    def list_identity_facts(self, limit=20):
        return list(self._identity_facts[:limit])

    def list_shared_events(self, limit=20):
        return list(self._shared_events[:limit])

    def list_conflict_repairs(self, limit=20):
        return list(self._conflict_repairs[:limit])

    def list_relationship_timeline(self, limit=20):
        return list(self._relationship_timeline[:limit])

    def list_commitments(self, limit=20):
        return list(self._commitments[:limit])

    def list_unresolved_tensions(self, limit=20):
        return list(self._unresolved_tensions[:limit])

    def list_semantic_self_narratives(self, limit=20):
        return list(self._semantic_self_narratives[:limit])

    def list_canon_facts(self):
        return []

    def list_memory_quarantine(self, limit=20):
        return []

    def snapshot(self):
        return {
            "profile": {"name": "okabe"},
            "relationship": {"stage": "warming"},
            "moments": [],
            "worldline_events": list(self._worldline_events),
            "identity_facts": list(self._identity_facts),
            "shared_events": list(self._shared_events),
            "conflict_repair": list(self._conflict_repairs),
            "relationship_timeline": list(self._relationship_timeline),
            "commitments": list(self._commitments),
            "unresolved_tensions": list(self._unresolved_tensions),
            "semantic_self_narratives": list(self._semantic_self_narratives),
            "counterpart_assessment_history": list(self._counterpart_history),
            "proactive_continuity_history": list(self._proactive_history),
            "revision_traces": list(self._traces),
            "source_refs": list(self._source_refs),
        }


def test_normalize_revision_trace_export_promotes_nested_embodied_context():
    row = {
        "id": 7,
        "source": "auto:passive_evolution_final",
        "behavior_consequence": {
            "kind": "defer_recontact",
            "embodied_context": {
                "kind": "environmental_friction",
                "missing_access": ["browser_session"],
                "artifact_carrier": "source_ref",
                "artifact_source_ref_ids": [17],
                "preferred_source_ref_id": 17,
                "preferred_anchor_reason": "primary_more_current",
                "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                "artifact_source_query": "langgraph persistence checkpointer thread",
                "artifact_source_title": "Persistence",
                "artifact_source_tool_name": "search_web",
                "environmental_friction": True,
            },
        },
    }

    normalized = normalize_revision_trace_export(row)

    assert normalized["id"] == 7
    assert normalized["embodied_context"]["kind"] == "environmental_friction"
    assert normalized["embodied_context"]["missing_access"] == ["browser_session"]
    assert normalized["embodied_context"]["artifact_carrier"] == "source_ref"
    assert normalized["embodied_context"]["artifact_source_ref_ids"] == [17]
    assert normalized["embodied_context"]["preferred_source_ref_id"] == 17
    assert normalized["embodied_context"]["preferred_anchor_reason"] == "primary_more_current"
    assert normalized["embodied_context"]["artifact_source_title"] == "Persistence"
    assert normalized["embodied_context"]["artifact_source_tool_name"] == "search_web"
    assert normalized["behavior_consequence"]["kind"] == "defer_recontact"
    assert normalized["behavior_consequence"]["embodied_context"]["artifact_source_ref_ids"] == [17]
    assert normalized["behavior_consequence"]["embodied_context"]["preferred_source_ref_id"] == 17
    assert normalized["behavior_consequence"]["embodied_context"]["preferred_anchor_reason"] == "primary_more_current"
    assert normalized["behavior_consequence"]["embodied_context"]["artifact_source_title"] == "Persistence"
    assert "bodyfx=environmental_friction" in normalized.get("preview_line") or ""
    assert "source=Persistence" in normalized.get("preview_line") or ""


def test_normalize_revision_trace_export_merges_legacy_top_level_source_ref_identity():
    row = {
        "id": 7,
        "source": "auto:passive_evolution_final",
        "metadata": {
            "body_consequence_kind": "source_material_compared",
            "artifact_carrier": "source_ref",
            "artifact_source_ref_ids": ["21", "21", "17", "bad"],
            "preferred_source_ref_id": "21",
            "preferred_anchor_reason": "primary_more_current",
            "artifact_source_query": "langgraph persistence checkpointer thread",
            "artifact_source_title": "Persistence v2",
            "embodied_context": {
                "kind": "source_material_compared",
                "artifact_carrier": "source_ref",
            },
        },
    }

    normalized = normalize_revision_trace_export(row)

    assert normalized["embodied_context"]["kind"] == "source_material_compared"
    assert normalized["embodied_context"]["artifact_carrier"] == "source_ref"
    assert normalized["embodied_context"]["artifact_source_ref_ids"] == [21, 17]
    assert normalized["embodied_context"]["preferred_source_ref_id"] == 21
    assert normalized["embodied_context"]["preferred_anchor_reason"] == "primary_more_current"
    assert normalized["embodied_context"]["artifact_source_query"] == "langgraph persistence checkpointer thread"
    assert normalized["embodied_context"]["artifact_source_title"] == "Persistence v2"
    assert "source=Persistence v2" in normalized.get("preview_line") or ""


def test_list_revision_traces_tool_normalizes_embodied_context():
    traces = [
        {
            "id": 8,
            "source": "auto:passive_evolution_final",
            "interaction_carryover": {
                "embodied_context": {
                    "kind": "access_request_pending",
                    "requested_access": ["workspace_write"],
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [17],
                    "preferred_source_ref_id": 17,
                    "preferred_anchor_reason": "primary_more_current",
                    "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "artifact_source_query": "langgraph persistence checkpointer thread",
                    "artifact_source_title": "Persistence",
                    "artifact_source_tool_name": "search_web",
                    "requested_help": True,
                    "primary_status": "awaiting_approval",
                }
            },
        }
    ]
    store = FakeTraceStore(traces)

    with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
        payload = list_revision_traces.invoke({"limit": 20})

    assert payload[0]["embodied_context"]["kind"] == "access_request_pending"
    assert payload[0]["embodied_context"]["requested_access"] == ["workspace_write"]
    assert payload[0]["embodied_context"]["artifact_carrier"] == "source_ref"
    assert payload[0]["embodied_context"]["artifact_source_ref_ids"] == [17]
    assert payload[0]["embodied_context"]["preferred_source_ref_id"] == 17
    assert payload[0]["embodied_context"]["preferred_anchor_reason"] == "primary_more_current"
    assert payload[0]["embodied_context"]["artifact_source_title"] == "Persistence"
    assert payload[0]["embodied_context"]["artifact_source_tool_name"] == "search_web"
    assert payload[0]["embodied_context"]["requested_help"] is True
    assert "bodyfx=access_request_pending" in payload[0].get("preview_line") or ""
    assert "source=Persistence" in payload[0].get("preview_line") or ""


def test_get_worldline_snapshot_tool_normalizes_revision_trace_embodied_context():
    traces = [
        {
            "id": 9,
            "source": "auto:passive_evolution_final",
            "metadata": {
                "digital_body_consequence": {
                    "kind": "embodied_growth",
                    "granted_toolsets": ["filesystem"],
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [17],
                    "preferred_source_ref_id": 17,
                    "preferred_anchor_reason": "primary_more_current",
                    "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "artifact_source_query": "langgraph persistence checkpointer thread",
                    "artifact_source_title": "Persistence",
                    "artifact_source_tool_name": "search_web",
                    "procedural_growth": True,
                }
            },
        }
    ]
    store = FakeTraceStore(traces)

    with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
        payload = get_worldline_snapshot.invoke({"limit": 20})

    assert payload["revision_traces"][0]["embodied_context"]["kind"] == "embodied_growth"
    assert payload["revision_traces"][0]["embodied_context"]["granted_toolsets"] == ["filesystem"]
    assert payload["revision_traces"][0]["embodied_context"]["artifact_carrier"] == "source_ref"
    assert payload["revision_traces"][0]["embodied_context"]["artifact_source_ref_ids"] == [17]
    assert payload["revision_traces"][0]["embodied_context"]["preferred_source_ref_id"] == 17
    assert payload["revision_traces"][0]["embodied_context"]["preferred_anchor_reason"] == "primary_more_current"
    assert payload["revision_traces"][0]["embodied_context"]["artifact_source_title"] == "Persistence"
    assert payload["revision_traces"][0]["embodied_context"]["artifact_source_tool_name"] == "search_web"
    assert payload["revision_traces"][0]["embodied_context"]["procedural_growth"] is True
    assert "bodyfx=embodied_growth" in payload["revision_traces"][0].get("preview_line") or ""
    assert "source=Persistence" in payload["revision_traces"][0].get("preview_line") or ""


def test_normalize_revision_trace_export_preserves_workspace_path_inspection_embodied_context():
    row = {
        "id": 10,
        "source": "auto:passive_evolution_final",
        "behavior_consequence": {
            "kind": "continue_work_surface",
            "embodied_context": {
                "kind": "workspace_path_inspected",
                "workspace_root": "E:/runtime/workspaces/lab-notes",
                "artifact_continuity": "attached",
                "active_artifact_kind": "file",
                "active_artifact_ref": "E:/runtime/workspaces/lab-notes/notes/today.md",
                "active_artifact_label": "today.md",
                "active_tools": ["inspect_workspace_path"],
                "primary_status": "completed",
            },
        },
    }

    normalized = normalize_revision_trace_export(row)

    assert normalized["embodied_context"]["kind"] == "workspace_path_inspected"
    assert normalized["embodied_context"]["workspace_root"] == "E:/runtime/workspaces/lab-notes"
    assert normalized["embodied_context"]["artifact_continuity"] == "attached"
    assert normalized["embodied_context"]["active_artifact_kind"] == "file"
    assert normalized["embodied_context"]["active_artifact_label"] == "today.md"
    assert normalized["embodied_context"]["active_tools"] == ["inspect_workspace_path"]
    assert "bodyfx=workspace_path_inspected" in normalized.get("preview_line") or ""
    assert "file:today.md:attached" in normalized.get("preview_line") or ""


def test_normalize_revision_trace_export_preserves_workspace_access_resolved_embodied_context():
    row = {
        "id": 12,
        "source": "auto:passive_evolution_final",
        "behavior_consequence": {
            "kind": "continue_work_surface",
            "embodied_context": {
                "kind": "workspace_access_resolved",
                "workspace_root": "E:/runtime/workspaces/lab-notes",
                "artifact_continuity": "attached",
                "active_artifact_kind": "workspace",
                "active_artifact_ref": "E:/runtime/workspaces/lab-notes",
                "active_artifact_label": "lab-notes",
                "filesystem_state": "writable",
                "session_continuity": "stable",
                "session_recovery_mode": "refresh_session",
                "access_acquire_proposals": [
                    {
                        "target": "filesystem",
                        "mode": "operator_create_workspace",
                        "summary": "先新建一个可写工作区。",
                        "grants": ["filesystem", "workspace_write"],
                        "requires_operator": True,
                    }
                ],
                "selected_access_proposal": {
                    "target": "filesystem",
                    "mode": "operator_create_workspace",
                    "summary": "先新建一个可写工作区。",
                    "grants": ["filesystem", "workspace_write"],
                    "requires_operator": True,
                },
                "primary_status": "completed",
            },
        },
    }

    normalized = normalize_revision_trace_export(row)

    assert normalized["embodied_context"]["kind"] == "workspace_access_resolved"
    assert normalized["embodied_context"]["workspace_root"] == "E:/runtime/workspaces/lab-notes"
    assert normalized["embodied_context"]["active_artifact_kind"] == "workspace"
    assert normalized["embodied_context"]["active_artifact_label"] == "lab-notes"
    assert normalized["embodied_context"]["filesystem_state"] == "writable"
    assert normalized["embodied_context"]["session_continuity"] == "stable"
    assert normalized["embodied_context"]["session_recovery_mode"] == "refresh_session"
    assert normalized["embodied_context"]["selected_access_proposal"]["mode"] == "operator_create_workspace"
    assert normalized["embodied_context"]["access_acquire_proposals"][0]["target"] == "filesystem"
    assert "bodyfx=workspace_access_resolved" in normalized.get("preview_line") or ""
    assert "proposal=operator_create_workspace@filesystem" in normalized.get("preview_line") or ""


def test_list_revision_traces_tool_preserves_workspace_path_inspection_embodied_context():
    traces = [
        {
            "id": 11,
            "source": "auto:passive_evolution_final",
            "content": {
                "embodied_context": {
                    "kind": "workspace_path_inspected",
                    "workspace_root": "E:/runtime/workspaces/lab-notes",
                    "artifact_continuity": "attached",
                    "active_artifact_kind": "file",
                    "active_artifact_ref": "E:/runtime/workspaces/lab-notes/notes/today.md",
                    "active_artifact_label": "today.md",
                    "active_tools": ["inspect_workspace_path"],
                    "primary_status": "completed",
                }
            },
        }
    ]
    store = FakeTraceStore(traces)

    with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
        payload = list_revision_traces.invoke({"limit": 20})

    assert payload[0]["embodied_context"]["kind"] == "workspace_path_inspected"
    assert payload[0]["embodied_context"]["workspace_root"] == "E:/runtime/workspaces/lab-notes"
    assert payload[0]["embodied_context"]["artifact_continuity"] == "attached"
    assert payload[0]["embodied_context"]["active_artifact_kind"] == "file"
    assert payload[0]["embodied_context"]["active_artifact_label"] == "today.md"
    assert payload[0]["embodied_context"]["active_tools"] == ["inspect_workspace_path"]
    assert payload[0]["content"]["embodied_context"]["workspace_root"] == "E:/runtime/workspaces/lab-notes"
    assert payload[0]["content"]["embodied_context"]["active_artifact_kind"] == "file"
    assert payload[0]["content"]["embodied_context"]["active_artifact_label"] == "today.md"
    assert "bodyfx=workspace_path_inspected" in payload[0].get("preview_line") or ""
    assert "file:today.md:attached" in payload[0].get("preview_line") or ""


def test_get_worldline_snapshot_tool_preserves_access_state_refresh_embodied_context():
    traces = [
        {
            "id": 13,
            "source": "auto:passive_evolution_final",
            "content": {
                "embodied_context": {
                    "kind": "access_state_refreshed",
                    "api_key_state": "present",
                    "filesystem_state": "writable",
                    "network_access": "enabled",
                    "session_continuity": "stable",
                    "session_recovery_mode": "refresh_session",
                    "access_acquire_proposals": [
                        {
                            "target": "filesystem",
                            "mode": "operator_create_workspace",
                            "summary": "需要时可以补一个新工作区。",
                            "grants": ["filesystem", "workspace_write"],
                            "requires_operator": True,
                        }
                    ],
                    "selected_access_proposal": {
                        "target": "filesystem",
                        "mode": "operator_create_workspace",
                        "summary": "需要时可以补一个新工作区。",
                        "grants": ["filesystem", "workspace_write"],
                        "requires_operator": True,
                    },
                    "primary_status": "completed",
                }
            },
        }
    ]
    store = FakeTraceStore(traces)

    with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
        payload = get_worldline_snapshot.invoke({"limit": 20})

    assert payload["revision_traces"][0]["embodied_context"]["kind"] == "access_state_refreshed"
    assert payload["revision_traces"][0]["embodied_context"]["api_key_state"] == "present"
    assert payload["revision_traces"][0]["embodied_context"]["filesystem_state"] == "writable"
    assert payload["revision_traces"][0]["embodied_context"]["network_access"] == "enabled"
    assert payload["revision_traces"][0]["embodied_context"]["session_continuity"] == "stable"
    assert payload["revision_traces"][0]["embodied_context"]["session_recovery_mode"] == "refresh_session"
    assert payload["revision_traces"][0]["embodied_context"]["selected_access_proposal"]["mode"] == "operator_create_workspace"
    assert payload["revision_traces"][0]["embodied_context"]["access_acquire_proposals"][0]["target"] == "filesystem"
    assert "bodyfx=access_state_refreshed" in payload["revision_traces"][0].get("preview_line") or ""
    assert "proposal=operator_create_workspace@filesystem" in payload["revision_traces"][0].get("preview_line") or ""


def test_get_memory_snapshot_tool_normalizes_revision_trace_embodied_context_when_include_core():
    traces = [
        {
            "id": 14,
            "source": "auto:passive_evolution_final",
            "behavior_consequence": {
                "embodied_context": {
                    "kind": "access_state_refreshed",
                    "api_key_state": "present",
                    "filesystem_state": "writable",
                    "network_access": "enabled",
                    "session_continuity": "stable",
                    "session_recovery_mode": "refresh_session",
                    "access_acquire_proposals": [
                        {
                            "target": "filesystem",
                            "mode": "operator_create_workspace",
                            "summary": "需要时可以补一个新工作区。",
                            "grants": ["filesystem", "workspace_write"],
                            "requires_operator": True,
                        }
                    ],
                    "selected_access_proposal": {
                        "target": "filesystem",
                        "mode": "operator_create_workspace",
                        "summary": "需要时可以补一个新工作区。",
                        "grants": ["filesystem", "workspace_write"],
                        "requires_operator": True,
                    },
                    "primary_status": "completed",
                }
            },
        }
    ]
    store = FakeTraceStore(traces)

    with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
        payload = get_memory_snapshot.invoke({"include_core": True})

    assert payload["revision_traces"][0]["embodied_context"]["kind"] == "access_state_refreshed"
    assert payload["revision_traces"][0]["embodied_context"]["api_key_state"] == "present"
    assert payload["revision_traces"][0]["embodied_context"]["filesystem_state"] == "writable"
    assert payload["revision_traces"][0]["embodied_context"]["network_access"] == "enabled"
    assert payload["revision_traces"][0]["embodied_context"]["session_continuity"] == "stable"
    assert payload["revision_traces"][0]["embodied_context"]["session_recovery_mode"] == "refresh_session"
    assert payload["revision_traces"][0]["embodied_context"]["selected_access_proposal"]["mode"] == "operator_create_workspace"
    assert "bodyfx=access_state_refreshed" in payload["revision_traces"][0].get("preview_line") or ""
    assert "proposal=operator_create_workspace@filesystem" in payload["revision_traces"][0].get("preview_line") or ""


def test_get_memory_snapshot_tool_normalizes_history_embodied_context_when_include_core():
    store = FakeTraceStore(
        [],
        counterpart_history=[
            {
                "id": 21,
                "content": {
                    "summary": "她确认这次工作面已经真的接回来了。",
                    "stance": "open",
                    "scene": "co_work",
                    "respect_level": "0.76",
                    "assessment_profile": {
                        "dominant_scene_signal": " Care ",
                        "openness_drive": "0.74",
                        "scene_strengths": {"care": "0.81"},
                    },
                    "embodied_context": {
                        "kind": "workspace_access_resolved",
                        "workspace_root": "E:/runtime/workspaces/lab-notes",
                        "filesystem_state": "writable",
                        "session_continuity": "stable",
                    },
                },
            }
        ],
        proactive_history=[
            {
                "id": 22,
                "content": {
                    "summary": "她把这条稳定入口继续带进后续连续性里。",
                    "kind": "promoted",
                    "trace_family": "access_state_refresh_followthrough",
                    "carryover_mode": "continue_work_surface",
                    "carryover_strength": "0.53",
                    "embodied_context": {
                        "kind": "access_state_refreshed",
                        "api_key_state": "present",
                        "filesystem_state": "writable",
                        "network_access": "enabled",
                    },
                },
            }
        ],
    )

    with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
        payload = get_memory_snapshot.invoke({"include_core": True})

    assert payload["counterpart_assessment_history"][0]["scene"] == "co_work"
    assert payload["counterpart_assessment_history"][0]["respect_level"] == 0.76
    assert payload["counterpart_assessment_history"][0]["assessment_profile"]["dominant_scene_signal"] == "care"
    assert payload["counterpart_assessment_history"][0]["embodied_context"]["kind"] == "workspace_access_resolved"
    assert payload["counterpart_assessment_history"][0]["embodied_context"]["workspace_root"] == "E:/runtime/workspaces/lab-notes"
    assert payload["proactive_continuity_history"][0]["trace_family"] == "access_state_refresh_followthrough"
    assert payload["proactive_continuity_history"][0]["carryover_strength"] == 0.53
    assert payload["proactive_continuity_history"][0]["embodied_context"]["kind"] == "access_state_refreshed"
    assert payload["proactive_continuity_history"][0]["embodied_context"]["api_key_state"] == "present"


def test_get_worldline_snapshot_tool_normalizes_content_only_memory_rows():
    store = FakeTraceStore(
        [],
        worldline_events=[
            {
                "id": 31,
                "content": {
                    "summary": "她把这次入口接通记成了一次真实发生过的共事。",
                    "category": "shared_event",
                },
            }
        ],
        commitments=[
            {
                "id": 32,
                "content": {
                    "text": "晚点继续看 lab-notes。",
                    "status": "open",
                },
            }
        ],
        semantic_self_narratives=[
            {
                "id": 33,
                "content": {
                    "text": "她会把真实接通的工作面沉淀回长期连续性。",
                    "category": "agency_style",
                },
            }
        ],
    )

    with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
        payload = get_worldline_snapshot.invoke({"limit": 20})

    assert payload["worldline_events"][0]["summary"] == "她把这次入口接通记成了一次真实发生过的共事。"
    assert payload["worldline_events"][0]["category"] == "shared_event"
    assert payload["commitments"][0]["text"] == "晚点继续看 lab-notes。"
    assert payload["commitments"][0]["status"] == "open"
    assert payload["semantic_self_narratives"][0]["text"] == "她会把真实接通的工作面沉淀回长期连续性。"
    assert payload["semantic_self_narratives"][0]["category"] == "agency_style"


def test_get_memory_snapshot_tool_normalizes_content_only_memory_rows_when_include_core():
    store = FakeTraceStore(
        [],
        worldline_events=[
            {
                "id": 34,
                "content": {
                    "summary": "她把这次入口接通记成了一次真实发生过的共事。",
                    "category": "shared_event",
                },
            }
        ],
        relationship_timeline=[
            {
                "id": 35,
                "content": {
                    "summary": "关系因为真实共事而往前推了一点。",
                    "affinity_delta": 0.08,
                    "trust_delta": 0.11,
                },
            }
        ],
        commitments=[
            {
                "id": 36,
                "content": {
                    "text": "晚点继续看 lab-notes。",
                    "status": "open",
                },
            }
        ],
    )

    with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
        payload = get_memory_snapshot.invoke({"include_core": True})

    assert payload["worldline_events"][0]["summary"] == "她把这次入口接通记成了一次真实发生过的共事。"
    assert payload["relationship_timeline"][0]["summary"] == "关系因为真实共事而往前推了一点。"
    assert payload["relationship_timeline"][0]["affinity_delta"] == 0.08
    assert payload["relationship_timeline"][0]["trust_delta"] == 0.11
    assert payload["commitments"][0]["text"] == "晚点继续看 lab-notes。"
