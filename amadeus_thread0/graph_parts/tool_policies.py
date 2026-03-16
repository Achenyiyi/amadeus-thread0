from __future__ import annotations


MEMORY_WRITE_TOOLS = {
    "set_profile",
    "confirm_profile",
    "correct_profile",
    "undo_profile_correction",
    "delete_profile",
    "add_moment",
    "delete_moment",
    "rebuild_moment_embeddings",
    "add_reflection",
    "delete_reflection",
    "rebuild_reflection_embeddings",
    "set_relationship",
    "add_worldline_event",
    "add_relationship_event",
    "add_commitment",
    "resolve_commitment",
    "add_unresolved_tension",
    "resolve_unresolved_tension",
    "add_semantic_self_narrative",
    "add_skill",
    "merge_moments",
    "rollback_memory_change",
}


WORLDLINE_ABLATION_READ_TOOLS = {
    "get_memory_snapshot",
    "search_moments",
    "list_reflections",
    "search_reflections",
    "get_worldline_snapshot",
    "list_memory_ledger",
    "list_memory_quarantine",
}
