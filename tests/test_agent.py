"""Tests for the Phase 4 retrieval-first agent.

Covers:
- Heuristic fast-path patterns produce the right tool/params (no LLM, no embeds).
- decide_turn picks fastpath > llm_tools > llm_chat correctly.
- toolspec_to_openai_tool emits a well-formed OpenAI function-tool schema.
- build_agent_system_prompt inlines RAG <KNOWLEDGE> blocks when supplied.
- Tool memory/result formatting prefixes are stable.

These tests deliberately avoid touching the LLM or the embedding server. We
stub `agent.retrieve` with a fake function whose result drives `decide_turn`.
"""
from __future__ import annotations

import unittest
from typing import Callable
from unittest.mock import patch

import agent
from agent import (
    DEFAULT_BASE_IDENTITY,
    TOOL_FEEDBACK_PREFIX,
    TOOL_MEMORY_PREFIX,
    build_agent_system_prompt,
    decide_turn,
    format_tool_memory_message,
    format_tool_result_message,
    match_fastpath,
    toolspec_to_openai_tool,
)
from retrieval.index import KIND_RAG, KIND_TOOL, IndexEntry, IndexHit
from retrieval.query import RetrievalResult
from retrieval.rag_chunker import RagChunk
from tools.registry import get_tool
from tools.schema import tool_result_ok


def _tool_hit(tool_name: str, score: float) -> IndexHit:
    return IndexHit(
        entry=IndexEntry(kind=KIND_TOOL, index_text=f"ex {tool_name}", tool_name=tool_name),
        score=score,
    )


def _rag_hit(doc: str, section: str, body: str, score: float) -> IndexHit:
    chunk = RagChunk(doc_path=doc, doc_title=doc, section=section, body=body)
    return IndexHit(
        entry=IndexEntry(kind=KIND_RAG, index_text=chunk.index_text, rag_chunk=chunk),
        score=score,
    )


def _patch_retrieve(retrieve_fn: Callable[..., RetrievalResult]):
    """Helper to swap out agent.retrieve in a test."""
    return patch.object(agent, "retrieve", side_effect=retrieve_fn)


class TestFastpath(unittest.TestCase):
    def test_volume_set_percent(self) -> None:
        c = match_fastpath("set volume to 30%")
        self.assertEqual(c, {"tool": "volume_set_percent", "params": {"percent": 30}})

    def test_volume_short_form(self) -> None:
        c = match_fastpath("volume 75")
        self.assertIsNotNone(c)
        assert c is not None
        self.assertEqual(c["tool"], "volume_set_percent")
        self.assertEqual(c["params"], {"percent": 75})

    def test_mute_unmute(self) -> None:
        self.assertEqual(
            match_fastpath("mute"), {"tool": "volume_mute_toggle", "params": {"state": "mute"}}
        )
        self.assertEqual(
            match_fastpath("Unmute"), {"tool": "volume_mute_toggle", "params": {"state": "unmute"}}
        )
        self.assertEqual(
            match_fastpath("please mute the audio"),
            {"tool": "volume_mute_toggle", "params": {"state": "mute"}},
        )

    def test_brightness_set(self) -> None:
        c = match_fastpath("set brightness to 60%")
        self.assertEqual(c, {"tool": "brightness_set", "params": {"action": "set", "value": 60}})

    def test_screenshot(self) -> None:
        for q in ("take a screenshot", "screenshot.", "grab a screenshot please"):
            self.assertEqual(match_fastpath(q), {"tool": "screenshot_save", "params": {}})

    def test_datetime(self) -> None:
        for q in ("what time is it?", "what's the date?", "what day is it"):
            c = match_fastpath(q)
            self.assertIsNotNone(c, msg=f"no fastpath for: {q!r}")
            assert c is not None
            self.assertEqual(c["tool"], "datetime_query")
            self.assertEqual(c["params"], {})

    def test_process_running(self) -> None:
        c = match_fastpath("is firefox running?")
        self.assertEqual(c, {"tool": "process_check_running", "params": {"name": "firefox"}})

    def test_wifi_toggle(self) -> None:
        self.assertEqual(match_fastpath("turn wifi off"), {"tool": "wifi_toggle", "params": {"state": "off"}})
        self.assertEqual(match_fastpath("enable wi-fi"), {"tool": "wifi_toggle", "params": {"state": "on"}})

    def test_alt_tab_switch_windows_fastpath(self) -> None:
        self.assertEqual(
            match_fastpath("traditional alt tab"),
            {"tool": "gnome_alt_tab_switch_windows_mode", "params": {"mode": "traditional"}},
        )
        self.assertEqual(
            match_fastpath("restore alt tab to default"),
            {"tool": "gnome_alt_tab_switch_windows_mode", "params": {"mode": "default"}},
        )
        self.assertEqual(
            match_fastpath("ungroup alt tab"),
            {"tool": "gnome_alt_tab_switch_windows_mode", "params": {"mode": "traditional"}},
        )
        self.assertEqual(
            match_fastpath("group alt tab by apps"),
            {"tool": "gnome_alt_tab_switch_windows_mode", "params": {"mode": "default"}},
        )

    def test_titlebar_buttons_no_fastpath(self) -> None:
        self.assertIsNone(match_fastpath("show minimize and maximize buttons on windows"))

    def test_clamps_volume_out_of_range(self) -> None:
        c = match_fastpath("set volume to 250")
        self.assertIsNotNone(c)
        assert c is not None
        self.assertEqual(c["params"]["percent"], 100)

    def test_no_match(self) -> None:
        self.assertIsNone(match_fastpath("how do I tar a directory?"))
        self.assertIsNone(match_fastpath("hello there"))
        self.assertIsNone(match_fastpath(""))


class TestDecideTurn(unittest.TestCase):
    def test_fastpath_wins_before_retrieval(self) -> None:
        def fake_retrieve(*_, **__):
            raise AssertionError("retrieve must not be called when fastpath matches")

        with _patch_retrieve(fake_retrieve):
            plan = decide_turn("set volume to 40%")
        self.assertEqual(plan.kind, "fastpath")
        self.assertIsNotNone(plan.fastpath_call)
        assert plan.fastpath_call is not None
        self.assertEqual(plan.fastpath_call["tool"], "volume_set_percent")

    def test_llm_tools_when_candidates_present(self) -> None:
        def fake_retrieve(query, **_):
            return RetrievalResult(
                query=query,
                tools=[_tool_hit("file_search_name", 0.81), _tool_hit("file_list_dir", 0.62)],
                rag=[_rag_hit("rag_data/grep_basics.md", "Common usage", "use rg -n", 0.55)],
            )

        with _patch_retrieve(fake_retrieve), patch.object(agent, "supports_tools", return_value=True):
            plan = decide_turn("can you find a file called notes.md?")
        self.assertEqual(plan.kind, "llm_tools")
        self.assertEqual(plan.candidate_tools, ["file_search_name", "file_list_dir"])
        self.assertEqual(len(plan.rag_hits), 0)

    def test_chat_when_no_tool_candidates(self) -> None:
        def fake_retrieve(query, **_):
            return RetrievalResult(
                query=query,
                tools=[],
                rag=[_rag_hit("rag_data/grep_basics.md", "Common usage", "rg -n pattern", 0.61)],
            )

        with _patch_retrieve(fake_retrieve), patch.object(agent, "supports_tools", return_value=True):
            plan = decide_turn("how do I search inside files with ripgrep?")
        self.assertEqual(plan.kind, "llm_chat")
        self.assertEqual(plan.candidate_tools, [])
        self.assertEqual(len(plan.rag_hits), 1)

    def test_chat_when_backend_lacks_tool_support(self) -> None:
        def fake_retrieve(query, **_):
            return RetrievalResult(
                query=query,
                tools=[_tool_hit("file_search_name", 0.81)],
                rag=[],
            )

        with _patch_retrieve(fake_retrieve), patch.object(agent, "supports_tools", return_value=False):
            plan = decide_turn("can you find a file called notes.md?")
        self.assertEqual(plan.kind, "llm_chat")
        self.assertEqual(plan.candidate_tools, [])

    def test_chat_on_embedding_outage(self) -> None:
        from embeddings import EmbeddingUnavailableError

        def fake_retrieve(*_, **__):
            raise EmbeddingUnavailableError("embed server down")

        with _patch_retrieve(fake_retrieve), patch.object(agent, "supports_tools", return_value=True):
            plan = decide_turn("anything that wouldn't fastpath")
        self.assertEqual(plan.kind, "llm_chat")
        self.assertEqual(plan.candidate_tools, [])
        self.assertEqual(plan.rag_hits, [])


class TestToolspecConversion(unittest.TestCase):
    def test_known_tool_round_trip(self) -> None:
        spec = get_tool("volume_set_percent")
        self.assertIsNotNone(spec)
        assert spec is not None
        payload = toolspec_to_openai_tool(spec)
        self.assertEqual(payload["type"], "function")
        fn = payload["function"]
        self.assertEqual(fn["name"], "volume_set_percent")
        self.assertIn("parameters", fn)
        self.assertEqual(fn["parameters"]["type"], "object")
        self.assertIn("percent", fn["parameters"]["properties"])
        self.assertNotIn("distro", fn["parameters"]["properties"])

    def test_required_propagated(self) -> None:
        spec = get_tool("file_search_name")
        self.assertIsNotNone(spec)
        assert spec is not None
        payload = toolspec_to_openai_tool(spec)
        required = payload["function"]["parameters"].get("required", [])
        for p in spec.parameters:
            if p.required and p.name != "distro":
                self.assertIn(p.name, required)

    def test_no_additional_properties(self) -> None:
        for spec_name in ("ping", "wifi_toggle", "datetime_query"):
            spec = get_tool(spec_name)
            self.assertIsNotNone(spec, msg=spec_name)
            assert spec is not None
            payload = toolspec_to_openai_tool(spec)
            self.assertFalse(payload["function"]["parameters"]["additionalProperties"])


class TestSystemPrompt(unittest.TestCase):
    def test_prompt_has_distro_and_identity(self) -> None:
        s = build_agent_system_prompt(rag_hits=None, distro="fedora", base_identity="You are Meera.")
        self.assertIn("You are Meera.", s)
        self.assertIn("Host distro: fedora.", s)
        self.assertIn("Current local date:", s)
        self.assertIn("time:", s)
        self.assertNotIn("UTC offset", s)
        self.assertNotIn("<KNOWLEDGE", s)

    def test_prompt_inlines_rag_blocks(self) -> None:
        hits = [
            _rag_hit("rag_data/grep_basics.md", "Common usage", "use rg -n pattern path/", 0.7),
            _rag_hit("rag_data/find_basics.md", "Find by name", "find . -name '*.md'", 0.6),
        ]
        s = build_agent_system_prompt(rag_hits=hits, distro="ubuntu")
        self.assertIn("<KNOWLEDGE doc=\"rag_data/grep_basics.md\" section=\"Common usage\">", s)
        self.assertIn("rg -n pattern path/", s)
        self.assertIn("<KNOWLEDGE doc=\"rag_data/find_basics.md\" section=\"Find by name\">", s)
        self.assertIn(DEFAULT_BASE_IDENTITY.split("\n", 1)[0][:20], s)


class TestToolMemoryFormatting(unittest.TestCase):
    def test_feedback_prefix(self) -> None:
        r = tool_result_ok("ok", data={"x": 1})
        msg = format_tool_result_message("ping", r)
        self.assertTrue(msg.startswith(TOOL_FEEDBACK_PREFIX))
        self.assertIn("ping", msg)
        self.assertIn('"ok": true', msg)

    def test_memory_prefix_truncates_long_lists(self) -> None:
        r = tool_result_ok("ok", data={"entries": [str(i) for i in range(120)]})
        msg = format_tool_memory_message("file_search_name", r)
        self.assertTrue(msg.startswith(TOOL_MEMORY_PREFIX))
        self.assertIn("file_search_name", msg)
        self.assertIn("...(", msg)


if __name__ == "__main__":
    unittest.main()
