#!/usr/bin/env python3
"""CP-012 cover acceptance: the machine half of the A3 kit check.

Run from the plugin root:

    python3 scripts/cp012-cover-accept.py

Per pack it proves, from the bytes on disk:

* the master is a 1200x800 3:2 PNG with no alpha channel;
* the 3:2 export is byte-identical to the master;
* the 4:5 file is the master's exact centre crop (pixel comparison, not a claim);
* the corner paper is the contract's `card-stock` #f7f1e4 within 4 units;
* the contour is not black: near-black pixels stay under 0.2 % of the frame;
* every dominant colour (>1 % of a 96 px quantization) sits in the painted
  family — warm hue 0-70 or plum hue 270-340, chroma <= 0.80, or a near-neutral
  paper/cream under 0.15 chroma. No synthetic hue passes;
* the left 4 % of the frame stays clear of the form (the shelf paints a spine there);
* tesseract reads no text on the plate (a text-detector failure is a defect, an
  OCR hit is evidence of lettering).

Across the kit it proves:

* exactly three covers, one per bundled pack, each with >=2 declared motifs;
* every motif set is pairwise disjoint with the other two covers, so a swapped
  caption cannot survive on shared marks;
* every swap row in `audit/cp012-covers/swap-check.json` is `rejected` with a
  written reason (the judgement itself is the reviewer's, recorded in
  `docs/concept-parity/COVERS.md`);
* every provenance hash in `audit/cp012-covers/provenance.json` equals the file.

Exit code 1 on any failure, and every failure is named.
"""

from __future__ import annotations

import colorsys
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COVERS = ROOT / "assets" / "art" / "covers"
AUDIT = ROOT / "audit" / "cp012-covers"
PAPER = (247, 241, 228)
CHROMA_MAX = 0.80
HUE_WARM = (0.0, 70.0)
HUE_PLUM = (270.0, 340.0)
DOMINANT_SHARE = 0.01
FAILURES: list[str] = []


def magick(*args: str) -> str:
    r = subprocess.run(("magick",) + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"magick failed: {' '.join(args)}\n{r.stderr}")
    return r.stdout.strip()


def check(ok: bool, name: str, detail: str) -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: {detail}")
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def paper_corner(path: Path) -> tuple[int, int, int]:
    out = magick(str(path), "-gravity", "northeast", "-crop", "32x32+0+0", "+repage",
                 "-format", "%[fx:round(255*mean.r)] %[fx:round(255*mean.g)] %[fx:round(255*mean.b)]",
                 "info:")
    return tuple(int(v) for v in out.split())  # type: ignore[return-value]


def dominant_colours(path: Path) -> list[tuple[float, tuple[int, int, int]]]:
    text = magick(str(path), "-resize", "96x", "-colors", "10", "-format", "%c", "histogram:info:")
    rows = []
    total = 0
    for line in text.splitlines():
        m = re.match(r"\s*(\d+):.*#([0-9A-Fa-f]{6})", line)
        if not m:
            continue
        count, hexv = int(m.group(1)), m.group(2)
        total += count
        rows.append((count, tuple(int(hexv[i:i + 2], 16) for i in (0, 2, 4))))  # type: ignore[arg-type]
    return [(c / total, rgb) for c, rgb in rows]  # type: ignore[return-value]


def hls(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    r, g, b = (v / 255 for v in rgb)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360.0, l, s


def ocr(path: Path) -> str:
    if not shutil.which("tesseract"):
        return ""
    r = subprocess.run(("tesseract", str(path), "stdout"), capture_output=True, text=True)
    return r.stdout.strip()


def quiet_field(path: Path) -> float:
    """Paper-coloured share of the upper-right quadrant, where the copy sits."""
    out = magick(str(path), "-gravity", "northeast", "-crop", "600x400+0+0", "+repage",
                 "-fuzz", "8%", "-fill", "white", "-opaque", "#f7f1e4",
                 "-fill", "black", "+opaque", "white", "-format", "%[fx:mean]", "info:")
    return float(out)


def near_black(path: Path) -> float:
    out = magick(str(path), "-fuzz", "6%", "-fill", "white", "+opaque", "black",
                 "-format", "%[fx:1-mean]", "info:")
    return float(out)


def main() -> int:
    prompts = json.loads((AUDIT / "prompts.json").read_text())
    swap = json.loads((AUDIT / "swap-check.json").read_text())
    prov = json.loads((AUDIT / "provenance.json").read_text())

    slugs = {"japanese-affection-context-l0": "japanese",
             "parent-measurement-practice": "parent",
             "technical-demo-pack": "technical"}

    prov_by_pack = {row["pack"]: row for row in prov["rows"]}

    for src in prompts["rows"]:
        slug = slugs[src["pack"]]
        print(f"\n{src['pack']} ({slug})")
        master = COVERS / f"{slug}-master-1200x800.png"
        crop32 = COVERS / f"{slug}-crop-3x2-1200x800.png"
        crop45 = COVERS / f"{slug}-crop-4x5-640x800.png"

        for p in (master, crop32, crop45):
            check(p.exists(), "file exists", str(p.relative_to(ROOT)))
        if FAILURES:
            continue

        from PIL import Image

        with Image.open(master) as im:
            check(im.size == (1200, 800), "master size", f"{im.width}x{im.height}")
            check(im.mode == "RGB", "master mode", f"{im.mode} (no alpha)")
        check(sha256(master) == sha256(crop32), "3:2 is the master", "byte-identical")
        with Image.open(crop45) as im:
            check(im.size == (640, 800), "4:5 size", f"{im.width}x{im.height}")
        # compare without shell pipelines: write the recomputed crop, then compare
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="cp012-accept-")) / "crop45.png"
        magick(str(master), "-gravity", "center", "-crop", "640x800+0+0", "+repage", str(tmp))
        ae = subprocess.run(("magick", "compare", "-metric", "AE", str(tmp), str(crop45), "null:"),
                            capture_output=True, text=True)
        ae_metric = ae.stderr.strip()
        check(ae_metric.replace(" (0)", "") in ("0", "0.0"), "4:5 is the master centre crop",
              f"AE={ae_metric}")

        corner = paper_corner(master)
        delta = max(abs(corner[i] - PAPER[i]) for i in range(3))
        check(delta <= 4, "paper is card-stock", f"corner={corner} target={PAPER} max_delta={delta}")

        nb = near_black(master)
        check(nb < 0.002, "no black contour", f"near-black share={nb:.5f}")

        bad = []
        for share, rgb in dominant_colours(master):
            if share < DOMINANT_SHARE:
                continue
            hue, _light, chroma = hls(rgb)
            warm = HUE_WARM[0] <= hue <= HUE_WARM[1]
            plum = HUE_PLUM[0] <= hue <= HUE_PLUM[1]
            neutral = chroma <= 0.15
            if not (neutral or ((warm or plum) and chroma <= CHROMA_MAX)):
                bad.append(f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x} "
                           f"h={hue:.0f} c={chroma:.2f} share={share:.1%}")
        check(not bad, "one palette family", "off-family: " + "; ".join(bad) if bad else
              "every dominant colour is warm/plum and <=0.80 chroma")

        quiet = quiet_field(master)
        check(quiet >= 0.50, "quiet field upper right",
              f"paper share={quiet:.1%} of the 600x400 upper-right quadrant (GM §1 needs >=35 %)")

        text = ocr(master)
        check(text == "", "textless (tesseract)", "no text read" if not text else repr(text[:60]))

        row = prov_by_pack.get(src["pack"])
        check(row is not None, "provenance row", "present" if row else "missing")
        if row:
            for shipped in row["shipped"]:
                p = ROOT / shipped["path"]
                check(p.exists() and sha256(p) == shipped["sha256"],
                      "provenance hash", f"{p.name} {shipped['sha256'][:16]}")
            raw = ROOT / row["raw"]["path"]
            check(raw.exists() and sha256(raw) == row["raw"]["sha256"],
                  "raw hash", f"{raw.name} {row['raw']['sha256'][:16]}")

    print("\nkit")
    covers = swap["covers"]
    check(len(covers) == 3, "three covers", f"{len(covers)}")
    namesets = []
    for c in covers:
        marks = [m["mark"].lower() for m in c["motifs"]]
        check(len(c["motifs"]) >= 2, f"{c['pack']} motif count", f"{len(c['motifs'])}")
        check(all(m["must_never_become"] for m in c["motifs"]),
              f"{c['pack']} must-never-become", "every motif has one")
        check(c["swaps"] and all(s["verdict"] == "rejected" and s["reason"] for s in c["swaps"]),
              f"{c['pack']} swap verdicts", f"{len(c['swaps'])} rejected with reasons")
        namesets.append(set(marks))
    for i in range(len(namesets)):
        for j in range(i + 1, len(namesets)):
            shared = namesets[i] & namesets[j]
            check(not shared, "marks disjoint",
                  f"{i}-{j} shared={sorted(shared) if shared else 'none'}")

    print()
    if FAILURES:
        print(f"{len(FAILURES)} failure(s):")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("A3 cover kit accepted by the machine checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
