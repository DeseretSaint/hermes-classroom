"""D1: a long section file must never become an unreadable lesson page.

``cb.rpc`` v6 caps one ``lesson.page`` segment at 8,000 characters and one page at 500 segments;
``cb.pack`` allows a section file of 32 MB. Import reconciles the two by cutting long section text
into ordered pieces, and refuses (before writing anything) a lesson that could never fit the page.
These tests pin the boundary at 7,999 / 8,001 characters, the split's exactness, the refusal, and
the repair of text stored by a build that predates the cap.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from coursebook import archive, db, packs, segments
from tests.kernel_support import KernelCase
from tests.test_pack_flow import PackFlowCase

ROOT = Path(__file__).resolve().parent.parent
JAPANESE = ROOT / "bundled" / "packs" / "japanese-affection-context-l0"


def section_text(characters: int, *, heading: str = "## Lesson one") -> str:
    """Markdown of exactly ``characters`` characters, built from real paragraph boundaries."""
    text = heading + "\n\n"
    index = 0
    while len(text) < characters:
        text += (
            f"Paragraph {index}: the register you choose names the addressee and the relationship.\n\n"
        )
        index += 1
    return text[:characters]


def manifest_for(section_bytes: dict[str, bytes], pack_id: str = "cap-boundary-pack") -> dict:
    objectives = []
    for index, path in enumerate(sorted(section_bytes), start=1):
        objectives.append(
            {
                "objective_id": f"obj-cap-{index:02d}",
                "ordinal": index,
                "title": f"Long section {index}",
                "evidence_target": "comprehension",
                "evidence_criteria": [
                    "Names the addressee and the relationship",
                    "Chooses a register and says why",
                    "Transfers the reasoning to one new setting",
                ],
                "estimated_minutes": 8,
                "sections": [{"section_id": f"sec-cap-{index:02d}", "title": f"Section {index}", "path": path}],
                "checks": [
                    {
                        "check_id": f"chk-cap-{index:02d}",
                        "version": 1,
                        "evidence_target": "comprehension",
                        "stimulus": "Which register do you choose, and which word carries the politeness?",
                        "reference_answer": "the formal business register",
                        "accepted_alternatives": ["formal", "business register"],
                        "rubric": [
                            "Chooses the formal business register",
                            "Names the addressee and the relationship",
                            "Does not use the casual form for a first meeting",
                        ],
                        "audit_state": "unreviewed",
                    }
                ],
            }
        )
    return packs.build_manifest(
        pack_id=pack_id,
        pack_version="1.0.0",
        title="Segment cap boundary fixture",
        recipe="casual",
        minimum_coursebook_version="0.1.0",
        license={"id": "unspecified", "note": "test fixture", "redistribution": "local_only"},
        attribution="Original text written for the D1 boundary test.",
        objectives=objectives,
        files=section_bytes,
        file_metadata={path: {"mime": "text/markdown", "role": "section"} for path in section_bytes},
    )


class SplitTest(unittest.TestCase):
    """The splitter itself: exact, ordered, bounded, and kind to headings and code fences."""

    def test_a_short_section_is_one_piece(self) -> None:
        self.assertEqual(segments.split_text(section_text(7999)), [section_text(7999)])

    def test_pieces_are_bounded_and_concatenate_back_to_the_source(self) -> None:
        text = section_text(8001)
        pieces = segments.split_text(text)
        self.assertGreater(len(pieces), 1)
        for piece in pieces:
            self.assertLessEqual(len(piece), segments.max_segment_chars())
        self.assertEqual("".join(pieces), text)

    def test_a_single_unbroken_line_is_hard_cut_without_losing_a_character(self) -> None:
        text = "x" * 20001
        pieces = segments.split_text(text)
        self.assertEqual("".join(pieces), text)
        self.assertEqual([len(piece) for piece in pieces], [8000, 8000, 4001])

    def test_a_code_fence_is_not_split_and_a_heading_is_not_stranded(self) -> None:
        filler = "Paragraph before the code.\n\n"
        fence = "```python\n" + ("value = 1\n" * 450) + "```\n\n"
        text = section_text(7600) + filler + fence + section_text(6000, heading="## After the code")
        pieces = segments.split_text(text)
        self.assertEqual("".join(pieces), text)
        for piece in pieces:
            self.assertEqual(piece.count("```") % 2, 0, "a piece must not end inside a code fence")
            last = [line for line in piece.rstrip().splitlines() if line.strip()][-1]
            self.assertFalse(last.startswith("#"), f"piece ends on a stranded heading: {last!r}")

    def test_a_fence_longer_than_the_cap_is_still_bounded_and_exact(self) -> None:
        # A single fenced block cannot be both whole and <= 8,000 characters. Cutting it is the
        # only way to keep the page readable; the text is still preserved byte for byte.
        text = "```python\n" + ("value = 1\n" * 1200) + "```\n"
        pieces = segments.split_text(text)
        self.assertEqual("".join(pieces), text)
        for piece in pieces:
            self.assertLessEqual(len(piece), segments.max_segment_chars())

    def test_the_caps_come_from_the_contract(self) -> None:
        self.assertEqual(segments.lesson_page_caps(), (8000, 500))


class SectionBoundaryImportTest(PackFlowCase):
    """A pack section at the cap boundary imports and reads; each objective page is contract-legal."""

    def import_zip(self, section_bytes: dict[str, bytes], name: str = "cap.zip") -> dict:
        manifest = manifest_for(section_bytes)
        destination = self.work / name
        archive.write_archive(destination, manifest, {path: data for path, data in section_bytes.items()})
        staged_id = self.grant_zip(destination)
        return self.import_pack(staged_id)["result"]

    def teaching_text(self, enrollment_id: str, objective_id: str) -> list[str]:
        page = self.ok(
            "lesson.page", {"enrollment_id": enrollment_id, "objective_id": objective_id}
        )["result"]
        return [segment["text"] for segment in page["segments"] if segment["kind"] == "teaching"]

    def objective_id(self, result: dict, ordinal: int) -> str:
        outline = self.ok("course.outline", {"enrollment_id": result["enrollment_id"]})["result"]
        match = [item for item in outline["objectives"] if item["ordinal"] == ordinal]
        self.assertTrue(match, f"objective {ordinal} missing from the outline")
        return match[0]["objective_id"]

    def test_a_7999_character_section_is_one_segment_and_reads(self) -> None:
        text = section_text(7999)
        result = self.import_zip({"content/long.md": text.encode("utf-8")}, name="7999.zip")
        teaching = self.teaching_text(result["enrollment_id"], self.objective_id(result, 1))
        self.assertEqual(teaching, [text])

    def test_a_8001_character_section_is_split_and_reads(self) -> None:
        text = section_text(8001)
        result = self.import_zip({"content/long.md": text.encode("utf-8")}, name="8001.zip")
        teaching = self.teaching_text(result["enrollment_id"], self.objective_id(result, 1))
        self.assertGreater(len(teaching), 1, "an 8,001-character section must be cut into pieces")
        for piece in teaching:
            self.assertLessEqual(len(piece), segments.max_segment_chars())
        self.assertEqual("".join(teaching), text, "the split must not lose or rewrite a character")

        stored = self.rows(
            "SELECT ordinal, text FROM lesson_segments WHERE kind = 'teaching' ORDER BY ordinal"
        )
        self.assertEqual([row["ordinal"] for row in stored], list(range(1, len(stored) + 1)))

    def test_the_lesson_page_of_a_split_section_is_contract_valid(self) -> None:
        # ok() runs the real response contract check, so this pins "no INTERNAL_ERROR from a
        # successful import" for the exact fixture Sentinel reported.
        text = section_text(47000)
        result = self.import_zip({"content/huge.md": text.encode("utf-8")}, name="47000.zip")
        for ordinal in (1,):
            teaching = self.teaching_text(result["enrollment_id"], self.objective_id(result, ordinal))
            self.assertEqual("".join(teaching), text)

    def test_a_lesson_that_could_not_fit_the_page_is_refused_before_any_write(self) -> None:
        limit, budget = segments.lesson_page_caps()
        text = section_text(limit * budget + 1)
        manifest = manifest_for({"content/too-long.md": text.encode("utf-8")})
        destination = self.work / "too-long.zip"
        archive.write_archive(destination, manifest, {"content/too-long.md": text.encode("utf-8")})
        staged_id = self.grant_zip(destination)

        refusal = self.dispatch("pack.preview", {"staged_id": staged_id})
        self.assertFalse(refusal["ok"])
        self.assertEqual(refusal["error"]["code"], "PACK_REJECTED")
        message = refusal["error"]["message"]
        self.assertIn("content/too-long.md", message)
        self.assertIn(f"{len(text):,}", message)
        self.assertIn(f"{limit:,}", message)
        self.assertIn(f"{budget}", message)

        imported = self.dispatch("pack.import", {"staged_id": staged_id, "mode": "fresh"})
        self.assertFalse(imported["ok"])
        self.assertEqual(imported["error"]["code"], "PACK_REJECTED")
        for table in ("packs", "courses", "objectives", "lesson_runs", "lesson_segments"):
            self.assertEqual(int(self.scalar(f"SELECT COUNT(*) FROM {table}")), 0, table)


class StoredTextRepairTest(PackFlowCase):
    """Text stored by the pre-fix build becomes readable without a re-import."""

    def test_an_over_cap_stored_segment_is_cut_in_place_and_reads(self) -> None:
        staged_id, _manifest = self.grant(JAPANESE)
        result = self.import_pack(staged_id)["result"]
        enrollment_id = result["enrollment_id"]
        objective_id = self.ok("course.outline", {"enrollment_id": enrollment_id})["result"]["objectives"][0][
            "objective_id"
        ]
        run_id = self.scalar(
            "SELECT id FROM lesson_runs WHERE enrollment_id = ? AND objective_id = ?",
            (enrollment_id, objective_id),
        )
        # Reproduce exactly what the old writer produced: the whole section as ONE teaching row.
        long_text = section_text(24000)
        self.execute(
            "DELETE FROM lesson_segments WHERE lesson_run_id = ? AND kind = 'teaching'", (run_id,)
        )
        self.execute(
            "INSERT INTO lesson_segments (id, lesson_run_id, ordinal, kind, text, created_at)"
            " VALUES ('seg_legacy_overlong', ?, 1, 'teaching', ?,"
            " '2026-11-06T00:00:00.000000+00:00')",
            (run_id, long_text),
        )
        # A database that predates the fix has never run the repair.
        self.execute("PRAGMA user_version = 0")

        before = self.dispatch(
            "lesson.page", {"enrollment_id": enrollment_id, "objective_id": objective_id}
        )
        self.assertTrue(before["ok"], f"lesson.page still unreadable after repair: {before.get('error')}")
        teaching = [segment["text"] for segment in before["result"]["segments"] if segment["kind"] == "teaching"]
        self.assertGreater(len(teaching), 1)
        for piece in teaching:
            self.assertLessEqual(len(piece), segments.max_segment_chars())
        self.assertEqual("".join(teaching), long_text)
        self.assertEqual(int(self.scalar("PRAGMA user_version")), db.SEGMENT_REPAIR_MARKER)

        # Idempotent: a second read re-runs nothing and does not multiply the rows.
        count = int(self.scalar("SELECT COUNT(*) FROM lesson_segments WHERE lesson_run_id = ?", (run_id,)))
        again = self.ok(
            "lesson.page", {"enrollment_id": enrollment_id, "objective_id": objective_id}
        )["result"]
        self.assertEqual(
            "".join(segment["text"] for segment in again["segments"] if segment["kind"] == "teaching"),
            long_text,
        )
        self.assertEqual(
            int(self.scalar("SELECT COUNT(*) FROM lesson_segments WHERE lesson_run_id = ?", (run_id,))),
            count,
        )


class RepairScopeTest(KernelCase):
    def test_a_fresh_database_records_the_repair_marker_once(self) -> None:
        self.assertEqual(int(self.scalar("PRAGMA user_version")), 0)
        db.ensure_schema()
        self.assertEqual(int(self.scalar("PRAGMA user_version")), db.SEGMENT_REPAIR_MARKER)
        db.ensure_schema()
        self.assertEqual(int(self.scalar("PRAGMA user_version")), db.SEGMENT_REPAIR_MARKER)


if __name__ == "__main__":
    unittest.main()
