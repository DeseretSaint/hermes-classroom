"""Item 28b — the drawn labels are painted by the UI over a textless figure, inside the frame.

The image request is textless by contract (``media.lesson_illustration_prompt``): a model that
paints a label garbles it into a false fact. So the Desktop draws the labels as an absolutely
positioned overlay on a legible backing plate.

These tests render the real shipped module (``desktop/plugin.js``) — the same file the runtime
loads — and prove the geometry where it is honest to prove it:

* ``mediaLabelPlacement`` maps each label's normalised ``x``/``y`` onto the measured frame, so an
  interior label's anchor point lands exactly at its fraction;
* every plate stays inside the frame — at **380 px**, the figure height the lesson column uses,
  and at **70 vh** (630 px of a 900 px viewport), where a centred or end-anchored label at the
  very edge would otherwise hang off the picture;
* the overlay draws one plate per label, carrying the label's text and anchor.

What this does NOT prove: that a real browser lays the plate out at these pixels — the geometry is
the pure function's, and the component measures the frame at runtime.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.desktop_node_modules import desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { mediaLabelPlacement, MediaLabelOverlay } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const frames = payload.frames.map((frame) => ({
  frame,
  placed: mediaLabelPlacement(payload.labels, frame)
}))
const html = renderToStaticMarkup(
  React.createElement(MediaLabelOverlay, { labels: payload.labels, frame: payload.frames[0] })
)
process.stdout.write(JSON.stringify({ frames, html }))
"""

SDK_STUB = """
import React from 'react'
const el = (tag, props, children) => React.createElement(tag, props, children)
export const ROUTES_AREA = 'routes'
export const SIDEBAR_NAV_AREA = 'sidebar.nav'
export const PANES_AREA = 'panes'
export const PALETTE_AREA = 'palette'
export const KEYBINDS_AREA = 'keybinds'
export const SETTINGS_PLUGINS_AREA = 'settings.plugins'
export const TOOL_MEDIA_RENDERER_AREA = 'tool.media'
export const useValue = (atom) => atom.get()
export const useTheme = () => ({ renderedMode: 'light', resolvedMode: 'light' })
export const Button = (props) => el('button', { type: 'button' }, props.children)
export const RowButton = (props) => el('button', { type: 'button' }, props.children)
export const Badge = (props) => el('span', {}, props.children)
export const PanelSectionLabel = (props) => el('div', {}, props.children)
export const PanelEmpty = (props) => el('div', {}, props.children)
export const Loader = () => null
export const ErrorState = () => null
export const EmptyState = () => null
export const MessageTextContent = () => null
export const SegmentedControl = () => null
export const Input = () => null
export const Textarea = () => null
export const SearchField = () => null
export const Select = () => null
export const SelectTrigger = () => null
export const SelectValue = () => null
export const SelectContent = () => null
export const SelectItem = () => null
export const ListRow = () => null
export const ConfirmDialog = () => null
export const DropdownMenu = () => null
export const DropdownMenuItem = () => null
export const DropdownMenuTrigger = () => null
export const DropdownMenuContent = () => null
export const Codicon = () => null
export const Checkbox = () => null
export const SandboxedFrame = () => null
export const Tabs = () => null
export const Tip = () => null
export const Panel = () => null
export const PanelHeader = () => null
export const PanelBody = () => null
export const PanelSection = () => null
export const SIDEBAR = 'sidebar'
export const useHost = () => ({ notify: () => {} })
export const useRpc = () => async () => ({ ok: false, error: { code: 'NOT_IMPLEMENTED', message: 'stub' } })
export const definePlugin = (definition) => definition
"""

LABELS = [
    {"text": "Jaws", "x": 0.28, "y": 0.74, "anchor": "start"},
    {"text": "Workpiece", "x": 0.62, "y": 0.41, "anchor": "center"},
]

#: The two frames the card names: the 380 px figure the lesson column draws, and 70 vh of a
#: 900 px viewport, which is the tall figure a wide window gets.
FRAMES = [{"width": 380, "height": 380}, {"width": 900, "height": 630}]


class MediaLabelOverlayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-media-labels-")
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

    def render(self, labels: list[dict], frames: list[dict]) -> dict:
        case = self.root / "case.json"
        case.write_text(json.dumps({"labels": labels, "frames": frames}), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        return json.loads(result.stdout)

    def test_every_plate_stays_inside_the_frame(self) -> None:
        result = self.render(LABELS, FRAMES)
        for entry in result["frames"]:
            frame = entry["frame"]
            self.assertEqual(len(entry["placed"]), len(LABELS))
            for plate in entry["placed"]:
                with self.subTest(frame=frame, text=plate["text"]):
                    self.assertGreaterEqual(plate["left"], 0)
                    self.assertGreaterEqual(plate["top"], 0)
                    self.assertLessEqual(plate["left"] + plate["plateWidth"], frame["width"])
                    self.assertLessEqual(plate["top"] + plate["plateHeight"], frame["height"])

    def test_an_interior_label_draws_at_its_fraction(self) -> None:
        result = self.render(LABELS, FRAMES)
        for entry in result["frames"]:
            frame = entry["frame"]
            start, centre = entry["placed"][0], entry["placed"][1]
            with self.subTest(frame=frame):
                # A `start` anchor puts the plate's left edge at x, and the plate's middle at y.
                self.assertEqual(start["left"], round(LABELS[0]["x"] * frame["width"]))
                self.assertAlmostEqual(
                    start["top"] + start["plateHeight"] / 2,
                    LABELS[0]["y"] * frame["height"],
                    delta=0.5,  # the plate's top is rounded to whole pixels
                )
                # A `center` anchor puts the plate's middle at x.
                self.assertAlmostEqual(
                    centre["left"] + centre["plateWidth"] / 2,
                    LABELS[1]["x"] * frame["width"],
                    delta=1.0,  # two roundings: the plate's left and the estimated plate width
                )
                self.assertEqual(centre["anchor"], "center")

    def test_a_label_at_the_very_edge_is_pulled_back_inside(self) -> None:
        edge = [
            {"text": "Right edge", "x": 1.0, "y": 1.0, "anchor": "end"},
            {"text": "Left edge", "x": 0.0, "y": 0.0, "anchor": "start"},
        ]
        result = self.render(edge, FRAMES)
        for entry in result["frames"]:
            frame = entry["frame"]
            right, left = entry["placed"][0], entry["placed"][1]
            with self.subTest(frame=frame):
                self.assertLessEqual(right["left"] + right["plateWidth"], frame["width"])
                self.assertLessEqual(right["top"] + right["plateHeight"], frame["height"])
                self.assertGreaterEqual(right["left"], 0)
                self.assertGreaterEqual(left["left"], 0)
                self.assertGreaterEqual(left["top"], 0)

    def test_the_overlay_draws_one_plate_per_label_with_a_backing(self) -> None:
        result = self.render(LABELS, FRAMES)
        html = result["html"]
        self.assertIn('data-cb-media-labels="2"', html)
        for label in LABELS:
            self.assertEqual(html.count(label["text"]), 1, label["text"])
        self.assertEqual(html.count("data-cb-media-label-text"), 2)
        self.assertIn('data-cb-media-label-anchor="center"', html)
        self.assertNotIn("<img", html)  # the raster is not painted by this component
        for plate in result["frames"][0]["placed"]:
            self.assertIn(f"left:{plate['left']}px", html)
            self.assertIn(f"top:{plate['top']}px", html)

    def test_no_labels_draws_no_overlay(self) -> None:
        result = self.render([], FRAMES)
        self.assertNotIn("data-cb-media-labels", result["html"])


if __name__ == "__main__":
    unittest.main()
