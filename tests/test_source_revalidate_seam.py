"""The host fetch seam that lets ``source.revalidate`` be honest (W2).

``source.revalidate`` is frozen in ``cb.rpc`` and takes the page text from its caller, but the
plugin ``ctx`` has no fetch capability, so no Desktop surface could ever produce the state that
``CHECK_STALE`` guards. This card lands the missing half: ``POST /sources/revalidate`` dispatches
``web_extract`` through the host's own tool registry and hands the bounded text to the frozen
method.

What these tests pin:

* the seam binds the **dashboard-loaded** copy of the backend (a different module object from the
  agent's, which is why binding in the agent process left ``host_search() -> None`` here), and the
  fetch is dispatched through a stand-in registered *behind* the host registry — never by patching
  ``research.host_search``;
* a process with no host tool package refuses with a named ``EXTRACT_UNAVAILABLE`` and writes
  nothing, instead of silently passing;
* one idempotency key per (source, page text), so re-checking unchanged text replays the recorded
  response instead of writing the source row again.
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from coursebook import db, generation, research
from tests.kernel_support import KernelCase

ROOT = Path(__file__).resolve().parent.parent
API_MODULE = "coursebook_plugin_api_revalidate_test"
BACKEND = "coursebook_plugin_backend"
SOURCE_ID = "src_revalidate_1"
PAGE_URL = "https://example.test/page"
PAGE_BODY = "the page body"


def load_api() -> Any:
    """Load the serving route module the way the dashboard does: by path, not by import."""
    if API_MODULE in sys.modules:
        return sys.modules[API_MODULE]
    spec = importlib.util.spec_from_file_location(API_MODULE, ROOT / "dashboard" / "plugin_api.py")
    if spec is None or spec.loader is None:  # pragma: no cover - packaging error
        raise AssertionError("cannot load dashboard/plugin_api.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[API_MODULE] = module
    spec.loader.exec_module(module)
    return module


class RevalidateSeamCase(KernelCase):
    """One real migrated profile database, one seeded ledger row, a stand-in behind the registry."""

    def setUp(self) -> None:
        super().setUp()
        self.api = load_api()
        self.api._load_backend()
        self.serving = importlib.import_module(f"{BACKEND}.coursebook.research")
        # The seam is process-global on the module the routes actually use; every case starts
        # unbound so the route has to bind it the way a serving process does.
        self.serving.bind_host_seam(None)
        self.addCleanup(self.serving.bind_host_seam, None)
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.source_id = self.seed_source()

    # ── fixtures ────────────────────────────────────────────────────────

    def seed_source(self, *, status: str = "model_assessed") -> str:
        lesson = self.prepare_lesson()
        with db.transaction() as connection:
            generation.ensure_schema(connection)
            connection.execute(
                "INSERT INTO sources (id, course_id, url, title, source_type, published_at, fetched_at,"
                " support_status, claim_count, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (SOURCE_ID, lesson["course_id"], PAGE_URL, "Example page", "web",
                 "2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z", status, 1,
                 "2026-02-01T00:00:00Z"),
            )
        return SOURCE_ID

    def registry_with_stand_in(self, content: str) -> Any:
        """A real host ``ToolRegistry`` with the stand-in registered behind ``web_extract``."""
        from tools.registry import ToolRegistry

        page = {"url": PAGE_URL, "title": "Example page", "content": content}

        def handler(args: dict[str, Any]) -> str:
            self.calls.append(("web_extract", dict(args)))
            return json.dumps({"results": [page]})

        registry = ToolRegistry()
        registry.register(
            name="web_extract",
            toolset="coursebook-tests",
            schema={
                "name": "web_extract",
                "description": "stand-in for the host web_extract handler",
                "parameters": {"type": "object", "properties": {}},
            },
            handler=handler,
            description="test stand-in for the host web_extract handler",
        )
        return registry

    def revalidate(self, *, content: str = PAGE_BODY) -> dict[str, Any]:
        registry = self.registry_with_stand_in(content)
        self.assertTrue(self.api.bind_process_seam(registry), "an injected host registry must bind")
        return asyncio.run(self.api.sources_revalidate({"source_id": self.source_id}))

    # ── the seam ────────────────────────────────────────────────────────

    def test_the_fetch_is_dispatched_through_the_host_registry_stand_in(self) -> None:
        response = self.revalidate()

        self.assertTrue(response["ok"], response)
        self.assertTrue(response["fetched"], "a live fetch is reported as one")
        self.assertEqual(
            self.calls,
            [("web_extract", {"urls": [PAGE_URL], "char_limit": research.REVALIDATE_TEXT_LIMIT})],
            "the handler behind the host registry is the only fetch path",
        )
        # The module the routes use is the dashboard copy, not the agent package: binding it is
        # the whole point (binding the agent-side copy leaves this one at None).
        self.assertEqual(self.serving.__name__, f"{BACKEND}.coursebook.research")
        self.assertIsNotNone(self.serving.host_search())
        self.assertEqual(response["content_hash"], research.sha256_of_text(PAGE_BODY))
        self.assertFalse(response["changed"], "the first fetch of a baseline source is not a change")
        self.assertEqual(
            self.scalar("SELECT support_status FROM sources WHERE id = ?", (self.source_id,)),
            "model_assessed",
        )

    # ── idempotency ─────────────────────────────────────────────────────

    def test_unchanged_text_replays_instead_of_writing_the_row_twice(self) -> None:
        first = self.revalidate()
        second = self.revalidate()

        self.assertEqual(second, first, "the same (source, text) must replay the recorded response")
        key = research.revalidate_key(self.source_id, PAGE_BODY)
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM idempotency_keys WHERE key = ?", (key,)),
            1,
            "one key per (source, page text)",
        )
        self.assertEqual(
            self.scalar("SELECT fetched_at FROM sources WHERE id = ?", (self.source_id,)),
            first["fetched_at"],
            "a replayed re-check does not re-stamp the row",
        )
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM sources"), 1)

    def test_changed_text_is_a_new_key_and_a_real_comparison(self) -> None:
        self.revalidate()
        changed = self.revalidate(content="a revised page body")

        self.assertTrue(changed["ok"], changed)
        self.assertTrue(changed["changed"])
        self.assertEqual(changed["support_status"], "stale")
        self.assertTrue(changed["review_required"])
        self.assertEqual(
            changed["content_hash"], research.sha256_of_text("a revised page body")
        )
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM idempotency_keys"), 2)
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM idempotency_keys WHERE key = ?",
                        (research.revalidate_key(self.source_id, PAGE_BODY),)),
            1,
        )

    # ── the honest refusal ──────────────────────────────────────────────

    def test_a_process_without_the_host_tool_package_refuses_extract_unavailable(self) -> None:
        self.assertIsNone(self.serving.host_search(), "no seam is bound before the route runs")
        # A process that never had the agent's tool package: the import the seam needs fails.
        with mock.patch.dict(sys.modules, {"tools": None, "tools.registry": None}):
            self.assertFalse(self.api.bind_process_seam())
            response = asyncio.run(self.api.sources_revalidate({"source_id": self.source_id}))

        self.assertFalse(response["ok"], response)
        self.assertEqual(response["code"], "EXTRACT_UNAVAILABLE")
        self.assertIsNone(self.serving.host_search(), "a failed bind leaves no half-seam behind")
        self.assertEqual(self.calls, [], "nothing was fetched")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM idempotency_keys"), 0)
        self.assertIsNone(
            self.scalar("SELECT content_hash FROM sources WHERE id = ?", (self.source_id,))
        )
        self.assertEqual(
            self.scalar("SELECT support_status FROM sources WHERE id = ?", (self.source_id,)),
            "model_assessed",
            "a capability refusal writes nothing: the source is not marked unreachable",
        )

    def test_an_unreachable_page_is_recorded_not_reported_unchanged(self) -> None:
        """A fetch failure is the contract's ``fetched: null`` outcome, not a capability refusal."""
        from tools.registry import ToolRegistry

        def failing(args: dict[str, Any]) -> str:
            self.calls.append(("web_extract", dict(args)))
            return json.dumps({"results": [{"url": PAGE_URL, "error": "connection reset"}]})

        registry = ToolRegistry()
        registry.register(
            name="web_extract",
            toolset="coursebook-tests",
            schema={"name": "web_extract", "parameters": {"type": "object", "properties": {}}},
            handler=failing,
            description="stand-in that fails the extract",
        )
        self.assertTrue(self.api.bind_process_seam(registry))
        response = asyncio.run(self.api.sources_revalidate({"source_id": self.source_id}))

        self.assertTrue(response["ok"], response)
        self.assertFalse(response["fetched"], "an unreachable page is not a fetch")
        self.assertFalse(response["changed"])
        self.assertEqual(response["support_status"], "unreachable")
        self.assertTrue(response["review_required"])
        self.assertIsNone(
            self.scalar("SELECT content_hash FROM sources WHERE id = ?", (self.source_id,)),
            "no baseline hash is invented for a page that did not load",
        )


if __name__ == "__main__":
    unittest.main()
