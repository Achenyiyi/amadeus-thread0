from __future__ import annotations

from unittest.mock import patch

import pytest

from amadeus_thread0.utils.tools import reacquire_artifact


class FakeSourceRefStore:
    def __init__(self, refs):
        self._refs = list(refs)

    def list_source_refs(self, limit=120):
        return list(self._refs[:limit])


def test_reacquire_artifact_reads_local_file(tmp_path):
    artifact = tmp_path / "plan.md"
    artifact.write_text("artifact continuity test\n" * 30, encoding="utf-8")

    payload = reacquire_artifact.invoke(
        {
            "mode": "reopen_file",
            "artifact_kind": "file",
            "artifact_ref": str(artifact),
            "preview_chars": 120,
        }
    )

    assert payload["artifact_continuity"] == "attached"
    assert payload["artifact_kind"] == "file"
    assert payload["artifact_ref"] == str(artifact)
    assert payload["artifact_label"] == "plan.md"
    assert payload["artifact_reacquisition_mode"] == "reopen_file"
    assert payload["artifact_exists"] is True
    assert "artifact continuity test" in payload["artifact_preview"]
    assert payload["artifact_preview_truncated"] is True


def test_reacquire_artifact_reads_workspace_directory(tmp_path):
    (tmp_path / "alpha.txt").write_text("a", encoding="utf-8")
    (tmp_path / "beta.txt").write_text("b", encoding="utf-8")

    payload = reacquire_artifact.invoke(
        {
            "mode": "reattach_workspace",
            "artifact_kind": "workspace",
            "artifact_ref": str(tmp_path),
        }
    )

    assert payload["artifact_continuity"] == "attached"
    assert payload["artifact_kind"] == "workspace"
    assert payload["artifact_ref"] == str(tmp_path)
    assert payload["artifact_exists"] is True
    assert "alpha.txt" in payload["artifact_preview"]
    assert "beta.txt" in payload["artifact_preview"]
    assert payload["artifact_preview_truncated"] is False


def test_reacquire_artifact_reuses_saved_source_ref_surface():
    store = FakeSourceRefStore(
        [
            {
                "id": 17,
                "tool_name": "search_langchain_docs",
                "title": "Persistence",
                "url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                "query": "langgraph persistence checkpointer thread",
                "snippet": "Persistence docs cover checkpointers and thread-scoped state.",
            }
        ]
    )

    with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
        payload = reacquire_artifact.invoke(
            {
                "mode": "rerun_search",
                "artifact_kind": "search_result",
                "artifact_ref": "source_ref:17",
                "artifact_label": "Persistence",
            }
        )

    assert payload["artifact_continuity"] == "attached"
    assert payload["artifact_kind"] == "search_result"
    assert payload["artifact_label"] == "Persistence"
    assert payload["artifact_reacquisition_mode"] == "rerun_search"
    assert payload["artifact_exists"] is True
    assert payload["source_ref_ids"] == [17]
    assert payload["source_url"] == "https://docs.langchain.com/oss/python/langgraph/persistence"
    assert payload["source_query"] == "langgraph persistence checkpointer thread"
    assert payload["tool_name"] == "search_langchain_docs"
    assert "checkpointers" in payload["artifact_preview"]


def test_reacquire_artifact_blocks_browser_surface_without_saved_source_ref():
    store = FakeSourceRefStore([])

    with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
        with pytest.raises(RuntimeError, match="UNSUPPORTED"):
            reacquire_artifact.invoke(
                {
                    "mode": "reopen_page",
                    "artifact_kind": "page",
                    "artifact_ref": "https://example.com/missing",
                    "artifact_label": "missing page",
                }
            )


def test_reacquire_artifact_reuses_legacy_content_only_saved_source_ref_surface():
    store = FakeSourceRefStore(
        [
            {
                "id": "17",
                "content": {
                    "tool_name": " search_langchain_docs ",
                    "title": " Persistence ",
                    "url": " https://docs.langchain.com/oss/python/langgraph/persistence ",
                    "query": " langgraph persistence checkpointer thread ",
                    "snippet": " Persistence docs cover checkpointers and thread-scoped state. ",
                },
            }
        ]
    )

    with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
        payload = reacquire_artifact.invoke(
            {
                "mode": "rerun_search",
                "artifact_kind": "search_result",
                "artifact_ref": "source_ref:17",
                "artifact_label": "Persistence",
            }
        )

    assert payload["source_ref_ids"] == [17]
    assert payload["source_url"] == "https://docs.langchain.com/oss/python/langgraph/persistence"
    assert payload["source_query"] == "langgraph persistence checkpointer thread"
    assert payload["tool_name"] == "search_langchain_docs"
    assert payload["artifact_label"] == "Persistence"
