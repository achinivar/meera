"""Tests for Phase 3 agent tool-call parsing."""
from __future__ import annotations

import unittest

from agent import (
    build_route_system_message_content,
    build_reply_system_message_content,
    build_summarize_system_message_content,
    build_tool_selection_system_message_content,
    format_tool_result_message,
    try_parse_route_decision,
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

    def test_route_prompt_mentions_route_json(self) -> None:
        s = build_route_system_message_content("You are Meera.")
        self.assertIn('{"route":"tool","type":"<type>"}', s)
        self.assertIn('{"route":"no_tool"}', s)
        self.assertIn("Available tools", s)

    def test_tool_selector_prompt_contains_examples(self) -> None:
        s = build_tool_selection_system_message_content("You are Meera.", "volume")
        self.assertIn('{"tool":"<tool_id>","params":{...}}', s)
        self.assertIn("## Examples", s)
        self.assertIn("refers to volume", s)
        self.assertIn("volume_set_percent", s)
        self.assertNotIn("brightness_set", s)

    def test_reply_prompt_simple_plain_text_mode(self) -> None:
        s = build_reply_system_message_content("You are Meera.")
        self.assertIn("Reply conversationally in plain text.", s)
        self.assertIn("Available tool categories:", s)
        self.assertIn("volume", s)
        self.assertIn("wifi", s)

    def test_summarize_prompt_has_no_catalog(self) -> None:
        s = build_summarize_system_message_content("You are Meera.")
        self.assertIn("Tool result follow-up", s)
        self.assertIn("Do not add tips, opinions, suggestions, or extra thoughts.", s)

    def test_route_parser_tool(self) -> None:
        p = try_parse_route_decision('{"route":"tool","type":"wifi"}')
        self.assertEqual(p, {"route": "tool", "type": "wifi"})

    def test_route_parser_no_tool(self) -> None:
        p = try_parse_route_decision('{"route":"no_tool"}')
        self.assertEqual(p, {"route": "no_tool"})

    def test_route_parser_rejects_invalid_type(self) -> None:
        self.assertIsNone(try_parse_route_decision('{"route":"tool","type":"unknown"}'))

    def test_route_parser_accepts_tool_name_type(self) -> None:
        p = try_parse_route_decision('{"route":"tool","type":"volume_set_percent"}')
        self.assertEqual(p, {"route": "tool", "type": "volume"})


class TestToolFormat(unittest.TestCase):
    def test_feedback_prefix(self) -> None:
        r = tool_result_ok("ok", data={"x": 1})
        msg = format_tool_result_message("ping", r)
        self.assertTrue(msg.startswith("[Tool result]\n"))
        self.assertIn("ping", msg)
        self.assertIn('"ok": true', msg)


if __name__ == "__main__":
    unittest.main()
