"""H-115-D1 (renderer half): a pack source URL is a link only when it is absolute http(s).

The backend refuses a non-http(s) ``source.url`` at every pre-write/read seam
(``coursebook/packs.py::is_http_url``); this is the defence-in-depth half. A pack adopted
*before* that rule can still reach the Desktop, and four surfaces used to pass whatever
string arrived straight into ``href``. ``javascript:``, ``data:``, ``file:`` and
scheme-relative values were all confirmed to persist and preview as links in H-115.

The four pack-data sinks, all guarded by one helper (``safeHttpHref``):

* ``ProcedureSourceCard`` (``meta.url``) — 80-components.js
* ``SourceProvenanceCard`` (``source.url``) — 90-course.js
* the homework sheet's source list (``task.sources[].url``) — 95-studio.js
* the Workshop detail's source list (``item.sources[].url``) — 96-workshop.js

**Scope fence.** Only pack data. Host-issued relative artifact routes
(``artifact.download.url``, ``facts.download.url``) keep their own ``href`` untouched: they are
backend paths the user's own host minted, not strings a pack author wrote.

**Deliberate residual.** Loopback and link-local http hosts still pass the scheme rule, because
this rule is about link injection, not SSRF — that filter belongs to the ``source.revalidate``
fetch seam. Nothing here claims a hostile URL cannot be *fetched*; it claims it cannot be *linked*.

What this does NOT prove: that the live Electron window paints the fallback, or anything about
navigating a ``data:``/``file:`` URL under the runtime's sandbox. No XSS is claimed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import PLUGIN_JS, SDK_STUB, _desktop_node_modules
from tests.test_desktop_procedure import SOURCES as PROCEDURE_SOURCES
from tests.test_procedure_document import SOURCE_ID, head_gasket_document

HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { LessonDocumentView, SourceProvenanceCard } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const render = (node) => renderToStaticMarkup(React.createElement('div', null, node))
const out = {}

payload.cases.forEach((one) => {
  out['card:' + one.name] = render(
    React.createElement(SourceProvenanceCard, {
      source: {
        source_id: 'src_0123456789abcdef',
        title: 'Kitchen chemistry notes',
        url: one.url,
        support_status: 'unassessed',
        excerpt_state: 'missing'
      }
    })
  )
  const index = {}
  index[payload.procedure.source_id] = Object.assign({}, payload.procedure.source, { url: one.url })
  out['procedure:' + one.name] = render(
    React.createElement(LessonDocumentView, {
      document: payload.procedure.document,
      view: 'textbook',
      sources: index,
      checkSlot: null
    })
  )
})

process.stdout.write(JSON.stringify(out))
"""

CASES = [{"name": "plain", "url": "https://example.test/notes"}]

HOSTILE_URLS = [
    "javascript:alert(1)",
    "data:text/html,x",
    "file:///etc/passwd",
    "//169.254.169.254/",
    "chapter-1.md",
]

HELPER_CASES = [
    "javascript:alert(1)",
    "JavaScript:alert(1)",
    "data:text/html,x",
    "file:///etc/passwd",
    "//169.254.169.254/",
    "chapter-1.md",
    "",
    None,
    " http://example.org/x ",
    "https://example.org/x",
]
HELPER_EXPECTED = [
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    "http://example.org/x",
    "https://example.org/x",
]


def _function_source(text: str, name: str) -> str:
    """Return the balanced ``function <name>(...) { ... }`` block from module source."""
    marker = f"function {name}("
    start = text.find(marker)
    if start < 0:
        raise AssertionError(f"{name} is not defined in desktop/plugin.js")
    brace = text.find("{", start)
    if brace < 0:
        raise AssertionError(f"{name} has no body")
    depth = 0
    index = brace
    quote = None
    while index < len(text):
        char = text[index]
        if quote is not None:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in "'\"`":
            quote = char
            index += 1
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
        index += 1
    raise AssertionError(f"unbalanced body for {name}")


class SafeHttpHrefTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = PLUGIN_JS.read_text(encoding="utf-8")
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to evaluate the shipped helper")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-source-urls-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(cls.text, encoding="utf-8")
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

    # -- the shipped helper --------------------------------------------------------------------
    def test_helper_refuses_non_http_schemes(self) -> None:
        """Evaluate the shipped helper: only absolute http(s) with a host survives."""
        source = _function_source(self.text, "safeHttpHref")
        harness = (
            source
            + "\nconst cases = "
            + json.dumps(HELPER_CASES)
            + "\nprocess.stdout.write(JSON.stringify(cases.map((value) => safeHttpHref(value))))\n"
        )
        with tempfile.TemporaryDirectory(prefix="coursebook-source-urls-helper-") as tmp:
            script = Path(tmp) / "harness.mjs"
            script.write_text(harness, encoding="utf-8")
            result = subprocess.run(
                ["node", str(script)], capture_output=True, text=True, timeout=60
            )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertEqual(json.loads(result.stdout), HELPER_EXPECTED)

    # -- every pack-data sink reads the guard ---------------------------------------------------
    def test_every_pack_data_anchor_reads_the_guarded_value(self) -> None:
        text = self.text
        self.assertTrue(
            "function safeHttpHref(" in text, "desktop/plugin.js has no safeHttpHref helper"
        )

        # No pack-data URL reaches a raw href on any surface.
        self.assertNotIn("href: source.url", text)
        self.assertNotIn("href: meta.url", text)

        # The four call sites, each with its own text fallback next to it.
        self.assertIn("const metaHref = safeHttpHref(meta && meta.url)", text)
        self.assertIn("const sourceHref = safeHttpHref(source && source.url)", text)
        self.assertEqual(
            text.count("const sourceHref = safeHttpHref(source.url)"),
            2,
            "expected the homework sheet and the Workshop source list to guard their URLs",
        )

        windows = {
            "procedure source card": "const metaHref = safeHttpHref(meta && meta.url)",
            "course source card": "const sourceHref = safeHttpHref(source && source.url)",
            "homework sheet sources": "children: task.sources.length === 1 ? 'Source · ' : 'Sources · '",
            "workshop sources": ": jsx('span', { children: source.title })",
        }
        anchors = {
            "procedure source card": "href: metaHref",
            "course source card": "'data-cb-source-open'",
            "homework sheet sources": ": jsx('span', { children: label }, 'link')",
            "workshop sources": ": jsx('span', { children: source.title })",
        }
        for name, marker in windows.items():
            offset = text.find(marker)
            self.assertGreaterEqual(offset, 0, f"{name} is not in the shipped module")
            window = text[max(0, offset - 900):offset + 4200]
            self.assertIn("safeHttpHref(", window, f"{name} does not read the guard")
            self.assertIn(anchors[name], window, f"{name} has no guarded anchor")

    def test_host_issued_artifact_routes_are_untouched(self) -> None:
        """The scope fence: a backend-minted relative route is not pack data."""
        text = self.text
        self.assertEqual(text.count("href: artifact.download.url"), 3)
        self.assertEqual(text.count("href: facts.download.url"), 1)
        self.assertNotIn("safeHttpHref(artifact", text)
        self.assertNotIn("safeHttpHref(facts", text)

    # -- what a hostile value actually paints ---------------------------------------------------
    def render_cases(self, cases: list[dict]) -> dict:
        procedure = {
            "source_id": SOURCE_ID,
            "source": dict(PROCEDURE_SOURCES[0]),
            "document": head_gasket_document(),
        }
        case = self.root / "case.json"
        case.write_text(
            json.dumps({"cases": cases, "procedure": procedure}), encoding="utf-8"
        )
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        return json.loads(result.stdout)

    def test_an_absolute_http_source_url_is_a_link(self) -> None:
        html = self.render_cases(CASES)
        card = html["card:plain"]
        self.assertIn('href="https://example.test/notes"', card)
        self.assertIn("Open source", card)
        procedure = html["procedure:plain"]
        self.assertIn('href="https://example.test/notes"', procedure)

    def test_a_non_http_source_url_is_text_on_every_surface(self) -> None:
        cases = [{"name": f"hostile{index}", "url": url} for index, url in enumerate(HOSTILE_URLS)]
        html = self.render_cases(cases)
        for case in cases:
            card = html[f"card:{case['name']}"]
            self.assertNotIn("<a ", card, f"{case['url']} still paints an anchor on the source card")
            self.assertNotIn("Open source", card, f"{case['url']} still offers an open link")

            procedure = html[f"procedure:{case['name']}"]
            self.assertNotIn("<a ", procedure, f"{case['url']} still paints an anchor on the procedure source card")
            self.assertNotIn("href=\"javascript", procedure)
            self.assertNotIn("href=\"data:", procedure)
            self.assertNotIn("href=\"file:", procedure)
            # The refusal is visible, not silent: the value is still on screen for review.
            self.assertIn("Kitchen chemistry notes", card)


if __name__ == "__main__":
    unittest.main()
