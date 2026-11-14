"""A minimal PDF writer for geometry tests: real text and rules at known coordinates.

The print proof measures PDFs Chromium wrote; a test for that measurement needs a PDF whose glyph
positions are known exactly, including one that is deliberately wrong. Generating it here — a
couple of content streams and an xref table — keeps the test hermetic: no Chromium, no image
encoder, no committed binary fixture whose bytes nobody can read.

``pages`` is a list of pages; each page is a list of operations:

* ``("text", x, y, size, text)`` — one run at that baseline, in PDF user space (bottom-left origin,
  unrotated), so a rotated page's coordinates are the *raw media box* coordinates on purpose.
* ``("line", x0, y0, x1, y1)`` — a hairline rule, for a table the geometry reader can find.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

A4_PORTRAIT = (595.28, 841.89)
LETTER = (612.0, 792.0)


def _escape(text: str) -> str:
    """A PDF literal string. Latin-1 characters go out as octal escapes so they survive as
    PDFDocEncoding (0xB7 stays the middle dot the running copy uses)."""
    out: list[str] = []
    for char in text:
        if char in "\\()":
            out.append("\\" + char)
        elif 32 <= ord(char) < 256:
            out.append(f"\\{ord(char):03o}")
        else:
            out.extend(f"\\{byte:03o}" for byte in char.encode("utf-8"))
    return "(" + "".join(out) + ")"


def _content(ops: Iterable[Sequence[Any]]) -> bytes:
    body: list[str] = []
    for op in ops:
        if op[0] == "text":
            _, x, y, size, text = op
            body.append(f"BT /F1 {size} Tf 1 0 0 1 {x} {y} Tm {_escape(str(text))} Tj ET")
        elif op[0] == "line":
            _, x0, y0, x1, y1 = op
            body.append(f"0.5 w {x0} {y0} m {x1} {y1} l S")
        else:  # pragma: no cover - a typo in a test fixture
            raise ValueError(f"unknown fixture operation {op[0]!r}")
    return "\n".join(body).encode("latin-1")


def build_pdf(
    pages: Sequence[Sequence[Sequence[Any]]],
    *,
    size: tuple[float, float] = A4_PORTRAIT,
    rotation: int = 0,
) -> bytes:
    """Return PDF bytes: one page per entry in *pages*, each drawn at the given *rotation*."""
    width, height = size
    font_id = 3 + 2 * len(pages)
    objects: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{3 + 2 * index} 0 R" for index in range(len(pages)))
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    for index, ops in enumerate(pages):
        content_id = 3 + 2 * index + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] "
            f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> "
            f"/Rotate {rotation} >>".encode()
        )
        stream = _content(ops)
        objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    return bytes(out)


def ruled_table(
    *,
    left: float,
    top: float,
    columns: Sequence[float],
    rows: Sequence[Sequence[str]],
    row_height: float = 22.0,
    font_size: float = 9.5,
) -> list[list[Any]]:
    """Ops for a ruled table: ``rows[0]`` is the header row, each cell left-aligned in its column.

    Rules are what ``pdfplumber``'s default strategy reads a table from, so the geometry — not the
    text spacing — is what makes these cells one row.
    """
    ops: list[list[Any]] = []
    width = columns[-1] - columns[0]
    right = columns[0] + width
    height = row_height * len(rows)
    bottom = top - height
    for index in range(len(rows) + 1):
        y = top - index * row_height
        ops.append(["line", columns[0], y, right, y])
    for edge in (columns[0], *columns[1:], right):
        ops.append(["line", edge, top, edge, bottom])
    for row_index, row in enumerate(rows):
        baseline = top - (row_index + 1) * row_height + 6.0
        for column_index, cell in enumerate(row):
            if not cell:
                continue
            ops.append(["text", columns[column_index] + 3.0, baseline, font_size, cell])
    return ops
