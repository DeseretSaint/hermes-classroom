"""H-106 — the Sources panel shows provenance, the exact excerpt and the support basis.

What this proves, against the shipped code:

* the two reads that feed the panel (``lesson.page`` and ``parent.blueprint.read``) carry the
  publisher, the fetched excerpt, the rows hash and the model's own assessment word, joined from the
  immutable research-run snapshot — the ``sources`` row alone never had those;
* ``excerpt_state`` is a typed absence, so "no excerpt stored" and "the snapshot could not be read"
  never collapse into one sentence;
* the panel renders plain words, keeps every raw enum inside a Technical detail disclosure, shows a
  long excerpt in full behind a collapsible reveal, and escapes text (no HTML injection);
* the prose measure stays inside the 50–75 character band;
* an empty list is a typed state, not a silent blank, and a failed read is an error with a retry.

What this does NOT prove: that a live provider run today records an excerpt — that needs a real
research job; these reads are exercised against the real kernel database with a recorded snapshot.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from coursebook import db, generation
from tests.kernel_support import KernelCase
from tests.test_desktop_lesson_views import PLUGIN_JS, SDK_STUB, _desktop_node_modules

HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { ProvenanceInventoryRow, SourceProvenancePanel } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
if (payload.kind === 'panel') {
  process.stdout.write(
    renderToStaticMarkup(
      React.createElement(SourceProvenancePanel, {
        sources: payload.sources,
        status: payload.status || 'ready',
        error: payload.error || null,
        onRetry: payload.onRetry ? () => {} : null,
        intro: payload.intro || null,
        emptyTitle: payload.emptyTitle || null,
        emptyDescription: payload.emptyDescription || null,
        dense: Boolean(payload.dense),
        extra: payload.vocabulary
          ? React.createElement(ProvenanceInventoryRow, { vocabulary: payload.vocabulary })
          : null
      })
    )
  )
} else if (payload.kind === 'inventory') {
  process.stdout.write(
    renderToStaticMarkup(React.createElement(ProvenanceInventoryRow, { vocabulary: payload.vocabulary }))
  )
} else {
  throw new Error(`unknown payload kind ${payload.kind}`)
}
"""

EXCERPT = "A frequency list is a description of a corpus, not a claim about any learner."


class ProvenanceReadTest(KernelCase):
    """The real handlers join the recorded snapshot onto both reads the panel consumes."""

    def seed_source(
        self,
        lesson: dict,
        *,
        status: str = "model_assessed",
        snapshot: bool = True,
        assessment: str = "partial",
        excerpt: str | None = EXCERPT,
        publisher: str | None = "Example Press",
        broken_snapshot: bool = False,
    ) -> str:
        source_id = "src_h106_1"
        with db.transaction() as connection:
            generation.ensure_schema(connection)
            connection.execute(
                "INSERT INTO sources (id, course_id, url, title, source_type, published_at, fetched_at,"
                " support_status, claim_count, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    source_id,
                    lesson["course_id"],
                    "https://example.test/frequency",
                    "Frequency list",
                    "reference",
                    "2026-01-01T00:00:00Z",
                    "2026-02-01T00:00:00Z",
                    status,
                    2,
                    "2026-02-01T00:00:00Z",
                ),
            )
            if snapshot:
                connection.execute(
                    "INSERT INTO gen_research_runs (id, course_id, job_id, status, queries_json,"
                    " sources_json, reason, created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        "run_h106",
                        lesson["course_id"],
                        None,
                        "ok",
                        "[]",
                        "{not json" if broken_snapshot else json.dumps(
                            [
                                {
                                    "source_id": source_id,
                                    "url": "https://example.test/frequency",
                                    "title": "Frequency list",
                                    "publisher": publisher,
                                    "source_type": "reference",
                                    "support_status": assessment,
                                    "excerpt": excerpt,
                                    "content_hash": "sha256:" + "b" * 64,
                                }
                            ]
                        ),
                        None,
                        "2026-02-01T00:00:00Z",
                    ),
                )
        return source_id

    def lesson_page_sources(self, lesson: dict) -> list[dict]:
        result = self.ok(
            "lesson.page",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
        )["result"]
        return result["sources"]

    def test_the_page_carries_publisher_excerpt_hash_and_the_model_word(self) -> None:
        lesson = self.prepare_lesson()
        self.seed_source(lesson)
        [source] = self.lesson_page_sources(lesson)
        self.assertEqual(source["support_status"], "model_assessed")
        self.assertEqual(source["support_assessment"], "partial")
        self.assertEqual(source["publisher"], "Example Press")
        self.assertEqual(source["excerpt"], EXCERPT)
        self.assertEqual(source["excerpt_state"], "recorded")
        self.assertEqual(source["content_hash"], "sha256:" + "b" * 64)

    def test_the_blueprint_read_carries_the_same_fields_for_plan_review(self) -> None:
        lesson = self.prepare_lesson()
        self.seed_source(lesson, assessment="supported")
        result = self.ok("parent.blueprint.read", {"course_id": lesson["course_id"]})["result"]
        [source] = result["sources"]
        self.assertEqual(source["publisher"], "Example Press")
        self.assertEqual(source["support_assessment"], "supported")
        self.assertEqual(source["excerpt"], EXCERPT)

    def test_a_course_without_a_recorded_run_says_the_excerpt_is_missing(self) -> None:
        lesson = self.prepare_lesson()
        self.seed_source(lesson, snapshot=False)
        [source] = self.lesson_page_sources(lesson)
        self.assertEqual(source["excerpt_state"], "missing")
        self.assertIsNone(source["excerpt"])
        self.assertIsNone(source["support_assessment"])

    def test_an_unreadable_snapshot_is_not_the_same_as_no_excerpt(self) -> None:
        lesson = self.prepare_lesson()
        self.seed_source(lesson, broken_snapshot=True)
        [source] = self.lesson_page_sources(lesson)
        self.assertEqual(source["excerpt_state"], "unreadable")

    def test_the_contract_accepts_the_additive_fields(self) -> None:
        lesson = self.prepare_lesson()
        self.seed_source(lesson)
        [source] = self.lesson_page_sources(lesson)
        self.assertIn("excerpt_state", source)
        self.assertIn("support_assessment", source)
        self.assertIn("modality", source)
        self.assertIn("licence", source)


class ProvenanceRenderTest(unittest.TestCase):
    """The shipped module renders with React's server renderer — no build, no reimplementation."""

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-h106-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        node_modules = root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
            encoding="utf-8",
        )
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")
        cls.root = root

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def render(self, payload: dict) -> str:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        return result.stdout

    def source(self, **overrides) -> dict:
        base = {
            "source_id": "src_render_1",
            "title": "Frequency list",
            "url": "https://example.test/frequency",
            "publisher": "Example Press",
            "source_type": "reference",
            "support_status": "model_assessed",
            "support_assessment": "partial",
            "excerpt": EXCERPT,
            "excerpt_state": "recorded",
            "content_hash": "sha256:" + "c" * 64,
            "fetched_at": "2026-02-01T00:00:00Z",
            "published_at": "2026-01-01T00:00:00Z",
            "claim_count": 2,
        }
        base.update(overrides)
        return base

    def main_line(self, html: str) -> str:
        """Everything a reader sees before opening a disclosure."""
        without_details = re.sub(r"<details\b.*?</details>", "", html, flags=re.DOTALL)
        return re.sub(r"<[^>]+>", " ", without_details)

    def test_empty_is_a_typed_state_not_a_blank_panel(self) -> None:
        html = self.render({"kind": "panel", "sources": [], "status": "ready"})
        self.assertIn('data-cb-provenance-state="empty"', html)
        self.assertIn("No source is recorded", html)
        self.assertIn("presented as cited", html)

    def test_a_failed_read_is_an_error_with_a_retry_not_an_empty_list(self) -> None:
        html = self.render(
            {
                "kind": "panel",
                "sources": [],
                "status": "error",
                "error": {"code": "INTERNAL_ERROR", "message": "the ledger could not be read"},
                "onRetry": True,
            }
        )
        self.assertIn('data-cb-provenance-state="error"', html)
        self.assertIn("INTERNAL_ERROR", html)
        self.assertIn("Try again", html)

    def test_partial_support_is_labelled_as_a_model_assessment(self) -> None:
        html = self.render({"kind": "panel", "sources": [self.source()], "status": "ready"})
        self.assertIn('data-cb-source-support="model_assessed"', html)
        self.assertIn("Model-assessed", html)
        self.assertIn("only partly supports the claim", html)
        self.assertIn("not a document proof", html)
        main = self.main_line(html)
        self.assertNotIn("model_assessed", main)
        self.assertIn("model_assessed", html)  # the technical disclosure keeps the enum

    def test_unverified_support_never_reads_as_verified(self) -> None:
        html = self.render(
            {
                "kind": "panel",
                "sources": [self.source(support_assessment="unverified")],
                "status": "ready",
            }
        )
        self.assertIn("could not verify the claim", html)
        self.assertIn("Not assessed", self.render({
            "kind": "panel",
            "sources": [self.source(support_status="unassessed", support_assessment=None)],
            "status": "ready",
        }))
        self.assertNotIn("Verified</span>", html)

    def test_a_long_excerpt_is_shown_in_full_behind_a_disclosure(self) -> None:
        long_text = ("Long fetched passage. " * 400).strip()
        html = self.render(
            {
                "kind": "panel",
                "sources": [self.source(excerpt=long_text, excerpt_state="recorded")],
                "status": "ready",
            }
        )
        self.assertIn('data-cb-source-excerpt="recorded"', html)
        self.assertIn("<details", html)
        self.assertIn("Exact excerpt", html)
        self.assertIn(long_text, html)
        self.assertIn("max-height:14rem", html)

    def test_a_missing_excerpt_is_said_plainly(self) -> None:
        html = self.render(
            {
                "kind": "panel",
                "sources": [self.source(excerpt=None, excerpt_state="missing")],
                "status": "ready",
            }
        )
        self.assertIn('data-cb-source-excerpt="missing"', html)
        self.assertIn("No excerpt is stored for this source", html)

    def test_an_unreadable_snapshot_is_not_reported_as_no_excerpt(self) -> None:
        html = self.render(
            {
                "kind": "panel",
                "sources": [self.source(excerpt=None, excerpt_state="unreadable")],
                "status": "ready",
            }
        )
        self.assertIn('data-cb-source-excerpt="unreadable"', html)
        self.assertIn("could not be read", html)
        self.assertIn("not absent", html)
        self.assertNotIn("No excerpt is stored for this source", html)

    def test_text_is_escaped_and_no_markup_survives(self) -> None:
        injected = '<script>alert("x")</script><img src=x onerror=alert(1)>'
        html = self.render(
            {
                "kind": "panel",
                "sources": [self.source(title=injected, excerpt=injected, publisher=injected)],
                "status": "ready",
            }
        )
        self.assertNotIn("<script>alert", html)
        self.assertNotIn("<img src=x", html)
        self.assertIn("&lt;script&gt;", html)

    def test_the_prose_measure_stays_inside_the_readable_band(self) -> None:
        html = self.render({"kind": "panel", "sources": [self.source()], "status": "ready"})
        measures = [int(value) for value in re.findall(r"max-width:\s*(\d+)ch", html)]
        self.assertTrue(measures)
        for value in measures:
            self.assertGreaterEqual(value, 50)
            self.assertLessEqual(value, 75)

    def test_no_licence_is_recorded_rather_than_guessed(self) -> None:
        html = self.render({"kind": "panel", "sources": [self.source()], "status": "ready"})
        self.assertIn("Rights: not recorded", html)
        self.assertIn("A title and a URL are not a licence.", html)

    def test_an_inventory_prints_source_licence_band_and_hash(self) -> None:
        vocabulary = {
            "status": "inventory",
            "source_id": "coursebook-fixture-ja-v1",
            "licence": "CC0-1.0",
            "licence_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "modality": "mixed",
            "content_hash": "sha256:" + "d" * 64,
            "band": {"id": "band-core", "from_rank": 1, "to_rank": 7},
            "items": [{"lemma": "水"}, {"lemma": "これ"}, {"lemma": "食べる"}],
        }
        html = self.render({"kind": "inventory", "vocabulary": vocabulary})
        self.assertIn('data-cb-vocabulary-source="inventory"', html)
        for expected in ("coursebook-fixture-ja-v1", "CC0-1.0", "mixed", "band-core", "1–7", "sha256:dddddddddddd…"):
            self.assertIn(expected, html)
        self.assertNotIn("水", html)
        self.assertNotIn("%", html)
        main = self.main_line(html)
        self.assertIn("sha256:dddddddddddd…", main)
        self.assertNotIn("sha256:" + "d" * 64, main)

    def test_an_absent_inventory_is_the_typed_unverified_state(self) -> None:
        html = self.render({"kind": "inventory", "vocabulary": None})
        self.assertIn('data-cb-vocabulary-source="unverified"', html)
        self.assertIn("No word list is verified for this plan", html)


if __name__ == "__main__":
    unittest.main()
