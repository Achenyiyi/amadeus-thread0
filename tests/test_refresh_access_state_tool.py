from __future__ import annotations

from amadeus_thread0.utils.tools import refresh_access_state


def test_refresh_access_state_recomputes_runtime_access(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()

    monkeypatch.setenv("AMADEUS_DATA_DIR", str(runtime_dir))
    monkeypatch.setenv("AMADEUS_MODEL_PROVIDER", "openai_compatible")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")
    monkeypatch.setenv("AMADEUS_NETWORK_ACCESS", "restricted")
    monkeypatch.setenv("AMADEUS_SANDBOX_MODE", "open")

    payload = refresh_access_state.invoke(
        {
            "access_hints": {
                "browser_session": "present",
                "account_state": "logged_in",
                "cookie_state": "present",
                "session_expires_in_s": 600,
                "api_key_state": "missing",
                "quota_state": "low",
                "missing_access": ["api_key"],
                "requestable_access": ["session_refresh"],
            }
        }
    )

    assert payload["api_key_state"] == "present"
    assert payload["filesystem_state"] == "writable"
    assert payload["network_access"] == "restricted"
    assert payload["session_continuity"] == "expiring"
    assert payload["session_recovery_mode"] == "refresh_session"
    assert "session_refresh" in payload["requestable_access"]
    assert payload["access_hints"]["api_key_state"] == "present"
    assert payload["access_hints"]["filesystem_state"] == "writable"
    assert "已重新检查当前" in payload["summary"]
