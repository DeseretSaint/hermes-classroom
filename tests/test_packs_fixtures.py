"""Fixture validation: the demo packs match their builder, honour the L0 script policy, and
never place the answer key on a learner page."""

from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path

from coursebook import archive, packs

ROOT = Path(__file__).resolve().parent.parent
PACKS = ROOT / "bundled" / "packs"
JAPANESE = PACKS / "japanese-affection-context-l0"
PARENT = PACKS / "parent-measurement-practice"
BUILDER = PACKS / "build_demo_packs.py"

CJK = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
LATIN = re.compile(r"[A-Za-z]{2,}")


def load_builder():
    spec = importlib.util.spec_from_file_location("coursebook_demo_pack_builder", BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the demo pack builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = load_builder()

    def test_committed_manifests_match_the_builder(self) -> None:
        for directory, build in ((JAPANESE, self.builder.japanese_manifest), (PARENT, self.builder.parent_manifest)):
            with self.subTest(pack=directory.name):
                committed = packs.load_manifest(directory / "pack.json")
                self.assertEqual(committed, build(), "rebuild bundled/packs/*/pack.json; it is stale")

    def test_committed_visual_matches_the_deterministic_generator(self) -> None:
        committed = (JAPANESE / "content" / "relationship-map.png").read_bytes()
        self.assertEqual(committed, self.builder.relationship_map_png())
        self.assertTrue(committed.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_both_packs_pass_the_content_audit(self) -> None:
        for directory in (JAPANESE, PARENT):
            with self.subTest(pack=directory.name):
                self.assertEqual(packs.audit_bundle(directory), [])
                manifest, files = archive.read_directory(directory)
                packs.validate_manifest(manifest)
                packs.validate_minima(manifest)
                self.assertTrue(files)


class JapanesePackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest, cls.files = archive.read_directory(JAPANESE)

    def learner_texts(self) -> dict[str, str]:
        return {
            entry["path"]: (JAPANESE / entry["path"]).read_text(encoding="utf-8")
            for entry in self.manifest["files"]
            if entry["role"] in packs.LEARNER_FACING_ROLES and entry["mime"].startswith("text/")
        }

    def test_script_policy_every_japanese_line_carries_romaji(self) -> None:
        texts = self.learner_texts()
        self.assertTrue(texts)
        for path, text in texts.items():
            for number, line in enumerate(text.splitlines(), start=1):
                if CJK.search(line):
                    with self.subTest(file=path, line=number):
                        self.assertRegex(line, LATIN, "Japanese text without romaji on the same line")

    def test_every_japanese_string_has_romaji_and_an_english_gloss_nearby(self) -> None:
        section = self.files["content/section-02-choosing.md"].decode("utf-8")
        rows = [line for line in section.splitlines() if line.startswith("|") and CJK.search(line)]
        self.assertEqual(len(rows), 4)
        for row in rows:
            cells = [cell.strip() for cell in row.strip("|").split("|")]
            self.assertEqual(len(cells), 5)
            self.assertTrue(CJK.search(cells[2]))
            self.assertRegex(cells[3], r"^[a-z ]+$")  # romaji column
            self.assertTrue(cells[4])  # English meaning

    def test_answer_key_never_appears_on_a_learner_page(self) -> None:
        texts = self.learner_texts()
        for objective in self.manifest["objectives"]:
            for check in objective["checks"]:
                answer = check["reference_answer"]
                for path, text in texts.items():
                    with self.subTest(check=check["check_id"], file=path):
                        self.assertNotIn(answer, text)

    def test_checks_cover_discrimination_selection_recall_and_transfer(self) -> None:
        targets = [
            check["evidence_target"]
            for objective in self.manifest["objectives"]
            for check in objective["checks"]
        ]
        self.assertEqual(targets, ["discrimination", "comprehension", "recall", "transfer"])
        for objective in self.manifest["objectives"]:
            for check in objective["checks"]:
                self.assertGreaterEqual(len(check["rubric"]), 3)
                self.assertEqual(check["audit_state"], "unreviewed")
                self.assertTrue(check["reference_answer"])
                self.assertTrue(check["stimulus"])

    def test_sources_are_fresh_linked_and_rights_aware(self) -> None:
        sources = self.manifest["sources"]
        self.assertGreaterEqual(len(sources), 5)
        for source in sources:
            with self.subTest(source=source["source_id"]):
                self.assertTrue(source["url"].startswith("https://"))
                self.assertEqual(source["fetched_at"], "2026-11-06")
                self.assertFalse(source.get("bundled", False))
                self.assertTrue(source["publisher"])
                self.assertTrue(source["license_note"])
                self.assertIn(
                    source["support_status"],
                    {"unassessed", "model_assessed", "conflicting", "authoritative_documentation", "stale", "unreachable"},
                )
        statuses = {source["support_status"] for source in sources}
        self.assertIn("authoritative_documentation", statuses)
        self.assertIn("model_assessed", statuses)

    def test_no_native_speaker_review_is_claimed(self) -> None:
        self.assertNotIn("human_review_recorded", packs.trust_labels(
            self.manifest, integrity_verified=True, automated_checks_passed=True
        ))
        self.assertNotIn("reviewed_by", self.manifest.get("trust", {}))
        notes = " ".join(self.manifest["content_notes"])
        self.assertIn("No native-speaker review is recorded", notes)
        self.assertNotIn("native-speaker reviewed", notes)

    def test_register_variants_are_present_and_contextual(self) -> None:
        text = self.files["content/section-02-choosing.md"].decode("utf-8")
        for phrase in ("suki da yo", "suki desu", "daisuki", "aishiteru"):
            self.assertIn(phrase, text)
        for cue in ("friend", "respect", "partner", "casual", "polite", "intimate"):
            self.assertIn(cue, text.lower())

    def test_relationship_visual_has_a_text_equivalent(self) -> None:
        visual = next(entry for entry in self.manifest["files"] if entry["role"] == "visual")
        self.assertEqual(visual["mime"], "image/png")
        self.assertIn("register", visual["text_equivalent"].lower())
        self.assertTrue(visual["text_equivalent"])
        self.assertTrue(any(item["path"] == visual["path"] for item in self.manifest["license"]["per_artifact"]))

    def test_licence_is_unset_for_local_use_not_assumed(self) -> None:
        self.assertEqual(self.manifest["license"]["id"], "unspecified")
        self.assertEqual(self.manifest["license"]["redistribution"], "local_only")
        self.assertIn("operator has not chosen", self.manifest["license"]["note"])

    def test_narration_asset_is_declared_licensed_and_not_a_stub(self) -> None:
        narration = next(entry for entry in self.manifest["files"] if entry["role"] == "narration")
        self.assertEqual(narration["mime"], "audio/mpeg")
        self.assertGreater(narration["bytes"], 4096)
        data = self.files[narration["path"]]
        self.assertEqual(len(data), narration["bytes"])
        self.assertEqual(packs.file_sha256(data), narration["sha256"])
        # Not an all-zero placeholder: encoded speech carries many distinct byte values.
        self.assertGreater(len(set(data[256:])), 100)
        rights = {item["path"]: item for item in self.manifest["license"]["per_artifact"]}
        self.assertIn(narration["path"], rights)
        self.assertEqual(rights[narration["path"]]["license_id"], "Apache-2.0")
        self.assertIn("Kokoro-82M", rights[narration["path"]]["attribution"])
        # L0 scaffold: the text equivalent carries script, romaji and English.
        self.assertIn("好きです", narration["text_equivalent"])
        self.assertIn("suki desu", narration["text_equivalent"])
        self.assertIn("I like you", narration["text_equivalent"])

    def test_audio_note_claims_only_what_the_pack_implements(self) -> None:
        notes = " ".join(self.manifest["safety_notes"])
        self.assertNotIn("No audio is bundled", notes)  # stale claim, no longer true
        self.assertIn("synthetic", notes)
        self.assertIn("no listening evidence is claimed", notes)
        for claim in ("pronunciation score is claimed", "native-speaker reviewed", "voice is certified"):
            self.assertNotIn(claim, notes)
        # No check scores listening: every evidence target stays production/recognition based.
        for objective in self.manifest["objectives"]:
            for check in objective["checks"]:
                self.assertNotIn(check["evidence_target"], {"listening", "pronunciation"})


class ParentPackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest, cls.files = archive.read_directory(PARENT)

    def test_learner_page_has_no_answers(self) -> None:
        learner = self.files["content/learner-page.md"].decode("utf-8")
        answers = [
            check["reference_answer"]
            for objective in self.manifest["objectives"]
            for check in objective["checks"]
        ]
        self.assertEqual(answers, ["150 ml", "350 ml"])
        for answer in answers:
            self.assertNotIn(answer, learner)
        self.assertEqual(learner.count("____________"), 2)

    def test_answer_guide_holds_every_answer(self) -> None:
        guide = self.files["content/answer-guide.md"].decode("utf-8")
        for objective in self.manifest["objectives"]:
            for check in objective["checks"]:
                self.assertIn(check["reference_answer"], guide)

    def test_parent_guide_is_a_script_not_an_answer_sheet(self) -> None:
        guide = self.files["content/parent-guide.md"].decode("utf-8")
        for objective in self.manifest["objectives"]:
            for check in objective["checks"]:
                self.assertNotIn(check["reference_answer"], guide)
        self.assertIn("approved", guide.lower())
        self.assertIn("guided work", guide.lower())

    def test_parent_recipe_is_declared(self) -> None:
        self.assertEqual(self.manifest["recipe"], "parent")
        roles = {entry["role"] for entry in self.manifest["files"]}
        self.assertEqual(roles, {"learner_page", "answer_guide", "parent_guide"})
        self.assertEqual(self.manifest["license"]["redistribution"], "local_only")


if __name__ == "__main__":
    unittest.main()
