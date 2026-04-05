from __future__ import annotations

from unittest.mock import patch

from amadeus_thread0.utils.tools import search_web


class _SourceRefStore:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def add_source_ref(self, **kwargs):
        self.records.append(dict(kwargs))
        return {"id": len(self.records), **kwargs}


def test_search_web_normalizes_tavily_results_and_persists_source_refs():
    store = _SourceRefStore()

    class _FakeTavilySearch:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def _run(self, **kwargs):
            self.last_run = dict(kwargs)
            return {
                "answer": "LangGraph interrupts allow approval-gated pause and resume.",
                "results": [
                    {
                        "title": "LangGraph interrupts",
                        "url": "https://docs.langchain.com/oss/python/langgraph/interrupts",
                        "content": "Interrupts let you pause graph execution for human approval.",
                        "score": 0.93,
                        "published_date": "2026-04-05",
                    },
                    {
                        "title": "LangGraph interrupts duplicate",
                        "url": "https://docs.langchain.com/oss/python/langgraph/interrupts",
                        "content": "Lower score duplicate should be ignored.",
                        "score": 0.41,
                    },
                    {
                        "title": "LangGraph persistence",
                        "url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                        "content": "Persistence keeps thread state across runs.",
                        "score": 0.84,
                    },
                    {
                        "title": "missing url",
                        "content": "This row should be skipped.",
                        "score": 0.99,
                    },
                ],
            }

    with patch("amadeus_thread0.utils.tools.TavilySearch", _FakeTavilySearch):
        with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
            result = search_web.invoke(
                {
                    "query": "langgraph interrupts human approval",
                    "max_results": 3,
                    "topic": "general",
                    "search_depth": "advanced",
                    "time_range": "month",
                    "include_domains": ["docs.langchain.com", "docs.langchain.com"],
                }
            )

    assert result["query"] == "langgraph interrupts human approval"
    assert result["topic"] == "general"
    assert result["search_depth"] == "advanced"
    assert result["time_range"] == "month"
    assert result["include_domains"] == ["docs.langchain.com"]
    assert result["source_ref_ids"] == [1, 2]
    assert result["answer"] == "LangGraph interrupts allow approval-gated pause and resume."
    assert [item["url"] for item in result["items"]] == [
        "https://docs.langchain.com/oss/python/langgraph/interrupts",
        "https://docs.langchain.com/oss/python/langgraph/persistence",
    ]
    assert result["items"][0]["score"] == 0.93
    assert len(store.records) == 2
    assert store.records[0]["tool_name"] == "search_web"
    assert store.records[0]["query"] == "langgraph interrupts human approval"
    assert store.records[0]["published_at"] == "2026-04-05"
