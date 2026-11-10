"""CP-020b — the Field Atlas v3 primitives, executed rather than read.

The card's contract, in executable form:

* `PillAction` is the only filled control and a surface has at most one: the lab carries none, a
  normal surface carries exactly one, and the same counter that proves that also counts two when a
  composition has two (so the assertion is a measurement, not a wording);
* `StampNode` is a real button in all four states — done, current, upcoming, locked — and the
  current one carries `aria-current="step"` and the word beside the shape;
* `FoxPose` is `aria-hidden`, sits inside its safe area, and is **absent** below a 620 px route;
* `CollectibleCard` carries no rating, star, review count, percentage or XP — only a title, one
  subject chip, one real meta row and an optional backed `New` chip;
* `DialogueBubble` renders the deck's ruby as `<rt>` over the kana *and* a separate romaji line;
* every primitive paints from `var(--cb3-*)` only: no hex, no `rgb()`/`hsl()`, no viewport unit,
  no shadow recipe, no gradient, and no v2 `--cb-` token.

What this does NOT prove: that a browser paints these correctly, that the material reads as paper,
or that a composed screen keeps the composition anchors. Those are the lab frames, the live
Desktop captures and the reviewer's rubric.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.cb_source_scope import (
    ANIMATION,
    GLASS,
    GRADIENT,
    HEX,
    PLUGIN_JS,
    ROOT,
    SHADOW,
    V3_BEGIN,
    V3_END,
    VW,
)
from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

#: The segment the primitives live in. Reading it directly is the point: a hex that only exists
#: inside the v3 marker region still ships, so it is still a defect.
SEGMENT = ROOT / "desktop" / "src" / "85-v3-primitives.js"

PRIMITIVES = (
    "PillAction",
    "ForestRail",
    "ForestBand",
    "PaperCard",
    "CollectibleCard",
    "CoverPlate3",
    "ShelfPlank",
    "StampNode",
    "Medallion",
    "FoxPose",
    "DialogueBubble",
    "ChallengeCard",
    "EvidenceTray",
)

HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import fs from 'node:fs'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
// Set BEFORE the module import: the SDK stub reads the viewport atom at module evaluation, and a
// static `import` would hoist above this assignment (ESM). A dynamic import keeps the order real.
globalThis.__CB_TEST_WIDTH__ = String(payload.width || 1049)
globalThis.__CB_TEST_MODE__ = payload.mode || 'light'

const {
  PillAction, ForestRail, ForestBand, PaperCard, CollectibleCard, CoverPlate3, ShelfPlank,
  StampNode, Medallion, FoxPose, DialogueBubble, ChallengeCard, EvidenceTray, CbV3LabSheet,
  CB3_POSES, CB3_STAMP_STATES, CB3_MEDALS
} = await import('./plugin.js')

const h = React.createElement
const mount = (node) => renderToStaticMarkup(node)

const surface = mount(
  h('div', { 'data-cb3-surface': 'home.global' }, [
    h(PillAction, { key: 'p', variant: 'primary', label: 'Start a course', onClick: () => {} }),
    h(PillAction, { key: 'q', variant: 'quiet', label: 'Browse library', onClick: () => {} })
  ])
)

// Negative control: the same counter must see two filled controls when a composition has two.
const twoPrimaries = mount(
  h('div', { 'data-cb3-surface': 'double' }, [
    h(PillAction, { key: 'a', variant: 'primary', label: 'One', onClick: () => {} }),
    h(PillAction, { key: 'b', variant: 'primary', label: 'Two', onClick: () => {} })
  ])
)

const lab = mount(h(CbV3LabSheet, { onBack: () => {} }))

const stamps = mount(
  h('div', null,
    CB3_STAMP_STATES.map((state, index) =>
      h(StampNode, { key: state, state, index: index + 1, label: `Section ${index + 1}`, onClick: () => {} })
    ).concat([
      h(StampNode, { key: 'bogus', state: 'bogus', label: 'Unknown state', onClick: () => {} })
    ])
  )
)

const fox = mount(h(FoxPose, { pose: 'clock', size: 128 }))

const cardArt = mount(h(CollectibleCard, {
  title: 'Japanese Lantern District',
  subject: 'Language',
  meta: '2 of 5 sections done',
  src: 'data:image/webp;base64,AAAA',
  isNew: true,
  newLabel: 'New',
  action: h(PillAction, { variant: 'quiet', label: 'Continue', onClick: () => {} })
}))

const cardTyped = mount(h(CollectibleCard, {
  title: 'Japanese Lantern District',
  subject: 'Language',
  meta: '2 of 5 sections done'
}))

const bubble = mount(h(DialogueBubble, {
  segments: [{ text: 'この' }, { text: '店', ruby: 'みせ' }, { text: 'です。' }],
  romaji: 'Kono mise desu.',
  en: 'This is the shop.',
  playLabel: 'Play the line',
  onPlay: () => {}
}))

const bubbleQuiet = mount(h(DialogueBubble, {
  segments: [{ text: 'この' }, { text: '店', ruby: 'みせ' }, { text: 'です。' }],
  romaji: 'Kono mise desu.',
  en: 'This is the shop.'
}))

const details = mount(
  h('div', null, [
    h(ShelfPlank, { key: 'shelf' }, [h(CollectibleCard, { key: 'c', title: 'A course', meta: '0 of 4 sections done' })]),
    h(PaperCard, { key: 'paper', emphasis: 'elev-1', title: 'Card', meta: 'elev-1' }),
    h(ForestRail, { key: 'rail', value: 'home', onChange: () => {} }),
    h(ForestBand, { key: 'band', value: 'courses', onChange: () => {} }),
    h(Medallion, { key: 'm1', event: 'first_check' }),
    h(Medallion, { key: 'm2', event: 'not_an_event' }),
    h(ChallengeCard, { key: 'ch', title: 'Field challenge', prompt: 'Name one more shop.', actionLabel: 'Open the check' }),
    h(EvidenceTray, { key: 't', countLabel: '2 of 5 checks recorded', recorded: 2, events: ['First check'], note: 'Could not record.' })
  ])
)

process.stdout.write(JSON.stringify({
  surface, twoPrimaries, lab, stamps, fox, cardArt, cardTyped, bubble, bubbleQuiet, details,
  poses: CB3_POSES, stampStates: CB3_STAMP_STATES, medals: Object.keys(CB3_MEDALS)
}))
"""


def strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


class V3PrimitivesRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-v3primitives-")
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
        cls.reports = {}
        for width in (1049, 800, 460):
            case = root / f"case-{width}.json"
            case.write_text(json.dumps({"width": width}), encoding="utf-8")
            result = subprocess.run(
                ["node", str(root / "harness.mjs"), str(case)],
                cwd=root, capture_output=True, text=True, timeout=240,
            )
            if result.returncode != 0:
                raise AssertionError(result.stderr[-6000:])
            cls.reports[width] = json.loads(result.stdout)
        cls.report = cls.reports[1049]

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def test_v3_one_primary_per_surface(self) -> None:
        home = self.report["surface"]
        self.assertEqual(home.count('data-cb3-pill="primary"'), 1,
                         "the composition carries more than one filled control")
        self.assertEqual(home.count('data-cb3-pill="quiet"'), 1)
        self.assertIn("cb3-quiet-outline", home, "the quiet action lost its 1 px rule treatment")
        # The counter is load-bearing: two primaries in one composition must read as two.
        self.assertEqual(self.report["twoPrimaries"].count('data-cb3-pill="primary"'), 2,
                         "the one-primary counter cannot see a second filled control")
        # SPEC-V3 §3.10 documents the lab's N/A: no filled control, Back is quiet navigation.
        self.assertEqual(self.report["lab"].count('data-cb3-pill="primary"'), 0,
                         "the component lab minted a filled primary")
        # And every call site names its weight: no implicit primary, no third value.
        source = SEGMENT.read_text(encoding="utf-8")
        call_sites = re.findall(r"PillAction, \{[^}]*variant: '([a-z]+)'", source)
        self.assertTrue(call_sites, "no PillAction call site carries an explicit variant")
        self.assertTrue(set(call_sites) <= {"primary", "quiet"},
                        f"a call site asks for an unsupported weight: {sorted(set(call_sites))}")

    def test_stamp_node_states_are_buttons_with_labels(self) -> None:
        html = self.report["stamps"]
        buttons = re.findall(r"<button[^>]*>.*?</button>", html, flags=re.S)
        self.assertEqual(len(buttons), 5, f"expected four states plus the fallback, got {len(buttons)}")
        for state in ("done", "current", "upcoming", "locked"):
            match = re.search(
                r'<button[^>]*data-cb3-stamp="' + state + r'"[^>]*>(.*?)</button>', html, flags=re.S
            )
            self.assertIsNotNone(match, f"no button renders the {state} state")
            assert match is not None
            label = strip_tags(match.group(1)).strip()
            self.assertTrue(label, f"the {state} stamp has no visible label")
        current = re.search(r'<button[^>]*data-cb3-stamp="current"[^>]*>', html)
        self.assertIsNotNone(current)
        assert current is not None
        self.assertIn('aria-current="step"', current.group(0))
        self.assertIn("Now", strip_tags(html), "the current step is marked by shape alone")
        locked = re.search(r'<button[^>]*data-cb3-stamp="locked"[^>]*>', html)
        self.assertIsNotNone(locked)
        assert locked is not None
        self.assertIn("disabled", locked.group(0), "a locked stamp is a live button")
        unknown = re.findall(r'<button[^>]*data-cb3-stamp="upcoming"[^>]*>(.*?)</button>', html, flags=re.S)
        self.assertEqual(len(unknown), 2, "an unknown stamp state did not fall back to upcoming")
        self.assertTrue(
            any("Unknown state" in strip_tags(entry) for entry in unknown),
            "an unknown stamp state rendered an invisible or invented state",
        )

    def test_fox_pose_aria_hidden_and_hidden_below_620(self) -> None:
        wide = self.report["fox"]
        self.assertIn('data-cb3-fox="clock"', wide)
        self.assertIn('aria-hidden="true"', wide)
        self.assertIn('alt=""', wide)
        self.assertIn('data-cb3-fox-safe="24px"', wide)
        self.assertIn("data:image/webp;base64,", wide, "the fox rendered without its shipped sheet")
        # A route between 620 and 920 keeps the fox at the 16 px safe area.
        mid = self.reports[800]["fox"]
        self.assertIn('data-cb3-fox-safe="16px"', mid)
        # Below 620 the mascot is absent, not squashed (SPEC-V3 §3.8).
        self.assertNotIn("data-cb3-fox=", self.reports[460]["fox"],
                         "the fox renders below a 620 px route")

    def test_collectible_card_has_no_rating_fields(self) -> None:
        html = self.report["cardArt"]
        for banned in ("★", "☆", "stars", "rating", "reviews", "review_count", "xp", "percent"):
            self.assertNotIn(banned, html.lower(), f"the card renders a banned field: {banned}")
        self.assertIn('data-cb3-card="collectible"', html)
        self.assertEqual(html.count('data-cb3-card-meta'), 1, "the card has more than one meta row")
        self.assertIn('data-cb3-chip="subject"', html)
        self.assertIn('data-cb3-chip="new"', html)
        # One title, once: the art plate is media, so the title is the card's own heading.
        self.assertEqual(html.lower().count("japanese lantern district"), 1,
                         "the card title is printed twice")
        typed = self.report["cardTyped"]
        self.assertIn('data-cb3-cover="type"', typed, "no typographic fallback for a missing cover")
        self.assertNotIn('data-cb3-chip="new"', typed, "a New chip without a backing fact")
        self.assertEqual(typed.lower().count("japanese lantern district"), 1,
                         "the typographic plate duplicated the title")

    def test_dialogue_bubble_renders_ruby_and_romaji(self) -> None:
        html = self.report["bubble"]
        self.assertIn("<ruby>", html)
        self.assertIn("<rt", html)
        self.assertIn("みせ", html, "the deck's ruby reading is missing")
        self.assertIn('lang="ja-Latn"', html, "the romaji line is not marked as romanised Japanese")
        self.assertIn("Kono mise desu.", html)
        self.assertIn("This is the shop.", html)
        self.assertIn("data-cb3-speak", html, "the speaker button is missing when a line can play")
        self.assertNotIn("data-cb3-speak", self.report["bubbleQuiet"],
                         "a speaker button rendered with no play handler")

    def test_primitives_use_only_v3_tokens(self) -> None:
        source = SEGMENT.read_text(encoding="utf-8")
        # Every primitive is defined here, inside the v3 marker region, and exported.
        self.assertIn(V3_BEGIN, source)
        self.assertIn(V3_END, source)
        export = PLUGIN_JS.read_text(encoding="utf-8")
        for name in PRIMITIVES:
            self.assertIn(f"function {name}(", source, f"{name} is not defined in the primitives segment")
            self.assertIn(name, export[export.index("export {"):], f"{name} is not exported for the lab")
        # Paint comes from the v3 custom properties and nothing else.
        self.assertEqual(HEX.findall(source), [], "a raw hex colour is painted outside the token table")
        self.assertEqual(re.findall(r"\brgba?\(", source), [], "an rgb()/rgba() colour literal is painted")
        self.assertEqual(re.findall(r"\bhsla?\(", source), [], "an hsl() colour literal is painted")
        self.assertEqual(VW.findall(source), [], "a viewport unit on a v3 primitive")
        self.assertEqual(SHADOW.findall(source), [], "a shadow recipe outside the elevation token")
        self.assertEqual(GRADIENT.findall(source), [], "a gradient on a primitive")
        self.assertEqual(GLASS.findall(source), [], "glass paint on a primitive")
        self.assertEqual(ANIMATION.findall(source), [], "a loop or keyframe on a primitive")
        # A colour role must be a --cb3-* reference: the v2 prefix is drift, not a fallback.
        for name in re.findall(r"var\((--[a-z0-9-]+)", source):
            self.assertTrue(
                name.startswith("--cb3-"),
                f"{name} is not a v3 token (v3 uses --cb3-*; --cb-* is the retired v2 table)",
            )
        # Sizes come from the six contract steps, never an authored font size. The one exception is
        # the ruby's relative `em`, which the contract names explicitly ("furigana is smaller than
        # the body step by design, never a seventh authored size") and which scales with its base.
        for value in re.findall(r"fontSize: [^,\n]+", source):
            self.assertTrue(
                "cb3Type(" in value or re.search(r"'\d*\.?\d+em'", value),
                f"an authored font size: {value.strip()}",
            )
        # Every primitive documents the tokens it reads: a `Tokens:` line naming contract roles.
        roles = json.loads((ROOT / "contracts" / "cb.tokens.v3.json").read_text(encoding="utf-8"))["roles"]
        for name in PRIMITIVES:
            head = source.rfind("/**", 0, source.index(f"function {name}("))
            block = source[head:source.index(f"function {name}(")]
            self.assertIn("Tokens:", block, f"{name} has no doc comment naming its tokens")
            named = [role for role in roles if role in block.split("Tokens:", 1)[1]]
            self.assertTrue(named, f"{name}'s doc comment names no contract role")


if __name__ == "__main__":
    unittest.main()
