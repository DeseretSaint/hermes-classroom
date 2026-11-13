"""Measure the shipped wide Home at a 1250 px route in a real browser (E2E U9).

Renders `CoursebookHome` through the CP-053 proof generator (the same path `design/home-scene.html`
comes from), but at a 1250 px route with five courses, then injects one measurement script and reads
Chromium's own layout back with `--dump-dom`. The numbers printed here are the browser's boxes, not
a re-derivation: the scene's scaled box, the fox inside it, and the fifth course's door.

Usage:
  python3 audit/u9-probe.py [--width 1250] [--rows 5]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FIFTH = {
    "title": "Brake Service",
    "sections_total": 5,
    "sections_done": 0,
    "updated_at": "2026-11-06T09:00:00.000000+00:00",
}

PROBE = """
<script>
(() => {
  const r = (el) => {
    if (!el) return null
    const b = el.getBoundingClientRect()
    return { left: +b.left.toFixed(2), right: +b.right.toFixed(2), top: +b.top.toFixed(2),
             bottom: +b.bottom.toFixed(2), width: +b.width.toFixed(2), height: +b.height.toFixed(2) }
  }
  const scene = document.querySelector('[data-cb-home-scene]')
  const fit = document.querySelector('[data-cb-home-scene-fit]')
  const fox = document.querySelector('[data-cb-home-scene-fox]')
  const seeAll = document.querySelector('[data-cb-home-scene-see-all]')
  const cards = [...document.querySelectorAll('[data-cb-home-scene-card]')]
  const inner = scene ? [...scene.querySelectorAll('*')] : []
  const maxRight = inner.reduce((m, el) => Math.max(m, el.getBoundingClientRect().right), 0)
  const data = {
    windowWidth: window.innerWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    documentClientWidth: document.documentElement.clientWidth,
    fit: r(fit),
    scene: r(scene),
    sceneCssWidth: scene ? getComputedStyle(scene).width : null,
    sceneTransform: scene ? getComputedStyle(scene).transform : null,
    fox: r(fox),
    foxRightInsideScene: fox && scene ? r(fox).right <= r(scene).right : null,
    sceneContentMaxRight: +maxRight.toFixed(2),
    sceneContentOverflows: scene ? maxRight > r(scene).right + 0.5 : null,
    cardCount: cards.length,
    lastCard: cards.length ? r(cards[cards.length - 1]) : null,
    seeAll: r(seeAll),
    seeAllText: seeAll ? seeAll.textContent.trim() : null,
    seeAllInsideScene: seeAll && scene
      ? r(seeAll).right <= r(scene).right && r(seeAll).left >= r(scene).left
      : null
  }
  const pre = document.createElement('pre')
  pre.id = 'cb-probe'
  pre.textContent = JSON.stringify(data)
  document.body.appendChild(pre)
})()
</script>
"""


def generator():
    spec = importlib.util.spec_from_file_location("gen_home_proof", ROOT / "scripts" / "gen-home-proof.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=1250)
    parser.add_argument("--rows", type=int, default=5)
    args = parser.parse_args()

    proof = generator()
    rows = list(proof.ROWS)
    while len(rows) < args.rows:
        rows.append(dict(FIFTH))
    proof.ROWS = rows[: args.rows]

    with tempfile.TemporaryDirectory(prefix="cb-u9-probe-") as tmp:
        page = Path(tmp) / f"home-scene-{args.width}.html"
        proof.render(page, args.width, 900)
        probe = Path(tmp) / "probe.html"
        probe.write_text(
            page.read_text(encoding="utf-8").replace("</body>", PROBE + "</body>"), encoding="utf-8"
        )
        result = subprocess.run(
            [
                "chromium", "--headless=new", "--no-sandbox", "--disable-gpu",
                "--hide-scrollbars", "--force-device-scale-factor=1",
                f"--window-size={args.width},900", "--virtual-time-budget=4000",
                "--dump-dom", probe.as_uri(),
            ],
            capture_output=True, text=True, timeout=240,
        )
        match = re.search(r'<pre id="cb-probe">(.*?)</pre>', result.stdout, re.S)
        if not match:
            print(result.stderr[-2000:], file=sys.stderr)
            return 1
        data = json.loads(match.group(1))
        shot = ROOT / "audit" / "e2e-u9-u10" / f"home-{args.width}.png"
        subprocess.run(
            [
                "chromium", "--headless=new", "--no-sandbox", "--disable-gpu",
                "--hide-scrollbars", "--force-device-scale-factor=1",
                f"--window-size={args.width},900", "--virtual-time-budget=4000",
                f"--screenshot={shot}", probe.as_uri(),
            ],
            capture_output=True, timeout=240,
        )
        print(json.dumps(data, indent=2))
        print(f"screenshot: {shot}")
        record = ROOT / "audit" / "e2e-u9-u10" / f"measure-{args.width}.json"
        record.write_text(
            json.dumps(
                {
                    "surface": "desktop/plugin.js CoursebookHome at route width %d, %d courses" % (args.width, args.rows),
                    "capture": "chromium --headless=new --window-size=%d,900 --force-device-scale-factor=1" % args.width,
                    "render": "scripts/gen-home-proof.py at the same width (design/home-scene.html path)",
                    "screenshot": str(shot.relative_to(ROOT)),
                    **data,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"record: {record}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
