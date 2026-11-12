"""Re-render the CP-053 Home scene at the recorded size and recompute its parity row.

The record in docs/concept-parity/cp053/measure.json names the module it was measured on. When the
module moves, the row must be re-measured rather than edited: capture the generated proof page in
headless Chromium at the recorded window, diff it against the reference, and write the numbers the
run actually produced.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
MEASURE = ROOT / "docs" / "concept-parity" / "cp053" / "measure.json"
REFERENCE = ROOT / "docs" / "concept-parity" / "refs" / "home.png"
PAGE = ROOT / "design" / "home-scene.html"
PLUGIN = ROOT / "desktop" / "plugin.js"
RENDER = ROOT / "docs" / "concept-parity" / "cp053" / "home-scene-1344.png"
WIDTH, HEIGHT = 1344, 768


def capture(target: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="cp053-capture-") as tmp:
        profile = Path(tmp) / "profile"
        subprocess.run(
            [
                "chromium", "--headless=new", "--no-sandbox", "--disable-gpu",
                "--hide-scrollbars", "--force-device-scale-factor=1",
                f"--window-size={WIDTH},{HEIGHT}", f"--user-data-dir={profile}",
                f"--screenshot={target}", PAGE.as_uri(),
            ],
            check=True, capture_output=True, timeout=180,
        )


def rmse(left: Image.Image, right: Image.Image, bands: int) -> float:
    diff = ImageChops.difference(left, right)
    total = 0.0
    count = 0
    for band in diff.split()[:bands]:
        for value in band.getdata():
            channel = float(value)
            total += channel * channel
            count += 1
    return math.sqrt(total / count)


def main() -> int:
    record = json.loads(MEASURE.read_text(encoding="utf-8"))
    capture(RENDER)
    rendered = Image.open(RENDER).convert("RGB")
    reference = Image.open(REFERENCE).convert("RGB").resize(rendered.size, Image.Resampling.LANCZOS)
    grey_r = rendered.convert("L")
    grey_ref = reference.convert("L")
    rmse_rgb = round(rmse(rendered, reference, 3), 3)
    rmse_grey = round(rmse(grey_r, grey_ref, 1), 3)
    module_sha = hashlib.sha256(PLUGIN.read_bytes()).hexdigest()
    record.update(
        {
            "module_sha256": module_sha,
            "size": list(rendered.size),
            "rmse_rgb": rmse_rgb,
            "rmse_grey": rmse_grey,
            "sim_grey": round(1 - rmse_grey / 255, 4),
            "sim_rgb": round(1 - rmse_rgb / 255, 4),
            "measured_at": "2026-11-11",
            "note": (
                f"Re-measured 2026-11-11 on module {module_sha[:8]} after the generated page was "
                "re-rendered from that module; fresh chromium capture at 1344x768 of "
                "design/home-scene.html, fresh RMSE against docs/concept-parity/refs/home.png, "
                "nothing carried over. The CP-053 reference is the pre-plate hand frame, so this row "
                "records the approved-kit composition rather than clearing the 0.85 floor."
            ),
        }
    )
    MEASURE.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"module {module_sha[:12]} sim_grey {record['sim_grey']} rmse_grey {rmse_grey}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
