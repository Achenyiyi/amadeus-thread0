import json
import unittest

from langchain_core.messages import AIMessage, SystemMessage

from amadeus_thread0.graph import (
    _invoke_model_with_retries,
    _normalize_event_override,
    _sanitize_message,
)
from amadeus_thread0.perception_events import build_sense_event


class _DummyLLM:
    def invoke(self, msgs):
        for msg in msgs:
            dumped = msg.model_dump(mode="python")
            json.dumps(dumped, ensure_ascii=False).encode("utf-8")
        return SystemMessage(content="ok")


class Utf8SanitizationTests(unittest.TestCase):
    def test_sanitize_message_removes_surrogates_from_tool_payloads(self):
        bad = AIMessage(
            content="ok",
            tool_calls=[
                {
                    "name": "set_profile",
                    "args": {"value": "a\udc81b"},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
            additional_kwargs={"trace": "x\udc8by"},
        )

        cleaned = _sanitize_message(bad)
        dumped = cleaned.model_dump(mode="python")
        encoded = json.dumps(dumped, ensure_ascii=False).encode("utf-8")

        self.assertIn(b'"value": "ab"', encoded)
        self.assertNotIn(b"\\udc81", encoded)
        self.assertNotIn(b"\\udc8b", encoded)

    def test_invoke_model_sanitizes_before_provider_call(self):
        bad = AIMessage(
            content="ok",
            tool_calls=[
                {
                    "name": "set_profile",
                    "args": {"value": "a\udc81b"},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        )

        out = _invoke_model_with_retries(_DummyLLM(), [bad])
        self.assertEqual(getattr(out, "content", ""), "ok")

    def test_normalize_event_override_removes_surrogates(self):
        payload = _normalize_event_override(
            {
                "kind": "gesture_signal",
                "source": "vision",
                "text": "你\udc81好",
                "effective_text": "你\udc81好",
                "semantic_goal": "你\udc81好",
                "event_frame": "custom\udc81_frame",
                "tags": ["vision", "gesture\udc81"],
            },
            counterpart_name="冈部",
        )

        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.assertIn("你好", payload.get("text", ""))
        self.assertNotIn(b"\\udc81", encoded)

    def test_build_sense_event_cleans_note_override(self):
        _, payload = build_sense_event("gesture", note_override="你\udc81朝她挥了挥手")

        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.assertEqual(payload.get("text"), "你朝她挥了挥手")
        self.assertNotIn(b"\\udc81", encoded)


if __name__ == "__main__":
    unittest.main()
