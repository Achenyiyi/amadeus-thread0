from amadeus_thread0.graph_parts.session_context import resolve_session_context


def test_resolve_session_context_prefers_configurable_identity_and_rebuilds_turn_id():
    context = resolve_session_context(
        state={
            "session_context": {
                "thread_id": "older-thread",
                "turn_id": "older-thread:77",
                "turn_started_at": 77,
            },
            "current_event": {"perception": {"thread_id": "stale-event-thread"}},
        },
        config={"configurable": {"thread_id": "thread-live", "user_id": "okabe", "checkpoint_id": "cp-9"}},
        turn_now_ts=123,
    )

    assert context["thread_id"] == "thread-live"
    assert context["turn_id"] == "thread-live:123"
    assert context["turn_started_at"] == 123
    assert context["user_id"] == "okabe"
    assert context["checkpoint_id"] == "cp-9"
