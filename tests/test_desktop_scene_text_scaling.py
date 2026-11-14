"""CP-TEXT-SCALE — the wide Home scene's lettering stays inside the sign when its type is enlarged.

The defect this gate closes (`t_ac0885cd`): the pinned 1344x768 scene keeps a 520x162 px sign, but
its headline, subline, CTA labels and card titles are sized from the root-relative token scale
(`clamp(2.5rem, 1.5rem + 3cqi, 4rem)` and friends). A browser at its 125 % default text size
therefore pushes the CTA row off the sign and onto the painted wall; at 200 % the row sits on the
course board row and the two-line card title is clipped by the fixed 140 px card.

The rule the scene must hold, measured on the rendered proof at 1344 with `html` font-size set to
16, 20, 24 and 32 px in turn:

  * ``[data-cb-home-scene-cta]``'s box closes at or above ``[data-cb-home-scene-panel]``'s box
    (the CTA is inside the sign, not under it);
  * the CTA box does not intersect ``[data-cb-home-scene-cards]`` (the buttons never sit on the
    board row);
  * every ``[data-cb-home-scene-title]`` has ``scrollHeight <= clientHeight`` (no card title is
    clipped by the card's own ``overflow: hidden``).

Two things are pinned so the browser check cannot pass by accident:

  * **The 100 % frame does not move.** The scene's type is capped, not re-valued: at a 16 px root
    each ``--cb3-text-*`` step inside the scene resolves to the step the token scale already
    produced there. The static pin below recomputes those caps from ``CB_TOKENS_V3_JSON`` (never
    from a literal copied into this file), so a cap that is looser or tighter than the token's own
    16 px value fails.
  * **The measurement is tied to the shipped module.** The proof page names the current
    ``desktop/plugin.js`` sha; a stale page is refused rather than measured.

Host chrome is not in scope: this is the generated proof page, not a Desktop capture (no host, no
backend, no chat rail). The scene is a pinned composition, so the gate proves the sign holds its
copy at every text size a browser can ask for instead of asking the sign to grow over the plate.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.cb_source_scope import (
    PLUGIN_JS,
    V3_CSS_CONST,
    V3_TOKEN_CONST,
    declarations,
    literal_text,
    split_selectors,
    style_rules,
)

ROOT = Path(__file__).resolve().parent.parent
PROOF = ROOT / "design" / "home-scene.html"

#: The route container's own width for the binding frame (the scene is authored to 1344).
DESIGN_WIDTH = 1344.0
#: A browser's 100 % root. The cap must equal the token's value here, so 100 % is byte-identical.
ROOT_16 = 16.0
#: The four root sizes the acceptance names: 100 %, 125 %, 150 %, 200 %.
ROOT_SIZES = (16, 20, 24, 32)

#: The scene subtree and the token steps it paints with.
SCENE_SELECTOR = "[data-cb-v3] [data-cb-home-scene]"
SCENE_STEPS = ("display", "lead", "meta", "heading")

MEASURE = r"""
import { spawn } from 'node:child_process'
import fs from 'node:fs'

const [htmlPath, sizesJson, userDataDir] = process.argv.slice(2)
const sizes = JSON.parse(sizesJson)
const port = 9900 + (process.pid % 90)
const chromium = spawn('chromium', [
  '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
  '--force-device-scale-factor=1',
  `--remote-debugging-port=${port}`, `--user-data-dir=${userDataDir}`, 'about:blank'
], { stdio: 'ignore' })
const sleep = (ms) => new Promise((done) => setTimeout(done, ms))
let targets = null
for (let attempt = 0; attempt < 120; attempt += 1) {
  try {
    targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json()
    if (targets.length) break
  } catch (error) { targets = null }
  await sleep(250)
}
if (!targets || !targets.length) { chromium.kill(); throw new Error('chromium CDP did not open') }
const page = targets.find((entry) => entry.type === 'page')
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((done, fail) => {
  socket.addEventListener('open', done, { once: true })
  socket.addEventListener('error', fail, { once: true })
})
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data)
  if (message.id && pending.has(message.id)) {
    const entry = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) entry.fail(new Error(JSON.stringify(message.error)))
    else entry.done(message.result)
  }
})
const send = (method, params = {}) => new Promise((done, fail) => {
  const id = nextId++
  pending.set(id, { done, fail })
  socket.send(JSON.stringify({ id, method, params }))
})
const evaluate = async (expression) => {
  const answer = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  if (answer.exceptionDetails) throw new Error(JSON.stringify(answer.exceptionDetails))
  return answer.result.value
}
await send('Page.enable')
await send('Runtime.enable')
await send('Emulation.setDeviceMetricsOverride', { width: 1344, height: 768, deviceScaleFactor: 1, mobile: false })
await send('Page.navigate', { url: `file://${htmlPath}` })
await sleep(900)
await evaluate('document.fonts.ready.then(() => true)')
await evaluate('new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(() => done(true))))')

const out = []
for (const size of sizes) {
  const row = await evaluate(`(() => {
    document.documentElement.style.fontSize = '${size}px'
    const rect = (selector) => {
      const node = document.querySelector(selector)
      if (!node) return null
      const box = node.getBoundingClientRect()
      return { top: box.top, bottom: box.bottom, left: box.left, right: box.right, width: box.width, height: box.height }
    }
    const overlaps = (a, b) => Boolean(a && b) &&
      !(a.right <= b.left || a.left >= b.right || a.bottom <= b.top || a.top >= b.bottom)
    const cta = rect('[data-cb-home-scene-cta]')
    const panel = rect('[data-cb-home-scene-panel]')
    const cards = rect('[data-cb-home-scene-cards]')
    const titles = [...document.querySelectorAll('[data-cb-home-scene-title]')].map((node) => ({
      text: (node.textContent || '').trim(),
      scrollHeight: node.scrollHeight,
      clientHeight: node.clientHeight
    }))
    const font = (selector) => {
      const node = document.querySelector(selector)
      return node ? getComputedStyle(node).fontSize : null
    }
    return {
      root: getComputedStyle(document.documentElement).fontSize,
      cta, panel, cards,
      ctaClearsPanel: Boolean(cta && panel) && cta.bottom <= panel.bottom,
      ctaClearsCards: !overlaps(cta, cards),
      titles,
      type: {
        question: font('[data-cb-home-scene-question]'),
        subline: font('[data-cb-home-scene-subline]'),
        cta: font('[data-cb-home-scene-cta] button'),
        title: font('[data-cb-home-scene-title]')
      }
    }
  })()`)
  out.push(row)
}
socket.close()
chromium.kill()
process.stdout.write(JSON.stringify(out))
"""


def plugin_source() -> str:
    return PLUGIN_JS.read_text(encoding="utf-8")


def v3_css(source: str | None = None) -> str:
    text = literal_text(plugin_source() if source is None else source, V3_CSS_CONST)
    if text is None:
        raise AssertionError(f"desktop/plugin.js has no {V3_CSS_CONST} literal")
    return text


def v3_tokens(source: str | None = None) -> dict:
    text = literal_text(plugin_source() if source is None else source, V3_TOKEN_CONST)
    if text is None:
        raise AssertionError(f"desktop/plugin.js has no {V3_TOKEN_CONST} literal")
    return json.loads(text)


def rule_for(css: str, selector: str) -> dict[str, str]:
    """The declarations of the first style rule whose selector list carries ``selector``.

    The base rule is the first one; a later ``@media`` block may re-declare the same selector for a
    different mode, so the base declarations are what a static pin must read.
    """
    found = [(prelude, body) for prelude, body in style_rules(css)
             if selector in split_selectors(prelude)]
    if not found:
        raise AssertionError(f"the stylesheet has no rule for {selector!r}")
    return dict(declarations(found[0][1]))


def token_px(scale: str, root: float = ROOT_16, container: float = DESIGN_WIDTH) -> float:
    """A contract type step's px value at ``root`` on a ``container``-wide route.

    The contract writes a step as either ``1.25rem`` or ``clamp(2.5rem, 1.5rem + 3cqi, 4rem)``;
    ``cqi`` resolves against the route container, ``rem`` against the root. The caps this gate
    pins are these values at a 100 % root, which is exactly the frame the composition is pinned to.
    """
    value = scale.strip()
    simple = re.fullmatch(r"([\d.]+)rem", value)
    if simple:
        return float(simple.group(1)) * root
    clamp = re.fullmatch(
        r"clamp\(\s*([\d.]+)rem\s*,\s*([\d.]+)rem\s*\+\s*([\d.]+)cqi\s*,\s*([\d.]+)rem\s*\)",
        value,
    )
    if not clamp:
        raise AssertionError(f"the contract's type scale has a shape this gate cannot read: {value!r}")
    floor, base, cqi, ceiling = (float(part) for part in clamp.groups())
    preferred = base * root + cqi / 100.0 * container
    return max(floor * root, min(preferred, ceiling * root))


class SceneTypeCapTest(unittest.TestCase):
    """The static half: the scene's type is capped to the sign, and the cap is the token's 16 px value."""

    def setUp(self) -> None:
        self.source = plugin_source()
        self.css = v3_css(self.source)
        self.tokens = v3_tokens(self.source)
        self.scale = self.tokens["type"]["scale"]
        self.scene = rule_for(self.css, SCENE_SELECTOR)

    def cap(self, step: str) -> float:
        declaration = self.scene.get(f"--cb3-text-{step}", "")
        match = re.fullmatch(
            r"min\(\s*var\(\s*--cb3-scene-type-"
            + re.escape(step)
            + r"\s*\)\s*,\s*([\d.]+)px\s*\)",
            declaration.strip(),
        )
        if match is None:
            raise AssertionError(
                f"the scene does not cap --cb3-text-{step} from its own box: {declaration!r}"
            )
        return float(match.group(1))

    def test_every_scene_type_step_is_capped_from_the_scene_box(self) -> None:
        self.assertEqual(
            [step for step in SCENE_STEPS if f"--cb3-text-{step}" in self.scene],
            list(SCENE_STEPS),
            "the scene no longer overrides every type step it paints with; a new step would scale "
            "from the root again and reintroduce the overflow",
        )
        for step in SCENE_STEPS:
            with self.subTest(step=step):
                self.cap(step)

    def test_each_cap_is_the_step_the_token_scale_produced_at_a_100_percent_root(self) -> None:
        # The composition is pinned at 100 %, so the cap may not bite there: a tighter cap moves the
        # frame, a looser one lets the root scale past the sign again.
        for step in SCENE_STEPS:
            with self.subTest(step=step):
                expected = token_px(self.scale[step])
                self.assertAlmostEqual(
                    self.cap(step), expected, places=2,
                    msg=f"--cb3-text-{step} caps at {self.cap(step)}px but the token yields "
                        f"{expected}px at a 16 px root on a {int(DESIGN_WIDTH)} px route",
                )

    def test_the_cap_alias_reads_the_route_token_before_the_scene_redefines_it(self) -> None:
        # A scene rule that wrote `--cb3-text-display: min(var(--cb3-text-display), 64px)` would be a
        # cycle and resolve to nothing, so the inherited token is aliased one level up.
        route = rule_for(self.css, "[data-cb-v3]")
        for step in SCENE_STEPS:
            with self.subTest(step=step):
                self.assertEqual(
                    route.get(f"--cb3-scene-type-{step}", "").strip(),
                    f"var(--cb3-text-{step})",
                    "the scene cap does not read the route's own token",
                )


@unittest.skipIf(shutil.which("node") is None, "node is required for the browser measurement")
@unittest.skipIf(shutil.which("chromium") is None, "chromium is required to paint the proof")
class SceneTextScalingTest(unittest.TestCase):
    """The measured half: the acceptance, on the rendered proof at 16/20/24/32 px roots."""

    @classmethod
    def setUpClass(cls) -> None:
        if not PROOF.exists():
            raise unittest.SkipTest("design/home-scene.html has not been generated")
        cls.page = PROOF.read_text(encoding="utf-8")
        cls.module_sha = hashlib.sha256(PLUGIN_JS.read_bytes()).hexdigest()

    def measure(self) -> list[dict]:
        self.assertIn(
            f"desktop/plugin.js (sha256 {self.module_sha})",
            self.page,
            "the rendered proof does not name the current desktop/plugin.js; the measurement "
            "would not be tied to the shipped module",
        )
        with tempfile.TemporaryDirectory(prefix="cp-text-scale-") as tmp:
            root = Path(tmp)
            (root / "measure.mjs").write_text(MEASURE, encoding="utf-8")
            result = subprocess.run(
                ["node", str(root / "measure.mjs"), str(PROOF), json.dumps(list(ROOT_SIZES)),
                 str(root / "chromium")],
                cwd=root, capture_output=True, text=True, timeout=420,
            )
        if result.returncode != 0:
            raise AssertionError(f"the browser driver failed:\n{result.stderr[-4000:]}")
        return json.loads(result.stdout)

    def test_the_sign_holds_its_copy_at_every_enlarged_root(self) -> None:
        frames = self.measure()
        self.assertEqual([round(float(frame["root"].rstrip("px"))) for frame in frames],
                         list(ROOT_SIZES), "the driver did not apply every root size")
        problems = []
        for frame in frames:
            root = int(round(float(frame["root"].rstrip("px"))))
            if frame["panel"] is None or frame["cta"] is None or frame["cards"] is None:
                problems.append(f"{root} px root: the scene did not paint the sign, CTA or board row")
                continue
            if not frame["ctaClearsPanel"]:
                problems.append(
                    f"{root} px root: the CTA closes at {frame['cta']['bottom']:.2f} px but the sign "
                    f"closes at {frame['panel']['bottom']:.2f} px"
                )
            if not frame["ctaClearsCards"]:
                problems.append(
                    f"{root} px root: the CTA box ({frame['cta']['bottom']:.2f} px bottom) "
                    f"intersects the board row (top {frame['cards']['top']:.2f} px)"
                )
            for title in frame["titles"]:
                if title["scrollHeight"] > title["clientHeight"]:
                    problems.append(
                        f"{root} px root: the card title {title['text']!r} is clipped "
                        f"(scrollHeight {title['scrollHeight']} > clientHeight {title['clientHeight']})"
                    )
        self.assertEqual(problems, [], "\n".join(problems))

    def test_the_scene_type_does_not_grow_with_the_root(self) -> None:
        # The cap is the whole fix: every run the scene paints keeps its 100 % size, so the sign's
        # content box cannot be over-subscribed by an enlarged root.
        frames = self.measure()
        baseline = frames[0]["type"]
        self.assertEqual(len(frames), len(ROOT_SIZES))
        for frame in frames[1:]:
            with self.subTest(root=frame["root"]):
                self.assertEqual(
                    frame["type"], baseline,
                    "the scene's type grew with the root; the sign is a pinned composition and "
                    "cannot absorb it",
                )
        self.assertEqual(
            baseline,
            {"question": "64px", "subline": "20px", "cta": "20px", "title": "14px"},
            "the 100 % composition's type steps moved; the proof is no longer the pinned frame",
        )


if __name__ == "__main__":
    unittest.main()
