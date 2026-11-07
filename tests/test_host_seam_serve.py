"""H-63 D-H63-1 — the research seam in a serve/dashboard process.

A ``hermes serve`` process loads plugins but never runs the agent's tool setup, so its registry
holds no ``web_search`` handler and ``ctx.dispatch_tool`` answers the registry's own
``{"error": "Unknown tool: web_search"}`` body. The adapter used to read only
``{"success": false}``, so that body looked like a successful empty search: every plan authored by
the serving process recorded ``research.status = "unavailable"`` with the reason "no source could
be fetched" and no failure at all.

These tests pin both halves of the fix: the registry error body is a recorded failure, and the
adapter asks the host to register its own web tools and retries once.
"""

from __future__ import annotations

import json
import unittest
from unittest import mock

from coursebook import research


class RegistryShapedHost:
    """A host whose registry has no web tool: every dispatch answers the registry error body."""

    def __init__(self, *, results: list[dict] | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.results = results

    def dispatch_tool(self, name: str, args: dict) -> str:
        self.calls.append((name, dict(args)))
        if self.results is not None and len(self.calls) > 1:
            return json.dumps(
                {"success": True, "data": {"web": self.results}},
                ensure_ascii=False,
            )
        return json.dumps({"error": f"Unknown tool: {name}"})


class ServeResearchSeamTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tools = research._HOST_TOOLS
        research._HOST_TOOLS = None

    def tearDown(self) -> None:
        research._HOST_TOOLS = self._tools

    def test_unknown_tool_body_is_a_failure_not_an_empty_search(self) -> None:
        host = RegistryShapedHost()
        seam = research.HermesToolSearch.from_ctx(host)
        with mock.patch.object(research, "ensure_host_tools", return_value=False):
            with self.assertRaises(research.ResearchUnavailable) as caught:
                seam.search("bicycle derailleur", 3)
        self.assertIn("Unknown tool", str(caught.exception))

    def test_run_research_records_the_registry_failure_as_the_reason(self) -> None:
        host = RegistryShapedHost()
        seam = research.HermesToolSearch.from_ctx(host)
        with mock.patch.object(research, "ensure_host_tools", return_value=False):
            run = research.run_research("bicycle derailleur indexing", recipe="one_off", scope="single", search=seam)
        self.assertEqual(run.status, "unavailable")
        self.assertIn("Unknown tool", run.reason or "")
        self.assertEqual(run.sources, [])

    def test_unknown_tool_retries_once_after_the_host_tools_register(self) -> None:
        host = RegistryShapedHost(
            results=[{"url": "https://example.org/doc", "title": "Doc", "description": "d"}]
        )
        seam = research.HermesToolSearch.from_ctx(host)
        with mock.patch.object(research, "ensure_host_tools", return_value=True):
            rows = seam.search("bicycle derailleur", 3)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["url"], "https://example.org/doc")
        self.assertEqual([name for name, _ in host.calls], ["web_search", "web_search"])

    def test_registry_error_without_a_success_flag_is_a_failure(self) -> None:
        class FailingHost:
            def dispatch_tool(self, name: str, args: dict) -> str:
                return json.dumps({"error": "Tool execution failed: provider exploded"})

        seam = research.HermesToolSearch.from_ctx(FailingHost())
        with mock.patch.object(research, "ensure_host_tools", return_value=False):
            with self.assertRaises(research.ResearchUnavailable):
                seam.search("q", 3)


if __name__ == "__main__":
    unittest.main()
