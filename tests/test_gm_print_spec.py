"""GM-013 print proof: five page roles, two page boxes, and an answer key that is actually separate.

The proof is a real A4 and US-Letter PDF built by ``scripts/build_gm_print_proof.py`` from a print
stylesheet, not a mockup. These tests read the PDFs: page count, page box, per-page extracted text,
and the sentinel that marks the answer key. They re-derive the separation claim instead of trusting
``proof.json``.

What this does NOT prove: that a real pack's prose is correct, that the source lesson is validated,
or that the PDF is tagged (it is not; PDF/UA is GM-014's proof). It proves the page anatomy and the
no-answer-key-on-the-learner-page rule.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRINT = ROOT / "docs" / "gm-visual" / "print"
PROOF = PRINT / "proof.json"
SPEC = ROOT / "docs" / "GM-PRINT-SPEC.md"
BUILDER = ROOT / "scripts" / "build_gm_print_proof.py"

SENTINEL = "\u27e8answer-key\u27e9"
ANSWER_HEADING = "EXPECTED RESPONSE"
PARENT_LABEL = "PARENT ONLY"


def page_text(pdf: Path, page: int) -> str | None:
    if not shutil.which("pdftotext"):
        return None
    done = subprocess.run(
        ["pdftotext", "-f", str(page), "-l", str(page), str(pdf), "-"],
        capture_output=True, text=True, check=False,
    )
    return done.stdout if done.returncode == 0 else None


def pdf_info(pdf: Path) -> dict[str, str]:
    if not shutil.which("pdfinfo"):
        return {}
    done = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=False)
    info = {}
    for line in done.stdout.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            info[key.strip()] = value.strip()
    return info


class TestPrintProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PROOF.is_file():
            raise unittest.SkipTest("print proof not built; run scripts/build_gm_print_proof.py")
        cls.proof = json.loads(PROOF.read_text(encoding="utf-8"))

    def test_both_page_boxes_exist_and_are_the_named_sizes(self):
        for variant, needle in (("a4", "A4"), ("letter", "letter")):
            row = self.proof["pdfs"][variant]
            pdf = ROOT / row["path"]
            self.assertTrue(pdf.is_file(), row["path"])
            self.assertEqual(hashlib.sha256(pdf.read_bytes()).hexdigest(), row["sha256"])
            self.assertEqual(row["pages"], 5, f"{variant} does not have five pages")
            info = pdf_info(pdf)
            if info:
                self.assertIn(needle, info.get("Page size", ""), f"{variant} page box is not {needle}")

    def test_answer_key_is_on_page_three_only(self):
        for variant in ("a4", "letter"):
            pdf = ROOT / self.proof["pdfs"][variant]["path"]
            texts = {n: page_text(pdf, n) for n in range(1, 6)}
            if any(t is None for t in texts.values()):
                self.skipTest("pdftotext not available")
            self.assertNotIn(SENTINEL, texts[1])
            self.assertNotIn(SENTINEL, texts[2], f"{variant}: learner page carries the answer key")
            self.assertIn(SENTINEL, texts[3], f"{variant}: answer guide lost its answer")
            self.assertNotIn(SENTINEL, texts[4])
            self.assertNotIn(SENTINEL, texts[5])

    def test_learner_page_has_no_answer_material_and_no_bleed(self):
        pdf = ROOT / self.proof["pdfs"]["a4"]["path"]
        learner = page_text(pdf, 2)
        answer = page_text(pdf, 3)
        if learner is None or answer is None:
            self.skipTest("pdftotext not available")
        self.assertNotIn(ANSWER_HEADING, learner)
        self.assertIn(ANSWER_HEADING, answer)
        # the regression this proof first caught: a following page's first line leaking into the
        # learner page's bottom margin.
        self.assertNotIn(PARENT_LABEL, learner)
        self.assertIn(PARENT_LABEL, answer)
        for forbidden in ("mastery", "grade:", "score"):
            self.assertNotIn(forbidden, learner.lower())
        # a plate that failed to load prints its alt text; a rendered plate prints nothing
        for page in (2, 5):
            text = page_text(pdf, page)
            if text is None:
                self.skipTest("pdftotext not available")
            self.assertNotIn("Plate: a lantern street", text, f"page {page}: the plate did not render")

    def test_every_page_has_selectable_text(self):
        pdf = ROOT / self.proof["pdfs"]["a4"]["path"]
        for n in range(1, 6):
            text = page_text(pdf, n)
            if text is None:
                self.skipTest("pdftotext not available")
            self.assertGreater(len(text.strip()), 200, f"page {n} has no selectable text")

    def test_page_images_and_manifest_agree(self):
        images = sorted(PRINT.glob("page-*.png"))
        self.assertEqual(len(images), 5)
        self.assertEqual(self.proof["page_image_count"], 5)
        self.assertEqual(self.proof["answer_key_separated"], True)

    def test_stylesheet_declares_both_margins_and_the_six_print_roles(self):
        html = (PRINT / "pack-specimen-a4.html").read_text(encoding="utf-8")
        self.assertIn("size: A4", html)
        self.assertIn("margin: 18mm", html)
        letter = (PRINT / "pack-specimen-letter.html").read_text(encoding="utf-8")
        self.assertIn("size: Letter", letter)
        self.assertIn("margin: 0.70in", letter)
        for role in ("parent guide", "learner page", "answer guide", "sources and provenance", "visual caption"):
            self.assertIn(role, html.lower(), f"page role {role} missing from the proof source")

    def test_spec_and_builder_agree_on_the_proof_path(self):
        spec = SPEC.read_text(encoding="utf-8")
        self.assertIn("build_gm_print_proof.py", spec)
        self.assertIn("A4", spec)
        self.assertIn("Letter", spec)
        self.assertTrue(BUILDER.is_file())
        builder = BUILDER.read_text(encoding="utf-8")
        self.assertIn("print-to-pdf", builder)
        self.assertIn("answer_key_separated", builder)


if __name__ == "__main__":
    unittest.main()
