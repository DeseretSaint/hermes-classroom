"""Ink & Field Notes: the token contract, its contrast floor, and the scoped route shell.

The runtime plugin is one ESM file with no build step and no stylesheet, so the token layer ships
as an embedded JSON table painted onto the Coursebook route root as CSS custom properties. These
tests read the *shipped* module: the table is compared with ``contracts/cb.tokens.v2.json``, WCAG
contrast is computed on the values that actually ship, the file is scanned for colour literals
outside the table, and the shell is rendered through real React at a wide and a 460px viewport.

What this does NOT prove: that the host paints these custom properties anywhere outside the
Coursebook route and pane roots. The scope is the seam, and the scope is asserted, not assumed.
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
    document,
)

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"
CONTRACT = ROOT / "contracts" / "cb.tokens.v2.json"

HARNESS = """
// Globals must be set BEFORE the plugin module (and its SDK stub) evaluate.
globalThis.__CB_TEST_WIDTH__ = process.env.CB_TEST_WIDTH || '1280'
globalThis.__CB_TEST_MODE__ = process.env.CB_TEST_MODE || 'light'

const React = (await import('react')).default
const { renderToStaticMarkup } = await import('react-dom/server')
const mod = await import('./plugin.js')

const page = JSON.parse(process.env.CB_TEST_PAGE)
const html = {}
html.shell = renderToStaticMarkup(
  React.createElement(mod.WorkspaceShell, {
    eyebrow: 'Coursebook',
    title: 'Affection and register',
    subtitle: 'in_progress · discrimination',
    meta: [React.createElement('span', { key: 'm' }, 'session bound')],
    actions: React.createElement('button', { type: 'button' }, 'Textbook'),
    rail: React.createElement(mod.FieldRail, {
      next: 'Ask a question in the polite register',
      facts: [{ label: 'State', value: 'in_progress' }],
      sources: [{ source_id: 'src_affection01', title: 'Register and affection', support_status: 'supported' }],
      notes: [{ entry_id: 'ent_1', excerpt: 'Keigo versus casual' }]
    }),
    children: React.createElement('p', null, 'Reading column')
  })
)
html.media = renderToStaticMarkup(
  React.createElement(mod.MediaFrame, {
    artifactId: 'art_0123456789abcdef',
    kind: 'audio',
    label: 'Narration',
    caption: 'Reference audio for the target phrase.',
    provenance: 'audio/mpeg · 18234 bytes · tts:openai',
    textEquivalent: 'Konnichiwa. A greeting used through the day.'
  })
)
html.section = renderToStaticMarkup(
  React.createElement('div', {
    'data-cb-scope': globalThis.__CB_TEST_MODE__ === 'dark' ? 'dark' : 'light',
    'data-cb-motion': 'full',
    style: mod.cbScopeStyle(globalThis.__CB_TEST_MODE__ === 'dark' ? 'dark' : 'light')
  },
  React.createElement(mod.SectionPage, {
    row: { enrollment_id: 'enr_0123456789abcdef', profile: 'default', next_step: { kind: 'resume_lesson', label: 'Resume this lesson' } },
    objectiveId: page.document.objective_id,
    page,
    pageStatus: 'ready',
    pageError: null,
    onRetryPage: () => {},
    implemented: new Set(['check.open', 'artifact.get', 'notebook.save']),
    onBack: () => {},
    onChanged: () => {},
    review: null
  })
  )
)
process.stdout.write(JSON.stringify({
  html,
  scope_light: mod.cbScopeStyle('light'),
  scope_dark: mod.cbScopeStyle('dark'),
  layout_wide: mod.cbLayoutFor(1280),
  layout_narrow: mod.cbLayoutFor(460),
  layout_unknown: mod.cbLayoutFor(0),
  motion_reduced: mod.cbMotionPreference({ matches: true }),
  motion_full: mod.cbMotionPreference({ matches: false }),
  tokens: mod.CB_TOKENS,
  token_names: mod.CB_TOKEN_NAMES
}))
"""


def _relative_luminance(hex_value: str) -> float:
    raw = hex_value.lstrip("#")
    channels = [int(raw[index:index + 2], 16) / 255 for index in (0, 2, 4)]

    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    return 0.2126 * linear(channels[0]) + 0.7152 * linear(channels[1]) + 0.0722 * linear(channels[2])


def contrast_ratio(foreground: str, background: str) -> float:
    first = _relative_luminance(foreground)
    second = _relative_luminance(background)
    high, low = max(first, second), min(first, second)
    return (high + 0.05) / (low + 0.05)


def shipped_tokens() -> tuple[dict, list[str], str]:
    source = PLUGIN_JS.read_text(encoding="utf-8")
    match = re.search(r"const CB_TOKENS_JSON =\s*\n?\s*'([^']+)'", source)
    if match is None:
        raise AssertionError("desktop/plugin.js has no CB_TOKENS_JSON literal")
    names = re.search(r"const CB_TOKEN_NAMES = Object\.freeze\(\[([^\]]+)\]\)", source)
    if names is None:
        raise AssertionError("desktop/plugin.js has no CB_TOKEN_NAMES list")
    token_names = re.findall(r"'([^']+)'", names.group(1))
    return json.loads(match.group(1)), token_names, match.group(1)


class TokenContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.tokens, self.names, self.literal = shipped_tokens()

    def test_the_shipped_table_equals_the_contract(self) -> None:
        self.assertEqual(self.tokens, self.contract["modes"])
        self.assertEqual(self.names, self.contract["tokens"])

    def test_every_token_has_a_light_and_a_dark_value(self) -> None:
        expected = set(self.contract["tokens"])
        for mode in ("light", "dark"):
            self.assertEqual(set(self.tokens[mode]), expected, mode)
            for name, value in self.tokens[mode].items():
                self.assertRegex(value, r"^#[0-9a-f]{6}$", f"{mode}.{name}")

    def test_no_colour_literal_outside_the_token_table(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8").replace(self.literal, "")
        stray = re.findall(r"#[0-9a-fA-F]{3,8}\b", source)
        self.assertEqual(stray, [], f"raw colours outside the token table: {stray}")

    def test_no_decorative_gradients(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8").lower()
        self.assertNotIn("gradient(", source)
        self.assertNotIn("linear-gradient", source)

    def test_contrast_gates_hold_for_the_values_that_ship(self) -> None:
        for gate in self.contract["gates"]:
            for mode in ("light", "dark"):
                foreground = self.tokens[mode][gate["foreground"]]
                background = self.tokens[mode][gate["background"]]
                ratio = contrast_ratio(foreground, background)
                self.assertGreaterEqual(
                    round(ratio, 2),
                    gate["min"],
                    f"{mode}: {gate['foreground']} on {gate['background']} is {ratio:.2f}, "
                    f"floor {gate['min']} ({gate['why']})",
                )

    def test_the_host_tertiary_floor_is_not_lowered(self) -> None:
        # The plan's floor: Coursebook secondary text may not sit below the host's tertiary text.
        for mode in ("light", "dark"):
            secondary = contrast_ratio(self.tokens[mode]["ink-soft"], self.tokens[mode]["paper"])
            self.assertGreaterEqual(round(secondary, 2), 4.5, mode)

    def test_the_route_and_pane_roots_are_the_scope(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        # Both registered surfaces paint the layer; nothing else declares a colour.
        self.assertEqual(source.count("style: cbScopeStyle(cbMode)"), 2)
        self.assertEqual(source.count("'data-cb-scope': cbMode"), 2)


class RouteShellRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-tokens-")
        cls.root = Path(cls.tmp.name)
        (cls.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (cls.root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        node_modules = cls.root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.mjs"}),
            encoding="utf-8",
        )
        (sdk / "index.mjs").write_text(SDK_STUB, encoding="utf-8")
        cls.document = document(
            guided=True,
            blocks=COMPLETE_BLOCKS,
            check_id="chk_0123456789abcdef",
        )
        cls.page = {
            "revision": 4,
            "section": {
                "objective_id": cls.document["objective_id"],
                "title": "Affection and register",
                "state": "in_progress",
                "evidence_target": "discrimination",
                "last_opened_at": None,
            },
            "runtime": {"lesson_run_id": "run_1", "binding_id": None, "binding_status": "detached", "session_state": "stored_only"},
            "segments": [],
            "attempts": [],
            "notebook_entries": [{"entry_id": "ent_1", "excerpt": "Keigo versus casual"}],
            "sources": [{"source_id": "src_affection01", "title": "Register and affection", "support_status": "supported"}],
            "document": cls.document,
        }
        cls.cache: dict[tuple[str, str], dict] = {}

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def render(self, width: int, mode: str) -> dict:
        key = (str(width), mode)
        if key in self.cache:
            return self.cache[key]
        env = dict(os.environ)
        env["CB_TEST_WIDTH"] = str(width)
        env["CB_TEST_MODE"] = mode
        env["CB_TEST_PAGE"] = json.dumps(self.page)
        result = subprocess.run(
            ["node", "harness.mjs"],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        payload = json.loads(result.stdout)
        self.cache[key] = payload
        return payload

    def test_the_scope_carries_every_token_in_both_modes(self) -> None:
        payload = self.render(1280, "light")
        light = payload["scope_light"]
        dark = payload["scope_dark"]
        for name in payload["token_names"]:
            self.assertIn(f"--cb-{name}", light)
            self.assertIn(f"--cb-{name}", dark)
        self.assertEqual(light["--cb-paper"], payload["tokens"]["light"]["paper"])
        self.assertEqual(dark["--cb-paper"], payload["tokens"]["dark"]["paper"])
        self.assertEqual(light["colorScheme"], "light")
        self.assertEqual(dark["colorScheme"], "dark")

    def test_layout_stacks_below_the_breakpoint_and_never_guesses_wide(self) -> None:
        payload = self.render(1280, "light")
        self.assertEqual(payload["layout_wide"], "wide")
        self.assertEqual(payload["layout_narrow"], "narrow")
        self.assertEqual(payload["layout_unknown"], "phone")
        self.assertEqual(payload["motion_reduced"], "reduced")
        self.assertEqual(payload["motion_full"], "full")

    def test_wide_shell_puts_the_rail_beside_the_reading_column(self) -> None:
        html = self.render(1280, "light")["html"]["shell"]
        self.assertIn('data-cb-workspace-shell="wide"', html)
        self.assertIn('data-cb-rail-slot="side"', html)
        self.assertIn("grid-template-columns:minmax(0, 1fr) 20rem", html)
        self.assertIn("var(--cb-rule)", html)
        self.assertIn('data-cb-field-rail', html)
        self.assertIn("Ask a question in the polite register", html)

    def test_a_460px_shell_stacks_the_rail_and_keeps_the_measure(self) -> None:
        html = self.render(460, "light")["html"]["shell"]
        self.assertIn('data-cb-workspace-shell="stacked"', html)
        self.assertIn('data-cb-rail-slot="bottom"', html)
        self.assertIn("flex-direction:column", html)
        self.assertIn("max-width:100%", html)
        self.assertNotIn("grid-template-columns", html)

    def test_the_reading_typography_scales_with_the_root_font(self) -> None:
        html = self.render(1280, "light")["html"]["shell"]
        # 200% text is a root-font change; px font sizes would not follow it.
        self.assertIn("clamp(1.45rem", html)
        self.assertNotRegex(html, r"font-size:\s*\d+px")

    def test_dark_mode_paints_the_dark_table_on_the_same_root(self) -> None:
        html = self.render(1280, "dark")["html"]["section"]
        self.assertIn('data-cb-scope="dark"', html)
        self.assertIn("--cb-paper:#131210", html)

    def test_media_frame_carries_caption_provenance_and_text_equivalent(self) -> None:
        html = self.render(1280, "light")["html"]["media"]
        self.assertIn('data-cb-media="art_0123456789abcdef"', html)
        self.assertIn('data-cb-media-kind="audio"', html)
        self.assertIn('data-cb-media-label', html)
        self.assertIn("Reference audio for the target phrase.", html)
        self.assertIn("audio/mpeg", html)
        self.assertIn("Text equivalent", html)
        self.assertIn("Konnichiwa.", html)

    def test_the_lesson_page_is_a_three_part_workspace(self) -> None:
        html = self.render(1280, "light")["html"]["section"]
        self.assertIn('data-cb-workspace-shell="wide"', html)
        self.assertIn('data-cb-reading-column', html)
        self.assertIn('data-cb-field-rail', html)
        self.assertIn('data-cb-source-card="src_affection01"', html)
        self.assertIn("Register and affection", html)
        # The source cards moved into the rail; the reading column does not print them twice.
        self.assertNotIn("SOURCES ON THIS COURSE", html)
        self.assertEqual(html.count("CHECK-NODE"), 0)
        self.assertIn('data-cb-view-switcher="available"', html)

    def test_a_460px_lesson_page_does_not_render_a_side_rail(self) -> None:
        html = self.render(460, "light")["html"]["section"]
        self.assertIn('data-cb-workspace-shell="stacked"', html)
        self.assertIn('data-cb-rail-slot="bottom"', html)
        self.assertNotIn('data-cb-rail-slot="side"', html)
        self.assertIn('data-cb-scope="light"', html)
        self.assertIn('data-cb-motion="full"', html)


if __name__ == "__main__":
    unittest.main()
