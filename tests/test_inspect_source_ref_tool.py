from __future__ import annotations

from unittest.mock import patch

from amadeus_thread0.utils.tools import inspect_source_ref


class _SourceRefStore:
    def __init__(self, refs):
        self._refs = list(refs)

    def list_source_refs(self, limit=120):
        return list(self._refs[:limit])


def test_inspect_source_ref_returns_attached_source_material_context():
    store = _SourceRefStore(
        [
            {
                "id": 17,
                "url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                "title": "Persistence",
                "query": "langgraph persistence checkpointer thread",
                "tool_name": "search_web",
                "snippet": "Checkpointers enable persistence across thread runs.",
                "retrieved_at": 1712345678,
            }
        ]
    )
    with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
        result = inspect_source_ref.invoke({"source_ref_id": 17})

    assert result["artifact_kind"] == "search_result"
    assert result["source_ref_ids"] == [17]
    assert result["artifact_context"]["carrier"] == "source_ref"
    assert result["artifact_context"]["artifact_label"] == "Persistence"
    assert result["artifact_context"]["source_tool_name"] == "search_web"
    assert result["access_hints"]["artifact_source_ref_ids"] == [17]
    assert result["resource_state"]["active_artifact_kind"] == "search_result"
    assert "Persistence" in result["summary"]


def test_inspect_source_ref_keeps_related_previous_source_ref_id_for_continuity_bias():
    store = _SourceRefStore(
        [
            {
                "id": 21,
                "url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                "title": "Persistence v2",
                "query": "langgraph persistence checkpointer thread recovery",
                "tool_name": "search_web",
                "snippet": "Recovery keeps the same persistence thread coherent.",
                "retrieved_at": 1712345688,
            },
            {
                "id": 17,
                "url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                "title": "Persistence",
                "query": "langgraph persistence checkpointer thread",
                "tool_name": "search_web",
                "snippet": "Checkpointers enable persistence across thread runs.",
                "retrieved_at": 1712345678,
            },
        ]
    )
    with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
        result = inspect_source_ref.invoke(
            {
                "source_ref_id": 21,
                "access_hints": {
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [17],
                    "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                    "artifact_source_query": "langgraph persistence checkpointer thread",
                    "artifact_source_title": "Persistence",
                },
            }
        )

    assert result["access_hints"]["artifact_source_ref_ids"] == [21, 17]


def test_inspect_source_ref_does_not_keep_unrelated_previous_source_ref_id():
    store = _SourceRefStore(
        [
            {
                "id": 21,
                "url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                "title": "Persistence v2",
                "query": "langgraph persistence checkpointer thread recovery",
                "tool_name": "search_web",
                "snippet": "Recovery keeps the same persistence thread coherent.",
                "retrieved_at": 1712345688,
            },
            {
                "id": 9,
                "url": "https://example.com/unrelated",
                "title": "Unrelated Notes",
                "query": "random unrelated page",
                "tool_name": "search_web",
                "snippet": "Nothing about langgraph here.",
                "retrieved_at": 1712345600,
            },
        ]
    )
    with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
        result = inspect_source_ref.invoke(
            {
                "source_ref_id": 21,
                "access_hints": {
                    "artifact_carrier": "source_ref",
                    "artifact_source_ref_ids": [9],
                    "artifact_source_url": "https://example.com/unrelated",
                    "artifact_source_query": "random unrelated page",
                    "artifact_source_title": "Unrelated Notes",
                },
            }
        )

    assert result["access_hints"]["artifact_source_ref_ids"] == [21]
