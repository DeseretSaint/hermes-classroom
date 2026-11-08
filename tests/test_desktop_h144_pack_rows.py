"""H-144: Library pack rows are packs, not course covers.

The Library shelf used `CourseCover`, which paints a 16:9 decorative field, a 40 px Atlas Lamp
seal and a title-derived monogram. Two packs whose titles began with the same two words therefore
showed the same "HL" mark and the same mostly-empty cover; the owner read it as a product logo and
could not tell the rows apart. These source gates keep the pack row compact and keep the seal on
course surfaces only. The live capture is separate evidence.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"
SOURCE = PLUGIN_JS.read_text(encoding="utf-8")


def _function(name: str, end: str) -> str:
    return SOURCE[SOURCE.index(f"function {name}") : SOURCE.index(f"function {end}")]


class PackRowsTest(unittest.TestCase):
    def test_library_does_not_use_a_course_cover(self) -> None:
        library = _function("LibraryView", "planTimingCopy")
        self.assertIn("PackShelfRow", library)
        self.assertNotIn("CourseCover", library)
        self.assertNotIn("SurveyMark", library)
        self.assertNotIn("cbCourseMonogram", library)

    def test_pack_row_has_no_seal_or_monogram(self) -> None:
        row = _function("PackShelfRow", "DeskProgress")
        self.assertNotIn("SurveyMark", row)
        self.assertNotIn("cbCourseMonogram", row)
        self.assertNotIn("data-cb-cover-field", row)
        self.assertNotIn("data-cb-seal", row)
        self.assertIn("data-cb-pack-row", row)

    def test_empty_pack_is_named_and_offers_preview_without_a_path(self) -> None:
        row = _function("PackShelfRow", "DeskProgress")
        self.assertIn("data-cb-pack-empty", row)
        self.assertIn("This pack has no sections yet.", row)
        self.assertIn("Preview it to see the manifest", row)
        # The empty branch returns before CoursePath; a missing pack must not imply progress.
        empty_branch = row[row.index("empty\n        ?"):row.index("        : jsxs('div'")]
        self.assertNotIn("CoursePath", empty_branch)

    def test_pack_row_still_has_one_preview_action(self) -> None:
        row = _function("PackShelfRow", "DeskProgress")
        self.assertEqual(row.count("children: 'Preview'"), 1)
        self.assertNotIn("children: 'Open'", row)


if __name__ == "__main__":
    unittest.main()
