"""Item 32 — the review verdict is a chip on the media item, with its reason.

The gate rejects a generated illustration and records ``{state, reasons, criteria?}``; the learner
used to be shown a degraded figure with no explanation. These tests render the real shipped module
(``desktop/plugin.js``) — the same file the runtime loads — and prove what the media item draws:

* a degraded item (a rejected illustration, no bytes) draws the chip and its bounded reason;
* a delivered, approved item draws nothing at all — the chip is for a verdict, not decoration;
* a rejection that was repaired into the deterministic schematic still shows the verdict over the
  shipped bytes, criteria included, because the route returns the review with the picture;
* ``mediaVerdict`` reads only explicit fields: an approved verdict, an item with no verdict and no
  degradation, and an unknown state all draw nothing.

What this does NOT prove: that a real browser lays the chip out at these pixels — the markup is the
component's, and the visual audit covers paint.
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
import { MediaSegment, MediaVerdictChip, mediaVerdict } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const cases = payload.cases.map((entry) => {
  const media = entry.media
  const review = entry.review
  const html = renderToStaticMarkup(
    React.createElement(MediaVerdictChip, { media, review })
  )
  const segmentHtml = entry.segment
    ? renderToStaticMarkup(React.createElement(MediaSegment, { segment: entry.segment }))
    : null
  return { name: entry.name, verdict: mediaVerdict(media, review), html, segmentHtml }
})
process.stdout.write(JSON.stringify({ cases }))
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

#: The reason string the backend writes for a rejected illustration that degraded to text, in the
#: shape ``media.generate_for_lessons`` stores (bounded to the media child's 300-character reason).
DEGRADED_REASON = (
    "illustration rejected by review (failed contains_legible_text: the picture contains legible "
    "text or numbers a learner could read as a fact); delivered as text"
)

#: The preview's review payload for the schematic that was drawn after a rejection.
SCHEMATIC_REVIEW = {
    "state": "rejected",
    "reasons": [
        "the picture contains legible text or numbers a learner could read as a fact",
        "the deterministic schematic drawn from the procedure table was delivered instead",
    ],
    "criteria": ["contains_legible_text"],
}

APPROVED_REVIEW = {
    "state": "approved",
    "reasons": ["the picture matches the prompt and shows no legible text, procedure or measurement"],
}

CASES = [
    {
        "name": "degraded",
        "media": {"degraded": True, "reason": DEGRADED_REASON},
        "review": None,
        "segment": {
            "kind": "visual",
            "text": "A brake caliper rests on a workshop bench.",
            "label": "Illustration (context only)",
            "degraded": True,
            "reason": DEGRADED_REASON,
        },
    },
    {
        "name": "approved",
        "media": {"degraded": False, "reason": None},
        "review": APPROVED_REVIEW,
        "segment": {
            "artifact_id": "art_caliper_1",
            "kind": "visual",
            "text": "A brake caliper rests on a workshop bench.",
            "label": "Illustration (context only)",
            "degraded": False,
            "reason": None,
        },
    },
    {
        "name": "schematic",
        "media": {"degraded": True, "reason": DEGRADED_REASON + "; the deterministic schematic was delivered instead"},
        "review": SCHEMATIC_REVIEW,
    },
    {
        "name": "unreviewed",
        "media": {"degraded": False, "reason": None},
        "review": {
            "state": "unreviewed",
            "reasons": ["the host vision tool is unavailable (vision_analyze returned no text)"],
        },
    },
    {"name": "silent", "media": {"degraded": False, "reason": None}, "review": None},
    {
        "name": "unknown-state",
        "media": {"degraded": False, "reason": None},
        "review": {"state": "pending", "reasons": ["should not render"]},
    },
]


class MediaVerdictChipTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-media-verdict-")
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
        cls.rendered = cls._run(CASES)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    @classmethod
    def _run(cls, cases: list[dict]) -> dict[str, dict]:
        case = cls.root / "case.json"
        case.write_text(json.dumps({"cases": cases}), encoding="utf-8")
        result = subprocess.run(
            ["node", str(cls.root / "harness.mjs"), str(case)],
            cwd=cls.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise AssertionError(f"node harness failed: {result.stderr[-2000:]}")
        return {entry["name"]: entry for entry in json.loads(result.stdout)["cases"]}

    def html(self, name: str) -> str:
        return self.rendered[name]["html"]

    def test_a_degraded_item_draws_the_chip_and_its_reason(self) -> None:
        html = self.html("degraded")
        self.assertIn('data-cb-media-verdict="degraded"', html)
        self.assertIn('data-cb-media-verdict-chip="degraded"', html)
        self.assertIn("Media degraded", html)
        self.assertIn('data-cb-media-verdict-reason=""', html)
        self.assertIn("failed contains_legible_text", html)
        self.assertIn("delivered as text", html)

    def test_a_delivered_approved_item_draws_nothing(self) -> None:
        self.assertEqual(self.rendered["approved"]["verdict"], None)
        self.assertEqual(self.html("approved"), "")

    def test_a_silent_item_draws_nothing(self) -> None:
        self.assertEqual(self.rendered["silent"]["verdict"], None)
        self.assertEqual(self.html("silent"), "")

    def test_an_unknown_verdict_state_draws_nothing(self) -> None:
        # The chip never invents a state it was not told about, and an unknown one is not an alarm.
        self.assertEqual(self.rendered["unknown-state"]["verdict"], None)
        self.assertEqual(self.html("unknown-state"), "")

    def test_a_repaired_rejection_keeps_its_verdict_over_the_shipped_bytes(self) -> None:
        html = self.html("schematic")
        self.assertIn('data-cb-media-verdict="rejected"', html)
        self.assertIn("Rejected by review", html)
        # The failing criterion is printed as the gate's own key, not as a re-parsed sentence.
        self.assertIn('data-cb-media-verdict-criteria="contains_legible_text"', html)
        self.assertIn("contains_legible_text", html)
        self.assertIn("deterministic schematic", html)

    def test_an_unreviewed_item_says_so_rather_than_looking_approved(self) -> None:
        html = self.html("unreviewed")
        self.assertIn('data-cb-media-verdict="unreviewed"', html)
        self.assertIn("Not reviewed", html)
        self.assertIn("vision_analyze returned no text", html)

    def test_the_media_item_draws_the_chip_and_nothing_for_a_delivered_item(self) -> None:
        """The wiring, not just the chip: the item a lesson page renders carries the verdict."""
        degraded = self.rendered["degraded"]["segmentHtml"]
        self.assertIn('data-cb-media-verdict="degraded"', degraded)
        self.assertIn("failed contains_legible_text", degraded)
        self.assertIn("A brake caliper rests on a workshop bench.", degraded)

        delivered = self.rendered["approved"]["segmentHtml"]
        self.assertNotIn("data-cb-media-verdict", delivered)

    def test_the_verdict_is_never_read_out_of_a_reason_string(self) -> None:
        # A reason that merely mentions a rejection is not a verdict: only the explicit fields are.
        rendered = self._run(
            [
                {
                    "name": "prose-only",
                    "media": {
                        "degraded": False,
                        "reason": "illustration rejected by review (failed contains_legible_text)",
                    },
                    "review": None,
                }
            ]
        )
        self.assertEqual(rendered["prose-only"]["verdict"], None)
        self.assertEqual(rendered["prose-only"]["html"], "")


if __name__ == "__main__":
    unittest.main()
