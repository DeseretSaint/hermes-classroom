"""CP-053 parity measure: RMSE and similarity for a render against the binding reference.

sim = 1 - RMSE/255 (both channels). Writes <out>/<label>-diff.png, <out>/<label>-sheet.png,
<out>/<label>.json. Both images are compared at their native pixels; a size mismatch is a hard
error (a parity claim on a resized frame is not a parity claim).
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

render, ref = sys.argv[1], sys.argv[2]
out = Path(sys.argv[3] if len(sys.argv) > 3 else "visual/compare")
label = sys.argv[4] if len(sys.argv) > 4 else Path(render).stem
out.mkdir(parents=True, exist_ok=True)

r_im = Image.open(render).convert("RGB")
f_im = Image.open(ref).convert("RGB")
if r_im.size != f_im.size:
    raise SystemExit(f"size mismatch: render {r_im.size} vs reference {f_im.size}")
a = np.asarray(r_im).astype(np.float64)
b = np.asarray(f_im).astype(np.float64)
d = a - b
rmse_rgb = float(np.sqrt((d ** 2).mean()))
ga, gb = a.mean(axis=2), b.mean(axis=2)
rmse_grey = float(np.sqrt(((ga - gb) ** 2).mean()))
sim_grey = 1 - rmse_grey / 255.0
sim_rgb = 1 - rmse_rgb / 255.0

# Per-band breakdown, so a pass can name its largest deltas.
bands = {"header": (0, 110), "hero": (110, 340), "cards": (340, 560),
         "shelf1": (555, 640), "objects": (600, 690), "shelf2": (680, 768)}
band_rows = {}
for name, (y0, y1) in bands.items():
    sub = ((ga[y0:y1] - gb[y0:y1]) ** 2)
    band_rows[name] = round(1 - float(np.sqrt(sub.mean())) / 255.0, 4)

diff = np.abs(d).mean(axis=2)
Image.fromarray(np.clip(diff * 2.2, 0, 255).astype(np.uint8)).save(out / f"{label}-diff.png")

report = {
    "render": str(render), "reference": str(ref), "size": list(r_im.size),
    "rmse_rgb": round(rmse_rgb, 3), "rmse_grey": round(rmse_grey, 3),
    "sim_grey": round(sim_grey, 4), "sim_rgb": round(sim_rgb, 4),
    "bands_sim_grey": band_rows,
    "diff": str(out / f"{label}-diff.png"),
}
(out / f"{label}.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
