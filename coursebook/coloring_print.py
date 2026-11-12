"""A coloring page for a take-home pack, built from the lesson's own vocabulary.

Why this module exists
----------------------
A take-home pack that is only text asks a small child to sit still through an adult's script. The
page here gives the child something to do with their hands while the parent asks for the words, and
it stays honest by drawing *only* the vocabulary the lesson already teaches: the scene is composed
from the task's own label set (or its phrase targets), never from invented content.

Why the drawing is deterministic
--------------------------------
The obvious route is to trace a painted lesson plate into line art. That route is rejected here.
Edge extraction on a painterly plate produces dense grey mush, not a colorable drawing -- the
reference staged pipeline (`cbconvert.py`) says as much in its own header and tells you to supply
line art by other means for painterly sources. A second route, generating a plate with an image
model, produces attractive art but cannot be the default: a provider may be absent, and every page
must print. So this module draws the objects itself, from a small flat-shape kit, in the ring
weight and gap geometry a crayon needs:

* one ink, no fills, no grey tones, no gradient;
* effective stroke 2.0-2.6 pt at the printed size (``STROKE`` below is computed, not eyeballed);
* at least 3 mm between two colorable shapes, so a crayon tip fits between them;
* no text inside the drawing -- every word is DOM text under the figure, never baked into the art.

The generated-art lane can be added later behind the same page frame; it has to obey the same
measured rules, so nothing about this page's contract changes when it arrives.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .homework_print import (
    PAPER_SIZES,
    _esc,
    _label_set_ids,
    _masthead,
    _page,
    _task_target,
    _text_with_jp,
    document_html,
    label_index,
    task_by_id,
    target_index,
)

#: Scene units. The figure is printed at the live width of the sheet (174 mm on A4), so one unit
#: is 174/300 mm = 0.58 mm = 1.644 pt. ``STROKE`` is chosen so the printed ink lands inside the
#: 2.0-2.6 pt band with room for rounding in the PDF.
VIEW_W = 300.0
VIEW_H = 250.0
LIVE_WIDTH_MM = 174.0
STROKE = 1.5
INK = "#1a1713"

#: A4/Letter live width is the same by design in the print spec, so one figure geometry serves both.
MM_PER_UNIT = LIVE_WIDTH_MM / VIEW_W
PT_PER_UNIT = MM_PER_UNIT * 72.0 / 25.4

#: The smallest gap a crayon needs between two colorable shapes (3 mm), in scene units.
MIN_GAP_UNITS = 3.0 / MM_PER_UNIT

#: The room scene: a door, a window, a chair, a table and the two things that sit on it. These are
#: the household words an L0 lesson actually teaches, and they compose into one readable room.
ROOM_LAYOUT: dict[str, tuple[float, float, float, float]] = {
    "door": (10.0, 55.0, 66.0, 170.0),
    "window": (200.0, 28.0, 78.0, 96.0),
    "table": (86.0, 150.0, 140.0, 75.0),
    "chair": (238.0, 137.0, 50.0, 88.0),
    "book": (96.0, 122.0, 52.0, 28.0),
    "glass": (158.0, 118.0, 30.0, 32.0),
}

FLOOR_Y = 225.0
WALL_Y = 22.0


# ── the flat-shape kit ─────────────────────────────────────────────────────
# Each function draws one object inside its own box in scene coordinates. Drawing in scene
# coordinates (rather than scaling a 100-unit glyph) keeps every stroke exactly ``STROKE`` wide
# without relying on `vector-effect`, which print engines honour inconsistently.


def _rect(x: float, y: float, w: float, h: float) -> str:
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" />'


def _line(x1: float, y1: float, x2: float, y2: float) -> str:
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" />'


def _door(x: float, y: float, w: float, h: float) -> str:
    return (
        _rect(x, y, w, h)
        + _rect(x + w * 0.18, y + h * 0.10, w * 0.64, h * 0.34)
        + f'<circle cx="{x + w * 0.83:.1f}" cy="{y + h * 0.56:.1f}" r="{w * 0.07:.1f}" />'
    )


def _window(x: float, y: float, w: float, h: float) -> str:
    return (
        _rect(x, y, w, h)
        + _line(x + w / 2, y, x + w / 2, y + h)
        + _line(x, y + h / 2, x + w, y + h / 2)
        + _line(x - w * 0.03, y + h, x + w * 1.03, y + h)
    )


def _table(x: float, y: float, w: float, h: float) -> str:
    top = h * 0.20
    left = x + w * 0.10
    right = x + w * 0.90
    return (
        _rect(x, y, w, top)
        + _line(left, y + top, left, y + h)
        + _line(right, y + top, right, y + h)
        + _line(left, y + h * 0.68, right, y + h * 0.68)
    )


def _chair(x: float, y: float, w: float, h: float) -> str:
    # Side elevation with an *open* backrest: two posts and a top rail. A closed rectangle here
    # reads as a box balanced on a pedestal, which is the one thing a child cannot colour as a chair.
    seat = y + h * 0.44
    return (
        _line(x + w * 0.56, y, x + w * 0.56, seat)
        + _line(x + w * 0.90, y, x + w * 0.90, seat)
        + _line(x + w * 0.56, y + h * 0.04, x + w * 0.90, y + h * 0.04)
        + _rect(x, seat, w * 0.96, h * 0.09)
        + _line(x + w * 0.10, seat + h * 0.09, x + w * 0.10, y + h)
        + _line(x + w * 0.80, seat + h * 0.09, x + w * 0.80, y + h)
    )


def _glass(x: float, y: float, w: float, h: float) -> str:
    rim = y + h * 0.07
    return (
        f'<ellipse cx="{x + w / 2:.1f}" cy="{rim:.1f}" rx="{w * 0.36:.1f}" ry="{h * 0.07:.1f}" />'
        + f'<path d="M {x + w * 0.14:.1f},{rim:.1f} L {x + w * 0.26:.1f},{y + h:.1f} '
        f'L {x + w * 0.74:.1f},{y + h:.1f} L {x + w * 0.86:.1f},{rim:.1f}" />'
    )


def _book(x: float, y: float, w: float, h: float) -> str:
    left = (
        f'<path d="M {x:.1f},{y + h * 0.58:.1f} '
        f'C {x + w * 0.18:.1f},{y + h * 0.28:.1f} {x + w * 0.36:.1f},{y + h * 0.26:.1f} '
        f'{x + w * 0.49:.1f},{y + h * 0.40:.1f} '
        f'L {x + w * 0.49:.1f},{y + h * 0.86:.1f} '
        f'C {x + w * 0.33:.1f},{y + h * 0.72:.1f} {x + w * 0.16:.1f},{y + h * 0.76:.1f} '
        f'{x:.1f},{y + h * 0.92:.1f} Z" />'
    )
    right = (
        f'<path d="M {x + w:.1f},{y + h * 0.58:.1f} '
        f'C {x + w * 0.82:.1f},{y + h * 0.28:.1f} {x + w * 0.64:.1f},{y + h * 0.26:.1f} '
        f'{x + w * 0.51:.1f},{y + h * 0.40:.1f} '
        f'L {x + w * 0.51:.1f},{y + h * 0.86:.1f} '
        f'C {x + w * 0.67:.1f},{y + h * 0.72:.1f} {x + w * 0.84:.1f},{y + h * 0.76:.1f} '
        f'{x + w:.1f},{y + h * 0.92:.1f} Z" />'
    )
    return left + right


def _bowl(x: float, y: float, w: float, h: float) -> str:
    return (
        f'<path d="M {x:.1f},{y + h * 0.30:.1f} '
        f'Q {x + w / 2:.1f},{y + h * 1.24:.1f} {x + w:.1f},{y + h * 0.30:.1f}" />'
        + _line(x, y + h * 0.30, x + w, y + h * 0.30)
        + _line(x + w * 0.34, y + h * 0.92, x + w * 0.66, y + h * 0.92)
    )


def _cup(x: float, y: float, w: float, h: float) -> str:
    return (
        _rect(x + w * 0.10, y + h * 0.16, w * 0.62, h * 0.58)
        + _line(x + w * 0.10, y + h * 0.16, x + w * 0.72, y + h * 0.16)
        + f'<path d="M {x + w * 0.72:.1f},{y + h * 0.26:.1f} '
        f'Q {x + w * 0.98:.1f},{y + h * 0.45:.1f} {x + w * 0.72:.1f},{y + h * 0.64:.1f}" />'
        + _line(x + w * 0.20, y + h * 0.74, x + w * 0.62, y + h * 0.74)
    )


def _plate(x: float, y: float, w: float, h: float) -> str:
    return (
        f'<circle cx="{x + w / 2:.1f}" cy="{y + h / 2:.1f}" r="{min(w, h) * 0.46:.1f}" />'
        + f'<circle cx="{x + w / 2:.1f}" cy="{y + h / 2:.1f}" r="{min(w, h) * 0.28:.1f}" />'
    )


def _chopsticks(x: float, y: float, w: float, h: float) -> str:
    return (
        _line(x + w * 0.22, y + h * 0.08, x + w * 0.46, y + h * 0.92)
        + _line(x + w * 0.44, y + h * 0.04, x + w * 0.70, y + h * 0.88)
    )


def _spoon(x: float, y: float, w: float, h: float) -> str:
    return (
        f'<ellipse cx="{x + w / 2:.1f}" cy="{y + h * 0.26:.1f}" rx="{w * 0.24:.1f}" ry="{h * 0.22:.1f}" />'
        + _line(x + w / 2, y + h * 0.48, x + w / 2, y + h * 0.94)
    )


def _bag(x: float, y: float, w: float, h: float) -> str:
    return (
        _rect(x + w * 0.08, y + h * 0.34, w * 0.84, h * 0.58)
        + f'<path d="M {x + w * 0.30:.1f},{y + h * 0.34:.1f} '
        f'Q {x + w / 2:.1f},{y + h * 0.02:.1f} {x + w * 0.70:.1f},{y + h * 0.34:.1f}" />'
    )


def _shoe(x: float, y: float, w: float, h: float) -> str:
    return (
        f'<path d="M {x + w * 0.06:.1f},{y + h * 0.78:.1f} '
        f'L {x + w * 0.06:.1f},{y + h * 0.40:.1f} '
        f'Q {x + w * 0.44:.1f},{y + h * 0.34:.1f} {x + w * 0.56:.1f},{y + h * 0.58:.1f} '
        f'L {x + w * 0.94:.1f},{y + h * 0.70:.1f} L {x + w * 0.94:.1f},{y + h * 0.78:.1f} Z" />'
        + _line(x + w * 0.06, y + h * 0.78, x + w * 0.94, y + h * 0.78)
    )


def _pencil(x: float, y: float, w: float, h: float) -> str:
    body = f'M {x + w * 0.30:.1f},{y + h * 0.06:.1f} L {x + w * 0.70:.1f},{y + h * 0.06:.1f} ' \
           f'L {x + w * 0.70:.1f},{y + h * 0.72:.1f} L {x + w * 0.50:.1f},{y + h * 0.94:.1f} ' \
           f'L {x + w * 0.30:.1f},{y + h * 0.72:.1f} Z'
    return body + _line(x + w * 0.30, y + h * 0.16, x + w * 0.70, y + h * 0.16)


def _mug_fallback(x: float, y: float, w: float, h: float) -> str:
    """Unknown word: a plain box the child can still colour. Never a broken figure."""
    return _rect(x + w * 0.10, y + h * 0.10, w * 0.80, h * 0.80)


SHAPES = {
    "door": _door,
    "window": _window,
    "table": _table,
    "chair": _chair,
    "glass": _glass,
    "book": _book,
    "bowl": _bowl,
    "cup": _cup,
    "plate": _plate,
    "chopsticks": _chopsticks,
    "spoon": _spoon,
    "bag": _bag,
    "shoe": _shoe,
    "pencil": _pencil,
}

#: Word -> shape. Matched on the label's meaning, then its romaji, then its display form. Only the
#: first match wins, so the table stays readable; a word that matches nothing gets the plain box.
KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("door", "gate"), "door"),
    (("window",), "window"),
    (("table", "desk"), "table"),
    (("chair", "seat", "stool"), "chair"),
    (("glass", "tumbler", "cup of water"), "glass"),
    (("book", "notebook"), "book"),
    (("bowl", "dish", "rice"), "bowl"),
    (("cup", "mug", "teacup", "tea"), "cup"),
    (("plate",), "plate"),
    (("chopstick",), "chopsticks"),
    (("spoon", "fork", "cutlery"), "spoon"),
    (("bag", "satchel", "backpack"), "bag"),
    (("shoe", "sneaker", "boot"), "shoe"),
    (("pencil", "pen", "brush"), "pencil"),
)


def shape_for(meaning: str, romaji: str = "", display: str = "") -> str:
    haystack = f"{meaning} {romaji} {display}".lower()
    for words, shape in KEYWORDS:
        if any(word in haystack for word in words):
            return shape
    return "blank"


# ── the object set ─────────────────────────────────────────────────────────


def scene_objects(fixture: Mapping[str, Any], task: Mapping[str, Any]) -> list[dict[str, str]]:
    """The words this page draws: the task's label set, else the lesson's phrase targets.

    Ordering is the fixture's own, so the same lesson always prints the same page.
    """
    target = _task_target(fixture, task)
    labels = label_index(fixture)
    chosen: list[dict[str, str]] = []
    if target.get("kind") == "label_set":
        for label_id in _label_set_ids(fixture, task):
            row = labels.get(label_id)
            if not row:
                continue
            chosen.append(
                {
                    "id": label_id,
                    "display": row["display"],
                    "romaji": row["romaji"],
                    "meaning": row["meaning"],
                    "shape": shape_for(row["meaning"], row["romaji"], row["display"]),
                    "kind": "label",
                }
            )
    if not chosen:
        for target_id in target.get("target_ids") or []:
            row = target_index(fixture).get(target_id)
            if not row:
                continue
            chosen.append(
                {
                    "id": target_id,
                    "display": row["display"],
                    "romaji": row["romaji"],
                    "meaning": row["meaning"],
                    "shape": shape_for(row["meaning"], row["romaji"], row["display"]),
                    "kind": "phrase",
                }
            )
    return chosen


# ── layout ─────────────────────────────────────────────────────────────────


def _room_boxes(objects: Sequence[Mapping[str, str]]) -> list[tuple[str, tuple[float, float, float, float]]]:
    return [(str(o["shape"]), ROOM_LAYOUT[o["shape"]]) for o in objects if o["shape"] in ROOM_LAYOUT]


def _grid_boxes(objects: Sequence[Mapping[str, str]]) -> list[tuple[str, tuple[float, float, float, float]]]:
    """Two rows of three large cells for word sets that do not compose a room."""
    cell_w, cell_h = 86.0, 74.0
    origin_x, origin_y = 12.0, 22.0
    boxes = []
    for index, obj in enumerate(objects[:6]):
        row, col = divmod(index, 3)
        boxes.append(
            (
                str(obj["shape"]),
                (origin_x + col * (cell_w + 12.0), origin_y + row * (cell_h + 18.0), cell_w, cell_h),
            )
        )
    return boxes


def layout_boxes(objects: Sequence[Mapping[str, str]]) -> list[tuple[str, tuple[float, float, float, float]]]:
    room = _room_boxes(objects)
    if len(room) == len(objects) and room:
        return room
    return _grid_boxes(objects)


def min_shape_gap(objects: Sequence[Mapping[str, str]]) -> float:
    """The smallest edge-to-edge distance between two drawn objects, in scene units.

    Objects that sit on a surface are allowed to touch that surface (``table`` carries ``glass``);
    the rule this measures is the distance between two *separate* objects, which is what a crayon
    has to fit into.
    """
    boxes = layout_boxes(objects)
    carriers = {"table"}

    def resting_on(lo: tuple[float, ...], hi: tuple[float, ...]) -> bool:
        """True when `lo`'s bottom sits on `hi`'s top: a glass on a table is one object, not two."""
        return abs((lo[1] + lo[3]) - hi[1]) <= 1.0

    worst = float("inf")
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            (shape_a, a), (shape_b, b) = boxes[i], boxes[j]
            if shape_a in carriers and shape_b not in carriers and resting_on(b, a):
                continue
            if shape_b in carriers and shape_a not in carriers and resting_on(a, b):
                continue
            dx = max(0.0, max(a[0], b[0]) - min(a[0] + a[2], b[0] + b[2]))
            dy = max(0.0, max(a[1], b[1]) - min(a[1] + a[3], b[1] + b[3]))
            worst = min(worst, max(dx, dy))
    return worst


# ── drawing ────────────────────────────────────────────────────────────────


def scene_title(objects: Sequence[Mapping[str, str]]) -> str:
    words = ", ".join(obj["meaning"].split(";")[0].strip() for obj in objects)
    return f"Line drawing: {words}"


def scene_description(objects: Sequence[Mapping[str, str]]) -> str:
    if not objects:
        return "An empty page with a frame to colour in."
    words = "; ".join(f"{obj['display']} ({obj['romaji']}), {obj['meaning']}" for obj in objects)
    return (
        "A room drawn in outline with one large shape for each word in this lesson: "
        + words
        + ". Colour each shape in, then say the word for it."
    )


def coloring_svg(objects: Sequence[Mapping[str, str]], *, figure_id: str = "cb-coloring") -> str:
    """One ink, no fills, no text. The figure is decorative for a screen reader only as a whole:
    ``role="img"`` with a title and a description that names every word, and the word bank under
    the figure carries the same words as real text."""
    boxes = layout_boxes(objects)
    parts = [
        f'<svg class="coloring-figure" viewBox="0 0 {VIEW_W:.0f} {VIEW_H:.0f}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-labelledby="{figure_id}-title {figure_id}-desc" '
        f'fill="none" stroke="{INK}" stroke-width="{STROKE}" '
        f'stroke-linecap="round" stroke-linejoin="round">',
        f'<title id="{figure_id}-title">{_esc(scene_title(objects))}</title>',
        f'<desc id="{figure_id}-desc">{_esc(scene_description(objects))}</desc>',
        # The room the words belong to: a wall line and a floor line, nothing else. Those two
        # lines are what make six separate objects read as one place a child can colour, and they
        # are what stop the window reading as a calendar hung in mid-air.
        _line(6.0, WALL_Y, VIEW_W - 6.0, WALL_Y),
        _line(6.0, FLOOR_Y, VIEW_W - 6.0, FLOOR_Y),
    ]
    for shape, (x, y, w, h) in boxes:
        draw = SHAPES.get(shape, _mug_fallback)
        parts.append(draw(x, y, w, h))
    parts.append("</svg>")
    return "".join(parts)


# ── the page ───────────────────────────────────────────────────────────────


def _short_meaning(meaning: str) -> str:
    """The word a child needs, not the dictionary sense with its parenthetical."""
    head = meaning.split(";")[0].split("(")[0].strip()
    return head or meaning


def _word_bank(objects: Sequence[Mapping[str, str]]) -> str:
    if not objects:
        return ""
    cells = []
    for obj in objects:
        cells.append(
            '<li class="word-cell">'
            f'<span class="word-jp jp" lang="ja">{_esc(obj["display"])}</span>'
            f'<span class="word-romaji">{_esc(obj["romaji"])}</span>'
            f'<span class="word-meaning">{_esc(_short_meaning(obj["meaning"]))}</span>'
            "</li>"
        )
    return (
        '<h2 class="word-bank-head">Words in this picture</h2>'
        '<ul class="word-bank">' + "".join(cells) + "</ul>"
    )


def _coloring_page(fixture: Mapping[str, Any], task: Mapping[str, Any], paper: str) -> str:
    objects = scene_objects(fixture, task)
    parts = [
        _masthead("Coursebook · take-home pack · colouring page", "Colour it in"),
        "<p>Colour the picture. As you colour each thing, say its word out loud.</p>",
        '<figure class="coloring-sheet">'
        + coloring_svg(objects)
        + '<figcaption>Line drawing made from this lesson’s own words. '
        "One colour, thick outlines, large areas to fill.</figcaption>"
        "</figure>",
        _word_bank(objects),
        '<p class="quiet">Colouring is the activity, not a reward and not a test. '
        "Nothing here is marked, scored or sent anywhere.</p>",
    ]
    return _page(
        "".join(parts),
        role="coloring-page",
        paper=paper,
        index=1,
        total=1,
        running="Coursebook · colouring page",
    )


_COLORING_CSS = """
/* The shared sheet stylesheet caps every `figure svg` at 34 mm, which is right for the label
   diagram and wrong here: a colouring page is the page. Override at higher specificity rather
   than loosening the shared rule. */
.coloring-sheet { margin: 3mm 0 2mm; }
.coloring-sheet .coloring-figure { display: block; width: 100%; height: auto; max-height: none; }
.word-bank-head { margin-top: 4mm; }
.word-bank { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(3, 1fr); gap: 3mm 6mm; }
.word-cell { display: flex; flex-direction: column; border-top: 0.75pt solid #1a1713; padding-top: 1.2mm; }
.word-jp { font-size: 14pt; line-height: 1.2; }
.word-romaji { font-style: italic; font-size: 9.5pt; color: #1a1713; }
.word-meaning { font-size: 8.5pt; color: #5c5347; }
"""


def render_coloring(fixture: Mapping[str, Any], task_id: str, *, paper: str = "A4") -> str:
    """One-page coloring document for a homework task, as complete HTML.

    Kept out of :func:`homework_print.render_documents` on purpose: that function's four keys are a
    frozen contract (`test_homework_content_print` pins the exact set), so the coloring page is a
    separate door until the take-home pack spec amendment lands.
    """
    if paper not in PAPER_SIZES:
        raise ValueError(f"paper must be one of {sorted(PAPER_SIZES)}")
    task = task_by_id(fixture, task_id)
    lesson = fixture["lesson"]
    title = f"{lesson['title']} — {task['title']} — colouring page"
    html_text = document_html([_coloring_page(fixture, task, paper)], title=title, paper=paper)
    # The page's own classes ride in after the shared sheet stylesheet, so the sheet contract
    # (page box, margins, folio) is untouched.
    return html_text.replace("</style>", _COLORING_CSS + "</style>", 1)


def parent_ask_line(fixture: Mapping[str, Any], task_id: str) -> str:
    """The one sentence page 1 of the parent guide gains when a coloring page ships."""
    task = task_by_id(fixture, task_id)
    objects = scene_objects(fixture, task)
    if not objects:
        return ""
    words = " · ".join(obj["display"] for obj in objects)
    return (
        "<h2>While they colour</h2>"
        "<p>Print the colouring page with this pack. As the child colours, point and ask for each "
        f'word: <span class="jp" lang="ja">{_esc(words)}</span>. '
        "Ask for the word, never a translation. Colouring keeps the hands busy while the mouth works."
        "</p>"
    )
