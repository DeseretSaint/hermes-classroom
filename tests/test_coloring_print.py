"""The colouring page is content, not decoration: these are the rules that make it safe to print.

The page may only draw words the lesson already teaches, it may not carry any text inside the
drawing, its ink must be heavy enough for a crayon and its shapes far enough apart to colour
between, and it may never carry an answer. A pretty page that breaks one of these is a defect, so
each rule is asserted rather than reviewed.
"""

from __future__ import annotations

import re
import unittest

from coursebook import coloring_print as cp
from coursebook import homework_print as hp


def _fixture() -> dict:
    return hp.load_fixture()


class ColouringPageContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = _fixture()

    # -- what it draws -----------------------------------------------------
    def test_it_draws_only_words_the_lesson_teaches(self) -> None:
        task = hp.task_by_id(self.fixture, "hw_labels")
        objects = cp.scene_objects(self.fixture, task)
        self.assertTrue(objects, "a labels task must produce a drawing")
        known = {row["label_id"] for row in self.fixture["lesson"]["labels"]}
        self.assertEqual({obj["id"] for obj in objects} - known, set())

    def test_every_drawn_word_is_recognised_by_the_shape_kit(self) -> None:
        # A word the kit cannot draw gets the plain fallback box, which is honest but must be a
        # deliberate copy of the kit, not a silent regression: the bundled room words all match.
        task = hp.task_by_id(self.fixture, "hw_labels")
        shapes = {obj["shape"] for obj in cp.scene_objects(self.fixture, task)}
        self.assertNotIn("blank", shapes)

    def test_an_unknown_word_falls_back_to_a_colourable_box(self) -> None:
        self.assertEqual(cp.shape_for("flux capacitor"), "blank")
        svg = cp.coloring_svg(
            [{"id": "x", "display": "x", "romaji": "x", "meaning": "flux capacitor", "shape": "blank", "kind": "label"}]
        )
        self.assertIn("<rect", svg)  # the fallback draws, it does not vanish
        self.assertIn("<title", svg)

    def test_scene_order_is_the_fixtures_order(self) -> None:
        task = hp.task_by_id(self.fixture, "hw_labels")
        drawn = [obj["id"] for obj in cp.scene_objects(self.fixture, task)]
        self.assertEqual(drawn, cp._label_set_ids(self.fixture, task))

    # -- print rules -------------------------------------------------------
    def test_stroke_lands_inside_the_two_to_2_6pt_band(self) -> None:
        points = cp.STROKE * cp.PT_PER_UNIT
        self.assertGreaterEqual(points, 2.0, f"{points:.2f} pt is too thin for a crayon")
        self.assertLessEqual(points, 2.6, f"{points:.2f} pt is too heavy and fills the page")

    def test_three_millimetres_between_every_two_separate_objects(self) -> None:
        task = hp.task_by_id(self.fixture, "hw_labels")
        objects = cp.scene_objects(self.fixture, task)
        gap = cp.min_shape_gap(objects)
        self.assertGreaterEqual(
            gap,
            cp.MIN_GAP_UNITS,
            f"closest two objects are {gap:.2f} units = {gap * cp.MM_PER_UNIT:.2f} mm apart",
        )

    def test_the_drawing_carries_no_text_and_no_fill(self) -> None:
        task = hp.task_by_id(self.fixture, "hw_labels")
        svg = cp.coloring_svg(cp.scene_objects(self.fixture, task))
        self.assertNotIn("<text", svg)
        self.assertNotIn("<tspan", svg)
        self.assertIn('fill="none"', svg)
        # One ink only: no second colour anywhere in the drawing.
        self.assertEqual(set(re.findall(r'(?:stroke|fill)="(#[0-9a-fA-F]{6})"', svg)), {cp.INK})

    def test_the_drawing_carries_no_grey_tone_no_gradient_and_no_shadow(self) -> None:
        task = hp.task_by_id(self.fixture, "hw_labels")
        svg = cp.coloring_svg(cp.scene_objects(self.fixture, task))
        # One ink and no fill: every paint value is either the ink stroke or "none". The sibling
        # test only pins six-digit hex, which would let `fill="white"` or a named grey through.
        for attr, value in re.findall(r'(stroke|fill)="([^"]+)"', svg):
            self.assertIn(value, {cp.INK, "none"}, f"{attr}={value!r} is a second paint")
        # A grey tone, gradient, shadow, bitmap or transparency would let the page print as a
        # picture to look at rather than a line drawing to colour. The kit emits none of these;
        # this pins that, so §4a's "no grey tones, gradients, shadows" row is asserted, not prose.
        lowered = svg.lower()
        for needle in ("opacity", "gradient", "filter", "shadow", "<image", "#808080", "gray", "grey"):
            self.assertNotIn(needle, lowered, f"the drawing carries {needle!r}")

    def test_the_figure_is_a_labelled_image_with_every_word_in_its_description(self) -> None:
        task = hp.task_by_id(self.fixture, "hw_labels")
        objects = cp.scene_objects(self.fixture, task)
        svg = cp.coloring_svg(objects)
        self.assertIn('role="img"', svg)
        self.assertIn("cb-coloring-title", svg)
        self.assertIn("cb-coloring-desc", svg)
        desc = cp.scene_description(objects)
        for obj in objects:
            self.assertIn(obj["meaning"].split(";")[0].strip(), desc)

    # -- the document ------------------------------------------------------
    def test_the_page_prints_one_sheet_with_a_word_bank_and_no_answer(self) -> None:
        html_text = cp.render_coloring(self.fixture, "hw_labels")
        self.assertEqual(html_text.count('class="sheet"'), 1)
        self.assertIn('data-role="coloring-page"', html_text)
        self.assertIn("Words in this picture", html_text)
        for word in ("ドア", "まど", "いす", "テーブル", "コップ", "ほん"):
            self.assertIn(word, html_text)
        self.assertNotIn("answer-key", html_text)
        self.assertNotIn("PARENT ONLY", html_text)

    def test_it_renders_identical_bytes_twice(self) -> None:
        first = cp.render_coloring(self.fixture, "hw_labels")
        second = cp.render_coloring(self.fixture, "hw_labels")
        self.assertEqual(first, second)

    def test_both_paper_sizes_are_produced_by_one_template(self) -> None:
        a4 = cp.render_coloring(self.fixture, "hw_labels", paper="A4")
        letter = cp.render_coloring(self.fixture, "hw_labels", paper="Letter")
        self.assertIn('data-paper="A4"', a4)
        self.assertIn('data-paper="Letter"', letter)
        self.assertIn("8.5in", letter)

    def test_it_refuses_an_unknown_paper(self) -> None:
        with self.assertRaises(ValueError):
            cp.render_coloring(self.fixture, "hw_labels", paper="A3")

    # -- the tie-in to the parent guide ------------------------------------
    def test_the_parent_guide_asks_for_the_words_while_the_child_colours(self) -> None:
        guide = hp.render_documents(self.fixture, "hw_labels")["parent_guide"]
        self.assertIn("While they colour", guide)
        for word in ("ドア", "まど", "いす", "テーブル", "コップ", "ほん"):
            self.assertIn(word, guide)

    def test_the_parent_guide_still_prints_two_pages_and_keeps_its_last_sentence(self) -> None:
        guide = hp.render_documents(self.fixture, "hw_labels")["parent_guide"]
        self.assertEqual(guide.count('class="sheet"'), 2)
        self.assertIn("the folio at the foot of each page prints the page number", guide)


class ColouringPrintProof(unittest.TestCase):
    """One real PDF: proves the figure survives the print path and keeps its words as text."""

    def test_the_pdf_keeps_the_page_text_and_prints_one_page(self) -> None:
        fixture = _fixture()
        html_text = cp.render_coloring(fixture, "hw_labels")
        pdf = hp.write_pdf(html_text, "/tmp/cb-coloring-proof.pdf")
        info = hp.pdf_info(pdf)
        self.assertEqual(info["Pages"], "1")
        text = hp.pdf_text(pdf)
        for word in ("Colour it in", "Words in this picture", "ドア", "まど"):
            self.assertIn(word, text)


if __name__ == "__main__":
    unittest.main()
