"""Unit tests for the Phase 2 tool layer (mocked where needed)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.registry import TOOLS, get_tool, tools_prompt_catalog_json
from tools.runner import run_tool


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


if __name__ == "__main__":
    unittest.main()
