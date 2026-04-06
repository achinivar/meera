"""Unit tests for the Phase 2 tool layer (mocked where needed)."""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from tools.registry import TOOLS, get_tool, tools_manifest_json
from tools.runner import run_tool
from tools.schema import TOOLS_SCHEMA_VERSION


class TestRegistry(unittest.TestCase):
    def test_unique_tool_names(self) -> None:
        names = [t.name for t in TOOLS]
        self.assertEqual(len(names), len(set(names)))

    def test_get_tool(self) -> None:
        self.assertIsNotNone(get_tool("ping"))
        self.assertIsNone(get_tool("nonexistent_tool_xyz"))

    def test_manifest_json_roundtrip(self) -> None:
        payload = json.loads(tools_manifest_json())
        self.assertEqual(payload["schema_version"], TOOLS_SCHEMA_VERSION)
        self.assertGreater(len(payload["tools"]), 3)
        for spec in payload["tools"]:
            names = {p["name"] for p in spec["parameters"]}
            self.assertIn(
                "distro",
                names,
                msg=f"tool {spec['name']!r} must declare distro per Phase2 plan",
            )

    def test_manifest_has_no_handler(self) -> None:
        raw = tools_manifest_json()
        self.assertNotIn("handler", raw)


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

    def test_distro_mismatch(self) -> None:
        with patch("tools.runner.detect_distro", return_value="fedora"):
            r = run_tool("ping", {"distro": "ubuntu"})
        self.assertFalse(r.ok)
        self.assertEqual(r.error_code, "DISTRO_MISMATCH")

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


if __name__ == "__main__":
    unittest.main()
