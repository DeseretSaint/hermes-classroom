"""Measure a printed PDF's glyphs against the page box its stylesheet declares.

This is the seam that turns "the sheet declares 18 mm / 16 mm margins" into a measurement.
``coursebook.homework_print`` prints HTML through Chromium, and until now the print proof only
round-tripped the page's *text* back out with ``pdftotext``: a caption pushed into the margin, or a
table row that spilled past the content box, still contained every word and therefore passed.

What is measured, and why it is measured this way:

* **The display page.** PDF user space is bottom-left origin in points; ``pdfplumber`` reports a
  character's box with a top-down ``top``/``bottom`` pair in the page's *displayed* orientation and
  ``page.width``/``page.height`` already swapped for a ``/Rotate 90`` or ``/Rotate 270`` page. This
  module converts ``mm`` to points explicitly (``PT_PER_MM``), flips ``top``/``bottom`` onto a
  bottom-left origin explicitly, and refuses a rotation it does not understand instead of quietly
  comparing boxes in two different coordinate systems.
* **The layout box, anchored at the pen.** ``pdfplumber``'s ``x0`` is the glyph's advance box;
  ``char["matrix"]`` is ``(a, b, c, d, e, f)`` and ``(e, f)`` is the pen origin in display space on a
  bottom-left origin. The box a margin contract is about is the pen plus one advance width — that is
  what the stylesheet placed. Chromium does position a run's first glyph by the font's proportional
  metrics (``palt`` in the sheet's Japanese face), which can start the pen slightly before the
  column: 30 pt Noto Sans CJK JP starts 3.51 pt early (0.117 em), while the ink it paints begins
  1.8 mm *inside* the margin when the sheet is rasterised. ``GLYPH_BEARING_EM`` covers exactly that
  font placement and nothing else. Rotation changes which axis the advance runs along, handled per
  rotation below.
* **Font furniture is declared, not excused.** A running folio is positioned in the bottom margin
  on purpose (``.folio { bottom: 9mm }``). The caller passes the footer band and the pattern of the
  running copy it printed, so those glyphs are checked against the band they belong to — and any
  other glyph sitting in that band is a violation.

``table_rows`` exposes the same measurement to the syllabus parser: a weekly schedule is a grid,
and a grid read as flat text loses which reading belongs to which week.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

#: One PDF point is 1/72 inch and one inch is 25.4 mm, so a millimetre is 72/25.4 pt = 2.834 645 pt.
PT_PER_MM = 72.0 / 25.4

#: Chromium's A4 raster box is 594.96 x 841.92 pt, a third of a point narrower than 210 mm x 297 mm.
#: That rounding is the only slack the default measurement allows.
ROUNDING_PT = 0.5

#: A run's first glyph is positioned by the font's proportional metrics (``palt`` in the sheet's
#: Japanese face), and the glyph box can therefore begin before the column the stylesheet placed it
#: in: 30 pt Noto Sans CJK JP starts 3.51 pt early, 0.117 em, while the ink it paints begins 1.8 mm
#: *inside* the margin when the sheet is rasterised. That em-fraction is the allowance; it is not a
#: margin tolerance, and it never grows past a fraction of the type size.
GLYPH_BEARING_EM = 0.125

#: Rotations this module understands, in display degrees clockwise.
SUPPORTED_ROTATIONS = (0, 90, 180, 270)

#: Default content-box margins for a sheet that declares none.
ZERO_MARGINS: dict[str, float] = {"top": 0.0, "right": 0.0, "bottom": 0.0, "left": 0.0}


class GeometryUnavailable(RuntimeError):
    """``pdfplumber`` is not installed, so a PDF's glyphs cannot be located."""


class UnsupportedRotation(ValueError):
    """The page carries a rotation this module will not silently mis-measure."""


@dataclass(frozen=True)
class Box:
    """An axis-aligned box in PDF points, bottom-left origin."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)

    def as_mm(self) -> tuple[float, float, float, float]:
        return tuple(round(value / PT_PER_MM, 2) for value in self.as_tuple())  # type: ignore[return-value]

    def overflow(self, other: "Box") -> dict[str, float]:
        """How far this box leaves *other*, per side, in points. Zero or negative means inside."""
        return {
            "left": other.x0 - self.x0,
            "bottom": other.y0 - self.y0,
            "right": self.x1 - other.x1,
            "top": self.y1 - other.y1,
        }


@dataclass(frozen=True)
class FooterBand:
    """The declared band a running folio occupies, in millimetres from the page's own edges."""

    pattern: re.Pattern[str]
    bottom_mm: float
    top_mm: float
    left_mm: float
    right_mm: float

    def box(self, page_width_pt: float, page_height_pt: float) -> Box:
        return Box(
            x0=self.left_mm * PT_PER_MM,
            y0=self.bottom_mm * PT_PER_MM,
            x1=page_width_pt - self.right_mm * PT_PER_MM,
            y1=self.top_mm * PT_PER_MM,
        )


def mm_to_pt(value: float) -> float:
    return float(value) * PT_PER_MM


def _module() -> Any:
    try:  # optional declared dependency
        import logging

        import pdfplumber  # type: ignore

        # pdfminer warns about fonts whose descriptor has no FontBBox; the measurement uses each
        # glyph's advance box from the text matrix, so such a warning changes nothing it reports.
        logging.getLogger("pdfminer").setLevel(logging.ERROR)
        return pdfplumber
    except Exception as exc:  # noqa: BLE001 - absence is a typed refusal, not a crash
        raise GeometryUnavailable(
            "glyph geometry needs the optional pdfplumber dependency, which this build does not have."
        ) from exc


def _open(source: Any) -> Any:
    """Open a PDF from a path *or* from bytes already in memory (syllabus intake holds bytes)."""
    module = _module()
    if isinstance(source, (bytes, bytearray)):
        import io

        return module.open(io.BytesIO(bytes(source)))
    if hasattr(source, "read"):
        return module.open(source)
    return module.open(str(source))


def version() -> str:
    """``pdfplumber <version>``, or ``unavailable`` when the optional dependency is missing."""
    try:
        return f"pdfplumber {_module().__version__}"
    except GeometryUnavailable:
        return "unavailable"


def resolved_rotation(page: Any) -> int:
    """The page's rotation in display degrees clockwise, or a typed refusal."""
    rotation = int(getattr(page, "rotation", 0) or 0) % 360
    if rotation not in SUPPORTED_ROTATIONS:
        raise UnsupportedRotation(
            f"page rotation {rotation} is not one of {SUPPORTED_ROTATIONS}; "
            "the boxes would be compared in two coordinate systems."
        )
    return rotation


def content_box(page: Any, margins_mm: Mapping[str, float] | None = None) -> Box:
    """The declared page box in points, bottom-left origin, *for the displayed page*.

    ``page.width`` / ``page.height`` are the displayed size, so a ``/Rotate 90`` page yields a box
    whose width is the paper's height. The margins are subtracted from that displayed size, which is
    what the stylesheet means: ``@page { margin: 18mm 16mm }`` insets the page the reader sees.
    """
    margins = dict(ZERO_MARGINS)
    for side, value in (margins_mm or {}).items():
        if side not in margins:
            raise ValueError(f"unknown margin side {side!r}; expected top/right/bottom/left")
        margins[side] = float(value)
    width = float(page.width)
    height = float(page.height)
    box = Box(
        x0=mm_to_pt(margins["left"]),
        y0=mm_to_pt(margins["bottom"]),
        x1=width - mm_to_pt(margins["right"]),
        y1=height - mm_to_pt(margins["top"]),
    )
    if box.width <= 0 or box.height <= 0:
        raise ValueError(
            f"margins {margins!r} leave no content box on a {width:.2f} x {height:.2f} pt page"
        )
    return box


def char_layout_box(char: Mapping[str, Any], page: Any) -> Box:
    """The box the *layout* gives a glyph, in points, bottom-left origin, display orientation.

    ``pdfplumber`` reports ``x0``/``x1`` as the glyph's advance box including its side bearing.
    ``char["matrix"]`` is ``(a, b, c, d, e, f)`` and its ``(e, f)`` is the pen origin — the point
    the stylesheet laid the glyph out at — in display space with a bottom-left origin. The layout
    box runs one advance width from that pen along the rotation's advance axis, and takes its
    perpendicular extent from the glyph's ascent/descent band.
    """
    rotation = resolved_rotation(page)
    _a, _b, _c, _d, pen_x, pen_y = char["matrix"]
    width = float(char["width"])
    height = float(page.height)
    top_down_y0 = height - float(char["bottom"])
    top_down_y1 = height - float(char["top"])
    if rotation == 0:
        return Box(float(pen_x), top_down_y0, float(pen_x) + width, top_down_y1)
    if rotation == 180:
        return Box(float(pen_x) - width, top_down_y0, float(pen_x), top_down_y1)
    x0, x1 = float(char["x0"]), float(char["x1"])
    if rotation == 90:  # text runs down the displayed page
        return Box(x0, float(pen_y) - width, x1, float(pen_y))
    return Box(x0, float(pen_y), x1, float(pen_y) + width)  # 270: text runs up the page


def _line_key(char: Mapping[str, Any]) -> float:
    """Group glyphs that share a baseline. Column text and leading are far wider than one point, so
    a whole-point key joins one line's glyphs without joining two adjacent lines."""
    return round(float(char["top"]), 0)


def _line_text(chars: Iterable[Mapping[str, Any]]) -> str:
    return "".join(str(char["text"]) for char in sorted(chars, key=lambda char: float(char["x0"])))


def _violation(*, page_number: int, char: Mapping[str, Any] | None, line: str, box: Box,
               against: Box, against_name: str, over: Mapping[str, float]) -> dict[str, Any]:
    side, amount = max(over.items(), key=lambda item: item[1])
    return {
        "page": page_number,
        "char": str(char["text"]) if char is not None else "",
        "line": line,
        "box": [round(value, 2) for value in box.as_tuple()],
        "box_mm": [round(value, 2) for value in box.as_mm()],
        "against": against_name,
        "against_box": [round(value, 2) for value in against.as_tuple()],
        "against_box_mm": [round(value, 2) for value in against.as_mm()],
        "side": side,
        "over_pt": round(float(amount), 2),
        "over_mm": round(float(amount) / PT_PER_MM, 2),
    }


def describe(violation: Mapping[str, Any]) -> str:
    """One sentence naming the glyph, its bbox and the box it left."""
    char = violation.get("char") or "?"
    line = violation.get("line") or ""
    excerpt = line if len(line) <= 60 else line[:57] + "..."
    return (
        f"page {violation['page']} glyph {char!r} bbox={violation['box']} pt "
        f"({violation['box_mm']} mm) is {violation['over_mm']} mm past the {violation['side']} edge of the "
        f"{violation['against']} {violation['against_box']} pt ({violation['against_box_mm']} mm) "
        f"by {violation['over_pt']} pt; line: {excerpt!r}"
    )


def glyph_violations(
    source: Any,
    *,
    margins_mm: Mapping[str, float] | None = None,
    footer: FooterBand | None = None,
    rounding_pt: float = ROUNDING_PT,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Every glyph whose layout box leaves its declared box, measured from the written PDF.

    A glyph belongs to a footer line when the line it sits on matches ``footer.pattern``; that line
    is then measured against the declared footer band instead of the content box. Anything else
    must sit inside the content box. ``rounding_pt`` absorbs sub-point rounding and each glyph adds
    ``GLYPH_BEARING_EM`` of its own type size for the font's proportional placement; neither is a
    margin allowance.
    """
    violations: list[dict[str, Any]] = []
    with _open(source) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            box = content_box(page, margins_mm)
            band = footer.box(float(page.width), float(page.height)) if footer is not None else None
            lines: dict[float, list[Mapping[str, Any]]] = {}
            for char in page.chars:
                lines.setdefault(_line_key(char), []).append(char)
            for chars in lines.values():
                text = _line_text(chars)
                is_footer = bool(footer is not None and band is not None and footer.pattern.match(text))
                against = band if is_footer and band is not None else box
                against_name = "declared footer band" if against is band else "declared content box"
                for char in chars:
                    if not str(char["text"]).strip():
                        continue
                    laid_out = char_layout_box(char, page)
                    over = laid_out.overflow(against)
                    amount = max(over.values())
                    allowance = rounding_pt + GLYPH_BEARING_EM * float(char.get("size") or 0.0)
                    if amount <= allowance:
                        continue
                    violations.append(_violation(
                        page_number=index, char=char, line=text, box=laid_out,
                        against=against, against_name=against_name, over=over,
                    ))
                    if limit is not None and len(violations) >= limit:
                        return violations
    return violations


def page_geometry(source: Any, margins_mm: Mapping[str, float] | None = None) -> list[dict[str, Any]]:
    """Per-page page box and wording, for a manifest that names what it measured."""
    out: list[dict[str, Any]] = []
    with _open(source) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            box = content_box(page, margins_mm)
            out.append({
                "page": index,
                "width_pt": round(float(page.width), 2),
                "height_pt": round(float(page.height), 2),
                "rotation": resolved_rotation(page),
                "glyphs": sum(1 for char in page.chars if str(char["text"]).strip()),
                "content_box_pt": [round(value, 2) for value in box.as_tuple()],
                "content_box_mm": [round(value, 2) for value in box.as_mm()],
            })
    return out


def measure(
    source: Any,
    *,
    margins_mm: Mapping[str, float] | None = None,
    footer: FooterBand | None = None,
    rounding_pt: float = ROUNDING_PT,
) -> dict[str, Any]:
    """A report a proof can store: pages measured, glyphs located, and every violation found."""
    pages = page_geometry(source, margins_mm)
    violations = glyph_violations(source, margins_mm=margins_mm, footer=footer, rounding_pt=rounding_pt)
    margins = dict(ZERO_MARGINS)
    margins.update({key: float(value) for key, value in (margins_mm or {}).items()})
    return {
        "pdf": str(source) if isinstance(source, (str, Path)) else None,
        "margins_mm": margins,
        "rounding_pt": rounding_pt,
        "footer_band_mm": None if footer is None else {
            "bottom": footer.bottom_mm, "top": footer.top_mm,
            "left": footer.left_mm, "right": footer.right_mm,
        },
        "pages": pages,
        "glyphs": sum(page["glyphs"] for page in pages),
        "violations": violations,
        "inside": not violations,
    }


# ── table geometry (syllabus intake) ───────────────────────────────────────


def _cell_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def page_table_rows(source: Any) -> list[dict[str, Any]]:
    """Every table row that carries at least two non-empty cells, with its geometry.

    Each row is ``{"page", "table", "row", "cells", "text", "bbox"}``. ``text`` joins
    the cells with a tab so a downstream parser can tell "Week 3" from the reading beside it; a
    flat text extraction cannot, which is the whole reason this exists.
    """
    out: list[dict[str, Any]] = []
    with _open(source) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            found = page.find_tables()
            for table_index, table in enumerate(found, start=1):
                row_objects = list(getattr(table, "rows", []) or [])
                for row_index, cells_row in enumerate(table.extract() or []):
                    cells = [_cell_text(cell) for cell in (cells_row or [])]
                    filled = [cell for cell in cells if cell]
                    if len(filled) < 2:
                        continue
                    row_box: Sequence[float] | None = None
                    if row_index < len(row_objects):
                        row_box = row_objects[row_index].bbox
                    out.append({
                        "page": page_index,
                        "table": table_index,
                        "row": row_index,
                        "cells": cells,
                        "text": "\t".join(cells).strip(),
                        "bbox": [round(float(value), 2) for value in (row_box or table.bbox)],
                    })
    return out


def table_rows(source: Any) -> list[str]:
    """Just the row texts, page order preserved."""
    return [row["text"] for row in page_table_rows(source)]
