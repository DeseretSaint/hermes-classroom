"""The Workshop favourite control must state 'Saved' in legible type, in light and in dark.

The failure this pins: the selected state recoloured the word and the star glyph to `lamp` on
`paper` (#e8a93a on #f7f1e4 = 1.83:1 light, #efc06b on #131210 dark). The token contract gates
`lamp` as a *fill* (1.25 against paper) and separately gates `on-lamp` on `lamp` at 4.5, so the
only painted claim here is text on a chip: it is a 4.5:1 AA control label, not a fill edge.

What this measures, and how. `WorkshopCard` is the shipped component that owns the control; it is
rendered through real React inside the shipped `cbScopeStyle(mode)` scope for both modes. jsdom
does not compute CSS custom properties, so the test resolves each `var(--cb-*)` the element
declares against the declaration the same scope emits, and asserts that declaration is one of the
shipped `CB_TOKENS[mode]` values before computing WCAG contrast. That is a measurement of the
rendered markup plus the shipped token table, not a browser paint and not a live Desktop window
(owner directive 2026-11-12: no live window, rig backend or CDP probe for shipping evidence).

What this does not prove: that the host paints the scope on a live route, and that the Discover
surface mounts this control at all. `WorkshopView`'s Discover tab now renders the v3 pack cards,
which carry no favourite affordance; the chip is reachable through `WorkshopShelf`/`WorkshopCard`
and is still shipped and still rendered by the H-196 frame audit. The contrast gate is proven on
the rendered component, and the reachability gap is recorded on the card rather than papered over.

Fails at HEAD: `lamp` on `paper` is 1.83:1 and the source pin still finds the accent word colour.
Passes after: `on-lamp` on `lamp` (8.65:1 light, 11.2:1 dark) and the ink word colour is gone.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.cb_source_scope import PLUGIN_JS, ROOT
from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules
from tests.test_desktop_tokens import contrast_ratio, shipped_tokens

SEGMENT = ROOT / "desktop" / "src" / "96-workshop.js"
AA_FLOOR = 4.5
FAVORITE = "data-cb-workshop-favorite"

HARNESS = r"""
import { JSDOM } from 'jsdom'

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://127.0.0.1/' })
globalThis.window = dom.window
globalThis.document = dom.window.document
Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator })
globalThis.HTMLElement = dom.window.HTMLElement
globalThis.Node = dom.window.Node
globalThis.Event = dom.window.Event
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })

const React = (await import('react')).default
const { renderToStaticMarkup } = await import('react-dom/server')
const mod = await import('./plugin.js')

const ITEM = {
  pack_id: 'japanese-affection-context-l0',
  title: 'Japanese: the two ways to say it',
  subtitle: 'Choose the register that fits the person you are speaking to.',
  outcome: 'Choose the Japanese expression that fits the person you are speaking to, and say why it fits.',
  pack_version: '2.2.0',
  categories: ['Languages'],
  section_count: 6,
  objective_count: 4,
  minutes: 40,
  featured: true,
  will_not_teach: [],
  creator_note: '',
  sections: [{ title: 'Two ways to say it', objective: 'Pick the register', minutes: 10 }],
  sources: [],
  contributors: [],
  integrity: { hashes_match: true, file_count: 6, expanded_bytes: 4096 },
  license: { id: 'CC0-1.0', note: '', redistribution: 'allowed' },
  attribution: '',
  content_hash: 'sha256:1111111111111111111111111111111111111111111111111111111111111111',
  recipe: 'japanese',
  locale: 'ja-JP',
  level_label: 'CEFR A1',
  changelog: [],
  trust_labels: ['integrity_verified'],
  validated: true,
  cover: { kind: 'typographic', artifact_id: null, alt: null, caption: null },
  installed: null
}

// jsdom parses a shorthand the same way the DOM does, and `background: var(--cb-paper)` does not
// expand in jsdom, so the declarations are read from the authored style attribute instead.
const declarations = (node) => {
  const out = {}
  for (const part of String(node.getAttribute('style') || '').split(';')) {
    const cut = part.indexOf(':')
    if (cut < 0) continue
    out[part.slice(0, cut).trim().toLowerCase()] = part.slice(cut + 1).trim()
  }
  return out
}

const card = (favorite) =>
  React.createElement(mod.WorkshopCard, {
    item: ITEM,
    motion: { reduced: true },
    index: 0,
    shelfKey: 'Languages',
    onOpen: () => {},
    onInstall: () => {},
    busy: false,
    favorite,
    onFavorite: () => {},
    userCategory: null,
    layout: mod.cbLayoutFor(1049)
  })

const readings = {}
for (const mode of ['light', 'dark']) {
  const scope = mod.cbScopeStyle(mode)
  const html = renderToStaticMarkup(
    React.createElement(
      'div',
      { 'data-cb-scope': mode, style: scope },
      React.createElement(
        'div',
        null,
        card(false),
        card(true)
      )
    )
  )
  const parsed = new JSDOM(html).window.document
  const controls = [...parsed.querySelectorAll('[data-cb-workshop-favorite]')].map((node) => ({
    state: node.getAttribute('data-cb-workshop-favorite'),
    text: (node.textContent || '').trim(),
    ariaPressed: node.getAttribute('aria-pressed'),
    style: declarations(node)
  }))
  readings[mode] = { scope, controls }
}

process.stdout.write(JSON.stringify(readings))
"""


def _scope_declarations(scope: dict) -> dict:
    """The custom properties the route scope actually paints, as `name -> value`."""
    declarations = {}
    for key, value in scope.items():
        if isinstance(key, str) and key.startswith("--cb-"):
            declarations[key[len("--cb-"):]] = str(value).strip()
    return declarations


def _resolve(value: str, declarations: dict, tokens: dict, mode: str, where: str) -> str:
    """Resolve one authored custom-property reference to the hex the shipped table paints."""
    match = re.fullmatch(r"var\(--cb-([a-z0-9-]+)\)", value.strip())
    if match is None:
        raise AssertionError(f"{mode}: {where} is {value!r}, which is not a token reference")
    name = match.group(1)
    if name not in tokens:
        raise AssertionError(f"{mode}: {where} names --cb-{name}, which is not a shipped token")
    painted = declarations.get(name)
    if painted is None or painted != tokens[name]:
        raise AssertionError(
            f"{mode}: the scope paints --cb-{name} as {painted!r}, not the shipped {tokens[name]!r}"
        )
    return str(painted)


class WorkshopFavoriteSourceTest(unittest.TestCase):
    """The mechanism, pinned in the segment a card can edit without regenerating the module."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SEGMENT.read_text(encoding="utf-8")
        start = cls.source.index("'data-cb-workshop-favorite'")
        end = cls.source.index("}, 'favorite')", start)
        cls.block = cls.source[start:end]

    def test_the_saved_word_is_painted_from_on_lamp(self) -> None:
        self.assertIn("background: favorite ? 'var(--cb-lamp)' : 'var(--cb-paper)'", self.block)
        self.assertIn("color: favorite ? 'var(--cb-on-lamp)' : 'var(--cb-ink-soft)'", self.block)

    def test_the_accent_is_never_the_word(self) -> None:
        self.assertNotIn(
            "color: favorite ? 'var(--cb-lamp)'",
            self.block,
            "the saved state paints its own label in the accent; lamp is a fill, never text",
        )
        self.assertNotRegex(
            self.block,
            r"color:\s*'?var\(--cb-lamp\)",
            "a lamp-coloured text run in the favourite control",
        )

    def test_the_state_is_still_announced_to_assistive_technology(self) -> None:
        self.assertIn("'aria-pressed': favorite ? 'true' : 'false'", self.block)


class WorkshopFavoriteRenderTest(unittest.TestCase):
    """The rendered component, measured against the shipped token table in both modes."""

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-favorite-contrast-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
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
        completed = subprocess.run(
            ["node", "harness.mjs"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if completed.returncode != 0:
            raise AssertionError(f"the render harness failed:\n{completed.stderr}")
        cls.readings = json.loads(completed.stdout)
        cls.tokens, _, _ = shipped_tokens()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def _control(self, mode: str, state: str) -> dict:
        controls = [row for row in self.readings[mode]["controls"] if row["state"] == state]
        self.assertEqual(len(controls), 1, f"{mode}: expected one {state!r} favourite control")
        return controls[0]

    def _pair(self, mode: str, state: str) -> tuple[str, str, str, str]:
        control = self._control(mode, state)
        declarations = _scope_declarations(self.readings[mode]["scope"])
        color = _resolve(control["style"].get("color", ""), declarations, self.tokens[mode], mode, f"{state} colour")
        background = _resolve(
            control["style"].get("background", ""), declarations, self.tokens[mode], mode, f"{state} background"
        )
        return color, background, control["text"], control["ariaPressed"]

    def test_the_saved_state_is_legible_in_light_and_dark(self) -> None:
        for mode in ("light", "dark"):
            with self.subTest(mode=mode):
                color, background, text, pressed = self._pair(mode, "on")
                self.assertEqual(text, "Saved")
                self.assertEqual(pressed, "true")
                ratio = contrast_ratio(color, background)
                self.assertGreaterEqual(
                    round(ratio, 2),
                    AA_FLOOR,
                    f"{mode}: the saved word is {color} on {background} at {ratio:.2f}:1, "
                    f"below the {AA_FLOOR}:1 caption floor",
                )

    def test_the_saved_state_is_visible_against_the_unsaved_one(self) -> None:
        # A legible label that looks identical to the unsaved one reports nothing. The fill is what
        # carries the state to a sighted reader; aria-pressed carries it to a screen reader.
        for mode in ("light", "dark"):
            with self.subTest(mode=mode):
                _, saved, _, _ = self._pair(mode, "on")
                _, unsaved, text, pressed = self._pair(mode, "off")
                self.assertEqual(text, "Save")
                self.assertEqual(pressed, "false")
                self.assertNotEqual(saved, unsaved, f"{mode}: the saved and unsaved chips share a fill")

    def test_the_unsaved_state_keeps_the_quiet_caption_floor(self) -> None:
        for mode in ("light", "dark"):
            with self.subTest(mode=mode):
                color, background, _, _ = self._pair(mode, "off")
                ratio = contrast_ratio(color, background)
                self.assertGreaterEqual(round(ratio, 2), AA_FLOOR, f"{mode}: {color} on {background} is {ratio:.2f}")


if __name__ == "__main__":
    unittest.main()
