from __future__ import annotations

from amadeus_thread0.graph_parts.tool_runtime import _build_evidence_from_tool_result


class _SourceRefStore:
    def __init__(self, refs):
        self._refs = list(refs)

    def list_source_refs(self, limit=120):
        return list(self._refs[:limit])


def test_build_evidence_from_tool_result_normalizes_legacy_content_only_source_refs():
    store = _SourceRefStore(
        [
            {
                "id": "17",
                "content": {
                    "url": " https://docs.langchain.com/oss/python/langgraph/persistence ",
                    "title": " Persistence ",
                    "query": " langgraph persistence checkpointer thread ",
                    "tool_name": " search_langchain_docs ",
                    "snippet": " Checkpointers enable persistence across thread runs. ",
                },
            }
        ]
    )

    result = _build_evidence_from_tool_result(
        tool_name="search_langchain_docs",
        result={"source_ref_ids": ["17"]},
        store=store,
    )

    assert result == [
        {
            "source_id": 17,
            "url": "https://docs.langchain.com/oss/python/langgraph/persistence",
            "title": "Persistence",
            "tool_name": "search_langchain_docs",
            "reliability_score": None,
            "snippet": "Checkpointers enable persistence across thread runs.",
            "query": "langgraph persistence checkpointer thread",
            "span_hint": "",
        }
    ]
