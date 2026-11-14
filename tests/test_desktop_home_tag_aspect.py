"""VQ-011 — the Home tag plate paints the square kraft tag at its own aspect.

The card's defect: `[data-cb-home-scene-tag]` painted `assets/objects/tag.webp` (a 256x256 master)
with `background-size: 100% 100%` into a 164x88 box, so the kraft body was squashed 1.0x by 0.34x
and the rope hole and corners were distorted.

This test pins the composition twice:

  * statically — the stylesheet's box is square and `background-size` is the single keyword
    `contain`, so a future `100% 100%` (or any other two-value, box-derived size) fails here;
  * in a real browser — `design/home-scene.html` (the module-rendered proof D-010 accepts) is
    painted in headless Chromium at 1344x768 and 900x768 and the tag's `getBoundingClientRect()`
    must match the file's aspect ratio within 1%.

Host frames are not part of this test: D-010 records that the generated proof stands in for a live
Desktop capture, and forbids claiming a live install from it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROOF = ROOT / "design" / "home-scene.html"
MANIFEST = ROOT / "assets" / "objects" / "manifest.json"
SOURCE = ROOT / "desktop" / "src" / "76-v3-scope.js"

MEASURE = r"""
import { spawn } from 'node:child_process'
import fs from 'node:fs'

const [htmlPath, widthsJson, userDataDir] = process.argv.slice(2)
const widths = JSON.parse(widthsJson)
const port = 9700 + (process.pid % 200)
const chromium = spawn('chromium', [
  '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
  `--remote-debugging-port=${port}`, `--user-data-dir=${userDataDir}`, 'about:blank'
], { stdio: 'ignore' })
const sleep = (ms) => new Promise((done) => setTimeout(done, ms))
let targets = null
for (let attempt = 0; attempt < 80; attempt += 1) {
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
await send('Page.enable')
await send('Runtime.enable')

const expression = `(() => {
  const tag = document.querySelector('[data-cb-home-scene-tag]')
  if (!tag) return { missing: true }
  const rect = tag.getBoundingClientRect()
  const style = getComputedStyle(tag)
  return {
    missing: false,
    rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height, top: rect.top, left: rect.left },
    backgroundSize: style.backgroundSize,
    backgroundImage: style.backgroundImage.slice(0, 64),
    backgroundColour: style.backgroundColor,
    boxShadow: style.boxShadow,
    text: tag.textContent,
    ratio: rect.width / rect.height,
    sceneWidth: document.querySelector('[data-cb-home-scene]').getBoundingClientRect().width
  }
})()`

const out = []
for (const width of widths) {
  await send('Emulation.setDeviceMetricsOverride', { width, height: 768, deviceScaleFactor: 1, mobile: false })
  await send('Page.navigate', { url: `file://${htmlPath}` })
  await sleep(600)
  // The proof page is authored at 1344 px. On a narrower viewport it stays 1344 px wide and
  // scrolls; bring the tag (left 790) into the 900 px frame before measuring/screenshotting.
  await send('Runtime.evaluate', { expression: 'window.scrollTo(600, 0)' })
  await sleep(150)
  const answer = await send('Runtime.evaluate', { expression, returnByValue: true })
  const value = answer.result.value
  const shot = await send('Page.captureScreenshot', { format: 'png' })
  const png = Buffer.from(shot.data, 'base64')
  const pngPath = `${userDataDir}/frame-${width}.png`
  fs.writeFileSync(pngPath, png)
  out.push({ width, png: pngPath, ...value })
}
socket.close()
chromium.kill()
process.stdout.write(JSON.stringify(out))
"""


def _manifest_tag_size() -> tuple[int, int]:
    rows = json.loads(MANIFEST.read_text(encoding="utf-8"))
    row = next(item for item in rows if item.get("role") == "object.tag")
    return int(row["width"]), int(row["height"])


@unittest.skipIf(shutil.which("node") is None, "node is required for the browser measurement")
@unittest.skipIf(shutil.which("chromium") is None, "chromium is required to paint the proof")
class HomeTagAspectTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not PROOF.exists():
            raise unittest.SkipTest("design/home-scene.html has not been generated")

    def measure(self) -> list[dict]:
        with tempfile.TemporaryDirectory(prefix="vq011-tag-aspect-") as tmp:
            root = Path(tmp)
            (root / "measure.mjs").write_text(MEASURE, encoding="utf-8")
            result = subprocess.run(
                ["node", str(root / "measure.mjs"), str(PROOF), json.dumps([1344, 900]), str(root / "chromium")],
                cwd=root, capture_output=True, text=True, timeout=300,
            )
        if result.returncode != 0:
            raise AssertionError(result.stderr[-4000:])
        return json.loads(result.stdout)

    def test_the_master_is_still_square(self) -> None:
        width, height = _manifest_tag_size()
        self.assertEqual(width, height, "VQ-011's plate geometry assumes the square tag master")

    def test_the_stylesheet_never_sets_a_box_derived_two_value_size(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        block = source.split("[data-cb-home-scene-tag]", 1)[1].split("}", 1)[0]
        self.assertNotIn("100% 100%", block, "the squash is back on the tag selector")
        sizes = [line.split(":", 1)[1].strip().rstrip(";")
                 for line in block.splitlines() if line.strip().startswith("background-size")]
        self.assertEqual(sizes, ["contain"], f"the tag plate size must stay a single keyword: {sizes}")

    def test_the_painted_plate_matches_the_file_aspect_at_1344_and_900(self) -> None:
        file_width, file_height = _manifest_tag_size()
        file_ratio = file_width / file_height
        frames = self.measure()
        self.assertEqual([frame["width"] for frame in frames], [1344, 900])
        for frame in frames:
            with self.subTest(width=frame["width"]):
                self.assertFalse(frame["missing"], "the proof no longer paints the Home tag plate")
                self.assertEqual(frame["backgroundSize"], "contain",
                                 "the tag must paint at its own aspect, not a box-derived size")
                # A rotation still yields a square AABB for a square box, so the aspect pin holds
                # whatever angle the plate is tilted to.
                self.assertAlmostEqual(frame["ratio"], file_ratio, delta=file_ratio * 0.01,
                                       msg=f"tag box is {frame['rect']['width']}x{frame['rect']['height']}")
                self.assertIn("New course", frame["text"], "the words stay DOM type")
                # A solid plate or a square shadow behind a transparent-corner object would paint
                # the corners; neither may come back.
                self.assertIn("rgba(0, 0, 0, 0)", frame["backgroundColour"],
                              f"transparent corners are painted over: {frame['backgroundColour']}")
                self.assertIn("none", frame["boxShadow"], f"a box shadow paints the corners: {frame['boxShadow']}")
                self.assertTrue(frame["backgroundImage"].startswith('url("data:image/'),
                                "the plate no longer paints the shipped tag object")


if __name__ == "__main__":
    unittest.main()
