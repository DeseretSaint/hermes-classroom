"""UP-48: the print proof measures the page box it declares, glyph by glyph.

``docs/visual-review/gm-014`` is the shipped print proof: real A4 and US-Letter PDFs written by
headless Chromium from ``coursebook/homework_print.py``. Before this test the proof only proved that
the page's *text* survived ``pdftotext``, so a caption pushed into the margin and a table row that
spilled past the content box both passed: every word was still there.

These cases read PDFs — the committed proof sheets and fixtures built in ``tests/print_pdf_fixture.py``
— and compare each glyph's layout box with the box the sheet declares:

* the overflowing fixture fails, naming the offending glyph's bbox and the box it left;
* the shipped sheets pass, including their footers, which are declared to live in the bottom margin;
* the conversion and the rotation handling are exercised, because a PDF point is 1/72 inch on a
  bottom-left origin and a rotated page's raw media box is not the page a reader sees.

What this does NOT prove: that Chromium's own layout is correct, that a printer honours the margin,
or anything about a page that was never printed. It measures the written PDF, not the on-screen
sheet.
"""

from __future__ import annotations

import io
import unittest
from pathlib import Path

from coursebook import homework_print as hp
from coursebook import print_geometry, syllabus

from tests.print_pdf_fixture import A4_PORTRAIT, build_pdf, ruled_table

ROOT = Path(__file__).resolve().parent.parent
PROOF = ROOT / "docs" / "visual-review" / "gm-014"

A4_MARGINS = {"top": 18.0, "right": 16.0, "bottom": 16.0, "left": 16.0}
A4_FOOTER = print_geometry.FooterBand(
    pattern=__import__("re").compile(hp.FOLIO_LINE_PATTERN),
    bottom_mm=hp.FOLIO_BOTTOM_MM, top_mm=A4_MARGINS["bottom"],
    left_mm=A4_MARGINS["left"], right_mm=A4_MARGINS["right"],
)


class PrintGeometryTest(unittest.TestCase):
    def test_a_caption_in_the_margin_fails_with_its_bbox(self) -> None:
        """A sheet whose caption sits in the bottom margin fails, and says which box it left."""
        pdf = build_pdf([[
            ["text", 60, 700, 12, "Body sentence that sits inside the content box."],
            ["text", 60, 26, 8.5, "Coursebook · learner page"],   # the declared folio, in its band
            ["text", 505, 26, 8.5, "Page 1 of 1"],
            ["text", 60, 40, 9, "Figure 1 · caption pushed into the margin"],
        ]])

        violations = print_geometry.glyph_violations(pdf, margins_mm=A4_MARGINS, footer=A4_FOOTER)

        self.assertTrue(violations, "a caption 40 pt from the paper edge is inside the 16 mm margin")
        captions = [entry for entry in violations if "caption" in entry["line"]]
        self.assertTrue(captions, f"the caption line should be the failure, got {violations!r}")
        first = captions[0]
        self.assertEqual(first["side"], "bottom")
        self.assertEqual(first["against"], "declared content box")
        self.assertGreater(first["over_pt"], 2.0)
        message = print_geometry.describe(first)
        self.assertIn(str(first["box"]), message)
        self.assertIn("declared content box", message)
        self.assertIn("page 1", message)
        # The folio in its declared band is not a violation.
        self.assertFalse([entry for entry in violations if "Coursebook" in entry["line"]])

    def test_the_folio_band_only_excuses_the_running_line(self) -> None:
        """A line sitting in the folio's band but not matching it is measured as body text."""
        caption_in_the_band = build_pdf([[
            ["text", 60, 700, 12, "Body"],
            ["text", 60, 30, 8.5, "not the folio"],
        ]])
        violations = print_geometry.glyph_violations(
            caption_in_the_band, margins_mm=A4_MARGINS, footer=A4_FOOTER
        )
        self.assertTrue(violations, "the band must only excuse the running line it declares")
        self.assertEqual({entry["line"] for entry in violations}, {"not the folio"})
        self.assertTrue(all(entry["against"] == "declared content box" for entry in violations))

    def test_the_shipped_proof_sheets_keep_every_glyph_inside_the_declared_box(self) -> None:
        """Every page of the committed proof passes, measured from the written PDFs."""
        sheets = sorted(PROOF.rglob("*.pdf"))
        self.assertTrue(sheets, f"the print proof is missing from {PROOF}")
        measured = 0
        for sheet in sheets:
            paper = "Letter" if sheet.parent.name == "letter" else "A4"
            with self.subTest(sheet=str(sheet.relative_to(ROOT))):
                margins = hp.paper_margins(paper)
                report = print_geometry.measure(sheet, margins_mm=margins, footer=hp.folio_footer(paper))
                if report["violations"]:
                    self.fail(
                        f"{sheet.name}: {len(report['violations'])} glyph(s) outside the declared box; "
                        + print_geometry.describe(report["violations"][0])
                    )
                self.assertGreater(report["glyphs"], 0, f"{sheet.name}: no glyph was located")
                measured += report["glyphs"]
        self.assertGreater(measured, 10_000, "the proof should hold thousands of locatable glyphs")

    def test_the_declared_margins_come_from_the_sheet_not_from_the_test(self) -> None:
        """``paper_margins`` parses the stylesheet's own padding shorthand."""
        self.assertEqual(hp.PAPER_SIZES["A4"]["pad"], "18mm 16mm 16mm")
        self.assertEqual(hp.paper_margins("A4"), A4_MARGINS)
        self.assertAlmostEqual(hp.paper_margins("Letter")["left"], 0.65 * 25.4, places=6)
        self.assertAlmostEqual(hp.paper_margins("Letter")["top"], 0.7 * 25.4, places=6)
        self.assertEqual(print_geometry.mm_to_pt(16.0), 16 * 72 / 25.4)
        self.assertAlmostEqual(print_geometry.mm_to_pt(25.4), 72.0, places=6)

    def test_a_rotated_page_is_measured_in_the_page_a_reader_sees(self) -> None:
        """Rotation is handled explicitly: the displayed page is measured, not the raw media box."""
        # A4 rotated 90° clockwise is displayed 841.89 x 595.28 pt. Raw user-space (46, 400) puts the
        # pen at display (400, 549.28) — inside every horizontal margin, but 5 pt above the displayed
        # page's top content edge, because the raw x axis becomes the display's y axis.
        rotated = build_pdf([[
            ["text", 46, 400, 12, "SAT"],  # deliberate sentinel, not a learner word
        ]], rotation=90)

        raw_box = print_geometry.Box(45.35, 45.35, 595.28 - 45.35, 841.89 - 51.02)
        self.assertTrue(
            raw_box.x0 < 46 < raw_box.x1 and raw_box.y0 < 400 < raw_box.y1,
            "the sentinel must look inside the raw media box for this test to bite",
        )

        violations = print_geometry.glyph_violations(rotated, margins_mm=A4_MARGINS)

        self.assertTrue(violations, "measuring a rotated page in raw media-box coordinates would pass")
        self.assertEqual(violations[0]["page"], 1)
        self.assertEqual(violations[0]["char"], "S")
        self.assertEqual(violations[0]["side"], "top")
        geometry = print_geometry.page_geometry(rotated, A4_MARGINS)
        self.assertEqual(geometry[0]["rotation"], 90)
        self.assertAlmostEqual(geometry[0]["width_pt"], A4_PORTRAIT[1], places=1)
        self.assertAlmostEqual(geometry[0]["height_pt"], A4_PORTRAIT[0], places=1)

    def test_a_glyph_inside_the_rotated_box_still_passes(self) -> None:
        """Rotation handling is not a blanket failure: a correctly placed rotated glyph passes."""
        inside = build_pdf([[["text", 300, 100, 12, "Body"]]], rotation=90)
        self.assertEqual(
            print_geometry.glyph_violations(inside, margins_mm=A4_MARGINS), []
        )
        geometry = print_geometry.page_geometry(inside, A4_MARGINS)
        self.assertEqual(geometry[0]["rotation"], 90)

    def test_an_unknown_rotation_is_refused_rather_than_mismeasured(self) -> None:
        odd = build_pdf([[["text", 100, 100, 12, "Body"]]], rotation=45)
        with self.assertRaises(print_geometry.UnsupportedRotation):
            print_geometry.glyph_violations(odd, margins_mm=A4_MARGINS)


class SyllabusTableGeometryTest(unittest.TestCase):
    """The syllabus parser reads a weekly schedule as rows, not as run-on page text."""

    def _schedule_pdf(self) -> bytes:
        weeks = ruled_table(
            left=60, top=720,
            columns=[60, 170, 300, 430, 540],
            rows=[
                ["Week", "Topic", "Readings", "Assessment"],
                ["Week 1", "Greetings", "Chapter 1", "Quiz 1 (5%) 2026-02-10"],
                ["Week 2", "Numbers", "Chapter 2", ""],
            ],
        )
        return build_pdf([[
            ["text", 60, 780, 14, "CS 340 - Databases"],
            *weeks,
            ["text", 60, 640, 10, "Instructor: Ada Lovelace"],
        ]])

    def test_a_weekly_schedule_row_keeps_its_cells_together(self) -> None:
        pdf = self._schedule_pdf()
        rows = print_geometry.table_rows(pdf)
        self.assertIn("Week 1\tGreetings\tChapter 1\tQuiz 1 (5%) 2026-02-10", rows)
        self.assertIn("Week 2\tNumbers\tChapter 2", [row.rstrip("\t") for row in rows])

        blocks = syllabus.extract_blocks("pdf", pdf)
        for ordinal, block in enumerate(blocks, start=1):  # parse_stored assigns these too
            block["id"] = f"blk_{ordinal}"
            block["ordinal"] = ordinal
        row_blocks = [block for block in blocks if "\t" in block["text"]]
        self.assertTrue(row_blocks, f"no table row survived extraction: {[b['text'] for b in blocks]!r}")
        self.assertTrue(
            any(block["text"].startswith("Week 1\t") for block in row_blocks),
            "the week and its reading must stay in one block",
        )

        document = syllabus.parse_document(blocks, source_kind="pdf")
        self.assertTrue(document["weeks"], f"no week parsed from {[b['text'] for b in blocks]!r}")
        first = document["weeks"][0]
        self.assertEqual(first["ordinal"]["value"], 1)
        self.assertEqual(first["topic"]["value"], "Greetings")
        self.assertTrue(first["readings"], "the reading beside week 1 must not be lost")
        self.assertIn("Chapter 1", first["readings"][0]["value"])
        self.assertTrue(first["assessments"], "the quiz beside week 1 must not be lost")
        assessment = first["assessments"][0]
        self.assertEqual(assessment["title"]["value"], "Quiz 1")
        self.assertEqual(assessment["weight"]["value"], 5.0)
        self.assertEqual(assessment["due"]["value"], "2026-02-10")

    def test_prose_outside_the_table_still_arrives(self) -> None:
        blocks = syllabus.extract_blocks("pdf", self._schedule_pdf())
        texts = [block["text"] for block in blocks]
        self.assertTrue(any("CS 340" in text for text in texts), texts)
        self.assertTrue(any("Ada Lovelace" in text for text in texts), texts)
        # The table's own words must not also arrive as prose lines: that would duplicate items.
        self.assertEqual(len([text for text in texts if text.strip() == "Greetings"]), 0, texts)

    def test_the_flat_text_fallback_still_parses_a_pdf(self) -> None:
        """Without pdfplumber the shipped pypdf page-text path still returns blocks."""
        pdf = self._schedule_pdf()
        original = syllabus._pdfplumber_module
        syllabus._pdfplumber_module = lambda: None
        try:
            blocks = syllabus.extract_blocks("pdf", pdf)
        finally:
            syllabus._pdfplumber_module = original
        self.assertTrue(blocks)
        self.assertTrue(all("\t" not in block["text"] for block in blocks))
        self.assertTrue(any("Week 1" in block["text"] for block in blocks))


if __name__ == "__main__":
    unittest.main()
