from __future__ import annotations

from unittest.mock import patch

from amadeus_thread0.utils.tools import compare_source_refs


class _SourceRefStore:
    def __init__(self, refs):
        self._refs = list(refs)

    def list_source_refs(self, limit=120):
        return list(self._refs[:limit])


def test_compare_source_refs_returns_compared_source_material_context():
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
        result = compare_source_refs.invoke({"source_ref_id": 21, "compare_source_ref_id": 17})

    assert result["relation"] in {"same_thread", "close_followup"}
    assert result["source_ref_ids"] == [21, 17]
    assert result["artifact_context"]["carrier"] == "source_ref"
    assert result["artifact_context"]["source_ref_ids"] == [21, 17]
    assert result["access_hints"]["artifact_source_ref_ids"] == [21, 17]
    assert result["resource_state"]["active_artifact_kind"] == "search_result"
    assert "Persistence v2" in result["summary"]


def test_compare_source_refs_can_reanchor_to_more_current_saved_material():
    store = _SourceRefStore(
        [
            {
                "id": 31,
                "url": "https://docs.example.com/spec",
                "title": "Spec Draft",
                "query": "amadeus source anchor draft",
                "tool_name": "search_web",
                "snippet": "Older draft with a short note.",
                "retrieved_at": 1712000000,
            },
            {
                "id": 32,
                "url": "https://docs.example.com/spec",
                "title": "Spec Final",
                "query": "amadeus source anchor final",
                "tool_name": "search_web",
                "snippet": "Final spec with the stable anchor details and the longer resolved summary.",
                "retrieved_at": 1712999999,
            },
        ]
    )
    with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
        result = compare_source_refs.invoke({"source_ref_id": 31, "compare_source_ref_id": 32})

    assert result["preferred_source_ref_id"] == 32
    assert result["preferred_source_title"] == "Spec Final"
    assert result["preferred_anchor_reason"] == "baseline_more_current"
    assert result["source_ref_ids"] == [32, 31]
    assert result["artifact_context"]["artifact_label"] == "Spec Final"
    assert result["artifact_context"]["source_ref_ids"] == [32, 31]
    assert result["artifact_context"]["preferred_source_ref_id"] == 32
    assert result["artifact_context"]["preferred_anchor_reason"] == "baseline_more_current"
    assert result["access_hints"]["artifact_source_ref_ids"] == [32, 31]
    assert result["access_hints"]["preferred_source_ref_id"] == 32
    assert result["access_hints"]["preferred_anchor_reason"] == "baseline_more_current"
    assert "Spec Final" in result["summary"]


def test_compare_source_refs_can_choose_best_candidate_from_saved_candidate_set():
    store = _SourceRefStore(
        [
            {
                "id": 31,
                "url": "https://docs.example.com/spec",
                "title": "Spec Draft",
                "query": "amadeus source anchor draft",
                "tool_name": "search_web",
                "snippet": "Older draft with a short note.",
                "retrieved_at": 1712000000,
            },
            {
                "id": 32,
                "url": "https://docs.example.com/spec",
                "title": "Spec Final",
                "query": "amadeus source anchor final",
                "tool_name": "search_web",
                "snippet": "Final spec with the stable anchor details and the longer resolved summary.",
                "retrieved_at": 1712999999,
            },
            {
                "id": 33,
                "url": "https://docs.example.com/side-note",
                "title": "Side Note",
                "query": "amadeus unrelated note",
                "tool_name": "search_web",
                "snippet": "A weaker side note that should not outrank the final spec.",
                "retrieved_at": 1712500000,
            },
        ]
    )
    with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
        result = compare_source_refs.invoke({"source_ref_id": 31, "source_ref_ids": [31, 33, 32]})

    assert result["compare_source_ref_id"] == 32
    assert result["preferred_source_ref_id"] == 32
    assert result["source_ref_ids"] == [32, 31, 33]
    assert result["artifact_context"]["source_ref_ids"] == [32, 31, 33]
    assert result["access_hints"]["artifact_source_ref_ids"] == [32, 31, 33]
    assert result["artifact_context"]["preferred_source_ref_id"] == 32
