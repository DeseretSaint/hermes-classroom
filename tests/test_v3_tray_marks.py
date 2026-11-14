"""Upgrade 28 — the evidence tray's tally is a mark on paper, measured on the rendered tray.

The failure this closes: the recorded-check marks were 8x8 px `sage` fills on the wooden tray.
Sage `#7f9a72` on wood `#a5763f` is 1.29:1 in light and 2.17:1 in dark, so the marks — the entire
visual meaning of the tray — merged into the object in both modes, and the photographic
`passport-tray` tile painted under them only made the real ratio worse.

What this test samples is the *rendered* primitive, not the CSS pair: `EvidenceTray` is mounted
through the real shipped module, the marks, the printed field and the wood tray are read from the
markup it returns, and their declared `background-color` tokens are resolved against the contract
in both modes. A tray that reads 1.29:1 in the markup fails here even if a gate table still lists a
comfortable number.

The photograph is the reason a token pair alone is not enough, so the flat sample area is asserted
too: the field under the marks must be an opaque `card-stock` fill with no image of its own, and
the wood tray must keep its tile. If the marks were painted straight onto the tile, the sampled
pixel would vary with the photograph and a CSS-only fix would "pass" a test no learner experiences.

What this does NOT prove: how the tray looks beside its count sentence at 460 px, or that the
shipped bundle is loaded by a Desktop window. Those are the live-rig and quality gates.
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

CONTRACT = ROOT / "contracts" / "cb.tokens.v3.json"
SEGMENT = ROOT / "desktop" / "src" / "85-v3-primitives.js"

#: WCAG 2.2 1.4.11 Non-text Contrast, and the floor the card names.
FLOOR = 3.0

HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

globalThis.__CB_TEST_WIDTH__ = '1049'
globalThis.__CB_TEST_MODE__ = 'light'

const { EvidenceTray } = await import('./plugin.js')
const h = React.createElement

const recorded = renderToStaticMarkup(
  h(EvidenceTray, {
    countLabel: '2 of 5 checks recorded',
    recorded: 2,
    events: ['First check', 'Second check'],
    note: 'Could not record one check.',
    toggleLabel: 'Record an observation',
    onToggle: () => {}
  })
)

const zero = renderToStaticMarkup(
  h(EvidenceTray, { recorded: 0, emptyLabel: 'No checks recorded yet' })
)

process.stdout.write(JSON.stringify({ recorded, zero }))
"""


def relative_luminance(hex_value: str) -> float:
    raw = hex_value.lstrip("#")
    channels = [int(raw[index:index + 2], 16) / 255 for index in (0, 2, 4)]

    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    return 0.2126 * linear(channels[0]) + 0.7152 * linear(channels[1]) + 0.0722 * linear(channels[2])


def contrast_ratio(foreground: str, background: str) -> float:
    first = relative_luminance(foreground)
    second = relative_luminance(background)
    high, low = max(first, second), min(first, second)
    return (high + 0.05) / (low + 0.05)


#: The opening tag of every element that carries `attribute`, style string included.
def opening_tags(html: str, attribute: str) -> list[str]:
    return re.findall(
        r"<(?:div|span)[^>]*" + re.escape(attribute) + r"[^>]*>",
        html,
    )


def style_of(tag: str) -> dict[str, str]:
    match = re.search(r'style="([^"]*)"', tag)
    if match is None:
        return {}
    declarations = {}
    for chunk in match.group(1).split(";"):
        if ":" not in chunk:
            continue
        name, _, value = chunk.partition(":")
        declarations[name.strip().lower()] = value.strip()
    return declarations


ROLE_REF = re.compile(r"^var\(--cb3-([a-z0-9-]+)\)$")


class TrayMarkContrastTest(unittest.TestCase):
    """The tally mark, the printed field and the wood tray, sampled from the rendered component."""

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-v3-tray-")
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
        result = subprocess.run(
            ["node", str(root / "harness.mjs")],
            cwd=root, capture_output=True, text=True, timeout=240,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr[-6000:])
        cls.markup = json.loads(result.stdout)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    # ── the sample ────────────────────────────────────────────────────────────────────────────

    def _painted(self, tag: str, layer: str) -> str:
        """The hex a rendered element's `background-color` resolves to in a mode."""
        style = style_of(tag)
        declared = style.get("background-color", "")
        match = ROLE_REF.match(declared)
        self.assertIsNotNone(
            match,
            f"{layer} paints {declared!r}, not a contract role; the sample cannot be resolved",
        )
        assert match is not None
        roles = self.contract["modes"][layer]
        self.assertIn(match.group(1), roles, f"{layer} names an unknown role {match.group(1)}")
        return roles[match.group(1)]

    def _tray(self) -> str:
        tags = opening_tags(self.markup["recorded"], 'data-cb3-tray="wood"')
        if not tags:
            # HEAD's tray carries no marker of its own: it is the element that paints wood and the
            # photographic tile. Finding it by what it paints keeps the measurement on the tray.
            for tag in re.findall(r"<div[^>]*>", self.markup["recorded"]):
                style = style_of(tag)
                if style.get("background-color") == "var(--cb3-wood)":
                    return tag
        self.assertEqual(len(tags), 1, "the recorded tray does not render exactly one wood tray")
        return tags[0]

    def _field(self) -> str:
        tags = opening_tags(self.markup["recorded"], "data-cb3-tally-field")
        self.assertEqual(len(tags), 1, "the recorded tally has no printed field to sit on")
        return tags[0]

    def _ground(self) -> tuple[str, str]:
        """The surface the marks are actually painted on, and how to name it in a failure.

        At HEAD there is no printed field: the marks sit straight on the tray's `background-color`
        and its photograph. Returning the tray there is what lets the acceptance read as a contrast
        number instead of only "an attribute is missing".
        """
        fields = opening_tags(self.markup["recorded"], "data-cb3-tally-field")
        if len(fields) == 1:
            return fields[0], "the printed field"
        return self._tray(), "the tray's own background (no printed field exists)"

    def _marks(self) -> list[str]:
        tags = opening_tags(self.markup["recorded"], "data-cb3-tally-mark")
        if not tags:
            # HEAD's marks are 8x8 px spans with no marker of their own; find them by their shape
            # so the contrast failure is measured on what the tray really paints.
            shaped = []
            for tag in re.findall(r"<span[^>]*>", self.markup["recorded"]):
                style = style_of(tag)
                if style.get("width") == "8px" and style.get("height") == "8px":
                    shaped.append(tag)
            tags = shaped
        self.assertEqual(len(tags), 2, "the tray did not stamp one mark per recorded check")
        return tags

    # ── the defect ────────────────────────────────────────────────────────────────────────────

    def test_the_marks_clear_three_to_one_against_the_field_they_sit_on(self) -> None:
        ground, ground_name = self._ground()
        marks = self._marks()
        for layer in ("light", "dark"):
            ground_colour = self._painted(ground, layer)
            for index, mark in enumerate(marks):
                mark_colour = self._painted(mark, layer)
                ratio = contrast_ratio(mark_colour, ground_colour)
                self.assertGreaterEqual(
                    round(ratio, 2), FLOOR,
                    f"{layer}: tally mark {index} is {ratio:.2f}:1 on {ground_name} "
                    f"({mark_colour} on {ground_colour}); the marks are the tray's whole meaning",
                )

    def test_the_marks_clear_three_to_one_against_the_wood_tray_itself(self) -> None:
        # The card's acceptance measures the mark against the tray's own background-color. The
        # wood is the tray, so the mark must separate from it as well as from the paper field.
        tray = self._tray()
        marks = self._marks()
        for layer in ("light", "dark"):
            tray_colour = self._painted(tray, layer)
            for index, mark in enumerate(marks):
                mark_colour = self._painted(mark, layer)
                ratio = contrast_ratio(mark_colour, tray_colour)
                self.assertGreaterEqual(
                    round(ratio, 2), FLOOR,
                    f"{layer}: tally mark {index} is {ratio:.2f}:1 against the wood tray "
                    f"({mark_colour} on {tray_colour})",
                )

    def test_the_printed_field_separates_from_the_wood_it_lies_in(self) -> None:
        tray = self._tray()
        field = self._field()
        for layer in ("light", "dark"):
            ratio = contrast_ratio(self._painted(field, layer), self._painted(tray, layer))
            self.assertGreaterEqual(
                round(ratio, 2), FLOOR,
                f"{layer}: the printed field is {ratio:.2f}:1 against the wood and merges into it",
            )

    def test_the_sample_area_is_flat_and_opaque_over_the_photograph(self) -> None:
        # The tile is under the marks. If the field were transparent or carried its own image the
        # sampled pixel would move with the photograph: a CSS pair would pass and the tray would
        # still fail. The field is a flat card-stock fill; the tray keeps the tile.
        field_style = style_of(self._field())
        self.assertNotIn("background-image", field_style, "the printed field paints an image")
        self.assertNotIn("opacity", field_style, "the printed field is not opaque")
        self.assertIn("background-color", field_style)
        tray_style = style_of(self._tray())
        self.assertIn("background-image", tray_style, "the wood tray lost its photographic tile")
        self.assertIn("url(", tray_style["background-image"])

    def test_a_zero_tray_paints_no_field_and_no_marks(self) -> None:
        # The empty state is the object alone plus its sentence; an empty paper strip would read as
        # a broken tally, and a zero mark would read as one recorded check.
        zero = self.markup["zero"]
        self.assertEqual(opening_tags(zero, "data-cb3-tally-field"), [], "a zero tray painted a field")
        self.assertEqual(opening_tags(zero, "data-cb3-tally-mark"), [], "a zero tray painted a mark")
        self.assertIn("No checks recorded yet", zero)

    # ── the source, so the fix cannot be undone by a quiet fill ───────────────────────────────

    def test_the_tray_paints_no_sage_fill(self) -> None:
        source = SEGMENT.read_text(encoding="utf-8")
        body = source[source.index("function EvidenceTray("):]
        body = body[:body.index("\n}\n") + 3]
        self.assertNotIn("cb3Role('sage')", body,
                         "the evidence tray still fills a mark with sage, which merges into wood")
        self.assertIn("cb3Role('ink')", body, "the tally marks are not stamped in ink")
        self.assertIn("data-cb3-tally-mark", body)


if __name__ == "__main__":
    unittest.main()
