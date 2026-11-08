"""The pane must not reference a component the shipped module never defines (H-135).

`desktop/plugin.js` is one uncompiled ESM module, so a component used in a `jsx()` call is resolved
the moment that branch renders. On local `master` (`bdc9d71` and still `860ce2a`) the pane header
was ``jsx(CbLabel, …)`` with no ``CbLabel`` binding in the file, because the H-84 copy helper only
landed on the `origin/master` line: opening any chat's Coursebook pane threw
``ReferenceError: CbLabel is not defined`` and nothing rendered.

Three checks:

1. **Every capitalised component passed to ``jsx``/``jsxs`` is bound at module scope** — imported,
   or declared with ``function``/``class``/``const``/``let``/``var`` at column 0. This is the
   cheap, always-on half: it fails on the exact commit the defect was found on and names the line.
2. **The detector actually fires.** A synthetic module that uses an undefined component must be
   refused, and the same module with the definition added must be accepted, so check 1 cannot pass
   by scanning nothing.
3. **The registered ``pane`` contribution renders in jsdom** with a stub SDK and a host that
   answers every read the pane makes. One React render is enough: a ``ReferenceError`` at the
   header aborts the whole pane, so "no throw and the header text is present" is the product fact
   the batch of pane-state fixes depends on.

What it does NOT prove: that a live Desktop window paints the pane (that needs the Electron shell
and a real backend), or that the copy inside the pane is correct — only that the module resolves
every component it renders.

Run against another revision's module with ``CB_PLUGIN_JS=/path/to/plugin.js``; the default is the
working tree's ``desktop/plugin.js``.
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

from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = Path(os.environ.get("CB_PLUGIN_JS") or ROOT / "desktop" / "plugin.js")

IMPORT_RE = re.compile(r"^import\s+(?:(\w+)\s*,?\s*)?(?:\{([^}]*)\}|\*\s+as\s+(\w+))?\s*from\s*['\"]", re.M)
DECL_RE = re.compile(
    r"^(?:export\s+)?(?:async\s+)?(?:function\s*\*?|class|const|let|var)\s+([A-Za-z_$][\w$]*)", re.M
)
JSX_RE = re.compile(r"\bjsxs?\(\s*([A-Z][\w$]*)\s*[,)]")


def module_bindings(source: str) -> set[str]:
    """Names bound at module scope: imports plus column-0 declarations."""
    names: set[str] = set()
    for match in IMPORT_RE.finditer(source):
        if match.group(1):
            names.add(match.group(1))
        if match.group(2):
            for piece in match.group(2).split(","):
                piece = piece.strip()
                if piece:
                    names.add(piece.split(" as ")[-1].strip())
        if match.group(3):
            names.add(match.group(3))
    for match in DECL_RE.finditer(source):
        names.add(match.group(1))
    return names


def component_uses(source: str) -> dict[str, list[int]]:
    """Capitalised identifiers used as the jsx/jsxs element type, with their line numbers."""
    uses: dict[str, list[int]] = {}
    for match in JSX_RE.finditer(source):
        line = source.count("\n", 0, match.start(1)) + 1
        uses.setdefault(match.group(1), []).append(line)
    return uses


def unresolved_components(source: str) -> dict[str, list[int]]:
    bound = module_bindings(source)
    return {name: lines for name, lines in component_uses(source).items() if name not in bound}


MOUNT_HARNESS = r"""
import React, { act } from 'react'
import { JSDOM } from 'jsdom'

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://127.0.0.1/',
  pretendToBeVisual: true
})
globalThis.window = dom.window
globalThis.document = dom.window.document
globalThis.HTMLElement = dom.window.HTMLElement
globalThis.Node = dom.window.Node
globalThis.Event = dom.window.Event
globalThis.IS_REACT_ACT_ENVIRONMENT = true

const mod = await import('./plugin.js')
const sdk = await import('@hermes/plugin-sdk')

const fakeRest = async (path) => {
  const base = String(path).split('?')[0]
  if (base === '/rpc') return { ok: false }
  if (base === '/runtime') return { wire_version: 6, implemented_methods: [], single_home_host: false }
  return { skill: null, reason: 'unrelated_session' }
}

let pane = null
try {
  mod.default.register({
    rest: fakeRest,
    register: (contribution) => { if (contribution && contribution.id === 'pane') pane = contribution },
    onDispose: () => {}
  })
} catch (error) {
  process.stdout.write(JSON.stringify({ stage: 'register', threw: true, name: error.name, message: error.message }))
  process.exit(0)
}
if (!pane) {
  process.stdout.write(JSON.stringify({ stage: 'register', threw: false, pane: false }))
  process.exit(0)
}

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))
try {
  // The host places the focused durable chat before the pane renders, exactly like Desktop does.
  sdk.host.state.focusedStoredSessionId = { get: () => 'sess_0123456789abcdef', subscribe: () => () => {} }
  await act(async () => { root.render(React.createElement(pane.render)) })
  await act(async () => { await new Promise((done) => setTimeout(done, 30)) })
  const node = document.getElementById('root')
  const text = (node.textContent || '').replace(/\s+/g, ' ').trim()
  process.stdout.write(JSON.stringify({ stage: 'render', threw: false, text: text.slice(0, 300) }))
} catch (error) {
  process.stdout.write(JSON.stringify({
    stage: 'render',
    threw: true,
    name: error.name,
    message: error.message,
    stack: String(error.stack || '').split('\n').slice(0, 4)
  }))
}
"""


class ComponentBindingSourceTest(unittest.TestCase):
    """Static: a component the module renders must be bound in that same module."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PLUGIN_JS.read_text(encoding="utf-8")

    def test_every_jsx_component_is_bound(self) -> None:
        missing = unresolved_components(self.source)
        if missing:
            detail = "\n".join(
                f"  {name}: used at line(s) {', '.join(str(n) for n in lines[:8])}"
                for name, lines in sorted(missing.items())
            )
            self.fail(
                f"{PLUGIN_JS.name} renders component(s) it never defines — the pane will throw "
                f"ReferenceError the moment that branch runs:\n{detail}"
            )

    def test_the_check_would_catch_an_undefined_component(self) -> None:
        # The detector must fire on the exact defect shape, and stay quiet once the binding lands.
        broken = "function Pane() {\n  return jsx(CbLabel, { children: 'Coursebook' })\n}\n"
        self.assertEqual(unresolved_components(broken), {"CbLabel": [2]})

        fixed = broken + "\nfunction CbLabel({ children }) {\n  return jsx('div', { children })\n}\n"
        self.assertEqual(unresolved_components(fixed), {})

    def test_the_check_reads_a_real_module_not_an_empty_scan(self) -> None:
        # Guard against a scanner that silently matches nothing and therefore always passes.
        uses = component_uses(self.source)
        self.assertGreater(len(uses), 50, "the scanner found almost no jsx components; it is broken")
        self.assertIn("CoursebookPane", uses)


class PaneMountTest(unittest.TestCase):
    """Dynamic: the pane contribution renders instead of throwing."""

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-pane-bindings-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "mount.mjs").write_text(MOUNT_HARNESS, encoding="utf-8")
        node_modules = root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler", "jsdom"):
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

    def mount(self) -> dict:
        result = subprocess.run(
            ["node", str(self.root / "mount.mjs")],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return json.loads(result.stdout)

    def test_the_registered_pane_renders_without_a_reference_error(self) -> None:
        observed = self.mount()
        self.assertFalse(
            observed.get("threw"),
            f"the pane threw {observed.get('name')}: {observed.get('message')} "
            f"(stage {observed.get('stage')})",
        )
        self.assertTrue(observed.get("pane", True), "the plugin registered no pane contribution")
        self.assertIn("Coursebook", observed.get("text", ""))


if __name__ == "__main__":
    unittest.main()
