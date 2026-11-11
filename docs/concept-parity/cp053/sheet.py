"""Compose the CP-053 side-by-side sheet: shipped render (left) | binding reference (right)."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

render, reference, out = (Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
a = Image.open(render).convert("RGB")
b = Image.open(reference).convert("RGB")
if a.size != b.size:
    raise SystemExit(f"size mismatch: {a.size} vs {b.size}")
w, h = a.size
sheet = Image.new("RGB", (w * 2, h + 28), (24, 22, 18))
sheet.paste(a, (0, 28))
sheet.paste(b, (w, 28))
draw = ImageDraw.Draw(sheet)
draw.text((12, 9), "shipped HomeScene — desktop/plugin.js @ 1344x768", fill=(240, 232, 214))
draw.text((w + 12, 9), "binding reference — docs/concept-parity/refs/home.png", fill=(240, 232, 214))
out.parent.mkdir(parents=True, exist_ok=True)
sheet.save(out)
print(f"wrote {out} ({sheet.size[0]}x{sheet.size[1]})")
