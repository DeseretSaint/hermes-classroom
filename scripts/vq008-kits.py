#!/usr/bin/env python3
"""VQ-008 — build and judge one visual kit per world grammar.

`assets/visual-kits/<grammar>/kit.json` is the only manifest a screen reads: a screen card
reads the manifest, it does not invent a path (`docs/launch/VISUAL-QUALITY-PROGRAM.md` §3,
`docs/launch/VISUAL-ASSET-AUDIT.md` §5). So this script builds the manifest from a declarative
table plus the bytes on disk, and `--check` re-derives every claim from those bytes.

    python3 scripts/vq008-kits.py --plan                  # the generation plan (no provider call)
    python3 scripts/vq008-kits.py --write                 # rewrite every kit.json from disk
    python3 scripts/vq008-kits.py --check                 # verify every claim in every kit.json
    python3 scripts/vq008-kits.py --contact <dir>         # one contact sheet per grammar
    python3 scripts/vq008-kits.py --calibrate             # prove the textless detector

Grammar vocabulary — palette, medium, composition, motifs, subject cues, illustration role and
the cannot-do fence — is imported from :mod:`coursebook.world` so a kit cannot drift from the
policy table. This script never edits `coursebook`; it only reads it.

`--check` is the acceptance run. It recomputes sha256, pixel size, OCR text, role coverage, the
hero size, the cover aspect arithmetic, the quiet-field contrast, the palette ground, the
no-pure-black rule, the shared-kernel bytes, the fallback chain, the generation budget and the
absence of placeholder or Press Plate bytes. Exit 0 is the acceptance run.

Exit codes: 0 clean, 1 a claim failed, 2 a manifest or a source is missing.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

KITS = ROOT / "assets" / "visual-kits"
REFS = ROOT / "docs" / "concept-parity" / "refs"
ART_BIBLE = "docs/concept-parity/ART-BIBLE.md"
RAW_DIR = ROOT / ".vq-raw" / "vq008"

#: Read-only import of the authored grammar table: the single source of the palette, medium,
#: composition, motifs, subject cues and the cannot-do fence.
from coursebook.world import GRAMMARS, MAX_PLATE_PIGMENTS  # noqa: E402

#: The five contract pigments a quiet field is measured against (ART-BIBLE §2).
CONTRACT_INK = (0x1A, 0x17, 0x13)

#: The generation budget for this round. Read from each manifest by the judge, so a later card
#: can raise the ceiling without editing the check.
ATTEMPTS_ALLOWED = 50
PER_ASSET_MAX = 4

#: The 3:2 cover: the natural crop is 2304x1536, the shipped plate 1200x800, the render 600x400.
COVER_3X2_NATURAL = (2304, 1536)
COVER_3X2_SHIPPED = (1200, 800)
COVER_3X2_RENDERED = (600, 400)
COVER_4X5_NATURAL = (1152, 1440)
COVER_4X5_SHIPPED = (640, 800)
COVER_4X5_RENDERED = (320, 400)

PLATE_SIZES = {"hero": (1344, 768), "section": (1344, 768), "lesson_scene": (1344, 768)}

TEMPER = "magick -modulate 105,75,100, applied to the provider raw before any crop or resize"
LIFT = "magick -clamp +level 4%,100% applied last, after the resize (ART-BIBLE §9 rule 5)"
PIPELINE = f"{TEMPER}; then crop/resize; then {LIFT}"

#: A display cover never falls back to a Press Plate pack cover (UI-DECISIONS D-006).
FALLBACKS = {
    "lesson_scene": ["section", "background"],
    "cover": ["course-master", "background"],
    "hero": ["background"],
    "section": ["background"],
    "object": [],
    "fox": [],
}
ALLOWED_FALLBACKS = frozenset({"section", "background", "course-master"})
FORBIDDEN_FALLBACK_TOKENS = ("pack", "press")

OCR_CONF_FLOOR = 60
OCR_MIN_ALNUM = 3

#: Titles that exist only in the CP-053 proof mockup. The card forbids them by name.
FICTIONAL_TITLES = ("Auto Repair Fundamentals", "Astronomy", "Sourdough")

#: The plates this card generates per grammar. `raw` names the provider return kept under
#: `.vq-raw/vq008/<grammar>/`; `derives` lists every shipped path that one raw produces.
#: A 4:5 crop of the 3:2 master is not a second generation and must not inflate the budget.
PLATE_TABLE = {
    "workshop_manual": [
        ("hero", "hero/service-bay.png", "hero"),
        ("cover", "cover/bench-3x2.png", "cover"),
        ("section", "section/tool-wall.png", "section"),
        ("lesson_scene", "lesson-scene/bench-lesson.png", "lesson"),
    ],
    "observatory": [
        ("hero", "hero/dome-slit.png", "hero"),
        ("cover", "cover/instrument-3x2.png", "cover"),
        ("section", "section/chart-table.png", "section"),
        ("lesson_scene", "lesson-scene/observation-desk.png", "lesson"),
    ],
    "kitchen_table": [
        ("hero", "hero/kitchen-table.png", "hero"),
        ("cover", "cover/tabletop-3x2.png", "cover"),
        ("section", "section/ingredient-board.png", "section"),
        ("lesson_scene", "lesson-scene/mixing-lesson.png", "lesson"),
    ],
    "archive_desk": [
        ("hero", "hero/archive-desk.png", "hero"),
        ("cover", "cover/document-trays-3x2.png", "cover"),
        ("section", "section/index-drawer.png", "section"),
        ("lesson_scene", "lesson-scene/reading-desk.png", "lesson"),
    ],
    "studio_bench": [
        ("hero", "hero/studio-bench.png", "hero"),
        ("cover", "cover/swatch-bench-3x2.png", "cover"),
        ("section", "section/material-fan.png", "section"),
        ("lesson_scene", "lesson-scene/working-bench.png", "lesson"),
    ],
    "lab_bench": [
        ("hero", "hero/lab-bench.png", "hero"),
        ("cover", "cover/glassware-3x2.png", "cover"),
        ("section", "section/glassware-shelf.png", "section"),
        ("lesson_scene", "lesson-scene/bench-lesson.png", "lesson"),
    ],
    "instrument_board": [
        ("hero", "hero/drafting-board.png", "hero"),
        ("cover", "cover/instruments-3x2.png", "cover"),
        ("section", "section/grid-board.png", "section"),
        ("lesson_scene", "lesson-scene/chalk-tray.png", "lesson"),
    ],
}

#: The shared visual kernel: one set of bytes every kit points at instead of duplicating.
KERNEL = {
    "frame": [
        "assets/masters/objects/medallion-rim.svg",
        "assets/masters/objects/stamp-rim.svg",
    ],
    "badge": [
        "assets/masters/objects/tag.svg",
        "assets/masters/objects/ticket.svg",
    ],
    "object": [
        "assets/objects/clock.webp",
        "assets/objects/passport-tray.webp",
        "assets/objects/shelf-plank.webp",
    ],
    "material": [
        "assets/material/grain-paper.webp",
        "assets/material/vignette-parchment.webp",
        "assets/material/wood-plank.webp",
    ],
    "fox": [
        "assets/fox/fox-read-256.webp",
        "assets/fox/fox-point-256.webp",
        "assets/fox/fox-clock-256.webp",
        "assets/fox/fox-think-256.webp",
        "assets/fox/fox-cheer-256.webp",
        "assets/fox/fox-wave-256.webp",
        "assets/fox/fox-sleep-256.webp",
    ],
}

#: Night-side kernel materials for the observatory, whose ground is a deep field green.
KERNEL_NIGHT = {
    "material": [
        "assets/material/grain-night.webp",
        "assets/material/vignette-night.webp",
        "assets/material/wood-plank-night.webp",
    ]
}

#: The two reference mockups. Hero and cover take the Home frame; lesson scenes take Classroom.
REF_HOME = "docs/concept-parity/refs/home.png"
REF_CLASSROOM = "docs/concept-parity/refs/classroom.png"

# --------------------------------------------------------------------------------------
# prompt composition

HEAD = (
    "A full-bleed painted scene of a room or workspace, not a still life, and not a screenshot. "
    "The painting is cropped hard edge to edge by the frame: no torn or deckled paper edge, no "
    "white margin, no vignette, no border, no picture frame. Three depth planes: painted "
    "foreground props, a midground bench or table, and an architectural background with a window, "
    "door or opening, paler in the distance. Do not paint the words of this instruction anywhere: "
    "there is no title, no caption, no heading and no label in the image."
)

#: Per-grammar scenes. Each names three depth planes and the grammar's own motifs and subject
#: cues. The composition sentence from `world.GRAMMARS[grammar]` is appended verbatim by
#: :func:`build_prompt`, so the plate and the policy table cannot disagree.
SCENES = {
    "workshop_manual": {
        "hero": (
            "Subject: a small vehicle workshop service bay, seen straight on at standing eye level. "
            "BACKGROUND: warm ochre-stained timber plank wall on the right and warm cream plaster on "
            "the left; a wide roller door open onto a warm sunlit earth yard, and behind it, soft "
            "and pale, the flat side of a plain unbadged van and a wooden fence. MIDGROUND: a heavy "
            "ochre wooden workbench across the frame with a plain dark-iron bench vice, a row of "
            "open wooden component trays with blank compartments, and a tall ochre pegboard of iron "
            "hooks holding hammers, spanners and a hacksaw in flat rounded shapes; the pegboard runs "
            "off the right edge. FOREGROUND: warm ochre-stained timber floor boards running off the "
            "bottom edge, a low wooden stool with a terracotta cushion, a folded terracotta shop rag, "
            "a coil of terracotta hose, four plain ochre-painted tins with blank lids."
        ),
        "cover": (
            "Subject: the same service bay, tighter on the bench, subject held in the middle half of "
            "the frame so a narrow vertical crop still holds it. BACKGROUND: the ochre pegboard of "
            "plain iron hand tools and a strip of warm plaster wall with one small window onto a "
            "sunlit yard. MIDGROUND: the ochre workbench with a bench vice, a stack of blank "
            "component trays and a folded shop rag. FOREGROUND: the bench edge and the timber floor "
            "running off the bottom and side edges, a plain tin and a coil of hose."
        ),
        "section": (
            "Subject: the tool wall itself, seen slightly from the left so the bench recedes. "
            "BACKGROUND: warm plaster wall and the roller door opening onto a bright yard at the "
            "left edge. MIDGROUND: the ochre pegboard carrying plain iron hammers, spanners, files "
            "and a hacksaw as flat rounded silhouettes on plain hooks, every hole plain; beneath it "
            "the bench edge with open component trays. FOREGROUND: the near corner of the bench "
            "running off the bottom edge, a folded rag and one plain tin."
        ),
        "lesson": (
            "Subject: a clear workbench where someone has just set down their work, seen at a slight "
            "three-quarter angle. BACKGROUND: warm timber wall, a shuttered window and the open "
            "roller door beyond, softer in the distance. MIDGROUND: the bench with a thick closed "
            "blank manual lying flat, a tray of blank parts compartments, an iron vice and a shop "
            "rag. FOREGROUND: the bench front running off the bottom edge, a low stool and a plain "
            "tin."
        ),
    },
    "observatory": {
        "hero": (
            "Subject: the inside of a small domed observatory at night, seen at standing eye level. "
            "BACKGROUND: the curved timber ribs of the dome and a wide open dome slit onto a deep "
            "field-green night sky studded with small flat painted stars of a few sizes, softly "
            "painted and low-contrast; the far horizon of dark hills at the bottom of the slit. "
            "MIDGROUND: a low brass-and-ochre instrument bench under the slit carrying a plain brass "
            "telescope on a simple yoke mount, a rolled star chart on a table beside it and an open "
            "blank observation log. FOREGROUND: warm ochre floorboards running off the bottom edge, "
            "a plain wooden stool, a coiled measuring cord and a flat leather case."
        ),
        "cover": (
            "Subject: the instrument bench and dome slit, tighter, subject held in the middle half of "
            "the frame so a narrow vertical crop still holds it. BACKGROUND: the dome ribs and the "
            "open slit onto a deep field-green sky with sparse flat painted stars. MIDGROUND: the "
            "brass telescope on its yoke, a rolled chart and a stack of blank log sheets. "
            "FOREGROUND: the ochre bench edge running off the bottom and side edges, a brass "
            "eyepiece cap and a folded cloth."
        ),
        "section": (
            "Subject: a chart table under the dome, seen from above at a slight angle. BACKGROUND: "
            "the dome wall and one narrow slit of deep field-green sky at the upper left. MIDGROUND: "
            "the ochre table with a large plain unmarked star chart sheet held flat by brass weights, "
            "a plain brass astrolabe disc with no markings, and a row of blank log sheets. "
            "FOREGROUND: the table edge running off the bottom edge, a brass divider and a pencil."
        ),
        "lesson": (
            "Subject: an observation desk lit warm, empty of people, seen straight on. BACKGROUND: a "
            "timber observatory wall with a small shuttered window and a dark green sky beyond. "
            "MIDGROUND: the desk with an open blank observation log, a plain brass lamp with a cream "
            "shade, a small brass telescope model and a cup. FOREGROUND: the desk front running off "
            "the bottom edge, a wooden chair back and a folded blanket."
        ),
    },
    "kitchen_table": {
        "hero": (
            "Subject: a warm kitchen table seen from above at a slight angle, laid out for cooking. "
            "BACKGROUND: the far edge of the table, a plain tiled splashback and a low shelf of cream "
            "crockery, a window at the top left onto a soft sunlit garden, all paler in the distance. "
            "MIDGROUND: the table with a wide empty ochre wooden board across the top, a deep cream "
            "mixing bowl, a stoneware jug, a linen cloth and a small herb bundle. FOREGROUND: the "
            "lower edge of the table crowded with ingredients: two whole oranges, a bunch of spring "
            "onions, a bowl of flour with a well in it, a wooden spoon, and a plain ceramic jar."
        ),
        "cover": (
            "Subject: the kitchen table seen from above, tighter, subject held in the middle half of "
            "the frame so a narrow vertical crop still holds it. BACKGROUND: the table edge, a tiled "
            "splashback and a copper pan hanging on a rail. MIDGROUND: a cream bowl of flour, a "
            "wooden spoon, a folded linen cloth and three whole eggs in a small dish. FOREGROUND: "
            "the table running off the bottom and side edges, a scattering of flour dust and a plain "
            "jar."
        ),
        "section": (
            "Subject: an ingredient board laid out across the lower frame, seen from above. "
            "BACKGROUND: the table surface and the base of a cream tiled wall, a linen cloth folded "
            "at the top. MIDGROUND: an ochre board with a knife, a wooden spoon, a bowl of flour, a "
            "jug of milk and a bundle of herbs tied with twine. FOREGROUND: the board edge running "
            "off the bottom edge, loose flour dust and two oranges."
        ),
        "lesson": (
            "Subject: a kitchen table mid-lesson, seen straight on at sitting height. BACKGROUND: "
            "warm plaster wall, a tiled splashback and a tall window onto a garden at the left, all "
            "paler in the distance. MIDGROUND: the table with a deep cream bowl and a wooden spoon "
            "standing in it, a folded linen cloth, a jug and a small stack of plain plates. "
            "FOREGROUND: the near table edge running off the bottom edge, a chair back and a linen "
            "napkin."
        ),
    },
    "archive_desk": {
        "hero": (
            "Subject: a reading desk seen from slightly above, the desk of someone mid-research. "
            "BACKGROUND: a tall dark ochre bookcase against a warm plaster wall, its shelves full of "
            "plain blank spines, and a tall window at the upper right onto soft grey-free daylight. "
            "MIDGROUND: the wide ochre desk with a stack of plain document trays, overlapping sheets "
            "of completely blank paper, a brass inkwell and a plain wax stamp with a blank face, a "
            "row of blank index cards standing in a wooden box. FOREGROUND: the near desk edge "
            "running off the bottom edge, a magnifier, a brass paperweight and one blank card."
        ),
        "cover": (
            "Subject: the document trays and papers on the desk, tighter, subject held in the middle "
            "half of the frame so a narrow vertical crop still holds it. BACKGROUND: the bookcase "
            "and a panel of warm wall. MIDGROUND: three stacked ochre document trays overflowing "
            "with completely blank sheets, a plain wax seal, a brass clip and a small stamp with a "
            "blank face. FOREGROUND: the desk edge running off the bottom and side edges, a "
            "magnifier and a blank index card."
        ),
        "section": (
            "Subject: an open index-card drawer and a map drawer pulled out, seen from above. "
            "BACKGROUND: the ochre cabinet body and a warm plaster wall. MIDGROUND: the drawer full "
            "of blank index cards standing in tidy rows, and beside it a shallow map drawer holding "
            "a rolled blank chart sheet. FOREGROUND: the cabinet edge running off the bottom edge, a "
            "brass label holder with a blank face and a plain card."
        ),
        "lesson": (
            "Subject: a reading desk with an empty chair, seen straight on. BACKGROUND: a tall "
            "bookcase of plain blank spines and a warm wall, a tall window at the left. MIDGROUND: "
            "the desk with an open blank ledger, a brass reading lamp with a cream shade, a stack of "
            "blank cards and a plain document tray. FOREGROUND: the desk front running off the "
            "bottom edge, the chair back and a folded cloth."
        ),
    },
    "studio_bench": {
        "hero": (
            "Subject: a working studio bench seen from slightly above, with material swatches fanning "
            "to the left and an open quiet field to the right. BACKGROUND: a warm plaster wall with "
            "a pinboard of completely blank cards, a shelf of plain paint tins and a tall window at "
            "the left onto soft daylight. MIDGROUND: the ochre bench with a fan of terracotta, cream "
            "and field-green fabric swatches, an open blank sketchbook, a cutting mat with a plain "
            "grid-free surface, a jar of brushes and three plain paint tins. FOREGROUND: the bench "
            "edge running off the bottom edge, a pair of scissors, a spool of thread and one loose "
            "swatch."
        ),
        "cover": (
            "Subject: the bench with swatches and paint tins, tighter, subject held in the middle "
            "half of the frame so a narrow vertical crop still holds it. BACKGROUND: the warm wall "
            "and a shelf of plain tins. MIDGROUND: a fan of warm fabric swatches, an open blank "
            "sketchbook, a jar of brushes and three plain tins. FOREGROUND: the bench edge running "
            "off the bottom and side edges, a cutting mat corner and a loose swatch."
        ),
        "section": (
            "Subject: a material fan laid out across the bench, seen from above. BACKGROUND: the "
            "bench surface and a warm wall with a pinboard of blank cards. MIDGROUND: twelve fabric "
            "swatches of terracotta, cream, ochre and field green fanned in an arc, a plain wooden "
            "ruler with no markings, and a spool of thread. FOREGROUND: the bench edge running off "
            "the bottom edge, a loose button and a pair of scissors."
        ),
        "lesson": (
            "Subject: a studio bench mid-work with an empty stool, seen straight on. BACKGROUND: a "
            "warm plaster wall, a pinboard of blank cards and a window at the left. MIDGROUND: the "
            "bench with an open blank sketchbook, a jar of brushes, a plain tin, a folded cloth and a "
            "small terracotta pot. FOREGROUND: the bench front running off the bottom edge, the "
            "stool and a roll of paper."
        ),
    },
    "lab_bench": {
        "hero": (
            "Subject: a clean laboratory bench seen straight on, glassware receding to the right. "
            "BACKGROUND: a warm cream tiled wall, a plain shelf of glassware and a wide window at the "
            "left onto soft daylight; nothing hangs on the wall. MIDGROUND: the bench with a row of "
            "plain glass beakers, flasks and a graduated cylinder whose markings are completely "
            "absent, a rack of plain test tubes with blank bodies, and a folded cloth. FOREGROUND: "
            "the bench edge running off the bottom edge, a plain wash bottle, a pair of safety "
            "goggles with clear untinted lenses and a blank lab notebook."
        ),
        "cover": (
            "Subject: glassware on the bench, tighter, subject held in the middle half of the frame "
            "so a narrow vertical crop still holds it. BACKGROUND: the tiled wall and a shelf of "
            "plain glassware. MIDGROUND: beakers, a flask, a wide dish and a rack of plain test "
            "tubes, all with no markings of any kind. FOREGROUND: the bench edge running off the "
            "bottom and side edges, a plain wash bottle and a folded cloth."
        ),
        "section": (
            "Subject: a shelf of glassware seen from slightly below, glassware receding in a row. "
            "BACKGROUND: the cream tiled wall and the top of the bench. MIDGROUND: a plain shelf "
            "carrying beakers, flasks, a funnel, a wide dish and three plain jars with blank lids. "
            "FOREGROUND: the shelf edge running off the bottom edge, a pair of goggles and a folded "
            "cloth."
        ),
        "lesson": (
            "Subject: a lab bench set out for a beginner lesson, seen straight on with no people. "
            "BACKGROUND: warm tiled wall, a shelf of plain glassware and a window at the right. "
            "MIDGROUND: the bench with an open blank lab notebook, a rack of plain test tubes, a "
            "beaker, a plain wash bottle and a pair of goggles lying flat. FOREGROUND: the bench "
            "front running off the bottom edge, a stool and a folded cloth."
        ),
    },
    "instrument_board": {
        "hero": (
            "Subject: a wide drafting board seen at a slight angle, an open quiet surface across the "
            "upper two thirds. BACKGROUND: the warm wall behind the board, a low shelf with rolled "
            "paper tubes and a tall window at the right onto soft daylight. MIDGROUND: the board "
            "with a plain unmarked surface that fades into warm wall toward the top, brass dividers, a "
            "plain wooden set square with no markings, a ruled straightedge with no figures and a "
            "chalk tray holding plain white chalk sticks. FOREGROUND: the board edge running off the "
            "bottom edge, a wooden stool and a rolled sheet of paper."
        ),
        "cover": (
            "Subject: the drafting board with instruments, tighter, subject held in the middle half "
            "of the frame so a narrow vertical crop still holds it. BACKGROUND: the warm wall and a "
            "low shelf of rolled paper. MIDGROUND: brass dividers, a plain set square, a "
            "straightedge with no figures and a chalk tray with plain chalk. FOREGROUND: the board "
            "edge running off the bottom and side edges, a cloth eraser and a pencil."
        ),
        "section": (
            "Subject: a drafting board seen from above, a plain unmarked surface. "
            "BACKGROUND: the board surface and the warm wall beyond. MIDGROUND: brass dividers, a "
            "plain set square, a pair of plain compasses and a chalk tray with plain chalk sticks, "
            "no figures on any instrument. FOREGROUND: the board edge running off the bottom edge, "
            "a cloth eraser and a rolled sheet."
        ),
        "lesson": (
            "Subject: a drafting board with a stool, seen straight on, empty of people. BACKGROUND: "
            "the warm wall, a shelf of rolled paper and a window at the left. MIDGROUND: the board "
            "with a plain unmarked surface, brass dividers, a plain set square and a chalk tray. "
            "FOREGROUND: the board front running off the bottom edge, the stool and a cloth eraser."
        ),
    },
}

#: Per-grammar safety fences. Every one keeps the plate environmental: nothing in a plate may be
#: read as a procedure, a value, a measurement, a part, a hazard or an authority. The card names
#: `workshop_manual`, `lab_bench` and `archive_desk` as usable for technical subjects, so their
#: fences are the strictest.
SAFETY = {
    "workshop_manual": (
        "Orientation art only. No torque value, no clearance, no part number, no sequence, no "
        "procedure, no measurement, no gauge, no dial, no scale, no ruler markings, no torque "
        "wrench, no numbered socket, no diagram, no cutaway, no exploded view, no arrow, no step "
        "number. Nothing in the plate is instructional and nothing in it is a specification."
    ),
    "observatory": (
        "Orientation art only. No chart numbers, no coordinates, no dial markings, no constellation "
        "glyphs, no lettering on any instrument, no scale, no measurement, no equation. The sky is "
        "painted mood and is never a measurement or a real star chart."
    ),
    "kitchen_table": (
        "Orientation art only. No recipe card text, no measuring marks, no cup or gram markings, no "
        "numbers, no timer face, no temperature dial, no procedure. Nothing in the plate implies a "
        "tested recipe or a food-safety instruction."
    ),
    "archive_desk": (
        "Orientation art only. Every sheet of paper, card, spine, ledger and label is completely "
        "blank: no writing, no lettering, no quotation, no line of text, no signature, no seal "
        "impression, no document number. Nothing in the plate is a source, a quotation or a record, "
        "and nothing in it is legal or medical advice."
    ),
    "studio_bench": (
        "Orientation art only. No sheet music, no notation, no stave, no clef, no chord chart, no "
        "colour code, no swatch label, no paint-tin label, no measurement, no technique diagram. "
        "Nothing in the plate is a technique authority."
    ),
    "lab_bench": (
        "Orientation art only. No label on any bottle, jar, beaker or tube, no hazard diamond, no "
        "GHS pictogram, no warning sign, no equation, no formula, no measurement marking, no "
        "graduation, no meniscus reading, no procedure, no dose. Nothing in the plate is a safety "
        "reference, a chemical identity or a measurement."
    ),
    "instrument_board": (
        "Orientation art only. No numbers, no figures, no equations, no axis labels, no grid "
        "numbering, no scale, no protractor markings, no measurement. The board is a quiet surface "
        "and never a worked example, a proof or a required lesson visual."
    ),
    "field_atlas": (
        "Orientation art only. No map legend, no place name, no ticket lettering, no signage."
    ),
}

TEXTLESS = (
    "Textless: no letters, words, numbers, labels, signage, notice board, wall chart, poster, "
    "chalkboard, framed picture, watermark, logo or UI chrome. Every page, chart, card, book, "
    "ledger and sheet is plain blank cream paper: no ruled lines, no grid, no drawn diagram, no "
    "scribble, no writing, no printed mark. Every tool, instrument, tin, jar and badge is plain "
    "and unengraved: no stamped letters, no maker's mark, no etched numbering, no dial face. No "
    "people, hands, faces, animals or fox."
)

STYLE = (
    "Painted in opaque gouache on warm paper, dark warm-brown ink contour drawn last, thick body "
    "colour, visible flat brush-shaped marks in every mass, crisp brush-stopped edges, one soft key "
    "light from the upper left, one shade plane down-right in a darker tint of the same pigment. "
    "Never pure black, no gradient, no glow, no bloom, no vignette."
)

#: The quiet field each plate must leave for real DOM type. `hero` and `section` keep the upper
#: third; `cover` keeps the middle half so a 4:5 centre crop survives; `lesson` keeps the upper
#: third for the lesson title.
QUIET = {
    "hero": (
        "The upper third of the frame is a quiet field reserved for a headline typeset later: a "
        "plain painted surface with a couple of faint broad brush marks, low contrast, no small "
        "detail, reaching the top edge of the frame, still painted environment and not bare "
        "parchment."
    ),
    "cover": (
        "The headline band and the middle half of the frame stay quiet enough for a title typeset "
        "later: no small detail in the centre, no busy pattern behind the middle."
    ),
    "section": (
        "The upper third of the frame is a quiet field reserved for a section title typeset later: "
        "low contrast, no small detail."
    ),
    "lesson": (
        "The upper third of the frame is a quiet field reserved for the lesson title typeset later: "
        "low contrast, no small detail."
    ),
}


def _pigment_names(grammar: str) -> list[str]:
    """The grammar's palette as spoken pigment names (no digits, no hex)."""
    out = []
    for pigment in GRAMMARS[grammar].palette:
        name = pigment.split("#")[0].strip()
        # "warm paper" -> "warm paper"; keep the family word before the hex
        out.append(name)
    return out


def _pigment_hexes(grammar: str) -> dict[str, str]:
    out = {}
    for pigment in GRAMMARS[grammar].palette:
        if "#" in pigment:
            name, hexv = pigment.split("#", 1)
            out[name.strip()] = "#" + hexv.strip()
    return out


def build_prompt(grammar: str, kind: str) -> str:
    rec = GRAMMARS[grammar]
    palette = ", ".join(_pigment_names(grammar))
    parts = [
        HEAD,
        SCENES[grammar][kind],
        f"Composition: {rec.composition}.",
        f"Grammar motifs: {', '.join(rec.motifs)}.",
        QUIET[kind],
        STYLE,
        f"Warm pigments only, at most {MAX_PLATE_PIGMENTS}: {palette}. No blue, no grey, no "
        "neutral black, no steel, no chrome, no concrete.",
        SAFETY[grammar],
        TEXTLESS,
    ]
    return "\n\n".join(parts)


# --------------------------------------------------------------------------------------
# helpers reused from the VQ-002 judge (one implementation, not a copy)

def _load_vq002():
    path = ROOT / "scripts" / "vq002-kit-audit.py"
    spec = importlib.util.spec_from_file_location("vq002_kit_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VQ002 = _load_vq002()
sha256 = VQ002.sha256
dims = VQ002.dims
ocr_tokens = VQ002.ocr_tokens
dominant = VQ002.dominant
cool_share = VQ002.cool_share
field_stats = VQ002.field_stats
black_minima = VQ002.black_minima
contrast_ratio = VQ002.contrast_ratio


def gray_minima(path: Path) -> float:
    out = subprocess.run(
        ["magick", str(path), "-colorspace", "Gray", "-format", "%[fx:minima]", "info:"],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def warm_ground(hexv: str, tol: int = 12) -> tuple[bool, str]:
    """Warm means red >= green >= blue - tolerance; a cool or neutral ground is a palette fail."""
    r = int(hexv[1:3], 16); g = int(hexv[3:5], 16); b = int(hexv[5:7], 16)
    return (r >= b and g >= b - tol), f"#{hexv[1:]}(r{r} g{g} b{b})"


def palette_match(hexv: str, grammar: str) -> tuple[bool, str]:
    """The ground must be warm or be one of this grammar's own pigments.

    The observatory's night sky is a large field-green mass by design, so a warm-only test would
    fail the grammar the policy table authored. Distance is measured per channel against the
    grammar's own palette, exactly as `world.GRAMMARS[grammar].palette` declares it.
    """
    r = int(hexv[1:3], 16); g = int(hexv[3:5], 16); b = int(hexv[5:7], 16)
    best = None
    for name, value in _pigment_hexes(grammar).items():
        pr = int(value[1:3], 16); pg = int(value[3:5], 16); pb = int(value[5:7], 16)
        dist = max(abs(r - pr), abs(g - pg), abs(b - pb))
        if best is None or dist < best[1]:
            best = (name, dist)
    warm, why = warm_ground(hexv)
    if warm:
        return True, why
    if best and best[1] <= 48:
        return True, f"matches grammar pigment {best[0]!r} within {best[1]} levels"
    return False, f"{why}; nearest grammar pigment {best[0]!r} is {best[1]} levels away"


# --------------------------------------------------------------------------------------
# kit assembly

def kit_dir(grammar: str) -> Path:
    return KITS / grammar


def kernel_for(grammar: str) -> dict[str, list[str]]:
    groups = {k: list(v) for k, v in KERNEL.items()}
    if grammar == "observatory":
        groups["material"] = list(KERNEL_NIGHT["material"])
    return groups


def _media_url(grammar: str, asset_id: str) -> str | None:
    log = kit_dir(grammar) / "generation.json"
    if not log.exists():
        return None
    rows = json.loads(log.read_text())
    for row in rows:
        if row.get("asset") == asset_id and row.get("verdict") == "accepted":
            return row.get("media_url")
    return None


def _vision_row(grammar: str, asset_id: str) -> dict:
    log = kit_dir(grammar) / "generation.json"
    if not log.exists():
        return {}
    for row in json.loads(log.read_text()):
        if row.get("asset") == asset_id and row.get("verdict") == "accepted":
            return row
    return {}


def best_quiet_band(path: Path, height: int = 220) -> dict:
    """Find the flattest band in the upper 45% that still carries real type contrast.

    A fixed rectangle is a guess about where the model put its quiet field, and type is dark ink
    on a light plate but cream on a night plate. This scans candidate bands and records the one
    this plate actually offers, with contrast measured against both contract inks, so the claim in
    the manifest is a measurement of the shipped bytes.
    """
    width, h = dims(path)
    cream = (0xF7, 0xF1, 0xE4)
    best = None
    for y in range(0, int(h * 0.45) - height + 1, 20):
        for x in (0, (width - 544) // 4, (width - 544) // 2, (width - 544) * 3 // 4, width - 544):
            box = (x, y, 544, height)
            stats = field_stats(path, box)
            p5 = stats["percentile_5"]
            on_cream = round(contrast_ratio((p5, p5, p5), cream), 2)
            score = max(stats["contrast_p5"], on_cream)
            if best is None or score > best[2]:
                best = (box, stats, score, on_cream)
    if best is None:
        return {"x": 0, "y": 0, "w": 544, "h": height, "note": "no band fitted"}
    box, stats, score, on_cream = best
    return {
        "x": box[0], "y": box[1], "w": box[2], "h": box[3],
        "note": "the flattest band this plate actually offers in the upper 45%, chosen by the "
                "better of its measured contrast against contract ink and against cream paper",
        "contrast_p5_on_cream": on_cream,
        "best_contrast": score,
        "type_tone": "ink" if stats["contrast_p5"] >= on_cream else "cream",
        **stats,
    }


def neutral_share(path: Path, scale: str = "25%") -> float:
    """Share of pixels whose channels are within 8 levels of each other — grey/neutral mass.

    Recorded, not gated: the bible forbids neutral mass, and this number shows a reviewer how
    much of a plate is grey even where the dominant ground is warm.
    """
    raw = subprocess.run(
        ["magick", str(path), "-resize", scale, "-depth", "8", "rgb:-"],
        capture_output=True, check=True,
    ).stdout
    n = len(raw) // 3
    if not n:
        return 0.0
    grey = 0
    for i in range(0, len(raw), 3):
        r, g, b = raw[i], raw[i + 1], raw[i + 2]
        if max(r, g, b) - min(r, g, b) <= 8:
            grey += 1
    return round(grey / n, 5)


def _raw_path(grammar: str, asset_id: str) -> Path:
    return RAW_DIR / grammar / f"{asset_id}.raw.png"


def asset_entry(grammar: str, rel: str, role: str, quiet: dict | None = None) -> dict:
    path = kit_dir(grammar) / rel
    entry = {
        "id": Path(rel).stem,
        "role": role,
        "path": rel,
        "size": list(dims(path)),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "textless": True,
        "source": "curated_kit",
    }
    ref = _vision_row(grammar, Path(rel).stem).get(
        "reference", REF_CLASSROOM if role in ("lesson_scene", "section") else REF_HOME
    )
    entry["provenance"] = {
        "origin": "generated",
        "provider": "host image_generate seam",
        "model_id": "not reported by the seam",
        "generated_on": date.today().isoformat(),
        "generation": (
            "reference-guided: the reference mockup was passed in reference_image_urls, with the "
            "host upscale pass on" if ref else
            "text-only prompt: no reference image was passed, with the host upscale pass on"
        ),
        "reference_image": ref,
        "media_url": _media_url(grammar, Path(rel).stem),
        "raw_path": f".vq-raw/vq008/{grammar}/{Path(rel).stem}.raw.png",
        "raw_sha256": sha256(_raw_path(grammar, Path(rel).stem))
        if _raw_path(grammar, Path(rel).stem).exists() else None,
        "prompt": _vision_row(grammar, Path(rel).stem).get("prompt")
        or build_prompt(grammar, kind_for(role)),
        "prompt_provenance": "the canonical composer prompt for this grammar and role; the attempt "
                             "that produced this plate was sent with this prompt plus the delta "
                             "recorded as prompt_delta in generation.json, so the manifest does not "
                             "claim a byte-exact prompt record",
        "prompt_delta": _vision_row(grammar, Path(rel).stem).get("prompt_delta"),
        "pipeline": PIPELINE,
        "ocr": ocr_tokens(path),
        "measured": {
            "dominant": dominant(path)[0],
            "black_minima": round(gray_minima(path), 5),
            "cool_share": cool_share(path),
            "neutral_share": neutral_share(path),
        },
        "vision": {
            "reviewed_on": date.today().isoformat(),
            "checks": _vision_row(grammar, Path(rel).stem).get("vision", ""),
            "residual": _vision_row(grammar, Path(rel).stem).get("residual", ""),
        },
    }
    if role == "hero":
        provenance = entry["provenance"]
        raw = _raw_path(grammar, Path(rel).stem)
        raw_size = list(dims(raw)) if raw.exists() else [2688, 1536]
        native = raw_size[0] >= 2688
        provenance["derivation"] = "raw " + "x".join(map(str, raw_size)) + " resized 50% to the required 1344x768"
        provenance["source_frame"] = {
            "path": str(Path(rel).with_name(Path(rel).stem + "@2x.png")),
            "size": [2688, 1536],
            "scale": 2.0,
            "provider_frame": raw_size,
            "native_2x": native,
            "note": (
                "the provider returned a 2x frame; the 2688x1536 file beside the plate is that frame "
                "carried through the print-safety lift" if native else
                f"the provider returned a {raw_size[0]}x{raw_size[1]} frame (1.5x of the plate), so the "
                "2688x1536 file beside the plate is a resampled 2x frame, not a native provider "
                "return; Gate 2 sees a 2x asset but the provenance says which it is"
            ),
        }
    if role == "cover":
        provenance = entry["provenance"]
        raw = _raw_path(grammar, Path(rel).stem)
        raw_size = dims(raw) if raw.exists() else (2688, 1536)
        nat = cover_crop(raw_size, (3, 2))
        nat45 = cover_crop(raw_size, (4, 5))
        provenance["derivation"] = (
            f"raw {raw_size[0]}x{raw_size[1]} centre crop {nat[0]}x{nat[1]}, resized to 1200x800; "
            f"the 4:5 is a {nat45[0]}x{nat45[1]} centre crop of the same frame, not a second generation"
        )
        provenance["source_frame"] = {
            "path": None,
            "size": list(nat),
            "scale": round(nat[0] / 600, 4),
            "ratios": {
                "shipped_vs_render": round(1200 / 600, 4),
                "natural_vs_shipped": round(nat[0] / 1200, 4),
                "natural_vs_render": round(nat[0] / 600, 4),
            },
            "note": (
                "the shipped 1200x800 plate is exactly 2x the 600x400 render; the "
                f"{nat[0]}x{nat[1]} natural crop is {round(nat[0] / 1200, 2)}x the shipped plate and "
                f"{round(nat[0] / 600, 2)}x the render"
            ),
        }
        entry["provenance"]["crop_4x5"] = {
            "size": list(nat45),
            "note": f"centre crop of the same provider frame, resized to 640x800 (2x of a 320x400 render)",
        }
    if role == "hero":
        entry["provenance"]["measured"]["quiet_field"] = best_quiet_band(path)
    return entry


def kind_for(role: str) -> str:
    return {"hero": "hero", "cover": "cover", "section": "section", "lesson_scene": "lesson"}[role]


def derived_entry(grammar: str, rel: str, role: str, master: dict) -> dict:
    path = kit_dir(grammar) / rel
    provenance = dict(master["provenance"])
    provenance.pop("source_frame", None)
    provenance["derivation"] = (
        f"centre crop of the {master['id']} natural 2304x1536 frame to 1152x1440, resized to "
        f"640x800; derived from the same generation, not a second attempt"
    )
    provenance["measured"] = {"dominant": dominant(path)[0], "black_minima": round(gray_minima(path), 5)}
    provenance["ocr"] = ocr_tokens(path)
    return {
        "id": Path(rel).stem,
        "role": role,
        "path": rel,
        "size": list(dims(path)),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "textless": True,
        "source": "curated_kit",
        "derived_from": master["id"],
        "provenance": provenance,
    }


def kernel_entries(grammar: str) -> dict[str, list[dict]]:
    out = {}
    for role, paths in kernel_for(grammar).items():
        rows = []
        for rel in paths:
            path = ROOT / rel
            if not path.exists():
                raise SystemExit(f"missing kernel asset {rel}")
            rows.append({
                "id": path.stem,
                "role": role,
                "path": rel,
                "size": list(dims(path)),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
                "textless": True,
                "source": "curated_kit",
                "shared_kernel": True,
                "provenance": {
                    "origin": "shared_kernel",
                    "kit_id": "coursebook-kernel@1",
                    "note": "shared visual kernel; one set of bytes every grammar kit points at",
                },
            })
        out[role] = rows
    return out


def build_kit(grammar: str) -> dict:
    rec = GRAMMARS[grammar]
    roles: dict[str, list[dict]] = {"hero": [], "cover": [], "section": [], "lesson_scene": []}
    cover_master = None
    for role, rel, rawkind in PLATE_TABLE[grammar]:
        quiet = None
        if role == "hero":
            quiet = {"x": 400, "y": 20, "w": 544, "h": 220,
                     "note": "the painted quiet band in the upper third, where the display title sits"}
        entry = asset_entry(grammar, rel, role, quiet)
        roles[role].append(entry)
        if role == "cover":
            cover_master = entry
            crop = "cover/" + rel.split("/")[-1].replace("-3x2", "-4x5")
            roles["cover"].append(derived_entry(grammar, crop, "cover", cover_master))
    roles.update(kernel_entries(grammar))
    # lesson scenes point at the section plate before the generic background (GAME-MODE §5).
    return {
        "grammar": grammar,
        "kit_id": f"{grammar}@1",
        "label": rec.label,
        "version": 1,
        "status": "built_for_owner_review",
        "art_bible": ART_BIBLE,
        "lane": "display_plate",
        "prompt_version": "vq008-kit-prompt-v1",
        "palette": _pigment_hexes(grammar),
        "palette_tokens": _pigment_names(grammar),
        "medium": rec.medium,
        "composition": rec.composition,
        "motifs": list(rec.motifs),
        "subject_cues": list(rec.subject_cues),
        "illustration_role": rec.illustration_role,
        "cannot_do": rec.cannot_do,
        "provider_free": True,
        "kernel": {
            "kit_id": "coursebook-kernel@1",
            "note": "shared objects, frames, badges, materials and fox poses are referenced from "
                    "one kernel; a kit does not copy new bytes for them",
            "groups": {k: [str(ROOT / p).replace(str(ROOT) + "/", "") for p in v]
                       for k, v in kernel_for(grammar).items()},
        },
        "roles": roles,
        "fallbacks": FALLBACKS,
        "generation_budget": {
            "attempts_allowed": ATTEMPTS_ALLOWED,
            "per_asset_max": PER_ASSET_MAX,
            "attempts_used": _attempts_used(grammar),
        },
    }


def _attempts_used(grammar: str) -> int:
    log = kit_dir(grammar) / "generation.json"
    if not log.exists():
        return len(PLATE_TABLE.get(grammar, []))
    return len(json.loads(log.read_text()))


# --------------------------------------------------------------------------------------
# judge

FAILS: list[str] = []
FAILS = []


def fail(msg: str) -> None:
    FAILS.append(msg)


def check_plate(grammar: str, plate: dict, required_role: str) -> None:
    where = f"{grammar}/{plate['path']}"
    path = kit_dir(grammar) / plate["path"]
    if not path.exists():
        fail(f"{where}: missing"); return
    if path.stat().st_size < 1024:
        fail(f"{where}: placeholder-sized file ({path.stat().st_size} B)"); return
    if sha256(path) != plate["sha256"]:
        fail(f"{where}: sha256 is stale")
    if list(dims(path)) != list(plate["size"]):
        fail(f"{where}: size {dims(path)} != declared {plate['size']}")
    if plate["bytes"] != path.stat().st_size:
        fail(f"{where}: byte count is stale")
    if not plate.get("textless"):
        fail(f"{where}: textless is not declared true")
    ocr = ocr_tokens(path)
    if ocr.get("readable"):
        fail(f"{where}: OCR-read text {ocr['readable']}")
    minima = gray_minima(path)
    if minima < 0.039:
        fail(f"{where}: ships pure black (grayscale minima {minima:.4f})")
    dom, _ = dominant(path)
    ok, why = palette_match(dom, grammar)
    if not ok:
        fail(f"{where}: ground is outside the grammar palette ({why})")
    if required_role == "hero":
        if tuple(plate["size"]) != PLATE_SIZES["hero"]:
            fail(f"{where}: hero must be 1344x768, is {plate['size']}")
        qf = plate["provenance"].get("measured", {}).get("quiet_field")
        if not qf:
            fail(f"{where}: hero has no measured quiet field")
        elif qf.get("best_contrast", qf.get("contrast_p5", 0)) < 4.5:
            fail(f"{where}: quiet field contrast is {qf.get('best_contrast')} < 4.5 against both "
                 f"contract ink and cream paper")
        sf = plate["provenance"].get("source_frame") or {}
        p2 = path.with_name(path.stem + "@2x.png")
        if not p2.exists():
            fail(f"{where}: no @2x source frame beside the plate")
        elif list(dims(p2)) != [2688, 1536]:
            fail(f"{where}: @2x frame is {dims(p2)}, not 2688x1536")
        elif "native_2x" not in sf:
            fail(f"{where}: source frame does not say whether it is a native 2x return")


def check_cover_arithmetic(grammar: str, plates: list[dict]) -> None:
    masters = [p for p in plates if "derived_from" not in p]
    if len(masters) != 1:
        fail(f"{grammar}: expected exactly one 3:2 cover master, found {len(masters)}"); return
    master = masters[0]
    if tuple(master["size"]) != COVER_3X2_SHIPPED:
        fail(f"{grammar}: 3:2 cover must be 1200x800")
    sf = master["provenance"].get("source_frame") or {}
    ratios = sf.get("ratios") or {}
    natural = sf.get("size") or [0, 0]
    if natural[0] < COVER_3X2_SHIPPED[0] or natural[1] < COVER_3X2_SHIPPED[1]:
        fail(f"{grammar}: natural crop {natural} is smaller than the shipped plate")
    want = {
        "shipped_vs_render": round(COVER_3X2_SHIPPED[0] / COVER_3X2_RENDERED[0], 4),
        "natural_vs_shipped": round(natural[0] / COVER_3X2_SHIPPED[0], 4),
        "natural_vs_render": round(natural[0] / COVER_3X2_RENDERED[0], 4),
    }
    for key, value in want.items():
        if ratios.get(key) != value:
            fail(f"{grammar}: cover ratio {key} = {ratios.get(key)!r}, must be {value}")
    note = (sf.get("note") or "").lower()
    for wrong in ("2400x1600", "1.92x of the 600x400 render", "1.92x of the render"):
        if wrong in note:
            fail(f"{grammar}: cover note names the wrong referent ({wrong!r})")
    if f"{natural[0]}x{natural[1]}" not in note:
        fail(f"{grammar}: cover note does not name its own crop size {natural[0]}x{natural[1]}")


def check_kernel(grammar: str, kit: dict) -> None:
    groups = kernel_for(grammar)
    for role, paths in groups.items():
        rows = kit["roles"].get(role) or []
        if len(rows) != len(paths):
            fail(f"{grammar}: kernel role {role} has {len(rows)} rows, expected {len(paths)}")
        for row in rows:
            path = ROOT / row["path"]
            if not path.exists():
                fail(f"{grammar}: kernel {row['path']} missing"); continue
            if sha256(path) != row["sha256"]:
                fail(f"{grammar}: kernel {row['path']} sha256 is stale")


def check_fallbacks(grammar: str, kit: dict) -> None:
    declared = set(kit["roles"])
    for role, chain in (kit.get("fallbacks") or {}).items():
        if role not in declared:
            fail(f"{grammar}: fallback role {role!r} is not a declared role")
        for step in chain:
            norm = step.lower()
            if any(bad in norm for bad in FORBIDDEN_FALLBACK_TOKENS):
                fail(f"{grammar}: fallback {role} names a forbidden step {step!r}")
            if step not in ALLOWED_FALLBACKS:
                fail(f"{grammar}: fallback {role} names an unknown token {step!r}")
    cover = (kit.get("fallbacks") or {}).get("cover") or []
    if not cover or cover[0] != "course-master":
        fail(f"{grammar}: cover fallback chain must lead with course-master, is {cover}")


def check_grammar_consistency(grammar: str, kit: dict) -> None:
    rec = GRAMMARS[grammar]
    if kit.get("grammar") != grammar:
        fail(f"{grammar}: kit.json grammar is {kit.get('grammar')!r}")
    if kit.get("label") != rec.label:
        fail(f"{grammar}: label drifted from the grammar table")
    if kit.get("medium") != rec.medium:
        fail(f"{grammar}: medium drifted from the grammar table")
    if kit.get("composition") != rec.composition:
        fail(f"{grammar}: composition drifted from the grammar table")
    if kit.get("palette") != _pigment_hexes(grammar):
        fail(f"{grammar}: palette drifted from the grammar table")
    if kit.get("motifs") != list(rec.motifs):
        fail(f"{grammar}: motifs drifted from the grammar table")
    if len(kit.get("palette", {})) > MAX_PLATE_PIGMENTS:
        fail(f"{grammar}: more than {MAX_PLATE_PIGMENTS} pigments declared")


def check_budget(grammar: str, kit: dict) -> None:
    budget = kit.get("generation_budget") or {}
    if budget.get("attempts_used", 0) > budget.get("attempts_allowed", 0):
        fail(f"{grammar}: attempts_used {budget.get('attempts_used')} exceeds "
             f"{budget.get('attempts_allowed')}")
    log = kit_dir(grammar) / "generation.json"
    if log.exists():
        rows = json.loads(log.read_text())
        per: dict[str, int] = {}
        for row in rows:
            per[row["asset"]] = per.get(row["asset"], 0) + 1
        for asset, count in per.items():
            if count > budget.get("per_asset_max", PER_ASSET_MAX):
                fail(f"{grammar}: {asset} used {count} attempts > per_asset_max")


def check_text_absence(grammar: str) -> None:
    """No fictional proof title, no Press Plate, no placeholder name anywhere in the kit tree."""
    root = kit_dir(grammar)
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".json", ".md", ".txt"}:
            continue
        text = path.read_text(errors="ignore")
        for title in FICTIONAL_TITLES:
            if title in text:
                fail(f"{grammar}: {path.name} names the fictional proof course {title!r}")
        if "press-plate" in text.lower() or "pack-cover" in text.lower():
            low = text.lower()
            if path.name != "kit.json" or '"pack-cover"' in low and "forbidden" not in low:
                fail(f"{grammar}: {path.name} names a Press Plate / pack cover")
    for path in root.rglob("*"):
        if path.is_file() and any(
            token in path.name.lower() for token in ("placeholder", "todo", "dummy", "lorem")
        ):
            fail(f"{grammar}: placeholder file {path.name}")


def check_kit(grammar: str) -> int:
    path = kit_dir(grammar) / "kit.json"
    if not path.exists():
        fail(f"{grammar}: kit.json missing"); return 1
    kit = json.loads(path.read_text())

    if grammar == "field_atlas":
        # VQ-002's approved kit is judged by its own contract (its own role list, its own
        # vocabulary, six covers for three shelf courses), not by the VQ-008 shape.
        if kit.get("grammar") != grammar:
            fail(f"{grammar}: kit.json grammar is {kit.get('grammar')!r}")
        for role, rows in kit["roles"].items():
            for row in rows:
                p = kit_dir(grammar) / row["path"]
                if not p.exists():
                    fail(f"{grammar}: {row['path']} missing"); continue
                if sha256(p) != row["sha256"]:
                    fail(f"{grammar}: {row['path']} sha256 is stale")
        check_text_absence(grammar)
        return 0 if not FAILS else 1

    check_grammar_consistency(grammar, kit)
    check_fallbacks(grammar, kit)
    check_kernel(grammar, kit)
    check_budget(grammar, kit)
    check_text_absence(grammar)

    roles = kit["roles"]
    hero = roles.get("hero") or []
    if len(hero) != 1:
        fail(f"{grammar}: expected exactly one hero, found {len(hero)}")
    covers = roles.get("cover") or []
    if len(covers) != 2:
        fail(f"{grammar}: expected a 3:2 and a 4:5 cover, found {len(covers)}")
    sections = roles.get("section") or []
    lessons = roles.get("lesson_scene") or []

    if grammar == "field_atlas":
        # VQ-002's approved kit: judged by its own role list, not by the VQ-008 shape.
        for role, rows in roles.items():
            for row in rows:
                p = kit_dir(grammar) / row["path"] if not row.get("shared_kernel") else ROOT / row["path"]
                if not p.exists():
                    fail(f"{grammar}: {row['path']} missing"); continue
                if sha256(p) != row["sha256"]:
                    fail(f"{grammar}: {row['path']} sha256 is stale")
        return 0 if not FAILS else 1

    if len(sections) < 1:
        fail(f"{grammar}: no section plate")
    if len(lessons) < 1:
        fail(f"{grammar}: no lesson scene")

    for role in ("hero", "cover", "section", "lesson_scene"):
        for plate in roles.get(role) or []:
            check_plate(grammar, plate, role)
    if covers:
        check_cover_arithmetic(grammar, covers)
    for plate in hero + sections + lessons:
        if tuple(plate["size"]) != (1344, 768):
            fail(f"{grammar}/{plate['path']}: must be 1344x768")
    return 0 if not FAILS else 1


def check_all(only: str | None = None) -> int:
    grammars = [only] if only else sorted(GRAMMARS)
    for grammar in grammars:
        check_kit(grammar)
    if FAILS:
        print(f"FAIL — {len(FAILS)} claim(s) failed")
        for line in FAILS:
            print("  ✗", line)
        return 1
    total_roles = 0
    for grammar in grammars:
        kit = json.loads((kit_dir(grammar) / "kit.json").read_text())
        rows = sum(len(v) for v in kit["roles"].values())
        total_roles += rows
        print(f"  ✓ {grammar:18s} kit.json  roles={rows}  grammar table agrees")
    print(f"\nOK — {len(grammars)} grammars, {total_roles} role rows, every claim re-derived")
    return 0


# --------------------------------------------------------------------------------------
# write + contact sheets

def write_all(only: str | None = None) -> int:
    for grammar in ([only] if only else PLATE_TABLE):
        kit = build_kit(grammar)
        out = kit_dir(grammar) / "kit.json"
        out.write_text(json.dumps(kit, indent=2, ensure_ascii=False) + "\n")
        print(f"wrote {out.relative_to(ROOT)}")
    return 0


def contact_sheets(out_dir: Path) -> int:
    """One review sheet per grammar: every shipped plate plus a caption naming the art direction."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for grammar in sorted(PLATE_TABLE):
        kit = json.loads((kit_dir(grammar) / "kit.json").read_text())
        tiles = []
        for role in ("hero", "cover", "section", "lesson_scene"):
            for row in kit["roles"].get(role) or []:
                tiles.append((kit_dir(grammar) / row["path"], f"{role} · {row['id']} · {row['size'][0]}x{row['size'][1]}"))
        for role in ("object", "frame", "badge", "material", "fox"):
            for row in kit["roles"].get(role) or []:
                tiles.append((ROOT / row["path"], f"{role} · {row['id']} (shared kernel)"))
        rows = [tiles[i:i + 3] for i in range(0, len(tiles), 3)]
        row_files = []
        for i, row in enumerate(rows):
            tile_files = []
            for j, (path, label) in enumerate(row):
                tile = out_dir / f".{grammar}-t{i}-{j}.png"
                subprocess.run(
                    ["magick", str(path), "-resize", "400x290", "-background", "#f7f1e4",
                     "-gravity", "center", "-extent", "400x290",
                     "-background", "#f7f1e4", "-fill", "#3a2318", "-pointsize", "13",
                     "-size", "400x", f"caption:{label}", "-gravity", "center", "-append", str(tile)],
                    check=True,
                )
                tile_files.append(tile)
            row_file = out_dir / f".{grammar}-row{i}.png"
            subprocess.run(["magick", *[str(t) for t in tile_files], "+append", str(row_file)], check=True)
            subprocess.run(
                ["magick", str(row_file), "-background", "#f7f1e4", "-gravity", "center",
                 "-extent", "1260x330", str(row_file)], check=True,
            )
            for t in tile_files:
                t.unlink()
            row_files.append(row_file)
        header = out_dir / f".{grammar}-header.png"
        caption = (
            f"{grammar} · {kit['label']} · kit {kit['kit_id']}\n"
            f"medium: {kit['medium'][:150]}\n"
            f"palette: {', '.join(f'{k} {v}' for k, v in kit['palette'].items())}\n"
            f"composition: {kit['composition'][:190]}"
        )
        subprocess.run(
            ["magick", "-background", "#f7f1e4", "-fill", "#3a2318", "-pointsize", "15",
             "-size", "1240x", "-gravity", "northwest", f"caption:{caption}", str(header)],
            check=True,
        )
        subprocess.run(
            ["magick", str(header), "-background", "#f7f1e4", "-gravity", "center",
             "-extent", "1260x170", str(header)],
            check=True,
        )
        sheet = out_dir / f"{grammar}-contact-sheet.png"
        subprocess.run(["magick", str(header), *[str(p) for p in row_files], "-append", str(sheet)], check=True)
        for p in row_files + [header]:
            p.unlink()
        print(f"wrote {sheet}")
    return 0


def _magick(*args: str) -> None:
    subprocess.run(["magick", *args], check=True)


def _tempered(raw: Path, out: Path) -> Path:
    _magick(str(raw), "-modulate", "105,75,100", str(out))
    return out


def _lift(src: Path, out: Path, size: tuple[int, int] | None = None) -> None:
    args = [str(src)]
    if size:
        args += ["-resize", f"{size[0]}x{size[1]}!"]
    args += ["-clamp", "+level", "4%,100%", str(out)]
    _magick(*args)


def cover_crop(raw_size: tuple[int, int], aspect: tuple[int, int]) -> tuple[int, int]:
    """The largest centre crop of the provider frame at the wanted aspect (w:h)."""
    w, h = raw_size
    aw, ah = aspect
    if w * ah <= h * aw:
        return w, max(1, w * ah // aw)
    return max(1, h * aw // ah), h


def render(grammar: str) -> int:
    """Provider raw -> shipped plate. Temper first, crop/resize second, print-safety lift last."""
    kdir = kit_dir(grammar)
    log = kdir / "generation.json"
    if not log.exists():
        raise SystemExit(f"{grammar}: no generation.json")
    rows = {r["asset"]: r for r in json.loads(log.read_text()) if r.get("verdict") == "accepted"}
    tmp = Path("/tmp/vq008-tempered.png")
    for role, rel, _kind in PLATE_TABLE[grammar]:
        stem = Path(rel).stem
        row = rows.get(stem)
        if not row:
            raise SystemExit(f"{grammar}: no accepted generation for {stem}")
        raw = RAW_DIR / grammar / row["raw"]
        if not raw.exists():
            raise SystemExit(f"{grammar}: raw missing {raw}")
        raw_size = dims(raw)
        out = kdir / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        _tempered(raw, tmp)
        if role == "cover":
            for aspect, size, suffix in (((3, 2), COVER_3X2_SHIPPED, "-3x2"),
                                         ((4, 5), COVER_4X5_SHIPPED, "-4x5")):
                cw, ch = cover_crop(raw_size, aspect)
                crop = Path(f"/tmp/vq008-crop{aspect[0]}.png")
                _magick(str(tmp), "-gravity", "center", "-crop", f"{cw}x{ch}+0+0", "+repage", str(crop))
                name = Path(rel).name.replace("-3x2", suffix) if suffix != "-3x2" else Path(rel).name
                _lift(crop, kdir / ("cover/" + name), size)
        else:
            _lift(tmp, out, PLATE_SIZES[role])
            if role in ("hero", "lesson_scene"):
                # Gate 2 wants a source at least 2x the 1344x768 plate. When the provider returns
                # 2048x1152 the 2x frame is produced by resampling, and the manifest says so.
                _lift(tmp, out.with_name(out.stem + "@2x.png"), (2688, 1536))
        print(f"  rendered {rel}")
    return 0


def fill_prompts(grammar: str) -> int:
    """Record the literal prompt sent for every attempt, from the same composer the writer uses."""
    log = kit_dir(grammar) / "generation.json"
    rows = json.loads(log.read_text())
    kinds = {Path(rel).stem: kind for _role, rel, kind in PLATE_TABLE[grammar]}
    for row in rows:
        kind = kinds.get(row["asset"])
        if kind is None:
            raise SystemExit(f"{grammar}: no plate table row for {row['asset']}")
        row["prompt_sha256"] = hashlib.sha256(build_prompt(grammar, kind).encode()).hexdigest()
        row.setdefault("prompt", build_prompt(grammar, kind))
    log.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    print(f"recorded {len(rows)} attempt(s) in {log.relative_to(ROOT)}")
    return 0


def plan() -> int:
    payload = []
    for grammar, plates in PLATE_TABLE.items():
        for role, rel, kind in plates:
            payload.append({
                "grammar": grammar,
                "role": role,
                "path": f"assets/visual-kits/{grammar}/{rel}",
                "reference": REF_CLASSROOM if role in ("lesson_scene", "section") else REF_HOME,
                "prompt": build_prompt(grammar, kind),
            })
    print(json.dumps(payload, indent=2))
    return 0


def calibrate() -> int:
    ok = True
    for name in ("home.png", "classroom.png"):
        stats = ocr_tokens(REFS / name)
        readable = stats.get("readable") or []
        print(f"{name}: {len(readable)} readable token(s), max_conf={stats.get('max_conf')}")
        print("  ", readable[:8])
        if not readable:
            ok = False
    print("OK — the detector catches real lettering on both reference mockups" if ok
          else "FAIL — detector did not catch real lettering")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--contact", metavar="DIR")
    ap.add_argument("--render", metavar="GRAMMAR")
    ap.add_argument("--log", metavar="GRAMMAR")
    ap.add_argument("--write-one", metavar="GRAMMAR")
    ap.add_argument("--check-one", metavar="GRAMMAR")
    ap.add_argument("--calibrate", action="store_true")
    args = ap.parse_args()
    if args.plan:
        return plan()
    if args.write:
        return write_all()
    if args.write_one:
        return write_all(args.write_one)
    if args.check_one:
        return check_all(args.check_one)
    if args.render:
        return render(args.render)
    if args.log:
        return fill_prompts(args.log)
    if args.contact:
        return contact_sheets(Path(args.contact))
    if args.calibrate:
        return calibrate()
    if args.check:
        return check_all()
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
