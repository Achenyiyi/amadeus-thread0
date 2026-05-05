from __future__ import annotations

from amadeus_thread0.graph_parts.perception import attach_perception_context
from amadeus_thread0.graph_parts.turn_events import _normalize_event_override
from amadeus_thread0.runtime.event_identity import resolve_readback_current_event


def test_attach_perception_context_adds_runtime_surface_fields():
    event = attach_perception_context(
        {
            "kind": "user_utterance",
            "source": "text",
            "text": "我回来了。",
            "effective_text": "我回来了。",
            "tags": ["relationship"],
            "created_at": 1710000000,
        },
        thread_id="thread-k",
        turn_now_ts=1710000005,
    )

    perception = event["perception"]
    assert perception["thread_id"] == "thread-k"
    assert perception["turn_id"] == "thread-k:1710000005"
    assert perception["channel"] == "text"
    assert perception["modality"] == "text"
    assert perception["source_role"] == "counterpart"
    assert perception["trust_tier"] == "high"
    assert perception["interruptibility"] == "hard"
    assert perception["delivery_mode"] == "direct"
    assert perception["salience"] > 0.8


def test_browser_runtime_observation_keeps_body_perception_hints():
    event = attach_perception_context(
        {
            "kind": "browser_runtime_observation",
            "source": "browser",
            "text": "Browser profile is still active.",
            "digital_body_hints": {
                "browser_runtime_state": {
                    "profile_id": "profile-a",
                    "context_status": "active",
                }
            },
        },
        thread_id="thread-body",
        turn_now_ts=1710000200,
    )

    assert event["perception"]["modality"] == "browser"
    assert event["perception"]["source_role"] == "environment"
    assert event["perception"]["digital_body_hints"]["browser_runtime_state"]["profile_id"] == "profile-a"


def test_sandbox_run_observation_keeps_body_perception_hints():
    event = attach_perception_context(
        {
            "kind": "sandbox_run_observation",
            "source": "sandbox",
            "text": "The isolated run finished.",
            "digital_body_hints": {
                "sandbox_state": {
                    "runner_kind": "docker_isolated_runner",
                    "last_exit_code": 0,
                }
            },
        },
        thread_id="thread-body",
        turn_now_ts=1710000201,
    )

    assert event["perception"]["modality"] == "sandbox"
    assert event["perception"]["source_role"] == "environment"
    assert event["perception"]["digital_body_hints"]["sandbox_state"]["runner_kind"] == "docker_isolated_runner"


def test_skill_usage_observation_keeps_capability_perception_hints():
    event = attach_perception_context(
        {
            "kind": "skill_usage_observation",
            "source": "skill",
            "text": "A workspace triage skill completed.",
            "digital_body_hints": {
                "skill_effects": {
                    "skill_id": "workspace-regression-triage",
                    "status": "completed",
                }
            },
        },
        thread_id="thread-body",
        turn_now_ts=1710000202,
    )

    assert event["perception"]["modality"] == "skill"
    assert event["perception"]["source_role"] == "capability"
    assert event["perception"]["digital_body_hints"]["skill_effects"]["skill_id"] == "workspace-regression-triage"


def test_audio_observation_keeps_voice_channel_and_medium_trust():
    event = attach_perception_context(
        {"kind": "audio_observation", "source": "audio", "text": "Background voice activity detected."},
        thread_id="thread-body",
        turn_now_ts=1710000203,
    )

    assert event["perception"]["modality"] == "audio"
    assert event["perception"]["channel"] == "voice"
    assert event["perception"]["trust_tier"] == "medium"


def test_vision_observation_keeps_vision_channel_and_medium_trust():
    event = attach_perception_context(
        {"kind": "vision_observation", "source": "vision", "text": "A visible login prompt appeared."},
        thread_id="thread-body",
        turn_now_ts=1710000204,
    )

    assert event["perception"]["modality"] == "vision"
    assert event["perception"]["channel"] == "vision"
    assert event["perception"]["trust_tier"] == "medium"


def test_readback_current_event_exposes_perception_digital_body_hints():
    event = attach_perception_context(
        {
            "kind": "browser_runtime_observation",
            "source": "browser",
            "created_at": 1710000205,
            "perception": {
                "digital_body_hints": {
                    "browser_runtime_state": {
                        "profile_id": "profile-readback",
                        "context_status": "active",
                    }
                }
            },
        },
        thread_id="thread-body",
        turn_now_ts=1710000205,
    )

    readback = resolve_readback_current_event(
        {
            "current_event": event,
            "session_context": {"thread_id": "thread-body", "turn_id": "thread-body:1710000205"},
        },
        thread_id="thread-body",
        session_context={"thread_id": "thread-body", "turn_id": "thread-body:1710000205"},
    )

    perception = readback["perception"]
    assert perception["modality"] == "browser"
    assert perception["source_role"] == "environment"
    assert perception["digital_body_hints"]["browser_runtime_state"]["profile_id"] == "profile-readback"
    assert readback["digital_body_hints"]["browser_runtime_state"]["context_status"] == "active"


def test_readback_current_event_mirrors_top_level_digital_body_hints_into_perception():
    readback = resolve_readback_current_event(
        {
            "current_event": {
                "kind": "sandbox_run_observation",
                "source": "sandbox",
                "created_at": 1710000206,
                "digital_body_hints": {
                    "sandbox_state": {
                        "runner_kind": "docker_isolated_runner",
                        "last_exit_code": 0,
                    }
                },
                "perception": {
                    "thread_id": "thread-body",
                    "turn_id": "thread-body:1710000206",
                    "modality": "sandbox",
                    "source_role": "environment",
                },
            }
        },
        thread_id="thread-body",
        session_context={"thread_id": "thread-body", "turn_id": "thread-body:1710000206"},
    )

    assert readback["digital_body_hints"]["sandbox_state"]["runner_kind"] == "docker_isolated_runner"
    assert readback["perception"]["digital_body_hints"]["sandbox_state"]["last_exit_code"] == 0


def test_readback_current_event_prefers_richer_perception_hints_when_top_level_is_stale():
    readback = resolve_readback_current_event(
        {
            "current_event": {
                "kind": "browser_runtime_observation",
                "source": "browser",
                "created_at": 1710000208,
                "digital_body_hints": {
                    "browser_runtime_state": {
                        "context_status": "stale_top_level",
                    }
                },
                "perception": {
                    "thread_id": "thread-body",
                    "turn_id": "thread-body:1710000208",
                    "modality": "browser",
                    "source_role": "environment",
                    "digital_body_hints": {
                        "browser_runtime_state": {
                            "context_status": "active",
                            "profile_id": "profile-rich",
                        }
                    },
                },
            }
        },
        thread_id="thread-body",
        session_context={"thread_id": "thread-body", "turn_id": "thread-body:1710000208"},
    )

    hints = readback["perception"]["digital_body_hints"]["browser_runtime_state"]
    assert hints["context_status"] == "active"
    assert hints["profile_id"] == "profile-rich"
    assert readback["digital_body_hints"]["browser_runtime_state"]["context_status"] == "active"


def test_readback_current_event_does_not_mutate_source_event():
    event = {
        "kind": "browser_runtime_observation",
        "source": "browser",
        "created_at": 1710000207,
        "digital_body_hints": {
            "browser_runtime_state": {
                "profile_id": "profile-source",
            }
        },
        "perception": {
            "thread_id": "thread-body",
            "turn_id": "thread-body:1710000207",
            "modality": "browser",
            "source_role": "environment",
        },
    }

    readback = resolve_readback_current_event(
        {"current_event": event},
        thread_id="thread-body",
        session_context={"thread_id": "thread-body", "turn_id": "thread-body:1710000207"},
    )

    assert event["perception"].get("digital_body_hints") is None
    assert event.get("digital_body_hints", {}).get("browser_runtime_state", {}).get("profile_id") == "profile-source"
    assert readback["perception"]["digital_body_hints"]["browser_runtime_state"]["profile_id"] == "profile-source"


def test_tts_presence_timing_observation_keeps_runtime_voice_timing_hints():
    event = attach_perception_context(
        {
            "kind": "tts_presence_timing_observation",
            "source": "tts",
            "text": "TTS delivered the frozen final text.",
            "final_text_ref": "turn.final_text",
            "digital_body_hints": {
                "tts_presence_state": {
                    "last_status": "delivered",
                    "voice_profile_id": "default",
                }
            },
        },
        thread_id="thread-body",
        turn_now_ts=1710000210,
    )

    perception = event["perception"]
    assert perception["modality"] == "TTS_presence_timing"
    assert perception["channel"] == "voice"
    assert perception["source_role"] == "runtime"
    assert perception["trust_tier"] == "high_runtime_telemetry"
    assert perception["delivery_mode"] == "spoken"
    assert event["digital_body_hints"]["tts_presence_state"]["last_status"] == "delivered"


def test_readback_current_event_mirrors_tts_presence_timing_hints_into_perception():
    readback = resolve_readback_current_event(
        {
            "current_event": {
                "kind": "tts_presence_timing_observation",
                "source": "tts",
                "created_at": 1710000211,
                "digital_body_hints": {
                    "tts_presence_state": {
                        "last_status": "delivered",
                        "voice_profile_id": "default",
                    }
                },
                "perception": {
                    "thread_id": "thread-body",
                    "turn_id": "thread-body:1710000211",
                    "modality": "TTS_presence_timing",
                    "source_role": "runtime",
                },
            }
        },
        thread_id="thread-body",
        session_context={"thread_id": "thread-body", "turn_id": "thread-body:1710000211"},
    )

    assert readback["perception"]["modality"] == "TTS_presence_timing"
    assert readback["perception"]["source_role"] == "runtime"
    assert readback["perception"]["digital_body_hints"]["tts_presence_state"]["last_status"] == "delivered"


def test_normalize_event_override_preserves_idle_defaults_and_attaches_perception():
    payload = _normalize_event_override(
        {
            "kind": "time_idle",
            "source": "ambient",
            "idle_minutes": "7",
            "tags": ["quiet_presence", ""],
            "carryover_strength": "1.8",
        },
        counterpart_name="冈部伦太郎",
        thread_id="thread-life",
        turn_now_ts=1710000100,
    )

    assert payload["kind"] == "time_idle"
    assert payload["event_frame"] == "7 分钟的静默时间过去了。"
    assert payload["idle_minutes"] == 7
    assert payload["tags"] == ["quiet_presence"]
    assert payload["carryover_strength"] == 1.0
    assert payload["perception"]["thread_id"] == "thread-life"
    assert payload["perception"]["channel"] == "ambient"
    assert payload["perception"]["interruptibility"] == "soft"
    assert payload["perception"]["delivery_mode"] == "ambient"
