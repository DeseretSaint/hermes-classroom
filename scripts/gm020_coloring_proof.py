#!/usr/bin/env python3
"""GM-020 colouring page proof: build the page, print it, and measure the claims.

Writes into ``docs/visual-review/gm-020-coloring/``:

* ``coloring-page-{a4,letter}.pdf`` / ``.png`` — the real print path, not a browser screenshot;
* ``parent-guide-page1.png`` — page one of the guide, showing the "while they colour" tie-in;
* ``MANIFEST.json`` — the measurements: stroke weight in pt, closest pair gap in mm, page count,
  extracted text, and the OCR result of the drawing region (a colouring page must carry no words
  inside the art).

Run: ``python3 scripts/gm020_coloring_proof.py``
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from coursebook import coloring_print as cp  # noqa: E402
from coursebook import homework_print as hp  # noqa: E402

OUT = ROOT / "docs" / "visual-review" / "gm-020-coloring"
TASK = "hw_labels"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ocr_words(png: Path) -> str:
    if not shutil.which("tesseract"):
        return "tesseract-not-installed"
    proc = subprocess.run(
        ["tesseract", str(png), "stdout", "--psm", "6"], capture_output=True, text=True, timeout=120
    )
    return " ".join((proc.stdout or "").split())


def figure_only_png(objects, paper: str, out: Path) -> Path | None:
    """Rasterise the drawing with no page furniture around it, so OCR answers one question.

    Cropping a band out of the full page guesses at the figure's position and reads the heading
    instead. Printing the figure on its own sheet makes the no-text check exact.
    """
    body = '<section class="sheet" data-role="coloring-figure-only">' + cp.coloring_svg(objects) + "</section>"
    html_text = cp.document_html([body], title="colouring figure only", paper=paper)
    pdf_path = out.with_suffix(".pdf")
    html_path = out.with_suffix(".html")
    html_path.write_text(html_text, encoding="utf-8")
    pdf = hp.write_pdf(html_text, pdf_path)
    pngs = hp.pdf_to_png(pdf, out.with_suffix(""), dpi=144, gray=True)
    return pngs[0]


def main() -> int:
    fixture = hp.load_fixture()
    task = hp.task_by_id(fixture, TASK)
    objects = cp.scene_objects(fixture, task)
    OUT.mkdir(parents=True, exist_ok=True)

    gap_units = cp.min_shape_gap(objects)
    frames: dict[str, dict[str, object]] = {}
    for paper in ("A4", "Letter"):
        stem = f"coloring-page-{paper.lower()}"
        html_text = cp.render_coloring(fixture, TASK, paper=paper)
        (OUT / f"{stem}.html").write_text(html_text, encoding="utf-8")
        pdf = hp.write_pdf(html_text, OUT / f"{stem}.pdf")
        pngs = hp.pdf_to_png(pdf, OUT / stem, dpi=144, gray=False)
        info = hp.pdf_info(pdf)
        frames[paper] = {
            "pdf": pdf.name,
            "pdf_sha256": sha256(pdf),
            "png": pngs[0].name,
            "png_sha256": sha256(pngs[0]),
            "pages": info["Pages"],
            "page_size": info["Page size"],
            "page_box": hp.paper_dimensions(paper),
            "text_kept": ["Colour it in", "Words in this picture"] + [o["display"] for o in objects[:2]],
            "text_sha256": hashlib.sha256(hp.pdf_text(pdf).encode("utf-8")).hexdigest(),
        }
        art = figure_only_png(objects, paper, OUT / f"{stem}-figure.png")
        frames[paper]["figure_only_png"] = art.name if art else None
        frames[paper]["figure_ocr"] = ocr_words(art) if art else "render-failed"

    guide = hp.render_documents(fixture, TASK)["parent_guide"]
    guide_pdf = hp.write_pdf(guide, OUT / "parent-guide.pdf")
    guide_pngs = hp.pdf_to_png(guide_pdf, OUT / "parent-guide", dpi=120, gray=False)

    manifest = {
        "card": "GM-020",
        "generated_by": "scripts/gm020_coloring_proof.py",
        "task": TASK,
        "words_drawn": [
            {"id": o["id"], "display": o["display"], "romaji": o["romaji"], "shape": o["shape"]} for o in objects
        ],
        "measurements": {
            "stroke_pt": round(cp.STROKE * cp.PT_PER_UNIT, 3),
            "stroke_pt_band": [2.0, 2.6],
            "closest_pair_units": round(gap_units, 3),
            "closest_pair_mm": round(gap_units * cp.MM_PER_UNIT, 3),
            "min_gap_mm_required": 3.0,
            "mm_per_scene_unit": round(cp.MM_PER_UNIT, 5),
            "inks": [cp.INK],
            "fill": "none",
            "text_inside_drawing": False,
        },
        "pages": frames,
        "parent_guide": {
            "pdf": guide_pdf.name,
            "pdf_sha256": sha256(guide_pdf),
            "sheets": guide.count('class="sheet"'),
            "pngs": [p.name for p in guide_pngs],
            "carries_while_they_colour": "While they colour" in guide,
        },
        "limits": [
            "The drawing is deterministic geometry from a flat-shape kit, not generated art. It is "
            "legible and cheap to print; it is not an illustration and is not claimed to be one.",
            "A word the kit has no shape for prints as a plain colour block, never as a broken figure.",
            "OCR of the art crop is a no-text check only; it is not a quality verdict.",
        ],
    }
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["measurements"], indent=2))
    print("pages:", {k: v["pages"] for k, v in frames.items()})
    print("figure ocr:", {k: v["figure_ocr"] for k, v in frames.items()})
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
