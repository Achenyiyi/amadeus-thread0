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


def test_resolve_session_context_preserves_digital_body_hints():
    context = resolve_session_context(
        state={
            "session_context": {
                "thread_id": "older-thread",
                "digital_body_hints": {
                    "browser_session": "missing",
                    "filesystem_state": "read_only",
                },
            },
        },
        config={"configurable": {"thread_id": "thread-live"}},
        turn_now_ts=123,
    )

    assert context["thread_id"] == "thread-live"
    assert context["digital_body_hints"]["browser_session"] == "missing"
    assert context["digital_body_hints"]["filesystem_state"] == "read_only"


def test_resolve_session_context_fills_missing_fields_from_event_hints_without_overwriting_state_truth():
    context = resolve_session_context(
        state={
            "session_context": {
                "thread_id": "thread-live",
                "digital_body_hints": {
                    "browser_session": "present",
                    "browser_runtime_state": {
                        "context_status": "active",
                    },
                },
            },
            "current_event": {
                "kind": "browser_runtime_observation",
                "digital_body_hints": {
                    "browser_session": "missing",
                    "workspace_root": "E:/runtime/workspaces/lab",
                    "browser_runtime_state": {
                        "context_status": "manual_takeover",
                        "profile_id": "profile-a",
                    },
                },
            },
        },
        config={"configurable": {"thread_id": "thread-live"}},
        turn_now_ts=124,
    )

    hints = context["digital_body_hints"]
    assert hints["browser_session"] == "present"
    assert hints["workspace_root"] == "E:/runtime/workspaces/lab"
    assert hints["browser_runtime_state"]["context_status"] == "active"
    assert hints["browser_runtime_state"]["profile_id"] == "profile-a"


def test_resolve_session_context_prefers_config_hints_over_event_hints():
    context = resolve_session_context(
        state={
            "current_event": {
                "kind": "sandbox_run_observation",
                "perception": {
                    "digital_body_hints": {
                        "sandbox_state": {
                            "runner_kind": "local_restricted_runner",
                            "last_exit_code": 1,
                        }
                    }
                },
            },
        },
        config={
            "configurable": {
                "thread_id": "thread-live",
                "digital_body_hints": {
                    "sandbox_state": {
                        "runner_kind": "docker_isolated_runner",
                    }
                },
            }
        },
        turn_now_ts=125,
    )

    hints = context["digital_body_hints"]
    assert hints["sandbox_state"]["runner_kind"] == "docker_isolated_runner"
    assert hints["sandbox_state"]["last_exit_code"] == 1


def test_resolve_session_context_uses_same_event_hint_order_as_digital_body_runtime():
    context = resolve_session_context(
        state={
            "current_event": {
                "kind": "browser_runtime_observation",
                "digital_body_hints": {
                    "browser_runtime_state": {
                        "context_status": "stale_top_level",
                    }
                },
                "perception": {
                    "digital_body_hints": {
                        "browser_runtime_state": {
                            "context_status": "active",
                            "profile_id": "profile-rich",
                        }
                    }
                },
            },
        },
        config={"configurable": {"thread_id": "thread-live"}},
        turn_now_ts=126,
    )

    runtime_state = context["digital_body_hints"]["browser_runtime_state"]
    assert runtime_state["context_status"] == "active"
    assert runtime_state["profile_id"] == "profile-rich"
