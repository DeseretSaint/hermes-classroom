#!/usr/bin/env python3
"""VQ-002 — build and judge the `field_atlas` visual-kit manifest.

The manifest is the only source of truth for a screen consuming the kit: a screen card reads
`kit.json`, it does not invent a path (`docs/launch/VISUAL-QUALITY-PROGRAM.md` §3). So the manifest
is written by this script from a declarative table and then checked back against the bytes on disk,
rather than hand-typed.

    python3 scripts/vq002-kit-audit.py --write     # rewrite kit.json from the table below
    python3 scripts/vq002-kit-audit.py --check     # verify every claim in kit.json
    python3 scripts/vq002-kit-audit.py --calibrate # prove the textless detector on known-text refs

`--check` is the acceptance run: it recomputes sha256, dimensions, role coverage, the hero size,
the two cover aspects for every course on the real Home shelf, the 2x source claim, the quiet-field
contrast, the palette family, and the textless claim. It reads the shelf from a coursebook
database, never from a proof HTML.

Version 2 is the owner-directed rebuild of `field_atlas@1`. v1's contact sheet was rejected on
2026-11-11 02:22 as below reference quality; its plates are retained under `rejected-v1/` as
evidence and are not a consumer fallback. v2 is generated with the reference mockups attached and
describes places, not still lifes.

Exit codes: 0 clean, 1 a claim failed, 2 the manifest or a source is missing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT_DIR = ROOT / "assets" / "visual-kits" / "field_atlas"
KIT_JSON = KIT_DIR / "kit.json"
REFS_HOME = ROOT / "docs" / "concept-parity" / "refs" / "home.png"
REFS_CLASSROOM = ROOT / "docs" / "concept-parity" / "refs" / "classroom.png"
RAW_DIR = ROOT / ".vq-raw" / "field_atlas" / "v2"

GRAMMAR = "field_atlas"
VERSION = 2
ART_BIBLE = "docs/concept-parity/ART-BIBLE.md"

#: The seeded library the Home shelf was read from. This is the product's own import path
#: (`scripts/seed-demo-course.py`), not a fixture: three bundled packs, three courses.
SHELF_DB = Path(
    "/home/deseretsaint/.hermes/coursebook-test-vq006/home/plugin-data/coursebook/data.db"
)

#: Titles that exist only in the CP-053 proof mockup. The card forbids them by name.
FICTIONAL_TITLES = ("Auto Repair Fundamentals", "Astronomy", "Sourdough")

PALETTE = {
    "paper": "#f7f1e4",
    "ink": "#3a2318",
    "field": "#2f6047",
    "ochre": "#7b4b0a",
    "lamp": "#e8a93a",
    "coral": "#9c2e1c",
}

#: The contract ink a quiet field is measured against (ART-BIBLE §2/§9: the field must leave the
#: contract ink at or above 4.5:1 on its darkest fifth). `ink` above is the drawn line.
CONTRACT_INK = (0x1A, 0x17, 0x13)

MEDIUM = "opaque gouache on warm paper, dark warm-brown ink contour drawn last, one key light upper left"

COMPOSITION = (
    "field-atlas place: a lantern-lit street, cafe or workshop interior built in three depth "
    "planes — painted foreground props, a midground counter or bench, an architectural background "
    "with a window or open street; the hero keeps a quiet painted sky in the upper third for DOM "
    "type, and every other plate is full-bleed with no bare paper margin"
)

#: The owner's ceiling for this round: 33 attempts in total (v1's 9 + up to 24 additional), and at
#: most four attempts on any one asset within this round. Read from the manifest by the judge, so a
#: later card can raise it without editing the check.
ATTEMPTS_ALLOWED = 33
PER_ASSET_MAX = 4
ADDITIONAL_ALLOWED = 24

#: One deterministic colour temper, then one print-safety lift. The provider does not honour the
#: bible's hexes; measured on the shipped bytes this brings the painted ground to #F2EDE2 against
#: the art bible's #f7f1e4 (channel distance 6), where the untempered raw measured #EFE5CD (23).
#: The lift is applied last and after a clamp, because the downscale filter's ringing goes negative
#: and would otherwise survive under `+level` as pure black.
TEMPER = "magick -modulate 105,75,100, applied to the provider raw before any crop or resize"
LIFT = "magick -clamp +level 4%,100% applied last, after the resize (ART-BIBLE §9 rule 5)"

PIPELINE = f"{TEMPER}; then crop/resize; then {LIFT}"

#: The chain a consuming screen walks when a kit plate is absent. It never names a Press Plate pack
#: cover: UI-DECISIONS D-006 and VISUAL-QUALITY-PROGRAM forbid the substitution. A display cover
#: falls back to the course's own approved master, then to a textless material field.
FALLBACKS = {
    "lesson_scene": ["section", "background"],
    "cover": ["course-master", "background"],
    "hero": ["background"],
    "object": [],
    "fox": [],
}

ALLOWED_FALLBACKS = frozenset({"section", "background", "course-master"})
FORBIDDEN_FALLBACKS = frozenset(
    {"pack-cover", "pack-cover-plate", "press-plate", "press-plate-cover"}
)

#: The textless detector. OCR alone cannot tell painted pseudo-lettering from line art — measured
#: on this provider's output, a notice board of gibberish scored 7–54 % while a painted window
#: lattice scored 30–52 %, so a confidence floor cannot separate them. What OCR *can* do reliably
#: is find readable text: on `refs/home.png` and `refs/classroom.png` the real UI strings score
#: 74–95 %. So the judge fails a plate that yields a token of three or more alphanumeric characters
#: at 60 % or better, records every token it saw, and `--calibrate` proves the rule catches the two
#: reference mockups. Painted pseudo-lettering is caught by the recorded vision pass instead.
OCR_CONF_FLOOR = 60
OCR_MIN_ALNUM = 3

#: The 3:2 covers' natural crop is 2304x1536 and the plate shipped from it is 1200x800, rendered at
#: 600x400. The round-3 defect was a note that named the wrong referent ("2400x1600 would be an
#: exact 2x of the 600x400 render", "1.92x of the 600x400 render"): Gate 2 reads natural-vs-rendered
#: size out of provenance, so a wrong ratio there fails a cover that actually passes. The ratios are
#: recomputed by the judge, and these exact sentences are refused so the error cannot be pasted back.
COVER_3X2_NATURAL = (2304, 1536)
COVER_3X2_SHIPPED = (1200, 800)
COVER_3X2_RENDERED = (600, 400)
WRONG_3X2_NOTES = (
    "2400x1600",
    "1.92x of the 600x400 render",
    "1.92x of the render",
    "1.92x of its render",
)

# --------------------------------------------------------------------------------------
# the plates

#: Every generated plate that ships. `raw` names the provider return kept under `.vq-raw`; `derives`
#: lists the shipped paths the single raw produces (a 4:5 crop of the 3:2 master is not a second
#: generation attempt and must not inflate the budget).
PLATES = [
    {
        "id": "home-hero",
        "role": "hero",
        "path": "hero/home-hero.png",
        "raw": "hero-03.raw.png",
        "media_url": "https://v3b.fal.media/files/b/0ab2054a/D7WU66zYXDwxsxBnjHZfK_O5vPgeT6.png",
        "derivation": "raw 2688x1536 resized 50% to the required 1344x768",
        "source": {"path": "hero/home-hero@2x.png", "size": [2688, 1536], "scale": 2.0,
                   "note": "the provider source, shipped beside the 1344x768 plate so Gate 2's "
                           "'natural size at least 2x rendered' can be satisfied without a second "
                           "generation"},
        "quiet_field": {"x": 370, "y": 15, "w": 604, "h": 230,
                        "note": "the centre of the painted sky, where Home's display title sits"},
        "noren": {"x": 80, "y": 280, "w": 260, "h": 210},
        "vision": {
            "reviewed_on": "2026-11-11",
            "checks": "full-bleed street, three depth planes, blank lanterns, blank gate panel, "
                      "no notice board or sign, no people",
            "residual": "lantern strings and roof eaves cross the title band; the painted sky "
                        "between them is the quiet field, so the DOM title must not sit on a lantern",
        },
        "prompt": (
            "Full-bleed painted plate of a PLACE, not a still life: an edge-to-edge scene with no "
            "bare paper margin on any side. Subject: a narrow lane in a Japanese paper-lantern "
            "quarter in warm evening light, seen at eye level, receding into depth. Layered depth "
            "in three planes. BACKGROUND: a row of low wooden townhouses with tiled eaves, "
            "horizontal timber slats and lattice windows; strings of round paper lanterns cross "
            "the lane above, lit warm from within; at the far end of the lane a plain wooden gate "
            "frame, and its crossbeam panel is a completely blank plain board with no mark, no "
            "glyph, no character and no carving; distant roof lines painted soft, pale and "
            "low-contrast at the top of the frame. MIDGROUND: at the left an open shopfront of a "
            "small cafe, a plain indigo noren cloth hanging in its doorway, inside a wooden service "
            "counter with shelves of blank ceramic bowls, blank jars and three plain bottles whose "
            "labels are empty pale rectangles with no writing; at the right the timber wall and "
            "shuttered window of the neighbouring house, a low bench, stacked wooden crates and a "
            "tub of potted plants outside. FOREGROUND: a painted earth-and-stone lane running off "
            "the bottom edge, wooden crates, a short stack of blank bowls, a small potted plant, "
            "one stool leg. Hanging paper lanterns of three sizes, all completely blank with no "
            "marks of any kind. Every wall is plain painted timber and lattice panelling only: no "
            "notice board, no framed picture, no pinned paper, no poster, no menu, no chalkboard, "
            "no A-frame sign board, no hanging shop sign, no banner. The upper third of the frame "
            "is a quiet field reserved for a headline typeset later: pale warm cream sky wash with "
            "a couple of faint broad brush marks, distant roof tops and one lantern string painted "
            "softly with low contrast and no small detail, still painted environment and not bare "
            "parchment. Painted in opaque gouache on warm paper #f7f1e4, dark warm-brown ink "
            "contour #3a2318 drawn last, visible flat brush-shaped marks inside every mass, crisp "
            "brush-stopped edges, one soft key light from the upper left, one shade plane "
            "down-right in a darker tint of the same pigment. Warm pigments only: warm cream "
            "paper, ochre wood #7b4b0a, field green #2f6047, lamp gold #e8a93a, terracotta "
            "#9c2e1c, one plain indigo cloth #2b2a61. The sky is pale warm cream, never blue. No "
            "blue, no grey, no neutral black, no gradient, no glow, no bloom, no vignette, no "
            "frame, no border. Textless: no letters, no words, no numbers, no kanji, no kana, no "
            "signage of any kind, no watermark, no logo, no UI chrome. No people, no hands, no "
            "faces, no animals, no fox."
        ),
        "reference": "docs/concept-parity/refs/home.png",
        "derives": ["hero/home-hero.png"],
    },
    {
        "id": "japanese-cover-3x2",
        "role": "cover",
        "path": "cover/japanese-3x2-1200x800.png",
        "raw": "japanese-02.raw.png",
        "media_url": "https://v3b.fal.media/files/b/0ab2056b/Tjjd2kvgpdg3JxBc26Vqf_l3GQ0GcB.png",
        "derivation": "raw 2688x1536 centre crop 2304x1536, resized to 1200x800",
        "source": {"path": None, "size": [2304, 1536], "scale": 2.0,
                   "ratios": {"shipped_vs_render": 2.0, "natural_vs_shipped": 1.92,
                              "natural_vs_render": 3.84},
                   "note": "the shipped 1200x800 plate is exactly 2x the 600x400 render; the "
                           "2304x1536 natural crop is 1.92x the shipped plate and 3.84x the "
                           "render, so the 2x requirement is met by the shipped plate itself, "
                           "not only by the crop that fed it"},
        "vision": {
            "reviewed_on": "2026-11-11",
            "checks": "dense cafe interior, counter and dresser of bowls, pendant lamps, window "
                      "onto a street, noren, no emblems on any lantern, blank bottle labels",
            "residual": "the noren is a large cool mass; it is the one ratified indigo cloth",
        },
        "noren": {"x": 960, "y": 60, "w": 240, "h": 500},
        "prompt": (
            "Full-bleed painted place, edge to edge with no bare paper margin on any side: the "
            "inside of a small neighbourhood Japanese cafe in warm afternoon light, seen straight "
            "on, with real depth through three planes. FOREGROUND: the near end of a plain wooden "
            "service counter running off the bottom edge, two simple wooden stools below it, a "
            "short stack of blank bowls and a small brass teapot on the counter. MIDGROUND: the "
            "counter continues across the frame; behind it a tall wooden dresser of open shelves "
            "crowded with plain ceramic bowls, stacked plates, blank jars and a row of plain "
            "bottles whose paper labels are completely empty; a plain indigo noren cloth hangs in "
            "the open doorway at the right; a wooden bench with a folded green cloth at the left. "
            "BACKGROUND: a warm plaster wall, a low shelf carrying more bowls, and one wide window "
            "at the left through which a sunlit street of low wooden houses can be seen, softer "
            "and paler in the distance; a ceiling beam and two pendant lamps hang above. Every "
            "lantern, lamp and cloth is a completely plain blank surface: no emblem, no crest, no "
            "mon, no badge, no symbol and no mark of any kind. The whole scene is dense with "
            "furniture, crockery and architecture, layered from near to far, with objects "
            "overlapping. Subject kept centred in the middle half of the frame so a narrow vertical "
            "crop still holds the counter and the shelves. Painted in opaque gouache on warm paper "
            "#f7f1e4, dark warm-brown ink contour #3a2318 drawn last, visible flat brush-shaped "
            "marks inside every mass, crisp brush-stopped edges, one soft key light from the upper "
            "left, one shade plane down-right in a darker tint of the same pigment. Warm pigments "
            "only: warm cream paper, ochre wood #7b4b0a, field green #2f6047, lamp gold #e8a93a, "
            "terracotta #9c2e1c, one plain indigo cloth #2b2a61. No blue, no grey, no neutral "
            "black, no gradient, no glow, no bloom, no vignette, no frame, no border. No notice "
            "board, no menu, no chalkboard, no sign of any kind, no framed picture, no poster. "
            "Textless: no letters, no words, no numbers, no kanji, no kana, no labels, no "
            "watermark, no logo, no UI chrome. No people, no hands, no faces, no fox."
        ),
        "reference": "docs/concept-parity/refs/home.png",
        "derives": ["cover/japanese-3x2-1200x800.png", "cover/japanese-4x5-640x800.png"],
        "course_key": "japanese",
    },
    {
        "id": "parent-cover-3x2",
        "role": "cover",
        "path": "cover/parent-3x2-1200x800.png",
        "raw": "parent-02.raw.png",
        "media_url": "https://v3b.fal.media/files/b/0ab20576/9aj2USg72eT3UE2uxche9_VQsFOEBH.png",
        "derivation": "raw 2688x1536 centre crop 2304x1536, resized to 1200x800",
        "source": {"path": None, "size": [2304, 1536], "scale": 2.0,
                   "ratios": {"shipped_vs_render": 2.0, "natural_vs_shipped": 1.92,
                              "natural_vs_render": 3.84},
                   "note": "same method as the japanese cover: the shipped 1200x800 plate is "
                           "exactly 2x the 600x400 render; the 2304x1536 natural crop is 1.92x "
                           "the plate and 3.84x the render"},
        "vision": {
            "reviewed_on": "2026-11-11",
            "checks": "full kitchen, tiled splashback, copper pans, shelf, cutting board, herbs, "
                      "bowls and jars, window onto a garden, no lettering, warm metal only",
            "residual": "the sink basin reads pale; no measuring mark or scale is painted",
        },
        "prompt": (
            "Full-bleed painted place, edge to edge with no bare paper margin on any side: a warm "
            "home kitchen in the middle of a cooking lesson, seen straight on, with real depth "
            "through three planes. FOREGROUND: a wide scrubbed wooden worktop running off the "
            "bottom edge and both side edges, holding a deep cream ceramic mixing bowl with a "
            "wooden spoon resting in it, a wide stoneware jug of milk, two whole oranges and a "
            "folded field-green tea cloth. MIDGROUND: a low wooden shelf on the wall behind the "
            "worktop crowded with stacked cream bowls, three blank ceramic jars, a plain wooden "
            "chopping board leaning against the wall and a hanging bunch of dried herbs; beneath "
            "the worktop, panelled cupboard doors and a drawer. BACKGROUND: the kitchen wall is "
            "busy, not bare: a tiled splashback of plain cream tiles above the worktop, a hanging "
            "rail with two warm copper pans, a small shelf with a warm brass kettle, and at the "
            "left a tall window above the sink, open to a soft sunlit garden of trees and a fence, "
            "paler in the distance. Dense, layered, objects overlapping, no large empty wall area "
            "and no flat blank panel standing in for scenery. Subject kept centred in the middle "
            "half of the frame so a narrow vertical crop still holds the worktop and the shelves. "
            "Every object is plain: no measuring marks, no scale, no dial, no numbers, no labels on "
            "any jar. All metal in the room is warm brass or copper, never steel, never chrome, "
            "never grey. Painted in opaque gouache on warm paper #f7f1e4, dark warm-brown ink "
            "contour #3a2318 drawn last, visible flat brush-shaped marks inside every mass, crisp "
            "brush-stopped edges, one soft key light from the upper left, one shade plane "
            "down-right in a darker tint of the same pigment. Warm pigments only: warm cream paper "
            "and tiles, ochre wood #7b4b0a, field green #2f6047, lamp gold #e8a93a, terracotta "
            "#9c2e1c, warm orange, copper. No blue, no grey, no neutral black, no chrome, no glass, "
            "no transparent vessel, no gradient, no glow, no bloom, no vignette, no frame, no "
            "border. No notice board, no recipe card, no chalkboard, no signage. Textless: no "
            "letters, no words, no numbers, no labels, no watermark, no logo, no UI chrome. No "
            "people, no children, no hands, no faces, no fox."
        ),
        "reference": "docs/concept-parity/refs/home.png",
        "derives": ["cover/parent-3x2-1200x800.png", "cover/parent-4x5-640x800.png"],
        "course_key": "parent",
    },
    {
        "id": "technical-cover-3x2",
        "role": "cover",
        "path": "cover/technical-3x2-1200x800.png",
        "raw": "technical-01.raw.png",
        "media_url": "https://v3b.fal.media/files/b/0ab2057b/c1xQT3AdJoDre9qC9voMD_JQQWW1uV.png",
        "derivation": "raw 2688x1536 centre crop 2304x1536, resized to 1200x800",
        "source": {"path": None, "size": [2304, 1536], "scale": 2.0,
                   "ratios": {"shipped_vs_render": 2.0, "natural_vs_shipped": 1.92,
                              "natural_vs_render": 3.84},
                   "note": "same method: the shipped 1200x800 plate is exactly 2x the 600x400 "
                           "render; the 2304x1536 natural crop is 1.92x the plate and 3.84x the "
                           "render"},
        "vision": {
            "reviewed_on": "2026-11-11",
            "checks": "workshop with shelving of plain boxes, pegboard of plain tools, bench with "
                      "parcel, blank open book, tray of parts, coiled cord; no diagrams, no marks",
            "residual": "none recorded",
        },
        "prompt": (
            "Full-bleed painted place, edge to edge with no bare paper margin on any side: the "
            "inside of a small warm workshop where a technical pack is read before anything is "
            "installed, seen straight on, with real depth through three planes. FOREGROUND: a "
            "heavy plain wooden workbench running off the bottom edge and both side edges, holding "
            "a thick book lying open with completely blank pages, a plain wrapped parcel tied with "
            "field-green twine, a small brass hand lens, a wooden tray of plain unlabelled parts "
            "and a coiled length of plain cord. MIDGROUND: the bench continues; behind it a tall "
            "wooden rack of open shelves crowded with plain wooden boxes, a rolled paper tube, two "
            "blank folded cloths, a stack of blank cards and a warm brass tin; below the bench, "
            "deep drawers and a wooden crate on the floor. BACKGROUND: a warm plaster and timber "
            "wall, a plank pegboard at the right hung with plain hand tools (hammer, spanner, "
            "pliers, all plain wood and warm metal, no markings), and at the left a tall workshop "
            "window showing a soft sunlit yard with a fence, a tree and stacked timber, paler in "
            "the distance; a ceiling beam and one hanging brass lamp above. Dense, layered, objects "
            "overlapping, no large empty wall area. Subject kept centred in the middle half of the "
            "frame so a narrow vertical crop still holds the bench and the shelves. All metal is "
            "warm brass or copper, never steel or chrome, never grey. Painted in opaque gouache on "
            "warm paper #f7f1e4, dark warm-brown ink contour #3a2318 drawn last, visible flat "
            "brush-shaped marks inside every mass, crisp brush-stopped edges, one soft key light "
            "from the upper left, one shade plane down-right in a darker tint of the same pigment. "
            "Warm pigments only: warm cream paper, ochre wood #7b4b0a, field green #2f6047, lamp "
            "gold #e8a93a, terracotta #9c2e1c. No blue, no grey, no neutral black, no chrome, no "
            "gradient, no glow, no bloom, no vignette, no frame, no border. No diagrams, no charts, "
            "no arrows, no rulers, no gauges, no dials, no numbers, no labels, no notice board, no "
            "signage. Textless: no letters, no words, no writing on any page, no watermark, no "
            "logo, no UI chrome. No people, no hands, no faces, no fox."
        ),
        "reference": "docs/concept-parity/refs/home.png",
        "derives": ["cover/technical-3x2-1200x800.png", "cover/technical-4x5-640x800.png"],
        "course_key": "technical",
    },
    {
        "id": "field-atlas-lesson-room",
        "role": "lesson_scene",
        "path": "lesson-scene/lesson-room.png",
        "raw": "lesson-01.raw.png",
        "media_url": "https://v3b.fal.media/files/b/0ab20584/5WFXXon7MCSJ4zr1_-K0b_OpkJCllG.png",
        "derivation": "raw 2688x1536 resized 50% to 1344x768",
        "source": {"path": "lesson-scene/lesson-room@2x.png", "size": [2688, 1536], "scale": 2.0,
                   "note": "the provider source shipped beside the 1344x768 plate; the classroom "
                           "reuses this scene full-bleed when no per-course plate exists"},
        "vision": {
            "reviewed_on": "2026-11-11",
            "checks": "cafe study room: counter, dresser of jars and bottles, three pendant lamps, "
                      "chairs and table, window onto a street, noren doorway, no lettering",
            "residual": "the pale wall band above the counter is the calm field for lesson text",
        },
        "noren": {"x": 1140, "y": 110, "w": 160, "h": 330},
        "prompt": (
            "Full-bleed painted place, edge to edge with no bare paper margin on any side: the "
            "inside of a warm cafe used as a study room, seen straight on, with real depth through "
            "three planes. FOREGROUND: two simple wooden chairs and the near edge of a plain "
            "wooden table running off the bottom edge, a closed plain notebook and a cream teacup "
            "on the table. MIDGROUND: a long wooden service counter crossing the frame behind the "
            "table, with a warm brass teapot, a small stack of blank bowls and a plain folded cloth "
            "on it; behind the counter a tall wooden dresser of open shelves crowded with plain "
            "jars, stacked plates, canisters and a short row of plain bottles with empty labels. "
            "BACKGROUND: a warm plaster wall, three pendant lamps with plain cream shades hanging "
            "on long cords above the counter, a low shelf with more bowls, and at the left a wide "
            "window open to a soft sunlit street of low wooden houses and a hanging paper lantern, "
            "paler in the distance; a ceiling beam and a doorway at the right with a plain indigo "
            "noren cloth. Dense, layered, objects overlapping from near to far, no large empty wall "
            "area. The middle of the frame above the counter is calm wall and lamp-lit air, kept "
            "simple so lesson text can be laid over it later, but still painted environment. "
            "Subject centred so a narrow vertical crop still holds the counter. Every lantern, "
            "lamp, jar and cloth is a completely plain blank surface: no emblem, no crest, no mon, "
            "no badge, no symbol, no mark of any kind. Painted in opaque gouache on warm paper "
            "#f7f1e4, dark warm-brown ink contour #3a2318 drawn last, visible flat brush-shaped "
            "marks inside every mass, crisp brush-stopped edges, one soft key light from the upper "
            "left, one shade plane down-right in a darker tint of the same pigment. Warm pigments "
            "only: warm cream paper, ochre wood #7b4b0a, field green #2f6047, lamp gold #e8a93a, "
            "terracotta #9c2e1c, one plain indigo cloth #2b2a61. No blue, no grey, no neutral "
            "black, no gradient, no glow, no bloom, no vignette, no frame, no border. No notice "
            "board, no menu, no chalkboard, no blackboard, no poster, no signage of any kind. "
            "Textless: no letters, no words, no numbers, no kanji, no kana, no labels, no "
            "watermark, no logo, no UI chrome. No people, no hands, no faces, no fox."
        ),
        "reference": "docs/concept-parity/refs/classroom.png",
        "derives": ["lesson-scene/lesson-room.png"],
    },
]

#: The 4:5 display covers, derived by centre crop from the 3:2 master. They are shipped plates with
#: their own hash, but they are not generation attempts: `produces` on the master's accepted row
#: names them, and the judge refuses to count them as attempts.
DERIVED_COVERS = [
    {"path": "cover/japanese-4x5-640x800.png", "master": "cover/japanese-3x2-1200x800.png",
     "crop": "raw 2688x1536 centre crop 1229x1536, resized to 640x800",
     "id": "japanese-cover-4x5", "course_key": "japanese",
     "vision": {"reviewed_on": "2026-11-11",
                "checks": "portrait crop holds the counter, shelves, lamps and stools",
                "residual": "centre crop, not a separately composed portrait plate"}},
    {"path": "cover/parent-4x5-640x800.png", "master": "cover/parent-3x2-1200x800.png",
     "crop": "raw 2688x1536 centre crop 1229x1536, resized to 640x800",
     "id": "parent-cover-4x5", "course_key": "parent",
     "vision": {"reviewed_on": "2026-11-11",
                "checks": "portrait crop holds the worktop, shelf, bowls and jars",
                "residual": "centre crop, not a separately composed portrait plate"}},
    {"path": "cover/technical-4x5-640x800.png", "master": "cover/technical-3x2-1200x800.png",
     "crop": "raw 2688x1536 centre crop 1229x1536, resized to 640x800",
     "id": "technical-cover-4x5", "course_key": "technical",
     "vision": {"reviewed_on": "2026-11-11",
                "checks": "portrait crop holds the shelving, bench and blank open book",
                "residual": "centre crop, not a separately composed portrait plate"}},
]

#: Every generation attempt across both kits. Rejected bytes are deleted, never kept as a fallback
#: (ART-BIBLE §7.3); the record of what failed and why is what survives.
GENERATION_LOG = [
    # --- field_atlas@1: mechanically clean, rejected by the owner on art 2026-11-11 02:22 ---
    {"kit": 1, "asset": "hero/home-hero.png", "attempt": 1, "verdict": "rejected",
     "media_url": "https://v3b.fal.media/files/b/0ab204c7/ykzHm26ISFpnyJZWIbB1K_9zcNo3uk.png",
     "reason": "alarm clock face carried roman numerals and dial ticks — OCR-readable glyphs in art"},
    {"kit": 1, "asset": "hero/home-hero.png", "attempt": 2, "verdict": "accepted",
     "superseded_by": "field_atlas@2",
     "media_url": "https://v3b.fal.media/files/b/0ab204ca/E9XJ8ljMOyKzoG7oHhW3A_cy9P4jrv.png",
     "raw_sha256": "ae2b82660344f3886964dad22224066c7f32ac4cb44d8d675469f2d841b63184",
     "reason": "blank clock face, textless; still life on a bare-paper field, which the owner "
               "rejected as not a place — superseded by the v2 hero"},
    {"kit": 1, "asset": "cover/japanese-4x5-640x800.png", "attempt": 1, "verdict": "rejected",
     "media_url": "https://v3b.fal.media/files/b/0ab204cd/T4tbtW3sVtKA-wiG4IU6i_6glUVk30.png",
     "reason": "the noren was rendered as a pair of hanging trousers — garment for cloth"},
    {"kit": 1, "asset": "cover/japanese-3x2-1200x800.png", "attempt": 1, "verdict": "rejected",
     "media_url": "https://v3b.fal.media/files/b/0ab204d1/EbIDPahDt_XURxSj_4Trw_gKWNKGXD.png",
     "reason": "noren again rendered as trousers, and a bare paper margin on the right edge"},
    {"kit": 1, "asset": "cover/japanese-3x2-1200x800.png", "attempt": 2, "verdict": "accepted",
     "superseded_by": "field_atlas@2",
     "media_url": "https://v3b.fal.media/files/b/0ab204d3/XZ2dOsdjSZbICyBn-uRW6_6SYBc5pZ.png",
     "raw_sha256": "66a4adf8c40a58aa9f1bc6d06e38edd3c95852b9f616ebbb4b35940fa88cb619",
     "reason": "textless but a sparse vignette; rejected by the owner as below reference density"},
    {"kit": 1, "asset": "cover/parent-3x2-1200x800.png", "attempt": 1, "verdict": "rejected",
     "media_url": "https://v3b.fal.media/files/b/0ab204d6/yLkktUJfw2sd7mQ_djK57_zY7RljtD.png",
     "reason": "still life inset on bare paper with a margin on all four edges"},
    {"kit": 1, "asset": "cover/parent-3x2-1200x800.png", "attempt": 2, "verdict": "accepted",
     "superseded_by": "field_atlas@2",
     "media_url": "https://v3b.fal.media/files/b/0ab204d9/UD15ktRtoYsQbj4oiO2xQ_wIeWYaeD.png",
     "raw_sha256": "b0a266f58dbaeee395ca4f09d8c282e79955858bebfe09ff1a885ebdcf8d969a",
     "reason": "textless but a wall and a worktop with isolated props; superseded by the v2 kitchen"},
    {"kit": 1, "asset": "cover/technical-3x2-1200x800.png", "attempt": 1, "verdict": "accepted",
     "superseded_by": "field_atlas@2",
     "media_url": "https://v3b.fal.media/files/b/0ab204db/eXc-eWdp_m2UokBq5JvMN_Xu7IpWr4.png",
     "raw_sha256": "7101a70196261d115b7b0ebf1a7ce73b91a5428feaac93b7f9fb9651ad1572e6",
     "reason": "textless but a flat workbench with isolated props; superseded by the v2 workshop"},
    {"kit": 1, "asset": "lesson-scene/lesson-room.png", "attempt": 1, "verdict": "accepted",
     "superseded_by": "field_atlas@2",
     "media_url": "https://v3b.fal.media/files/b/0ab204de/i_9Ocq9X8ESG3LRanOPNF_0IpOiDU6.png",
     "raw_sha256": "775deb31e98f432cb6a5ac5d88087f0ca96762be493420587186cae46c767d81",
     "reason": "a flat wall with a shelf of bowls; superseded by the v2 cafe interior"},

    # --- field_atlas@2: reference-guided rebuild, owner-approved rework direction 02:22 ---
    {"kit": 2, "asset": "hero/home-hero.png", "attempt": 1, "verdict": "rejected",
     "media_url": "https://v3b.fal.media/files/b/0ab20536/5gimh2LPW3-l-o-ei52oW_wBdDTPC7.png",
     "reason": "painted lettering: a framed notice with pseudo-text on the wall, a pinned typed "
               "notice beside the door and an A-frame sign board — ART-BIBLE §9 rule 3"},
    {"kit": 2, "asset": "hero/home-hero.png", "attempt": 2, "verdict": "rejected",
     "media_url": "https://v3b.fal.media/files/b/0ab20545/kSjco0u1lLZciXPeZjL0T_1Wkv5W7Q.png",
     "reason": "a glyph drawn inside the gate plaque at the far end of the lane — a painted mark"},
    {"kit": 2, "asset": "hero/home-hero.png", "attempt": 3, "verdict": "accepted",
     "media_url": "https://v3b.fal.media/files/b/0ab2054a/D7WU66zYXDwxsxBnjHZfK_O5vPgeT6.png",
     "raw_sha256": "3e044e6c4d8dddf299b550fc2a59e680d1c0a62373c90019152d493fbdee4561",
     "produces": ["hero/home-hero.png"],
     "reason": "full-bleed street of paper lanterns with three depth planes, blank gate panel, "
               "no lettering anywhere by OCR or inspection"},
    {"kit": 2, "asset": "hero/home-hero.png", "attempt": 4, "verdict": "rejected",
     "media_url": "https://v3b.fal.media/files/b/0ab2054e/Bq61Y019G7XTY_wdQRyI0_M7d12Utx.png",
     "reason": "default tesseract reads '8 3 -' from the left window lattice (confidence 30–52). "
               "The marks are lattice bars, not lettering, but a plate that OCR reads cannot claim "
               "textless by OCR — rejected on the card's own rule, not on art"},
    {"kit": 2, "asset": "cover/japanese-3x2-1200x800.png", "attempt": 1, "verdict": "rejected",
     "media_url": "https://v3b.fal.media/files/b/0ab20565/ssEW2YqVpLIajvVQ9qLzR_34DDrbXV.png",
     "reason": "the outdoor lantern seen through the window carries a crest emblem — a painted "
               "mark on a lantern (ART-BIBLE §9 rule 3)"},
    {"kit": 2, "asset": "cover/japanese-3x2-1200x800.png", "attempt": 2, "verdict": "accepted",
     "media_url": "https://v3b.fal.media/files/b/0ab2056b/Tjjd2kvgpdg3JxBc26Vqf_l3GQ0GcB.png",
     "raw_sha256": "85da434da44a371549674d26baed4fb23b9c7c58b3bd8367651170aeeded68e3",
     "produces": ["cover/japanese-3x2-1200x800.png", "cover/japanese-4x5-640x800.png"],
     "reason": "dense cafe interior with counter, dresser, pendant lamps and a window onto a "
               "street; every lantern and label blank"},
    {"kit": 2, "asset": "cover/parent-3x2-1200x800.png", "attempt": 1, "verdict": "rejected",
     "media_url": "https://v3b.fal.media/files/b/0ab20572/HyLwCiFbc-4Iu0xgps0og_Eu8hXRq9.png",
     "reason": "neutral grey steel pans, kettle and tap (bible forbids grey) and a large bare "
               "wall area standing in for scene"},
    {"kit": 2, "asset": "cover/parent-3x2-1200x800.png", "attempt": 2, "verdict": "accepted",
     "media_url": "https://v3b.fal.media/files/b/0ab20576/9aj2USg72eT3UE2uxche9_VQsFOEBH.png",
     "raw_sha256": "262574d05835374f2d8cc2ea885ed8500ba6062ce188bd1907b689e0fd14061a",
     "produces": ["cover/parent-3x2-1200x800.png", "cover/parent-4x5-640x800.png"],
     "reason": "full kitchen with tiled splashback, copper pans, shelf, worktop and window; warm "
               "metal only, no measuring marks"},
    {"kit": 2, "asset": "cover/technical-3x2-1200x800.png", "attempt": 1, "verdict": "accepted",
     "media_url": "https://v3b.fal.media/files/b/0ab2057b/c1xQT3AdJoDre9qC9voMD_JQQWW1uV.png",
     "raw_sha256": "44c685643c76491856a993b6d2e10653c75f69454253e246b60526a9d6d6306b",
     "produces": ["cover/technical-3x2-1200x800.png", "cover/technical-4x5-640x800.png"],
     "reason": "workshop with shelving, pegboard, bench, blank open book and parcel; no diagrams "
               "or markings"},
    {"kit": 2, "asset": "lesson-scene/lesson-room.png", "attempt": 1, "verdict": "accepted",
     "media_url": "https://v3b.fal.media/files/b/0ab20584/5WFXXon7MCSJ4zr1_-K0b_OpkJCllG.png",
     "raw_sha256": "27874a4a756f51499d7c27099ef1ad67e8b4bb96ae20f08884200095397a9bcd",
     "produces": ["lesson-scene/lesson-room.png"],
     "reason": "full cafe study room: counter, dresser, three pendant lamps, chairs, window and "
               "noren doorway; calm painted wall band for lesson text"},
]

COVER_MAP = {"japanese": "japanese", "parent": "parent", "technical": "technical"}


# --------------------------------------------------------------------------------------
# facts about the bytes


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dims(path: Path) -> tuple[int, int]:
    out = subprocess.run(
        ["identify", "-format", "%w %h", str(path)], capture_output=True, text=True, check=True
    ).stdout.split()
    return int(out[0]), int(out[1])


def ocr_tokens(path: Path) -> dict:
    """Every token tesseract reads at its default page segmentation, with its confidence."""
    if not shutil.which("tesseract"):
        return {"raw": "<no tesseract>", "tokens": [], "max_conf": None, "readable": []}
    out = subprocess.run(
        ["tesseract", str(path), "stdout", "tsv"], capture_output=True, text=True
    ).stdout
    tokens = []
    for line in out.splitlines()[1:]:
        cols = line.split("\t")
        if len(cols) < 12:
            continue
        text, conf = cols[11].strip(), float(cols[10] or -1)
        if not text or conf <= 0:
            continue
        tokens.append({"text": text, "conf": round(conf, 2)})
    readable = []
    for t in tokens:
        alnum = "".join(ch for ch in t["text"] if ch.isalnum())
        if len(alnum) >= OCR_MIN_ALNUM and t["conf"] >= OCR_CONF_FLOOR:
            readable.append(t)
    raw = " ".join(t["text"] for t in tokens)
    return {
        "raw": raw,
        "max_conf": max([t["conf"] for t in tokens], default=0.0),
        "tokens": tokens,
        "readable": readable,
    }


def dominant(path: Path) -> tuple[str, tuple[int, int, int]]:
    out = subprocess.run(
        ["magick", str(path), "-resize", "10%", "-colors", "3", "-format", "%c", "histogram:info:"],
        capture_output=True, text=True, check=True,
    ).stdout
    rows = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append((int(line.split(":")[0]), line.split("#")[1].split()[0]))
    rows.sort(reverse=True)
    if not rows:
        return "#000000", (0, 0, 0)
    hexcode = rows[0][1]
    return f"#{hexcode}", (
        int(hexcode[0:2], 16), int(hexcode[2:4], 16), int(hexcode[4:6], 16)
    )


def rgb_bytes(path: Path, region=None, scale="25%") -> tuple[bytes, int, int]:
    cmd = ["magick", str(path)]
    if region:
        x, y, w, h = region
        cmd += ["-crop", f"{w}x{h}+{x}+{y}", "+repage"]
    cmd += ["-resize", scale, "-depth", "8", "rgb:-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    w, h = dims(path)
    if region:
        w, h = region[2], region[3]
    factor = float(scale.rstrip("%")) / 100.0
    return raw, max(1, int(w * factor)), max(1, int(h * factor))


def cool_share(path: Path, exclude=None) -> float:
    """Share of pixels whose blue channel exceeds both red and green by more than 10/255.

    `exclude` is a rectangle held out of the count: the one ratified indigo noren region
    (ART-BIBLE §9). Everything outside it must be warm.
    """
    raw, w, h = rgb_bytes(path)
    bounds = None
    if exclude:
        nw, nh = dims(path)
        bounds = (exclude["x"] * w / nw, exclude["y"] * h / nh,
                  exclude["w"] * w / nw, exclude["h"] * h / nh)
    cool = total = 0
    for idx in range(0, len(raw) - 2, 3):
        px = idx // 3
        if bounds:
            x, y = px % w, px // w
            ex, ey, ew, eh = bounds
            if ex <= x < ex + ew and ey <= y < ey + eh:
                continue
        total += 1
        if raw[idx + 2] - max(raw[idx], raw[idx + 1]) > 10:
            cool += 1
    return cool / total if total else 0.0


def gray_region(path: Path, region) -> bytes:
    x, y, w, h = region
    return subprocess.run(
        ["magick", str(path), "-crop", f"{w}x{h}+{x}+{y}", "+repage",
         "-colorspace", "Gray", "-depth", "8", "gray:-"],
        capture_output=True, check=True,
    ).stdout


def _lin(v: float) -> float:
    v = v / 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def luminance(rgb) -> float:
    r, g, b = (_lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a, b) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def field_stats(path: Path, region) -> dict:
    raw = gray_region(path, region)
    vals = sorted(raw)
    n = len(vals)
    if not n:
        return {}
    p5 = vals[max(0, int(n * 0.05) - 1)]
    p25 = vals[max(0, int(n * 0.25) - 1)]
    med = vals[n // 2]
    w = region[2]
    grad = 0.0
    count = 0
    for row in range(region[3]):
        base = row * w
        for col in range(1, w):
            grad += abs(raw[base + col] - raw[base + col - 1])
            count += 1
    energy = (grad / count / 255.0) if count else 0.0
    return {
        "percentile_5": p5,
        "percentile_25": p25,
        "median": med,
        "contrast_p5": round(contrast_ratio((p5, p5, p5), CONTRACT_INK), 2),
        "contrast_median": round(contrast_ratio((med, med, med), CONTRACT_INK), 2),
        "detail_energy": round(energy, 4),
    }


def black_minima(path: Path) -> float:
    return float(subprocess.run(
        ["magick", str(path), "-colorspace", "Gray", "-format", "%[fx:minima]", "info:"],
        capture_output=True, text=True, check=True,
    ).stdout)


def shelf_courses() -> list[dict]:
    """The real Home shelf: live courses in the seeded library, by title and pack."""
    if not SHELF_DB.exists():
        raise SystemExit(f"shelf db missing: {SHELF_DB}")
    con = sqlite3.connect(f"file:{SHELF_DB}?mode=ro", uri=True)
    rows = con.execute(
        "select c.id, c.title, coalesce(p.pack_id, c.pack_id, '') from courses c "
        "left join packs p on p.id = c.pack_id order by c.created_at"
    ).fetchall()
    con.close()
    return [{"id": r[0], "title": r[1], "pack_id": r[2]} for r in rows]


def cover_key(pack_slug: str) -> str | None:
    if "japanese" in pack_slug:
        return "japanese"
    if "parent" in pack_slug:
        return "parent"
    if "technical" in pack_slug:
        return "technical"
    return None


# --------------------------------------------------------------------------------------
# the manifest


def measured_block(full: Path, plate: dict) -> dict:
    dom_hex, dom_rgb = dominant(full)
    block = {
        "dominant": dom_hex,
        "cool_share": round(cool_share(full), 5),
        "black_minima": round(black_minima(full), 5),
    }
    if plate.get("noren"):
        block["cool_share_outside_noren"] = round(cool_share(full, plate["noren"]), 5)
        block["noren_region"] = plate["noren"]
    if plate.get("quiet_field"):
        qf = plate["quiet_field"]
        block["quiet_field"] = {"region": [qf["x"], qf["y"], qf["w"], qf["h"]],
                                **field_stats(full, (qf["x"], qf["y"], qf["w"], qf["h"]))}
    return block


def build_entry(plate: dict, courses: list[dict]) -> dict:
    rel = plate["path"]
    full = KIT_DIR / rel
    w, h = dims(full)
    row = {
        "id": plate["id"],
        "role": plate["role"],
        "path": rel,
        "size": [w, h],
        "sha256": sha256(full),
        "bytes": full.stat().st_size,
        "textless": True,
        "source": "curated_kit",
        "provenance": {
            "origin": "generated",
            "provider": "fal (host image_generate seam)",
            "model_id": "not reported by the seam",
            "generated_on": str(date.today()),
            "generation": "reference-guided: the reference image was passed in "
                          "reference_image_urls, with the host upscale pass on",
            "reference_image": plate["reference"],
            "media_url": plate["media_url"],
            "prompt": plate["prompt"],
            "prompt_sha256": hashlib.sha256(plate["prompt"].encode()).hexdigest(),
            "raw_path": f".vq-raw/field_atlas/v2/{plate['raw']}",
            "raw_sha256": sha256(RAW_DIR / plate["raw"]) if (RAW_DIR / plate["raw"]).exists() else None,
            "temper": TEMPER,
            "print_safety_lift": LIFT,
            "pipeline": PIPELINE,
            "derivation": plate["derivation"],
            "source_frame": plate["source"],
            "ocr": ocr_tokens(full),
            "measured": measured_block(full, plate),
            "vision": plate["vision"],
        },
    }
    if plate.get("course_key"):
        course = next((c for c in courses if cover_key(c["pack_id"]) == plate["course_key"]), None)
        if course:
            row["course"] = {"title": course["title"], "course_id": course["id"]}
    return row


def build_derived(d: dict, master_row: dict, courses: list[dict]) -> dict:
    full = KIT_DIR / d["path"]
    w, h = dims(full)
    mprov = master_row["provenance"]
    course = next((c for c in courses if cover_key(c["pack_id"]) == d["course_key"]), None)
    return {
        "id": d["id"],
        "role": "cover",
        "path": d["path"],
        "size": [w, h],
        "sha256": sha256(full),
        "bytes": full.stat().st_size,
        "textless": True,
        "source": "curated_kit",
        "course": {"title": course["title"], "course_id": course["id"]} if course else None,
        "provenance": {
            "origin": "derived",
            "derived_from": d["master"],
            "master_media_url": mprov["media_url"],
            "master_raw_sha256": mprov["raw_sha256"],
            "derivation": d["crop"],
            "temper": TEMPER,
            "print_safety_lift": LIFT,
            "pipeline": PIPELINE,
            "ocr": ocr_tokens(full),
            "measured": measured_block(full, d),
            "vision": d["vision"],
            "note": "a 4:5 centre crop of the accepted 3:2 master, not a separately composed "
                    "portrait plate and not a generation attempt",
        },
    }


def build() -> dict:
    courses = shelf_courses()
    roles: dict[str, list] = {
        "hero": [], "cover": [], "section": [], "lesson_scene": [],
        "collectible": [], "object": [], "fox": [],
    }
    master_rows = {}
    for plate in PLATES:
        row = build_entry(plate, courses)
        roles[plate["role"]].append(row)
        master_rows[plate["path"]] = row
    for d in DERIVED_COVERS:
        roles["cover"].append(build_derived(d, master_rows[d["master"]], courses))

    for obj in ("clock", "medallion-rim", "passport-tray", "shelf-plank", "stamp-rim", "tag", "ticket"):
        src = ROOT / "assets" / "art" / "objects" / f"{obj}.png"
        full = KIT_DIR / "objects" / f"{obj}.png"
        roles["object"].append({
            "id": obj, "role": "object", "path": f"objects/{obj}.png",
            "size": list(dims(full)), "sha256": sha256(full), "bytes": full.stat().st_size,
            "textless": True, "source": "curated_kit",
            "provenance": {"origin": "carried", "source_path": str(src.relative_to(ROOT)),
                           "source_sha256": sha256(src), "approved_by": "CP-013 (object kit)"},
        })
    for pose in ("cheer", "clock", "point", "read", "sleep", "think", "wave"):
        src = ROOT / "assets" / "art" / "fox" / f"fox-{pose}-256.png"
        full = KIT_DIR / "fox" / f"fox-{pose}-256.png"
        roles["fox"].append({
            "id": f"fox-{pose}", "role": "fox", "path": f"fox/fox-{pose}-256.png",
            "size": list(dims(full)), "sha256": sha256(full), "bytes": full.stat().st_size,
            "textless": True, "source": "curated_kit",
            "provenance": {"origin": "carried", "source_path": str(src.relative_to(ROOT)),
                           "source_sha256": sha256(src), "approved_by": "CP-010 (fox)"},
        })
    src = ROOT / "assets" / "art" / "fox" / "fox-model-sheet-512.png"
    full = KIT_DIR / "fox" / "fox-model-sheet-512.png"
    roles["fox"].append({
        "id": "fox-model-sheet", "role": "fox", "path": "fox/fox-model-sheet-512.png",
        "size": list(dims(full)), "sha256": sha256(full), "bytes": full.stat().st_size,
        "textless": True, "source": "curated_kit",
        "provenance": {"origin": "carried", "source_path": str(src.relative_to(ROOT)),
                       "source_sha256": sha256(src), "approved_by": "CP-010 (fox)"},
    })

    resolution: dict = {"cover": {
        "4x5": {"size": [640, 800], "rendered": [320, 400], "scale": 2.0},
        "3x2": {"size": [1200, 800], "rendered": [600, 400], "scale": 2.0,
                "natural": {"size": [2304, 1536], "scale_vs_plate": 1.92,
                            "scale_vs_render": 3.84}},
    }}
    for plate in PLATES:
        if plate["role"] in ("hero", "lesson_scene"):
            src = plate["source"]
            full = KIT_DIR / src["path"]
            key = "hero" if plate["role"] == "hero" else "lesson_scene"
            resolution[key] = {
                "size": list(dims(KIT_DIR / plate["path"])),
                "source": {
                    "path": src["path"],
                    "size": list(dims(full)),
                    "sha256": sha256(full),
                    "scale": src["scale"],
                    "method": "provider return at 2688x1536 (host upscale pass on), kept un-resized",
                    "note": src["note"],
                },
            }

    return {
        "grammar": GRAMMAR,
        "kit_id": f"{GRAMMAR}@{VERSION}",
        "label": "Field atlas",
        "version": VERSION,
        "status": "owner_rework_of_rejected_v1",
        "art_bible": ART_BIBLE,
        "lane": "display_plate",
        "palette": PALETTE,
        "medium": MEDIUM,
        "composition": COMPOSITION,
        "supersedes": {
            "kit_id": "field_atlas@1",
            "status": "rejected_by_owner",
            "rejected_on": "2026-11-11",
            "reason": "contact sheet v1 judged below reference quality: still life hero on bare "
                      "paper, sparse vignette covers, flat lesson wall",
            "evidence_dir": "rejected-v1/",
            "consumer_note": "v1 is evidence only; no downstream card may read it as a fallback",
        },
        "source_library": {
            "db": str(SHELF_DB),
            "read_on": str(date.today()),
            "courses": [
                {"course_id": c["id"], "title": c["title"], "pack_id": c["pack_id"]}
                for c in courses
            ],
        },
        "roles": roles,
        "fallbacks": FALLBACKS,
        "specimens": {
            "contact_sheet": {
                "path": "specimens/contact-sheet.png",
                "size": list(dims(KIT_DIR / "specimens" / "contact-sheet.png")),
                "sha256": sha256(KIT_DIR / "specimens" / "contact-sheet.png"),
                "bytes": (KIT_DIR / "specimens" / "contact-sheet.png").stat().st_size,
                "note": "rebuilt by scripts/vq002-contact-sheet.sh; shows hero, both cover aspects "
                        "for every real Home course, fox, objects, lesson scene, and the "
                        "side-by-side against refs/home.png and refs/classroom.png",
            }
        },
        "resolution": resolution,
        "reference": {
            "path": "docs/concept-parity/refs/home.png",
            "sha256": sha256(REFS_HOME),
            "classroom": {"path": "docs/concept-parity/refs/classroom.png",
                          "sha256": sha256(REFS_CLASSROOM)},
            "note": "the two reference mockups the plates were generated against and the contact "
                    "sheet is compared with; mockups, not a source of course titles",
        },
        "ocr_policy": {
            "tool": "tesseract default page segmentation on the shipped plate",
            "fail_rule": f"a token of >= {OCR_MIN_ALNUM} alphanumeric characters at confidence "
                         f">= {OCR_CONF_FLOOR}",
            "calibration": "real UI strings on refs/home.png and refs/classroom.png score 74-95; "
                           "painted line art on these plates scores 12-52",
            "limitation": "painted pseudo-lettering is not readable enough for OCR to score; it "
                          "is caught by the recorded vision pass on each plate instead",
            "calibrated_on": [str(REFS_HOME.relative_to(ROOT)),
                              str(REFS_CLASSROOM.relative_to(ROOT))],
        },
        "generation_log": GENERATION_LOG,
        "generation_budget": {
            "attempts_allowed": ATTEMPTS_ALLOWED,
            "per_asset_max": PER_ASSET_MAX,
            "additional_allowed_this_round": ADDITIONAL_ALLOWED,
            "attempts_used": len(GENERATION_LOG),
            "accepted": sum(1 for r in GENERATION_LOG if r["verdict"] == "accepted"),
            "rejected": sum(1 for r in GENERATION_LOG if r["verdict"] == "rejected"),
        },
    }


# --------------------------------------------------------------------------------------
# the judge

REQUIRED_TOP = (
    "grammar", "kit_id", "version", "art_bible", "palette", "medium", "composition",
    "roles", "fallbacks", "specimens", "generation_budget", "supersedes",
)
REQUIRED_ROLE = ("id", "role", "path", "size", "sha256", "bytes", "source", "provenance")
ROLE_NAMES = ("hero", "cover", "section", "lesson_scene", "collectible", "object", "fox")


def check() -> int:
    problems: list[str] = []

    if not KIT_JSON.exists():
        print(f"FAIL missing {KIT_JSON}")
        return 2
    kit = json.loads(KIT_JSON.read_text())

    for key in REQUIRED_TOP:
        if key not in kit:
            problems.append(f"missing top-level key {key!r}")
    if kit.get("grammar") != GRAMMAR:
        problems.append(f"grammar is {kit.get('grammar')!r}, expected {GRAMMAR!r}")
    if kit.get("kit_id") != f"{GRAMMAR}@{kit.get('version')}":
        problems.append("kit_id is not <grammar>@<version>")
    if kit.get("version") != VERSION:
        problems.append(f"version is {kit.get('version')!r}, expected {VERSION}")
    if kit.get("art_bible") != ART_BIBLE:
        problems.append("art_bible does not point at the frozen art bible")
    if not (ROOT / str(kit.get("art_bible"))).exists():
        problems.append("art_bible path does not exist")

    # v1 is rejected evidence: the manifest must say so, and must not be readable as a fallback
    sup = kit.get("supersedes") or {}
    if sup.get("kit_id") != "field_atlas@1" or sup.get("status") != "rejected_by_owner":
        problems.append("supersedes does not record v1 as rejected evidence")
    if not (KIT_DIR / str(sup.get("evidence_dir", ""))).exists():
        problems.append("supersedes.evidence_dir does not exist")

    roles = kit.get("roles") or {}
    for name in ROLE_NAMES:
        if name not in roles:
            problems.append(f"roles.{name} missing")

    # the hero is exactly 1344x768 and has a real 2x source beside it
    hero = roles.get("hero") or []
    if len(hero) != 1:
        problems.append(f"expected exactly one hero, found {len(hero)}")
    else:
        if hero[0].get("size") != [1344, 768]:
            problems.append(f"hero size is {hero[0].get('size')}, expected [1344, 768]")
        src = (kit.get("resolution") or {}).get("hero", {}).get("source") or {}
        src_path = KIT_DIR / str(src.get("path", ""))
        if not src.get("path") or not src_path.exists():
            problems.append("hero has no 2x source file recorded in resolution")
        else:
            if list(dims(src_path)) != [2688, 1536]:
                problems.append(f"hero 2x source is {dims(src_path)}, expected [2688, 1536]")
            if sha256(src_path) != src.get("sha256"):
                problems.append("hero 2x source sha256 does not match resolution")

    # covers: both aspects for every real shelf course, at 2x of the rendered size
    courses = shelf_courses()
    covers = roles.get("cover") or []
    manifest_text = KIT_JSON.read_text()
    rendered = {"4x5": (320, 400), "3x2": (600, 400)}
    for course in courses:
        matched = [c for c in covers if (c.get("course") or {}).get("course_id") == course["id"]]
        aspects = {tuple(c.get("size")) for c in matched}
        if aspects != {(640, 800), (1200, 800)}:
            problems.append(
                f"course {course['title']!r} has cover sizes {sorted(aspects)}, expected 4:5 and 3:2"
            )
        if course["title"] not in manifest_text:
            problems.append(f"course {course['title']!r} is on the shelf but not named in kit.json")
    for c in covers:
        size = tuple(c.get("size") or ())
        if size == (640, 800) and size != tuple(2 * v for v in rendered["4x5"]):
            problems.append(f"{c['path']} is not 2x its 320x400 render")
        if size == (1200, 800) and size != tuple(2 * v for v in rendered["3x2"]):
            problems.append(f"{c['path']} is not 2x its 600x400 render")

    # the 3:2 source frame must state the right referent, recomputed from the recorded numbers
    want_ratios = {
        "shipped_vs_render": round(COVER_3X2_SHIPPED[0] / COVER_3X2_RENDERED[0], 2),
        "natural_vs_shipped": round(COVER_3X2_NATURAL[0] / COVER_3X2_SHIPPED[0], 2),
        "natural_vs_render": round(COVER_3X2_NATURAL[0] / COVER_3X2_RENDERED[0], 2),
    }
    for c in covers:
        if tuple(c.get("size") or ()) != COVER_3X2_SHIPPED:
            continue
        sf = (c.get("provenance") or {}).get("source_frame") or {}
        if tuple(sf.get("size") or ()) != COVER_3X2_NATURAL:
            problems.append(
                f"{c['path']} natural source frame is {sf.get('size')!r}, "
                f"expected {list(COVER_3X2_NATURAL)}"
            )
            continue
        if sf.get("ratios") != want_ratios:
            problems.append(
                f"{c['path']} source_frame ratios are {sf.get('ratios')!r}, expected {want_ratios}"
            )
        if sf.get("scale") != want_ratios["shipped_vs_render"]:
            problems.append(
                f"{c['path']} source_frame scale is {sf.get('scale')!r}; it must state the "
                f"shipped-plate-to-render ratio {want_ratios['shipped_vs_render']}"
            )
        note = sf.get("note") or ""
        for wrong in WRONG_3X2_NOTES:
            if wrong in note:
                problems.append(
                    f"{c['path']} source_frame note repeats the wrong referent {wrong!r}"
                )

    res32 = (((kit.get("resolution") or {}).get("cover") or {}).get("3x2") or {})
    if (res32.get("size") != list(COVER_3X2_SHIPPED)
            or res32.get("rendered") != list(COVER_3X2_RENDERED)
            or res32.get("scale") != want_ratios["shipped_vs_render"]):
        problems.append(
            "resolution.cover.3x2 must state the shipped 1200x800 plate at 2x the 600x400 render"
        )
    nat = res32.get("natural") or {}
    if (nat.get("size") != list(COVER_3X2_NATURAL)
            or nat.get("scale_vs_plate") != want_ratios["natural_vs_shipped"]
            or nat.get("scale_vs_render") != want_ratios["natural_vs_render"]):
        problems.append(
            "resolution.cover.3x2.natural must state the 2304x1536 crop at 1.92x the plate and "
            "3.84x the render"
        )
    for title in FICTIONAL_TITLES:
        if title in manifest_text:
            problems.append(f"fictional proof title {title!r} appears in kit.json")

    # every row: file exists, hash and size match, role declared, plate is textless
    checked = 0
    for role_name, rows in roles.items():
        for row in rows:
            for key in REQUIRED_ROLE:
                if key not in row:
                    problems.append(f"{role_name}/{row.get('id')} missing {key!r}")
                    break
            else:
                if row["role"] != role_name:
                    problems.append(f"{role_name}/{row['id']} declares role {row['role']!r}")
                full = KIT_DIR / row["path"]
                if not full.exists():
                    problems.append(f"{row['path']} missing on disk")
                    continue
                if sha256(full) != row["sha256"]:
                    problems.append(f"{row['path']} sha256 does not match the manifest")
                if list(dims(full)) != list(row["size"]):
                    problems.append(f"{row['path']} is {dims(full)}, manifest says {row['size']}")
                if full.stat().st_size != row["bytes"]:
                    problems.append(f"{row['path']} byte count does not match the manifest")
                checked += 1

    # textless: recompute OCR and compare with the recorded tokens. A plate that yields readable
    # text fails; the recorded token list must also be the token list the bytes produce now.
    for role_name, rows in roles.items():
        for row in rows:
            prov = row.get("provenance") or {}
            if prov.get("origin") not in ("generated", "derived"):
                continue
            full = KIT_DIR / row["path"]
            if not full.exists():
                continue
            live = ocr_tokens(full)
            recorded = prov.get("ocr") or {}
            if recorded.get("raw") != live["raw"]:
                problems.append(f"{row['path']} recorded OCR text does not reproduce")
            if live["readable"]:
                problems.append(
                    f"{row['path']} is not textless: OCR read "
                    f"{[t['text'] for t in live['readable']]}"
                )

    # provenance is recorded, never inferred
    for role_name, rows in roles.items():
        for row in rows:
            prov = row.get("provenance") or {}
            origin = prov.get("origin")
            if origin == "generated":
                for key in ("provider", "generated_on", "prompt", "prompt_sha256", "media_url",
                            "pipeline", "ocr", "vision", "measured"):
                    if not prov.get(key):
                        problems.append(f"{row['path']} generated but provenance.{key} is empty")
                if prov.get("prompt") and hashlib.sha256(
                    prov["prompt"].encode()
                ).hexdigest() != prov.get("prompt_sha256"):
                    problems.append(f"{row['path']} prompt_sha256 does not match the prompt text")
            elif origin == "derived":
                for key in ("derived_from", "master_media_url", "master_raw_sha256", "ocr",
                            "vision"):
                    if not prov.get(key):
                        problems.append(f"{row['path']} derived but provenance.{key} is empty")
            elif origin == "carried":
                src = ROOT / str(prov.get("source_path", ""))
                if not src.exists():
                    problems.append(f"{row['path']} carried from a missing source")
                elif sha256(src) != prov.get("source_sha256"):
                    problems.append(f"{row['path']} carried source hash does not match")
            else:
                problems.append(f"{row['path']} has no provenance origin")

    # palette family: no pure black, warm outside the one ratified indigo cloth, and a measured
    # quiet field on the hero that clears 4.5:1 against the contract ink at its median
    for role_name, rows in roles.items():
        for row in rows:
            prov = row.get("provenance") or {}
            if prov.get("origin") not in ("generated", "derived"):
                continue
            full = KIT_DIR / row["path"]
            if not full.exists():
                continue
            m = prov.get("measured") or {}
            if m.get("black_minima") is not None and m["black_minima"] <= 2 / 255:
                problems.append(f"{row['path']} contains a pure black pixel")
            if m.get("cool_share_outside_noren") is not None:
                if m["cool_share_outside_noren"] > 0.005:
                    problems.append(
                        f"{row['path']} has {m['cool_share_outside_noren']:.3%} cool pixels "
                        "outside the declared noren region (limit 0.5%)"
                    )
            elif m.get("cool_share") is not None and m["cool_share"] > 0.005:
                problems.append(
                    f"{row['path']} has {m['cool_share']:.3%} cool pixels and declares no noren "
                    "region (limit 0.5%)"
                )
            if row["role"] == "hero":
                qf = m.get("quiet_field") or {}
                if qf.get("contrast_median", 0) < 4.5:
                    problems.append(
                        f"hero quiet field median contrast is {qf.get('contrast_median')}:1, "
                        "below the contract 4.5:1"
                    )

    # 2x source for the lesson scene, recorded the same way as the hero
    ls = (kit.get("resolution") or {}).get("lesson_scene") or {}
    lsrc = ls.get("source") or {}
    if not lsrc.get("path") or not (KIT_DIR / str(lsrc.get("path"))).exists():
        problems.append("lesson scene has no 2x source file recorded in resolution")
    elif list(dims(KIT_DIR / lsrc["path"])) != [2688, 1536]:
        problems.append("lesson scene 2x source is not 2688x1536")

    sheet = (kit.get("specimens") or {}).get("contact_sheet")
    if isinstance(sheet, str):
        sheet = {"path": sheet}
    sheet_path = KIT_DIR / str((sheet or {}).get("path", ""))
    if not sheet or not sheet_path.exists():
        problems.append("contact sheet missing")
    else:
        if sha256(sheet_path) != sheet.get("sha256"):
            problems.append("contact sheet sha256 does not match the manifest")
        if list(dims(sheet_path)) != list(sheet.get("size") or []):
            problems.append(
                f"contact sheet is {dims(sheet_path)}, manifest says {sheet.get('size')}"
            )

    # budget: the ceiling comes from the manifest, the per-asset cap from this round, and derived
    # plates are never counted as attempts because they have no row of their own
    budget = kit.get("generation_budget") or {}
    log = kit.get("generation_log") or []
    allowed = budget.get("attempts_allowed")
    per_asset = budget.get("per_asset_max")
    if not isinstance(allowed, int) or allowed != ATTEMPTS_ALLOWED:
        problems.append(f"generation_budget.attempts_allowed is {allowed!r}, expected {ATTEMPTS_ALLOWED}")
    if per_asset != PER_ASSET_MAX:
        problems.append(f"generation_budget.per_asset_max is {per_asset!r}, expected {PER_ASSET_MAX}")
    if budget.get("attempts_used") != len(log):
        problems.append("generation_budget.attempts_used does not match the log")
    if len(log) > ATTEMPTS_ALLOWED:
        problems.append(f"generation log records {len(log)} attempts, over the budget of {ATTEMPTS_ALLOWED}")
    if budget.get("accepted") != sum(1 for r in log if r.get("verdict") == "accepted"):
        problems.append("generation_budget.accepted does not match the log")
    if budget.get("rejected") != sum(1 for r in log if r.get("verdict") == "rejected"):
        problems.append("generation_budget.rejected does not match the log")
    per_asset_counts: dict[tuple, int] = {}
    for row in log:
        asset = row.get("asset")
        if row.get("verdict") not in ("accepted", "rejected"):
            problems.append(f"log entry for {asset!r} has verdict {row.get('verdict')!r}")
        if not row.get("media_url") or not row.get("reason"):
            problems.append(f"log entry for {asset!r} lacks a media url or a reason")
        per_asset_counts[(row.get("kit"), asset)] = per_asset_counts.get((row.get("kit"), asset), 0) + 1
    for (kit_no, asset), count in per_asset_counts.items():
        if kit_no == VERSION and count > PER_ASSET_MAX:
            problems.append(f"{asset!r} has {count} attempts in kit {kit_no}, over the cap of {PER_ASSET_MAX}")

    # accepted rows of this kit: every produced path ships, and every generated or derived plate
    # traces to exactly one accepted row on media_url + raw_sha256 + produces membership
    shipped_paths = {r["path"] for rows in roles.values() for r in rows}
    shipped_rows = {r["path"]: r for rows in roles.values() for r in rows}
    accepted = [r for r in log if r.get("verdict") == "accepted" and r.get("kit") == VERSION]
    for r in accepted:
        produces = r.get("produces") or []
        if not produces:
            problems.append(f"accepted log row for {r.get('asset')!r} lists no produced asset")
        for path in produces:
            if path not in shipped_paths:
                problems.append(f"accepted log row produces {path!r}, which is not shipped")

    for row in shipped_rows.values():
        prov = row.get("provenance") or {}
        if prov.get("origin") == "generated":
            traces = [
                r for r in accepted
                if r.get("media_url") == prov.get("media_url")
                and r.get("raw_sha256") == prov.get("raw_sha256")
                and row["path"] in (r.get("produces") or [])
            ]
            if len(traces) != 1:
                problems.append(
                    f"{row['path']} traces to {len(traces)} accepted generation rows, expected 1"
                )
        elif prov.get("origin") == "derived":
            master = shipped_rows.get(prov.get("derived_from"))
            if not master:
                problems.append(f"{row['path']} derives from a plate that is not shipped")
                continue
            mprov = master.get("provenance") or {}
            traces = [
                r for r in accepted
                if r.get("media_url") == mprov.get("media_url")
                and r.get("raw_sha256") == mprov.get("raw_sha256")
                and row["path"] in (r.get("produces") or [])
            ]
            if len(traces) != 1:
                problems.append(
                    f"{row['path']} traces to {len(traces)} accepted generation rows, expected 1"
                )

    # a superseded accepted row keeps its evidence (media url, raw hash, reason) but must not claim
    # a path that is shipped today: two accepted rows naming one shipped plate is the round-3 defect
    for r in log:
        if r.get("verdict") != "accepted" or r.get("kit") == VERSION:
            continue
        if not r.get("superseded_by"):
            problems.append(
                f"superseded accepted row for {r.get('asset')!r} does not name superseded_by"
            )
        if not r.get("raw_sha256"):
            problems.append(
                f"superseded accepted row for {r.get('asset')!r} dropped the raw_sha256 it consumed"
            )
        claimed = [p for p in (r.get("produces") or []) if p in shipped_paths]
        if claimed:
            problems.append(
                f"superseded kit-{r.get('kit')} accepted row for {r.get('asset')!r} still claims "
                f"shipped path(s) {claimed}"
            )

    # v1 art is not in the consumer path: no shipped plate carries a superseded media url
    superseded_urls = {
        r["media_url"] for r in log
        if r.get("kit") != VERSION and r.get("verdict") == "accepted"
    }
    for row in shipped_rows.values():
        prov = row.get("provenance") or {}
        for url in (prov.get("media_url"), prov.get("master_media_url")):
            if url and url in superseded_urls:
                problems.append(f"{row['path']} still consumes superseded v1 art")

    # fallbacks are a contract for the consuming screen, not decoration
    fallbacks = kit.get("fallbacks") or {}
    for name in ("cover", "hero", "lesson_scene", "object", "fox"):
        if name not in fallbacks:
            problems.append(f"fallbacks.{name} missing")
    for name, chain in fallbacks.items():
        if name not in ROLE_NAMES:
            problems.append(f"fallbacks.{name} is not a declared role")
        if not isinstance(chain, list):
            problems.append(f"fallbacks.{name} is not a list")
            continue
        for step in chain:
            low = str(step).lower().replace("_", "-")
            if low in FORBIDDEN_FALLBACKS or "pack" in low or "press" in low:
                problems.append(
                    f"fallbacks.{name} names {step!r}: a Press Plate pack cover may never be a "
                    "display-cover fallback"
                )
            elif step not in ALLOWED_FALLBACKS:
                problems.append(f"fallbacks.{name} names {step!r}, not a known chain step")
    cover_chain = fallbacks.get("cover") or []
    if not cover_chain or cover_chain[0] != "course-master":
        problems.append(
            f"fallbacks.cover leads with {cover_chain[0] if cover_chain else None!r}; it must "
            "lead with 'course-master'"
        )

    # the references the plates were generated against and compared with are pinned
    ref = kit.get("reference") or {}
    for key, expected in (("", REFS_HOME), ("classroom", REFS_CLASSROOM)):
        block = ref if not key else (ref.get(key) or {})
        path = block.get("path")
        if not path or not (ROOT / path).exists():
            problems.append(f"reference {key or 'home'} is missing")
            continue
        if sha256(ROOT / path) != block.get("sha256"):
            problems.append(f"reference {path} does not match the pinned sha256")

    print(f"kit: {kit.get('kit_id')}  assets checked: {checked}  shelf courses: {len(courses)}")
    if problems:
        for p in problems:
            print(f"FAIL {p}")
        print(f"{len(problems)} problem(s)")
        return 1
    print("OK all claims in kit.json reproduce")
    return 0


def calibrate() -> int:
    """Prove the textless rule on the two reference mockups, which carry real UI text."""
    failures = []
    for path in (REFS_HOME, REFS_CLASSROOM):
        found = ocr_tokens(path)["readable"]
        if not found:
            failures.append(f"{path.relative_to(ROOT)}: detector found no readable text")
        else:
            words = ", ".join(f"{t['text']}@{t['conf']}" for t in found[:5])
            print(f"detector flags {path.relative_to(ROOT)}: {words}")
    for role, rows in (json.loads(KIT_JSON.read_text()).get("roles") or {}).items():
        for row in rows:
            prov = row.get("provenance") or {}
            if prov.get("origin") not in ("generated", "derived"):
                continue
            found = ocr_tokens(KIT_DIR / row["path"])["readable"]
            if found:
                failures.append(f"{row['path']}: detector flags {[t['text'] for t in found]}")
    if failures:
        for f in failures:
            print(f"FAIL {f}")
        return 1
    print("calibrated: the rule catches real text and passes every painted plate")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--calibrate", action="store_true")
    args = ap.parse_args()
    if args.write:
        kit = build()
        KIT_JSON.write_text(json.dumps(kit, indent=2) + "\n")
        print(f"wrote {KIT_JSON}")
    if args.calibrate:
        return calibrate()
    if args.check or not args.write:
        return check()
    return 0


if __name__ == "__main__":
    sys.exit(main())
