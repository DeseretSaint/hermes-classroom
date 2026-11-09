"""Content and print rules for the GM-014 take-home pack.

These tests pin the things the card asks a reviewer to check without needing a browser:

* one target, one context and one success criterion per task;
* no answer key on the learner page (the answer guide is a separate, marked document);
* every phrase, reading, romaji and gloss bound to a cited source and the lesson hash;
* no AI illustration presented as a procedure in the technical sheet;
* low-ink templates, alt text and captions, A4/Letter paper and selectable text.

The committed proof under ``docs/visual-review/gm-014/`` is inspected directly, so a stale or
missing proof fails here rather than being re-described from memory.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from coursebook import homework_print as hp
from tests.test_procedure_document import head_gasket_document

ROOT = Path(__file__).resolve().parent.parent
PROOF_DIR = ROOT / "docs" / "visual-review" / "gm-014"
PROVENANCE = PROOF_DIR / "SOURCE-PROVENANCE.md"
CHECKLIST = PROOF_DIR / "CONTENT-CHECKLIST.md"


def fixture() -> dict:
    return hp.load_fixture()


def sentences(text: str) -> list[str]:
    return [part for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part]


class HomeWorkContentRuleTest(unittest.TestCase):
    def test_fixture_passes_every_content_rule(self) -> None:
        self.assertEqual(hp.validate_fixture(fixture()), [])

    def test_homework_content_has_one_target_and_context(self) -> None:
        data = fixture()
        targets = hp.target_index(data)
        for task in data["tasks"]:
            with self.subTest(task=task["task_id"]):
                # Exactly one target object is named, and it resolves to the lesson.
                self.assertIn(task["target_id"], targets)
                target = targets[task["target_id"]]
                self.assertTrue(target.get("display") or target.get("title"))
                # Exactly one place-and-time context, expressed as a single sentence.
                context = task["context"]
                self.assertIsInstance(context, str)
                self.assertGreater(len(sentences(context)), 0)
                self.assertEqual(len(sentences(context)), 1, context)
                # Exactly one observable success criterion.
                criterion = task["success_criterion"]
                self.assertEqual(len(sentences(criterion)), 1, criterion)
                # At most three steps, 3-10 minutes, and honest completion.
                self.assertTrue(1 <= len(task["steps"]) <= 3)
                self.assertTrue(3 <= int(task["estimated_minutes"]) <= 10)
                self.assertIn(task["completion"], ("self_reported", "parent_reported"))
                # No generic "practise for ten minutes" task.
                self.assertGreater(len(criterion.split()), 6)

    def test_homework_content_has_no_answer_key_on_learner_page(self) -> None:
        data = fixture()
        for task in data["tasks"]:
            with self.subTest(task=task["task_id"]):
                learner = hp.learner_visible_text(
                    hp.render_documents(data, task["task_id"])["learner_page"]
                ).lower()
                self.assertNotIn("parent only", learner)
                self.assertNotIn("answer guide", learner)
                self.assertNotIn("expected response", learner)
                self.assertNotIn("common error", learner)
                self.assertNotIn("answer", learner)
                guide = hp.learner_visible_text(
                    hp.render_documents(data, task["task_id"])["answer_guide"]
                )
                self.assertIn("PARENT ONLY", guide)
                self.assertIn("Do not give this page to the learner", guide)

    def test_homework_content_is_source_bound(self) -> None:
        data = fixture()
        sources = hp.source_index(data)
        self.assertTrue(sources)
        for source_id, source in sources.items():
            with self.subTest(source=source_id):
                self.assertTrue(source["url"].startswith("https://"))
                self.assertRegex(source["accessed"], r"^\d{4}-\d{2}-\d{2}$")
                self.assertTrue(source["quote"].strip())

        for target in data["lesson"]["targets"]:
            for source_id in target["source_ids"]:
                self.assertIn(source_id, sources)
        for label in data["lesson"]["labels"]:
            for source_id in label["source_ids"]:
                self.assertIn(source_id, sources)

        # The hash covers the exact lesson block and changes if a reading changes.
        binding = data["binding"]
        self.assertEqual(binding["source_lesson_hash"], hp.lesson_hash(data["lesson"]))
        mutated = copy.deepcopy(data["lesson"])
        mutated["targets"][0]["reading"] = "いただきまーす"
        self.assertNotEqual(hp.lesson_hash(mutated), binding["source_lesson_hash"])

        # The provenance note records the live hash and every cited URL.
        note = PROVENANCE.read_text(encoding="utf-8")
        self.assertIn(binding["source_lesson_hash"], note)
        self.assertIn(binding["source_course_id"], note)
        self.assertIn(binding["source_lesson_version"], note)
        for source in sources.values():
            self.assertIn(source["url"], note)

    def test_technical_print_has_no_ai_procedure(self) -> None:
        document = head_gasket_document()
        html_text = hp.render_technical_document(document)
        visible = hp.learner_visible_text(html_text)
        self.assertNotIn("<img", html_text)
        self.assertNotIn("<svg", html_text)
        self.assertNotIn("data:image", html_text)
        # No generated-artifact id is printed as if it were a diagram.
        self.assertNotIn("art_torque_seq_001", visible)
        # The structured rows, not a picture, carry the torque facts.
        for row in document["procedure"]["schematic"]["rows"]:
            self.assertIn(row["value"], visible)
        self.assertIn("Deterministic schematic", visible)
        self.assertIn("not an illustration", visible.lower())
        self.assertIn(document["procedure"]["source"]["source_id"], visible)
        self.assertIn("permission: licensed", visible)

    def test_print_templates_are_low_ink_and_use_words_not_colour(self) -> None:
        data = fixture()
        for paper in ("A4", "Letter"):
            docs = hp.render_documents(data, "hw_premeal", paper=paper)
            self.assertIn(f"@page {{ size: {paper}; margin: 0; }}", docs["learner_page"])
            for role, html_text in docs.items():
                with self.subTest(paper=paper, role=role):
                    # Every painted print surface is paper-white; no filled colour panels.
                    print_css = re.sub(r"@media screen \{.*", "", html_text, flags=re.S)
                    backgrounds = set(re.findall(r"background(?:-color)?:\s*(#[0-9a-fA-F]{6})", print_css))
                    self.assertEqual(backgrounds, {"#ffffff"})
                    self.assertNotIn("linear-gradient", print_css)
                    # Meaning is carried by words, not a colour swatch.
                    visible = hp.learner_visible_text(html_text)
                    self.assertIn("Page 1 of", visible)
                    if role == "learner_page":
                        self.assertNotIn("green", visible.lower())
                        self.assertNotIn("red", visible.lower())

    def test_images_have_alt_text_and_a_caption(self) -> None:
        data = fixture()
        html_text = hp.render_documents(data, "hw_labels")["learner_page"]
        self.assertIn('<svg role="img" aria-labelledby="fig1-title fig1-desc"', html_text)
        self.assertIn('<title id="fig1-title">', html_text)
        self.assertIn('<desc id="fig1-desc">', html_text)
        self.assertIn("<figcaption", html_text)
        self.assertIn("Orientation only", html_text)

    def test_answer_guide_is_separate_and_parent_only(self) -> None:
        data = fixture()
        docs = hp.render_documents(data, "hw_premeal")
        self.assertEqual(set(docs), {"parent_guide", "learner_page", "answer_guide", "homework_sheet"})
        self.assertIn("PARENT ONLY · ANSWER GUIDE", docs["answer_guide"])
        self.assertNotIn("PARENT ONLY", docs["learner_page"])
        self.assertNotIn("PARENT ONLY", docs["homework_sheet"])

    def test_content_checklist_records_each_gate(self) -> None:
        checklist = CHECKLIST.read_text(encoding="utf-8")
        for phrase in (
            "one target",
            "one context",
            "one success criterion",
            "no generic task",
            "no surveillance",
            "no grade",
            "no XP",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), checklist.lower())
        data = fixture()
        self.assertFalse(data["checklist"]["generic_task"])
        self.assertFalse(data["checklist"]["surveillance"])
        self.assertFalse(data["checklist"]["grade"])
        self.assertFalse(data["checklist"]["xp"])
        self.assertFalse(data["checklist"]["external_send"])

    def test_learner_pages_ask_for_no_surveillance(self) -> None:
        data = fixture()
        requests = (
            "take a photo",
            "send a photo",
            "record yourself",
            "record a voice",
            "share your location",
            "turn on location",
            "upload",
        )
        for task in data["tasks"]:
            visible = hp.learner_visible_text(
                hp.render_documents(data, task["task_id"])["learner_page"]
            ).lower()
            self.assertIn("no photo, no recording, no location, no score", visible)
            for phrase in requests:
                with self.subTest(task=task["task_id"], phrase=phrase):
                    self.assertNotIn(phrase, visible)


class PrintProofTest(unittest.TestCase):
    """Inspect the committed proof. These run without Chromium."""

    def test_proof_set_exists_for_a4_and_letter(self) -> None:
        manifest_path = PROOF_DIR / "MANIFEST.json"
        self.assertTrue(manifest_path.is_file(), "print proof manifest is missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["fixture"]["source_lesson_hash"], fixture()["binding"]["source_lesson_hash"])
        papers = {entry["paper"] for entry in manifest["documents"]}
        self.assertEqual(papers, {"A4", "Letter"})
        for entry in manifest["documents"]:
            with self.subTest(document=entry["file"]):
                pdf = PROOF_DIR / entry["file"]
                self.assertTrue(pdf.is_file(), f"missing proof: {pdf}")
                info = hp.pdf_info(pdf)
                self.assertEqual(int(info["Pages"]), entry["pages"])
                self.assertTrue(entry["required_text_present"], entry.get("missing_text"))

    def test_pdfs_are_real_paper_with_selectable_japanese(self) -> None:
        if not shutil.which("pdfinfo") or not shutil.which("pdftotext"):
            self.skipTest("pdfinfo/pdftotext not installed")
        manifest = json.loads((PROOF_DIR / "MANIFEST.json").read_text(encoding="utf-8"))
        for entry in manifest["documents"]:
            with self.subTest(document=entry["file"]):
                info = hp.pdf_info(PROOF_DIR / entry["file"])
                width, height = hp.paper_dimensions(entry["paper"])
                self.assertAlmostEqual(float(info["Page size"].split()[0]), width, delta=3.0)
                text = entry.get("required_text") or []
                extracted = re.sub(r"\s+", "", hp.pdf_text(PROOF_DIR / entry["file"]))
                for needle in text:
                    self.assertIn(re.sub(r"\s+", "", needle), extracted)

    def test_committed_bw_proof_is_grayscale_and_legible(self) -> None:
        if not shutil.which("pdftoppm"):
            self.skipTest("pdftoppm not installed")
        manifest = json.loads((PROOF_DIR / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["bw_proofs"], "no black-and-white proof recorded")
        for entry in manifest["bw_proofs"]:
            path = PROOF_DIR / entry["file"]
            self.assertTrue(path.is_file(), f"missing bw proof: {path}")
            self.assertGreater(path.stat().st_size, 10_000, "grayscale page is suspiciously empty")

    def test_html_to_pdf_path_produces_a4_with_embedded_text(self) -> None:
        try:
            hp.chromium_binary()
        except hp.PrintUnavailable:
            self.skipTest("Chromium is not installed")
        data = fixture()
        html_text = hp.render_documents(data, "hw_premeal")["learner_page"]
        with tempfile.TemporaryDirectory(prefix="gm014-test-") as tmp:
            pdf = hp.write_pdf(html_text, Path(tmp) / "learner.pdf")
            info = hp.pdf_info(pdf)
            self.assertEqual(info["Pages"], "1")
            self.assertAlmostEqual(float(info["Page size"].split()[0]), 595.28, delta=3.0)
            text = hp.pdf_text(pdf)
            self.assertIn("いただきます", text)
            self.assertIn("itadakimasu", text)
            self.assertIn("Page 1 of 1", text)
