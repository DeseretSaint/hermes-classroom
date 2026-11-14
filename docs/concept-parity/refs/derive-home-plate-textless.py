#!/usr/bin/env python3
"""Derive the textless 1344x768 home ground from the approved 1024x768 art.

Deterministic, offline, no model calls. Writes
`home-plate-1344-textless.png` next to this script (or --out).

Method, per region (output coordinates; source x = output x - 160):
  copy bands   band rects masked except where the art is warm (roof/eave/foliage
               survive), filled by a harmonic (Laplace) solution whose only
               Dirichlet boundary is the surrounding sky.
  CTA pill     eave sliver continued along the eave's measured slope (0.29),
               wall side (x < 250) tiled from the visible wall strip left of the
               pill, sky side harmonic from the sky above/right + 2 px feather.
  board faces  flat card stock #F7F2E8 inside each card's own rounded cream run;
               edges, corners and shadow rind untouched.
  width        E1's exact mirror+blur+feather pad to 1344x768 (no height crop).

Asserts that every changed pixel lies inside a declared mask.
"""
import argparse
import hashlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

CREAM = np.array([247, 242, 232], dtype=np.uint8)
TEXT_BANDS_OUT = [(203, 50, 362, 65), (203, 95, 368, 110)]
PILL_OUT = (218, 126, 393, 172)
CORNER_X_OUT = 250
CARDS_OUT = [(261, 379), (395, 513), (529, 647), (663, 781)]
CARD_Y = (319, 459)
PAD_LEFT = 160
PAD_RIGHT = 160
BLUR_RADIUS, FEATHER = 14.0, 48


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dilate(mask, r):
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dy == 0 and dx == 0:
                continue
            sh = np.zeros_like(mask)
            ys = slice(max(dy, 0), mask.shape[0] + min(dy, 0))
            xs = slice(max(dx, 0), mask.shape[1] + min(dx, 0))
            yd = slice(max(-dy, 0), mask.shape[0] + min(-dy, 0))
            xd = slice(max(-dx, 0), mask.shape[1] + min(-dx, 0))
            sh[yd, xd] = mask[ys, xs]
            out |= sh
    return out


def tri(offset, period):
    k = offset % (2 * period)
    return k if k < period else 2 * period - k


def harmonic_fill(out, mask, ok, iters=6000):
    """Harmonic fill; neighbours that are neither masked nor `ok` carry no value."""
    ys, xs = np.nonzero(mask)
    if not len(ys):
        return 0
    y0, y1 = max(int(ys.min()) - 3, 0), min(int(ys.max()) + 4, out.shape[0])
    x0, x1 = max(int(xs.min()) - 3, 0), min(int(xs.max()) + 4, out.shape[1])
    f = out[y0:y1, x0:x1].astype(np.float64)
    unknown = mask[y0:y1, x0:x1]
    usable = ~unknown & ok[y0:y1, x0:x1]
    last = None
    for yy in range(f.shape[0]):
        row_ok = usable[yy]
        if row_ok.any():
            last = f[yy][row_ok].mean(axis=0)
        if last is not None:
            f[yy][unknown[yy]] = last
    for _ in range(iters):
        nb_sum = np.zeros_like(f)
        nb_cnt = np.zeros(f.shape[:2])
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            srcf = np.roll(f, (dy, dx), axis=(0, 1))
            skip = np.roll(~(usable | unknown), (dy, dx), axis=(0, 1))
            nb_sum += np.where(skip[..., None], 0.0, srcf)
            nb_cnt += np.where(skip, 0.0, 1.0)
        upd = np.where((unknown & (nb_cnt > 0))[..., None],
                       nb_sum / np.maximum(nb_cnt, 1)[..., None], f)
        f = np.clip(upd, 0, 255)
    out[y0:y1, x0:x1][unknown] = np.rint(f).astype(np.uint8)[unknown]
    return int(unknown.sum())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(Path.home() / ".hermes/cache/scratch/composite_street.png"))
    ap.add_argument("--out", default=str(Path(__file__).with_name("home-plate-1344-textless.png")))
    args = ap.parse_args()

    src_path = Path(args.source).expanduser()
    out_path = Path(args.out)
    src = Image.open(src_path).convert("RGB")
    assert src.size == (1024, 768), src.size
    print("source", src_path, src.size, sha256(src_path))

    a = np.asarray(src)
    out = a.copy()
    r = a[:, :, 0].astype(np.int16)
    g = a[:, :, 1].astype(np.int16)
    b = a[:, :, 2].astype(np.int16)
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    warm = (r - b) > 22
    skyish = (b - r) > 10

    # 1. copy bands
    glyph = np.zeros((768, 1024), bool)
    for x0, y0, x1, y1 in TEXT_BANDS_OUT:
        sx0, sx1 = x0 - 160, x1 - 160
        band = np.zeros_like(glyph)
        band[y0:y1, sx0:sx1] = True
        glyph |= band & ~warm
    print("glyph-band px repainted", harmonic_fill(out, glyph, skyish))

    # 2. CTA pill
    px0, py0, px1, py1 = PILL_OUT
    sx0, sy0, sx1, sy1 = px0 - 160, py0, px1 - 160, py1
    rust = ((r >= 140) & ((r - g) >= 55) & ((r - b) >= 65) & (g >= 45) & (g <= 130))
    pill = np.zeros_like(rust)
    pill[sy0:sy1, sx0:sx1] = rust[sy0:sy1, sx0:sx1]
    ys, xs = np.nonzero(pill)
    print("rust bbox output x %d..%d y %d..%d" % (xs.min() + 160, xs.max() + 160, ys.min(), ys.max()))
    pill = dilate(pill, 2)

    corner = CORNER_X_OUT - 160
    strip0, strip1 = corner - 52, corner - 33
    period = strip1 - strip0 + 1

    eave = np.zeros_like(pill)
    for y in range(py0 - 2, min(py0 + 22, 768)):
        for x in np.nonzero(pill[y])[0]:
            if not (corner - 34 <= x <= corner + 50):
                continue
            for d in (9, 12, 15):
                sy, sx = y - d, x - int(round(d / 0.29))
                if sy < 0 or sx < 0 or pill[sy, sx] or rust[sy, sx]:
                    continue
                if warm[sy, sx] and lum[sy, sx] < 150:
                    out[y, x] = a[sy, sx]
                    eave[y, x] = True
                    break
    print("pill eave px restored", int(eave.sum()))

    mask_wall = np.zeros_like(pill)
    mask_wall[:, :corner] = pill[:, :corner]
    mask_wall &= ~eave
    wall_px = 0
    for y in np.nonzero(mask_wall.any(axis=1))[0]:
        row_src = out[y].astype(np.float64)
        for x in np.nonzero(mask_wall[y])[0]:
            off = x - (strip1 + 1)
            out[y, x] = np.clip(np.rint(row_src[strip1 - tri(off, period)]), 0, 255).astype(np.uint8)
            wall_px += 1

    mask_sky = np.zeros_like(pill)
    mask_sky[:, corner:sx1] = pill[:, corner:sx1]
    mask_sky &= ~eave
    sky_ok = (lum > 150) & ((b - r) > -30) & ~warm
    mask_sky_ext = dilate(mask_sky, 2)
    mask_sky_ext[:, :corner] = False
    mask_sky_ext &= ~eave
    sky_px = harmonic_fill(out, mask_sky_ext, sky_ok)
    ring1 = dilate(mask_sky, 1) & ~mask_sky
    w = np.zeros(mask_sky_ext.shape)
    w[mask_sky_ext] = 0.15
    w[ring1] = 0.5
    w[mask_sky] = 1.0
    fill = out.astype(np.float64)
    base = a.astype(np.float64)
    out[mask_sky_ext] = np.clip(np.rint(w[..., None] * fill + (1 - w[..., None]) * base),
                                0, 255).astype(np.uint8)[mask_sky_ext]
    # harmonic fill is smooth by construction; re-inject the surrounding sky's
    # high-frequency detail (mirrored from the clean sky to the right) so the
    # repaint does not read as a flat patch.
    blur = np.asarray(Image.fromarray(out).filter(ImageFilter.GaussianBlur(3.0))).astype(np.float64)
    basef = out.astype(np.float64)
    detail = basef - blur
    inner = mask_sky.copy()
    for _ in range(2):                       # erode: keep the seam clean
        inner = inner & np.roll(inner, 1, 0) & np.roll(inner, -1, 0) \
                    & np.roll(inner, 1, 1) & np.roll(inner, -1, 1)
    for y in np.nonzero(mask_sky.any(axis=1))[0]:
        for x in np.nonzero(mask_sky[y])[0]:
            if not inner[y, x]:
                continue
            dx_m = min(2 * sx1 - 1 - x, 1023)
            d = detail[y, dx_m]
            if np.abs(d).max() > 12:
                d = np.clip(d, -12, 12)
            out[y, x] = np.clip(np.rint(basef[y, x] + 0.7 * d), 0, 255).astype(np.uint8)
    print("pill wall px", wall_px, "pill sky px", sky_px)

    # 3. blank the board faces
    cream = (out[:, :, 0] >= 244) & (out[:, :, 1] >= 238) & (out[:, :, 2] >= 222)
    blanked = 0
    for cx0, cx1 in [(c[0] - 160, c[1] - 160) for c in CARDS_OUT]:
        missing = 0
        for y in range(CARD_Y[0], CARD_Y[1] + 1):
            idx = np.nonzero(cream[y, cx0 - 1:cx1 + 1])[0]
            if not len(idx):
                missing += 1
                continue
            lo, hi = cx0 - 1 + int(idx[0]), cx0 - 1 + int(idx[-1])
            out[y, lo:hi + 1] = CREAM
            blanked += hi - lo + 1
        print("card x %d..%d rows without cream: %d" % (cx0, cx1, missing))
    print("blanked px", blanked)

    # 4. nothing may have moved outside the declared masks
    changed = (out != a).any(axis=2)
    allowed = glyph | pill | mask_sky_ext
    for cx0, cx1 in [(c[0] - 160, c[1] - 160) for c in CARDS_OUT]:
        allowed[CARD_Y[0]:CARD_Y[1] + 1, cx0:cx1 + 1] = True
    illegal = changed & ~allowed
    print("changed px", int(changed.sum()), "illegal px", int(illegal.sum()))
    assert illegal.sum() == 0, "edit escaped the declared regions"

    # 5. width-extend exactly as E1
    mid = Image.fromarray(out)

    def make_strip(img, side):
        if side == "left":
            band = img.crop((0, 0, PAD_LEFT, 768)).transpose(Image.FLIP_LEFT_RIGHT)
        else:
            band = img.crop((1024 - PAD_RIGHT, 0, 1024, 768)).transpose(Image.FLIP_LEFT_RIGHT)
        band = band.filter(ImageFilter.GaussianBlur(BLUR_RADIUS))
        alpha = Image.new("L", (band.width, band.height), 255)
        ap = alpha.load()
        for x in range(band.width):
            dist = (band.width - 1) - x if side == "left" else x
            av = 255 if dist >= FEATHER else int(255 * dist / FEATHER)
            for y in range(band.height):
                ap[x, y] = av
        rgba = band.convert("RGBA")
        rgba.putalpha(alpha)
        return rgba

    canvas = Image.new("RGB", (1344, 768))
    canvas.paste(mid, (PAD_LEFT, 0))
    left, right = make_strip(mid, "left"), make_strip(mid, "right")
    canvas.paste(left, (0, 0), left)
    canvas.paste(right, (PAD_LEFT + 1024, 0), right)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, format="PNG", optimize=True)
    print("out", out_path, canvas.size, sha256(out_path), out_path.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
