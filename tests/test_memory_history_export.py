from __future__ import annotations

from amadeus_thread0.utils.memory_history_export import normalize_memory_record_export


def test_normalize_memory_record_export_normalizes_content_only_embodied_context():
    row = {
        "id": "9",
        "content": {
            "title": " paper ",
            "embodied_context": {
                "kind": "source_material_compared",
                "artifact_carrier": "source_ref",
                "artifact_source_ref_ids": ["9", "17", "9"],
                "preferred_source_ref_id": "9",
                "preferred_anchor_reason": "primary_more_current",
                "artifact_source_title": " paper ",
            },
        },
    }

    normalized = normalize_memory_record_export(row)

    assert normalized["title"] == "paper"
    assert normalized["embodied_context"]["artifact_source_ref_ids"] == [9, 17]
    assert normalized["embodied_context"]["preferred_source_ref_id"] == 9
    assert normalized["embodied_context"]["artifact_source_title"] == "paper"
    assert normalized["content"]["title"] == "paper"
    assert normalized["content"]["embodied_context"]["artifact_source_ref_ids"] == [9, 17]
    assert normalized["content"]["embodied_context"]["preferred_source_ref_id"] == 9
    assert normalized["content"]["embodied_context"]["artifact_source_title"] == "paper"
    assert "bodyfx=source_material_compared" in normalized.get("preview_line") or ""
    assert "source=paper" in normalized.get("preview_line") or ""
