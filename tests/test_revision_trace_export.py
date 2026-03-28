from __future__ import annotations

from unittest.mock import patch

from amadeus_thread0.utils.revision_trace_export import normalize_revision_trace_export
from amadeus_thread0.utils.tools import get_worldline_snapshot, list_revision_traces


class FakeTraceStore:
    def __init__(self, traces):
        self._traces = list(traces)

    def list_revision_traces(self, limit=20):
        return list(self._traces[:limit])

    def list_worldline_events(self, limit=20):
        return []

    def list_identity_facts(self, limit=20):
        return []

    def list_shared_events(self, limit=20):
        return []

    def list_conflict_repairs(self, limit=20):
        return []

    def list_relationship_timeline(self, limit=20):
        return []

    def list_commitments(self, limit=20):
        return []

    def list_unresolved_tensions(self, limit=20):
        return []

    def list_semantic_self_narratives(self, limit=20):
        return []

    def list_canon_facts(self):
        return []

    def list_memory_quarantine(self, limit=20):
        return []


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
    assert normalized["embodied_context"]["artifact_source_title"] == "Persistence"
    assert normalized["embodied_context"]["artifact_source_tool_name"] == "search_web"


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
    assert payload[0]["embodied_context"]["artifact_source_title"] == "Persistence"
    assert payload[0]["embodied_context"]["artifact_source_tool_name"] == "search_web"
    assert payload[0]["embodied_context"]["requested_help"] is True


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
    assert payload["revision_traces"][0]["embodied_context"]["artifact_source_title"] == "Persistence"
    assert payload["revision_traces"][0]["embodied_context"]["artifact_source_tool_name"] == "search_web"
    assert payload["revision_traces"][0]["embodied_context"]["procedural_growth"] is True
