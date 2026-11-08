"""Reproducible builder for the bundled demonstration packs.

Run from the plugin root:

    python3 bundled/packs/build_demo_packs.py

It rewrites each ``pack.json`` from the content files beside it, generating the relationship
schematic for the Japanese pack deterministically (fixed geometry, fixed zlib level, fixed PNG
chunks). ``tests/test_packs_fixtures.py`` asserts the committed manifests still match this
builder, so a content edit that forgets to rebuild fails the suite instead of shipping a pack
whose declared hashes are stale.
"""

from __future__ import annotations

import json
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent.parent))

from coursebook import packs  # noqa: E402  (path is set above for direct execution)

JAPANESE = ROOT / "japanese-affection-context-l0"
PARENT = ROOT / "parent-measurement-practice"
#: H-196 — a third real fixture so the Workshop storefront is built from real packs, not invented
#: cards. It teaches the pack contract this repository implements; every claim is a file in this
#: tree, and the pack bundles no third-party text or media.
TECHNICAL = ROOT / "technical-demo-pack"

#: H-197 — the cover plates. The Japanese and technical packs carry one as a real pack media
#: artifact (cb.pack v2). The parent pack stays cb.pack v1 on purpose: it is the repository's only
#: v1 fixture and the gate that proves a v1 pack imports byte-for-byte as before, so it keeps the
#: typographic cover rather than gaining a `media[]` link. Its plate exists in `cover_plate_png`
#: for the day that pack is released as v2, but nothing ships it unused.
COVER_CAPTION = "Pack visual — generated plate; not a diagram of the course."
COVER_ATTRIBUTION = (
    "Host-composed Press Plate printed deterministically by the Coursebook demo pack builder "
    "(bundled/packs/build_demo_packs.py) from the Atlas Lamp token palette: five flat inks, no "
    "gradient, no grain, no photograph, no model call, no third-party imagery."
)
JAPANESE_COVER_TEXT = (
    "Pack visual: a flat printed plate in five inks — warm paper, a pale gold field across the "
    "lower half, a wide shallow indigo band rising across it, one near-black rule along the field's "
    "edge, and a gold bar along the bottom. Decorative material only: it is not a diagram of the "
    "course, not a photograph, and it carries no text."
)
TECHNICAL_COVER_TEXT = (
    "Pack visual: a flat printed plate in five inks — warm paper, a solid near-black half with a "
    "pale grey band along its cut edge, a pale gold field on the paper half, and a gold bar along "
    "the bottom. Decorative material only: it is not a diagram of the pack format and carries no "
    "text."
)
PARENT_COVER_TEXT = (
    "Pack visual: a flat printed plate in five inks — warm paper, a solid plum plane to two thirds "
    "with one ink cut edge, a narrow plum band across the frame, a pale gold field, and a gold bar "
    "along the bottom. Decorative material only: it is not a diagram of the measurement lesson and "
    "carries no text."
)

FETCHED_AT = "2026-11-06"
ORIGINAL = (
    "Original teaching text and schematic: Coursebook demo pack. Sources are cited by link and "
    "are not bundled; see sources[] and content/source-notes.md."
)
JAPANESE_ATTRIBUTION = (
    "Original teaching text, cover plate, schematic and narration: Coursebook demo pack. The cover "
    "plate and the schematic are host-composed, deterministic artwork built from the Atlas Lamp "
    "token palette; no third-party imagery is bundled. The narration clip is "
    "synthetic speech from Kokoro-82M voice jf_alpha (Apache-2.0), generated offline by the pack "
    "maintainer; no human speaker was recorded. Sources are cited by link and are not bundled; see "
    "sources[] and content/source-notes.md."
)
#: The one narration asset. It is committed as bytes (synthesis needs an offline neural engine that
#: is not a build dependency) and re-hashed by this builder from the real file, so the manifest can
#: never drift from the audio. Exact tool, version, voice and command: docs/REVIEW_H72.md.
NARRATION_PATH = "content/narration-polite-confession.mp3"
NARRATION_TEXT = (
    "好きです。付き合ってください。 (suki desu. tsukiatte kudasai.) — polite register: "
    "\"I like you. Please go out with me.\" One line, spoken as the first-confession example the "
    "pack teaches. Synthetic speech, not a native-speaker pronunciation model."
)
#: The one-line caption a learner sees beside the audio. It is the media child's ``purpose`` and
#: ``text_equivalent`` (cb.pack v2), and it repeats the file's own transcript rather than inventing
#: a new claim about the audio.
NARRATION_CAPTION = (
    '好きです。付き合ってください。 (suki desu. tsukiatte kudasai.) — '
    '"I like you. Please go out with me."'
)
#: The caption beside the relationship map. The long text equivalent stays on the file record.
VISUAL_CAPTION = (
    "Relationship and register map: friend to casual (suki da yo); respected addressee to polite "
    "(suki desu); long-term partner to intimate (aishiteru)."
)
UNSPECIFIED_LICENSE = {
    "id": "unspecified",
    "redistribution": "local_only",
    "note": (
        "Bundled demonstration fixture. The teaching text is original Coursebook-authored material; "
        "the operator has not chosen a redistribution license. Linked sources are cited, not bundled."
    ),
}


# ── Deterministic PNG ──────────────────────────────────────────────────────


_FONT: dict[str, tuple[str, ...]] = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "00110", "00110"),
    ":": ("00000", "00110", "00110", "00000", "00110", "00110", "00000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
}


class Canvas:
    def __init__(self, width: int, height: int, background: tuple[int, int, int]) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray(bytes(background) * (width * height))

    def _put(self, x: int, y: int, colour: tuple[int, int, int]) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            offset = (y * self.width + x) * 3
            self.pixels[offset : offset + 3] = bytes(colour)

    def rect(self, x0: int, y0: int, x1: int, y1: int, colour: tuple[int, int, int]) -> None:
        for y in range(max(0, y0), min(self.height, y1)):
            row = (y * self.width + x0) * 3
            self.pixels[row : row + (x1 - x0) * 3] = bytes(colour) * (x1 - x0)

    def outline(self, x0: int, y0: int, x1: int, y1: int, colour: tuple[int, int, int], width: int = 3) -> None:
        self.rect(x0, y0, x1, y0 + width, colour)
        self.rect(x0, y1 - width, x1, y1, colour)
        self.rect(x0, y0, x0 + width, y1, colour)
        self.rect(x1 - width, y0, x1, y1, colour)

    def arrow(self, x0: int, y0: int, x1: int, colour: tuple[int, int, int]) -> None:
        self.rect(x0, y0 - 2, x1 - 10, y0 + 3, colour)
        for step in range(10):
            self.rect(x1 - 10 + step, y0 - 9 + step, x1 - 9 + step, y0 + 10 - step, colour)

    def text(self, x: int, y: int, value: str, *, scale: int, colour: tuple[int, int, int]) -> int:
        cursor = x
        for character in value.upper():
            glyph = _FONT.get(character, _FONT[" "])
            for row, line in enumerate(glyph):
                for column, bit in enumerate(line):
                    if bit == "1":
                        self.rect(cursor + column * scale, y + row * scale, cursor + (column + 1) * scale, y + (row + 1) * scale, colour)
            cursor += (len(glyph[0]) + 1) * scale
        return cursor

    def to_png(self) -> bytes:
        raw = bytearray()
        stride = self.width * 3
        for y in range(self.height):
            raw.append(0)
            raw.extend(self.pixels[y * stride : (y + 1) * stride])
        compressed = zlib.compress(bytes(raw), 9)

        def chunk(tag: bytes, payload: bytes) -> bytes:
            return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)

        header = struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)
        return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")


def relationship_map_png() -> bytes:
    ink = (24, 26, 33)
    background = (246, 247, 251)
    header = (32, 52, 84)
    colours = [(214, 232, 246), (222, 240, 224), (250, 232, 205)]
    canvas = Canvas(1080, 470, background)
    canvas.text(40, 28, "RELATIONSHIP MAP: ADDRESSEE SETS REGISTER", scale=3, colour=header)

    columns = [("SPEAKER", 40), ("ADDRESSEE", 280), ("INTENT", 570), ("REGISTER + EXAMPLE", 810)]
    for label, x in columns:
        canvas.text(x, 92, label, scale=2, colour=(90, 96, 112))

    canvas.rect(40, 110, 1060, 118, (200, 206, 220))

    rows = [
        ("YOU", "FRIEND", "AFFECTION", "CASUAL: SUKI DA YO"),
        ("YOU", "SOMEONE YOU RESPECT", "FIRST CONFESSION", "POLITE: SUKI DESU"),
        ("YOU", "LONG-TERM PARTNER", "DEEP AFFECTION", "INTIMATE: AISHITERU"),
    ]
    top = 140
    for index, (speaker, addressee, intent, register) in enumerate(rows):
        y0 = top + index * 100
        colour = colours[index]
        for x, width in ((40, 190), (280, 250), (570, 210), (810, 250)):
            canvas.rect(x, y0, x + width, y0 + 62, colour)
            canvas.outline(x, y0, x + width, y0 + 62, (120, 130, 150), width=2)
        canvas.text(56, y0 + 24, speaker, scale=2, colour=ink)
        canvas.text(296, y0 + 24, addressee, scale=2, colour=ink)
        canvas.text(586, y0 + 24, intent, scale=2, colour=ink)
        canvas.text(820, y0 + 24, register, scale=2, colour=ink)
        canvas.arrow(238, y0 + 31, 274, (120, 130, 150))
        canvas.arrow(538, y0 + 31, 564, (120, 130, 150))
        canvas.arrow(788, y0 + 31, 804, (120, 130, 150))

    canvas.text(40, 448, "REGISTER IS A FUNCTION OF ADDRESSEE, RELATIONSHIP AND SETTING.", scale=2, colour=(90, 96, 112))
    return canvas.to_png()


# ── H-197 · the one approved cover lane: Press Plate ───────────────────────
#
# Every pack is one sheet off the same press. The cover is a printed *field*, not a picture: one
# broad flat form, one hard-edged `lamp-soft` flood, one `lamp` band full bleed at a fixed y, and
# one heavy ink rule. There is no depiction of teaching content, no object, no person, no symbol and
# no text in the raster — the title is type the app renders beside the plate, so the artwork can
# neither garble a glyph nor imply a fact the pack does not teach.
#
# The art direction measured the host image pipeline and found it unusable for exact geometry
# (four probes ignored "exactly five flat inks": 4,851 to 34,692 unique colours, plus grain and an
# unrequested keyline frame). It recommended Press Plate precisely because the model is good at
# material and broad mass and bad at topology. This builder therefore prints the plate itself,
# deterministically, to the same brief and the same acceptance block: five identity inks, the left
# 4% clear (the app paints its 6px lamp spine there), the form's centroid inside the middle 84%,
# and the lamp band at a fixed y. The prompts (P1–P3) remain in `docs/ART-DIRECTION-COVERS.md` for a
# host that does have `image_generate`; nothing here claims a model made these bytes.
COVER_MASTER = "content/cover-16x9.png"
COVER_CROP = "content/cover-3x2.png"
COVER_W = 1024
COVER_H = 576
#: The 3:2 card crop at the same height: 864 x 576 keeps 84.4% of the width, centred.
COVER_CROP_W = 864
COVER_CROP_OFFSET = (COVER_W - COVER_CROP_W) // 2  # 80
#: 4% of the width. WorkshopCover paints a 6px lamp spine over the plate's left edge, so nothing
#: meaningful may sit inside it.
COVER_LEFT_CLEAR = 41
#: The lamp band is 58px = 10.1% of the frame height, full bleed, at one fixed y for the imprint.
COVER_BAND_TOP = 518
#: The cover surfaces present the master; the crop is the file a 3:2 surface uses.
COVER_PATH = COVER_MASTER

#: Atlas Lamp, light mode, copied from contracts/cb.tokens.v2.json. A plate is a lit page, so it
#: keeps the paper palette in both UI modes; the app mounts it on its own token background.
_PAPER = (247, 241, 228)  # paper      #f7f1e4
_INK = (26, 23, 19)  # ink        #1a1713
_RULE = (215, 203, 180)  # rule       #d7cbb4
_ACCENT = (44, 74, 140)  # accent     #2c4a8c
_LAMP = (232, 169, 58)  # lamp       #e8a93a
_LAMP_SOFT = (251, 235, 203)  # lamp-soft  #fbebcb
_PLUM = (106, 62, 116)  # plum       #6a3e74


def _fill(canvas: "Canvas", x0: int, y0: int, x1: int, y1: int, colour) -> None:
    """A clipped flat rectangle: the form, the flood and the band are all just flat fills."""
    canvas.rect(max(0, x0), max(0, y0), min(canvas.width, x1), min(COVER_H, y1), colour)


def _arc_band(canvas: "Canvas", *, dx: int, colour) -> None:
    """One broad form: a straight-cut plane with a slanted edge, bleeding off the top and bottom.

    Printed row by row so the cut edge is exact — no anti-aliasing, no gradient, no outline. A
    plane was chosen over an arc after inspection: a band that rises and falls reads as an arch or
    a bridge, and a cover may not carry a recognisable thing.
    """
    x_top, x_bottom = 760, 560
    for y in range(0, COVER_BAND_TOP):
        share = y / max(1, COVER_BAND_TOP - 1)
        edge = int(round(x_top + (x_bottom - x_top) * share))
        _fill(canvas, COVER_LEFT_CLEAR, y, edge, y + 1, colour)
        _fill(canvas, edge, y, edge + 8, y + 1, _INK)  # the cut edge, in ink


def _japanese_plate(canvas: "Canvas", dx: int) -> None:
    """P1: a pale gold field, one indigo plane with a slanted cut edge, the gold band."""
    _fill(canvas, 0, 300, COVER_W, COVER_BAND_TOP, _LAMP_SOFT)  # one flood, hard top edge
    _arc_band(canvas, dx=dx, colour=_ACCENT)  # one broad form, bleeding off top and bottom


def _technical_plate(canvas: "Canvas", dx: int) -> None:
    """P3: a solid near-black half, one pale grey band along its edge, a pale gold field."""
    _fill(canvas, 522, 340, COVER_W, COVER_BAND_TOP, _LAMP_SOFT)  # the flood on the paper side
    _fill(canvas, COVER_LEFT_CLEAR, 0, 512, COVER_BAND_TOP, _INK)  # the one broad form
    _fill(canvas, 512, 0, 522, COVER_BAND_TOP, _RULE)  # the pale grey band along its cut edge


def _parent_plate(canvas: "Canvas", dx: int) -> None:
    """P2: a solid plum plane to two thirds, one plum band across it, one ink cut rule."""
    _fill(canvas, COVER_LEFT_CLEAR, 340, COVER_W, COVER_BAND_TOP, _LAMP_SOFT)  # the flood
    _fill(canvas, COVER_LEFT_CLEAR, 0, 682, COVER_BAND_TOP, _PLUM)  # the one broad form
    _fill(canvas, 682, 0, 690, COVER_BAND_TOP, _INK)  # its cut edge, in ink
    _fill(canvas, COVER_LEFT_CLEAR, 190, COVER_W, 210, _PLUM)  # one narrow band across the frame


def _press_plate(kind: str, *, width: int = COVER_W) -> bytes:
    """One printed plate: the pack's form, then the imprint's lamp band over everything."""
    plates = {
        "japanese": _japanese_plate,
        "technical": _technical_plate,
        "parent": _parent_plate,
    }
    if kind not in plates:
        raise ValueError(f"unknown cover plate {kind!r}")
    canvas = Canvas(COVER_W, COVER_H, _PAPER)
    plates[kind](canvas, 0)
    # The band is printed last and full bleed, so every pack carries the same y and the same height.
    _fill(canvas, 0, COVER_BAND_TOP, COVER_W, COVER_H, _LAMP)
    if width == COVER_W:
        return canvas.to_png()
    # A real crop of the master's pixels, never a second drawing: the 3:2 file is provably the
    # centre of the 16:9 plate.
    offset_x = (COVER_W - width) // 2
    crop = Canvas(width, COVER_H, _PAPER)
    for y in range(COVER_H):
        source = (y * COVER_W + offset_x) * 3
        target = y * width * 3
        crop.pixels[target : target + width * 3] = canvas.pixels[source : source + width * 3]
    return crop.to_png()


def cover_plate_png(kind: str) -> bytes:
    """The 16:9 master: the plate every cover surface presents."""
    return _press_plate(kind)


def cover_crop_png(kind: str) -> bytes:
    """The 3:2 card file: a mechanical centre crop of the master, never a regeneration."""
    return _press_plate(kind, width=COVER_CROP_W)


# ── Pack definitions ───────────────────────────────────────────────────────


def _sections(paths: list[str]) -> dict[str, bytes]:
    return {path: (JAPANESE / path).read_bytes() for path in paths}


def japanese_manifest() -> dict:
    section_paths = [
        "content/section-01-two-ways.md",
        "content/section-02-choosing.md",
        "content/section-03-new-context.md",
        "content/source-notes.md",
        "content/relationship-map.png",
        COVER_MASTER,
        COVER_CROP,
        NARRATION_PATH,
    ]
    files = _sections(section_paths[:-4])
    files["content/relationship-map.png"] = relationship_map_png()
    files[COVER_MASTER] = cover_plate_png("japanese")
    files[COVER_CROP] = cover_crop_png("japanese")
    files[NARRATION_PATH] = (JAPANESE / NARRATION_PATH).read_bytes()
    metadata = {
        "content/section-01-two-ways.md": {"mime": "text/markdown", "role": "section"},
        "content/section-02-choosing.md": {"mime": "text/markdown", "role": "section"},
        "content/section-03-new-context.md": {"mime": "text/markdown", "role": "section"},
        "content/source-notes.md": {"mime": "text/markdown", "role": "source_note"},
        NARRATION_PATH: {
            "mime": "audio/mpeg",
            "role": "narration",
            "text_equivalent": NARRATION_TEXT,
            "description": (
                "One synthesized Japanese narration clip of the polite first-confession line. "
                "Kokoro-82M voice jf_alpha (Apache-2.0), generated offline on 2026-11-07; "
                "no human speaker was recorded."
            ),
        },
        "content/relationship-map.png": {
            "mime": "image/png",
            "role": "visual",
            "text_equivalent": (
                "Schematic with three paths from speaker to register. You to a friend, affection, "
                "casual register (suki da yo). You to someone you respect, first confession, polite "
                "register (suki desu). You to a long-term partner, deep affection, intimate register "
                "(aishiteru). The schematic states that register is a function of addressee, "
                "relationship and setting."
            ),
            "description": "Relationship and register map drawn deterministically for the demo pack.",
        },
        COVER_MASTER: {
            "mime": "image/png",
            "role": "visual",
            "text_equivalent": JAPANESE_COVER_TEXT,
            "description": (
                "Press Plate cover for this pack (16:9 master): five flat inks, printed "
                "deterministically. Decorative material; it carries no register facts and no text."
            ),
        },
        COVER_CROP: {
            "mime": "image/png",
            "role": "visual",
            "text_equivalent": JAPANESE_COVER_TEXT,
            "description": (
                "Press Plate cover for this pack (864x576, a mechanical centre crop of the 16:9 "
                "master for a 3:2 card). Same plate, same five inks."
            ),
        },
    }

    sources = [
        {
            "source_id": "src-jf-marugoto-a1",
            "title": "Marugoto: Japanese Language and Culture, Starter (A1) — Coursebook for Communicative Language Activities, table of contents",
            "url": "https://marugoto.jpf.go.jp/en/assets/docs/about/starter_activities_contents_en.pdf",
            "publisher": "The Japan Foundation",
            "source_type": "course_material",
            "fetched_at": FETCHED_AT,
            "support_status": "authoritative_documentation",
            "license_note": "Linked, not bundled. © The Japan Foundation; cited as a curriculum reference only.",
            "bundled": False,
        },
        {
            "source_id": "src-jf-marugoto-teaching",
            "title": "How to teach with Marugoto (teacher FAQ)",
            "url": "https://marugoto.jpf.go.jp/en/teacher/qateaching/",
            "publisher": "The Japan Foundation",
            "source_type": "course_material",
            "fetched_at": FETCHED_AT,
            "support_status": "authoritative_documentation",
            "license_note": "Linked, not bundled. © The Japan Foundation; quoted only for the romaji/script policy fact.",
            "bundled": False,
        },
        {
            "source_id": "src-wiktionary-suki",
            "title": "Wiktionary — 好き (suki)",
            "url": "https://en.wiktionary.org/wiki/%E5%A5%BD%E3%81%8D",
            "publisher": "Wikimedia Foundation",
            "source_type": "reference",
            "fetched_at": FETCHED_AT,
            "support_status": "model_assessed",
            "license_note": "Linked, not bundled. Wiktionary content is CC BY-SA 4.0; no text is copied.",
            "bundled": False,
        },
        {
            "source_id": "src-wiktionary-aisuru",
            "title": "Wiktionary — 愛する (aisuru)",
            "url": "https://en.wiktionary.org/wiki/%E6%84%9B%E3%81%99%E3%82%8B",
            "publisher": "Wikimedia Foundation",
            "source_type": "reference",
            "fetched_at": FETCHED_AT,
            "support_status": "model_assessed",
            "license_note": "Linked, not bundled. Wiktionary content is CC BY-SA 4.0; no text is copied.",
            "bundled": False,
        },
        {
            "source_id": "src-sng-love",
            "title": "Learn how to say \"I love you\" in Japanese",
            "url": "https://www.sng.ac.jp/sng-news/learn-say-love-japanese/",
            "publisher": "Shinjuku Japanese Language Institute (SNG)",
            "source_type": "secondary",
            "fetched_at": FETCHED_AT,
            "support_status": "model_assessed",
            "license_note": "Linked, not bundled. Language-school guidance used as a secondary usage source.",
            "bundled": False,
        },
        {
            "source_id": "src-wikipedia-keigo",
            "title": "Honorific speech in Japanese",
            "url": "https://en.wikipedia.org/wiki/Honorific_speech_in_Japanese",
            "publisher": "Wikimedia Foundation",
            "source_type": "reference",
            "fetched_at": FETCHED_AT,
            "support_status": "model_assessed",
            "license_note": "Linked, not bundled. Wikipedia content is CC BY-SA 4.0; used only for general framing.",
            "bundled": False,
        },
    ]

    objectives = [
        {
            "objective_id": "obj-context-discrimination",
            "ordinal": 1,
            "title": "Tell everyday affection from a direct romantic declaration",
            "evidence_target": "discrimination",
            "evidence_criteria": [
                "Names which line is the romantic confession",
                "Names which line is affection between friends",
                "Points at the cue (form or request) that changes the reading",
            ],
            "estimated_minutes": 8,
            "sections": [
                {"section_id": "sec-two-ways", "title": "Two ways of saying it", "path": "content/section-01-two-ways.md"}
            ],
            "checks": [
                {
                    "check_id": "chk-discrimination-1",
                    "version": 1,
                    "evidence_target": "discrimination",
                    "stimulus": (
                        "Two lines are shown. A: うん、好きだよ。 (un, suki da yo.) said to a friend after an outing. "
                        "B: 好きです。付き合ってください。 (suki desu. tsukiatte kudasai.) said privately to someone "
                        "the speaker is not yet close to. Which line is the romantic confession, and which cue makes it one?"
                    ),
                    "rubric": [
                        "Chooses B as the romantic confession",
                        "Chooses A as affection between friends",
                        "Names a cue: the request 付き合ってください (tsukiatte kudasai), the polite です form, or the private setting",
                    ],
                    "reference_answer": "B (romantic confession)",
                    "accepted_alternatives": ["B", "b", "confession", "the confession"],
                    "locale": "ja-JP",
                    "audit_state": "unreviewed",
                }
            ],
        },
        {
            "objective_id": "obj-polite-selection",
            "ordinal": 2,
            "title": "Choose the polite expression for a first confession",
            "evidence_target": "comprehension",
            "evidence_criteria": [
                "Selects the polite line for a first confession",
                "Relates the choice to the addressee and setting",
            ],
            "estimated_minutes": 10,
            "sections": [
                {"section_id": "sec-choosing", "title": "Choosing by addressee and setting", "path": "content/section-02-choosing.md"}
            ],
            "checks": [
                {
                    "check_id": "chk-polite-selection-1",
                    "version": 1,
                    "evidence_target": "comprehension",
                    "stimulus": (
                        "Context: an adult speaker, an adult addressee they respect but do not know well, a private "
                        "setting, a first confession, standard polite register. Which line from this pack fits, and why?"
                    ),
                    "rubric": [
                        "Selects the polite 好きです line",
                        "Explains that the addressee is not close and the setting is deliberate",
                        "Does not select the intimate line for a first confession",
                    ],
                    "reference_answer": "好きです (suki desu)",
                    "accepted_alternatives": ["好きです", "すきです", "suki desu", "suki desu."],
                    "locale": "ja-JP",
                    "audit_state": "unreviewed",
                }
            ],
        },
        {
            "objective_id": "obj-intimate-recall",
            "ordinal": 3,
            "title": "Recall the intimate declaration in a new context",
            "evidence_target": "recall",
            "evidence_criteria": [
                "Produces the intimate line in a new, non-identical context",
                "Does not reuse the first-confession line for a settled partnership",
            ],
            "estimated_minutes": 8,
            "sections": [
                {"section_id": "sec-new-context", "title": "A new context", "path": "content/section-03-new-context.md"}
            ],
            "checks": [
                {
                    "check_id": "chk-intimate-recall-1",
                    "version": 1,
                    "evidence_target": "recall",
                    "stimulus": (
                        "New context, no answer visible: you are at home with your spouse of ten years, in a private "
                        "moment, and the feeling is settled and deep rather than new. Write the line you would use."
                    ),
                    "rubric": [
                        "Produces 愛してる (aishiteru), in script or romaji",
                        "Does not produce the first-confession request",
                        "Keeps the setting private and the addressee a long-term partner",
                    ],
                    "reference_answer": "愛してる (aishiteru)",
                    "accepted_alternatives": ["愛してる", "あいしてる", "aishiteru", "aishiteru."],
                    "locale": "ja-JP",
                    "audit_state": "unreviewed",
                }
            ],
        },
        {
            # H-186: this objective used to be a free-English "explain the register" prompt with an
            # empty accepted-alternatives list. The import projection stores a ``transfer`` target as
            # ``rubric_only``, and this build has no configured aux grader, so the one check the
            # library pointed Resume at could only answer ``needs_retry``. It is now a closed choice
            # about a third situation: one register genuinely fits, and the learner names it. No
            # model-assessed score is claimed, and the open explanation is no longer graded at all.
            "objective_id": "obj-register-transfer",
            "ordinal": 4,
            "title": "Choose the register for a close friend in public",
            "evidence_target": "discrimination",
            "evidence_criteria": [
                "Picks the casual register for a close friend in public",
                "Does not apply the intimate line to a friend in public",
                "Reads the choice from the addressee and the public setting",
            ],
            "estimated_minutes": 7,
            "sections": [
                {"section_id": "sec-new-context-2", "title": "A close friend in public", "path": "content/section-03-new-context.md"}
            ],
            "checks": [
                {
                    "check_id": "chk-friend-public-choice-1",
                    "version": 1,
                    "evidence_target": "discrimination",
                    "stimulus": (
                        "A close friend, in public, after an outing: you want to say something affectionate "
                        "without making it a confession and without overstating the relationship. Which "
                        "register fits? Answer A, B or C. A: casual register (suki da yo). B: polite "
                        "register (suki desu). C: intimate register (aishiteru)."
                    ),
                    "rubric": [
                        "Chooses the casual register for a close friend in public",
                        "Does not choose the polite or intimate register for that relationship",
                        "Keeps the choice tied to the addressee and the public setting",
                    ],
                    "reference_answer": "A (casual register)",
                    "accepted_alternatives": ["A", "a", "casual", "casual register", "suki da yo", "suki dayo"],
                    "locale": "ja-JP",
                    "audit_state": "unreviewed",
                }
            ],
        },
    ]

    return packs.build_manifest(
        pack_id="japanese-affection-context-l0",
        pack_version="2.1.0",
        title="Japanese affection and register — a Sample L0 classroom",
        subtitle="Four lines, three addressees, one decision: who is listening, how close, and where.",
        recipe="casual",
        locale="ja-JP",
        level_label="CEFR A1 · ab initio (L0)",
        minimum_coursebook_version="0.1.0",
        # H-186: the release now ships v2 media playback, so the bundled demo declares its two
        # real assets as ``media[]`` links. A v1 document may not carry them (M1-M7 in packs.py).
        contract_version=2,
        media=[
            # H-197: the cover plate is the pack's first linked visual, so the Workshop's
            # catalogue cover is the plate the catalogue names, not an incidental figure.
            {
                "path": COVER_PATH,
                "section_path": "content/section-01-two-ways.md",
                "caption": COVER_CAPTION,
            },
            {
                "path": NARRATION_PATH,
                "section_path": "content/section-02-choosing.md",
                "caption": NARRATION_CAPTION,
            },
            {
                "path": "content/relationship-map.png",
                "section_path": "content/section-01-two-ways.md",
                "caption": VISUAL_CAPTION,
            },
        ],
        license={
            **UNSPECIFIED_LICENSE,
            "per_artifact": [
                {
                    "path": COVER_MASTER,
                    "license_id": "CC0-1.0",
                    "attribution": COVER_ATTRIBUTION,
                },
                {
                    "path": COVER_CROP,
                    "license_id": "CC0-1.0",
                    "attribution": COVER_ATTRIBUTION,
                },
                {
                    "path": "content/relationship-map.png",
                    "license_id": "CC0-1.0",
                    "attribution": "Deterministic schematic generated by the Coursebook demo pack builder; no third-party imagery.",
                },
                {
                    "path": NARRATION_PATH,
                    "license_id": "Apache-2.0",
                    "attribution": (
                        "Synthetic speech generated locally with Kokoro-82M (hexgrad/Kokoro-82M, "
                        "Apache-2.0), voice jf_alpha, on 2026-11-07. No human speaker was recorded. "
                        "Not a native-speaker pronunciation reference."
                    ),
                },
            ],
        },
        attribution=JAPANESE_ATTRIBUTION,
        contributors=[
            {"name": "Coursebook demo pack", "role": "author"},
            {"name": "Kokoro-82M voice jf_alpha (synthetic; no human speaker)", "role": "narrator"},
        ],
        objectives=objectives,
        files=files,
        file_metadata=metadata,
        sources=sources,
        content_notes=[
            "Fresh verification: every Japanese wording and usage claim was re-read against the linked sources on "
            "2026-11-06. No native-speaker review is recorded, and none is claimed.",
            "Pack revision note: this pack now declares cb.pack v2 and links its two real assets through media[]. "
            "No Japanese wording changed in that revision, so the 2026-11-06 wording check still describes the "
            "language taught here. No new language or native-speaker review was performed for it.",
            "L0 script policy: Japanese script is always paired with romaji and an English meaning. Romaji is a "
            "scaffold that fades; a romaji-only answer is not evidence of reading Japanese.",
            "Register is taught as a function of addressee, relationship and setting, not as one correct translation "
            "of the English phrase 'I love you'.",
            "Culture claims are kept narrow and attributed; regional, generational and personal variation is stated "
            "in the lesson rather than smoothed away.",
            "One narration clip is bundled: content/narration-polite-confession.mp3, the polite first-confession "
            "line, synthesized offline on 2026-11-07 with Kokoro-82M voice jf_alpha (Apache-2.0), 24 kHz mono, "
            "encoded to 64 kbps MP3 with LAME 4.0. Its text equivalent carries the Japanese line, its romaji and "
            "its English meaning. Fading scaffold: the audio is a model of the line, not a substitute for the "
            "script or the romaji.",
            "The fourth objective is a closed choice about a third situation, graded by exact comparison against "
            "its accepted registers. It is not a model-assessed explanation, and the pack claims no score for an "
            "open-response answer.",
            "2.1.0 adds one composed cover plate (content/cover-plate.png), linked first in media[] so the "
            "Workshop storefront, the Library row and the course detail show the same plate. It is decorative "
            "illustration: it carries no register facts. The relationship map remains the pack's deterministic "
            "schematic and the only visual that states them. No wording, check or source changed.",
        ],
        safety_notes=[
            "Audio is bundled and is synthetic. It is not a native-speaker pronunciation model, and this pack "
            "implements no listening check and no pronunciation score, so no listening evidence is claimed.",
            "The topic is affection and confession, written for adult self-study; there is no explicit material.",
        ],
        accessibility_notes=[
            "Every Japanese line carries romaji and an English meaning.",
            "The relationship schematic has a text equivalent on its file record and a short caption beside it on "
            "the lesson page.",
            "The cover plate is illustration only: it has a text equivalent on its file record and the caption "
            "'Cover plate — illustration, not a technical diagram.' beside it. Nothing in the course depends on "
            "seeing it.",
            "The narration clip carries its Japanese line, romaji and English meaning as its text equivalent and as "
            "its lesson caption, and the lesson does not depend on hearing it.",
            "Content files are UTF-8 without BOM; CJK line breaking and font fallback are renderer responsibilities.",
        ],
        default_dials={"pace": "light", "depth": "survey", "assessment": "self_check", "autonomy": "guided"},
    )


def parent_manifest() -> dict:
    paths = ["content/learner-page.md", "content/answer-guide.md", "content/parent-guide.md"]
    files = {path: (PARENT / path).read_bytes() for path in paths}
    metadata = {
        "content/learner-page.md": {"mime": "text/markdown", "role": "learner_page"},
        "content/answer-guide.md": {"mime": "text/markdown", "role": "answer_guide"},
        "content/parent-guide.md": {"mime": "text/markdown", "role": "parent_guide"},
    }
    objectives = [
        {
            "objective_id": "obj-read-scale",
            "ordinal": 1,
            "title": "Read the marks on a measuring jug",
            "evidence_target": "comprehension",
            "evidence_criteria": [
                "Counts the 50 ml marks instead of estimating",
                "Gives the quantity in millilitres",
            ],
            "estimated_minutes": 5,
            "sections": [
                {"section_id": "sec-learner-1", "title": "Task 1 — read the jug", "path": "content/learner-page.md"}
            ],
            "checks": [
                {
                    "check_id": "chk-read-scale-1",
                    "version": 1,
                    "evidence_target": "comprehension",
                    "stimulus": "The jug is marked every 50 ml. Liquid reaches the third mark. How many millilitres are in the jug?",
                    "rubric": [
                        "Answers 150 ml",
                        "Refers to the three 50 ml marks",
                        "Does not estimate without counting",
                    ],
                    "reference_answer": "150 ml",
                    "accepted_alternatives": ["150", "150ml", "150 millilitres", "150 milliliters"],
                    "audit_state": "unreviewed",
                }
            ],
        },
        {
            "objective_id": "obj-double-recipe",
            "ordinal": 2,
            "title": "Double a recipe quantity and explain the operation",
            "evidence_target": "procedure",
            "evidence_criteria": [
                "Adds the single batch quantity to itself",
                "Explains the operation in words",
            ],
            "estimated_minutes": 5,
            "sections": [
                {"section_id": "sec-learner-2", "title": "Task 2 — double the recipe", "path": "content/learner-page.md"}
            ],
            "checks": [
                {
                    "check_id": "chk-double-recipe-1",
                    "version": 1,
                    "evidence_target": "procedure",
                    "stimulus": "One batch uses 175 ml. You make two batches of the same size. How much juice do you need?",
                    "rubric": [
                        "Answers 350 ml",
                        "Shows 175 + 175 (or 175 x 2)",
                        "Explains the operation in words",
                    ],
                    "reference_answer": "350 ml",
                    "accepted_alternatives": ["350", "350ml", "350 millilitres", "350 milliliters"],
                    "audit_state": "unreviewed",
                }
            ],
        },
    ]
    return packs.build_manifest(
        pack_id="parent-measurement-practice",
        pack_version="1.0.0",
        title="Parent demo: measuring ingredients together",
        subtitle="A ten-minute parent-led measurement practice with a separate answer guide.",
        recipe="parent",
        locale="en-US",
        level_label="Age 8-10 · parent-led",
        minimum_coursebook_version="0.1.0",
        # H-73 §13 ordering: the bundled pack stays at ``cb.pack`` v1 until the release that
        # ships v2 media playback is the version this demo names. Re-issuing v2 first would make
        # the bundled pack unimportable on every build that only knows v1 — a worse defect than
        # an unplayed file.
        contract_version=1,
        license=UNSPECIFIED_LICENSE,
        attribution=ORIGINAL,
        contributors=[{"name": "Coursebook demo pack", "role": "author"}],
        objectives=objectives,
        files=files,
        file_metadata=metadata,
        content_notes=[
            "Parent recipe: this pack is prepared by a parent and approved before use; it is not a child-facing chat.",
            "The learner page never carries the answer key. Answers live only in the answer guide, which the manifest "
            "declares with the answer_guide role.",
            "Observation records from a session are parent-reported evidence and are never exported with the pack.",
        ],
        safety_notes=["Uses water and a jug; no heat, sharp tools or hazardous materials."],
        accessibility_notes=[
            "Learner page uses short sentences and a blank line per answer.",
            "The answer guide repeats each task number so a parent can match pages without scanning.",
        ],
        default_dials={"pace": "light", "depth": "working", "assessment": "self_check", "autonomy": "guided"},
    )


def technical_manifest() -> dict:
    paths = [
        "content/section-01-anatomy.md",
        "content/section-02-labels.md",
        "content/source-notes.md",
    ]
    files = {path: (TECHNICAL / path).read_bytes() for path in paths}
    files[COVER_MASTER] = cover_plate_png("technical")
    files[COVER_CROP] = cover_crop_png("technical")
    metadata = {
        "content/section-01-anatomy.md": {"mime": "text/markdown", "role": "section"},
        "content/section-02-labels.md": {"mime": "text/markdown", "role": "section"},
        "content/source-notes.md": {"mime": "text/markdown", "role": "source_note"},
        COVER_MASTER: {
            "mime": "image/png",
            "role": "visual",
            "text_equivalent": TECHNICAL_COVER_TEXT,
            "description": (
                "Press Plate cover for this pack (16:9 master): five flat inks, printed "
                "deterministically. Decorative material; it is not a schema diagram and has no text."
            ),
        },
        COVER_CROP: {
            "mime": "image/png",
            "role": "visual",
            "text_equivalent": TECHNICAL_COVER_TEXT,
            "description": (
                "Press Plate cover for this pack (864x576, a mechanical centre crop of the 16:9 "
                "master for a 3:2 card). Same plate, same five inks."
            ),
        },
    }
    objectives = [
        {
            "objective_id": "obj-manifest-anatomy",
            "ordinal": 1,
            "title": "Read what a pack manifest declares",
            "evidence_target": "comprehension",
            "evidence_criteria": [
                "Names the field that lists every shipped file",
                "Says what each file record must match",
            ],
            "estimated_minutes": 6,
            "sections": [
                {
                    "section_id": "sec-anatomy",
                    "title": "Anatomy of a pack",
                    "path": "content/section-01-anatomy.md",
                }
            ],
            "checks": [
                {
                    "check_id": "chk-anatomy-files-1",
                    "version": 1,
                    "evidence_target": "comprehension",
                    "stimulus": (
                        "A pack's manifest declares every file it ships, each with a path, mime, "
                        "size and sha256. Which manifest field holds that list?"
                    ),
                    "rubric": [
                        "Names files[]",
                        "Does not name objectives[] or sources[]",
                        "Says each record's bytes must match its declared size and hash",
                    ],
                    "reference_answer": "the files list",
                    "accepted_alternatives": ["files", "the files field", "files array", "file list"],
                    "locale": "en-US",
                    "audit_state": "unreviewed",
                }
            ],
        },
        {
            "objective_id": "obj-label-meaning",
            "ordinal": 2,
            "title": "Say what an unreviewed check record means",
            "evidence_target": "discrimination",
            "evidence_criteria": [
                "Separates a hash match from a human review",
                "Reads audit_state as a recorded fact about review",
            ],
            "estimated_minutes": 6,
            "sections": [
                {
                    "section_id": "sec-labels",
                    "title": "What a label can and cannot prove",
                    "path": "content/section-02-labels.md",
                }
            ],
            "checks": [
                {
                    "check_id": "chk-label-unreviewed-1",
                    "version": 1,
                    "evidence_target": "discrimination",
                    "stimulus": (
                        "A pack's check carries audit_state \"unreviewed\". What does that record "
                        "mean, and what does it not mean?"
                    ),
                    "rubric": [
                        "Says no human review of that check is recorded",
                        "Does not read it as a failed or unsafe pack",
                        "Does not read a matching hash as a human review",
                    ],
                    "reference_answer": "that check has no recorded human review",
                    "accepted_alternatives": [
                        "unreviewed",
                        "no human review",
                        "no human review recorded",
                        "nobody has reviewed it",
                    ],
                    "locale": "en-US",
                    "audit_state": "unreviewed",
                }
            ],
        },
    ]
    return packs.build_manifest(
        pack_id="technical-demo-pack",
        pack_version="2.0.0",
        title="Technical demo: reading a pack before you install it",
        subtitle="Two sections on the pack contract: what a manifest declares, and what a trust label can prove.",
        recipe="one_off",
        locale="en-US",
        level_label="Technical · for pack readers",
        minimum_coursebook_version="0.1.0",
        # H-197: 2.0.0 moves this fixture to cb.pack v2 so it can carry the one composed cover
        # plate through media[]. The cover is the pack's only media and it is decorative.
        contract_version=2,
        media=[
            {
                "path": COVER_MASTER,
                "section_path": "content/section-01-anatomy.md",
                "caption": COVER_CAPTION,
            },
        ],
        license={
            "id": "CC0-1.0",
            "redistribution": "local_only",
            "note": (
                "Original Coursebook-authored teaching text and Press Plate about this repository's "
                "own pack contract. No third-party text or media is bundled; the repository files it "
                "cites are read locally by the pack maintainer, not redistributed."
            ),
            "per_artifact": [
                {
                    "path": COVER_MASTER,
                    "license_id": "CC0-1.0",
                    "attribution": COVER_ATTRIBUTION,
                },
                {
                    "path": COVER_CROP,
                    "license_id": "CC0-1.0",
                    "attribution": COVER_ATTRIBUTION,
                },
            ],
        },
        attribution=(
            "Original teaching text and cover plate: Coursebook demo pack. No third-party text or "
            "media is bundled."
        ),
        contributors=[{"name": "Coursebook demo pack", "role": "author"}],
        objectives=objectives,
        files=files,
        file_metadata=metadata,
        content_notes=[
            "Every claim in this pack is about the cb.pack contract as implemented in this repository "
            "(contracts/pack-manifest.v1.json, contracts/pack-manifest.v2.json, "
            "contracts/vocabulary.v1.json, coursebook/archive.py). It links no external source and "
            "quotes no third-party text.",
            "The pack claims no human review and no native-speaker or expert review: its checks are "
            "recorded audit_state \"unreviewed\", which is the fact the second section teaches.",
            "This is a technical demo. It teaches the pack format, not the subject of any other pack.",
            "2.0.0 adds one composed cover plate (content/cover-plate.png) and moves the document to "
            "cb.pack v2 so the plate can be linked through media[]. The plate is decorative: it is "
            "not a diagram of the manifest schema and states no field, count or rule.",
        ],
        safety_notes=[
            "Text plus one decorative cover plate. No external services, no learner data, and no "
            "image that carries a technical claim.",
        ],
        accessibility_notes=[
            "Plain markdown; every field name is written as literal text so it survives a screen reader.",
            "The cover plate has a text equivalent on its file record and the caption 'Cover plate — "
            "illustration, not a technical diagram.' beside it; nothing in the course depends on "
            "seeing it.",
        ],
        default_dials={"pace": "light", "depth": "survey", "assessment": "self_check", "autonomy": "independent"},
    )


def write_manifest(directory: Path, manifest: dict) -> Path:
    path = directory / "pack.json"
    text = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    packs.load_manifest(path)
    return path


def main() -> int:
    (JAPANESE / "content" / "relationship-map.png").write_bytes(relationship_map_png())
    # H-197: each plate is written beside its pack before the manifest is rebuilt, so the committed
    # bytes, the declared sha256 and the catalogue cover path all come from one generator.
    (JAPANESE / COVER_MASTER).write_bytes(cover_plate_png("japanese"))
    (JAPANESE / COVER_CROP).write_bytes(cover_crop_png("japanese"))
    (TECHNICAL / COVER_MASTER).write_bytes(cover_plate_png("technical"))
    (TECHNICAL / COVER_CROP).write_bytes(cover_crop_png("technical"))
    for directory, builder in (
        (JAPANESE, japanese_manifest),
        (PARENT, parent_manifest),
        (TECHNICAL, technical_manifest),
    ):
        manifest = builder()
        path = write_manifest(directory, manifest)
        print(f"{path.relative_to(ROOT.parent.parent)}  {manifest['content_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
