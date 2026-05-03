"""Unit tests for the Phase 2 tool layer (mocked where needed)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.gsettings import _build_titlebar_layout
from tools.registry import TOOLS, get_tool, tools_prompt_catalog_json
from tools.scheduler import (
    _build_vevent_ics_document,
    _ics_dtstart_compact_from_start_arg,
    _ics_text_escape,
)
from tools.runner import run_tool
from tools.schema import ToolResult


class TestRegistry(unittest.TestCase):
    def test_unique_tool_names(self) -> None:
        names = [t.name for t in TOOLS]
        self.assertEqual(len(names), len(set(names)))

    def test_get_tool(self) -> None:
        self.assertIsNotNone(get_tool("ping"))
        self.assertIsNone(get_tool("nonexistent_tool_xyz"))

    def test_tools_prompt_catalog_json(self) -> None:
        raw = tools_prompt_catalog_json()
        self.assertNotIn("handler", raw)
        self.assertNotIn("schema_version", raw)
        self.assertNotIn("read_only", raw)
        self.assertNotIn("requires_elevation", raw)
        payload = json.loads(raw)
        self.assertGreater(len(payload["tools"]), 3)
        for spec in payload["tools"]:
            for p in spec["parameters"]:
                self.assertNotEqual(p.get("name"), "distro")
                self.assertNotIn("default", p)

    def test_every_tool_has_exemplars(self) -> None:
        # Phase 4 retrieval needs at least a few paraphrased utterances per tool
        # so the index can map natural-language requests onto the right tool.
        # Tighten this lower bound only as we systematically add more.
        MIN_EXEMPLARS = 3
        missing: list[str] = []
        for spec in TOOLS:
            if not isinstance(spec.exemplars, list):
                missing.append(f"{spec.name}: exemplars not a list")
                continue
            if len(spec.exemplars) < MIN_EXEMPLARS:
                missing.append(f"{spec.name}: only {len(spec.exemplars)} exemplars")
                continue
            for ex in spec.exemplars:
                if not isinstance(ex, str) or not ex.strip():
                    missing.append(f"{spec.name}: empty/non-string exemplar")
                    break
        self.assertEqual(missing, [], f"tools missing exemplars: {missing}")


class TestRunner(unittest.TestCase):
    def test_unknown_tool(self) -> None:
        r = run_tool("not_a_real_tool", {})
        self.assertFalse(r.ok)
        self.assertEqual(r.error_code, "UNKNOWN_TOOL")

    def test_distro_inject_ping(self) -> None:
        with patch("tools.runner.detect_distro", return_value="ubuntu"):
            r = run_tool("ping", {})
        self.assertTrue(r.ok)
        self.assertEqual(r.data, {"distro": "ubuntu"})

    def test_model_distro_ignored_host_wins(self) -> None:
        with patch("tools.runner.detect_distro", return_value="fedora"):
            r = run_tool("ping", {"distro": "ubuntu"})
        self.assertTrue(r.ok)
        self.assertEqual(r.data, {"distro": "fedora"})

    def test_unexpected_param(self) -> None:
        with patch("tools.runner.detect_distro", return_value="ubuntu"):
            r = run_tool("ping", {"distro": "ubuntu", "extra": 1})
        self.assertFalse(r.ok)
        self.assertEqual(r.error_code, "VALIDATION_ERROR")

    def test_file_list_dir_resolves_defaults(self) -> None:
        with patch("tools.runner.detect_distro", return_value="ubuntu"):
            r = run_tool("file_list_dir", {"distro": "ubuntu"})
        # May fail on permissions but should not be validation error
        self.assertNotEqual(r.error_code, "VALIDATION_ERROR")

    def test_optional_json_null_uses_defaults(self) -> None:
        """JSON null for optional args must not become the string 'None' for path."""
        with patch("tools.runner.detect_distro", return_value="ubuntu"):
            r = run_tool(
                "file_list_dir",
                {"path": None, "max_entries": 500},
            )
        self.assertNotEqual(r.error_code, "VALIDATION_ERROR")
        if r.ok:
            assert r.data is not None
            home = str(Path.home().resolve())
            self.assertTrue(str(r.data.get("path", "")).startswith(home))


class TestGnomeCalendarIcs(unittest.TestCase):
    def test_ics_escape_commas_and_newlines(self) -> None:
        self.assertEqual(_ics_text_escape("a, b"), "a\\, b")
        self.assertIn("\\n", _ics_text_escape("line1\nline2"))

    def test_vevent_document_dtstart_duration(self) -> None:
        doc = _build_vevent_ics_document(
            "Meeting", "20240501T090000", "America/Los_Angeles", 60
        )
        self.assertIn("BEGIN:VCALENDAR\r\n", doc)
        self.assertIn("SUMMARY:Meeting\r\n", doc)
        self.assertIn(
            "DTSTART;TZID=America/Los_Angeles:20240501T090000\r\n", doc
        )
        self.assertIn("DURATION:PT1H\r\n", doc)
        self.assertIn("END:VCALENDAR", doc)

    def test_duration_minutes_not_whole_hours(self) -> None:
        doc = _build_vevent_ics_document(
            "Quick", "20240501T090000", "America/Los_Angeles", 45
        )
        self.assertIn("DURATION:PT45M", doc)

    def test_dtstart_copies_model_digits_compact(self) -> None:
        v = _ics_dtstart_compact_from_start_arg("2026-05-02T09:00:00Z")
        self.assertEqual(v, "20260502T090000")


class TestGnomeTitlebarLayout(unittest.TestCase):
    """Parsing for gnome_titlebar_button_layout_set (no gsettings I/O)."""

    def test_default_when_both_none(self) -> None:
        layout = _build_titlebar_layout(None, None)
        self.assertEqual(layout, "appmenu:minimize,maximize,close")

    def test_only_right(self) -> None:
        layout = _build_titlebar_layout(None, "close")
        self.assertEqual(layout, ":close")
        layout2 = _build_titlebar_layout(None, "close,minimize,maximize")
        self.assertEqual(layout2, ":close,minimize,maximize")

    def test_only_left(self) -> None:
        layout = _build_titlebar_layout("appmenu", None)
        self.assertEqual(layout, "appmenu:")

    def test_custom_order(self) -> None:
        layout = _build_titlebar_layout("appmenu", "close,minimize,maximize")
        self.assertEqual(layout, "appmenu:close,minimize,maximize")

    def test_omit_some_buttons(self) -> None:
        layout = _build_titlebar_layout(None, "minimize,close")
        self.assertEqual(layout, ":minimize,close")

    def test_empty_explicit_both_invalid(self) -> None:
        out = _build_titlebar_layout("", "")
        self.assertIsInstance(out, ToolResult)
        assert isinstance(out, ToolResult)
        self.assertFalse(out.ok)

    def test_unknown_token(self) -> None:
        out = _build_titlebar_layout(None, "quit")
        self.assertIsInstance(out, ToolResult)
        assert isinstance(out, ToolResult)
        self.assertFalse(out.ok)

    def test_duplicate_across_sides(self) -> None:
        out = _build_titlebar_layout("close", "minimize,close")
        self.assertIsInstance(out, ToolResult)
        assert isinstance(out, ToolResult)
        self.assertFalse(out.ok)


if __name__ == "__main__":
    unittest.main()
