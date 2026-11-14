"""Upgrade 50 — contrast is measured on what the host paints, not on the token table.

The shipping gate (`tests/test_desktop_tokens.py`) computes WCAG ratios by hand over
`CB_TOKENS_JSON`. That is the right arbiter for values that *are* the table, and it stays the
arbiter here: this file never replaces it and never relaxes it.

What the hex gate cannot see is any surface the host composes at paint time: `color-mix`, an
alpha blend, a hover wash, an SDK theme remap. Those surfaces are gated on nothing at all. So this
file drives a dev-only probe (`visual/contrast-probe.mjs`) that

  * renders the shipped scope (`cbScopeStyle` from `desktop/plugin.js`) into a page,
  * reads `getComputedStyle` for every token pair on that page,
  * computes WCAG 2.x from the *painted* colour strings with `colorjs.io` (MIT), and
  * reports APCA as an informational column only — colorjs.io carries the APCA 0.0.98G draft
    constants, and `apca-w3` itself is refused on licence (All Rights Reserved, patents pending).

Two assertions close the gap:

  * `test_a_color_mix_surface_reports_a_measured_ratio` — a `color-mix` hover wash measures below
    the 4.5 floor while the closest hex pair passes, and its ratio matches no ratio the hex gate
    can compute. That is the blind spot, demonstrated on a painted surface.
  * `test_both_gates_agree_on_the_static_pairs` — for every static pair the contract gates, the
    measured ratio equals the Python gate's ratio. Agreement is what makes the measured gate
    trustworthy; a disagreement is a real defect in one of the two, never a tolerance to widen.

The probe is dev-only tooling. Nothing it does ships in the runtime module.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules
from tests.test_desktop_tokens import contrast_ratio, shipped_tokens

ROOT = Path(__file__).resolve().parent.parent
VISUAL = ROOT / "visual"
PROBE = VISUAL / "contrast-probe.mjs"
PLUGIN_JS = ROOT / "desktop" / "plugin.js"
CONTRACT = ROOT / "contracts" / "cb.tokens.v2.json"

# The upgrade note names "the 15 static pairs". The v2 contract gates 21 today; the floor records
# the documented claim and the tests assert agreement on every pair the contract actually ships, so
# a pair added to the contract is measured rather than skipped.
STATIC_PAIR_FLOOR = 15

# The measured WCAG value must match the Python gate. Both implement the same formula on the same
# 8-bit sRGB channels, so the only room needed is float noise from the painted rgb() string.
AGREEMENT_TOLERANCE = 0.01

# The hover wash is the mixed surface under test: paper darkened toward ink. It is authored with
# `color-mix` on the shipped custom properties, exactly as a hover or SDK remap composes a surface.
HOVER_MIX = "color-mix(in srgb, var(--cb-paper) 70%, var(--cb-ink))"
LAMP_MIX = "color-mix(in srgb, var(--cb-lamp) 40%, var(--cb-paper))"

SCOPE_HARNESS = """
globalThis.__CB_TEST_WIDTH__ = '1280'
const mod = await import('./plugin.js')

// Serialise the shipped scope style object into real CSS declarations. Custom properties are
// emitted verbatim; the three camelCase declarations are kebab-cased. Nothing is retyped by hand:
// every value below came out of cbScopeStyle() in desktop/plugin.js.
const cssText = (style) => Object.entries(style).map(([key, value]) => {
  if (key.startsWith('--')) return `${key}:${value};`
  const kebab = key.replace(/[A-Z]/g, (letter) => '-' + letter.toLowerCase())
  return `${kebab}:${value};`
}).join('')

process.stdout.write(JSON.stringify({
  light: cssText(mod.cbScopeStyle('light')),
  dark: cssText(mod.cbScopeStyle('dark')),
  tokens: mod.CB_TOKENS
}))
"""


def _node_available() -> bool:
    return shutil.which("node") is not None and shutil.which(os.environ.get("CB_CHROMIUM", "chromium")) is not None


def _colorjs_available() -> bool:
    return (VISUAL / "node_modules" / "colorjs.io").is_dir()


def _rgb(hex_value: str) -> str:
    """The exact string Chromium computes for a painted 6-digit hex token."""
    raw = hex_value.lstrip("#")
    return "rgb({}, {}, {})".format(*(int(raw[index:index + 2], 16) for index in (0, 2, 4)))


def _srgb_triplet(painted: str) -> tuple[float, float, float]:
    """Channels of a computed `color(srgb r g b)` / `rgb(r, g, b)` string, 0-1."""
    if painted.startswith("color(srgb "):
        parts = painted[len("color(srgb "):].rstrip(")").split()
        return (float(parts[0]), float(parts[1]), float(parts[2]))
    if painted.startswith("rgb("):
        parts = painted[len("rgb("):].rstrip(")").replace("/", " ").replace(",", " ").split()
        return (float(parts[0]) / 255, float(parts[1]) / 255, float(parts[2]) / 255)
    raise AssertionError(f"unreadable painted colour: {painted!r}")


def _pairs() -> list[dict]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    return contract["gates"]


def _page(scope_css: dict[str, str], tokens: dict, gates: list[dict]) -> str:
    """The rendered route: the shipped scope plus one element per pair, and the mixed surfaces."""
    rows: list[str] = []
    for mode in ("light", "dark"):
        rows.append(f'<section data-cb-scope="{mode}" data-cb-mode="{mode}">')
        rows.append(f'<h2>{mode}</h2>')
        for gate in gates:
            foreground = gate["foreground"]
            background = gate["background"]
            rows.append(
                '<p class="row" data-cb-measure data-cb-kind="pair"'
                f' data-cb-id="{mode}:{foreground}-on-{background}"'
                f' data-cb-fg="{foreground}" data-cb-bg="{background}"'
                f' style="color:var(--cb-{foreground});background-color:var(--cb-{background})">'
                "Aa</p>"
            )
        rows.append(
            '<p class="row" data-cb-measure data-cb-kind="mix"'
            f' data-cb-id="{mode}:ink-soft-on-mixed-hover"'
            ' data-cb-fg="ink-soft" data-cb-bg="mixed-hover"'
            f' style="color:var(--cb-ink-soft);background-color:{HOVER_MIX}">Aa</p>'
        )
        rows.append(
            '<p class="row" data-cb-measure data-cb-kind="mix"'
            f' data-cb-id="{mode}:ink-on-mixed-lamp"'
            ' data-cb-fg="ink" data-cb-bg="mixed-lamp"'
            f' style="color:var(--cb-ink);background-color:{LAMP_MIX}">Aa</p>'
        )
        rows.append("</section>")

    style = (
        "[data-cb-scope] { display: block; font: 16px/1.4 sans-serif; }"
        f'[data-cb-scope="light"] {{{scope_css["light"]}}}'
        f'[data-cb-scope="dark"] {{{scope_css["dark"]}}}'
        ".row { margin: 0; padding: 12px; }"
        "h2 { font-size: 16px; margin: 8px 12px; }"
    )
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<title>Coursebook measured contrast</title><style>{style}</style></head>"
        f'<body>{"".join(rows)}</body></html>'
    )


def _render_scope(root: Path, modules: Path) -> dict:
    """Import the shipped module once and return its own scope CSS plus its token table."""
    (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
    (root / "scope.mjs").write_text(SCOPE_HARNESS, encoding="utf-8")
    node_modules = root / "node_modules"
    node_modules.mkdir(exist_ok=True)
    for name in ("react", "react-dom", "scheduler"):
        source = modules / name
        if source.is_dir() and not (node_modules / name).exists():
            (node_modules / name).symlink_to(source, target_is_directory=True)
    sdk = node_modules / "@hermes" / "plugin-sdk"
    sdk.mkdir(parents=True, exist_ok=True)
    (sdk / "package.json").write_text(
        json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}), encoding="utf-8"
    )
    (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")

    scope = subprocess.run(
        ["node", str(root / "scope.mjs")], cwd=root, capture_output=True, text=True, timeout=120,
    )
    if scope.returncode != 0:
        raise AssertionError(f"the scope harness failed:\n{scope.stderr[-3000:]}")
    return json.loads(scope.stdout)


def _probe(page: Path, scratch: Path) -> dict:
    """Run the dev-only probe over a rendered page and return its report."""
    report = subprocess.run(
        ["node", str(PROBE), str(page)],
        cwd=VISUAL, capture_output=True, text=True, timeout=420,
        env={**os.environ, "CB_SCRATCH": str(scratch)},
    )
    if report.returncode != 0:
        raise AssertionError(f"the contrast probe failed (exit {report.returncode}):\n{report.stderr[-3000:]}")
    return json.loads(report.stdout)


class ContrastMeasuredTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # A missing probe is a product defect, not an environment skip: this is the file the card
        # adds, and its absence is exactly the RED state at HEAD. It is checked before every
        # environment probe so a clean checkout cannot report this gate as "skipped" and green.
        if not PROBE.is_file():
            raise AssertionError(f"the measured-contrast probe is missing: {PROBE}")
        if not _node_available():
            raise unittest.SkipTest("node + chromium are required to read what the host paints")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        if not _colorjs_available():
            raise unittest.SkipTest("visual/node_modules/colorjs.io is missing; run `npm ci` in visual/")

        cls.tmp = tempfile.TemporaryDirectory(prefix="up-contrast-measured-")
        root = Path(cls.tmp.name)
        rendered = _render_scope(root, modules)

        cls.tokens, cls.names, cls.literal = shipped_tokens()
        # The scope style must carry the shipped table, or the page is not the shipped paint.
        if rendered["tokens"] != cls.tokens:
            raise AssertionError("cbScopeStyle and CB_TOKENS disagree inside desktop/plugin.js")

        cls.page = root / "contrast.html"
        cls.page.write_text(_page(rendered, cls.tokens, _pairs()), encoding="utf-8")

        cls.report = _probe(cls.page, root)
        cls.measured = {row["id"]: row for row in cls.report["measurements"]}

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    # -- the blind spot -----------------------------------------------------------------------

    def test_a_color_mix_surface_reports_a_measured_ratio(self) -> None:
        gates = _pairs()
        for mode in ("light", "dark"):
            row = self.measured[f"{mode}:ink-soft-on-mixed-hover"]
            self.assertEqual(row["kind"], "mix")
            self.assertIsNone(row["error"], row["error"])
            measured = row["wcag"]

            # The hex gate cannot express this surface at all: the painted background is not any
            # token, so no pair in the table is this pair.
            token_hexes = {_rgb(value) for value in self.tokens[mode].values()}
            self.assertNotIn(row["background"], token_hexes,
                             f"{mode}: a mixed surface computed to a token value; the probe saw nothing new")

            # And it is a real interpolation, not a dropped declaration: an unsupported color-mix
            # computes to transparent, which would sail past every ratio assertion below.
            self.assertNotIn(row["background"], ("rgba(0, 0, 0, 0)", "transparent"),
                             f"{mode}: color-mix did not paint (computed {row['background']})")
            painted = _srgb_triplet(row["background"])
            paper = _srgb_triplet(_rgb(self.tokens[mode]["paper"]))
            ink = _srgb_triplet(_rgb(self.tokens[mode]["ink"]))
            expected_mix = tuple(0.7 * back + 0.3 * fore for back, fore in zip(paper, ink))
            for channel, (got, want) in enumerate(zip(painted, expected_mix)):
                self.assertAlmostEqual(
                    got, want, delta=0.01,
                    msg=(f"{mode}: channel {channel} painted {got:.4f}, but 70% paper + 30% ink is "
                         f"{want:.4f}; the surface under test is not the mix it claims to be"),
                )

            # And the ratio it paints matches no ratio the hex gate computes for the same ink.
            nearest = min(
                abs(measured - contrast_ratio(self.tokens[mode][gate["foreground"]],
                                              self.tokens[mode][gate["background"]]))
                for gate in gates
            )
            self.assertGreater(nearest, 0.5,
                               f"{mode}: measured {measured:.2f} is within {nearest:.2f} of a hex pair; "
                               "the fixture no longer demonstrates the blind spot")

            # The demonstration has teeth: the mixed hover fails the floor the closest hex pair passes.
            self.assertLess(measured, 4.5,
                            f"{mode}: the mixed hover measures {measured:.2f}; the fixture must show a "
                            "surface the hex gate would have passed unseen")
            hex_pair = contrast_ratio(self.tokens[mode]["ink-soft"], self.tokens[mode]["paper"])
            self.assertGreaterEqual(hex_pair, 4.5,
                                    f"{mode}: the static ink-soft/paper pair is itself under the floor")

            # The benign mix is measured too, and it is a real measurement, not a placeholder.
            benign = self.measured[f"{mode}:ink-on-mixed-lamp"]
            self.assertIsNone(benign["error"], benign["error"])
            self.assertGreater(benign["wcag"], measured)

    # -- agreement ----------------------------------------------------------------------------

    def test_both_gates_agree_on_the_static_pairs(self) -> None:
        gates = _pairs()
        pairs = {(gate["foreground"], gate["background"]) for gate in gates}
        self.assertGreaterEqual(len(pairs), STATIC_PAIR_FLOOR,
                                "the contract ships fewer static pairs than the upgrade note names")

        for mode in ("light", "dark"):
            for foreground, background in sorted(pairs):
                row = self.measured[f"{mode}:{foreground}-on-{background}"]
                self.assertEqual(row["kind"], "pair")
                self.assertIsNone(row["error"], row["error"])

                # The host painted the token the contract names, exactly.
                self.assertEqual(row["foreground"], _rgb(self.tokens[mode][foreground]),
                                 f"{mode}: {foreground} did not paint its contract value")
                self.assertEqual(row["background"], _rgb(self.tokens[mode][background]),
                                 f"{mode}: {background} did not paint its contract value")

                # Both implementations agree on the ratio.
                expected = contrast_ratio(self.tokens[mode][foreground], self.tokens[mode][background])
                self.assertAlmostEqual(row["wcag"], expected, delta=AGREEMENT_TOLERANCE,
                                       msg=(f"{mode}: {foreground} on {background} — hex gate says "
                                            f"{expected:.4f}, the host paints {row['wcag']:.4f}"))

    # -- APCA stays informational, apca-w3 stays refused ---------------------------------------

    def test_apca_is_reported_as_information_never_as_a_gate(self) -> None:
        self.assertTrue(self.report["apca"]["informational"])
        self.assertIn("draft", self.report["apca"]["implementation"].lower())
        self.assertIn("apca-w3", self.report["apca"]["refused"])
        for row in self.report["measurements"]:
            # APCA clips near-equal pairs to a plain 0, so the column is numeric, not always float.
            self.assertIsInstance(row["apca"], (int, float), f"{row['id']} has no APCA column")
            self.assertFalse(math.isnan(row["apca"]), f"{row['id']} has a NaN APCA column")

    def test_the_refused_apca_package_is_not_a_dependency(self) -> None:
        package = (VISUAL / "package.json").read_text(encoding="utf-8")
        lockfile = (VISUAL / "package-lock.json").read_text(encoding="utf-8")
        self.assertNotIn("apca-w3", package)
        self.assertNotIn("apca-w3", lockfile)
        self.assertIn("colorjs.io", package)

    # -- the probe reads paint, not the table -------------------------------------------------

    def test_the_probe_reads_computed_style_and_computes_with_colorjs(self) -> None:
        source = PROBE.read_text(encoding="utf-8")
        self.assertIn("getComputedStyle", source)
        self.assertIn("'WCAG21'", source)
        self.assertIn("contrastAPCA", source)
        self.assertIn("from 'colorjs.io'", source)
        # Every measured row is an engine string, never a hex literal from the table.
        for row in self.report["measurements"]:
            self.assertTrue(row["foreground"].startswith("rgb("), row["foreground"])
            self.assertTrue(row["background"].startswith(("rgb(", "color(", "oklab(", "oklch(")),
                            row["background"])


if __name__ == "__main__":
    unittest.main()
