"""H-152 — the motion and feedback contract.

The shipped module had one transition class and zero keyframes: press, route changes, check
verdicts and completion had no temporal feedback, so the product read as a static document.

This suite reads the *shipped* module twice over:

  * as source — one motion ladder, four beats, no fifth duration, no keyframes, no shadow or
    gradient, and every authored transition naming only transform / opacity / colour;
  * as computed style — real React + jsdom, where `CbAction`, `CheckpointPath`, `PlayerVerdict`
    and `PlayerClose` are mounted, pressed, and measured, in both the full-motion and the
    `prefers-reduced-motion: reduce` posture.

What this does NOT prove: that the installed Desktop paints the same pixels, that the transitions
actually run on a compositor thread at 60 fps, or that the host SDK's own controls are still. Those
are captured live by ``scripts/h152-motion-capture.mjs`` (docs/H152-EVIDENCE.md).
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

from tests.test_desktop_lesson_views import _desktop_node_modules
from tests.test_desktop_field_desk import SDK_STUB

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

# The stub SDK forwards the style object and the pointer handlers, because the press beat is a
# style change driven by a real pointer event; the shared stub drops both.
BUTTON_STUB = """export const Button = (props) => {
  const attrs = {
    type: 'button',
    disabled: Boolean(props.disabled),
    'data-variant': props.variant || null,
    onClick: props.onClick
  }
  for (const name of ['onPointerDown', 'onPointerUp', 'onPointerLeave', 'onPointerCancel', 'onBlur']) {
    if (typeof props[name] === 'function') attrs[name] = props[name]
  }
  if (props.className) attrs.className = props.className
  if (props.style) attrs.style = props.style
  if (props.title) attrs.title = props.title
  for (const [name, value] of Object.entries(props)) {
    if ((name.startsWith('data-') || name.startsWith('aria-')) && value !== undefined && !(name in attrs)) {
      attrs[name] = value
    }
  }
  return el('button', attrs, textOf(props))
}"""

OLD_BUTTON = SDK_STUB[SDK_STUB.index("export const Button"):SDK_STUB.index("export const Badge")]
STUB = SDK_STUB.replace(OLD_BUTTON, BUTTON_STUB + "\n")

HARNESS = r"""
import { JSDOM } from 'jsdom'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
const reduced = process.env.CB_TEST_REDUCED === '1'
const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  pretendToBeVisual: true,
  url: 'http://localhost/'
})
const { window } = dom
for (const key of ['window', 'document', 'navigator', 'HTMLElement', 'Element', 'Node', 'Event', 'FocusEvent', 'MouseEvent', 'getComputedStyle']) {
  if (!(key in globalThis) || key === 'window' || key === 'document') {
    globalThis[key] = key === 'window' ? window : key === 'document' ? window.document : window[key]
  }
}
window.matchMedia = (query) => ({
  matches: reduced && query.includes('prefers-reduced-motion'),
  media: query,
  onchange: null,
  addEventListener() {},
  removeEventListener() {},
  addListener() {},
  removeListener() {}
})
globalThis.matchMedia = window.matchMedia

const React = (await import('react')).default
const { createRoot } = await import('react-dom/client')
const { act } = await import('react')
const mod = await import('./plugin.js')

const payload = JSON.parse(process.argv[2] || '{}')
const root = createRoot(document.getElementById('root'))
const flush = (ms = 40) => new Promise((resolve) => setTimeout(resolve, ms))

const computedOf = (node) => {
  if (!node) return null
  const style = window.getComputedStyle(node)
  return {
    transition: style.transition || '',
    transitionDelay: style.transitionDelay || '',
    opacity: style.opacity,
    transform: style.transform || 'none',
    boxShadow: style.boxShadow || '',
    backgroundImage: style.backgroundImage || '',
    animationName: style.animationName || 'none',
    animationIterationCount: style.animationIterationCount || '1',
    outlineStyle: style.outlineStyle || '',
    state: node.getAttribute('data-cb-state'),
    inline: node.getAttribute('style') || ''
  }
}

const attributesOf = (node) => {
  if (!node) return null
  const out = {}
  for (const attr of node.attributes) out[attr.name] = attr.value
  return out
}

const actions = []
async function mountAction(variant, extra) {
  await act(async () => {
    root.render(
      React.createElement('div', { 'data-cb-scope': 'light', style: mod.cbScopeStyle('light') },
        React.createElement(mod.CbAction, Object.assign({ variant, onClick: () => {} }, extra || {}), 'Do the thing'))
    )
  })
  await flush()
  const button = document.querySelector('[data-cb-action]')
  const rest = computedOf(button)
  await act(async () => {
    button.dispatchEvent(new window.Event('pointerdown', { bubbles: true }))
  })
  await flush(10)
  const pressed = computedOf(button)
  await act(async () => {
    button.dispatchEvent(new window.Event('pointerup', { bubbles: true }))
  })
  await flush(10)
  const released = computedOf(button)
  actions.push({ variant, rest, pressed, released, attributes: attributesOf(button) })
}

async function mountPath(objectives) {
  const outline = { enrollment_id: 'enr_h152', objectives }
  const library = {
    items: [{
      enrollment_id: 'enr_h152',
      course_id: 'crs_h152',
      title: 'Small-engine maintenance',
      recipe: 'committed',
      revision: 3,
      evidence_summary: {
        total_objectives: objectives.length,
        independent: objectives.filter((o) => o.independent).length,
        review_due: 0,
        current_objective_id: objectives[1] ? objectives[1].objective_id : null
      },
      next_step: { kind: 'resume_lesson', label: 'Resume this lesson' }
    }]
  }
  const desk = mod.buildDeskModel({ library, outline, estimate: { status: 'ready', minutes: 20 } })
  await act(async () => {
    root.render(
      React.createElement('div', { 'data-cb-scope': 'light', style: mod.cbScopeStyle('light') },
        React.createElement(mod.CheckpointPath, { desk, onOpenSection: () => {} }))
    )
  })
  await flush()
  return [...document.querySelectorAll('[data-cb-path-node]')].map((node) => ({
    id: node.getAttribute('data-cb-path-node'),
    motion: node.getAttribute('data-cb-path-node-motion'),
    computed: computedOf(node),
    open: computedOf(node.querySelector('[data-cb-path-open]')),
    openAttributes: attributesOf(node.querySelector('button')),
    openInnerAttributes: attributesOf(node.querySelector('[data-cb-path-open]'))
  }))
}

async function mountVerdict(result) {
  await act(async () => {
    root.render(
      React.createElement('div', { 'data-cb-scope': 'light', style: mod.cbScopeStyle('light') },
        React.createElement(mod.PlayerVerdict, {
          result,
          criteria: [{ id: 'c1', met: true, observed: 'named the three parts' }],
          checklist: null,
          answer: 'compression, fuel, spark'
        }))
    )
  })
  await flush()
  const node = document.querySelector('[data-cb-player-feedback]')
  return { computed: computedOf(node), attributes: attributesOf(node), html: node.outerHTML.slice(0, 400) }
}

async function mountClose() {
  await act(async () => {
    root.render(
      React.createElement('div', { 'data-cb-scope': 'light', style: mod.cbScopeStyle('light') },
        React.createElement(mod.PlayerClose, {
          section: { ordinal: 2, title: 'Compression' },
          progress: { total_objectives: 4, independent: 2, review_due: 1 },
          onBack: () => {}
        }))
    )
  })
  await flush()
  const node = document.querySelector('[data-cb-player-close]')
  return { computed: computedOf(node), attributes: attributesOf(node) }
}

const objectives = []
for (let i = 1; i <= 10; i += 1) {
  objectives.push({
    objective_id: `obj_${String(i).padStart(2, '0')}`,
    ordinal: i,
    title: `Checkpoint ${i} of the route`,
    evidence_target: 'recall',
    state: i === 2 ? 'in_progress' : 'not_started',
    check_state: i === 1 ? 'closed' : 'none',
    attempt_count: 0,
    independent: i === 1,
    last_opened_at: null
  })
}

await mountAction('primary')
await mountAction('row')
await mountAction('primary', { disabled: true })
const path = await mountPath(objectives)
const verdict = await mountVerdict({ verdict: 'pass', evidence_class: 'assessed', criteria: [{ id: 'c1', met: true }] })
const notQuite = await mountVerdict({ verdict: 'fail', evidence_class: 'assessed', criteria: [{ id: 'c1', met: false, observed: 'missing the third part' }] })
const close = await mountClose()

const scope = mod.cbScopeStyle('light')
process.stdout.write(JSON.stringify({
  reduced,
  scopeTokens: Object.fromEntries(Object.entries(scope).filter(([key]) => key.startsWith('--cb-dur') || key === '--cb-ease')),
  motion: {
    beats: mod.CB_MOTION_BEATS,
    ceiling: mod.CB_MOTION_CEILING_MS,
    ladder: mod.CB_MOTION
  },
  reducedMotion: mod.cbMotionFor('reduced').transition('transform', 'press'),
  fullMotion: mod.cbMotionFor('full').transition('transform', 'press'),
  actions,
  path,
  verdict,
  notQuite,
  close
}))
"""


def objective(objective_id: str, ordinal: int, **kwargs) -> dict:
    return {"objective_id": objective_id, "ordinal": ordinal, "title": f"Checkpoint {ordinal}", **kwargs}


MS = re.compile(r"(-?\d+(?:\.\d+)?)(ms|s)\b")
TRANSITION = re.compile(r"([a-z-]+)\s+var\((--cb-dur-[a-z]+)\)")


def parse_transition(value: str) -> list[tuple[str, str]]:
    """Return (property, duration-token) pairs from a computed transition shorthand."""
    pairs = []
    for chunk in value.split(","):
        match = TRANSITION.search(chunk.strip())
        if match:
            pairs.append((match.group(1), match.group(2)))
    return pairs


def ms_of(token: str) -> int:
    match = re.match(r"^(-?\d+(?:\.\d+)?)(ms|s)$", token)
    assert match, f"unreadable duration {token!r}"
    number = float(match.group(1))
    return int(round(number * 1000)) if match.group(2) == "s" else int(round(number))


class MotionHarness(unittest.TestCase):
    reduced = False
    payload: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom/jsdom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-h152-")
        cls.root = Path(cls.tmp.name)
        (cls.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (cls.root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        node_modules = cls.root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler", "jsdom"):
            source = modules / name
            if not source.is_dir():
                # jsdom lives at the app root, one level above the react/react-dom bundle.
                source = modules.parent / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}), encoding="utf-8"
        )
        (sdk / "index.js").write_text(STUB, encoding="utf-8")
        cls.payload = cls.run_render(reduced=cls.reduced)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    @classmethod
    def run_render(cls, reduced: bool) -> dict:
        env = dict(os.environ)
        env["CB_TEST_REDUCED"] = "1" if reduced else "0"
        result = subprocess.run(
            ["node", str(cls.root / "harness.mjs"), "{}"],
            cwd=cls.root,
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        if result.returncode != 0:
            raise AssertionError(f"harness failed: {result.stderr[-2000:]}")
        return json.loads(result.stdout)


class FullMotionTest(MotionHarness):
    """The default posture: four beats, each inside its ladder rung, each transform/opacity only."""

    reduced = False

    def test_the_ladder_is_one_table_with_four_beats_and_a_ceiling(self) -> None:
        motion = self.payload["motion"]
        self.assertEqual(motion["beats"], ["press", "route", "verdict", "complete"])
        self.assertEqual(motion["ceiling"], 600)
        ladder = motion["ladder"]
        self.assertTrue(90 <= ms_of(ladder["press"]) <= 120, ladder["press"])
        # H-189 raised the route/edge beat from 180 ms to 280 ms so the trailhead's one arrival
        # sits inside the card's authored 240-320 ms window. It is still one ladder rung, still
        # under the 600 ms ceiling, and the reduced-motion frame is still static.
        self.assertTrue(240 <= ms_of(ladder["route"]) <= 320, ladder["route"])
        self.assertTrue(120 <= ms_of(ladder["verdict"]) <= 180, ladder["verdict"])
        self.assertLessEqual(ms_of(ladder["complete"]), 600, ladder["complete"])
        self.assertLessEqual(ms_of(ladder["fade"]), 120, ladder["fade"])
        for name, value in ladder.items():
            if name in ("ease",):
                continue
            self.assertLessEqual(ms_of(value), 600, f"{name} outruns the ceiling")

    def test_the_scope_root_carries_the_tokens_the_transitions_reference(self) -> None:
        tokens = self.payload["scopeTokens"]
        ladder = self.payload["motion"]["ladder"]
        for beat in ("press", "route", "verdict", "complete", "fade"):
            self.assertEqual(tokens[f"--cb-dur-{beat}"], ladder[beat])
        self.assertEqual(tokens["--cb-ease"], ladder["ease"])

    def test_every_computed_transition_is_transform_opacity_or_colour(self) -> None:
        allowed = {"transform", "opacity", "border-color", "color", "background-color"}
        seen = 0
        blocks = [item["rest"] for item in self.payload["actions"]]
        blocks += [item["computed"] for item in self.payload["path"]]
        blocks += [self.payload["verdict"]["computed"], self.payload["notQuite"]["computed"], self.payload["close"]["computed"]]
        for computed in blocks:
            for prop, token in parse_transition(computed["transition"]):
                seen += 1
                self.assertIn(prop, allowed, computed["transition"])
                self.assertIn(token, {"--cb-dur-press", "--cb-dur-route", "--cb-dur-verdict", "--cb-dur-complete", "--cb-dur-fade"})
        self.assertGreater(seen, 0, "no beat painted a transition at all")

    def test_no_shadow_gradient_or_repeating_animation(self) -> None:
        blocks = [item["rest"] for item in self.payload["actions"]]
        blocks += [item["computed"] for item in self.payload["path"]]
        blocks += [self.payload["verdict"]["computed"], self.payload["close"]["computed"]]
        for computed in blocks:
            self.assertIn(computed["boxShadow"], ("", "none"), computed["boxShadow"])
            self.assertNotIn("gradient", computed["backgroundImage"])
            self.assertIn(computed["animationName"], ("none", ""), computed["animationName"])
            self.assertIn(computed["animationIterationCount"], ("1", ""), computed["animationIterationCount"])

    def test_press_is_one_hundred_milliseconds_of_translate_and_returns_to_rest(self) -> None:
        primary = self.payload["actions"][0]
        self.assertEqual(primary["rest"]["state"], "rest")
        self.assertEqual(primary["pressed"]["state"], "pressed")
        self.assertEqual(primary["released"]["state"], "rest")
        self.assertEqual(primary["released"]["transform"], "none")
        pairs = parse_transition(primary["pressed"]["transition"])
        self.assertIn(("transform", "--cb-dur-press"), pairs)
        self.assertIn("translateY(1px)", primary["pressed"]["transform"])

    def test_a_disabled_action_never_animates_and_says_so(self) -> None:
        disabled = self.payload["actions"][2]
        self.assertEqual(disabled["rest"]["state"], "disabled")
        self.assertEqual(disabled["pressed"]["state"], "disabled")
        self.assertNotIn("translateY", disabled["pressed"]["transform"])

    def test_the_row_primitive_carries_data_cb_state(self) -> None:
        row = self.payload["actions"][1]
        self.assertEqual(row["attributes"].get("data-cb-action"), "row")
        self.assertEqual(row["rest"]["state"], "rest")
        self.assertIn("translateY(1px)", row["pressed"]["transform"])

    def test_route_settle_is_eight_nodes_at_forty_milliseconds_and_no_more(self) -> None:
        nodes = self.payload["path"]
        self.assertEqual(len(nodes), 10)
        beat = [node for node in nodes if node["motion"] == "settle"]
        self.assertEqual(len(beat), 8, "the route beat must stop at eight nodes")
        self.assertEqual([node["motion"] for node in nodes[8:]], ["static", "static"])
        delays = [ms_of(parse_delay(node["computed"]["transitionDelay"])) for node in beat]
        self.assertEqual(delays, [0, 40, 80, 120, 160, 200, 240, 280])
        for node in beat:
            self.assertEqual(node["computed"]["opacity"], "1")
            self.assertEqual(node["computed"]["transform"], "none")
            pairs = parse_transition(node["computed"]["transition"])
            self.assertEqual(pairs, [("opacity", "--cb-dur-route"), ("transform", "--cb-dur-route")])
        for node in nodes[8:]:
            self.assertEqual(node["computed"]["transition"], "")
            self.assertEqual(node["computed"]["opacity"], "1")

    def test_every_route_node_is_a_row_action_with_a_state(self) -> None:
        for node in self.payload["path"]:
            self.assertEqual(node["openAttributes"].get("data-cb-action"), "row")
            self.assertIn(node["openAttributes"].get("data-cb-state"), ("rest", "selected"))

    def test_the_verdict_beat_is_caused_by_a_graded_result(self) -> None:
        correct = self.payload["verdict"]
        self.assertEqual(correct["attributes"]["data-cb-state"], "correct")
        self.assertEqual(correct["attributes"]["data-cb-player-beat"], "verdict")
        self.assertEqual(correct["computed"]["opacity"], "1")
        pairs = parse_transition(correct["computed"]["transition"])
        self.assertEqual(pairs, [("opacity", "--cb-dur-verdict"), ("transform", "--cb-dur-verdict")])
        not_quite = self.payload["notQuite"]
        self.assertEqual(not_quite["attributes"]["data-cb-state"], "not_quite")

    def test_completion_is_one_six_hundred_millisecond_beat(self) -> None:
        close = self.payload["close"]
        self.assertEqual(close["attributes"]["data-cb-state"], "complete")
        self.assertEqual(close["attributes"]["data-cb-player-beat"], "complete")
        self.assertEqual(close["computed"]["opacity"], "1")
        pairs = parse_transition(close["computed"]["transition"])
        self.assertEqual(pairs, [("opacity", "--cb-dur-complete"), ("transform", "--cb-dur-complete")])

    def test_focus_is_never_part_of_a_beat(self) -> None:
        blocks = [item["rest"] for item in self.payload["actions"]]
        blocks += [item["computed"] for item in self.payload["path"]]
        blocks += [self.payload["verdict"]["computed"], self.payload["close"]["computed"]]
        for computed in blocks:
            self.assertNotIn("outline", computed["transition"])
            self.assertNotIn("shadow", computed["transition"])
            self.assertNotIn("outline", computed["inline"])


def parse_delay(value: str) -> str:
    return (value or "0s").split(",")[0].strip()


class ReducedMotionTest(MotionHarness):
    """Reduced motion keeps the state change and drops the travel: nothing is temporally animated."""

    reduced = True

    def test_the_preference_reaches_the_root(self) -> None:
        self.assertTrue(self.payload["reduced"])
        self.assertIsNone(self.payload["reducedMotion"])

    def test_every_beat_is_static_and_still_shows_its_state(self) -> None:
        blocks = [item["rest"] for item in self.payload["actions"]]
        blocks += [item["computed"] for item in self.payload["path"]]
        blocks += [self.payload["verdict"]["computed"], self.payload["close"]["computed"]]
        for computed in blocks:
            self.assertIn(computed["transition"], ("", "none"), computed["transition"])
            self.assertEqual(computed["opacity"], "1")
            self.assertEqual(computed["transform"], "none")
        self.assertEqual(self.payload["actions"][0]["pressed"]["state"], "pressed")
        self.assertEqual(self.payload["verdict"]["attributes"]["data-cb-player-beat"], "static")
        self.assertEqual(self.payload["close"]["attributes"]["data-cb-player-beat"], "static")

    def test_the_route_has_no_stagger_under_reduced_motion(self) -> None:
        for node in self.payload["path"]:
            self.assertEqual(node["motion"], "static")
            self.assertIn(node["computed"]["transitionDelay"], ("", "0s"))


class MotionSourceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = PLUGIN_JS.read_text(encoding="utf-8")

    def test_one_motion_table_and_one_hook_supply_every_duration(self) -> None:
        self.assertEqual(self.source.count("const CB_MOTION = Object.freeze({"), 1)
        self.assertEqual(self.source.count("function useCbMotion()"), 1)
        # Every transition the module authors comes through the hook, never as a literal duration.
        literals = re.findall(r"transition:\s*'([^']+)'", self.source)
        self.assertEqual(literals, ["none"])
        # More than one call site is allowed (press, route settle, the current stop's finite
        # cycle); what matters is that each names a beat, which the duration test above proves.
        self.assertGreaterEqual(self.source.count("motion.transition("), 2)

    def test_no_keyframes_no_animation_no_shadow_no_gradient(self) -> None:
        self.assertNotIn("@keyframes", self.source)
        self.assertNotIn("keyframes", self.source)
        self.assertNotIn("animation:", self.source)
        self.assertNotIn("animationName", self.source)
        self.assertNotIn("boxShadow", self.source)
        self.assertNotIn("box-shadow", self.source)
        self.assertNotIn("linear-gradient", self.source)
        self.assertNotIn("radial-gradient", self.source)

    def test_no_surface_named_a_beat_outside_the_ladder(self) -> None:
        ladder = re.findall(r"var\(--cb-dur-([a-z]+)\)", self.source)
        self.assertTrue(ladder)
        for name in ladder:
            self.assertIn(name, ("press", "route", "verdict", "complete", "fade"), name)
        # The four values live in one table; a second copy would drift.
        durations = re.findall(r"^\s+(press|route|verdict|complete|fade): '(\d+ms)'", self.source, re.M)
        self.assertEqual(
            durations,
            [("press", "100ms"), ("route", "280ms"), ("verdict", "160ms"), ("complete", "600ms"), ("fade", "120ms")],
        )

    def test_the_learner_motion_setting_reaches_the_one_hook(self) -> None:
        # H-179: the settings sheet's `Reduce motion` publishes into the one motion hook, so the
        # switch has a real reader below the route instead of only painting `data-cb-motion`.
        self.assertIn("function publishCbMotion(motion)", self.source)
        self.assertIn("cbMotionListeners.add(sync)", self.source)
        route = self.source[self.source.index("function CoursebookPage()"):]
        route = route[: route.index("const online = useOnline()")]
        self.assertIn("publishCbMotion(cbMotion)", route)
        pane = self.source[self.source.index("function CoursebookPane()"):]
        pane = pane[: pane.index("const scopeProfile = currentScope().profile")]
        self.assertIn("publishCbMotion(cbMotion)", pane)

    def test_the_only_utility_transition_is_colour_only(self) -> None:
        utilities = re.findall(r"transition-(colors|transform|opacity|all)\b", self.source)
        # H-179 replaced the create card's colour-only utility with inline token borders, so the
        # inventory may be empty — but nothing but a colour transition may ever appear.
        for name in utilities:
            self.assertEqual(name, "colors", utilities)

    def test_no_decorative_beat_survives(self) -> None:
        # Out of scope by card: seal draw, beacon loop, hover lift, parallax, confetti, shake.
        for banned in ("seal-draw", "beacon", "parallax", "confetti", "particle", "shake", "hover-lift", "count-up"):
            self.assertNotIn(banned, self.source, banned)


class MotionEvidenceTest(unittest.TestCase):
    """The live capture is the proof this suite cannot give; it must exist and parse."""

    EVIDENCE = ROOT / "docs" / "h152-shots" / "measurements.json"

    def test_live_capture_recorded_the_beats(self) -> None:
        if not self.EVIDENCE.is_file():
            self.skipTest("live motion capture has not been run in this tree")
        data = json.loads(self.EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(data.get("motion_preference"), "full")
        self.assertEqual(data.get("reduced_motion_preference"), "reduced")
        digest = data.get("digest", {})
        # The plugin authors no keyframes and no animation at all; the 32 keyframe rules the page
        # carries are the host's own stylesheet (codicon-spin, scroll-fade, starmap-twinkle…).
        self.assertEqual(digest.get("plugin_animations"), 0)
        self.assertEqual(digest.get("seal_draw"), 0)
        self.assertEqual(digest.get("plugin_shadows", 0), 0)
        self.assertGreater(digest.get("keyframes", 0), 0, "the host stylesheet should still be there")
        for beat in ("press", "route"):
            samples = data.get("beats", {}).get(beat, [])
            self.assertTrue(samples, f"no live sample for the {beat} beat")
        for sample in data.get("measured", {}).get("durations_ms", []):
            self.assertLessEqual(sample, 600, sample)
        reduced = data.get("reduced_motion", {})
        self.assertEqual(reduced.get("plugin_animated_elements"), 0)
        self.assertEqual(reduced.get("path_in_beat"), 0)
        self.assertEqual(data.get("overflow", {}).get("page"), 0)
        self.assertEqual(data.get("overflow", {}).get("route"), 0)
        # The verdict + completion beats are render-proven only; the capture must say so rather
        # than leave an empty list that reads like a pass.
        if not data.get("beats", {}).get("verdict"):
            self.assertTrue(data.get("player", {}).get("reason"), "the live gap must be recorded")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
