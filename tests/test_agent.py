"""Tests for Phase 3 agent tool-call parsing."""
from __future__ import annotations

import unittest

from agent import (
    build_summarize_system_message_content,
    build_system_message_content,
    format_tool_result_message,
    try_parse_tool_call,
)
from tools.schema import tool_result_ok


class TestToolCallParse(unittest.TestCase):
    def test_minimal_json(self) -> None:
        t = '{"tool":"ping","params":{}}'
        p = try_parse_tool_call(t)
        self.assertIsNotNone(p)
        assert p is not None
        self.assertEqual(p["tool"], "ping")
        self.assertEqual(p["params"], {})

    def test_with_distro(self) -> None:
        t = '{"tool":"volume_get","params":{"distro":"fedora"}}'
        p = try_parse_tool_call(t)
        self.assertIsNotNone(p)
        assert p is not None
        self.assertEqual(p["tool"], "volume_get")
        self.assertEqual(p["params"], {"distro": "fedora"})

    def test_fenced(self) -> None:
        t = '```json\n{"tool":"ping","params":{}}\n```'
        p = try_parse_tool_call(t)
        self.assertIsNotNone(p)
        assert p is not None
        self.assertEqual(p["tool"], "ping")

    def test_embedded_object_in_prose(self) -> None:
        t = 'Sure thing {"tool":"ping","params":{}}'
        p = try_parse_tool_call(t)
        self.assertIsNotNone(p)
        assert p is not None
        self.assertEqual(p["tool"], "ping")

    def test_plain_text_none(self) -> None:
        self.assertIsNone(try_parse_tool_call("Hello world"))

    def test_system_prompt_contains_manifest(self) -> None:
        s = build_system_message_content("You are Meera.")
        self.assertIn("Tool catalog JSON:", s)
        self.assertIn("ping", s)

    def test_summarize_prompt_has_no_catalog(self) -> None:
        s = build_summarize_system_message_content("You are Meera.")
        self.assertNotIn("Tool catalog JSON:", s)
        self.assertNotIn('"name":"ping"', s)
        self.assertIn("Tool result follow-up", s)


class TestToolFormat(unittest.TestCase):
    def test_feedback_prefix(self) -> None:
        r = tool_result_ok("ok", data={"x": 1})
        msg = format_tool_result_message("ping", r)
        self.assertTrue(msg.startswith("[Tool result]\n"))
        self.assertIn("ping", msg)
        self.assertIn('"ok": true', msg)


if __name__ == "__main__":
    unittest.main()
