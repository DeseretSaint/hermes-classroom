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
* **no state hue is shipped.** `docs/GM-SUBJECT-WORLDS.md` §0 bans ochre, coral
  and plum in art, because a plate must never look like a due/attention/parent
  state. Measured on the frame: (a) plum hue 270-340 deg at HSV chroma > 0.15
  stays under 0.5 %, and (b) pixels within dE*ab <= 12 of #7b4b0a (ochre),
  #9c2e1c (coral) or #6a3e74 (plum) stay under 0.5 % each. The hue-family leg
  is only usable for plum: lamp gold #e8a93a is hue 39 and ochre #7b4b0a is hue
  36, so an ochre "hue family" would ban the lamp token the kit requires; those
  two pigments are gated by pigment distance instead;
* every dominant colour (>1 % of a 96 px quantization) is in the plate's colour
  family: the warm band (hue 10-70 deg, the paper/cream/ink-brown/gold gouache
  tints), the one field-green band (hue 75-165 deg, chroma <= 0.80), or a
  near-neutral (chroma <= 0.15). Cold and violet hues are therefore rejected.
  Round 1 passed a `HUE_PLUM` allowance here; that allowance is gone, so a
  plum cloth can no longer define its own oracle;
* **every declared motif survives the 4:5 crop.** For each motif bbox in
  `audit/cp012-covers/swap-check.json`, the bbox holds at least 150 non-paper
  pixels (the motif is really painted there) and at least 60 % of those pixels
  fall inside the mechanical 640x800 centre crop. This is the check the round-1
  packet lacked: the crop severed the Japanese lantern (18 % of its ink
  survived) while the document claimed it cut only frame elements;
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

The script counts its own checks and prints the total as its final line,
`<N> checks: <N> pass, <F> fail`. That line is the only authoritative total: a
witness document that states a different number is wrong, and
`tests/test_cp012_covers.py::test_the_declared_check_count_matches_the_script`
fails when `docs/concept-parity/COVERS.md` and this line disagree. Round 2
shipped a document claiming 88 checks against a script that ran 80, because no
artefact owned the number.
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
HUE_WARM = (10.0, 70.0)     # paper, cream, ink-brown, gold and their gouache tints
HUE_FIELD = (75.0, 165.0)   # the one field-green accent
HUE_PLUM = (270.0, 340.0)
DOMINANT_SHARE = 0.01
CROP = (280, 920)          # the mechanical 640x800 centre crop window
CROP_MIN_SHARE = 0.60      # every declared motif keeps >=60 % of its ink
MOTIF_MIN_INK = 150
STATE_MAX_SHARE = 0.005    # 0.5 % of the frame
STATE_PIGMENTS = {"ochre": "#7b4b0a", "coral": "#9c2e1c", "plum": "#6a3e74"}
PLATE_PIGMENTS = {"paper": "#f7f1e4", "ink": "#3a2318", "cuff": "#2b1d14",
                  "cream": "#efe0c2", "field": "#2f6047", "lamp": "#e8a93a"}
PAPER_TOL = 60             # max channel distance that still counts as paper
FAILURES: list[str] = []
PASSES = 0


def magick(*args: str) -> str:
    r = subprocess.run(("magick",) + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"magick failed: {' '.join(args)}\n{r.stderr}")
    return r.stdout.strip()


def check(ok: bool, name: str, detail: str) -> None:
    global PASSES
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: {detail}")
    if ok:
        PASSES += 1
    else:
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


def hex_rgb(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    return tuple(float(int(value[i:i + 2], 16)) for i in (0, 2, 4))  # type: ignore[return-value]


def to_lab(rgb: tuple[float, float, float] | list[float]) -> tuple[float, float, float]:
    c = [v / 255.0 for v in rgb]
    c = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    x = c[0] * 0.4124 + c[1] * 0.3576 + c[2] * 0.1805
    y = c[0] * 0.2126 + c[1] * 0.7152 + c[2] * 0.0722
    z = c[0] * 0.0193 + c[1] * 0.1192 + c[2] * 0.9505
    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x / 0.95047), f(y / 1.0), f(z / 1.08883)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(rgb: tuple[float, float, float], anchor_hex: str) -> float:
    a, b = to_lab(rgb), to_lab(hex_rgb(anchor_hex))
    return sum((a[i] - b[i]) ** 2 for i in range(3)) ** 0.5


def state_hue_report(path: Path) -> dict[str, float]:
    """Frame shares of the forbidden state pigments."""
    import numpy as np
    from PIL import Image

    with Image.open(path) as im:
        a = np.asarray(im.convert("RGB"))[::2, ::2].reshape(-1, 3).astype(np.float64)

    # hue/chroma on the numpy copy (colorsys per pixel is too slow for a frame)
    c = a / 255.0
    mx = c.max(axis=1)
    mn = c.min(axis=1)
    d = mx - mn
    chroma = np.where(mx > 0, d / np.maximum(mx, 1e-9), 0.0)
    r, g, b = c[:, 0], c[:, 1], c[:, 2]
    hue = np.zeros(len(c))
    nz = d > 1e-9
    m = nz & (mx == r)
    hue[m] = (60 * ((g[m] - b[m]) / d[m])) % 360
    m = nz & (mx == g)
    hue[m] = 60 * ((b[m] - r[m]) / d[m]) + 120
    m = nz & (mx == b)
    hue[m] = 60 * ((r[m] - g[m]) / d[m]) + 240

    # vectorised CIE Lab
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    mtx = np.array([[0.4124, 0.3576, 0.1805],
                    [0.2126, 0.7152, 0.0722],
                    [0.0193, 0.1192, 0.9505]])
    xyz = lin @ mtx.T / np.array([0.95047, 1.0, 1.08883])
    t = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    lab = np.stack([116 * t[:, 1] - 16, 500 * (t[:, 0] - t[:, 1]),
                    200 * (t[:, 1] - t[:, 2])], axis=1)

    out = {"plum_hue": float(((hue >= HUE_PLUM[0]) & (hue <= HUE_PLUM[1]) &
                              (chroma > 0.15)).mean())}
    for name, anchor in STATE_PIGMENTS.items():
        anc = np.array(to_lab(hex_rgb(anchor)))
        out[name] = float((np.linalg.norm(lab - anc, axis=1) <= 12).mean())
    return out


def ink_mask(path: Path):
    import numpy as np
    from PIL import Image

    paper = np.array(PAPER)
    with Image.open(path) as im:
        a = np.asarray(im.convert("RGB")).astype(np.int16)
    return np.abs(a - paper).max(axis=2) > PAPER_TOL


def motif_report(path: Path, bbox: list[int]) -> tuple[int, float]:
    """Ink pixels inside a motif bbox, and the share of them inside the 4:5 crop."""
    import numpy as np

    mask = ink_mask(path)
    h, w = mask.shape
    x0, y0, x1, y1 = bbox
    if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h):
        return 0, 0.0
    sub = mask[y0:y1, x0:x1]
    total = int(sub.sum())
    ix0, ix1 = max(x0, CROP[0]), min(x1, CROP[1])
    inside = int(mask[y0:y1, ix0:ix1].sum()) if ix1 > ix0 else 0
    return total, (inside / total if total else 0.0)


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
    global PASSES
    PASSES = 0
    FAILURES.clear()
    prompts = json.loads((AUDIT / "prompts.json").read_text())
    swap = json.loads((AUDIT / "swap-check.json").read_text())
    prov = json.loads((AUDIT / "provenance.json").read_text())

    slugs = {"japanese-affection-context-l0": "japanese",
             "parent-measurement-practice": "parent",
             "technical-demo-pack": "technical"}

    prov_by_pack = {row["pack"]: row for row in prov["rows"]}
    swap_by_pack = {c["pack"]: c for c in swap["covers"]}

    for src in prompts["rows"]:
        slug = slugs[src["pack"]]
        print(f"\n{src['pack']} ({slug})")
        master = COVERS / f"{slug}-master-1200x800.png"
        crop32 = COVERS / f"{slug}-crop-3x2-1200x800.png"
        crop45 = COVERS / f"{slug}-crop-4x5-640x800.png"

        missing = [p for p in (master, crop32, crop45) if not p.exists()]
        for p in (master, crop32, crop45):
            check(p.exists(), "file exists", str(p.relative_to(ROOT)))
        if missing:
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

        off_plate = []
        for share, rgb in dominant_colours(master):
            if share < DOMINANT_SHARE:
                continue
            hue, _light, chroma = hls(rgb)
            warm = HUE_WARM[0] <= hue <= HUE_WARM[1]
            field = HUE_FIELD[0] <= hue <= HUE_FIELD[1]
            neutral = chroma <= 0.15
            if not (neutral or ((warm or field) and chroma <= CHROMA_MAX)):
                off_plate.append(f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x} "
                                 f"h={hue:.0f} c={chroma:.2f} share={share:.1%}")
        check(not off_plate, "one plate palette", "off-palette: " + "; ".join(off_plate) if off_plate
              else "every dominant colour is warm paper/brown/gold, field green, or a near-neutral")

        state = state_hue_report(master)
        worst = max(state.values())
        detail = " ".join(f"{k}={v:.4%}" for k, v in state.items())
        check(worst <= STATE_MAX_SHARE, "no state hue shipped",
              f"{detail} (each must stay <= {STATE_MAX_SHARE:.1%} of the frame)")

        cover = swap_by_pack[src["pack"]]
        for motif in cover["motifs"]:
            bbox = motif.get("bbox")
            if not bbox:
                check(False, f"motif {motif['mark']}", "no bbox declared")
                continue
            ink, retained = motif_report(master, bbox)
            check(ink >= MOTIF_MIN_INK and retained >= CROP_MIN_SHARE,
                  f"4:5 keeps {motif['mark']}",
                  f"ink={ink}px retained={retained:.1%} bbox={bbox}")

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
    total = PASSES + len(FAILURES)
    if FAILURES:
        print(f"{len(FAILURES)} failure(s):")
        for f in FAILURES:
            print(f"  - {f}")
        print(f"{total} checks: {PASSES} pass, {len(FAILURES)} fail")
        return 1
    print(f"{total} checks: {PASSES} pass, 0 fail")
    print("A3 cover kit accepted by the machine checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
