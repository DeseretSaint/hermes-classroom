"""The Desktop renders a procedure lesson from the document's typed facts, not from prose.

The fixture is the real validated head-gasket document from `test_procedure_document`; this test
renders the shipped `desktop/plugin.js` through React's server renderer with a stub
`@hermes/plugin-sdk`. It proves placement and labelling: the header, the "do not proceed"
callout, the numbered step cards referencing the document's own blocks, the deterministic
schematic rows, the single verification checklist and the source card with its permission.

What it does NOT prove: that a live backend authors `procedure` today. It proves the renderer
honours the document it is served, and refuses to invent anything the document does not carry.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import PLUGIN_JS, SDK_STUB, _desktop_node_modules
from tests.test_procedure_document import (
    CHECK_ID,
    SCHEMATIC_SOURCE_ID,
    SOURCE_ID,
    head_gasket_blocks,
    head_gasket_document,
)

HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { LessonDocumentView } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const index = {}
for (const source of payload.sources || []) index[source.source_id] = source
const checkNode = React.createElement('div', { id: 'cb-check-node' }, 'CHECK-NODE')
const html = renderToStaticMarkup(
  React.createElement(LessonDocumentView, {
    document: payload.document,
    view: payload.view || 'textbook',
    sources: index,
    checkSlot: payload.withCheck === false ? null : checkNode
  })
)
process.stdout.write(html)
"""

SOURCES = [
    {
        "source_id": SOURCE_ID,
        "title": "Workshop manual — 1.8 L cylinder head replacement",
        "url": "https://example.test/manual/head-gasket",
        "publisher": "Workshop Manuals",
        "source_type": "manual",
        "support_status": "supported",
    }
]


class ProcedureRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-procedure-")
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

    def render(self, doc: dict, *, view: str = "textbook", with_check: bool = True,
               sources: list[dict] | None = None) -> str:
        case = self.root / "case.json"
        case.write_text(
            json.dumps(
                {
                    "document": doc,
                    "view": view,
                    "withCheck": with_check,
                    "sources": sources if sources is not None else SOURCES,
                }
            ),
            encoding="utf-8",
        )
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        return result.stdout

    # -- the layout ---------------------------------------------------------------------------
    def test_procedure_document_renders_every_section(self) -> None:
        html = self.render(head_gasket_document())
        self.assertIn('data-cb-lesson-view="procedure"', html)
        self.assertIn("data-cb-procedure-header", html)
        self.assertIn('data-cb-procedure-tools="4"', html)
        self.assertIn('data-cb-procedure-parts="3"', html)
        self.assertIn("Torque wrench 5–25 Nm", html)
        self.assertIn("Head gasket", html)

    def test_hazard_callout_is_distinct_and_names_the_stop_condition(self) -> None:
        html = self.render(head_gasket_document())
        self.assertIn('data-cb-procedure-hazard', html)
        self.assertIn('role="note"', html)
        self.assertIn("Do not proceed", html)
        self.assertIn("Coolant is toxic and stays hot for hours after the engine stops.", html)
        self.assertIn("Stop if:", html)
        self.assertIn("Stop and do not proceed if any bolt will not reach the specified torque", html)

    def test_numbered_steps_reference_the_documents_own_blocks(self) -> None:
        html = self.render(head_gasket_document())
        self.assertIn('data-cb-procedure-steps="5"', html)
        for number in range(1, 6):
            self.assertIn(f'data-cb-procedure-step="{number}"', html)
        for block_id in (
            "blk_gasket_orient1",
            "blk_gasket_explain1",
            "blk_gasket_step0001",
            "blk_gasket_step0002",
            "blk_gasket_recap001",
        ):
            self.assertIn(f'data-cb-block="{block_id}"', html)
        self.assertIn('data-cb-procedure-step-check="blk_gasket_step0001"', html)
        self.assertIn("Gasket tab faces the front of the engine.", html)
        # Step prose is the block's authored `deep`; the action is never re-summarised here.
        self.assertIn("Scrape the block deck with a plastic scraper", html)
        self.assertNotIn("Clean the deck; fit the gasket dry, tab to the front.", html)

    def test_the_section_check_is_printed_exactly_once_as_the_verification_checklist(self) -> None:
        html = self.render(head_gasket_document())
        self.assertEqual(html.count("CHECK-NODE"), 1)
        self.assertIn('data-cb-block-check="blk_gasket_step0001"', html)
        self.assertIn("Verification checklist", html)
        self.assertIn('data-cb-procedure-verification="attached"', html)

    def test_verification_checklist_survives_an_unattached_check(self) -> None:
        doc = head_gasket_document()
        doc = dict(doc)
        doc["blocks"] = [dict(block, check_id=None) for block in doc["blocks"]]
        doc["check_id"] = None
        doc["procedure"] = dict(doc["procedure"])
        html = self.render(doc)
        self.assertEqual(html.count("CHECK-NODE"), 0)
        self.assertNotIn("data-cb-procedure-verification", html)

    def test_schematic_renders_deterministic_rows_from_structured_facts(self) -> None:
        html = self.render(head_gasket_document())
        self.assertIn('data-cb-procedure-schematic', html)
        self.assertIn('data-cb-procedure-rows="4"', html)
        self.assertIn("Head bolt torque sequence", html)
        self.assertIn("Bolt 1", html)
        self.assertIn("40 Nm", html)
        self.assertIn("Drawing from the steps below", html)
        self.assertIn(f'data-cb-procedure-schematic-source="{SCHEMATIC_SOURCE_ID}"', html)
        self.assertIn("Workshop manual — 1.8 L cylinder head replacement", html)

    def test_source_card_prints_the_permission_status(self) -> None:
        html = self.render(head_gasket_document())
        self.assertIn(f'data-cb-procedure-source="{SOURCE_ID}"', html)
        self.assertIn("Licensed for this course", html)
        self.assertIn("https://example.test/manual/head-gasket", html)

    def test_illustration_is_labelled_context_not_a_specification(self) -> None:
        doc = head_gasket_document()
        blocks = [dict(block, media=[dict(item) for item in block["media"]]) for block in doc["blocks"]]
        blocks[0]["media"] = [
            {
                "kind": "visual",
                "role": "illustration",
                "artifact_id": "art_context_0001",
                "purpose": "Workshop bench context",
                "text_equivalent": "A workbench with a head gasket and a torque wrench in view.",
                "label": "Illustration — generated for context only.",
                "degraded": False,
                "reason": None,
            }
        ]
        doc["blocks"] = blocks
        html = self.render(doc)
        self.assertIn('data-cb-procedure-media="illustration"', html)
        self.assertIn(
            "Context illustration — not a specification, measurement, sequence or safety authority.",
            html,
        )

    def test_schematic_media_carries_its_deterministic_label(self) -> None:
        html = self.render(head_gasket_document())
        self.assertIn('data-cb-procedure-media="schematic"', html)
        self.assertIn("Drawing made from the steps below.", html)

    def test_a_block_outside_the_step_list_is_still_taught(self) -> None:
        doc = head_gasket_document()
        doc = dict(doc)
        doc["procedure"] = dict(doc["procedure"])
        doc["procedure"]["steps"] = [step for step in doc["procedure"]["steps"]
                                     if step["block_id"] != "blk_gasket_recap001"]
        html = self.render(doc)
        self.assertIn('data-cb-procedure-unplaced="1"', html)
        self.assertIn("Also in this lesson", html)
        self.assertIn(
            "Re-check the sequence, confirm every connector is seated, refill coolant",
            html,
        )

    def test_a_document_without_a_procedure_keeps_the_flat_textbook(self) -> None:
        doc = head_gasket_document()
        doc = dict(doc)
        doc.pop("procedure", None)
        html = self.render(doc)
        self.assertIn('data-cb-lesson-view="textbook"', html)
        self.assertNotIn("data-cb-procedure", html)
        self.assertNotIn("Do not proceed", html)

    def test_guided_view_keeps_its_single_block_lens(self) -> None:
        html = self.render(head_gasket_document(), view="guided")
        self.assertIn('data-cb-lesson-view="guided"', html)
        self.assertNotIn("data-cb-procedure-header", html)
        self.assertIn("Step 1 of 5", html)
        self.assertEqual(html.count("data-cb-block="), 1)

    def test_no_steps_is_an_empty_state_not_an_empty_layout(self) -> None:
        doc = head_gasket_document()
        doc = dict(doc)
        doc["procedure"] = dict(doc["procedure"], steps=[])
        html = self.render(doc)
        self.assertIn('data-cb-procedure-steps="0"', html)
        self.assertIn("Also in this lesson", html)


if __name__ == "__main__":
    unittest.main()
