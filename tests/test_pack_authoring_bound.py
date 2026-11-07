"""R2: one lesson section is bounded at 4,000,000 characters, warned at authoring.

``cb.rpc`` v7 caps one ``lesson.page`` segment at 8,000 characters and one page at 500 segments, so
500 x 8,000 = 4,000,000 characters is the most a single lesson section can carry. That bound is
derived from the contract, never a second constant. Authoring warns with the file and its measured
length; import owns the refusal. These tests pin the derivation, the silent acceptance at the
bound, the warning one character over (validator and export), and the pre-write import refusal.
"""

from __future__ import annotations

import unittest
import warnings
from unittest import mock

from coursebook import archive, packs, segments
from tests.test_pack_flow import PackFlowCase
from tests.test_segment_cap import manifest_for, section_text

PATH = "content/chapter-one.md"


class BoundDerivationTest(unittest.TestCase):
    def test_the_bound_is_the_contract_product(self) -> None:
        limit, budget = segments.lesson_page_caps()
        self.assertEqual(segments.lesson_section_char_bound(), limit * budget)
        self.assertEqual(segments.lesson_section_char_bound(), 4_000_000)

    def test_the_bound_follows_the_contract_rather_than_a_second_constant(self) -> None:
        with mock.patch.object(segments, "lesson_page_caps", return_value=(4_000, 100)):
            self.assertEqual(segments.lesson_section_char_bound(), 400_000)

    def test_the_manifest_file_ceiling_is_a_separate_bound(self) -> None:
        # The 32 MiB per-file limit is a decompression/security bound, not the readability bound.
        self.assertEqual(packs.limits()["max_single_file_bytes"], 33_554_432)
        self.assertNotEqual(segments.lesson_section_char_bound(), packs.limits()["max_single_file_bytes"])


class AuthoringBoundaryTest(unittest.TestCase):
    def test_a_section_at_the_bound_is_accepted_and_not_warned(self) -> None:
        bound = segments.lesson_section_char_bound()
        text = section_text(bound)
        manifest = manifest_for({PATH: text.encode("utf-8")})
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.assertEqual(packs.authoring_warnings(manifest, {PATH: text.encode("utf-8")}), [])
            packs.build_export(manifest, {PATH: text.encode("utf-8")})
        raised = [item for item in caught if issubclass(item.category, packs.PackAuthoringWarning)]
        self.assertEqual(raised, [], "a section exactly at the bound must not warn")

    def test_one_character_over_is_warned_by_the_validator_and_the_export_path(self) -> None:
        bound = segments.lesson_section_char_bound()
        text = section_text(bound + 1)
        manifest = manifest_for({PATH: text.encode("utf-8")})
        expected_length = f"{len(text):,}"

        found = packs.authoring_warnings(manifest, {PATH: text.encode("utf-8")})
        self.assertEqual(len(found), 1)
        self.assertIn(PATH, found[0])
        self.assertIn(expected_length, found[0])
        self.assertIn(f"{bound:,}", found[0])
        self.assertIn("check prompts", found[0])

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            packs.build_export(manifest, {PATH: text.encode("utf-8")})
        raised = [item for item in caught if issubclass(item.category, packs.PackAuthoringWarning)]
        self.assertEqual(len(raised), 1, f"export must warn once: {[str(item.message) for item in raised]}")
        self.assertIn(PATH, str(raised[0].message))
        self.assertIn(expected_length, str(raised[0].message))


class ImportRefusalTest(PackFlowCase):
    """One character over the authoring bound: warned at preview, refused before any write."""

    def test_one_character_over_is_warned_at_preview_and_refused_at_import(self) -> None:
        bound = segments.lesson_section_char_bound()
        text = section_text(bound + 1)
        section_bytes = {PATH: text.encode("utf-8")}
        manifest = manifest_for(section_bytes)
        destination = self.work / "authoring-bound.zip"
        archive.write_archive(destination, manifest, section_bytes)
        staged_id = self.grant_zip(destination)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            preview = self.dispatch("pack.preview", {"staged_id": staged_id})
        self.assertFalse(preview["ok"])
        self.assertEqual(preview["error"]["code"], "PACK_REJECTED")
        self.assertIn(PATH, preview["error"]["message"])
        self.assertIn(f"{len(text):,}", preview["error"]["message"])
        authoring = [item for item in caught if issubclass(item.category, packs.PackAuthoringWarning)]
        self.assertEqual(len(authoring), 1, "preview must surface the authoring warning before refusing")
        self.assertIn(PATH, str(authoring[0].message))
        self.assertIn(f"{len(text):,}", str(authoring[0].message))

        imported = self.dispatch("pack.import", {"staged_id": staged_id, "mode": "fresh"})
        self.assertFalse(imported["ok"])
        self.assertEqual(imported["error"]["code"], "PACK_REJECTED")
        for table in ("packs", "courses", "objectives", "lesson_runs", "lesson_segments"):
            self.assertEqual(int(self.scalar(f"SELECT COUNT(*) FROM {table}")), 0, table)


if __name__ == "__main__":
    unittest.main()
