"""CP-015b: the shelf seeder proves the import, not the archive's file list.

The seeder used to expect a hard-coded four-course shelf and to check only that a title appeared
in ``library.list``. Both were wrong for the capability claim: one exported course could never
satisfy a four-title tuple, and a title on the shelf says nothing about whether the imported course
serves a lesson page with its media. These tests pin the two derivations.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEEDER = ROOT / "scripts" / "seed-demo-shelf.py"


def _load_seeder():
    spec = importlib.util.spec_from_file_location("seed_demo_shelf", SEEDER)
    if spec is None or spec.loader is None:  # pragma: no cover - a missing file is a failure
        raise AssertionError(f"missing seeder: {SEEDER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SeedShelfContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.seeder = _load_seeder()

    def test_expected_titles_come_from_the_archives(self) -> None:
        manifests = [
            {"pack_id": "a", "title": "Sourdough"},
            {"pack_id": "b", "title": "Astronomy"},
            {"pack_id": "c", "title": ""},
        ]
        self.assertEqual(self.seeder.expected_titles(manifests), ["Sourdough", "Astronomy"])
        self.assertEqual(self.seeder.expected_titles([]), [])

    def test_a_page_with_segments_and_no_declared_media_is_clean(self) -> None:
        page = {"segments": [{"short": "x"}], "artifacts": []}
        self.assertEqual(self.seeder.artifact_problems(page, {"media": []}), [])

    def test_a_segmentless_page_is_a_problem(self) -> None:
        problems = self.seeder.artifact_problems({"segments": [], "artifacts": []}, {})
        self.assertTrue(problems)
        self.assertIn("served no segments", problems[0])

    def test_declared_media_that_the_page_does_not_resolve_is_a_problem(self) -> None:
        page = {"segments": [{"short": "x"}], "artifacts": []}
        manifest = {"media": [{"path": "media/plate.png", "section_path": "sections/1.json"}]}
        problems = self.seeder.artifact_problems(page, manifest)
        self.assertEqual(len(problems), 1)
        self.assertIn("resolved no artifact", problems[0])

    def test_declared_media_that_resolves_is_clean(self) -> None:
        page = {"segments": [{"short": "x"}],
                "artifacts": [{"artifact_id": "art_1", "kind": "audio", "mime": "audio/mpeg"}]}
        manifest = {"media": [{"path": "media/plate.png", "section_path": "sections/1.json"}]}
        self.assertEqual(self.seeder.artifact_problems(page, manifest), [])

    def test_the_driver_spelling_is_still_accepted(self) -> None:
        page = {"blocks": [{"short": "x"}], "media": [{"artifact_id": "art_1"}]}
        manifest = {"media": [{"path": "media/plate.png", "section_path": "sections/1.json"}]}
        self.assertEqual(self.seeder.artifact_problems(page, manifest), [])


if __name__ == "__main__":
    unittest.main()
