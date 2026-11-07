"""Field Notes makes a saved moment a first-class learning surface.

The plugin is one ESM file with no build step, so these tests render the shipped module through
React and inspect the DOM it produces. They cover the three save surfaces (a document block, that
block's media child, and a quiz review), the provenance the save carries, the Field Notes strip on
the Field Desk, and the notebook's search/provenance/return affordances.

What this does NOT prove: that a live backend is serving these rows right now. It proves the
renderer honours what it is served, including the empty, loading, failed and stale cases, and that
the exact-block return is carried in the notebook's own `source_ref` rather than invented from the
chat transcript.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import (
    COMPLETE_BLOCKS,
    SDK_STUB,
    _desktop_node_modules,
    block,
    document,
)

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import {
  FieldNotesStrip,
  LessonDocumentView,
  NotebookView,
  blockSaveExcerpt,
  notebookSourceRef,
  readNotebookRef,
  stripExcerpt
} from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const index = {}
for (const source of payload.sources || []) index[source.source_id] = source

let output
if (payload.kind === 'document') {
  output = renderToStaticMarkup(
    React.createElement(LessonDocumentView, {
      document: payload.document,
      view: payload.view,
      sources: index,
      checkSlot: null,
      onSaveBlock: () => {}
    })
  )
} else if (payload.kind === 'document-no-save') {
  output = renderToStaticMarkup(
    React.createElement(LessonDocumentView, {
      document: payload.document,
      view: payload.view,
      sources: index,
      checkSlot: null
    })
  )
} else if (payload.kind === 'strip') {
  output = renderToStaticMarkup(
    React.createElement(FieldNotesStrip, {
      notes: payload.notes,
      courseTitle: payload.courseTitle || null,
      current: payload.current || null,
      stale: Boolean(payload.stale),
      onOpenSection: () => {},
      onShowNotebook: () => {},
      onRetry: () => {}
    })
  )
} else if (payload.kind === 'notebook') {
  output = renderToStaticMarkup(
    React.createElement(NotebookView, {
      row: payload.row,
      notebooks: payload.notebooks,
      implemented: new Set(['notebook.update', 'notebook.delete', 'notebook.save', 'artifact.get']),
      onOpenSection: () => {},
      onChanged: () => {},
      sections: payload.sections || []
    })
  )
} else if (payload.kind === 'summary') {
  output = JSON.stringify({
    plain: stripExcerpt({ excerpt: payload.excerpt }),
    clippedLength: stripExcerpt({ excerpt: 'x'.repeat(400) }).length
  })
} else if (payload.kind === 'ref') {
  const seed = payload.seed
  output = JSON.stringify({
    encoded: notebookSourceRef(seed),
    decoded: readNotebookRef(notebookSourceRef(seed)),
    legacy: readNotebookRef(payload.legacy || null),
    excerpt: payload.block ? blockSaveExcerpt(payload.block, payload.checkLabels || [], payload.media || null) : null
  })
} else {
  throw new Error('unknown payload kind ' + payload.kind)
}
process.stdout.write(output)
"""

ENTRY_ARTIFACT = {
    "entry_id": "nbt_00000000000000000000000000000001",
    "enrollment_id": "enr_0123456789abcdef",
    "objective_id": "obj_0123456789abcdef",
    "lesson_run_id": "run_1",
    "kind": "artifact",
    "excerpt": "A bow is lower than a nod.",
    "note": "Remember the waist bend.",
    "tags": ["register", "politeness"],
    "source_ref": json.dumps(
        {"block": "blk_explain001", "artifact": "art_0000000000000001", "sources": ["src_affection01"]}
    ),
    "created_at": "2026-11-06T12:00:00.000000+00:00",
    "updated_at": "2026-11-06T12:00:00.000000+00:00",
    "revision": 0,
}

ENTRY_PLAIN = {
    **ENTRY_ARTIFACT,
    "entry_id": "nbt_00000000000000000000000000000002",
    "kind": "lesson_segment",
    "excerpt": "Older saved line.",
    "note": None,
    "source_ref": "src_affection01",
    "created_at": "2026-11-05T09:00:00.000000+00:00",
}


class FieldNotesRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-field-notes-")
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
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}), encoding="utf-8"
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

    def doc(self, *, view: str = "textbook") -> dict:
        return {
            "kind": "document",
            "document": document(guided=True, blocks=COMPLETE_BLOCKS, check_id="chk_0123456789abcdef"),
            "view": view,
            "sources": [{"source_id": "src_affection01", "title": "Affection and register — field notes"}],
        }

    # -- Save from a teaching segment ---------------------------------------------------------
    def test_every_block_offers_a_save_action_in_every_view(self) -> None:
        for view in ("textbook", "guided", "field_quest"):
            with self.subTest(view=view):
                html = self.render(self.dict_doc(view))
                saves = re.findall(r'data-cb-block-save="(blk_[^"]+)"', html)
                self.assertTrue(saves, f"{view} rendered no save affordance")
                self.assertEqual(len(saves), len(set(saves)), "a block offered the save twice")
                self.assertIn("Save to notebook", html)

    def dict_doc(self, view: str) -> dict:
        payload = self.doc(view=view)
        payload["document"]["views"]["field_quest"] = True
        return payload

    def test_media_child_gets_its_own_save_action(self) -> None:
        media_block = block(
            "blk_media00001",
            "explain",
            "The bow",
            short="Short.",
            deep="Deep.",
            media=[
                {
                    "kind": "visual",
                    "role": "schematic",
                    "artifact_id": "art_0000000000000001",
                    "purpose": "Show the angle",
                    "text_equivalent": "A bow is lower than a nod.",
                    "label": "Bow angle",
                }
            ],
            source_ids=["src_affection01"],
        )
        payload = {
            "kind": "document",
            "document": document(guided=True, blocks=[media_block], check_id=None),
            "view": "textbook",
            "sources": [{"source_id": "src_affection01", "title": "Affection and register — field notes"}],
        }
        html = self.render(payload)
        self.assertEqual(html.count('data-cb-block-save="blk_media00001"'), 1)
        self.assertIn("Save visual", html)

    def test_no_save_affordance_when_the_backend_cannot_save(self) -> None:
        payload = self.doc()
        payload["kind"] = "document-no-save"
        html = self.render(payload)
        self.assertNotIn("data-cb-block-save", html)

    # -- Provenance ---------------------------------------------------------------------------
    def test_the_saved_ref_carries_block_artifact_and_sources(self) -> None:
        out = json.loads(
            self.render(
                {
                    "kind": "ref",
                    "seed": {"block_id": "blk_explain001", "artifact_id": "art_1", "source_ids": ["src_a", "src_b"]},
                }
            )
        )
        self.assertEqual(out["decoded"]["block_id"], "blk_explain001")
        self.assertEqual(out["decoded"]["artifact_id"], "art_1")
        self.assertEqual(out["decoded"]["source_ids"], ["src_a", "src_b"])

    def test_older_bare_source_refs_still_read(self) -> None:
        out = json.loads(self.render({"kind": "ref", "seed": {}, "legacy": "src_affection01"}))
        self.assertEqual(out["decoded"], {"block_id": None, "artifact_id": None, "source_ids": [], "check_id": None, "legacy": None})
        self.assertEqual(out["legacy"]["legacy"], "src_affection01")

    def test_the_excerpt_is_the_documents_own_text(self) -> None:
        out = json.loads(
            self.render(
                {
                    "kind": "ref",
                    "seed": {},
                    "block": {"id": "blk_1", "deep": "Deep prose.", "short": "Short.", "headline": "H"},
                    "checkLabels": [],
                }
            )
        )
        self.assertEqual(out["excerpt"], "Deep prose.")

    def test_the_strip_summarises_markdown_without_rendering_it(self) -> None:
        out = json.loads(
            self.render(
                {
                    "kind": "summary",
                    "excerpt": "## The four lines\n\n| friend | casual | 好きだよ |\n\n**Bold** and `code`.",
                }
            )
        )
        self.assertNotIn("#", out["plain"])
        self.assertNotIn("|", out["plain"])
        self.assertNotIn("**", out["plain"])
        self.assertIn("The four lines", out["plain"])
        self.assertLessEqual(out["clippedLength"], 240)

    # -- The Field Notes strip ----------------------------------------------------------------
    def notes(self, status: str, *, entries: list[dict] | None = None, error: dict | None = None) -> dict:
        return {
            "status": status,
            "data": {"entries": entries} if entries is not None else None,
            "error": error,
            "reload": None,
        }

    def strip(self, payload: dict) -> str:
        return self.render(
            {
                "kind": "strip",
                "notes": payload,
                "courseTitle": "Japanese affection (L0)",
                "current": {"objective_id": "obj_0123456789abcdef", "title": "Affection and register"},
            }
        )

    def test_the_strip_shows_saved_moments_with_a_route_back(self) -> None:
        html = self.strip(self.notes("ready", entries=[ENTRY_ARTIFACT]))
        self.assertIn('data-cb-field-notes="ready"', html)
        self.assertIn("A bow is lower than a nod.", html)
        self.assertIn("Remember the waist bend.", html)
        self.assertIn("Japanese affection (L0)", html)
        self.assertIn("Open in textbook", html)
        self.assertEqual(html.count('data-cb-field-note="nbt_'), 1)

    def test_the_strip_is_capped_and_says_how_many_more(self) -> None:
        entries = [dict(ENTRY_ARTIFACT, entry_id=f"nbt_{index:032d}") for index in range(6)]
        html = self.strip(self.notes("ready", entries=entries))
        self.assertEqual(html.count('data-cb-field-note="'), 4)
        self.assertIn("6 saved", html)
        self.assertIn("showing the last 4", html)

    def test_an_empty_strip_names_the_save_surfaces(self) -> None:
        html = self.strip(self.notes("ready", entries=[]))
        self.assertIn('data-cb-field-notes="ready"', html)
        self.assertIn("Save an explanation, visual or quiz moment and it will appear here.", html)
        self.assertIn("Go to the current lesson", html)
        self.assertNotIn("data-cb-field-note=", html)

    def test_a_failed_strip_shows_the_error_and_never_an_empty_state(self) -> None:
        html = self.strip(self.notes("error", error={"code": "HOST_UNAVAILABLE", "message": "no answer"}))
        self.assertIn('data-cb-field-notes="error"', html)
        self.assertIn("HOST_UNAVAILABLE", html)
        self.assertIn("Try again", html)
        self.assertNotIn("Save an explanation, visual or quiz moment", html)

    def test_a_loading_strip_says_it_is_reading(self) -> None:
        html = self.strip(self.notes("loading"))
        self.assertIn('data-cb-field-notes="loading"', html)
        self.assertIn("Reading your field notes", html)

    def test_a_stale_strip_says_saves_are_paused(self) -> None:
        html = self.render(
            {
                "kind": "strip",
                "notes": self.notes("ready", entries=[ENTRY_ARTIFACT]),
                "courseTitle": "Japanese affection (L0)",
                "current": None,
                "stale": True,
            }
        )
        self.assertIn("A save or an edit is paused until the desk reconnects.", html)

    # -- Notebook surface ---------------------------------------------------------------------
    def notebook(self, entries: list[dict]) -> str:
        return self.render(
            {
                "kind": "notebook",
                "row": {
                    "enrollment_id": "enr_0123456789abcdef",
                    "title": "Japanese affection (L0)",
                    "evidence_summary": {"current_objective_id": "obj_0123456789abcdef"},
                },
                "notebooks": {"entries": entries},
                "sections": [
                    {"objective_id": "obj_0123456789abcdef", "title": "Affection and register", "ordinal": 1}
                ],
            }
        )

    def test_the_notebook_shows_search_section_provenance_and_return(self) -> None:
        html = self.notebook([ENTRY_ARTIFACT, ENTRY_PLAIN])
        self.assertIn("Section · Affection and register", html)
        self.assertIn("Source · src_affection01", html)
        self.assertIn("Course · Japanese affection (L0)", html)
        self.assertIn("Open in textbook", html)
        self.assertIn("Continue from here", html)
        self.assertIn("Edit note and tags", html)
        self.assertIn("Remove from notebook", html)

    def test_only_a_media_entry_offers_play_or_view(self) -> None:
        html = self.notebook([ENTRY_ARTIFACT, ENTRY_PLAIN])
        self.assertEqual(html.count("Play/view media"), 1)

    def test_an_empty_notebook_says_what_to_save(self) -> None:
        html = self.notebook([])
        self.assertIn("Save an explanation, visual or quiz moment and it will appear here.", html)
        self.assertIn("Go to the current lesson", html)


if __name__ == "__main__":
    unittest.main()
